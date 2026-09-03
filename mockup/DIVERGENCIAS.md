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
