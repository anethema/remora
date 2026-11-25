"""Share the existing Remora dashboard through an opt-in Gradio Live invite."""
# AP_FLAKE8_CLEAN
import argparse
import asyncio
import contextlib
import fcntl
import json
import os
from pathlib import Path
import secrets
import signal

from aiohttp import ClientError, ClientSession, ClientTimeout, WSMsgType, web

LOCAL = "http://127.0.0.1:8765"
COOKIE = "__Host-remora"
CACHE = Path.home() / ".cache/remora/share"
STATE = CACHE / "session.json"


class SharedDashboard:
    def __init__(self, client):
        self.client = client
        self.origin = None
        self.key = secrets.token_urlsafe(32)

    def valid(self, token):
        return secrets.compare_digest(self.key.encode(), token.encode())

    async def join(self, request):
        if not self.valid(request.match_info["token"]):
            raise web.HTTPForbidden(text="Open the private invite from the host.")
        response = web.HTTPFound("/", headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})
        response.set_cookie(COOKIE, self.key, path="/", secure=True, httponly=True, samesite="Lax")
        raise response

    def authorize(self, request, *, check_origin=False):
        if not self.origin or not self.valid(request.cookies.get(COOKIE, "")):
            raise web.HTTPForbidden(text="Open the complete Remora invite link from the host.")
        if check_origin and request.headers.get("Origin") != self.origin:
            raise web.HTTPForbidden(text="Use the shared Remora dashboard for this action.")

    async def http(self, request):
        changing = request.method in ("POST", "PUT")
        self.authorize(request, check_origin=changing)
        payload = await request.read() if changing else None
        headers = {"Content-Type": "application/json"} if changing else {}
        try:
            async with self.client.request(request.method, LOCAL + request.path, data=payload, headers=headers,
                                           allow_redirects=False) as local:
                result = web.StreamResponse(status=local.status, headers={
                    "Content-Type": local.headers.get("Content-Type", "application/octet-stream"),
                    "Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                    "X-Content-Type-Options": "nosniff",
                })
                await result.prepare(request)
                async for chunk in local.content.iter_chunked(65536):
                    await result.write(chunk)
                return result
        except (ClientError, asyncio.TimeoutError) as exc:
            raise web.HTTPBadGateway(text="The WSL simulator is unavailable.") from exc

    async def events(self, request):
        self.authorize(request, check_origin=True)
        async with self.client.ws_connect(LOCAL + "/api/events", heartbeat=20) as local:
            stream = web.WebSocketResponse(heartbeat=20, max_msg_size=4096)
            await stream.prepare(request)

            async def send_updates():
                try:
                    async for message in local:
                        if message.type != WSMsgType.TEXT:
                            break
                        await stream.send_str(message.data)
                finally:
                    await stream.close()

            sender = asyncio.create_task(send_updates())
            try:
                # Reading the socket processes browser close frames and heartbeat pongs.
                async for _ in stream:
                    await stream.close(code=1008, message=b"Telemetry is read-only; use the dashboard controls.")
            finally:
                sender.cancel()
                with contextlib.suppress(asyncio.CancelledError, ConnectionError, ClientError):
                    await sender
            return stream

    def application(self):
        app = web.Application(client_max_size=64 * 1024)
        app.router.add_get("/join/{token}", self.join)
        for path in ("/", "/app.js", "/design.js", "/style.css", "/api/state", "/api/scenario",
                     "/api/export.json", "/api/export.csv"):
            app.router.add_get(path, self.http)
        app.router.add_put("/api/scenario", self.http)
        app.router.add_post("/api/action", self.http)
        app.router.add_get("/api/events", self.events)
        return app


async def share():
    from gradio.networking import setup_tunnel

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    async with ClientSession(timeout=ClientTimeout(total=50)) as client:
        async with client.get(LOCAL + "/api/state") as response:
            response.raise_for_status()
            if "status" not in await response.json():
                raise ValueError("Start the Remora dashboard on port 8765 first.")
        dashboard = SharedDashboard(client)
        runner = web.AppRunner(dashboard.application(), access_log=None, shutdown_timeout=2)
        await runner.setup()
        try:
            site = web.TCPSite(runner, "127.0.0.1", 0)
            await site.start()
            port = runner.addresses[0][1]
            dashboard.origin = (await asyncio.to_thread(
                setup_tunnel, "127.0.0.1", port, secrets.token_urlsafe(32), None, None
            )).rstrip("/")
            if not dashboard.origin.startswith("https://"):
                raise ValueError("The Gradio sharing service did not return an HTTPS address.")
            invite = f"{dashboard.origin}/join/{dashboard.key}"
            state_tmp = STATE.with_suffix(".tmp")
            state_tmp.write_text(json.dumps({"pid": os.getpid(), "invite": invite}))
            state_tmp.replace(STATE)
            print(invite, flush=True)
            await stop.wait()
        finally:
            STATE.unlink(missing_ok=True)
            await runner.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--url", action="store_true", help="print the active private invite")
    group.add_argument("--stop", action="store_true", help="close the share without stopping the boat simulation")
    args = parser.parse_args()
    os.umask(0o077)
    CACHE.mkdir(mode=0o700, exist_ok=True, parents=True)
    with (CACHE / "share.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if not STATE.exists():
                raise SystemExit("Remora is connecting to Gradio. Try --url again shortly.")
            session = json.loads(STATE.read_text())
            if args.stop:
                os.kill(session["pid"], signal.SIGTERM)
            else:
                print(session["invite"])
            return
        STATE.unlink(missing_ok=True)
        if args.stop or args.url:
            raise SystemExit("No active Remora share.")
        os.chdir(CACHE)  # Gradio stores its tunnel certificate in the working directory.
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(share())


if __name__ == "__main__":
    main()
