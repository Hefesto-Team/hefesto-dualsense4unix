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
