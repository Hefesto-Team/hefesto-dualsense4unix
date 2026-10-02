"""Aba "No jogo": o que está atravessando para o jogo, recurso por recurso.

O PEDIDO DELA (09/08/2026), literal, quando perguntou como validar giroscópio
e touchpad:

    *"eu sei que a aba status é uma coisa, mas isso converter em input seja
    via xbox ou dualsense ou nativo é outra"*

Ela está certa, e o produto não sabia responder. A aba Status mostra o controle
**FÍSICO** — os sticks tremem, o giroscópio pinta barras, o touchpad acende um
ponto. Nada disso diz o que o JOGO recebe: entre o controle e o jogo há um
gamepad virtual (nas duas máscaras) ou não há nada (na Conexão Nativa, em que o
jogo abre o controle físico direto). Para saber, ela tinha de abrir o testador
da Steam.

Esta aba é a resposta, e o trabalho aqui é quase todo de TELA: os números já
subiam no ``daemon.state_full`` (``rumble_ff.per_vpad``) e a REGRA que os lê já
existia — ela mora em :func:`controller_card.estado_do_recurso`, entregue pela
PAINEL-DA-VERDADE-01 e ampliada pela ORFAOS-QUE-VOLTAM-01 e pela
MOTOR-QUE-NAO-SE-VE-01. Este módulo **chama** aquela função; não reimplementa
nem uma linha dela.

POR QUE NÃO É UMA CÓPIA DA LINHA DO CARD
----------------------------------------

O card já mostra ``resumo_do_que_chega_ao_jogo`` — uma frase corrida, ótima
para o relance ("está tudo bem?") e ruim para o gesto que ela descreveu: trocar
a máscara na aba Início, aplicar, e conferir se **movimento** e **toque**
continuam atravessando. Numa frase corrida os recursos mudam de posição
conforme mudam de situação, e comparar antes/depois vira leitura de texto.

Aqui cada recurso tem LINHA FIXA, na mesma ordem, sempre — o que muda é só a
coluna da direita. Trocar a máscara e olhar duas vezes para o mesmo lugar é o
que fecha a pergunta dela em três minutos, sem terminal e sem a Steam.

A HONESTIDADE QUE ESTE MÓDULO TEM DE MANTER
-------------------------------------------

É a mesma da PAINEL-DA-VERDADE-01, e está herdada por construção, porque as
frases nascem da função de lá: nenhuma linha afirma que o JOGO consumiu o dado
— isso depende de qual biblioteca o jogo carregou (medido em 01/08: a
``libSDL2`` do Ubuntu não enumerava o gamepad virtual; a SDL3 que a Steam
distribui enumerava). O que se afirma é o que o daemon PODE saber: o dado saiu
daqui, e alguém escreveu de volta.

E onde não há dado, a tela **cala** em vez de escrever zero. Campo ausente
vira ``None`` lá dentro e some daqui.
"""
from __future__ import annotations

from typing import Any, Final, NamedTuple

from hefesto_dualsense4unix.app.actions.contrato_da_mascara import (
    ITENS_DE_MASCARA as _FLAVOR_ITEMS,
)
from hefesto_dualsense4unix.app.actions.contrato_da_mascara import (
    ITENS_DE_MODO as _MODE_ITEMS,
)
from hefesto_dualsense4unix.app.actions.contrato_da_mascara import (
    ROTULO_RECONCILIAR as RECONCILIAR_LABEL,
)
from hefesto_dualsense4unix.app.actions.mode_transition import (
    MODE_DESKTOP,
    MODE_GAMEPAD,
    MODE_NATIVE,
    mode_of_state,
)
from hefesto_dualsense4unix.app.widgets.controller_card import (
    _NOME_NA_FRASE,
    LADO_DO_SWATCH,
    SITUACAO_CHEGANDO,
    SITUACAO_IMPOSSIVEL,
    SITUACAO_NATIVO,
    SITUACAO_NUNCA,
    SITUACAO_PARADO,
    cor_do_swatch,
    desenhar_swatch,
    estado_do_recurso,
    titulo_do_card,
)
from hefesto_dualsense4unix.utils.markup import escapar_markup

RECURSOS: Final[tuple[str, ...]] = tuple(nome for nome, _rot in _NOME_NA_FRASE)

NOME_DO_RECURSO: Final[dict[str, str]] = dict(_NOME_NA_FRASE)

LARGURA_PAINEL: Final[int] = 700

PALAVRA_DA_SITUACAO: Final[dict[str, str]] = {
    SITUACAO_CHEGANDO: "no jogo agora",
    SITUACAO_PARADO: "parou",
    SITUACAO_NUNCA: "sem pedido ainda",
}

#: * o resto é EXPLICAÇÃO, não defeito, e fica apagado: "sem pedido ainda" é o
COR_DA_SITUACAO: Final[dict[str, str]] = {
    SITUACAO_CHEGANDO: "#50fa7b",
    SITUACAO_PARADO: "#f1fa8c",
}

COR_DO_AVISO_DE_PERFIL: Final[str] = "#f1fa8c"

SITUACOES_APAGADAS: Final[frozenset[str]] = frozenset(
    {SITUACAO_NUNCA, SITUACAO_IMPOSSIVEL, SITUACAO_NATIVO}
)

_SITUACOES_MEDIDAS: Final[frozenset[str]] = frozenset(
    {SITUACAO_CHEGANDO, SITUACAO_PARADO, SITUACAO_NUNCA}
)

TEXTO_OFFLINE: Final[str] = "O Hefesto está desligado."

TEXTO_SEM_CONTROLE: Final[str] = "Nenhum controle conectado."

TEXTO_NATIVO: Final[str] = (
    "Não há controle virtual nenhum neste modo: o jogo abre o controle físico "
    "e fala direto com ele. Movimento, toque, vibração e som saem do próprio "
    "DualSense, e por isso não há aqui o que medir."
)

TEXTO_DESKTOP: Final[str] = (
    "O controle está movendo o mouse e o teclado. Enquanto estiver assim, o "
    'Hefesto não entrega controle nenhum ao jogo — troque para "Jogar pelo '
    'Hefesto" na aba Início.'
)

#: não tem um gamepad virtual casado com ele no `state_full`.
TEXTO_SEM_VPAD: Final[str] = (
    "O jogo ainda não vê este controle. Se você acabou de conectá-lo, ele entra "
    f'sozinho em alguns segundos; se demorar, use "{RECONCILIAR_LABEL}" na aba '
    "Início."
)


class LinhaDoJogo(NamedTuple):
    """Uma linha da tabela: o recurso, o que dizer dele e como pintar."""

    recurso: str
    nome: str
    situacao: str
    texto: str


def _detalhe(frase: str, nome: str) -> str:
    """O que sobra da frase da função-dona depois do nome do recurso."""
    if frase == nome:
        return ""
    if frase.startswith(nome):
        return frase[len(nome) :].strip()
    return frase


def linhas_do_controle(
    entry: dict[str, Any], state_global: dict[str, Any]
) -> list[LinhaDoJogo]:
    """As linhas de UM controle; ``[]`` = não há o que afirmar sobre ele."""
    linhas: list[LinhaDoJogo] = []
    for recurso in RECURSOS:
        estado = estado_do_recurso(recurso, entry, state_global)
        if estado is None:
            continue
        nome = NOME_DO_RECURSO[recurso]
        palavra = PALAVRA_DA_SITUACAO.get(estado.situacao)
        if palavra is None:
            texto = estado.frase
        else:
            detalhe = _detalhe(estado.frase, nome)
            texto = f"{palavra} {detalhe}" if detalhe else palavra
        linhas.append(LinhaDoJogo(recurso, nome, estado.situacao, texto))
    return linhas


def tem_controle_no_jogo(
    entry: dict[str, Any], state_global: dict[str, Any]
) -> bool:
    """True quando existe um gamepad virtual DESTE controle para medir.

    Derivado, e não um segundo dono: se ao menos um recurso chegou a uma
    situação MEDIDA (chegando/parou/sem pedido), é porque o casamento
    controle -> vpad de ``_item_do_vpad`` encontrou alguém. Perguntar
    diretamente ao ``per_vpad`` daqui seria repetir aquele casamento — e ele
    tem regra sutil (jogador 1 sem ``is_primary`` nunca casa) que já divergiu
    uma vez nesta casa quando teve duas implementações.
    """
    return any(
        linha.situacao in _SITUACOES_MEDIDAS
        for linha in linhas_do_controle(entry, state_global)
    )


def recado_do_controle(
    entry: dict[str, Any], state_global: dict[str, Any]
) -> str | None:
    """A frase que substitui as linhas; ``None`` = há linhas a mostrar."""
    if tem_controle_no_jogo(entry, state_global):
        return None
    modo = mode_of_state(state_global)
    if modo == MODE_NATIVE:
        return TEXTO_NATIVO
    if modo == MODE_DESKTOP:
        return TEXTO_DESKTOP
    return TEXTO_SEM_VPAD


def recado_global(state_global: dict[str, Any] | None) -> str | None:
    """A frase que responde pela JANELA inteira; ``None`` = é por controle."""
    if not isinstance(state_global, dict):
        return None
    modo = mode_of_state(state_global)
    if modo == MODE_NATIVE:
        return TEXTO_NATIVO
    if modo == MODE_DESKTOP:
        return TEXTO_DESKTOP
    return None


def aviso_do_perfil(state_global: dict[str, Any] | None) -> str | None:
    """O perfil que ela escreveu PARA este jogo e que não entrou. ``None`` = nada a dizer."""
    if not isinstance(state_global, dict):
        return None
    achados = state_global.get("perfil_do_jogo_que_nao_entrou")
    if not isinstance(achados, list):
        return None
    frases = [
        str(a.get("frase") or "")
        for a in achados
        if isinstance(a, dict) and a.get("frase")
    ]
    if not frases:
        return None
    ativo = state_global.get("active_profile")
    if isinstance(ativo, str) and ativo:
        frases.append(f'Enquanto isso, vale o perfil "{ativo}".')
    return "\n".join(frases)


def jogo_steam_aberto(state_global: dict[str, Any] | None) -> bool | None:
    """Há jogo da Steam aberto AGORA? ``None`` = **não dá para saber**."""
    if not isinstance(state_global, dict):
        return None
    bloco = state_global.get("jogo_steam")
    if not isinstance(bloco, dict) or bloco.get("lido") is not True:
        return None
    appid = bloco.get("appid")
    return isinstance(appid, int) and not isinstance(appid, bool)


def texto_do_contexto(state_global: dict[str, Any] | None) -> str:
    """A linha de cabeçalho da aba: em que modo e com que máscara ela está.

    É a linha que amarra esta aba à aba Início — e ela usa os rótulos DE LÁ,
    importados, para as duas abas nunca chamarem a mesma coisa por dois nomes.
    A pergunta que a aba fecha é *"funciona nos três modos?"*, então o modo tem
    de estar escrito na tela junto com a resposta.

    Sem daemon, devolve a frase de desligado: afirmar máscara nenhuma a partir
    de um payload que não existe é a família de erro que esta casa já removeu
    do `texto_do_custo_da_mascara`.

    **A DIVERGÊNCIA, quando o daemon a publica** (T3 desta sprint). O
    ``mascara_divergente`` existe no ``state_full`` desde a MASCARA-01 (19/08)
    e **não tinha um leitor na janela inteira** — o comentário que o publica
    diz *"e a GUI decide se mostra"*, e a GUI não sabia que ele existia. Ele é
    o alarme: o jogo está em cena AGORA e vê máscara diferente da que o perfil
    dele pedia. É exatamente a pergunta que esta aba existe para responder, e
    ela estava sendo respondida pela metade — a linha afirmava a máscara viva
    como se ninguém tivesse pedido outra.

    A LISTA (``mascara_divergencias``) fica de fora de propósito, e o daemon
    separa as duas chaves por isso: divergência de jogo FECHADO é antecipação,
    é normal, e escrevê-la no topo da aba ensinaria a ignorar o aviso.
    """
    if not isinstance(state_global, dict):
        return TEXTO_OFFLINE
    modo = mode_of_state(state_global)
    rotulo_do_modo = dict(_MODE_ITEMS).get(modo or "", "")
    if modo != MODE_GAMEPAD:
        return rotulo_do_modo
    gamepad = state_global.get("gamepad_emulation")
    flavor = gamepad.get("flavor") if isinstance(gamepad, dict) else None
    rotulo_da_mascara = dict(_FLAVOR_ITEMS).get(str(flavor), "")
    if not rotulo_da_mascara:
        return rotulo_do_modo
    linha = f"{rotulo_do_modo} · O jogo vê o controle como: {rotulo_da_mascara}"
    pedida = mascara_pedida_pelo_jogo_em_cena(state_global)
    if pedida is not None and pedida != rotulo_da_mascara:
        linha = f"{linha} — o perfil deste jogo pedia {pedida}"
    return linha


def mascara_pedida_pelo_jogo_em_cena(
    state_global: dict[str, Any] | None,
) -> str | None:
    """O rótulo da máscara que o perfil do jogo EM CENA pedia. ``None`` = sem"""
    if not isinstance(state_global, dict):
        return None
    gamepad = state_global.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return None
    divergente = gamepad.get("mascara_divergente")
    if not isinstance(divergente, dict):
        return None
    return dict(_FLAVOR_ITEMS).get(str(divergente.get("mascara_perfil"))) or None


def titulo_do_painel(entry: dict[str, Any]) -> str:
    """O título de um painel — o MESMO do card do controle na aba Status."""
    return titulo_do_card(entry)


try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk

    _GTK_DISPONIVEL = all(
        hasattr(Gtk, attr)
        for attr in ("Frame", "Box", "Grid", "Label", "Align", "Orientation")
    ) and hasattr(GLib, "markup_escape_text")
except (ImportError, ValueError):
    _GTK_DISPONIVEL = False


if _GTK_DISPONIVEL:

    class PainelNoJogo(Gtk.Frame):  # type: ignore[misc]
        """O painel de UM controle na aba "No jogo".

        Uso (a mixin de status monta e distribui, no molde do ControllerCard)::

            painel = PainelNoJogo()
            painel.atualizar(entry, state_full)

        Sem timer próprio: quem chama é o tique de 2 Hz que a mixin já tinha, e
        só com esta aba à vista. O gate de timers da `status_actions` conta as
        ocorrências de `GLib.timeout_add` no fonte — este widget não acrescenta
        nenhuma, de propósito.
        """

        def __init__(self) -> None:
            super().__init__()
            self._titulo = ""
            self._swatch_rgb: Any = None
            self._ultimo: tuple[Any, ...] | None = None
            self._linhas: dict[str, Any] = {}

            cabecalho = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=6
            )
            swatch = Gtk.DrawingArea()
            swatch.set_size_request(LADO_DO_SWATCH, LADO_DO_SWATCH)
            swatch.set_valign(Gtk.Align.CENTER)
            swatch.connect("draw", self._on_draw_swatch)
            self._swatch = swatch
            cabecalho.pack_start(swatch, False, False, 0)
            self._titulo_label = Gtk.Label(label=" ")
            self._titulo_label.set_xalign(0.0)
            cabecalho.pack_start(self._titulo_label, False, False, 0)
            cabecalho.show_all()
            self.set_label_widget(cabecalho)
            self.set_size_request(LARGURA_PAINEL, -1)
            self.set_halign(Gtk.Align.START)

            corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            corpo.set_margin_top(8)
            corpo.set_margin_bottom(8)
            corpo.set_margin_start(10)
            corpo.set_margin_end(10)
            self.add(corpo)

            self._grade = Gtk.Grid()
            self._grade.set_column_spacing(18)
            self._grade.set_row_spacing(4)
            corpo.pack_start(self._grade, False, False, 0)

            self._recado = Gtk.Label()
            self._recado.set_xalign(0.0)
            self._recado.set_line_wrap(True)
            self._recado.set_max_width_chars(72)
            self._recado.set_halign(Gtk.Align.START)
            self._recado.get_style_context().add_class("dim-label")
            self._recado.set_no_show_all(True)
            corpo.pack_start(self._recado, False, False, 0)

            self._montar_linhas()

        def _montar_linhas(self) -> None:
            """Cria as seis linhas UMA vez; o tique só troca texto e classe."""
            for indice, recurso in enumerate(RECURSOS):
                nome = Gtk.Label(label=NOME_DO_RECURSO[recurso])
                nome.set_xalign(0.0)
                nome.get_style_context().add_class("hefesto-rotulo")
                valor = Gtk.Label(label="")
                valor.set_xalign(0.0)
                valor.set_line_wrap(True)
                valor.set_max_width_chars(56)
                valor.set_halign(Gtk.Align.START)
                nome.set_no_show_all(True)
                valor.set_no_show_all(True)
                self._grade.attach(nome, 0, indice, 1, 1)
                self._grade.attach(valor, 1, indice, 1, 1)
                self._linhas[recurso] = (nome, valor)

        def atualizar(
            self, entry: dict[str, Any], state_global: dict[str, Any]
        ) -> None:
            """Repinta o painel a partir do ``state_full``.

            Diff no começo, como o card: repetir o mesmo estado não toca em
            widget nenhum. O que muda de fato a 2 Hz é o número do giroscópio
            e o dos motores, e mesmo assim só enquanto ela está jogando.
            """
            titulo = titulo_do_painel(entry)
            recado = recado_do_controle(entry, state_global)
            linhas = [] if recado else linhas_do_controle(entry, state_global)
            cor_do_controle = cor_do_swatch(entry)
            assinatura = (titulo, cor_do_controle, recado, tuple(linhas))
            if assinatura == self._ultimo:
                return
            self._ultimo = assinatura

            if titulo != self._titulo:
                self._titulo = titulo
                self._titulo_label.set_text(titulo)

            if cor_do_controle != self._swatch_rgb:
                self._swatch_rgb = cor_do_controle
                self._swatch.queue_draw()

            self._recado.set_text(recado or "")
            self._recado.set_visible(recado is not None)
            self._grade.set_visible(recado is None)
            por_recurso = {linha.recurso: linha for linha in linhas}
            for recurso, (rotulo, valor) in self._linhas.items():
                linha = por_recurso.get(recurso)
                visivel = linha is not None
                rotulo.set_visible(visivel)
                valor.set_visible(visivel)
                if linha is None:
                    continue
                cor = COR_DA_SITUACAO.get(linha.situacao)
                contexto = valor.get_style_context()
                if cor is None:
                    valor.set_text(linha.texto)
                    contexto.add_class("dim-label")
                else:
                    contexto.remove_class("dim-label")
                    valor.set_markup(
                        f'<span foreground="{cor}">'
                        f"{escapar_markup(linha.texto)}</span>"
                    )

        def _on_draw_swatch(self, widget: Any, ctx: Any) -> bool:
            """Ponte com o widget. O desenho é do card, e é um só."""
            desenhar_swatch(
                ctx,
                widget.get_allocated_width(),
                widget.get_allocated_height(),
                self._swatch_rgb,
            )
            return False

else:

    class PainelNoJogo:  # type: ignore[no-redef]
        """Stub sem GTK3 — guarda o resultado das funções puras."""

        def __init__(self) -> None:
            self.titulo: str | None = None
            self.cor: Any = None
            self.recado: str | None = None
            self.linhas: list[LinhaDoJogo] = []

        def atualizar(
            self, entry: dict[str, Any], state_global: dict[str, Any]
        ) -> None:
            self.titulo = titulo_do_painel(entry)
            self.cor = cor_do_swatch(entry)
            self.recado = recado_do_controle(entry, state_global)
            self.linhas = (
                [] if self.recado else linhas_do_controle(entry, state_global)
            )


__all__ = [
    "COR_DA_SITUACAO",
    "COR_DO_AVISO_DE_PERFIL",
    "LARGURA_PAINEL",
    "NOME_DO_RECURSO",
    "PALAVRA_DA_SITUACAO",
    "RECURSOS",
    "SITUACOES_APAGADAS",
    "TEXTO_DESKTOP",
    "TEXTO_NATIVO",
    "TEXTO_OFFLINE",
    "TEXTO_SEM_CONTROLE",
    "TEXTO_SEM_VPAD",
    "LinhaDoJogo",
    "PainelNoJogo",
    "aviso_do_perfil",
    "jogo_steam_aberto",
    "linhas_do_controle",
    "mascara_pedida_pelo_jogo_em_cena",
    "recado_do_controle",
    "recado_global",
    "tem_controle_no_jogo",
    "texto_do_contexto",
    "titulo_do_painel",
]
