"""A ABA PERFIS: o que ela manda tem onde cair, e o cabeçalho não é dela.

POR QUE ESTA RÉGUA EXISTE, e o motivo é um erro de MEDIÇÃO, não de código —
02/09/2026:

    a aba emitia a chave ``ativo`` com o nome do perfil que vale, resolvido
    contra o disco. **Nenhuma página tem esse endereço.**
    ``data-(campo|papel|hef)="ativo"`` dá ZERO ocorrências em
    ``interface/paginas/10-perfis.html`` e zero em ``mockup/10-perfis.html``.

    Três réguas chamavam esse valor de *"o chip Perfil ativo"* e provavam nele
    uma cura do marcador órfão. Ficavam verdes sem tocar em nada que ela veja: o
    chip é ``<span class="pa-nome" data-campo="perfil">`` (linha 1035 das duas
    páginas), mora no ``topo.html`` — que é das DEZ abas — e quem o pinta é
    ``pacotes.topo()``, com ``ctx.state.get("active_profile")`` CRU.

A PERGUNTA QUE ESTA RÉGUA FAZ POR ESCRITO, e que ninguém tinha feito:
**este valor tem endereço na página PUBLICADA?** Se não tem, o que ela vê não
mudou — por mais verde que esteja a suíte.

AS QUATRO COISAS QUE ELA COBRA:

1. toda chave emitida tem endereço na página, ou está declarada em
   ``a10_perfis.SEM_ENDERECO`` com a razão medida;
2. ``SEM_ENDERECO`` não guarda quem já tem casa — declaração que envelhece é a
   régua se desligando sozinha;
3. esta aba **não emite** os três campos do cabeçalho. Emiti-los seria o segundo
   dono de ``perfil`` — o defeito fotografado às 04:23 de 02/09 na aba Sistema,
   e a regra que ele deixou está escrita em ``a09_sistema.pacote``: *"um pacote
   de aba só emite endereço DAQUELA página"*;
4. **a dívida do chip, medida pelo caminho do piloto** — ver
   ``test_o_chip_do_topo_ainda_mostra_o_nome_cru_e_isso_e_divida``.
"""
from __future__ import annotations

import re
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import onde, pacotes
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis
from hefesto_dualsense4unix.profiles import loader

PAGINA = "10-perfis.html"  # (noqa-acento) nome de arquivo
CAMPO = re.compile(r'data-(?:campo|papel|hef)="([^"]+)"')

#: A MESA — endereço MASCARADO, faixa sintética da casa. Há dois portões de
#: anonimato nesta árvore e nenhum deles perdoa.
UNIQ = "aabbcc000001"
MESA = [{"pref": "p1", "uniq": UNIQ, "jogador": 1, "cor": "cosmic-red",
         "nome": "Cosmic Red", "via": "USB", "transporte": "usb", "alvo": True,
         "mascara": "DualSense"}]


def _perfis(*nomes: str) -> list[Any]:
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    return [Profile(name=n, match=MatchAny(), priority=100 - i)
            for i, n in enumerate(nomes)]


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Estado de MÓDULO herdado de outro teste não é prova de nada."""
    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ARMADO", None, raising=False)
    monkeypatch.setattr(a10_perfis, "_PINTADO_PARA", "", raising=False)
    monkeypatch.setattr(a10_perfis, "_ULTIMO_TIQUE", 0.0, raising=False)


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Dois perfis, sem escrever no disco.

    SEM ISTO A PASTA É VAZIA: a ``conftest.py`` põe
    ``HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED=1`` em TODO teste, e
    ``load_all_profiles()`` devolve ``[]`` na suíte inteira.
    """
    todos = _perfis("Pragmata", "Sackboy")
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: todos)
    return todos


def _ctx(diz: str | None = "Sackboy") -> Contexto:
    return Contexto(state={"active_profile": diz}, mesa=list(MESA),
                    conectados=list(MESA), estados={})


def _como_o_piloto_pinta(ctx: Contexto) -> dict[str, Any]:
    """As TRÊS LINHAS de ``hefesto_vivo.py``, na ordem em que ele as roda.

    É o que separa esta régua das que erraram: aqui o valor medido é o que o
    ``escrever()`` recebe para pôr no ``data-campo`` da página, e não o que o
    pacote devolveu antes de o cabeçalho entrar.
    """
    bruto = pacotes.pacote_da_pagina(PAGINA, ctx) or {}
    carga = pacotes.normalizar(bruto, {UNIQ: "p1"})
    for chave, valor in pacotes.topo(ctx).items():
        carga["mesa"].setdefault(chave, valor)
    return carga


def _enderecos(publicado: bool) -> set[str]:
    return set(CAMPO.findall(
        onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")))


def _emitidas(carga: dict[str, Any]) -> set[str]:
    fora = set(carga["mesa"])
    for campos in carga["colunas"].values():
        fora |= set(campos)
    return fora


# --------------------------------------------------------------------------
# 1 e 2. TODA CHAVE TEM ONDE CAIR
# --------------------------------------------------------------------------
@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicada"])
def test_toda_chave_emitida_tem_endereco_ou_esta_declarada(
    disco: list[Any], publicado: bool,
) -> None:
    """Órfão calado é o defeito; órfão DECLARADO é inventário.

    **AS DUAS PÁGINAS SÃO COBRADAS, e é de propósito.** A armadilha desta leva é
    curar na BANCADA e o produto continuar lendo a PUBLICADA; uma régua que só
    olhasse o mockup diria "tem endereço" sobre uma tela que ela não vê.

    MORDIDA: devolva ``"ativo": ativo or "—"`` ao ``fora`` de
    ``a10_perfis.pacote`` — é a chave que provocou esta régua — e os dois casos
    reprovam nomeando-a.
    """
    # O QUE ESPERA O ATO DELA SÓ VALE NA PUBLICADA — 03/09/2026. Um campo que o
    # gerador acabou de marcar existe na BANCADA e não na publicada, porque
    # publicar é ato dela. Sem esta linha, marcar campo novo reprovava sempre, e
    # a única forma de ficar verde era publicar — que é o que uma frente não faz.
    # Na bancada a lista NÃO desconta nada: lá o endereço tem de estar mesmo.
    espera = set(a10_perfis.ESPERANDO_A_PUBLICACAO) if publicado else set()
    orfaos = (_emitidas(_como_o_piloto_pinta(_ctx()))
              - _enderecos(publicado)
              - set(pacotes.topo(_ctx()))
              - set(a10_perfis.SEM_ENDERECO)
              - espera)
    assert not orfaos, (
        f"o pacote da 10 manda {sorted(orfaos)} e a página "
        f"{'publicada' if publicado else 'da bancada'} não tem onde pôr.\n"
        "Ou o gerador marca o campo, ou a chave entra em `SEM_ENDERECO` com a "
        "razão medida. Emitir para o vazio não aparece na tela nem no portão — "
        "e um valor sem endereço já foi usado como PROVA de uma cura de tela.")


def test_o_sem_endereco_nao_guarda_quem_ja_tem_casa(disco: list[Any]) -> None:
    """Declaração que envelheceu é a régua desligada sem ninguém decidir isso.

    MORDIDA: ponha em ``SEM_ENDERECO`` um nome que a página tem (``perfis.conta``,
    por exemplo) e este teste o nomeia.
    """
    tem_casa = set(a10_perfis.SEM_ENDERECO) & (
        _enderecos(publicado=True) | _enderecos(publicado=False))
    assert not tem_casa, (
        f"{sorted(tem_casa)} está declarado como sem endereço e a página já tem "
        f"o lugar. Tire da lista: uma declaração velha esconde a próxima.")


def test_o_sem_endereco_nao_declara_quem_a_aba_nao_manda(disco: list[Any]) -> None:
    """A outra ponta: declarar chave que ninguém emite é inventário de fantasma."""
    emitidas = _emitidas(_como_o_piloto_pinta(_ctx()))
    sobrando = set(a10_perfis.SEM_ENDERECO) - emitidas
    assert not sobrando, (
        f"{sorted(sobrando)} está em `SEM_ENDERECO` e o pacote não emite mais. "
        f"Quem parou de emitir tira da lista no mesmo commit.")


# --------------------------------------------------------------------------
# 3. O CABEÇALHO É DAS DEZ ABAS
# --------------------------------------------------------------------------
def test_esta_aba_nao_emite_os_campos_do_cabecalho(disco: list[Any]) -> None:
    """``perfil``, ``conta`` e ``conta-b`` são de ``pacotes.topo()``, não daqui.

    A REGRA É MEDIDA e está escrita em ``a09_sistema.pacote``: *"um pacote de
    aba só emite endereço DAQUELA página. O que é de todas é do dono
    compartilhado, e um nome curto e genérico (`perfil`, `conta`, `estado`) é do
    dono compartilhado até prova contrária."* Ela nasceu de uma foto: a aba
    Sistema emitia ``perfil`` com o rótulo do perfil de BATERIA, chegava antes
    do ``setdefault`` e o cabeçalho inteiro virava travessão.

    **ESTA RÉGUA TAMBÉM FECHA UM ATALHO.** A dívida do teste seguinte tem uma
    cura fácil e errada: fazer esta aba emitir ``perfil`` já resolvido. Isso
    consertaria UMA das dez telas e criaria o segundo dono do cabeçalho — o
    defeito de cima, de volta pela porta da frente.

    MORDIDA: acrescente ``"perfil": ativo`` ao ``fora`` de ``a10_perfis.pacote``
    e este teste reprova.
    """
    bruto = pacotes.pacote_da_pagina(PAGINA, _ctx()) or {}
    invadidos = set(bruto) & set(pacotes.topo(_ctx()))
    assert not invadidos, (
        f"o pacote da aba Perfis emite {sorted(invadidos)}, que é do cabeçalho "
        f"das dez abas. Como o piloto usa `setdefault`, quem emite aqui GANHA "
        f"de `pacotes.topo()` — e as outras nove telas ficam com outro valor.")


# --------------------------------------------------------------------------
# 4. A DÍVIDA DO CHIP — declarada, medida, e ela reprova no dia em que for paga
# --------------------------------------------------------------------------
def test_o_chip_do_topo_ainda_mostra_o_nome_cru_e_isso_e_divida(
    disco: list[Any],
) -> None:
    """O chip "Perfil ativo" **não** passa pelo dono que resolve o nome.

    ``a10_perfis._valendo`` chama o §P1 (``perfil_que_esta_valendo``) e depois
    ``find_by_slug`` contra os perfis do disco, então o que sai dele já é o
    ``p.name`` de uma linha da lista. ``pacotes.topo()`` não faz nada disso: ele
    devolve ``ctx.state.get("active_profile") or "—"``, e o piloto escreve isso
    no ``data-campo="perfil"``.

    **AS DUAS CONSEQUÊNCIAS, medidas pelo caminho do piloto:**

        daemon diz               chip na tela             linhas realçadas
        "Perfil Que Ela Apagou"  "Perfil Que Ela Apagou"  []
        "sackboy"                "sackboy"                ["Sackboy"]

    A primeira é o marcador órfão sobrevivendo no lugar mais visível da tela. A
    segunda é pior: a MESMA tela dá dois nomes para a mesma pergunta.

    **ISTO É UMA DÍVIDA DECLARADA, e a cura mora fora desta aba** —
    ``interface/pacotes/__init__.py``, ``topo()``, que tem de resolver o nome do
    mesmo jeito (ou perguntar a quem já resolve). Ver o teste acima para por que
    a aba **não** deve consertar isto por conta própria.

    SE ESTE TESTE REPROVOU, a dívida foi paga: troque as asserções pelo nome
    resolvido (``"—"`` e ``"Sackboy"``), apague este parágrafo e a nota que
    ficou em ``_valendo``.
    """
    orfao = _como_o_piloto_pinta(_ctx("Perfil Que Ela Apagou"))
    assert orfao["mesa"]["perfil"] == "Perfil Que Ela Apagou", (
        "o chip parou de nomear o órfão — a dívida foi paga; atualize esta "
        "régua e a nota de `a10_perfis._valendo`.")

    caixa = _como_o_piloto_pinta(_ctx("sackboy"))
    assert caixa["mesa"]["perfil"] == "sackboy", (
        "o chip passou a resolver a caixa — a dívida foi paga; atualize esta "
        "régua e a nota de `a10_perfis._valendo`.")
    assert a10_perfis._valendo(_ctx("sackboy")) == "Sackboy", (
        "o dono desta aba deixou de resolver o nome; sem isso a lista volta a "
        "não acender linha nenhuma")
