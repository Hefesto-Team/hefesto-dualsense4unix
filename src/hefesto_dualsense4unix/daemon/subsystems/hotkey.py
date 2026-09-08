"""Subsystem Hotkey — gerencia HotkeyManager e hotkey de microfone.

Responsabilidades:
  - Instanciar HotkeyManager com callback on_ps_solo (leitura de config em runtime).
  - Iniciar e parar a task _mic_button_loop que ouve BUTTON_DOWN para mic_btn.
  - Expor funções utilitárias usadas pelo Daemon como thin wrappers.
  - FEAT-HOTKEY-PONTE-CYCLE-01: o gesto PS+R3 cicla a PONTE (a forma
    como o jogo enxerga o controle) — ver `build_next_bridge_callback`, que
    também registra o que o gesto NÃO pode prometer.
"""
from __future__ import annotations

import asyncio
import contextlib
import subprocess as _sp
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from hefesto_dualsense4unix.daemon.subsystems import recado_do_microfone
from hefesto_dualsense4unix.integrations import ponte_tentativa
from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
    EleitorDeMicrofone,
    ResultadoDaEleicao,
    dizer_no_ar,
    esquecer_a_palavra,
    palavra_no_ar,
    recusa_de_quem_nao_elegeu,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.daemon.context import DaemonContext
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

#: Sossego do botão de microfone, contado a partir do FIM do toggle anterior
#: (MIC-REPIQUE-01). Não é um debounce de teclinha: o que está do outro lado é
#: um mudo LATCHED do sistema inteiro, e o botão é o único jeito de desfazê-lo
#: com o controle na mão. Um segundo é mais que qualquer repique elétrico e
#: menos que qualquer segundo toque DELIBERADO — ninguém muta e desmuta de
#: propósito em menos de um segundo. Ver o docstring de `mic_button_loop` para
#: por que o debounce de 200 ms do `AudioControl` não cobre este caso.
MIC_SOSSEGO_S = 1.0


#: ONDA5-06-01 — ONDE MORA A ESCOLHA DO PS ENQUANTO O DAEMON VIVE.
#:
#: O PS tem DOIS donos, e a precedência é escrita: `Profile.button_actions["ps"]`
#: vence, e `DaemonConfig.ps_button_action` é o degrau da máquina, que vale para
#: o perfil que não diz nada. Este atributo é o primeiro dos dois, EM MEMÓRIA —
#: `profiles/manager.apply_button_actions` o escreve a cada ativação, pelo
#: `ps_action_sink` que `gerente_do_daemon` injeta.
#:
#: EM MEMÓRIA, E NÃO POR LEITURA DE DISCO: o `_on_ps_solo` roda inline no poll
#: loop, e um `pgrep` ali já travou input, IPC e co-op por até 2 s
#: (REVIEW-M5-PGREP-BLOCK-01). `daemon.store.active_profile` devolve só o NOME —
#: carregar o perfil daqui seria disco dentro do laço.
_ATRIBUTO_DA_ACAO_DO_PS = "_acao_do_ps_do_perfil"

#: OS TOKENS VIRTUAIS QUE O TECLADO VIRTUAL SABE ENTREGAR. São os três do
#: teclado na tela, e só eles: `_delegate_virtual_tokens`
#: (`integrations/uinput_keyboard.py`) os manda ao `_OSKController`. Os outros
#: `__*__` do vocabulário da tela (`__STEAM__`, `__SAIR_DO_JOGO__`,
#: `__PROGRAMA__`, `__CURSOR__`, `__ROLAGEM__`) NÃO são tecla, e mandá-los ao
#: device viraria um `keyboard_key_unknown` calado por toque.
_TOKENS_QUE_O_TECLADO_ENTREGA: Final[frozenset[str]] = frozenset({
    "__OPEN_OSK__", "__CLOSE_OSK__", "__TOGGLE_OSK__",
})


def definir_acao_do_ps(daemon: Any, token: str | None) -> None:
    """Guarda o que o PERFIL ATIVO deu ao botão PS. `None` = o perfil não opinou.

    Chamado por `profiles/manager.ProfileManager._empurrar_o_ps` a cada
    ativação, inclusive com `None` — e o `None` é metade do contrato: sem ele a
    escolha do perfil de ontem continuaria digitando no perfil de hoje.
    """
    setattr(daemon, _ATRIBUTO_DA_ACAO_DO_PS, token)


def acao_do_ps_do_perfil(daemon: Any) -> str | None:
    """O token que o perfil ativo deu ao PS, ou `None` — leitura de memória."""
    token = getattr(daemon, _ATRIBUTO_DA_ACAO_DO_PS, None)
    return str(token) if token else None


def _o_ps_digita(token: str | None) -> bool:
    """O token escolhido é coisa que o teclado virtual sabe entregar?

    `KEY_*` (inclusive combos colados com `+`) e os três tokens do teclado na
    tela. Tudo o mais é escolha SEM ATENDENTE para o PS hoje — e quem a nomeia
    é o journal, não o silêncio.
    """
    if not token:
        return False
    partes = token.split("+")
    return all(
        p.startswith("KEY_") or p in _TOKENS_QUE_O_TECLADO_ENTREGA for p in partes
    )


def _digitar_o_ps(daemon: Any, token: str) -> bool:
    """Emite, UMA vez, a tecla que o perfil deu ao PS. Devolve se emitiu.

    PELO TECLADO VIRTUAL QUE JÁ EXISTE, e não por um device novo: é o mesmo
    `UinputKeyboardDevice` que atende as outras linhas da tabela, então um combo
    (`KEY_LEFTALT+KEY_TAB`) e os tokens do teclado na tela saem daqui do mesmo
    jeito que sairiam de qualquer outro botão.

    POR QUE `_emit_sequence_*` E NÃO `dispatch()`, e a razão é medida no código
    do device: `dispatch()` é SNAPSHOT — ele faz
    `newly_released = self._pressed_buttons - now_mapped`. Chamá-lo com
    `{"ps"}` soltaria toda tecla que estivesse segurada no instante do toque, e
    o tique seguinte a pressionaria de novo: um caractere dobrado no meio do que
    ela estivesse digitando. O par `_emit_sequence_press`/`_release` é o único
    emissor que não mexe no rastreador de bordas.

    O `bindings` VOLTA AO QUE ERA no `finally`, e isso não é zelo: deixar `"ps"`
    no mapa do device faria o `dispatch()` do poll loop emitir a tecla uma
    SEGUNDA vez no dia em que o latch do combo
    (`integrations/hotkey_daemon.combo_buttons_active`) deixar o PS passar para
    `emu_buttons`. Hoje ele não deixa — e o produto não pode depender disso para
    não digitar duas vezes.

    RELATO (arquivo de outra posse): a cura de verdade é um método público de
    TOQUE no `UinputKeyboardDevice` — `integrations/uinput_keyboard.py` — e
    enquanto ele não existir este é o caminho que não estraga o que já funciona.
    """
    teclado = getattr(daemon, "_keyboard_device", None)
    if teclado is None:
        # SEM TECLADO VIRTUAL NÃO É "APLICOU" NEM "FALHOU": é a escolha estar no
        # perfil e não ter onde pousar, que é a mesma frase do
        # `ignorado_sem_device` do `apply_keyboard`.
        logger.info("ps_digita_sem_teclado", token=token)
        return False
    if not getattr(teclado, "is_active", lambda: True)():
        logger.info("ps_digita_teclado_parado", token=token)
        return False
    antes = dict(getattr(teclado, "bindings", None) or {})
    seq = tuple(token.split("+"))
    try:
        teclado.bindings = {**antes, "ps": seq}
        teclado._emit_sequence_press("ps")
        teclado._emit_sequence_release("ps")
    except Exception as exc:
        logger.warning("ps_digita_falhou", token=token, err=str(exc))
        return False
    finally:
        teclado.bindings = antes
    logger.info("ps_digitou", token=token, teclas=list(seq))
    return True


def _a_metade_da_maquina(cfg: Any, escolha: str | None) -> str:
    """Qual dos três atos da máquina o toque no PS dispara: steam·none·custom.

    A PRECEDÊNCIA DA CASA, em uma tabela — e ela vem ANTES do antigo
    `if cfg.ps_button_action == "none": return`, que era a primeira porta. Se o
    `"none"` continuasse sendo a primeira porta, um perfil que escolheu `Enter`
    para o PS ficaria mudo por causa de uma config de máquina que ela nunca viu.

        escolha do perfil        o que a máquina faz
        ---------------------    -------------------------------------------
        None (perfil calado)     `cfg.ps_button_action`, intocado
        tecla / teclado na tela  `cfg.ps_button_action` — *"digita SEM parar
                                 de abrir a Steam"*, a palavra dela na 06-Q3
        `__NADA__`               nada. É ela dizendo que este botão não faz
                                 nada, e é o espelho exato do `"none"`
        `__STEAM__`              abre a Steam, mesmo com a máquina em `"none"`
        qualquer outro token     `cfg.ps_button_action` + linha no journal:
                                 escolha que o PS ainda não atende

    `__PROGRAMA__` FICA NA TERCEIRA LINHA DE PROPÓSITO, e é dívida declarada: o
    caminho do programa existe (`DaemonConfig.ps_button_command`), mas mora na
    MÁQUINA e não no perfil. Fazê-lo disparar aqui daria à escolha do perfil o
    comando de outro dono — um fato com dois donos, que é a família que esta
    casa persegue. Fechar isso é dar campo de CAMINHO ao perfil, e é sprint
    própria.
    """
    da_maquina = str(getattr(cfg, "ps_button_action", "steam"))
    if escolha is None:
        return da_maquina
    if escolha == "__NADA__":
        return "none"
    if escolha == "__STEAM__":
        return "steam"
    if not _o_ps_digita(escolha):
        logger.info("ps_solo_escolha_sem_atendente", token=escolha)
    return da_maquina


def build_ps_solo_callback(daemon: DaemonProtocol) -> Any:
    """Cria o callback on_ps_solo que lê self.config em runtime (REFACTOR-DAEMON-RELOAD-01).

    Leitura em runtime — não em closure — para que reload_config funcione sem
    recriar closures manualmente.

    ONDA5-06-01: E ELE FAZ AS DUAS COISAS, NESTA ORDEM — digita o que o perfil
    deu ao PS e **continua** fazendo o que a máquina manda. A ordem é a decisão:
    `open_or_focus_steam()` muda o foco da janela, e uma tecla emitida depois
    disso chegaria à Steam em vez de chegar ao que estava na frente dela.

    AS TRÊS GUARDAS DE HOJE FICAM INTEIRAS, e agora valem para as DUAS metades:
    modo nativo e modo jogo pulam o solo (com o controle dedicado a um jogo,
    digitar seria pior que abrir a Steam), e o teto do toque curto
    (PS-TOQUE-CURTO-01) é anterior a tudo — ele mora em `hotkey_daemon.py` e
    decide antes de este callback existir, então segurar o PS para religar o
    controle no rádio continua não digitando.
    """

    def _on_ps_solo() -> None:
        cfg = daemon.config
        escolha = acao_do_ps_do_perfil(daemon)
        digita = _o_ps_digita(escolha)
        da_maquina = _a_metade_da_maquina(cfg, escolha)
        if da_maquina == "none" and not digita:
            return
        # FEAT-PARITY-REVIEW-01 + M5: com o controle dedicado a um JOGO, o PS já
        # vai cru como BTN_MODE (guide/overlay) e disparar TAMBÉM a ação de sistema
        # roubaria o foco. O sinal de "está em jogo" é o MODO JOGO — Modo Nativo
        # (native_mode_active) ou emulação suprimida (_emulation_suppressed, que os
        # perfis de jogo ligam e o long-press do PS alterna). Ambos são flags EM
        # MEMÓRIA — nada de subprocess aqui (o callback roda inline no poll loop; um
        # pgrep bloqueava input/IPC/co-op por até 2s — REVIEW-M5-PGREP-BLOCK-01).
        # Cobre também jogos NÃO-Steam (Lutris/Heroic/nativo), que a checagem por
        # processo Steam deixava passar (REVIEW-M5-NONSTEAM-FOCUS-01). No desktop
        # (sem modo jogo) a ação roda normal — abre a Steam. Combos PS+* seguem.
        store = getattr(daemon, "store", None)
        if store is not None and getattr(store, "native_mode_active", False):
            logger.info("hotkey_ps_solo_skip_native_mode")
            return
        if getattr(daemon, "_emulation_suppressed", False):
            logger.info("hotkey_ps_solo_skip_modo_jogo")
            return
        # A TECLA PRIMEIRO — ver o docstring: a Steam rouba o foco, e o que vier
        # depois dela chega à Steam.
        if digita and escolha is not None:
            _digitar_o_ps(daemon, escolha)
        if da_maquina == "steam":
            from hefesto_dualsense4unix.integrations.steam_launcher import open_or_focus_steam

            open_or_focus_steam()
        elif da_maquina == "custom":
            command = cfg.ps_button_command
            if not command:
                logger.warning("hotkey_ps_solo_custom_sem_comando")
                return
            with contextlib.suppress(Exception):
                _sp.Popen(
                    command,
                    stdin=_sp.DEVNULL,
                    stdout=_sp.DEVNULL,
                    stderr=_sp.DEVNULL,
                    start_new_session=True,
                )

    return _on_ps_solo


def build_ps_long_press_callback(daemon: DaemonProtocol) -> Any:
    """Cria o callback on_ps_long_press: alterna o modo jogo (supressao da
    emulacao de mouse/teclado). FEAT-EMULATION-GAMEMODE-LONGPRESS-01."""

    def _on_ps_long_press() -> None:
        daemon.set_emulation_suppressed()

    return _on_ps_long_press


#: FEAT-HOTKEY-PONTE-CYCLE-01 — as PONTES que o gesto PS+R3 percorre.
#: Ponte = a forma como o jogo enxerga o controle. A ordem é a de "chance de
#: pegar": máscara Xbox primeiro não, porque a casa parte do DualSense — a
#: ordem abaixo começa na máscara nativa e só depois cai no XInput.
PONTE_DUALSENSE = "dualsense"
PONTE_XBOX = "xbox"
PONTE_MOUSE_TECLADO = "mouse_teclado"
CICLO_DE_PONTES: tuple[str, ...] = (PONTE_DUALSENSE, PONTE_XBOX, PONTE_MOUSE_TECLADO)

#: AVISO-DE-MODO-01 — os DOIS modos que NÃO são ponte e que ela mesma nomeou
#: no pedido de 19/08/2026: *"entramos no modo steam input azul clarinho, modo
#: xbox verde claro, modo sony nativo branco"*. Não entram no `CICLO_DE_PONTES`
#: (o gesto não liga Steam Input nem entra em Modo Nativo — ver
#: `build_next_bridge_callback`), mas o AVISO vale para eles igual: quem troca
#: pela janela tem de ver a mesma coisa que quem troca pelo gesto.
MODO_STEAM_INPUT = "steam_input"
MODO_NATIVO = "nativo"

#: Cor da lightbar de cada MODO — o ÚNICO canal que ela enxerga sem sair do
#: jogo. Os hex saem da paleta de `gui/theme.css`, que é o léxico visual desta
#: casa: `cyan` #8be9fd, `green` #50fa7b, `fg` #f8f8f2, `pink` #ff79c6 (a cor de
#: MARCA do produto) e `orange` #ffb86c. Inventar cor nova aqui seria dizer na
#: barra uma coisa que a janela não diz.
#:
#: SUBSTITUI (19/08/2026) o `CORES_DA_PONTE` de 18/08, em que a máscara
#: DualSense era AZUL (0, 60, 255). Não é decisão apagada, é fato corrigido: o
#: azul claro passou a significar **Steam Input** por decisão dela, e deixar os
#: dois azuis lado a lado tornaria a barra ilegível justamente no par que ela
#: mais precisa distinguir. A máscara DualSense é o "Hefesto na frente", e a
#: cor do Hefesto é o rosa da marca.
CORES_DO_MODO: dict[str, tuple[int, int, int]] = {
    MODO_STEAM_INPUT: (139, 233, 253),
    PONTE_XBOX: (80, 250, 123),
    MODO_NATIVO: (248, 248, 242),
    PONTE_DUALSENSE: (255, 121, 198),
    PONTE_MOUSE_TECLADO: (255, 184, 108),
}
#: Aviso de RISCO: a troca de máscara destrói e recria o vpad, e foi MEDIDO
#: (R-04) que isso invalida o handle que o jogo abriu. Dois pulsos vermelhos
#: antes de aplicar = "isto pode derrubar o controle dentro do jogo".
#: Falha ao construir a ponte (o vpad não subiu): os mesmos pulsos vermelhos
#: seguidos de um vermelho longo — "pedi e não consegui", que é diferente de
#: "consegui e pode ter derrubado o jogo".
COR_AVISO_RISCO = (255, 0, 0)
#: Duração de um pulso, em segundos.
PULSO_SEG = 0.14

#: Sentinela do "ainda não anunciei nada". O boot NÃO é troca de modo: um
#: daemon que sobe já em máscara DualSense não pode piscar como se ela tivesse
#: acabado de mexer em alguma coisa. `None` não serve de sentinela porque
#: `modo_vigente` nunca devolve `None` — mas um daemon dublado sem o atributo e
#: um daemon que já anunciou têm de ser distinguíveis, e é isso que o objeto
#: único abaixo faz.
_NUNCA_ANUNCIADO = object()

#: Uma piscada por vez. O aviso é level-triggered e quem o chama passa de novo
#: no tique seguinte, então uma troca que caiu em cima de outra piscada não se
#: perde: ela só não CARIMBA o modo anunciado, e a próxima passada tenta outra
#: vez. Enfileirar meio segundo de piscada por apertada seria o aviso ficando
#: para trás da mão dela.
_AVISO_EM_CURSO = threading.Lock()


def ponte_atual(daemon: DaemonProtocol) -> str:
    """A ponte de pé AGORA, lida do estado VIVO — não da config.

    O estado vivo é o vpad: se existe, a ponte é a máscara dele; se não
    existe, o controle está indo para o desktop (mouse+teclado). Ler do
    `config.gamepad_flavor` seria repetir o defeito da noite de 18/08, em que
    o perfil dizia `xbox` e o vivo dizia `dualsense` — e o daemon ficou
    destruindo e recriando o vpad em laço por acreditar no papel.
    """
    from hefesto_dualsense4unix.integrations.uinput_gamepad import normalize_flavor

    device = getattr(daemon, "_gamepad_device", None)
    if device is None:
        return PONTE_MOUSE_TECLADO
    return normalize_flavor(getattr(device, "flavor", None))


def _cor_do_degrau(degrau: Any) -> tuple[int, int, int] | None:
    """A cor de `CORES_DO_MODO` que anuncia um degrau da `ESCADA`.

    Serve ao aviso do degrau PULADO, e por isso ela é a cor do MODO, não a da
    máscara: o que ela precisa distinguir é *"o Nativo ficou para o
    lançamento"* de *"o Steam Input ficou para o lançamento"*. Steam Input
    primeiro de propósito — o degrau `gamepad/dualsense+steam_input` é as duas
    coisas, e quem manda nele é a Steam, não a máscara que viaja por baixo.

    `None` para o que não tem cor, e o chamador simplesmente não pisca: um
    degrau sem cor não pode derrubar a troca que ela pediu.
    """
    ponte = getattr(degrau, "ponte", None)
    if ponte is None:
        return None
    if getattr(ponte, "steam_input", False):
        return CORES_DO_MODO.get(MODO_STEAM_INPUT)
    from hefesto_dualsense4unix.integrations import ponte_escada

    if getattr(ponte, "kind", None) == ponte_escada.KIND_NATIVE:
        return CORES_DO_MODO.get(MODO_NATIVO)
    return CORES_DO_MODO.get(getattr(ponte, "mascara", None) or "")


def proxima_ponte(atual: str) -> str:
    """A ponte seguinte no ciclo, com wrap-around. Desconhecida → a primeira."""
    if atual not in CICLO_DE_PONTES:
        return CICLO_DE_PONTES[0]
    return CICLO_DE_PONTES[(CICLO_DE_PONTES.index(atual) + 1) % len(CICLO_DE_PONTES)]


async def _sinalizar_lightbar(
    daemon: DaemonProtocol, cores: list[tuple[tuple[int, int, int], float]]
) -> None:
    """Pinta uma sequência (cor, segundos) na lightbar e devolve a cor resolvida.

    A lightbar é o único canal que ela enxerga sem sair do jogo — não há
    notificação de desktop que apareça por cima de um jogo em tela cheia.
    Best-effort: falha de HID aqui NUNCA pode derrubar a troca de ponte, que
    é o que ela pediu.

    **CONSERTO de 19/08/2026 (AVISO-DE-MODO-01): o aviso ROUBAVA a cor dela.**
    Esta função pintava com `controller.set_led`, e o `set_led` GRAVA a cor no
    estado desejado — no caminho broadcast o `_record_desired_locked` ainda
    LIMPA o campo `led` de todos os overrides por-uniq. O
    `reassert_resolved_outputs` do fim, então, devolvia fielmente… a cor do
    AVISO, porque era ela que estava gravada. Duas voltas do gesto e a cor do
    perfil dela tinha sumido de vez. Agora o par usado é o
    `pintar_lightbar_sem_lembrar` / `restaurar_lightbar_do_perfil`, que não
    grava nada e por isso tem o que devolver.

    Também passa a pintar em TODOS os controles (o `set_led` obedecia ao
    seletor da janela) e a sair pelas três rotas — inclusive o `0x31` avulso
    por rádio, que é o que pinta com a Steam segurando o nó.

    HONESTIDADE: com um jogo que pinta a lightbar sozinho (a defesa de
    exibição do backend repassa o que o jogo escreve), este aviso pode ser
    sobrepintado em seguida. É sinal, não garantia.
    """
    pintar = getattr(daemon.controller, "pintar_lightbar_sem_lembrar", None)
    for cor, segundos in cores:
        if pintar is not None:
            with contextlib.suppress(Exception):
                await daemon._run_blocking(pintar, cor)
        if segundos > 0:
            await asyncio.sleep(segundos)
    devolver = getattr(daemon.controller, "restaurar_lightbar_do_perfil", None)
    if devolver is None:
        devolver = getattr(daemon.controller, "reassert_resolved_outputs", None)
    if devolver is not None:
        with contextlib.suppress(Exception):
            await daemon._run_blocking(devolver)


def modo_vigente(daemon: DaemonProtocol) -> str:
    """O MODO de pé AGORA, lido do estado VIVO. AVISO-DE-MODO-01.

    Superconjunto de `ponte_atual`: acrescenta os dois estados que não são
    ponte e que mudam o que o jogo enxerga tanto quanto uma máscara.

    A ordem de precedência é a de quem está NA FRENTE do controle:

    1. **Modo Nativo** primeiro, porque nele o dono do aparelho é o jogo — não
       há vpad para consultar e não há máscara nossa em lugar nenhum;
    2. **Steam Input** depois: com a exceção por appid valendo, quem entrega o
       dispositivo ao jogo é a Steam, mesmo com o nosso vpad de pé. Os dois
       flags são lidos (`_steam_input_excecao` e `_steam_input_vpad_suspenso`)
       porque eles não andam sempre juntos — o par distingue "exceção ativa com
       o vpad recolhido" de "exceção ativa e a suspensão não pôde ser armada",
       e nos DOIS quem está na frente é a Steam;
    3. **a ponte**, que é o caso comum.

    Tudo por `getattr`/`suppress`: daemons dublados de teste não têm store nem
    os flags, e um aviso NUNCA pode derrubar o laço que o chama.
    """
    store = getattr(daemon, "store", None)
    if store is not None and getattr(store, "native_mode_active", False):
        return MODO_NATIVO
    with contextlib.suppress(Exception):
        checar = getattr(daemon, "is_native_mode", None)
        if callable(checar) and bool(checar()):
            return MODO_NATIVO
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
            steam_input_excecao_ativa,
            steam_input_vpad_suspenso,
        )

        if steam_input_excecao_ativa(daemon) or steam_input_vpad_suspenso(daemon):
            return MODO_STEAM_INPUT
    return ponte_atual(daemon)


def _disparar_piscada(
    daemon: DaemonProtocol, cor: tuple[int, int, int], *, modo: str
) -> bool:
    """Manda a piscada para uma thread. True = saiu daqui. AVISO-DE-MODO-01.

    A piscada é BLOQUEANTE (meio segundo de `time.sleep` no backend) e quem
    chama o aviso é o poll loop — segurar o laço do controle por meio segundo
    para acender uma luz seria trocar a rota do jogo por um enfeite. Thread
    `daemon=True`: um aviso no ar nunca segura o desligamento do produto.
    """
    piscar = getattr(getattr(daemon, "controller", None), "piscar_aviso_de_modo", None)
    if not callable(piscar):
        # Backend sem a piscada (fake da bancada, controle desconectado): o
        # modo mudou do mesmo jeito e o journal registra — o produto não trava
        # nem finge que avisou.
        logger.debug("aviso_de_modo_sem_backend", modo=modo)
        return False
    if not _AVISO_EM_CURSO.acquire(blocking=False):
        logger.debug("aviso_de_modo_sobreposto", modo=modo)
        return False

    def _correr() -> None:
        try:
            escritas = piscar(cor)
        except Exception as exc:
            logger.warning("aviso_de_modo_falhou", modo=modo, err=str(exc))
            return
        finally:
            _AVISO_EM_CURSO.release()
        # `escritas` = controles que RECEBERAM a escrita, não que acenderam. A
        # barra por rádio pode nascer travada (medido: ignora as escritas do
        # kernel até o power-off físico), e não há leitura que desminta isso —
        # o `multi_intensity` é a memória do que se PEDIU. Dizer "acendeu" aqui
        # seria o journal mentindo.
        logger.info(
            "aviso_de_modo_piscado", modo=modo, cor=cor, controles_escritos=escritas
        )

    threading.Thread(
        target=_correr, name="hefesto-aviso-de-modo", daemon=True
    ).start()
    return True


def avisar_troca_de_modo(daemon: DaemonProtocol) -> str | None:
    """Pisca em TODOS os controles quando o MODO muda. AVISO-DE-MODO-01.

    Pedido dela, 19/08/2026: *"um alerta visual no lightbar de todos os
    controles dualsense conectados, seja via bt, seja via cabo. seja com steam
    aberta ou não"* — e *"o lightbar de todos pisca 3 vezes rápido"*.

    **Por que é level-triggered, e não um callback do gesto.** Ela troca de
    modo por quatro portas: o gesto no controle, a janela, a CLI/IPC e o
    autoswitch por jogo. Pendurar o aviso no callback do gesto faria a barra
    dizer a verdade só numa delas — e o combinado é que o controle diga o modo,
    não que ele conte quem mexeu. Comparando o estado VIVO com o último modo
    ANUNCIADO, toda troca acende, tenha vindo de onde tiver vindo. É a mesma
    disciplina do `ponte_atual`: acreditar no vivo, nunca no papel.

    **O boot não é troca.** Na primeira passada o modo só é memorizado — um
    daemon que sobe já em máscara DualSense não pode piscar como se ela tivesse
    acabado de mexer em alguma coisa.

    **Só carimba o que ANUNCIOU.** Se a piscada não saiu (backend sem a rota,
    outra piscada no ar), o modo NÃO é registrado como anunciado, e a próxima
    passada tenta de novo. O carimbo é a prova de que o aviso saiu, e não um
    "eu vi que mudou".

    Devolve o modo anunciado, ou `None` quando não houve o que anunciar.
    """
    modo = modo_vigente(daemon)
    anterior = getattr(daemon, "_modo_anunciado", _NUNCA_ANUNCIADO)
    if modo == anterior:
        return None
    if anterior is _NUNCA_ANUNCIADO:
        with contextlib.suppress(Exception):
            daemon._modo_anunciado = modo  # type: ignore[attr-defined]
        logger.debug("aviso_de_modo_primeira_leitura", modo=modo)
        return None
    cor = CORES_DO_MODO.get(modo)
    if cor is None:
        # Modo sem cor no léxico: registrar e seguir. Piscar uma cor inventada
        # seria a barra dizendo uma coisa que a janela não diz.
        logger.warning("aviso_de_modo_sem_cor", modo=modo, de=anterior)
        with contextlib.suppress(Exception):
            daemon._modo_anunciado = modo  # type: ignore[attr-defined]
        return None
    if not _disparar_piscada(daemon, cor, modo=modo):
        return None
    with contextlib.suppress(Exception):
        daemon._modo_anunciado = modo  # type: ignore[attr-defined]
    logger.info("aviso_de_modo_trocado", de=anterior, para=modo, cor=cor)
    return modo


def _aplicar_ponte(daemon: DaemonProtocol, alvo: str) -> bool:
    """Constrói a ponte `alvo`. True = de pé ao final.

    Chamado SÍNCRONO (não pelo executor) de propósito: é a decisão já
    registrada em `ipc_handlers._handle_gamepad_emulation_set` (Achado Onda S
    #6) — a parte bloqueante da cadeia já foi para o executor do broker, e
    jogar o setter inteiro numa thread criaria corrida real com o
    `coop.sync()` do poll loop.

    `origin="manual"` é o que faz o gesto valer: é a ÚNICA origem que o gate
    R-04 (`gamepad._recriacao_bloqueada_por_jogo`) deixa passar com o jogo
    aberto, e a casa já decidiu por escrito que "trocar de máscara com o jogo
    aberto é uma escolha legítima dela; a última palavra é sempre da usuária".
    O kwarg é chamado por `getattr` porque o `DaemonProtocol` ainda não o
    declara (existe no Daemon real — `lifecycle.py:1572`) e o Protocol é
    arquivo de outra frente nesta leva.
    """
    setter = getattr(daemon, "set_gamepad_emulation", None)
    if setter is None:
        logger.warning("ponte_sem_setter_de_gamepad")
        return False
    if alvo in (PONTE_DUALSENSE, PONTE_XBOX):
        return bool(setter(True, alvo, origin="manual"))
    # Ponte mouse+teclado (point and click): sem vpad, o controle vira
    # cursor/teclas. A supressão (modo jogo) tem de cair junto — senão a ponte
    # sobe muda, porque é ela que gateia o dispatch de mouse/teclado no poll
    # loop — e é gesto dela, então o toggle manual é legítimo.
    setter(False, origin="manual")
    with contextlib.suppress(Exception):
        daemon.set_emulation_suppressed(False)
    with contextlib.suppress(Exception):
        # `origin="manual"` porque É gesto dela: o `PS + R3` é a
        # vontade explícita da usuária, e é o único origin que atravessa o
        # gate R-04 (`_recriacao_bloqueada_por_jogo`). Vir sem ele reprovaria
        # o mypy — o protocolo exige o parâmetro justamente para ninguém
        # trocar de ponte "por engano" no meio da partida.
        daemon.set_mouse_emulation(True, origin="manual")
    with contextlib.suppress(Exception):
        # SEGUNDO-ESCRITOR-01 (22/08/2026): esta linha é o segundo escritor da
        # `keyboard_emulation.flag`, e por isso ela tem eco na janela. O
        # `set_keyboard_emulation` persiste por padrão
        # (`daemon/protocols.py:180`), então o gesto não liga o teclado só para
        # esta partida — grava a escolha. Enquanto a janela era o único caminho
        # até a flag, o interruptor da aba Navegação não era relido ao entrar na
        # aba; agora é (`app/app.py`, `_REFRESH_POR_ABA["tab_navegacao_dsx"]`).
        # Quem for recontar escritores: o grep é por `set_keyboard_emulation(`,
        # não por `keyboard.emulation.set` — o nome do método IPC não pega esta
        # chamada, que é em processo, e foi esse grep que sustentou a razão
        # caduca.
        daemon.set_keyboard_emulation(True)
    return True


def _appid_do_jogo_do_wrapper() -> int | None:
    """O appid do jogo que o wrapper lançou e que ainda roda, ou None.

    Fachada de UMA linha sobre `launch_env.launch_session_appid`, e ela existe
    para que o gesto não ganhe uma terceira definição de *"que jogo é este"*:
    é o mesmo sinal que sustenta o `game_signal`, a exceção do R-06 e o desvio
    da allowlist. Import local porque `launch_env` é do pacote de cima e este
    módulo é carregado pelo poll loop — a mesma disciplina dos vizinhos que
    importam `profiles` dentro da função.

    `None` quando não há jogo do wrapper rodando, e isso é uma RECUSA, não uma
    falta: sem appid não há perfil de jogo para receber a máscara, e escrever
    no perfil errado é pior que não escrever.
    """
    from hefesto_dualsense4unix.daemon.launch_env import launch_session_appid

    return launch_session_appid()


def build_next_bridge_callback(daemon: DaemonProtocol) -> Any:
    """Cria o callback do gesto PS + R3: PRÓXIMA PONTE.

    FEAT-HOTKEY-PONTE-CYCLE-01. Ponte = a forma como o jogo enxerga o
    controle. Ela pediu poder trocar de ponte SEM fechar o jogo, com um gesto
    no controle; o ciclo é `dualsense → xbox → mouse+teclado → dualsense`.

    PONTE-ESCADA-LACO-01 (19/08/2026) — o gesto ganhou um SEGUNDO leitor, e
    não uma segunda regra. O que ele faz não mudou: sempre troca, na hora,
    com `origin="manual"`. O que mudou é que agora alguém ESCUTA:

    - **para o laço da escada, este gesto significa "o degrau de pé não
      funcionou"**. É o único sinal que a escada tem, e é dela que ela
      aprende (`ponte_tentativa.avancar_por_gesto`);
    - com uma tentativa em curso, o ALVO passa a ser o próximo degrau da
      `ESCADA` em vez do próximo item do `CICLO_DE_PONTES`. A diferença é o
      dado por trás: a ordem da escada é justificada linha a linha contra o
      `mapa-controles.csv`; a do ciclo era um arranjo;
    - sem tentativa — jogo com ponte CONFIRMADA, ou nenhum jogo — o alvo volta
      a ser o do ciclo. **E o gesto continua trocando mesmo num jogo
      confirmado**: recusar seria o produto discutindo com a dona. Quem não
      roda em jogo confirmado é a ESCADA, que é o caminho automático.

    A MÁSCARA DO GESTO VOLTA PARA O PERFIL (29/08/2026). O gesto sozinho
    continua não confirmando nada — ele é o contrário de uma confirmação. O que
    mudou é que ele deixa RASTRO: a máscara que ficou de pé é anotada
    (`ponte_tentativa.gesto_deixou_de_pe`), e se ela parar de apertar e
    continuar jogando, o tique de 1 Hz grava essa máscara no perfil do jogo —
    carimbo `POR_GESTO` **e** `mode.gamepad_flavor`, porque num perfil que opina
    o carimbo sozinho não muda o próximo lançamento. Sem isso, o gesto era um
    trabalho que ela refazia a cada abertura: 24 apertos em 7 dias, medidos no
    journal, com 23 perfis pedindo `dualsense` e ela jogando em `xbox`.

    O QUE O GESTO PROMETE:
      - troca a ponte na hora, com `origin="manual"` — a única origem que
        atravessa o gate R-04 com o jogo aberto;
      - avisa pela lightbar qual ponte ficou de pé, e avisa ANTES quando a
        troca corre risco de derrubar o controle dentro do jogo;
      - é sempre reversível pelo próprio gesto: nenhuma ponte do ciclo mata o
        caminho de volta pelo controle, e **não há exceção que custe um
        aperto**. Um degrau que só o lançamento alcança é PULADO, com aviso na
        lightbar e no journal — ver `pulados` no corpo.

    E O GESTO SE COMPORTA IGUAL EM TODO JOGO (30/08/2026,
    `D-O-GESTO-DA-PONTE-E-UNIVERSAL-NAO-APRENDE-POR-JOGO`). Decisão dela:
    *"pera, pq isso tá sob a identidade de um jogo específico? Isso deveria ser
    universal — não é produto, é gambiarra!"*

    Até esta data o gesto dependia de o jogo ter carimbo. Com carimbo a escada
    não roda e todo aperto anda o `CICLO_DE_PONTES`; sem carimbo, o 2º aperto
    pedia o degrau `native`, que exige REABRIR o jogo, e morria ali. Medido com
    os quatro jogos dela, quatro apertos cada: **3 trocas em 4 apertos no
    Sackboy (sem carimbo) contra 4 em 4 nos três carimbados** — e o usuário
    novo, que não tem carimbo em jogo nenhum, tinha o pior comportamento em
    todos.

    A cura é no GESTO e em nada mais: o degrau que não se alcança ao vivo é
    pulado (`ponte_tentativa.avancar_por_gesto`), e a `ESCADA`, o `como_subir`
    e o `comecar` do lançamento ficaram intactos. O que ela usa o gesto para
    fazer é *"testar a bridge sem fechar o jogo"* — e um degrau que exige
    fechar o jogo não pertence a ele.

    O QUE O GESTO NÃO PROMETE (medido, não suposto):
      - NÃO garante que o jogo sobreviva à troca. A troca de máscara destrói e
        recria o vpad (`gamepad.py:1867` para, `:1892` cria — slot único, sem
        double-buffer na árvore), e foi medido em 23/07 que recriar o vpad com
        o jogo rodando invalida os handles que ele abriu: a Steam não reabre o
        hidraw do vpad do P1. Jogo que já estava com o controle na mão pode
        precisar de um replug lógico (menu de controles do jogo) ou de
        reabrir. Por isso o aviso vermelho vem ANTES de aplicar;
      - NÃO liga o Steam Input. Nenhuma linha deste repositório liga o Steam
        Input; o guard o DESLIGA e a allowlist só PRESERVA o que já estava
        ligado (o estorvo `excecao_inerte` do `prontuario_dos_jogos.py` diz
        isso com todas as letras). Ponte de Steam Input é escolha na Steam,
        não gesto no controle;
      - NÃO entra nem sai do MODO NATIVO. Medido: o `observe` do hotkey roda
        DEPOIS do gate do nativo no poll loop (`lifecycle.py`: `input_ready =
        grace_passed and not self._paused and not self._native_mode`, e o
        `observe` só é chamado abaixo dele). Entrar em Modo Nativo mataria o
        vpad SEM consultar o R-04 e, pior, mataria o próprio gesto: não
        haveria porta de volta pelo controle. Beco sem saída não entra em
        ciclo. Para o Modo Nativo continuam valendo a GUI, a CLI e o IPC.
    """

    async def _ciclar_ponte() -> None:
        # Cinto e suspensório: em Modo Nativo o gesto nem chega aqui (o gate do
        # poll loop congela o dispatch antes do `observe`). Se um dia chegar —
        # outro caller, outro gate — a resposta é não fazer nada, pelo motivo
        # do docstring: o nativo não tem porta de volta pelo controle.
        store = getattr(daemon, "store", None)
        if store is not None and getattr(store, "native_mode_active", False):
            logger.info("ponte_ciclo_skip_native_mode")
            return

        atual = ponte_atual(daemon)
        # `display_authority == "game"` é o MESMO sinal que o R-04 consulta
        # (`gamepad._autoridade_do_jogo`) — quem responde "há jogo com o
        # controle na mão AGORA?".
        jogo_no_controle = getattr(daemon, "display_authority", "unknown") == "game"

        # PONTE-ESCADA-LACO-01, momento 2 (19/08/2026). O gesto TROCA de
        # qualquer jeito — a linha abaixo não decide SE troca, decide PARA
        # ONDE. Com uma tentativa de escada em curso (jogo sem carimbo), o
        # próximo degrau da `ESCADA` vence o `CICLO_DE_PONTES`, porque é ele
        # que carrega o dado: o mapa de canais diz por que a máscara DualSense
        # vem antes da Xbox, e o ciclo fixo não dizia nada. Sem tentativa —
        # jogo com carimbo, ou nenhum jogo — `passo` é `None` e o gesto faz
        # exatamente o que fazia ontem.
        passo = None
        with contextlib.suppress(Exception):
            passo = ponte_tentativa.avancar_por_gesto(
                daemon, jogo_vivo=jogo_no_controle
            )
        degrau_da_escada = None
        if passo is not None and passo.mascara is not None:
            alvo = passo.mascara
            degrau_da_escada = passo.degrau
        else:
            # Inclui o degrau caro, o caso em que a escada acabou, e o jogo sem
            # tentativa nenhuma (carimbado, ou fora do wrapper). O gesto não
            # pode ficar sem resposta: ela apertou, e alguma coisa tem de
            # mudar. Volta ao ciclo de sempre.
            alvo = proxima_ponte(atual)

        logger.info(
            "ponte_troca_pedida_por_gesto",
            de=atual,
            para=alvo,
            jogo_com_autoridade=jogo_no_controle,
            escada=passo.motivo if passo is not None else None,
            pulados=[d.ponte.chave for d in passo.pulados] if passo else [],
        )

        # O DEGRAU CARO NÃO SOME EM SILÊNCIO (29/08/2026,
        # `D-O-GESTO-DA-PONTE-E-UNIVERSAL-NAO-APRENDE-POR-JOGO`). A escada
        # acabou de pular um degrau que só o LANÇAMENTO alcança, e ela tem de
        # saber disso sem sair do jogo — senão a única diferença visível entre
        # "pulei o Nativo" e "o ciclo de sempre" é nenhuma.
        #
        # A cor é a do MODO pulado, e ela não é nova: são as três que ela mesma
        # nomeou em 19/08 — *"modo steam input azul clarinho, modo xbox verde
        # claro, modo sony nativo branco"*. Até hoje `MODO_NATIVO` e
        # `MODO_STEAM_INPUT` estavam em `CORES_DO_MODO` sem ninguém que as
        # pintasse; este é o caminho que faltava.
        for degrau_pulado in passo.pulados if passo is not None else ():
            cor_pulada = _cor_do_degrau(degrau_pulado)
            if cor_pulada is None:
                continue
            await _sinalizar_lightbar(
                daemon,
                [
                    (cor_pulada, PULSO_SEG * 2),
                    ((0, 0, 0), PULSO_SEG),
                    (cor_pulada, PULSO_SEG * 2),
                    ((0, 0, 0), PULSO_SEG),
                ],
            )

        if jogo_no_controle:
            # Aviso ANTES de aplicar: dois pulsos vermelhos = "o jogo pode
            # perder o controle nesta troca". Prometer troca ao vivo indolor
            # seria mentir — a medição do R-04 não sustenta isso.
            await _sinalizar_lightbar(
                daemon,
                [
                    (COR_AVISO_RISCO, PULSO_SEG),
                    ((0, 0, 0), PULSO_SEG),
                    (COR_AVISO_RISCO, PULSO_SEG),
                    ((0, 0, 0), PULSO_SEG),
                ],
            )

        ok = _aplicar_ponte(daemon, alvo)
        efetiva = ponte_atual(daemon)
        if degrau_da_escada is not None and efetiva == alvo:
            # A escada só anda depois que o APARELHO concorda. `ok` vale True
            # para três desfechos diferentes (aplicou, já-estava, bloqueado —
            # MASCARA-01), e avançar a tentativa por ele faria o gesto
            # seguinte pular o degrau que nunca chegou a ser tentado.
            with contextlib.suppress(Exception):
                ponte_tentativa.degrau_subiu(daemon, degrau_da_escada)
        if efetiva == alvo:
            # A MÁSCARA DO GESTO VOLTA PARA O PERFIL (29/08/2026). Aqui, e só
            # aqui, porque a prova é o APARELHO: a comparação acima é a mesma
            # disciplina da MASCARA-01, e anotar pelo retorno do applier
            # anotaria uma ponte que não subiu.
            #
            # `gesto_deixou_de_pe` recusa sozinho o que não é dele — sem jogo
            # vivo, sem appid, máscara fora das duas, ou tentativa de escada em
            # curso (esse caminho já tem dono). O que sobra é o caso que mais
            # custa a ela: o jogo que o produto JÁ "sabia", em que a escada não
            # roda e o gesto dela não deixava rastro nenhum. Medido: 24 apertos
            # em 7 dias, porque os 23 perfis de jogo dela pedem `dualsense` e
            # ela joga em `xbox`.
            with contextlib.suppress(Exception):
                ponte_tentativa.gesto_deixou_de_pe(
                    daemon,
                    appid=_appid_do_jogo_do_wrapper(),
                    mascara=efetiva,
                    jogo_vivo=jogo_no_controle,
                )
        logger.info(
            "ponte_trocada_por_gesto",
            de=atual,
            para=alvo,
            efetiva=efetiva,
            ok=ok,
            jogo_com_autoridade=jogo_no_controle,
        )
        if store is not None:
            with contextlib.suppress(Exception):
                store.bump("hotkey.ponte.cycled")

        if ok and efetiva == alvo:
            # QUEM PINTA A COR DO MODO NÃO É DAQUI (AVISO-DE-MODO-01,
            # 19/08/2026). O gesto pintava a cor da ponte nova aqui mesmo, e
            # por isso a barra só dizia a verdade quando a troca vinha DO
            # GESTO — trocar pela janela não acendia nada. O aviso passou a ser
            # level-triggered em `avisar_troca_de_modo`, disparado do ponto por
            # onde toda troca passa; pintar de novo aqui daria piscada dupla no
            # único caminho que já estava certo.
            return
        # A ponte NÃO subiu (vpad recusado, uinput/uhid fora do ar). Dizer isso
        # é obrigatório: `set_gamepad_emulation` devolve True para três
        # desfechos diferentes (aplicou, já-estava, bloqueado), então o sinal
        # honesto é comparar com o estado VIVO, e não confiar no retorno.
        logger.warning("ponte_nao_subiu", pedida=alvo, efetiva=efetiva, retorno=ok)
        await _sinalizar_lightbar(
            daemon,
            [
                (COR_AVISO_RISCO, PULSO_SEG),
                ((0, 0, 0), PULSO_SEG),
                (COR_AVISO_RISCO, PULSO_SEG),
                ((0, 0, 0), PULSO_SEG),
                (COR_AVISO_RISCO, PULSO_SEG * 3),
            ],
        )

    return _ciclar_ponte


def build_profile_cycle_callback(daemon: DaemonProtocol, direction: int) -> Any:
    """Cria o callback on_next (+1) / on_prev (-1): cicla para o perfil
    seguinte/anterior e o ativa — triggers + LEDs + key_bindings + marca ativo +
    notifica — reusando ProfileManager.activate, o MESMO caminho do profile.switch
    (IPC) e do restore_last_profile. FEAT-HOTKEY-PROFILE-CYCLE-01.

    Antes os combos PS+D-pad estavam disabled_until_wired: o observe() disparava
    com cb=None (no-op) mas ainda suprimia o D-pad e o PS-solo — gesto morto que
    comia o D-pad. Agora o cb troca de perfil de verdade.

    Feedback in-hand (você está com o controle na mão): flasha o lightbar em
    branco antes do activate() repintar a cor do perfil novo, então há sinal
    visível mesmo que dois perfis tenham a mesma cor. O sleep roda em task
    própria (não bloqueia o poll loop).
    """

    async def _cycle() -> None:
        import functools
        import time as _time

        from hefesto_dualsense4unix.daemon.state_store import MANUAL_PROFILE_LOCK_SEC
        from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon
        from hefesto_dualsense4unix.utils.session import save_active_marker

        # FEAT-NATIVE-MODE-01: em Modo Nativo o controle está solto para o jogo —
        # o ciclo de perfil (PS+dpad) NÃO troca de perfil (re-escreveria gatilhos).
        store = getattr(daemon, "store", None)
        if store is not None and getattr(store, "native_mode_active", False):
            logger.info("profile_cycle_skip_native_mode")
            return

        # A-FÁBRICA-COM-UM-CLIENTE-01 (22/08/2026): a lista de appliers vem da
        # FÁBRICA — paridade com o `profile.switch` (IPC), o autoswitch e o
        # lançamento por ser a MESMA lista, não por ser uma cópia fiel dela.
        # O que este gesto tem de próprio é o `origin="manual"` lá embaixo: o
        # ciclo PS+D-pad é troca explícita dela, e é o ÚNICO caminho por onde o
        # `mic.muted` do perfil atravessa (MIC-GRAVACAO-01).
        manager = gerente_do_daemon(daemon, store=daemon.store)
        profiles = await daemon._run_blocking(manager.list_profiles)
        if len(profiles) < 2:
            logger.info("profile_cycle_skip", n=len(profiles))
            return
        names = [p.name for p in profiles]
        active = daemon.store.active_profile
        idx = names.index(active) if active in names else 0
        target = names[(idx + direction) % len(names)]

        # Feedback visual imediato; activate() repinta a cor do perfil a seguir.
        with contextlib.suppress(Exception):
            await daemon._run_blocking(daemon.controller.set_led, (255, 255, 255))
            await asyncio.sleep(0.12)

        # Gesto explícito do usuário: libera o autoswitch e arma o lock manual
        # (paridade com _handle_profile_switch) — senão o autoswitch desfaz a
        # troca no próximo tick por causa da janela ativa.
        #
        # TRAVA-QUE-SOLTA-TARDE-01 (medido ao vivo, 05/08): estas duas linhas
        # vinham DEPOIS do `activate`, e o comentário acima ("paridade com
        # _handle_profile_switch") era literal — a paridade copiou a ordem
        # errada do irmão. Com a trava ainda armada durante o `activate`, o
        # `manager.apply` pulava as categorias travadas, e a promessa do
        # `speaker_applier` logo acima (SOM-02/E4: *"limpa as categorias
        # travadas (inclusive `audio`) e portanto aplica o volume do perfil que
        # entra"*) não se cumpria. Este é o gesto que ela usa DENTRO do jogo.
        # `getattr` pelo mesmo motivo que `ProfileManager._categorias_travadas`
        # (`profiles/manager.py:384-387`): dublês de teste e stores parciais
        # continuam funcionando, e "não sei listar" vira "nada a restaurar".
        travadas_antes = getattr(daemon.store, "manual_override_categories", ()) or ()
        lock_antes = getattr(daemon.store, "_manual_profile_lock_until", 0.0)
        daemon.store.clear_manual_trigger_active()
        daemon.store.mark_manual_profile_lock(
            _time.monotonic() + MANUAL_PROFILE_LOCK_SEC
        )
        # PERFIL-03: botão físico no controle = gesto MANUAL — origin="manual"
        # persiste a intenção em session.json (paridade com o profile.switch).
        # `functools.partial` porque `_run_blocking(fn, *args)` só aceita
        # posicionais e `origin` é keyword-only.
        try:
            profile = await daemon._run_blocking(
                functools.partial(manager.activate, target, origin="manual")
            )
        except Exception:
            # Ativação que falhou não é gesto cumprido — devolve a trava E o
            # lock que ela tinha, como faz o `_handle_profile_switch`. Sem o
            # lock de volta, um ciclo que falha congelaria a troca automática
            # por 30 s sem gesto nenhum cumprido.
            for categoria in travadas_antes:
                daemon.store.mark_manual_trigger_active(categoria)
            daemon.store.mark_manual_profile_lock(lock_antes)
            raise
        with contextlib.suppress(Exception):
            save_active_marker(profile.name)
        logger.info("profile_cycled", direction=direction, to=profile.name)

    return _cycle


def start_hotkey_manager(daemon: DaemonProtocol) -> None:
    """Instancia HotkeyManager e atribui a daemon._hotkey_manager.

    BUGFIX: o HotkeyManager era criado sem config, ignorando
    `daemon.config.ps_long_press_ms` (ficava preso no default 1000ms). Agora a
    config do daemon é propagada — inclusive 0 = desliga o long-press do PS.
    """
    from hefesto_dualsense4unix.integrations.hotkey_daemon import (
        DEFAULT_COMBO_NEXT,
        DEFAULT_COMBO_PONTE,
        DEFAULT_COMBO_PREV,
        HotkeyConfig,
        HotkeyManager,
    )

    # FEAT-HOTKEY-PROFILE-CYCLE-01: os combos next/prev (PS+D-pad) agora estão
    # LIGADOS — on_next/on_prev ciclam o perfil via ProfileManager.activate (o
    # mesmo caminho do profile.switch). Antes ficavam disabled_until_wired: o
    # observe() disparava com cb=None (no-op) mas ainda comia o D-pad. Com o cb
    # de verdade, suprimir o D-pad durante o hold do PS é o comportamento certo
    # (você está trocando de perfil, não mirando). Modo-jogo segue no PS+Options.
    hotkey_config = HotkeyConfig(
        ps_long_press_ms=getattr(daemon.config, "ps_long_press_ms", 0),
        next_profile=DEFAULT_COMBO_NEXT,
        prev_profile=DEFAULT_COMBO_PREV,
        # FEAT-HOTKEY-PONTE-CYCLE-01: PS+R3 = próxima ponte.
        next_bridge=DEFAULT_COMBO_PONTE,
    )
    daemon._hotkey_manager = HotkeyManager(
        on_ps_solo=build_ps_solo_callback(daemon),
        on_ps_long_press=build_ps_long_press_callback(daemon),
        on_next=build_profile_cycle_callback(daemon, +1),
        on_prev=build_profile_cycle_callback(daemon, -1),
        on_next_bridge=build_next_bridge_callback(daemon),
        config=hotkey_config,
    )
    logger.info(
        "hotkey_manager_started",
        ps_button_action=daemon.config.ps_button_action,
        ps_long_press_ms=hotkey_config.ps_long_press_ms,
        next_prev_combos="ps+dpad_up / ps+dpad_down",
        ponte_combo="ps+r3",
    )


def stop_hotkey_manager(daemon: DaemonProtocol) -> None:
    """Descarta o HotkeyManager. Idempotente."""
    daemon._hotkey_manager = None


def start_mic_hotkey(daemon: DaemonProtocol) -> None:
    """Sobe os DOIS laços do microfone: as bordas com endereço, e a eleição.

    MIC-DA-MESA-ELEICAO-01: são dois de propósito. O primeiro só LÊ (dá `uniq`
    à borda, aplica sossego e carência) e o segundo só AGE (elege, confere,
    acende). Separá-los é o que permite recusar a eleição — que toca no áudio
    da máquina dela — sem perder a leitura do gesto.

    O `AudioControl` continua sendo criado aqui porque outros gestos ainda o
    usam; o gesto do microfone **não** o usa mais (ver `mic_button_loop`).
    """
    from hefesto_dualsense4unix.daemon.subsystems.mic_da_mesa import start_mic_da_mesa
    from hefesto_dualsense4unix.integrations.audio_control import AudioControl

    if daemon._audio is None:
        daemon._audio = AudioControl()
    start_mic_da_mesa(daemon)
    task = asyncio.create_task(mic_button_loop(daemon), name="mic_button_loop")
    daemon._tasks.append(task)
    # A QUARTA FACE DO ESTADO (MICROFONE-UM-ATO-01): o que o PipeWire diz sobre
    # o canal deste controle. Laço próprio, e não leitura no tique, porque o
    # `state_full` roda a 20 Hz no loop do daemon e cada resposta destas custa
    # um subprocesso — perguntar ali travaria o loop inteiro pelo tempo do
    # `pactl`. Aqui a pergunta é feita a cada dois segundos, numa thread, e o
    # tique só LÊ o que já está lido.
    tarefa_do_canal = asyncio.create_task(
        canal_do_microfone_loop(daemon), name="canal_do_microfone_loop"
    )
    daemon._tasks.append(tarefa_do_canal)
    logger.info("mic_hotkey_iniciado")


#: De quanto em quanto o canal de captura de cada controle é relido. Dois
#: segundos é o dobro do sossego das bordas: a tela mostra a mudança no ciclo
#: seguinte ao gesto, e a máquina paga dois subprocessos por controle nesse
#: intervalo, não vinte por segundo.
CANAL_TTL_S: float = 2.0

#: `{uniq: {fonte, canal_ativo, canal_mudo, volume_captura}}` — a última
#: leitura do PipeWire por controle. Nasce VAZIO de propósito: até a primeira
#: varredura o `state_full` não publica as chaves, e ausência é a resposta
#: honesta de quem ainda não perguntou. Inventar `false` aqui seria dizer "o
#: canal não está ativo" sobre um canal que ninguém olhou.
_CANAL_POR_UNIQ: dict[str, dict[str, Any]] = {}


def canal_do_microfone(uniq: str | None) -> dict[str, Any] | None:
    """O que o PipeWire disse sobre o canal deste controle, ou `None`.

    Leitura de dicionário, sem subprocesso: é o que o `state_full` chama.
    `None` = ainda não perguntamos (ou este controle não tem canal).
    """
    if not uniq:
        return None
    lido = _CANAL_POR_UNIQ.get(uniq)
    return dict(lido) if isinstance(lido, dict) else None


def _ler_o_canal(uniq: str) -> dict[str, Any]:
    """As três respostas do PipeWire sobre UM controle. Bloqueante.

    `canal_ativo` compara a fonte DESTE controle com a fonte ativa do sistema,
    e as duas leituras vêm dos donos que já existem — `fonte_de_captura_do_uniq`
    (o casamento por dispositivo USB, o mesmo do `mic.volume.set`) e
    `fonte_ativa` (que já sabe recusar `auto_null` e `.monitor`). Escrever uma
    terceira régua aqui daria ao selo uma verdade diferente da do gesto.
    """
    from hefesto_dualsense4unix.integrations.audio_control import (
        fonte_de_captura_do_uniq,
        volume_da_captura,
    )
    from hefesto_dualsense4unix.integrations.eleicao_de_microfone import fonte_ativa

    fonte = None
    with contextlib.suppress(Exception):
        fonte = fonte_de_captura_do_uniq(uniq)
    if not fonte:
        return {"fonte": None, "canal_ativo": False, "canal_mudo": None,
                "volume_captura": None}
    ativa = None
    with contextlib.suppress(Exception):
        ativa = fonte_ativa()
    volume = None
    with contextlib.suppress(Exception):
        volume = volume_da_captura(fonte=fonte)
    return {
        "fonte": fonte,
        "canal_ativo": bool(ativa) and ativa == fonte,
        "canal_mudo": _fonte_esta_muda(fonte),
        "volume_captura": volume,
    }


def _fonte_esta_muda(fonte: str) -> bool | None:
    """`pactl get-source-mute` — `None` quando a pergunta não teve resposta.

    `None` NÃO é `False`: "não sei se está muda" e "não está muda" levam a
    telas diferentes, e colapsá-las é o hábito que faz o selo prometer o que
    ninguém mediu.
    """
    import os
    import subprocess

    try:
        r = subprocess.run(
            ["pactl", "get-source-mute", fonte],
            capture_output=True,
            text=True,
            timeout=2.0,
            check=False,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    saida = (r.stdout or "").strip().lower()
    if saida.endswith("yes"):
        return True
    if saida.endswith("no"):
        return False
    return None


async def canal_do_microfone_loop(daemon: DaemonProtocol) -> None:
    """Relê o canal de cada controle da mesa, a cada `CANAL_TTL_S`.

    **A ARMADILHA QUE ELE EVITA, medida em 04/09/2026:** leitura sob demanda
    mede ausência. Quem pergunta uma vez e lê na mesma linha recebe vazio
    sempre — vale para toda leitura sob demanda deste daemon, não só a do
    sensor. Aqui o laço já correu antes de alguém perguntar, e a primeira
    varredura acontece no primeiro ciclo, não no primeiro pedido.
    """
    while not daemon._is_stopping():
        await asyncio.sleep(CANAL_TTL_S)
        uniqs = _uniqs_conectados(daemon)
        if not uniqs:
            _CANAL_POR_UNIQ.clear()
            continue
        for uniq in uniqs:
            if daemon._is_stopping():
                return
            with contextlib.suppress(Exception):
                _CANAL_POR_UNIQ[uniq] = await daemon._run_blocking(_ler_o_canal, uniq)
        # Controle que saiu da mesa perde a leitura: publicar o canal de quem
        # não está mais aqui é o nono caso desta casa de nomear um controle
        # fora da mesa.
        for fora in [u for u in _CANAL_POR_UNIQ if u not in uniqs]:
            _CANAL_POR_UNIQ.pop(fora, None)



async def mic_button_loop(daemon: DaemonProtocol) -> None:
    """Consome `MIC_DA_MESA` e ELEGE o microfone do controle que apertou.

    MIC-DA-MESA-ELEICAO-01 (01/09/2026) — ESTE LAÇO MUDOU DE DONO E DE EIXO.

    Decisão dela, com as palavras dela: *"Se eu apertar o botão físico mic do
    controle e ele acender, significa que eu quero que o canal de áudio do
    microfone seja o controle. O botão de silenciar é confuso e mexendo com
    ambos os canais de áudio é péssimo."*

    O QUE SAIU, e as três medições que mandaram sair:

    (a) **`audio.toggle_default_source_mute`.** Ele opera em
        `@DEFAULT_AUDIO_SOURCE@` — GLOBAL, sem `uniq` — e muta o microfone de
        quem quer que seja o padrão. Isso é o oposto do gesto dela, que é
        *escolher* um canal, não silenciar dois.

    (b) **A guarda `fonte_padrao_e_o_controle`.** Ela pergunta por SUBSTRING
        "dualsense" (`integrations/audio_control.py`), logo responde *"a fonte
        padrão é ALGUM DualSense"* e nunca *"é ESTE"* — numa mesa de quatro os
        quatro respondem `True`. E ela está escrita **de costas para o gesto
        novo**: só deixava agir quando a fonte padrão JÁ era o controle, que é
        exatamente o caso em que eleger não teria efeito nenhum.
        O que ela protegia (BT-E-VPAD-01: o botão do controle não pode mutar
        aparelho de terceiro) continua protegido **por construção** — o gesto
        novo não muta nada, ele elege.

    (c) **O `BUTTON_DOWN`.** O botão do mic não chega lá: o `hid-playstation`
        CONSOME a borda e ela não vira evdev. E o `BUTTON_DOWN` não carrega
        `uniq`, então o Jogador 2 apertando elegeria o Jogador 1. A borda com
        endereço vem de `daemon/subsystems/mic_da_mesa.py`.

    O QUE FICOU: `mic_button_toggles_system` continua sendo o interruptor de
    *"o botão é nosso"*, consultado A CADA borda (e não no boot), para que a
    seção `mic` do perfil valha no próximo toque sem restart. Desligado, não
    elegemos nada e o kernel segue dono do mudo e da luz.

    E O LED SÓ ACENDE — E SÓ APAGA — DEPOIS DA RELEITURA.
    `set_mic_led(..., uniq=)` é chamado com o resultado CONFERIDO, nunca com o
    que mandamos, nos DOIS sentidos. Um LED pintado da escrita seria a mentira
    de segunda geração: o plástico dizendo "estou no ar" sobre um nó que o
    WirePlumber já desfez. E um LED apagado da INTENÇÃO é a mesma mentira ao
    contrário — foi o que acontecia na devolução recusada, com o canal
    continuando a ser o do controle e a luz caindo assim mesmo.

    O sossego e a carência não estão aqui: eles moram no laço das bordas, que
    é onde a borda nasce. Duas réguas sobre o mesmo estado é o defeito que esta
    casa já pagou onze vezes.
    """
    from hefesto_dualsense4unix.core.events import EventTopic

    queue = daemon.bus.subscribe(EventTopic.MIC_DA_MESA)
    try:
        while not daemon._is_stopping():
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            uniq = payload.get("uniq")
            if not isinstance(uniq, str) or not uniq:
                # O gesto EXIGE endereço. Cair no primário quando o clique não
                # diz o controle é o que faria a mesa de quatro eleger sempre
                # o mesmo — recusar é a resposta certa.
                logger.warning("mic_da_mesa_sem_endereco")
                continue
            if not getattr(daemon.config, "mic_button_toggles_system", True):
                logger.debug("mic_hotkey_desligado_por_config")
                continue
            mudo = bool(payload.get("mudo"))
            # A BORDA QUE NÓS MESMOS CAUSAMOS NÃO É GESTO — MICROFONE-UM-ATO-01
            # (04/09/2026). O ato do microfone escreve o bit do mudo no
            # firmware, e o firmware devolve essa mudança no report de INPUT
            # ~550 ms depois (medido na bancada: o `report_thread` só põe o
            # byte no fio no ciclo do keepalive). O laço das bordas não tem
            # como saber, sozinho, se o bit mudou pelo dedo dela ou pela nossa
            # escrita — e tratar o eco como gesto executa o ato DUAS vezes.
            #
            # A segunda execução não é inócua: com `ligado=False`, a primeira
            # devolve o canal e zera o eleito, e o eco chega em `mudo=True`
            # sobre `eleito is None` — que é o ramo da RECUSA, e ele deposita
            # no cartão dela uma frase dizendo que o microfone está com outro
            # controle. Medido em 04/09 pelo caminho do `mic.set` da tela.
            if _borda_e_eco_do_ato(uniq, mudo):
                logger.debug("mic_da_mesa_eco_do_ato_engolido", uniq=uniq, mudo=mudo)
                continue
            try:
                await ligar_o_microfone(daemon, uniq, ligado=not mudo)
            except Exception as exc:
                logger.warning("mic_hotkey_falhou", err=str(exc))
    finally:
        daemon.bus.unsubscribe(EventTopic.MIC_DA_MESA, queue)


# ---------------------------------------------------------------------------
# O ATO DO MICROFONE — uma função, dois chamadores (MICROFONE-UM-ATO-01)
# ---------------------------------------------------------------------------

#: Teto da espera pela CONFIRMAÇÃO do byte do mudo no aparelho. Medido na
#: bancada em 04/09/2026, com o controle no cabo: o `mic.set` leva **547 ms e
#: 548 ms** (duas medições, nos dois sentidos) até o `state_full` publicar o
#: valor novo — o `report_thread` só escreve no ciclo do keepalive, que é de
#: 0,5 s. Três segundos é seis vezes isso, e continua curto o bastante para a
#: posse não ficar nossa por engano quando o aparelho responde.
CONFIRMACAO_DO_MUDO_S: float = 3.0

#: De quanto em quanto se relê, esperando a confirmação. 100 ms é um décimo do
#: sossego das bordas e cinco vezes o intervalo do laço que as vê.
PASSO_DA_CONFIRMACAO_S: float = 0.1

#: Janela em que uma borda do bit de mudo é ECO da nossa própria escrita.
#: Maior que a confirmação medida (~550 ms) com folga, e menor que qualquer
#: segundo toque deliberado de quem está com o controle na mão.
ECO_DO_ATO_S: float = 2.0

#: `{uniq: (instante, mudo_que_escrevemos)}` — o registro das escritas que o
#: ATO fez no byte do mudo. Só ele; o que o kernel escreve na borda do botão
#: físico não passa por aqui, que é justamente a diferença que o laço precisa.
_ECO_DO_ATO: dict[str, tuple[float, bool]] = {}


def _relogio() -> float:
    """O monotônico, isolado num nome para o teste poder congelá-lo."""
    import time

    return time.monotonic()


def _marcar_eco_do_ato(uniq: str, mudo: bool) -> None:
    """Anota que NÓS escrevemos este valor no byte do mudo deste controle."""
    _ECO_DO_ATO[uniq] = (_relogio(), bool(mudo))


def _borda_e_eco_do_ato(uniq: str, mudo: bool) -> bool:
    """A borda que chegou é o eco da nossa escrita, e não um gesto dela?

    Exige as DUAS coisas — a janela de tempo **e** o mesmo valor. Só o tempo
    engoliria o gesto de quem apertasse o plástico para desfazer o que acabou
    de fazer pela tela, que é o uso mais provável do botão logo depois de um
    clique. O valor casa porque o eco só pode trazer de volta o que mandamos.
    """
    marca = _ECO_DO_ATO.get(uniq)
    if marca is None:
        return False
    quando, escrito = marca
    if bool(mudo) != escrito:
        return False
    if (_relogio() - quando) >= ECO_DO_ATO_S:
        _ECO_DO_ATO.pop(uniq, None)
        return False
    # O eco só vale UMA vez: a próxima borda com o mesmo valor é gesto dela.
    _ECO_DO_ATO.pop(uniq, None)
    return True


@dataclass(frozen=True)
class MetadeDoAto:
    """Uma das duas metades do ato, e o motivo quando ela não aconteceu.

    `motivo` vazio com `feita=False` é proibido por construção: quem constrói
    uma metade não-feita passa a frase, porque é ela que vai para o cartão.
    """

    feita: bool
    motivo: str = ""


@dataclass(frozen=True)
class AtoDoMicrofone:
    """O ato inteiro: o canal no sistema **e** o mudo no firmware.

    O CONCEITO É DELA, e ele derrubou a pergunta que eu tinha feito. Eu levei
    o microfone como *"duas camadas se contradizem"* e ofereci três arranjos
    que GUARDAVAM a contradição; ela recusou os três:

        *"tá errado o conceito da coisa. o botão é pra ligar o microfone e ele
        ser ouvido no canal específico dele."*

    E ao meio-dia de 04/09 acrescentou as duas regras que faltavam, com todas
    as letras:

        *"o botão fisico do mic se ligado no  # noqa-acento: citação dela
        microfone ele fica ligado tambem.  # noqa-acento: citação dela
        indepente se nativo ou virtual"*  # noqa-acento: citação dela

    Não são duas camadas com duas verdades: é UM ato, e ele só está feito
    quando as duas metades estão feitas. Por isso este tipo carrega as duas
    separadas — para a frase de recusa poder dizer QUAL faltou, que é o que a
    S-01 do piloto leva ao cartão.
    """

    uniq: str
    ligado: bool
    canal_no_sistema: MetadeDoAto
    firmware: MetadeDoAto
    ativo: str | None = None

    @property
    def feito(self) -> bool:
        """As duas metades feitas. Nada de "meio ato" contando como sucesso."""
        return self.canal_no_sistema.feita and self.firmware.feita

    @property
    def motivo(self) -> str:
        """A frase que diz QUAL metade faltou — vazia quando o ato está feito.

        As duas metades falhando viram UMA frase com as duas razões, e não a
        primeira delas: quem lê o cartão precisa saber que não foi só um
        pedaço. O texto de tela é dela; o que se monta aqui é a junção.
        """
        faltou = [
            m.motivo
            for m in (self.canal_no_sistema, self.firmware)
            if not m.feita
        ]
        return " · ".join(f for f in faltou if f)

    def como_corpo(self) -> dict[str, Any]:
        """A resposta do IPC — o mesmo dicionário para os dois chamadores."""
        return {
            "status": "ok" if self.feito else "incompleto",
            "uniq": self.uniq,
            "ligado": self.ligado,
            "canal_feito": self.canal_no_sistema.feita,
            "canal_motivo": self.canal_no_sistema.motivo,
            "firmware_pedido": self.firmware.feita,
            "firmware_motivo": self.firmware.motivo,
            "ativo": self.ativo,
            "motivo": self.motivo,
        }


async def ligar_o_microfone(
    daemon: DaemonProtocol, uniq: str, *, ligado: bool
) -> AtoDoMicrofone:
    """O ATO — e é a MESMA função para o botão do plástico e o da tela.

    Uma função, dois chamadores, por nome: `mic_button_loop` (a borda do
    plástico) e `ipc_handlers._handle_mic_canal_set` (o 🎙 da tela). A régua
    `tests/unit/test_o_microfone_e_um_estado_so.py` confere isso arrancando o
    chamador — se os dois deixarem de apontar para este nome, ela reprova.

    **ELE NÃO CONSULTA O MODO**, e é a segunda regra dela. Não há um `if
    native_mode` neste caminho nem em nenhuma das duas metades: o ato é o
    mesmo em Nativo e em Virtual. O que muda é o que o APARELHO consegue
    fazer, e isso o ato RELATA em vez de esconder — ver a metade do firmware.

    A ORDEM É O CANAL PRIMEIRO, e ela é medida: a metade do canal é a que
    funciona em qualquer modo (o PipeWire não passa pelo hidraw) e é a que ela
    nomeou — *"ele ser ouvido no canal específico dele"*. A do firmware pode
    ficar represada; fazê-la primeiro atrasaria a metade que sempre pega.
    """
    no_sistema, ativo = await _metade_do_canal(daemon, uniq, ligado)
    firmware = await _metade_do_firmware(daemon, uniq, ligado)
    ato = AtoDoMicrofone(
        uniq=uniq,
        ligado=ligado,
        canal_no_sistema=no_sistema,
        firmware=firmware,
        ativo=ativo,
    )
    logger.info(
        "mic_ato",
        uniq=uniq,
        ligado=ligado,
        feito=ato.feito,
        canal=no_sistema.feita,
        firmware=firmware.feita,
        motivo=ato.motivo,
    )
    return ato


async def _metade_do_canal(
    daemon: DaemonProtocol, uniq: str, ligado: bool
) -> tuple[MetadeDoAto, str | None]:
    """A metade do SISTEMA: a fonte de captura deste controle é a ouvida.

    É `_eleger_ou_devolver` inteiro, sem uma linha de regra nova: ele já é o
    dono da eleição, da recusa de quem não elegeu, do LED que segue a leitura
    conferida e do recado que vai para o cartão. Chamá-lo daqui é o oposto de
    reescrevê-lo — a segunda régua sobre o mesmo estado é o defeito que esta
    casa já pagou onze vezes.

    **E A PALAVRA DELA VAI ANTES — 08/09/2026.** Por Bluetooth o canal só
    existe enquanto a ponte de microfone estiver de pé, e o `0x32` que põe o
    microfone do controle no ar seguia só o estado da source. Como o ato ELEGE
    o canal como fonte padrão, e eleger não põe nó nenhum em ``RUNNING``, a
    source ficava ``SUSPENDED`` e o `0x32` saía DESLIGADO: medido no journal
    dela em 07/09/2026, quase três minutos de botão apertado com a ponte em
    `bt_mic_pedido ligar=False`. O ato respondia `feito=True` sobre um
    microfone mudo no ar.

    **AQUI, E NÃO EM `_handle_mic_canal_set`.** Este é o ponto por onde passam
    os DOIS chamadores de `ligar_o_microfone` — o 🎙 da tela e a borda do botão
    do plástico. Costurar isto no `ipc_handlers` deixaria o plástico de fora,
    com a suíte verde, e a regra dela é explícita:
    *"o botão fisico do mic se ligado no microfone ele fica ligado tambem.  # (noqa-acento) dela
    indepente se nativo ou virtual"*.

    **ANTES da eleição** porque ligar pode PRECISAR da ponte subir: com a
    palavra já guardada, a ponte que `_canal_no_ar` faz nascer já recebe o
    pedido dela na primeira varredura, em vez de esperar o toque seguinte.

    **E POR ISSO O ATO RECUSADO A DESFAZ — A SEXTA PORTA, 08/09/2026.** Dizer
    antes é o que faz a ponte nascer sabendo; nada desfazia quando a eleição
    respondia `ok=False`, e o desfecho era a MESMA mentira de segunda geração
    que `_apagar_a_luz_de_quem_perdeu_o_canal` fecha do outro lado, entrando
    pela porta da frente: a tela dizia RECUSADO, o LED não acendia, e
    `BtMicSubsystem._aplicar_a_palavra_dela` entregava `True` à ponte na
    varredura seguinte — **0x32 LIGADO**.

    Não é caso inventado: `EleitorDeMicrofone.eleger_o_controle` devolve
    `ok=False` com *"o PipeWire não publica canal de captura nenhum para o
    controle"* sempre que a ponte demora a publicar, que é o desfecho COMUM por
    rádio, e `eleger_por_uniq` tem mais quatro recusas. Medido com o eleitor
    REAL, a ponte REAL e o registro REAL: `no_ar() == {uniq: True}`,
    `_pedido_dela is True`, e o `0x32` saindo LIGADO na varredura seguinte com
    a source ``SUSPENDED``.

    **DESFAZER É DEVOLVER O QUE HAVIA, não apagar.** `palavra_no_ar` é lido
    ANTES do ato exatamente para isso: um ato que não aconteceu não muda nada.
    Apagar sempre tiraria do ar o microfone que ela já tinha posto lá num ato
    ANTERIOR que deu certo; dizer `False` a calaria sem ela ter pedido.

    **E SÓ O `ligado=True` SE DESFAZ.** O `False` é *"me cale"* e não depende
    de eleição nenhuma: a recusa de quem não elegeu diz, com todas as letras,
    que *"este botão apagou a luz deste controle e não mexeu no canal de áudio
    de ninguém"* — o microfone DELE tem de sair do ar do mesmo jeito. Desfazer
    o mudo aqui seria pôr de volta no ar uma voz que ela mandou calar, que é o
    defeito de privacidade com o sinal trocado.

    **E NO CABO ISTO NÃO FAZ NADA**, que é o desfecho certo: quem atende só
    conhece nós de Bluetooth (`nos_dualsense_bluetooth`), e no fio a placa USB
    publica o canal sozinha. Uma regra só no ato, em vez de um `if` de
    transporte no caminho dela.
    """
    antes = palavra_no_ar(uniq)
    dizer_no_ar(uniq, ligado)
    resultado = await _eleger_ou_devolver(daemon, uniq, not ligado)
    if resultado is None:
        _devolver_a_palavra(uniq, antes, ligado)
        return (
            MetadeDoAto(False, "o canal deste controle não foi tocado"),
            None,
        )
    if not resultado.ok:
        _devolver_a_palavra(uniq, antes, ligado)
    return (
        MetadeDoAto(bool(resultado.ok), "" if resultado.ok else resultado.motivo),
        resultado.ativo,
    )


def _devolver_a_palavra(uniq: str, antes: bool | None, ligado: bool) -> None:
    """O ato foi RECUSADO: o registro volta a ser o que era antes dele.

    A SEXTA PORTA do pedido dela, e é a única que se fecha depois do ato em vez
    de antes — as cinco de 08/09 são condições sobre quando a palavra nasce e
    morre; esta é sobre o ato que NÃO aconteceu.

    `ligado=False` sai pela porta sem tocar em nada, e o porquê está em
    `_metade_do_canal`: calar não depende de eleição.

    Nunca levanta — `dizer_no_ar` e `esquecer_a_palavra` já engolem o que der
    errado, e este caminho é o do gesto dela.
    """
    if not ligado:
        return
    if antes is None:
        esquecer_a_palavra(uniq)
    else:
        dizer_no_ar(uniq, antes)
    logger.info("mic_da_mesa_palavra_desfeita", uniq=uniq, voltou_para=antes)


async def _metade_do_firmware(
    daemon: DaemonProtocol, uniq: str, ligado: bool
) -> MetadeDoAto:
    """A metade do APARELHO: o bit `MIC_MUTE` do firmware, e a posse de volta.

    **É IDEMPOTENTE, E ISSO NÃO É ZELO — É A DECISÃO DELA.** Escrever o byte
    toma a posse dele do `hid-playstation`, e enquanto a posse for nossa o
    botão do plástico **deixa de valer** (`_handle_mic_set`: *"é uma ORDEM, e
    enquanto ela vigorar o botão físico não manda mais"*). Vindo do plástico,
    o kernel JÁ pôs o bit no valor certo antes de a borda chegar aqui — então
    não há o que escrever, e não escrever é o que mantém o botão dela vivo.
    Só o gesto de TELA encontra o bit divergente, e só ele escreve.

    **E A POSSE VOLTA AO KERNEL depois de o valor ir ao fio**, pela mesma
    razão: *"o botão do Controle sempre controla a interface"* (decisão dela,
    30/08/2026). A devolução é AGENDADA e não imediata, e isso é medição: o
    `handle.set_microphone_mute` só marca o desejo, e quem põe bytes no fio é
    o `report_thread` — devolver na linha seguinte apagaria o bit de validação
    antes de o report sair, e o valor nunca aconteceria.

    O QUE ELA DEVOLVE quando o aparelho não confirma: `feita=True` com o
    pedido ACEITO pelo backend é o que se sabe AGORA — a confirmação leva
    ~550 ms e a ponte da GUI tem teto de 250 ms. Quem diz a verdade conferida
    é o `state_full`, e é de lá que o selo composto se pinta. O que NÃO se faz
    aqui é responder "ok" sobre um backend que recusou: aí `feita` é `False`
    com a frase.
    """
    mudo_desejado = not ligado
    controller = getattr(daemon, "controller", None)
    leitor = getattr(controller, "audio_status_for", None)
    estado: Any = None
    if callable(leitor):
        with contextlib.suppress(Exception):
            estado = leitor(uniq)
    mudo_agora = estado.get("mic_mudo") if isinstance(estado, dict) else None
    if isinstance(mudo_agora, bool) and mudo_agora == mudo_desejado:
        # Já está como o ato pede. É o caminho do BOTÃO DO PLÁSTICO, e não
        # escrever aqui é o que deixa a posse com o kernel — ou seja, o que
        # deixa o botão dela continuar funcionando no toque seguinte.
        return MetadeDoAto(True)
    setter = getattr(controller, "set_microphone_mute", None)
    if not callable(setter):
        return MetadeDoAto(
            False, "este controle não expõe o mudo do microfone ao Hefesto"
        )
    ok = False
    with contextlib.suppress(Exception):
        ok = bool(await daemon._run_blocking(_mutar, setter, mudo_desejado, uniq))
    if not ok:
        return MetadeDoAto(False, MOTIVO_FIRMWARE_REPRESADO)
    _marcar_eco_do_ato(uniq, mudo_desejado)
    _agendar_a_devolucao_da_posse(daemon, uniq, mudo_desejado)
    return MetadeDoAto(True)


def _mutar(setter: Any, muted: bool | None, uniq: str) -> bool:
    """`set_microphone_mute(muted, uniq=…)` por POSICIONAIS. Não é enfeite.

    **`_run_blocking(self, fn, *args)` NÃO ACEITA KEYWORDS** — é a assinatura
    do daemon real (`daemon/lifecycle.py`) e a do protocolo. Chamar
    `_run_blocking(setter, muted, uniq=uniq)` levanta `TypeError`, e um
    `TypeError` dentro de um `suppress` vira "a escrita não pegou" com o
    produto respondendo uma frase educada sobre um byte que nunca saiu.

    **ISSO ACONTECEU AQUI, em 04/09/2026, e o teste estava VERDE.** O dublê da
    régua tinha `async def _run_blocking(self, fn, *a, **kw)` — mais frouxo que
    o daemon real —, e quem revelou foi o APARELHO: o ato respondeu "não
    conseguiu escrever" na bancada, com o backend intacto. É a mesma família da
    máscara que nunca gravou um byte (`p.chamar("gamepad.mask.set", {…})` com
    o dicionário virando o `timeout` posicional).

    O envelope existe pelo mesmo motivo do `_acender` deste arquivo, e é o
    padrão da casa: quem precisa de keyword embrulha em posicionais.
    """
    return bool(setter(muted, uniq=uniq))


def _agendar_a_devolucao_da_posse(
    daemon: DaemonProtocol, uniq: str, mudo_desejado: bool
) -> None:
    """Espera o aparelho CONFIRMAR e só então devolve a posse ao kernel.

    Task própria porque a confirmação custa ~550 ms (medido) e o handler do
    IPC não pode pagá-la: a ponte da GUI corta em 250 ms. Sem task, ou a tela
    trava, ou a posse fica nossa para sempre — e a posse nossa é o botão do
    plástico morto.

    **NÃO devolve quando a confirmação não vem**, e isso é deliberado: em Modo
    Nativo o `report_thread` não escreve nada (contrato de zero escrita,
    FEAT-NATIVE-OUTPUT-MUTE-01, medido na bancada em 04/09 — `mic.set`
    respondeu `ok` com o `mic_mudo` parado). Devolver ali apagaria o bit de
    validação e o pedido dela morreria calado. Ele fica represado, a posse
    fica nossa, e o `state_full` publica a discordância — que é o que o selo
    composto existe para mostrar.
    """
    with contextlib.suppress(Exception):
        task = asyncio.create_task(
            _confirmar_e_devolver(daemon, uniq, mudo_desejado),
            name=f"mic_ato_confirma_{uniq}",
        )
        daemon._tasks.append(task)


async def _confirmar_e_devolver(
    daemon: DaemonProtocol, uniq: str, mudo_desejado: bool
) -> None:
    """Relê até o aparelho concordar; devolve a posse; anota o que aconteceu."""
    controller = getattr(daemon, "controller", None)
    leitor = getattr(controller, "audio_status_for", None)
    devolver = getattr(controller, "set_microphone_mute", None)
    if not (callable(leitor) and callable(devolver)):
        return
    esperou = 0.0
    while esperou < CONFIRMACAO_DO_MUDO_S:
        await asyncio.sleep(PASSO_DA_CONFIRMACAO_S)
        esperou += PASSO_DA_CONFIRMACAO_S
        if daemon._is_stopping():
            return
        estado: Any = None
        with contextlib.suppress(Exception):
            estado = leitor(uniq)
        lido = estado.get("mic_mudo") if isinstance(estado, dict) else None
        if isinstance(lido, bool) and lido == mudo_desejado:
            with contextlib.suppress(Exception):
                # POSICIONAIS: `_run_blocking(self, fn, *args)`. Ver `_mutar`.
                await daemon._run_blocking(_mutar, devolver, None, uniq)
            logger.info(
                "mic_ato_posse_devolvida", uniq=uniq, esperou_s=round(esperou, 2)
            )
            return
    logger.info("mic_ato_represado", uniq=uniq, mudo_desejado=mudo_desejado)
    # `recusa` E NÃO UMA PALAVRA NOVA. `recado_do_microfone.GESTOS` é uma
    # tupla FECHADA e `anotar` LEVANTA em gesto desconhecido — de propósito,
    # para a tela nunca receber uma palavra que não sabe pintar. Medido na
    # bancada em 04/09: a primeira redação disto mandava
    # `gesto="firmware-represado"`, o `ValueError` subiu dentro da task e o
    # recado do represamento nunca chegou ao `state_full` — o log dizia
    # `mic_ato_represado` e a tela não recebia nada.
    #
    # `recusa` é a palavra certa e não é remendo: ela já significa *"o produto
    # não fez, e a razão é esta"*. O que muda é o `motivo`, que é o que a tela
    # pinta.
    with contextlib.suppress(Exception):
        recado_do_microfone.anotar(
            daemon,
            uniq,
            gesto="recusa",
            ok=False,
            motivo=MOTIVO_FIRMWARE_REPRESADO,
        )


#: A frase de quando o byte do mudo não chega ao aparelho. Ela NÃO nomeia o
#: modo por adivinhação — nomeia o que foi medido: o pedido ficou de pé e o
#: controle não confirmou. Em Modo Nativo o hidraw é do jogo e o daemon não
#: escreve nada nele; é o caso conhecido, e é o que a frase descreve sem
#: prometer que é o único.
MOTIVO_FIRMWARE_REPRESADO: Final[str] = (
    "o microfone foi ligado no canal deste controle, mas o Hefesto não "
    "conseguiu escrever o mudo no aparelho — enquanto um jogo estiver com o "
    "controle (Modo Nativo) quem manda no plástico é ele, e o pedido fica "
    "guardado até o Hefesto poder escrever"
)


async def _eleger_ou_devolver(
    daemon: DaemonProtocol, uniq: str, mudo: bool
) -> ResultadoDaEleicao:
    """O controle passou a NÃO-MUDO: elege. O ELEITO passou a MUDO: devolve.

    **DEVOLVE O RESULTADO desde 04/09/2026 (MICROFONE-UM-ATO-01).** Ele já
    tinha um: as cinco frases de `ResultadoDaEleicao.motivo` iam para o log e
    para o recado, e o chamador ficava sem saber se a metade do canal tinha
    acontecido. O ato precisa saber — é metade dele.

    O caminho de VOLTA não é opcional: sem ele, o desfecho padrão de ela tirar
    o mic do controle é o `.monitor` do sink ou o `auto_null` — o sistema
    gravando o som que SAI no lugar da voz dela
    (FONTE-PADRÃO-01/MONITOR-QUE-VENCE-01).

    **SÓ O ELEITO DEVOLVE** (auditoria de 02/09/2026). `devolver_o_microfone()`
    é GLOBAL — não recebe `uniq` —, e aqui se decidia só pelo bit `mudo`. Numa
    mesa de quatro isso é o defeito inteiro: a J1 elege, o J2 aperta o botão
    DELE, e o microfone sai da J1, que fica com o LED aceso dizendo "estou no
    ar". Quem não é o eleito e vai a mudo apaga só a própria luz.

    **E A LUZ DE QUEM PERDEU O CANAL TAMBÉM É DESTE LAÇO** (segunda auditoria
    de 02/09/2026). Este método escrevia o LED de `uniq` e de mais ninguém — e
    a posse pode sair de OUTRO controle no mesmo gesto, seja porque o novo
    eleito ganhou o canal, seja porque o WirePlumber deu o canal a um terceiro.
    Ver `_apagar_a_luz_de_quem_perdeu_o_canal`.
    """
    eleitor = _eleitor(daemon)
    # QUEM ESTAVA COM O CANAL ANTES DESTE TOQUE. Ele é lido AQUI porque o
    # gesto de um controle pode tirar o microfone de OUTRO, e depois da
    # chamada não há mais como saber quem era. Ver o bloco da luz no fim.
    dono_antes = eleitor.eleito
    if mudo:
        # SÓ QUEM ESTÁ COM O MICROFONE PODE DEVOLVÊ-LO (auditoria 02/09/2026).
        #
        # Aqui se decidia só pelo bit `mudo`, sem perguntar de QUEM ele era. Na
        # mesa de quatro que ela nomeou, isso é o defeito inteiro: a J1 elege e
        # o plástico dela acende; o J2 aperta o botão DELE, o mudo do firmware
        # dele vira `True`, e o `devolver_o_microfone()` — que é GLOBAL, não
        # recebe `uniq` — tirava o padrão do sistema da J1, que continuava com
        # o LED aceso dizendo "estou no ar". É a mentira que esta onda existe
        # para matar, e era alcançável no PRIMEIRO toque.
        #
        # Quem não elegeu e vai a mudo só apaga a PRÓPRIA luz: o mudo do
        # firmware é dele, a luz é dele, e o microfone da mesa não é.
        #
        # `eleito is None` cai no mesmo ramo, e de propósito: ninguém tomou o
        # microfone, logo não há o que devolver. Devolver ali reelegeria a
        # "melhor fonte" e trocaria o padrão do sistema dela sem que ela tivesse
        # elegido nada — na bancada de hoje isso não aparece só porque não há
        # fonte elegível, o que é sorte, não cura.
        if eleitor.eleito != uniq:
            # A RECUSA CHEGA À TELA — MIC-RECUSA-NA-TELA-01 (02/09/2026).
            # Este ramo voltava só com o `logger.info` abaixo: o jogador que
            # apertou o botão via a luz apagar, o microfone continuar no
            # vizinho, e o produto não dizia uma palavra. É quem MAIS precisa
            # da frase — a dona do canal pelo menos tem o LED aceso dizendo
            # que está no ar.
            #
            # E A FRASE FALA DA MESA, NÃO DA MEMÓRIA DO ELEITOR (auditoria de
            # 02/09/2026). O eleito pode ter SAÍDO da mesa: nada em `src/`
            # devolve o microfone no hotplug-out — as únicas escritas de
            # `EleitorDeMicrofone.eleito` são caminhos de eleição. Com a J1
            # fora do cabo, `recusa_de_quem_nao_elegeu(eleitor.eleito)` dizia
            # ao J2 *"o microfone da mesa está com outro controle"* e mandava
            # ele procurar um dono que não tem card na tela — a nona vez que
            # esta casa nomeia um controle fora da mesa.
            #
            # Com o dono fora da mesa a notícia certa é a que ela já escreveu
            # para `eleito is None`: da mesa, ninguém está com o microfone.
            # Nenhuma frase nova nasce aqui — texto de tela é dela.
            #
            # E QUEM DIZ QUEM ESTÁ NA MESA É UMA FUNÇÃO SÓ, que é a mesma que
            # o `state_full` usa: `recado_do_microfone.mesa_de_agora`. Esta
            # linha perguntava a `_uniqs_conectados`, que **não exige o
            # `connected`** — a lista dele vai para a ELEIÇÃO, e lá a pergunta
            # é outra. O backend real devolve uma entrada POR HANDLE e mantém
            # o `uniq` preenchido com `connected: False`
            # (`core/backend_pydualsense.py:5389`), então o controle que saiu
            # DE VERDADE continuava na lista e o dono não caía.
            #
            # Medido com o laço deste arquivo e um backend que faz o que o real
            # faz: o MESMO `state_full` saía com `eleito_na_mesa: false` e o
            # recado do J2 dizendo *"o microfone da mesa está com outro
            # controle"*. Duas leituras do mesmo estado, dois vereditos.
            #
            # Mesa `None` (backend que não sabe listar) e mesa VAZIA deixam o
            # dono de pé: quem apertou o botão está na mesa por construção,
            # logo o vazio só pode ser instrumento cego — e "não sei" nunca
            # vira "saiu".
            dono = eleitor.eleito
            mesa = recado_do_microfone.mesa_de_agora(daemon)
            if dono is not None and mesa and dono not in mesa:
                dono = None
            recusa = recusa_de_quem_nao_elegeu(dono)
            logger.info(
                "mic_da_mesa_mudo_de_quem_nao_elegeu",
                uniq=uniq,
                eleito=eleitor.eleito,
                dono_na_mesa=dono,
                motivo=recusa.motivo,
            )
            recado_do_microfone.anotar(
                daemon,
                uniq,
                gesto="recusa",
                ok=False,
                motivo=recusa.motivo,
                eleito=dono,
            )
            acender_outro = getattr(daemon.controller, "set_mic_led", None)
            if callable(acender_outro):
                await daemon._run_blocking(_acender, acender_outro, False, uniq)
            return recusa
        # ANOTADO porque `_run_blocking` devolve `Any` e este método passou a
        # DEVOLVER o resultado (MICROFONE-UM-ATO-01): sem a anotação o `Any`
        # vazaria para o ato inteiro e o mypy pararia de conferir as metades.
        resultado: ResultadoDaEleicao = await daemon._run_blocking(
            eleitor.devolver_o_microfone
        )
        # A LUZ FICA ACESA QUANDO A DEVOLUÇÃO É RECUSADA — decisão dela, e ela
        # não é nova: o contrato do LED é *"aceso = este mic está no ar"*
        # (01/09/2026). Se o produto não conseguiu devolver, o padrão do
        # sistema continua sendo o canal DESTE controle — logo o microfone
        # dele está no ar, logo a luz fica acesa.
        #
        # Aqui estava `aceso = False`, cravado ANTES de saber o desfecho. Com
        # `melhor_fonte_elegivel()` vazia — o estado desta bancada, com a
        # webcam fora e as três portas analógicas `not available` — a
        # devolução volta `ok=False` sem ter escrito nada, e o plástico apagava
        # sobre um canal que continuava sendo o dele. Era a mentira de segunda
        # geração ao contrário: o LED dizendo "saí do ar" com o sistema
        # gravando por ele.
        #
        # E é a MESMA regra dos dois lados — a luz segue a leitura CONFERIDA,
        # nunca o que mandamos. `eleger` acende quando o ativo relido é o
        # controle; `devolver` só apaga quando o ativo relido deixou de ser.
        #
        # E AGORA A LUZ SEGUE A POSSE, que é a mesma frase escrita uma vez só
        # (auditoria de 02/09/2026). Aqui estava `aceso = not bool(resultado.
        # ok)`, e o comentário acima prometia o que o código não fazia: ele
        # lia `resultado.ok`, e `ok=False` na volta significa *"o OUTRO destino
        # não virou o ativo"*, que NÃO implica *"o canal ainda é deste
        # controle"*. Os três desfechos de recusa de `_eleger_nome` ficavam
        # iguais, e no terceiro — a escrita ACEITA com o ativo relido virando
        # um TERCEIRO, que é o `eleicao_mic_nao_pegou` que o módulo existe para
        # pegar — o plástico continuava aceso sobre um canal que a própria
        # medição dizia não ser mais dele.
        #
        # `eleitor.eleito` já é essa resposta, e é a ÚNICA: quem a escreve é
        # `_o_eleito_saiu_do_ar`, comparando o ativo relido com o NOME do canal
        # do eleito. Este ramo só é alcançado com `eleitor.eleito == uniq` (a
        # guarda acima), então a posse de pé é a luz acesa, e a posse caída é a
        # luz apagada — e o `state_full` não pode mais dizer `eleito: …011` com
        # `ativo: mic_de_um_terceiro` e o LED aceso ao mesmo tempo.
        aceso = eleitor.eleito == uniq
    else:
        # A LISTA DA ELEIÇÃO É CALCULADA AQUI, e não antes do `if` (auditoria
        # de 02/09/2026). Ela era, e o ramo `mudo` não a usava mais desde que a
        # recusa passou a perguntar a `recado_do_microfone.mesa_de_agora` —
        # então todo toque de botão pagava DOIS `describe_controllers()`, com
        # duas aquisições do `_io_lock`, para jogar o primeiro fora. É caminho
        # de BORDA e não os 10 Hz, mas duas leituras do mesmo estado é o que
        # este arquivo acabou de gastar uma cura inteira para deixar de fazer.
        conectados = _uniqs_conectados(daemon)
        resultado = await daemon._run_blocking(
            eleitor.eleger_o_controle, uniq, conectados
        )
        aceso = bool(resultado.ok)
    logger.info(
        "mic_da_mesa_eleicao",
        uniq=uniq,
        mudo=mudo,
        ok=resultado.ok,
        ativo=resultado.ativo,
        motivo=resultado.motivo,
    )
    # ...E A MESMA FRASE VAI PARA A TELA. As cinco frases de
    # `ResultadoDaEleicao.motivo` ("não há canal de captura atribuível a este
    # controle", "o WirePlumber reelegeu por cima", "não há microfone para onde
    # voltar"…) saíam SÓ no `logger.info` acima, e o docstring do tipo já
    # prometia que elas eram "o texto que vai para a tela". O recado sobrevive
    # ao tique seguinte porque fica GUARDADO — ver
    # `daemon/subsystems/recado_do_microfone`.
    recado_do_microfone.anotar(
        daemon,
        uniq,
        gesto="devolver" if mudo else "eleger",
        ok=bool(resultado.ok),
        motivo=resultado.motivo,
        ativo=resultado.ativo,
        eleito=eleitor.eleito,
    )
    acender = getattr(daemon.controller, "set_mic_led", None)
    if callable(acender):
        await daemon._run_blocking(_acender, acender, aceso, uniq)
        await _apagar_a_luz_de_quem_perdeu_o_canal(
            daemon, acender, dono_antes=dono_antes, quem_tocou=uniq, eleitor=eleitor
        )
    return resultado


async def _apagar_a_luz_de_quem_perdeu_o_canal(
    daemon: DaemonProtocol,
    acender: Any,
    *,
    dono_antes: str | None,
    quem_tocou: str,
    eleitor: Any,
) -> None:
    """O plástico de quem perdeu o microfone SEM TER TOCADO EM NADA.

    ACHADO DA AUDITORIA DE 02/09/2026, e é a outra metade do defeito que
    `EleitorDeMicrofone.eleger_por_uniq` acabou de fechar do lado da posse. O
    contrato do LED é dela, de 01/09: *"aceso = este mic está no ar"*. Este
    laço acendia e apagava a luz de **quem apertou o botão**, e só dele — o
    ex-dono do canal nunca era tocado. Nas duas cenas em que a posse muda por
    gesto alheio, o plástico dele continuava afirmando o que a posse já negava:

    * o J2 elege e DÁ CERTO — o canal é do J2, e a J1 seguia acesa;
    * o J2 elege, a escrita PASSA e o WirePlumber reelege um TERCEIRO — o canal
      não é de ninguém, e a J1 seguia acesa.

    Só apaga, nunca acende: quem ganha o canal é `quem_tocou`, e a luz dele já
    foi escrita acima. E só quando a posse REALMENTE saiu do ex-dono — se ela
    continuar com ele (a escrita nem aconteceu, ou o WirePlumber devolveu o
    canal a ele), a luz dele está certa e mexer nela seria fabricar a mentira
    ao contrário.

    **NÃO NASCE FRASE DE TELA AQUI.** O que o card da J1 deveria dizer quando
    ela perde o canal num gesto de outra pessoa é texto novo, e texto de tela é
    decisão dela — está no relato desta frente. O LED, não: ele já tem
    contrato escrito, e obedecê-lo é o trabalho.

    **E O MICROFONE SAI DO AR COM A LUZ — 08/09/2026.** Desde que o `0x32` do
    rádio passou a ter um segundo dono (a palavra dela, ver
    `_metade_do_canal`), apagar só o LED abriria a mesma mentira pelo lado de
    dentro: o plástico dizendo *"saí do ar"* com o microfone ainda
    transmitindo. Quem perde o canal por gesto alheio deixa de ter dito
    qualquer coisa — a decisão volta ao ouvinte da source, que é o
    comportamento de 06/09. Não é `dizer_no_ar(False)`: ela não pediu para ser
    calada, ela só deixou de ser a dona do canal.
    """
    if dono_antes is None or dono_antes == quem_tocou:
        return
    if eleitor.eleito == dono_antes:
        return
    logger.info(
        "mic_da_mesa_luz_do_ex_dono_apagada",
        ex_dono=dono_antes,
        por=quem_tocou,
        eleito_agora=eleitor.eleito,
    )
    esquecer_a_palavra(dono_antes)
    await daemon._run_blocking(_acender, acender, False, dono_antes)


def _acender(acender: Any, aceso: bool, uniq: str) -> None:
    """Chama `set_mic_led(aceso, uniq=...)`, tolerando backend sem endereço.

    O `TypeError` é o backend antigo (ou um dublê) que não aceita `uniq`. Cair
    para a chamada sem endereço é degradar declarado — e o log diz qual foi,
    porque "degradou calado" é como esta casa fabrica o LED do controle errado.
    """
    try:
        acender(aceso, uniq=uniq)
    except TypeError:
        logger.warning("mic_da_mesa_led_sem_endereco", uniq=uniq)
        acender(aceso)


def devolver_a_luz_ao_kernel(daemon: DaemonProtocol) -> int:
    """Devolve a POSSE do `common[8]` de todos os controles da mesa.

    ACHADO DA AUDITORIA DE 02/09/2026, e ele é sobre uma frase que ficou falsa.
    O comentário de `mic_button_toggles_system` em `daemon/lifecycle.py`
    prometia: *"Desligado, não elegemos e não acendemos: o kernel segue dono do
    mudo E da luz do próprio controle"*. A segunda metade era falsa depois da
    primeira eleição, e o caminho é REENTRANTE em runtime —
    `daemon/ipc_draft_applier.py` escreve o campo sem restart.

    Medido nesta árvore, sobre o `_build_common` de verdade:

        1. de fabrica                   : flag1&0x01=0  common[8]=0  -> kernel
        2. depois de UMA eleicao ok     : flag1&0x01=1  common[8]=1  -> hefesto
        3. perfil desliga o interruptor : flag1&0x01=1  common[8]=1  -> hefesto
        4. so a devolucao de posse      : flag1&0x01=0  common[8]=0  -> kernel

    Cena real: ela joga, aperta o mic (LED acende, posse nossa), depois carrega
    um perfil de gravação com `mic.button_toggles_system: false`. Daí em diante
    o botão físico não mexe mais na luz, e a luz fica CONGELADA no que a última
    eleição deixou. Havia porta de emergência (`hefesto-dualsense4unix mic
    led-release`), mas ela é comando de terminal e a prosa prometia que não
    precisava dela.

    Devolve quantos controles tiveram a posse devolvida. É idempotente: um
    `set_microphone_led(None)` sobre quem já devolveu não muda nada.
    """
    devolver = getattr(daemon.controller, "set_microphone_led", None)
    if not callable(devolver):
        # NÃO É HIPÓTESE: medido em 02/09/2026, nem `core/controller.IController`
        # nem o `FakeController` da suíte declaram `set_microphone_led` — só o
        # `PyDualSenseController`. Num daemon dublado a devolução não acontece,
        # e sair calado daqui seria a tela e o log dizendo que a luz voltou ao
        # kernel quando ela não voltou.
        logger.warning("mic_da_mesa_posse_sem_backend")
        return 0
    quantos = 0
    for uniq in _uniqs_conectados(daemon) or [None]:  # type: ignore[list-item]
        try:
            if uniq is None:
                devolver(None)
            else:
                devolver(None, uniq=uniq)
        except TypeError:
            # Backend (ou dublê) sem endereço: degradar é declarado, e o log
            # diz qual foi — "degradou calado" é como esta casa fabrica o LED
            # do controle errado.
            logger.warning("mic_da_mesa_posse_sem_endereco", uniq=uniq)
            with contextlib.suppress(Exception):
                devolver(None)
        except Exception as exc:  # pragma: no cover - defensivo
            logger.warning("mic_da_mesa_posse_falhou", uniq=uniq, err=str(exc))
            continue
        quantos += 1
    logger.info("mic_da_mesa_posse_devolvida", controles=quantos)
    return quantos


def _eleitor(daemon: DaemonProtocol) -> Any:
    """O eleitor da SESSÃO. Um só, porque ele guarda o microfone de antes.

    Se cada borda criasse um eleitor novo, a memória do "anterior" seria a
    fonte que a borda passada acabou de eleger — e numa mesa em turnos o
    caminho de volta devolveria o microfone ao controle do jogador anterior em
    vez de ao microfone real dela.

    O import de `EleitorDeMicrofone` era preguiçoso e deixou de comprar
    qualquer coisa em 02/09/2026, quando `recusa_de_quem_nao_elegeu` — do MESMO
    módulo — subiu para o topo do arquivo: o módulo já está carregado quando
    esta função roda. Ciclo não há (`eleicao_de_microfone` só importa
    `integrations/fontes_de_captura` e `utils/logging_config`, nada que volte a
    `daemon/`). Deixá-lo aqui faria a próxima pessoa supor um custo que não
    existe e reproduzir o padrão por imitação.
    """
    eleitor = getattr(daemon, "_eleitor_de_microfone", None)
    if eleitor is None:
        eleitor = EleitorDeMicrofone()
        daemon._eleitor_de_microfone = eleitor  # type: ignore[attr-defined]
    return eleitor


def _uniqs_conectados(daemon: DaemonProtocol) -> list[str]:
    """MACs dos controles na mesa agora — o `uniqs_com_audio` de `escolher_fonte`."""
    descrever = getattr(daemon.controller, "describe_controllers", None)
    if not callable(descrever):
        return []
    try:
        itens = descrever()
    except Exception:  # pragma: no cover - defensivo
        return []
    out: list[str] = []
    for item in itens if isinstance(itens, list) else []:
        uniq = item.get("uniq") if isinstance(item, dict) else None
        if isinstance(uniq, str) and uniq:
            out.append(uniq)
    return out


class HotkeySubsystem:
    """Subsystem sentinela para hotkey no registry.

    A lógica real está nas funções start_hotkey_manager / start_mic_hotkey
    porque o Daemon precisa de referências diretas para backcompat de testes
    que acessam daemon._hotkey_manager e daemon._audio.
    """

    name = "hotkey"

    async def start(self, ctx: DaemonContext) -> None:
        """Noop: hotkey é iniciado diretamente pelo Daemon.run()."""
        logger.debug("hotkey_subsystem_start")

    async def stop(self) -> None:
        """Noop: daemon._hotkey_manager é limpado em _shutdown."""
        logger.debug("hotkey_subsystem_stop")

    def is_enabled(self, config: Any) -> bool:
        return True


__all__ = [
    "CANAL_TTL_S",
    "CICLO_DE_PONTES",
    "CONFIRMACAO_DO_MUDO_S",
    "CORES_DO_MODO",
    "ECO_DO_ATO_S",
    "MIC_SOSSEGO_S",
    "MODO_NATIVO",
    "MODO_STEAM_INPUT",
    "MOTIVO_FIRMWARE_REPRESADO",
    "PONTE_DUALSENSE",
    "PONTE_MOUSE_TECLADO",
    "PONTE_XBOX",
    "AtoDoMicrofone",
    "HotkeySubsystem",
    "MetadeDoAto",
    "acao_do_ps_do_perfil",  # (noqa-acento) nome de função
    "avisar_troca_de_modo",
    "build_next_bridge_callback",
    "build_profile_cycle_callback",
    "build_ps_long_press_callback",
    "build_ps_solo_callback",
    "canal_do_microfone",
    "canal_do_microfone_loop",
    "definir_acao_do_ps",  # (noqa-acento) nome de função
    "devolver_a_luz_ao_kernel",
    "ligar_o_microfone",
    "mic_button_loop",
    "modo_vigente",
    "ponte_atual",
    "proxima_ponte",
    "start_hotkey_manager",
    "start_mic_hotkey",
    "stop_hotkey_manager",
]
