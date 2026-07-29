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
    [ Touchpad     |                                              ]
    [ Lightbar     | L3 | R3 | Microfone |          botões (4x4)  ]
    [ Alto-falante |                                              ]

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

Sem timers próprios (zero timeout/idle do GLib aqui — quem agenda é a mixin
de status, com os timers que ela JÁ tinha; o aceite do STATUS-02 é diff
contra esse baseline) e sem popups (cosmic-epoch#2497): tudo inline, sempre
visível. Como os demais widgets da casa, há a variante GTK real e um stub
puro para ambiente sem GTK (testes/CI sem display).
"""
from __future__ import annotations

from typing import Any, Final, NamedTuple

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.widgets.sensor_widgets import (
    GyroBars,
    LightbarBar,
    MicMeter,
    SpeakerBar,
    TouchpadView,
    fracao_do_volume,
    posicao_normalizada,
    selo_mic,
    texto_toques,
    texto_volume,
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


def glyph_size(escala: int | None = None) -> int:
    """Tamanho do glifo em px, DERIVADO da escala de fonte da interface.

    Chamada na MONTAGEM do grid (`_montar_glyphs`), nunca no import: é isso que
    faz um card novo já nascer com o tamanho da escala vigente, e é isso que o
    A/B de escala 0 contra escala 3 mede.
    """
    if escala is None:
        escala = _escala_da_interface()
    return GLYPH_SIZE_BASE + GLYPH_PX_POR_DEGRAU_DE_FONTE * max(0, int(escala))


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
STICK_SIZE_SINGLE: Final[int] = 110
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

#: A lateral de cada analógico, agora ao lado do X/Y (ver `_markup_xy`).
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
LARGURA_CARD_UNICO: Final[int] = 960

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
LARGURA_BARRA_GATILHO_UNICO: Final[int] = 300
LARGURA_GYRO_UNICO: Final[int] = 320
LARGURA_BARRA_GATILHO_COMPACTO: Final[int] = 200
LARGURA_GYRO_COMPACTO: Final[int] = 220

#: Tamanhos dos desenhos no card de UM controle (o compacto usa os do
#: `sensor_widgets`). Mesma troca do analógico: a altura sobrava e a metade de
#: baixo da aba era vazia.
_TOUCHPAD_PX_UNICO: Final[tuple[int, int]] = (140, 60)
_MIC_METER_PX_UNICO: Final[tuple[int, int]] = (140, 44)
_BARRA_FINA_PX_UNICO: Final[tuple[int, int]] = (120, 14)

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
TEXTO_MIC_AUSENTE: Final[str] = "sem sinal"
TEXTO_MIC_SEM_MUTE: Final[str] = "captando"

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
TEXTO_BOTAO_MIC_DEVOLVER: Final[str] = "Devolver"
TEXTO_BOTAO_MIC_SEM_LEITURA: Final[str] = "sem dado"

#: As dicas (tooltip) do botão. Elas carregam o que o rótulo curto não cabe —
#: em especial o preço de mandar no mudo pela janela: enquanto o hefesto for o
#: dono do registrador, o botão FÍSICO do controle para de valer. Esconder esse
#: preço seria repetir o erro de "a config que eu deixo nunca é respeitada".
DICA_MIC_ATIVAR: Final[str] = (
    "O microfone está mudo no firmware do controle (camada 3). Desmutar daqui "
    "faz o hefesto assumir o registrador — e o botão de microfone do controle "
    "para de valer até você clicar em Devolver."
)
DICA_MIC_SILENCIAR: Final[str] = (
    "O microfone está aberto e quem manda no mudo é o botão físico do "
    "controle. Silenciar daqui faz o hefesto assumir o registrador."
)
DICA_MIC_DEVOLVER: Final[str] = (
    "Quem manda no mudo agora é o hefesto, e por isso o botão de microfone do "
    "controle não responde. Devolver a posse faz o botão físico voltar a valer."
)
DICA_MIC_SEM_LEITURA: Final[str] = (
    "O daemon ainda não leu o estado do microfone deste controle. Sem saber "
    "se ele está mudo, mandar mutar ou desmutar seria chute."
)

#: Alto-falante sem volume conhecido. O DualSense NÃO devolve o volume — não
#: há report de input nem feature report que o leia, e o daemon só publica a
#: chave `speaker` depois de um `speaker.set` nosso (ipc_handlers). Então o
#: bloco existe sempre, e diz que ninguém ajustou nada: um "0 %" ali seria
#: volume inventado, e esconder o bloco seria dizer que o controle não tem
#: alto-falante.
TEXTO_SPEAKER_SEM_DADO: Final[str] = "não ajustado"

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
#: um lado, 2 do outro); aqui ela entra num campo que já é mono e de largura
#: fixa, e a segunda linha recebe espaços do mesmo tamanho para o ``X`` e o
#: ``Y`` continuarem alinhados um sob o outro.
_XY_MARKUP: Final[str] = "{rot} X:{x:>3}\n{pad} Y:{y:>3}"


def _markup_xy(rotulo: str, x: int, y: int) -> str:
    """``"L3 X:128" / "   Y:128"`` — a lateral e o par de eixos, em mono."""
    return _XY_MARKUP.format(rot=rotulo, pad=" " * len(rotulo), x=x, y=y)

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


def rotulo_lightbar(
    entry: dict[str, Any], state_global: dict[str, Any]
) -> tuple[str | None, RGB | None]:
    """``(rótulo, cor_base_do_accent)`` da lightbar de UM controle.

    Regras (STATUS-03 + refutação 1 do sprint — o dono da escrita decide):

    * ``native_mode`` global → "em Nativo o jogo é dono do LED"; o accent usa
      a última cor conhecida (ou o neutro, se nenhuma). O jogo escreve por
      hidraw e o daemon não pisa no LED — o card avisa em vez de mentir.
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
        return ("em Nativo o jogo é dono do LED", rgb)
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
    return f"emulação degradada (uinput): {legivel}"


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
    """
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
    ativo, posse nossa          Devolver            ``None``
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
    from gi.repository import Gtk, Pango

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

        def __init__(self, *, compact: bool = False) -> None:
            super().__init__()
            self._compact = compact
            self._espaco = (
                _ESPACO_FAIXA_COMPACTO if compact else _ESPACO_FAIXA_UNICO
            )
            # Caches de diff (sentinela onde None é valor válido).
            self._last_titulo: str | None = None
            self._last_battery: Any = _SENTINELA
            self._last_lightbar: Any = _SENTINELA
            self._last_degradacao: Any = _SENTINELA
            self._last_motion: Any = _SENTINELA
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
            self._mic_acao: AcaoMic | None = None
            self._montar_ui()

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
            uniq = entry.get("uniq")
            self._uniq = uniq if isinstance(uniq, str) and uniq else None
            self._update_titulo(entry)
            self._update_bateria(entry)
            self._update_lightbar(entry, state_global)
            self._update_degradacao(entry)
            self._update_motion(entry, state_global)
            self._update_inputs(entry.get("inputs"))
            self._update_gyro(entry.get("inputs"))
            self._update_touchpad(entry.get("inputs"))
            self._update_mic(mic, str(entry.get("transport") or ""))
            self._update_mic_botao(entry)
            self._update_speaker(entry)

        def reset_inputs(self) -> None:
            """IPC sem resposta: mostra "—" — nunca o último valor como vivo."""
            self._mostrar_sem_leitor()

        # ------------------------------------------------------------------
        # Montagem da UI (uma vez, no __init__)
        # ------------------------------------------------------------------

        def _montar_ui(self) -> None:
            if not self._compact:
                # Card de UM controle: largura com teto e centrado na aba.
                # Sem isto ele estica pelos 1870px da tela maximizada e a
                # sobra vira buraco DENTRO da faixa — o defeito 4 da
                # STATUS-SIMETRIA-02, não margem de página.
                self.set_size_request(LARGURA_CARD_UNICO, -1)
                self.set_halign(Gtk.Align.CENTER)
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
            linha_bateria = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=12
            )
            cap_bateria = Gtk.Label(label="Bateria:")
            cap_bateria.set_xalign(1.0)
            linha_bateria.pack_start(cap_bateria, False, False, 0)
            bateria = Gtk.ProgressBar()
            bateria.set_show_text(True)
            bateria.set_text("— %")
            bateria.set_hexpand(True)
            self._battery_bar = bateria
            linha_bateria.pack_start(bateria, True, True, 0)
            self._battery_row = linha_bateria
            corpo.pack_start(linha_bateria, False, False, 0)
            if not self._compact:
                self._esconder_modulo(linha_bateria)

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

            # GYRO-03: linha discreta do giroscópio espelhado — inline
            # (dim-label), nunca popup (veto cosmic-comp). Só aparece com o
            # espelho de motion ATIVO no vpad deste controle.
            motion = Gtk.Label()
            motion.set_xalign(0.0)
            motion.get_style_context().add_class("dim-label")
            motion.set_no_show_all(True)
            motion.hide()
            self._motion_label = motion
            corpo.pack_start(motion, False, False, 0)

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
            grid.set_column_spacing(16)
            grid.set_column_homogeneous(True)
            grid.attach(self._montar_gatilhos(), 0, 0, 1, 1)
            slot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            slot.pack_start(self._montar_gyro(), False, False, 0)
            self._gyro_slot = slot
            grid.attach(slot, 1, 0, 1, 1)
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
                barra.set_halign(Gtk.Align.START)
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
            barras.set_halign(Gtk.Align.START)
            # O bloco acompanha o conteúdo em vez de esticar pela coluna
            # inteira do grid: moldura larga com desenho estreito dentro
            # devolveria o vazio para DENTRO do bloco.
            caixa.set_halign(Gtk.Align.START)
            miolo.pack_start(barras, False, False, 0)
            self._gyro_bars = barras
            self._gyro_box = caixa
            self._esconder_modulo(caixa)
            return caixa

        def _montar_linha_inferior(self) -> Any:
            """A faixa de leitura ao vivo, na ordem que a mantenedora pediu.

            STATUS-SIMETRIA-01 — *"a área do mic que deveria ficar à direita
            dos analógicos"*::

                [ Touchpad     ]                             [ ]  [ ]  [ ]  [ ]
                [ Lightbar     ] [ L3 ] [ R3 ] [ Microfone ] [ ]  [ ]  [ ]  [ ]
                [ Alto-falante ]                             [ ]  [ ]  [ ]  [ ]
                                                             [ ]  [ ]  [ ]  [ ]

            O microfone continua DENTRO do card — a madrugada de 26/07 o mandou
            para o rodapé da aba, que é o oposto do pedido, e foi revertida.

            Os três módulos que sobraram à esquerda ficam EMPILHADOS, e não em
            duas fileiras de dois. É a troca que paga a coluna do microfone e o
            glifo maior: em duas fileiras a coluna pedia 163px (a fileira
            "lightbar + alto-falante" mandava na largura); empilhada ela pede
            88px, e os 75px devolvidos são exatamente da ordem de grandeza da
            coluna nova do microfone. A altura sobe ~30px, e altura é o que
            sobra nesta faixa — a restrição dura aqui é LARGURA, porque dois
            cards lado a lado somam direto no mínimo da janela e a aba Status
            não tem rolagem horizontal para onde fugir.

            Cada módulo se esconde SOZINHO quando não há sensor: nenhum deles
            arrasta o vizinho, e nenhum deles leva os botões junto (a armadilha
            de LEGIBILIDADE-01, quando o grid morava dentro da linha que sumia).
            """
            linha = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=self._espaco,
            )

            linha.pack_start(self._montar_coluna_sensores(), False, False, 0)
            # O miolo — os dois analógicos e o microfone COLADO à direita deles,
            # que é o pedido ao pé da letra. Vai empacotado com
            # `expand=True, fill=False`: a sobra de largura do card se reparte
            # nos dois lados do miolo em vez de virar um buraco só (medido no
            # card de um controle: 764px de vazio entre o fim dos analógicos e o
            # começo do grid). `fill=False` mantém os três blocos juntos —
            # esticar a caixa afastaria o microfone dos analógicos de novo.
            miolo = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=self._espaco,
            )
            miolo.pack_start(self._montar_sticks(), False, False, 0)
            miolo.pack_start(self._montar_mic(), False, False, 0)
            self._miolo_inferior = miolo
            linha.pack_start(miolo, True, False, 0)
            # Botões ancorados à DIREITA (`pack_end`), não empurrados pelo que
            # vem antes: microfone e alto-falante aparecem e somem conforme o
            # controle, e o grid de 16 glyphs não pode dançar de lugar a cada
            # vez que um módulo de sensor entra ou sai.
            glyphs = self._montar_glyphs()
            glyphs.set_halign(Gtk.Align.END)
            linha.pack_end(glyphs, False, False, 0)
            self._linha_inferior = linha
            return linha

        def _montar_coluna_sensores(self) -> Any:
            """Coluna da esquerda: touchpad, lightbar e alto-falante empilhados."""
            coluna = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=self._espaco // 2,
            )
            coluna.pack_start(self._montar_touchpad(), False, False, 0)
            coluna.pack_start(self._montar_lightbar(), False, False, 0)
            coluna.pack_start(self._montar_speaker(), False, False, 0)
            self._coluna_sensores = coluna
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
                painel.set_size_request(*_TOUCHPAD_PX_UNICO)
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
                medidor.set_size_request(*_MIC_METER_PX_UNICO)
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
            miolo.pack_start(botao, False, False, 0)
            # O botão fica FORA do SizeGroup de propósito: ele já tem teto
            # próprio (o `max_width_chars` do rótulo acima) e amarrá-lo aqui
            # faria o medidor e o selo herdarem a largura DELE — o oposto do
            # que este grupo existe para fazer.
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
            if acao is None or not acao.sensivel:
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
            """Bloco "Alto-falante": volume do speaker embutido do controle.

            STATUS-SIMETRIA-02, entrega 4 — *"não tem a parte do som"*. O
            bloco sumia da tela dela por construção: o daemon só publica a
            chave ``speaker`` DEPOIS de um ``speaker.set`` nosso, porque o
            DualSense não devolve o volume (não há report de input nem feature
            report que o leia — ver ``ipc_handlers``), e o card escondia o
            módulo inteiro na ausência da chave. Só que sumir é
            indistinguível de "este controle não tem alto-falante".

            Agora o bloco fica, em LEITURA: a barra em repouso e o rótulo
            dizendo ``não ajustado``. Nenhum controle novo entra aqui — pôr um
            botão de volume que o daemon aceita mas cujo valor ninguém
            consegue ler de volta seria inventar controle que não funciona.
            """
            caixa, miolo = self._bloco("Alto-falante")
            barra = SpeakerBar()
            barra.set_valign(Gtk.Align.CENTER)
            if not self._compact:
                barra.set_size_request(*_BARRA_FINA_PX_UNICO)
            miolo.pack_start(barra, False, False, 0)
            # Sem campo fixo aqui, ao contrário do microfone: quem manda na
            # largura desta coluna é o rótulo "Alto-falante", que é maior que
            # qualquer valor e não muda — trocar "não ajustado" por "50 %" não
            # mexe em nada. Um `width_chars` seria 30px de largura cobrados por
            # nada, e a largura é o que falta nesta aba.
            valor = self._rotulo_secao(TEXTO_SPEAKER_SEM_DADO)
            miolo.pack_start(valor, False, False, 0)
            self._speaker_bar = barra
            self._speaker_label = valor
            self._speaker_box = caixa
            return caixa

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
            label_xy.set_markup(_markup_xy(rotulo_stick, 128, 128))
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
            """
            tamanho = glyph_size()
            self._glyph_size = tamanho
            glyph_grid = Gtk.Grid()
            glyph_grid.set_row_spacing(2)
            glyph_grid.set_column_spacing(2)
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

        def _update_titulo(self, entry: dict[str, Any]) -> None:
            titulo = titulo_do_card(entry)
            if titulo != self._last_titulo:
                self._last_titulo = titulo
                self._title_label.set_text(titulo)

        def _update_bateria(self, entry: dict[str, Any]) -> None:
            bateria = _int_ou_none(entry.get("battery_pct"))
            if bateria == self._last_battery:
                return
            self._last_battery = bateria
            if bateria is None:
                self._battery_bar.set_fraction(0.0)
                self._battery_bar.set_text("— %")
            else:
                self._battery_bar.set_fraction(
                    max(0, min(100, bateria)) / 100
                )
                self._battery_bar.set_text(f"{bateria} %")

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
            if texto:
                self._motion_label.set_text(texto)
                self._motion_label.show()
            else:
                self._motion_label.hide()

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

        def _update_speaker(self, entry: dict[str, Any]) -> None:
            dados = speaker_do_entry(entry)
            if dados == self._last_speaker:
                return
            self._last_speaker = dados
            self._aplicar_estado_speaker(dados)

        def _aplicar_estado_speaker(
            self, dados: tuple[int, bool | None] | None
        ) -> None:
            """Volume do alto-falante, ou a frase que diz que ninguém ajustou.

            O bloco NUNCA se esconde: some é o que ela leu como "não tem a
            parte do som".
            """
            if dados is None:
                self._speaker_bar.set_volume(0.0, None)
                self._speaker_label.set_text(TEXTO_SPEAKER_SEM_DADO)
                return
            volume, muted = dados
            self._speaker_bar.set_volume(fracao_do_volume(volume), muted)
            self._speaker_label.set_text(texto_volume(volume, muted))

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
                    _markup_xy(ROTULO_STICK_ESQ, lx, ly)
                )
                self._last_lx = lx
                self._last_ly = ly
            if rx != self._last_rx or ry != self._last_ry:
                self._stick_right.update(rx, ry)
                self._stick_right_xy.set_markup(
                    _markup_xy(ROTULO_STICK_DIR, rx, ry)
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
                _markup_xy(ROTULO_STICK_ESQ, 128, 128)
            )
            self._stick_right_xy.set_markup(
                _markup_xy(ROTULO_STICK_DIR, 128, 128)
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
            self._aplicar_estado_speaker(None)
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

else:

    class ControllerCard:  # type: ignore[no-redef]
        """Stub para ambientes sem GTK3 (testes/CI sem display).

        Guarda o resultado das funções puras — o suficiente para asserções
        de contrato sem toolkit.
        """

        def __init__(self, *, compact: bool = False) -> None:
            self._compact = compact
            self.titulo: str | None = None
            self.rotulo: str | None = None
            self.accent: RGB | None = None
            self.degradacao: str | None = None
            self.motion: str | None = None
            self.sem_leitor: bool = False
            # S2 — None em qualquer um deles = o módulo não apareceria.
            self.gyro: tuple[float, float, float] | None = None
            self.touchpad: tuple[bool, float, float] | None = None
            self.mic_selo: tuple[str, str, str] | None = None
            self.mic_nivel: float | None = None
            self.mic_acao: AcaoMic = acao_mic(None)
            self.uniq: str | None = None
            self.speaker: tuple[int, bool | None] | None = None

        def update(
            self,
            entry: dict[str, Any],
            state_global: dict[str, Any],
            mic: Any = None,
        ) -> None:
            """Aplica as funções puras (mesma semântica do widget real)."""
            self.titulo = titulo_do_card(entry)
            self.rotulo, _base = rotulo_lightbar(entry, state_global)
            self.accent = accent_do_card(entry, state_global)
            self.degradacao = texto_degradacao(entry)
            self.motion = texto_motion(entry, state_global)
            self.sem_leitor = not isinstance(entry.get("inputs"), dict)
            self.gyro = gyro_do_inputs(entry.get("inputs"))
            self.touchpad = touchpad_do_inputs(entry.get("inputs"))
            self.mic_nivel = getattr(mic, "nivel", None) if mic is not None else None
            self.mic_selo = selo_mic(
                getattr(mic, "muted", None) if mic is not None else None
            )
            self.mic_acao = acao_mic(entry)
            uniq = entry.get("uniq")
            self.uniq = uniq if isinstance(uniq, str) and uniq else None
            self.speaker = speaker_do_entry(entry)

        def reset_inputs(self) -> None:
            """IPC sem resposta → "—" (mesmo contrato do widget real)."""
            self.sem_leitor = True

        def show_all(self) -> None:
            """No-op no stub."""

        def destroy(self) -> None:
            """No-op no stub."""


__all__ = [
    "ALL_BUTTONS",
    "DICA_MIC_ATIVAR",
    "DICA_MIC_DEVOLVER",
    "DICA_MIC_SEM_LEITURA",
    "DICA_MIC_SILENCIAR",
    "GLYPH_PX_POR_DEGRAU_DE_FONTE",
    "GLYPH_SIZE_BASE",
    "GRID_BOTOES",
    "L2_R2_THRESHOLD",
    "LARGURA_BARRA_GATILHO_COMPACTO",
    "LARGURA_BARRA_GATILHO_UNICO",
    "LARGURA_CARD_UNICO",
    "LARGURA_GYRO_COMPACTO",
    "LARGURA_GYRO_UNICO",
    "MOTIVOS_DEGRADACAO_LEIGOS",
    "ROTULO_STICK_DIR",
    "ROTULO_STICK_ESQ",
    "STICK_SIZE_COMPACT",
    "STICK_SIZE_SINGLE",
    "TEXTO_BOTAO_MIC_ATIVAR",
    "TEXTO_BOTAO_MIC_DEVOLVER",
    "TEXTO_BOTAO_MIC_SEM_LEITURA",
    "TEXTO_BOTAO_MIC_SILENCIAR",
    "TEXTO_MIC_AUSENTE",
    "TEXTO_MIC_SEM_MUTE",
    "TEXTO_SPEAKER_SEM_DADO",
    "AcaoMic",
    "ControllerCard",
    "acao_mic",
    "accent_do_card",
    "glyph_size",
    "gyro_do_inputs",
    "rotulo_lightbar",
    "speaker_do_entry",
    "texto_degradacao",
    "texto_motion",
    "titulo_do_card",
    "touchpad_do_inputs",
]
