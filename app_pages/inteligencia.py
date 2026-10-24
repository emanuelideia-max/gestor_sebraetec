from datetime import date, timedelta

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import data, insights
from core.ui import marca, md, cores, brl, kpi_w, label_limit, num, filtros

AZUL, LARANJA, _ = marca()

df = filtros(data.consultorias_view())
if df.empty:
    st.info("Nenhuma consultoria para os filtros escolhidos.", icon=":material/filter_alt:")
    st.stop()

r = insights.risco(df)
ativas = r[~r["finalizada"]]
prev = insights.previsao_pagamentos(df)
hoje = pd.Timestamp(date.today())
a_liberar_30 = ativas[ativas["data_fim"].between(hoje, hoje + timedelta(days=30))]["valor_total"].sum()
hhi, maior, fatia = insights.concentracao(df)

# ---------------------------------------------------------------- indicadores
with st.container(horizontal=True):
    st.metric("Risco médio", f"{ativas['risco'].mean():.0f}/100" if len(ativas) else "—", border=True,
              width=kpi_w(), help="Média da nota de risco das consultorias ativas")
    st.metric("Em risco alto", f"{int((ativas['nivel'] == 'Alto').sum())}", border=True, width=kpi_w())
    st.metric("Prazo consumido", f"{ativas['prazo_consumido'].mean():.0%}" if ativas["prazo_consumido"].notna().any()
              else "—", border=True, width=kpi_w(), help="Média do tempo já decorrido entre início e fim da proposta")
    st.metric("A liberar em 30 dias", brl(a_liberar_30), border=True, width=kpi_w(),
              help="Valor das consultorias com fim previsto nos próximos 30 dias")
    st.metric("Concentração (HHI)", num(hhi), border=True, width=kpi_w(),
              help="Índice Herfindahl do valor por fornecedor: acima de 2.500 = concentração alta")

# ---------------------------------------------------------------- radar
with st.container(border=True):
    st.subheader(":material/radar: Radar", anchor=False)
    for icone, cor, texto in insights.alertas(df):
        st.markdown(f":{cor}[{icone}] {md(texto)}")

# ---------------------------------------------------------------- risco
col1, col2 = st.columns([3, 2])
with col1:
    with st.container(border=True, height="stretch"):
        st.subheader("Matriz de risco", anchor=False)
        st.caption("Tempo consumido do prazo × avanço nas 21 etapas. Quanto mais à direita e embaixo, maior o risco.")
        m = ativas.dropna(subset=["prazo_consumido"])
        if m.empty:
            st.caption("Cadastre datas de início e fim para ver a matriz.")
        else:
            fundo = alt.Chart(pd.DataFrame({"x": [0.75], "x2": [1.5], "y": [0], "y2": [0.8]})).mark_rect(
                color="#D9534F", opacity=0.07).encode(x="x:Q", x2="x2:Q", y="y:Q", y2="y2:Q")
            pontos = alt.Chart(m).mark_circle(opacity=0.85, stroke=cores()["borda"], strokeWidth=1).encode(
                x=alt.X("prazo_consumido:Q", title="Prazo consumido", axis=alt.Axis(format="%"),
                        scale=alt.Scale(domain=[0, max(1.1, float(m["prazo_consumido"].max()) + 0.05)])),
                y=alt.Y("progresso:Q", title="Avanço nas etapas", axis=alt.Axis(format="%"),
                        scale=alt.Scale(domain=[0, 1])),
                size=alt.Size("valor_total:Q", legend=None, scale=alt.Scale(range=[80, 900])),
                color=alt.Color("nivel:N", title="Risco", scale=alt.Scale(
                    domain=insights.NIVEIS, range=["#D9534F", LARANJA, "#2BA394"]),
                    legend=alt.Legend(orient="bottom")),
                tooltip=[alt.Tooltip("cliente:N", title="Cliente"), alt.Tooltip("fornecedor:N", title="Fornecedor"),
                         alt.Tooltip("prazo_consumido:Q", title="Prazo consumido", format=".0%"),
                         alt.Tooltip("status:N", title="Etapa"), alt.Tooltip("risco:Q", title="Risco"),
                         alt.Tooltip("motivos:N", title="Motivos")],
            )
            st.altair_chart((fundo + pontos).properties(height=340), width="stretch",
                            alt="Matriz de risco: prazo consumido por avanço nas etapas")
with col2:
    with st.container(border=True, height="stretch"):
        st.subheader("Ranking de risco", anchor=False)
        st.dataframe(
            ativas.sort_values("risco", ascending=False),
            hide_index=True,
            column_order=["cliente", "risco", "motivos"],
            column_config={
                "cliente": "Cliente",
                "risco": st.column_config.ProgressColumn("Risco", min_value=0, max_value=100, format="%d"),
                "motivos": st.column_config.TextColumn("Motivos", width="large"),
            },
            height=340,
            alt="Consultorias ordenadas pela nota de risco",
        )

# ---------------------------------------------------------------- previsão financeira
with st.container(border=True):
    st.subheader("Previsão de pagamentos", anchor=False)
    st.caption("Valor a liberar por mês, pela data de fim prevista das consultorias não finalizadas.")
    if prev.empty:
        st.caption("Sem consultorias ativas com data de fim.")
    else:
        longo = prev.melt("mes", ["subsidio", "contrapartida"], var_name="tipo", value_name="valor")
        longo["tipo"] = longo["tipo"].map({"subsidio": "Subsídio Sebrae", "contrapartida": "Contrapartida"})
        prev["acumulado"] = prev["valor_total"].cumsum()
        prev["rotulo"] = prev["mes"].dt.strftime("%m/%Y")
        longo["rotulo"] = longo["mes"].dt.strftime("%m/%Y")
        ordem = list(prev["rotulo"])
        barras = alt.Chart(longo).mark_bar(size=46, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
            x=alt.X("rotulo:O", title=None, sort=ordem, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("valor:Q", title="R$", stack=True),
            color=alt.Color("tipo:N", title=None, legend=alt.Legend(orient="bottom"),
                            scale=alt.Scale(domain=["Subsídio Sebrae", "Contrapartida"], range=[AZUL, LARANJA])),
            tooltip=[alt.Tooltip("rotulo:O", title="Mês"), "tipo",
                     alt.Tooltip("valor:Q", format=",.2f", title="R$")],
        )
        linha = alt.Chart(prev).mark_line(point=True, color=cores()["suave"], strokeDash=[4, 3]).encode(
            x=alt.X("rotulo:O", sort=ordem), y="acumulado:Q",
            tooltip=[alt.Tooltip("acumulado:Q", title="Acumulado (R$)", format=",.2f")],
        )
        st.altair_chart((barras + linha).properties(height=280), width="stretch",
                        alt="Previsão mensal de pagamentos com linha de valor acumulado")

# ---------------------------------------------------------------- fluxo e composição
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True, height="stretch"):
        st.subheader("Fluxo de recursos", anchor=False)
        st.caption("Área → fornecedor → cidade, pela largura do valor contratado.")
        nos = list(dict.fromkeys(list(df["area"]) + list(df["fornecedor"]) + list(df["cidade"])))
        idx = {n: i for i, n in enumerate(nos)}
        l1 = df.groupby(["area", "fornecedor"])["valor_total"].sum().reset_index()
        l2 = df.groupby(["fornecedor", "cidade"])["valor_total"].sum().reset_index()
        fonte = [idx[a] for a in l1["area"]] + [idx[f] for f in l2["fornecedor"]]
        alvo = [idx[f] for f in l1["fornecedor"]] + [idx[c] for c in l2["cidade"]]
        valores = list(l1["valor_total"]) + list(l2["valor_total"])
        cores_nos = ([AZUL] * df["area"].nunique() + [LARANJA] * df["fornecedor"].nunique()
                 + ["#2BA394"] * df["cidade"].nunique())
        sk = go.Figure(go.Sankey(
            node=dict(label=nos, pad=14, thickness=12, color=cores_nos[:len(nos)], line=dict(width=0)),
            link=dict(source=fonte, target=alvo, value=valores, color="rgba(0,94,184,0.15)",
                      hovertemplate="%{source.label} → %{target.label}<br>R$ %{value:,.2f}<extra></extra>"),
        ))
        sk.update_layout(height=380, margin=dict(l=4, r=4, t=4, b=4), separators=",.", font_size=11)
        st.plotly_chart(sk, config={"displayModeBar": False}, alt="Diagrama de fluxo do valor por área, fornecedor e cidade")
with col2:
    with st.container(border=True, height="stretch"):
        st.subheader("Composição do portfólio", anchor=False)
        st.caption("Área → solução → fornecedor. Clique num bloco para aproximar.")
        tm = df.groupby(["area", "ficha_tecnica", "fornecedor"])["valor_total"].sum().reset_index()
        ids, labels, parents, values = [], [], [], []
        for nivel in (["area"], ["area", "ficha_tecnica"], ["area", "ficha_tecnica", "fornecedor"]):
            g = tm.groupby(nivel)["valor_total"].sum().reset_index()
            for _, x in g.iterrows():
                ids.append(" / ".join(x[c] for c in nivel))
                labels.append(x[nivel[-1]])
                parents.append(" / ".join(x[c] for c in nivel[:-1]))
                values.append(x["valor_total"])
        tr = go.Figure(go.Treemap(ids=ids, labels=labels, parents=parents, values=values, branchvalues="total",
                                  marker=dict(colors=values, colorscale=[[0, "#CFE2F6"], [1, AZUL]], line=dict(width=1)),
                                  hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percentRoot:.0%} do total<extra></extra>",
                                  texttemplate="%{label}<br>%{percentRoot:.0%}"))
        tr.update_layout(height=380, margin=dict(l=4, r=4, t=4, b=4), separators=",.")
        st.plotly_chart(tr, config={"displayModeBar": False}, alt="Treemap do valor por área, solução e fornecedor")

# ---------------------------------------------------------------- benchmark e scorecard
b = insights.benchmark_valor_hora(df)
with st.container(border=True):
    st.subheader("Benchmark de R$/hora por solução", anchor=False)
    st.caption("Cada ponto é uma consultoria; a linha é a média da solução. Pontos acima indicam preço/hora maior.")
    pontos = alt.Chart(b).mark_circle(size=140, opacity=0.85).encode(
        y=alt.Y("ficha_tecnica:N", title=None, axis=alt.Axis(labelLimit=label_limit())),
        x=alt.X("valor_hora:Q", title="R$/hora", scale=alt.Scale(zero=False, padding=20)),
        color=alt.Color("fornecedor:N", title=None, legend=alt.Legend(orient="bottom")),
        tooltip=["cliente", "fornecedor", alt.Tooltip("valor_hora:Q", title="R$/h", format=",.2f"),
                 alt.Tooltip("desvio:Q", title="vs. média", format="+.0%")],
    )
    media = alt.Chart(b.drop_duplicates("ficha_tecnica")).mark_tick(color=cores()["texto"], thickness=2, size=26).encode(
        y="ficha_tecnica:N", x="media_solucao:Q",
        tooltip=[alt.Tooltip("media_solucao:Q", title="Média R$/h", format=",.2f")])
    st.altair_chart((pontos + media).properties(height=alt.Step(64)),
                    width="stretch", alt="Valor por hora de cada consultoria comparado à média da solução")

with st.container(border=True):
    st.subheader("Scorecard de fornecedores", anchor=False)
    total = df["valor_total"].sum() or 1
    sc = r.groupby("fornecedor").agg(
        consultorias=("id", "count"),
        valor_total=("valor_total", "sum"),
        valor_hora=("valor_hora", "mean"),
        risco=("risco", "mean"),
        cidades=("cidade", "nunique"),
        no_prazo=("dias_para_fim", lambda s: (s.dropna() >= 0).mean() if s.notna().any() else None),
    ).reset_index()
    sc = sc.merge(
        b.groupby("fornecedor")["desvio"].mean().rename("desvio").reset_index(), on="fornecedor")
    sc["participacao"] = sc["valor_total"] / total
    st.dataframe(
        sc.sort_values("valor_total", ascending=False),
        hide_index=True,
        column_order=["fornecedor", "consultorias", "participacao", "valor_total", "valor_hora", "desvio",
                      "cidades", "no_prazo", "risco"],
        column_config={
            "fornecedor": "Fornecedor",
            "consultorias": "Qtd.",
            "participacao": st.column_config.ProgressColumn("Participação", min_value=0, max_value=1, format="percent"),
            "valor_total": st.column_config.NumberColumn("Valor (R$)", format="localized"),
            "valor_hora": st.column_config.NumberColumn("R$/h médio", format="%.2f"),
            "desvio": st.column_config.NumberColumn("R$/h vs. média", format="percent",
                                                    help="Diferença para a média das mesmas soluções"),
            "cidades": "Cidades",
            "no_prazo": st.column_config.ProgressColumn("Dentro do prazo", min_value=0, max_value=1, format="percent"),
            "risco": st.column_config.ProgressColumn("Risco médio", min_value=0, max_value=100, format="%.0f"),
        },
        alt="Scorecard comparativo de fornecedores",
    )
