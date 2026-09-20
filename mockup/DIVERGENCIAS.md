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

## 01-jogar.html
- **20/09/2026** — a **legenda** da aba diz duas coisas que o produto já não faz.
  É a `2026-09-17-POINT-AND-CLICK-01`, e as duas afirmações foram medidas:

  1. *"Os DOIS que ainda não têm quem os atenda aparecem, e dizem isso (…) os
     dois entram marcados"* — **nenhum dos dois entra marcado**. O Point And
     Click saiu da fileira em 31/08, por ordem dela (*"nos mockups tira o point
     and click e deixa só o navegação"*), e a linha que sobrou na tabela
     (`painel.CHIPS_DA_ESCADA`) saiu agora: `chips_sem_dono()` devolve `()`;
  2. *"O que ainda não existe é o PS + R3 parar nela"* — **ele para nela** desde
     13/09 (`hotkey.CICLO_DE_PONTES`, MODO-DE-CONEXAO-01), e desde esta sprint
     entra pela mesma porta do clique. A frase confundia a escada AUTOMÁTICA com
     o ciclo do GESTO, que são dois objetos de nomes parecidos.

  A terceira frase do parágrafo estava truncada no meio (*"ela leva traço no
  dica que diz o que falta"*).

  **O QUE ESPERA O OLHO DELA:** só o parágrafo da legenda mudou — nenhum chip,
  nenhum cartão, nenhuma medida. A fileira continua com os mesmos quatro
  `data-degrau`, e a regra CSS `.degrau.sem-dono` continua desenhada e sem uso,
  que é a gramática desta casa para *"botão que aparece e diz que ainda não tem
  quem o atenda"*.

  **O QUE ELA VÊ HOJE, até publicar:** a página que o produto renderiza continua
  com a legenda antiga, e o texto dela é só EXPLICAÇÃO — nenhum clique, nenhuma
  medida e nenhum rótulo dependem dele. O comportamento novo já está na tela
  dela: clicar no chip **Navegação** carrega o perfil desde o merge desta
  sprint, com legenda velha ou nova. O que a espera custa é a explicação
  descrever a fileira de 31/08 em vez da de hoje.

  **E UMA PARTE DISTO É DECISÃO DELA, na §7.1 da sprint:** o **nome** do chip.
  Ela usou as duas palavras na mesma frase — *"o modo point and click é o modo
  navegação"* — e a tela tem UM chip. Ele se chama **Navegação** hoje, e o texto
  novo diz isso; se ela escolher «Point And Click» ou «Navegação (Point and
  click)», este parágrafo é reescrito junto com o `rotulo`. Publicar antes da
  palavra dela custaria a mesma edição duas vezes.

## 02-controles.html
- **20/09/2026** — o «Nativo» do microfone nasce CINZA onde o aparelho não o
  alcança, com a razão no `?` ao lado. É a PARTE 3 da
  `2026-09-20-O-APARELHO-NAO-SE-CONTRADIZ-01`, e a decisão é dela, verbatim:
  *"Fica os dois botões. Mas no rádio o botão fica cinza sem ser ativado"*.

  **O QUE ESPERA O OLHO DELA:** a fileira do modo do microfone ganhou o `?` ao
  lado do «Nativo» — mais nada muda de tamanho (o card continua em 328 px, e a
  altura foi medida no próprio gerador). O produto já sabe apagar o botão e já
  recusa o clique com a mesma frase; enquanto a aba não for publicada, o pacote
  NÃO emite o campo (`a02_controles.A_PAGINA_APAGA_O_NATIVO`), então a tela que
  ela usa hoje continua idêntica.

- **20/09/2026** — os **dois primeiros botões da saída de som** têm os nomes que
  ela escreveu: «Efeitos do Jogo» e «Efeitos do Jogo e Áudio da TV no Controle».
  É a `2026-09-20-O-BOTAO-ENTREGA-O-QUE-PROMETE-01`, e o conceito é correção
  dela: *"não gosto do termo jogo pra se referir ao canal especifico pro sfx do
  controle, pq hdmi tecnicamente é jogo que manda pra lá também"*.
  <!-- noqa-acento: citação literal dela -->

  **O QUE ESPERA O OLHO DELA:** os nomes não cabem lado a lado na coluna do
  Microfone, então a fileira **empilhou** — três botões um sobre o outro. Os
  pixels que isso custaria voltaram de quatro alturas vizinhas (o par
  Virtual/Nativo, o botão de calar, os dois interruptores de sensor e o respiro
  das molduras), e o cartão **encolheu**: 329,6 px antes, **327,6** depois,
  contra os 328 que a caixa reserva. Ela aprovou a geometria vendo a foto —
  *"ṕqp perfeito. vc mandou muito bem. aprovadíssimo."*
  <!-- noqa-acento: citação literal dela -->

  **O TERCEIRO BOTÃO NÃO FOI RENOMEADO, E ISSO PRECISA DELA.** O nome que ela
  escreveu para ele é «Tudo na TV e Nada no Controle»; o botão faz o oposto —
  traz o som do PC para o alto-falante do controle e cala a televisão —, e a
  MORDIDA da própria sprint exige que ele continue fazendo isso. Pôr o nome sem
  trocar o ato seria a mentira que esta aba existe para não contar. Até a
  palavra dela ele segue «Só no controle».
