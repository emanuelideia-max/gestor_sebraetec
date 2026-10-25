"""Abre cada página logado (modo local) e verifica que nenhuma lança exceção."""
from streamlit.testing.v1 import AppTest

PAGINAS = ["app_pages/painel.py", "app_pages/consultorias.py", "app_pages/agenda.py", "app_pages/mapa.py",
           "app_pages/analises.py", "app_pages/inteligencia.py", "app_pages/relatorios.py", "app_pages/cadastros.py",
           "app_pages/configuracoes.py"]


def test_paginas_abrem():
    at = AppTest.from_file("../streamlit_app.py", default_timeout=60)
    at.session_state["user_email"] = "teste@local"
    at.run()
    assert not at.exception, at.exception
    for p in PAGINAS:
        at.switch_page(p).run()
        assert not at.exception, (p, at.exception)


def test_pdf():
    from core import data, pdf
    df = data.consultorias_view()
    assert pdf.relatorio_geral(df, pdf.SECOES).startswith(b"%PDF")
    if not df.empty:
        assert pdf.ficha_consultoria(df.iloc[0], data.historico_view()).startswith(b"%PDF")


def test_ficha_e_avanco_de_etapa():
    at = AppTest.from_file("../streamlit_app.py", default_timeout=60)
    at.session_state["user_email"] = "teste@local"
    at.run()
    at.switch_page("app_pages/consultorias.py").run()
    import pytest
    from core import data
    if data.consultorias_view().empty:
        pytest.skip("sem planilha na pasta para semear dados de teste")
    cid = int(data.consultorias_view().iloc[0]["id"])
    at.session_state["consultoria_sel"] = cid
    at.run()
    assert not at.exception, at.exception
    antes = int(data.consultorias_view().set_index("id").loc[cid, "status_id"])
    next(b for b in at.button if b.label == "Avançar etapa").click().run()
    assert not at.exception, at.exception
    data.refresh()
    depois = int(data.consultorias_view().set_index("id").loc[cid, "status_id"])
    assert depois == antes + 1
    next(b for b in at.button if b.label == "Voltar").click().run()
    data.refresh()
    assert int(data.consultorias_view().set_index("id").loc[cid, "status_id"]) == antes


def test_token_de_sessao_local():
    from core import auth
    token = auth._assinar("gestor@exemplo.com")
    assert auth._verificar(token) == "gestor@exemplo.com"
    corpo, sig = token.rsplit(".", 1)
    assert auth._verificar(corpo + "." + "0" * len(sig)) is None  # assinatura adulterada
    assert auth._verificar("lixo") is None


def test_todas_as_secoes_de_dados_e_configuracoes():
    at = AppTest.from_file("../streamlit_app.py", default_timeout=60)
    at.session_state["user_email"] = "teste@local"
    at.run()
    for secao in ["Consultorias", "Clientes", "Fornecedores", "Compromissos", "Lembretes",
                  "Histórico de etapas", "Etapas do fluxo", "Importar planilha", "Exportar"]:
        at.session_state["cad_secao"] = secao
        at.switch_page("app_pages/cadastros.py").run()
        assert not at.exception, (secao, at.exception)
    for secao in ["Aparência", "Alertas", "Identidade", "Sistema"]:
        at.session_state["cfg_secao"] = secao
        at.switch_page("app_pages/configuracoes.py").run()
        assert not at.exception, (secao, at.exception)


def test_tema_gerado_e_valido():
    import tomllib
    from core import config_app
    for modo in ["Seguir o sistema", "Claro", "Escuro"]:
        cfg = {**config_app.PADRAO, "modo": modo}
        tomllib.loads(config_app.gerar_toml(cfg))
        for fundo in config_app.FUNDOS:
            config_app.css_fundo({**cfg, "fundo": fundo})


def test_configuracoes_salvar_e_restaurar():
    from core import config_app, data
    at = AppTest.from_file("../streamlit_app.py", default_timeout=60)
    at.session_state["user_email"] = "teste@local"
    at.run()
    at.switch_page("app_pages/configuracoes.py").run()
    at.session_state["cfg_alerta_prazo_dias"] = 30
    at.run()
    next(b for b in at.button if b.label == "Salvar configurações").click().run()
    assert not at.exception, at.exception
    data.refresh()
    assert config_app.carregar()["alerta_prazo_dias"] == 30
    next(b for b in at.button if b.label == "Restaurar padrão").click().run()
    assert not at.exception, at.exception
    next(b for b in at.button if b.label == "Salvar configurações").click().run()
    data.refresh()
    assert config_app.carregar()["alerta_prazo_dias"] == config_app.PADRAO["alerta_prazo_dias"]


def test_logo_da_instituicao(tmp_path, monkeypatch):
    import io

    import pytest
    from PIL import Image

    from core import config_app, data, pdf

    monkeypatch.setattr(config_app, "ROOT", tmp_path)  # não mexer na pasta assets/ do projeto
    buf = io.BytesIO()
    Image.new("RGB", (300, 100), "#005EB8").save(buf, "PNG")
    png = buf.getvalue()

    with pytest.raises(ValueError):
        config_app.validar_logo(b"nada", "logo.gif")
    with pytest.raises(ValueError):
        config_app.validar_logo(b"isto nao e imagem", "logo.png")
    assert config_app.validar_logo(png, "Logo.PNG") == "png"

    config_app.definir_logo_instituicao(png, "png")
    data.refresh()
    assert config_app.arquivo_logo_instituicao() == tmp_path / "assets" / "logo_instituicao.png"
    assert config_app.carregar()["logo_inst_ext"] == "png"
    assert pdf.relatorio_geral(data.consultorias_view(), pdf.SECOES).startswith(b"%PDF")

    config_app.definir_logo_instituicao(b"", "")
    data.refresh()
    assert config_app.arquivo_logo_instituicao() is None
    assert config_app.carregar()["logo_inst_dados"] == ""
