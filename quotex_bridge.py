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
            log.info("Reconnecting in 15s...")
            await asyncio.sleep(15)

    async def connect_tv(self):
        url = "wss://data.tradingview.com/socket.io/websocket"
        headers = {
            "Origin": "https://www.tradingview.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"
        }
        ssl_ctx = ssl.create_default_context()

        log.info("Connecting TradingView...")
        async with websockets.connect(
            url,
            extra_headers=headers,
            ssl=ssl_ctx,
            open_timeout=30,
            ping_interval=20,
            ping_timeout=10,
        ) as ws:
            log.info("Connected!")

            csid = "cs_" + ''.join(random.choices(string.ascii_lowercase+string.digits, k=10))
            qsid = "qs_" + ''.join(random.choices(string.ascii_lowercase+string.digits, k=10))

            def tv_send(func, *args):
                d = json.dumps({"m": func, "p": list(args)})
                return f"~m~{len(d)}~m~{d}"

            # Auth
            await ws.send(tv_send("set_auth_token", "unauthorized_user_token"))
            await asyncio.sleep(0.5)

            # Sessions
            await ws.send(tv_send("chart_create_session", csid, ""))
            await ws.send(tv_send("quote_create_session", qsid))
            await ws.send(tv_send("quote_set_fields", qsid,
                "ch","chp","lp","lp_time","volume","short_name"))
            await asyncio.sleep(0.5)

            # Subscribe all symbols
            for i, sym in enumerate(SYMBOLS):
                sid = f"s{i+1}"
                await ws.send(tv_send("resolve_symbol", csid, f"sym{i}",
                    f'={{"symbol":"{sym}","adjustment":"splits"}}'))
                await asyncio.sleep(0.2)
                await ws.send(tv_send("create_series", csid, sid,
                    f"sym{i}", f"sym{i}", "1", 200))
                await asyncio.sleep(0.2)
                await ws.send(tv_send("quote_add_symbols", qsid, sym,
                    {"flags":["force_permission"]}))

            log.info(f"Subscribed to {len(SYMBOLS)} markets!")

            async for raw in ws:
                try:
                    # TradingView heartbeat
                    if raw.startswith("~h~"):
                        await ws.send(f"~h~{raw[3:]}")
                        continue

                    # Parse messages
                    idx = 0
                    while idx < len(raw):
                        if raw[idx:idx+3] != "~m~":
                            break
                        idx += 3
                        end = raw.index("~m~", idx)
                        length = int(raw[idx:end])
                        idx = end + 3
                        part = raw[idx:idx+length]
                        idx += length

                        if not part.startswith("{"): continue
                        data = json.loads(part)
                        m = data.get("m", "")
                        p = data.get("p", [])

                        # Candle history
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
                                    self.market_candles[sym] = self.market_candles[sym][-150:]
                                    log.info(f"{sym}: {len(self.market_candles[sym])} candles, price={self.market_candles[sym][-1]['close']}")

                            # Update default candles
                            if self.market_candles.get("FX_IDC:USDBDT"):
                                self.candles = self.market_candles["FX_IDC:USDBDT"]
                            elif self.market_candles.get("FX:EURUSD"):
                                self.candles = self.market_candles["FX:EURUSD"]

                        # Live price update
                        elif m == "du" and len(p) > 1:
                            qt = p[1]
                            for sym in SYMBOLS:
                                info = qt.get(sym, {})
                                lp = info.get("lp")
                                if lp and self.market_candles.get(sym):
                                    self.market_candles[sym][-1]["close"] = float(lp)

                        # Series update (new candle)
                        elif m == "series_completed" and len(p) > 1:
                            log.info(f"Series completed: {p}")

                except Exception as e:
                    log.error(f"Parse error: {e}")
                    continue

    def _parse(self, msg): pass

api = QuotexAPI()
