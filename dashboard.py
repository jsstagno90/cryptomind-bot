"""
CryptoMind Dashboard — Interfaz Streamlit en Español
Ejecutar con: streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

load_dotenv(r"C:\Users\jssta\OneDrive\Escritorio\Proyecto crypto\.env")

sys.path.append(str(Path(__file__).parent))
from crypto_agent import analyze_coin, _paper_trades, _paper_portfolio

st.set_page_config(page_title="CryptoMind Agente", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #030712; color: #e2e8f0; }
    .senal-compra { background: #22c55e20; border: 1px solid #22c55e; border-radius: 8px; padding: 12px; color: #22c55e; font-weight: bold; text-align: center; font-size: 18px; }
    .senal-venta  { background: #ef444420; border: 1px solid #ef4444; border-radius: 8px; padding: 12px; color: #ef4444; font-weight: bold; text-align: center; font-size: 18px; }
    .senal-espera { background: #fbbf2420; border: 1px solid #fbbf24; border-radius: 8px; padding: 12px; color: #fbbf24; font-weight: bold; text-align: center; font-size: 18px; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## 🧠 CRYPTOMIND")
    st.markdown("*Agente de Trading con IA*")
    st.markdown("---")
    moneda = st.selectbox("Seleccionar moneda", ["BTC", "ETH", "SOL", "BNB", "ADA"])
    st.markdown("---")
    st.markdown("### 💼 Portafolio Virtual")
    st.metric("Capital disponible", f"${_paper_portfolio['cash_usd']:,.0f}")
    st.metric("Operaciones totales", len(_paper_trades))
    ganancia_total = sum(t.get('pnl', 0) for t in _paper_trades)
    st.metric("P&L Total", f"${ganancia_total:+.2f}")
    st.markdown("---")
    st.caption(f"Última actualización: {datetime.now().strftime('%H:%M:%S')}")

st.markdown("# ⚡ CRYPTOMIND — PANEL DE CONTROL")
st.markdown("---")

col1, col2, col3, col4 = st.columns(4)
with col1: st.metric("Monedas monitoreadas", "5")
with col2: st.metric("Operaciones ejecutadas", len(_paper_trades))
with col3:
    ganadoras = len([t for t in _paper_trades if t.get('pnl', 0) > 0])
    tasa = f"{(ganadoras/len(_paper_trades)*100):.0f}%" if _paper_trades else "—"
    st.metric("Tasa de acierto", tasa)
with col4: st.metric("Capital inicial", "$10,000")

st.markdown("---")

boton = st.button(f"▶ ANALIZAR {moneda} AHORA", type="primary", use_container_width=True)

if boton:
    with st.spinner(f"🧠 El agente está analizando {moneda}..."):
        placeholder = st.empty()
        pasos = []
        for paso in [
            f"📰 Obteniendo noticias de {moneda} desde CryptoPanic...",
            f"📊 Consultando precio en tiempo real desde Binance...",
            "🌡️ Verificando índice de Miedo y Codicia...",
            "🧠 Buscando patrones en la memoria del agente...",
            "🔮 Generando señal de trading...",
        ]:
            pasos.append(paso)
            placeholder.info("\n\n".join(pasos))
            time.sleep(0.4)

        resultado = analyze_coin(moneda)
        placeholder.empty()
        st.session_state['ultimo_resultado'] = resultado
        st.session_state['ultima_moneda'] = moneda
        st.success(f"✅ ¡Análisis completo para {moneda}!")

if 'ultimo_resultado' in st.session_state:
    resultado = st.session_state['ultimo_resultado']
    moneda_actual = st.session_state['ultima_moneda']
    st.markdown("---")
    st.markdown(f"## 📊 Análisis de {moneda_actual}")

    trade_ejecutado = next((t for t in resultado['tool_calls'] if t['tool'] == 'execute_paper_trade'), None)
    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("### 🤖 Análisis del Agente")
        st.markdown(resultado['analysis'])

    with col2:
        st.markdown("### 🛠️ Herramientas Usadas")
        nombres_es = {
            "get_crypto_news": "📰 Noticias crypto",
            "get_price_data": "📊 Precio en tiempo real",
            "get_market_sentiment": "🌡️ Sentimiento del mercado",
            "get_memory": "🧠 Consulta de memoria",
            "save_memory": "💾 Guardado en memoria",
            "execute_paper_trade": "🤖 Operación simulada",
        }
        for tool in resultado['tool_calls']:
            st.markdown(f"✓ {nombres_es.get(tool['tool'], tool['tool'])}")

        if trade_ejecutado:
            st.markdown("---")
            trade = trade_ejecutado['result']
            mapa = {"BUY": ("COMPRAR", "senal-compra"), "SELL": ("VENDER", "senal-venta"), "HOLD": ("ESPERAR", "senal-espera")}
            texto, clase = mapa.get(trade['action'], ("ESPERAR", "senal-espera"))
            st.markdown(f'<div class="{clase}">📌 OPERACIÓN SIMULADA<br>{texto} {moneda_actual}<br>Confianza: {trade["confidence"]}%</div>', unsafe_allow_html=True)

if _paper_trades:
    st.markdown("---")
    st.markdown("## 📋 Historial de Operaciones Simuladas")
    df = pd.DataFrame(_paper_trades)
    mapa_accion = {"BUY": "COMPRAR", "SELL": "VENDER", "HOLD": "ESPERAR"}
    if 'action' in df.columns:
        df['Acción'] = df['action'].map(mapa_accion)
    if 'pnl' not in df.columns:
        df['pnl'] = 0.0
    cols = {c: n for c, n in [('coin','Moneda'),('Acción','Acción'),('confidence','Confianza (%)'),('pnl','P&L (USD)'),('timestamp','Fecha/Hora')] if c in df.columns}
    st.dataframe(df[list(cols.keys())].rename(columns=cols), use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("⚠️ Solo paper trading — sin dinero real involucrado. No es asesoramiento financiero.")
