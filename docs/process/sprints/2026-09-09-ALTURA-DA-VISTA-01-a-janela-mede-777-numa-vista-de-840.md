---
sprint: ALTURA-DA-VISTA-01
estado: feita
posse:
  ALTURA-DA-VISTA-01:
    - src/hefesto_dualsense4unix/interface/topo.html
    - src/hefesto_dualsense4unix/gui/ponte_da_tela.py
    - src/hefesto_dualsense4unix/interface/aba03.py
    - src/hefesto_dualsense4unix/interface/aba09.py
    - scripts/ensaios/a_janela_cabe_no_que_ela_ve.py
bancada: false
depois_de:
  - DICA-DA-COR-01
  # A lista dela de 11/09 vem antes: a GATILHOS-VAO-01 escreve no mesmo
  # `aba03.py` e é a queixa viva. Esta mede a janela inteira depois, com o
  # vão daquela já curado — medir a altura antes seria medir o mundo de
  # ontem.
  - GATILHOS-VAO-01
  # SERIALIZADA PARA DEPOIS DA SEGUNDA LISTA DELA — 11/09/2026, e é o
  # mesmo precedente da lista anterior: a queixa VIVA vem primeiro. As
  # frentes abaixo reescrevem o TEXTO dos arquivos que esta sprint
  # também toca; medir ou desenhar sobre a prosa de ontem seria medir o
  # mundo de ontem — e a costura viraria «a última a gravar vence».
  - ESQUELETO-C2
  - LINGUA-A1
  - LINGUA-A4
---

> **ESTADO 2026-09-10: feita** — a altura virou
> `clamp(--piso-da-vista, 100dvh - 32, --teto-da-vista)`, a faixa de cabeçalho
> saiu (60 px) e o rodapé encolheu 12; medido na vista de 840 px da TV dela, o
> `.miolo` vai de 564 para **666** e a tela morta embaixo da `.janela` de 31
> para **zero**. O logotipo dela e a contagem de controles desceram para a
> linha do alvo — o LUGAR da contagem é PROPOSTA, com foto, e é dela decidir.
> O piso e os dois números digitados (`aba09.MIOLO_H`, `aba03.TETO_DA_GRADE`)
> passaram a sair de um dono só, `ponte_da_tela.MIOLO_NO_PISO`. A régua ganhou
> `--vista=N` e passou a medir a tela que sobra abaixo da `.janela`.
> Entrega: `docs/process/agentes/2026-09-10/ALTURA-DA-VISTA-01-opus.md`.
>
> **COSTURADA EM 13/09/2026** na `onda/1309`, liberada pela triagem das branches
> entregues (a nota de 12/09 que a mantinha aberta cumpriu o papel dela). Na
> costura, o LUGAR da contagem ficou onde a entrega propôs, decidido por quem
> coordena por delegação (a palavra dela de 13/09 no
> [índice da terceira lista](2026-09-13-A-TERCEIRA-LISTA-DELA-INDICE.md)); a régua
> da dica com ponteiro deixou de escolher alvo que embrulha outra dica (os dois
> vermelhos da §3 da OS-QUATRO-ORFAOS-DE-1009 eram da régua); e a §2.2 perdeu o
> fato que o COSMIC derrubou.

> *"maximizando a tela ela vai pra fora do limite, mas ponto 2 aprovado"* <!-- noqa-acento: citação literal dela -->
>
> *"semi aprovado. ainda joga pra baixo e abre a barra de navegação. tem espaço vertical pra aproveitar aqui"* <!-- noqa-acento: citação literal dela -->


> **DECIDIDO POR ELA, 09/09/2026: «1 + rodapé».** A opção (C) da §3 — a altura
> passa a seguir a vista E o cabeçalho da página encolhe — **mais o RODAPÉ**,
> que a lista não tinha oferecido. São as duas faixas de cromo que sobram
> depois de a altura ficar fluida.
>
> **O QUE ISSO OBRIGA A MEDIR, e é trabalho da sprint:** a §3 mediu 54px de
> folga só com o cabeçalho; com o rodapé junto a folga cresce, e o número tem
> de sair medido, não somado de cabeça. O rodapé é a faixa de «Aplicar · Salvar
> Perfil · Importar · Exportar» — ela existe nas DEZ abas, então encolhê-la
> alcança as dez de uma vez, e nenhum dos quatro botões pode ficar menor do que
> a mão dela alcança.
>
> **E o `4 controles: 2 USB · 2 BT` continua precisando de casa** — ele mora no
> cabeçalho que vai encolher. Proponha onde ele pousa e mostre a foto.

# ALTURA-DA-VISTA-01 — a janela mede 777 px numa vista de 840, e os 31 que sobram morrem

**O acordeão da ROLAGEM-01 foi aprovado; o que ela reporta agora é o que ele
não alcançava.** A largura virou fluida em 08/09 (`d63bbd73`,
`width:min(100%,1600px)`) e **a altura ficou para trás**: `--alt-janela:777px`,
o mesmo pixel nas dez abas, em qualquer tela.

---

## §1 — O que ela viu, e o que está MEDIDO

### A tela dela, medida na foto dela

A janela do Hefesto estava aberta e maximizada na TV dela às 22:24 de
09/09/2026. A foto foi lida pixel a pixel (`GdkPixbuf`, colunas em `x=1450` e
`x=1600`, longe do terminal que cobre a esquerda). A TV é **1920x1080 a 100 %**
(`cosmic-randr`), e a janela ocupa:

| banda | de · até | quanto |
| --- | --- | --- |
| painel do COSMIC (zona exclusiva) | y 0 · 81 | **82** |
| borda de cima da janela | y 82 | 1 |
| `Gtk.HeaderBar` | y 83 · 128 | **46** — confere com `ALTURA_DA_BARRA` |
| vista da `WebView` | y 129 · 968 | **840** |
| ⤷ recuo de cima do `body` | y 129 · 144 | 16 |
| ⤷ a `.janela` | y 145 · 921 | **777** — confere com `--alt-janela` |
| ⤷ o que sobra abaixo dela | y 922 · 968 | 47, dos quais 16 são recuo do `body` |
| borda de baixo da janela | y 969 | 1 |
| doca do COSMIC (zona exclusiva) | y 970 · 1079 | **110** |

A conta fecha nos 1080: `82 + 1 + 46 + 16 + 777 + 47 + 1 + 110`.

**A janela dela tem 888 px de altura e a vista da página, 840.** A página pede
809 (`16 + 777 + 16`). **Sobram 31 px que ninguém usa** — a faixa escura entre o
rodapé «Aplicar · Salvar Perfil» e a moldura da janela, que é o *"espaço
vertical pra aproveitar"* da segunda queixa dela.

### O que a `.janela` responde quando a vista muda — no WebKit vivo

Sonda de rascunho (fora do repositório), piloto **oculto**, dado vivo do daemon
com os quatro DualSense na mesa dela, a janela redimensionada antes de cada aba:

| vista da `WebView` | `.janela` | `.miolo` | morto abaixo da `.janela` |
| --- | --- | --- | --- |
| 809 (o desenho) | 777 | 564 | 0 |
| **840 (a dela)** | **777** | **564** | **31** |

*A `.janela` não olha para a vista.* Cresça a janela quanto quiser: o `.miolo`
fica nos mesmos 564.

### O caso exato da foto dela — a 03 com um bloco ABERTO

O acordeão da ROLAGEM-01 abre um bloco por vez. Com o L2 aberto (o `.miolo`
medido pela ponte JS, não calculado):

| | `.miolo` pede | caixa | barra |
| --- | --- | --- | --- |
| hoje, na vista dela | 633 | 564 | **69 px** |

São os mesmos 69 px que a §6 da ROLAGEM-01 já previa e aceitava — e é
exatamente isso que ela recusou: *"ainda joga pra baixo e abre a barra de
navegação"*. <!-- noqa-acento: citação literal dela -->

---

## §2 — A causa, com o número

### 2.1 — A altura é pixel; a vista não é

```
interface/topo.html:712   --alt-janela:777px;   /* a MESMA altura nas dez abas */
interface/topo.html:187   .janela{ width:min(100%,1600px); height:var(--alt-janela); }
```

O `.miolo` é o resto de uma subtração fixa. Medido nas dez, com o dado vivo:

```
cabeçalho 60 + fita 50 (52 em três abas) + tira 42 + rodapé 59 + 2 bordas
= 213 (215 nas três) de cromo da própria `.janela`
777 − 213 = 564        777 − 215 = 562
```

**Nenhuma das duas parcelas conhece a tela.** Por isso a barra que ela vê
maximizada é a mesma que veria numa janela de 809: a `.janela` recusa os 31 px
que a tela oferece, e a única coisa que a vista maior muda é o tamanho da faixa
morta embaixo.

### 2.2 — A hipótese que eu recebi CAIU pela metade, e a metade que caiu importa

O enunciado desta sprint dizia: *"numa janela mais BAIXA que 777 + o cromo, a
`.janela` passa da tela — que é o «vai pra fora do limite»"*.

**Não acontece, e o motivo é uma linha que já existe:**

```
gui/ponte_da_tela.py:511   self.janela.set_size_request(LARGURA_DO_DESENHO,
                                                        ALTURA_DO_DESENHO + ALTURA_DA_BARRA)
```

São **1212 x 855** de MÍNIMO. A tentativa de medir uma vista menor no piloto
oculto devolve teimosamente 809, porque a `Gtk.OffscreenWindow` se recusa a
ficar menor que a página. **FATO SUBSTITUÍDO EM 13/09/2026:** esta linha dizia
que a janela dela não encolhe abaixo disso porque o compositor não consegue. O
COSMIC que ladrilha (autotile ligado na sessão dela) não lê o mínimo do GTK —
uma foto dela das 02:48 de 13/09 mostra a janela com 816 px de altura, a vista
rolando e o rodapé cortado (estudo da RECONECTAR-SAMBA-02). *A `.janela` pode
passar da vista por encolhimento, sim — quando o ladrilho é menor que o piso.*

**O que existe é o inverso, e é um penhasco de 33 px:**

```
área útil da TV dela  888   (1080 − 82 de painel − 110 de doca)
mínimo da janela      855   (set_size_request)
folga                  33
```

Um painel ou uma doca 34 px maiores — trocar `size: M` por `L` na doca basta —
e a janela do Hefesto deixa de caber na tela dela. Aí sim ela vai «para fora do
limite», e sem afordância nenhuma: `set_size_request` é mínimo duro. **Isso não
é o que ela viu hoje, mas está a 34 px de acontecer**, e a cura desta sprint o
remove de graça (§3.4).

### 2.3 — O que "fora do limite" era, então

O que passa do limite é o CONTEÚDO, não a janela: o `.miolo` pede 633 numa
caixa de 564 e o bloco do R2 fica cortado embaixo — que é o que a foto dela
mostra. *A janela cabe na tela; o que não cabe é a aba dentro da janela, e a
janela não deixa a aba usar a tela que sobra.*

---

## §3 — A cura, e as opções onde há decisão dela

### 3.1 — O que é cura em qualquer cenário: a altura passa a ler a vista

`dvh` **existe neste WebKit** — medido, e não suposto:

```
100vh=840  100dvh=840  100svh=840  100lvh=840  calc(100dvh - 32px)=808
CSS.supports('height','100dvh') = true
```

Numa `WebView` embutida não há barra de navegador que apareça e suma, então
`dvh`, `svh`, `lvh` e `vh` valem o mesmo número. Usar `dvh` não custa nada e
diz a intenção.

**A forma é um `clamp`, e os três números são medidos:**

```css
--alt-janela: clamp(777px, calc(100dvh - 32px), 855px);
```

| o número | de onde vem |
| --- | --- |
| piso **777** | é o desenho de hoje: nenhuma aba fica pior do que já está |
| a conta **100dvh − 32** | os 32 px de recuo do `body` (16 em cima, 16 embaixo) |
| teto **855** | `.miolo` 642 — o maior pedido que existe hoje é a 03 com um bloco aberto, 633. Sem teto, uma tela 4K (a TV dela tem o modo 3840x2160) daria `.miolo` de 1915 px e a Navegação teria **1374 px de vão** |

Na tela dela o teto nunca é alcançado: `840 − 32 = 808`, e o `.miolo` vai a
**595**.

### 3.2 — O que isso resolve, e o que NÃO resolve — as dez, antes e depois

Medido na vista dela (840), com os quatro na mesa. `usa` é o fundo do último
quadro; `caixa` é o `.miolo`:

| aba | hoje | (A) altura fluida | (B) (A) + `body` sem recuo |
| --- | --- | --- | --- |
| 01-jogar | 420 / 562 | 420 / 593 | 420 / 625 |
| 02-controles | 562 / 562 | 593 / 593 | 625 / 625 |
| 03-gatilhos (fechada) | 403 / 564 | 403 / 595 | 403 / 627 |
| 04-iluminação | 560 / 564 | 560 / 595 | 560 / 627 |
| 05-vibração | 540 / 564 | 540 / 595 | 540 / 627 |
| 06-navegação | 541 / 564 | 541 / 595 | 541 / 627 |
| 07-lançadores | 564 / 564 | 595 / 595 | 627 / 627 |
| 08-conexões | 373 / 562 | 373 / 593 | 373 / 625 |
| 09-sistema | 564 / 564 | 564 / 595 | 564 / 627 |
| 10-perfis | 564 / 564 | 595 / 595 | 627 / 627 |

**As quatro que esticam ou rolam (02, 07, 09, 10) ganham 31 px de conteúdo de
verdade.** As seis que não esticam ganham 31 px de vão — e é preciso dizer isso
com todas as letras, porque **vão vazio é queixa dela**, de 27/08: *"iluminação,
jogar e outras abas tão muito ruins com esse super espaço vazio na parte
inferior"*. <!-- noqa-acento: citação literal dela -->

**O que a medição responde a essa objeção:** os 31 px **já estão vazios hoje** —
só que do lado de fora da moldura, entre a `.janela` e a borda da janela. A cura
não cria vão; ela move o vão para dentro do quadro e o entrega a quem souber
usá-lo. O total de pixel escuro na tela dela não muda.

**E o que ela NÃO resolve, que é o ponto:**

| a 03 com um bloco aberto | `.miolo` pede | caixa | barra |
| --- | --- | --- | --- |
| hoje | 633 | 564 | 69 |
| (A) altura fluida | 633 | 595 | **38** |
| (B) (A) + `body` sem recuo | 633 | 627 | **6** |
| (C) (B) + o cabeçalho encolhe | 633 | 687 | **nenhuma**, com 54 de folga |

*A altura fluida sozinha não fecha a queixa dela.* Ela derruba a barra de 69
para 38 px — metade — e a barra continua lá.

### 3.3 — A DECISÃO DELA: de onde vêm os 38 px que faltam

São três caminhos medidos, e nenhum é técnico — os três mudam o que ela vê:

* **(A) fica como está: 38 px rolam.** Zero decisão de desenho. É a aposta da
  ROLAGEM-01 §6 outra vez (*"os 69 px rolam no instante em que ela está mexendo
  NAQUELE bloco"*), com o número pela metade. **Ela já recusou essa aposta com
  69**; recusar com 38 é o resultado provável.
* **(B) o `body` perde o recuo quando a vista aperta** (`padding:16px` → 0 acima
  de certo aperto). Ganha 32 px, sobra barra de **6**. O preço é visual e é
  dela: a moldura arredondada da `.janela` encosta na borda da janela do
  sistema, e o desenho perde o "cartão sobre fundo".
* **(C) o cabeçalho da página encolhe quando a vista aperta.** São **60 px**: o
  logo de 46, o `h1` «Hefesto — DualSense4Unix» e a linha «Gerenciador DualSense
  para Linux». **A `Gtk.HeaderBar` já diz «Hefesto»**, e o comentário que tirou
  o subtítulo dela em 08/09 escreve a razão que serve aqui inteira: *"a barra já
  diz «Hefesto», e tudo o que muda — a aba, o alvo, o perfil ativo — já está
  DENTRO da janela"* (`interface/hefesto_vivo.py`). Com (B)+(C) a barra morre
  com 54 px de folga. **A ressalva medida:** o `.conectado` («4 controles: 2 USB
  · 2 BT») mora nesse cabeçalho e é dado vivo, não enfeite — encolher o
  cabeçalho obriga a mudá-lo de casa (a `.fita-linha`, 50 px, tem lugar à
  direita). Isso é redesenho de tela e passa pelo `mockup/`.

**A recomendação, com os números na mão, é (A) + (C):** a altura fluida porque
espaço morto não se defende em tela nenhuma, e o cabeçalho porque ele é a única
parcela dos 213 px de cromo que **repete o que a moldura do sistema já diz**. A
(B) fica de fora da recomendação: 32 px por trocar o cartão por uma tela cheia
é o pior preço por pixel das três.

**Uma quarta existe e não é desta sprint:** a linha de ajustes do L2/R2 mede 230
px porque `MultiPositionVibration` tem onze parâmetros a 20,9 px cada. Apertar
essa linha é da `aba03` e da palavra dela sobre legibilidade; fica registrado,
não proposto.

### 3.4 — Os dois donos do número, e como passam a concordar

Hoje a direção é: **o CSS manda e o Python copia.**

```
topo.html:712        --alt-janela: 777px
ponte_da_tela.py:169 ALTURA_DO_DESENHO = 809      # = 16 + 777 + 16
ponte_da_tela.py:174 ALTURA_DA_BARRA   = 46
ponte_da_tela.py:511 set_size_request(1212, 855)  # = 809 + 46
```

O comentário de `ponte_da_tela.py:150-152` chega a **transcrever três linhas do
CSS** para justificar o 809 — cópia manual de valor com dono, que é a forma
exata do defeito que esta casa já nomeou (*quando um valor tem dono, a régua
PERGUNTA ao dono*).

**E a cópia já apodreceu, o que dispensa argumento:** a linha 151 aponta o
`--alt-janela` para `interface/topo.html:693`, e ele mora em **712** desde
alguma edição que ninguém veio refletir aqui. Dezenove linhas de defasagem numa
transcrição de três.

**Depois da cura a direção INVERTE, e ninguém copia mais nada:**

| quem | manda em | e o outro |
| --- | --- | --- |
| **o CSS** | quanto a `.janela` usa da tela (`clamp(piso, 100dvh − 32, teto)`) | não precisa saber a altura da janela |
| **o Python** | o PISO — abaixo de que vista o desenho deixa de servir (`set_size_request`) | não precisa saber o 777 |

`ALTURA_DO_DESENHO` deixa de ser *"a altura do desenho"* e passa a ser
`PISO_DA_VISTA` — a menor vista que prometemos. O `777` sai do Python de vez, e
o comentário que transcreve o CSS é substituído pela razão do piso.

**E o piso pode CAIR, o que remove o penhasco da §2.2.** Com a altura fluida a
página não precisa mais de 777: ela se ajusta. Medido, forçando
`--alt-janela:500px` na vista de 840, o `.miolo` vai a 287 e as abas **rolam por
dentro** — não são cortadas:

```
03-gatilhos  DIV.miolo 403>287        04-iluminacao  DIV.miolo 560>287
```

Ou seja: numa tela baixa o produto degrada com barra, que é o comportamento de
qualquer aplicativo, em vez de recusar-se a encolher. **Quanto baixar o piso é
decisão de produto** — mas ele só pode baixar depois de a altura ser fluida, e
não antes.

### 3.5 — Os dois números digitados que passam a mentir

O `564` não vive só no CSS. Ele está **digitado em dois arquivos que reprovam a
geração**, e os dois param de ser verdade no instante em que a altura vira
fluida:

| onde | o que diz | o que vira |
| --- | --- | --- |
| `interface/aba09.py:68` | `MIOLO_H, ALTURA = 564, 530` | `MIOLO_H` passa a derivar do PISO, não da vista |
| `interface/aba03.py:1135` | `TETO_DA_GRADE = 477` — *"última coluna que coube: 477 px"* | idem: o teto que interessa é o do piso |

**A regra que resolve os dois:** um gerador não pode assegurar contra a vista,
porque ele roda sem tela. Ele assegura contra o **PISO** — a menor vista
prometida —, e quem mede a vista de verdade é a régua da §4, com a janela
aberta. Assim os dois números passam a sair de um dono só
(`ponte_da_tela.PISO_DA_VISTA` menos o cromo medido), e nenhum deles é digitado
de novo.

---

## §4 — O que MORDE

### 4.1 — A régua de hoje NÃO VÊ esta cura. Medido.

`scripts/ensaios/a_janela_cabe_no_que_ela_ve.py` roda o piloto oculto no
tamanho padrão, que é `TAMANHO_OCULTA = (1212, 809)`. Com a cura aplicada e a
vista em **809**:

```
03-gatilhos.html   .janela 777px   .miolo 633>564    (o mesmo de hoje, pixel por pixel)
```

**A régua devolveria números idênticos antes e depois da cura.** Com a altura
fixa isso não importava — 809 e 840 davam o mesmo. Com a altura fluida é a
diferença inteira, e a régua estaria medindo uma janela que não é a dela.

> *A armadilha desta sprint tem a assinatura das outras: o instrumento responde
> sobre outra coisa que não o produto. Aqui, sobre outra JANELA.*

**Então a primeira mordida é da régua, e vem antes da cura:** ela passa a
receber a altura da vista (`--vista=840`, e o padrão deixa de ser o único
caso), e reprova nas duas pontas — a do desenho e a da tela dela.

### 4.2 — A `.janela` que cresce nunca "não cabe"

O ramo `rola_j` da régua (`ja > jc + 2`, a `.janela` contra a própria caixa)
**morre com esta cura**: uma `.janela` que segue a vista jamais transborda de si
mesma. Quem continua mordendo é o ramo do culpado — o `.miolo` —, que nasceu em
09/09 justamente porque o ramo da `.janela` dava PASSA com a barra na tela dela.

**A cura não pode deixar o ramo morto sem dizer.** Ou ele sai com a razão
escrita, ou vira o que ele já foi uma vez: verde sobre nada.

### 4.3 — A mordida da altura, e ela é reprodutível

Medida, com a receita injetada na janela oculta:

| o que se força | o que a régua tem de acusar |
| --- | --- |
| `--alt-janela:500px` | `04-iluminacao DIV.miolo 560>287` e `03-gatilhos DIV.miolo 403>287` |
| voltar a `--alt-janela:777px` com a vista em 840 | **31 px mortos abaixo da `.janela`** |

A segunda é NOVA e hoje **nenhuma régua a enxerga**: todas medem dentro da
`.janela` e nenhuma olha o que há embaixo dela. É a mesma cegueira de 09/09, um
nível acima — *a régua parava na borda da `.janela`, e a tela dela não para.*

A conta é uma linha na sonda:

```js
window.innerHeight - document.querySelector('.janela').getBoundingClientRect().bottom
```

Hoje ela devolve 47 na vista dela (31 mortos + 16 de recuo) e tem de devolver
16 depois da cura.

### 4.4 — As dez, antes e depois

A tabela da §3.2 é a régua: **as dez abas medidas na vista dela, antes e
depois**. Uma cura de altura que só se mede na aba que doeu quebra as outras
nove — as dez partilham a mesma variável.

E o piso: com a vista em 809 as dez têm de sair **idênticas ao que são hoje**.
Se alguma mudar, o `clamp` está errado.

---

## Critério de pronto — por cabo · por BT · no perfil · por controle

É a régua dela de 08/09 ([CABO-BT-PERFIL-CONTROLE-01](2026-09-08-CABO-BT-PERFIL-CONTROLE-01-a-regua-de-pronto-de-toda-feature-da-tela.md)); a sprint só fecha com as quatro respondidas.

| | |
| --- | --- |
| cabo | **é tela pura, e mesmo assim se mede com os quatro na mesa**: a altura que o `.miolo` pede na 03 depende do MODO de cada gatilho, e o modo vem do aparelho. A régua da §4 roda com dois no cabo |
| BT | idem, com dois no rádio. O número não pode mudar com o transporte — se mudar, é a fita ou o cartão crescendo, e isso é outro defeito |
| no perfil | **não se aplica, e é decisão declarada**: quanto a janela mede não entra no perfil. O que ela vê é a tela dela, não uma preferência que viaja com o controle |
| por controle | **não se aplica**: a `.janela` é uma só para os quatro. A 03 desenha quatro colunas dentro da mesma caixa, e a dobra da ROLAGEM-01 já é por LINHA (as quatro colunas juntas), de propósito |

---

## §5 — O que fica registrado e não é desta sprint

Medido no caminho, com a janela na largura maximizada cheia (1918 de vista), e
**nenhum destes é de altura**:

* a `.janela` **centraliza** ao bater no teto de 1600 (`@x=159`, que é
  `(1918−1600)/2`, pelo `align-items:center` do `body`, `topo.html:122`) — está
  certo, e ficou conferido porque uma janela ancorada à esquerda seria outra
  leitura possível do *"vai pra fora do limite"*;
* `03-gatilhos`: `DIV.rotulos 159>135` — a coluna de rótulos do L2/R2 corta 24
  px do próprio conteúdo em QUALQUER largura, porque `--rot` é fixo. É corte
  (`overflow:hidden`), não barra, e é da `aba03`;
* `09-sistema`: `DIV.log 1938>1258` na largura — o registro técnico rola na
  horizontal. Já está declarado em `POR_DESENHO` na vertical; a horizontal, não.
