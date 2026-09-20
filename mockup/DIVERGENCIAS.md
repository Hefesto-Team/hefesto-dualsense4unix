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
