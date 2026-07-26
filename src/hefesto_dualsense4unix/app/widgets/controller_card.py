"""controller_card.py — card de UM controle na aba Status (STATUS-02/03 + BT-03).

A aba Status deixou de ser single-controller: cada DualSense conectado ganha
um card com identidade própria — título pelo ``player_slot`` de sessão,
bateria própria, swatch da cor CRUA da lightbar — e os inputs ao vivo DAQUELE
controle (barras L2/R2, dois ``StickPreviewGtk`` e o grid 4x4 de
``ButtonGlyph``) com os traços pintados na cor da lightbar dele, ajustada por
``ensure_min_contrast`` (decisão D8: o swatch mostra a cor crua; só os TRAÇOS
recebem a ajustada).

O corpo do card ocupa TRÊS linhas (STATUS-3-LINHAS-01), montadas em código —
não no Glade::

    [ L2 / R2 .................. | Giroscópio ..................... ]
    [ Touchpad ......... | Analógicos (L3/R3) | botões (4x4) ...... ]
    [ Lightbar | Alto-falante |                                     ]

Antes eram seis blocos de largura total, empilhados: o card pedia 457px de
altura e o giroscópio caía abaixo do corte da janela. Emparelhado, o que
somava altura passou a dividir a mesma faixa.

O microfone NÃO está mais nesta lista (MIC-FAIXA-01): ele saiu do card e
virou uma faixa própria e permanente no rodapé da aba Status, montada em
`app/actions/status_actions.py`. Ver `update()` para o porquê.

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

from typing import Any, Final

from hefesto_dualsense4unix.app.actions.base import sufixo_de_jogador
from hefesto_dualsense4unix.app.widgets.sensor_widgets import (
    GyroBars,
    LightbarBar,
    SpeakerBar,
    TouchpadView,
    fracao_do_volume,
    posicao_normalizada,
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

#: Tamanho dos glyphs no card (o layout single antigo usava 40px; com um card
#: por controle e o grid dividindo a linha de baixo com os quatro blocos de
#: sensor, 20px mantém o glifo legível sem estourar largura nem altura).
GLYPH_SIZE: Final[int] = 20

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
STICK_SIZE_SINGLE: Final[int] = 88
STICK_SIZE_COMPACT: Final[int] = 70

#: Largura de referência do título do analógico antes de quebrar linha, em
#: caracteres. O rótulo tem de caber na largura do DESENHO do analógico
#: (`STICK_SIZE_*`), não o contrário — ver `_montar_capsula_stick`.
_TITULO_STICK_MAX_CHARS: Final[int] = 10

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
_XY_MARKUP: Final[str] = "X: {x:>3}\nY: {y:>3}"

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
    # SLOT-JOGADOR-01: o sufixo deixou de ser "Jogador {N}" cru e passou a ter
    # a AUTORIDADE colada ("P1 no co-op" / "P4 no jogo"), com a regra num dono
    # só (`base.sufixo_de_jogador`). Duas telas montavam este rótulo com duas
    # implementações, e o número solto ao lado do "Controle N" lia-se como dois
    # números para a mesma pergunta — o que a CONTAGEM-01 proibe. Sao duas
    # perguntas: QUAL APARELHO é este (o número que acende na lâmpada dele) e
    # QUE JOGADOR ele alimenta.
    sufixo = sufixo_de_jogador(entry)
    if sufixo is not None:
        titulo += f" · {sufixo}"
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
    from gi.repository import Gtk

    # Com um stub parcial de gi (testes antigos sem display), o import acima
    # passa mas faltam classes — o card cai no stub em vez de explodir.
    _GTK_DISPONIVEL = all(
        hasattr(Gtk, attr)
        for attr in (
            "Frame",
            "Box",
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
            self._last_speaker: Any = _SENTINELA
            self._montar_ui()

        # ------------------------------------------------------------------
        # API pública
        # ------------------------------------------------------------------

        def update(
            self,
            entry: dict[str, Any],
            state_global: dict[str, Any],
        ) -> None:
            """Atualiza o card a partir de ``controllers[i]`` (diff interno).

            MIC-FAIXA-01: o microfone SAIU do card. Ele era o único módulo
            daqui cujo dado não vem do IPC, e o único que precisava dizer por
            que não está medindo — dentro do card não havia espaço para essa
            frase, então ele simplesmente sumia, e "sumiu" é indistinguível de
            "não existe". Agora ele mora numa faixa própria no rodapé da aba,
            permanente, montada por `status_actions._sync_mic_strip`. Um fato,
            um dono: aqui não sobrou nenhum medidor de microfone.
            """
            self._update_titulo(entry)
            self._update_bateria(entry)
            self._update_lightbar(entry, state_global)
            self._update_degradacao(entry)
            self._update_motion(entry, state_global)
            self._update_inputs(entry.get("inputs"))
            self._update_gyro(entry.get("inputs"))
            self._update_touchpad(entry.get("inputs"))
            self._update_speaker(entry)

        def reset_inputs(self) -> None:
            """IPC sem resposta: mostra "—" — nunca o último valor como vivo."""
            self._mostrar_sem_leitor()

        # ------------------------------------------------------------------
        # Montagem da UI (uma vez, no __init__)
        # ------------------------------------------------------------------

        def _montar_ui(self) -> None:
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

        def _montar_gatilhos(self) -> Any:
            grid = Gtk.Grid()
            grid.set_row_spacing(6)
            grid.set_column_spacing(12)
            for linha, nome in enumerate(("L2", "R2")):
                cap = Gtk.Label(label=nome)
                cap.set_xalign(1.0)
                cap.set_width_chars(3)
                grid.attach(cap, 0, linha, 1, 1)
                barra = Gtk.ProgressBar()
                barra.set_show_text(True)
                barra.set_text("0 / 255")
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
            caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            caixa.pack_start(
                self._rotulo_secao("Giroscópio (graus/s)"), False, False, 0
            )
            barras = GyroBars()
            caixa.pack_start(barras, False, False, 0)
            self._gyro_bars = barras
            self._gyro_box = caixa
            self._esconder_modulo(caixa)
            return caixa

        def _montar_linha_inferior(self) -> Any:
            """A faixa de leitura ao vivo: sensores, analógicos e botões.

            `_sensores_linha` é SÓ o touchpad desde a MIC-FAIXA-01 (o
            microfone virou faixa própria no rodapé da aba), e mantém a
            semântica de sempre: some inteira quando não há touchpad no
            payload. A lightbar, o alto-falante, os analógicos e o grid de
            botões entram em containers EXTERNOS: se morassem dentro dela,
            sumiriam junto no caso comum de um controle com o dedo fora do
            touchpad.

            Os módulos de sensor ficam em DUAS linhas em vez de uma fileira só
            (LEGIBILIDADE-01/R4). É o que abre a coluna para os analógicos sem
            alargar o card: numa fileira única, dois cards lado a lado passavam
            de 1300px de largura mínima, e a aba Status não tem rolagem
            horizontal para onde fugir. Medido de novo depois que o microfone
            saiu daqui (MIC-FAIXA-01): juntar o touchpad à lightbar e ao
            alto-falante numa fileira só custa 2px a MAIS que a janela inteira
            tem, e não devolve altura nenhuma — a altura do card é ditada pela
            coluna dos analógicos, não por esta.
            """
            linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

            sensores = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            sensores.pack_start(self._montar_touchpad(), False, False, 0)
            saida = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            saida.pack_start(self._montar_lightbar(), False, False, 0)
            saida.pack_start(self._montar_speaker(), False, False, 0)
            self._modulos_saida = saida
            sensores.pack_start(saida, False, False, 0)
            linha.pack_start(sensores, False, False, 0)

            linha.pack_start(self._montar_sticks(), False, False, 0)
            # Botões ancorados à DIREITA (`pack_end`), não empurrados pelo que
            # vem antes: touchpad e alto-falante aparecem e somem conforme o
            # controle, e o grid de 16 glyphs não pode dançar de lugar a cada
            # vez que um módulo de sensor entra ou sai.
            glyphs = self._montar_glyphs()
            glyphs.set_halign(Gtk.Align.END)
            linha.pack_end(glyphs, False, False, 0)
            self._linha_inferior = linha
            return linha

        def _montar_touchpad(self) -> Any:
            linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

            # LEGIBILIDADE-01/R4 — o estado de cada módulo desceu para BAIXO do
            # desenho. Ao lado do título ele economizava uma linha de altura,
            # que era o recurso escasso quando os cinco blocos dividiam UMA
            # fileira. Agora a altura da faixa é ditada pelos analógicos (a
            # cápsula é o bloco mais alto) e sobra folga vertical de sobra; o
            # que ficou escasso é a LARGURA, porque dois cards lado a lado
            # somam direto no mínimo da janela e a aba Status não tem rolagem
            # horizontal. Com "sem toque" ao lado do título, a coluna do
            # touchpad pedia 105px para desenhar um painel de 76.
            touch = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            touch.pack_start(self._rotulo_secao("Touchpad"), False, False, 0)
            painel = TouchpadView()
            touch.pack_start(painel, False, False, 0)
            rotulo = self._rotulo_secao(texto_toques(0))
            touch.pack_start(rotulo, False, False, 0)
            self._touch_view = painel
            self._touch_label = rotulo
            self._touch_box = touch
            linha.pack_start(touch, False, False, 0)

            self._esconder_modulo(linha)
            touch.set_no_show_all(True)
            touch.hide()
            self._sensores_linha = linha
            return linha

        def _montar_lightbar(self) -> Any:
            """Bloco "Lightbar": a cor que já chega no card, agora como BARRA.

            Mesma fonte do swatch do título (``entry.lightbar_rgb``) — nada de
            consultar o daemon outra vez. Sem cor conhecida o bloco some: o
            rótulo "Lightbar: cor desconhecida" do corpo já responde, e uma
            faixa preta ali seria "apagada" dita sem prova.
            """
            caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            caixa.pack_start(self._rotulo_secao("Lightbar"), False, False, 0)
            barra = LightbarBar()
            barra.set_valign(Gtk.Align.CENTER)
            caixa.pack_start(barra, False, False, 0)
            hexa = self._rotulo_secao("")
            caixa.pack_start(hexa, False, False, 0)
            self._lightbar_bar = barra
            self._lightbar_hex = hexa
            self._lightbar_box = caixa
            self._esconder_modulo(caixa)
            return caixa

        def _montar_speaker(self) -> Any:
            """Bloco "Alto-falante": volume do speaker embutido do controle.

            Consumo defensivo (a chave ``speaker`` é opcional): sem ela no
            payload, o módulo nem aparece — nunca uma barra em zero fingindo
            que o volume está no mínimo.
            """
            caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            caixa.pack_start(self._rotulo_secao("Alto-falante"), False, False, 0)
            barra = SpeakerBar()
            barra.set_valign(Gtk.Align.CENTER)
            caixa.pack_start(barra, False, False, 0)
            valor = self._rotulo_secao("")
            caixa.pack_start(valor, False, False, 0)
            self._speaker_bar = barra
            self._speaker_label = valor
            self._speaker_box = caixa
            self._esconder_modulo(caixa)
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
            # O título QUEBRA em vez de alargar a cápsula: na faixa de baixo
            # quem manda na largura tem de ser o desenho do analógico, não o
            # rótulo. Sem isso, "Analógico Esquerdo (L3)" pedia 156px numa
            # cápsula de 70 e alargava o card inteiro. O peso visual passa a
            # ser o dos módulos vizinhos (`dim-label`), que é o que eles são
            # agora: pares na mesma faixa de leitura ao vivo.
            label_titulo.set_line_wrap(True)
            label_titulo.set_justify(Gtk.Justification.CENTER)
            label_titulo.set_max_width_chars(_TITULO_STICK_MAX_CHARS)
            label_titulo.get_style_context().add_class("dim-label")
            caps.pack_start(label_titulo, False, False, 0)
            preview = StickPreviewGtk(label=rotulo_stick)
            preview.set_size_request(tamanho, tamanho)
            slot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            slot.set_halign(Gtk.Align.CENTER)
            slot.pack_start(preview, False, False, 0)
            caps.pack_start(slot, False, False, 0)
            label_xy = Gtk.Label()
            label_xy.set_markup(_XY_MARKUP.format(x=128, y=128))
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
            # Caixa e não mais `Gtk.Grid` homogêneo: a grade dava às duas
            # cápsulas a largura da MAIOR, e a maior era a do rótulo. Aqui cada
            # uma pede o próprio desenho.
            faixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

            caps_esq, stick_esq, titulo_esq, xy_esq = (
                self._montar_capsula_stick(
                    "Analógico Esquerdo (L3)", "L3", tamanho
                )
            )
            self._stick_left = stick_esq
            self._stick_left_title = titulo_esq
            self._stick_left_xy = xy_esq
            faixa.pack_start(caps_esq, False, False, 0)

            caps_dir, stick_dir, titulo_dir, xy_dir = (
                self._montar_capsula_stick(
                    "Analógico Direito (R3)", "R3", tamanho
                )
            )
            self._stick_right = stick_dir
            self._stick_right_title = titulo_dir
            self._stick_right_xy = xy_dir
            faixa.pack_start(caps_dir, False, False, 0)
            self._faixa_sticks = faixa
            return faixa

        def _montar_glyphs(self) -> Any:
            """Grid 4x4 dos 16 botões — o bloco da direita na linha de baixo."""
            glyph_grid = Gtk.Grid()
            glyph_grid.set_row_spacing(2)
            glyph_grid.set_column_spacing(2)
            glyph_grid.set_halign(Gtk.Align.CENTER)
            glyph_grid.set_valign(Gtk.Align.CENTER)
            for row, linha in enumerate(GRID_BOTOES):
                for col, nome in enumerate(linha):
                    tooltip = BUTTON_GLYPH_LABELS.get(nome, nome)
                    glyph = ButtonGlyph(
                        nome, size=GLYPH_SIZE, tooltip_pt_br=tooltip
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
                self._sincronizar_linha_sensores()
                return
            tocando, fx, fy = dados
            self._touch_view.set_toque((fx, fy) if tocando else None)
            self._touch_label.set_text(texto_toques(1 if tocando else 0))
            self._touch_box.show()
            self._sincronizar_linha_sensores()

        def _update_speaker(self, entry: dict[str, Any]) -> None:
            dados = speaker_do_entry(entry)
            if dados == self._last_speaker:
                return
            self._last_speaker = dados
            if dados is None:
                self._speaker_box.hide()
                return
            volume, muted = dados
            self._speaker_bar.set_volume(fracao_do_volume(volume), muted)
            self._speaker_label.set_text(texto_volume(volume, muted))
            self._speaker_box.show()

        def _sincronizar_linha_sensores(self) -> None:
            """A linha de sensores só existe se o touchpad existe.

            Ela era o PAR touchpad + microfone; desde a MIC-FAIXA-01 o
            microfone saiu daqui e sobrou o touchpad. A lightbar, o
            alto-falante e os botões continuam no container externo
            (`_linha_inferior`) para não sumirem junto com ele.
            """
            if self._touch_box.get_visible():
                self._sensores_linha.show()
            else:
                self._sensores_linha.hide()

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
                self._stick_left_xy.set_markup(_XY_MARKUP.format(x=lx, y=ly))
                self._last_lx = lx
                self._last_ly = ly
            if rx != self._last_rx or ry != self._last_ry:
                self._stick_right.update(rx, ry)
                self._stick_right_xy.set_markup(_XY_MARKUP.format(x=rx, y=ry))
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
                self._stick_left_title,
                "Analógico Esquerdo (L3)",
                self._l3_pressed,
            )
            self._pintar_titulo_stick(
                self._stick_right_title,
                "Analógico Direito (R3)",
                self._r3_pressed,
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
            self._stick_left_xy.set_markup(_XY_MARKUP.format(x=128, y=128))
            self._stick_right_xy.set_markup(_XY_MARKUP.format(x=128, y=128))
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
            # congelado no último valor seria movimento inventado.
            self._gyro_bars.limpar()
            self._gyro_box.hide()
            self._touch_view.set_toque(None)
            self._touch_box.hide()
            self._sensores_linha.hide()
            self._speaker_box.hide()
            self._last_gyro = _SENTINELA
            self._last_touch = _SENTINELA
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
            # (O microfone saiu do card na MIC-FAIXA-01 — ver `update`.)
            self.gyro: tuple[float, float, float] | None = None
            self.touchpad: tuple[bool, float, float] | None = None
            self.speaker: tuple[int, bool | None] | None = None

        def update(
            self,
            entry: dict[str, Any],
            state_global: dict[str, Any],
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
    "GLYPH_SIZE",
    "GRID_BOTOES",
    "L2_R2_THRESHOLD",
    "MOTIVOS_DEGRADACAO_LEIGOS",
    "STICK_SIZE_COMPACT",
    "STICK_SIZE_SINGLE",
    "ControllerCard",
    "accent_do_card",
    "gyro_do_inputs",
    "rotulo_lightbar",
    "speaker_do_entry",
    "texto_degradacao",
    "texto_motion",
    "titulo_do_card",
    "touchpad_do_inputs",
]
