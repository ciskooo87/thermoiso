
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
from matplotlib.ticker import FuncFormatter
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from pathlib import Path

st.set_page_config(page_title="PCP – Dashboard Dinâmico v5.1", layout="wide")

# -----------------------------
# Branding (logo)
# -----------------------------
logo_path = Path("icon128.png")
if not logo_path.exists():
    alt = Path("/mnt/data/icon128.png")
    if alt.exists():
        logo_path = alt

colA, colB = st.columns([0.1, 0.9])
if logo_path.exists():
    colA.image(str(logo_path), use_container_width=True)  # updated param
colB.title("PCP – Dashboard Dinâmico v5.1")
st.caption("Gráficos aprimorados + metas dinâmicas por família/célula + simuladores.")

# -----------------------------
# Helpers
# -----------------------------
def format_brl(x, pos=None, dec=0):
    try:
        s = f"{x:,.{dec}f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {s}"
    except Exception:
        return "R$ 0"

def date_axes(ax):
    locator = AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))
    ax.grid(True, linewidth=0.6, alpha=0.5)

def annotate_peaks(ax, x, y, topn=3, fmt=lambda v: f"{v:.2f}"):
    if len(y) == 0:
        return
    idx = np.argsort(y)[-topn:]
    for i in idx:
        ax.annotate(fmt(y[i]), (x[i], y[i]), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=9)

def rolling_series(series, window):
    if window is None or window <= 1:
        return None
    return series.rolling(window=window, min_periods=max(1, window//2)).mean()

def load_base():
    up = st.sidebar.file_uploader("Substituir base padrão (CSV do template)", type=["csv"])
    if up is not None:
        df = pd.read_csv(up, parse_dates=["month"])
        st.sidebar.success("Base oficial carregada.")
    else:
        df = pd.read_csv("pcp_data.csv", parse_dates=["month"])
    return df

# -----------------------------
# Data & Filters
# -----------------------------
df = load_base().sort_values("month").reset_index(drop=True)

st.sidebar.header("Filtros")
min_d, max_d = df["month"].min().date(), df["month"].max().date()
preset = st.sidebar.selectbox("Preset de período", ["Custom", "Últimos 6 meses", "Últimos 12 meses"])
if preset == "Últimos 6 meses":
    start = pd.to_datetime(max_d) - pd.DateOffset(months=6)
    end = pd.to_datetime(max_d)
elif preset == "Últimos 12 meses":
    start = pd.to_datetime(max_d) - pd.DateOffset(months=12)
    end = pd.to_datetime(max_d)
else:
    start = pd.to_datetime(st.sidebar.date_input("Início", min_d))
    end = pd.to_datetime(st.sidebar.date_input("Fim", max_d))

mask = (df["month"] >= start) & (df["month"] <= end)
dff = df.loc[mask].copy()

# Visual controls
st.sidebar.header("Controles de gráfico")
mv_win = st.sidebar.number_input("Média móvel (meses)", min_value=1, value=3, step=1)
topn = st.sidebar.slider("Anotar Top-N picos", min_value=0, max_value=10, value=3, step=1)

# Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Overview",
    "Custo de Perda vs. Meta",
    "Simulador — No-Cut <7d",
    "Paradas por Código",
    "Metas Dinâmicas por Subgrupo"
])

# -----------------------------
# Tab 1 — Overview
# -----------------------------
with tab1:
    if dff.empty:
        st.warning("Período sem dados.")
    else:
        lead_time = dff["lead_time_mean"].mean()
        efetividade = dff["efetividade_media"].mean()
        perda_prem_r = dff["perda_prem_R"].sum()
        pct_prem = dff["pct_refugo_prem"].replace(0, np.nan).mean()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Lead time médio (dias)", f"{lead_time:.2f}")
        c2.metric("Efetividade média", f"{efetividade:.2f}x")
        c3.metric("Perda prematura (R$)", f"{perda_prem_r:,.0f}".replace(",", "."))
        c4.metric("% refugo por corte prematuro", f"{0 if np.isnan(pct_prem) else pct_prem:.1f}%")

        st.subheader("Série temporal — Lead time médio (dias)")
        fig1, ax1 = plt.subplots()
        ax1.plot(dff["month"], dff["lead_time_mean"], marker="o")
        ma_lt = rolling_series(dff["lead_time_mean"], mv_win)
        if ma_lt is not None and mv_win > 1:
            ax1.plot(dff["month"], ma_lt, linestyle="--")
        ax1.set_xlabel("Mês")
        ax1.set_ylabel("Dias")
        ax1.set_title("Lead time médio (dias) — com média móvel")
        date_axes(ax1)
        if topn > 0:
            annotate_peaks(ax1, dff["month"].values, dff["lead_time_mean"].values, topn=topn, fmt=lambda v: f"{v:.1f}")
        st.pyplot(fig1)

        st.subheader("Série temporal — % do refugo por corte prematuro")
        fig2, ax2 = plt.subplots()
        ax2.plot(dff["month"], dff["pct_refugo_prem"], marker="o")
        ma_pct = rolling_series(dff["pct_refugo_prem"], mv_win)
        if ma_pct is not None and mv_win > 1:
            ax2.plot(dff["month"], ma_pct, linestyle="--")
        ax2.set_xlabel("Mês")
        ax2.set_ylabel("%")
        ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:.1f}%"))
        ax2.set_title("% do refugo por corte prematuro — com média móvel")
        date_axes(ax2)
        if topn > 0:
            annotate_peaks(ax2, dff["month"].values, dff["pct_refugo_prem"].values, topn=topn, fmt=lambda v: f"{v:.1f}%")
        st.pyplot(fig2)

        st.subheader("Tabela — Base mensal filtrada")
        st.dataframe(dff)

# -----------------------------
# Tab 2 — Custo de Perda vs. Meta
# -----------------------------
with tab2:
    st.write("Defina a **meta mensal (R$)** para avaliar gap no agregado.")
    meta = st.number_input("Meta mensal (R$)", min_value=0, value=50000, step=5000)

    dff2 = dff.copy()
    dff2["meta"] = meta
    dff2["gap"] = dff2["perda_prem_R"] - dff2["meta"]

    c1, c2 = st.columns(2)
    c1.metric("Perda total no período (R$)", f"{dff2['perda_prem_R'].sum():,.0f}".replace(",", "."))
    c2.metric("Desvio total vs. meta (R$)", f"{dff2['gap'].sum():,.0f}".replace(",", "."))

    st.subheader("Perda por corte prematuro x meta — Mensal")
    fig3, ax3 = plt.subplots()
    ax3.plot(dff2["month"], dff2["perda_prem_R"], marker="o", label="Perda (R$)")
    ax3.plot(dff2["month"], dff2["meta"], linestyle="--", label="Meta (R$)")
    ax3.set_xlabel("Mês")
    ax3.set_ylabel("R$")
    ax3.yaxis.set_major_formatter(FuncFormatter(lambda x, pos: format_brl(x)))
    ax3.set_title("Perda prematura vs. meta")
    ax3.legend()
    date_axes(ax3)
    if topn > 0:
        annotate_peaks(ax3, dff2["month"].values, dff2["perda_prem_R"].values, topn=topn, fmt=lambda v: format_brl(v))
    st.pyplot(fig3)

    st.subheader("Tabela — Perda, Meta e Gap")
    show = dff2[["month","perda_prem_R","meta","gap"]].copy()
    show.columns = ["Mês", "Perda (R$)", "Meta (R$)", "Gap (R$)"]
    st.dataframe(show)

# -----------------------------
# Tab 3 — Simulador No-Cut <7d
# -----------------------------
with tab3:
    st.write("Assume efeito linear: aumentar compliance reduz proporcionalmente a perda prematura.")
    colA, colB = st.columns(2)
    compliance = colA.slider("Compliance em No-Cut <7d (%)", min_value=0, max_value=100, value=50, step=5)
    meta_alvo = colB.number_input("Meta mensal alvo (R$)", min_value=0, value=50000, step=5000)

    dff3 = dff.copy()
    factor = (100 - compliance) / 100.0
    dff3["perda_prem_R_simulada"] = dff3["perda_prem_R"] * factor

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Perda atual (R$)", f"{dff['perda_prem_R'].sum():,.0f}".replace(",", "."))
    col_b.metric("Perda simulada (R$)", f"{dff3['perda_prem_R_simulada'].sum():,.0f}".replace(",", "."))
    economia = dff["perda_prem_R"].sum() - dff3["perda_prem_R_simulada"].sum()
    col_c.metric("Economia estimada (R$)", f"{economia:,.0f}".replace(",", "."))

    st.subheader("Série — Perda atual vs. simulada (média móvel opcional)")
    fig4, ax4 = plt.subplots()
    ax4.plot(dff["month"], dff["perda_prem_R"], marker="o", label="Atual")
    ax4.plot(dff3["month"], dff3["perda_prem_R_simulada"], linestyle="--", label="Simulada")
    ma_atual = rolling_series(dff["perda_prem_R"], mv_win)
    ma_sim = rolling_series(dff3["perda_prem_R_simulada"], mv_win)
    if ma_atual is not None and mv_win > 1:
        ax4.plot(dff["month"], ma_atual, linestyle=":")
    if ma_sim is not None and mv_win > 1:
        ax4.plot(dff3["month"], ma_sim, linestyle=":")
    ax4.set_xlabel("Mês")
    ax4.set_ylabel("R$")
    ax4.set_title("Perda prematura — Atual vs. Simulada")
    ax4.legend()
    date_axes(ax4)
    st.pyplot(fig4)

# -----------------------------
# Tab 4 — Paradas por Código
# -----------------------------
with tab4:
    st.write("Upload de CSV com colunas: **data, codigo_parada, minutos, celula**.")
    up = st.file_uploader("Enviar CSV de Paradas", type=["csv"], key="paradas")
    if up is not None:
        dfp = pd.read_csv(up, parse_dates=["data"])
        msk = (dfp["data"] >= pd.to_datetime(start)) & (dfp["data"] <= pd.to_datetime(end))
        dfp = dfp.loc[msk].copy()

        st.subheader("Top 10 códigos de parada (min)")
        top = dfp.groupby("codigo_parada", as_index=False)["minutos"].sum().sort_values("minutos", ascending=False).head(10)
        st.dataframe(top)

        st.subheader("Série temporal — minutos totais de parada (por mês)")
        dfp["mes"] = dfp["data"].values.astype("datetime64[M]")
        serie = dfp.groupby("mes", as_index=False)["minutos"].sum()

        fig5, ax5 = plt.subplots()
        ax5.plot(serie["mes"], serie["minutos"], marker="o")
        ax5.set_xlabel("Mês")
        ax5.set_ylabel("Minutos de parada")
        ax5.set_title("Paradas — minutos por mês")
        date_axes(ax5)
        st.pyplot(fig5)

        st.subheader("Detalhamento por célula")
        detal = dfp.groupby(["celula","codigo_parada"], as_index=False)["minutos"].sum().sort_values(["celula","minutos"], ascending=[True, False])
        st.dataframe(detal)

        st.download_button(
            label="Baixar agregações de paradas (CSV)",
            data=detal.to_csv(index=False).encode("utf-8"),
            file_name="paradas_aggregado.csv",
            mime="text/csv",
        )
    else:
        st.info("Nenhum arquivo enviado. Exemplo de estrutura esperada:")
        exemplo = pd.DataFrame({
            "data": ["2025-09-01","2025-09-02"],
            "codigo_parada": ["FALTA_MP","MANUT_ELETRICA"],
            "minutos": [120, 45],
            "celula": ["Corte","Acabamento"]
        })
        st.dataframe(exemplo)

# -----------------------------
# Tab 5 — Metas Dinâmicas por Subgrupo
# -----------------------------
with tab5:
    st.write("Defina metas por **célula** ou **família** via tabela editável e acompanhe gaps e séries.")
    available = [c for c in ["celula","familia"] if c in dff.columns]
    if not available:
        st.info("A base atual não possui 'celula' ou 'familia'. Suba uma base com esses campos na barra lateral.")
    else:
        eixo = st.selectbox("Agrupar por", available)
        unicos = dff[[eixo]].dropna().drop_duplicates().reset_index(drop=True)
        if unicos.empty:
            st.warning("Não há valores no período selecionado para o agrupamento escolhido.")
        else:
            unicos["Meta (R$)"] = 30000
            metas_edit = st.data_editor(
                unicos,
                num_rows="dynamic",
                use_container_width=True,
                hide_index=True,
                column_config={
                    eixo: st.column_config.TextColumn(eixo.capitalize(), width="medium"),
                    "Meta (R$)": st.column_config.NumberColumn("Meta (R$)", min_value=0, step=1000, width="small"),
                },
            )
            metas_map = dict(zip(metas_edit[eixo], metas_edit["Meta (R$)"]))

            g = dff.groupby([eixo, "month"], as_index=False)["perda_prem_R"].sum()
            g["meta"] = g[eixo].map(metas_map).fillna(0)
            g["gap"] = g["perda_prem_R"] - g["meta"]

            st.subheader("Ranking — maior desvio (gap) no período")
            rank = g.groupby(eixo, as_index=False)["gap"].sum().sort_values("gap", ascending=False)
            rank.columns = [eixo, "Gap total (R$)"]
            st.dataframe(rank, use_container_width=True)

            st.subheader("Série — Perda por subgrupo (linha) e meta (tracejado)")
            fig6, ax6 = plt.subplots()
            for key, chunk in g.groupby(eixo):
                ax6.plot(chunk["month"], chunk["perda_prem_R"], label=str(key))
            for key, chunk in g.groupby(eixo):
                ax6.plot(chunk["month"], chunk["meta"], linestyle="--")
            ax6.set_xlabel("Mês")
            ax6.set_ylabel("R$")
            ax6.set_title("Perda prematura por subgrupo vs metas")
            ax6.legend()
            date_axes(ax6)
            st.pyplot(fig6)

            st.subheader("Tabela — Subgrupo x Mês")
            show = g[[eixo, "month", "perda_prem_R", "meta", "gap"]].copy()
            show.columns = [eixo.capitalize(), "Mês", "Perda (R$)", "Meta (R$)", "Gap (R$)"]
            st.dataframe(show, use_container_width=True)
