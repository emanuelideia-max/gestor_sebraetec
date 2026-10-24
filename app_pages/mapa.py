import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import data
from core.db import ROOT
from core.ui import cores, kpi_w, is_phone, METRICAS, RESUMO_COLUNAS, resumo_por, filtros


@st.cache_data
def carregar_malha() -> tuple[dict, pd.DataFrame]:
    with open(ROOT / "data" / "pb_municipios.geojson", encoding="utf-8") as fh:
        geo = json.load(fh)
    municipios = pd.read_csv(ROOT / "data" / "municipios_pb.csv")
    return geo, municipios


df = filtros(data.consultorias_view())
geo, municipios = carregar_malha()

metrica = st.segmented_control(
    "Colorir cidades atendidas por", list(METRICAS), default="Consultorias", key="mapa_metrica"
) or "Consultorias"
col, fmt = METRICAS[metrica]
mostrar_nomes = st.toggle("Mostrar nomes das cidades atendidas", value=False, key="mapa_nomes")

com_cidade = df.dropna(subset=["codigo_ibge"]).astype({"codigo_ibge": int})
resumo = resumo_por(com_cidade, "codigo_ibge") if not com_cidade.empty else pd.DataFrame()
if not resumo.empty:
    extra = com_cidade.groupby("codigo_ibge").agg(
        fornecedores=("fornecedor", lambda s: ", ".join(sorted(set(s)))),
    )
    resumo = resumo.merge(extra, on="codigo_ibge").merge(municipios, on="codigo_ibge", how="left")

atendidas = set(resumo["codigo_ibge"]) if not resumo.empty else set()
nao_atendidas = municipios[~municipios["codigo_ibge"].isin(atendidas)]

paleta = cores()
fig = go.Figure()
fig.add_trace(
    go.Choropleth(
        geojson=geo,
        featureidkey="properties.codigo_ibge",
        locations=nao_atendidas["codigo_ibge"],
        z=[0] * len(nao_atendidas),
        text=nao_atendidas["nome"],
        colorscale=[[0, paleta["vazio"]], [1, paleta["vazio"]]],
        showscale=False,
        marker_line_color=paleta["borda"],
        marker_line_width=0.6,
        hovertemplate="%{text}<br>Sem consultorias<extra></extra>",
    )
)
if not resumo.empty:
    valor_fmt = ",.2f" if "valor" in col else (",.1f" if col == "horas_media" else ",.0f")
    prefixo = "R$ " if "valor" in col else ""
    fig.add_trace(
        go.Choropleth(
            geojson=geo,
            featureidkey="properties.codigo_ibge",
            locations=resumo["codigo_ibge"],
            z=resumo[col],
            customdata=resumo[["nome", "consultorias", "valor_total", "horas_media", "valor_hora_medio", "fornecedores"]],
            colorscale=[[0, paleta["escala"][0]], [1, paleta["escala"][1]]],
            marker_line_color=paleta["borda"],
            marker_line_width=0.8,
            colorbar=dict(title=dict(text=metrica, side="right"), thickness=10, len=0.6, tickprefix=prefixo),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Consultorias: %{customdata[1]}<br>"
                "Valor total: R$ %{customdata[2]:,.2f}<br>"
                "Média de horas: %{customdata[3]:.1f} h<br>"
                "R$/hora médio: R$ %{customdata[4]:,.2f}<br>"
                "Fornecedores: %{customdata[5]}<extra></extra>"
            ),
        )
    )
CAMADA_PINOS = len(fig.data)  # índice da camada clicável (o Streamlit só captura clique em pontos)
if not resumo.empty:
    fig.add_trace(
        go.Scattergeo(
            lon=resumo["lon"],
            lat=resumo["lat"],
            text=resumo["nome"],
            customdata=resumo[["nome", "consultorias", "valor_total", "horas_media", "valor_hora_medio", "fornecedores"]],
            mode="markers+text" if mostrar_nomes else "markers",
            textposition="top center",
            textfont=dict(size=10, color=paleta["texto"]),
            marker=dict(size=11, color=paleta["pino"], line=dict(width=1.5, color=paleta["borda"])),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Consultorias: %{customdata[1]}<br>"
                "Valor total: R$ %{customdata[2]:,.2f}<br>"
                "Média de horas: %{customdata[3]:.1f} h<br>"
                "R$/hora médio: R$ %{customdata[4]:,.2f}<br>"
                "Fornecedores: %{customdata[5]}<br><i>Clique para abrir</i><extra></extra>"
            ),
        )
    )
fig.update_geos(fitbounds="geojson", visible=False, projection_type="mercator", bgcolor="rgba(0,0,0,0)")
fig.update_layout(height=360 if is_phone() else 520, margin=dict(l=0, r=0, t=0, b=0), showlegend=False, clickmode="event+select",
                  separators=",.")  # números no padrão brasileiro

with st.container(horizontal=True):
    st.metric("Cidades atendidas", f"{len(atendidas)} de {len(municipios)}", border=True, width=kpi_w())
    st.metric("Mesorregiões", f"{resumo['mesorregiao'].nunique() if not resumo.empty else 0}", border=True, width=kpi_w())
    st.metric("Consultorias no filtro", f"{len(df)}", border=True, width=kpi_w())

def abrir_consultorias(cidade: str) -> None:
    """Leva para a tela Consultorias já filtrada pela cidade."""
    st.session_state["cons_cidade"] = [cidade]
    st.session_state["cons_situacao"] = "Todas"
    st.session_state.pop("consultoria_sel", None)
    st.switch_page("app_pages/consultorias.py")


with st.container(border=True):
    evento = st.plotly_chart(
        fig,
        config={"displayModeBar": False, "scrollZoom": False},
        on_select="rerun",
        selection_mode="points",
        key="mapa_clique",
        alt="Mapa dos municípios da Paraíba com as cidades atendidas em azul",
    )
    st.caption("Cidades atendidas em azul (mais escuro = maior valor da métrica). "
               "Clique no ponto de uma cidade para abrir as consultorias dela.")
    if not resumo.empty:
        escolhida = st.pills("Abrir consultorias de", sorted(resumo["nome"]), key="mapa_pill")
        if escolhida:
            abrir_consultorias(escolhida)

pontos = (evento.selection.points if evento and evento.selection else []) or []
for p in pontos:
    if p.get("curve_number") == CAMADA_PINOS and not resumo.empty:
        abrir_consultorias(resumo.iloc[int(p["point_index"])]["nome"])

if not resumo.empty:
    with st.container(border=True):
        st.subheader("Resumo por cidade", anchor=False)
        tabela = resumo.rename(columns={"nome": "cidade"})
        st.dataframe(
            tabela,
            hide_index=True,
            column_order=["cidade", "mesorregiao", "consultorias", "valor_total", "valor_medio",
                          "horas_media", "valor_hora_medio", "fornecedores"],
            column_config={**RESUMO_COLUNAS, "cidade": "Cidade", "mesorregiao": "Mesorregião",
                           "fornecedores": "Fornecedores"},
            alt="Resumo das consultorias por cidade",
        )
