# keep_alive.py
from aiohttp import web
import asyncio

async def handle(request):
    return web.Response(text="Bot is alive!")

async def run_web():
    app = web.Application()
    app.add_routes([web.get("/", handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("🌐 Keep-alive server started on port 8080")
    # this coroutine returns, but site keeps running in loop
