import asyncio, json, ssl, random, string
import websockets
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

SYMBOL = "FX_IDC:USDBDT"

class QuotexAPI:
    def __init__(self):
        self.candles = []

    async def start(self):
        while True:
            try:
                await self.connect_tv()
            except Exception as e:
                log.error(f"Error: {e}")
            log.info("Reconnecting in 5s...")
            await asyncio.sleep(5)

    async def connect_tv(self):
        url = "wss://data.tradingview.com/socket.io/websocket"
        headers = {
            "Origin": "https://www.tradingview.com",
            "User-Agent": "Mozilla/5.0 Chrome/120"
        }
        ssl_ctx = ssl.create_default_context()

        log.info("Connecting TradingView...")
        async with websockets.connect(
            url, extra_headers=headers,
            ssl=ssl_ctx, open_timeout=20
        ) as ws:
            log.info("✅ TradingView Connected!")

            sid = ''.join(random.choices(string.ascii_lowercase, k=12))
            csid = ''.join(random.choices(string.ascii_lowercase, k=12))

            def tv_msg(func, *args):
                d = json.dumps({"m": func, "p": list(args)})
                return f"~m~{len(d)}~m~{d}"

            await ws.send(tv_msg("set_auth_token", "unauthorized_user_token"))
            await ws.send(tv_msg("chart_create_session", csid, ""))
            await ws.send(tv_msg("quote_create_session", sid))
            await ws.send(tv_msg("quote_add_symbols", sid, SYMBOL))
            await ws.send(tv_msg("resolve_symbol", csid, "sds_1",
                f'={{"symbol":"{SYMBOL}","adjustment":"splits"}}'))
            await ws.send(tv_msg("create_series", csid, "s1", "sds_1", "sds_1", "1", 300))

            log.info("📡 Waiting for candle data...")

            async for raw in ws:
                try:
                    parts = raw.split("~m~")
                    for part in parts:
                        if not part or not part.startswith("{"): continue
                        data = json.loads(part)
                        m = data.get("m", "")
                        p = data.get("p", [])

                        if m == "timescale_update" and len(p) > 1:
                            series = p[1]
                            bars = series.get("s1", {}).get("s", [])
                            for bar in bars:
                                v = bar.get("v", [])
                                if len(v) >= 5:
                                    self.candles.append({
                                        "time":  int(v[0]),
                                        "open":  float(v[1]),
                                        "high":  float(v[2]),
                                        "low":   float(v[3]),
                                        "close": float(v[4]),
                                    })
                            self.candles = self.candles[-100:]
                            if self.candles:
                                log.info(f"✅ {len(self.candles)} candles! Price: {self.candles[-1]['close']}")

                        elif m == "du" and len(p) > 1:
                            qt = p[1]
                            lp = qt.get(SYMBOL, {}).get("lp") or qt.get("lp")
                            if lp and self.candles:
                                self.candles[-1]["close"] = float(lp)
                                log.info(f"Price: {lp}")

                except Exception as e:
                    continue

    def _parse(self, msg):
        pass

api = QuotexAPI()
