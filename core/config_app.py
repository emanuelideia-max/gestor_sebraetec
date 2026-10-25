"""Configurações da plataforma (aparência e alertas).

Ficam salvas no banco (tabela `configuracoes`, linha id=1) para valer em qualquer aparelho.
O tema nativo do Streamlit é gerado em `.streamlit/config.toml` a partir delas; o plano de fundo
decorativo é aplicado por CSS (pedido explícito do usuário).
"""

from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path

import streamlit as st

from core.db import ROOT, get_backend

CONFIG_TOML = ROOT / ".streamlit" / "config.toml"

FONTES = {
    "Space Grotesk": "Space+Grotesk:wght@500;600;700",
    "Sora": "Sora:wght@500;600;700",
    "IBM Plex Sans": "IBM+Plex+Sans:wght@500;600;700",
    "JetBrains Mono": "JetBrains+Mono:wght@500;600;700",
    "Geist": "Geist:wght@500;600;700",
}

FUNDOS = ["Liso", "Gradiente suave", "Grade tecnológica", "Pontos", "Aurora"]

# Paletas prontas: (principal, destaque, fundo claro, painel claro, texto claro, fundo escuro, painel escuro, texto escuro)
PALETAS = {
    "Sebrae": ("#005EB8", "#E8833A", "#FFFFFF", "#F4F6FA", "#1E293B", "#0B1220", "#111B2E", "#E2E8F0"),
    "Tech neon": ("#22D3EE", "#A78BFA", "#F8FAFC", "#EEF2F7", "#0F172A", "#05070D", "#0D1220", "#E5F2FF"),
    "Grafite": ("#64748B", "#F59E0B", "#FAFAF9", "#F1F1EF", "#1C1917", "#111111", "#1A1A1A", "#E7E5E4"),
    "Verde": ("#059669", "#0EA5E9", "#FFFFFF", "#F2F7F5", "#14261F", "#07130F", "#0E1F19", "#DCEFE7"),
    "Roxo": ("#7C3AED", "#EC4899", "#FFFFFF", "#F6F4FB", "#1E1B2E", "#0D0B16", "#161226", "#EAE6F7"),
}

PADRAO = {
    "titulo": "Gestor SEBRAETEC",
    "subtitulo": "Acompanhamento de consultorias",
    "modo": "Seguir o sistema",          # "Seguir o sistema" | "Claro" | "Escuro"
    "paleta": "Sebrae",
    "primaria": PALETAS["Sebrae"][0],
    "destaque": PALETAS["Sebrae"][1],
    "claro_fundo": PALETAS["Sebrae"][2],
    "claro_painel": PALETAS["Sebrae"][3],
    "claro_texto": PALETAS["Sebrae"][4],
    "escuro_fundo": PALETAS["Sebrae"][5],
    "escuro_painel": PALETAS["Sebrae"][6],
    "escuro_texto": PALETAS["Sebrae"][7],
    "fundo": "Grade tecnológica",
    "fundo_intensidade": 40,              # 0–100
    "fonte_titulos": "Space Grotesk",
    "arredondamento": 8,                  # px
    "bordas": True,
    "alerta_prazo_dias": 15,
    "alerta_parada_dias": 20,
    "logo_inst_posicao": "Topo da barra lateral",  # ou "Abaixo do menu"
    "logo_inst_dados": "",                        # arquivo enviado, em base64 (fica no banco)
    "logo_inst_ext": "",                          # png | jpg | svg
}


def carregar() -> dict:
    from core import data

    df = data.tables().get("configuracoes")
    cfg = dict(PADRAO)
    if df is not None and not df.empty:
        bruto = df.iloc[0].get("dados")
        if isinstance(bruto, str):
            try:
                bruto = json.loads(bruto)
            except ValueError:
                bruto = {}
        if isinstance(bruto, dict):
            cfg.update({k: v for k, v in bruto.items() if k in PADRAO})
    return cfg


def salvar(cfg: dict) -> None:
    from core import data

    backend = get_backend()
    dados = cfg if backend.name == "supabase" else json.dumps(cfg, ensure_ascii=False)
    atual = data.tables().get("configuracoes")
    if atual is not None and not atual.empty:
        backend.update("configuracoes", 1, {"dados": dados})
    else:
        backend.insert("configuracoes", {"id": 1, "dados": dados})
    data.refresh()
    aplicar_tema(cfg)


# ---------------------------------------------------------------- tema nativo (config.toml)

def _q(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def gerar_toml(cfg: dict) -> str:
    fonte = cfg["fonte_titulos"]
    claro = {
        "primaryColor": cfg["primaria"], "backgroundColor": cfg["claro_fundo"],
        "secondaryBackgroundColor": cfg["claro_painel"], "textColor": cfg["claro_texto"],
        "linkColor": cfg["primaria"],
    }
    escuro = {
        "primaryColor": cfg["primaria"], "backgroundColor": cfg["escuro_fundo"],
        "secondaryBackgroundColor": cfg["escuro_painel"], "textColor": cfg["escuro_texto"],
        "linkColor": cfg["primaria"],
    }
    cores_graf = [cfg["primaria"], cfg["destaque"], "#14B8A6", "#8B5CF6", "#EF4444", "#64748B"]

    def secao(nome: str, valores: dict) -> str:
        return f"[{nome}]\n" + "\n".join(f"{k} = {_q(v)}" for k, v in valores.items()) + "\n"

    base = {
        "font": "Geist:https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&display=swap",
        "headingFont": f"{fonte}:https://fonts.googleapis.com/css2?family={FONTES[fonte]}&display=swap",
        "codeFont": "JetBrains Mono:https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap",
        "baseRadius": f"{int(cfg['arredondamento'])}px",
        "showWidgetBorder": bool(cfg["bordas"]),
        "metricValueFontSize": "1.6rem",
        "metricValueFontWeight": 600,
    }
    partes = ["# Gerado pela tela Configurações do sistema. Edite por lá.\n"]
    if cfg["modo"] == "Claro":
        partes.append(secao("theme", {"base": "light", **base, **claro, "borderColor": "#E3E8F0",
                                      "chartCategoricalColors": cores_graf}))
        partes.append(secao("theme.sidebar", {"backgroundColor": cfg["claro_painel"]}))
    elif cfg["modo"] == "Escuro":
        partes.append(secao("theme", {"base": "dark", **base, **escuro, "borderColor": "#1E2B45",
                                      "chartCategoricalColors": cores_graf}))
        partes.append(secao("theme.sidebar", {"backgroundColor": cfg["escuro_painel"]}))
    else:
        partes.append(secao("theme", base))
        partes.append(secao("theme.light", {**claro, "borderColor": "#E3E8F0", "chartCategoricalColors": cores_graf}))
        partes.append(secao("theme.light.sidebar", {"backgroundColor": cfg["claro_painel"]}))
        partes.append(secao("theme.dark", {**escuro, "borderColor": "#1E2B45", "chartCategoricalColors": cores_graf}))
        partes.append(secao("theme.dark.sidebar", {"backgroundColor": cfg["escuro_painel"]}))
    partes.append(secao("server", {"runOnSave": True}))
    partes.append(secao("client", {"toolbarMode": "minimal"}))
    return "\n".join(partes)


def aplicar_tema(cfg: dict) -> bool:
    """Reescreve o config.toml se mudou. Devolve True quando houve mudança."""
    if os.environ.get("GESTOR_TEMA_FIXO"):  # testes: não mexer no arquivo do projeto
        return False
    novo = gerar_toml(cfg)
    atual = CONFIG_TOML.read_text(encoding="utf-8") if CONFIG_TOML.exists() else ""
    if novo == atual:
        return False
    CONFIG_TOML.write_text(novo, encoding="utf-8")
    return True


# ---------------------------------------------------------------- plano de fundo (CSS)

def _rgba(hex_cor: str, alfa: float) -> str:
    h = hex_cor.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alfa:.3f})"


def css_fundo(cfg: dict) -> str:
    """CSS do plano de fundo decorativo. Usa a cor principal com transparência, então serve no claro e no escuro."""
    k = max(0, min(100, int(cfg["fundo_intensidade"]))) / 100
    p, d = cfg["primaria"], cfg["destaque"]
    estilo = cfg["fundo"]
    if estilo == "Liso" or k == 0:
        return ""
    if estilo == "Gradiente suave":
        img = f"linear-gradient(160deg, {_rgba(p, 0.16 * k)} 0%, transparent 45%, {_rgba(d, 0.10 * k)} 100%)"
        extra = ""
    elif estilo == "Grade tecnológica":
        linha = _rgba(p, 0.12 * k)
        img = (f"linear-gradient({linha} 1px, transparent 1px), linear-gradient(90deg, {linha} 1px, transparent 1px), "
               f"radial-gradient(ellipse at top, {_rgba(p, 0.14 * k)}, transparent 60%)")
        extra = "background-size: 32px 32px, 32px 32px, 100% 100%;"
    elif estilo == "Pontos":
        img = f"radial-gradient({_rgba(p, 0.28 * k)} 1px, transparent 1.5px)"
        extra = "background-size: 22px 22px;"
    else:  # Aurora
        img = (f"radial-gradient(circle at 15% 10%, {_rgba(p, 0.22 * k)}, transparent 40%), "
               f"radial-gradient(circle at 85% 0%, {_rgba(d, 0.18 * k)}, transparent 35%), "
               f"radial-gradient(circle at 60% 100%, {_rgba(p, 0.12 * k)}, transparent 45%)")
        extra = ""
    return (
        "<style>"
        f'[data-testid="stAppViewContainer"] {{ background-image: {img}; {extra} background-attachment: fixed; }}'
        '[data-testid="stHeader"] { background: transparent; }'
        "</style>"
    )


# ---------------------------------------------------------------- logo

LOGO = ROOT / "assets" / "logo.svg"
LOGO_ICONE = ROOT / "assets" / "logo_icone.svg"


def svg_icone(p: str, d: str) -> str:
    """Ícone: quadrado arredondado com uma linha de crescimento ligando nós (consultoria + dados)."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="48" height="48">
  <rect x="2" y="2" width="44" height="44" rx="12" fill="{p}"/>
  <path d="M11 34 L20 24 L27 29 L37 15" fill="none" stroke="#FFFFFF" stroke-width="3.2"
        stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="11" cy="34" r="3.4" fill="#FFFFFF"/>
  <circle cx="20" cy="24" r="3.4" fill="#FFFFFF"/>
  <circle cx="27" cy="29" r="3.4" fill="#FFFFFF"/>
  <circle cx="37" cy="15" r="4.6" fill="{d}" stroke="#FFFFFF" stroke-width="2"/>
</svg>"""


def svg_logo(p: str, d: str) -> str:
    """Logo completa: ícone + nome. Texto na cor principal, legível no claro e no escuro."""
    icone = svg_icone(p, d).split("\n", 1)[1].rsplit("</svg>", 1)[0]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 230 48" width="230" height="48">
  <g>{icone}</g>
  <text x="58" y="22" font-family="Space Grotesk, Geist, Segoe UI, Arial, sans-serif" font-size="17"
        font-weight="700" fill="{p}" letter-spacing="0.2">Gestor</text>
  <text x="58" y="40" font-family="Space Grotesk, Geist, Segoe UI, Arial, sans-serif" font-size="13"
        font-weight="600" fill="{d}" letter-spacing="2.6">SEBRAETEC</text>
</svg>"""


def gerar_logos(cfg: dict) -> None:
    LOGO.parent.mkdir(parents=True, exist_ok=True)
    for arq, conteudo in [(LOGO, svg_logo(cfg["primaria"], cfg["destaque"])),
                          (LOGO_ICONE, svg_icone(cfg["primaria"], cfg["destaque"]))]:
        if not arq.exists() or arq.read_text(encoding="utf-8") != conteudo:
            arq.write_text(conteudo, encoding="utf-8")


# ---------------------------------------------------------------- logo da instituição (ex.: Sebrae)

LOGO_INST_EXTS = ("png", "jpg", "svg")
POSICOES_LOGO_INST = ["Topo da barra lateral", "Abaixo do menu"]


def arquivo_logo_instituicao() -> Path | None:
    """Arquivo da logo da instituição em assets/ (enviado pelas Configurações ou colocado no repositório)."""
    for ext in LOGO_INST_EXTS:
        p = ROOT / "assets" / f"logo_instituicao.{ext}"
        if p.exists():
            return p
    return None


def _gravar_logo_instituicao(dados: bytes, ext: str) -> None:
    for e in LOGO_INST_EXTS:
        (ROOT / "assets" / f"logo_instituicao.{e}").unlink(missing_ok=True)
    if dados:
        (ROOT / "assets").mkdir(exist_ok=True)
        (ROOT / "assets" / f"logo_instituicao.{ext}").write_bytes(dados)


def validar_logo(dados: bytes, nome: str) -> str:
    """Devolve a extensão normalizada ou levanta ValueError com a explicação."""
    ext = nome.rsplit(".", 1)[-1].lower().replace("jpeg", "jpg")
    if ext not in LOGO_INST_EXTS:
        raise ValueError("Use um arquivo PNG, JPG ou SVG.")
    if len(dados) > 1_000_000:
        raise ValueError("O arquivo passa de 1 MB. Use uma versão menor da logo.")
    if ext == "svg":
        if b"<svg" not in dados[:2000]:
            raise ValueError("O arquivo não parece ser um SVG válido.")
    else:
        from PIL import Image

        try:
            Image.open(io.BytesIO(dados)).verify()
        except Exception as e:
            raise ValueError("Não foi possível ler a imagem.") from e
    return ext


def definir_logo_instituicao(dados: bytes, ext: str) -> None:
    cfg = carregar()
    cfg.update(logo_inst_dados=base64.b64encode(dados).decode() if dados else "", logo_inst_ext=ext if dados else "")
    salvar(cfg)
    _gravar_logo_instituicao(dados, ext)


def aplicar(cfg: dict | None = None) -> dict:
    """Chamado a cada execução: garante tema e logos salvos e injeta o plano de fundo."""
    cfg = cfg or carregar()
    gerar_logos(cfg)
    aplicar_tema(cfg)  # o Streamlit relê o config.toml e aplica o tema sozinho
    # o banco é a fonte: recria o arquivo se o servidor reiniciou (ex.: Streamlit Cloud)
    if cfg.get("logo_inst_dados") and not (ROOT / "assets" / f"logo_instituicao.{cfg['logo_inst_ext']}").exists():
        _gravar_logo_instituicao(base64.b64decode(cfg["logo_inst_dados"]), cfg["logo_inst_ext"])
    inst = arquivo_logo_instituicao()
    if inst and cfg.get("logo_inst_posicao") == "Topo da barra lateral":
        st.logo(str(inst), icon_image=str(inst), size="large")
    else:
        st.logo(str(LOGO), icon_image=str(LOGO_ICONE), size="large")
    css = css_fundo(cfg)
    if css:
        st.html(css)
    st.session_state["_cfg"] = cfg
    return cfg


def atual() -> dict:
    return st.session_state.get("_cfg") or dict(PADRAO)
