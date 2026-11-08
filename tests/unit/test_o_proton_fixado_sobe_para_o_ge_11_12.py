"""O Proton fixado sobe para o GE 11-12: o contrato lê o GE do disco, e o pad cabe no 11-12.

O-PROTON-FIXADO-SOBE-PARA-O-GE-11-12-01. Com a subida sozinha
(D-0811-O-PROTON-SE-ATUALIZA-SOZINHO), um teto digitado de «último GE medido» quebra a cada
lançamento; o contrato `ge-por-versao` passa a ler o script `proton` do GE instalado. E duas
mudanças do 11-12 tocam o pad virtual: o input report cortado no tamanho que o descritor
declara, e o XInput que só re-enumera quando um aparelho pode ter mudado (chegou ou saiu).

AS MORDIDAS: pôr de volta em `_fala_da_versao_do_ge` um teto de versão (o 11-8
avisa «posterior») reprova `test_o_ge_novo_sem_o_fallback_no_script_cala`; subir o
`_INPUT_PAYLOAD_SIZE` do `uhid_gamepad` para 64 reprova
`test_todo_input_report_do_pad_cabe_no_tamanho_declarado`; trocar o `UHID_DESTROY` do
`_destruir_o_device` por só fechar o fd reprova `test_o_pad_que_sai_e_volta_e_aparelho_novo`;
manter o pad de pé com a máscara mudada (a comparação do `flavor` em `start_gamepad_emulation`
trocada por ``True``) reprova `test_a_mascara_que_muda_desce_o_pad_e_sobe_outro`.
"""

from __future__ import annotations

import itertools
import struct
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import contratos_de_fora as cf
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_blueprint import (
    CANONICAL_DESCRIPTOR_USB,
    canonical_blueprint,
)

SCRIPT_DO_11_12 = '''
class Session:
    def setup(self, appid):
        if appid in [
                "1580240",  # Rune Factory 4 Special (#843)
                "3564740",  # Where Winds Meet (#829)
                ]:
            self.env.setdefault("PROTON_SONY_AUTO_XINPUT", "0")

        if appid in [
                "2420110",  # Horizon Forbidden West Complete Edition
                ]:
            self.env.setdefault("PROTON_SONY_WINDOWS_DEVICE_NAMES", "1")

    def init_session(self):
        # Keep native Sony HID available; XInput withdraws only its automatic
        # fallback when this process consumes native input or Steam Input owns it.
        self.env.setdefault("PROTON_SONY_AUTO_XINPUT", "1")
'''

SCRIPT_SEM_O_FALLBACK = '''
class Session:
    def setup(self, appid):
        if appid in ["3564740"]:
            self.env.setdefault("PROTON_SONY_AUTO_XINPUT", "0")
'''


def _casa(base: Path, pasta: str, script: str | None) -> cf.Ambiente:
    steam = base / "casa" / ".steam" / "steam"
    (steam / "config").mkdir(parents=True)
    alvo = steam / "compatibilitytools.d" / pasta
    alvo.mkdir(parents=True)
    if script is not None:
        (alvo / "proton").write_text(script, encoding="utf-8")
    (base / "raiz").mkdir()
    return cf.Ambiente(home=base / "casa", env={}, raiz=base / "raiz")


def _ge_por_versao(amb: cf.Ambiente) -> tuple[str, str]:
    contrato = next(c for c in cf.CONTRATOS if c.id == "ge-por-versao")
    ((tag, mensagem),) = cf.linhas_do_doctor(amb, [contrato])
    return tag, mensagem


def test_o_11_12_e_lido_no_script_e_avisa_o_fallback(tmp_path: Path) -> None:
    tag, mensagem = _ge_por_versao(_casa(tmp_path, "GE-Proton11-12-x86_64", SCRIPT_DO_11_12))
    assert tag == "[WARN]", mensagem
    assert "PROTON_SONY_AUTO_XINPUT=1 para todo jogo" in mensagem
    assert "posterior" not in mensagem and "não foi lido" not in mensagem


def test_o_ge_novo_sem_o_fallback_no_script_cala(tmp_path: Path) -> None:
    """D-0811-O-CONTRATO-DO-GE-LE-O-SCRIPT-INSTALADO."""
    amb = _casa(tmp_path, "GE-Proton12-30-x86_64", SCRIPT_SEM_O_FALLBACK)
    assert _ge_por_versao(amb)[0] == "[ OK ]"


def test_o_padrao_por_jogo_a_zero_nao_e_o_fallback_de_todo_jogo() -> None:
    valores = cf._valores_por_padrao(SCRIPT_DO_11_12, cf.ENV_DO_FALLBACK_XINPUT)
    assert valores == [("0", True), ("1", False)]


def test_o_script_que_nao_se_le_avisa_que_nao_foi_lido(tmp_path: Path) -> None:
    amb = _casa(tmp_path, "GE-Proton11-12-x86_64", "def quebrado(:\n")
    tag, mensagem = _ge_por_versao(amb)
    assert tag == "[WARN]" and "não se lê" in mensagem, mensagem


def test_o_contrato_nao_guarda_teto_de_versao() -> None:
    assert not [nome for nome in vars(cf) if nome.startswith("GE_ULTIMO")]


def _tamanhos_de_entrada(descritor: bytes) -> dict[int, int]:
    """``{report_id: bytes com o id}`` de cada input report que o descritor declara."""
    globais = {"tamanho": 0, "quantos": 0, "id": 0}
    bits: dict[int, int] = {}
    i = 0
    while i < len(descritor):
        prefixo = descritor[i]
        if prefixo == 0xFE:
            i += 3 + descritor[i + 1]
            continue
        largura = (0, 1, 2, 4)[prefixo & 0x03]
        valor = int.from_bytes(descritor[i + 1 : i + 1 + largura], "little")
        tipo, etiqueta = (prefixo >> 2) & 0x03, prefixo >> 4
        if tipo == 1 and etiqueta in (7, 8, 9):
            globais[{7: "tamanho", 8: "id", 9: "quantos"}[etiqueta]] = valor
        elif tipo == 0 and etiqueta == 8:
            bits[globais["id"]] = bits.get(globais["id"], 0) + globais["tamanho"] * globais[
                "quantos"]
        i += 1 + largura
    return {rid: total // 8 + (1 if rid else 0) for rid, total in bits.items()}


class _Uhid:
    def __init__(self) -> None:
        self.escritas: list[bytes] = []


@pytest.fixture()
def uhid(monkeypatch: pytest.MonkeyPatch) -> _Uhid:
    falso = _Uhid()
    monkeypatch.setattr(uhid_gamepad.os, "open", lambda *_a, **_k: 4242)
    monkeypatch.setattr(uhid_gamepad.os, "close", lambda _fd: None)
    monkeypatch.setattr(uhid_gamepad.os, "set_blocking", lambda _fd, _b: None)

    def escrever(_fd: int, dados: bytes) -> int:
        falso.escritas.append(bytes(dados))
        return len(dados)

    def ler(_fd: int, _n: int) -> bytes:
        raise BlockingIOError

    monkeypatch.setattr(uhid_gamepad.os, "write", escrever)
    monkeypatch.setattr(uhid_gamepad.os, "read", ler)
    return falso


def _entradas(escritas: list[bytes]) -> list[bytes]:
    saida = []
    for evento in escritas:
        tipo, tamanho = struct.unpack("<IH", evento[:6])
        if tipo == uhid_gamepad.UHID_INPUT2:
            saida.append(evento[6 : 6 + tamanho])
    return saida


def _tipos(escritas: list[bytes]) -> list[int]:
    return [struct.unpack("<I", evento[:4])[0] for evento in escritas]


def test_o_descritor_do_pad_declara_o_report_0x01_de_64_bytes() -> None:
    assert _tamanhos_de_entrada(CANONICAL_DESCRIPTOR_USB) == {0x01: 64}


def test_todo_input_report_do_pad_cabe_no_tamanho_declarado(uhid: _Uhid) -> None:
    """D-0811-O-CONTRATO-DO-GE-LE-O-SCRIPT-INSTALADO."""
    declarados = _tamanhos_de_entrada(CANONICAL_DESCRIPTOR_USB)
    pad = uhid_gamepad.UhidDualSense(player=1, blueprint=canonical_blueprint())
    assert pad.start() is True
    pad.forward_analog(lx=10, ly=250, rx=128, ry=128, l2=255, r2=3)
    pad.forward_buttons(frozenset({"cross", "ps", "dpad_up"}))
    pad.forward_motion(bytes(range(25)))
    pad.forward_touchpad_click(True)
    pad.forward_mic_button(True)
    pad.forward_battery(40, charging=True)
    reports = [*_entradas(uhid.escritas), uhid_gamepad._report_neutro(pad)]
    assert len(reports) >= 6, reports
    for report in reports:
        assert report[0] in declarados, report[:2]
        assert len(report) == declarados[report[0]], (report[0], len(report))
    pad.stop()


def test_o_pad_que_sai_e_volta_e_aparelho_novo(uhid: _Uhid) -> None:
    """D-0811-O-CONTRATO-DO-GE-LE-O-SCRIPT-INSTALADO."""
    pad = uhid_gamepad.UhidDualSense(player=2, blueprint=canonical_blueprint())
    assert pad.start() is True
    pad.forward_buttons(frozenset({"cross"}))
    pad.stop()
    assert pad.start() is True
    pad.stop()
    sequencia = [
        t for t in _tipos(uhid.escritas)
        if t in (uhid_gamepad.UHID_CREATE2, uhid_gamepad.UHID_DESTROY)
    ]
    assert sequencia == [
        uhid_gamepad.UHID_CREATE2,
        uhid_gamepad.UHID_DESTROY,
        uhid_gamepad.UHID_CREATE2,
        uhid_gamepad.UHID_DESTROY,
    ]


def test_a_mascara_que_muda_desce_o_pad_e_sobe_outro(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing import FakeController

    class _Pad:
        backend = "uhid"

        def __init__(self, flavor: str) -> None:
            self.flavor = flavor
            self.parou = False

        def stop(self) -> None:
            self.parou = True

    class _Coop:
        def sync(self, *, force: bool = False, origem: str | None = None) -> None: ...

        def disable(self) -> None: ...

        def player_count(self) -> int:
            return 1

    for alvo in ("save_gamepad_emulation", "save_mouse_emulation"):
        monkeypatch.setattr(f"hefesto_dualsense4unix.utils.session.{alvo}", lambda *a, **k: None)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env", lambda _d: None
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
        lambda flavor, **_kw: _Pad(str(flavor)),
    )
    daemon: Any = Daemon(
        controller=FakeController(transport="bt"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    daemon._coop_manager = _Coop()
    vistos = []
    for mascara in ("dualsense", "xbox", "nintendo", "dualsense"):
        assert daemon.set_gamepad_emulation(True, mascara, origin="manual") is True
        vistos.append(daemon._gamepad_device)
    assert all(a is not b and a.parou for a, b in itertools.pairwise(vistos))
    assert [p.flavor for p in vistos] == ["dualsense", "xbox", "nintendo", "dualsense"]
