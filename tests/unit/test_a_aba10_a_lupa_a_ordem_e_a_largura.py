"""A lupa, o duplo clique e a coluna que ela arrasta — PERFIS-LIMPA-01.

ORDEM DELA, 11/09/2026:

    *"Na tabela do perfil tem que terum svg dde lupa no titulo da tabela.  # (noqa-acento) cita ela
    Temos que remover esse botão voltar a de ontem ??? e o botão  # (noqa-acento) cita ela
    recarregar vira um svg clicável ao lado de Perfis Salvos que irá fazer  # (noqa-acento) cita ela
    essa função. Temos que deixar o layout mais limpo.. Aonde tá escrito  # (noqa-acento) cita ela
    Ajustes Próprios Vira Status e essa tabela abaixo dele tem a largura  # (noqa-acento) cita ela
    configurável pelo user (quando o cursor muda e  # (noqa-acento) cita ela
    permite alterar a largura da coluna) e isso passa  # (noqa-acento) cita ela
    a ser lembrado no futuro."*  # (noqa-acento) cita ela

O QUE ESTE ARQUIVO MEDE, e o que ele NÃO mede
----------------------------------------------
Ele mede o lado PYTHON — o que a lupa esconde, o que o duplo clique ordena, o
que o disco lembra — e a FORMA da página que o gerador emite. O que roda no
navegador (o roteiro abrir o campo, o `dblclick` virar clique, a divisa
arrastar) foi medido no `WebKit2.WebView` da janela dela, com o `BOOTSTRAP` do
piloto instalado, e está na entrega desta sprint, leitura a leitura.

**A LINHA DA SPRINT QUE CAIU, e ela caiu por medição.** A §6 dizia que *"as
três coisas novas — filtrar, ordenar, arrastar — são comportamento de DOM"*.
Medido: só DUAS são. O pacote emite a lista por duas portas ao mesmo tempo — o
`blocos` (o `<tbody>` pronto) e as três listas `perfis.linha.*`, que o pintor
distribui pelos elementos de mesmo endereço **na ordem do documento**.
Reordenar as `<tr>` no DOM não move as listas: no tique seguinte o nome do
primeiro perfil é escrito na primeira linha da TELA, que já é outra — nomes de
um perfil com o realce de outro, em silêncio, 100 ms depois. Esconder é seguro
(a linha oculta não sai do lugar); ordenar não é. Por isso a ordem mora aqui.

AS TRÊS MORDIDAS que a §7 da sprint cobra estão nomeadas uma a uma, e cada uma
arranca a cura e exige a reprovação.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app import gui_prefs
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis

TABELA = a10_perfis.TABELA_DA_LISTA


def _gerador() -> Any:
    """O `aba10.py` importado como o gerador se importa — só no TESTE."""
    pasta = Path(onde.__file__).parent
    if str(pasta) not in sys.path:
        sys.path.insert(0, str(pasta))
    import aba10  # type: ignore[import-not-found]

    return aba10


@pytest.fixture(autouse=True)
def _sem_estado_herdado(monkeypatch: pytest.MonkeyPatch) -> None:
    """O termo da lupa é estado de MÓDULO — sem isto um teste herda o anterior."""
    monkeypatch.setattr(a10_perfis, "_PROCURA", "", raising=False)


LISTA = [
    {"nome": "Mortal Kombat", "prioridade": "90", "quando": "Jogo · mk1.exe",
     "ativo": True, "dica": ""},
    {"nome": "Ação", "prioridade": "9", "quando": "Todos — quando nenhum casa",
     "ativo": False, "dica": ""},
    {"nome": "Elden Ring", "prioridade": "85", "quando": "Jogo da Steam · 1245620",
     "ativo": False, "dica": "disputa este jogo com outro perfil"},
]


# --------------------------------------------------------------------------
# §1 — A LUPA
# --------------------------------------------------------------------------
def test_a_lupa_acha_o_nome_do_jogo_sem_acento_e_sem_caixa(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A busca acha o jogo, e é o `Quando usar` que o guarda.

    Frase dela: *"achar rápido o nome de um jogo"*.  # (noqa-acento) cita ela
    """
    monkeypatch.setattr(a10_perfis, "_PROCURA", "MORTAL")
    assert [x["nome"] for x in a10_perfis._filtrada(LISTA)] == ["Mortal Kombat"]

    # sem acento: `acao` tem de achar `Ação`  (noqa-acento) o termo SEM acento
    # é o dado do teste — é ele que prova o normalizador
    monkeypatch.setattr(a10_perfis, "_PROCURA", "acao")  # (noqa-acento) dado
    assert [x["nome"] for x in a10_perfis._filtrada(LISTA)] == ["Ação"]

    # o appid da Steam mora no `Quando usar`, e é config de perfil
    monkeypatch.setattr(a10_perfis, "_PROCURA", "1245620")
    assert [x["nome"] for x in a10_perfis._filtrada(LISTA)] == ["Elden Ring"]

    # a DISPUTA é o `title` da linha, e ela também casa
    monkeypatch.setattr(a10_perfis, "_PROCURA", "disputa")
    assert [x["nome"] for x in a10_perfis._filtrada(LISTA)] == ["Elden Ring"]


def test_o_campo_vazio_devolve_as_linhas_todas(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Esvaziar o campo devolve a lista inteira — e um termo sem letra também.

    `slugify("—")` LEVANTA, e um `except` que devolvesse o termo cru faria a
    tela esconder tudo no dia em que ela colasse um travessão no campo.
    """
    for termo in ("", "   ", "—", "!!!"):
        monkeypatch.setattr(a10_perfis, "_PROCURA", termo)
        assert len(a10_perfis._filtrada(LISTA)) == 3, f"o termo {termo!r} filtrou"


# --------------------------------------------------------------------------
# §2 — A ORDENAÇÃO
# --------------------------------------------------------------------------
def test_a_prioridade_ordena_como_numero_e_nao_como_texto(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`90` vem depois de `9` — ordenar como texto é o defeito clássico.

    E ele seria o PRIMEIRO que ela veria: a Priorização é a coluna mais curta, e
    a que tem os números mais parecidos.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    gui_prefs.guardar_ordem_da_tabela(TABELA, "prioridade", "asc")
    assert [x["prioridade"] for x in a10_perfis._ordenada(LISTA)] == ["9", "85", "90"]
    gui_prefs.guardar_ordem_da_tabela(TABELA, "prioridade", "desc")
    assert [x["prioridade"] for x in a10_perfis._ordenada(LISTA)] == ["90", "85", "9"]


def test_o_ciclo_do_duplo_clique_tem_tres_estados(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """↑ → ↓ → nenhuma. O terceiro é o caminho de volta pela TELA.

    Sem ele, quem ordenou uma vez fica ordenado para sempre: não há gesto que
    devolva a ordem do produto (o perfil que está valendo em primeiro).
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    ctx = Contexto(state={"active_profile": "régua"}, mesa=[], conectados=[],
                   estados={})
    monkeypatch.setattr(a10_perfis, "pacote", lambda _c: {})

    a10_perfis.ordenar(ctx, {"coluna": "nome"}, None)
    assert gui_prefs.ordem_da_tabela(TABELA) == ("nome", "asc")
    a10_perfis.ordenar(ctx, {"coluna": "nome"}, None)
    assert gui_prefs.ordem_da_tabela(TABELA) == ("nome", "desc")
    a10_perfis.ordenar(ctx, {"coluna": "nome"}, None)
    assert gui_prefs.ordem_da_tabela(TABELA)[0] == "", (
        "o terceiro duplo clique tem de DESLIGAR a ordem — sem ele não há "
        "caminho de volta pela tela")
    assert a10_perfis._ordenada(LISTA) == LISTA, (
        "com a ordem desligada a lista sai como o produto a montou")


def test_o_duplo_clique_recusa_uma_coluna_que_nao_ordena(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Um clique sem coluna, ou com coluna inventada, RECUSA dizendo."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    ctx = Contexto(state={}, mesa=[], conectados=[], estados={})
    for bruto in ({}, {"coluna": ""}, {"coluna": "plastico"}):
        with pytest.raises(ValueError, match="coluna"):
            a10_perfis.ordenar(ctx, bruto, None)


def test_a_seta_acende_so_na_coluna_escolhida(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Uma seta acesa por vez, e o valor dela diz o SENTIDO."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    gui_prefs.guardar_ordem_da_tabela(TABELA, "quando", "desc")
    assert a10_perfis._seta_da_coluna("quando") == "↓"
    assert a10_perfis._seta_da_coluna("nome") == ""
    assert a10_perfis._seta_da_coluna("prioridade") == ""


# --------------------------------------------------------------------------
# §5 — A LARGURA
# --------------------------------------------------------------------------
def test_a_largura_volta_depois_de_fechar_e_reabrir(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Ela arrasta, a janela fecha, a janela abre — e a coluna está onde ela deixou.

    O `load_gui_prefs` de uma SEGUNDA leitura é o que representa a reabertura: o
    valor não está em memória de módulo nenhuma, ele está no disco.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    gui_prefs.guardar_largura_de_coluna(TABELA, "nome", 315)
    assert (tmp_path / "hefesto-dualsense4unix" / "gui_preferences.json").exists()
    assert gui_prefs.larguras_da_tabela(TABELA) == {"nome": 315}
    assert a10_perfis._larguras_em_texto(TABELA) == "nome:315"


def test_o_piso_da_coluna_impede_que_ela_suma(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Uma coluna arrastada a 3px some, e ela não tem onde pegar de novo.

    O piso mora no PYTHON, e é por isso que o gesto devolve o valor APARADO: o
    roteiro tem o mesmo número para o desenho não passar dele durante o
    arraste, mas quem decide é o lado que grava — um roteiro é uma linha de JS
    a mudar, e o disco é para sempre.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert gui_prefs.guardar_largura_de_coluna(TABELA, "nome", 3) == gui_prefs.PISO_DA_COLUNA
    assert gui_prefs.guardar_largura_de_coluna(TABELA, "nome", 9999) == gui_prefs.TETO_DA_COLUNA


def test_o_gesto_da_largura_recusa_tabela_e_numero_que_nao_existem(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    ctx = Contexto(state={}, mesa=[], conectados=[], estados={})
    with pytest.raises(ValueError, match="tabela"):
        a10_perfis.largura_da_coluna(
            ctx, {"tabela": "a-de-outra-aba", "coluna": "nome", "px": "200"}, None)
    with pytest.raises(ValueError, match="coluna"):
        a10_perfis.largura_da_coluna(ctx, {"tabela": TABELA, "px": "200"}, None)
    with pytest.raises(ValueError, match="pixels"):
        a10_perfis.largura_da_coluna(
            ctx, {"tabela": TABELA, "coluna": "nome", "px": "larguinho"}, None)


# --------------------------------------------------------------------------
# AS TRÊS MORDIDAS — §7.4 da sprint
# --------------------------------------------------------------------------
def test_mordida_1_arrancar_a_gravacao_da_largura_reprova(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """ARRANQUE a gravação e veja a régua reprovar.

    A cura arrancada é `save_gui_prefs` — o gesto passa a fazer tudo o que fazia
    (aparar, devolver o número, pintar) MENOS gravar. É o defeito mais caro
    desta família, porque a tela continua certa: a coluna fica onde ela a
    deixou, e só na próxima abertura ela descobre que nada foi lembrado.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setattr(gui_prefs, "save_gui_prefs", lambda _p: None)
    gui_prefs.guardar_largura_de_coluna(TABELA, "nome", 315)
    assert gui_prefs.larguras_da_tabela(TABELA) == {}, (
        "com a gravação arrancada a largura NÃO pode voltar — se este `assert` "
        "falhar, a régua está lendo uma memória de processo e não o disco")


def test_mordida_2_devolver_ajuste_proprio_no_th_reprova() -> None:
    """DEVOLVA `Ajuste próprio` ao `<th>` e veja o gerador RECUSAR de escrever.

    O gerador é quem pode recusar: uma decisão dela desfeita não chega ao disco.
    A mordida troca o rótulo no HTML já montado e chama a mesma `_conferir` que
    o `python aba10.py` chama.
    """
    aba10 = _gerador()
    html = onde.pagina("10-perfis.html").read_text(encoding="utf-8")
    aba10._conferir(html)  # a página de hoje passa

    torto = html.replace(">Status<span class=\"puxador\"",
                         ">Ajuste próprio<span class=\"puxador\"", 1)
    assert torto != html, "a mordida não mordeu — o rótulo mudou de forma"
    with pytest.raises(SystemExit, match="Status"):
        aba10._conferir(torto)


def test_mordida_3_trocar_o_duplo_clique_por_clique_simples_reprova() -> None:
    """ARRANQUE o `pointer-events:none` da seta e veja reprovar.

    **É A TRAVA INTEIRA DO DUPLO CLIQUE.** A seta é o elemento que carrega
    `data-hef-gesto="ordenar"`, e o ouvinte do piloto despacha no PRIMEIRO
    clique. Sem esta linha de CSS o cabeçalho passa a ordenar com um clique
    simples — a um pixel da célula do nome, que troca o perfil aberto no editor.
    Ela pediu duplo clique, e esta régua é o que segura a palavra dela.
    """
    aba10 = _gerador()
    html = onde.pagina("10-perfis.html").read_text(encoding="utf-8")
    regra = re.search(r"\.ordena\{[^}]*\}", html)
    assert regra is not None
    torto = html.replace(regra.group(0),
                         regra.group(0).replace("pointer-events:none;", ""), 1)
    assert torto != html, "a mordida não mordeu — a regra mudou de forma"
    with pytest.raises(SystemExit, match="pointer-events"):
        aba10._conferir(torto)


# --------------------------------------------------------------------------
# §3/§4 — O QUE A PÁGINA TEM DE DIZER
# --------------------------------------------------------------------------
def test_os_dois_gestos_nao_perderam_o_nome_ao_virar_icone() -> None:
    """Troca de invólucro não troca o nome do gesto — e há dono dos dois lados."""
    html = onde.pagina("10-perfis.html").read_text(encoding="utf-8")
    from hefesto_dualsense4unix.interface import pacotes

    for nome in ("recarregar", "voltar-a-de-ontem"):
        assert f'class="icone-rot" data-hef-gesto="{nome}"' in html, (
            f"o gesto `{nome}` não é mais um ícone do rótulo")
        assert pacotes.gesto_da_pagina(a10_perfis.PAGINA, nome) is not None, (
            f"o gesto `{nome}` perdeu o dono no pacote")


def test_os_tres_gestos_novos_tem_dono() -> None:
    """Um `data-hef-gesto` sem `@gesto` atrás responde CALADO no stdout dela."""
    from hefesto_dualsense4unix.interface import pacotes

    for nome in ("procurar", "ordenar", "largura-da-coluna"):
        assert pacotes.gesto_da_pagina(a10_perfis.PAGINA, nome) is not None, (
            f"o gesto `{nome}` está na página e não tem dono")


def test_a_lupa_nao_manda_gesto_nenhum_ao_python() -> None:
    """Abrir o campo é `classList.toggle` — e endereçar por `data-papel` custava.

    MEDIDO em 11/09/2026, com o `BOOTSTRAP` instalado: `data-papel` está na
    lista que o ouvinte do piloto casa, e cada clique na lupa chegava como
    `[gesto sem dono] 10-perfis.html · abrir-a-lupa`.
    """
    html = onde.pagina("10-perfis.html").read_text(encoding="utf-8")
    assert 'data-papel="abrir-a-lupa"' not in html
    assert 'class="icone-rot lupa"' in html


# --------------------------------------------------------------------------
# AS DUAS PORTAS DIZEM A MESMA COISA — e é a razão de a ordem morar no Python
# --------------------------------------------------------------------------
def test_o_blocos_e_as_tres_listas_saem_da_mesma_lista(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """O `<tbody>` pronto e as três colunas não podem discordar de ordem.

    **É A MEDIÇÃO QUE DERRUBOU A §6 DA SPRINT.** O pintor distribui
    `perfis.linha.nome` pelos elementos de mesmo endereço **na ordem do
    DOCUMENTO**; o `blocos` traz as linhas prontas, com `class="ativo"` e
    `aria-selected` dentro. Se as duas saíssem de listas com ordens diferentes,
    o tique seguinte escreveria o nome de um perfil na linha de outro — e o
    realce ficaria com o perfil errado, em silêncio.

    Esta régua fecha a única porta por onde isso pode voltar: alguém filtrar ou
    ordenar depois de as três listas serem montadas.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    perfis = [Profile(name=n, match=MatchAny()) for n in ("Zelda", "Ação", "Mario")]
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: perfis)
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    gui_prefs.guardar_ordem_da_tabela(TABELA, "nome", "asc")

    ctx = Contexto(state={"active_profile": "Zelda"}, mesa=[], conectados=[],
                   estados={})
    carga = a10_perfis.pacote(ctx)
    do_blocos = re.findall(
        r'data-hef="perfis\.linha\.nome"[^>]*>([^<]*)</td>',
        carga["blocos"][a10_perfis.SELETOR_DA_LISTA])
    assert do_blocos == carga["perfis.linha.nome"], (
        "o `<tbody>` e a lista `perfis.linha.nome` saíram em ordens "
        "diferentes — no tique seguinte a tela escreve o nome de um perfil na "
        "linha de outro, e o realce fica no errado")
    assert do_blocos == ["Ação", "Mario", "Zelda"], (
        f"a ordem escolhida não chegou à tela: {do_blocos}")
