"""O pad veste a identidade que o jogo obedece: a camada 2 do MMJ, o identificador.

A sprint O-PAD-VIRTUAL-VESTE-A-IDENTIDADE-QUE-O-JOGO-OBEDECE-01. Jogos de mentira em
`tmp_path`, com os nomes medidos no Mullet MadJack e nos jogos do Rewired e da SDL (os
nomes, não cópia dos arquivos).
"""
from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.numeros_da_sony import ROUPA_COMUM, ROUPA_PADRAO
from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon import lifecycle as lc
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import a_roupa_do_jogo as rj
from hefesto_dualsense4unix.integrations import cura_por_estrada
from hefesto_dualsense4unix.integrations.steam_launch_options import IGNORE_SIGNATURE
from hefesto_dualsense4unix.profiles.schema import (
    MatchCriteria,
    Profile,
    ProfileModeConfig,
)

_METADATA = "Jogo_Data/il2cpp_data/Metadata/global-metadata.dat"
_INCONTROL = "Jogo_Data/Managed/InControl.dll"
_REWIRED = "Jogo_Data/Managed/Rewired_Core.dll"
_ASSETS = "Jogo_Data/sharedassets0.assets"

#: Os perfis que o `global-metadata.dat` do MMJ traz, e os dois falsos amigos do Hori.
_PERFIS_DO_COMUM = b"\0".join([
    b"InControl.NativeDeviceProfiles",
    b"PlayStation5USBWindowsNativeProfile",
    b"PlayStation5BluetoothWindowsNativeProfile",
    b"PlayStation4WindowsNativeProfile",
    b"SDLPlayStation5NativeProfile",
    b"DualSenseMFiNativeProfile",
])
_HORI = b"\0".join([
    b"HoriEdgeFightingStickWindowsNativeProfile",
    b"HoriFightingEdgeArcadeStickPlayStation5NativeProfile",
])
_PERFIL_DO_EDGE = b"PlayStation5EdgeUSBWindowsNativeProfile"


def _u16(texto: str) -> bytes:
    return texto.encode("utf-16-le")


@pytest.fixture(autouse=True)
def _cache_limpo() -> Any:
    rj._CACHE.clear()
    yield
    rj._CACHE.clear()


def _jogo(tmp_path: Path, arquivos: dict[str, bytes]) -> Path:
    raiz = tmp_path / "Jogo"
    raiz.mkdir(exist_ok=True)
    for relativo, conteudo in arquivos.items():
        caminho = raiz / relativo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(b"\0" + conteudo + b"\0")
    return raiz


@pytest.mark.parametrize("onde", [_METADATA, _INCONTROL])
def test_o_incontrol_so_do_comum_veste_o_0ce6(tmp_path: Path, onde: str) -> None:
    raiz = _jogo(tmp_path, {onde: _PERFIS_DO_COMUM + b"\0" + _HORI, "Jogo.exe": b"MZ"})

    roupa, fonte = rj.roupa_do_jogo(raiz)

    assert roupa == rj.ROUPA_DO_COMUM, fonte
    assert Path(onde).name in fonte, "a fonte nomeia o arquivo que declarou"


@pytest.mark.parametrize(
    ("arquivos", "esperada"),
    [
        ({_METADATA: _PERFIS_DO_COMUM + b"\0" + _PERFIL_DO_EDGE}, "0df2"),
        ({_METADATA: _PERFIS_DO_COMUM, _INCONTROL: b"DualSenseEdgeNativeProfile"}, "0df2"),
        ({_METADATA: _PERFIS_DO_COMUM + b"\0" + _HORI}, "0ce6"),
        ({_METADATA: _HORI}, "0df2"),
        ({_METADATA: _PERFIS_DO_COMUM, "Jogo.exe": b"MZ\x4c\x05\xf2\x0d"}, "0df2"),
        ({"Jogo.exe": b"MZ\x4c\x05\xe6\x0c"}, "0ce6"),
        ({"Jogo.exe": b"MZ\x4c\x05\xe6\x0c\0\0\x4c\x05\xf2\x0d"}, "0df2"),
    ],
    ids=["perfil-do-edge", "edge-no-mono", "hori-nao-conta", "so-hori",
         "pid-do-edge", "pid-do-comum", "os-dois-pids"],
)
def test_o_sinal_do_edge_ganha(
    tmp_path: Path, arquivos: dict[str, bytes], esperada: str
) -> None:
    roupa, fonte = rj.roupa_do_jogo(_jogo(tmp_path, arquivos))

    assert roupa == esperada, fonte


@pytest.mark.parametrize(
    ("arquivos", "esperada"),
    [
        ({_REWIRED: _u16("DualSenseDriver"), _ASSETS: b"Sony DualSense"}, "0ce6"),
        ({_REWIRED: _u16("DualSense Edge"), _ASSETS: b"Sony DualSense"}, "0df2"),
        ({_REWIRED: b"DualSenseDriver", _ASSETS: b"Sony DualSense Edge"}, "0df2"),
        ({_ASSETS: b"Sony DualSense"}, "0df2"),
        ({"SDL3.dll": b"DualSense Edge\0DualSense", _METADATA: _PERFIS_DO_COMUM}, "0df2"),
        ({"SDL2.dll": b"DualSense"}, "0df2"),
    ],
    ids=["rewired-comum", "rewired-edge-na-dll", "rewired-edge-no-assets",
         "assets-sem-rewired", "sdl3-com-edge", "sdl2-sem-edge"],
)
def test_o_rewired_e_a_sdl(tmp_path: Path, arquivos: dict[str, bytes], esperada: str) -> None:
    roupa, fonte = rj.roupa_do_jogo(_jogo(tmp_path, arquivos))

    assert roupa == esperada, fonte


@pytest.mark.parametrize(
    ("arquivos", "extras"),
    [
        ({}, {}),
        ({"Jogo_Data/Plugins/libScePad.dll": b"x"}, {}),
        ({"Jogo_Data/Plugins/libScePad.dll": b"x", _METADATA: _PERFIS_DO_COMUM}, {}),
        ({_METADATA: _PERFIS_DO_COMUM}, {"opcoes_de_lancamento": f"{IGNORE_SIGNATURE} %command%"}),
        ({_METADATA: _PERFIS_DO_COMUM}, {"no_steam_input": True}),
        ({_METADATA: _PERFIS_DO_COMUM}, {"modo_xbox": True}),
    ],
    ids=["pasta-vazia", "so-libscepad", "libscepad-ganha-do-incontrol",
         "launch-option-envenenada", "steam-input", "modo-xbox"],
)
def test_sem_sinal_fica_o_edge(
    tmp_path: Path, arquivos: dict[str, bytes], extras: dict[str, Any]
) -> None:
    roupa, fonte = rj.roupa_do_jogo(_jogo(tmp_path, arquivos), **extras)

    assert roupa == rj.ROUPA_DO_EDGE, fonte


@pytest.mark.parametrize("decrescente", [False, True], ids=["crescente", "decrescente"])
def test_o_sharedassets0_entra_mesmo_com_muitos_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, decrescente: bool
) -> None:
    import os

    arquivos = {f"Jogo_Data/sharedassets{n}.assets": b"cena" for n in range(1, 30)}
    arquivos |= {_REWIRED: b"DualSenseDriver", _ASSETS: b"Sony DualSense"}
    raiz = _jogo(tmp_path, arquivos)
    de_verdade = os.scandir

    class _NaOrdem(list[Any]):
        def __enter__(self) -> _NaOrdem:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    def na_ordem(pasta: Any) -> Any:
        with de_verdade(pasta) as entradas:
            return _NaOrdem(sorted(entradas, key=lambda e: e.name, reverse=decrescente))

    monkeypatch.setattr(os, "scandir", na_ordem)
    roupa, fonte = rj.roupa_do_jogo(raiz)

    assert roupa == "0ce6" and "sharedassets0" in fonte, (
        "o InputManager do Rewired mora no sharedassets0 (Scarlet Deer Inn, Spirit Valley)")


def test_no_laco_so_o_cache_e_o_fio_aquece(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading

    from hefesto_dualsense4unix.integrations import prontuario_dos_jogos

    raiz = _jogo(tmp_path, {_METADATA: _PERFIS_DO_COMUM})
    monkeypatch.setattr(prontuario_dos_jogos, "jogos_instalados", lambda home=None: [
        ("10", "Jogo", raiz)])
    monkeypatch.setattr(rj, "_opcoes_de_lancamento", lambda home: {})
    aqueceu = threading.Event()

    assert rj.roupas_dos_jogos(so_o_cache=True, ao_aquecer=aqueceu.set) == {}, (
        "o laço do serviço nunca espera o disco")
    assert aqueceu.wait(10), "o fio da roupa não avisou"
    assert rj.roupas_dos_jogos(so_o_cache=True)["10"][0] == "0ce6"


def test_a_roupa_que_aquece_pede_outra_escrita() -> None:
    daemon = SimpleNamespace(_launch_env_assinatura=("velha",), _launch_env_sossego_em=None)

    le._a_roupa_aqueceu(daemon)

    assert daemon._launch_env_assinatura is None
    assert daemon._launch_env_sossego_em is not None


def test_a_roupa_sai_em_cache_pela_assinatura(tmp_path: Path) -> None:
    raiz = _jogo(tmp_path, {_METADATA: _PERFIS_DO_COMUM})
    assert rj.roupa_do_jogo(raiz)[0] == "0ce6"

    (raiz / _METADATA).write_bytes(_PERFIS_DO_COMUM + b"\0" + _PERFIL_DO_EDGE)

    assert rj.roupa_do_jogo(raiz)[0] == "0df2", "o arquivo mudou e o cache não viu"


def test_nao_ha_tabela_por_appid() -> None:
    arvore = ast.parse(Path(rj.__file__).read_text(encoding="utf-8"))
    suspeitos = [
        no.value
        for no in ast.walk(arvore)
        if isinstance(no, ast.Constant)
        and (
            (isinstance(no.value, int) and not isinstance(no.value, bool) and no.value > 255)
            or (isinstance(no.value, str) and no.value.isdigit() and len(no.value) >= 3)
        )
    ]
    assert suspeitos == [], "a roupa sai do binário, nunca de uma lista de appids"


# ---------------------------------------------------------------------------
# A env do jogo


_COM_PERFIL = 111
_SEM_PERFIL = 222
_DO_EDGE = 333


def _perfil(appid: int) -> Profile:
    return Profile(
        name=f"jogo_{appid}",
        match=MatchCriteria(window_class=[f"steam_app_{appid}"]),
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


@pytest.fixture
def lancamento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    pasta = tmp_path / "launch_env"
    pasta.mkdir()
    agora = dt.datetime(2026, 10, 22, 12, 0, 0)
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: pasta)
    monkeypatch.setattr(le, "_ESCREVENTE", None)
    monkeypatch.setattr(le, "_dt", SimpleNamespace(datetime=SimpleNamespace(now=lambda: agora)))
    monkeypatch.setattr(le, "_receitas_dos_jogos", dict)
    monkeypatch.setattr(le, "_device_ks_nos_lancadores", dict)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(le, "_steam_profiles", lambda d: [(_COM_PERFIL, _perfil(_COM_PERFIL))])
    monkeypatch.setattr(cura_por_estrada, "curar_todas_as_estradas", lambda **k: [])
    monkeypatch.setattr(
        rj,
        "roupas_dos_jogos",
        lambda home=None, **k: {
            str(_COM_PERFIL): ("0ce6", "global-metadata.dat declara só o DualSense comum"),
            str(_SEM_PERFIL): ("0ce6", "InControl.dll declara só o DualSense comum"),
            str(_DO_EDGE): ("0df2", "nenhum sinal do controle: o Edge de hoje"),
        },
    )
    return pasta


def _valores(arquivo: Path) -> str:
    return "\n".join(
        linha for linha in arquivo.read_text(encoding="utf-8").splitlines()
        if not linha.startswith("#")
    ).lower()


def test_a_env_do_jogo_segue_a_roupa(lancamento: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(le, "_o_dono_esconde", lambda daemon: False)
    le.materialize_launch_env(_daemon_uhid())
    padrao_de_hoje = (lancamento / "default.env").read_bytes()
    assert "0x054c/0x0ce6" in _valores(lancamento / f"steam_app_{_COM_PERFIL}.env")
    assert not (lancamento / f"steam_app_{_SEM_PERFIL}.env").exists(), (
        "sem o broker, a env sai a de hoje")

    rancoso = lancamento / "steam_app_999.env"
    rancoso.write_text("X=1\n", encoding="utf-8")
    monkeypatch.setattr(le, "_o_dono_esconde", lambda daemon: True)
    le.materialize_launch_env(_daemon_uhid())

    for appid in (_COM_PERFIL, _SEM_PERFIL):
        arquivo = lancamento / f"steam_app_{appid}.env"
        assert arquivo.exists(), f"o {appid} do 0ce6 sumiu na limpeza dos rançosos"
        assert "0x054c/0x0ce6" not in _valores(arquivo), appid
        assert "sdl_gamecontroller_ignore_devices=0x28de/0x11ff" in _valores(arquivo), appid
        assert le.roupa_gravada(appid, lancamento) == ROUPA_COMUM, appid
    assert not (lancamento / f"steam_app_{_DO_EDGE}.env").exists()
    assert le.roupa_gravada(_DO_EDGE, lancamento) == ROUPA_PADRAO
    assert not rancoso.exists()
    assert (lancamento / "default.env").read_bytes() == padrao_de_hoje, (
        "o default.env sai byte a byte o de hoje")


def test_a_env_do_freestyle_fica_no_edge(lancamento: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(le, "_o_dono_esconde", lambda daemon: True)
    monkeypatch.setattr(le, "_o_freestyle_que_manda", lambda leitor: _perfil(0))
    le.materialize_launch_env(_daemon_uhid())

    assert le.roupa_gravada(_COM_PERFIL, lancamento) == ROUPA_PADRAO
    assert not (lancamento / f"steam_app_{_SEM_PERFIL}.env").exists()


# ---------------------------------------------------------------------------
# O arme e a soltura


class _DaemonDoArme:
    def __init__(self, roupa: int = ROUPA_PADRAO) -> None:
        self.aplicados: list[Any] = []
        self.config = SimpleNamespace(gamepad_emulation_enabled=True, gamepad_flavor="dualsense")
        self._gamepad_device = SimpleNamespace(backend="uhid")
        self._coop_manager = None
        self.controller = SimpleNamespace()
        self.roupa_do_pad = roupa
        self.vestidas: list[tuple[int, Any, int]] = []

    def is_native_mode(self) -> bool:
        return False

    def apply_profile_mode(self, mode: Any, *, profile: Any = None, origin: str = "") -> str:
        self.aplicados.append(mode)
        return "aplicado"

    def apply_profile_suppression(self, desired: bool, **_k: Any) -> str:
        return "aplicado"


@pytest.fixture
def arme(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(le, "_steam_profiles", lambda d: [])

    def vestir(daemon: Any, roupa: int) -> list[str]:
        daemon.vestidas.append(
            (roupa, daemon._pad_travado_pelo_lancamento, len(daemon.aplicados)))
        daemon.roupa_do_pad = roupa
        return ["p1"]

    monkeypatch.setattr(gp, "vestir_a_roupa", vestir)
    return tmp_path


def _lancar(pasta: Path, appid: int, *, roupa: int | None, gravada_em: float = 990.0) -> None:
    """O `last_run` do lançamento no epoch 1000, e a env que o wrapper leu, gravada antes."""
    import os

    (pasta / "last_run").write_text(f"appid={appid}\nepoch=1000\npid=1\n", encoding="utf-8")
    if roupa is not None:
        env = pasta / f"steam_app_{appid}.env"
        env.write_text(le._render({"X": "1"}, "teste", (roupa, "a fonte")), encoding="utf-8")
        os.utime(env, (gravada_em, gravada_em))


def test_o_arme_veste_e_o_fim_devolve(arme: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _lancar(arme, _SEM_PERFIL, roupa=ROUPA_COMUM)
    daemon = _DaemonDoArme()
    resultado = le.arm_launch_profile(daemon, base_dir=arme, now=1001.0)
    assert resultado is not None and resultado["motivo"] == "sem_perfil"
    assert daemon.vestidas == [(ROUPA_COMUM, None, 0)], (
        "o jogo sem perfil veste o 0ce6 ANTES da trava (o MMJ anda sem perfil)")
    assert daemon._pad_travado_pelo_lancamento == (_SEM_PERFIL, 1000)

    monkeypatch.setattr(lc, "vestir_a_roupa", lambda d, r: d.vestidas.append((r, None, -1)))
    lc._soltar_o_pad_do_lancamento(daemon, lc.MOTIVO_DA_AUTORIDADE)
    assert daemon.vestidas[-1] == (ROUPA_PADRAO, None, -1), "o fim do jogo devolve o Edge"


def test_o_arme_com_perfil_veste_antes_do_modo(arme: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(le, "_steam_profiles", lambda d: [(_COM_PERFIL, _perfil(_COM_PERFIL))])
    monkeypatch.setattr(le, "materialize_launch_env", lambda d: None)
    _lancar(arme, _COM_PERFIL, roupa=ROUPA_COMUM)
    daemon = _DaemonDoArme()

    resultado = le.arm_launch_profile(daemon, base_dir=arme, now=1001.0)

    assert resultado is not None and resultado["armado"] is True
    assert daemon.vestidas == [(ROUPA_COMUM, None, 0)], "veste antes do modo e da trava"
    assert daemon._pad_travado_pelo_lancamento == (_COM_PERFIL, 1000)


@pytest.mark.parametrize("caso", ["freestyle", "steam-input", "sem-env", "regravada-depois"])
def test_o_arme_que_fica_no_edge(arme: Path, monkeypatch: pytest.MonkeyPatch, caso: str) -> None:
    """`regravada-depois`: a env do `0ce6` nasceu (ou mudou) depois do `last_run`, e o
    jogo leu a de antes, com o `0x054C/0x0CE6` nas listas: o pad `0ce6` sumiria dele."""
    from hefesto_dualsense4unix.profiles import manager

    _lancar(arme, _SEM_PERFIL, roupa=None if caso == "sem-env" else ROUPA_COMUM,
            gravada_em=1001.5 if caso == "regravada-depois" else 990.0)
    if caso == "freestyle":
        monkeypatch.setattr(manager, "o_freestyle_manda", lambda store: True)
    if caso == "steam-input":
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {_SEM_PERFIL})
    daemon = _DaemonDoArme(roupa=ROUPA_COMUM)

    le.arm_launch_profile(daemon, base_dir=arme, now=1001.0)

    assert [r for r, _t, _a in daemon.vestidas] == [ROUPA_PADRAO], caso


def test_a_soltura_sem_roupa_nao_mexe(monkeypatch: pytest.MonkeyPatch) -> None:
    chamadas: list[int] = []
    monkeypatch.setattr(lc, "vestir_a_roupa", lambda d, r: chamadas.append(r))
    daemon = SimpleNamespace(_pad_travado_pelo_lancamento=(1, 1.0), roupa_do_pad=ROUPA_PADRAO)

    lc._soltar_o_pad_do_lancamento(daemon, lc.MOTIVO_DO_LANCAMENTO_QUE_CAIU)

    assert chamadas == [] and daemon._pad_travado_pelo_lancamento is None
