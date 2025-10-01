from aiohttp import web

async def handle(request):
    return web.Response(text="Bot is alive!")

def keep_alive():
    app = web.Application()
    app.add_routes([web.get("/", handle)])
    web.run_app(app, host="0.0.0.0", port=8080)
