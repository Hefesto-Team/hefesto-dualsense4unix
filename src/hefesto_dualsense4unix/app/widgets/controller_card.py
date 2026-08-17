"""controller_card.py — card de UM controle na aba Status (STATUS-02/03 + BT-03).

A aba Status deixou de ser single-controller: cada DualSense conectado ganha
um card com identidade própria — título pelo ``player_slot`` de sessão,
bateria própria, swatch da cor CRUA da lightbar — e os inputs ao vivo DAQUELE
controle (barras L2/R2, dois ``StickPreviewGtk`` e o grid 4x4 de
``ButtonGlyph``) com os traços pintados na cor da lightbar dele, ajustada por
``ensure_min_contrast`` (decisão D8: o swatch mostra a cor crua; só os TRAÇOS
recebem a ajustada).

O corpo do card ocupa DUAS linhas, montadas em código — não no Glade::

    [ L2 / R2 ......  |  Giroscópio ......                        ]
    [ Touchpad     |                | Microfone     |             ]
    [ Lightbar     | L3 | R3        | Alto-falante  | botões 4x4  ]

Antes eram seis blocos de largura total, empilhados: o card pedia 457px de
altura e o giroscópio caía abaixo do corte da janela. Emparelhado, o que
somava altura passou a dividir a mesma faixa.

STATUS-SIMETRIA-01 fechou a faixa de baixo em três pontos, todos pedidos pela
mantenedora depois de olhar a tela:

* o **microfone à direita dos analógicos**, em coluna própria e DENTRO do card
  (a madrugada de 26/07 o mandou para o rodapé da aba e foi revertida);
* os **dois analógicos alinhados pelo desenho**, com um ``Gtk.SizeGroup``
  vertical amarrando as duas linhas de título — o degrau de 20px nascia do
  rótulo da esquerda quebrar em 3 linhas e o da direita em 2;
* o **glifo dos botões derivado da escala de fonte** (:func:`glyph_size`), que
  era o único tamanho da interface fora do alcance do ajuste dela.

STATUS-SIMETRIA-02 é o veredito dela sobre aquela entrega: *"só distanciou as
coisas"*. Espalhar os módulos pela largura resolveu o amontoamento e não
produziu leitura. As seis mudanças desta rodada, todas medidas na tela dela:

* **o microfone não sai mais da faixa** (MIC-PRESENTE-01). Os dois ``hide()``
  viraram estado apagado com o motivo em palavras, e a largura do bloco é
  reservada por construção — campo fixo do rótulo mais ``Gtk.SizeGroup``
  horizontal. Sumir era indistinguível de "não existe", e fazia os analógicos
  pularem 42px a cada vez que o sinal ia e voltava (por Bluetooth, o tempo
  todo);
* **as duas legendas de analógico têm o mesmo número de linhas**, agora por
  construção: a quebra está ESCRITA no rótulo e o ``(L3)``/``(R3)`` desceu
  para a linha dos números. O ``SizeGroup`` vertical da rodada anterior
  igualava a altura do bloco, não o número de linhas do texto;
* **cada sensor tem bloco com moldura** no card de um controle — a coluna da
  esquerda era uma lista de seis itens sem separação entre dois assuntos. No
  card compacto a moldura não cabe na largura, e o motivo está em `_bloco`;
* **o alto-falante existe na tela** mesmo sem ninguém ter ajustado o volume;
* **as barras e o giroscópio ganharam teto de largura**, e o card de um
  controle também (:data:`LARGURA_CARD_UNICO`): o vazio deixou de ser buraco
  entre os módulos e virou margem em volta de uma coluna de conteúdo;
* **a bateria aparece uma vez só**: com um controle, quem fala é o frame
  "Estado"; com 2+, quem fala é cada card.

SOM-01 é a terceira rodada, e vem dos três pedidos que ela fez olhando a v2
("quase perfeito"): *"dava pra colocar o auto falante abaixo do microfone"*,
*"aumentar e espaçar mais os botões do controle tipo x quadrado bola e
triângulo e afins"* e *"permitir a expansão da janela"*. As três mudanças:

* **o alto-falante mudou de coluna**: saiu de baixo da lightbar (coluna da
  esquerda) e passou a ficar imediatamente ABAIXO do microfone, numa coluna de
  som própria (:meth:`_montar_coluna_audio`). Os dois são o mesmo assunto — o
  áudio do controle — e estavam em pontas opostas da faixa;
* **os glifos dos botões cresceram e ganharam respiro** no card de UM controle
  (:func:`glyph_size_unico`, :data:`GLYPH_ESPACO_UNICO`). No card compacto eles
  ficam com o tamanho de hoje, e o motivo está em :func:`glyph_size_unico`:
  com 2+ cards lado a lado cada px soma direto no mínimo da janela;
* **o teto de largura virou ELÁSTICO**: o card cresce com a janela do piso
  (:data:`LARGURA_CARD_UNICO`) até :data:`LARGURA_CARD_ELASTICA`, em vez de
  ficar travado num número só. O que impede o vazio de voltar não é o teto e
  sim o CONTEÚDO crescer junto — desenhos maiores e a sobra repartida entre os
  três blocos da faixa, medida em ``test_status_faixa_blocos``.

SOM-02 é a rodada em que o alto-falante deixou de ser só leitura. O bloco
ganhou um controle deslizante de volume (E1), um botão de mudo cuja primeira
linha é INSENSÍVEL (E2) e o botão de devolução da posse (E3, do lado do IPC), e
a barra continuou sendo LEITURA — quem repinta é o tique de 10 Hz relendo
``daemon.state_full``, nunca o valor mandado. A insensibilidade da primeira
linha é entrega, não detalhe: sem volume conhecido, um ``muted`` tranca o
alto-falante em zero e o próprio botão não tem como soltá-lo (armadilha 2 da
sprint, medida no backend real).

Contratos honrados (sprint status-por-controle, itens 6-9 do desenho):

* Rótulo da lightbar pela FONTE (``lightbar_source`` do ``state_full``):
  fonte conhecida e apagada → "Lightbar: apagada"; ``"desconhecida"`` →
  "Lightbar: cor desconhecida" (NUNCA "apagada" — o 0,0,0 da classe LED sem
  escrita nossa pode ser o azul-kernel brilhando agora, refutação 1 do
  sprint); ``native_mode`` global → "em Nativo o jogo é dono do LED" com a
  última cor conhecida. Sem cor conhecida, os traços usam o accent neutro
  (``ACCENT_NEUTRO``) ajustado.
* BT-03: ``vpad_backend == "uinput"`` com ``vpad_motivo`` preenchido acende
  uma linha visível de degradação com o motivo em palavras leigas
  (``MOTIVOS_DEGRADACAO_LEIGOS``). O texto NUNCA crava o mecanismo do sono
  BT como causa — diz o que aconteceu com o "modo completo", não por quê.
* ``inputs is None`` → a área de inputs mostra "—" (sem leitor); o card
  NUNCA congela o último valor como se fosse vivo.
* ``update()`` tem DIFF interno por seção (título/bateria/cor/degradação/
  inputs): repetir o mesmo estado a 10 Hz não re-renderiza nada.

Sem timers RECORRENTES próprios (quem agenda o tique é a mixin de status, com
os timers que ela JÁ tinha; o aceite do STATUS-02 é diff contra esse baseline)
e sem popups (cosmic-epoch#2497): tudo inline, sempre visível. A ÚNICA exceção
é o repouso do controle deslizante de volume (SOM-02/E1): um
``GLib.timeout_add`` de UM disparo, armado por gesto humano e desarmado ao
disparar ou ao soltar o botão do mouse — sem ele, arrastar o controle vira uma
rajada de IPC bloqueante (um pedido por pixel). Como os demais widgets da casa,
há a variante GTK real e um stub puro para ambiente sem GTK (testes/CI sem
display).
"""
from __future__ import annotations

import contextlib
from typing import Any, Final, NamedTuple

from hefesto_dualsense4unix.app import audio_saida, ipc_bridge
from hefesto_dualsense4unix.app.draft_config import registrar_alto_falante_no_rascunho
from hefesto_dualsense4unix.app.widgets.sensor_widgets import (
    GyroBars,
    LightbarBar,
    MicMeter,
    SpeakerBar,
    TouchpadView,
    fracao_do_volume,
    percentual_do_volume,
    posicao_normalizada,
    selo_mic,
    texto_toques,
    texto_volume,
    volume_do_percentual,
)
from hefesto_dualsense4unix.gui.widgets import (
    BUTTON_GLYPH_LABELS,
    ButtonGlyph,
    StickPreviewGtk,
)
from hefesto_dualsense4unix.utils.color_contrast import (
    ACCENT_NEUTRO,
    ensure_min_contrast,
    rgb_para_hex,
    tintar_progressbar,
)

RGB = tuple[int, int, int]

# ---------------------------------------------------------------------------
# Layout do grid de glyphs (4x4) — era da mixin de status; o card absorveu
# (UI-STATUS-STICKS-REDESIGN-01 → STATUS-02). Ordem de leitura: linha 0..3.
# ---------------------------------------------------------------------------

GRID_BOTOES: Final[list[list[str]]] = [
    ["cross",   "circle",    "square",    "triangle"],
    ["dpad_up", "dpad_down", "dpad_left", "dpad_right"],
    ["l1",      "r1",        "l2",        "r2"],
    ["share",   "options",   "ps",        "touchpad"],
]

#: Todos os 16 botões do grid numa lista plana (para iteração).
ALL_BUTTONS: Final[list[str]] = [b for linha in GRID_BOTOES for b in linha]

#: Threshold para considerar L2/R2 analógicos "pressionados" no glyph.
L2_R2_THRESHOLD: Final[int] = 30

#: Piso do glifo, em px, com a escala de fonte ZERADA (STATUS-SIMETRIA-01).
#:
#: O número que estava aqui (20px cru) era o ÚNICO tamanho da interface fora do
#: alcance da escala de fonte: o A/B com escala 0 e escala 3 devolvia 20x20 nos
#: dois casos, então o recurso que a mantenedora tem para enxergar melhor não
#: tinha efeito nenhum sobre triângulo, X, bola e quadrado — justamente os
#: menores desenhos do card. Agora o glifo deriva da escala pelo mesmo molde do
#: `app/theme.py`: lá o delta é somado a cada `font-size` do CSS; aqui ele entra
#: multiplicado, porque um glifo cresce nas DUAS dimensões e um degrau de 1px de
#: fonte quase não se vê num quadrado de 20.
GLYPH_SIZE_BASE: Final[int] = 24

#: Quantos px o glifo ganha por degrau de escala de fonte. Com a escala 3 desta
#: casa o glifo sai em 36px (era 20), e o grid 4x4 passa de 86 para 150px de
#: largura — cabendo no orçamento medido da aba Status com dois cards.
GLYPH_PX_POR_DEGRAU_DE_FONTE: Final[int] = 4


def _escala_da_interface() -> int:
    """Delta de fonte (px) que a interface está usando, ou 0 sem tema.

    Import TARDIO de propósito: `app/theme.py` importa `gi` no topo, e este
    módulo tem de continuar carregando no ambiente sem GTK (o stub do fim do
    arquivo). Qualquer falha vira escala 0 — o glifo encolhe até o piso, mas a
    janela nunca deixa de abrir por causa do tamanho de um desenho.
    """
    try:
        from hefesto_dualsense4unix.app.theme import escala_fonte

        return max(0, int(escala_fonte()))
    except (ImportError, ValueError, TypeError, OSError):
        return 0


#: Quanto o glifo do card de UM controle é maior que o do compacto, em oitavos.
#:
#: SOM-01, pedido 2 — *"aumentar e espaçar mais os botões do controle tipo x
#: quadrado bola e triângulo e afins"*. Medido na tela dela: o grid 4x4 inteiro
#: ocupava 150x150px no canto direito de um card de 960 — os quatro símbolos que
#: ela nomeou cabiam num quadrado de 36px cada, com 2px entre eles. Cinco
#: terços (13/8) levava o glifo de 36 para 58px, mas o grid 4x4 manda também na
#: ALTURA do card, e o orçamento da faixa é apertado: com 58px o card pedia
#: 357px contra 369px disponíveis — 12px de folga, que a máquina do CI (sem as
#: fontes do projeto, com métricas de fallback diferentes) estourou na estreia
#: da v0.3.0, pedindo 431px. 12/8 leva o glifo a 54px e o grid a 246px, que é
#: um aumento de 50% sobre os 36px de antes e devolve 16px de altura de folga.
#: O teto de verdade é a altura, não a largura — a largura o teto elástico paga.
GLYPH_FATOR_UNICO_OITAVOS: Final[int] = 12

#: Respiro entre os glifos, em px: 2 no card compacto (o de hoje), 10 no de um
#: controle. Colados, o grid lia como um bloco só; é a segunda metade do pedido
#: ("e espaçar mais"), e ela custa 3x8=24px de largura, que só o card único tem.
GLYPH_ESPACO_COMPACTO: Final[int] = 2
GLYPH_ESPACO_UNICO: Final[int] = 10


def glyph_size(escala: int | None = None) -> int:
    """Tamanho do glifo em px, DERIVADO da escala de fonte da interface.

    Chamada na MONTAGEM do grid (`_montar_glyphs`), nunca no import: é isso que
    faz um card novo já nascer com o tamanho da escala vigente, e é isso que o
    A/B de escala 0 contra escala 3 mede.

    Este é o tamanho do card COMPACTO (2+ controles). O de um controle só sai
    de :func:`glyph_size_unico`.
    """
    if escala is None:
        escala = _escala_da_interface()
    return GLYPH_SIZE_BASE + GLYPH_PX_POR_DEGRAU_DE_FONTE * max(0, int(escala))


def glyph_size_unico(escala: int | None = None) -> int:
    """Tamanho do glifo no card de UM controle — maior, e por quanto.

    **Por que só aqui.** O glifo cresce onde há largura para pagá-lo. Com 2+
    controles os cards vão lado a lado e a largura de cada um soma DIRETO no
    mínimo da janela, sem rolagem horizontal para absorver (a folga da aba
    inteira com dois cards é de 128px, medida em
    `test_dois_cards_lado_a_lado_cabem_na_largura_da_janela`); no card de um
    controle, o teto elástico devolve centenas de px, e é deles que sai o
    tamanho novo. É a mesma decisão já escrita para a moldura dos blocos em
    `_bloco`, aplicada ao grid de botões.
    """
    return glyph_size(escala) * GLYPH_FATOR_UNICO_OITAVOS // 8


#: Sticks: 88px com card único; 70px quando há 2+ cards. Os dois encolheram
#: junto com o reagrupamento em três linhas. Estes números NÃO são chute: o
#: teto vem medido em `test_card_de_controle_cabe_na_faixa_que_a_aba_status_da`
#: (a faixa que o `status_players_scroll` recebe com a janela no tamanho com
#: que ela abre), e é esse teste que manda aqui.
#: O caminho de UM controle é o card mais ALTO (usa o stick maior) e era o
#: único sem teste: com 104px ele pedia 411px para uma faixa de 397px e voltava
#: a esconder os botões abaixo da dobra — o caso mais comum de quem tem um
#: controle só. `test_card_de_um_controle_so_tambem_cabe_na_faixa` agora tranca
#: os DOIS caminhos.
#: STATUS-SIMETRIA-02: com UM controle o desenho subiu de 88 para 110px. A
#: altura que ele consome vinha sobrando — a faixa que a aba dá ao card tinha
#: 170px livres — e a metade de baixo da aba era vazio puro. Crescer o desenho
#: usa esse vazio; espalhar os blocos por ele foi o que ela reprovou.
#: SOM-01: 110 -> 140 no card de um controle. O teto elástico devolve largura, e
#: a regra desta leva é que quem cresce é o CONTEÚDO — sobra virando desenho
#: maior, não vão entre os blocos. A altura continua cabendo: a faixa da aba
#: tinha 140px livres antes desta rodada (medido em `orcamento`).
STICK_SIZE_SINGLE: Final[int] = 140
STICK_SIZE_COMPACT: Final[int] = 70

#: Os dois títulos de analógico, com a quebra ESCRITA no texto.
#:
#: STATUS-SIMETRIA-02, defeito 1 — *"um nome dos analógicos tem 3 linhas outro
#: dois"*. A quebra automática dependia da largura disponível e do tamanho da
#: fonte: `Analógico Esquerdo (L3)` (três palavras) caía em 3 linhas no card
#: compacto e `Analógico Direito (R3)` em 2, e o `Gtk.SizeGroup` vertical da
#: entrega anterior igualava a ALTURA do bloco sem igualar o número de linhas
#: do texto — o desenho ficava alinhado e a legenda não.
#:
#: Com a quebra explícita e `line_wrap` desligado, os dois rótulos têm DUAS
#: linhas por construção: não dependem mais da largura, da fonte nem da escala.
#: O ``(L3)``/``(R3)`` saiu do título e desceu para a linha dos números, onde
#: já havia texto: era ele a terceira palavra, e é a terceira palavra que
#: fazia um rótulo quebrar em 3 linhas e o outro em 2. Sem ele, os dois viram
#: "Analógico" + a lateral — e a linha mais larga passa a ser a mesma nos
#: dois, o que também devolve a largura que a moldura dos blocos custa.
_TITULO_STICK_ESQ: Final[str] = "Analógico\nesquerdo"
_TITULO_STICK_DIR: Final[str] = "Analógico\ndireito"

#: A lateral de cada analógico. CARD-ÚNICO-01: ela é a MARCA D'ÁGUA desenhada
#: no centro do círculo (`StickPreviewGtk`), e não mais um prefixo da linha de
#: valores — quem a recebe é o construtor do desenho.
ROTULO_STICK_ESQ: Final[str] = "L3"
ROTULO_STICK_DIR: Final[str] = "R3"

#: Largura do card quando há UM controle só, em px.
#:
#: STATUS-SIMETRIA-02, defeito 4 — na tela maximizada o card recebia 1870px
#: para ~700px de conteúdo, e a sobra virava DOIS buracos de 673px dentro da
#: faixa (um antes dos analógicos, outro depois do microfone). Com um teto, a
#: sobra sai de dentro do card e vira margem da página, com o card centrado:
#: é a diferença entre "espaço vazio entre as coisas" e "margem em volta do
#: bloco", que é o que a sprint pede.
#:
#: O número tem de caber na janela no MENOR tamanho em que ela abre (1062px de
#: mínimo medido em `test_a_janela_inteira_cabe_na_largura_de_projeto`), porque
#: a aba Status não tem rolagem horizontal para onde fugir.
#:
#: SOM-01: este número deixou de ser o teto e virou o PISO. Ele é repetido no
#: `frame_status_estado` do glade (e a igualdade é travada por
#: `test_status_faixa_blocos`), então continua sendo a largura da coluna de
#: conteúdo da aba na janela do tamanho de projeto. Subiu de 960 para 1040 por
#: uma razão medida: com os desenhos maiores desta leva o conteúdo do card pede
#: ~1030px, e um piso ABAIXO do que o conteúdo pede não é piso nenhum — seria
#: um número decorativo que o card ignora.
LARGURA_CARD_UNICO: Final[int] = 1040

#: Largura da barra de bateria DENTRO do card único, em px.
#:
#: CARD-ÚNICO-01. Ela é PEDIDA e não expandida, e a razão é a mesma que tirou
#: o `show-text` da barra: uma barra que estica pela faixa toda transforma o
#: número num ponto perdido no meio do vazio. Aqui a barra tem um tamanho de
#: leitura e quem expande é o vão à esquerda dela, onde mora a linha do
#: giroscópio. 300px é o número que o frame Estado já usava no glade.
LARGURA_BARRA_BATERIA_CARD: Final[int] = 300

#: O que o card mostra antes de a janela dizer qual perfil está ativo.
#:
#: Ele é o MESMO texto que o `status_actions` escreve quando o daemon responde
#: sem perfil (`state.get("active_profile") or "Nenhum"`) — o card nasce
#: dizendo o que a aba diria, e não um "—" que some meio segundo depois.
TEXTO_PERFIL_SEM_DADO: Final[str] = "Nenhum"

#: Idem para o daemon. "Consultando..." é o que o Glade já dizia no
#: `status_daemon`, e a palavra importa: o card nasce antes da primeira
#: resposta do IPC, e "Desligado" ali seria afirmar o que ninguém apurou.
TEXTO_DAEMON_SEM_DADO: Final[str] = "Consultando..."

#: Teto ELÁSTICO do card de um controle, em px.
#:
#: SOM-01, pedido 3 — *"permitir a expansão da janela"*. Na tela dela
#: (maximizada em 1920) o card ficava travado nos 960px do piso e sobravam
#: ~950px de vazio nas laterais: a janela crescia e o conteúdo não.
#:
#: O teto NÃO some, e o motivo é o defeito que a rodada anterior curou: sem
#: teto nenhum o card estica pelos 1870px com ~1000px de conteúdo e a sobra vira
#: buraco DENTRO da faixa (eram dois vãos de 673px). Elástico é o meio-termo
#: medido: o card cresce com a janela até aqui, o conteúdo cresce junto (glifos,
#: analógicos, medidores) e o que ainda sobra se reparte entre os três blocos da
#: faixa em vez de virar um vão só — `test_status_faixa_blocos` cobra os 200px
#: de vão máximo com a janela em 1920.
#:
#: O corte fica no `do_size_allocate`, e não num `set_size_request`: pedido de
#: tamanho no GTK3 é MÍNIMO, não máximo — não existe "largura máxima" declarada.
LARGURA_CARD_ELASTICA: Final[int] = 1400

#: Teto da barra de gatilho e do giroscópio no card de UM controle, em px.
#:
#: Medido na tela dela em 27/07: a barra do L2 recebia 881px para dizer um
#: número de 0 a 255, com o "0 / 255" flutuando no meio do vazio, e o
#: giroscópio recebia 914px — o "+1.6" do eixo X saía a ~880px do "X". Nada
#: disso é informação: é o widget aceitando toda a largura que o card tem.
#:
#: O card compacto tem tetos MENORES, e não é preferência: um teto é um pedido
#: MÍNIMO de largura, e com 2+ cards lado a lado cada px sobe direto para o
#: mínimo da janela. Estes números vieram da folga medida na linha de cima do
#: card compacto (a faixa de baixo é que manda na largura dele, e sobram ~140px
#: na de cima) — cabem sem mexer no mínimo do card.
#:
#: SOM-01: os dois do card único subiram junto com o teto elástico (300 -> 400 e
#: 320 -> 420). A linha de cima tem duas colunas homogêneas, então cada uma
#: recebe metade da largura do card: com o card em 1400 elas passam a ter ~680px
#: e os tetos antigos deixariam 380px de nada à direita de cada bloco. Os
#: números novos continuam abaixo da metade do PISO ((1040-40)/2 = 500), que é o
#: que impede a linha de cima de virar quem manda no mínimo do card.
LARGURA_BARRA_GATILHO_UNICO: Final[int] = 400
LARGURA_GYRO_UNICO: Final[int] = 420
LARGURA_BARRA_GATILHO_COMPACTO: Final[int] = 200
LARGURA_GYRO_COMPACTO: Final[int] = 220

#: Tamanhos dos desenhos no card de UM controle (o compacto usa os do
#: `sensor_widgets`). Mesma troca do analógico: a altura sobrava e a metade de
#: baixo da aba era vazia.
#: SOM-01: cresceram de novo, e pelo mesmo motivo do teto elástico — a largura
#: que a janela larga devolve tem de virar desenho, não vão.
#:
#: SOM-03, segunda rodada: a ALTURA parou de sobrar. O comando do alto-falante
#: (controle deslizante numa linha própria mais os dois botões) custa ~74px de
#: bloco, e a coluna do som passou a ser a MAIS ALTA da faixa — quando ela
#: passa da grade de glifos, cada pixel dela vira pixel de card. A altura
#: destes dois desenhos foi o que pagou, e o critério está medido em
#: `test_a_coluna_do_som_nao_e_a_mais_alta_da_faixa`: o medidor do microfone
#: caiu de 56 para 28px e a barra fina do alto-falante de 18 para 12 (a mesma
#: espessura que o card compacto sempre usou). A LARGURA dos dois não mudou —
#: é ela que a CARD-OCUPA-01 mediu, e é ela que continua sendo cobrada.
_TOUCHPAD_PX_UNICO: Final[tuple[int, int]] = (180, 80)
_MIC_METER_PX_UNICO: Final[tuple[int, int]] = (180, 28)
_BARRA_FINA_PX_UNICO: Final[tuple[int, int]] = (160, 18)
#: A barra fina do ALTO-FALANTE no card de um controle. Separada da lightbar
#: (`_BARRA_FINA_PX_UNICO`) porque só ela vive na coluna que estoura: 12px é a
#: espessura que `_SPEAKER_PX` já declara e que o card compacto sempre
#: desenhou, então não é um tamanho novo — é o mesmo, aplicado onde custa.
_BARRA_SPEAKER_PX_UNICO: Final[tuple[int, int]] = (160, 12)

#: Largura NATURAL do touchpad e do medidor do microfone no card de UM
#: controle, em px. Os números acima continuam sendo o MÍNIMO — este é o teto
#: até onde cada um cresce quando a janela larga devolve largura.
#:
#: CARD-OCUPA-01 — *"tem muito espaço vazio aqui, dava pra aumentar a largura
#: do touchpad e lightbar e do microfone e alto falante pra ocuparem os espaços
#: laterais vazios"*. Medido na bancada offscreen antes da cura, com a janela
#: em 1870 e o card no teto elástico de 1400: touchpad e medidor parados em
#: 180px, com 148px de vão de cada lado do miolo — os "espaços laterais" da
#: foto de 01h34.
#:
#: **Por que não subir o `set_size_request`.** Pedido de tamanho no GTK3 é
#: MÍNIMO: um número maior ali sobe direto para o mínimo do card (hoje
#: 1040px, com ~1030px de conteúdo dentro) e daí para o mínimo da janela
#: (1062px medidos, sem rolagem horizontal para onde fugir). O crescimento
#: mora no NATURAL (`DesenhoElastico`), que só é pago quando há espaço.
#:
#: **De onde sai o 360.** A faixa pede, com os dois desenhos em L px,
#: ``L + L + 618`` de natural (296 dos analógicos, 246 do grid de botões, 28
#: das duas molduras e 48 dos três respiros de 16px) contra 1374px úteis do
#: card no teto elástico. L = 360 fecha a conta com 36px de sobra, que vira o
#: respiro entre os blocos (28px medidos de cada lado do miolo, contra 148px
#: antes da cura); L = 378 zeraria o vão e colaria bloco em bloco. O
#: dobro exato do piso também é o que mantém a leitura do retângulo do
#: touchpad — 360x80 ainda é um retângulo deitado, e a altura NÃO muda nesta
#: leva (o orçamento apertado do card é vertical).
#:
#: O mesmo número serve às duas colunas de propósito: a do touchpad e a do som
#: são espelhos na faixa, e um número por coluna deixaria a simetria à mercê
#: da próxima edição. As barras finas (lightbar e alto-falante) não têm teto
#: próprio — elas preenchem a coluna em que vivem e acompanham o desenho de
#: cima por construção.
_DESENHO_NATURAL_PX_UNICO: Final[int] = 360

#: Estado do microfone dito em palavras, ao lado do medidor.
#:
#: MIC-PRESENTE-01/E2 — *"na aba status falta a presença permanente do
#: microfone (mesmo que não esteja funcionando no bt, mas o espaço do icon
#: sempre fica lá)"*. Um medidor mudo sem explicação comunica a coisa errada:
#: parece microfone aberto em silêncio. São estados diferentes e a faixa
#: precisa distingui-los em palavras.
#: As duas frases são CURTAS de propósito: é o rótulo mais longo do bloco que
#: decide a largura reservada, e a largura é a restrição dura desta aba (dois
#: cards lado a lado somam direto no mínimo da janela, sem rolagem horizontal
#: para absorver). Quem diz "microfone" é a moldura do bloco; estas dizem só o
#: estado, e é assim que a linha inteira se lê: "Microfone / sem sinal".
TEXTO_MIC_AUSENTE: Final[str] = "Sem sinal"
TEXTO_MIC_SEM_MUTE: Final[str] = "Captando"

#: Campo fixo do rótulo de estado do microfone, em caracteres: é o que impede
#: a faixa de mudar de largura quando o texto troca de "sem sinal" para
#: "ativo" (a mesma disciplina de campo fixo do `texto_eixo`).
_MIC_ESTADO_CHARS: Final[int] = len(TEXTO_MIC_AUSENTE)

#: Rótulos do BOTÃO do microfone (MIC-USB-01, entrega 2). Cada um diz o que o
#: CLIQUE faz — não o estado, que quem diz é o rótulo acima. Curtos porque o
#: botão herda a largura reservada do bloco (140px), e um rótulo mais largo que
#: isso empurraria a coluna inteira.
TEXTO_BOTAO_MIC_ATIVAR: Final[str] = "Ativar"
TEXTO_BOTAO_MIC_SILENCIAR: Final[str] = "Silenciar"
#: SOLTAR-01 (01/08, decisão dela). Era "Devolver", e ela perguntou se não
#: seria melhor "Resetar". A resposta foi NÃO, e o motivo vale ficar escrito:
#: "Resetar" prometeria que o valor volta ao anterior — e ele NÃO volta. O
#: DualSense não devolve o volume nem o estado do mute (não há report de
#: leitura), então o que estiver valendo continua até desconectar. O botão
#: devolve o CONTROLE, nunca o valor.
#:
#: O rótulo diz isso e é mais curto que "Devolver ao controle", que custaria
#: ~90px e faria os três rótulos da linha cortarem em 1180px (medido).
TEXTO_BOTAO_MIC_DEVOLVER: Final[str] = "Liberar"
#: SOM-ROTULO-01 (01/08), a mesma cura do botão do alto-falante e pela mesma
#: razão dela: *"não sei se faz sentido ter o 'sem dado'"*. Não fazia — não é
#: rótulo de AÇÃO, é a janela escrevendo "não sei" dentro de um botão, no lugar
#: onde deveria dizer o que o clique faz. O botão passa a se chamar sempre pela
#: ação e nasce INSENSÍVEL enquanto não há leitura; quem explica o porquê é a
#: dica (:data:`DICA_MIC_SEM_LEITURA`). Um botão cinza não promete nada.
TEXTO_BOTAO_MIC_SEM_LEITURA: Final[str] = "Silenciar"

#: As dicas (tooltip) do botão. Elas carregam o que o rótulo curto não cabe —
#: em especial o preço de mandar no mudo pela janela: enquanto o hefesto for o
#: dono do registrador, o botão FÍSICO do controle para de valer. Esconder esse
#: preço seria repetir o erro de "a config que eu deixo nunca é respeitada".
DICA_MIC_ATIVAR: Final[str] = (
    "O microfone está mudo no firmware do controle (camada 3). Desmutar daqui "
    "faz o hefesto assumir o registrador — e o botão de microfone do controle "
    "para de valer até você clicar em Liberar."
)
DICA_MIC_SILENCIAR: Final[str] = (
    "O microfone está aberto e quem manda no mudo é o botão físico do "
    "controle. Silenciar daqui faz o hefesto assumir o registrador."
)
DICA_MIC_DEVOLVER: Final[str] = (
    "Quem manda no mudo agora é o hefesto, e por isso o botão de microfone do "
    "controle não responde. Liberar faz o botão físico voltar a valer."
)
DICA_MIC_SEM_LEITURA: Final[str] = (
    "O daemon ainda não leu o estado do microfone deste controle. Sem saber "
    "se ele está mudo, mandar mutar ou desmutar seria chute."
)

# --- MIC-BT-01: onde ficava o interruptor "Pelo rádio", e por que ele saiu ---
#
# ELE EXISTIU aqui de 07/08 a 16/08/2026 (`TEXTO_MIC_BT_ROTULO = "Pelo rádio"`,
# um `Gtk.Switch` na linha do botão de mudo, com `acao_ponte_bt`,
# `ligar_ponte_bt` e `desligar_ponte_bt` neste mesmo módulo). SAIU por dois
# motivos, e o segundo é o que manda:
#
# 1. **É o desenho dela**, 16/08: *"dá espaço a um slicer de microfone pra
#    definir o volume do microfone real (independente de saber se tá via bt ou
#    via cabo), o app deve ser inteligente pra saber qual caminho usar. Ali
#    onde temos o botão por rádio trocamos por Silenciar"*. O interruptor punha
#    na tela uma decisão TÉCNICA que é do aplicativo: no rádio o áudio vem em
#    Opus dentro dos reports HID, no cabo vem por placa de som USB — e é o
#    MESMO microfone. Ela não deveria precisar saber disso para falar.
#
# 2. **A ponte NÃO é segura**, medido DUAS vezes em 16/08/2026. Com ela de pé,
#    o botão PS aparece pressionado em pulsos de ~17 ms (`held_ms=17.6 / 17.5
#    / 17.9` — um ciclo de leitura a 60 Hz; mão nenhuma faz isso) e o daemon
#    tenta abrir a Steam em laço. A segunda rodada já tinha o filtro do bit de
#    áudio no lugar e travou igual. Ela descreveu como *"o teclado e o mouse
#    com vida própria"* e desligou o controle, com medo.
#    Estudo inteiro, com o log:
#    `docs/process/estudos/2026-08-16-O-PS-PRESO-a-ponte-do-mic-e-o-laco-que-
#    abria-a-steam-sozinho.md`.
#
#    **Um interruptor que oferece um gesto perigoso é pior que interruptor
#    nenhum.** Oferecer é convidar, e o convite estava numa janela que ela usa
#    para conferir o controle.
#
# O QUE NÃO SAIU: a CAPACIDADE. A ponte continua inteira e funcionando —
# `integrations/dualsense_bt_audio.py` (publicou o source no PipeWire em
# 16/08), o subsystem `daemon/subsystems/bt_mic.py`, o `mic bt` da linha de
# comando, e o gate `HEFESTO_DUALSENSE4UNIX_BT_MIC` para quem quiser subi-la à
# mão. O que saiu é o BOTÃO.
#
# COMO ELE VOLTA — a condição, escrita para não se perder:
#
#   (a) **Arbitrar a posse do hidraw.** A ponte lê o mesmo nó que o
#       `motion_reader`, e o broker entrega o fd para quem pedir. O broker é o
#       dono da posse: é ele que tem de recusar o segundo pedido, ou
#       multiplexar.
#   (b) **Um dono só para o contador de sequência do report `0x32`.** O log de
#       16/08 mostra a ponte mandando `seq=1`, começando do zero, enquanto o
#       daemon mantém a própria sequência por handle. Dois escritores, um
#       contador. (Ainda é hipótese: não se mediu a sequência dos dois lados no
#       mesmo instante. Mas é a única de pé, e tem endereço.)
#   (c) **Debounce no PS**, para que botão preso nenhum vire enxurrada de
#       janelas — a ponte foi o gatilho, o laço sem freio foi o estrago.
#
# Fechadas (a) e (b), o interruptor volta a ter lugar; o desenho dela de 16/08
# continua valendo, então o que voltar não é este widget de novo, e sim uma
# escolha que não obrigue ela a saber por onde o som anda.
# O portão que o segura fora: `tests/unit/test_o_interruptor_do_mic_no_card.py`
# e `tests/unit/test_o_interruptor_do_mic_por_bluetooth.py`.

# --- MIC-VOLUME-01 (16/08/2026): o controle deslizante do microfone ---------
#
# Pedido dela, olhando o bloco: *"esse botão de silenciar some. dá espaço a um
# slicer de microfone pra definir o volume do microfone real (independente de
# saber se tá via bt ou via cabo), o app deve ser inteligente pra saber qual
# caminho usar"*.
#
# A SIMETRIA é o motivo, e ela apareceu na tela antes de aparecer no código: o
# bloco do alto-falante tinha nível, volume e silenciar; o do microfone tinha
# nível e silenciar. Faltava o do meio, e a falta não era só visual — o perfil
# guardava `volume`/`muted`/`rota` do alto-falante e só um booleano do
# microfone. Ver `profiles/schema.ProfileMicConfig`.
#
# O QUE ELE MEXE, e por que isso o torna universal: o volume da FONTE DE
# CAPTURA no sistema (o source do PipeWire), nunca um registrador do controle.
# O DualSense não expõe ganho de microfone — o que existe no firmware é o mudo,
# e quem fala com ele é o botão ao lado. Como o volume é do caminho e não do
# aparelho, ele funciona igual no cabo e no rádio sem que ela precise saber
# qual está valendo. Era exatamente o "independente de saber se tá via bt ou
# via cabo" do pedido.
#
# A escala é 0-100 (por cento), diferente da do alto-falante (0-255, porque
# aquela escreve um byte do report). Pedir que ela pense em bytes seria vazar
# o protocolo para a tela.
TEXTO_MIC_VOLUME_TITULO: Final[str] = "Microfone"

#: A dica do controle deslizante. Ela carrega o preço e o alcance — que é o que
#: o rótulo curto não cabe, e o que separa este controle do botão ao lado.
DICA_MIC_ESCALA: Final[str] = (
    "Volume da captura do microfone, no sistema. Vale igual no cabo e no "
    "rádio: o Hefesto escolhe o caminho sozinho. Este controle NÃO mexe no "
    "mudo do firmware — quem faz isso é o botão ao lado, e só ele apaga a luz "
    "vermelha do microfone. Salvar ou aplicar o perfil grava este valor."
)

#: Repouso do controle deslizante do microfone, em ms. Mesmo número do
#: alto-falante e pela mesma razão: `value-changed` dispara por pixel de
#: arrasto e o IPC é bloqueante, então quem manda é o fim do gesto ou o
#: repouso — o que vier primeiro.
_MIC_REPOUSO_MS: Final[int] = 180

#: Alto-falante sem volume conhecido. O DualSense NÃO devolve o volume — não
#: há report de input nem feature report que o leia, e o daemon só publica a
#: chave `speaker` depois de um `speaker.set` nosso (ipc_handlers). Então o
#: bloco existe sempre, e diz que ninguém ajustou nada: um "0 %" ali seria
#: volume inventado, e esconder o bloco seria dizer que o controle não tem
#: alto-falante.
TEXTO_SPEAKER_SEM_DADO: Final[str] = "Não ajustado"

#: O nome do bloco, sozinho. CARD-ÚNICO-01: ele é o título INTEIRO quando não
#: há volume conhecido — a moldura deixou de anunciar "não ajustado" ao lado
#: do nome. Constante e não literal porque agora dois lugares o escrevem (a
#: montagem da moldura e `_escrever_valor_do_speaker`), e um teste de faixa
#: casa o prefixo do rótulo da moldura com este nome.
TITULO_SPEAKER: Final[str] = "Alto-falante"

# ---------------------------------------------------------------------------
# SOM-CANAL-01 — os DOIS caminhos de áudio, que a tela tratava como um
# ---------------------------------------------------------------------------
#
# Ela, olhando o bloco: *"o bloco Alto-falante do card está confundindo duas
# coisas diferentes"*. São dois caminhos INDEPENDENTES, e os dois podem estar
# ligados ao mesmo tempo — por isso um seletor de dois estados, e não um botão.

#: A pergunta que o seletor responde. Ela nomeia o eixo (ONDE o som sai) e é o
#: que separa este seletor do `Silenciar`, que responde outra coisa (SE há som).
TEXTO_CANAL_PERGUNTA: Final[str] = "O que sai no controle:"

#: O id do canal, e o rótulo que ela escolheu. A ORDEM é a da tela.
#:
#: `jogo` é o PADRÃO, e é o estado novo: só o que o jogo mandar para o
#: dispositivo de áudio do controle sai nele, e o resto continua na TV. Ele
#: depende do byte `OUTPUT_PATH_SEL`, medido em 02/08 pela orelha dela.
#:
#: `tudo` é o que o botão "Ouvir no controle" fazia: troca o default sink do
#: PipeWire e todo o som do PC passa a sair no controle.
CANAL_SONS_DO_JOGO: Final[str] = "jogo"
CANAL_TODO_O_PC: Final[str] = "tudo"
#: Os rótulos são os que ELA escreveu, e a medição os liberou.
#:
#: Ela avisou na sprint que aquela linha é a mais apertada do card e mandou
#: medir antes. Medido: o seletor com estes dois rótulos pede **155px** de
#: largura, e com o `Silenciar` ao lado dá **241px** — contra um teto de 258.
#: Cabem com folga.
#:
#: O que quase os matou foi um diagnóstico errado meu: o teste que reprovou
#: mede `get_preferred_HEIGHT`, e eu li como largura. Encurtei rótulos que não
#: precisavam encurtar, e cheguei a levar a decisão a ela com um número que
#: não era o do problema. O custo real era a ALTURA do seletor — 67px contra
#: os 34 do botão que ele substitui.
CANAIS_DO_SPEAKER: Final[tuple[tuple[str, str], ...]] = (
    (CANAL_SONS_DO_JOGO, "Sons do jogo"),
    (CANAL_TODO_O_PC, "Todo o som do PC"),
)

#: As dicas, uma por botão. Curtas de propósito: a dica do slider tinha 206
#: caracteres, ocupava três linhas e aparecia POR CIMA dos botões que ela
#: mandava usar. O detalhe longo (a posse, como devolvê-la) mora na dica do
#: BLOCO — cada altura de detalhe no seu lugar.
DICAS_DO_CANAL: Final[tuple[tuple[str, str], ...]] = (
    (
        CANAL_SONS_DO_JOGO,
        "O que sai no controle: só o que o jogo mandar para ele. A trilha "
        "continua na TV. Depende do jogo ter essa opção.",
    ),
    (
        CANAL_TODO_O_PC,
        "O que sai no controle: todo o som do computador passa a sair pelo "
        "alto-falante dele.",
    ),
)

#: O valor de `OUTPUT_PATH_SEL` de cada canal.
#:
#: `jogo` usa o **2** — canal esquerdo para o fone/TV e o direito para o
#: alto-falante do controle. É o caso que ela descreveu com o Zelda, e é o
#: único dos quatro que separa os dois destinos.
#:
#: `tudo` usa o **3** — só o alto-falante interno: com o som do PC inteiro
#: vindo pelo sink do controle, mandar metade para um fone que não existe
#: seria perder metade.
ROTA_DO_CANAL: Final[dict[str, int]] = {
    CANAL_SONS_DO_JOGO: 2,
    CANAL_TODO_O_PC: 3,
}

#: Rótulos dos DOIS botões do alto-falante (SOM-02, entregas 2 e 3). Cada um
#: diz o que o CLIQUE faz, no mesmo desenho do botão do microfone.
#:
#: Por que DOIS botões e não um só como no microfone: lá as três ações cabem
#: num ciclo porque o firmware DEVOLVE o estado do mudo, e "quem manda" é uma
#: leitura (``mic_mudo_desejado``). Aqui não há leitura nenhuma — a chave
#: ``speaker`` só existe quando a posse é NOSSA, então "posse do firmware" e
#: "mudo por nossa ordem" nunca convivem no mesmo payload e um botão só
#: alternaria eternamente entre Silenciar e Ativar, sem nunca oferecer a
#: devolução. Com dois, mudo e devolução ficam disponíveis ao mesmo tempo, que
#: é o que a sprint pede: a saída não pode depender de passar por um mudo.
TEXTO_BOTAO_SPEAKER_ATIVAR: Final[str] = "Ativar"
TEXTO_BOTAO_SPEAKER_SILENCIAR: Final[str] = "Silenciar"
#: SOM-ROTULO-01 (01/08, pedido dela: *"arruma os dois botões, não sei se faz
#: sentido ter o 'sem dado' e o 'Devolver' — ou renomeia eles ou remove"*).
#:
#: SOLTAR-01 (01/08, decisão dela) — mesma razão do irmão do microfone, acima.
#: E o custo continua mandando: esta linha já é a mais apertada do card (sem
#: posse ela quer 296px num bloco de 243 na janela de projeto) e agora recebe
#: também o botão da rota. Cabe onde "Devolver ao controle" não caberia.
TEXTO_BOTAO_SPEAKER_DEVOLVER: Final[str] = "Liberar"
#: E `sem dado` não era rótulo de ação, era ESTADO escrito dentro de um botão —
#: a janela dizendo "não sei" no lugar onde deveria dizer o que o clique faz.
#: O botão passa a se chamar sempre pela ação e nasce INSENSÍVEL enquanto não
#: há volume conhecido; quem explica o porquê é a dica
#: (:data:`DICA_SPEAKER_MUDO_SEM_DADO`), que é onde a explicação cabe sem
#: mentir. Um botão cinza não promete nada.
TEXTO_BOTAO_SPEAKER_SEM_DADO: Final[str] = "Silenciar"

#: Campo fixo dos rótulos dos botões do alto-falante, em caracteres — medido
#: pelo mais longo deles. Mesma disciplina do botão do microfone: sem teto, o
#: rótulo mais largo decidiria a largura da coluna e trocar de estado moveria
#: os vizinhos de lugar.
_SPEAKER_BOTAO_CHARS: Final[int] = len(TEXTO_BOTAO_SPEAKER_SILENCIAR)

#: O PREÇO do controle deslizante, na dica dele — as três verdades medidas na
#: SOM-02, ditas antes do clique e não depois: (1) a posse passa a ser nossa,
#: (2) ela vale para o alto-falante E para o fone (o backend manda o mesmo
#: valor nos dois bytes, `common[4]` e `common[5]`), e (3) não há leitura, então
#: quem manda continua sendo a janela até a devolução ou a desconexão.
DICA_SPEAKER_ESCALA: Final[str] = (
    "Mover isto faz o hefesto assumir o volume do alto-falante E do fone do "
    "controle. O DualSense não devolve esse valor: depois disso, quem manda é "
    "a janela até você clicar em Liberar ou desconectar o controle."
)

#: As dicas dos botões. A do estado sem dado explica o CAMINHO, e não só a
#: recusa: sem volume conhecido o par mudo/desmudo tranca o alto-falante em
#: zero (o `muted=False` restaura a preferência, e a preferência seria 0).
DICA_SPEAKER_SILENCIAR: Final[str] = (
    "O alto-falante está no volume que o hefesto mandou. Silenciar manda zero "
    "sem perder esse volume — Ativar o devolve."
)
DICA_SPEAKER_ATIVAR: Final[str] = (
    "O alto-falante está mudo por ordem nossa. Ativar devolve o mesmo volume "
    "de antes do mudo."
)
DICA_SPEAKER_SEM_DADO: Final[str] = (
    "Ainda não há volume conhecido — use o controle deslizante primeiro"
)
DICA_SPEAKER_DEVOLVER: Final[str] = (
    "Liberar faz o hefesto parar de mandar o volume, e o botão do controle volta "
    "a valer. O que estiver valendo continua até você desconectar o controle — "
    "o DualSense não devolve o volume anterior."
)
DICA_SPEAKER_DEVOLVER_SEM_POSSE: Final[str] = (
    "Não há o que soltar: o volume ainda é do firmware do controle"
)

#: A linha de explicação no lugar do silêncio (SOM-02/E5), na dica do BLOCO.
#: É a diferença entre "a janela não sabe" e "a janela está quebrada".
DICA_BLOCO_SPEAKER: Final[str] = (
    "O volume é do firmware do controle e ele não o devolve; mover o controle "
    "deslizante passa a mandá-lo"
)

# -- GUARDA-SEM-ENDEREÇO-01: o card sem MAC não comanda o som de ninguém ----
#
# O vocabulário desta guarda fica AQUI, nas duas constantes abaixo, e em lugar
# nenhum além: trocá-lo tem de ser uma linha, e não uma caçada por strings
# (regra de execução da D-9, 14/08/2026).
#
# O defeito que ela cura: TODA saída de som do card viaja com `self._uniq`
# (`mic.set`, `speaker.set` e a ponte por rádio), e o daemon, sem endereço,
# cai no controle **PRIMÁRIO** — que pode ser qualquer um. Num card sem
# `uniq` isso é a pior forma da mentira: ela clica no bloco do Controle 3,
# lê "Controle 3 — BT" no título, e quem muda de volume é o Controle 1.
#
# `uniq` ausente NÃO é hipótese: o `_key_to_uniq` do backend devolve `None`
# sempre que a key do handle é um caminho (`/dev/hidrawN`), o que acontece
# quando o MAC não pôde ser lido do sysfs — e ele devolve `None` de propósito,
# porque a alternativa era publicar um pseudo-MAC.

#: O aviso VISÍVEL, no topo da coluna do som. Ele existe porque bloco
#: desabilitado sem explicação é um defeito do mesmo tamanho do que a guarda
#: cura: ela leria "o produto quebrou". O rótulo diz QUE, a dica diz POR QUÊ —
#: a mesma divisão que o selo do som já usa neste bloco.
TEXTO_AUDIO_SEM_ENDERECO: Final[str] = (
    "Som desligado: este controle está sem endereço"
)

#: O POR QUÊ, na dica dos DOIS blocos de som (microfone e alto-falante). Ela
#: vai na moldura, e não nas peças: no GTK3 um widget insensível não recebe
#: evento e por isso não mostra dica própria — a explicação ficaria invisível
#: exatamente no estado em que ela é necessária (o mesmo desenho de
#: `DICA_SPEAKER_SEM_DADO` no bloco do alto-falante).
DICA_AUDIO_SEM_ENDERECO: Final[str] = (
    "Este controle não publicou endereço, e sem ele todo comando de som iria "
    "para o controle PRIMÁRIO — outro controle, com o título deste na frente. "
    "O som volta sozinho quando o endereço aparecer."
)

#: Selo da CAMADA 1 (SENSOR-VIVO-01/E5): com o sink do controle mudo no
#: PipeWire, mover o volume do registrador HID não produz som nenhum. O selo é
#: o que impede o bloco de parecer mentiroso — e ele só aparece quando a
#: leitura da camada 1 DIZ isso. Sem leitura, nada: inventar "saída muda" a
#: partir de ausência seria a mesma mentira, do outro lado.
TEXTO_SELO_SAIDA_MUDA: Final[str] = "Saída muda"

#: Selo do SOM DE CONFIRMAÇÃO que não saiu (SOM-04, entrega 1, regra 4). Ele é
#: CURTO por medição, não por estilo: o rótulo do selo não tem teto de largura
#: próprio, e a primeira versão desta leva pôs a frase inteira ("sem
#: confirmação: falta paplay ou pw-play na máquina") aqui — o mínimo do bloco
#: saltou de 174 para 383px e o do card de 1040 para **1223**, estourando os
#: 1180px com que a janela abre. No card compacto era pior: 550 para 827, o que
#: com dois cards lado a lado pede 1690px.
#:
#: A cura é a mesma disciplina do card compacto, onde os rótulos dos botões
#: truncam e "quem diz a ação por inteiro é a dica": o selo diz QUE não houve
#: confirmação, e a dica do bloco diz POR QUÊ. Sete caracteres cabem dentro dos
#: dez de ``saída muda``, que já passava no orçamento — o selo continua
#: custando ZERO largura.
TEXTO_SELO_SEM_SOM: Final[str] = "Sem som"

#: Selo do CANAL DORMINDO (SOM-ACORDADO-01, 16/08/2026). Terceiro informante
#: desta mesma linha, pela mesma disciplina dos dois de cima: o selo diz QUE,
#: a dica do bloco diz POR QUÊ, e ele só acende quando há defeito a denunciar.
#:
#: Ele é o par visível de :data:`SUFIXO_CANAL_DORMINDO` no rótulo da moldura.
#: O rótulo é a leitura de relance e vale para os dois estados; o selo é o
#: alarme, e por isso existe só no estado ruim — um selo que diz "acordado"
#: em toda sessão normal gastaria os 19px de altura que ele custa
#: (medido nesta bancada) para não informar nada.
TEXTO_SELO_CANAL_DORMINDO: Final[str] = "Canal dormindo"

#: Teto de largura do selo, em caracteres, medido pelo mais longo dos três
#: textos acima. Sem ele, um texto novo amanhã volta a decidir a largura do
#: bloco — e daí a da janela — sem ninguém perceber.
_SELO_CHARS: Final[int] = max(
    len(TEXTO_SELO_SAIDA_MUDA),
    len(TEXTO_SELO_SEM_SOM),
    len(TEXTO_SELO_CANAL_DORMINDO),
)

# ---------------------------------------------------------------------------
# SOM-ACORDADO-01 (16/08/2026) — os DOIS estados do som na aba Status
# ---------------------------------------------------------------------------
#
# Decisão dela, textual: *"precisamos setar o som sempre em todos os controles
# no 100% e garantir que sempre fique acordado e ligar isso a interface na aba
# de status (config default)"*.
#
# "config default" é a metade que decide o DESENHO: a tela **mostra o estado,
# não oferece um interruptor**. Não há caixa para marcar aqui, e é de propósito
# — quem põe o volume é o daemon e quem impede o sono é o drop-in 54 do
# WirePlumber que o `install.sh` põe SEM FLAG (SOM-QUE-NAO-DORME-01). Um
# interruptor na tela sugeriria que existe uma escolha a fazer, e não existe.
#
# ONDE ISTO APARECE, e por que aí: no **rótulo da moldura**, que já carrega o
# volume desde a CARD-ÚNICO-01 (`Alto-falante · 71 %`). Medido nesta bancada,
# com o card montado e alocado numa `Gtk.OffscreenWindow`:
#
#   =====================================  ============  =================
#   desenho                                bloco mínimo  card mínimo
#   =====================================  ============  =================
#   hoje (`Alto-falante · 100 %`)          183 x 144     1040 x 429
#   `... · acordado` no rótulo             186 x 144     1040 x 429
#   `... · canal acordado` no rótulo       222 x 144     1040 x 429
#   um rótulo NOVO, sempre visível         183 x 163     1040 x 448
#   =====================================  ============  =================
#
# O rótulo da moldura custa **zero altura** e não move o mínimo do card. O
# rótulo novo custa 19px de ALTURA — e a altura é justamente o que não há: o
# `test_status_som_02_controle_de_volume` cobra que a coluna do som não passe
# da maior coluna vizinha por mais de 12px, e 19 estoura isso. Foi o teste
# desta casa que escolheu o desenho, não o gosto.

#: O sufixo que entra no rótulo da moldura em cada estado. "" quando não há
#: leitura — e "" é **não sei**, não "acordado": sem placa de som (o caso do
#: rádio, medido em 15/08/2026) a janela não tem o que afirmar.
SUFIXO_CANAL_ACORDADO: Final[str] = "acordado"
SUFIXO_CANAL_DORMINDO: Final[str] = "dormindo"

#: A frase da dica quando o canal está acordado. Ela diz as DUAS coisas que
#: ela pediu: o estado, e que ele é o PADRÃO — ninguém precisa ligar nada.
DICA_CANAL_ACORDADO: Final[str] = (
    "O canal de áudio deste controle está acordado: o próximo som sai desde o "
    "primeiro instante."
)
#: E a frase quando ele está dormindo. Cada afirmação aqui foi medida com a
#: orelha dela em 15-16/08/2026, no cabo, com o mesmo arquivo, o mesmo volume e
#: a mesma rota: o canal 1 sozinho no nó ocioso saiu "não saiu", e segundos
#: depois, com o nó já acordado, saiu "tuuuuuuuu". Três leituras daquela
#: rodada foram descartadas antes de alguém entender o que estava acontecendo.
DICA_CANAL_DORMINDO: Final[str] = (
    "O canal de áudio deste controle está SUSPENSO no PipeWire. Religar o "
    "hardware come o começo do som — medido: o mesmo canal, no mesmo volume e "
    "na mesma rota, não saiu com o nó ocioso e saiu inteiro com ele acordado. "
    "Num jogo é o efeito sonoro sumindo na hora que importa."
)
#: E a linha que responde "por que eu não preciso ligar isso?". Ela só entra
#: quando a regra ESTÁ no lugar: afirmar que é automático com a cura arrancada
#: seria a tela dando por curado o que não está.
DICA_CANAL_E_PADRAO: Final[str] = (
    "É o padrão: o Hefesto instala a regra que impede o alto-falante de "
    "dormir junto com o produto, para todo controle. Não há nada a ligar aqui."
)
#: A cura foi arrancada (ou nunca entrou). O sintoma no jogo é silencioso, e
#: por isso a tela o denuncia em vez de calar.
DICA_CANAL_SEM_A_REGRA: Final[str] = (
    "A regra que impede o alto-falante de dormir NÃO está instalada nesta "
    "máquina. Rode o install.sh de novo — ela entra sem flag nenhuma."
)
#: Quem manda no volume somos nós, e este é o número. A frase substitui a
#: :data:`DICA_BLOCO_SPEAKER` quando há posse, porque aquela descreve o estado
#: SEM posse ("o volume é do firmware do controle") e passaria a mentir.
DICA_SPEAKER_POSSE_NOSSA: Final[str] = (
    "Quem manda no volume do alto-falante agora é o Hefesto. O DualSense não "
    "devolve esse valor: o número acima é o que NÓS mandamos, não uma leitura "
    "do aparelho."
)

#: Repouso do controle deslizante antes de mandar o volume, em ms. Arrastar
#: emite ``value-changed`` por pixel e o IPC é BLOQUEANTE: sem repouso, um
#: arrasto de 2 cm vira dezenas de pedidos enfileirados no executor de uma
#: thread só. 250 ms é abaixo do que se percebe como demora e acima da cadência
#: de um arrasto.
_SPEAKER_REPOUSO_MS: Final[int] = 250

#: Respiro entre blocos da faixa de leitura, em px. O card compacto (2+
#: controles) usa o menor porque cada px dele soma na largura da janela; o de
#: um controle usa o maior, porque ali o espaço é dele para gastar — e a
#: moldura de cada bloco só se lê como bloco com ar em volta.
_ESPACO_FAIXA_COMPACTO: Final[int] = 8
_ESPACO_FAIXA_UNICO: Final[int] = 16

#: Campo de largura fixa dos labels X/Y (BUG-STATUS-LABEL-REFLOW-01): sem o
#: padding, o texto muda de largura ao cruzar dígitos e o re-layout a 10 Hz
#: faz o painel "respirar".
#:
#: LEGIBILIDADE-01 — duas linhas, e o tamanho saiu do markup. O `size="small"`
#: que estava aqui era RELATIVO à fonte que a distribuição tivesse configurado
#: (rendia 11,1px nesta máquina) e ficava FORA do alcance de qualquer ajuste de
#: tema — a escala global reescreve `font-size` do CSS, não atributo de Pango.
#: Agora o degrau vem da classe `.hefesto-valor-mono` (12px, mono), que cresce
#: junto com o resto. Empilhar X e Y corta a largura do rótulo pela metade, e
#: é essa largura que paga a mudança dos analógicos para a faixa de baixo: numa
#: linha só, o rótulo — e não o desenho do analógico — é quem dizia a largura
#: da cápsula.
#:
#: STATUS-SIMETRIA-02 — a lateral (``L3``/``R3``) mudou do título para cá. No
#: título ela era a terceira palavra e mandava na quebra de linha (3 linhas de
#: um lado, 2 do outro); aqui ela entrou num campo que já é mono e de largura
#: fixa, e a segunda linha recebia espaços do mesmo tamanho para o ``X`` e o
#: ``Y`` continuarem alinhados um sob o outro.
#:
#: CARD-ÚNICO-01, entrega 3 — e agora ela saiu daqui também, para dentro do
#: desenho: *"L3 e R3 saem do X: e vão ficar no centro do desenho do analógico
#: com transparência 70% e grande ao fundo"*. Sem o prefixo, some junto o
#: `pad` de espaços que só existia para alinhar o ``Y`` sob o ``X``.
_XY_MARKUP: Final[str] = "X:{x:>3}\nY:{y:>3}"


def _markup_xy(x: int, y: int) -> str:
    """``"X:128" / "Y:128"`` — o par de eixos, em mono, sem a lateral.

    Quem diz de qual analógico são os números é a marca d'água desenhada
    dentro do círculo, logo acima (``StickPreviewGtk``).
    """
    return _XY_MARKUP.format(x=x, y=y)

# ---------------------------------------------------------------------------
# BT-03 — motivos de degradação em palavras leigas
# ---------------------------------------------------------------------------

#: Motivo técnico (``vpad_motivo`` do state_full) → frase curta leiga. As
#: frases dizem O QUE aconteceu com o "modo completo" (o vocabulário que a
#: aba Início já usa para uhid), sem cravar causa não provada — em especial,
#: NADA de atribuir o sono do Bluetooth (contrato do BT-03).
MOTIVOS_DEGRADACAO_LEIGOS: Final[dict[str, str]] = {
    "uhid_indisponivel": "o modo completo não está disponível neste sistema",
    "uhid_start_falhou": "o modo completo falhou ao iniciar",
    "uhid_bind_falhou": "o sistema não aceitou o modo completo",
    "uhid_vetado_pelo_chamador": "o modo completo foi desligado nesta sessão",
    "sem_uhid": "o modo completo não subiu",
}

#: Sentinela para caches de diff cujo valor válido inclui ``None``.
_SENTINELA: Final[object] = object()


# ---------------------------------------------------------------------------
# Funções puras (testáveis sem GTK) — o widget real e o stub usam as mesmas
# ---------------------------------------------------------------------------


def _rgb3(valor: Any) -> RGB | None:
    """Normaliza o ``lightbar_rgb`` do IPC (``[r, g, b]``/tuple) em tuple.

    ``None`` para qualquer coisa fora do contrato (ausente, tamanho errado,
    canal não numérico) — o chamador trata como "sem cor conhecida".
    """
    if isinstance(valor, (list, tuple)) and len(valor) == 3:
        try:
            r, g, b = (max(0, min(255, int(c))) for c in valor)
        except (TypeError, ValueError):
            return None
        return (r, g, b)
    return None


def _int_ou_none(valor: Any) -> int | None:
    """int estrito (rejeita bool — blindagem contra payload malformado)."""
    if isinstance(valor, int) and not isinstance(valor, bool):
        return valor
    return None


def titulo_do_card(entry: dict[str, Any]) -> str:
    """Título "Controle {N} — {USB|BT}[ · Jogador {X}]" (função pura).

    ``N`` é o ``player_slot`` de sessão (COR-01/D6 — o MESMO número da CLI e
    do applet); sem slot (registry ausente, controle sem MAC) cai em
    ``index + 1``, a posição 1-based. O sufixo "· Jogador {X}" só aparece
    quando o daemon numerou um jogador (D7): fora do co-op todos os controles
    alimentam o MESMO vpad e o jogo vê um controle só — inventar número de
    jogador seria mentira.
    """
    slot = _int_ou_none(entry.get("player_slot"))
    if slot is None:
        indice = _int_ou_none(entry.get("index"))
        slot = (indice + 1) if indice is not None else 1
    transporte = str(entry.get("transport") or "?").upper()
    titulo = f"Controle {slot} — {transporte}"
    jogador = _int_ou_none(entry.get("player"))
    if jogador is not None:
        titulo += f" · Jogador {jogador}"
    return titulo


#: QUEM-É-QUEM-01: o que a dica diz quando o físico já está na mesa mas
#: o gamepad virtual dele ainda não nasceu (grab pendente, ou emulação
#: desligada). Frase separada de propósito: "ainda não" e "não sei" são
#: respostas diferentes, e o card já pagou caro por dizê-las igual.
DICA_TITULO_SEM_VPAD: Final[str] = (
    "Este controle ainda não alimenta gamepad virtual nenhum."
)


def dica_do_titulo(entry: dict[str, Any], state_global: dict[str, Any]) -> str | None:
    """Dica do título: QUAL gamepad virtual este controle alimenta (função pura).

    QUEM-É-QUEM-01 (15/08/2026). O título já diz *"Controle 2 — USB ·
    Jogador 3"*; o que faltava era o outro lado do par — **qual vpad esse
    jogador é**, com o endereço por onde `quem_e_quem.py` e o `/sys` o
    enxergam. Sem isso, conferir se o produto ligou cada físico ao vpad certo
    custava apertar botão em cada controle, um por um.

    Por que uma DICA e não uma linha do card, e a escolha é deliberada:

    * o endereço é **diagnóstico**, não vocabulário de interface — o alvo por
      MAC foi derrubado por ela em 13/08/2026 como estratégia de produto, e
      nada aqui o reabre: a dica não seleciona nada, não é rótulo e não muda
      uma palavra do que o card já mostra;
    * o corpo do card tem altura amarrada (ver o cabeçalho deste módulo, e a
      LEGIBILIDADE-01), e uma linha nova empurraria os quatro cards da mesa
      dela. A dica aparece sob o cursor, no lugar exato do que ela quer
      conferir, e custa zero pixel.

    ``None`` = sem nada a dizer (controle sem endereço, daemon antigo sem a
    lista, ou controle que não está na mesa de jogadores) — a dica some, em
    vez de o card inventar um par.
    """
    uniq = uniq_do_entry(entry)
    if uniq is None:
        return None
    coop = state_global.get("coop")
    mesa = coop.get("mesa") if isinstance(coop, dict) else None
    if not isinstance(mesa, list):
        return None
    for item in mesa:
        if not isinstance(item, dict) or item.get("uniq") != uniq:
            continue
        backend = item.get("vpad_backend")
        if not isinstance(backend, str) or not backend:
            return DICA_TITULO_SEM_VPAD
        numero = _int_ou_none(item.get("player"))
        alvo = f"do Jogador {numero}" if numero else "deste jogador"
        vpad_uniq = item.get("vpad_uniq")
        detalhe = (
            f"{backend} · {vpad_uniq}"
            if isinstance(vpad_uniq, str) and vpad_uniq
            else backend
        )
        frase = f"Alimenta o gamepad virtual {alvo} ({detalhe})."
        # E3 do QUEM-É-QUEM-01: o nome do vpad congela o índice de ALOCAÇÃO, e
        # desde a MESA-CHEIA-12 ele pode não ser o número da fila. Quem estiver
        # conferindo card↔dispositivo tem de ver o nome REAL, senão procura
        # "Hefesto P2" e encontra "Hefesto P4" sem entender por quê.
        nome = item.get("vpad_nome")
        if item.get("nome_divergente") and isinstance(nome, str) and nome:
            frase += f" No sistema ele se chama “{nome}”."
        return frase
    return None


def rotulo_lightbar(
    entry: dict[str, Any], state_global: dict[str, Any]
) -> tuple[str | None, RGB | None]:
    """``(rótulo, cor_base_do_accent)`` da lightbar de UM controle.

    Regras (STATUS-03 + refutação 1 do sprint — o dono da escrita decide):

    * ``native_mode`` global → "em Nativo o jogo é dono do LED"; o accent usa
      a última cor conhecida (ou o neutro, se nenhuma). O jogo escreve por
      hidraw e o daemon não pisa no LED — o card avisa em vez de mentir.
    * ``lightbar_disputada`` (ESCRITOR-CRU-01) → "a Steam também escreve
      nesta barra"; o accent segue a última cor NOSSA. Vem logo depois do
      Nativo e antes de tudo o mais porque é um aviso sobre a CONFIANÇA no
      valor, não sobre o valor: com a Steam segurando o hidraw, o que a
      classe LED devolve é o que o Hefesto PEDIU — a madrugada de 16/08 leu
      ``[0 255 0]`` com a barra apagada e ``[0 255 0]`` com ela verde. Dizer
      "apagada" ou pintar a bolinha de verde sem ressalva seria, nos dois
      casos, afirmar o que ninguém mediu.
    * ``lightbar_source == "desconhecida"`` (ou rgb ausente) → "Lightbar: cor
      desconhecida" + accent neutro. NUNCA "apagada": o 0,0,0 do sysfs sem
      escrita nossa pode ser o azul-kernel brilhando neste exato momento.
    * fonte conhecida (``sysfs``/``desired`` — a escrita foi NOSSA) e apagada
      (``lightbar_on`` False ou rgb preto) → "Lightbar: apagada" + neutro.
    * cor conhecida e acesa → sem rótulo; o accent é a própria cor.

    A cor devolvida é a BASE do accent (crua); ``None`` = usar o neutro.
    O chamador ajusta com ``ensure_min_contrast`` antes de pintar traço.
    """
    rgb = _rgb3(entry.get("lightbar_rgb"))
    if bool(state_global.get("native_mode")):
        return ("Em Nativo o jogo é dono do LED", rgb)
    if bool(entry.get("lightbar_disputada")):
        return ("A Steam também escreve nesta barra", rgb)
    fonte = str(entry.get("lightbar_source") or "desconhecida")
    if fonte == "desconhecida" or rgb is None:
        return ("Lightbar: cor desconhecida", None)
    if not bool(entry.get("lightbar_on")) or rgb == (0, 0, 0):
        return ("Lightbar: apagada", None)
    return (None, rgb)


def texto_degradacao(entry: dict[str, Any]) -> str | None:
    """Linha do badge de degradação (BT-03); ``None`` = badge some.

    Só acende com ``vpad_backend == "uinput"`` E ``vpad_motivo`` preenchido:
    máscara xbox é uinput POR DESIGN (motivo None) e não é degradação;
    controle sem vpad próprio (backend None — co-op off/pending/emulação
    off) idem. Motivo fora do mapa aparece com os ``_`` trocados por espaço
    (diagnosticável sem quebrar com motivo novo do daemon).
    """
    if entry.get("vpad_backend") != "uinput":
        return None
    motivo = entry.get("vpad_motivo")
    if not isinstance(motivo, str) or not motivo:
        return None
    legivel = MOTIVOS_DEGRADACAO_LEIGOS.get(motivo, motivo.replace("_", " "))
    return f"Emulação degradada (uinput): {legivel}"


def texto_motion(entry: dict[str, Any], state_global: dict[str, Any]) -> str | None:
    """Linha discreta do giroscópio espelhado (GYRO-03); ``None`` = some.

    Só aparece quando o vpad DESTE controle está com o espelho de motion
    ATIVO (``motion_streaming`` no ``rumble_ff.per_vpad`` do state_full) —
    a ausência da linha não é alarme: uinput/máscara xbox/Modo Nativo não
    têm espelho por design, e acusar "sem giroscópio" em todo card seria
    ruído crônico (quem diagnostica silêncio anômalo é o doctor).

    Mapeamento controle→vpad: entrada com ``player`` numerado (co-op, D7)
    casa com o vpad daquele jogador; sem número, o PRIMÁRIO casa com o vpad
    do P1 (fora do co-op o espelho só existe nele). Demais controles → None.

    GYRO-03-FIX: jogador 1 SEM ``is_primary`` nunca mostra a linha — fora do
    co-op ``resolve_player_numbers`` numera TODOS os conectados como jogador
    1 (é o que o jogo vê), mas o espelho do vpad P1 lê só o hidraw do
    PRIMÁRIO; exibir a linha num secundário seria telemetria mentindo.

    PAINEL-DA-VERDADE-01 acrescentou DOIS casos em que o silêncio deixa de
    ser a resposta certa, e só dois. A decisão medida acima continua inteira
    — a ausência da linha não é alarme, e "sem giroscópio" em todo card seria
    ruído crônico. O que mudou é que há duas situações em que o silêncio faz
    a tela parecer QUEBRADA quando ela está certa:

    * **máscara Xbox 360** — o jogo não recebe giroscópio, e o motivo não é
      defeito nosso: a API do controle de Xbox não tem esse sensor. Sem a
      frase, ela vê um card com giroscópio desenhado e nenhum sinal de que o
      dado não sai dali;
    * **Modo Nativo** — não existe gamepad virtual, e perguntar se o dado
      "chegou ao vpad" não faz sentido. O jogo abre o hidraw do controle
      físico e recebe tudo, inclusive o giroscópio.

    Nos dois casos a frase EXPLICA; nos demais o silêncio continua.
    """
    if bool(state_global.get("native_mode")):
        return f"Giroscópio: {_FRASE_NATIVO}"
    if _mascara_e_xbox(state_global):
        return f"Giroscópio: {_FRASE_MASCARA_XBOX['giroscopio']}"
    rumble_ff = state_global.get("rumble_ff")
    per_vpad = rumble_ff.get("per_vpad") if isinstance(rumble_ff, dict) else None
    if not isinstance(per_vpad, list):
        return None
    player = _int_ou_none(entry.get("player"))
    if player == 1 and not bool(entry.get("is_primary")):
        # Co-op OFF com 2+ DualSense: todos vêm com player=1, mas só o
        # primário tem reader de motion. (Em co-op, o jogador 1 É o primário
        # e os secundários recebem índices >= 2 — o guarda não os afeta.)
        return None
    if player is None:
        if not bool(entry.get("is_primary")):
            return None
        player = 1
    for item in per_vpad:
        if not isinstance(item, dict) or _int_ou_none(item.get("player")) != player:
            continue
        if item.get("motion_streaming") is not True:
            return None
        hz = item.get("motion_hz")
        if isinstance(hz, (int, float)) and not isinstance(hz, bool) and hz > 0:
            return f"Giroscópio: fluindo para o jogo (~{hz:.0f} Hz)"
        return "Giroscópio: fluindo para o jogo"
    return None


# ---------------------------------------------------------------------------
# PAINEL-DA-VERDADE-01 — o que CHEGA ao jogo, e não o que existe
# ---------------------------------------------------------------------------
#
# O pedido dela, literal: *"naquela aba de Status podemos ver o funcionamento
# de tudo, e o funcionamento de lá obviamente impacta o funcionamento real do
# controle na hora de jogar"*.
#
# Hoje a aba mostra que o sensor EXISTE. Ela quer saber se ele CHEGA. São
# perguntas diferentes, e a diferença já produziu um diagnóstico errado nesta
# casa em 01/08.
#
# **A honestidade que estas frases têm de manter.** Nenhuma delas afirma que o
# JOGO consumiu o dado — isso é medição de fora, e depende de qual biblioteca
# o jogo carregou (medido em 01/08: a `libSDL2` do Ubuntu não enumera o gamepad
# virtual; a SDL3 que a Steam distribui enumera). O que estas frases afirmam é
# o que o daemon PODE saber: o dado saiu daqui, e alguém escreveu de volta.

#: Quanto tempo sem evento até a tela parar de dizer "chegando", em segundos.
#:
#: 3,0 s é o mesmo teto do `_RUMBLE_STALE_SEC` do vpad, e não por comodidade:
#: as categorias são eventos ESPARSOS (um jogo manda um efeito de gatilho
#: quando a arma muda, não a cada quadro), e um teto curto faria a tela piscar
#: entre "chegando" e "parado" no meio de uma partida. O giroscópio, que é
#: fluxo contínuo, não passa por aqui — ele tem `motion_hz`, com morte por
#: inatividade própria (`_HZ_STALE_S`, 1,0 s).
ATIVIDADE_FRESCA_S: Final[float] = 3.0

#: Teto de largura da linha da verdade, em CARACTERES.
#:
#: Ele existe porque a linha é a única do card que pode ficar longa (cinco
#: recursos, três situações), e um parágrafo de uma linha só esticaria o
#: mínimo do card — que sobe intacto até a janela, numa aba sem rolagem
#: horizontal. Com o teto, ele quebra em duas linhas antes de empurrar
#: qualquer coisa.
#:
#: `max_width_chars` NÃO basta sozinho, e isto foi medido aqui em 01/08: ele
#: limita a largura NATURAL (o que o widget PEDE) e o pai continua livre para
#: alocar mais — um parágrafo de 1869px ficou intacto. Precisa de
#: `halign=start` junto, e é assim que ele é usado.
_VERDADE_MAX_CHARS: Final[int] = 110

#: O Hz mais largo que a linha da verdade pode imprimir, para MEDIR a régua.
#:
#: NAO-DANCA-01. Não é teto de nada e não entra em tela nenhuma: serve só para
#: :func:`frase_mais_longa_do_que_chega_ao_jogo` montar o pior caso. Quatro
#: dígitos porque o `motion_hz` é medido, não declarado — o DualSense entrega
#: IMU a algumas centenas de hertz, e um pico de quatro dígitos num payload é
#: barato de acomodar aqui e caro de descobrir na tela dela.
_HZ_MAIS_LARGO: Final[str] = "1000"

#: E o maior valor de motor, pela mesma razão. 255 é o teto de um byte, que é
#: o que o par `rumble_no_fisico` carrega (`uhid_gamepad`).
_MOTOR_MAIS_LARGO: Final[str] = "255"

#: As quatro situações que um recurso pode estar, e o que cada uma significa.
#: `NUNCA` e `PARADO` são separadas de propósito: "o jogo ainda não pediu" e
#: "o jogo pediu e parou" levam a ações diferentes de quem lê.
SITUACAO_CHEGANDO: Final[str] = "chegando"
SITUACAO_PARADO: Final[str] = "parado"
SITUACAO_NUNCA: Final[str] = "nunca"
SITUACAO_IMPOSSIVEL: Final[str] = "impossivel"
SITUACAO_NATIVO: Final[str] = "nativo"


class EstadoDoRecurso(NamedTuple):
    """A situação de um recurso e a frase que a diz, em português leigo."""

    situacao: str
    frase: str


#: Os recursos que a máscara Xbox 360 APAGA, e a razão. Ela não é do Hefesto:
#: a API do controle de Xbox declara 8 eixos e 11 botões, e não há onde pôr
#: IMU nem dedo. O `virtual_pad` recusa o backend uhid para todo sabor que não
#: seja `dualsense`, então nem o caminho existe.
RECURSOS_SEM_MASCARA_XBOX: Final[frozenset[str]] = frozenset(
    {"giroscopio", "touchpad"}
)

#: Recurso → a categoria de atividade que o vpad carimba por ele
#: (`uhid_gamepad.ATIVIDADE_*`). Recurso fora deste mapa não tem carimbo e
#: responde por outra via (o giroscópio, por `motion_hz`).
_CATEGORIA_DO_RECURSO: Final[dict[str, str]] = {
    "touchpad": "touchpad_click",
    "lightbar": "lightbar",
    "gatilho": "trigger",
    "vibracao": "rumble",
    # SOM-DO-JOGO-NA-LINHA-01 (09/08/2026, decisão dela: *"sim, na linha de
    # recursos do card"*). O carimbo `audio_do_jogo` existe no vpad desde
    # 02/08 (PARIDADE-SONY-01/E1) e NADA na janela o lia — mais um órfão da
    # mesma família dos quatro de hoje, e o único que já tinha respondido
    # "sim" ao vivo: medido com o jogo aberto, `{flag0: 160, fone: 0,
    # alto_falante: 100, microfone: 0, rota: 48}`.
    #
    # É o recurso que ela descreveu assim: *"o jogo tem duas saídas de áudio:
    # a do HDMI, que é a do jogo padrão, e a do speaker do controle, que
    # normalmente é uma feature extra usada pra adicionar efeitos sonoros
    # extras, SFX. (...) no Zelda Skyward Sword, ao golpear com o Link usando
    # uma espada, o efeito de uma lâmina cortando o ar sai pelo speaker do
    # próprio controle. A Sony fez o mesmo pro DualSense."*
    #
    # O carimbo é EXATAMENTE a pergunta da linha, e por construção: ele só sai
    # quando o escritor liga um dos quatro bits de áudio, manda byte não-nulo
    # E há sessão de jogo aberta (`_replicating()`) — o áudio que o PROBE do
    # `hid-playstation` escreve ao nascer do vpad não entra, que foi a
    # correção de 02/08. Por isso "sem pedido ainda" aqui significa mesmo
    # "nenhum jogo pediu", e não "o kernel ainda não passou por aqui".
    "alto_falante": "audio_do_jogo",
}

#: O nome de cada recurso na frase, e a ORDEM em que eles aparecem nela.
#:
#: **Por que uma frase só, e não um selo em cada bloco.** O desenho óbvio —
#: e o que a sprint sugeria — era um indicador dentro de cada moldura. Ele foi
#: descartado por medida, não por gosto: as colunas do Touchpad e da Lightbar
#: têm ~180px na tela dela, e o próprio comentário do `_montar_touchpad`
#: registra que um "sem toque" ao lado do título já fazia a coluna pedir 105px
#: para desenhar um painel de 76. Cinco frases explicativas espalhadas custam
#: largura onde não há, e altura em quatro lugares.
#:
#: A linha única custa UMA altura, mora na faixa larga do topo do card (onde
#: sobra vão) e responde a pergunta dela de uma vez — que era uma pergunta
#: sobre o conjunto, não sobre cada peça: *"não sei se o alto-falante,
#: giroscópio, microfone e touchpad — todas as features — na hora de jogar um
#: jogo na Steam se elas vão estar funcionando"*.
#:
#: SOM-DO-JOGO-NA-LINHA-01: o alto-falante entra por ÚLTIMO e sem número.
#: Sem número por decisão dela — a linha diz que o som está chegando, e não
#: em que volume; a amostra medida (`audio_do_jogo_amostra`) continua sendo
#: dado de diagnóstico, não texto de tela. E o nome vem do léxico que o card
#: já usa nos dois lugares que falam disto: o rótulo do canal ("Sons do
#: jogo", `CANAIS_DO_SPEAKER`) e o nome da peça ("alto-falante", em toda a
#: coluna do som). O nome final é DELA, escolhido em 09/08/2026 ao ver as
#: duas opções: ela chamou o recurso assim quando o explicou — *"a do
#: speaker do controle, que normalmente é uma feature extra usada pra
#: adicionar efeitos sonoros extras"*. Não é uma
#: palavra nova.
_NOME_NA_FRASE: Final[tuple[tuple[str, str], ...]] = (
    ("giroscopio", "giroscópio"),
    ("vibracao", "vibração"),
    ("gatilho", "gatilho"),
    ("lightbar", "luz"),
    ("touchpad", "clique do touchpad"),
    ("alto_falante", "som do controle"),
)

#: A frase do estado IMPOSSÍVEL, por recurso. Ela é a mais valiosa das quatro
#: e é a que hoje não existe: com máscara Xbox o card mostra um sensor apagado
#: como se estivesse quebrado, quando o que houve é que a API escolhida não
#: tem aquele sensor. O texto longo e explicativo continua sendo o
#: `home_actions.TEXTO_CUSTO_MASCARA_XBOX` — este é a versão de uma linha, para
#: caber dentro do bloco.
_FRASE_MASCARA_XBOX: Final[dict[str, str]] = {
    "giroscopio": "a máscara Xbox 360 não tem giroscópio",
    "touchpad": "a máscara Xbox 360 não tem touchpad",
}

#: E a do Modo Nativo, em que não há gamepad virtual nenhum: o jogo abre o
#: hidraw do controle FÍSICO e fala com ele direto. Tudo chega — não porque
#: nós entregamos, mas porque não há intermediário.
_FRASE_NATIVO: Final[str] = "o jogo fala direto com o controle"


def _item_do_vpad(
    entry: dict[str, Any], state_global: dict[str, Any]
) -> dict[str, Any] | None:
    """O bloco `rumble_ff.per_vpad` do vpad DESTE controle; ``None`` = não há.

    O casamento controle→vpad é o MESMO do `texto_motion`, e as regras dele
    estão documentadas lá — inclusive o guarda do GYRO-03-FIX (jogador 1 sem
    `is_primary` nunca casa: fora do co-op todos os conectados vêm como
    jogador 1, mas só o primário tem reader).

    Este é o dono único do casamento. Dois jeitos de responder "qual vpad é o
    deste controle" divergiriam na primeira mudança do co-op, e esta casa tem
    defeito registrado com essa forma exata.
    """
    rumble_ff = state_global.get("rumble_ff")
    per_vpad = rumble_ff.get("per_vpad") if isinstance(rumble_ff, dict) else None
    if not isinstance(per_vpad, list):
        return None
    player = _int_ou_none(entry.get("player"))
    if player == 1 and not bool(entry.get("is_primary")):
        return None
    if player is None:
        if not bool(entry.get("is_primary")):
            return None
        player = 1
    for item in per_vpad:
        if isinstance(item, dict) and _int_ou_none(item.get("player")) == player:
            return item
    return None


def _visto_ha_s_do_vpad(entry: dict[str, Any], state_global: dict[str, Any]) -> Any:
    """O bloco `visto_ha_s` do vpad deste controle; ``None`` se não há vpad.

    ``None`` distingue "não há vpad" de "há vpad e nada aconteceu" (que é
    `{}`) — a tela diz coisas diferentes nos dois casos.
    """
    item = _item_do_vpad(entry, state_global)
    if item is None:
        return None
    visto = item.get("visto_ha_s")
    return visto if isinstance(visto, dict) else {}


def _contagem(item: Any, chave: str) -> int:
    """Um contador cumulativo do bloco do vpad; 0 quando não há.

    ORFAOS-QUE-VOLTAM-01. Um `int` estrito: daemon antigo não manda a chave, e
    um `MagicMock` de teste devolveria algo que compara `> 0` com qualquer
    coisa — a mesma blindagem que o resto deste módulo já aplica a `motion_hz`.
    """
    if not isinstance(item, dict):
        return 0
    valor = item.get(chave)
    if isinstance(valor, bool) or not isinstance(valor, int):
        return 0
    return valor


def motores_no_fisico(item: Any) -> tuple[int, int] | None:
    """``(weak, strong)`` que chegou AOS MOTORES agora; ``None`` = nada a dizer.

    MOTOR-QUE-NAO-SE-VE-01 (09/08/2026). Três respostas viram ``None``, e as
    três de propósito:

    * **daemon antigo / vpad uinput** — a chave não existe. Silêncio, como em
      todo campo opcional deste payload;
    * **nunca escreveu** (``rumble_no_fisico_ha_s`` ausente) — dizer 0/0 aqui
      seria afirmar que os motores receberam uma parada, quando o que houve
      foi ninguém ter escrito;
    * **velho** — mais de `ATIVIDADE_FRESCA_S` sem escrita. É o mesmo teto que
      governa o resto da linha, e pelo mesmo motivo: um número congelado de
      três minutos atrás ao lado da palavra "chegando" é a mentira confortável
      que esta tela existe para não contar.

    O par ``(0, 0)`` fresco também some: ele é o jogo mandando PARAR, e a
    parada não é o número que responde *"a vibração saiu do nosso lado?"*.
    """
    if not isinstance(item, dict):
        return None
    idade = item.get("rumble_no_fisico_ha_s")
    if isinstance(idade, bool) or not isinstance(idade, (int, float)):
        return None
    if idade > ATIVIDADE_FRESCA_S:
        return None
    par = item.get("rumble_no_fisico")
    if not isinstance(par, (list, tuple)) or len(par) != 2:
        return None
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in par):
        return None
    if par[0] == 0 and par[1] == 0:
        return None
    return (int(par[0]), int(par[1]))


def estado_do_recurso(
    recurso: str, entry: dict[str, Any], state_global: dict[str, Any]
) -> EstadoDoRecurso | None:
    """A situação de um recurso AGORA; ``None`` = não há o que afirmar.

    PAINEL-DA-VERDADE-01/E2. A ordem das perguntas é a ordem da verdade, e
    não pode ser trocada:

    1. **Modo Nativo?** Não há gamepad virtual — o jogo fala direto com o
       hidraw do controle. Perguntar "chegou ao vpad?" não faria sentido, e
       responder "não" seria mentira;
    2. **A máscara apaga este recurso?** Então ele não chega, não vai chegar,
       e o motivo não é defeito nosso: o controle de Xbox não tem giroscópio
       nem touchpad. É o estado que hoje não existe e que faz a tela parecer
       quebrada quando ela está certa;
    3. **Há vpad?** Sem vpad não há caminho, e ``None`` deixa o card mudo em
       vez de acusar;
    4. **Só então** o carimbo decide entre chegando, parado e nunca.

    ``None`` também para recurso desconhecido: inventar frase a partir de
    payload incompleto é a família de erro que esta casa já removeu do
    `texto_do_custo_da_mascara`.
    """
    if bool(state_global.get("native_mode")):
        return EstadoDoRecurso(SITUACAO_NATIVO, _FRASE_NATIVO)

    if recurso in RECURSOS_SEM_MASCARA_XBOX and _mascara_e_xbox(state_global):
        frase = _FRASE_MASCARA_XBOX.get(recurso)
        return EstadoDoRecurso(SITUACAO_IMPOSSIVEL, frase) if frase else None

    visto = _visto_ha_s_do_vpad(entry, state_global)
    if visto is None:
        return None

    item = _item_do_vpad(entry, state_global)

    if recurso == "giroscopio":
        # O giroscópio não passa por carimbo: ele é fluxo CONTÍNUO e já tem
        # medida própria de recência (`motion_hz`, com morte por inatividade
        # em 1,0 s no `physical_report_reader`). Reaproveitar o carimbo aqui
        # seria um segundo jeito de dizer "agora" no mesmo payload — e o
        # `motion_hz` é melhor: ele traz o número que ela vê na tela.
        if not isinstance(item, dict) or item.get("motion_streaming") is not True:
            # ORFAOS-QUE-VOLTAM-01 (09/08/2026): sem espelho vivo, o card dizia
            # "sem pedido ainda" — inclusive depois de meia hora de giroscópio
            # fluindo, se o reader tivesse acabado de cair. As duas situações
            # mandam agir em lugares opostos ("nunca ligou" é fiação; "parou"
            # é o reader/o rádio), e a própria constante desta tela existe
            # para não as confundir. Quem as separa é `motion_forwards`, o
            # contador CUMULATIVO de janelas que o vpad de fato escreveu no
            # /dev/uhid — a property `motion_forward_count` existia desde
            # 19/07 e nunca tinha sido lida por ninguém.
            if _contagem(item, "motion_forwards") > 0:
                return EstadoDoRecurso(SITUACAO_PARADO, "giroscópio")
            return EstadoDoRecurso(SITUACAO_NUNCA, "giroscópio")
        hz = item.get("motion_hz")
        if isinstance(hz, (int, float)) and not isinstance(hz, bool) and hz > 0:
            return EstadoDoRecurso(
                SITUACAO_CHEGANDO, f"giroscópio (~{hz:.0f} Hz)"
            )
        return EstadoDoRecurso(SITUACAO_CHEGANDO, "giroscópio")

    categoria = _CATEGORIA_DO_RECURSO.get(recurso)
    if categoria is None:
        return None
    nome = dict(_NOME_NA_FRASE)[recurso]

    # ORFAOS-QUE-VOLTAM-01: o clique SEGURADO. O carimbo marca a BORDA (a
    # pressionada), então um dedo que fica em cima do touchpad por mais de
    # `ATIVIDADE_FRESCA_S` fazia a tela dizer "parou" com o botão ainda
    # apertado dentro do jogo — o oposto do que estava acontecendo. O estado
    # vivo vence o carimbo, e só nesse sentido: ele pode PROMOVER a chegando,
    # nunca rebaixar. A property `touchpad_click` estava no vpad desde a
    # TOUCH-CLICK-01 sem uma única leitura real.
    if (
        recurso == "touchpad"
        and isinstance(item, dict)
        and item.get("touchpad_pressionado") is True
    ):
        return EstadoDoRecurso(SITUACAO_CHEGANDO, nome)

    idade = visto.get(categoria)
    if not isinstance(idade, (int, float)) or isinstance(idade, bool):
        situacao = SITUACAO_NUNCA
    elif idade <= ATIVIDADE_FRESCA_S:
        situacao = SITUACAO_CHEGANDO
    else:
        situacao = SITUACAO_PARADO

    # MOTOR-QUE-NAO-SE-VE-01: a vibração ganha o número que ela pediu — o par
    # que foi AOS MOTORES, e não o que o jogo pediu ao vpad. Entre um e outro
    # há a política de intensidade: em `economia` (0,3) um pedido de 20 chega
    # como 6 e um de 1 chega como ZERO, e a linha dizia "chegando" nos dois
    # casos. Mesmo desenho do `(~250 Hz)` do giroscópio: o número entra na
    # frase só quando ele existe e é fresco.
    if recurso == "vibracao" and situacao == SITUACAO_CHEGANDO:
        motores = motores_no_fisico(item)
        if motores is not None:
            nome = f"{nome} (motores: {motores[0]}/{motores[1]})"

    return EstadoDoRecurso(situacao, nome)


def resumo_do_que_chega_ao_jogo(
    entry: dict[str, Any], state_global: dict[str, Any]
) -> str | None:
    """A linha que responde *"vai funcionar na hora de jogar?"*; ``None`` = some.

    PAINEL-DA-VERDADE-01/E2 — a entrega central da sprint, em uma frase.

    **O que ela afirma, e o que ela cuidadosamente NÃO afirma.** Ela diz que o
    dado saiu do daemon e que alguém escreveu de volta no gamepad virtual. Ela
    NÃO diz que o jogo consumiu — isso depende de qual biblioteca o jogo
    carregou, e essa medição é de fora: em 01/08 a `libSDL2` 2.30.0 do Ubuntu
    não enumerava o gamepad virtual e a SDL3 3.4.10 que a Steam distribui
    enumerava por completo. Uma tela que dissesse "o jogo está recebendo" sem
    saber qual das duas está carregada estaria adivinhando, e foi exatamente
    esse tipo de afirmação que produziu um diagnóstico errado nesta casa.

    Por isso o vocabulário é "no jogo agora" (o caminho está com tráfego) e
    "sem pedido ainda" (o caminho existe e ninguém usou) — e nunca "o jogo
    recebeu".
    """
    if bool(state_global.get("native_mode")):
        return "Modo Nativo: o jogo fala direto com o controle — tudo chega."
    if _mascara_e_xbox(state_global):
        return (
            "Máscara Xbox 360: giroscópio e touchpad não chegam ao jogo — o "
            "controle de Xbox não tem esses dois. Vibração, luz e gatilho vão."
        )
    if _visto_ha_s_do_vpad(entry, state_global) is None:
        return None

    por_situacao: dict[str, list[str]] = {}
    for recurso, _nome in _NOME_NA_FRASE:
        estado = estado_do_recurso(recurso, entry, state_global)
        if estado is None:
            continue
        por_situacao.setdefault(estado.situacao, []).append(estado.frase)

    partes = []
    if por_situacao.get(SITUACAO_CHEGANDO):
        partes.append(
            "No jogo agora: " + ", ".join(por_situacao[SITUACAO_CHEGANDO])
        )
    if por_situacao.get(SITUACAO_PARADO):
        partes.append("pararam: " + ", ".join(por_situacao[SITUACAO_PARADO]))
    if por_situacao.get(SITUACAO_NUNCA):
        partes.append(
            "sem pedido ainda: " + ", ".join(por_situacao[SITUACAO_NUNCA])
        )
    if not partes:
        return None
    # A frase começa por "No jogo agora" quando há tráfego; quando não há, a
    # primeira parte é "pararam"/"sem pedido ainda" e precisa da maiúscula.
    # `capitalize()` não serve: ele rebaixa o resto da frase, e há nomes com
    # maiúscula no meio dela.
    texto = " · ".join(partes) + "."
    return texto[0].upper() + texto[1:]


def frase_mais_longa_do_que_chega_ao_jogo() -> str:
    """A MAIOR frase que :func:`resumo_do_que_chega_ao_jogo` sabe montar.

    NAO-DANCA-01 (13/08/2026). Ela não é para ser mostrada a ninguém: é a
    régua que reserva a altura da linha da verdade no card, para que a frase
    encolher ou crescer não mova mais nada — o defeito que ela relatou assim:
    *"não sei se dá pra ver mas o layout fica sambando aqui na interface"*.

    **Por que a maior frase, e não um número de linhas escrito à mão.** A
    altura que se reserva tem de ser a altura MÁXIMA que a frase pode pedir,
    e essa altura depende da largura que o card recebeu e da escala de fonte
    dela — as duas mudam. Um "2" cravado no código seria um número inventado
    que envelhece calado no dia em que um recurso ganhar nome mais longo.

    O que torna esta frase a maior, item por item:

    * **os TRÊS grupos aparecem**. Os seis recursos estão sempre na frase; o
      que muda é como se repartem. Com os três prefixos na tela ("No jogo
      agora: ", "pararam: ", "sem pedido ainda: ") e os dois " · " que os
      separam, o texto fixo é o mais longo possível — e o número de ", " entre
      nomes é o mesmo em qualquer repartição (seis nomes menos três grupos);
    * **os dois detalhes numéricos entram**, e os dois só existem na situação
      "chegando" (o `(~N Hz)` do giroscópio e o `(motores: a/b)` da vibração),
      então os dois moram no primeiro grupo;
    * **os números vão no maior tamanho que podem ter**: o Hz com quatro
      dígitos e os motores com os três de 255, que é o teto de um byte.

    Deriva de :data:`_NOME_NA_FRASE` de propósito: ela é a lista-dona dos
    recursos, e uma cópia dos nomes aqui viraria mentira no primeiro rename.
    """
    nomes = dict(_NOME_NA_FRASE)
    com_detalhe = ("giroscopio", "vibracao")
    chegando = [
        f"{nomes['giroscopio']} (~{_HZ_MAIS_LARGO} Hz)",
        f"{nomes['vibracao']} (motores: {_MOTOR_MAIS_LARGO}/{_MOTOR_MAIS_LARGO})",
    ]
    restantes = [
        nome for recurso, nome in _NOME_NA_FRASE if recurso not in com_detalhe
    ]
    meio = len(restantes) // 2
    partes = [
        "No jogo agora: " + ", ".join(chegando),
        "pararam: " + ", ".join(restantes[:meio]),
        "sem pedido ainda: " + ", ".join(restantes[meio:]),
    ]
    return " · ".join(partes) + "."


def _mascara_e_xbox(state_global: dict[str, Any]) -> bool:
    """True quando o gamepad virtual está com a máscara de Xbox 360.

    Lê `gamepad_emulation.flavor`, e só afirma no valor EXATO "xbox" — a
    mesma regra do `home_actions.texto_do_custo_da_mascara`, pelo mesmo
    motivo: valor ausente ou desconhecido não autoriza aviso nenhum.
    """
    gamepad = state_global.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return False
    return gamepad.get("flavor") == "xbox"


def gyro_do_inputs(inputs: Any) -> tuple[float, float, float] | None:
    """``(x, y, z)`` em graus/s do bloco ``inputs.gyro``; None = sem sensor.

    S2 — o campo é OPCIONAL no payload: daemon antigo (ou controle sem node
    de "Motion Sensors") simplesmente não o manda, e ``None`` faz o módulo
    inteiro sumir do card. Devolver ``(0, 0, 0)`` seria pior que não
    mostrar nada: três barras paradas no centro dizem "o controle está em
    repouso", e não "eu não sei".
    """
    if not isinstance(inputs, dict):
        return None
    bloco = inputs.get("gyro")
    if not isinstance(bloco, dict):
        return None
    try:
        return (
            float(bloco["x"]),
            float(bloco["y"]),
            float(bloco["z"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def touchpad_do_inputs(inputs: Any) -> tuple[bool, float, float] | None:
    """``(tocando, fx, fy)`` do bloco ``inputs.touchpad``; None = sem sensor.

    ``fx``/``fy`` já normalizados 0..1 pelos limites que o PRÓPRIO payload
    declara (``width``/``height``) — ver `posicao_normalizada`.
    """
    if not isinstance(inputs, dict):
        return None
    bloco = inputs.get("touchpad")
    if not isinstance(bloco, dict):
        return None
    try:
        fx, fy = posicao_normalizada(
            int(bloco["x"]),
            int(bloco["y"]),
            int(bloco.get("width", 1920)),
            int(bloco.get("height", 1080)),
        )
    except (KeyError, TypeError, ValueError):
        return None
    return (bool(bloco.get("touching")), fx, fy)


def speaker_do_entry(entry: Any) -> tuple[int, bool | None] | None:
    """``(volume 0-255, muted)`` do alto-falante; ``None`` = sem dado.

    A chave ``speaker`` é OPCIONAL e pode chegar no ``entry`` do controle ou
    dentro de ``inputs`` — o card aceita as duas posições porque quem publica
    é o daemon, e o widget não pode quebrar por causa de onde o dado mora.
    Ausente nos dois lugares, o módulo inteiro SOME: a mesma regra do
    giroscópio (uma barra em zero diria "o volume está no mínimo", e o que
    queremos dizer é "eu não sei").

    ``muted`` fica ``None`` quando o payload traz volume mas não traz mute —
    o rótulo mostra a porcentagem sem afirmar que o som está saindo.
    """
    bloco: Any = None
    if isinstance(entry, dict):
        bloco = entry.get("speaker")
        if not isinstance(bloco, dict):
            inputs = entry.get("inputs")
            bloco = inputs.get("speaker") if isinstance(inputs, dict) else None
    if not isinstance(bloco, dict):
        return None
    volume = bloco.get("volume")
    if isinstance(volume, bool) or not isinstance(volume, (int, float)):
        return None
    muted = bloco.get("muted")
    return (
        max(0, min(255, round(volume))),
        muted if isinstance(muted, bool) else None,
    )


class AcaoMic(NamedTuple):
    """O que o botão do microfone diz e o que ele manda quando clicado.

    ``valor`` é o argumento de ``ipc_bridge.mic_set``: ``True`` muta,
    ``False`` desmuta e ``None`` DEVOLVE a posse do registrador ao
    `hid-playstation` (o botão físico do controle volta a mandar). Os três
    são pedidos explícitos e diferentes — ``False`` não é "não mexer".
    """

    rotulo: str
    valor: bool | None
    sensivel: bool
    dica: str


def acao_mic(entry: Any) -> AcaoMic:
    """Estado do botão de microfone a partir de ``entry['audio']``.

    MIC-USB-01, entrega 2 — a CAMADA 3 do mudo, a única que a janela alcança.
    Duas chaves, publicadas pelo daemon em ``audio`` e que respondem coisas
    diferentes (``daemon/ipc_handlers._merge_audio``):

    * ``mic_mudo`` — o que o firmware DECLARA agora, lido do byte de estado
      que vem em todo report de INPUT. Existe no cabo e no Bluetooth, e não
      depende de PipeWire nenhum: é por isso que o botão funciona mesmo com
      o medidor em "sem sinal", que é o normal por Bluetooth.
    * ``mic_mudo_desejado`` — QUEM MANDA. ``None`` = a posse é do
      `hid-playstation` e o botão físico alterna o mudo; ``True``/``False`` =
      nós estamos afirmando esse valor em todo report, e o botão físico
      deixou de valer enquanto durar.

    O botão é UM só e o rótulo diz o que o clique faz, sempre. As três ações
    formam um ciclo que passa por todos os estados, inclusive a devolução da
    posse — sem ela, o primeiro clique tiraria o botão físico do controle da
    mantenedora para sempre, que é o tipo de sequestro silencioso que esta
    sprint foi fechar:

    ==========================  ==================  ==============
    estado                      rótulo              manda
    ==========================  ==================  ==============
    firmware mudo               Ativar              ``False``
    ativo, posse nossa          Liberar             ``None``
    ativo, posse do kernel      Silenciar           ``True``
    sem leitura de ``audio``    sem dado            (insensível)
    ==========================  ==================  ==============

    Sem a chave ``audio`` o botão fica INSENSÍVEL em vez de sumir: sumir é
    indistinguível de "este controle não tem microfone" (MIC-PRESENTE-01), e
    mandar um pedido sem saber o estado atual seria chutar qual é o oposto.
    """
    audio = entry.get("audio") if isinstance(entry, dict) else None
    if not isinstance(audio, dict):
        return AcaoMic(TEXTO_BOTAO_MIC_SEM_LEITURA, None, False, DICA_MIC_SEM_LEITURA)
    mudo = audio.get("mic_mudo")
    if not isinstance(mudo, bool):
        return AcaoMic(TEXTO_BOTAO_MIC_SEM_LEITURA, None, False, DICA_MIC_SEM_LEITURA)
    if mudo:
        return AcaoMic(TEXTO_BOTAO_MIC_ATIVAR, False, True, DICA_MIC_ATIVAR)
    if isinstance(audio.get("mic_mudo_desejado"), bool):
        return AcaoMic(TEXTO_BOTAO_MIC_DEVOLVER, None, True, DICA_MIC_DEVOLVER)
    return AcaoMic(TEXTO_BOTAO_MIC_SILENCIAR, True, True, DICA_MIC_SILENCIAR)


class AcaoSpeaker(NamedTuple):
    """O que um botão do alto-falante diz e o que ele manda quando clicado.

    ``muted`` é o argumento homônimo de ``ipc_bridge.speaker_set`` (``None`` =
    não mexer no mudo) e ``release`` pede a DEVOLUÇÃO da posse. Nenhum dos dois
    carrega volume: volume só sai do controle deslizante, e sempre explícito.
    """

    rotulo: str
    muted: bool | None
    release: bool
    sensivel: bool
    dica: str


def acao_speaker_mudo(entry: Any) -> AcaoSpeaker:
    """Estado do botão de MUDO do alto-falante (SOM-02, entrega 2).

    A tabela, e cada linha vem de medição:

    ==============================  ==========  ===================
    estado                          rótulo      manda
    ==============================  ==========  ===================
    sem volume conhecido            sem dado    (insensível)
    tocando, posse nossa            Silenciar   ``muted=True``
    mudo por nossa ordem            Ativar      ``muted=False``
    ==============================  ==========  ===================

    **A primeira linha é INSENSÍVEL, e isso é a entrega.** A chave ``speaker``
    só existe depois de um ``speaker.set`` nosso com volume; antes dela, um
    ``muted=True`` faria o backend assumir a posse com preferência ZERO, e o
    ``muted=False`` seguinte "restauraria" essa preferência — o par tranca o
    alto-falante em ``{'volume': 0, 'muted': True}`` e o próprio botão não tem
    como soltá-lo (armadilha 2 da SOM-02, executada contra o backend real).

    O botão fica insensível em vez de sumir, pela mesma regra do microfone:
    sumir muda a largura dos vizinhos e é indistinguível de "este controle não
    tem alto-falante" (MIC-PRESENTE-01).
    """
    dados = speaker_do_entry(entry)
    if dados is None:
        return AcaoSpeaker(
            TEXTO_BOTAO_SPEAKER_SEM_DADO, None, False, False, DICA_SPEAKER_SEM_DADO
        )
    _volume, muted = dados
    if muted:
        return AcaoSpeaker(
            TEXTO_BOTAO_SPEAKER_ATIVAR, False, False, True, DICA_SPEAKER_ATIVAR
        )
    return AcaoSpeaker(
        TEXTO_BOTAO_SPEAKER_SILENCIAR, True, False, True, DICA_SPEAKER_SILENCIAR
    )


def acao_speaker_devolucao(entry: Any) -> AcaoSpeaker:
    """Estado do botão de DEVOLUÇÃO da posse (SOM-02, entrega 3).

    Sensível exatamente quando há posse — que é o mesmo que dizer "quando a
    chave ``speaker`` existe", porque o daemon só a publica enquanto o volume
    for nosso. Sem posse não há o que devolver, e mandar ``release`` ali seria
    pedir ao daemon que soltasse um byte que ele nunca tomou.

    O rótulo não muda de estado: ele já diz o que o clique faz. O que muda é a
    dica, e ela é HONESTA sobre o limite — devolver para de mandar o volume, e
    o firmware fica com o ÚLTIMO valor que mandamos. Não existe leitura, logo
    não existe restauração: prometer que o volume anterior volta seria a mesma
    família de mentira que a SOM-01 recusou ao não publicar ``0 %``.
    """
    if speaker_do_entry(entry) is None:
        return AcaoSpeaker(
            TEXTO_BOTAO_SPEAKER_DEVOLVER,
            None,
            False,
            False,
            DICA_SPEAKER_DEVOLVER_SEM_POSSE,
        )
    return AcaoSpeaker(
        TEXTO_BOTAO_SPEAKER_DEVOLVER, None, True, True, DICA_SPEAKER_DEVOLVER
    )


def saida_muda_do_entry(entry: Any, mic: Any = None) -> bool | None:
    """A CAMADA 1 (o sink do PipeWire) está muda? ``None`` = não dá para saber.

    SENSOR-VIVO-01/E5 e SOM-02/E5, item 4 — são a mesma verdade vista dos dois
    lados. Com o sink do controle mudo no PipeWire, mover o volume do
    registrador HID (a camada 2, a única que a janela alcança nos dois
    transportes) não produz som nenhum: o bloco ficaria dizendo uma
    porcentagem enquanto nada sai.

    Duas posições aceitas, nesta ordem, e nenhuma delas inventada aqui:

    1. o PAYLOAD do daemon, em ``speaker.saida_muda`` ou ``audio.saida_muda`` —
       é onde a leitura mora quando quem lê o PipeWire é o daemon;
    2. a leitura do microfone da própria janela (``LeituraMic.saida_muda``), lida
       por ``getattr`` defensivo — é onde ela mora se quem passar a ler o sink
       for o ``app/mic_monitor.py``, que já é o leitor de PipeWire desta
       interface e já roda fora da thread GTK.

    **Hoje nenhuma das duas existe** (medido em 01/08/2026: o daemon publica
    ``audio`` e ``speaker`` sem nenhuma chave de camada 1, e o ``MicMonitor`` lê
    SOURCES, não sinks). A função devolve ``None`` e o selo não aparece — que é
    o comportamento correto para "não há como saber", e não um placeholder:
    ela é o ponto de encaixe, e o dia em que qualquer um dos dois lados
    publicar a leitura, o selo acende sem tocar no card.

    Só ``True`` acende o selo. ``False`` (a saída está aberta) e ``None`` (não
    sabemos) mostram a mesma coisa — nada —, porque um selo "saída viva" seria
    ruído em cima do que a barra já diz.
    """
    inputs = entry.get("inputs") if isinstance(entry, dict) else None
    for dono in (entry, inputs):
        if not isinstance(dono, dict):
            continue
        for bloco_nome in ("speaker", "audio"):
            bloco = dono.get(bloco_nome)
            if isinstance(bloco, dict):
                valor = bloco.get("saida_muda")
                if isinstance(valor, bool):
                    return valor
    valor = getattr(mic, "saida_muda", None)
    return valor if isinstance(valor, bool) else None


def uniq_do_entry(entry: Any) -> str | None:
    """O endereço DESTE controle, ou ``None`` — a regra, num lugar só.

    GUARDA-SEM-ENDEREÇO-01. A regra estava escrita duas vezes com as mesmas
    palavras (no ``update`` do widget e no do stub), e uma terceira cópia
    nasceria com a guarda do som. Uma regra de identidade com três donos é
    como as duas afirmações se afastam sem ninguém perceber.

    ``""`` e ``"   "`` valem ``None`` de propósito: um endereço em branco
    viajaria no IPC como "sem alvo" e o daemon cairia no primário — que é
    exatamente o defeito que a guarda existe para impedir.
    """
    uniq = entry.get("uniq") if isinstance(entry, dict) else None
    if isinstance(uniq, str) and uniq.strip():
        return uniq
    return None


def audio_sem_endereco(entry: Any) -> bool:
    """O bloco de som deste card tem de ficar DESLIGADO? (função pura)

    GUARDA-SEM-ENDEREÇO-01. É a pergunta inteira: sem endereço, `mic.set`,
    `speaker.set` e a ponte por rádio caem no controle PRIMÁRIO, e o card
    aplicaria no controle de outra pessoa mostrando o título deste.
    """
    return uniq_do_entry(entry) is None


def accent_do_card(entry: dict[str, Any], state_global: dict[str, Any]) -> RGB:
    """Cor AJUSTADA dos traços do card (contraste mínimo garantido).

    Base = cor da lightbar quando conhecida (via :func:`rotulo_lightbar`);
    sem cor conhecida, o neutro ``ACCENT_NEUTRO`` — sempre passado por
    ``ensure_min_contrast`` (o neutro cru rende ~2.6:1, ilegível de traço).
    """
    _rotulo, base = rotulo_lightbar(entry, state_global)
    return ensure_min_contrast(base if base is not None else ACCENT_NEUTRO)


# ---------------------------------------------------------------------------
# Resolução condicional de GTK (padrão da casa: real + stub)
# ---------------------------------------------------------------------------

try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk, Pango

    from hefesto_dualsense4unix.app.widgets.segmented_selector import (
        SegmentedSelector,
    )

    # Com um stub parcial de gi (testes antigos sem display), o import acima
    # passa mas faltam classes — o card cai no stub em vez de explodir.
    _GTK_DISPONIVEL = all(
        hasattr(Gtk, attr)
        for attr in (
            "Frame",
            "Box",
            "Button",
            "Grid",
            "Label",
            "ProgressBar",
            "DrawingArea",
            "Align",
            "Orientation",
        )
    )
except (ImportError, ValueError):
    _GTK_DISPONIVEL = False


if _GTK_DISPONIVEL:

    class ControllerCard(Gtk.Frame):  # type: ignore[misc]
        """Card de UM controle físico na aba Status.

        Uso (a mixin de status monta e distribui — STATUS-02)::

            card = ControllerCard(compact=True)   # compact = 2+ cards
            card.update(entry, state_full)        # diff interno por seção
            card.reset_inputs()                   # IPC falhou → mostra "—"

        ``entry`` é uma entrada de ``state_full.controllers`` (contrato em
        ``daemon/ipc_handlers._enrich_controllers_per_controller``);
        ``state_full`` inteiro entra como contexto global (``native_mode``).
        """

        def __init__(
            self,
            *,
            compact: bool = False,
            mostrar_estado_global: bool | None = None,
        ) -> None:
            super().__init__()
            self._compact = compact
            # EMPILHA-02 (02/08/2026) — o `compact` controlava DUAS coisas
            # misturadas, e o empilhamento expôs isso na tela dela:
            #
            #   1. o TAMANHO dos desenhos (sticks de 90 vs 120px, glifos
            #      menores) — que depende da LARGURA que o card recebe;
            #   2. a presença do par global "Perfil ativo / Hefesto" — que
            #      depende de haver OUTRO lugar mostrando os mesmos fatos.
            #
            # Enquanto os cards ficavam lado a lado, as duas andavam juntas por
            # acidente: meia largura E frame Estado visível. Empilhados, cada
            # card recebe a largura INTEIRA e continuava desenhando para meia —
            # o conteúdo espremido à esquerda com um vazio à direita, que foi
            # exatamente o que ela apontou no print de 02/08.
            #
            # `None` mantém o casamento antigo (o par aparece quando o card não
            # é compacto), que é o que os testes e o card avulso esperam.
            self._mostrar_estado_global = (
                (not compact)
                if mostrar_estado_global is None
                else mostrar_estado_global
            )
            self._espaco = (
                _ESPACO_FAIXA_COMPACTO if compact else _ESPACO_FAIXA_UNICO
            )
            # Caches de diff (sentinela onde None é valor válido).
            self._last_titulo: str | None = None
            self._last_dica_titulo: str | None = None
            self._last_battery: Any = _SENTINELA
            self._last_lightbar: Any = _SENTINELA
            self._last_degradacao: Any = _SENTINELA
            self._last_motion: Any = _SENTINELA
            self._last_verdade: Any = _SENTINELA
            self._accent: RGB | None = None
            self._accent_hex: str = rgb_para_hex(
                ensure_min_contrast(ACCENT_NEUTRO)
            )
            self._swatch_rgb: RGB | None = None
            # None = nunca pintado (força o primeiro render de qualquer view).
            self._sem_leitor: bool | None = None
            self._last_l2: int | None = None
            self._last_r2: int | None = None
            self._last_lx: int | None = None
            self._last_ly: int | None = None
            self._last_rx: int | None = None
            self._last_ry: int | None = None
            self._last_buttons: frozenset[str] | None = None
            self._last_l2_lit: bool | None = None
            self._last_r2_lit: bool | None = None
            self._l3_pressed = False
            self._r3_pressed = False
            self._glyphs: dict[str, ButtonGlyph] = {}
            # S2 — caches de diff dos módulos de sensor.
            self._last_gyro: Any = _SENTINELA
            self._last_touch: Any = _SENTINELA
            self._last_mic: Any = _SENTINELA
            self._last_speaker: Any = _SENTINELA
            # MIC-USB-01: o MAC deste controle, para o `mic.set` ir SÓ nele —
            # sem ele o daemon aplicaria no primário, e com quatro controles
            # isso mutaria o microfone de outra pessoa.
            self._uniq: str | None = None
            #: GUARDA-SEM-ENDEREÇO-01: o último estado da guarda do som.
            #: `None` = nunca aplicada, e é o que força a primeira pintura —
            #: um `False` inicial faria o card nascer com a guarda "já
            #: devolvida" e pularia a devolução do primeiro `update`.
            self._audio_sem_endereco: bool | None = None
            self._mic_acao: AcaoMic | None = None
            # MIC-BT-01 — o card NÃO segura mais ponte de mic por BT nenhuma.
            # Ela subia daqui pelo interruptor "Pelo rádio", que saiu em 16/08
            # (o porquê e o caminho de volta estão no cabeçalho deste arquivo).
            # Sem o interruptor não há estado de ponte a guardar, e é isso que
            # tira o processo da JANELA de dentro da disputa pelo hidraw.
            # SOM-02 — o estado do COMANDO do alto-falante. Nenhum deles é
            # leitura: `_speaker_volume_enviado` existe só para a guarda
            # anti-rajada (o mesmo número duas vezes), e jamais é pintado.
            self._speaker_acao_mudo: AcaoSpeaker | None = None
            self._speaker_acao_devolucao: AcaoSpeaker | None = None
            self._speaker_arrastando = False
            #: Guarda do POPULATE do seletor de canal — o mesmo desenho do
            #: `_speaker_pintando` da escala: pintar o estado vindo do daemon
            #: não pode disparar o gesto dela de volta ao daemon.
            self._speaker_canal_pintando = False
            #: SOM-CANAL-01: a aba injeta aqui quem executa a camada 1.
            self._pedir_rota_do_sistema: Any = None
            #: SOM-02/E4: quem GUARDA o rascunho do perfil em edição (a
            #: `HefestoApp`), injetado pela aba — o card não o descobre
            #: sozinho, pela mesma razão do `definir_sink_de_saida`. `None` =
            #: card avulso (teste, ou antes de a janela terminar de nascer):
            #: o gesto continua indo ao daemon e simplesmente não é anotado.
            self._dono_do_rascunho: Any = None
            #: O último `(volume, muted)` LIDO do daemon — a preferência que
            #: ele publica, não o que a tela desenhou. Os gestos SEM número (o
            #: mudo e o canal) precisam de um volume para registrar, e o do
            #: controle deslizante não volta igual fora da faixa útil do
            #: registrador: 200 desenha 100 % e a volta pela tela devolve 102,
            #: a saturação que ela mediu em 01/08. Registrar o número da tela
            #: baixaria o volume guardado dela sem ninguém ter pedido.
            self._speaker_lido: tuple[int, bool | None] | None = None
            self._speaker_pintando = False
            self._speaker_repouso_id: int | None = None
            self._speaker_volume_enviado: int | None = None
            # SOM-04 — o som de confirmação. O DualSense não devolve o volume
            # (SOM-02, o preço da camada 2): depois de um gesto, NADA na tela
            # pode confirmar que ele valeu, porque o número exibido é o que nós
            # mandamos. O som É a leitura que falta.
            #
            # `_speaker_sink` é o sink de SAÍDA deste controle, posto de fora
            # por `definir_sink_de_saida`. "" = não dá para saber, e desde
            # 15/08/2026 isso quer dizer sobretudo UMA coisa: o controle está
            # no RÁDIO, onde o DualSense não publica placa de som nenhuma (a
            # placa segue o transporte). No cabo o `escolher_sink` casa placa e
            # controle pelo dispositivo USB em que os dois penduram, e devolve
            # o sink certo mesmo com quatro controles. Com "" não se toca:
            # medido nesta bancada,
            # `paplay --device=` vazio é ACEITO, sai com zero e cai no sink
            # PADRÃO, que na máquina dela é o HDMI.
            self._speaker_sink = ""
            # O motivo pelo qual a última confirmação NÃO saiu. Nunca é leitura
            # de sensor: é recado, e some no primeiro som que sair.
            self._speaker_recado_do_som = ""
            # A camada 1 (o sink do PipeWire) da última releitura, guardada
            # porque o selo do bloco passou a ter DOIS informantes e o
            # `_aplicar_selo_do_som` precisa dos dois para decidir a prioridade.
            self._speaker_saida_muda: bool | None = None
            # SOM-ACORDADO-01: o canal deste controle está acordado ou
            # dormindo, e a regra do WirePlumber que impede o sono está no
            # lugar? Os dois entram de FORA (`definir_estado_do_canal`), pela
            # `status_actions`, que já lê o PipeWire numa worker a 0,5 Hz —
            # o card continua sem um leitor próprio de PipeWire.
            self._speaker_canal_estado = ""
            self._speaker_regra_do_sono: bool | None = None
            self._montar_ui()
            # Um repouso pendente segura uma referência ao card e dispararia
            # sobre um widget já destruído quando a aba recria os cards
            # (`_rebuild_status_cards` destrói e refaz a cada troca de
            # conjunto de controles).
            self.connect("destroy", lambda _w: self._cancelar_repouso_do_volume())
            # O MESMO gancho para o repouso do microfone (MIC-VOLUME-01). Ele
            # nasceu sem, na leva do controle deslizante, e o irmão acima é
            # justamente a prova de que a falta importa: são dois `timeout_add`
            # de um disparo só, e os dois seguram uma referência ao card.
            self.connect("destroy", lambda _w: self._cancelar_repouso_do_mic())

        # ------------------------------------------------------------------
        # API pública
        # ------------------------------------------------------------------

        def update(
            self,
            entry: dict[str, Any],
            state_global: dict[str, Any],
            mic: Any = None,
        ) -> None:
            """Atualiza o card a partir de ``controllers[i]`` (diff interno).

            ``mic`` é a `LeituraMic` do `MicMonitor` da GUI (nível + mute) —
            opcional porque o microfone é o único sensor que NÃO vem pelo
            IPC: quem captura é a própria interface, só enquanto a aba Status
            está visível. ``None`` = sem microfone atribuível a este controle,
            e o módulo some.
            """
            self._uniq = uniq_do_entry(entry)
            self._update_titulo(entry, state_global)
            self._update_bateria(entry)
            self._update_lightbar(entry, state_global)
            self._update_degradacao(entry)
            self._update_motion(entry, state_global)
            self._update_verdade(entry, state_global)
            self._update_inputs(entry.get("inputs"))
            self._update_gyro(entry.get("inputs"))
            self._update_touchpad(entry.get("inputs"))
            self._update_mic(mic, str(entry.get("transport") or ""))
            self._update_mic_botao(entry)
            self._update_speaker(entry, mic)
            # GUARDA-SEM-ENDEREÇO-01: por ÚLTIMO, e não é ordem de gosto. Os
            # três `_update_` acima acabam de decidir a sensibilidade das peças
            # de som a partir do que o daemon publicou; a guarda é a palavra
            # final sobre elas, porque nenhum daqueles estados sabe que o card
            # não tem para onde mandar o gesto.
            self._update_guarda_de_audio()

        def reset_inputs(self) -> None:
            """IPC sem resposta: mostra "—" — nunca o último valor como vivo."""
            self._mostrar_sem_leitor()

        # ------------------------------------------------------------------
        # Montagem da UI (uma vez, no __init__)
        # ------------------------------------------------------------------

        def do_size_allocate(self, allocation: Any) -> None:
            """Teto ELÁSTICO do card de um controle (SOM-01, pedido 3).

            O GTK3 não tem largura máxima: `set_size_request` declara o
            MÍNIMO, e `halign=CENTER` com um mínimo declarado trava o widget
            naquele número exato — era assim que o card ficava em 960px com a
            janela em 1920 e sobravam ~950px de margem morta.

            Aqui o card aceita toda a largura que a aba der até
            :data:`LARGURA_CARD_ELASTICA` e devolve o excedente como margem,
            centrando-se. Abaixo do teto ele cresce junto com a janela, que é
            o pedido; acima dele para de crescer, que é o que impede a sobra
            de voltar a virar buraco entre os blocos.

            A alocação recebida NÃO é mutada: ela é a variável local do
            `gtk_widget_size_allocate` do pai, usada depois para o clip. O
            corte vai numa CÓPIA (`.copy()` do próprio retângulo, que já é um
            `Gdk.Rectangle` — sem import novo neste módulo).
            """
            # EMPILHA-01: o teto vale para os DOIS modos desde que os cards
            # passaram a ser empilhados numa coluna só. Antes o compacto
            # dividia a largura com o vizinho e nunca chegava perto do teto;
            # com uma coluna ele recebe a janela inteira, e sem o corte um
            # card de dois controles esticaria por 1900px com ~900 de
            # conteúdo — o buraco que o teto do card único veio curar.
            if allocation.width > LARGURA_CARD_ELASTICA:
                sobra = allocation.width - LARGURA_CARD_ELASTICA
                cortado = allocation.copy()
                cortado.x = allocation.x + sobra // 2
                cortado.width = LARGURA_CARD_ELASTICA
                allocation = cortado
            Gtk.Frame.do_size_allocate(self, allocation)

        def _montar_ui(self) -> None:
            if not self._compact:
                # Card de UM controle: PISO de largura, e teto elástico no
                # `do_size_allocate`. O `halign` fica em FILL de propósito —
                # com CENTER o card recebe exatamente o mínimo pedido e para
                # de crescer, que é o defeito que a SOM-01 veio curar.
                self.set_size_request(LARGURA_CARD_UNICO, -1)
                self.set_halign(Gtk.Align.FILL)
                self.set_hexpand(True)
            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            swatch = Gtk.DrawingArea()
            swatch.set_size_request(14, 14)
            swatch.set_valign(Gtk.Align.CENTER)
            swatch.connect("draw", self._on_draw_swatch)
            self._swatch = swatch
            header.pack_start(swatch, False, False, 0)
            titulo = Gtk.Label(label="Controle")
            titulo.set_xalign(0.0)
            self._title_label = titulo
            header.pack_start(titulo, False, False, 0)
            header.show_all()
            self.set_label_widget(header)

            corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            corpo.set_margin_top(10)
            corpo.set_margin_bottom(10)
            corpo.set_margin_start(12)
            corpo.set_margin_end(12)
            corpo.get_style_context().add_class("hefesto-dualsense4unix-card")
            self.add(corpo)
            self._montar_estado_global(corpo)

            # Bateria DESTE controle (a barra do frame Estado só fala pelo
            # primário e some com 2+ controles — cada card tem a sua).
            #
            # STATUS-SIMETRIA-02, entrega 6 — a bateria aparecia DUAS vezes na
            # tela dela: no frame "Estado" e no card, com o mesmo número. As
            # duas regras já eram complementares e ninguém as tinha juntado:
            # a linha do frame Estado só fica visível com 0 ou 1 controle
            # (`_set_battery_row_visible`), e o card só é compacto com 2+. A
            # linha do CARD é a que sai no caso de um controle só — a do frame
            # Estado fica, porque é a que responde também quando não há
            # controle nenhum, e o card nem existe.
            # CARD-ÚNICO-01, entrega 1 — a bateria do card único DEIXOU de se
            # esconder, porque o frame "Estado" que a mostrava não existe mais
            # na tela dela. A regra antiga ("aparece uma vez só") continua
            # inteira; o que inverteu foi qual das duas sai. Ver
            # `_montar_estado_global`, logo abaixo, para o par que a acompanha.
            linha_bateria = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=12
            )
            cap_bateria = Gtk.Label(label="Bateria:")
            cap_bateria.set_xalign(1.0)
            linha_bateria.pack_start(cap_bateria, False, False, 0)
            bateria = Gtk.ProgressBar()
            self._battery_bar = bateria
            # `show-text` DESLIGADO e o número num rótulo ao lado, nos DOIS
            # modos. O GtkProgressBar desenha o próprio texto CENTRADO, e numa
            # barra larga o "85 %" fica a centenas de pixels de cada borda — é
            # o defeito que ela apontou nas barras de L2/R2, e o mesmo motivo
            # pelo qual a barra do frame Estado já tinha `show-text=False`.
            #
            # EMPILHA-01 (02/08): o card COMPACTO passou por aqui também. Ele
            # ficava de fora com a justificativa de que "a barra é estreita e o
            # texto centrado cabe" — o que era verdade enquanto dois cards
            # dividiam a largura em duas colunas. Empilhados numa coluna só,
            # cada card recebe a janela inteira, a barra ficou larga e o número
            # voltou a flutuar no vazio. O desenho é um só agora.
            #
            # O `set_text` continua sendo chamado por `_update_bateria`: ele é
            # o dono do valor e é o que os testes leem.
            bateria.set_show_text(False)
            bateria.set_text("— %")
            bateria.set_valign(Gtk.Align.CENTER)
            bateria.set_size_request(LARGURA_BARRA_BATERIA_CARD, -1)
            linha_bateria.pack_start(bateria, False, False, 0)
            pct = Gtk.Label(label="— %")
            pct.set_xalign(0.0)
            self._battery_pct_label = pct
            linha_bateria.pack_start(pct, False, False, 0)
            self._battery_row = linha_bateria
            if self._compact:
                corpo.pack_start(linha_bateria, False, False, 0)

            # Rótulo do estado da lightbar (apagada/desconhecida/nativo).
            rotulo = Gtk.Label()
            rotulo.set_xalign(0.0)
            rotulo.get_style_context().add_class("dim-label")
            rotulo.set_no_show_all(True)
            rotulo.hide()
            self._lightbar_label = rotulo
            corpo.pack_start(rotulo, False, False, 0)

            # Badge de degradação do vpad (BT-03) — inline, nunca popup.
            badge = Gtk.Label()
            badge.set_xalign(0.0)
            badge.set_line_wrap(True)
            badge.get_style_context().add_class(
                "hefesto-dualsense4unix-status-warn"
            )
            badge.set_no_show_all(True)
            badge.hide()
            self._degradacao_badge = badge
            corpo.pack_start(badge, False, False, 0)

            # GUARDA-SEM-ENDEREÇO-01 — o aviso VISÍVEL do som desligado, ao
            # lado do badge de degradação e com o mesmo desenho: nasce apagado
            # com `no_show_all`, então o `show_all()` do card não o revela e um
            # filho escondido não entra no pedido de tamanho de um `GtkBox`.
            # No caso normal ele custa ZERO.
            #
            # Ele fica no CORPO, e não na coluna do som que explica, e isso é
            # medido: na coluna (194px no card de um controle, 94 no compacto)
            # a frase quebra em três linhas e custa +42px de altura no card
            # único e +72 no compacto — contra uma faixa que já pede 463 dos
            # 467 que a aba dá. No corpo, que tem a largura inteira do card,
            # ela cabe em UMA linha: **+23px de altura e ZERO de largura**,
            # e só no card que está sem endereço. Quem amarra o aviso ao bloco
            # certo é a dica das duas molduras, que não custa pixel nenhum.
            aviso = Gtk.Label(label=TEXTO_AUDIO_SEM_ENDERECO)
            aviso.set_xalign(0.0)
            aviso.set_line_wrap(True)
            aviso.get_style_context().add_class(
                "hefesto-dualsense4unix-status-warn"
            )
            aviso.set_no_show_all(True)
            aviso.hide()
            self._audio_aviso = aviso
            corpo.pack_start(aviso, False, False, 0)

            # GYRO-03: linha discreta do giroscópio espelhado — inline
            # (dim-label), nunca popup (veto cosmic-comp). Só aparece com o
            # espelho de motion ATIVO no vpad deste controle.
            motion = Gtk.Label()
            motion.set_xalign(0.0)
            motion.get_style_context().add_class("dim-label")
            motion.set_no_show_all(True)
            motion.hide()
            self._motion_label = motion
            if self._compact:
                corpo.pack_start(motion, False, False, 0)
            else:
                # CARD-ÚNICO-01, anotação 1 do print dela: *"a bateria fica ao
                # lado do hertz do giroscópio até o final"*.
                #
                # **Quem mora aqui é a linha da VERDADE, e não o rótulo do
                # giroscópio** — e isso não contraria o pedido dela, cumpre-o:
                # desde a PAINEL-DA-VERDADE-01 é a linha da verdade que traz o
                # hertz do giroscópio ("No jogo agora: giroscópio (~194 Hz),
                # vibração, luz"). Com os dois na tela, o card dizia a mesma
                # coisa duas vezes, uma embaixo da outra — a duplicação que
                # esta aba já corrigiu na bateria.
                #
                # O `_motion_label` continua existindo e continua sendo o dono
                # do texto no card COMPACTO, onde não há linha da verdade.
                #
                # O slot fica SEMPRE visível e é ele quem expande; quem se
                # esconde é o rótulo dentro dele. Um widget oculto não ocupa
                # espaço, e sem o slot a bateria saltaria da direita para a
                # esquerda no instante em que a linha ficasse sem o que
                # afirmar. É o mesmo mecanismo do `_gyro_slot` da linha de
                # cima, e pelo mesmo motivo.
                faixa = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=12
                )
                slot_motion = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                slot_motion.set_valign(Gtk.Align.CENTER)
                slot_motion.pack_start(self._verdade_label, False, False, 0)
                faixa.pack_start(slot_motion, True, True, 0)
                faixa.pack_start(linha_bateria, False, False, 0)
                corpo.pack_start(faixa, False, False, 0)
                self._faixa_gyro_bateria = faixa
                # As duas linhas novas são as duas PRIMEIRAS do corpo (o
                # desenho que ela aprovou). O `lightbar_label` e o badge de
                # degradação foram empacotados antes por ordem de código e
                # nascem ocultos — sem esta reordenação, no dia em que um
                # deles acendesse ele apareceria ENTRE as duas linhas.
                corpo.reorder_child(faixa, 1)

            # "—": sem leitor de inputs para este controle agora.
            sem_leitor = Gtk.Label(label="—")
            sem_leitor.get_style_context().add_class("dim-label")
            sem_leitor.set_no_show_all(True)
            sem_leitor.hide()
            self._sem_leitor_label = sem_leitor
            corpo.pack_start(sem_leitor, False, False, 0)

            area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            self._inputs_area = area
            corpo.pack_start(area, False, False, 0)
            # LEGIBILIDADE-01/R4 — o card ocupa DUAS linhas. Eram três, com os
            # analógicos numa faixa só deles:
            #
            #   1) [ L2/R2 ............. | Giroscópio ............. ]
            #   2) [ Touchpad  Microfone | L3 | R3 | botões (4x4) ]
            #      [ Lightbar Alto-fal.  |    |    |              ]
            #
            # O pedido da mantenedora: "os analógicos no Status deveriam ficar
            # ao lado do microfone e lightbar e entre os botões. Eles estão
            # acima." Ela tem razão pelo motivo do desenho e pelo do orçamento:
            # microfone, lightbar, alto-falante, touchpad e analógicos são
            # todos LEITURA DE ESTADO AO VIVO e pertencem à mesma faixa; e a
            # faixa só deles gastava a largura que falta para a fonte crescer.
            area.pack_start(self._montar_gatilhos_e_gyro(), False, False, 0)
            area.pack_start(self._montar_linha_inferior(), False, False, 0)

        def _montar_estado_global(self, corpo: Any) -> None:
            """A linha ``Perfil ativo: <v>    Hefesto: <v>``, no topo do card.

            CARD-ÚNICO-01, entrega 1. Ela é o que sobrou do frame "Estado",
            que ela mandou apagar: *"apaga estado, a bateria fica ao lado do
            hertz do giroscópio até o final e adicionamos as duas linhas"*.

            `Conexão:` e `Transporte:` NÃO vêm junto, e não é economia de
            espaço: cada um já é dito noutro lugar da mesma tela — a conexão
            no cabeçalho ("Conectado Via USB") e o transporte no título deste
            card ("Controle 1 — USB"). Repetir os dois era o frame Estado
            dizendo o que o resto da aba já dizia.

            **Só no card único.** Perfil ativo e daemon são fatos GLOBAIS, não
            deste controle: com dois cards lado a lado eles apareceriam duas
            vezes na tela, e é justamente o defeito que a bateria tinha. Com
            2+ controles quem responde por eles volta a ser o frame Estado —
            a mesma regra da bateria, invertida.

            Caixa horizontal e não `Gtk.Grid`: numa grade, o `hexpand` que
            afasta os dois pares expandiria a COLUNA inteira, e esta casa já
            pagou por isso duas vezes (LARGURA-01/E2 e ESTADO-TRES-LINHAS-01).
            """
            self._perfil_ativo_label = None
            self._daemon_label = None
            self._linha_estado_global = None
            self._verdade_label = None
            if self._compact:
                return

            # A linha da VERDADE é por CONTROLE, e não global — ela diz o que
            # chega ao jogo NAQUELE controle, com o hertz do giroscópio dele.
            # Por isso ela é montada antes do par perfil/daemon, e não depende
            # do `mostrar_estado_global`: com dois controles, cada card tem a
            # sua.
            #
            # `line_wrap` LIGADO com `max_width_chars` e `halign=start`: os
            # três juntos, e não um deles. Medido nesta casa em 01/08 — o
            # `max-width-chars` sozinho limita a largura NATURAL (o que o
            # widget PEDE) e o pai continua livre para alocar mais; um
            # parágrafo de 1869px ficou intacto até o `halign=start` entrar.
            # NAO-DANCA-01: não é uma `Gtk.Label` — é a que RESERVA a altura da
            # maior frase que ela pode receber, para encolher e crescer não
            # mexerem em nada abaixo. O porquê está na classe.
            verdade = RotuloDeAlturaReservada()
            verdade.set_xalign(0.0)
            verdade.set_halign(Gtk.Align.START)
            verdade.set_line_wrap(True)
            verdade.set_max_width_chars(_VERDADE_MAX_CHARS)
            verdade.get_style_context().add_class("dim-label")
            verdade.set_no_show_all(True)
            verdade.hide()
            self._verdade_label = verdade

            if not self._mostrar_estado_global:
                return
            linha = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=6
            )
            cap_perfil = Gtk.Label(label="Perfil ativo:")
            cap_perfil.set_xalign(1.0)
            linha.pack_start(cap_perfil, False, False, 0)
            perfil = Gtk.Label(label=TEXTO_PERFIL_SEM_DADO)
            perfil.set_xalign(0.0)
            self._perfil_ativo_label = perfil
            linha.pack_start(perfil, False, False, 0)

            # O vão que separa os dois pares mora AQUI, numa caixa vazia que
            # expande — e não num `hexpand` do rótulo de valor. Com o hexpand
            # no valor, o texto do perfil ficaria colado no rótulo e o espaço
            # cresceria DEPOIS dele; com um separador próprio, cada par fica
            # inteiro e a distância entre os dois é o que respira.
            vao = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            linha.pack_start(vao, True, True, 0)

            cap_daemon = Gtk.Label(label="Hefesto:")
            cap_daemon.set_xalign(1.0)
            linha.pack_start(cap_daemon, False, False, 0)
            daemon = Gtk.Label(label=TEXTO_DAEMON_SEM_DADO)
            daemon.set_xalign(0.0)
            self._daemon_label = daemon
            linha.pack_start(daemon, False, False, 0)

            self._linha_estado_global = linha
            corpo.pack_start(linha, False, False, 0)

            # PAINEL-DA-VERDADE-01/E2 — a linha que responde *"vai funcionar
            # na hora de jogar?"*. Ela nasce OCULTA: sem vpad não há o que
            # afirmar, e uma linha vazia reservando altura é pior que nenhuma.
            #
            # `line_wrap` LIGADO com `max_width_chars` e `halign=start`: os
            # três juntos, e não um deles. Medido nesta casa em 01/08 — o
            # `max-width-chars` sozinho limita a largura NATURAL (o que o
            # widget pede) e o pai continua livre para alocar mais; um
            # parágrafo de 1869px ficou intacto até o `halign=start` entrar.
            # A linha da verdade NÃO é empacotada aqui: o lugar dela é a faixa
            # da linha 2, ao lado da bateria, e quem a empacota é o bloco do
            # motion. Criá-la acima é o que permite aquele bloco encontrá-la
            # pronta — a ordem de montagem do corpo é a ordem do desenho.

        def definir_estado_global(self, perfil: str, daemon: str) -> None:
            """Escreve o par ``Perfil ativo``/``Hefesto`` — chamada pela aba.

            Quem calcula os dois textos é a `status_actions`, que já os
            calculava para o frame Estado: os mesmos valores, da mesma
            fonte, no mesmo tique. Este método só os PINTA — nenhuma regra de
            negócio entra aqui, e no card compacto ele é inerte de propósito.
            """
            for rotulo, texto in (
                (self._perfil_ativo_label, perfil),
                (self._daemon_label, daemon),
            ):
                if rotulo is not None and texto and rotulo.get_text() != texto:
                    rotulo.set_text(texto)

        def _montar_gatilhos_e_gyro(self) -> Any:
            """Linha 1: gatilhos à esquerda, giroscópio à direita.

            `Gtk.Grid` homogêneo e NÃO um `Gtk.Box`: o giroscópio nasce oculto
            e só aparece quando há sensor. Num box, os gatilhos tomariam a
            largura toda enquanto o gyro estivesse escondido e encolheriam
            para metade no instante em que ele aparecesse — reflow visível a
            cada troca de controle. O grid guarda a metade direita porque a
            coluna tem um `_gyro_slot` SEMPRE visível; quem se esconde é o
            módulo dentro dele (que é o que os testes observam).
            """
            grid = Gtk.Grid()
            grid.set_column_spacing(self._espaco)
            # ALINHA-DUAS-LINHAS-01: o `column_homogeneous` SAIU, e a razão é
            # que ela mediu de olho o que ele fazia. Homogêneo dá metade do
            # card a cada coluna, e as duas metades da faixa de baixo NÃO são
            # metades iguais — medido na tela dela: a esquerda (touchpad até o
            # analógico direito) tem 698px e a direita (microfone até o último
            # glifo) tem 648. Dividir 50/50 aqui em cima colocava as duas
            # divisórias 25px fora do lugar, e era isso que fazia a linha de
            # cima parecer de outro desenho.
            #
            # Quem manda na largura agora são os `Gtk.SizeGroup` abaixo: cada
            # coluna desta linha pede exatamente o que a metade correspondente
            # da faixa de baixo pede. O `_gyro_slot` continua SEMPRE visível
            # (quem se esconde é o módulo dentro dele), então a coluna não
            # colapsa quando não há giroscópio — que era o motivo de o grid
            # existir em vez de um box.
            gatilhos = self._montar_gatilhos()
            grid.attach(gatilhos, 0, 0, 1, 1)
            slot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            slot.pack_start(self._montar_gyro(), False, False, 0)
            self._gyro_slot = slot
            grid.attach(slot, 1, 0, 1, 1)

            # Os dois grupos que amarram as duas linhas. Eles são criados aqui
            # e recebem o segundo membro em `_montar_linha_inferior`, que roda
            # logo depois (`_montar_ui`) — a ordem não importa para o
            # `SizeGroup`, que só iguala o pedido de quem já está dentro.
            self._grupo_coluna_esquerda = Gtk.SizeGroup(
                mode=Gtk.SizeGroupMode.HORIZONTAL
            )
            self._grupo_coluna_esquerda.add_widget(gatilhos)
            self._grupo_coluna_direita = Gtk.SizeGroup(
                mode=Gtk.SizeGroupMode.HORIZONTAL
            )
            self._grupo_coluna_direita.add_widget(slot)
            return grid

        def largura_da_barra_de_gatilho(self) -> int:
            """Teto da barra de L2/R2 neste card, em px."""
            if self._compact:
                return LARGURA_BARRA_GATILHO_COMPACTO
            return LARGURA_BARRA_GATILHO_UNICO

        def largura_do_giroscopio(self) -> int:
            """Teto do desenho do giroscópio neste card, em px."""
            if self._compact:
                return LARGURA_GYRO_COMPACTO
            return LARGURA_GYRO_UNICO

        def _montar_gatilhos(self) -> Any:
            """As duas barras de gatilho, com TETO de largura.

            STATUS-SIMETRIA-02, defeito 4: com `hexpand` e sem teto, cada
            barra recebia 881px na tela maximizada — para um valor de 0 a 255,
            com o "0 / 255" flutuando no meio dela, longe do "L2" que a nomeia.

            ALINHA-DUAS-LINHAS-01 (01/08) mudou o TETO, não a regra. Aquele
            defeito era barra sem limite nenhum, esticando pelo card inteiro;
            o limite agora é a metade esquerda da faixa de baixo — do touchpad
            ao analógico direito — que é onde ela pediu que a linha terminasse.
            Continua havendo teto, e ele continua sendo bem menor que o card:
            698 dos 1400px medidos na tela dela.

            `LARGURA_BARRA_GATILHO_UNICO` deixa de ser o teto e passa a ser o
            PISO, que é o que `set_size_request` sempre foi no GTK3 — o
            `halign=START` é que o transformava em teto de fato, e é ele que
            sai. Com `FILL` a barra ocupa a coluna que o `SizeGroup` mediu.
            """
            grid = Gtk.Grid()
            grid.set_row_spacing(6)
            grid.set_column_spacing(12)
            grid.set_valign(Gtk.Align.START)
            for linha, nome in enumerate(("L2", "R2")):
                cap = Gtk.Label(label=nome)
                cap.set_xalign(1.0)
                cap.set_width_chars(3)
                grid.attach(cap, 0, linha, 1, 1)
                barra = Gtk.ProgressBar()
                barra.set_show_text(True)
                barra.set_text("0 / 255")
                barra.set_size_request(self.largura_da_barra_de_gatilho(), -1)
                barra.set_halign(Gtk.Align.FILL)
                barra.set_hexpand(True)
                grid.attach(barra, 1, linha, 1, 1)
                if nome == "L2":
                    self._l2_bar = barra
                else:
                    self._r2_bar = barra
            return grid

        @staticmethod
        def _rotulo_secao(texto: str) -> Any:
            """Rótulo pequeno de seção (mesmo peso visual do `dim-label`)."""
            label = Gtk.Label(label=texto)
            label.set_xalign(0.0)
            label.get_style_context().add_class("dim-label")
            return label

        def _bloco(self, titulo: str) -> tuple[Any, Any]:
            """``(bloco, miolo)`` de UM assunto da faixa de leitura.

            STATUS-SIMETRIA-02, defeito 2 — *"o touchpad não tem um espaço
            próprio"*. Touchpad, o retângulo dele, "sem toque", Lightbar, a
            barra de cor e o hex dela eram SEIS elementos empilhados numa
            coluna única, sem nada separando os dois assuntos: lidos de cima
            para baixo, pareciam uma lista só. A moldura é a separação que a
            sprint pede ("cada um com moldura própria ou separação visível,
            como o card do Estado já faz") — o mesmo recurso, um nível abaixo.
            O rótulo vira o RÓTULO DA MOLDURA em vez de mais uma linha dentro
            dela: o bloco ganha borda sem ganhar linha.

            **A moldura só entra no card de UM controle, e o motivo é medido.**
            Ela custa ~50px de largura por coluna (borda, margens e o respiro
            do rótulo). Com 2+ controles os cards vão lado a lado e a largura
            de cada um soma DIRETO no mínimo da janela, sem rolagem horizontal
            para absorver: o orçamento inteiro da aba Status com dois cards é
            de 26px (`test_dois_cards_lado_a_lado_cabem_na_largura_da_janela`,
            1154px para 1180px). Não cabe, e forçar a moldura ali faria a
            janela nascer maior que o projeto — o preço que a mantenedora não
            pediu para pagar. No card único, que é a tela que ela mediu, a
            largura sobra e a moldura entra.
            """
            if self._compact:
                caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                caixa.pack_start(self._rotulo_secao(titulo), False, False, 0)
                return caixa, caixa
            moldura = Gtk.Frame()
            moldura.set_label_widget(self._rotulo_secao(titulo))
            moldura.set_valign(Gtk.Align.START)
            miolo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            miolo.set_margin_top(4)
            miolo.set_margin_bottom(4)
            miolo.set_margin_start(6)
            miolo.set_margin_end(6)
            moldura.add(miolo)
            return moldura, miolo

        @staticmethod
        def _esconder_modulo(widget: Any) -> None:
            """Deixa o módulo pronto para aparecer, mas apagado.

            A ordem importa: `show_all()` ANTES marca os filhos como
            visíveis, e só então `no_show_all` + `hide()` apagam o módulo
            inteiro. Se o `no_show_all` viesse primeiro, o `show_all()` do
            card seria ignorado no subwidget e um `show()` posterior
            revelaria uma caixa vazia — o módulo existiria sem nada dentro.
            """
            widget.show_all()
            widget.set_no_show_all(True)
            widget.hide()

        def _montar_gyro(self) -> Any:
            caixa, miolo = self._bloco("Giroscópio (graus/s)")
            barras = GyroBars()
            # Teto de largura: o número do eixo é desenhado colado na borda
            # DIREITA do widget (`fim_barra + 4`, em sensor_widgets), então a
            # largura do widget É a distância entre o "X" e o "+143.2". Sem
            # teto ela era de 914px na tela maximizada, com os rótulos
            # apertados de um lado e os números do outro. A altura pedida pelo
            # PRÓPRIO widget é preservada: ela deriva da escala de fonte, e
            # trocá-la por -1 faria as três linhas do desenho se sobreporem.
            _largura, altura = barras.get_size_request()
            barras.set_size_request(self.largura_do_giroscopio(), altura)
            # ALINHA-DUAS-LINHAS-01: o desenho e a moldura ESTICAM até a coluna
            # que o `SizeGroup` mediu — do microfone ao último glifo, que é
            # onde ela pediu que esta seção começasse e terminasse.
            #
            # O comentário que estava aqui dizia que a moldura acompanha o
            # conteúdo "porque moldura larga com desenho estreito devolveria o
            # vazio para DENTRO do bloco". A observação continua certa, e é por
            # isso que os DOIS esticam juntos: quem cresce é o desenho, e a
            # moldura só o acompanha. Uma moldura em FILL com o desenho em
            # START seria exatamente o defeito que aquele comentário descreve.
            barras.set_halign(Gtk.Align.FILL)
            barras.set_hexpand(True)
            caixa.set_halign(Gtk.Align.FILL)
            miolo.pack_start(barras, True, True, 0)
            self._gyro_bars = barras
            self._gyro_box = caixa
            self._esconder_modulo(caixa)
            return caixa

        def _montar_linha_inferior(self) -> Any:
            """A faixa de leitura ao vivo, na ordem que a mantenedora pediu.

            STATUS-SIMETRIA-01 — *"a área do mic que deveria ficar à direita
            dos analógicos"*; SOM-01 — *"dava pra colocar o auto falante abaixo
            do microfone"*::

                [ Touchpad ]                 [ Microfone    ] [ ] [ ] [ ] [ ]
                [ Lightbar ] [ L3 ] [ R3 ]   [ Alto-falante ] [ ] [ ] [ ] [ ]
                                                              [ ] [ ] [ ] [ ]
                                                              [ ] [ ] [ ] [ ]

            O microfone continua DENTRO do card — a madrugada de 26/07 o mandou
            para o rodapé da aba, que é o oposto do pedido, e foi revertida.

            Cada módulo se esconde SOZINHO quando não há sensor: nenhum deles
            arrasta o vizinho, e nenhum deles leva os botões junto (a armadilha
            de LEGIBILIDADE-01, quando o grid morava dentro da linha que sumia).

            **A sobra de largura se reparte entre os TRÊS blocos da faixa.**
            Os três filhos entram com ``expand=True, fill=False``: cada um
            recebe um terço do excedente e fica CENTRADO no próprio pedaço, de
            modo que o que sobra vira o mesmo respiro em toda a faixa. Com a
            sobra indo só para o miolo (o que valia antes do teto elástico),
            ela se acumulava em dois vãos — e com o card podendo chegar a
            1400px seriam ~270px de nada de cada lado, acima do aceite de 200px
            que `test_status_faixa_blocos` cobra. `fill=False` é o que mantém
            os blocos com a largura do conteúdo: com `fill=True` a moldura de
            cada um esticaria e o vazio voltaria para DENTRO dos blocos.
            """
            linha = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=self._espaco,
            )

            # ALINHA-DUAS-LINHAS-01 (01/08, pedido dela: *"alinha e estica a
            # seção do giroscópio pra ficar entre o microfone e o triângulo;
            # alinha a seção do L2 e R2 pra ficar entre o touchpad e o
            # analógico direito"*).
            #
            # A faixa passa a ter DUAS METADES nomeadas, e não três blocos
            # soltos. Elas existem para que a linha de CIMA (gatilhos e
            # giroscópio) tenha em que se alinhar: sem um widget que vá do
            # touchpad ao analógico direito, "alinhar com aquilo" não tem
            # objeto — era por isso que a linha de cima dividia o card ao meio
            # por conta própria e nada batia.
            #
            # Medido na tela dela (1870, card em 1400) antes desta leva:
            #   metade esquerda  254 -> 952   |  L2/R2 ia de 281 a 681
            #   metade direita   968 -> 1616  |  giroscópio ia de 943 a 1377
            # As duas metades já eram os limites certos; faltava alguém que os
            # carregasse.
            #
            # `fill=False` nos filhos DENTRO de cada metade continua valendo —
            # é o que mantém o microfone colado nos analógicos e o vazio fora
            # dos blocos.
            esquerda = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=self._espaco,
            )
            esquerda.pack_start(self._montar_coluna_sensores(), True, False, 0)
            esquerda.pack_end(self._montar_sticks(), True, False, 0)
            self._metade_esquerda = esquerda
            self._grupo_coluna_esquerda.add_widget(esquerda)
            linha.pack_start(esquerda, True, True, 0)

            # O miolo — a coluna do som COLADA à direita dos analógicos, que é
            # o pedido ao pé da letra da SOM-01, mais o grid de glifos. Ele
            # continua se chamando `_miolo_inferior` porque é a cadeia de pais
            # que `test_status_cards_sensores` trava
            # (`_mic_box -> _coluna_audio -> _miolo_inferior -> _linha_inferior`)
            # e o microfone continua exatamente onde estava.
            miolo = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=self._espaco,
            )
            miolo.pack_start(self._montar_coluna_audio(), True, False, 0)
            # Botões ancorados à DIREITA (`pack_end`), não empurrados pelo que
            # vem antes: microfone e alto-falante aparecem e somem conforme o
            # controle, e o grid de 16 glyphs não pode dançar de lugar a cada
            # vez que um módulo de sensor entra ou sai.
            glyphs = self._montar_glyphs()
            glyphs.set_halign(Gtk.Align.END)
            miolo.pack_end(glyphs, True, False, 0)
            self._miolo_inferior = miolo
            self._grupo_coluna_direita.add_widget(miolo)
            linha.pack_start(miolo, True, True, 0)
            self._linha_inferior = linha
            return linha

        def _montar_coluna_sensores(self) -> Any:
            """Coluna da esquerda: touchpad e lightbar empilhados.

            SOM-01: o alto-falante saiu daqui e foi para baixo do microfone
            (`_montar_coluna_audio`). Ele estava nesta coluna por herança da
            rodada que empilhou o que sobrava à esquerda, não porque o assunto
            fosse esse: som e cor não têm relação, e o microfone — que é o par
            dele — ficava do outro lado da faixa.
            """
            coluna = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=self._espaco // 2,
            )
            coluna.pack_start(self._montar_touchpad(), False, False, 0)
            coluna.pack_start(self._montar_lightbar(), False, False, 0)
            coluna.set_valign(Gtk.Align.START)
            self._coluna_sensores = coluna
            return coluna

        def _montar_coluna_audio(self) -> Any:
            """Coluna do SOM: microfone e, logo abaixo dele, o alto-falante.

            SOM-01, pedido 1 — *"dava pra colocar o auto falante abaixo do
            microfone"*. Os dois são o mesmo assunto (o áudio do controle) e
            estavam em pontas opostas da faixa: o alto-falante embaixo da
            lightbar, na coluna da esquerda, e o microfone à direita dos
            analógicos.

            A coluna alinha pelo TOPO (`valign=START`) como as vizinhas: sem
            isso o microfone desceria para o meio da faixa quando o grid de
            botões — que é o bloco mais alto — crescesse, e os títulos das
            molduras deixariam de se ler na mesma linha.
            """
            coluna = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=self._espaco // 2,
            )
            coluna.pack_start(self._montar_mic(), False, False, 0)
            coluna.pack_start(self._montar_speaker(), False, False, 0)
            coluna.set_valign(Gtk.Align.START)
            self._coluna_audio = coluna
            return coluna

        def _montar_touchpad(self) -> Any:
            # LEGIBILIDADE-01/R4 — o estado de cada módulo desceu para BAIXO do
            # desenho. Ao lado do título ele economizava uma linha de altura,
            # que era o recurso escasso quando os cinco blocos dividiam UMA
            # fileira. Agora a altura da faixa é ditada pelos analógicos (a
            # cápsula é o bloco mais alto) e sobra folga vertical de sobra; o
            # que ficou escasso é a LARGURA, porque dois cards lado a lado
            # somam direto no mínimo da janela e a aba Status não tem rolagem
            # horizontal. Com "sem toque" ao lado do título, a coluna do
            # touchpad pedia 105px para desenhar um painel de 76.
            touch, miolo = self._bloco("Touchpad")
            painel = TouchpadView()
            if not self._compact:
                # O piso é o de sempre; o teto de crescimento é o natural.
                # CARD-OCUPA-01: subir o piso estouraria o mínimo do card.
                painel.set_size_request(*_TOUCHPAD_PX_UNICO)
                painel.definir_largura_natural(_DESENHO_NATURAL_PX_UNICO)
            miolo.pack_start(painel, False, False, 0)
            rotulo = self._rotulo_secao(texto_toques(0))
            miolo.pack_start(rotulo, False, False, 0)
            self._touch_view = painel
            self._touch_label = rotulo
            self._touch_box = touch
            self._esconder_modulo(touch)
            return touch

        def _montar_mic(self) -> Any:
            """Bloco PRÓPRIO do microfone, à direita dos dois analógicos.

            MIC-PRESENTE-01 — ele NUNCA se esconde. Esconder um widget de uma
            faixa horizontal muda a largura de todos os vizinhos: além de o
            microfone desaparecer (e sumir é indistinguível de "não existe"),
            os analógicos e o grid de botões pulavam de lugar a cada vez que
            ele entrava ou saía — e por Bluetooth ele sai quase sempre, porque
            a captura é Opus tunelado em HID e é instável.

            A largura fica reservada por construção, em dois pontos: o campo
            fixo do rótulo de estado (`_MIC_ESTADO_CHARS`, medido pela mais
            longa das frases) e um `Gtk.SizeGroup` HORIZONTAL amarrando o
            medidor ao rótulo — os dois passam a ter a largura do maior, e
            trocar de estado não mexe em nenhuma das duas.
            """
            mic, miolo = self._bloco("Microfone")
            medidor = MicMeter()
            medidor.set_valign(Gtk.Align.CENTER)
            if not self._compact:
                # Espelho do touchpad (CARD-OCUPA-01): piso igual, teto no
                # natural. O `Gtk.SizeGroup` lá embaixo leva o teto ao selo
                # junto — os dois passam a ter a largura da coluna.
                medidor.set_size_request(*_MIC_METER_PX_UNICO)
                medidor.definir_largura_natural(_DESENHO_NATURAL_PX_UNICO)
            miolo.pack_start(medidor, False, False, 0)
            selo = Gtk.Label()
            selo.set_valign(Gtk.Align.CENTER)
            selo.set_halign(Gtk.Align.START)
            selo.set_width_chars(_MIC_ESTADO_CHARS)
            selo.set_max_width_chars(_MIC_ESTADO_CHARS)
            # LEGIBILIDADE-01: o degrau vem da escala (`.hefesto-selo`), não do
            # `font_size="x-small"` que estava no markup. Aquele atributo era
            # RELATIVO à fonte da distribuição — rendia 9,3px nesta máquina, o
            # MENOR texto da interface — e nenhum ajuste de tema o alcançava,
            # porque a escala global reescreve o CSS, não markup de Pango.
            selo.get_style_context().add_class("hefesto-selo")
            miolo.pack_start(selo, False, False, 0)
            # MIC-USB-01, entrega 2 — o BOTÃO. Ele estava escrito no IPC
            # (`ipc_bridge.mic_set`, com o ponto de fiação documentado) e não
            # tinha um único chamador na interface: o projeto sabia ler o mudo,
            # sabia mostrá-lo e tinha a função para mudá-lo, e não oferecia o
            # botão. O único caminho para desmutar era o botão físico.
            #
            # Ele entra ABAIXO do medidor porque o miolo do bloco é vertical:
            # ali custa altura (que sobra — a coluna dos botões 4x4 é bem mais
            # alta) e não largura, que é a restrição dura desta aba.
            botao = Gtk.Button()
            botao.set_halign(Gtk.Align.FILL)
            # O rótulo é um Label NOSSO, e não o que `Gtk.Button(label=...)`
            # fabrica, por uma razão medida: `set_label()` DESTRÓI e recria o
            # label interno, e levaria o teto de largura junto no primeiro
            # troca-troca de estado — o campo fixo duraria até o primeiro
            # clique.
            #
            # Campo FIXO aqui pelo mesmo motivo do rótulo de estado: sem teto,
            # o rótulo mais longo do botão decidiria a largura da coluna e
            # trocar de estado moveria os vizinhos de lugar. Com dois cards
            # lado a lado essa largura soma DIRETO no mínimo da janela — o
            # orçamento inteiro da aba é de 26px
            # (`test_dois_cards_lado_a_lado_cabem_na_largura_da_janela`).
            rotulo_botao = Gtk.Label(label=TEXTO_BOTAO_MIC_SEM_LEITURA)
            rotulo_botao.set_ellipsize(Pango.EllipsizeMode.END)
            rotulo_botao.set_max_width_chars(_MIC_ESTADO_CHARS)
            botao.add(rotulo_botao)
            self._mic_botao_rotulo = rotulo_botao
            botao.connect("clicked", self._on_mic_clicado)
            # O botão fica FORA do SizeGroup de propósito: ele já tem teto
            # próprio (o `max_width_chars` do rótulo acima) e amarrá-lo aqui
            # faria o medidor e o selo herdarem a largura DELE — o oposto do
            # que este grupo existe para fazer.
            # MIC-VOLUME-01 — o controle deslizante, em LINHA PRÓPRIA, pelo
            # mesmo motivo medido do alto-falante (SOM-03): dividindo a linha
            # com um botão, o `GtkBox` reparte pelo NATURAL de cada um e o
            # controle fica com ~34px — "só a bolinha, sem trilho", nas palavras
            # dela. Sozinho na linha, ele recebe a largura inteira da caixa.
            #
            # E **sem `set_size_request`**: um piso de largura subiria direto
            # para o mínimo do bloco e dali para o da janela, que é a restrição
            # dura desta aba (o orçamento dos dois cards lado a lado é de 26px).
            # Quem dá largura a ele é a linha própria, não um piso.
            escala_mic = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 0, 100, 1
            )
            # O número não é desenhado aqui: o medidor acima já mostra o SINAL,
            # e escrever o valor MANDADO ao lado do nível LIDO é a confusão que
            # o bloco do alto-falante aprendeu a não criar.
            escala_mic.set_draw_value(False)
            escala_mic.set_valign(Gtk.Align.CENTER)
            escala_mic.set_hexpand(True)
            escala_mic.set_tooltip_text(DICA_MIC_ESCALA)
            escala_mic.connect("value-changed", self._on_mic_escala_mudou)
            escala_mic.connect("button-press-event", self._on_mic_escala_pega)
            escala_mic.connect("button-release-event", self._on_mic_escala_solta)
            escala_mic.connect("key-release-event", self._on_mic_escala_solta)
            self._mic_escala = escala_mic
            self._mic_arrastando = False
            self._mic_pintando = False
            self._mic_repouso_id: int | None = None

            # A LINHA ÚNICA, e ela é o desenho dela: *"esse botão de silenciar
            # some, dá espaço a um slicer de microfone (…) ali onde temos o
            # botão por rádio trocamos por Silenciar"*. O controle deslizante
            # ocupa o LUGAR do botão, e o botão vai para onde estava o
            # interruptor da ponte. **Substituir, não somar.**
            #
            # E a geometria concorda, o que não é coincidência: numa primeira
            # tentativa eu acrescentei o controle numa linha PRÓPRIA sem tirar
            # nada, e o `test_a_coluna_do_som_nao_e_a_mais_alta_da_faixa`
            # reprovou na hora — a coluna do som foi a 292px contra os 258 de
            # teto (246 da maior vizinha + 12 de folga). Os 34px eram
            # exatamente a linha nova. Na linha única o custo é ZERO: ela já
            # tem 34px por causa do botão.
            #
            # O controle entra com `expand=True` e o botão com o natural dele:
            # é o que o bloco do alto-falante NÃO conseguiu fazer, porque lá a
            # linha tinha DOIS botões (101 + 93px) e não sobrava trilho. Aqui
            # sobra — um botão só.
            #
            # A LINHA TEM DUAS PEÇAS, e não três: até 16/08 havia aqui um
            # terceiro morador, o interruptor "Pelo rádio" (com o rótulo dele
            # no card largo). Ele saiu — o porquê e a condição de volta estão
            # no cabeçalho deste arquivo, junto do MIC-BT-01 — e a largura que
            # ele devolveu é o que faz o controle deslizante caber sem afrouxar
            # número nenhum: com os dois na mesma linha, a aba pedia 1236px
            # numa janela de 1180 e o card pedia 595px de 590.
            linha_mic = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            linha_mic.pack_start(escala_mic, True, True, 0)
            linha_mic.pack_start(botao, False, False, 0)
            miolo.pack_start(linha_mic, False, False, 0)
            grupo = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
            grupo.add_widget(medidor)
            grupo.add_widget(selo)
            self._grupo_largura_mic = grupo
            self._mic_meter = medidor
            self._mic_selo = selo
            self._mic_botao = botao
            self._mic_box = mic
            self._aplicar_estado_mic(None, presente=False)
            self._aplicar_acao_mic(acao_mic(None))
            return mic

        def _on_mic_clicado(self, _botao: Any) -> None:
            """Manda o pedido de mudo ao firmware — fora da thread GTK.

            O IPC é bloqueante (``ipc_bridge.mic_set`` espera a resposta do
            daemon), e bloquear a thread GTK num clique é como esta interface
            já congelou antes. O callback de volta não pinta nada: quem repinta
            é o tick de 10 Hz da aba, relendo ``daemon.state_full``. Guardar o
            valor MANDADO como se fosse leitura é justamente o hábito que fez a
            tela parecer mentirosa quando ela nunca mentiu.
            """
            acao = self._mic_acao
            if acao is None or not acao.sensivel or self._som_sem_alvo():
                return
            valor = acao.valor
            uniq = self._uniq

            def _pedir() -> bool:
                return ipc_bridge.mic_set(valor, uniq)

            ipc_bridge.run_in_thread(_pedir, lambda _ok: False)

        def _montar_lightbar(self) -> Any:
            """Bloco "Lightbar": a cor que já chega no card, agora como BARRA.

            Mesma fonte do swatch do título (``entry.lightbar_rgb``) — nada de
            consultar o daemon outra vez. Sem cor conhecida o bloco some: o
            rótulo "Lightbar: cor desconhecida" do corpo já responde, e uma
            faixa preta ali seria "apagada" dita sem prova.
            """
            caixa, miolo = self._bloco("Lightbar")
            barra = LightbarBar()
            barra.set_valign(Gtk.Align.CENTER)
            if not self._compact:
                barra.set_size_request(*_BARRA_FINA_PX_UNICO)
            miolo.pack_start(barra, False, False, 0)
            hexa = self._rotulo_secao("")
            miolo.pack_start(hexa, False, False, 0)
            self._lightbar_bar = barra
            self._lightbar_hex = hexa
            self._lightbar_box = caixa
            self._esconder_modulo(caixa)
            return caixa

        def _montar_speaker(self) -> Any:
            """Bloco "Alto-falante": leitura EM CIMA, comando EMBAIXO.

            STATUS-SIMETRIA-02, entrega 4 — *"não tem a parte do som"*. O
            bloco sumia da tela dela por construção: o daemon só publica a
            chave ``speaker`` DEPOIS de um ``speaker.set`` nosso, porque o
            DualSense não devolve o volume (não há report de input nem feature
            report que o leia — ver ``ipc_handlers``), e o card escondia o
            módulo inteiro na ausência da chave. Só que sumir é
            indistinguível de "este controle não tem alto-falante". O bloco
            NUNCA se esconde, em nenhum dos caminhos.

            SOM-02 põe o comando ao lado da leitura, e as duas peças têm
            significados diferentes de propósito:

            * **a barra e o rótulo são LEITURA** — repintados pelo tique de
              10 Hz a partir de ``daemon.state_full``, jamais pelo valor que
              mandamos. Sem posse, a barra fica vazia e o rótulo diz
              ``não ajustado``;
            * **o controle deslizante é COMANDO** — e fica em repouso (no
              zero) enquanto não houver posse, sem afirmar posição. Pôr o
              cursor no meio com o rótulo ``não ajustado`` seria desenhar 50 %
              e negá-lo por escrito;
            * **os dois botões** só ficam sensíveis com posse
              (:func:`acao_speaker_mudo`, :func:`acao_speaker_devolucao`).

            Tudo isso entra ABAIXO da barra pelo mesmo motivo que o botão do
            microfone (`_montar_mic`): no miolo vertical do bloco o custo é de
            ALTURA, que sobra, e não de largura, que é a restrição dura desta
            aba. Medido nesta bancada com a fonte na escala 3: no card de um
            controle o mínimo do bloco é 174px com posse e 200px sem ela, e o
            do controle deslizante 34px; no compacto, 94px contra os mesmos
            34px — o controle deslizante custa ZERO largura nos dois, pelo
            mesmo teste que o botão do microfone passou.

            SOM-03 arrumou a ORDEM das quatro peças, que era o que tornava o
            controle deslizante inútil (30px de bolinha sem trilho na tela
            dela). O desenho de agora, nos dois cards::

                [============ barra ============]   leitura
                [--------O---------------------]    comando
                71 %             [Silenciar][Devolver]

            O controle deslizante tem LINHA PRÓPRIA e nasce colado na barra que
            comanda — as duas peças continuam sendo duas (E5), e ficarem uma
            sobre a outra, do mesmo tamanho, é o que deixa ler de relance que
            dizem a mesma grandeza. No card compacto o rótulo de valor fica na
            linha dele e os botões na de baixo, porque fundi-los ali estouraria
            a largura da aba — os números estão no bloco de comentários do
            empacotamento, mais abaixo.
            """
            caixa, miolo = self._bloco(TITULO_SPEAKER)
            # O rótulo da moldura vira o lugar do número (card único).
            self._speaker_titulo = (
                caixa.get_label_widget() if not self._compact else None
            )
            # SOM-02/E5, item 3: a linha de explicação no lugar do silêncio.
            # Ela vive na dica do BLOCO (e não do controle deslizante) porque
            # responde à pergunta que o bloco inteiro levanta — por que o
            # normal aqui é "não ajustado".
            caixa.set_tooltip_text(DICA_BLOCO_SPEAKER)
            barra = SpeakerBar()
            barra.set_valign(Gtk.Align.CENTER)
            if not self._compact:
                barra.set_size_request(*_BARRA_SPEAKER_PX_UNICO)
            # A ORDEM de empacotar está toda junta lá embaixo, depois que as
            # peças existem: ela é o assunto desta leva e muda entre os dois
            # cards, e espalhá-la pela função foi o que escondeu, na SOM-02,
            # que o controle deslizante dividia a linha com 194px de botões.
            # Sem campo fixo aqui, ao contrário do microfone. A razão escrita
            # até a SOM-02 era que o rótulo da moldura seria sempre o mais
            # largo — e a medição desta leva REFUTOU isso: no card compacto
            # "Alto-falante" pede 80px e "não ajustado" pede 89, e é este quem
            # dita o mínimo do bloco. O campo fixo continua fora por outro
            # motivo, esse sim medido: ele reservaria a largura do MAIOR texto
            # em todos os estados, e o estado com posse ("71 %", 28px) é o
            # comum depois do primeiro gesto — pagaríamos 61px por card, em
            # dobro na aba com dois cards, para não mover um rótulo que muda
            # uma vez por sessão.
            valor = self._rotulo_secao(TEXTO_SPEAKER_SEM_DADO)
            # O selo da CAMADA 1 nasce escondido e só aparece quando alguém
            # souber dizer que o sink está mudo. `_esconder_modulo` (e não um
            # `hide()` cru) porque o `show_all()` do card revelaria de volta
            # qualquer filho apagado antes dele.
            selo_saida = self._rotulo_secao(TEXTO_SELO_SAIDA_MUDA)
            # O TETO de largura do selo (SOM-04). Ele não tinha nenhum: o texto
            # do selo decidia o mínimo do bloco, e daí o do card e o da janela.
            # Com a frase inteira do recado do som ali, o card de um controle
            # ia a 1223px numa janela que abre com 1180. Os números estão em
            # `_SELO_CHARS`.
            selo_saida.set_ellipsize(Pango.EllipsizeMode.END)
            selo_saida.set_max_width_chars(_SELO_CHARS)
            escala = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 0, 100, 1
            )
            # O número já está no rótulo de leitura acima; desenhá-lo de novo
            # aqui custaria 13px de largura mínima para repetir o que a linha
            # de cima diz — e diria o valor MANDADO ao lado do valor LIDO, que
            # é exatamente a confusão que este bloco existe para não criar.
            escala.set_draw_value(False)
            escala.set_valign(Gtk.Align.CENTER)
            # **Nenhum piso de largura aqui, nos DOIS cards.** Não é
            # esquecimento: o controle deslizante ocupa a LINHA INTEIRA do
            # bloco (é o único filho dela), e um `set_size_request` é MÍNIMO —
            # subiria direto para o mínimo do bloco e dali para o da janela.
            # Medido: com o piso de 160px da barra fina, o mínimo do bloco vai
            # de 174 para 258px no card de um controle e de 80 para 206px no
            # compacto — 126px A MAIS por card, somados nos dois cards lado a
            # lado (1148 + 252 = 1400px, contra os 1180 com que a janela abre).
            # É o mesmo teste que o botão do microfone passou: o mínimo do
            # controle novo (34px) tem de ficar ABAIXO do mínimo do bloco.
            # Quem dá LARGURA a ele não é um piso: é a linha própria, que num
            # `GtkBox` vertical entrega a largura inteira da caixa a cada filho
            # independentemente do natural dele (SOM-03).
            escala.set_hexpand(True)
            escala.set_tooltip_text(DICA_SPEAKER_ESCALA)
            escala.connect("value-changed", self._on_speaker_escala_mudou)
            escala.connect("button-press-event", self._on_speaker_escala_pega)
            escala.connect("button-release-event", self._on_speaker_escala_solta)
            escala.connect("key-release-event", self._on_speaker_escala_solta)
            botao_mudo = self._botao_de_acao(TEXTO_BOTAO_SPEAKER_SEM_DADO)
            botao_mudo.connect("clicked", self._on_speaker_mudo_clicado)
            botao_devolver = self._botao_de_acao(TEXTO_BOTAO_SPEAKER_DEVOLVER)
            botao_devolver.connect(
                "clicked", self._on_speaker_devolucao_clicada
            )
            # SOM-03 — *"a escala tem cerca de 30 pixels de largura, é só a
            # bolinha, sem trilho"*. **O controle deslizante tem LINHA PRÓPRIA
            # nos dois cards**, e quem paga a linha é o rótulo de valor, que
            # sobe para a linha dos botões em vez de gastar uma só para si.
            #
            # A causa do defeito era de REQUISIÇÃO, não de alocação: dividindo
            # a linha com os dois botões, o controle recebia o NATURAL dele
            # (34px) e os botões, os deles (101 e 93px) — `GtkBox` reparte o
            # excedente só depois de todo mundo chegar ao natural, e num bloco
            # de 254px não havia excedente nenhum. A barra de leitura logo
            # acima, essa sim sozinha na linha, recebia 240px para dizer a
            # MESMA grandeza. Medido na janela de projeto (1180px), que é como
            # ela abre: controle deslizante 38px contra uma barra de 240px.
            #
            # Num `GtkBox` VERTICAL o filho único de uma linha recebe a largura
            # inteira da caixa, natural ou não — é por isso que a linha própria
            # cura sem piso de largura, sem tocar no mínimo de ninguém e sem
            # gastar um pixel dos 32 que a aba tem de folga.
            #
            # **De onde vieram os pixels de ALTURA.** Empilhar as três peças em
            # linhas separadas (barra / valor / controle / botões) é o desenho
            # óbvio e pedia 477px para uma faixa de 467 — 10px acima do corte.
            # Fundir o rótulo de valor com a linha dos botões devolve os 20px
            # da linha do rótulo mais os 2px do respiro dela, e a linha
            # resultante não cresce: ela já tinha a altura do botão (38px), que
            # é maior que a do rótulo (20px). Sobra a diferença entre o que o
            # controle deslizante pede (34px) e o que o rótulo pedia (20px).
            # As duas peças continuam sendo duas peças (E5): a leitura é a
            # barra mais o número, o comando é o controle mais os botões.
            #
            # * card de UM controle: a altura é o recurso escasso e é dela que
            #   esta cura gasta. O card pede 456px dos 467 da faixa (contra 442
            #   com o controle espremido) e o controle deslizante passa de 38
            #   para 240px na janela de projeto e para 360px na tela dela
            #   maximizada — a mesma largura da barra que ele comanda;
            # * card COMPACTO: a largura é o recurso escasso, e lá o controle
            #   JÁ tinha linha própria desde a SOM-02 — recebe 113px com dois
            #   cards na janela de projeto e 206px com a janela em 1870. Este
            #   card NÃO funde o rótulo de valor com a linha dos botões, e o
            #   motivo é medido: fundir levaria o mínimo do bloco de 94 para
            #   186px, somados nos dois cards lado a lado, e estouraria os
            #   1180px com que a janela abre. A altura dele fica onde estava
            #   (449px dos 467), e o que muda é só a ORDEM — o controle passa
            #   a nascer colado na barra que ele comanda, como no card único.
            if self._compact:
                # SOM-03, segunda rodada: o número sobe para a linha da BARRA
                # em vez de gastar uma linha só dele. Aqui a altura é o recurso
                # escasso (a coluna do som é a mais alta do card compacto e não
                # há grade de glifos por baixo para lhe servir de piso), e a
                # largura não tem de onde vir — 32px de folga na aba inteira,
                # somados nos dois cards.
                #
                # Esta é a ÚNICA fusão que sai de graça nos dois orçamentos, e
                # os números são medidos: o rótulo entra elipsável, então o
                # mínimo dele cai de 94 para ~20px e a linha inteira pede
                # 60 (barra) + 20 + 4 = 84px — ABAIXO dos 94 que o bloco já
                # custava. O bloco fica 21px mais baixo E 6px mais estreito.
                # Fundir com a linha dos BOTÕES, que era o reflexo, pediria
                # 112px e subiria a aba de 1148 para 1184 contra os 1180.
                #
                # O `get_text()` continua devolvendo o texto inteiro — elipse é
                # desenho, não conteúdo — e no card de UM controle o rótulo
                # segue sem elipse nenhuma, com a linha dos botões só para ele.
                valor.set_ellipsize(Pango.EllipsizeMode.END)
                linha_leitura = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=4
                )
                linha_leitura.pack_start(barra, True, True, 0)
                linha_leitura.pack_start(valor, False, False, 0)
                miolo.pack_start(linha_leitura, False, False, 0)
                miolo.pack_start(escala, False, False, 0)
                # LIMITAÇÃO DECLARADA, com o preço medido: com dois cards na
                # janela de projeto cada bloco recebe ~113px, e os dois botões
                # lado a lado ficam com ~55px cada — os rótulos truncam para
                # "Ativ..." e "Dev...", e quem diz a ação por inteiro é a dica.
                # As saídas foram medidas e custam mais do que existe:
                # empilhar os botões custa 40px de altura; fundir os botões com
                # o rótulo de valor sobe o mínimo do bloco de 94 para 186px; e
                # alargar o bloco sobe somado nos dois cards, contra 32px de
                # folga na aba inteira. No card de um controle — a tela que ela
                # usa com um DualSense — os dois rótulos aparecem inteiros
                # sempre que há posse, que é quando eles funcionam.
                linha_botoes = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=4
                )
                linha_botoes.set_homogeneous(True)
                linha_botoes.pack_start(botao_mudo, True, True, 0)
                linha_botoes.pack_start(botao_devolver, True, True, 0)
                miolo.pack_start(linha_botoes, False, False, 0)
            else:
                # SOM-ROTA-NO-CARD-01: a barra fica SOZINHA na linha, e o
                # número vai para o rótulo da moldura (`_speaker_titulo`).
                #
                # As duas outras casas foram medidas e cada uma quebra uma
                # regra que já estava paga:
                #   * dividir a linha com a barra faz a barra medir 276px
                #     debaixo de um medidor de microfone de 360 — a
                #     CARD-OCUPA-01 exige os dois IGUAIS, e há teste;
                #   * dividir a linha com a escala encurta o controle
                #     deslizante abaixo da barra que ele comanda, e há teste
                #     para isso também (SOM-03).
                # O rótulo da moldura não custa altura nem largura: ele já
                # existe, e "Alto-falante" tem folga de sobra na borda.
                miolo.pack_start(barra, False, False, 0)
                miolo.pack_start(escala, False, False, 0)
                # O número à ESQUERDA e as ações à direita: o rótulo entra com
                # `expand`/`fill` e empurra os dois botões para a borda da
                # moldura. `xalign=0` (de `_rotulo_secao`) mantém o texto
                # colado à esquerda enquanto a caixa dele estica.
                #
                # LIMITAÇÃO DECLARADA, com o preço medido nesta bancada: com a
                # janela na largura de PROJETO (1180px) e SEM posse, esta linha
                # quer 296px (o rótulo "não ajustado" pede 94, "sem dado" 101 e
                # "Devolver" 93, mais 8 de respiro) e o bloco tem 243 — os dois
                # botões encolhem para ~70px e os rótulos elipsam. É o único
                # estado em que isso acontece, e é o estado em que os dois
                # botões estão INSENSÍVEIS (sem volume conhecido não há mudo
                # nem devolução a fazer — `acao_speaker_mudo`). Com posse, que
                # é quando eles funcionam, a linha quer 223 dos mesmos 243 e os
                # rótulos saem inteiros; com a janela em 1400 ou mais, saem
                # inteiros nos dois estados.
                #
                # As duas saídas foram medidas e custam mais do que existe:
                # devolver ao rótulo de valor a linha só dele leva o card a
                # 478px contra os 467 da faixa (é o desenho "óbvio", 11px acima
                # do corte); e alargar o bloco para 296 não tem de onde vir —
                # na largura de projeto a faixa inteira já está comprimida
                # (pede 1338px de natural e recebe 1098), e cada pixel do bloco
                # do som sai do touchpad e do medidor do microfone, que a
                # CARD-OCUPA-01 acabou de encher.
                # SOM-ROTA-NO-CARD-01 (01/08, pedido dela: *"aquele botão de
                # voltar ao anterior sai de lá de cima e fica no espaço onde
                # tem 'não ajustado' no alto-falante"*).
                #
                # O rótulo de valor sobe para a linha da BARRA — é a mesma
                # fusão que o card compacto já fazia — e o lugar que ele
                # ocupava recebe o botão da rota de som. Duas consequências
                # medidas, e as duas importam:
                #
                # 1. **custo de ALTURA zero.** A linha de ações já tinha a
                #    altura de um botão (38px contra os 20 do rótulo), então
                #    trocar o rótulo por um botão não a faz crescer. Era esse
                #    o impedimento registrado na SOM-04 — *"um botão a mais no
                #    bloco custa +36px e leva o card de 442 para 478 contra os
                #    467 da faixa"* — e ele valia para ACRESCENTAR uma peça,
                #    não para TROCAR. A linha de leitura, por sua vez, cresce
                #    para a altura do rótulo, que é menor que a do botão.
                # 2. **o botão continua sendo UM.** Ele é o widget do glade,
                #    reparentado pela `status_actions` para o slot do card
                #    PRIMÁRIO — a segunda razão da SOM-04 (a saída padrão do
                #    sistema é um fato global, e dois cards não podem ter dois
                #    botões para um interruptor só) continua de pé, e é por
                #    isso que aqui há um SLOT vazio e não um botão novo.
                # SOM-CANAL-01 (02/08/2026) — o bloco confundia DUAS coisas.
                #
                # Ela: *"existem dois caminhos de áudio independentes para o
                # alto-falante do DualSense, e a tela hoje trata os dois como
                # se fossem o mesmo"*.
                #
                #   1. **a rota do SISTEMA** (PipeWire): trocar o default sink
                #      faz TODO o som do PC sair no controle. É um comando do
                #      sistema operacional;
                #   2. **o canal do JOGO** (`OUTPUT_PATH_SEL`, byte 7): o jogo
                #      manda um som para o dispositivo de áudio do controle e
                #      o byte decide como o firmware o distribui. É o caso do
                #      Zelda — a espada no controle, a trilha na TV.
                #
                # **Os dois podem estar ligados ao mesmo tempo**, e por isso
                # não podem ser um botão só. Viraram um SELETOR de dois
                # estados, com o `Silenciar` ao lado como o "desligado" — e
                # não um terceiro estado, que confundiria "onde o som sai" com
                # "tem som".
                #
                # O byte foi MEDIDO antes deste desenho existir: em 02/08 ela
                # ouviu o toque da rota 3 (canal direito ao alto-falante) e NÃO
                # ouviu o da rota 0 (tudo ao fone, que não está plugado). O
                # portão da SOM-ROTA-01/E1 abriu com a orelha dela.
                # A pergunta "O que sai no controle:" NÃO ganha linha própria.
                # Ela foi medida e custa a QUARTA linha do bloco, que é altura
                # de card em toda fonte (`test_o_bloco_do_som_nao_gasta_linha_
                # com_o_que_pode_dividir`). Ela vive na dica do seletor, e os
                # dois rótulos já dizem o eixo sozinhos.
                linha_acoes = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=4
                )
                seletor = SegmentedSelector()
                # A altura é o orçamento apertado desta linha (ver a classe no
                # theme.css): o seletor pede 67px contra os 34 do botão que ele
                # substituiu, e isso sozinho estourava a coluna do som.
                seletor.get_style_context().add_class("hefesto-seletor-compacto")
                seletor.set_items(list(CANAIS_DO_SPEAKER))
                seletor.set_tooltips(dict(DICAS_DO_CANAL))
                seletor.connect("changed", self._on_canal_do_speaker_mudou)
                self._speaker_canal = seletor
                linha_acoes.pack_start(seletor, True, True, 0)
                linha_acoes.pack_start(botao_mudo, False, False, 0)
                # SOM-CANAL-01/E4: o `Soltar` SAIU da fileira. Ela mediu a
                # utilidade real dele: *"o DualSense não tem botão físico de
                # volume, o valor não é restaurado ao soltar, e quem poderia
                # mandar depois é o jogo — que é justamente o que a
                # PARIDADE-SONY-01 ainda não confirmou"*. E ele não pertencia
                # ali por significado: os outros falam de ONDE o som sai, e
                # ele fala de QUEM manda no volume.
                #
                # Ele continua existindo e continua funcionando — quem o
                # explica agora é a dica do bloco. Quando a paridade for
                # confirmada, ele volta para a tela.
                self._speaker_rota_slot = None
                miolo.pack_start(linha_acoes, False, False, 0)
            # O selo da camada 1 fica por último nos dois cards: ele é a
            # exceção (aparece só quando o sink do sistema está mudo) e é o
            # único filho do bloco que entra e sai em tempo de execução. Numa
            # linha compartilhada, cada aparição dele empurraria o mínimo do
            # bloco — e daí o da janela — no meio da sessão.
            miolo.pack_start(selo_saida, False, False, 0)
            self._esconder_modulo(selo_saida)
            self._speaker_bar = barra
            self._speaker_label = valor
            self._speaker_selo_saida = selo_saida
            self._speaker_escala = escala
            self._speaker_botao_mudo = botao_mudo
            self._speaker_botao_devolver = botao_devolver
            self._speaker_box = caixa
            self._aplicar_estado_speaker(None)
            self._aplicar_acoes_speaker(
                acao_speaker_mudo(None), acao_speaker_devolucao(None)
            )
            return caixa

        def _botao_de_acao(self, rotulo_inicial: str) -> Any:
            """Botão de ação de bloco, no molde do botão do microfone.

            O rótulo é um Label NOSSO, e não o que ``Gtk.Button(label=...)``
            fabrica, pela razão medida em `_montar_mic`: ``set_label()``
            DESTRÓI e recria o label interno e levaria o teto de largura junto
            no primeiro troca-troca de estado. O campo fixo
            (:data:`_SPEAKER_BOTAO_CHARS`) é o que impede o rótulo mais longo
            de decidir a largura da coluna.
            """
            botao = Gtk.Button()
            botao.set_halign(Gtk.Align.FILL)
            rotulo = Gtk.Label(label=rotulo_inicial)
            rotulo.set_ellipsize(Pango.EllipsizeMode.END)
            rotulo.set_max_width_chars(_SPEAKER_BOTAO_CHARS)
            botao.add(rotulo)
            botao._rotulo_hefesto = rotulo
            return botao

        # ------------------------------------------------------------------
        # Alto-falante: os pedidos (SOM-02, entregas 1 a 3)
        # ------------------------------------------------------------------

        # -- MIC-VOLUME-01: o controle deslizante do microfone --------------
        #
        # Os três handlers abaixo são gêmeos dos do alto-falante, e a repetição
        # é deliberada: unificá-los pediria um parâmetro "de quem é o volume"
        # atravessando tudo, e os dois lados têm estados próprios
        # (`_mic_arrastando` x `_speaker_arrastando`) que se tocariam. Duas
        # cópias curtas e óbvias valem mais que uma abstração que confunde de
        # quem é o gesto.

        def _on_mic_escala_pega(self, _escala: Any, _evento: Any) -> bool:
            """A mão dela assumiu: o tique de 10 Hz para de mexer no cursor.

            Sem isto, a releitura do estado brigaria com o arrasto e o controle
            pularia para trás no meio do gesto.
            """
            self._mic_arrastando = True
            return False

        def _on_mic_escala_solta(self, _escala: Any, _evento: Any) -> bool:
            """Fim do gesto: manda o volume agora, sem esperar o repouso."""
            self._mic_arrastando = False
            self._enviar_volume_do_mic()
            return False

        def _on_mic_escala_mudou(self, _escala: Any) -> None:
            """Valor mudou: arma o repouso — nunca manda no ato.

            A guarda do `_mic_pintando` é a parte que não pode cair: sem ela, o
            tique que repinta o controle a partir do estado dispararia um pedido
            de volta ao daemon — um laço de eco entre leitura e comando. Foi
            assim que o volume do alto-falante já andou sozinho.
            """
            if self._mic_pintando:
                return
            self._cancelar_repouso_do_mic()
            self._mic_repouso_id = GLib.timeout_add(
                _MIC_REPOUSO_MS, self._on_mic_repouso
            )

        def _on_mic_repouso(self) -> bool:
            """Passou o repouso sem novo movimento: manda."""
            self._mic_repouso_id = None
            if not self._mic_arrastando:
                self._enviar_volume_do_mic()
            return False

        def _cancelar_repouso_do_mic(self) -> None:
            """Desarma o disparo pendente, se houver."""
            if self._mic_repouso_id is not None:
                with contextlib.suppress(Exception):
                    GLib.source_remove(self._mic_repouso_id)
                self._mic_repouso_id = None

        def _enviar_volume_do_mic(self) -> None:
            """Manda o volume ao daemon, FORA da thread do GTK.

            O IPC é bloqueante, e bloquear a thread do GTK num gesto é como
            esta interface já congelou antes. Não pintamos nada de volta: quem
            repinta é o tique relendo o estado. Guardar o valor MANDADO como se
            fosse leitura é o hábito que fez a tela parecer mentirosa.
            """
            self._cancelar_repouso_do_mic()
            escala = getattr(self, "_mic_escala", None)
            if escala is None or self._som_sem_alvo():
                # Sem endereço, o pedido cairia no PRIMÁRIO — e o repouso podia
                # já estar armado quando o endereço sumiu. Mesma tranca do
                # alto-falante, e pelo mesmo motivo.
                return
            volume = round(escala.get_value())
            if volume == getattr(self, "_mic_volume_enviado", None):
                # Repouso disparando logo depois do fim do arrasto: o mesmo
                # número duas vezes é rajada, não pedido.
                return
            self._mic_volume_enviado = volume
            uniq = self._uniq
            # O `lambda _ok: False` não é enfeite de tipagem: `run_in_thread`
            # reposta o `on_success` pelo laço ocioso do GLib SEMPRE, e um
            # `None` ali estoura dentro da worker — o pedido saía, e o erro
            # morria sem ninguém ver. É o mesmo callback vazio que o
            # alto-falante usa. (Sem escrever o nome da função: há um portão
            # que conta as ocorrências dela neste arquivo por texto cru —
            # `test_gate_timers_nenhuma_ocorrencia_nova_vs_baseline`.)
            ipc_bridge.run_in_thread(
                lambda: ipc_bridge.mic_volume_set(volume=volume, uniq=uniq),
                lambda _ok: False,
            )

        def _pintar_volume_do_mic(self, volume: int | None) -> None:
            """Repõe o cursor a partir do ESTADO — sem disparar novo pedido.

            Respeita a mão dela: enquanto `_mic_arrastando`, não mexe. E o
            `_mic_pintando` é o que impede o eco (ver `_on_mic_escala_mudou`).
            """
            escala = getattr(self, "_mic_escala", None)
            if escala is None or volume is None or self._mic_arrastando:
                return
            if round(escala.get_value()) == int(volume):
                return
            self._mic_pintando = True
            try:
                escala.set_value(float(volume))
            finally:
                self._mic_pintando = False

        def _on_speaker_escala_pega(self, _escala: Any, _evento: Any) -> bool:
            """Botão do mouse APERTADO no controle: a mão dela assumiu.

            Enquanto durar, o tique de 10 Hz para de reposicionar o cursor: sem
            isto, a releitura do estado brigaria com o arrasto e o controle
            pularia para trás no meio do gesto.
            """
            self._speaker_arrastando = True
            return False

        def _on_speaker_escala_solta(self, _escala: Any, _evento: Any) -> bool:
            """Soltou o botão (ou a tecla): manda o volume AGORA.

            É o fim do gesto, e mandar aqui é o que faz o pedido chegar sem
            esperar o repouso. O repouso continua existindo para o que não tem
            fim de gesto — a roda do mouse.
            """
            self._speaker_arrastando = False
            self._enviar_volume_do_controle()
            return False

        def _on_speaker_escala_mudou(self, _escala: Any) -> None:
            """Valor mudou: arma o repouso — nunca manda no ato.

            ``value-changed`` dispara por pixel de arrasto, e o IPC é
            BLOQUEANTE: mandar aqui viraria uma rajada de pedidos enfileirados
            num executor de uma thread só. Quem manda é o fim do gesto
            (`_on_speaker_escala_solta`) ou o repouso, o que vier primeiro.

            A guarda do `_speaker_pintando` é a parte que não pode cair: sem
            ela, o tique de 10 Hz que repinta o controle a partir do estado
            dispararia um pedido de volta ao daemon — um laço de eco entre
            leitura e comando.
            """
            if self._speaker_pintando:
                return
            self._agendar_envio_de_volume()

        def _agendar_envio_de_volume(self) -> None:
            """(Re)arma o disparo único do repouso."""
            self._cancelar_repouso_do_volume()
            self._speaker_repouso_id = GLib.timeout_add(
                _SPEAKER_REPOUSO_MS, self._on_speaker_repouso
            )

        def _cancelar_repouso_do_volume(self) -> None:
            fonte = self._speaker_repouso_id
            self._speaker_repouso_id = None
            if fonte is not None:
                GLib.source_remove(fonte)

        def _on_speaker_repouso(self) -> bool:
            self._speaker_repouso_id = None
            self._enviar_volume_do_controle()
            return False  # disparo ÚNICO (contrato do GLib.timeout_add)

        def _enviar_volume_do_controle(self) -> None:
            """Manda o volume do controle deslizante — fora da thread GTK.

            Três invariantes, cada uma paga com uma medição da SOM-02:

            * **o valor vai SEMPRE explícito.** ``speaker.set`` sem ``volume``
              não é consulta: o backend cai na preferência, que sem volume
              anterior é ZERO, toma a posse e emudece o controle (armadilha 1);
            * **nada de bloquear a thread do GTK**: o pedido vai por
              ``run_in_thread``, como o botão do microfone. Esta interface já
              congelou por IPC bloqueante num clique;
            * **o valor mandado NÃO vira leitura.** O callback não pinta nada;
              quem repinta é o tique de 10 Hz relendo ``daemon.state_full``. Um
              número pintado a partir do que mandamos seria "a tela mentindo"
              no dia em que o daemon recusasse o pedido.
            """
            self._cancelar_repouso_do_volume()
            if self._som_sem_alvo():
                # Sem endereço, `speaker.set` toma a posse do volume do
                # PRIMÁRIO. O repouso já podia estar armado quando o endereço
                # sumiu, e é por isso que a tranca é aqui e não só no gesto.
                return
            volume = volume_do_percentual(self._speaker_escala.get_value())
            if volume == self._speaker_volume_enviado:
                # Repouso disparando logo depois do fim do arrasto: o mesmo
                # número duas vezes é rajada, não pedido.
                return
            self._speaker_volume_enviado = volume
            uniq = self._uniq

            def _pedir() -> Any:
                ok = ipc_bridge.speaker_set(volume=volume, uniq=uniq)
                return self._confirmar_com_som() if ok else None

            # `muted=False` não é chute: `set_speaker_volume` calcula
            # `efetivo = 0 if muted else pref`, e um pedido só de volume chega
            # com `muted=None` — ou seja, este gesto DESMUDA. Registrar o que
            # ficou de pé é registrar isso.
            ipc_bridge.run_in_thread(
                _pedir, self._confirmado_pelo_daemon(volume=volume, muted=False)
            )

        def _on_canal_do_speaker_mudou(self, seletor: Any) -> None:
            """O gesto dela no seletor: escolhe ONDE o som do controle sai.

            SOM-CANAL-01/E2. Os dois estados fazem coisas de CAMADAS
            diferentes, e é por isso que eles não podiam ser um botão só:

            * **Sons do jogo** mexe no byte `OUTPUT_PATH_SEL` (camada 2, o
              firmware) e devolve o default sink do sistema para onde ele
              estava. O jogo continua mandando som para o dispositivo de áudio
              do controle; o byte decide que só o canal direito sai no
              alto-falante e o esquerdo vai para o fone/TV;
            * **Todo o som do PC** mexe no default sink (camada 1, o PipeWire)
              E põe a rota em "só o alto-falante" — com o som inteiro do PC
              vindo por aqui, mandar metade para um fone que não existe seria
              perder metade.

            **A camada 1 vence a camada 2** (armadilha 3 da sprint): volume e
            rota perfeitos num sink mudo é trabalho invisível. Por isso o
            estado "Todo o som do PC" mexe nas duas.

            E ele TOCA o som de confirmação, que é ideia dela: *"ao clicar em
            cada botão ele emite o som (...) tem que ajudar a entender o
            conceito"*. O seletor não só configura — ele demonstra.
            """
            canal = seletor.get_active_id()
            if canal is None or self._speaker_canal_pintando:
                return
            if self._som_sem_alvo():
                # A cura de 04/08 pôs o `uniq` nesta chamada exatamente para
                # ela não escrever no primário. Sem endereço não há `uniq` a
                # pôr, e o pedido volta a ser o defeito que aquela cura matou.
                return
            rota = ROTA_DO_CANAL.get(canal)
            if rota is None:
                return

            # A camada 1 (o default sink do PipeWire) NÃO é chamada daqui: o
            # card é um widget e não tem a `RotaDeSaida`, que vive na aba. Ele
            # PEDE, e a aba executa — o mesmo desenho do `definir_sink_de_saida`
            # que a `status_actions` já injeta aqui.
            #
            # A separação não é cerimônia: a rota do sistema é um fato GLOBAL
            # (há um default sink só), e deixar cada card mexer nele
            # diretamente é como ter dois botões para um interruptor.
            pedir_rota_do_sistema = self._pedir_rota_do_sistema
            # SOM-CANAL-01, CURADO em 04/08/2026 — MEDIDO com ela: clicar aqui
            # SILENCIAVA o alto-falante.
            #
            # A chamada era `speaker_set(rota=rota)`, sem volume e sem uniq, e
            # os dois faltavam por motivos diferentes:
            #
            # 1. **sem volume**: o daemon faz `pref = None -> pref = 0` e
            #    escreve ZERO nos dois registradores, tomando a posse
            #    (`core/backend_pydualsense.py`, `set_speaker_volume`). É a
            #    "Armadilha 1" que a SOM-02 escreveu por extenso — *"speaker.set
            #    {} toma a posse e manda ZERO"* — e que os três irmãos deste
            #    mesmo widget respeitam (`:2963`, `:3036`, `:3049`). O
            #    `profiles/schema.py` chega a RECUSAR perfil sem volume pela
            #    mesma razão; só este chamador escapava;
            # 2. **sem uniq**: o daemon cai no controle PRIMÁRIO. Com dois cards
            #    na tela, clicar no card do Controle 2 escrevia no Controle 1.
            #
            # O volume vem do controle deslizante ao lado, que é o que ela
            # enxerga — reafirmá-lo aqui é dizer ao firmware o mesmo que a tela
            # mostra, em vez de deixá-lo adivinhar.
            uniq = self._uniq
            volume = volume_do_percentual(self._speaker_escala.get_value())

            sink = self._speaker_sink

            def _pedir() -> Any:
                ok = ipc_bridge.speaker_set(rota=rota, volume=volume, uniq=uniq)
                # SOM-SAIDA-MUDA-01: os DOIS estados prometem som no controle,
                # então os dois precisam da camada 1 audível — e só "Todo o som
                # do PC" a tocava, por ser o único que mexe no sink padrão.
                #
                # Com o sink do controle mudo, "Sons do jogo" escrevia o byte
                # certo, devolvia o sink certo e produzia silêncio, sem recado:
                # o `MOTIVO_SAIDA_MUDA` do tocador só dispara quando o mute foi
                # LIDO com certeza, e ausência de leitura é "não sei" — que
                # seguia direto para o tocador.
                audio_saida.garantir_saida_audivel(sink)
                if pedir_rota_do_sistema is not None:
                    pedir_rota_do_sistema(canal == CANAL_TODO_O_PC)
                return self._confirmar_com_som() if ok else None

            # SOM-CANAL-NO-PERFIL-01 (09/08/2026, decisão dela): *"quero a
            # ideia é respeitar tudo (...) tanto usar o mic do controle quanto
            # usar o canal de saída de som específico do DS"*. A rota entra no
            # rascunho junto do volume porque é a MESMA posse: este gesto já
            # manda os dois no mesmo `speaker.set` desde a cura de 04/08, e
            # anotar um sem o outro deixaria o perfil com metade do gesto.
            #
            # O volume anotado é o LIDO do daemon quando existe: o número da
            # tela não volta igual fora da faixa útil do registrador, e trocar
            # o canal não pode baixar o volume dela. Sem leitura
            # (primeira escrita da sessão) vale o que acabou de ser mandado,
            # que é o único número que existe.
            volume_anotado = self._volume_lido_do_daemon()
            ipc_bridge.run_in_thread(
                _pedir,
                self._confirmado_pelo_daemon(
                    volume=volume if volume_anotado is None else volume_anotado,
                    muted=False,
                    rota=rota,
                ),
            )

        def definir_pedido_de_rota(self, callback: Any) -> None:
            """Quem executa a camada 1 quando ela troca o canal.

            Recebe `True` para "manda todo o som do PC para o controle" e
            `False` para "devolve o som para onde ele estava". A aba injeta
            isto na montagem dos cards; sem ele, o seletor ainda escreve o
            byte da camada 2 e o card não fica mudo.
            """
            self._pedir_rota_do_sistema = callback

        def definir_dono_do_rascunho(self, janela: Any) -> None:
            """Quem GUARDA o rascunho do perfil em edição (SOM-02/E4).

            A aba injeta a própria janela na montagem dos cards, do mesmo jeito
            que injeta o sink e o pedido de rota. Sem ela o bloco continua
            funcionando ao vivo e nada é anotado — que é o comportamento
            correto de um card avulso, e é como todo teste de geometria deste
            widget o monta.

            **O card PEDE, quem escreve é o dono.** A escrita mora em
            ``draft_config.registrar_alto_falante_no_rascunho``, escritor único
            e visível ao portão de AST: a classe de defeito desta casa é *"três
            escritores do perfil sem dono"* (auditoria 23/07).
            """
            self._dono_do_rascunho = janela

        def _confirmado_pelo_daemon(
            self,
            *,
            volume: int | None = None,
            muted: bool = False,
            rota: int | None = None,
            soltar: bool = False,
        ) -> Any:
            """O callback de sucesso dos gestos do alto-falante.

            REGISTRAR NÃO É APLICAR, e registrar é DEPOIS. Quem aplica é o
            ``speaker.set`` que já saiu; aqui só se anota no rascunho o que
            ficou DE PÉ, para o "Salvar Perfil" persistir — a mesma disciplina
            de ``registrar_modo_no_rascunho`` na aba Emulação.

            O defeito que isto cura (auditoria de 09/08/2026): o bloco mandava
            o volume por IPC e não tocava no rascunho, então ``to_profile``
            devolvia o número VELHO e ``lifecycle.apply_profile_speaker`` o
            reaplicava ao controle na ativação. Ela ajustava o volume, clicava
            em Salvar, e o próprio gesto de salvar desfazia o ajuste — não só
            perder o valor novo, mas persistir um eco do estado velho.

            ``resultado is None`` é o daemon tendo RECUSADO o pedido (contrato
            escrito em ``_on_som_de_confirmacao``): aí não há o que registrar,
            porque o rascunho descreve o que está de pé e não a intenção.

            ``soltar`` é a DEVOLUÇÃO da posse, e apaga a seção do rascunho — um
            perfil salvo depois de "Soltar" não pode continuar carregando um
            número que a ativação seguinte reaplicaria, retomando a posse que
            ela acabou de largar.

            ``volume=None`` SEM ``soltar`` não registra nada, e a distinção é a
            entrega: "não sei o volume" e "ela largou o volume" são coisas
            opostas, e confundi-las apagaria a seção do perfil num gesto de
            mudo que só não tinha leitura ainda.
            """

            def _feito(resultado: Any) -> bool:
                if resultado is not None and (soltar or volume is not None):
                    registrar_alto_falante_no_rascunho(
                        self._dono_do_rascunho,
                        volume=None if soltar else volume,
                        muted=muted,
                        rota=rota,
                        # POR-UNIDADE-01: DE QUEM foi o gesto. O bloco já manda
                        # este mesmo `uniq` no `speaker.set` — o que faltava era
                        # o rascunho saber. Quem decide se isso vira override da
                        # peça ou opinião da casa é o escritor único (ver
                        # `registrar_alto_falante_no_rascunho`); o card só diz
                        # a verdade sobre onde a mão dela encostou.
                        uniq=self._uniq,
                    )
                return self._on_som_de_confirmacao(resultado)

            return _feito

        def _volume_lido_do_daemon(self) -> int | None:
            """A preferência de volume que o daemon publica, ou None.

            É ela que entra no rascunho nos gestos que NÃO carregam número (o
            mudo e o canal). O valor do controle deslizante não serve: fora da
            faixa útil do registrador a volta pela tela não é a identidade
            (200 desenha 100 % e volta 102), e registrá-lo baixaria o volume
            guardado dela por efeito colateral de outro gesto.
            """
            lido = self._speaker_lido
            return None if lido is None else lido[0]

        def _on_speaker_mudo_clicado(self, _botao: Any) -> None:
            """Silenciar/Ativar — nunca a PRIMEIRA escrita (ver `acao_speaker_mudo`)."""
            acao = self._speaker_acao_mudo
            if acao is None or not acao.sensivel or acao.muted is None:
                return
            if self._som_sem_alvo():
                return
            muted = acao.muted
            uniq = self._uniq

            def _pedir() -> Any:
                ok = ipc_bridge.speaker_set(muted=muted, uniq=uniq)
                return self._confirmar_com_som() if ok else None

            # O mudo é MODULAÇÃO de um volume conhecido (o backend recusa mudo
            # sem volume, SOM-02/E3), e o botão só é sensível quando esse
            # volume existe. O par volume+mudo entra junto no rascunho porque
            # é o único par que o esquema do perfil aceita.
            ipc_bridge.run_in_thread(
                _pedir,
                self._confirmado_pelo_daemon(
                    volume=self._volume_lido_do_daemon(), muted=muted
                ),
            )

        def _on_speaker_devolucao_clicada(self, _botao: Any) -> None:
            """Devolver a posse dos bytes de volume (SOM-02, entrega 3)."""
            acao = self._speaker_acao_devolucao
            if acao is None or not acao.sensivel or not acao.release:
                return
            if self._som_sem_alvo():
                return
            uniq = self._uniq

            def _pedir() -> Any:
                ok = ipc_bridge.speaker_set(release=True, uniq=uniq)
                return self._confirmar_com_som() if ok else None

            # `soltar` APAGA a seção do rascunho: devolver a posse é a ausência
            # de opinião, não um valor. Sem isto, o "Salvar Perfil" depois de
            # Soltar guardaria o último número e a ativação seguinte retomaria
            # a posse que ela acabou de largar.
            ipc_bridge.run_in_thread(
                _pedir, self._confirmado_pelo_daemon(soltar=True)
            )

        # ------------------------------------------------------------------
        # Alto-falante: o som que confirma (SOM-04, entrega 1)
        # ------------------------------------------------------------------

        def definir_sink_de_saida(self, sink: str) -> None:
            """O sink de saída DESTE controle, para o som de confirmação.

            Quem resolve "qual sink é de qual controle" é o ``mic_monitor``
            (``escolher_sink``), que já é o leitor de PipeWire da janela e roda
            fora da thread do GTK com cadência própria; quem repassa é a
            ``status_actions``, no tique dos cards. **O card não vai ao sistema
            por conta própria** — um segundo leitor de PipeWire aqui seria a
            mesma classe de defeito dos três escritores de perfil.

            ``""`` é resposta legítima e frequente: o controle está no RÁDIO,
            onde o DualSense não publica placa de som (medido 15/08/2026 — a
            placa segue o transporte). No cabo o ``escolher_sink`` casa placa e
            controle pelo dispositivo USB em que os dois penduram, e responde
            com o sink certo por card. Com "" não se toca.
            """
            self._speaker_sink = sink or ""

        def definir_estado_do_canal(
            self, estado: str, *, regra_instalada: bool | None = None
        ) -> None:
            """O canal deste controle está acordado ou dormindo (e é padrão?).

            SOM-ACORDADO-01, e é a metade "ligar isso a interface" da decisão
            dela. Dois fatos entram por aqui, os dois de fora:

            * ``estado`` — ``"acordado"``, ``"dormindo"`` ou ``""``. O
              vocabulário é o do ``audio_saida`` (:data:`CANAL_ACORDADO` e
              irmãos) e ``""`` é **não sei**: pelo rádio o DualSense não
              publica placa de som nenhuma (medido em 15/08/2026 — a placa
              segue o transporte), e ali não há canal a descrever;
            * ``regra_instalada`` — o drop-in 54 do WirePlumber está no lugar?
              É o que separa "acordado agora, por acaso" de "acordado por
              padrão". ``None`` = ninguém perguntou, e a dica não afirma nem
              um nem outro.

            **O card não vai ao sistema por conta própria**, aqui como no
            ``definir_sink_de_saida``: quem lê o PipeWire é a ``status_actions``,
            uma vez por ciclo, para todos os cards. Um `pactl` por card seria
            quatro por ciclo na mesa dela — e um segundo leitor de PipeWire
            nesta janela é a mesma classe de defeito dos três escritores de
            perfil.

            Só repinta quando algo MUDA: este método é chamado no tique de
            10 Hz dos cards, e `set_text` a 10 Hz num rótulo de moldura é
            trabalho de layout por nada.
            """
            estado = estado or ""
            if (
                estado == self._speaker_canal_estado
                and regra_instalada == self._speaker_regra_do_sono
            ):
                return
            self._speaker_canal_estado = estado
            self._speaker_regra_do_sono = regra_instalada
            # O rótulo da moldura é reescrito a partir do texto que o
            # `_speaker_label` já guarda — ele é o dono do valor, e recompor
            # daqui evita um segundo lugar decidindo o que a moldura diz.
            self._escrever_valor_do_speaker(self._speaker_label.get_text())
            self._aplicar_selo_do_som()

        def _confirmar_com_som(self) -> Any:
            """Toca a confirmação — JÁ na thread worker, nunca na do GTK.

            Chamado de DENTRO do mesmo ``_pedir`` do IPC, e de propósito: o som
            é a confirmação daquele pedido, e emiti-lo antes de o daemon
            responder confirmaria uma coisa que pode não ter acontecido.

            Por que o som existe: o registrador de volume do DualSense não tem
            leitura, e o número que o bloco mostra é o que NÓS mandamos. Sem o
            som não há como saber se a mudança valeu — é o mesmo papel que o
            "bip" de qualquer controle de volume de sistema operacional cumpre,
            aqui por necessidade e não por costume.

            A saída muda da camada 1 entra como argumento porque, com o sink do
            sistema mudo, tocar gastaria um processo para produzir silêncio — e
            ela leria o silêncio como defeito do controle, que é exatamente o
            contrário do que a confirmação existe para dizer.

            **Um som por gesto, não um por pixel.** Três camadas empilhadas, e
            nenhuma delas mora aqui: o repouso de 250ms
            (:data:`_SPEAKER_REPOUSO_MS`) e a deduplicação do mesmo volume, em
            `_enviar_volume_do_controle`, e a trava de um som por vez do
            `audio_saida`, para o caso de o gesto ser mais rápido que o tocador
            (medido: 0,35s de ponta a ponta).
            """
            return audio_saida.tocar_confirmacao(
                self._speaker_sink, saida_muda=self._speaker_saida_muda
            )

        def _on_som_de_confirmacao(self, resultado: Any) -> bool:
            """Guarda o recado do som e repinta o selo (contrato do idle_add).

            ``resultado`` é ``None`` quando o daemon recusou o pedido: aí não
            houve som porque não houve mudança, e não há recado a dar — quem
            responde por um pedido recusado é o tique de 10 Hz, que simplesmente
            não vai mostrar o valor novo.
            """
            recado = getattr(resultado, "recado", "") if resultado is not None else ""
            if recado != self._speaker_recado_do_som:
                self._speaker_recado_do_som = recado
                self._aplicar_selo_do_som()
            return False

        def _aplicar_selo_do_som(self) -> None:
            """A linha de recado do bloco: camada 1, depois o som, depois nada.

            SOM-CANAL-01/E4 (02/08/2026) — decisão dela, olhando a tela:
            *"essa parte do sem som faz sentido continuar na interface? o
            slicer mostra isso"*.

            **O `Sem som` saiu; o `Saída muda` FICOU**, e a diferença é o que
            cada um responde:

            * `Saída muda` é a CAMADA 1 — o sink do controle mudo no PipeWire.
              O controle deslizante NÃO mostra isso, e é justamente a armadilha
              que ela nomeou na sprint: *"volume perfeito num sink mudo no
              PipeWire é trabalho invisível"*. Sem o selo, ela mexe no controle
              deslizante e não sai som, sem saber por quê;
            * `Sem som` era sobre a CONFIRMAÇÃO sonora (falta `paplay`/`pw-play`
              na máquina), e não sobre o som do controle. Além de secundário,
              o rótulo era ambíguo: lia como "o controle está sem som". Ele
              continua existindo na DICA do bloco, que é onde cabe a explicação.

            SOM-04, regra 4: **se não houver como tocar, não finja — e não erre
            calado.** Um clique que promete som e não entrega é pior que nenhum
            som, e a diferença entre "a janela não sabe" e "a janela está
            quebrada" é esta linha existir.

            A prioridade não é arbitrária. ``saída muda`` ganha porque é um fato
            PERSISTENTE do sistema, e porque quando ele vale o motivo da recusa
            do som é exatamente esse — não há colisão entre os dois
            informantes, há a mesma verdade dita uma vez só.

            Reusa o rótulo que a SOM-02 já pôs aqui em vez de acrescentar um
            widget, e a razão é medida: a aba Status abre com 116px de folga em
            1180 e o card mais alto pede 463 de 467. Um rótulo a mais custaria
            uma linha; este custa ZERO, porque só aparece quando tem o que
            dizer — que é a mesma regra que ele já obedecia.

            **O selo é curto e a razão mora na dica do bloco**, e isso também é
            medição: a frase inteira no selo levava o card a 1223px numa janela
            de 1180 (ver :data:`TEXTO_SELO_SEM_SOM`). O desenho é o mesmo que o
            card compacto já usa nos botões — o rótulo diz QUE, a dica diz POR
            QUÊ —, e a dica é o único lugar da interface que não custa pixel.
            """
            # SOM-CANAL-01/E4: o selo mostra SÓ a camada 1. O recado de "não
            # deu para confirmar" continua sendo lido — ele entra na DICA do
            # bloco, logo abaixo, e é de lá que ela o lê quando quiser saber
            # por que o bipe não tocou.
            #
            # SOM-ACORDADO-01 acrescenta o TERCEIRO informante, e a prioridade
            # continua sendo a mesma regra: ganha o fato que explica o
            # silêncio ANTES do outro. Uma saída muda cala o som venha o canal
            # de onde vier; um canal dormindo só come o começo. Dizer as duas
            # coisas na mesma linha seria trocar um alarme por dois avisos.
            recado = self._speaker_recado_do_som
            dormindo = self._speaker_canal_estado == SUFIXO_CANAL_DORMINDO
            if self._speaker_saida_muda is True:
                texto = TEXTO_SELO_SAIDA_MUDA
            elif dormindo:
                texto = TEXTO_SELO_CANAL_DORMINDO
            else:
                texto = ""
            if texto:
                self._speaker_selo_saida.set_text(texto)
                self._speaker_selo_saida.show()
            else:
                self._speaker_selo_saida.hide()
            # A dica do BLOCO carrega o porquê. Ela nunca perde a linha de
            # explicação da SOM-02/E5: o recado ENTRA embaixo dela, porque as
            # duas respondem a perguntas diferentes ("por que o normal aqui é
            # não ajustado" e "por que não deu para confirmar agora").
            #
            # SOM-ACORDADO-01: a primeira linha passou a depender da POSSE. A
            # `DICA_BLOCO_SPEAKER` descreve o estado SEM posse — *"o volume é
            # do firmware do controle"* —, e com o daemon mandando o volume ela
            # passaria a mentir na tela justamente no estado que esta leva
            # torna o normal.
            partes = [
                DICA_BLOCO_SPEAKER
                if self._speaker_lido is None
                else DICA_SPEAKER_POSSE_NOSSA
            ]
            partes.extend(self._frases_do_canal())
            if recado and self._speaker_saida_muda is not True:
                partes.append(recado)
            caixa = getattr(self, "_speaker_box", None)
            if caixa is not None:
                caixa.set_tooltip_text("\n\n".join(partes))

        def _frases_do_canal(self) -> list[str]:
            """As frases do canal na dica do bloco: o estado, e se é o padrão.

            SOM-ACORDADO-01. Sem leitura do canal não sai frase nenhuma — o
            silêncio da dica é a resposta honesta para o controle no rádio, que
            não tem placa de som para acordar.

            A frase do PADRÃO é condicionada à regra estar instalada, e a
            condição é a metade que importa: um nó pode estar acordado por
            acaso (alguém acabou de tocar algo) com o drop-in fora do lugar, e
            chamar isso de "é o padrão" seria a tela dando por curado o que só
            está momentaneamente de pé — mesma regra que o `texto_do_sono` do
            `audio_saida` já aplica do lado da leitura.
            """
            estado = self._speaker_canal_estado
            if not estado:
                return []
            frases = [
                DICA_CANAL_DORMINDO
                if estado == SUFIXO_CANAL_DORMINDO
                else DICA_CANAL_ACORDADO
            ]
            if self._speaker_regra_do_sono is True:
                frases.append(DICA_CANAL_E_PADRAO)
            elif self._speaker_regra_do_sono is False:
                frases.append(DICA_CANAL_SEM_A_REGRA)
            return frases

        def _montar_capsula_stick(
            self, titulo: str, rotulo_stick: str, tamanho: int
        ) -> tuple[Any, StickPreviewGtk, Any, Any]:
            caps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            caps.set_halign(Gtk.Align.CENTER)
            caps.set_valign(Gtk.Align.START)
            label_titulo = Gtk.Label()
            label_titulo.set_markup(titulo)
            label_titulo.set_xalign(0.5)
            # A quebra é ESCRITA no texto e o `line_wrap` fica DESLIGADO.
            #
            # STATUS-SIMETRIA-02, defeito 1: com a quebra automática, quantas
            # linhas cada rótulo ocupava dependia da largura sobrando e do
            # tamanho da fonte — "Analógico Esquerdo (L3)" caía em 3 linhas e
            # "Analógico Direito (R3)" em 2 no mesmo card, e ela viu isso na
            # tela. Agora os dois têm DUAS linhas por construção, em qualquer
            # largura e em qualquer escala de fonte. O peso visual continua o
            # dos módulos vizinhos (`dim-label`): são pares na mesma faixa.
            label_titulo.set_line_wrap(False)
            label_titulo.set_justify(Gtk.Justification.CENTER)
            label_titulo.get_style_context().add_class("dim-label")
            # STATUS-SIMETRIA-01 — a CURA do degrau de 20px entre os dois
            # analógicos. "Analógico Esquerdo (L3)" quebra em 3 linhas e
            # "Analógico Direito (R3)" em 2; sem nada amarrando, essa diferença
            # de altura de RÓTULO empurrava o desenho da esquerda 20px para
            # baixo. O SizeGroup vertical dá aos dois títulos a altura do maior,
            # e o alinhamento passa a não depender do texto: trocar uma palavra
            # do rótulo amanhã não traz o degrau de volta. Encurtar o texto
            # seria cinto de segurança, não cura.
            self._grupo_titulos_stick.add_widget(label_titulo)
            caps.pack_start(label_titulo, False, False, 0)
            preview = StickPreviewGtk(label=rotulo_stick)
            preview.set_size_request(tamanho, tamanho)
            slot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            slot.set_halign(Gtk.Align.CENTER)
            slot.pack_start(preview, False, False, 0)
            caps.pack_start(slot, False, False, 0)
            label_xy = Gtk.Label()
            label_xy.set_markup(_markup_xy(128, 128))
            label_xy.set_xalign(0.5)
            label_xy.set_justify(Gtk.Justification.CENTER)
            # O degrau de tamanho e a família mono saem da escala do CSS, não
            # de atributo de Pango — é o que deixa a escala global alcançá-los.
            label_xy.get_style_context().add_class("hefesto-valor-mono")
            caps.pack_start(label_xy, False, False, 0)
            return caps, preview, label_titulo, label_xy

        def _montar_sticks(self) -> Any:
            """Os dois analógicos, lado a lado, dentro da faixa de baixo."""
            tamanho = (
                STICK_SIZE_COMPACT if self._compact else STICK_SIZE_SINGLE
            )
            # O grupo é POR CARD: amarrar títulos de cards diferentes faria um
            # controle mudar de layout porque o vizinho apareceu.
            self._grupo_titulos_stick = Gtk.SizeGroup(
                mode=Gtk.SizeGroupMode.VERTICAL
            )
            # Caixa e não mais `Gtk.Grid` homogêneo: a grade dava às duas
            # cápsulas a largura da MAIOR, e a maior era a do rótulo. Aqui cada
            # uma pede o próprio desenho.
            faixa = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=self._espaco,
            )

            caps_esq, stick_esq, titulo_esq, xy_esq = (
                self._montar_capsula_stick(
                    _TITULO_STICK_ESQ, ROTULO_STICK_ESQ, tamanho
                )
            )
            self._stick_left = stick_esq
            self._stick_left_title = titulo_esq
            self._stick_left_xy = xy_esq
            faixa.pack_start(caps_esq, False, False, 0)

            caps_dir, stick_dir, titulo_dir, xy_dir = (
                self._montar_capsula_stick(
                    _TITULO_STICK_DIR, ROTULO_STICK_DIR, tamanho
                )
            )
            self._stick_right = stick_dir
            self._stick_right_title = titulo_dir
            self._stick_right_xy = xy_dir
            faixa.pack_start(caps_dir, False, False, 0)
            self._faixa_sticks = faixa
            return faixa

        def _montar_glyphs(self) -> Any:
            """Grid 4x4 dos 16 botões — o bloco da direita na linha de baixo.

            O tamanho sai de `glyph_size()`, lido AQUI (na montagem) e não do
            módulo: card montado com a escala 3 nasce com glifo de 36px, e com
            a escala 0, de 24px.

            SOM-01 — *"aumentar e espaçar mais os botões do controle tipo x
            quadrado bola e triângulo e afins"*. No card de UM controle o
            tamanho passa por `glyph_size_unico` (36 -> 58px na escala desta
            casa) e o respiro sobe de 2 para 10px: o grid sai de 150x150 para
            262x262. No compacto os dois números são os de hoje, e o motivo
            medido está em `glyph_size_unico`.
            """
            tamanho = glyph_size() if self._compact else glyph_size_unico()
            espaco = (
                GLYPH_ESPACO_COMPACTO if self._compact else GLYPH_ESPACO_UNICO
            )
            self._glyph_size = tamanho
            glyph_grid = Gtk.Grid()
            glyph_grid.set_row_spacing(espaco)
            glyph_grid.set_column_spacing(espaco)
            glyph_grid.set_halign(Gtk.Align.CENTER)
            glyph_grid.set_valign(Gtk.Align.CENTER)
            for row, linha in enumerate(GRID_BOTOES):
                for col, nome in enumerate(linha):
                    tooltip = BUTTON_GLYPH_LABELS.get(nome, nome)
                    glyph = ButtonGlyph(
                        nome, size=tamanho, tooltip_pt_br=tooltip
                    )
                    self._glyphs[nome] = glyph
                    glyph_grid.attach(glyph, col, row, 1, 1)
            self._glyph_grid = glyph_grid
            return glyph_grid

        # ------------------------------------------------------------------
        # Seções do update (cada uma com o próprio diff)
        # ------------------------------------------------------------------

        def _update_titulo(
            self, entry: dict[str, Any], state_global: dict[str, Any]
        ) -> None:
            titulo = titulo_do_card(entry)
            if titulo != self._last_titulo:
                self._last_titulo = titulo
                self._title_label.set_text(titulo)
            # QUEM-É-QUEM-01: a dica tem diff PRÓPRIO — ela muda por
            # motivo diferente do título (um jogador promovido não renomeia
            # card nenhum), e pendurá-la no diff do título a deixaria velha.
            dica = dica_do_titulo(entry, state_global)
            if dica != self._last_dica_titulo:
                self._last_dica_titulo = dica
                self._title_label.set_tooltip_text(dica)

        def _update_bateria(self, entry: dict[str, Any]) -> None:
            bateria = _int_ou_none(entry.get("battery_pct"))
            if bateria == self._last_battery:
                return
            self._last_battery = bateria
            if bateria is None:
                self._battery_bar.set_fraction(0.0)
                texto = "— %"
            else:
                self._battery_bar.set_fraction(
                    max(0, min(100, bateria)) / 100
                )
                texto = f"{bateria} %"
            # O `set_text` da barra é chamado SEMPRE, inclusive no card único
            # onde ela não desenha texto nenhum: ele é o dono do valor e é o
            # que `get_text()` — e os testes — leem. Este método é o único
            # lugar que espelha esse valor no rótulo ao lado, pelo mesmo
            # motivo que a `status_actions._set_battery_text` é único lá:
            # dois escritores derivam, e esta casa já pagou por isso.
            self._battery_bar.set_text(texto)
            if self._battery_pct_label is not None:
                self._battery_pct_label.set_text(texto)

        def _update_lightbar(
            self, entry: dict[str, Any], state_global: dict[str, Any]
        ) -> None:
            cru = _rgb3(entry.get("lightbar_rgb"))
            rotulo, base = rotulo_lightbar(entry, state_global)
            accent = ensure_min_contrast(
                base if base is not None else ACCENT_NEUTRO
            )
            chave = (cru, rotulo, accent)
            if chave == self._last_lightbar:
                return
            self._last_lightbar = chave

            if cru != self._swatch_rgb:
                self._swatch_rgb = cru
                self._swatch.queue_draw()

            self._aplicar_lightbar_bar(cru)

            if rotulo:
                self._lightbar_label.set_text(rotulo)
                self._lightbar_label.show()
            else:
                self._lightbar_label.hide()

            if accent != self._accent:
                self._accent = accent
                self._accent_hex = rgb_para_hex(accent)
                # Os widgets já cacheiam por hex — repetir cor é no-op neles.
                self._stick_left.set_accent(accent)
                self._stick_right.set_accent(accent)
                for glyph in self._glyphs.values():
                    glyph.set_accent(accent)
                tintar_progressbar(self._l2_bar, accent)
                tintar_progressbar(self._r2_bar, accent)
                self._pintar_titulos_sticks()

        def _aplicar_lightbar_bar(self, cru: RGB | None) -> None:
            """Bloco "Lightbar" da linha de baixo: a faixa e o hex, ou nada.

            Cor desconhecida (o caso do 0,0,0 sem escrita nossa) esconde o
            bloco em vez de pintar preto: "não sei" e "apagada" não podem
            desenhar a mesma faixa.
            """
            if cru is None:
                self._lightbar_bar.set_cor(None)
                self._lightbar_box.hide()
                return
            self._lightbar_bar.set_cor(cru)
            self._lightbar_hex.set_text(rgb_para_hex(cru))
            self._lightbar_box.show()

        def _update_degradacao(self, entry: dict[str, Any]) -> None:
            texto = texto_degradacao(entry)
            if texto == self._last_degradacao:
                return
            self._last_degradacao = texto
            if texto:
                self._degradacao_badge.set_text(texto)
                self._degradacao_badge.show()
            else:
                self._degradacao_badge.hide()

        def _update_motion(
            self, entry: dict[str, Any], state_global: dict[str, Any]
        ) -> None:
            texto = texto_motion(entry, state_global)
            if texto == self._last_motion:
                return
            self._last_motion = texto
            # O texto é ESCRITO sempre — ele é o dono do valor e é o que os
            # testes leem. Quem só aparece no card compacto é o widget: no
            # card único o giroscópio é dito pela linha da verdade, que o
            # contém e amplia (ver `_montar_ui`), e mostrar os dois seria o
            # card falando duas vezes a mesma coisa.
            if texto:
                self._motion_label.set_text(texto)
            if self._motion_label.get_parent() is None:
                return
            if texto:
                self._motion_label.show()
            else:
                self._motion_label.hide()

        def _update_verdade(
            self, entry: dict[str, Any], state_global: dict[str, Any]
        ) -> None:
            """PAINEL-DA-VERDADE-01: a linha do que chega ao jogo agora."""
            if self._verdade_label is None:
                return  # card compacto: a linha é do card único
            texto = resumo_do_que_chega_ao_jogo(entry, state_global)
            if texto == self._last_verdade:
                return
            self._last_verdade = texto
            if texto:
                self._verdade_label.set_text(texto)
                self._verdade_label.show()
            else:
                self._verdade_label.hide()

        # ------------------------------------------------------------------
        # Sensores (S2) — cada um some inteiro quando não há dado
        # ------------------------------------------------------------------

        def _update_gyro(self, inputs: Any) -> None:
            valores = gyro_do_inputs(inputs)
            if valores == self._last_gyro:
                return
            self._last_gyro = valores
            if valores is None:
                self._gyro_bars.limpar()
                self._gyro_box.hide()
                return
            self._gyro_bars.set_valores(*valores)
            self._gyro_box.show()

        def _update_touchpad(self, inputs: Any) -> None:
            dados = touchpad_do_inputs(inputs)
            if dados == self._last_touch:
                return
            self._last_touch = dados
            if dados is None:
                self._touch_view.set_toque(None)
                self._touch_box.hide()
                return
            tocando, fx, fy = dados
            self._touch_view.set_toque((fx, fy) if tocando else None)
            self._touch_label.set_text(texto_toques(1 if tocando else 0))
            self._touch_box.show()

        def _update_mic(self, mic: Any, transporte: str = "") -> None:
            nivel = getattr(mic, "nivel", None) if mic is not None else None
            muted = getattr(mic, "muted", None) if mic is not None else None
            chave = (nivel, muted, transporte)
            if chave == self._last_mic:
                return
            self._last_mic = chave
            if nivel is None:
                # A onda vai embora — reaparecer com o traço da última captura
                # seria mostrar áudio que não está mais entrando —, mas o
                # BLOCO fica (MIC-PRESENTE-01).
                self._mic_meter.limpar()
                self._aplicar_estado_mic(None, presente=False)
                return
            self._mic_meter.set_nivel(float(nivel))
            self._aplicar_estado_mic(muted, presente=True)

        def _update_mic_botao(self, entry: dict[str, Any]) -> None:
            """Rótulo/sensibilidade do botão a partir de ``entry['audio']``.

            Diffado como o resto: o tick é de 10 Hz e o estado do microfone
            muda por gesto humano.
            """
            acao = acao_mic(entry)
            if acao == self._mic_acao:
                return
            self._aplicar_acao_mic(acao)

        def _aplicar_acao_mic(self, acao: AcaoMic) -> None:
            self._mic_acao = acao
            self._mic_botao_rotulo.set_text(acao.rotulo)
            self._mic_botao.set_sensitive(acao.sensivel)
            self._mic_botao.set_tooltip_text(acao.dica)

        def _aplicar_estado_mic(
            self, muted: Any, *, presente: bool
        ) -> None:
            """Diz o estado do microfone em palavras — sem nunca esconder.

            Quatro estados, um espaço só (a tabela da MIC-PRESENTE-01):
            captando com mute lido vira o selo colorido ``ATIVO``/``MUDO``;
            captando sem mute lido vira ``captando`` apagado (cravar "ATIVO"
            sem ter lido o mute seria afirmar que o microfone está aberto por
            chute); sem sinal nenhum vira ``sem sinal``, também apagado.
            """
            selo = selo_mic(muted) if presente else None
            contexto = self._mic_selo.get_style_context()
            if selo is None:
                contexto.add_class("dim-label")
                self._mic_selo.set_text(
                    TEXTO_MIC_SEM_MUTE if presente else TEXTO_MIC_AUSENTE
                )
                return
            contexto.remove_class("dim-label")
            texto, fundo, cor = selo
            self._mic_selo.set_markup(
                f'<span background="{fundo}" foreground="{cor}">'
                f" {texto} </span>"
            )

        def _update_speaker(self, entry: dict[str, Any], mic: Any = None) -> None:
            dados = speaker_do_entry(entry)
            # SOM-02/E4: guardado ANTES do diff, e fora dele. O que o mudo e
            # o canal registram no rascunho é esta LEITURA — a preferência que
            # o daemon publica —, e não o número do controle deslizante, que
            # fora da faixa útil do registrador não volta igual.
            self._speaker_lido = dados
            saida_muda = saida_muda_do_entry(entry, mic)
            chave = (dados, saida_muda)
            if chave == self._last_speaker:
                return
            self._last_speaker = chave
            self._aplicar_estado_speaker(dados, saida_muda=saida_muda)
            self._aplicar_acoes_speaker(
                acao_speaker_mudo(entry), acao_speaker_devolucao(entry)
            )

        def _aplicar_estado_speaker(
            self,
            dados: tuple[int, bool | None] | None,
            *,
            saida_muda: bool | None = None,
        ) -> None:
            """Volume do alto-falante, ou a frase que diz que ninguém ajustou.

            O bloco NUNCA se esconde: some é o que ela leu como "não tem a
            parte do som".

            O controle deslizante acompanha a LEITURA (é o mesmo estado, e é
            de onde o próximo gesto dela parte), com duas guardas: não repinta
            embaixo da mão dela (``_speaker_arrastando``) e não dispara pedido
            ao se mover (``_speaker_pintando``). Sem posse ele volta ao
            repouso, no zero — não ao meio, que desenharia 50 % ao lado de um
            rótulo dizendo que ninguém ajustou nada.
            """
            # SOM-02/E5, item 4: o selo aparece SÓ quando a leitura da camada 1
            # disser que o sink está mudo. Sem leitura, nada.
            #
            # SOM-04: quem decide o texto e a visibilidade passou a ser o
            # `_aplicar_selo_do_som`, porque o rótulo ganhou um SEGUNDO
            # informante — o motivo pelo qual a última confirmação sonora não
            # saiu. A camada 1 continua tendo prioridade; a razão está lá.
            self._speaker_saida_muda = saida_muda
            self._aplicar_selo_do_som()
            if dados is None:
                self._speaker_bar.set_volume(0.0, None)
                self._escrever_valor_do_speaker(TEXTO_SPEAKER_SEM_DADO)
                self._pintar_escala_do_speaker(0)
                # Sem posse, o próximo gesto dela é a PRIMEIRA escrita da
                # sessão: esquecer o último valor mandado é o que impede a
                # guarda anti-rajada de engolir esse gesto.
                self._speaker_volume_enviado = None
                return
            volume, muted = dados
            self._speaker_bar.set_volume(fracao_do_volume(volume), muted)
            self._escrever_valor_do_speaker(texto_volume(volume, muted))
            self._pintar_escala_do_speaker(percentual_do_volume(volume))

        def _escrever_valor_do_speaker(self, texto: str) -> None:
            """O valor do alto-falante, no rótulo E no título da moldura.

            SOM-ROTA-NO-CARD-01. O `_speaker_label` continua existindo e sendo
            escrito: ele é o dono do texto, é o que os testes leem, e no card
            COMPACTO ele é o que aparece na tela. O que mudou é o card único —
            lá o rótulo saiu do empacotamento para o botão da rota caber no
            lugar dele, e quem MOSTRA o valor passou a ser o rótulo da
            moldura, que já existia e não custa pixel nenhum.

            O título é montado aqui, e não guardado pronto, porque
            "Alto-falante" é o nome do bloco e tem de sobreviver a qualquer
            valor — inclusive a `None`, que é como o card nasce.

            CARD-ÚNICO-01, entrega 2 — *"remover o não ajustado"*. O sufixo
            some no estado SEM DADO e continua no estado com valor
            (`Alto-falante · 71 %`). É a leitura literal do pedido, e a que
            custa zero: das duas opções escritas na sprint, a outra (tirar o
            sufixo sempre) obrigaria o valor a achar um terceiro lugar, e os
            três candidatos já foram medidos e todos cobram pixel — o rótulo
            de valor deste bloco foi justamente quem cedeu o lugar para o
            botão da rota, na leva anterior.

            O `_speaker_label` continua recebendo o texto CRU, sem exceção:
            ele é o dono do valor e é o que os testes leem. Quem decide o que
            aparece na moldura é só a linha de baixo.
            """
            self._speaker_label.set_text(texto)
            titulo = getattr(self, "_speaker_titulo", None)
            if titulo is not None and hasattr(titulo, "set_text"):
                titulo.set_text(self._titulo_do_speaker(texto))

        def _titulo_do_speaker(self, texto: str) -> str:
            """O rótulo da moldura: nome · volume · estado do canal.

            SOM-ACORDADO-01. Os dois sufixos entram do mesmo jeito e pela mesma
            razão — são LEITURA, e o rótulo da moldura é o único lugar deste
            bloco que custa zero pixel de altura (a medição está no bloco de
            comentários de :data:`SUFIXO_CANAL_ACORDADO`).

            Cada um some sozinho quando não há o que dizer, e os dois somem
            juntos no card recém-nascido:

            * sem posse do volume, o nome fica sozinho (CARD-ÚNICO-01, decisão
              dela: *"remover o não ajustado"*);
            * sem leitura do canal — o caso do rádio, em que não há placa de
              som —, não entra sufixo nenhum. "" é **não sei**, e escrever
              "acordado" a partir de ausência seria prometer que o som sai
              inteiro num controle que não tem por onde tocá-lo.
            """
            partes = [TITULO_SPEAKER]
            if texto != TEXTO_SPEAKER_SEM_DADO:
                partes.append(texto)
            estado = getattr(self, "_speaker_canal_estado", "")
            if estado:
                partes.append(estado)
            return " · ".join(partes)

        def _pintar_escala_do_speaker(self, percentual: int) -> None:
            """Move o cursor SEM disparar pedido (e nunca durante o arrasto)."""
            if self._speaker_arrastando:
                return
            self._speaker_pintando = True
            try:
                self._speaker_escala.set_value(percentual)
            finally:
                self._speaker_pintando = False

        def _aplicar_acoes_speaker(
            self, mudo: AcaoSpeaker, devolucao: AcaoSpeaker
        ) -> None:
            self._speaker_acao_mudo = mudo
            self._speaker_acao_devolucao = devolucao
            for botao, acao in (
                (self._speaker_botao_mudo, mudo),
                (self._speaker_botao_devolver, devolucao),
            ):
                botao._rotulo_hefesto.set_text(acao.rotulo)
                botao.set_sensitive(acao.sensivel)
                botao.set_tooltip_text(acao.dica)
            # Dica do bloco: a linha de sempre e, sem posse, o CAMINHO. Botão
            # insensível não recebe evento e por isso não mostra dica própria
            # no GTK3 — a explicação de "sem dado" ficaria invisível justamente
            # no estado em que ela é necessária.
            self._speaker_box.set_tooltip_text(
                DICA_BLOCO_SPEAKER
                if mudo.sensivel
                else f"{DICA_BLOCO_SPEAKER} ({DICA_SPEAKER_SEM_DADO})"
            )

        # ------------------------------------------------------------------
        # GUARDA-SEM-ENDEREÇO-01 — sem MAC, o som deste card não manda em nada
        # ------------------------------------------------------------------

        def _pecas_que_escrevem_som(self) -> tuple[Any, ...]:
            """As peças de COMANDO do som — as que viajam com o ``uniq``.

            A leitura fica de fora de propósito (a barra, o medidor, os
            rótulos): ela conta o que o daemon publicou sobre ESTE controle e
            continua verdadeira sem endereço nenhum. Quem mente sem endereço é
            o comando, e é só ele que a guarda desliga.
            """
            pecas: list[Any] = [
                self._mic_botao,
                # MIC-VOLUME-01 — o controle deslizante do microfone ocupa aqui
                # a vaga que era do interruptor "Pelo rádio" (saiu em 16/08), e
                # ele PRECISA da vaga: `mic.volume.set` sem `uniq` cai no
                # controle primário, que é o microfone de outra pessoa na mesa
                # cheia. A tranca de dentro do gesto (`_enviar_volume_do_mic`)
                # é a segunda; esta é a que ela VÊ.
                self._mic_escala,
                self._speaker_escala,
                self._speaker_botao_mudo,
                self._speaker_botao_devolver,
            ]
            # O seletor de canal só existe no card de UM controle (no compacto
            # a linha não cabe), e por isso é buscado e não assumido.
            canal = getattr(self, "_speaker_canal", None)
            if canal is not None:
                pecas.append(canal)
            return tuple(pecas)

        def _update_guarda_de_audio(self) -> None:
            """Desliga (ou devolve) o som do card conforme haja endereço.

            **O estado ligado é reaplicado a cada tique, e isso não é
            desperdício.** Os `_update_` do som são diffados: qualquer mudança
            no que o daemon publica sobre este controle os faz repintar a
            sensibilidade das peças, e sem a reaplicação um `speaker` que
            aparecesse no meio da sessão devolveria os botões por baixo da
            guarda. `set_sensitive` com o mesmo valor é no-op no GTK.

            **A volta é diffada**, porque é ela que precisa acontecer UMA vez:
            quem sabe o estado certo de cada peça são as ações já calculadas
            (`_aplicar_acao_mic`, `_aplicar_acoes_speaker`), e reaplicá-las é a
            única forma de devolver a sensibilidade sem a guarda ter de
            adivinhá-la. Os dois controles deslizantes não têm ação calculada —
            eles só dependem do endereço, e por isso voltam direto.
            """
            if self._uniq is None:
                for peca in self._pecas_que_escrevem_som():
                    peca.set_sensitive(False)
                # A dica vai na MOLDURA dos dois blocos: peça insensível não
                # recebe evento no GTK3, e a dica dela não apareceria.
                self._mic_box.set_tooltip_text(DICA_AUDIO_SEM_ENDERECO)
                self._speaker_box.set_tooltip_text(DICA_AUDIO_SEM_ENDERECO)
                self._audio_aviso.show()
                self._audio_sem_endereco = True
                return
            if self._audio_sem_endereco is False:
                return
            self._audio_sem_endereco = False
            self._audio_aviso.hide()
            self._mic_box.set_tooltip_text(None)
            self._aplicar_acao_mic(self._mic_acao or acao_mic(None))
            self._mic_escala.set_sensitive(True)
            self._speaker_escala.set_sensitive(True)
            canal = getattr(self, "_speaker_canal", None)
            if canal is not None:
                canal.set_sensitive(True)
            self._aplicar_acoes_speaker(
                self._speaker_acao_mudo or acao_speaker_mudo(None),
                self._speaker_acao_devolucao or acao_speaker_devolucao(None),
            )

        def _som_sem_alvo(self) -> bool:
            """A guarda vista de DENTRO do gesto — a segunda tranca.

            Peça insensível não recebe clique **da mão dela**, e isso basta
            para a tela. Não basta para o código: um `set_active` de teste, um
            gesto que chegou antes do `update` e um repouso de volume já
            armado passam por cima da sensibilidade e chegam ao IPC do mesmo
            jeito. Aqui o pedido morre antes de virar byte no controle errado.
            """
            return self._uniq is None

        # ------------------------------------------------------------------
        # Inputs ao vivo (a 10 Hz — tudo diffado)
        # ------------------------------------------------------------------

        def _update_inputs(self, inputs: Any) -> None:
            if not isinstance(inputs, dict):
                # Sem leitor para este controle (co-op desmontado, Nativo,
                # emulação off): "—" honesto, nunca o último valor congelado.
                self._mostrar_sem_leitor()
                return
            if self._sem_leitor is not False:
                self._sem_leitor = False
                self._sem_leitor_label.hide()
                self._inputs_area.show()

            l2 = int(inputs.get("l2_raw", 0))
            r2 = int(inputs.get("r2_raw", 0))
            if l2 != self._last_l2:
                self._l2_bar.set_fraction(l2 / 255)
                self._l2_bar.set_text(f"{l2} / 255")
                self._last_l2 = l2
            if r2 != self._last_r2:
                self._r2_bar.set_fraction(r2 / 255)
                self._r2_bar.set_text(f"{r2} / 255")
                self._last_r2 = r2

            lx = int(inputs.get("lx", 128))
            ly = int(inputs.get("ly", 128))
            rx = int(inputs.get("rx", 128))
            ry = int(inputs.get("ry", 128))
            if lx != self._last_lx or ly != self._last_ly:
                self._stick_left.update(lx, ly)
                self._stick_left_xy.set_markup(
                    _markup_xy(lx, ly)
                )
                self._last_lx = lx
                self._last_ly = ly
            if rx != self._last_rx or ry != self._last_ry:
                self._stick_right.update(rx, ry)
                self._stick_right_xy.set_markup(
                    _markup_xy(rx, ry)
                )
                self._last_rx = rx
                self._last_ry = ry

            buttons_raw = inputs.get("buttons") or []
            buttons_pressed = frozenset(str(b) for b in buttons_raw)
            self._refresh_glyphs(buttons_pressed, l2, r2)

        def _refresh_glyphs(
            self, buttons_pressed: frozenset[str], l2_raw: int, r2_raw: int
        ) -> None:
            l2_lit = l2_raw > L2_R2_THRESHOLD
            r2_lit = r2_raw > L2_R2_THRESHOLD
            if (
                buttons_pressed == self._last_buttons
                and l2_lit == self._last_l2_lit
                and r2_lit == self._last_r2_lit
            ):
                return
            self._last_buttons = buttons_pressed
            self._last_l2_lit = l2_lit
            self._last_r2_lit = r2_lit

            efetivos: dict[str, bool] = {
                nome: (nome in buttons_pressed) for nome in ALL_BUTTONS
            }
            efetivos["l2"] = l2_lit
            efetivos["r2"] = r2_lit
            # BUG-GLYPH-SHARE-NAME-MISMATCH-01: o daemon emite "create"
            # (BTN_SELECT), mas o glyph/asset chama-se "share".
            efetivos["share"] = ("share" in buttons_pressed) or (
                "create" in buttons_pressed
            )
            for nome, glyph in self._glyphs.items():
                glyph.set_pressed(efetivos.get(nome, False))

            l3 = "l3" in buttons_pressed
            r3 = "r3" in buttons_pressed
            if l3 != self._l3_pressed or r3 != self._r3_pressed:
                self._l3_pressed = l3
                self._r3_pressed = r3
                self._stick_left.set_l3_pressed(l3)
                self._stick_right.set_l3_pressed(r3)
                self._pintar_titulos_sticks()

        def _pintar_titulos_sticks(self) -> None:
            """Títulos dos sticks: accent do CONTROLE quando pressionados."""
            self._pintar_titulo_stick(
                self._stick_left_title, _TITULO_STICK_ESQ, self._l3_pressed
            )
            self._pintar_titulo_stick(
                self._stick_right_title, _TITULO_STICK_DIR, self._r3_pressed
            )

        def _pintar_titulo_stick(
            self, label: Any, texto: str, pressionado: bool
        ) -> None:
            if pressionado:
                label.set_markup(
                    f'<span foreground="{self._accent_hex}">{texto}</span>'
                )
            else:
                label.set_markup(texto)

        def _mostrar_sem_leitor(self) -> None:
            if self._sem_leitor is True:
                return
            self._sem_leitor = True
            self._inputs_area.hide()
            self._sem_leitor_label.show()
            self._reset_inputs_render()

        def _reset_inputs_render(self) -> None:
            """Volta a área de inputs ao repouso e invalida os caches.

            Caches em None forçam o repaint completo no próximo tick com
            leitor — sem isso, um valor igual ao de antes da queda seria
            pulado pelo diff e a barra ficaria stale.
            """
            self._l2_bar.set_fraction(0.0)
            self._l2_bar.set_text("0 / 255")
            self._r2_bar.set_fraction(0.0)
            self._r2_bar.set_text("0 / 255")
            self._stick_left.update(128, 128)
            self._stick_left.set_l3_pressed(False)
            self._stick_right.update(128, 128)
            self._stick_right.set_l3_pressed(False)
            self._stick_left_xy.set_markup(
                _markup_xy(128, 128)
            )
            self._stick_right_xy.set_markup(
                _markup_xy(128, 128)
            )
            for glyph in self._glyphs.values():
                glyph.set_pressed(False)
            self._l3_pressed = False
            self._r3_pressed = False
            self._pintar_titulos_sticks()
            self._last_l2 = None
            self._last_r2 = None
            self._last_lx = None
            self._last_ly = None
            self._last_rx = None
            self._last_ry = None
            self._last_buttons = None
            self._last_l2_lit = None
            self._last_r2_lit = None
            # Sensores voltam ao "não sei" junto com o resto: um giroscópio
            # congelado no último valor seria movimento inventado, e o
            # medidor do mic parado, silêncio inventado.
            self._gyro_bars.limpar()
            self._gyro_box.hide()
            self._touch_view.set_toque(None)
            self._touch_box.hide()
            # Microfone e alto-falante voltam ao estado apagado — e NÃO se
            # escondem: o espaço deles é reservado em todos os quatro estados
            # (MIC-PRESENTE-01), inclusive neste, o de controle sem leitor.
            self._mic_meter.limpar()
            self._aplicar_estado_mic(None, presente=False)
            # O BOTÃO também volta ao "não sei": sem leitor não há como saber
            # se o firmware está mudo, e um botão que continuasse dizendo
            # "Silenciar" mandaria o oposto do estado real no primeiro clique.
            self._aplicar_acao_mic(acao_mic(None))
            # O alto-falante volta ao "não sei" pelo mesmo motivo: sem leitor
            # não há posse conhecida, e os dois botões voltam a insensíveis —
            # um `Silenciar` clicável sem volume conhecido é a armadilha 2.
            self._aplicar_estado_speaker(None)
            self._aplicar_acoes_speaker(
                acao_speaker_mudo(None), acao_speaker_devolucao(None)
            )
            self._last_gyro = _SENTINELA
            self._last_touch = _SENTINELA
            self._last_mic = _SENTINELA
            self._last_speaker = _SENTINELA

        # ------------------------------------------------------------------
        # Swatch (cor CRUA — decisão D8: a identidade da cor fica aqui)
        # ------------------------------------------------------------------

        def _on_draw_swatch(self, widget: Any, ctx: Any) -> bool:
            largura = widget.get_allocated_width()
            altura = widget.get_allocated_height()
            rgb = self._swatch_rgb
            if rgb is not None:
                ctx.set_source_rgb(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
                ctx.rectangle(0, 0, largura, altura)
                ctx.fill()
            # Contorno neutro delimita o swatch sem trair a cor crua (e é o
            # único traço visível quando a cor é desconhecida).
            ctx.set_source_rgb(
                ACCENT_NEUTRO[0] / 255,
                ACCENT_NEUTRO[1] / 255,
                ACCENT_NEUTRO[2] / 255,
            )
            ctx.set_line_width(1)
            ctx.rectangle(0.5, 0.5, largura - 1, altura - 1)
            ctx.stroke()
            return False

    class CaixaDeTetoElastico(Gtk.Bin):  # type: ignore[misc]
        """Dá a um widget do glade o MESMO teto elástico do card.

        SOM-01 deu ao card de um controle um teto que cresce com a janela até
        :data:`LARGURA_CARD_ELASTICA`. O `frame_status_estado` do glade ficou
        de fora — ele não tem código nosso, e a única alavanca de um widget de
        glade é `width-request`, que é MÍNIMO e sobe intacto até a janela.
        Resultado medido na captura de 1870px: um frame Estado de 1040px em
        cima de um card de 1400px, visivelmente desalinhados.

        Esta caixa resolve pelo mesmo mecanismo do card, em vez de por um
        segundo: ela aceita toda a largura que a aba der, corta no teto e
        devolve o excedente como margem, centrando o filho. Quem estiver
        abaixo do teto cresce junto com a janela.
        """

        def __init__(self, filho: Any) -> None:
            super().__init__()
            self.set_halign(Gtk.Align.FILL)
            self.set_hexpand(True)
            self.add(filho)

        def do_size_allocate(self, allocation: Any) -> None:
            if allocation.width > LARGURA_CARD_ELASTICA:
                sobra = allocation.width - LARGURA_CARD_ELASTICA
                cortado = allocation.copy()
                cortado.x = allocation.x + sobra // 2
                cortado.width = LARGURA_CARD_ELASTICA
                allocation = cortado
            Gtk.Bin.do_size_allocate(self, allocation)

    class RotuloDeAlturaReservada(Gtk.Label):  # type: ignore[misc]
        """Um rótulo que pede a altura da MAIOR frase que pode receber.

        NAO-DANCA-01 (13/08/2026). É a cura do que ela relatou assim: *"não
        sei se dá pra ver mas o layout fica sambando aqui na interface"*.

        O MECANISMO DO DEFEITO, medido antes desta classe existir
        --------------------------------------------------------

        A linha da verdade mora numa `Gtk.Label` com quebra de linha, e a
        altura dela governa a altura da faixa inteira (a frase à esquerda, a
        bateria à direita) — o primeiro bloco do corpo do card. Com o card na
        largura da tela dela, a frase **recebe 904px e pede 905px** de largura
        natural: um pixel de folga negativa. Nessa lâmina, um único dígito do
        `(~N Hz)` decide se a frase cabe em uma linha ou quebra em duas. Com as
        três frases das fotos dela: ~160 Hz e ~190 Hz quebram, ~193 Hz não, e
        **tudo o que vem abaixo sobe e desce 18px**, duas vezes por segundo.

        POR QUE RESERVAR A ALTURA, E NÃO AS OUTRAS DUAS SAÍDAS
        -----------------------------------------------------

        * **estabilizar o número** (largura fixa para o Hz) curaria só o
          tremor de 2 Hz e deixaria de pé o salto maior, o de quando um
          recurso muda de grupo e a frase muda de tamanho de verdade. E aqui
          nem haveria o que estabilizar: medido nesta fonte, `'160'` e `'193'`
          têm a MESMA largura em pixel inteiro — o que os separa é fração de
          pixel, e é a folga de 1px que a transforma em quebra de linha;
        * **tirar a bateria da disputa** curaria a bateria e mais nada: a
          frase continuaria governando a altura da faixa, e o Touchpad, os
          analógicos, o Microfone e o teclado de botões continuariam subindo
          e descendo juntos;
        * **dar mais largura à frase** (mexer no teto de caracteres ou
          estreitar a barra da bateria) é cura de sintoma: vale para a frase
          de hoje e cai na primeira frase mais longa.

        POR QUE UMA SUBCLASSE, E NÃO UM `set_size_request`
        -------------------------------------------------

        Foi a primeira tentativa, e a medição a reprovou: quem calcula a
        reserva de fora só sabe a largura DEPOIS da primeira alocação (antes
        dela um widget mede 1x1, e um rótulo vazio pede largura natural ZERO),
        então o card nascia com a altura errada e se corrigia no tique
        seguinte — um pulo de 18px meio segundo depois de abrir a janela, que
        é o mesmo defeito com outro relógio.

        Respondendo à PERGUNTA da altura, não há esse instante: o GTK pergunta
        "de que altura você precisa NESTA largura?" e a resposta já é a do
        pior caso, na primeira alocação e em todas as seguintes. De quebra,
        acompanha de graça o que a régua de fora teria de vigiar — a janela
        mudar de tamanho e a escala de fonte dela mudar (`app/theme.py`).
        """

        def __init__(self) -> None:
            super().__init__()
            #: Cache por largura: a mesma pergunta chega várias vezes por
            #: negociação, e montar o layout do Pango a cada uma seria trabalho
            #: repetido num caminho que roda a 2 Hz. Some quando a fonte muda.
            self._alturas: dict[int, int] = {}
            self.connect("style-updated", self._esquecer_alturas)

        def _esquecer_alturas(self, *_args: Any) -> None:
            """A fonte mudou: a altura de uma linha mudou junto."""
            self._alturas.clear()

        def altura_reservada(self, largura_perguntada: int = 0) -> int:
            """A altura da frase mais longa possível, em px, na largura REAL.

            A largura em que se mede é a que o rótulo TEM — a alocada —, e a
            perguntada só entra antes da primeira alocação. A diferença foi
            medida, e é a segunda metade desta cura:

            o GTK responde "de que altura você precisa?" (sem largura)
            calculando a largura NATURAL do rótulo e perguntando a altura
            nela. Só que a largura natural de um rótulo que quebra linha
            depende do TEXTO: 618px com a frase curta, 1060px com a mais
            longa. Medir a reserva em cima dela devolveria a dança pela porta
            dos fundos — 40px de reserva num caso e 20px no outro, e a altura
            que o CARD pede oscilando 18px com o texto, que é exatamente o
            defeito, um nível acima. O teste
            `test_a_frase_curta_e_a_mais_longa_nao_movem_nada` reprova por
            isto.

            O preço, dito na mesa: ao ARRASTAR a janela para outra largura, a
            reserva fica um ciclo de negociação atrás (ela mede na largura
            anterior). O GTK renegocia assim que a alocação muda, então o erro
            dura um quadro, só cresce (nunca corta texto) e acontece durante
            um gesto dela — não duas vezes por segundo, sozinho, que é o que
            ela relatou.
            """
            largura = self.get_allocated_width()
            if largura <= 1:
                largura = largura_perguntada
            if largura <= 0:
                return 0
            em_cache = self._alturas.get(largura)
            if em_cache is not None:
                return em_cache
            layout = self.create_pango_layout(
                frase_mais_longa_do_que_chega_ao_jogo()
            )
            layout.set_wrap(self.get_line_wrap_mode())
            layout.set_width(largura * Pango.SCALE)
            altura = int(layout.get_pixel_size()[1])
            self._alturas[largura] = altura
            return altura

        def do_get_preferred_height_for_width(
            self, largura: int
        ) -> tuple[int, int]:
            minimo, natural = Gtk.Label.do_get_preferred_height_for_width(
                self, largura
            )
            reserva = self.altura_reservada(largura)
            return max(minimo, reserva), max(natural, reserva)

        def do_get_preferred_height(self) -> tuple[int, int]:
            # O caminho sem largura. Num rótulo que quebra linha o GTK nem
            # costuma passar por aqui (ele resolve por height-for-width na
            # largura natural), mas quem passar tem de ver a mesma reserva.
            minimo, natural = Gtk.Label.do_get_preferred_height(self)
            reserva = self.altura_reservada()
            return max(minimo, reserva), max(natural, reserva)


else:

    class CaixaDeTetoElastico:  # type: ignore[no-redef]
        """Stub sem GTK3 — a caixa só existe para layout."""

        def __init__(self, filho: Any) -> None:
            self.filho = filho


    class ControllerCard:  # type: ignore[no-redef]
        """Stub para ambientes sem GTK3 (testes/CI sem display).

        Guarda o resultado das funções puras — o suficiente para asserções
        de contrato sem toolkit.
        """

        def __init__(self, *, compact: bool = False) -> None:
            self._compact = compact
            self.titulo: str | None = None
            self.dica_titulo: str | None = None
            self.rotulo: str | None = None
            self.accent: RGB | None = None
            self.degradacao: str | None = None
            self.motion: str | None = None
            #: PAINEL-DA-VERDADE-01: a linha do que chega ao jogo agora.
            self.verdade: str | None = None
            self.sem_leitor: bool = False
            # S2 — None em qualquer um deles = o módulo não apareceria.
            self.gyro: tuple[float, float, float] | None = None
            self.touchpad: tuple[bool, float, float] | None = None
            self.mic_selo: tuple[str, str, str] | None = None
            self.mic_nivel: float | None = None
            self.mic_acao: AcaoMic = acao_mic(None)
            self.uniq: str | None = None
            #: GUARDA-SEM-ENDEREÇO-01: o som deste card está desligado? No
            #: stub isso é o estado inteiro — ele não tem peça para dessensibi-
            #: lizar, mas quem o lê precisa da MESMA resposta do widget real.
            self.audio_sem_endereco: bool = True
            self.speaker: tuple[int, bool | None] | None = None
            self.speaker_acao_mudo: AcaoSpeaker = acao_speaker_mudo(None)
            self.speaker_acao_devolucao: AcaoSpeaker = acao_speaker_devolucao(None)
            self.speaker_saida_muda: bool | None = None
            #: SOM-ACORDADO-01 — o canal e a regra que impede o sono. No stub
            #: são só o que entrou pelo `definir_estado_do_canal`.
            self.speaker_canal: str = ""
            self.speaker_regra_do_sono: bool | None = None
            self.speaker_sink: str = ""
            # CARD-ÚNICO-01 — o par global que o frame "Estado" deixou. No
            # stub eles são o que o widget real mostra ao nascer, e o card
            # compacto não os recebe (com 2+ controles quem responde por eles
            # é o frame Estado, que volta a aparecer).
            self.perfil_ativo: str | None = (
                None if compact else TEXTO_PERFIL_SEM_DADO
            )
            self.daemon: str | None = None if compact else TEXTO_DAEMON_SEM_DADO

        def definir_estado_global(self, perfil: str, daemon: str) -> None:
            """Guarda o par global (mesmo contrato do widget real)."""
            if self._compact:
                return
            if perfil:
                self.perfil_ativo = perfil
            if daemon:
                self.daemon = daemon

        def update(
            self,
            entry: dict[str, Any],
            state_global: dict[str, Any],
            mic: Any = None,
        ) -> None:
            """Aplica as funções puras (mesma semântica do widget real)."""
            self.titulo = titulo_do_card(entry)
            self.dica_titulo = dica_do_titulo(entry, state_global)
            self.rotulo, _base = rotulo_lightbar(entry, state_global)
            self.accent = accent_do_card(entry, state_global)
            self.degradacao = texto_degradacao(entry)
            self.motion = texto_motion(entry, state_global)
            self.verdade = resumo_do_que_chega_ao_jogo(entry, state_global)
            self.sem_leitor = not isinstance(entry.get("inputs"), dict)
            self.gyro = gyro_do_inputs(entry.get("inputs"))
            self.touchpad = touchpad_do_inputs(entry.get("inputs"))
            self.mic_nivel = getattr(mic, "nivel", None) if mic is not None else None
            self.mic_selo = selo_mic(
                getattr(mic, "muted", None) if mic is not None else None
            )
            self.mic_acao = acao_mic(entry)
            self.uniq = uniq_do_entry(entry)
            self.audio_sem_endereco = audio_sem_endereco(entry)
            self.speaker = speaker_do_entry(entry)
            self.speaker_acao_mudo = acao_speaker_mudo(entry)
            self.speaker_acao_devolucao = acao_speaker_devolucao(entry)
            self.speaker_saida_muda = saida_muda_do_entry(entry, mic)

        def definir_estado_do_canal(
            self, estado: str, *, regra_instalada: bool | None = None
        ) -> None:
            """Guarda o estado do canal (mesmo contrato do widget real)."""
            self.speaker_canal = estado or ""
            self.speaker_regra_do_sono = regra_instalada

        def definir_sink_de_saida(self, sink: str) -> None:
            """Guarda o sink deste controle (mesmo contrato do widget real)."""
            self.speaker_sink = sink or ""

        def reset_inputs(self) -> None:
            """IPC sem resposta → "—" (mesmo contrato do widget real)."""
            self.sem_leitor = True

        def show_all(self) -> None:
            """No-op no stub."""

        def destroy(self) -> None:
            """No-op no stub."""


__all__ = [
    "ALL_BUTTONS",
    "DICA_AUDIO_SEM_ENDERECO",
    "DICA_BLOCO_SPEAKER",
    "DICA_CANAL_ACORDADO",
    "DICA_CANAL_DORMINDO",
    "DICA_CANAL_E_PADRAO",
    "DICA_CANAL_SEM_A_REGRA",
    "DICA_MIC_ATIVAR",
    "DICA_MIC_DEVOLVER",
    "DICA_MIC_SEM_LEITURA",
    "DICA_MIC_SILENCIAR",
    "DICA_SPEAKER_ATIVAR",
    "DICA_SPEAKER_DEVOLVER",
    "DICA_SPEAKER_DEVOLVER_SEM_POSSE",
    "DICA_SPEAKER_ESCALA",
    "DICA_SPEAKER_POSSE_NOSSA",
    "DICA_SPEAKER_SEM_DADO",
    "DICA_SPEAKER_SILENCIAR",
    "DICA_TITULO_SEM_VPAD",
    "GLYPH_ESPACO_COMPACTO",
    "GLYPH_ESPACO_UNICO",
    "GLYPH_FATOR_UNICO_OITAVOS",
    "GLYPH_PX_POR_DEGRAU_DE_FONTE",
    "GLYPH_SIZE_BASE",
    "GRID_BOTOES",
    "L2_R2_THRESHOLD",
    "LARGURA_BARRA_GATILHO_COMPACTO",
    "LARGURA_BARRA_GATILHO_UNICO",
    "LARGURA_CARD_ELASTICA",
    "LARGURA_CARD_UNICO",
    "LARGURA_GYRO_COMPACTO",
    "LARGURA_GYRO_UNICO",
    "MOTIVOS_DEGRADACAO_LEIGOS",
    "ROTULO_STICK_DIR",
    "ROTULO_STICK_ESQ",
    "STICK_SIZE_COMPACT",
    "STICK_SIZE_SINGLE",
    "SUFIXO_CANAL_ACORDADO",
    "SUFIXO_CANAL_DORMINDO",
    "TEXTO_AUDIO_SEM_ENDERECO",
    "TEXTO_BOTAO_MIC_ATIVAR",
    "TEXTO_BOTAO_MIC_DEVOLVER",
    "TEXTO_BOTAO_MIC_SEM_LEITURA",
    "TEXTO_BOTAO_MIC_SILENCIAR",
    "TEXTO_BOTAO_SPEAKER_ATIVAR",
    "TEXTO_BOTAO_SPEAKER_DEVOLVER",
    "TEXTO_BOTAO_SPEAKER_SEM_DADO",
    "TEXTO_BOTAO_SPEAKER_SILENCIAR",
    "TEXTO_MIC_AUSENTE",
    "TEXTO_MIC_SEM_MUTE",
    "TEXTO_SELO_CANAL_DORMINDO",
    "TEXTO_SELO_SAIDA_MUDA",
    "TEXTO_SELO_SEM_SOM",
    "TEXTO_SPEAKER_SEM_DADO",
    "TITULO_SPEAKER",
    "AcaoMic",
    "AcaoSpeaker",
    "CaixaDeTetoElastico",
    "ControllerCard",
    "acao_mic",
    "acao_speaker_devolucao",
    "acao_speaker_mudo",
    "accent_do_card",
    "audio_sem_endereco",
    "dica_do_titulo",
    "frase_mais_longa_do_que_chega_ao_jogo",
    "glyph_size",
    "glyph_size_unico",
    "gyro_do_inputs",
    "rotulo_lightbar",
    "saida_muda_do_entry",
    "speaker_do_entry",
    "texto_degradacao",
    "texto_motion",
    "titulo_do_card",
    "touchpad_do_inputs",
    "uniq_do_entry",
]
