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

## 02-controles.html
- **02/09/2026** — **QUATRO endereços novos**, e três deles são decisão sua deste
  dia. Nenhum muda o que a tela DESENHA: o card continua idêntico ao aprovado.
  O que muda é que quatro pedaços que eram desenho cravado passam a ter dono.

  | endereço | onde | o que era | o que passa a ser |
  | --- | --- | --- | --- |
  | `alto-num` | o `100` ao lado da barra do alto-falante | **cravado**, igual em todo controle | a porcentagem viva, pela curva medida no hardware |
  | `alto-barra` | a barra do alto-falante | cravada em `width:100%` | a mesma porcentagem, como largura |
  | `luz-cor` | o retângulo da Barra de luz | `background:#7EB8D4` do mockup | a cor viva do LED, ou nada quando não se sabe |
  | `touch-ponto` | o pontinho do touchpad | aceso pelo `style` do desenho | **só aparece quando há toque** |

  **Item 16 da sua lista, palavra por palavra:** *"o volume do alto-falante ganha
  endereço. O número E a barra. Hoje os dois estão congelados: com o volume em
  40, a tela mostra 100."*

  **Item 15:** *"o pontinho do touchpad só aparece quando há toque — hoje ele
  aparece com `touching` falso, contra o que a própria dica promete."*

  **O `luz-cor` não estava na sua lista, e é um defeito que a foto pegou.**
  Fotografada a aba em 02/09 às 19h, com os seus dois controles: o campo dizia
  `#0000FF` (a cor viva do P1) e o retângulo logo abaixo dele estava no
  `#7EB8D4` do mockup. **O campo e o desenho ao lado dele diziam cores
  diferentes, na mesma moldura.** A régua do mockup não vê isso — ela conta
  `data-campo`, e o retângulo não tinha nenhum.

  **DUAS MUDANÇAS DE PALAVRA, e as duas são o item 15:** o canto do touchpad
  passa a dizer **`Sem toque` / `1 toque`** em vez de `Sem toque` / `Tocando`.
  `Tocando` era palavra do desenho; `1 toque` é a do produto
  (`app/widgets/sensor_widgets.texto_toques`), a mesma que a janela GTK escreve.

  **O QUE VOCÊ VÊ ENQUANTO ESPERA:** nada muda, e nada piora. Os quatro
  endereços não existem na página publicada, então o piloto não os acha e
  o pacote escreve zero neles — a régua de endereço órfão cobra exatamente
  isso. Até você publicar a 02, o número do alto-falante continua em `100`,
  a barra continua cheia, o retângulo da Barra de luz continua no azul do
  desenho e o pontinho do touchpad continua aceso. **Os quatro nascem
  certos no minuto do `--publicar 02`**, sem ninguém tocar em código.
  **`2 toques` a tela ainda não pode dizer**: o daemon publica UM booleano
  (`touchpad.touching`), não uma contagem de dedos — no dia em que publicar, a
  palavra sai sozinha, sem ninguém tocar nesta aba.

  **O que o produto ainda NÃO alcança, e espera outro trabalho:** a POSIÇÃO do
  ponto. O `left`/`top` dele continua o do desenho (`62%`/`44%` no P1), porque o
  piloto não tem alvo de posição — os sete são
  texto·largura·fundo·valor·html·classe·cor. O dado existe e já está calculado
  (`controller_card.touchpad_do_inputs` devolve a fração x/y); falta o alvo.

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

  **O QUE ELA VÊ ENQUANTO ESPERA:** nada muda. O bloco do estado só existe
  na bancada, então o `querySelector` do piloto devolve `null` na página
  publicada e o laço não faz coisa nenhuma — medido: 2 pinturas e 14
  valores, iguais antes e depois. A aba continua exatamente como está até
  ela publicar; o aviso de que a força não chega a jogo nenhum nasce no
  minuto do `--publicar 05`.

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


## 08-conexoes.html
- **02/09/2026** — **o QUARTO SELO do Check-up**, que é a sua decisão de hoje:
  *"o que está quebrado agora não pode parecer igual ao que só podia estar
  melhor."*

  O exame da mesa tem QUATRO estados (`certo`, `atencao`, `problema`,
  `nao_sei`) e esta tela tinha TRÊS cores: `atencao` e `problema` dividiam a
  pílula laranja, pela mesma palavra do mapa do produto
  (`gui/aba_conexoes.SELO_DO_ESTADO`).

  **O que mudou na bancada, e são duas linhas:**

  1. cada uma das cinco pílulas ganhou o endereço `data-campo="selo-estado"`,
     com alvo `classe` — o produto acende `grave` na linha cujo estado for
     `problema`. A palavra continua no seu próprio endereço, num `<span>` filho
     (um `data-campo` por elemento, e o selo tem dois dados: a palavra e a cor);
  2. nasceu a regra `.selo.grave{background:var(--red);color:var(--app-bg)}` —
     o `--red` (`#ff5555`) é o token da casa para o que está quebrado, o mesmo
     do `.btn.vermelho`. Ela é declarada DEPOIS da laranja de propósito: as
     duas classes convivem na pílula e a última declarada é a que pinta.

  **Zero pixel mudou no desenho parado.** Nenhuma das cinco linhas cravadas
  está em `problema`, então a bancada abre idêntica à página que você usa. A
  cor só aparece quando a sua mesa tiver um achado quebrado.

  Medido no Chrome, acendendo a classe na segunda linha: `rgb(255, 184, 108)`
  (laranja) → `rgb(255, 85, 85)` (vermelho).

  **O que espera o seu OK, e é a outra metade da decisão: A PALAVRA.**
  `SELO_DO_ESTADO` manda `atencao` e `problema` para **AJUSTAR**, e escolher o
  texto do quarto selo é seu. Enquanto você não disser, a linha quebrada
  aparece vermelha dizendo "AJUSTAR". Três propostas, e a razão de cada uma:

  | palavra | por que ela |
  | --- | --- |
  | **QUEBRADO** | é o que o estado é, e é a sua própria palavra na decisão |
  | **PAROU** | diz que era para funcionar e não está — sem julgar de quem é |
  | **URGENTE** | fala do que fazer, e não do que houve; é a que menos afirma |

  Quando você escolher, quem muda é `gui/aba_conexoes.SELO_DO_ESTADO` — e a
  mudança alcança **a janela GTK junto**, porque a linha dela lê o mesmo mapa.

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
  a ressalva da barra, que já tem dono no motor
  (`controller_card.rotulo_lightbar`, e ela sabe os quatro estados em que a cor
  publicada não é a que está no plástico). Na sua mesa de agora, com a barra sem
  ressalva a dizer, ela lê só:

      White (USB)

  **E ela ficou nisso porque uma segunda frase CAIU no mesmo dia.** A dica também
  dizia *"Desenho que mandamos: desenho do P1 — automático, do número deste
  controle"*, e essa era uma afirmação que esta aba não pode fazer. O desenho das
  5 luzes é resolvido por um merge de cinco camadas no daemon, e a que decide
  quando você aplica um desenho na janela GTK — o *override* por controle — fica
  ACIMA da automática. **A aba não recebe essa camada:** o `state_full` publica
  o número do controle e não publica `player_leds`. Reproduzido com o merge de
  verdade, sem tocar o aparelho: com o override preenchido, o produto manda
  `[T,F,F,F,T]` e a tela dizia *"desenho do P2 — automático"*. É a sua regra de
  hoje — *"se não tá mostrando agora, não tem info pra mostrar no produto"* —,
  então a frase saiu. **Ela volta sozinha, correta, no dia em que o daemon
  publicar o desenho em vigor**; nada aqui precisa ser mexido de novo.

  Sobra UM caso em que a aba pode afirmar, e ele continua sendo a frase do motor:
  com o **co-op numerando mais de um jogador**, a camada de co-op está acima do
  override, e a dica diz que é ele que manda nas 5 luzes.

  **O que espera o seu OK:** as duas coisas acima — a dica que passa a nomear
  quem está conectado, e a frase do desenho das 5 luzes que saiu. **Nenhum pixel
  mudou:** a dica só aparece ao passar o mouse.

  **E mais uma coisa que estava por declarar** (achada na auditoria do mesmo
  dia): os oito botões da guia de cores de cada coluna conectada ganharam
  endereço — `data-campo="hex" data-hef-alvo="classe"`, dezesseis atributos ao
  todo. Isso NÃO muda pixel no desenho, mas muda o produto depois da publicação:
  o anel que marca a cor escolhida deixa de ficar cravado no tom do mockup e
  passa a acender na cor viva. Sem isso, escolher uma cor fora da guia de oito
  (o seletor livre existe para isso) deixava o anel parado no tom velho para
  sempre.

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

## 01-jogar.html
- **03/09/2026** — **a borda do cartão passou a ser a cor do SEU controle**, e é
  a sua lei de hoje: *"se no topo tá mostrando controle white player 1, então
  cada aba vai usar os controles lá de cima. Não mistura com a info dos
  mockups."*

  **O que estava na tela, fotografado com os seus dois controles na mesa:**

  | | o rótulo do cartão | a BORDA do cartão |
  | --- | --- | --- |
  | P1 (no cabo) | `White · USB` | **Cosmic Red** |
  | P2 (no rádio) | `Não sei · BT` | **Starlight Blue** |

  O cartão discordava de si mesmo com quatro pixels entre uma coisa e outra: o
  rótulo já era leitura do aparelho e a borda ainda era o desenho. E a do P2 era
  pior que velha — era **inventada**: ninguém leu a cor daquele controle.

  **O que mudou no desenho, e são três coisas:**

  | | o que era | o que passa a ser |
  | --- | --- | --- |
  | a cor da borda | `style="--plastico:#ae335a"` no cartão | uma **pele** endereçada (`data-campo="plastico"`, alvo `cor`), que o pacote escreve com o hex do mapa |
  | a dica do cartão | `title="Sony • Player 1 • Cosmic Red • USB"` | **saiu** — ela repetia o rótulo palavra por palavra, e `title` é atributo: o piloto não tem alvo para atributo, então ela só podia dizer o que o mockup sabia |
  | a citação da fita na legenda | `"Ajustes vão para: [Todos] [P1 · Cosmic Red · USB]…"` | `"Selecionar: [Todos] [P1 · o plástico · USB]…"`, com o rótulo lido de `monta.ROTULO_DA_FITA` |

  **POR QUE UMA PELE, E NÃO A COR NO PRÓPRIO CARTÃO:** o `escrever()` do piloto
  tem sete alvos — texto, largura, fundo, valor, html, classe e cor — e **nenhum
  escreve uma custom property do CSS**. Um `--plastico` cravado é, por
  construção, cor que o produto nunca alcança. O alvo `cor` escreve
  `style.color`, e `color` **herda**: posto no cartão, ele desceria até o
  desenho grande, que tem 16 traços em `currentColor` — o controle inteiro
  mudaria de cor junto. A pele é um elemento vazio deitado exatamente sobre a
  borda (2px, mesmo raio, `pointer-events:none`), e é o que permite trocar a
  moldura sem tocar no desenho.

  **NENHUM PIXEL A MAIS MUDOU, e está medido nas duas direções.** As duas fotos
  do produto — antes e depois, com os seus dois controles vivos — foram
  comparadas pixel a pixel:

  | o que foi comparado | pixels diferentes |
  | --- | --- |
  | a tela toda, fora da fileira de cartões | **0** |
  | o miolo do cartão do P1 (dentro da moldura) | **0** |
  | o miolo do cartão do P2 (dentro da moldura) | **0** |

  O que muda são as duas molduras de 2 px, e só elas: nada moveu, nada
  reposicionou, nenhuma letra andou um pixel.

  **O P2 FICA SEM COR, E É DE PROPÓSITO.** A cor do plástico só se lê **pelo
  cabo** (o mapa diz isso: `identidade.cor_do_aparelho`, `radio_aciona = não`),
  então o controle no rádio não tem cor a mostrar. O pacote manda vazio, o alvo
  `cor` apaga o `style.color` e a moldura volta ao cinza neutro que o cartão já
  usava quando faltava plástico. **É a sua regra:** campo sem informação não
  mostra nada. No dia em que a leitura por rádio chegar, a moldura dele acende
  sozinha, sem ninguém tocar nesta aba.

  **O QUE VOCÊ VÊ ENQUANTO ESPERA:** nada muda, e nada piora. A pele não existe
  na página publicada, então o piloto não a acha e o pacote escreve nela zero
  vezes — a moldura do produto que você usa continua no Cosmic Red e no
  Starlight Blue do desenho, exatamente como está hoje. **As duas nascem certas
  no minuto do `--publicar 01`**, sem ninguém tocar em código.

  **O QUE ESTA FRENTE NÃO ALCANÇOU, e é honesto dizer, porque está na mesma
  foto:**

  1. **A FITA DO TOPO CONTINUA DIZENDO `Cosmic Red` E `Starlight Blue`** —
     inclusive na sua tela de agora. Os chips dela saem de `monta.fita()`, que é
     das dez abas, e o piloto os repinta em bloco; mas ele desiste da fita
     INTEIRA quando **um** controle da mesa está sem cor
     (`hefesto_vivo._fita`, `any(not c.get("cor") …)`), e é exatamente o seu
     caso: um no cabo com cor, um no rádio sem. Com dois controles na mesa, um
     deles no rádio, a fita nunca é repintada.
  2. **O DESENHO PEQUENO dentro do cartão continua na cor do mockup.** Ele é o
     SVG, pintado no arquivo; trocá-lo pede que o pacote emita o desenho
     inteiro a cada tique, e isso é outro trabalho.

  As duas moram em arquivos que esta aba não possui (`monta.py` e
  `hefesto_vivo.py`) e valem para as **dez** abas — estão relatadas para quem
  cuidar da camada compartilhada.
---

## 02-controles.html — a identidade vem da fita
- **03/09/2026** — **os DEZ valores de identidade congelados desta aba foram a
  ZERO**, e a lei é sua:

  > *"se no topo tá mostrando controle white player 1, então cada aba vai usar
  > os controles lá de cima. Não mistura com a info dos mockups. Cada feature faz
  > referencia ao controle conectado. Por isso temos o mapa pra servir como <!-- noqa-acento: citação literal dela -->
  > variável de identificação"*

  **O QUE ESTAVA NA SUA TELA**, fotografado nesta árvore em 03/09 com os seus
  dois controles ligados — um `White` no cabo, um por rádio:

  | | o que a tela dizia |
  | --- | --- |
  | a fita do topo | `P1 · Cosmic Red · USB` · `P2 · Starlight Blue · BT` |
  | o cabeçalho do card | `Cosmic Red · USB` |
  | a linha fechada | `P2 · Starlight Blue · BT` |
  | a borda das duas caixas | vermelha e azul — as cores do desenho |

  **Nenhuma dessas quatro coisas é um controle seu.** A fita foi consertada e
  ninguém percebeu que a aba abaixo dela continuava mostrando o desenho.

  **O QUE MUDOU NO DESENHO: uma linha de texto, e é uma DICA.** O chip da fita
  dizia, ao passar o mouse, `Cosmic Red — a borda é a cor do plástico`; agora diz
  `Clique para abrir o card dele — a borda é a cor do plástico.` O nome saiu do
  `title` porque ele era a **segunda cópia congelada** do mesmo fato, e uma dica
  não tem como ser repintada pelo produto — ela sobreviveria ao conserto do texto
  e continuaria dizendo `Cosmic Red` na sua mesa. **Nenhum pixel mudou** fora
  disso: o card, o chip e a linha fechada continuam idênticos ao que você
  aprovou.

  **OS CINCO ENDEREÇOS NOVOS**, e nenhum deles muda o que a tela desenha:

  | endereço | onde | o que era | o que passa a ser |
  | --- | --- | --- | --- |
  | `peca` | o nome no cabeçalho do card e na linha fechada | `Cosmic Red` cravado | o nome do plástico lido do aparelho |
  | `via` | o `USB`/`BT` ao lado dele | cravado | o transporte vivo |
  | `fita-peca` | o nome dentro do chip da fita | cravado | o mesmo nome, vivo |
  | `fita-via` | o `USB`/`BT` do chip | cravado | o mesmo transporte |
  | `plastico-css` | uma folha de estilo vazia no fim do `<head>` | não existia | a cor da borda de cada caixa, lida do mapa |

  **A COR SAIU DO `style=` DE CADA CAIXA**, e isso foi obrigatório: estilo de
  linha vence qualquer folha de estilo, então enquanto o `--plastico` morasse ali
  o produto **não tinha como** trocar a cor da borda. Ela virou regra na folha do
  desenho, e o produto escreve por cima na folha endereçada. A cor não é digitada
  em lugar nenhum: sai de `docs/data/cores-do-dualsense.csv` pelo mesmo dono que
  a janela GTK já usa (`cor_do_plastico.tom_para_a_borda`, que também é quem
  impede o Midnight Black de virar *ausência* de borda sobre o fundo escuro).

  **O QUE VOCÊ VÊ NA BANCADA:** exatamente o desenho de sempre — `Cosmic Red` e
  `Starlight Blue`, com as bordas vermelha e azul. A folha nova nasce **vazia**
  de propósito; quem a preenche é o produto, com o que leu.

  **O QUE VOCÊ VAI VER DEPOIS DE PUBLICAR** (medido nesta árvore, com os seus
  dois controles, publicando a bancada num teste e desfazendo em seguida):

  | | antes | depois |
  | --- | --- | --- |
  | fita | `P1 · Cosmic Red · USB` · `P2 · Starlight Blue · BT` | `P1 · White · USB` · `P2 · — · BT` |
  | cabeçalho do card | `Cosmic Red · USB` | `White · USB` |
  | linha fechada | `P2 · Starlight Blue · BT` | `P2 · — · BT` |
  | borda das caixas | vermelha e azul | branca e cinza-neutra |
  | valores pintados | 14 | 24 |

  **O TRAVESSÃO DO CONTROLE DE RÁDIO É A SUA REGRA**, e não uma falta: pelo rádio
  a cor do plástico **não é lida** — o mapa de canais diz `radio_aciona = não`
  para `identidade.cor_do_aparelho`. Campo sem informação não mostra nada, e a
  borda dele fica no cinza neutro que o lugar vazio desta aba já usa. Quando a
  leitura por rádio chegar, o nome e a cor aparecem sozinhos.

  **NADA FOI PUBLICADO.** Publicar continua sendo ato seu:
  `scripts/check_o_desenho_aprovado.py --publicar 02`.
- **03/09/2026** — **A COR DO CONTROLE PASSA A VIR DO APARELHO.** É a sua lei
  deste dia: *"se no topo tá mostrando controle white player 1, então cada aba
  vai usar os controles lá de cima. Não mistura com a info dos mockups."* — e,
  sobre a cor: *"se identificou o controle como modelo White a cor do card em
  volta tem que ser branco. Temos isso no mapa."*

  **O que estava na sua tela, fotografado hoje com os seus dois controles:** o
  rótulo da coluna dizia `P1 • White • USB` — certo, vivo — e a **moldura em
  volta do desenho estava vermelha**, que é o Cosmic Red do mockup. A moldura é
  justamente como esta aba diz de quem é a luz. Eram **39 valores de identidade
  congelados** nesta página; **sobraram 6**, e os seis não são desta aba (ver o
  fim desta seção).

  | o que era | o que passa a ser |
  | --- | --- |
  | a moldura com `--plastico:#ae335a` cravado | `data-campo="plastico"`, e o produto escreve a cor da casca LIDA |
  | *"Apaga a barra de luz do Cosmic Red"* | *"…deste controle"* |
  | *"pinta a barra do Cosmic Red"*, nos 8 botões de cor de cada coluna | *"…pinta a barra deste controle"* |
  | a dica do **Jogador**: *"pôr o Starlight Blue no 1 faz o Cosmic Red virar 2"* | a REGRA: *"quem tem aquele número hoje fica com o deste"* |
  | o **antes/depois** do rodapé, desenhado com os controles do mockup | um bloco vivo, com os controles que estiverem na mesa |

  **SEM COR LIDA, A MOLDURA FICA NEUTRA — e isso é a sua regra:** campo sem
  informação não mostra nada. A cor do plástico chega pelo broker, e hoje o
  controle **por rádio** ainda vem sem ela. Fotografado agora: a coluna do cabo
  com a borda **branca** (o seu White) e a do rádio **cinza**. Antes as duas
  mostravam cor de controle nenhum.

  **NENHUM PIXEL DO DESENHO MUDOU NA BANCADA.** Medido no Chrome, dentro desta
  página, antes e depois: a borda da coluna P1 continua `rgb(174, 51, 90)` e os
  glifos do desenho continuam nas cores de sempre. O que muda é de onde a cor
  vem quando o produto abre a página.

  **O QUE VOCÊ VÊ ENQUANTO ESPERA:** nada muda e nada piora. O
  `data-campo="plastico"` não existe na página publicada, então o produto de
  hoje não acha onde escrever e a moldura fica no que o arquivo diz. **Quando
  você publicar a 04**, a borda passa a ser a do controle de verdade.

  **O QUE FICA ABERTO, e é honesto dizer: o DESENHO dentro da moldura continua
  na cor do mockup.** A borda diz White e o controle desenhado continua
  vermelho. Não é esquecimento — é medida: redesenhar o SVG a cada tique custa
  **4,5 ms e 52 KB por coluna** (medido hoje), contra um tique que hoje leva
  1,4 ms inteiro. O caminho barato existe e não é desta aba: o piloto não tem
  alvo de pintura para ATRIBUTO, e com ele bastaria trocar o `data-colorway` do
  SVG. **O mesmo alvo cura de uma vez as dicas congeladas desta aba**, que são
  `title` e por isso ficam no que o gerador soube.

  **E OS SEIS QUE SOBRAM SÃO DE TODAS AS DEZ ABAS, não desta:** são os dois
  chips da fita — `P1 · Cosmic Red · USB` e `P2 · Starlight Blue · BT` —, que
  saem de `interface/monta.py::fita()`, um arquivo só para as dez páginas. O
  produto já os reescreve por `document.querySelector('.fita')`, mas eles não
  têm endereço no HTML, e por isso toda régua os lê como congelados. A cura é
  uma linha no dono comum, e não dez cópias dela.

## 07-lancadores.html
<!-- SEGUNDA SEÇÃO DESTA ABA, e é de propósito: a de 02/09 continua valendo (o
     comentário HTML no `lanc-fora`), e escrever aqui em vez de lá é o que
     permitiu dez frentes mexerem neste arquivo no mesmo dia sem conflito. -->
- **03/09/2026** — **a fita desta aba deixou de nomear dois controles que você
  não tem.** Esta é a única mudança, e ela é do que se VÊ.

  **O que estava na sua tela**, medido com os seus dois controles na mesa (um no
  cabo, um no rádio), na `07-lancadores`:

  | | o que a tela dizia |
  | --- | --- |
  | cabeçalho | `2 controles: 1 USB · 1 BT` — certo, lido do aparelho |
  | fita | `P1 · Cosmic Red · USB` — **o mockup** |
  | fita | `P2 · Starlight Blue · BT` — **o mockup** |

  Nenhuma das duas cores é de um controle seu. É a sua lei de hoje ao contrário:
  *"se no topo tá mostrando controle white player 1, então cada aba vai usar os
  controles lá de cima. Não mistura com a info dos mockups."*

  **O que a bancada passa a ter:** a fita nasce só com `Selecionar:` e o chip
  `Todos`. **Os dois chips de controle saíram do desenho** — a página estática
  não sabe nada dos seus controles, e a regra é a sua: *campo sem informação não
  mostra nada*. Quem põe os chips é o produto, no tique, com quem estiver na
  mesa naquele instante.

  **O que a sua tela passa a mostrar** (fotografado hoje, com o daemon no ar):

      Selecionar:   [ Todos ]   [ P1 • White • USB ]   [ P2 • BT ]

  O `White` é o seu controle do cabo, lido do aparelho. O do rádio aparece com o
  jogador e o transporte e **cala sobre a cor**, porque o leitor de plástico
  ainda não conhece essa peça — inventar um nome ali seria o mesmo defeito de
  novo, com outra roupa.

  **O que NÃO mudou:** a fita continua esmaecida (nada nesta aba se ajusta por
  controle — sua decisão de 28/08), o chip continua sem a borda de plástico (a
  folha de estilo a apaga na fita inerte, de propósito), e o número do jogador
  continua sendo a POSIÇÃO na mesa, como você disse.

  **O que você vê enquanto espera:** a página publicada continua com os dois
  chips do mockup. Enquanto a 07 não for publicada, a sua tela segue mostrando
  `Cosmic Red` e `Starlight Blue` na fita desta aba.

  **O que fica de fora desta aba, e está relatado:** a fita é das dez páginas.
  `hefesto_vivo._fita` desiste de repintá-la INTEIRA quando qualquer controle
  está sem cor, e é por isso que o desenho sobrevivia — as outras nove abas têm
  o mesmo defeito, e curá-lo aqui seria mexer no arquivo de todo mundo.
