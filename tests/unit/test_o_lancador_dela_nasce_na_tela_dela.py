"""O atalho DELA abre na tela DELA — o avesso do TELA-DELA-02, e o par dele.

06/09/2026, e o defeito foi vivo: *"a versão .desktop dele atual não abre"*.
Ela clicou o atalho às 01:48 e às 01:49; o `ps` mostrava os dois processos
vivos, cada um com um `Xvfb` filho e o `WebKitWebProcess` pintando as dez
abas. **A janela existia. A tela dela é que não recebia nada.**

A causa é a guarda TELA-DELA-02 (`utils/tela_de_mentira.py`), acrescentada em
04/09 ao topo de `scripts/abrir_interface.py` sob a premissa — escrita ali em
comentário — de que *"o produto que ela usa é o lançador instalado, e não passa
por aqui"*. O `Exec=` do `.desktop` aponta para `interface.sh`, que chama
`run.sh --gui`, que chama aquele script. A premissa era falsa, e a guarda
engoliu o produto por dois dias.

POR QUE UMA RÉGUA E NÃO SÓ A CURA: a guarda existe para proteger a tela dela e
vai continuar crescendo (24 instrumentos hoje). O risco não é ela estar errada
— é ela alcançar o lançador de novo, sem ninguém ver, porque o sintoma é a
AUSÊNCIA de janela. Esta régua fecha os dois lados: o caminho do atalho até o
piloto, e o escape declarado no ponto certo dele.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LANCADOR = RAIZ / "interface.sh"
MOTOR = RAIZ / "run.sh"
ATALHO = RAIZ / "packaging" / "hefesto-dualsense4unix.desktop"


def _exec_do_atalho() -> str:
    for linha in ATALHO.read_text(encoding="utf-8").splitlines():
        if linha.startswith("Exec="):
            return linha[len("Exec=") :]
    raise AssertionError(f"{ATALHO} não tem linha `Exec=`")


def test_o_atalho_aponta_para_o_lancador() -> None:
    """O elo 1 de 3. Se o `Exec=` mudar de alvo, o resto desta régua mente."""
    assert "interface.sh" in _exec_do_atalho(), (
        "o `Exec=` do .desktop não aponta mais para `interface.sh` — esta régua "
        "mede o caminho errado, e o novo alvo precisa declarar a tela dele:\n  "
        + _exec_do_atalho()
    )


def test_o_lancador_chama_o_motor_com_gui() -> None:
    """O elo 2 de 3."""
    fonte = LANCADOR.read_text(encoding="utf-8")
    assert re.search(r'^exec "\$MOTOR" --gui', fonte, re.M), (
        "`interface.sh` não chama mais `run.sh --gui` — reveja o caminho inteiro"
    )
    chamada = r'^\s*exec python3 "\$\{HERE\}/scripts/abrir_interface\.py"'
    assert re.search(chamada, MOTOR.read_text(encoding="utf-8"), re.M), (
        "`run.sh --gui` não chama mais `scripts/abrir_interface.py`"
    )


def test_o_lancador_dela_declara_a_tela() -> None:
    """O elo 3 de 3, e é ELE que quebrou: o escape, no arquivo que ela clica.

    A forma `${HEFESTO_NA_TELA:-1}` é de propósito: quem quiser rodar o
    lançador sem tela (uma bancada, um agente) declara `HEFESTO_NA_TELA=0` e
    a guarda volta a desviar. O padrão é a tela dela, porque o padrão é ela
    clicando.
    """
    fonte = LANCADOR.read_text(encoding="utf-8")
    linhas = [
        linha
        for linha in fonte.splitlines()
        if "HEFESTO_NA_TELA" in linha and not linha.lstrip().startswith("#")
    ]
    assert linhas, (
        "`interface.sh` não declara `HEFESTO_NA_TELA` — o atalho dela atravessa "
        "a guarda TELA-DELA-02 e a janela nasce num `Xvfb` que ela não vê. "
        "Ponha antes do `exec`:\n"
        '    export HEFESTO_NA_TELA="${HEFESTO_NA_TELA:-1}"'
    )
    assert any("export" in linha for linha in linhas), (
        "a declaração tem de ser `export` — o piloto é outro processo:\n  "
        + "\n  ".join(linhas)
    )
    assert any('${HEFESTO_NA_TELA:-1}' in linha for linha in linhas), (
        "declare com padrão, não na marra: `${HEFESTO_NA_TELA:-1}` deixa a "
        "bancada desligar com `HEFESTO_NA_TELA=0`:\n  " + "\n  ".join(linhas)
    )


def test_a_guarda_honra_o_escape_declarado() -> None:
    """A cura vale porque a guarda respeita o escape. Sem isto, é fé."""
    import os

    from hefesto_dualsense4unix.utils import tela_de_mentira as tm

    fonte = Path(tm.__file__ or "").read_text(encoding="utf-8")
    assert 'os.environ.get("HEFESTO_NA_TELA") == "1"' in fonte, (
        "a guarda deixou de ler `HEFESTO_NA_TELA` — o escape do lançador virou "
        "letra morta e o atalho dela volta a abrir no vazio"
    )
    antes = os.environ.get("HEFESTO_NA_TELA")
    antes_display = os.environ.get("DISPLAY")
    os.environ["HEFESTO_NA_TELA"] = "1"
    try:
        # `_JA_FEITO` já é True sob a suíte (TELA-DELA-01), então o que se mede
        # aqui é o que se pode medir sem subir tela: a guarda não troca o
        # DISPLAY de quem declarou.
        tm.garantir_tela_de_mentira(anunciar=False)
        assert os.environ.get("DISPLAY") == antes_display
    finally:
        if antes is None:
            os.environ.pop("HEFESTO_NA_TELA", None)
        else:
            os.environ["HEFESTO_NA_TELA"] = antes
