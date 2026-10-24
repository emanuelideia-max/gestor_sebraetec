"""Regras de análise: risco de cada consultoria, alertas automáticos e indicadores de gestão."""

from __future__ import annotations

from datetime import date

import pandas as pd

from core import data
from core.ui import brl, num

NIVEIS = ["Alto", "Médio", "Baixo"]
COR_NIVEL = {"Alto": "red", "Médio": "orange", "Baixo": "green"}


def risco(df: pd.DataFrame, today: date | None = None) -> pd.DataFrame:
    """Acrescenta `risco` (0–100), `nivel` e `motivos` a cada consultoria ativa.

    Pontos somados (máx. 100):
    - prazo vencido sem finalizar: 50 · termina em até 7 dias: 25 · em até 15 dias: 10
    - parada na mesma etapa (fora da execução) > 30 dias: 25 · > 15 dias: 10
    - data de início já passou e ainda não entrou em execução: 30
    - em execução com mais de 90% do prazo consumido: 15 (relatório final se aproxima)
    """
    hoje = pd.Timestamp(today or date.today())
    out = df.copy()
    total = (out["data_fim"] - out["data_inicio"]).dt.days
    out["prazo_consumido"] = ((hoje - out["data_inicio"]).dt.days / total.where(total > 0)).clip(0, 1.5)

    pontos, motivos = [], []
    for _, r in out.iterrows():
        p, m = 0, []
        if r["finalizada"]:
            pontos.append(0)
            motivos.append("")
            continue
        d = r["dias_para_fim"]
        if pd.notna(d):
            if d < 0:
                p += 50
                m.append(f"prazo vencido há {int(-d)} dias")
            elif d <= 7:
                p += 25
                m.append(f"termina em {int(d)} dias")
            elif d <= 15:
                p += 10
                m.append(f"termina em {int(d)} dias")
        parada = r["dias_na_etapa"]
        if pd.notna(parada) and r["status_id"] != 16:
            if parada > 30:
                p += 25
                m.append(f"{int(parada)} dias na mesma etapa")
            elif parada > 15:
                p += 10
                m.append(f"{int(parada)} dias na mesma etapa")
        if pd.notna(r["data_inicio"]) and r["data_inicio"] < hoje and r["status_id"] < 16:
            p += 30
            m.append("deveria já estar em execução")
        if r["status_id"] == 16 and pd.notna(r["prazo_consumido"]) and r["prazo_consumido"] > 0.9:
            p += 15
            m.append(f"{r['prazo_consumido']:.0%} do prazo consumido")
        pontos.append(min(100, p))
        motivos.append("; ".join(m))
    out["risco"] = pontos
    out["motivos"] = motivos
    out["nivel"] = pd.cut(out["risco"], [-1, 19, 49, 100], labels=["Baixo", "Médio", "Alto"]).astype(str)
    return out


def benchmark_valor_hora(df: pd.DataFrame) -> pd.DataFrame:
    """R$/hora de cada consultoria comparado à média da mesma solução (ficha técnica)."""
    b = df.copy()
    media = b.groupby("ficha_tecnica")["valor_hora"].transform("mean")
    b["media_solucao"] = media
    b["desvio"] = (b["valor_hora"] / media.where(media > 0) - 1).fillna(0)
    return b


def concentracao(df: pd.DataFrame, col: str = "fornecedor") -> tuple[float, str, float]:
    """Índice HHI (0–10.000) e o maior participante com sua fatia do valor."""
    v = df.groupby(col)["valor_total"].sum()
    if v.sum() == 0:
        return 0.0, "—", 0.0
    fatias = v / v.sum()
    return float((fatias * 100).pow(2).sum()), str(fatias.idxmax()), float(fatias.max())


def previsao_pagamentos(df: pd.DataFrame) -> pd.DataFrame:
    """Valor a liberar por mês, estimado pela data de fim das consultorias não finalizadas."""
    p = df[~df["finalizada"] & df["data_fim"].notna()].copy()
    if p.empty:
        return pd.DataFrame(columns=["mes", "subsidio", "contrapartida", "valor_total", "qtd"])
    p["mes"] = p["data_fim"].dt.to_period("M").dt.to_timestamp()
    return (p.groupby("mes").agg(subsidio=("subsidio", "sum"), contrapartida=("contrapartida", "sum"),
                                 valor_total=("valor_total", "sum"), qtd=("id", "count"))
            .reset_index())


def alertas(df: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Frases curtas com o que merece atenção: (ícone, cor, texto)."""
    if df.empty:
        return []
    r = risco(df)
    ativas = r[~r["finalizada"]]
    out: list[tuple[str, str, str]] = []

    altos = ativas[ativas["nivel"] == "Alto"]
    if len(altos):
        out.append((":material/error:", "red",
                    f"**{len(altos)} consultoria(s) em risco alto**: " + ", ".join(altos["cliente"].head(3))
                    + ("…" if len(altos) > 3 else "")))

    em15 = ativas[ativas["dias_para_fim"].between(0, 15)]
    if len(ativas) and len(em15) / len(ativas) >= 0.5:
        out.append((":material/hourglass_bottom:", "orange",
                    f"**{len(em15) / len(ativas):.0%} das ativas terminam em até 15 dias** "
                    f"({brl(em15['valor_total'].sum())}). Prepare relatórios finais, reuniões e avaliações."))

    hhi, maior, fatia = concentracao(df)
    if fatia >= 0.4:
        out.append((":material/pie_chart:", "violet",
                    f"**{maior} concentra {fatia:.0%} do valor** (HHI {num(hhi)}). "
                    "Dependência alta de um fornecedor."))

    b = benchmark_valor_hora(df)
    caros = b[(b["desvio"] > 0.15)]
    for _, x in caros.head(2).iterrows():
        out.append((":material/trending_up:", "blue",
                    f"**{x['fornecedor']}** cobra {brl(x['valor_hora'], 2)}/h em *{x['ficha_tecnica']}*, "
                    f"{x['desvio']:.0%} acima da média da solução ({brl(x['media_solucao'], 2)}/h)."))

    fases = ativas["fase"].value_counts()
    if len(fases) == 1 and len(ativas) >= 5:
        out.append((":material/view_kanban:", "gray",
                    f"Todas as ativas estão na fase **{fases.index[0]}**. Sem novas consultorias entrando no funil."))

    cidades = df["cidade"].nunique()
    out.append((":material/map:", "gray",
                f"Atuação em **{cidades} de 223 municípios** da Paraíba ({cidades / 223:.1%})."))
    return out
