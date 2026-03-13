"""
CryptoMind Master Dashboard
Muestra: Market Making Bot + Swing Bot + Order Flow Scalping Bot
Correr con: streamlit run master_dashboard.py
"""

import streamlit as st
import httpx
import os
import hmac
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv(r"C:\Users\jssta\OneDrive\Escritorio\Proyecto crypto\.env")

DEMO_API_KEY = os.getenv("BINANCE_API_KEY")
DEMO_SECRET  = os.getenv("BINANCE_SECRET_KEY")
BASE_URL     = "https://fapi.binance.com"
COINS = ["BTC", "ETH", "SOL", "BNB", "ADA", "XRP"]

st.set_page_config(page_title="CryptoMind", page_icon="🤖", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Rajdhani:wght@400;600;700&display=swap');

* { font-family: 'Rajdhani', sans-serif; }
.stApp { background: #060a0f; }

.terminal {
    font-family: 'Share Tech Mono', monospace;
    background: #0a0f1a;
    border: 1px solid #0ff3;
    border-radius: 4px;
    padding: 16px;
    color: #00ff88;
    font-size: 13px;
}
.card {
    background: linear-gradient(135deg, #0d1117 0%, #0a1628 100%);
    border: 1px solid #1a2940;
    border-radius: 8px;
    padding: 20px;
    position: relative;
    overflow: hidden;
}
.card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, #00ff88, #0088ff, #ff0066);
}
.card-mm::before { background: linear-gradient(90deg, #f0b90b, #ff6b00); }
.card-swing::before { background: linear-gradient(90deg, #00ff88, #00ffcc); }
.card-scalp::before { background: linear-gradient(90deg, #ff0066, #ff6b00); }

.metric-val { font-size: 28px; font-weight: 700; letter-spacing: 1px; }
.metric-label { font-size: 11px; color: #4a6080; text-transform: uppercase; letter-spacing: 2px; }
.green { color: #00ff88; }
.red { color: #ff3366; }
.yellow { color: #f0b90b; }
.blue { color: #4488ff; }
.gray { color: #4a6080; }

.bot-header {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 3px;
    color: #4a6080;
    margin-bottom: 16px;
    border-bottom: 1px solid #1a2940;
    padding-bottom: 8px;
}
.order-row {
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid #0d1520;
    font-size: 14px;
}
.bid-price { color: #00ff88; font-family: 'Share Tech Mono', monospace; }
.ask-price { color: #ff3366; font-family: 'Share Tech Mono', monospace; }
.spread-badge {
    background: #f0b90b22;
    border: 1px solid #f0b90b44;
    color: #f0b90b;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-family: 'Share Tech Mono', monospace;
}
.live-dot {
    display: inline-block;
    width: 8px; height: 8px;
    background: #00ff88;
    border-radius: 50%;
    margin-right: 6px;
    animation: pulse 1.5s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}
.pos-long  { color: #00ff88; font-weight: 700; }
.pos-short { color: #ff3366; font-weight: 700; }
.pos-flat  { color: #4a6080; }

.stMetric { background: transparent !important; }
div[data-testid="stMetricValue"] { font-family: 'Share Tech Mono', monospace; font-size: 22px; }
</style>
""", unsafe_allow_html=True)


# ── API helpers ───────────────────────────────────────────────────────────────

def sign(params):
    sp = dict(sorted(params.items()))
    sig = hmac.new(DEMO_SECRET.encode(), urlencode(sp).encode(), hashlib.sha256).hexdigest()
    sp["signature"] = sig
    return sp

def hdrs():
    return {"X-MBX-APIKEY": DEMO_API_KEY}

def ts():
    return httpx.get(f"{BASE_URL}/fapi/v1/time", timeout=10).json()["serverTime"]

@st.cache_data(ttl=10)
def fetch_balance():
    try:
        r = httpx.get(f"{BASE_URL}/fapi/v2/balance", params=sign({"timestamp": ts()}), headers=hdrs(), timeout=10).json()
        if isinstance(r, list):
            for item in r:
                if item.get("asset") == "USDT":
                    return float(item.get("balance", 0)), float(item.get("availableBalance", 0))
        return 0, 0
    except: return 0, 0

@st.cache_data(ttl=10)
def fetch_positions():
    try:
        r = httpx.get(f"{BASE_URL}/fapi/v2/positionRisk", params=sign({"timestamp": ts()}), headers=hdrs(), timeout=10).json()
        if isinstance(r, list):
            return [p for p in r if abs(float(p.get("positionAmt", 0))) > 0]
        return []
    except: return []

@st.cache_data(ttl=10)
def fetch_open_orders():
    try:
        r = httpx.get(f"{BASE_URL}/fapi/v1/openOrders", params=sign({"timestamp": ts()}), headers=hdrs(), timeout=10).json()
        return r if isinstance(r, list) else []
    except: return []

@st.cache_data(ttl=8)
def fetch_ticker(coin):
    try:
        r = httpx.get(f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={coin}USDT", timeout=5).json()
        bid = float(r["bidPrice"])
        ask = float(r["askPrice"])
        mid = (bid + ask) / 2
        r2  = httpx.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={coin}USDT", timeout=5).json()
        chg = float(r2["priceChangePercent"])
        return mid, bid, ask, chg
    except: return 0, 0, 0, 0

@st.cache_data(ttl=20)
def fetch_volatility(coin):
    try:
        klines = httpx.get(f"https://api.binance.com/api/v3/klines?symbol={coin}USDT&interval=1m&limit=20", timeout=8).json()
        closes = [float(k[4]) for k in klines]
        rets   = [(closes[i]-closes[i-1])/closes[i-1]*100 for i in range(1, len(closes))]
        return round((sum(r**2 for r in rets)/len(rets))**0.5, 4)
    except: return 0

@st.cache_data(ttl=20)
def fetch_funding(coin):
    try:
        r = httpx.get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={coin}USDT&limit=1", timeout=8).json()
        return round(float(r[0]["fundingRate"])*100, 5) if r else 0
    except: return 0

@st.cache_data(ttl=30)
def fetch_fng():
    try:
        r = httpx.get("https://api.alternative.me/fng/?limit=1", timeout=8).json()
        return int(r["data"][0]["value"]), r["data"][0]["value_classification"]
    except: return 50, "Neutral"


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════

st.markdown(f"""
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:24px;">
    <div>
        <div style="font-size:32px; font-weight:700; letter-spacing:3px; color:white">
            CRYPTO<span style="color:#00ff88">MIND</span>
        </div>
        <div style="font-size:12px; color:#4a6080; letter-spacing:4px; text-transform:uppercase">
            Trading Intelligence Platform
        </div>
    </div>
    <div style="text-align:right">
        <div style="font-size:12px; color:#4a6080">
            <span class="live-dot"></span>LIVE — Binance Demo Futures
        </div>
        <div style="font-family:'Share Tech Mono',monospace; font-size:13px; color:#4488ff">
            {datetime.now().strftime('%d/%m/%Y  %H:%M:%S')}
        </div>
    </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# BALANCE + MÉTRICAS GLOBALES
# ══════════════════════════════════════════════════════════════════════════════

balance, available = fetch_balance()
positions = fetch_positions()
open_orders = fetch_open_orders()
fng_score, fng_label = fetch_fng()

total_pnl = sum(float(p.get("unRealizedProfit", 0)) for p in positions)
en_uso = balance - available

c1, c2, c3, c4, c5 = st.columns(5)

with c1:
    st.markdown(f"""<div class="card">
        <div class="metric-label">Balance Total</div>
        <div class="metric-val yellow">${balance:,.2f}</div>
        <div style="font-size:12px;color:#4a6080;margin-top:4px">USDT Demo</div>
    </div>""", unsafe_allow_html=True)

with c2:
    st.markdown(f"""<div class="card">
        <div class="metric-label">Disponible</div>
        <div class="metric-val green">${available:,.2f}</div>
        <div style="font-size:12px;color:#4a6080;margin-top:4px">Libre</div>
    </div>""", unsafe_allow_html=True)

with c3:
    pnl_color = "green" if total_pnl >= 0 else "red"
    pnl_sign  = "+" if total_pnl >= 0 else ""
    st.markdown(f"""<div class="card">
        <div class="metric-label">PnL No Realizado</div>
        <div class="metric-val {pnl_color}">{pnl_sign}${total_pnl:.2f}</div>
        <div style="font-size:12px;color:#4a6080;margin-top:4px">{len(positions)} posiciones</div>
    </div>""", unsafe_allow_html=True)

with c4:
    st.markdown(f"""<div class="card">
        <div class="metric-label">Órdenes Abiertas</div>
        <div class="metric-val blue">{len(open_orders)}</div>
        <div style="font-size:12px;color:#4a6080;margin-top:4px">Límite activas</div>
    </div>""", unsafe_allow_html=True)

with c5:
    fng_color = "green" if fng_score < 30 else "red" if fng_score > 70 else "yellow"
    st.markdown(f"""<div class="card">
        <div class="metric-label">Fear & Greed</div>
        <div class="metric-val {fng_color}">{fng_score}</div>
        <div style="font-size:12px;color:#4a6080;margin-top:4px">{fng_label}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# MARKET MAKING — LIBRO DE ÓRDENES EN VIVO
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""<div class="card card-mm">
    <div class="bot-header">🏦 Market Making Bot — Órdenes Activas</div>
""", unsafe_allow_html=True)

mm_cols1 = st.columns(3) * 2 
for i, coin in enumerate(COINS[:3]):
    with mm_cols1[i]:
        mid, bid_mkt, ask_mkt, chg = fetch_ticker(coin)
        vol   = fetch_volatility(coin)
        fund  = fetch_funding(coin)

        # Calcular spread dinámico (igual que el bot)
        spread = max(0.08, min(0.08 + vol * 2, 0.5))
        our_bid = mid * (1 - spread/100)
        our_ask = mid * (1 + spread/100)
        spread_usd = our_ask - our_bid

        # Posición actual
        pos = next((p for p in positions if p.get("symbol") == f"{coin}USDT"), None)
        pos_amt = float(pos.get("positionAmt", 0)) if pos else 0
        pos_pnl = float(pos.get("unRealizedProfit", 0)) if pos else 0

        pos_class = "pos-long" if pos_amt > 0 else "pos-short" if pos_amt < 0 else "pos-flat"
        pos_label = f"LONG {pos_amt:+.4f}" if pos_amt > 0 else f"SHORT {pos_amt:+.4f}" if pos_amt < 0 else "FLAT"

        chg_color = "#00ff88" if chg >= 0 else "#ff3366"

        st.markdown(f"""
        <div style="background:#060a0f; border:1px solid #1a2940; border-radius:6px; padding:16px; margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:12px;">
                <span style="font-size:18px; font-weight:700; color:white">{coin}/USDT</span>
                <span style="color:{chg_color}; font-size:14px">{chg:+.2f}%</span>
            </div>
            <div style="font-family:'Share Tech Mono',monospace; font-size:20px; color:white; margin-bottom:8px;">
                ${mid:,.4f}
            </div>
            <div style="display:flex; justify-content:space-between; margin:8px 0;">
                <div>
                    <div style="font-size:10px;color:#4a6080;letter-spacing:2px">NUESTRO BID</div>
                    <div class="bid-price">${our_bid:,.4f}</div>
                </div>
                <div style="text-align:center">
                    <div style="font-size:10px;color:#4a6080;letter-spacing:2px">SPREAD</div>
                    <span class="spread-badge">{spread:.3f}%</span>
                </div>
                <div style="text-align:right">
                    <div style="font-size:10px;color:#4a6080;letter-spacing:2px">NUESTRO ASK</div>
                    <div class="ask-price">${our_ask:,.4f}</div>
                </div>
            </div>
            <div style="border-top:1px solid #1a2940; margin-top:10px; padding-top:10px; display:flex; justify-content:space-between;">
                <div>
                    <span style="font-size:10px;color:#4a6080">VOL </span>
                    <span style="font-size:13px;color:#f0b90b">{vol}%</span>
                </div>
                <div>
                    <span style="font-size:10px;color:#4a6080">FUNDING </span>
                    <span style="font-size:13px;color:{'#ff3366' if fund > 0.03 else '#00ff88'}">{fund:.4f}%</span>
                </div>
                <div>
                    <span class="{pos_class}" style="font-size:13px">{pos_label}</span>
                </div>
            </div>
            {'<div style="font-size:12px;color:' + ('#00ff88' if pos_pnl >= 0 else '#ff3366') + ';margin-top:6px">PnL: $' + f"{pos_pnl:+.4f}" + '</div>' if pos_amt != 0 else ''}
        </div>
        """, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# POSICIONES + SWING + SCALPING
# ══════════════════════════════════════════════════════════════════════════════

left, right = st.columns([3, 2])

with left:
    st.markdown("""<div class="card card-swing">
        <div class="bot-header">📈 Posiciones Abiertas (Todos los Bots)</div>
    """, unsafe_allow_html=True)

    if not positions:
        st.markdown('<div style="color:#4a6080;padding:20px;text-align:center">Sin posiciones abiertas</div>', unsafe_allow_html=True)
    else:
        for pos in positions:
            coin     = pos["symbol"].replace("USDT","")
            amt      = float(pos["positionAmt"])
            entry    = float(pos["entryPrice"])
            mark     = float(pos["markPrice"])
            pnl      = float(pos["unRealizedProfit"])
            notional = abs(float(pos["notional"]))
            lev      = pos["leverage"]
            pnl_pct  = (pnl / (notional / int(lev))) * 100 if notional > 0 else 0
            direction = "LONG" if amt > 0 else "SHORT"
            dir_color = "#00ff88" if amt > 0 else "#ff3366"
            pnl_color = "#00ff88" if pnl >= 0 else "#ff3366"
            price_diff = ((mark - entry) / entry * 100) if direction == "LONG" else ((entry - mark) / entry * 100)

            st.markdown(f"""
            <div style="background:#060a0f;border:1px solid #1a2940;border-radius:6px;padding:14px;margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;align-items:center">
                    <div>
                        <span style="font-size:18px;font-weight:700;color:white">{coin}</span>
                        <span style="color:{dir_color};font-size:13px;margin-left:8px;border:1px solid {dir_color};padding:2px 8px;border-radius:4px">{direction} {lev}x</span>
                    </div>
                    <div style="text-align:right">
                        <div style="font-size:20px;font-weight:700;color:{pnl_color}">${pnl:+.2f}</div>
                        <div style="font-size:12px;color:{pnl_color}">{pnl_pct:+.2f}%</div>
                    </div>
                </div>
                <div style="display:flex;gap:20px;margin-top:10px;font-family:'Share Tech Mono',monospace;font-size:12px;color:#4a6080">
                    <span>ENTRADA <span style="color:white">${entry:,.2f}</span></span>
                    <span>ACTUAL <span style="color:white">${mark:,.2f}</span></span>
                    <span>TAMAÑO <span style="color:white">${notional:,.0f}</span></span>
                    <span>DIFF <span style="color:{pnl_color}">{price_diff:+.2f}%</span></span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown("""<div class="card card-scalp">
        <div class="bot-header">⚡ Order Flow — Señales 5m</div>
    """, unsafe_allow_html=True)

    for coin in COINS:
        mid, bid_mkt, ask_mkt, chg = fetch_ticker(coin)
        try:
            klines = httpx.get(f"https://api.binance.com/api/v3/klines?symbol={coin}USDT&interval=5m&limit=20", timeout=8).json()
            closes = [float(k[4]) for k in klines]
            gains  = [max(closes[i]-closes[i-1],0) for i in range(1,len(closes))]
            losses = [max(closes[i-1]-closes[i],0) for i in range(1,len(closes))]
            ag, al = sum(gains[-14:])/14, sum(losses[-14:])/14
            rsi    = round(100-(100/(1+ag/al)),1) if al > 0 else 100

            def ema(d,p):
                k,e=2/(p+1),d[0]
                for x in d[1:]: e=x*k+e*(1-k)
                return e
            ema9  = ema(closes[-20:], 9)
            ema21 = ema(closes[-30:], 21)
            cross = "🟢" if ema9 > ema21 else "🔴"
            rsi_color = "#ff3366" if rsi > 70 else "#00ff88" if rsi < 30 else "#f0b90b"
        except:
            rsi, cross = 50, "⚪"
            rsi_color = "#f0b90b"

        st.markdown(f"""
        <div style="background:#060a0f;border:1px solid #1a2940;border-radius:6px;padding:12px;margin-bottom:8px;">
            <div style="display:flex;justify-content:space-between;align-items:center">
                <span style="font-size:16px;font-weight:700;color:white">{coin}</span>
                <span style="font-family:'Share Tech Mono',monospace;font-size:14px;color:white">${mid:,.2f}</span>
            </div>
            <div style="display:flex;gap:12px;margin-top:8px;font-size:13px;">
                <span style="color:#4a6080">RSI <span style="color:{rsi_color};font-family:'Share Tech Mono',monospace">{rsi}</span></span>
                <span style="color:#4a6080">EMA {cross}</span>
                <span style="color:{'#00ff88' if chg >= 0 else '#ff3366'}">{chg:+.2f}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ÓRDENES LÍMITE ABIERTAS (MARKET MAKER)
# ══════════════════════════════════════════════════════════════════════════════

if open_orders:
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("""<div class="card">
        <div class="bot-header">📋 Órdenes Límite Activas (Market Making)</div>
    """, unsafe_allow_html=True)

    cols_header = st.columns([2,2,2,2,2])
    for col, header in zip(cols_header, ["Par","Lado","Precio","Cantidad","Estado"]):
        col.markdown(f'<span style="font-size:11px;color:#4a6080;letter-spacing:2px">{header}</span>', unsafe_allow_html=True)

    for order in open_orders[:15]:
        symbol = order.get("symbol","").replace("USDT","")
        side   = order.get("side","")
        price  = float(order.get("price",0))
        qty    = float(order.get("origQty",0))
        status = order.get("status","")
        side_color = "#00ff88" if side == "BUY" else "#ff3366"

        cols_row = st.columns([2,2,2,2,2])
        cols_row[0].markdown(f'<span style="color:white;font-weight:600">{symbol}</span>', unsafe_allow_html=True)
        cols_row[1].markdown(f'<span style="color:{side_color}">{side}</span>', unsafe_allow_html=True)
        cols_row[2].markdown(f'<span style="font-family:monospace;color:white">${price:,.4f}</span>', unsafe_allow_html=True)
        cols_row[3].markdown(f'<span style="font-family:monospace;color:#4a6080">{qty:.4f}</span>', unsafe_allow_html=True)
        cols_row[4].markdown(f'<span style="color:#f0b90b">{status}</span>', unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;padding:20px;font-size:11px;color:#1a2940;letter-spacing:3px;text-transform:uppercase;margin-top:20px">
    CryptoMind v2  ·  Market Making  ·  Order Flow Scalping  ·  Swing Trading  ·  Binance Demo Futures
</div>
""", unsafe_allow_html=True)

# Auto-refresh cada 10 segundos
st.markdown("""
<script>
setTimeout(function(){window.location.reload()}, 10000);
</script>
""", unsafe_allow_html=True)
