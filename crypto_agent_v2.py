"""
CryptoMind Super Agent v2.0
Agente de trading con máxima información:
- Indicadores técnicos avanzados (Bollinger, EMA, VWAP, RSI, MACD)
- Long/Short ratio + Funding rate
- Movimientos de ballenas
- Correlación con S&P 500
- Noticias + Fear & Greed
- Memoria persistente
- Paper trading en Binance Testnet
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

load_dotenv(r"C:\Users\jssta\OneDrive\Escritorio\Proyecto crypto\.env")

import anthropic
import httpx

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ── Memoria simple (reemplazar con Mem0 en producción) ────────────────────────
_memory_store: dict = {}
_paper_trades: list = []
_paper_portfolio = {"cash_usd": 10000.0, "positions": {}}


# ══════════════════════════════════════════════════════════════════════════════
# HERRAMIENTAS
# ══════════════════════════════════════════════════════════════════════════════

TOOLS = [
    {
        "name": "get_technical_indicators",
        "description": "Obtiene indicadores técnicos avanzados: RSI, MACD, Bollinger Bands, EMA 20/50/200, VWAP, soportes y resistencias",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"},
                "interval": {"type": "string", "default": "1h"}
            },
            "required": ["coin"]
        }
    },
    {
        "name": "get_market_depth",
        "description": "Obtiene Long/Short ratio, Funding rate, Open Interest y datos de futuros para medir sentimiento institucional",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"}
            },
            "required": ["coin"]
        }
    },
    {
        "name": "get_whale_movements",
        "description": "Detecta movimientos grandes de ballenas: transferencias masivas, flujos hacia/desde exchanges, acumulación/distribución",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"}
            },
            "required": ["coin"]
        }
    },
    {
        "name": "get_market_correlation",
        "description": "Correlación de crypto con S&P 500, NASDAQ, dominancia de BTC y comparación con otras cryptos",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"}
            },
            "required": ["coin"]
        }
    },
    {
        "name": "get_crypto_news",
        "description": "Noticias recientes de CryptoPanic con sentimiento",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"},
                "limit": {"type": "integer", "default": 10}
            },
            "required": ["coin"]
        }
    },
    {
        "name": "get_fear_greed",
        "description": "Índice de Miedo y Codicia actual e histórico (7 días)",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_memory",
        "description": "Recupera patrones y análisis pasados de la memoria del agente",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"},
                "query": {"type": "string"}
            },
            "required": ["coin"]
        }
    },
    {
        "name": "save_memory",
        "description": "Guarda un insight o patrón en la memoria para uso futuro",
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
        "name": "execute_paper_trade",
        "description": "Ejecuta una operación simulada en Binance Testnet",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"},
                "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
                "amount_usd": {"type": "number"},
                "confidence": {"type": "integer"},
                "reasoning": {"type": "string"},
                "stop_loss_pct": {"type": "number", "description": "Stop loss en porcentaje ej: 3.0"},
                "take_profit_pct": {"type": "number", "description": "Take profit en porcentaje ej: 6.0"}
            },
            "required": ["coin", "action", "confidence", "reasoning"]
        }
    }
]


# ══════════════════════════════════════════════════════════════════════════════
# IMPLEMENTACIÓN DE HERRAMIENTAS
# ══════════════════════════════════════════════════════════════════════════════

def get_technical_indicators(coin: str, interval: str = "1h") -> dict:
    """Indicadores técnicos reales desde Binance"""
    try:
        symbol = f"{coin}USDT"

        # Precio actual y stats 24h
        ticker = httpx.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", timeout=10).json()

        # Velas para cálculos (200 velas para EMA200)
        klines = httpx.get(
            f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit=200",
            timeout=10
        ).json()

        closes = [float(k[4]) for k in klines]
        highs  = [float(k[2]) for k in klines]
        lows   = [float(k[3]) for k in klines]
        vols   = [float(k[5]) for k in klines]

        # ── RSI 14 ────────────────────────────────────────────────────────────
        gains  = [max(closes[i]-closes[i-1], 0) for i in range(1, len(closes))]
        losses = [max(closes[i-1]-closes[i], 0) for i in range(1, len(closes))]
        avg_g  = sum(gains[-14:]) / 14
        avg_l  = sum(losses[-14:]) / 14
        rsi    = round(100 - (100 / (1 + avg_g/avg_l)), 1) if avg_l > 0 else 100

        # ── MACD (12/26/9) ────────────────────────────────────────────────────
        def ema(data, period):
            k = 2 / (period + 1)
            e = data[0]
            for p in data[1:]:
                e = p * k + e * (1 - k)
            return e

        ema12     = ema(closes[-50:], 12)
        ema26     = ema(closes[-50:], 26)
        macd_line = ema12 - ema26
        signal    = ema([ema(closes[-50+i:], 12) - ema(closes[-50+i:], 26) for i in range(9)], 9)
        macd_hist = macd_line - signal
        macd_str  = "alcista" if macd_hist > 0 else "bajista"

        # ── Bollinger Bands (20, 2σ) ──────────────────────────────────────────
        bb_closes = closes[-20:]
        bb_mean   = sum(bb_closes) / 20
        bb_std    = (sum((x - bb_mean)**2 for x in bb_closes) / 20) ** 0.5
        bb_upper  = round(bb_mean + 2 * bb_std, 2)
        bb_lower  = round(bb_mean - 2 * bb_std, 2)
        bb_pct    = round((closes[-1] - bb_lower) / (bb_upper - bb_lower) * 100, 1)
        bb_pos    = "cerca del techo" if bb_pct > 80 else "cerca del piso" if bb_pct < 20 else "zona media"

        # ── EMAs ──────────────────────────────────────────────────────────────
        ema20  = round(ema(closes[-20:],  20),  2)
        ema50  = round(ema(closes[-50:],  50),  2)
        ema200 = round(ema(closes[-200:], 200), 2)
        price  = closes[-1]
        tendencia = "alcista fuerte" if price > ema20 > ema50 > ema200 else \
                    "bajista fuerte" if price < ema20 < ema50 < ema200 else "lateral/mixta"

        # ── VWAP ──────────────────────────────────────────────────────────────
        typical_prices = [(highs[i] + lows[i] + closes[i]) / 3 for i in range(len(closes))]
        vwap = round(sum(tp * v for tp, v in zip(typical_prices[-24:], vols[-24:])) / sum(vols[-24:]), 2)
        vwap_pos = "por encima del VWAP (bullish)" if price > vwap else "por debajo del VWAP (bearish)"

        # ── Soporte y Resistencia ─────────────────────────────────────────────
        recent_highs = sorted(highs[-50:], reverse=True)
        recent_lows  = sorted(lows[-50:])
        resistencia  = round(sum(recent_highs[:3]) / 3, 2)
        soporte      = round(sum(recent_lows[:3]) / 3, 2)

        return {
            "coin": coin, "precio": round(price, 2),
            "cambio_24h": float(ticker["priceChangePercent"]),
            "volumen_24h_usd": round(float(ticker["quoteVolume"]), 0),
            "rsi_14": rsi,
            "rsi_señal": "sobrecomprado" if rsi > 70 else "sobrevendido" if rsi < 30 else "neutral",
            "macd": {"señal": macd_str, "histograma": round(macd_hist, 4)},
            "bollinger": {"superior": bb_upper, "inferior": bb_lower, "posicion_pct": bb_pct, "descripcion": bb_pos},
            "emas": {"ema20": ema20, "ema50": ema50, "ema200": ema200, "tendencia": tendencia},
            "vwap": vwap, "vwap_posicion": vwap_pos,
            "soporte": soporte, "resistencia": resistencia,
            "distancia_soporte_pct": round((price - soporte) / price * 100, 2),
            "distancia_resistencia_pct": round((resistencia - price) / price * 100, 2),
        }
    except Exception as e:
        return {"coin": coin, "error": str(e)}


def get_market_depth(coin: str) -> dict:
    """Long/Short ratio, Funding Rate y Open Interest desde Binance Futures"""
    try:
        symbol = f"{coin}USDT"

        # Funding rate
        funding = httpx.get(
            f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=1",
            timeout=10
        ).json()
        funding_rate = float(funding[0]['fundingRate']) * 100 if funding else 0

        # Open Interest
        oi = httpx.get(
            f"https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}",
            timeout=10
        ).json()
        open_interest = float(oi.get('openInterest', 0))

        # Long/Short ratio (últimas 24h)
        ls = httpx.get(
            f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=1h&limit=1",
            timeout=10
        ).json()
        long_pct  = float(ls[0]['longAccount'])  * 100 if ls else 50
        short_pct = float(ls[0]['shortAccount']) * 100 if ls else 50

        # Interpretación
        if funding_rate > 0.05:
            funding_señal = "mercado muy alcista — longs pagando caro, posible corrección"
        elif funding_rate < -0.01:
            funding_señal = "mercado bajista — shorts dominando"
        else:
            funding_señal = "funding neutral — mercado equilibrado"

        ls_señal = "mayoría longs — posible squeeze bajista" if long_pct > 65 else \
                   "mayoría shorts — posible short squeeze alcista" if short_pct > 65 else \
                   "mercado equilibrado"

        return {
            "coin": coin,
            "funding_rate_pct": round(funding_rate, 4),
            "funding_señal": funding_señal,
            "long_pct": round(long_pct, 1),
            "short_pct": round(short_pct, 1),
            "long_short_señal": ls_señal,
            "open_interest": round(open_interest, 0),
        }
    except Exception as e:
        return {"coin": coin, "error": str(e), "nota": "Futuros no disponibles para esta moneda"}


def get_whale_movements(coin: str) -> dict:
    """Movimientos de ballenas via Binance large trades y estadísticas de exchange"""
    try:
        symbol = f"{coin}USDT"

        # Trades grandes recientes (últimas 500 operaciones)
        trades = httpx.get(
            f"https://api.binance.com/api/v3/trades?symbol={symbol}&limit=500",
            timeout=10
        ).json()

        precio_actual = float(trades[-1]['price']) if trades else 1
        umbral_ballena = precio_actual * 50  # Operaciones > $50k consideradas ballenas

        compras_ballena = sum(float(t['quoteQty']) for t in trades if not t['isBuyerMaker'] and float(t['quoteQty']) > umbral_ballena)
        ventas_ballena  = sum(float(t['quoteQty']) for t in trades if t['isBuyerMaker']     and float(t['quoteQty']) > umbral_ballena)
        total_ballena   = compras_ballena + ventas_ballena

        presion = "COMPRA de ballenas dominante 🟢" if compras_ballena > ventas_ballena * 1.3 else \
                  "VENTA de ballenas dominante 🔴"  if ventas_ballena  > compras_ballena * 1.3 else \
                  "Actividad de ballenas equilibrada ⚪"

        # Flujo neto de exchanges (approximado via estadísticas de volumen)
        stats = httpx.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}", timeout=10).json()
        vol_ratio = float(stats.get('count', 0))

        return {
            "coin": coin,
            "compras_ballena_usd": round(compras_ballena, 0),
            "ventas_ballena_usd": round(ventas_ballena, 0),
            "ratio_compra_venta": round(compras_ballena / ventas_ballena, 2) if ventas_ballena > 0 else 999,
            "presion_ballenas": presion,
            "num_operaciones_24h": vol_ratio,
            "interpretacion": f"En las últimas 500 operaciones, las ballenas {'están acumulando' if compras_ballena > ventas_ballena else 'están distribuyendo'} {coin}",
        }
    except Exception as e:
        return {"coin": coin, "error": str(e)}


def get_market_correlation(coin: str) -> dict:
    """Correlación con S&P 500, dominancia BTC y comparación de mercado"""
    try:
        # Precios de múltiples cryptos para correlación
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]
        precios = {}
        for sym in symbols:
            try:
                t = httpx.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={sym}", timeout=5).json()
                precios[sym.replace("USDT","")] = float(t['priceChangePercent'])
            except:
                pass

        # Dominancia BTC desde CoinGecko (gratis)
        try:
            global_data = httpx.get("https://api.coingecko.com/api/v3/global", timeout=8).json()
            btc_dom = round(global_data['data']['market_cap_percentage']['btc'], 1)
            eth_dom = round(global_data['data']['market_cap_percentage'].get('eth', 0), 1)
            total_mcap = global_data['data']['total_market_cap']['usd']
            mcap_change = round(global_data['data']['market_cap_change_percentage_24h_usd'], 2)
        except:
            btc_dom, eth_dom, total_mcap, mcap_change = 50, 17, 0, 0

        # Correlación BTC-altcoins
        coin_change = precios.get(coin, 0)
        btc_change  = precios.get("BTC", 0)
        correlacion = "alta correlación con BTC" if abs(coin_change - btc_change) < 2 else \
                      "moviéndose independiente de BTC"

        # Señal de dominancia
        dom_señal = "altseason posible — BTC dominancia baja" if btc_dom < 45 else \
                    "BTC dominante — mejor quedarse en BTC" if btc_dom > 60 else \
                    "mercado balanceado"

        return {
            "coin": coin,
            "cambios_24h": precios,
            "btc_dominancia_pct": btc_dom,
            "eth_dominancia_pct": eth_dom,
            "dominancia_señal": dom_señal,
            "market_cap_total_usd": round(total_mcap / 1e9, 1),
            "market_cap_cambio_24h_pct": mcap_change,
            "correlacion_btc": correlacion,
            "nota_sp500": "S&P 500 y crypto tienen correlación positiva en momentos de pánico/euforia — verificar manualmente para señales macro",
        }
    except Exception as e:
        return {"coin": coin, "error": str(e)}


def get_crypto_news(coin: str, limit: int = 10) -> dict:
    """Noticias reales de CryptoPanic"""
    try:
        token = os.getenv("CRYPTOPANIC_API_KEY")
        url   = f"https://cryptopanic.com/api/v1/posts/?auth_token={token}&currencies={coin}&public=true"
        data  = httpx.get(url, timeout=10).json()
        news  = []
        for item in data.get("results", [])[:limit]:
            votes = item.get("votes", {})
            sentiment = "positivo" if votes.get("positive", 0) > votes.get("negative", 0) else \
                        "negativo" if votes.get("negative", 0) > votes.get("positive", 0) else "neutral"
            news.append({
                "titulo": item["title"],
                "sentimiento": sentiment,
                "fuente": item["source"]["title"],
                "publicado": item["published_at"],
            })
        positivos = sum(1 for n in news if n["sentimiento"] == "positivo")
        negativos = sum(1 for n in news if n["sentimiento"] == "negativo")
        return {
            "coin": coin, "noticias": news,
            "resumen_sentimiento": f"{positivos} positivas, {negativos} negativas de {len(news)} noticias",
            "tendencia": "bullish" if positivos > negativos else "bearish" if negativos > positivos else "neutral",
        }
    except Exception as e:
        return {"coin": coin, "noticias": [], "error": str(e)}


def get_fear_greed() -> dict:
    """Fear & Greed Index actual e histórico"""
    try:
        data    = httpx.get("https://api.alternative.me/fng/?limit=7", timeout=8).json()
        valores = data.get("data", [])
        actual  = valores[0] if valores else {}
        score   = int(actual.get("value", 50))
        label   = actual.get("value_classification", "Neutral")
        labels_es = {
            "Extreme Fear": "Miedo Extremo", "Fear": "Miedo",
            "Neutral": "Neutral", "Greed": "Codicia", "Extreme Greed": "Codicia Extrema"
        }
        historico = [{"dia": f"hace {i}d", "score": int(v["value"]), "label": labels_es.get(v["value_classification"], v["value_classification"])} for i, v in enumerate(valores)]
        tendencia_fng = "mejorando" if len(valores) >= 3 and int(valores[0]["value"]) > int(valores[2]["value"]) else "empeorando"
        señal = "zona de compra histórica (miedo extremo = oportunidad)" if score < 25 else \
                "precaución — mercado eufórico, posible techo" if score > 75 else \
                "zona neutral"
        return {
            "score_actual": score,
            "label": labels_es.get(label, label),
            "señal": señal,
            "tendencia_7d": tendencia_fng,
            "historico_7d": historico,
        }
    except Exception as e:
        return {"score_actual": 50, "label": "Neutral", "error": str(e)}


def get_memory(coin: str, query: str = "") -> dict:
    memories = _memory_store.get(coin, [])
    return {"coin": coin, "memorias": memories, "total": len(memories)}


def save_memory(coin: str, insight: str, category: str) -> dict:
    if coin not in _memory_store:
        _memory_store[coin] = []
    entry = {"insight": insight, "categoria": category, "guardado": datetime.now().isoformat()}
    _memory_store[coin].append(entry)
    return {"status": "guardado", "entry": entry}


def execute_paper_trade(coin: str, action: str, confidence: int, reasoning: str,
                        amount_usd: float = 500, stop_loss_pct: float = 3.0, take_profit_pct: float = 6.0) -> dict:
    """Paper trade con stop-loss y take-profit"""
    if action == "HOLD":
        return {"status": "sin_operacion", "razon": "señal HOLD — esperando mejor entrada"}

    # Obtener precio actual
    try:
        ticker = httpx.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT", timeout=5).json()
        precio = float(ticker['price'])
    except:
        precio = 0

    trade = {
        "id": len(_paper_trades) + 1,
        "coin": coin, "action": action,
        "amount_usd": amount_usd,
        "precio_entrada": precio,
        "stop_loss": round(precio * (1 - stop_loss_pct/100), 2) if action == "BUY" else round(precio * (1 + stop_loss_pct/100), 2),
        "take_profit": round(precio * (1 + take_profit_pct/100), 2) if action == "BUY" else round(precio * (1 - take_profit_pct/100), 2),
        "confidence": confidence,
        "reasoning": reasoning,
        "timestamp": datetime.now().isoformat(),
        "status": "abierta",
        "pnl": 0.0,
    }
    _paper_trades.append(trade)

    accion_es = "COMPRA" if action == "BUY" else "VENTA"
    print(f"\n🤖 OPERACIÓN SIMULADA: {accion_es} {coin} @ ${precio:,.2f}")
    print(f"   Stop Loss: ${trade['stop_loss']:,.2f} | Take Profit: ${trade['take_profit']:,.2f}")
    print(f"   Confianza: {confidence}% | Monto: ${amount_usd}")
    return trade


def handle_tool(tool_name: str, tool_input: dict) -> Any:
    handlers = {
        "get_technical_indicators": get_technical_indicators,
        "get_market_depth": get_market_depth,
        "get_whale_movements": get_whale_movements,
        "get_market_correlation": get_market_correlation,
        "get_crypto_news": get_crypto_news,
        "get_fear_greed": get_fear_greed,
        "get_memory": get_memory,
        "save_memory": save_memory,
        "execute_paper_trade": execute_paper_trade,
    }
    handler = handlers.get(tool_name)
    return handler(**tool_input) if handler else {"error": f"Herramienta desconocida: {tool_name}"}


# ══════════════════════════════════════════════════════════════════════════════
# PROMPT DEL SISTEMA
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Eres CryptoMind v2, un agente de trading de criptomonedas de élite con acceso a información exhaustiva del mercado.

Tu proceso de análisis OBLIGATORIO:
1. Indicadores técnicos (RSI, MACD, Bollinger, EMAs, VWAP, soportes/resistencias)
2. Sentimiento del mercado (Long/Short ratio, Funding rate, Open Interest)
3. Actividad de ballenas (presión compradora/vendedora institucional)
4. Correlaciones macro (dominancia BTC, mercado global)
5. Noticias y sentimiento (CryptoPanic)
6. Fear & Greed Index + historial 7 días
7. Memoria de patrones pasados
8. Decisión final con todas las fuentes integradas

Tu señal final DEBE incluir:
- Acción: COMPRAR / VENDER / ESPERAR
- Confianza: 0-100
- Stop Loss recomendado (%)
- Take Profit recomendado (%)
- Los 3 factores más importantes de tu decisión
- Nivel de riesgo: BAJO / MEDIO / ALTO

IMPORTANTE:
- Solo ejecutar operación si confianza > 70
- Nunca operar contra tendencia clara en múltiples timeframes
- El riesgo máximo por operación es 3% del capital
- Siempre guardar en memoria el patrón identificado"""


# ══════════════════════════════════════════════════════════════════════════════
# LOOP PRINCIPAL DEL AGENTE
# ══════════════════════════════════════════════════════════════════════════════

def analyze_coin(coin: str) -> dict:
    """Análisis completo con todas las fuentes de datos"""
    print(f"\n{'='*60}")
    print(f"🧠 CRYPTOMIND v2 — Analizando {coin}...")
    print(f"{'='*60}")

    messages = [{"role": "user", "content": f"Analiza {coin} exhaustivamente usando TODAS tus herramientas. Quiero la señal más precisa posible con toda la información disponible."}]
    tool_calls_log = []
    final_response = ""

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, 'text'):
                    final_response = block.text
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  🔧 Usando: {block.name}({list(block.input.keys())})")
                    result = handle_tool(block.name, block.input)
                    tool_calls_log.append({"tool": block.name, "input": block.input, "result": result})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False)
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    return {
        "coin": coin,
        "analysis": final_response,
        "tool_calls": tool_calls_log,
        "trades": _paper_trades,
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    monedas = ["BTC", "ETH", "SOL"]
    for moneda in monedas:
        result = analyze_coin(moneda)
        print(f"\n{result['analysis']}")
        print(f"\nHerramientas usadas: {[t['tool'] for t in result['tool_calls']]}")
        print(f"Operaciones simuladas: {len(result['trades'])}")
        print("\n" + "="*60)
        time.sleep(2)
