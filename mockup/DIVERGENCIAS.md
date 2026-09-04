# As abas em trabalho na bancada

Toda seção aqui é uma aba cujo **desenho já andou** e cujo **produto ainda não
recebeu** — porque ela ainda não deu o OK. O
`scripts/check_o_desenho_aprovado.py` lê este arquivo; a aba que não estiver
aqui, ele reprova.

**A direção é `mockup/` → `layout/`.** A bancada é o desenho de hoje; o produto
só recebe quando ela aprova a aba **inteira**, que é a escolha dela de
31/08/2026 — nem a cada ponto, nem só no fim da lista.

**Formato** — uma seção por página, com data e o ponto que está aberto:

```
## 01-jogar.html
- **DD/MM/AAAA** — o ponto da lista que está aberto nela.
```

Quando ela aprovar a aba, `--publicar NN` leva o desenho ao produto e **apaga a
seção daqui**: a aba deixou de estar em trabalho.

---

## 04-iluminacao.html
- **03/09/2026** — as duas cores das lâmpadas (`--led-apagado` e `--led-aceso`)
  passaram a ser declaradas em `.luz-grade`, o escopo que o DESENHO alcança.
  Elas moravam só em `.luzinhas`, que é o indicador PEQUENO da célula LEDs, e
  `.luzinhas` é uma folha da árvore — as cinco lâmpadas do desenho grande não
  acendiam **nenhuma**, medido no DOM vivo. É CSS, e só: nenhuma caixa nova,
  nenhum texto novo, nenhum botão. O que muda na tela é a lâmpada do número
  aparecer, que é o que o `title` da moldura já prometia.
  **O que ela vê HOJE, na página publicada, enquanto isto espera o OK:** a aba
  Iluminação está INTEIRA — as cinco lâmpadas do desenho grande já acendem o
  número vivo e a barra já mostra a luz do aparelho. A metade viva desta cura
  (`a04_iluminacao.folha_da_luz`) não espera publicação nenhuma: ela declara o
  par de cores e escreve as regras dentro do `<style id="plastico-vivo">`, que o
  produto de hoje JÁ tem. O que a publicação acrescenta é a mesma declaração na
  folha estática — o que faz a bancada se ver sozinha, sem daemon, no navegador.
  Nenhum clique fica morto e nada some da tela até lá.
- **03/09/2026** — **o trilho de brilho passou a GRAVAR.** Decisão dela:
  perguntada se mexer no brilho grava o perfil na hora ou espera o "Salvar
  Perfil", ela respondeu ***"Grava na hora"***. O trilho JÁ ERA desenhado como
  slider — a regra `.cheio::after` punha um knob de 12px na ponta da barra roxa
  — e **não fazia nada**: ela via `100%`, arrastava, e o número não mudava.
  O que muda no DESENHO é uma coisa só: o knob deixa de ser pintado pelo CSS e
  passa a ser o polegar de um `<input type="range">` de verdade. **A geometria é
  a mesma**, e não por aproximação: o `left:-7px` e a `width:calc(100% + 12px)`
  saem de igualar o centro do polegar nativo ao centro do knob do mockup para
  TODO valor — medido no WebKit vivo, trilho em `[164, 169]px` e polegar em
  `[157, 181]px`. Nenhuma caixa nova, nenhum texto novo, nenhuma cor nova.
  **O que ela vê HOJE, na página publicada, enquanto isto espera o OK:** a
  célula de brilho exatamente como está — a barra roxa, o knob e o `%`, tudo
  vivo e tudo SÓ LEITURA, que é o que ela já era. O `<input>` não existe no
  publicado, então **nenhum clique fica morto**: não há polegar a arrastar. O
  gesto `brilho` já está registrado no pacote e entra em ação no instante em que
  a página for publicada.
## 05-vibracao.html
- **03/09/2026** — a barra "Personalizado" deixou de ser LEITURA e virou um
  `<input type=range>` que ela arrasta, **de 0 a 200%**, decisão dela do mesmo
  dia: *"0 a 200%, e grava na hora."* Três coisas mudam no desenho, e nenhuma
  acrescenta caixa ou texto:
  1. o trilho da linha do "Personalizado" é agora um `<input type=range>` com
     `min=0`, `max=200` (o `RUMBLE_CUSTOM_MULT_MAX` do esquema) e passo 10 (o
     MDC dos degraus com o teto, para que cada degrau tenha uma parada em cima
     dele). A aparência é reconstruída pixel a pixel pelo CSS — mesma altura,
     mesmo raio, mesmo polegar de 12 px em `--purple` —, porque a aba está
     FECHADA por elogio literal dela (`CORRECOES-DELA.md:39`);
  2. o teto da barra passou de 150 para 200, e as larguras da CENA acompanham:
     o P1 (150%) desenha 75% do trilho em vez de 100%, o P2 (100%) desenha 50%.
     O `Máx` da cena, que acendia no P1, apaga — a cena deixou de estar no teto,
     porque o teto subiu;
  3. o endereço do trilho trocou de `forca-pct` (a LARGURA de um `<span>`) para
     `mult-pos` (o `value` do `<input>`), que é o que move o polegar.

  **O que ela vê HOJE, na página publicada, enquanto isto espera o OK:** a
  barra continua sendo o `<div>` de leitura de sempre, com o teto em 150 — o
  desenho não some e nada fica torto. O que NÃO funciona lá é justamente o que
  esta mudança traz: arrastar. O gesto `intensidade` já existe no produto e o
  ouvinte de `change` do piloto já o alcança; o que falta é o elemento com
  `value` na página, e ele só chega com `--publicar 05`.

  **A outra metade da leva NÃO espera publicação:** os quatro degraus de cada
  coluna passaram a gravar a força **daquele controle** no perfil ativo (decisão
  dela, *"construir por controle"*), e isso é `a05_vibracao`, que o produto de
  hoje já carrega. Na página publicada os botões já estão lá, com os mesmos
  endereços — o clique deles muda de comportamento na hora, sem publicar nada.

## 08-conexoes.html
- **03/09/2026** — a linha fechada da Gestão de Controles e a confissão do mapa
  ganharam ENDEREÇO, para o produto poder reescrever o que era do desenho:
  `mic-existe` no `<b>` do resumo, `mic-caminho`, `luz-trava` (a classe
  `apagado` do botão da luz) e os três da `.mm-conf-linha`. Nenhum texto novo e
  nenhuma caixa nova — o que muda é quem escreve.
  **Até publicar, a tela dela continua com os quatro valores do desenho:**
  "Microfone **Ligado**" (a ponte deste controle está DESLIGADA no
  `maquina.json`), o caminho e a trava do botão da luz decididos pela posição no
  mockup, e a confissão do mapa dizendo "**três coisas**" onde a bancada dela
  tem uma. O pacote já emite os cinco campos e o `achar()` do piloto não os
  encontra — escreve zero, sem custo e sem estrago.
## 10-perfis.html
- **03/09/2026** — **a Prioridade virou SLIDER**, que é o pedido dela de 27/08
  (*"prioridade é slicer"*) reconfirmado hoje: *"Slider, como você pediu"*. Era
  o único campo do editor sem NENHUM caminho de escrita na interface nova — o
  desenho trazia uma barra, e barra não se arrasta.
  **O que muda no desenho, e é só isto:** dentro do mesmo `<span class="trilho">`
  nasce um `<input type="range">` transparente do tamanho do trilho, com a faixa
  do esquema (`0..200`, de `profiles/schema.PRIORIDADE_MINIMA/MAXIMA`). O punho
  redondo saiu do `::after` do cheio e passou a ser o do próprio range — mesma
  cor, mesmo tamanho, mesma posição; a diferença é que agora ele segue o dedo.
  E a barra do desenho passou de `width:90%` para **45%**: com o teto em 200, os
  90% diziam "quase no máximo" sobre um perfil que está em 90 de 200.
  **O que ela vê HOJE, na página publicada, enquanto isto espera o OK:** a
  Prioridade continua sendo uma barra de leitura, com o número certo ao lado —
  nada some da tela e nenhum clique fica morto. O gesto que grava
  (`a10_perfis.editor_prioridade`) já existe e já está provado; ele só não tem
  onde ser clicado até a publicação.
  **O "Estilo de Jogo" NÃO espera nada disto:** o `<select>` já está na página
  publicada, e desde hoje escolher um estilo GRAVA (gatilho, degrau de vibração
  e a cor de cada controle, de `profiles/estilos_de_jogo.py`). O único efeito de
  desenho ali é que a lista de rótulos passou a sair do motor em vez de ser
  digitada — as quinze palavras são as mesmas.
## 02-controles.html
- **03/09/2026** — o **selo do microfone ganhou COR + ÍCONE**, decisão dela:
  *"Cor + ícone. Redundante de propósito — quem lê rápido pega pela cor, quem
  não distingue cor pega pelo risco."*

  O que MUDA na tela: o selo passa a trazer um microfone desenhado (SVG de 9px,
  em `currentColor`) antes da palavra, e um **risco** cruza esse microfone
  quando o valor é MUDO. A classe da cor foi **invertida** — o selo nasce
  apagado e ACENDE em ATIVO, em vez de nascer verde e apagar em MUDO. A largura
  do selo vai de **34,8px para 46,8px** (MUDO) e para 52,5px (ATIVO), medido no
  `WebKit2.WebView`; a linha do rótulo **não transborda** (`scrollWidth ==
  clientWidth`), e há régua cobrando isso.

  **O que ela vê HOJE, na página publicada, enquanto isto espera o OK:** o selo
  sem ícone, e **a cor congelada no que o gerador desenhou**. Medido no DOM vivo
  em 03/09, injetando os três valores do selo na página publicada: o cartão do
  P1 fica `rgb(80,250,123)` nos três — diz **MUDO em VERDE** — e o do P2 fica
  `rgb(68,71,90)` nos três — diz **ATIVO em CINZA**. É o defeito que esta
  divergência cura, e ele está na tela dela agora. Nada some e nenhum clique
  morre até a publicação: o que falta é a cor seguir a palavra.

  A metade do PACOTE não espera publicação — ela não mudou: o valor continua
  saindo de `mesa_viva.selo_do_mic`, e é o mesmo dos três alvos.
