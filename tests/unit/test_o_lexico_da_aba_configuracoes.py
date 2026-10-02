"""O portão do LÉXICO da aba Configurações — a régua da leva CONFIGURAÇÕES-O-LÉXICO-01."""
from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any

from tests.conftest import exigir_gi_real

exigir_gi_real("o léxico da aba Configurações")

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.config import secao_janela
from hefesto_dualsense4unix.app.actions.config.secoes import SECOES_DA_ABA

RAIZ = Path(__file__).resolve().parents[2]
FONTE = RAIZ / "src" / "hefesto_dualsense4unix" / "app"


_TAMANHO_DE_PARAGRAFO = 60

PARAGRAFOS_QUE_FICAM: dict[str, str] = {
    "Nenhum controle ligado agora.": (
        "seção VAZIA: só existe quando não há controle nenhum, logo é o próprio "
        "estado dos controles. `secao_controles`. A frase dizia `na mesa` até "
        "05/09/2026, quando ela mandou tirar a palavra da interface."
    ),
    "Não sei quem está no rádio": (
        "estado do daemon: só aparece quando ele não respondeu. `secao_orcamento`."
    ),
    "Você ainda não mapeou as suas entradas.": (
        "estado da declaração dela: some no instante em que o mapa é desenhado. "
        "`secao_mesa`. A frase dizia `Você ainda não desenhou a sua mesa.` até "
        "05/09/2026, e a razão escrita aqui era que a palavra FICAVA — por ser "
        "a mesa FÍSICA, a escrivaninha e as entradas USB. **Ela derrubou esse "
        "juízo no mesmo dia**: *\"muda o termo pra objeto e sinônimos nesses "
        "casos\"*. O verbo acompanhou o botão ao lado, que é o \"o que fazer\" "
        "desta frase e passou a chamar-se `Mapear Entradas`."
    ),
    "A sessão não diz qual é o ambiente.": (
        "estado da SESSÃO: `app/ambiente.frase_do_detectado` só a escreve quando "
        "a sessão não declara ambiente nenhum; com um declarado, a linha é o "
        "curto «Detectado: …». Numa sessão gráfica ela nunca aparece, e por isso "
        "a régua só a viu no job `gtk-real` do CI, que roda sem sessão "
        "(corrida 36119169814, 25/09/2026)."
    ),
}

AINDA_NA_PAGINA: dict[str, str] = {
    "Com o microfone ligado, um controle no BT troca": (
        "LEX-2, item 2 — `secao_controles.montar`. BLOQUEADO EM 26/08/2026, e a "
        "medição é esta: `test_o_interruptor_do_microfone_na_aba_configuracoes"
        ".py::test_a_frase_aparece_uma_unica_vez_na_secao` (`:445-452`) exige "
        "`_rotulos(caixa).count(frase) == 1`, e o `_rotulos` daquele arquivo "
        "(`:139-151`) colhe SÓ `get_label()` — nunca dica. Mover a frase para o "
        "hover deixa a contagem em zero e reprova. O conserto é o mesmo que a "
        "G9 já fez no `_textos` -> `_falas` de "
        "`test_a_aba_diz_quando_a_escolha_fica_guardada.py`: o coletor passa a "
        "colher `get_tooltip_text()` junto. Aquele arquivo não está na posse "
        "da LEVA-4-A (R-A), então a frente relata em vez de editar.\n"
        "Ela também é a única casa da `QUANDO_VALE` em `secao_controles`: numa "
        "mesa sem controle nenhum, o interruptor que a frase explica não "
        "existe. Quem mover a frase move a dica junto."
    ),
}

NUNCA_MENOS_QUE = 3


def _descer(raiz: Any) -> list[Any]:
    """Todo widget da subárvore, o título de `Gtk.Frame` incluído."""
    achados: list[Any] = []
    pilha = [raiz]
    while pilha:
        widget = pilha.pop()
        achados.append(widget)
        if isinstance(widget, Gtk.Frame):
            rotulo = widget.get_label_widget()
            if rotulo is not None:
                pilha.append(rotulo)
        filhos = getattr(widget, "get_children", None)
        if filhos is not None:
            pilha.extend(filhos())
    return achados


def _paragrafos_de_apoio(raiz: Any) -> list[str]:
    """Os textos que a régua considera parágrafo de apoio."""
    achados: list[str] = []
    for widget in _descer(raiz):
        if not isinstance(widget, Gtk.Label):
            continue
        esmaecido = False
        with contextlib.suppress(Exception):
            esmaecido = widget.get_style_context().has_class("dim-label")
        if not (esmaecido and widget.get_line_wrap()):
            continue
        texto = widget.get_text() or ""
        if len(texto) > _TAMANHO_DE_PARAGRAFO:
            achados.append(texto)
    return achados


def _conhecido(texto: str) -> bool:
    """O texto casa com alguma entrada declarada, por PREFIXO ou por trecho."""
    return any(
        chave in texto
        for chave in (*PARAGRAFOS_QUE_FICAM, *AINDA_NA_PAGINA)
    )


class _HospedeiroVazio:
    """Sem builder, sem mesa, sem daemon — o dublê mínimo de "A janela"."""

    def __init__(self) -> None:
        self.builder = None
        self.interruptor = Gtk.Switch()

    def _get(self, nome: str) -> Any:
        return self.interruptor if nome == "daemon_autostart_switch" else None


def _janela_montada() -> tuple[Any, Any]:
    """`(host, caixa)` com a seção "A janela" montada de verdade."""
    host = _HospedeiroVazio()
    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    secao_janela.montar(host, caixa)
    return host, caixa


POPUPS_PROIBIDOS = frozenset({"ComboBox", "ComboBoxText", "EntryCompletion"})

PASTAS_SEM_POPUP = ("widgets", "actions/config")


def _altura(widget: Any) -> int:
    """A altura pedida pelo widget, medida sob `Gtk.OffscreenWindow`."""
    janela = Gtk.OffscreenWindow()
    janela.add(widget)
    janela.show_all()
    _minima, natural = widget.get_preferred_height()
    janela.remove(widget)
    janela.destroy()
    return int(natural)


def test_o_rodape_nao_perde_o_campo_que_nao_tem_secao() -> None:
    """`mapa` não é `TITULO` de seção nenhuma, e mesmo assim tem rótulo."""
    fundidos = ipc_bridge._rotulos_dos_campos()
    assert fundidos["mapa"] == ipc_bridge._ROTULOS_SEM_SECAO["mapa"]
    assert fundidos["mapa"] != "mapa", (
        "o campo sem seção caiu no nome cru — a fusão perdeu `_ROTULOS_SEM_SECAO`"
    )


RENOMES_DA_LEX_1: dict[str, str] = {
    "A mesa": "Conexões",
    "Orçamento": "Desempenho",
}


def test_as_duas_secoes_renomeadas_dizem_a_palavra_dela() -> None:
    """"A mesa" virou "Conexões" e "Orçamento" virou "Desempenho"."""
    titulos = {
        secao.__name__.rsplit(".", 1)[-1]: secao.TITULO for secao in SECOES_DA_ABA
    }
    velhas = {
        modulo: titulo
        for modulo, titulo in titulos.items()
        if titulo in RENOMES_DA_LEX_1
    }
    assert not velhas, (
        "estas seções voltaram ao nome velho: "
        + ", ".join(
            f"{modulo} diz {titulo!r} e devia dizer "
            f"{RENOMES_DA_LEX_1[titulo]!r}"
            for modulo, titulo in sorted(velhas.items())
        )
    )
    assert titulos["secao_mesa"] == "Conexões"
    assert titulos["secao_orcamento"] == "Desempenho"


JARGAO_DAS_DUAS_PERGUNTAS = ("antena", "visada")

VALORES_QUE_NAO_MUDAM: dict[str, dict[str, str]] = {
    "altura_da_antena": {"Sim": "acima", "Não": "abaixo", "Não sei": "nao_sei"},
    "linha_de_visada": {"Sim": "com_gente", "Não": "livre", "Não sei": "nao_sei"},
}


class _HospedeiroDaMesa:
    """O mínimo que a seção da mesa toca: o rascunho, e nada mais."""

    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None


