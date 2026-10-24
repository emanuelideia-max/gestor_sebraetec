"""Os testes usam um banco SQLite temporário, semeado com a planilha da pasta."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["GESTOR_TEMA_FIXO"] = "1"
os.environ["GESTOR_DB"] = str(Path(tempfile.mkdtemp()) / "teste.db")
sys.path.insert(0, str(ROOT))

from core import data, importer  # noqa: E402

data.bootstrap()
planilhas = sorted(ROOT.glob("*.xlsx"))
if planilhas:
    importer.importar(importer.ler_planilha(planilhas[0])[0])
