#!/usr/bin/env python3
"""Os números que valem em MAIS DE UMA aba. Dono único, nunca digitados duas vezes.

POR QUE ESTE ARQUIVO EXISTE, e a pergunta é dela, em 31/08/2026:

    "consegue pensar em como arrumar a distância horizontal da primeira coluna
     pra termos uma largura universal ali que funcione bem? tem algo que deixa
     estranho essa área da primeira coluna."

ELA VIU CERTO, E O ESTRANHO É MEDÍVEL. Só TRÊS abas têm coluna de rótulos —
Gatilhos, Iluminação e Vibração —, e as três chegaram a números diferentes:

    aba            coluna   gap   maior rótulo   sobra   o texto acaba em
    03 Gatilhos     138px   12px      77px       61px   x=542
    04 Iluminação   132px   16px     129px        3px   x=536
    05 Vibração     132px   16px     126px        6px   x=536

Dois defeitos, e o segundo é o que ela sentiu sem medir:

1. A SOBRA VAI DE 3 A 61px. Na Iluminação o rótulo quase encosta na divisa; na
   Gatilhos ele nada em espaço vazio. É a mesma coluna, em três larguras.
2. O TEXTO ACABA EM x DIFERENTES — 542 numa, 536 nas outras. Seis pixels, e ela
   repara em dois: trocar de aba MOVE a coluna, que é exatamente o desconforto
   que a janela de altura única nasceu para matar (*"sair clicando entre as abas
   causa muito desconforto, pq muda tudo"*, 27/08).

POR QUE UM ARQUIVO NOVO, e não o `monta.py`: ele está CONGELADO em 31/08 porque
há dois agentes na mesma árvore, e quem salvar por último apaga o outro. Três
cópias do mesmo número seria o defeito que esta casa mais combate; um arquivo
novo, que só eu toco, é a saída que respeita as duas coisas. **Quando o
congelamento sair, este conteúdo vai para o `monta.py`.**
"""

#: O MAIOR RÓTULO DE CADA ABA, medido no Chrome em 31/08/2026. É por ABA, e não
#: um número só para as três — e isso foi ela quem corrigiu, olhando a foto:
#:
#:     "diminui a largura da primeira coluna" (a da Iluminação, apontada em
#:      verde na tela: *"primeira coluna que tem controle, modelo..."*)
#:
#: EU TINHA FEITO UMA LARGURA ÚNICA PARA AS TRÊS, e ela estava errada pela
#: metade. O pedido original era outro — *"tem algo que deixa estranho essa área
#: da primeira coluna"* — e a causa era o RESPIRO ir de 3 a 61px entre abas. Uma
#: largura única igualou o respiro, mas ao preço de dar a TODAS a largura da mais
#: exigente: a Iluminação, cujo maior rótulo tem 73px, ficou com uma coluna de
#: 138 e **65px de vão inútil**. Trocar um estranho por outro não é curar.
#:
#: O QUE É UNIVERSAL É O RESPIRO, e só ele. A largura é conteúdo, e conteúdo é
#: de cada aba. As três continuam lendo como a mesma casa porque o ar entre o
#: fim do texto e a divisa é o mesmo nas três; o que muda é onde o texto começa,
#: e isso ninguém compara entre telas que não estão lado a lado.
#:
#: O comando que mede, e ele não envelhece:
#:     [...document.querySelectorAll('.miolo .rotulos .sec-rot')]
#:       .map(e => e.getBoundingClientRect().width)
MAIOR_ROTULO = {
    "03-gatilhos": 77,      # "Efeito pronto"
    "04-iluminacao": 73,    # "Controle"
    "05-vibracao": 126,     # "Força da vibração"
}

#: O respiro entre o fim do rótulo e a divisa da coluna. É o único número
#: ESCOLHIDO aqui, e o único que vale nas três: ele é o mesmo `--r-passo` que a
#: Gatilhos usa entre linhas, e o ar horizontal e o vertical serem iguais é o
#: que faz a coluna ler como uma caixa em vez de duas medidas que por acaso
#: ficaram perto.
RESPIRO_DO_ROTULO = 12


def larg_rotulos(aba, com_glifo=False):
    """A largura da coluna de rótulos daquela aba.

    `com_glifo=True` só na Gatilhos, onde o L2/R2 ocupa uma trilha própria à
    esquerda do rótulo (decisão dela de 31/08: *"o L2 e o R2 deveriam controlar
    a seção"*). Os três — glifo, vão e rótulo — cabem na conta.
    """
    if aba not in MAIOR_ROTULO:
        raise SystemExit(f"ERRO: não sei o maior rótulo de {aba!r}. Meça antes de "
                         f"usar: um número chutado aqui corta ou quebra a palavra.")
    extra = (GLIFO_DA_SECAO + VAO_DO_GLIFO) if com_glifo else 0
    return extra + MAIOR_ROTULO[aba] + RESPIRO_DO_ROTULO


#: O VÃO ENTRE A COLUNA DE RÓTULOS E A PRIMEIRA COLUNA DE CONTROLE. Ele estava
#: em 12 na Gatilhos e 16 nas outras duas. Este SIM é universal: ele é o mesmo
#: vão que separa duas colunas de controle, e ter dois vãos diferentes na mesma
#: fileira é o que fazia a primeira coluna ler como se fosse de outra tabela.
GAP_DAS_COLUNAS = 16

#: O GLIFO QUE TITULA A SEÇÃO na aba Gatilhos (o L2 e o R2), e o vão dele até o
#: rótulo. Moram aqui porque entram na conta da largura acima: na Gatilhos a
#: coluna é [glifo][vão][rótulo], e os três têm de caber nos mesmos px que as
#: outras duas gastam só com o rótulo.
GLIFO_DA_SECAO = 36
VAO_DO_GLIFO = 10
