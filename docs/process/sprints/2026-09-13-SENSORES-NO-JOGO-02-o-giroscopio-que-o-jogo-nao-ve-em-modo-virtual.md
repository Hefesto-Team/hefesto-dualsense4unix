---
sprint: SENSORES-NO-JOGO-02
estado: aberta
onda: A-TERCEIRA-LISTA-DELA
posse:
  SENSORES-NO-JOGO-02:
    # PROVISÓRIA — o ESTUDO escreve a posse real antes de qualquer implementação.
    - docs/process/sprints/2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md
bancada: true
depois_de: []
nao_toca:
  - docs/data/ensaios.csv
---

# SENSORES-NO-JOGO-02 — o giroscópio que o jogo não vê em Modo Virtual

Nasce do §7 do laudo
[OS SENSORES ATÉ O JOGO](../2026-09-09-OS-SENSORES-ATE-O-JOGO-o-que-a-bancada-mediu.md),
como a §4 da
[SENSORES-NO-JOGO-01](2026-09-08-SENSORES-NO-JOGO-01-o-giroscopio-e-o-acelerometro-provados-ate-o-jogo.md)
mandava, e responde à pergunta dela na terceira lista:

> *"tenho receio que nossas features não cheguem aos jogos pelo mesmo motivo ou semelhantes"*

([o índice](2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md)).

## §1 — O que a bancada mediu (09/09)

* **Até o vpad, os dois sensores funcionam**, nos dois transportes: 250
  relatórios por segundo, 222 valores distintos de giro.
* **Em Modo Virtual o jogo recebe ZERO:** o SDL abre o vpad por evdev e responde
  `HasSensor=False` para o giroscópio e para o acelerômetro. Um jogo que pergunta
  antes de usar nem chega a ler.
* **Em Modo Nativo chegam:** o mesmo instrumento recebe 96 amostras distintas de
  giro e 586 de acelerômetro por HIDAPI.

## §2 — As perguntas, nesta ordem (o §7 do laudo)

1. **Por que o SDL não abre o `hidraw` do vpad por HIDAPI**, sendo ele `0660` e
   legível? É a pergunta que decide se a cura é barata ou cara. Olhe o que o
   Hefesto põe no ambiente do jogo (a lista IGNORE, o hidraw escondido do Proton,
   o env por jogo), as propriedades do dispositivo virtual que o SDL lê
   (barramento, VID e PID, nome), e o que o SDL da Steam e o do Proton fazem com
   cada uma.
2. **Se não houver caminho por HIDAPI, como o movimento chega ao jogo em
   Virtual** — o nó «Motion Sensors» do vpad existe e publica, mas o SDL o pula
   por desenho.

## §3 — A decisão que já está registrada

Em máscara Xbox 360 e Nintendo Pro não há onde pôr o movimento: o aparelho que a
máscara imita não tem giroscópio. A entrega não pode ser independente da máscara
— é decisão registrada na §2 da SENSORES-NO-JOGO-01, não dívida.

## §4 — O processo (índice da terceira lista, §0)

**ESTUDO primeiro**, só leitura e medição sem aparelho: o fonte do SDL,
`docs/protocol/pilha-steam-input-xpad-sdl.md`, o ensaio
`scripts/ensaios/o_jogo_para_de_ver_o_giro.py`, e o que o lançador põe no
ambiente do jogo. Ele escreve aqui a causa, a cura e a posse real. A implementação
só é despachada se a cura couber sem aparelho; a prova dentro do jogo é da
MESA-DE-QUATRO-01.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** / **por BT** | o laudo mediu zero nos dois, em Virtual |
| **no perfil** | os interruptores por peça já existem (`ControllerSensoresOverride`) |
| **por controle** | o registro de movimento é por controle |
