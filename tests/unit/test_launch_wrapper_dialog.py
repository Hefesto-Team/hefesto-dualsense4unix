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

import contextlib
import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd
from hefesto_dualsense4unix.app.actions.launch_wrapper_dialog import (
    DECISION_PROMPT,
    DECISION_READ_VDF,
    DECISION_SKIP,
    RESPONSE_COPY,
    RESPONSE_DISMISS,
    LaunchWrapperDialogMixin,
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


# ---------------------------------------------------------------------------
# extract_steam_appid — condição (b)
# ---------------------------------------------------------------------------


class TestExtractSteamAppid:
    @pytest.mark.parametrize(
        ("wm_class", "esperado"),
        [
            ("steam_app_1599660", "1599660"),
            ("STEAM_APP_42", "42"),  # tolerante a caixa
            ("  steam_app_7  ", "7"),  # tolerante a espaço acidental
            ("steam_app_", None),
            ("steam_app_abc", None),
            ("steam_app_12x", None),
            ("firefox", None),
            ("unknown", None),
            ("", None),
            (None, None),
            (123, None),  # payload malformado não explode
        ],
    )
    def test_extracao(self, wm_class: object, esperado: str | None) -> None:
        assert extract_steam_appid(wm_class) == esperado


# ---------------------------------------------------------------------------
# Decisão pura — condições a-e
# ---------------------------------------------------------------------------


class TestDecisaoPura:
    def test_gatilho_completo_com_cache_quente_mostra(self) -> None:
        assert _decide(_state(), vdf_cache={APPID: True}) == (
            DECISION_PROMPT,
            APPID,
        )

    def test_cache_frio_pede_leitura_do_vdf(self) -> None:
        assert _decide(_state()) == (DECISION_READ_VDF, APPID)

    def test_jogo_que_ja_usa_o_wrapper_nao_incomoda(self) -> None:
        """(c) cache False = LaunchOptions já chama o wrapper (ou sem Steam
        elegível) — nunca mostra."""
        assert _decide(_state(), vdf_cache={APPID: False}) == (
            DECISION_SKIP,
            None,
        )

    # --- (a) emulação de gamepad ativa ---------------------------------

    def test_gamepad_desligado_nao_mostra(self) -> None:
        assert _decide(
            _state(gamepad_on=False), vdf_cache={APPID: True}
        ) == (DECISION_SKIP, None)

    def test_modo_nativo_vence_o_gamepad_e_nao_mostra(self) -> None:
        """Nativo ligado = sem vpad (o físico é que joga) — o lembrete da
        dedup do vpad não se aplica, mesmo com gamepad_emulation.enabled."""
        assert _decide(
            _state(gamepad_on=True, native=True), vdf_cache={APPID: True}
        ) == (DECISION_SKIP, None)

    # --- (b) janela focada é jogo Steam ---------------------------------

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

    # --- (d) appid dispensado (persistido) ------------------------------

    def test_appid_dispensado_nao_mostra(self) -> None:
        assert _decide(
            _state(), vdf_cache={APPID: True}, dismissed={APPID}
        ) == (DECISION_SKIP, None)

    def test_dispensa_vence_ate_a_leitura_do_vdf(self) -> None:
        """Appid dispensado nem dispara a leitura — o gate (d) vem antes do
        (c) de propósito (não pagar I/O por um jogo que ela já recusou)."""
        assert _decide(_state(), dismissed={APPID}) == (DECISION_SKIP, None)

    def test_dispensa_de_outro_appid_nao_bloqueia(self) -> None:
        assert _decide(
            _state(), vdf_cache={APPID: True}, dismissed={"42"}
        ) == (DECISION_PROMPT, APPID)

    # --- anti-spam por sessão --------------------------------------------

    def test_appid_ja_exibido_na_sessao_nao_repete(self) -> None:
        assert _decide(
            _state(), vdf_cache={APPID: True}, shown_this_session={APPID}
        ) == (DECISION_SKIP, None)

    # --- (e) nenhum diálogo/popup nosso aberto ---------------------------

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


# ---------------------------------------------------------------------------
# Persistência das dispensas (JSON atômico em tmp)
# ---------------------------------------------------------------------------


@pytest.fixture()
def config_dir_isolado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Path:
    """Redireciona `xdg_paths.config_dir` para tmp (padrão test_session_persist).

    O `_dismissed_path` faz import LAZY de `config_dir`, então o monkeypatch
    no módulo `xdg_paths` é o ponto hermético certo.
    """
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

    def test_roundtrip_de_uma_dispensa(self, config_dir_isolado: Path) -> None:
        lwd.add_dismissed_appid(APPID)
        assert lwd.load_dismissed_appids() == {APPID}
        gravado = json.loads(
            (config_dir_isolado / "launch_dialog_dismissed.json").read_text(
                encoding="utf-8"
            )
        )
        assert gravado == {"dismissed_appids": [APPID]}

    def test_add_faz_merge_com_o_que_ja_existe(
        self, config_dir_isolado: Path
    ) -> None:
        lwd.add_dismissed_appid("42")
        lwd.add_dismissed_appid(APPID)
        assert lwd.load_dismissed_appids() == {"42", APPID}

    def test_add_e_idempotente(self, config_dir_isolado: Path) -> None:
        lwd.add_dismissed_appid(APPID)
        lwd.add_dismissed_appid(APPID)
        assert lwd.load_dismissed_appids() == {APPID}

    def test_arquivo_corrompido_vira_vazio_e_add_recupera(
        self, config_dir_isolado: Path
    ) -> None:
        arquivo = config_dir_isolado / "launch_dialog_dismissed.json"
        arquivo.write_text("{lixo sem json", encoding="utf-8")
        assert lwd.load_dismissed_appids() == set()
        lwd.add_dismissed_appid(APPID)
        assert lwd.load_dismissed_appids() == {APPID}

    def test_formato_inesperado_e_tolerado(
        self, config_dir_isolado: Path
    ) -> None:
        arquivo = config_dir_isolado / "launch_dialog_dismissed.json"
        arquivo.write_text('["lista", "no", "topo"]', encoding="utf-8")
        assert lwd.load_dismissed_appids() == set()
        arquivo.write_text(
            '{"dismissed_appids": [42, "77", "", null]}', encoding="utf-8"
        )
        # int vira string (edição manual tolerada); vazio/null caem fora.
        assert lwd.load_dismissed_appids() == {"42", "77"}

    def test_escrita_atomica_nao_deixa_temporario_para_tras(
        self, config_dir_isolado: Path
    ) -> None:
        lwd.add_dismissed_appid(APPID)
        sobras = list(config_dir_isolado.glob(".launch_dialog_*"))
        assert sobras == []


# ---------------------------------------------------------------------------
# Leitura do vdf por appid (integrations/steam_launch_options)
# ---------------------------------------------------------------------------

_TAB = "\t"


def _vdf(launch_options: dict[str, str]) -> str:
    """localconfig.vdf mínimo (mesmo builder do test_steam_launch_options_vdf,
    com o escaping de KeyValues aplicado — a string do wrapper tem aspas)."""
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
        """A string do wrapper tem aspas duplas — no vdf ela vive escapada e a
        leitura devolve a forma crua (comparável com WRAPPER_PREFIX)."""
        texto = _vdf({APPID: slo.WRAPPER_LAUNCH})
        mapa = slo.read_launch_options_by_appid(texto)
        assert mapa[APPID] == slo.WRAPPER_LAUNCH
        assert slo.WRAPPER_PREFIX in mapa[APPID]

    def test_roundtrip_com_a_migracao_real(self) -> None:
        """Arquivo envenenado migrado pelo `transform_vdf_text` REAL → a
        leitura por appid enxerga o wrapper naquele jogo."""
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
        """Só Flatpak/Snap no computador → o wrapper do host é invisível à
        sandbox (a migração é recusada lá) — não faz sentido lembrar."""
        home = _home_com_vdf(
            tmp_path, _vdf({APPID: "-fullscreen"}), sandbox=True
        )
        assert slo.appid_needs_wrapper(APPID, home=home) is False


# ---------------------------------------------------------------------------
# Mixin — cache por appid, anti-spam por sessão, gates ao vivo
# ---------------------------------------------------------------------------


class _AppStub(LaunchWrapperDialogMixin):
    """Instância mínima (padrão `_HomeStub`) — grava toasts e exibições."""

    def __init__(self) -> None:
        self.toasts: list[str] = []
        self.shows: list[str] = []

    def _status_toast(self, _ctx: str, msg: str) -> None:
        self.toasts.append(msg)

    def _show_wrapper_dialog(self, appid: str) -> None:
        self.shows.append(appid)

    @staticmethod
    def _popup_is_open() -> bool:
        return False


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


class TestMixinCacheEAntiSpam:
    def test_fluxo_completo_le_uma_vez_e_mostra_uma_vez(
        self, leitura_vdf: dict[str, int], config_dir_isolado: Path
    ) -> None:
        stub = _AppStub()
        estado = _state()

        stub._maybe_prompt_wrapper_dialog(estado)  # tick 1: só a leitura
        assert leitura_vdf["leituras"] == 1
        assert stub.shows == []

        stub._maybe_prompt_wrapper_dialog(estado)  # tick 2: cache quente
        assert stub.shows == [APPID]
        assert stub._wrapper_dialog_open is True

        # Diálogo fechado sem dispensa: anti-spam de SESSÃO segura o resto.
        stub._wrapper_dialog_open = False
        for _ in range(5):
            stub._maybe_prompt_wrapper_dialog(estado)
        assert stub.shows == [APPID]
        assert leitura_vdf["leituras"] == 1  # appid repetido NUNCA relê

    def test_appid_novo_le_de_novo_mas_o_antigo_nao(
        self, leitura_vdf: dict[str, int], config_dir_isolado: Path
    ) -> None:
        stub = _AppStub()
        estado_a = _state()
        estado_b = _state("steam_app_42")

        stub._maybe_prompt_wrapper_dialog(estado_a)
        stub._maybe_prompt_wrapper_dialog(estado_a)
        stub._wrapper_dialog_open = False
        assert leitura_vdf["leituras"] == 1

        stub._maybe_prompt_wrapper_dialog(estado_b)  # B em foco: nova leitura
        stub._maybe_prompt_wrapper_dialog(estado_b)
        stub._wrapper_dialog_open = False
        assert leitura_vdf["leituras"] == 2
        assert stub.shows == [APPID, "42"]

        # Voltar ao A: cache quente + anti-spam — nem leitura, nem exibição.
        stub._maybe_prompt_wrapper_dialog(estado_a)
        assert leitura_vdf["leituras"] == 2
        assert stub.shows == [APPID, "42"]

    def test_dispensa_persistida_nem_le_o_vdf(
        self, leitura_vdf: dict[str, int], config_dir_isolado: Path
    ) -> None:
        lwd.add_dismissed_appid(APPID)
        stub = _AppStub()

        for _ in range(3):
            stub._maybe_prompt_wrapper_dialog(_state())

        assert leitura_vdf["leituras"] == 0
        assert stub.shows == []

    def test_gamepad_desligado_nao_dispara_nada(
        self, leitura_vdf: dict[str, int], config_dir_isolado: Path
    ) -> None:
        stub = _AppStub()
        stub._maybe_prompt_wrapper_dialog(_state(gamepad_on=False))
        assert leitura_vdf["leituras"] == 0
        assert stub.shows == []

    def test_popup_aberto_segura_o_tick(
        self, leitura_vdf: dict[str, int], config_dir_isolado: Path
    ) -> None:
        stub = _AppStub()
        stub._popup_is_open = lambda: True  # type: ignore[method-assign]
        stub._wrapper_dialog_bootstrap()
        stub._wrapper_dialog_vdf_cache[APPID] = True

        stub._maybe_prompt_wrapper_dialog(_state())

        assert stub.shows == []

    def test_dialogo_ja_aberto_nao_empilha(
        self, leitura_vdf: dict[str, int], config_dir_isolado: Path
    ) -> None:
        stub = _AppStub()
        stub._wrapper_dialog_bootstrap()
        stub._wrapper_dialog_vdf_cache[APPID] = True
        stub._wrapper_dialog_open = True

        stub._maybe_prompt_wrapper_dialog(_state())

        assert stub.shows == []

    def test_leitura_pendente_nao_acumula_submissoes(
        self, monkeypatch: pytest.MonkeyPatch, config_dir_isolado: Path
    ) -> None:
        """Worker que nunca responde (IPC lento): o guard de inflight impede
        fila de leituras no executor de 1 worker."""
        submissoes: list[Any] = []
        monkeypatch.setattr(
            lwd,
            "run_in_thread",
            lambda fn, ok, fail=None: submissoes.append(fn),
        )
        stub = _AppStub()

        stub._maybe_prompt_wrapper_dialog(_state())
        stub._maybe_prompt_wrapper_dialog(_state())
        stub._maybe_prompt_wrapper_dialog(_state())

        assert len(submissoes) == 1

    def test_falha_na_leitura_e_silenciosa_e_nao_insiste(
        self, monkeypatch: pytest.MonkeyPatch, config_dir_isolado: Path
    ) -> None:
        """Erro no vdf memoiza False (fail-quiet): sem exceção no tick, sem
        releitura a 2 Hz e sem diálogo."""
        leituras = {"n": 0}

        def explode(appid: str, home: Path | None = None) -> bool:
            leituras["n"] += 1
            raise OSError("disco sumiu")

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

        monkeypatch.setattr(lwd, "appid_needs_wrapper", explode)
        monkeypatch.setattr(lwd, "run_in_thread", sync_run_in_thread)
        stub = _AppStub()

        stub._maybe_prompt_wrapper_dialog(_state())  # não propaga
        stub._maybe_prompt_wrapper_dialog(_state())
        stub._maybe_prompt_wrapper_dialog(_state())

        assert leituras["n"] == 1
        assert stub.shows == []

    def test_estado_offline_e_no_op(
        self, leitura_vdf: dict[str, int], config_dir_isolado: Path
    ) -> None:
        stub = _AppStub()
        stub._maybe_prompt_wrapper_dialog(None)
        assert leitura_vdf["leituras"] == 0
        assert stub.shows == []


# ---------------------------------------------------------------------------
# Handler de resposta do diálogo
# ---------------------------------------------------------------------------


class _FakeDialog:
    def __init__(self) -> None:
        self.destroyed = False

    def destroy(self) -> None:
        self.destroyed = True


class TestRespostaDoDialogo:
    def test_dispensa_persiste_fecha_e_libera_o_gate(
        self, config_dir_isolado: Path
    ) -> None:
        stub = _AppStub()
        stub._wrapper_dialog_open = True
        dlg = _FakeDialog()

        stub._on_wrapper_dialog_response(dlg, RESPONSE_DISMISS, "42")

        assert lwd.load_dismissed_appids() == {"42"}
        assert "42" in stub._wrapper_dialog_dismissed_set()
        assert dlg.destroyed is True
        assert stub._wrapper_dialog_open is False

    def test_copiar_nao_fecha_e_nao_persiste(
        self, config_dir_isolado: Path
    ) -> None:
        stub = _AppStub()
        stub._wrapper_dialog_open = True
        stub._copy_wrapper_launch_to_clipboard = lambda: True  # type: ignore[method-assign]
        dlg = _FakeDialog()

        stub._on_wrapper_dialog_response(dlg, RESPONSE_COPY, APPID)

        assert dlg.destroyed is False
        assert stub._wrapper_dialog_open is True
        assert lwd.load_dismissed_appids() == set()
        assert any("Copiado" in t for t in stub.toasts)

    def test_falha_do_clipboard_orienta_a_copia_manual(
        self, config_dir_isolado: Path
    ) -> None:
        stub = _AppStub()
        stub._wrapper_dialog_open = True
        stub._copy_wrapper_launch_to_clipboard = lambda: False  # type: ignore[method-assign]
        dlg = _FakeDialog()

        stub._on_wrapper_dialog_response(dlg, RESPONSE_COPY, APPID)

        assert dlg.destroyed is False
        assert any("selecione" in t.lower() for t in stub.toasts)

    def test_fechar_nao_persiste_nada(self, config_dir_isolado: Path) -> None:
        """Fechar/Esc/X (qualquer response que não seja copiar/dispensar)
        fecha SEM gravar — dispensa persistente só pelo botão explícito."""
        stub = _AppStub()
        stub._wrapper_dialog_open = True
        dlg = _FakeDialog()

        stub._on_wrapper_dialog_response(dlg, -4, APPID)  # DELETE_EVENT

        assert dlg.destroyed is True
        assert stub._wrapper_dialog_open is False
        assert lwd.load_dismissed_appids() == set()


class TestTemaDoDialogo:
    """GUI-05/P5 — espelho stub-level (roda headless, sem GTK real).

    O assert GTK-real vive em ``TestDialogoGtkReal`` (has_class de verdade);
    aqui a garantia é estrutural, por fonte: a construção aplica a classe de
    tema escopo-de-todo-o-CSS, e ANTES de qualquer chance de early-return.
    """

    def test_build_aplica_a_classe_de_tema(self) -> None:
        import inspect

        src = inspect.getsource(LaunchWrapperDialogMixin._build_wrapper_dialog)
        assert 'add_class("hefesto-dualsense4unix-window")' in src


# ---------------------------------------------------------------------------
# Diálogo GTK real (construção + sinal response de verdade)
# ---------------------------------------------------------------------------

_DISPLAY_OK = False
with contextlib.suppress(Exception):
    import gi as _gi

    _gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk as _Gdk

    _DISPLAY_OK = _Gdk.Display.get_default() is not None


@pytest.mark.skipif(
    not _DISPLAY_OK, reason="sem display GTK — construção real do diálogo"
)
class TestDialogoGtkReal:
    def test_message_dialog_nao_modal_com_texto_honesto_e_botoes(
        self, config_dir_isolado: Path
    ) -> None:
        from gi.repository import Gtk

        stub = _AppStub()
        dlg = stub._build_wrapper_dialog("777")
        try:
            assert isinstance(dlg, Gtk.MessageDialog)
            # GUI-05/P5: o diálogo carrega a classe de tema — sem ela, sob
            # XWayland no COSMIC ele abria Adwaita CLARO (tema nem instalado).
            assert dlg.get_style_context().has_class(
                "hefesto-dualsense4unix-window"
            )
            # NÃO-modal: aberto durante o jogo, não pode segurar grab GTK.
            assert dlg.get_modal() is False
            assert "777" in (dlg.get_property("text") or "")
            corpo = dlg.get_property("secondary-text") or ""
            # Texto honesto exigido pelo sprint: duplicado, nunca zero — e a
            # string constante visível/copiável.
            assert "DUPLICADO" in corpo
            assert "nunca zero controles" in corpo
            assert slo.WRAPPER_LAUNCH in corpo
            for response in (
                RESPONSE_COPY,
                RESPONSE_DISMISS,
                Gtk.ResponseType.CLOSE,
            ):
                assert dlg.get_widget_for_response(response) is not None
        finally:
            dlg.destroy()

    def test_sinal_response_real_dispensa_e_persiste(
        self, config_dir_isolado: Path
    ) -> None:
        stub = _AppStub()
        stub._wrapper_dialog_open = True
        dlg = stub._build_wrapper_dialog("888")

        dlg.emit("response", RESPONSE_DISMISS)

        assert lwd.load_dismissed_appids() == {"888"}
        assert stub._wrapper_dialog_open is False


# ---------------------------------------------------------------------------
# Fiação no HefestoApp — o lembrete engancha no tick lento EXISTENTE
# ---------------------------------------------------------------------------


def _gdkpixbuf_ok() -> bool:
    """GdkPixbuf disponível? A App real o importa (app.py); a CI headless de
    release não tem o typelib, então esta fiação-da-App-inteira é pulada lá
    (mesma filosofia do importorskip dos testes de GUI). Roda local."""
    try:
        import gi

        gi.require_version("GdkPixbuf", "2.0")
        from gi.repository import GdkPixbuf  # noqa: F401

        return True
    except Exception:
        return False


@pytest.mark.skipif(
    not _gdkpixbuf_ok(), reason="GdkPixbuf ausente (CI headless): a App real precisa dele"
)
class TestFiacaoNoApp:
    def test_app_compoe_o_mixin(self) -> None:
        from hefesto_dualsense4unix.app import app as app_mod

        assert LaunchWrapperDialogMixin in app_mod.HefestoApp.__mro__

    def test_render_slow_state_chama_o_super_e_depois_o_lembrete(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Zero timers novos: o gancho é o `_render_slow_state` do tick de
        2 Hz — o render da aba Status roda como sempre e SÓ DEPOIS o lembrete
        avalia o estado (ordem verificada)."""
        from hefesto_dualsense4unix.app import app as app_mod

        chamadas: list[tuple[str, Any]] = []
        monkeypatch.setattr(
            app_mod.StatusActionsMixin,
            "_render_slow_state",
            lambda self, state: chamadas.append(("status", state)),
        )
        monkeypatch.setattr(
            app_mod.LaunchWrapperDialogMixin,
            "_maybe_prompt_wrapper_dialog",
            lambda self, state: chamadas.append(("lembrete", state)),
        )

        app = object.__new__(app_mod.HefestoApp)
        estado = _state()
        app._render_slow_state(estado)

        assert chamadas == [("status", estado), ("lembrete", estado)]
