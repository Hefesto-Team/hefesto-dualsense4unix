"""Gerencia perfis em memória e coordena aplicação no controle."""
from __future__ import annotations

import contextlib
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.core.controller import IController, OutputSpec, TriggerEffect
from hefesto_dualsense4unix.core.keyboard_mappings import DEFAULT_BUTTON_BINDINGS, KeyBinding
from hefesto_dualsense4unix.core.led_control import (
    LEGADO,
    LedSettings,
    cor_escolhida,
    degrau_do_brilho_das_luzes,
)
from hefesto_dualsense4unix.core.speaker_scale import volume_do_percentual
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.loader import (
    delete_profile,
    load_all_profiles,
    load_profile,
    save_profile,
)
from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale
from hefesto_dualsense4unix.profiles.schema import (
    CONFIRMADA_POR_ESCOLHA,
    CONFIRMADA_POR_GESTO,
    ControllerOverrides,
    LedsConfig,
    MatchCriteria,
    PonteConfirmada,
    Profile,
    ProfileModeConfig,
    ProfileMouseConfig,
    controles_em_economia,
    e_endereco_de_jogo,
    economia_da_mesa,
    economia_vale,
    gatilhos_do_perfil_na_economia,
    gatilhos_na_economia,
    leds_do_perfil_na_economia,
    leds_na_economia,
    normalizar_gamepad_flavor,
    vibracao_na_economia,
)
from hefesto_dualsense4unix.profiles.steam_app import steam_appid_from_wm_class
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)


MOTIVO_SELECIONADO = "selecionado"
MOTIVO_SEM_CANDIDATO = "sem_candidato"
MOTIVO_JOGO_SEM_PERFIL_PROPRIO = "jogo_sem_perfil_proprio"


_SECOES_DA_SAIDA = frozenset({"trigger", "led"})

_RESULTADO_PARA_RELATORIO: dict[str, str] = {
    "escreveu": "aplicado",
    "registrado": "adiado_sem_controle",
    "falhou": "falhou_escrita",
    "sem_alvo": "ignorado_sem_alvo",
    "nada_a_fazer": "ignorado_sem_pedido",
}


# Ela, 27/09 à tarde: *«O freestyle nao deveria se comportar como  (noqa-acento: citação)
# jogo.»*  (noqa-acento: citação literal)


class OFreestyleMandaError(RuntimeError):
    """Um caminho automático pediu outro perfil com o Freestyle ligado."""


class OFreestyleDesligadoError(RuntimeError):
    """Um caminho que não é a mão do usuário pediu o Freestyle com o modo desligado."""


def e_o_freestyle(nome: object) -> bool:
    """O nome aponta o Freestyle? Pelo slug, que é a identidade do arquivo."""
    from hefesto_dualsense4unix.profiles.loader import SLUG_DO_PADRAO
    from hefesto_dualsense4unix.profiles.slug import mesmo_slug

    return isinstance(nome, str) and mesmo_slug(nome, SLUG_DO_PADRAO)


def os_perfis_de_escolher(perfis: Iterable[Any]) -> list[Any]:
    """A lista que se oferece para ESCOLHER: todos os perfis, menos o Freestyle."""
    return [p for p in perfis if not e_o_freestyle(getattr(p, "name", None))]


def o_freestyle_manda(store: object | None) -> bool:
    """O Modo Freestyle está ligado agora? Só o `True` literal do store conta."""
    return getattr(store, "freestyle_ligado", False) is True


def ligar_o_freestyle(store: object | None, ligado: bool) -> None:
    """O ÚNICO escritor do Modo Freestyle: a memória e o disco, juntos."""
    from hefesto_dualsense4unix.utils.session import (
        espelhar_a_escolha,
        save_freestyle_ligado,
    )

    antes = o_freestyle_manda(store)
    setter = getattr(store, "set_freestyle_ligado", None)
    if callable(setter):
        setter(bool(ligado))
    save_freestyle_ligado(bool(ligado))
    with contextlib.suppress(Exception):
        espelhar_a_escolha()
    if antes != bool(ligado):
        logger.info("freestyle_ligado" if ligado else "freestyle_desligado")


def armar_a_trava_da_mao(store: object | None) -> None:
    """Arma a trava da troca à mão, sem prazo. Nunca levanta."""
    marcar = getattr(store, "mark_manual_profile_lock", None)
    if callable(marcar):
        with contextlib.suppress(Exception):
            marcar(math.inf)


def soltar_a_trava_da_mao(store: object | None, motivo: str, **contexto: object) -> bool:
    """Solta a trava da troca à mão, com a linha no diário. Devolve se estava armada."""
    import time as _time

    ativa = getattr(store, "manual_profile_lock_active", None)
    marcar = getattr(store, "mark_manual_profile_lock", None)
    if not callable(ativa) or not callable(marcar):
        return False
    try:
        if not ativa(_time.monotonic()):
            return False
        marcar(0.0)
    except Exception:
        return False
    logger.info("trava_da_troca_a_mao_solta", motivo=motivo, **contexto)
    return True


@dataclass
class ProfileManager:
    controller: IController
    store: StateStore = field(default_factory=StateStore)
    # Quando presente, `activate()` propaga o `key_bindings` resolvido para
    keyboard_device: object | None = None
    keyboard_device_provider: Callable[[], object | None] | None = None
    # pelo qual `apply_button_actions` empurra o que cada botão faz. É LAZY pela
    mouse_device_provider: Callable[[], object | None] | None = None
    # `button_actions` e o único que não é device. Recebe o token que o perfil
    #
    # no poll loop, e o comentário dele proíbe trabalho bloqueante ali com um
    ps_action_sink: Callable[[str | None], object] | None = None
    mouse_applier: Callable[..., object] | None = None
    suppression_applier: Callable[..., object] | None = None
    mode_applier: Callable[..., object] | None = None
    # só política aplicada por OUTRO perfil; política manual fica), mais o
    rumble_policy_applier: Callable[..., object] | None = None
    # Os callsites injetam `daemon.apply_profile_rumble_passthrough` — recebe o
    rumble_passthrough_applier: Callable[[bool], None] | None = None
    speaker_applier: Callable[..., object] | None = None
    #
    mic_applier: Callable[..., object] | None = None
    _ultimo_veto_catch_all: str | None = field(default=None, repr=False)
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
        # slug (ex.: active="Ação", name="acao" — slugs iguais, strings não).  # (noqa-acento)
        if active is not None and self._refers_same_profile(active, name):
            self.store.set_active_profile(None)
        if e_o_freestyle(name):
            ligar_o_freestyle(self.store, False)
        from hefesto_dualsense4unix.utils.session import esquecer_a_escolha

        esquecer_a_escolha(name)
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
        "Navegação" em vez da escolha do usuário. Valores:

          - ``"manual"`` (default) — profile.switch via IPC (GUI/CLI/bandeja/
            TUI) e o ciclo por hotkey (PS+D-pad): É a escolha do usuário → grava
            pelo dono (`utils.session.gravar_a_escolha`), decide o Modo
            Freestyle e arma a trava da troca à mão (ver o bloco antes da
            classe).
          - ``"autoswitch"`` — troca automática por janela em foco: aplica e
            marca ativo, mas NÃO grava a escolha.
          - ``"launch"`` — o lançamento de um jogo com perfil: idem, e solta a
            trava da troca à mão (o jogo com perfil abriu).
          - ``"system"`` — restore de boot e de reconexão, saída do Modo
            Nativo e o botão desligado: idem, o sistema devolvendo a escolha
            não é escolha nova.

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
        return self._ativar(
            name, origin=origin, relatorio=relatorio, e_a_escolha=origin == "manual"
        )

    def reaplicar(
        self,
        name: str,
        *,
        relatorio: dict[str, str] | None = None,
    ) -> Profile:
        """O perfil inteiro de novo aos controles, sem virar a escolha do usuário.

        O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01 (01/10/2026). O «Aplicar» mandava
        `profile.apply_draft` (já removido), que levava menos da metade do
        perfil: ficavam de fora o volume e o ganho do microfone, os sensores, a
        máscara, a mira, o modo e a política de vibração. Agora ele roda a
        MESMA cadeia da ativação, com todas as camadas.

        Os appliers recebem a origem `manual`: o «Aplicar» é gesto do usuário
        (`D-A-MASCARA-POR-CONTROLE-VALE-NO-APLICAR`), e com o jogo na
        autoridade a R-04 vale igual à da ativação. O que ele NÃO faz é o que
        só a escolha faz: não grava o `session.json` nem o
        `active_profile.txt`, não mexe no Modo Freestyle e não arma a trava da
        troca à mão (essa é do handler do `profile.switch`).
        """
        return self._ativar(name, origin="manual", relatorio=relatorio, e_a_escolha=False)

    def apagar_o_freestyle(
        self,
        name: str | None,
        *,
        origin: str = "system",
        relatorio: dict[str, str] | None = None,
    ) -> Profile | None:
        """O botão «Modo Freestyle» apagado: o perfil que volta, e o modo desliga."""
        if name and not e_o_freestyle(name):
            try:
                return self._ativar(
                    name, origin=origin, relatorio=relatorio,
                    e_a_escolha=False, apagando_o_freestyle=True,
                )
            except Exception as exc:
                logger.warning("freestyle_apagado_sem_o_perfil_que_volta",
                               name=name, err=str(exc))
        self.store.set_active_profile(None)
        ligar_o_freestyle(self.store, False)
        return None

    def _ativar(
        self,
        name: str,
        *,
        origin: str,
        relatorio: dict[str, str] | None,
        e_a_escolha: bool,
        apagando_o_freestyle: bool = False,
    ) -> Profile:
        """A cadeia única da ativação e do «Aplicar». Ver :meth:`activate`."""
        manda = o_freestyle_manda(self.store)
        if not e_a_escolha and manda and not apagando_o_freestyle and not e_o_freestyle(name):
            logger.info("perfil_recusado_o_freestyle_manda", pedido=name, origin=origin)
            raise OFreestyleMandaError(
                f"o Modo Freestyle está ligado: {name!r} não entra por {origin!r}"
            )
        if not e_a_escolha and not manda and e_o_freestyle(name):
            logger.info("perfil_recusado_o_freestyle_desligado", pedido=name, origin=origin)
            raise OFreestyleDesligadoError(
                f"o Modo Freestyle está desligado: {name!r} não entra por {origin!r}"
            )
        profile = o_que_vale(load_profile(name))
        self.apply(profile, origin=origin, relatorio=relatorio)
        self.apply_keyboard(profile, relatorio=relatorio)
        self.apply_button_actions(profile, relatorio=relatorio)
        self.apply_remapeamento(profile, relatorio=relatorio)
        self.apply_movimento(profile, relatorio=relatorio)
        self.apply_emulation(profile, origin=origin, relatorio=relatorio)
        if e_a_escolha and e_o_freestyle(profile.name):
            ligar_o_freestyle(self.store, True)
        self.store.set_active_profile(profile.name)
        if apagando_o_freestyle:
            ligar_o_freestyle(self.store, False)
        reaplicacao = origin == "manual" and not e_a_escolha
        self.store.bump("profile.reaplicado" if reaplicacao else "profile.activated")
        logger.info(
            "perfil_reaplicado" if reaplicacao else "profile_activated",
            name=profile.name,
            priority=profile.priority,
            origin=origin,
        )
        if e_a_escolha:
            from hefesto_dualsense4unix.utils.session import gravar_a_escolha

            # liga (acima, antes do `set_active_profile`), o de qualquer outro
            if not e_o_freestyle(profile.name):
                ligar_o_freestyle(self.store, False)
            gravar_a_escolha(profile.name)
            armar_a_trava_da_mao(self.store)
        elif origin == "launch":
            soltar_a_trava_da_mao(
                self.store, "lancamento_de_jogo_com_perfil", perfil=profile.name
            )
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
        (`LedSettings.apply_brightness`).

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
        apagado segundos depois (a configuração por controle não valia
        controle a controle). Agora a ativação substitui só o que é do perfil
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
        # sair. ABAS-05 (25/07): o `trigger.reset` (botão "Desligar" da aba
        if origin == "manual":
            soltar = getattr(self.controller, "clear_user_output_overrides", None)
            if callable(soltar):
                soltar()

        profile = _perfil_na_economia(
            profile, economia_da_mesa(), controles_em_economia()
        )
        left = build_from_name(profile.triggers.left.mode, profile.triggers.left.params)
        right = build_from_name(profile.triggers.right.mode, profile.triggers.right.params)
        settings = _to_led_settings(profile.leds)
        effective = settings.apply_brightness(settings.brightness_level)
        # ESCOLHIDA (antes do brilho): depois dele, um `lightbar_brightness`
        cor_do_global = cor_escolhida(settings.lightbar)
        self._configure_auto_player_colors(profile)
        resultado_da_saida = self.controller.apply_output_defaults(
            OutputSpec(
                trigger_left=left,
                trigger_right=right,
                led=None if cor_do_global is None else effective.lightbar,
                player_leds=settings.player_leds,
                player_led_brightness=(
                    degrau_do_brilho_das_luzes(profile.leds.player_led_brightness)
                    if self._o_todos_das_luzes_vai_cru(profile)
                    else None
                ),
            )
        )
        overrides = _controllers_to_specs(profile.controllers, profile.leds)
        # `#0000FF` do disco é a escolha do usuário para o número de hoje ou o
        procedencias = _controllers_to_procedencias(profile.controllers)
        escalas = _controllers_to_led_scales(profile.controllers, profile.leds)
        escalar = getattr(self.controller, "set_led_scales", None)
        if callable(escalar):
            try:
                escalar(
                    escalas or None,
                    brilho_do_perfil=float(profile.leds.lightbar_brightness),
                    cor_do_perfil=cor_do_global,
                )
            except TypeError:
                escalar(escalas or None)
        escalas_rumble = _controllers_to_rumble_scales(
            profile.controllers, getattr(profile, "rumble", None)
        )
        escalar_rumble = getattr(self.controller, "set_rumble_scales", None)
        if callable(escalar_rumble):
            escalar_rumble(escalas_rumble or None)
        publicar = getattr(self.controller, "reset_profile_overrides", None)
        if callable(publicar):
            _publicar_camada(publicar, overrides, procedencias)
        else:
            _publicar_camada(
                self.controller.reset_output_overrides, overrides, procedencias
            )
            for uniq, spec in overrides.items():
                _aplicar_com_procedencia(
                    self.controller.apply_output_for,
                    uniq,
                    spec,
                    procedencias.get(uniq, LEGADO),
                )
        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()
        if relatorio is not None:
            palavra = _RESULTADO_PARA_RELATORIO.get(
                resultado_da_saida if isinstance(resultado_da_saida, str) else "",
                "aplicado",
            )
            for categoria in sorted(_SECOES_DA_SAIDA):
                relatorio.setdefault(categoria, palavra)

    def _o_todos_das_luzes_vai_cru(self, profile: Profile) -> bool:
        """O «Todos» das luzes de número vai cru a todo controle nesta ativação?

        O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01 (01/10/2026), a regra que o
        «Aplicar» antigo já tinha. O
        `apply_output_defaults` leva o global CRU a todo handle; um controle que
        termina noutro degrau (a palavra dele, ou o Fraco da economia) passaria
        por ele antes do dele, um quadro intermediário (medido na mesa de
        quatro: o P1 no Forte passava por `[2, 0, 0]`). Com o MESMO perfil que
        já vale, o padrão do backend já é este global, e ele fica: cada
        controle recebe o seu pela camada do perfil. Na troca de perfil o
        global novo vai sempre, porque o padrão de antes é de outro perfil.
        `profile` é a vista com a economia posta.
        """
        if not self._refers_same_profile(
            str(getattr(self.store, "active_profile", "") or ""), profile.name
        ):
            return True
        global_ = profile.leds.player_led_brightness
        for override in (profile.controllers or {}).values():
            leds = getattr(override, "leds", None)
            if (
                leds is not None
                and "player_led_brightness" in leds.model_fields_set
                and leds.player_led_brightness != global_
            ):
                return False
        return True


    @staticmethod
    def _configure_auto_player_colors(profile: Profile) -> None:
        """Propaga o toggle/brilho do automático ao registro de identidade (COR-03)."""
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

    def _empurrar_o_ps(self, profile: Profile) -> None:
        """A escolha do PS, entregue a quem a atende — o callback do `ps_solo`.

        A QUARTA SAÍDA de `core/acoes_de_botao` (:func:`acao_do_ps`), e ela não
        vai a device nenhum: o PS nunca chega à emulação, porque o latch do
        combo (`integrations/hotkey_daemon.py`) o subtrai de `emu_buttons`
        enquanto estiver pressionado. Quem o atende é o `ps_solo`, no release.

        `None` É PARTE DO CONTRATO e não é ausência de chamada: ele diz "o
        perfil não opinou sobre o PS", e é o que devolve o botão ao degrau da
        máquina (`DaemonConfig.ps_button_action`). Um perfil sem `button_actions`
        chega aqui igual, e é por isso que a chamada é antes da saída antecipada.

        Sem `ps_action_sink` (CLI, testes sem daemon) isto é no-op silencioso —
        a mesma disciplina dos dois providers de device.
        """
        empurrar = self.ps_action_sink
        if empurrar is None:
            return
        from hefesto_dualsense4unix.core.acoes_de_botao import acao_do_ps

        try:
            empurrar(acao_do_ps(profile.button_actions))
        except Exception as exc:
            logger.warning(
                "ps_action_push_failed", profile=profile.name, err=str(exc))

    def apply_button_actions(
        self, profile: Profile, *, relatorio: dict[str, str] | None = None
    ) -> None:
        """Propaga `button_actions` do perfil aos TRÊS destinos (FEAT-ACOES-DE-BOTAO-01).

        Ele é o irmão do `apply_keyboard`, e a diferença é o alcance: aquele
        escreve os nove botões que o teclado virtual conhece; este escreve as
        vinte e duas linhas que a tela mostra, e o
        `core/acoes_de_botao.resolver()` é quem as separa entre o device de
        mouse (`BTN_*`) e o de teclado (`KEY_*` e os tokens virtuais).

        O TERCEIRO DESTINO NÃO É DEVICE (ONDA5-06-01): a linha do botão PS vai
        para o subsistema de hotkey, pelo `ps_action_sink`, porque quem a atende
        é o callback do `ps_solo` — ver :meth:`_empurrar_o_ps`.

        A ORDEM IMPORTA, e ela é: este método roda DEPOIS do `apply_keyboard`.
        Sem `button_actions` no perfil ele não toca em nada — o `None` do campo
        significa "herda o de fábrica", e o de fábrica já é o que os dois
        devices fazem. Com o campo preenchido, ele escreve por cima, e o que
        escreve é o resolvido: um botão nunca fica nos dois devices.

        OS TRÊS ESTADOS DO RELATÓRIO, como no irmão — e "sem device" NÃO é
        "aplicou" nem "falhou". É a tela podendo dizer que a escolha está no
        disco e ainda não pousou em lugar nenhum, que é a verdade quando a
        emulação de mouse está desligada.

        O BOTÃO PS É O TERCEIRO DESTINO (ONDA5-06-01), e ele é empurrado ANTES
        de qualquer saída antecipada — inclusive a do perfil sem
        `button_actions` e a do "sem device de mouse". As duas razões são
        medidas: o PS não passa por device nenhum (quem o atende é o callback do
        `ps_solo`), e um perfil que NÃO opina sobre o PS precisa apagar o que o
        perfil anterior opinou — senão a escolha do perfil de ontem continua
        digitando no perfil de hoje.

        ELE HERDA `key_bindings`, E ESSA É A CURA DE UMA PERDA SILENCIOSA —
        06/09/2026, ONDA3-MOTOR-01. Este método roda DEPOIS do `apply_keyboard`
        e reescreve o conjunto INTEIRO do teclado virtual com o que o
        `resolver()` deriva. Enquanto o `resolver()` não consultava
        `profile.key_bindings`, todo atalho que o usuário escreveu na janela antiga
        morria na ativação seguinte de qualquer perfil que tivesse
        `button_actions` — sem uma palavra, e com os dois campos continuando a
        aparecer no arquivo dela. Passar o campo é o elo; as três camadas e a
        precedência estão em `core/acoes_de_botao._tabela_efetiva`.

        E ELE DIZ AO DEVICE O QUE FOI CALADO, pela mesma data e pelo mesmo
        motivo: `do_mouse` não distingue "não é do mouse" de "foi calado", e o
        `set_button_actions` reconstruía o d-pad e o tap do de fábrica — seis
        botões em `— Nada —` voltavam a emitir. Quem monta a sacola é
        `core/acoes_de_botao.botoes_calados`.
        """
        self._empurrar_o_ps(profile)
        if profile.button_actions is None:
            self._mouse_ao_de_fabrica(profile)
            if relatorio is not None:
                relatorio["button_actions"] = "de_fabrica"
            return

        from hefesto_dualsense4unix.core.acoes_de_botao import (
            botoes_calados,
            resolver,
        )

        do_mouse, do_teclado, sem_dono = resolver(
            profile.button_actions, profile.key_bindings)
        calados = botoes_calados(profile.button_actions, profile.key_bindings)
        if sem_dono:
            logger.info(
                "button_actions_sem_atendente",
                profile=profile.name,
                botoes=sorted(sem_dono),
            )

        provider = self.mouse_device_provider
        device = provider() if provider is not None else None
        if device is None:
            if relatorio is not None:
                relatorio["button_actions"] = "ignorado_sem_device"
            return
        try:
            device.set_button_actions(  # type: ignore[attr-defined]
                do_mouse, calados)
            teclado_provider = self.keyboard_device_provider
            teclado = (teclado_provider() if teclado_provider is not None
                       else self.keyboard_device)
            if teclado is not None:
                teclado.set_bindings(  # type: ignore[attr-defined]
                    resolve_key_bindings(dict(
                        (b, list(toks)) for b, toks in do_teclado.items())))
        except Exception as exc:
            logger.warning(
                "button_actions_apply_failed", profile=profile.name, err=str(exc))
            if relatorio is not None:
                relatorio["button_actions"] = "falhou"
            return
        if relatorio is not None:
            relatorio["button_actions"] = "aplicado"

    def _mouse_ao_de_fabrica(self, profile: Profile) -> None:
        """O mapa de botões do mouse virtual de fábrica. Sem device, nada; nunca levanta."""
        provider = self.mouse_device_provider
        device = provider() if provider is not None else None
        if device is None:
            return
        try:
            # `None` é o de fábrica do device (`UinputMouseDevice.set_button_actions`).
            device.set_button_actions(None)  # type: ignore[attr-defined]
        except Exception as exc:
            logger.warning("button_actions_de_fabrica_falhou",
                           profile=profile.name, err=str(exc))

    def apply_remapeamento(
        self, profile: Profile, *, relatorio: dict[str, str] | None = None
    ) -> None:
        """Deposita a troca botão a botão do perfil no `store` (F1-REMAPEAR)."""
        from hefesto_dualsense4unix.core.remapeamento_de_botao import (
            definir_ativo,
            resolver,
        )

        try:
            mapa = resolver(profile.remapeamento)
        except ValueError as exc:
            logger.warning(
                "remapeamento_recusado", profile=profile.name, err=str(exc))
            mapa = {}
            if relatorio is not None:
                relatorio["remapeamento"] = "falhou"
        definir_ativo(self.store, mapa or None)
        if relatorio is not None and "remapeamento" not in relatorio:
            relatorio["remapeamento"] = "aplicado" if mapa else "de_fabrica"

    def apply_movimento(
        self, profile: Profile, *, relatorio: dict[str, str] | None = None
    ) -> None:
        """Deposita a mira por movimento do perfil no `store`."""
        from hefesto_dualsense4unix.core.roteador_de_movimento import (
            ArranjoRecusadoError,
            definir_ativo,
            definir_por_peca,
            montar,
            sincronizar_o_filtro,
        )

        arranjo = None
        try:
            arranjo = montar(profile.movimento) if profile.movimento is not None else None
        except ArranjoRecusadoError as exc:
            logger.warning("movimento_recusado", profile=profile.name, err=str(exc))
            if relatorio is not None:
                relatorio["movimento"] = "falhou"
        definir_ativo(self.store, arranjo)
        por_peca = _controllers_to_miras(
            profile.controllers, profile.movimento, relatorio=relatorio
        )
        definir_por_peca(self.store, por_peca)
        sincronizar_o_filtro(self.store)
        ligado = arranjo is not None and arranjo.ligado
        if relatorio is not None and "movimento" not in relatorio:
            relatorio["movimento"] = "aplicado" if ligado else "desligado"
        if ligado and arranjo is not None:
            logger.info(
                "roteador_de_movimento_ligado",
                profile=profile.name,
                destino=arranjo.destino,
                gatilho=arranjo.gatilho or "sempre",
            )

    def apply_keyboard(
        self, profile: Profile, *, relatorio: dict[str, str] | None = None
    ) -> None:
        """Propaga `key_bindings` do perfil ao device virtual de teclado (A-06)."""
        provider = self.keyboard_device_provider
        device = provider() if provider is not None else self.keyboard_device
        if device is None:
            if relatorio is not None:
                relatorio["keyboard"] = "ignorado_sem_device"
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
            if relatorio is not None:
                relatorio["keyboard"] = "falhou"
            return
        if relatorio is not None:
            relatorio["keyboard"] = "aplicado"

    def apply_emulation(
        self,
        profile: Profile,
        *,
        origin: str = "manual",
        relatorio: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Aplica a seção `mouse` e a supressão de modo-jogo do perfil."""
        resultado: dict[str, str] = relatorio if relatorio is not None else {}
        secao_mouse = profile.mouse
        diz_navegacao = getattr(getattr(profile, "mode", None), "kind", None) == "desktop"
        if self.mouse_applier is not None and (secao_mouse is not None or diz_navegacao):
            try:
                resultado["mouse"] = _estado_da_secao(
                    self.mouse_applier(
                        secao_mouse.enabled if secao_mouse is not None else True,
                        secao_mouse.speed if secao_mouse is not None else None,
                        secao_mouse.scroll_speed if secao_mouse is not None else None,
                        origin=origin,
                        profile=profile,
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
        # o P3 ficaram com a DualSense do Freestyle. E os secundários renasciam
        self.apply_controller_mascaras(profile, origin=origin, relatorio=resultado)
        if self.mode_applier is not None:
            try:
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
        if self.rumble_policy_applier is not None:
            rumble_cfg = getattr(profile, "rumble", None)
            try:
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
        # (`lifecycle.apply_profile_rumble_passthrough`) devolve `None` em TODOS
        if self.rumble_passthrough_applier is not None:
            rumble_cfg = getattr(profile, "rumble", None)
            try:
                estado_passthrough = self.rumble_passthrough_applier(
                    bool(getattr(rumble_cfg, "passthrough", True))
                )
                if isinstance(estado_passthrough, str):
                    resultado["rumble_passthrough"] = estado_passthrough
            except Exception as exc:
                resultado["rumble_passthrough"] = "falhou"
                logger.warning(
                    "profile_rumble_passthrough_apply_failed",
                    profile=profile.name,
                    err=str(exc),
                )
        self.apply_speaker(profile, origin=origin, relatorio=resultado)
        self.apply_controller_speakers(profile, origin=origin, relatorio=resultado)
        self.apply_mic(profile, origin=origin, relatorio=resultado)
        self.apply_controller_mics(profile, origin=origin, relatorio=resultado)
        self.apply_controller_sensores(profile, origin=origin, relatorio=resultado)
        return resultado

    def apply_controller_mascaras(
        self,
        profile: Profile,
        *,
        origin: str = "manual",
        relatorio: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Aplica a MÁSCARA das UNIDADES que o perfil declara (08/09/2026).

        Decisão de produto, MASCARA-NO-PERFIL-01: *"pode entrar sim"* — a máscara por
        controle entra no perfil, ao lado de luz, gatilho, vibração, som, mic e
        sensores. **A consequência que ela sentiu, e que abriu a sprint:**
        trocar de perfil trocava o modo e **não trocava a máscara** de ninguém,
        porque a máscara era da SESSÃO e sobrevivia ao perfil.

        QUEM É O DONO AGORA — e é o ponto inteiro desta entrega. O
        ``controller_masks.json`` (``daemon/subsystems/external_mask.py``)
        deixou de ser dono e virou **cache do que o perfil ativo diz**. Ele
        continua existindo, e por uma razão medida: ``mascara_efetiva`` é
        consultada na criação de todo gamepad virtual **e no tique do co-op**,
        que compara para decidir recriar. Ler o perfil do disco ali seria uma
        tempestade de syscalls — a mesma lição do
        ``gamepad._motores_do_perfil_ativo``. Então o perfil escreve no
        registro, e o registro responde em memória.

        **O PERFIL CALADO DEVOLVE AO PADRÃO — DECISÃO, 09/09/2026.** A
        pergunta era *"um perfil que não fala de máscara deve devolver todo
        mundo ao padrão, ou deixar cada um como está?"*, e a resposta de produto foi
        a primeira: *"Default é Hefesto dualsense padrão"*. Então esta função
        varre o registro e **apaga a máscara própria de todo controle que o
        perfil não declara** (:meth:`ExternalMaskRegistry.manter_somente`).
        Aquele controle passa a herdar o degrau de baixo — o
        ``mode.gamepad_flavor`` do perfil e, na falta dele, o
        ``DaemonConfig.gamepad_flavor``, que de fábrica é ``dualsense``. Isto
        SUBSTITUI a leitura provisória que esta docstring trazia (*"``mascara``
        ausente não mexe na máscara daquela peça"*): aqui ``None`` não é silêncio
        — é *"volte ao padrão"*, e só nesta seção.

        **O CUSTO FOI MEDIDO ANTES DE SER PAGO, e ele é pequeno** (09/09/2026,
        esta árvore). O medo escrito na entrega de ontem era *"derrubar e
        recriar os quatro vpads dela ao ativar um perfil calado"*. Não é o que
        acontece, e o número diz por quê:

        * quem derruba vpad é o laço do co-op, por ``vpad_ficou_para_tras``, e
          ele compara a máscara EFETIVA. Apagar a entrada de quem já estava no
          padrão não muda a efetiva — a comparação dá igual e o vpad **não
          cai**. Só cai o vpad de quem estava FORA do padrão, que é exatamente
          quem a decisão de produto manda trazer de volta;
        * medido nos quatro assentos, com o padrão em ``dualsense``: **0 de 4**
          vpads caem quando a mesa já seguia o padrão, **1 de 4** quando um só
          estava em Xbox, **4 de 4** quando os quatro estavam. E **0 de 4**
          quando os quatro TINHAM entrada própria, mas igual ao padrão: as
          quatro entradas somem do disco e nenhum controle do usuário sai da partida;
        * a varredura em si custa **0,034 ms** e ZERO escrita de disco quando
          não há nada a devolver — o caso comum —, e **0,21 ms** com uma
          escrita só quando há quatro. (Mediana de 200 voltas, ``ext4``. O
          ``manter_somente`` batelha de propósito: quatro ``clear_mask``
          seguidos custariam 0,63 ms e quatro ``_save_locked``.)

        **UMA POR CONTROLE, E SÓ PARA QUEM MUDOU.** A escrita é peça a peça, na
        ordem em que o perfil as declara, e a máscara que já está valendo não é
        reescrita: ``set_mask`` só persiste quando o valor difere, e
        ``vpad_ficou_para_tras`` compara antes de derrubar. Um perfil que repete
        a máscara de três jogadores e muda a do quarto derruba UM vpad.

        Relatório: ``mascara:<uniq>`` → a máscara, uma chave por unidade, no
        mesmo formato-por-peça do ``mic:<uniq>`` e do ``sensores:<uniq>``. Quem
        foi devolvido ao padrão entra com o valor ``"padrão"``, e não com uma
        máscara: o nome do flavor herdado é do degrau de baixo, que esta função
        não conhece (ela não vê a config do daemon) e não pode fingir conhecer.
        """
        from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
            registro_de_mascaras,
        )

        resultado: dict[str, str] = relatorio if relatorio is not None else {}
        registro = registro_de_mascaras()
        controllers = getattr(profile, "controllers", None) or {}
        declaradas: list[str] = []
        for uniq, cfg in controllers.items():
            mascara = getattr(cfg, "mascara", None)
            if mascara is None:
                continue
            alvo = str(uniq)
            declaradas.append(alvo)
            anterior = registro.mask_for(alvo)
            if anterior == str(mascara):
                resultado[f"mascara:{alvo}"] = str(mascara)
                continue
            if not registro.set_mask(alvo, str(mascara)):
                resultado[f"mascara:{alvo}"] = "recusado"
                logger.warning(
                    "profile_mascara_por_peca_recusada",
                    profile=getattr(profile, "name", None),
                    uniq=alvo,
                    origin=origin,
                    mascara=str(mascara),
                )
                continue
            resultado[f"mascara:{alvo}"] = str(mascara)
            logger.info(
                "profile_mascara_por_peca",
                profile=getattr(profile, "name", None),
                uniq=alvo,
                origin=origin,
                mascara=str(mascara),
                anterior=anterior,
            )
        for chave in registro.manter_somente(declaradas):
            resultado[f"mascara:{chave}"] = "padrão"
            logger.info(
                "profile_mascara_devolvida_ao_padrao",
                profile=getattr(profile, "name", None),
                uniq=chave,
                origin=origin,
            )
        return resultado

    def apply_controller_sensores(
        self,
        profile: Profile,
        *,
        origin: str = "manual",
        relatorio: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Aplica o giroscópio/acelerômetro das UNIDADES que têm opinião."""
        from hefesto_dualsense4unix.core.virtual_motion import REGISTRO

        resultado: dict[str, str] = relatorio if relatorio is not None else {}
        controllers = getattr(profile, "controllers", None)
        if not controllers:
            return resultado
        for uniq, cfg in controllers.items():
            secao = getattr(cfg, "sensores", None)
            if secao is None:
                continue
            estado = REGISTRO.definir(
                str(uniq),
                giroscopio=getattr(secao, "giroscopio", None),
                acelerometro=getattr(secao, "acelerometro", None),
            )
            resultado[f"sensores:{uniq}"] = (
                f"giro={'on' if estado.giroscopio else 'off'} "
                f"accel={'on' if estado.acelerometro else 'off'}"
            )
            logger.info(
                "profile_sensores_por_peca",
                profile=getattr(profile, "name", None),
                uniq=str(uniq),
                origin=origin,
                giroscopio=estado.giroscopio,
                acelerometro=estado.acelerometro,
            )
        return resultado

    def apply_controller_speakers(
        self,
        profile: Profile,
        *,
        origin: str = "manual",
        relatorio: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Aplica o alto-falante das UNIDADES que discordam do global (10/08)."""
        resultado: dict[str, str] = relatorio if relatorio is not None else {}
        controllers = getattr(profile, "controllers", None)
        if not controllers:
            return resultado
        for uniq, cfg in controllers.items():
            secao = getattr(cfg, "speaker", None)
            if secao is None:
                continue
            vista = profile.model_copy(update={"speaker": secao})
            estado = self.apply_speaker(vista, origin=origin, uniq=str(uniq))
            if estado is not None:
                resultado[f"speaker:{uniq}"] = estado
        return resultado

    def apply_controller_mics(
        self,
        profile: Profile,
        *,
        origin: str = "manual",
        relatorio: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Aplica o microfone das UNIDADES que discordam do global (03/09/2026)."""
        resultado: dict[str, str] = relatorio if relatorio is not None else {}
        controllers = getattr(profile, "controllers", None)
        if not controllers:
            return resultado
        for uniq, cfg in controllers.items():
            secao = getattr(cfg, "mic", None)
            if secao is None:
                continue
            vista = profile.model_copy(update={"mic": secao})
            estado = self.apply_mic(vista, origin=origin, uniq=str(uniq))
            if estado is not None:
                resultado[f"mic:{uniq}"] = estado
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
           pagar esse preço (é a queixa de que a configuração do usuário nunca é
           respeitada, do lado do áudio).
        2. **a trava manual de áudio vence o perfil.** Categoria `"audio"` do
           `StateStore` (irmã de "trigger"/"led"/"rumble"): se ela acabou de
           mexer no volume na mão, o autoswitch reaplicando o perfil a cada
           troca de janela NÃO pisa o ajuste dela — a mesma disciplina do
           PERFIL-MANUAL-VENCE-01, que trata cor e gatilho assim. Trocar de
           perfil explicitamente limpa as categorias e solta a trava.

           **NOTA DATADA — 18/08/2026.** A categoria `"audio"` deixou de ser só
           do alto-falante: o `mic.set` e o `mic.volume.set` passaram a armá-la
           também, e `apply_mic` a consulta aqui do lado. O que continua sendo
           só daqui é a razão do item 1 (a POSSE dos bytes de volume do report);
           o microfone tem razão própria, escrita em `apply_mic` — a trava
           sozinha não bastava, porque o perfil de JOGO a limpa ao entrar, e
           desde 28/09 o mudo é do controle (O-MUDO-E-DO-CONTROLE-01).
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
        try:
            estado = _estado_da_secao(
                self.speaker_applier(
                    # «Padrão» (04/10/2026): o volume é o do jogo, 100% do registrador; o
                    # `volume` guardado espera o botão desligar.
                    VOLUME_DO_PADRAO if getattr(secao, "volume_padrao", None) is True
                    else int(secao.volume),
                    bool(secao.muted),
                    uniq=uniq,
                    origin=origin,
                    # (o default de quem nunca mexeu no seletor) significa
                    # NÃO TOCAR no `common[7]`, que é o mesmo byte do caminho
                    # do microfone: sem opinião continua sendo silêncio.
                    rota=getattr(secao, "rota", None),
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

    def apply_mic(
        self,
        profile: Profile,
        *,
        origin: str = "manual",
        uniq: str | None = None,
        relatorio: dict[str, str] | None = None,
    ) -> str | None:
        """Aplica a seção `mic` do perfil (PERFIL-GUARDA-O-MIC-01, 18/08/2026)."""
        resultado: dict[str, str] = relatorio if relatorio is not None else {}
        secao = getattr(profile, "mic", None)
        if self.mic_applier is None or secao is None:
            return None
        volume = getattr(secao, "volume", None)
        muted = getattr(secao, "muted", None)
        muted = True if (origin == "replug" and muted is True) else None
        estado_do_ganho = self._aplicar_ganho_do_mic(secao, uniq, resultado)
        if volume is None and muted is None:
            return estado_do_ganho
        try:
            estado = _estado_da_secao(
                self.mic_applier(
                    None if volume is None else int(volume),
                    None if muted is None else bool(muted),
                    uniq=uniq,
                    origin=origin,
                )
            )
        except Exception as exc:
            estado = "falhou"
            logger.warning(
                "profile_mic_apply_failed",
                profile=profile.name,
                err=str(exc),
            )
        resultado["mic"] = estado
        return estado

    def _aplicar_ganho_do_mic(
        self,
        secao: Any,
        uniq: str | None,
        resultado: dict[str, str],
    ) -> str | None:
        """Escreve o `gain` desta seção na placa ALSA deste controle."""
        pedido = getattr(secao, "gain", None)
        if pedido is None:
            return None
        from hefesto_dualsense4unix.integrations import ganho_do_microfone
        if not uniq:
            resultado["mic:ganho"] = "sem_uniq"
            return "sem_uniq"
        try:
            ficou = ganho_do_microfone.definir(str(uniq), int(pedido), [str(uniq)])
        except Exception as exc:  # pragma: no cover - defesa
            logger.warning("profile_mic_gain_failed", uniq=uniq, err=str(exc))
            resultado[f"mic:ganho:{uniq}"] = "falhou"
            return "falhou"
        estado = "sem_placa" if ficou is None else "aplicado"
        resultado[f"mic:ganho:{uniq}"] = estado
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

        **Só reaplica quando o perfil ativo TEM opinião sobre aquela peça** —
        sem isso voltaríamos a tomar posse sem pedido a cada replug, que é o
        defeito que a E4 inteira existe para não cometer. Sem perfil ativo, sem
        opinião nenhuma ou sem applier: devolve `None` e não escreve nada. Com
        a trava manual de áudio armada devolve `"ignorado_trava_manual"` (e
        também não escreve): se o usuário mexeu no volume na mão, quem manda é ela —
        a reconexão não é ocasião para o perfil retomar o campo.

        **"A SEÇÃO" ERA SÓ A GLOBAL, E ISSO ERA O DEFEITO — SOM-ROTA-03,
        16/09/2026.** Este gancho olhava apenas `profile.speaker`, a seção
        GLOBAL. Só que o alto-falante é da PEÇA — decisão de 10/08 — e os
        perfis do usuário guardam o som exclusivamente em
        `controllers[uniq].speaker`, sem global nenhuma. Medido nos dois
        perfis do usuário: `global_speaker: null`, e este gancho devolvendo `None`
        para todos os uniqs. Efeito: **a escolha do usuário nunca voltava depois de
        um replug** — a última palavra ficava sendo a da adoção
        (`ROTA_PADRAO_DO_SOM`), e o `rota 3 + mudo` que ela gravou para uma
        peça sumia em silêncio ao trocar o cabo.

        E havia o mesmo defeito com o sinal trocado: quando a global existia,
        este gancho mandava a GLOBAL para o `uniq` que voltou, ignorando o
        override daquela peça — o replug pisava o ajuste dela.

        A cura reusa o que já existia e mantém a ordem que `apply` respeita
        (global na `:992`, peça na `:994`): o override da peça, quando há,
        entra por último e vence, pela mesma vista `model_copy` que
        `apply_controller_speakers` monta. Mesma família do PERFIL-MANDA-01 e
        do SOM-ROTA-02: o desejo dela existia e morria antes do aparelho.

        `origin="system"` de propósito: reconexão é o sistema reaplicando o
        que já estava configurado, nunca um gesto novo dela (mesma leitura do
        restore de boot).
        """
        nome = getattr(getattr(self, "store", None), "active_profile", None)
        if not nome:
            return None
        try:
            profile = o_que_vale(load_profile(str(nome)))
        except Exception as exc:
            logger.warning(
                "profile_speaker_reapply_load_failed", name=str(nome), err=str(exc)
            )
            return None
        override = None
        if uniq:
            from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

            chave = norm_mac(str(uniq)) or str(uniq)
            cfg = (getattr(profile, "controllers", None) or {}).get(chave)
            override = getattr(cfg, "speaker", None) if cfg is not None else None
        global_ = getattr(profile, "speaker", None)
        if override is None and global_ is None:
            return None
        estado = None
        if global_ is not None:
            estado = self.apply_speaker(profile, origin="system", uniq=uniq)
        if override is not None:
            vista = profile.model_copy(update={"speaker": override})
            estado = self.apply_speaker(vista, origin="system", uniq=uniq)
        return estado

    def reapply_mic_on_connect(self, uniq: str | None = None) -> str | None:
        """Devolve o MICROFONE daquela peça quando o controle (re)conecta."""
        mudo = self._mudo_do_controle(uniq)
        lido = self._mic_do_perfil_ativo(uniq)
        if lido is None:
            if mudo is not True:
                return None
            profile = self._perfil_ativo_carregado()
            if profile is None:
                from hefesto_dualsense4unix.profiles.schema import MatchManual

                profile = Profile(name="o mudo do controle", match=MatchManual())
            global_, override = None, None
        else:
            profile, global_, override = lido
        estado = None
        if global_ is not None:
            secao = global_
            if getattr(global_, "muted", None) is not None:
                secao = global_.model_copy(update={"muted": None})
            estado = self.apply_mic(
                profile.model_copy(update={"mic": secao}), origin="replug", uniq=uniq
            )
        if override is not None or mudo is not None:
            from hefesto_dualsense4unix.profiles.schema import ControllerMicOverride

            peca = override if override is not None else ControllerMicOverride()
            peca = peca.model_copy(update={"muted": mudo})
            vista = profile.model_copy(update={"mic": peca})
            escrito = self.apply_mic(vista, origin="replug", uniq=uniq)
            if escrito is not None:
                estado = escrito
        return estado

    def _mudo_do_controle(self, uniq: str | None) -> bool | None:
        """O mudo que ela deixou no microfone DESTE controle, lido do dono."""
        if not uniq:
            return None
        from hefesto_dualsense4unix.utils.maquina import mudo_do_microfone

        try:
            return mudo_do_microfone(str(uniq))
        except Exception:
            logger.debug("mic_mudo_do_controle_ilegivel", exc_info=True)
            return None

    def _perfil_ativo_carregado(self) -> Any:
        """O `Profile` ativo lido do disco, ou `None` (sem ativo, ou não carrega)."""
        nome = getattr(getattr(self, "store", None), "active_profile", None)
        if not nome:
            return None
        try:
            return o_que_vale(load_profile(str(nome)))
        except Exception as exc:
            logger.warning(
                "profile_mic_reapply_load_failed", name=str(nome), err=str(exc)
            )
            return None

    def _mic_do_perfil_ativo(
        self, uniq: str | None = None
    ) -> tuple[Any, Any, Any] | None:
        """`(perfil, mic_global, mic_da_peça)` do perfil ATIVO, ou `None`."""
        profile = self._perfil_ativo_carregado()
        if profile is None:
            return None
        override = None
        if uniq:
            from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

            chave = norm_mac(str(uniq)) or str(uniq)
            cfg = (getattr(profile, "controllers", None) or {}).get(chave)
            override = getattr(cfg, "mic", None) if cfg is not None else None
        global_ = getattr(profile, "mic", None)
        if override is None and global_ is None:
            return None
        return profile, global_, override

    def o_controle_pede_silencio(self, uniq: str | None = None) -> bool:
        """Ela calou o microfone DESTE controle? (NASCE-LIGADO-MIC-01)"""
        return self._mudo_do_controle(uniq) is True

    def select_for_window(self, window_info: dict[str, object]) -> Profile | None:
        """Escolhe o perfil MAIS ESPECÍFICO que case com a janela."""
        profile, _motivo = self.select_for_window_ex(window_info)
        return profile

    def select_for_window_ex(
        self, window_info: dict[str, object]
    ) -> tuple[Profile | None, str]:
        """Como `select_for_window`, mas devolve `(perfil, motivo)`."""
        casaram = [p for p in load_all_profiles() if p.matches(dict(window_info))]
        candidates = [p for p in casaram if not p.e_catch_all]
        wm_class = str(window_info.get("wm_class") or "")
        e_janela_de_jogo = e_endereco_de_jogo(wm_class)
        if not candidates:
            if not e_janela_de_jogo:
                self._ultimo_veto_catch_all = None
                return None, MOTIVO_SEM_CANDIDATO
            if casaram and self._ultimo_veto_catch_all != wm_class:
                self._ultimo_veto_catch_all = wm_class
                logger.info(
                    "profile_select_catch_all_sem_autoridade_em_jogo",
                    wm_class=wm_class,
                    candidatos=sorted(p.name for p in casaram),
                )
            return None, MOTIVO_JOGO_SEM_PERFIL_PROPRIO
        self._ultimo_veto_catch_all = None
        return self._melhor_candidato(candidates, wm_class), MOTIVO_SELECIONADO

    @staticmethod
    def _chave_de_selecao(profile: Profile) -> tuple[bool, int]:
        """Chave HISTÓRICA da escolha: especificidade e, só depois, prioridade."""
        return (not profile.e_catch_all, profile.priority)

    def _nome_do_incumbente(self) -> str | None:
        """Nome do perfil que JÁ ESTÁ ATIVO, ou None quando não há."""
        nome = getattr(self.store, "active_profile", None)
        return nome if isinstance(nome, str) and nome else None

    def _melhor_candidato(
        self, candidates: list[Profile], wm_class: str
    ) -> Profile:
        """Elege UM candidato — e o terceiro termo do desempate é declarado."""
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


    def perfil_do_appid(self, appid: object) -> Profile | None:
        """O perfil que é a REGRA deste jogo da Steam, ou None."""
        return perfil_do_appid(appid)

    def ponte_confirmada(self, appid: object) -> PonteConfirmada | None:
        """A ponte já CONFIRMADA neste jogo, ou None = ainda não sei."""
        return ponte_confirmada_do_appid(appid)

    def confirmar_ponte(
        self,
        appid: object,
        *,
        kind: str,
        gamepad_flavor: object = None,
        steam_input: bool = False,
        por: str = CONFIRMADA_POR_GESTO,
        quando: str | None = None,
        alinhar_o_modo: bool = False,
    ) -> Profile | None:
        """Carimba a ponte no perfil do jogo e GRAVA. None = não há perfil."""

        def _carimbar(profile: Profile) -> Profile:
            if _a_escolha_dela_ja_carimbou(profile, kind, gamepad_flavor, steam_input):
                return profile
            carimbado = carimbar_ponte(
                profile,
                kind=kind,
                gamepad_flavor=gamepad_flavor,
                steam_input=steam_input,
                por=por,
                quando=quando,
            )
            if not alinhar_o_modo:
                return carimbado
            return alinhar_o_modo_com_a_ponte(
                carimbado, kind=kind, caminho=gamepad_flavor
            )

        salvo = self._gravar_no_perfil_do_appid(
            appid, _carimbar, origem="ponte_confirmada", evento="ponte_confirmada_sem_perfil"
        )
        if salvo is None:
            return None
        if salvo.ponte is not None and salvo.ponte.confirmada_por == CONFIRMADA_POR_ESCOLHA:
            logger.info(
                "ponte_ja_confirmada_pela_escolha_dela",
                appid=str(appid),
                profile=salvo.name,
                pedida_por=por,
            )
            return salvo
        logger.info(
            "ponte_confirmada",
            appid=str(appid),
            profile=salvo.name,
            kind=kind,
            gamepad_flavor=salvo.ponte.gamepad_flavor if salvo.ponte else None,
            steam_input=steam_input,
            por=por,
            modo_alinhado=alinhar_o_modo,
        )
        return salvo

    def alinhar_o_modo_do_appid(
        self, appid: object, *, kind: str, caminho: object = None
    ) -> Profile | None:
        """Grava no `mode` do perfil a ponte de pé, SEM carimbar. None = sem perfil."""
        salvo = self._gravar_no_perfil_do_appid(
            appid,
            lambda profile: alinhar_o_modo_com_a_ponte(
                profile, kind=kind, caminho=caminho
            ),
            origem="ponte_de_pe",
            evento="ponte_de_pe_sem_perfil",
        )
        if salvo is None:
            return None
        logger.info(
            "ponte_de_pe_alinhada_no_perfil",
            appid=str(appid),
            profile=salvo.name,
            kind=kind,
            caminho=salvo.mode.caminho if salvo.mode else None,
        )
        return salvo

    @staticmethod
    def _gravar_no_perfil_do_appid(
        appid: object,
        transformar: Callable[[Profile], Profile],
        *,
        origem: str,
        evento: str,
    ) -> Profile | None:
        """O ÚNICO `save_profile` do caminho por appid. None = não há perfil.

        O `transformar` que devolve o PRÓPRIO perfil diz «nada a mudar», e nada
        se grava (a guarda da escolha do usuário em :meth:`confirmar_ponte`).
        """
        profile = perfil_do_appid(appid)
        if profile is None:
            logger.info(evento, appid=str(appid))
            return None
        novo = transformar(profile)
        if novo is profile:
            return profile
        save_profile(novo, origem=origem)
        return novo

    @staticmethod
    def pontes_confirmadas() -> dict[str, dict[str, object]]:
        """A forma publicada: `{appid: ponte}` — ver `pontes_confirmadas`."""
        return pontes_confirmadas()


def _appids_do_perfil(profile: Profile) -> set[int]:
    """Os appids da Steam que ESTE perfil declara como sua regra.

    Uma regra de jogo é `match.window_class = ["steam_app_<appid>"]` — o mesmo
    formato que `simple_match.from_simple_choice` escreve e que
    `perfil_e_regra_de_jogo` reconhece. Aqui a lista inteira é varrida (e não só
    o primeiro elemento, como em `simple_match._detect_steam_appid`): um perfil
    escrito à mão pode cobrir dois appids, e ignorar o segundo faria a ponte
    confirmada sumir para um jogo que o arquivo nomeia.

    Catch-all e `MatchManual` não declaram appid nenhum, por construção: quem
    chegou por acidente não confirma ponte de ninguém.
    """
    if not isinstance(profile.match, MatchCriteria):
        return set()
    achados = {
        appid
        for wc in profile.match.window_class
        if (appid := steam_appid_from_wm_class(wc)) is not None
    }
    return achados


def _chave_do_appid(appid: object) -> int | None:
    """Aceita `2054970`, `"2054970"` e `"steam_app_2054970"` — um dono só."""
    if isinstance(appid, bool):
        return None
    if isinstance(appid, int):
        return appid if appid > 0 else None
    if isinstance(appid, str):
        texto = appid.strip()
        pela_classe = steam_appid_from_wm_class(texto)
        if pela_classe is not None:
            return pela_classe
        return int(texto) if texto.isdigit() and int(texto) > 0 else None
    return None


def perfil_do_appid(
    appid: object, *, profiles: list[Profile] | None = None
) -> Profile | None:
    """O perfil que é a regra deste appid, ou None."""
    alvo = _chave_do_appid(appid)
    if alvo is None:
        return None
    candidatos = [
        p
        for p in (profiles if profiles is not None else load_all_profiles())
        if alvo in _appids_do_perfil(p)
    ]
    if not candidatos:
        return None
    return max(
        candidatos,
        key=lambda p: (p.ponte is not None, p.priority, p.name),
    )


def ponte_confirmada_do_appid(
    appid: object, *, profiles: list[Profile] | None = None
) -> PonteConfirmada | None:
    """A ponte confirmada deste appid, ou None = **ainda não sei**."""
    profile = perfil_do_appid(appid, profiles=profiles)
    return profile.ponte if profile is not None else None


def pontes_confirmadas(
    profiles: list[Profile] | None = None,
) -> dict[str, dict[str, object]]:
    """`{appid: ponte}` de tudo que já foi confirmado, pronto para o estado.

    É a forma PUBLICADA (item 4 da PONTE-CONFIRMADA-01): quem monta o
    `state_full` do IPC e quem arma o lançamento não precisam abrir perfil
    nenhum nem conhecer o formato do `match` — chamam isto e leem o dicionário.
    Chave `str` porque é JSON, como o resto do estado; valor no formato do
    `PonteConfirmada.model_dump(mode="json")`.

    Só entram os appids COM carimbo. Publicar `{"2054970": null}` para todo
    jogo sem confirmação seria enviar a biblioteca inteira a 10 Hz para dizer
    "não sei" — e "não sei" já é a ausência da chave.

    O empate é resolvido por `perfil_do_appid`, e a delegação é o ponto: uma
    varredura própria aqui responderia pela ORDEM DE CARGA dos arquivos, e a
    janela passaria a mostrar uma ponte enquanto o launch armava outra para o
    mesmo jogo — divergência entre duas leituras da mesma casa, que é o defeito
    que esta frente existe para fechar. Os perfis são lidos UMA vez e passados
    adiante: a resposta é a mesma e o disco é tocado uma vez só.
    """
    todos = list(profiles if profiles is not None else load_all_profiles())
    com_carimbo = {
        appid
        for profile in todos
        if profile.ponte is not None
        for appid in _appids_do_perfil(profile)
    }
    saida: dict[str, dict[str, object]] = {}
    for appid in sorted(com_carimbo):
        ponte = ponte_confirmada_do_appid(appid, profiles=todos)
        if ponte is not None:
            saida[str(appid)] = ponte.model_dump(mode="json")
    return saida


def _a_escolha_dela_ja_carimbou(
    profile: Profile, kind: str, gamepad_flavor: object, steam_input: bool
) -> bool:
    """O perfil já tem ESTA ponte carimbada pela escolha do usuário?

    O-CARIMBO-DA-PONTE-SEGUE-A-ESCOLHA-DELA-01: a escada pede o carimbo da
    ponte de pé depois do silêncio, `por=silencio` ou `por=gesto`. Quando a
    escolha do usuário já carimbou a MESMA ponte (o PS + R3 carimba na hora e deixa o
    gesto anotado, que o tique colhe 180 s depois), o carimbo dela fica: a
    escada não rebaixa a escolha. Outra ponte de pé, a escada carimba como
    sempre.
    """
    atual = profile.ponte
    if atual is None or atual.confirmada_por != CONFIRMADA_POR_ESCOLHA:
        return False
    pedida = carimbar_ponte(
        profile, kind=kind, gamepad_flavor=gamepad_flavor, steam_input=steam_input
    ).ponte
    return pedida is not None and _mesma_ponte_carimbada(atual, pedida)


def carimbar_ponte(
    profile: Profile,
    *,
    kind: str,
    gamepad_flavor: object = None,
    steam_input: bool = False,
    por: str = CONFIRMADA_POR_GESTO,
    quando: str | None = None,
) -> Profile:
    """Devolve uma CÓPIA do perfil com a ponte carimbada. Não grava."""
    flavor = normalizar_gamepad_flavor(gamepad_flavor) if kind == "gamepad" else None
    dados: dict[str, object] = {
        "kind": kind,
        "gamepad_flavor": flavor,
        "steam_input": bool(steam_input),
        "confirmada_por": por,
    }
    if quando is not None:
        dados["confirmada_em"] = quando
    return profile.model_copy(update={"ponte": PonteConfirmada(**dados)})  # type: ignore[arg-type]


def alinhar_o_modo_com_a_ponte(
    profile: Profile, *, kind: str, caminho: object = None
) -> Profile:
    """Devolve uma CÓPIA do perfil com o `mode` igual à ponte de pé. Não grava."""
    secao = secao_do_modo_com_o_caminho(profile.mode, kind=kind, caminho=caminho)
    return profile.model_copy(update={"mode": secao})


def secao_do_modo_com_o_caminho(
    atual: ProfileModeConfig | None, *, kind: str, caminho: object = None
) -> ProfileModeConfig:
    """A seção `mode` depois de o MODO mudar — o ESCRITOR ÚNICO do caminho."""
    from hefesto_dualsense4unix.integrations.virtual_pad import normalizar_caminho

    campos: dict[str, object] = {} if atual is None else atual.model_dump()
    campos["kind"] = kind
    if kind == "gamepad":
        escolhido = normalizar_caminho(caminho)
        if escolhido is not None:
            campos["caminho"] = escolhido
    else:
        campos["caminho"] = None
    return ProfileModeConfig(**campos)  # type: ignore[arg-type]


def nome_do_perfil_que_grava(do_daemon: object) -> str | None:
    """Em que perfil uma escolha do MOMENTO vai ser gravada — `None` quando nenhum."""
    if isinstance(do_daemon, str) and do_daemon:
        return do_daemon
    try:
        from hefesto_dualsense4unix.profiles.loader import load_profile as _carregar
        from hefesto_dualsense4unix.utils.session import resolve_boot_profile

        do_disco = resolve_boot_profile()
        if not isinstance(do_disco, str) or not do_disco:
            return None
        _carregar(do_disco)
    except Exception as exc:
        logger.debug("perfil_que_grava_sem_perna_de_disco", err=str(exc))
        return None
    return do_disco


def secao_do_mouse_da_navegacao(
    atual: ProfileMouseConfig | None,
    *,
    ligado: bool,
    velocidades: tuple[int, int] | None = None,
) -> ProfileMouseConfig:
    """A seção `mouse` depois de a Navegação ligar ou desligar o mouse — o dono.

    O-MOUSE-SEGUE-A-NAVEGACAO-01 (29/09/2026). Dois chamadores, uma regra: a
    entrada à mão na Navegação (que grava ``enabled: true`` junto com o modo,
    :func:`gravar_o_modo_no_perfil_ativo`) e o «Status do Modo» da aba
    Navegação (:func:`gravar_a_navegacao_no_perfil_ativo`). Só o ``enabled``
    muda; as velocidades que a seção já tinha FICAM (quem as escreve são as
    duas barras da aba). O perfil sem a seção ganha uma com as velocidades
    VIVAS (``velocidades``), que são as que o mouse está usando: a mesma
    leitura que a janela fazia (`a06_navegacao._secao_do_mouse`). Sem elas,
    as do esquema.

    RECONSTRUÍDA, e não `model_copy`ada, pela razão de
    :func:`secao_do_modo_com_o_caminho`: o pydantic v2 não revalida no
    `model_copy`.
    """
    if atual is not None:
        campos: dict[str, object] = atual.model_dump()
    elif velocidades is not None:
        campos = _velocidades_que_nao_sao_do_computador(velocidades)
    else:
        campos = {}
    campos["enabled"] = bool(ligado)
    return ProfileMouseConfig(**campos)  # type: ignore[arg-type]


def _velocidades_que_nao_sao_do_computador(
    velocidades: tuple[int, int],
) -> dict[str, object]:
    """As velocidades vivas que a seção nova leva: só as que o computador não guarda."""
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
        velocidades_do_computador,
    )

    do_computador = velocidades_do_computador()
    return {
        campo: viva
        for campo, viva, do_pc in zip(
            ("speed", "scroll_speed"), velocidades, do_computador, strict=True)
        if do_pc is None
    }


def gravar_o_modo_no_perfil_ativo(
    nome: str | None,
    *,
    kind: str,
    caminho: object = None,
    porta: str,
    mouse_ligado: bool | None = None,
    velocidades: tuple[int, int] | None = None,
    appid_do_jogo: object = None,
    steam_input: bool = False,
) -> Profile | None:
    """O modo escolhido vai ao perfil ATIVO, na hora. None = não gravou.

    MODO-DE-CONEXAO-01, §D.4 (13/09/2026), pela  Até aqui o gesto só deixava rastro
    depois de 180 s de jogo aberto, e no perfil do JOGO; agora ele grava no
    perfil que está valendo logo que o aparelho confirma, sem esperar e sem
    precisar de jogo.

    UM CHAMADOR SÓ — O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01 (29/09/2026):
    `Daemon.gravar_o_modo_escolhido`, que os três setters do modo chamam
    depois do aparelho. O chip da aba Jogar gravava pela janela, e só com a
    resposta no prazo; o PS + R3 gravava por aqui, com `origem="ps_r3"` fixo,
    e o diário dizia PS + R3 sobre um clique. Agora a `porta` (``"ipc"`` ou
    ``"controle"``) vai ao `profile_salvo` e à linha
    `modo_escolhido_gravado_no_perfil`.

    `mouse_ligado` (O-MOUSE-SEGUE-A-NAVEGACAO-01, 29/09/2026): a entrada à mão
    na Navegação grava, NA MESMA GRAVAÇÃO, o ``mouse.enabled`` que ela deixou
    de pé (:func:`secao_do_mouse_da_navegacao`); ``None`` não toca a seção.

    `appid_do_jogo` e `steam_input` (O-CARIMBO-DA-PONTE-SEGUE-A-ESCOLHA-DELA-01,
    03/10/2026): o jogo que o wrapper lançou e que ainda roda, e se ele está na
    allowlist do Steam Input. Quando o perfil que grava é a regra DESSE jogo, o
    carimbo vai na mesma gravação, `por=escolha_dela`
    (:func:`_carimbo_da_escolha`): a escolha do usuário é confirmação da ponte naquele
    jogo. Sem isto, o modo mudava e o carimbo ficava na ponte de antes, e o
    serviço avisava `ponte_confirmada_diverge_do_perfil` sobre a escolha do usuário
    (Pro Jank Footy, 01/10, 19h17). Fora de jogo, ou com o Freestyle valendo,
    nada de carimbo: ele é «confirmada NESTE jogo».

    NADA MUDOU, NADA SE GRAVA: o `.json` dela não ganha uma versão idêntica a
    cada aperto repetido.
    """
    if not nome:
        return None
    profile = load_profile(nome)
    antes = profile.mode
    depois = secao_do_modo_com_o_caminho(antes, kind=kind, caminho=caminho)
    mudou: dict[str, Any] = {}
    if antes is None or antes.model_dump() != depois.model_dump():
        mudou["mode"] = depois
    carimbo = _carimbo_da_escolha(
        profile, depois, appid_do_jogo=appid_do_jogo, steam_input=steam_input
    )
    if carimbo is not None:
        mudou["ponte"] = carimbo
    if mouse_ligado is not None:
        mouse = secao_do_mouse_da_navegacao(
            profile.mouse,
            ligado=mouse_ligado,
            velocidades=velocidades,
        )
        if profile.mouse is None or profile.mouse.model_dump() != mouse.model_dump():
            mudou["mouse"] = mouse
    if not mudou:
        return profile
    novo = profile.model_copy(update=mudou)
    save_profile(novo, origem=porta)
    logger.info(
        "modo_escolhido_gravado_no_perfil",
        profile=novo.name,
        kind=kind,
        caminho=depois.caminho,
        porta=porta,
        **({"mouse_enabled": mudou["mouse"].enabled} if "mouse" in mudou else {}),
        **({"ponte_confirmada_por": carimbo.confirmada_por} if carimbo else {}),
    )
    return novo


def _carimbo_da_escolha(
    profile: Profile,
    modo: ProfileModeConfig,
    *,
    appid_do_jogo: object,
    steam_input: bool,
) -> PonteConfirmada | None:
    """O carimbo `escolha_dela` que a escolha do modo leva, ou None quando nenhum.

    None em três casos: não há jogo do wrapper vivo; o perfil que grava não é a
    regra desse jogo (o Freestyle, ou o perfil escolhido fora dele); o carimbo
    de hoje já é este, pela escolha do usuário. O gamepad sem caminho declarado não
    carimba: a ponte dele é a máscara do aparelho, que este escritor não lê, e
    carimbar `gamepad` sem o canal diria «confirmada» sobre o que ninguém
    escolheu.
    """
    if appid_do_jogo is None:
        return None
    do_jogo = perfil_do_appid(appid_do_jogo)
    if do_jogo is None or do_jogo.name != profile.name:
        return None
    if modo.kind == "gamepad" and modo.caminho is None:
        return None
    novo = carimbar_ponte(
        profile,
        kind=modo.kind,
        gamepad_flavor=modo.caminho,
        steam_input=steam_input,
        por=CONFIRMADA_POR_ESCOLHA,
    ).ponte
    atual = profile.ponte
    if (
        novo is not None
        and atual is not None
        and atual.confirmada_por == CONFIRMADA_POR_ESCOLHA
        and _mesma_ponte_carimbada(atual, novo)
    ):
        return None
    return novo


def _mesma_ponte_carimbada(a: PonteConfirmada, b: PonteConfirmada) -> bool:
    """Os dois carimbos dizem a mesma ponte (`kind`, canal, Steam Input)?"""
    return (a.kind, a.gamepad_flavor, a.steam_input) == (
        b.kind, b.gamepad_flavor, b.steam_input)


def gravar_a_navegacao_no_perfil_ativo(
    nome: str | None,
    *,
    ligado: bool,
    porta: str,
    velocidades: tuple[int, int] | None = None,
) -> Profile | None:
    """O «Status do Modo» vai ao perfil ATIVO: ``mouse.enabled`` e ``teclado_emulado``."""
    if not nome:
        return None
    profile = load_profile(nome)
    mouse = secao_do_mouse_da_navegacao(
        profile.mouse, ligado=ligado, velocidades=velocidades
    )
    mudou: dict[str, Any] = {}
    if profile.mouse is None or profile.mouse.model_dump() != mouse.model_dump():
        mudou["mouse"] = mouse
    # O TECLADO É DO COMPUTADOR (O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01):
    # vai ao perfil só quando ele já sobrepõe o cartão do teclado; nos outros
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc

    if opc.onde_grava("teclado", profile) == opc.JOGO:
        if profile.teclado_emulado is not bool(ligado):
            mudou["teclado_emulado"] = bool(ligado)
    elif opc.o_computador().global_.teclado_emulado is not bool(ligado):
        opc.gravar("teclado", {"teclado_emulado": bool(ligado)}, perfil_ativo=nome,
                   origem=porta)
    if not mudou:
        return profile
    novo = profile.model_copy(update=mudou)
    save_profile(novo, origem=porta)
    logger.info(
        "status_da_navegacao_gravado_no_perfil",
        profile=novo.name,
        ligado=bool(ligado),
        porta=porta,
        secoes=sorted(mudou),
    )
    return novo


def chave_de_peca_que_grava(alvo: str) -> str | None:
    """A chave sob a qual é SEGURO gravar a escolha de UMA peça, ou `None`."""
    from hefesto_dualsense4unix.broker.hidraw_broker import VPAD_UNIQ_PREFIX
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    chave = norm_mac(alvo)
    if not chave or len(chave) != 12:
        return None
    if chave.startswith(VPAD_UNIQ_PREFIX):
        return None
    return chave


def gravar_a_mascara_no_perfil_ativo(
    nome: str | None, *, chave: str | None, mascara: str | None
) -> tuple[str | None, bool, str | None]:
    """A máscara de UMA peça no perfil ATIVO — a irmã de `gravar_o_modo_no_perfil_ativo`."""
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    if not chave:
        return None, False, "sem_endereco"
    if not nome:
        return None, False, "sem_perfil"
    perfil = load_profile(nome)
    atuais = dict(perfil.controllers or {})
    dele = atuais.get(chave) or ControllerOverrides()
    if getattr(dele, "mascara", None) == mascara:
        return nome, False, "sem_mudanca"
    novo = dele.model_copy(update={"mascara": mascara})
    if all(
        getattr(novo, campo, None) is None for campo in ControllerOverrides.model_fields
    ):
        atuais.pop(chave, None)
    else:
        atuais[chave] = novo
    save_profile(perfil.model_copy(update={"controllers": atuais or None}))
    logger.info(
        "gamepad_mascara_gravada_no_perfil", uniq=chave, perfil=nome, mascara=mascara
    )
    return nome, True, None


def _estado_da_secao(valor: object) -> str:
    """Normaliza o retorno de um applier de perfil (R-03)."""
    return valor if isinstance(valor, str) else "aplicado"


def resolve_key_bindings(
    raw: dict[str, list[str]] | None,
) -> dict[str, KeyBinding]:
    """Resolve um mapping CRU de key_bindings (button→tokens) para o device.

    Mesmas regras de `_to_key_bindings`, mas recebe o mapping cru em vez de um
    `Profile` — para empurrar os bindings editados na aba Teclado ao device vivo sem
    reativar o perfil do disco (BUG-FOOTER-APPLY-IGNORA-KEYBINDINGS-01).

    Regras (FEAT-KEYBOARD-PERSISTENCE-01):
    - `None` → herda `DEFAULT_BUTTON_BINDINGS` completo.
    - `{}` → vazio (teclado silencioso; usuário removeu todos os bindings).
    - dict parcial → override isolado; **não mescla com defaults**.
    """
    if raw is None:
        return dict(DEFAULT_BUTTON_BINDINGS)
    return {button: tuple(tokens) for button, tokens in raw.items()}


def _to_key_bindings(profile: Profile) -> dict[str, KeyBinding]:
    """Resolve `Profile.key_bindings` em mapping pronto para o device."""
    return resolve_key_bindings(profile.key_bindings)


def _controllers_to_specs(
    controllers: dict[str, ControllerOverrides] | None,
    global_leds: LedsConfig | None = None,
) -> dict[str, OutputSpec]:
    """Converte o mapa `controllers` do perfil em `OutputSpec` por MAC."""
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
        brilho_das_luzes: int | None = None
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
                led = (
                    None
                    if cor_escolhida(rgb) is None
                    else settings.apply_brightness(settings.brightness_level).lightbar
                )
            if "player_leds" in campos:
                player_leds = _to_led_settings(cfg.leds).player_leds
            if "player_led_brightness" in campos:
                brilho_das_luzes = degrau_do_brilho_das_luzes(
                    cfg.leds.player_led_brightness
                )
        if (
            trigger_left is None
            and trigger_right is None
            and led is None
            and player_leds is None
            and brilho_das_luzes is None
        ):
            continue
        out[uniq] = OutputSpec(
            trigger_left=trigger_left,
            trigger_right=trigger_right,
            led=led,
            player_leds=player_leds,
            player_led_brightness=brilho_das_luzes,
        )
    return out


def _controllers_na_economia(
    controllers: dict[str, ControllerOverrides] | None,
    profile: Profile,
    mesa: bool,
    em_economia: frozenset[str] = frozenset(),
) -> dict[str, ControllerOverrides]:
    """O mapa por controle com a economia posta em quem ela vale."""
    herdar = not mesa
    rumble = getattr(profile, "rumble", None)
    politica = getattr(rumble, "policy", None)
    custom = getattr(rumble, "custom_mult", None)
    todos: dict[str, ControllerOverrides] = dict(controllers or {})
    for uniq in sorted(em_economia):
        todos.setdefault(uniq, ControllerOverrides())
    out: dict[str, ControllerOverrides] = {}
    for uniq, cfg in todos.items():
        if not economia_vale(uniq in em_economia, mesa):
            out[uniq] = cfg
            continue
        out[uniq] = cfg.model_copy(
            update={
                "leds": leds_na_economia(
                    cfg.leds, profile.leds if herdar else None
                ),
                "triggers": gatilhos_na_economia(
                    cfg.triggers, profile.triggers if herdar else None
                ),
                "rumble": vibracao_na_economia(
                    cfg.rumble, politica, custom, mesa=mesa
                ),
            }
        )
    return out


def _perfil_na_economia(
    profile: Profile,
    mesa: bool,
    em_economia: frozenset[str] = frozenset(),
) -> Profile:
    """A VISTA do perfil que vai ao aparelho, com a economia posta."""
    if not mesa and not em_economia:
        return profile
    update: dict[str, Any] = {
        "controllers": _controllers_na_economia(
            profile.controllers, profile, mesa, em_economia
        ),
    }
    if mesa:
        update["leds"] = leds_do_perfil_na_economia(profile.leds)
        update["triggers"] = gatilhos_do_perfil_na_economia(profile.triggers)
    return profile.model_copy(update=update)


def _controllers_to_procedencias(
    controllers: dict[str, ControllerOverrides] | None,
) -> dict[str, object]:
    """PARA QUAL NÚMERO cada cor do perfil foi escolhida (`{uniq: procedência}`)."""
    out: dict[str, object] = {}
    for uniq, cfg in (controllers or {}).items():
        if cfg.leds is None or "lightbar" not in cfg.leds.model_fields_set:
            continue
        numero = cfg.leds.lightbar_para_o_numero
        out[uniq] = LEGADO if numero is None else int(numero)
    return out


def _publicar_camada(
    publicar: Any,
    overrides: dict[str, OutputSpec],
    procedencias: dict[str, object],
) -> None:
    """Publica a camada de overrides levando a procedência, quando ela cabe."""
    try:
        publicar(overrides or None, procedencias=procedencias or None)
    except TypeError:
        publicar(overrides or None)


def _aplicar_com_procedencia(
    aplicar: Any, uniq: str, spec: OutputSpec, procedencia: object
) -> None:
    """`apply_output_for` com o carimbo, e a MESMA queda do `_publicar_camada`."""
    try:
        aplicar(uniq, spec, procedencia_da_cor=procedencia)
    except TypeError:
        aplicar(uniq, spec)


def _brilho_materializa_cor(
    cfg: ControllerOverrides, global_leds: LedsConfig | None
) -> bool:
    """True quando o brilho por-controle ainda precisa virar cor (R-20 item 2).

    Só no caso degenerado: a escala relativa é `brilho_do_controle /
    brilho_global`, e com brilho global 0 (ou sem seção global para comparar)
    a cor resolvida JÁ é preta — não há o que escalar de volta. Aí materializar
    é a única forma honesta de honrar o pedido, e o custo (perder a cor
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

    Devolve `{uniq: fator}` para todo override que escreveu
    `lightbar_brightness`. O fator é RELATIVO ao brilho global —
    `brilho_do_controle / brilho_global` — porque a cor que ele escala (o
    global do perfil ou a paleta automática do slot) já vem escalada pelo
    global; multiplicar de novo pelo absoluto escureceria duas vezes.

    O BACKEND O APLICA SÓ NA BASE, nunca no override (`_scaled_led`), e por
    isso o override que também escreveu a COR entra aqui desde 25/09/2026
    (A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01): a cor dele já saiu escalada da
    borda e o fator não a toca, mas a base dele é a cor do número, e é para
    ela que o controle volta quando a cor gravada é fóssil ou é o preto, que
    não é cor. Sem o fator, o fóssil do P2 a 50% voltava à cor do número no
    brilho do perfil, e o preto gravado com 30% acendia a paleta a 82%.

    Fator 1.0 não entra — é "sem opinião", e uma entrada inócua no mapa só
    custaria uma cópia de `_DesiredOutput` a cada resolução.
    """
    out: dict[str, float] = {}
    if global_leds is None:
        return out
    base = float(global_leds.lightbar_brightness)
    if base <= 0.0:
        return out
    for uniq, cfg in (controllers or {}).items():
        if cfg.leds is None:
            continue
        if "lightbar_brightness" not in cfg.leds.model_fields_set:
            continue
        fator = float(cfg.leds.lightbar_brightness) / base
        if fator == 1.0:
            continue
        out[uniq] = fator
    return out


#: Política de intensidade que o daemon assume quando NINGUÉM opinou — o
#: default de `DaemonConfig.rumble_policy`. É o denominador honesto do fator
#: por unidade num perfil sem seção `rumble.policy` própria: sem opinião
#: global, o que o hardware recebe é o "balanceado" do daemon.
_RUMBLE_POLICY_PADRAO = "balanceado"

#: O volume do alto-falante em «Padrão» (04/10/2026): os 100% de sempre, que o controle já ganha na
#: adoção (`backend_pydualsense.VOLUME_PADRAO_DO_SOM`); o jogo decide o quanto toca.
VOLUME_DO_PADRAO = volume_do_percentual(100)


def _mult_da_politica(policy: str | None, custom_mult: float | None) -> float | None:
    """Multiplicador de uma política FIXA de rumble, ou None se não há.

    Fonte única: a MESMA tabela `RUMBLE_POLICY_MULT` que o daemon usa
    (`daemon.subsystems.rumble`), com import lazy — `profiles/` não importa
    `daemon/` no topo. `auto` devolve None de propósito: ele não é um número,
    é uma função da bateria (ver `ControllerRumbleOverride`).
    """
    if policy is None:
        return None
    if policy == "custom":
        return None if custom_mult is None else float(custom_mult)
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    return RUMBLE_POLICY_MULT.get(policy)


def fator_da_unidade(
    policy_da_peca: str | None,
    policy_global: str | None,
    custom_da_peca: float | None = None,
    custom_global: float | None = None,
) -> float | None:
    """O fator RELATIVO que uma peça registra contra o global do PERFIL.

    É o corpo da conta de :func:`_controllers_to_rumble_scales`, extraído em
    01/09/2026 porque a TELA precisava do mesmo número para dizer o que chega ao
    motor (`interface.conexoes.forca_no_motor`). Enquanto ele estivesse só dentro
    do laço, a tela teria de reescrevê-lo — e o `?` da aba Conexões passou uma
    leva inteira afirmando "o global vale Sem teto" justamente por não ter de
    onde ler este denominador.

    ``None`` = não dá para calcular: política fora da tabela, ou base móvel (o
    global em ``auto``, cujo degrau muda com a bateria a cada tique). O
    denominador é a política do PRÓPRIO perfil quando ele tem uma; sem opinião,
    é o ``balanceado`` que o daemon assume.

    **NÃO é o que chega ao motor**: o valor que sai daqui multiplica o que a
    política VIVA do daemon já deixou passar (`core.rumble.forca_do_global`).
    Os dois "globais" são coisas diferentes, e confundi-los é o defeito que esta
    função existe para não deixar repetir.
    """
    base = _mult_da_politica(policy_global or _RUMBLE_POLICY_PADRAO, custom_global)
    if base is None or base <= 0.0:
        return None
    mult = _mult_da_politica(policy_da_peca, custom_da_peca)
    return None if mult is None else mult / base


def _controllers_to_rumble_scales(
    controllers: dict[str, ControllerOverrides] | None,
    global_rumble: Any | None = None,
) -> dict[str, float]:
    """Escala de VIBRAÇÃO por controle do perfil (POR-UNIDADE-01, 10/08/2026)."""
    out: dict[str, float] = {}
    policy_global = getattr(global_rumble, "policy", None) or _RUMBLE_POLICY_PADRAO
    custom_global = getattr(global_rumble, "custom_mult", None)
    base = _mult_da_politica(policy_global, custom_global)
    for uniq, cfg in (controllers or {}).items():
        if cfg.rumble is None:
            continue
        campos = cfg.rumble.model_fields_set
        if "policy" not in campos:
            continue
        if _mult_da_politica(cfg.rumble.policy, cfg.rumble.custom_mult) is None:
            continue
        if base is None or base <= 0.0:
            logger.info(
                "escala_de_vibracao_pulada_base_movel",
                uniq=uniq,
                policy_global=policy_global,
            )
            continue
        fator = fator_da_unidade(
            cfg.rumble.policy, policy_global, cfg.rumble.custom_mult, custom_global
        )
        if fator is None or fator == 1.0:
            continue
        out[uniq] = fator
    return out


def _to_led_settings(leds: LedsConfig) -> LedSettings:
    """Converte `LedsConfig` (schema de perfil) em `LedSettings` (camada de hardware)."""
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


APPLIERS_DO_DAEMON: tuple[tuple[str, str], ...] = (
    ("mouse_applier", "apply_profile_mouse"),
    ("suppression_applier", "apply_profile_suppression"),
    ("mode_applier", "apply_profile_mode"),
    ("rumble_policy_applier", "apply_profile_rumble_policy"),
    ("rumble_passthrough_applier", "apply_profile_rumble_passthrough"),
    ("speaker_applier", "apply_profile_speaker"),
    ("mic_applier", "apply_profile_mic"),
)


#: *"falta `rumble_passthrough_applier`"* — que é o nome do parâmetro, não o
SECAO_DO_APPLIER: dict[str, str] = {
    "mouse_applier": "mouse",
    "suppression_applier": "suppress_desktop_emulation",
    "mode_applier": "mode",
    "rumble_policy_applier": "rumble.policy",
    "rumble_passthrough_applier": "rumble.passthrough",
    "speaker_applier": "speaker",
    "mic_applier": "mic",
}


HERDA_DO_DAEMON: Any = object()


def _canal_do_ps(daemon: Any) -> Callable[[str | None], None]:
    """O `lambda` que leva a escolha do PS ao subsistema que atende o `ps_solo`."""

    def _empurra(token: str | None) -> None:
        if daemon is None:
            return
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import definir_acao_do_ps

        definir_acao_do_ps(daemon, token)

    return _empurra


def gerente_do_daemon(
    daemon: Any,
    *,
    controller: Any = None,
    store: Any = None,
    mode_applier: Any = HERDA_DO_DAEMON,
) -> ProfileManager:
    """O ``ProfileManager`` COMPLETO de uma rota do daemon — uma fonte só."""
    argumentos: dict[str, Any] = {
        "controller": controller if controller is not None else daemon.controller,
        "keyboard_device_provider": lambda: getattr(daemon, "_keyboard_device", None),
        # `button_actions` do perfil existiria, gravaria e nunca acenderia nada
        "mouse_device_provider": lambda: getattr(daemon, "_mouse_device", None),
        # manager, e sem esta linha o `button_actions["ps"]` seria gravado,
        "ps_action_sink": _canal_do_ps(daemon),
    }
    if store is not None:
        argumentos["store"] = store
    for parametro, atributo in APPLIERS_DO_DAEMON:
        argumentos[parametro] = getattr(daemon, atributo, None)
    if mode_applier is not HERDA_DO_DAEMON:
        argumentos["mode_applier"] = mode_applier
    _avisa_secoes_sem_applier(
        argumentos,
        declarados=(
            () if mode_applier is HERDA_DO_DAEMON else ("mode_applier",)
        ),
    )
    return ProfileManager(**argumentos)


def _controllers_to_miras(
    controllers: dict[str, Any] | None,
    movimento_do_perfil: Any,
    *,
    relatorio: dict[str, str] | None = None,
) -> dict[str, Any]:
    """A mira por movimento de CADA peça que tem opinião — `{chave: arranjo}`."""
    from hefesto_dualsense4unix.core.roteador_de_movimento import (
        ArranjoRecusadoError,
        arranjo_da_peca,
    )

    mapa: dict[str, Any] = {}
    for uniq, cfg in (controllers or {}).items():
        secao = getattr(cfg, "movimento", None)
        if secao is None:
            continue
        try:
            mapa[str(uniq)] = arranjo_da_peca(movimento_do_perfil, secao)
        except ArranjoRecusadoError as exc:
            logger.warning("movimento_da_peca_recusado", uniq=str(uniq), err=str(exc))
            mapa[str(uniq)] = None
            if relatorio is not None:
                relatorio[f"movimento:{uniq}"] = "falhou"
    return mapa


def _avisa_secoes_sem_applier(
    argumentos: dict[str, Any],
    *,
    declarados: tuple[str, ...] = (),
) -> list[str]:
    """Faz BARULHO quando a fábrica monta um gerente PELA METADE (BG-07).

    O defeito desta família, em uma linha: **applier ausente não levanta — a
    seção é ignorada em silêncio**. A rota nasce funcionando "quase", o "quase"
    só aparece no aparelho do usuário, e o journal não guarda uma linha sequer sobre
    a seção que não foi aplicada. Foi assim que a saída do Modo Nativo passou
    de 05/08 a 25/08 devolvendo tudo menos a vibração.

    QUANDO ELE FALA, e o critério é a FORMA do defeito, não a contagem:

    - o daemon entregou TODOS → silêncio. É a rota sã;
    - o daemon não entregou NENHUM → silêncio, e não é descuido. É contrato
      escrito no docstring de `gerente_do_daemon`: rotas de CLI e dublês da
      suíte sobem sem daemon (`daemon=None`, `controller`/`store` por fora),
      e ali "seção ignorada" é o comportamento histórico e desejado;
    - o daemon entregou ALGUNS → **é este o formato do defeito**, e o aviso
      nomeia as SEÇÕES órfãs, não os parâmetros: o que ela sente é
      `rumble.passthrough`, não `rumble_passthrough_applier`.

    ``declarados`` é a lista dos appliers que o CHAMADOR informou de propósito
    — hoje só o `mode_applier`, o único desvio nomeado da fábrica. `None` ali
    é escolha medida (ver o docstring de `gerente_do_daemon`), e chamar de
    ausência uma escolha explícita seria alarme falso — o defeito que esta casa
    mede desde a `O-PORTAO-QUE-NAO-MEDE-O-QUE-PROMETE`. Eles saem da conta
    inteira: nem contam como ausentes, nem como presentes.

    Devolve as seções órfãs (ordenadas) para quem quiser conferir sem ler log.
    """
    considerados = [
        parametro
        for parametro, _atributo in APPLIERS_DO_DAEMON
        if parametro not in declarados
    ]
    ausentes = [
        parametro for parametro in considerados if argumentos.get(parametro) is None
    ]
    orfas = sorted(
        SECAO_DO_APPLIER.get(parametro, parametro) for parametro in ausentes
    )
    if ausentes and len(ausentes) < len(considerados):
        logger.warning(
            "gerente_com_secao_sem_applier",
            secoes=orfas,
            appliers=sorted(ausentes),
        )
    return orfas


__all__ = [
    "APPLIERS_DO_DAEMON",
    "HERDA_DO_DAEMON",
    "MOTIVO_JOGO_SEM_PERFIL_PROPRIO",
    "MOTIVO_SELECIONADO",
    "MOTIVO_SEM_CANDIDATO",
    "SECAO_DO_APPLIER",
    "OFreestyleMandaError",
    "ProfileManager",
    "_controllers_to_led_scales",
    "_controllers_to_procedencias",
    "_controllers_to_specs",
    "_estado_da_secao",
    "_to_key_bindings",
    "_to_led_settings",
    "e_o_freestyle",
    "gerente_do_daemon",
    "ligar_o_freestyle",
    "o_freestyle_manda",
    "os_perfis_de_escolher",
    "resolve_key_bindings",
]
