import asyncio, logging, time
import yfinance as yf

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

SYMBOLS = {
    "EURUSD":  "EURUSD=X",
    "GBPUSD":  "GBPUSD=X",
    "USDJPY":  "USDJPY=X",
    "USDCAD":  "USDCAD=X",
    "AUDUSD":  "AUDUSD=X",
    "EURJPY":  "EURJPY=X",
    "GBPJPY":  "GBPJPY=X",
    "USDBDT":  "BDT=X",
}

class QuotexAPI:
    def __init__(self):
        self.candles = []
        self.market_candles = {s: [] for s in SYMBOLS.keys()}

    def fetch_candles(self, name, ticker):
        try:
            data = yf.download(
                ticker, period="1d",
                interval="1m", progress=False,
                auto_adjust=True
            )
            if data.empty: return []
            candles = []
            for idx, row in data.iterrows():
                try:
                    candles.append({
                        "time":  int(idx.timestamp()),
                        "open":  float(row["Open"]),
                        "high":  float(row["High"]),
                        "low":   float(row["Low"]),
                        "close": float(row["Close"]),
                    })
                except: pass
            log.info(f"{name}: {len(candles)} candles, price={candles[-1]['close'] if candles else '?'}")
            return candles
        except Exception as e:
            log.error(f"{name} error: {e}")
            return []

    async def start(self):
        log.info("Yahoo Finance data source starting...")
        while True:
            try:
                await self.update_all()
            except Exception as e:
                log.error(f"Update error: {e}")
            log.info("Next update in 60s...")
            await asyncio.sleep(60)

    async def update_all(self):
        loop = asyncio.get_event_loop()
        for name, ticker in SYMBOLS.items():
            candles = await loop.run_in_executor(
                None, self.fetch_candles, name, ticker
            )
            if candles:
                self.market_candles[name] = candles
        # Default candles
        for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
            if self.market_candles.get(sym):
                self.candles = self.market_candles[sym]
                break

    def _parse(self, msg): pass

api = QuotexAPI()
