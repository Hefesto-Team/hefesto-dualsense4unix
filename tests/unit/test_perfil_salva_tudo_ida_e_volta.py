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

# GUARDA-GI-REAL-01: antes de qualquer `import gi`, e no lugar do
# `pytest.importorskip("gi")` — que ACEITA o stub plantado por outro arquivo.
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

# ---------------------------------------------------------------------------
# A PONTE COM O PORTÃO DE COBERTURA — dicionário LITERAL, lido por AST
# ---------------------------------------------------------------------------

#: ``campo de Profile`` -> ``a superfície da janela que o escreve``.
#:
#: Este dicionário é lido por ``ast.literal_eval`` pelo portão de cobertura
#: (``test_perfil_salva_tudo_cobertura_das_secoes.py``). Ele NÃO pode virar
#: uma compreensão, uma chamada ou um ``dict()`` — tem de continuar sendo um
#: literal, senão o portão perde a única fonte que não exige GTK para ser lida.
#:
#: Quem acrescentar um campo a ``Profile`` acrescenta a entrada aqui E o caso
#: em ``_GESTOS`` abaixo. O portão reprova sozinho quem esquecer.
SECOES_COBERTAS: dict[str, str] = {
    "name": "rodapé — o nome digitado no diálogo do Salvar Perfil",
    "match": "rodapé — _regra_do_save (disco > origem do rascunho > MatchManual)",
    "priority": "rodapé — _prioridade_do_save (quem já existe herda a do disco)",
    "triggers": "aba Gatilhos — TriggersActionsMixin._persist_params_to_draft",
    "leds": "aba Lightbar — LightbarActionsMixin._persist_leds_update",
    "rumble": "aba Rumble — RumbleActionsMixin._set_policy",
    "key_bindings": "aba Teclado — InputActionsMixin._persist_key_bindings_to_draft",
    "mouse": "aba Mouse — MouseActionsMixin.on_mouse_speed_changed",
    "mic": "NENHUMA — não há superfície que escreva ProfileMicConfig no rascunho",
    "speaker": "card do controle — draft_config.registrar_alto_falante_no_rascunho",
    "mode": "abas Início/Emulação — home_actions.registrar_modo_no_rascunho",
    "suppress_desktop_emulation": (
        "aba Emulação — emulation_actions.registrar_modo_jogo_no_rascunho"
    ),
    "controllers": "aba Lightbar com um controle no seletor — _persist_leds_update",
}

#: MAC de teste — máscara da casa (octetos 4 e 5 zerados), como o portão de
#: anonimato exige. Não é o controle dela.
UNIQ_DE_TESTE = "aabbcc000002"


# ---------------------------------------------------------------------------
# Aparelhagem
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _sync_run_in_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """``ipc_bridge.run_in_thread`` síncrono — sem loop GTK não há callback.

    Mesma aparelhagem de ``test_gravacao_de_perfil_passa_pelo_funil.py``:
    worker e callback na mesma thread preservam a semântica observável do
    ``PERF-FOOTER-ASYNC-IO-01``.
    """

    def _sync(fn: Any, on_success: Any, on_failure: Any = None) -> None:
        try:
            resultado = fn()
        except Exception as exc:  # espelha o run_in_thread real
            if on_failure is not None:
                on_failure(exc)
            return
        on_success(resultado)

    monkeypatch.setattr(footer_actions.ipc_bridge, "run_in_thread", _sync)


@pytest.fixture
def disco(tmp_path: Path) -> Path:
    """O diretório de perfis DE VERDADE — provado dentro do ``tmp_path``.

    Não monkeypatcha nada: o ``_hefesto_fake_env`` do conftest já aponta o
    ``XDG_CONFIG_HOME`` para dentro do ``tmp_path`` deste teste, e
    ``xdg_paths.profiles_dir`` resolve por ele a cada chamada. O ``assert``
    aqui é o instrumento conferindo a própria régua: se um dia essa fixture
    parar de isolar, o teste REPROVA antes de escrever um byte no
    ``~/.config`` dela, em vez de deixar o canário do conftest descobrir
    depois de o estrago estar feito.
    """
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
            # Guardas de refresh — todas BAIXAS: o gesto é dela, não eco.
            self._refresh_guard = False
            self._rumble_guard_refresh = False
            self._mouse_guard_refresh = False
            self._triggers_guard_refresh = False
            self._trigger_preset_applying = False
            # Seletor de alvo do banner (PERFIL-04) e mapa de conectados (R-14).
            self._edit_target_uniq = alvo
            self._target_uniq_by_index = dict(conectados or {})
            # Widgets que os handlers de gatilho leem.
            self._trigger_mode: dict[str, Any] = {}
            self._trigger_param_widgets: dict[str, dict[str, Any]] = {}
            self._trigger_live_preview_timer: dict[str, int] = {"left": 0, "right": 0}
            self._key_bindings_store: Any = None
            self._escolha_pendente: Any = None
            self._rumble_policy: str | None = None

        # --- widgets: não há glade neste dublê ---
        def _get(self, widget_id: str) -> Any:
            return None

        # --- toasts: as quatro abas usam nomes diferentes ---
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

        # --- efeitos colaterais que exigiriam daemon/glade ---
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
    """O perfil que ela tem em disco quando abre a janela.

    Tudo aqui é ESCOLHA, e cada uma tem um porquê:

    - ``match`` com regra de verdade e prioridade alta: é o perfil de um jogo,
      não um catch-all — é nele que ela reclama de perder configuração;
    - ``auto_player_colors=False``: o D4 da aba Lightbar (COR-04) desliga o
      automático quando a cor é editada em "Todos" sem alvo conhecido, e um
      teste de ida-e-volta de COR não pode medir o D4 de carona. O toggle tem
      caso próprio (``_gesto_leds_auto``);
    - as seções opcionais VAZIAS (``mouse``/``mic``/``speaker``/``mode``): a
      pergunta desta suíte é se o gesto da aba as CRIA, e um perfil que já as
      trouxesse responderia por herança em vez de pelo gesto.
    """
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
    """O gesto dela: botão VERDE "Aplicar", com o daemon respondendo tudo ok.

    O daemon não está no laço: o que se mede aqui é o efeito do "Aplicar"
    sobre o RASCUNHO — o HARM-05 mostrou que ele mexe (baixa o ``dirty`` do
    mouse), e mexer no rascunho é mexer no que o "Salvar Perfil" seguinte vai
    gravar.
    """
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
    """Dublê do rótulo "vai mudar para:" da aba Início — só o que ele expõe.

    O-SALVAR-TAMBEM-APLICA-01 (11/08/2026). Sem ele, "a pendência foi limpa" só
    se mede no MODELO (``_escolha_pendente``), e o pedido dela é sobre a TELA:
    *"a linha vai mudar para: tem de apagar"*. As duas coisas podem divergir —
    ``render_pendente`` sai cedo quando não há rótulo montado —, e um teste que
    olhasse só o modelo passaria com a linha acesa na cara dela.
    """

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
    """Nenhum IPC de leitura sai desta bancada — nem para o daemon dela.

    ``_ha_jogo_aberto_agora`` lê o estado vivo e ENGOLE o erro, mantendo
    "nenhum jogo aberto" — o caminho sem diálogo de relançamento, que é o que
    estes casos medem. A armadilha existe para o teste não depender do que está
    ligado na máquina de quem o roda (o socket já é isolado pelo modo fake do
    conftest; isto é a segunda rede, e é a que documenta a intenção).
    """

    def _explode(*_a: Any, **_kw: Any) -> Any:
        raise RuntimeError("daemon ausente nesta bancada")

    monkeypatch.setattr(footer_actions.ipc_bridge, "_run_call", _explode)


def _armadilha_de_apply_mode(
    monkeypatch: pytest.MonkeyPatch, *, desfecho: str = "sucesso"
) -> list[tuple[str, str | None]]:
    """Registra CADA ``apply_mode`` e devolve a lista — a régua da transição.

    ``desfecho`` escolhe o que o daemon responde: ``"sucesso"`` chama o
    ``on_done``, ``"falha"`` chama o ``on_fail``, e ``"mudo"`` não chama nada
    (o caso em que o IPC ainda está em voo).
    """
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


# ---------------------------------------------------------------------------
# OS GESTOS — um por seção do perfil, no ponto mais próximo do dedo dela
# ---------------------------------------------------------------------------
#
# Cada gesto abaixo entra pelo MESMO ponto que o handler da aba usa. Onde o
# handler lê widget demais para caber num dublê honesto, entra-se pela função
# que ele chama na linha seguinte — e o nome dela está no `SECOES_COBERTAS`
# acima, para quem for conferir saber exatamente onde olhar.


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
    """Aba Rumble: clicar em "Economia" (a política persiste no perfil).

    O IPC vivo é dublado: ``_set_policy`` fala com o daemon na mesma função em
    que escreve o rascunho, e o que se mede aqui é o disco. O dublê responde
    ACEITO — recusa do daemon é outra história, com testemunha própria.
    """
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
    assert perfil.key_bindings == {"triangle": ["KEY_C"]}, (
        f"os bindings no arquivo são {perfil.key_bindings!r} — o teclado que "
        "ela montou não sobreviveu ao salvar"
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
    """Aba/seção do MICROFONE: desligar "o botão do controle muda o mic do PC".

    NÃO HÁ GESTO. Procurado em 09/08/2026 com
    ``grep -rn button_toggles_system src/``: as ÚNICAS escritas de
    ``MicDraft`` no projeto inteiro estão em ``DraftConfig.from_profile``
    (leitura do disco) — nenhuma superfície da janela escreve a seção. O
    campo existe no esquema, no rascunho, no ``to_profile``, no
    ``to_ipc_dict`` e no ``ipc_draft_applier``; só não existe onde ela
    poderia tocá-lo.

    O gesto simulado aqui é o que a janela FARIA se tivesse a superfície —
    escrever o ``MicDraft`` com ``dirty=True``, exatamente como o
    ``MouseDraft`` faz. Enquanto não houver handler, este caso mede a metade
    de BAIXO (rascunho -> disco) — a de cima é medida, e HOJE REPROVA, no
    portão ao lado: ``test_perfil_salva_tudo_cobertura_das_secoes.py``,
    ``TestTodaSecaoTemEscritorNaJanela``, com ``xfail(strict=True)`` e o
    endereço da lacuna por extenso.

    Este caso ficar VERDE não quer dizer que o microfone está salvo: quer dizer
    que, no dia em que a superfície nascer, o que ela escrever chega ao disco.
    """
    from hefesto_dualsense4unix.app.draft_config import MicDraft

    janela.draft = janela.draft.model_copy(
        update={
            "mic": MicDraft(button_toggles_system=False, dirty=True, in_profile=True)
        }
    )


def _confere_mic(perfil: Profile) -> None:
    assert perfil.mic is not None, (
        "a seção `mic` NÃO existe no arquivo — o comportamento do botão de "
        "microfone não foi salvo no perfil"
    )
    assert perfil.mic.button_toggles_system is False, (
        "o `button_toggles_system` do arquivo é "
        f"{perfil.mic.button_toggles_system!r} — ela desligou"
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
    """Abas Início/Emulação: "Jogar pelo Hefesto" com a máscara Xbox.

    Entra pelo escritor ÚNICO da casa (``registrar_modo_no_rascunho``), que é
    o que o "Aplicar" chama no callback de sucesso da transição de modo — o
    clique no seletor só MARCA a escolha desde a AGORA-E-DEPOIS-01.
    """
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
    """Aba Lightbar COM um controle selecionado no seletor do banner.

    É o "configurei pro 1-BT, fica salvo pra ele dentro do meu perfil" da
    PERFIL-04 — e é o caso do BLUETOOTH que ela nomeou no pedido: o override
    é chaveado pelo MAC, o mesmo entre USB e BT.
    """
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


#: ``campo`` -> ``(gesto, conferência)``. As chaves TÊM de bater com
#: ``SECOES_COBERTAS`` — há teste logo abaixo que cobra isso, para o portão de
#: cobertura não poder ser enganado por um literal desatualizado.
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

#: Seções cujo ida-e-volta está QUEBRADO hoje, com o motivo por extenso e o
#: endereço de onde o dado se perde. ``xfail(strict=True)``: no dia em que a
#: cura entrar, o caso passa e o pytest REPROVA o xfail que sobrou — a lápide
#: não pode envelhecer calada, e quem entrega a cura apaga a entrada daqui.
#:
#: ESTÁ VAZIO, e isso é MEDIÇÃO de 09/08/2026, não descuido: nas TREZE seções, a
#: metade de baixo do caminho (rascunho -> arquivo) está inteira hoje. O que
#: falta é a metade de CIMA numa delas — ``mic`` não tem superfície que a
#: escreva —, e essa lacuna é medida e marcada no portão ao lado
#: (``test_perfil_salva_tudo_cobertura_das_secoes.py``, ``_SEM_ESCRITOR_HOJE``).
#: Separar as duas metades é o que permite dizer, de uma seção quebrada, se
#: falta a superfície ou se falta a persistência.
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


# ---------------------------------------------------------------------------
# A ida e volta
# ---------------------------------------------------------------------------


class TestIdaEVolta:
    """Uma seção do perfil por caso, e o caminho REAL entre a aba e o arquivo."""

    @pytest.mark.parametrize("campo", _casos())
    def test_o_gesto_da_aba_chega_ao_arquivo(
        self, campo: str, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Gesto na aba -> "Salvar Perfil" -> disco -> releitura.

        MORDIDA (onde arrancar para ver reprovar): tire do
        ``DraftConfig.to_profile`` (``app/draft_config.py``) a linha que emite
        a seção deste caso — por exemplo trocar ``mode=self.source_mode if ...``
        por ``mode=None`` — e o caso correspondente fica vermelho com a frase
        que descreve a perda pelos olhos dela. Medido: com ``mode=None``
        forçado, só o caso ``mode`` reprova; os demais seguem verdes, que é o
        que prova que os casos medem coisas DIFERENTES.

        A releitura é de DISCO (``load_profile``), nunca do objeto em memória:
        o ``save_profile`` omite seções ``None`` do JSON de propósito
        (compatibilidade de downgrade), e um teste que olhasse o objeto não
        veria uma seção perdida na serialização.
        """
        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)

        _gesto_de(campo, janela, monkeypatch)
        _salvar_pelo_rodape(janela, perfil.name)

        _GESTOS[campo][1](_relido(perfil.name))

    @pytest.mark.parametrize("campo", _casos())
    def test_o_gesto_sobrevive_ao_aplicar_antes_de_salvar(
        self, campo: str, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ordem que ela usa: mexe, clica no VERDE, e SÓ ENTÃO salva.

        É a frase dela ao pé da letra — *"ao clicarmos em salvar perfil e
        aplicar (botão verde) tudo fique salvo no perfil ativo"*. O "Aplicar"
        NÃO grava disco, mas mexe no rascunho (o HARM-05 é exatamente isso: o
        rodapé baixa o ``dirty`` do mouse no callback de sucesso), e mexer no
        rascunho é mexer no que o "Salvar Perfil" seguinte grava.

        MORDIDA: troque, em ``footer_actions._clear_mouse_dirty``, o
        ``{"dirty": False, "in_profile": True}`` por ``{"dirty": False}`` — o
        caso ``mouse`` deste teste fica vermelho ("a seção `mouse` NÃO existe
        no arquivo") e o do teste irmão acima continua verde, porque lá não
        houve Aplicar. É a diferença entre os dois testes, escrita como
        medição.
        """
        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)

        _gesto_de(campo, janela, monkeypatch)
        _aplicar_pelo_rodape(janela, monkeypatch)
        _salvar_pelo_rodape(janela, perfil.name)

        _GESTOS[campo][1](_relido(perfil.name))


class TestTudoDeUmaVezSo:
    """Todas as abas mexidas na MESMA sessão, e um "Salvar Perfil" só.

    É o cenário LITERAL da queixa — *"em todas as abas fiz alterações e salvei
    o perfil, e essas configurações de outras abas não ficam salvas"*. Vale
    além da soma dos casos acima: os defeitos desta família são de FRONTEIRA
    (uma aba reemite a fotografia velha por cima do que a outra escreveu), e
    nenhum caso isolado os enxerga.
    """

    def test_uma_sessao_inteira_de_ajustes_sobrevive_a_um_unico_salvar(
        self, disco: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sete abas, um clique em Salvar, e o arquivo tem as sete coisas.

        MORDIDA: qualquer regressão que faça UMA seção ser reemitida do
        snapshot do boot (o defeito do ``BUG-FOOTER-SAVE-DROPS-SECTIONS-01``)
        derruba este teste com o nome da seção perdida na mensagem.
        """
        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)

        # `controllers` por último, e a ordem é medição, não estética: o gesto
        # dele DEIXA um controle selecionado no seletor do banner, e toda edição
        # de LED posterior cairia no override em vez do global — que é o
        # comportamento certo do produto e o errado para esta bancada.
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
        """O mesmo cenário, mas a aba Início entra pelo GESTO — não pelo escritor.

        O PEDIDO DELA, 10/08/2026, literal:

            *"eu ir de uma aba pra outra depois de alterar todas as anteriores
            mas eu clicar em salvar somente na última. ele vai salvar na última
            aba todas as informações passadas."*

        O teste acima faz a Início entrar por ``registrar_modo_no_rascunho``,
        que é o escritor — e por isso ele nunca viu o buraco. O dedo dela não
        chama o escritor: clicar no seletor de modo só MARCA a escolha em
        ``_escolha_pendente`` (AGORA-E-DEPOIS-01), e até 10/08/2026 quem levava
        a marca ao rascunho era **só** o callback do botão VERDE. Sem o verde,
        este Salvar gravava ``mode: null`` em cima do que ela acabara de
        escolher — a Início era a ÚNICA das oito abas que não contribuía.

        MORDIDA: apague a chamada a ``recolher_escolha_pendente_no_rascunho``
        da primeira linha de ``footer_actions._persist_profile_async`` e este
        teste reprova com ``mode:`` na lista de seções perdidas, enquanto o
        teste acima — que entra pelo escritor — continua VERDE.
        """
        from hefesto_dualsense4unix.app.actions import home_actions

        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)
        # O-SALVAR-TAMBEM-APLICA-01 (11/08/2026): este Salvar passou a disparar
        # a transição de modo, e uma bancada de DISCO não pode falar com daemon
        # nenhum. As duas armadilhas mantêm o teste hermético e medindo o que
        # ele sempre mediu — o arquivo. Quem mede a transição são os casos
        # próprios, em `TestOSalvarSozinho...`.
        _sem_daemon(monkeypatch)
        _armadilha_de_apply_mode(monkeypatch)

        # Mesma ordem e mesma razão do teste acima; `mode` sai da lista porque
        # aqui ele entra pela porta dela, logo abaixo.
        ordem = [c for c in SECOES_COBERTAS if c not in ("controllers", "mode")]
        for campo in [*ordem, "controllers"]:
            if campo in _QUEBRADAS_HOJE:
                continue
            _gesto_de(campo, janela, monkeypatch)

        # A aba Início, pelo dedo dela: dois cliques em seletor, nada mais.
        home_actions.marcar_escolha(janela, "modo", "gamepad")
        home_actions.marcar_escolha(janela, "mascara", "xbox")

        # E o único clique em "Salvar Perfil", na ÚLTIMA aba.
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

        # O daemon não entra no laço: `_ha_jogo_aberto_agora` lê o estado vivo
        # por IPC e engole o erro — sem daemon ele mantém "nenhum jogo aberto",
        # que é o caminho sem diálogo de relançamento.
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

        # O gesto dela na aba Início: escolher o modo e a máscara.
        home_actions.marcar_escolha(janela, "modo", "gamepad")
        home_actions.marcar_escolha(janela, "mascara", "xbox")
        assert janela._escolha_pendente, "a escolha dela não ficou marcada"

        # O botão VERDE do rodapé.
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
        """Ela marca o modo na Início e salva **SEM** tocar no botão verde.

        (O ``sem`` do nome é minúsculo porque o ``N802`` do ruff reprova nome de
        função com maiúscula — a ênfase mora aqui.)

        Mede as QUATRO metades do pedido dela, e cada uma tem uma mordida
        própria, medidas em 11/08/2026 uma a uma:

        1. o arquivo tem o modo — MORDIDA: apague a chamada a
           ``recolher_escolha_pendente_no_rascunho`` da primeira linha de
           ``footer_actions._persist_profile_async``;
        2. o daemon recebeu o ``apply_mode`` — MORDIDA: apague o
           ``depois_na_janela=depois`` do ``_gravar_perfil_async`` no mesmo
           método, e o arquivo continua certo enquanto a máquina fica para trás
           (que é o defeito exato que ela mandou consertar);
        3. a linha "vai mudar para:" apagou — MORDIDA: troque o
           ``_esquecer_a_pendencia(self)`` do ``_aplicou`` por um
           ``self._escolha_pendente = None`` cru, e o modelo fica limpo com a
           linha ACESA na tela;
        4. o toast diz a verdade nova — MORDIDA: devolva o texto antigo
           ("próxima abertura") ao ``_texto_do_perfil_salvo``.
        """
        from hefesto_dualsense4unix.app.actions import home_actions

        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)
        janela._home_pendente_label = _LinhaDoPendente()
        _sem_daemon(monkeypatch)
        aplicados = _armadilha_de_apply_mode(monkeypatch)

        # O gesto dela na aba Início — e SÓ ele. Nenhum clique no verde.
        home_actions.marcar_escolha(janela, "modo", "gamepad")
        home_actions.marcar_escolha(janela, "mascara", "xbox")
        assert janela._home_pendente_label.visivel, (
            "a linha 'vai mudar para:' nem chegou a acender — o teste mediria "
            "o apagar de uma linha que nunca esteve na tela"
        )

        _salvar_pelo_rodape(janela, perfil.name)

        # 1. o ARQUIVO.
        _confere_mode(_relido(perfil.name))

        # 2. o DAEMON. A escolha dela viaja inteira: modo E máscara, porque a
        # máscara foi escolha explícita dela (o clique no seletor).
        assert aplicados == [("gamepad", "xbox")], (
            "o Salvar não pediu a transição de modo ao daemon — o arquivo "
            f"mudou e a máquina ficou para trás: {aplicados!r}"
        )

        # 3. a TELA. As duas metades: o modelo e o rótulo.
        assert janela._escolha_pendente is None, (
            "a pendência sobreviveu a um Salvar que APLICOU: "
            f"{janela._escolha_pendente!r} — a janela promete uma mudança que "
            "já aconteceu"
        )
        assert not janela._home_pendente_label.visivel, (
            "a linha 'vai mudar para:' continua acesa depois de o daemon "
            f"confirmar a mudança (texto: {janela._home_pendente_label.texto!r})"
        )

        # 4. o TOAST. A última palavra é a que ela lê, e ela não pode mandar
        # clicar em nada nem falar de "próxima abertura": já está valendo.
        ultimo = janela.toasts[-1]
        assert "Jogar pelo Hefesto" in ultimo and "já está valendo" in ultimo, (
            f"o último toast do Salvar não diz que o modo já vale: {ultimo!r}"
        )
        # E NENHUM dos toasts da sequência pode ter sobrado do desenho antigo.
        # A varredura é sobre todos, e não só sobre o último, porque o texto
        # velho morava no PRIMEIRO (`_texto_do_perfil_salvo`, dito no instante
        # em que o arquivo fica pronto) — uma asserção só sobre a última frase
        # deixaria a mentira passar no meio do caminho.
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
        # O arquivo NÃO se desfaz: desfazer seria apagar a escolha dela por
        # causa de um engasgo de IPC.
        _confere_mode(_relido(perfil.name))
        # E a tela continua dizendo o que é verdade: o daemon não chegou lá.
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
        """AUTO-01.3 no caminho novo: quem não escolheu não manda.

        Trocar só o modo não é escolher máscara. O passo tem de sair SEM o
        campo, e o daemon preserva a que já está configurada — o MESMO contrato
        que ``test_a_inicio_sem_mascara_escolhida_nao_impoe_mascara_nenhuma``
        tranca para o botão verde.

        Aqui a tentação é maior que lá, e é por isso que este caso existe: o
        recolhimento devolve ``{"modo": "gamepad", "mascara": "dualsense"}`` —
        com a máscara VINDA DO DAEMON, porque o esquema não aceita ``kind``
        gamepad sem ela —, e reaproveitar esse dicionário inteiro no IPC parece
        a coisa óbvia a fazer. Seria a GUI decidindo máscara por causa de um
        payload que ela apenas leu: o "segundo dono do valor" da AUTO-01.3,
        entrando pela porta nova.

        MORDIDA: em ``_persist_profile_async``, troque a máscara explícita
        (``escolhida``) por ``recolhido.get("mascara")`` e este teste reprova
        com ``flavor='dualsense'`` na chamada.
        """
        from hefesto_dualsense4unix.app.actions import home_actions

        perfil = _semear(_perfil_de_partida())
        janela = _janela(DraftConfig.from_profile(perfil), perfil.name)
        # O que a aba Início leu do daemon no último tique.
        janela._modo_vigente_do_daemon = "desktop"
        janela._mascara_vigente_do_daemon = "dualsense"
        _sem_daemon(monkeypatch)
        aplicados = _armadilha_de_apply_mode(monkeypatch)

        # Ela escolhe o MODO, e só ele.
        home_actions.marcar_escolha(janela, "modo", "gamepad")

        _salvar_pelo_rodape(janela, perfil.name)

        assert aplicados == [("gamepad", None)], (
            "o Salvar impôs uma máscara que ela não escolheu — ecoar o vigente "
            f"do daemon é o segundo dono do valor: {aplicados!r}"
        )
        # E o ARQUIVO continua guardando a máscara vigente, que é outra
        # pergunta: o esquema exige uma, e o recolhimento a herda do daemon.
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
        # Daemon offline: a aba Início nunca renderizou, logo não há vigente.
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
        """``SECOES_COBERTAS`` é lido por AST — ele não pode mentir.

        MORDIDA: acrescente uma chave a ``SECOES_COBERTAS`` sem o caso
        correspondente em ``_GESTOS`` e este teste reprova. Sem ele, o portão
        de cobertura ao lado poderia ser satisfeito com um literal decorativo,
        e a regressão passaria.
        """
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
    """A régua é conferida antes de qualquer veredito dela ser citado.

    "O instrumento mente mais que o produto" é a lição mais cara desta casa
    (três medições falsas num dia, 07/08). Estes dois casos são a contagem
    independente: se a aparelhagem deixasse de escrever no disco, ou passasse
    a ler o objeto em memória em vez do arquivo, TODOS os casos acima ficariam
    verdes sem medir nada.
    """

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
        """A prova de que nenhuma conferência passa de graça.

        Salva-se o perfil SEM fazer gesto nenhum e cobra-se que cada
        conferência reprove. É a mordida de todos os casos de uma vez, feita
        dentro da suíte: se uma conferência passasse aqui, ela estaria medindo
        o valor que o perfil já tinha — cobertura falsa, que é pior que
        cobertura ausente.

        TRÊS EXCEÇÕES, e elas são o contrato, não folga:

        - ``name``, ``match`` e ``priority`` **não têm gesto de aba**. Eles vêm
          do DISCO, e o que os testes deles medem é o contrário: que salvar
          NÃO os mexa (SALVAR-NAO-REBAIXA-01/02, REGRA-NAO-SE-PERDE-01/02).
          Passar sem gesto é exatamente o que se quer deles.

        MEDIDO em 09/08/2026: 10 conferências reprovam sem o gesto, 3 passam —
        as três de cima, e só elas.
        """
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
        """A mordida provada DENTRO da suíte, sem arrancar produção à mão.

        Aqui a cura é arrancada em memória: ``to_profile`` passa a devolver um
        perfil SEM a seção ``mode``, exatamente como fazia antes da
        PERFIL-SALVA-TUDO-01. A conferência de ``mode`` tem de reprovar — e se
        não reprovar, é a régua que está quebrada, não o produto que está bom.
        """
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
    """Touch e giroscópio: a lacuna é de PRODUTO, e fica escrita aqui.

    Ela citou os dois no pedido (*"todas as features em cada aba, touch,
    giroscopio, speaker, mic, gatilho, lightbar"*). Speaker, mic, gatilho e
    lightbar têm campo no esquema e caso acima. Touch e giroscópio NÃO TÊM
    CAMPO NENHUM — não há o que salvar, e por isso não há ida-e-volta possível.

    Este teste não pede que passem a existir: ele impede que a AUSÊNCIA seja
    esquecida. No dia em que alguém acrescentar ``touchpad`` ou ``gyro`` ao
    ``Profile``, ele reprova pedindo o caso de ida-e-volta — junto com o
    portão de cobertura ao lado.
    """

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
    """As seções opcionais continuam sendo as classes que os casos conferem.

    Sem isto, uma troca de tipo (``ProfileSpeakerConfig`` virando dict cru, por
    exemplo) passaria despercebida porque as conferências usam ``getattr``.
    """

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
