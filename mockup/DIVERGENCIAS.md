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
