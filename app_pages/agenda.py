import calendar
from datetime import date

import pandas as pd
import streamlit as st

from core import data
from core.ui import data_br, is_phone

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro"]
DIAS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]

hoje = date.today()
t = data.tables()
cons = data.consultorias_view()
nomes_cons = {int(r["id"]): f"{r['cliente']} · {r['ficha_tecnica']}" for _, r in cons.iterrows()}

agenda = t["agenda"].copy()
if not agenda.empty:
    agenda["data"] = pd.to_datetime(agenda["data"]).dt.date
lembretes = t["lembretes"].copy()
if not lembretes.empty:
    lembretes["data"] = pd.to_datetime(lembretes["data"]).dt.date
    lembretes["concluido"] = lembretes["concluido"].astype(bool)


def eventos_do_mes(ano: int, mes: int) -> dict[date, list[tuple[str, str]]]:
    """{dia: [(cor, texto)]} juntando agenda, prazos das consultorias e lembretes."""
    ev: dict[date, list[tuple[str, str]]] = {}

    def add(d, cor, texto):
        if d and d.year == ano and d.month == mes:
            ev.setdefault(d, []).append((cor, texto))

    for _, r in agenda.iterrows():
        add(r["data"], "blue", f"{r['hora'] + ' ' if r.get('hora') else ''}{r['titulo']}")
    for _, r in cons[~cons["finalizada"]].iterrows():
        if pd.notna(r["data_inicio"]):
            add(r["data_inicio"].date(), "green", f"Início · {r['cliente']}")
        if pd.notna(r["data_fim"]):
            add(r["data_fim"].date(), "orange", f"Fim · {r['cliente']}")
    for _, r in lembretes.iterrows():
        if not r["concluido"]:
            add(r["data"], "violet", r["titulo"])
    return ev


# ---------------------------------------------------------------- calendário
st.session_state.setdefault("cal_mes", (hoje.year, hoje.month))
ano, mes = st.session_state.cal_mes


def mover(delta: int) -> None:
    a, m = st.session_state.cal_mes
    m += delta
    a, m = (a - 1, 12) if m < 1 else ((a + 1, 1) if m > 12 else (a, m))
    st.session_state.cal_mes = (a, m)


with st.container(border=True):
    st.subheader(f"{MESES[mes - 1]} de {ano}", anchor=False)
    with st.container(horizontal=True, vertical_alignment="center"):
        st.button("Anterior", icon=":material/chevron_left:", on_click=mover, args=(-1,))
        if st.button("Hoje"):
            st.session_state.cal_mes = (hoje.year, hoje.month)
            st.rerun()
        st.button("Próximo", icon=":material/chevron_right:", icon_position="right", on_click=mover, args=(1,))
        st.space("stretch")
        modo = st.segmented_control("Visualização", ["Mês", "Lista"], default="Lista" if is_phone() else "Mês",
                                    key="cal_modo", label_visibility="collapsed")
    st.caption(":blue[■] compromisso  ·  :green[■] início de consultoria  ·  "
               ":orange[■] fim de consultoria  ·  :violet[■] lembrete")

    ev = eventos_do_mes(ano, mes)
    if modo == "Lista":  # melhor no celular: um dia por linha, só os dias com eventos
        if not ev:
            st.caption("Nada neste mês.")
        for dia in sorted(ev):
            semana = DIAS[dia.weekday()]
            st.markdown(f"**{dia:%d/%m} · {semana}**" + (" :blue-badge[hoje]" if dia == hoje else ""))
            for cor, texto in ev[dia]:
                st.markdown(f"&nbsp;&nbsp;:{cor}[■] {texto}")
    else:  # grade do mês (desktop e tablet)
        cols = st.columns(7, gap="xsmall")
        for c, nome in zip(cols, DIAS):
            c.markdown(f"**:gray[{nome}]**")
        for semana in calendar.Calendar(firstweekday=0).monthdatescalendar(ano, mes):
            cols = st.columns(7, gap="xsmall")
            for c, dia in zip(cols, semana):
                with c.container(border=True, height=118):
                    if dia.month != mes:
                        st.markdown(f":gray[{dia.day}]")
                        continue
                    st.markdown(f"**:blue[{dia.day}]** :blue-badge[hoje]" if dia == hoje else f"**{dia.day}**")
                    itens = ev.get(dia, [])
                    for cor, texto in itens[:3]:
                        st.caption(f":{cor}[■] {texto}")
                    if len(itens) > 3:
                        st.caption(f"+{len(itens) - 3} mais")

# ---------------------------------------------------------------- cadastro
col_ev, col_lb = st.columns(2)
with col_ev:
    with st.container(border=True, height="stretch"):
        st.subheader(":material/event: Novo compromisso", anchor=False)
        with st.form("novo_evento", clear_on_submit=True, border=False):
            titulo = st.text_input("Título", placeholder="Ex.: Reunião inicial com o cliente")
            c1, c2, c3 = st.columns(3)
            d = c1.date_input("Data", value=hoje, format="DD/MM/YYYY")
            hora = c2.time_input("Hora", value=None, step=900)
            tipo = c3.selectbox("Tipo", data.TIPOS_EVENTO)
            cons_id = st.selectbox("Consultoria (opcional)", list(nomes_cons), index=None,
                                   format_func=nomes_cons.get, placeholder="Nenhuma")
            local = st.text_input("Local")
            if st.form_submit_button("Adicionar", type="primary", icon=":material/add:"):
                if titulo:
                    data.insert("agenda", {"titulo": titulo, "data": d, "hora": hora.strftime("%H:%M") if hora else None,
                                           "tipo": tipo, "local": local or None, "consultoria_id": cons_id})
                    st.rerun()
                else:
                    st.error("Informe o título.")

with col_lb:
    with st.container(border=True, height="stretch"):
        st.subheader(":material/notifications: Novo lembrete", anchor=False)
        with st.form("novo_lembrete", clear_on_submit=True, border=False):
            titulo_l = st.text_input("Lembrete", placeholder="Ex.: Cobrar relatório final do fornecedor")
            c1, c2 = st.columns(2)
            d_l = c1.date_input("Data", value=hoje, format="DD/MM/YYYY", key="lb_data")
            prio = c2.selectbox("Prioridade", data.PRIORIDADES, index=1)
            cons_l = st.selectbox("Consultoria (opcional)", list(nomes_cons), index=None,
                                  format_func=nomes_cons.get, placeholder="Nenhuma", key="lb_cons")
            if st.form_submit_button("Adicionar", type="primary", icon=":material/add:"):
                if titulo_l:
                    data.insert("lembretes", {"titulo": titulo_l, "data": d_l, "prioridade": prio,
                                              "concluido": False, "consultoria_id": cons_l})
                    st.rerun()
                else:
                    st.error("Informe o lembrete.")

# ---------------------------------------------------------------- listas
col_ev, col_lb = st.columns(2)
with col_ev:
    with st.container(border=True, height="stretch"):
        st.subheader("Próximos compromissos", anchor=False)
        prox = agenda[agenda["data"] >= hoje].sort_values(["data", "hora"]) if not agenda.empty else agenda
        if prox.empty:
            st.caption("Nenhum compromisso futuro.")
        for _, r in prox.iterrows():
            with st.container(horizontal=True, vertical_alignment="center"):
                extra = f" · {nomes_cons[int(r['consultoria_id'])]}" if pd.notna(r.get("consultoria_id")) and int(r["consultoria_id"]) in nomes_cons else ""
                st.markdown(f"**{data_br(r['data'])}** {r.get('hora') or ''} · {r['titulo']} "
                            f":gray[({r.get('tipo') or '—'}{extra})]")
                if st.button("Remover", icon=":material/close:", key=f"del_ev_{r['id']}", type="tertiary"):
                    data.delete("agenda", r["id"])
                    st.rerun()

with col_lb:
    with st.container(border=True, height="stretch"):
        st.subheader("Lembretes pendentes", anchor=False)
        pend = lembretes[~lembretes["concluido"]].sort_values("data") if not lembretes.empty else lembretes
        if pend.empty:
            st.caption("Nenhum lembrete pendente.")
        cores = {"Alta": "red", "Normal": "blue", "Baixa": "gray"}
        for _, r in pend.iterrows():
            atrasado = r["data"] < hoje
            with st.container(horizontal=True, vertical_alignment="center"):
                feito = st.checkbox(
                    f"{r['titulo']} — {data_br(r['data'])}" + (" :red[(atrasado)]" if atrasado else ""),
                    key=f"lb_{r['id']}",
                )
                st.badge(r.get("prioridade") or "Normal", color=cores.get(r.get("prioridade"), "gray"))
            if feito:
                data.update("lembretes", r["id"], {"concluido": True})
                st.rerun()
