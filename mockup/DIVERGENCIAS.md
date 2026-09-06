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

## 01-jogar.html

- **06/09/2026** — **DOIS ENDEREÇOS NOVOS DENTRO DE CADA CARTÃO**, os dois
  invisíveis na página parada e acesos só pelo produto:

  1. **o marcador «primário»** (`marcador-principal`, alvo `classe`) — a palavra
     que a janela GTK põe na linha secundária do card
     (`home_actions._format_controller_subtitle`) e que esta tela nunca teve.
     Era a linha 18 do CSV da paridade, e o SINAL daquela linha **é este
     endereço**. Ele **não** reusa a classe `.cartao.alvo`, que já existe e
     responde a outra pergunta (o alvo de edição da fita): os dois podem ser
     aparelhos diferentes, e reusar a classe faria os dois significados
     brigarem no mesmo pixel;
  2. **a marca da emulação degradada** (`degradou-cartao`, alvo `atributo`) — o
     `*` laranja com o motivo no ponteiro do mouse, a MESMA gramática do cartão
     da aba 02 (decisão dela de 04/09: *"uma marca na palavra e o motivo no
     hover"*). Era a linha 32 do CSV, e a frase inteira vem do dono
     (`controller_card.texto_degradacao`, por `pacotes.degradacao_de`).

  **Por que não publiquei:** publicar é ato dela, e aqui nasce uma PALAVRA nova
  na tela — «primário» —, que é o caso exato da `PROVA-DE-TELA-01`. A palavra é
  a que ela já lê na janela antiga, e há régua que reprova se as duas se
  afastarem; ainda assim, quem confere que ela chegou certa é ela, olhando.

  **Os dois NASCEM APAGADOS no desenho, de propósito:** quem decide o primário é
  o serviço, e um cartão que nascesse marcado afirmaria um fato que o desenho
  não tem como saber. O mesmo vale para a marca da degradação — um `title`
  cravado acenderia alarme sobre um controle que ninguém mediu. Logo **a cena
  que ela aprovou não muda um pixel**: as duas regras de CSS só acendem sob
  classe e sob `[title]`, e nenhuma das duas está no arquivo parado.

  **O que ela vê HOJE, até publicar:** a aba Jogar de ontem, com os cartões
  dizendo só `{modelo} · {cabo|rádio}`. Os dois endereços saem do pacote a cada
  tique e caem no vazio na página publicada — nada regride enquanto ela espera.
  **Medido no WebKit**, com o mesmo dublê nos dois lados
  (`scripts/ensaios/a_jogar_diz_quem_e_o_primario.py`):

  | | marcador «primário» | marca da degradação |
  | --- | --- | --- |
  | **bancada** | acende no cartão do primário, e ANDA quando ele troca | acende com motivo, some sem ele |
  | **publicado** | **não existe** | **não existe** |

  **E o que NÃO espera publicação:** a linha do **serviço calado** na coluna
  Atenção (o Passo 5 desta sprint). Ela usa os endereços `aviso-selo` e
  `aviso-texto`, que a página publicada já tem — medido no mesmo ensaio, ela
  acende nos dois lados.

  **O que fecha:** `scripts/check_o_desenho_aprovado.py --publicar 01`, depois
  do olho dela.

---

## 10-perfis.html

- **06/09/2026** — **UMA FILEIRA NOVA no editor: o quadro «Modo»**, com os
  QUATRO botões que a janela GTK tem desde sempre (`profiles_actions.
  _install_mode_section`) e que esta tela nunca teve — *Não mexer no modo* ·
  *Controlar o PC* · *Jogar pelo Hefesto* · *Conexão Nativa (Sony)*. Os rótulos
  são dela, de 06/08 (UX-MODE-TERMS-02), e o desenho os LÊ de
  `_MODE_KIND_ITEMS` em vez de digitá-los.

  **Por que não publiquei:** publicar é ato dela, e aqui a mudança é a MAIOR
  desta aba — nasce uma sexta linha em "Definições", com quatro `<button>` onde
  não havia nada. Nem a régua do que-se-vê a absolveria, e não deveria.

  **O que ela vê HOJE, até publicar:** a aba Perfis de ontem — cinco campos e
  nenhum Modo. `editor.modo` sai do pacote a cada tique e cai no vazio na página
  publicada (declarado em `a10_perfis.ESPERANDO_A_PUBLICACAO`), e o gesto
  `editor.modo` não tem botão de onde nascer. **Nada regride enquanto ela
  espera.** Medido no WebKit, com o mesmo perfil no disco, por
  `scripts/ensaios/o_quadro_do_modo_grava_pelo_webkit.py`:

  | | botões do Modo | o campo do jogo consulta a lista? |
  | --- | --- | --- |
  | **bancada** | 4, e o clique grava nos quatro | **sim** |
  | **publicado** | **0** | **não** |

  **DUAS COISAS DE DESENHO VIERAM JUNTO, e as duas são MEDIDAS — quem for
  aprovar precisa saber o que elas compraram:**

  1. **o rótulo do botão quebra em DUAS linhas dentro dele** (`white-space:
     normal`, `flex:1 1 0`, 11,5px). Os quatro rótulos numa fileira normal somam
     **563px** e o `.val` desta coluna tem **412px** — em duas fileiras eles
     custam 82px, e a coluna tinha **41** de folga. Uma varredura de 180
     combinações de altura, padding e margem não achou nenhuma que coubesse. Com
     o rótulo quebrando dentro do botão, a fileira fica com os mesmos 36px de um
     `<select>` desta aba, e nada mais na coluna precisou encolher;
  2. **a tabela «Ajuste próprio» ganhou barra de rolagem** (`overflow-y:auto`,
     no lugar de `overflow:hidden`). Ela é `flex:1` e absorve o que sobra; a
     tira do desfecho (10-Q5) come 37px quando acende, e com a fileira do Modo a
     conta virava negativa — **as linhas do P3 e do P4 sumiam por 30 segundos a
     cada gesto**, sem barra e sem aviso. A barra nasce só quando há o que
     rolar: no tamanho do desenho, sem tira, ela não aparece. É o mesmo
     argumento que o `.rolo` da lista de perfis já tinha escrito.

  **O que NÃO nasceu, por decisão dela (10-Q6, via `ONDA5-10-03`):** as duas
  frases do modo. Nem a linha condicional do rádio frágil no Nativo, nem a dica
  com o custo da máscara Xbox. Há régua cobrando a ausência
  (`test_o_quadro_do_modo_nao_descreve_o_que_perde`), e ela LÊ as constantes de
  `home_actions` em vez de digitá-las.

  **O que fecha:** `scripts/check_o_desenho_aprovado.py --publicar 10`, no OK
  dela da aba.

- **06/09/2026** — **A LISTA SUSPENSA COM OS JOGOS DESTA MÁQUINA**, no campo
  "Nome do Jogo". Um `<datalist>` vazio no desenho, que o pacote enche com o
  catálogo do disco (`integrations/jogos_locais.catalogo_de_jogos`) — o mesmo
  que alimenta o `Gtk.EntryCompletion` da janela GTK.

  **`<datalist>` e não `<select>`**, e a razão é o enunciado dela: *"uma lista
  que recusa o que ela sabe que existe é pior que campo livre"*. O campo
  continua aceitando qualquer texto, inclusive o appid de um jogo que ela ainda
  vai comprar.

  **Por que não publiquei:** o `<input>` ganha um `list=` e o documento ganha um
  elemento. Medido no WebKit vivo: na bancada `input.list` resolve para o
  `<datalist>` e as opções chegam; no publicado não há para onde apontar.
  **Ela não vê pixel nenhum a mais** — o `<datalist>` é invisível até ela
  digitar —, mas o elemento é novo e o `--publicar-enderecos` o recusa.

- **06/09/2026** — **UMA OPÇÃO A MAIS no seletor "Funciona em": "Jogo (pela
  janela)"**, a sexta forma que a ONDA5-10-01 (decisão 10-Q2 dela) fez o produto
  saber guardar. É a regra que o botão "Detectar" passa a gravar quando o jogo
  **não é da Steam** — uma classe de janela só.

  **Por que não publiquei:** publicar é ato dela. Aqui a mudança é VISÍVEL (uma
  linha nova no `<select>`), então nem a régua do que-se-vê a absolveria — e
  não deveria.

  **O que ela vê HOJE, até publicar:** a aba Perfis de ontem, com cinco opções
  no seletor. **E o custo da espera NÃO é zero — medido no WebKit vivo** por
  `scripts/ensaios/o_detectar_grava_o_jogo_de_fora_da_steam.py`, com o MESMO
  perfil no disco (`window_class: ["GrimFandango"]`) pintado nas duas páginas:

  | | opções do seletor | a pintura escreveu | o campo mostrou |
  | --- | --- | --- | --- |
  | **bancada** | 6 (com "Jogo (pela janela)") | 3 de 3 | `Jogo (pela janela)` |
  | **publicado** | 5 | **2 de 3** | **`Jogo`** |

  O `escrever()` do piloto só escreve num `<select>` quando alguma opção CASA
  (`hefesto_vivo.py`, `if(!tem) return 0;`), então o campo **fica com o "Jogo"
  que o desenho cravou** — e o cadeado NÃO acende, porque o produto sabe
  descrever a regra. É o defeito que o `aba10.opts` documenta, pelo avesso: a
  tela afirma "Jogo" sobre um perfil que casa por janela, sem nada ao lado
  dizendo que ela não sabe. O `Detectar` **grava certo no disco** nos dois
  casos; o que espera pelo `--publicar 10` é o rótulo.

  **O que fecha:** `scripts/check_o_desenho_aprovado.py --publicar 10`, no OK
  dela da aba. Nada mais espera por isto.

- **06/09/2026** — **UM RÓTULO NOVO à direita do campo "Nome do Jogo"**, a
  decisão **10-Q4** dela: *"Rótulo ao lado, ao vivo — à direita do campo aparece
  o nome do jogo enquanto você digita, ou «não está nesta máquina», ou «não
  reconheci este endereço»."* Ela recusou a opção que o produto tinha construído
  em 04/09 (a resposta só na tira, depois do `change`), e a escolha ACRESCENTA:
  o campo continua se corrigindo sozinho.

  **Por que a sprint não publicou:** publicar é ato dela, e aqui a mudança é
  VISÍVEL — nascem três `<span>` dentro do `.val` de um campo e o `<input>`
  encolhe de 324px para até 125px.

  **O que ela vê HOJE, até publicar:** a aba Perfis de ontem — o campo do jogo
  sem rótulo nenhum ao lado. Os dois endereços novos (`editor.jogo.rotulo` e
  `editor.jogo.alerta`) saem do pacote a cada tique e caem no vazio na página
  publicada; estão declarados em `a10_perfis.ESPERANDO_A_PUBLICACAO`, e duas
  réguas cobram a declaração nos dois sentidos. **Nada regride enquanto ela
  espera** — medido: `--conta-mutacoes 100` na publicada dá 0 mutações e 35
  valores, o mesmo de antes.

  **O que ela ganha ao publicar**, medido no Chrome com o `BOOTSTRAP` do piloto
  sobre a bancada:

  | o que está no campo | o rótulo diz | cor |
  | --- | --- | --- |
  | `1245620` (jogo instalado) | `ELDEN RING` | cinza |
  | `999999` (jogo que ela ainda vai comprar) | `Não instalado aqui (o número vale).` | cinza |
  | `store.steampowered.com/app/` | `Não reconheci este endereço.` | **laranja** |
  | `mk1.exe` (perfil por programa) | *(o rótulo some)* | — |

  **A METADE QUE NÃO VEM JUNTO:** o *"ao vivo"* tecla a tecla depende de uma
  QUARTA porta de escuta no piloto (`hefesto_vivo.py`), que é da ONDA0-P. Até
  ela existir, o rótulo acerta em todo tique em que ela **não** está digitando —
  ao abrir o perfil, ao trocar de perfil, e um tique depois do `change`. A
  guarda dessa porta já nasceu: `_so_mudou` virou lista de PERMITIDOS, e o
  `input` nasce barrado.

  **E A TIRA PASSOU A DIZER A METADE CURTA** (10-Q5). A fronteira que isso move
  foi medida, e não é a que a sprint supunha: a tira comporta **413 caracteres**
  (bissecção no Chrome) e nenhuma das duas frases passa disso sozinha — quem
  estoura é o NÚMERO DE JOGOS, porque a lista não tem teto. A forma longa cabe
  até DOIS jogos; a curta, até CINCO. A janela GTK e o cartão da Steam continuam
  com a frase inteira, com régua cobrando.

  **O que fecha:** `scripts/check_o_desenho_aprovado.py --publicar 10`, no OK
  dela da aba — junto com a sexta opção do "Funciona em", que já espera aqui.

## 02-controles.html

- **05/09/2026** — **UMA LINHA DE COMENTÁRIO CSS, sem um pixel de diferença.**
  O gerador `aba02.py` teve um endereço de linha remedido (o alvo `classe` do
  `escrever()` mudou de lugar quando o piloto ganhou a piscada da `03-Q4`), e o
  comentário que o cita é EMITIDO dentro do `<style>` da página. A bancada foi
  regerada; o produto não.

  **Por que não publiquei:** publicar é ato dela, e a regra existe porque
  publicar troca o que ela abre. Aqui a mudança é provadamente invisível — as
  dez fotos de `docs/usage/assets/aba-NN-*.png` saíram byte a byte idênticas
  antes desta regeração —, mas *"é só um comentário"* é exatamente o argumento
  com que uma exceção vira hábito.

  **O que ela vê HOJE, até publicar:** exatamente a mesma aba Controles de
  ontem. A página que o produto renderiza continua com o endereço antigo dentro
  de um comentário do `<style>` — nenhum clique, nenhuma frase e nenhum pixel
  dependem dele. O custo da espera é zero, e esta é a primeira declaração desta
  lista de que isso se pode dizer com medição por trás.

- **06/09/2026 — E A LINHA ACIMA DEIXOU DE SER VERDADE NO MESMO DIA.** A
  `ONDA5-02-02` entrou e a aba mudou de VERDADE: o `♪` do alto-falante trocou o
  alvo `classe` pelo `atributo` (`data-som`) e ganhou duas cores lidas do dono
  (`mesa_viva.selo_do_mic`) — ATIVO no `--green` da página, MUDO no `--orange`,
  e sem leitura o piloto REMOVE o atributo e o botão volta ao neutro. O `🎙` do
  segundo cartão perdeu um vermelho que estava **congelado** pelo gerador
  (`rgb(255,85,85)` → `rgb(68,71,90)`, igual ao do primeiro): a classe vinha do
  gerador e o glifo não tinha `data-campo`. Com os dois escritores fora,
  `.mudo-i.on` saiu da folha.

  **E as duas dicas pararam de mandar para uma janela que está saindo:** o `🎙`
  aponta para `hefesto-dualsense4unix mic release` e o `♪` para
  `speaker release`, dizendo que devolve **o controle**, não o valor. A frase
  banida *"janela do aplicativo"* saiu; *"linha de comando"* não entrou — o que
  a tela mostra é o nome do verbo, LIDO de `cmd_speaker._ACOES` e
  `cmd_mic._ACOES_FIRMWARE`.

  **Nenhum botão novo no cartão:** a decisão 02-Q6 dela (Liberar/Devolver ficam
  fora) segue intacta.

  **Quem escreveu esta atualização, e por quê:** o coordenador, na costura da
  ONDA A. O agente da `ONDA5-02-02` mediu que **este arquivo é `nao_toca` em
  quatro sprints e `posse` em nenhuma** — o portão do desenho ficava VERDE
  porque a seção `## 02-controles.html` existia, enquanto o corpo dela
  descrevia uma aba que deixou de existir. *Uma declaração de divergência que
  envelhece em silêncio é um portão verde sobre nada* — a oitava desta casa em
  quatro dias. **Este arquivo passa a ser posse declarada do coordenador na
  costura de cada onda.**

  **O que fecha:** o `--publicar 02` da próxima vez que ela aprovar a aba. Nada
  espera por isto — nenhuma sprint depende desta linha.

---


- **06/09/2026 — A LINHA DO GIROSCÓPIO ENTROU, E A DA VERDADE NÃO**
  (`CONTROLES-VERDADE-01`). O cabeçalho do card aberto ganhou o número que
  responde *"o giroscópio está chegando ao jogo AGORA?"* — `Giroscópio: fluindo
  para o jogo (~N Hz)`, do dono `controller_card.texto_motion`, com as duas
  exceções (Modo Nativo e máscara Xbox 360). O que ele substitui é um **número
  de catálogo**: a dica do interruptor de Giroscópio afirma *"No cabo são 250,0
  Hz exatos"* para todo controle e todo momento.

  **Ela mora no vão do cabeçalho, e custa ZERO altura.** Medido: 410 px de vazio
  entre a máscara e o par de sensores, e o card continua com os mesmos 348 px.
  Sem frase, o `title` some e a folha apaga o elemento. A conta do card tem 24 px
  de folga, e uma linha no corpo os teria gasto.

  **E O CABEÇALHO PASSOU A FALAR A LÍNGUA DA TELA:** `USB`/`BT` viraram
  **cabo**/**rádio**, do dono `home_actions.palavra_do_transporte`. Isso curou um
  defeito vivo que a costura da ONDA B abriu no mesmo dia — um controle sem cor
  lida (a mesa dela pelo rádio) lia `P2 • rádio • BT`, o transporte duas vezes em
  dois dialetos.

  **A LINHA DA VERDADE NÃO ENTROU, e é decisão dela:** ela saiu da tela da GTK em
  17/08/2026 (*"remover guia dos status em tempo real"*) e continua criada e
  alimentada fora da tela. Reconstruí-la aqui seria reintroduzir o que ela mandou
  tirar. Há régua que impede a volta.

  **O que ela vê HOJE, até publicar:** exatamente a aba de ontem. O campo novo
  não é sequer emitido — o `_so_se_a_pagina_tiver` pergunta ao publicado.

  **O que fecha:** o `--publicar 02` quando ela aprovar a aba.

## 03-gatilhos.html

- **06/09/2026 — O BOTÃO DE REENVIO SAIU DO DESENHO** (`ONDA5-03-02`, a decisão
  dela de 06/09, `D-0609-REENVIO-SAI`). O `↻` que morava na faixa de cada
  coluna, ao lado do "Guardar esse efeito", não é mais emitido pelo gerador. Com
  ele saíram as duas regras de CSS que o vestiam e o item da legenda que o
  explicava.

  **É uma REVERSÃO, e a reversão é dela.** O botão nasceu em 04/09 às 20:14 pela
  decisão [03] do PO; ela respondeu a `03-Q3` — *"a coluna GANHA um botão para
  mandar o efeito de novo?"* — com *"Nada novo"* **dezenove horas depois**,
  sobre um mundo em que ele ainda não existia. Perguntada de novo em 06/09, com
  o botão na tela e a foto ao lado, escolheu **"sai"**.

  **E A LEGENDA MUDOU JUNTO, pela `03-Q4`:** o item *"Quando o efeito chega, a
  tela diz … a confirmação nasce no próprio cartão"* descrevia a forma que ela
  trocou. Ele passou a contar a piscada — *"o campo pisca em verde … cerca de um
  segundo e meio"* —, e a caixa do cartão ficou nomeada como o que ela é hoje: o
  canal de quem tem **notícia**.

  **Por que não publiquei:** publicar é ato dela, e aqui a mudança é VISÍVEL —
  um botão a menos em cada uma das quatro colunas.

  **O QUE ELA VÊ HOJE, ATÉ PUBLICAR, e o custo NÃO é zero — é o ponto desta
  declaração.** A página publicada continua com o `↻` nas quatro colunas, e ele
  continua FUNCIONANDO: o gesto `reenviar` segue no pacote de propósito. Tirar o
  dono junto com o desenho daria a ela um botão MORTO — medido: um clique sem
  dono não recusa, não avisa e não muda a tela, só imprime `[gesto sem dono]` no
  stderr de quem lançou a janela (`hefesto_vivo._chamar_gesto`).

  **O que fecha, e são DOIS atos no mesmo momento:**

  1. `scripts/check_o_desenho_aprovado.py --publicar 03`, depois do OK dela;
  2. **no mesmo commit**, o gesto sai do pacote — a função `reenviar` e o
     `@gesto` dela, a entrada do `PROVAS`, `PISO_DA_ABA` de 5 para 4, as quatro
     réguas de gesto e as duas de página em
     `test_a_aba_03_gatilhos_fecha_as_linhas.py`, mais o `test_reenviar_nao_grava`
     e o `test_o_reenviar_nao_ganhou_frase_de_disco` em
     `test_o_gatilho_aplicado_vai_para_o_perfil.py`.

  **Quem impede que o passo 2 seja esquecido é uma régua, e não esta prosa:**
  `test_o_reenvio_sai_do_pacote_quando_sair_do_produto` exige que o botão na
  página publicada e o dono no pacote existam JUNTOS ou não existam. Ela fica
  VERMELHA no instante do `--publicar 03` e a mensagem dela lista o que apagar.

- **06/09/2026 — NASCEU O "EM TODOS", E ELE ESPERA A SUA PALAVRA**
  (`GATILHOS-EM-TODOS-01`, a linha 110 do CSV da paridade). Cada coluna ganhou um
  segundo botão na faixa de ação: **"Em todos"**. Ele põe o par L2+R2 daquela
  coluna nos controles todos e grava o efeito no perfil como o de **todo mundo**
  — e é essa gravação que faz um controle ligado DEPOIS já nascer com ele.

  **O DEFEITO QUE ELE FECHA, e ele é invisível até doer:** tudo o que esta tela
  gravava era por controle. Com dois na mesa, pôr o mesmo efeito nos dois criava
  DOIS ajustes separados no perfil e nenhuma opinião geral — e o terceiro
  controle, ligado depois, pegava o gatilho de ontem. Os dois primeiros estão
  certos, então não há como ela desconfiar de quê.

  **O "Guardar esse efeito" ENCURTOU PARA "Guardar", e a razão foi MEDIDA**, no
  Chrome a 1920x1080, com a página parada: com o texto longo os três não cabem —
  a faixa sangra 24px e o campo do nome cai para **16px** de largura, que é um
  campo que não se digita. Com "Guardar" a conta fecha na faixa de 202px:

      campo do nome  66px  ·  Guardar  58px  ·  Em todos  66px  ·  sangria ZERO

  Nada se perde: a frase inteira virou o `?` do botão. E o encurtamento é o
  mesmo que você pediu em 31/08 noutro botão — *"aonde tem Voltar ao automático
  deixa só Automático"*.

  **POR QUE NA COLUNA E NÃO NA FAIXA DO TÍTULO**, que é onde a Iluminação pôs o
  "Todos no automático" dela: a Iluminação espalha um ESTADO, que não tem
  origem; aqui o que se espalha é um EFEITO, e o efeito é o par de UMA coluna.
  Um botão lá em cima teria de escolher a coluna de origem sozinho, e escolher a
  do P1 seria a tela afirmando o que ninguém pediu. A faixa do título ficou
  medida e vaga (980px livres) para quem vier depois.

  **Por que não publiquei:** publicar é ato seu, e aqui a mudança é VISÍVEL em
  dois lugares — um botão a mais e um rótulo mais curto —, na mesma faixa de que
  você mandou tirar o reenvio ontem. É o caso exato da `PROVA-DE-TELA-01`.

  **O que você vê HOJE, até publicar, e o custo NÃO é zero:** a aba Gatilhos de
  ontem, sem o "Em todos". O mecanismo já está no produto (o gesto `em-todos`
  tem dono no pacote e régua própria), mas ninguém o alcança — a página
  publicada não tem o botão. Enquanto isso, pôr o mesmo efeito em dois controles
  continua criando dois ajustes separados, e o terceiro continua não pegando
  nada.

  **O que fecha:** o `--publicar 03` depois do OK seu.

## 04-iluminacao.html

- **06/09/2026 — LUZES-01.** A célula LEDs ganhou a botoeira das cinco luzes de
  jogador (clicáveis, uma a uma) e seis teclas de desenho — `P1`..`P4`, todas e
  nenhuma —, o indicador virou o botão de reenvio, e a faixa do título ganhou o
  "Todos no automático". **Esta sprint NÃO publica**: o `--publicar 04` continua
  sendo ato dela, e a leva inteira publica de uma vez, no fecho (decisão dela,
  06/09). Enquanto isso, o pacote emite o indicador de LEITURA que o publicado
  sabe desenhar — a guarda é `a04_iluminacao.a_folha_alcanca_a_botoeira()`, e
  ela responde `False` até a folha chegar à página publicada.

  **A densidade é o ponto de olho dela:** a botoeira ocupa 216 dos 220 px da
  célula. Se ela recusar, a saída medida é a faixa nova da grade, e ela custa
  uma rolagem ou a redução do desenho do controle.

  **O que fecha:** o `--publicar 04` depois do OK dela na aba inteira.

## 05-vibracao.html

- **06/09/2026** — **A NOTA DO TESTAR VOLTOU PARA O `?`** (`ONDA5-05-01`, a
  05-Q2 dela: *"As duas na dica."*). A frase *"Os valores acima ainda passam
  pela intensidade escolhida ali em cima…"* deixou de ser a linha cinza em
  itálico embaixo da grade e voltou para dentro do `?` do **Testar agora**, ao
  lado das duas orações do par. Saíram junto a `.vib-nota` do miolo e a regra
  de CSS que só ela usava.

  **E a dica passou a abrir para a DIREITA, o que é conserto de defeito
  medido:** ela carregava `left:auto;right:22px` — o arranjo das dicas do lado
  direito da página —, e neste `?`, que mora na primeira coluna da grade, isso
  punha **224 dos 330 px da caixa fora da janela**. Medido nos dois motores, a
  1920x1080: Chrome (`interface/olhar.py`) e WebKit (o piloto). Com o padrão da
  casa a caixa vai de x=505 a x=835 dentro de uma janela de 370 a 1550 —
  **sangria zero**.

  **O que ela vê HOJE, até publicar:** a aba Vibração de ontem — a linha cinza
  ainda embaixo da grade, e o `?` do Testar agora ainda cortado pela borda
  esquerda da janela. **O corte é do produto publicado, não desta mudança**:
  medido em `interface/paginas/05-vibracao.html`, a mesma sangria de 224 px já
  existia com as duas orações.

  **O que fecha:** o `--publicar 05` depois do OK dela na aba inteira.

- **06/09/2026** — **A CONFIRMAÇÃO SAIU DO CARTÃO E FOI PARA A FAIXA**
  (`ONDA5-05-03`, a 05-Q4 dela: *"Linha embaixo da grade (…) nomeando a coluna
  (`P2 · voltou ao ajuste geral`) e some logo depois; nada se mexe dentro das
  colunas"*). O `#vib-estado` passou a declarar `data-hef-recados="sucesso"` e
  `data-hef-recado-classe="est recibo"`, e a folha ganhou o quarto tom, o
  `recibo`, em `--green`. As três frases do clique encolheram para caber numa
  linha (331 → 134, 267 → 162) e ganharam o `P{n} ·` na frente; o mecanismo do
  `Auto` foi para o `?` do "Força da vibração", que passou de 190 para 262 px de
  altura com sangria zero nos quatro lados.

  **A METADE DO PILOTO ENTROU NA COSTURA** — `pintar_recados` conhece agora o
  TERCEIRO lugar, a faixa que a página declara. Medido pelo coordenador contra a
  bancada da 05, com o sucesso entrando pelo `_depositar`: o recado pousa em
  `#vib-estado` com a classe `hef-recado est recibo`, 16 px de uma linha, e o
  desenho do P1 fica parado em 230 px. Com o terceiro lugar arrancado ele volta
  para DENTRO da coluna, em `y=228` sobre um desenho que começa em 230.

  **O que ela vê HOJE, até publicar:** a aba Vibração de ontem — o aviso do
  clique nascendo dentro da coluna, tarja verde cobrindo o topo do desenho do
  controle por 6 s. Nenhuma das dez páginas publicadas declara
  `data-hef-recados`, então o piloto se comporta hoje como ontem.

  **O que fecha:** o `--publicar 05` depois do OK dela na aba inteira.
## 06-navegacao.html

> **ATENÇÃO — esta aba JÁ FOI PUBLICADA UMA VEZ hoje, e ela precisa saber
> disso.** O título desta seção é o nome do arquivo E NADA MAIS: o
> `check_o_desenho_aprovado.declaradas()` casa `^##\s+(\S+\.html)\s*$`, e
> o adorno que estava aqui fazia a seção NÃO contar como declaração — o
> portão não acusou enquanto a bancada e o publicado eram iguais, e
> acusou no primeiro dia em que deixaram de ser (06/09/2026).

- **06/09/2026** — a `ONDA5-06-02` **publicou** `interface/paginas/06-navegacao.html`.
  A aba passou a ter **22 linhas**: o **Botão PS** é a 19ª, e abre em *"Abrir a
  Steam"*, que é o `padrao()["ps"]` do motor.

  **Publicar é ato dela, e esta é a exceção do dia — declarada, não escondida.**
  A decisão de manter foi do coordenador, na costura da ONDA B, com três razões:

  1. **A sprint declarava a posse.** `interface/paginas/06-navegacao.html` está
     em `posse:` da `ONDA5-06-02`, enquanto as irmãs da mesma leva (`ONDA5-05-01`,
     `ONDA5-02-02`) a põem em `nao_toca:`. A diferença é do desenho da fila, não
     escolha do agente.
  2. **Desfazer criaria perda SILENCIOSA de trabalho dela**, que é o defeito que
     esta casa mais persegue: a tela ficaria com 21 linhas sobre um produto de
     22, e o «Guardar» **descartaria a escolha do PS sem dizer uma palavra**,
     porque a varredura não a traria.
  3. **O piloto renderiza o PUBLICADO.** Sem publicar não existe prova de tela —
     e ela é obrigatória —, e duas das sete réguas que a `ONDA5-06-01` deixou
     vermelhas leem a página publicada.

  **O que isso muda para ela, no FECHO:** a volta única de publicação continua
  acontecendo, e a aba 06 entra nela — só que **já publicada**. Se ela olhar a
  linha do PS e disser que não, o desfazer é um comando:
  `git checkout <commit> -- src/hefesto_dualsense4unix/interface/paginas/06-navegacao.html`.

- **06/09/2026 — E ELA VOLTOU A ESTAR ATRÁS, por desenho:** a
  `NAVEGACAO-TECLAS-01` acrescentou a tela **"Teclas do teclado"** à bancada e
  **não publicou** — `interface/paginas/06-navegacao.html` está no `nao_toca:`
  daquela sprint, e a leva publica de uma vez no fecho, com a palavra dela.

  **O que é a tela nova:** oito linhas com um **campo de texto** onde ela
  escreve a tecla que o botão digita — `Alt + Tab`, `Ctrl + Shift + F`, `F5`,
  **qualquer combinação**, e não uma opção nova na lista de 26. É a linha
  `FALTA_NO_HTML` de *Editar QUAL TECLA cada botão digita*
  (`docs/data/paridade-gtk-html.csv:208`), que era a maior perda de alcance
  desta aba na migração. Cada linha tem um **↺** que devolve **só ela** ao de
  fábrica — até hoje voltar uma linha custava o "Voltar ao padrão" da tela
  inteira, que zera `key_bindings` e `button_actions` de uma vez.

  **São oito e não vinte e duas porque o domínio é do produto:**
  `acoes_de_botao.DOMINIO_DO_TECLADO` (`create`, `l1`, `l3`, `options`, `r1` e
  as três regiões do touchpad). Nos outros catorze o que manda é o mapa fixo do
  `UinputMouseDevice`, e oferecer campo ali gravaria no disco uma escolha que o
  `resolver()` não lê.

  **O que ela vê HOJE, até publicar:** a aba Navegação sem o botão
  *"Teclas do teclado"* no rodapé da tela de Definições, e portanto **sem
  nenhum caminho** para escrever uma tecla livre — o mesmo estado de ontem. O
  **custo da espera é o da linha do CSV**: o que ela escreveu na janela antiga
  continua sem ter como ser reescrito pela tela nova.

  **O que NÃO espera pela publicação, e já vale no produto de hoje:** o
  `guardar-definicoes` deixou de apagar `key_bindings` fora do alcance dele, a
  tabela das 22 linhas passou a mostrar as TRÊS camadas (antes ignorava
  `key_bindings`, e mostrava o de fábrica sobre um botão que digitava outra
  coisa), e a tira sob a tabela deixou de nomear como perdidos os oito atalhos
  que a `ONDA3-MOTOR-01` fez sobreviver.

  **O que fecha:** `scripts/check_o_desenho_aprovado.py --publicar 06`, no OK
  dela da aba.

## 08-conexoes.html

- **06/09/2026** — a 08-Q5 e a 08-Q7 (`ONDA5-08-01`). O desenho ganhou a linha
  do exame que fica **em cinza** quando ela manda ignorar, o `title` do ⊘ que
  troca de verbo, e as duas linhas de `+N` (exame e rádios vizinhos).

  **O que ela vê HOJE, enquanto não publicar:** a aba Conexões de ontem, com uma
  diferença medida — o ⊘ grava e desfaz no disco, e a LINHA não muda de cor,
  porque a página publicada não tem o endereço `exame-calada`. O veredito do
  topo continua respondendo.

  **O que fecha:** `--publicar 08`, que é ato dela — e nesta leva isso acontece
  numa volta só, no FECHO (decisão dela, 06/09).

  **Escrito pelo coordenador**, na costura da ONDA A: este arquivo é posse do
  coordenador desde 06/09, e a sprint que produziu a divergência não podia
  declará-la. O texto é o que o agente da `ONDA5-08-01` deixou pronto no
  relatório dele.

- **06/09/2026** — as linhas 4, 5, 8, 14 e 15 do balde `LIGAR`
  (`CONEXOES-LIGAR-TUDO-01`). O desenho ganhou **cinco endereços**: os
  `data-campo="alvo-aberto"` nos cinco rádios do acordeão (que fazem a linha
  aberta e o chip da fita seguirem o alvo de saída do serviço) e quatro linhas de
  ressalva — o controle que o sistema não entregou, o rádio nativo frágil, o hub
  em comum e as contagens do gabinete.

  **Nenhuma delas ocupa um pixel em repouso**: as quatro são `monta.ressalva`, e
  a folha as apaga quando não há o que dizer. Medido no WebKit: a página tem
  **809 px** com as quatro caladas e **809 px** com as quatro falando.

  **O que ela vê HOJE, enquanto não publicar:** a Conexões de ontem. Os cinco
  rádios do acordeão da página publicada não têm endereço — medido —, então a
  linha aberta e o chip da fita continuam onde o desenho os pôs, e não onde o
  serviço está mirando. Os quatro avisos não têm onde aparecer. **O serviço
  responde certo; a tela é que não pergunta.**

  **E DUAS VIOLAÇÕES DE GLOSSÁRIO SAÍRAM DA BANCADA NO CAMINHO** — `"hoje no
  USB"` e `"• BT — 260,4"` na régua de Desempenho. São as duas únicas linhas de
  texto do diff do `mockup/` nesta frente.

  **O que fecha:** o `--publicar 08`, que é ato dela.

## 09-sistema.html

- **06/09/2026** — **DOIS BOTÕES NOVOS, e um deles NASCE ESCONDIDO**
  (`SISTEMA-OS-QUATRO-QUE-FALTAM-01`, as linhas 315 e 340 do CSV da paridade).

  1. **"Corrigir modo de execução"**, na coluna do serviço. Ele é a saída que
     faltava: a aba já RECONHECE o modo improvisado desde 03/09 — a linha "O
     serviço está" escreve *"Ligado, em modo improvisado"* em laranja — e não
     oferecia conserto nenhum. **Ele nasce com `display:none`** e só acende
     quando o produto diz que há modo a corrigir (`data-campo`
     `corrigir-modo-quando`, alvo `classe`), e quando acende **entra no LUGAR
     do «Reiniciar o serviço»**, não ao lado dele;
  2. **"Aplicar aos jogos da Steam"**, na coluna dos gestos raros (Avançado),
     ao lado do "Restaurar de fábrica". É a metade que APLICA o que o «Copiar
     a linha» da aba Lançadores só entrega na área de transferência, e mora
     nesta aba por decisão dela (`D-0609-STEAM-DIVIDIDO`).

  **A TROCA COM O «Reiniciar» é de ALTURA e de VERDADE, e as duas metades
  foram medidas no WebKit:**

  ```
  os dois na tela ao mesmo tempo ... a coluna vai a 194px (o irmão tem 156)
                                     e o miolo ROLA 38px por dentro
  a troca (`.so-avulso.mostra + .acao{display:none}`) ... rola 0px
  ```

  E no modo improvisado o «Reiniciar o serviço» é justamente o clique que **não
  funciona**: `systemctl restart` sobe a unit, a unit encontra o Hefesto avulso
  segurando a instância única e não sobe (é o terceiro portão de
  `ativar_o_servico`, a BUG-MULTI-INSTANCE-01) — e `travas()` não o tranca
  nesse estado. Pôr um no lugar do outro é trocar o clique que falha pelo que
  conserta. É o irmão CSS das duas caras que o botão «Parar o serviço»/«Ativar
  o serviço» já tem por decisão dela de 03/09.

  **O PREÇO DO QUARTO BOTÃO DOS GESTOS RAROS, medido e pago em pixel:** a
  coluna passou a empilhar sem vão entre os botões (`gap:0`, a MESMA gramática
  que `.exame .col-acao` já usa nesta página) e o vão ENTRE as faixas caiu de
  10 para 8px. **Nenhum bloco encolheu e nenhum texto mudou de tamanho.** A
  página fecha em **530px de conteúdo para 530px de espaço útil**, sem rolar —
  e o par `MIOLO_H, ALTURA` do gerador, que dizia `544, 542`, foi **remedido**:
  o miolo tem 564 e o conteúdo tinha 508.

  **Por que não publiquei:** publicar é ato dela, e aqui nasce **um botão que
  ela nunca viu** e uma troca de lugar entre dois. A `PROVA-DE-TELA-01` vale
  exatamente para isto — quem confere que a tela ficou certa é ela, olhando.

  **O que ela vê HOJE, até publicar:** a aba Sistema de ontem, inteira. Os dois
  botões não existem na página publicada, e o `corrigir-modo-quando` que o
  pacote emite a cada tique cai no vazio lá — está declarado em
  `a09_sistema.ESPERA_A_PUBLICACAO`, com a régua que cobra a declaração nos
  dois sentidos. **Nada regride enquanto ela espera:** quem cair no modo
  improvisado continua vendo o aviso que a aba já dá; só não ganha ainda o
  botão que o conserta.

  **O que fecha:** o mesmo `--publicar 09` das duas linhas abaixo. As três
  divergências desta aba fecham no mesmo ato.

- **06/09/2026** — **DUAS LINHAS DO PERFIL DE BATERIA DEIXARAM DE SER
  LITERAL** (`SISTEMA-STEAM-01`). *"O teto alcança"* e *"Ainda sem teto"*
  ganharam `data-campo` e passam a ser lidas do dono
  (`secao_orcamento.LINHAS_DO_TETO`) a cada tique. Até hoje elas eram derivadas
  no instante em que alguém rodava o gerador e ficavam **cravadas no HTML**: no
  dia em que os "Gatilhos" ganharem ponto de aplicação no daemon, a tela dela
  continuaria dizendo que o teto não os alcança.

  **NENHUM PIXEL MUDA, e é medida, não promessa.** O que entrou são quatro
  atributos — `data-campo` e o `-g` do glifo nas duas linhas —, e `data-campo`
  está nos INVISÍVEIS do `check_o_desenho_aprovado.py`, que compara **o que se
  vê** (decisão dela em 01/09: *"ok, pode comparar então o que se vê"*). O
  texto que a bancada mostra hoje é byte a byte o de ontem, porque
  `LINHAS_DO_TETO` não mudou de valor.

  **O que ela vê HOJE, até publicar:** o valor congelado do desenho. Ele está
  CERTO hoje, e é por isso que esta divergência não urge — o custo dela é
  futuro, e chega calado no dia em que o produto mudar.

  **O que fecha:** o mesmo `--publicar 09` da linha abaixo. As duas divergências
  desta aba fecham no mesmo ato.

- **06/09/2026** — **UMA LINHA, e os dois pixels que ela mudam são PALAVRA
  DELA** (`ONDA5-09-01`, a 09-Q1 e a 09-Q3). O botão do `daemon.reload` volta a
  se chamar **"Atualizar"** e a espera a dizer **"Atualizando…"**; a dica dele
  passa a nomear o que foi MEDIDO do outro lado do clique, e não o que se
  supunha.

  ```
  linha 1245 · bancada  Atualizar          · data-hef-em-voo="Atualizando…"
  linha 1245 · produto  Reaplicar ajustes  · data-hef-em-voo="Reaplicando…"
  ```

  **É uma REVERSÃO, e a reversão é dela.** Em 04/09 o PO decidiu rebatizar o
  botão pela metade cara; em 05/09 ela leu a mesma pergunta e escolheu o
  contrário: *"Segue fazendo os dois. Com mesmo nome"*. O que estava no produto
  desde `a45b7799` é a recomendação que perdeu.

  **A dica mudou de metade, e por medição:** ela prometia *"reaplicar a
  configuração"*, e com `config_overrides` vazio isso **não acontece** —
  `daemon/lifecycle.py:1353` e `:1361` comparam `old` com `new` e nunca
  disparam. O que acontece são duas coisas: o serviço religa o leitor dos
  atalhos do controle (`lifecycle.py:1351-1352`) e reescreve os arquivos de
  ambiente da Steam (`ipc_handlers.py:5472`). A dica passou a dizer essas duas.

  **Por que não publiquei:** publicar é ato dela, e aqui a mudança é VISÍVEL —
  duas palavras que ela lê no botão. A `PROVA-DE-TELA-01` é a regra mais velha
  desta casa, e ela vale exatamente para o caso em que a mudança é a palavra
  dela: quem confere que a palavra chegou certa é ela, olhando.

  **O que ela vê HOJE, até publicar:** a aba Sistema de ontem, com o botão
  ainda dizendo "Reaplicar ajustes". Nada quebra — os quatro botões da coluna,
  os três cinzas e o `data-hef-em-voo` continuam inteiros nos dois lados.

  **O que fecha:** `scripts/check_o_desenho_aprovado.py --publicar 09`, depois
  do olho dela.
