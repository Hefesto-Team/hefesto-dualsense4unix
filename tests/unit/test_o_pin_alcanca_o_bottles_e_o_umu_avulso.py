"""O pin alcança o Bottles e o umu avulso (O-PIN-ALCANCA-O-BOTTLES-E-O-UMU-AVULSO-01).

D-3010-O-PIN-DO-PROTON-VALE-PARA-TODO-JOGO: a garrafa do Bottles pelo Proton vai ao pino, extraído
na ``runners/`` da casa; a que roda pelo Wine fica e é dita; o atalho do umu avulso não tem
configuração a fixar e é dito. A casa, a Steam, o Bottles e os atalhos são de mentira.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.integrations import proton_pin as pp
from tests.unit import test_o_pin_do_proton_alcanca_todo_jogo as irmao
from tests.unit.test_o_pino_chega_a_qualquer_computador import (
    PINO,
    _pino_na,
    _steam_de_verdade,
    trava_da_rede,  # noqa: F401
)
from tests.unit.test_o_proton_novo_so_entra_se_passar import _proton_de_mentira

lar = irmao.lar
conf = irmao.conf
_apontar = irmao._apontar
NATIVO = ".local/share/bottles"
FLATPAK = ".var/app/com.usebottles.bottles/data/bottles"
VELHO = "GE-Proton9-20"
SODA = "soda-7.0-9"


def _runners(casa: Path) -> Path:
    _proton_de_mentira(casa / "runners" / VELHO)
    (casa / "runners" / SODA / "bin").mkdir(parents=True)
    (casa / "runners" / SODA / "bin" / "wine").write_text("#!/bin/sh\n", encoding="utf-8")
    return casa / "runners"


def _garrafa(casa: Path, pasta: str, runner: str, nome: str = "") -> Path:
    arquivo = casa / "bottles" / pasta / "bottle.yml"
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text(
        "Arch: win64\nDXVK: dxvk-2.3\nEnvironment: Gaming\n"
        f"Name: {nome or pasta}\nPath: {pasta}\nRunner: {runner}\nWindows: win10\n",
        encoding="utf-8")
    return arquivo


def _runner(arquivo: Path) -> str:
    return next(linha.split(":", 1)[1].strip()
                for linha in arquivo.read_text(encoding="utf-8").splitlines()
                if linha.startswith("Runner:"))


@pytest.mark.parametrize("rel", [NATIVO, FLATPAK], ids=["nativo", "flatpak"])
def test_a_garrafa_pelo_proton_vai_ao_pino_na_runners_da_casa(
        lar: Path, conf: dict[str, str], rel: str) -> None:
    """Mordida: sem o laço do Bottles no dono único, a garrafa fica no Proton velho."""
    _pino_na(_steam_de_verdade(lar))
    casa = lar / rel
    runners = _runners(casa)
    arquivo = _garrafa(casa, "Jogo-Velho", VELHO, "Jogo Velho")
    antes = arquivo.read_text(encoding="utf-8")

    feito = _apontar(lar, conf)

    assert _runner(arquivo) == PINO
    assert pp.pinned_proton_installed(PINO, runners), "o pino não chegou à runners/ da casa"
    assert arquivo.read_text(encoding="utf-8") == antes.replace(f"Runner: {VELHO}",
                                                               f"Runner: {PINO}")
    assert feito.reescritas == 1 and feito.fora == ()
    assert list(arquivo.parent.glob("bottle.yml.bak.hefesto-proton-*"))
    assert "Bottles" in pp.quem_usa_o_proton(lar)


def test_a_garrafa_pelo_wine_fica_e_e_dita_sem_extrair_o_pino(
        lar: Path, conf: dict[str, str]) -> None:
    """Mordida: o runner Wine tratado como Proton troca o runner e estraga o prefixo."""
    _pino_na(_steam_de_verdade(lar))
    casa = lar / NATIVO
    runners = _runners(casa)
    arquivo = _garrafa(casa, "Pelo-Wine", SODA, "Um Programa")
    sistema = _garrafa(casa, "Do-Sistema", "sys-wine-9.0")
    antes = (arquivo.read_bytes(), sistema.read_bytes())

    feito = _apontar(lar, conf)

    assert (arquivo.read_bytes(), sistema.read_bytes()) == antes
    assert feito.reescritas == 0
    assert feito.fora == (censo.ForaDoPino("bottles", "Do-Sistema", censo.PORQUE_PELO_WINE),
                          censo.ForaDoPino("bottles", "Um Programa", censo.PORQUE_PELO_WINE))
    assert not pp.pinned_proton_installed(PINO, runners), (
        "a casa só com garrafa do Wine ganhou o Proton inteiro no disco")


def test_o_segundo_lancadores_nao_reescreve_nada(
        lar: Path, conf: dict[str, str], tmp_path: Path) -> None:
    """Mordida: comparar o runner sem o nome do pino reescreve a garrafa a cada volta."""
    casa = lar / FLATPAK
    _runners(casa)
    arquivo = _garrafa(casa, "Jogo-Velho", VELHO)
    arquivo_conf = tmp_path / "proton-pin.conf"
    arquivo_conf.write_text("".join(f"{k}={v}\n" for k, v in conf.items()), encoding="utf-8")
    argv = ["--lancadores", "--conf", str(arquivo_conf)]

    assert pp.main(argv) == 0
    depois_da_primeira = arquivo.read_bytes(), arquivo.stat().st_ino
    copias = sorted(arquivo.parent.glob("bottle.yml.bak.*"))
    assert _runner(arquivo) == PINO

    assert pp.main(argv) == 0
    assert (arquivo.read_bytes(), arquivo.stat().st_ino) == depois_da_primeira
    assert sorted(arquivo.parent.glob("bottle.yml.bak.*")) == copias
    assert _apontar(lar, conf).reescritas == 0


def test_o_bottles_aberto_nao_e_escrito_e_e_dito(
        lar: Path, conf: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Mordida: escrever com o Bottles aberto perde a troca quando ele regrava a garrafa."""
    _pino_na(_steam_de_verdade(lar))
    casa = lar / NATIVO
    _runners(casa)
    arquivo = _garrafa(casa, "Jogo-Velho", VELHO)
    antes = arquivo.read_bytes()
    monkeypatch.setattr(censo, "bottles_aberto", lambda: True)

    feito = _apontar(lar, conf)

    assert arquivo.read_bytes() == antes and feito.reescritas == 0
    assert feito.fora == (censo.ForaDoPino("bottles", "", censo.PORQUE_BOTTLES_ABERTO),
                          censo.ForaDoPino("bottles", "Jogo-Velho", censo.PORQUE_AINDA_NAO))


def test_so_medir_nao_escreve_nem_extrai(lar: Path, conf: dict[str, str]) -> None:
    casa = lar / NATIVO
    runners = _runners(casa)
    arquivo = _garrafa(casa, "Jogo-Velho", VELHO)
    _garrafa(casa, "Pelo-Wine", SODA)
    antes = arquivo.read_bytes()

    medida = _apontar(lar, conf, escrever=False)

    assert arquivo.read_bytes() == antes
    assert not pp.pinned_proton_installed(PINO, runners)
    assert medida.fora == (censo.ForaDoPino("bottles", "", censo.PORQUE_SEM_O_PINO),
                           censo.ForaDoPino("bottles", "Pelo-Wine", censo.PORQUE_PELO_WINE))


def test_o_runner_entre_aspas_e_o_runner_que_saiu_do_disco(
        lar: Path, conf: dict[str, str]) -> None:
    """O ``bottle.yml`` com aspas e a garrafa cujo runner Proton já saiu da ``runners/``."""
    casa = lar / NATIVO
    _runners(casa)
    aspas = _garrafa(casa, "Aspas", f"'{VELHO}'", "'Com Aspas'")
    sumiu = _garrafa(casa, "Sumiu", "GE-Proton8-1")
    wine_ge = _garrafa(casa, "Wine-GE", "wine-ge-proton8-26")
    antes = wine_ge.read_bytes()
    quebrada = casa / "bottles" / "Quebrada" / "bottle.yml"
    quebrada.parent.mkdir(parents=True)
    quebrada.write_text("Name: Quebrada\nArch: win64\n", encoding="utf-8")

    feito = _apontar(lar, conf)

    assert _runner(aspas) == PINO and _runner(sumiu) == PINO
    assert wine_ge.read_bytes() == antes, "o Wine-GE que saiu do disco virou Proton"
    assert feito.reescritas == 2
    assert feito.fora == (censo.ForaDoPino("bottles", "Quebrada", censo.PORQUE_ILEGIVEL),
                          censo.ForaDoPino("bottles", "Wine-GE", censo.PORQUE_PELO_WINE))


@pytest.mark.parametrize(("argv", "aberto"), [
    (["/usr/bin/bottles"], True),
    (["/usr/bin/python3", "/app/bin/bottles"], True),
    (["/usr/bin/python3", "-sP", "/usr/bin/bottles", "--no-update"], True),
    (["vim", "bottles"], False),
    (["/usr/bin/python3", "-m", "http.server", "bottles"], False),
    (["/usr/bin/bottles-cli", "list"], False),
], ids=["nativo", "script", "script-com-opcao", "outro-programa", "outro-script", "a-cli"])
def test_o_bottles_aberto_e_o_processo_do_bottles(
        tmp_path: Path, argv: list[str], aberto: bool) -> None:
    """Mordida: casar ``bottles`` em qualquer argumento trava o pin com um editor na pasta."""
    proc = tmp_path / "proc"
    (proc / "self").mkdir(parents=True)
    (proc / "41").mkdir()
    (proc / "41" / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    assert censo.bottles_aberto(proc) is aberto


def _atalho(pasta: Path, nome: str, exec_: str, *extra: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / f"{nome}.desktop").write_text(
        "\n".join(("[Desktop Entry]", "Type=Application", f"Name={nome.title()}",
                   f"Exec={exec_}", "Categories=Game;", *extra)) + "\n", encoding="utf-8")


def test_o_atalho_do_umu_avulso_e_dito_e_o_de_outro_programa_nao(
        lar: Path, conf: dict[str, str]) -> None:
    """Mordida: sem o atalho do umu no ``fora``, o jogo pelo umu avulso some em silêncio."""
    _pino_na(_steam_de_verdade(lar))
    meus = lar / ".local/share/applications"
    sistema = lar / "sistema/applications"
    _atalho(meus, "corrida", "env PROTONPATH=GE-Proton WINEPREFIX=/p umu-run /p/corrida.exe")
    _atalho(meus, "pelo-caminho", "/usr/bin/umu-run /p/jogo.exe")
    _atalho(meus, "do-lutris", "lutris lutris:rungameid/7")
    _atalho(meus, "escondido", "umu-run /p/x.exe", "Hidden=true")
    _atalho(sistema, "escondido", "umu-run /p/x.exe")
    _atalho(sistema, "parecido", "meu-umu-runner /p/x.exe")
    _atalho(sistema, "de-fora", "umu-run /p/de-fora.exe")

    feito = _apontar(lar, conf)

    assert feito.fora == (censo.ForaDoPino("umu", "Corrida", censo.PORQUE_UMU_AVULSO),
                          censo.ForaDoPino("umu", "Pelo-Caminho", censo.PORQUE_UMU_AVULSO))
    assert "umu" in pp.quem_usa_o_proton(lar)
    assert censo.atalhos_do_umu_avulso() == ("Corrida", "Pelo-Caminho", "De-Fora"), (
        "sem o lar, as pastas do XDG da máquina contam, e o atalho escondido do usuário vence")


def test_sem_bottles_nem_umu_nada_muda(lar: Path, conf: dict[str, str]) -> None:
    _pino_na(_steam_de_verdade(lar))
    feito = _apontar(lar, conf)
    assert feito == censo.FixadoNoLancador()
    assert pp.quem_usa_o_proton(lar) == ("Steam",)
