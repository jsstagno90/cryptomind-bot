# 🧠 CryptoMind Agent

> An AI-powered crypto trading intelligence agent with persistent memory, real-time news analysis, and automated paper trading.

![Python](https://img.shields.io/badge/Python-3.11+-blue) ![Anthropic](https://img.shields.io/badge/Anthropic-Claude--Sonnet-purple) ![License](https://img.shields.io/badge/License-MIT-green)

---

## 🎯 What it does

CryptoMind is an autonomous agent that:

1. **Monitors crypto news 24/7** — CryptoPanic, CoinDesk, Reddit, Twitter
2. **Analyzes with Claude** — detects FUD vs genuine signals, extracts sentiment
3. **Remembers patterns** — *"last time SEC news hit BTC, it dropped 8% in 4h"*
4. **Generates trading signals** — BUY/SELL/HOLD with confidence score 0-100
5. **Paper trades automatically** — simulated portfolio with full P&L tracking
6. **Sends Telegram alerts** — only when confidence > threshold

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     DATA SOURCES                        │
│  CryptoPanic · CoinDesk RSS · Reddit · Fear&Greed API  │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  CRYPTOMIND AGENT                       │
│                                                         │
│   Claude Sonnet (tool use) ←──→ Memory (Mem0 + Qdrant) │
│          │                                              │
│   ┌──────┴───────┐                                      │
│   │  TOOL SUITE  │                                      │
│   │ get_news     │                                      │
│   │ get_price    │                                      │
│   │ get_sentiment│                                      │
│   │ get_memory   │                                      │
│   │ save_memory  │                                      │
│   │ paper_trade  │                                      │
│   └──────────────┘                                      │
└──────────────────────┬──────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    Streamlit      Telegram      SQLite
    Dashboard       Alerts       Ledger
```

---

## ⚡ Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/yourusername/cryptomind-agent
cd cryptomind-agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
cp .env.example .env
# Edit .env with your API keys

# 4. Run the agent (single analysis)
python agent/crypto_agent.py

# 5. Launch dashboard
streamlit run dashboard/app.py

# 6. Run continuous monitoring
python run.py --interval 30  # analyze every 30 minutes
```

---

## 🔑 API Keys Required

| Service | Free? | Purpose |
|---------|-------|---------|
| [Anthropic](https://console.anthropic.com) | $5 free credit | Core AI reasoning |
| [CryptoPanic](https://cryptopanic.com/api) | ✅ Free | Crypto news feed |
| [Binance](https://binance.com/api) | ✅ Free (read-only) | Price data |
| [Mem0](https://mem0.ai) | ✅ Free tier | Persistent memory |
| Telegram Bot | ✅ Free | Alerts (optional) |

---

## 🧠 Memory System

The agent uses a two-layer memory architecture:

**Episodic Memory (Mem0)**
- Stores specific past events and their outcomes
- *"On March 3rd, ETF approval news → BTC +12% in 6h"*

**Semantic Memory (Qdrant)**
- Stores generalized patterns as vector embeddings
- Enables similarity search: *"find past events similar to current news"*

```python
# Memory is automatically built as the agent runs
agent.save_memory(
    coin="BTC",
    insight="ETF inflow news correlates with +4.2% avg 24h gain",
    category="news_pattern"
)

# And recalled when needed
past_patterns = agent.get_memory("BTC", query="ETF regulatory news")
```

---

## 📊 Paper Trading

All trades are simulated — no real money at risk.

```
Starting capital: $10,000 USD (virtual)
Trade size: $500 per signal
Min confidence to trade: 65/100
Coins: BTC, ETH, SOL, BNB, ADA
```

Track performance vs. simple buy-and-hold to evaluate signal quality.

---

## 🗂️ Project Structure

```
cryptomind/
├── agent/
│   ├── crypto_agent.py      # Core agent with tool use
│   ├── tools/
│   │   ├── news.py          # CryptoPanic + RSS fetchers
│   │   ├── price.py         # Binance/ccxt integration
│   │   └── trading.py       # Paper trading execution
│   └── memory/
│       ├── episodic.py      # Mem0 integration
│       └── semantic.py      # Qdrant vector store
├── dashboard/
│   └── app.py               # Streamlit dashboard
├── config/
│   └── settings.py          # Configuration management
├── tests/
│   └── test_agent.py        # Unit tests
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🚀 Roadmap

- [ ] Live Binance Testnet integration (real API, fake money)
- [ ] Multi-agent system (researcher + trader + risk manager)
- [ ] Backtesting engine (test signals on 1 year of historical data)
- [ ] Web3 wallet monitoring for whale alerts
- [ ] Discord bot integration

---

## ⚠️ Disclaimer

This project is for educational purposes only. It uses paper trading (simulated money). Not financial advice. Never invest more than you can afford to lose.

---

## 📝 License

MIT — use freely, attribution appreciated.
