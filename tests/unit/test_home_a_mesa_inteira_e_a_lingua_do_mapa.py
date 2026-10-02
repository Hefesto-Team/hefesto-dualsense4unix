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
* **o texto do aviso de grab** estava bloqueado por aqui e **nasceu em
  25/08/2026**, quando a ``ESCONDE-SÓ-O-HIDRAW-01`` fechou e mediu o que o jogo
  continua vendo: o `hide` age em UMA superfície (`hidraw`) e o mesmo controle
  mora em TRÊS — `event*` e `js*` seguem alcançáveis. O `EVIOCGRAB` é o que
  impede o físico de produzir entrada nelas, então com ele recusado a
  duplicação não é hipótese, é o que sobra. Ver `TestOAvisoDeGrabFalaComEla`
  abaixo;
* **a palavra "primário"** no subtítulo do card continua. É o outro jargão que
  a I9 nomeia, e trocá-la é decisão DELA: o card já mostra o número do jogador,
  então qualquer substituto ou repete o que está ali ou inventa um conceito
  novo na primeira tela.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_home_a_mesa_inteira_e_a_lingua_do_mapa: importa código da janela GTK")

import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import home_actions

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_EXTERNOS = RAIZ / "tests" / "fixtures" / "inventario_externos.json"

def _um_externo() -> dict[str, Any]:
    bruto = json.loads(FIXTURE_EXTERNOS.read_text(encoding="utf-8"))
    return dict(bruto["external"][0])


class _Widget:
    def __init__(self, label: str | None = None, **_kw: Any) -> None:
        self.texto = label or ""
        self.visivel = True
        self.filhos: list[Any] = []
        self.classes: list[str] = []
        self.dica: str | None = None

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

    def set_tooltip_text(self, v: str) -> None:
        self.dica = v

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


class TestAContaDaMesaContaQuemEstaNaMesa:


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


#: *"Melhor que cabo e bt"*. <!-- noqa-acento: citação literal dela -->
_LINGUA_DO_MAPA = ("cabo", "rádio")


class TestOCardFalaALinguaDoMapa:
    def test_o_mapa_de_canais_fala_cabo_e_radio(self) -> None:
        """A premissa: o dono do vocabulário é o CSV, e ele diz isto."""
        csv = (RAIZ / "docs/data/mapa-controles.csv").read_text(encoding="utf-8")
        for palavra in _LINGUA_DO_MAPA:
            assert palavra in csv, (
                f"o mapa de canais não fala {palavra!r} — a régua desta seção "
                "perdeu o chão"
            )

    def test_o_dicionario_normaliza_os_seis_crus_em_duas_palavras(self) -> None:
        """A MORDIDA do dono: seis grafias entram, DUAS palavras saem."""
        assert home_actions.palavra_do_transporte("usb") == "USB"
        assert home_actions.palavra_do_transporte("USB") == "USB"
        assert home_actions.palavra_do_transporte("cabo") == "USB"
        assert home_actions.palavra_do_transporte("bt") == "BT"
        assert home_actions.palavra_do_transporte("bluetooth") == "BT"
        assert home_actions.palavra_do_transporte("rádio") == "BT"

    def test_transporte_desconhecido_aparece_cru_em_vez_de_sumir(self) -> None:
        """Um transporte novo tem de chegar aos olhos de alguém."""
        assert home_actions.palavra_do_transporte("thunderbolt") == "thunderbolt"

    def test_ausencia_de_transporte_nao_vira_interrogacao(self) -> None:
        """`"?"` é a tela encolhendo os ombros. Ela tem de dizer o que não sabe."""
        assert (
            home_actions.palavra_do_transporte(None)
            == home_actions.PALAVRA_DE_TRANSPORTE_DESCONHECIDO
        )
        assert "?" not in home_actions.palavra_do_transporte(None)


class TestOAvisoDeGrabFalaComEla:
    """25/08/2026 — a metade da I9 que a ``ESCONDE-SÓ-O-HIDRAW-01`` destravou."""

    def test_a_linha_nao_fala_a_lingua_do_kernel(self) -> None:
        """A MORDIDA: devolva o texto antigo e este teste reprova."""
        linha, _porque = home_actions.aviso_de_grab(
            "failed", is_primary=True, gamepad_on=True
        )

        for jargao in ("grab", "input", "eviocgrab", "evdev", "hidraw"):
            assert jargao not in linha.lower(), (
                f"a linha do card voltou a dizer {jargao!r}. É o nome da peça "
                "do sistema que falhou — e o card é a primeira tela de quem "
                f"quer jogar: {linha!r}"
            )
        assert "duas vezes" in linha

    def test_o_porque_diz_o_que_fazer_e_nao_acusa_ninguem(self) -> None:
        """Diagnóstico desta casa diz o quê, por quê e o que fazer."""
        _linha, porque = home_actions.aviso_de_grab(
            "failed", is_primary=True, gamepad_on=True
        )

        assert "ao mesmo tempo" in porque, "o porquê não diz o que acontece"
        assert "2 segundos" in porque, "o porquê não diz que o Hefesto insiste"
        assert "feche" in porque.lower(), "o porquê não diz o que fazer"
        assert "Steam" not in porque, (
            "o aviso passou a acusar a Steam, que a GRAB-DOBRADO-01 registra "
            "como candidata SEM PROVA (§2)"
        )

    def test_so_acende_no_primario_com_gamepad_de_pe_e_recusa(self) -> None:
        """A condição é a que já estava certa — e agora é testável sem GTK."""
        assert home_actions.aviso_de_grab(
            "failed", is_primary=True, gamepad_on=True
        ) is not None
        for estado in ("held", "pending", "off", None, ""):
            assert (
                home_actions.aviso_de_grab(
                    estado, is_primary=True, gamepad_on=True
                )
                is None
            ), f"o aviso acendeu com grab_state={estado!r}"
        assert (
            home_actions.aviso_de_grab("failed", is_primary=False, gamepad_on=True)
            is None
        )
        assert (
            home_actions.aviso_de_grab("failed", is_primary=True, gamepad_on=False)
            is None
        )

