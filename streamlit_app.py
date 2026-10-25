import streamlit as st

from core import auth, config_app, data

st.set_page_config(page_title="Gestor SEBRAETEC", page_icon="assets/logo_icone.svg", layout="wide")

auth.restaurar_sessao()
if not auth.is_logged_in():
    st.navigation([st.Page(auth.login_form, title="Entrar")], position="hidden").run()
    st.stop()

auth.aplicar_cookie()
data.bootstrap()
cfg = config_app.aplicar()

page = st.navigation(
    {
        "Acompanhamento": [
            st.Page("app_pages/painel.py", title="Painel", icon=":material/space_dashboard:", default=True),
            st.Page("app_pages/consultorias.py", title="Consultorias", icon=":material/assignment:"),
            st.Page("app_pages/agenda.py", title="Agenda e lembretes", icon=":material/calendar_month:"),
        ],
        "Análise": [
            st.Page("app_pages/inteligencia.py", title="Inteligência", icon=":material/insights:"),
            st.Page("app_pages/mapa.py", title="Mapa da Paraíba", icon=":material/map:"),
            st.Page("app_pages/analises.py", title="Análises", icon=":material/bar_chart:"),
            st.Page("app_pages/relatorios.py", title="Relatórios em PDF", icon=":material/print:"),
        ],
        "Administração": [
            st.Page("app_pages/cadastros.py", title="Dados e cadastros", icon=":material/database:"),
            st.Page("app_pages/configuracoes.py", title="Configurações", icon=":material/settings:"),
        ],
    }
)

with st.sidebar:
    inst = config_app.arquivo_logo_instituicao()
    if inst and cfg.get("logo_inst_posicao") == "Abaixo do menu":
        st.image(str(inst), width=170)
    elif inst:  # a da instituição está no topo: a do app vem aqui, discreta
        st.image(str(config_app.LOGO), width=150)
    with st.container(horizontal=True, vertical_alignment="center"):
        st.caption(f":material/person: {st.session_state.user_email}")
        if st.button("Sair", icon=":material/logout:", type="tertiary"):
            auth.logout()

st.title(page.title, anchor=False)
page.run()
