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
