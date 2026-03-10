"""
CryptoMind Agent — Core trading intelligence agent
Uses Anthropic API with tool use for crypto analysis
"""

import json
import os
from datetime import datetime
from typing import Any
import anthropic

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_crypto_news",
        "description": "Fetch latest news for a specific cryptocurrency from CryptoPanic API",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string", "description": "Coin symbol e.g. BTC, ETH, SOL"},
                "limit": {"type": "integer", "description": "Number of news items (max 20)", "default": 10}
            },
            "required": ["coin"]
        }
    },
    {
        "name": "get_price_data",
        "description": "Get current price, 24h change, volume and OHLCV data for a coin",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string", "description": "Coin symbol e.g. BTC, ETH"},
                "interval": {"type": "string", "description": "Candle interval: 1h, 4h, 1d", "default": "1h"}
            },
            "required": ["coin"]
        }
    },
    {
        "name": "get_market_sentiment",
        "description": "Get Fear & Greed index and overall market sentiment",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_memory",
        "description": "Retrieve past analysis and patterns stored in agent memory for a coin",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"},
                "query": {"type": "string", "description": "What to search for in memory"}
            },
            "required": ["coin"]
        }
    },
    {
        "name": "save_memory",
        "description": "Save an insight or pattern to agent memory for future use",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"},
                "insight": {"type": "string"},
                "category": {"type": "string", "description": "news_pattern, price_pattern, correlation"}
            },
            "required": ["coin", "insight", "category"]
        }
    },
    {
        "name": "execute_paper_trade",
        "description": "Execute a simulated paper trade (no real money)",
        "input_schema": {
            "type": "object",
            "properties": {
                "coin": {"type": "string"},
                "action": {"type": "string", "enum": ["BUY", "SELL", "HOLD"]},
                "amount_usd": {"type": "number"},
                "confidence": {"type": "integer", "description": "Confidence score 0-100"},
                "reasoning": {"type": "string"}
            },
            "required": ["coin", "action", "confidence", "reasoning"]
        }
    }
]


# ── Tool handlers (connect to real APIs in production) ────────────────────────

def handle_tool(tool_name: str, tool_input: dict) -> Any:
    """Route tool calls to their handlers"""
    handlers = {
        "get_crypto_news": get_crypto_news,
        "get_price_data": get_price_data,
        "get_market_sentiment": get_market_sentiment,
        "get_memory": get_memory,
        "save_memory": save_memory,
        "execute_paper_trade": execute_paper_trade,
    }
    handler = handlers.get(tool_name)
    if handler:
        return handler(**tool_input)
    return {"error": f"Unknown tool: {tool_name}"}


def get_crypto_news(coin: str, limit: int = 10) -> dict:
    """
    In production: connect to CryptoPanic API
    https://cryptopanic.com/api/v1/posts/?auth_token=YOUR_TOKEN&currencies=BTC
    """
    # Mock data for demo — replace with real API call
    mock_news = [
        {"title": f"{coin} ETF sees record inflows this week", "sentiment": "positive", "source": "CoinDesk", "published": "2h ago"},
        {"title": f"Major exchange lists new {coin} trading pairs", "sentiment": "positive", "source": "CryptoPanic", "published": "4h ago"},
        {"title": f"Analyst warns of {coin} correction after 30% rally", "sentiment": "negative", "source": "CoinTelegraph", "published": "6h ago"},
    ]
    return {"coin": coin, "news": mock_news[:limit], "fetched_at": datetime.now().isoformat()}


def get_price_data(coin: str, interval: str = "1h") -> dict:
    """
    In production: connect to Binance API via ccxt
    import ccxt; exchange = ccxt.binance(); exchange.fetch_ohlcv(f'{coin}/USDT', interval)
    """
    import random
    base_prices = {"BTC": 68000, "ETH": 3500, "SOL": 180, "BNB": 420, "ADA": 0.65}
    price = base_prices.get(coin, 1.0) * (1 + random.uniform(-0.05, 0.05))
    return {
        "coin": coin,
        "price_usd": round(price, 2),
        "change_24h": round(random.uniform(-8, 8), 2),
        "volume_24h_usd": round(random.uniform(1e9, 5e10), 0),
        "rsi_14": round(random.uniform(25, 75), 1),
        "macd_signal": random.choice(["bullish", "bearish", "neutral"]),
    }


def get_market_sentiment() -> dict:
    """
    In production: https://api.alternative.me/fng/
    """
    import random
    score = random.randint(20, 80)
    label = "Extreme Fear" if score < 25 else "Fear" if score < 45 else "Neutral" if score < 55 else "Greed" if score < 75 else "Extreme Greed"
    return {"fear_greed_index": score, "label": label, "timestamp": datetime.now().isoformat()}


# Simple in-memory store (replace with Mem0 or Redis in production)
_memory_store: dict = {}

def get_memory(coin: str, query: str = "") -> dict:
    memories = _memory_store.get(coin, [])
    return {"coin": coin, "memories": memories, "count": len(memories)}


def save_memory(coin: str, insight: str, category: str) -> dict:
    if coin not in _memory_store:
        _memory_store[coin] = []
    entry = {"insight": insight, "category": category, "saved_at": datetime.now().isoformat()}
    _memory_store[coin].append(entry)
    return {"status": "saved", "coin": coin, "entry": entry}


# Paper trading ledger (replace with DB in production)
_paper_trades: list = []
_paper_portfolio = {"cash_usd": 10000.0, "positions": {}}

def execute_paper_trade(coin: str, action: str, confidence: int, reasoning: str, amount_usd: float = 500) -> dict:
    trade = {
        "id": len(_paper_trades) + 1,
        "coin": coin,
        "action": action,
        "amount_usd": amount_usd if action != "HOLD" else 0,
        "confidence": confidence,
        "reasoning": reasoning,
        "timestamp": datetime.now().isoformat(),
        "status": "executed" if action != "HOLD" else "skipped"
    }
    if action != "HOLD":
        _paper_trades.append(trade)
    return trade


# ── Main agent loop ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are CryptoMind, an elite crypto trading intelligence agent with persistent memory.

Your capabilities:
- Analyze real-time crypto news and detect FUD vs genuine signals
- Correlate news sentiment with price movements using historical memory
- Generate trading signals with confidence scores and clear reasoning
- Execute paper trades and track performance over time
- Remember patterns: "last time SEC news hit BTC, it dropped 8% in 4h"

Your analysis process:
1. Fetch current news and price data for the requested coin
2. Check memory for relevant past patterns
3. Assess market sentiment context
4. Generate a signal (BUY/SELL/HOLD) with confidence 0-100
5. Save new insights to memory for future use
6. Execute paper trade if confidence > 65

Always be specific, data-driven, and explain your reasoning clearly.
Format your final analysis with: Signal, Confidence, Key Factors, and Risk Warning."""


def analyze_coin(coin: str) -> dict:
    """Run full agent analysis on a coin"""
    messages = [{"role": "user", "content": f"Analyze {coin} right now. Should I buy, sell, or hold? Use all your tools."}]
    
    tool_calls_log = []
    final_response = ""
    
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )
        
        if response.stop_reason == "end_turn":
            final_response = response.content[0].text if response.content else ""
            break
        
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = handle_tool(block.name, block.input)
                    tool_calls_log.append({"tool": block.name, "input": block.input, "result": result})
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result)
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
    result = analyze_coin("BTC")
    print(f"\n{'='*60}")
    print(f"CRYPTOMIND ANALYSIS — {result['coin']}")
    print(f"{'='*60}")
    print(result["analysis"])
    print(f"\nTools used: {[t['tool'] for t in result['tool_calls']]}")
    print(f"Paper trades executed: {len(result['trades'])}")
