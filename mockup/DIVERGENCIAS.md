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
