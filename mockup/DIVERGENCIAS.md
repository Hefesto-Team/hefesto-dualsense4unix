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

  A linha **some** quando não há nada a dizer (`.vib-estado:empty`).

  **A FRASE ENCURTOU — 02/09/2026, e foi a sua decisão.** Ela tinha 211
  caracteres e ocupava 1072 px numa caixa de 1072: quebrava em duas sublinhas, e
  a segunda — *"que você fixar aqui embaixo."* — ficava **cortada** pela borda
  de baixo do miolo. Para ler o aviso inteiro você tinha de arrastar. Medido no
  WebKit da janela do produto (1180x757), com os seus dois controles e
  `vpads == 0`, e fotografado:

  | | a linha de estado | a aba rola | o aviso |
  | --- | --- | --- | --- |
  | a cena do desenho | 1 linha, 18 px | 0 px | não acende |
  | a sua mesa, frase de 211 chars | 2 linhas, 60 px | 40 px | **cortado** |
  | **a sua mesa, frase de hoje** | 2 linhas, 42 px | 22 px | **inteiro** |

  A frase de hoje tem 162 caracteres e diz as mesmas quatro coisas: o que não
  está acontecendo, por quê, o que fazer, e o que a intensidade ainda faz. Ela é
  a **mesma** que a janela GTK usa, com um dono só
  (`rumble_actions.texto_do_alcance_da_intensidade`) — encurtar ali encurtou as
  duas telas, que é o certo: uma frase, um dono. Na GTK ela caiu de 3 linhas
  para 2 numa janela de 600 px, e de 2 para 1 numa de 1100.

  **SOBRAM 22 px DE ROLAGEM, e eles não são a frase.** São DUAS mensagens
  acesas ao mesmo tempo — a dos pedidos do jogo e a do alcance — onde o desenho
  reservou espaço para UMA: 42 px contra 20 de folga. Nada fica cortado, mas a
  barra de rolagem aparece.

  **O que espera o seu OK, e é uma escolha entre três:**

  1. **deixar como está** — a aba rola 22 px quando os dois avisos acendem, e
     nada fica cortado;
  2. **o bloco no TOPO do quadro**, ao lado do título — quem sai de vista é a
     linha "Testar agora" embaixo;
  3. **encolher uma linha da tabela** em ~22 px — cabe tudo, mas mexe no
     desenho que você aprovou em 27/08.

  Não dá para caber sem escolher: o `.miolo` é do `topo.html`, comum às dez
  abas, e mexer nele move as outras nove.

  **Um tom novo, e ele é da janela estável:** a frase *"grava aqui, manda ali"*
  saía cinza e lá é ciano — `#8be9fd`, o token de INFO da casa
  (`rumble_actions.py:608`, *"a frase explica, não alarma"*). Hoje ela não
  aparece nesta aba (a fita do topo é inerte, decisão sua de 28/08); nasce no
  tom certo quando a força ganhar endereço por controle.


## 07-lancadores.html
- **02/09/2026** — **um comentário HTML dentro da lista do cartão da Steam, e
  nenhum pixel mudou.** O `<div class="lanc-fora">` nascia VAZIO; ele passa a
  nascer com `<!-- ainda não há lista para este cartão -->`, que o navegador
  renderiza como nada.

  **Por que ele existe:** o `escrever()` do piloto troca vazio por travessão
  antes de despachar o alvo (`hefesto_vivo.py:118`), inclusive no alvo `html`.
  Enquanto o produto emitia `steam-fora=""`, a tela ganhava um **`—` solto** no
  pé do cartão — fotografado em 02/09 nos dois estados sem leitura, e no da
  **Steam ilegível ele é permanente**: justo a tela em que ela precisa ler uma
  mensagem, com um traço mudo pendurado embaixo.

  O comentário não é vazio (logo o travessão não entra) e não é frase (logo não
  afirma o resultado de uma leitura que não aconteceu). A raiz é uma linha no
  piloto — separar `alvo === 'html'` do vazio genérico —, e está relatada como
  trabalho do PINTOR.

  **O que espera o seu OK:** nada visual. A bancada e o publicado diferem por
  esta linha só; enquanto ela não publicar, o produto que ela usa continua
  igual.
