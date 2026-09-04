#!/usr/bin/env python3
"""Duas unidades NUNCA mostram a mesma cor — nem no mesmo perfil e estilo.

A REGRA É DELA, 03/09/2026, e vem inteira:

    *"nenhuma cor dos controles nunca pode ser a mesma, mesmo no mesmo perfil e
    estilo de jogo. Dentro da paleta de fps tem que ter variações pra cada
    unidade de controle."*

**NÃO É PREFERÊNCIA ESTÉTICA — É ENDEREÇO.** A barra de luz é a única maneira de
saber, olhando para a mesa, qual controle é qual. Duas unidades com a mesma cor
apagam essa informação exatamente quando ela mais importa: com quatro ligados.

E ELA PEGA UM DEFEITO VIVO, medido no perfil dela em 03/09: a seção GLOBAL do
perfil guarda UMA cor (`leds.lightbar = [40, 80, 180]`), e com
``auto_player_colors`` desligado os quatro controles a recebem — os quatro
iguais. Hoje quem impede é aquele interruptor, e ele é um interruptor: alguém
pode desligá-lo sem perceber o que perde.

A MORDIDA: baixe `GIRO_DE_MATIZ` para `0.0` e
:func:`test_as_quatro_saem_distintas_em_todo_estilo` reprova nomeando o estilo e
a distância; troque a família de qualquer estilo por um cinza claro e a mesma
régua acusa que branco não rende quatro.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.profiles import estilos_de_jogo as estilos


def _pior(cores) -> int:
    return min(estilos._distancia(cores[i], cores[j])
               for i in range(len(cores)) for j in range(i + 1, len(cores)))


# --------------------------------------------------------------------------
# 1. A REGRA DELA, em toda receita
# --------------------------------------------------------------------------
@pytest.mark.parametrize("estilo", [e for e in estilos.ESTILOS if e.chave != "personalizado"],
                         ids=lambda e: e.chave)
def test_as_quatro_saem_distintas_em_todo_estilo(estilo) -> None:
    """As quatro unidades daquele estilo, e nenhuma igual a outra."""
    cores = estilos.as_quatro(estilo)
    assert len(set(cores)) == 4, f"{estilo.rotulo}: cores repetidas em {cores}"
    assert _pior(cores) >= estilos.DISTANCIA_MINIMA, (
        f"{estilo.rotulo}: as duas mais próximas ficam a {_pior(cores)}, e o "
        f"mínimo é {estilos.DISTANCIA_MINIMA}")


def test_toda_receita_rende_quatro_sem_levantar() -> None:
    """Nenhuma família da tabela pode ser escura ou branca demais.

    Foi assim que DUAS receitas caíram na primeira execução, e as duas ensinaram
    coisas diferentes: o Terror com um vinho escuro (as quatro a 61 — abaixo do
    meio da luminância não há espaço), e o Retrô com quase-branco (as quatro a
    **9** — branco não tem matiz para girar nem saturação para variar, e nenhuma
    abertura de família conserta isso).
    """
    ruins = []
    for e in estilos.ESTILOS:
        if e.chave == "personalizado":
            continue
        try:
            estilos.as_quatro(e)
        except ValueError as x:
            ruins.append(f"{e.rotulo}: {x}")
    assert not ruins, "receita(s) com família que não rende quatro:\n  " + "\n  ".join(ruins)


def test_as_quatro_variam_em_matiz_e_nao_so_em_luz() -> None:
    """A variação tem de ser de COR, e não uma escala de cinza da mesma cor.

    **ESTA RÉGUA NASCEU DE UMA MORDIDA QUE NÃO MORDEU.** Zerei `GIRO_DE_MATIZ` e
    os 23 testes ficaram VERDES: o passo de luminância sozinho já separava as
    quatro pela distância RGB, e a régua não tinha como notar que a família
    tinha virado quatro tons do mesmo tom.

    Por que isso importa e não é purismo: o alvo é um **LED difuso atrás de
    plástico leitoso**, e ali a luminância é justamente a dimensão que menos se
    distingue — quatro azuis mais claros e mais escuros, vistos do outro lado do
    sofá, são quatro azuis. A regra dela pede *"variações"*, e variação que só
    existe na conta não cumpre o que ela serve para cumprir: dizer qual controle
    é qual.

    A MORDIDA, agora de verdade: `GIRO_DE_MATIZ = 0.0` e esta função reprova
    nomeando o estilo.
    """
    import colorsys

    ruins = []
    for e in estilos.ESTILOS:
        if e.chave == "personalizado":
            continue
        matizes = [colorsys.rgb_to_hls(*(c / 255 for c in cor))[0]
                   for cor in estilos.as_quatro(e)]
        # A DISTÂNCIA É NO CÍRCULO: 0.98 e 0.02 são vizinhos, não opostos.
        espalhamento = max(
            min(abs(a - b), 1 - abs(a - b)) for a in matizes for b in matizes)
        if espalhamento < 0.02:          # ~7 graus, o piso do perceptível
            ruins.append(f"{e.rotulo}: as quatro cabem em {espalhamento*360:.0f} "
                         "graus de matiz — é a mesma cor em quatro brilhos")
    assert not ruins, (
        "a variação virou escala de luminância, e num LED difuso isso não "
        "separa:\n  " + "\n  ".join(ruins))


# --------------------------------------------------------------------------
# 2. A GARANTIA É MEDIDA, e não prometida
# --------------------------------------------------------------------------
def test_uma_familia_que_nao_rende_levanta() -> None:
    """Devolver um par colidido em silêncio seria o defeito inteiro.

    A função tem de RECUSAR, e a mensagem tem de dizer o que fazer — trocar a
    família —, senão quem esbarrar nela vai procurar defeito na conta.
    """
    branco = estilos.Estilo("x", "Teste", None, "balanceado", (250, 250, 250), 1.0, "")
    with pytest.raises(ValueError, match="não separa quatro unidades"):
        estilos.as_quatro(branco)


def test_o_personalizado_recusa_dizendo_por_que() -> None:
    """`Personalizado` não escolhe cor, e perguntar a dele é erro de quem chama.

    Devolver uma cor qualquer ali seria o estilo que diz *"eu ajusto na mão"*
    passando a mexer na mão dela.
    """
    with pytest.raises(ValueError, match="não escolhe cor"):
        estilos.as_quatro("personalizado")


@pytest.mark.parametrize("fora", [0, 5, -1])
def test_jogador_fora_da_mesa_recusa(fora: int) -> None:
    """A mesa é 1..4. Um índice fora não vira a cor do vizinho."""
    with pytest.raises(ValueError, match="fora da mesa"):
        estilos.cor_da_unidade("fps", fora)


# --------------------------------------------------------------------------
# 3. O QUE A TABELA PROMETE tem de existir no produto
# --------------------------------------------------------------------------
def test_todo_gatilho_da_receita_e_um_modo_real() -> None:
    """A chave do gatilho sai da lista que a aba Gatilhos oferece.

    Digitar `AutoGunn` numa receita passaria calado até alguém escolher aquele
    estilo com o controle na mão — e então o produto mandaria ao aparelho um
    modo que não existe. A lista é LIDA da página publicada, não digitada aqui.
    """
    import pathlib
    import re

    pagina = (pathlib.Path(__file__).resolve().parents[2]
              / "src/hefesto_dualsense4unix/interface/paginas/03-gatilhos.html")
    m = re.search(r'<select class="modo"[^>]*>(.*?)</select>',
                  pagina.read_text(encoding="utf-8"), re.S)
    assert m, "a página Gatilhos não tem lista de modo — a régua ficaria cega"
    reais = set(re.findall(r'<option value="([^"]*)"', m.group(1)))

    ruins = [f"{e.rotulo} -> {e.gatilho!r}" for e in estilos.ESTILOS
             if e.gatilho is not None and e.gatilho not in reais]
    assert not ruins, (
        "receita(s) apontando para modo de gatilho que não existe:\n  "
        + "\n  ".join(ruins) + f"\nos reais: {sorted(reais)}")


def test_todo_degrau_de_vibracao_da_receita_e_real() -> None:
    """O degrau sai de `RUMBLE_POLICY_MULT`, que é o dono deles."""
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    ruins = [f"{e.rotulo} -> {e.vibracao!r}" for e in estilos.ESTILOS
             if e.vibracao and e.vibracao not in RUMBLE_POLICY_MULT]
    assert not ruins, (
        "receita(s) com degrau de vibração inexistente:\n  " + "\n  ".join(ruins)
        + f"\nos reais: {sorted(RUMBLE_POLICY_MULT)}")


def test_a_lista_da_tela_e_a_das_receitas_batem() -> None:
    """Os rótulos das receitas são os que o `<select>` da aba Perfis oferece.

    Sem esta linha, ela escolheria "Ritmo/Música" na tela e o motor procuraria
    uma receita que não existe — o campo voltaria a aceitar e não fazer, que é
    o defeito que o motor veio curar.
    """
    import pathlib
    import re

    pagina = (pathlib.Path(__file__).resolve().parents[2]
              / "src/hefesto_dualsense4unix/interface/paginas/10-perfis.html")
    t = pagina.read_text(encoding="utf-8")
    m = re.search(r'<select[^>]*(?:data-hef|data-campo)="editor\.estilo"[^>]*>(.*?)</select>',
                  t, re.S)
    if not m:
        pytest.skip("o `<select>` do estilo não está na página publicada")
    da_tela = {x.strip() for x in re.findall(r'<option[^>]*>([^<]*)</option>', m.group(1))}
    da_tela.discard("—")
    das_receitas = {e.rotulo for e in estilos.ESTILOS}
    assert da_tela == das_receitas, (
        f"só na tela: {sorted(da_tela - das_receitas)}\n"
        f"só nas receitas: {sorted(das_receitas - da_tela)}")
