import asyncio, math, threading
from fastapi import FastAPI, Request
from quotex_bridge import api

app = FastAPI()

def mean(l): return sum(l)/len(l) if l else 0
def ema(d,n):
    a=2/(n+1);r=[d[0]]
    for v in d[1:]:r.append(a*v+(1-a)*r[-1])
    return r

def analyze(candles):
    if len(candles)<15: return {"signal":"WAIT","confidence":0}
    cl=[float(c.get("close",c.get("c",0))) for c in candles]
    op=[float(c.get("open",c.get("o",0))) for c in candles]
    up=0;dn=0

    # RSI
    d=[cl[i]-cl[i-1] for i in range(1,len(cl))]
    g=mean([x for x in d[-14:] if x>0] or [0])
    ls=mean([-x for x in d[-14:] if x<0] or [0])
    rsi=100-100/(1+g/(ls+1e-9))
    if rsi<30:up+=20
    elif rsi>70:dn+=20
    elif rsi<45:up+=10
    elif rsi>55:dn+=10

    # MACD
    e12=ema(cl,12);e26=ema(cl,26)
    m=[e12[i]-e26[i] for i in range(len(e26))]
    s=ema(m,9);h=[m[i]-s[i] for i in range(len(s))]
    if h[-2]<0 and h[-1]>0:up+=22
    elif h[-2]>0 and h[-1]<0:dn+=22

    # EMA cross
    e9=ema(cl,9);e21=ema(cl,21)
    if e9[-2]<e21[-2] and e9[-1]>e21[-1]:up+=18
    elif e9[-2]>e21[-2] and e9[-1]<e21[-1]:dn+=18

    tot=up+dn+1e-9
    if up>dn:d2="UP";cf=int(up/tot*100)
    elif dn>up:d2="DOWN";cf=int(dn/tot*100)
    else:d2="NEUTRAL";cf=50

    return {
        "signal":d2,"confidence":cf,
        "candle1":d2,"candle2":d2 if cf>=68 else "NEUTRAL",
        "rsi":round(rsi,1),"price":cl[-1],
        "trade":d2 if cf>=62 and d2!="NEUTRAL" else "SKIP"
    }

@app.get("/")
def root(): return {"status":"FINORIX PRO API running"}

@app.get("/signal")
def signal():
    return analyze(api.candles) if len(api.candles)>=15 else {"signal":"LOADING","candles":len(api.candles)}

@app.get("/candles")
def candles(): return {"count":len(api.candles),"data":api.candles[-10:]}

@app.on_event("startup")
async def startup():
    asyncio.create_task(api.start())
from fastapi import Request

@app.post("/inject")
async def inject(request: Request):
    body = await request.json()
    msg = body.get("data", "")
    api._parse(msg)
    return {"ok": True, "candles": len(api.candles)}
