"""Aba Lightbar + Player LEDs."""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.alvo_de_edicao import AlvoDeEdicao, alvo_de_edicao
from hefesto_dualsense4unix.app.ipc_bridge import (
    led_set_detalhado,
    player_leds_set_detalhado,
)
from hefesto_dualsense4unix.app.textos_de_aplicacao import (
    alvo_fora_da_mesa,
    coop_manda_nas_luzes,
    frase_de_guardado,
    frase_do_desfecho,
)
from hefesto_dualsense4unix.utils.i18n import _

_AVISO_HEFESTO_DESLIGADO = (
    "Não consegui aplicar a cor — o Hefesto pode estar desligado "
    "(ligue na aba Sistema)"
)

_TOAST_COR_ENVIADA = "Cor enviada ao controle ({pct}% de brilho)"

_ASSUNTO_COR = "Cor ({pct}% de brilho)"

#: por-MAC do "Aplicar no controle" logo ao lado (`led_set((0, 0, 0),
_TOAST_LIGHTBAR_APAGADA = "Lightbar apagada"
_ASSUNTO_APAGAR = "Apagar a lightbar"

_AVISO_D4 = "Cores automáticas desligadas para aplicar uma cor única"

_AVISO_SEM_DESTINATARIO = (
    "Ainda não sei quais controles estão ligados — espere um instante e "
    "tente de novo (mandar sem destinatário seria desfeito pela numeração "
    "automática)"
)

#: escolha DELA, e estão no §8 da sprint. Enquanto a resposta não vem, o
_AVISO_MESMO_DESENHO_NOS_QUATRO = (
    "O mesmo desenho foi para os {n} controles ligados."
)

_DESENHO_VAZIO: tuple[bool, bool, bool, bool, bool] = (False,) * 5


def mensagem_de_secao_fora(resposta: Any) -> str | None:
    """Frase honesta quando o daemon RESPONDEU e a cor não entrou (E2)."""
    if not isinstance(resposta, dict) or resposta.get("status") != "ok":
        return None
    secoes = footer_actions._lista_de_secoes(resposta.get("failed"))
    if secoes:
        return _("O Hefesto está ligado, mas não entrou: {secoes}").format(
            secoes=secoes
        )
    return footer_actions._mensagem_de_aplicacao(resposta)


def somar_os_corpos(corpos: list[Any]) -> dict[str, Any] | None:
    """Junta em UM corpo as N respostas de um envio por MAC ("Todos", R-14).

    BG-01 (26/08/2026). Com o alvo em "Todos" esta aba manda um pedido POR
    CONTROLE — é a R-14/R-17, e é o que faz a cor única vencer a paleta
    automática sem desligar o automático de ninguém. O daemon responde N
    vezes; a tela diz UMA frase. Somar é unir ``aplicado_em`` e ``guardado_em``
    das N respostas, sem repetir MAC e sem perder a ordem em que os controles
    foram atendidos — o mesmo vocabulário que
    ``ipc_bridge.destinos_da_aplicacao`` lê, e que
    ``textos_de_aplicacao.frase_do_desfecho`` decide.

    Somar em vez de olhar só a primeira resposta importa na mesa cheia dela:
    com dois controles na mesa e um terceiro que caiu, a soma diz *aplicado em
    2* e *guardado em 1* — escolher uma resposta ao acaso diria uma das duas
    metades como se fosse a história inteira.

    Devolve ``None`` quando NENHUMA das N respostas veio (daemon desligado,
    transporte): aí não há corpo a ler, e quem chama cai na frase de sempre.
    Uma resposta que não é dicionário é ignorada pelo mesmo motivo que
    ``_corpo_do_daemon`` a descarta — não é o daemon falando.

    ``motivo`` não é somado, e é medido: nem ``led.set`` nem
    ``led.player_set`` publicam esse campo (``daemon/ipc_handlers.py``, os dois
    devolvem ``status``/``aplicado_em``/``guardado_em``, mais ``bits`` no
    segundo). Se um dia publicarem, esta função tem de crescer junto — está
    escrito aqui de propósito, em vez de descoberto na tela.
    """
    aplicado_em: list[str] = []
    guardado_em: list[str] = []
    houve_resposta = False
    for corpo in corpos:
        if not isinstance(corpo, dict):
            continue
        houve_resposta = True
        aplicado, guardado = ipc_bridge.destinos_da_aplicacao(corpo)
        for mac in aplicado:
            if mac not in aplicado_em:
                aplicado_em.append(mac)
        for mac in guardado:
            if mac not in guardado_em:
                guardado_em.append(mac)
    if not houve_resposta:
        return None
    return {
        "status": "ok",
        "aplicado_em": aplicado_em,
        "guardado_em": guardado_em,
    }


def frase_do_envio(
    assunto: str,
    enviado: str,
    corpo: Any,
    host: Any,
    *,
    coop_aplica: bool = False,
) -> str:
    """A frase do gesto decidida pelo CORPO do daemon (BG-01, 26/08/2026).

    **Quem decide é ``textos_de_aplicacao.frase_do_desfecho``, e só ele.** Esta
    função não lê ``aplicado_em``, não conhece a ordem das razões e não tem
    opinião sobre ramo nenhum: ela chama o dono da decisão e, no ramo do
    APLICADO — e só nele —, devolve a frase que esta aba já tinha.

    **Por que a troca de palavra, e por que ela não é preferência.** O ramo do
    aplicado sai de lá como *"<assunto> aplicado"*, e "aplicada" é uma
    afirmação que esta aba MEDIU como falsa: LIGHTBAR-BT-RESET-01 (17-18/07,
    ainda em vigor em 09/08) — por Bluetooth, depois que o daemon adota o
    controle, o firmware ACEITA E IGNORA as escritas de cor; foram 330 mil
    escritas ignoradas com a barra apagada. O que o daemon sabe é que o byte
    saiu no fio, que é exatamente o que "enviada" diz e "aplicada" não. A
    decisão está registrada em ``_TOAST_COR_ENVIADA``, com a medição; trocar a
    palavra aqui seria desfazê-la em silêncio.

    **Se o ramo do aplicado mudar de forma lá, esta função para de reconhecê-lo**
    e a frase de lá aparece na tela com a palavra que esta aba recusa. É um
    acoplamento REAL, e por isso ele tem régua: ``test_a_regua_do_ramo_aplicado``
    em ``tests/unit/test_aplicar_verdade_ponte_lightbar.py`` reprova no dia em
    que as duas formas divergirem, em vez de a divergência sair na tela dela.

    ``coop_aplica`` viaja intacto: só quem escreve os 5 LEDs de jogador o passa
    ``True`` (``_COOP_LAYER_FIELDS = ("player_leds",)`` no backend), e a cor da
    lightbar nunca foi governada pelo co-op.

    ``nativo_aplica=False`` SEMPRE, e é a decisão dela de 23/09/2026
    (`D-2309-NO-NATIVO-A-LUZ-E-O-NUMERO-SAO-DO-HEFESTO`): no Modo Nativo o
    Hefesto escreve a barra e o número, e esta aba só fala dos dois.
    """
    frase = frase_do_desfecho(
        assunto, corpo, host, coop_aplica=coop_aplica, nativo_aplica=False
    )
    return enviado if frase.startswith(f"{assunto} aplicado") else frase


def nome_do_desenho(bits: tuple[bool, ...] | list[bool]) -> str | None:
    """"desenho do P3" quando ``bits`` é um padrão canônico; ``None`` se não.

    Os padrões vêm de ``core.led_control.player_led_pattern`` — a MESMA fonte
    que o daemon usa para acender, para a janela nunca batizar de "P3" um
    desenho que o hardware não chamaria assim. A varredura vai até 8 porque o
    espaço de numeração é único entre DualSense, externos e co-op (R-24/R-25)
    e um DualSense pode legitimamente cair no 5 ou acima.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    alvo = tuple(bool(b) for b in bits)
    for numero in range(1, 9):
        if tuple(player_led_pattern(numero)) == alvo:
            return f"desenho do P{numero}"
    return None


_PREFIXO_DESENHO = "Desenho que mandamos"


def texto_do_desenho_aceso(
    player_leds: tuple[bool, ...] | list[bool],
    slot: int | None,
    *,
    coop_ligado: bool = False,
    descricao_livre: str = "",
) -> str:
    """A frase do desenho das 5 luzes EM VIGOR (PLAYER-01 entrega 5, L5)."""
    if coop_ligado:
        return (
            f"{_PREFIXO_DESENHO}: o do co-op — com o co-op ligado, é ele que "
            "manda nas 5 luzes."
        )
    bits = tuple(bool(b) for b in player_leds)
    if bits != _DESENHO_VAZIO:
        nome = nome_do_desenho(bits) or descricao_livre or "desenho próprio"
        return f"{_PREFIXO_DESENHO}: {nome} — escolha sua."
    if isinstance(slot, int) and slot >= 1:
        return (
            f"{_PREFIXO_DESENHO}: desenho do P{slot} — automático, do número "
            "deste controle."
        )
    return (
        f"{_PREFIXO_DESENHO}: o desenho automático do número do controle "
        "(nenhuma escolha sua)."
    )


class LightbarActionsMixin(WidgetAccessMixin):
    """Controla a aba Lightbar + Player LEDs."""

    _current_rgb: tuple[int, int, int] = (255, 128, 0)
    _current_brightness: float = 1.0
    _pending_brightness: float = 1.0
    _refresh_guard: bool = False
    _brilho_pendente: bool = False
    _soltar_fiado: bool = False

    def _uniqs_conectados(self) -> list[str]:
        """MACs dos controles CONECTADOS, na ordem do índice (R-14).

        Fonte: ``_target_uniq_by_index``, o mapa que a aba Status recalcula do
        ``state_full`` a cada tick (só controles conectados entram). Controle
        sem MAC estável (handle por path) fica de fora — para ele não existe
        override por-controle, e a escrita dele continua sendo a global.

        Lista vazia = a GUI ainda não sabe quem está na mesa (nenhum tick do
        daemon, host parcial de teste). Os chamadores tratam isso como
        "escopo desconhecido" e caem no caminho global de sempre, nunca em
        broadcast disfarçado de por-controle.
        """
        mapa = getattr(self, "_target_uniq_by_index", None)
        if not isinstance(mapa, dict):
            return []
        vistos: set[str] = set()
        saida: list[str] = []
        for _idx, uniq in sorted(mapa.items(), key=lambda kv: kv[0]):
            if isinstance(uniq, str) and uniq and uniq not in vistos:
                vistos.add(uniq)
                saida.append(uniq)
        return saida

    def _edit_uniq(self) -> AlvoDeEdicao:
        """O alvo de edição (PERFIL-04), com o estado explícito ao lado do MAC."""
        return alvo_de_edicao(self)

    def _auto_preview_slot(self) -> int | None:
        """Slot do controle em edição QUANDO a prévia deve mostrar a cor
        AUTOMÁTICA (achado ao vivo 2026-07-17).

        Com "Cores automáticas por controle" LIGADO e um controle específico
        selecionado no seletor do banner, o que ele EXIBE é a cor da paleta
        (azul/vermelho...), não a cor manual global — mas a prévia mostrava a
        manual (roxo), MENTINDO. ``None`` = mostrar a cor manual (automático
        desligado, alvo "Todos", ou número desconhecido).

        L7 (25/08/2026) — o número vem de ``_edit_target_slot``, o número
        CANÔNICO do alvo, mantido pela aba Status a partir do ``state_full``
        (``status_actions.py:1283``) e já usado por
        ``_atualizar_estado_das_luzes`` sete linhas abaixo. A leitura anterior
        era uma expressão regular sobre o TEXTO do rótulo do cabeçalho
        (``re.search(r"Controle\\s+(\\d+)", _edit_target_label)``), e esse
        rótulo é ``translatable="yes"``: em inglês ele vira "Controller 2", a
        busca falha, a função devolve ``None`` e a prévia volta a mostrar a
        cor manual — **o defeito exato de 17/07 ressuscitado por um idioma**.
        Uma cura que morre ao traduzir a interface não é cura.

        O ``getattr`` defensivo FICA: os mixins só convivem de fato na
        instância composta, e sem slot conhecido a resposta continua sendo
        ``None`` (mostrar a cor manual), exatamente como antes.
        """
        draft = getattr(self, "draft", None)
        if draft is None or not draft.leds.auto_player_colors:
            return None
        if self._edit_uniq().uniq is None:
            return None
        slot = getattr(self, "_edit_target_slot", None)
        if isinstance(slot, int) and not isinstance(slot, bool) and slot >= 1:
            return slot
        return None

    def _persist_leds_update(self, update: dict[str, Any]) -> bool:
        """Grava campos de LEDs no draft — no GLOBAL ou no override do alvo.

        PERFIL-04 (sprint perfis-por-controle): com um controle selecionado
        no seletor do banner, a edição cai em ``draft.controllers[uniq].leds``
        — semeada com o que está NA TELA (o efetivo do alvo), então mudar só
        a cor preserva brilho/player-LEDs exibidos. É o que faz o "Salvar
        Perfil" do rodapé persistir o ajuste DENTRO do perfil, por controle
        ("configurei pro 1-BT, fica salvo pra ele dentro do meu perfil").

        Em "Todos", seção global do draft — E o campo editado sai dos
        overrides por-controle (fix HIGH do review 2026-07-16), espelhando a
        regra que o backend aplica ao vivo: sem a limpeza, "mudei todos para
        azul" + "Salvar Perfil" ressuscitava a cor antiga do alvo na próxima
        ativação. Cor e brilho saem JUNTOS (formam um único campo — o RGB
        pré-escalado — no estado desejado do backend).

        COR-04 (semântica D4): COR (``lightbar_rgb``) editada em "Todos" com
        o automático ligado também DESLIGA ``auto_player_colors`` no draft —
        senão a cor única seria invisível (a paleta automática vence o global
        no merge). Brilho NÃO dispara o D4 (o brilho escala a própria paleta
        — D11). ONDA-U (U9): ``player_leds`` (clique manual de player-LED)
        AGORA também dispara o D4 — antes só ``lightbar_rgb`` disparava, e a
        paleta automática (COR-03) reescrevia o player-LED por cima no
        próximo merge do backend, fazendo o clique manual parecer que "não
        funciona". Devolve True quando o D4 desligou o automático AGORA (o
        chamador compõe o aviso ``_AVISO_D4`` no toast — visível, nunca
        popup); o checkbox da aba é sincronizado aqui mesmo, sob guard.

        R-14 (auditoria 23/07) — o D4 vira EXCEÇÃO, não regra. Desligar
        ``auto_player_colors`` é o martelo mais pesado que a aba tem: além da
        paleta, o flag governava a numeração dos DualSense E a dos externos
        (Pro Nintendo/8BitDo paravam de receber número), e o valor ainda ia
        para o JSON do perfil — um clique de cor em "Todos" apagava a
        identidade automática de todo mundo, para sempre. Com os controles
        CONECTADOS conhecidos, o mesmo desejo ("esta cor/este padrão em todo
        mundo") é expresso como OVERRIDE POR-MAC em cada um deles: override
        vence a camada automática no merge por campo do backend (D5), então a
        cor única aparece **sem** desligar nada e a numeração continua viva.
        A ordem importa: os overrides são escritos ANTES de o global mudar,
        porque ``with_controller_leds`` só guarda o que DIVERGE do global — se
        o global já tivesse o valor novo, o override seria podado e a paleta
        automática voltaria a vencer (a cor "não pegaria").

        ABAS-02 (25/07) — a limpeza é do campo EDITADO, e só dele. Cor e brilho
        saíam JUNTOS dos overrides (formam um único campo no estado desejado do
        backend: o RGB pré-escalado), mas o brilho não tem alvo para re-semear
        (ele não disputa com o automático, então ``alvos`` fica vazio neste
        ramo). Efeito medido: com o alvo em "Todos", arrastar o controle de
        brilho UM PIXEL apagava o campo de cor de TODOS os ajustes por controle
        — Controle 1 azul e Controle 2 vermelho viravam nada — e o evento
        dispara a cada movimento do arraste, então bastava encostar. Limpando
        só o campo editado, o brilho global passa a valer em todo mundo (que é
        o que "Todos" quer dizer) e a cor própria de cada controle sobrevive: a
        emissão por campo de ``_controllers_to_ipc`` resolve o brilho do GLOBAL
        quando o override fala só de cor, e o merge por campo do backend faz o
        mesmo na ativação. A recíproca também melhora — editar a COR em "Todos"
        deixa de apagar o brilho próprio de quem tem um.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return False
        estado_alvo = self._edit_uniq()
        if estado_alvo.desconhecido:
            return False
        uniq = estado_alvo.uniq
        if uniq is None:
            campos: set[str] = set()
            if "lightbar_rgb" in update:
                campos.add("lightbar")
            if "lightbar_brightness" in update:
                campos.add("lightbar_brightness")
            if "player_leds" in update:
                campos.add("player_leds")
            disputa_com_o_auto = "lightbar_rgb" in update or "player_leds" in update
            alvos = self._uniqs_conectados() if disputa_com_o_auto else []
            campos_update = dict(update)
            d4_disparou = bool(
                disputa_com_o_auto and draft.leds.auto_player_colors and not alvos
            )
            if d4_disparou:
                campos_update["auto_player_colors"] = False
            if campos:
                draft = draft.with_override_fields_cleared("leds", campos)
            for alvo in alvos:
                base = draft.effective_leds_for(alvo)
                draft = draft.with_controller_leds(
                    alvo, base.model_copy(update=update)
                )
            new_leds = draft.leds.model_copy(update=campos_update)
            draft = draft.model_copy(update={"leds": new_leds})
            self.draft = draft
            if d4_disparou:
                self._sync_auto_checkbox(False)
            return d4_disparou
        base = draft.effective_leds_for(uniq)
        self.draft = draft.with_controller_leds(uniq, base.model_copy(update=update))
        return False

    def _refresh_lightbar_from_draft(self) -> None:
        """Popula widgets da aba Lightbar a partir do draft."""
        if self._refresh_guard:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        self._refresh_guard = True
        try:
            leds = draft.effective_leds_for(self._edit_uniq().uniq)
            auto_check: Gtk.CheckButton = self._get("auto_player_colors_check")
            if auto_check is not None:
                auto_check.set_active(bool(draft.leds.auto_player_colors))
            if leds.lightbar_rgb is not None:
                r, g, b = leds.lightbar_rgb
                self._current_rgb = (r, g, b)
                button: Gtk.ColorButton = self._get("lightbar_color_button")
                if button is not None:
                    rgba = Gdk.RGBA()
                    rgba.red = r / 255.0
                    rgba.green = g / 255.0
                    rgba.blue = b / 255.0
                    rgba.alpha = 1.0
                    button.set_rgba(rgba)
            auto_slot = self._auto_preview_slot()
            if auto_slot is not None:
                from hefesto_dualsense4unix.core.led_control import player_slot_color

                self._current_rgb = player_slot_color(auto_slot)
                auto_btn: Gtk.ColorButton = self._get("lightbar_color_button")
                if auto_btn is not None:
                    ar, ag, ab = self._current_rgb
                    auto_rgba = Gdk.RGBA()
                    auto_rgba.red = ar / 255.0
                    auto_rgba.green = ag / 255.0
                    auto_rgba.blue = ab / 255.0
                    auto_rgba.alpha = 1.0
                    auto_btn.set_rgba(auto_rgba)
            pct = float(leds.lightbar_brightness)
            self._current_brightness = pct / 100.0
            self._pending_brightness = self._current_brightness
            scale: Gtk.Scale = self._get("lightbar_brightness_scale")
            if scale is not None:
                scale.set_value(pct)
            for i, state in enumerate(leds.player_leds, start=1):
                checkbox: Gtk.CheckButton = self._get(f"player_led_{i}")
                if checkbox is not None:
                    checkbox.set_active(bool(state))
            self._atualizar_estado_das_luzes(leds.player_leds)
            self._atualizar_estado_da_barra()
            preview: Gtk.DrawingArea = self._get("lightbar_preview")
            if preview is not None:
                preview.queue_draw()
        finally:
            self._refresh_guard = False

    def _atualizar_estado_da_barra(self) -> None:
        """Escreve no rótulo ``lightbar_estado_no_controle`` o que o daemon sabe.

        **L6 (25/08/2026) — a aba da barra era a ÚNICA do produto que não lia
        nada do que o produto já sabe sobre a barra.** Medido:

        ``grep -rln "lightbar_source\\|lightbar_disputada\\|lightbar_on"
        src/hefesto_dualsense4unix/app/`` devolvia **um** arquivo, e era
        ``widgets/controller_card.py`` — o card, que mora na Status, na Início
        e na "No jogo". Consequência direta: quem está na aba da COR era
        justamente quem não era avisado de que a Steam segura o ``hidraw``
        deste controle (``lightbar_disputada``, ESCRITOR-CRU-01) nem de que o
        valor exibido é o que o Hefesto PEDIU, não o que a lâmpada faz
        (``lightbar_source``).

        **A interpretação é REUSADA, não reescrita.** A frase sai de
        ``widgets/controller_card.rotulo_lightbar``, a mesma que os cards já
        usam, com a mesma ordem de precedência (Modo Nativo → disputa →
        fonte desconhecida → apagada). Escrever uma segunda leitura destes
        campos aqui seria o defeito F5 nascendo dentro da própria cura: duas
        semânticas para ``lightbar_source`` no mesmo produto.

        **Quando o rótulo SOME**, e é regra, não descuido: sem alvo por
        controle ("Todos" ou alvo desconhecido), sem daemon, com o controle
        fora do bloco ``controllers``, ou quando ``rotulo_lightbar`` não tem
        aviso a dar (cor conhecida e acesa) — aí a prévia ao lado já diz tudo,
        e um aviso sem conteúdo é ruído. Um "não sei" **não** vira aviso: é a
        mesma disciplina que a `secao_controles` já aplica.
        """
        rotulo = self._get("lightbar_estado_no_controle")
        if rotulo is None:
            return
        texto = self._texto_do_estado_da_barra()
        rotulo.set_text(texto or "")
        if texto:
            rotulo.show()
        else:
            rotulo.hide()

    def _texto_do_estado_da_barra(self) -> str | None:
        """O aviso da barra para o controle EM EDIÇÃO; ``None`` = nenhum (L6).

        Uma leitura por repintura da aba, nunca por tique: quem chama é
        ``_refresh_lightbar_from_draft``, que roda ao ENTRAR na aba
        (``app._REFRESH_POR_ABA``), ao trocar de alvo, ao trocar de perfil e
        na transição do co-op. A chamada síncrona ao ``daemon.state_full``
        segue o precedente de
        ``daemon_actions._refresh_window_detect_diag``: leitura read-only do
        ``state_full``, feita de dentro do refresh da aba, com o corpo inteiro
        num ``try`` — porque linha informativa não derruba aba
        (DIAGNÓSTICO-NAO-DERRUBA-A-ABA-01). O precedente que esta linha citava
        antes foi apagado pela T-12 em 25/08/2026, por ser código sem chamador;
        o nome dele não se repete aqui de propósito — há portão que reprova
        símbolo morto ressuscitado em prosa.
        """
        from hefesto_dualsense4unix.app.mesa import controles_conectados
        from hefesto_dualsense4unix.app.widgets.controller_card import (
            rotulo_lightbar,
        )

        uniq = self._edit_uniq().uniq
        if uniq is None:
            return None
        try:
            state = ipc_bridge.daemon_state_full()
        except Exception:
            return None
        if not isinstance(state, dict):
            return None
        for entrada in controles_conectados(state):
            if entrada.get("uniq") == uniq:
                texto, _cor = rotulo_lightbar(entrada, state)
                return texto
        return None

    def _atualizar_estado_das_luzes(
        self, player_leds: tuple[bool, ...] | list[bool]
    ) -> None:
        """Escreve no rótulo ``player_leds_estado`` o desenho ACESO (PLAYER-01).

        O número do alvo (``_edit_target_slot``) e o estado do co-op
        (``_coop_ligado``) são mantidos pela aba Status a partir do
        ``state_full`` — ``getattr`` defensivo porque os mixins só convivem de
        fato na instância composta, nunca isolados nos testes. Sem os dois, a
        frase degrada para "o automático manda", que continua sendo verdade.
        """
        rotulo = self._get("player_leds_estado")
        if rotulo is None:
            return
        rotulo.set_text(
            texto_do_desenho_aceso(
                player_leds,
                getattr(self, "_edit_target_slot", None),
                coop_ligado=bool(getattr(self, "_coop_ligado", False)),
                descricao_livre=self._descreve_player_leds(list(player_leds)),
            )
        )

    def install_lightbar_tab(self) -> None:
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.connect("draw", self._on_lightbar_preview_draw)
        button: Gtk.ColorButton = self._get("lightbar_color_button")
        if button is not None:
            rgba = Gdk.RGBA()
            rgba.red = 1.0
            rgba.green = 128 / 255
            rgba.blue = 0.0
            rgba.alpha = 1.0
            button.set_rgba(rgba)
            self._current_rgb = (255, 128, 0)
        auto_check: Gtk.CheckButton = self._get("auto_player_colors_check")
        if auto_check is not None:
            auto_check.connect("toggled", self.on_auto_player_colors_toggled)
        reset_target: Gtk.Button = self._get("lightbar_auto_reset_target")
        if reset_target is not None:
            reset_target.connect("clicked", self.on_lightbar_auto_reset_target)
        reset_all: Gtk.Button = self._get("lightbar_auto_reset_all")
        if reset_all is not None:
            reset_all.connect("clicked", self.on_lightbar_auto_reset_all)
        self._fiar_aplicar_ao_soltar()

    def _fiar_aplicar_ao_soltar(self) -> None:
        """Liga o "acende ao SOLTAR" da cor e do brilho (BOTÃO-QUE-NÃO-MENTE-01)."""
        if self._soltar_fiado:
            return
        botao_cor: Gtk.ColorButton = self._get("lightbar_color_button")
        if botao_cor is not None:
            botao_cor.connect("color-set", self._on_lightbar_cor_solta)
        escala: Gtk.Scale = self._get("lightbar_brightness_scale")
        if escala is not None:
            escala.connect("button-release-event", self._on_lightbar_brilho_solto)
            escala.connect("key-release-event", self._on_lightbar_brilho_solto)
        self._soltar_fiado = True

    def _on_lightbar_cor_solta(self, _botao: Any = None) -> None:
        """Cor confirmada no diálogo -> acende no controle AGORA (entrega 1)."""
        if self._refresh_guard:
            return
        # O brilho da tela vai junto na mesma escrita (cor e brilho são um
        self._brilho_pendente = False
        self._aplicar_cor_no_controle()

    def _on_lightbar_brilho_solto(
        self, _widget: Any = None, _evento: Any = None
    ) -> bool:
        """Soltou o controle deslizante de brilho -> UMA escrita (entrega 1)."""
        if self._refresh_guard:
            return False
        if not self._brilho_pendente:
            return False
        self._brilho_pendente = False
        self._aplicar_cor_no_controle()
        return False


    def on_lightbar_color_set(self, button: Gtk.ColorButton) -> None:
        if self._refresh_guard:
            return
        rgba = button.get_rgba()
        self._current_rgb = (
            int(rgba.red * 255),
            int(rgba.green * 255),
            int(rgba.blue * 255),
        )
        if self._persist_leds_update({"lightbar_rgb": self._current_rgb}):
            self._toast_light(_AVISO_D4)
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.queue_draw()

    def on_lightbar_apply(self, _btn: Gtk.Button) -> None:
        """Botão "Aplicar no controle" — reenvia a cor da tela ao hardware.

        Continua existindo depois da entrega 1 do BOTÃO-QUE-NÃO-MENTE-01 (a
        cor já acende ao soltar o seletor): é o reenvio explícito, útil depois
        de reconectar um controle ou trocar de alvo no seletor do banner, e é
        o botão que os textos da tela citam. Um único caminho de escrita para
        os dois gestos — ``_aplicar_cor_no_controle``.
        """
        self._aplicar_cor_no_controle()

    def _aplicar_cor_no_controle(self) -> bool:
        """Envia a cor da tela ao hardware. Devolve True quando todos aceitaram."""
        estado_alvo = self._edit_uniq()
        if estado_alvo.desconhecido:
            self._toast_light(estado_alvo.recusa() or _AVISO_HEFESTO_DESLIGADO)
            return False
        pct = round(self._current_brightness * 100)
        draft = getattr(self, "draft", None)
        d4_disparou = False
        resposta: Any = None
        corpo: Any = None
        alvos = self._uniqs_conectados() if estado_alvo.uniq is None else []
        if estado_alvo.uniq is None and alvos:
            ok, corpo = self._enviar_led_em_todos(
                self._current_rgb, self._current_brightness, alvos
            )
        elif estado_alvo.uniq is None and draft is not None:
            d4_disparou = self._d4_disable_auto_for_single_color()
            resposta = ipc_bridge.apply_draft_detalhado(
                {
                    "leds": {
                        "lightbar_rgb": list(self._current_rgb),
                        "lightbar_brightness": self._current_brightness,
                        "auto_player_colors": self.draft.leds.auto_player_colors,
                    }
                }
            )
            ok = ipc_bridge.aplicacao_confirmada(resposta)
        else:
            # PERFIL-05 (22/07): com um controle selecionado, o MAC viaja no
            corpo = led_set_detalhado(
                self._current_rgb,
                brightness=self._current_brightness,
                uniq=estado_alvo.uniq,
            )
            # BG-01: `None` é a MESMA resposta que o `led_set` dava como
            ok = corpo is not None
        if not ok:
            msg = mensagem_de_secao_fora(resposta) or _AVISO_HEFESTO_DESLIGADO
        elif corpo is not None:
            # (dentro de `frase_do_desfecho`), nunca mais a decisão.
            # `coop_aplica` fica no padrão `False`, e é medido: a camada do
            msg = frase_do_envio(
                _ASSUNTO_COR.format(pct=pct),
                _TOAST_COR_ENVIADA.format(pct=pct),
                corpo,
                self,
            )
        else:
            # `frase_do_desfecho` não faz. Está relatado como o que sobrou.
            msg = frase_de_guardado(
                _ASSUNTO_COR.format(pct=pct),
                alvo_ausente=alvo_fora_da_mesa(self),
            ) or _TOAST_COR_ENVIADA.format(pct=pct)
        if d4_disparou:
            msg = f"{_AVISO_D4} — {msg}"
        self._toast_light(msg)
        return bool(ok)

    def on_lightbar_brightness_changed(self, scale: Gtk.Scale) -> None:
        """Controle deslizante 0-100 (%) -> luminosidade corrente e prévia."""
        if self._refresh_guard:
            return
        raw = float(scale.get_value())
        pct = max(0.0, min(100.0, raw))
        self._current_brightness = pct / 100.0
        self._pending_brightness = self._current_brightness
        self._persist_leds_update({"lightbar_brightness": round(pct)})
        self._brilho_pendente = True
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.queue_draw()

    def on_lightbar_off(self, _btn: Gtk.Button) -> None:
        estado_alvo = self._edit_uniq()
        if estado_alvo.desconhecido:
            self._toast_light(estado_alvo.recusa() or _AVISO_HEFESTO_DESLIGADO)
            return
        self._current_rgb = (0, 0, 0)
        rgba = Gdk.RGBA()
        rgba.red = 0.0
        rgba.green = 0.0
        rgba.blue = 0.0
        rgba.alpha = 1.0
        button: Gtk.ColorButton = self._get("lightbar_color_button")
        if button is not None:
            button.set_rgba(rgba)
        d4_disparou = self._persist_leds_update({"lightbar_rgb": self._current_rgb})
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.queue_draw()
        draft = getattr(self, "draft", None)
        # `_aplicar_cor_no_controle` — "Apagar" é aplicar a cor preta e mente
        resposta: Any = None
        # BG-01: idem `_aplicar_cor_no_controle` — o corpo do `led.set`.
        corpo: Any = None
        alvos = self._uniqs_conectados() if estado_alvo.uniq is None else []
        if estado_alvo.uniq is None and alvos:
            ok, corpo = self._enviar_led_em_todos((0, 0, 0), None, alvos)
        elif estado_alvo.uniq is None and draft is not None:
            resposta = ipc_bridge.apply_draft_detalhado(
                {
                    "leds": {
                        "lightbar_rgb": [0, 0, 0],
                        "auto_player_colors": draft.leds.auto_player_colors,
                    }
                }
            )
            ok = ipc_bridge.aplicacao_confirmada(resposta)
        else:
            corpo = led_set_detalhado((0, 0, 0), uniq=estado_alvo.uniq)
            ok = corpo is not None
        if not ok:
            msg = mensagem_de_secao_fora(resposta) or "Falha (daemon offline?)"
        elif corpo is not None:
            msg = frase_do_envio(
                _ASSUNTO_APAGAR, _TOAST_LIGHTBAR_APAGADA, corpo, self
            )
        else:
            # COR-04: ver o comentário homônimo em `_aplicar_cor_no_controle`.
            msg = frase_de_guardado(
                _ASSUNTO_APAGAR,
                alvo_ausente=alvo_fora_da_mesa(self),
            ) or _TOAST_LIGHTBAR_APAGADA
        if d4_disparou:
            msg = f"{_AVISO_D4} — {msg}"
        self._toast_light(msg)


    def on_auto_player_colors_toggled(self, checkbox: Gtk.CheckButton) -> None:
        """Checkbox "Cores automáticas por controle" → ``draft.leds``."""
        if self._refresh_guard:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        ativo = bool(checkbox.get_active())
        if bool(draft.leds.auto_player_colors) == ativo:
            return
        self.draft = draft.model_copy(
            update={
                "leds": draft.leds.model_copy(update={"auto_player_colors": ativo})
            }
        )
        if ativo:
            self._toast_light(
                "Cores automáticas ligadas — cores escolhidas por controle "
                "continuam valendo onde existirem"
            )
        else:
            self._toast_light(
                "Cores automáticas desligadas — vale a cor única do perfil"
            )

    def on_lightbar_auto_reset_target(self, _btn: Gtk.Button) -> None:
        """"Voltar ao automático" — remove a cor explícita do ALVO selecionado.

        Só a cor (``lightbar`` + ``lightbar_brightness``, que formam UM campo
        no backend) sai do override do controle; player-LEDs e gatilhos
        próprios ficam. A automática volta a valer nele no próximo Aplicar
        (ou na próxima ativação do perfil salvo). Com o alvo em "Todos" não
        há controle selecionado: orienta pelo toast, sem popup.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        uniq = self._edit_uniq().uniq
        if uniq is None:
            self._toast_light(
                'Sem um controle escolhido, use o botão '
                '"Voltar todos ao automático".'
            )
            return
        self.draft = draft.with_controller_fields_cleared(
            uniq, "leds", {"lightbar", "lightbar_brightness"}
        )
        self._refresh_lightbar_from_draft()
        if self.draft.leds.auto_player_colors:
            self._toast_light(
                "Cor própria removida — a cor automática volta a valer "
                "neste controle no próximo Aplicar"
            )
        else:
            self._toast_light(
                'Cor própria removida — ligue "Cores automáticas por '
                'controle" para valer a paleta'
            )

    def on_lightbar_auto_reset_all(self, _btn: Gtk.Button) -> None:
        """"Voltar todos ao automático" — limpa as cores explícitas e religa o auto.

        Remove ``lightbar``/``lightbar_brightness`` de TODOS os overrides
        por-controle do draft (player-LEDs e gatilhos explícitos ficam) e
        religa ``auto_player_colors`` — a paleta automática volta a valer em
        todo mundo no próximo Aplicar/Salvar.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        novo = draft.with_override_fields_cleared(
            "leds", {"lightbar", "lightbar_brightness"}
        )
        novo = novo.model_copy(
            update={"leds": novo.leds.model_copy(update={"auto_player_colors": True})}
        )
        self.draft = novo
        self._refresh_lightbar_from_draft()
        self._toast_light(
            "Cores automáticas religadas para todos os controles — aplique "
            "ou salve o perfil para valer"
        )

    def _enviar_led_em_todos(
        self,
        rgb: tuple[int, int, int],
        brightness: float | None,
        alvos: list[str],
    ) -> tuple[bool, dict[str, Any] | None]:
        """``led.set`` por MAC em cada controle conectado (R-14)."""
        corpos = [
            led_set_detalhado(rgb, brightness=brightness, uniq=alvo)
            for alvo in alvos
        ]
        return all(corpo is not None for corpo in corpos), somar_os_corpos(corpos)

    def _enviar_player_leds(
        self, bits: tuple[bool, bool, bool, bool, bool]
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Envia o desenho das 5 luzes ao alvo certo (R-14/R-17/PLAYER-01)."""
        estado_alvo = self._edit_uniq()
        if estado_alvo.desconhecido:
            return False, estado_alvo.recusa(), None
        if estado_alvo.uniq is not None:
            corpo = player_leds_set_detalhado(bits, uniq=estado_alvo.uniq)
            return corpo is not None, None, corpo
        alvos = self._uniqs_conectados()
        if not alvos:
            return False, _AVISO_SEM_DESTINATARIO, None
        corpos = [player_leds_set_detalhado(bits, uniq=alvo) for alvo in alvos]
        return (
            all(corpo is not None for corpo in corpos),
            None,
            somar_os_corpos(corpos),
        )

    def _d4_disable_auto_for_single_color(self) -> bool:
        """D4 fora do ``_persist_leds_update``: desliga o auto no draft."""
        draft = getattr(self, "draft", None)
        if draft is None or not draft.leds.auto_player_colors:
            return False
        self.draft = draft.model_copy(
            update={"leds": draft.leds.model_copy(update={"auto_player_colors": False})}
        )
        self._sync_auto_checkbox(False)
        return True

    def _sync_auto_checkbox(self, active: bool) -> None:
        """Reflete ``active`` no checkbox SEM disparar o handler (guard)."""
        check: Gtk.CheckButton = self._get("auto_player_colors_check")
        if check is None:
            return
        prev = self._refresh_guard
        self._refresh_guard = True
        try:
            check.set_active(active)
        finally:
            self._refresh_guard = prev


    def aplicar_desenho_do_jogador(self, numero: int) -> None:
        """Aplica o desenho CANÔNICO do jogador ``numero`` (L9, 25/08/2026).

        **A fiação que faltava.** Os quatro botões "Desenho do P1..P4" traziam
        o padrão escrito à mão — ``[False, True, False, True, False]`` e os
        outros três — enquanto ``core/led_control.player_led_pattern`` já é a
        tabela canônica que o DAEMON usa para acender, cobre **1..8** (R-25,
        porque o espaço de numeração é único entre DualSense, externos e co-op
        — R-24) e ainda tem padrão de overflow para ≥9. Literal e tabela eram
        duas cópias independentes que nada amarrava: mudar a tabela deixava os
        botões pintando o desenho antigo, sem um único teste vermelho. O mesmo
        arquivo já lia a tabela em ``nome_do_desenho`` para BATIZAR o desenho —
        então a aba nomeava por uma fonte e pintava por outra.

        Ela também é o que torna baratas as duas respostas possíveis da
        pergunta que é DELA (§8 da sprint): quantos botões de desenho aparecem
        — sempre oito, ou só até o maior número vivo na mesa. Esta entrega é a
        fiação; **quantos botões existem na tela continua sendo escolha dela**,
        e por isso o glade segue com os mesmos quatro.
        """
        from hefesto_dualsense4unix.core.led_control import player_led_pattern

        self._set_player_leds(list(player_led_pattern(numero)))

    def on_player_leds_preset_all(self, _btn: Gtk.Button) -> None:
        self._set_player_leds([True] * 5)

    def on_player_leds_preset_p1(self, _btn: Gtk.Button) -> None:
        self.aplicar_desenho_do_jogador(1)

    def on_player_leds_preset_p2(self, _btn: Gtk.Button) -> None:
        self.aplicar_desenho_do_jogador(2)

    def on_player_leds_preset_p3(self, _btn: Gtk.Button) -> None:
        self.aplicar_desenho_do_jogador(3)

    def on_player_leds_preset_p4(self, _btn: Gtk.Button) -> None:
        self.aplicar_desenho_do_jogador(4)

    def on_player_leds_preset_none(self, _btn: Gtk.Button) -> None:
        self._set_player_leds([False] * 5)

    def on_player_leds_apply(self, _btn: Gtk.Button) -> None:
        """Reenvia o padrão atual dos 5 checkboxes ao hardware"""
        if self._refresh_guard:
            return
        bits = self.get_current_player_leds()
        # Atualiza draft — mantém consistência com on_player_led_toggled.
        d4_disparou = self._persist_leds_update({"player_leds": bits})
        ok, motivo, corpo = self._enviar_player_leds(bits)
        descricao = self._descreve_player_leds(bits)
        msg = self._msg_do_desenho(
            ok=ok,
            motivo=motivo,
            corpo=corpo,
            descricao=descricao,
            feito="aplicado",
            fazer="aplicar",
        )
        if d4_disparou:
            msg = f"{_AVISO_D4} — {msg}"
        self._toast_light(msg)
        if ok:
            self._atualizar_estado_das_luzes(bits)

    def on_player_led_toggled(self, _checkbox: Gtk.CheckButton) -> None:
        """Sinal de toggle de qualquer checkbox de player LED."""
        if self._refresh_guard:
            return
        if getattr(self, "_player_leds_batch_guard", False):
            return
        bits = self.get_current_player_leds()
        d4_disparou = self._persist_leds_update({"player_leds": bits})
        ok, motivo, corpo = self._enviar_player_leds(bits)
        descricao = self._descreve_player_leds(bits)
        msg = self._msg_do_desenho(
            ok=ok,
            motivo=motivo,
            corpo=corpo,
            descricao=descricao,
            feito="atualizado",
            fazer="atualizar",
        )
        if d4_disparou:
            msg = f"{_AVISO_D4} — {msg}"
        self._toast_light(msg)


    def _set_player_leds(self, pattern: list[bool]) -> None:
        """Atualiza checkboxes e envia bitmask ao hardware via IPC (1 chamada).

        Aplica `_player_leds_batch_guard` enquanto atualiza os 5 checkboxes para
        evitar que `on_player_led_toggled` dispare IPCs redundantes -- so envia
        o bitmask final ao fim, em uma chamada única.
        """
        self._player_leds_batch_guard = True
        try:
            for i, state in enumerate(pattern, start=1):
                checkbox: Gtk.CheckButton = self._get(f"player_led_{i}")
                if checkbox is not None:
                    checkbox.set_active(state)
        finally:
            self._player_leds_batch_guard = False
        bits: tuple[bool, bool, bool, bool, bool] = (
            pattern[0], pattern[1], pattern[2], pattern[3], pattern[4]
        )
        d4_disparou = self._persist_leds_update({"player_leds": bits})
        ok, motivo, corpo = self._enviar_player_leds(bits)
        descricao = self._descreve_player_leds(pattern)
        msg = self._msg_do_desenho(
            ok=ok,
            motivo=motivo,
            corpo=corpo,
            descricao=descricao,
            feito="atualizado",
            fazer="atualizar",
        )
        if d4_disparou:
            msg = f"{_AVISO_D4} — {msg}"
        self._toast_light(msg)
        if ok:
            self._atualizar_estado_das_luzes(bits)

    def get_current_player_leds(self) -> tuple[bool, bool, bool, bool, bool]:
        states: list[bool] = []
        for i in range(1, 6):
            checkbox: Gtk.CheckButton = self._get(f"player_led_{i}")
            states.append(bool(checkbox.get_active()) if checkbox is not None else False)
        return (states[0], states[1], states[2], states[3], states[4])

    def _msg_do_desenho(
        self,
        *,
        ok: bool,
        motivo: str | None,
        corpo: dict[str, Any] | None,
        descricao: str,
        feito: str,
        fazer: str,
    ) -> str:
        """A frase do desenho das 5 luzes — UMA, para os três gestos."""
        if not ok:
            return motivo or (
                f"Não consegui {fazer} o desenho das luzes — o Hefesto pode "
                "estar desligado (ligue na aba Sistema)"
            )
        assunto = f"Desenho das luzes ({descricao})"
        enviado = f"Desenho das luzes {feito} — {descricao}"
        if coop_manda_nas_luzes(self):
            frase = frase_de_guardado(
                assunto,
                alvo_ausente=alvo_fora_da_mesa(self),
                coop=True,
            ) or enviado
        else:
            frase = frase_do_envio(assunto, enviado, corpo, self, coop_aplica=True)
        quantos = self._quantos_recebem_o_desenho()
        if quantos >= 2:
            frase = f"{frase} {_AVISO_MESMO_DESENHO_NOS_QUATRO.format(n=quantos)}"
        return frase

    def _quantos_recebem_o_desenho(self) -> int:
        """Quantos controles um clique de desenho atinge; 0 se for um só (L12)."""
        estado_alvo = self._edit_uniq()
        if estado_alvo.desconhecido or estado_alvo.uniq is not None:
            return 0
        return len(self._uniqs_conectados())

    @staticmethod
    def _descreve_player_leds(bits: list[bool] | tuple[bool, ...]) -> str:
        """Padrão dos LEDs de jogador em palavras (LB-03)."""
        acesos = [str(i) for i, ligado in enumerate(bits, start=1) if ligado]
        if not acesos:
            return "todos os LEDs apagados"
        if len(acesos) == 1:
            return f"LED aceso: {acesos[0]}"
        return "LEDs acesos: " + ", ".join(acesos[:-1]) + " e " + acesos[-1]

    def _on_lightbar_preview_draw(
        self, widget: Gtk.DrawingArea, cairo_ctx: Any
    ) -> bool:
        alloc = widget.get_allocation()
        r, g, b = self._current_rgb
        level = max(0.0, min(1.0, self._current_brightness))
        cairo_ctx.set_source_rgb(
            (r / 255) * level,
            (g / 255) * level,
            (b / 255) * level,
        )
        cairo_ctx.rectangle(0, 0, alloc.width, alloc.height)
        cairo_ctx.fill()
        return False

    def _toast_light(self, msg: str) -> None:
        self._status_toast("light", msg)
