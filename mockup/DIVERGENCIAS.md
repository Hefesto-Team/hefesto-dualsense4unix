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


## 10-perfis.html
- **02/09/2026** — **o "Estilo de Jogo" ganha o travessão, e é decisão sua deste
  dia.** O `<select>` passa a nascer com uma primeira opção `value=""`, texto
  `—`, marcada; nenhuma das quinze nasce marcada.

  **Por que ele existe:** o desenho trazia `<option selected>Luta</option>`, e
  por isso os seus **33 perfis** apareciam como `Luta` — um valor que ninguém
  escreveu. O perfil não tem campo de Estilo (`profiles/schema.Profile` não tem,
  `SIMPLE_MATCH_PRESETS` não tem chave), então `perfis_web` devolve
  `estilo: None`. É a sua regra do mesmo dia — *"se não tá mostrando agora, não
  tem info pra mostrar no produto"* — aplicada ao desenho.

  **A pintura não resolvia isto sozinha, e a medição é o motivo de ser desenho:**
  o `escrever()` do piloto troca vazio por `'—'` ANTES do ramo `valor`
  (`hefesto_vivo.py`, `const t = vazio ? '—' : …`). Num `<select>` cuja opção
  vazia tem `value=""`, escrever `'—'` passa a guarda pelo TEXTO da opção e
  depois deixa `selectedIndex = -1`: o campo renderiza **em branco**, e o
  contador de pinturas soma +1 a cada visita porque `el.value` nunca volta igual
  ao escrito. Por isso o pacote **parou de escrever** neste endereço
  (`a10_perfis.NAO_PINTAVEIS`, com a medição) e quem diz o `—` é o desenho.

- **02/09/2026** — **um comentário HTML caduco, e nenhum pixel mudou.** O bloco
  ao lado do trilho da Prioridade dizia que *"enquanto esta página não for
  PUBLICADA por ela, `a10_perfis.NAO_PINTAVEIS` segura a emissão do
  `editor.prioridade`"*. As duas metades caíram: a página foi publicada
  (`70b58116`) e o nome saiu de `NAO_PINTAVEIS` (`1f6e356b`). O texto foi
  substituído pelo fato.

  **O que espera o seu OK:** só a linha do travessão é visível. Enquanto você
  não publicar, o campo continua abrindo em `Luta` no produto que você usa.
