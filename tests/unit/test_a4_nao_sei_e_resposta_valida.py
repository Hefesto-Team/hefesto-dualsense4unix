"""A4 — "não sei" continua existindo DEPOIS do primeiro clique."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

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

ENDERECO = "aabbcc0000d8"


@pytest.fixture
def arquivo(tmp_path: Path) -> Path:
    """O ``maquina.json`` desta bancada — e a prova de que ele não é o dela."""
    caminho = caminho_da_maquina()
    assert tmp_path in caminho.parents, f"{caminho} escapou do tmp da bancada"
    return caminho


class _HostDoOrcamento:
    """O mínimo que a seção Orçamento toca no hospedeiro."""

    def __init__(self, gravado: str | None) -> None:
        self._maquina_pendente: dict[str, Any] | None = None
        self._orcamento_lido = lambda: gravado
        self._caixa: Any = None

    def _get(self, _ident: str) -> Any:
        return None


def test_o_orcamento_declarado_volta_a_nao_sei_e_o_disco_esvazia(
    arquivo: Path,
) -> None:
    """MORDIDA 1. Declarou "Bateria longa" por engano; um clique desfaz até o disco."""
    assert gravar_maquina({"orcamento": {"teto": "economia"}})
    assert carregar_maquina().orcamento.teto == "economia"

    host = _HostDoOrcamento("economia")
    host._caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    secao_orcamento.montar(host, host._caixa)

    seletor = host._config_orcamento_seletor  # type: ignore[attr-defined]
    assert seletor.get_active_id() == secao_orcamento.PERFIL_BATERIA_LONGA, (
        "a montagem não migrou o `economia` gravado para o perfil dele"
    )
    seletor.set_active_id(secao_orcamento.PERFIL_EU_ESCOLHO)

    assert host._maquina_pendente == {"orcamento": {"teto": None}}, (
        "o clique em 'Eu escolho' tem de acumular `None` EXPLÍCITO: a ausência "
        "da chave preservaria a escolha antiga na fusão"
    )
    assert gravar_maquina(host._maquina_pendente or {})
    assert carregar_maquina().orcamento.teto is None


def test_nao_sei_nao_entra_nas_chaves_do_schema() -> None:
    """Perfil é palavra de TELA; em `CHAVES` o `Literal` recusaria o documento."""
    for perfil in secao_orcamento.PERFIS:
        assert perfil not in secao_orcamento.CHAVES


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
    """Os três campos têm gesto de desfazer — e dois deles com a mesma palavra."""
    assert cores_do_plastico_items()[-1] == (ID_DE_NAO_SEI, "Não sei")
    assert BOTOES_DO_APARELHO[-1] == (ID_DE_NAO_SEI, "Não sei")
    assert secao_orcamento.PERFIS[-1] == secao_orcamento.PERFIL_EU_ESCOLHO
    assert secao_orcamento.TETO_POR_PERFIL[secao_orcamento.PERFIL_EU_ESCOLHO] is None
    assert (
        secao_orcamento.ROTULOS_DOS_PERFIS[secao_orcamento.PERFIL_EU_ESCOLHO]
        == "Personalizado"
    )
