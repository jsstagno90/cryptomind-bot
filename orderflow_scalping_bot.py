"""
CryptoMind Order Flow Scalping Bot
Ratio: 5:1 (SL 0.5% / TP 2.5%)
Señales: Orderbook Depth + Trade Flow + Liquidations + Open Interest + Funding Rate
Velas: 5 minutos | Leverage: 5x
"""

import os
import json
import time
import hmac
import hashlib
import httpx
import anthropic
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv(r"C:\Users\jssta\OneDrive\Escritorio\Proyecto crypto\.env")

# ── Configuración ─────────────────────────────────────────────────────────────
ANTHROPIC_KEY    = os.getenv("ANTHROPIC_API_KEY")
DEMO_API_KEY     = os.getenv("BINANCE_DEMO_API_KEY")
DEMO_SECRET      = os.getenv("BINANCE_DEMO_SECRET")
BASE_URL         = "https://demo-fapi.binance.com"

LEVERAGE         = 5
TRADE_SIZE_USD   = 100
MIN_CONFIDENCE   = 72      # Más alto porque el ratio es 5:1 — solo entrar en setups claros
STOP_LOSS_PCT    = 0.5     # SL 0.5%
TAKE_PROFIT_PCT  = 2.5     # TP 2.5% → ratio 5:1
INTERVAL         = "5m"
COINS = ["BTC", "ETH", "SOL", "BNB", "ADA", "XRP"]
CICLO_SEGUNDOS   = 5 * 60

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
_memory_store = {}
_trade_log    = []


# ══════════════════════════════════════════════════════════════════════════════
# BINANCE API
# ══════════════════════════════════════════════════════════════════════════════

def sign_request(params):
    sp  = dict(sorted(params.items()))
    sig = hmac.new(DEMO_SECRET.encode(), urlencode(sp).encode(), hashlib.sha256).hexdigest()
    sp["signature"] = sig
    return sp

def get_headers():
    return {"X-MBX-APIKEY": DEMO_API_KEY}

def get_server_time():
    return httpx.get(f"{BASE_URL}/fapi/v1/time", timeout=10).json()["serverTime"]

def get_balance():
    try:
        params = sign_request({"timestamp": get_server_time()})
        r = httpx.get(f"{BASE_URL}/fapi/v2/balance", params=params, headers=get_headers(), timeout=10)
        data = r.json()
        if isinstance(data, list):
            for item in data:
                if item.get("asset") == "USDT":
                    return float(item.get("balance", 0))
        return 0
    except:
        return 0

def get_open_positions(symbol):
    try:
        params = sign_request({"symbol": symbol, "timestamp": get_server_time()})
        r = httpx.get(f"{BASE_URL}/fapi/v2/positionRisk", params=params, headers=get_headers(), timeout=10)
        data = r.json()
        if isinstance(data, list):
            return [p for p in data if float(p.get("positionAmt", 0)) != 0]
        return []
    except:
        return []

def close_position(symbol, position_amt):
    try:
        side = "SELL" if position_amt > 0 else "BUY"
        params = sign_request({
            "symbol": symbol, "side": side, "type": "MARKET",
            "quantity": abs(position_amt), "reduceOnly": "true",
            "timestamp": get_server_time()
        })
        r = httpx.post(f"{BASE_URL}/fapi/v1/order", params=params, headers=get_headers(), timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def set_leverage(symbol, leverage):
    try:
        params = sign_request({"symbol": symbol, "leverage": leverage, "timestamp": get_server_time()})
        httpx.post(f"{BASE_URL}/fapi/v1/leverage", params=params, headers=get_headers(), timeout=10)
    except:
        pass

def place_order(symbol, side, quantity, stop_loss, take_profit):
    try:
        params = sign_request({
            "symbol": symbol, "side": side, "type": "MARKET",
            "quantity": round(quantity, 3), "timestamp": get_server_time()
        })
        r = httpx.post(f"{BASE_URL}/fapi/v1/order", params=params, headers=get_headers(), timeout=10)
        order = r.json()
        if "orderId" not in order:
            return {"error": order}
        time.sleep(0.5)

        sl_side = "SELL" if side == "BUY" else "BUY"
        for order_type, price in [("STOP_MARKET", stop_loss), ("TAKE_PROFIT_MARKET", take_profit)]:
            p = sign_request({
                "symbol": symbol, "side": sl_side, "type": order_type,
                "stopPrice": round(price, 2), "closePosition": "true",
                "timestamp": get_server_time()
            })
            httpx.post(f"{BASE_URL}/fapi/v1/order", params=p, headers=get_headers(), timeout=10)

        return {"status": "ejecutada", "orderId": order["orderId"]}
    except Exception as e:
        return {"error": str(e)}

def get_price(coin):
    try:
        r = httpx.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT", timeout=5)
        return float(r.json()["price"])
    except:
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS ORDER FLOW
# ══════════════════════════════════════════════════════════════════════════════

TOOLS = [
    {
        "name": "get_technical_5m",
        "description": "Indicadores técnicos en velas 5m: RSI, EMA9/21 cruce, MACD, Bollinger, momentum, volumen",
        "input_schema": {"type": "object", "properties": {"coin": {"type": "string"}}, "required": ["coin"]}
    },
    {
        "name": "get_orderbook_depth",
        "description": "Profundidad del libro de órdenes: paredes bid/ask, ratio de presión, niveles clave de soporte/resistencia en el orderbook",
        "input_schema": {"type": "object", "properties": {"coin": {"type": "string"}}, "required": ["coin"]}
    },
    {
        "name": "get_trade_flow",
        "description": "Flujo de trades recientes: agresividad compradora vs vendedora, tamaño promedio, trades grandes (posibles institucionales)",
        "input_schema": {"type": "object", "properties": {"coin": {"type": "string"}}, "required": ["coin"]}
    },
    {
        "name": "get_liquidation_and_oi",
        "description": "Open Interest, Funding Rate y zonas de liquidación estimadas donde se van a liquidar posiciones apalancadas",
        "input_schema": {"type": "object", "properties": {"coin": {"type": "string"}}, "required": ["coin"]}
    },
    {
        "name": "get_memory",
        "description": "Recupera patrones de order flow pasados",
        "input_schema": {"type": "object", "properties": {"coin": {"type": "string"}}, "required": ["coin"]}
    },
    {
        "name": "save_memory",
        "description": "Guarda un patrón de order flow en memoria",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"},
                "insight": {"type": "string"},
                "category": {"type": "string"}
            },
            "required": ["coin", "insight", "category"]
        }
    },
    {
        "name": "execute_scalp",
        "description": "Ejecuta scalp con ratio 5:1 (SL 0.5% / TP 2.5%)",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"},
                "direction": {"type": "string", "enum": ["LONG", "SHORT", "CLOSE", "WAIT"]},
                "confidence": {"type": "integer", "description": "0-100"},
                "reasoning": {"type": "string"},
                "stop_loss_pct": {"type": "number", "default": 0.5},
                "take_profit_pct": {"type": "number", "default": 2.5}
            },
            "required": ["coin", "direction", "confidence", "reasoning"]
        }
    }
]


# ── Implementaciones ──────────────────────────────────────────────────────────

def get_technical_5m(coin: str) -> dict:
    try:
        symbol = f"{coin}USDT"
        klines = httpx.get(
            f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=5m&limit=100",
            timeout=10
        ).json()

        closes  = [float(k[4]) for k in klines]
        highs   = [float(k[2]) for k in klines]
        lows    = [float(k[3]) for k in klines]
        volumes = [float(k[5]) for k in klines]
        price   = closes[-1]

        # RSI 14
        gains  = [max(closes[i]-closes[i-1], 0) for i in range(1, len(closes))]
        losses = [max(closes[i-1]-closes[i], 0) for i in range(1, len(closes))]
        ag, al = sum(gains[-14:])/14, sum(losses[-14:])/14
        rsi    = round(100-(100/(1+ag/al)), 1) if al > 0 else 100

        # EMAs
        def ema(d, p):
            k, e = 2/(p+1), d[0]
            for x in d[1:]: e = x*k + e*(1-k)
            return round(e, 4)

        ema9  = ema(closes[-20:], 9)
        ema21 = ema(closes[-30:], 21)
        ema50 = ema(closes[-60:], 50)

        # MACD
        macd_val = ema(closes[-50:], 12) - ema(closes[-50:], 26)

        # Bollinger
        mean  = sum(closes[-20:])/20
        std   = (sum((x-mean)**2 for x in closes[-20:])/20)**0.5
        bb_up = round(mean + 2*std, 4)
        bb_lo = round(mean - 2*std, 4)
        bb_pct = round((price-bb_lo)/(bb_up-bb_lo)*100, 1) if bb_up != bb_lo else 50

        # Volumen relativo
        vol_avg    = sum(volumes[-20:]) / 20
        vol_ratio  = round(volumes[-1] / vol_avg, 2)

        # Momentum 3 velas
        momentum = round((closes[-1]-closes[-4])/closes[-4]*100, 4)

        # Vela actual
        open_price = float(klines[-1][1])
        vela_pct   = round((price-open_price)/open_price*100, 4)

        # Patrón de velas (últimas 3)
        patrones = []
        for i in range(-3, 0):
            o, c = float(klines[i][1]), float(klines[i][4])
            patrones.append("🟢" if c > o else "🔴")

        return {
            "coin": coin, "precio": round(price, 4),
            "rsi": rsi,
            "rsi_zona": "sobrecomprado" if rsi > 70 else "sobrevendido" if rsi < 30 else "neutral",
            "ema9": ema9, "ema21": ema21, "ema50": ema50,
            "ema_señal": "EMA9 > EMA21 alcista 🟢" if ema9 > ema21 else "EMA9 < EMA21 bajista 🔴",
            "macd": "alcista 🟢" if macd_val > 0 else "bajista 🔴",
            "bollinger_pct": bb_pct,
            "bb_señal": "techo — SHORT posible" if bb_pct > 85 else "piso — LONG posible" if bb_pct < 15 else "zona media",
            "volumen_relativo": vol_ratio,
            "vol_señal": "volumen alto 🔥" if vol_ratio > 1.5 else "volumen bajo" if vol_ratio < 0.7 else "normal",
            "momentum_pct": momentum,
            "vela_actual_pct": vela_pct,
            "ultimas_3_velas": " ".join(patrones),
            "soporte_5m": round(min(lows[-10:]), 4),
            "resistencia_5m": round(max(highs[-10:]), 4),
        }
    except Exception as e:
        return {"coin": coin, "error": str(e)}


def get_orderbook_depth(coin: str) -> dict:
    """Profundidad del orderbook — detecta paredes y zonas de soporte/resistencia"""
    try:
        symbol = f"{coin}USDT"
        depth  = httpx.get(
            f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=50",
            timeout=8
        ).json()

        bids = [(float(p), float(q)) for p, q in depth["bids"]]
        asks = [(float(p), float(q)) for p, q in depth["asks"]]

        # Volumen total bid vs ask
        bid_vol = sum(p*q for p, q in bids)
        ask_vol = sum(p*q for p, q in asks)
        ratio   = round(bid_vol / ask_vol, 3) if ask_vol > 0 else 1

        # Top 3 paredes de compra y venta
        top_bids = sorted(bids, key=lambda x: x[1], reverse=True)[:3]
        top_asks = sorted(asks, key=lambda x: x[1], reverse=True)[:3]

        # Spread
        spread_pct = round((asks[0][0]-bids[0][0])/bids[0][0]*100, 5)

        # Imbalance por niveles (primeros 10)
        imbalance_10 = round(
            sum(q for _, q in bids[:10]) / sum(q for _, q in asks[:10]), 3
        ) if asks else 1

        señal = (
            "LONG fuerte 🟢🟢 — compradores dominan masivamente" if ratio > 1.5 else
            "LONG leve 🟢 — leve presión compradora" if ratio > 1.2 else
            "SHORT fuerte 🔴🔴 — vendedores dominan masivamente" if ratio < 0.67 else
            "SHORT leve 🔴 — leve presión vendedora" if ratio < 0.83 else
            "NEUTRAL ⚪ — mercado equilibrado, esperar"
        )

        return {
            "coin": coin,
            "ratio_bid_ask": ratio,
            "bid_vol_usd": round(bid_vol, 0),
            "ask_vol_usd": round(ask_vol, 0),
            "imbalance_10_niveles": imbalance_10,
            "señal_orderbook": señal,
            "paredes_compra": [{"precio": p, "cantidad": q} for p, q in top_bids],
            "paredes_venta": [{"precio": p, "cantidad": q} for p, q in top_asks],
            "spread_pct": spread_pct,
            "spread_ok": "sí ✅" if spread_pct < 0.02 else "spread alto ⚠️",
        }
    except Exception as e:
        return {"coin": coin, "error": str(e)}


def get_trade_flow(coin: str) -> dict:
    """Flujo de trades — agresividad compradora vs vendedora"""
    try:
        symbol = f"{coin}USDT"
        # Últimos 500 trades
        trades = httpx.get(
            f"https://api.binance.com/api/v3/trades?symbol={symbol}&limit=500",
            timeout=10
        ).json()

        precio = float(trades[-1]["price"])

        # Buy market vs Sell market
        # isBuyerMaker=True significa que el comprador era el maker (alguien vendió agresivamente)
        buy_aggressive  = sum(float(t["quoteQty"]) for t in trades if not t["isBuyerMaker"])
        sell_aggressive = sum(float(t["quoteQty"]) for t in trades if t["isBuyerMaker"])
        total = buy_aggressive + sell_aggressive

        buy_pct  = round(buy_aggressive / total * 100, 1) if total > 0 else 50
        sell_pct = round(100 - buy_pct, 1)

        # Trades grandes (posibles institucionales) > $10k
        umbral = precio * 10
        big_buys  = sum(float(t["quoteQty"]) for t in trades if not t["isBuyerMaker"] and float(t["quoteQty"]) > umbral)
        big_sells = sum(float(t["quoteQty"]) for t in trades if t["isBuyerMaker"]     and float(t["quoteQty"]) > umbral)

        # Delta acumulado (buy - sell agresivos)
        delta = round(buy_aggressive - sell_aggressive, 0)
        delta_señal = "delta positivo — presión compradora 🟢" if delta > 0 else "delta negativo — presión vendedora 🔴"

        # Tendencia de los últimos 50 trades
        recent = trades[-50:]
        recent_buy  = sum(float(t["quoteQty"]) for t in recent if not t["isBuyerMaker"])
        recent_sell = sum(float(t["quoteQty"]) for t in recent if t["isBuyerMaker"])
        tendencia_reciente = "acelerando compradores 🟢" if recent_buy > recent_sell * 1.3 else \
                             "acelerando vendedores 🔴" if recent_sell > recent_buy * 1.3 else "equilibrado"

        señal = (
            "LONG fuerte 🟢🟢" if buy_pct > 60 and big_buys > big_sells else
            "LONG leve 🟢" if buy_pct > 55 else
            "SHORT fuerte 🔴🔴" if sell_pct > 60 and big_sells > big_buys else
            "SHORT leve 🔴" if sell_pct > 55 else
            "NEUTRAL ⚪"
        )

        return {
            "coin": coin,
            "buy_agresivo_pct": buy_pct,
            "sell_agresivo_pct": sell_pct,
            "delta_usd": delta,
            "delta_señal": delta_señal,
            "institucionales_buy_usd": round(big_buys, 0),
            "institucionales_sell_usd": round(big_sells, 0),
            "tendencia_50_trades": tendencia_reciente,
            "señal_trade_flow": señal,
            "interpretacion": f"{buy_pct}% de los trades fueron compras agresivas en los últimos 500 trades",
        }
    except Exception as e:
        return {"coin": coin, "error": str(e)}


def get_liquidation_and_oi(coin: str) -> dict:
    """Open Interest, Funding Rate y zonas de liquidación estimadas"""
    try:
        symbol = f"{coin}USDT"

        # Open Interest
        oi = httpx.get(f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}", timeout=8).json()
        oi_val = float(oi.get("openInterest", 0))

        # Historial OI (últimas 2 horas)
        oi_hist = httpx.get(
            f"https://fapi.binance.com/futures/data/openInterestHist?symbol={symbol}&period=5m&limit=24",
            timeout=8
        ).json()
        if isinstance(oi_hist, list) and len(oi_hist) >= 2:
            oi_cambio = round((float(oi_hist[-1]["sumOpenInterest"]) - float(oi_hist[0]["sumOpenInterest"])) / float(oi_hist[0]["sumOpenInterest"]) * 100, 2)
        else:
            oi_cambio = 0

        # Funding Rate
        fr = httpx.get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=1", timeout=8).json()
        funding = float(fr[0]["fundingRate"]) * 100 if fr else 0

        # Long/Short ratio
        ls = httpx.get(
            f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=5m&limit=1",
            timeout=8
        ).json()
        long_pct = float(ls[0]["longAccount"]) * 100 if isinstance(ls, list) and ls else 50

        # Precio actual para calcular zonas de liquidación estimadas
        precio = get_price(coin)

        # Zonas de liquidación estimadas (leverage 10x, 20x, 50x)
        liq_long_10x  = round(precio * 0.90, 2)
        liq_long_20x  = round(precio * 0.95, 2)
        liq_short_10x = round(precio * 1.10, 2)
        liq_short_20x = round(precio * 1.05, 2)

        # Interpretación
        oi_señal = "OI subiendo — nuevas posiciones entrando" if oi_cambio > 1 else \
                   "OI bajando — posiciones cerrando" if oi_cambio < -1 else "OI estable"

        funding_señal = "longs pagando mucho — sobreextendido alcista ⚠️" if funding > 0.05 else \
                        "shorts pagando — sobreextendido bajista ⚠️" if funding < -0.01 else \
                        "funding neutro ✅"

        ls_señal = "mayoría longs — posible short squeeze si baja 🔴" if long_pct > 65 else \
                   "mayoría shorts — posible short squeeze si sube 🟢" if long_pct < 35 else \
                   "equilibrado"

        return {
            "coin": coin, "precio_actual": precio,
            "open_interest": round(oi_val, 2),
            "oi_cambio_2h_pct": oi_cambio,
            "oi_señal": oi_señal,
            "funding_rate_pct": round(funding, 5),
            "funding_señal": funding_señal,
            "long_pct": round(long_pct, 1),
            "short_pct": round(100-long_pct, 1),
            "ls_señal": ls_señal,
            "zonas_liquidacion": {
                "longs_10x": liq_long_10x,
                "longs_20x": liq_long_20x,
                "shorts_10x": liq_short_10x,
                "shorts_20x": liq_short_20x,
            },
            "señal_general": (
                "LONG 🟢 — OI subiendo + funding neutro + mayoría shorts" if oi_cambio > 0 and abs(funding) < 0.03 and long_pct < 45 else
                "SHORT 🔴 — OI subiendo + funding alto + mayoría longs" if oi_cambio > 0 and funding > 0.04 and long_pct > 60 else
                "PRECAUCIÓN ⚠️ — funding extremo" if abs(funding) > 0.05 else
                "NEUTRAL ⚪"
            )
        }
    except Exception as e:
        return {"coin": coin, "error": str(e)}


def get_memory(coin: str) -> dict:
    return {"coin": coin, "memorias": _memory_store.get(coin, [])[-5:]}

def save_memory(coin: str, insight: str, category: str) -> dict:
    if coin not in _memory_store:
        _memory_store[coin] = []
    _memory_store[coin].append({
        "insight": insight, "categoria": category,
        "fecha": datetime.now().isoformat()
    })
    return {"status": "guardado"}


def execute_scalp(coin: str, direction: str, confidence: int, reasoning: str,
                  stop_loss_pct: float = 0.5, take_profit_pct: float = 2.5) -> dict:
    symbol = f"{coin}USDT"
    precio = get_price(coin)
    ratio  = round(take_profit_pct / stop_loss_pct, 1)

    print(f"\n⚡ ORDER FLOW SCALP: {direction} {coin} @ ${precio:,.4f}")
    print(f"   Ratio: {ratio}:1 | SL: {stop_loss_pct}% | TP: {take_profit_pct}% | Confianza: {confidence}%")

    if direction == "WAIT":
        print("⏳ WAIT — setup no es suficientemente claro")
        return {"status": "esperando"}

    if confidence < MIN_CONFIDENCE:
        print(f"⚠️ Confianza {confidence}% < {MIN_CONFIDENCE}% — no se entra")
        return {"status": "confianza_insuficiente"}

    positions = get_open_positions(symbol)
    if positions:
        pos_amt = float(positions[0]["positionAmt"])
        pos_dir = "LONG" if pos_amt > 0 else "SHORT"

        if direction == "CLOSE" or direction != pos_dir:
            print(f"🔄 Cerrando {pos_dir}...")
            close_position(symbol, pos_amt)
            time.sleep(0.5)
            if direction == "CLOSE":
                return {"status": "posicion_cerrada"}
        else:
            print(f"ℹ️ Ya en {pos_dir} — manteniendo")
            return {"status": "posicion_ya_abierta"}

    if direction in ["LONG", "SHORT"]:
        balance = get_balance()
        if balance < 10:
            return {"status": "balance_insuficiente", "balance": balance}

        monto = min(TRADE_SIZE_USD, balance * 0.8)
        qty   = round((monto * LEVERAGE) / precio, 3)

        if direction == "LONG":
            sl, tp, side = precio*(1-stop_loss_pct/100), precio*(1+take_profit_pct/100), "BUY"
        else:
            sl, tp, side = precio*(1+stop_loss_pct/100), precio*(1-take_profit_pct/100), "SELL"

        set_leverage(symbol, LEVERAGE)
        result = place_order(symbol, side, qty, sl, tp)

        if "error" not in result:
            emoji = "📈" if direction == "LONG" else "📉"
            print(f"✅ {emoji} {direction} ejecutado!")
            print(f"   Entrada: ${precio:,.4f}")
            print(f"   Stop Loss:   ${sl:,.4f} (-{stop_loss_pct}%)")
            print(f"   Take Profit: ${tp:,.4f} (+{take_profit_pct}%)")
            print(f"   Ratio: {ratio}:1 — ganás {ratio}x lo que arriesgás")

            _trade_log.append({
                "id": len(_trade_log)+1,
                "coin": coin, "direction": direction,
                "precio": precio, "sl": round(sl,4), "tp": round(tp,4),
                "qty": qty, "monto_usd": monto,
                "ratio": ratio, "confidence": confidence,
                "timestamp": datetime.now().isoformat(),
            })

            # Stats
            if len(_trade_log) > 1:
                print(f"\n📊 Stats: {len(_trade_log)} trades totales")
        else:
            print(f"❌ Error: {result['error']}")

        return {**result, "precio": precio, "sl": round(sl,4), "tp": round(tp,4), "ratio": ratio}

    return {"status": "desconocido"}


def handle_tool(name: str, inputs: dict):
    handlers = {
        "get_technical_5m":       get_technical_5m,
        "get_orderbook_depth":    get_orderbook_depth,
        "get_trade_flow":         get_trade_flow,
        "get_liquidation_and_oi": get_liquidation_and_oi,
        "get_memory":             get_memory,
        "save_memory":            save_memory,
        "execute_scalp":          execute_scalp,
    }
    fn = handlers.get(name)
    return fn(**inputs) if fn else {"error": f"Herramienta desconocida: {name}"}


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT ORDER FLOW
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Eres CryptoMind Order Flow Scalping Bot — especializado en leer el flujo real del mercado.

RATIO OBJETIVO: 5:1 (arriesgás 0.5% para ganar 2.5%)
Esto significa que podés perder 4 de cada 5 trades y AÚN ASÍ ser rentable.
Por eso solo entrás cuando el setup es MUY claro.

TU VENTAJA: Order Flow
No dependés solo de indicadores técnicos — leés lo que el mercado realmente está haciendo:

1. ORDERBOOK DEPTH → ¿Dónde están las paredes? ¿Quién domina el libro?
2. TRADE FLOW → ¿Están comprando o vendiendo agresivamente ahora mismo?
3. LIQUIDATION + OI → ¿Hacia dónde van a cazar liquidaciones? ¿OI subiendo o bajando?
4. TÉCNICO 5M → RSI, EMA9/21, Bollinger como contexto

SETUP IDEAL PARA LONG (todos deben alinearse):
✅ Orderbook ratio > 1.3 (compradores dominan)
✅ Trade flow buy > 55% (comprando agresivamente)
✅ Delta positivo y acelerando
✅ OI subiendo (nuevas posiciones alcistas)
✅ Funding neutro o negativo (no sobreextendido)
✅ EMA9 > EMA21 en 5m
✅ RSI entre 40-65 (no sobrecomprado)

SETUP IDEAL PARA SHORT (todos deben alinearse):
✅ Orderbook ratio < 0.7 (vendedores dominan)
✅ Trade flow sell > 55%
✅ Delta negativo y acelerando
✅ OI subiendo con funding alto (longs sobreextendidos)
✅ EMA9 < EMA21 en 5m
✅ RSI entre 35-60

REGLA DE ORO: Si no hay al menos 4 de 6 señales alineadas → WAIT.
Es mejor perderse 10 trades que entrar en uno malo.

Stop Loss: 0.5% | Take Profit: 2.5% | Confianza mínima: 72%"""


def scalp_coin(coin: str) -> dict:
    messages = [{
        "role": "user",
        "content": f"Analiza {coin} con Order Flow completo. ¿Hay setup para LONG, SHORT o hay que WAIT? Necesito al menos 4/6 señales alineadas."
    }]
    final_response = ""
    tool_log = []

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    final_response = block.text
            break

        if response.stop_reason == "tool_use":
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  📊 {block.name}")
                    result = handle_tool(block.name, block.input)
                    tool_log.append({"tool": block.name, "result": result})
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False)
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": results})
        else:
            break

    return {"coin": coin, "analysis": final_response, "tools": tool_log}


# ══════════════════════════════════════════════════════════════════════════════
# LOOP PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def run_orderflow_bot():
    print("\n" + "⚡ "*25)
    print("   CRYPTOMIND — ORDER FLOW SCALPING BOT")
    print("   Ratio 5:1 | SL 0.5% | TP 2.5% | Leverage 5x")
    print("   Orderbook + Trade Flow + Liquidations + OI")
    print("⚡ "*25)

    balance = get_balance()
    print(f"\n💰 Balance inicial: {balance:.2f} USDT (demo)")
    print(f"🎯 Monedas: {', '.join(COINS)}")
    print(f"⏱️  Ciclo: cada {CICLO_SEGUNDOS//60} minutos")
    print(f"📐 Ratio: 5:1 — ganás 5x lo que arriesgás\n")

    ciclo = 0
    while True:
        ciclo += 1
        print(f"\n{'='*60}")
        print(f"⚡ CICLO #{ciclo} — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"{'='*60}")

        for coin in COINS:
            print(f"\n🔍 Analizando Order Flow {coin}...")
            result = scalp_coin(coin)
            resumen = result['analysis'][:200].replace('\n', ' ')
            print(f"📊 {resumen}...")
            time.sleep(2)

        balance = get_balance()
        print(f"\n💰 Balance: {balance:.2f} USDT | Trades: {len(_trade_log)}")
        print(f"⏳ Próximo ciclo en {CICLO_SEGUNDOS//60} min... (Ctrl+C para detener)")
        time.sleep(CICLO_SEGUNDOS)


if __name__ == "__main__":
    run_orderflow_bot()
