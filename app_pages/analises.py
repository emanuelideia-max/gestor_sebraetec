import altair as alt
import pandas as pd
import streamlit as st

from core import data
from core.ui import marca, kpi_w, METRICAS, RESUMO_COLUNAS, barras, brl, num, resumo_por, filtros

AZUL, LARANJA, _ = marca()

df = filtros(data.consultorias_view())

if df.empty:
    st.info("Nenhuma consultoria para os filtros escolhidos.", icon=":material/filter_alt:")
    st.stop()

horas = df["carga_horaria"].sum()
with st.container(horizontal=True):
    st.metric("Consultorias", f"{len(df)}", border=True, width=kpi_w())
    st.metric("Valor total", brl(df["valor_total"].sum()), border=True, width=kpi_w())
    st.metric("Média de horas", f"{num(df['carga_horaria'].mean(), 1)} h", border=True, width=kpi_w())
    st.metric("Valor médio", brl(df["valor_total"].mean()), border=True, width=kpi_w())
    st.metric("R$/hora médio", brl(df["valor_total"].sum() / horas if horas else 0, 2), border=True, width=kpi_w())

visao = st.segmented_control(
    "Visão",
    ["Por cidade", "Por fornecedor", "Por cliente", "Financeiro"],
    default="Por cidade",
    key="analise_visao",
    label_visibility="collapsed",
) or "Por cidade"


def ranking(col: str, rotulo: str, chave: str) -> pd.DataFrame:
    resumo = resumo_por(df, col)
    metrica = st.pills("Métrica", list(METRICAS), default="Valor total", key=chave) or "Valor total"
    campo, fmt = METRICAS[metrica]
    with st.container(border=True):
        st.subheader(f"{metrica} {rotulo}", anchor=False)
        st.altair_chart(
            barras(resumo, col, campo, metrica, fmt),
            width="stretch",
            alt=f"{metrica} {rotulo}",
        )
    return resumo


if visao == "Por cidade":
    resumo = ranking("cidade", "por cidade", "m_cidade")
    with st.container(border=True):
        st.subheader("Tabela por cidade", anchor=False)
        st.dataframe(resumo, hide_index=True, column_config={**RESUMO_COLUNAS, "cidade": "Cidade"},
                     alt="Indicadores por cidade")

elif visao == "Por fornecedor":
    resumo = ranking("fornecedor", "por fornecedor", "m_forn")
    extra = df.groupby("fornecedor").agg(
        cidades=("cidade", "nunique"),
        ativas=("finalizada", lambda s: int((~s).sum())),
        etapa_media=("status_id", "mean"),
    ).reset_index()
    resumo = resumo.merge(extra, on="fornecedor")
    with st.container(border=True):
        st.subheader("Tabela por fornecedor", anchor=False)
        st.dataframe(
            resumo,
            hide_index=True,
            column_order=["fornecedor", "consultorias", "ativas", "cidades", "valor_total", "valor_medio",
                          "horas_media", "valor_hora_medio", "etapa_media"],
            column_config={
                **RESUMO_COLUNAS,
                "fornecedor": "Fornecedor",
                "ativas": "Ativas",
                "cidades": "Cidades",
                "etapa_media": st.column_config.ProgressColumn(
                    "Avanço médio", min_value=1, max_value=data.ETAPA_FINAL, format="%.1f / 21"
                ),
            },
            alt="Indicadores por fornecedor",
        )

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True, height="stretch"):
            st.subheader("Participação no valor", anchor=False)
            pizza = (
                alt.Chart(resumo)
                .mark_arc(innerRadius=60)
                .encode(
                    theta="valor_total:Q",
                    color=alt.Color("fornecedor:N", title=None, legend=alt.Legend(orient="bottom", columns=2)),
                    tooltip=[alt.Tooltip("fornecedor:N", title="Fornecedor"),
                             alt.Tooltip("valor_total:Q", title="Valor", format=",.2f")],
                )
                .properties(height=300)
            )
            st.altair_chart(pizza, width="stretch", alt="Participação de cada fornecedor no valor total")
    with col2:
        with st.container(border=True, height="stretch"):
            st.subheader("Cidades atendidas por fornecedor", anchor=False)
            mapa_fc = df.groupby(["fornecedor", "cidade"]).size().rename("qtd").reset_index()
            heat = (
                alt.Chart(mapa_fc)
                .mark_rect(cornerRadius=3)
                .encode(
                    x=alt.X("cidade:N", title=None, axis=alt.Axis(labelAngle=-35)),
                    y=alt.Y("fornecedor:N", title=None, axis=alt.Axis(labelLimit=200)),
                    color=alt.Color("qtd:Q", scale=alt.Scale(range=["#CFE2F6", AZUL]), legend=None),
                    tooltip=["fornecedor", "cidade", alt.Tooltip("qtd:Q", title="Consultorias")],
                )
                .properties(height=300)
            )
            st.altair_chart(heat, width="stretch", alt="Consultorias por fornecedor e cidade")

    with st.container(border=True):
        st.subheader("Tempo médio em cada etapa (dias)", anchor=False)
        tempos = data.tempo_por_etapa()
        tempos = tempos[tempos["consultoria_id"].isin(df["id"])]
        if tempos["status_id"].nunique() < 2:
            st.caption(
                "Este gráfico aparece quando houver histórico de mudanças de etapa. "
                "Cada avanço feito na tela **Consultorias** fica registrado com a data."
            )
        else:
            t = tempos.merge(df[["id", "fornecedor"]], left_on="consultoria_id", right_on="id")
            t = t.groupby(["fornecedor", "status_id"])["dias"].mean().reset_index()
            t["etapa"] = t["status_id"].astype(int).map(lambda i: f"{i:02d}. {data.nome_curto_etapa(data.nomes_etapas()[i - 1])}")
            chart = (
                alt.Chart(t)
                .mark_bar()
                .encode(
                    y=alt.Y("etapa:N", title=None, axis=alt.Axis(labelLimit=300)),
                    x=alt.X("dias:Q", title="Dias (média)"),
                    color=alt.Color("fornecedor:N", title=None, legend=alt.Legend(orient="bottom")),
                    yOffset="fornecedor:N",
                    tooltip=["fornecedor", "etapa", alt.Tooltip("dias:Q", format=".1f")],
                )
            )
            st.altair_chart(chart, width="stretch", alt="Dias médios por etapa e fornecedor")

elif visao == "Por cliente":
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True, height="stretch"):
            st.subheader("Clientes por categoria", anchor=False)
            cat = resumo_por(df, "categoria")
            st.altair_chart(barras(cat, "categoria", "consultorias", "Consultorias", ",.0f"), width="stretch",
                            alt="Consultorias por categoria de cliente")
    with col2:
        with st.container(border=True, height="stretch"):
            st.subheader("Soluções contratadas", anchor=False)
            sol = resumo_por(df, "ficha_tecnica")
            st.altair_chart(barras(sol, "ficha_tecnica", "consultorias", "Consultorias", ",.0f", cor=LARANJA),
                            width="stretch", alt="Consultorias por solução (ficha técnica)")
    with st.container(border=True):
        st.subheader("Clientes", anchor=False)
        cli = df.groupby(["cliente", "categoria", "cidade"]).agg(
            consultorias=("id", "count"),
            valor_total=("valor_total", "sum"),
            contrapartida=("contrapartida", "sum"),
            horas_total=("carga_horaria", "sum"),
            etapa=("etapa", "last"),
        ).reset_index().sort_values("valor_total", ascending=False)
        st.dataframe(
            cli,
            hide_index=True,
            column_config={**RESUMO_COLUNAS, "cliente": "Cliente", "categoria": "Categoria",
                           "cidade": "Cidade", "etapa": "Status atual"},
            alt="Clientes com valores e status",
        )

else:  # Financeiro
    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True, height="stretch"):
            st.subheader("Subsídio x contrapartida por fornecedor", anchor=False)
            fin = df.groupby("fornecedor")[["subsidio", "contrapartida"]].sum().reset_index()
            fin = fin.melt("fornecedor", var_name="tipo", value_name="valor")
            fin["tipo"] = fin["tipo"].map({"subsidio": "Subsídio Sebrae", "contrapartida": "Contrapartida"})
            chart = (
                alt.Chart(fin)
                .mark_bar()
                .encode(
                    y=alt.Y("fornecedor:N", title=None, axis=alt.Axis(labelLimit=220)),
                    x=alt.X("valor:Q", title="R$", stack=True),
                    color=alt.Color("tipo:N", title=None, scale=alt.Scale(domain=["Subsídio Sebrae", "Contrapartida"], range=[AZUL, LARANJA]),
                                    legend=alt.Legend(orient="bottom")),
                    tooltip=["fornecedor", "tipo", alt.Tooltip("valor:Q", format=",.2f")],
                )
            )
            st.altair_chart(chart, width="stretch", alt="Subsídio e contrapartida por fornecedor")
    with col2:
        with st.container(border=True, height="stretch"):
            st.subheader("Valor por área", anchor=False)
            area = resumo_por(df, "area")
            st.altair_chart(barras(area, "area", "valor_total", "Valor total"), width="stretch",
                            alt="Valor total por área")
    with st.container(border=True):
        st.subheader("Valor contratado por mês de processamento", anchor=False)
        mensal = df.dropna(subset=["mes"]).groupby("mes")[["subsidio", "contrapartida"]].sum().reset_index()
        mensal = mensal.melt("mes", var_name="tipo", value_name="valor")
        mensal["tipo"] = mensal["tipo"].map({"subsidio": "Subsídio Sebrae", "contrapartida": "Contrapartida"})
        chart = (
            alt.Chart(mensal)
            .mark_bar(size=40)
            .encode(
                x=alt.X("yearmonth(mes):T", title=None, axis=alt.Axis(format="%m/%Y")),
                y=alt.Y("valor:Q", title="R$", stack=True),
                color=alt.Color("tipo:N", title=None, scale=alt.Scale(domain=["Subsídio Sebrae", "Contrapartida"], range=[AZUL, LARANJA]),
                                legend=alt.Legend(orient="bottom")),
                tooltip=[alt.Tooltip("yearmonth(mes):T", title="Mês", format="%m/%Y"), "tipo",
                         alt.Tooltip("valor:Q", format=",.2f")],
            )
            .properties(height=280)
        )
        st.altair_chart(chart, width="stretch", alt="Valor contratado por mês")

st.download_button(
    "Baixar dados filtrados (CSV)",
    df.drop(columns=["mes"]).to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig"),
    file_name="consultorias_filtradas.csv",
    mime="text/csv",
    icon=":material/download:",
)
