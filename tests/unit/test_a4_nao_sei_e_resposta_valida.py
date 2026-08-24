"""A4 — "não sei" continua existindo DEPOIS do primeiro clique.

A ``D-A1`` (``docs/process/sprints/2026-08-21-ABA-CONFIGURACOES/DECISOES-ABERTAS.md``)
diz duas coisas: *"toda declaração nasce em 'não sei'"* e *"'não sei' é resposta
válida"*. Até 23/08/2026 só a primeira metade existia. O ``SegmentedSelector`` é
grupo de rádio e IGNORA o clique no botão já afundado
(``segmented_selector.py``, ``_on_button_toggled``), e não havia gesto de limpar
em lugar nenhum da aba: quem declarasse "Economia", "Xbox" ou "Vermelho" por
engano ficava preso àquilo para sempre.

Esta bateria cobre os TRÊS campos que ganharam o botão "Não sei", e cobre cada
um **até o disco** — não basta o widget mudar de cara. A declaração que sai do
gesto é a que vai para o ``maquina.json``, e o que se afirma é que o campo
voltou a ``None`` lá dentro.

Os outros dois campos apontados no achado NÃO estão aqui, e a ausência é
deliberada:

* **Jogador 1..5** — não existe "desafixado" para onde voltar: o
  ``identity.number.set`` recusa ``number < 1`` e o daemon PERMUTA em vez de
  fixar. É decisão dela (verbo IPC novo, ou reescrever a dica), não conserto.
* **Ambiente** — o que não volta é a AUSÊNCIA de correção, e mora em
  ``app/ambiente.py``.

AS MORDIDAS, arrancadas e conferidas em 23/08/2026
---------------------------------------------------

Uma por campo, e todas a mesma: tirar o item ``("nao_sei", "Não sei")`` da lista
do seletor. ``set_active_id`` de um id inexistente é NO-OP (não emite "changed"),
então o gesto some sem erro nenhum e o valor antigo sobrevive ao disco — que é
exatamente o defeito que o achado descreve.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: os três campos são widgets de verdade, e "pulei porque não
# tenho GTK" é reprovação no job `gtk-real`.
exigir_gi_real("os seletores de declaração da aba Configurações")

from pathlib import Path
from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_orcamento
from hefesto_dualsense4unix.app.actions.external_controllers import (
    ID_DE_NAO_SEI,
    cores_do_plastico_items,
)
from hefesto_dualsense4unix.app.widgets.external_card import (
    BOTOES_DO_APARELHO,
    DadosDoControle,
    ExternalCard,
)
from hefesto_dualsense4unix.utils.maquina import (
    caminho_da_maquina,
    carregar_maquina,
    gravar_maquina,
)

#: O endereço deste controle de bancada, com a máscara da casa (octetos 4 e 5
#: zerados) e na forma que vai ao disco: doze hexa minúsculos, sem separador.
ENDERECO = "aabbcc0000d8"


@pytest.fixture
def arquivo(tmp_path: Path) -> Path:
    """O ``maquina.json`` desta bancada — e a prova de que ele não é o dela.

    CANÁRIO, no molde de ``test_maquina_a_declaracao_persiste.py``: se algum dia
    o módulo resolver ``config_dir`` no topo, o caminho deixa de cair no
    ``tmp_path`` e esta asserção é a única coisa entre a suíte e o ``~/.config``
    da mantenedora.
    """
    caminho = caminho_da_maquina()
    assert tmp_path in caminho.parents, f"{caminho} escapou do tmp da bancada"
    return caminho


# ---------------------------------------------------------------------------
# Orçamento
# ---------------------------------------------------------------------------


class _HostDoOrcamento:
    """O mínimo que a seção Orçamento toca no hospedeiro."""

    def __init__(self, gravado: str | None) -> None:
        self._maquina_pendente: dict[str, Any] | None = None
        self._orcamento_lido = lambda: gravado
        #: PENDURADA no hospedeiro de propósito: solta numa local, a caixa é
        #: coletada ao fim do `_montar`, o GTK destrói os filhos junto e o
        #: seletor para de emitir "changed" — o teste falharia sem uma linha de
        #: erro, com o rascunho vazio.
        self._caixa: Any = None

    def _get(self, _ident: str) -> Any:
        return None


def test_o_orcamento_declarado_volta_a_nao_sei_e_o_disco_esvazia(
    arquivo: Path,
) -> None:
    """MORDIDA 1. Declarou "Economia" por engano; "Não sei" desfaz até o disco."""
    assert gravar_maquina({"orcamento": {"teto": "economia"}})
    assert carregar_maquina().orcamento.teto == "economia"

    host = _HostDoOrcamento("economia")
    host._caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    secao_orcamento.montar(host, host._caixa)

    seletor = host._config_orcamento_seletor  # type: ignore[attr-defined]
    assert seletor.get_active_id() == "economia", "a montagem não marcou o gravado"
    seletor.set_active_id(secao_orcamento.ID_DE_NAO_SEI)

    assert host._maquina_pendente == {"orcamento": {"teto": None}}, (
        "o clique em 'Não sei' tem de acumular `None` EXPLÍCITO: a ausência da "
        "chave preservaria a escolha antiga na fusão"
    )
    assert gravar_maquina(host._maquina_pendente or {})
    assert carregar_maquina().orcamento.teto is None


def test_nao_sei_nao_entra_nas_chaves_do_schema() -> None:
    """O botão é palavra de TELA; em `CHAVES` o `Literal` recusaria o documento."""
    assert secao_orcamento.ID_DE_NAO_SEI not in secao_orcamento.CHAVES


# ---------------------------------------------------------------------------
# Os dois campos do card
# ---------------------------------------------------------------------------


def _dados(**extra: Any) -> DadosDoControle:
    return DadosDoControle(
        chave="bancada",
        titulo="Jogador 2",
        subtitulo="8BitDo · Bluetooth",
        uniq="aa:bb:cc:00:00:d8",
        endereco=ENDERECO,
        **extra,
    )


def _seletores(widget: Any) -> list[Any]:
    """Todo `SegmentedSelector` do card, em profundidade."""
    achados: list[Any] = []
    if hasattr(widget, "_items") and hasattr(widget, "set_active_id"):
        achados.append(widget)
    if hasattr(widget, "get_children"):
        for filho in widget.get_children():
            achados.extend(_seletores(filho))
    return achados


def _seletor_com(card: Any, ident: str) -> Any:
    """O seletor do card que oferece `ident` — e só pode haver um."""
    candidatos = [
        sel for sel in _seletores(card) if ident in [i for i, _r in sel._items]
    ]
    assert len(candidatos) == 1, (
        f"esperava UM seletor oferecendo {ident!r}, achei {len(candidatos)}"
    )
    return candidatos[0]


def test_os_botoes_declarados_voltam_a_nao_sei_e_o_disco_esvazia(
    arquivo: Path,
) -> None:
    """MORDIDA 2. "Xbox" clicado por engano deixa de ser sentença perpétua."""
    assert gravar_maquina(
        {"controles": {ENDERECO: {"botoes": "xbox", "cor": "Cosmic Red"}}}
    )

    saida: list[tuple[str, str, str | None]] = []
    card = ExternalCard(
        _dados(botoes="xbox"),
        ao_declarar=lambda chave, campo, valor: saida.append((chave, campo, valor)),
    )
    seletor = _seletor_com(card, "nintendo")
    assert seletor.get_active_id() == "xbox", "a montagem não marcou o declarado"
    seletor.set_active_id(ID_DE_NAO_SEI)

    assert saida == [("bancada", "botoes", None)], (
        "o gesto tem de declarar `None`, e não a string 'nao_sei' — o `Literal` "
        "de `ControleDeclarado.botoes` recusaria o documento inteiro"
    )
    _, campo, valor = saida[-1]
    assert gravar_maquina({"controles": {ENDERECO: {campo: valor}}})

    declarado = carregar_maquina().controles[ENDERECO]
    assert declarado.botoes is None
    assert declarado.cor == "Cosmic Red", "apagar um campo não apaga o vizinho"


def test_a_cor_declarada_volta_a_nao_sei_e_o_disco_esvazia(arquivo: Path) -> None:
    """MORDIDA 3. E o campo livre some junto — "Outra" vazia era tela mentindo."""
    assert gravar_maquina(
        {"controles": {ENDERECO: {"cor": "Cosmic Red", "botoes": "xbox"}}}
    )

    saida: list[tuple[str, str, str | None]] = []
    card = ExternalCard(
        _dados(cor_id="02", botoes="xbox"),
        ao_declarar=lambda chave, campo, valor: saida.append((chave, campo, valor)),
    )
    seletor = _seletor_com(card, "00")
    assert seletor.get_active_id() == "02", "a montagem não marcou a cor declarada"
    seletor.set_active_id(ID_DE_NAO_SEI)

    assert saida == [("bancada", "cor", None)]
    assert not card._campo_livre.get_visible(), (
        "'Não sei' não pode deixar o campo livre aberto: um campo aberto e vazio "
        "é a tela pedindo o que ela acabou de dizer que não sabe"
    )
    _, campo, valor = saida[-1]
    assert gravar_maquina({"controles": {ENDERECO: {campo: valor}}})

    declarado = carregar_maquina().controles[ENDERECO]
    assert declarado.cor is None
    assert declarado.botoes == "xbox", "apagar um campo não apaga o vizinho"


def test_os_tres_seletores_oferecem_o_mesmo_botao() -> None:
    """Uma palavra só na tela inteira: "Não sei", com o mesmo id nos três."""
    assert cores_do_plastico_items()[-1] == (ID_DE_NAO_SEI, "Não sei")
    assert BOTOES_DO_APARELHO[-1] == (ID_DE_NAO_SEI, "Não sei")
    assert secao_orcamento.ID_DE_NAO_SEI == ID_DE_NAO_SEI
    assert secao_orcamento.ROTULO_DE_NAO_SEI == "Não sei"
