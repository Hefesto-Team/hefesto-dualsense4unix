"""Handlers do rodapé global: Aplicar, Salvar Perfil, Importar, Restaurar Default."""
from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.app import gui_dialogs, ipc_bridge
from hefesto_dualsense4unix.app.actions.carona_do_wrapper import GESTO_APLICAR
from hefesto_dualsense4unix.app.actions.profile_writer import (
    ProfileWriterMixin,
    carimbo_que_o_save_leva,
)
from hefesto_dualsense4unix.integrations.lugar_declarado import declarar_a_maquina
from hefesto_dualsense4unix.profiles.loader import (
    ARQUIVO_ANTIGO_DO_PADRAO,
    ARQUIVO_DO_PADRAO,
    ARQUIVO_DO_PERSONALIZADO,
    NOME_DO_PADRAO,
    _seed_source_file,
    load_all_profiles,
    load_profile,
)
from hefesto_dualsense4unix.profiles.schema import (
    Match,
    MatchManual,
    PonteConfirmada,
    Profile,
)
from hefesto_dualsense4unix.profiles.slug import find_by_slug
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_MEU_PERFIL_NOME = NOME_DO_PADRAO
_MEU_PERFIL_ARQUIVO = ARQUIVO_DO_PADRAO


def frase_do_preset_ausente() -> str:
    """A recusa do "Restaurar de fábrica" quando não há preset em lugar nenhum."""
    return _(
        "Não encontrei o perfil de fábrica instalado nesta máquina — sem ele "
        "não há para onde voltar."
    )


def frase_do_restauro(caminho: object = None) -> str:
    """O recibo do "Restaurar de fábrica", com o destino quando há um a dizer."""
    if caminho:
        return _("Pronto — o perfil {nome} voltou ao de fábrica ({destino}).").format(
            nome=NOME_DO_PADRAO, destino=caminho
        )
    return _("Pronto — o perfil {nome} voltou ao de fábrica.").format(
        nome=NOME_DO_PADRAO
    )


def _meu_perfil_asset() -> Path | None:
    """Acha o preset do perfil padrão; ``None`` quando não há em lugar nenhum."""
    return (_seed_source_file(ARQUIVO_DO_PADRAO) or _seed_source_file(
        ARQUIVO_DO_PERSONALIZADO) or _seed_source_file(ARQUIVO_ANTIGO_DO_PADRAO))


_NOMES_DE_SECAO: dict[str, str] = {
    "leds": "luzes",
    "triggers": "gatilhos",
    "rumble": "vibração",
    "mouse": "mouse",
    "keyboard": "teclado",
    "mic": "microfone",
    "speaker": "alto-falante",
    "controllers": "ajustes por controle",
}

_MAX_SECOES_NO_TEXTO = 3

FROZEN_WIDGET_IDS: tuple[str, ...] = (
    "btn_footer_apply",
    "btn_footer_save_profile",
    "btn_footer_import",
    "btn_footer_restore_default",
    "lightbar_color_button",
    "lightbar_brightness_scale",
    "trigger_left_mode_slot",
    "trigger_right_mode_slot",
    "rumble_weak_scale",
    "rumble_strong_scale",
    "mouse_emulation_toggle",
    "mouse_speed_scale",
    "mouse_scroll_speed_scale",
)


class FooterActionsMixin(ProfileWriterMixin):
    """Handlers dos 4 botões do rodapé global da GUI."""

    draft: Any

    #: então não atropela perfil de jogo alheio.
    _PISO_ACIMA_DOS_CATCH_ALL = 15

    _recado_da_maquina: str | None = None


    def _freeze_ui(self, freeze: bool) -> None:
        """Habilita ou desabilita widgets conhecidos durante operação longa."""
        sensitive = not freeze
        for widget_id in FROZEN_WIDGET_IDS:
            widget = self._get(widget_id)
            if widget is not None:
                widget.set_sensitive(sensitive)
        if freeze:
            return
        reconcile = getattr(self, "_refresh_mouse_from_daemon_async", None)
        if reconcile is not None:
            try:
                reconcile()
            except Exception as exc:
                logger.warning("footer_regate_mouse_falhou", erro=str(exc))


    def _footer_toast(self, msg: str, context: str = "footer") -> None:
        """Empurra mensagem na statusbar com contexto ``context``."""
        self._status_toast(context, msg)


    def _notify_launch_env_refresh(self) -> None:
        """Avisa o daemon que o conjunto de perfis mudou (`launch_env.refresh`).

        save/import/restore de perfil rodam no processo da GUI, direto no
        disco — sem este aviso o `steam_app_<appid>.env` de antecipação só
        seria regravado na PRÓXIMA transição de estado do daemon, tarde demais
        para o primeiro launch de um jogo com perfil recém-criado (achado MED
        da revisão adversarial da Fase 2). Best-effort: daemon offline é
        normal (ele rematerializa sozinho no boot).
        """
        ipc_bridge.call_async(
            method="launch_env.refresh",
            params={},
            on_success=lambda _result: False,
            on_failure=lambda _exc: False,
        )


    def on_apply_draft(self, _btn: Any = None) -> None:
        """O botão verde do rodapé. Aplica o AGORA e, se houver, o DEPOIS."""
        self.pegar_carona_no_gesto(GESTO_APLICAR)
        _gravou, self._recado_da_maquina = self._gravar_declaracao_de_maquina()
        pendente = getattr(self, "_escolha_pendente", None)
        if pendente:
            self._aplicar_escolha_pendente(dict(pendente))
            return
        self._apply_draft_agora()

    def _gravar_declaracao_de_maquina(self) -> tuple[bool, str | None]:
        """Grava o que a aba Configurações declarou, e devolve ``(gravou, frase)``.

        **POR QUE UM PAR, e não só a frase** (achado da auditoria de
        rastreabilidade, 24/08/2026). A versão anterior devolvia ``str | None``,
        e a string significava TRÊS coisas: sucesso, sucesso com descarte, e
        fracasso. Dois chamadores fazem perguntas DIFERENTES — o rodapé quer a
        FRASE, o fechamento da janela quer saber se GRAVOU — e o segundo lia
        "há string, logo falhou".

        O defeito era vivo no uso diário: ela declarava, clicava "Aplicar e
        fechar", **o arquivo era gravado, a janela NÃO fechava**, e o rodapé
        exibia *"Configurações gravadas."* como se fosse o motivo da recusa.

        Nasceu de uma cura ler o contrato antigo de outra: a metade "e DIZ" do
        descarte mudou o retorno, e o portão do fechamento continuou lendo
        ``is not None``. **Duas perguntas exigem dois valores** — é a mesma lei
        que separou ``orcamento_em_vigor`` de ``orcamento_na_tela``.

        Sem declaração, sai cedo.

        DEVOLVE a frase que o rodapé deve dizer sobre a declaração — ou ``None``
        quando não havia nada a declarar. Quem a mostra é o toast FINAL do
        "Aplicar" (``_apply_draft_agora``), e a razão está no
        ``_recado_da_maquina``: escrever aqui perdia a frase no mesmo tique.

        CONFIG-03 (22/08/2026). A aba Configurações é DIFERIDA por decisão de
        produto (D-A4): clicar num seletor lá não muda nada — acumula em
        ``_maquina_pendente`` (``actions/base.py``). Quem salva é este botão, e
        a aba diz isso na linha do rodapé dela.

        **O lugar é o TOPO de ``on_apply_draft``, não ``_apply_draft_agora``**, e
        duas medições fixam o ponto. Logo abaixo, ``on_apply_draft`` RETORNA CEDO
        quando há escolha de modo pendente — pendurar depois daquele ramo faria o
        "Aplicar com modo pendente" nunca gravar a declaração. E
        ``_apply_draft_agora`` tem CINCO chamadores neste arquivo (o caminho
        direto, a saída "sem modo vigente" e os três callbacks da transição de
        modo), então pendurar lá dentro gravaria até duas vezes por clique.

        Síncrono na thread do GTK pelo mesmo argumento do
        ``_ha_jogo_aberto_agora`` (ver a docstring dele): o clique no "Aplicar"
        já congela a janela, e o teto de 1,0 s da ponte é menor que o do
        ``apply_draft`` que vem em seguida.

        A pendência só é limpa quando a gravação CONFIRMA — pelo daemon ou pelo
        disco. Recusa deixa a declaração de pé: as escolhas seguem marcadas na
        aba e clicar de novo tenta de novo — o contrário perderia em silêncio o
        que ela declarou.

        O HEFESTO DESLIGADO NÃO É MOTIVO PARA PERDER O QUE ELA DECLAROU
        ---------------------------------------------------------------

        CONEXÕES · MAPA 2D 01 / G3 (25/08/2026). Até hoje o ÚNICO escritor de
        produção do ``maquina.json`` era o handler ``machine.declare``, atrás do
        IPC — e o ``maquina.json`` não depende de daemon nenhum: é um arquivo
        de configuração que a própria janela sabe gravar, com o mesmo lock e a
        mesma gravação atômica (``utils/maquina``). Com o Hefesto parado, a tela
        respondia *"não gravei o que você declarou"* e jogava fora a mesa, o
        desenho, os controles e o orçamento que ela acabara de declarar.

        O caminho de disco é FALLBACK, e o gatilho é exato: ``motivo is None``
        quer dizer que o daemon **não respondeu** (contrato de
        ``machine_declare_detalhado``). Daemon VIVO que recusou vem com motivo, e
        aí o disco não é tentado — gravar por trás de um daemon que disse "não"
        deixaria a memória dele divergindo do arquivo, que é pior que não
        gravar.

        **Não nasce um segundo dono do gesto.** O dono continua sendo este
        método; o que mudou foi o que ele faz quando a ponte está morta. A
        objeção escrita em ``config/secao_mesa._ao_declarar`` — *"chamar
        ``machine.declare`` daqui criaria um segundo dono do gesto de gravar"* —
        segue valendo, e nenhuma seção da aba ganhou porta própria para o disco.

        E o daemon lê o arquivo ao ligar (``daemon/lifecycle.py``:788,
        ``carregar_maquina``), então o que desce ao disco aqui chega a ele
        sozinho no próximo start — não há segunda metade a fazer depois.
        """
        declaracao = self._maquina_pendente
        if not declaracao:
            return (True, None)
        ok, motivo, descartados = ipc_bridge.machine_declare_detalhado(
            dict(declaracao)
        )
        if not ok and motivo is None:
            return self._gravar_declaracao_no_disco(dict(declaracao))
        if ok:
            self._maquina_pendente = None
            if descartados:
                logger.warning(
                    "footer_declaracao_de_maquina_com_descartes",
                    descartados=list(descartados),
                )
                return (True, _(
                    "Gravei o que deu. Isto o Hefesto não entendeu e "
                    "descartou: {campos}."
                ).format(campos=", ".join(descartados)))
            return (True, _("Configurações gravadas."))
        logger.warning("footer_declaracao_de_maquina_nao_gravada", motivo=motivo)
        return (False, motivo or _(
            "O Hefesto está desligado — não gravei o que você declarou"
        ))

    def _gravar_declaracao_no_disco(
        self, declaracao: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """O mesmo gesto, sem a ponte: grava direto no ``maquina.json``."""
        recibo = declarar_a_maquina(declaracao)
        if not recibo.gravou:
            logger.warning(
                "footer_declaracao_de_maquina_nem_no_disco", motivo=recibo.motivo
            )
            return (False, _(
                "O Hefesto está desligado — não gravei o que você declarou"
            ))
        self._maquina_pendente = None
        if recibo.descartados:
            logger.warning(
                "footer_declaracao_no_disco_com_descartes",
                descartados=list(recibo.descartados),
            )
        return (True, _(
            "O Hefesto está desligado — gravei aqui, e ele lê isso ao ligar."
        ))

    def _dizer_com_o_recado_da_maquina(self, msg: str) -> None:
        """Uma linha só: o recado da declaração seguido do resultado do Aplicar."""
        recado = self._recado_da_maquina
        self._recado_da_maquina = None
        self._footer_toast(f"{recado} {msg}" if recado else msg)

    def _marcar_declaracao_por_aplicar(self) -> None:
        """Diz na linha do rodapé que há escolha declarada e não aplicada."""
        if getattr(self, "_maquina_pendente", None):
            self._footer_toast(
                _('Há escolhas declaradas por aplicar — clique em "Aplicar".')
            )

    def _ha_jogo_aberto_agora(self) -> bool:
        """Relê o sinal de jogo aberto NA HORA. Devolve o que ficou em cache."""
        import contextlib

        from hefesto_dualsense4unix.app.actions.mode_transition import (
            STATE_IPC_TIMEOUT_S,
        )

        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.app.ipc_bridge import _run_call

            estado = _run_call("daemon.state_full", None, timeout=STATE_IPC_TIMEOUT_S)
            if isinstance(estado, dict):
                sinal = estado.get("game_signal")
                self._jogo_aberto = (
                    isinstance(sinal, dict) and sinal.get("authority") == "game"
                )
        return bool(getattr(self, "_jogo_aberto", False))

    def _aplicar_escolha_pendente(self, pendente: dict[str, str]) -> None:
        """Aplica o que ela escolheu na aba Início e SÓ ENTÃO o rascunho."""
        from hefesto_dualsense4unix.app.actions.home_actions import (
            DESFECHO_BLOQUEADO,
            DESFECHO_FALHOU,
            desfecho_da_troca,
            lembrar_mascara_recusada,
            registrar_modo_no_rascunho,
            toast_da_troca_de_mascara,
        )

        modo_alvo = pendente.get("modo") or getattr(
            self, "_modo_vigente_do_daemon", None
        )
        mascara_alvo = pendente.get("mascara")
        if not modo_alvo:
            logger.info("aplicar_pendencia_sem_modo_vigente")
            self._apply_draft_agora()
            return

        def _done(resultado: Any) -> None:
            registrar_modo_no_rascunho(
                self,
                modo_alvo,
                mascara_alvo or getattr(self, "_mascara_vigente_do_daemon", None),
            )
            desfecho = (
                desfecho_da_troca(resultado, pedida=mascara_alvo)
                if mascara_alvo
                else None
            )
            if desfecho is not None:
                self._recado_da_maquina = " ".join(
                    parte
                    for parte in (
                        self._recado_da_maquina,
                        toast_da_troca_de_mascara(desfecho, mascara_alvo),
                    )
                    if parte
                )
            if desfecho in (DESFECHO_BLOQUEADO, DESFECHO_FALHOU):
                lembrar_mascara_recusada(self, mascara_alvo)
                logger.info(
                    "aplicar_mascara_recusada", desfecho=desfecho,
                    mascara=mascara_alvo,
                )
            else:
                _esquecer_a_pendencia(self)
            self._apply_draft_agora()

        def _fail(exc: Exception) -> None:
            logger.warning("aplicar_pendencia_falhou", erro=str(exc))
            self._footer_toast(
                _(
                    "Não consegui preparar o que vale na próxima abertura "
                    "({erro}) — o resto dos ajustes foi aplicado."
                ).format(erro=exc)
            )
            self._apply_draft_agora()

        def _sem_relancar(escolha: str) -> None:
            """Os dois ramos em que o jogo NÃO é relançado."""
            if escolha != "cancelar":
                _esquecer_a_pendencia(self)
            self._apply_draft_agora()

        _transicao_de_modo(
            self,
            modo=modo_alvo,
            mascara=mascara_alvo,
            ao_aplicar=_done,
            ao_falhar=_fail,
            ao_nao_relancar=_sem_relancar,
        )

    def _apply_draft_agora(self) -> None:
        """Envia DraftConfig inteiro ao daemon via IPC ``profile.apply_draft``."""
        # `lightbar_color_button` e o `lightbar_brightness_scale`: se
        draft_dict = self.draft.to_ipc_dict()
        self._freeze_ui(True)
        self._footer_toast(_("Aplicando perfil inteiro..."))

        def _on_ok(result: Any) -> bool:
            self._freeze_ui(False)
            if isinstance(result, bool):
                aceita = result
            elif isinstance(result, dict):
                aceita = result.get("status") == "ok"
            else:
                aceita = bool(result)
            aplicou = aceita and _algo_foi_aplicado(result)
            if aplicou and _secao_aplicada(result, "mouse"):
                self._clear_mouse_dirty()
            # Aplicar seguinte reenviaria o mesmo volume — idempotente, sem dano
            if aplicou and _secao_aplicada(result, "speaker"):
                self._clear_speaker_dirty()
            msg = (
                _mensagem_de_aplicacao(result)
                if aceita
                else _("ERRO ao aplicar perfil (daemon offline?).")
            )
            self._dizer_com_o_recado_da_maquina(msg)
            logger.info(
                "footer_apply_draft_resultado", ok=aplicou, aceita=aceita
            )
            return False

        def _on_err(exc: Exception) -> bool:
            self._freeze_ui(False)
            self._dizer_com_o_recado_da_maquina(
                _("ERRO ao aplicar: {erro}").format(erro=exc)
            )
            logger.warning("footer_apply_draft_falhou", erro=str(exc))
            return False

        ipc_bridge.call_async(
            "profile.apply_draft",
            draft_dict,
            on_success=_on_ok,
            on_failure=_on_err,
            timeout_s=1.5,
        )

    def _clear_mouse_dirty(self) -> None:
        """Baixa o ``dirty`` da seção mouse DEPOIS de aplicar com sucesso (HARM-05)."""
        draft = getattr(self, "draft", None)
        if draft is None or not draft.mouse.dirty:
            return
        novo_mouse = draft.mouse.model_copy(update={"dirty": False, "in_profile": True})
        self.draft = draft.model_copy(update={"mouse": novo_mouse})

    def _clear_speaker_dirty(self) -> None:
        """Baixa o ``dirty`` do alto-falante depois de aplicar — irmão do mouse."""
        draft = getattr(self, "draft", None)
        if draft is None or not draft.speaker.dirty:
            return
        novo = draft.speaker.model_copy(update={"dirty": False, "in_profile": True})
        self.draft = draft.model_copy(update={"speaker": novo})


    def on_save_profile(self, _btn: Any = None) -> None:
        """Abre diálogo de nome e persiste DraftConfig como perfil nomeado."""
        window = self._get("main_window")
        active_name: str = self._perfil_que_as_abas_editam()
        nome = gui_dialogs.prompt_profile_name(parent=window, default_name=active_name)
        if nome is None:
            return

        def _perfis_em_disco() -> list[Profile]:
            return load_all_profiles()

        def _on_checked(existentes: list[Profile]) -> bool:
            alvo = find_by_slug(nome, existentes)
            if alvo is not None and not gui_dialogs.prompt_overwrite_existing(
                parent=window, name=alvo.name
            ):
                self._footer_toast(_("Operação cancelada."))
                return False
            self._persist_profile_async(nome, existente=alvo)
            return False

        ipc_bridge.run_in_thread(_perfis_em_disco, on_success=_on_checked)

    def _perfil_que_as_abas_editam(self) -> str:
        """Nome com que o diálogo do rodapé nasce pré-preenchido."""
        draft = getattr(self, "draft", None)
        origem = getattr(draft, "source_name", None) if draft is not None else None
        if isinstance(origem, str) and origem:
            return origem
        return str(getattr(self, "_active_profile_name", "") or "")

    def _prioridade_do_save(self, existente: Profile | None) -> int:
        """Número que o perfil recebe ao ser gravado pelo rodapé.

        GRAVA-POR-UM-FUNIL-01 (04/08/2026): a prioridade só é CALCULADA para
        perfil que NÃO existe em disco. Quem já existe herda a do próprio
        arquivo — recalcular era o segundo dente da catraca medida no rodapé
        (1º save prioridade 10, 2º save 20, 3º 30): um perfil que ela salva
        três vezes subia sozinho até atropelar as regras de jogo dela.

        O ``to_profile`` já protege o caso mais comum — salvar por cima do
        MESMO perfil de onde o rascunho veio preserva ``source_priority``. Mas
        essa guarda depende da fotografia estar fresca, e é exatamente ela que
        envelhecia; e não cobre salvar por cima de um perfil DIFERENTE do
        ativo, onde o número calculado entrava por cima do dela do mesmo jeito.
        Perguntar ao DISCO fecha os dois, sem depender da fotografia.

        PERFIL-NASCE-CERTO-01, que continua valendo para o perfil NOVO: o
        número sai de ``_prioridade_acima_dos_catch_all`` (o mesmo que a aba
        Perfis usa, ``profiles_actions.py``): ``max(prioridade dos catch-all) +
        folga``. Com o disco dela hoje isso dá 15, acima de todos os "vale
        sempre" que ela tem (medido em 30/07: ``fallback`` 0, ``vitoria`` 0,
        ``meu_perfil`` 1, ``Pragmata`` 5, ``Pragmata2`` 5). Sem ele o perfil
        recém-salvo nasceria no default do ESQUEMA (``0``) e perderia para o
        Pragmata — a queixa crônica dela, "a config que eu deixo nunca é
        respeitada".

        O acesso é por `getattr` e não direto, pelo mesmo motivo que o resto
        desta base usa `getattr` para falar com irmão de mixin: dublê de teste
        (e qualquer composição degradada) monta só ESTE mixin, e uma chamada
        direta viraria `AttributeError` no gesto de salvar. O piso do fallback
        não é 0 de propósito — 0 é justamente o valor que reabria o defeito.
        """
        if existente is not None:
            return int(existente.priority)
        calcula = getattr(self, "_prioridade_acima_dos_catch_all", None)
        return int(calcula()) if callable(calcula) else self._PISO_ACIMA_DOS_CATCH_ALL

    def _regra_do_save(self, existente: Profile | None, draft: Any) -> Match:
        """Regra de casamento que o perfil recebe ao ser gravado pelo rodapé."""
        if existente is not None:
            return existente.match
        origem = getattr(draft, "source_match", None)
        if origem is not None:
            candidato = Profile(name="sonda", match=origem)
            if candidato.e_catch_all is False:
                return candidato.match
        return MatchManual()

    @staticmethod
    def _carimbo_do_save(
        existente: Profile | None, do_rascunho: PonteConfirmada | None
    ) -> PonteConfirmada | None:
        """Carimbo de ponte que o perfil leva ao disco. Irmão de ``_regra_do_save``.

        A escada inteira — e o porquê de cada degrau — mora em
        ``profile_writer.carimbo_que_o_save_leva``, que é o dono único desta
        resposta desde a PONTE-SOBREVIVE-A-CORRIDA-01 (28/08/2026): a aba Perfis
        pergunta o MESMO a partir de lá.

        Aqui o degrau 1 chega FRESCO: ``existente`` vem do
        ``load_all_profiles()`` que ``on_save_profile`` roda no worker no
        instante do save, nunca de cache. É por isso que o rodapé nunca teve a
        corrida que a aba Perfis tinha.
        """
        return carimbo_que_o_save_leva(existente, do_rascunho)

    def _persist_profile_async(
        self, nome: str, existente: Profile | None = None
    ) -> None:
        """Grava o DraftConfig como perfil ``nome`` pelo funil único."""
        # Import TARDIO pelo mesmo motivo do `_aplicar_escolha_pendente` logo
        from hefesto_dualsense4unix.app.actions.home_actions import (
            recolher_escolha_pendente_no_rascunho,
        )

        escolhida = dict(getattr(self, "_escolha_pendente", None) or {}).get("mascara")
        recolhido = recolher_escolha_pendente_no_rascunho(self)
        draft = self.draft
        prioridade = self._prioridade_do_save(existente)
        regra = self._regra_do_save(existente, draft)

        def _construir() -> Profile:
            perfil: Profile = draft.to_profile(nome, priority=prioridade)
            return perfil.model_copy(
                update={
                    "match": regra,
                    "ponte": self._carimbo_do_save(existente, perfil.ponte),
                }
            )

        # está por extenso em `_aplicar_o_modo_que_foi_gravado`; em uma linha:
        depois: Callable[[Profile, Path, Any], None] | None = None
        if recolhido:
            gravado: dict[str, str] = recolhido

            def _levar_a_maquina_ate_o_arquivo(
                _perfil: Profile, _caminho: Path, _extra: Any
            ) -> None:
                self._aplicar_o_modo_que_foi_gravado(gravado, escolhida)

            depois = _levar_a_maquina_ate_o_arquivo

        self._gravar_perfil_async(
            _construir,
            adotar_como_ativo=True,
            mensagem_ok=lambda _perfil, caminho: self._texto_do_perfil_salvo(
                caminho, recolhido
            ),
            mensagem_erro=lambda exc: _("Falha ao salvar perfil: {erro}").format(
                erro=exc
            ),
            evento="footer_save_profile",
            depois_na_janela=depois,
        )

    def _aplicar_o_modo_que_foi_gravado(
        self, gravado: dict[str, str], mascara_escolhida: str | None
    ) -> None:
        """O Salvar leva a MÁQUINA até o arquivo que ele acabou de gravar."""
        modo = gravado.get("modo")
        if not modo:
            logger.info("salvar_nao_aplica_sem_modo")
            return
        alvo = _rotulo_do_modo(gravado)

        def _aplicou(resultado: Any) -> None:
            from hefesto_dualsense4unix.app.actions.home_actions import (
                DESFECHO_BLOQUEADO,
                DESFECHO_FALHOU,
                desfecho_da_troca,
                lembrar_mascara_recusada,
                toast_da_troca_de_mascara,
            )

            desfecho = (
                desfecho_da_troca(resultado, pedida=mascara_escolhida)
                if mascara_escolhida
                else None
            )
            if desfecho in (DESFECHO_BLOQUEADO, DESFECHO_FALHOU):
                lembrar_mascara_recusada(self, mascara_escolhida)
                logger.info(
                    "salvar_gravou_e_a_mascara_foi_recusada",
                    desfecho=desfecho,
                    mascara=mascara_escolhida,
                )
                self._footer_toast(
                    _("Perfil salvo. {recado}").format(
                        recado=toast_da_troca_de_mascara(desfecho, mascara_escolhida)
                    )
                )
                return
            _esquecer_a_pendencia(self)
            logger.info("salvar_aplicou_o_modo", modo=modo)
            self._footer_toast(
                _("Perfil salvo, e o modo “{alvo}” já está valendo.").format(alvo=alvo)
            )

        def _falhou(exc: Exception) -> None:
            logger.warning("salvar_nao_aplicou_o_modo", modo=modo, erro=str(exc))
            self._footer_toast(
                _(
                    "Perfil salvo, mas não consegui mudar para “{alvo}” agora "
                    "({erro}) — a escolha continua marcada."
                ).format(alvo=alvo, erro=exc)
            )

        def _sem_relancar(_escolha: str) -> None:
            self._footer_toast(
                _(
                    "Perfil salvo — o modo “{alvo}” está no arquivo e vale "
                    "quando o jogo abrir de novo."
                ).format(alvo=alvo)
            )

        _transicao_de_modo(
            self,
            modo=modo,
            mascara=mascara_escolhida,
            ao_aplicar=_aplicou,
            ao_falhar=_falhou,
            ao_nao_relancar=_sem_relancar,
        )

    def _texto_do_perfil_salvo(
        self, caminho: Any, recolhido: dict[str, str] | None
    ) -> str:
        """O toast do Salvar, dito no instante em que o ARQUIVO ficou pronto.

        A-INICIO-TAMBEM-SALVA-01 (10/08/2026). O Salvar passou a gravar o modo
        que ela escolheu na aba Início, e um toast que dissesse só *"Perfil
        salvo"* deixaria a metade cara da verdade de fora.

        NOTA DATADA — 11/08/2026, O-SALVAR-TAMBEM-APLICA-01. A frase que estava
        aqui — *"o modo foi para o arquivo e vale na próxima abertura do jogo;
        para mudar agora, clique em Aplicar"* — **caducou por decisão dela**,
        textual: *"salvar também aplica"*. A divisão que ela ensinava (o Salvar
        grava, o verde muda a máquina) deixou de existir para o modo: os dois
        botões mudam a máquina agora. Manter aquele texto seria mandá-la clicar
        num botão para terminar um gesto que já terminou — e a pergunta EM
        ABERTO que a nota antiga registrava está respondida em
        ``_aplicar_o_modo_que_foi_gravado``, com a ordem e o desfecho da falha.

        Esta frase é a PRIMEIRA de duas, e o funil a diz antes de
        ``depois_na_janela`` rodar (``profile_writer._ao_gravar``). Ela cobre a
        janela de até 6 s em que o ``apply_mode`` está em voo: sem um "aplicando"
        no rodapé, o silêncio seria lido como "não fez nada" — e a última palavra
        (aplicou / não consegui / está no arquivo) vem do callback.

        Os rótulos vêm de ``_mode_label``/``_flavor_label`` — os MESMOS da aba
        Início e da linha do pendente. Ela lê "Jogar pelo Hefesto" no botão; um
        toast dizendo "gamepad" falaria de uma coisa que não está escrita em
        lugar nenhum da tela (LEIGO-02).
        """
        base = _("Perfil salvo em {caminho}").format(caminho=caminho)
        if not recolhido:
            return base
        return base + " " + _("Aplicando o modo “{alvo}”...").format(
            alvo=_rotulo_do_modo(recolhido)
        )


    def on_import_profile(self, _btn: Any = None) -> None:
        """Abre FileChooserDialog para importar perfil JSON.

        Valida via ``Profile.model_validate``, copia para profiles_dir e
        resolve conflito de nome se necessário.
        """
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        from hefesto_dualsense4unix.profiles.schema import Profile

        window = self._get("main_window")

        chooser = Gtk.FileChooserDialog(
            title="Importar Perfil",
            parent=window,
            action=Gtk.FileChooserAction.OPEN,
        )
        chooser.add_button("Cancelar", Gtk.ResponseType.CANCEL)
        chooser.add_button("Abrir", Gtk.ResponseType.OK)
        chooser.set_default_response(Gtk.ResponseType.OK)

        filtro = Gtk.FileFilter()
        filtro.set_name("Perfis JSON (*.json)")
        filtro.add_pattern("*.json")
        chooser.add_filter(filtro)

        response = gui_dialogs.executar_dialogo(
            chooser, nome="importar_perfil_escolher_arquivo"
        )
        filename = chooser.get_filename()
        chooser.destroy()

        if response != Gtk.ResponseType.OK or not filename:
            return

        def _read() -> tuple[Profile, list[Profile]]:
            raw = json.loads(Path(filename).read_text(encoding="utf-8"))
            profile = Profile.model_validate(raw)
            existentes = list(load_all_profiles())
            return profile, existentes

        def _on_read(payload: tuple[Profile, list[Profile]]) -> bool:
            profile, existentes = payload
            # SLUG (`on_save_profile` e `on_profile_save`) — o importar era o
            alvo = find_by_slug(profile.name, existentes)
            if alvo is not None:
                escolha = gui_dialogs.prompt_import_conflict(
                    parent=window, name=alvo.name
                )
                if escolha is None:
                    self._footer_toast(_("Importação cancelada."))
                    return False
                if escolha == "renomear":
                    novo_nome = gui_dialogs.prompt_profile_name(
                        parent=window, default_name=profile.name
                    )
                    if not novo_nome:
                        self._footer_toast(_("Importação cancelada."))
                        return False
                    if find_by_slug(novo_nome, existentes) is not None:
                        self._footer_toast(
                            _(
                                "'{nome}' ocupa o mesmo arquivo de um perfil que "
                                "já existe — escolha outro nome."
                            ).format(nome=novo_nome)
                        )
                        return False
                    dados = profile.model_dump(mode="python")
                    dados["name"] = novo_nome
                    try:
                        profile = Profile.model_validate(dados)
                    except Exception as exc:
                        self._footer_toast(_("Nome inválido: {erro}").format(erro=exc))
                        return False
            self._import_save_async(profile)
            return False

        def _on_read_err(exc: Exception) -> bool:
            self._footer_toast(_("Arquivo inválido: {erro}").format(erro=exc))
            logger.warning("footer_import_invalido", arquivo=filename, erro=str(exc))
            return False

        ipc_bridge.run_in_thread(_read, on_success=_on_read, on_failure=_on_read_err)

    def _import_save_async(self, profile: Any) -> None:
        """Grava o perfil importado pelo funil único (GRAVA-POR-UM-FUNIL-01)."""
        self._gravar_perfil_async(
            lambda: profile,
            adotar_como_ativo=False,
            mensagem_ok=lambda perfil, caminho: _(
                "Perfil importado: {nome} -> {caminho}"
            ).format(nome=perfil.name, caminho=caminho),
            mensagem_erro=lambda exc: _("Falha ao importar: {erro}").format(erro=exc),
            evento="footer_import",
        )


    def on_restore_default(self, _btn: Any = None) -> None:
        """Restaura o perfil padrão ao estado do asset original."""
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        window = self._get("main_window")

        asset = _meu_perfil_asset()
        if asset is None:
            self._footer_toast(frase_do_preset_ausente())
            logger.warning("footer_restore_default_asset_ausente")
            return

        if not gui_dialogs.confirm_restore_default(parent=window):
            self._footer_toast(_("Restauração cancelada."))
            return

        def _construir() -> Profile:
            raw = json.loads(asset.read_text(encoding="utf-8"))
            raw["name"] = NOME_DO_PADRAO
            return Profile.model_validate(raw)

        def _rascunho_restaurado(profile: Profile) -> Any:
            """Rascunho inteiro relido do disco — roda no WORKER, pós-gravação."""
            try:
                return DraftConfig.from_profile(load_profile(_MEU_PERFIL_NOME))
            except Exception as exc:
                logger.warning("footer_restore_default_draft_falhou", erro=str(exc))
                return DraftConfig.from_profile(profile)

        def _aplicar_rascunho(
            _profile: Profile, _caminho: Path, novo_draft: Any
        ) -> None:
            if novo_draft is not None:
                self.draft = novo_draft
                self._draft_baseline = novo_draft
                logger.info(
                    "footer_restore_default_draft_recarregado",
                    perfil_ativo_agora=_MEU_PERFIL_NOME,
                )
            _refresh_all_tabs(self)

        self._gravar_perfil_async(
            _construir,
            adotar_como_ativo=True,
            mensagem_ok=lambda _perfil, caminho: frase_do_restauro(caminho),
            mensagem_erro=lambda exc: _("Falha ao restaurar: {erro}").format(erro=exc),
            evento="footer_restore_default",
            depois_no_worker=_rascunho_restaurado,
            depois_na_janela=_aplicar_rascunho,
        )


# (`_aplicar_escolha_pendente`) para medir a paridade de IPC entre a Início e a


def _rotulo_do_modo(escolha: dict[str, str]) -> str:
    """"Jogar pelo Hefesto (Xbox 360)" a partir de ``{"modo","mascara"}``."""
    from hefesto_dualsense4unix.app.actions.home_actions import (
        _flavor_label,
        _mode_label,
    )

    alvo = _mode_label(escolha.get("modo"))
    mascara = escolha.get("mascara")
    if mascara:
        alvo = f"{alvo} ({_flavor_label(mascara)})"
    return alvo


def _esquecer_a_pendencia(janela: Any) -> None:
    """Apaga a escolha pendente E a linha "vai mudar para:" da aba Início."""
    from hefesto_dualsense4unix.app.actions.home_actions import render_pendente

    janela._escolha_pendente = None
    render_pendente(janela)


def _transicao_de_modo(
    janela: Any,
    *,
    modo: str,
    mascara: str | None,
    ao_aplicar: Callable[[Any], None],
    ao_falhar: Callable[[Exception], None],
    ao_nao_relancar: Callable[[str], None],
) -> None:
    """A sequência que leva a MÁQUINA ao modo escolhido. Os dois botões usam.

    O-SALVAR-TAMBEM-APLICA-01 (11/08/2026). Este é o caminho CERTO do modo, e
    ele já existia — era o corpo do "Aplicar" (`_aplicar_escolha_pendente`). Ele
    virou função para o "Salvar Perfil" poder percorrê-lo inteiro em vez de
    inventar um segundo caminho; a docstring de `on_apply_draft` diz por que o
    caminho ERRADO (juntar o modo ao `apply_draft`) produz "ERRO ao aplicar" com
    o modo JÁ aplicado.

    O que ela faz, nesta ordem e para os dois botões:

    1. **relê o sinal de jogo na hora** (`_ha_jogo_aberto_agora`) — sem isto o
       Salvar decidiria com o `_jogo_aberto` que a aba Início deixou, que é
       `False` por omissão a partir de qualquer outra aba;
    2. **pergunta, quando há jogo aberto** — modo e máscara mexem no que o jogo
       em curso já leu, e recriar o vpad ao vivo é o caminho do "Jogador 3"
       fantasma (DEPOIS-QUE-APLICAVA-AGORA-01). O Salvar herda a pergunta de
       graça, e tinha de herdar: sem ela o botão de gravar seria mais perigoso
       que o verde;
    3. **dispara `apply_mode`**, com o `MODE_IPC_TIMEOUT_S` de 2,0 s por chamada
       — nunca o 1,5 s do `apply_draft` — e **sem congelar a janela**. Os até
       3 x 2,0 s correm no worker do `ipc_bridge`; quem chama recebe o desfecho
       no `ao_aplicar`/`ao_falhar` e escreve o toast que sabe contar.

    O import de `apply_mode` é TARDIO de propósito, e não só pelo ciclo: é o que
    deixa o `monkeypatch.setattr(mode_transition, "apply_mode", ...)` alcançar
    esta chamada — a armadilha com que as duas suítes provam que a transição
    saiu (ou que não saiu).

    A MÁSCARA que chega aqui é a **escolha explícita** dela, ou `None`. Ecoar de
    volta a máscara vigente do daemon recria o "segundo dono do valor" que a
    AUTO-01.3 enterrou: sem o campo, o daemon preserva a que já está lá.

    ``ao_aplicar`` RECEBE O RESULTADO — I1 da INÍCIO NÃO MENTE-01 (25/08/2026)
    ------------------------------------------------------------------------

    NOTA DATADA. Até aqui a assinatura era ``Callable[[], None]`` e o
    ``_done(_resultado)`` abaixo **descartava a resposta do daemon**. Não era
    detalhe: ``set_gamepad_emulation`` devolve o MESMO ``True`` para três
    desfechos diferentes — apliquei / já estava / **recusei pelo gate R-04** — e
    o handler traduz os três em ``status: "ok"``. Com o jogo aberto, o daemon
    RECUSAVA a troca de máscara e o rodapé anunciava *"O jogo agora vê: Xbox
    360"*, com o journal registrando ``vpad_recriacao_bloqueada_por_jogo`` sete
    milissegundos antes (medido na noite de 18→19/08/2026).

    A cura já estava escrita e nunca ligada: ``home_actions.desfecho_da_troca``
    e ``home_actions.toast_da_troca_de_mascara`` existiam desde 19/08 sem um
    único chamador de produção — o defeito-mãe desta casa. O que faltava era
    esta assinatura. Quem lê o desfecho são os dois chamadores; aqui só se
    entrega o que o daemon respondeu.
    """
    from hefesto_dualsense4unix.app.actions.home_actions import (
        _flavor_label,
        _mode_label,
    )
    from hefesto_dualsense4unix.app.actions.mode_transition import apply_mode

    janela._ha_jogo_aberto_agora()

    def _done(resultado: Any) -> bool:
        ao_aplicar(resultado)
        return False

    def _fail(exc: Exception) -> bool:
        ao_falhar(exc)
        return False

    def _aplicar() -> None:
        apply_mode(modo, flavor=mascara, on_done=_done, on_fail=_fail)

    if mascara:
        mudanca, valor = "mascara", _flavor_label(mascara)
    else:
        mudanca, valor = "modo", _mode_label(modo)

    if janela._perguntar_antes_de_relancar(
        mudanca=mudanca,
        valor=valor,
        aplicar=_aplicar,
        ao_nao_relancar=ao_nao_relancar,
    ):
        return
    _aplicar()


def _lista_de_secoes(secoes: Any) -> str:
    """Nomes legíveis das seções, curtos o bastante para a statusbar."""
    if isinstance(secoes, dict):
        chaves: list[Any] = list(secoes)
    elif isinstance(secoes, list):
        chaves = list(secoes)
    else:
        return ""
    nomes = [_(_NOMES_DE_SECAO.get(str(s), str(s))) for s in chaves]
    if not nomes:
        return ""
    if len(nomes) > _MAX_SECOES_NO_TEXTO:
        return _("{primeiras} e mais {resto}").format(
            primeiras=", ".join(nomes[:_MAX_SECOES_NO_TEXTO]),
            resto=len(nomes) - _MAX_SECOES_NO_TEXTO,
        )
    return ", ".join(nomes)


def _algo_foi_aplicado(result: Any) -> bool:
    """Alguma seção entrou de fato no controle? (APLICAR-VERDADE-02)."""
    if not isinstance(result, dict):
        return True
    aplicadas = result.get("applied")
    if not isinstance(aplicadas, list):
        return True
    return bool(aplicadas)


def _secao_aplicada(result: Any, secao: str) -> bool:
    """A seção ``secao`` está no ``applied`` da resposta? (APLICAR-VERDADE-02)."""
    if not isinstance(result, dict):
        return True
    aplicadas = result.get("applied")
    if not isinstance(aplicadas, list):
        return True
    return secao in aplicadas


def _mensagem_de_aplicacao(result: Any) -> str:
    """Texto do rodapé para uma resposta ACEITA de ``profile.apply_draft``."""
    if not isinstance(result, dict):
        return _("Perfil aplicado ao controle.")
    aplicadas = result.get("applied")
    if isinstance(aplicadas, list) and not aplicadas:
        return _("Nada foi aplicado ao controle.")
    nao_entraram = _lista_de_secoes(result.get("failed"))
    if nao_entraram:
        return _("Aplicado, menos: {secoes}.").format(secoes=nao_entraram)
    return _("Perfil aplicado ao controle.")


def _refresh_all_tabs(mixin: Any) -> None:
    """Dispara refresh das abas que têm método _refresh_*_from_draft."""
    for method_name in (
        "_refresh_lightbar_from_draft",
        "_refresh_triggers_from_draft",
        "_refresh_rumble_from_draft",
        "_refresh_mouse_tab",
        "_refresh_key_bindings_from_draft",
        # Ambos os agregadores são idempotentes e read-only (IPC state_full).
        "_refresh_home_tab",
        "_refresh_emulation_tab",
    ):
        fn = getattr(mixin, method_name, None)
        if fn is not None:
            try:
                fn()
            except Exception as exc:
                logger.warning(
                    "footer_refresh_aba_falhou",
                    metodo=method_name,
                    erro=str(exc),
                )

    reload_fn = getattr(mixin, "_reload_profiles_store", None)
    if reload_fn is not None:
        try:
            reload_fn()
        except Exception as exc:
            logger.warning("footer_refresh_perfis_falhou", erro=str(exc))


__all__ = [
    "FROZEN_WIDGET_IDS",
    "FooterActionsMixin",
]
