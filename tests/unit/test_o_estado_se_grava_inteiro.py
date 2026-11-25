"""O estado se grava inteiro ou fica o de antes, com a escrita curta e com o disco cheio."""
from __future__ import annotations

import contextlib
import errno
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import keyboard
from hefesto_dualsense4unix.daemon.subsystems.external_identity import ExternalIdentityRegistry
from hefesto_dualsense4unix.daemon.subsystems.identity import ControllerIdentityRegistry
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.utils import maquina, session, xdg_paths

_ESCRITA_DE_VERDADE = os.write


def _perfil(prioridade: int) -> None:
    loader.save_profile(Profile(name="corrida", match=MatchAny(), priority=prioridade))


def _fila(posicao: int) -> None:
    registro = ExternalIdentityRegistry()
    registro._ordem = {"aabbcc000001": posicao, "aabbcc000002": posicao + 1}
    registro._save_locked()


def _fila_dos_dualsense(posicao: int) -> None:
    registro = ControllerIdentityRegistry()
    registro._ordem = {"aabbcc000001": posicao, "aabbcc000002": posicao + 1}
    registro._save_locked()


def _osk(pid: int) -> None:
    keyboard._gravar_sessao(pid, "onboard")


ESCRITORES: dict[str, tuple[Callable[[int], Any], Callable[[], Path]]] = {
    "maquina": (
        lambda n: maquina.gravar_maquina({"controles": {f"aabbcc00000{n}": {"nome": f"P{n}"}}}),
        maquina.caminho_da_maquina,
    ),
    "perfil": (_perfil, lambda: xdg_paths.profiles_dir() / "corrida.json"),
    "sessão": (lambda n: session.save_last_profile(f"perfil-{n}"),
               lambda: xdg_paths.config_dir() / "session.json"),
    "marca-do-teclado": (lambda n: session.save_keyboard_emulation(n % 2 == 0),
                         lambda: xdg_paths.config_dir() / "keyboard_emulation.flag"),
    "bandeira-do-mouse": (lambda n: session.save_mouse_emulation(True, speed=n),
                          lambda: xdg_paths.config_dir() / "mouse_emulation.flag"),
    "zeros": (lambda n: session.gravar_os_zeros({"aabbcc000001": [n, n, n]}),
              lambda: xdg_paths.config_dir() / "zeros-dos-sensores.json"),
    "teclado-na-tela": (_osk, lambda: xdg_paths.runtime_dir() / keyboard._OSK_SESSAO_ARQUIVO),
    "fila-dos-dualsense": (
        _fila_dos_dualsense, lambda: xdg_paths.config_dir() / "controllers.json"
    ),
    "fila-dos-externos": (_fila, lambda: xdg_paths.config_dir() / "controllers.json"),
}


def _sob(fd: int, pasta: Path) -> bool:
    try:
        return os.readlink(f"/proc/self/fd/{fd}").startswith(str(pasta.resolve()))
    except OSError:
        return False


def _o_disco_que_corta(monkeypatch: pytest.MonkeyPatch, pasta: Path, *, enche: bool) -> None:
    """``os.write`` sob ``pasta`` grava a metade; com ``enche``, a escrita seguinte dá ENOSPC."""
    feitas: list[int] = []

    def escrever(fd: int, dados: Any) -> int:
        if not _sob(fd, pasta):
            return _ESCRITA_DE_VERDADE(fd, dados)
        if enche and feitas:
            raise OSError(errno.ENOSPC, os.strerror(errno.ENOSPC))
        feitas.append(fd)
        return _ESCRITA_DE_VERDADE(fd, bytes(dados[: max(1, len(dados) // 2)]))

    monkeypatch.setattr(os, "write", escrever)


def _arquivos(pasta: Path) -> set[str]:
    return {p.name for p in pasta.iterdir() if p.is_file()}


@pytest.mark.parametrize("escritor", sorted(ESCRITORES))
def test_o_disco_cheio_deixa_o_arquivo_de_antes(
    escritor: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-1911-O-ESTADO-SE-GRAVA-INTEIRO: o disco cheio no meio deixa o arquivo de antes."""
    gravar, onde = ESCRITORES[escritor]
    gravar(1)
    alvo = onde()
    antes = alvo.read_bytes()
    nomes = _arquivos(alvo.parent)
    _o_disco_que_corta(monkeypatch, alvo.parent, enche=True)

    with contextlib.suppress(OSError):
        gravar(2)

    assert alvo.read_bytes() == antes
    assert _arquivos(alvo.parent) == nomes


@pytest.mark.parametrize("escritor", sorted(ESCRITORES))
def test_a_escrita_curta_grava_o_resto(
    escritor: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-1911-O-ESTADO-SE-GRAVA-INTEIRO: a escrita curta continua até o último byte."""
    gravar, onde = ESCRITORES[escritor]
    gravar(1)
    alvo = onde()
    gravar(2)
    inteiro = alvo.read_bytes()
    gravar(1)
    _o_disco_que_corta(monkeypatch, alvo.parent, enche=False)

    gravar(2)

    assert alvo.read_bytes() == inteiro


def test_a_marca_do_teclado_desligada_segue_desligada_no_disco_cheio(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-1911-O-ESTADO-SE-GRAVA-INTEIRO: o teclado desligado não volta ligado."""
    session.save_keyboard_emulation(False)
    _o_disco_que_corta(monkeypatch, xdg_paths.config_dir(), enche=True)

    session.save_keyboard_emulation(True)

    assert session.load_keyboard_preference() is False


def test_o_maquina_json_cortado_nao_apaga_os_controles(
    monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-1911-O-ESTADO-SE-GRAVA-INTEIRO: os quatro controles seguem no maquina.json."""
    quatro = {f"aabbcc00000{n}": {"nome": f"P{n}"} for n in range(1, 5)}
    assert maquina.gravar_maquina({"controles": quatro})
    _o_disco_que_corta(monkeypatch, maquina.caminho_da_maquina().parent, enche=False)

    assert maquina.gravar_maquina({"controles": {"aabbcc000001": {"nome": "Azul"}}})

    monkeypatch.setattr(os, "write", _ESCRITA_DE_VERDADE)
    disco = json.loads(maquina.caminho_da_maquina().read_text(encoding="utf-8"))
    assert {k: v["nome"] for k, v in disco["controles"].items()} == {
        **{k: v["nome"] for k, v in quatro.items()}, "aabbcc000001": "Azul"
    }
