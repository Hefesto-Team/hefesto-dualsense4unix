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
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.integrations import ponte_tentativa
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


def build_ps_solo_callback(daemon: DaemonProtocol) -> Any:
    """Cria o callback on_ps_solo que lê self.config em runtime (REFACTOR-DAEMON-RELOAD-01).

    Leitura em runtime — não em closure — para que reload_config funcione sem
    recriar closures manualmente.
    """

    def _on_ps_solo() -> None:
        cfg = daemon.config
        if cfg.ps_button_action == "none":
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
        if cfg.ps_button_action == "steam":
            from hefesto_dualsense4unix.integrations.steam_launcher import open_or_focus_steam

            open_or_focus_steam()
        elif cfg.ps_button_action == "custom":
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
    declara (existe no Daemon real — `lifecycle.py:1190`) e o Protocol é
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
        daemon.set_keyboard_emulation(True)
    return True


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
    - sem tentativa — jogo com ponte CONFIRMADA, ou nenhum jogo — nada muda.
      **E o gesto continua trocando mesmo num jogo confirmado**: recusar seria
      o produto discutindo com a dona. Quem não roda em jogo confirmado é a
      ESCADA, que é o caminho automático.

    O gesto NÃO confirma nada. Ele é o contrário de uma confirmação, e quem
    carimba é o silêncio dela (`launch_env.tique_da_escada`).

    O QUE O GESTO PROMETE:
      - troca a ponte na hora, com `origin="manual"` — a única origem que
        atravessa o gate R-04 com o jogo aberto;
      - avisa pela lightbar qual ponte ficou de pé, e avisa ANTES quando a
        troca corre risco de derrubar o controle dentro do jogo;
      - é sempre reversível pelo próprio gesto: nenhuma ponte do ciclo mata o
        caminho de volta pelo controle.

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
            # Inclui os dois casos em que a escada AVISA E PARA (o próximo
            # degrau exige reabrir o jogo ou fechar a Steam) e o caso em que
            # ela acabou. O gesto não pode ficar sem resposta: ela apertou, e
            # alguma coisa tem de mudar. Volta ao ciclo de sempre.
            alvo = proxima_ponte(atual)

        logger.info(
            "ponte_troca_pedida_por_gesto",
            de=atual,
            para=alvo,
            jogo_com_autoridade=jogo_no_controle,
            escada=passo.motivo if passo is not None else None,
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
        from hefesto_dualsense4unix.profiles.manager import ProfileManager
        from hefesto_dualsense4unix.utils.session import save_active_marker

        # FEAT-NATIVE-MODE-01: em Modo Nativo o controle está solto para o jogo —
        # o ciclo de perfil (PS+dpad) NÃO troca de perfil (re-escreveria gatilhos).
        store = getattr(daemon, "store", None)
        if store is not None and getattr(store, "native_mode_active", False):
            logger.info("profile_cycle_skip_native_mode")
            return

        # FEAT-POINT-AND-CLICK-01 (fix A-06/A8): provider lazy + appliers de
        # emulação — paridade com o profile.switch (IPC) e o autoswitch.
        manager = ProfileManager(
            controller=daemon.controller,
            store=daemon.store,
            keyboard_device_provider=lambda: getattr(
                daemon, "_keyboard_device", None
            ),
            mouse_applier=getattr(daemon, "apply_profile_mouse", None),
            suppression_applier=getattr(daemon, "apply_profile_suppression", None),
            mode_applier=getattr(daemon, "apply_profile_mode", None),
            # FEAT-RUMBLE-POLICY-PROFILE-01: política de rumble por perfil.
            rumble_policy_applier=getattr(
                daemon, "apply_profile_rumble_policy", None
            ),
            rumble_passthrough_applier=getattr(
                daemon, "apply_profile_rumble_passthrough", None
            ),
            # SOM-02/E4: o ciclo PS+D-pad é gesto MANUAL dela — troca explícita
            # de perfil, que limpa as categorias travadas (inclusive `audio`) e
            # portanto aplica o volume do perfil que entra.
            speaker_applier=getattr(daemon, "apply_profile_speaker", None),
            # PERFIL-GUARDA-O-MIC-01 (18/08/2026): o ciclo PS+D-pad é gesto MANUAL dela, e
            # `origin="manual"` é o ÚNICO caminho por onde o `mic.muted` do
            # perfil atravessa (MIC-GRAVACAO-01) — o mudo do firmware só muda
            # quando ela troca de perfil de propósito.
            mic_applier=getattr(daemon, "apply_profile_mic", None),
        )
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
    """Cria AudioControl e inicia task de consumo de BUTTON_DOWN para mic_btn."""
    from hefesto_dualsense4unix.integrations.audio_control import AudioControl

    if daemon._audio is None:
        daemon._audio = AudioControl()
    task = asyncio.create_task(mic_button_loop(daemon), name="mic_button_loop")
    daemon._tasks.append(task)
    logger.info("mic_hotkey_iniciado")



async def mic_button_loop(daemon: DaemonProtocol) -> None:
    """Consome BUTTON_DOWN do bus e aciona mute/unmute do microfone do sistema.

    Filtra apenas eventos com button='mic_btn'. Chama AudioControl e atualiza
    o LED do microfone. Não relança exceções: falhas viram warning. O mudo do
    FIRMWARE fica com o `hid-playstation`, que é o contrato de fábrica — ver o
    comentário MIC-DOIS-DONOS-01 no corpo do laço.
    E só age quando a fonte padrão do sistema é o microfone do próprio
    controle — BT-E-VPAD-01, o gate logo abaixo do sossego.

    O toggle de mute (wpctl/pactl via subprocess) e o set_mic_led (HID) são
    chamadas SÍNCRONAS bloqueantes (até ~4s). Rodá-las direto no event loop
    asyncio travaria o daemon inteiro; por isso são offloadadas para o executor
    via `daemon._run_blocking`.

    **A janela de sossego (MIC-REPIQUE-01, 19/08/2026).** O journal da noite de
    18→19/08 tem três `mic_hotkey_toggle` em 2,5 s às 01:52:27 — `muted=False`,
    `muted=True`, `muted=False`. Isso não é mão humana, e o produto não tinha
    defesa nenhuma contra isso: toda a proteção estava terceirizada para o
    debounce de 200 ms do `AudioControl`, que é inútil AQUI por três motivos,
    cada um verificável no fonte:

    1. **O relógio dele começa no INÍCIO da chamada**
       (`integrations/audio_control.py`: `self._last_call_at = now` é gravado
       ANTES dos subprocessos). Como o toggle roda dois `wpctl`/`pactl` com
       `timeout=2.0` cada, uma chamada pode levar segundos — e quando ela
       termina o debounce já expirou faz tempo. A janela efetiva é
       ``max(0, 0.2 - duração_do_toggle)``, ou seja: ZERO sempre que o áudio
       demora. É por isso que uma rajada de bordas vira uma rajada de toggles
       espaçados pela duração do subprocesso, e não um toggle só.
    2. **Ele protege a coisa errada.** 200 ms é uma medida de teclinha
       repicando; o que está do outro lado é um mudo LATCHED, do sistema
       inteiro, invisível para quem está de controle na mão dentro de um jogo.
    3. **Ele não sabe de onde vieram as bordas.** E há mais de uma fonte
       possível: `mic_btn` não vem do evdev como os outros botões — vem do
       HID cru (`ds.state.micBtn`), e esta casa já documentou "micBtn
       fantasma" ao (re)conectar (`INPUT_GRACE_SEC`, lifecycle.py:57) e já
       pegou áudio do próprio microfone sendo lido como estado de botão
       (commit `702f5b6`). Além disso o poll loop zera `previous_buttons` a
       cada blip de conexão, e um bit ainda alto vira BUTTON_DOWN de novo.

    A guarda daqui não precisa saber qual das fontes disparou: ela é contada a
    partir do FIM do toggle e engole tudo que chegar dentro de
    :data:`MIC_SOSSEGO_S`. N bordas viram UM toggle, venham de onde vierem. O
    preço de um falso engolir é um toque ignorado — visível e refazível num
    segundo; o preço de um falso toggle é a usuária muda no jogo sem saber.
    Os repiques engolidos são contados e saem no `mic_hotkey_toggle` seguinte,
    para que a próxima investigação veja a rajada em vez de adivinhá-la.
    """
    from hefesto_dualsense4unix.core.events import EventTopic

    relogio = asyncio.get_running_loop().time
    queue = daemon.bus.subscribe(EventTopic.BUTTON_DOWN)
    fim_do_ultimo_toggle = float("-inf")
    repiques = 0
    try:
        while not daemon._is_stopping():
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if payload.get("button") != "mic_btn":
                continue
            # MIC-EXPOSE-01: o flag é consultado AQUI, a cada evento, e não só
            # no boot — assim a seção `mic` do perfil/draft vale no próximo
            # toque do botão sem restart do daemon. Desligado, o botão não
            # mexe no mute do sistema (nem no LED) e o kernel segue dono do
            # mudo de microfone do próprio controle — nada de posse.
            if not getattr(daemon.config, "mic_button_toggles_system", True):
                logger.debug("mic_hotkey_desligado_por_config")
                continue
            desde = relogio() - fim_do_ultimo_toggle
            if desde < MIC_SOSSEGO_S:
                repiques += 1
                logger.debug("mic_hotkey_repique_engolido", desde_s=round(desde, 3))
                continue
            audio = daemon._audio
            if audio is None:
                continue
            try:
                # BT-E-VPAD-01, defeito 1 — o botão do microfone do CONTROLE
                # não pode mutar o microfone de OUTRO dispositivo.
                #
                # Medido em 01/08/2026: no Bluetooth o DualSense não tem placa
                # de som nenhuma (o áudio vai dentro dos reports HID), então a
                # fonte padrão do sistema é outra coisa — nesta máquina, o
                # microfone da placa-mãe. O botão alternava aquele, e o LED do
                # controle acendia para refletir um estado que não era dele.
                #
                # Das três saídas que a sprint desenhou, esta é a (a): o botão
                # só age quando a fonte padrão É o controle. É a mais honesta
                # e a mais barata. A (b) — mutar o registrador do firmware —
                # foi recusada em 01/08/2026 porque TOMA A POSSE e faz o botão
                # físico parar de valer, que é o oposto do que se espera de um
                # botão físico.
                #
                # 19/08/2026, MIC-DOIS-DONOS-01: a medição de 01/08 continua
                # de pé e o gate (a) continua sendo o primeiro portão daqui —
                # o que caducou foi a recusa CATEGÓRICA da (b). O mudo do
                # firmware é afirmado logo abaixo, mas só enquanto o botão é
                # NOSSO (`mic_button_toggles_system`, checado acima): com o
                # flag desligado não encostamos no firmware e a posse volta
                # inteira para o `hid-playstation`, que é o contrato de
                # fábrica — o botão físico segue valendo. Sem isso, os dois
                # mudos em série saíam de fase e o microfone ficava morto no
                # jogo com o `pactl` respondendo `Mute: não`.
                #
                # O `getattr`: o gate é da CAPACIDADE do backend de áudio de
                # responder "a fonte padrão é o controle?". O `AudioControl`
                # real responde, e nele o portão vale sempre; um backend que
                # não conhece a pergunta não vira portão silencioso.
                perguntar = getattr(audio, "fonte_padrao_e_o_controle", None)
                if callable(perguntar):
                    pertence = await daemon._run_blocking(perguntar)
                    if not pertence:
                        logger.info("mic_hotkey_fonte_nao_e_o_controle")
                        continue
                mudo = bool(
                    await daemon._run_blocking(audio.toggle_default_source_mute)
                )
                await daemon._run_blocking(daemon.controller.set_mic_led, mudo)
                # MIC-DOIS-DONOS-01 fica ABERTO de propósito. A leitura é certa —
                # um toque move DOIS mudos (o do firmware, que o `hid-playstation`
                # alterna na borda do botão, e o do sistema) e eles saem de fase.
                # Mas a cura proposta (afirmar o mudo do firmware junto) foi
                # RECUSADA por decisão medida, e a recusa é antiga: escrever ali
                # TOMA A POSSE e o botão físico dela para de valer (BT-E-VPAD-01,
                # 01/08; MIC-BT-DONO-01, 03/08; a linha `audio.microfone.mudo` do
                # mapa de canais; e o `controller_card.py`, que chama isso de
                # "sequestro silencioso que esta sprint foi fechar"). No rádio nem
                # se sustenta — a posse EVAPORA, medido em 03/08: 100% -> 46% ->
                # 100%, porque `_mic_mute_desejado` é atributo de um handle que
                # morre a cada reconexão. E em co-op escreveria no controle
                # ERRADO: o `BUTTON_DOWN` não carrega `uniq`, então o jogador 2
                # mutaria o firmware do jogador 1.
                logger.info(
                    "mic_hotkey_toggle",
                    muted=mudo,
                    sistema_mudo=mudo,
                    repiques_engolidos=repiques,
                )
                repiques = 0
            except Exception as exc:
                logger.warning("mic_hotkey_falhou", err=str(exc))
            finally:
                fim_do_ultimo_toggle = relogio()
    finally:
        daemon.bus.unsubscribe(EventTopic.BUTTON_DOWN, queue)


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
    "CICLO_DE_PONTES",
    "CORES_DO_MODO",
    "MIC_SOSSEGO_S",
    "MODO_NATIVO",
    "MODO_STEAM_INPUT",
    "PONTE_DUALSENSE",
    "PONTE_MOUSE_TECLADO",
    "PONTE_XBOX",
    "HotkeySubsystem",
    "avisar_troca_de_modo",
    "build_next_bridge_callback",
    "build_profile_cycle_callback",
    "build_ps_long_press_callback",
    "build_ps_solo_callback",
    "mic_button_loop",
    "modo_vigente",
    "ponte_atual",
    "proxima_ponte",
    "start_hotkey_manager",
    "start_mic_hotkey",
    "stop_hotkey_manager",
]
