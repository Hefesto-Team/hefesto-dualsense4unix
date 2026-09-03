#!/usr/bin/env python3
"""A RÉGUA DO "Abrir o lançador" — o botão que a casa sabia fazer e não fazia.

DECISÃO 17 DELA, 03/09/2026: o botão LIGA, e o gesto entra em
`hefesto_vivo.PERIGOSOS`, para que a prova automática nunca o clique e nunca
abra a Steam na tela dela. **As duas metades são uma decisão só**, e é por
isso que esta régua cobra as duas no mesmo arquivo: ligar sem o isento seria
ligar contra ela — a `--prova-gesto` roda sozinha e abriria a Steam por cima do
que ela estivesse fazendo.

O FATO QUE CAIU. `SEM_DONO["abrir-lancador"]` afirmava que *"o daemon não tem
método para isso"*. A afirmação é verdadeira pelo IPC e é a **pergunta errada**:
`integrations/steam_launch_options.reopen_steam` abre a Steam desde 23/08/2026,
é função pública, tem os dois caminhos provados (o binário `steam` e o
`xdg-open steam://open/main` de quem a instalou por Flatpak ou Snap) — e tinha
**zero chamadores vindos de `interface/`**. A casa sabia; o botão não chamava.

O QUE ESTA RÉGUA COBRA, e cada item é uma forma de recaída:

1. **O botão tem endereço nos SEIS cartões**, e o `data-v` diz qual — sem ele o
   gesto abriria um lançador escolhido por acaso.
2. **O gesto da Steam CHAMA `reopen_steam`.** É a única metade que faz alguma
   coisa, e é a que um refatorador desatento apagaria sem que a tela mudasse.
3. **A recusa da Steam vira `RuntimeError`**, que é o contrato desta casa para
   "o produto recusou" — e é o que leva a frase à TELA (`_recusou_dizendo`).
4. **Os cinco sem função RECUSAM DIZENDO, e nomeando o lançador.** Um botão que
   abrisse "alguma coisa" para o Heroic seria pior que um que recusa.
5. **`reopen_steam` NÃO é chamada pelos cinco.** É a mordida mais importante:
   um `if` invertido abriria a Steam quando ela clicasse no cartão do RetroArch.
6. **O gesto está em `hefesto_vivo.PERIGOSOS`**, com a chave qualificada pela
   página — a metade que protege a tela dela.

A MORDIDA (as duas saídas estão no relatório desta frente): troque
`qual != desenho.STEAM` por `qual == desenho.STEAM` em `abrir_lancador` e os
itens 2, 4 e 5 reprovam nomeando o defeito; tire a linha
`("07-lancadores.html", "abrir-lancador")` de `PERIGOSOS` e o item 6 reprova.

NENHUM TESTE DAQUI ABRE A STEAM. `reopen_steam` é trocada por um dublê que só
anota que foi chamada — a régua mede a CHAMADA, nunca o efeito. Uma régua desta
casa que abrisse a Steam da máquina dela para provar que sabe abrir a Steam
seria exatamente o que a segunda metade da decisão 17 existe para impedir.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

PAGINA = "07-lancadores.html"


@pytest.fixture(scope="module")
def desenho():
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as dl

    return dl


@pytest.fixture(scope="module")
def a07():
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    return a07_lancadores


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})


class _Espia:
    """O dublê de `reopen_steam`. Conta as chamadas e NÃO abre nada."""

    def __init__(self, devolve: bool = True) -> None:
        self.chamadas = 0
        self.devolve = devolve

    def __call__(self) -> bool:
        self.chamadas += 1
        return self.devolve


@pytest.fixture
def espia(monkeypatch):
    """Troca `reopen_steam` pelo dublê. Sem isto, um teste abriria a Steam."""
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    duble = _Espia()
    monkeypatch.setattr(slo, "reopen_steam", duble)
    return duble


# --------------------------------------------------------------------------
# 1. o endereço está nos seis cartões, e ele diz QUAL
# --------------------------------------------------------------------------
def test_os_seis_cartoes_mandam_o_gesto_e_dizem_qual_lancador(desenho):
    """Um botão sem `data-v` faria o gesto adivinhar pelo TEXTO do botão.

    E o texto é o mesmo nos seis — é a razão de o `Acao.v` existir, e a mesma
    pela qual `Consertar` já o carregava.
    """
    cartoes = desenho.cartoes(None)
    assert len(cartoes) == 6, "a aba tem SEIS cartões; a régua mediria outra tela"
    for cartao in cartoes:
        html = desenho.acoes_html(cartao)
        assert f'data-gesto="{desenho.ABRIR}"' in html, (
            f"o cartão {cartao.chave!r} tem 'Abrir o lançador' sem endereço — o "
            f"clique não chega ao Python e some")
        assert f'data-v="{cartao.chave}"' in html, (
            f"o botão do cartão {cartao.chave!r} não diz qual lançador é")


def test_o_botao_da_steam_tem_endereco_nos_quatro_estados_do_cartao(desenho):
    """Os quatro estados do cartão da Steam trocam a FILEIRA inteira.

    Ligar só o estado que o HTML estático mostra deixaria o botão morto nos
    outros três — e a fileira é pintada, então o defeito seria mudo.
    """
    lidas = {
        "primeira meia volta": None,
        "Steam ilegível": desenho.Leitura(erros=("não abriu o vdf",)),
        "com jogo faltando": desenho.Leitura(
            com_wrapper=("1",), instalados=2,
            reparaveis=(("2", "Um jogo", "nunca recebeu o atalho"),)),
        "tudo em ordem": desenho.Leitura(com_wrapper=("1",), instalados=1),
    }
    for estado, lida in lidas.items():
        html = desenho.acoes_html(desenho.cartao_da_steam(lida))
        assert f'data-gesto="{desenho.ABRIR}" data-v="{desenho.STEAM}"' in html, (
            f"o cartão da Steam em '{estado}' perdeu o endereço do botão")


# --------------------------------------------------------------------------
# 2, 3. o gesto da Steam CHAMA quem sabe abrir — e recusa dizendo quando não dá
# --------------------------------------------------------------------------
def test_o_gesto_da_steam_chama_reopen_steam(a07, ctx, espia, desenho):
    """A metade que FAZ. Sem esta régua, apagar a chamada não muda a tela.

    A MORDIDA: troque `qual != desenho.STEAM` por `qual == desenho.STEAM` em
    `abrir_lancador` e este teste reprova dizendo que a Steam não foi chamada.
    """
    a07.abrir_lancador(ctx, {"gesto": desenho.ABRIR, "v": desenho.STEAM}, None)
    assert espia.chamadas == 1, (
        f"o botão da Steam chamou `reopen_steam` {espia.chamadas} vez(es) — o "
        f"gesto voltou sem abrir nada e quem clicou conclui que funcionou")


def test_a_steam_que_nao_abre_recusa_dizendo(a07, ctx, monkeypatch, desenho):
    """`reopen_steam` devolve `False` quando não há `steam` nem `xdg-open`.

    O contrato desta casa para "o produto recusou" é `RuntimeError`, e é ele
    que leva a frase à tela. Engolir o `False` seria o botão que aceita o
    clique e não faz nada — que é o defeito com nome desta casa.
    """
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    monkeypatch.setattr(slo, "reopen_steam", _Espia(devolve=False))
    with pytest.raises(RuntimeError) as erro:
        a07.abrir_lancador(ctx, {"gesto": desenho.ABRIR, "v": desenho.STEAM}, None)
    frase = str(erro.value)
    assert "steam" in frase.lower() and "xdg-open" in frase, (
        f"a recusa não diz o que faltou: {frase!r}. Sem os dois nomes ela não "
        f"tem como conferir por que o botão não abriu.")


def test_o_clique_sem_qual_lancador_e_recusa_e_nao_palpite(a07, ctx, espia,
                                                           desenho):
    """`data-v` vazio não vira "abre a Steam, vai que é ela".

    É o mesmo contrato do `_appid_do_clique`: `ValueError` é clique inválido, e
    um palpite aqui abriria um lançador que ela não pediu.
    """
    with pytest.raises(ValueError):
        a07.abrir_lancador(ctx, {"gesto": desenho.ABRIR, "v": ""}, None)
    assert espia.chamadas == 0, "o clique sem endereço abriu a Steam mesmo assim"


# --------------------------------------------------------------------------
# 4, 5. os cinco sem função recusam DIZENDO — e não abrem a Steam por engano
# --------------------------------------------------------------------------
def test_os_cinco_sem_funcao_recusam_nomeando_o_lancador(a07, ctx, espia,
                                                         desenho):
    """Um botão que mente é pior que um botão que recusa.

    O produto sabe ONDE eles estão (`_onde_estao_os_lancadores` devolve o
    caminho inteiro) e **não sabe abri-los**: não há função no produto que abra
    o Heroic, o Lutris, o RetroArch, o Dolphin ou o mGBA, e o Flatpak não é
    aplicativo. A recusa nomeia o lançador para ela saber de qual cartão veio.
    """
    assert len(desenho.SEM_FONTE) == 5, "a lista dos sem censo mudou de tamanho"
    for item in desenho.SEM_FONTE:
        with pytest.raises(RuntimeError) as erro:
            a07.abrir_lancador(ctx, {"gesto": desenho.ABRIR, "v": item.chave}, None)
        assert item.nome in str(erro.value), (
            f"a recusa do {item.chave!r} não nomeia o lançador: "
            f"{str(erro.value)!r}")


def test_nenhum_dos_cinco_abre_a_steam(a07, ctx, espia, desenho):
    """A MORDIDA CENTRAL: um `if` invertido abriria a Steam pelo RetroArch.

    Troque `qual != desenho.STEAM` por `qual == desenho.STEAM` em
    `abrir_lancador` e este teste reprova — que é o que se quer: o defeito é
    invisível na tela (a Steam abrindo parece "funcionou").
    """
    for item in desenho.SEM_FONTE:
        with pytest.raises(RuntimeError):
            a07.abrir_lancador(ctx, {"gesto": desenho.ABRIR, "v": item.chave}, None)
    assert espia.chamadas == 0, (
        f"clicar nos cinco cartões sem função abriu a Steam {espia.chamadas} "
        f"vez(es) — a tela dela ganharia uma janela que ela não pediu")


# --------------------------------------------------------------------------
# 6. a segunda metade da decisão dela: a prova automática NÃO clica este botão
# --------------------------------------------------------------------------
def test_o_gesto_esta_entre_os_perigosos(desenho):
    """Sem isto, `--prova-gesto` abriria a Steam na tela dela a cada volta.

    A CHAVE É QUALIFICADA PELA PÁGINA, e o `PERIGOSOS` já explica por quê:
    `modo` na Navegação mexe no cursor dela e `modo` nos Gatilhos é inócuo. Uma
    lista por nome cru trataria os dois igual.

    A MORDIDA: tire a linha `("07-lancadores.html", "abrir-lancador")` de
    `hefesto_vivo.PERIGOSOS` e este teste reprova.
    """
    from hefesto_dualsense4unix.interface import hefesto_vivo

    assert (PAGINA, desenho.ABRIR) in hefesto_vivo.PERIGOSOS, (
        "o `abrir-lancador` saiu dos PERIGOSOS — a prova automática voltaria a "
        "poder abrir a Steam por cima do que ela estiver fazendo, e a decisão "
        "17 dela pede as DUAS metades")


def test_a_prova_automatica_pula_o_botao_e_nao_reprova_por_isso(desenho):
    """A CONSEQUÊNCIA, e não a lista: o botão fica de fora dos cliques.

    Estar em `PERIGOSOS` é o MEIO; o fim é `_alvos_a_clicar` mandá-lo para os
    PULADOS. E a segunda metade importa tanto quanto: `_cobertura_dos_gestos`
    NÃO pode reprovar por ele ter ficado de fora — senão a saída seria tirá-lo
    dos perigosos, que é o inverso da decisão dela.
    """
    import pacotes

    from hefesto_dualsense4unix.interface import hefesto_vivo, onde, regua_do_mockup

    da_pagina = regua_do_mockup._gestos_cravados(
        onde.pagina(PAGINA).read_text(encoding="utf-8"))
    assert desenho.ABRIR in {g.nome for g in da_pagina}, (
        "a página não oferece o `abrir-lancador` — a régua mediria o vazio")
    registrados = {n for (p, n) in pacotes.GESTOS if p in (PAGINA, "*")}
    alvos, pulados = regua_do_mockup._alvos_a_clicar(
        da_pagina, registrados, PAGINA, hefesto_vivo.PERIGOSOS)
    assert desenho.ABRIR not in alvos, (
        "a prova automática CLICARIA o `abrir-lancador` — e a Steam abriria na "
        "tela dela")
    assert any(desenho.ABRIR in str(x) for x in pulados), (
        f"o `abrir-lancador` não foi para os pulados: {sorted(pulados)}")
    faltou = regua_do_mockup._cobertura_dos_gestos(
        da_pagina, registrados, alvos, pulados)
    assert not faltou, (
        f"a cobertura reprova por causa do botão isento: {faltou}. A saída "
        f"seria tirá-lo dos perigosos, que é o inverso da decisão dela.")


def test_o_botao_saiu_do_sem_dono(a07, desenho):
    """Um botão não pode ter dono e ser declarado sem dono na mesma carga.

    `sem_dono` é o que a tela usa para marcar o que o produto não faz. Deixar o
    `abrir-lancador` lá depois de ligá-lo faria a aba declarar contra si mesma.
    """
    assert desenho.ABRIR not in a07.SEM_DONO, (
        "o `abrir-lancador` tem dono agora e continua declarado sem dono")
    assert "criar-perfil" in a07.SEM_DONO, (
        "o `criar-perfil` continua sem dono por decisão (é da aba Perfis) — se "
        "ele sumiu daqui, a declaração se perdeu junto")
