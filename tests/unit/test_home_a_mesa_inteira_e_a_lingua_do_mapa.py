"""A conta da mesa conta quem está na mesa, e o card fala a língua da casa.

INÍCIO NÃO MENTE-01 — **I5** e a metade de transporte da **I9**.

**I5.** A Início não desenhava um único controle externo e não lia
``state["external"]`` (§2.2g). Com dois DualSense e um 8BitDo na mesa, esta aba
dizia *"2 controles = 2 jogadores"* enquanto a aba Configurações mostrava TRÊS
cards. Era a pergunta dela — *"o produto funciona com 4 controles ao mesmo
tempo?"* — respondida com **não, a primeira tela nem os enxerga**.

**I9 (metade de transporte).** Quatro dialetos para o mesmo fato na mesma
janela (§2.2h): a Início dizia ``USB``/``BT``, os externos ``cabo``/``BT``, a
Configurações ``Rádio em uso``, e o mapa de canais — que é o **portão** — diz
``cabo``/``rádio``. Nenhum estava errado sozinho; juntos ensinavam que são
coisas diferentes.

O QUE FICOU DE FORA, E POR QUÊ (não é esquecimento)
----------------------------------------------------

* **as outras três superfícies** (``external_controllers.transport_label``,
  ``config/secao_mesa.py``, e a Status) são de outros donos nesta leva. A régua
  que as cobra existe abaixo e está ``xfail(strict=True)``: no dia em que elas
  falarem a mesma língua, ela PASSA e o strict reprova, obrigando quem integrar
  a apagar o xfail;
* **o texto do aviso de grab** (*"Grab falhou — input pode dobrar no jogo"*)
  continua o de sempre. Ele é jargão de kernel, e a I9 o reescreveria para
  dizer o que acontece com ela — mas o que exatamente acontece depende do que a
  ``ESCONDE-SO-O-HIDRAW-01`` (aberta) concluir sobre o que o jogo continua
  vendo pelo evdev. Trocar a frase antes disso é trocar um jargão CERTO por uma
  promessa não apurada.
"""
from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_EXTERNOS = RAIZ / "tests" / "fixtures" / "inventario_externos.json"

#: O 8BitDo em modo Switch por rádio, do inventário VERSIONADO. Lido do disco e
#: não escrito aqui: endereço digitado num teste é endereço que o portão de
#: anonimato de fixtures não confere.
def _um_externo() -> dict[str, Any]:
    bruto = json.loads(FIXTURE_EXTERNOS.read_text(encoding="utf-8"))
    return dict(bruto["external"][0])


class _Widget:
    def __init__(self, label: str | None = None, **_kw: Any) -> None:
        # O `label=` do construtor é guardado: `Gtk.Label(label=...)` é como
        # o `_render_home_controllers` escreve o subtítulo do card, e um
        # dublê que o jogasse fora mediria uma fileira de cards mudos.
        self.texto = label or ""
        self.visivel = True
        self.filhos: list[Any] = []
        self.classes: list[str] = []

    def set_text(self, v: str) -> None:
        self.texto = v

    def get_text(self) -> str:
        return self.texto

    def set_markup(self, v: str) -> None:
        self.texto = v

    def set_label(self, v: str) -> None:
        self.texto = v

    def set_visible(self, v: bool) -> None:
        self.visivel = bool(v)

    def get_visible(self) -> bool:
        return self.visivel

    def set_sensitive(self, _v: bool) -> None:
        pass

    def set_no_show_all(self, _v: bool) -> None:
        pass

    def set_active(self, _v: bool) -> None:
        pass

    def set_active_id(self, _v: str) -> None:
        pass

    def set_xalign(self, _v: float) -> None:
        pass

    def set_margin_end(self, _v: int) -> None:
        pass

    def get_style_context(self) -> Any:
        return SimpleNamespace(add_class=self.classes.append, remove_class=lambda n: None)

    def pack_start(self, filho: Any, *_a: object) -> None:
        self.filhos.append(filho)

    def get_children(self) -> list[Any]:
        return list(self.filhos)

    def remove(self, filho: Any) -> None:
        self.filhos.remove(filho)

    def show_all(self) -> None:
        pass


class _HomeStub:
    _render_home = HomeActionsMixin._render_home
    _render_home_controllers = HomeActionsMixin._render_home_controllers
    _render_ponte_e_divergencia = HomeActionsMixin._render_ponte_e_divergencia
    _mascara_escolhida_por_ela = HomeActionsMixin._mascara_escolhida_por_ela
    _mascara_escolhida_com_fonte = HomeActionsMixin._mascara_escolhida_com_fonte

    def __init__(self) -> None:
        self._home_installed = True
        self._home_guard = False
        self._home_inflight = False
        self._home_flavor_pedido: str | None = None
        self._escolha_pendente: dict[str, str] | None = None
        self._modo_vigente_do_daemon: str | None = None
        self._mascara_vigente_do_daemon: str | None = None
        for nome in (
            "_home_mode_selector",
            "_home_flavor_selector",
            "_home_mode_desc",
            "_home_origin_label",
            "_home_session_label",
            "_home_players_hint",
            "_home_gamepad_opts",
            "_home_controllers_box",
            "_home_vpad_banner",
            "_home_wrapper_banner",
            "_home_shutdown_btn",
            "_home_reconciliar_btn",
            "_home_reconciliar_hint",
            "_home_ponte_label",
            "_home_divergencia_banner",
        ):
            setattr(self, nome, _Widget())
        self._home_offline = False

    def _status_toast(self, _c: str, _m: str) -> None:
        pass


@pytest.fixture()
def fake_gtk(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = types.ModuleType("gi.repository")
    repo.Gtk = SimpleNamespace(  # type: ignore[attr-defined]
        Label=_Widget,
        Box=_Widget,
        Orientation=SimpleNamespace(VERTICAL=0, HORIZONTAL=1),
    )
    monkeypatch.setitem(sys.modules, "gi.repository", repo)


def _dois_dualsense() -> list[dict[str, Any]]:
    return [
        {
            "index": 0,
            "connected": True,
            "transport": "usb",
            "is_primary": True,
            "player": 1,
            "player_slot": 1,
        },
        {
            "index": 1,
            "connected": True,
            "transport": "bt",
            "is_primary": False,
            "player": 2,
            "player_slot": 2,
        },
    ]


def _estado_da_mesa_mista() -> dict[str, Any]:
    return {
        "connected": True,
        "native_mode": False,
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense", "backend": "uhid"},
        "controllers": _dois_dualsense(),
        "external": [_um_externo()],
    }


def _textos_dos_cards(host: _HomeStub) -> list[str]:
    return [
        str(filho.texto)
        for card in host._home_controllers_box.get_children()
        for filho in ([card, *card.get_children()])
        if getattr(filho, "texto", "")
    ]


# ----------------------------------------------------------------------
# I5 — a conta da mesa
# ----------------------------------------------------------------------


class TestAContaDaMesaContaQuemEstaNaMesa:
    def test_dois_dualsense_e_um_externo_nao_dizem_dois_controles(self) -> None:
        """A MORDIDA da I5, primeira metade do §5.

        Arranque o ramo dos externos em `_format_players_hint` e a frase volta
        a ser "2 controles = 2 jogadores" com três aparelhos na mesa.
        """
        frase = home_actions._format_players_hint(
            _dois_dualsense(), [_um_externo()]
        )

        assert "2 controles" not in frase, (
            f"a primeira tela continua contando só quem ela adotou: {frase!r}"
        )
        assert frase.startswith("3 controles")

    def test_a_frase_nao_promete_que_o_externo_e_um_jogador(self) -> None:
        """O §6 da sprint proíbe, e a proibição tem lastro no mapa de canais.

        ``plataforma.vpad@sn30`` está em ``existe: desconhecido`` — ninguém
        mediu se um externo por rádio entra na conta de jogadores. A frase diz
        quantos estão na mesa e quais o Hefesto adotou; nunca que o 8BitDo é o
        jogador 3.
        """
        frase = home_actions._format_players_hint(
            _dois_dualsense(), [_um_externo()]
        )

        assert "3 jogadores" not in frase
        assert "só vê" in frase

    def test_sem_externo_a_frase_antiga_fica_inteira(self) -> None:
        """A régua sabe dizer NÃO. Mesa só de DualSense não mudou uma vírgula."""
        assert (
            home_actions._format_players_hint(_dois_dualsense())
            == "2 controles = 2 jogadores"
        )

    def test_o_frame_desenha_tres_cards(self, fake_gtk: None) -> None:
        """A MORDIDA da I5, segunda metade do §5: 2 DualSense + 1 externo = 3.

        Arranque a leitura de `external` (`externos_na_mesa`) e o frame volta a
        ter dois cards com três aparelhos na mesa.
        """
        host = _HomeStub()

        host._render_home(_estado_da_mesa_mista())

        cards = host._home_controllers_box.get_children()
        assert len(cards) == 3, (
            f"o frame Controles desenhou {len(cards)} cards para uma mesa de "
            "três. A aba Configurações mostra os três desde a 8BIT-01."
        )

    def test_o_card_do_externo_diz_a_marca_e_que_o_hefesto_so_ve(
        self, fake_gtk: None
    ) -> None:
        """O que a pessoa procura ao ver um controle que não acende."""
        host = _HomeStub()

        host._render_home(_estado_da_mesa_mista())

        textos = " | ".join(_textos_dos_cards(host))
        assert "só vê" in textos
        assert "Controle" in textos

    def test_um_externo_sozinho_tira_a_aba_do_nenhum_controle(
        self, fake_gtk: None
    ) -> None:
        """Só o 8BitDo na mesa deixou de ser "Nenhum controle conectado.".

        É a metade mais enganosa do defeito: com um controle ligado e aceso, a
        primeira tela dizia que não havia nenhum.
        """
        host = _HomeStub()
        estado = _estado_da_mesa_mista()
        estado["controllers"] = []

        host._render_home(estado)

        textos = _textos_dos_cards(host)
        assert "Nenhum controle conectado." not in textos
        assert len(host._home_controllers_box.get_children()) == 1

    def test_o_payload_manda_e_o_cache_e_o_degrau_de_tras(self) -> None:
        """`state_full` NÃO publica `external` hoje — medido por leitura.

        Quem responde é o `controller.list {"external": true}`, guardado no
        tique lento. O ramo do payload existe para o dublê da foto e para um
        daemon mais novo; a ordem é a que faz os dois caminhos conviverem sem
        um segundo dono.
        """
        do_payload = [{"name": "do payload"}]
        do_cache = [{"name": "do cache"}]

        assert home_actions.externos_na_mesa({"external": do_payload}, do_cache) == (
            do_payload
        )
        assert home_actions.externos_na_mesa({}, do_cache) == do_cache
        assert home_actions.externos_na_mesa(None, do_cache) == do_cache
        assert home_actions.externos_na_mesa({"external": None}, ()) == []

    def test_o_state_full_de_hoje_nao_publica_external(self) -> None:
        """A hipótese 3 do §2.5, RESOLVIDA — e por isso vira teste.

        Ela dizia: *"que o daemon publica `external` quando há um externo na
        mesa. Aqui ele veio `null` com a mesa vazia, o que não distingue 'não
        há' de 'não publica'."* Distingue agora, por leitura de código: o
        handler do `state_full` nunca escreve essa chave — quem a escreve é o
        `controller.list`, e só sob `{"external": true}`.

        Este teste é o que impede a próxima pessoa de refazer a medição. Se
        alguma onda passar a publicar `external` no `state_full`, ele reprova e
        o IPC extra desta aba pode sair.
        """
        fonte = (
            RAIZ / "src/hefesto_dualsense4unix/daemon/ipc_handlers.py"
        ).read_text(encoding="utf-8")
        inicio = fonte.index("async def _handle_daemon_state_full")
        fim = fonte.index("async def ", inicio + 10)
        corpo = fonte[inicio:fim]

        assert 'result["external"]' not in corpo, (
            "o `state_full` passou a publicar `external`. Se for de propósito, "
            "o `_maybe_fetch_externos` da aba Início pode sair — e este teste "
            "com ele."
        )


# ----------------------------------------------------------------------
# I9 — a língua do mapa de canais
# ----------------------------------------------------------------------

#: O que o mapa de canais fala. É o PORTÃO
#: (`scripts/check_paridade_transporte.py` cruza CSV, testes e specs), e por
#: isso é ele quem manda no vocabulário — não a tela.
_LINGUA_DO_MAPA = ("cabo", "rádio")


class TestOCardFalaALinguaDoMapa:
    def test_o_mapa_de_canais_fala_cabo_e_radio(self) -> None:
        """A premissa: o dono do vocabulário é o CSV, e ele diz isto.

        Sem esta conferência a normalização abaixo seria uma preferência de
        quem escreveu, e não a língua da casa.
        """
        csv = (RAIZ / "docs/data/mapa-controles.csv").read_text(encoding="utf-8")
        for palavra in _LINGUA_DO_MAPA:
            assert palavra in csv, (
                f"o mapa de canais não fala {palavra!r} — a régua desta seção "
                "perdeu o chão"
            )

    def test_usb_vira_cabo_e_bt_vira_radio(self) -> None:
        """A MORDIDA da I9. Arranque o mapa e o card volta a dizer `USB`/`BT`."""
        assert home_actions.palavra_do_transporte("usb") == "cabo"
        assert home_actions.palavra_do_transporte("USB") == "cabo"
        assert home_actions.palavra_do_transporte("bt") == "rádio"
        assert home_actions.palavra_do_transporte("bluetooth") == "rádio"

    def test_transporte_desconhecido_aparece_cru_em_vez_de_sumir(self) -> None:
        """Um transporte novo tem de chegar aos olhos de alguém.

        Escondê-lo atrás de "não sei" faria um daemon mais novo passar
        despercebido — e a tela mentiria por omissão, que é o defeito de forma
        desta onda inteira.
        """
        assert home_actions.palavra_do_transporte("thunderbolt") == "thunderbolt"

    def test_ausencia_de_transporte_nao_vira_interrogacao(self) -> None:
        """`"?"` é a tela encolhendo os ombros. Ela tem de dizer o que não sabe."""
        assert (
            home_actions.palavra_do_transporte(None)
            == home_actions.PALAVRA_DE_TRANSPORTE_DESCONHECIDO
        )
        assert "?" not in home_actions.palavra_do_transporte(None)

    def test_o_card_do_adotado_e_o_do_externo_falam_igual(
        self, fake_gtk: None
    ) -> None:
        """Dois dialetos lado a lado no MESMO frame seria o defeito de novo."""
        host = _HomeStub()

        host._render_home(_estado_da_mesa_mista())

        textos = " | ".join(_textos_dos_cards(host))
        assert "USB" not in textos
        assert "Bluetooth" not in textos
        assert "cabo" in textos
        assert "rádio" in textos

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "as outras três superfícies são de outros donos nesta leva: "
            "`external_controllers.transport_label` (Cabo (USB)/Bluetooth), "
            "`config/secao_mesa.py` (Rádio em uso) e a aba Status. MEDIDO em "
            "24/08/2026, §2.2h da sprint. Quando as três falarem a língua do "
            "mapa este teste PASSA e o strict reprova — que é o gatilho para "
            "apagar o xfail."
        ),
    )
    def test_as_quatro_superficies_dizem_as_mesmas_palavras(self) -> None:
        """O contrato inteiro da I9: um vocabulário só, o do mapa.

        Enquanto reprovar, a janela continua dizendo o mesmo fato com quatro
        conjuntos de palavras — e quem lê conclui que são quatro fatos.
        """
        from hefesto_dualsense4unix.app.actions.external_controllers import (
            transport_label,
        )

        dialetos = {
            "Início": {
                home_actions.palavra_do_transporte("usb"),
                home_actions.palavra_do_transporte("bt"),
            },
            "externos": {
                transport_label({"bus": "usb"}),
                transport_label({"bus": "bluetooth"}),
            },
        }
        assert dialetos["Início"] == dialetos["externos"], dialetos
