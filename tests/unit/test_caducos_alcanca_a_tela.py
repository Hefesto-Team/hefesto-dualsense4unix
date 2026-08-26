"""O portão de caducos tem de alcançar a TELA — e não pode se desarmar sozinho.

DOIS DEFEITOS MEDIDOS EM 26/08/2026 (LEVA-4-E), no mesmo arquivo:

1. **O `.glade` ficava de fora.** `RAIZES_VIVAS` já incluía `src`, mas
   `EXTENSOES` era ``{".md", ".py", ".html", ".rst", ".txt"}`` — e o
   `src/hefesto_dualsense4unix/gui/main.glade` é a superfície MAIS viva que
   existe nesta casa: um fato declarado caduco escrito num
   ``<property name="label">`` chega à tela dela com o portão VERDE. O mesmo
   valia para `po/*.po`, que é essa frase traduzida.

2. **O portão se desarmava sozinho.** `mv docs/data/caducos.csv /tmp/` fazia
   ele imprimir ``OK`` e sair ``rc=0``. Fonte ausente virava selo verde — que
   é o inverso do que o `scripts/portoes.sh` faz para portão ausente.
"""
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

#: O molde do `main.glade` reduzido ao que importa: um rótulo que vira pixel.
GLADE_COM_O_LITERAL = """<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <object class="GtkLabel" id="rotulo_do_microfone">
    <property name="label">O mudo entrega literal-caduco-de-teste do sinal</property>
  </object>
</interface>
"""

GLADE_LIMPO = """<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <object class="GtkLabel" id="rotulo_do_microfone">
    <property name="label">O microfone está mudo</property>
  </object>
</interface>
"""

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
    (tmp_path / "src" / "hefesto_dualsense4unix" / "gui").mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / "po").mkdir(parents=True, exist_ok=True)
    return tmp_path


def rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), "--all"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_fato_caduco_no_glade_reprova(tmp_path: Path) -> None:
    """MORDIDA — o rótulo do Glade é o texto que ela LÊ na tela."""
    raiz = monta_arvore(tmp_path)
    glade = raiz / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
    glade.write_text(GLADE_COM_O_LITERAL, encoding="utf-8")

    processo = rodar(raiz)

    assert processo.returncode == 1, (
        "um fato declarado caduco chegou à TELA com o portão verde:\n"
        + processo.stdout
    )
    assert "main.glade" in processo.stdout
    assert "chave.de.teste@dualsense" in processo.stdout
    assert "2026-08-07" in processo.stdout


def test_glade_limpo_continua_verde(tmp_path: Path) -> None:
    """Régua que só sabe reprovar não é régua."""
    raiz = monta_arvore(tmp_path)
    (raiz / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade").write_text(
        GLADE_LIMPO, encoding="utf-8"
    )
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


def test_o_arquivo_real_do_glade_esta_no_alcance() -> None:
    """A régua tem de olhar para o Glade DESTE repositório, não só para o dublê.

    Sem esta linha, os testes acima provariam apenas que o mecanismo funciona
    numa árvore de mentira — e foi assim que um portão desta casa passou uma
    leva inteira olhando para a árvore errada.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("vc", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["vc"] = modulo
    spec.loader.exec_module(modulo)

    glade = RAIZ_REAL / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
    assert glade.is_file(), "o main.glade sumiu do lugar — acerte este teste"
    assert glade in modulo._arquivos_vivos(RAIZ_REAL), (
        "o main.glade não está entre os arquivos vivos que o portão varre"
    )
