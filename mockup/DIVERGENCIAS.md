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

## 05-vibracao.html
- **02/09/2026** — **a linha do estado da vibração**, que a janela GTK tem e esta
  aba não tinha. Ela nasce no rodapé do quadro e diz, com as palavras que já
  eram do produto (`app/actions/rumble_actions.py:186,291,370`): quantas vezes o
  jogo pediu vibração, se a intensidade escolhida **não está chegando** a jogo
  nenhum, e se o orçamento da mesa limitou o multiplicador.

  **Por que ela importa hoje:** com os dois controles na mesa, o daemon
  respondia `rumble_ff.vpads == 0` — não há gamepad virtual —, e nesse estado os
  quatro degraus de força **não agem sobre a vibração de jogo nenhum**. A janela
  estável avisa isso desde 11/08; a aba nova ficava calada e a pessoa continuava
  clicando em "Máximo".

  A linha **some** quando não há nada a dizer (`.vib-estado:empty`), e no estado
  normal ela cabe sem fazer a aba rolar — medido: o miolo tem 564 px e o quadro
  passou de 476 para 498. Com um alerta aceso a aba rola, e isso é de propósito.

  **O que espera o seu OK:** o texto sai inteiro do produto, mas o LUGAR e o
  tamanho são desenho. Se preferir a linha no topo do quadro, ao lado do título,
  é uma linha no gerador.
