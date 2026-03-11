"""
CryptoMind Dashboard
Interfaz visual para el Futures Bot
Correr con: streamlit run dashboard.py
"""

import streamlit as st
import httpx
import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv
import hmac
import hashlib
from urllib.parse import urlencode

load_dotenv(r"C:\Users\jssta\OneDrive\Escritorio\Proyecto crypto\.env")

DEMO_API_KEY = os.getenv("BINANCE_DEMO_API_KEY")
DEMO_SECRET  = os.getenv("BINANCE_DEMO_SECRET")
BASE_URL     = "https://demo-fapi.binance.com"

st.set_page_config(
    page_title="CryptoMind Bot",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .metric-card {
        background: #1e2329;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        border: 1px solid #2d3139;
    }
    .profit { color: #0ecb81; font-size: 24px; font-weight: bold; }
    .loss   { color: #f6465d; font-size: 24px; font-weight: bold; }
    .coin-header { font-size: 20px; font-weight: bold; color: #f0b90b; }
</style>
""", unsafe_allow_html=True)


def sign_request(params):
    sorted_params = dict(sorted(params.items()))
    query_string  = urlencode(sorted_params)
    signature     = hmac.new(DEMO_SECRET.encode(), query_string.encode(), hashlib.sha256).hexdigest()
    sorted_params["signature"] = signature
    return sorted_params

def get_headers():
    return {"X-MBX-APIKEY": DEMO_API_KEY}

def get_server_time():
    r = httpx.get(f"{BASE_URL}/fapi/v1/time", timeout=10)
    return r.json()["serverTime"]

@st.cache_data(ttl=15)
def get_balance():
    try:
        params = sign_request({"timestamp": get_server_time()})
        r = httpx.get(f"{BASE_URL}/fapi/v2/balance", params=params, headers=get_headers(), timeout=10)
        data = r.json()
        if isinstance(data, list):
            for item in data:
                if item.get("asset") == "USDT":
                    return float(item.get("balance", 0)), float(item.get("availableBalance", 0))
        return 0, 0
    except:
        return 0, 0

@st.cache_data(ttl=15)
def get_positions():
    try:
        params = sign_request({"timestamp": get_server_time()})
        r = httpx.get(f"{BASE_URL}/fapi/v2/positionRisk", params=params, headers=get_headers(), timeout=10)
        data = r.json()
        if isinstance(data, list):
            return [p for p in data if float(p.get("positionAmt", 0)) != 0]
        return []
    except:
        return []

@st.cache_data(ttl=15)
def get_price(coin):
    try:
        r = httpx.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={coin}USDT", timeout=5)
        d = r.json()
        return float(d["lastPrice"]), float(d["priceChangePercent"])
    except:
        return 0, 0

@st.cache_data(ttl=30)
def get_fear_greed():
    try:
        r = httpx.get("https://api.alternative.me/fng/?limit=1", timeout=8)
        d = r.json()["data"][0]
        return int(d["value"]), d["value_classification"]
    except:
        return 50, "Neutral"

@st.cache_data(ttl=30)
def get_rsi(coin):
    try:
        klines = httpx.get(f"https://api.binance.com/api/v3/klines?symbol={coin}USDT&interval=1h&limit=20", timeout=8).json()
        closes = [float(k[4]) for k in klines]
        gains  = [max(closes[i]-closes[i-1], 0) for i in range(1, len(closes))]
        losses = [max(closes[i-1]-closes[i], 0) for i in range(1, len(closes))]
        ag, al = sum(gains[-14:])/14, sum(losses[-14:])/14
        return round(100 - (100/(1+ag/al)), 1) if al > 0 else 100
    except:
        return 0

# Header
st.markdown("# 🤖 CryptoMind Futures Bot")
st.markdown(f"*Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*")
st.markdown("---")

# Balance
balance, available = get_balance()
fng_score, fng_label = get_fear_greed()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("💰 Balance Total", f"${balance:,.2f} USDT")
with col2:
    st.metric("💵 Disponible", f"${available:,.2f} USDT")
with col3:
    st.metric("📊 En Posiciones", f"${balance - available:,.2f} USDT")
with col4:
    color = "🔴" if fng_score < 25 else "🟡" if fng_score < 50 else "🟢"
    st.metric(f"{color} Fear & Greed", f"{fng_score} — {fng_label}")

st.markdown("---")

# Posiciones
st.markdown("## 📈 Posiciones Abiertas")
positions = get_positions()

if not positions:
    st.info("No hay posiciones abiertas actualmente.")
else:
    total_pnl = sum(float(p["unRealizedProfit"]) for p in positions)
    pnl_class = "profit" if total_pnl >= 0 else "loss"
    st.markdown(f"**PnL Total:** <span class='{pnl_class}'>${total_pnl:+.2f} USDT</span>", unsafe_allow_html=True)
    st.markdown("")

    cols = st.columns(max(len(positions), 1))
    for i, pos in enumerate(positions):
        with cols[i]:
            coin     = pos["symbol"].replace("USDT", "")
            amt      = float(pos["positionAmt"])
            entry    = float(pos["entryPrice"])
            mark     = float(pos["markPrice"])
            pnl      = float(pos["unRealizedProfit"])
            notional = float(pos["notional"])
            lev      = pos["leverage"]
            direction = "LONG 📈" if amt > 0 else "SHORT 📉"
            pnl_pct  = (pnl / (abs(notional) / int(lev))) * 100
            pnl_class = "profit" if pnl >= 0 else "loss"

            st.markdown(f"""
            <div class="metric-card">
                <div class="coin-header">{coin}</div>
                <div style="color:#848e9c; margin:4px 0">{direction} | {lev}x</div>
                <div style="font-size:13px;color:#848e9c">Entrada: ${entry:,.2f}</div>
                <div style="font-size:13px;color:#848e9c">Actual: ${mark:,.2f}</div>
                <div style="font-size:13px;color:#848e9c">Tamaño: ${abs(notional):,.0f}</div>
                <div style="margin-top:12px" class="{pnl_class}">${pnl:+.2f} ({pnl_pct:+.2f}%)</div>
            </div>
            """, unsafe_allow_html=True)

st.markdown("---")

# Mercado
st.markdown("## 📊 Mercado en Tiempo Real")
coins = ["BTC", "ETH", "SOL", "BNB"]
cols  = st.columns(4)

for i, coin in enumerate(coins):
    with cols[i]:
        price, change = get_price(coin)
        rsi = get_rsi(coin)
        change_class = "profit" if change >= 0 else "loss"
        change_emoji = "▲" if change >= 0 else "▼"
        rsi_color = "#f6465d" if rsi > 70 else "#0ecb81" if rsi < 30 else "#f0b90b"

        st.markdown(f"""
        <div class="metric-card">
            <div class="coin-header">{coin}/USDT</div>
            <div style="font-size:22px;font-weight:bold;color:white;margin:8px 0">${price:,.2f}</div>
            <div class="{change_class}">{change_emoji} {change:+.2f}%</div>
            <div style="margin-top:8px;font-size:13px;color:#848e9c">RSI: <span style="color:{rsi_color}">{rsi}</span></div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# Estado del bot
st.markdown("## ⚙️ Estado del Bot")
col1, col2, col3 = st.columns(3)
with col1:
    st.success("🟢 Bot Activo — analizando cada 30 min")
with col2:
    st.info("⚙️ Config: 3x leverage | SL 2% | TP 4% | Confianza mín 70%")
with col3:
    st.warning("🔄 Se actualiza automáticamente cada 15 segundos")

st.markdown("---")
st.markdown("*CryptoMind Bot v2 — Binance Demo Futures*")
