"""PS-L3-MASCARA-01 — o jogo abre pronto para trocar de modo e de máscara dentro dele.

O que se mediu na máquina dela em 14/09/2026, com a matriz de modo e máscara no
daemon vivo e a libSDL2 do sistema: os seis pares dão o aparelho certo em 1,5 s,
e em todos o DualSense de PLÁSTICO (054c:0ce6) continua na lista do SDL como
PS5. Quem o esconde do jogo é a env do lançamento, lida UMA vez no `exec` — e
ela seguia o modo e a máscara do INSTANTE em que o jogo abriu:

* o PS + R3 parou na Navegação, gravou `kind=desktop` no perfil do Future
  Knight, e o `steam_app_4235410.env` ficou sem IGNORE e sem DISABLE. Ao subir
  para um modo de jogo dentro da partida, o jogo segue com o físico (que o
  Hefesto graba) e o vpad chega como segundo controle;
* o caminho Xbox com o cartão DualSense (o vpad Edge 0df2 em uinput) saía sem
  IGNORE, pela regra de quando o uinput DualSense era 0ce6;
* a env e o alarme de divergência liam a máscara da SESSÃO (`xbox`) com o vpad
  vestindo a do cartão (`dualsense`).

MORDE (medido em 14/09, uma cura de cada vez): devolver o `and all(b == "uhid" …)`
ao `compose_env`; devolver `backends=()` ao ramo desktop do `_modo_antecipado`;
devolver a leitura de `config.gamepad_flavor` ao `_snapshot`; o prognóstico
ignorar o cartão; o `env_do_modo` ignorar a troca; tirar o ramo do caminho Xbox.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le

_IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES"
_DISABLE = "PROTON_DISABLE_HIDRAW"
_HIDAPI = "SDL_JOYSTICK_HIDAPI"
P1 = "aabbcc000001"
APPID = 4235410


def _env(path: Path) -> dict[str, str]:
    return dict(
        linha.split("=", 1)
        for linha in path.read_text(encoding="utf-8").splitlines()
        if linha and not linha.startswith("#") and "=" in linha
    )


def _estado(path: Path) -> str:
    return next(ln for ln in path.read_text(encoding="utf-8").splitlines()
                if ln.startswith("# estado:"))


def _perfil(mode: Any, controllers: dict[str, Any] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        name="Future Knight",
        mode=mode,
        controllers=controllers,
        match=SimpleNamespace(
            window_class=[f"steam_app_{APPID}"], window_title_regex=None, process_name=[]
        ),
    )


def _daemon(*, sessao: str, vpad: Any = None, ligado: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        is_native_mode=lambda: False,
        config=SimpleNamespace(gamepad_emulation_enabled=ligado, gamepad_flavor=sessao),
        _gamepad_device=vpad,
        _coop_manager=None,
        controller=SimpleNamespace(primary_uniq=P1),
        store=SimpleNamespace(window_detect_current_class=None),
    )


@pytest.fixture
def pasta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    monkeypatch.setattr(le, "_permite_uhid", lambda daemon: True)
    monkeypatch.setattr(le, "_load_profiles", lambda daemon: [])
    return tmp_path


def test_o_dualsense_no_canal_comum_esconde_o_fisico() -> None:
    env = le.compose_env(
        native_mode=False, emulation_enabled=True, flavor="dualsense", backends=["uinput"]
    )
    assert _IGNORE in env and _DISABLE in env
    assert _HIDAPI not in env


def test_o_jogo_que_abre_na_navegacao_ja_esconde_o_fisico(
    pasta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    perfil = _perfil(SimpleNamespace(kind="desktop", gamepad_flavor="xbox", caminho=None),
                     {P1: SimpleNamespace(mascara="dualsense")})
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(APPID, perfil)])

    le.materialize_launch_env(_daemon(sessao="xbox", ligado=False))

    env = _env(pasta / f"steam_app_{APPID}.env")
    assert _IGNORE in env, "na Navegação o jogo abria vendo o DualSense de plástico"
    assert _DISABLE in env
    assert _HIDAPI not in env, "a env é a da máscara do cartão (DualSense), não a padrão"
    assert "divergente=" not in _estado(pasta / f"steam_app_{APPID}.env")
    # O `default.env` é do estado VIVO, e sem vpad ele continua sem IGNORE.
    assert _IGNORE not in _env(pasta / "default.env")


def test_o_perfil_do_caminho_xbox_com_cartao_dualsense(
    pasta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    perfil = _perfil(SimpleNamespace(kind="gamepad", gamepad_flavor="xbox", caminho="xbox"),
                     {P1: SimpleNamespace(mascara="dualsense")})
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(APPID, perfil)])
    vpad = SimpleNamespace(backend="uinput", flavor="dualsense")

    le.materialize_launch_env(_daemon(sessao="xbox", vpad=vpad))

    arquivo = pasta / f"steam_app_{APPID}.env"
    env = _env(arquivo)
    assert _IGNORE in env and _DISABLE in env
    assert _HIDAPI not in env
    assert "mascara=dualsense" in _estado(arquivo)
    assert "divergente=" not in _estado(arquivo), (
        "o alarme comparava a máscara padrão do perfil com a da sessão"
    )


def test_o_caminho_xbox_nao_promete_o_canal_proprio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com a sessão em outra máscara, o prognóstico R-05 prometia o uhid.

    O caminho Xbox é o canal comum POR ESCOLHA dela: o vpad nasce em uinput mesmo
    com o uhid disponível, e o arquivo tem de dizer o canal que vai existir.
    """
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.uhid_gamepad.uhid_available", lambda: True
    )
    perfil = _perfil(SimpleNamespace(kind="gamepad", gamepad_flavor="xbox", caminho="xbox"),
                     {P1: SimpleNamespace(mascara="dualsense")})

    modo = le._modo_antecipado(
        perfil, flavor_atual="xbox", backends=["uinput"], permite_uhid=True, identidade=P1
    )

    assert modo is not None
    assert (modo.mascara, modo.backends) == ("dualsense", ("uinput",))


def test_a_env_viva_segue_a_mascara_que_o_vpad_veste(pasta: Path) -> None:
    vpad = SimpleNamespace(backend="uhid", flavor="dualsense")

    le.materialize_launch_env(_daemon(sessao="xbox", vpad=vpad))

    env = _env(pasta / "default.env")
    assert _HIDAPI not in env, "o Sony DualSense saía com a dica do Xbox"
    assert _IGNORE in env and _DISABLE in env
    assert "mascara=dualsense" in _estado(pasta / "default.env")


def test_o_modo_nativo_continua_entregando_o_fisico(
    pasta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    perfil = _perfil(SimpleNamespace(kind="native", gamepad_flavor=None, caminho=None))
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(APPID, perfil)])

    le.materialize_launch_env(_daemon(sessao="dualsense", ligado=False))

    env = _env(pasta / f"steam_app_{APPID}.env")
    assert _IGNORE not in env and _DISABLE not in env
