"""Relatórios em PDF (fpdf2) para impressão."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from fpdf import FPDF
from fpdf.fonts import FontFace

from core import data
from core.ui import brl, data_br, num

AZUL = (0, 94, 184)
CINZA_TXT = (120, 119, 116)
CINZA_LINHA = (234, 234, 234)
FUNDO = (247, 246, 243)


def _t(text) -> str:
    """Fontes padrão do PDF usam latin-1: troca o que não existe nele."""
    s = "" if text is None or (not isinstance(text, str) and pd.isna(text)) else str(text)
    for a, b in {"—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "…": "...", "■": "-"}.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


class Relatorio(FPDF):
    def __init__(self, titulo: str, subtitulo: str = "", paisagem: bool = False):
        super().__init__(orientation="L" if paisagem else "P", unit="mm", format="A4")
        self.titulo, self.subtitulo = titulo, subtitulo
        self.set_auto_page_break(True, margin=16)
        self.set_margins(14, 14, 14)
        self.alias_nb_pages()
        self.add_page()

    def header(self):
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(47, 52, 55)
        self.cell(0, 8, _t(self.titulo), new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*CINZA_TXT)
        info = f"Gestor SEBRAETEC - gerado em {datetime.now():%d/%m/%Y %H:%M}"
        self.cell(0, 5, _t(f"{self.subtitulo}  |  {info}" if self.subtitulo else info), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*AZUL)
        self.set_line_width(0.6)
        self.line(self.l_margin, self.get_y() + 2, self.w - self.r_margin, self.get_y() + 2)
        self.ln(6)

    def footer(self):
        self.set_y(-11)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*CINZA_TXT)
        self.cell(0, 5, f"Página {self.page_no()} de {{nb}}", align="R")

    # ------------------------------------------------------------ blocos
    def secao(self, titulo: str):
        if self.get_y() > self.h - 40:
            self.add_page()
        self.ln(2)
        self.set_font("Helvetica", "B", 11.5)
        self.set_text_color(*AZUL)
        self.cell(0, 7, _t(titulo), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(47, 52, 55)

    def kpis(self, itens: list[tuple[str, str]]):
        largura = (self.w - self.l_margin - self.r_margin - 3 * (len(itens) - 1)) / len(itens)
        y = self.get_y()
        for i, (rot, val) in enumerate(itens):
            x = self.l_margin + i * (largura + 3)
            self.set_fill_color(*FUNDO)
            self.set_draw_color(*CINZA_LINHA)
            self.rect(x, y, largura, 16, style="DF")
            self.set_xy(x + 3, y + 2)
            self.set_font("Helvetica", "", 7.5)
            self.set_text_color(*CINZA_TXT)
            self.cell(largura - 6, 4, _t(rot))
            self.set_xy(x + 3, y + 7)
            self.set_font("Helvetica", "B", 11)
            self.set_text_color(47, 52, 55)
            self.cell(largura - 6, 6, _t(val))
        self.set_y(y + 19)

    def barras(self, df: pd.DataFrame, cat: str, val: str, fmt=lambda v: brl(v)):
        if df.empty:
            return
        df = df.sort_values(val, ascending=False).head(15)
        rotulo_w = 55
        area_w = self.w - self.l_margin - self.r_margin - rotulo_w - 28
        maximo = df[val].max() or 1
        self.set_font("Helvetica", "", 8.5)
        for _, r in df.iterrows():
            if self.get_y() > self.h - 22:
                self.add_page()
            y = self.get_y()
            self.set_text_color(47, 52, 55)
            self.cell(rotulo_w, 5.5, _t(str(r[cat]))[:38])
            self.set_fill_color(*AZUL)
            self.rect(self.l_margin + rotulo_w, y + 1, max(0.5, area_w * r[val] / maximo), 3.6, style="F")
            self.set_xy(self.l_margin + rotulo_w + area_w * r[val] / maximo + 2, y)
            self.set_text_color(*CINZA_TXT)
            self.cell(26, 5.5, _t(fmt(r[val])))
            self.set_xy(self.l_margin, y + 5.5)
        self.ln(2)

    def tabela(self, df: pd.DataFrame, colunas: dict[str, tuple[str, callable]], larguras: list[float]):
        if df.empty:
            self.set_font("Helvetica", "I", 9)
            self.cell(0, 6, "Sem dados.", new_x="LMARGIN", new_y="NEXT")
            return
        self.set_font("Helvetica", "", 8)
        self.set_draw_color(*CINZA_LINHA)
        self.set_text_color(47, 52, 55)
        cab = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=AZUL)
        listras = [FontFace(color=(47, 52, 55), fill_color=(255, 255, 255)),
                   FontFace(color=(47, 52, 55), fill_color=FUNDO)]
        with self.table(col_widths=larguras, headings_style=cab, line_height=5,
                        borders_layout="HORIZONTAL_LINES", text_align="LEFT") as t:
            linha = t.row()
            for titulo, _ in colunas.values():
                linha.cell(_t(titulo))
            for i, (_, r) in enumerate(df.iterrows()):
                linha = t.row(style=listras[i % 2])
                for col, (_, fmt) in colunas.items():
                    linha.cell(_t(fmt(r[col]) if fmt else r[col]))
        self.ln(3)

    def saida(self) -> bytes:
        return bytes(self.output())


def _resumo(df: pd.DataFrame, col: str) -> pd.DataFrame:
    from core.ui import resumo_por
    return resumo_por(df, col)


COL_RESUMO = {
    "consultorias": ("Qtd.", lambda v: f"{int(v)}"),
    "valor_total": ("Valor total", brl),
    "valor_medio": ("Valor médio", brl),
    "horas_media": ("Média de horas", lambda v: f"{num(v, 1)} h"),
    "valor_hora_medio": ("R$/hora", lambda v: brl(v, 2)),
}

SECOES = ["Resumo geral", "Por cidade", "Por fornecedor", "Por etapa", "Prazos próximos", "Lista de consultorias"]


def relatorio_geral(df: pd.DataFrame, secoes: list[str], filtros: str = "", paisagem: bool = True) -> bytes:
    pdf = Relatorio("Relatório de consultorias SEBRAETEC", filtros, paisagem)
    largura = pdf.w - pdf.l_margin - pdf.r_margin

    if "Resumo geral" in secoes:
        horas = df["carga_horaria"].sum()
        pdf.kpis([
            ("Consultorias", f"{len(df)} ({int((~df['finalizada']).sum())} ativas)"),
            ("Valor contratado", brl(df["valor_total"].sum())),
            ("Subsídio Sebrae", brl(df["subsidio"].sum())),
            ("Contrapartida", brl(df["contrapartida"].sum())),
            ("Horas", f"{num(horas)} h"),
            ("R$/hora médio", brl(df["valor_total"].sum() / horas if horas else 0, 2)),
        ])

    for titulo, col in [("Por cidade", "cidade"), ("Por fornecedor", "fornecedor")]:
        if titulo in secoes:
            r = _resumo(df, col)
            pdf.secao(f"Valor total {titulo.lower()}")
            pdf.barras(r, col, "valor_total")
            pdf.tabela(r, {col: (titulo.split()[-1].capitalize(), None), **COL_RESUMO},
                       [largura * p for p in (0.32, 0.08, 0.16, 0.16, 0.14, 0.14)])

    if "Por etapa" in secoes:
        pdf.secao("Consultorias por etapa")
        e = df.groupby(["status_id", "status"]).agg(qtd=("id", "count"), valor=("valor_total", "sum")).reset_index()
        e["etapa"] = e["status_id"].map(lambda i: f"{int(i):02d}")
        pdf.tabela(e, {"etapa": ("Nº", None), "status": ("Etapa", None), "qtd": ("Qtd.", lambda v: f"{int(v)}"),
                       "valor": ("Valor", brl)}, [largura * p for p in (0.08, 0.56, 0.12, 0.24)])

    if "Prazos próximos" in secoes:
        pdf.secao("Prazos das consultorias ativas")
        p = df[~df["finalizada"] & df["data_fim"].notna()].sort_values("data_fim")
        pdf.tabela(p, {"cliente": ("Cliente", None), "cidade": ("Cidade", None), "fornecedor": ("Fornecedor", None),
                       "data_fim": ("Fim", data_br),
                       "dias_para_fim": ("Dias", lambda v: "-" if pd.isna(v) else f"{int(v)}")},
                   [largura * p for p in (0.32, 0.2, 0.28, 0.12, 0.08)])

    if "Lista de consultorias" in secoes:
        pdf.secao("Lista de consultorias")
        lst = df.sort_values(["cidade", "cliente"])
        pdf.tabela(lst, {
            "cliente": ("Cliente", None), "cidade": ("Cidade", None), "fornecedor": ("Fornecedor", None),
            "ficha_tecnica": ("Solução", None), "valor_total": ("Valor", brl),
            "carga_horaria": ("Horas", lambda v: num(v)), "status": ("Etapa atual", None),
            "data_fim": ("Fim", data_br),
        }, [largura * p for p in (0.17, 0.11, 0.14, 0.2, 0.09, 0.05, 0.16, 0.08)])

    return pdf.saida()


def ficha_consultoria(row: pd.Series, hist: pd.DataFrame) -> bytes:
    pdf = Relatorio(f"Ficha da consultoria - {row['cliente']}", row["ficha_tecnica"])
    largura = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.kpis([
        ("Valor total", brl(row["valor_total"], 2)),
        ("Subsídio Sebrae", brl(row["subsidio"], 2)),
        ("Contrapartida", brl(row["contrapartida"], 2)),
        ("Carga horária", f"{num(row['carga_horaria'])} h"),
    ])
    pdf.secao("Dados")
    dados = pd.DataFrame([
        ("Cliente", row["cliente"]), ("Categoria", row["categoria"]), ("Cidade", row["cidade"]),
        ("Fornecedor", row["fornecedor"]), ("Área", row["area"]), ("Solução", row["ficha_tecnica"]),
        ("Valor por hora", brl(row["valor_hora"], 2)),
        ("Início do processamento", data_br(row["inicio_processamento"])),
        ("Período da proposta", f"{data_br(row['data_inicio'])} a {data_br(row['data_fim'])}"),
        ("Etapa atual", f"{int(row['status_id'])}/{data.ETAPA_FINAL} - {row['status']}"),
        ("Na etapa desde", data_br(row["status_desde"])),
        ("Observações", row["observacoes"] if pd.notna(row["observacoes"]) else "-"),
    ], columns=["campo", "valor"])
    pdf.tabela(dados, {"campo": ("Campo", None), "valor": ("Informação", None)}, [largura * 0.3, largura * 0.7])

    pdf.secao("Etapas")
    datas = hist.groupby("status_id")["data"].max().to_dict() if not hist.empty else {}
    etapas = pd.DataFrame({"n": range(1, data.ETAPA_FINAL + 1), "nome": data.nomes_etapas()})
    etapas["situacao"] = etapas["n"].map(
        lambda i: "Concluída" if i < row["status_id"] else ("Atual" if i == row["status_id"] else "Pendente"))
    etapas["data"] = etapas["n"].map(lambda i: data_br(datas.get(i)))
    pdf.tabela(etapas, {"n": ("Nº", lambda v: f"{int(v):02d}"), "nome": ("Etapa", None),
                        "situacao": ("Situação", None), "data": ("Data", None)},
               [largura * p for p in (0.08, 0.6, 0.16, 0.16)])
    return pdf.saida()
