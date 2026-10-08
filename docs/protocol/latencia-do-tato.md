# A latência do tato

Quanto tempo passa entre a escrita do relatório de vibração e o motor do DualSense
mexer. Todas as sprints do tato (vibração, luz, som) precisam deste número; sem ele,
«sente atrasado» é opinião. Escrito em 08/10/2026
(`A-LATENCIA-DO-TATO-SE-MEDE-SEM-A-MAO-DELA-01`).

## O instrumento

`scripts/ensaios/latencia_do_tato.py` lê o giroscópio do PRÓPRIO controle, pousado e
parado: a vibração do atuador aparece no giro, e o instante em que o giro sai do ruído é
o instante em que o motor mexeu. Não precisa da mão dela, nem de um segundo aparelho.

```
.venv/bin/python scripts/ensaios/latencia_do_tato.py                     # plano e recusas, sem tocar em nada
.venv/bin/python scripts/ensaios/latencia_do_tato.py --medir \
    --transporte cabo --controle P1 --hidraw /dev/hidrawN --movimento /dev/input/eventM
```

O `--movimento` é o nó «Motion Sensors» do MESMO controle do `--hidraw`. Um controle por
vez; repetir por transporte (`cabo`, `radio`) e por controle (P1 a P4).

## Como mede

1. A linha de base é o giro dos 0,2 s ANTES da escrita: o centro (mediana) e a dispersão
   do desvio em relação a ele.
2. O limiar é `max(0,5 °/s, média + 6 desvios)`, nunca zero.
3. O toque é lido quando dois de três quadros seguidos passam do limiar. A latência é o
   instante do primeiro desse grupo MENOS o instante da escrita DAQUELE toque, dentro da
   janela de 150 ms que termina na escrita do toque seguinte, se houver.
4. Sem desvio, o resultado é «nenhum toque lido» e não entra na mediana; zero nunca é
   devolvido no lugar de «não li».

O relógio da escrita é o `time.time()` imediatamente antes do `os.write`, o mesmo
`CLOCK_REALTIME` do carimbo do evdev. O carimbo do giro é o da CHEGADA do quadro ao
computador: no cabo o quadro chega a cada ~4 ms; no rádio, em rajadas, e a latência do
rádio inclui o intervalo do enlace. É a latência que o JOGO enxerga (do escritor ao
primeiro quadro que mostra o motor), não a do firmware por dentro.

## O que ele recusa

O instrumento que briga com o produto recusa, não anuncia:

| recusa | rc | por quê |
| --- | --- | --- |
| `HOME` é o lar real | 2 | roda em lar de mentira; no lar real migra o perfil dela |
| socket do daemon aceita conexão (o do ambiente ou o de `/run/user/<uid>`) | 2 | o daemon escreve no mesmo hidraw e o relatório dele no meio mediria outra coisa |
| giro da linha de base com pico acima de 5 °/s | 3 | o controle está na mão ou se mexe, não pousado |
| menos de 8 quadros de giro antes da escrita | 4 | não há ruído medido, logo não há medida |

Sem `--medir` nada vai ao aparelho: ele só imprime o plano e o que recusaria agora. Ao
sair, por qualquer caminho, manda o relatório de motor zerado.

## A tabela (preenchida pela bancada)

A tabela é o orçamento de que as sprints de vibração, luz e som falam. O ensaio imprime a
linha pronta; a bancada cola abaixo, com a data. Nenhuma linha foi medida na árvore de
desenvolvimento: ela não toca o aparelho.

| transporte | controle | toques lidos | mediana | p95 | máximo |
| --- | --- | --- | --- | --- | --- |

Datas e condições de cada linha vão em nota abaixo da tabela quando a bancada a preencher
(8 de outubro de 2026: ainda sem linha).
