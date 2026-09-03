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
## 03-gatilhos.html
- **02/09/2026** — **as suas três decisões da tarde sobre esta aba.** Nenhuma
  delas inventa nada: as duas primeiras mudam o que a tela DIZ, e a terceira dá
  dono a uma seção que já estava desenhada.

  **1. A caixa de ajustes acompanha o modo** (sua decisão 2). Ela reservava
  quatro casas à esquerda e duas à direita, e cinco dos 19 modos do produto
  pedem mais: `Galope` 5, `Metralhadora` 6, `Montar do zero` 8, `Curva de
  força` 10 e `Vibração por posição` 11. O que sobrava **não aparecia** — a
  tela calava sobre números que estão no seu disco. Agora a caixa é uma lista
  do tamanho do modo, e as cinco colunas continuam acabando no mesmo y porque
  a grade passou a ser uma só (`subgrid`).

  **Medido nos seus 33 perfis, um por um:** CINCO têm gatilho configurado
  (`acao`, `aventura`, `corrida`, `esportes`, `fps`). Destes, **`aventura` tem
  `Curva de força` nos dois gatilhos e `corrida` tem `Vibração por posição` no
  R2** — dois perfis, e os dois mostravam quatro barras EM BRANCO (travessão no
  nome e no valor) sobre dez e onze intensidades gravadas no seu disco. Agora
  mostram o nome e o número de cada posição.

  | | a caixa do L2 | a aba rola |
  | --- | --- | --- |
  | a cena deste desenho | 92 px (4 barras) | 0 px |
  | `Vibração por posição` nos dois lados | 253 px (11 barras) | **230 px** |

  Você aceitou a rolagem com todas as letras — *"a aba passa a rolar nos modos
  grandes, e isso é aceito"*. **O que ainda pode ser escolhido:** hoje a caixa
  nunca fica MENOR que o que este desenho reserva (92 px no L2, 46 no R2),
  mesmo com o gatilho desligado nas quatro colunas. Deixá-la encolher devolveria
  92 px de altura quando não há o que ajustar — e mudaria a proporção que você
  aprovou em 27/08. Fica como está até você dizer.

  **2. O lugar vazio mostra `—`** (sua decisão 13). Os dois campos de escolha
  ganharam a opção, e o P3 e o P4 do desenho passaram a mostrá-la no lugar de
  `Desligado` e `— Nenhum —`. É a sua razão: *"`Desligado` é uma escolha
  legítima de um controle conectado"*. A opção nasce `disabled` — o produto a
  escreve, ninguém a escolhe com o rato.

  Isto **revoga a metade da sua decisão de 31/08** que dizia *"tudo com
  Desligado e Nenhum"*; o resto dela (a coluna fica, a borda de cor sai) segue
  valendo, e a régua do gerador continua cobrando as duas metades.

  **3. Nasceu o campo do nome do efeito** (sua decisão 17). *"Isso é pra quando
  o user salva algum efeito. (…) O nome que o user deixar lá. Ali é só
  exemplo."* Cada coluna ganhou um campo `Nome` ao lado do "Guardar esse
  efeito": com um nome, o par L2+R2 daquela coluna entra em **Meus efeitos** e
  passa a aparecer no campo de escolha das quatro colunas; em branco, o botão
  faz exatamente o que sempre fez.

  **Custo de altura: ZERO** — o campo divide a linha do botão, que já tinha
  34 px. O campo mede 74 px, e é pouco: cabe o nome inteiro (ele rola por
  dentro), mas o texto de exemplo teve de encurtar de "Nome do efeito" para
  "Nome". **Se você quiser um campo confortável**, o preço é uma linha nova de
  48 px na coluna — a grade tem 24 px de folga sobre o teto medido, então ela
  sairia dos 24 e de mais 24 de outro lugar. É sua a escolha.

  **Os dois exemplos do desenho ficam** — `Recuo do MK` e `Freio do carro` —,
  e é o que você mandou. O que o PRODUTO mostra é a sua biblioteca: enquanto
  ela estiver vazia, o separador "Meus efeitos" não aparece na tela, porque
  *"se não tá mostrando agora, não tem info pra mostrar no produto"*.

  **Onde os efeitos moram:** `~/.config/hefesto-dualsense4unix/gui_preferences.json`,
  a caixa de preferências que a interface já tinha. **Não** no perfil, de
  propósito: um efeito seu é da sua biblioteca, e guardado no perfil ele
  existiria só naquele jogo e sumiria nos outros 32.

  **O que espera o seu OK:** as três acima, e o texto novo — o `Nome` do campo,
  a dica dele e o aviso da caixa cheia (abaixo).

  ### O QUE VOCÊ VÊ HOJE, ANTES DE PUBLICAR — e por que vale a pena publicar

  **CORREÇÃO DE FATO, 02/09/2026.** Este parágrafo dizia que *"o produto que
  você usa mostra as caixas certas, isso já vale hoje"*. **Não valia, e o
  contrário era pior:** a decisão tem duas metades e elas caíram em lados
  diferentes desta fronteira. A que ENCHE a caixa é o produto e valia mesmo; a
  que a faz CRESCER é o desenho, e desenho só chega à sua tela quando você
  publica. Medido no navegador, sobre o arquivo que o produto renderiza agora,
  com os seus perfis:

  | | o que acontecia |
  | --- | --- |
  | `aventura` (Curva de força nos dois) | 10 barras numa caixa de 92 px → **58 px por cima da linha de baixo** à esquerda, **104 px** à direita |
  | `corrida` (Vibração por posição no R2) | 11 barras em 46 px → **119 px** |

  As `Posição 7/8/9` caíam em cima do campo **Modo** do R2 e as barras do R2 em
  cima do **Guardar esse efeito**, saindo da moldura do quadro.

  **Curado antes de chegar em você.** O produto agora **pergunta à página** de
  quantas barras ela dá conta, e se limita a isso — e a última casa passa a
  dizer quantos ajustes ficaram de fora: *"+7 não cabem nesta caixa ainda"*.
  Nada vaza, nada é destruído (o "Guardar esse efeito" continua lendo os dez
  valores, mesmo os que a caixa não mostra) e nada é calado.

  **O preço, e ele é seu para aceitar:** na página de hoje a última barra vira
  o aviso. Nos três perfis de três ajustes num lado de duas casas (`acao`,
  `esportes`, `fps`), você passa a ver **um** número em vez de dois, com o aviso
  ao lado. Se preferir ver os dois e ficar sem o aviso, é uma linha — diga.

  **No dia em que você publicar, o teto some sozinho:** o produto lê a
  declaração nova, a caixa passa a ter o tamanho do modo e o aviso deixa de
  existir. Ninguém precisa mexer em código para isso acontecer.

  E, enquanto você não publicar, o lugar vazio continua dizendo `Desligado`,
  porque a página publicada ainda não oferece o `—`. O dia da publicação troca a
  palavra sozinho, pelo mesmo mecanismo.


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
