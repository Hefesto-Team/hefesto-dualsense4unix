"""O pad veste o DualSense comum, e o Edge só quando o jogo pede.

A sprint O-PAD-VESTE-O-DUALSENSE-COMUM-E-O-EDGE-SO-QUANDO-O-JOGO-PEDE-01. Um teste por
cláusula da regra (docs/protocol/a-identidade-do-pad-virtual.md): o Edge quando o jogo nomeia o
Edge ou o caminho dele o pede (a biblioteca Sony, o Modo Xbox, a lista do Steam Input, a Launch
Option que esconde o `0ce6`); em todo outro caso, inclusive sem sinal nenhum, o `0ce6`. E a
volta inteira até a env que o jogo lê, com a leitura do disco de verdade.

MORDIDA: devolver a regra antiga em `_a_regra` (o `0ce6` só com `declarado.comum`) reprova o
«sem sinal», no `roupa_do_jogo`, no laço e na env.

Jogos de mentira em `tmp_path`, com os nomes medidos nos jogos de verdade (não cópia deles).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.numeros_da_sony import ROUPA_COMUM, ROUPA_PADRAO
from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.integrations import a_roupa_do_jogo as rj
from hefesto_dualsense4unix.integrations import cura_por_estrada, prontuario_dos_jogos
from hefesto_dualsense4unix.integrations.steam_launch_options import IGNORE_SIGNATURE

_METADATA = "Jogo_Data/il2cpp_data/Metadata/global-metadata.dat"
_REWIRED = "Jogo_Data/Managed/Rewired_Core.dll"
_ASSETS = "Jogo_Data/sharedassets0.assets"
_PERFIL_DO_COMUM = b"PlayStation5USBWindowsNativeProfile"
_PERFIL_DO_EDGE = b"PlayStation5EdgeUSBWindowsNativeProfile"
_HORI = b"HoriFightingEdgeArcadeStickPlayStation5NativeProfile"
_PID_DO_COMUM = b"\x4c\x05\xe6\x0c"
_PID_DO_EDGE = b"\x4c\x05\xf2\x0d"
_SEPARA = b"\0" * 12


def _u16(texto: str) -> bytes:
    return texto.encode("utf-16-le")


@pytest.fixture(autouse=True)
def _cache_limpo() -> Any:
    rj._CACHE.clear()
    rj._LIDO_EM.clear()
    yield
    rj._CACHE.clear()
    rj._LIDO_EM.clear()


def _jogo(raiz: Path, arquivos: dict[str, bytes]) -> Path:
    raiz.mkdir(parents=True)
    for relativo, conteudo in arquivos.items():
        caminho = raiz / relativo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(b"\0" + conteudo + b"\0")
    return raiz


_SEM_SINAL: dict[str, dict[str, bytes]] = {
    "pasta-vazia": {},
    "so-o-exe": {"Jogo.exe": b"MZ"},
    "so-hori": {_METADATA: _HORI, "Jogo.exe": b"MZ"},
    "sdl2-sem-edge": {"SDL2.dll": b"DualSense", "Jogo.exe": b"MZ"},
    "assets-sem-rewired": {_ASSETS: b"Sony DualSense", "Jogo.exe": b"MZ"},
}


@pytest.mark.parametrize("caso", sorted(_SEM_SINAL))
def test_o_jogo_sem_sinal_veste_o_comum(tmp_path: Path, caso: str) -> None:
    """Prova da D-3110-O-PAD-VESTE-O-COMUM-POR-PADRAO."""
    roupa, fonte = rj.roupa_do_jogo(_jogo(tmp_path / "Jogo", _SEM_SINAL[caso]))

    assert (roupa, fonte) == (rj.ROUPA_DO_COMUM, "nenhum sinal do controle: o DualSense comum")


_SO_O_COMUM: dict[str, dict[str, bytes]] = {
    "perfil-do-incontrol": {_METADATA: _PERFIL_DO_COMUM, "Jogo.exe": b"MZ"},
    "rewired": {_REWIRED: _u16("DualSenseDriver"), _ASSETS: b"Sony DualSense"},
    "pid-no-exe": {"Jogo.exe": b"MZ" + _PID_DO_COMUM},
}


@pytest.mark.parametrize("caso", sorted(_SO_O_COMUM))
def test_o_jogo_que_nomeia_so_o_comum_veste_o_comum(tmp_path: Path, caso: str) -> None:
    roupa, fonte = rj.roupa_do_jogo(_jogo(tmp_path / "Jogo", _SO_O_COMUM[caso]))

    assert roupa == rj.ROUPA_DO_COMUM, fonte
    assert "comum" in fonte and "nenhum sinal" not in fonte, "a fonte diz quem nomeou o comum"


_NOMEIA_O_EDGE: dict[str, dict[str, bytes]] = {
    "perfil-do-incontrol": {_METADATA: _PERFIL_DO_COMUM + b"\0" + _PERFIL_DO_EDGE},
    "rewired": {_REWIRED: _u16("DualSense Edge"), _ASSETS: b"Sony DualSense"},
    "sdl": {"SDL3.dll": b"DualSense Edge\0DualSense", "Jogo.exe": b"MZ"},
    "pid-no-exe": {"Jogo.exe": b"MZ" + _PID_DO_COMUM + _SEPARA + _PID_DO_EDGE},
}


@pytest.mark.parametrize("caso", sorted(_NOMEIA_O_EDGE))
def test_o_jogo_que_nomeia_o_edge_veste_o_edge(tmp_path: Path, caso: str) -> None:
    roupa, fonte = rj.roupa_do_jogo(_jogo(tmp_path / "Jogo", _NOMEIA_O_EDGE[caso]))

    assert roupa == rj.ROUPA_DO_EDGE, fonte
    assert "Edge" in fonte or "0DF2" in fonte, fonte


_BIBLIOTECA_SONY: dict[str, dict[str, bytes]] = {
    "libScePad": {"Jogo_Data/Plugins/libScePad.dll": b"x", _METADATA: _PERFIL_DO_COMUM},
    "scePad": {"Jogo.exe": b"MZ" + b"scePadOpen" + _SEPARA + _PID_DO_COMUM},
    "WinDualSense": {"Jogo.exe": b"MZ" + _u16("WinDualSense")},
    "WinDualShock": {"Jogo.exe": b"MZ" + _u16("WinDualShock") + _SEPARA + _PID_DO_COMUM},
}


@pytest.mark.parametrize("caso", sorted(_BIBLIOTECA_SONY))
def test_a_biblioteca_sony_veste_o_edge(tmp_path: Path, caso: str) -> None:
    """A biblioteca Sony procura o contêiner USB da háptica, e só o Edge sobe no gadget."""
    roupa, fonte = rj.roupa_do_jogo(_jogo(tmp_path / "Jogo", _BIBLIOTECA_SONY[caso]))

    assert roupa == rj.ROUPA_DO_EDGE, fonte
    assert fonte.startswith("a biblioteca Sony") and caso in fonte, fonte


_CAMINHO: dict[str, dict[str, Any]] = {
    "modo-xbox": {"modo_xbox": True},
    "steam-input": {"no_steam_input": True},
    "launch-option": {"opcoes_de_lancamento": f"{IGNORE_SIGNATURE} %command%"},
}


@pytest.mark.parametrize("nomeia", ["nada", "o-comum"])
@pytest.mark.parametrize("caminho", sorted(_CAMINHO))
def test_o_caminho_que_nao_mostra_o_comum_veste_o_edge(
    tmp_path: Path, caminho: str, nomeia: str
) -> None:
    arquivos = _SEM_SINAL["so-o-exe"] if nomeia == "nada" else _SO_O_COMUM["perfil-do-incontrol"]

    roupa, fonte = rj.roupa_do_jogo(_jogo(tmp_path / "Jogo", arquivos), **_CAMINHO[caminho])

    assert roupa == rj.ROUPA_DO_EDGE, fonte
    assert fonte == rj._o_caminho_pede_o_edge(
        _CAMINHO[caminho].get("opcoes_de_lancamento", ""),
        bool(_CAMINHO[caminho].get("no_steam_input")),
        bool(_CAMINHO[caminho].get("modo_xbox")),
    )


def _dois_jogos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `10` sem sinal nenhum e o `20` que nomeia o Edge, sem Steam de verdade."""
    sem_sinal = _jogo(tmp_path / "SemSinal", _SEM_SINAL["so-o-exe"])
    do_edge = _jogo(tmp_path / "DoEdge", _NOMEIA_O_EDGE["pid-no-exe"])
    monkeypatch.setattr(prontuario_dos_jogos, "jogos_instalados", lambda home=None: [
        ("10", "Sem sinal", sem_sinal), ("20", "Do Edge", do_edge)])
    monkeypatch.setattr(rj, "_opcoes_de_lancamento", lambda home: {})


@pytest.mark.parametrize("so_o_cache", [False, True], ids=["fora-do-laco", "no-laco"])
def test_o_laco_do_servico_da_o_comum_ao_jogo_sem_sinal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, so_o_cache: bool
) -> None:
    _dois_jogos(tmp_path, monkeypatch)
    if so_o_cache:
        rj.roupas_dos_jogos()

    roupas = rj.roupas_dos_jogos(so_o_cache=so_o_cache)

    assert {a: r for a, (r, _f) in roupas.items()} == {"10": "0ce6", "20": "0df2"}
    assert rj.roupas_dos_jogos(steam_input=["10"])["10"][0] == "0df2"
    assert rj.roupas_dos_jogos(modo_xbox=True)["10"][0] == "0df2"


def _daemon_uhid() -> SimpleNamespace:
    return SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=SimpleNamespace(backend="uhid"),
        _coop_manager=None,
        controller=SimpleNamespace(),
    )


def _valores(arquivo: Path) -> str:
    return "\n".join(
        linha for linha in arquivo.read_text(encoding="utf-8").splitlines()
        if not linha.startswith("#")
    ).lower()


def test_a_env_do_jogo_sem_sinal_veste_o_comum_e_esconde_so_o_fisico(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A roupa lida no disco chega à env que o wrapper entrega ao jogo, sem dublê da regra.

    O jogo sem sinal ganha a env do `0ce6`, com o par dele fora das listas (o físico fica
    escondido pelo broker), e o arme lê o `0ce6` na env; o jogo do Edge fica sem env própria.
    """
    _dois_jogos(tmp_path, monkeypatch)
    pasta = tmp_path / "launch_env"
    pasta.mkdir()
    agora = dt.datetime(2026, 10, 31, 3, 0, 0)
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: pasta)
    monkeypatch.setattr(le, "_ESCREVENTE", None)
    monkeypatch.setattr(le, "_dt", SimpleNamespace(datetime=SimpleNamespace(now=lambda: agora)))
    monkeypatch.setattr(le, "_receitas_dos_jogos", dict)
    monkeypatch.setattr(le, "_device_ks_nos_lancadores", dict)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(le, "_steam_profiles", lambda d: [])
    monkeypatch.setattr(cura_por_estrada, "curar_todas_as_estradas", lambda **k: [])
    monkeypatch.setattr(le, "_o_dono_esconde", lambda daemon: True)

    le.materialize_launch_env(_daemon_uhid())

    env = pasta / "steam_app_10.env"
    assert env.exists(), "o jogo sem sinal não ganhou a env do 0ce6"
    assert "0x054c/0x0ce6" not in _valores(env)
    assert "sdl_gamecontroller_ignore_devices=0x28de/0x11ff" in _valores(env)
    assert le.roupa_gravada(10, pasta) == ROUPA_COMUM
    assert not (pasta / "steam_app_20.env").exists()
    assert le.roupa_gravada(20, pasta) == ROUPA_PADRAO
