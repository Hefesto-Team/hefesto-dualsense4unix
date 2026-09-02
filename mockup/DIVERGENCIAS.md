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


## 04-iluminacao.html
- **02/09/2026** — **a dica da célula `LEDs` saiu do atributo da célula e entrou
  no desenho**, e são as suas duas decisões de hoje na mesma frase. A que estava
  cravada dizia:

      title="O Cosmic Red aceso: as duas tiras na cor escolhida, e as cinco
             lâmpadas no padrão do Player 1."

  **O nome** era o do mockup: com o seu controle na mesa, a mesma coluna escreve
  `P1 • White • USB` no rótulo e `Cosmic Red` na dica, dez pixels abaixo — *"a
  interface mostra o que tá conectado e não o controle do mockup"*. **E a
  palavra `aceso`** afirma um estado do aparelho que ninguém pode conferir:
  você já tinha mandado tirá-la, a janela GTK obedeceu em 25/08
  (`lightbar_actions._PREFIXO_DESENHO` passou a dizer *"Desenho que
  mandamos"*), e o mockup a reintroduziu.

  **Por que ela não podia ficar onde estava:** `title` é ATRIBUTO, e o piloto
  não tem alvo de pintura para atributo — os alvos são `texto`, `largura`,
  `fundo`, `valor`, `html`, `classe` e `cor`. Toda dica escrita na célula fica
  congelada no que o gerador soube, e o gerador só sabe o mockup. Dentro do
  desenho ela viaja pelo alvo `html`, que se troca a cada tique.

  **A frase nova não tem uma palavra minha.** Ela é o nome vivo do controle mais
  duas frases que já têm dono no motor: a ressalva da barra
  (`controller_card.rotulo_lightbar`, que sabe os quatro estados em que a cor
  publicada não é a que está no plástico) e o desenho das cinco lâmpadas
  (`lightbar_actions.texto_do_desenho_aceso`). Na sua mesa de agora ela lê:

      White (USB) · Desenho que mandamos: desenho do P1 — automático, do número
      deste controle.

  **O que espera o seu OK:** a frase acima, e nada mais. Nenhum pixel mudou —
  a dica só aparece ao passar o mouse.

  **E o que espera a PUBLICAÇÃO, que é ato seu:** a célula `LEDs` da sua tela
  continua mostrando as duas tiras congeladas do desenho — azul a 82% na coluna
  do P1, enquanto a linha `Brilho` da mesma coluna já diz `100%`. A aba discorda
  de si mesma, e a causa é só o endereço: o publicado ainda diz
  `data-campo="aceso"` e a bancada diz `data-campo="luz"`. Medido em 02/09: o
  produto emite `opacity:1.0` (o brilho vivo) e a tela mostra `opacity:0.82` (o
  do arquivo). **Não dá para curar sem publicar** — escrever no endereço velho
  apagaria o desenho, porque ali o alvo é `texto` e `textContent` mata os filhos
  (é a razão de `pacotes.enderecos_que_o_texto_apaga`, que protege esta célula
  pelo nome). Publicando a 04, a célula passa a viver.
