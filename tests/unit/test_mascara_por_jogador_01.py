"""MÁSCARA-POR-JOGADOR-01 — a máscara de cada jogador é o modo único.

NOTA DATADA, 27/10/2026: a máscara era do JOGADOR (15/08, D-5), com o jogo como padrão
herdado. Desde a D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES ela é o modo único, igual
para os quatro: a identidade continua chegando à fábrica (para o pad saber de quem é), e
não muda mais a máscara de ninguém.

MORDIDA: devolva à `mascara_efetiva` a leitura por identidade, e o vizinho com outra
máscara reprova.
"""
from __future__ import annotations

import ast
import struct
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
    mascara_efetiva,
    vpad_ficou_para_tras,
)
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    DUALSENSE_EDGE_PRODUCT,
    DUALSENSE_VENDOR,
    XBOX360_PRODUCT,
    XBOX360_VENDOR,
    UinputGamepad,
)
from hefesto_dualsense4unix.integrations.virtual_pad import make_virtual_pad

MAC_P1 = "aa:bb:cc:00:00:01"
MAC_P2 = "aa:bb:cc:00:00:02"
MAC_P3 = "aa:bb:cc:00:00:03"

IDENTIDADE_VOLATIL = "dev:0003:057E:2009.0001"
JOGADORES = (MAC_P1, MAC_P2, MAC_P3, IDENTIDADE_VOLATIL)

_SRC = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"


@pytest.mark.parametrize("modo", ["dualsense", "xbox", "nintendo"])
def test_os_quatro_jogadores_recebem_o_modo_unico(modo: str) -> None:
    for quem in (*JOGADORES, None):
        assert mascara_efetiva(quem, modo) == modo, quem


def test_o_vpad_fora_do_modo_unico_fica_para_tras_em_toda_vaga() -> None:
    """O juiz do co-op derruba quem não está no modo de todos, e só ele."""
    mesa = {MAC_P1: "xbox", MAC_P2: "dualsense", MAC_P3: "xbox", IDENTIDADE_VOLATIL: "dualsense"}
    caem = {quem for quem, flavor in mesa.items() if vpad_ficou_para_tras(flavor, quem, "xbox")}
    assert caem == {MAC_P2, IDENTIDADE_VOLATIL}
    assert vpad_ficou_para_tras(None, MAC_P1, "xbox") is True


_INTEGRACOES = _SRC / "integrations"
_LEITURAS_DA_MASCARA = frozenset({"mascara_efetiva"})


def _quem_le_a_mascara(pasta: Path) -> set[str]:
    """Os módulos de `pasta` que chamam ou importam a decisão da máscara."""
    leitores: set[str] = set()
    for modulo in sorted(pasta.glob("*.py")):
        arvore = ast.parse(modulo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom):
                nomes = {alias.name for alias in no.names}
            elif isinstance(no, ast.Call):
                alvo = no.func
                nomes = {alvo.attr if isinstance(alvo, ast.Attribute) else getattr(alvo, "id", "")}
            else:
                continue
            if nomes & _LEITURAS_DA_MASCARA:
                leitores.add(modulo.name)
    return leitores


def test_so_a_fabrica_decide_a_mascara_dentro_das_integracoes() -> None:
    """Dono único: um construtor que relê a máscara é uma segunda decisão."""
    assert _quem_le_a_mascara(_INTEGRACOES) == {"virtual_pad.py"}


def _vid_pid_no_kernel(pad: Any) -> tuple[int, int]:
    """O VID e o PID com que o nó nasce: o do `uinput` e o do `UHID_CREATE2`."""
    if isinstance(pad, UhidDualSense):
        evento = pad._create2_event(b"")
        inicio = 4 + 128 + 64 + 64 + 4
        vendor, product = struct.unpack("<II", evento[inicio : inicio + 8])
        return vendor, product
    return pad.vendor, pad.product


@pytest.fixture
def _sem_no_de_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fábrica de verdade, com os dois nós de kernel de mentira."""
    monkeypatch.setattr(UinputGamepad, "start", lambda self: True)
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: True)
    monkeypatch.setattr(UhidDualSense, "start", lambda self: True)
    monkeypatch.setattr(UhidDualSense, "wait_for_bind", lambda self, timeout_s=2.0: True)


@pytest.mark.usefixtures("_sem_no_de_kernel")
@pytest.mark.parametrize("quem", JOGADORES)
def test_no_modo_xbox_todo_jogador_nasce_xbox_360(quem: str) -> None:
    pad = make_virtual_pad("xbox", identity=quem, player=2)

    assert isinstance(pad, UinputGamepad)
    assert pad.flavor == "xbox"
    assert _vid_pid_no_kernel(pad) == (XBOX360_VENDOR, XBOX360_PRODUCT)


@pytest.mark.usefixtures("_sem_no_de_kernel")
@pytest.mark.parametrize("quem", JOGADORES)
def test_no_modo_dualsense_todo_jogador_nasce_dualsense_edge(quem: str) -> None:
    pad = make_virtual_pad("dualsense", identity=quem, player=2)

    assert isinstance(pad, UhidDualSense)
    assert _vid_pid_no_kernel(pad) == (DUALSENSE_VENDOR, DUALSENSE_EDGE_PRODUCT)


@pytest.mark.usefixtures("_sem_no_de_kernel")
def test_o_dualsense_sem_uhid_guarda_a_mascara_e_veste_o_xbox_360() -> None:
    """A pergunta 6 da NO-MODO-XBOX-TUDO-FUNCIONA-01 (13/10): o Edge no `uinput`, sem
    hidraw, o Proton não usa; até o canal voltar, o pad é o Xbox 360."""
    pad = make_virtual_pad("dualsense", identity=MAC_P2, player=2, allow_uhid=False)

    assert isinstance(pad, UinputGamepad)
    assert pad.flavor == "dualsense"
    assert _vid_pid_no_kernel(pad) == (XBOX360_VENDOR, XBOX360_PRODUCT)


def test_os_construtores_vestem_a_chave_que_recebem() -> None:
    assert UinputGamepad.for_flavor("xbox").flavor == "xbox"
    assert UinputGamepad.for_flavor("dualsense").flavor == "dualsense"
    assert UhidDualSense.for_flavor("xbox", player=1) is None
    assert UhidDualSense.for_flavor("dualsense", player=2, identity=MAC_P2) is not None
    assert UhidDualSense.for_flavor(None, player=1) is not None


def _chama_make_virtual_pad_com_identidade(modulo: Path) -> bool:
    """``make_virtual_pad(...)`` deste módulo passa ``identity=``?"""
    arvore = ast.parse(modulo.read_text(encoding="utf-8"))
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        nome = alvo.attr if isinstance(alvo, ast.Attribute) else getattr(alvo, "id", "")
        if nome != "make_virtual_pad":
            continue
        if any(kw.arg == "identity" for kw in no.keywords):
            return True
    return False


def test_o_ultimo_degrau_da_mascara_por_jogador_chegou() -> None:
    """O degrau CHEGOU em 29/08/2026 — e daqui para frente não pode sair."""
    assert _chama_make_virtual_pad_com_identidade(
        _SRC / "daemon" / "subsystems" / "coop.py"
    ), "coop.py não passa a identidade do jogador ao criar o vpad"
    assert _chama_make_virtual_pad_com_identidade(
        _SRC / "daemon" / "subsystems" / "gamepad.py"
    ), "gamepad.py não passa a identidade do primário ao criar o vpad"
