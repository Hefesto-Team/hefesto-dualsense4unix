"""O install fecha e reabre a janela e a bandeja que estavam abertas, para valer o código novo."""
from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions import atos_da_bandeja as bandeja
from hefesto_dualsense4unix.app.actions import recarga_do_install as recarga

RAIZ = Path(__file__).resolve().parents[2]

ESPERA = "import time\nfor _ in range(600): time.sleep(0.1)"

Filhos = list[subprocess.Popen[bytes]]


class Registro:
    def __init__(self, subiu: bool = True) -> None:
        self.telas: list[dict[str, str]] = []
        self.abas: list[str] = []
        self.subidas = 0
        self.subiu = subiu

    def abrir(self, tela: dict[str, str], aba: str) -> bool:
        self.telas.append(tela)
        self.abas.append(aba)
        return True

    def subir(self) -> bool:
        self.subidas += 1
        return self.subiu


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    corre = tmp_path / "corre"
    corre.mkdir()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(corre))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    return corre


@pytest.fixture
def filhos() -> Iterator[Filhos]:
    vivos: Filhos = []
    yield vivos
    for filho in vivos:
        if filho.poll() is None:
            filho.kill()
        filho.wait(timeout=5)


def _subir(filhos: Filhos, *marcas: str, tela: str = "",
           python: str = sys.executable) -> subprocess.Popen[bytes]:
    ambiente = {"PATH": "/usr/bin:/bin", "WAYLAND_DISPLAY": tela} if tela else None
    filho = subprocess.Popen([python, "-c", ESPERA, *marcas], env=ambiente)
    filhos.append(filho)
    return filho


def _anotar_a_janela(lar: Path, pid: int) -> None:
    pasta = lar / "hefesto-dualsense4unix"
    pasta.mkdir(exist_ok=True)
    (pasta / "gui-wayland-9.pid").write_text(f"{pid}\n", encoding="ascii")


def _morreu(filho: subprocess.Popen[bytes]) -> bool:
    try:
        filho.wait(timeout=5)
    except subprocess.TimeoutExpired:
        return False
    return True


def test_a_janela_aberta_fecha_e_volta_na_mesma_tela(lar: Path, filhos: Filhos) -> None:
    """Prova da D-2610-O-INSTALL-RECARREGA-A-JANELA-E-A-BANDEJA."""
    janela = _subir(filhos, "hefesto", "--gui", tela="wayland-9")
    _anotar_a_janela(lar, janela.pid)
    feito = Registro(subiu=False)

    frases = recarga.recarregar(abrir=feito.abrir, subir_a_bandeja=feito.subir)

    assert _morreu(janela)
    assert feito.telas == [{"WAYLAND_DISPLAY": "wayland-9"}]
    assert "janela: fechada e reaberta" in frases


def test_a_janela_volta_na_aba_que_mostrava(lar: Path, filhos: Filhos) -> None:
    janela = _subir(filhos, "hefesto", "--gui", tela="wayland-9")
    _anotar_a_janela(lar, janela.pid)
    recarga.arquivo_da_aba(janela.pid).write_text("08-conexoes.html\n", encoding="utf-8")
    feito = Registro(subiu=False)

    recarga.recarregar(abrir=feito.abrir, subir_a_bandeja=feito.subir)

    assert feito.abas == ["08-conexoes.html"]


def test_a_aba_que_nao_e_pagina_publicada_nao_se_pede(lar: Path, filhos: Filhos) -> None:
    janela = _subir(filhos, "hefesto", "--gui", tela="wayland-9")
    _anotar_a_janela(lar, janela.pid)
    recarga.arquivo_da_aba(janela.pid).write_text("../../etc/passwd\n", encoding="utf-8")
    feito = Registro(subiu=False)

    recarga.recarregar(abrir=feito.abrir, subir_a_bandeja=feito.subir)

    assert feito.abas == [""]


def test_a_janela_anota_a_aba_que_o_install_le(lar: Path) -> None:
    from hefesto_dualsense4unix.interface import hefesto_vivo

    hefesto_vivo._anotar_a_aba("10-perfis.html")

    assert recarga.a_aba_de(os.getpid()) == "10-perfis.html"


def test_sem_janela_aberta_nada_se_abre(lar: Path) -> None:
    feito = Registro(subiu=False)

    frases = recarga.recarregar(abrir=feito.abrir, subir_a_bandeja=feito.subir)

    assert feito.telas == []
    assert frases[0] == "janela: nenhuma aberta"


def test_o_pid_que_nao_e_do_hefesto_nao_se_mata(lar: Path, filhos: Filhos) -> None:
    alheio = _subir(filhos, "outro-programa", python="/usr/bin/python3")
    _anotar_a_janela(lar, alheio.pid)
    feito = Registro(subiu=False)

    recarga.recarregar(abrir=feito.abrir, subir_a_bandeja=feito.subir)

    assert alheio.poll() is None
    assert feito.telas == []


def test_a_bandeja_de_pe_fecha_e_sobe_de_novo(lar: Path, filhos: Filhos) -> None:
    velha = _subir(filhos, "hefesto", "tray")
    bandeja.caminho_do_pid().write_text(f"{velha.pid}\n", encoding="ascii")
    feito = Registro()

    frases = recarga.recarregar(abrir=feito.abrir, subir_a_bandeja=feito.subir)

    assert _morreu(velha)
    assert feito.subidas == 1
    assert "ícone na bandeja: fechado e reaberto" in frases


def test_o_install_recarrega_depois_de_reiniciar_o_daemon() -> None:
    texto = (RAIZ / "install.sh").read_text(encoding="utf-8")
    reinicio = texto.index('systemctl --user restart "${DAEMON_UNIT_NAME}"')
    chamada = texto.index("-m hefesto_dualsense4unix.app.actions.recarga_do_install")
    assert reinicio < chamada
    assert "import garantir_a_bandeja" not in texto
