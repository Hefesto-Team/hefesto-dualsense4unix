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
