"""Login: Supabase Auth (e-mail e senha) ou usuário local definido em secrets.toml.

A sessão sobrevive a recarregar a página por meio de um cookie:
- Supabase: guarda o refresh token (validado pelo próprio Supabase e renovado a cada uso).
- Local: guarda um token assinado com HMAC (e-mail + validade).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

import streamlit as st

from core.db import ROOT, supabase_config

COOKIE = "gestor_sebraetec_sessao"
DIAS_SESSAO = 7


def is_logged_in() -> bool:
    return bool(st.session_state.get("user_email"))


# ---------------------------------------------------------------- cookie

def _segredo_local() -> bytes:
    try:
        cfg = st.secrets.get("auth", {})
    except FileNotFoundError:
        cfg = {}
    if cfg.get("cookie_secret"):
        return str(cfg["cookie_secret"]).encode()
    arquivo = ROOT / "data" / ".cookie_secret"
    if not arquivo.exists():
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(secrets.token_hex(32))
    return arquivo.read_text().strip().encode()


def _assinar(email: str) -> str:
    corpo = base64.urlsafe_b64encode(
        json.dumps({"e": email, "x": int(time.time()) + DIAS_SESSAO * 86400}).encode()
    ).decode()
    sig = hmac.new(_segredo_local(), corpo.encode(), hashlib.sha256).hexdigest()
    return f"{corpo}.{sig}"


def _verificar(token: str) -> str | None:
    try:
        corpo, sig = token.rsplit(".", 1)
        esperado = hmac.new(_segredo_local(), corpo.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, esperado):
            return None
        dados = json.loads(base64.urlsafe_b64decode(corpo))
        return dados["e"] if dados["x"] > time.time() else None
    except Exception:
        return None


def _agendar_cookie(valor: str | None) -> None:
    """O cookie é gravado pelo navegador na próxima execução (ver `aplicar_cookie`)."""
    st.session_state["_cookie_pendente"] = valor


def aplicar_cookie() -> None:
    """Grava ou apaga o cookie de sessão no navegador, se houver mudança pendente."""
    if "_cookie_pendente" not in st.session_state:
        return
    valor = st.session_state.pop("_cookie_pendente")
    seguro = "; Secure" if st.context.url.startswith("https") else ""
    if valor:
        js = f"document.cookie = '{COOKIE}={valor}; max-age={DIAS_SESSAO * 86400}; path=/; SameSite=Strict{seguro}';"
    else:
        js = f"document.cookie = '{COOKIE}=; max-age=0; path=/; SameSite=Strict{seguro}';"
    # o valor é gerado pelo próprio app (token base64/hex), nunca digitado pelo usuário
    st.html(f"<script>{js}</script>", unsafe_allow_javascript=True)


def login_liberado() -> bool:
    """`[auth] login_liberado = true` no secrets.toml pula a tela de login (só para testes, modo local)."""
    try:
        return bool(st.secrets.get("auth", {}).get("login_liberado")) and not supabase_config()
    except FileNotFoundError:
        return False


def restaurar_sessao() -> None:
    """Se houver cookie válido, entra sem pedir senha."""
    if not is_logged_in() and login_liberado():
        st.session_state.user_email = "teste@local"
        return
    if is_logged_in() or st.session_state.get("_sem_restaurar"):
        return
    token = st.context.cookies.get(COOKIE)
    if not token:
        return
    if supabase_config():
        from supabase import create_client

        cfg = supabase_config()
        client = create_client(cfg["url"], cfg["key"])
        try:
            res = client.auth.refresh_session(token)
        except Exception:
            _agendar_cookie(None)
            return
        st.session_state.sb_client = client
        st.session_state.user_email = res.user.email
        _agendar_cookie(res.session.refresh_token)  # o Supabase troca o refresh token a cada uso
    else:
        email = _verificar(token)
        if email:
            st.session_state.user_email = email
        else:
            _agendar_cookie(None)


# ---------------------------------------------------------------- login / logout

def _login_supabase(email: str, senha: str) -> tuple[str, str] | None:
    from supabase import create_client

    cfg = supabase_config()
    client = create_client(cfg["url"], cfg["key"])
    try:
        res = client.auth.sign_in_with_password({"email": email, "password": senha})
    except Exception:
        return None
    st.session_state.sb_client = client
    return res.user.email, res.session.refresh_token


def _login_local(email: str, senha: str) -> tuple[str, str] | None:
    try:
        users = st.secrets.get("local_users", {})
    except FileNotFoundError:
        users = {}
    email = email.strip().lower()
    expected = users.get(email)
    if expected and hmac.compare_digest(str(expected), senha):
        return email, _assinar(email)
    return None


def login_form() -> None:
    aplicar_cookie()  # apaga o cookie depois de "Sair"
    with st.container(horizontal_alignment="center"):
        with st.container(width=380):
            st.space("large")
            st.image(str(ROOT / "assets" / "logo.svg"), width=260)
            st.caption("Acompanhamento de consultorias")
            with st.form("login", border=True):
                email = st.text_input("E-mail", autocomplete="username")
                senha = st.text_input("Senha", type="password", autocomplete="current-password")
                manter = st.checkbox("Manter conectado neste aparelho", value=True)
                entrar = st.form_submit_button("Entrar", type="primary", width="stretch")
            if entrar:
                fn = _login_supabase if supabase_config() else _login_local
                res = fn(email, senha) if email and senha else None
                if res:
                    st.session_state.user_email, token = res
                    st.session_state.pop("_sem_restaurar", None)
                    if manter:
                        _agendar_cookie(token)
                    st.rerun()
                else:
                    st.error("E-mail ou senha inválidos.")
            if not supabase_config():
                st.caption(":material/info: Modo local (sem Supabase configurado).")


def logout() -> None:
    client = st.session_state.pop("sb_client", None)
    if client is not None:
        try:
            client.auth.sign_out()
        except Exception:
            pass
    st.session_state.pop("user_email", None)
    st.session_state["_sem_restaurar"] = True  # não reentrar com o cookie antigo nesta aba
    _agendar_cookie(None)
    st.rerun()
