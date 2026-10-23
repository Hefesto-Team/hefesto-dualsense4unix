"""O atalho DO USUÁRIO abre na tela do usuário — o avesso do TELA-DELA-02, e o par dele."""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
MOTOR = RAIZ / "run.sh"
ATALHO = RAIZ / "packaging" / "hefesto-dualsense4unix.desktop"
INSTALADOR = RAIZ / "install.sh"


def _abre_com_tela(linha: str) -> bool:
    """`env [VAR=…]… HEFESTO_NA_TELA=1 [VAR=…]… …/run.sh --gui`, lido palavra por palavra.

    A regex de `(?:\\S+=\\S+\\s+)*` volta atrás sem fim numa linha cheia de `=`; a lista de palavras
    anda uma vez só.
    """
    palavras = linha.split()
    if palavras[:1] != ["env"]:
        return False
    fim = 1
    while fim < len(palavras) and "=" in palavras[fim][1:-1]:
        fim += 1
    return (
        "HEFESTO_NA_TELA=1" in palavras[1:fim]
        and fim + 1 < len(palavras)
        and palavras[fim].endswith("/run.sh")
        and re.match(r"--gui\b", palavras[fim + 1]) is not None
    )


def _exec_do_atalho() -> str:
    for linha in ATALHO.read_text(encoding="utf-8").splitlines():
        if linha.startswith("Exec="):
            return linha[len("Exec=") :]
    raise AssertionError(f"{ATALHO} não tem linha `Exec=`")


def _linhas_de_exec_do_instalador() -> list[str]:
    """Os `_EXEC_LINE=` do `install.sh` — é ELE que escreve o `Exec=` instalado."""
    achadas = re.findall(
        r'^\s*_EXEC_LINE="([^"]*)"', INSTALADOR.read_text(encoding="utf-8"), re.M
    )
    assert achadas, "o `install.sh` não monta mais `_EXEC_LINE` — releia a régua"
    return [a.replace("${ROOT_DIR}", "/raiz") for a in achadas]


def _lancador_do_instalador() -> str:
    """A linha do lançador de `~/.local/bin` que o `install.sh` escreve."""
    fonte = INSTALADOR.read_text(encoding="utf-8")
    corpo = re.search(
        r'^cat > "\$\{LAUNCHER\}" <<LAUNCH\n(.*?)^LAUNCH$', fonte, re.M | re.S
    )
    assert corpo, "o `install.sh` não escreve mais o lançador com `<<LAUNCH`"
    linhas = [
        linha
        for linha in corpo.group(1).splitlines()
        if "setsid" in linha and not linha.lstrip().startswith("#")
    ]
    assert len(linhas) == 1, f"esperava uma linha com `setsid`, achei {linhas}"
    return linhas[0]


def _linhas_vivas(fonte: str) -> list[str]:
    return [linha for linha in fonte.splitlines() if not linha.lstrip().startswith("#")]


def test_o_atalho_versionado_abre_o_motor_com_a_tela() -> None:
    """O elo 1: o `.desktop` versionado chama `run.sh --gui` declarando a tela."""
    exec_ = _exec_do_atalho()
    assert _abre_com_tela(exec_), (
        "o `Exec=` do .desktop não abre `run.sh --gui` com `HEFESTO_NA_TELA=1` — "
        "sem a variável, o atalho dela atravessa a guarda TELA-DELA-02 e a "
        "janela nasce num `Xvfb` que ela não vê:\n  " + exec_
    )


def test_o_atalho_instalado_abre_o_motor_com_a_tela() -> None:
    """O elo 1, do lado de quem instala: as duas formas do `Exec=` (com e sem"""
    for linha in _linhas_de_exec_do_instalador():
        assert _abre_com_tela(linha), (
            "o `install.sh` escreve um `Exec=` sem `HEFESTO_NA_TELA=1` (ou que "
            "não chama `run.sh --gui`):\n  " + linha
        )


def test_o_lancador_do_tray_declara_a_tela() -> None:
    """O «Abrir programa» do tray chama o lançador de `~/.local/bin`."""
    linha = _lancador_do_instalador()
    assert re.match(
        r'^HEFESTO_NA_TELA="\\\$\{HEFESTO_NA_TELA:-1\}"\s+setsid\s+nohup\s+'
        r'"\$\{ROOT_DIR\}/run\.sh"\s+--gui\b',
        linha,
    ), (
        "o lançador de `~/.local/bin` não chama `run.sh --gui` declarando "
        '`HEFESTO_NA_TELA="${HEFESTO_NA_TELA:-1}"` na frente do `setsid`:\n  '
        + linha
    )


def test_o_motor_chama_o_envoltorio() -> None:
    """O elo 2: `run.sh --gui` entrega ao `scripts/abrir_interface.py`."""
    chamada = r'^\s*exec python3 "\$\{HERE\}/scripts/abrir_interface\.py"'
    assert re.search(chamada, MOTOR.read_text(encoding="utf-8"), re.M), (
        "`run.sh --gui` não chama mais `scripts/abrir_interface.py`"
    )


def test_o_motor_nao_declara_a_tela() -> None:
    """A outra metade: `run.sh` é o que os instrumentos chamam."""
    vivas = [
        linha
        for linha in _linhas_vivas(MOTOR.read_text(encoding="utf-8"))
        if "HEFESTO_NA_TELA" in linha
    ]
    assert not vivas, (
        "`run.sh` passou a declarar `HEFESTO_NA_TELA` — todo instrumento que o "
        "chama abre janela na tela dela. A variável viaja com o atalho, não com "
        "o motor:\n  " + "\n  ".join(vivas)
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
        tm.garantir_tela_de_mentira(anunciar=False)
        assert os.environ.get("DISPLAY") == antes_display
    finally:
        if antes is None:
            os.environ.pop("HEFESTO_NA_TELA", None)
        else:
            os.environ["HEFESTO_NA_TELA"] = antes


def test_a_leitura_do_exec_anda_uma_vez_so() -> None:
    """Linha hostil de `=` não trava a régua, e a régua segue reprovando o `Exec=` sem a tela.

    A MORDIDA: devolva a regex `(?:\\S+=\\S+\\s+)*` e a primeira asserção leva minutos.
    """
    import time

    hostil = "env HEFESTO_NA_TELA=1 " + "!==! " * 4000
    comeco = time.monotonic()
    assert not _abre_com_tela(hostil)
    assert time.monotonic() - comeco < 2.0, "a leitura do `Exec=` voltou a voltar atrás"
    assert _abre_com_tela("env A=b HEFESTO_NA_TELA=1 C=d /raiz/run.sh --gui")
    assert not _abre_com_tela("env A=b /raiz/run.sh --gui")
    assert not _abre_com_tela("env HEFESTO_NA_TELA=1 /raiz/run.sh --cli")
