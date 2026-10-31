import asyncio, json, os, ssl, websockets

EMAIL = os.environ.get("QUOTEX_EMAIL", "")
PASSWORD = os.environ.get("QUOTEX_PASSWORD", "")

# Browser থেকে নেওয়া cookie
COOKIE = "lang=en; __vid1=09697a9396c74d06016039b91a745b09; activeAccount=demo; _ga=GA1.1.396201687.1791633171"

class QuotexAPI:
    def __init__(self):
        self.candles = []

    async def start(self):
        while True:
            try:
                await self.connect_ws()
            except Exception as e:
                print(f"WS error: {e}, retry in 5s")
                await asyncio.sleep(5)

    async def connect_ws(self):
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        headers = {
            "Cookie": COOKIE,
            "Origin": "https://market-qx.info",
            "User-Agent": "Mozilla/5.0 Chrome/120"
        }
        urls = [
            "wss://ws2.market-qx.info/socket.io/?EIO=3&transport=websocket",
            "wss://ws2.qxbroker.com/socket.io/?EIO=3&transport=websocket",
            "wss://ws2.quotex.io/socket.io/?EIO=3&transport=websocket",
        ]
        for url in urls:
            try:
                print(f"Trying: {url}")
                async with websockets.connect(
                    url, additional_headers=headers,
                    ssl=ssl_ctx, open_timeout=20
                ) as ws:
                    print(f"Connected: {url}")
                    await ws.recv()
                    await ws.recv()
                    await ws.send('42["instruments/update",{"asset":"USDBDT_otc","period":60}]')
                    await asyncio.sleep(1)
                    await ws.send('42["candles/subscribe",{"asset":"USDBDT_otc","period":60,"offset":4800}]')
                    async for msg in ws:
                        if msg in ("2","3"):
                            await ws.send("3")
                            continue
                        self._parse(msg)
            except Exception as e:
                print(f"Failed {url}: {e}")
                continue

    def _parse(self, msg):
        try:
            if not msg.startswith("42"): return
            data = json.loads(msg[2:])
            ev = data[0]
            pl = data[1] if len(data)>1 else {}
            if "candles" in ev:
                raw = pl.get("data", [])
                for c in raw:
                    self.candles.append(c)
                self.candles = self.candles[-100:]
                print(f"Candles loaded: {len(self.candles)}")
            elif "generated" in ev:
                self.candles.append(pl)
                self.candles = self.candles[-100:]
                print(f"New candle: {len(self.candles)}")
        except: pass

api = QuotexAPI()
