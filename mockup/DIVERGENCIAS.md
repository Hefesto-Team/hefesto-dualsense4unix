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


## 06-navegacao.html
- **02/09/2026** — **o L3 passou a ALTERNAR o teclado na tela, e as 21 listas
  ganharam a opção que diz isso.** Decisão sua, verbatim: *"deixar no preset do
  botão L3, no mapeamento, abrir o teclado virtual e fechar o teclado virtual
  caso apertado novamente."*

  O que mudou no desenho, e é só isto: cada `<select>` de ação ganhou
  **`Abrir e fechar o teclado na tela`** no grupo *Executar Comando*, e a linha
  do **L3** passou a nascer com ela marcada. Nenhum pixel a mais — 56 linhas,
  todas dentro dos `<select>`. As outras vinte listas ganham a opção porque a
  lista é UMA (`core/acoes_de_botao.ACOES`), e nenhuma delas muda de escolha.

  **O produto JÁ alterna** — o `__TOGGLE_OSK__` está no mapa de fábrica e o
  daemon o cumpre. Enquanto você não publicar, a página que o produto renderiza
  continua oferecendo só *Abrir* e *Fechar*, e a linha do L3 continua
  **mostrando** *"Abrir o teclado na tela"*: o piloto se recusa a escrever num
  `<select>` um texto que ele não oferece (`hefesto_vivo.py`, ramo
  `alvo === 'valor'`), então o campo fica no que está cravado em vez de ficar em
  branco. É tela desatualizada, não tela quebrada.

  **O QUE ESPERA O SEU OK É O TEXTO, não o comportamento.** Você decidiu o que o
  botão faz; o rótulo é leitura direta da sua frase. Se preferir outro — *"Abrir
  ou fechar o teclado na tela"*, *"Teclado na tela (abre e fecha)"* — ele muda
  em um lugar só (`core/acoes_de_botao.ACOES`) e as 21 listas acompanham.

  Publicar: `scripts/check_o_desenho_aprovado.py --publicar 06`.


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
