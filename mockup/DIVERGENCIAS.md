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

<!-- AS DEZ ESTÃO AQUI PELO MESMO MOTIVO, e ele é UM: a folha das dez ganhou as
     duas peças da D-02 e da D-03 (`monta.CSS_FOLHA`), e o `<style>` do
     esqueleto é um só para as dez páginas. São 50 linhas acrescentadas,
     e NENHUM elemento das dez abas as usa hoje — quem as usa são as frentes da
     Onda 2, aba por aba.

     ZERO PIXEL MUDOU, e está medido: as fotos da `06` e da `09` saem BYTE A
     BYTE iguais às de antes (`olhar.py`, Chrome, 1920x1080). O que mudou foi o
     sha256, porque o portão compara o arquivo e o INVISIVEIS dele só sabe
     descontar ATRIBUTO de endereço, não regra de folha que nada casa.

     ELAS SAEM DAQUI JUNTAS, na leva de publicação — e não uma a uma: o que
     separa cada aba do produto vai ser o desenho NOVO da Onda 2, que é o que
     precisa do olho dela. -->

## 01-jogar.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.
- **04/09/2026 · ONDA2-01** — **DUAS mudanças, e uma delas move pixel.**
  1. **O CADEADO voltou para a aba** (decisão [03]: *"Volta para a Jogar,
     embaixo de Modo"*) — pedido nomeado dela, de 23/07/2026, que saiu do
     desenho por escolha minha. É **uma linha de 16 px** no rodapé do quadro
     Modo, fora das duas seções do interruptor. Medido nas duas fotos
     (`olhar.py`, Chrome, 1920×1080): a `.janela` continua em **1180×777**,
     `passa_da_dobra: 0` e sem rolagem lateral — a linha coube na folga que a
     foto de 04/09 já mostrava embaixo do último quadro. **O rótulo e a dica
     são os do `Gtk.CheckButton` da janela antiga**, palavra por palavra: não
     há texto novo de tela nesta mudança.
  2. **O "Player N" esmaece enquanto o jogo não recebeu o controle** (decisão
     [02]). **ZERO pixel:** só `color` e `font-weight` mudam, e a cena que ela
     aprovou tem os dois controles já recebidos pelo jogo — nenhum dos dois
     cartões nasce esmaecido, e o gerador reprova quem os fizer nascer assim.
     A palavra fica: a **D-04** dela é *"Player N, como está hoje"*.

  **O QUE ELA PRECISA OLHAR ANTES DE PUBLICAR:** a linha do cadeado — é a única
  coisa desta leva que ocupa espaço na tela dela.

## 02-controles.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.
- **04/09/2026 · ONDA2-02** — as dez decisões desta aba viraram desenho na
  BANCADA, e **nada foi publicado**: a publicação é uma leva só, para o olho
  dela (`PROVA-DE-TELA-01`). O que a bancada passou a ter, e o produto ainda
  não:

  | o quê | decisão | o que muda no desenho |
  | --- | --- | --- |
  | o **anel interno** de cada cartão, seguindo a luz viva | D-06 / S-11 | um `<span class="anel-vivo">` de 1px dentro dos 2px do casco. **É o único item desta lista que move pixel**, e é o que ela pediu com todas as letras: *"casco borda externa lightbar borda interna"* |
  | a **palavra curta** no lugar do travessão da Barra de luz | [02] | o campo passa a mostrar `Jogo` · `Steam` · `Não sei` · `Apagada`; o `title` da linha passa a ser PINTADO com a frase inteira |
  | o **`?`** ao lado do 🎙 e do ♪ | [04] / [06] | invisível em repouso (a folha o esconde); ele só aparece com o botão apagado |
  | o **`disabled` do ♪ SAIU** | [04] | o botão continua respondendo ao clique — *"apagado e ainda assim responde"* |
  | a **marca da emulação degradada** na máscara | [07] | um `<sup>` que nasce `display:none` e só aparece quando o produto escreve o motivo no `title` |
  | a **linha de ressalva** do alto-falante | [09] + D-02 | não ocupa nada em repouso (`:empty` e `.nada`, as duas metades da peça) |
  | o **endereço do décimo alvo** no acordeão | T-07 | `data-hef-alvo="marcado"` no rádio — endereço de LEITURA, e nada mais |

  **O QUE O PRODUTO FAZ ENQUANTO ESPERA:** exatamente o que fazia. Os endereços
  novos só existem na bancada, e o pacote pergunta à página PUBLICADA antes de
  emitir (`a02_controles._so_se_a_pagina_tiver`) — nenhum valor novo é escrito
  num vão que não existe, e nenhum órfão entra no `casamento.medir(...)`.

  **O QUE JÁ VALE NO PRODUTO SEM PUBLICAR NADA**, porque é campo que a página
  publicada JÁ TEM: o selo composto do microfone (`mic-selo`), a rota lida nas
  duas camadas (`alto-rota`) e o ato do 🎙 num pedido só.

## 03-gatilhos.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.

## 04-iluminacao.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.

## 05-vibracao.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.
- **04/09/2026 · ONDA2-05** — **QUATRO decisões dela viraram desenho, e três
  delas OCUPAM ESPAÇO. Nada foi publicado.**

  | o que entrou | decisão | o que muda na tela |
  | --- | --- | --- |
  | as duas linhas de motor viraram **barra que arrasta**, de 0 a 100% | dela, 04/09 (*"os slcers … se multiplicam"*) <!-- noqa-acento: citação literal dela --> | mesma linha, mesmo lugar. O que muda é o **significado do número**: era o par 0-255 que o jogo pediu, e passa a ser o AJUSTE que multiplica o degrau. O pedido do jogo não se perdeu — vira o `title` da linha, pintado pelo produto |
  | uma **linha de estado por coluna** | D-14 | uma faixa nova no fim de cada coluna, com um dos três estados que ela nomeou |
  | uma **linha de MESA** embaixo da grade | [05] | uma linha nova com os quatro degraus do ajuste geral, fora das colunas. E as colunas sem ajuste próprio **deixam de acender degrau** |
  | a **nota do Testar** sobe do `?` para a tela | [02] | uma linha em itálico, esmaecida, embaixo de tudo |

  **O QUE ELA PRECISA OLHAR ANTES DE PUBLICAR — e é um número, não uma
  impressão: o quadro passou a ROLAR 103 px.** Medido no Chrome, no tamanho da
  janela do produto (1180×757), com a `.nota` escondida:

  ```
  PUBLICADO (a que ela abre hoje)  miolo 564 visíveis · 564 de conteúdo · rola 0
  BANCADA   (o desenho de hoje)    miolo 564 visíveis · 667 de conteúdo · rola 103
  ```

  O custo, medido peça por peça: **linha de mesa 53 px · faixa de estado 31 px ·
  nota do Testar 21 px**. Na foto, o que fica abaixo da dobra é a linha de mesa.

  **NÃO HÁ PIXEL A DEVOLVER DENTRO DO QUADRO**, e isso também foi medido: a
  única faixa com conteúdo elástico é o desenho do controle (`--r-des`, 124 px),
  e pagar os 103 px ali deixaria o desenho com 21 — a faixa que ela aprovou
  desapareceria. O `.miolo` (que reserva os 564) é do `topo.html`, comum às dez
  abas, e é decisão dela. **O piso do estado já foi apertado ao mínimo** (20 px,
  uma sublinha) e as margens da mesa e da nota também: os 118 px da primeira
  medição viraram 103.

  **O QUE ISSO DEIXA PARA ELA DECIDIR**, e é a única coisa que este trabalho não
  pode escolher sozinho: se a aba pode rolar 103 px, ou se alguma das três sai.
  As três são decisão dela, e nenhuma foi encolhida para economizar pixel.

  **O QUE O PRODUTO CONTINUA FAZENDO ATÉ ELA PUBLICAR:** as duas linhas de motor
  seguem sendo LEITURA (o par 0-255), e o pacote continua emitindo os endereços
  velhos (`motor-e`, `motor-e-pct`) exatamente para isso — a página que ela abre
  hoje não congela. O gesto `motor`, a linha de mesa e a linha de estado por
  coluna **existem no código e não têm onde cair** na página publicada: são
  endereço novo, e endereço novo só chega pelo `--publicar 05`.

## 06-navegacao.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje** — e aqui
  isso está fotografado: a foto desta aba sai byte a byte igual à de antes da
  mudança (`olhar.py`, Chrome, 1920x1080).

## 07-lancadores.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.

## 08-conexoes.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.
- **04/09/2026 · ONDA2-08** — quatro decisões do PO viraram desenho, e **três
  delas já valem no produto sem publicar nada**: a coluna da direita do Check-up
  é UM endereço com alvo `html` (`data-campo="ordem"`), e quem a desenha é o
  pacote.

  | o quê | decisão | onde já vale |
  | --- | --- | --- |
  | o **cartão de cura** abaixo da ordem de serviço | [03] | **no produto**, hoje |
  | o **`[derivado da conta]`** nas frases não medidas aqui | [04] | **no produto**, hoje |
  | o **`+N`** das ordens que não couberam | [07] | **no produto**, hoje |
  | a **frase do rodapé do Mapa**, trocada pela verdade | [08] | só na bancada |
  | o `?` da quinta linha e a dica do ⊘, sem o botão morto | [05], a metade do fato errado | só na bancada |

  **O QUE MUDA DE PIXEL NA BANCADA, e é o que ela precisa olhar:** a coluna da
  direita ganhou um segundo card, e com ele a coluna da esquerda estica — as
  cinco linhas do exame passam a repartir mais altura. Medido nas duas fotos
  (`olhar.py`, Chrome, 1920×1080): a `.janela` continua em **1180×777**,
  `passa_da_dobra: 0`, sem rolagem lateral. O card coube na folga que a coluna
  já tinha.

  **A DÍVIDA DECLARADA, e ela é de tinta, nunca de informação:** as regras
  `.col-ordem .mais` e `.ordem.cura` nasceram nesta folha e a página publicada
  ainda não as tem. Fotografado no produto vivo em 04/09: a pílula do card de
  cura sai **certa** (`.selo.warn` é global e já existe), e a linha do `+N` sai
  em corpo de texto normal em vez de 11 px itálico cinza. **A frase está certa
  desde já; a tinta chega no `--publicar`.**

## 09-sistema.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje** — e aqui
  isso está fotografado: a foto desta aba sai byte a byte igual à de antes da
  mudança (`olhar.py`, Chrome, 1920x1080).

## 10-perfis.html
- **04/09/2026** — a folha das dez peças (D-02 e D-03) entrou pelo `monta.py`.
  **Até publicar, o produto continua exatamente como ela o vê hoje:** nenhum
  elemento desta aba usa as peças, então as regras novas não casam com nada e
  a página publicada desenha o mesmo pixel que a bancada.
