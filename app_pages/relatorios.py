from datetime import date

import streamlit as st

from core import data, pdf
from core.ui import filtros

df = filtros(data.consultorias_view())

st.markdown("Escolha o que entra no relatório. Os filtros acima também se aplicam.")

with st.container(border=True):
    secoes = st.pills("Seções", pdf.SECOES, selection_mode="multi", default=pdf.SECOES, key="rel_secoes",
                      persist_state="session")
    orientacao = st.segmented_control("Orientação da página", ["Paisagem", "Retrato"], default="Paisagem",
                                      key="rel_orient", persist_state="session")

    filtros = []
    for chave, rotulo in [("f_cidade", "Cidades"), ("f_fornecedor", "Fornecedores"), ("f_area", "Áreas"),
                          ("f_categoria", "Categorias"), ("f_status", "Status")]:
        if st.session_state.get(chave):
            filtros.append(f"{rotulo}: {', '.join(st.session_state[chave])}")
    if not st.session_state.get("f_finalizadas", True):
        filtros.append("Sem finalizadas")
    st.caption("Filtros aplicados: " + ("; ".join(filtros) if filtros else "nenhum (todas as consultorias)"))

    if df.empty or not secoes:
        st.info("Nada para imprimir com os filtros e seções escolhidos.", icon=":material/info:")
    else:
        arquivo = pdf.relatorio_geral(df, secoes, "; ".join(filtros), paisagem=orientacao != "Retrato")
        st.download_button(
            f"Baixar PDF ({len(df)} consultorias)",
            arquivo,
            file_name=f"relatorio_sebraetec_{date.today():%Y-%m-%d}.pdf",
            mime="application/pdf",
            icon=":material/picture_as_pdf:",
            type="primary",
            width="stretch",
        )
        st.caption("Abra o arquivo e use Ctrl+P (ou Compartilhar → Imprimir no celular) para imprimir.")

if not df.empty and secoes:
    with st.expander("Pré-visualizar", icon=":material/visibility:", on_change="rerun", key="rel_prev") as prev:
        if prev.open:
            st.pdf(arquivo, height=700)
