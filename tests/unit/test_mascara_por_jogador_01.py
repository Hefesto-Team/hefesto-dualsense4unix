"""MÁSCARA-POR-JOGADOR-01 — a máscara é do JOGADOR, o jogo é o padrão herdado."""
from __future__ import annotations

import ast
import struct
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
    ExternalMaskRegistry,
    _zerar_registro_de_mascaras,
    mascara_efetiva,
    registro_de_mascaras,
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

_SRC = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"


@pytest.fixture(autouse=True)
def _hermetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``config_dir`` em tmp + registro do processo ZERADO antes e depois."""
    from hefesto_dualsense4unix.utils import xdg_paths

    target = tmp_path / "config"

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    _zerar_registro_de_mascaras()
    yield target
    _zerar_registro_de_mascaras()


def test_a_mascara_escolhida_do_jogador_vence_a_do_jogo() -> None:
    """A garantia 1. Sem ela, a D-5 não existe: a escolha do usuário seria enfeite."""
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    assert mascara_efetiva(MAC_P2, "xbox") == "dualsense"
    registro_de_mascaras().set_mask(MAC_P3, "xbox")
    assert mascara_efetiva(MAC_P3, "dualsense") == "xbox"


def test_sem_escolha_o_jogador_herda_a_mascara_do_jogo() -> None:
    """A garantia 2 — e é ela que torna o recurso seguro diante do risco não medido."""
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    assert mascara_efetiva(MAC_P1, "xbox") == "xbox"
    assert mascara_efetiva(MAC_P1, "dualsense") == "dualsense"
    assert mascara_efetiva(None, "dualsense") == "dualsense"


def test_a_mascara_do_externo_volatil_vale_na_sessao() -> None:
    """O 8BitDo/Pro degradado tem máscara também — a regra "universal" de 09/08."""
    registro_de_mascaras().set_mask(IDENTIDADE_VOLATIL, "dualsense")
    assert mascara_efetiva(IDENTIDADE_VOLATIL, "xbox") == "dualsense"


def test_a_escolha_invalida_nao_vira_mascara_e_o_jogador_segue_herdando() -> None:
    """Lixo não escolhe máscara por ninguém (ESCOLHA-DELA-VENCE-01)."""
    assert registro_de_mascaras().set_mask(MAC_P2, "wiimote") is False
    assert mascara_efetiva(MAC_P2, "xbox") == "xbox"


def test_a_divergencia_escolhida_nao_derruba_o_vpad() -> None:
    """O P2 escolheu DualSense numa sessão Xbox: o vpad dele SOBREVIVE.

    Este é o lado novo. Hoje `coop.py`:417-424 derrubaria este vpad a cada tick
    — e o jogador ficaria num laço de nascer e morrer.
    """
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    assert vpad_ficou_para_tras("dualsense", MAC_P2, "xbox") is False


def test_o_flavor_que_ficou_para_tras_ainda_derruba_o_vpad() -> None:
    """O lado VELHO, que não pode morrer: senão volta `P2+ preso no flavor antigo`."""
    assert vpad_ficou_para_tras("xbox", MAC_P1, "dualsense") is True

    registro_de_mascaras().set_mask(MAC_P2, "xbox")
    assert vpad_ficou_para_tras("dualsense", MAC_P2, "xbox") is True

    assert vpad_ficou_para_tras(None, MAC_P1, "xbox") is True


def test_a_mesa_heterogenea_derruba_so_quem_ficou_para_tras() -> None:
    """O laço do co-op inteiro, com quatro jogadores, numa asserção só."""
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")
    registro_de_mascaras().set_mask(IDENTIDADE_VOLATIL, "dualsense")
    mesa = {
        MAC_P1: "xbox",
        MAC_P2: "dualsense",
        MAC_P3: "dualsense",
        IDENTIDADE_VOLATIL: "xbox",
    }

    caem = {
        identidade
        for identidade, flavor in mesa.items()
        if vpad_ficou_para_tras(flavor, identidade, "xbox")
    }

    assert caem == {MAC_P3, IDENTIDADE_VOLATIL}


def test_duas_instancias_do_registro_divergem_e_por_isso_existe_o_singleton() -> None:
    """A razão MEDIDA de :func:`registro_de_mascaras` — não é preguiça de injeção."""
    escritora = ExternalMaskRegistry()
    leitora = ExternalMaskRegistry()
    leitora.load()

    escritora.set_mask(MAC_P2, "dualsense")

    assert escritora.mask_for(MAC_P2) == "dualsense"
    assert leitora.mask_for(MAC_P2) is None

    assert registro_de_mascaras() is registro_de_mascaras()
    registro_de_mascaras().set_mask(MAC_P3, "dualsense")
    assert mascara_efetiva(MAC_P3, "xbox") == "dualsense"


# A-MASCARA-DO-PAD-SE-DECIDE-SO-NA-FABRICA-01 (10/10/2026): a máscara de cada pad
# se decide uma vez, em `make_virtual_pad`. Os construtores recebem a chave já
# resolvida; as réguas abaixo passam pela fábrica e conferem o VID e o PID que o
# jogo vê, sem `/dev/uinput` nem `/dev/uhid`.

_INTEGRACOES = _SRC / "integrations"
_LEITURAS_DO_REGISTRO = frozenset({"mascara_efetiva", "registro_de_mascaras"})


def _quem_le_o_registro(pasta: Path) -> set[str]:
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
            if nomes & _LEITURAS_DO_REGISTRO:
                leitores.add(modulo.name)
    return leitores


def test_so_a_fabrica_decide_a_mascara_dentro_das_integracoes() -> None:
    """Dono único: um construtor que relê o registro é uma segunda decisão."""
    assert _quem_le_o_registro(_INTEGRACOES) == {"virtual_pad.py"}


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
def test_o_p2_que_escolheu_dualsense_numa_sessao_xbox_nasce_dualsense_edge() -> None:
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    pad = make_virtual_pad("xbox", identity=MAC_P2, player=2)

    assert isinstance(pad, UhidDualSense)
    assert _vid_pid_no_kernel(pad) == (DUALSENSE_VENDOR, DUALSENSE_EDGE_PRODUCT)


@pytest.mark.usefixtures("_sem_no_de_kernel")
def test_o_p2_que_escolheu_dualsense_sem_uhid_guarda_o_cartao_e_veste_o_xbox_360() -> None:
    """O mesmo jogador com o uhid vetado: o cartão fica, e o jogo vê o Xbox 360.

    A pergunta 6 da NO-MODO-XBOX-TUDO-FUNCIONA-01 (13/10): o Edge no `uinput`, sem
    hidraw, o Proton não usa; até o canal voltar, o pad é o Xbox 360.
    """
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    pad = make_virtual_pad("xbox", identity=MAC_P2, player=2, allow_uhid=False)

    assert isinstance(pad, UinputGamepad)
    assert pad.flavor == "dualsense"
    assert _vid_pid_no_kernel(pad) == (XBOX360_VENDOR, XBOX360_PRODUCT)


@pytest.mark.usefixtures("_sem_no_de_kernel")
def test_o_p1_sem_escolha_numa_sessao_xbox_nasce_xbox_360() -> None:
    """O vizinho de mesa do P2 não muda de máscara junto com ele."""
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    pad = make_virtual_pad("xbox", identity=MAC_P1, player=1)

    assert isinstance(pad, UinputGamepad)
    assert pad.flavor == "xbox"
    assert _vid_pid_no_kernel(pad) == (XBOX360_VENDOR, XBOX360_PRODUCT)


@pytest.mark.usefixtures("_sem_no_de_kernel")
def test_o_p2_que_escolheu_xbox_numa_sessao_dualsense_nasce_no_uinput_como_xbox() -> None:
    """Sem isto, o jogador marcado Xbox ganharia um DualSense Edge HID no kernel."""
    registro_de_mascaras().set_mask(MAC_P2, "xbox")

    pad = make_virtual_pad("dualsense", identity=MAC_P2, player=2)

    assert isinstance(pad, UinputGamepad)
    assert pad.flavor == "xbox"
    assert _vid_pid_no_kernel(pad) == (XBOX360_VENDOR, XBOX360_PRODUCT)


@pytest.mark.usefixtures("_sem_no_de_kernel")
def test_sem_identidade_o_pad_nasce_na_mascara_do_jogo() -> None:
    """`identity=None` = "não sei de quem é este pad" = a máscara do JOGO."""
    registro_de_mascaras().set_mask(MAC_P1, "dualsense")
    registro_de_mascaras().set_mask(MAC_P2, "xbox")

    xbox = make_virtual_pad("xbox", player=1)
    dualsense = make_virtual_pad("dualsense", player=2)

    assert _vid_pid_no_kernel(xbox) == (XBOX360_VENDOR, XBOX360_PRODUCT)
    assert isinstance(dualsense, UhidDualSense)
    assert _vid_pid_no_kernel(dualsense) == (DUALSENSE_VENDOR, DUALSENSE_EDGE_PRODUCT)


def test_os_construtores_vestem_a_chave_que_recebem() -> None:
    """A escolha registrada não muda o que o construtor faz com a chave dada."""
    registro_de_mascaras().set_mask(MAC_P1, "dualsense")
    registro_de_mascaras().set_mask(MAC_P2, "xbox")

    assert UinputGamepad.for_flavor("xbox").flavor == "xbox"
    assert UinputGamepad.for_flavor("dualsense").flavor == "dualsense"
    assert UhidDualSense.for_flavor("xbox", player=1) is None
    assert UhidDualSense.for_flavor("dualsense", player=2, identity=MAC_P2) is not None
    assert UhidDualSense.for_flavor(None, player=1) is not None


def test_a_frase_de_10_08_vale_so_para_o_mode() -> None:
    """A decisão de 15/08 mora no esquema, não só no documento."""
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    doc = ControllerOverrides.__doc__ or ""

    assert "e a máscara do gamepad são da SESSÃO" not in doc, (
        "a frase de 10/08 voltou a valer para a máscara. Ela a reescreveu em "
        "15/08/2026: vale só para o `mode`."
    )
    assert "``mode`` é da SESSÃO" in doc
    assert "15/08/2026" in doc, "decisão reescrita sem data não se sustenta"
    assert "external_mask.py" in doc


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
