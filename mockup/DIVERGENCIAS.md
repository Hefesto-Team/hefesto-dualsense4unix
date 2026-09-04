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
