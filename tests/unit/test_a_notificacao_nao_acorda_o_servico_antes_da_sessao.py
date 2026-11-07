"""A notificação não acorda o serviço antes da sessão (07/11/2026).

O serviço fica 124 s no ar sem sessão gráfica, e o ``Notify`` sem ``no_auto_start`` ativava o
``org.freedesktop.Notifications`` de quem o tem por ativação (``dunst``, ``mako``), que nascia sem
``WAYLAND_DISPLAY``. Aqui o barramento é um ``dbus-daemon`` particular, com um servidor de avisos
ATIVÁVEL de verdade (toma o nome, responde e anota o que recebeu) e um ``systemd1`` de mentira.

MORDIDA: tirar a bandeira do ``notify`` reprova o primeiro caso; ``no_auto_start`` sempre reprova o
segundo; tirar a conferência da resposta de erro reprova o do ``once_key``.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import desktop_notifications as avisos
from tests.unit.test_a_captura_nao_acorda_o_portal_antes_da_sessao import (
    _CONFIG,
    _SERVICO,
    _SYSTEMD,
    GerenteDeMentira,
)

_NOME = "org.freedesktop.Notifications"
_LER_O_AMBIENTE = "org.freedesktop.DBus.Properties.Get"
_COM_SESSAO = ["HOME=/lar", "XDG_CURRENT_DESKTOP=COSMIC", "WAYLAND_DISPLAY=w-1"]
_SEM_SESSAO = ["HOME=/lar", "PATH=/usr/bin"]

_SERVIDOR = textwrap.dedent(
    """
    import os
    import sys

    from jeepney import HeaderFields, MessageType, new_method_return
    from jeepney.bus_messages import message_bus
    from jeepney.io.blocking import open_dbus_connection

    canal = open_dbus_connection(bus=os.environ["DBUS_STARTER_ADDRESS"])
    canal.send(message_bus.RequestName("org.freedesktop.Notifications", 4))
    while True:
        mensagem = canal.receive()
        if mensagem.header.message_type != MessageType.method_call:
            continue
        if mensagem.header.fields.get(HeaderFields.member) == "Notify":
            with open(sys.argv[1], "a", encoding="utf-8") as entregas:
                entregas.write(mensagem.body[3] + "\\n")
        canal.send(new_method_return(mensagem, "u", (1,)))
    """
)

_ATIVADOR = """#!/bin/sh
echo ativado >> "{marca}"
exec "{python}" "{servidor}" "{entregas}"
"""

_ATIVADOR_DO_GERENTE = """#!/bin/sh
echo ativado >> "{marca}"
exit 1
"""

_PRECISA_DO_BARRAMENTO = pytest.mark.skipif(
    shutil.which("dbus-daemon") is None, reason="sem dbus-daemon, não há barramento particular")


def _linhas(arquivo: Path) -> list[str]:
    return arquivo.read_text(encoding="utf-8").splitlines() if arquivo.exists() else []


class Barramento:
    """O ``dbus-daemon`` particular: ``marca`` conta as ativações do servidor de avisos, e
    ``entregas`` guarda o título de cada ``Notify`` que chegou a ele."""

    def __init__(self, pasta: Path) -> None:
        self.marca = pasta / "ativado"
        self.entregas = pasta / "entregas"
        self.marca_do_gerente = pasta / "gerente-ativado"
        servicos = pasta / "ativaveis"
        servicos.mkdir()
        servidor = pasta / "servidor.py"
        servidor.write_text(_SERVIDOR, encoding="utf-8")
        ativador = pasta / "ativador.sh"
        ativador.write_text(_ATIVADOR.format(marca=self.marca, python=sys.executable,
                                             servidor=servidor, entregas=self.entregas),
                            encoding="utf-8")
        do_gerente = pasta / "ativador-do-gerente.sh"
        do_gerente.write_text(_ATIVADOR_DO_GERENTE.format(marca=self.marca_do_gerente),
                              encoding="utf-8")
        (servicos / f"{_NOME}.service").write_text(
            _SERVICO.format(nome=_NOME, ativador=ativador), encoding="utf-8")
        (servicos / f"{_SYSTEMD}.service").write_text(
            _SERVICO.format(nome=_SYSTEMD, ativador=do_gerente), encoding="utf-8")
        config = pasta / "barramento.conf"
        config.write_text(_CONFIG.format(soquete=pasta / "barramento", servicos=servicos),
                          encoding="utf-8")
        self._processo = subprocess.Popen(
            ["dbus-daemon", "--config-file", str(config), "--print-address", "--nofork",
             "--nopidfile"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        assert self._processo.stdout is not None
        self.endereco = self._processo.stdout.readline().strip()
        assert self.endereco, "o dbus-daemon particular não disse o endereço"

    def fechar(self) -> None:
        self._processo.terminate()
        self._processo.wait(timeout=5)


@pytest.fixture
def barramento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Barramento]:
    monkeypatch.setattr(avisos, "_DBUS_TIMEOUT_SECONDS", 20.0)
    monkeypatch.setenv(avisos.AVISO_DE_VERDADE_NA_SUITE, "1")
    vivo = Barramento(tmp_path)
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", vivo.endereco)
    try:
        yield vivo
    finally:
        vivo.fechar()


@pytest.fixture
def sem_sessao(barramento: Barramento) -> Iterator[GerenteDeMentira]:
    gerente = GerenteDeMentira(barramento.endereco, list(_SEM_SESSAO))
    try:
        yield gerente
    finally:
        gerente.fechar()


@pytest.fixture
def com_sessao(barramento: Barramento) -> Iterator[GerenteDeMentira]:
    gerente = GerenteDeMentira(barramento.endereco, list(_COM_SESSAO))
    try:
        yield gerente
    finally:
        gerente.fechar()


@pytest.fixture(autouse=True)
def _cache_zerado() -> Iterator[None]:
    avisos.reset_once_cache()
    yield
    avisos.reset_once_cache()


@_PRECISA_DO_BARRAMENTO
def test_sem_a_sessao_o_aviso_nao_ativa_o_servico(
    barramento: Barramento, sem_sessao: GerenteDeMentira
) -> None:
    assert avisos.notify("Hefesto", "cedo demais") is False
    assert _linhas(barramento.marca) == []
    assert _linhas(barramento.entregas) == []
    assert sem_sessao.pedidos == [_LER_O_AMBIENTE]


@_PRECISA_DO_BARRAMENTO
def test_com_a_sessao_de_pe_o_aviso_ativa_e_entrega(
    barramento: Barramento, com_sessao: GerenteDeMentira
) -> None:
    assert avisos.notify("Hefesto", "com a sessão") is True
    assert len(_linhas(barramento.marca)) == 1
    assert _linhas(barramento.entregas) == ["Hefesto"]


@_PRECISA_DO_BARRAMENTO
def test_sem_a_sessao_quem_ja_esta_de_pe_recebe(
    barramento: Barramento, sem_sessao: GerenteDeMentira
) -> None:
    sem_sessao.ambiente[:] = _COM_SESSAO
    assert avisos.notify("Primeiro") is True
    sem_sessao.ambiente[:] = _SEM_SESSAO
    assert avisos.notify("Segundo") is True
    assert len(_linhas(barramento.marca)) == 1
    assert _linhas(barramento.entregas) == ["Primeiro", "Segundo"]


@_PRECISA_DO_BARRAMENTO
def test_o_aviso_de_uma_vez_recusado_antes_da_sessao_nao_se_gasta(
    barramento: Barramento, sem_sessao: GerenteDeMentira
) -> None:
    assert avisos.notify_teclado_na_tela_ausente(["onboard"]) is False
    assert _linhas(barramento.entregas) == []
    sem_sessao.ambiente[:] = _COM_SESSAO
    assert avisos.notify_teclado_na_tela_ausente(["onboard"]) is True
    assert avisos.notify_teclado_na_tela_ausente(["onboard"]) is False
    assert _linhas(barramento.entregas) == ["Teclado na tela não instalado"]


@_PRECISA_DO_BARRAMENTO
@pytest.mark.parametrize(("ligado", "titulo"), [(True, "Modo jogo ligado"),
                                                (False, "Modo jogo desligado")])
def test_o_aviso_do_modo_jogo_sai_igual_com_a_sessao_de_pe(
    barramento: Barramento, com_sessao: GerenteDeMentira, ligado: bool, titulo: str
) -> None:
    assert avisos.notify_emulation_suppressed(ligado) is True
    assert _linhas(barramento.entregas) == [titulo]


@_PRECISA_DO_BARRAMENTO
@pytest.mark.parametrize(("desktop", "entregue"), [(None, False), ("", False), ("COSMIC", True)])
def test_sem_o_gerente_vale_o_ambiente_do_proprio_processo_e_ele_nao_se_ativa(
    barramento: Barramento, monkeypatch: pytest.MonkeyPatch, desktop: str | None, entregue: bool
) -> None:
    if desktop is None:
        monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    else:
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", desktop)
    assert avisos.notify("Hefesto") is entregue
    assert len(_linhas(barramento.entregas)) == int(entregue)
    time.sleep(0.1)
    assert _linhas(barramento.marca_do_gerente) == []
