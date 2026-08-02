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
    mensagem_de_secao_fora,
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
    assert "Cor aplicada no controle" in msg
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

    assert "Cor aplicada no controle" in _ultimo_toast(host)
