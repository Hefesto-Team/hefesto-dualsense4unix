"""MESA-CHEIA-09/E3 — os toasts param de afirmar o que não aconteceu.

Metade de tela do
`test_mesa_cheia_09_aplicado_e_verdade.py` (que prova o daemon). Aqui prova-se
o que a JANELA diz, nos casos que a D-9 nomeia:

* **alvo fora da mesa** — *"Guardado — vai valer quando o Controle N voltar"*;
* **co-op ligado** — a aba Lightbar dizia *"Desenho das luzes aplicado"* no
  toast e *"com o co-op ligado, é ele que manda nas 5 luzes"* no rótulo três
  centímetros abaixo. A MESMA tela, contradizendo a si mesma;
* **Modo Nativo ligado** (entrou no conserto 1.3) — o jogo é o dono do
  `hidraw` e o backend muta toda escrita de output.

O vocabulário está num lugar só (`app/textos_de_aplicacao.py`) — a regra de
execução da própria D-9. Este arquivo também PROVA isso: as frases dos gestos
saem daquele módulo, e trocá-lo troca todas.

CONSERTO 1.5, e são três coisas que faltavam:

* o QUINTO gesto de saída da aba Lightbar — o botão "Apagar" — dizia "Lightbar
  apagada" pela mesma rota por-MAC do vizinho já curado (`TestOQuintoGesto…`);
* as razões SOMAM: co-op ligado E alvo fora da mesa é o estado normal da mesa
  dela, e a cadeia `if/elif` prometia só a primeira liberação
  (`TestAsPendenciasSomam` — e ali estão as QUATRO somas possíveis, inclusive a
  trinca, que na primeira volta do conserto ficou sem mordida nenhuma);
* mapa de conectados VAZIO não é "não sei quem está na mesa" — é "nenhum
  DualSense na mesa", e a guarda que os confundia devolvia a frase de sucesso
  no exato caso em que o daemon responde `guardado_em=[uniq]`.

GUI: precisa de `gi` real (padrão de `test_lightbar_todos_por_mac_r14.py`).
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("toasts honestos da mesa cheia 09")

import inspect
import json
from pathlib import Path
from typing import Any

import pytest

gi = pytest.importorskip("gi")

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app import draft_config as draft_mod
from hefesto_dualsense4unix.app.actions import lightbar_actions, triggers_actions
from hefesto_dualsense4unix.app.actions.lightbar_actions import (
    LightbarActionsMixin,
    texto_do_desenho_aceso,
)
from hefesto_dualsense4unix.app.actions.triggers_actions import TriggersActionsMixin
from hefesto_dualsense4unix.app.textos_de_aplicacao import (
    GUARDADO,
    guardado_ate_o_alvo_voltar,
    nome_curto_do_alvo,
)
from hefesto_dualsense4unix.profiles.schema import LedsConfig, MatchAny, Profile

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "state_full_quatro_controles.json"
)
UNIQS: list[str] = [
    c["uniq"] for c in json.loads(FIXTURE.read_text(encoding="utf-8"))["controllers"]
]
NA_MESA, FORA_DA_MESA = UNIQS[0], UNIQS[1]
ROTULO_DO_AUSENTE = "Controle 2 (BT)"


class _Host(LightbarActionsMixin):
    """Host mínimo com o estado que a aba Status mantém do `state_full`."""

    def __init__(
        self,
        *,
        alvo: str | None,
        conectados: dict[int, str | None],
        coop: bool = False,
        nativo: bool = False,
    ) -> None:
        perfil = Profile(
            name="mesa",
            match=MatchAny(),
            priority=1,
            leds=LedsConfig(
                lightbar=(255, 0, 0),
                player_leds=[True, False, False, False, False],
                lightbar_brightness=1.0,
                auto_player_colors=False,
            ),
        )
        self.draft = draft_mod.DraftConfig.from_profile(perfil)
        self._edit_target_uniq = alvo
        self._edit_target_label = ROTULO_DO_AUSENTE
        self._target_uniq_by_index = conectados
        self._coop_ligado = coop
        self._modo_nativo_ligado = nativo
        _MESA_DO_DAEMON["conectados"] = {
            v for v in conectados.values() if isinstance(v, str) and v
        }
        _MESA_DO_DAEMON["nativo"] = nativo
        self._current_rgb = (255, 0, 0)
        self._current_brightness = 0.8
        self._widgets: dict[str, Any] = {}
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)


_MESA_DO_DAEMON: dict[str, Any] = {"conectados": set(), "nativo": False}


def _corpo_por_uniq(uniq: str | None) -> dict[str, Any]:
    """A resposta que o daemon monta para um ``led.set``/``led.player_set``."""
    if uniq and uniq in _MESA_DO_DAEMON["conectados"]:
        return {"status": "ok", "aplicado_em": [uniq], "guardado_em": []}
    if uniq:
        return {"status": "ok", "aplicado_em": [], "guardado_em": [uniq]}
    return {"status": "ok", "aplicado_em": [], "guardado_em": []}


@pytest.fixture(autouse=True)
def _ipc_mudo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O daemon responde como o daemon — o que está em julgamento é a FRASE."""
    monkeypatch.setattr(
        lightbar_actions,
        "led_set_detalhado",
        lambda _rgb, brightness=None, uniq=None: _corpo_por_uniq(uniq),
    )
    monkeypatch.setattr(
        lightbar_actions,
        "player_leds_set_detalhado",
        lambda _bits, uniq=None: _corpo_por_uniq(uniq),
    )


class TestACorDaLightbar:
    def test_alvo_fora_da_mesa_diz_guardado_e_quando_vale(self) -> None:
        host = _Host(alvo=FORA_DA_MESA, conectados={0: NA_MESA})
        host._aplicar_cor_no_controle()
        (toast,) = host._toasts
        assert GUARDADO in toast
        assert "vai valer quando o Controle 2 voltar" in toast
        assert "enviada" not in toast, "a frase antiga afirmava envio sem envio"

    def test_alvo_na_mesa_continua_dizendo_o_que_dizia(self) -> None:
        """Hipótese tem de explicar o que JÁ funcionava."""
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA})
        host._aplicar_cor_no_controle()
        (toast,) = host._toasts
        assert toast == "Cor enviada ao controle (80% de brilho)"

    def test_mesa_sem_dualsense_com_o_alvo_de_pe_tambem_e_guardado(self) -> None:
        """CONSERTO 1.5 — mapa VAZIO não é "não sei quem está na mesa".

        A guarda antiga tratava mapa vazio como ignorância e devolvia a frase
        de sucesso, transformando a mentira em comportamento desejado. Mapa
        vazio é *"nenhum DualSense na mesa"* — e com o alvo de pé (R-16) a
        escrita vai por MAC para quem não está lá, que é exatamente o caso em
        que o daemon devolve ``guardado_em=[uniq]``.
        """
        host = _Host(alvo=FORA_DA_MESA, conectados={})
        host._aplicar_cor_no_controle()
        (toast,) = host._toasts
        assert GUARDADO in toast
        assert "vai valer quando o Controle 2 voltar" in toast

    def test_sem_o_mapa_a_janela_nao_promete_uma_volta_que_nao_conhece(
        self,
    ) -> None:
        """O ÚNICO "não sei" que sobrou: a janela não tem o atributo."""
        host = _Host(alvo=FORA_DA_MESA, conectados={})
        del host._target_uniq_by_index
        host._aplicar_cor_no_controle()
        (toast,) = host._toasts
        assert GUARDADO in toast, "o daemon disse guardado; a tela cala isso?"
        assert "voltar" not in toast, (
            "a janela prometeu a volta de um controle que ela não sabe se "
            "está fora da mesa"
        )
        assert "enviada" not in toast

    def test_o_estado_de_mapa_vazio_com_alvo_de_pe_existe_no_produto(self) -> None:
        """A guarda antiga se justificava com um estado impossível; este é o
        possível, e é o que a manda cair.

        Com ZERO DualSense e um externo na mesa (8BitDo, Pro Controller), a
        aba Status recalcula o mapa a partir de uma lista vazia de conectados
        e NÃO mexe no alvo — ``editavel = contagem.adotados >= 1`` é falso, e
        ``_sync_edit_target`` só é chamado dentro dele (ou com a mesa
        literalmente vazia, `total < 1`). O resultado é este host.
        """
        from hefesto_dualsense4unix.app.actions.status_actions import (
            StatusActionsMixin,
        )

        host = _Host(alvo=FORA_DA_MESA, conectados={0: NA_MESA})
        StatusActionsMixin._update_target_maps(host, [])
        assert host._target_uniq_by_index == {}
        assert host._edit_target_uniq == FORA_DA_MESA, "R-16 mantém o alvo"
        host._aplicar_cor_no_controle()
        assert GUARDADO in host._toasts[-1]
        fonte = inspect.getsource(
            StatusActionsMixin._refresh_controller_target_combo
        )
        assert "editavel = contagem.adotados >= 1" in fonte
        assert "Só externos conectados" in fonte


class TestODesenhoDasCincoLuzes:
    def test_com_o_coop_ligado_o_toast_e_o_rotulo_dizem_o_mesmo_dono(self) -> None:
        """MORDIDA 4 — a contradição medida ao vivo em 03/08."""
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA}, coop=True)
        host.on_player_leds_preset_p3(None)
        toast = host._toasts[-1]
        rotulo = texto_do_desenho_aceso(
            (True, False, True, False, True), 3, coop_ligado=True
        )
        assert "co-op" in rotulo and "manda nas 5 luzes" in rotulo
        assert "co-op" in toast and "manda nas 5 luzes" in toast, (
            "o toast afirmava um dono das 5 luzes e o rótulo logo abaixo "
            "afirmava outro"
        )
        assert GUARDADO in toast
        assert "atualizado —" not in toast

    def test_alvo_fora_da_mesa_guarda_o_desenho(self) -> None:
        host = _Host(alvo=FORA_DA_MESA, conectados={0: NA_MESA})
        host.on_player_leds_preset_p3(None)
        toast = host._toasts[-1]
        assert GUARDADO in toast
        assert "vai valer quando o Controle 2 voltar" in toast

    def test_sem_coop_e_com_o_alvo_na_mesa_a_frase_e_a_de_sempre(self) -> None:
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA})
        host.on_player_leds_preset_p3(None)
        toast = host._toasts[-1]
        assert toast.startswith("Desenho das luzes atualizado —")


class TestOQuintoGestoDaAba:
    """CONSERTO 1.5 — o botão "Apagar", que ficou de fora dos quatro curados.

    Ele escreve pela MESMA rota por-MAC do "Aplicar no controle" 60 linhas
    acima (``led_set((0, 0, 0), uniq=self._edit_uniq())``) e dizia "Lightbar
    apagada" — fato consumado — sem um byte no fio. Era a mesma tela dizendo a
    verdade num botão e a mentira no botão ao lado.
    """

    def test_alvo_fora_da_mesa_nao_diz_apagada(self) -> None:
        host = _Host(alvo=FORA_DA_MESA, conectados={0: NA_MESA})
        host.on_lightbar_off(None)
        toast = host._toasts[-1]
        assert GUARDADO in toast
        assert "vai valer quando o Controle 2 voltar" in toast
        assert "Lightbar apagada" not in toast

    def test_em_modo_nativo_diz_apagada(self) -> None:
        """Era «em Modo Nativo não diz apagada». Desde 23/09/2026 a barra é do"""
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA}, nativo=True)
        host.on_lightbar_off(None)
        toast = host._toasts[-1]
        assert GUARDADO not in toast
        assert "Modo Nativo" not in toast
        assert "Lightbar apagada" in toast

    def test_modo_nativo_e_alvo_fora_somam_no_quinto_gesto_tambem(self) -> None:
        """O gesto novo passa pela mesma soma dos outros — não por uma cópia."""
        host = _Host(alvo=FORA_DA_MESA, conectados={0: NA_MESA}, nativo=True)
        host.on_lightbar_off(None)
        assert host._toasts[-1] == (
            "Apagar a lightbar — guardado, vai valer quando o Controle 2 voltar."
        )

    def test_com_o_alvo_na_mesa_a_frase_e_a_de_sempre(self) -> None:
        """Hipótese tem de explicar o que JÁ funcionava."""
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA})
        host.on_lightbar_off(None)
        assert host._toasts[-1] == "Lightbar apagada"

    def test_o_coop_nao_governa_a_cor_e_a_frase_nao_o_cita(self) -> None:
        """Medido, não suposto: a camada do co-op tem vocabulário de UM campo."""
        from hefesto_dualsense4unix.core import backend_pydualsense

        assert backend_pydualsense._COOP_LAYER_FIELDS == ("player_leds",)
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA}, coop=True)
        host.on_lightbar_off(None)
        assert host._toasts[-1] == "Lightbar apagada"


class TestAsPendenciasSomam:
    """CONSERTO 1.5 — duas razões ao mesmo tempo, que é a mesa dela de hoje."""

    def test_coop_ligado_e_alvo_fora_promete_as_duas_liberacoes(self) -> None:
        host = _Host(alvo=FORA_DA_MESA, conectados={0: NA_MESA}, coop=True)
        host.on_player_leds_preset_p3(None)
        toast = host._toasts[-1]
        assert GUARDADO in toast
        assert "co-op sair" in toast, "a pendência do co-op sumiu"
        assert "Controle 2 voltar" in toast, (
            "sair do co-op não basta — o controle também precisa voltar, e a "
            "frase prometia que bastava"
        )

    def test_modo_nativo_e_alvo_fora_a_cor_so_espera_o_controle(self) -> None:
        """A cor no Modo Nativo sai no fio desde 23/09/2026"""
        host = _Host(alvo=FORA_DA_MESA, conectados={0: NA_MESA}, nativo=True)
        host._aplicar_cor_no_controle()
        toast = host._toasts[-1]
        assert GUARDADO in toast
        assert "Modo Nativo" not in toast
        assert "Controle 2 voltar" in toast

    def test_os_dois_donos_de_agora_juntos_somam(self) -> None:
        """co-op E Modo Nativo, com o alvo NA mesa — o par que faltava."""
        from hefesto_dualsense4unix.app.textos_de_aplicacao import frase_de_guardado

        assert frase_de_guardado(
            "Desenho das luzes (LEDs acesos: 1, 3 e 5)",
            alvo_ausente=None,
            coop=True,
            nativo=True,
        ) == (
            "Desenho das luzes (LEDs acesos: 1, 3 e 5) — guardado: com o co-op "
            "ligado, quem manda nas 5 luzes é ele; em Modo Nativo quem manda no "
            "controle é o jogo. Vale quando o co-op sair e o Modo Nativo sair."
        )
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA}, coop=True, nativo=True)
        host.on_player_leds_preset_p3(None)
        assert host._toasts[-1] == (
            "Desenho das luzes (LEDs acesos: 1, 3 e 5) — guardado; com o co-op "
            "ligado, quem manda nas 5 luzes é ele. Vale quando o co-op sair."
        )
        assert "não está ligado" not in host._toasts[-1], (
            "o alvo está na mesa — a frase não pode inventar a terceira pendência"
        )

    def test_as_tres_pendencias_juntas_prometem_as_tres_liberacoes(self) -> None:
        """A trinca: co-op ligado, Modo Nativo ligado e o alvo fora da mesa."""
        from hefesto_dualsense4unix.app.textos_de_aplicacao import frase_de_guardado

        toast = frase_de_guardado(
            "Desenho das luzes (LEDs acesos: 1, 3 e 5)",
            alvo_ausente=ROTULO_DO_AUSENTE.split(" (")[0],
            coop=True,
            nativo=True,
        )
        assert toast is not None
        for liberacao in ("o co-op sair", "o Modo Nativo sair", "o Controle 2 voltar"):
            assert liberacao in toast, (
                f"a liberação «{liberacao}» sumiu da soma de três: {toast}"
            )
        assert toast == (
            "Desenho das luzes (LEDs acesos: 1, 3 e 5) — guardado: com o co-op "
            "ligado, quem manda nas 5 luzes é ele; em Modo Nativo quem manda no "
            "controle é o jogo; o Controle 2 não está ligado. Vale quando o "
            "co-op sair, o Modo Nativo sair e o Controle 2 voltar."
        )
        assert (
            toast.index("co-op ligado")
            < toast.index("em Modo Nativo")
            < toast.index("não está ligado")
        )
        host = _Host(
            alvo=FORA_DA_MESA, conectados={0: NA_MESA}, coop=True, nativo=True
        )
        host.on_player_leds_preset_p3(None)
        assert "Modo Nativo" not in host._toasts[-1]
        assert "o co-op sair" in host._toasts[-1]
        assert "o Controle 2 voltar" in host._toasts[-1]

    def test_uma_pendencia_so_continua_com_a_frase_de_sempre(self) -> None:
        """Hipótese tem de explicar o que JÁ funcionava: com UMA condição, as"""
        so_coop = _Host(alvo=NA_MESA, conectados={0: NA_MESA}, coop=True)
        so_coop.on_player_leds_preset_p3(None)
        assert so_coop._toasts[-1] == (
            "Desenho das luzes (LEDs acesos: 1, 3 e 5) — guardado; com o co-op "
            "ligado, quem manda nas 5 luzes é ele. Vale quando o co-op sair."
        )
        so_fora = _Host(alvo=FORA_DA_MESA, conectados={0: NA_MESA})
        so_fora._aplicar_cor_no_controle()
        assert so_fora._toasts[-1] == (
            "Cor (80% de brilho) — guardado, vai valer quando o Controle 2 "
            "voltar."
        )
        so_nativo = _Host(alvo=NA_MESA, conectados={0: NA_MESA}, nativo=True)
        so_nativo._aplicar_cor_no_controle()
        assert so_nativo._toasts[-1] == "Cor enviada ao controle (80% de brilho)"


class _BarraDeStatus:
    def __init__(self) -> None:
        self.mensagens: list[str] = []

    def get_context_id(self, _k: str) -> int:
        return 1

    def push(self, _ctx: int, msg: str) -> None:
        self.mensagens.append(msg)


class _HostGatilhos(TriggersActionsMixin):
    def __init__(
        self,
        *,
        alvo: str | None,
        conectados: dict[int, str | None],
        nativo: bool = False,
    ) -> None:
        self._edit_target_uniq = alvo
        self._edit_target_label = ROTULO_DO_AUSENTE
        self._target_uniq_by_index = conectados
        self._modo_nativo_ligado = nativo
        self.barra = _BarraDeStatus()

    def _get(self, widget_id: str) -> Any:
        return self.barra if widget_id == "status_bar" else None


class TestOToastDosGatilhos:
    def test_alvo_fora_da_mesa_diz_guardado(self) -> None:
        host = _HostGatilhos(alvo=FORA_DA_MESA, conectados={0: NA_MESA})
        host._toast_trigger("left", "Rigid", True)
        (msg,) = host.barra.mensagens
        assert msg.startswith("Gatilho esquerdo (L2): Rigid")
        assert GUARDADO in msg
        assert "vai valer quando o Controle 2 voltar" in msg
        assert "aplicado" not in msg

    def test_alvo_na_mesa_continua_aplicado(self) -> None:
        host = _HostGatilhos(alvo=NA_MESA, conectados={0: NA_MESA})
        host._toast_trigger("left", "Rigid", True)
        assert host.barra.mensagens == ["Gatilho esquerdo (L2): Rigid aplicado"]

    def test_recusa_do_daemon_nao_vira_guardado(self) -> None:
        """"Guardado" é sucesso adiado; recusa é outra coisa e continua sendo."""
        host = _HostGatilhos(alvo=FORA_DA_MESA, conectados={0: NA_MESA})
        host._toast_trigger("left", "Rigid", False, motivo="Fim <= Início")
        (msg,) = host.barra.mensagens
        assert GUARDADO not in msg
        assert "não aplicado" in msg


class TestOModoNativoNaTela:
    """CONSERTO 1.3 — a terceira condição da tabela de mentiras, na janela."""

    def test_gatilho_em_modo_nativo_nao_diz_aplicado(self) -> None:
        host = _HostGatilhos(alvo=NA_MESA, conectados={0: NA_MESA}, nativo=True)
        host._toast_trigger("left", "Rigid", True)
        (msg,) = host.barra.mensagens
        assert msg.startswith("Gatilho esquerdo (L2): Rigid")
        assert GUARDADO in msg
        assert "Modo Nativo" in msg
        assert "aplicado" not in msg, (
            "em Modo Nativo o dono do hidraw é o jogo — o toast afirmava "
            "escrita com o report_thread inteiro mutado"
        )

    def test_cor_em_modo_nativo_diz_enviada(self) -> None:
        """Era «não diz enviada»; desde 23/09/2026 a cor SAI no Modo Nativo"""
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA}, nativo=True)
        host._aplicar_cor_no_controle()
        (toast,) = host._toasts
        assert toast == "Cor enviada ao controle (80% de brilho)"

    def test_desenho_em_modo_nativo_diz_atualizado(self) -> None:
        """O número também é do Hefesto no Modo Nativo desde 23/09/2026"""
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA}, nativo=True)
        host.on_player_leds_preset_p3(None)
        toast = host._toasts[-1]
        assert GUARDADO not in toast
        assert "Modo Nativo" not in toast
        assert toast.startswith("Desenho das luzes atualizado —")

    def test_sem_modo_nativo_as_tres_frases_sao_as_de_sempre(self) -> None:
        """Hipótese tem de explicar o que JÁ funcionava."""
        gatilhos = _HostGatilhos(alvo=NA_MESA, conectados={0: NA_MESA})
        gatilhos._toast_trigger("left", "Rigid", True)
        assert gatilhos.barra.mensagens == ["Gatilho esquerdo (L2): Rigid aplicado"]
        luzes = _Host(alvo=NA_MESA, conectados={0: NA_MESA})
        luzes._aplicar_cor_no_controle()
        luzes.on_player_leds_preset_p3(None)
        assert luzes._toasts[0] == "Cor enviada ao controle (80% de brilho)"
        assert luzes._toasts[-1].startswith("Desenho das luzes atualizado —")

    def test_a_janela_le_o_modo_nativo_do_state_full(self) -> None:
        """O flag tem de ter DONO: a aba Status o publica a cada tique lento."""
        from hefesto_dualsense4unix.app.actions.status_actions import (
            StatusActionsMixin,
        )

        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA})
        StatusActionsMixin._sync_modo_nativo_manda_no_output(host, {"native_mode": True})
        assert host._modo_nativo_ligado is True
        StatusActionsMixin._sync_modo_nativo_manda_no_output(host, {})
        assert host._modo_nativo_ligado is False
        fonte = inspect.getsource(StatusActionsMixin._render_slow_state)
        assert "_sync_modo_nativo_manda_no_output" in fonte


class TestOVocabularioMoraNumLugarSo:
    def test_o_nome_do_alvo_perde_o_transporte(self) -> None:
        assert nome_curto_do_alvo("Controle 2 (BT)") == "Controle 2"
        assert nome_curto_do_alvo(None) == "esse controle"

    def test_o_alvo_sem_nome_nao_compoe_portugues_quebrado(self) -> None:
        """CONSERTO 1.5 — o fallback compunha *"quando o esse controle"""
        assert guardado_ate_o_alvo_voltar("Cor", nome_curto_do_alvo(None)) == (
            "Cor — guardado, vai valer quando esse controle voltar."
        )
        assert guardado_ate_o_alvo_voltar("Cor", "Controle 2") == (
            "Cor — guardado, vai valer quando o Controle 2 voltar."
        )

    def test_os_modulos_que_o_importam_usam_a_mesma_palavra(self) -> None:
        """Se alguém escrever "guardado" à mão em outro arquivo, esta conta"""
        importadores = {
            caminho.name
            for caminho in Path(lightbar_actions.__file__).parent.parent.rglob(
                "*.py"
            )
            if "textos_de_aplicacao" in caminho.read_text(encoding="utf-8")
            and caminho.name != "textos_de_aplicacao.py"
        }
        assert importadores == {"lightbar_actions.py", "triggers_actions.py"}
        for modulo in (lightbar_actions, triggers_actions):
            fonte = Path(modulo.__file__).read_text(encoding="utf-8")
            assert "textos_de_aplicacao" in fonte, modulo.__name__
            escrita_a_mao = [
                trecho
                for trecho in fonte.split(f'"{GUARDADO}')[1:]
                if not trecho.startswith("_em")
            ]
            assert not escrita_a_mao, (
                f"{modulo.__name__} escreveu a palavra em vez de importá-la"
            )
