import asyncio
from fastapi import FastAPI, Request
from quotex_bridge import api

app = FastAPI()

def mean(l): return sum(l)/len(l) if l else 0

def ema(d, n):
    a=2/(n+1); r=[d[0]]
    for v in d[1:]: r.append(a*v+(1-a)*r[-1])
    return r

def analyze(candles):
    if len(candles)<15:
        return {"signal":"LOADING","confidence":0,"candles":len(candles)}

    cl=[float(c.get("close",c.get("c",0))) for c in candles]
    hi=[float(c.get("high", c.get("h",0))) for c in candles]
    lo=[float(c.get("low",  c.get("l",0))) for c in candles]
    op=[float(c.get("open", c.get("o",0))) for c in candles]
    up=0; dn=0

    # 1. RSI
    d=[cl[i]-cl[i-1] for i in range(1,len(cl))]
    g=mean([x for x in d[-14:] if x>0] or [0])
    ls=mean([-x for x in d[-14:] if x<0] or [0])
    rsi=100-100/(1+g/(ls+1e-9))
    if rsi<30: up+=20
    elif rsi>70: dn+=20
    elif rsi<45: up+=10
    elif rsi>55: dn+=10

    # 2. MACD
    e12=ema(cl,12); e26=ema(cl,26)
    m=[e12[i]-e26[i] for i in range(len(e26))]
    s=ema(m,9); h=[m[i]-s[i] for i in range(len(s))]
    if len(h)>=2:
        if h[-2]<0 and h[-1]>0: up+=22
        elif h[-2]>0 and h[-1]<0: dn+=22
        elif h[-1]>0: up+=10
        elif h[-1]<0: dn+=10

    # 3. EMA 9/21
    e9=ema(cl,9); e21=ema(cl,21)
    if len(e9)>=2:
        if e9[-2]<e21[-2] and e9[-1]>e21[-1]: up+=18
        elif e9[-2]>e21[-2] and e9[-1]<e21[-1]: dn+=18
        elif e9[-1]>e21[-1]: up+=8
        elif e9[-1]<e21[-1]: dn+=8

    # 4. Bollinger
    if len(cl)>=20:
        sma=mean(cl[-20:])
        std=(sum((x-sma)**2 for x in cl[-20:])/20)**0.5
        p=cl[-1]
        if p<sma-2*std: up+=15
        elif p>sma+2*std: dn+=15

    # 5. Stochastic
    if len(cl)>=14:
        lo14=min(lo[-14:]); hi14=max(hi[-14:])
        sk=(cl[-1]-lo14)/(hi14-lo14+1e-9)*100
        if sk<20: up+=14
        elif sk>80: dn+=14
        elif sk<30: up+=8
        elif sk>70: dn+=8

    # 6. Momentum
    if len(cl)>=6:
        mom=cl[-1]-cl[-6]
        if mom>0: up+=10
        elif mom<0: dn+=10

    # 7. Candle pattern
    if len(cl)>=2:
        lc_bull = cl[-1]>op[-1]
        if lc_bull: up+=8
        else: dn+=8

    tot=up+dn+1e-9
    if up>dn: d2="UP"; cf=int(up/tot*100)
    elif dn>up: d2="DOWN"; cf=int(dn/tot*100)
    else: d2="NEUTRAL"; cf=50

    return {
        "signal":d2, "confidence":cf,
        "candle1":d2,
        "candle2":d2 if cf>=68 else "NEUTRAL",
        "rsi":round(rsi,1),
        "price":cl[-1],
        "up_score":up, "dn_score":dn,
        "trade":d2 if cf>=62 and d2!="NEUTRAL" else "SKIP"
    }

@app.get("/")
def root(): return {"status":"FINORIX PRO API ✅ Running"}

@app.get("/signal")
def signal():
    return analyze(api.candles)

@app.get("/candles")
def candles():
    return {"count":len(api.candles),"data":api.candles[-5:]}

@app.post("/inject")
async def inject(request: Request):
    body = await request.json()
    msg = body.get("data","")
    api._parse(msg)
    return {"ok":True,"candles":len(api.candles)}

@app.on_event("startup")
async def startup():
    asyncio.create_task(api.start())
@app.get("/best-signal")
def best_signal():
    results = []
    for sym, candles in api.market_candles.items():
        if len(candles) >= 15:
            res = analyze(candles)
            res["market"] = sym.replace("FX_IDC:","").replace("FX:","")
            res["symbol"] = sym
            results.append(res)
    if not results:
        return {"error":"No data yet","candles":len(api.candles)}
    best = max(results, key=lambda x: x.get("confidence",0))
    summary = sorted(results, key=lambda x: x.get("confidence",0), reverse=True)
    return {"best":best, "all_markets":summary}
