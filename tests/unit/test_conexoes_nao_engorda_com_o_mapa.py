"""O mapa entra em "Conexões" por uma linha, e uma linha é o teto.

CONEXÕES · MAPA 2D 01, tarefa ``MAPA-5`` (25/08/2026).

O NÚMERO QUE ESCOLHE O LUGAR DO MAPA
--------------------------------------

A seção pede **2465 px numa janela de 1080** (``CONFIGURAÇÕES-FECHA-01`` §2.4,
foto ``readme_configuracoes_inteira.png``). Três faces de quadrados mais a
lista de aparelhos são mais uns 350 px, e nasceriam **abaixo da dobra** — seria
construir a feature e escondê-la, que é a ``A-CASA-SABE-E-O-PRODUTO-NAO-FAZ``
outra vez. Por isso o desenho mora em janela própria, e aqui dentro ficam uma
linha e um botão.

COMO SE MEDE "UMA LINHA"
-------------------------

A seção é montada DUAS vezes sobre a mesma bancada: uma com a linha do mapa, e
outra com ela trocada por uma caixa vazia. A diferença é exatamente o que esta
tarefa gastou de altura, e é ela que tem teto. Medir a seção inteira contra um
número absoluto mediria as outras quatro frentes junto.

Sob ``Gtk.OffscreenWindow``, nunca ``Gtk.Window``: sob Xvfb não há gerenciador
de janelas e uma ``Gtk.Window`` fica 1x1 para sempre — a régua devolveria zero
e o teto passaria sempre (``COMO-OLHAR-A-TELA.md``).
"""
from __future__ import annotations

from typing import Any

import pytest

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`.
exigir_gi_real("a linha do mapa dentro da seção Conexões")

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.utils.maquina import MapaDaMesa, MaquinaConfig
from tests.unit.test_mapa_a_bancada_de_mentira import bancada_de_agora, mapa_dela

#: O teto declarado da tarefa: uma linha de texto mais o botão ao lado dela.
TETO_EM_PX = 48


class _Hospedeiro:
    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None


def _altura_da_secao(
    *, mapa: MapaDaMesa, monkeypatch: pytest.MonkeyPatch | None = None
) -> int:
    """A altura mínima da seção montada sobre a bancada de mentira."""
    bancada = bancada_de_agora()
    mesa = bancada.mesa()
    censo = bancada.censo()
    documento = MaquinaConfig.model_validate(
        {"version": 1, "mapa": mapa.model_dump(mode="json")}
    )

    janela = Gtk.OffscreenWindow()
    caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    janela.add(caixa)

    painel = secao_mesa._PainelDaMesa(_Hospedeiro())
    painel._ler = lambda: mesa  # type: ignore[method-assign]
    painel._ler_o_censo = lambda: censo  # type: ignore[method-assign]
    painel._pedir_o_estado = lambda: None  # type: ignore[method-assign]
    original = secao_mesa.carregar_maquina
    secao_mesa.carregar_maquina = lambda: documento  # type: ignore[assignment]
    try:
        painel.montar(caixa)
    finally:
        secao_mesa.carregar_maquina = original  # type: ignore[assignment]
    janela.show_all()
    return int(caixa.get_preferred_height()[0])


def test_a_secao_ganha_no_maximo_uma_linha(monkeypatch: pytest.MonkeyPatch) -> None:
    """A linha do mapa custa uma linha, e não uma grade de quadrados.

    Mordida exercida em 25/08/2026: troquei ``_linha_do_mapa`` por uma que
    devolve a grade das três faces (quinze quadrados de 56 px). O delta passou
    de 48 px e o teste reprovou imprimindo os dois números — ver
    ``test_a_grade_de_faces_dentro_da_secao_estoura_o_teto``, que é a mordida
    escrita como teste.
    """
    com_a_linha = _altura_da_secao(mapa=mapa_dela())

    monkeypatch.setattr(
        secao_mesa, "_linha_do_mapa", lambda *_a, **_k: Gtk.Box()
    )
    sem_a_linha = _altura_da_secao(mapa=mapa_dela())

    delta = com_a_linha - sem_a_linha
    assert 0 < delta <= TETO_EM_PX, (
        f"a linha do mapa custou {delta} px, e o teto é {TETO_EM_PX}. "
        f"Com: {com_a_linha} px. Sem: {sem_a_linha} px. A seção já pede 2465 px "
        "numa janela de 1080 — o que passar daqui nasce abaixo da dobra"
    )


def test_a_grade_de_faces_dentro_da_secao_estoura_o_teto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mordida, escrita como teste: a grade inline passa MUITO do teto.

    Este teste é a régua da régua. Se ele passar a caber em 48 px, a medição de
    cima deixou de medir alguma coisa — e um teto que nada estoura não é teto.
    """
    sem_a_linha_base = _altura_da_secao(mapa=mapa_dela())

    def _grade_das_faces(mapa: MapaDaMesa, *_a: Any, **_k: Any) -> Any:
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        for face in mapa.faces:
            grade = Gtk.Grid()
            for coluna, numero in enumerate(face.portas):
                quadrado = Gtk.Button(label=numero)
                quadrado.set_size_request(84, 56)
                grade.attach(quadrado, coluna, 0, 1, 1)
            caixa.pack_start(grade, False, False, 0)
        return caixa

    monkeypatch.setattr(secao_mesa, "_linha_do_mapa", _grade_das_faces)
    com_a_grade = _altura_da_secao(mapa=mapa_dela())

    monkeypatch.setattr(secao_mesa, "_linha_do_mapa", lambda *_a, **_k: Gtk.Box())
    sem_nada = _altura_da_secao(mapa=mapa_dela())

    delta = com_a_grade - sem_nada
    assert delta > TETO_EM_PX, (
        f"a grade das três faces coube em {delta} px, dentro do teto de "
        f"{TETO_EM_PX}. A régua de altura parou de medir (base: "
        f"{sem_a_linha_base} px)"
    )


def test_quem_nunca_desenhou_le_o_preco_de_nao_ter_desenhado() -> None:
    """A frase de quem abre a aba sem mapa nenhum — e ela diz o preço.

    Mordida: fazer a linha sumir quando o mapa é vazio. O botão de desenhar a
    mesa some junto, e a feature inteira fica inalcançável para exatamente
    quem mais precisa dela — quem nunca desenhou.
    """
    linha = secao_mesa._linha_do_mapa(
        MapaDaMesa(), bancada_de_agora().censo(), lambda *_a: None
    )
    textos = _textos(linha)

    assert secao_mesa._SEM_MAPA in textos, (
        f"a frase de quem nunca desenhou não apareceu: {textos}"
    )
    assert secao_mesa._BOTAO_DESENHAR in _rotulos_de_botao(linha), (
        "o botão de desenhar a mesa não está na linha"
    )


def test_com_o_mapa_a_linha_conta_faces_entradas_e_aparelhos() -> None:
    """Três faces, quinze entradas, sete aparelhos — os números da mesa dela.

    Mordida: trocar o ``resumo_do_mapa`` por uma contagem do dicionário de
    entradas. A linha passa a dizer "16 entradas" (a ``15a`` entra na conta) e
    o número da tela deixa de bater com a fileira do metal.
    """
    linha = secao_mesa._linha_do_mapa(
        mapa_dela(), bancada_de_agora().censo(), lambda *_a: None
    )
    textos = _textos(linha)

    esperado = secao_mesa._RESUMO_DO_MAPA.format(
        faces=3, entradas=15, colocados=7
    )
    assert esperado in textos, f"a linha-resumo mudou de número: {textos}"


def _textos(raiz: Any) -> list[str]:
    achados: list[str] = []

    def _andar(widget: Any) -> None:
        if isinstance(widget, Gtk.Label):
            achados.append(widget.get_text())
        obter = getattr(widget, "get_children", None)
        if obter is not None:
            for filho in obter():
                _andar(filho)

    _andar(raiz)
    return achados


def _rotulos_de_botao(raiz: Any) -> list[str]:
    achados: list[str] = []

    def _andar(widget: Any) -> None:
        if isinstance(widget, Gtk.Button):
            achados.append(widget.get_label() or "")
            return
        obter = getattr(widget, "get_children", None)
        if obter is not None:
            for filho in obter():
                _andar(filho)

    _andar(raiz)
    return achados
