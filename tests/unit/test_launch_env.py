"""DEDUP-04: o compositor de envs do wrapper — todos os estados do daemon.

O wrapper `hefesto-launch` só EXPORTA; quem decide é o daemon, regravando os
arquivos de `launch_env/` com o backend REAL agregado POR JOGADOR. A regra de
ouro fail-safe: qualquer vpad degradado (uinput/0ce6) => SEM IGNORE — o pior
caso permitido é controle DUPLICADO, nunca zero controles.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from hefesto_dualsense4unix.daemon import launch_env
from hefesto_dualsense4unix.daemon.launch_env import (
    ENV_ALLOWLIST,
    compose_env,
    materialize_launch_env,
)

_IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES"


# --- compose_env (pura) — os estados do critério de aceite -------------------


def test_uhid_vivo_em_todos_os_vpads_desduplica_no_layout_ps():
    env = compose_env(
        native_mode=False, emulation_enabled=True,
        flavor="dualsense", backends=["uhid"],
    )
    assert env[_IGNORE] == "0x054c/0x0ce6"
    assert env["PROTON_ENABLE_HIDRAW"] == "1"
    assert "SDL_JOYSTICK_HIDAPI" not in env  # HIDAPI ligado (driver PS5 no vpad)
    assert env["__GL_SHADER_DISK_CACHE"] == "1"


def test_uinput_degradado_nunca_esconde_o_fisico():
    """Critério (c) — o caso que o desenho original não testava: daemon VIVO
    com vpad em uinput/0ce6 => SEM IGNORE (duplicado > zero controles)."""
    env = compose_env(
        native_mode=False, emulation_enabled=True,
        flavor="dualsense", backends=["uinput"],
    )
    assert _IGNORE not in env
    assert "PROTON_ENABLE_HIDRAW" not in env
    assert env["__GL_SHADER_DISK_CACHE"] == "1"  # só o preload inócuo


def test_coop_com_um_jogador_degradado_derruba_o_ignore():
    """dedup POR JOGADOR: P1 uhid + P2 uinput => o IGNORE congelado deixaria
    AQUELE jogador com zero controle — então não sai IGNORE nenhum."""
    env = compose_env(
        native_mode=False, emulation_enabled=True,
        flavor="dualsense", backends=["uhid", "uinput"],
    )
    assert _IGNORE not in env


def test_xbox_forca_evdev_e_esconde_o_fisico():
    env = compose_env(
        native_mode=False, emulation_enabled=True,
        flavor="xbox", backends=["uinput"],
    )
    assert env["SDL_JOYSTICK_HIDAPI"] == "0"
    assert env[_IGNORE] == "0x054c/0x0ce6"
    assert "PROTON_ENABLE_HIDRAW" not in env  # rumble volta pelo FF do vpad


def test_modo_nativo_entrega_o_hidraw_sem_esconder_nada():
    env = compose_env(
        native_mode=True, emulation_enabled=False,
        flavor="dualsense", backends=[],
    )
    assert env["PROTON_ENABLE_HIDRAW"] == "1"
    assert _IGNORE not in env


def test_emulacao_desligada_ou_sem_vpad_vivo_nao_esconde():
    for enabled, backends in ((False, []), (True, []), (False, ["uhid"])):
        env = compose_env(
            native_mode=False, emulation_enabled=enabled,
            flavor="dualsense", backends=backends,
        )
        assert _IGNORE not in env, (enabled, backends)


def test_compose_env_so_emite_vars_da_allowlist():
    """O wrapper filtra por allowlist — emitir var fora dela = env que nunca
    chega ao jogo (drift silencioso)."""
    estados = [
        dict(native_mode=True, emulation_enabled=False, flavor="dualsense", backends=[]),
        dict(native_mode=False, emulation_enabled=True, flavor="xbox", backends=["uinput"]),
        dict(native_mode=False, emulation_enabled=True, flavor="dualsense", backends=["uhid"]),
        dict(native_mode=False, emulation_enabled=False, flavor="dualsense", backends=[]),
    ]
    for estado in estados:
        for var in compose_env(**estado):
            assert var in ENV_ALLOWLIST, var


def test_allowlist_espelhada_no_wrapper_sh():
    """Contrato allowlist Python <-> wrapper POSIX-sh: cada var precisa ter o
    seu `case` no assets/hefesto-launch.sh, senão o daemon a materializa e o
    wrapper a descarta calado."""
    root = Path(__file__).resolve().parents[2]
    wrapper = (root / "assets/hefesto-launch.sh").read_text(encoding="utf-8")
    for var in ENV_ALLOWLIST:
        assert f"{var}=*)" in wrapper, var


# --- materialize_launch_env (arquivos) ---------------------------------------


def _fake_daemon(
    *,
    native: bool = False,
    enabled: bool = True,
    flavor: str = "dualsense",
    backend: str | None = "uhid",
    coop_backends: tuple[str, ...] = (),
) -> SimpleNamespace:
    players = {
        f"p{i}": SimpleNamespace(vpad=SimpleNamespace(backend=b))
        for i, b in enumerate(coop_backends, start=2)
    }
    return SimpleNamespace(
        is_native_mode=lambda: native,
        config=SimpleNamespace(
            gamepad_emulation_enabled=enabled, gamepad_flavor=flavor
        ),
        _gamepad_device=(
            SimpleNamespace(backend=backend) if backend is not None else None
        ),
        _coop_manager=SimpleNamespace(_players=players) if players else None,
        controller=SimpleNamespace(),
    )


def _env_do_arquivo(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for linha in path.read_text(encoding="utf-8").splitlines():
        if linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        out[chave] = valor
    return out


def test_materialize_grava_default_env_com_o_estado_real(tmp_path, monkeypatch):
    monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: tmp_path)
    materialize_launch_env(_fake_daemon(backend="uhid"))
    env = _env_do_arquivo(tmp_path / "default.env")
    assert env[_IGNORE] == "0x054c/0x0ce6"
    assert env["PROTON_ENABLE_HIDRAW"] == "1"


def test_materialize_reflete_degradacao_por_jogador(tmp_path, monkeypatch):
    monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: tmp_path)
    materialize_launch_env(
        _fake_daemon(backend="uhid", coop_backends=("uhid", "uinput"))
    )
    env = _env_do_arquivo(tmp_path / "default.env")
    assert _IGNORE not in env


def test_materialize_por_appid_e_limpeza_de_rancosos(tmp_path, monkeypatch):
    """Perfil com `steam_app_<appid>` no match ganha arquivo próprio com a
    opinião DELE (modo nativo antecipado); arquivos de perfis apagados somem."""
    monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: tmp_path)
    perfil_nativo = SimpleNamespace(mode=SimpleNamespace(kind="native"))
    monkeypatch.setattr(
        launch_env, "_steam_profiles", lambda daemon: [(1599660, perfil_nativo)]
    )
    rancoso = tmp_path / "steam_app_999.env"
    rancoso.write_text("PROTON_ENABLE_HIDRAW=1\n", encoding="utf-8")

    materialize_launch_env(_fake_daemon(backend="uhid"))

    env_jogo = _env_do_arquivo(tmp_path / "steam_app_1599660.env")
    assert env_jogo["PROTON_ENABLE_HIDRAW"] == "1"
    assert _IGNORE not in env_jogo  # nativo: esconder o físico = zero controles
    assert not rancoso.exists()


def test_materialize_por_appid_perfil_sem_opiniao_cai_no_default(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: tmp_path)
    sem_opiniao = SimpleNamespace(mode=None)
    monkeypatch.setattr(
        launch_env, "_steam_profiles", lambda daemon: [(620, sem_opiniao)]
    )
    materialize_launch_env(_fake_daemon())
    assert not (tmp_path / "steam_app_620.env").exists()
    assert (tmp_path / "default.env").exists()


def test_materialize_nunca_propaga_excecao(monkeypatch):
    """A materialização quebrada não pode derrubar o start da emulação."""
    def _explode(ensure: bool = False) -> Path:
        raise OSError("disco cheio")

    monkeypatch.setattr(launch_env, "launch_env_dir", _explode)
    materialize_launch_env(_fake_daemon())  # não levanta


# --- perfil nativo fora da antecipação por appid (achado MED da revisão) -----


def _perfil(
    *,
    kind: str | None,
    window_class: tuple[str, ...] = (),
    title: str | None = None,
    process: tuple[str, ...] = (),
    name: str = "perfil",
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        mode=SimpleNamespace(kind=kind) if kind is not None else None,
        match=SimpleNamespace(
            window_class=list(window_class),
            window_title_regex=title,
            process_name=list(process),
        ),
    )


def test_nativo_por_titulo_e_arriscado_e_por_appid_nao():
    """Perfil nativo casado por título/processo escapa do steam_app_<id>.env;
    o casado SÓ por steam_app_* está coberto pela antecipação."""
    arriscado = _perfil(kind="native", title="Rockstar Games Launcher", name="rdr2")
    coberto = _perfil(
        kind="native", window_class=("steam_app_1599660",), name="sackboy_nativo"
    )
    gamepad = _perfil(kind="gamepad", title="qualquer", name="jogo")
    sem_modo = _perfil(kind=None, name="vitoria")

    nomes = launch_env._nativos_fora_da_antecipacao(
        [arriscado, coberto, gamepad, sem_modo]
    )
    assert nomes == ["rdr2"]


def test_nativo_matchany_e_desktop_por_processo_tambem_sao_arriscados():
    matchany_nativo = SimpleNamespace(
        name="tudo_nativo", mode=SimpleNamespace(kind="native"), match=SimpleNamespace()
    )
    desktop_por_processo = _perfil(
        kind="desktop", process=("firefox",), name="navegacao"
    )
    nomes = launch_env._nativos_fora_da_antecipacao(
        [matchany_nativo, desktop_por_processo]
    )
    assert nomes == ["tudo_nativo", "navegacao"]


def test_nativo_com_appid_mais_titulo_continua_arriscado():
    """O título pode casar OUTRA janela além do appid antecipado — conservador."""
    perfil = _perfil(
        kind="native",
        window_class=("steam_app_620",),
        title="Launcher",
        name="misto",
    )
    assert launch_env._nativos_fora_da_antecipacao([perfil]) == ["misto"]


def test_default_env_omite_ignore_quando_ha_nativo_fora_da_antecipacao(
    tmp_path, monkeypatch
):
    """Estado uhid saudável (IGNORE sairia) + perfil nativo por título → o
    default.env OMITE o IGNORE: se o autoswitch ativar esse perfil depois do
    launch, a emulação cai e o IGNORE congelado deixaria zero controles.
    Duplicado > zero."""
    monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(
        launch_env,
        "_load_profiles",
        lambda daemon: [_perfil(kind="native", title="Launcher", name="rdr2")],
    )
    materialize_launch_env(_fake_daemon(backend="uhid"))
    env = _env_do_arquivo(tmp_path / "default.env")
    assert _IGNORE not in env
    assert env["__GL_SHADER_DISK_CACHE"] == "1"


def test_default_env_mantem_ignore_quando_todos_os_nativos_tem_appid(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(launch_env, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(
        launch_env,
        "_load_profiles",
        lambda daemon: [
            _perfil(
                kind="native",
                window_class=("steam_app_1599660",),
                name="sackboy_nativo",
            )
        ],
    )
    materialize_launch_env(_fake_daemon(backend="uhid"))
    env = _env_do_arquivo(tmp_path / "default.env")
    assert env[_IGNORE] == "0x054c/0x0ce6"
    # E o arquivo por-appid antecipa o modo nativo DAQUELE jogo (sem IGNORE).
    env_jogo = _env_do_arquivo(tmp_path / "steam_app_1599660.env")
    assert _IGNORE not in env_jogo
    assert env_jogo["PROTON_ENABLE_HIDRAW"] == "1"
