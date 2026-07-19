"""controller_card.py — card de UM controle na aba Status (STATUS-02/03 + BT-03).

A aba Status deixou de ser single-controller: cada DualSense conectado ganha
um card com identidade própria — título pelo ``player_slot`` de sessão,
bateria própria, swatch da cor CRUA da lightbar — e os inputs ao vivo DAQUELE
controle (barras L2/R2, dois ``StickPreviewGtk`` e o grid 4x4 de
``ButtonGlyph``) com os traços pintados na cor da lightbar dele, ajustada por
``ensure_min_contrast`` (decisão D8: o swatch mostra a cor crua; só os TRAÇOS
recebem a ajustada).

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

#: Tamanho dos glyphs no card (o layout single antigo usava 40px; com um
#: card por controle, 28px mantém o grid legível sem estourar a largura).
GLYPH_SIZE: Final[int] = 28

#: Sticks: 120px com card único (paridade com o layout antigo da aba);
#: 90px quando há 2+ cards (dois controles cabem sem rolagem infinita).
STICK_SIZE_SINGLE: Final[int] = 120
STICK_SIZE_COMPACT: Final[int] = 90

#: Campo de largura fixa dos labels X/Y (BUG-STATUS-LABEL-REFLOW-01): sem o
#: padding, o texto muda de largura ao cruzar dígitos e o re-layout a 10 Hz
#: faz o painel "respirar".
_XY_MARKUP: Final[str] = (
    '<span font_family="monospace" size="small">X: {x:>3}  Y: {y:>3}</span>'
)

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
            self._montar_ui()

        # ------------------------------------------------------------------
        # API pública
        # ------------------------------------------------------------------

        def update(
            self, entry: dict[str, Any], state_global: dict[str, Any]
        ) -> None:
            """Atualiza o card a partir de ``controllers[i]`` (diff interno)."""
            self._update_titulo(entry)
            self._update_bateria(entry)
            self._update_lightbar(entry, state_global)
            self._update_degradacao(entry)
            self._update_motion(entry, state_global)
            self._update_inputs(entry.get("inputs"))

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

            corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            corpo.set_margin_top(12)
            corpo.set_margin_bottom(12)
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

            area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            self._inputs_area = area
            corpo.pack_start(area, False, False, 0)
            area.pack_start(self._montar_gatilhos(), False, False, 0)
            area.pack_start(self._montar_sticks_e_glyphs(), False, False, 0)

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

        def _montar_capsula_stick(
            self, titulo: str, rotulo_stick: str, tamanho: int
        ) -> tuple[Any, StickPreviewGtk, Any, Any]:
            caps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            caps.set_halign(Gtk.Align.CENTER)
            caps.set_valign(Gtk.Align.START)
            label_titulo = Gtk.Label()
            label_titulo.set_markup(titulo)
            label_titulo.set_xalign(0.5)
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
            caps.pack_start(label_xy, False, False, 0)
            return caps, preview, label_titulo, label_xy

        def _montar_sticks_e_glyphs(self) -> Any:
            tamanho = (
                STICK_SIZE_COMPACT if self._compact else STICK_SIZE_SINGLE
            )
            grid = Gtk.Grid()
            grid.set_column_spacing(16)
            grid.set_row_spacing(0)
            grid.set_column_homogeneous(True)

            caps_esq, stick_esq, titulo_esq, xy_esq = (
                self._montar_capsula_stick(
                    "Analógico Esquerdo (L3)", "L3", tamanho
                )
            )
            self._stick_left = stick_esq
            self._stick_left_title = titulo_esq
            self._stick_left_xy = xy_esq
            grid.attach(caps_esq, 0, 0, 1, 1)

            caps_dir, stick_dir, titulo_dir, xy_dir = (
                self._montar_capsula_stick(
                    "Analógico Direito (R3)", "R3", tamanho
                )
            )
            self._stick_right = stick_dir
            self._stick_right_title = titulo_dir
            self._stick_right_xy = xy_dir
            grid.attach(caps_dir, 1, 0, 1, 1)

            glyph_grid = Gtk.Grid()
            glyph_grid.set_row_spacing(6)
            glyph_grid.set_column_spacing(6)
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
            grid.attach(glyph_grid, 2, 0, 1, 1)
            return grid

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

        def update(
            self, entry: dict[str, Any], state_global: dict[str, Any]
        ) -> None:
            """Aplica as funções puras (mesma semântica do widget real)."""
            self.titulo = titulo_do_card(entry)
            self.rotulo, _base = rotulo_lightbar(entry, state_global)
            self.accent = accent_do_card(entry, state_global)
            self.degradacao = texto_degradacao(entry)
            self.motion = texto_motion(entry, state_global)
            self.sem_leitor = not isinstance(entry.get("inputs"), dict)

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
    "rotulo_lightbar",
    "texto_degradacao",
    "texto_motion",
    "titulo_do_card",
]
