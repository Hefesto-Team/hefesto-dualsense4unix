"""APLICAR-VERDADE-01/E2 — a ponte parou de estreitar a verdade.

A sprint de 01/08 curou o RODAPÉ: quando uma seção do rascunho não entra, ele
diz "Aplicado, menos: luzes." em vez de anunciar sucesso. A aba Lightbar ficou
de fora, e por um motivo de uma linha só: ela não usa o ``call_async`` (que
entrega o dicionário do daemon) — usa ``ipc_bridge.apply_draft()``, que
devolvia ``bool``. Com um ``False`` na mão, as duas chamadas da aba diziam:

- "Não consegui aplicar a cor — o Hefesto pode estar desligado (ligue na aba
  Sistema)";
- "Falha (daemon offline?)".

Ou seja: mandavam procurar o problema no daemon quando o daemon estava VIVO e
foi a seção ``leds`` que caiu — palavra por palavra o defeito que a sprint
existiu para eliminar.

O que este arquivo morde, nas duas metades que o aceite exige (consertar só
uma troca uma mentira por outra):

1. daemon VIVO + ``failed={"leds": ...}`` -> a frase NOMEIA a seção e não fala
   em daemon desligado/offline nem manda para a aba Sistema;
2. daemon REALMENTE offline -> a frase continua sendo a de hoje, ao pé da
   letra, nos dois botões;
3. o vocabulário é EMPRESTADO do rodapé (``footer_actions._NOMES_DE_SECAO``),
   não copiado: mexer no dicionário lá muda a frase daqui.

Nota de portão: ``exigir_gi_real()`` vem antes de qualquer ``import gi`` de
propósito — este módulo PULA no CI headless (dívida declarada do job de GUI,
CI-GUI-PULAVA-CALADO-01) e morde na máquina de desenvolvimento. A metade que
mede a PONTE, e que não precisa de GTK, mora em ``tests/unit/test_ipc_bridge.py``
para ter rede também no CI.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("aplicar-verdade ponte lightbar")

from typing import Any

import gi
import pytest

# BUG-TEST-GDK-VERSION-PIN-01: pina Gdk/Gtk 3.0 ANTES de importar a GUI.
gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.actions import footer_actions, lightbar_actions
from hefesto_dualsense4unix.app.actions.lightbar_actions import (
    LightbarActionsMixin,
    frase_do_envio,
    mensagem_de_secao_fora,
)
from hefesto_dualsense4unix.app.textos_de_aplicacao import (
    GUARDADO,
    NADA_ACONTECEU,
    frase_do_desfecho,
)
from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

#: As frases de HOJE, que a segunda metade do aceite obriga a preservar ao pé
#: da letra quando o daemon está mesmo desligado.
FRASE_APLICAR_OFFLINE = (
    "Não consegui aplicar a cor — o Hefesto pode estar desligado "
    "(ligue na aba Sistema)"
)
FRASE_APAGAR_OFFLINE = "Falha (daemon offline?)"

#: Resposta de um daemon VIVO em que a seção de luzes não entrou. É o payload
#: exato que o handler monta hoje (`daemon/ipc_handlers.py`): `status` fixo em
#: "ok" por contrato, `applied` vazio e `failed` nomeando a seção.
RESPOSTA_LEDS_FORA: dict[str, Any] = {
    "status": "ok",
    "applied": [],
    "failed": {"leds": "hidraw: Permission denied"},
}


class _Host(LightbarActionsMixin):
    """Hospedeiro mínimo do mixin: draft + toast espião, sem display."""

    def __init__(self, draft: DraftConfig) -> None:
        self.draft = draft
        self._edit_target_uniq = None
        self._widgets: dict[str, Any] = {}
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)


def _host() -> _Host:
    """Host no caminho degradado COR-04: alvo "Todos" e nenhum MAC conhecido.

    ``auto_player_colors=False`` de propósito: com o automático LIGADO o D4
    dispara e prefixa o toast com "Cores automáticas desligadas...", e a
    palavra "desligadas" ali envenenaria a asserção que procura por "desligado"
    na frase do resultado.
    """
    perfil = Profile(
        name="vitoria",
        match=MatchAny(),
        priority=5,
        leds=LedsConfig(
            lightbar=(129, 61, 156),
            lightbar_brightness=1.0,
            auto_player_colors=False,
        ),
    )
    return _Host(DraftConfig.from_profile(perfil))


def _selar_daemon(
    monkeypatch: pytest.MonkeyPatch, resposta: Any, *, respondeu: bool = True
) -> None:
    """Sela a saída IPC: nenhum teste daqui toca no daemon real."""
    monkeypatch.setattr(
        lightbar_actions.ipc_bridge,
        "_safe_call",
        lambda *_a, **_kw: (respondeu, resposta),
    )


def _gdk_rgba_ok() -> bool:
    """A CI headless de release tem um Gdk parcial sem RGBA (o "Apagar"
    constrói um) — mesmo skip de ``test_lightbar_auto_colors``."""
    try:
        from gi.repository import Gdk

        return hasattr(Gdk, "RGBA")
    except Exception:
        return False


def _ultimo_toast(host: _Host) -> str:
    assert host._toasts, "a aba não disse nada — o toast do resultado sumiu"
    return host._toasts[-1]


# ---------------------------------------------------------------------------
# Metade 1 — daemon VIVO, seção fora: a frase nomeia a seção
# ---------------------------------------------------------------------------


def test_aplicar_com_leds_fora_nomeia_a_secao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Falha-sem: com o ``bool`` da ponte antiga esta frase era a de daemon
    desligado — a aba mandava procurar o Hefesto na aba Sistema com ele vivo."""
    host = _host()
    _selar_daemon(monkeypatch, RESPOSTA_LEDS_FORA)

    host.on_lightbar_apply(None)

    msg = _ultimo_toast(host)
    assert "luzes" in msg, (
        "a seção que caiu tem de aparecer NOMEADA: é a informação que o daemon "
        "manda desde a APLICAR-VERDADE-01 e que morria na ponte"
    )
    assert "desligado" not in msg
    assert "offline" not in msg.lower()
    assert "aba Sistema" not in msg, (
        "com o daemon vivo, mandar para a aba Sistema é mandar caçar o "
        "problema no lugar errado"
    )


@pytest.mark.skipif(not _gdk_rgba_ok(), reason="Gdk.RGBA ausente (CI headless)")
def test_apagar_com_leds_fora_nomeia_a_secao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O "Apagar" mente pelo mesmo motivo: é aplicar a cor preta pela ponte."""
    host = _host()
    _selar_daemon(monkeypatch, RESPOSTA_LEDS_FORA)

    host.on_lightbar_off(None)

    msg = _ultimo_toast(host)
    assert "luzes" in msg
    assert "offline" not in msg.lower()
    assert "desligado" not in msg


# ---------------------------------------------------------------------------
# Metade 2 — daemon REALMENTE offline: a frase de hoje, ao pé da letra
# ---------------------------------------------------------------------------


def test_aplicar_com_daemon_offline_continua_mandando_para_a_aba_sistema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cura não pode trocar uma mentira por outra: sem resposta nenhuma, a
    aba Sistema É o lugar certo para onde mandar."""
    host = _host()
    _selar_daemon(monkeypatch, None, respondeu=False)

    host.on_lightbar_apply(None)

    assert _ultimo_toast(host) == FRASE_APLICAR_OFFLINE


@pytest.mark.skipif(not _gdk_rgba_ok(), reason="Gdk.RGBA ausente (CI headless)")
def test_apagar_com_daemon_offline_continua_dizendo_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    host = _host()
    _selar_daemon(monkeypatch, None, respondeu=False)

    host.on_lightbar_off(None)

    assert _ultimo_toast(host) == FRASE_APAGAR_OFFLINE


def test_sucesso_continua_sendo_sucesso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resposta com a seção aplicada não vira aviso de falha (R-18 intacto)."""
    host = _host()
    _selar_daemon(monkeypatch, {"status": "ok", "applied": ["leds"]})

    host.on_lightbar_apply(None)

    msg = _ultimo_toast(host)
    # TELA-QUE-SO-AFIRMA-O-QUE-SABE-01: a frase do caminho feliz virou "Cor
    # ENVIADA ao controle" — o `ok` sempre significou "o report saiu". O que
    # este teste mede continua sendo o mesmo: sucesso não vira aviso de falha.
    assert "Cor enviada ao controle" in msg
    assert "não entrou" not in msg


# ---------------------------------------------------------------------------
# O vocabulário é EMPRESTADO do rodapé, não copiado (RADAR-01)
# ---------------------------------------------------------------------------


def test_a_frase_pega_os_nomes_das_secoes_no_rodape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dono único do vocabulário: mexer no dicionário do rodapé muda a frase
    daqui. Se a aba tivesse a própria cópia dos nomes, isto não mudaria nada —
    e as duas superfícies divergiriam com o tempo, que é o defeito medido pela
    RADAR-01."""
    monkeypatch.setitem(footer_actions._NOMES_DE_SECAO, "leds", "lanternas")

    msg = mensagem_de_secao_fora(RESPOSTA_LEDS_FORA)

    assert msg is not None and "lanternas" in msg


def test_secao_desconhecida_aparece_com_o_nome_cru() -> None:
    """Daemon mais novo que a janela: melhor um termo estranho do que omitir
    que algo ficou de fora (a mesma regra de ``_lista_de_secoes``)."""
    msg = mensagem_de_secao_fora(
        {"status": "ok", "applied": [], "failed": {"holografia": "x"}}
    )
    assert msg is not None and "holografia" in msg


def test_gatilhos_tambem_saem_pelo_nome_da_janela() -> None:
    msg = mensagem_de_secao_fora(
        {"status": "ok", "applied": [], "failed": {"triggers": "x"}}
    )
    assert msg is not None and "gatilhos" in msg


# ---------------------------------------------------------------------------
# As bordas do helper
# ---------------------------------------------------------------------------


def test_sem_resposta_o_helper_se_cala() -> None:
    """``None`` = o daemon não respondeu; quem fala é a frase de sempre. Se
    este helper inventasse uma frase aqui, a segunda metade do aceite cairia."""
    assert mensagem_de_secao_fora(None) is None


def test_resposta_aceita_sem_failed_usa_a_frase_do_rodape() -> None:
    """Respondeu, nada entrou e nada foi nomeado: quem fala é o rodapé, para
    não nascer uma quarta frase de estado."""
    resposta = {"status": "ok", "applied": []}
    assert mensagem_de_secao_fora(resposta) == footer_actions._mensagem_de_aplicacao(
        resposta
    )
    assert mensagem_de_secao_fora(resposta) == "Nada foi aplicado ao controle."


def test_daemon_antigo_sem_os_campos_novos_nao_vira_falha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resposta sem ``applied``/``failed`` continua sendo sucesso — a regra que
    ``_algo_foi_aplicado`` e ``_mensagem_de_aplicacao`` afirmam nos dois e que
    a APLICAR-VERDADE-02 já pagou para manter."""
    host = _host()
    _selar_daemon(monkeypatch, {"status": "ok"})

    host.on_lightbar_apply(None)

    assert "Cor enviada ao controle" in _ultimo_toast(host)


# ---------------------------------------------------------------------------
# BG-01 (26/08/2026) — a aba parou de ADIVINHAR e passou a perguntar ao daemon
#
# O defeito, medido na bancada viva em 23/08 e ainda de pé nesta aba: a frase
# de "Cor enviada" x "guardada" saía da HEURÍSTICA do estado da janela
# (`alvo_fora_da_mesa`, `modo_nativo_manda_no_output`), que enxerga DUAS das
# razões e joga fora o corpo do daemon, que traz `aplicado_em`/`guardado_em`.
# A mesma aba já lia o daemon no outro ramo (`apply_draft_detalhado`): eram
# duas verdades sobre o mesmo gesto numa tela só.
# ---------------------------------------------------------------------------

UNIQ_ALVO = "aabbcc000001"

#: A janela num estado em que a HEURÍSTICA diria "aplicado": o alvo escolhido
#: ESTÁ na mesa, o Modo Nativo está desligado, o co-op está desligado. Se a
#: decisão voltar a ser dela, o toast volta a dizer "Cor enviada ao controle".
#: A cor é o gesto: o co-op não governa a cor, e é medido.
def _host_que_a_heuristica_leria_como_aplicado() -> _Host:
    host = _host()
    host._edit_target_uniq = UNIQ_ALVO
    host._edit_target_label = "Controle 1 (USB)"
    host._target_uniq_by_index = {0: UNIQ_ALVO}
    host._modo_nativo_ligado = False
    host._coop_ligado = False
    host._current_rgb = (10, 20, 30)
    host._current_brightness = 0.8
    return host


def _selar_corpo(monkeypatch: pytest.MonkeyPatch, corpo: Any) -> None:
    """Sela a rota `led.set` por MAC com um corpo escolhido do daemon."""
    monkeypatch.setattr(
        lightbar_actions,
        "led_set_detalhado",
        lambda *_a, **_kw: corpo,
    )


def test_zero_destinos_nao_vira_cor_enviada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A MORDIDA da BG-01, e ela é uma frase contra a outra.

    O daemon responde `aplicado_em: []` e `guardado_em: [uniq]` — nada saiu no
    fio, o override ficou registrado — com a janela num estado que a heurística
    leria como "aplicado". A frase tem de dizer GUARDADA.

    **Com a cura arrancada** (trocar `frase_do_envio(...)` de volta por
    `frase_de_guardado(alvo_ausente=alvo_fora_da_mesa(self), ...) or
    _TOAST_COR_ENVIADA...` em `_aplicar_cor_no_controle`), a janela não vê
    pendência nenhuma, a heurística devolve `None`, e o toast volta a ser
    "Cor enviada ao controle (80% de brilho)" — este teste reprova imprimindo
    as duas frases lado a lado.
    """
    host = _host_que_a_heuristica_leria_como_aplicado()
    _selar_corpo(
        monkeypatch,
        {"status": "ok", "aplicado_em": [], "guardado_em": [UNIQ_ALVO]},
    )

    host._aplicar_cor_no_controle()

    frase = _ultimo_toast(host)
    heuristica = "Cor enviada ao controle (80% de brilho)"
    assert GUARDADO in frase, (
        "o daemon disse que NADA saiu no fio e a tela afirmou que a cor foi.\n"
        f"  daemon    : aplicado_em=[] guardado_em=['{UNIQ_ALVO}']\n"
        f"  a tela diz: {frase!r}\n"
        f"  heurística: {heuristica!r}  <- a frase que a adivinhação devolve"
    )
    assert frase != heuristica


def test_com_o_daemon_dizendo_aplicado_a_frase_e_a_de_sempre(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mordida gêmea: a cura não pode avançar longe demais.

    Com `aplicado_em` cheio, o byte saiu — e a palavra desta aba continua
    sendo "enviada", nunca "aplicada" (LIGHTBAR-BT-RESET-01: por Bluetooth o
    firmware aceita e IGNORA a escrita de cor; foram 330 mil escritas com a
    barra apagada). Sem este teste, uma cura que dissesse "guardado" sempre
    passaria no de cima.
    """
    host = _host_que_a_heuristica_leria_como_aplicado()
    _selar_corpo(
        monkeypatch,
        {"status": "ok", "aplicado_em": [UNIQ_ALVO], "guardado_em": []},
    )

    host._aplicar_cor_no_controle()

    assert _ultimo_toast(host) == "Cor enviada ao controle (80% de brilho)"


def test_as_duas_listas_vazias_dizem_que_ninguem_recebeu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rota EXATA que a bancada mediu em 23/08: zero destino, tela verde.

    `{"status": "ok", "aplicado_em": [], "guardado_em": []}` é o que o daemon
    devolve em cinco situações (`_destinos_do_broadcast`), e a única coisa
    honesta a dizer é que ninguém recebeu.
    """
    host = _host_que_a_heuristica_leria_como_aplicado()
    _selar_corpo(monkeypatch, {"status": "ok", "aplicado_em": [], "guardado_em": []})

    host._aplicar_cor_no_controle()

    frase = _ultimo_toast(host)
    assert NADA_ACONTECEU in frase
    assert "enviada" not in frase


def test_o_apagar_tambem_pergunta_ao_daemon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O quinto gesto da aba escreve pela mesma rota e mentia pelo mesmo motivo."""
    host = _host_que_a_heuristica_leria_como_aplicado()
    _selar_corpo(
        monkeypatch,
        {"status": "ok", "aplicado_em": [], "guardado_em": [UNIQ_ALVO]},
    )

    host.on_lightbar_off(None)

    frase = _ultimo_toast(host)
    assert GUARDADO in frase
    assert frase != "Lightbar apagada"


def test_as_cinco_luzes_do_jogador_tambem_perguntam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A BG-01 vale para a cor E para o desenho das 5 luzes (mesma ponte)."""
    host = _host_que_a_heuristica_leria_como_aplicado()
    monkeypatch.setattr(
        lightbar_actions,
        "player_leds_set_detalhado",
        lambda *_a, **_kw: {
            "status": "ok",
            "bits": [],
            "aplicado_em": [],
            "guardado_em": [UNIQ_ALVO],
        },
    )

    host.on_player_leds_preset_p2(None)

    frase = _ultimo_toast(host)
    assert GUARDADO in frase
    assert "Desenho das luzes atualizado" not in frase


def test_a_regua_do_ramo_aplicado(monkeypatch: pytest.MonkeyPatch) -> None:
    """O acoplamento REAL de `frase_do_envio`, medido em vez de suposto.

    `frase_do_envio` reconhece o ramo do aplicado de `frase_do_desfecho` pela
    FORMA com que ele sai de lá — `"<assunto> aplicado"` e
    `"<assunto> aplicado em N controles"`. No dia em que aquela frase mudar de
    forma, esta aba deixa de reconhecê-la e passa a mostrar na tela a palavra
    "aplicado", que ela recusa por medição. Este teste reprova nesse dia, em
    vez de a divergência sair na tela dela.
    """
    corpo_um = {"status": "ok", "aplicado_em": ["a"], "guardado_em": []}
    corpo_tres = {"status": "ok", "aplicado_em": ["a", "b", "c"], "guardado_em": []}
    host = _host_que_a_heuristica_leria_como_aplicado()

    for corpo in (corpo_um, corpo_tres):
        assert frase_do_desfecho("Assunto", corpo, host).startswith(
            "Assunto aplicado"
        ), "o ramo do aplicado mudou de forma — `frase_do_envio` não o vê mais"
        assert frase_do_envio("Assunto", "a frase desta aba", corpo, host) == (
            "a frase desta aba"
        )
