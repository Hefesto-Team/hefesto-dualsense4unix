"""O portão de caducos tem de alcançar a TELA — e não pode se desarmar sozinho."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "validar-caducos.py"

CADUCOS_CSV = (
    "id,o_que_caducou,caducou_em,substituto,onde_pode_ficar\n"
    'chave.de.teste@dualsense,"literal-caduco-de-teste — número obtido com '
    'instrumento quebrado",2026-08-07,,"docs/process/**"\n'
)

PAGINA_COM_O_LITERAL = """<!doctype html>
<section class="card">
  <p data-campo="som.mic.estado">O mudo entrega literal-caduco-de-teste do sinal</p>
</section>
"""

PAGINA_LIMPA = """<!doctype html>
<section class="card">
  <p data-campo="som.mic.estado">O microfone está mudo</p>
</section>
"""

PAGINA_RELATIVA = (
    "src",
    "hefesto_dualsense4unix",
    "interface",
    "paginas",  # noqa-acento (nome de pasta)
    "09-sistema.html",
)

PO_COM_O_LITERAL = (
    'msgid "the mute delivers a fraction of the signal"\n'
    'msgstr "O mudo entrega literal-caduco-de-teste do sinal"\n'
)


def monta_arvore(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "data" / "caducos.csv").write_text(
        CADUCOS_CSV, encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("# README\n\nLimpo.\n", encoding="utf-8")
    (tmp_path.joinpath(*PAGINA_RELATIVA).parent).mkdir(parents=True, exist_ok=True)
    (tmp_path / "po").mkdir(parents=True, exist_ok=True)
    return tmp_path


def rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), "--all"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_fato_caduco_na_pagina_publicada_reprova(tmp_path: Path) -> None:
    """MORDIDA — o texto da página publicada é o que ela LÊ na tela."""
    raiz = monta_arvore(tmp_path)
    raiz.joinpath(*PAGINA_RELATIVA).write_text(
        PAGINA_COM_O_LITERAL, encoding="utf-8"
    )

    processo = rodar(raiz)

    assert processo.returncode == 1, (
        "um fato declarado caduco chegou à TELA com o portão verde:\n"
        + processo.stdout
    )
    assert "09-sistema.html" in processo.stdout
    assert "chave.de.teste@dualsense" in processo.stdout
    assert "2026-08-07" in processo.stdout


def test_pagina_limpa_continua_verde(tmp_path: Path) -> None:
    """Régua que só sabe reprovar não é régua."""
    raiz = monta_arvore(tmp_path)
    raiz.joinpath(*PAGINA_RELATIVA).write_text(PAGINA_LIMPA, encoding="utf-8")
    processo = rodar(raiz)
    assert processo.returncode == 0, processo.stdout


def test_fato_caduco_na_traducao_reprova(tmp_path: Path) -> None:
    """MORDIDA — `po/` é a mesma frase, para quem não lê a língua original."""
    raiz = monta_arvore(tmp_path)
    (raiz / "po" / "pt_BR.po").write_text(PO_COM_O_LITERAL, encoding="utf-8")

    processo = rodar(raiz)

    assert processo.returncode == 1, processo.stdout
    assert "pt_BR.po" in processo.stdout


def test_ledger_ausente_nao_e_verde(tmp_path: Path) -> None:
    """MORDIDA — sem o livro-caixa o portão está CEGO, e cego não é limpo."""
    raiz = monta_arvore(tmp_path)
    (raiz / "docs" / "data" / "caducos.csv").unlink()

    processo = rodar(raiz)

    assert processo.returncode == 1, (
        "o portão ficou verde sem a própria fonte no disco:\n" + processo.stdout
    )
    assert "caducos.csv" in processo.stdout
    assert "FALHA" in processo.stdout


def test_ledger_vazio_diz_que_nao_mediu(tmp_path: Path) -> None:
    """Ledger presente e sem linha é honesto — mas não se chama `OK`."""
    raiz = monta_arvore(tmp_path)
    (raiz / "docs" / "data" / "caducos.csv").write_text(
        "id,o_que_caducou,caducou_em,substituto,onde_pode_ficar\n", encoding="utf-8"
    )
    processo = rodar(raiz)
    assert processo.returncode == 0, processo.stdout
    assert "NÃO MEDIU NADA" in processo.stdout


def test_as_dez_paginas_reais_estao_no_alcance() -> None:
    """A régua tem de olhar para a tela DESTE repositório, não só para o dublê."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("vc", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["vc"] = modulo
    spec.loader.exec_module(modulo)

    pasta = (
        RAIZ_REAL / "src" / "hefesto_dualsense4unix"
        / "interface" / "paginas"  # noqa-acento (nome de pasta)
    )
    paginas = sorted(pasta.glob("[0-9][0-9]-*.html"))
    assert len(paginas) >= 10, (
        f"achei {len(paginas)} páginas publicadas em {pasta} — o caminho mudou?"
    )
    vivos = modulo._arquivos_vivos(RAIZ_REAL)
    faltando = [p.name for p in paginas if p not in vivos]
    assert not faltando, (
        f"as páginas {faltando} não estão entre os arquivos vivos que o portão "
        "varre — um fato caduco escrito nelas chegaria à tela dela em silêncio"
    )
