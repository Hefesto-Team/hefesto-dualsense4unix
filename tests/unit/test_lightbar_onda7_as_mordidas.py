"""LIGHTBAR — COR DE CADA UM-01 (Onda 7): os seis casos que a aba não tinha."""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("lightbar onda7 as mordidas")

from typing import Any

import pytest

gi = pytest.importorskip("gi")

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app import draft_config as draft_mod
from hefesto_dualsense4unix.app.actions import lightbar_actions, triggers_actions
from hefesto_dualsense4unix.app.actions.lightbar_actions import LightbarActionsMixin
from hefesto_dualsense4unix.app.actions.triggers_actions import TriggersActionsMixin
from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

UNIQ_1 = "aa:bb:cc:00:00:01"
UNIQ_2 = "aa:bb:cc:00:00:02"

ROXO = (129, 61, 156)

P2 = (False, True, False, True, False)


class _Rotulo:
    """Rótulo GTK reduzido ao que a aba usa: texto, mostrar e esconder."""

    def __init__(self, texto: str = "") -> None:
        self.texto = texto
        self.visivel = True

    def set_text(self, valor: str) -> None:
        self.texto = valor

    def get_text(self) -> str:
        return self.texto

    def show(self) -> None:
        self.visivel = True

    def hide(self) -> None:
        self.visivel = False


class _Caixa:
    def __init__(self) -> None:
        self.active = False

    def connect(self, *_a: Any, **_kw: Any) -> None:
        return None

    def get_active(self) -> bool:
        return self.active

    def set_active(self, valor: bool) -> None:
        self.active = bool(valor)


class _BotaoDeCor:
    def __init__(self, rgb: tuple[int, int, int] = ROXO) -> None:
        self._rgb = rgb

    def get_rgba(self) -> Any:
        class _RGBA:
            red = self._rgb[0] / 255
            green = self._rgb[1] / 255
            blue = self._rgb[2] / 255

        return _RGBA()

    def set_rgba(self, _rgba: Any) -> None:
        return None


def _aceitou(uniq: str | None) -> dict[str, Any]:
    """Corpo de um ``led.set``/``led.player_set`` que ESCREVEU em ``uniq``."""
    return {
        "status": "ok",
        "aplicado_em": [uniq] if uniq else [],
        "guardado_em": [],
    }


class _HostLightbar(LightbarActionsMixin):
    """Host mínimo da aba Lightbar — o molde de ``test_lightbar_todos_por_mac_r14``."""

    def __init__(
        self,
        draft: draft_mod.DraftConfig,
        *,
        conectados: dict[int, str | None] | None = None,
        alvo: str | None = None,
        com_alvo: bool = True,
        slot: int | None = None,
        rotulo_do_alvo: str | None = None,
    ) -> None:
        self.draft = draft
        if com_alvo:
            self._edit_target_uniq = alvo
        if rotulo_do_alvo is not None:
            self._edit_target_label = rotulo_do_alvo
        if slot is not None:
            self._edit_target_slot = slot
        if conectados is not None:
            self._target_uniq_by_index = conectados
        self._widgets: dict[str, Any] = {
            "auto_player_colors_check": _Caixa(),
            "player_leds_estado": _Rotulo("Desenho que mandamos: lendo o perfil…"),
            "lightbar_estado_no_controle": _Rotulo(),
            "lightbar_color_button": _BotaoDeCor(),
        }
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)

    @property
    def rotulo_do_desenho(self) -> _Rotulo:
        return self._widgets["player_leds_estado"]

    @property
    def rotulo_da_barra(self) -> _Rotulo:
        return self._widgets["lightbar_estado_no_controle"]


class _HostSoGatilhos(TriggersActionsMixin):
    """Host com os Gatilhos e **sem** o mixin da Lightbar montado (L2)."""

    def __init__(self) -> None:
        self._widgets: dict[str, Any] = {}
        self._toasts: list[tuple[str, bool, str | None]] = []
        self._trigger_mode: dict[str, Any] = {}

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _rebuild_params(self, _side: str, _modo: str) -> None:
        return None

    def _toast_trigger(
        self,
        side: str,
        preset_id: str,
        ok: bool,
        *,
        motivo: str | None = None,
        spec: Any = None,
        corpo: dict[str, Any] | None = None,
    ) -> None:
        self._toasts.append((side, ok, motivo))

    def _cancelar_live_preview(self, _side: str) -> None:
        return None

    def _adiantar_live_preview(self, _side: str) -> None:
        return None


def _perfil(auto: bool = True) -> Profile:
    return Profile(
        name="vitoria",
        match=MatchAny(),
        priority=5,
        leds=LedsConfig(
            lightbar=ROXO,
            player_leds=[False, False, False, False, False],
            lightbar_brightness=1.0,
            auto_player_colors=auto,
        ),
    )


def _draft(auto: bool = True) -> draft_mod.DraftConfig:
    return draft_mod.DraftConfig.from_profile(_perfil(auto))


def test_mesa_desconhecida_a_cor_recusa_e_a_paleta_sobrevive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L1 — o caso em que um clique de cor apagava a identidade de todo mundo.

    O estado: a fita do cabeçalho ainda diz "Controle 2" (ela viu isso na tela
    um segundo atrás), mas ``_target_uniq_by_index`` está vazio — a janela NÃO
    sabe quem está na mesa. Era exatamente aqui que o ramo degradado disparava:
    ``_d4_disable_auto_for_single_color`` gravava ``auto_player_colors: False``
    no rascunho E no perfil dela, e esse flag governava a paleta, a numeração
    dos DualSense e a dos externos.

    **Com a cura arrancada** (o ``estado_alvo.desconhecido`` de
    ``_aplicar_cor_no_controle``) reprovam DUAS asserções: a escrita sai para a
    mesa e a paleta é desligada.
    """
    chamadas: list[Any] = []
    monkeypatch.setattr(
        lightbar_actions,
        "led_set_detalhado",
        lambda *a, **kw: chamadas.append((a, kw)) or _aceitou(kw.get("uniq")),
    )
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "apply_draft_detalhado",
        lambda *a, **kw: chamadas.append((a, kw)) or {"status": "ok"},
    )
    host = _HostLightbar(
        _draft(auto=True),
        conectados={},
        com_alvo=False,
        rotulo_do_alvo="Controle 2 (BT)",
    )

    assert host._aplicar_cor_no_controle() is False
    assert chamadas == [], "nenhum byte pode sair com a mesa desconhecida"
    assert host.draft.leds.auto_player_colors is True, (
        "a paleta automática dela sobreviveu ao clique"
    )
    assert host._toasts, "a recusa tem de chegar à tela"
    assert "Nada foi alterado" in host._toasts[-1]


def test_gatilhos_sem_o_mixin_da_lightbar_recusam_em_vez_de_escrever_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L2 — a regressão da ABAS-06 (25/07) não pode voltar por um refactor.

    ``_edit_uniq`` era propriedade PRIVADA da aba Lightbar, e os Gatilhos a
    liam por ``getattr(self, "_edit_uniq", lambda: None)()``. O default
    silencioso do ``getattr`` significava "escreva global" — então bastava o
    mixin da Lightbar sair da MRO para os Gatilhos passarem a escrever nos
    quatro controles sem uma palavra na tela.

    **Com a cura arrancada** (``alvo_de_edicao`` devolvendo o ``None`` do
    atributo legado em vez de ``DESCONHECIDO``) este teste reprova: o
    ``trigger.reset`` sai, sem ``uniq``, e ninguém é avisado.

    NOTA DATADA (25/08/2026) — POR QUE O ALVO DO ``monkeypatch`` MUDOU. Esta
    régua nasceu nesta mesma madrugada dublando ``triggers_actions.trigger_reset``.
    Horas depois, na mesma madrugada, a frente dos Gatilhos (ELO-MUDO-01/T3,
    ``41541a7``) trocou a chamada de ``_reset_trigger`` por
    ``trigger_reset_detalhado``, que devolve ``(ok, motivo, corpo)`` em vez de
    ``(ok, motivo)`` — porque *"aplicado" tem de vir de quem viu o byte*, e o
    corpo da resposta do daemon é quem sabe disso. O símbolo antigo deixou de
    existir neste módulo e o ``monkeypatch.setattr`` passou a levantar
    ``AttributeError``.

    **Quem estava errado era o TESTE, e isso foi conferido no produto antes de
    mexer aqui:** o ``if estado_alvo.desconhecido: ... return`` de
    ``triggers_actions._reset_trigger`` continua ANTES de qualquer IPC. A
    recusa da L2 está viva; o que fossilizou foi o nome da função dublada.
    """
    resets: list[Any] = []
    monkeypatch.setattr(
        triggers_actions,
        "trigger_reset_detalhado",
        lambda side, uniq=None: resets.append((side, uniq)) or (True, None, None),
    )
    host = _HostSoGatilhos()
    assert not hasattr(host, "_edit_uniq"), (
        "o cenário exige um host SEM o mixin da Lightbar"
    )

    host._reset_trigger("left")

    assert resets == [], "nenhum gatilho pode ser escrito às cegas"
    assert host._toasts, "a recusa tem de chegar à tela"
    _side, ok, motivo = host._toasts[-1]
    assert ok is False
    assert motivo and "Nada foi alterado" in motivo


def test_o_ultimo_override_limpo_viaja_como_secao_vazia() -> None:
    """L3 — o "Voltar ao automático" que não chegava ao daemon."""
    draft = _draft()
    com_override = draft.with_controller_leds(
        UNIQ_1, draft.leds.model_copy(update={"lightbar_rgb": (255, 0, 0)})
    )
    assert com_override.to_ipc_dict()["controllers"], "o override viaja"

    limpo = com_override.with_controller_fields_cleared(
        UNIQ_1, "leds", {"lightbar", "lightbar_brightness"}
    )
    secao = limpo.to_ipc_dict()["controllers"]
    assert secao == {}, (
        "a seção tem de viajar VAZIA — `None` faz o applier sair antes de "
        "chamar `reset_output_overrides`, e a cor antiga fica no controle"
    )

    assert _draft().to_ipc_dict()["controllers"] is None


def test_envio_recusado_o_rotulo_nao_afirma_o_desenho(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L4 — duas afirmações contraditórias, na mesma aba, do mesmo clique."""
    monkeypatch.setattr(
        lightbar_actions,
        "player_leds_set_detalhado",
        lambda *a, **kw: pytest.fail("nenhum envio pode sair com a mesa vazia"),
    )
    host = _HostLightbar(
        _draft(auto=False),
        conectados={},
        alvo=None,
    )
    antes = host.rotulo_do_desenho.texto

    host.on_player_leds_preset_p2(None)

    assert host._toasts, "o toast do resultado continua saindo"
    assert lightbar_actions._AVISO_SEM_DESTINATARIO in host._toasts[-1]
    assert "P2" not in host.rotulo_do_desenho.texto, (
        "o rótulo anunciava um desenho que o produto acabou de declarar que "
        "não conseguiu enviar"
    )
    assert host.rotulo_do_desenho.texto == antes, (
        "na recusa o rótulo MANTÉM o último desenho que de fato mandamos"
    )


def _state(**campos: Any) -> dict[str, Any]:
    entrada = {
        "index": 0,
        "connected": True,
        "transport": "bt",
        "uniq": UNIQ_1,
        "lightbar_rgb": [0, 0, 255],
        "lightbar_on": True,
        "lightbar_source": "sysfs",
        "lightbar_disputada": False,
    }
    entrada.update(campos)
    return {"native_mode": False, "controllers": [entrada]}


def test_fonte_desconhecida_o_rotulo_nao_nomeia_cor_nem_diz_aceso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L6 — a aba da barra era a única do produto que não lia a barra."""
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "daemon_state_full",
        lambda: _state(lightbar_source="desconhecida", lightbar_rgb=None),
    )
    host = _HostLightbar(_draft(), alvo=UNIQ_1, conectados={0: UNIQ_1})

    host._refresh_lightbar_from_draft()

    texto = host.rotulo_da_barra.texto
    assert texto == "Lightbar: cor desconhecida"
    assert host.rotulo_da_barra.visivel is True
    assert "aceso" not in texto.lower(), "não há canal de leitura para afirmar isso"
    for palavra in ("azul", "vermelho", "verde", "rosa"):
        assert palavra not in texto.lower(), "sem fonte conhecida não se nomeia cor"


def test_a_disputa_da_steam_aparece_na_aba_da_cor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L6 — a entrega que faltava da ESCRITOR-CRU-01."""
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        ROTULO_LIGHTBAR_SEGURADA,
    )

    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "daemon_state_full",
        lambda: _state(lightbar_disputada=True),
    )
    host = _HostLightbar(_draft(), alvo=UNIQ_1, conectados={0: UNIQ_1})

    host._refresh_lightbar_from_draft()

    assert host.rotulo_da_barra.texto == ROTULO_LIGHTBAR_SEGURADA
    assert host.rotulo_da_barra.visivel is True


def test_sem_aviso_a_dar_o_rotulo_da_barra_some(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L6 — um "está tudo normal" não vira linha de tela."""
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge, "daemon_state_full", lambda: _state()
    )
    host = _HostLightbar(_draft(), alvo=UNIQ_1, conectados={0: UNIQ_1})

    host._refresh_lightbar_from_draft()

    assert host.rotulo_da_barra.texto == ""
    assert host.rotulo_da_barra.visivel is False


def test_alvo_em_todos_nao_inventa_estado_de_barra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L6 — sem alvo por controle não há barra sobre a qual falar."""
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "daemon_state_full",
        lambda: _state(lightbar_disputada=True),
    )
    host = _HostLightbar(_draft(), alvo=None, conectados={0: UNIQ_1})

    host._refresh_lightbar_from_draft()

    assert host.rotulo_da_barra.texto == ""
    assert host.rotulo_da_barra.visivel is False


def test_daemon_mudo_nao_derruba_a_aba(monkeypatch: pytest.MonkeyPatch) -> None:
    """L6 — o Hefesto desligado deixa a aba SEM aviso, nunca sem aba."""

    def _explode() -> dict[str, Any]:
        raise OSError("daemon fora do ar")

    monkeypatch.setattr(
        lightbar_actions.ipc_bridge, "daemon_state_full", _explode
    )
    host = _HostLightbar(_draft(), alvo=UNIQ_1, conectados={0: UNIQ_1})

    host._refresh_lightbar_from_draft()

    assert host.rotulo_da_barra.texto == ""
    assert host.rotulo_da_barra.visivel is False


def test_a_previa_da_paleta_sobrevive_a_traducao_da_interface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L7 — o defeito de 17/07 ressuscitado por um idioma."""
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    monkeypatch.setattr(
        lightbar_actions.ipc_bridge, "daemon_state_full", lambda: _state()
    )
    host = _HostLightbar(
        _draft(auto=True),
        alvo=UNIQ_1,
        conectados={0: UNIQ_1},
        slot=2,
        rotulo_do_alvo="Controller 2 — BT",
    )

    host._refresh_lightbar_from_draft()

    assert host._current_rgb == player_slot_color(2)
    assert host._current_rgb != ROXO, "a prévia voltou a mostrar a cor manual"


@pytest.mark.parametrize("numero", [1, 2, 3, 4])
def test_cada_botao_de_desenho_sai_da_tabela_canonica(
    numero: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """L9 — o botão e a tabela deixam de ser duas cópias que nada amarra.

    Os quatro botões "Desenho do PN" traziam o padrão escrito à mão, enquanto
    ``core/led_control.player_led_pattern`` já é a tabela que o DAEMON usa para
    acender — e que o MESMO arquivo já lia em ``nome_do_desenho`` para BATIZAR
    o desenho. A aba nomeava por uma fonte e pintava por outra.

    **O ARRANQUE, e ele tem duas metades porque o defeito tinha duas.** Devolva
    o literal escrito à mão a um dos botões E troque o bit correspondente em
    ``_PLAYER_LED_PATTERNS`` — que é exatamente o estado de 24/08: duas cópias
    independentes. O botão reprova nomeando o número. Trocar o bit da tabela
    SOZINHO já não reprova nada, e isso é a cura funcionando: depois do L9 há
    uma fonte só, e uma fonte só não tem como divergir de si mesma.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    enviados: list[tuple[bool, ...]] = []
    monkeypatch.setattr(
        lightbar_actions,
        "player_leds_set_detalhado",
        lambda bits, uniq=None: enviados.append(tuple(bits)) or _aceitou(uniq),
    )
    host = _HostLightbar(_draft(auto=False), alvo=UNIQ_1, conectados={0: UNIQ_1})

    getattr(host, f"on_player_leds_preset_p{numero}")(None)

    assert enviados == [tuple(player_led_pattern(numero))], (
        f"o botão P{numero} pintou um desenho que a tabela canônica não "
        "produz — o daemon acenderia outra coisa"
    )


def test_a_fiação_alcança_os_desenhos_5_a_8(monkeypatch: pytest.MonkeyPatch) -> None:
    """L9 — a aba sabia NOMEAR o P5 e não sabia oferecê-lo.

    ``player_led_pattern`` cobre 1..8 (R-25) porque o espaço de numeração é
    único entre DualSense, externos e co-op (R-24): com um Pro Controller
    numerado antes, um DualSense cai legitimamente no slot 5. O glade continua
    com QUATRO botões — quantos aparecem é escolha dela (§8) — mas a fiação já
    alcança os oito, e é isso que torna as duas respostas baratas.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    enviados: list[tuple[bool, ...]] = []
    monkeypatch.setattr(
        lightbar_actions,
        "player_leds_set_detalhado",
        lambda bits, uniq=None: enviados.append(tuple(bits)) or _aceitou(uniq),
    )
    host = _HostLightbar(_draft(auto=False), alvo=UNIQ_1, conectados={0: UNIQ_1})

    for numero in (5, 6, 7, 8):
        host.aplicar_desenho_do_jogador(numero)

    assert enviados == [tuple(player_led_pattern(n)) for n in (5, 6, 7, 8)]
    assert len(set(enviados)) == 4, "os quatro têm de ser distinguíveis entre si"
