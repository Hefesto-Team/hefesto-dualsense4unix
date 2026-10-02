"""Diálogo do wrapper "1x por jogo" (DEDUP-05, item 4 — aprovado 2026-07-16).

Cobre as quatro frentes pedidas pelo sprint:

1. Decisão PURA do gatilho (`wrapper_dialog_decision`) — todas as condições
   a-e, em todas as combinações relevantes;
2. Persistência/carga das dispensas (JSON atômico em tmp, padrão
   `utils/session.py`);
3. Cache do vdf por appid (contador de leituras: appid repetido NÃO relê) e
   anti-spam de sessão (1 exibição por appid mesmo sem dispensa);
4. Handler de resposta do diálogo (copiar não fecha; dispensa persiste SÓ
   pelo botão explícito) + construção GTK real do MessageDialog.

Harness no padrão dos testes de actions (`test_home_actions_handlers._HomeStub`):
instância mínima do mixin com toasts/shows gravados, IPC/worker monkeypatchados.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("launch wrapper dialog")

import contextlib
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd
from hefesto_dualsense4unix.app.actions.launch_wrapper_dialog import (
    DECISION_PROMPT,
    DECISION_READ_VDF,
    DECISION_SKIP,
    extract_steam_appid,
    wrapper_dialog_decision,
)
from hefesto_dualsense4unix.integrations import steam_launch_options as slo


APPID = "1599660"
WM_JOGO = f"steam_app_{APPID}"


def _state(
    wm_class: str | None = WM_JOGO,
    *,
    gamepad_on: bool = True,
    native: bool = False,
) -> dict[str, Any]:
    """state_full mínimo para o gatilho (mesma forma do daemon.state_full)."""
    return {
        "connected": True,
        "native_mode": native,
        "gamepad_emulation": {
            "enabled": gamepad_on,
            "flavor": "dualsense",
            "backend": "uhid",
        },
        "window_detect_last_class": wm_class,
    }


def _decide(state: dict[str, Any] | None, **overrides: Any) -> tuple[str, str | None]:
    """`wrapper_dialog_decision` com defaults "tudo liberado" (só o vdf falta)."""
    kwargs: dict[str, Any] = {
        "vdf_cache": {},
        "dismissed": set(),
        "shown_this_session": set(),
        "popup_open": False,
        "dialog_open": False,
    }
    kwargs.update(overrides)
    return wrapper_dialog_decision(state, **kwargs)


class TestExtractSteamAppid:
    @pytest.mark.parametrize(
        ("wm_class", "esperado"),
        [
            ("steam_app_1599660", "1599660"),
            ("STEAM_APP_42", "42"),
            ("  steam_app_7  ", "7"),
            ("steam_app_", None),
            ("steam_app_abc", None),
            ("steam_app_12x", None),
            ("firefox", None),
            ("unknown", None),
            ("", None),
            (None, None),
            (123, None),
        ],
    )
    def test_extracao(self, wm_class: object, esperado: str | None) -> None:
        assert extract_steam_appid(wm_class) == esperado

    def test_devolve_str_e_nao_int(self) -> None:
        """UNIFICA-PREDICADO-01: a fronteira de TIPO fica neste callsite."""
        appid = extract_steam_appid(WM_JOGO)
        assert isinstance(appid, str)
        assert _decide(_state(), dismissed={APPID}) == (DECISION_SKIP, None)
        assert _decide(_state(), shown_this_session={APPID}) == (DECISION_SKIP, None)
        assert _decide(_state(), vdf_cache={APPID: True}) == (DECISION_PROMPT, APPID)


class TestDecisaoPura:
    def test_gatilho_completo_com_cache_quente_mostra(self) -> None:
        assert _decide(_state(), vdf_cache={APPID: True}) == (
            DECISION_PROMPT,
            APPID,
        )

    def test_cache_frio_pede_leitura_do_vdf(self) -> None:
        assert _decide(_state()) == (DECISION_READ_VDF, APPID)

    def test_jogo_que_ja_usa_o_wrapper_nao_incomoda(self) -> None:
        """(c) cache False = LaunchOptions já chama o wrapper (ou sem Steam"""
        assert _decide(_state(), vdf_cache={APPID: False}) == (
            DECISION_SKIP,
            None,
        )


    def test_gamepad_desligado_nao_mostra(self) -> None:
        assert _decide(
            _state(gamepad_on=False), vdf_cache={APPID: True}
        ) == (DECISION_SKIP, None)

    def test_modo_nativo_vence_o_gamepad_e_nao_mostra(self) -> None:
        """Nativo ligado = sem vpad (o físico é que joga) — o lembrete da"""
        assert _decide(
            _state(gamepad_on=True, native=True), vdf_cache={APPID: True}
        ) == (DECISION_SKIP, None)


    @pytest.mark.parametrize("wm_class", [None, "unknown", "firefox", "cosmic-term"])
    def test_janela_que_nao_e_jogo_steam_nao_mostra(
        self, wm_class: str | None
    ) -> None:
        assert _decide(_state(wm_class), vdf_cache={APPID: True}) == (
            DECISION_SKIP,
            None,
        )

    def test_estado_offline_nao_mostra(self) -> None:
        assert _decide(None, vdf_cache={APPID: True}) == (DECISION_SKIP, None)


    def test_appid_dispensado_nao_mostra(self) -> None:
        assert _decide(
            _state(), vdf_cache={APPID: True}, dismissed={APPID}
        ) == (DECISION_SKIP, None)

    def test_dispensa_vence_ate_a_leitura_do_vdf(self) -> None:
        """Appid dispensado nem dispara a leitura — o gate (d) vem antes do"""
        assert _decide(_state(), dismissed={APPID}) == (DECISION_SKIP, None)

    def test_dispensa_de_outro_appid_nao_bloqueia(self) -> None:
        assert _decide(
            _state(), vdf_cache={APPID: True}, dismissed={"42"}
        ) == (DECISION_PROMPT, APPID)


    def test_appid_ja_exibido_na_sessao_nao_repete(self) -> None:
        assert _decide(
            _state(), vdf_cache={APPID: True}, shown_this_session={APPID}
        ) == (DECISION_SKIP, None)


    def test_popup_aberto_segura_o_dialogo(self) -> None:
        assert _decide(
            _state(), vdf_cache={APPID: True}, popup_open=True
        ) == (DECISION_SKIP, None)

    def test_popup_aberto_segura_ate_a_leitura(self) -> None:
        assert _decide(_state(), popup_open=True) == (DECISION_SKIP, None)

    def test_nosso_dialogo_aberto_nao_empilha_outro(self) -> None:
        assert _decide(
            _state(), vdf_cache={APPID: True}, dialog_open=True
        ) == (DECISION_SKIP, None)


@pytest.fixture()
def config_dir_isolado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    """Redireciona `xdg_paths.config_dir` para tmp (padrão test_session_persist)."""
    destino = tmp_path / "config"
    destino.mkdir()

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            destino.mkdir(parents=True, exist_ok=True)
        return destino

    from hefesto_dualsense4unix.utils import xdg_paths

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    return destino


class TestPersistenciaDasDispensas:
    def test_sem_arquivo_devolve_conjunto_vazio(
        self, config_dir_isolado: Path
    ) -> None:
        assert lwd.load_dismissed_appids() == set()


    def test_formato_inesperado_e_tolerado(
        self, config_dir_isolado: Path
    ) -> None:
        arquivo = config_dir_isolado / "launch_dialog_dismissed.json"
        arquivo.write_text('["lista", "no", "topo"]', encoding="utf-8")
        assert lwd.load_dismissed_appids() == set()
        arquivo.write_text(
            '{"dismissed_appids": [42, "77", "", null]}', encoding="utf-8"
        )
        assert lwd.load_dismissed_appids() == {"42", "77"}


_TAB = "\t"


def _vdf(launch_options: dict[str, str]) -> str:
    """localconfig.vdf mínimo (mesmo builder do test_steam_launch_options_vdf,"""
    blocos = []
    for appid, valor in launch_options.items():
        blocos.append(
            f'{_TAB * 5}"{appid}"\n{_TAB * 5}{{\n'
            f'{_TAB * 6}"LaunchOptions"{_TAB * 2}"{slo._vdf_escape(valor)}"\n'
            f'{_TAB * 6}"playtime"{_TAB * 2}"42"\n'
            f"{_TAB * 5}}}\n"
        )
    apps = "".join(blocos)
    return (
        '"UserLocalConfigStore"\n{\n'
        f'{_TAB}"Software"\n{_TAB}{{\n'
        f'{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
        f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n'
        f'{_TAB * 4}"apps"\n{_TAB * 4}{{\n'
        f"{apps}"
        f"{_TAB * 4}}}\n{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n}}\n"
    )


def _home_com_vdf(base: Path, text: str, *, sandbox: bool = False) -> Path:
    """$HOME falso com um localconfig.vdf num layout que o discover conhece."""
    home = base / "home"
    rel = (
        ".var/app/com.valvesoftware.Steam/.steam/steam/userdata/1/config"
        if sandbox
        else ".steam/steam/userdata/111/config"
    )
    cfg = home / rel
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "localconfig.vdf").write_text(text, encoding="utf-8")
    return home


class TestLeituraDoVdfPorAppid:
    def test_mapeia_appid_para_launch_options(self) -> None:
        texto = _vdf({APPID: "MANGOHUD=1 %command%", "42": "-fullscreen"})
        mapa = slo.read_launch_options_by_appid(texto)
        assert mapa == {
            APPID: "MANGOHUD=1 %command%",
            "42": "-fullscreen",
        }

    def test_desfaz_o_escaping_da_string_do_wrapper(self) -> None:
        """A string do wrapper tem aspas duplas — no vdf ela vive escapada e a"""
        texto = _vdf({APPID: slo.WRAPPER_LAUNCH})
        mapa = slo.read_launch_options_by_appid(texto)
        assert mapa[APPID] == slo.WRAPPER_LAUNCH
        assert slo.WRAPPER_PREFIX in mapa[APPID]

    def test_roundtrip_com_a_migracao_real(self) -> None:
        """Arquivo envenenado migrado pelo `transform_vdf_text` REAL → a"""
        veneno = (
            "SDL_JOYSTICK_HIDAPI=0 "
            f"{slo.IGNORE_SIGNATURE} %command%"
        )
        migrado, mudadas = slo.transform_vdf_text(_vdf({APPID: veneno}), "migrate")
        assert mudadas == 1
        mapa = slo.read_launch_options_by_appid(migrado)
        assert slo.WRAPPER_PREFIX in mapa[APPID]

    def test_launch_options_fora_do_bloco_apps_e_ignorado(self) -> None:
        texto = (
            '"UserLocalConfigStore"\n{\n'
            '\t"Broadcast"\n\t{\n'
            '\t\t"LaunchOptions"\t\t"nada"\n'
            "\t}\n"
            "}\n"
        )
        assert slo.read_launch_options_by_appid(texto) == {}

    def test_chave_nao_numerica_sob_apps_e_ignorada(self) -> None:
        texto = (
            '"UserLocalConfigStore"\n{\n'
            '\t"apps"\n\t{\n'
            '\t\t"config"\n\t\t{\n'
            '\t\t\t"LaunchOptions"\t\t"nada"\n'
            "\t\t}\n"
            "\t}\n"
            "}\n"
        )
        assert slo.read_launch_options_by_appid(texto) == {}


class TestAppidNeedsWrapper:
    def test_sem_nenhum_vdf_nao_ha_o_que_lembrar(self, tmp_path: Path) -> None:
        home = tmp_path / "home"
        home.mkdir()
        assert slo.appid_needs_wrapper(APPID, home=home) is False

    def test_jogo_sem_wrapper_precisa(self, tmp_path: Path) -> None:
        home = _home_com_vdf(tmp_path, _vdf({APPID: "MANGOHUD=1 %command%"}))
        assert slo.appid_needs_wrapper(APPID, home=home) is True

    def test_jogo_sem_entrada_no_vdf_tambem_precisa(self, tmp_path: Path) -> None:
        home = _home_com_vdf(tmp_path, _vdf({"42": "-fullscreen"}))
        assert slo.appid_needs_wrapper(APPID, home=home) is True

    def test_jogo_com_wrapper_nao_precisa(self, tmp_path: Path) -> None:
        home = _home_com_vdf(tmp_path, _vdf({APPID: slo.WRAPPER_LAUNCH}))
        assert slo.appid_needs_wrapper(APPID, home=home) is False

    def test_wrapper_em_outro_jogo_nao_conta(self, tmp_path: Path) -> None:
        home = _home_com_vdf(
            tmp_path,
            _vdf({"42": slo.WRAPPER_LAUNCH, APPID: "-fullscreen"}),
        )
        assert slo.appid_needs_wrapper(APPID, home=home) is True

    def test_steam_sandboxed_fica_de_fora(self, tmp_path: Path) -> None:
        """Só Flatpak/Snap no computador → o wrapper do host é invisível à"""
        home = _home_com_vdf(
            tmp_path, _vdf({APPID: "-fullscreen"}), sandbox=True
        )
        assert slo.appid_needs_wrapper(APPID, home=home) is False


@pytest.fixture()
def leitura_vdf(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, int]:
    """Worker síncrono + contador de leituras do vdf (sempre "precisa")."""
    contador = {"leituras": 0}

    def fake_needs(appid: str, home: Path | None = None) -> bool:
        contador["leituras"] += 1
        return True

    def sync_run_in_thread(
        fn: Any, on_success: Any, on_failure: Any = None
    ) -> None:
        try:
            result = fn()
        except Exception as exc:
            if on_failure is not None:
                on_failure(exc)
            return
        on_success(result)

    monkeypatch.setattr(lwd, "appid_needs_wrapper", fake_needs)
    monkeypatch.setattr(lwd, "run_in_thread", sync_run_in_thread)
    return contador


class _FakeDialog:
    def __init__(self) -> None:
        self.destroyed = False

    def destroy(self) -> None:
        self.destroyed = True


_DISPLAY_OK = False
with contextlib.suppress(Exception):
    import gi as _gi

    _gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk as _Gdk

    _DISPLAY_OK = _Gdk.Display.get_default() is not None


def _gdkpixbuf_ok() -> bool:
    """GdkPixbuf disponível? A App real o importa (app.py); a CI headless de"""
    try:
        import gi

        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf  # noqa: F401

        return True
    except Exception:
        return False


