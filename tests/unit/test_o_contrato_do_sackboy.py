"""O contrato do Sackboy: o que o jogo em que tudo funciona recebe do Hefesto.

A trava da A-IDENTIDADE-DO-PAD-VIRTUAL-E-UMA-REGRA-SO-01, escrita ANTES da regra nova e
verde na base `29c489469`: a roupa, o VID:PID, o nome, o descritor, a env gravada, o
caminho do gadget, a vibração, a luz e os gatilhos. Os valores são os de 22/10/2026 (a env
é a do `steam_app_1599660.env` lido naquele dia). Se a cura de qualquer sprint mudar um
deles, a sprint para e a pergunta vai a ela: o Sackboy é o jogo de referência do DualSense.

O jogo é de mentira, com os sinais medidos no executável do Sackboy (a biblioteca
`WinDualSense` e os dois pares `054c:0ce6` e `054c:0df2`), nunca cópia do arquivo.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import struct
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.numeros_da_sony import ROUPA_EDGE, ROUPA_PADRAO, VENDOR_SONY
from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.integrations import a_roupa_do_jogo as rj
from hefesto_dualsense4unix.integrations import cura_por_estrada, pad_usb, uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_blueprint import canonical_blueprint
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile, ProfileModeConfig
from tests.unit.test_o_broker_veste_o_pid_que_o_pad_pede import Gravador, gravador  # noqa: F401
from tests.unit.test_uhid_replica import (
    _BLOCO_L,
    _BLOCO_R,
    _edge_report,
    _FakeFd,
    _output_event,
    _pad_em_sessao,
    _Sinks,
    fake_uhid,  # noqa: F401
)

SACKBOY = 1599660
JOGADORES = (1, 2, 3, 4)

#: Os sinais que o executável do Sackboy traz (medidos em 22/10/2026 pela `ficha_declarada`).
_EXE_DO_SACKBOY = (
    b"MZ\0" + "WinDualSense".encode("utf-16-le")
    + b"\0\0\x4c\x05\xe6\x0c\0\0\0\0\0\0\0\0\0\0\0\0\x4c\x05\xf2\x0d\0"
)

#: A env do Sackboy em 22/10/2026, 20h07 (`steam_app_1599660.env`), sem o cabeçalho.
ENV_DO_SACKBOY: dict[str, str] = {
    "PROTON_DISABLE_HIDRAW": "0x054C/0x0CE6",
    "SDL_GAMECONTROLLER_IGNORE_DEVICES": "0x054c/0x0ce6,0x28de/0x11ff",
    "__GL_SHADER_DISK_CACHE": "1",
    "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP": "1",
    "SDL_GAMECONTROLLER_USE_BUTTON_LABELS": "0",
    "SDL_ACCELEROMETER_AS_JOYSTICK": "0",
    "PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE": "1",
    "PROTON_ENABLE_MHWILDS_USB_AUDIO": "1",
}

#: O descritor e os features que o pad do Sackboy apresenta (o blueprint canônico).
SHA_DO_DESCRITOR = "4f48767516627510521512af13c20a064877465122b7bcc7cac1f3b608d37994"
SHA_DOS_FEATURES = {
    0x05: "f8ca61e4506db188bfcb51ed5e1b6069b0ce1c531928fb7ca8e9342e77c3bfff",
    0x20: "017f562e62570b840906a4c78ebfd4bd834d0f931e3c7112c84f04349806fc56",
}


@pytest.fixture(autouse=True)
def _cache_limpo() -> Any:
    rj._CACHE.clear()
    yield
    rj._CACHE.clear()


def _o_sackboy(tmp_path: Path) -> Path:
    raiz = tmp_path / "SackboyAdventure"
    exe = raiz / "GameApp" / "Binaries" / "Win64" / "GameApp-Win64-Shipping.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(_EXE_DO_SACKBOY)
    return raiz


# --- 1. A roupa ------------------------------------------------------------------


def test_o_sackboy_veste_o_edge(tmp_path: Path) -> None:
    raiz = _o_sackboy(tmp_path)

    assert rj.roupa_do_jogo(raiz) == ("0df2", "o executável conhece o modelo 0DF2 do Edge")
    for extras in ({"no_steam_input": True}, {"modo_xbox": True}):
        assert rj.roupa_do_jogo(raiz, **extras)[0] == "0df2", extras


# --- 2. O VID:PID, o nome e o descritor ------------------------------------------


@pytest.mark.parametrize("jogador", JOGADORES)
def test_o_pad_do_sackboy_e_o_edge_de_hoje(jogador: int) -> None:
    blueprint = canonical_blueprint()
    pad = uhid_gamepad.UhidDualSense.for_flavor(
        "dualsense", player=jogador, blueprint=blueprint,
        identity=f"aa:bb:cc:00:00:{jogador:02x}", roupa=ROUPA_EDGE)
    assert pad is not None
    evento = pad._create2_event(blueprint["descriptor"])
    nome = evento[4:132].rstrip(b"\0").decode()
    tamanho, barramento = struct.unpack("<HH", evento[260:264])
    vendor, produto, versao, _pais = struct.unpack("<IIII", evento[264:280])
    descritor = evento[280:280 + tamanho]

    assert nome == f"DualSense Wireless Controller (Hefesto P{jogador})"
    assert evento[132:196].rstrip(b"\0") == b"hefesto-vpad"
    assert (vendor, produto, versao, barramento) == (VENDOR_SONY, 0x0DF2, 0x0100, 0x03)
    assert (tamanho, hashlib.sha256(descritor).hexdigest()) == (289, SHA_DO_DESCRITOR)
    for numero, sha in SHA_DOS_FEATURES.items():
        assert hashlib.sha256(blueprint["features"][numero]).hexdigest() == sha, hex(numero)


# --- 3. A env gravada --------------------------------------------------------------


@pytest.mark.parametrize("vpads", [1, 2, 4])
def test_a_env_do_sackboy_e_a_de_hoje(vpads: int) -> None:
    base: dict[str, Any] = {"native_mode": False, "emulation_enabled": True, "flavor": "dualsense",
                            "backends": ["uhid"] * vpads, "fisicos": vpads}

    assert le.compose_env(**base) == ENV_DO_SACKBOY
    assert le.compose_env(**base, roupa=ROUPA_EDGE) == ENV_DO_SACKBOY


def _perfil_do_sackboy() -> Profile:
    return Profile(
        name="Sackboy",
        match=MatchCriteria(window_class=[f"steam_app_{SACKBOY}"]),
        priority=80,
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
    )


def _daemon_uhid() -> SimpleNamespace:
    return SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=SimpleNamespace(backend="uhid"),
        _coop_manager=None,
        controller=SimpleNamespace(),
    )


@pytest.mark.parametrize("dono", [False, True], ids=["sem-o-dono", "com-o-dono"])
def test_o_arquivo_do_sackboy_sai_o_de_hoje(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dono: bool
) -> None:
    pasta = tmp_path / "launch_env"
    pasta.mkdir()
    raiz = _o_sackboy(tmp_path)
    agora = dt.datetime(2026, 10, 22, 20, 7, 16)
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: pasta)
    monkeypatch.setattr(le, "_ESCREVENTE", None)
    monkeypatch.setattr(le, "_dt", SimpleNamespace(datetime=SimpleNamespace(now=lambda: agora)))
    monkeypatch.setattr(le, "_receitas_dos_jogos", dict)
    monkeypatch.setattr(le, "_device_ks_nos_lancadores", dict)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(le, "_steam_profiles", lambda d: [(SACKBOY, _perfil_do_sackboy())])
    monkeypatch.setattr(le, "_o_dono_esconde", lambda daemon: dono)
    monkeypatch.setattr(cura_por_estrada, "curar_todas_as_estradas", lambda **k: [])
    monkeypatch.setattr(rj, "roupas_dos_jogos",
                        lambda home=None, **k: {str(SACKBOY): rj.roupa_do_jogo(raiz)})

    le.materialize_launch_env(_daemon_uhid())

    texto = (pasta / f"steam_app_{SACKBOY}.env").read_text(encoding="utf-8")
    valores = dict(
        linha.split("=", 1) for linha in texto.splitlines() if linha and not linha.startswith("#"))
    assert valores == ENV_DO_SACKBOY
    assert "# roupa:" not in texto, "o Edge nunca leva a linha da roupa"
    assert le.roupa_gravada(SACKBOY, pasta) == ROUPA_PADRAO == ROUPA_EDGE


# --- 4. O caminho: o Edge sobe no gadget, com a quirk do físico no lugar ------------


@pytest.mark.parametrize("jogador", JOGADORES)
def test_o_pad_do_sackboy_pede_o_gadget(
    gravador: Gravador, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,  # noqa: F811
    jogador: int,
) -> None:
    quirks = tmp_path / "quirks"
    quirks.write_text("054c:0ce6:gn\n", encoding="ascii")
    monkeypatch.setattr(uhid_gamepad, "QUIRK_DO_PAR",
                        lambda par: pad_usb.o_par_tem_a_quirk_que_atrasa(par, str(quirks)))
    pad = uhid_gamepad.UhidDualSense(
        player=jogador, product=ROUPA_EDGE, blueprint=canonical_blueprint(),
        identity=f"aa:bb:cc:00:00:{jogador:02x}")
    try:
        assert pad.start() is True
    finally:
        pad.stop()

    assert [(p["vendor"], p["product"]) for p in gravador.pedidos] == [(VENDOR_SONY, ROUPA_EDGE)]


# --- 5. A vibração, a luz e os gatilhos que o jogo escreve -------------------------


def test_o_que_o_sackboy_escreve_chega_ao_controle(fake_uhid: _FakeFd) -> None:  # noqa: F811
    sinks = _Sinks()
    pad, relogio = _pad_em_sessao(fake_uhid, product=ROUPA_EDGE, **sinks.kwargs())
    fake_uhid.reads.append(_output_event(_edge_report(flag0=0x03, weak=0x40, strong=0xC0)))
    fake_uhid.reads.append(_output_event(_edge_report(
        flag0=0x0C, flag1=0x14, trigger_r=_BLOCO_R, trigger_l=_BLOCO_L,
        rgb=(0, 0, 255), player_mask=0x04)))

    pad.pump_ff()
    relogio.t += 1.0
    pad.pump_ff()

    assert sinks.rumbles == [(0x40, 0xC0)]
    assert sorted(sinks.triggers) == [("left", _BLOCO_L), ("right", _BLOCO_R)]
    assert sinks.cores == [(0, 0, 255)]
    assert sinks.players == [(False, False, True, False, False)]
