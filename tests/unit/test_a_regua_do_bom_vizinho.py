"""A régua do bom vizinho (07/11/2026).

Em 05/11 um pedido cedo demais do Hefesto quebrou o compartilhamento de tela da máquina inteira, e a
tabela de quem acorda quem era feita à mão. Agora são três peças: a coluna ``ativa`` do censo, a
porta ``integrations/barramento_do_sistema.py`` e a prova de boot.

A prova de boot é um ``dbus-daemon`` particular com todo nome ``dbus:`` do censo ativável de
mentira, inclusive os ``não``, cada um com a sua marca: declarar ``não`` não tira o nome da prova.
Fora da prova
ficam só o próprio barramento e o ``org.gnome``, que é nome de janela. Sem sessão, cada caminho do
produto que fala com o nome roda de verdade, e o certo é zero ativação. O serviço inteiro não sobe
aqui: ele abriria os nós da máquina. Por isso a lista dos caminhos é igual à do censo, e nome novo
sem caminho reprova.

MORDIDA: tirar a guarda de um nome reprova com o nome dito: o ``sem_ativar`` da porta
(``org.freedesktop.Notifications`` e ``org.freedesktop.systemd1``), o ``NO_AUTO_START`` do Gio
(``org.bluez`` e ``org.freedesktop.NetworkManager``), o ``sessao_ainda_nao_subiu`` do ``abrir``
(``org.freedesktop.portal``) ou o ``NameHasOwner`` da bandeja (``org.kde``).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import desktop_notifications as avisos
from hefesto_dualsense4unix.integrations import diario_do_radio, faixa_do_wifi
from hefesto_dualsense4unix.integrations import tela_do_jogo as tj
from tests.unit import bluez_de_mentira as bm
from tests.unit.test_a_captura_nao_acorda_o_portal_antes_da_sessao import (
    _ATIVADOR,
    _CONFIG,
    _SERVICO,
    GerenteDeMentira,
)
from tests.unit.test_o_portal_da_tela_responde_ao_pedido_da_captura import _ha_pipewiresrc
from tests.unit.test_os_contratos_de_fora import PACOTE, RAIZ, _arvore, _linha, regua

_NOME_NO_BARRAMENTO = {"org.freedesktop.portal": tj._PORTAL,
                       "org.freedesktop.impl": tj._ARMAZEM,
                       "org.kde": "org.kde.StatusNotifierWatcher"}
_FORA_DA_PROVA = {"org.freedesktop.DBus", "org.gnome"}
_ARQUIVO = f"{PACOTE}/novo.py"
_FALA_COM_O_NOME = 'NOME = "org.freedesktop.login1"\n'
_ALVO = "dbus:org.freedesktop.login1"

_ha_o_barramento = pytest.mark.skipif(
    not bm.ha_dbus_daemon() or shutil.which("busctl") is None or not _ha_pipewiresrc(),
    reason="sem dbus-daemon, Gio, busctl ou pipewiresrc, os caminhos do produto nem chegam ao nome")


def _nomes_do_censo() -> set[str]:
    return {linha["alvo"].removeprefix("dbus:") for linha in regua.ler_censo(RAIZ)
            if linha["alvo"].startswith("dbus:")} - _FORA_DA_PROVA


class Barramento:
    """Um ``dbus-daemon`` só faz de barramento da sessão e do sistema: todo nome é ativável."""

    def __init__(self, pasta: Path) -> None:
        servicos = pasta / "ativaveis"
        servicos.mkdir()
        self.marcas: dict[str, Path] = {}
        for censo in _nomes_do_censo():
            nome = _NOME_NO_BARRAMENTO.get(censo, censo)
            self.marcas[censo] = pasta / f"marca-{nome}"
            ativador = pasta / f"ativador-{nome}.sh"
            ativador.write_text(_ATIVADOR.format(contagem=self.marcas[censo]), encoding="utf-8")
            (servicos / f"{nome}.service").write_text(
                _SERVICO.format(nome=nome, ativador=ativador), encoding="utf-8")
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
        self.binarios = pasta / "bin"
        self.binarios.mkdir()
        envelope = self.binarios / "busctl"
        envelope.write_text(
            f'#!/bin/sh\nexec "{shutil.which("busctl")}" --address="{self.endereco}" "$@"\n',
            encoding="utf-8")
        envelope.chmod(0o755)

    def ativados(self) -> dict[str, int]:
        return {nome: len(marca.read_text(encoding="utf-8").splitlines())
                for nome, marca in self.marcas.items() if marca.exists()}

    def fechar(self) -> None:
        self._processo.terminate()
        self._processo.wait(timeout=5)


@pytest.fixture
def barramento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Barramento]:
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(tmp_path / "radio-diario.jsonl"))
    monkeypatch.setenv(avisos.AVISO_DE_VERDADE_NA_SUITE, "1")
    monkeypatch.delenv("XDG_CURRENT_DESKTOP", raising=False)
    avisos.reset_once_cache()
    vivo = Barramento(tmp_path)
    monkeypatch.setenv("DBUS_SESSION_BUS_ADDRESS", vivo.endereco)
    monkeypatch.setenv("PATH", f"{vivo.binarios}{os.pathsep}{os.environ['PATH']}")
    try:
        yield vivo
    finally:
        vivo.fechar()
        avisos.reset_once_cache()


def _o_aviso_da_subida(_barramento: Barramento, _pasta: Path) -> None:
    assert avisos.notify_emulation_suppressed(True) is False
    assert avisos.notify_teclado_na_tela_ausente(["onboard"]) is False


def _a_captura_que_assinou(_barramento: Barramento, pasta: Path) -> None:
    (pasta / "ficha").write_text("ficha-guardada", encoding="utf-8")
    with pytest.raises(RuntimeError):
        tj.FonteDoPortal(pasta / "ficha").abrir()


def _o_dono_do_radio(barramento: Barramento, _pasta: Path) -> None:
    leitor = bd.PeloBusctl()
    assert leitor.caminhos() is None
    assert leitor.propriedade("/org/bluez/hci0", bd.ADAPTADOR, "Address") is None
    vivo_no_gio = bd.BarramentoGio(barramento.endereco)
    assert vivo_no_gio.abrir()
    vivo = bd.DonoVivo(vivo_no_gio)
    try:
        assert vivo.ligar()
    finally:
        vivo.fechar()


def _a_faixa_do_wifi(barramento: Barramento, _pasta: Path) -> None:
    ponte = bd.BarramentoGio(barramento.endereco)
    assert ponte.abrir()
    try:
        assert faixa_do_wifi.ler_as_redes(ponte) is None
    finally:
        ponte.fechar()


def _a_bandeja(_barramento: Barramento, _pasta: Path) -> None:
    assert avisos.statusnotifierwatcher_available() is False


_CAMINHOS: dict[str, Callable[[Barramento, Path], None]] = {
    "org.bluez": _o_dono_do_radio,
    "org.freedesktop.NetworkManager": _a_faixa_do_wifi,
    "org.freedesktop.Notifications": _o_aviso_da_subida,
    "org.freedesktop.impl": _a_captura_que_assinou,
    "org.freedesktop.portal": _a_captura_que_assinou,
    "org.freedesktop.systemd1": _o_aviso_da_subida,
    "org.kde": _a_bandeja,
}


def test_todo_nome_do_censo_tem_o_caminho_na_prova_de_boot() -> None:
    assert _nomes_do_censo() == set(_CAMINHOS), (
        "nome novo no censo: acrescente o caminho do produto que fala com ele")


@_ha_o_barramento
@pytest.mark.parametrize("com_o_gerente", [True, False], ids=["gerente-sem-desktop", "sem-gerente"])
def test_a_prova_de_boot_sem_a_sessao_nada_se_ativa(
    barramento: Barramento, tmp_path: Path, com_o_gerente: bool
) -> None:
    gerente = GerenteDeMentira(barramento.endereco, ["HOME=/lar"]) if com_o_gerente else None
    try:
        for caminho in dict.fromkeys(_CAMINHOS.values()):
            caminho(barramento, tmp_path)
    finally:
        if gerente is not None:
            gerente.fechar()
    assert barramento.ativados() == {}, f"acordou sem a sessão: {barramento.ativados()}"


def test_contato_novo_sem_a_coluna_reprova(tmp_path: Path) -> None:
    raiz = _arvore(tmp_path, {_ARQUIVO: _FALA_COM_O_NOME}, [_linha(_ARQUIVO, _ALVO)])
    assert any("SEM a coluna `ativa`" in q and _ALVO in q for q in regua.julgar(raiz))


def test_nome_ativavel_sem_protecao_reprova(tmp_path: Path) -> None:
    raiz = _arvore(tmp_path, {_ARQUIVO: _FALA_COM_O_NOME},
                   [_linha(_ARQUIVO, _ALVO, ativa=regua.ATIVA_SIM)])
    assert any("SEM proteção" in q for q in regua.julgar(raiz))


@pytest.mark.parametrize(("texto", "reprova"), [
    (_FALA_COM_O_NOME, True),
    (f"# {regua.PORTA_DO_BARRAMENTO}\n{_FALA_COM_O_NOME}", False),
    (f'{_FALA_COM_O_NOME}FLAG = "{regua.BORDA_DO_GIO}"\n', False),
], ids=["sem-a-porta", "pela-porta", "pelo-gio"])
def test_o_protegido_precisa_da_porta_no_arquivo(
    tmp_path: Path, texto: str, reprova: bool
) -> None:
    raiz = _arvore(tmp_path, {_ARQUIVO: texto},
                   [_linha(_ARQUIVO, _ALVO, ativa=regua.ATIVA_PROTEGIDO)])
    assert any("não usa a porta" in q for q in regua.julgar(raiz)) is reprova


def test_a_coluna_so_vale_em_dbus(tmp_path: Path) -> None:
    fonte = 'import subprocess\n\ndef ver():\n    return subprocess.run(["busctl", "tree"])\n'
    raiz = _arvore(tmp_path, {_ARQUIVO: fonte},
                   [_linha(_ARQUIVO, "cmd:busctl", ativa=regua.ATIVA_NAO)])
    assert any("só vale em `dbus:`" in q for q in regua.julgar(raiz))


@pytest.mark.parametrize(("arquivo", "corpo", "reprova"), [
    ("scripts/novo.sh", "busctl tree org.bluez --list\n", True),
    ("scripts/novo.sh", "busctl get-property org.bluez /org/bluez/hci0 x y\n", True),
    ("scripts/novo.sh", "busctl set-property org.bluez /org/bluez/hci0 x y s z\n", True),
    ("scripts/novo.sh", "busctl call org.bluez /org/bluez/hci0 x y\n", True),
    ("scripts/novo.sh", "busctl call org.bluez /org/bluez/hci0 x y --auto-start=no\n", False),
    ("scripts/novo.sh", "_bluez_de_pe() { :; }\nbusctl tree org.bluez --list\n", False),
    ("scripts/doctor.sh", "busctl tree org.bluez --list\n", False),
], ids=["tree", "get-property", "set-property", "call", "call-sem-ativar", "com-a-guarda",
        "gesto-de-diagnostico"])
def test_script_que_pergunta_ao_radio_precisa_da_guarda(
    tmp_path: Path, arquivo: str, corpo: str, reprova: bool
) -> None:
    raiz = _arvore(tmp_path, {arquivo: corpo}, [])
    queixas = regua.julgar_os_scripts(raiz)
    assert bool(queixas) is reprova, queixas
