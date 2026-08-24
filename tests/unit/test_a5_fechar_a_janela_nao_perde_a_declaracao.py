"""A5 (23/08/2026) — fechar a janela não joga fora o que ela declarou.

O DEFEITO, medido: a aba Configurações é DIFERIDA (o clique acumula em
`_maquina_pendente`, só o "Aplicar" grava) e NENHUM dos dois ramos de
`on_window_delete_event` olhava para isso. Encerrar descartava a declaração em
silêncio. O que salvava o caso comum nesta máquina era acidente de ambiente —
a bandeja do COSMIC viva faz o X esconder em vez de sair —, não cura.

O portão vale SÓ no ramo que ENCERRA: no da bandeja o rascunho sobrevive, e ali
cabe no máximo a marca na linha do rodapé.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("a5 fechar a janela e a declaracao pendente")

from typing import Any

import pytest

from gi.repository import Gtk

from hefesto_dualsense4unix.app import app as app_module
from hefesto_dualsense4unix.app.app import HefestoApp


DECLARACAO = {"orcamento": {"teto": "equilibrado"}}


class _Espia:
    """Responde pelo diálogo e guarda o que ele oferecia."""

    def __init__(self, resposta: int) -> None:
        self.resposta = resposta
        self.chamadas: list[str] = []
        self.botoes: list[str] = []
        self.default: int | None = None

    def __call__(self, dialog: Any, *, nome: str, **_kw: Any) -> int:
        self.chamadas.append(nome)
        self.botoes = [
            b.get_label() for b in dialog.get_action_area().get_children()
        ]
        self.default = self._default_de(dialog)
        return self.resposta

    @staticmethod
    def _default_de(dialog: Any) -> int | None:
        for botao in dialog.get_action_area().get_children():
            if botao.get_can_default() and botao.has_default():
                return int(dialog.get_response_for_widget(botao))
        return None


def _janela(
    monkeypatch: pytest.MonkeyPatch,
    *,
    pendente: dict[str, Any] | None,
    bandeja: bool,
    resposta: int = Gtk.ResponseType.CANCEL,
    recusa: str | None = None,
) -> tuple[HefestoApp, _Espia, list[str]]:
    """`HefestoApp` sem `__init__` — só os atributos que o fechamento toca."""
    janela = HefestoApp.__new__(HefestoApp)
    janela._quitting = False
    janela.window = Gtk.Window()
    janela._maquina_pendente = pendente
    janela.barra = Gtk.Statusbar()
    monkeypatch.setattr(
        HefestoApp, "_has_persistent_access", lambda _self: bandeja
    )
    monkeypatch.setattr(HefestoApp, "_get", lambda _self, _wid: None)

    gravou: list[str] = []

    def _gravar(_self: object) -> str | None:
        """O contrato real: `None` no sucesso, a FRASE do motivo no fracasso.

        O dublê anterior devolvia sempre `None` (o retorno de `list.append`), e
        por isso o teste não conseguia enxergar o caminho da recusa — que é
        exatamente onde o defeito estava. Régua que só sabe passar não é régua.
        """
        gravou.append("gravou")
        return recusa

    monkeypatch.setattr(HefestoApp, "_gravar_declaracao_de_maquina", _gravar)
    monkeypatch.setattr(app_module.Gtk, "main_quit", lambda: gravou.append("quit"))

    espia = _Espia(resposta)
    monkeypatch.setattr(app_module, "executar_dialogo", espia)
    return janela, espia, gravou


class TestOPortaoDoFechamento:
    def test_cancelar_impede_o_encerramento(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDE: sem a guarda o delete-event ia direto ao `Gtk.main_quit`."""
        janela, espia, feito = _janela(
            monkeypatch,
            pendente=dict(DECLARACAO),
            bandeja=False,
            resposta=Gtk.ResponseType.CANCEL,
        )
        cancelou = janela.on_window_delete_event(None, None)

        assert espia.chamadas == ["declaracao_pendente_ao_fechar"], (
            "o diálogo tem de aparecer com declaração de pé"
        )
        assert cancelou is True, "'Cancelar' tem de cancelar o destroy"
        assert "quit" not in feito
        assert janela._maquina_pendente == DECLARACAO

    def test_aplicar_e_fechar_grava_antes_de_sair(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        janela, _espia, feito = _janela(
            monkeypatch,
            pendente=dict(DECLARACAO),
            bandeja=False,
            resposta=Gtk.ResponseType.OK,
        )
        assert janela.on_window_delete_event(None, None) is False
        assert feito == ["gravou", "quit"], feito

    def test_fechar_sem_aplicar_sai_sem_gravar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        janela, _espia, feito = _janela(
            monkeypatch,
            pendente=dict(DECLARACAO),
            bandeja=False,
            resposta=Gtk.ResponseType.CLOSE,
        )
        assert janela.on_window_delete_event(None, None) is False
        assert feito == ["quit"], feito

    def test_o_default_e_cancelar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Um Enter distraído nunca pode custar edição não salva."""
        janela, espia, _feito = _janela(
            monkeypatch, pendente=dict(DECLARACAO), bandeja=False
        )
        janela.on_window_delete_event(None, None)
        assert espia.default == Gtk.ResponseType.CANCEL
        assert len(espia.botoes) == 3, espia.botoes


class TestOsCaminhosQueJaFuncionavam:
    def test_sem_declaracao_o_fechamento_sai_direto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        janela, espia, feito = _janela(monkeypatch, pendente=None, bandeja=False)
        assert janela.on_window_delete_event(None, None) is False
        assert espia.chamadas == [], "sem pendência não se pergunta nada"
        assert feito == ["quit"]

    def test_ramo_da_bandeja_esconde_e_nao_pergunta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Na bandeja o rascunho sobrevive — diálogo ali seria ruído."""
        janela, espia, feito = _janela(
            monkeypatch, pendente=dict(DECLARACAO), bandeja=True
        )
        assert janela.on_window_delete_event(None, None) is True
        assert espia.chamadas == []
        assert feito == []
        assert janela._maquina_pendente == DECLARACAO

    def test_quitting_continua_passando_reto(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        janela, espia, feito = _janela(
            monkeypatch, pendente=dict(DECLARACAO), bandeja=False
        )
        janela._quitting = True
        assert janela.on_window_delete_event(None, None) is False
        assert espia.chamadas == []
        assert feito == []


class TestARecusaSeguraAJanela:
    """A cura do A5 reintroduzia o A5 quando o Hefesto estava desligado.

    Achado da conferência de 23/08/2026, e ele é do tipo mais caro: o conserto
    parecia certo, o teste passava, e o defeito estava de volta no caminho que o
    próprio conserto construiu. Com o daemon fora do ar a gravação RECUSA, e
    "Aplicar e fechar" ficava idêntico a "Fechar sem aplicar" — a declaração
    morria com o processo, sem uma palavra.

    O teste antigo não pegava porque o dublê de `_gravar_declaracao_de_maquina`
    devolvia sempre `None`: ele só sabia ter sucesso.
    """

    def test_recusa_da_gravacao_impede_o_encerramento(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDE: sem checar o retorno, a janela encerra e a declaração morre."""
        janela, _espia, feito = _janela(
            monkeypatch,
            pendente=dict(DECLARACAO),
            bandeja=False,
            resposta=Gtk.ResponseType.OK,
            recusa="O Hefesto está desligado — não gravei o que você declarou",
        )

        segurou = janela.on_window_delete_event(None, None)

        assert "gravou" in feito, "instrumento inválido: nem tentou gravar"
        assert "quit" not in feito, (
            "a janela ENCERROU mesmo com a gravação recusada: a declaração "
            f"{DECLARACAO} morreria com o processo — que é o defeito A5 de volta"
        )
        assert segurou is True, (
            "o delete-event tem de devolver True para cancelar o destroy"
        )

    def test_sucesso_deixa_encerrar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O caminho feliz não pode ter sido estragado pela guarda nova."""
        janela, _espia, feito = _janela(
            monkeypatch,
            pendente=dict(DECLARACAO),
            bandeja=False,
            resposta=Gtk.ResponseType.OK,
            recusa=None,
        )

        janela.on_window_delete_event(None, None)

        assert feito == ["gravou", "quit"], (
            "com a gravação aceita, 'Aplicar e fechar' tem de gravar E fechar; "
            f"saiu {feito}"
        )
