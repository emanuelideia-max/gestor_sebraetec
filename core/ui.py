"""Formatação, filtros e gráficos reutilizados pelas páginas."""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

AZUL = "#005EB8"
AZUL_CLARO = "#9CC3EA"
CINZA = "#E6E9EF"
LARANJA = "#E8833A"


def marca() -> tuple[str, str, str]:
    """(principal, destaque, principal clara) conforme as Configurações."""
    from core import config_app

    cfg = config_app.atual()
    p = cfg.get("primaria", AZUL)
    return p, cfg.get("destaque", LARANJA), p + "66"  # versão translúcida da principal


def escuro() -> bool:
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


def cores() -> dict[str, str]:
    """Cores que acompanham o tema claro/escuro e a paleta das Configurações (mapa, rótulos, linhas)."""
    from core.config_app import _rgba

    p, d, _ = marca()
    if escuro():
        return {"vazio": "#1A2640", "borda": "#0B1220", "texto": "#CBD5E1", "suave": "#94A3B8",
                "escala": [_rgba(p, 0.45), p], "pino": d}
    return {"vazio": CINZA, "borda": "#FFFFFF", "texto": "#1E293B", "suave": "#64748B",
            "escala": [_rgba(p, 0.35), p], "pino": d}


def _user_agent() -> str:
    try:
        return st.context.headers.get("User-Agent", "") or ""
    except Exception:
        return ""


def is_phone() -> bool:
    """Celular (pelo navegador do aparelho): layouts mais enxutos."""
    ua = _user_agent()
    return "iPhone" in ua or ("Android" in ua and "Mobile" in ua) or "Mobi" in ua and "iPad" not in ua


def is_tablet() -> bool:
    ua = _user_agent()
    return "iPad" in ua or ("Android" in ua and "Mobile" not in ua) or "Tablet" in ua


def kpi_w():
    """Largura dos cartões de indicador: dois por linha no celular."""
    return 162 if is_phone() else "stretch"


def label_limit() -> int:
    return 110 if is_phone() else (200 if is_tablet() else 300)


def brl(v: float, casas: int = 0) -> str:
    s = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {s}"


def num(v: float, casas: int = 0) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def data_br(d) -> str:
    return "—" if pd.isna(d) else pd.Timestamp(d).strftime("%d/%m/%Y")


MOEDA = st.column_config.NumberColumn(format="localized")


# ---------------------------------------------------------------- filtros

def _multi(label: str, key: str, opts: list) -> list:
    if key in st.session_state:  # descarta opções que sumiram dos dados
        st.session_state[key] = [v for v in st.session_state[key] if v in opts]
    return st.multiselect(label, opts, key=key, placeholder="Todos", persist_state="session")


CHAVES_FILTRO = ["f_cidade", "f_fornecedor", "f_area", "f_categoria", "f_status"]


def _limpar_filtros() -> None:
    for k in [k for k in st.session_state if str(k).startswith("f_")]:
        del st.session_state[k]


def filtros(df: pd.DataFrame) -> pd.DataFrame:
    """Filtros no topo da página (não na barra lateral). Os valores ficam salvos ao trocar de página."""
    ativos = sum(bool(st.session_state.get(k)) for k in CHAVES_FILTRO) + (
        0 if st.session_state.get("f_finalizadas", True) else 1)
    rotulo = "Filtros" + (f" · {ativos} ativo(s)" if ativos else "")
    # no celular ficam recolhidos para não empurrar o conteúdo; no computador ficam à vista
    caixa = (st.expander(rotulo, icon=":material/filter_alt:") if is_phone()
             else st.container(border=True))
    with caixa:
        if not is_phone():
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(f":material/filter_alt: **{rotulo}**")
                st.space("stretch")
                st.button("Limpar filtros", icon=":material/filter_alt_off:", type="tertiary",
                          on_click=_limpar_filtros, disabled=not ativos)
        c1, c2, c3 = st.columns(3)
        with c1:
            cidades = _multi("Cidade", "f_cidade", sorted(df["cidade"].unique()))
        with c2:
            fornecedores = _multi("Fornecedor", "f_fornecedor", sorted(df["fornecedor"].unique()))
        with c3:
            areas = _multi("Área", "f_area", sorted(df["area"].unique()))
        c1, c2, c3 = st.columns(3, vertical_alignment="bottom")
        with c1:
            categorias = _multi("Categoria do cliente", "f_categoria", sorted(df["categoria"].unique()))
        with c2:
            etapas = _multi("Status", "f_status", sorted(df["etapa"].unique()))
        with c3:
            datas = df["inicio_processamento"].dropna()
            periodo = None
            if not datas.empty:
                periodo = st.date_input(
                    "Início do processamento",
                    value=(datas.min().date(), datas.max().date()),
                    key="f_periodo",
                    format="DD/MM/YYYY",
                    persist_state="session",
                )
        with st.container(horizontal=True, vertical_alignment="center"):
            incluir_finalizadas = st.toggle("Incluir finalizadas", value=True, key="f_finalizadas",
                                            persist_state="session")
            if is_phone():
                st.button("Limpar", icon=":material/filter_alt_off:", type="tertiary",
                          on_click=_limpar_filtros, disabled=not ativos)

    out = df
    for col, sel in [("cidade", cidades), ("fornecedor", fornecedores), ("area", areas),
                     ("categoria", categorias), ("etapa", etapas)]:
        if sel:
            out = out[out[col].isin(sel)]
    if periodo and isinstance(periodo, tuple) and len(periodo) == 2:
        ini, fim = pd.Timestamp(periodo[0]), pd.Timestamp(periodo[1])
        out = out[out["inicio_processamento"].isna() | out["inicio_processamento"].between(ini, fim)]
    if not incluir_finalizadas:
        out = out[~out["finalizada"]]
    return out


# ---------------------------------------------------------------- agregações e gráficos

def resumo_por(df: pd.DataFrame, col: str) -> pd.DataFrame:
    g = (
        df.groupby(col)
        .agg(
            consultorias=("id", "count"),
            valor_total=("valor_total", "sum"),
            valor_medio=("valor_total", "mean"),
            horas_total=("carga_horaria", "sum"),
            horas_media=("carga_horaria", "mean"),
            subsidio=("subsidio", "sum"),
            contrapartida=("contrapartida", "sum"),
        )
        .reset_index()
    )
    g["valor_hora_medio"] = (g["valor_total"] / g["horas_total"].where(g["horas_total"] > 0)).fillna(0)
    return g.sort_values("valor_total", ascending=False)


RESUMO_COLUNAS = {
    "consultorias": st.column_config.NumberColumn("Consultorias"),
    "valor_total": st.column_config.NumberColumn("Valor total (R$)", format="localized"),
    "valor_medio": st.column_config.NumberColumn("Valor médio (R$)", format="localized"),
    "horas_total": st.column_config.NumberColumn("Horas", format="%.0f h"),
    "horas_media": st.column_config.NumberColumn("Média de horas", format="%.1f h"),
    "valor_hora_medio": st.column_config.NumberColumn("R$/hora médio (R$)", format="localized"),
    "subsidio": st.column_config.NumberColumn("Subsídio Sebrae (R$)", format="localized"),
    "contrapartida": st.column_config.NumberColumn("Contrapartida (R$)", format="localized"),
}

METRICAS = {
    "Consultorias": ("consultorias", ",.0f"),
    "Valor total": ("valor_total", ",.2f"),
    "Valor médio": ("valor_medio", ",.2f"),
    "Média de horas": ("horas_media", ",.1f"),
    "R$/hora médio": ("valor_hora_medio", ",.2f"),
}


def barras(df: pd.DataFrame, cat: str, val: str, titulo_val: str, fmt: str = ",.2f",
           cor: str | None = None, ordenar: bool = True, altura_barra: int = 28) -> alt.Chart:
    cor = cor or marca()[0]
    sort = "-x" if ordenar else None
    base = alt.Chart(df).encode(
        y=alt.Y(f"{cat}:N", sort=sort, title=None, axis=alt.Axis(labelLimit=label_limit())),
        x=alt.X(f"{val}:Q", title=titulo_val, axis=alt.Axis(format="~s" if fmt.startswith(",.2") else "d")),
        tooltip=[alt.Tooltip(f"{cat}:N", title=""), alt.Tooltip(f"{val}:Q", title=titulo_val, format=fmt)],
    )
    chart = base.mark_bar(color=cor, cornerRadiusEnd=3) + base.mark_text(
        align="left", dx=4, color=cores()["suave"], fontSize=11
    ).encode(text=alt.Text(f"{val}:Q", format=fmt))
    return chart.properties(height=max(120, altura_barra * len(df)))

