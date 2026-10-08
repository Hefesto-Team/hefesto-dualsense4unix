# O que o jogo manda ao controle por tiro

Quantos relatórios de saída um jogo de DualSense escreve no controle a cada tiro, e de que
tipo. Escrito em 08/10/2026. Os emuladores
de PS5 mostram o que o jogo PODE pedir; nenhuma fonte pública dá o que ele pede de fato, e
rodar um jogo de PS5 num emulador exige o jogo tirado de um console desbloqueado, coisa que a
casa não faz. Medir no PC, com um jogo que fala DualSense (o PRAGMATA), é o caminho legal.
Duas decisões esperam este número: «o jogo manda o gatilho uma vez por arma» e «rearmar por
tiro só se um jogo fizer isso».

## O instrumento

`scripts/ensaios/contar_o_que_o_jogo_manda.py`, em duas metades:

```
.venv/bin/python scripts/ensaios/contar_o_que_o_jogo_manda.py --ler gravacao.jsonl \
    --jogo PRAGMATA --transporte cabo --controle P1          # conta uma gravação, em qualquer lugar
.venv/bin/python scripts/ensaios/contar_o_que_o_jogo_manda.py --gravar 120 --saida gravacao.jsonl
                                                              # no aparelho: o daemon com a escuta
```

O **contador** (`--ler`) é puro: lê a gravação e imprime a tabela. O **gravador** (`--gravar`)
roda o daemon do produto no próprio processo, em lar de mentira, com uma escuta no vpad que
anota cada `UHID_OUTPUT` no instante em que chega, ANTES da deduplicação do produto (o produto
entrega ao sink só o bloco que mudou, então contar na saída dele subconta). O jogo atira pelo
físico que o daemon liga ao vpad; um vpad que só ouvisse não teria entrada. Nada do produto
muda: a escuta só anota e repassa, e sai no fim da gravação. O gravador recusa o `HOME` real e
o daemon no ar, como o ensaio da latência (`docs/protocol/latencia-do-tato.md`): o serviço do
daemon para antes, porque durante a gravação o ensaio é o daemon.

Pelo gadget USB o jogo não passa pelo `UHID_OPEN`, e a terceira pergunta sai «sem dado».

## A gravação

Linhas JSON, uma por evento:

| tipo | campos | o que é |
| --- | --- | --- |
| `saida` | `t`, `corpo` (hex) | o report 0x02 sem o byte do id, como o vpad o recebe |
| `abriu` | `t` | o jogo abriu o controle (`UHID_OPEN`) |
| `audio` | `t`, `energia` | energia do monitor dos canais 3 e 4 (a ponte já o captura) |
| `tiro` | `t` | marca explícita de tiro |

Os tiros são as marcas; sem elas, as rajadas de energia do áudio (uma amostra curta por bala,
no PS5, separadas por 80 ms de silêncio); sem nenhum dos dois não há «por tiro», só «por
segundo», e a saída diz «sem dado». A janela de um tiro vai do instante dele ao do seguinte
(0,5 s no último).

## O que se conta

Por categoria (`gatilho_direito`, `gatilho_esquerdo`, `luz`, `luzes_de_jogador`, `motores`,
`audio_do_jogo`): o total, a média por segundo e o pico em 1 s. Uma categoria só conta se a
flag do report a liga (o byte do bloco sozinho não vale). Mais as três perguntas:

- blocos de gatilho por tiro (mediana e máximo);
- o jogo escreve Off e o mesmo efeito em menos de 4 ms: sim ou não (Off é o modo 0x00 ou o
  0x05 oficial; o mesmo efeito é o bloco igual ao último ativo do mesmo lado; sem nenhum bloco
  de gatilho na gravação, «sem dado»);
- o jogo escreve o gatilho nos primeiros 0,5 s depois de abrir o controle: sim ou não (0,5 s é
  a graça do vpad: o que o jogo escreve antes desse prazo, o produto hoje descarta).

## O resultado (preenchido por quem mede no aparelho)

O contador imprime as linhas prontas.
Nenhuma linha foi medida na árvore de desenvolvimento: ela não toca o aparelho nem joga.

| jogo | transporte | controle | categoria | total | por segundo | pico em 1 s |
| --- | --- | --- | --- | --- | --- | --- |

As três respostas, quando houver uma sessão medida: (8 de outubro de 2026: ainda sem sessão).
