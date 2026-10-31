import asyncio, json, os, ssl, websockets
from playwright.async_api import async_playwright

EMAIL = os.environ.get("QUOTEX_EMAIL", "")
PASSWORD = os.environ.get("QUOTEX_PASSWORD", "")
SESSION_FILE = "session.json"

async def get_session():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto("https://qxbroker.com/en/sign-in")
        await page.fill('input[name="email"]', EMAIL)
        await page.fill('input[name="password"]', PASSWORD)
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(5000)
        cookies = await ctx.cookies()
        token = next((c["value"] for c in cookies if c["name"] == "token"), None)
        cookie_str = "; ".join(f"{c['name']}={c['value']}" for c in cookies)
        await browser.close()
        session = {"token": token, "cookies": cookie_str}
        with open(SESSION_FILE, "w") as f:
            json.dump(session, f)
        return session

class QuotexAPI:
    def __init__(self):
        self.candles = []
        self.session = None
        self.ws = None

    async def start(self):
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE) as f:
                self.session = json.load(f)
        else:
            self.session = await get_session()
        await self.connect_ws()

    async def connect_ws(self):
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        headers = {
            "Cookie": self.session["cookies"],
            "Origin": "https://qxbroker.com",
            "User-Agent": "Mozilla/5.0 Chrome/120"
        }
        url = "wss://ws2.qxbroker.com/socket.io/?EIO=3&transport=websocket"
        async with websockets.connect(url, additional_headers=headers,
                ssl=ssl_ctx, open_timeout=20) as ws:
            self.ws = ws
            await ws.recv(); await ws.recv()
            await ws.send('42["instruments/update",{"asset":"USDBDT_otc","period":60}]')
            await asyncio.sleep(1)
            await ws.send('42["candles/subscribe",{"asset":"USDBDT_otc","period":60,"offset":4800}]')
            async for msg in ws:
                if msg in ("2","3"): await ws.send("3"); continue
                self._parse(msg)

    def _parse(self, msg):
        try:
            if not msg.startswith("42"): return
            data = json.loads(msg[2:])
            ev = data[0]; pl = data[1] if len(data)>1 else {}
            if "candles" in ev:
                raw = pl.get("data", [])
                for c in raw:
                    self.candles.append(c)
                self.candles = self.candles[-100:]
            elif "generated" in ev:
                self.candles.append(pl)
                self.candles = self.candles[-100:]
        except: pass

api = QuotexAPI()
