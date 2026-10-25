import streamlit as st

from core import config_app
from core.config_app import FONTES, FUNDOS, PADRAO, PALETAS, POSICOES_LOGO_INST
from core.db import supabase_config

salvo = config_app.carregar()

# O arquivo da logo da instituição é salvo na hora do envio, fora do botão "Salvar configurações".
ARQUIVO_LOGO = ("logo_inst_dados", "logo_inst_ext")
EDITAVEIS = [k for k in PADRAO if k not in ARQUIVO_LOGO]

# Valores de trabalho em session_state ("cfg_<campo>"), iniciados com o que está salvo.
for k in EDITAVEIS:
    st.session_state.setdefault(f"cfg_{k}", salvo[k])

CORES = ["primaria", "destaque", "claro_fundo", "claro_painel", "claro_texto",
         "escuro_fundo", "escuro_painel", "escuro_texto"]


def usar_paleta() -> None:
    nome = st.session_state.get("cfg_paleta")
    if nome in PALETAS:
        for campo, cor in zip(CORES, PALETAS[nome]):
            st.session_state[f"cfg_{campo}"] = cor


def marcar_personalizada() -> None:
    st.session_state["cfg_paleta"] = "Personalizada"


def desfazer() -> None:
    for k in EDITAVEIS:
        st.session_state[f"cfg_{k}"] = salvo[k]


def restaurar_padrao() -> None:
    for k in EDITAVEIS:
        st.session_state[f"cfg_{k}"] = PADRAO[k]


def coletar() -> dict:
    cfg = {k: st.session_state.get(f"cfg_{k}", salvo[k]) for k in EDITAVEIS}
    return {**cfg, **{k: salvo[k] for k in ARQUIVO_LOGO}}


secao = st.segmented_control(
    "Seção", ["Aparência", "Alertas", "Identidade", "Sistema"], default="Aparência",
    key="cfg_secao", label_visibility="collapsed",
) or "Aparência"

if secao == "Aparência":
    col1, col2 = st.columns([3, 2])
    with col1:
        with st.container(border=True):
            st.subheader(":material/palette: Cores", anchor=False)
            st.segmented_control("Modo", ["Seguir o sistema", "Claro", "Escuro"], key="cfg_modo", persist_state="page",
                                 help="“Seguir o sistema” usa claro ou escuro conforme o computador/celular")
            st.pills("Paleta pronta", [*PALETAS, "Personalizada"], key="cfg_paleta", persist_state="page", on_change=usar_paleta)
            with st.container(horizontal=True):
                st.color_picker("Cor principal", key="cfg_primaria", persist_state="page", on_change=marcar_personalizada,
                                help="Botões, links, gráficos e mapa")
                st.color_picker("Cor de destaque", key="cfg_destaque", persist_state="page", on_change=marcar_personalizada,
                                help="Segunda série dos gráficos, pontos do mapa e detalhes da logo")
            st.markdown("**Tema claro**")
            with st.container(horizontal=True):
                st.color_picker("Fundo", key="cfg_claro_fundo", persist_state="page", on_change=marcar_personalizada)
                st.color_picker("Painéis e barra lateral", key="cfg_claro_painel", persist_state="page", on_change=marcar_personalizada)
                st.color_picker("Texto", key="cfg_claro_texto", persist_state="page", on_change=marcar_personalizada)
            st.markdown("**Tema escuro**")
            with st.container(horizontal=True):
                st.color_picker("Fundo", key="cfg_escuro_fundo", persist_state="page", on_change=marcar_personalizada)
                st.color_picker("Painéis e barra lateral", key="cfg_escuro_painel", persist_state="page", on_change=marcar_personalizada)
                st.color_picker("Texto", key="cfg_escuro_texto", persist_state="page", on_change=marcar_personalizada)

    with col2:
        with st.container(border=True):
            st.subheader(":material/wallpaper: Plano de fundo", anchor=False)
            st.selectbox("Estilo", FUNDOS, key="cfg_fundo", persist_state="page")
            st.slider("Intensidade", 0, 100, key="cfg_fundo_intensidade", persist_state="page", step=5,
                      disabled=st.session_state["cfg_fundo"] == "Liso")
        with st.container(border=True):
            st.subheader(":material/text_fields: Tipografia e formas", anchor=False)
            st.selectbox("Fonte dos títulos", list(FONTES), key="cfg_fonte_titulos", persist_state="page")
            st.slider("Arredondamento dos cantos (px)", 0, 20, key="cfg_arredondamento", persist_state="page")
            st.toggle("Bordas nos campos", key="cfg_bordas", persist_state="page")
        with st.container(border=True):
            st.subheader(":material/preview: Logo com estas cores", anchor=False)
            st.image(config_app.svg_logo(st.session_state["cfg_primaria"], st.session_state["cfg_destaque"])
                     , width=240)

elif secao == "Alertas":
    with st.container(border=True):
        st.subheader(":material/notifications_active: Alertas do Painel", anchor=False)
        st.slider("Avisar quando a consultoria terminar em até (dias)", 3, 60, key="cfg_alerta_prazo_dias", persist_state="page",
                  help="Consultorias com fim dentro deste prazo aparecem em “Atenção” no Painel")
        st.slider("Considerar parada quando ficar na mesma etapa por mais de (dias)", 5, 90,
                  key="cfg_alerta_parada_dias", persist_state="page",
                  help="Não vale para a etapa “Execução do projeto”, que naturalmente é longa")
        st.caption("A nota de risco da tela Inteligência usa regras fixas, descritas no README.")

elif secao == "Identidade":
    with st.container(border=True):
        st.subheader(":material/account_balance: Logo da instituição", anchor=False)
        st.caption("Envie a logo oficial do Sebrae (PNG com fundo transparente ou SVG funcionam melhor). "
                   "Ela aparece na barra lateral, na tela de login e no cabeçalho dos PDFs.")
        atual = config_app.arquivo_logo_instituicao()
        if atual:
            st.image(str(atual), width=220)
        else:
            st.info("Nenhuma logo enviada ainda.", icon=":material/image:")
        arq = st.file_uploader("Arquivo da logo", type=["png", "jpg", "jpeg", "svg"], key="up_logo_inst",
                               max_upload_size=1)
        with st.container(horizontal=True):
            if st.button("Usar esta logo", type="primary", icon=":material/upload:", disabled=arq is None):
                try:
                    ext = config_app.validar_logo(arq.getvalue(), arq.name)
                except ValueError as e:
                    st.error(str(e))
                else:
                    config_app.definir_logo_instituicao(arq.getvalue(), ext)
                    st.toast("Logo atualizada.", icon=":material/check_circle:")
                    st.rerun()
            if atual and st.button("Remover logo", icon=":material/delete:", type="tertiary"):
                config_app.definir_logo_instituicao(b"", "")
                st.rerun()
        st.segmented_control("Onde mostrar na barra lateral", POSICOES_LOGO_INST, key="cfg_logo_inst_posicao",
                             persist_state="page",
                             help="No topo, ela fica no lugar da logo do app (que passa para baixo do menu)")

    with st.container(border=True):
        st.subheader(":material/badge: Identidade", anchor=False)
        st.text_input("Nome da plataforma", key="cfg_titulo", persist_state="page")
        st.text_input("Subtítulo", key="cfg_subtitulo", persist_state="page")
        st.image(str(config_app.LOGO), width=260)
        st.caption("A logo usa a cor principal e a de destaque escolhidas em Aparência.")
        with st.container(horizontal=True):
            st.download_button("Baixar logo (SVG)", config_app.LOGO.read_bytes(), "logo_gestor_sebraetec.svg",
                               mime="image/svg+xml", icon=":material/download:", on_click="ignore")
            st.download_button("Baixar ícone (SVG)", config_app.LOGO_ICONE.read_bytes(), "icone_gestor_sebraetec.svg",
                               mime="image/svg+xml", icon=":material/download:", on_click="ignore")

else:  # Sistema
    with st.container(border=True):
        st.subheader(":material/storage: Banco de dados", anchor=False)
        if supabase_config():
            st.success("Conectado ao Supabase. Os dados ficam na nuvem e valem em qualquer aparelho.",
                       icon=":material/cloud_done:")
        else:
            st.warning(
                "Modo local: os dados ficam só neste computador (arquivo `data/local.db`). Para usar na "
                "internet e em vários aparelhos, preencha a seção `[supabase]` em `.streamlit/secrets.toml` "
                "(passo a passo no README).",
                title="Dados locais", icon=":material/info:",
            )
    with st.container(border=True):
        st.subheader(":material/help: Sobre", anchor=False)
        st.markdown(
            "- **Configurações** valem para todos os usuários e ficam salvas no banco.\n"
            "- Mudanças de cor e fonte aparecem logo após salvar (a página recarrega sozinha)."
        )

# ---------------------------------------------------------------- salvar
st.divider()
mudou = coletar() != salvo
with st.container(horizontal=True, vertical_alignment="center"):
    if st.button("Salvar configurações", type="primary", icon=":material/save:", disabled=not mudou):
        config_app.salvar(coletar())
        st.toast("Configurações salvas.", icon=":material/check_circle:")
        st.rerun()
    st.button("Desfazer alterações", icon=":material/undo:", disabled=not mudou, on_click=desfazer)
    st.button("Restaurar padrão", icon=":material/restart_alt:", type="tertiary", on_click=restaurar_padrao)
    if mudou:
        st.caption(":orange[Há alterações não salvas.]")
