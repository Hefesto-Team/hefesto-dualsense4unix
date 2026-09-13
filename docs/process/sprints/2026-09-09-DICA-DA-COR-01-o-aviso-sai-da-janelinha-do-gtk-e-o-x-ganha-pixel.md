---
sprint: DICA-DA-COR-01
estado: aberta
posse:
  DICA-DA-COR-01:
    - src/hefesto_dualsense4unix/interface/aba04.py
    # 13/09/2026: o pacote da 04 e o `topo.html` saíram da posse — o refazer
    # desta sprint é só o X, no CSS de `aba04.py` (ROTA CORRIGIDA abaixo).
    - tests/unit/test_o_x_do_vizinho_e_quadrado.py
cria:
  # 13/09/2026: o ensaio abaixo não nasce mais (a metade da dica fechou pela
  # TOOLTIP-C1); fica declarado só porque o corpo antigo o cita.
  - scripts/ensaios/a_dica_da_cor_nao_e_do_gtk.py
  - tests/unit/test_o_x_do_vizinho_e_quadrado.py
# 13/09/2026: o X se mede no WebKit do piloto; a metade que pedia o compositor
# dela — o pisca da dica — fechou pela TOOLTIP-C1.
bancada: false
depois_de:
  # A lista dela de 11/09 vem antes: a ILUMINACAO-PALETA-01 tira três tons
  # e o seletor livre da MESMA guia de `aba04.py`. A dica da cor se escreve
  # sobre a guia que sobrar, e não sobre a de ontem.
  - ILUMINACAO-PALETA-01
  # E A GRADE VEM ANTES DA DICA, pela mesma razão levada um passo adiante:
  # a ILUMINACAO-GRADE-01 muda a LARGURA da coluna (decisão dela de 11/09,
  # «estreitar a grade de verdade»). Uma dica posicionada sobre a coluna de
  # hoje nasceria fora do lugar amanhã.
  - ILUMINACAO-GRADE-01
  # SERIALIZADA PARA DEPOIS DA SEGUNDA LISTA DELA — 11/09/2026, e é o
  # mesmo precedente da lista anterior: a queixa VIVA vem primeiro. As
  # frentes abaixo reescrevem o TEXTO dos arquivos que esta sprint
  # também toca; medir ou desenhar sobre a prosa de ontem seria medir o
  # mundo de ontem — e a costura viraria «a última a gravar vence».
  - ESQUELETO-C2
  - LINGUA-A4
  # 13/09/2026: a FRASES-E-DICAS-01 regera a página 04 e enxuga a dica do tom
  # tomado no pacote; o X se mede sobre a página que ela deixar.
  - FRASES-E-DICAS-01
---

> **ROTA CORRIGIDA — 13/09/2026, e ela vence tudo abaixo** (triagem das
> branches entregues). **A entrega `65838cf4` NÃO se costura.** A metade da DICA
> já está dentro por outro caminho, e maior: a TOOLTIP-C1 (`b2ac44ce`, 11/09)
> colhe todo `title` para a dica da própria página nas dez abas
> (`DICA_DA_CASA`, em `hefesto_vivo.py`) — é o «as dez abas de uma vez» da
> decisão dela. Costurar criaria um segundo mecanismo ao lado, e a branch é
> anterior à paleta de 11 tons. **A metade do X continua valendo, e é o que se
> refaz:** `aba04.py` ainda tem `inset:5px` no X do tom tomado, e ele mede 4,17 x
> 14 px na janela como ela abre (1212 x 809) — uma tira, não um X. A cura: o X
> centrado e quadrado, com o teto de 12 px da branch como referência, medido no
> WebKit do piloto; regerar e `--publicar 04`. A mordida devolve o `inset:5px` e
> vê a régua reprovar.

> **ESTADO 12/09/2026: continua ABERTA, e o motivo não é falta de
> trabalho.** Ela foi ENTREGUE em `voo/DICA-DA-COR-01-opus` e **não está na costura** —
> medido com `git cherry` contra `onda/0911c`, que não a tem:
>
>   · `65838cf4ef91` fix(iluminacao): a explicação da cor sai da janelinha do GTK, e o X ga
>
> Ela ficou de fora da arrumação de estados de 12/09 DE PROPÓSITO:
> carimbá-la `feita` porque existe uma branch faria o trabalho
> desaparecer — ninguém mais abriria essa branch. **O que falta é a
> costura, não o código.**

> *"com o mouse parado na frente da cor ele fica piscando e tirando o aviso e voltando"* <!-- noqa-acento: citação literal dela -->


> **DECIDIDO POR ELA, 09/09/2026: «As dez abas de uma vez».** A cura não para
> nos 56 `title` da guia — os **660** das dez páginas publicadas saem da
> janelinha do GTK na mesma leva (03-gatilhos 195, 08-conexões 124,
> 04-iluminação 97, e as sete restantes). A §3 continua valendo para o
> mecanismo; o que muda é o ESCOPO, e com ele o preço: cada aba que ganha dica
> própria é superfície de tela nova, e a PROVA-DE-TELA-01 pede o olho dela em
> cada uma. Divida em passos por aba, com foto antes e depois, e não publique
> as dez de uma vez.
>
> O X ganhar pixel continua sendo a metade que NÃO pode esperar: com zero de
> largura na janela ao abrir, tirar o `title` sem dar corpo ao X deixaria a
> tela sem NENHUM canal dizendo de quem é a cor.

# DICA-DA-COR-01 — o aviso sai da janelinha do GTK, e o X ganha pixel

**É a segunda vez que ela reporta este sintoma.** A primeira foi em 06/09
(*"algo ativa o tooltip mas ele se desativa"*) <!-- noqa-acento: citação literal dela -->
e a cura de então — o alvo `atributo` do pintor deixando de reescrever `title`
com o mesmo valor — está viva e **medida como suficiente para o que ela curava**.
Ela não alcança este caso porque **este caso não passa pelo DOM**.

## §1 — O que ela viu, e o que está MEDIDO

**O aviso é a janelinha NATIVA do GTK, e não um elemento da página.** Medido em
09/09/2026, com o produto vivo (os quatro controles, dois no cabo e dois no
rádio) numa `Xvfb` própria, o ponteiro parado sobre o tom que o P3 tomou:

| o que | medido |
| --- | --- |
| a janela do aviso | **uma janela X11 à parte**, `498x47+0+488`, irmã da janela do Hefesto na raiz — não é nó da página |
| a fonte e a cor | as do **tema GTK**, não as da folha do produto: fundo preto liso, sem a `--elevated` nem a `--linha` das dez abas |
| o texto | `P3 (Starlight Blue) já está neste tom — duas peças nunca ficam da mesma cor.` — o `title` que `a04_iluminacao.fileira_de_tons` escreve |
| onde ela nasce | em **`x=0`**, a borda esquerda da janela, a 189 px do botão que a pediu: o GTK centra a caixa na área da dica e a caixa é larga demais, então ela bate na borda e para lá |
| o que ela cobre | **a fileira de baixo** — «Brilho» na foto do instrumento, «Jogador» na foto dela. É a segunda queixa, e ela é geométrica, não de texto |

Fotos do instrumento: a dica nativa em
`pisca-11-dica-zoom.png`, a fileira de tons em `pisca-13-linha-p1.png`
(o caminho completo vai no relatório desta sprint; os PNG são de scratchpad e
não sobrevivem à sessão — o que sobrevive é o ensaio da §4, que os refaz).

### E o que ISSO exclui — três medições, todas negativas

1. **o DOM não muda.** `hefesto_vivo.py --oculta --abre 04 --conta-mutacoes 100`,
   com os quatro na mesa: **0 mutações em 100 tiques (10,1 s)**, `0.0 por
   tique`. A medição do batedor foi refeita aqui, com o daemon vivo e os quatro
   nós hidraw abertos, e deu o mesmo número;
2. **o pintor não é o culpado.** A dica nativa aberta com o **piloto vivo
   pintando 10 vezes por segundo**, ponteiro parado, 15 s de vigia a 33 Hz sobre
   as janelas da raiz X: **abre em 0,529 s e fica** — 465 de 482 amostras com a
   dica na tela, **1 troca abre/some em 15 s** (a de nascer);
3. **a página estática também não pisca.** A `04-iluminacao.html` publicada,
   `WebKit2.WebView` cru, **sem piloto nenhum**: `query-tooltip` dispara **2
   vezes**, a dica abre em 0,503 s e fica 11,5 s. 1 troca, a de nascer.

**Nada que esta casa escreve reproduz o pisca.**

## §2 — A causa, com o número

**A hipótese que recebi ficou de pé, e ficou mais estreita:** o aviso é a dica
nativa do WebKitGTK/GTK, e o pisca é dela — fora do DOM, fora do nosso
JavaScript. O que as três medições da §1 acrescentam é **quanto** fora: a única
variável que sobra entre o instrumento que NÃO pisca e a tela dela que pisca é
**o compositor**.

```
o instrumento   Xvfb + X11 puro, sem gerenciador de janelas   → 1 troca em 15 s
a tela dela     COSMIC + XWayland                             → pisca em laço
```

E ela roda sob XWayland por decisão do instalador, não por acaso:

```
~/.local/share/applications/hefesto-dualsense4unix.desktop
Exec=env GDK_BACKEND=x11 /mnt/Apate/.../interface.sh

cosmic-randr list → DP-1 (TV PHILCO, 3840x2160) · Xwayland primary: true
```

**ESTA CASA JÁ MEDIU ESTA JANELA QUEBRANDO NESTE COMPOSITOR, e já decidiu o que
fazer.** `gui/widgets/button_glyph.py:223`, escrito em 13/07/2026:

> `BUG-GLYPH-TOOLTIP-ORFAO-01: tooltip DESLIGADO de propósito. Sob
> COSMIC+XWayland a janelinha de tooltip ficava PRESA na tela (órfã, sobre o
> grid) após o hover — visto ao vivo em 2026-07-13.`

Mesma janela, mesmo compositor, sintoma oposto (presa em vez de piscando), e a
cura de então foi `set_has_tooltip(False)` — **a casa parou de usar a dica
nativa**. O que aconteceu depois foi que a interface nova nasceu em HTML e o
`title` voltou pela porta do WebKit, que faz exatamente a mesma chamada.

**Por que o pisca não se reproduz aqui é parte do achado, não uma falha da
medição.** A máquina de estados de dica do GTK é dirigida por `enter`/`leave`
do ponteiro sobre o widget; sem compositor não há quem reposicione, reancore ou
redispare a janelinha *override-redirect* debaixo dela. Perseguir a linha exata
do COSMIC custaria uma sessão e **não mudaria a cura**: o canal que ela vê é
nosso e tem substituto pronto na casa.

### O NÚMERO QUE FALTAVA, e ele é pior: o X mede ZERO PIXEL

A `COR-X-01` fechou em 09/09 com o X que ela pediu — *"um X na cor selecionada
por mim de forma que me impeça de setar alguma cor de um coleguinha"* <!-- noqa-acento: citação literal dela -->
— e a conferência mediu `getComputedStyle(el,'::after')` devolvendo
`rgb(0,0,0)` com o `drop-shadow` branco. **Ela mediu a cor. Ninguém mediu a
largura.**

`.guia .tom.tomado::after` é `position:absolute;inset:5px`, e o tom é uma
pílula **estreita**. Medido no `WebKit2.WebView`, na página publicada:

| largura da janela | o botão `.tom` | o `::after` do X |
| --- | --- | --- |
| 1222 px (a janela ao abrir) | 10,94 px | **`0px` × 14 px** |
| 1400 px | 13,91 px | 1,91 px × 14 px |
| **1600 px (a dela: 4K, com o teto `min(100%,1600px)`)** | 17,23 px | **5,23 px × 14 px** |
| 1900 px | 17,77 px | 5,77 px × 14 px |

`inset:5px` come 10 px de largura de um botão que tem 11 a 18. **Na janela como
ela abre, o X não existe; maximizado na TV dela, ele é uma tira de 5 px** — o
que a foto do instrumento mostra como um risco escuro dentro da pílula, não
como um X.

**E é isto que faz o pisca doer.** Desde que ela mandou o aviso de recusa sair
(*"no caso o X fica o aviso saí"*, 09/09) <!-- noqa-acento: citação literal dela -->,
o `title` é o **único** canal que diz de quem é a cor — e o X, que devia ser o
outro, tem 5 px. A tela inteira depende de uma janelinha que o compositor dela
apaga e reacende.

*A assinatura é a de sempre nesta casa: o instrumento respondeu sobre o CSS, e
não sobre o pixel.*

## §3 — A cura

**Uma decisão, e ela já era a política desta casa em 13/07: a explicação sai da
janelinha do GTK e entra na página.** A casa já tem o canal — `.ajuda:hover
.dica` / `.ajuda:focus .dica` (`topo.html:368,397`), 104 usos vivos nas dez
abas. O que falta é a forma que serve a 56 botões minúsculos.

### 1. A dica vira `::before`, e custa ZERO nó

Medido, injetando a regra na página publicada e trocando o canal nos 56 tons:

| | antes | depois |
| --- | --- | --- |
| nós na página | 1425 | **1426** — e o único nó a mais é o `<style>` do experimento, que na cura mora na folha e não existe |
| `.guia .tom[title]` | 56 | **0** |
| `.guia .tom[data-dica]` | 0 | **56** |
| `query-tooltip` do WebView, 10 s de ponteiro parado | 2 | **0** |
| janelas de dica do GTK na raiz X | 1 | **nenhuma** |

Um `<div class="dica">` filho, como o `?` usa, custaria **56 nós**; o
pseudo-elemento custa **zero** — e o `::after` do `.tom` já está tomado pelo X,
então o `::before` está livre. A forma medida:

```css
.guia .tom{position:relative}
.guia .tom[data-dica]:hover::before,
.guia .tom[data-dica]:focus::before{
  content:attr(data-dica);
  position:absolute;left:50%;bottom:calc(100% + 6px);transform:translateX(-50%);
  width:240px;white-space:normal;text-align:left;z-index:60;pointer-events:none;
  background:var(--elevated);color:var(--texto-suave);
  border:1px solid var(--linha);border-radius:7px;padding:8px 10px;
  font-size:11.5px;line-height:1.45;box-shadow:0 8px 24px rgba(0,0,0,.5);
}
```

**Ela abre PARA CIMA, e isso resolve a segunda queixa dela de graça:** a caixa
nasce acima do tom e não encosta na fileira «Jogador». Medido: caixa de
240 × 32 px, topo do botão em `y=405` dentro de uma `.janela` de 777 px — sobram
373 px acima. Na foto do instrumento a caixa está inteira dentro da janela, na
paleta do produto, com a fonte do produto.

**O `:focus` não é enfeite:** é a regra de 07/09 que já mora na folha da casa
(`topo.html`, o bloco do `?` que abre no foco), e o `.tom` é `<button>`, logo já
é focável — a dica passa a responder ao controle sem nada a mais. *Medido só o
`:hover`; o `:focus` é requisito desta sprint, não medição.*

**O que declarar sobre os ancestrais:** medido, dois cortam —
`.miolo` (`overflow:auto`) e `.janela` (`overflow:hidden`). A fileira de tons
está longe do topo, então a caixa cabe; **um tom na primeira fileira de uma aba
qualquer não caberia**, e quem levar esta regra para as outras nove precisa
medir de novo lá.

### 2. O X ganha um quadrado de verdade

`inset:5px` amarra o X à largura da pílula, que é a coisa que menos largura tem
na tela. A cura é soltá-lo dela:

```css
.guia .tom.tomado::after{
  inset:auto;left:50%;top:50%;transform:translate(-50%,-50%);
  width:min(12px,calc(100% - 2px));height:min(12px,calc(100% - 2px));
  /* o gradiente e o drop-shadow de contorno ficam como estão */
}
```

12 × 12 na janela dela, 8,9 × 8,9 na janela ao abrir — **quadrado nas duas**, que
é o que faz um X parecer um X. O contorno branco de `drop-shadow` de 1 px
continua valendo (foi ele que resolveu o controle branco dela, e a razão está na
`COR-X-01` §6.2).

### 3. A dívida, com o tamanho medido — e ela NÃO entra nesta sprint

O `title` não é só da guia. Nas dez páginas publicadas:

```
01-jogar  27 · 02-controles  68 · 03-gatilhos 195 · 04-iluminação  97
05-vibração 29 · 06-navegação 42 · 07-lançadores 6 · 08-conexões 124
09-sistema 35 · 10-perfis  37                        TOTAL: 660
```

**660 `title` atravessam a mesma janelinha do GTK**, e os 604 de fora da guia
piscam pelo mesmo motivo no dia em que ela parar o mouse em cima. Esta sprint
cura os **56** que ela nomeou e **põe a regra na folha da casa (`topo.html`)**,
para que as outras nove herdem a forma em vez de reinventá-la — que é a regra de
05/09: *quando a cura conhece a causa, ela cobre todos os chamadores.* Cobrir os
660 numa sprint é uma leva, não uma sprint; a ordem é dela.

## §4 — O que MORDE

**O ensaio novo é `scripts/ensaios/a_dica_da_cor_nao_e_do_gtk.py`**, e ele mede
no motor que ela usa — `WebKit2.WebView` numa `Xvfb` própria
(`garantir_tela_de_mentira`), `xdotool` parando o ponteiro sobre o tom tomado.
Ele conta as três coisas que separam a cura do defeito:

| arrancar | tem de reprovar |
| --- | --- |
| devolver o `title` a um `.tom` | `query-tooltip` sai de 0 e **nasce uma janela de dica do GTK** na raiz X — hoje, com o `title`, são 2 consultas e 1 janela; sem ele, 0 e nenhuma |
| devolver `inset:5px` ao `::after` do X | a largura computada do `::after` volta a `0px` a 1222 e `5,23px` a 1600 — a régua exige **quadrado e ≥ 8 px nos dois** |
| trocar o `::before` por um `<div class="dica">` filho | a contagem de nós sobe de +0 para **+56**, e a régua reprova pelo número |

E **a régua tem de olhar o PIXEL, não a folha** — é o defeito que esta sprint
corrige na conferência anterior: `getComputedStyle(el,'::after').width`, com o
retângulo do botão ao lado, nas duas larguras. Uma régua que confira só `content`
e `background` passa verde sobre um X de zero pixel, e foi o que aconteceu.

**A prova de que a cura é a cura é DELA.** O pisca não se reproduz fora do
compositor dela; nenhum ensaio desta árvore pode dizer que ele acabou. O ensaio
prova o que é provável aqui — *não existe mais janelinha do GTK para piscar* — e
ela prova o resto abrindo a 04 e parando o mouse em cima de um tom com X.

## Critério de pronto — por cabo · por BT · no perfil · por controle

| | |
| --- | --- |
| **cabo** | não se aplica ao canal: a frase e o X são desenho de tela e não descem ao aparelho. Vale como CONDIÇÃO — pronto exige a guia com dono de verdade, e um dono só existe com controle ligado: dois no cabo, com cores diferentes, cada coluna com o X do outro |
| **BT** | idem, e é a metade que importa medir junto: o `tomadas` do pacote nasce da mesa inteira, sem olhar transporte. Pronto = os quatro dela (2 cabo · 2 rádio), cada coluna com 3 X e nenhum na própria cor |
| **no perfil** | não se aplica — nada aqui grava. O `title`/`data-dica` e o X são derivados da cor viva a cada tique; um perfil velho abre igual e não ganha campo nenhum |
| **por controle** | ✓ é o assunto inteiro: a frase nomeia **qual** controle tem a cor, e o X mora na coluna de quem NÃO pode usá-la. Pronto = trocar a cor do P1 move o X nas outras três colunas no mesmo tique, e a frase de cada coluna passa a nomear o novo dono |

**Por que `bancada: true`:** a §2 mede que o pisca só existe sob o compositor
dela, e a §4 diz por quê isso não se resolve daqui. O passo dela é o de sempre
nesta aba — abrir a 04 com os quatro na mesa e **parar o mouse em cima de um tom
com X**. Se a caixa ficar parada, a sprint fecha; se ainda piscar, o que sobrou
não é o `title`, e a próxima medição é no GTK dela e não no nosso HTML.
