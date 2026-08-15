"""Helpers compartilhados por todos os mixins da GUI."""
# ruff: noqa: E402
from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from hefesto_dualsense4unix.app.actions import relancar
from hefesto_dualsense4unix.app.ipc_bridge import _get_executor
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


def numero_do_controle(entry: dict[str, Any]) -> int:
    """Número com que UM controle se identifica na interface inteira.

    Fonte única da regra (COR-01/D6): é o ``player_slot`` de sessão — a
    identidade ESTÁVEL, que sobrevive a desconectar e reconectar e que a CLI e o
    applet também usam. Sem slot (controle sem MAC, registro ainda ausente) cai
    na posição 1-based da lista.

    Existia uma cópia dessa regra em cada tela, e a aba Início usava a POSIÇÃO no
    loop em vez do slot: com um controle só, ela dizia "Controle 1" enquanto o
    cabeçalho, olhando o mesmo controle, dizia "Sony 3". Duas verdades na mesma
    janela sobre qual é o "Controle 1".

    ``player`` (o número do JOGADOR, que vem do daemon) responde uma pergunta
    diferente — "este controle está jogando agora, e como quem?" —, e por isso
    é ``None`` fora do co-op. Mas desde a MESA-CHEIA-12 (15/08/2026) ele já não
    é outro NÚMERO: `CoopManager.numeros_de_jogador()` o tira da mesma fila de
    chegada que dá o ``player_slot``, e é a mesma fila que escolhe o desenho
    aceso na barra do controle. Quando os dois existem, eles são iguais — antes
    disso divergiam, e o card dizia "jogador 2" no controle que acendia 4.
    """
    slot = entry.get("player_slot")
    if isinstance(slot, int) and not isinstance(slot, bool):
        return slot
    indice = entry.get("index")
    if isinstance(indice, int) and not isinstance(indice, bool):
        return indice + 1
    return 1


#: DEPOIS-QUE-APLICAVA-AGORA-01: as mudanças cuja APLICAÇÃO é a própria escrita
#: em disco — para essas, "aplicar na próxima abertura" pode escrever agora, e a
#: única coisa adiada é o jogo relê-las. As demais (modo, máscara) recriam
#: dispositivo ao vivo e NÃO podem ser aplicadas neste ramo.
_MUDANCAS_QUE_SAO_ESCRITA: frozenset[str] = frozenset({"steam_input_do_jogo"})


class WidgetAccessMixin:
    """Acesso comum ao `Gtk.Builder` via `self.builder`.

    Todos os mixins de ação herdam daqui para usar `_get` e `_set_label`.
    """

    builder: Gtk.Builder

    #: AGORA-E-DEPOIS-01 (08/08/2026): a escolha dela que ainda não valeu —
    #: ``{"modo": ..., "mascara": ...}``, ou ``None`` quando não há nada
    #: pendente. Chave ausente significa "este campo segue o daemon".
    #:
    #: A DECLARAÇÃO mora aqui, na base comum, porque dois mixins da mesma classe
    #: a tocam: a aba Início escreve (o clique marca) e o rodapé lê e limpa (o
    #: "Aplicar" aplica). Declarar em cada um faria dois tipos para o mesmo
    #: atributo na MRO de `HefestoApp` — o mypy pega, e ele está certo: seriam
    #: dois donos da mesma verdade, que é o defeito que esta casa persegue.
    #:
    #: O dono do VALOR continua sendo a aba Início (`home_actions`), que é onde
    #: ele nasce e onde mora a regra de reconciliação com o daemon.
    _escolha_pendente: dict[str, str] | None = None

    # --- RELANCAR-01: o que só vale quando o jogo reabre --------------------

    #: Ids de resposta do diálogo. Positivos de propósito: os `Gtk.ResponseType`
    #: nativos são negativos, então não há colisão (mesmo padrão do
    #: `_RESP_RENOMEAR`).
    _RESP_DEPOIS = 210
    _RESP_FECHAR_E_ABRIR = 211

    def _perguntar_antes_de_relancar(
        self,
        *,
        mudanca: str,
        valor: str | None,
        aplicar: Callable[[], None],
        ao_nao_relancar: Callable[[str], None] | None = None,
    ) -> bool:
        """True se assumiu o gesto (vai perguntar); False para aplicar direto.

        RELANCAR-01 (08/08/2026). Sonda num worker — dois `pgrep` de até 5 s
        congelariam a janela — e decide na thread do GTK, que é o padrão de
        `emulation_actions.on_emulation_steam_input_disable`.

        **Devolver False no erro é deliberado:** se a sondagem falhar, a mudança
        aplica como sempre aplicou. Um diálogo que aparece por engano no meio da
        partida é pior que uma pergunta que não foi feita — e a sondagem é
        best-effort por natureza.

        ``ao_nao_relancar`` roda nos DOIS ramos em que o jogo não é relançado —
        "Aplicar na próxima abertura" e "Cancelar" —, recebendo qual deles foi.
        Existe porque quem chama daqui pode ter mais a fazer do que este módulo
        tem como saber: o "Aplicar" do rodapé carrega SETE seções que mudam na
        hora (gatilhos, LEDs, rumble…) além do modo/máscara que adiam.

        AGORA-E-DEPOIS-01 → O-AGORA-NAO-E-REFEM-DO-DEPOIS-01 (08/08/2026, noite).
        Ele nasceu cobrindo só o ramo de adiar, com a razão escrita de que o
        "Cancelar" promete que **nada** mudou. A verificação adversarial mostrou
        que a promessa é sobre o JOGO — *"não mexe na minha partida"* — e que
        engolir a cor que ela ajustou na aba ao lado não é honrar promessa
        nenhuma; é perder trabalho dela. Pior: o Cancelar é o botão DEFAULT do
        diálogo, então Esc e o X da janela caíam ali.

        No "Aplicar agora e reiniciar" ele NÃO roda, e isso continua certo: ali
        quem continua a sequência é o callback de sucesso do próprio ``aplicar``.
        """
        if mudanca not in relancar.EXIGEM_RELANCAR:
            return False
        jogo_aberto = bool(getattr(self, "_jogo_aberto", False))
        if not relancar.precisa_perguntar(
            mudanca=mudanca, jogo_aberto=jogo_aberto
        ):
            # Sem jogo aberto NADA muda: aplica na hora, síncrono, como sempre.
            # Este retorno é o que mantém o caminho comum sem diálogo e sem
            # espera — e é o que os testes da caixinha exercitam.
            return False
        # H (achado adversarial de 08/08): se o diálogo NÃO nascer — exceção
        # no construtor, GTK sem tela —, quem chamou não pode ficar sem resposta.
        # Antes, a exceção subia com o `True` já prometido e o clique dela morria
        # em silêncio: sem toast, sem log, sem aplicação. Devolver False aqui
        # devolve o gesto ao chamador, que aplica direto — é a MESMA filosofia
        # de fail-safe já escrita acima: na dúvida, não interromper.
        try:
            self._relancar_decidir(mudanca, valor, True, aplicar, ao_nao_relancar)
        except Exception as exc:
            logger.warning("relancar_dialogo_nao_nasceu", erro=str(exc))
            return False
        return True

    def _relancar_decidir(
        self,
        mudanca: str,
        valor: str | None,
        jogo: object,
        aplicar: Callable[[], None],
        ao_nao_relancar: Callable[[str], None] | None = None,
    ) -> bool:
        """Na thread do GTK: sem jogo aplica; com jogo, pergunta."""
        nome_do_jogo = jogo if isinstance(jogo, str) and jogo else None

        def _resposta(dialog: Any, resposta: int) -> None:
            with contextlib.suppress(Exception):
                dialog.destroy()
            if resposta == self._RESP_FECHAR_E_ABRIR:
                aplicar()
                self._toast_do_relancar(
                    relancar.toast_da_escolha("fechar_e_abrir", jogo=nome_do_jogo)
                )
                self._relancar_o_jogo()
            elif resposta == self._RESP_DEPOIS:
                # DEPOIS-QUE-APLICAVA-AGORA-01 (08/08/2026) — defeito MEU, achado
                # por verificação adversarial antes de ela pagar por ele.
                #
                # Esta linha chamava `aplicar()` incondicionalmente, com o
                # raciocínio de que "a marca dela mora no disco, então escrever é
                # o certo". Isso vale para a caixinha do Steam Input, cuja
                # aplicação É a escrita no arquivo. **Não vale para a máscara:**
                # ali `aplicar()` chama `gamepad.emulation.set`, que RECRIA O VPAD
                # AO VIVO — exatamente o dano que este diálogo existe para evitar.
                #
                # Ou seja: o botão "Aplicar na próxima abertura" fazia, na
                # máscara, a mesma coisa que o "Aplicar agora" — sem fechar o
                # jogo, e portanto deixando o jogo e a máquina em desacordo.
                #
                # Agora só aplica o que é ESCRITA (a marca no disco). O que
                # recria dispositivo fica para a próxima abertura de verdade, e o
                # toast diz isso. Enquanto o rascunho não souber segurar a
                # máscara, o honesto é não fingir que guardou.
                if mudanca in _MUDANCAS_QUE_SAO_ESCRITA:
                    aplicar()
                else:
                    logger.info(
                        "relancar_adiado_sem_guardar", mudanca=mudanca
                    )
                self._toast_do_relancar(
                    relancar.toast_da_escolha(
                        "na_proxima_abertura",
                        jogo=nome_do_jogo,
                        guardou=mudanca in _MUDANCAS_QUE_SAO_ESCRITA,
                    )
                )
                # AGORA-E-DEPOIS-01: o resto do gesto de quem chamou — hoje, as
                # sete seções do "Aplicar" que mudam NA HORA e não têm nada a
                # ver com a abertura do jogo. Vem depois do toast de propósito:
                # quem chama pode escrever o seu por cima, e a última palavra
                # tem de ser a de quem sabe o que aconteceu por inteiro.
                if ao_nao_relancar is not None:
                    with contextlib.suppress(Exception):
                        ao_nao_relancar("na_proxima_abertura")
            else:
                self._toast_do_relancar(relancar.toast_da_escolha("cancelar"))
                # O-AGORA-NAO-E-REFEM-DO-DEPOIS-01: cancelar é sobre o JOGO —
                # "não mexe na minha partida" —, e não sobre a cor da luz que
                # ela ajustou na aba ao lado. Antes, este ramo engolia as sete
                # seções do "Aplicar" em silêncio, e era o pior lugar possível
                # para isso: o Cancelar é o botão DEFAULT do diálogo
                # (`daemon_actions.build_consentimento_dialog` chama
                # `set_default_response(botoes[0])`), então Esc, Enter distraído
                # e o X da janela caíam todos aqui.
                if ao_nao_relancar is not None:
                    with contextlib.suppress(Exception):
                        ao_nao_relancar("cancelar")
                # A tela volta ao que o disco diz: janela que não mente.
                with contextlib.suppress(Exception):
                    sincronizar = getattr(self, "_sincronizar_caixa_do_steam_input", None)
                    if callable(sincronizar):
                        sincronizar()

        from hefesto_dualsense4unix.app.actions.daemon_actions import (
            build_consentimento_dialog,
        )

        dialog = build_consentimento_dialog(
            getattr(self, "window", None),
            titulo=relancar.TITULO,
            corpo=relancar.corpo_do_dialogo(
                mudanca=mudanca, valor=valor, jogo=nome_do_jogo
            ),
            botoes=[
                (relancar.ROTULO_CANCELAR, Gtk.ResponseType.CANCEL),
                (relancar.ROTULO_DEPOIS, self._RESP_DEPOIS),
                (relancar.ROTULO_FECHAR, self._RESP_FECHAR_E_ABRIR),
            ],
            on_response=_resposta,
            destrutivo=self._RESP_FECHAR_E_ABRIR,
        )
        with contextlib.suppress(Exception):
            dialog.show_all()
        return False

    def _relancar_o_jogo(self) -> None:
        """Fecha a Steam e o jogo, espera, e ABRE o jogo de novo.

        RELANCAR-AGORA-01 (08/08/2026) — corrige um defeito que ela viu na tela
        antes de qualquer teste pegar: *"a última opção deveria ser aplicar agora
        e reiniciar jogo. Pior que essa terceira opção nem faz isso né? Só fecha
        mesmo, não sei nem se aplicou."*

        Estava certa nas três coisas. O botão dizia "Fechar o jogo e abrir de
        novo", chamava `stop_steam()` e acabava ali — **não abria nada**, e o
        docstring anterior desta função afirmava que abria. Um botão que promete
        e não cumpre é pior que um botão que não existe: ela fica sem o jogo e
        sem saber se a mudança valeu.

        A sequência, e cada passo tem um porquê:

        1. **descobrir o appid ANTES de fechar** — depois do `stop_steam` o
           processo do jogo já morreu, e com ele a única pista de qual jogo era
           (`SteamLaunch AppId=`);
        2. **fechar** com o mesmo `stop_steam` do precedente HONESTIDADE-STEAM-01,
           que já espera até 30 s e escala se preciso;
        3. **reabrir por `steam://rungameid/<appid>`**, que é como a própria Steam
           abre pelos atalhos — e é o que faz o jogo nascer COM o wrapper do
           Hefesto, lendo o `launch_env` novo. Chamar o executável direto pularia
           o wrapper, e a mudança dela não valeria.

        Roda inteiro num worker: o `stop_steam` bloqueia por até 30 s, e a janela
        não pode congelar nesse tempo. O toast final é despachado de volta pela
        thread do GTK.
        """

        def _fazer() -> None:
            from hefesto_dualsense4unix.integrations import (
                steam_launch_options as slo,
            )

            appid = None
            with contextlib.suppress(Exception):
                appid = slo.steam_game_running_appid()

            fechou = False
            with contextlib.suppress(Exception):
                fechou = bool(slo.stop_steam())

            reabriu = False
            if appid is not None:
                with contextlib.suppress(Exception):
                    reabriu = bool(slo.start_steam_game(appid))

            GLib.idle_add(
                self._toast_do_relancar,
                relancar.toast_do_relancamento(
                    fechou=fechou, reabriu=reabriu, appid=appid
                ),
            )

        with contextlib.suppress(Exception):
            _get_executor().submit(_fazer)

    def _toast_do_relancar(self, texto: str) -> None:
        """Onde o resultado do diálogo aparece. A aba dona pode especializar.

        RELANCAR-01: o diálogo é compartilhado pelas abas Início e Perfis, mas o
        rodapé é de cada uma. Este gancho evita que a base assuma qual toast
        usar — e, na ausência dos dois, o texto vai para o log em vez de sumir.
        """
        for nome in ("_toast_profile", "_status_toast_home", "_status_toast"):
            metodo = getattr(self, nome, None)
            if callable(metodo):
                with contextlib.suppress(Exception):
                    if nome == "_status_toast":
                        metodo("home", texto)
                    else:
                        metodo(texto)
                    return
        logger.info("relancar_toast_sem_destino", texto=texto)

    def _get(self, widget_id: str) -> Any:
        return self.builder.get_object(widget_id)

    def _set_label(self, widget_id: str, text: str) -> None:
        widget = self._get(widget_id)
        if widget is not None:
            widget.set_text(text)

    def _status_toast(self, context: str, msg: str) -> None:
        """Mostra ``msg`` na statusbar, mantendo no máximo 1 mensagem por contexto.

        Faz ``pop`` antes do ``push``: sem isso cada aba/área empilhava mensagens
        indefinidamente — o feedback ficava stale (a barra mostrava a primeira da
        pilha) e a pilha crescia sem limite. Com o pop, cada ``context`` guarda
        apenas a sua última mensagem. Ponto único reusado por todos os helpers
        ``_toast_*`` da GUI.
        """
        bar = self._get("status_bar")
        if bar is None:
            return
        ctx_id = bar.get_context_id(context)
        bar.pop(ctx_id)
        bar.push(ctx_id, msg)


__all__ = ["WidgetAccessMixin", "numero_do_controle"]
