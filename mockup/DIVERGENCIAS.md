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

  A linha **some** quando não há nada a dizer (`.vib-estado:empty`).

  **CORRIGIDO EM 02/09/2026 — o número anterior foi medido na cena errada.**
  Esta seção dizia *"no estado normal ela cabe sem fazer a aba rolar — o miolo
  tem 564 px e o quadro passou de 476 para 498"*. Isso é verdade sobre o
  desenho CRAVADO, que tem UMA linha de propósito; é falso sobre a sua máquina.
  Medido no WebKit da janela do produto (1180x757), com os seus dois controles:

  | | quadro | a aba rola | a linha de estado |
  | --- | --- | --- | --- |
  | a cena do desenho | 528 px | 0 px | 1 linha, 18 px |
  | **a sua mesa agora** | 570 px | **40 px** | 2 linhas, 60 px |

  O miolo tem 530 px de conteúdo: **dois px de folga**, e o seu estado custa 42.
  Resultado fotografado: a segunda linha do alerta laranja — *"que você fixar
  aqui embaixo."* — fica **cortada** pela borda de baixo, com barra de rolagem à
  direita. Para ler o aviso inteiro você tem de arrastar.

  **O que espera o seu OK, e agora é uma escolha entre três:**

  1. **deixar como está** — a aba rola 40 px quando há alerta, e você arrasta;
  2. **o bloco no TOPO do quadro**, ao lado do título — o aviso fica sempre
     inteiro à vista, e quem sai de vista é a linha "Testar agora" embaixo;
  3. **encolher uma linha da tabela** em ~42 px — cabe tudo, mas mexe no
     desenho que você aprovou em 27/08.

  Não dá para caber sem escolher: o `.miolo` é do `topo.html`, comum às dez
  abas, e mexer nele move as outras nove.

  **Um tom novo, e ele é da janela estável:** a frase *"grava aqui, manda ali"*
  saía cinza e lá é ciano — `#8be9fd`, o token de INFO da casa
  (`rumble_actions.py:608`, *"a frase explica, não alarma"*). Hoje ela não
  aparece nesta aba (a fita do topo é inerte, decisão sua de 28/08); nasce no
  tom certo quando a força ganhar endereço por controle.

## 08-conexoes.html
- **02/09/2026** — **dois endereços novos no Check-up, e nenhum pixel mudou.**
  O desenho é o mesmo que ela aprovou; o que a bancada ganhou foram dois
  `data-campo` em elementos que já estavam lá, para que o produto pare de
  mentir neles:

  | onde | o que era | o que passa a escrever |
  | --- | --- | --- |
  | o `?` de cada uma das cinco linhas | a explicação do MOCKUP, ao lado do achado DELA | `secao_exame._dica_do_item` — o que a linha significa, a medição desta rodada e a cura |
  | o `Examinado há 3 minutos` do topo | a frase fixa desde que o mockup nasceu | `secao_exame.frase_de_quando`, com a idade do último **Examinar Portas** |

  Fotografado nesta bancada, com dois controles na mesa: a linha 1 dizia
  **"Economia de energia desligada"** e o `?` ao lado explicava *"as entradas
  em uso entregam 500 mA ou mais"* — a medição de OUTRO achado. Nas duas
  posições que o exame não preencheu, o texto vinha `—` e o `?` continuava
  contando os quatro rádios vizinhos do desenho.

  **O pacote já emite os dois** (`achado-explica` e `examinado`): no dia em que
  ela publicar, a tela nasce certa; até lá o piloto não acha o endereço e
  escreve zero — nada muda no produto que ela usa.
