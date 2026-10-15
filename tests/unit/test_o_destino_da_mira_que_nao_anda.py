"""A-MIRA-NA-NAVEGACAO-02 — o destino que não anda, e o cartão «Só a janela».

As duas decisões são de produto (24/09/2026), pelo mesmo padrão: *a
tela nunca afirma o que não acontece*.

1. **O destino «mouse» fora da Navegação** (só por JSON à mão) não movia nada:
   o mouse emulado e o controle virtual se excluem, e a dica do Giroscópio
   dizia «move o cursor». O esquema passou a ler o «mouse» como o analógico
   direito (`ProfileMovimentoConfig._o_cursor_fora_da_navegacao_e_o_analogico_direito`);
   na Navegação todo destino ligado já é o cursor (`roteador.para_o_cursor`).
2. **O cartão de quem não navega** (a aba 06 do desenho antigo) saiu com o desenho
   do todo: a Navegação não tem mais cartão por controle, e as réguas dele saíram junto.

A RÉGUA MEDE O QUE O PRODUTO FAZ, e não só o que o esquema devolve: o `Daemon`,
o `IpcServer`, o `SensorHub`, o `CoopManager` e os DOIS controles virtuais de
verdade — o `UhidDualSense` (a máscara Sony DualSense) e o `UinputGamepad`
(a Xbox) —, com o nó do kernel de mentira nos dois. Nenhum nó de verdade
nasce aqui. Endereços da faixa SINTÉTICA da casa (``aa:bb:cc``).

OS QUATRO MODOS, e por que o Nativo não tem motor aqui: no Nativo não há
controle virtual nem mouse emulado, e o co-op não sobe
(`test_o_coop_vive_na_conexao_nativa.py`); o chip recusa
(`test_em_modo_nativo_a_resposta_diz_o_que_nao_alcanca`). O que o Nativo mostra
na tela — a dica — está na seção 4.

Cada régua diz a MORDIDA: o que arrancar para vê-la reprovar.
"""

from __future__ import annotations

import json
import os
import pathlib
import struct
import sys
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.subsystems import coop as co
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import UHID_INPUT2, UhidDualSense
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    Profile,
    ProfileMovimentoConfig,
)
from hefesto_dualsense4unix.testing import FakeController
from tests.unit.test_a_mira_na_navegacao import (
    _P as _P_DA_NAVEGACAO,
)
from tests.unit.test_a_mira_na_navegacao import (
    _PX_POR_TIQUE,
    _ate_andar,
    _navegacao,
    _RegistroDeIdentidade,
)
from tests.unit.test_a_mira_por_movimento_na_tela import _estado, _hub

RAIZ = pathlib.Path(__file__).resolve().parents[2]
_INTERFACE = str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")
if _INTERFACE not in sys.path:
    sys.path.insert(0, _INTERFACE)

_P = {n: f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4)}
_CHAVE = {n: f"aabbcc00000{n}" for n in (1, 2, 3, 4)}
_GIRO = (0.0, 150.0, 0.0)
_CENTRO = 128


@pytest.fixture(autouse=True)
def _registro_limpo() -> Iterator[None]:
    """O `REGISTRO` dos sensores é do processo: nada desta régua vaza dele."""
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis isolado — o molde das réguas da A-MIRA."""
    from hefesto_dualsense4unix.profiles import loader as loader_module

    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


def _perfil_escrito_a_mao(
    *, mesa: dict[str, Any] | None = None, por_controle: dict[int, dict[str, Any]] | None = None
) -> dict[str, Any]:
    """O perfil como ela o escreveria num editor de texto: um dicionário cru."""
    bruto: dict[str, Any] = {"name": "Feito no editor", "match": {"type": "any"}}
    if mesa is not None:
        bruto["movimento"] = mesa
    if por_controle:
        bruto["controllers"] = {_CHAVE[n]: {"movimento": m} for n, m in por_controle.items()}
    return bruto


def test_o_mouse_escrito_a_mao_vira_o_analogico_direito(perfis: Path) -> None:
    """A seção do perfil, a peça de um controle e o ARQUIVO no disco: nas três"""
    from hefesto_dualsense4unix.profiles.loader import load_profile

    secao = ProfileMovimentoConfig.model_validate({"destino": "mouse", "sensibilidade": 9})
    assert (secao.destino, secao.sensibilidade) == ("analogico_direito", 9)
    peca = ControllerOverrides.model_validate({"movimento": {"destino": "mouse"}})
    assert peca.movimento is not None and peca.movimento.destino == "analogico_direito"
    bruto = _perfil_escrito_a_mao(mesa={"destino": "mouse", "gatilho": "l2"},
                                  por_controle={3: {"destino": "mouse"}})
    (perfis / "feito_no_editor.json").write_text(json.dumps(bruto), encoding="utf-8")
    lido = load_profile("feito_no_editor")
    assert lido.movimento is not None
    assert (lido.movimento.destino, lido.movimento.gatilho) == ("analogico_direito", "l2")
    dele = (lido.controllers or {})[_CHAVE[3]].movimento
    assert dele is not None and dele.destino == "analogico_direito"


@pytest.mark.parametrize("destino", ["nenhum", "analogico_direito", "analogico_esquerdo"])
def test_os_outros_destinos_nao_mudam(destino: str) -> None:
    """Só o «mouse» é lido de outro jeito: o esquerdo continua o esquerdo e o"""
    assert ProfileMovimentoConfig(destino=destino).destino == destino  # type: ignore[arg-type]


# 2. O MOTOR FORA DA NAVEGAÇÃO — Sony DualSense e Xbox, P1 a P4, USB e BT


class _NoDoUinput:
    """O nó `uinput` de mentira do `UinputGamepad`: guarda cada `write`, na"""

    def __init__(self) -> None:
        self.escritas: list[tuple[int, int, int]] = []

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        self.escritas.append((tipo, codigo, valor))

    def syn(self) -> None:
        pass

    def read_one(self) -> None:
        return None


#: O blueprint mínimo do `UhidDualSense` — o molde de `test_uhid_gamepad.py`,
_BLUEPRINT = {
    "descriptor": bytes([0x05, 0x01, 0x09, 0x05, 0xA1, 0x01]),
    "features": {
        0x05: bytes([0x05]) + bytes(40),
        0x09: bytes([0x09]) + bytes.fromhex("010000ccbbaa") + bytes(13),
        0x20: bytes([0x20]) + bytes(63),
    },
}


class _NoDoUhid:
    """O `/dev/uhid` de mentira: um descritor por vpad, cada escrita guardada."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.escritas: dict[int, list[bytes]] = {}
        self._proximo = 4242
        real = SimpleNamespace(open=os.open, write=os.write, close=os.close,
                               read=os.read, set_blocking=os.set_blocking)

        def _open(caminho: Any, flags: int, *a: Any, **k: Any) -> int:
            if str(caminho) == uhid_gamepad.UHID_NODE:
                fd = self._proximo
                self._proximo += 1
                self.escritas[fd] = []
                return fd
            return int(real.open(caminho, flags, *a, **k))

        def _write(fd: int, dados: bytes) -> int:
            if fd in self.escritas:
                self.escritas[fd].append(bytes(dados))
                return len(dados)
            return int(real.write(fd, dados))

        def _close(fd: int) -> None:
            if fd not in self.escritas:
                real.close(fd)

        def _read(fd: int, tamanho: int) -> bytes:
            if fd in self.escritas:
                raise BlockingIOError
            return bytes(real.read(fd, tamanho))

        def _set_blocking(fd: int, bloqueia: bool) -> None:
            if fd not in self.escritas:
                real.set_blocking(fd, bloqueia)

        for nome, fn in (("open", _open), ("write", _write), ("close", _close),
                         ("read", _read), ("set_blocking", _set_blocking)):
            monkeypatch.setattr(uhid_gamepad.os, nome, fn)


def _eixos_que_o_jogo_le(vpad: Any, uhid: _NoDoUhid | None) -> dict[str, int]:
    """O `lx` e o `rx` do ÚLTIMO relatório que chegou ao kernel.

    No Sony DualSense é o report HID 0x01 dentro do `UHID_INPUT2`
    (`<IH` + report: o id no byte 0, os seis eixos a partir do 1); na Xbox é o
    último `EV_ABS` de cada código.
    """
    if isinstance(vpad, UinputGamepad):
        from evdev import ecodes

        no: _NoDoUinput = vpad._device
        ultimo = {c: v for t, c, v in no.escritas if t == ecodes.EV_ABS}
        return {"lx": ultimo.get(ecodes.ABS_X, _CENTRO), "rx": ultimo.get(ecodes.ABS_RX, _CENTRO)}
    assert uhid is not None
    relatorios = [e[6:] for e in uhid.escritas[vpad._fd]
                  if len(e) > 6 and struct.unpack("<I", e[:4])[0] == UHID_INPUT2]
    assert relatorios, "nenhum relatório chegou ao nó do vpad"
    ultimo = relatorios[-1]
    assert ultimo[0] == 0x01, f"o relatório não é o 0x01: {ultimo[:4].hex()}"
    return {"lx": ultimo[1], "rx": ultimo[3]}


@pytest.fixture
def vpads_de_verdade(monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """Fábrica dos controles virtuais das duas máscaras; os uhid morrem no fim"""
    uhid = _NoDoUhid(monkeypatch)
    vivos: list[UhidDualSense] = []

    def fabricar(mascara: str, n: int) -> Any:
        if mascara == "xbox":
            from evdev import ecodes

            vpad = UinputGamepad(flavor="xbox")
            vpad._device = _NoDoUinput()
            vpad._ecodes = ecodes
            return vpad
        vpad = UhidDualSense(player=n, identity=_P[n], blueprint=_BLUEPRINT)
        assert vpad.start(), "o uhid de mentira não subiu"
        vivos.append(vpad)
        return vpad

    yield SimpleNamespace(fabricar=fabricar, uhid=uhid)
    for vpad in vivos:
        vpad.stop()


def _mesa_com_controle_virtual(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str, mascara: str,
    bruto: dict[str, Any], vpads_de_verdade: Any,
) -> dict[int, Any]:
    """O `Daemon` real com o controle virtual de pé: o P1 pelo `dispatch_gamepad`"""
    hub = _hub({_P[n]: _GIRO for n in (1, 2, 3, 4)})
    controle = FakeController(transport=transporte)  # type: ignore[arg-type]
    controle.primary_uniq = _P[1]  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(controller=controle, store=daemon.store, profile_manager=gerente,
                         socket_path=tmp_path / "destino.sock", daemon=daemon)
    servidor._sensor_hub = hub
    daemon._ipc_server = servidor
    gerente.apply_movimento(Profile.model_validate(bruto))
    assert daemon._mouse_device is None, "com o controle virtual não há mouse emulado"
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    vpads = {n: vpads_de_verdade.fabricar(mascara, n) for n in (1, 2, 3, 4)}
    daemon._gamepad_device = vpads[1]
    coop = co.CoopManager(daemon)
    for n in (2, 3, 4):
        coop._players[_P[n]] = co._SecondaryPlayer(
            identity=_P[n],
            evdev_path=f"/dev/input/event-destino-{n}",
            reader=SimpleNamespace(
                snapshot=lambda: SimpleNamespace(
                    lx=_CENTRO, ly=_CENTRO, rx=_CENTRO, ry=_CENTRO, l2_raw=0, r2_raw=0,
                    buttons_pressed=frozenset()),
                grab_state="held",
            ),
            player_index=n,
            vpad=vpads[n],
        )
    for _ in range(2):
        gp.dispatch_gamepad(daemon, _estado(transporte), frozenset())
        coop.forward_all()
        hub.reconciliar()
    return vpads


def _quem_mirou(vpads: dict[int, Any], uhid: _NoDoUhid) -> dict[int, dict[str, int]]:
    return {n: _eixos_que_o_jogo_le(v, uhid) for n, v in vpads.items()}


@pytest.mark.parametrize("mascara", ["dualsense", "xbox"])
@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_fora_da_navegacao_o_mouse_da_peca_move_o_analogico_direito(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, vpads_de_verdade: Any,
    jogador: int, transporte: str, mascara: str,
) -> None:
    """O «mouse» escrito à mão na peça do jogador N: o analógico direito do"""
    bruto = _perfil_escrito_a_mao(por_controle={jogador: {"destino": "mouse"}})
    vpads = _mesa_com_controle_virtual(monkeypatch, tmp_path, transporte, mascara,
                                       bruto, vpads_de_verdade)
    eixos = _quem_mirou(vpads, vpads_de_verdade.uhid)
    moveram = sorted(n for n, e in eixos.items() if e["rx"] != _CENTRO)
    assert moveram == [jogador], (
        f"{mascara}/{transporte}: o «mouse» do P{jogador} devia mover o analógico "
        f"direito dele, e moveram {moveram} — {eixos}")
    assert eixos[jogador]["lx"] == _CENTRO, f"o giro foi ao analógico esquerdo: {eixos}"


@pytest.mark.parametrize("mascara", ["dualsense", "xbox"])
@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_fora_da_navegacao_o_mouse_da_mesa_move_os_quatro(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, vpads_de_verdade: Any,
    transporte: str, mascara: str,
) -> None:
    """O «mouse» na mira do PERFIL inteiro: os quatro analógicos direitos andam."""
    bruto = _perfil_escrito_a_mao(mesa={"destino": "mouse"})
    vpads = _mesa_com_controle_virtual(monkeypatch, tmp_path, transporte, mascara,
                                       bruto, vpads_de_verdade)
    eixos = _quem_mirou(vpads, vpads_de_verdade.uhid)
    assert all(e["rx"] != _CENTRO for e in eixos.values()), (
        f"{mascara}/{transporte}: a mira da mesa no «mouse» não moveu os quatro: {eixos}")


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_na_navegacao_o_mouse_escrito_a_mao_continua_o_cursor(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    jogador: int, transporte: str,
) -> None:
    """O mesmo «mouse» à mão, na Navegação: o cursor anda o giro de UM controle,"""
    bruto = _perfil_escrito_a_mao(por_controle={jogador: {"destino": "mouse"}})
    nav = _navegacao(tmp_path, monkeypatch, transporte, perfil=Profile.model_validate(bruto))
    assert _ate_andar(nav) == (_PX_POR_TIQUE, 0), f"P{jogador}/{transporte}"
    u = nav.mouse._uinput_mod
    assert not [e for e in nav.no.eventos if e[0] in (u.REL_WHEEL, u.REL_HWHEEL)]


def test_na_navegacao_a_peca_de_chip_apagado_drena(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A DRENAGEM VEM ANTES DO PORTÃO DA PEÇA, no caminho que o produto alcança."""
    bruto = _perfil_escrito_a_mao(mesa={"destino": "mouse"},
                                  por_controle={4: {"destino": "nenhum"}})
    nav = _navegacao(tmp_path, monkeypatch, "bt", perfil=Profile.model_validate(bruto))
    nav.daemon.identity_registry = _RegistroDeIdentidade(set(_P_DA_NAVEGACAO.values()))
    assert _ate_andar(nav) == (3 * _PX_POR_TIQUE, 0)
    drenagens = {n: nav.mesa.movimento[u].drenagens for n, u in _P_DA_NAVEGACAO.items()
                 if u in nav.mesa.movimento}
    assert drenagens.get(2, 0) >= 1, f"nem a peça que mira drenou — régua cega: {drenagens}"
    assert drenagens.get(4) == drenagens[2], (
        f"a peça de chip apagado não descartou o ângulo: {drenagens}")


_DICA_DE_HOJE = "Ligado: o jogo recebe o giro deste controle."
_DICA_NO_DIREITO = ("Com o analógico virtual aceso, o giro deste controle vai ao jogo "
                    "pelo analógico direito.")
_DICA_NO_CURSOR = "Com o analógico virtual aceso, o giro deste controle move o cursor."

_RATO_ANDANDO = {"enabled": True, "device_ativo": True, "despachando": True, "bloqueio": None}
_RATO_DESLIGADO = {"enabled": False, "device_ativo": False, "despachando": False,
                   "bloqueio": "desligada"}

#: Os modos vivos, na forma do `state_full` que `mode_of_state` lê. O Sony
#: DualSense e o Xbox são o mesmo modo para a dica (a máscara não muda o destino).
_NAVEGACAO = {"native_mode": False, "gamepad_emulation": {"enabled": False},
              "mouse_emulation": _RATO_ANDANDO}
_DUALSENSE = {"native_mode": False, "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
              "mouse_emulation": _RATO_DESLIGADO}
_XBOX = {"native_mode": False, "gamepad_emulation": {"enabled": True, "flavor": "xbox"},
         "mouse_emulation": _RATO_DESLIGADO}
_NATIVO = {"native_mode": True, "gamepad_emulation": {"enabled": False},
           "mouse_emulation": _RATO_DESLIGADO}


def _o_que_o_servico_publica(tmp_path: Path, bruto: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """O bloco `mira` de cada controle, pelo `_merge_mira` do `IpcServer` real,"""
    controle = FakeController(transport="usb")  # type: ignore[arg-type]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(controller=controle, store=daemon.store, profile_manager=gerente,
                         socket_path=tmp_path / "publica.sock", daemon=daemon)
    gerente.apply_movimento(Profile.model_validate(bruto))
    entradas: list[dict[str, Any]] = [{"uniq": _P[n]} for n in (1, 2, 3, 4)]
    servidor._merge_mira(entradas)
    return {e["uniq"]: e["mira"] for e in entradas}


@pytest.mark.parametrize(("estado", "esperada"), [
    (_DUALSENSE, _DICA_NO_DIREITO),
    (_XBOX, _DICA_NO_DIREITO),
    (_NAVEGACAO, _DICA_NO_CURSOR),
    (_NATIVO, _DICA_DE_HOJE),
])
def test_a_dica_do_mouse_a_mao_diz_o_que_acontece_em_cada_modo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    estado: dict[str, Any], esperada: str,
) -> None:
    """O perfil com o «mouse» à mão no P3: o serviço publica o analógico direito,
    e a dica da aba 02 diz o que o modo faz com ele — sem frase nova.

    MORDIDA: apague o validador do esquema e o Sony DualSense e o Xbox voltam a
    dizer «move o cursor» sobre um giro que vai ao jogo.
    """
    import pacotes
    import pacotes.a02_controles as a02

    publicado = _o_que_o_servico_publica(
        tmp_path, _perfil_escrito_a_mao(por_controle={3: {"destino": "mouse"}}))
    assert publicado[_P[3]]["ligada"] is True
    assert publicado[_P[3]]["destino"] == "analogico_direito", publicado[_P[3]]
    monkeypatch.setattr(a02, "_so_se_a_pagina_tiver", lambda campos: campos)
    dele = {"uniq": _P[3], "transport": "bt", "connected": True, "inputs": {},
            "audio": {}, "speaker": {}, "mira": publicado[_P[3]]}
    ctx = pacotes.Contexto(state=estado, mesa=[], conectados=[dele], estados={})
    assert a02.pacote(ctx)["cards"][_P[3]]["giro-dica"] == esperada
