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

<!-- Nenhuma aba em trabalho: o produto está igual ao desenho dela. -->

## 01-jogar.html
- **03/09/2026** — a aba passou a LER o que mostrava sozinha: a posição do
  interruptor (`painel.hefesto_ligado`), o chip aceso da fileira
  (`painel.modo_vivo` + `home_actions.mascara_do_aparelho`), a máscara acesa nos
  cartões e a coluna **Atenção** inteira (`painel.avisos_do_estado`, as seis
  fontes puras da GTK, mais o opt-out antigo). O que mudou no desenho é
  ENDEREÇO e CSS de estado — a cena continua a que ela aprovou: um aviso na
  coluna, `Ligado` marcado, `Sony DualSense` aceso, a faixa laranja com a
  frase. As cinco linhas novas da coluna nascem apagadas e só existem para o
  produto ter onde escrever quando a máquina dela tiver mais de um aviso.
  **O QUE ELA VÊ HOJE, enquanto o produto não recebe** — fotografado em
  03/09 com os dois controles na mesa e o daemon em `desktop`: a página
  publicada tem os endereços de TEXTO (a coluna Atenção já mostra o aviso
  do cadeado cego e a conta certa, porque `aviso-selo`, `aviso-texto` e
  `atencao-conta` já existiam lá), e **não** tem os de ESTADO. Então
  continuam na tela dela, até publicar: o chip **Sony DualSense** aceso com
  o modo vivo em Navegação, o chip **Xbox 360** aceso no cartão do P2 com o
  daemon em `flavor=dualsense`, o segundo aviso sem linha onde caber, e a
  faixa laranja com um travessão solto quando não há pendência. Medido: 12
  valores pintados com a página publicada contra 29 com a da bancada.
  **O produto recebe no `--publicar 01`**, que é ato de quem coordena.
## 02-controles.html
- **03/09/2026** — a LEITURA VIVA do card ganhou endereço, e duas coisas que
  chegam aos olhos mudaram junto. Nenhuma delas é desenho novo.

  **1. A barrinha de cada eixo virou DUAS METADES.** Ela era um `<span
  class="v" style="left:L%;width:W%;background:C">`, e os três valores mudam a
  cada leitura: o `escrever` do piloto sabe escrever largura e cor, e **não tem
  alvo de POSIÇÃO** — com um elemento só, a barra de um eixo negativo cresceria
  para o lado errado. Agora são `.v.neg` (ancorada em `right:50%`) e `.v.pos`
  (em `left:50%`), e a cor sobe para o trilho por `currentColor`.
  **Os pixels são os mesmos, e isto está medido**, não afirmado: as duas
  páginas abertas no Chrome, `getBoundingClientRect` nas doze barras visíveis —
  **10 das 12 idênticas na esquerda, na largura e na cor**, e as outras duas
  diferem em **0,02 px** (arredondamento de sub-pixel entre `left:12%` e
  `right:50%`).

  **2. `X:  60` virou `X: 60`** — um espaço a menos por eixo, nos quatro
  analógicos. A frase passou a sair de `controller_card._markup_xy`, que é o
  dono dela na GTK, em vez de uma segunda cópia digitada no gerador. É a LEI 0:
  *"no gtk eu já deixei praticamente tudo pronto (…) Não temos que recriar
  nada."*

  **O QUE O PRODUTO FAZ ENQUANTO ESPERA O OK DELA, e é medido:** o pacote
  pergunta à página **publicada** quais endereços ela tem
  (`_so_se_a_pagina_tiver`) e **só emite esses**. Medido nesta árvore com os
  dois controles dela na mesa: `leitura_viva` calcula **46 campos por card** e
  o pacote emite **15** — os 46 ficam de fora, e nenhum deles chega ao
  `casamento.medir` como órfão. **A tela dela não muda nada até o
  `--publicar 02`**: os dezesseis glifos, os dois gatilhos, os seis eixos e os
  dois pares X/Y continuam mostrando o desenho, exatamente como hoje. No
  minuto em que ela publicar, os 46 passam a ser pintados sem uma linha de
  código a mais.

  **O que espera a sua palavra:** o giroscópio e o acelerômetro do desenho usam
  **quatro cores** (ciano, verde, laranja, cinza) e a leitura viva usa **três**
  (`mesa_viva._barra_bipolar`: verde para positivo, vermelho para negativo,
  cinza para o repouso). Quando o produto pintar, o ciano e o laranja somem.
## 05-vibracao.html
- **03/09/2026** — o desenho ganhou DUAS coisas que a página publicada ainda não
  tem, e nenhuma muda um pixel do que ela aprovou:
  1. **endereço para o punho que treme** — `data-campo="treme-e"`/`"treme-d"`
     nos dois grupos de motor do SVG, com `data-hef-classe="acesa"`;
  2. **as três frases da janela estável** que a aba nova não tinha, lidas do
     `gui/main.glade` e não redigitadas: o teto da mesa (dos quatro tooltips de
     degrau), os 5 segundos do Modo Auto e a nota *"os valores acima ainda
     passam pela intensidade escolhida ali em cima"*.
- **03/09/2026 · O QUE ELA VÊ HOJE, com a página publicada de agora**, medido
  com a mesa dela (um DualSense no cabo, um por rádio):
  - **o número da força já está certo sem publicar**, porque a cura é do PACOTE:
    a barra "Personalizado" mostra `100%` com o degrau em "Balanceado", e não os
    `70%` presos de antes. Fotografado nas duas páginas, com o mesmo daemon;
  - **o que fica para trás são TRÊS pinturas**: 22 valores na bancada contra 19
    na publicada, e as três são os punhos que continuam acesos da CENA do
    mockup — o motor direito do P1 e os dois do P2 — com a mesa parada e
    `vpads == 0`. O `achar()` devolve zero elementos para `treme-e`/`treme-d`
    na página publicada: **não há erro de JS, nem clique morto, nem texto
    vazando** — só o punho que não apaga. As três frases novas também não
    aparecem nas dicas até lá;
  - o resto da aba continua idêntico: mesmos degraus, mesmos dois botões, mesma
    linha de estado.
- **03/09/2026 · o que ESPERA a palavra dela**: no degrau **Auto** a barra passa
  a dizer `100%`, que é o teto dele e o mesmo número da janela estável. A cena do
  mockup ensina `70%` no P3 (*"porque a bateria dele está no meio"*), e esse
  valor vivo exige um campo que o daemon não publica com honestidade:
  `rumble_mult_applied` ficou em `0.7` nos QUATRO degraus clicados em 03/09, com
  a política mudando a cada clique.
