from datetime import date, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from core import config_app, data
from core.ui import marca, cores, kpi_w, brl, data_br, is_phone, label_limit, num

AZUL, LARANJA, AZUL_CLARO = marca()

df = data.consultorias_view()

if df.empty:
    st.info(
        "Nenhuma consultoria cadastrada ainda. Importe a planilha em **Cadastros e importação** "
        "ou cadastre a primeira em **Consultorias**.",
        icon=":material/upload_file:",
    )
    st.stop()

hoje = pd.Timestamp(date.today())
ativas = df[~df["finalizada"]]

cfg = config_app.atual()  # limites dos alertas: tela Configurações
janela, parada = int(cfg["alerta_prazo_dias"]), int(cfg["alerta_parada_dias"])

vencendo = ativas[ativas["dias_para_fim"].between(-3650, janela)]
paradas = ativas[(ativas["dias_na_etapa"] >= parada) & (ativas["status_id"] != 16)]
com_gestor = ativas[ativas["responsavel"].fillna("").str.contains("Gestor")]

# ---------------------------------------------------------------- KPIs
horas = df["carga_horaria"].sum()
with st.container(horizontal=True):
    st.metric("Ativas", f"{len(ativas)}", border=True, width=kpi_w(), help=f"{len(df)} no total")
    st.metric("Valor contratado", brl(df["valor_total"].sum()), border=True, width=kpi_w())
    st.metric("Subsídio Sebrae", brl(df["subsidio"].sum()), border=True, width=kpi_w())
    st.metric("Horas contratadas", f"{num(horas)} h", border=True, width=kpi_w())
    st.metric("R$/hora médio", brl(df["valor_total"].sum() / horas if horas else 0, 2), border=True, width=kpi_w())
    st.metric(f"Fim em até {janela} dias", f"{len(vencendo)}", border=True, width=kpi_w())

# ---------------------------------------------------------------- atenção hoje
lemb = data.tables()["lembretes"]
if not lemb.empty:
    lemb = lemb.assign(data=pd.to_datetime(lemb["data"]), concluido=lemb["concluido"].astype(bool))
    lemb = lemb[~lemb["concluido"] & (lemb["data"] <= hoje)]

col_a, col_b = st.columns([3, 2])
with col_a:
    with st.container(border=True, height="stretch"):
        st.subheader(":material/notifications_active: Atenção", anchor=False)
        itens = 0
        for _, r in vencendo.sort_values("dias_para_fim").iterrows():
            d = int(r["dias_para_fim"])
            quando = "venceu" if d < 0 else ("termina hoje" if d == 0 else f"termina em {d} dias")
            cor = "red" if d <= 7 else "orange"
            st.markdown(f":{cor}-badge[Prazo] **{r['cliente']}** — {quando} ({data_br(r['data_fim'])}) · {r['fornecedor']}")
            itens += 1
        for _, r in paradas.sort_values("dias_na_etapa", ascending=False).iterrows():
            st.markdown(
                f":violet-badge[Parada] **{r['cliente']}** — {int(r['dias_na_etapa'])} dias em "
                f"*{r['status']}*"
            )
            itens += 1
        for _, r in com_gestor.iterrows():
            st.markdown(f":blue-badge[Sua ação] **{r['cliente']}** — {r['status']}")
            itens += 1
        if not lemb.empty:
            for _, r in lemb.sort_values("data").iterrows():
                st.markdown(f":gray-badge[Lembrete] {r['titulo']} — {data_br(r['data'])}")
                itens += 1
        if not itens:
            st.success("Nada pendente por agora.", icon=":material/check_circle:")

with col_b:
    with st.container(border=True, height="stretch"):
        st.subheader(":material/event: Próximos 14 dias", anchor=False)
        ag = data.tables()["agenda"]
        eventos = []
        if not ag.empty:
            ag = ag.assign(data=pd.to_datetime(ag["data"]))
            for _, r in ag[ag["data"].between(hoje, hoje + timedelta(days=14))].iterrows():
                eventos.append((r["data"], r.get("hora") or "", r["titulo"]))
        for _, r in ativas.iterrows():
            for col, rot in [("data_inicio", "Início"), ("data_fim", "Fim")]:
                if pd.notna(r[col]) and hoje <= r[col] <= hoje + timedelta(days=14):
                    eventos.append((r[col], "", f"{rot} da consultoria — {r['cliente']}"))
        if eventos:
            for d, h, t in sorted(eventos, key=lambda e: (e[0], e[1]))[:12]:
                st.markdown(f"**{d.strftime('%d/%m')}** {h} · {t}")
        else:
            st.caption("Nenhum compromisso nos próximos dias.")

# ---------------------------------------------------------------- funil das etapas
with st.container(border=True):
    st.subheader("Consultorias por etapa", anchor=False)
    etapas = pd.DataFrame({"status_id": range(1, data.ETAPA_FINAL + 1), "nome": data.nomes_etapas()})
    etapas["etapa"] = etapas["status_id"].astype(str).str.zfill(2) + ". " + etapas["nome"].map(data.nome_curto_etapa)
    cont = df.groupby("status_id").size().rename("qtd").reset_index()
    etapas = etapas.merge(cont, on="status_id", how="left").fillna({"qtd": 0})
    etapas["cor"] = etapas["qtd"].map(lambda q: "com" if q else "sem")
    chart = (
        alt.Chart(etapas)
        .mark_bar(cornerRadiusEnd=3)
        .encode(
            y=alt.Y("etapa:N", sort=None, title=None, axis=alt.Axis(labelLimit=label_limit())),
            x=alt.X("qtd:Q", title="Consultorias", axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("cor:N", scale=alt.Scale(domain=["com", "sem"], range=[AZUL, cores()["vazio"]]), legend=None),
            tooltip=[alt.Tooltip("etapa:N", title="Etapa"), alt.Tooltip("qtd:Q", title="Consultorias")],
        )
        .properties(height=21 * 24)
    )
    st.altair_chart(chart, width="stretch", alt="Quantidade de consultorias em cada uma das 21 etapas")

# ---------------------------------------------------------------- cronograma
with st.container(border=True):
    st.subheader("Cronograma das consultorias ativas", anchor=False)
    crono = ativas.dropna(subset=["data_inicio", "data_fim"]).copy()
    if crono.empty:
        st.caption("Sem datas de início e fim cadastradas.")
    else:
        crono["rotulo"] = crono["cliente"] if is_phone() else crono["cliente"] + " · " + crono["fornecedor"]
        barras_g = alt.Chart(crono).mark_bar(cornerRadius=3, color=AZUL_CLARO, height=14).encode(
            y=alt.Y("rotulo:N", sort=alt.EncodingSortField("data_fim"), title=None, axis=alt.Axis(labelLimit=label_limit())),
            x=alt.X("data_inicio:T", title=None, axis=alt.Axis(format="%d/%m")),
            x2="data_fim:T",
            tooltip=[
                alt.Tooltip("cliente:N", title="Cliente"),
                alt.Tooltip("cidade:N", title="Cidade"),
                alt.Tooltip("data_inicio:T", title="Início", format="%d/%m/%Y"),
                alt.Tooltip("data_fim:T", title="Fim", format="%d/%m/%Y"),
                alt.Tooltip("status:N", title="Status"),
            ],
        )
        linha_hoje = alt.Chart(pd.DataFrame({"hoje": [hoje]})).mark_rule(color=LARANJA, strokeDash=[4, 3]).encode(x="hoje:T")
        st.altair_chart(
            (barras_g + linha_hoje).properties(height=max(140, 30 * len(crono))),
            width="stretch",
            alt="Linha do tempo de início e fim das consultorias ativas, com o dia de hoje marcado",
        )
        st.caption("A linha tracejada marca o dia de hoje.")
