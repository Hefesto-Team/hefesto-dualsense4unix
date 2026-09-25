"""A-MIRA-NA-NAVEGACAO-02 — o destino que não anda, e o cartão «Só a janela».

As duas decisões são dela, por delegação (24/09/2026), pelo mesmo padrão: *a
tela nunca afirma o que não acontece*.

1. **O destino «mouse» fora da Navegação** (só por JSON à mão) não movia nada:
   o mouse emulado e o controle virtual se excluem, e a dica do Giroscópio
   dizia «move o cursor». O esquema passou a ler o «mouse» como o analógico
   direito (`ProfileMovimentoConfig._o_cursor_fora_da_navegacao_e_o_analogico_direito`);
   na Navegação todo destino ligado já é o cursor (`roteador.para_o_cursor`).
2. **O cartão de quem não navega** dizia «Só a janela» na aba 06 com a Mira
   acesa, e o giro dele movia o cursor do PC. Agora diz «Move o cursor»
   (`a06_navegacao.move_o_cursor`).

A RÉGUA MEDE O QUE O PRODUTO FAZ, e não só o que o esquema devolve: o `Daemon`,
o `IpcServer`, o `SensorHub`, o `CoopManager` e os DOIS controles virtuais de
verdade — o `UhidDualSense` (a máscara Sony DualSense) e o `UinputGamepad`
(a Xbox) —, com o nó do kernel de mentira nos dois. Nenhum nó de verdade
nasce aqui. Endereços da faixa SINTÉTICA da casa (``aa:bb:cc``).

OS QUATRO MODOS, e por que o Nativo não tem motor aqui: no Nativo não há
controle virtual nem mouse emulado, e o co-op não sobe
(`test_o_coop_vive_na_conexao_nativa.py`); o chip recusa
(`test_em_modo_nativo_a_resposta_diz_o_que_nao_alcanca`). O que o Nativo mostra
na tela — a dica e o cartão — está nas seções 4 e 5.

Cada régua diz a MORDIDA: o que arrancar para vê-la reprovar.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
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

#: Os quatro controles, na grafia do backend (com dois-pontos).
_P = {n: f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4)}
#: A chave de peça do perfil (doze hex), como o JSON à mão a escreveria.
_CHAVE = {n: f"aabbcc00000{n}" for n in (1, 2, 3, 4)}
#: Um giro de pulso no `yaw`, bem acima da zona morta e abaixo do teto.
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


# ---------------------------------------------------------------------------
# 1. O ESQUEMA — as três portas por onde o «mouse» entra
# ---------------------------------------------------------------------------


def test_o_mouse_escrito_a_mao_vira_o_analogico_direito(perfis: Path) -> None:
    """A seção do perfil, a peça de um controle e o ARQUIVO no disco: nas três
    o «mouse» sai analógico direito, e o resto do arranjo dela fica intacto.

    MORDIDA: apague o `_o_cursor_fora_da_navegacao_e_o_analogico_direito` do
    esquema e as três reprovam com `'mouse'`.
    """
    from hefesto_dualsense4unix.profiles.loader import load_profile

    secao = ProfileMovimentoConfig.model_validate({"destino": "mouse", "sensibilidade": 9})
    assert (secao.destino, secao.sensibilidade) == ("analogico_direito", 9)
    peca = ControllerOverrides.model_validate({"movimento": {"destino": "mouse"}})
    assert peca.movimento is not None and peca.movimento.destino == "analogico_direito"
    # O ARQUIVO À MÃO: o caminho que o JSON dela faz de verdade.
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
    """Só o «mouse» é lido de outro jeito: o esquerdo continua o esquerdo e o
    desligado continua desligado.

    MORDIDA: faça o validador devolver sempre o analógico direito e o esquerdo
    e o desligado reprovam.
    """
    assert ProfileMovimentoConfig(destino=destino).destino == destino  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. O MOTOR FORA DA NAVEGAÇÃO — Sony DualSense e Xbox, P1 a P4, USB e BT
# ---------------------------------------------------------------------------


class _NoDoUinput:
    """O nó `uinput` de mentira do `UinputGamepad`: guarda cada `write`, na
    ordem, e não tem evento de volta (`read_one` é `None`)."""

    def __init__(self) -> None:
        self.escritas: list[tuple[int, int, int]] = []

    def write(self, tipo: int, codigo: int, valor: int) -> None:
        self.escritas.append((tipo, codigo, valor))

    def syn(self) -> None:
        pass

    def read_one(self) -> None:
        return None


#: O blueprint mínimo do `UhidDualSense` — o molde de `test_uhid_gamepad.py`,
#: com o MAC FORJADO da faixa sintética no feature 0x09.
_BLUEPRINT = {
    "descriptor": bytes([0x05, 0x01, 0x09, 0x05, 0xA1, 0x01]),
    "features": {
        0x05: bytes([0x05]) + bytes(40),
        0x09: bytes([0x09]) + bytes.fromhex("010000ccbbaa") + bytes(13),
        0x20: bytes([0x20]) + bytes(63),
    },
}


class _NoDoUhid:
    """O `/dev/uhid` de mentira: um descritor por vpad, cada escrita guardada.

    Só os descritores DELE são desviados — todo o resto do processo continua
    falando com o `os` de verdade (a régua monta um `Daemon` inteiro, e ele
    escreve arquivos no lar de mentira da suíte).
    """

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
    """Fábrica dos controles virtuais das duas máscaras; os uhid morrem no fim
    (o `stop` devolve o MAC que o registro dos vpads vivos guarda)."""
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
    """O `Daemon` real com o controle virtual de pé: o P1 pelo `dispatch_gamepad`
    e os P2 a P4 pelo `CoopManager.forward_all`, os quatro girando igual.

    O perfil entra pelo `model_validate` do dicionário cru — o caminho do
    arquivo à mão — e pelo `ProfileManager.apply_movimento` do produto.
    """
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
    for _ in range(2):  # a demanda abre o leitor; a segunda volta lê o giro
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
    """O «mouse» escrito à mão na peça do jogador N: o analógico direito do
    controle virtual DELE anda, e só o dele. O esquerdo fica no centro.

    MORDIDA: apague o validador do esquema e os dezesseis casos reprovam com o
    analógico direito parado — o giro ia a um mouse emulado que não existe.
    """
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
    """O «mouse» na mira do PERFIL inteiro: os quatro analógicos direitos andam.

    MORDIDA: a mesma do esquema.
    """
    bruto = _perfil_escrito_a_mao(mesa={"destino": "mouse"})
    vpads = _mesa_com_controle_virtual(monkeypatch, tmp_path, transporte, mascara,
                                       bruto, vpads_de_verdade)
    eixos = _quem_mirou(vpads, vpads_de_verdade.uhid)
    assert all(e["rx"] != _CENTRO for e in eixos.values()), (
        f"{mascara}/{transporte}: a mira da mesa no «mouse» não moveu os quatro: {eixos}")


# ---------------------------------------------------------------------------
# 3. NA NAVEGAÇÃO CONTINUA O CURSOR
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("jogador", [1, 2, 3, 4])
def test_na_navegacao_o_mouse_escrito_a_mao_continua_o_cursor(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    jogador: int, transporte: str,
) -> None:
    """O mesmo «mouse» à mão, na Navegação: o cursor anda o giro de UM controle,
    o dele, e nada vira rolagem.

    MORDIDA: faça o validador ler o «mouse» como `nenhum` e os oito casos
    reprovam com o cursor parado.
    """
    bruto = _perfil_escrito_a_mao(por_controle={jogador: {"destino": "mouse"}})
    nav = _navegacao(tmp_path, monkeypatch, transporte, perfil=Profile.model_validate(bruto))
    assert _ate_andar(nav) == (_PX_POR_TIQUE, 0), f"P{jogador}/{transporte}"
    u = nav.mouse._uinput_mod
    assert not [e for e in nav.no.eventos if e[0] in (u.REL_WHEEL, u.REL_HWHEEL)]


def test_na_navegacao_a_peca_de_chip_apagado_drena(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A DRENAGEM VEM ANTES DO PORTÃO DA PEÇA, no caminho que o produto alcança.

    A mira do perfil no «mouse» (à mão) e o P4 com o chip apagado: os três
    outros movem o cursor, e o P4 DESCARTA o próprio ângulo a cada tique em vez
    de guardá-lo para um salto no dia em que voltar a seguir o perfil. Conta as
    drenagens, não o efeito.

    MORDIDA: ponha o `return` da peça que não mira ANTES da drenagem em
    `gamepad.aplicar_o_movimento` e o P4 reprova.
    """
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


# ---------------------------------------------------------------------------
# 4. O QUE O SERVIÇO PUBLICA E A DICA DO GIROSCÓPIO DIZ — os quatro modos
# ---------------------------------------------------------------------------
#: AS FRASES, por extenso: a régua confere o pacote contra o que o produto faz.
_DICA_DE_HOJE = "Ligado: o jogo recebe o giro deste controle."
_DICA_NO_DIREITO = ("Com a Mira Virtual acesa, o giro deste controle vai ao jogo "
                    "pelo analógico direito.")
_DICA_NO_CURSOR = "Com a Mira Virtual acesa, o giro deste controle move o cursor."

#: O bloco `mouse_emulation` como o daemon o publica
#: (`ipc_handlers._mouse_emulation_payload`): o interruptor, o device e o
#: `despachando`/`bloqueio` do dono único (`_bloqueio_da_emulacao_de_desktop`).
#: A CONFERÊNCIA achou o dublê anterior mais frouxo que o daemon: ele só tinha o
#: `enabled`, e o cartão lia o sinal mais fraco.
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
    """O bloco `mira` de cada controle, pelo `_merge_mira` do `IpcServer` real,
    depois de o perfil à mão passar pelo `apply_movimento` do produto."""
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


# ---------------------------------------------------------------------------
# 5. O CARTÃO DA ABA 06 — o pacote, e a página renderizada
# ---------------------------------------------------------------------------
_PAPEL_QUE_NAVEGA = "Navega o PC"
_PAPEL_SO_A_JANELA = "Só a janela"
_PAPEL_DO_CURSOR = "Move o cursor"

#: As duas mesas de transporte: cada jogador passa pelo USB e pelo BT.
_MESAS = {"A": {1: "usb", 2: "bt", 3: "bt", 4: "usb"},
          "B": {1: "bt", 2: "usb", 3: "usb", 4: "bt"}}


def _estado_da_06(modo: dict[str, Any], mesa: str, quem_navega: int,
                  com_a_mira: set[int], sem_giroscopio: set[int] | None = None,
                  ) -> dict[str, Any]:
    """O `state_full` da 06: quatro controles, o primário marcado, a Mira acesa
    em quem a régua escolher (o bloco `mira` que o `_merge_mira` publica), e o
    giroscópio de cada um como o `_merge_sensores` o publica — o leitor aberto
    (`inputs.gyro`) e o interruptor (`sensores.giroscopio_ligado`), desligado
    em quem estiver em `sem_giroscopio`."""
    controles = []
    for n, transporte in _MESAS[mesa].items():
        acesa = n in com_a_mira
        controles.append({
            "uniq": _P[n], "player": n, "player_slot": n, "index": n - 1,
            "connected": True, "is_primary": n == quem_navega, "transport": transporte,
            "battery_pct": 80,
            "inputs": {"lx": _CENTRO, "ly": _CENTRO, "rx": _CENTRO, "ry": _CENTRO,
                       "gyro": {"x": 0.1, "y": -0.2, "z": 0.05}},
            "sensores": {"giroscopio_ligado": n not in (sem_giroscopio or set()),
                         "acelerometro_ligado": True},
            "mira": {"ligada": acesa, "destino": "analogico_direito" if acesa else "nenhum"},
        })
    return {**modo, "controllers": controles,
            "keyboard_emulation": {"enabled": True, "osk_disponivel": False}}


def _a_carga_da_06(estado: dict[str, Any]) -> dict[str, Any]:
    """A carga que o piloto manda à página, montada como `Piloto._contexto` monta."""
    import mesa_viva
    import pacotes

    mesa = mesa_viva.mesa_do_estado(estado, {})
    para_pref = {str(c.get("uniq") or ""): c["pref"] for c in mesa}
    ctx = pacotes.Contexto(state=estado, mesa=mesa, conectados=estado["controllers"],
                           estados={})
    pacote = pacotes.pacote_da_pagina("06-navegacao.html", ctx)
    assert pacote is not None
    return pacotes.normalizar(pacote, para_pref)


def _texto(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def _linhas_do_pacote(estado: dict[str, Any]) -> dict[int, str]:
    colunas = _a_carga_da_06(estado)["colunas"]
    return {n: _texto(colunas[f"p{n}"]["navega"]) for n in (1, 2, 3, 4)}


def _via(mesa: str, n: int) -> str:
    return "USB" if _MESAS[mesa][n] == "usb" else "BT"


#: Os casos da matriz: cada jogador fora do posto de quem navega, nos dois
#: transportes. O P1 só sai do posto com o P2 navegando.
_CASOS = [(mesa, quem_navega, n) for mesa in _MESAS
          for quem_navega, jogadores in ((1, (2, 3, 4)), (2, (1,))) for n in jogadores]


@pytest.mark.parametrize(("mesa", "quem_navega", "jogador"), _CASOS)
def test_o_cartao_de_quem_nao_navega_diz_o_cursor_com_a_mira(
    mesa: str, quem_navega: int, jogador: int,
) -> None:
    """Na Navegação, com o mouse ligado, a Mira acesa no jogador N: o cartão dele
    diz «Move o cursor», o de quem navega diz «Navega o PC» e os outros dois,
    «Só a janela». Sem bolinha verde no cartão novo: o verde é de quem navega.

    MORDIDA: devolva sempre «Só a janela» em `linha_do_cartao` para quem não
    navega e os oito casos reprovam.
    """
    estado = _estado_da_06(_NAVEGACAO, mesa, quem_navega, {jogador})
    linhas = _linhas_do_pacote(estado)
    for n, linha in linhas.items():
        papel = (_PAPEL_QUE_NAVEGA if n == quem_navega
                 else _PAPEL_DO_CURSOR if n == jogador else _PAPEL_SO_A_JANELA)
        assert linha == f"{_via(mesa, n)} • {papel}", (mesa, quem_navega, jogador, linhas)
    carga = _a_carga_da_06(estado)
    assert "bolinha" not in carga["colunas"][f"p{jogador}"]["navega"]


@pytest.mark.parametrize(("nome", "modo"), [
    ("mouse desligado", {**_NAVEGACAO, "mouse_emulation": _RATO_DESLIGADO}),
    # O INTERRUPTOR LIGADO NÃO BASTA — a conferência, 25/09/2026. Nos três o
    # `enabled` segue `true` e o tique da Navegação não roda
    # (`lifecycle._poll_loop`): o PS segurado (modo jogo), o `/dev/uinput` sem
    # permissão e o jogo com a entrada calando o desktop.
    ("modo jogo", {**_NAVEGACAO, "mouse_emulation": {
        **_RATO_ANDANDO, "despachando": False, "bloqueio": "modo_jogo"}}),
    ("sem o mouse virtual", {**_NAVEGACAO, "mouse_emulation": {
        **_RATO_ANDANDO, "device_ativo": False, "despachando": False,
        "bloqueio": "sem_device"}}),
    ("o jogo com a entrada", {**_NAVEGACAO, "mouse_emulation": {
        **_RATO_ANDANDO, "despachando": False,
        "bloqueio": "vpad_suspenso_pelo_steam_input"}}),
    ("Sony DualSense", _DUALSENSE),
    ("Xbox", _XBOX),
    ("Nativo", _NATIVO),
    ("sem resposta do mouse", {"native_mode": False, "gamepad_emulation": {"enabled": False}}),
    # O MODO VENCE A PREFERÊNCIA DO MOUSE. O serviço desliga o mouse ao sair da
    # Navegação (`mouse.stop_mouse_emulation` zera `mouse_emulation_enabled`),
    # e o cartão não depende dessa ordem: quem diz para onde vai o giro é o
    # modo (`mode_of_state`), o mesmo leitor da dica do Giroscópio.
    ("Sony DualSense com o mouse ainda ligado",
     {**_DUALSENSE, "mouse_emulation": _RATO_ANDANDO}),
    ("Nativo com o mouse ainda ligado", {**_NATIVO, "mouse_emulation": _RATO_ANDANDO}),
])
def test_fora_do_cursor_o_cartao_continua_so_a_janela(nome: str, modo: dict[str, Any]) -> None:
    """A MESMA Mira acesa nos quatro, onde o giro NÃO vai ao cursor: o cartão de
    quem não navega continua «Só a janela», e o de quem navega, «Navega o PC».

    MORDIDA: tire a pergunta `_na_navegacao` de `move_o_cursor` e os dois casos
    do mouse ainda ligado reprovam; tire a do `mouse_emulation` e reprovam o
    mouse desligado, os três bloqueios e o mouse sem resposta; troque o
    `despachando` pelo `enabled` e reprovam os três bloqueios.
    """
    linhas = _linhas_do_pacote(_estado_da_06(modo, "A", 1, {1, 2, 3, 4}))
    assert linhas == {1: f"USB • {_PAPEL_QUE_NAVEGA}", 2: f"BT • {_PAPEL_SO_A_JANELA}",
                      3: f"BT • {_PAPEL_SO_A_JANELA}", 4: f"USB • {_PAPEL_SO_A_JANELA}"}, (
        nome, linhas)


def test_sem_leitura_da_mira_o_cartao_nao_afirma_o_cursor() -> None:
    """Um controle sem o bloco `mira` (o serviço ainda não publicou): «Só a
    janela». Afirmação sem leitura é chute.

    MORDIDA: troque o `is not True` de `move_o_cursor` por `is False`.
    """
    estado = _estado_da_06(_NAVEGACAO, "A", 1, set())
    for c in estado["controllers"]:
        c.pop("mira")
    assert _linhas_do_pacote(estado)[3] == f"BT • {_PAPEL_SO_A_JANELA}"


@pytest.mark.parametrize(("mesa", "quem_navega", "jogador"), _CASOS)
def test_com_o_giroscopio_desligado_o_cartao_nao_afirma_o_cursor(
    mesa: str, quem_navega: int, jogador: int,
) -> None:
    """A Mira acesa nos quatro, e o chip Giroscópio do jogador N DESLIGADO por
    ela: o giro dele não chega ao cursor (`gamepad.aplicar_o_movimento` para no
    `REGISTRO.estado(uniq).giroscopio`, medido em
    `test_a_mira_na_navegacao.test_o_giroscopio_desligado_nao_move_o_cursor`), e
    o cartão dele diz «Só a janela»; os outros dois que não navegam seguem
    «Move o cursor». Do P1 ao P4, USB e BT.

    Achado da conferência (25/09/2026): no piloto, com o Giroscópio do P2
    desligado pela aba Controles, a 06 dizia «BT • Move o cursor».

    MORDIDA: tire a pergunta do giroscópio de `move_o_cursor` e os oito casos
    reprovam.
    """
    estado = _estado_da_06(_NAVEGACAO, mesa, quem_navega, {1, 2, 3, 4},
                           sem_giroscopio={jogador})
    linhas = _linhas_do_pacote(estado)
    for n, linha in linhas.items():
        papel = (_PAPEL_QUE_NAVEGA if n == quem_navega
                 else _PAPEL_SO_A_JANELA if n == jogador else _PAPEL_DO_CURSOR)
        assert linha == f"{_via(mesa, n)} • {papel}", (mesa, quem_navega, jogador, linhas)


@pytest.mark.parametrize("sem", ["o interruptor", "o leitor de movimento"])
def test_sem_leitura_do_giroscopio_o_cartao_nao_afirma_o_cursor(sem: str) -> None:
    """Sem o bloco `sensores` (ninguém leu o interruptor) ou sem `inputs.gyro`
    (o controle sem leitor de movimento — o motor não tem velocidade para
    mover): «Só a janela». Afirmação sem leitura é chute.

    MORDIDA: troque o `is not True` do interruptor por `is False`, ou tire a
    pergunta do `gyro_do_inputs`, e o caso correspondente reprova.
    """
    estado = _estado_da_06(_NAVEGACAO, "A", 1, {3})
    dele = next(c for c in estado["controllers"] if c["uniq"] == _P[3])
    if sem == "o interruptor":
        dele.pop("sensores")
    else:
        dele["inputs"].pop("gyro")
    assert _linhas_do_pacote(estado)[3] == f"BT • {_PAPEL_SO_A_JANELA}", sem


# --- a página renderizada: o WebKit, o BOOTSTRAP do piloto, as duas páginas ---

_PILOTO = RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
_PAGINAS = {
    "bancada": RAIZ / "mockup/06-navegacao.html",
    "publicada": RAIZ / "src/hefesto_dualsense4unix/interface/paginas/06-navegacao.html",
}


def _bootstrap() -> str:
    """O BOOTSTRAP lido do FONTE do piloto, e não importado."""
    fonte = _PILOTO.read_text(encoding="utf-8")
    achou = re.search(r'^BOOTSTRAP = r"""(.*?)"""$', fonte, re.S | re.M)
    assert achou, "o piloto perdeu o BOOTSTRAP — não há o que testar"
    return achou.group(1)


_LER = r"""
(function(){
  const fora = {};
  for (const pref of ['p1','p2','p3','p4']) {
    const card = document.querySelector('.nav-mesa [data-controle="' + pref + '"]');
    const linha = card ? card.querySelector('[data-campo="navega"]') : null;
    fora[pref] = linha ? (linha.innerText || '').replace(/\s+/g, ' ').trim() : null;
    fora['vazia_' + pref] = card ? card.classList.contains('vazia') : null;
  }
  return fora;
})()
"""


def _roteiro(cenarios: list[tuple[str, dict[str, Any]]]) -> str:
    """Pinta cada cenário na página, na ordem, e lê a linha dos quatro cartões."""
    passos = "".join(
        f"window.__hef.pintar({json.dumps(carga, ensure_ascii=False)});"
        f"saida[{json.dumps(nome)}] = {_LER};"
        for nome, carga in cenarios)
    return f"(function(){{const saida = {{}};{passos}return JSON.stringify(saida);}})()"


def _cenarios_da_pagina() -> list[tuple[str, dict[str, Any]]]:
    cenarios = [(f"{mesa}-{quem_navega}-{n}",
                 _a_carga_da_06(_estado_da_06(_NAVEGACAO, mesa, quem_navega, {n})))
                for mesa, quem_navega, n in _CASOS]
    cenarios.append(("nativo", _a_carga_da_06(_estado_da_06(_NATIVO, "A", 1, {1, 2, 3, 4}))))
    # O P1 E O P3 NA MESA, o P2 e o P4 fora: a casca de vazio vai para quem saiu.
    dois = _estado_da_06(_NAVEGACAO, "A", 1, {3})
    dois["controllers"] = [c for c in dois["controllers"] if c["uniq"] in (_P[1], _P[3])]
    cenarios.append(("dois", _a_carga_da_06(dois)))
    return cenarios


@pytest.fixture(scope="module")
def renderizada() -> dict[str, dict[str, dict[str, str | None]]]:
    """As duas páginas da 06 num WebKit offscreen, pintadas pela carga do pacote."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    roteiro = _roteiro(_cenarios_da_pagina())
    medidas: dict[str, dict[str, dict[str, str | None]]] = {}
    for nome, onde in _PAGINAS.items():
        saiu: list[str] = []
        janela = Gtk.OffscreenWindow()
        view = WebKit2.WebView()
        view.set_size_request(1280, 900)
        janela.add(view)
        janela.show_all()

        def guardou(v: Any, res: Any, saiu: list[str] = saiu) -> None:
            try:
                saiu.append(v.evaluate_javascript_finish(res).to_string())
            except Exception as e:  # a exceção É a resposta desta ponte
                saiu.append(f"ERRO {e}")
            Gtk.main_quit()

        def instalou(v: Any, res: Any, saiu: list[str] = saiu) -> None:
            try:
                v.evaluate_javascript_finish(res)
            except Exception as e:
                saiu.append(f"ERRO no bootstrap: {e}")
                Gtk.main_quit()
                return
            v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

        def carregou(v: Any, evento: Any) -> None:
            if evento == WebKit2.LoadEvent.FINISHED:
                v.evaluate_javascript(_bootstrap(), -1, None, None, None, instalou)

        view.connect("load-changed", carregou)
        view.load_uri(onde.as_uri())
        guarda = GLib.timeout_add(20000, Gtk.main_quit)
        try:
            Gtk.main()
        finally:
            GLib.source_remove(guarda)
            janela.destroy()
        assert saiu, f"o WebKit não respondeu em 20 s na {nome}"
        assert not saiu[0].startswith("ERRO"), saiu[0]
        medidas[nome] = json.loads(saiu[0])
    return medidas


@pytest.mark.parametrize("onde", sorted(_PAGINAS))
@pytest.mark.parametrize(("mesa", "quem_navega", "jogador"), _CASOS)
def test_a_pagina_renderizada_diz_o_cursor(
    renderizada: dict[str, dict[str, dict[str, str | None]]],
    onde: str, mesa: str, quem_navega: int, jogador: int,
) -> None:
    """A carga do pacote pintada pelo BOOTSTRAP do piloto, na bancada e na
    publicada: o cartão do jogador N diz «Move o cursor», do P1 ao P4, USB e BT.

    MORDIDA: a mesma do pacote; e tire o `data-hef-alvo="html"` da linha do
    cartão no gerador, e a bancada reprova (a linha vira texto cru).
    """
    lido = renderizada[onde][f"{mesa}-{quem_navega}-{jogador}"]
    for n in (1, 2, 3, 4):
        papel = (_PAPEL_QUE_NAVEGA if n == quem_navega
                 else _PAPEL_DO_CURSOR if n == jogador else _PAPEL_SO_A_JANELA)
        assert lido[f"p{n}"] == f"{_via(mesa, n)} • {papel}", (onde, mesa, lido)


@pytest.mark.parametrize("onde", sorted(_PAGINAS))
def test_no_nativo_a_pagina_renderizada_nao_fala_do_cursor(
    renderizada: dict[str, dict[str, dict[str, str | None]]], onde: str,
) -> None:
    """Com a Mira acesa nos quatro, no Nativo: ninguém diz «Move o cursor»."""
    lido = renderizada[onde]["nativo"]
    assert _PAPEL_DO_CURSOR not in " ".join(str(v) for v in lido.values()), lido


@pytest.mark.parametrize("onde", sorted(_PAGINAS))
def test_o_lugar_com_dono_perde_a_cara_de_vazio(
    renderizada: dict[str, dict[str, dict[str, str | None]]], onde: str,
) -> None:
    """O P3 e o P4 nascem `nav-ctl vazia` no desenho. Com os quatro na mesa,
    nenhum cartão fica esmaecido; com o P1 e o P3, o P2 e o P4 ficam — e o P3
    diz «Move o cursor» com a casca de quem está na mesa.

    MORDIDA: tire a chave `vazia` das marcas do lugar no pacote da 06 e o P3 e
    o P4 conectados reprovam, esmaecidos como se tivessem saído.
    """
    quatro = renderizada[onde]["A-1-3"]
    assert [quatro[f"vazia_p{n}"] for n in (1, 2, 3, 4)] == [False] * 4, quatro
    dois = renderizada[onde]["dois"]
    assert [dois[f"vazia_p{n}"] for n in (1, 2, 3, 4)] == [False, True, False, True], dois
    assert dois["p3"] == f"BT • {_PAPEL_DO_CURSOR}", dois
