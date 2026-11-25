"""Exercise the share boundary with an in-memory state model and no firmware."""
# AP_FLAKE8_CLEAN
import asyncio

from aiohttp import ClientSession, web
from aiohttp.test_utils import TestClient, TestServer

from remora import share


def test_public_invite_and_shared_controls(monkeypatch):
    async def exercise():
        calls = []

        async def action(request):
            calls.append(await request.json())
            return web.json_response({"state": "shared"})

        app = web.Application()
        app.router.add_post("/api/action", action)
        async with TestServer(app) as local, ClientSession() as session:
            monkeypatch.setattr(share, "LOCAL", str(local.make_url("/")).rstrip("/"))
            dashboard = share.SharedDashboard(session)
            dashboard.origin = "https://remora.example"
            async with TestClient(TestServer(dashboard.application())) as guest:
                assert (await guest.post("/api/action", json={"action": "reset"})).status == 403
                assert (await guest.get("/join/invalid")).status == 403
                joined = await guest.get("/join/" + dashboard.key, allow_redirects=False)
                assert joined.status == 302
                cookie = joined.cookies[share.COOKIE]
                assert cookie["secure"] and cookie["httponly"]
                headers = {"Cookie": share.COOKIE + "=" + cookie.value, "Origin": "https://unrelated.example"}
                assert (await guest.post("/api/action", json={"action": "reset"}, headers=headers)).status == 403
                headers["Origin"] = dashboard.origin
                reply = await guest.post("/api/action", json={"action": "request"}, headers=headers)
                assert (reply.status, await reply.json()) == (200, {"state": "shared"})
                assert calls == [{"action": "request"}]
                assert (await guest.get("/unknown", headers=headers)).status == 404

    asyncio.run(exercise())
