
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
from datetime import timedelta

st.set_page_config(page_title="PCP – Dashboard Dinâmico v3", layout="wide")
st.title("PCP – Dashboard Dinâmico v3")
st.caption("Layer executivo + simuladores operacionais — pronto para tomada de decisão.")

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

def pct(x, dec=1):
    return f"{x:.{dec}f}%"

def load_base():
    # Upload opcional de base oficial
    up = st.sidebar.file_uploader("Substituir base padrão (CSV com colunas do template)", type=["csv"])
    if up is not None:
        df = pd.read_csv(up, parse_dates=["month"])
        st.sidebar.success("Base oficial carregada.")
    else:
        df = pd.read_csv("pcp_data.csv", parse_dates=["month"])
    return df

# -----------------------------
# Data
# -----------------------------
df = load_base()
df = df.sort_values("month").reset_index(drop=True)

# Presets de período
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
    start = st.sidebar.date_input("Início", min_d)
    end = st.sidebar.date_input("Fim", max_d)

mask = (df["month"] >= pd.to_datetime(start)) & (df["month"] <= pd.to_datetime(end))
dff = df.loc[mask].copy()

# Período anterior para delta
window_days = (pd.to_datetime(end) - pd.to_datetime(start)).days + 1
prev_start = pd.to_datetime(start) - pd.to_datetime(window_days, unit="D")
prev_end = pd.to_datetime(start) - pd.to_datetime(1, unit="D")

mask_prev = (df["month"] >= prev_start) & (df["month"] <= prev_end)
dfp = df.loc[mask_prev].copy()

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Overview",
    "Custo de Perda vs. Meta",
    "Simulador — No-Cut <7d",
    "Paradas por Código",
    "Metas por Célula/Família",
    "Qualidade de Dados"
])

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

        # KPIs período anterior (para delta)
        if not dfp.empty:
            lead_time_p = dfp["lead_time_mean"].mean()
            efetividade_p = dfp["efetividade_media"].mean()
            perda_prem_r_p = dfp["perda_prem_R"].sum()
            pct_prem_p = dfp["pct_refugo_prem"].replace(0, np.nan).mean()
        else:
            lead_time_p = efetividade_p = perda_prem_r_p = pct_prem_p = np.nan

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

        st.download_button(
            label="Baixar CSV filtrado",
            data=dff.to_csv(index=False).encode("utf-8"),
            file_name="pcp_data_filtrado.csv",
            mime="text/csv",
        )

# -----------------------------
# Tab 2 — Custo de Perda vs. Meta
# -----------------------------
with tab2:
    st.write("Defina a **meta mensal de perda por corte prematuro (R$)** e avalie o gap por mês, além do total do período.")
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
    st.write("""
    Modelo de primeira ordem: assumimos que **compliance** em "no-cut <7d" reduz linearmente a
    perda prematura do período. Ajuste a aderência e/ou a meta desejada para estimar o breakeven.
    """)
    colA, colB = st.columns(2)
    compliance = colA.slider("Compliance em No-Cut <7d (%)", min_value=0, max_value=100, value=50, step=5)
    meta_alvo = colB.number_input("Meta mensal alvo (R$)", min_value=0, value=50000, step=5000)

    dff3 = dff.copy()
    factor = (100 - compliance) / 100.0  # 100% compliance -> 0 de perda
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

    # Breakeven: qual compliance faz a média mensal simulada ficar <= meta_alvo?
    if not dff.empty:
        media_atual = dff["perda_prem_R"].mean()
        if media_atual == 0:
            st.info("Perda média atual é zero. Nenhum esforço adicional necessário para bater a meta.")
        else:
            # meta >= media_atual * (1 - comp/100)  -> comp >= 100 * (1 - meta/media_atual)
            comp_needed = 100 * (1 - (meta_alvo / media_atual)) if media_atual > 0 else 0
            comp_needed = max(0, min(100, comp_needed))
            st.metric("Compliance necessário (breakeven) para bater a meta", f"{comp_needed:.1f}%")

# -----------------------------
# Tab 4 — Paradas por Código (upload opcional)
# -----------------------------
with tab4:
    st.write("Upload de CSV com colunas: **data, codigo_parada, minutos, celula**. O período aplicado é o mesmo dos filtros laterais.")
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
        ax5.plot(serie["mes"], serie["minutos"])
        ax5.set_xlabel("Mês")
        ax5.set_ylabel("Minutos de parada")
        ax5.set_title("Paradas — minutos por mês")
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
# Tab 5 — Metas por Célula/Família (opcional)
# -----------------------------
with tab5:
    st.write("Se sua base conter colunas **celula** e/ou **familia**, você pode comparar metas e perdas por subgrupos.")
    if ("celula" in df.columns) or ("familia" in df.columns):
        eixo = st.selectbox("Agrupar por", [c for c in ["celula","familia"] if c in df.columns])
        meta_sub = st.number_input("Meta mensal por subgrupo (R$)", min_value=0, value=30000, step=5000)

        agg_cols = ["perda_prem_R"]
        cols = [eixo, "month"] + [c for c in agg_cols if c in df.columns]
        g = dff[cols].groupby([eixo, "month"], as_index=False)["perda_prem_R"].sum()
        g["meta"] = meta_sub
        g["gap"] = g["perda_prem_R"] - g["meta"]

        st.subheader("Tabela por subgrupo")
        st.dataframe(g)

        st.subheader("Série — Perda por subgrupo (somatório mensal)")
        # plot multiple lines: one axis, lines per subgroup
        fig6, ax6 = plt.subplots()
        for key, chunk in g.groupby(eixo):
            ax6.plot(chunk["month"], chunk["perda_prem_R"], label=str(key))
        ax6.set_xlabel("Mês")
        ax6.set_ylabel("R$")
        ax6.set_title("Perda prematura por subgrupo")
        ax6.legend()
        st.pyplot(fig6)
    else:
        st.info("A base atual não possui colunas 'celula' ou 'familia'. Você pode subir uma base oficial com esses campos na barra lateral.")

# -----------------------------
# Tab 6 — Qualidade de Dados
# -----------------------------
with tab6:
    st.write("Higiene de dados é margem no caixa. Validamos NaNs, zeros suspeitos e negativos nos campos críticos.")
    campos = ["lead_time_mean","efetividade_media","perda_total_m3","perda_prem_m3","perda_prem_R","pct_refugo_prem"]
    checks = []
    for c in campos:
        if c in dff.columns:
            na = dff[c].isna().sum()
            neg = (dff[c] < 0).sum() if dff[c].dtype != "O" else 0
            zeros = (dff[c] == 0).sum() if dff[c].dtype != "O" else 0
            checks.append({"campo": c, "NaN": int(na), "Negativos": int(neg), "Zeros": int(zeros)})
    if checks:
        st.subheader("Score de qualidade — período filtrado")
        st.dataframe(pd.DataFrame(checks))
    else:
        st.info("Nenhum campo avaliado disponível na base atual.")
