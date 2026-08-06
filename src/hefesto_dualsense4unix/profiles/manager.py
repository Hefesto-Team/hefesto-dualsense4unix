"""Gerencia perfis em memória e coordena aplicação no controle.

Responsabilidades:
  - Listar, selecionar e aplicar perfis.
  - Atualizar o `StateStore` com o nome do perfil ativo.
  - Aplicar triggers + LEDs no controle quando um perfil é ativado — via a
    API por-uniq do backend (PERFIL-01: broadcast REAL que ignora o seletor
    de alvo da GUI + substituição do mapa de overrides por-controle).

Auto-switch por janela ativa fica em `hefesto_dualsense4unix.profiles.autoswitch` (W6.2).
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from hefesto_dualsense4unix.core.controller import IController, OutputSpec, TriggerEffect
from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS, KeyBinding
from hefesto_dualsense4unix.core.led_control import LedSettings
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.loader import (
    delete_profile,
    load_all_profiles,
    load_profile,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    Profile,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: R-21 (auditoria 24/07): a wm_class que a Steam dá a TODA janela de jogo
#: lançado por ela. Mesma forma reconhecida por `perfil_e_regra_de_jogo`
#: (schema) e por `lifecycle._janela_de_jogo_em_foco` — a doutrina do
#: "catch_all_sem_opiniao" precisa da MESMA noção de "isto é um jogo" nos três
#: lugares, senão a divergência entre os predicados vira o buraco de sempre.
_STEAM_APP_WM_CLASS_RE = re.compile(r"^steam_app_\d+$", re.IGNORECASE)

#: MODO-01 (B3, sprint 25/07): vocabulário do MOTIVO devolvido por
#: `select_for_window_ex`. Até aqui a seleção respondia só `Profile | None`, e o
#: `None` era ambíguo entre duas coisas que pedem reações OPOSTAS:
#:
#:   - `MOTIVO_SEM_CANDIDATO` — nenhum perfil casou com esta janela. Nada a
#:     fazer: o autoswitch retém o perfil corrente, como sempre fez.
#:   - `MOTIVO_JOGO_SEM_PERFIL_PROPRIO` — é uma janela de JOGO e nenhum perfil
#:     ESPECÍFICO opina sobre ela (o veto R-21 abaixo, ou nem candidato houve).
#:     Aqui o silêncio não é "não faça nada": o daemon SABE que há um jogo e
#:     precisa ligar o modo jogo padrão sem trocar de perfil
#:     (`Daemon.aplicar_modo_jogo_padrao`).
#:
#: Era exatamente o buraco medido: a R-21 trocou "o catch-all entra num jogo"
#: por "NINGUÉM entra num jogo" e não pôs nada no lugar — o modo jogo deixou de
#: ligar sozinho para quem não administra um perfil por jogo.
MOTIVO_SELECIONADO = "selecionado"
MOTIVO_SEM_CANDIDATO = "sem_candidato"
MOTIVO_JOGO_SEM_PERFIL_PROPRIO = "jogo_sem_perfil_proprio"

#: SOM-02/E4: a seção não entrou porque a usuária mexeu NAQUELA categoria na mão
#: e a trava (`StateStore.manual_override_categories`) está armada. Vocabulário
#: `ignorado_*` de `daemon.lifecycle`, escrito aqui porque quem o produz é o
#: manager, não o daemon (e importar o lifecycle no topo deste módulo fecharia
#: um ciclo). Era literal solto em `apply_speaker`; virou constante quando a
#: PERFIL-REESCRITO-NA-PARTIDA-01 passou a usá-lo também em `apply`.
IGNORADO_TRAVA_MANUAL = "ignorado_trava_manual"

#: PERFIL-REESCRITO-NA-PARTIDA-01 (leva de 05/08), item 4: as categorias de
#: trava manual que `ProfileManager.apply` de fato SILENCIA — são as que viram
#: `None` no `OutputSpec` logo abaixo. As outras duas categorias existem e são
#: consumidas noutros pontos ("audio" em `apply_speaker`, "rumble" fora da
#: ativação), e reportá-las aqui seria inventar um silêncio que este método não
#: produziu. O relatório só pode afirmar o que este código fez.
_CATEGORIAS_SILENCIADAS_NO_APPLY = frozenset({"trigger", "led"})


@dataclass
class ProfileManager:
    controller: IController
    store: StateStore = field(default_factory=StateStore)
    # FEAT-KEYBOARD-PERSISTENCE-01: referência opcional ao device virtual.
    # Quando presente, `activate()` propaga o `key_bindings` resolvido para
    # o device. Typing "Any" para evitar ciclo de import com integrations.
    keyboard_device: object | None = None
    # FEAT-POINT-AND-CLICK-01 (fix A-06/A8): provider LAZY do device de teclado.
    # O manager é criado no boot ANTES de o keyboard subir (lifecycle sobe
    # IPC/autoswitch primeiro) e o device é anulado/recriado em disconnect e
    # reload — capturar a referência eager congela `None` para sempre. Os
    # callsites injetam `lambda: getattr(daemon, "_keyboard_device", None)`;
    # `apply_keyboard` resolve o provider a cada ativação. Quando presente,
    # tem precedência sobre `keyboard_device` (mantido para backcompat).
    keyboard_device_provider: Callable[[], object | None] | None = None
    # FEAT-POINT-AND-CLICK-01: applier da seção `mouse` do perfil. Os callsites
    # injetam `daemon.set_mouse_emulation` (retorna bool — por isso o retorno é
    # `object`, não `None`). Assinatura: (enabled, speed, scroll_speed) mais o
    # `origin=` por keyword (R-03: o applier precisa saber se a ativação é gesto
    # manual dela — que fura o lock — ou automática). `Callable[..., object]`
    # pelo mesmo motivo dos outros: a assinatura tem keyword-only.
    # None = seção mouse do perfil é ignorada (CLI/testes sem daemon).
    mouse_applier: Callable[..., object] | None = None
    # FEAT-POINT-AND-CLICK-01: applier da supressão de emulação (modo-jogo)
    # por perfil. Os callsites injetam `daemon.apply_profile_suppression`, que
    # concentra a política (origem perfil vs. toggle manual + lock de 30s).
    # Recebe `profile.suppress_desktop_emulation` a cada ativação, mais o
    # `profile=` por keyword (R-02: o applier precisa saber se quem mandou tem
    # opinião ou é um catch-all).
    suppression_applier: Callable[..., object] | None = None
    # FEAT-PROFILE-MODE-01: applier da seção `mode` do perfil (nativo/gamepad/
    # desktop + co-op). Os callsites injetam `daemon.apply_profile_mode` —
    # recebe `profile.mode` (inclusive None: perfil sem opinião reverte só modo
    # ligado por OUTRO perfil) mais o `profile=` por keyword (R-02).
    # None = seção ignorada (CLI/testes sem daemon).
    mode_applier: Callable[..., object] | None = None
    # FEAT-RUMBLE-POLICY-PROFILE-01: applier da política de rumble do perfil
    # (seção `rumble.policy`/`rumble.custom_mult`). Os callsites injetam
    # `daemon.apply_profile_rumble_policy` — recebe (policy, custom_mult) a
    # cada ativação, inclusive (None, None) para perfil sem opinião (reverte
    # só política aplicada por OUTRO perfil; política manual fica), mais o
    # `origin=` por keyword (R-03). None = seção ignorada (CLI/testes sem
    # daemon).
    # PERFIL-REESCRITO-NA-PARTIDA-01 (05/08): e o `profile=` por keyword, como
    # `suppression_applier`/`mode_applier` — é o que permite ao applier recusar
    # a reversão pedida por um catch-all (R-02), a guarda que faltava só neste.
    rumble_policy_applier: Callable[..., object] | None = None
    # SPRINT-GAME-RUMBLE-01: applier da seção `rumble.passthrough` do perfil.
    # Os callsites injetam `daemon.apply_profile_rumble_passthrough` — recebe o
    # bool a cada ativação. passthrough=True (default de TODO perfil) solta o
    # rumble FIXADO pela GUI (rumble_active=None), devolvendo a vibração ao JOGO;
    # sem isto, testar os motores na GUI ("Aplicar"/"Parar") deixava o rumble
    # travado e o FF do jogo era ignorado mesmo com a máscara certa. None =
    # seção ignorada (CLI/testes sem daemon).
    rumble_passthrough_applier: Callable[[bool], None] | None = None
    # SOM-02/E4: applier da seção `speaker` do perfil (volume do alto-falante
    # e do fone do controle). Assinatura: `(volume: int, muted: bool, *,
    # uniq: str | None = None, origin: str)` — o par SEMPRE explícito, nunca
    # um `speaker.set` sem `volume` (armadilha 1 da sprint: chamada sem
    # volume toma a posse e manda ZERO).
    #
    # DIFERENÇA deliberada em relação a `mode_applier`/`rumble_policy_applier`,
    # que recebem SEMPRE a seção (inclusive None, para reverter o que outro
    # perfil ligou): aqui perfil sem a seção NÃO chama o applier. Reverter
    # áudio custaria tomar a posse dos bytes de volume por um perfil que não
    # pediu nada — o hábito que produziu "a config que eu deixo nunca é
    # respeitada". Sem opinião é silêncio, não ordem.
    #
    # None = seção ignorada (CLI/testes sem daemon).
    speaker_applier: Callable[..., object] | None = None
    # R-21: última `wm_class` de jogo cujo veto ao catch-all já foi logado. O
    # `select_for_window` roda a 2 Hz (poll do autoswitch): sem esta chave o
    # veto viraria ~7 mil linhas/hora no journal enquanto ela joga.
    _ultimo_veto_catch_all: str | None = field(default=None, repr=False)
    # EMPATE-01 (sprint 27/07): último empate já registrado no journal, como
    # `(wm_class, nome do vencedor)`. Mesma razão do `_ultimo_veto_catch_all`
    # acima: a seleção roda a 2 Hz e o empate medido no disco dela é
    # PERMANENTE (três catch-all em prioridade 0), então logar sem dedup
    # viraria ~7 mil linhas por hora no journal enquanto ela joga.
    _ultimo_empate_logado: tuple[str, str] | None = field(default=None, repr=False)

    def list_profiles(self) -> list[Profile]:
        return load_all_profiles()

    def get(self, name: str) -> Profile:
        return load_profile(name)

    def create(self, profile: Profile) -> None:
        save_profile(profile)
        logger.info("profile_created", name=profile.name)

    def delete(self, name: str) -> None:
        delete_profile(name)
        active = self.store.active_profile
        # BUG-PROFILE-DELETE-ACTIVE-SLUG-01: `activate()` grava o DISPLAY NAME em
        # `active_profile`, mas `delete()` aceita slug OU display name. Comparar
        # as strings cruas deixava o active "preso" quando o delete vinha por
        # slug (ex.: active="Ação", name="acao" — slugs iguais, strings não).  # (noqa-acento)
        # Normalizamos AMBOS via slugify antes de comparar.
        if active is not None and self._refers_same_profile(active, name):
            self.store.set_active_profile(None)
        logger.info("profile_deleted", name=name)

    @staticmethod
    def _refers_same_profile(active: str, name: str) -> bool:
        """True se `active` e `name` apontam para o mesmo perfil (compara slugs).

        O arquivo já foi removido por `delete_profile`, então NÃO dependemos do
        disco: `slugify` roda sobre as strings em memória. Tolera nomes exóticos
        que não produzem slug (ValueError) caindo na comparação literal — assim
        um active sem slug ainda é limpo quando o delete vem com a mesma string.
        """
        from hefesto_dualsense4unix.profiles.slug import slugify

        try:
            return slugify(active) == slugify(name)
        except ValueError:
            return active == name

    def activate(
        self,
        name: str,
        *,
        origin: str = "manual",
        relatorio: dict[str, str] | None = None,
    ) -> Profile:
        """Carrega, aplica triggers + LEDs + teclado + emulação e marca como ativo.

        PERFIL-03 (autoload): `origin` separa o GESTO MANUAL da usuária das
        ativações automáticas — o bug provado do sprint era o autoswitch
        reescrever `session.json` a cada troca de janela, e o boot restaurar
        "Navegação" em vez da escolha dela. Valores:

          - ``"manual"`` (default) — profile.switch via IPC (GUI/CLI) e o
            ciclo por hotkey (PS+D-pad): É a intenção da usuária → persiste
            em `session.json` (`save_last_profile`).
          - ``"autoswitch"`` — troca automática por janela em foco: aplica e
            marca ativo, mas NÃO grava a intenção manual.
          - ``"system"`` — restore de boot e saída do Modo Nativo: idem, o
            sistema re-aplicando estado não é escolha nova.

        O default "manual" é deliberado: um caller novo que esqueça o
        parâmetro preserva o comportamento histórico (gravar), nunca
        silencia um gesto real da usuária. NÃO confundir com o `origin`
        do latch de `start_gamepad_emulation` ("manual"/"profile") — são
        contratos distintos.

        R-03 (auditoria 23/07): o `origin` também SEGUE até os appliers de
        emulação — é lá que ele decide se o lock de gesto manual (30 s) é
        furado (ativação manual dela) ou vira pendência de retry (autoswitch).
        `relatorio`, quando passado, é preenchido com `seção → estado`
        (`"aplicado"`, `"adiado_lock_manual"`, `"ignorado_*"`, `"falhou"`) para
        quem precisa contar a verdade — hoje o `profile.switch` do IPC. É um
        out-param em vez de estado no manager de propósito: sem ele, o
        resultado de uma ativação disparada pela hotkey (thread do executor)
        poderia ser lido como se fosse o de outra.
        """
        profile = load_profile(name)
        # PERFIL-REESCRITO-NA-PARTIDA-01, item 4: o `relatorio` desce até o
        # `apply` para as categorias travadas na mão entrarem nele — ver lá.
        self.apply(profile, origin=origin, relatorio=relatorio)
        self.apply_keyboard(profile)
        self.apply_emulation(profile, origin=origin, relatorio=relatorio)
        self.store.set_active_profile(profile.name)
        self.store.bump("profile.activated")
        logger.info(
            "profile_activated",
            name=profile.name,
            priority=profile.priority,
            origin=origin,
        )
        if origin == "manual":
            from hefesto_dualsense4unix.utils.session import save_last_profile
            save_last_profile(profile.name)
        # FEAT-COSMIC-NOTIFICATIONS-01: opt-in via env var
        # `HEFESTO_DUALSENSE4UNIX_DESKTOP_NOTIFICATIONS=1`. Sem isso, no-op.
        try:
            from hefesto_dualsense4unix.integrations.desktop_notifications import (
                notify_profile_activated,
            )
            notify_profile_activated(profile.name)
        except Exception:
            pass
        return profile

    def apply(
        self,
        profile: Profile,
        *,
        origin: str = "auto",
        relatorio: dict[str, str] | None = None,
    ) -> None:
        """Aplica triggers e LEDs do perfil em TODOS os controles (sem marcar ativo).

        PERFIL-01 (4P-01): a seção global vai por `apply_output_defaults` —
        broadcast REAL que IGNORA o seletor de alvo da GUI. Os setters
        clássicos respeitam o seletor, então ativar um perfil com um alvo
        selecionado (manual OU via autoswitch, que passa pela MESMA cadeia
        `activate()` → `apply()`) atingia SÓ o alvo — bug provado do sprint.
        O brilho passa pelo MESMO caminho de escala do histórico
        (`LedSettings.apply_brightness`, paridade com `apply_led_settings`).

        Na sequência, a ativação republica a CAMADA DO PERFIL no mapa de
        overrides por-controle (`reset_profile_overrides`): nada do perfil
        anterior ressuscita num replug sob o perfil novo. PERFIL-04: as
        entradas de `profile.controllers` (mapa por-MAC no JSON) entram na
        camada — controle conectado recebe na hora, desconectado fica
        REGISTRADO no mapa em memória do backend (o hotplug o aplica quando
        ele chegar; é o teste de fogo do PERFIL-05c). O brilho do override
        escala pelo MESMO caminho da seção global.

        R-20 (auditoria 23/07) — por que CAMADA e não substituição do mapa:
        `reset_output_overrides` trocava o mapa por-uniq INTEIRO, e o
        autoswitch ativa perfil a CADA troca de janela. Resultado medido no
        achado C5: o ajuste por-controle que ela acabava de fazer na GUI era
        apagado segundos depois — "as configs que eu faço não impactam
        controle a controle". Agora a ativação substitui só o que é do perfil
        e cede o campo que a usuária ajustou na mão.

        O `origin` é o botão de soltar dessa precedência: ativação MANUAL
        (ela escolhendo o perfil na GUI/CLI) é gesto mais novo que o slider
        que ela arrastou antes, então limpa a camada da usuária; ativação
        automática (autoswitch, restore de boot) nunca limpa — é dela que a
        camada precisa se defender. Default `"auto"` de propósito: caller
        novo que esqueça o parâmetro PRESERVA o ajuste dela (o erro seguro).

        Backends sem a API de camadas (FakeController e dublês de teste) caem
        no caminho histórico (`reset_output_overrides` + `apply_output_for`),
        que continua correto para quem não tem estado por-controle.

        COR-03: a ativação também configura o estado do AUTOMÁTICO (cores por
        controle) no registro de identidade — `enabled` vem de
        `profile.leds.auto_player_colors` (perfil sem seção `leds` no JSON
        valida com `LedsConfig()` → auto ON, o default do campo) e o brilho
        vigente de `profile.leds.lightbar_brightness` (a cor automática é
        escalada pelo MESMO brilho do global — D11). O provider injetado no
        backend consulta esse estado a cada resolução; a escrita física dos
        conectados acontece pelos broadcasts/reasserts desta mesma ativação.

        Mic-LED fica de fora por decisão deliberada
        (AUDIT-FINDING-PROFILE-MIC-LED-RESET-01): jamais colateral de
        profile switch.
        """
        # PERFIL-MANUAL-VENCE-01 (pedido da mantenedora, 23/07: "o sackboy
        # deveria ser trava manual também").
        #
        # Até aqui, o perfil do JOGO limpava as três categorias de override
        # manual e reescrevia tudo. Isso está certo para o MODO (ela precisa do
        # gamepad+co-op para jogar Sackboy a 4) e ERRADO para a aparência: a
        # cor/gatilho/rumble que ela acabou de ajustar sumia ao abrir o jogo —
        # a queixa "a config que eu deixo nunca é respeitada".
        #
        # Os eixos são independentes e passam a ser tratados assim: o `mode`
        # continua aplicando sempre (é o que faz o jogo funcionar); as seções
        # que ela travou NA MÃO sobrevivem à ativação.
        #
        # Categoria travada = ela mexeu e o daemon carimbou
        # (`mark_manual_trigger_active`). Trocar de perfil pela GUI limpa as
        # TRÊS categorias — então isso NÃO é um estado do qual ela não consiga
        # sair. ABAS-05 (25/07): o `trigger.reset` (botão "Desligar" da aba
        # Gatilhos) também solta, mas SÓ a categoria "trigger"; antes soltava
        # as três, e desligar um gatilho reabria a troca automática para
        # reescrever a cor que a aba Lightbar tinha acabado de aplicar.
        # R-20: gesto MANUAL de trocar de perfil solta a camada por-controle
        # da usuária (ver a docstring). É o único caminho que a solta, e é o
        # que impede a precedência "manual vence perfil" de virar estado preso.
        if origin == "manual":
            soltar = getattr(self.controller, "clear_user_output_overrides", None)
            if callable(soltar):
                soltar()

        travadas = self._categorias_travadas()
        if travadas:
            logger.info(
                "profile_apply_respeita_override_manual",
                profile=profile.name,
                categorias=sorted(travadas),
            )
            # PERFIL-REESCRITO-NA-PARTIDA-01, item 4: o que a trava silencia
            # entra no RELATÓRIO, e não só no journal. Este método já sabia
            # quais categorias iria pular — emitia `None` no `OutputSpec` e
            # seguia — e nada disso chegava a quem pergunta pelo resultado da
            # ativação: o `profile.switch` respondia "ativado" e a janela não
            # tinha como dizer à usuária que o gatilho/a cor do perfil não
            # entraram porque o ajuste de mão dela venceu. Mesmo vocabulário
            # que o `apply_speaker` já usava para a categoria "audio", agora
            # numa constante só.
            if relatorio is not None:
                for categoria in travadas & _CATEGORIAS_SILENCIADAS_NO_APPLY:
                    relatorio[categoria] = IGNORADO_TRAVA_MANUAL

        left = build_from_name(profile.triggers.left.mode, profile.triggers.left.params)
        right = build_from_name(profile.triggers.right.mode, profile.triggers.right.params)
        settings = _to_led_settings(profile.leds)
        effective = settings.apply_brightness(settings.brightness_level)
        self._configure_auto_player_colors(profile)
        # `None` num campo do OutputSpec = "não mexe nele" (o backend resolve
        # por camadas). É assim que a seção travada atravessa a ativação.
        self.controller.apply_output_defaults(
            OutputSpec(
                trigger_left=None if "trigger" in travadas else left,
                trigger_right=None if "trigger" in travadas else right,
                led=None if "led" in travadas else effective.lightbar,
                player_leds=None if "led" in travadas else settings.player_leds,
            )
        )
        overrides = _controllers_to_specs(profile.controllers, profile.leds)
        # R-20 item 2: o brilho por-controle vira ESCALA (aplicada depois do
        # merge), nunca cor materializada — publicado ANTES da camada para o
        # reassert do fim já convergir com ele.
        escalas = _controllers_to_led_scales(profile.controllers, profile.leds)
        escalar = getattr(self.controller, "set_led_scales", None)
        if callable(escalar):
            escalar(escalas or None)
        publicar = getattr(self.controller, "reset_profile_overrides", None)
        if callable(publicar):
            publicar(overrides or None)
        else:
            # Caminho histórico (backend sem camadas): substitui o mapa e
            # escreve um a um. Correto para quem não tem estado por-controle.
            self.controller.reset_output_overrides(overrides or None)
            for uniq, spec in overrides.items():
                self.controller.apply_output_for(uniq, spec)
        # COR-03 (fix de integração, 2026-07-17): o broadcast acima escreve o
        # GLOBAL nos conectados — sem este reassert, a paleta automática só
        # apareceria no próximo replug (boot com controles presentes ficava
        # com a cor global; visto AO VIVO na validação pós-install). Converge
        # o estado físico ao RESOLVIDO por-controle (explícita > auto >
        # global). Getattr defensivo: backends sem o método (fakes) seguem.
        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()

    def _categorias_travadas(self) -> frozenset[str]:
        """Categorias de override MANUAL armadas no store agora.

        ONDA-U F1/F2: "trigger" | "led" | "rumble" — e "audio" desde a SOM-02,
        que é a categoria que o alto-falante consome. Lido por `getattr` de
        propósito: dublês de teste e o `ProfileManager` sem store continuam
        funcionando, e o conjunto vazio significa "nada travado".
        """
        store = getattr(self, "store", None)
        if store is None:
            return frozenset()
        return frozenset(getattr(store, "manual_override_categories", ()) or ())

    @staticmethod
    def _configure_auto_player_colors(profile: Profile) -> None:
        """Propaga o toggle/brilho do automático ao registro de identidade (COR-03).

        Import lazy do singleton (`get_identity_registry`) de propósito: o
        `ProfileManager` é instanciado em ≥3 lugares (restore de boot,
        hotkey, IPC) e todos precisam configurar o MESMO estado que o
        provider do backend consulta — sem parâmetro novo em cada callsite.
        Best-effort (falha loga debug, não aborta a ativação): CLI/testes
        sem daemon configuram um singleton que ninguém consulta — inócuo e
        sem I/O (`configure` só toca memória).
        """
        try:
            from hefesto_dualsense4unix.daemon.subsystems.identity import (
                get_identity_registry,
            )

            get_identity_registry().configure(
                enabled=bool(profile.leds.auto_player_colors),
                brightness=float(profile.leds.lightbar_brightness),
            )
        except Exception as exc:
            logger.debug("auto_player_colors_configure_falhou", err=str(exc))

    def apply_keyboard(self, profile: Profile) -> None:
        """Propaga `key_bindings` do perfil ao device virtual de teclado (A-06).

        No-op quando não há device (CLI, testes sem daemon) ou o device não
        está ativo. Spec opção (c): método público para que a chamada fique
        explícita nos pontos que têm acesso ao device.

        FEAT-POINT-AND-CLICK-01 (A8): quando `keyboard_device_provider` existe,
        ele é resolvido AQUI, a cada ativação — imune ao boot fora de ordem
        (IPC/autoswitch sobem antes do keyboard) e ao device anulado/recriado
        em disconnect/reload.
        """
        provider = self.keyboard_device_provider
        device = provider() if provider is not None else self.keyboard_device
        if device is None:
            return
        resolved = _to_key_bindings(profile)
        try:
            device.set_bindings(resolved)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.warning(
                "keyboard_device_apply_failed",
                profile=profile.name,
                err=str(exc),
            )

    def apply_emulation(
        self,
        profile: Profile,
        *,
        origin: str = "manual",
        relatorio: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Aplica a seção `mouse` e a supressão de modo-jogo do perfil.

        FEAT-POINT-AND-CLICK-01. Best-effort (falha loga warning, não aborta a
        ativação — paridade com `apply_keyboard`):

        - `profile.mouse` presente + `mouse_applier` injetado → liga/desliga a
          emulação de mouse com as velocidades do perfil. `mouse=None` NÃO toca
          no estado (comportamento v1 preservado).
        - `suppression_applier` injetado → recebe SEMPRE o valor de
          `suppress_desktop_emulation` (inclusive o default False, para que
          trocar para um perfil sem o campo LIBERE a supressão ligada por outro
          perfil). A política de "não reverter toggle manual" mora no applier
          (`Daemon.apply_profile_suppression`).

        R-03 (auditoria 23/07): `origin` (a origem da ATIVAÇÃO — "manual",
        "autoswitch", "system") vai junto a cada applier, e o retorno de cada um
        é registrado em `relatorio` como `seção → estado`. Sem esse relatório, a
        seção que o lock de gesto manual descartava sumia sem rastro: a ativação
        era commitada, o IPC respondia sucesso e a GUI mostrava o perfil ativo
        com a máscara errada. Devolve o relatório (o mesmo dict, quando passado).

        Applier de dublê que devolve `None` conta como "aplicado" — só o daemon
        real sabe adiar, e um dublê nunca deve fabricar um adiamento.

        SOM-02/E4: a seção `speaker` fecha a lista, com contrato PRÓPRIO —
        perfil sem ela não chama applier nenhum (ver `apply_speaker`).
        """
        resultado: dict[str, str] = relatorio if relatorio is not None else {}
        if self.mouse_applier is not None and profile.mouse is not None:
            try:
                resultado["mouse"] = _estado_da_secao(
                    self.mouse_applier(
                        profile.mouse.enabled,
                        profile.mouse.speed,
                        profile.mouse.scroll_speed,
                        origin=origin,
                    )
                )
            except Exception as exc:
                resultado["mouse"] = "falhou"
                logger.warning(
                    "profile_mouse_apply_failed",
                    profile=profile.name,
                    err=str(exc),
                )
        if self.suppression_applier is not None:
            try:
                # R-02: o applier precisa saber SE o perfil tem opinião — um
                # catch-all liberando a supressão de desktop dentro do jogo é
                # ausência de regra sendo executada como ordem.
                resultado["suppression"] = _estado_da_secao(
                    self.suppression_applier(
                        profile.suppress_desktop_emulation,
                        profile=profile,
                        origin=origin,
                    )
                )
            except Exception as exc:
                resultado["suppression"] = "falhou"
                logger.warning(
                    "profile_suppression_apply_failed",
                    profile=profile.name,
                    err=str(exc),
                )
        # FEAT-PROFILE-MODE-01: o applier recebe SEMPRE a seção (inclusive
        # None) — é assim que trocar para um perfil sem opinião REVERTE o modo
        # ligado por outro perfil, respeitando gesto manual (política no
        # `Daemon.apply_profile_mode`). Ordem: por último, para que "sair do
        # nativo" não re-aplique nada por cima dos triggers/LEDs já aplicados.
        if self.mode_applier is not None:
            try:
                # R-02: junto com a seção vai QUEM a mandou. Sem isso o applier
                # não distingue "o perfil do jogo mandou voltar ao desktop" de
                # "caiu num catch-all porque este jogo não tem perfil" — e a
                # segunda hipótese desligava o vpad no meio da partida.
                resultado["mode"] = _estado_da_secao(
                    self.mode_applier(
                        getattr(profile, "mode", None),
                        profile=profile,
                        origin=origin,
                    )
                )
            except Exception as exc:
                resultado["mode"] = "falhou"
                logger.warning(
                    "profile_mode_apply_failed",
                    profile=profile.name,
                    err=str(exc),
                )
        # FEAT-RUMBLE-POLICY-PROFILE-01: idem `mode` — o applier recebe SEMPRE
        # o par (policy, custom_mult), inclusive (None, None), para que trocar
        # para um perfil sem opinião REVERTA a política aplicada por outro
        # perfil. A política de reversão/lock manual mora no applier
        # (`Daemon.apply_profile_rumble_policy`).
        if self.rumble_policy_applier is not None:
            rumble_cfg = getattr(profile, "rumble", None)
            try:
                # PERFIL-REESCRITO-NA-PARTIDA-01 (leva de 05/08), item 3: junto
                # com o par vai QUEM mandou, como já ia para `suppression` e
                # `mode` (R-02). Sem isso o applier não conseguia distinguir "o
                # perfil deste jogo não quer política" de "caiu num catch-all
                # porque nenhuma regra casou" — e a segunda hipótese revertia a
                # política de rumble DENTRO da partida dela.
                resultado["rumble_policy"] = _estado_da_secao(
                    self.rumble_policy_applier(
                        getattr(rumble_cfg, "policy", None),
                        getattr(rumble_cfg, "custom_mult", None),
                        profile=profile,
                        origin=origin,
                    )
                )
            except Exception as exc:
                resultado["rumble_policy"] = "falhou"
                logger.warning(
                    "profile_rumble_policy_apply_failed",
                    profile=profile.name,
                    err=str(exc),
                )
        # SPRINT-GAME-RUMBLE-01: aplica o `rumble.passthrough` do perfil — solta
        # o rumble FIXADO pela GUI para o JOGO controlar a vibração. SEMPRE (o
        # default True cobre todo perfil); o applier só age se há rumble fixado.
        if self.rumble_passthrough_applier is not None:
            rumble_cfg = getattr(profile, "rumble", None)
            try:
                self.rumble_passthrough_applier(
                    bool(getattr(rumble_cfg, "passthrough", True))
                )
            except Exception as exc:
                logger.warning(
                    "profile_rumble_passthrough_apply_failed",
                    profile=profile.name,
                    err=str(exc),
                )
        # SOM-02/E4: o alto-falante entra POR ÚLTIMO e só quando o perfil tem
        # opinião — ver `apply_speaker`.
        self.apply_speaker(profile, origin=origin, relatorio=resultado)
        return resultado

    def apply_speaker(
        self,
        profile: Profile,
        *,
        origin: str = "manual",
        uniq: str | None = None,
        relatorio: dict[str, str] | None = None,
    ) -> str | None:
        """Aplica a seção `speaker` do perfil (SOM-02/E4). Devolve o estado.

        As TRÊS guardas desta entrega, cada uma vinda de uma medição da sprint:

        1. **perfil sem a seção não escreve NADA.** `speaker=None` é ausência
           de opinião, e o applier nem é chamado — diferente do `mode` e da
           política de rumble, que recebem `None` para reverter o que outro
           perfil ligou. Aqui "reverter" custaria tomar a posse dos bytes de
           volume: a primeira escrita nossa faz o hefesto mandar o volume do
           alto-falante E do fone em todo report, e o DualSense não devolve o
           valor que o firmware tinha. Um perfil que não pediu nada não pode
           pagar esse preço (é a queixa "a config que eu deixo nunca é
           respeitada", do lado do áudio).
        2. **a trava manual de áudio vence o perfil.** Categoria `"audio"` do
           `StateStore` (irmã de "trigger"/"led"/"rumble"): se ela acabou de
           mexer no volume na mão, o autoswitch reaplicando o perfil a cada
           troca de janela NÃO pisa o ajuste dela — a mesma disciplina do
           PERFIL-MANUAL-VENCE-01, que trata cor e gatilho assim. Trocar de
           perfil explicitamente limpa as categorias e solta a trava.
        3. **o par vai SEMPRE completo.** `volume` e `muted` juntos, nunca um
           `speaker.set` sem volume — medido: sem volume e sem preferência
           guardada a chamada toma a posse e manda ZERO, publicando
           `{'volume': 0, 'muted': True}`. O esquema já recusa a seção sem
           `volume` (ver `ProfileSpeakerConfig`); aqui o `int(...)` explícito
           é a segunda cerca, para um dublê ou um objeto parcial não
           conseguirem produzir a chamada vazia.

        Best-effort como os irmãos: falha do applier loga warning e não aborta
        a ativação. `relatorio` recebe `"speaker" → estado` para a GUI poder
        contar a verdade (inclusive `"ignorado_trava_manual"`, que sem o
        registro sumiria sem rastro — o buraco que o R-03 fechou).
        """
        resultado: dict[str, str] = relatorio if relatorio is not None else {}
        secao = getattr(profile, "speaker", None)
        if self.speaker_applier is None or secao is None:
            return None
        if "audio" in self._categorias_travadas():
            resultado["speaker"] = IGNORADO_TRAVA_MANUAL
            logger.info(
                "profile_speaker_ignorado_trava_manual",
                profile=profile.name,
                origin=origin,
            )
            return resultado["speaker"]
        try:
            estado = _estado_da_secao(
                self.speaker_applier(
                    int(secao.volume),
                    bool(secao.muted),
                    uniq=uniq,
                    origin=origin,
                )
            )
        except Exception as exc:
            estado = "falhou"
            logger.warning(
                "profile_speaker_apply_failed",
                profile=profile.name,
                err=str(exc),
            )
        resultado["speaker"] = estado
        return estado

    def reapply_speaker_on_connect(self, uniq: str | None = None) -> str | None:
        """Reaplica o volume do perfil ATIVO quando um controle (re)conecta.

        SOM-02/E4, item 3 das medições da sprint — a armadilha 4: a posse dos
        bytes de áudio morre com o cabo. `_volumes_audio` nasce vazio em cada
        handle e CADA conexão cria um handle novo, então desconectar e
        reconectar (ou reiniciar o daemon) apaga a posse e o volume: a chave
        `speaker` some do estado e o rótulo volta a "não ajustado". Persistir
        por perfil sem este gancho faria o volume voltar ao do firmware ao
        trocar o cabo, em silêncio.

        **Só reaplica quando o perfil ativo TEM a seção** — sem isso
        voltaríamos a tomar posse sem pedido a cada replug, que é o defeito
        que a E4 inteira existe para não cometer. Sem perfil ativo, sem seção
        ou sem applier: devolve `None` e não escreve nada. Com a trava manual
        de áudio armada devolve `"ignorado_trava_manual"` (e também não
        escreve): se ela mexeu no volume na mão, quem manda é ela — a
        reconexão não é ocasião para o perfil retomar o campo.

        `origin="system"` de propósito: reconexão é o sistema reaplicando o
        que já estava configurado, nunca um gesto novo dela (mesma leitura do
        restore de boot).
        """
        nome = getattr(getattr(self, "store", None), "active_profile", None)
        if not nome:
            return None
        try:
            profile = load_profile(str(nome))
        except Exception as exc:
            logger.warning(
                "profile_speaker_reapply_load_failed", name=str(nome), err=str(exc)
            )
            return None
        if getattr(profile, "speaker", None) is None:
            return None
        return self.apply_speaker(profile, origin="system", uniq=uniq)

    def select_for_window(self, window_info: dict[str, object]) -> Profile | None:
        """Escolhe o perfil MAIS ESPECÍFICO que case com a janela.

        Se nenhum perfil casa (inclusive fallback), retorna None. Chamado pelo
        autoswitch em W6.2.

        MODO-01 (B3): a assinatura histórica é PRESERVADA — quem só precisa do
        perfil (o `_profile_rule_matches_game` do lifecycle, a CLI, os dublês de
        teste) continua chamando isto. Quem precisa saber POR QUE a resposta foi
        `None` usa `select_for_window_ex`, que carrega o motivo junto.
        """
        profile, _motivo = self.select_for_window_ex(window_info)
        return profile

    def select_for_window_ex(
        self, window_info: dict[str, object]
    ) -> tuple[Profile | None, str]:
        """Como `select_for_window`, mas devolve `(perfil, motivo)`.

        O motivo é um dos `MOTIVO_*` do topo do módulo. É a metade que faltava
        da R-21 (MODO-01/B3): sem ele, o autoswitch não tinha como distinguir
        "nada casou com esta janela de desktop" de "é um JOGO e ninguém opina
        sobre ele" — e a segunda é a única em que existe algo a fazer sem trocar
        de perfil (ligar o modo jogo padrão).

        R-01 (auditoria 23/07): a ordenação era só por `priority`, e por isso um
        perfil catch-all podia vencer a regra própria do jogo. É o caso medido
        no disco da usuária: `vitoria` (MatchAny, prio 5) vencia qualquer perfil
        de jogo recém-criado, que nasce com prioridade 0 — ou seja, criar o
        perfil do jogo pela GUI **não resolvia** o problema que ela tentava
        resolver.

        Agora **especificidade vem antes de prioridade**: qualquer perfil que
        casou por critério real vence qualquer catch-all. Entre perfis de mesma
        especificidade a prioridade continua decidindo, o que preserva o tuning
        50-80 dos presets (Navegação 50 < FPS 60 < Aventura 70 < Sackboy 80).

        Deliberadamente NÃO se introduz uma escada `window_class > regex`: isso
        reordenaria perfis de critério hoje empatados e mudaria comportamento já
        validado. A distinção fina entre "casou por regex solto" e "é a regra do
        jogo" mora em `perfil_e_regra_de_jogo`, usada por quem precisa dela.

        R-21 (auditoria 24/07): o R-01 acertou a ORDEM mas não a AUTORIDADE. Com
        a janela de um jogo em foco e nenhuma regra específica para ele (o caso
        medido: Mullet Mad Jack, `steam_app_2111190`, sem perfil próprio), a
        ordenação continuava elegendo o melhor dos catch-all — o `vitoria`
        (MatchAny, prio 5). Basta alternar para a janela `steam` (que casa
        `Navegação`, prio 50) e voltar para ter o ping-pong do journal de
        22-23/07, com lightbar/gatilhos/rumble diferentes a cada 18-28 s.

        Um genérico de DESKTOP não tem autoridade sobre uma janela de JOGO:
        quando a `wm_class` em foco é `steam_app_<id>` e os ÚNICOS candidatos são
        catch-all, a resposta honesta é None ("nenhum perfil opina sobre este
        jogo") — e o autoswitch retém o perfil corrente em vez de trocar. É
        exatamente a doutrina do `catch_all_sem_opiniao` de
        `lifecycle.apply_profile_suppression`, aplicada um nível acima: lá o
        catch-all não pode REVERTER a supressão; aqui ele não pode ENTRAR.

        MODO-01 (B3): o veto CONTINUA valendo — ele tinha razão própria e não é
        revogado aqui. O que muda é que ele deixou de ser mudo: em vez de um
        `None` indistinguível de "nada casou", devolve
        `MOTIVO_JOGO_SEM_PERFIL_PROPRIO`, e é o chamador que decide o que fazer
        com a informação (ligar o modo jogo padrão, sem trocar de perfil).
        Também cobre o caso vizinho que o veto nunca alcançou: janela de jogo com
        ZERO candidatos (nem catch-all no disco) é o mesmo silêncio, pelo mesmo
        motivo.
        """
        candidates = [p for p in load_all_profiles() if p.matches(dict(window_info))]
        wm_class = str(window_info.get("wm_class") or "")
        e_janela_de_jogo = bool(_STEAM_APP_WM_CLASS_RE.match(wm_class))
        if not candidates:
            if e_janela_de_jogo:
                return None, MOTIVO_JOGO_SEM_PERFIL_PROPRIO
            return None, MOTIVO_SEM_CANDIDATO
        if e_janela_de_jogo and all(p.e_catch_all for p in candidates):
            if self._ultimo_veto_catch_all != wm_class:
                self._ultimo_veto_catch_all = wm_class
                logger.info(
                    "profile_select_catch_all_sem_autoridade_em_jogo",
                    wm_class=wm_class,
                    candidatos=sorted(p.name for p in candidates),
                )
            return None, MOTIVO_JOGO_SEM_PERFIL_PROPRIO
        self._ultimo_veto_catch_all = None
        return self._melhor_candidato(candidates, wm_class), MOTIVO_SELECIONADO

    @staticmethod
    def _chave_de_selecao(profile: Profile) -> tuple[bool, int]:
        """Chave HISTÓRICA da escolha: especificidade e, só depois, prioridade.

        Preservada exatamente como era (R-01): `not e_catch_all` primeiro, para
        que qualquer regra real vença qualquer catch-all, e a prioridade em
        seguida. Maior tupla vence.
        """
        return (not profile.e_catch_all, profile.priority)

    def _nome_do_incumbente(self) -> str | None:
        """Nome do perfil que JÁ ESTÁ ATIVO, ou None quando não há.

        EMPATE-01: a fonte é o `StateStore` — o mesmo objeto que
        `activate()` escreve. Não se consulta `session.json` de propósito: ele
        guarda a última escolha MANUAL dela, que não é necessariamente o perfil
        vigente, e lê-lo aqui somaria I/O de disco a um caminho que roda a 2 Hz.
        Quem quiser o incumbente num `ProfileManager` só-leitura injeta o store
        do daemon (é o que `Daemon._manager_de_selecao` passou a fazer).

        Tolerante a dublê: um store falso pode devolver qualquer coisa, e só
        uma string não vazia é nome de perfil.
        """
        nome = getattr(self.store, "active_profile", None)
        return nome if isinstance(nome, str) and nome else None

    def _melhor_candidato(
        self, candidates: list[Profile], wm_class: str
    ) -> Profile:
        """Elege UM candidato — e o terceiro termo do desempate é declarado.

        EMPATE-01 (sprint 27/07). Até aqui a escolha era
        `sort(key=(not catch_all, priority), reverse=True)` e nada mais. Como o
        `sort` do Python é estável e o `load_all_profiles` entrega os arquivos
        em `sorted(glob("*.json"))`, todo empate caía na ORDEM ALFABÉTICA DO
        NOME DO ARQUIVO — que não é critério de ninguém, é acidente de `glob`.
        Medido no disco dela: `pragmata.json` e `pragmata2.json` são idênticos
        fora o campo `name`, ambos empatam em prioridade 5, e quem vencia era
        `Pragmata` — enquanto o perfil que ela deixou ativo era o `Pragmata2`.
        É um mecanismo direto para a queixa mais antiga desta casa, *"a config
        que eu deixo nunca é respeitada"*.

        O terceiro termo é o INCUMBENTE: em empate, o perfil que já está ativo
        continua. É a escolha deliberadamente mais conservadora do leque —
        não inventa hierarquia nova (nenhuma "data de modificação", nenhum
        "perfil padrão" a mais para ela administrar), não muda nada quando não
        há empate, e o que ele faz em uma frase é: **uma disputa sem critério
        deixa de derrubar o que estava valendo**.

        Quando o incumbente não está entre os empatados, o desempate segue
        sendo o histórico (o primeiro da ordem de carga) — mudar isso mudaria
        comportamento já validado sem que ninguém tenha pedido.
        """
        melhor = max(self._chave_de_selecao(p) for p in candidates)
        empatados = [p for p in candidates if self._chave_de_selecao(p) == melhor]
        if len(empatados) == 1:
            return empatados[0]
        incumbente = self._nome_do_incumbente()
        vencedor = empatados[0]
        if incumbente is not None:
            for candidato in empatados:
                if self._refers_same_profile(incumbente, candidato.name):
                    vencedor = candidato
                    break
        chave_log = (wm_class, vencedor.name)
        if self._ultimo_empate_logado != chave_log:
            self._ultimo_empate_logado = chave_log
            logger.info(
                "profile_select_empate_resolvido",
                wm_class=wm_class,
                empatados=sorted(p.name for p in empatados),
                vencedor=vencedor.name,
                incumbente=incumbente,
                prioridade=vencedor.priority,
            )
        return vencedor


def _estado_da_secao(valor: object) -> str:
    """Normaliza o retorno de um applier de perfil (R-03).

    O daemon real devolve o vocabulário de `daemon.lifecycle`
    (`"aplicado"`, `"adiado_lock_manual"`, `"ignorado_*"`). Dublês de teste,
    a CLI e appliers de terceiros devolvem `None`/bool — e nesse caso a leitura
    honesta é "aplicado": quem não sabe adiar não pode fabricar um adiamento no
    relatório que a GUI vai mostrar.
    """
    return valor if isinstance(valor, str) else "aplicado"


def resolve_key_bindings(
    raw: dict[str, list[str]] | None,
) -> dict[str, KeyBinding]:
    """Resolve um mapping CRU de key_bindings (button→tokens) para o device.

    Mesmas regras de `_to_key_bindings`, mas recebe o mapping cru em vez de um
    `Profile` — usado por `profile.apply_draft` (DraftApplier) para empurrar os
    bindings editados na aba Teclado ao device vivo sem reativar o perfil do
    disco (BUG-FOOTER-APPLY-IGNORA-KEYBINDINGS-01).

    Regras (FEAT-KEYBOARD-PERSISTENCE-01):
    - `None` → herda `DEFAULT_BUTTON_BINDINGS` completo.
    - `{}` → vazio (teclado silencioso; usuário removeu todos os bindings).
    - dict parcial → override isolado; **não mescla com defaults**.
    """
    if raw is None:
        return dict(DEFAULT_BUTTON_BINDINGS)
    return {button: tuple(tokens) for button, tokens in raw.items()}


def _to_key_bindings(profile: Profile) -> dict[str, KeyBinding]:
    """Resolve `Profile.key_bindings` em mapping pronto para o device.

    Converte `list[str]` do schema em `tuple[str, ...]` (KeyBinding). Delega a
    resolução das regras (None/{}/parcial) a `resolve_key_bindings`.
    """
    return resolve_key_bindings(profile.key_bindings)


def _controllers_to_specs(
    controllers: dict[str, ControllerOverrides] | None,
    global_leds: LedsConfig | None = None,
) -> dict[str, OutputSpec]:
    """Converte o mapa `controllers` do perfil em `OutputSpec` por MAC.

    PERFIL-04 (sprint perfis-por-controle): o vocabulário parcial se
    preserva — seção ausente no override (`None`) vira campo `None` no spec
    ("sem opinião": o merge POR CAMPO do backend herda o padrão broadcast).

    Fix do review (2026-07-16, MED): a parcialidade vale também DENTRO da
    seção — só campos EXPLICITAMENTE escritos no JSON (``model_fields_set``
    do pydantic) entram no spec; campo não escrito vira ``None`` e herda o
    global no merge do backend, em paridade com o applier IPC. Antes, os
    defaults do schema densificavam os campos ausentes (player-LEDs todos
    apagados, brilho 1.0, gatilho ``Off``) e pisavam o global do controle —
    a resolução-por-objeto refutada pelo sprint doc, um nível abaixo.

    Cor e brilho formam UM campo no backend (o RGB pré-escalado); quando o
    override escreve a COR, o brilho é resolvido de ``global_leds`` (a seção
    global do perfil) AQUI na borda e escala o RGB pelo MESMO caminho da
    seção global (`LedSettings.apply_brightness`): o que fica registrado no
    mapa do backend — e reaplicado no hotplug — é a cor JÁ escalada, em
    paridade com o broadcast. Entradas sem nenhum campo escrito são puladas.

    R-20 item 2 (auditoria 23/07): override que escreve SÓ o brilho deixou
    de virar cor. Antes ele resolvia `lightbar` do global só para poder
    escalar — e, como o override por-uniq vence a camada AUTOMÁTICA, ajustar
    o brilho de um controle MATAVA a cor do slot dele (o achado
    `brilho-por-controle-materializa-cor-global`). Esse caso sai daqui e vai
    para `_controllers_to_led_scales`, que registra um FATOR aplicado depois
    do merge, sobre a cor resolvida — automática inclusive.
    """
    out: dict[str, OutputSpec] = {}
    for uniq, cfg in (controllers or {}).items():
        trigger_left: TriggerEffect | None = None
        trigger_right: TriggerEffect | None = None
        if cfg.triggers is not None:
            lados = cfg.triggers.model_fields_set
            if "left" in lados:
                trigger_left = build_from_name(
                    cfg.triggers.left.mode, cfg.triggers.left.params
                )
            if "right" in lados:
                trigger_right = build_from_name(
                    cfg.triggers.right.mode, cfg.triggers.right.params
                )
        led: tuple[int, int, int] | None = None
        player_leds: tuple[bool, bool, bool, bool, bool] | None = None
        if cfg.leds is not None:
            campos = cfg.leds.model_fields_set
            if "lightbar" in campos or _brilho_materializa_cor(cfg, global_leds):
                rgb = (
                    cfg.leds.lightbar
                    if "lightbar" in campos or global_leds is None
                    else global_leds.lightbar
                )
                brilho = (
                    cfg.leds.lightbar_brightness
                    if "lightbar_brightness" in campos or global_leds is None
                    else global_leds.lightbar_brightness
                )
                settings = LedSettings(
                    lightbar=rgb, brightness_level=float(brilho)
                )
                led = settings.apply_brightness(settings.brightness_level).lightbar
            if "player_leds" in campos:
                player_leds = _to_led_settings(cfg.leds).player_leds
        if (
            trigger_left is None
            and trigger_right is None
            and led is None
            and player_leds is None
        ):
            continue
        out[uniq] = OutputSpec(
            trigger_left=trigger_left,
            trigger_right=trigger_right,
            led=led,
            player_leds=player_leds,
        )
    return out


def _brilho_materializa_cor(
    cfg: ControllerOverrides, global_leds: LedsConfig | None
) -> bool:
    """True quando o brilho por-controle ainda precisa virar cor (R-20 item 2).

    Só no caso degenerado: a escala relativa é `brilho_do_controle /
    brilho_global`, e com brilho global 0 (ou sem seção global para comparar)
    a cor resolvida JÁ é preta — não há o que escalar de volta. Aí materializar
    é a única forma honesta de honrar o pedido dela, e o custo (perder a cor
    automática daquele controle) é o comportamento antigo, restrito a um canto
    que ninguém alcança sem zerar o brilho do perfil inteiro.
    """
    if cfg.leds is None or "lightbar_brightness" not in cfg.leds.model_fields_set:
        return False
    return global_leds is None or float(global_leds.lightbar_brightness) <= 0.0


def _controllers_to_led_scales(
    controllers: dict[str, ControllerOverrides] | None,
    global_leds: LedsConfig | None = None,
) -> dict[str, float]:
    """Escala de brilho POR CONTROLE do perfil (R-20 item 2).

    Devolve `{uniq: fator}` para os overrides que escreveram SÓ
    `lightbar_brightness` (sem `lightbar`). O fator é RELATIVO ao brilho
    global — `brilho_do_controle / brilho_global` — porque a cor que chega ao
    merge (broadcast do perfil ou paleta automática do slot) já vem escalada
    pelo global; multiplicar de novo pelo absoluto escureceria duas vezes.

    Override que escreve a COR (com ou sem brilho) não entra: ali o brilho já
    foi aplicado na borda, em paridade com o broadcast. Fator 1.0 também não
    entra — é "sem opinião", e uma entrada inócua no mapa só custaria uma
    cópia de `_DesiredOutput` a cada resolução.
    """
    out: dict[str, float] = {}
    if global_leds is None:
        return out
    base = float(global_leds.lightbar_brightness)
    if base <= 0.0:
        # Degenerado: `_brilho_materializa_cor` cobre esse caso na outra ponta.
        return out
    for uniq, cfg in (controllers or {}).items():
        if cfg.leds is None:
            continue
        campos = cfg.leds.model_fields_set
        if "lightbar" in campos or "lightbar_brightness" not in campos:
            continue
        fator = float(cfg.leds.lightbar_brightness) / base
        if fator == 1.0:
            continue
        out[uniq] = fator
    return out


def _to_led_settings(leds: LedsConfig) -> LedSettings:
    """Converte `LedsConfig` (schema de perfil) em `LedSettings` (camada de hardware).

    Propaga todos os campos relevantes: lightbar RGB, brightness_level
    e player_leds. Armadilha A-06 resolvida para brightness (FEAT-LED-BRIGHTNESS-02).
    """
    player_leds_tuple: tuple[bool, bool, bool, bool, bool] = (
        leds.player_leds[0],
        leds.player_leds[1],
        leds.player_leds[2],
        leds.player_leds[3],
        leds.player_leds[4],
    )
    return LedSettings(
        lightbar=leds.lightbar,
        brightness_level=float(leds.lightbar_brightness),
        player_leds=player_leds_tuple,
    )


__all__ = [
    "MOTIVO_JOGO_SEM_PERFIL_PROPRIO",
    "MOTIVO_SELECIONADO",
    "MOTIVO_SEM_CANDIDATO",
    "ProfileManager",
    "_controllers_to_led_scales",
    "_controllers_to_specs",
    "_estado_da_secao",
    "_to_key_bindings",
    "_to_led_settings",
    "resolve_key_bindings",
]
