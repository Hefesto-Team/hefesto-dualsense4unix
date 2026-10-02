"""PERFIL-SALVA-TUDO — IDA E VOLTA: o gesto da aba chega ao ARQUIVO do perfil.

O PEDIDO DELA, 09/08/2026, literal:

    *"Preciso que cada feature de cada aba ao clicarmos em salvar perfil e
    aplicar (botão verde) tudo fique salvo no perfil ativo. Assim é impossível
    funcionar o app. faz uma solução robusta, considerando bt, todas as features
    que trabalhamos, e todas as features em cada aba, touch, giroscopio, speaker,
    mic, gatilho, lightbar. tudo."*

Este módulo é a RÉGUA, não a cura. Ele mede UMA pergunta por seção do perfil, e
a pergunta é sempre a mesma:

    o gesto da aba entra no rascunho, o "Salvar Perfil" do rodapé o leva ao
    disco, e o arquivo relido ainda o tem?

O caminho medido é o REAL, de ponta a ponta — nada de atalho pelo ``to_profile``:

    gesto da aba  ->  ``self.draft``  ->  ``on_save_profile`` (rodapé)
                  ->  ``_persist_profile_async``  ->  ``_gravar_perfil_async``
                  ->  ``profiles.loader.save_profile``  ->  DISCO
                  ->  ``profiles.loader.load_profile``  ->  asserção

É de propósito que a montagem do dublê espelhe a ``HefestoApp``: os defeitos
desta família SÓ existem na fronteira entre abas (uma escreve, outra reemite a
fotografia velha por cima), e um teste de módulo isolado nunca os veria.

HERMETISMO. Nenhum byte sai para o ``~/.config`` dela: o ``_hefesto_fake_env``
do ``tests/conftest.py`` isola ``XDG_CONFIG_HOME`` em ``tmp_path`` a cada teste,
e a fixture ``disco`` daqui CONFERE isso antes de deixar qualquer teste rodar —
o canário CANARIO-FS-01 do conftest é a segunda rede, não a primeira.

O QUE ESTE MÓDULO **NÃO** MEDE, declarado para ninguém tomar por garantia:

- **touch e giroscópio não existem no esquema de perfil.** ``Profile`` não tem
  campo de touchpad nem de giroscópio (``profiles/schema.py``) — não há o que
  fazer ida-e-volta. Isto não é lacuna de teste, é lacuna de PRODUTO, e está
  nomeada no relatório da sprint em vez de escondida atrás de um teste verde;
- o caminho de gravação da **aba Perfis** (``_build_profile_from_editor``), que
  é o OUTRO botão que grava. Ele lê widgets do editor e exigiria um glade
  montado; a fronteira entre ele e o rascunho já tem testemunha própria em
  ``test_perfil_salva_tudo_abas.py``.

O PORTÃO QUE IMPEDE A REGRESSÃO FUTURA mora ao lado, em
``test_perfil_salva_tudo_cobertura_das_secoes.py``: ele deriva
``Profile.model_fields`` em RUNTIME e reprova quando nasce uma seção nova sem
ida-e-volta aqui. A ponte entre os dois é ``SECOES_COBERTAS``, logo abaixo —
um dicionário LITERAL de propósito, para o portão poder lê-lo por AST, sem
importar este módulo (que exige GTK real) e sem pular onde não há PyGObject.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("PERFIL-SALVA-TUDO — ida e volta por seção")

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.actions.trigger_specs import get_spec
from hefesto_dualsense4unix.app.draft_config import (
    DraftConfig,
    registrar_alto_falante_no_rascunho,
)
from hefesto_dualsense4unix.profiles.loader import load_all_profiles, load_profile
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
    ProfileMicConfig,
    ProfileModeConfig,
    ProfileMouseConfig,
    ProfileSpeakerConfig,
    RumbleConfig,
    TriggerConfig,
    TriggersConfig,
)


SECOES_COBERTAS: dict[str, str] = {
    "name": "rodapé — o nome digitado no diálogo do Salvar Perfil",
    "match": "rodapé — _regra_do_save (disco > origem do rascunho > MatchManual)",
    "priority": "rodapé — _prioridade_do_save (quem já existe herda a do disco)",
    "triggers": "aba Gatilhos — TriggersActionsMixin._persist_params_to_draft",
    "leds": "aba Lightbar — LightbarActionsMixin._persist_leds_update",
    "rumble": "aba Rumble — RumbleActionsMixin._set_policy",
    "key_bindings": "aba Teclado — InputActionsMixin._persist_key_bindings_to_draft",
    "mouse": "aba Mouse — MouseActionsMixin.on_mouse_speed_changed",
    "mic": "card do controle — draft_config.registrar_microfone_no_rascunho",
    "speaker": "card do controle — draft_config.registrar_alto_falante_no_rascunho",
    "mode": "abas Início/Emulação — home_actions.registrar_modo_no_rascunho",
    "suppress_desktop_emulation": (
        "aba Emulação — emulation_actions.registrar_modo_jogo_no_rascunho"
    ),
    "controllers": "aba Lightbar com um controle no seletor — _persist_leds_update",
}

UNIQ_DE_TESTE = "aabbcc000002"


@pytest.fixture(autouse=True)
def _sync_run_in_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """``ipc_bridge.run_in_thread`` síncrono — sem loop GTK não há callback."""

    def _sync(fn: Any, on_success: Any, on_failure: Any = None) -> None:
        try:
            resultado = fn()
        except Exception as exc:
            if on_failure is not None:
                on_failure(exc)
            return
        on_success(resultado)

    monkeypatch.setattr(footer_actions.ipc_bridge, "run_in_thread", _sync)


@pytest.fixture
def disco(tmp_path: Path) -> Path:
    """O diretório de perfis DE VERDADE — provado dentro do ``tmp_path``."""
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    destino = profiles_dir(ensure=True)
    assert str(destino).startswith(str(tmp_path)), (
        "o diretório de perfis NÃO está isolado — este teste escreveria no "
        f"~/.config real da usuária ({destino})"
    )
    return destino


def _janela(
    draft: DraftConfig,
    ativo: str,
    *,
    alvo: str | None = None,
    conectados: dict[int, str] | None = None,
) -> Any:
    """Dublê com os mixins que a ``HefestoApp`` compõe de verdade.

    A composição não é zelo: o ``_prioridade_do_save`` do rodapé chama o
    ``_prioridade_acima_dos_catch_all`` da aba Perfis, e testar o rodapé sem o
    irmão mediria uma montagem que não existe em produção.

    ``_get`` devolve ``None`` de propósito (e não um ``MagicMock``): um mock é
    SEMPRE verdadeiro, e handlers que perguntam "o widget está ligado?"
    (``_mouse_is_enabled``) responderiam "sim" para um widget que não existe,
    disparando IPC no meio de um teste de disco.
    """
    from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
    from hefesto_dualsense4unix.app.actions.input_actions import InputActionsMixin
    from hefesto_dualsense4unix.app.actions.lightbar_actions import LightbarActionsMixin
    from hefesto_dualsense4unix.app.actions.profiles_actions import ProfilesActionsMixin
    from hefesto_dualsense4unix.app.actions.rumble_actions import RumbleActionsMixin
    from hefesto_dualsense4unix.app.actions.triggers_actions import TriggersActionsMixin

    class _Janela(  # type: ignore[misc]
        TriggersActionsMixin,
        LightbarActionsMixin,
        RumbleActionsMixin,
        ProfilesActionsMixin,
        InputActionsMixin,
        FooterActionsMixin,
    ):
        def __init__(self) -> None:
            self.draft = draft
            self._active_profile_name = ativo
            self._draft_baseline: Any = draft
            self._profiles_cache: list[Profile] = list(load_all_profiles())
            self.builder = MagicMock()
            self.toasts: list[str] = []
            self._refresh_guard = False
            self._rumble_guard_refresh = False
            self._mouse_guard_refresh = False
            self._triggers_guard_refresh = False
            self._trigger_preset_applying = False
            self._edit_target_uniq = alvo
            self._target_uniq_by_index = dict(conectados or {})
            self._trigger_mode: dict[str, Any] = {}
            self._trigger_param_widgets: dict[str, dict[str, Any]] = {}
            self._trigger_live_preview_timer: dict[str, int] = {"left": 0, "right": 0}
            self._key_bindings_store: Any = None
            self._escolha_pendente: Any = None
            self._rumble_policy: str | None = None

        def _get(self, widget_id: str) -> Any:
            return None

        def _status_toast(self, contexto: str, msg: str) -> None:
            self.toasts.append(msg)

        def _footer_toast(self, msg: str, context: str = "footer") -> None:
            self.toasts.append(msg)

        def _toast_profile(self, msg: str) -> None:
            self.toasts.append(msg)

        def _toast_light(self, msg: str) -> None:
            self.toasts.append(msg)

        def _toast_rumble(self, msg: str) -> None:
            self.toasts.append(msg)

        def _toast_mouse(self, msg: str) -> None:
            self.toasts.append(msg)

        def _toast_input(self, msg: str) -> None:
            self.toasts.append(msg)

        def _reload_profiles_store(
            self, select_name: str | None = None, on_done: Any | None = None
        ) -> None:
            self._profiles_cache = list(load_all_profiles())
            if on_done is not None:
                on_done()

        def _notify_launch_env_refresh(self) -> None:
            return None

        def _refresh_mouse_from_daemon_async(self) -> None:
            return None

        def _refresh_mouse_view(self) -> None:
            return None

        def _refresh_key_bindings_from_draft(self) -> None:
            return None

    return _Janela()


class _Escala:
    """Dublê de ``Gtk.Scale``/``Gtk.Adjustment`` — só o que os handlers leem."""

    def __init__(self, valor: float) -> None:
        self._valor = valor

    def get_value(self) -> float:
        return self._valor


class _Combo:
    """Dublê de ``Gtk.ComboBoxText`` — só o ``get_active_id``."""

    def __init__(self, ident: str | None) -> None:
        self._id = ident

    def get_active_id(self) -> str | None:
        return self._id


class _Caixa:
    """Dublê de ``Gtk.CheckButton`` — só o ``get_active``."""

    def __init__(self, ativo: bool) -> None:
        self._ativo = ativo

    def get_active(self) -> bool:
        return self._ativo


def _perfil_de_partida(nome: str = "Pragmata") -> Profile:
    """O perfil que ela tem em disco quando abre a janela."""
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=["steam_app_3357650"]),
        priority=60,
        leds=LedsConfig(lightbar=(97, 53, 131), auto_player_colors=False),
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"), right=TriggerConfig(mode="Off")
        ),
        rumble=RumbleConfig(passthrough=True),
    )


def _semear(perfil: Profile) -> Profile:
    """Grava o perfil de partida no disco isolado, pelo caminho de produção."""
    from hefesto_dualsense4unix.profiles.loader import save_profile

    save_profile(perfil, origem="teste:ida-e-volta")
    return perfil


def _salvar_pelo_rodape(janela: Any, nome: str) -> None:
    """O gesto dela: botão "Salvar Perfil", confirma o nome, confirma a troca."""
    dialogos = MagicMock()
    dialogos.prompt_profile_name.return_value = nome
    dialogos.prompt_overwrite_existing.return_value = True
    with patch(
        "hefesto_dualsense4unix.app.actions.footer_actions.gui_dialogs", dialogos
    ):
        janela.on_save_profile()


def _aplicar_pelo_rodape(janela: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O gesto dela: botão VERDE "Aplicar", com o daemon respondendo tudo ok."""
    secoes = ["triggers", "leds", "rumble", "mouse", "mic", "keyboard", "controllers"]

    def _call_async(
        metodo: str,
        params: Any = None,
        on_success: Any = None,
        on_failure: Any = None,
        timeout_s: float | None = None,
    ) -> None:
        if on_success is not None:
            on_success({"status": "ok", "applied": secoes, "failed": {}})

    monkeypatch.setattr(footer_actions.ipc_bridge, "call_async", _call_async)
    janela.on_apply_draft()


def _relido(nome: str) -> Profile:
    """O perfil como ele ficou NO DISCO — nunca o objeto em memória."""
    return load_profile(nome)


class _LinhaDoPendente:
    """Dublê do rótulo "vai mudar para:" da aba Início — só o que ele expõe."""

    def __init__(self) -> None:
        self.texto = ""
        self.visivel = False

    def set_text(self, texto: str) -> None:
        self.texto = texto

    def set_visible(self, visivel: bool) -> None:
        self.visivel = bool(visivel)

    def get_visible(self) -> bool:
        return self.visivel


def _sem_daemon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum IPC de leitura sai desta bancada — nem para o daemon dela."""

    def _explode(*_a: Any, **_kw: Any) -> Any:
        raise RuntimeError("daemon ausente nesta bancada")

    monkeypatch.setattr(footer_actions.ipc_bridge, "_run_call", _explode)


def _armadilha_de_apply_mode(
    monkeypatch: pytest.MonkeyPatch, *, desfecho: str = "sucesso"
) -> list[tuple[str, str | None]]:
    """Registra CADA ``apply_mode`` e devolve a lista — a régua da transição."""
    from hefesto_dualsense4unix.app.actions import mode_transition

    chamadas: list[tuple[str, str | None]] = []

    def _apply_mode_falso(
        mode_id: str,
        *,
        flavor: str | None = None,
        on_done: Callable[[Any], bool],
        on_fail: Callable[[Exception], bool],
    ) -> None:
        chamadas.append((mode_id, flavor))
        if desfecho == "sucesso":
            on_done({"status": "ok"})
        elif desfecho == "falha":
            on_fail(RuntimeError("o daemon recusou a transição"))

    monkeypatch.setattr(mode_transition, "apply_mode", _apply_mode_falso)
    return chamadas


def _gesto_triggers(janela: Any) -> None:
    """Aba Gatilhos: escolher "Rígido" e mexer nas escalas de posição/força."""
    spec = get_spec("Rigid")
    assert spec is not None, "o preset 'Rigid' sumiu do trigger_specs"
    janela._trigger_mode["left"] = _Combo("Rigid")
    janela._trigger_param_widgets["left"] = {
        p.name: _Escala(7 if p.name != "force" else 240) for p in spec.params
    }
    janela._persist_params_to_draft("left")


def _confere_triggers(perfil: Profile) -> None:
    assert perfil.triggers.left.mode == "Rigid", (
        "o gatilho esquerdo voltou para "
        f"{perfil.triggers.left.mode!r} — o modo escolhido na aba não chegou "
        "ao arquivo"
    )
    assert list(perfil.triggers.left.params) == [7, 240], (
        f"os parâmetros do gatilho chegaram como {perfil.triggers.left.params!r} "
        "— o que ela sente no dedo não é o que está no disco"
    )


def _gesto_leds(janela: Any) -> None:
    """Aba Lightbar: escolher uma cor e um brilho em "Todos"."""
    janela._persist_leds_update({"lightbar_rgb": (12, 34, 56)})
    janela._persist_leds_update({"lightbar_brightness": 40})


def _confere_leds(perfil: Profile) -> None:
    assert tuple(perfil.leds.lightbar) == (12, 34, 56), (
        f"a cor no arquivo é {tuple(perfil.leds.lightbar)!r} — a lightbar que "
        "ela escolheu não sobreviveu ao salvar"
    )
    assert abs(perfil.leds.lightbar_brightness - 0.40) < 1e-6, (
        f"o brilho no arquivo é {perfil.leds.lightbar_brightness!r}, e ela "
        "escolheu 40%"
    )


def _gesto_rumble(janela: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Aba Rumble: clicar em "Economia" (a política persiste no perfil)."""
    from hefesto_dualsense4unix.app.actions import rumble_actions

    monkeypatch.setattr(
        rumble_actions, "rumble_policy_set_checked", lambda *a, **kw: (True, None)
    )
    janela.on_rumble_policy_economia(None)


def _confere_rumble(perfil: Profile) -> None:
    assert perfil.rumble.policy == "economia", (
        f"a política de vibração no arquivo é {perfil.rumble.policy!r} — o "
        "botão que ela afundou na aba Rumble não chegou ao perfil"
    )


def _gesto_key_bindings(janela: Any) -> None:
    """Aba Teclado: mapear o triângulo para a tecla C."""
    janela._key_bindings_store = [["triangle", "KEY_C"]]
    janela._persist_key_bindings_to_draft()


def _confere_key_bindings(perfil: Profile) -> None:
    """O gesto da aba CHEGOU, e o que a aba não mostra CONTINUA lá."""
    bindings = perfil.key_bindings or {}
    assert bindings.get("triangle") == ["KEY_C"], (
        f"os bindings no arquivo são {perfil.key_bindings!r} — o teclado que "
        "ela montou não sobreviveu ao salvar"
    )
    intocados = {
        chave: valor
        for chave, valor in bindings.items()
        if chave != "triangle"
    }
    assert intocados, (
        "o perfil ficou SÓ com o que a aba mostra. O gesto voltou a apagar o "
        "que a lista não exibe — é a N1 desfeita, e o preço é o perfil dela"
    )


def _gesto_mouse(janela: Any) -> None:
    """Aba Mouse: arrastar os dois controles deslizantes de velocidade."""
    janela.on_mouse_speed_changed(_Escala(11))
    janela.on_mouse_scroll_speed_changed(_Escala(4))


def _confere_mouse(perfil: Profile) -> None:
    assert perfil.mouse is not None, (
        "a seção `mouse` NÃO existe no arquivo — arrastar os controles de "
        "velocidade não criou a seção (BUG-MOUSE-SAVE-DROPS-SECTION-01)"
    )
    assert (perfil.mouse.speed, perfil.mouse.scroll_speed) == (11, 4), (
        f"as velocidades no arquivo são {perfil.mouse.speed}/"
        f"{perfil.mouse.scroll_speed} — ela arrastou para 11/4"
    )


def _gesto_mic(janela: Any) -> None:
    """Card do controle: o VOLUME da captura e o MUDO do firmware."""
    from hefesto_dualsense4unix.app.draft_config import (
        MicDraft,
        registrar_microfone_no_rascunho,
    )

    janela.draft = janela.draft.model_copy(
        update={"mic": MicDraft(button_toggles_system=False, dirty=True, in_profile=True)}
    )
    registrar_microfone_no_rascunho(janela, volume=70, muted=True)


def _confere_mic(perfil: Profile) -> None:
    assert perfil.mic is not None, (
        "a seção `mic` NÃO existe no arquivo — o microfone não foi salvo no "
        "perfil (é a queixa literal de 18/08: nenhum dos 18 perfis dela tinha "
        "esta seção)"
    )
    assert perfil.mic.button_toggles_system is False, (
        "o `button_toggles_system` do arquivo é "
        f"{perfil.mic.button_toggles_system!r} — ela desligou"
    )
    assert perfil.mic.volume == 70, (
        f"o volume do microfone no arquivo é {perfil.mic.volume!r} — ela "
        "deixou 70 no controle deslizante do card"
    )
    assert perfil.mic.muted is None, (
        f"o mudo do microfone chegou ao arquivo ({perfil.mic.muted!r}) — ele é "
        "do controle, e o perfil não o leva"
    )


def _gesto_speaker(janela: Any) -> None:
    """Card do controle: volume, mudo e o CANAL de saída (a rota do 09/08)."""
    registrar_alto_falante_no_rascunho(janela, volume=180, muted=False, rota=2)


def _confere_speaker(perfil: Profile) -> None:
    assert perfil.speaker is not None, (
        "a seção `speaker` NÃO existe no arquivo — o volume que ela ajustou no "
        "card não virou configuração do perfil"
    )
    assert perfil.speaker.volume == 180, (
        f"o volume no arquivo é {perfil.speaker.volume} — ela deixou 180"
    )
    assert perfil.speaker.rota == 2, (
        f"a rota de saída no arquivo é {perfil.speaker.rota!r} — ela escolheu o "
        "canal 2 (L no fone, R no alto-falante)"
    )


def _gesto_mode(janela: Any) -> None:
    """Abas Início/Emulação: "Jogar pelo Hefesto" com a máscara Xbox."""
    from hefesto_dualsense4unix.app.actions.home_actions import registrar_modo_no_rascunho

    registrar_modo_no_rascunho(janela, "gamepad", "xbox")


def _confere_mode(perfil: Profile) -> None:
    assert perfil.mode is not None, (
        "a seção `mode` NÃO existe no arquivo — o modo que ela escolheu na aba "
        "Início evaporou no salvar (é a queixa literal do pragmata2.json)"
    )
    assert perfil.mode.kind == "gamepad", (
        f"o modo no arquivo é {perfil.mode.kind!r} — ela escolheu 'gamepad'"
    )
    assert perfil.mode.gamepad_flavor == "xbox", (
        f"a máscara no arquivo é {perfil.mode.gamepad_flavor!r} — ela escolheu "
        "'xbox'"
    )


def _gesto_suppress(janela: Any) -> None:
    """Aba Emulação: ligar o "modo jogo" (suspender mouse e teclado)."""
    from hefesto_dualsense4unix.app.actions.emulation_actions import (
        registrar_modo_jogo_no_rascunho,
    )

    registrar_modo_jogo_no_rascunho(janela, True)


def _confere_suppress(perfil: Profile) -> None:
    assert perfil.suppress_desktop_emulation is True, (
        "o `suppress_desktop_emulation` do arquivo é False — o modo jogo que "
        "ela ligou na aba Emulação não ficou salvo"
    )


def _gesto_controllers(janela: Any) -> None:
    """Aba Lightbar COM um controle selecionado no seletor do banner."""
    janela._edit_target_uniq = UNIQ_DE_TESTE
    janela._persist_leds_update({"lightbar_rgb": (200, 10, 10)})


def _confere_controllers(perfil: Profile) -> None:
    assert perfil.controllers, (
        "o mapa `controllers` NÃO existe no arquivo — a cor que ela ajustou "
        "para UM controle não ficou dentro do perfil"
    )
    entrada = perfil.controllers.get(UNIQ_DE_TESTE)
    assert entrada is not None and entrada.leds is not None, (
        f"o override do controle {UNIQ_DE_TESTE} não tem seção de LEDs: "
        f"{perfil.controllers!r}"
    )
    assert tuple(entrada.leds.lightbar) == (200, 10, 10), (
        f"a cor do override é {tuple(entrada.leds.lightbar)!r} — ela escolheu "
        "(200, 10, 10) com aquele controle selecionado"
    )


def _gesto_nome(janela: Any) -> None:
    """O nome não tem gesto de aba: ele é o que ela digita no diálogo."""
    return None


def _confere_nome(perfil: Profile) -> None:
    assert perfil.name == "Pragmata", (
        f"o perfil no disco se chama {perfil.name!r} — o nome do arquivo e o "
        "nome de dentro dele divergiram"
    )


def _gesto_match(janela: Any) -> None:
    """A regra não tem gesto de rodapé: ela vem do disco (REGRA-NAO-SE-PERDE)."""
    return None


def _confere_match(perfil: Profile) -> None:
    assert isinstance(perfil.match, MatchCriteria), (
        f"a regra virou {type(perfil.match).__name__} — salvar rebaixou o "
        "perfil do jogo a catch-all (REGRA-NAO-SE-PERDE-01)"
    )
    assert perfil.match.window_class == ["steam_app_3357650"], (
        f"a regra no arquivo é {perfil.match.window_class!r} — a do disco era "
        "steam_app_3357650"
    )


def _gesto_priority(janela: Any) -> None:
    """A prioridade não tem gesto de rodapé: quem existe herda a do disco."""
    return None


def _confere_priority(perfil: Profile) -> None:
    assert perfil.priority == 60, (
        f"a prioridade no arquivo é {perfil.priority} — era 60 no disco, e o "
        "rodapé não pode recalculá-la (a catraca do GRAVA-POR-UM-FUNIL-01)"
    )


_GESTOS: dict[str, tuple[Callable[..., Any], Callable[[Profile], None]]] = {
    "name": (_gesto_nome, _confere_nome),
    "match": (_gesto_match, _confere_match),
    "priority": (_gesto_priority, _confere_priority),
    "triggers": (_gesto_triggers, _confere_triggers),
    "leds": (_gesto_leds, _confere_leds),
    "rumble": (_gesto_rumble, _confere_rumble),
    "key_bindings": (_gesto_key_bindings, _confere_key_bindings),
    "mouse": (_gesto_mouse, _confere_mouse),
    "mic": (_gesto_mic, _confere_mic),
    "speaker": (_gesto_speaker, _confere_speaker),
    "mode": (_gesto_mode, _confere_mode),
    "suppress_desktop_emulation": (_gesto_suppress, _confere_suppress),
    "controllers": (_gesto_controllers, _confere_controllers),
}

_QUEBRADAS_HOJE: dict[str, str] = {}


def _gesto_de(campo: str, janela: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Chama o gesto do campo, passando o ``monkeypatch`` a quem precisa dele."""
    gesto = _GESTOS[campo][0]
    if campo == "rumble":
        gesto(janela, monkeypatch)
        return
    gesto(janela)


def _casos() -> list[Any]:
    """Um ``pytest.param`` por seção, com o xfail estrito de quem está quebrada."""
    saida: list[Any] = []
    for campo in SECOES_COBERTAS:
        motivo = _QUEBRADAS_HOJE.get(campo)
        marcas = (
            [pytest.mark.xfail(strict=True, reason=motivo)] if motivo else []
        )
        saida.append(pytest.param(campo, id=campo, marks=marcas))
    return saida


class TestIdaEVolta:
    """Uma seção do perfil por caso, e o caminho REAL entre a aba e o arquivo."""

    @pytest.mark.parametrize("campo", _casos())
    def test_o_gesto_da_aba_chega_ao_arquivo(
        self, campo: str, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Gesto na aba -> "Salvar Perfil" -> disco -> releitura."""
        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)

        _gesto_de(campo, janela, monkeypatch)
        _salvar_pelo_rodape(janela, perfil.name)

        _GESTOS[campo][1](_relido(perfil.name))

    @pytest.mark.parametrize("campo", _casos())
    def test_o_gesto_sobrevive_ao_aplicar_antes_de_salvar(
        self, campo: str, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ordem que ela usa: mexe, clica no VERDE, e SÓ ENTÃO salva."""
        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)

        _gesto_de(campo, janela, monkeypatch)
        _aplicar_pelo_rodape(janela, monkeypatch)
        _salvar_pelo_rodape(janela, perfil.name)

        _GESTOS[campo][1](_relido(perfil.name))


class TestTudoDeUmaVezSo:
    """Todas as abas mexidas na MESMA sessão, e um "Salvar Perfil" só."""

    def test_uma_sessao_inteira_de_ajustes_sobrevive_a_um_unico_salvar(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sete abas, um clique em Salvar, e o arquivo tem as sete coisas."""
        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)

        ordem = [c for c in SECOES_COBERTAS if c != "controllers"] + ["controllers"]
        for campo in ordem:
            if campo in _QUEBRADAS_HOJE:
                continue
            _gesto_de(campo, janela, monkeypatch)
        _salvar_pelo_rodape(janela, perfil.name)

        relido = _relido(perfil.name)
        perdidas: list[str] = []
        for campo in SECOES_COBERTAS:
            if campo in _QUEBRADAS_HOJE:
                continue
            try:
                _GESTOS[campo][1](relido)
            except AssertionError as exc:
                perdidas.append(f"{campo}: {exc}")
        assert not perdidas, (
            "seções perdidas quando TODAS as abas são mexidas na mesma sessão "
            "(o cenário da queixa dela):\n  - " + "\n  - ".join(perdidas)
        )

    def test_a_inicio_entra_no_cenario_pelo_dedo_dela_com_um_salvar_so(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O mesmo cenário, mas a aba Início entra pelo GESTO — não pelo escritor."""
        from hefesto_dualsense4unix.app.actions import home_actions

        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)
        _sem_daemon(monkeypatch)
        _armadilha_de_apply_mode(monkeypatch)

        ordem = [c for c in SECOES_COBERTAS if c not in ("controllers", "mode")]
        for campo in [*ordem, "controllers"]:
            if campo in _QUEBRADAS_HOJE:
                continue
            _gesto_de(campo, janela, monkeypatch)

        home_actions.marcar_escolha(janela, "modo", "gamepad")
        home_actions.marcar_escolha(janela, "mascara", "xbox")

        _salvar_pelo_rodape(janela, perfil.name)

        relido = _relido(perfil.name)
        perdidas: list[str] = []
        for campo in SECOES_COBERTAS:
            if campo in _QUEBRADAS_HOJE:
                continue
            try:
                _GESTOS[campo][1](relido)
            except AssertionError as exc:
                perdidas.append(f"{campo}: {exc}")
        assert not perdidas, (
            "seções perdidas quando ela passa por TODAS as abas e clica em "
            "Salvar só na última:\n  - " + "\n  - ".join(perdidas)
        )


class TestOBotaoVerdeLevaAEscolhaDaAbaInicioAoArquivo:
    """O caminho INTEIRO do modo, do jeito que ele funciona desde 08/08/2026.

    A AGORA-E-DEPOIS-01 separou os dois tempos da janela: clicar no seletor de
    modo da aba Início **marca** a escolha (``marcar_escolha``) e não aplica
    nada; quem aplica é o botão VERDE do rodapé, e é o callback de sucesso dele
    que registra o modo no rascunho (``registrar_modo_no_rascunho``, chamado de
    ``footer_actions._aplicar_escolha_pendente``).

    O caso parametrizado de ``mode`` lá em cima entra pelo escritor. Este entra
    pelo DEDO DELA: marca, clica no verde, salva. São medições diferentes — a
    primeira mede a persistência, esta mede a FIAÇÃO entre o botão e o
    escritor, que é onde o modo dela sumia antes desta sprint.
    """

    def test_marcar_na_inicio_clicar_no_verde_e_salvar_grava_o_modo(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: apague a chamada ``registrar_modo_no_rascunho`` do ``_done``
        de ``footer_actions._aplicar_escolha_pendente`` e este teste reprova com
        "a seção `mode` NÃO existe no arquivo" — enquanto o caso parametrizado
        de ``mode``, que entra direto pelo escritor, continua VERDE. É essa
        diferença que faz os dois valerem a pena.
        """
        from hefesto_dualsense4unix.app.actions import home_actions, mode_transition

        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)

        def _sem_daemon(*_a: Any, **_kw: Any) -> Any:
            raise RuntimeError("daemon ausente nesta bancada")

        monkeypatch.setattr(footer_actions.ipc_bridge, "_run_call", _sem_daemon)

        aplicados: list[tuple[str, str | None]] = []

        def _apply_mode_falso(
            mode_id: str,
            *,
            flavor: str | None = None,
            on_done: Callable[[Any], bool],
            on_fail: Callable[[Exception], bool],
        ) -> None:
            aplicados.append((mode_id, flavor))
            on_done(True)

        monkeypatch.setattr(mode_transition, "apply_mode", _apply_mode_falso)

        home_actions.marcar_escolha(janela, "modo", "gamepad")
        home_actions.marcar_escolha(janela, "mascara", "xbox")
        assert janela._escolha_pendente, "a escolha dela não ficou marcada"

        _aplicar_pelo_rodape(janela, monkeypatch)
        assert aplicados == [("gamepad", "xbox")], (
            f"o botão verde não pediu a transição de modo: {aplicados!r}"
        )

        _salvar_pelo_rodape(janela, perfil.name)
        _confere_mode(_relido(perfil.name))


class TestOSalvarSozinhoLevaAEscolhaDaAbaInicioAoArquivoEAoControle:
    """O Salvar sem o verde — e, desde 11/08/2026, ele também APLICA.

    A classe irmã acima mede o caminho COM o botão verde, e ele continua igual.
    Esta mede o caminho que ela descreveu em 10/08: mexer em tudo, aba por aba,
    e clicar em Salvar **uma vez só**, na última.

    NOTA DATADA — 11/08/2026 (O-SALVAR-TAMBEM-APLICA-01). Esta classe se chamava
    ``...AoArquivo``, e o que estava travado nela era a decisão CONTRÁRIA: a de
    que o Salvar grava e **não** aplica, com a pendência ficando acesa de
    propósito e um toast mandando clicar no verde. Aquilo não era descuido —
    estava escrito como consequência assumida, com a pergunta declarada EM
    ABERTO para ela. Ela respondeu, e a resposta é uma frase: *"salvar também
    aplica"*.

    O que caducou, exatamente, para quem for ler o histórico:

    - o toast *"foi para o arquivo e vale na próxima abertura; para mudar agora,
      clique em Aplicar"* — a divisão que ele ensinava deixou de existir;
    - a asserção de que ``apply_mode`` NUNCA sai de um Salvar. Ela virou o
      contrário: sai, e este arquivo prova que sai.

    O que **não** caducou, e continua medido aqui: registrar não é aplicar
    (HARM-05) segue de pé no ESCRITOR — quem aplica é o rodapé, nunca
    ``recolher_escolha_pendente_no_rascunho``, e o portão de AST ao lado
    (``test_perfil_salva_tudo_registrar_nao_e_aplicar.py``) é quem tranca isso.
    """

    def test_marcar_na_inicio_e_salvar_sem_o_verde_grava_e_aplica_o_modo(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ela marca o modo na Início e salva **SEM** tocar no botão verde."""
        from hefesto_dualsense4unix.app.actions import home_actions

        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)
        janela._home_pendente_label = _LinhaDoPendente()
        _sem_daemon(monkeypatch)
        aplicados = _armadilha_de_apply_mode(monkeypatch)

        home_actions.marcar_escolha(janela, "modo", "gamepad")
        home_actions.marcar_escolha(janela, "mascara", "xbox")
        assert janela._home_pendente_label.visivel, (
            "a linha 'vai mudar para:' nem chegou a acender — o teste mediria "
            "o apagar de uma linha que nunca esteve na tela"
        )

        _salvar_pelo_rodape(janela, perfil.name)

        _confere_mode(_relido(perfil.name))

        assert aplicados == [("gamepad", "xbox")], (
            "o Salvar não pediu a transição de modo ao daemon — o arquivo "
            f"mudou e a máquina ficou para trás: {aplicados!r}"
        )

        assert janela._escolha_pendente is None, (
            "a pendência sobreviveu a um Salvar que APLICOU: "
            f"{janela._escolha_pendente!r} — a janela promete uma mudança que "
            "já aconteceu"
        )
        assert not janela._home_pendente_label.visivel, (
            "a linha 'vai mudar para:' continua acesa depois de o daemon "
            f"confirmar a mudança (texto: {janela._home_pendente_label.texto!r})"
        )

        ultimo = janela.toasts[-1]
        assert "Jogar pelo Hefesto" in ultimo and "já está valendo" in ultimo, (
            f"o último toast do Salvar não diz que o modo já vale: {ultimo!r}"
        )
        mentiras = [
            t
            for t in janela.toasts
            if "próxima abertura" in t or "clique em “Aplicar”" in t
        ]
        assert not mentiras, (
            "o Salvar ainda manda esperar a próxima abertura (ou clicar no "
            f"verde) com o modo JÁ aplicado: {mentiras!r}"
        )

    def test_a_falha_ao_aplicar_nao_desfaz_o_arquivo_e_o_toast_nao_mente(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O desfecho honesto quando o daemon recusa a transição.

        A decisão, escrita por extenso em
        ``footer_actions._aplicar_o_modo_que_foi_gravado``: o arquivo FICA como
        ela pediu (um perfil descreve o que vale quando ele ativa, e o daemon
        aplica a seção ``mode`` na ativação), a pendência FICA acesa (é a única
        coisa na tela que diz que o daemon está atrasado em relação ao arquivo),
        e o toast diz as DUAS metades — gravei, não apliquei.

        MORDIDA: faça o ``_falhou`` chamar ``_esquecer_a_pendencia(self)`` — o
        caminho "limpa sempre", que parece simetria e é a janela mentindo por
        omissão — e este teste reprova com a linha apagada e o daemon no modo
        velho.
        """
        from hefesto_dualsense4unix.app.actions import home_actions

        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)
        janela._home_pendente_label = _LinhaDoPendente()
        _sem_daemon(monkeypatch)
        aplicados = _armadilha_de_apply_mode(monkeypatch, desfecho="falha")

        home_actions.marcar_escolha(janela, "modo", "gamepad")
        home_actions.marcar_escolha(janela, "mascara", "xbox")

        _salvar_pelo_rodape(janela, perfil.name)

        assert aplicados == [("gamepad", "xbox")], (
            f"o Salvar nem tentou a transição: {aplicados!r}"
        )
        _confere_mode(_relido(perfil.name))
        assert janela._escolha_pendente == {"modo": "gamepad", "mascara": "xbox"}, (
            "a escolha dela evaporou numa transição que FALHOU: "
            f"{janela._escolha_pendente!r}"
        )
        assert janela._home_pendente_label.visivel, (
            "a linha 'vai mudar para:' apagou sem que o daemon tivesse mudado "
            "coisa nenhuma — a janela mentindo por omissão"
        )
        ultimo = janela.toasts[-1]
        assert "salvo" in ultimo and "não consegui mudar" in ultimo, (
            f"o toast da falha não conta as duas metades: {ultimo!r}"
        )
        assert "já está valendo" not in ultimo, (
            f"o toast anuncia um modo que o daemon RECUSOU: {ultimo!r}"
        )

    def test_o_salvar_nao_impoe_a_mascara_que_ela_nao_escolheu(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AUTO-01.3 no caminho novo: quem não escolheu não manda."""
        from hefesto_dualsense4unix.app.actions import home_actions

        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)
        janela._modo_vigente_do_daemon = "desktop"
        janela._mascara_vigente_do_daemon = "dualsense"
        _sem_daemon(monkeypatch)
        aplicados = _armadilha_de_apply_mode(monkeypatch)

        home_actions.marcar_escolha(janela, "modo", "gamepad")

        _salvar_pelo_rodape(janela, perfil.name)

        assert aplicados == [("gamepad", None)], (
            "o Salvar impôs uma máscara que ela não escolheu — ecoar o vigente "
            f"do daemon é o segundo dono do valor: {aplicados!r}"
        )
        relido = _relido(perfil.name)
        assert relido.mode is not None and relido.mode.kind == "gamepad", (
            f"o modo não chegou ao arquivo: {relido.mode!r}"
        )

    def test_mascara_sem_modo_com_daemon_offline_nao_grava_nem_aplica_nada(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem ``kind`` conhecido não se grava NADA — nem um default nosso.

        O esquema não aceita máscara sem ``kind``
        (``profiles/schema.ProfileModeConfig``), então o recolhimento precisa de
        um modo. Ele o tira da escolha dela ou do vigente do daemon — a MESMA
        expressão do "Aplicar" (``footer_actions._aplicar_escolha_pendente``).
        Com o daemon offline não há nem um nem outro, e a resposta honesta é
        não escrever: escolher ``"gamepad"`` por conta própria aqui criaria um
        SEGUNDO dono do valor, que é o defeito que a AUTO-01.3 enterrou.

        O-SALVAR-TAMBEM-APLICA-01 (11/08/2026): e não se aplica nada tampouco.
        Nada gravado, nada aplicado — a transição é a sombra da gravação, nunca
        um gesto por conta própria.

        MORDIDA: troque, em ``home_actions.recolher_escolha_pendente_no_rascunho``,
        o degrau de trás por um default (``or MODE_GAMEPAD``) e este teste
        reprova com "o Salvar inventou um modo".
        """
        from hefesto_dualsense4unix.app.actions import home_actions

        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)
        assert getattr(janela, "_modo_vigente_do_daemon", None) is None
        _sem_daemon(monkeypatch)
        aplicados = _armadilha_de_apply_mode(monkeypatch)

        home_actions.marcar_escolha(janela, "mascara", "xbox")

        _salvar_pelo_rodape(janela, perfil.name)

        relido = _relido(perfil.name)
        assert relido.mode is None, (
            f"o Salvar inventou um modo: {relido.mode!r} — sem escolha dela e "
            "sem vigente do daemon não há `kind` honesto para gravar"
        )
        assert aplicados == [], (
            f"o Salvar aplicou um modo que ele não gravou: {aplicados!r}"
        )
        assert janela._escolha_pendente == {"mascara": "xbox"}, (
            f"a escolha de máscara dela evaporou: {janela._escolha_pendente!r}"
        )


class TestARegistroEACoberturaNaoPodemDivergir:
    """O literal que o portão lê tem de descrever os casos que existem aqui."""

    def test_o_literal_e_os_gestos_tem_as_mesmas_chaves(self) -> None:
        """``SECOES_COBERTAS`` é lido por AST — ele não pode mentir."""
        assert set(SECOES_COBERTAS) == set(_GESTOS), (
            "SECOES_COBERTAS (que o portão lê) e _GESTOS (o que roda de fato) "
            f"divergiram: só no literal {set(SECOES_COBERTAS) - set(_GESTOS)}, "
            f"só nos gestos {set(_GESTOS) - set(SECOES_COBERTAS)}"
        )

    def test_toda_secao_quebrada_tem_motivo_escrito(self) -> None:
        """xfail sem razão é defeito escondido, não defeito documentado."""
        for campo, motivo in _QUEBRADAS_HOJE.items():
            assert campo in SECOES_COBERTAS, (
                f"{campo!r} está marcada como quebrada e não é seção coberta"
            )
            assert motivo and len(motivo) > 40, (
                f"a razão do xfail de {campo!r} é curta demais para explicar "
                f"onde o dado se perde: {motivo!r}"
            )


class TestOInstrumentoNaoMente:
    """A régua é conferida antes de qualquer veredito dela ser citado."""

    def test_a_aparelhagem_escreve_no_disco_de_verdade(self, disco: Path) -> None:
        """O arquivo existe, com o slug do nome — e o conteúdo é JSON."""
        import json

        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)
        _salvar_pelo_rodape(janela, perfil.name)

        arquivo = disco / "pragmata.json"
        assert arquivo.exists(), (
            f"o 'Salvar Perfil' não deixou arquivo em {disco} — os casos de "
            "ida-e-volta estariam medindo o nada"
        )
        assert json.loads(arquivo.read_text(encoding="utf-8"))["name"] == "Pragmata"

    def test_sem_o_gesto_a_conferencia_reprova(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A prova de que nenhuma conferência passa de graça."""
        sem_gesto_e_esperado = {"name", "match", "priority"}
        passaram_de_graca: list[str] = []
        for campo in SECOES_COBERTAS:
            if campo in sem_gesto_e_esperado:
                continue
            perfil = _semear(_perfil_de_partida())
            janela = _janela(DraftConfig.from_profile(perfil), perfil.name)
            _salvar_pelo_rodape(janela, perfil.name)
            try:
                _GESTOS[campo][1](_relido(perfil.name))
            except AssertionError:
                continue
            passaram_de_graca.append(campo)
        assert not passaram_de_graca, (
            "estas conferências passam SEM o gesto da aba — elas não medem "
            f"nada: {passaram_de_graca}"
        )

    def test_uma_perda_deliberada_e_vista(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mordida provada DENTRO da suíte, sem arrancar produção à mão."""
        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)
        _gesto_de("mode", janela, monkeypatch)

        original = DraftConfig.to_profile

        def _sem_mode(self: DraftConfig, nome: str, priority: int | None = None) -> Any:
            return original(self, nome, priority).model_copy(update={"mode": None})

        monkeypatch.setattr(DraftConfig, "to_profile", _sem_mode)
        _salvar_pelo_rodape(janela, perfil.name)

        with pytest.raises(AssertionError, match="mode"):
            _confere_mode(_relido(perfil.name))


class TestOQueOEsquemaNaoTem:
    """Touch e giroscópio: a lacuna é de PRODUTO, e fica escrita aqui."""

    def test_touch_e_giroscopio_ainda_nao_sao_campos_do_perfil(self) -> None:
        """MORDIDA: acrescente ``gyro`` ao ``Profile`` e este teste reprova."""
        campos = set(Profile.model_fields)
        nascidos = {
            nome
            for nome in campos
            if any(
                pista in nome.lower()
                for pista in ("touch", "gyro", "giro", "motion", "sensor")
            )
        }
        assert not nascidos, (
            f"nasceram campos de touch/giroscópio no perfil ({sorted(nascidos)}) "
            "— acrescente o caso de ida-e-volta em SECOES_COBERTAS/_GESTOS, "
            "senão a feature nasce sem prova de que chega ao disco"
        )


class TestOsTiposDoEsquemaContinuamOsMesmos:
    """As seções opcionais continuam sendo as classes que os casos conferem."""

    def test_as_secoes_opcionais_tem_os_tipos_esperados(self, disco: Path) -> None:
        perfil = Profile(
            name="sonda",
            match=MatchCriteria(window_class=["x"]),
            mouse=ProfileMouseConfig(enabled=True),
            mic=ProfileMicConfig(button_toggles_system=True),
            speaker=ProfileSpeakerConfig(volume=100),
            mode=ProfileModeConfig(kind="gamepad"),
        )
        assert isinstance(perfil.mouse, ProfileMouseConfig)
        assert isinstance(perfil.mic, ProfileMicConfig)
        assert isinstance(perfil.speaker, ProfileSpeakerConfig)
        assert isinstance(perfil.mode, ProfileModeConfig)
