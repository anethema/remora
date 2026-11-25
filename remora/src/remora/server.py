"""Offline dashboard server. Only this process's private SITL child can receive commands."""
import argparse
import asyncio
import json

from aiohttp import web

from .engine import Engine
from .scenario import DEFAULT, PROJECT, load


def create_app(engine, port):
    @web.middleware
    async def local(request, handler):
        hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        origins = {"http://"+host for host in hosts}
        if request.host not in hosts or ("Origin" in request.headers and request.headers["Origin"] not in origins):
            raise web.HTTPForbidden(text="This workbench accepts local requests only")
        try:
            return await handler(request)
        except (ValueError, TypeError) as exc:
            return web.json_response({"error":str(exc)},status=400)

    app = web.Application(middlewares=[local],client_max_size=64*1024)

    async def index(request):
        return web.FileResponse(PROJECT/"web/index.html", headers={"Cache-Control":"no-cache"})

    async def asset(request):
        return web.FileResponse(PROJECT/"web"/request.match_info["file"])

    async def state(request):
        return web.json_response(engine.snapshot())

    async def config(request):
        if request.method == "PUT":
            return web.json_response(engine.configure(await request.json()))
        with engine.lock:
            return web.json_response(engine.config.copy())

    async def action(request):
        data = await request.json()
        if not isinstance(data,dict) or set(data) != {"action"} or not isinstance(data["action"],str):
            raise ValueError("Expected one action name")
        return web.json_response(await asyncio.to_thread(engine.action,data["action"]))

    async def download(request):
        kind = request.match_info["kind"]
        if not engine.snapshot()["run_id"]:
            raise ValueError("Start a simulation before exporting its data")
        if kind == "csv":
            return web.Response(text=engine.csv(),content_type="text/csv")
        return web.json_response(engine.export())

    async def events(request):
        stream = web.WebSocketResponse(heartbeat=20)
        await stream.prepare(request)
        try:
            while not stream.closed:
                await stream.send_json(engine.snapshot())
                try:
                    msg = await stream.receive(timeout=.4)
                    if msg.type in (web.WSMsgType.CLOSE,web.WSMsgType.CLOSED,web.WSMsgType.ERROR):
                        break
                except asyncio.TimeoutError:
                    pass
        except ConnectionError:
            pass
        return stream

    async def cleanup(app):
        await asyncio.to_thread(engine.finish)

    app.router.add_get("/", index)
    app.router.add_get(r"/{file:app\.js|style\.css}", asset)
    app.router.add_get("/api/state", state)
    app.router.add_get("/api/scenario", config)
    app.router.add_put("/api/scenario", config)
    app.router.add_post("/api/action", action)
    app.router.add_get(r"/api/export.{kind:json|csv}", download)
    app.router.add_get("/api/events", events)
    app.on_cleanup.append(cleanup)
    return app


def main():
    parser = argparse.ArgumentParser(description="Start the local Remora simulation workbench")
    parser.add_argument("--scenario", default=str(DEFAULT), help="version 1 scenario YAML")
    parser.add_argument("--port", type=int, default=8765, help="loopback HTTP port (default 8765)")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be 1–65535")
    web.run_app(create_app(Engine(load(args.scenario)),args.port),host="127.0.0.1",port=args.port)


if __name__ == "__main__":
    main()
