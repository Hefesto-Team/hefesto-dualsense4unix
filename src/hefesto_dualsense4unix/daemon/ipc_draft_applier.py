"""DraftApplier — aplica `profile.apply_draft` em ordem canônica.

Extraído de `_handle_profile_apply_draft` em AUDIT-FINDING-IPC-SERVER-SPLIT-01.
Cada seção (leds, triggers, controllers, rumble, mouse, keyboard, mic, speaker)
é aplicada de forma best-effort: falha em uma seção loga warning, fica registrada
em ``failed`` (APLICAR-VERDADE-01) e não bloqueia as demais. A ordem é leds
-> triggers -> controllers -> rumble -> mouse -> keyboard -> mic -> speaker
(leds primeiro por ser menos transiente visualmente; controllers DEPOIS das
seções globais para o override por-controle vencer no alvo — PERFIL-04).

ESTA LISTA É A PROMESSA DO BOTÃO VERDE, e ela ficou desatualizada duas vezes
antes de alguém notar: o `mic` entrou pela MIC-EXPOSE-01 sem ser citado aqui, e
o `speaker` faltava por inteiro até 10/08/2026 — `grep -c speaker` neste arquivo
devolvia ZERO, e o volume que ela ajustava no card só chegava ao controle na
próxima troca de perfil. Há portão que compara esta lista com o que o rascunho
emite; se as duas divergirem, ele reprova
(`tests/unit/test_o_verde_leva_tudo_01.py`).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core.controller import OutputSpec, TriggerEffect
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.daemon.ipc_rumble_policy import (
    apply_rumble_policy,
    uniq_do_alvo_de_output,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.core.controller import IController
    from hefesto_dualsense4unix.daemon.state_store import StateStore

logger = get_logger(__name__)


def _brilho_de(cru: Any) -> float | None:
    """O brilho 0,0-1,0 de um campo do rascunho, ou `None` quando não é número."""
    if cru is None or isinstance(cru, bool):
        return None
    try:
        return max(0.0, min(1.0, float(cru)))
    except (TypeError, ValueError):
        return None


class DraftApplier:
    """Aplica as seções de `profile.apply_draft` em ordem canônica."""

    def __init__(
        self,
        controller: IController,
        store: StateStore,
        daemon: Any,
    ) -> None:
        self.controller = controller
        self.store = store
        self.daemon = daemon
        # APLICAR-VERDADE-01: seção -> motivo curto das que NÃO entraram. O
        # best-effort continua igual (uma seção que falha não bloqueia as
        # outras), mas a falha para de morrer no warning do log: sobe junto
        # com `applied` para quem chamou poder dizer a verdade na tela.
        self.failed: dict[str, str] = {}
        #: O brilho global do rascunho em aplicação — o denominador dos fatores
        #: por controle (`_publicar_escalas_de_brilho`). `None` = sem seção `leds`.
        self._brilho_do_rascunho: float | None = None
        #: A cor global do rascunho, antes do brilho — o par do brilho acima,
        #: publicado com ele (`set_led_scales(cor_do_perfil=)`).
        self._cor_do_rascunho: Any = None
        #: Os controles em que a economia vale neste «Aplicar» — a camada deles
        #: é a do perfil, como na ativação (`_com_o_teto_da_economia`).
        self._em_economia: frozenset[str] = frozenset()
        #: O rascunho trouxe o mapa `controllers` (e não `None`): só então o
        #: mapa de overrides do daemon é trocado (Z4/T8).
        self._o_rascunho_tem_o_mapa = False
        #: A seção `controllers` da vista, para o «Todos» das luzes saber se vai cru.
        self._controles_do_rascunho: Any = None

    def apply(self, params: dict[str, Any]) -> list[str]:
        # ONDA-U (Causa A): trava manual INCONDICIONAL, no topo — antes vivia
        # só dentro de `_apply_triggers` (BUG-MOUSE-TRIGGERS-01), então um
        # "Aplicar no controle" sem a seção `triggers` (ex.: só `leds`, o
        # botão da aba Lightbar) não armava a trava; o `AutoSwitcher`
        # reativava o perfil salvo no próximo tick com troca de foco de
        # janela e apagava a edição recém-aplicada ("perfil eterno", U3/U4/
        # U9/U11). `apply_draft` É sempre edição manual explícita — arma
        # ANTES de aplicar, POR CATEGORIA das seções presentes (F1, auditoria
        # 21/07); payload sem seção mapeável (ex.: só `mouse`) arma as três,
        # preservando o incondicional da cura original.
        # O CARIMBO DE CATEGORIA SAIU — 14/09/2026,
        # `D-1409-A-TRAVA-MANUAL-SAI-O-PERFIL-APLICA-TUDO`. Aqui o "Aplicar" da
        # janela traduzia as seções do rascunho em categorias de trava manual e
        # armava uma a uma, para o perfil reaplicado não pisar o que ela acabara
        # de aplicar. Nenhum caminho lê a trava desde a decisão dela, e a razão
        # está em `profiles/manager.apply`: o que ela aplica pela interface já
        # vai para o perfil, então o perfil é quem guarda o ajuste dela.
        applied: list[str] = []
        # Cada `apply` conta a história dele: zera o registro de falhas antes
        # de começar (o mesmo applier pode ser reusado).
        self.failed = {}
        # O TETO DA ECONOMIA ANTES DE TUDO — O-APLICAR-NAO-SOLTA-O-TETO-DO-CONTROLE-01
        # (26/09/2026). Daqui para baixo cada seção lê a VISTA com o teto posto,
        # como a ativação lê a dela; ver `_com_o_teto_da_economia`.
        self._o_rascunho_tem_o_mapa = isinstance(params.get("controllers"), dict)
        params = self._com_o_teto_da_economia(params)
        self._controles_do_rascunho = params.get("controllers")
        # O denominador dos fatores de brilho por controle: o brilho GLOBAL do
        # rascunho, lido da seção `leds` (ver `_publicar_escalas_de_brilho`).
        leds_raw = params.get("leds")
        self._brilho_do_rascunho = (
            _brilho_de(leds_raw.get("lightbar_brightness"))
            if isinstance(leds_raw, dict)
            else None
        )
        self._cor_do_rascunho = (
            leds_raw.get("lightbar_rgb") if isinstance(leds_raw, dict) else None
        )
        self._apply_section(applied, params.get("leds"), "leds", self._apply_leds)
        self._apply_section(applied, params.get("triggers"), "triggers", self._apply_triggers)
        # PERFIL-04: overrides por-controle DEPOIS das seções globais — o
        # override vence no alvo (mesma precedência da ativação de perfil).
        self._apply_section(
            applied, params.get("controllers"), "controllers", self._apply_controllers
        )
        self._apply_section(applied, params.get("rumble"), "rumble", self._apply_rumble)
        self._apply_section(applied, params.get("mouse"), "mouse", self._apply_mouse)
        self._apply_section(
            applied, params.get("keyboard"), "keyboard", self._apply_keyboard
        )
        # MIC-EXPOSE-01: seção `mic` (botão de mic  mute do sistema).
        self._apply_section(applied, params.get("mic"), "mic", self._apply_mic)
        # O-VERDE-NAO-LEVAVA-O-SOM-01 (10/08/2026): a seção `speaker` faltava
        # aqui, e a palavra é literal — `grep -c speaker` neste arquivo devolvia
        # ZERO. O botão verde "Aplicar" carregava gatilho, luz, rumble, mouse,
        # teclado e mic, e deixava o alto-falante do controle para trás.
        #
        # O volume, o mudo e o canal chegavam ao PERFIL (`to_profile`) e ao
        # hardware na ATIVAÇÃO do perfil (`apply_profile_speaker`, pela rota do
        # autoswitch), mas não no AGORA: ela mexia no card, clicava no verde, e
        # o som não mudava até trocar de perfil. É metade exata da queixa dela —
        # *"literalmente nenhuma feature ficou lá"*.
        #
        # Por último de propósito, como o mic: é a seção mais barata de refazer
        # se falhar, e nenhuma outra depende dela.
        self._apply_section(applied, params.get("speaker"), "speaker", self._apply_speaker)
        return applied

    def _apply_section(
        self,
        applied: list[str],
        raw: Any,
        section: str,
        fn: Any,
    ) -> None:
        if raw is None:
            return
        try:
            fn(raw)
            applied.append(section)
        except Exception as exc:
            logger.warning(f"apply_draft_{section}_falhou", erro=str(exc))
            # APLICAR-VERDADE-01: além do warning (que só a gente lê), a seção
            # entra em `self.failed`. Sem isto a resposta do handler dizia
            # apenas o que deu certo, e a GUI, sem nada que contradissesse o
            # `status: "ok"`, anunciava "Perfil aplicado ao controle." mesmo
            # com todas as seções fora. Motivo curto e cortado: serve de
            # diagnóstico, não é o texto que a usuária lê.
            motivo = str(exc) or type(exc).__name__
            self.failed[section] = motivo[:120]

    @staticmethod
    def _scaled_rgb_from(leds_raw: dict[str, Any]) -> tuple[int, int, int] | None:
        """RGB da seção de leds já escalado pelo brilho (0.0-1.0); None sem cor.

        É O caminho de escala do brilho no apply_draft — os overrides
        por-controle (PERFIL-04) passam por aqui também, em paridade com a
        seção global.
        """
        rgb_raw = leds_raw.get("lightbar_rgb")
        if rgb_raw is None:
            return None
        if not isinstance(rgb_raw, list) or len(rgb_raw) != 3:
            raise ValueError("leds.lightbar_rgb deve ser lista de 3 inteiros")
        brightness_raw = leds_raw.get("lightbar_brightness", 1.0)
        try:
            brightness = float(brightness_raw)
        except (TypeError, ValueError):
            brightness = 1.0
        brightness = max(0.0, min(1.0, brightness))
        return (
            max(0, min(255, int(rgb_raw[0] * brightness))),
            max(0, min(255, int(rgb_raw[1] * brightness))),
            max(0, min(255, int(rgb_raw[2] * brightness))),
        )

    @staticmethod
    def _player_bits_from(
        leds_raw: dict[str, Any],
    ) -> tuple[bool, bool, bool, bool, bool] | None:
        """5 flags de player-LEDs da seção de leds; None quando ausentes."""
        player_leds_raw = leds_raw.get("player_leds")
        if player_leds_raw is None:
            return None
        if not isinstance(player_leds_raw, list) or len(player_leds_raw) != 5:
            raise ValueError("leds.player_leds deve ser lista de 5 booleanos")
        return (
            bool(player_leds_raw[0]),
            bool(player_leds_raw[1]),
            bool(player_leds_raw[2]),
            bool(player_leds_raw[3]),
            bool(player_leds_raw[4]),
        )

    @staticmethod
    def _trigger_effect_from(side_raw: Any, label: str) -> TriggerEffect:
        """Valida um lado de triggers do payload e constrói o efeito."""
        if not isinstance(side_raw, dict):
            raise ValueError(f"{label} deve ser objeto")
        mode = side_raw.get("mode")
        trigger_params = side_raw.get("params", [])
        if not isinstance(mode, str):
            raise ValueError(f"{label}.mode deve ser string")
        if not isinstance(trigger_params, list):
            raise ValueError(f"{label}.params deve ser lista")
        return build_from_name(mode, trigger_params)

    def _apply_leds(self, leds_raw: Any) -> None:
        """Aplica a seção GLOBAL de leds do draft em TODOS os controles.

        Fix do review (2026-07-16, MED): via ``apply_output_defaults`` —
        broadcast REAL que ignora o seletor de alvo e grava o
        ``_desired_default`` (mesma medicina do `ProfileManager.apply`). Os
        setters clássicos respeitavam o seletor: com um alvo selecionado
        (o estado normal do fluxo de edição por-controle), o "Aplicar" do
        rodapé gravava a seção GLOBAL no override do alvo, o default nunca
        era atualizado e o replug de outro controle reassertava estado velho.

        COR-04: ``auto_player_colors`` viaja nesta seção — propagado ao
        registro de identidade ANTES do broadcast (mesma ordem da ativação
        de perfil: ``_configure_auto_player_colors`` primeiro), para os
        reasserts subsequentes já resolverem com o toggle novo. Payload sem
        a chave (GUI antiga) = sem opinião — o estado vigente fica.
        """
        if not isinstance(leds_raw, dict):
            raise ValueError("leds deve ser objeto")
        self._configure_auto_colors(leds_raw)
        rgb = self._scaled_rgb_from(leds_raw)
        bits = self._player_bits_from(leds_raw)
        luzes = self._o_todos_das_luzes(leds_raw)
        if rgb is not None or bits is not None or luzes is not None:
            self.controller.apply_output_defaults(
                OutputSpec(led=rgb, player_leds=bits, player_led_brightness=luzes)
            )
        # COR-03 (fix de integração, 2026-07-17): converge o estado físico ao
        # RESOLVIDO por-controle após o toggle/broadcast — sem isto, religar
        # as cores automáticas pelo "Aplicar" só surtiria efeito no próximo
        # replug (e o D4 "a cor única aparece em todos" já dependia do
        # broadcast acima). Getattr defensivo (fakes seguem sem o método).
        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()

    def _o_todos_das_luzes(self, leds_raw: dict[str, Any]) -> int | None:
        """O degrau do «Todos» das luzes de número, quando ele pode ir a todos.

        O-APLICAR-NAO-SOLTA-O-TETO-DO-CONTROLE-01 (26/09/2026). A palavra
        viaja na seção `leds` do rascunho; `None` sem ela (rascunho de outra
        versão), e aí o padrão da ativação fica.

        O `apply_output_defaults` leva o global CRU a todo handle, e não o
        resolvido de cada um (`backend_pydualsense`, a razão está lá). Com um
        controle que termina noutro degrau — a palavra dele, ou o Fraco da
        economia —, o global cru seria nele um QUADRO INTERMEDIÁRIO antes da
        palavra dele: medido na mesa de quatro com o global sempre cru, o P1
        no Forte passava por `[2, 0, 0]` (o Fraco do «Todos», depois o dele).
        Então o global só vai cru quando ninguém termina noutro degrau; senão
        o padrão fica o que a ativação do perfil ativo deixou — o mesmo global
        do disco, porque a tela só escreve a palavra por controle —, e cada
        controle recebe a sua pela seção `controllers`. O que sobra (um
        «Todos» mudado no disco sem ativação, com alguém noutro degrau) espera
        a próxima ativação: o backend não tem porta que grave o padrão sem o
        escrever cru, e ela não é desta posse.
        """
        palavra = leds_raw.get("player_led_brightness")
        if palavra is None:
            return None
        from hefesto_dualsense4unix.core.led_control import degrau_do_brilho_das_luzes

        degrau = degrau_do_brilho_das_luzes(str(palavra))
        controles = self._controles_do_rascunho
        for entrada in (controles if isinstance(controles, dict) else {}).values():
            leds = entrada.get("leds") if isinstance(entrada, dict) else None
            propria = leds.get("player_led_brightness") if isinstance(leds, dict) else None
            if propria is not None and str(propria) != str(palavra):
                return None
        return degrau

    @staticmethod
    def _configure_auto_colors(leds_raw: dict[str, Any]) -> None:
        """COR-04: propaga o toggle do automático ao registro de identidade.

        Espelho do ``ProfileManager._configure_auto_player_colors`` para o
        caminho ``profile.apply_draft`` (o "Aplicar" do rodapé e o botão
        "Aplicar no controle" em "Todos") — sem isto o toggle editado na GUI
        só valeria na PRÓXIMA ativação de perfil, e a semântica D4 ("a cor
        única aparece em todos") ficaria quebrada ao vivo. O brilho
        acompanha quando presente (a paleta automática respeita o brilho do
        perfil — D11). Best-effort na mesma medida do manager: falha de
        import/configure loga warning e NÃO derruba a aplicação da cor.
        """
        raw = leds_raw.get("auto_player_colors")
        if raw is None:
            return
        if not isinstance(raw, bool):
            raise ValueError("leds.auto_player_colors deve ser booleano")
        brightness: float | None = None
        brightness_raw = leds_raw.get("lightbar_brightness")
        if brightness_raw is not None:
            try:
                brightness = max(0.0, min(1.0, float(brightness_raw)))
            except (TypeError, ValueError):
                brightness = None
        try:
            from hefesto_dualsense4unix.daemon.subsystems.identity import (
                get_identity_registry,
            )

            get_identity_registry().configure(enabled=raw, brightness=brightness)
        except Exception as exc:
            logger.warning("apply_draft_auto_colors_falhou", erro=str(exc))

    def _apply_triggers(self, triggers_raw: Any) -> None:
        """Aplica a seção GLOBAL de gatilhos em TODOS os controles.

        Broadcast real via ``apply_output_defaults`` — mesma justificativa
        de ``_apply_leds`` (fix do review 2026-07-16, MED).
        """
        if not isinstance(triggers_raw, dict):
            raise ValueError("triggers deve ser objeto")
        effects: dict[str, TriggerEffect] = {}
        for side in ("left", "right"):
            side_raw = triggers_raw.get(side)
            if side_raw is None:
                continue
            effects[side] = self._trigger_effect_from(side_raw, f"triggers.{side}")
        if effects:
            self.controller.apply_output_defaults(
                OutputSpec(
                    trigger_left=effects.get("left"),
                    trigger_right=effects.get("right"),
                )
            )

    def _apply_controllers(self, raw: Any) -> None:
        """Aplica os overrides POR CONTROLE do draft (PERFIL-04).

        Cada entrada ``{uniq: {leds?, triggers?}}`` vira um ``OutputSpec``
        aplicado via ``apply_output_for`` — a API por-uniq do PERFIL-01
        (alvo no parâmetro, nunca o seletor global). O brilho escala o RGB
        pelo MESMO caminho da seção global (``_scaled_rgb_from``). Backend
        sem estado por-controle (FakeController) herda o no-op seguro do
        ``IController``; controle desconectado fica registrado no mapa em
        memória do backend real (o hotplug o aplica quando chegar).

        A seção presente SUBSTITUI o mapa inteiro de overrides
        (``reset_output_overrides``) ANTES de reaplicar — o MESMO ciclo de
        vida da ativação de perfil (``ProfileManager.apply``). Sem isto, um
        ajuste especial que a usuária TIROU de um controle na GUI (ele voltou
        a "Todos" e sumiu do payload) seguiria vivo no controle até a próxima
        troca de perfil, e o "Aplicar" mostraria a cor/gatilho antigo.
        """
        if not isinstance(raw, dict):
            raise ValueError("controllers deve ser objeto")
        specs: dict[str, OutputSpec] = {}
        for uniq, entry in raw.items():
            if not isinstance(entry, dict):
                raise ValueError(f"controllers[{uniq!r}] deve ser objeto")
            spec = self._controller_override_spec(entry, str(uniq))
            if spec is not None:
                specs[str(uniq)] = spec
        # O CONTROLE EM ECONOMIA VAI NA CAMADA DO PERFIL, como na ativação
        # (`_publicar_a_economia`); o resto é a camada dela, como sempre.
        da_economia = {u: s for u, s in specs.items() if u in self._em_economia}
        da_mao = {u: s for u, s in specs.items() if u not in da_economia}
        # Getattr defensivo: stubs/fakes de teste sem o método seguem (a base
        # ``IController`` e os backends reais o têm — no-op sem estado por-uniq).
        reset = getattr(self.controller, "reset_output_overrides", None)
        if callable(reset) and self._o_rascunho_tem_o_mapa:
            reset(da_mao or None)
        for uniq, spec in da_mao.items():
            self._aplicar_com_o_brilho_da_cor(uniq, spec, raw.get(uniq))
        self._publicar_escalas_de_brilho(raw)
        self._publicar_a_economia(da_economia)
        # A LUZ CONVERGE DEPOIS DO MAPA NOVO — conferência da
        # A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01, 25/09/2026. O brilho sozinho de
        # um controle viaja como FATOR, sem cor, e o `apply_output_for` acima
        # não escreve luz nenhuma por ele; o único reassert desta aplicação era
        # o de `_apply_leds`, que roda ANTES do mapa novo. Medido na mesa de
        # quatro real: com o brilho do P1 mudado no disco (30%) e o «Aplicar»,
        # o produto decidia `(0,0,76)` e a barra ficava em `(0,0,153)` até o
        # próximo reassert. É o mesmo fecho da ativação (`manager.apply`).
        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()
        # POR-UNIDADE-01 (10/08/2026): vibração e som da PEÇA. Ficam FORA do
        # `OutputSpec` de propósito — não são output persistente do controle
        # (o rumble é transitório; o áudio tem posse própria), e empurrá-los
        # para dentro do spec faria o reassert de hotplug re-vibrar o que já
        # passou. Cada um segue a sua rota por-uniq, que já existia.
        self._publicar_escalas_de_vibracao(raw)
        self._escrever_alto_falantes_por_unidade(raw)

    def _aplicar_com_o_brilho_da_cor(
        self, uniq: str, spec: OutputSpec, entrada: Any
    ) -> None:
        """`apply_output_for` com o brilho em que a cor do override foi escalada.

        A-04-PERGUNTA-AO-DAEMON-VIVO-01, 25/09/2026: o backend guarda o brilho
        ao lado da cor da camada da usuária, e é o que o `state_full` publica
        como `brilho_da_barra` — a aba Iluminação pergunta ao daemon vivo, e a
        cor do «Aplicar» atravessa a troca automática de perfil como a do
        `led.set`. O brilho é o MESMO que `_scaled_rgb_from` usou. Backend sem o
        parâmetro recebe a cor igual, sem o carimbo.
        """
        aplicar: Any = self.controller.apply_output_for
        leds_raw = entrada.get("leds") if isinstance(entrada, dict) else None
        if spec.led is None or not isinstance(leds_raw, dict):
            aplicar(uniq, spec)
            return
        brilho = _brilho_de(leds_raw.get("lightbar_brightness", 1.0))
        try:
            aplicar(uniq, spec, brilho_da_cor=1.0 if brilho is None else brilho)
        except TypeError:
            aplicar(uniq, spec)

    def _publicar_escalas_de_brilho(self, raw: dict[str, Any]) -> None:
        """Publica o brilho por controle como FATOR, como a ativação (R-20 item 2).

        A-BARRA-NAO-ESCURECE-AO-REAPLICAR-01, 25/09/2026. O override que só
        escreveu o brilho chega aqui SEM cor (`DraftConfig._controllers_to_ipc`
        parou de lhe emprestar o global), e o brilho dele vale sobre a base do
        merge — a cor do número ou o global —, pelo mesmo fator que
        `manager._controllers_to_led_scales` publica na ativação: o brilho do
        controle sobre o do perfil. SUBSTITUI o mapa inteiro, como a
        vibração logo abaixo, e pela mesma razão: o brilho que ela tirou de um
        controle tem de sumir no mesmo "Aplicar".

        Sem o brilho global no rascunho (seção `leds` ausente) não há
        denominador, e o mapa da última ativação fica; com ele em 0% também não
        — é o caso degenerado em que a cor viaja materializada.
        """
        escalar = getattr(self.controller, "set_led_scales", None)
        base = self._brilho_do_rascunho
        if not callable(escalar) or base is None or base <= 0.0:
            return
        escalas: dict[str, float] = {}
        for uniq, entry in raw.items():
            leds_raw = entry.get("leds") if isinstance(entry, dict) else None
            if not isinstance(leds_raw, dict):
                continue
            brilho = _brilho_de(leds_raw.get("lightbar_brightness"))
            if brilho is None:
                continue
            fator = brilho / base
            if fator != 1.0:
                escalas[str(uniq)] = fator
        try:
            escalar(
                escalas or None,
                brilho_do_perfil=base,
                cor_do_perfil=self._cor_do_rascunho,
            )
        except TypeError:
            escalar(escalas or None)

    def _publicar_escalas_de_vibracao(self, raw: dict[str, Any]) -> None:
        """Publica a escala de vibração por peça no backend (POR-UNIDADE-01).

        SUBSTITUI o mapa inteiro, como o ``reset_output_overrides`` acima e
        pela mesma razão: intensidade que ela TIROU de um controle na janela
        (a peça voltou ao global e sumiu do payload) tem de sumir do backend
        no mesmo "Aplicar", senão continuaria valendo até a próxima troca de
        perfil e a tela mentiria.

        O fator é RELATIVO à política global vigente no daemon — o mesmo
        denominador que ``_controllers_to_rumble_scales`` usa na ativação,
        porque o valor que chega ao ``set_rumble`` já vem escalado por ela
        (``apply_rumble_policy``). Sem daemon (CLI/testes), o denominador é o
        ``balanceado`` padrão.
        """
        from hefesto_dualsense4unix.profiles.manager import _mult_da_politica

        escalar = getattr(self.controller, "set_rumble_scales", None)
        if not callable(escalar):
            return
        base = _mult_da_politica(*self._politica_viva())
        escalas: dict[str, float] = {}
        for uniq, entry in raw.items():
            rumble_raw = entry.get("rumble") if isinstance(entry, dict) else None
            if not isinstance(rumble_raw, dict):
                continue
            mult = _mult_da_politica(
                rumble_raw.get("policy"), rumble_raw.get("custom_mult")
            )
            if mult is None or base is None or base <= 0.0:
                # Global em `auto` (denominador móvel) ou política que não vira
                # número: a peça fica com o global. Ver a docstring do irmão em
                # `profiles/manager.py` — prometer um fator contra denominador
                # móvel seria pior do que não entregar.
                continue
            fator = mult / base
            if fator != 1.0:
                escalas[str(uniq)] = fator
        escalar(escalas or None)

    def _escrever_alto_falantes_por_unidade(self, raw: dict[str, Any]) -> None:
        """Aplica o alto-falante de cada peça (POR-UNIDADE-01).

        Rota por-``uniq`` que já existia e nunca fora ligada pelo perfil:
        ``set_speaker_volume(volume, muted=..., uniq=..., rota=...)``. Fala
        DIRETO com o backend, e não pelo ``speaker.set`` do IPC, pela mesma
        razão de ``lifecycle.apply_profile_speaker``: aquele handler arma a
        trava manual da categoria ``"audio"``, e um "Aplicar" que a armasse
        faria todo "Aplicar" seguinte ser descartado em silêncio.

        Sem broadcast e sem ``None``: seção ausente é ausência de opinião, e
        nunca escrever é o que impede tomar a posse dos bytes de áudio de uma
        peça que ninguém pediu (SOM-02, armadilha 1).
        """
        setter = getattr(self.controller, "set_speaker_volume", None)
        if not callable(setter):
            return
        for uniq, entry in raw.items():
            speaker_raw = entry.get("speaker") if isinstance(entry, dict) else None
            if not isinstance(speaker_raw, dict):
                continue
            volume = speaker_raw.get("volume")
            if not isinstance(volume, int) or isinstance(volume, bool):
                raise ValueError(
                    f"controllers[{uniq!r}].speaker.volume precisa ser int 0-255"
                )
            if not (0 <= volume <= 255):
                raise ValueError(
                    f"controllers[{uniq!r}].speaker.volume fora de 0-255"
                )
            muted = speaker_raw.get("muted", False)
            if not isinstance(muted, bool):
                raise ValueError(
                    f"controllers[{uniq!r}].speaker.muted precisa ser booleano"
                )
            rota = speaker_raw.get("rota")
            if rota is not None and (
                not isinstance(rota, int) or isinstance(rota, bool) or not (0 <= rota <= 3)
            ):
                raise ValueError(
                    f"controllers[{uniq!r}].speaker.rota precisa ser int 0-3"
                )
            try:
                setter(volume, muted=muted, uniq=str(uniq), rota=rota)
            except Exception as exc:
                logger.warning(
                    "apply_draft_speaker_por_unidade_falhou",
                    uniq=str(uniq),
                    erro=str(exc),
                )

    def _controller_override_spec(
        self, entry: dict[str, Any], uniq: str
    ) -> OutputSpec | None:
        """Converte uma entrada de override em ``OutputSpec``; None se vazia."""
        led: tuple[int, int, int] | None = None
        player: tuple[bool, bool, bool, bool, bool] | None = None
        leds_raw = entry.get("leds")
        if leds_raw is not None:
            if not isinstance(leds_raw, dict):
                raise ValueError(f"controllers[{uniq!r}].leds deve ser objeto")
            led = self._scaled_rgb_from(leds_raw)
            player = self._player_bits_from(leds_raw)
        trigger_left: TriggerEffect | None = None
        trigger_right: TriggerEffect | None = None
        triggers_raw = entry.get("triggers")
        if triggers_raw is not None:
            if not isinstance(triggers_raw, dict):
                raise ValueError(f"controllers[{uniq!r}].triggers deve ser objeto")
            base = f"controllers[{uniq!r}].triggers"
            left_raw = triggers_raw.get("left")
            if left_raw is not None:
                trigger_left = self._trigger_effect_from(left_raw, f"{base}.left")
            right_raw = triggers_raw.get("right")
            if right_raw is not None:
                trigger_right = self._trigger_effect_from(right_raw, f"{base}.right")
        luzes = None
        if isinstance(leds_raw, dict) and leds_raw.get("player_led_brightness") is not None:
            from hefesto_dualsense4unix.core.led_control import degrau_do_brilho_das_luzes

            luzes = degrau_do_brilho_das_luzes(str(leds_raw["player_led_brightness"]))
        if (led is None and player is None and luzes is None
                and trigger_left is None and trigger_right is None):
            return None
        return OutputSpec(
            trigger_left=trigger_left,
            trigger_right=trigger_right,
            led=led,
            player_leds=player,
            player_led_brightness=luzes,
        )

    def _apply_rumble(self, rumble_raw: Any) -> None:
        """Aplica a seção rumble do "Aplicar" do RODAPÉ.

        NATIVO-RUMBLE-01 (19/08/2026) — **no Modo Nativo esta seção é recusada
        inteira, sem tocar em nada.** Este era o vazamento silencioso da cura:
        o rodapé emite a seção rumble em TODO "Aplicar" (mexer só no brilho já
        basta — ABAS-04), então não passa por handler de rumble nenhum, e
        gravar `rumble_active` aqui desarmava a HARM-16 pela porta de trás,
        mesmo com o `rumble.set` já recusando. Ver o bloco de comentário em
        `daemon.subsystems.rumble`.

        Recusar SEM ESCREVER, e não "gravar passthrough", é deliberado: como a
        seção viaja de carona em qualquer edição, zerar aqui apagaria um par
        que ela tenha fixado por outro caminho num gesto que não era sobre
        vibração.

        A recusa sai como EXCEÇÃO, não como `return`, por APLICAR-VERDADE-01:
        quem retorna sem levantar entra em `applied`, e o rodapé anunciaria
        "aplicado" sobre uma seção que não encostou no controle — a mesma
        mentira que esta leva inteira veio consertar. Levantando, a seção cai
        em `self.failed` com o motivo e a tela conta a verdade.
        """
        from hefesto_dualsense4unix.daemon.subsystems.rumble import (
            modo_nativo_manda_nos_motores,
        )

        if not isinstance(rumble_raw, dict):
            raise ValueError("rumble deve ser objeto")
        if modo_nativo_manda_nos_motores(self.daemon):
            logger.warning(
                "draft_rumble_recusado_modo_nativo",
                pedido=rumble_raw,
            )
            # Motivo curto de propósito (`_apply_section` corta em 120): serve
            # de diagnóstico. A frase que a usuária lê é a de
            # `daemon.subsystems.rumble`.
            raise ValueError("Modo Nativo: quem manda nos motores é o jogo")
        weak = rumble_raw.get("weak", 0)
        strong = rumble_raw.get("strong", 0)
        if not isinstance(weak, int) or not isinstance(strong, int):
            raise ValueError("rumble.weak e rumble.strong devem ser inteiros")
        weak = max(0, min(255, weak))
        strong = max(0, min(255, strong))
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        # BUG-RUMBLE-APPLY-KILLS-GAME-01: (0,0) num "Aplicar" significa "não force
        # rumble" (passthrough), NÃO "force silêncio". Antes, rumble_active=(0,0)
        # fazia o poll loop (_reassert_rumble) reescrever set_rumble(0,0) a cada
        # tick, SOBRESCREVENDO o rumble do JOGO — qualquer "Aplicar" com sliders em
        # 0 (o default) matava a vibração in-game. Passthrough = rumble_active None
        # (o poll loop deixa o jogo controlar; idêntico a rumble.passthrough);
        # aplica (0,0) uma vez para soltar um rumble contínuo anterior. "Parar"
        # (rumble.stop) continua fixando (0,0) como silêncio deliberado.
        if weak == 0 and strong == 0:
            if daemon_cfg is not None:
                daemon_cfg.rumble_active = None
                # MESA-CHEIA-05 (E0): sem par fixado não há dono a lembrar.
                daemon_cfg.rumble_active_uniq = None
            self.controller.set_rumble(weak=0, strong=0)
            return
        # AUDIT-FINDING-IPC-DRAFT-RUMBLE-POLICY-01:
        # Persiste valores brutos para que o poll loop (_reassert_rumble)
        # continue reaplicando a política a cada tick. Antes de enviar ao
        # hardware, escala via apply_rumble_policy — mesmo comportamento
        # canônico de _handle_rumble_set.
        if daemon_cfg is not None:
            daemon_cfg.rumble_active = (weak, strong)
            # MESA-CHEIA-05 (E0): o "Aplicar" do rodapé mira o alvo do seletor
            # tanto quanto a aba Rumble — então congela o dono junto do par,
            # senão o valor migra para quem entrar no seletor depois.
            daemon_cfg.rumble_active_uniq = uniq_do_alvo_de_output(self.controller)
        eff_weak, eff_strong = apply_rumble_policy(self.daemon, weak, strong)
        self.controller.set_rumble(weak=eff_weak, strong=eff_strong)

    def _apply_mouse(self, mouse_raw: Any) -> None:
        """Aplica a seção mouse do draft.

        HARM-05: sem ``enabled`` cai na rota speed-only (``set_mouse_speed``) —
        a mesma que o handler ``mouse.emulation.set`` já oferece (A4): atualiza
        as velocidades sem start/stop e sem persistir o flag. É por aqui que o
        "Aplicar" do rodapé entra, e ele não pode mudar o modo do sistema: o
        dono do liga/desliga é a aba Início. Exigir ``enabled`` aqui não
        protegia nada — só fazia a edição de velocidade morrer em silêncio
        (``_apply_section`` engole a exceção como "seção falhou").
        """
        if not isinstance(mouse_raw, dict):
            raise ValueError("mouse deve ser objeto")
        enabled = mouse_raw.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            raise ValueError("mouse.enabled deve ser booleano ou omitido")
        speed = mouse_raw.get("speed")
        scroll_speed = mouse_raw.get("scroll_speed")
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar emulação de mouse")
        if enabled is None:
            self.daemon.set_mouse_speed(speed=speed, scroll_speed=scroll_speed)
            return
        self.daemon.set_mouse_emulation(
            enabled=enabled,
            speed=speed,
            scroll_speed=scroll_speed,
        )

    def _apply_mic(self, mic_raw: Any) -> None:
        """Aplica a seção mic do draft (MIC-EXPOSE-01).

        Único campo: ``button_toggles_system`` — se o botão de mic do controle
        alterna o mute do microfone PADRÃO DO SISTEMA. Escreve na config VIVA
        do daemon; o laço `mic_button_loop` consulta o flag a cada evento, então
        a mudança vale já no próximo toque do botão, sem restart e sem
        derrubar/recriar task nenhuma (o laço é um assinante de bus barato e
        fica de pé independente do flag).

        `volume` e `muted` chegam na mesma seção (PERFIL-GUARDA-O-MIC-01) e NÃO
        são aplicados aqui: quem os manda ao vivo é o `mic.volume.set`/`mic.set`
        do IPC, disparado pelo card no gesto dela — o rascunho só os carrega
        para o "Salvar Perfil".

        MIC-GATE-POR-CAMPO-01 (22/08/2026): campo ausente **ou nulo** é campo
        NÃO tocado, a mesma régua do `speaker.rota` aqui do lado. Sem o nulo,
        um rascunho sem opinião sobre o botão (o default desde esta data — ver
        `MicDraft`) cairia em `failed` e o rodapé diria que o microfone falhou,
        no gesto mais comum que existe: arrastar o volume e clicar no verde.
        """
        if not isinstance(mic_raw, dict):
            raise ValueError("mic deve ser objeto")
        if mic_raw.get("button_toggles_system") is None:
            return
        valor = mic_raw.get("button_toggles_system")
        if not isinstance(valor, bool):
            raise ValueError("mic.button_toggles_system deve ser booleano")
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar o botão de mic")
        antes = bool(getattr(self.daemon.config, "mic_button_toggles_system", True))
        self.daemon.config.mic_button_toggles_system = valor
        logger.info("mic_button_toggles_system_aplicado", enabled=valor)
        # DESLIGAR TEM DE DEVOLVER A LUZ (auditoria de 02/09/2026). O comentário
        # do campo em `daemon/lifecycle.py` promete que, desligado, "o kernel
        # segue dono do mudo E da luz do próprio controle". Isso era falso
        # depois da primeira eleição: a posse do `common[8]` só cai por
        # `set_microphone_led(None)`, e este caminho é reentrante em runtime —
        # ela carrega um perfil de gravação e a luz fica CONGELADA no que a
        # última eleição deixou, com o botão físico já sem efeito sobre ela.
        if antes and not valor:
            from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
                devolver_a_luz_ao_kernel,
            )

            devolver_a_luz_ao_kernel(self.daemon)

    def _apply_speaker(self, speaker_raw: Any) -> None:
        """Aplica a seção `speaker` do rascunho — O-VERDE-NAO-LEVAVA-O-SOM-01.

        Três campos, os MESMOS do `ProfileSpeakerConfig` e do `SpeakerDraft`:
        ``volume`` (0 a 255, byte do registrador), ``muted`` e ``rota`` (o canal de saída). Um nome
        diferente aqui criaria um terceiro vocabulário para o mesmo fato.

        **Reusa a porta que já existe**, `Daemon.apply_profile_speaker`, e isso
        é requisito, não conveniência: ela é a mesma que a ativação de perfil
        usa, já sabe conversar por-`uniq` e já carrega a política de silêncio da
        SOM-02/E4. Um caminho novo direto ao backend seria um segundo dono dos
        bytes de áudio — e o `set_speaker_volume` do backend, medido em 10/08,
        **não tem gate de `_output_mute`**: chamá-lo por fora responderia `ok` em
        Modo Nativo sem mandar byte nenhum, e a tela diria que aplicou.

        Campo ausente é campo NÃO tocado (`volume` obrigatório, o resto opcional):
        o rascunho só emite esta seção quando ela mexeu, e mesmo assim o mudo e a
        rota podem não ter opinião. Sem opinião é silêncio, nunca ordem.
        """
        if not isinstance(speaker_raw, dict):
            raise ValueError("speaker deve ser objeto")
        if "volume" not in speaker_raw:
            return
        volume = speaker_raw.get("volume")
        if not isinstance(volume, int) or isinstance(volume, bool):
            raise ValueError("speaker.volume deve ser inteiro")
        # A RÉGUA É 0..255, e errar isso recusa o volume NORMAL dela. Medido em
        # 10/08/2026: a primeira versão desta guarda usou 0..100, por eu ter lido
        # "volume" como porcentagem — e o controle deslizante do card em 100 %
        # sai como **102**. A seção cairia em `failed` e o rodapé diria que o som
        # falhou, no gesto mais comum que existe. O registrador do controle é um
        # byte, e é assim em toda a casa: `ProfileSpeakerConfig` (`ge=0, le=255`),
        # o `SpeakerDraft`, o IPC `speaker.set` e o `set_speaker_volume` do
        # backend. Aqui não pode ser diferente — quatro réguas iguais e uma
        # sozinha é como se recusa em silêncio o que a pessoa acabou de escolher.
        if not 0 <= volume <= 255:
            raise ValueError("speaker.volume fora de 0..255")
        muted = speaker_raw.get("muted", False)
        if not isinstance(muted, bool):
            raise ValueError("speaker.muted deve ser booleano")
        rota = speaker_raw.get("rota")
        if rota is not None and (not isinstance(rota, int) or isinstance(rota, bool)):
            raise ValueError("speaker.rota deve ser inteiro ou nulo")
        applier = getattr(self.daemon, "apply_profile_speaker", None)
        if not callable(applier):
            raise ValueError("daemon não expõe apply_profile_speaker")
        applier(volume, muted, uniq=speaker_raw.get("uniq"), origin="draft", rota=rota)
        logger.info(
            "speaker_do_rascunho_aplicado", volume=volume, muted=muted, rota=rota
        )

    def _apply_keyboard(self, keyboard_raw: Any) -> None:
        """Aplica os key_bindings editados ao device de teclado virtual vivo.

        BUG-FOOTER-APPLY-IGNORA-KEYBINDINGS-01: antes o único caminho que empurrava
        bindings ao device era ``profile.switch`` (que recarrega do DISCO); o
        rodapé "Aplicar" (``profile.apply_draft``) ignorava o teclado. Agora a
        seção ``keyboard`` resolve o inner ``key_bindings`` (None →
        DEFAULT_BUTTON_BINDINGS; ``{}`` → silêncio; dict → override) e chama
        ``set_bindings`` no device vivo, sem reativar/regravar o perfil.

        No-op seguro quando não há device de teclado (CLI/headless, emulação de
        teclado desligada, ou gamepad ligado — que assume o ramo do gamepad e o
        teclado nunca despacha): os bindings entram em vigor quando o teclado
        virtual subir.
        """
        if not isinstance(keyboard_raw, dict):
            raise ValueError("keyboard deve ser objeto")
        if "key_bindings" not in keyboard_raw:
            return
        device = getattr(self.daemon, "_keyboard_device", None) if self.daemon else None
        if device is None:
            return
        raw = keyboard_raw.get("key_bindings")
        if raw is not None and not isinstance(raw, dict):
            raise ValueError("keyboard.key_bindings deve ser objeto ou null")
        from hefesto_dualsense4unix.profiles.manager import resolve_key_bindings

        device.set_bindings(resolve_key_bindings(raw))

    # --- O-APLICAR-NAO-SOLTA-O-TETO-DO-CONTROLE-01 (26/09/2026) ---

    def _politica_viva(self) -> tuple[str, float | None]:
        """A política global de vibração do daemon, e o teto dela — o denominador.

        Um lugar só para as duas contas do «Aplicar» que precisam dele: o fator
        de cada peça (`_publicar_escalas_de_vibracao`) e a vibração da peça na
        economia (`_com_o_teto_da_economia`). Sem daemon (CLI/testes), o
        ``balanceado`` padrão.
        """
        from hefesto_dualsense4unix.profiles.manager import _RUMBLE_POLICY_PADRAO

        cfg = getattr(self.daemon, "config", None) if self.daemon else None
        politica = getattr(cfg, "rumble_policy", None) or _RUMBLE_POLICY_PADRAO
        return str(politica), getattr(cfg, "rumble_policy_custom_mult", None)

    def _com_o_teto_da_economia(self, params: dict[str, Any]) -> dict[str, Any]:
        """O rascunho com o teto da economia posto — a MESMA vista da ativação.

        A QUEIXA: achada pela O-BRILHO-DAS-LUZES-SOBREVIVE-AO-APLICAR-01 e
        medida na mesa de quatro (o `IpcServer` real, o merge do
        `PyDualSenseController`): com a economia ligada só no P2, a ativação o
        deixava na luz a 30% `(76, 38, 0)`, nas luzes de número no Fraco, nos
        gatilhos com metade da força e na vibração a 0,3; o «Aplicar» o levava
        a `(209, 104, 0)`, ao Médio do perfil, à força inteira e à vibração do
        global. O rascunho não sabe da economia, e o «Aplicar» troca o mapa de
        overrides inteiro (`reset_output_overrides`).

        O DONO DO TETO É O DA ATIVAÇÃO, e ele não se reescreve aqui: quem está
        em economia é a declaração da mesa (`schema.economia_da_mesa` e
        `schema.controles_em_economia`, o que o gesto `economia-do-controle`
        grava), e o que ela faz em cada peça é `manager._perfil_na_economia` —
        as mesmas três chamadas de `ProfileManager.apply`. Quem estender a
        economia (outro teto, outro jeito de escolher quem economiza) estende
        lá, e o «Aplicar» segue sozinho. Aqui só se traduz o rascunho para o
        esquema e de volta.

        A TRADUÇÃO NÃO PERDE NADA QUE O TETO USE: o rascunho já chega com o
        brilho de cada cor resolvido (`DraftConfig._controllers_to_ipc`), e o
        teto é um `min` — o do brilho próprio e o do global dão o mesmo número.

        Devolve o rascunho intacto (o MESMO objeto) sem economia nenhuma: o
        «Aplicar» de quem não ligou nada é byte a byte o de antes. Os controles
        em economia ficam em `self._em_economia`, e vão na camada do PERFIL
        (`_publicar_a_economia`).
        """
        from hefesto_dualsense4unix.profiles.schema import (
            controles_em_economia,
            economia_da_mesa,
        )

        mesa, ligados = economia_da_mesa(), controles_em_economia()
        self._em_economia = frozenset()
        if not mesa and not ligados:
            return params
        try:
            return self._a_vista_da_economia(params, mesa, ligados)
        except Exception as exc:
            logger.warning("apply_draft_economia_falhou", erro=str(exc))
            self.failed["economia"] = (str(exc) or type(exc).__name__)[:120]
            return params

    def _a_vista_da_economia(
        self, params: dict[str, Any], mesa: bool, ligados: frozenset[str]
    ) -> dict[str, Any]:
        """O corpo de `_com_o_teto_da_economia`: rascunho → esquema → teto → rascunho."""
        from hefesto_dualsense4unix.profiles.manager import _perfil_na_economia
        from hefesto_dualsense4unix.profiles.schema import (
            LedsConfig,
            Profile,
            RumbleConfig,
            TriggersConfig,
            economia_vale,
        )

        leds_raw = params.get("leds")
        trig_raw = params.get("triggers")
        ctrl_raw = params.get("controllers")
        leds = _leds_do_rascunho(leds_raw) if isinstance(leds_raw, dict) else None
        gatilhos = _gatilhos_do_rascunho(trig_raw) if isinstance(trig_raw, dict) else None
        politica, custom = self._politica_viva()
        mapa = {str(u): _override_do_rascunho(e) for u, e in (
            ctrl_raw.items() if isinstance(ctrl_raw, dict) else ()) if isinstance(e, dict)}
        # SEM A SEÇÃO GLOBAL NO RASCUNHO NÃO HÁ O QUE HERDAR: o controle que
        # liga a sua economia herda do perfil o que não escreveu, e o global que
        # não viajou não é o do perfil. Com a mesa, o global da vista é pedido
        # pelo dono e descartado aqui.
        vista = _perfil_na_economia(
            Profile.model_construct(
                leds=leds if leds is not None else (LedsConfig() if mesa else None),
                triggers=(gatilhos if gatilhos is not None
                          else (TriggersConfig() if mesa else None)),
                rumble=RumbleConfig.model_construct(policy=politica, custom_mult=custom),
                controllers=mapa or None,
            ),
            mesa,
            ligados,
        )
        novo = dict(params)
        if mesa and isinstance(leds_raw, dict):
            novo["leds"] = {
                **leds_raw,
                "lightbar_brightness": float(vista.leds.lightbar_brightness),
                "player_led_brightness": str(vista.leds.player_led_brightness),
            }
        if mesa and isinstance(trig_raw, dict):
            novo["triggers"] = {
                **trig_raw,
                **{lado: _gatilho_para_o_rascunho(getattr(vista.triggers, lado))
                   for lado in ("left", "right") if isinstance(trig_raw.get(lado), dict)},
            }
        da_vista = vista.controllers or {}
        em_economia = frozenset(
            u for u in da_vista if economia_vale(u in ligados, mesa))
        controles = dict(ctrl_raw) if isinstance(ctrl_raw, dict) else {}
        for uniq in sorted(em_economia):
            controles[uniq] = _entrada_na_economia(controles.get(uniq), da_vista[uniq])
        if controles:
            novo["controllers"] = controles
        self._em_economia = em_economia
        return novo

    def _publicar_a_economia(self, specs: dict[str, OutputSpec]) -> None:
        """O controle em economia vai na camada do PERFIL, como a ativação o põe.

        Na camada dela (`reset_output_overrides`/`apply_output_for`) o teto
        ficaria PRESO: desligar a economia reaplica o perfil com a origem
        ``system`` (`lifecycle.reaplicar_se_a_economia_mudou`), e a camada da
        usuária atravessa essa ativação — o P2 seguiria a 30% com a economia
        desligada. Na do perfil, a ativação seguinte o republica sem o teto.
        Backend sem camadas recebe o mesmo `apply_output_for` de sempre.
        """
        if not specs:
            return
        publicar = getattr(self.controller, "reset_profile_overrides", None)
        if callable(publicar):
            publicar(specs)
            return
        for uniq, spec in specs.items():
            self.controller.apply_output_for(uniq, spec)


# ---------------------------------------------------------------------------
# A tradução do rascunho para o esquema, e de volta — só o que o teto lê
# ---------------------------------------------------------------------------


def _leds_do_rascunho(leds_raw: dict[str, Any]) -> Any:
    """A luz de uma seção do rascunho como `LedsConfig`, só com o que ela escreveu."""
    from hefesto_dualsense4unix.profiles.schema import LedsConfig

    campos: dict[str, Any] = {}
    rgb = leds_raw.get("lightbar_rgb")
    if isinstance(rgb, list) and len(rgb) == 3:
        campos["lightbar"] = tuple(int(c) for c in rgb)
    brilho = _brilho_de(leds_raw.get("lightbar_brightness"))
    if brilho is not None:
        campos["lightbar_brightness"] = brilho
    if isinstance(leds_raw.get("player_leds"), list):
        campos["player_leds"] = [bool(b) for b in leds_raw["player_leds"]]
    if leds_raw.get("player_led_brightness") is not None:
        campos["player_led_brightness"] = str(leds_raw["player_led_brightness"])
    return LedsConfig.model_validate(campos) if campos else None


def _gatilhos_do_rascunho(trig_raw: dict[str, Any]) -> Any:
    """Os gatilhos de uma seção do rascunho, só os lados que ela escreveu."""
    from hefesto_dualsense4unix.profiles.schema import TriggerConfig, TriggersConfig

    lados = {
        lado: TriggerConfig(mode=cru["mode"], params=list(cru.get("params") or []))
        for lado in ("left", "right")
        if isinstance(cru := trig_raw.get(lado), dict) and isinstance(cru.get("mode"), str)
    }
    return TriggersConfig(**lados) if lados else None


def _override_do_rascunho(entrada: dict[str, Any]) -> Any:
    """A entrada de um controle do rascunho como `ControllerOverrides` (luz, gatilhos, vibração)."""
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        ControllerRumbleOverride,
    )

    leds_raw, trig_raw, vib_raw = (
        entrada.get("leds"), entrada.get("triggers"), entrada.get("rumble"))
    vibracao = None
    if isinstance(vib_raw, dict) and vib_raw.get("policy") is not None:
        vibracao = ControllerRumbleOverride.model_validate(
            {k: vib_raw[k] for k in ("policy", "custom_mult") if vib_raw.get(k) is not None})
    return ControllerOverrides(
        leds=_leds_do_rascunho(leds_raw) if isinstance(leds_raw, dict) else None,
        triggers=_gatilhos_do_rascunho(trig_raw) if isinstance(trig_raw, dict) else None,
        rumble=vibracao,
    )


def _gatilho_para_o_rascunho(gatilho: Any) -> dict[str, Any]:
    return {"mode": gatilho.mode, "params": list(gatilho.params)}


def _entrada_na_economia(entrada: Any, dele: Any) -> dict[str, Any]:
    """A entrada de um controle com a luz, os gatilhos e a vibração da vista da economia.

    O resto da entrada (o alto-falante) segue como veio: a economia não o toca
    (`schema.A_ECONOMIA_EM_CADA_PECA`).
    """
    saida = {k: v for k, v in (entrada or {}).items()
             if k not in ("leds", "triggers", "rumble")}
    luz = getattr(dele, "leds", None)
    if luz is not None:
        campos = luz.model_fields_set
        leds: dict[str, Any] = {}
        if "lightbar" in campos:
            leds["lightbar_rgb"] = [int(c) for c in luz.lightbar]
        if "lightbar_brightness" in campos:
            leds["lightbar_brightness"] = float(luz.lightbar_brightness)
        if "player_leds" in campos:
            leds["player_leds"] = [bool(b) for b in luz.player_leds]
        if "player_led_brightness" in campos:
            leds["player_led_brightness"] = str(luz.player_led_brightness)
        if leds:
            saida["leds"] = leds
    gatilhos = getattr(dele, "triggers", None)
    if gatilhos is not None:
        lados = {lado: _gatilho_para_o_rascunho(getattr(gatilhos, lado))
                 for lado in ("left", "right") if lado in gatilhos.model_fields_set}
        if lados:
            saida["triggers"] = lados
    vibracao = getattr(dele, "rumble", None)
    if vibracao is not None and getattr(vibracao, "policy", None) is not None:
        saida["rumble"] = {"policy": vibracao.policy}
        if vibracao.custom_mult is not None:
            saida["rumble"]["custom_mult"] = float(vibracao.custom_mult)
    return saida


__all__ = ["DraftApplier"]
