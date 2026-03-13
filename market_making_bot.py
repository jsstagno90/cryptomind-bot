"""
CryptoMind Market Making Bot
Estrategia: poner bid y ask alrededor del precio justo
Protección: spread dinámico según volatilidad + hedge de inventario
Mercado: Binance Demo Futures
Monedas: BTC, ETH, SOL
"""

import os
import json
import time
import hmac
import hashlib
import httpx
import math
from datetime import datetime
from dotenv import load_dotenv
from urllib.parse import urlencode

load_dotenv(r"C:\Users\jssta\OneDrive\Escritorio\Proyecto crypto\.env")

# ── Configuración ─────────────────────────────────────────────────────────────
DEMO_API_KEY = os.getenv("BINANCE_API_KEY")
DEMO_SECRET  = os.getenv("BINANCE_SECRET_KEY")
BASE_URL     = "https://fapi.binance.com"

LEVERAGE       = 2          # Bajo para market making
ORDER_SIZE_USD = 20        # Tamaño de cada orden
SPREAD_BASE    = 0.08       # Spread base 0.08% en cada lado
SPREAD_MAX     = 0.5        # Spread máximo en mercado muy volátil
REBALANCE_SEC  = 15         # Recolocar órdenes cada 15 segundos
MAX_INVENTORY  = 3          # Máximo de posiciones abiertas por moneda
COINS = ["ETH", "SOL", "XRP", "ADA", "TRX", "AVAX", "DOT"]

# Stats globales
_stats = {coin: {"trades": 0, "pnl_estimado": 0, "spreads_capturados": 0} for coin in COINS}
_order_log = []


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

def get_open_orders(symbol):
    try:
        params = sign_request({"symbol": symbol, "timestamp": get_server_time()})
        r = httpx.get(f"{BASE_URL}/fapi/v1/openOrders", params=params, headers=get_headers(), timeout=10)
        return r.json() if isinstance(r.json(), list) else []
    except:
        return []

def cancel_all_orders(symbol):
    try:
        params = sign_request({"symbol": symbol, "timestamp": get_server_time()})
        r = httpx.delete(f"{BASE_URL}/fapi/v1/allOpenOrders", params=params, headers=get_headers(), timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def get_position(symbol):
    try:
        params = sign_request({"symbol": symbol, "timestamp": get_server_time()})
        r = httpx.get(f"{BASE_URL}/fapi/v2/positionRisk", params=params, headers=get_headers(), timeout=10)
        data = r.json()
        if isinstance(data, list):
            for p in data:
                if p.get("symbol") == symbol:
                    return float(p.get("positionAmt", 0)), float(p.get("unRealizedProfit", 0))
        return 0, 0
    except:
        return 0, 0

def set_leverage(symbol, leverage):
    try:
        params = sign_request({"symbol": symbol, "leverage": leverage, "timestamp": get_server_time()})
        r = httpx.post(f"{BASE_URL}/fapi/v1/leverage", params=params, headers=get_headers(), timeout=5)
        print(f"  Leverage response: {r.json()}")
    except Exception as e:
        print(f"  Leverage error: {e}")
        pass

def place_limit_order(symbol, side, quantity, price):
    try:
        # Precisión según moneda
        if "BTC" in symbol:
            qty = round(quantity, 3)
            prc = round(round(price / 1.0) * 1.0, 0)
        elif symbol in ["SOLUSDT", "DOTUSDT"]:
            qty = round(quantity, 1)
            prc = round(price, 2)
        elif symbol in ["AVAXUSDT"]:
            qty = round(quantity, 0)
            prc = round(price, 2)
        elif symbol in ["XRPUSDT", "ADAUSDT", "TRXUSDT"]:
            qty = round(quantity, 0)
            prc = round(price, 4)
        else:
            qty = round(quantity, 2)
            prc = round(price, 2)

        params = sign_request({
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "timeInForce": "GTC",
            "quantity": qty,
            "price": prc,
            "timestamp": get_server_time()
        })
        r = httpx.post(f"{BASE_URL}/fapi/v1/order", params=params, headers=get_headers(), timeout=5)
        print(f"  Orden {side} {symbol}: {r.json()}")
        return r.json()
    except Exception as e:
        print(f"  Error orden: {e}")
        return {"error": str(e)}

def place_market_order(symbol, side, quantity):
    """Orden de mercado para hedge de inventario"""
    try:
        params = sign_request({
            "symbol": symbol, "side": side, "type": "MARKET",
            "quantity": round(abs(quantity), 3),
            "timestamp": get_server_time()
        })
        r = httpx.post(f"{BASE_URL}/fapi/v1/order", params=params, headers=get_headers(), timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# LÓGICA DE MARKET MAKING
# ══════════════════════════════════════════════════════════════════════════════

def get_mid_price(coin):
    """Precio medio del mercado (entre mejor bid y mejor ask)"""
    try:
        symbol = f"{coin}USDT"
        r = httpx.get(f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={symbol}", timeout=5)
        d = r.json()
        bid = float(d["bidPrice"])
        ask = float(d["askPrice"])
        mid = (bid + ask) / 2
        return mid, bid, ask
    except:
        r = httpx.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT", timeout=5)
        p = float(r.json()["price"])
        return p, p, p

def get_volatility(coin):
    """Calcula volatilidad reciente para ajustar el spread"""
    try:
        klines = httpx.get(
            f"https://api.binance.com/api/v3/klines?symbol={coin}USDT&interval=1m&limit=20",
            timeout=8
        ).json()
        closes = [float(k[4]) for k in klines]
        returns = [(closes[i]-closes[i-1])/closes[i-1]*100 for i in range(1, len(closes))]
        vol = (sum(r**2 for r in returns) / len(returns)) ** 0.5  # Desviación estándar
        return round(vol, 4)
    except:
        return 0.05

def calculate_spread(volatility):
    """
    Spread dinámico según volatilidad
    Más volátil = spread más ancho (más protección)
    Menos volátil = spread más angosto (más competitivo)
    """
    # Spread = base + ajuste por volatilidad
    spread = SPREAD_BASE + (volatility * 2)
    spread = max(SPREAD_BASE, min(spread, SPREAD_MAX))
    return round(spread, 4)

def calculate_skew(position_amt, mid_price):
    """
    Sesga las órdenes según el inventario actual
    Si tenés demasiado LONG → subí el ask, bajá el bid (querés vender más)
    Si tenés demasiado SHORT → bajá el bid, subí el ask (querés comprar más)
    """
    if abs(position_amt) < 0.001:
        return 0  # Sin posición = sin sesgo

    # Valor del inventario en USD
    inventory_usd = position_amt * mid_price
    # Sesgo: 0.01% por cada $100 de inventario
    skew = (inventory_usd / 100) * 0.01
    skew = max(-0.15, min(skew, 0.15))  # Limitar sesgo máximo
    return round(skew, 4)

def should_hedge(position_amt, mid_price):
    """Determina si hay que hedgear el inventario"""
    inventory_usd = abs(position_amt * mid_price)
    return inventory_usd > ORDER_SIZE_USD * MAX_INVENTORY

def market_make_coin(coin):
    """
    Lógica principal de market making para una moneda
    1. Obtener precio medio y volatilidad
    2. Calcular spread dinámico
    3. Calcular sesgo por inventario
    4. Cancelar órdenes viejas
    5. Poner nuevas órdenes bid y ask
    6. Hedge si el inventario es demasiado grande
    """
    symbol   = f"{coin}USDT"
    mid, bid_mkt, ask_mkt = get_mid_price(coin)
    vol      = get_volatility(coin)
    spread   = calculate_spread(vol)
    pos_amt, unrealized_pnl = get_position(symbol)
    skew     = calculate_skew(pos_amt, mid)

    # Calcular precios de nuestras órdenes
    # Bid: compramos a mid - spread% - skew
    # Ask: vendemos a mid + spread% - skew (skew negativo si tenemos mucho long)
    our_bid = mid * (1 - spread/100 - skew/100)
    our_ask = mid * (1 + spread/100 - skew/100)

    # Cantidad por orden
    qty = (ORDER_SIZE_USD * LEVERAGE) / mid

    # Cancelar órdenes anteriores
    open_orders = get_open_orders(symbol)
    if open_orders:
        cancel_all_orders(symbol)

    # Verificar si necesitamos hedgear inventario
# STOP LOSS 1% por posición
        if pos_amt != 0 and unrealized_pnl < -(abs(pos_amt * mid) * 0.01):
            print(f"  🛑 SL 1% ACTIVADO {coin}: PnL ${unrealized_pnl:.2f} — cerrando")
            cancel_all_orders(f"{coin}USDT")
            close_position(f"{coin}USDT", pos_amt)
            return {"coin": coin, "mid": round(mid,4), "bid": 0, "ask": 0,
                    "spread_pct": 0, "volatilidad": vol, "skew": 0,
                    "posicion": 0, "pnl": 0, "bid_ok": False, "ask_ok": False}

        # Verificar si necesitamos hedgear inventario
        if should_hedge(pos_amt, mid):
            hedge_side = "SELL" if pos_amt > 0 else "BUY"
            hedge_qty  = abs(pos_amt) * 0.5
            place_market_order(symbol, hedge_side, hedge_qty)
            print(f"  🛡️ {coin} HEDGE: {hedge_side} {hedge_qty:.4f} (inventario: ${pos_amt*mid:+.0f})")

    # Poner nuevas órdenes límite
    set_leverage(symbol, LEVERAGE)

    bid_result = place_limit_order(symbol, "BUY",  qty, our_bid)
    ask_result = place_limit_order(symbol, "SELL", qty, our_ask)

    bid_ok = "orderId" in bid_result
    ask_ok = "orderId" in ask_result

    # Spread efectivo capturado cuando ambas se ejecutan
    spread_efectivo = round((our_ask - our_bid) / mid * 100, 4)

    # Log
    _order_log.append({
        "coin": coin, "timestamp": datetime.now().isoformat(),
        "mid": round(mid, 4), "bid": round(our_bid, 4), "ask": round(our_ask, 4),
        "spread_pct": spread_efectivo, "volatilidad": vol, "skew": skew,
        "pos_amt": pos_amt, "unrealized_pnl": unrealized_pnl,
        "bid_ok": bid_ok, "ask_ok": ask_ok,
    })

    return {
        "coin": coin, "mid": round(mid, 4),
        "bid": round(our_bid, 4), "ask": round(our_ask, 4),
        "spread_pct": spread_efectivo, "volatilidad": vol, "skew": skew,
        "posicion": pos_amt, "pnl": round(unrealized_pnl, 4),
        "bid_ok": bid_ok, "ask_ok": ask_ok,
    }


# ══════════════════════════════════════════════════════════════════════════════
# LOOP PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

def print_status(results, ciclo, balance):
    """Imprime estado limpio del bot"""
    print(f"\033[2J\033[H", end="")  # Limpiar pantalla
    print("═"*65)
    print(f"  🏦 CRYPTOMIND MARKET MAKING BOT  |  Ciclo #{ciclo}")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}  |  Balance: ${balance:,.2f} USDT")
    print("═"*65)

    for r in results:
        pos_emoji = "📈" if r["posicion"] > 0 else "📉" if r["posicion"] < 0 else "⚪"
        pnl_emoji = "🟢" if r["pnl"] >= 0 else "🔴"
        bid_ok = "✅" if r["bid_ok"] else "❌"
        ask_ok = "✅" if r["ask_ok"] else "❌"

        print(f"\n  {r['coin']}")
        print(f"  Mid: ${r['mid']:,.4f}  |  Spread: {r['spread_pct']}%  |  Vol: {r['volatilidad']}%")
        print(f"  BID {bid_ok}: ${r['bid']:,.4f}  ←→  ASK {ask_ok}: ${r['ask']:,.4f}")
        print(f"  {pos_emoji} Inventario: {r['posicion']:+.4f}  |  {pnl_emoji} PnL: ${r['pnl']:+.4f}")
        if r["skew"] != 0:
            print(f"  ↗️  Sesgo: {r['skew']:+.4f}% (ajustando por inventario)")

    print("\n" + "─"*65)
    print(f"  📊 Total órdenes colocadas: {len(_order_log)}")
    print(f"  ⏱️  Rebalanceo cada {REBALANCE_SEC}s  |  Ctrl+C para detener")
    print("─"*65)


def run_market_maker():
    print("\n" + "🏦 "*20)
    print("   CRYPTOMIND MARKET MAKING BOT")
    print("   Spread dinámico + Hedge de inventario")
    print("   BTC | ETH | SOL — Binance Demo Futures")
    print("🏦 "*20 + "\n")

    # Setup inicial
    for coin in COINS:
        set_leverage(f"{coin}USDT", LEVERAGE)
        print(f"✅ {coin}: leverage {LEVERAGE}x configurado")

    balance = get_balance()
    print(f"\n💰 Balance: {balance:.2f} USDT")
    print(f"📐 Spread base: {SPREAD_BASE}% cada lado")
    print(f"🛡️  Hedge automático si inventario > ${ORDER_SIZE_USD * MAX_INVENTORY}")
    print(f"\nIniciando en 3 segundos...")
    time.sleep(1)

    ciclo = 0
    while True:
        ciclo += 1
        results = []

        for coin in COINS:
            try:
                r = market_make_coin(coin)
                results.append(r)
                time.sleep(0.5)  # Pequeña pausa entre monedas
            except Exception as e:
                print(f"❌ Error en {coin}: {e}")
                results.append({"coin": coin, "mid": 0, "bid": 0, "ask": 0,
                                "spread_pct": 0, "volatilidad": 0, "skew": 0,
                                "posicion": 0, "pnl": 0, "bid_ok": False, "ask_ok": False})

        balance = get_balance()
        print_status(results, ciclo, balance)
        time.sleep(REBALANCE_SEC)


if __name__ == "__main__":
    run_market_maker()
