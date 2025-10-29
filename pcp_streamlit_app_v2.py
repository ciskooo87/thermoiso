
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

st.set_page_config(page_title="PCP – Dashboard Dinâmico v3 (fix)", layout="wide")
st.title("PCP – Dashboard Dinâmico v3 (fix)")
st.caption("Correção de comparação de datas e janela do período anterior.")

# -----------------------------
# Helpers
# -----------------------------
def format_brl(x, dec=0):
    try:
        s = f"{x:,.{dec}f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {s}"
    except Exception:
        return "R$ 0"

def load_base():
    up = st.sidebar.file_uploader("Substituir base padrão (CSV com colunas do template)", type=["csv"])
    if up is not None:
        df = pd.read_csv(up)
    else:
        df = pd.read_csv("pcp_data.csv")
    # Coerce datetime and clean
    if "month" not in df.columns:
        st.stop()
    df["month"] = pd.to_datetime(df["month"], errors="coerce")
    df = df.dropna(subset=["month"]).sort_values("month").reset_index(drop=True)
    return df

# -----------------------------
# Data
# -----------------------------
df = load_base()

# Sidebar filters
st.sidebar.header("Filtros")
min_d, max_d = df["month"].min().date(), df["month"].max().date()

preset = st.sidebar.selectbox("Preset de período", ["Custom", "Últimos 6 meses", "Últimos 12 meses"])
if preset == "Últimos 6 meses":
    start_dt = pd.to_datetime(max_d) - pd.DateOffset(months=6)
    end_dt = pd.to_datetime(max_d)
elif preset == "Últimos 12 meses":
    start_dt = pd.to_datetime(max_d) - pd.DateOffset(months=12)
    end_dt = pd.to_datetime(max_d)
else:
    start_dt = pd.to_datetime(st.sidebar.date_input("Início", min_d))
    end_dt = pd.to_datetime(st.sidebar.date_input("Fim", max_d))

# Current window
mask = (df["month"] >= start_dt) & (df["month"] <= end_dt)
dff = df.loc[mask].copy()

# Previous window — use Timedelta (NOT to_datetime on integers)
window_days = int((end_dt - start_dt).days) + 1
prev_end = start_dt - pd.Timedelta(days=1)
prev_start = prev_end - pd.Timedelta(days=max(0, window_days - 1))

mask_prev = (df["month"] >= prev_start) & (df["month"] <= prev_end)
dfp = df.loc[mask_prev].copy()

# Tabs
tab1, tab2, tab3 = st.tabs(["Overview", "Custo de Perda vs. Meta", "Simulador — No-Cut <7d"])

# -----------------------------
# Tab 1 — Overview
# -----------------------------
with tab1:
    if dff.empty:
        st.warning("Período sem dados.")
    else:
        # KPIs atuais
        lead_time = dff["lead_time_mean"].mean()
        efetividade = dff["efetividade_media"].mean()
        perda_prem_r = dff["perda_prem_R"].sum()
        pct_prem = dff["pct_refugo_prem"].replace(0, np.nan).mean()

        # KPIs período anterior
        lead_time_p = dfp["lead_time_mean"].mean() if not dfp.empty else np.nan
        efetividade_p = dfp["efetividade_media"].mean() if not dfp.empty else np.nan
        perda_prem_r_p = dfp["perda_prem_R"].sum() if not dfp.empty else np.nan
        pct_prem_p = dfp["pct_refugo_prem"].replace(0, np.nan).mean() if not dfp.empty else np.nan

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Lead time médio (dias)", f"{lead_time:.2f}", None if np.isnan(lead_time_p) else f"{lead_time - lead_time_p:+.2f}")
        c2.metric("Efetividade média", f"{efetividade:.2f}x", None if np.isnan(efetividade_p) else f"{efetividade - efetividade_p:+.2f}x")
        c3.metric("Perda prematura (R$)", format_brl(perda_prem_r), None if np.isnan(perda_prem_r_p) else format_brl(perda_prem_r - perda_prem_r_p))
        c4.metric("% refugo por corte prematuro", f"{0 if np.isnan(pct_prem) else pct_prem:.1f}%", None if np.isnan(pct_prem_p) else f"{(pct_prem - pct_prem_p):+.1f}pp")

        st.subheader("Série temporal — Lead time médio (dias)")
        fig1, ax1 = plt.subplots()
        ax1.plot(dff["month"], dff["lead_time_mean"])
        ax1.set_xlabel("Mês")
        ax1.set_ylabel("Dias")
        ax1.set_title("Lead time médio (dias) - Mensal")
        st.pyplot(fig1)

        st.subheader("Série temporal — % do refugo devido a corte prematuro")
        fig2, ax2 = plt.subplots()
        ax2.plot(dff["month"], dff["pct_refugo_prem"])
        ax2.set_xlabel("Mês")
        ax2.set_ylabel("%")
        ax2.set_title("% do refugo atribuído ao corte prematuro - Mensal")
        st.pyplot(fig2)

        st.subheader("Tabela — Base mensal filtrada")
        st.dataframe(dff)

# -----------------------------
# Tab 2 — Custo de Perda vs. Meta
# -----------------------------
with tab2:
    meta = st.number_input("Meta mensal (R$)", min_value=0, value=50000, step=5000)
    dff2 = dff.copy()
    dff2["meta"] = meta
    dff2["gap"] = dff2["perda_prem_R"] - dff2["meta"]

    c1, c2 = st.columns(2)
    c1.metric("Perda total no período (R$)", format_brl(dff2["perda_prem_R"].sum()))
    c2.metric("Desvio total vs. meta (R$)", format_brl(dff2["gap"].sum()))

    st.subheader("Perda por corte prematuro x meta — Mensal")
    fig3, ax3 = plt.subplots()
    ax3.plot(dff2["month"], dff2["perda_prem_R"], label="Perda (R$)")
    ax3.plot(dff2["month"], dff2["meta"], label="Meta (R$)")
    ax3.set_xlabel("Mês")
    ax3.set_ylabel("R$")
    ax3.set_title("Perda prematura vs. meta")
    ax3.legend()
    st.pyplot(fig3)

    st.subheader("Tabela — Perda, Meta e Gap")
    show = dff2[["month","perda_prem_R","meta","gap"]].copy()
    show.columns = ["Mês", "Perda (R$)", "Meta (R$)", "Gap (R$)"]
    st.dataframe(show)

# -----------------------------
# Tab 3 — Simulador No-Cut <7d
# -----------------------------
with tab3:
    colA, colB = st.columns(2)
    compliance = colA.slider("Compliance em No-Cut <7d (%)", min_value=0, max_value=100, value=50, step=5)
    meta_alvo = colB.number_input("Meta mensal alvo (R$)", min_value=0, value=50000, step=5000)

    dff3 = dff.copy()
    factor = (100 - compliance) / 100.0
    dff3["perda_prem_R_simulada"] = dff3["perda_prem_R"] * factor

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Perda atual (R$)", format_brl(dff["perda_prem_R"].sum()))
    col_b.metric("Perda simulada (R$)", format_brl(dff3["perda_prem_R_simulada"].sum()))
    economia = dff["perda_prem_R"].sum() - dff3["perda_prem_R_simulada"].sum()
    col_c.metric("Economia estimada (R$)", format_brl(economia))

    st.subheader("Série — Perda atual vs. simulada")
    fig4, ax4 = plt.subplots()
    ax4.plot(dff["month"], dff["perda_prem_R"], label="Atual")
    ax4.plot(dff3["month"], dff3["perda_prem_R_simulada"], label="Simulada")
    ax4.set_xlabel("Mês")
    ax4.set_ylabel("R$")
    ax4.set_title("Perda prematura — Atual vs. Simulada")
    ax4.legend()
    st.pyplot(fig4)

    # Breakeven de compliance
    if not dff.empty:
        media_atual = dff["perda_prem_R"].mean()
        if media_atual > 0:
            comp_needed = 100 * (1 - (meta_alvo / media_atual))
            comp_needed = max(0, min(100, comp_needed))
            st.metric("Compliance necessário (breakeven) para bater a meta", f"{comp_needed:.1f}%")
        else:
            st.info("Perda média atual é zero — já está abaixo de qualquer meta positiva.")
