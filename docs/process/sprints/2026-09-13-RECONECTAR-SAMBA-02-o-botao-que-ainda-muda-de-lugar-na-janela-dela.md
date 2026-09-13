---
sprint: RECONECTAR-SAMBA-02
estado: feita
onda: A-TERCEIRA-LISTA-DELA
posse:
  RECONECTAR-SAMBA-02:
    - src/hefesto_dualsense4unix/interface/aba01.py
    - src/hefesto_dualsense4unix/interface/hefesto_vivo.py
    - tests/unit/test_o_reconectar_nao_muda_de_lugar.py
    - docs/process/sprints/2026-09-13-RECONECTAR-SAMBA-02-o-botao-que-ainda-muda-de-lugar-na-janela-dela.md
bancada: false
depois_de:
  # 13/09/2026: o `_tique` mora no mesmo `hefesto_vivo.py` de que a
  # FRASES-E-DICAS-01 tira o canal de recado.
  - FRASES-E-DICAS-01
nao_toca:
  - src/hefesto_dualsense4unix/interface/topo.html
  - src/hefesto_dualsense4unix/gui/ponte_da_tela.py
  - src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py
  - src/hefesto_dualsense4unix/interface/mesa_viva.py
---

# RECONECTAR-SAMBA-02 — o botão que ainda muda de lugar e de formato na janela dela

> **ESTADO 2026-09-13: feita** — entrega em
> [agentes/2026-09-13/RECONECTAR-SAMBA-02-opus.md](../agentes/2026-09-13/RECONECTAR-SAMBA-02-opus.md).
> O chip do lugar vazio guarda o vão (`visibility:hidden`), a frase da mesa pousa
> por cima da fileira, e o tique mudo repinta o último estado bom por três tiques
> (`hefesto_vivo.FolgaDoServicoMudo`). No piloto oculto, sobre `e1c7d96b`, o botão
> ia de y 463 a 402 com o serviço mudo e a 429 com a lista vazia; com a cura, 462
> nos dois.

A palavra dela está no índice: *«reconectar controles segue dando pau… falo do
posicionamento e formato dele. ele segue sambando.»*

## §E — O que o estudo mediu (13/09; WebKitGTK 2.52.6 do piloto e Chrome headless, sobre `e7d1dac2`)

1. **A cura de ontem está instalada e vale.** A página da janela dela é idêntica à
   da integração. De 900 a 1920 px de largura, com vista de 770, 809 e 840 px, o
   botão sai numa linha, 159,3 x 34 px, colado à direita; parado 60 s, nada acima
   dele muda. O recibo invisível das fotos das 02:48 não se reproduz mais.
2. **O que ainda o faz sambar é VERTICAL, e vem do estado:**
   * **o tique que não responde** — o estado do daemon espera até 2 s; no
     `except`, o `_tique` pinta `{}`, os quatro lugares viram
     `data-conectado="nao"`, a regra S-04 de `aba01.py` tira os chips com
     `display:none`, a fileira de cartões cai de 129 para 67 px e **o botão sobe
     62 px**, voltando no tique seguinte. O diário dela tem `[daemon mudo] timed
     out` em 09, 10, 12 e 13/09 (os de 07/09 são `[Errno 2]` e `[Errno 104]`, o
     serviço reiniciando);
   * **zero controles** — a frase da mesa vazia entra NO FLUXO, acima dos
     cartões, e desce o botão 27 px (saldo de −35 px).
3. **O comentário acima da regra S-04 afirma o contrário** («a altura da fileira
   não cai»): só vale com um controle cheio. Deixado, a próxima pessoa desfaz a
   cura lendo-o.
4. **Fora da página, sem cura aqui:** o COSMIC ladrilha a janela, e o
   `cosmic-comp` instalado não lê o tamanho mínimo — a foto 4 é a janela com 816
   px de altura, abaixo do mínimo de 855. E as duas viagens de IPC do `_tique`
   seguram o laço do GTK por até 541 ms no piloto e 2006 ms no diário dela, o que
   atrasa a janela quando o compositor muda o ladrilho. Presa à direita, o botão
   anda o que a largura do ladrilho anda: é o desenho, e fica.
5. A fonte do Google (`display=swap`) desloca o botão 5,6 px enquanto não chega.

O estudo inteiro fica na pasta do lote `1309-terceira`.

**ATENÇÃO: os números acima são de ANTES da costura da ALTURA-DA-VISTA-01**, que
tira a faixa do cabeçalho das dez páginas. Remeça sobre a base em que a sua árvore
nasceu.

**REMEDIDO em 13/09/2026, sobre `e1c7d96b`, antes da cura.** Piloto oculto (vista de
1212x809), dublê de `DaemonMudo` com `TimeoutError` na causa: o botão sobe **61 px**
(y 463 → 402, cartão 128 → 67) e, com a lista vazia, o saldo é de **34 px** para
cima (463 → 429). No Chrome, na página publicada, a 1228 e 1300: 464 → 403 e
464 → 430. O diário tem 17 tiques `timed out` em 15 corridas; das 14 que voltaram,
13 duraram um tique e uma durou três.

## §D — Decisões (quem coordena, por delegação)

| decisão | base |
| --- | --- |
| O botão continua à direita e numa linha | a palavra dela de 30/08, citada em `aba01.py` («o reconectar controles vai pra direita…»); a JOGAR-A-FAIXA-QUE-PULA-01, §2 |
| O chip do lugar vazio fica invisível e não clicável, mas deixa de sair do fluxo (`visibility:hidden`), sem número cravado | a rede S-04 («um botão cinza num lugar vazio ainda promete que ali cabe uma escolha»); «quando um valor tem dono, a régua pergunta ao dono» |
| **A frase da mesa vazia vai POR CIMA dos lugares apagados, fora do fluxo** | **a D-07, escolha dela em 04/09: «Uma frase por cima dos lugares apagados.»** ([AS DEZESSEIS DECISÕES](../2026-09-04-AS-DEZESSEIS-DECISOES-DELA-e-as-sprints-que-nascem.md)) — o desenho de hoje a pôs acima; a cura devolve a escolha dela |
| O tique que não responde não apaga os lugares: repinta o último estado bom por uma folga curta e medida; depois dela, a verdade | a queixa dela; a regra da casa de a tela não mentir |
| O ladrilho do COSMIC e o IPC síncrono do `_tique` ficam registrados com número, sem cura nesta sprint | índice, §0 item 4 («mexer o mínimo»); a A-TELA-SAMBA-01 escolheu pular o tique em vez de enfileirar |

## §I — IMPLEMENTA

1. `aba01.py`, a regra S-04 dos chips do lugar vazio: `display:none` →
   `visibility:hidden`. O comentário que afirma que a fileira não cai é
   substituído pelo número medido. Procure antes réguas que exijam o literal.
2. `aba01.py`, `.mesa-notas`: acesa, ela fica por cima dos lugares apagados, fora
   do fluxo; o desenho com controles não muda um pixel.
3. `_tique`: o `TimeoutError` do estado não pinta `{}`. Enquanto as falhas
   seguidas forem menos que N, o tique repinta o último estado bom; na N-ésima,
   pinta a verdade. **N sai do diário dela** (`interface.log`, só leitura): o
   maior número de `[daemon mudo]` seguidos de uma janela que depois voltou. O
   `[daemon mudo]` do diário fica.
4. Na régua `tests/unit/test_o_reconectar_nao_muda_de_lugar.py`: a cena «serviço
   mudo» (dublê levantando `TimeoutError`), a cena «lista vazia com a frase
   acesa», e o clique no centro de um chip escondido, que não pode devolver o
   chip.
5. Regerar e `--publicar 01`.

## §V — VALIDA/CORRIGE — o que morde

* Piloto `--oculta`, retângulo do botão amostrado a cada 100 ms: com o dublê
  mudo, o y do botão não se move (±2 px); sem controles e com a frase acesa,
  também. **Arrancar o `visibility` → o botão sobe ~60 px e reprova; arrancar a
  folga do `_tique` → os lugares apagam no tique mudo e reprova; arrancar o «por
  cima» → o botão desce ~25 px e reprova.**
* `elementFromPoint` no centro do chip escondido cai na `.mascara`.
* Foto em repouso idêntica antes e depois; fotos com o dublê mudo e com a lista
  vazia.
* Perfis conferidos por md5 depois de cada corrida; portões verdes.

## §R — Riscos declarados

* Resíduo de 2 px no WebKit no estado mudo: tolerância declarada, ou o pixel
  achado.
* A página 01 muda em outras sprints desta leva: regerar, nunca mesclar à mão.

**Só o aparelho responde:** se o gesto Reconectar faz o daemon passar dos 2 s na
máquina dela; que ladrilhos o COSMIC dá quando outra janela abre; quatro controles
na mesa, no cabo e no rádio.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| pergunta | resposta |
| --- | --- |
| **por cabo** / **por BT** | não se aplica: é a tela |
| **no perfil** | nada vai ao disco |
| **por controle** | os quatro lugares ficam na mesma altura com ou sem controle |
