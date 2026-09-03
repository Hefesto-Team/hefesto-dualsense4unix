import re, sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
import onde
from monta import (monta, glifo, rotulo, CSS_GLIFO, CSS_LUZINHAS, MESA, CONECTADOS,
                   SEPARADOR, cor_da_zona, luzinhas, player_slot_color, tom_da_casa)

# O TEXTO DE TELA DESTA ABA MORA NO PACOTE, e a seta aponta para cá — não daqui
# para lá. O produto (`pacotes/a02_controles.py`) é quem ESCREVE estas palavras
# na tela a cada tique; o gerador só as desenha uma vez, e desenhá-las de uma
# segunda cópia é como o "Sem toque" já divergiu antes.
#
# A DIREÇÃO É OBRIGATÓRIA, e não gosto: o `portao_a_casa_sabe_e_o_produto_nao_faz`
# PODA os `abaNN.py` da conta, porque são BANCADA (`_NAO_E_PROMESSA`:
# *"rodam à mão, escrevem em `mockup/`, e o produto lê o HTML já pronto"*).
# Importar o gerador DE DENTRO do pacote arrasta a bancada para o fecho de
# produção — medido em 02/09/2026: três lápides de `interface/monta.py`
# (`monta`, `luzinhas`, `tom_da_casa`) viraram alcançáveis e o portão reprovou
# nomeando as três. Aqui, ao contrário, é bancada lendo produto, e a poda segue
# valendo.
#
# E O IMPORT É O DO VIZINHO (`pacotes.…`), não o de pacote instalado
# (`hefesto_dualsense4unix.interface.pacotes.…`): os dois caminhos carregam o
# MESMO arquivo em DOIS módulos diferentes, com dois registros de gesto e duas
# cópias de cada string. É por isso que a linha 1 deste arquivo põe a pasta no
# `sys.path`, e é a forma que o `onde` e o `monta` logo acima já usam.
# O `CLICADO` NÃO ENTRA: a cena fixa do mockup não tem analógico apertado, e
# importá-lo sem uso é F401 no portão. Ele é do PACOTE — quem o escreve na
# tela é o tique, não o desenho.
from hefesto_dualsense4unix.app.widgets.sensor_widgets import texto_toques
from pacotes.a02_controles import ROTULO_DO_CLIQUE, meias_da_barra as _meias_da_barra
from pacotes.a02_controles import texto_do_xy as _texto_do_xy

# ---------------------------------------------------------------------------
# D-A-LEITURA-DO-ACELERÔMETRO-SAI-DA-TELA (29/08/2026) — MUDANÇA DE ESPECIFICAÇÃO.
#
# O mockup que ela aprovou desenhava três linhas de acelerômetro com NÚMEROS
# (`X +0.1 · Y +0.9 · Z +0.0` — um controle deitado numa mesa). Elas saem.
#
# A PALAVRA DELA QUE AUTORIZA, 29/08: *"Redistribuir o último bloco
# (giroscópio/acelerômetro) — o acelerômetro não funciona"*.
#
# A MEDIÇÃO QUE JUSTIFICA, e ela é de três fontes independentes:
#   1. o `daemon.state_full` da mesa dela, agora: `inputs` = buttons, gyro,
#      l2_raw, lx, ly, r2_raw, rx, ry, speaker, touchpad. NÃO HÁ chave de
#      acelerômetro, nos dois controles;
#   2. `docs/data/mapa-controles.csv`, `movimento.acelerometro@dualsense`:
#      `cabo_aciona=não`, `radio_aciona=não`, os DOIS medidos, provados em
#      15/08/2026 com teste que morde
#      (`test_sensores_status.py::test_motion_reader_ignora_o_acelerometro…`);
#   3. `2026-08-26-O-QUE-ELA-DESENHOU:177`: *"O acelerômetro não existe do lado
#      dela em ponto nenhum: nem tela, nem perfil, nem IPC."*
#
# O CONTRATO NÃO É CONTRARIADO — ELE É CORRIGIDO. O `2026-08-26-O-REDESENHO`
# lista, em "Leitura viva, sem botão", *"os três eixos do giroscópio"*, e o
# "Nada se perdeu" desta aba diz *"16 glifos, analógicos, L2/R2, touchpad,
# giroscópio — ficam"*. O acelerômetro não está em nenhuma das duas. A única
# linha que o afirmava é a de contexto do "o que ainda falta decidir" (*"o
# giroscópio e o acelerômetro são lidos nesta tela"*), e essa frase é FALSA,
# medida.
#
# O QUE **FICA**, e confundi-los apagaria uma decisão dela: o INTERRUPTOR de
# Acelerômetro na linha de cada controle (D9, 28/08 — *"Três botões separados:
# [Giroscópio] [Acelerômetro] [Calibrar sensores]"*). Interruptor e leitura são
# coisas diferentes com a mesma palavra; o que sai é a LEITURA.
#
# O QUE ISSO DEVOLVE: 81px na coluna dos sensores, que era o bloco mais vazio
# dos cinco — e é o espaço que a pergunta dela ("redistribuir") mandou olhar.
#
# CORREÇÃO DE FATO, 29/08 (o mesmo dia, mais tarde): a dica do bloco e a legenda
# diziam *"o aparelho **não o entrega** — nem pelo cabo, nem pelo rádio"*. É
# FALSO, e as duas frases foram substituídas. A leitura de `aciona=não` como "o
# aparelho não entrega" pulou uma coluna: quem responde por isso é `aceita`, e o
# mapa diz `cabo_aceita=sim` e `radio_aceita=sim` na MESMA linha. Medido nos dois
# controles dela agora, com `evdev` cru nos nós `… Motion Sensors`: ABS_X/Y/Z
# publicam `resolution = 8192` (a escala de ±4 g do `hid-playstation.c`) e o
# módulo do vetor fecha em **0,996 g** e **0,993 g** contra 1 g, com os dois em
# poses diferentes na mesa (25° entre os vetores) — leitura, não constante.
# O acelerômetro CHEGA; quem descarta é o `MotionSensorReader`, cujo laço de
# `_handle_event` percorre só ABS_RX/RY/RZ. `aciona=não` continua certo, e é o
# que a tela mostra: o produto não publica. O que mudou é a EXPLICAÇÃO.
#
# ESTE BLOCO INTEIRO É LÁPIDE — CADUCOU NO MESMO 29/08, MAIS TARDE. Ela derrubou
# a premissa com estas palavras: *"não era pra ele sair. era pra ele
# FUNCIONAR."*, e a `ONDA-CONTROLES-04` fez o produto publicar `inputs.accel`.
# A leitura VOLTOU (é o `accel_html` e o `data-bloco="acelerometro"` logo
# abaixo), e a linha 2 acima virou FATO ERRADO — conferido em 01/09/2026:
#
#     docs/data/mapa-controles.csv:175  movimento.acelerometro@dualsense
#         cabo_aciona = SIM · radio_aciona = SIM   (desde 29/08/2026)
#
# O bloco fica porque a decisão de tirar a leitura foi TOMADA e depois
# REVERTIDA, e apagar isso faria a próxima pessoa refazer a conta dos 81px. Mas
# ninguém deve mais ler `aciona=não` daqui: o número certo está na linha do CSV
# acima, que é o dono.
# ---------------------------------------------------------------------------

CSS = CSS_GLIFO + CSS_LUZINHAS + """
  /* ---------- Controles ----------
     O DESENHO É O DA ABA STATUS DE HOJE, que ela disse gostar muito. Comparado
     lado a lado em 27/08, o que quebrava a harmonia da minha primeira versão:
       1) TRÊS CAIXAS grandes envolvendo tudo — o original só põe moldura em
          Touchpad, Barra de luz, Giroscópio, Microfone e Alto-falante; o resto
          flutua, e é isso que dá ar à tela;
       2) DENSIDADE — 394 px contra 637 px meus, para o mesmo conteúdo;
       3) COR COM SIGNIFICADO — ✕ e L2/R2 na cor do plástico, o resto neutro.
     O que muda do original é só o que ela pediu: sai o "Ouvir no controle",
     entra o Calibrar da mesa no topo e os dois interruptores de sensor na linha
     de CADA controle (28/08), e a faixa da antiga aba "No jogo" desce para
     dentro do card. */

  /* A COR DO PLÁSTICO É UMA VARIÁVEL, NÃO UMA CLASSE. Ela era `.c-red` e
     `.c-blue` — uma classe por modelo, com o hexadecimal digitado no CSS. Com os
     QUATRO da mesa isso vira quatro classes; com os 28 do
     `docs/data/cores-do-dualsense.csv`, vinte e oito. E o hex digitado era o
     defeito medido: o Cosmic Red do mockup era `#b11f54` e a amostragem devolveu
     `#A51C48`. Agora cada card nasce com `--plastico`, lido por
     `monta.cor_da_zona()` do `<style>` que o gerador de cores escreveu dentro do
     desenho — a MESMA folha que pinta o SVG, lida de volta. */
  /* O CARD CRESCE PARA FECHAR O VÃO, E NÃO ENCOLHE: `flex:1 0 auto`. O `0` é a
     parte que morde — com o `flex-shrink` de fábrica o card afundaria abaixo dos
     seus 301px e o conteúdo vazaria por baixo da borda, calado. */
  /* A CLASSE `card` DEIXOU DE PINTAR, e ficá-la aqui não é sobra: ela é a
     âncora da régua (`.quadro-corpo > .card`), que confere POR DENTRO que nada
     vaza da caixa — foi ela que pegou o círculo do analógico passando 24px para
     fora da moldura. Quem pinta agora é `.ctl`, logo abaixo, porque o card
     aberto e a tira fechada viraram O MESMO ELEMENTO. */

  /* ---------- O ACORDEÃO, E ELE É CSS PURO ----------
     Decisão dela, 28/08/2026: "clicar num abre e fecha os outros", "CSS puro,
     sem JavaScript", "o da fita já vem aberto, e clicar num card muda a fita",
     "o chip Todos abre os quatro", "a linha fechada mantém o resumo de hoje".

     COMO, SEM UMA LINHA DE JS: um rádio por controle, todos com o mesmo `name`.
     O navegador já garante que ligar um desliga os outros — que é exatamente a
     regra do acordeão, e não precisa de código. A linha de identidade é um
     `<label for>` do rádio do seu controle, e os chips da fita são `<label for>`
     DOS MESMOS rádios. Por isso clicar na fita e clicar na linha são o MESMO
     gesto: não há dois estados para manter de acordo, há um só, e ele mora no
     rádio. Quem escolhe qual abre continua sendo a fita — ela só ganhou um
     segundo lugar de onde ser clicada.

     O CARD E A TIRA VIRARAM UM ELEMENTO SÓ. Antes eram duas caixas escritas por
     duas funções (`card()` e `tira()`), e o que as impedia de discordar era a
     linha de identidade compartilhada. Com o acordeão isso não bastaria: a
     mesma caixa tem de VIRAR a outra ao clique, e CSS não troca elemento — troca
     estilo. Então `.ctl` é a caixa e o estado é `:has(> input:checked)`.
     A conta do recuo é a prova de que a troca não move o texto um pixel:
     fechado, ele começa em 2 (borda) + 26 (padding) = 28; aberto, em 2 (borda)
     + 14 (margem da faixa) + 1 (borda dela) + 11 (padding dela) = 28. Os mesmos
     28 das duas formas antigas, e a mesma largura útil de 1096px nas duas.

     O CORPO FECHADO NÃO PODE VIRAR `display:none`, e o motivo é medido nesta
     régua: ela lê a altura de todo `button` e reprova família com alturas
     divergentes. Com `display:none`, os dois botões de rota de cada card
     fechado medem 0, e ela acusa `altura divergente em button.-: 0 / 36` — um
     defeito que só existiria porque o elemento sumiu. `height:0;overflow:hidden`
     mantém o corpo DESENHADO no tamanho natural e só o recorta: a régua segue
     medindo os QUATRO cards por dentro (as colunas somando a largura da caixa,
     as colunas acabando no mesmo y), e não só o que está à mostra. A régua ficou
     mais severa do que era, não menos.

     "TODOS" ABRE OS QUATRO, E AÍ A CAIXA ROLA — o número está na legenda. É o
     único estado desta aba que rola, e ele é um gesto explícito dela; o estado
     em que a aba abre (um card e três tiras) continua fechando sem sobra e sem
     rolagem, que é o que curou a aba que mostrava um controle e meio.

     A CLASSE NÃO PODE SE CHAMAR `tira`, e o estrago já esteve de pé e MEDIDO:
     `.tira` é a TIRA DE ABAS do esqueleto (`topo.html:109`). Com a regra deste
     arquivo chamada assim, `height:34px` e `text-transform:uppercase` caíam na
     fila de abas lá em cima: o cabeçalho encolheu 8px e o miolo desta aba mediu
     **550px contra os 542 de todas as outras nove**. É a mesma cicatriz que a
     Conexões pagou com `.peca` e com `.mesa` — e a régua de alinhamento passou
     VERDE nas duas vezes. Nome de classe se confere no `topo.html` ANTES de
     escrever. */
  .radio-mesa{position:absolute;width:0;height:0;opacity:0;margin:0}
  .quadro-corpo{overflow-y:auto;gap:9px}
  /* O RECUO DE 26px NÃO É ARBITRÁRIO: é o 14px da margem lateral da faixa
     aberta mais os 11px do padding dela — mais 1, porque a borda da faixa aberta
     tem 1px e a da caixa tem 2. Com ele o nome do controle nasce no MESMO x nas
     quatro linhas (432), abertas ou fechadas, e as quatro barras de bateria
     terminam no mesmo x (1488). Com os 25px da primeira tentativa dava 431
     contra 432: um pixel, e ela repara em dois. */
  .ctl{display:flex;flex-direction:column;flex:0 0 auto;height:var(--h-acao);
       border:2px solid var(--plastico);border-radius:9px;background:var(--app-bg)}
  .ctl > .faixa{flex:1;margin:0;padding:0 26px;border:0;border-radius:0;
                background:transparent;flex-wrap:nowrap;white-space:nowrap;
                cursor:pointer;-webkit-user-select:none;user-select:none}
  /* A LINHA FECHADA DIZ QUE SE CLICA NELA, e diz do jeito que esta casa já diz:
     é o mesmo `rgba(255,255,255,.03)` do hover da fila de abas (`topo.html`).
     Uma segunda gramática de "clicável" na mesma janela é uma a mais. */
  .ctl:hover{background:rgba(255,255,255,.03)}

  /* ---------- O LUGAR VAZIO ----------
     Decisão dela, 31/08/2026: *"Deixa os outros espaços dos 4 controles a mostra
     ainda mas cinza igual vc fez na aba jogar."* — e, no mesmo turno,
     *"tiramos o modo p3. p4 (seções expandidas não aparecem)"*.

     A GRAMÁTICA É A MESMA DA JOGAR, de propósito: cor explícita e nada de
     `opacity` (a lição medida da `.fita.inerte`), borda `--border-sutil` no
     lugar do plástico, e o texto em `--linha`. Duas gramáticas de "vazio" na
     mesma janela seria uma a mais — a mesma razão que o `.ctl:hover` acima dá.

     A ALTURA É 24, E ELA É O QUE PAGA OS BOTÕES NOVOS. Um lugar vazio não tem
     giroscópio para ligar nem bateria para medir, então não precisa dos 34 de
     `--h-acao`. Medido: com os dois lugares em 34 o `.quadro-corpo` pedia 509
     e recebia 478 — o quadro rolava e os dois botões saíam da tela pela metade.
     Não se clica: sem `<input>` no HTML, não há o que expandir. */
  /* A BORDA SE DECLARA INTEIRA AQUI, e não só a cor — e isto é uma armadilha de
     CSS que custou duas voltas. `.ctl` diz `border:2px solid var(--plastico)`, e
     o lugar vazio NÃO tem `--plastico` (não há controle, não há cor de
     plástico). Uma `var()` sem valor **invalida a declaração inteira**, em
     silêncio: a borda não fica cinza — ela deixa de existir. Medido no DOM,
     depois de a foto mostrar dois lugares soltos, sem caixa nenhuma:
     `border-width: 0px, border-style: none`, com o `border-color` que eu tinha
     escrito ali, intacto e inútil.
     Trocar só a COR de uma regra que usa `var()` indefinido não conserta nada.

     E A COR NÃO É A `--border-sutil` DA JOGAR: lá o cartão vazio fica sobre
     `--app-bg` (#21222c) e aquele #343746 aparece; aqui ele fica sobre `--panel`
     (#282a36) e sumiria de novo. Copiar a gramática é copiar o CONTRASTE, não o
     token. */
  .ctl.off{height:24px;border:1px solid var(--border-forte);background:transparent}
  .ctl.off > .faixa{cursor:default;color:var(--linha)}
  .ctl.off:hover{background:transparent}
  .ctl.off .card-nome,
  .ctl.off .div,
  .ctl.off .leia,
  .ctl.off .bat{color:var(--linha)}

  /* ---------- UM LUGAR SEM CONTROLE NÃO TEM BATERIA, NEM LUZ, NEM SENSOR ----
     03/09/2026, medido clicando no produto instalado com UM controle no cabo.

     O QUE A TELA MOSTRAVA: a linha do P2 — com o cabeçalho dizendo `1 controle`
     e TODOS os campos de texto no travessão — trazia uma barra de bateria
     PINTADA a 89,9 px de 140,5 (`style="width:64%"`, o literal deste gerador) e
     os dois chips de sensor em `rgb(80, 250, 123)`, o mesmo verde do controle
     que está mesmo na mesa. Quem olha lê "o P2 tem 64% e o giroscópio ligado".

     POR QUE O TRAVESSÃO NÃO ALCANÇOU ESTES: o molde do lugar vazio
     (`pacotes.apagar_os_lugares_sem_dono`) escreve `—` em TODA chave, e o
     `escrever()` do piloto leva o travessão a `style.width = '—%'` — CSS
     inválido, que o CSSOM DESCARTA CALADO. O número virou travessão; o pixel
     ficou com o desenho. Medido: escrever `'—%'` na barra deixa `style.width`
     em `64%`, byte por byte. Os chips não têm `data-campo` nenhum — não há
     endereço por onde o produto os alcance.

     A CURA AQUI É DA FOLHA, e é a que sobrevive ao pixel do mockup: uma regra
     de estilo vence o `style=` inline com `!important`, e não depende de o
     produto lembrar de apagar. Ela pende do `data-conectado`, que é o que o
     piloto MANTÉM a cada tique (`hefesto_vivo.py`, laço dos `vazios`) — o mesmo
     seletor que a aba Gatilhos já usa, e não um terceiro estado inventado.

     E O CINZA NÃO É NOVO: `.sensores-peca .sw.off` já é o desligado que ESTE
     desenho tem. O lugar vazio passa a usá-lo, em vez de ganhar cor própria. */
  .ctl[data-conectado="nao"] .bat .cheio,
  .ctl[data-conectado="nao"] .vol .cheio{width:0 !important}
  .ctl[data-conectado="nao"] .vol .cheio::after{display:none}
  .ctl[data-conectado="nao"] .barra-luz{color:var(--panel) !important}
  .ctl[data-conectado="nao"] .sensores-peca .sw{
    border-color:var(--border-forte);background:var(--app-bg);color:var(--texto-mudo)}
  .ctl[data-conectado="nao"] .sensores-peca .sw .p{
    background:var(--border-forte);box-shadow:none}

  /* ---------- OS DOIS BOTÕES DO FIM ----------
     Ela, 31/08: *"Temos que ter dois botões no final."* Eles são `<a>`, e não
     `<button>`, porque abrem PÁGINA — o `.btn` desta casa já é usado nas duas
     formas, e um link que se veste de botão continua sendo um link para quem
     usa teclado e leitor de tela. */
  /* OS DOIS BOTÕES DO CANTO SUPERIOR DIREITO. Eles são `<a>` e não `<button>`
     porque abrem PÁGINA — um link que se veste de botão continua sendo link
     para quem usa teclado e leitor de tela. A `.sensores` (logo abaixo) é quem
     os empurra para a direita; aqui só a altura, que é a do `.btn` da casa.
     ELES JÁ ESTIVERAM NO FIM DO QUADRO, entre 31/08 e o turno seguinte, e ela
     mandou voltarem: *"A posição deles volta pro canto superior direito."* */
  .sensores .btn{display:inline-flex;align-items:center;text-decoration:none;
                 height:var(--h-acao);padding:0 13px;font-size:12.5px}
  .corpo-cx{flex:0 0 0;height:0;overflow:hidden;visibility:hidden}
  /* "TODOS" É O ÚNICO ESTADO QUE ROLA, E A BARRA TEM DE APARECER — senão ele
     é o defeito de 27/08 de volta com outra roupa. Medido agora, sem esta
     regra: em "Todos" a caixa esconde 794px, o P3 e o P4 ficam com ZERO pixel à
     mostra e a barra é SOBREPOSTA — ela some quando ninguém está rolando, e
     nada na tela diz que os dois existem. Com uma regra de `::-webkit-scrollbar`
     o Chrome desenha a barra CLÁSSICA, que ocupa espaço e fica: ela nasce só
     quando há o que rolar, então os estados de um card aberto não pagam nada
     por ela — e é por isso que ela vale mais que `scrollbar-gutter:stable`, que
     reservaria 15px em toda tela para um estado que quase nunca acontece. */
  .quadro-corpo::-webkit-scrollbar{width:10px}
  .quadro-corpo::-webkit-scrollbar-track{background:transparent}
  .quadro-corpo::-webkit-scrollbar-thumb{background:var(--border-forte);border-radius:5px}
  .quadro-corpo::-webkit-scrollbar-thumb:hover{background:var(--comment)}

  /* O NOME DO CONTROLE mora dentro da faixa de estado rápido — pedido dela em
     27/08. Antes era uma linha própria acima, e a faixa nascia meio vazia.
     A ORDEM É A DELA: player • plástico • transporte, a forma `curta` — a mesma
     do chip da fita. Ela nasceu em 26/08 com a marca na frente e ela a tirou em
     27/08 ("tira o Sony das outras abas também"). O comentário que estava aqui
     dizia que "a forma COMPLETA cabe": ela cabia por 1px, e não cabe mais — o
     porquê, com o número, está em `identidade()`.
     O TEXTO SAI DE `monta.rotulo(c, "curta")` — ver `identidade()`. Aqui morava
     `.card-nome .quem{color:var(--texto-mudo);font-weight:400}`, que esmaecia a
     segunda metade do rótulo: ela existia porque o nome vinha PARTIDO em dois
     `<span>` montados à mão. Com o rótulo vindo inteiro de uma fonte só não há
     metade para esmaecer, e a regra virou letra morta — sai junto.
     A CAIXA, se um dia ela a quiser, é `text-transform` NESTA regra, nunca
     maiúscula no HTML: em maiúscula ninguém copia o nome do plástico daqui. */
  .card-nome{font-size:12.5px;font-weight:600;color:var(--fg)}
  /* A BARRA DA BATERIA TEM UMA LARGURA SÓ, NAS QUATRO LINHAS — e isso não é
     capricho de alinhamento, é leitura. Ela ESTICAVA para ocupar o vão que
     sobrasse (`flex:1;max-width:420px`), e com o card aberto e três tiras o vão
     é diferente em cada linha: os trilhos mediram 312, 60, 35 e 139px. O
     preenchimento é uma porcentagem do trilho, então o 31% do P3 num trilho de
     35px desenhava uma barra MENOR que o 64% do P2 num de 60 — quatro réguas de
     tamanhos diferentes empilhadas, que o olho compara e lê errado. Fixa, as
     quatro comparam. */
  /* O `margin-left:auto` SAIU DAQUI e passou ao `.sensores-peca`, que agora é o
     vizinho da esquerda: dois autos na mesma linha partem a sobra ao meio, e o
     grupo de botões pararia num x diferente em cada linha. Quem empurra o fim
     da linha para a direita é ele; a bateria vem colada, no passo de 9px. */
  .bat{flex:0 0 var(--larg-bateria);display:flex;align-items:center;gap:9px;
       font-size:11.5px;color:var(--texto-mudo)}
  .bat .trilho{flex:1;height:6px;border-radius:3px;background:var(--border-forte);position:relative}
  .bat .cheio{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--purple)}
  .bat .n{font-family:'JetBrains Mono',monospace;color:var(--fg);flex:0 0 42px;text-align:right}
  /* A LINHA DE IDENTIDADE É UMA SÓ, E AGORA É UM ELEMENTO SÓ. `.faixa` é a
     linha do card aberto E a tira do fechado: o que muda entre as duas é a
     CAIXA, nunca o conteúdo. Card e tira não podem discordar sobre quem é o
     controle — e agora não têm como, porque são o mesmo `<label>`. */
  .faixa{display:flex;align-items:center;gap:9px;
         font-size:11.5px;color:var(--texto-mudo);
         }
  .faixa b{color:var(--texto-suave)}
  /* todo item da faixa tem a MESMA altura de linha. O ícone "?" do aviso de
     máscara tinha 17px e esticava só aquele span para 19px, subindo o texto
     2,5px. NÃO usar inline-flex aqui: ele transforma cada palavra em item e come
     o espaço entre elas — vira "vê comoDualSense". */
  .faixa > span{line-height:14px}
  /* O AVISO DE MÁSCARA SAIU DA TELA — decisão dela, 28/08: nenhum aviso, em
     máscara nenhuma. O texto que estava aqui dizia que sob Xbox 360 "o
     giroscópio, o acelerômetro e o touchpad não chegam ao jogo", e ele partia de
     uma leitura errada do que a máscara faz: ela limita o que o JOGO recebe, não
     o que o CONTROLE faz — o Hefesto continua acendendo a barra de luz, lendo o
     giro e capturando o microfone deste DualSense em qualquer máscara. O que
     sobra é o `cursor:help`: há texto a ler, e ele é explicação, não alarme.
     E A CLASSE MUDOU DE NOME COM ELE. Ela se chamava `.diverge` porque marcava
     a máscara que divergia do perfil; sem o aviso, o nome passou a apontar para
     um conceito que não existe mais nesta tela — e nome de classe que descreve
     o que morreu manda a próxima pessoa procurar uma pintura que não há. Agora
     é `.leia`, que é o que ela faz: diz que aquele item tem texto embaixo. */
  .faixa .leia{cursor:help}
  .faixa .div{color:var(--texto-mudo)}   /* cor de texto, não de borda (topo.html: `.seta`) */
  /* os gatilhos: número EM CIMA da barra, como no original.
     O `margin-top:auto` SAIU, e ele era a causa do maior buraco da tela.
     Enquanto L2/R2 moravam dentro da moldura do giroscópio, aquele `auto`
     empurrava as duas linhas para o pé e empoçava a sobra INTEIRA da coluna
     num vão só: medido em 29/08 na mesa dela, **181 px** de vazio entre o
     eixo Z e o L2 — e o vão variava com a mesa (138 com três controles, 95
     com quatro), porque não era desenho, era resto. */
  .gat{display:flex;flex-direction:column;justify-content:space-around;flex:1}
  .gat-linha{display:grid;grid-template-columns:20px 1fr;align-items:center;gap:8px;
             font-size:11px;color:var(--texto-mudo);margin-bottom:9px}
  .gat-linha:last-child{margin-bottom:0}
  .gat-linha .trilho{position:relative;height:8px;border-radius:4px;background:var(--panel);
                     border:1px solid var(--border-forte)}
  .gat-linha .cheio{position:absolute;left:0;top:0;bottom:0;border-radius:4px;background:var(--pink)}
  /* `white-space:nowrap` NO NÚMERO, e ele não é enfeite. O `.n` é absoluto com
     `left:50%` e sem `right`, então a largura que o navegador lhe dá é METADE do
     trilho: num trilho de 92px ele tem 46 para "200 / 255", que mede 57 — e
     quebrava em duas linhas, uma delas por cima da barra. Aparecia só quando a
     coluna encolhia, que é o estado que ninguém fotografa. */
  .gat-linha .n{position:absolute;top:-14px;left:50%;transform:translateX(-50%);
                white-space:nowrap;
                font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--texto-suave)}
  /* SEM as três caixas: o miolo é uma grade de blocos soltos */
  /* AS CINCO COLUNAS SÃO PROPORÇÕES, E NÃO PIXELS — 31/08/2026.
     Os números são os mesmos: na janela do produto (1180px) o `card-corpo` tem
     1036px para repartir, e 168+226+212+308+122 = 1036. Cada coluna nasce com a
     largura exata que tinha. O que muda é o que acontece quando a janela é MENOR
     que 1180 (o `.janela` é `max-width:100%`): com quatro colunas em pixel fixo,
     TODO o encolhimento caía na única coluna flexível — a do som. Medido em
     31/08 num navegador de 1000px: ela ia a 78px e os três botões do Modo do
     Mic, mais o "Todo o som do PC", pintavam 200px POR CIMA dos Sensores e dos
     Gatilhos. É a tela que ela fotografou. Em proporção, as cinco encolhem
     juntas e nenhuma colapsa — que é como as outras nove abas se comportam.
     `minmax(0,…)` continua obrigatório: `Nfr` sozinho tem mínimo automático
     `auto` (= min-content), e é ele que faz a coluna se recusar a encolher.

     A COLUNA DO SOM GANHOU 46px E A DOS SENSORES OS PERDEU (244 -> 290,
     186 -> 140), e a conta é medida, não gosto: a linha do rótulo do Microfone
     pede 278px ("Microfone" 55 + o selo 45 + o "?" 17 + os três botões de modo
     150, mais o padding da moldura) e recebia 244 — os 34px de diferença eram o
     "Nativo" e metade do "Desativado" pintados FORA da moldura, atravessando o
     bloco vizinho. Do outro lado sobrava: com os dois sensores numa moldura só,
     a quinta coluna pede 99px de conteúdo natural.
     E 140 É PISO, NÃO ESCOLHA: abaixo disso a barrinha de cada eixo cai de 51px
     para menos de 40 e deixa de dizer magnitude — que é a única coisa que ela
     diz. Foi por isso que a primeira tentativa (122) foi desfeita: a régua deu
     verde e a FOTO mostrou seis barras de 23px. Medir sem olhar não fecha. */
  .card-corpo{display:grid;gap:11px;
              grid-template-columns:minmax(0,168fr) minmax(0,226fr) minmax(0,212fr)
                                    minmax(0,290fr) minmax(0,140fr);
              padding:12px 14px 0;align-items:stretch}
  /* as cinco colunas terminam na mesma linha. A do som manda a altura; nas outras
     o CONTEÚDO cresce para acompanhar — o touchpad estica, os analógicos ficam
     maiores e a grade de botões espalha as fileiras. */
  .card-corpo > div{display:flex;flex-direction:column}
  .card-corpo > div > .moldura{flex:1;display:flex;flex-direction:column}
  .card-corpo > div > .moldura:first-child{flex:1;display:flex;flex-direction:column}
  /* NA COLUNA 1 QUEM CRESCE É O TOUCHPAD, E SÓ ELE. Com as duas molduras em
     `flex:1 1 0%` a sobra da coluna era partida ao meio, e como o touchpad tem
     piso (a proporção do sensor) a metade dele sobrava DENTRO da moldura da
     barra de luz: 42px de vazio cercados por uma borda, que é a cara de bloco
     quebrado. Medido antes: touch 118 / luz 109 com 42px de ar. Depois: o ar
     inteiro vira superfície de toque, e a moldura de baixo fica do tamanho do
     que tem dentro.
     ESTICAR O TOUCHPAD NÃO MENTE A POSIÇÃO DO DEDO, e isso é do produto, não
     meu: `sensor_widgets.TouchpadView` normaliza por FRAÇÃO
     (`px = 2 + fx * (largura - 4)`) e o comentário dele diz com todas as
     letras — "alargar não mente a posição do dedo… o que muda é a proporção do
     retângulo". */
  .card-corpo > div:first-child > .moldura.touchp{flex:0 0 auto}
  .card-corpo > div:first-child > .moldura.luz{flex:1 1 0%;min-height:55px}
  .card-corpo > div:first-child > .moldura.led{flex:1 1 0%;min-height:41px}
  .moldura.luz .barra-luz{flex:1;min-height:20px}
  /* as cinco lâmpadas ficam CENTRADAS no que sobrar do campo. Elas medem 6px de
     altura: encostá-las no topo deixaria o resto do campo como um vazio com
     borda, que é a cara de bloco quebrado que esta casa já nomeou em 27/08. */
  .lampadas{flex:1;display:flex;align-items:center;justify-content:center}
  /* A COLUNA DOS SENSORES SÃO DOIS CAMPOS, E ERA UM. Ela guardava o L2/R2
     dentro da moldura do giroscópio, e a sobra da coluna virava um buraco só
     (181 px na mesa dela). Agora Giroscópio e Gatilhos são duas molduras
     irmãs, cada uma com rótulo, separadas pelos mesmos 9 px do par
     Touchpad/Barra de luz e do par Microfone/Alto-falante; a sobra entra POR
     DENTRO das duas, abrindo as linhas em vez de empoçar no meio.
     Medido em 29/08 com a mesa dela: maior vão da coluna 181 px -> 5 px.
     O ACELERÔMETRO NÃO É O TERCEIRO CAMPO, e não por desenho: o daemon dela
     não publica `accel` (`inputs` = buttons, gyro, l2_raw, lx, ly, r2_raw, rx,
     ry, speaker, touchpad, medido no `state_full` de agora). Desenhar o campo
     antes da leitura existir seria trocar um buraco por outro. */
  .card-corpo > div:last-child > .moldura{display:flex;flex-direction:column}
  /* TRÊS BLOCOS NA COLUNA, e não dois: o acelerômetro entrou em 30/08.
     Os pisos caem de 94/87 para 78/72/72 porque a altura do card não mudou —
     ela é a mesma nas dez abas (`--alt-janela`). Três eixos a 18px mais o
     rótulo cabem em 72; abaixo disso a barra some antes do número. */
  /* DOIS SENSORES NUMA MOLDURA. Os pisos saem da conta, não do gosto: o rótulo
     mede 17, cada sub-rótulo 13 e cada eixo 14 — 17 + 2*(13 + 3*14) = 127. Com os
     Gatilhos (72) e o vão de 9, a coluna pede 208 dos 232 que ela pode gastar. */
  /* O BLOCO DOS SENSORES PEDE A ALTURA QUE ELE TEM, e os Gatilhos absorvem a
     sobra. Com `flex:1 1 0%` nos dois o flex reparte a coluna em partes IGUAIS
     (111 e 111) — e os sensores precisam de 143. O resultado era o bloco
     cortado no meio do acelerômetro: ela viu e disse *"tá muito quebrado"*.
     `flex:0 0 auto` aqui, `flex:1 1 auto` nos Gatilhos: cada um pede o que
     precisa e quem estica é o que tem folga. */
  /* A CLASSE SE CHAMA `leituras`, E NÃO `sensores` — 31/08/2026, e é a cicatriz
     da linha 125 deste arquivo repetida dentro dele.
     `.sensores` JÁ EXISTIA aqui embaixo (o grupo do "Calibrar sensores da mesa",
     no cabeçalho do quadro) e traz `margin-left:auto`. Quando a moldura nova
     nasceu com esse nome, em 30/08, herdou a margem — e `margin-left:auto` num
     container `flex-direction:column` é margem no EIXO CRUZADO: ela DESLIGA o
     stretch. Medido no Chrome: a moldura parou de acompanhar a coluna (99px de
     largura em vez de 186) e foi empurrada 87px para a direita, desalinhada da
     dos Gatilhos, logo abaixo dela. Foi o que ela viu e chamou de quebrado.
     Nome de classe se confere no arquivo INTEIRO antes de escrever, não só no
     `topo.html`. */
  .card-corpo > div:last-child > .moldura.leituras{flex:0 0 auto}
  /* O EIXO ENCOLHE DE 18 PARA 16 SÓ AQUI, e é conta: a moldura tem 151px
     (os 232 da coluna menos os 72 dos Gatilhos e o vão de 9), e seis eixos a 18
     mais dois sub-rótulos e o rótulo pedem 158. Dois pixels por eixo fecham a
     conta sem tirar sensor nenhum — que é o que ela pediu ao autorizar o ajuste:
     *"desde que não percamos as features"*. A barra continua com 6px. */
  /* O EIXO APERTA A COLUNA DO NÚMERO SÓ AQUI: 46px em vez de 52, e o vão de 6 em
     vez de 8. O valor mais largo desta moldura tem sete caracteres monoespaçados
     ("−412.0" com o sinal), que medem 44px — os 52 eram folga. Os 10px que saem
     vão inteiros para a barrinha, que é o que se lê de longe. */
  .card-corpo > div:last-child > .moldura.leituras > .eixo{height:14px;flex:0 0 auto;
                                                           grid-template-columns:11px 46px 1fr;gap:6px}
  /* O `gap` DA MOLDURA VAI A ZERO AQUI, e é ELE que estourava o card.
     `.moldura` traz `gap:8px`, pensada para 3 ou 4 filhos. Esta tem DEZ (rótulo,
     dois sub-rótulos e seis eixos): nove vãos de 8 são **72px**, mais da metade
     do bloco — mais que os seis eixos somados. Com o gap em zero e o respiro
     posto só ONDE ELE SIGNIFICA (antes de cada sub-rótulo, que é onde um sensor
     acaba e o outro começa), o bloco cai de 228 para dentro dos 151 que a coluna
     tem. Medido no navegador, não estimado. */
  .card-corpo > div:last-child > .moldura.leituras{gap:0;padding:5px 9px}
  .card-corpo > div:last-child > .moldura.gatilhos{flex:1 1 auto;min-height:72px}
  /* o sub-rótulo de cada sensor: diz de qual dos dois são os três eixos abaixo,
     e a unidade — que é o que os separa (graus/s contra g). */
  .sub-sensor{font-size:10px;color:var(--rot-campo);font-weight:600;margin-top:3px;line-height:12px}
  .sub-sensor:first-of-type{margin-top:2px}
  .sub-sensor .mudo{font-weight:400}
  /* O PISO DO TOUCHPAD É A PROPORÇÃO DO SENSOR DE VERDADE. Ele era 118px de
     altura para 148 de largura — 1,25:1 — e o touchpad do DualSense é
     **1920x1080**, medido no `state_full` dela agora: 16:9, ou 83px para os
     mesmos 148. O desenho esticava a superfície 41% na vertical, e com ela a
     posição do dedo: um toque na metade da altura caía num lugar que não
     corresponde a lugar nenhum do aparelho. O produto desenha 16:9
     (`sensor_widgets._TOUCHPAD_PX = (76, 42)`).
     A PROPORÇÃO DEIXOU DE SER PISO E VIROU A REGRA. Ela era `min-height:83px`
     com `flex:1`, e o piso ficou: o touchpad virou a esponja da coluna e
     esticou de novo — medido em 29/08 na mesa dela, 148x203, que são **2,44
     vezes** o que o sensor é (83px para 148 de largura). A correção de 27/08
     tinha derrubado 41% de esticada e o `flex:1` devolveu 145%. Agora a
     superfície tem `aspect-ratio:16/9` e não estica em mesa nenhuma; quem
     absorve a sobra da coluna são a barra de luz e o LED do jogador, que são
     COR e LÂMPADA e não têm proporção a respeitar. */
  .moldura.touchp .touch{flex:0 0 auto;height:auto;aspect-ratio:16/9}
  .moldura > .sticks{display:grid;grid-template-columns:1fr 1fr;height:100%}
  /* rótulo no topo · círculo no centro · X/Y na base, que é onde as outras
     molduras terminam. O círculo NÃO cresce com a coluna — com aspect-ratio e
     flex:1 ele passava da largura e os dois se sobrepunham. */
  .moldura > .sticks > div{display:flex;flex-direction:column;justify-content:space-between}
  .moldura > .sticks .stick{flex:0 0 auto;align-self:center}
  .moldura > .sticks .xy{margin-top:0}
  .moldura > .glifos{height:100%;align-content:space-between}
  /* moldura SÓ onde o original põe */
  .moldura{border:1px solid var(--border-forte);border-radius:6px;background:var(--app-bg);padding:7px 9px}
  /* O RÓTULO DE LINHA TEM UMA COR SÓ NAS DEZ ABAS — 30/08/2026.
     Eu curei `.sec-rot` e assumi que era A classe de rótulo. São CINCO —
     `.sec-rot`, `.linha-rot`, `.rot`, `.stick-rot` e o `<th>` das tabelas — e ela
     viu o resultado: *"dá pra ver em todas as abas problemas que não foram
     corrigidos"*. A Jogar, a Controles, a Navegação, a Sistema e a Perfis
     ficaram com rótulo cinza ao lado de cinco abas com rótulo verde.
     `--rot-campo` é o dono; quem nomeia uma linha lê dele. */
  .rot{font-size:11.5px;font-weight:600;color:var(--rot-campo);margin-bottom:5px}
  .rot-linha{display:flex;align-items:center}
  /* O HEXADECIMAL FICA — decisão dela, 28/08: "fica nas duas", Controles e
     Iluminação. Ele já esteve aqui, saiu em 27/08 por escolha minha ("cru é para
     quem programa") e volta por escolha dela. O que ficou da minha razão é o
     `title`: o número é a cor DO JOGADOR, escolhida pelo produto, e não a do
     plástico. O nome da cor ("azul") continua fora, e por um motivo que não é
     gosto: ele não existe em código nenhum do produto — só num comentário —, e
     digitá-lo aqui criaria uma segunda verdade sobre a paleta. */
  .de-quem{margin-left:auto;font-size:10.5px;color:var(--texto-mudo)}
  /* O LED DO JOGADOR É CAMPO, NÃO LINHA. Ele nasceu em 28/08 como uma linha
     apertada DENTRO da moldura da Barra de luz — rótulo à esquerda, lâmpadas à
     direita — e ali ele era 13px espremidos num campo de 75. Em 29/08 virou a
     TERCEIRA moldura da coluna, com rótulo próprio: é o que come a sobra que o
     touchpad esticado escondia, e é o que faz a coluna fechar sem vão. */
  .rot .mudo{color:var(--texto-mudo);font-weight:400}
  .sob{font-size:10.5px;color:var(--texto-mudo);margin-top:4px}
  .touch{border-radius:4px;background:var(--panel);position:relative}
  /* O PONTO É POSICIONADO PELO CENTRO — ver o `translate` do `.stick .p` logo
     abaixo, que nasceu do mesmo defeito. Sem ele, `left`/`top` põem o CANTO do
     ponto de 8px na conta e o dedo lê 4px à direita e abaixo de onde está: em
     148px de superfície são 2,7% do curso, e no fim do curso (100%) o ponto
     saía inteiro para fora do pad. O produto centra: `ctx.arc(px, py, 3.5)`
     em `app/widgets/sensor_widgets.TouchpadView._on_draw`. */
  /* O PONTO NASCE APAGADO E A CLASSE `on` O ACENDE — decisão dela de
     02/09/2026: *"o pontinho do touchpad só aparece quando há toque — hoje ele
     aparece com `touching` falso, contra o que a própria dica promete"*. Ele
     era pintado pelo `style` do gerador (`opacity:0` só no card que o desenho
     queria vazio), e por isso ficava aceso na tela dela com o dedo fora do pad
     — fotografado em 02/09 às 19h, `touch-estado` dizendo "Sem toque" com o
     ponto ciano no lugar. A CLASSE é o único alvo do piloto que serve: os sete
     são texto·largura·fundo·valor·html·classe·cor, e `classe` é o único
     idempotente que liga e desliga (`hefesto_vivo.py:217-224`). */
  .touch .ponto{position:absolute;width:8px;height:8px;border-radius:50%;background:var(--cyan);
                box-shadow:0 0 8px var(--cyan);transform:translate(-50%,-50%);opacity:0}
  .touch .ponto.on{opacity:1}
  /* A COR DA BARRA DE LUZ É `currentColor`, e isso é o que a torna PINTÁVEL.
     Ela era `style="background:#7EB8D4"` do gerador — desenho cravado ao lado
     de um campo que já dizia a cor viva, e os dois se contradiziam na mesma
     moldura. O alvo `fundo` do piloto não serve, e isto está MEDIDO no
     WebKitGTK — o motor da janela dela —, numa `Gtk.OffscreenWindow` sobre
     esta página, em 02/09/2026. Os dois ramos, TRÊS escritas do mesmo
     `#0000FF`, o valor que o P1 dela publica:

         cor    [1, 0, 0]   e `el.style.color` volta `rgb(0, 0, 255)`
         fundo  [1, 1, 1]   e `el.style.background` volta `rgb(0, 0, 255)`

     O ramo `fundo` compara `el.style.background` com o que VAI escrever, e o
     CSSOM normaliza na atribuição: a comparação nunca casa e o contador de
     pintura soma +1 por tique, para sempre. O ramo `cor` escreve e DEPOIS
     compara, e é idempotente por construção. Daí o desvio: o produto escreve
     `color` e o `background` o segue — `getComputedStyle(..).backgroundColor`
     deu `rgb(0, 0, 255)` depois da escrita e `rgb(40, 42, 54)` (o `--panel`)
     depois do vazio, na mesma medição.

     FATO QUE ISTO DERRUBA: `pacotes/__init__.py:375-382` explica o `fundo`
     dizendo que o problema é o TRAVESSÃO (`background: "—"` é inválido). É
     verdade, e é MENOR que o defeito: uma cor perfeitamente VÁLIDA infla o
     contador do mesmo jeito.
     SEM COR DE LINHA o retângulo fica `--panel`, que é o "nada" que ela
     decidiu para todo campo sem informação. */
  .barra-luz{height:20px;border-radius:4px;background:currentColor;color:var(--panel)}
  /* os analógicos: grandes e SEM moldura, com a cruz de eixos dentro */
  .sticks{display:grid;grid-template-columns:1fr 1fr;gap:8px}
  /* o título do analógico é o único sem moldura, e por isso nascia 8px ACIMA dos
     outros três. O padding da moldura entra aqui como margem, e os quatro alinham. */
  .stick-rot{font-size:10.5px;font-weight:600;color:var(--rot-campo);text-align:center;line-height:1.3;
             padding-top:8px;margin-bottom:5px}
  /* O CÍRCULO, A CRUZ E O RÓTULO L3/R3 VÊM DE `--plastico`.
     Eram `var(--cosmic-red)` e dois `rgba(177,31,84,…)` digitados — e 177,31,84 é
     exatamente o `#b11f54` que a amostragem do aparelho derrubou. `color-mix`
     tira a translucidez da mesma variável, em vez de uma segunda cópia do hex. */
  .stick{width:100px;height:100px;border-radius:50%;border:2px solid var(--plastico);
         position:relative;margin:0 auto;display:flex;align-items:center;justify-content:center}
  .stick::before,.stick::after{content:'';position:absolute;
    background:color-mix(in srgb, var(--plastico) 30%, transparent)}
  .stick::before{left:50%;top:6px;bottom:6px;width:1px}
  .stick::after{top:50%;left:6px;right:6px;height:1px}
  .stick .rotl{font-family:'JetBrains Mono',monospace;font-size:26px;
               /* 42% dava 1,16:1 contra o fundo — a letra sumia. 72% a põe
                  visível sem virar rótulo: ela é marca-d'água DENTRO do
                  círculo, e quem nomeia o analógico é o texto acima dele. */
               color:color-mix(in srgb, var(--plastico) 72%, transparent)}
  /* A BOLINHA É POSICIONADA PELO CENTRO, e o `translate` é o que diz isso.
     DEFEITO MEDIDO EM 29/08: sem ele, `left`/`top` põem o CANTO da bolinha de
     9px na conta, e o repouso (128) nascia 4,69px abaixo e à direita da cruz —
     4,9% do curso de 96px, o mesmo que um analógico com +12,5 unidades presas
     em cada eixo, permanente. O curso ficava assimétrico: 2px de folga de um
     lado, 7px vazando para fora do círculo do outro. Depois da cura o desvio em
     repouso é 0,19px, que é a distância de 128 ao centro exato da faixa (127,5).
     Não é invenção: `.gat-linha .n` já usa `translateX(-50%)` pelo mesmo motivo,
     e o widget do produto desenha o ponto centrado. */
  .stick .p{position:absolute;width:9px;height:9px;border-radius:50%;background:var(--pink);z-index:2;
            transform:translate(-50%,-50%)}
  .xy{font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--texto-suave);
      text-align:center;margin-top:6px;line-height:1.5}
  .eixo{display:grid;grid-template-columns:11px 52px 1fr;align-items:center;gap:8px;
        font-family:'JetBrains Mono',monospace;font-size:10.5px;color:var(--texto-suave);height:18px}
  .eixo .g{height:6px;border-radius:3px;background:var(--panel);position:relative}
  /* A BARRA BIPOLAR SÃO DUAS METADES, e a razão é o que o produto ALCANÇA.
     Ela era UM `<span class="v" style="left:L%;width:W%;background:C">`, e os
     três valores mudam com a leitura: o `escrever` do piloto sabe escrever
     `width` (alvo `largura`) e `color` (alvo `cor`), e NÃO tem alvo de
     POSIÇÃO. Com um elemento só, dar-lhe endereço pintaria a largura sobre um
     `left` congelado — a barra de um eixo NEGATIVO cresceria para o lado
     errado, que é pior que a barra parada.

     A GEOMETRIA É A MESMA, e isso é conta, não gosto: `mesa_viva._barra_bipolar`
     devolve `esquerda = 50 - largura` para todo valor negativo, ou seja a barra
     negativa SEMPRE termina no centro. Uma metade ancorada em `right:50%` e
     outra em `left:50%` desenham exatamente os mesmos pixels, e só uma delas
     tem largura por vez.

     A COR SOBE PARA O TRILHO (`.g`) e desce por `currentColor`: assim o cinza
     do repouso, o verde e o vermelho continuam sendo a resposta de
     `_barra_bipolar` — um valor só, num elemento só, em vez de repetido nas
     duas metades. */
  .eixo .v{position:absolute;top:0;bottom:0;border-radius:3px;background:currentColor}
  .eixo .v.neg{right:50%}
  .eixo .v.pos{left:50%}
  /* AS ONDAS SONORAS — o medidor de nível que a minha primeira versão comeu */
  .onda{height:22px;display:flex;align-items:flex-end;gap:2px;margin-bottom:5px}
  .onda i{flex:1;background:var(--cyan);border-radius:1px;display:block;opacity:.85}
  .onda.mudo i{background:var(--border-forte);opacity:.5}
  .selo-ativo{font-size:9.5px;font-family:'JetBrains Mono',monospace;padding:1px 6px;border-radius:3px;
              background:var(--green);color:var(--app-bg);font-weight:600}
  /* 3,47:1 sobre o próprio fundo -> 9,3:1. O selo continua dizendo
     "desligado" pelo FUNDO cinza, que é o sinal; o texto passa a ser lido. */
  .selo-ativo.off{background:var(--border-forte);color:var(--texto-suave)}
  .vol{display:flex;align-items:center;gap:8px;height:22px}
  .vol .trilho{flex:1;height:5px;border-radius:3px;background:var(--panel);position:relative}
  .vol .cheio{position:absolute;left:0;top:0;bottom:0;border-radius:3px;background:var(--purple)}
  .vol .cheio::after{content:'';position:absolute;right:-5px;top:-4px;width:12px;height:12px;
    border-radius:50%;background:var(--purple);border:2px solid var(--app-bg)}
  .vol .n{flex:0 0 30px;text-align:right;font-family:'JetBrains Mono',monospace;
          font-size:10.5px;color:var(--fg)}
  /* O 🎙 E O ♪ SÃO `<button>`, E NÃO ERAM (29/08/2026). Eram `<span>` com
     `cursor:pointer` e nada atrás: nem `data-*` para a ponte achar, nem ouvinte
     para o clique cair em algum lugar. Medido — dois cliques sintéticos neles
     produziram ZERO gestos, enquanto os botões de rota, ao lado, ecoavam. O
     `cursor:pointer` prometia o que a página não tinha, e a régua do
     `--prova-gesto` dava verde porque nunca os tocava.
     `font-family:inherit` é o preço de virar botão: sem ele o navegador põe a
     fonte dele e o glifo encolhe. */
  .mudo-i{width:22px;height:22px;flex:0 0 22px;border-radius:5px;cursor:pointer;
          border:1px solid var(--border-forte);background:var(--panel);color:var(--texto-mudo);
          font-size:10px;line-height:20px;text-align:center;padding:0;font-family:inherit}
  .mudo-i.on{border-color:var(--red);color:var(--red);background:rgba(255,85,85,.1)}
  /* SEM POSSE, SEM GESTO. `speaker.set {muted}` é RECUSADO pelo daemon enquanto
     o volume do controle for desconhecido (`ipc_handlers.py`). Um botão que a
     tela oferece e o produto recusa é a mentira que esta aba existe para não
     contar: ele apaga e para de responder ao clique. */
  .mudo-i[disabled]{opacity:.4;cursor:not-allowed}
  /* O `.solta` — o botão "Liberar" do microfone — SAIU em 31/08/2026, por
     decisão dela, e a regra de estilo saiu junto: CSS de elemento que ninguém
     mais escreve é promessa esperando alguém tropeçar nela. A história inteira
     (o fato errado que custou o botão, e o preço de não ter volta nesta tela)
     está na lápide de `tests/unit/test_regua_de_tela_a_aba_controles.py`. */
  /* O MODO DO MIC é o `.rota` em miniatura: mesma gramática (fileira de
     escolha exclusiva, um aceso), altura de RÓTULO em vez de altura de
     escolha, porque ele divide a linha com o nome do bloco. */
  /* O VÃO E O RECUO SÃO OS MENORES QUE AINDA SEPARAM — 2px entre os três botões
     e 5px de cada lado do texto. Com os 3 e 7 que eles tinham, a fileira media  (noqa-acento: verbo medir, imperfeito)
     164px e a linha do rótulo pedia 292 numa moldura de 242: os 50px de
     diferença eram o "Nativo" e metade do "Desativado" pintados fora da caixa,
     por cima do bloco dos sensores. Aqui a fileira mede 150 e cabe com folga. */
  /* O `.mic-modo` HERDA A `.rota` INTEIRA e não acrescenta nada — 31/08/2026,
     quando ela mandou os dois descerem *"igual o Sons do Jogo e Todo o som do
     PC"*. O seletor fica no HTML (`class="rota mic-modo"`) para dizer QUAL
     fileira é esta, mas de estilo ele não tem UMA linha própria: dois blocos
     que fazem o mesmo gesto na mesma coluna têm de ser o mesmo botão, e uma
     regra a mais aqui é como as duas alturas voltam.
     As 5 linhas de pastilha de 17px que moravam aqui saíram junto. */
  /* O `data-campo` DO CONTAINER SAIU DAQUI EM 01/09/2026, e ele APAGAVA os dois
     botões. (O nome dele não se escreve por extenso nesta linha: a régua do
     casamento acha `data-campo` por expressão regular e NÃO tira comentário,
     então um endereço citado aqui entraria na conta como se a página o tivesse.)
     Esta linha dizia que "a ponte viva endereça por ele" — endereçava
     mesmo, e o preço está medido: o `escrever` do piloto faz
     `el.textContent = t`, e o `t` de um valor vazio é `—`. Como o
     `data-campo` estava no `<span>` que ENVOLVE Virtual e Nativo, o primeiro
     tique da pintura trocava os dois botões por um travessão.
     Medido no Chrome headless sobre a página publicada: `[data-mic-modo]`
     antes 4, depois 0, nos dois valores que o pacote emitia (`''` e
     `'sem posse'`). Endereço de pintura só pode morar em FOLHA — um container
     endereçado é um container que some. */
  /* 30px, E NÃO OS 36 DE `--h-escolha` — 31/08/2026, e o número é o preço do
     pedido dela. Até hoje a coluna do som tinha UMA fileira de escolha (a rota
     do alto-falante); com os modos do microfone descendo *"igual o Sons do Jogo"*
     ela passou a ter DUAS, e a coluna foi de 236 para 269px. O card foi junto,
     de 308 para 341, contra os 328 que a caixa reserva: 13px a mais, e o P4
     saindo da tela.
     Medido: 6px por fileira em duas fileiras, mais 1px de margem em cada, dão
     os 14 que faltavam. Não é altura inventada — é a mesma faixa do chip da
     fita (28 a 30px) que esta aba já usa no `.mascara .chip`, e as duas
     fileiras continuam IGUAIS entre si, que é o que ela pediu. */
  .rota{display:flex;gap:5px;margin-top:5px}
  .rota button{flex:1;height:30px;border-radius:5px;font-size:10.5px;white-space:nowrap;font-family:inherit;
    border:1px solid var(--border-forte);background:var(--panel);color:var(--texto-mudo);cursor:pointer}
  .rota button.on{border-color:var(--purple);background:var(--sel-bg);color:var(--fg);font-weight:600}
  /* os 16 glifos: grandes, SOLTOS (sem caixa) e coloridos por identidade.
     UMA REGRA PARA OS QUATRO: `plast` é a cor do plástico (a variável do card) e
     `on` é a cor de "acendeu agora". Antes havia um par de regras por modelo
     (`.card.c-blue .gb.on`), e nele o azul pintava o aceso da MESMA cor do
     plástico — as duas informações ficavam indistinguíveis no card azul. */
  .glifos{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;justify-items:stretch}
  .gb{width:100%;height:100%;min-height:46px;display:flex;align-items:center;
      justify-content:center;color:var(--texto-suave)}
  .gb.plast{color:var(--plastico)}
  .gb.on{color:var(--pink);filter:drop-shadow(0 0 6px rgba(255,121,198,.55))}
  /* O QUE FICA NO TOPO DO QUADRO É O GESTO DE MESA, E SÓ ELE.
     Decisão dela, 28/08 (`D-CALIBRAR-SENSORES-CALIBRA-A-MESA-INTEIRA`): *"se
     conseguirmos fazer funcionar poderíamos deixar ele lá e ele mapearia os 4
     controles ao mesmo tempo"*. Os dois interruptores desceram para a linha de
     cada controle — são estado POR PEÇA —, e aqui em cima sobrou o Calibrar,
     que é o único que vale para a mesa toda.
     A GRADE DE LARGURA IGUAL DESCEU JUNTO: com um botão só, `grid-auto-columns`
     não iguala nada. Ela agora está no `.sensores-peca`, que é onde há dois. */
  .sensores{display:flex;gap:8px;margin-left:auto}
  /* OS DOIS INTERRUPTORES, DENTRO DA LINHA DE CADA CONTROLE.
     A ALTURA NÃO PODE SER `--h-acao`, e o número diz por quê: a linha fechada
     tem 34px por fora e 30px por dentro (as duas bordas de 2px do `.ctl`), e um
     botão de 34 não cabe em 30. Crescer a linha também não é saída — a conta do
     `PARA_O_CARD` lá embaixo já fecha sem sobra, e 3 linhas 6px mais altas
     roubariam 18px do card aberto, que tem 7. Os 26px daqui não inventam uma
     quinta altura na janela: são a mesma pastilha da FITA lá em cima (o chip
     mede 28 a 30px) e do `perfil-ativo` (29px) — a gramática de "pastilha" desta
     casa, que é o que estes dois são, e não botão de decidir.
     A LARGURA IGUAL É A GRADE, não o comprimento do rótulo: `grid-auto-flow:
     column` com `grid-auto-columns:1fr` dá às duas colunas o tamanho da maior.
     Como o par é o MESMO nas quatro linhas, o grupo tem a mesma largura nas
     quatro — e é isso que faz os oito botões nascerem no mesmo x, abertos ou
     fechados. O `margin-left:auto` é dele agora, e saiu do `.bat`: com os dois
     pedindo o vão, o flex partiria a sobra ao meio e o grupo flutuaria em
     quatro lugares diferentes. */
  .sensores-peca{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;
                 gap:8px;margin-left:auto}
  .sensores-peca .sw{
    height:26px;border-radius:6px;font-size:10.5px;font-family:inherit;cursor:pointer;

    border:1px solid var(--green);background:rgba(80,250,123,.09);color:var(--green);
    display:inline-flex;align-items:center;justify-content:center;gap:6px;padding:0 10px;
  }
  .sensores-peca .sw .p{width:6px;height:6px;border-radius:50%;background:var(--green);
                        box-shadow:0 0 6px var(--green)}
  .sensores-peca .sw.off{border-color:var(--border-forte);background:var(--app-bg);color:var(--texto-mudo)}
  .sensores-peca .sw.off .p{background:var(--border-forte);box-shadow:none}
"""

# ---------------------------------------------------------------------------
# OS ENDEREÇOS `data-*`, PARA A ABA RECEBER DADO VIVO (29/08/2026).
#
# NENHUM PIXEL MUDA: são atributos, e atributo não desenha. O que eles mudam é
# quem consegue achar um valor na página — a ponte `WebKit2` escreve por
# `[data-controle="…"] [data-eixo="giro-x"]`, e não por `.ctl:nth-child(3) .eixo`.
#
# A convenção NÃO é nova: é a que a 01-jogar já usa no desenho do controle
# (`data-entrada`, `data-feature`, `data-controle`, `data-colorway`, 148 deles).
# Um segundo vocabulário aqui seria a segunda verdade que esta casa mata.
#
# POR QUE NÃO BASTAVA O SELETOR ESTRUTURAL: foi assim que a fita viva morreu sem
# sintoma em 27/08 — o `fita_clicavel` deste arquivo carrega essa cicatriz por
# extenso. Um `nth-child` acerta a caixa errada em silêncio no dia em que um
# controle entra ou sai; um `data-controle` com o endereço do aparelho, não.
#
# São nove nomes, e só onde a CLASSE sozinha é ambígua dentro do card:
#   data-controle  no `.ctl`   — o `uniq` do aparelho, a chave estável do card
#   data-glifo     nos 16 `.gb`         data-eixo    nos 3 `.eixo` (giro-x … giro-z)
#   data-stick / data-xy  nos analógicos    data-gatilho nas duas linhas de L2/R2
#   data-bloco     nas duas molduras de som (microfone · alto-falante)
#   data-rota      nos dois botões de rota     data-sensor  nos dois interruptores
#   data-campo     nos leitores soltos (mascara, mic-selo, alto-estado, l3/r3)
#
# O `data-gesto` ENTROU EM 01/09/2026, e ele NÃO substitui os de cima — cada um
# responde uma pergunta diferente do mesmo clique:
#
#   data-gesto="mudo" · data-mudo="microfone"   QUEM atende · SOBRE O QUÊ
#
# A razão é medida no piloto: `hefesto_vivo.py:202` monta o nome do gesto como
# `d.gesto || d.hefGesto || d.papel || 'clique'`. Um botão marcado só com
# `data-mudo` chega ao despachante chamando-se **`clique`** — os oito botões de
# som e sensor da aba disputariam UM nome, e o gesto teria de adivinhar qual
# deles foi pelo texto. O `data-gesto` é o endereço de QUEM atende; o
# `data-mudo`/`data-rota` continua sendo o argumento, e é por isso que os dois
# ficam.
#
# E TRÊS PARES CONTINUAM SEM `data-gesto`, DE PROPÓSITO — os dois interruptores
# de sensor e os dois modos do microfone. Não é esquecimento: o daemon não
# atende nenhum dos dois (não há método de sensor nos 39 do `ipc_server`, e o
# modo Virtual/Nativo é a `ONDA-CONEXOES-06`, que ainda não existe em código).
# Sem `data-gesto` eles caem no `clique`, que não tem dono, e o piloto os RECUSA
# dizendo o nome. Marcá-los seria a mentira que esta casa persegue: o botão que
# responde calado, e quem clicou conclui que funcionou.
# ---------------------------------------------------------------------------
GL16 = [("cross","✕"),("circle","○"),("square","□"),("triangle","△"),
        ("dpad_up","↑"),("dpad_down","↓"),("dpad_left","←"),("dpad_right","→"),
        ("l1","L1"),("r1","R1"),("l2","L2"),("r2","R2"),
        ("share","<"),("options","≡"),("ps","PS"),("touchpad","···")]

NA_COR_DA_PECA = {"cross", "l2", "r2"}   # os que o original pinta na cor do plástico

# A TAXA DO GIROSCÓPIO É DO TRANSPORTE, e vinha DIGITADA — "~194 Hz", igual nos
# dois cards, cabo e rádio. A canônica
# (`docs/protocol/dualsense-referencia-canonica.md`, §5) mede outra coisa, e o
# número 194 não aparece em lugar nenhum dela. Com dois USB e dois BT na mesa a
# mentira ficaria escrita quatro vezes. O mapa responde POR TRANSPORTE — é o
# contrato do `docs/data/mapa-controles.csv` —, e é assim que ela nasce aqui.
#
# ELA ERA UM PAR (rótulo curto, explicação) porque o rótulo ia PARA A TELA, na
# leitura `Giroscópio 250 Hz`. A leitura saiu em 28/08, por decisão dela, e o
# rótulo curto ficou sem leitor: sobrou a explicação, que desce para o `title` do
# interruptor de giroscópio daquele controle (ver `sensores_da_peca`).
TAXA_DO_GIRO = {
    "USB": "No cabo são 250,0 Hz exatos, e três fontes independentes concordam: "
           "o relógio do host, o relógio do controle e o descritor USB "
           "(bInterval = 6).",
    "BT":  "No rádio não há taxa típica. Medido em cinco janelas de 8 a 10 s no "
           "mesmo controle: a média foi de 38 a 392 Hz entre janelas "
           "consecutivas, sem que nada mudasse. Os 1000 Hz que o SDL declara "
           "para Bluetooth não aparecem em janela nenhuma.",
}


def num(v):
    """O NÚMERO NA VÍRGULA, que é como esta janela escreve.

    O f-string do Python escreve ponto, e a legenda já dizia "13,7 px" e "115,8"
    à mão duas linhas adiante: medida nova interpolada saía `246.6` no meio de
    uma frase em português, com as duas grafias na mesma tela.
    """
    return f"{v:.1f}".replace(".", ",").removesuffix(",0")


def grade(apertados):
    def um(n):
        c = " on" if n in apertados else (" plast" if n in NA_COR_DA_PECA else "")
        # SEM `title=` AQUI. O nome da peça sai do `<title>` que o `glifo()`
        # escreve DENTRO do <svg>, derivado de `pecas-do-dualsense.csv`. Um
        # `title=` neste span era a segunda verdade: o span mede 42x46 e o svg
        # 38x38, então sobrava um anel de 2px de lado onde o tooltip do span
        # aparecia — e ele dizia `cross`, `dpad_up`, em inglês minúsculo.
        # Medido em 28/08: 64 glifos, 64 tooltips ingleses no anel.
        # O ENDEREÇO DO GLIFO — 03/09/2026, e ele é o maior buraco desta aba.
        # `data-glifo` é o vocabulário do DESENHO (o CSS e a régua de peças o
        # leem) e o piloto único não o lê: ele procura `data-campo`,
        # `data-papel` e `data-hef` (`hefesto_vivo.BOOTSTRAP::achar`). Sem um
        # `data-campo` aqui, os dezesseis glifos ficam com a classe `on` que
        # ESTA função escreveu — e no card do P1 do desenho são três
        # (`cross`, `dpad_up`, `l2`). A tela afirmava três botões apertados
        # para sempre, com o controle parado na mesa.
        #
        # O ALVO É `classe`, que é o que o glifo aceso É: `.gb.on` já existe no
        # CSS desta página, e o `escrever` acende/apaga a classe pelo valor
        # (`hefesto_vivo.py`, ramo `classe`). Sem `data-hef-quando` ele é
        # BOOLEANO — cada glifo decide por si, que é exatamente o contrato do
        # `_refresh_glyphs` da GTK (`efetivos[nome] = nome in buttons_pressed`).
        return (f'            <span class="gb{c}" data-glifo="{n}"'
                f' data-campo="glifo-{n}" data-hef-alvo="classe">'
                f'{glifo(n, ativo=False, tam=38)}</span>')
    return "\n".join(um(n) for n, _ in GL16)

def onda(vals, mudo=False):
    """O medidor de nível. Piso de 16%: com o microfone mudo os valores caem a 4-6%
    e as barras somem — o bloco lia como quebrado ao lado do card cheio. Silêncio
    é uma linha baixa e visível, não a ausência do desenho."""
    return ('<span class="onda' + (' mudo' if mudo else '') + '">'
            + "".join(f'<i style="height:{max(v, 16)}%"></i>' for v in vals) + '</span>')

def pos(v):
    """0-255 -> posição em % dentro do círculo. 128 é o centro."""
    return round(v / 255 * 100, 1)

def luz_do_jogador(c):
    """A cor da barra de luz, VINDA DO PRODUTO.

    Era um hex digitado por card (`#ff2d6f`, `#3ba7e8`), e o produto tem a tabela
    canônica de cor por jogador em `core/led_control.py::player_slot_color` — a
    mesma que `monta.PADRAO_JOGADOR` já usa para as cinco lâmpadas. Digitar aqui
    seria inventar uma segunda verdade sobre o que o produto acende.
    """
    return tom_da_casa("#%02X%02X%02X" % player_slot_color(c["jogador"]))


# O TOUCHPAD PRECISA DIZER ALGO QUANDO NINGUÉM ESTÁ TOCANDO, e era isto que
# faltava. Medido em 29/08: 238 leituras dos dois controles dela, `touching`
# verdadeiro em ZERO delas — a superfície de 148x83 mostrava um ponto invisível
# em 238 de 238 amostras, e um retângulo que nunca mostra nada lê como quebrado.
# O rótulo é o do produto (`sensor_widgets`: "Sem toque" / "N toque"), no mesmo
# canto onde a moldura de baixo já põe o hexadecimal.
DICA_TOQUE = ("O ponto marca onde o dedo está. Sem toque não há ponto — o DualSense "
              "só publica posição enquanto alguém encosta na superfície.")

# AS CINCO LÂMPADAS SÃO DERIVADAS, E ISSO PRECISA ESTAR DITO. O `state_full`
# publica o `player_slot` e NÃO publica `player_leds`: o padrão desenhado sai de
# `core/led_control.py::player_led_pattern(slot)` — a mesma função com que o
# produto acende —, e não de uma leitura do aparelho. O perfil TEM o campo
# (`profiles/schema.py`, cinco booleanos) e o daemon o aplica, logo o aceso pode
# divergir do derivado e a tela não teria como saber. O vizinho de cima é o
# contrário: a barra de luz é LIDA (`lightbar_rgb`, `lightbar_source:"sysfs"`).
DICA_LED_JOGADOR = ("As cinco lâmpadas do controle, no padrão do jogador "
                    "(1 no meio para o P1, as das pontas para o P2, e assim por "
                    "diante). É DERIVADO do número do jogador, não lido do "
                    "aparelho — o daemon publica o número, não o que está aceso.")

DE_QUEM_E_A_LUZ = ("Este é o código da cor do JOGADOR, não a do plástico — quem escolhe "
                   "é o produto, pela mesma tabela que acende as cinco lâmpadas "
                   "(core/led_control.py::player_slot_color). Ele não é digitado aqui: "
                   "sai da tabela, e muda no dia em que ela mudar.")

# O QUE A LINHA DIZ SOBRE A MÁSCARA, e o que ela NÃO diz. Decisão dela, 28/08:
# a máscara é por controle e mora na aba Jogar, com três opções e SEM aviso.
# Esta aba lê — e o `title` diz onde se muda, que é a única coisa que faltava
# a quem chega aqui procurando o seletor.
DE_ONDE_VEM_A_MASCARA = ("O que o jogo vê deste controle. A escolha é por controle e "
                         "mora na aba Jogar — DualSense, Xbox 360 ou Nintendo Pro. "
                         "Aqui é leitura.")

ABRE_O_CARD = ("Clique para abrir o card deste controle — os outros fecham. "
               "É o mesmo gesto de escolhê-lo na fita lá em cima.")


def sensores_da_peca(c):
    """OS DOIS INTERRUPTORES DE SENSOR, UM PAR POR CONTROLE.

    Decisão dela, 28/08 (`D-CALIBRAR-SENSORES-CALIBRA-A-MESA-INTEIRA`): *"se
    conseguirmos fazer funcionar poderíamos deixar ele lá e ele mapearia os 4
    controles ao mesmo tempo"*. Eles estavam no topo do quadro, GLOBAIS, ao lado
    do Calibrar — e giroscópio ligado é estado de UMA peça, não da mesa: com
    quatro controles, um interruptor global mente sobre três deles. O Calibrar
    ficou lá em cima, porque esse é gesto de mesa mesmo.

    A TAXA DO GIROSCÓPIO VIVE AQUI AGORA. Ela era uma LEITURA na linha
    (`Giroscópio 250 Hz`), e a leitura saiu — decisão dela no mesmo turno:
    *"se der problema de espaço remover Giroscópio, Hefesto e vê como (na real
    remove eles)"*. O número é medido e responde por transporte, então ele desce
    para o `title` do interruptor do mesmo controle: nada a mais na tela, e a
    medição não vira lápide. Quem a quiser por extenso tem a canônica
    (`docs/protocol/dualsense-referencia-canonica.md`, §5).
    """
    hz_por_que = TAXA_DO_GIRO[c["via"]]
    return f'''          <span class="sensores-peca">
            <button class="sw" data-sensor="giroscopio" title="Ligado: o jogo recebe o giro deste controle. {hz_por_que}"><span class="p"></span>Giroscópio</button>
            <button class="sw" data-sensor="acelerometro" title="Ligado: o jogo recebe a inclinação e o chacoalhar deste controle."><span class="p"></span>Acelerômetro</button>
          </span>'''


def identidade(c, *, bat, meio=""):
    """A LINHA DE IDENTIDADE, e ela é UMA SÓ.

    Sai daqui a linha das quatro caixas — a do controle aberto e a dos fechados,
    que agora são o MESMO elemento. `meio` é o que só a linha fechada mostra: o
    estado que ela resume porque o card aberto mostra por extenso.

    O RÓTULO SAI DE `monta.rotulo(c)`, e a MÁSCARA de `c["mascara"]`. Os dois
    eram montados/digitados aqui, e os dois já tinham divergido:
      · o rótulo vinha partido em dois `<span>` com o mesmo separador do chip por
        COINCIDÊNCIA, não por construção — a quinta gramática da mesma janela;
      · a máscara vinha do dicionário `ESTADO` deste arquivo, uma segunda cópia
        da que a Jogar mostra. Medido em 28/08: a Jogar dizia que o P2 era
        DualSense e o P3 Xbox 360, e esta aba dizia o contrário, **na mesma
        sessão**. Não é o valor que se corrige — é o segundo lugar que some.
    A caixa alta, se um dia ela a quiser, é `text-transform` no `.card-nome`:
    escrever em maiúscula no HTML tira de quem lê a chance de copiar o nome do
    plástico.

    O QUE SAIU DAQUI EM 28/08, E POR QUE SÓ DUAS DAS TRÊS QUE ELA CITOU.
    Palavra dela: *"se der problema de espaço remover Giroscópio, Hefesto e vê
    como (na real remove eles)"* — e o espaço apertou mesmo, porque os dois
    interruptores de sensor desceram para esta linha. Saíram as duas LEITURAS:
    `Hefesto on` (71px, e dizia a mesma coisa nas quatro linhas) e
    `Giroscópio NNN Hz` (114,6px no cabo, 148,1 no rádio — o número vive agora
    no `title` do interruptor, ver `sensores_da_peca`).
    O `vê como` FICOU, e a razão não é gosto: a decisão dela do dia anterior,
    registrada em `resumo_fechado`, diz que *"a linha fechada mantém o resumo de
    hoje — máscara, microfone, bateria"*, e máscara é justamente o `vê como`.
    São duas frases dela em sentidos opostos; quem executa RELATA em vez de
    escolher calado — e a conta dispensou a escolha: sem as duas leituras os dois
    botões couberam com folga em todas as linhas, com o número na legenda.
    E o que ENTROU não é o que ela mandou tirar: o que sai é a LEITURA
    `Giroscópio 250 Hz`, o que entra é o INTERRUPTOR de giroscópio. São coisas
    diferentes com a mesma palavra, e confundi-las apaga o que ela acabou de
    pedir.

    E A FORMA É A `curta`, não a `completa`, por duas razões que apontam para o
    mesmo lado:
      1) É A DECISÃO DELA. O `topo.html` a registra: a ordem nasceu em 26/08 com
         a marca na frente e ela a tirou em 27/08 — *"tira o Sony das outras
         abas também"* —, porque a marca se repetia em cada card e em cada chip
         sem separar um controle do outro. `player • plástico • transporte` é o
         que resta, e é o mesmo texto do chip da fita.
      2) AQUI APERTA, e o número diz quanto. Esta linha é a mais cheia da aba:
         nome · vê como · microfone · os dois sensores · bateria. Medido
         em 28/08 na janela da régua (1260), a linha FECHADA do P3 — o nome mais
         longo da mesa, `Galactic Purple` — passava da moldura por **1px** com a
         forma completa. Um pixel de folga não é folga: bastou o rótulo virar uma
         fonte só, sem a metade esmaecida que o encolhia, para a barra de bateria
         vazar **4,3px** e a régua reprovar. Com a curta sobram ~101px, que é o
         que aguenta um plástico de nome mais comprido — e o CSV tem 28.
    """
    # O NOME DO PLÁSTICO E O TRANSPORTE GANHARAM ENDEREÇO — 03/09/2026, e a lei é
    # dela: *"se no topo tá mostrando controle white player 1, então cada aba vai
    # usar os controles lá de cima. Não mistura com a info dos mockups."*
    #
    # O QUE ESTAVA ERRADO NA TELA, e ela viu com três centímetros entre uma coisa
    # e outra: a fita do topo dizia `P1 · White · USB` e este cabeçalho dizia
    # `Cosmic Red · USB` — o desenho, congelado, num `<span>` sem endereço nenhum.
    # O pacote desta aba já tinha o transporte na mão e o JOGOU FORA por não ter
    # onde pô-lo (`a02_controles.py`, o bloco do `via`: *"Dar-lhe endereço é
    # partir aquele `<span>` em três, que é desenho — logo, decisão dela"*). A
    # decisão veio, e é a lei acima.
    #
    # A ORDEM CONTINUA SENDO DE `monta.rotulo`, e é por isso que os dois
    # endereços entram DENTRO do `c` em vez de a junção ser refeita aqui: o
    # separador e a sequência têm um dono só, e escrevê-los de novo neste arquivo
    # seria a sexta gramática da mesma janela — a cicatriz que `rotulo()` existe
    # para não repetir.
    com_endereco = {
        **c,
        "nome": f'<span data-campo="peca">{c["nome"]}</span>',
        "via": f'<span data-campo="via">{c["via"]}</span>',
    }
    return f'''          <span class="card-nome"><span class="so-fechado">P{c["jogador"]}{SEPARADOR}</span>{rotulo(com_endereco, "peca")}</span>
          <span class="div">·</span>
          <!-- SAI O TEXTO "vê como"; O NOME DA MÁSCARA FICA — decisão dela,
               31/08/2026, em duas frases: *"remover o vê como de todos os
               controles"* e, na correção logo em seguida, *"era o texto Vê como
               mas o nome da máscara fica"*.

               A PRIMEIRA VOLTA TIROU O SPAN INTEIRO e levou a máscara junto —
               era ler o pedido pela metade. O que sobra aqui é o dado: o nome
               que o jogo vê, com o `data-campo="mascara"` intacto, que é o
               endereço por onde a ponte viva o pinta. Tirar o endereço junto
               teria quebrado a pintura sem uma linha de aviso.

               O `title` FICA no lugar do texto: quem quiser saber de onde vem a
               máscara passa o mouse. É a mesma economia que ela mandou fazer nos
               tooltips do resto da janela — o rótulo sai, a explicação continua
               alcançável. -->
          <span class="leia" title="{DE_ONDE_VEM_A_MASCARA}"><b data-campo="mascara">{c["mascara"]}</b></span>{meio}
{sensores_da_peca(c)}
          <!-- A BATERIA GANHOU ENDEREÇO EM 01/09/2026, e até aqui ela era a
               PINTURA DO MOCKUP para sempre: o pacote da aba emite `bateria`
               desde que nasceu, e não havia um `data-campo` onde ele caísse —
               a régua do casamento a listava entre os órfãos. O número e a
               barra ficavam nos 100% / 64% que este gerador desenhou, com o
               controle dela em qualquer carga.
               SÃO DOIS ENDEREÇOS PORQUE SÃO DUAS COISAS: o `.n` recebe TEXTO
               ("95%", ou "—" quando o daemon não sabe) e o `.cheio` recebe
               LARGURA, pelo `data-hef-alvo="largura"` que o `escrever` do
               piloto lê (`hefesto_vivo.py:107`). Um endereço só escreveria o
               número DENTRO da barra. -->
          <span class="bat">Bateria
            <span class="trilho"><span class="cheio" data-campo="bateria-barra"
              data-hef-alvo="largura" style="width:{bat}%"></span></span>
            <span class="n" data-campo="bateria">{bat}%</span></span>'''


def resumo_fechado(mic_mudo):
    """O QUE A LINHA FECHADA ACRESCENTA, e é um só: o microfone.

    Decisão dela, 28/08: "a linha fechada mantém o resumo de hoje — máscara,
    microfone, bateria". A máscara e a bateria já estão na identidade, que é a
    mesma nas duas formas; o microfone é o único que o card aberto mostra por
    extenso e a linha fechada precisa resumir. Ele some quando o card abre —
    repetir ali seria dizer duas vezes a mesma coisa, uma delas pior.

    A barra de luz esteve aqui e SAIU: ela acende na cor do jogador, e o número
    do jogador é a segunda palavra da linha. Era o único item que não dizia nada
    que a linha já não dissesse, e custava ~100px da largura da bateria.
    """
    selo = "MUDO" if mic_mudo else "ATIVO"
    porque = ("Calado no firmware do controle — a luz vermelha do plástico está apagada."
              if mic_mudo else "Capturando: o som que entra por este controle chega ao PC.")
    return (f'<span class="div so-fechado">·</span>\n'
            f'          <span class="leia so-fechado" title="{porque}">Microfone '
            f'<span class="selo-ativo{" off" if mic_mudo else ""}" data-campo="mic-selo">'
            f'{selo}</span></span>')


# OS DOIS TEXTOS DOS BOTÕES DE SOM, e cada um diz o PREÇO do clique — que é o
# que a dica antiga escondia. Ela dizia que o 🎙 "é o mesmo que apertar o botão
# do controle", e não é: o produto mede o contrário
# (`app/widgets/controller_card.py`), e clicar aqui faz o Hefesto ASSUMIR o
# registrador.
#
# ERAM TRÊS, E A DICA DO 🎙 CONTINUOU MANDANDO CLICAR NUM BOTÃO QUE NÃO EXISTE.
# Ela terminava em "até você clicar em Liberar" — e o `Liberar` saiu da tela em
# 31/08/2026, por decisão dela. Uma dica que manda a pessoa procurar um botão
# ausente é o mesmo defeito que esta aba persegue, só que dentro do produto e
# não da legenda: quem lesse ia varrer o card atrás de uma saída que não está
# desenhada. O preço é REAL e continua de pé — o que muda é dizer para onde ele
# manda de verdade. (`DICA_MIC_LIBERAR` saiu junto: era o terceiro lugar deste
# arquivo a descrever o botão.)
DICA_MIC_MUDO = ("Calar no firmware do controle — apaga a luz vermelha do plástico. "
                 "A partir daqui quem manda no mudo é o Hefesto, e o botão do "
                 "controle para de valer. Esta tela não devolve o comando: a volta é "
                 "pela janela do aplicativo ou reiniciando o Hefesto.")
DICA_ALTO_MUDO = "Manda zero ao alto-falante do controle, sem perder o volume guardado."
DICA_ALTO_SEM_POSSE = ("Apagado porque o volume deste alto-falante ainda é desconhecido: "
                       "o DualSense não o publica, e o daemon recusa calar sem ele.")

# ---------------------------------------------------------------------------
# OS QUATRO BOTÕES QUE DIZIAM "ESTE É O ESCOLHIDO" SEM LER NADA — 03/09/2026
# ---------------------------------------------------------------------------
# São os dois da rota do alto-falante (`Sons do jogo` / `Todo o som do PC`) e os
# dois do modo do microfone (`Virtual` / `Nativo`). Até hoje o aceso era a
# classe `on` que ESTE arquivo escreveu, uma vez, e valia para sempre. Medido na
# mesa dela em 03/09/2026: o card 2 mostrava `Todo o som do PC` aceso com
# `speaker.rota = 2` no daemon, e o card 1 mostrava `Virtual` aceso sem uma
# linha de `microfone` no `maquina.json`.
#
# OS TRÊS ATRIBUTOS QUE ELES GANHARAM, e nenhum move um pixel (os três estão em
# `check_o_desenho_aprovado.INVISIVEIS`):
#
#   data-campo         o endereço, IGUAL nos dois botões do par
#   data-hef-alvo      `classe` — o alvo que acende, e não escreve texto
#   data-hef-quando    quem é ESTE botão; acende o que casar com o valor pintado
#
# O ENDEREÇO VAI NO BOTÃO, NUNCA NO CONTAINER. A razão está medida no bloco do
# `.mic-modo` abaixo: `data-campo` no `<span>` que ENVOLVE os dois faz o piloto
# trocá-los por um travessão — `[data-mic-modo]` de 4 para 0, no Chrome, em
# 01/09/2026. Foi por isso que aquele endereço saiu, e é por isso que este entra
# num lugar diferente.
#
# LIGAR UM DESLIGA O OUTRO SEM LISTA DE IRMÃOS: os dois compartilham o mesmo
# `data-campo`, o `achar()` os visita com o mesmo valor e cada um decide por si
# — não há caminho no código em que os dois casem (`hefesto_vivo.escrever`,
# ramo `classe`).
#
# QUEM PINTA, e os donos são diferentes de propósito:
#
#   alto-rota        `a02_controles.rota_na_tela`, do `speaker.rota` que o
#                    daemon publica a cada tique. Rota 0 e 1 (tudo no fone,
#                    mono no fone) apagam os DOIS em vez de arredondar para o
#                    botão mais parecido.
#   mic-modo-aceso   `a02_controles.modo_do_mic`, do `maquina.json` — o
#                    `machine.declare` fica FORA do `state_full` de propósito
#                    (`a02_controles.SEM_ECO`), então o dono deste aceso é o
#                    DISCO, e o gesto invalida a leitura em cache ao gravar.
#
# E A PROSA FICA AQUI, EM PYTHON, e não num `<!-- -->` no HTML gerado: o
# `o_que_se_ve` do portão do desenho apaga os atributos de endereço e mais nada
# — um comentário novo no HTML conta como DESENHO MUDADO e tranca o
# `--publicar-enderecos`. Medido nesta leva: a primeira redação destes dois
# blocos vivia dentro da `f-string`, e `so_mudou_endereco('02-controles.html')`
# devolvia `False`.


def bloco(c, *, bat, glifos_on, l2, r2, touch, sticks,
          giro, mic_v, mic_mudo, mic_vol, alto_v, rota_pc, estado_alto,
          alto_mudo=False, alto_pode=True, mic_posse=False, tocando=True,
          mic_modo="virtual", accel=None):
    """Uma caixa de controle, a partir do ITEM DA MESA — nunca de um nome digitado.

    É UMA função para as duas formas, porque agora é uma caixa só: o rádio diz
    se ela está aberta (card) ou fechada (linha), e o CSS faz o resto. Do `c`
    saem a identidade inteira: o plástico (`cor_da_zona`, lido do desenho), o
    número do jogador, o transporte e o rótulo. O que entra por argumento é só o
    ESTADO — o que este controle está fazendo agora.
    """
    plastico = cor_da_zona(c["cor"])            # a cor da casca, lida do SVG gerado
    luz = luz_do_jogador(c)
    rid = f'c-{c["pref"]}'
    mic_selo = "MUDO" if mic_mudo else "ATIVO"
    mic_off  = " off" if mic_mudo else ""
    mic_on   = " on"  if mic_mudo else ""
    # OS TRÊS ESTADOS DE SOM QUE ENTRARAM POR ARGUMENTO TÊM DEFAULT, e o default
    # é o que a mesa dela responde HOJE, medido no `state_full` dos dois
    # controles: `speaker.muted: false` (o ♪ apagado), `volume: 101/102`
    # presentes (o ♪ pode ser clicado) e `mic_mudo_desejado: null` (a posse do
    # mudo é do kernel, logo não há o que Liberar). Assim a cena FIXA do mockup
    # — a que `--sem-ponte` mostra — não muda de forma nesta leva, e quem pinta
    # o valor de verdade é a ponte viva.
    alto_on = " on" if alto_mudo else ""
    # A PALAVRA É A DO PRODUTO, e o dono é `sensor_widgets.texto_toques` — o
    # mesmo que a GTK chama na mesma conta (`controller_card.py:5079`,
    # `texto_toques(1 if tocando else 0)`). Ela era `COM_TOQUE`/`SEM_TOQUE`,
    # duas constantes do pacote, e o "Tocando" era palavra do desenho: ela
    # decidiu em 02/09/2026 (item 15) que o touchpad usa a do produto.
    toque_txt = texto_toques(1 if tocando else 0)
    # os três botões de som: a trava e a dica saem do MESMO booleano, senão um
    # botão apagado poderia carregar a dica de quem está clicável.
    alto_trava, alto_dica = ("", DICA_ALTO_MUDO) if alto_pode else (" disabled", DICA_ALTO_SEM_POSSE)
    # O PONTO ACENDE POR CLASSE, e não por `style`: é o que o produto
    # alcança (`data-hef-alvo="classe"`) e o que faz o desenho parar de
    # contradizer o campo ao lado dele.
    ponto_on = " on" if tocando else ""
    def gx(fam, e, v, cor):
        # OS TRÊS ENDEREÇOS DE UM EIXO — 03/09/2026. Antes daqui a linha inteira
        # era desenho: `data-eixo` é vocabulário do CSS e o piloto não o lê, e
        # os números do mockup ficavam na tela para sempre. Fotografado com os
        # dois controles dela na mesa: o giroscópio do P1 dizia +143.2 / −412.0
        # / +22.8 com o aparelho parado, e o acelerômetro +0.105 / +0.976 /
        # +0.170 — que são os valores que ESTE arquivo mediu uma vez, no dia em
        # que foi escrito.
        #
        # SÃO TRÊS PORQUE UM ELEMENTO SÓ ACEITA UM ALVO: o número é texto, cada
        # metade da barra é largura, e a cor sobe para o trilho. Ver o bloco da
        # `.eixo .v` no CSS, que tem a conta da equivalência de pixels.
        chave, meias = f"{fam}-{e.lower()}", _meias_da_barra(cor)
        return (f'''            <div class="eixo" data-eixo="{chave}"><span>{e}</span><span data-campo="{chave}">{v}</span>
              <span class="g" data-campo="{chave}-cor" data-hef-alvo="cor" style="color:{meias[2]}"><span
                class="v neg" data-campo="{chave}-neg" data-hef-alvo="largura" style="width:{meias[0]}%"></span><span
                class="v pos" data-campo="{chave}-pos" data-hef-alvo="largura" style="width:{meias[1]}%"></span></span></div>''')
    giro_html = chr(10).join(gx("giro", e, v, cor) for e, v, cor in giro)
    # O ACELERÔMETRO SAI DA MESMA FUNÇÃO QUE O GIRO — mesma forma, mesma
    # linha, mesma barra. O que muda é a UNIDADE (g, não graus/s) e a
    # ESCALA: 1 g é o repouso, então a barra tem de mostrar 0,976 sem
    # estourar. Ver o comentário do bloco, abaixo.
    accel_html = chr(10).join(gx("accel", e, v, cor) for e, v, cor in (accel or []))
    fx = f'''      <label class="faixa" for="{rid}" title="{ABRE_O_CARD}">
{identidade(c, bat=bat, meio=resumo_fechado(mic_mudo))}
      </label>'''
    return f'''    <div class="ctl card" style="--plastico:{plastico}" data-controle="{c.get("uniq") or c["pref"]}">
      <input class="radio-mesa" type="radio" name="mesa" id="{rid}"{" checked" if c["alvo"] else ""}>
{fx}
      <div class="corpo-cx">
      <div class="card-corpo">

        <div>
          <div class="moldura touchp">
            <div class="rot rot-linha">Touchpad
              <span class="de-quem" data-campo="touch-estado" title="{DICA_TOQUE}">{toque_txt}</span></div>
            <div class="touch">
              <span class="ponto{ponto_on}" data-campo="touch-ponto" data-hef-alvo="classe"
                style="left:{touch[0]}%;top:{touch[1]}%"></span></div>
          </div>
          <div class="moldura luz" style="margin-top:9px">
            <div class="rot rot-linha">Barra de luz
              <span class="de-quem" data-campo="luz-hex" title="{DE_QUEM_E_A_LUZ}">{luz.upper()}</span></div>
            <div class="barra-luz" data-campo="luz-cor" data-hef-alvo="cor"
              style="color:{luz}"></div>
          </div>
          <div class="moldura led" style="margin-top:9px" title="{DICA_LED_JOGADOR}">
            <div class="rot rot-linha">LED do jogador</div>
            <div class="lampadas">{luzinhas(c["jogador"])}</div>
          </div>
        </div>

        <div>
          <div class="moldura">
            <div class="sticks">
              <div>
                <div class="stick-rot">Analógico<br>esquerdo</div>
                <div class="stick" data-stick="l">
                  <span class="rotl" data-campo="l3">{ROTULO_DO_CLIQUE["l"]}</span>
                  <span class="p" style="left:{pos(sticks[0])}%;top:{pos(sticks[1])}%"></span></div>
                <div class="xy" data-xy="l" data-campo="xy-l" data-hef-alvo="html">{_texto_do_xy(sticks[0], sticks[1])}</div>
              </div>
              <div>
                <div class="stick-rot">Analógico<br>direito</div>
                <div class="stick" data-stick="r">
                  <span class="rotl" data-campo="r3">{ROTULO_DO_CLIQUE["r"]}</span>
                  <span class="p" style="left:{pos(sticks[2])}%;top:{pos(sticks[3])}%"></span></div>
                <div class="xy" data-xy="r" data-campo="xy-r" data-hef-alvo="html">{_texto_do_xy(sticks[2], sticks[3])}</div>
              </div>
            </div>
          </div>
        </div>

        <div>
          <div class="moldura">
            <div class="glifos">
{grade(glifos_on)}
            </div>
          </div>
        </div>

        <div>
          <div class="moldura" data-bloco="microfone">
            <!-- O "LIBERAR" SAIU — 30/08/2026, e o argumento é dela, não meu:
                 *"o botão do Controle sempre controla a interface, por isso não faz
                 sentido o liberar ali"*.

                 EU TINHA MEDIDO O CONTRÁRIO e ela me corrigiu num plano acima. O
                 `mic.set {{muted: null}}` EXISTE (`ipc_handlers.py:4779`) e devolve a
                 posse ao `hid-playstation` — a minha objeção era que o botão tinha
                 dono. Mas ter dono não é ter SENTIDO: se o botão físico do controle
                 nunca deixa de comandar a interface, não há posse a devolver, e um
                 botão que desfaz algo que não acontece é um botão que ensina errado.
                 O método continua no daemon, para quem precisar dele. -->
            <div class="rot rot-linha">Microfone
              <span class="selo-ativo{mic_off}" style="margin-left:5px" data-campo="mic-selo">{mic_selo}</span>
              <span class="ajuda" style="display:inline-block;vertical-align:-3px">?<span class="dica">
                A barra mostra o som <b>entrando agora</b>. O <b>🎙</b> cala no
                <b>firmware</b> e apaga a luz vermelha do plástico.<br><br>
                O <b>modo</b>, à direita, diz por onde o som do microfone chega ao PC.
              </span></span>
              <!-- O MODO DO MICROFONE — pedido dela, 30/08: *"tá faltando o Modo do
                   Mic: Virtual, Desativado e Nativo"*.

                   ELE MORA NA LINHA DO RÓTULO, e isso é orçamento, não estética.
                   Como fileira própria embaixo ele custava 42px (36 da altura de
                   escolha + 6 de margem), e o card ia de 304 para 350 — contra os
                   308 que `PARA_O_CARD` reserva. O quadro passava a rolar por
                   dentro e o P4 saía da tela; medido antes de escolher este lugar.
                   Aqui ele ocupa o vão que o "Liberar" deixou: custo ZERO de
                   altura, e ainda fica ao lado do selo que diz se o mic está
                   ATIVO — que é a informação com que ele conversa. -->
              <!-- AS CHAVES SÃO SIMPLES, E A DUPLA ERA UM BOTÃO MORTO.
                   Este bloco é `return f` com aspas triplas (linha 834), e chave
                   dupla ESCAPA para chave simples literal: a expressão nunca era
                   avaliada e os 12 botões (4 controles x 3 modos) nasciam todos com
                   a mesma classe crua, nenhum aceso. Medido pelo cético:
                   classList.contains("on") falso nos doze.
                   É o defeito que o CLAUDE.md nomeia — *"uma validação de interface
                   que não cobre o botão novo é uma validação que mente"*: eu conferi
                   que os três botões EXISTEM e não que um deles ACENDE.
                   E o comentário que eu escrevi para explicar isto quebrou o gerador,
                   porque trazia chaves dentro da própria f-string. Por isso ele não
                   as tem. -->
            </div>
            {onda(mic_v, mic_mudo)}
            <div class="vol">
              <span class="trilho"><span class="cheio" style="width:{mic_vol}%"></span></span>
              <span class="n">{mic_vol}</span>
              <button class="mudo-i{mic_on}" data-gesto="mudo" data-mudo="microfone" title="{DICA_MIC_MUDO}">🎙</button>
            </div>
            <!-- OS DOIS MODOS DESCERAM PARA CÁ — decisão dela, 31/08/2026:
                 *"Os botões Virtual e Nativo ficam na parte de baixo do slider,
                 igual o Sons do Jogo e Todo o som do PC."*

                 ELES MORAVAM NA LINHA DO RÓTULO, e ali o custo de altura era
                 ZERO — foi o argumento que os pôs lá em 30/08, quando eram TRÊS
                 e não cabiam embaixo. Com o "Desativado" fora (ordem dela do
                 mesmo dia) sobraram dois, e dois cabem na mesma fileira que o
                 alto-falante usa: a mesma classe, a mesma altura, o mesmo gesto.
                 Duas gramáticas para "escolher a rota do som" na mesma coluna
                 era uma a mais. -->
              <!-- O `data-gesto="mic-modo"` ENTROU EM 01/09/2026, e é a mesma
                   razão do `data-gesto="mudo"` lá em cima: o piloto monta o
                   nome do gesto como `d.gesto || d.hefGesto || d.papel ||
                   'clique'` (`hefesto_vivo.py:221`). Sem ele, Virtual e Nativo
                   chegavam ao despachante chamando-se `clique`, disputando um
                   nome com os interruptores de sensor da mesma aba.
                   E O CONTAINER PERDEU O `data-campo` — ver o comentário no
                   CSS: endereçá-lo trocava os dois botões por um travessão. -->
              <span class="rota mic-modo">
                <button class="{'on' if mic_modo == 'virtual' else ''}" data-gesto="mic-modo" data-mic-modo="virtual" data-campo="mic-modo-aceso" data-hef-alvo="classe" data-hef-quando="virtual"
                  title="O Hefesto cria uma fonte de áudio própria e entrega o microfone do controle ao PC por ela. É o que faz o mic soar igual no cabo e no rádio.">Virtual</button>
                <button class="{'on' if mic_modo == 'nativo' else ''}" data-gesto="mic-modo" data-mic-modo="nativo" data-campo="mic-modo-aceso" data-hef-alvo="classe" data-hef-quando="nativo"
                  title="O microfone entra como o kernel o expõe, sem o Hefesto no meio. Pelo rádio isso depende do perfil que o adaptador negociou.">Nativo</button>
              </span>

          </div>
          <div class="moldura" style="margin-top:9px" data-bloco="alto-falante">
            <div class="rot">Alto-falante<span class="mudo" data-campo="alto-estado" hidden></span>
              <span class="ajuda" style="display:inline-block;vertical-align:-3px">?<span class="dica">
                <b>Sons do jogo</b> manda só o áudio do jogo ao alto-falante do controle;
                <b>Todo o som do PC</b> manda tudo, inclusive notificação.
              </span></span>
            </div>
            {onda(alto_v)}
            <div class="vol">
              <span class="trilho"><span class="cheio" data-campo="alto-barra"
                data-hef-alvo="largura" style="width:{alto_v[0]}%"></span></span>
              <span class="n" data-campo="alto-num">{alto_v[0]}</span>
              <button class="mudo-i{alto_on}" data-gesto="mudo" data-mudo="alto-falante"{alto_trava} title="{alto_dica}">♪</button>
            </div>
            <div class="rota">
              <button class="{'on' if not rota_pc else ''}" data-gesto="rota" data-rota="jogo" data-campo="alto-rota" data-hef-alvo="classe" data-hef-quando="jogo">Sons do jogo</button>
              <button class="{'on' if rota_pc else ''}" data-gesto="rota" data-rota="pc" data-campo="alto-rota" data-hef-alvo="classe" data-hef-quando="pc">Todo o som do PC</button>
            </div>
          </div>
        </div>

        <div>
          <!-- UM BLOCO, DOIS SENSORES — 30/08/2026.

               O acelerômetro entrou por decisão dela (*"não era pra ele sair, era
               pra ele FUNCIONAR"*), e como MOLDURA PRÓPRIA ele não cabia: medido,
               a coluna dos sensores passava de 190 para 278px de conteúdo natural,
               contra os **232** que as cinco colunas compartilham (a conta está no
               `ALTURA_DO_CARD`, e o card tem 4px de folga). O quadro rolava por
               dentro e o P4 saía da tela.

               Dois sensores numa moldura só custam UM rótulo e UMA borda em vez de
               dois — e é honesto: eles são o MESMO nó evdev (`Motion Sensors`),
               separados só pelo código do eixo. ABS_RX/RY/RZ é o giro, ABS_X/Y/Z é
               o acelerômetro; as escalas é que são independentes (1024 contra
               8192), e por isso cada grupo diz a sua unidade.

               Os números do acelerômetro do P1 são MEDIDOS, no daemon vivo:
               {{'x': 0.105, 'y': 0.976, 'z': 0.170}} — |v| = 0,996 g, a gravidade. -->
          <div class="moldura leituras" data-bloco="giroscopio">
            <div class="rot">Giroscópio
              <span class="ajuda" style="display:inline-block;vertical-align:-3px">?<span class="dica" style="left:auto;right:22px">
                Leitura viva do aparelho, dez vezes por segundo. Nada aqui se clica.<br><br>
                O <b>giroscópio</b> mede o quanto o controle gira, em graus por segundo.
                O <b>acelerômetro</b> mede a inclinação e o chacoalhar, em g — parado
                numa mesa plana a soma dos três eixos dá <b>1 g</b>, que é a gravidade,
                e é por isso que um deles fica perto de 1 e os outros perto de 0.<br><br>
                Um traço no lugar do número quer dizer que a leitura ainda não chegou.
              </span></span>
            </div>
{giro_html}
          </div>
          <div class="moldura leituras" style="margin-top:9px" data-bloco="acelerometro">
            <div class="rot">Acelerômetro</div>
{accel_html}
          </div>
          <div class="moldura gatilhos" style="margin-top:9px">
            <div class="rot">Gatilhos</div>
            <div class="gat">
              <div class="gat-linha" data-gatilho="l2"><span>L2</span>
                <span class="trilho"><span class="cheio" data-campo="l2-barra"
                  data-hef-alvo="largura" style="width:{l2*100//255}%"></span>
                  <span class="n" data-campo="l2-num">{l2} / 255</span></span></div>
              <div class="gat-linha" data-gatilho="r2"><span>R2</span>
                <span class="trilho"><span class="cheio" data-campo="r2-barra"
                  data-hef-alvo="largura" style="width:{r2*100//255}%"></span>
                  <span class="n" data-campo="r2-num">{r2} / 255</span></span></div>
            </div>
          </div>
        </div>

      </div>
      </div>
    </div>'''


# O ESTADO DE CADA UM, por `pref` da MESA — e SÓ o estado: quem é o controle,
# de que cor é o plástico, que jogador ele é e por onde ele fala já está na MESA,
# que é a fonte. Aqui fica o que muda de segundo a segundo.
#
# Os quatro não estão fazendo a mesma coisa de propósito: com a mesa cheia é o
# CONTRASTE que ensina a ler o card. O P1 está sendo jogado; o P2 tem o microfone
# calado no firmware; o P3 está parado com a bateria caindo; o P4 tem o microfone
# MUDO com o volume em 75 — que é a diferença entre mudo de firmware e volume
# zero, exatamente o que a dica do bloco explica.
#
# A MÁSCARA NÃO ESTÁ AQUI, E É DE PROPÓSITO. Ela morava neste dicionário, um
# `mask="…"` por controle — uma segunda cópia do que a aba Jogar mostra. As duas
# divergiram: medido em 28/08, a Jogar dizia que o P2 era DualSense e o P3
# Xbox 360, e esta aba dizia o contrário, na mesma sessão. Agora ela vem de
# `c["mascara"]`, da `monta.MESA`, que é o único lugar onde ela se escreve.
# O que fica aqui é só o que muda de segundo a segundo.
#
# O VALOR DE CAMPO COMEÇA EM MAIÚSCULA. Ela apontou o padrão com o dedo em outra
# aba — *"o rádio de cada adaptador, em fatias"* —: rótulo visível e valor de
# campo não começam em minúscula. Aqui o único era o estado do alto-falante
# (`· 100 % · acordado`), que virou `Acordado`. O outro candidato desta aba era o
# `em rajadas` do giroscópio, e ele saiu da tela junto com a leitura — sobrou no
# `title` do interruptor, dentro de frase corrida, que é onde minúscula é o certo.
#
# As TRÊS aparecem na tela ao mesmo tempo — DualSense (P1 e P3), Xbox 360 (P2) e
# Nintendo Pro (P4) —, e é assim que se aprende que a linha muda de controle para
# controle. A Nintendo Pro ainda não existe no catálogo do produto
# (`uinput_gamepad.FLAVORS` tem `dualsense` e `xbox`): nasce como sprint, e está
# dito na legenda.
PARADO = [("X", "  +0.0", "left:50%;width:1%;background:var(--border-forte)"),
          ("Y", "  +0.0", "left:50%;width:1%;background:var(--border-forte)"),
          ("Z", "  +0.0", "left:50%;width:1%;background:var(--border-forte)")]

ESTADO = {
  "p1": dict(bat=100, estado_alto="Acordado",
    mic_vol=80, glifos_on={"cross", "dpad_up", "l2"},
    l2=200, r2=40, touch=(62, 44), sticks=(60, 200, 180, 90),
    giro=[("X", "+143.2", "left:50%;width:22%;background:var(--red)"),
          ("Y", "−412.0", "left:12%;width:38%;background:var(--green)"),
          ("Z", " +22.8", "left:50%;width:4%;background:var(--cyan)")],
    # O ACELERÔMETRO, em g. O P1 traz os números MEDIDOS no daemon vivo em
    # 30/08 (|v| = 0,996 g). O P3 mostra o estado que a tela precisa saber
    # dizer: o leitor ainda não acordou, e um traço é mais honesto que zero.
    accel=[
          ("X", " +0.105", "left:50%;width:3%;background:var(--cyan)"),
          ("Y", " +0.976", "left:50%;width:24%;background:var(--green)"),
          ("Z", " +0.170", "left:50%;width:4%;background:var(--cyan)"),
    ],
    mic_v=[22, 48, 72, 95, 64, 38, 52, 80, 44, 26, 58, 88, 40, 20], mic_mudo=False,
    alto_v=[100, 88, 64, 92, 76, 54, 82, 96, 70, 48, 86, 60, 74, 90], rota_pc=False),

  # O P2 É O "SEM TOQUE" DA CENA, e é o mesmo contraste que já faz dele o do
  # microfone MUDO: com a mesa cheia é o CONTRASTE que ensina a ler o card, e
  # sem um card assim a leitura nova diria "Tocando" nos quatro — inclusive nos
  # dois que estão no (50,50), que é posição de enfeite e não de dedo.
  "p2": dict(bat=64, estado_alto="Acordado", mic_vol=0, glifos_on=set(), tocando=False,
    l2=0, r2=0, touch=(50, 50), sticks=(128, 128, 128, 128),
    giro=PARADO,
    # deitado na mesa: quase toda a gravidade num eixo só
    accel=[
          ("X", " −0.032", "left:49%;width:1%;background:var(--cyan)"),
          ("Y", " +0.998", "left:50%;width:25%;background:var(--green)"),
          ("Z", " +0.041", "left:50%;width:1%;background:var(--cyan)"),
    ],
    mic_v=[4, 6, 5, 4, 6, 5, 4, 5, 6, 4, 5, 4, 6, 5], mic_modo="desativado", mic_mudo=True,
    alto_v=[70, 52, 66, 44, 72, 58, 48, 64, 54, 70, 46, 60, 50, 68], rota_pc=True),

  "p3": dict(bat=31, estado_alto="Acordado",
    mic_vol=60, glifos_on={"circle"},
    l2=0, r2=18, touch=(38, 71), sticks=(128, 128, 141, 122),
    giro=[("X", " +11.4", "left:50%;width:3%;background:var(--cyan)"),
          ("Y", "  −6.2", "left:48%;width:2%;background:var(--cyan)"),
          ("Z", "  +2.0", "left:50%;width:1%;background:var(--cyan)")],
    # O ACELERÔMETRO, em g. O P1 traz os números MEDIDOS no daemon vivo em
    # 30/08 (|v| = 0,996 g). O P3 mostra o estado que a tela precisa saber
    # dizer: o leitor ainda não acordou, e um traço é mais honesto que zero.
    accel=[
          ("X", "      —", "left:50%;width:0%"),
          ("Y", "      —", "left:50%;width:0%"),
          ("Z", "      —", "left:50%;width:0%"),
    ],
    mic_v=[18, 30, 22, 41, 28, 19, 35, 24, 30, 20, 38, 26, 22, 31], mic_modo="nativo", mic_mudo=False,
    alto_v=[55, 40, 62, 48, 58, 36, 50, 44, 60, 38, 52, 46, 42, 56], rota_pc=False),

  "p4": dict(bat=88, estado_alto="Acordado",
    mic_vol=75, glifos_on={"triangle", "r1"},
    l2=12, r2=255, touch=(50, 50), sticks=(128, 128, 96, 128),
    giro=[("X", "  −8.6", "left:48%;width:2%;background:var(--cyan)"),
          ("Y", " +30.5", "left:50%;width:6%;background:var(--green)"),
          ("Z", "  +1.1", "left:50%;width:1%;background:var(--cyan)")],
    # O ACELERÔMETRO, em g. O P1 traz os números MEDIDOS no daemon vivo em
    # 30/08 (|v| = 0,996 g). O P3 mostra o estado que a tela precisa saber
    # dizer: o leitor ainda não acordou, e um traço é mais honesto que zero.
    accel=[
          ("X", " +0.412", "left:50%;width:10%;background:var(--orange)"),
          ("Y", " +0.884", "left:50%;width:22%;background:var(--green)"),
          ("Z", " −0.201", "left:45%;width:5%;background:var(--cyan)"),
    ],
    mic_v=[5, 4, 6, 5, 4, 5, 6, 4, 5, 6, 4, 5, 4, 6], mic_mudo=True,
    alto_v=[80, 66, 74, 58, 84, 62, 70, 76, 54, 68, 60, 78, 64, 72], rota_pc=False),
}

# O QUE ABRE É O ALVO DA FITA, E O ALVO É DA MESA. Ele estava escrito duas
# vezes — `alvo=True` no ESTADO do p1 e `"alvo": True` no item da mesa —, e duas
# fontes para a mesma escolha é o defeito que acaba divergindo. Agora só a MESA
# responde, e ela responde uma vez só: o `checked` do rádio nasce do mesmo campo.
# ERA UM LAÇO POR FORMA (um para os cards, outro para as tiras); agora é UM, e é
# assim que se sabe que a caixa é uma só. "Quatro" continua sem estar escrito em
# lugar nenhum: no dia em que a mesa tiver três ou cinco, esta linha não muda.
def lugar_vazio(c):
    """O lugar de um controle que não está na mesa — decisão dela, 31/08/2026:

        "Deixa os outros espaços dos 4 controles a mostra ainda mas cinza igual
         vc fez na aba jogar."

    ELE NÃO ABRE, e é pedido dela no mesmo turno: *"tiramos o modo p3. p4
    (seções expandidas não aparecem)"*. Por isso não há `<input type=radio>`
    aqui — sem rádio o CSS não tem como expandi-lo, e a impossibilidade fica na
    ESTRUTURA, não numa regra que alguém desfaz sem perceber.

    E ELE É MAIS BAIXO QUE UMA LINHA FECHADA, de propósito: um lugar vazio não
    tem giroscópio para ligar, nem microfone para resumir, nem bateria para
    medir. O que sobra é o número do lugar e travessões. Medido: 24px contra os
    34 da linha fechada — e esses 10px por lugar são o que faz os dois botões
    novos caberem sem o quadro rolar.
    """
    return f'''    <div class="ctl off" data-controle="{c["pref"]}" data-conectado="nao"
         title="Lugar vazio: nenhum controle conectado aqui.">
      <div class="faixa">
        <span class="card-nome">P{c["jogador"]}</span>
        <span class="div">·</span>
        <span class="leia">{_VAZIO}</span>
        <span class="bat">{_VAZIO}</span>
      </div>
    </div>'''


#: O marcador de campo vazio, o mesmo travessão da aba Jogar.
_VAZIO = "—"

BLOCOS = "\n".join(
    bloco(c, **ESTADO[c["pref"]]) if c.get("conectado", True) else lugar_vazio(c)
    for c in MESA)

# OS NÚMEROS DA APERTADA, medidos no Chrome em 27/08 e usados na legenda. Ficam
# aqui, e não escritos na prosa, porque a prosa envelhece calada.
# O CARD NÃO ENCOLHE: as cinco colunas param em ~236px de conteúdo natural.
# ERA 301, E 301 CADUCOU EM 29/08. Medido no WebKit do piloto, na cena fixa de
# quatro com o "Todos" aberto: **304,3 px**. Quem cresceu foi a coluna 1, ao
# partir a Barra de luz em dois campos (118 do touchpad + 9 + 55 da barra + 9 +
# 45 do LED do jogador = 236, contra 229 de antes). A coluna dos sensores NÃO
# entra na conta: com os dois numa moldura só, ela pede 228 px naturais (148 das
# leituras + 9 + 71 dos Gatilhos), abaixo dos 236 que a coluna 1 e a do som
# mandam — e é por isso que os Gatilhos é que esticam para fechar a coluna.
# ERAM 190, e 190 CADUCOU EM 30/08, quando o acelerômetro entrou: o número era o
# do par Giroscópio + Gatilhos, que deixou de existir.
# O preço está no `ROLA_EM_TODOS` aqui embaixo, e só nele: com 4 cards de 304 em
# vez de 301, o "Todos" rola 807 px em vez de 794. O estado em que a aba ABRE
# continua sem rolar — `PARA_O_CARD` (308) ainda cobre o card, agora com 4 px de
# folga em vez de 7, e é o `assert` logo abaixo que guarda isso.
ALTURA_DO_CARD = 304
FECHADOS = len(CONECTADOS) - 1          # as linhas fechadas: os conectados menos o aberto
VAZIOS = len(MESA) - len(CONECTADOS)    # os lugares apagados, que não abrem
ALTURA_VAZIA = 24                       # `.ctl.off` — sem sensor, sem bateria, sem 34

# O `quadro-corpo` com o quadro esticado até o rodapé, MEDIDO no Chrome hoje.
# Os dois botões não entram nesta conta desde que ela os mandou de volta ao canto
# superior direito: lá eles moram no `.quadro-topo`, que já existia, e custam
# ZERO do corpo — o cabeçalho mede os mesmos 45px com e sem eles.
#
# ELE JÁ FOI 478 NESTA MESMA SESSÃO, e por poucos minutos: era o que o corpo
# recebia enquanto os botões viviam DENTRO dele. Um número de layout copiado de
# um estado que não existe mais é a forma mais barata de uma régua mentir — e
# esta mentiu duas vezes hoje. O comando que o mede está no `COMO-OLHAR-A-TELA`.
VISIVEL = 461
PAD_DO_CORPO = 24             # 10px em cima + 14px embaixo, que rolam junto
ALTURA_FECHADA = 34           # --h-acao, e o `border-box` põe as duas bordas dentro
GAP_ENTRE = 9                 # o mesmo passo que separa duas molduras dentro do card
# A LARGURA DA BATERIA, IGUAL NAS QUATRO LINHAS. O teto é a linha mais apertada —
# a do P3, que junta o nome mais longo da mesa ("Galactic Purple") com "em
# rajadas" e "ATIVO". Medido nela: 253,7px disponíveis, dos quais estes 240
# ficam com a bateria e 13,7 sobram de folga. É pouco, e é o que há: um rótulo
# uma palavra maior nessa linha estoura, e aí a bateria é que encolhe — nas
# QUATRO, porque o número é um só.
LARG_BATERIA = 240
# O PAR DE SENSORES NA LINHA, medido no Chrome em 28/08 (janela de 1180px) DEPOIS
# de os dois interruptores descerem para cá. Ficam aqui pelo mesmo motivo dos de
# cima: a legenda os lê, e prosa com número digitado envelhece calada.
LARG_SW = 119.3               # cada botão — a grade dá aos dois o tamanho do maior
ALT_SW = 26                   # a linha fechada tem 30px por dentro; `--h-acao` (34) não cabe
LARG_PAR_SENSORES = 246.6     # os dois mais o vão de 8px
X_PAR_SENSORES = (992.4, 1119.7)   # os oito botões nascem nestes dois x, nas quatro linhas
# O VÃO LIVRE DA LINHA, medido do fim do texto até o que vem depois (a bateria
# ontem, o par de sensores hoje) e sempre com o vão de 9px dentro — é a mesma
# régua nas duas datas, senão os números não se comparam.
VAO_ANTES_P3 = 103.2          # a linha mais apertada da mesa, com as duas leituras
VAO_DEPOIS_P3 = 108           # a mesma linha, sem elas e com o par
VAO_DEPOIS_P1 = 270.8         # a linha do card aberto
CUSTO_HEFESTO_ON = 91.7       # o span (71) + o separador (2,7) + os dois vãos de 9
CUSTO_GIRO_RAJADAS = 168.8    # o span (148,1) + o separador + os vãos, na linha do P3
CUSTO_VE_COMO_P3 = 144.6      # idem, se um dia ela quiser este fora também
EMPILHADOS = len(MESA) * ALTURA_DO_CARD + (len(MESA) - 1) * 14   # o que NÃO cabia

# A CONTA FOI REFEITA EM 31/08/2026, e a versão antiga MENTIA. Ela dizia
# `FECHADOS = len(MESA) - 1` — três linhas fechadas —, e o gerador imprimia
# *"1 aberto de 308px e 3 linhas de 34px, sem rolar"* enquanto o Chrome mostrava
# o quadro ROLANDO e os dois botões novos cortados pela metade. Três coisas
# tinham mudado debaixo dela: dois controles viraram LUGAR VAZIO (24px, não 34),
# nasceu o bloco de AÇÕES no fim, e o padding de baixo do corpo saiu.
#
# *Uma régua que afirma "sem rolar" sem medir é pior que nenhuma:* ela encerra a
# conferência. Os números abaixo saem do Chrome, com o comando ao lado.
# O QUE O CARD ABERTO GANHA — e é aqui que se vê se a mesa cabe. A conta é a
# mesma que o CSS faz: a caixa menos o padding, menos as linhas fechadas, menos
# um passo de 9px entre cada duas caixas.
#
# O PASSO É UM SÓ AGORA. Eram dois — 14px entre o card e o grupo das tiras, 9px
# entre tiras —, porque eram dois containers. Com o acordeão as quatro caixas são
# irmãs no mesmo container, e duas medidas para o mesmo vão seria a mesma
# incoerência que a régua cobra nos títulos: o passo entre irmãos é um.
PARA_O_CARD = (VISIVEL - PAD_DO_CORPO - FECHADOS * ALTURA_FECHADA
               - VAZIOS * ALTURA_VAZIA - (len(MESA) - 1) * GAP_ENTRE)
# A CONTA É UM PORTÃO, e não um comentário: se um dia a mesa crescer a ponto de o
# card aberto não caber, o gerador PARA aqui em vez de entregar uma tela que
# esconde controle calada — que é exatamente o defeito que esta aba curou.
assert PARA_O_CARD >= ALTURA_DO_CARD, (
    f"a mesa de {len(MESA)} não cabe: o card aberto precisa de {ALTURA_DO_CARD}px "
    f"e sobram {PARA_O_CARD}px depois de {FECHADOS} linhas fechadas")
# O QUE "TODOS" CUSTA, e ele é o único estado desta aba que rola. Não é defeito
# escondido: é o preço de um gesto que ela pediu com todas as letras, e o preço
# está escrito na legenda em vez de ficar só aqui.
ALTURA_EM_TODOS = len(MESA) * ALTURA_DO_CARD + (len(MESA) - 1) * GAP_ENTRE
ROLA_EM_TODOS = ALTURA_EM_TODOS - (VISIVEL - PAD_DO_CORPO)

# ---------------------------------------------------------------------------
# AS REGRAS DO ESTADO ABERTO, GERADAS. São duas condições para a mesma cara — o
# rádio deste controle ligado, ou o "Todos" ligado —, e escrever cada regra duas
# vezes à mão é convidá-las a divergir na primeira mudança. O sufixo entra por
# argumento; o prefixo é um só.
# ---------------------------------------------------------------------------
def _aberto(sufixo=""):
    return (f".ctl:has(> input:checked){sufixo},\n"
            f"  body:has(#c-todos:checked) .ctl{sufixo}")


# O CHIP ESCOLHIDO SE ACENDE PELO RÁDIO, não por uma classe que o gerador
# escreveu. `monta.fita()` marca o chip do alvo com `on`; aqui esse `on` sai (é
# `fita_clicavel` quem o tira) e quem acende é o estado vivo — senão o P1
# ficaria aceso para sempre, com o card do P3 aberto ao lado.
_CHIPS = ["c-todos"] + [f'c-{c["pref"]}' for c in MESA]
CHIP_ACESO = ",\n  ".join(f'body:has(#{r}:checked) .chip[for="{r}"]' for r in _CHIPS)

# O número vive no Python e desce para o CSS por variável — escrever 240 nos dois
# lugares é convidá-los a divergir.
CSS += f"""
  .faixa{{--larg-bateria:{LARG_BATERIA}px}}
  {_aberto()}{{height:auto;flex:1 0 auto;padding-bottom:12px;
    background:linear-gradient(0deg,var(--sel-bg),var(--sel-bg)),var(--panel)}}
  {_aberto(" > .faixa")}{{flex:0 0 var(--h-acao);margin:10px 14px 0;padding:0 11px;
    border:1px solid var(--border-sutil);border-radius:7px;background:var(--app-bg);
    flex-wrap:wrap;white-space:normal}}
  {_aberto(" > .corpo-cx")}{{flex:1;height:auto;overflow:visible;visibility:visible;
    display:flex;flex-direction:column}}
  {_aberto(" > .corpo-cx > .card-corpo")}{{flex:1}}
  {_aberto(" .so-fechado")}{{display:none}}
  {CHIP_ACESO}{{background:var(--sel-bg);color:var(--fg);font-weight:600}}
  .fita label.chip{{cursor:pointer}}
  /* A LÁPIDE DA LEGENDA. Um item que fala do que SAIU não pode ter a mesma cara
     de um item que fala do que está na tela: era assim que o "Liberar" seguia
     lido como novidade dois dias depois de ser removido. O recuo e a cor mais
     apagada dizem "isto é registro", e a régua do gerador usa esta mesma classe
     como a única licença para nomear um termo que o desenho não escreve. */
  .nota li.foi{{color:var(--texto-mudo);border-left:2px solid var(--border-forte);
    padding-left:9px;list-style:none;margin-left:-16px}}
"""

MIOLO = f'''
    <div class="quadro estica">
      <div class="quadro-topo">
        <span class="quadro-titulo">Dispositivos Conectados</span>
        <span class="ajuda">?<span class="dica">
          Os <b>{len(MESA)} controles conectados agora</b>. O escolhido abre com a
          leitura viva do aparelho; os outros ficam numa <b>linha</b>, com quem eles são, o
          que o jogo vê, o microfone e a bateria.<br><br>
          <b>Clique na linha de um controle para abri-lo</b> — os outros fecham. Escolhê-lo
          na <b>fita</b> lá em cima faz exatamente a mesma coisa: é o mesmo gesto, e os
          ajustes desta aba vão para ele. O chip <b>Todos</b> abre os {len(MESA)}, e aí a
          caixa rola.<br><br>
          A <b>borda</b> tem a cor do plástico, aberto ou fechado — é como você sabe qual é
          qual com a mesa cheia; o <b>fundo lilás</b> diz qual está escolhido.<br><br>
          O <b>giroscópio</b> e o <b>acelerômetro</b> são de cada controle, e por isso o
          interruptor de cada um está na <b>linha dele</b>. O botão acima é o único que vale
          para a <b>mesa toda</b>: ele calibra os {len(MESA)} de uma vez.
        </span></span>
        <!-- OS DOIS BOTÕES VOLTARAM AO CANTO SUPERIOR DIREITO — decisão dela,
             31/08/2026: *"A posição deles volta pro canto superior direito."*
             É onde o Calibrar morava antes desta leva, e a classe `.sensores`
             que os alinha à direita nunca deixou de existir.
             DE QUEBRA, ELES DEIXAM DE DISPUTAR ALTURA com a lista de controles:
             no fim do quadro custavam 46px do corpo, e foi por isso que o card
             precisou dos 24px dos lugares vazios para caber. -->
        <span class="sensores">
          <a class="btn" href="calibrar-sensores.html"
             title="Calibra o giroscópio e o acelerômetro dos {len(CONECTADOS)} controles conectados numa passada só, com todos parados numa mesa plana.">Calibrar Sensores de Movimento</a>
          <a class="btn" href="mapa-do-controle.html"
             title="Abre o mapa do controle: cada peça do DualSense com o nome, o glifo e o que o Hefesto lê dela.">Mapa do Controle</a>
        </span>
      </div>
      <div class="quadro-corpo">
        <input class="radio-mesa" type="radio" name="mesa" id="c-todos">
{BLOCOS}
      </div>
    </div>
'''

LEGENDA = f'''<div class="nota">
  <h2>O que mudou em 31/08</h2>
  <ul>
    <li class="foi"><b>O <code>Liberar</code> do microfone saiu desta tela — decisão sua, mantida depois que o motivo dela caiu.</b> Ele estava aqui e devolvia ao <b>botão físico do controle</b> o comando do mudo. Você olhou a tela e disse: <i>"esse botão liberar no microfone não existe."</i> A RETOMADA de 30/08 anotou isso como <i>"não existe em lugar nenhum"</i> e mandou tirá-lo — e essa generalização é <b>falsa</b>: o produto tem o botão (<code>app/widgets/controller_card.py:490</code>) e o daemon aceita <code>mic.set {{muted: null}}</code> (<code>daemon/ipc_server.py:32</code>), que é a devolução. O fato foi medido e levado a você em 31/08 e <b>você manteve a decisão</b>: ele fica fora da tela nova, mesmo existindo no produto. <b>O preço, dito inteiro:</b> quem clicar no <b>🎙</b> daqui <b>assume</b> o mudo, e o botão do controle para de valer; a volta só existe pela janela do aplicativo completo ou reiniciando o Hefesto — e é isso que a dica do 🎙 passou a dizer, no lugar de mandar clicar num botão ausente. Os três testes que mediam este botão viraram <b>lápide</b> em <code>tests/unit/test_regua_de_tela_a_aba_controles.py</code>; se ele voltar, eles voltam inteiros do <code>git log</code>.</li>
    <li><b>Esta legenda anunciava o botão de cima como novidade — dois dias depois de ele sair da tela.</b> É o defeito que esta aba existe para não cometer, virado para dentro: <i>a prosa afirmando o que o produto não faz</i>. Agora o gerador <b>para</b> se a legenda citar um rótulo que o desenho não escreve, e só um <code>&lt;li class="foi"&gt;</code> — a lápide, o item recuado aqui em cima — tem licença de nomear o que saiu. A mesma régua recusa título com data relativa: foi um <i>"hoje"</i> num <code>&lt;h2&gt;</code> que envelheceu calado.</li>
  </ul>

  <h2>O que mudou em 30/08</h2>
  <ul>
    <li><b>O modo do microfone são DOIS, e eles desceram para baixo do slider</b> — suas duas ordens de 31/08: <i>"remove o desligado (fica desligado com slicer no zero)"</i> e <i>"os botões Virtual e Nativo ficam na parte de baixo do slider, igual o Sons do Jogo e Todo o som do PC"</i>. Agora são a <b>mesma fileira</b> que o alto-falante usa — mesma classe, mesma altura, mesmo gesto.<br><b>Em 30/08 eles eram TRÊS e moravam na linha do rótulo</b>, e o motivo era orçamento: como fileira embaixo custariam 42 px e o card estouraria a caixa. Com o "Desativado" fora sobraram dois, e o preço ficou pagável — mas ele existiu: a coluna do som foi de 236 para 269 px, e as duas fileiras de escolha passaram de 36 para <b>30 px</b> de altura para o card caber. É a mesma faixa do chip da fita, e as duas continuam iguais entre si.</li>
    <li><b>O acelerômetro passou a aparecer na tela</b>, com os três eixos e a unidade em <b>g</b>, embaixo do giroscópio e na <b>mesma moldura</b> — que por isso passou a se chamar <b>Sensores</b>. <b>Em 31/08 ela virou DUAS</b>, por ordem sua — <i>"é pra ser 3: um Giroscópio, outra Acelerômetro e outra gatilhos"</i> —, e as unidades (<i>°/s</i> e <i>g</i>) saíram dos rótulos junto. Coube sem custo: a coluna continua nos mesmos px. É a resposta à pergunta que a legenda de 29/08 deixou aberta (<i>vale ler?</i>): vale, e os números do P1 no desenho são <b>medidos</b> no daemon vivo — X +0,105 · Y +0,976 · Z +0,170, que dão <b>0,996 g</b>, a gravidade.</li>
  </ul>

  <h2>O que mudou em 29/08</h2>
  <ul>
    <li><b>Os botões do som passaram a existir.</b> O <b>🎙</b> e o <b>♪</b> tinham cara de botão — o cursor virava mãozinha — e <b>não tinham nada atrás</b>: nenhum clique chegava ao programa. Medido: dois cliques neles produziram <b>zero</b>, enquanto os de rota, ao lado, respondiam. Naquele dia passaram a responder <b>três</b>; hoje são <b>dois</b>, porque o terceiro saiu em 31/08 (acima). E o <b>♪</b> acende quando o alto-falante está mudo — o dado sempre esteve chegando e a tela não o lia.</li>
    <li><b>A dica do 🎙 estava errada, e a correção ficou.</b> Ela dizia que o 🎙 <i>"é o mesmo que apertar o botão do controle"</i>, e não é: clicar ali faz o Hefesto <b>tomar</b> o comando do mudo, e o botão do aparelho para de valer. A dica de hoje diz esse preço — é a informação que a antiga escondia.</li>
    <li><b>Os analógicos estavam mentindo de dois jeitos.</b> (1) No fim do curso — analógico todo à esquerda ou todo para cima — o valor <b>0</b> era trocado por <b>128</b>, o centro: a bolinha <b>pulava de volta ao meio</b> no talo. (2) A bolinha era posicionada pelo <b>canto</b> e não pelo <b>centro</b>, então em repouso ela nascia <b>4,7 px</b> abaixo e à direita da cruz — como se cada eixo tivesse 12,5 unidades presas. Agora o desvio em repouso é <b>0,19 px</b> e os dois extremos são simétricos.</li>
    <li><b>O motivo que eu te dei para o acelerômetro não estar na tela era falso.</b> Eu escrevi aqui que <b>"o aparelho não entrega esse dado"</b>. Ele entrega. Medido nos seus dois controles: o mesmo nó de sensor publica os três eixos do acelerômetro a <b>250 leituras por segundo</b>, calibrados, e a conta fecha na gravidade — <b>0,996 g</b> num controle e <b>0,993 g</b> no outro, contra 1 g de referência. Os dois estavam em <b>poses diferentes</b> na sua mesa (25° de diferença), então não é número decorado, é leitura. Quem não lia era o <b>Hefesto</b>: o dado chegava até a linha que o descarta. A pergunta que ficou — <i>vale ler?</i> — foi respondida no dia seguinte, e o campo está na tela desde 30/08.</li>
    <li><b>O touchpad passou a dizer alguma coisa.</b> Ele é um retângulo que só mostra um ponto <b>enquanto o dedo está lá</b> — e medindo 238 leituras dos seus dois controles, o dedo estava lá em <b>zero</b> delas. Ele nunca mostrava nada. Agora o canto diz <b>Sem toque</b> ou <b>1 toque</b> — a palavra do produto, a mesma que a janela de hoje escreve (<code>sensor_widgets.texto_toques</code>), por decisão sua de 02/09. E a superfície ganhou a <b>proporção do sensor de verdade</b> (16:9, que é o 1920×1080 do touchpad): ela estava 41% esticada na vertical, e com ela a posição do dedo.</li>
    <li><b>O LED do jogador virou campo</b>, com rótulo e moldura próprios, embaixo da Barra de luz — as cinco lâmpadas no padrão do controle. Ele nasceu ontem como uma <b>linha espremida</b> dentro da moldura da Barra de luz (13 px num campo de 75) e agora é o <b>terceiro campo</b> da coluna. Com ele ali, <b>o número do jogador saiu do título do card</b>, como você pediu. Ele <b>continua nas linhas fechadas</b>, e isso é de propósito: linha fechada não tem lâmpada, e sem o número não sobraria quem aquele controle é.</li>
    <li><b>O touchpad tinha voltado a esticar, e agora ele não estica mais.</b> Ontem a superfície ganhou a proporção do sensor como <b>piso</b>, não como regra — e com um piso ela virou a esponja da coluna: medido hoje na sua mesa, <b>148 × 203</b>, que são <b>2,4 vezes</b> a altura que 148 px de largura pedem num sensor 16:9. A correção de anteontem tinha derrubado 41% de esticada e o piso devolveu 145%. Agora a superfície é <b>148 × 83</b> em qualquer mesa, e quem cresce são a <b>cor</b> da barra e o <b>campo</b> do LED, que não têm proporção a respeitar.</li>
    <li><b>O maior buraco da tela fechou: eram 181 px.</b> Entre o eixo Z do giroscópio e o L2 havia um vazio do tamanho de meio card, e ele não era desenho — era <b>resto</b>: o L2/R2 morava dentro da moldura do giroscópio, colado no pé, e a sobra da coluna inteira empoçava no meio. Ele até mudava de tamanho com a mesa (181 px com os seus dois controles, 95 com quatro). Agora a coluna são <b>dois campos</b>, cada um com rótulo — <b>Sensores</b> e <b>Gatilhos</b> —, e a sobra entra por dentro dos dois abrindo as linhas. Maior vão da coluna: <b>5 px</b>. As cinco colunas continuam terminando na mesma linha.</li>
  </ul>

  <h2>O acordeão, que você pediu em 28/08</h2>
  <ul>
    <li><b>Clicar num abre e fecha os outros</b> — na <b>linha do controle</b> ou no <b>chip da fita</b>, indiferente: é o mesmo gesto. O <b>Todos</b> abre os {len(MESA)}.</li>
    <li><b>Sem uma linha de JavaScript</b>, como você pediu. São {len(MESA) + 1} rádios com o mesmo <code>name</code> — um por controle, mais o do <b>Todos</b> — o navegador já garante que ligar um desliga os outros, que é a regra do acordeão inteira. A linha e o chip são <code>&lt;label for&gt;</code> do <b>mesmo</b> rádio, e é por isso que fita e card não têm como divergir: não há dois estados para manter de acordo, há <b>um</b>, e ele mora no rádio.</li>
    <li><b>A linha fechada mantém o resumo de hoje</b> — máscara, microfone e bateria, mais quem é o controle. O microfone some quando o card abre: ali ele aparece por extenso, com o medidor e o volume, e repetir seria dizer a mesma coisa duas vezes, uma delas pior.</li>
    <li><b>Card e tira viraram um elemento só.</b> Eram duas caixas escritas por duas funções, e o que as impedia de discordar era a linha compartilhada; agora são <b>o mesmo</b> <code>&lt;label&gt;</code> mudando de roupa. A prova de que o texto não anda um pixel na troca é a conta do recuo: fechado, ele começa em 2 (borda) + 26 (padding) = <b>28</b>; aberto, em 2 + 14 (margem) + 1 (borda) + 11 (padding) = <b>28</b>. E a largura útil é <b>1096 px</b> nas duas.</li>
  </ul>

  <h2>Os sensores desceram para cada controle; o Calibrar ficou e cresceu</h2>
  <ul>
    <li><b>O giroscópio e o acelerômetro são estado de cada peça</b>, e por isso o interruptor de cada um está agora na <b>linha do controle</b>, nas {len(MESA)}. Eles estavam no topo do quadro, valendo para a mesa toda — e um interruptor global com {len(MESA)} controles na mesa <b>mente sobre {len(MESA) - 1} deles</b>.</li>
    <li><b>O Calibrar ficou onde estava, e virou gesto de mesa</b> — sua decisão de 29/08: <i>"se conseguirmos fazer funcionar poderíamos deixar ele lá e ele mapearia os {len(MESA)} controles ao mesmo tempo"</i>. <b>Em 31/08 ele mudou de nome e ganhou um irmão</b>, por ordem sua: <i>"o calibrar sensores de movimento, ao invés de mesa"</i> e <i>"o botão Mapa do Controle que abre a interface do mapa do Controle"</i>. <span class="marca">Calibrar Sensores de Movimento</span> diz <b>o que se calibra</b> — o escopo continua no ponteiro. Os dois <b>chegaram a ir para o fim do quadro</b> e você os mandou voltar: <i>"a posição deles volta pro canto superior direito"</i>. E o Calibrar abre uma <b>página nova</b> (<code>calibrar-sensores.html</code>) com o procedimento em três passos e os controles conectados lado a lado.</li>
    <li><b>O par custa {num(LARG_PAR_SENSORES)} px, e só coube porque duas leituras saíram.</b> A linha mais apertada é a do <b>P3</b>, o nome mais longo da mesa: ela tinha <b>{num(VAO_ANTES_P3)} px</b> livres, e o par pede {num(LARG_PAR_SENSORES)} mais o vão. Saíram <span class="marca">Hefesto on</span> ({num(CUSTO_HEFESTO_ON)} px, e dizia a mesma coisa nas {len(MESA)} linhas) e <span class="marca">Giroscópio em rajadas</span> ({num(CUSTO_GIRO_RAJADAS)} px), que juntas devolvem {num(CUSTO_HEFESTO_ON + CUSTO_GIRO_RAJADAS)} — <b>mais</b> do que o par ocupa. Depois da troca a mesma linha do P3 tem <b>{num(VAO_DEPOIS_P3)} px</b> livres ({num(VAO_DEPOIS_P3 - VAO_ANTES_P3)} a mais do que antes) e a do card aberto, {num(VAO_DEPOIS_P1)}.</li>
    <li><b>Você desempatou o "vê como", em 31/08 — e em duas frases.</b> A legenda de 30/08 deixou a contradição aberta: você tinha escrito <i>"remover Giroscópio, Hefesto e vê como"</i> e, no dia anterior, que <i>"a linha fechada mantém o resumo de hoje — máscara, microfone, bateria"</i>. Agora: <i>"remover o vê como de todos os controles"</i> e, logo depois, <i>"era o texto Vê como mas o nome da máscara fica"</i>. <b>Sai o rótulo, fica o dado.</b> A primeira volta tirou o span inteiro e levou a máscara junto — era ler o pedido pela metade. De onde ela vem continua no ponteiro, para quem passar o mouse.</li>
    <li><b>E o que saiu não é o que entrou, embora tenham a mesma palavra.</b> Saiu a <b>leitura</b> <span class="marca">Giroscópio 250 Hz</span>; entrou o <b>interruptor</b> de giroscópio. O número medido não virou lápide: ele está no ponteiro do interruptor, e responde por transporte — <b>250,0 Hz exatos</b> no cabo, <b>em rajadas</b> no rádio.</li>
    <li><b>Os {len(MESA) * 2} botões nascem nos mesmos dois x</b> ({num(X_PAR_SENSORES[0])} e {num(X_PAR_SENSORES[1])}), com <b>{num(LARG_SW)} px</b> cada. Quem iguala é a <b>grade</b>, não o comprimento do rótulo, e quem os prende ali é o <code>margin-left:auto</code>, que saiu da bateria e passou ao par: com os dois pedindo o vão, o flex partiria a sobra ao meio e o grupo flutuaria em {len(MESA)} lugares diferentes.</li>
    <li><b>{ALT_SW} px de altura, e não os {ALTURA_FECHADA} de <code>--h-acao</code>.</b> A linha fechada tem {ALTURA_FECHADA} px por fora e <b>30 por dentro</b> — um botão de {ALTURA_FECHADA} não cabe em 30. Crescer a linha também não era saída: a conta ali embaixo fecha com {PARA_O_CARD - ALTURA_DO_CARD} px de sobra, e {FECHADOS} linhas 6 px mais altas roubariam 18 do card. Não é uma altura inventada: é a mesma pastilha da <b>fita</b> lá em cima (o chip mede 28 a 30 px) e do <b>Perfil ativo</b> (29 px) — que é o que estes botões são, e não botão de decidir.</li>
    <li><b>Clicar no interruptor não abre o card</b> — medido, clicando: o botão vive dentro do <code>&lt;label&gt;</code> que abre o controle, e o navegador não repassa o clique ao rádio quando o alvo é um botão. Clicar em qualquer outro ponto da linha continua abrindo.</li>
  </ul>

  <h2>O que as suas decisões de 28/08 tiraram desta tela</h2>
  <ul>
    <li><b>O aviso de máscara saiu.</b> Ele estava no P2 e dizia que sob Xbox 360 "o giroscópio, o acelerômetro e o touchpad <b>não chegam</b> ao jogo". Você decidiu: <b>nenhum aviso, em máscara nenhuma</b> — e a decisão está certa por um motivo mais forte do que o que eu tinha escrito: a máscara limita o que o <b>jogo</b> recebe, não o que o <b>controle</b> faz. O Hefesto continua acendendo a barra de luz, lendo o giro e capturando o microfone deste DualSense em qualquer máscara.</li>
    <li><b>E o microfone não se perde em máscara nenhuma</b> — é o estado <b>Emulado</b> da ONDA-CONEXOES-06: o Hefesto publica uma fonte de captura virtual, e o jogo a enxerga independentemente da máscara. No rádio isso já existe hoje com outro nome (o DualSense não fala A2DP; o áudio vem dentro do HID e o Hefesto publica a fonte). Nada aqui promete o que não há: esta aba só <b>lê</b> o microfone.</li>
    <li><b>A linha da máscara ganhou o endereço de onde ela se muda</b> — passe o ponteiro: <span class="marca">a escolha é por controle e mora na aba Jogar</span>. Era a única coisa que faltava a quem chegava aqui procurando o seletor.</li>
    <li><b>As três máscaras estão na tela ao mesmo tempo</b>, uma por controle: <b>DualSense</b> (P1 e P3), <b>Xbox 360</b> (P2) e <b>Nintendo Pro</b> (P4). É assim que se aprende que a linha muda de controle para controle. <b>A Nintendo Pro nasce como sprint</b>: o catálogo do produto (<code>uinput_gamepad.FLAVORS</code>) tem hoje <code>dualsense</code> e <code>xbox</code>, e um invariante duro para essa sprint já está medido — o PID forjado <b>não pode ser 0x2009</b>, senão a launch option da Steam esconde o controle físico e o virtual juntos.</li>
    <li><b>Máscara Nintendo Pro não é adotar um Pro.</b> São duas coisas, e confundi-las é o erro clássico daqui: a máscara faz o <i>seu DualSense</i> aparecer como Pro para o jogo. O <b>aparelho</b> Nintendo e o 8BitDo estão <b>fora de escopo agora</b>, por decisão sua — viram sprint própria, e é por isso que nada nesta aba fala de controle externo.</li>
    <li><b>O hexadecimal voltou.</b> Eu o tinha tirado em 27/08 ("cru é para quem programa"); você decidiu que ele <b>fica nas duas</b>, aqui e na Iluminação. Ele está ao lado da barra de luz e <b>não é digitado</b>: sai de <code>core/led_control.py::player_slot_color</code>, a mesma tabela que acende as cinco lâmpadas. O que sobrou da minha razão está no ponteiro: o número é a cor do <b>jogador</b>, não a do plástico.</li>
  </ul>

  <h2>Onde apertou, com o número</h2>
  <ul>
    <li><b>O estado em que a aba abre não rola, e nada some.</b> A conta fecha sem sobra: {VISIVEL} px da caixa menos {PAD_DO_CORPO} de padding são {VISIVEL - PAD_DO_CORPO}; as {FECHADOS} linhas fechadas de {ALTURA_FECHADA} px com {GAP_ENTRE} px entre cada duas caixas somam {FECHADOS * ALTURA_FECHADA + (len(MESA) - 1) * GAP_ENTRE}; sobram <b>{PARA_O_CARD} px</b> para o card, que são os {ALTURA_DO_CARD} dele mais os {PARA_O_CARD - ALTURA_DO_CARD} que ele cresce para não deixar vão.</li>
    <li><b>O passo entre irmãos virou um só.</b> Eram dois — 14 px entre o card e o grupo das tiras, 9 px entre tiras —, porque eram dois containers. Agora as {len(MESA)} caixas são irmãs no mesmo lugar, e o passo é <b>{GAP_ENTRE} px</b> em todos os vãos.</li>
    <li><b>"Todos" abre os {len(MESA)}, e aí a caixa rola {ROLA_EM_TODOS} px.</b> É o único estado desta aba que rola, e é o preço do gesto: {len(MESA)} cards de {ALTURA_DO_CARD} px somam {ALTURA_EM_TODOS} px numa caixa de {VISIVEL - PAD_DO_CORPO}. Não dá para encolher o card — as cinco colunas param todas em <b>236 px</b> de conteúdo natural, e quem manda são duas: a do som (microfone 96 + 9 + alto-falante 131) e a do touchpad (118 + 9 + barra 55 + 9 + LED 45). A dos sensores não manda: com os dois numa moldura só ela pede 228 px, e sobra.</li>
    <li><b>E o preço, dito inteiro:</b> nesse estado o P1 aparece todo, o P2 aparece pela metade (141 px dos 301) e o <b>P3 e o P4 começam com zero pixel à mostra</b>. O que diz que eles estão ali são três coisas, e as três estão na tela: o chip <b>Todos</b> aceso, o <span class="marca">{len(MESA)} controles</span> do cabeçalho e a <b>barra de rolagem</b>, que nasce junto com a rolagem e ocupa 10 px. Foi por isso que a barra precisou de regra própria — a do Chrome é sobreposta e some quando ninguém está rolando, e aí seria o defeito de 27/08 de volta com outra roupa.</li>
    <li><b>2×2 foi medido e é pior.</b> Meio card tem 515 px de largura útil para cinco colunas que pedem 884; viraria três fileiras e cada card passaria a ~545 px de altura — aí só <b>um</b> aparece de cada vez.</li>
    <li><b>O corpo fechado não pode ser <code>display:none</code>, e o motivo é a régua.</b> Ela lê a altura de todo botão e reprova família com alturas divergentes; com <code>display:none</code> os dois botões de rota de cada card fechado medem <b>0</b>, e ela acusa <span class="marca">altura divergente em button.-: 0 / 36</span> — um defeito que só existiria porque o elemento sumiu. Com <code>height:0;overflow:hidden</code> o corpo continua <b>desenhado</b> no tamanho natural e só recortado: a régua segue medindo os <b>{len(MESA)}</b> cards por dentro, não só o que está à mostra. Ela ficou mais severa, não menos.</li>
    <li><b>As {len(MESA)} barras de bateria têm a mesma largura, e isso é leitura e não capricho.</b> Elas <i>esticavam</i> para ocupar o vão de cada linha, e os trilhos mediram <b>312, 60, 35 e 139 px</b>. O preenchimento é uma porcentagem do trilho: o <b>31%</b> do P3 num trilho de 35 px desenhava uma barra <b>menor</b> que o <b>64%</b> do P2 num de 60 — quatro réguas de tamanhos diferentes que o olho compara e lê errado. Agora são <b>{LARG_BATERIA} px</b> nas {len(MESA)}, e a mais apertada (a do P3) tem 13,7 px de folga.</li>
    <li><b>A conta é um portão.</b> Se um dia a mesa crescer a ponto de o card aberto não caber, o gerador <b>para</b> com o número na mão, em vez de entregar de novo uma tela que esconde controle calada.</li>
    <li><b>Cicatriz: a classe não pode se chamar <code>tira</code>.</b> <code>.tira</code> é a <b>fila de abas</b> do esqueleto (<code>topo.html:109</code>). Com a regra deste arquivo batizada assim, <code>height:34px</code> e <code>text-transform:uppercase</code> caíam na fila de abas lá em cima: o cabeçalho encolheu 8 px e o miolo desta aba mediu <b>550 px contra os 542 de todas as outras nove</b> — e a régua de alinhamento passou <b>verde</b>. A classe se chama <code>.ctl</code>.</li>
  </ul>

  <h2>O que vem do mapa, em vez de digitado</h2>
  <ul>
    <li><b>A cor do plástico é variável, não classe.</b> Eram duas classes com o hexadecimal escrito no CSS — com os 28 modelos do <code>docs/data/cores-do-dualsense.csv</code> seriam vinte e oito. Cada caixa nasce com <code>--plastico</code>, lido do <b>desenho</b> por <code>monta.cor_da_zona()</code>: a borda, o círculo dos analógicos, a cruz de eixos, o rótulo L3/R3 e os glifos ✕ · L2 · R2 vêm todos dela. O vermelho digitado era <code>#b11f54</code>; a amostragem do seu aparelho devolveu <code>#A51C48</code>, distância 17.</li>
    <li><b>A taxa do giroscópio responde por transporte.</b> Estava <span class="marca">~194 Hz</span> nos dois cards, e o 194 não aparece em nenhuma linha da referência canônica. No cabo são <b>250,0 Hz exatos</b>, com três fontes concordando; no rádio a leitura chega <b>em rajadas</b>, de 38 a 392 Hz de média entre janelas seguidas do mesmo controle. Passe o ponteiro na linha.</li>
    <li><b>Uma regra de cor para os {len(MESA)}.</b> O par <code>.card.c-blue .gb.on</code> pintava o botão <i>aceso</i> do controle azul da mesma cor do plástico dele — as duas informações ficavam indistinguíveis. Agora <span class="marca">plástico</span> e <span class="marca">acendeu agora</span> são sempre duas cores diferentes, em qualquer modelo.</li>
    <li><b>Os dois interruptores de sensor têm a mesma largura.</b> Soltos, o rótulo mandaria: <b>Giroscópio</b> e <b>Acelerômetro</b> mediam <b>100</b> e <b>115,8 px</b> em fila. Agora é a <b>grade</b> que manda — os dois em {num(LARG_SW)} px —, e como o par é o mesmo nas {len(MESA)} linhas, os {len(MESA) * 2} botões caem nos mesmos dois x. Nenhum número de controles está escrito no gerador.</li>
    <li><b>Um laço só, sobre a mesma mesa.</b> Eram dois — um para os cards, outro para as tiras —, e agora é <b>um</b>: é assim que se sabe que a caixa é uma só. A palavra "quatro" continua fora do gerador; no dia em que a mesa tiver três ou cinco, esta aba acompanha sozinha.</li>
  </ul>

  <h2>Ainda aberto</h2>
  <ul>
    <li><b>Os 16 quadradinhos viram o desenho do DualSense?</b> A pergunta é sua, do contrato da aba. A medição pende para os quadradinhos: a coluna deles tem 212 px e é a única das cinco que ainda estica sem estourar — o desenho inteiro do controle nessa largura empurraria o card muito além dos {ALTURA_DO_CARD} px, e o card tem exatamente <b>{PARA_O_CARD - ALTURA_DO_CARD} px</b> de folga.</li>
    <li><b>O botão de mic do controle muda o mudo do PC inteiro?</b> O campo existe no perfil e o daemon já o aplica, sem nenhuma tela que o escreva (<code>profiles/schema.py:451</code>).</li>
    <li><b>Histórico de bateria.</b> O diário grava por controle desde sempre e ninguém lê (<code>daemon/battery_journal.py:214</code>). Com {len(MESA)} na mesa o P3 já aparece em 31%.</li>
    <li><b>O acelerômetro está desenhado e não é pintado ao vivo.</b> Os três eixos em <b>g</b> aparecem no card, mas a ponte que dá vida a esta aba só escreve os do giroscópio: ela procura o endereço <code>acel-x</code> e a tela escreve <code>accel-x</code>, com dois cc (<code>controles_vivos.py:1340</code>). Com o daemon ligado, esses números ficam <b>parados</b> na medição de 30/08 em vez de acompanharem o aparelho — e número parado tem a mesma cara de número lido. A cura é de uma linha, mas mora fora deste gerador; fica dito aqui porque quem fotografar a aba não tem como notar.</li>
    <li><b>A régua não vê o "Todos".</b> Ela mede a página como ela abre, e a página abre com um card e {FECHADOS} linhas — nenhum quadro escondido, nenhuma rolagem. O estado que rola só existe depois de um clique, e a régua de arranjo não clica. Medi-o à mão, clicando, e os números estão acima; fica dito, porque a régua não é minha para mexer.<br><br><b>Fechou:</b> esta legenda avisava que o <code>olhar.py</code> escondia a barra de rolagem e que ela não sairia na foto. Não é mais verdade — a ferramenta foi curada em 30/08 e hoje fotografa a barra, os <b>10 px</b> que ela ocupa no "Todos" inclusive.</li>
  </ul>
</div>

</body>
</html>
'''


# ---------------------------------------------------------------------------
# A LEGENDA NÃO PROMETE O QUE A TELA NÃO TEM — 31/08/2026.
#
# POR QUE ELA EXISTE, e o caso é deste arquivo: em 29/08 a legenda anunciou o
# botão `Liberar` do microfone como a novidade do dia. Em 31/08 ela ainda o
# anunciava — e o botão tinha saído do desenho por decisão dela. Nada reprovou:
# a legenda é texto solto dentro de uma f-string, e a régua de arranjo mede
# CAIXAS, não frases. Uma legenda que anuncia um botão que a tela não tem é o
# mesmo defeito que esta aba persegue o dia inteiro — *a prosa afirma o que o
# produto não faz* —, só que virado para dentro.
#
# COMO ELA MEDE, e por que assim: um termo de tela citado na legenda tem de
# aparecer no MIOLO, que é o desenho de verdade. A licença para nomear o que
# saiu é uma só e é explícita — `<li class="foi">`, a lápide —, porque registrar
# uma remoção é diferente de anunciar uma novidade, e a diferença tem de estar
# no HTML e não na boa vontade de quem lê.
#
# A SEGUNDA REGRA é a data: um `<h2>` não pode dizer "hoje" nem "ontem". Foi
# "O que mudou hoje, 29/08" que envelheceu calado por dois dias. Data relativa
# em título é uma afirmação que se torna falsa sozinha, sem ninguém editar nada.
#
# MORDIDA: tire o `class="foi"` da lápide do `Liberar` e o gerador para.
# ---------------------------------------------------------------------------
# Os termos são os RÓTULOS que a aba desenha — o que ela chama de botão, campo
# ou estado. Nome de classe ou de `data-*` não entra: a legenda fala com ela, e
# ela lê o que está escrito na tela.
TERMOS_DA_TELA = (
    "Liberar", "Sons do jogo", "Todo o som do PC",
    "Calibrar sensores de movimento", "Mapa do Controle", "Dispositivos Conectados",
    "Sem toque", "Tocando", "LED do jogador", "Barra de luz", "Touchpad",
    "Microfone", "Alto-falante", "Gatilhos", "Giroscópio",
    "Acelerômetro", "Virtual", "Nativo",
)


def a_legenda_nao_promete_o_que_a_tela_nao_tem(legenda, miolo):
    """Reprova a legenda que cita rótulo ausente do desenho, ou data relativa em título.

    Ela roda ANTES de escrever o arquivo: um gerador que já gravou e depois
    reclama entrega a tela errada de qualquer jeito.

    CICATRIZ, e ela nasceu na primeira execução: o miolo tem COMENTÁRIOS de
    HTML, e um deles diz *"o vão que o `Liberar` deixou"*. Sem cortá-los, a
    régua achou a palavra e deu VERDE sobre a legenda que eu tinha acabado de
    escrever errado de propósito — comentário de código não é tela, e a régua
    que confunde os dois mede o arquivo, não o desenho. Os `title=` FICAM: dica
    é texto que ela lê na tela.
    """
    miolo = re.sub(r"<!--.*?-->", "", miolo, flags=re.S)
    for titulo in re.findall(r"<h2>(.*?)</h2>", legenda, re.S):
        if re.search(r"\b(hoje|ontem|anteontem)\b", titulo, re.I):
            raise SystemExit(
                f'ERRO na legenda: o título "{titulo}" usa data relativa.\n'
                "  Um <h2> tem de dizer a data que descreve — foi assim que\n"
                '  "O que mudou hoje, 29/08" continuou dizendo "hoje" em 31/08.'
            )
    for item in re.findall(r"<li\b([^>]*)>(.*?)</li>", legenda, re.S):
        atributos, corpo = item
        classes = " ".join(re.findall(r'class="([^"]*)"', atributos or "")).split()
        if "foi" in classes:
            continue                      # lápide: tem licença para nomear o que saiu
        for termo in TERMOS_DA_TELA:
            if termo in corpo and termo not in miolo:
                raise SystemExit(
                    f'ERRO na legenda: ela cita "{termo}" e o desenho não escreve\n'
                    "  esse rótulo em lugar nenhum. Ou o termo volta à tela, ou o\n"
                    '  item vira lápide (<li class="foi">) dizendo que ele SAIU.\n'
                    f"  O item: {re.sub(r'<[^>]+>', '', corpo)[:110]}…"
                )


# ---------------------------------------------------------------------------
# A FITA VIRA CLICÁVEL, E SÓ NESTA ABA.
#
# `monta.fita()` escreve `<span class="chip …">`, e ele é o dono da fita nas DEZ
# abas: mudá-lo lá mudaria as outras nove, que não pedem acordeão — e `monta.py`
# não é meu para mexer. Aqui os chips desta aba (e só os desta) passam a apontar
# para os MESMOS rádios que a linha do controle aciona. É o que faz clicar na
# fita e clicar no card serem o mesmo gesto, sem uma linha de JavaScript.
#
# O `on` que o gerador escreveu no chip do alvo SAI. Ele é uma foto de quem era o
# alvo na hora de gerar; quem acende agora é o estado vivo, senão o P1 ficaria
# aceso para sempre com o card do P3 aberto ao lado.
#
# ISTO NÃO É EDITAR O HTML À MÃO: é o gerador terminando a sua própria saída,
# com âncora asserida — se a fita mudar de forma, o gerador PARA em vez de
# entregar uma fita que não clica, calada. Foi assim que a fita viva morreu sem
# sintoma em 27/08, e a lição é a mesma.
# ---------------------------------------------------------------------------
def fita_clicavel(doc, mesa=None):
    # OS RÁDIOS SÃO OS DA MESA — 31/08/2026, quando ela mandou deixar dois
    # controles desconectados. A fita só desenha chip de quem está conectado
    # (`monta.fita()`), e um `id` a mais aqui faz a régua abaixo reprovar com
    # `3 chips para 5 rádios`. Foi ela quem pegou a propagação incompleta.
    #
    # `mesa` É PARA O PILOTO, e o padrão `None` mantém o mockup byte-idêntico.
    # Trocar `aba02.MESA` de fora NÃO alcança aqui: `CONECTADOS` é derivado de
    # `MESA` no IMPORT e nunca recalculado — a mesma armadilha que fazia a fita
    # do produto mostrar dois controles do mockup com UM no cabo (01/09/2026).
    ids = ["c-todos"] + [f'c-{c["pref"]}' for c in (CONECTADOS if mesa is None else mesa)]
    linhas = doc.split("\n")
    achados = 0
    for k, linha in enumerate(linhas):
        s = linha.strip()
        if not s.startswith('<span class="chip'):
            continue
        if achados >= len(ids):
            raise SystemExit("ERRO na fita: mais chips do que controles na mesa")
        if not s.endswith("</span>"):
            raise SystemExit(f"ERRO na fita: o chip {achados} não fecha na mesma linha")
        rid = ids[achados]
        achados += 1
        m = re.match(r'<span class="chip([^"]*)"([^>]*)>(.*)</span>$', s)
        if not m:
            raise SystemExit(f"ERRO na fita: o chip {rid} mudou de forma —\n  {s[:120]}")
        classe = m.group(1).replace(" on", "")
        resto, dentro = m.group(2), m.group(3)
        # O NOME DO PLÁSTICO E O TRANSPORTE GANHAM ENDEREÇO NO CHIP — 03/09/2026.
        #
        # A FITA JÁ SE TROCA INTEIRA a cada tique (`hefesto_vivo.py`,
        # `carga["fita"] = _fita(ctx.mesa)`), e enquanto ela se troca estes dois
        # `<span>` nem existem — o `achar()` não encontra nada e ninguém escreve.
        # ELES SÃO PARA QUANDO A TROCA NÃO ACONTECE, e ela deixa de acontecer o
        # tempo todo: `_fita` devolve `""` se UM controle da mesa vier sem cor
        # (`if not mesa or any(not c.get("cor") for c in mesa)`), e pelo rádio a
        # cor não é lida — o mapa de canais diz `identidade.cor_do_aparelho`,
        # `radio_aciona = não`. Com um controle no cabo e outro no rádio, que é a
        # mesa dela, a fita FICA COM O DESENHO: `Cosmic Red` e `Starlight Blue`.
        # Com o endereço, o pacote pinta o nome certo mesmo quando o bloco não
        # pôde ser trocado — que é exatamente o buraco que ela viu.
        #
        # A DIVISÃO É A DE `monta.fita()` e é asserida: `P<n> • <nome> • <via>`.
        # Se ela mudar, o gerador PARA aqui em vez de entregar um chip sem
        # endereço, calado — a mesma cicatriz de 27/08 que este arquivo já carrega.
        if classe.strip():          # o "Todos" não tem plástico nem nome de peça
            partes = dentro.split(SEPARADOR)
            if len(partes) != 3:
                raise SystemExit(
                    f"ERRO na fita: o chip {rid} não é `P<n> • <nome> • <via>` —\n  {dentro[:120]}")
            dentro = SEPARADOR.join([
                partes[0],
                f'<span data-campo="fita-peca">{partes[1]}</span>',
                f'<span data-campo="fita-via">{partes[2]}</span>',
            ])
        # o `title` do chip ganha o que ele passou a fazer; o "Todos", que não
        # tinha nenhum, ganha o seu.
        #
        # E O NOME DA COR SAI DO `title`. Ele era a SEGUNDA cópia congelada do
        # mesmo fato — `monta.fita()` escreve `title="{nome} — a borda é a cor do
        # plástico"` —, e um `title` não tem alvo de pintura no piloto (os sete
        # são texto·largura·fundo·valor·html·classe·cor). Duas cópias de um dado
        # em que só uma é alcançável é a forma exata de a dica sobreviver ao
        # conserto do texto e continuar dizendo `Cosmic Red` na mesa dela.
        if 'title="' in resto:
            resto = re.sub(
                r'title="[^"]*"',
                'title="Clique para abrir o card dele — a borda é a cor do plástico."',
                resto, count=1)
        else:
            resto += f' title="Abre os {len(MESA)} cards de uma vez — e aí a caixa rola."'
        novo = f'<label for="{rid}" class="chip{classe}"{resto}>{dentro}</label>'
        linhas[k] = linha.replace(s, novo)
    if achados != len(ids):
        raise SystemExit(f"ERRO na fita: {achados} chips para {len(ids)} rádios")
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# A COR DO PLÁSTICO SAI DO `style=` E VIRA REGRA — 03/09/2026
# ---------------------------------------------------------------------------
# A LEI É DELA: *"se identificou o controle como modelo White a cor do card em
# volta tem que ser branco. Temos isso no mapa."*
#
# O QUE ESTAVA NO CAMINHO, e é CSS e não opinião: `--plastico` morava no
# `style=` de cada caixa e de cada chip. **Estilo de linha vence qualquer folha
# de estilo**, então o produto não tinha como reescrever a cor da borda sem
# reescrever o atributo — e ele não tem alvo para isso: os sete do piloto são
# texto · largura · fundo · valor · html · classe · cor, e nenhum escreve
# propriedade personalizada (`hefesto_vivo.py`, a função `escrever`).
#
# ENTÃO A COR DO DESENHO VIRA REGRA, numa folha que o produto TROCA INTEIRA:
#
#     <style data-campo="plastico-css" data-hef-alvo="html">
#
# Ela nasce com o que ELA aprovou (sai da MESA), e é isso que a bancada mostra.
# Com o daemon vivo, o `escrever` do piloto substitui o `innerHTML` dela pelo
# que `pacotes.a02_controles.folha_do_plastico` monta da mesa LIDA.
#
# ERAM DUAS FOLHAS ATÉ 03/09/2026 — a do desenho e uma vazia por cima —, E O
# BURACO ESTÁ MEDIDO. Duas folhas só se sobrepõem no assento que a segunda
# NOMEIA. Com um controle só na mesa (P1 White), o produto escrevia uma regra
# para o `p1` e o `p2` ficava com o `#7eb8d4` do desenho: **Starlight Blue num
# assento onde não há controle nenhum** — medido no WebKitGTK desta máquina,
# `getComputedStyle(.ctl[data-controle="p2"]).borderTopColor` →
# `rgb(126, 184, 212)`. É exatamente a mentira que a lei dela veio matar.
#
# Uma folha só não tem esse buraco: o que a troca não escreve, deixa de existir.
#
# ISTO NÃO É EDITAR O HTML À MÃO: é o gerador terminando a própria saída, com
# âncora asserida, exatamente como o `fita_clicavel` acima. E ele roda só no
# `__main__`: `controles_vivos.py` chama `bloco()` direto para montar a mesa
# VIVA, e ali o `style=` de linha é o valor LIDO — tirá-lo de lá apagaria a cor
# de um piloto que não é meu.
CAIXA_COM_COR = re.compile(
    r'(<div class="ctl card") style="--plastico:(#[0-9a-fA-F]{3,8})"( data-controle="([^"]+)")')
# O `style` NÃO ESTÁ MAIS COLADO NO `class`, e por isso esta âncora tinha de
# afrouxar — 03/09/2026. Ela era `class="chip plastico") style="--plastico:…`,
# com os dois atributos vizinhos, e `monta.fita()` passou a escrever
# `data-campo="fita-chip"` ENTRE eles (a versão da frente do rádio, integrada
# hoje). Resultado medido nesta árvore, na ponta de `dev`: `python3 aba02.py`
# morria com `ERRO no plástico: 2 caixa(s) e 0 chip(s)` e **a bancada não podia
# mais ser reproduzida pelo próprio gerador** — o `mockup/02-controles.html` no
# disco veio de uma execução ANTERIOR à mudança da fita.
#
# E O PREÇO DE UMA ÂNCORA QUE MORRE NO MEIO É MAIOR QUE O ERRO: `monta()` GRAVA
# o arquivo, e só depois este pós-processamento o relê e o regrava. Quem
# rodasse o gerador ficava com a bancada dela **meio pronta no disco** — sem as
# duas folhas de plástico e com a fita ainda em `<span>` —, e o erro no
# terminal não dizia isso.
#
# `[^>]*?` É PREGUIÇOSO DE PROPÓSITO: ele para no PRIMEIRO ` style="--plastico:`
# da tag, e não engole o `>`. A âncora continua exigindo o `<label for="c-…"
# class="chip plastico"`, que é a forma que `fita_clicavel` garante uma linha
# acima — afrouxar o meio não afrouxa o que ela mede.
CHIP_COM_COR = re.compile(
    r'(<label for="(c-[^"]+)" class="chip plastico"[^>]*?)'
    r' style="--plastico:(#[0-9a-fA-F]{3,8})"')

#: O PISO DO PLÁSTICO — a cor de quem a folha NÃO nomeia, e ele é a metade
#: que faz a troca inteira ser segura.
#:
#: `.ctl{border:2px solid var(--plastico)}` usa uma `var()`, e uma `var()` sem
#: valor **invalida a declaração inteira, em silêncio**: a borda não fica cinza,
#: ela deixa de existir. Está medido neste próprio arquivo, no comentário do
#: `.ctl.off` — a foto mostrou dois lugares soltos, sem caixa nenhuma. Sem este
#: piso, um assento que a mesa VIVA não nomeia perderia a borda ao invés de
#: ficar neutro.
#:
#: A ESPECIFICIDADE É A MESMA das regras por assento — `.ctl[data-controle]` e
#: `.ctl[data-controle="p1"]` valem (0,2,0) —, então quem decide é a ORDEM, e
#: por isso o piso vem PRIMEIRO na folha. Nenhum `!important` no caminho.
#:
#: O TOM É O TOKEN QUE O LUGAR VAZIO JÁ USA (`.ctl.off{border:1px solid
#: var(--border-forte)}`), e é o mesmo `BORDA_SEM_COR` do lado do produto
#: (`pacotes/a02_controles.py`). Não é cor nova: é o "nada" que a regra dela
#: manda mostrar quando não se leu cor nenhuma.
PISO_DO_PLASTICO = ".ctl[data-controle],.fita .chip[for]{--plastico:var(--border-forte)}"


def seletor_do_plastico(pref: str) -> str:
    """Os dois lugares onde o plástico de um assento pinta: a caixa e o chip.

    UM SELETOR SÓ PARA OS DOIS, e não dois — é a mesma forma que
    `pacotes.a02_controles.folha_do_plastico` escreve com a mesa VIVA. Duas
    gramáticas para a mesma regra é o que faz a folha do produto e a do desenho
    divergirem sem ninguém ver; o
    `test_a_cor_do_plastico_da_02_vem_do_aparelho` compara as duas.
    """
    return f'.ctl[data-controle="{pref}"],.fita .chip[for="c-{pref}"]'


def cor_do_plastico_por_regra(doc):
    """Tira o `--plastico` cravado do `style=` e o devolve como folha VIVA."""
    das_caixas: dict[str, str] = {}
    dos_chips: dict[str, str] = {}

    def _caixa(m):
        das_caixas[m.group(4)] = m.group(2)
        return m.group(1) + m.group(3)

    def _chip(m):
        dos_chips[m.group(2).removeprefix("c-")] = m.group(3)
        return m.group(1)

    doc, caixas = CAIXA_COM_COR.subn(_caixa, doc)
    doc, chips = CHIP_COM_COR.subn(_chip, doc)
    # A ÂNCORA. Uma caixa ou um chip que mude de forma faz a troca casar ZERO
    # vezes — e o resultado seria uma página com a cor congelada de volta, verde
    # em todo portão. Régua que acha zero é ERRO, não silêncio.
    if caixas != len(CONECTADOS) or chips != len(CONECTADOS):
        raise SystemExit(
            f"ERRO no plástico: {caixas} caixa(s) e {chips} chip(s) com cor cravada, "
            f"e a mesa tem {len(CONECTADOS)} conectado(s) — a forma mudou.")
    # A CAIXA E O CHIP DO MESMO ASSENTO SÃO O MESMO PLÁSTICO. Se divergirem, o
    # seletor único calaria uma das duas cores — e a página sairia mostrando uma
    # divergência que ninguém veria.
    if das_caixas != dos_chips:
        raise SystemExit(
            f"ERRO no plástico: as caixas dizem {das_caixas} e os chips dizem "
            f"{dos_chips} — o mesmo assento com duas cores.")
    if "--plastico:#" in doc.split("</head>", 1)[-1]:
        raise SystemExit("ERRO no plástico: sobrou cor cravada no corpo da página")
    regras = [PISO_DO_PLASTICO] + [
        f"{seletor_do_plastico(pref)}{{--plastico:{cor}}}"
        for pref, cor in das_caixas.items()
    ]
    folha = ('<style data-campo="plastico-css" data-hef-alvo="html">\n'
             + "\n".join(f"  {r}" for r in regras)
             + "\n</style>\n")
    if "</head>" not in doc:
        raise SystemExit("ERRO no plástico: a página não tem `</head>`")
    return doc.replace("</head>", folha + "</head>", 1)


# ESCREVER O ARQUIVO É O `__main__`, E NÃO O IMPORT (29/08/2026).
#
# `regerar.py:31` chama este arquivo por `subprocess` — o portão continua o
# mesmo. O que muda é que `bloco()`, `identidade()` e `grade()` passam a poder
# ser IMPORTADOS por quem monta a mesa VIVA a partir do daemon: sem esta linha,
# um `import aba02` regeraria o `02-controles.html` da mesa fixa de quatro no
# meio da execução do produto — reescrevendo, calada, a especificação aprovada
# por ela.

def _conferir(doc):
    """As decisões dela de 31/08 nesta aba, conferidas NA SAÍDA.

    SÓ O MIOLO, e sem comentário HTML. A régua da aba Jogar nasceu errada duas
    vezes pela mesma família — casou o nome do produto no cabeçalho, oito
    citações na legenda e o próprio comentário que a explicava. É a armadilha do
    `COMO-OLHAR-A-TELA.md`: *"régua que casa um token em qualquer lugar do texto,
    em vez do campo que o significa"*. Aqui ela já nasce sabendo.
    """
    corpo = doc.split('<div class="miolo">', 1)[-1].split('<div class="nota">', 1)[0]
    corpo = re.sub(r"<!--.*?-->", "", corpo, flags=re.S)
    if len(corpo) < 2000:
        raise SystemExit("ERRO: a régua não achou o miolo — régua que mede 0 "
                         "caractere passa com qualquer desenho.")
    # A FOLHA É LIDA À PARTE, e de propósito: o `corpo` acima é o MIOLO, e as
    # regras de estilo moram no `<style>` do cabeçalho. Uma régua de CSS que
    # procurasse no miolo daria verde sobre folha nenhuma — que é a família de
    # régua cega que esta casa já pagou. O casamento é do SELETOR INTEIRO, não
    # de um token solto.
    folha = doc.split("<style", 1)[-1].split("</style>", 1)[0]
    if len(folha) < 2000:
        raise SystemExit("ERRO: a régua não achou a folha de estilo — régua que "
                         "mede 0 caractere passa com qualquer desenho.")
    falhas = []

    def exigir(cond, oque):
        if not cond:
            falhas.append(oque)

    # 0. O LUGAR VAZIO NÃO PODE MOSTRAR O DESENHO. As três regras que apagam a
    #    bateria, a luz e os sensores de um assento sem controle. Sem elas a
    #    linha do P2 volta a exibir 64% de bateria e dois chips VERDES com o
    #    cabeçalho dizendo `1 controle` — medido em 03/09/2026, 89,9 px de
    #    140,5. Elas pendem do `data-conectado`, que é o que o piloto mantém.
    exigir('.ctl[data-conectado="nao"] .bat .cheio' in folha
           and "width:0 !important" in folha,
           "a barra de bateria do lugar vazio voltou a mostrar o pixel do "
           "mockup — um assento sem controle não tem bateria")
    exigir('.ctl[data-conectado="nao"] .sensores-peca .sw{' in folha,
           "os chips de sensor do lugar vazio voltaram ao verde de ligado — "
           "um assento sem controle não tem giroscópio")
    exigir('.ctl[data-conectado="nao"] .barra-luz' in folha,
           "a barra de luz do lugar vazio voltou a acender com a cor do mockup")

    # 1. "Conectados" virou "Dispositivos Conectados".
    exigir(">Dispositivos Conectados</span>" in corpo, "o título novo sumiu")
    exigir(">Conectados</span>" not in corpo, "o título antigo voltou")

    # 2. O "Desativado" do microfone saiu. *"remove o desligado (fica desligado
    #    com slicer no zero)"* — o slider em 0 é o que desliga.
    exigir('data-mic-modo="desativado"' not in corpo, "o Desativado do microfone voltou")
    exigir(corpo.count('data-mic-modo="') == 2 * len(CONECTADOS),
           "os modos do microfone não são 2 por controle conectado")
    # 2b. OS DOIS MODOS TÊM QUEM OS ATENDA, e o container NÃO é endereço de
    #     pintura. As duas metades da cura de 01/09/2026, e as duas mordem:
    #     sem `data-gesto` os botões chegam ao despachante chamando-se `clique`
    #     e o gesto recusa; com `data-campo` no `<span>` que os envolve, o
    #     primeiro tique da pintura os troca por um travessão — medido, 4
    #     botões antes e 0 depois.
    exigir(corpo.count('data-gesto="mic-modo"') == 2 * len(CONECTADOS),
           "os modos do microfone perderam o `data-gesto` — chegam como 'clique'")
    exigir('data-campo="mic-modo"' not in corpo,
           "o `data-campo` voltou ao container dos modos do microfone: a "
           "pintura vai apagar os dois botões")

    # 2c. A BATERIA TEM ENDEREÇO, os DOIS. Sem eles o número e a barra ficam
    #     nos 100% / 64% que este gerador desenhou, com o controle dela em
    #     qualquer carga — e nada na tela diz que aquilo é do mockup.
    #     A régua mora AQUI e não no piso do casamento porque lá ela não morde:
    #     a aba casa 10 endereços contra um piso de 9, então perder UM passa.
    for campo in ("bateria", "bateria-barra"):
        exigir(corpo.count(f'data-campo="{campo}"') == len(CONECTADOS),
               f"a bateria perdeu o endereço `{campo}` — o número volta a ser "
               f"o do desenho")

    # 2d. CADA BARRA COM O SEU ALVO, e a régua deixou de contar por atacado.
    #     Ela era `corpo.count('data-hef-alvo="largura"') == len(CONECTADOS)`,
    #     e isso não olhava a barra da BATERIA: olhava se existiam N larguras
    #     no documento inteiro. Endereçar a barra do VOLUME (decisão dela de
    #     02/09, item 16) fez a conta dar o dobro e a régua reprovou uma
    #     ENTREGA — que é a forma exata do defeito que esta casa chama de
    #     "régua que cimenta o que existia".
    #
    #     Agora ela olha o ELEMENTO: todo `data-campo` desta lista tem de
    #     carregar o seu alvo, e nenhum outro. MORDE de verdade — tirar o
    #     `data-hef-alvo` de UMA das barras reprova nomeando qual, o que a
    #     contagem global não fazia (ela passaria com a largura no lugar
    #     errado, desde que o total batesse).
    for campo, alvo in (("bateria-barra", "largura"), ("alto-barra", "largura"),
                        ("luz-cor", "cor"), ("touch-ponto", "classe")):
        tags = re.findall(r'<[^>]*data-campo="' + re.escape(campo) + r'"[^>]*>', corpo)
        exigir(len(tags) == len(CONECTADOS),
               f"o endereço `{campo}` não está nos {len(CONECTADOS)} cards")
        errados = [t for t in tags if f'data-hef-alvo="{alvo}"' not in t]
        exigir(not errados,
               f"`{campo}` perdeu o `data-hef-alvo={alvo}` em {len(errados)} "
               f"card(s): a pintura vai escrever o valor como TEXTO dentro do "
               f"elemento, em vez de mexer no que ele desenha")

    # 3. O "· 100 % · Acordado" saiu do rótulo do alto-falante.
    exigir("Acordado" not in corpo, "o estado do alto-falante voltou ao rótulo")

    # 4. TRÊS molduras, e as unidades fora. *"É pra ser 3: um Giroscópio, outra
    #    Acelerômetro e outra gatilhos."*
    for b in ("giroscopio", "acelerometro"):
        exigir(f'data-bloco="{b}"' in corpo, f"a moldura {b} sumiu")
    exigir(">Sensores" not in corpo, "a moldura única 'Sensores' voltou")
    for u in (">°/s<", "Acelerômetro <span"):
        exigir(u not in corpo, f"uma unidade voltou ao rótulo do sensor: {u!r}")

    # 5. A mesa: os conectados abrem, os vazios não. *"tiramos o modo p3. p4
    #    (seções expandidas não aparecem)"* — sem `<input>` não há o que expandir.
    exigir(corpo.count('data-conectado="nao"') == VAZIOS,
           f"os lugares vazios não são {VAZIOS}")
    for pedaco in corpo.split('class="ctl off"')[1:]:
        exigir("<input" not in pedaco.split("</div>")[0],
               "um lugar vazio ganhou rádio — ele abriria")

    # 6. OS DOIS BOTÕES, e eles apontam para páginas que EXISTEM. Um botão que
    #    abre o nada é pior que nenhum botão.
    for destino, rot in (("calibrar-sensores.html", "Calibrar sensores de movimento"),
                         ("mapa-do-controle.html", "Mapa do Controle")):
        exigir(f'href="{destino}"' in corpo, f"o botão {rot!r} sumiu")
        exigir(onde.pagina(destino).exists(),
               f"o botão {rot!r} aponta para {destino}, que NÃO existe na bancada")
    exigir("Calibrar sensores da mesa" not in corpo, "o nome antigo do Calibrar voltou")
    exigir(">Calibrar Sensores de Movimento</a>" in corpo,
           "o rótulo do Calibrar não é o que ela escreveu")
    # E ELES MORAM NO CABEÇALHO, não no fim — *"a posição deles volta pro canto
    # superior direito."* Já estiveram nos dois lugares nesta mesma sessão.
    topo = corpo.split('<div class="quadro-corpo">', 1)[0]
    exigir('href="calibrar-sensores.html"' in topo and 'href="mapa-do-controle.html"' in topo,
           "os dois botões saíram do canto superior direito")
    exigir("acoes-da-mesa" not in corpo, "o bloco de ações do FIM do quadro voltou")

    # 7. OS MODOS DO MICROFONE FICAM ABAIXO DO SLIDER, na mesma fileira do som —
    #    *"os botões Virtual e Nativo ficam na parte de baixo do slider, igual o
    #    Sons do Jogo e Todo o som do PC."* A régua olha a CLASSE, que é o que
    #    faz os dois serem o mesmo botão: `class="rota mic-modo"`.
    #    A ORDEM SE MEDE COM `find`, NUNCA COM `index` — a primeira versão desta
    #    régua usava `index` e, quando a classe sumia, ela ESTOURAVA com
    #    `ValueError` em vez de acusar. Na mordida isso é indistinguível de uma
    #    régua que não pegou nada: o gerador morreu, e a mensagem que ele devia
    #    imprimir nunca saiu. Régua que quebra não diz o que está errado.
    tem_rota = 'class="rota mic-modo"' in corpo
    exigir(tem_rota, "os modos do microfone não estão na fileira `.rota` do som")
    if tem_rota:
        for pedaco in corpo.split('data-bloco="microfone"')[1:]:
            i_vol, i_rota = pedaco.find('class="vol"'), pedaco.find('class="rota mic-modo"')
            exigir(0 <= i_vol < i_rota,
                   "os modos do microfone voltaram para ACIMA do slider")

    # 8. O TEXTO "vê como" SAIU E A MÁSCARA FICOU. As duas metades, porque a
    #    primeira volta tirou o span inteiro e levou o dado junto.
    exigir("vê como" not in corpo, "o texto 'vê como' voltou")
    exigir(corpo.count('data-campo="mascara"') == len(CONECTADOS),
           "a máscara sumiu com o texto — ela FICA, e é o dado")

    # 9. A IDENTIDADE VEM DA FITA, E NÃO DO MOCKUP — 03/09/2026, lei dela.
    #    As quatro exigências são as quatro portas por onde o desenho voltava a
    #    mandar na tela: o nome e o transporte do cabeçalho, os mesmos dois no
    #    chip, e a cor de linha que folha de estilo nenhuma consegue vencer.
    for campo in ("peca", "via"):
        exigir(corpo.count(f'data-campo="{campo}"') == len(CONECTADOS),
               f"o `{campo}` do cabeçalho do card perdeu o endereço — "
               "a tela volta a mostrar o controle do desenho")
    # O CHIP MORA NO CABEÇALHO, ACIMA DO MIOLO — então ele se confere no `doc`,
    # e não no `corpo`. Conferi-lo no miolo daria VERDE sobre uma fita que
    # ninguém mediu, que é a armadilha desta própria função.
    for campo in ("fita-peca", "fita-via"):
        exigir(doc.count(f'data-campo="{campo}"') == len(CONECTADOS),
               f"o `{campo}` do chip da fita perdeu o endereço")
    exigir("--plastico:#" not in doc.split("</head>", 1)[-1],
           "a cor do plástico voltou para o `style=` — estilo de linha vence "
           "folha de estilo, e o produto não tem como reescrevê-la")
    exigir('<style data-campo="plastico-css" data-hef-alvo="html">' in doc,
           "a folha endereçada do plástico sumiu, ou perdeu o `data-hef-alvo=html` "
           "— sem ele o produto escreve a folha como TEXTO por cima da página, e "
           "a cor do desenho continua mandando")
    # UMA FOLHA SÓ, E ELA TEM O PISO. Duas folhas se sobrepõem apenas no
    # assento que a segunda nomeia — com um controle na mesa, o outro ficava
    # com a cor do desenho (medido no WebKit: `rgb(126, 184, 212)` num assento
    # vazio). E sem o piso, o assento que a troca não nomeia perde a borda
    # inteira, porque `var()` sem valor invalida a declaração.
    exigir(doc.count('data-campo="plastico-css"') == 1
           and "plastico-do-desenho" not in doc,
           "a folha do plástico deixou de ser UMA — duas folhas voltam a deixar "
           "a cor do desenho de pé no assento que a mesa viva não nomeia")
    exigir(PISO_DO_PLASTICO in doc,
           "o piso do plástico sumiu da folha — o assento que a mesa viva não "
           "nomeia perderia a borda em vez de ficar neutro")
    for nome in {str(c["nome"]) for c in CONECTADOS}:
        exigir(corpo.count(nome) == corpo.count(f'<span data-campo="peca">{nome}</span>'),
               f"o nome de plástico `{nome}` aparece no miolo sem endereço")

    if falhas:
        raise SystemExit("ERRO em 02-controles — decisão dela desfeita:\n  "
                         + "\n  ".join(f"- {f}" for f in falhas))


if __name__ == "__main__":
    # ANTES DE ESCREVER, e não depois: um gerador que grava e só então reclama
    # já deixou a tela errada no disco para quem abrir o arquivo.
    a_legenda_nao_promete_o_que_a_tela_nao_tem(LEGENDA, MIOLO)
    n = monta("02-controles", "Controles", MIOLO, CSS, fita_viva=True, legenda=LEGENDA)
    # A SAÍDA É A BANCADA (`mockup/`) — 31/08/2026, quando o fluxo inverteu.
    # Este caminho não dizia "layout": era `parent.parent`, e por isso o censo
    # por texto não o achou. Quem o achou foi a régua da fita logo abaixo, que
    # reprovou com `0 chips para 5 rádios` — ela lia o arquivo VELHO, já com os
    # `<label>` da execução anterior. Régua que acha zero é ERRO, não silêncio.
    SAIDA = onde.pagina("02-controles.html")
    SAIDA.write_text(cor_do_plastico_por_regra(fita_clicavel(SAIDA.read_text())))
    _conferir(SAIDA.read_text())
    print(f"02-controles: OK, {n} divs · {len(CONECTADOS)} conectado(s) "
          f"+ {VAZIOS} lugar(es) vazio(s) — 1 card de {PARA_O_CARD}px, "
          f"{FECHADOS} linha(s) de {ALTURA_FECHADA} e {VAZIOS} de {ALTURA_VAZIA}; "
          f"em 'Todos', {ROLA_EM_TODOS}px de rolagem")
