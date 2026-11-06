import asyncio, json, ssl, random, string, logging
import websockets

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

SYMBOLS = [
    "FX_IDC:USDBDT",
    "FX:EURUSD",
    "FX:GBPUSD",
    "FX:USDJPY",
    "FX:USDCAD",
    "FX:AUDUSD",
    "FX:EURJPY",
    "FX:GBPJPY",
]

class QuotexAPI:
    def __init__(self):
        self.candles = []
        self.market_candles = {s: [] for s in SYMBOLS}

    async def start(self):
        while True:
            try:
                await self.connect_tv()
            except Exception as e:
                log.error(f"Error: {e}")
            await asyncio.sleep(5)

    async def connect_tv(self):
        url = "wss://data.tradingview.com/socket.io/websocket"
        headers = {
            "Origin": "https://www.tradingview.com",
            "User-Agent": "Mozilla/5.0 Chrome/120"
        }
        ssl_ctx = ssl.create_default_context()

        log.info("Connecting TradingView multi-market...")
        async with websockets.connect(
            url, extra_headers=headers,
            ssl=ssl_ctx, open_timeout=20
        ) as ws:
            log.info("✅ Connected!")

            csid = ''.join(random.choices(string.ascii_lowercase, k=12))
            qsid = ''.join(random.choices(string.ascii_lowercase, k=12))

            def tv(func, *args):
                d = json.dumps({"m": func, "p": list(args)})
                return f"~m~{len(d)}~m~{d}"

            await ws.send(tv("set_auth_token", "unauthorized_user_token"))
            await ws.send(tv("chart_create_session", csid, ""))
            await ws.send(tv("quote_create_session", qsid))

            # সব symbol subscribe করো
            for i, sym in enumerate(SYMBOLS):
                sid = f"s{i+1}"
                await ws.send(tv("resolve_symbol", csid, f"sym_{i}",
                    f'={{"symbol":"{sym}","adjustment":"splits"}}'))
                await ws.send(tv("create_series", csid, sid,
                    f"sym_{i}", f"sym_{i}", "1", 100))
                await ws.send(tv("quote_add_symbols", qsid, sym))

            log.info(f"📡 Watching {len(SYMBOLS)} markets...")

            async for raw in ws:
                try:
                    parts = raw.split("~m~")
                    for part in parts:
                        if not part or not part.startswith("{"): continue
                        data = json.loads(part)
                        m = data.get("m", "")
                        p = data.get("p", [])

                        if m == "timescale_update" and len(p) > 1:
                            series_data = p[1]
                            for i, sym in enumerate(SYMBOLS):
                                sid = f"s{i+1}"
                                bars = series_data.get(sid, {}).get("s", [])
                                if bars:
                                    for bar in bars:
                                        v = bar.get("v", [])
                                        if len(v) >= 5:
                                            self.market_candles[sym].append({
                                                "time":  int(v[0]),
                                                "open":  float(v[1]),
                                                "high":  float(v[2]),
                                                "low":   float(v[3]),
                                                "close": float(v[4]),
                                            })
                                    self.market_candles[sym] = self.market_candles[sym][-100:]
                                    log.info(f"✅ {sym}: {len(self.market_candles[sym])} candles")

                        # Live price
                        elif m == "du" and len(p) > 1:
                            qt = p[1]
                            for sym in SYMBOLS:
                                lp = qt.get(sym, {}).get("lp")
                                if lp and self.market_candles[sym]:
                                    self.market_candles[sym][-1]["close"] = float(lp)

                        # Default candles (USDBDT)
                        if self.market_candles.get("FX_IDC:USDBDT"):
                            self.candles = self.market_candles["FX_IDC:USDBDT"]

                except Exception:
                    continue

    def _parse(self, msg): pass

api = QuotexAPI()
