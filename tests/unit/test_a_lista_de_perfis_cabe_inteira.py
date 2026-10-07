"""A lista de perfis mostra TODOS os perfis, e não os catorze do desenho.

O DEFEITO, medido em 02/09/2026 na máquina do usuário: ``load_all_profiles()``
devolve **33** perfis e o ``<tbody>`` publicado tem **14** linhas. O contador ao
lado do título dizia "33 perfis" — e dizia a verdade — enquanto a tabela logo
abaixo mostrava catorze. **Dezenove perfis do usuário não tinham como ser clicados**,
e com eles nove dos dez botões desta aba: ``ativar``, ``remover``, ``duplicar``,
``editor.nome``… todos agem sobre o perfil ESCOLHIDO, e escolher é clicar numa
linha que existe.

A CURA é o ``blocos`` — o mesmo degrau da fita de chips e do mapa do gabinete:
um bloco cujo NÚMERO DE FILHOS muda com o dado não tem endereço para o filho
que ainda não existe, então ele se troca inteiro.

**A RÉGUA DO MOCKUP NÃO ENXERGA ESTA ENTREGA, e é limite dela, não desta cura.**
Ela compara o que a tela mostra com o que o ARQUIVO crava, endereço a endereço:
um endereço que NASCE na tela não tem par no arquivo e sai só como nota
("3 endereço(s) NASCERAM na tela"). Dezenove linhas novas não mudam nenhuma das
três contagens. Por isso este arquivo existe.

AS TRÊS COISAS QUE SÓ CHEGAM À TELA POR AQUI:

1. as 19 linhas que faltavam;
2. a classe ``ativo`` na linha CERTA — o desenho a crava na primeira, e ela
   ficava lá. Acertava por acidente (``ordem_de_exibicao`` põe o ativo em
   primeiro) e mentia inteiro quando não há perfil ativo nenhum;
3. o ``title`` da disputa. ``explicacao_da_disputa`` existe em
   ``profiles_actions:403``, ``perfis_web._linhas_da_lista`` já a chamava a cada
   tique, e o valor morria no dicionário.

A MORDIDA de cada régua está na sua docstring.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis

MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1, "cor": "cosmic-red",
     "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True,
     "mascara": "DualSense"},
]


def _perfis(*nomes: str) -> list[Any]:
    """Perfis de verdade — o esquema do produto, não um dublê de dicionário."""
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    return [Profile(name=n, match=MatchAny(), priority=100 - i)
            for i, n in enumerate(nomes)]


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    """O ``_ESCOLHIDO`` é estado de MÓDULO: sem limpá-lo, um teste herda a"""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)


def _pacote(nomes: list[str], ativo: str = "") -> dict[str, Any]:
    """O que ``pacote()`` manda pintar, com uma pasta de perfis de mentira."""
    from hefesto_dualsense4unix.profiles import loader

    todos = _perfis(*nomes)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
        ctx = Contexto(state={"active_profile": ativo}, mesa=list(MESA),
                       conectados=list(MESA), estados={})
        return a10_perfis.pacote(ctx)


def _linhas(pacote: dict[str, Any]) -> list[str]:
    """As ``<tr>`` que o pacote manda para o ``<tbody>`` da lista."""
    html = (pacote.get("blocos") or {}).get(a10_perfis.SELETOR_DA_LISTA, "")
    return re.findall(r"<tr\b.*?</tr>", html, re.S)


def test_a_linha_viva_e_a_linha_do_desenho() -> None:
    """``_linha_da_lista`` tem de sair IGUAL a ``aba10.linha_do_perfil``.

    O gerador não atravessa para o produto — ``aba10.py`` faz ``sys.path.insert``
    e ``from monta import …``, e o ``monta`` lê seis arquivos do repositório no
    import. Um gerador no caminho do produto é uma janela que não abre onde não
    há repositório. Então a forma é copiada, e o que impede a segunda gramática
    é ESTA régua, não a boa vontade.

    MORDIDA: mude uma classe, um atributo ou a ordem das três células em
    qualquer um dos dois lados e este teste reprova nomeando a diferença.
    """
    aba10 = _gerador()
    for ativo in (True, False):
        do_desenho = aba10.linha_do_perfil("Elden Ring", "85",
                                           "Jogo da Steam · 1245620", ativo,
                                           "a disputa")
        do_produto = a10_perfis._linha_da_lista("Elden Ring", "85",
                                                "Jogo da Steam · 1245620", ativo,
                                                "a disputa")
        assert do_produto == do_desenho, (
            "a linha viva divergiu do desenho:\n"
            f"  desenho: {do_desenho!r}\n  produto: {do_produto!r}")


def _gerador() -> Any:
    """O ``aba10.py`` importado como o gerador se importa — só no TESTE."""
    pasta = Path(onde.__file__).parent
    if str(pasta) not in sys.path:
        sys.path.insert(0, str(pasta))
    import aba10  # type: ignore[import-not-found]

    return aba10


@pytest.mark.parametrize("quantos", [1, 14, 15, 33, 60])
def test_uma_linha_por_perfil_e_o_desenho_nao_e_teto(quantos: int) -> None:
    """N perfis no disco, N linhas na tela — inclusive acima dos catorze."""
    pacote = _pacote([f"Jogo {i}" for i in range(quantos)])
    linhas = _linhas(pacote)
    assert len(linhas) == quantos, (
        f"{quantos} perfis no disco e {len(linhas)} linhas emitidas")
    assert all(x.startswith("<tr") and x.endswith("</tr>") for x in linhas)


def test_a_lista_vazia_diz_o_que_fazer_em_vez_de_ficar_em_branco() -> None:
    """Sem perfil no disco, a tabela explica como nasce o primeiro.

    A frase é ``perfis_web.LISTA_VAZIA`` e já estava escrita — nunca tinha
    chegado à tela, porque não há ``data-hef`` para ela na página. Sem esta
    linha o ``<tbody>`` ficaria em branco: a tela calada sobre um estado que ela
    sabe explicar.

    MORDIDA: troque o ramo ``if not lista`` de ``_html_da_lista`` por ``""`` e
    este teste reprova.
    """
    from hefesto_dualsense4unix.app.actions.perfis_web import LISTA_VAZIA

    linhas = _linhas(_pacote([]))
    assert len(linhas) == 1
    assert LISTA_VAZIA in linhas[0]
    assert 'colspan="3"' in linhas[0]


def test_o_realce_acompanha_o_perfil_ativo_e_nao_a_primeira_linha() -> None:
    """``class="ativo"`` no perfil que está valendo, e em mais nenhum.

    O desenho crava a classe na PRIMEIRA linha. Nenhum dos cinco alvos do pintor
    (texto·largura·fundo·valor·html) liga uma CLASSE, então até hoje ela ficava
    onde o mockup a pôs. Aqui a linha chega pronta, com a classe dentro dela.

    MORDIDA: troque ``bool(x.get("ativo"))`` por ``False`` em ``_html_da_lista``
    e nenhuma linha fica realçada; troque por ``True`` e todas ficam.
    """
    nomes = ["Primeiro", "Segundo", "Terceiro"]
    linhas = _linhas(_pacote(nomes, ativo="Segundo"))
    realcadas = [x for x in linhas if 'class="ativo"' in x]
    assert len(realcadas) == 1, "só o perfil que está valendo se realça"
    assert 'data-hef-perfil="Segundo"' in realcadas[0]


def test_sem_perfil_ativo_ninguem_se_realca() -> None:
    """Nenhum perfil valendo, nenhuma linha realçada."""
    from hefesto_dualsense4unix.app.actions import profiles_actions

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(profiles_actions, "perfil_que_ela_ativou", lambda: None)
        linhas = _linhas(_pacote(["Primeiro", "Segundo"], ativo=""))
    assert len(linhas) == 2, (
        f"a lista parou de ser emitida — {len(linhas)} linha(s) para 2 perfis; "
        f"sem isto a negativa abaixo fica verde para sempre")
    assert not [x for x in linhas if 'class="ativo"' in x]


def test_o_title_da_linha_traz_a_explicacao_da_disputa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O ``title=""`` do desenho passa a carregar o que o produto já calculava.

    ``explicacao_da_disputa`` roda a cada tique dentro de
    ``perfis_web._linhas_da_lista`` desde 30/08 e o valor morria no dicionário —
    o desenho nasce com ``title=""`` *"porque a dica é a DISPUTA, e disputa é
    dado; o mockup não tem nenhum"* (palavras do gerador). O dado existe; o que
    faltava era a porta.

    NOTA DATADA — 01/10/2026 (O-HEFESTO-ABRE-NO-ULTIMO-PERFIL-E-O-FREESTYLE-DIZ-
    A-VERDADE-01): o `match any` saiu da seleção automática, e não há mais
    disputa entre os «Sempre» — o produto responde ``""``, e a linha sai sem
    dica. A régua passa a medir a PORTA com uma frase posta por ela: a porta
    fica, e a frase do produto é a que ele calcular.

    MORDIDA: emita ``""`` no lugar do ``dica`` em ``_html_da_lista`` e este
    teste reprova.
    """
    from hefesto_dualsense4unix.app.actions import perfis_web
    from hefesto_dualsense4unix.app.actions.profiles_actions import (
        explicacao_da_disputa,
    )

    perfis = _perfis("Um", "Dois")
    assert explicacao_da_disputa(perfis[0], perfis, None) == "", (
        "o produto voltou a explicar uma disputa que não existe desde 01/10/2026")
    esperado = "Primeiro parágrafo da régua.\n\nSegundo & último."
    monkeypatch.setattr(perfis_web, "explicacao_da_disputa", lambda *_a, **_k: esperado)

    linhas = _linhas(_pacote(["Um", "Dois"]))
    titulos = [re.search(r'title="((?:[^"])*)"', x, re.S) for x in linhas]
    vivos = [m.group(1) for m in titulos if m and m.group(1)]
    assert len(vivos) == len(linhas), "toda linha leva a explicação que o produto calcula"
    assert vivos[0] == esperado.replace("&", "&amp;"), (
        "o title da linha não é a frase que o produto calcula")


CRUS_EM_ATRIBUTO = ("'", "\n", "<", ">")


def test_o_miolo_da_lista_e_estavel_no_ida_e_volta_do_navegador() -> None:
    """Escapar DEMAIS faz o ``<tbody>`` ser reescrito a cada 500 ms, para sempre."""
    for caractere in CRUS_EM_ATRIBUTO:
        saiu = a10_perfis._atr(f"a{caractere}b")
        assert saiu == f"a{caractere}b", (
            f"o atributo escapou {caractere!r}, e o navegador o devolve cru — "
            f"o bloco seria reescrito a cada tique")
    assert a10_perfis._atr('a"b') == "a&quot;b", "a aspa dupla FECHA o atributo"
    assert a10_perfis._atr("a&b") == "a&amp;b"
    assert a10_perfis._texto("a<b>c") == "a&lt;b&gt;c"
    assert a10_perfis._texto('a"b') == 'a"b', "aspa em texto não fecha nada"


def test_um_nome_de_perfil_com_aspas_nao_derrama_marcacao() -> None:
    """Os 33 nomes vêm do disco do usuário — o gerador escrevia catorze nossos."""
    linhas = _linhas(_pacote(['Elden Ring "GOTY"']))
    assert "&quot;GOTY&quot;" in linhas[0]
    assert '"GOTY"' not in linhas[0].split(">", 1)[0], (
        "o nome saiu com a aspa CRUA na abertura da `<tr>` — ela fecha o "
        "atributo e o resto do nome vira marcação")
    assert linhas[0].count("<tr") == 1
    assert linhas[0].count("<td") == 3, (
        "a linha tem três células; um <td> a mais é marcação derramada pelo "
        "nome, que é exatamente o que o `_atr` existe para impedir")


def test_a_barra_da_prioridade_vai_em_numero_puro() -> None:
    """``editor.prioridade`` é LARGURA, e o pintor põe o ``%`` sozinho."""
    valor = _pacote(["Um"])["editor.prioridade"]
    assert not str(valor).endswith("%"), (
        f"a largura saiu com o sinal: {valor!r} — o pintor faria {valor}%")
    assert 0 <= float(valor) <= 100


def test_a_pagina_publicada_aceita_largura_no_trilho() -> None:
    """O ``data-hef-alvo="largura"`` do trilho JÁ ESTÁ PUBLICADO.

    FATO DERRUBADO em 02/09/2026: a nota em ``a10_perfis`` dizia que o atributo
    estava *"já escrito na BANCADA, esperando o ato de publicar DO USUÁRIO"*. Ela já
    publicou — o commit ``6f289554`` levou a aba inteira, o atributo está nas
    DUAS páginas, e ``mockup/DIVERGENCIAS.md`` não tem seção da aba 10. Enquanto
    a nota ficou de pé, a barra seguiu nos 90% do desenho com o conserto no
    disco há um commit.

    MORDIDA: esta régua olha a página PUBLICADA. Se alguém republicar a aba sem
    o atributo, ela reprova antes de a barra voltar a mentir.
    """
    texto = onde.pagina("10-perfis.html", publicado=True).read_text(encoding="utf-8")
    trilho = re.search(r'<span[^>]*data-hef="editor\.prioridade"[^>]*>', texto)
    assert trilho, "o trilho da prioridade sumiu da página publicada"
    assert 'data-hef-alvo="largura"' in trilho.group(0), (
        "o trilho voltou a receber TEXTO: o pintor escreveria o número dentro "
        "de uma barra de 5px e a largura ficaria no 90% do desenho")
    assert "editor.prioridade" not in a10_perfis.NAO_PINTAVEIS
