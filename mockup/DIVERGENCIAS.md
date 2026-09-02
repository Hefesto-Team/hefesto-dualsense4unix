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

  A linha **some** quando não há nada a dizer (`.vib-estado:empty`), e no estado
  normal ela cabe sem fazer a aba rolar — medido: o miolo tem 564 px e o quadro
  passou de 476 para 498. Com um alerta aceso a aba rola, e isso é de propósito.

  **O que espera o seu OK:** o texto sai inteiro do produto, mas o LUGAR e o
  tamanho são desenho. Se preferir a linha no topo do quadro, ao lado do título,
  é uma linha no gerador.

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
