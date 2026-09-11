# ALTURA-DA-VISTA-01 — a janela passou a seguir a vista, e duas faixas de cromo saíram

**Decisão dela, 09/09/2026: «1 + rodapé».** A altura segue a vista (opção C da
§3), o cabeçalho da página encolhe, **e o rodapé junto** — as duas faixas de
cromo que sobram depois de a altura ficar fluida.

Medido nesta árvore com o daemon VIVO e **dois DualSense na mesa, os dois no
rádio** (`● 2 controles: 0 USB · 2 BT`), janela OCULTA num Xvfb próprio, na
vista maximizada da TV dela: **1918 x 840**.

## O que mudou

### 1. A altura deixou de ser um pixel e virou um `clamp` — `interface/topo.html`

```css
--recuo-do-corpo:16px;
--piso-da-vista:777px;
--teto-da-vista:855px;
--alt-janela:clamp(var(--piso-da-vista),
                   calc(100dvh - var(--recuo-do-corpo) * 2),
                   var(--teto-da-vista));
```

O `body{padding:16px}` passou a ler `--recuo-do-corpo`: o 16 que entrava DUAS
vezes na conta da altura tem um dono só, e é o mesmo que o `ponte_da_tela.py`
transcrevia à mão.

### 2. A faixa de cabeçalho saiu, e a marca e a contagem desceram uma faixa

Eram **60 px** nas dez abas: o logotipo de 46, o `h1` «Hefesto —
DualSense4Unix» e a linha «Gerenciador DualSense para Linux». A razão é a
mesma que tirou o subtítulo da moldura em 08/09 — *a barra já diz «Hefesto», e
tudo o que muda já está DENTRO da janela*. Das 213 px de cromo da `.janela`,
essa faixa era a única parcela que REPETIA a moldura do sistema.

O que ela carregava e **não** era repetição desceu para a linha do alvo:

* o **logotipo dela** (o `.svg` que o `monta.py` lê do arquivo dela), agora
  como marca de 24 px à esquerda de «Selecionar:»;
* a **contagem de controles** («N controles: x USB · y BT»), que é dado vivo
  do daemon, agora à direita, ao lado do perfil ativo.

**O LUGAR DA CONTAGEM É PROPOSTA, NÃO DECISÃO** — está marcado
`PROVISÓRIO — DECISÃO DELA` no `topo.html`, e as fotos abaixo são para ela
decidir. A sprint pedia a proposta com a foto; é isto.

### 3. O rodapé encolheu 12 px, e nenhum botão encolheu

`padding:12px 18px` → `6px 18px`. A faixa media 59 (12 + 34 do botão + 12 + 1
de borda) e mede **47**. O botão continua em `--h-acao` = **34 px**: o que
encolheu foi o ar em volta dele. Encolher o botão seria trocar a barra de
rolagem dela por um alvo de clique menor.

### 4. O piso trocou de dono — `gui/ponte_da_tela.py`

A direção era *o CSS manda e o Python copia*, e a cópia já tinha apodrecido: o
comentário apontava o `--alt-janela` para uma linha dezenove acima de onde ele
morava. Agora:

| quem | manda em |
| --- | --- |
| o **CSS** | quanto a `.janela` usa da tela (`clamp`) |
| o **Python** | o PISO — `PISO_DA_VISTA`, que é o `set_size_request` |

`ALTURA_DO_DESENHO` continua existindo como **o mesmo objeto**, porque dois
arquivos de teste fora desta posse ainda o citam (ver *o que sobrou*).

### 5. Os dois números digitados que passariam a mentir

| onde | era | virou |
| --- | --- | --- |
| `interface/aba09.MIOLO_H` | `564` digitado | `_ponte.MIOLO_NO_PISO` |
| `interface/aba03.TETO_DA_GRADE` | `477` digitado | `MIOLO_NO_PISO - 87` |

`MIOLO_NO_PISO = PISO_DA_VISTA - 2*RECUO_DO_CORPO - CROMO_DA_JANELA` = **634**.
A regra: *um gerador não pode assegurar contra a vista, porque ele roda sem
tela — ele assegura contra o PISO.* O 87 da `aba03` é o que sobreviveu da
medição velha: o vão entre o miolo e a última coluna que coube (564 − 477), que
é do quadro e não da altura.

**E EU SOMEI ANTES DE MEDIR, e errei por 1 px:** escrevi `CROMO_DA_JANELA=141`
de cabeça e a janela devolveu 634 onde a conta prometia 636. O número agora é o
medido, 143, e é o caso APERTADO (a linha do alvo mede 52 em três abas e 51 em
sete). É a mesma cicatriz que o teto da grade já carregava — lá a soma deu 528
contra 477 medidos.

### 6. A régua ganhou a vista dela — `scripts/ensaios/a_janela_cabe_no_que_ela_ve.py`

* **`--vista=N`** — a régua rodava numa vista só, a do piso. Com a altura fixa
  tanto fazia; com a altura fluida é a diferença inteira.
* **a tela que sobra embaixo da `.janela`** passou a contar. Nenhuma régua
  desta casa olhava para lá.
* **o ramo `rola_j` saiu, NOMEADO.** Uma `.janela` que segue a vista jamais
  transborda de si mesma: o ramo passaria a dar verde sobre nada, que é o que
  ele já fez em 09/09.
* **o teto não é tela morta** — ver a mordida 4.

## As dez, antes e depois, na vista dela (1918 x 840)

| | antes | depois |
| --- | --- | --- |
| `--alt-janela` | `777px` | `clamp(...)` → **808** |
| cabeçalho | 60 | **não existe** |
| linha do alvo | 50 / 52 | 51 / 52 |
| tira | 42 | 42 |
| rodapé | 59 | **47** |
| `.miolo` | 562 / 564 | **665 / 666** |
| sobra embaixo da `.janela` | **47** (16 de recuo + **31 mortos**) | **16** |

**No piso (vista 809) a `.janela` sai em 777 — idêntica ao que era.** O
`.miolo` sai em 634/635 contra 562/564, e esse ganho é do cromo, não da vista.

**Quem ganha CONTEÚDO e quem ganha VÃO** — as duas metades, medidas:

| | usa | caixa antes | caixa depois |
| --- | --- | --- | --- |
| 02-controles (estica) | 562 → **647** | 562 | 665 |
| 07-lançadores (estica) | 564 → **648** | 564 | 666 |
| 10-perfis (estica) | 564 → **648** | 564 | 666 |
| 01-jogar | 402 | 562 | 665 |
| 03-gatilhos (fechada) | 385 | 564 | 666 |
| 04-iluminação | 542 | 564 | 666 |
| 05-vibração | 522 | 564 | 666 |
| 06-navegação | 523 | 564 | 666 |
| 08-conexões | 355 | 562 | 665 |
| 09-sistema | 546 | 564 | 666 |

**O preço, com o número, porque vão vazio é queixa dela:** nas SETE que não
esticam o vão no fundo do quadro cresce 102 px, dos quais **31 já estavam na
tela** — fora da moldura, na faixa morta. O saldo é **71 px a mais de vão
DENTRO do quadro**, e é exatamente o cabeçalho mais o rodapé que saíram. A
Iluminação vai de 22 px de vão para 124. **Isso está na foto e é dela decidir.**

## As fotos

| | |
| --- | --- |
| antes | `ALTURA-DA-VISTA-01-antes-04-iluminacao.png` · `...-antes-03-gatilhos.png` |
| depois | `ALTURA-DA-VISTA-01-depois-04-iluminacao.png` · `...-depois-03-gatilhos.png` |

As quatro na vista dela, 1918 x 840, janela oculta, daemon vivo. A tela dela
não recebeu nenhuma janela.

## Qual mordida prova

### Mordida 1 — a cura arrancada do PRODUTO, e a régua reprova as dez

Troquei o `clamp` por `--alt-janela:var(--piso-da-vista)` no `topo.html`,
regerei as dez e publiquei. A régua, na vista dela:

```
REPROVA: 10 aba(s) deixam tela morta embaixo da `.janela`:
  01-jogar.html: sobram 47px embaixo da `.janela` numa vista de 840px, e o
                 recuo do `body` é 16 — 31px de tela que a página não usou
  (… as dez, o mesmo número)
rc=1
```

**Os 31 px são exatamente os que a sprint previa.** Cura devolvida: `rc=0`,
`840-16` nas dez.

### Mordida 2 — a MESMA árvore quebrada, medida no piso, dá PASSA

Sem `--vista`, no mesmo build da mordida 1:

```
PASSA: as 10 abas cabem na janela e usam a vista inteira, com o dado vivo.
rc=0
```

*A régua presa ao piso responde sobre outra JANELA que não a dela.* É a prova
da §4.1 e a razão inteira de o `--vista` existir.

### Mordida 3 — a janela baixa, e a barra volta

`--alt-janela:500px`, regerado e publicado:

```
04-iluminacao.html: DIV.miolo 560>358 — a caixa não cabe no que ela vê
03-gatilhos.html:   DIV.miolo 403>358
REPROVA: 8 aba(s) com barra de rolagem     rc=1
```

A sprint previa `560>287` e `403>287`; a caixa é 358 e não 287 porque o cromo
caiu de 213 para 142 — é a cura aparecendo dentro da própria mordida.

### Mordida 4 — a régua reprovou o desenho aprovado, e eu vi

Na primeira volta, numa vista de **2160** (a TV dela tem o modo 3840x2160) a
régua reprovou as DEZ com *"1289px de tela que a página não usou"*. **Estava
errada:** a `.janela` tinha parado no teto que ela PROMETE parar, e o teto
existe porque vão vazio é queixa dela. A régua passou a perguntar o
`--teto-da-vista` ao CSS e a separar **TETO** (relato) de **MORRE** (vermelho).
Hoje: `2160` → `rc=0`, com a linha `TETO: a .janela parou no teto de 855px e
sobram 1273px de tela`.

### Mordida 5 — o painter vivo alcança a contagem na casa nova

O GERADOR escreveu `2 controles: 1 USB · 1 BT` (a mesa do desenho). A FOTO, com
o daemon vivo, mostra `2 controles: 0 USB · 2 BT` — os dois aparelhos que
estão de fato na mesa, os dois no rádio. **O `.conectado` mudou de faixa e o
piloto continua pintando nele**, pelos mesmos `data-campo="conta"` /
`"conta-b"`.

## O que NÃO verifiquei

* **A MESA TINHA DOIS, NÃO QUATRO, e os dois no RÁDIO.** A `Critério de pronto`
  pede cabo e BT. **O BT está medido; o CABO não** — não havia DualSense no
  cabo nesta bancada, e `bancada.sh status` dizia LIVRE mas isso não põe
  aparelho na mesa. A linha que isso deixa em aberto é estreita e está nomeada:
  a altura que o `.miolo` pede na 03 depende do MODO de cada gatilho, e o modo
  vem do aparelho.
* **A 03 com um bloco ABERTO não passou dos 564 nesta bancada.** A sprint mediu
  **633** com QUATRO na mesa; com dois, abri `#dobra-l2` e `#dobra-r2` por JS e
  o `.miolo` não cresceu um pixel além da caixa. Logo **a prova de que a barra
  de 69 px morre é ARITMÉTICA aqui, não medida**: o `.miolo` na vista dela
  passa de 564 para 666, e 666 > 633 com **33 px de folga**. Quem tiver os
  quatro na mesa fecha essa linha em um comando:
  `scripts/ensaios/a_janela_cabe_no_que_ela_ve.py --vista=840`.
* **Não rodei a suíte.** É de quem coordena, e roda no fim.
* **Não olhei a tela dela.** Toda janela nasceu e morreu no Xvfb da guarda.
* **O `--teto-da-vista` de 855 não foi re-derivado.** Ele vem da §3.1 e do
  `set_size_request`; com o cromo menor ele sobra 81 px sobre a maior demanda
  conhecida. Baixá-lo encurtaria o vão numa tela grande — e devolveria tela
  morta na dela, porque 840 − 32 = 808. É decisão de produto.

## O que sobrou para o próximo

1. **DOIS PORTÕES NASCERAM VERMELHOS NESTA ÁRVORE E NÃO SÃO DESTA SPRINT.**
   `mac-por-oui` e `mac-de-fixture` reprovam desde o commit-base
   (`315d912b`, a cura do som), e reprovam igual no `dev`. A causa é
   `tests/unit/test_o_no_do_radio_conta_como_placa.py:26` e `:28`:

   Os dois `UNIQ` das linhas 26 e 28 são **OUI REAL de fabricante + cauda
   sintética colada** — e é justamente essa forma que o `mac-de-fixture` pega:
   a faixa forjada tem de valer para o endereço INTEIRO, não só para o fim
   dele. (Os valores não vão citados aqui de propósito: o sanitizador desta
   pasta os mascara, e um valor mascarado no laudo confundiria quem for
   conferir. Estão no arquivo, nas duas linhas.)

   **JÁ ESTÁ CURADO NO `dev`, e não por mim: `f59e4ddf`** («os endereços das
   réguas saem da faixa real»), de 21h49 de hoje — depois de esta árvore
   nascer. **Medido aqui:** troquei só esse arquivo pela versão do `dev` e os
   dois portões passam (`12 passed`), depois devolvi o meu. **Logo os dois
   vermelhos somem no merge, sem ninguém fazer nada** — e a decisão de não
   tocar no arquivo estava certa: ele tinha dono, e o dono o consertou.

   É a cicatriz que o `CLAUDE.md` já nomeia — *máscara aplicada nos octetos
   errados*. Os dois valores são identificadores opacos passados a
   `nome_do_sink()`: nada depende do OUI ser real. O conserto é trocar por
   faixa sintética inteira (`02:fe`, `aa:bb:cc` ou `e8:47:3a`), duas linhas.
   **Não toquei: o arquivo é de outra posse e do lote do som.**

2. **`ALTURA_DO_DESENHO` ainda tem dois chamadores**, e é por eles que o nome
   velho sobrevive como apelido do mesmo objeto:
   `tests/unit/test_o_aviso_da_vibracao_cabe_na_aba.py` e
   `tests/unit/test_a_janela_estreita_nao_engole_o_desenho.py`. Quem os tocar
   troca o nome nos dois e apaga a linha do apelido.

3. **O PISO PODE CAIR, e cair remove um penhasco medido.** A área útil da TV
   dela tem 888 px e a janela pede 855 de mínimo — **33 de folga**. Um painel
   ou uma doca 34 px maiores e a janela deixa de caber, sem afordância, porque
   `set_size_request` é mínimo duro. Com a altura fluida a página já degrada com
   barra em vez de se recusar a encolher (mordida 3). **Quanto baixar é decisão
   dela**; deixei o piso onde estava para nenhuma aba ficar pior.

4. **`04-iluminacao: DIV.moldura 225>144` na LARGURA dela.** A régua media a
   1212 e via `153>144`; a 1918 a moldura esconde **81 px** de desenho, não 9.
   **Não é desta cura** — conferi que o CSS da `.moldura` é byte-idêntico ao do
   `HEAD` —, é a largura fluida de 08/09 que ninguém tinha medido na vista dela.
   É da `aba04`.

5. **As SETE abas que não esticam ganharam 71 px de vão** (tabela acima). Se
   ela recusar o vão, o caminho é fazer o último quadro delas ESTICAR (o
   mecanismo `estica` já existe e é o que a 02, a 07 e a 10 usam) — é trabalho
   de aba, não de esqueleto.

## Fora da posse, e por quê

Três arquivos, os três por exigência dos portões sobre a MINHA mudança, nenhum
deles um conserto de trabalho alheio:

| arquivo | o quê | por quê |
| --- | --- | --- |
| `docs/data/o-que-ainda-aponta-para-a-janela.csv` | +2 linhas | o portão `nada-aponta-para-a-janela` exige que toda citação nova a `gui.ponte_da_tela` seja declarada. Veredito `MOTOR-MUDA-DE-CASA`, o mesmo das outras 24 linhas do mesmo alvo |
| `gui/aba_sistema.py` | `aba09.py:247-249` → `539-541` | a citação **já estava errada**: no `HEAD` a linha 247 é `SUFIXO_DA_RAZAO`, e as três classes `.est.ok/.warn/.info` que o comentário nomeia moram em 539-541. O meu deslocamento de linhas a fez cair em branco e o portão a acusou |
| `src/.../interface/paginas/*.html` | as dez republicadas | é o `--publicar` do fluxo `mockup/` → produto, como no `d63bbd73` (a largura fluida). Sem ele a régua desta sprint mediria a página de ontem |

## Como reproduzir

```bash
cd /mnt/Apate/Desenvolvimento/hefesto-voo/ALTURA-DA-VISTA-01-opus && source .envrc-voo
scripts/ensaios/a_janela_cabe_no_que_ela_ve.py --vista=840   # a TV dela
scripts/ensaios/a_janela_cabe_no_que_ela_ve.py --vista=809   # o piso
scripts/ensaios/a_janela_cabe_no_que_ela_ve.py --vista=2160  # o teto
```
