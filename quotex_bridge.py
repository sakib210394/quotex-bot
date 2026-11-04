import asyncio, json, os, ssl, websockets, logging
from playwright.async_api import async_playwright

EMAIL = os.environ.get("QUOTEX_EMAIL", "")
PASSWORD = os.environ.get("QUOTEX_PASSWORD", "")
ASSET = "USDBDT_otc"
SESSION_FILE = "/tmp/qx_session.json"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class QuotexAPI:
    def __init__(self):
        self.candles = []
        self.session = None
        self.running = False

    async def get_session_playwright(self):
        log.info("🌐 Playwright login starting...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox','--disable-setuid-sandbox',
                      '--disable-dev-shm-usage','--disable-gpu']
            )
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"
            )
            page = await ctx.new_page()
            
            for host in ["qxbroker.com","quotex.io","market-qx.info"]:
                try:
                    log.info(f"Trying {host}...")
                    await page.goto(f"https://{host}/en/sign-in", timeout=30000)
                    await page.wait_for_timeout(2000)
                    
                    # Login
                    await page.fill('input[type="email"]', EMAIL)
                    await page.fill('input[type="password"]', PASSWORD)
                    await page.click('button[type="submit"]')
                    await page.wait_for_timeout(5000)
                    
                    # Cookies নাও
                    cookies = await ctx.cookies()
                    if cookies:
                        cookie_str = "; ".join(
                            f"{c['name']}={c['value']}" for c in cookies
                        )
                        ssid = next(
                            (c['value'] for c in cookies 
                             if c['name'] in ['token','ssid','session','auth']),
                            None
                        )
                        session = {
                            "cookies": cookie_str,
                            "ssid": ssid,
                            "host": host
                        }
                        with open(SESSION_FILE, "w") as f:
                            json.dump(session, f)
                        log.info(f"✅ Session saved! SSID: {ssid}")
                        await browser.close()
                        return session
                except Exception as e:
                    log.error(f"✗ {host}: {e}")
                    continue
            
            await browser.close()
            return None

    async def load_or_create_session(self):
        if os.path.exists(SESSION_FILE):
            with open(SESSION_FILE) as f:
                self.session = json.load(f)
                log.info(f"Session loaded from file")
                return True
        
        self.session = await self.get_session_playwright()
        return self.session is not None

    async def connect_ws(self):
        if not self.session:
            return
            
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        
        host = self.session.get("host", "qxbroker.com")
        cookie = self.session.get("cookies", "")
        
        ws_urls = [
            f"wss://ws2.{host}/socket.io/?EIO=3&transport=websocket",
            f"wss://ws2.quotex.io/socket.io/?EIO=3&transport=websocket",
            f"wss://ws2.market-qx.info/socket.io/?EIO=3&transport=websocket",
        ]
        
        for url in ws_urls:
            try:
                log.info(f"WS trying: {url}")
                headers = {
                    "Cookie": cookie,
                    "Origin": f"https://{host}",
                    "User-Agent": "Mozilla/5.0 Chrome/120"
                }
                async with websockets.connect(
                    url, extra_headers=headers,
                    ssl=ssl_ctx, open_timeout=20
                ) as ws:
                    log.info(f"✅ WS Connected: {url}")
                    await ws.recv()  # handshake
                    await ws.recv()  # connected
                    
                    # Subscribe candles
                    await ws.send(
                        f'42["instruments/update",{{"asset":"{ASSET}","period":60}}]'
                    )
                    await asyncio.sleep(1)
                    await ws.send(
                        f'42["candles/subscribe",{{"asset":"{ASSET}","period":60,"offset":4800}}]'
                    )
                    
                    log.info("📡 Listening for candles...")
                    async for msg in ws:
                        if msg in ("2","3"):
                            await ws.send("3")
                            continue
                        self._parse(msg)
                        
            except Exception as e:
                log.error(f"WS failed {url}: {e}")
                continue

    def _parse(self, msg):
        try:
            if not msg.startswith("42"): return
            data = json.loads(msg[2:])
            ev = data[0]; pl = data[1] if len(data)>1 else {}
            if "candles" in ev:
                raw = pl.get("data", [])
                for c in raw: self.candles.append(c)
                self.candles = self.candles[-100:]
                log.info(f"✅ Candles: {len(self.candles)}")
            elif "generated" in ev:
                self.candles.append(pl)
                self.candles = self.candles[-100:]
                log.info(f"New candle: price={pl.get('close','?')}")
        except: pass

    async def start(self):
        while True:
            try:
                ok = await self.load_or_create_session()
                if not ok:
                    log.error("Session failed, retry in 30s")
                    await asyncio.sleep(30)
                    continue
                await self.connect_ws()
            except Exception as e:
                log.error(f"Error: {e}")
            log.info("Reconnecting in 10s...")
            await asyncio.sleep(10)
            # Session refresh
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)

api = QuotexAPI()
