"""
CryptoMind Futures Bot
Conectado a Binance Demo Futures (https://demo-fapi.binance.com)
Opera LONG y SHORT automáticamente con dinero ficticio
"""
import os
import json
import math
import time
import httpx # Los imports siempre van al principio del archivo
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic
import httpx
import hmac
import hashlib
from urllib.parse import urlencode

load_dotenv(r"C:\Users\jssta\OneDrive\Escritorio\Proyecto crypto\.env")

print(httpx.get('https://demo-fapi.binance.com/fapi/v1/ping').json())
# ── Configuración ─────────────────────────────────────────────────────────────
ANTHROPIC_KEY     = os.getenv("ANTHROPIC_API_KEY")
DEMO_API_KEY      = os.getenv("BINANCE_DEMO_API_KEY")
DEMO_SECRET       = os.getenv("BINANCE_DEMO_SECRET")
BASE_URL          = "https://demo-fapi.binance.com"
LEVERAGE          = 3          # Apalancamiento 3x
TRADE_SIZE_USD    = 200        # Tamaño por operación en USDT
MIN_CONFIDENCE    = 70         # Confianza mínima para operar
STOP_LOSS_PCT     = 2.0        # Stop loss 2%
TAKE_PROFIT_PCT   = 4.0        # Take profit 4%
COINS             = ["BTC", "ETH", "SOL"]

client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
_memory_store = {}


# ══════════════════════════════════════════════════════════════════════════════
# BINANCE DEMO FUTURES API
# ══════════════════════════════════════════════════════════════════════════════

def sign_request(params):
    # 1. Ordenar los parámetros alfabéticamente por clave
    # Esto es crucial para que la firma coincida con el servidor de Binance
    sorted_params = dict(sorted(params.items()))
    
    # 2. Crear el string de consulta
    query_string = urlencode(sorted_params)
    
    # 3. Firmar usando tu secret key
    secret = os.getenv('BINANCE_DEMO_SECRET')
    signature = hmac.new(
        secret.encode('utf-8'), 
        query_string.encode('utf-8'), 
        hashlib.sha256
    ).hexdigest()
    
    # 4. Añadir la firma a los parámetros
    sorted_params['signature'] = signature
    return sorted_params

def get_headers() -> dict:
    return {
        "X-MBX-APIKEY": DEMO_API_KEY,
        "User-Agent": "Mozilla/5.0", # Binance a veces rechaza peticiones sin un User-Agent legítimo
        "Content-Type": "application/json"
    }

def round_step_size(quantity, step_size):
    """Ajusta la cantidad según el step_size de Binance."""
    precision = int(round(-math.log(step_size, 10), 0))
    return round(quantity, precision)

def get_symbol_info(symbol):
    """Obtiene los filtros de precisión de un par (ej: 'SOLUSDT')"""
    # Consulta a la API de Binance
    info = httpx.get(f"{BASE_URL}/fapi/v1/exchangeInfo").json()
    for s in info['symbols']:
        if s['symbol'] == symbol:
            # Buscamos el filtro LOT_SIZE para la cantidad
            for f in s['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    return float(f['stepSize'])
    return 0.001 # Valor por defecto seguro

def get_server_time() -> int:
    r = httpx.get(f"{BASE_URL}/fapi/v1/time", timeout=10)
    return r.json()["serverTime"]

def get_balance() -> float:
    """Obtiene balance USDT disponible correctamente"""
    try:
        params = sign_request({"timestamp": get_server_time()})
        r = httpx.get(f"{BASE_URL}/fapi/v2/balance", params=params, headers=get_headers(), timeout=10)
        data = r.json()
        
        # Iteramos sobre la lista para encontrar el objeto con asset == 'USDT'
        if isinstance(data, list):
            for item in data:
                if item.get("asset") == "USDT":
                    balance = float(item.get("balance", 0))
                    print(f"DEBUG: Balance encontrado: {balance}") # Para confirmar
                    return balance
        return 0.0
    except Exception as e:
        print(f"❌ Error obteniendo balance: {e}")
        return 0.0

def set_leverage(symbol: str, leverage: int) -> bool:
    """Configura el apalancamiento"""
    try:
        params = sign_request({
            "symbol": symbol,
            "leverage": leverage,
            "timestamp": get_server_time()
        })
        r = httpx.post(f"{BASE_URL}/fapi/v1/leverage", params=params, headers=get_headers(), timeout=10)
        return r.status_code == 200
    except:
        return False

def get_open_positions(symbol: str) -> list:
    """Obtiene posiciones abiertas"""
    try:
        params = sign_request({"symbol": symbol, "timestamp": get_server_time()})
        r = httpx.get(f"{BASE_URL}/fapi/v2/positionRisk", params=params, headers=get_headers(), timeout=10)
        positions = r.json()
        return [p for p in positions if float(p.get("positionAmt", 0)) != 0]
    except Exception as e:
        print(f"❌ Error obteniendo posiciones: {e}")
        return []

def close_position(symbol: str, position_amt: float) -> dict:
    """Cierra una posición existente"""
    try:
        side = "SELL" if position_amt > 0 else "BUY"
        qty  = abs(position_amt)
        params = sign_request({
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": qty,
            "reduceOnly": "true",
            "timestamp": get_server_time()
        })
        r = httpx.post(f"{BASE_URL}/fapi/v1/order", params=params, headers=get_headers(), timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def place_order(symbol: str, side: str, quantity: float,
                stop_loss: float, take_profit: float) -> dict:
    """Coloca orden de mercado con SL y TP"""
    try:
        # Orden principal
        params = sign_request({
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": round(quantity, 3),
            "timestamp": get_server_time()
        })
        r = httpx.post(f"{BASE_URL}/fapi/v1/order", params=params, headers=get_headers(), timeout=10)
        order = r.json()

        if "orderId" not in order:
            return {"error": order}

        time.sleep(1)

        # Stop Loss
        sl_side = "SELL" if side == "BUY" else "BUY"
        sl_params = sign_request({
            "symbol": symbol,
            "side": sl_side,
            "type": "STOP_MARKET",
            "stopPrice": round(stop_loss, 2),
            "closePosition": "true",
            "timestamp": get_server_time()
        })
        httpx.post(f"{BASE_URL}/fapi/v1/order", params=sl_params, headers=get_headers(), timeout=10)

        # Take Profit
        tp_params = sign_request({
            "symbol": symbol,
            "side": sl_side,
            "type": "TAKE_PROFIT_MARKET",
            "stopPrice": round(take_profit, 2),
            "closePosition": "true",
            "timestamp": get_server_time()
        })
        httpx.post(f"{BASE_URL}/fapi/v1/order", params=tp_params, headers=get_headers(), timeout=10)

        return {"status": "ejecutada", "orderId": order["orderId"], "symbol": symbol, "side": side}

    except Exception as e:
        return {"error": str(e)}

def get_price(coin: str) -> float:
    """Precio actual desde Binance"""
    try:
        r = httpx.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT", timeout=5)
        return float(r.json()["price"])
    except:
        return 0


# ══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS DEL AGENTE
# ══════════════════════════════════════════════════════════════════════════════

TOOLS = [
    {
        "name": "get_technical_indicators",
        "description": "RSI, MACD, Bollinger Bands, EMAs, VWAP, soporte y resistencia desde Binance",
        "input_schema": {"type": "object", "properties": {"coin": {"type": "string"}}, "required": ["coin"]}
    },
    {
        "name": "get_market_sentiment",
        "description": "Fear & Greed Index, Long/Short ratio, Funding rate",
        "input_schema": {"type": "object", "properties": {"coin": {"type": "string"}}, "required": ["coin"]}
    },
    {
        "name": "get_crypto_news",
        "description": "Últimas noticias de CryptoPanic con sentimiento",
        "input_schema": {"type": "object", "properties": {"coin": {"type": "string"}}, "required": ["coin"]}
    },
    {
        "name": "get_memory",
        "description": "Recupera patrones pasados de la memoria",
        "input_schema": {"type": "object", "properties": {"coin": {"type": "string"}}, "required": ["coin"]}
    },
    {
        "name": "save_memory",
        "description": "Guarda un patrón o insight en memoria",
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
        "name": "execute_trade",
        "description": "Ejecuta una operación LONG o SHORT en Binance Demo Futures",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"},
                "direction": {"type": "string", "enum": ["LONG", "SHORT", "CLOSE", "WAIT"]},
                "confidence": {"type": "integer", "description": "Confianza 0-100"},
                "reasoning": {"type": "string"},
                "stop_loss_pct": {"type": "number", "default": 2.0},
                "take_profit_pct": {"type": "number", "default": 4.0}
            },
            "required": ["coin", "direction", "confidence", "reasoning"]
        }
    }
]


def get_technical_indicators(coin: str) -> dict:
    try:
        symbol  = f"{coin}USDT"
        ticker  = httpx.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", timeout=10).json()
        klines  = httpx.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=200", timeout=10).json()
        closes  = [float(k[4]) for k in klines]
        highs   = [float(k[2]) for k in klines]
        lows    = [float(k[3]) for k in klines]

        # RSI
        gains  = [max(closes[i]-closes[i-1], 0) for i in range(1, len(closes))]
        losses = [max(closes[i-1]-closes[i], 0) for i in range(1, len(closes))]
        ag, al = sum(gains[-14:])/14, sum(losses[-14:])/14
        rsi    = round(100 - (100/(1+ag/al)), 1) if al > 0 else 100

        # EMA
        def ema(d, p):
            k, e = 2/(p+1), d[0]
            for x in d[1:]: e = x*k + e*(1-k)
            return round(e, 2)

        ema20, ema50, ema200 = ema(closes[-20:], 20), ema(closes[-50:], 50), ema(closes[-200:], 200)
        price = closes[-1]

        # Bollinger
        mean  = sum(closes[-20:])/20
        std   = (sum((x-mean)**2 for x in closes[-20:])/20)**0.5
        bb_up = round(mean + 2*std, 2)
        bb_lo = round(mean - 2*std, 2)
        bb_pct = round((price-bb_lo)/(bb_up-bb_lo)*100, 1)

        # MACD
        macd  = ema(closes[-50:], 12) - ema(closes[-50:], 26)

        return {
            "coin": coin, "precio": round(price, 2),
            "cambio_24h_pct": float(ticker["priceChangePercent"]),
            "rsi": rsi,
            "rsi_señal": "sobrecomprado ⚠️" if rsi > 70 else "sobrevendido 🟢" if rsi < 30 else "neutral",
            "macd_señal": "alcista 🟢" if macd > 0 else "bajista 🔴",
            "bollinger_pct": bb_pct,
            "bollinger_pos": "techo 🔴" if bb_pct > 80 else "piso 🟢" if bb_pct < 20 else "medio",
            "ema20": ema20, "ema50": ema50, "ema200": ema200,
            "tendencia": "alcista 🟢" if price > ema20 > ema50 else "bajista 🔴" if price < ema20 < ema50 else "lateral",
            "soporte": round(min(lows[-20:]), 2),
            "resistencia": round(max(highs[-20:]), 2),
        }
    except Exception as e:
        return {"coin": coin, "error": str(e)}


def get_market_sentiment(coin: str) -> dict:
    try:
        symbol = f"{coin}USDT"

        # Fear & Greed
        fng   = httpx.get("https://api.alternative.me/fng/?limit=1", timeout=8).json()
        score = int(fng["data"][0]["value"])
        label = fng["data"][0]["value_classification"]

        # Funding rate
        fr    = httpx.get(f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=1", timeout=8).json()
        fund  = float(fr[0]["fundingRate"]) * 100 if fr else 0

        # Long/Short
        ls    = httpx.get(f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=1h&limit=1", timeout=8).json()
        long_pct = float(ls[0]["longAccount"]) * 100 if ls else 50

        return {
            "fear_greed": score, "fear_greed_label": label,
            "señal_fng": "zona de compra histórica 🟢" if score < 25 else "euforia — precaución 🔴" if score > 75 else "neutral",
            "funding_rate_pct": round(fund, 4),
            "funding_señal": "longs pagando caro ⚠️" if fund > 0.05 else "shorts dominando" if fund < -0.01 else "equilibrado",
            "long_pct": round(long_pct, 1),
            "short_pct": round(100-long_pct, 1),
        }
    except Exception as e:
        return {"error": str(e)}


def get_crypto_news(coin: str) -> dict:
    try:
        token = os.getenv("CRYPTOPANIC_API_KEY")
        data  = httpx.get(f"https://cryptopanic.com/api/v1/posts/?auth_token={token}&currencies={coin}&public=true", timeout=10).json()
        news  = [{"titulo": i["title"], "fuente": i["source"]["title"]} for i in data.get("results", [])[:5]]
        return {"coin": coin, "noticias": news}
    except Exception as e:
        return {"coin": coin, "error": str(e)}


def get_memory(coin: str) -> dict:
    return {"coin": coin, "memorias": _memory_store.get(coin, []), "total": len(_memory_store.get(coin, []))}


def save_memory(coin: str, insight: str, category: str) -> dict:
    if coin not in _memory_store:
        _memory_store[coin] = []
    _memory_store[coin].append({"insight": insight, "categoria": category, "fecha": datetime.now().isoformat()})
    return {"status": "guardado"}


def execute_trade(coin: str, direction: str, confidence: int, reasoning: str,
                  stop_loss_pct: float = 2.0, take_profit_pct: float = 4.0) -> dict:
    """Ejecuta la operación en Binance Demo Futures"""

    symbol = f"{coin}USDT"
    precio = get_price(coin)

    print(f"\n{'='*50}")
    print(f"🤖 SEÑAL: {direction} {coin} | Confianza: {confidence}%")
    print(f"   Razón: {reasoning[:100]}...")
    print(f"{'='*50}")

    if direction == "WAIT":
        print("⏳ ESPERAR — señales no son suficientemente claras")
        return {"status": "esperando", "razon": reasoning}

    if confidence < MIN_CONFIDENCE:
        print(f"⚠️ Confianza {confidence}% < mínimo {MIN_CONFIDENCE}% — no se opera")
        return {"status": "confianza_insuficiente", "confidence": confidence}

    # Verificar posiciones abiertas
    positions = get_open_positions(symbol)
    print(f"DEBUG: Posiciones reales en Binance: {positions}")
    if positions:
        pos_amt = float(positions[0]["positionAmt"])
        pos_dir = "LONG" if pos_amt > 0 else "SHORT"

        if direction == "CLOSE" or (direction == "LONG" and pos_dir == "SHORT") or (direction == "SHORT" and pos_dir == "LONG"):
            print(f"🔄 Cerrando posición {pos_dir} existente...")
            close_position(symbol, pos_amt)
            time.sleep(1)
            if direction == "CLOSE":
                return {"status": "posicion_cerrada"}
        elif pos_dir == direction:
            print(f"ℹ️ Ya hay una posición {pos_dir} abierta — no se duplica")
            return {"status": "posicion_ya_abierta", "direction": pos_dir}

    if direction in ["LONG", "SHORT"]:
        # Calcular cantidad
        balance = get_balance()
        if balance < 10:
            return {"status": "balance_insuficiente", "balance": balance}

        monto   = min(TRADE_SIZE_USD, balance * 0.9)
        qty     = round((monto * LEVERAGE) / precio, 3)

        # SL y TP
        if direction == "LONG":
            sl = precio * (1 - stop_loss_pct/100)
            tp = precio * (1 + take_profit_pct/100)
            side = "BUY"
        else:
            sl = precio * (1 + stop_loss_pct/100)
            tp = precio * (1 - take_profit_pct/100)
            side = "SELL"

        set_leverage(symbol, LEVERAGE)
        result = place_order(symbol, side, qty, sl, tp)

        if "error" not in result:
            accion = "📈 LONG (apuesta a SUBIDA)" if direction == "LONG" else "📉 SHORT (apuesta a BAJADA)"
            print(f"✅ {accion}")
            print(f"   Precio entrada: ${precio:,.2f}")
            print(f"   Cantidad: {qty} {coin}")
            print(f"   Stop Loss: ${sl:,.2f} (-{stop_loss_pct}%)")
            print(f"   Take Profit: ${tp:,.2f} (+{take_profit_pct}%)")
            print(f"   Apalancamiento: {LEVERAGE}x")
            print(f"   Monto: ${monto} USDT")
        else:
            print(f"❌ Error: {result['error']}")

        return {**result, "precio": precio, "qty": qty, "sl": round(sl,2), "tp": round(tp,2)}

    return {"status": "accion_desconocida"}


def handle_tool(name: str, inputs: dict):
    handlers = {
        "get_technical_indicators": get_technical_indicators,
        "get_market_sentiment": get_market_sentiment,
        "get_crypto_news": get_crypto_news,
        "get_memory": get_memory,
        "save_memory": save_memory,
        "execute_trade": execute_trade,
    }
    fn = handlers.get(name)
    return fn(**inputs) if fn else {"error": f"Herramienta desconocida: {name}"}


# ══════════════════════════════════════════════════════════════════════════════
# AGENTE PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Eres CryptoMind Futures Bot — un agente de trading de futuros crypto.

Puedes operar en AMBAS direcciones:
- LONG: apostar a que el precio SUBE
- SHORT: apostar a que el precio BAJA
- CLOSE: cerrar posición actual
- WAIT: esperar mejor oportunidad

Tu proceso OBLIGATORIO:
1. Analizar indicadores técnicos (RSI, MACD, Bollinger, EMAs, tendencia)
2. Evaluar sentimiento (Fear & Greed, Funding rate, Long/Short ratio)
3. Revisar noticias recientes
4. Consultar memoria de patrones pasados
5. Decidir dirección con confianza 0-100
6. Ejecutar solo si confianza >= 70
7. Guardar el patrón en memoria

Reglas de trading:
- RSI < 30 + MACD alcista = señal LONG fuerte
- RSI > 70 + MACD bajista = señal SHORT fuerte  
- Funding rate muy alto (>0.05%) = mercado sobreextendido, considerar SHORT
- Fear & Greed < 25 = zona de compra histórica
- Nunca operar contra tendencia en EMA20/50/200
- Stop Loss máximo: 3% | Take Profit mínimo: 2x el Stop Loss
- Apalancamiento fijo: 3x (conservador)"""


def analyze_and_trade(coin: str) -> dict:
    print(f"\n🧠 Analizando {coin}...")
    messages = [{"role": "user", "content": f"Analiza {coin} y decide si operar LONG, SHORT o WAIT. Usa todas tus herramientas."}]
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
                    print(f"  🔧 {block.name}")
                    result = handle_tool(block.name, block.input)
                    tool_log.append({"tool": block.name, "result": result})
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result, ensure_ascii=False)})
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": results})
        else:
            break

    return {"coin": coin, "analysis": final_response, "tools": tool_log}


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULER — CORRE AUTOMÁTICO CADA 30 MINUTOS
# ══════════════════════════════════════════════════════════════════════════════

def run_bot():
    print("\n" + "🚀 "*20)
    print("   CRYPTOMIND FUTURES BOT — INICIANDO")
    print("   Binance Demo Futures | Apalancamiento 3x")
    print("🚀 "*20)

    balance = get_balance()
    print(f"\n💰 Balance inicial: {balance:.2f} USDT (demo)")

    ciclo = 0
    while True:
        ciclo += 1
        print(f"\n\n{'='*60}")
        print(f"⏰ CICLO #{ciclo} — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"{'='*60}")

        for coin in COINS:
            result = analyze_and_trade(coin)
            print(f"\n📊 {coin}: {result['analysis'][:200]}...")
            time.sleep(3)  # Pausa entre monedas

        balance = get_balance()
        print(f"\n💰 Balance actual: {balance:.2f} USDT (demo)")
        print(f"\n⏳ Próximo análisis en 30 minutos...")
        print(f"   (Presioná Ctrl+C para detener el bot)")

        time.sleep(30 * 60)  # 30 minutos


if __name__ == "__main__":
    run_bot()
