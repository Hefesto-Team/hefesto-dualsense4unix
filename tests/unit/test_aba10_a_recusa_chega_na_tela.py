"""A aba Perfis recusava para o TERMINAL — e o "Estilo de Jogo" nem recusava.

DOIS DEFEITOS, medidos em 03/09/2026 clicando a aba no PRODUTO INSTALADO, com o
daemon dela vivo e um DualSense White no cabo.

**1. O "Estilo de Jogo" era o último gesto SEM DONO da aba.** O
``data-hef-gesto="editor.estilo"`` está na página publicada
(``interface/paginas/10-perfis.html:1216``) num ``<select>`` de dezesseis
opções, com a classe ``destaque`` — o campo mais aceso do painel. Não havia
``@gesto``: o piloto caía no ramo do gesto sem dono e imprimia ``[gesto sem
dono]`` no stdout de quem lançou a janela. Dirigindo a aba como ela dirige
(``change`` de verdade, escolhendo "Terror" em ``meu_perfil``):

    estilo_na_tela: "Terror"   ← a tela AFIRMA, e continua afirmando
    tarjas: []                 ← ninguém disse nada
    md5 meu_perfil.json: b4387a17…  ANTES **e** DEPOIS — nada gravou

O contrato do produto já proibia isso com todas as letras
(``app/actions/perfis_web.py``, docstring do módulo): *"Ele nasce TRAVADO, com o
motivo — um ``<select>`` que aceita escolha e não guarda nada é a pior das
saídas"*. A aba entregava exatamente a pior das saídas.

**2. Nove recusas desta aba nunca chegavam à tela.** ``_recusou_dizendo``
(``hefesto_vivo.py``) pinta tarja **só para ``RuntimeError``** — um
``ValueError`` sai no ``stderr`` do processo que lançou a janela. As frases
desta aba são escritas para ELA (*"Escolha outro na lista da esquerda e clique
em Ativar"*, *"gravar este por cima apagaria o dele"*) e levantavam
``ValueError``. Medido: clicar "Ativar" no perfil que já vale imprime a recusa
no terminal e deixa ``document.querySelectorAll('.hef-recado')`` com **zero**
elementos.

A régua não roda o WebKit: ela cobra os DOIS degraus que decidem, no Python —
que o gesto exista com dono, e que a exceção seja da classe que a tarja pinta.
Quem prova o degrau de cima (a tarja aparecendo no DOM) é
``test_a_frase_pousa_no_cartao_de_quem_foi_clicado``.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader

PAGINA = "10-perfis.html"

#: A MESA — endereço MASCARADO (octetos 4 e 5 zerados).
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True,
     "mascara": "DualSense"},
]

#: AS FRASES QUE SÃO DELA, uma por gesto, com o pedaço que a identifica.
#:
#: Cada linha é um clique que ela pode dar hoje e que o produto RECUSA. A régua
#: exige ``RuntimeError`` em todas — é a única classe que ``_recusou_dizendo``
#: leva ao DOM. O ``selecionar`` fica FORA de propósito: a frase dele
#: ("o clique não trouxe o nome do perfil") fala com quem programa, e é o único
#: ``ValueError`` que continua certo neste arquivo.
#:
#: A SEXTA MUDOU EM 03/09/2026, à noite, e a troca é a entrega: era *"o perfil
#: não guarda Estilo de Jogo"*, a recusa do campo sem motor. O motor nasceu (ver
#: `test_aba10_o_slider_e_o_estilo_gravam.py`) e a frase que sobra é a de quem
#: escolheu o travessão — a única recusa que o campo ainda tem. As duas últimas
#: são as do slider, que nasceu no mesmo dia.
DELA = ("já é o perfil que está valendo",
        "escolha um perfil na lista primeiro",
        "o perfil precisa de um nome",
        "gravar este por cima apagaria o dele",
        "não é uma regra que o perfil saiba guardar",
        "escolha um Estilo de Jogo na lista",
        "está fora da faixa que o perfil aceita",
        "a prioridade tem de ser um número")


class PonteDeMentira:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(("profile_switch", (nome,)))
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(("chamar", (metodo, *a)))
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        self.chamadas.append(("resultado", (metodo, *a)))
        return {}


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado de MÓDULO herdado de outro teste não é prova de nada."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO_REBAIXAR", None, raising=False)


def _o_disco_tem(monkeypatch: pytest.MonkeyPatch, *nomes: str) -> list[Any]:
    """A pasta de perfis, sem escrever no disco.

    SEM ISTO A PASTA É VAZIA: a ``conftest.py`` põe
    ``HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`` em TODO teste.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    todos = [Profile(name=n, match=MatchAny(), priority=100 - i)
             for i, n in enumerate(nomes)]
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
    monkeypatch.setattr(
        loader, "load_profile",
        lambda nome, *a, **k: next(p for p in todos if p.name == nome))
    return todos


def _ctx(ativo: str | None = None) -> Contexto:
    return Contexto(state={"active_profile": ativo}, mesa=list(MESA),
                    conectados=list(MESA), estados={})


# --------------------------------------------------------------------------
# 1. O "ESTILO DE JOGO" TEM DONO — e desde 03/09/2026, à noite, o dono APLICA
#
# O QUE ESTA SEÇÃO GUARDA depois do motor: que o campo tem dono, e as DUAS
# recusas que sobraram — o clique sem valor e o travessão. O que ele GRAVA está
# em `test_aba10_o_slider_e_o_estilo_gravam.py`, junto do slider que nasceu no
# mesmo dia.
# --------------------------------------------------------------------------

def test_o_estilo_de_jogo_tem_dono() -> None:
    """MORDIDA: tire o ``@gesto`` de ``editor_estilo`` e isto reprova.

    É o degrau que o piloto consulta antes de despachar
    (``hefesto_vivo._gesto`` → ``pacotes.gesto_da_pagina``); sem ele o clique
    dela cai no ramo do ``print`` no stdout, calado na tela.
    """
    assert pacotes.gesto_da_pagina(PAGINA, "editor.estilo") is not None, (
        "o `<select>` Estilo de Jogo voltou a ser um gesto SEM DONO: a escolha "
        "dela some no stdout de quem lançou a janela")


def test_o_estilo_recusa_ate_sem_valor_no_clique(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem ``valor`` a recusa continua — e sem ``KeyError`` na cara dela.

    O ``change`` de um ``<select>`` sempre traz ``valor``, mas o gesto também
    chega pelo ``click`` (o ouvinte do bootstrap escuta os dois) e de qualquer
    régua que monte o dicionário à mão. Um ``KeyError`` aqui derrubaria o
    despacho em vez de recusar.
    """
    _o_disco_tem(monkeypatch, "Pragmata")
    with pytest.raises(RuntimeError, match="escolha um Estilo de Jogo na lista"):
        a10_perfis.editor_estilo(_ctx("Pragmata"), {}, PonteDeMentira())


def test_o_travessao_nao_e_uma_escolha(monkeypatch: pytest.MonkeyPatch) -> None:
    """A primeira opção do desenho é ``<option value="">—</option>``.

    Um clique que não escolheu nada chega com ``valor=""`` e ``rotulo="—"`` — o
    ``rotulo`` é o texto VISÍVEL da opção marcada (``hefesto_vivo.py:702``).
    Medido na prova no aparelho: a tarja saía dizendo *“—” não foi salvo*.

    MORDIDA: tire o ``if escolhido == "—"`` do gesto e isto reprova com
    *"“—” não é um dos Estilos de Jogo do produto"*, que não é frase de gente.
    """
    _o_disco_tem(monkeypatch, "Pragmata")
    with pytest.raises(RuntimeError) as erro:
        a10_perfis.editor_estilo(_ctx("Pragmata"),
                                 {"valor": "", "rotulo": "—"}, PonteDeMentira())
    assert "escolha um Estilo de Jogo na lista" in str(erro.value), str(erro.value)
    assert "“—”" not in str(erro.value), (
        f"o travessão do lugar vazio virou nome de estilo na tarja: {erro.value}")


def test_o_estilo_entrou_em_sem_eco_quando_ganhou_motor() -> None:
    """``SEM_ECO`` é de quem GRAVA no disco e o ``state_full`` não ecoa.

    ELE ESTAVA FORA por outra razão, e a razão caducou em 03/09/2026: até a
    tarde ele SEMPRE levantava, e recusa é ``!`` na prova no aparelho, não
    ``—``. Com o motor, ele grava três coisas no ``.json`` dela — deixá-lo de
    fora faria a régua acusar de mudo um gesto que trabalhou.

    MORDIDA: tire ``editor.estilo`` (ou ``editor.prioridade``) de ``SEM_ECO`` e
    isto reprova.
    """
    for nome in ("editor.estilo", "editor.prioridade"):
        assert nome in a10_perfis.SEM_ECO, (
            f"{nome} grava no disco e saiu de `SEM_ECO`: a prova no aparelho "
            f"vai contá-lo como 'disse aplicado e nada mudou'")


# --------------------------------------------------------------------------
# 2. AS RECUSAS DELA SÃO `RuntimeError` — a única classe que vira tarja
# --------------------------------------------------------------------------

def test_o_ativar_recusa_com_a_classe_que_a_tarja_pinta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O caso medido: ela clica "Ativar" no perfil que já vale.

    MORDIDA: troque o ``RuntimeError`` de ``a10_perfis.ativar`` por
    ``ValueError`` e isto reprova — que é exatamente o estado em que a aba
    estava, com a frase certa saindo só no terminal.
    """
    _o_disco_tem(monkeypatch, "meu_perfil")
    a10_perfis._ESCOLHIDO = "meu_perfil"
    ponte = PonteDeMentira()
    with pytest.raises(RuntimeError, match="já é o perfil que está valendo"):
        a10_perfis.ativar(_ctx("meu_perfil"), {}, ponte)
    assert ponte.chamadas == []


def test_renomear_por_cima_de_outro_perfil_recusa_na_tela(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A recusa que protege DADO DELA — e era a mais cara de perder.

    ``editor.nome`` recusa quando o nome novo já é de outro perfil, porque
    gravar apagaria o dele. Com ``ValueError``, ela renomeava, não via aviso
    nenhum, e ficava sem saber por que o nome não mudou.
    """
    _o_disco_tem(monkeypatch, "Pragmata", "Sackboy")
    a10_perfis._ESCOLHIDO = "Pragmata"
    with pytest.raises(RuntimeError, match="apagaria o dele"):
        a10_perfis.editor_nome(_ctx("Pragmata"), {"valor": "Sackboy"},
                               PonteDeMentira())


def test_nenhuma_frase_dela_sai_como_valueerror() -> None:
    """A régua de FORMA sobre o arquivo inteiro, e ela é a que segura a regra.

    As seis frases de :data:`DELA` são as que ela lê. A régua exige que cada
    uma esteja num ``raise RuntimeError`` — e não num ``ValueError``, que
    ``_recusou_dizendo`` descarta antes de tocar o DOM.

    POR QUE LER O FONTE, e é a exceção que esta casa aceita: as frases moram em
    guardas que dependem de estado de disco, de daemon e de relógio (o Remover
    ARMA por oito segundos), e exercitá-las todas custaria seis dublês para
    medir uma coisa só — a palavra ``RuntimeError`` antes da frase. Os testes
    acima cobrem o ATO nos dois casos que ela clica mais.

    MORDIDA: troque qualquer ``raise RuntimeError`` deste arquivo por
    ``raise ValueError`` e a linha da frase aparece na falha.
    """
    import inspect
    import re

    fonte = inspect.getsource(a10_perfis)
    # Cada `raise <Classe>(` com o corpo até o fecho do parêntese seguinte —
    # basta para dizer em qual `raise` a frase mora.
    blocos = re.findall(r"raise (ValueError|RuntimeError)\((.*?)\)\n",
                        fonte, re.S)
    mudas = [pedaco for pedaco in DELA
             if any(classe == "ValueError" and pedaco in corpo
                    for classe, corpo in blocos)]
    assert not mudas, (
        f"{len(mudas)} recusa(s) escrita(s) para ELA voltaram a ser "
        f"`ValueError`, e `_recusou_dizendo` só pinta `RuntimeError`: {mudas}")
    # O CONTRAPESO: a régua acima ficaria verde para sempre se as frases
    # sumissem do arquivo. Esta linha exige que as seis continuem EXISTINDO.
    achadas = [pedaco for pedaco in DELA if pedaco in fonte]
    assert achadas == list(DELA), (
        f"frase(s) de recusa sumiram do arquivo: "
        f"{sorted(set(DELA) - set(achadas))}")


def test_o_selecionar_continua_valueerror() -> None:
    """O contrapeso da regra: nem toda recusa é dela.

    ``selecionar`` levanta quando o clique não trouxe nome de perfil — não há
    nada que ela possa fazer com essa frase, e pô-la na tarja trocaria um
    silêncio por um ruído. Sem esta régua, "tudo vira ``RuntimeError``" passaria
    como se fosse a regra.
    """
    with pytest.raises(ValueError, match="não trouxe o nome do perfil"):
        a10_perfis.selecionar(_ctx(), {"texto": ""}, PonteDeMentira())
