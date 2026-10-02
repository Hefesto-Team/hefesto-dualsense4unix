"""Clicar num perfil TEM de aparecer na linha dele — e sobreviver à repintura."""
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
    """``_ESCOLHIDO`` é estado de MÓDULO: sem limpá-lo, um teste herda a escolha"""
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


def _marcada(linhas: list[str]) -> list[str]:
    """Os nomes das linhas que carregam a marca de ESCOLHIDA."""
    return [re.search(r'data-hef-perfil="([^"]*)"', x).group(1)  # type: ignore[union-attr]
            for x in linhas if 'aria-selected="true"' in x]


def _clicar(nome: str) -> None:
    """O gesto de verdade, pelo caminho de verdade — o clique na célula do nome."""
    a10_perfis.selecionar(Contexto(state={}), {"texto": nome}, None)


def _gerador() -> Any:
    """O ``aba10.py`` importado como o gerador se importa — só no TESTE."""
    pasta = Path(onde.__file__).parent
    if str(pasta) not in sys.path:
        sys.path.insert(0, str(pasta))
    import aba10  # type: ignore[import-not-found]

    return aba10


def test_o_clique_marca_a_linha_dele_e_desmarca_as_outras() -> None:
    """Clicar em ``Terceiro`` marca ``Terceiro``, e mais ninguém."""
    _clicar("Terceiro")
    linhas = _linhas(_pacote(["Primeiro", "Segundo", "Terceiro"], ativo="Segundo"))

    assert _marcada(linhas) == ["Terceiro"], (
        "a marca de ESCOLHIDA tem de estar na linha clicada, e só nela")
    # atributo que aparece e some — ver a nota do `blocos` em `_linha_da_lista`.
    assert sum('aria-selected="false"' in x for x in linhas) == 2


def test_o_escolhido_nao_e_o_ativo_e_a_tela_diz_os_dois() -> None:
    """A linha que VALE e a linha que está ABERTA podem ser outras — e são."""
    _clicar("Terceiro")
    linhas = _linhas(_pacote(["Primeiro", "Segundo", "Terceiro"], ativo="Segundo"))
    por_nome = {re.search(r'data-hef-perfil="([^"]*)"', x).group(1): x  # type: ignore[union-attr]
                for x in linhas}

    valendo, aberta = por_nome["Segundo"], por_nome["Terceiro"]
    assert 'class="ativo"' in valendo and 'aria-selected="false"' in valendo, (
        "o perfil que está VALENDO perdeu o realce — ou ganhou a marca de "
        "escolhida sem ninguém ter clicado nele")
    assert 'class=""' in aberta and 'aria-selected="true"' in aberta, (
        "a linha ABERTA no editor tem a marca de escolhida e NÃO a de ativa")


def test_os_tres_estados_saem_diferentes_do_python() -> None:
    """ativo+escolhido · só ativo · só escolhido — três linhas, três formas.

    Os dois primeiros COINCIDEM na abertura da aba, e é por isso que os três
    precisam existir: ``_escolhido()`` sincroniza o escolhido com o ativo
    enquanto ela não clicou em nada, então o estado inicial é o combinado. Uma
    tela que desenhasse só dois estados faria o combinado parecer "só ativo" —
    e a queixa dela voltaria no primeiro clique.

    MORDIDA: faça ``_linha_da_lista`` ignorar ``escolhido`` e os três viram
    dois; faça-a ignorar ``ativo`` e viram dois pelo outro lado.
    """
    forma = {
        "ativo+escolhido": a10_perfis._linha_da_lista("X", "9", "q", True,
                                                      escolhido=True),
        "so_ativo": a10_perfis._linha_da_lista("X", "9", "q", True,
                                               escolhido=False),
        "so_escolhido": a10_perfis._linha_da_lista("X", "9", "q", False,
                                                   escolhido=True),
        "nenhum": a10_perfis._linha_da_lista("X", "9", "q", False,
                                             escolhido=False),
    }
    assert len(set(forma.values())) == 4, (
        "dois estados da linha saem do Python com a MESMA marcação — a tela não "
        "tem como distingui-los:\n" + "\n".join(f"  {k}: {v}"
                                                for k, v in forma.items()))
    assert 'class="ativo"' in forma["ativo+escolhido"], (
        "o combinado perdeu a classe `ativo` — e com ela a régua do realce, "
        "`test_a_lista_de_perfis_cabe_inteira.py:159`, que procura a SUBSTRING "
        '`class="ativo"`')


def test_a_marca_sobrevive_a_repintura() -> None:
    """Dez tiques depois do clique, a marca continua na mesma linha."""
    _clicar("Terceiro")
    saidas = [_linhas(_pacote(["Primeiro", "Segundo", "Terceiro"],
                              ativo="Segundo")) for _ in range(10)]

    for i, linhas in enumerate(saidas):
        assert _marcada(linhas) == ["Terceiro"], (
            f"a marca sumiu no tique {i + 1} de 10 — ela não vem do Python")
    assert len(set(map(tuple, saidas))) == 1, (
        "o `<tbody>` sai diferente de um tique para o outro; o `blocos` o "
        "reescreveria para sempre e apagaria o `:hover` da linha sob o mouse")


def test_a_marca_muda_de_linha_quando_ela_clica_noutra() -> None:
    """Ela clica no ``Terceiro``, depois no ``Primeiro`` — a marca acompanha."""
    nomes = ["Primeiro", "Segundo", "Terceiro"]
    _clicar("Terceiro")
    assert _marcada(_linhas(_pacote(nomes, ativo="Segundo"))) == ["Terceiro"]
    _clicar("Primeiro")
    assert _marcada(_linhas(_pacote(nomes, ativo="Segundo"))) == ["Primeiro"]


def test_sem_clique_nenhum_a_marca_nasce_no_perfil_que_esta_valendo() -> None:
    """A aba abre com a linha do ativo marcada — e é a verdade, não um enfeite."""
    linhas = _linhas(_pacote(["Primeiro", "Segundo"], ativo="Segundo"))
    assert _marcada(linhas) == ["Segundo"]


def test_a_lista_vazia_nao_inventa_marca() -> None:
    """Sem perfil nenhum, a linha do estado vazio não carrega ``aria-selected``."""
    from hefesto_dualsense4unix.app.actions import profiles_actions

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(profiles_actions, "perfil_que_ela_ativou", lambda: None)
        linhas = _linhas(_pacote([], ativo=""))
    assert len(linhas) == 1 and "aria-selected" not in linhas[0]


def test_a_linha_escolhida_viva_e_a_linha_do_desenho() -> None:
    """A régua gêmea, agora também na dimensão NOVA."""
    aba10 = _gerador()
    for ativo in (True, False):
        for escolhido in (True, False):
            do_desenho = aba10.linha_do_perfil(
                "Elden Ring", "85", "Jogo da Steam · 1245620", ativo,
                "a disputa", escolhido)
            do_produto = a10_perfis._linha_da_lista(
                "Elden Ring", "85", "Jogo da Steam · 1245620", ativo,
                "a disputa", escolhido)
            assert do_produto == do_desenho, (
                f"a linha viva divergiu do desenho (ativo={ativo}, "
                f"escolhido={escolhido}):\n  desenho: {do_desenho!r}\n"
                f"  produto: {do_produto!r}")


def test_o_desenho_marca_a_linha_que_o_editor_abriu() -> None:
    """No mockup, a linha marcada é a que o editor ao lado está mostrando."""
    aba10 = _gerador()
    html = onde.pagina("10-perfis.html").read_text(encoding="utf-8")
    linhas = re.findall(r'<tr class="[^"]*" data-hef-perfil=.*?</tr>', html, re.S)

    marcadas = _marcada(linhas)
    assert marcadas == [aba10.PERFIL_DO_EDITOR], (
        f"o desenho marca {marcadas} e o editor dele abre em "
        f"{aba10.PERFIL_DO_EDITOR!r}")
    assert len(linhas) == len(aba10.PERFIS)


def test_a_folha_pinta_os_tres_estados() -> None:
    """Três regras, três estados. Sem elas o DOM sabe e a tela dela não mostra."""
    html = onde.pagina("10-perfis.html").read_text(encoding="utf-8")
    folha = re.sub(r"/\*.*?\*/", "", html, flags=re.S)

    exigidas = {
        "só ativo": ".tab tr.ativo td{",
        "só escolhido": '.tab tbody tr[aria-selected="true"] td{',
        "ativo+escolhido": '.tab tbody tr.ativo[aria-selected="true"] td{',
    }
    faltando = [k for k, v in exigidas.items() if v not in folha]
    assert not faltando, (
        f"a folha não desenha {faltando} — o estado existe no DOM e não chega "
        f"aos olhos dela")

    assert ("box-shadow:inset 3px 0 0 var(--green),"
            "inset 6px 0 0 var(--purple)" in folha.replace("\n", "")
            .replace("          ", "")), (
        "a linha que está valendo E aberta no editor não mostra a barra dupla")

    assert ':hover:not(.ativo):not([aria-selected="true"])' in folha, (
        "o `:hover` voltou a usar `--sel-bg` sem excluir a linha escolhida — "
        "passar o mouse pela lista fingiria a marca em toda linha")
