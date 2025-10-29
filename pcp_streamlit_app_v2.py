
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st

st.set_page_config(page_title="PCP – Dashboard Dinâmico", layout="wide")
st.title("PCP – Dashboard Dinâmico")
st.caption("Visão executiva orientada a resultado")

# Load base
df = pd.read_csv("pcp_data.csv", parse_dates=["month"])

# Sidebar filters
st.sidebar.header("Filtros")
start = st.sidebar.date_input("Início", df["month"].min().date())
end = st.sidebar.date_input("Fim", df["month"].max().date())
mask = (df["month"] >= pd.to_datetime(start)) & (df["month"] <= pd.to_datetime(end))
dff = df.loc[mask].copy()

# Tabs
tab1, tab2, tab3, tab4 = st.tabs([
    "Overview",
    "Custo de Perda vs. Meta",
    "Simulador — No-Cut <7d",
    "Paradas por Código"
])

# -----------------------------
# Tab 1 — Overview
# -----------------------------
with tab1:
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
    st.write("Defina a **meta mensal de perda por corte prematuro (R$)** e avalie o gap por mês.")
    meta = st.number_input("Meta mensal (R$)", min_value=0, value=50000, step=5000)

    # Agregação mensal within selection
    dff2 = dff.copy()
    dff2["meta"] = meta
    dff2["gap"] = dff2["perda_prem_R"] - dff2["meta"]

    c1, c2 = st.columns(2)
    c1.metric("Perda total no período (R$)", f"{dff2['perda_prem_R'].sum():,.0f}".replace(",", "."))
    c2.metric("Desvio total vs. meta (R$)", f"{dff2['gap'].sum():,.0f}".replace(",", "."))

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
    st.dataframe(dff2[["month","perda_prem_R","meta","gap"]])

# -----------------------------
# Tab 3 — Simulador No-Cut <7d
# -----------------------------
with tab3:
    st.write("""
    Modelo de primeira ordem: assumimos que **compliance** em "no-cut <7d" reduz linearmente a
    perda prematura do período. Use o slider para simular a aderência.
    """)
    compliance = st.slider("Compliance em No-Cut <7d (%)", min_value=0, max_value=100, value=50, step=5)

    dff3 = dff.copy()
    factor = (100 - compliance) / 100.0  # 100% compliance -> 0 de perda
    dff3["perda_prem_R_simulada"] = dff3["perda_prem_R"] * factor

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Perda atual (R$)", f"{dff['perda_prem_R'].sum():,.0f}".replace(",", "."))
    col_b.metric("Perda simulada (R$)", f"{dff3['perda_prem_R_simulada'].sum():,.0f}".replace(",", "."))
    economia = dff["perda_prem_R"].sum() - dff3["perda_prem_R_simulada"].sum()
    col_c.metric("Economia estimada (R$)", f"{economia:,.0f}".replace(",", "."))

    st.subheader("Série — Perda atual vs. simulada")
    fig4, ax4 = plt.subplots()
    ax4.plot(dff["month"], dff["perda_prem_R"], label="Atual")
    ax4.plot(dff3["month"], dff3["perda_prem_R_simulada"], label="Simulada")
    ax4.set_xlabel("Mês")
    ax4.set_ylabel("R$")
    ax4.set_title("Perda prematura — Atual vs. Simulada")
    ax4.legend()
    st.pyplot(fig4)

# -----------------------------
# Tab 4 — Paradas por Código (upload opcional)
# -----------------------------
with tab4:
    st.write("Faça upload de um CSV de paradas com colunas: **data, codigo_parada, minutos, celula**.")
    up = st.file_uploader("Enviar CSV de Paradas", type=["csv"])
    if up is not None:
        dfp = pd.read_csv(up, parse_dates=["data"])
        # período: alinhar com filtros da página
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
