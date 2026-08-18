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

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`.
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
#: O rótulo que a aba Status guarda do alvo (R-16 o preserva quando ele cai).
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
        self._current_rgb = (255, 0, 0)
        self._current_brightness = 0.8
        self._widgets: dict[str, Any] = {}
        self._toasts: list[str] = []
        self._refresh_guard = False

    def _get(self, widget_id: str) -> Any:
        return self._widgets.get(widget_id)

    def _toast_light(self, msg: str) -> None:
        self._toasts.append(msg)


@pytest.fixture(autouse=True)
def _ipc_mudo(monkeypatch: pytest.MonkeyPatch) -> None:
    """O daemon sempre aceita — o que está em julgamento é a FRASE."""
    monkeypatch.setattr(
        lightbar_actions, "led_set", lambda *_a, **_kw: True
    )
    monkeypatch.setattr(
        lightbar_actions, "player_leds_set", lambda *_a, **_kw: True
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

    def test_sem_o_mapa_a_janela_nao_inventa_guardado(self) -> None:
        """O ÚNICO "não sei" que sobrou: a janela não tem o atributo.

        Aqui ela de fato não sabe (mixin instanciada sozinha, sem a aba
        Status). Dizer "guardado" mandaria esperar um controle que talvez
        esteja ali — trocaria uma mentira por outra pior.
        """
        host = _Host(alvo=FORA_DA_MESA, conectados={})
        del host._target_uniq_by_index
        host._aplicar_cor_no_controle()
        (toast,) = host._toasts
        assert GUARDADO not in toast

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
        # ...e o ramo que produz isso está lá, dito com todas as letras.
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

    def test_em_modo_nativo_nao_diz_apagada(self) -> None:
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA}, nativo=True)
        host.on_lightbar_off(None)
        toast = host._toasts[-1]
        assert GUARDADO in toast
        assert "Modo Nativo" in toast
        assert "Lightbar apagada" not in toast

    def test_modo_nativo_e_alvo_fora_somam_no_quinto_gesto_tambem(self) -> None:
        """O gesto novo passa pela mesma soma dos outros — não por uma cópia.

        O "Apagar" foi o último a entrar no vocabulário; provar a soma só nos
        gestos antigos deixaria justamente o novo livre para voltar à cadeia
        ``if/elif`` que o conserto veio matar.
        """
        host = _Host(alvo=FORA_DA_MESA, conectados={0: NA_MESA}, nativo=True)
        host.on_lightbar_off(None)
        assert host._toasts[-1] == (
            "Apagar a lightbar — guardado: em Modo Nativo quem manda no "
            "controle é o jogo; o Controle 2 não está na mesa. Vale quando o "
            "Modo Nativo sair e o Controle 2 voltar."
        )

    def test_com_o_alvo_na_mesa_a_frase_e_a_de_sempre(self) -> None:
        """Hipótese tem de explicar o que JÁ funcionava."""
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA})
        host.on_lightbar_off(None)
        assert host._toasts[-1] == "Lightbar apagada"

    def test_o_coop_nao_governa_a_cor_e_a_frase_nao_o_cita(self) -> None:
        """Medido, não suposto: a camada do co-op tem vocabulário de UM campo.

        Somar o co-op à frase do "Apagar" seria inventar uma pendência que o
        mecanismo não tem — ``set_coop_outputs`` descarta tudo que não é
        ``player_leds``.
        """
        from hefesto_dualsense4unix.core import backend_pydualsense

        assert backend_pydualsense._COOP_LAYER_FIELDS == ("player_leds",)
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA}, coop=True)
        host.on_lightbar_off(None)
        assert host._toasts[-1] == "Lightbar apagada"


class TestAsPendenciasSomam:
    """CONSERTO 1.5 — duas razões ao mesmo tempo, que é a mesa dela de hoje.

    A cadeia ``if/elif`` parava na primeira condição verdadeira. Com o co-op
    ligado (o fixture de hoje traz ``coop.enabled=true``) e o alvo mantido
    fora da mesa pela R-16, o toast prometia *"Vale quando o co-op sair"* — e
    sair do co-op não faz valer nada, porque o controle continua fora.

    **As SEIS combinações, e por que as quatro primeiras não bastam.** As
    pendências são três, logo as somas possíveis são quatro (três pares e a
    trinca). A primeira volta do conserto provou só dois pares — co-op+ausente
    e nativo+ausente — e a metade que ficou de fora é justamente a que só
    existe por causa desta cura: *"com duas ou três monta uma só"*. Medido, não
    suposto: com ``_e()`` devolvendo lixo para três itens E com a
    ``frase_de_guardado`` descartando o co-op sempre que o Modo Nativo também
    vale, 796 testes passavam — a cura arrancada e nenhum vermelho. Por isso os
    dois testes abaixo, e por isso eles fixam a frase INTEIRA: quem some numa
    soma some em silêncio, e um ``in`` por pendência não vê a ordem trocada nem
    o separador errado.

    **O que estes testes NÃO resolvem, e é decisão dela** (medido em 14/08, não
    estimado): a frase da trinca tem 256 caracteres no pior caso — o desenho
    com os cinco LEDs acesos — e o rótulo da ``Gtk.Statusbar`` é de UMA linha
    com ``PANGO_ELLIPSIZE_END`` (conferido no widget, não na memória). Na
    largura padrão da janela (``default-width`` 1180 no `main.glade`) cabem
    ~183 caracteres: a frase de três pendências é cortada dentro do último
    motivo e o *"Vale quando…"* inteiro — a parte que diz o que ela precisa
    fazer — não chega à tela. A de duas pendências cabe raspando (1123 px de
    1156 px), e não cabe mais quando o aviso do D4 entra na frente. Encurtar é
    escolha de texto, e texto é dela; o que o teste pode garantir é que
    nenhuma pendência suma em silêncio.
    """

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

    def test_modo_nativo_e_alvo_fora_promete_as_duas_liberacoes(self) -> None:
        host = _Host(alvo=FORA_DA_MESA, conectados={0: NA_MESA}, nativo=True)
        host._aplicar_cor_no_controle()
        toast = host._toasts[-1]
        assert GUARDADO in toast
        assert "Modo Nativo sair" in toast
        assert "Controle 2 voltar" in toast

    def test_os_dois_donos_de_agora_juntos_somam(self) -> None:
        """co-op E Modo Nativo, com o alvo NA mesa — o par que faltava.

        São as duas pendências que valem mesmo com o controle na mesa, e
        nenhum teste as punha juntas. Sem esta mordida, quem escrevesse
        ``if coop and not nativo`` engolia a do co-op sem um vermelho.
        """
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA}, coop=True, nativo=True)
        host.on_player_leds_preset_p3(None)
        assert host._toasts[-1] == (
            "Desenho das luzes (LEDs acesos: 1, 3 e 5) — guardado: com o co-op "
            "ligado, quem manda nas 5 luzes é ele; em Modo Nativo quem manda no "
            "controle é o jogo. Vale quando o co-op sair e o Modo Nativo sair."
        )
        assert "não está na mesa" not in host._toasts[-1], (
            "o alvo está na mesa — a frase não pode inventar a terceira pendência"
        )

    def test_as_tres_pendencias_juntas_prometem_as_tres_liberacoes(self) -> None:
        """A trinca: co-op ligado, Modo Nativo ligado e o alvo fora da mesa.

        É o caso que só existe por causa deste conserto — e é alcançável na
        mesa dela: o co-op fica ligado, o Modo Nativo entra quando o jogo pega
        o `hidraw`, e a R-16 segura o alvo quando o controle cai. Prometer duas
        das três liberações é a mesma mentira que a soma veio matar, uma casa
        adiante.
        """
        host = _Host(
            alvo=FORA_DA_MESA, conectados={0: NA_MESA}, coop=True, nativo=True
        )
        host.on_player_leds_preset_p3(None)
        toast = host._toasts[-1]
        for liberacao in ("o co-op sair", "o Modo Nativo sair", "o Controle 2 voltar"):
            assert liberacao in toast, (
                f"a liberação «{liberacao}» sumiu da soma de três: {toast}"
            )
        assert toast == (
            "Desenho das luzes (LEDs acesos: 1, 3 e 5) — guardado: com o co-op "
            "ligado, quem manda nas 5 luzes é ele; em Modo Nativo quem manda no "
            "controle é o jogo; o Controle 2 não está na mesa. Vale quando o "
            "co-op sair, o Modo Nativo sair e o Controle 2 voltar."
        )
        # A ordem é a decisão documentada: os donos de AGORA antes da ausência.
        assert (
            toast.index("co-op ligado")
            < toast.index("em Modo Nativo")
            < toast.index("não está na mesa")
        )

    def test_uma_pendencia_so_continua_com_a_frase_de_sempre(self) -> None:
        """Hipótese tem de explicar o que JÁ funcionava: com UMA condição, as
        frases saem palavra por palavra como saíam."""
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
        assert so_nativo._toasts[-1] == (
            "Cor (80% de brilho) — guardado; em Modo Nativo quem manda no "
            "controle é o jogo. Vale quando o Modo Nativo sair."
        )


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
    """CONSERTO 1.3 — a terceira condição da tabela de mentiras, na janela.

    O backend deixou de dizer "escreveu" com o output mutado; aqui prova-se que
    a TELA deixou de dizer "aplicado" nas duas abas que escrevem output. A aba
    Gatilhos era a que não tinha portão nenhum de Modo Nativo: o toast
    "Rigido aplicado" saía com zero byte no fio.
    """

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

    def test_cor_em_modo_nativo_nao_diz_enviada(self) -> None:
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA}, nativo=True)
        host._aplicar_cor_no_controle()
        (toast,) = host._toasts
        assert GUARDADO in toast
        assert "Modo Nativo" in toast
        assert "enviada" not in toast

    def test_desenho_em_modo_nativo_nao_diz_atualizado(self) -> None:
        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA}, nativo=True)
        host.on_player_leds_preset_p3(None)
        toast = host._toasts[-1]
        assert GUARDADO in toast
        assert "Modo Nativo" in toast
        assert "atualizado —" not in toast

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
        """O flag tem de ter DONO: a aba Status o publica a cada tique lento.

        Sem esta ponte o gate acima seria letra morta — `_modo_nativo_ligado`
        ficaria sempre no padrão `False` e o toast voltaria a mentir.
        """
        from hefesto_dualsense4unix.app.actions.status_actions import (
            StatusActionsMixin,
        )

        host = _Host(alvo=NA_MESA, conectados={0: NA_MESA})
        StatusActionsMixin._sync_modo_nativo_manda_no_output(host, {"native_mode": True})
        assert host._modo_nativo_ligado is True
        StatusActionsMixin._sync_modo_nativo_manda_no_output(host, {})
        assert host._modo_nativo_ligado is False
        # ...e que o tique lento a CHAMA (mesmo vigia do import de vocabulário
        # logo abaixo): uma ponte que ninguém atravessa é o flag no padrão.
        fonte = inspect.getsource(StatusActionsMixin._render_slow_state)
        assert "_sync_modo_nativo_manda_no_output" in fonte


class TestOVocabularioMoraNumLugarSo:
    def test_o_nome_do_alvo_perde_o_transporte(self) -> None:
        assert nome_curto_do_alvo("Controle 2 (BT)") == "Controle 2"
        assert nome_curto_do_alvo(None) == "esse controle"

    def test_o_alvo_sem_nome_nao_compoe_portugues_quebrado(self) -> None:
        """CONSERTO 1.5 — o fallback compunha *"quando o esse controle
        voltar"*, pt-BR quebrado saindo do módulo cujo motivo de existir é a
        palavra certa. O nome próprio pede artigo; o de fallback já traz o
        seu."""
        assert guardado_ate_o_alvo_voltar("Cor", nome_curto_do_alvo(None)) == (
            "Cor — guardado, vai valer quando esse controle voltar."
        )
        assert guardado_ate_o_alvo_voltar("Cor", "Controle 2") == (
            "Cor — guardado, vai valer quando o Controle 2 voltar."
        )

    def test_os_modulos_que_o_importam_usam_a_mesma_palavra(self) -> None:
        """Se alguém escrever "guardado" à mão em outro arquivo, esta conta
        continua passando — mas o import some, e é o import que se vigia.

        São DOIS módulos, não três (o relatório da entrega dizia "três abas", e
        o nome antigo deste teste repetia o erro enquanto percorria dois): a
        aba Rumble não tem toast de "aplicado" para corrigir. A lista aqui é a
        conta, e a asserção de baixo a mantém honesta.
        """
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
            assert f'"{GUARDADO}' not in fonte, (
                f"{modulo.__name__} escreveu a palavra em vez de importá-la"
            )
