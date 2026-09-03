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

## 01-jogar.html
- **03/09/2026** — a aba passou a LER o que mostrava sozinha: a posição do
  interruptor (`painel.hefesto_ligado`), o chip aceso da fileira
  (`painel.modo_vivo` + `home_actions.mascara_do_aparelho`), a máscara acesa nos
  cartões e a coluna **Atenção** inteira (`painel.avisos_do_estado`, as seis
  fontes puras da GTK, mais o opt-out antigo). O que mudou no desenho é
  ENDEREÇO e CSS de estado — a cena continua a que ela aprovou: um aviso na
  coluna, `Ligado` marcado, `Sony DualSense` aceso, a faixa laranja com a
  frase. As cinco linhas novas da coluna nascem apagadas e só existem para o
  produto ter onde escrever quando a máquina dela tiver mais de um aviso.
  **O QUE ELA VÊ HOJE, enquanto o produto não recebe** — fotografado em
  03/09 com os dois controles na mesa e o daemon em `desktop`: a página
  publicada tem os endereços de TEXTO (a coluna Atenção já mostra o aviso
  do cadeado cego e a conta certa, porque `aviso-selo`, `aviso-texto` e
  `atencao-conta` já existiam lá), e **não** tem os de ESTADO. Então
  continuam na tela dela, até publicar: o chip **Sony DualSense** aceso com
  o modo vivo em Navegação, o chip **Xbox 360** aceso no cartão do P2 com o
  daemon em `flavor=dualsense`, o segundo aviso sem linha onde caber, e a
  faixa laranja com um travessão solto quando não há pendência. Medido: 12
  valores pintados com a página publicada contra 29 com a da bancada.
  **O produto recebe no `--publicar 01`**, que é ato de quem coordena.
## 02-controles.html
- **03/09/2026** — a LEITURA VIVA do card ganhou endereço, e duas coisas que
  chegam aos olhos mudaram junto. Nenhuma delas é desenho novo.

  **1. A barrinha de cada eixo virou DUAS METADES.** Ela era um `<span
  class="v" style="left:L%;width:W%;background:C">`, e os três valores mudam a
  cada leitura: o `escrever` do piloto sabe escrever largura e cor, e **não tem
  alvo de POSIÇÃO** — com um elemento só, a barra de um eixo negativo cresceria
  para o lado errado. Agora são `.v.neg` (ancorada em `right:50%`) e `.v.pos`
  (em `left:50%`), e a cor sobe para o trilho por `currentColor`.
  **Os pixels são os mesmos, e isto está medido**, não afirmado: as duas
  páginas abertas no Chrome, `getBoundingClientRect` nas doze barras visíveis —
  **10 das 12 idênticas na esquerda, na largura e na cor**, e as outras duas
  diferem em **0,02 px** (arredondamento de sub-pixel entre `left:12%` e
  `right:50%`).

  **2. `X:  60` virou `X: 60`** — um espaço a menos por eixo, nos quatro
  analógicos. A frase passou a sair de `controller_card._markup_xy`, que é o
  dono dela na GTK, em vez de uma segunda cópia digitada no gerador. É a LEI 0:
  *"no gtk eu já deixei praticamente tudo pronto (…) Não temos que recriar
  nada."*

  **O QUE O PRODUTO FAZ ENQUANTO ESPERA O OK DELA, e é medido:** o pacote
  pergunta à página **publicada** quais endereços ela tem
  (`_so_se_a_pagina_tiver`) e **só emite esses**. Medido nesta árvore com os
  dois controles dela na mesa: `leitura_viva` calcula **46 campos por card** e
  o pacote emite **15** — os 46 ficam de fora, e nenhum deles chega ao
  `casamento.medir` como órfão. **A tela dela não muda nada até o
  `--publicar 02`**: os dezesseis glifos, os dois gatilhos, os seis eixos e os
  dois pares X/Y continuam mostrando o desenho, exatamente como hoje. No
  minuto em que ela publicar, os 46 passam a ser pintados sem uma linha de
  código a mais.

  **O que espera a sua palavra:** o giroscópio e o acelerômetro do desenho usam
  **quatro cores** (ciano, verde, laranja, cinza) e a leitura viva usa **três**
  (`mesa_viva._barra_bipolar`: verde para positivo, vermelho para negativo,
  cinza para o repouso). Quando o produto pintar, o ciano e o laranja somem.
- **03/09/2026 · a cor do plástico virou UMA folha, e nenhum pixel do desenho
  mudou.** As duas folhas do fim do `<head>` — a do desenho e a vazia por cima —
  viraram **uma**, endereçada e com `data-hef-alvo="html"`, que o produto troca
  INTEIRA. Ela nasce com as suas duas cores (Cosmic Red no P1, Starlight Blue no
  P2), então **a bancada continua exatamente a cena que você aprovou**.

  **O buraco que isso fecha só aparece com MENOS controles na mesa do que o
  desenho tem**, e está medido no WebKit desta máquina: com duas folhas e um
  controle só ligado (o White no cabo), o assento do P2 continuava com a borda
  `rgb(126, 184, 212)` — **Starlight Blue num lugar onde não há controle
  nenhum**. Agora ele cai no cinza neutro, que é a sua regra: campo sem
  informação não mostra nada.

  **O que você vê hoje, sem publicar:** nada mudou. Com os seus DOIS controles
  na mesa o produto já nomeia os dois assentos, e a tela sai igual — fotografada
  com o daemon vivo: P1 com a borda branca do White, P2 com a roxa do Galactic
  Purple. A diferença nasce no dia em que você desligar um deles.
## 03-gatilhos.html
- **03/09/2026 · A COLUNA MORTA PASSA A PARECER MORTA** — só CSS, e ele pende do
  `data-conectado` que o piloto já reescreve a cada tique.

  **O defeito, medido nos pixels da foto do produto** com a mesa dela (dois
  controles, P3 e P4 vazios):

  ```
  o texto de "Guardar esse efeito"   P1 e P2  rgb(186,145,246)
                                     P3 e P4  rgb(186,145,246)
  a borda da caixa "Modo"            P1       rgb(189,147,249)
                                     P3 e P4  rgb(189,147,249)
  ```

  **Quatro botões byte a byte iguais, e dois deles mortos.** A trava de 02/09
  parou no `pointer-events:none`, que é INVISÍVEL — o comentário dela já dizia a
  lei (*"um botão que convida para uma recusa é pior que um botão que não
  existe"*) e curou só o rato. Para quem usa este produto é o pior arranjo que
  existe: o botão não responde nunca e não diz isso em lugar nenhum.

  **A gramática é a das outras abas**, e nada aqui é invenção: texto em
  `var(--linha)`, contorno em `var(--border-forte)`, fundo do quadro, **sem
  `opacity`** (a lição medida da `.fita.inerte`). É o que `.nav-ctl.vazia` (06),
  `.luz-grade .ctrl.vazia` (04) e a coluna vazia da 05 já fazem.

  Medido nas duas páginas, com o Chrome:

  | página | P1/P2 (na mesa) | P3/P4 (desconectados) |
  | --- | --- | --- |
  | publicada | `rgb(189,147,249)` | `rgb(189,147,249)` — igual |
  | bancada | `rgb(189,147,249)` | `rgb(83,87,111)` — apagado |

  **ESPERA O `--publicar 03`**: a cura mora na FOLHA, e a página publicada não a
  tem. Até lá as quatro colunas continuam idênticas na tela dela — as duas
  travas que já existem (o `pointer-events` e o `_exigir_controle` do Python)
  seguem valendo, e o clique continua não fazendo nada.
## 04-iluminacao.html
- **03/09/2026** — **DUAS LINHAS DE CSS, e zero pixel a mais no que ela
  aprovou.** O desenho ganhou `.players .dono.incerta` e
  `.troca-item .dono.incerta` — o anel TRACEJADO, que é a decisão 9 dela
  (*"tracejado para 'não sei'; lisa e vazia para 'apagada'"*) aplicada ao
  vizinho de cima da tira da luz.

  **O defeito que elas fecham, provado antes de curado:** um número da linha
  **Jogador** que está TOMADO por um controle cuja cor de plástico ainda não
  chegou saía **byte a byte igual** a um número LIVRE — a ressalva viajava só
  no `title`, e quem navega pelo controle nunca passa o mouse. Acontece no
  primeiro tique de toda sessão (a cor vem do broker em thread) e **para
  sempre** num colorway que o SVG não conhece. A prova está em
  `a04_iluminacao.ANEL_INCERTO`.

  **A tela do mockup não muda**: os dois controles da bancada têm cor
  conhecida, então nenhum elemento desta página carrega a classe nova. As duas
  regras são a folha alcançando o que o pacote já escreve.

  **O QUE ELA JÁ TEM SEM PUBLICAR, e é a cura inteira:** o anel do "não sei"
  sai com `style="border:2px dashed var(--comment)"` escrito na linha pelo
  pacote — é o mesmo piso que `TIRA_APAGADA` pagou na foto, e ele vence a folha
  publicada de hoje (`border:2px solid var(--plastico)`, que sem a variável fica
  inválida e apaga o anel). **O `--publicar 04` só acrescenta a regra da
  folha**, para quem ler o CSS achar o estado escrito onde os outros dois moram.
- **03/09/2026 · O DESENHO GRANDE PASSA A SER O CONTROLE DELA** — um
  `<style id="plastico-vivo">` vazio, e é a maior identidade congelada que
  sobrava nesta aba. A lei é dela, do mesmo dia: *"se no topo tá mostrando
  controle white player 1, então cada aba vai usar os controles lá de cima.
  **Não mistura com a info dos mockups.**"* <!-- noqa-acento: citação literal dela -->

  **A cura de hoje tinha parado na MOLDURA.** Medido nos pixels da foto do
  produto, com os dois controles na mesa:

  | célula | moldura (viva, curada hoje) | corpo desenhado dentro dela |
  | --- | --- | --- |
  | P1 · **White** | `rgb(228,224,216)` = White ✓ | `rgb(174,51,90)` = **Cosmic Red** |
  | P2 · **Galactic Purple** | `rgb(116,88,142)` = G. Purple ✓ | `rgb(126,184,212)` = **Starlight Blue** |

  A borda certa em volta do controle errado, na MESMA célula, com o rótulo certo
  logo abaixo. E a aba **Navegação** desenha os MESMOS dois controles nas cores
  certas no mesmo instante (`rgb(212,209,202)` e `rgb(108,82,132)`) — duas abas,
  duas cores para o mesmo aparelho.

  **O dono é o que a 06 já tem:** `a06_navegacao.folha_do_plastico` ganhou o
  parâmetro `caixa` (`.nav-ctl` lá, `.ctrl` aqui) em vez de uma segunda cópia,
  que divergiria no primeiro modelo novo. Medido no Chrome, com a mesa dela
  injetada no `#plastico-vivo` da bancada:

  ```
         antes (o mockup)   depois (a mesa dela)
  p1     #ae335a            #e4e0d8   (White)
  p2     #7eb8d4            #74588e   (Galactic Purple)
  MORDIDA — antes != depois nos dois? True
  ```

  **ESTA CURA ESPERA O `--publicar 04`**: o `<style>` é um ELEMENTO novo, e
  elemento não está em `check_o_desenho_aprovado.INVISIVEIS`. Até lá o
  `document.querySelector('#plastico-vivo')` devolve `null` na página publicada
  e o laço do `blocos` não escreve nada — calado e correto, como o rodapé da
  troca já faz.
## 05-vibracao.html
- **03/09/2026** — o desenho ganhou DUAS coisas que a página publicada ainda não
  tem, e nenhuma muda um pixel do que ela aprovou:
  1. **endereço para o punho que treme** — `data-campo="treme-e"`/`"treme-d"`
     nos dois grupos de motor do SVG, com `data-hef-classe="acesa"`;
  2. **as três frases da janela estável** que a aba nova não tinha, lidas do
     `gui/main.glade` e não redigitadas: o teto da mesa (dos quatro tooltips de
     degrau), os 5 segundos do Modo Auto e a nota *"os valores acima ainda
     passam pela intensidade escolhida ali em cima"*.
- **03/09/2026 · O QUE ELA VÊ HOJE, com a página publicada de agora**, medido
  com a mesa dela (um DualSense no cabo, um por rádio):
  - **o número da força já está certo sem publicar**, porque a cura é do PACOTE:
    a barra "Personalizado" mostra `100%` com o degrau em "Balanceado", e não os
    `70%` presos de antes. Fotografado nas duas páginas, com o mesmo daemon;
  - **o que fica para trás são TRÊS pinturas**: 22 valores na bancada contra 19
    na publicada, e as três são os punhos que continuam acesos da CENA do
    mockup — o motor direito do P1 e os dois do P2 — com a mesa parada e
    `vpads == 0`. O `achar()` devolve zero elementos para `treme-e`/`treme-d`
    na página publicada: **não há erro de JS, nem clique morto, nem texto
    vazando** — só o punho que não apaga. As três frases novas também não
    aparecem nas dicas até lá;
  - o resto da aba continua idêntico: mesmos degraus, mesmos dois botões, mesma
    linha de estado.
- **03/09/2026 · o que ESPERA a palavra dela**: no degrau **Auto** a barra passa
  a dizer `100%`, que é o teto dele e o mesmo número da janela estável. A cena do
  mockup ensina `70%` no P3 (*"porque a bateria dele está no meio"*), e esse
  valor vivo exige um campo que o daemon não publica com honestidade:
  `rumble_mult_applied` ficou em `0.7` nos QUATRO degraus clicados em 03/09, com
  a política mudando a cada clique.
- **03/09/2026 · O MARCADOR DO TOM `diz` DEIXOU DE SER VERDE** — uma linha de
  CSS a menos, e é defeito de significado. Fotografado na tela dela com a mesa
  parada, duas linhas coladas:

  ```
  ● (verde)   não há gamepad virtual — nenhum jogo tem onde pedir vibração
  ▲ (laranja) A intensidade não está chegando a jogo nenhum: falta o gamepad…
  ```

  O MESMO fato, com marcadores de sentido oposto — e nesta casa o verde quer
  dizer CERTO em todas as abas (`● 2 controles` do cabeçalho, `CERTO` da
  Conexões, `✓ OK` da Sistema, `Ligado` da Navegação, `CHEGAM` da Lançadores).
  O tom `diz` **não pode carregar valor**: pela mesma função
  (`rumble_actions.texto_dos_pedidos_de_vibracao`) saem *"o jogo pediu vibração
  12x"*, *"pediu força zero em todas"* e *"não há gamepad virtual"*. A regra que
  fica é a dos outros dois tons — o marcador tem a cor do texto dele —, e o
  contrato de `app/telas/vibracao.DIZ` já dizia isso desde 02/09 (*"a cor normal
  do rótulo"*).

  **Medido nas duas páginas**, com as duas linhas da mesa dela injetadas no
  `#vib-estado`:

  | página | marcador do `diz` | texto do `diz` |
  | --- | --- | --- |
  | publicada | `rgb(80,250,123)` — verde | `rgb(200,204,218)` |
  | bancada | `rgb(200,204,218)` | `rgb(200,204,218)` |

  **ESTA CURA NÃO CHEGA A ELA SEM PUBLICAR**, e é a diferença para a da aba 04:
  a cor mora na FOLHA, e o pacote não escreve estilo de linha aqui de propósito
  (*"viaja o NOME, e a cor mora no CSS da aba"*). Até o `--publicar 05`, a
  bolinha verde continua na frente da má notícia.
## 06-navegacao.html
- **03/09/2026** — a aba ganhou **as três leituras vivas que a GTK tem e ela
  não**, e todas as frases são do produto (nada foi escrito aqui):
  - o **"Status do Modo"** perdeu o `<input type="checkbox" checked>` e a
    palavra de `content:` de CSS. Ele nasce em `—` e passa a ser pintado pelo
    daemon (classe `ligado` + nó de texto). **Era a maior mentira desta aba:**
    a tela dizia *Ligado* com `mouse_emulation.enabled=false`, e clicar virava
    a caixa no DOM mesmo quando o gesto RECUSAVA;
  - **três linhas de estado** sob as opções de ativação, na mesma fileira: *por
    que o cursor não anda* (`mouse_actions`), *o teclado está ligado e calado?*
    (`emulation_actions.descrever_teclado_emulado`) e *há teclado na tela nesta
    máquina?* (`input_actions.frase_do_teclado_na_tela`). A dica do quadro
    Navegação já citava "a linha de estado abaixo" desde 27/08, para uma linha
    que não existia. Cada uma some quando não há o que dizer.

  **O que ela vê de diferente depois de publicar:** o interruptor pode passar a
  dizer *Desligado* (é o que o Hefesto dela responder), e nascem uma ou duas
  frases curtas entre as opções de ativação e a fileira dos botões. Nada mais
  mudou de lugar — medido na foto: a fileira dos botões continua dentro da
  janela.

  **O QUE O PRODUTO FAZ ATÉ ELA PUBLICAR, e é nada — de propósito:** a página
  que o `WebView` renderiza hoje não tem os quatro endereços novos, e o
  `escrever()` do piloto não acha elemento nenhum para eles. Logo **a tela dela
  hoje continua exatamente como estava**, inclusive dizendo *Ligado* sempre —
  a mentira só morre na publicação. Nenhum clique muda de comportamento por
  causa disso: o desenho velho não tem `data-campo` novo, e valor emitido sem
  destino é descartado sem erro. **O que JÁ chega a ela sem publicar** são as
  duas curas que vivem só no Python: a recusa do daemon passa a dizer o motivo
  no cartão (antes voltava como sucesso), e o segundo clique no `−`/`+` das
  velocidades dentro do mesmo tique passa a andar.

## 08-conexoes.html
- **03/09/2026** — `MIGRA-08-01`. **NÃO HÁ DESENHO NOVO AQUI: são DEZ endereços
  de pintura em elementos que já existiam**, e nenhum move um pixel. O
  `so_mudou_endereco()` deste portão confirma: apagados os trinta atributos que
  ele conhece, a única diferença que sobra são os seis `data-hef-quando` dos
  botões da sala — e `data-hef-quando` **não está na lista `INVISIVEIS`**, que é
  defeito do portão, não da página (a `08-conexoes.html` PUBLICADA já usa esse
  atributo, nas cinco pílulas do Check-up).

  Os dez: `ordem` (a coluna da ordem de serviço), `conta-gestao` (a contagem da
  seção), `sala-altura` e `sala-visada` (três botões cada) e `bateria` (um por
  controle). Sem eles o pacote emite e o `achar()` do piloto escreve ZERO,
  calado — a tela dela continua mostrando *"Mova o adaptador Bluetooth da
  Entrada 3 para a Entrada 9"*, que é o desenho apresentado como diagnóstico da
  máquina dela.

  **O caminho barato é `--publicar-enderecos 08`**, e ele só passa a existir
  quando alguém puser `data-hef-quando` (e `data-hef-classe`) na `INVISIVEIS`
  do `scripts/check_o_desenho_aprovado.py` — arquivo de outro dono. Enquanto
  isso, quem integra decide entre fazer aquilo ou `--publicar 08`.
## 10-perfis.html

- **03/09/2026** — **a TIRA DO DESFECHO**, uma linha nova sob o cabeçalho do
  quadro: o que aconteceu depois do último clique. É paridade com a janela
  estável, onde **todo** gesto desta aba termina num toast no rodapé
  (`profiles_actions._toast_profile`) — "Perfil removido: X",
  "Lista recarregada", `mensagem_de_ativacao`.

  **O QUE MUDA NA TELA, e é só isto:** uma faixa de 15px (mais 7px de vão) entre
  o cabeçalho `Perfis` e o corpo. Ela nasce **invisível** e reserva o espaço
  (`visibility`, não `display`), para a lista de 33 perfis não pular a cada
  clique. O espaço sai da altura da lista, que é quem estica.

  **O QUE ELA VÊ HOJE, sem publicar:** nada muda — a página publicada não tem a
  tira, e o valor emitido cai no vazio (declarado em
  `a10_perfis.SEM_ENDERECO`). **Enquanto** ela não aprova, os nove gestos desta
  aba que gravam no disco continuam mudos no sucesso: ela renomeia um perfil, o
  campo volta ao normal e nada diz que gravou. A recusa continua falando pela
  tarja do piloto, que já existe e não depende desta tira.

  **O que NÃO espera por ela** (já está no produto, sem tocar no desenho): o
  "Recarregar" deixou de ser botão morto, o "Novo" nasce com prioridade acima
  dos que valem sempre, a cópia do "Duplicar" não herda mais o carimbo de ponte,
  o "Ativar" lê o relatório de seções do daemon e pega a carona do wrapper, e
  trocar "Funciona em" para "Todos" num perfil de jogo pergunta antes.

## 01-jogar.html
- **03/09/2026** — **o DESENHO do controle passou a vestir o aparelho.** Era a
  queixa dela, com todas as letras: *"é white no p1, mas a borda de tudo é
  cosmic red e os svgs não são os que o meu mapa cataloga. isso tá errado"*.
  Fotografado no pixel, com os dois controles na mesa: o cartão dizia
  `White · USB` sobre um DualSense **Cosmic Red** (`#ae335a`), e
  `Galactic Purple · BT` sobre um **Starlight Blue** (`#7eb8d4`).

  **O QUE MUDOU NO DESENHO, e não é cena nova:** os quatro `<svg>` ganharam
  endereço (`data-campo="desenho"`, alvo `atributo`), e a folha das cores saiu
  de dentro deles para a página, uma vez, com os **28 modelos** do
  `docs/data/cores-do-dualsense.csv`. Aberta sozinha, a bancada mostra
  exatamente os mesmos quatro controles de antes — a folha compartilhada
  reproduz o que as quatro podadas já diziam. O arquivo cresceu 37 KB, que é o
  preço de uma tabela em vez de quatro escolhas.

  **O QUE ELA VÊ HOJE, enquanto o produto não recebe:** a página publicada
  continua com a folha PODADA dentro de cada desenho — cada SVG só conhece o
  próprio modelo. Então, até publicar, o controle desenhado no cartão continua
  Cosmic Red no P1 e Starlight Blue no P2, discordando do rótulo quatro pixels
  ao lado; e um Nova Pink, um Midnight Black ou qualquer um dos outros 24
  modelos dela não teria como aparecer. Medido no WebKit desta máquina: com a
  folha podada, **24 dos 28 modelos caem no cinza cru** (`rgb(58, 63, 75)`);
  com a da bancada, os 28 vestem a cor que ela mapeou.

  **O produto recebe no `--publicar 01`**, que é ato de quem coordena.
## 04-iluminacao.html

- **03/09/2026** — **o DESENHO DO CONTROLE passou a vestir o aparelho**, e com
  ele a página inteira aprendeu os **vinte e oito modelos** do mapa dela em vez
  dos quatro do desenho. É a lei dela deste dia:

  > *"os svgs do dualsense, as bordas das fitas das áreas, as escolhas dos
  > players com cada controle — tudo isso muda de acordo com o controle
  > identificado no canto superior. é white no p1, mas a borda de tudo é cosmic
  > red e os svgs não são os que o meu mapa cataloga. isso tá errado"*
  <!-- noqa-acento: citação literal dela -->

  **O DEFEITO ESTAVA FOTOGRAFADO nesta árvore**, com a mesa dela — um White no
  cabo e um Galactic Purple no rádio. A moldura e a fileira de números já
  vestiam o aparelho; dentro delas, o maior objeto da tela continuava do mockup:

  | | o que a coluna dizia | o que ela desenhava |
  | --- | --- | --- |
  | P1 | `P1 • White • USB` | um DualSense **cosmic-red** |
  | P2 | `P2 • Galactic Purple • BT` | um DualSense **starlight-blue** |

  **O QUE MUDA NO DESENHO**, e é só andaime — a cena que ela aprovou fica
  idêntica byte a byte enquanto a mesa for a do mockup:

  1. os dois `<svg>` das colunas conectadas ganham
     `data-campo="desenho" data-hef-alvo="atributo" data-hef-atributo="data-colorway"`;
  2. as **cores do mapa** (`<defs id="cores-do-dualsense">`: a folha dos 28 e os
     três fundos `url(#…)` que ela usa) saem de dentro dos quatro SVGs e passam
     a existir **uma vez** na página, num `<svg>` fora do fluxo. Sem isto o alvo
     não pinta nada: `monta._so_o_colorway` guarda em cada SVG só as regras do
     modelo pedido — 3.127 bytes dos 45.497 —, e escrever `galactic-purple` num
     desenho que nasceu `starlight-blue` cai no cinza neutro de um controle sem
     identidade. A página vai de 310 KB para 343 KB e passa a saber pintar 28
     modelos em vez de 4;
  3. os dois lugares **vazios** perdem o `data-colorway`. Não há aparelho ali, e
     a folha já os pinta de `var(--linha)` — o que sai é identidade do mockup
     parada num lugar que diz "Desconectado".

  **O QUE ELA VÊ HOJE, enquanto o produto não recebe:** nada muda. A página
  publicada não tem o endereço, e o pacote **não emite** o campo para uma página
  que não sabe recebê-lo (`a04_iluminacao.a_pintura_alcanca_o_desenho`) — os
  dois desenhos continuam Cosmic Red e Starlight Blue, exatamente como hoje.
  Medido: **13 valores** pintados com a página publicada, **15** com a da
  bancada.

  **ESPERA DUAS COISAS, e as duas são de quem integra:**

  * o alvo **`atributo`** do `escrever()` do piloto, que nasce numa frente irmã
    (`worktree-wf_88fbb9c0-f51-1`). Sem ele, `escrever()` cai no ramo padrão e
    faz `el.textContent = "white"` num `<svg>` — o desenho de 146 px some e vira
    a palavra. A guarda desta aba **falha fechada** e barra isso;
  * o **`--publicar 04`**, que é ato dela.
- **03/09/2026 · AS ÚLTIMAS DOZE CORES CRAVADAS DESTA ABA, e nenhuma delas
  mudou um pixel do que ela aprovou.** O portão da cor acusava doze
  `--plastico:#hex` na `04-iluminacao`, todos em dois lugares:

  | quantos | onde | o que é |
  | --- | --- | --- |
  | 4 | `.players .dono` | o anelzinho do dono, dentro de um botão de número |
  | 8 | `.troca-item` | os itens do "Trocar o número: o antes e o depois" |

  **OS DOIS TINHAM ENDEREÇO E NENHUM TINHA ALVO — meia fechadura.** O `achar()`
  do piloto encontra pelo endereço; o `data-hef-alvo` é o que diz o que escrever
  quando ele chega lá. Os dois contavam com o PAI: a fileira é reescrita inteira
  pelo alvo `html`, e a seção da troca pelo `blocos:`. **Nenhuma das duas coisas
  se lê no HTML** — a primeira é do pai, a segunda mora no JavaScript —, então
  para as réguas aquilo era cor congelada, e era acusado com razão pela letra
  dela: *"um pai endereçado não dá ao filho o direito de trazer cor congelada"*.

  **A cura é o par completo**, e ela não muda a cena: cada anel ganhou endereço
  PRÓPRIO (`players.dono.N`, um por número — quatro anéis com um endereço só
  receberiam a MESMA cor, e cada um é de um dono diferente), o item da troca
  ficou com `troca.item`, e os dois pedem `data-hef-alvo="plastico"`. O pacote
  emite os valores: os anéis por coluna, **depois** do `players` que os recria,
  e a troca como LISTA, na ordem em que a seção desenha os itens.

  **MEDIDO NO WEBKIT DESTA MÁQUINA**, com a mesa forçada a **Nova Pink** e
  **Astro Bot** — dois modelos que o desenho desta aba não tem:

  ```
    players.dono.1  --plastico #e35b8c  borda computada rgb(227, 91, 140)  selo 1
    players.dono.2  --plastico #e8e4dc  borda computada rgb(232, 228, 220)  selo 1
    troca.item x4   #e35b8c / #e8e4dc                                       selo 1
  ```

  **O QUE ELA VÊ HOJE, sem publicar:** nada muda. A página publicada não tem os
  alvos, e o portão continua contando os doze lá — a bancada da 04 está em
  **zero**. O produto recebe no `--publicar 04`, junto com o resto desta aba.

  **UMA COISA A SABER SOBRE O ANTES/DEPOIS:** a `.nota` inteira é escondida
  dentro da janela (`gui/ponte_da_tela.FOLHA_DA_CASA` põe
  `.nota{display:none !important}`) — ela é a legenda que ela lê ao abrir o
  `mockup/04-iluminacao.html` no navegador. A cura vale para o arquivo, que é o
  que ela olha e o que o portão mede; dentro do app, o campo pinta um bloco que
  ninguém vê. Não é motivo para deixar a cor do mockup ali: o arquivo é um só.
- **03/09/2026 · A ARMADILHA QUE QUASE DEU MORDIDA VERDE**, e ela pega qualquer
  frente: uma mordida que só TROCA A ORDEM de duas linhas deixa o arquivo com o
  **mesmo tamanho**, e o Python valida o `.pyc` por `(mtime, tamanho)`. Caindo
  no mesmo segundo da escrita anterior, ele roda o bytecode **CURADO** e a
  mordida passa verde sem ter sido desfeita. Medido nesta frente: a terceira
  mordida deu 15 verdes; com `PYTHONDONTWRITEBYTECODE=1` e o `__pycache__`
  apagado, reprovou na hora. **Toda mordida apaga o `__pycache__` antes de
  medir.**
## 05-vibracao.html

- **03/09/2026 · O DESENHO DO CONTROLE PASSOU A SER O DELA.** A lei: *"os svgs
  do dualsense (…) mudam de acordo com o controle identificado no canto
  superior. é white no p1, mas a borda de tudo é cosmic red e os svgs não são
  os que o meu mapa cataloga. isso tá errado"*. <!-- noqa-acento: citação literal dela -->

  **O QUE MUDA NO ARQUIVO, e nenhuma das três muda um pixel do que ela
  aprovou:**
  1. os quatro `<svg>` ganharam `data-campo="colorway"` mais
     `data-hef-alvo="atributo"` / `data-hef-atributo="data-colorway"`;
  2. a página publica **a folha das dez zonas dos 28 modelos** dela uma vez, e
     cada `<svg>` deixou de carregar a folha de um modelo só. Sem esta metade o
     endereço trocaria a cor errada por um **cinza**: `monta._so_o_colorway`
     poda a folha para o modelo pedido, e escrever `white` num desenho que só
     embute `cosmic-red` não casa regra nenhuma;
  3. os DOIS LUGARES VAZIOS saíram **sem `data-colorway`** — um lugar sem
     aparelho não tem modelo, e afirmar "Galactic Purple" ali é o desenho
     falando por um controle que não existe. O endereço fica, para o dia em que
     um terceiro controle entrar na mesa.

  **MEDIDO ANTES DE ESCRITO, no Chrome, com a página de antes e a de agora:** a
  casca, o painel e a borda das quatro colunas computam **os mesmos rgb** —
  inclusive nos dois lugares vazios, que o `.ctrl.vazia` já pintava com
  `var(--linha)` e `!important` (a especificidade dele, 0,5,1, ganha da regra de
  zona, 0,2,2). O `conferir05.py` sai **byte a byte igual** ao de antes.

- **03/09/2026 · O QUE ELA VÊ HOJE, com a página publicada de agora** —
  fotografado com a mesa dela (P1 White no cabo, P2 Galactic Purple no rádio),
  as duas páginas abertas no mesmo daemon:
  - **na publicada, o P1 é desenhado em Cosmic Red e o P2 em Starlight Blue**,
    com a fita do topo e a linha "Modelo" logo abaixo dizendo `P1 · White · USB`
    e `P2 · Galactic Purple · BT`. É o defeito que a lei nomeia, na tela, com
    três centímetros entre uma coisa e a outra;
  - **na bancada, os dois desenhos vestem o modelo lido** — o P1 branco, o P2
    roxo. 24 valores pintados contra 22 na publicada, e os dois a mais são
    exatamente o `colorway` de cada coluna.

- **03/09/2026 · O QUE ESTA ABA ESPERA, e não é a palavra dela:** o alvo
  `atributo` do `hefesto_vivo.escrever` nasceu numa frente irmã do mesmo dia e
  chega pelo merge. Enquanto ele não estiver no `dev`, os quatro desenhos têm
  endereço e **nenhum troca de modelo** — a página fica como está e nada quebra.
  O relógio dessa espera é
  `tests/unit/test_a_aba05_desenha_o_modelo_do_aparelho.py::test_o_pintor_sabe_escrever_atributo`,
  que reprova dizendo isso.

- **03/09/2026 · para quem for publicar:** `data-hef-atributo` **não está** na
  lista `INVISIVEIS` do `scripts/check_o_desenho_aprovado.py` (arquivo de outro
  dono), então o `--publicar-enderecos 05` não alcança esta leva — é
  `--publicar 05`, que é ato dela. O atributo é endereço puro: não há uma regra
  de CSS que o leia em nenhuma das dez páginas.
## 06-navegacao.html

- **03/09/2026** — **A-COR-VEM-DO-APARELHO.** O desenho do controle em cada um
  dos quatro cartões deixou de ser o do mockup e passou a ser o do aparelho.
  A lei é dela: *"os svgs do dualsense (…) mudam de acordo com o controle
  identificado no canto superior (…) os svgs nao sao os que o meu mapa cataloga. isso ta errado"*. <!-- noqa-acento: citação literal dela -->

  Três coisas, e as três são a mesma cura:

  - o `<svg>` de cada lugar ganhou `data-campo="desenho"`,
    `data-hef-alvo="atributo"` e `data-hef-atributo="data-colorway"`;
  - a folha das cores PODADA saiu de dentro dos quatro SVGs, e a página passa a
    publicar **os 28 modelos do mapa dela, uma vez** — sem isso o atributo
    escreveria um colorway que nenhuma regra casa;
  - uma zona sem `data-colorway` cai no neutro, porque o `ds_limpo.svg` guarda
    dois `fill="#b11f54"` crus (o Cosmic Red velho) que apareciam num controle
    que ninguém identificou.

  **O QUE ELA VÊ DE DIFERENTE DEPOIS DE PUBLICAR:** nos dois controles da mesa
  de hoje, **nada** — o casco já saía White e Galactic Purple, porque a
  `folha_do_plastico` sobrescrevia as variáveis. O que muda é quem tiver
  qualquer um dos outros 26 modelos, e o que some é a cor de aparelho num
  controle sem leitura. A página engorda 33 KB (401 → 434), que é o preço de a
  tabela dela estar inteira na tela em vez de recortada em quatro.

  **O QUE O PRODUTO FAZ ATÉ ELA PUBLICAR, e é nada:** a página que o `WebView`
  renderiza hoje não tem os quatro endereços novos, e valor emitido sem destino
  é descartado sem erro.

  **ATENÇÃO — ESTA PÁGINA NÃO PODE SER PUBLICADA ANTES DO ALVO `atributo` DO PILOTO.**
  Medido na tela em 03/09 com o `hefesto_vivo` sem o alvo: o `escrever()` cai no
  ramo padrão e faz `el.textContent` no `<svg>` — **os quatro desenhos SOMEM**.
  `tests/unit/test_a_06_o_desenho_vem_do_aparelho.py::test_o_piloto_tem_o_alvo_de_atributo`
  é o alarme: vermelho enquanto o degrau não estiver no lugar.
## 08-conexoes.html

- **03/09/2026** — **o desenho do controle deixou de ser o do mockup.** A lei é
  dela: *"os svgs do dualsense (…) mudam de acordo com o controle identificado
  no canto superior. é white no p1, mas a borda de tudo é cosmic red e os svgs
  não são os que o meu mapa cataloga. isso tá errado"*.

  Medido no motor antes desta cura, com os dois controles na mesa: o rótulo já
  dizia `Sony · Player 1 · White · USB` e o desenho ao lado era **Cosmic Red**
  (`rgb(174, 51, 90)`); o do P2 dizia `Galactic Purple` e era **Starlight Blue**
  (`rgb(126, 184, 212)`). Depois: `rgb(228, 224, 216)` e `rgb(116, 88, 142)` —
  o `--z-casca` que o mapa dela dá a cada um.

  **O QUE MUDA NO DESENHO, e é só isto:** os dois `<svg>` da Gestão de Controles
  ganharam três atributos invisíveis (`data-campo="desenho"`,
  `data-hef-alvo="atributo"`, `data-hef-atributo="data-colorway"`), e o
  `<defs id="cores-do-dualsense">` — a tabela dos 28 modelos, a hachura e os dois
  gradientes — saiu de dentro de cada desenho e passou a ir **uma vez** na
  página, num `<svg>` de zero pixel. Dentro dos desenhos ele vinha **podado**
  para um modelo só, e uma tabela podada não tem como virar outro modelo: o
  produto escreveria `white` e a casca cairia no cinza cru. Com a tabela
  compartilhada, **os 28 pintam** — medido no motor, um a um, nenhum sem tinta.
  Nenhuma cor, medida ou posição do que ela aprovou mudou; a página cresceu
  40 KB de CSS que ninguém lê.

  **Uma frase de tela mudou**, porque a antiga passou a ser falsa: a dica do `?`
  da Gestão dizia *"o desenho continua na cor que o resto do Hefesto já
  conhece"*. Agora diz que o desenho segue a mesma leitura da borda, e fica
  cinza junto com ela quando não há leitura.

  **O QUE ELA VÊ HOJE, enquanto o produto não recebe:** nada muda. A página
  publicada não tem os três atributos, o `achar()` do piloto não encontra o
  endereço e a pintura escreve zero — os dois desenhos continuam Cosmic Red e
  Starlight Blue na tela dela. **O produto recebe no `--publicar 08`**, que é
  ato de quem coordena, depois do OK dela.

  **O que NÃO espera por ela** (já está no produto, sem tocar no desenho): oito
  dos 28 modelos do mapa dela — Chroma Teal, Chroma Indigo, Chroma Pearl, Grey
  Camouflage, Ghost of Yōtei, Marathon, Genshin Impact e 007 First Light — são
  pintados com uma **hachura**, e o valor chegava a `tinta_legivel`, onde
  `int("ur", 16)` levanta `ValueError`. Quem ligasse um deles via a aba
  **parar de pintar por inteiro**, sem uma barra na tela e sem erro que
  dissesse por quê. A hachura continua valendo para o desenho; para a barra e
  para a régua do rádio ela é ausência de leitura, que é a regra dela.
- **03/09/2026** — **a DICA da linha por controle SAIU**, nas duas linhas de
  quem está na mesa. Ela dizia `Cosmic Red — 4 de 5 ajustes só deste controle.`
  e `Starlight Blue — 2 de 5 ajustes só deste controle.` — o modelo e a conta do
  DESENHO, congelados no arquivo.

  **MEDIDO NO WEBKIT VIVO, na mesa dela** (P1 White no cabo, P2 Galactic Purple
  no rádio), lendo o `<tr>` e a célula ao lado no mesmo instante:

  ```
    uniq  title do <tr> (congelado)                          guarda.nome (vivo)
      p1  Cosmic Red — 4 de 5 ajustes só deste controle.     P1 • White • USB
      p2  Starlight Blue — 2 de 5 ajustes só deste controle. P2 • Galactic Purple • BT
  ```

  A MESMA linha nomeava dois controles diferentes, e o perfil dela guarda ZERO
  ajustes por controle — o painel acima já dizia `0 de 2`. As duas metades da
  frase estavam erradas.

  **POR QUE SAIU EM VEZ DE VIRAR DADO:** não há canal. O `escrever()` do piloto
  conhece sete alvos e **nenhum escreve atributo**; o alvo `atributo` desta leva
  aceita só nome `data-*`/`aria-*`, para ninguém poder forjar o selo
  `data-hef-visto`. Um `title` do gerador fica congelado para sempre.

  **NADA SE PERDEU:** o modelo está na PRÓPRIA célula que o cursor toca
  (`guarda.nome`, vivo) e a conta está na coluna ao lado (`guarda.secao`, alvo
  `classe`, vivo). É a decisão nº4 dela deste mesmo dia, sobre esta mesma
  tabela: *"Meu Deus melhor nenhuma assim. Auto falante é auto falante, gatilho
  é gatilho."*

  **A DICA DO LUGAR VAZIO FICA**, e a assimetria é decisão: `P3` é um LUGAR, não
  uma peça. Aquela frase não afirma nada sobre aparelho nenhum, então não
  envelhece quando a mesa muda.

  **O QUE ELA VÊ HOJE, sem publicar:** a publicada ainda tem as duas dicas
  erradas. `tests/unit/test_aba10_a_dica_da_linha_nao_e_do_mockup.py` declara
  essa espera em `ESPERA_A_PUBLICACAO` e reprova no dia da publicação, para a
  declaração não apodrecer.

## 07-lancadores.html
- **03/09/2026 · a dica do rodapé parou de nomear um perfil que não é o dela.**
  O `title` dos botões "Salvar Perfil" e "Exportar" dizia *"Grava no perfil
  Mortal Kombat"* — o nome veio do seu próprio pedido, e era um EXEMPLO
  (*"'Aplicar vale agora • Salvar Perfil grava no Mortal Kombat' isso deveria em
  formato de tooltip"*); o `fim.html` congelou o exemplo em vez do nome.

  **O que você vê ao publicar:** a dica passa a dizer o nome do perfil que está
  ativo de verdade — hoje, `meu_perfil`. Sem perfil ativo ela diz *"no perfil
  ativo"*, que é o mesmo texto congelado, para nunca inventar um nome.

  **O rodapé é UM para as dez abas** (`fim.html`), então esta mesma linha vale
  para todas — as outras oito já estavam declaradas aqui por outros pontos.

  **O QUE O PRODUTO FAZ HOJE, até você publicar, e é preciso dizer:** a dica
  continua mostrando *"Grava no perfil Mortal Kombat"*. O produto já MANDA o
  nome certo — `topo()` emite `rodape.salvar` e `rodape.exportar` a cada tique
  —, mas a página publicada **não tem esses dois endereços**, então o valor
  chega e não encontra onde pousar; o `title` congelado da página de ontem é o
  que fica na tela. Nada quebra e nada muda: é o mesmo texto de sempre, e a
  correção só aparece no dia do `--publicar`.

## 09-sistema.html
- **03/09/2026 · a mesma dica do rodapé.** Ver a razão em `07-lancadores.html`,
  logo acima: o `fim.html` é um só para as dez páginas, e a correção chega às
  dez de uma vez.

  **O que o produto faz hoje:** o mesmo que na 07 — a dica ainda diz *"Grava no
  perfil Mortal Kombat"*, porque a página publicada não tem os dois endereços
  novos. O valor certo é emitido e fica órfão até você publicar.
## 03-gatilhos.html
- **03/09/2026 · A COR DO PLÁSTICO GANHOU ENDEREÇO PRÓPRIO** — a lei dela:
  *"imagina que cada pessoa tenha um dualsense diferente. (…) eu quero que cada
  um, ao usar seu controle, se toque disso — que o app se adaptou ao controle
  dele"*.

  **O que mudou no desenho é MARCAÇÃO, e a cena continua a que ela aprovou.** O
  cabeçalho de cada coluna era um `<div class="cabeca">` com o chip dentro; hoje
  são dois níveis, e cada um tem um trabalho:

  ```
  .cabeca   data-campo="plastico"          alvo `plastico`  → a COR do aparelho
    span    data-campo="chip-do-controle"  alvo `html`      → o CHIP inteiro
  ```

  **POR QUE PRECISOU DE DOIS NÍVEIS.** O `--plastico` morava no `style` do
  `<span class="chip …">`, isto é, DENTRO do `innerHTML` que o alvo `html`
  compara. Ali ele não podia ganhar alvo próprio: `escrever()` carimba
  `data-hef-visto` no elemento que visita, e um selo dentro do HTML comparado
  faz a comparação nunca mais bater — a coluna repintaria a cada tique, para
  sempre (medido nesta casa: 17 tiques, 17 pinturas). No embrulho, que fica
  fora da comparação, as duas escritas convivem.

  **A CONTA DA RÉGUA**, `scripts/check_a_cor_vem_do_aparelho.py --bancada
  --aba 03`: **2 → 0**.

  **MEDIDO NO WEBKIT, com uma mesa de dois modelos que o mockup NUNCA mostrou:**

  | coluna | texto | `border-color` computada |
  | --- | --- | --- |
  | P1 | `P1 • Nova Pink • USB` | `rgb(227, 91, 140)` = `#e35b8c` |
  | P2 | `P2 • Astro Bot • BT` | `rgb(232, 228, 220)` = `#e8e4dc` |
  | P3 e P4 | `Desconectado` | `rgb(68, 71, 90)` — a variável APAGADA |

  Nenhuma das duas primeiras é cor do desenho, e é esse o ponto: trocar o Cosmic
  Red por outro hexadecimal escrito à mão teria sido trocar um cravado por
  outro. O hexadecimal sai de `monta.cor_da_zona`, que LÊ a folha dos 28 modelos
  do `docs/data/cores-do-dualsense.csv` — no dia em que ela acrescentar um
  modelo, a aba o veste sem uma linha de Python a mais.

  **NADA MUDA NA TELA DELA ANTES DO `--publicar 03`, e isso foi conferido, não
  suposto.** A página publicada não tem o endereço da cor; se o pacote
  escrevesse só nele, as duas colunas dela ficariam com a borda neutra
  (`rgb(68, 71, 90)`) até a publicação. Por isso o pacote **pergunta à página**
  (`a_pagina_recebe_a_cor_por_endereco`) e, enquanto ela não tiver o endereço,
  continua mandando a cor dentro do chip — como sempre mandou. Medido nas duas
  páginas, com o mesmo Nova Pink na mesa: `rgb(227, 91, 140)` nas duas. A ponte
  **se aposenta sozinha** no dia da publicação, e
  `tests/unit/test_aba03_o_plastico_de_qualquer_modelo.py` cobra os dois lados.
