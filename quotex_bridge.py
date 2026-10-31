import asyncio, json, ssl
import urllib.request
import websockets

COOKIE = "lang=en; _ga=GA1.1.396201687.1791633171; OTCTooltip={%22value%22:false}; balance-visible={%22value%22:true}; nas=[%22USDBDT_otc%22%2C%22EURUSD_otc%22%2C%22EURNZD_otc%22%2C%22EURUSD%22%2C%22AUDUSD%22%2C%22EURJPY%22%2C%22USDJPY%22%2C%22EURGBP%22%2C%22AUDJPY%22%2C%22GBPUSD%22%2C%22NZDUSD_otc%22%2C%22GBPJPY%22%2C%22USDCAD%22%2C%22USDCHF%22%2C%22GBPCAD%22%2C%22XAGUSD_otc%22%2C%22USDIDR_otc%22%2C%22USDJPY_otc%22%2C%22NZDCHF_otc%22%2C%22EURAUD_otc%22%2C%22USDEGP_otc%22%2C%22EURCHF%22%2C%22USDZAR_otc%22%2C%22BTCUSD_otc%22%2C%22AUDCAD%22%2C%22AVAUSD_otc%22%2C%22CADCHF_otc%22%2C%22GBPJPY_otc%22%2C%22GBPCHF_otc%22%2C%22EURCHF_otc%22%2C%22EURJPY_otc%22%2C%22BRLUSD_otc%22%2C%22USDINR_otc%22]; __vid1=09697a9396c74d06016039b91a745b09; _ga_L4T5GBPFHJ=GS2.1.s1793439122$o55$g0$t1793439122$j60$l0$h0; activeAccount=demo; z=[[%22graph%22%2C2%2C1%2C-0.4%2C0.2075]%2C[%22graph%22%2C3%2C11%2C-1.7%2C0.2075]%2C[%22graph%22%2C4%2C19%2C-4.9%2C2.1156]%2C[%22graph%22%2C5%2C14%2C-2.9%2C0.2075]]"

class QuotexAPI:
    def __init__(self):
        self.candles = []

    async def start(self):
        while True:
            try:
                await self.connect_ws()
            except Exception as e:
                print(f"WS error: {e}")
                await asyncio.sleep(5)

    async def connect_ws(self):
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        urls = [
            "wss://ws2.market-qx.info/socket.io/?EIO=3&transport=websocket",
            "wss://ws2.quotex.io/socket.io/?EIO=3&transport=websocket",
        ]

        extra = {
            "Cookie": COOKIE,
            "Origin": "https://market-qx.info",
            "User-Agent": "Mozilla/5.0 Chrome/120"
        }

        for url in urls:
            try:
                print(f"Trying: {url}")
                async with websockets.connect(
                    url,
                    extra_headers=extra,
                    ssl=ssl_ctx,
                    open_timeout=20
                ) as ws:
                    print("Connected!")
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
                print(f"Failed: {e}")

    def _parse(self, msg):
        try:
            if not msg.startswith("42"): return
            data = json.loads(msg[2:])
            ev = data[0]; pl = data[1] if len(data)>1 else {}
            if "candles" in ev:
                raw = pl.get("data", [])
                for c in raw: self.candles.append(c)
                self.candles = self.candles[-100:]
                print(f"Candles: {len(self.candles)}")
            elif "generated" in ev:
                self.candles.append(pl)
                self.candles = self.candles[-100:]
        except: pass

api = QuotexAPI()
