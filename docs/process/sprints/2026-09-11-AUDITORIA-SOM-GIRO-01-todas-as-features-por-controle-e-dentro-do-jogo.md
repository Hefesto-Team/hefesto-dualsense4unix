---
sprint: AUDITORIA-SOM-GIRO-01
estado: feita
onda: A-LISTA-DE-0911
posse:
  AUDITORIA-SOM-GIRO-01:
    - docs/process/2026-09-11-A-AUDITORIA-DO-SOM-E-DO-GIROSCOPIO.md
cria:
  - docs/process/2026-09-11-A-AUDITORIA-DO-SOM-E-DO-GIROSCOPIO.md
bancada: false
depois_de: []
nao_toca:
  - src/
  - docs/data/mapa-controles.csv
---

# AUDITORIA-SOM-GIRO-01 — áudio e giroscópio, por controle e dentro do jogo

> **ESTADO 2026-09-11: feita** — a auditoria está em
> `docs/process/2026-09-11-A-AUDITORIA-DO-SOM-E-DO-GIROSCOPIO.md`: as duas
> matrizes (12 chaves de áudio e 12 de movimento/toque, `@dualsense`, com o
> degrau de cada célula), a coluna do JOGO em Steam · Heroic · jogo direto, as
> três máscaras, as cinco células que o caderno já ultrapassou, seis buracos com
> endereço e os sete gestos da bancada. **O número que ela decide: das 48
> células, 18 têm o jogo como destino e ZERO estão num degrau de jogo — e os
> 227 ensaios do caderno não declaram ponte nenhuma.** Nenhuma linha de produto
> mudou; o mapa não foi tocado. Entrega em
> `docs/process/agentes/2026-09-11/AUDITORIA-SOM-GIRO-01-opus.md`.

> *"eu preciso de uma auditoria completo no sistema de audio e giroscopio pra*  <!-- noqa-acento: citação literal dela -->
> *ver se todas as features funcionam por controles e se cada uma vai ser*  <!-- noqa-acento: citação literal dela -->
> *reconhecida dentro da steam heroic e jogos diretos."*  <!-- noqa-acento: citação literal dela -->

**Esta sprint NÃO escreve uma linha de produto.** Ela produz UM documento, e a
razão de ser só documento é a colisão: áudio e giroscópio atravessam o daemon,
os subsystems, as integrações e três abas — qualquer cura aqui brigaria com
quatro agentes desta mesma leva. **Quem audita não conserta; quem audita diz
onde doer e com que prova.**

---

## §1 — AS DUAS PERGUNTAS, e elas são diferentes

**Pergunta A — POR CONTROLE.** Cada feature de áudio e de movimento funciona
para CADA controle, independentemente, sem que um desfaça o outro?

**Pergunta B — DENTRO DO JOGO.** Cada uma é reconhecida por um jogo aberto pela
**Steam**, pelo **Heroic** e por um **jogo direto** (binário ou AppImage, sem
lançador)?

**A B é a mais cara e a menos medida desta casa.** A escada de degraus separa
`O APARELHO OBEDECEU` (a saída chegou ao plástico) de `O JOGO RECEBEU` (o
processo do jogo abriu o nó do nosso vpad) e de `O JOGO REAGIU`. **O giroscópio
está em `MONTOU` nos dois transportes.** **FATO SUBSTITUÍDO em 13/09/2026:** o
zero em Modo Virtual era da libSDL2 2.30.0 do sistema; nas bibliotecas dos
runtimes da Steam o vpad expõe os dois sensores, e o SDL pareia o nó «Motion
Sensors» pelo `uniq` (a tabela está na
[SENSORES-NO-JOGO-02](2026-09-13-SENSORES-NO-JOGO-02-o-giroscopio-que-o-jogo-nao-ve-em-modo-virtual.md),
§1). O jogo aberto recebendo e reagindo continua sem medição, com o touchpad
como precedente de repasse íntegro sem reação desde 16/08.

## §2 — DE ONDE SE LÊ, e nada se digita

| a pergunta | quem responde | onde |
| --- | --- | --- |
| o que a casa AFIRMA hoje | o mapa | `docs/data/mapa-controles.csv`, colunas `*_aciona`, `*_ate_onde_foi`, `*_de_onde_sei`, `provado_por` |
| até onde a prova chegou | a régua | `scripts/check_ate_onde_a_prova_chegou.py` |
| o que é de cada degrau | o dono da escada | `scripts/check_paridade_transporte.ESCADA` |
| o que a TELA oferece | as dez páginas | os `data-gesto` de `interface/paginas/` |
| o que o produto FAZ | o fonte | `daemon/subsystems/{alto_falante,bt_mic,luz_do_mic,mic_da_mesa,recado_do_microfone}.py`, `integrations/{alto_falante_bt,canal_do_microfone,eleicao_de_microfone,fontes_de_captura,dualsense_bt_audio,nivel_do_microfone}.py`, `core/virtual_motion.py`, `integrations/uhid_gamepad.py`, `integrations/no_do_vpad.py` |

**`docs/data/mapa-controles.csv` está em `nao_toca`.** Um auditor que corrige o
mapa some com a diferença entre *o que a casa dizia* e *o que a auditoria achou*
— e é essa diferença que vale. Proponha as mudanças de célula no documento, com
`chave`, `transporte`, valor de hoje, valor proposto e a prova. Quem grava é a
bancada dela.

## §3 — O QUE O DOCUMENTO TEM DE TER

1. **A matriz de áudio**, uma linha por feature × transporte: alto-falante
   (rota, volume, fonte `mix`/`sfx`), microfone (captura, mudo, volume, luz),
   fone na saída do controle. Colunas: **cabo · rádio · por controle? · degrau
   de hoje · quem prova**.
2. **A matriz de movimento**: giroscópio, acelerômetro, touchpad (toque, clique,
   cursor) — as mesmas colunas.
3. **A coluna que falta em toda outra página desta casa: o JOGO.** Para cada
   linha, o que acontece em Steam, Heroic e jogo direto — e **como se mediria**,
   se ainda não foi medido. O instrumento do degrau `O JOGO RECEBEU` é objetivo
   e já está especificado: o **inode** do nó do vpad (`stat -c %i`) aparecendo
   em `/proc/<pid>/fd` de um processo da árvore do jogo. **Nunca case por
   caminho** (o minor é reciclado) **nem pelo carimbo de tempo do fd**.
4. **As três máscaras contam.** O que o jogo vê muda com `flavor`
   (DualSense · Xbox 360 · Nintendo Pro) e com o Steam Input no meio. Uma
   afirmação sobre «o jogo recebe giroscópio» sem dizer a máscara não é
   afirmação.
5. **O que cada lançador muda no caminho**: a Steam entra com o Steam Input e
   com `LaunchOptions`; o Heroic e o jogo direto não. Diga o que isso faz com o
   nó do vpad e com o nó de som.
6. **A LISTA DE GESTOS PARA A BANCADA DELA**, no fim, ordenada pelo que
   desbloqueia mais, com o tempo de cada um e quantos controles precisa. É a
   parte que ela vai usar.

## §4 — A ARMADILHA DESTA SPRINT

**`MONTOU` não é «funciona».** É a mentira mais cara desta casa, e a auditoria é
exatamente o lugar onde ela se repete: ler o código, ver o byte sendo montado e
escrever «funciona» é o defeito que 10/09 pagou com a ponte de som que ninguém
construía. **Toda afirmação forte deste documento tem de dizer o degrau, e todo
degrau acima de `MONTOU` tem de citar o ensaio que o fecha.** Onde não houver
ensaio, escreva **«não medido»** — que é informação, e a boa.

## §5 — O QUE É DELA

Tudo o que precisa de orelha, de mão no controle ou de jogo aberto. O documento
não fecha nenhum degrau de aparelho: ele diz **quais gestos fechariam**, e é ela
quem os faz.
