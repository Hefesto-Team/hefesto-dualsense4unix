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

---

## 08-conexoes.html

**A identidade do controle passou a vir da FITA — 03/09/2026.**

**Sprint:** `IDENTIDADE-VEM-DE-CIMA-01`. **Lei sua, 03/09:** *"se no topo tá
mostrando controle white player 1, então cada aba vai usar os controles lá de
cima. Não mistura com a info dos mockups."*

**A régua `scripts/check_identidade_vem_de_cima.py --bancada --aba 08` foi de
15 para ZERO.** Os quinze eram nomes de plástico e `--plastico:#hex` escritos
na página, em quatro lugares: a fita do topo, as linhas da Gestão de Controles,
a régua de Desempenho e a lista de aparelhos da tela "Mapear entrada a entrada".

**NENHUM PIXEL DO SEU DESENHO MUDOU.** A bancada continua mostrando as mesmas
cores, os mesmos rótulos e os mesmos números — o `git diff` do HTML é só
endereço e comentário, mais UMA troca de forma: a cor da barra da linha do
controle saiu de `--plastico:#hex` no `.gc-item` e virou a tinta de um `<i>` de
3 px sobreposto à mesma borda. **O motivo é medido:** o piloto sabe escrever
`background` e `color`, e **não sabe escrever uma variável de CSS** — não há
alvo de custom property no `hefesto_vivo.escrever()`. Sem essa troca, a cor da
sua linha continuaria cravada no vermelho do desenho.

**O QUE MUDA NO PRODUTO, com os seus dois controles na mesa** (medido com o
piloto, janela oculta, a bancada encenada na pasta do publicado e devolvida por
cópia logo depois — a página publicada não foi tocada):

| a linha do controle | antes | depois |
| --- | --- | --- |
| P1 (o do cabo) | `Sony · Player 1 · Cosmic Red · USB` | `Sony · Player 1 · White · USB` |
| P2 (o do rádio) | `Sony · Player 2 · Starlight Blue · BT` | `Sony · Player 2 · BT` |
| a barra da esquerda | vermelha, do desenho | a cor lida — e VAZIA quando não houve leitura |

**O P2 perde o pedaço do plástico de propósito, e é a sua regra:** *campo sem
informação não mostra nada*. Pelo rádio o Hefesto ainda não pergunta a cor
(`ONDA-CONEXOES-11`), a mesa responde `Não sei`, e nem o `Não sei` nem a cor do
mockup entram na tela. **No dia em que a leitura por rádio chegar, o pedaço
volta sozinho** — nada aqui precisa ser mexido de novo.

**A régua de Desempenho (os turnos do rádio) virou bloco do produto.** Ela
nasce do que a máquina sabe: quem está no rádio, em qual adaptador
(`radio_da_mesa.adaptador_por_uniq`) e quanto cada fatia custa. **Uma coisa
piora à vista e é honesta:** o nome do adaptador passa a ser **Sem nome**, e a
dica `TP-Link UB500 — Entrada 3` some. O apelido mora na sua declaração,
endereçado por caminho de barramento, e a chave aqui é o endereço de rádio — as
duas não casam hoje. **Sem nome** é a palavra que o próprio produto já usa
(`gui/aba_conexoes.html_das_pistas`); nenhuma palavra nova nasceu.

**O QUE AINDA MOSTRA O DESENHO NESTA ABA, e não é meu de consertar:**

1. **A fita do topo continua dizendo `P1 · Cosmic Red · USB` e
   `P2 · Starlight Blue · BT`.** O piloto a reescreve inteira a cada tique — mas
   `hefesto_vivo._fita` **desiste quando UM controle da mesa está sem cor**, e o
   seu do rádio está. Um controle sem cor cala a fita inteira, e o desenho fica.
   O arquivo é das dez abas; o conserto é de quem for dono dele.
2. **O desenho pequeno do DualSense dentro da linha aberta continua no plástico
   do mockup.** A cor dele viaja num ATRIBUTO (`data-colorway`) e o piloto não
   tem alvo de atributo. **Tentei a rota óbvia e ela reprovou na medição:**
   trocar o `<svg>` inteiro custou **31 pinturas em 31 tiques** (uma por tique,
   para sempre) e triplicou o tique — **4,24 ms → 13,56 ms**. A cura certa é um
   alvo de atributo no piloto, e vale para as cinco abas que desenham controle.

**O QUE O PRODUTO FAZ ENQUANTO ESPERA O SEU OK, e é o custo desta espera:** a
página publicada não tem nenhum dos quatro endereços, então **na tela dela hoje
a Gestão de Controles continua dizendo `Cosmic Red` e `Starlight Blue`**, com a
borda vermelha do desenho. Nada quebra: o pacote emite os quatro campos, o
`achar()` do piloto não encontra onde escrever e devolve zero — **medido em
03/09 com os dois controles na mesa: 24 valores por tique com a página
publicada, 29 com a bancada no lugar dela.** Os cinco de diferença são
exatamente esta cura, e eles só chegam à sua tela quando você publicar.

**NÃO FOI PUBLICADO.** Publicar é ato seu:
`scripts/check_o_desenho_aprovado.py --publicar 08`.
