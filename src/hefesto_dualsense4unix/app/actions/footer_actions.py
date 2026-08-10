"""Handlers do rodapé global: Aplicar, Salvar Perfil, Importar, Restaurar Default.

``FooterActionsMixin`` é incorporado na MRO de ``HefestoApp``. Todos os handlers
atuam sobre ``self.draft`` (DraftConfig) e instrumentam ``self._footer_toast``
para feedback ao usuário.

Padrão de thread:
- ``on_apply_draft``: usa ``ipc_bridge.call_async`` para não bloquear GTK.
- ``on_save_profile`` / ``on_import_profile`` / ``on_restore_default``: diálogos
  na thread GTK, mas o I/O de disco (carregar/checar conflito/salvar) é despachado
  para um worker via ``ipc_bridge.run_in_thread`` e renderizado no callback
  (``GLib.idle_add``) — PERF-FOOTER-ASYNC-IO-01.

GRAVA-POR-UM-FUNIL-01 (04/08/2026): os TRÊS botões que gravam perfil (Salvar,
Importar, Restaurar Padrão) não chamam ``save_profile`` — eles montam o
``Profile`` e entregam ao ``_gravar_perfil_async`` do ``ProfileWriterMixin``,
que grava e deixa o rascunho apontando para o que ficou em disco. Ver
``actions/profile_writer.py`` para a invariante e o porquê dela; o portão que
impede a recaída é ``tests/unit/test_gravacao_de_perfil_passa_pelo_funil.py``.

Importações de topo para permitir patch nos testes:
- ``ipc_bridge`` exposto como variável de módulo.
- ``gui_dialogs`` exposto como variável de módulo.
- Funções de loader importadas em nível de módulo.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.app import gui_dialogs, ipc_bridge
from hefesto_dualsense4unix.app.actions.profile_writer import ProfileWriterMixin
from hefesto_dualsense4unix.profiles.loader import (
    _seed_source_file,
    load_all_profiles,
    load_profile,
)
from hefesto_dualsense4unix.profiles.schema import Match, MatchManual, Profile
from hefesto_dualsense4unix.profiles.slug import find_by_slug
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# Asset canônico do perfil do usuário (FEAT-PROFILES-PRESET-06).
_MEU_PERFIL_NOME = "meu_perfil"
_MEU_PERFIL_ARQUIVO = f"{_MEU_PERFIL_NOME}.json"


def _meu_perfil_asset() -> Path | None:
    """Acha o preset `meu_perfil.json`; ``None`` quando não há em lugar nenhum.

    JANELA-FIEL-01/E3: este caminho era `ROOT_DIR / "assets" / ...`, e
    `ROOT_DIR` é `parents[3]` do módulo — a raiz do repositório SÓ em instalação
    editável. Num `.deb`/AppImage/Flatpak o módulo vive dentro de um venv e
    `parents[3]` cai num diretório onde `assets/` nunca existiu, então o botão
    "Restaurar Padrão" desistia com o toast de indisponível numa máquina onde o
    preset ESTÁ instalado — os três pacotes o embalam, em
    `sys.prefix/share/...` ou em `/usr/share/...`.

    Quem responde é a cascata do loader (`_seed_source_file`), a mesma que
    semeia os presets em produção: repo editável → prefixo → `/usr/share`. Sem
    caminho duplicado aqui, o botão passa a achar o arquivo onde ele realmente
    está.
    """
    return _seed_source_file(_MEU_PERFIL_ARQUIVO)


# APLICAR-VERDADE-01: nome de cada seção do contrato IPC na língua da janela.
# O daemon fala "leds"/"triggers"; o rodapé precisa dizer o que não entrou com
# as palavras que ela lê nas abas. O dicionário guarda o PT-BR cru porque é
# construído no import, antes de `init_locale()` — traduzir AQUI congelaria o
# idioma errado. A tradução acontece no ponto de USO, em `_lista_de_secoes`.
_NOMES_DE_SECAO: dict[str, str] = {
    "leds": "luzes",
    "triggers": "gatilhos",
    "rumble": "vibração",
    "mouse": "mouse",
    "keyboard": "teclado",
    "mic": "microfone",
    # O-VERDE-NAO-LEVAVA-O-SOM-01: sem esta linha a seção aparecia na statusbar
    # como `speaker` cru, em inglês, no meio de uma frase em português — e é
    # justamente a linha que ela leria quando o som falhasse.
    "speaker": "alto-falante",
    "controllers": "ajustes por controle",
}

# A statusbar trunca com reticências em meia tela: acima disto a lista vira
# "os três primeiros e mais N".
_MAX_SECOES_NO_TEXTO = 3

# Widgets congelados durante operação de aplicar draft.
FROZEN_WIDGET_IDS: tuple[str, ...] = (
    "btn_footer_apply",
    "btn_footer_save_profile",
    "btn_footer_import",
    "btn_footer_restore_default",
    "lightbar_color_button",
    "lightbar_brightness_scale",
    # BUG-FROZEN-WIDGET-IDS-01: IDs reais do glade (eram *_combo / mouse_toggle,
    # que não existem -> freeze nunca cobria triggers nem o toggle de mouse).
    # FEAT-DSX-COMBO-TO-SEGMENTED-01: o combo de modo virou um slot (GtkBox) com
    # o SegmentedSelector dentro; congelar o slot propaga insensitive aos botões.
    "trigger_left_mode_slot",
    "trigger_right_mode_slot",
    "rumble_weak_scale",
    "rumble_strong_scale",
    "mouse_emulation_toggle",
    # BUG-MOUSE-GUI-SYNC-01: os sliders da aba Mouse também disparam IPC —
    # precisam congelar junto durante a transação do Aplicar.
    "mouse_speed_scale",
    "mouse_scroll_speed_scale",
)


class FooterActionsMixin(ProfileWriterMixin):
    """Handlers dos 4 botões do rodapé global da GUI.

    GRAVA-POR-UM-FUNIL-01: a base é o ``ProfileWriterMixin`` porque os TRÊS
    botões que gravam perfil (Salvar, Importar, Restaurar Padrão) passam pelo
    mesmo funil — nenhum deles chama ``save_profile`` por conta própria. Herdar
    (em vez de importar uma função) é o que dá ao funil o ``self.draft`` e o
    ``_active_profile_name`` que ele precisa manter coerentes com o disco.
    """

    # Referência ao draft central (definida em HefestoApp.__init__).
    draft: Any  # DraftConfig — evita import circular; validado em runtime

    #: Piso usado quando o cálculo do irmão não está alcançável — ver
    #: `_persist_profile_async`. Vale mais que TODO catch-all medido no disco
    #: dela em 30/07 (o maior era 5), então mesmo o caminho degradado nasce
    #: vencendo; e vale MENOS que a regra de jogo mais baixa de fábrica (50),
    #: então não atropela perfil de jogo alheio.
    _PISO_ACIMA_DOS_CATCH_ALL = 15

    # ------------------------------------------------------------------
    # Controle de freeze
    # ------------------------------------------------------------------

    def _freeze_ui(self, freeze: bool) -> None:
        """Habilita ou desabilita widgets conhecidos durante operação longa.

        Itera ``FROZEN_WIDGET_IDS`` e seta ``sensitive`` conforme ``freeze``.
        Widgets ausentes no builder são ignorados silenciosamente.
        """
        sensitive = not freeze
        for widget_id in FROZEN_WIDGET_IDS:
            widget = self._get(widget_id)
            if widget is not None:
                widget.set_sensitive(sensitive)
        if freeze:
            return
        # HARM-05: descongelar é "devolver o que a transação tomou", não "liberar
        # tudo" — o switch do mouse tem um gate próprio (só em "Controlar o PC")
        # e um set_sensitive(True) cego aqui o reabria fora do modo desktop,
        # ressuscitando o clique que derruba o vpad no meio do jogo. Reconciliar
        # com o daemon reaplica o gate (e a aba volta a mostrar o estado vivo).
        reconcile = getattr(self, "_refresh_mouse_from_daemon_async", None)
        if reconcile is not None:
            try:
                reconcile()
            except Exception as exc:
                logger.warning("footer_regate_mouse_falhou", erro=str(exc))

    # ------------------------------------------------------------------
    # Statusbar
    # ------------------------------------------------------------------

    def _footer_toast(self, msg: str, context: str = "footer") -> None:
        """Empurra mensagem na statusbar com contexto ``context``."""
        self._status_toast(context, msg)

    # ------------------------------------------------------------------
    # DEDUP-04: aviso ao daemon quando o conjunto de perfis muda
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Handler: Aplicar
    # ------------------------------------------------------------------

    def on_apply_draft(self, _btn: Any = None) -> None:
        """O botão verde do rodapé. Aplica o AGORA e, se houver, o DEPOIS.

        AGORA-E-DEPOIS-01 (08/08/2026). Este handler mandava só o ``DraftConfig``
        — e o payload dele **não carrega modo nem máscara** por contrato
        (``draft_config.to_ipc_dict``, e o porquê está lá). Era o defeito 1 da
        OITO-DEFEITOS-01, na palavra dela: *"quando eu clico ali no inferior no
        verde em aplicar, ele não aplica e não abre o pop up"*.

        Agora ele é o dono dos DOIS tempos da janela:

        - o **AGORA** (gatilhos, LEDs, rumble, mouse, mic, teclado) segue pelo
          ``profile.apply_draft``, como sempre;
        - o **DEPOIS** (modo e máscara, que o jogo só lê quando abre) vem da
          escolha pendente da aba Início e passa antes, pelo caminho que já
          existe — ``mode_transition.apply_mode``, nunca por dentro do
          ``apply_draft``. Ver o fato 5 do plano: ``apply_mode`` dispara até 3
          chamadas de 2,0 s e o ``apply_draft`` daqui tem ``timeout_s=1.5``;
          juntá-los produziria "ERRO ao aplicar" com o modo JÁ aplicado, que é
          exatamente a mentira que o APLICAR-VERDADE-02 existe para matar.

        Sem pendência nada disto acontece e o caminho é o de sempre — inclusive
        para quem não tem a aba Início montada (``getattr`` devolve ``None``).
        """
        pendente = getattr(self, "_escolha_pendente", None)
        if pendente:
            self._aplicar_escolha_pendente(dict(pendente))
            return
        self._apply_draft_agora()

    def _ha_jogo_aberto_agora(self) -> bool:
        """Relê o sinal de jogo aberto NA HORA. Devolve o que ficou em cache.

        JOGO-ABERTO-SO-NA-INICIO-01 (09/08/2026) — defeito achado por
        verificação adversarial poucas horas depois de a cura que ele fura ter
        sido entregue.

        O ``_jogo_aberto`` tem UM escritor: `home_actions._render_home`
        (`:1339`), e ele **só roda com a aba Início à vista** — o poller checa a
        página corrente antes de trabalhar (`home_actions.py:1050-1054`).
        Consequência: clicar no "Aplicar" a partir da aba Lightbar, ou nos
        primeiros 2 s da janela, deixava o flag em ``False`` e o diálogo **não
        aparecia** — a transição saía direto, com o jogo aberto. É exatamente o
        caminho que produziu o "Jogador 3" fantasma, e que esta leva dizia ter
        fechado.

        Por que uma leitura SÍNCRONA aqui é aceitável, sendo que a casa recusa
        I/O bloqueante na thread do GTK: este método só roda no clique do
        "Aplicar", que **já congela a janela** para a transação
        (`_apply_draft_agora`), e o teto é o mesmo `STATE_IPC_TIMEOUT_S` que a
        aba Início usa para a MESMA leitura. Não há caminho de tique por aqui.

        Falha para o lado de **não mudar de opinião**: qualquer erro mantém o
        valor que estava lá. Um diálogo que não aparece por engano é ruim, mas
        um diálogo que aparece porque o IPC engasgou interrompe a partida dela —
        e essa é a assimetria que o `_perguntar_antes_de_relancar` já declara.
        """
        import contextlib

        from hefesto_dualsense4unix.app.actions.mode_transition import (
            STATE_IPC_TIMEOUT_S,
        )

        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.app.ipc_bridge import _run_call

            estado = _run_call("daemon.state_full", None, timeout=STATE_IPC_TIMEOUT_S)
            if isinstance(estado, dict):
                sinal = estado.get("game_signal")
                # MESMO critério da aba Início (`home_actions.py:1337-1341`) —
                # duas leituras do mesmo fato não podem discordar.
                self._jogo_aberto = (
                    isinstance(sinal, dict) and sinal.get("authority") == "game"
                )
        return bool(getattr(self, "_jogo_aberto", False))

    def _aplicar_escolha_pendente(self, pendente: dict[str, str]) -> None:
        """Aplica o que ela escolheu na aba Início e SÓ ENTÃO o rascunho.

        AGORA-E-DEPOIS-01. Três caminhos, e a diferença entre eles é uma só
        pergunta — *há um jogo aberto agora?*:

        1. **sem jogo** → aplica a transição e emenda o ``apply_draft`` no
           callback de sucesso;
        2. **com jogo aberto** → o diálogo de relançamento pergunta
           (``base._perguntar_antes_de_relancar``), tanto para a máscara quanto
           para o modo: os dois mexem no que o jogo em curso já leu, e ela
           decidiu isso vendo a tela em 08/08 à noite (§12.2 do plano).

        NOTA DATADA (09/08/2026, madrugada): as três linhas que estavam aqui
        diziam que o modo **não** perguntava, e caducaram na mesma noite em que
        foram escritas — ``"modo"`` voltou a `relancar.EXIGEM_RELANCAR`
        (`relancar.py:47-71`) horas depois. Uma verificação adversarial pegou a
        contradição entre este texto e o código. Fica registrado porque é a
        mesma família de defeito que esta casa persegue na tela: **um comentário
        que descreve o gesto errado mente onde mais custa** — para quem for
        mexer aqui depois.

        O ESTADO DO JOGO É LIDO NA HORA, e essa parte é a metade que faltava.
        Ver `_ha_jogo_aberto_agora`.
        """
        from hefesto_dualsense4unix.app.actions.home_actions import (
            _flavor_label,
            _mode_label,
            registrar_modo_no_rascunho,
            render_pendente,
        )
        from hefesto_dualsense4unix.app.actions.mode_transition import apply_mode

        # JOGO-ABERTO-SO-NA-INICIO-01 (09/08/2026): confere ANTES de decidir.
        self._ha_jogo_aberto_agora()

        # O alvo do modo: a escolha dela, ou — quando só a máscara mudou — o que
        # já está valendo. Nunca um default nosso: escolher "gamepad" por conta
        # própria aqui seria um segundo dono do valor, o defeito que a AUTO-01.3
        # enterrou.
        modo_alvo = pendente.get("modo") or getattr(
            self, "_modo_vigente_do_daemon", None
        )
        mascara_alvo = pendente.get("mascara")
        if not modo_alvo:
            # Sem modo vigente conhecido (daemon offline, aba nunca renderizada)
            # não há transição honesta a fazer — some com a pendência não, que
            # é dela; só segue com o que este botão sempre soube aplicar.
            logger.info("aplicar_pendencia_sem_modo_vigente")
            self._apply_draft_agora()
            return

        def _done(_resultado: Any) -> bool:
            # Decisão 3 dela (08/08, noite): o modo entra no rascunho AQUI —
            # quando o Aplicar confirma —, nunca no clique. O rascunho descreve
            # o que ficou DE PÉ; uma intenção que falhou não pode virar perfil
            # salvo. (Este registro morava nos callbacks dos seletores da aba
            # Início, e veio junto com o IPC que saiu de lá.)
            #
            # A-VONTADE-DA-GUI-PREVALECE-01 (09/08/2026) — decisão dela, e ela
            # resolve uma dúvida que a auditoria desta madrugada levantou.
            #
            # A auditoria apontou que registrar aqui planta um `mode.kind` no
            # perfil mesmo quando ela mexeu SÓ na máscara (o `modo_alvo` cai no
            # vigente do daemon, `:311`), e chamou isso de eco virando opinião —
            # a família do `enabled` do mouse que o HARM-05 arrancou.
            #
            # Cheguei a recusar o registro nesse caso. **Estava errado**, e ela
            # cortou em uma frase: *"a vontade na GUI prevalece sempre"*.
            #
            # O raciocínio dela fecha melhor que o meu: a máscara SÓ existe
            # dentro de "Jogar pelo Hefesto" (`home_actions._on_home_flavor_
            # changed` recusa em qualquer outro modo), então escolher máscara É
            # escolher o modo em que ela vale. O `kind` que viaja junto não é
            # eco — é a metade implícita do gesto dela. E o esquema não aceita
            # máscara sem `kind` (`profiles/schema.ProfileModeConfig`), então
            # recusar o `kind` era recusar a máscara: perder o gesto dela para
            # proteger o perfil de uma opinião que ela deu.
            registrar_modo_no_rascunho(
                self,
                modo_alvo,
                mascara_alvo or getattr(self, "_mascara_vigente_do_daemon", None),
            )
            self._escolha_pendente = None
            render_pendente(self)
            # E só agora o AGORA: as sete seções do rascunho. Emendado no
            # sucesso, não disparado em paralelo — duas transações concorrentes
            # sobre o mesmo controle é como se recria vpad no meio de uma
            # aplicação de LEDs.
            self._apply_draft_agora()
            return False

        def _fail(exc: Exception) -> bool:
            # A pendência FICA quando a transição falha: ela ainda não valeu, e
            # apagá-la aqui faria a linha "vai mudar para:" sumir da tela sem
            # que nada tivesse mudado — a janela mentindo por omissão.
            logger.warning("aplicar_pendencia_falhou", erro=str(exc))
            # O-AGORA-NAO-E-REFEM-DO-DEPOIS-01 (08/08/2026, noite): esta linha
            # é o conserto de um defeito MEU, achado por verificação adversarial
            # e provável causa do *"não aplica mais as cores"* que ela relatou.
            #
            # Sem ela, uma transição de modo que FALHASSE engolia as sete seções
            # do rascunho — gatilhos, LEDs, rumble, mouse, mic, teclado — em
            # silêncio, e o toast falava só do modo. E não é hipótese remota: o
            # `apply_mode` espera 2,0 s por chamada, e a recriação do vpad com
            # dois controles, MEDIDA no journal dela hoje, levou ~1,7 s. Está na
            # borda: um estouro do timeout levava a cor dela junto.
            #
            # A regra que fica: **o AGORA nunca é refém do DEPOIS.** Cor,
            # brilho, gatilho e vibração mudam na hora e não dependem de o jogo
            # abrir — falhar em preparar a próxima abertura não pode cancelar o
            # que já valia agora.
            self._footer_toast(
                _(
                    "Não consegui preparar o que vale na próxima abertura "
                    "({erro}) — o resto dos ajustes foi aplicado."
                ).format(erro=exc)
            )
            self._apply_draft_agora()
            return False

        def _aplicar() -> None:
            apply_mode(
                modo_alvo,
                flavor=mascara_alvo,
                on_done=_done,
                on_fail=_fail,
            )

        if mascara_alvo:
            mudanca, valor = "mascara", _flavor_label(mascara_alvo)
        else:
            mudanca, valor = "modo", _mode_label(modo_alvo)

        def _sem_relancar(escolha: str) -> None:
            """Os dois ramos em que o jogo NÃO é relançado.

            Em ambos, o modo/máscara não são aplicados — recriariam o vpad ao
            vivo, que é o dano que o diálogo existe para evitar
            (DEPOIS-QUE-APLICAVA-AGORA-01). E em ambos **o AGORA sai**: as sete
            seções do rascunho não mexem no jogo em curso e são trabalho dela.

            A diferença está na PENDÊNCIA:

            - *"na próxima abertura"* → some da tela, porque o toast do diálogo
              acabou de dizer que ela precisa refazer a escolha depois de fechar
              o jogo. Deixar a linha "vai mudar para:" acesa poria a tela
              contradizendo o rodapé no mesmo segundo. (É aqui que o passo 6 do
              plano entra quando existir: a pendência gravada em disco, aplicada
              sozinha quando o jogo fechar.)
            - *"cancelar"* → **fica**. Ela não desistiu da escolha; ela recusou
              relançar o jogo agora. Apagá-la seria decidir no lugar dela.
            """
            if escolha != "cancelar":
                self._escolha_pendente = None
                render_pendente(self)
            self._apply_draft_agora()

        if self._perguntar_antes_de_relancar(
            mudanca=mudanca,
            valor=valor,
            aplicar=_aplicar,
            ao_nao_relancar=_sem_relancar,
        ):
            return
        _aplicar()

    def _apply_draft_agora(self) -> None:
        """Envia DraftConfig inteiro ao daemon via IPC ``profile.apply_draft``.

        Congela UI durante a transação (~500ms); callback via GLib.idle_add
        reabilita e exibe resultado na statusbar.
        """
        # O-AGORA-NAO-E-REFEM-DO-DEPOIS-01: o payload é montado ANTES do
        # congelamento, e a ordem não é estética. `FROZEN_WIDGET_IDS` inclui o
        # `lightbar_color_button` e o `lightbar_brightness_scale`: se
        # `to_ipc_dict()` levantasse com a UI já congelada, a exceção subiria e
        # os controles de cor ficariam INSENSÍVEIS pelo resto da sessão — que é,
        # ao pé da letra, "não aplica mais as cores". Montar primeiro faz uma
        # falha de serialização não deixar rastro na tela.
        draft_dict = self.draft.to_ipc_dict()
        self._freeze_ui(True)
        self._footer_toast(_("Aplicando perfil inteiro..."))

        def _on_ok(result: Any) -> bool:
            self._freeze_ui(False)
            # APLICAR-VERDADE-02: DUAS perguntas diferentes, que eram uma só.
            # `aceita` = o daemon respondeu (não está offline nem recusou) e
            # decide QUAL frase o rodapé usa. `aplicou` = alguma seção entrou
            # de fato no controle, e é o que pode baixar o `dirty` e o que o
            # journal registra. Enquanto foram a mesma variável, `ok` era
            # SEMPRE True (o `status` do `apply_draft` é fixo em "ok" por
            # contrato): o rodapé parou de mentir em e8f9060, mas a
            # contabilidade continuava dizendo `ok=True` e baixando o `dirty`
            # do mouse com as sete seções fora.
            if isinstance(result, bool):
                aceita = result
            elif isinstance(result, dict):
                aceita = result.get("status") == "ok"
            else:
                aceita = bool(result)
            aplicou = aceita and _algo_foi_aplicado(result)
            # A pendência do mouse só acaba se a seção MOUSE entrou: com
            # `applied=["leds"]` e `failed={"mouse": ...}` algo foi aplicado,
            # mas a edição do mouse continua por aplicar — baixar o `dirty`
            # aqui a perderia em silêncio.
            if aplicou and _secao_aplicada(result, "mouse"):
                self._clear_mouse_dirty()
            # O-VERDE-NAO-LEVAVA-O-SOM-01 (10/08/2026): o som ganhou o mesmo
            # tratamento do mouse no MESMO tique em que passou a viajar. Sem
            # isto o `speaker.dirty` ficaria de pé o resto da sessão e todo
            # Aplicar seguinte reenviaria o mesmo volume — idempotente, sem dano
            # medido, e assimétrico com o vizinho de cima sem nenhuma razão.
            if aplicou and _secao_aplicada(result, "speaker"):
                self._clear_speaker_dirty()
            msg = (
                _mensagem_de_aplicacao(result)
                if aceita
                else _("ERRO ao aplicar perfil (daemon offline?).")
            )
            self._footer_toast(msg)
            logger.info(
                "footer_apply_draft_resultado", ok=aplicou, aceita=aceita
            )
            return False  # GLib.idle_add não repete

        def _on_err(exc: Exception) -> bool:
            self._freeze_ui(False)
            self._footer_toast(_("ERRO ao aplicar: {erro}").format(erro=exc))
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
        """Baixa o ``dirty`` da seção mouse DEPOIS de aplicar com sucesso (HARM-05).

        ``dirty`` quer dizer "há uma edição de mouse por aplicar" — e era ligado
        para nunca mais baixar (o único ``dirty=False`` era a carga programática
        do bootstrap): a seção viajava em todo "Aplicar" pelo resto da sessão, e
        a aba Mouse nunca mais se reconciliava com o estado vivo (o overlay do
        daemon pula enquanto houver edição pendente). Aplicou, acabou a
        pendência.

        Isto NÃO é o que impede o Aplicar de mexer no modo — quem garante isso é
        ``to_ipc_dict``, que não emite ``enabled`` (o dano vinha do PRIMEIRO
        Aplicar, que uma limpeza no callback de sucesso não alcança: ela roda
        depois de o payload já ter ido e voltado).

        ``in_profile=True`` junto: a seção deixa de ser "edição pendente" e passa
        a fazer parte da configuração, que é exatamente o que ``to_profile``
        pergunta. Sem isso, "Aplicar" antes de "Salvar Perfil" faria o perfil
        salvo perder a seção mouse (BUG-MOUSE-SAVE-DROPS-SECTION-01 de novo).
        """
        draft = getattr(self, "draft", None)
        if draft is None or not draft.mouse.dirty:
            return
        novo_mouse = draft.mouse.model_copy(update={"dirty": False, "in_profile": True})
        self.draft = draft.model_copy(update={"mouse": novo_mouse})

    def _clear_speaker_dirty(self) -> None:
        """Baixa o ``dirty`` do alto-falante depois de aplicar — irmão do mouse.

        Mesma regra e mesma razão do ``_clear_mouse_dirty``, que a docstring ao
        lado explica por extenso: aplicou, acabou a pendência. E o
        ``in_profile=True`` junto pelo mesmo motivo — sem ele, "Aplicar" antes de
        "Salvar Perfil" faria o perfil salvo perder a seção do som, que é
        exatamente o defeito que ela relatou em 10/08 no outro sentido.
        """
        draft = getattr(self, "draft", None)
        if draft is None or not draft.speaker.dirty:
            return
        novo = draft.speaker.model_copy(update={"dirty": False, "in_profile": True})
        self.draft = draft.model_copy(update={"speaker": novo})

    # ------------------------------------------------------------------
    # Handler: Salvar Perfil
    # ------------------------------------------------------------------

    def on_save_profile(self, _btn: Any = None) -> None:
        """Abre diálogo de nome e persiste DraftConfig como perfil nomeado.

        Usa ``DraftConfig.to_profile(name)`` e ``save_profile(profile)``.
        Após salvar, dispara refresh da aba Perfis se disponível.

        PERF-FOOTER-ASYNC-IO-01: o diálogo de nome roda na thread GTK, mas o I/O
        de disco (checagem de conflito + gravação) é despachado para um worker via
        ``ipc_bridge.run_in_thread``, com o resultado renderizado no callback
        (``GLib.idle_add``). A checagem de conflito é feita NO DISCO dentro do
        worker (nunca no cache em memória), evitando decisão com estado stale.
        """
        window = self._get("main_window")
        active_name: str = self._perfil_que_as_abas_editam()
        nome = gui_dialogs.prompt_profile_name(parent=window, default_name=active_name)
        if nome is None:
            return  # usuário cancelou

        # Worker: lê os perfis do disco (sem cache) p/ checar conflito.
        def _perfis_em_disco() -> list[Profile]:
            return load_all_profiles()

        def _on_checked(existentes: list[Profile]) -> bool:
            # R-10 (auditoria 23/07): a identidade de um perfil em disco é o
            # SLUG — `save_profile` grava `<slugify(name)>.json`. Este gate
            # comparava NOME CRU, então "Navegacao" digitado aqui não casava com
            # a "Navegação" dela em disco: o diálogo não aparecia e
            # `navegacao.json` era regravado em silêncio, com prioridade e regra
            # de janela recalculadas — um catch-all a mais no lugar do perfil.
            # O diálogo cita `alvo.name` e não `nome`: quem some é o perfil do
            # disco. Mesma guarda que a aba Perfis e a CLI já usam.
            alvo = find_by_slug(nome, existentes)
            if alvo is not None and not gui_dialogs.prompt_overwrite_existing(
                parent=window, name=alvo.name
            ):
                self._footer_toast(_("Operação cancelada."))
                return False
            # GRAVA-POR-UM-FUNIL-01: `alvo` viaja junto porque é a resposta à
            # pergunta "este perfil JÁ existe em disco?" — quem existe herda a
            # prioridade do próprio arquivo em vez de receber um número novo
            # (ver `_prioridade_do_save`).
            self._persist_profile_async(nome, existente=alvo)
            return False

        ipc_bridge.run_in_thread(_perfis_em_disco, on_success=_on_checked)

    def _perfil_que_as_abas_editam(self) -> str:
        """Nome com que o diálogo do rodapé nasce pré-preenchido.

        NUNCA-TROCA-O-ALVO-01 (06/08/2026), terceiro caminho da queixa *"clico
        em salvar e ele salva com um nome aleatório ou de outro perfil"*.

        A fonte era `_active_profile_name` — uma segunda variável, escrita pela
        janela com a resposta do DAEMON, e que por isso descreve o perfil que
        está TOCANDO no controle, não o que as abas estão mostrando. As duas
        divergem, e foi medido: com o jogo abrindo, a reconciliação do tique de
        2 Hz movia `_active_profile_name` sozinha e o diálogo nascia perguntando
        "substituir 'sackboy_nativo'?" — um nome que ela nunca digitou nem
        escolheu. Pior: o "Salvar este perfil" da aba Perfis e o "Salvar Perfil"
        do rodapé, na MESMA janela e no mesmo instante, miravam arquivos
        diferentes.

        A fonte passa a ser a fotografia que o próprio rascunho carrega
        (``draft.source_name``, gravada por ``from_profile`` /
        ``with_profile_identity``). É a única resposta honesta para este botão:
        ele emite o RASCUNHO, então o perfil que ele quer sobrescrever é aquele
        de onde o rascunho veio. Uma fonte só, e ela viaja junto do dado que vai
        para o disco em vez de ao lado dele.

        `_active_profile_name` continua como degrau de trás: o rascunho pode não
        ter fotografia (defaults seguros no boot sem daemon), e nesse caso o
        nome do perfil ativo ainda é melhor do que campo vazio.
        """
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
        """Regra de casamento que o perfil recebe ao ser gravado pelo rodapé.

        REGRA-NAO-SE-PERDE-02 (05/08/2026, decisão dela). Irmão de
        ``_prioridade_do_save``, e pela mesma razão: o diálogo do rodapé não
        tem campo de regra, então a regra tem de VIR de algum lugar. Cada
        degrau desta escada é uma fonte, da mais autoritária para a menos.

        Degrau 1 — ``existente.match``, o DISCO. REGRA-NAO-SE-PERDE-01
        (05/08): quem já existe tem regra, e regra não se perde por um gesto
        que a tela nem sabe nomear. Foi o que transformou o ``sackboy_nativo``
        dela — regra ``steam_app_1599660`` — num catch-all no meio da sessão
        de jogo. A herança sai do disco, não da fotografia do rascunho, pelo
        mesmo motivo do ``_prioridade_do_save``: a fotografia envelhece.

        Degrau 2 — ``draft.source_match``, a regra do perfil de ORIGEM. É a
        herança NOVA, e é a revogação medida da frase *"nome NOVO pelo rodapé
        nasce ``MatchAny()``"* (``draft_config.py``, 23/07): ela nasceu para
        impedir que um perfil novo herdasse o regex de OUTRO jogo, mas o que
        entregava no lugar era um catch-all — e catch-all, dentro do jogo, é
        pior que a regra errada (ver o degrau 3). Quando ela está com o jogo em
        foco e salva "MadJack", a regra de origem É a regra do jogo, e é ela
        que faz o perfil recém-salvo valer dentro da partida.

        O predicado do degrau 2 é ESTRUTURAL, não de tipo: constrói-se o
        candidato e pergunta-se ``e_catch_all``. Isso cobre de uma vez o
        ``MatchAny`` e o ``MatchCriteria`` de campos vazios (as DUAS formas de
        catch-all, R-01) sem inventar predicado novo — herdar "vale sempre" não
        é herdar regra nenhuma.

        Degrau 3 — órfão, sem disco e sem origem: ``MatchManual()``, e **não**
        ``MatchAny()``. ``MatchAny`` não é neutro, é catch-all:

        - perde para QUALQUER regra na chave de seleção
          (``profiles/manager.py``, ``(não é catch-all, prioridade)``);
        - dispara o veto R-21 — janela ``steam_app_*`` com só catch-all
          candidato devolve ``MOTIVO_JOGO_SEM_PERFIL_PROPRIO``, ou seja, o
          perfil NUNCA ativa dentro do jogo;
        - e, ao mesmo tempo, nasce com ``max(catch-all) + folga`` de prioridade
          e ganha o desktop INTEIRO, carregando junto o
          ``suppress_desktop_emulation``.

        É exatamente a forma do ``sackboy_nativo`` de 05/08: invisível onde
        deveria valer, soberano onde não deveria. ``MatchManual`` não tem nada
        disso — ``matches()`` é sempre ``False`` (nunca vira candidato),
        ``e_catch_all`` é ``False`` para ele (não dispara o veto nem a
        reversão de modo), a ``profiles/sanidade.py`` o isenta, e ele é a
        tradução literal do que o diálogo do rodapé significa: *"guarde o que
        eu tenho agora; quando usar, eu digo"*.

        RESSALVA de downgrade, a mesma do ``MatchManual`` no esquema
        (``profiles/schema.py``): perfil gravado com ``{"type": "manual"}`` é
        rejeitado por binário ANTIGO, que não conhece o discriminador.
        """
        if existente is not None:
            return existente.match
        origem = getattr(draft, "source_match", None)
        if origem is not None:
            candidato = Profile(name="sonda", match=origem)
            if candidato.e_catch_all is False:
                return candidato.match
        return MatchManual()

    def _persist_profile_async(
        self, nome: str, existente: Profile | None = None
    ) -> None:
        """Grava o DraftConfig como perfil ``nome`` pelo funil único.

        GRAVA-POR-UM-FUNIL-01: aqui só se monta o ``Profile``; gravar,
        reapontar o rascunho (``with_profile_identity``), zerar a linha de base,
        recarregar a lista e avisar o daemon é trabalho do
        ``_gravar_perfil_async`` — o mesmo para os três botões que gravam.

        ``adotar_como_ativo=True`` porque este gesto É trocar o que a janela
        edita: depois de "Salvar Perfil" como "MadJack", o rascunho descreve o
        MadJack. Era a linha que faltava — sem ela o ``source_name`` continuava
        no perfil anterior e o SEGUNDO save do mesmo nome caía no ramo "nome
        novo" do ``to_profile``, gravando ``MatchAny()`` por cima da regra de
        janela que ela acabara de criar.

        REGRA-NAO-SE-PERDE-01 (05/08/2026, decisão dela) — **quem já existe em
        disco herda o próprio ``match``**, exatamente como já herdava a
        prioridade. Era o rodapé aplicando o ramo "nome novo" a **nome que JÁ
        EXISTE**: ali ele não estava "nascendo" coisa nenhuma, estava apagando
        a regra de um perfil que já tinha uma. Foi o que transformou o
        ``sackboy_nativo`` dela — regra ``steam_app_1599660`` — num catch-all,
        no meio da sessão de jogo, e o que fez o perfil do jogo perder DENTRO
        do jogo (a chave de seleção é ``(não é catch-all, prioridade)``:
        catch-all perde para qualquer regra, e por isso a prioridade 191 não a
        salvava).

        REGRA-NAO-SE-PERDE-02 (05/08/2026, mesma decisão dela, um degrau
        adiante) — o ``model_copy`` do ``match`` deixou de ser condicional. Até
        aqui ele só valia para quem existia em disco, e o nome NOVO caía no
        ``MatchAny()`` do ``to_profile``; a nota deste dia em
        ``draft_config.py`` conta por que aquela frase caducou. Agora a regra
        de TODO save do rodapé sai de ``_regra_do_save`` — disco, depois a
        origem do rascunho, e ``MatchManual()`` para o órfão. O ``to_profile``
        não foi tocado de propósito: ele tem dois chamadores, e o gate
        ``mesmo_perfil`` governa quatro campos com a mesma regra.

        Por que ``model_copy`` e não ``model_validate``: o ``model_dump`` do
        segundo DENSIFICA os ``controllers`` parciais (defaults do esquema
        viram campos explícitos) e reabriria a resolução-por-objeto refutada —
        a guarda está escrita no fim do ``DraftConfig.to_profile``.
        """
        draft = self.draft
        prioridade = self._prioridade_do_save(existente)
        regra = self._regra_do_save(existente, draft)

        def _construir() -> Profile:
            # A anotação é o que dá tipo ao retorno: `self.draft` é `Any` no
            # mixin (o `DraftConfig` viria por import circular).
            perfil: Profile = draft.to_profile(nome, priority=prioridade)
            return perfil.model_copy(update={"match": regra})

        self._gravar_perfil_async(
            _construir,
            adotar_como_ativo=True,
            mensagem_ok=lambda _perfil, caminho: _(
                "Perfil salvo em {caminho}"
            ).format(caminho=caminho),
            mensagem_erro=lambda exc: _("Falha ao salvar perfil: {erro}").format(
                erro=exc
            ),
            evento="footer_save_profile",
        )

    # ------------------------------------------------------------------
    # Handler: Importar
    # ------------------------------------------------------------------

    def on_import_profile(self, _btn: Any = None) -> None:
        """Abre FileChooserDialog para importar perfil JSON.

        Valida via ``Profile.model_validate``, copia para profiles_dir e
        resolve conflito de nome se necessário.
        """
        # Import tardio de Gtk para permitir testes sem GTK instalado.
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

        # DIÁLOGO-QUE-MATA-A-JANELA-01 (06/08/2026): o seletor de arquivo é
        # modal e bloqueante como os avisos — e um seletor que nasce invisível
        # mata a janela do mesmo jeito. Passa pelo envelope da casa.
        response = gui_dialogs.executar_dialogo(
            chooser, nome="importar_perfil_escolher_arquivo"
        )
        filename = chooser.get_filename()
        chooser.destroy()

        if response != Gtk.ResponseType.OK or not filename:
            return

        # PERF-FOOTER-ASYNC-IO-01: o FileChooser tem que rodar na thread GTK, mas
        # ler/validar o arquivo e listar os perfis existentes (p/ checar conflito)
        # é I/O de disco — vai para um worker. A checagem de conflito é feita no
        # disco (não no cache) e o diálogo de conflito decide no callback GTK.
        def _read() -> tuple[Profile, list[Profile]]:
            raw = json.loads(Path(filename).read_text(encoding="utf-8"))
            profile = Profile.model_validate(raw)
            existentes = list(load_all_profiles())
            return profile, existentes

        def _on_read(payload: tuple[Profile, list[Profile]]) -> bool:
            profile, existentes = payload
            # I-1 (06/08/2026): este gate comparava NOME CRU (`nome in
            # existentes`) enquanto os DOIS botões de salvar já perguntam por
            # SLUG (`on_save_profile` e `on_profile_save`) — o importar era o
            # último que ainda comparava outra coisa. Medido: importar um
            # `Navegacao.json` destruía a "Navegação" dela sem uma palavra na
            # tela, porque o arquivo de destino é o mesmo `navegacao.json` e o
            # diálogo de conflito nunca abria. Vale igual para "AÇÃO" → "Ação"
            # e "fps" → "FPS". Quem responde "quem eu apago?" é `find_by_slug`,
            # e o diálogo cita o perfil REALMENTE afetado (`alvo.name`), não o
            # nome que veio no arquivo.
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
                    # E o nome NOVO responde à mesma pergunta: renomear
                    # "Navegacao" para "AÇÃO" cairia em cima de `acao.json`
                    # pela porta dos fundos.
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
        """Grava o perfil importado pelo funil único (GRAVA-POR-UM-FUNIL-01).

        ``adotar_como_ativo=False``: importar um arquivo NÃO é dizer "passei a
        editar este perfil" — as abas continuam com o que estava aberto, e
        roubar o rascunho aqui deixaria a janela mostrando uma configuração e
        o nome de outra.

        O funil ainda reaponta o rascunho quando o arquivo importado é o do
        perfil ATIVO (mesmo slug): nesse caso o disco mudou debaixo dele, e
        manter a fotografia velha reabriria o mesmo defeito por outra porta —
        o "Salvar Perfil" seguinte gravaria ``MatchAny()`` por cima da regra
        que acabou de ser importada.
        """
        self._gravar_perfil_async(
            lambda: profile,
            adotar_como_ativo=False,
            mensagem_ok=lambda perfil, caminho: _(
                "Perfil importado: {nome} -> {caminho}"
            ).format(nome=perfil.name, caminho=caminho),
            mensagem_erro=lambda exc: _("Falha ao importar: {erro}").format(erro=exc),
            evento="footer_import",
        )

    # ------------------------------------------------------------------
    # Handler: Restaurar Default
    # ------------------------------------------------------------------

    def on_restore_default(self, _btn: Any = None) -> None:
        """Restaura meu_perfil ao estado do asset original.

        Confirma com usuário, copia asset -> profiles_dir/meu_perfil.json,
        recarrega DraftConfig e dispara refresh de todas as abas.
        """
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        window = self._get("main_window")

        asset = _meu_perfil_asset()
        if asset is None:
            self._footer_toast(
                _(
                    "Asset 'meu_perfil.json' não encontrado — "
                    "Restaurar Default indisponível."
                )
            )
            logger.warning("footer_restore_default_asset_ausente")
            return

        if not gui_dialogs.confirm_restore_default(parent=window):
            self._footer_toast(_("Restauração cancelada."))
            return

        # PERF-FOOTER-ASYNC-IO-01: a confirmação roda na thread GTK, mas ler o
        # asset, gravar o perfil e recarregar o DraftConfig é I/O de disco — vai
        # para um worker; o resultado é aplicado no callback (GLib.idle_add).
        # GRAVA-POR-UM-FUNIL-01: quem grava é o funil; aqui ficam só as duas
        # partes que são DESTE botão — ler o asset e recarregar o rascunho.
        def _construir() -> Profile:
            raw = json.loads(asset.read_text(encoding="utf-8"))
            return Profile.model_validate(raw)

        def _rascunho_restaurado(profile: Profile) -> Any:
            """Rascunho inteiro relido do disco — roda no WORKER, pós-gravação."""
            try:
                return DraftConfig.from_profile(load_profile(_MEU_PERFIL_NOME))
            except Exception as exc:
                logger.warning("footer_restore_default_draft_falhou", erro=str(exc))
                # O perfil que acabou de ser gravado é a melhor verdade
                # disponível. Devolver ``None`` aqui (o que este caminho fazia)
                # deixava o rascunho com a IDENTIDADE do meu_perfil — o funil
                # já a reaponta — e o CONTEÚDO antigo: o "Salvar Perfil"
                # seguinte desfaria a restauração em silêncio.
                return DraftConfig.from_profile(profile)

        def _aplicar_rascunho(
            _profile: Profile, _caminho: Path, novo_draft: Any
        ) -> None:
            if novo_draft is not None:
                # R-08/C9: draft e NOME trocam como unidade — o nome é
                # responsabilidade do funil (`adotar_como_ativo=True`), o
                # CONTEÚDO é deste botão. Sem os dois, o "Salvar Perfil" ao
                # lado (mesmo rodapé) vinha pré-preenchido com o perfil
                # ANTERIOR e gravava o conteúdo inteiro de meu_perfil por cima
                # dele — destruindo o perfil ativo sem que nada tivesse dito
                # "você trocou de perfil".
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
            mensagem_ok=lambda _perfil, caminho: _(
                "meu_perfil restaurado para {destino}"
            ).format(destino=caminho),
            mensagem_erro=lambda exc: _("Falha ao restaurar: {erro}").format(erro=exc),
            evento="footer_restore_default",
            depois_no_worker=_rascunho_restaurado,
            depois_na_janela=_aplicar_rascunho,
        )

    # ------------------------------------------------------------------
    # Instalação
    # ------------------------------------------------------------------
    # Os handlers do rodapé são registrados pelo builder.connect_signals()
    # em HefestoApp.__init__ (via _signal_handlers), como todos os demais.
    # Havia aqui um `install_footer_actions` que era só `pass` e se dizia
    # "referência canônica e ponto para testes que injetam botões" — nenhum
    # teste o chamava e nenhum call site existia. Um stub vazio que se
    # apresenta como ponto de extensão é pior que nada: quem procura onde
    # ligar um botão novo do rodapé para aqui em vez de ir ao Glade.


# ------------------------------------------------------------------
# Helpers de módulo
# ------------------------------------------------------------------


def _lista_de_secoes(secoes: Any) -> str:
    """Nomes legíveis das seções, curtos o bastante para a statusbar.

    Aceita o mapa ``{seção: motivo}`` do daemon (APLICAR-VERDADE-01) e também
    uma lista crua de nomes. Seção desconhecida (daemon mais novo que a GUI)
    aparece com o nome técnico mesmo — melhor um termo estranho do que omitir
    que algo ficou de fora.
    """
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
    """Alguma seção entrou de fato no controle? (APLICAR-VERDADE-02).

    Lê o ``applied`` do ``profile.apply_draft`` — o ``status`` não serve, é
    fixo em ``"ok"`` por contrato do daemon (a resposta é "recebi", não
    "apliquei"). Resposta SEM ``applied`` (daemon antigo, ou o ``True`` cru do
    bridge) conta como aplicada: sem informação não há do que desconfiar, a
    mesma regra que ``_mensagem_de_aplicacao`` já usa para o texto — as duas
    não podem divergir.
    """
    if not isinstance(result, dict):
        return True
    aplicadas = result.get("applied")
    if not isinstance(aplicadas, list):
        return True
    return bool(aplicadas)


def _secao_aplicada(result: Any, secao: str) -> bool:
    """A seção ``secao`` está no ``applied`` da resposta? (APLICAR-VERDADE-02).

    Mesma regra de ausência de informação de ``_algo_foi_aplicado``: sem
    ``applied`` no payload, assume-se que entrou.
    """
    if not isinstance(result, dict):
        return True
    aplicadas = result.get("applied")
    if not isinstance(aplicadas, list):
        return True
    return secao in aplicadas


def _mensagem_de_aplicacao(result: Any) -> str:
    """Texto do rodapé para uma resposta ACEITA de ``profile.apply_draft``.

    APLICAR-VERDADE-01: o ``status`` da resposta é sempre ``"ok"``, inclusive
    quando nenhuma seção entrou — decidir por ele fazia o rodapé anunciar
    "Perfil aplicado ao controle." depois de nada ter chegado no controle.
    Quem conta a verdade são ``applied`` (o que entrou) e ``failed`` (o que
    não entrou).

    Resposta sem esses campos — daemon antigo, ou o ``True`` cru do bridge —
    mantém a mensagem de sucesso: sem informação não há do que desconfiar.
    """
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
        # BUG-MOUSE-RESTORE-DEFAULT-LIES-01: usa _refresh_mouse_TAB (draft +
        # sync com o estado vivo do daemon), não _refresh_mouse_from_draft — se
        # não, após "Restaurar Default" com a emulação viva (ligada por CLI/
        # applet) a aba mostra toggle OFF enquanto o cursor continua andando.
        "_refresh_mouse_tab",
        # BUG-KEYBOARD-TAB-NO-REFRESH-01: faltava a aba Teclado -> Restaurar
        # Default (e qualquer recarga via _refresh_all_tabs) deixava os bindings
        # stale, podendo reverter o restore ao editar.
        "_refresh_key_bindings_from_draft",
        # BUG-RESTORE-DEFAULT-DEIXA-INICIO-E-EMULACAO-STALE-01: as abas Início e
        # Emulação ficavam de fora desta lista, então após "Restaurar Default"
        # elas só voltavam à verdade quando o poller passasse ou quando a
        # usuária trocasse de aba — até lá, mostravam o modo/máscara antigos.
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
