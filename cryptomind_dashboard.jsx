import { useState, useEffect } from "react";
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";

const COINS = ["BTC", "ETH", "SOL", "BNB", "ADA"];

const COLORS = {
  BTC: "#F7931A",
  ETH: "#627EEA",
  SOL: "#9945FF",
  BNB: "#F3BA2F",
  ADA: "#0033AD",
};

function generatePnL() {
  let val = 10000;
  return Array.from({ length: 30 }, (_, i) => {
    val += (Math.random() - 0.42) * 300;
    return { day: `D${i + 1}`, value: Math.round(val) };
  });
}

function generateSignals() {
  const actions = ["BUY", "SELL", "HOLD"];
  const sentiments = ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"];
  return COINS.map((coin) => ({
    coin,
    action: actions[Math.floor(Math.random() * 3)],
    confidence: Math.floor(Math.random() * 40) + 55,
    price: { BTC: 68420, ETH: 3512, SOL: 183, BNB: 418, ADA: 0.64 }[coin],
    change: (Math.random() * 14 - 7).toFixed(2),
    sentiment: sentiments[Math.floor(Math.random() * 5)],
    rsi: Math.floor(Math.random() * 50) + 25,
    newsCount: Math.floor(Math.random() * 8) + 2,
  }));
}

function generateTrades() {
  const base = new Date();
  return Array.from({ length: 12 }, (_, i) => {
    const coin = COINS[Math.floor(Math.random() * COINS.length)];
    const action = Math.random() > 0.5 ? "BUY" : "SELL";
    const pnl = (Math.random() * 400 - 150).toFixed(2);
    const d = new Date(base - i * 3600000 * 4);
    return {
      id: i + 1, coin, action, pnl: parseFloat(pnl),
      confidence: Math.floor(Math.random() * 25) + 65,
      time: d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      date: d.toLocaleDateString([], { month: "short", day: "numeric" }),
    };
  });
}

function generateMemories() {
  return [
    { coin: "BTC", insight: "SEC news correlates with -8% drop within 4h — seen 3 times", category: "news_pattern", age: "2d ago" },
    { coin: "ETH", insight: "ETH tends to follow BTC with 2h delay on major moves", category: "correlation", age: "5d ago" },
    { coin: "SOL", insight: "Outperforms market when overall greed > 70", category: "price_pattern", age: "1w ago" },
    { coin: "BTC", insight: "ETF inflow news drives +3-5% in 24h on average", category: "news_pattern", age: "3d ago" },
    { coin: "ADA", insight: "Low volume + high RSI = reversal signal (accuracy 71%)", category: "price_pattern", age: "4d ago" },
  ];
}

const pnlData = generatePnL();
const finalPnL = pnlData[pnlData.length - 1].value;
const pnlPct = (((finalPnL - 10000) / 10000) * 100).toFixed(1);

export default function CryptoMindDashboard() {
  const [signals, setSignals] = useState(generateSignals());
  const [trades] = useState(generateTrades());
  const [memories] = useState(generateMemories());
  const [selected, setSelected] = useState("BTC");
  const [tab, setTab] = useState("signals");
  const [analyzing, setAnalyzing] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [agentThoughts, setAgentThoughts] = useState([]);

  const simulateAnalysis = () => {
    setAnalyzing(true);
    setAgentThoughts([]);
    const steps = [
      "⚡ Fetching latest news from CryptoPanic...",
      "📊 Loading price data from Binance API...",
      "🧠 Querying memory for past BTC patterns...",
      "📰 Analyzing sentiment: 3 positive, 1 negative news items",
      "📈 RSI at 52 — neutral zone, MACD showing bullish crossover",
      "💡 Memory match: ETF inflow news → avg +4.2% in 24h (seen 4x)",
      "🔮 Fear & Greed Index: 68 (Greed) — favorable for longs",
      "✅ Signal: BUY | Confidence: 78/100 | Executing paper trade...",
    ];
    steps.forEach((s, i) => {
      setTimeout(() => {
        setAgentThoughts((prev) => [...prev, s]);
        if (i === steps.length - 1) {
          setAnalyzing(false);
          setSignals(generateSignals());
          setLastUpdate(new Date());
        }
      }, i * 600);
    });
  };

  const selectedSignal = signals.find((s) => s.coin === selected);
  const winRate = Math.round((trades.filter((t) => t.pnl > 0).length / trades.length) * 100);
  const totalPnL = trades.reduce((acc, t) => acc + t.pnl, 0).toFixed(2);

  return (
    <div style={{ fontFamily: "'Space Mono', 'Courier New', monospace", background: "#030712", minHeight: "100vh", color: "#e2e8f0", padding: "0" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Orbitron:wght@500;700;900&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-track { background: #0f172a; } ::-webkit-scrollbar-thumb { background: #334155; border-radius: 2px; }
        .glow { box-shadow: 0 0 20px rgba(99,102,241,0.15); }
        .coin-btn { transition: all 0.2s; cursor: pointer; border: none; }
        .coin-btn:hover { transform: translateY(-2px); }
        .trade-row:hover { background: rgba(99,102,241,0.05) !important; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        @keyframes slideIn { from{transform:translateX(-10px);opacity:0} to{transform:translateX(0);opacity:1} }
        .thought { animation: slideIn 0.3s ease forwards; }
        .scanning { animation: pulse 1.5s infinite; }
      `}</style>

      {/* Header */}
      <div style={{ background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)", borderBottom: "1px solid #1e293b", padding: "16px 28px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ width: 36, height: 36, background: "linear-gradient(135deg, #6366f1, #8b5cf6)", borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>🧠</div>
          <div>
            <div style={{ fontFamily: "'Orbitron', monospace", fontSize: 18, fontWeight: 900, letterSpacing: 2, color: "#a5b4fc" }}>CRYPTOMIND</div>
            <div style={{ fontSize: 10, color: "#475569", letterSpacing: 3 }}>AI TRADING AGENT</div>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 10, color: "#475569" }}>LAST SCAN</div>
            <div style={{ fontSize: 12, color: "#94a3b8" }}>{lastUpdate.toLocaleTimeString()}</div>
          </div>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: analyzing ? "#fbbf24" : "#22c55e", ...(analyzing ? { animation: "pulse 1s infinite" } : {}) }} />
          <button onClick={simulateAnalysis} disabled={analyzing} style={{ background: analyzing ? "#1e293b" : "linear-gradient(135deg, #6366f1, #8b5cf6)", border: "none", borderRadius: 8, padding: "8px 16px", color: "white", fontSize: 11, fontFamily: "inherit", cursor: analyzing ? "not-allowed" : "pointer", letterSpacing: 1 }}>
            {analyzing ? "SCANNING..." : "▶ RUN AGENT"}
          </button>
        </div>
      </div>

      <div style={{ padding: "20px 28px", maxWidth: 1400, margin: "0 auto" }}>

        {/* Stats Row */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 20 }}>
          {[
            { label: "PORTFOLIO VALUE", value: `$${finalPnL.toLocaleString()}`, sub: `${pnlPct > 0 ? "+" : ""}${pnlPct}% all time`, color: pnlPct > 0 ? "#22c55e" : "#ef4444" },
            { label: "WIN RATE", value: `${winRate}%`, sub: `${trades.filter(t => t.pnl > 0).length}/${trades.length} trades`, color: "#6366f1" },
            { label: "TOTAL P&L", value: `${totalPnL > 0 ? "+" : ""}$${totalPnL}`, sub: "paper trading", color: totalPnL > 0 ? "#22c55e" : "#ef4444" },
            { label: "MEMORY ENTRIES", value: memories.length, sub: "patterns learned", color: "#8b5cf6" },
          ].map((s, i) => (
            <div key={i} style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, padding: "16px 18px" }}>
              <div style={{ fontSize: 9, color: "#475569", letterSpacing: 2, marginBottom: 6 }}>{s.label}</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: s.color, fontFamily: "'Orbitron', monospace" }}>{s.value}</div>
              <div style={{ fontSize: 10, color: "#64748b", marginTop: 4 }}>{s.sub}</div>
            </div>
          ))}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 16, marginBottom: 16 }}>
          {/* P&L Chart */}
          <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, padding: 20 }}>
            <div style={{ fontSize: 10, color: "#475569", letterSpacing: 2, marginBottom: 14 }}>PORTFOLIO PERFORMANCE</div>
            <ResponsiveContainer width="100%" height={160}>
              <AreaChart data={pnlData}>
                <defs>
                  <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="day" tick={{ fill: "#334155", fontSize: 9 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#334155", fontSize: 9 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 8, fontSize: 11 }} formatter={(v) => [`$${v.toLocaleString()}`, "Value"]} />
                <Area type="monotone" dataKey="value" stroke="#6366f1" strokeWidth={2} fill="url(#pnlGrad)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Agent Thoughts */}
          <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, padding: 20 }}>
            <div style={{ fontSize: 10, color: "#475569", letterSpacing: 2, marginBottom: 14 }}>AGENT REASONING</div>
            <div style={{ fontSize: 10, color: "#334155", marginBottom: 10 }}>
              {analyzing ? <span className="scanning" style={{ color: "#fbbf24" }}>● AGENT RUNNING</span> : agentThoughts.length ? <span style={{ color: "#22c55e" }}>● ANALYSIS COMPLETE</span> : "Click RUN AGENT to watch it think →"}
            </div>
            <div style={{ height: 150, overflowY: "auto", display: "flex", flexDirection: "column", gap: 6 }}>
              {agentThoughts.length === 0 && !analyzing && (
                <div style={{ color: "#1e293b", fontSize: 11, lineHeight: 1.8 }}>
                  {["Fetch news...", "Analyze sentiment...", "Check memory...", "Generate signal...", "Execute trade..."].map((s, i) => (
                    <div key={i} style={{ opacity: 0.3 }}>○ {s}</div>
                  ))}
                </div>
              )}
              {agentThoughts.map((t, i) => (
                <div key={i} className="thought" style={{ fontSize: 10, color: i === agentThoughts.length - 1 ? "#a5b4fc" : "#64748b", lineHeight: 1.4 }}>{t}</div>
              ))}
            </div>
          </div>
        </div>

        {/* Coin Selector */}
        <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
          {COINS.map((coin) => {
            const sig = signals.find((s) => s.coin === coin);
            const isSelected = coin === selected;
            return (
              <button key={coin} className="coin-btn" onClick={() => setSelected(coin)} style={{
                background: isSelected ? `${COLORS[coin]}20` : "#0f172a",
                border: `1px solid ${isSelected ? COLORS[coin] : "#1e293b"}`,
                borderRadius: 10, padding: "10px 16px", color: isSelected ? COLORS[coin] : "#64748b", flex: 1,
              }}>
                <div style={{ fontSize: 13, fontWeight: 700 }}>{coin}</div>
                <div style={{ fontSize: 9, marginTop: 3 }}>{sig?.action} · {sig?.confidence}%</div>
              </button>
            );
          })}
        </div>

        {/* Main Content Tabs */}
        <div style={{ display: "flex", gap: 2, marginBottom: 16, background: "#0f172a", borderRadius: 10, padding: 4, width: "fit-content", border: "1px solid #1e293b" }}>
          {["signals", "trades", "memory"].map((t) => (
            <button key={t} onClick={() => setTab(t)} style={{ background: tab === t ? "#1e293b" : "transparent", border: "none", borderRadius: 7, padding: "6px 16px", color: tab === t ? "#a5b4fc" : "#475569", fontSize: 10, letterSpacing: 1, cursor: "pointer", fontFamily: "inherit", textTransform: "uppercase" }}>
              {t}
            </button>
          ))}
        </div>

        {tab === "signals" && selectedSignal && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
            <div style={{ background: "#0f172a", border: `1px solid ${COLORS[selected]}40`, borderRadius: 12, padding: 20 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                <div>
                  <div style={{ fontSize: 10, color: "#475569", letterSpacing: 2 }}>CURRENT SIGNAL</div>
                  <div style={{ fontSize: 36, fontFamily: "'Orbitron', monospace", fontWeight: 900, color: COLORS[selected], marginTop: 4 }}>{selected}</div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: 22, fontFamily: "'Orbitron', monospace", fontWeight: 700 }}>${selectedSignal.price?.toLocaleString()}</div>
                  <div style={{ color: parseFloat(selectedSignal.change) > 0 ? "#22c55e" : "#ef4444", fontSize: 13 }}>
                    {parseFloat(selectedSignal.change) > 0 ? "▲" : "▼"} {Math.abs(parseFloat(selectedSignal.change))}%
                  </div>
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                <div style={{ background: selectedSignal.action === "BUY" ? "#22c55e20" : selectedSignal.action === "SELL" ? "#ef444420" : "#fbbf2420", border: `1px solid ${selectedSignal.action === "BUY" ? "#22c55e" : selectedSignal.action === "SELL" ? "#ef4444" : "#fbbf24"}`, borderRadius: 8, padding: "6px 16px", color: selectedSignal.action === "BUY" ? "#22c55e" : selectedSignal.action === "SELL" ? "#ef4444" : "#fbbf24", fontWeight: 700, fontSize: 16 }}>
                  {selectedSignal.action}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 10, color: "#475569", marginBottom: 4 }}>CONFIDENCE {selectedSignal.confidence}%</div>
                  <div style={{ height: 6, background: "#1e293b", borderRadius: 3, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: `${selectedSignal.confidence}%`, background: `linear-gradient(90deg, #6366f1, #8b5cf6)`, borderRadius: 3 }} />
                  </div>
                </div>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                {[
                  { label: "SENTIMENT", value: selectedSignal.sentiment },
                  { label: "RSI (14)", value: selectedSignal.rsi },
                  { label: "NEWS ITEMS", value: `${selectedSignal.newsCount} found` },
                  { label: "MEMORY HITS", value: `${Math.floor(Math.random() * 4) + 1} patterns` },
                ].map((item, i) => (
                  <div key={i} style={{ background: "#1e293b", borderRadius: 8, padding: "10px 12px" }}>
                    <div style={{ fontSize: 9, color: "#475569", letterSpacing: 1 }}>{item.label}</div>
                    <div style={{ fontSize: 13, color: "#94a3b8", marginTop: 3 }}>{item.value}</div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, padding: 20 }}>
              <div style={{ fontSize: 10, color: "#475569", letterSpacing: 2, marginBottom: 14 }}>ALL SIGNALS</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {signals.map((s) => (
                  <div key={s.coin} onClick={() => setSelected(s.coin)} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", background: s.coin === selected ? "#1e293b" : "transparent", borderRadius: 8, cursor: "pointer", border: `1px solid ${s.coin === selected ? "#334155" : "transparent"}` }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 8, height: 8, borderRadius: "50%", background: COLORS[s.coin] }} />
                      <span style={{ fontWeight: 700, color: COLORS[s.coin] }}>{s.coin}</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span style={{ fontSize: 10, color: "#475569" }}>{s.confidence}%</span>
                      <span style={{ fontSize: 11, fontWeight: 700, color: s.action === "BUY" ? "#22c55e" : s.action === "SELL" ? "#ef4444" : "#fbbf24" }}>{s.action}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === "trades" && (
          <div style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, overflow: "hidden" }}>
            <div style={{ padding: "14px 20px", borderBottom: "1px solid #1e293b", fontSize: 10, color: "#475569", letterSpacing: 2 }}>PAPER TRADE HISTORY</div>
            {trades.map((t, i) => (
              <div key={t.id} className="trade-row" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderBottom: i < trades.length - 1 ? "1px solid #0f172a" : "none", transition: "background 0.15s" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                  <div style={{ width: 36, height: 36, borderRadius: 8, background: t.action === "BUY" ? "#22c55e15" : "#ef444415", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14 }}>
                    {t.action === "BUY" ? "↑" : "↓"}
                  </div>
                  <div>
                    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <span style={{ fontWeight: 700, color: COLORS[t.coin] }}>{t.coin}</span>
                      <span style={{ fontSize: 10, color: t.action === "BUY" ? "#22c55e" : "#ef4444" }}>{t.action}</span>
                    </div>
                    <div style={{ fontSize: 10, color: "#475569" }}>{t.date} · {t.time} · {t.confidence}% conf</div>
                  </div>
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontFamily: "'Orbitron', monospace", fontWeight: 700, color: t.pnl > 0 ? "#22c55e" : "#ef4444" }}>
                    {t.pnl > 0 ? "+" : ""}${t.pnl}
                  </div>
                  <div style={{ fontSize: 9, color: "#334155" }}>P&L</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "memory" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {memories.map((m, i) => (
              <div key={i} style={{ background: "#0f172a", border: "1px solid #1e293b", borderRadius: 12, padding: 16, display: "flex", gap: 14, alignItems: "flex-start" }}>
                <div style={{ width: 40, height: 40, borderRadius: 8, background: `${COLORS[m.coin]}15`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: 16 }}>🧠</div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
                    <span style={{ fontWeight: 700, color: COLORS[m.coin], fontSize: 12 }}>{m.coin}</span>
                    <span style={{ background: "#1e293b", borderRadius: 4, padding: "2px 8px", fontSize: 9, color: "#6366f1", letterSpacing: 1 }}>{m.category.toUpperCase()}</span>
                    <span style={{ fontSize: 9, color: "#334155", marginLeft: "auto" }}>{m.age}</span>
                  </div>
                  <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.5 }}>{m.insight}</div>
                </div>
              </div>
            ))}
            <div style={{ background: "#0f172a", border: "1px dashed #1e293b", borderRadius: 12, padding: 16, textAlign: "center", color: "#334155", fontSize: 11 }}>
              Memory grows automatically as the agent analyzes more patterns →
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
