"""Subsystem Hotkey — gerencia HotkeyManager e hotkey de microfone."""
from __future__ import annotations

import asyncio
import contextlib
import contextvars
import os
import subprocess as _sp
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon.subsystems import recado_do_microfone
from hefesto_dualsense4unix.integrations import fora_do_servico, ponte_tentativa
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

#: propósito em menos de um segundo. Ver o docstring de `mic_button_loop` para
MIC_SOSSEGO_S = 1.0


#: O PS tem DOIS donos, e a precedência é escrita: `Profile.button_actions["ps"]`
#: `profiles/manager.apply_button_actions` o escreve a cada ativação, pelo
_ATRIBUTO_DA_ACAO_DO_PS = "_acao_do_ps_do_perfil"

_TOKENS_QUE_O_TECLADO_ENTREGA: Final[frozenset[str]] = frozenset({
    "__OPEN_OSK__", "__CLOSE_OSK__", "__TOGGLE_OSK__",
})


def definir_acao_do_ps(daemon: Any, token: str | None) -> None:
    """Guarda o que o PERFIL ATIVO deu ao botão PS. `None` = o perfil não opinou."""
    setattr(daemon, _ATRIBUTO_DA_ACAO_DO_PS, token)


def acao_do_ps_do_perfil(daemon: Any) -> str | None:
    """O token que o perfil ativo deu ao PS, ou `None` — leitura de memória."""
    token = getattr(daemon, _ATRIBUTO_DA_ACAO_DO_PS, None)
    return str(token) if token else None


def _o_ps_digita(token: str | None) -> bool:
    """O token escolhido é coisa que o teclado virtual sabe entregar?"""
    if not token:
        return False
    partes = token.split("+")
    return all(
        p.startswith("KEY_") or p in _TOKENS_QUE_O_TECLADO_ENTREGA for p in partes
    )


def _digitar_o_ps(daemon: Any, token: str) -> bool:
    """Emite, UMA vez, a tecla que o perfil deu ao PS. Devolve se emitiu."""
    teclado = getattr(daemon, "_keyboard_device", None)
    if teclado is None:
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


def _a_metade_da_maquina(cfg: Any, escolha: str | None, do_computador: Any = None) -> str:
    """Qual ato do computador o toque no PS dispara: um token do ⑥, ou ``custom``."""
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag

    if do_computador is not None and getattr(do_computador, "declarada", False):
        da_maquina = str(do_computador.faz)
    else:
        degrau = str(getattr(cfg, "ps_button_action", "steam"))
        da_maquina = {"steam": ag.ABRIR_A_STEAM, "none": ag.NADA}.get(degrau, degrau)
    if escolha is None:
        return da_maquina
    if not _o_ps_digita(escolha):
        logger.info("ps_solo_escolha_sem_atendente", token=escolha)
    return da_maquina


def _a_acao_da_maquina(da_maquina: str, comando: Any, **ato: Any) -> None:
    """A metade do PS que fala com o sistema: o ⑥ da tabela, ou o programa dela."""
    appid = _jogo_aberto_agora()
    if appid is not None:
        logger.info("hotkey_ps_solo_skip_jogo_vivo", appid=appid, sinal="wrapper")
        return
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag

    logger.info("gesto_fez", gesto=ag.GESTO_DO_PS, acao=da_maquina, **_de_quem(ato.get("quem")))
    if da_maquina == ag.ABRIR_A_STEAM:
        from hefesto_dualsense4unix.integrations.steam_launcher import open_or_focus_steam

        open_or_focus_steam()
        return
    if da_maquina != "custom":
        atos = ato.get("atos")
        if atos is not None:
            atos.fazer_pelo_ps(da_maquina, ato.get("escolha"), ato.get("quem"),
                               ato.get("laco"), ato.get("contexto"))
        return
    from hefesto_dualsense4unix.integrations.ambiente_do_jogo import ambiente_limpo

    try:
        abertura = fora_do_servico.abrir(
            comando, env=ambiente_limpo(os.environ), popen=_sp.Popen
        )
    except Exception as exc:
        logger.warning("hotkey_ps_solo_custom_falhou", err=str(exc))
        return
    logger.info(
        "hotkey_ps_solo_custom_aberto",
        caminho=abertura.caminho,
        unidade=abertura.unidade,
        motivo=abertura.motivo,
    )


@dataclass
class _GestoDoPs:
    """O callback do PS solo: ``fazer`` no laço, a ação da máquina no ``fio``."""

    fazer: Any
    fio: fora_do_servico.FioDeTrabalho

    def __call__(self) -> None:
        self.fazer()

    def esperar(self, teto: float | None = None) -> bool:
        return self.fio.esperar(teto)


def build_ps_solo_callback(daemon: DaemonProtocol, atos: Any = None) -> Any:
    """Cria o callback on_ps_solo que lê self.config em runtime (REFACTOR-DAEMON-RELOAD-01)."""
    fio = fora_do_servico.FioDeTrabalho(
        "hefesto-acao-do-ps",
        ao_falhar=lambda erro: logger.warning("hotkey_ps_solo_acao_falhou", err=str(erro)),
    )
    quem_atende: list[Any] = [atos]

    def _on_ps_solo() -> None:
        cfg = daemon.config
        escolha = acao_do_ps_do_perfil(daemon)
        digita = _o_ps_digita(escolha)
        do_computador = _o_ps_do_computador(daemon)
        da_maquina = _a_metade_da_maquina(cfg, escolha, do_computador)
        if da_maquina == _NADA_DO_GESTO and not digita:
            return
        store = getattr(daemon, "store", None)
        if store is not None and getattr(store, "native_mode_active", False):
            logger.info("hotkey_ps_solo_skip_native_mode")
            return
        if getattr(daemon, "_emulation_suppressed", False):
            logger.info("hotkey_ps_solo_skip_modo_jogo")
            return
        if digita and escolha is not None:
            _digitar_o_ps(daemon, escolha)
        if da_maquina == _NADA_DO_GESTO:
            return
        if getattr(daemon, "display_authority", None) == "game":
            logger.info("hotkey_ps_solo_skip_jogo_vivo", sinal="autoridade")
            return
        comando: Any = None
        if da_maquina == "custom":
            comando = cfg.ps_button_command
            if not comando:
                logger.warning("hotkey_ps_solo_custom_sem_comando")
                return
        ato = _o_ato_do_ps_para_o_fio(daemon, quem_atende, do_computador)
        if not fio.disparar(lambda: _a_acao_da_maquina(da_maquina, comando, **ato)):
            logger.info("hotkey_ps_solo_acao_em_voo", acao=da_maquina)

    return _GestoDoPs(fazer=_on_ps_solo, fio=fio)


#: pegar": máscara Xbox primeiro não, porque a casa parte do DualSense — a
#: máscaras: Sony DualSense → Xbox → Navegação → Sony DualSense, os mesmos três
PONTE_DUALSENSE = "dualsense"
PONTE_XBOX = "xbox"
PONTE_MOUSE_TECLADO = "mouse_teclado"
CICLO_DE_PONTES: tuple[str, ...] = (PONTE_DUALSENSE, PONTE_XBOX, PONTE_MOUSE_TECLADO)

MODO_STEAM_INPUT = "steam_input"
MODO_NATIVO = "nativo"

#: DualSense era AZUL (0, 60, 255). Não é decisão apagada, é fato corrigido: o
#: mais precisa distinguir. A máscara DualSense é o "Hefesto na frente", e a
CORES_DO_MODO: dict[str, tuple[int, int, int]] = {
    MODO_STEAM_INPUT: (139, 233, 253),
    PONTE_XBOX: (80, 250, 123),
    MODO_NATIVO: (248, 248, 242),
    PONTE_DUALSENSE: (255, 121, 198),
    PONTE_MOUSE_TECLADO: (255, 184, 108),
}
COR_AVISO_RISCO = (255, 0, 0)
PULSO_SEG = 0.14

#: daemon que sobe já em máscara DualSense não pode piscar como se ela tivesse
_NUNCA_ANUNCIADO = object()

_AVISO_EM_CURSO = threading.Lock()


def ponte_atual(daemon: DaemonProtocol) -> str:
    """A ponte de pé AGORA, lida do estado VIVO — não da config.

    O estado vivo é o vpad: se existe, a ponte é a máscara dele; se não
    existe, o controle está indo para o desktop (mouse+teclado). Ler do
    `config.gamepad_flavor` seria repetir o defeito da noite de 18/08, em que
    o perfil dizia `xbox` e o vivo dizia `dualsense` — e o daemon ficou
    destruindo e recriando o vpad em laço por acreditar no papel.

    NOTA DATADA — MODO-DE-CONEXAO-01, 13/09/2026. Com o vpad de pé, a ponte é o
    CAMINHO dele, e não o `device.flavor`: ler a máscara travava o ciclo com
    máscara no cartão (todo aperto pedia uma máscara que o cartão vencia, e o
    vivo nunca virava o pedido). O caminho é o `config.gamepad_caminho`, que só
    é escrito DEPOIS de o vpad alcançar o pedido (`gamepad._guardar_o_caminho`)
    — é leitura do vivo, não do papel —, e sem escolha ele sai da máscara que o
    vpad veste, como antes.
    """
    from hefesto_dualsense4unix.integrations.uinput_gamepad import normalize_flavor
    from hefesto_dualsense4unix.integrations.virtual_pad import caminho_resolvido

    device = getattr(daemon, "_gamepad_device", None)
    if device is None:
        return PONTE_MOUSE_TECLADO
    return caminho_resolvido(
        getattr(getattr(daemon, "config", None), "gamepad_caminho", None),
        normalize_flavor(getattr(device, "flavor", None)),
    )


def _cor_do_degrau(degrau: Any) -> tuple[int, int, int] | None:
    """A cor de `CORES_DO_MODO` que anuncia um degrau da `ESCADA`."""
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
    """Pinta uma sequência (cor, segundos) na lightbar e devolve a cor resolvida."""
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
    """O MODO de pé AGORA, lido do estado VIVO. AVISO-DE-MODO-01."""
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
    """Manda a piscada para uma thread. True = saiu daqui. AVISO-DE-MODO-01."""
    piscar = getattr(getattr(daemon, "controller", None), "piscar_aviso_de_modo", None)
    if not callable(piscar):
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
    """Constrói a ponte `alvo`. True = de pé ao final."""
    setter = getattr(daemon, "set_gamepad_emulation", None)
    if setter is None:
        logger.warning("ponte_sem_setter_de_gamepad")
        return False
    if alvo in (PONTE_DUALSENSE, PONTE_XBOX):
        return bool(
            setter(True, None, origin="manual", caminho=alvo, grava_o_modo="controle")
        )
    # fazia `mouse.emulation.restore` e mais nada. O mesmo modo com DOIS donos
    # `keyboard_emulation.flag`, porque `set_keyboard_emulation` persiste por
    setter(False, origin="manual")
    arranjo = getattr(daemon, "aplicar_o_arranjo_do_desktop", None)
    if not callable(arranjo):
        logger.warning("ponte_sem_arranjo_do_desktop")
        return True
    with contextlib.suppress(Exception):
        arranjo(origin="manual", grava_o_modo="controle")
    return True


def _appid_do_jogo_do_wrapper() -> int | None:
    """O appid do jogo que o wrapper lançou e que ainda roda, ou None."""
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

    NOTA DATADA — MODO-DE-CONEXAO-01, 13/09/2026. O gesto troca o CAMINHO, e não
    a máscara, e grava no perfil ATIVO logo que o aparelho concorda, sem esperar
    silêncio nem jogo — é a regra dela de 13/09, citada na sprint. O rastro por
    jogo de cima continua, e o que ele alinha no perfil do jogo passou a ser
    `mode.caminho`. Desde a O-MODO-SE-GRAVA-ONDE-ELE-MUDA-01 (29/09/2026) quem
    grava é o setter do daemon (`Daemon.gravar_o_modo_escolhido`), o mesmo do
    chip: `_aplicar_ponte` manda `grava_o_modo="controle"`.

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
        recria o vpad (`gamepad.py:1799` para, `:2494` cria — slot único, sem
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
        store = getattr(daemon, "store", None)
        if store is not None and getattr(store, "native_mode_active", False):
            logger.info("ponte_ciclo_skip_native_mode")
            return

        atual = ponte_atual(daemon)
        jogo_no_controle = getattr(daemon, "display_authority", "unknown") == "game"

        # que carrega o dado: o mapa de canais diz por que a máscara DualSense
        passo = None
        with contextlib.suppress(Exception):
            passo = ponte_tentativa.avancar_por_gesto(
                daemon, jogo_vivo=jogo_no_controle
            )
        degrau_da_escada = None
        if passo is not None and passo.caminho is not None:
            alvo = passo.caminho
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
            with contextlib.suppress(Exception):
                ponte_tentativa.degrau_subiu(daemon, degrau_da_escada)
        if efetiva == alvo:
            with contextlib.suppress(Exception):
                ponte_tentativa.gesto_deixou_de_pe(
                    daemon,
                    appid=_appid_do_jogo_do_wrapper(),
                    caminho=efetiva,
                    jogo_vivo=jogo_no_controle,
                )
            # setter do daemon (`grava_o_modo="controle"` em `_aplicar_ponte`,
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
            return
        # desfechos diferentes (aplicou, já-estava, bloqueado), então o sinal
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
        from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon, os_perfis_de_escolher

        store = getattr(daemon, "store", None)
        if store is not None and getattr(store, "native_mode_active", False):
            logger.info("profile_cycle_skip_native_mode")
            return

        # FÁBRICA — paridade com o `profile.switch` (IPC), o autoswitch e o
        manager = gerente_do_daemon(daemon, store=daemon.store)
        profiles = os_perfis_de_escolher(await daemon._run_blocking(manager.list_profiles))
        if len(profiles) < 2:
            logger.info("profile_cycle_skip", n=len(profiles))
            return
        names = [p.name for p in profiles]
        active = daemon.store.active_profile
        idx = names.index(active) if active in names else 0
        target = names[(idx + direction) % len(names)]

        with contextlib.suppress(Exception):
            await daemon._run_blocking(daemon.controller.set_led, (255, 255, 255))
            await asyncio.sleep(0.12)

        lock_antes = getattr(daemon.store, "_manual_profile_lock_until", 0.0)
        daemon.store.mark_manual_profile_lock(
            _time.monotonic() + MANUAL_PROFILE_LOCK_SEC
        )
        # persiste a intenção em session.json (paridade com o profile.switch).
        try:
            profile = await daemon._run_blocking(
                functools.partial(manager.activate, target, origin="manual")
            )
        except Exception:
            daemon.store.mark_manual_profile_lock(lock_antes)
            raise
        logger.info("profile_cycled", direction=direction, to=profile.name)

    return _cycle


def start_hotkey_manager(daemon: DaemonProtocol) -> None:
    """Instancia HotkeyManager e atribui a daemon._hotkey_manager."""
    from hefesto_dualsense4unix.integrations.hotkey_daemon import (
        DEFAULT_COMBO_NEXT,
        DEFAULT_COMBO_PONTE,
        DEFAULT_COMBO_PREV,
        HotkeyConfig,
        HotkeyManager,
    )

    # mesmo caminho do profile.switch). Antes ficavam disabled_until_wired: o
    hotkey_config = HotkeyConfig(
        ps_long_press_ms=getattr(daemon.config, "ps_long_press_ms", 0),
        next_profile=DEFAULT_COMBO_NEXT,
        prev_profile=DEFAULT_COMBO_PREV,
        next_bridge=DEFAULT_COMBO_PONTE,
    )
    atos = _AtosDoGesto(daemon)
    daemon._hotkey_manager = HotkeyManager(
        on_ps_solo=build_ps_solo_callback(daemon, atos),
        on_ps_long_press=atos.callback("ps_options"),
        on_next=atos.callback("ps_cima"),
        on_prev=atos.callback("ps_baixo"),
        on_next_bridge=atos.callback("ps_r3"),
        on_next_mask=atos.callback("ps_l3"),
        config=hotkey_config,
    )
    logger.info(
        "hotkey_manager_started",
        ps_button_action=daemon.config.ps_button_action,
        ps_long_press_ms=hotkey_config.ps_long_press_ms,
        next_prev_combos="ps+dpad_up / ps+dpad_down",
        ponte_combo="ps+r3", mascara_combo="ps+l3",
        gestos=atos.resumo(),
    )


def stop_hotkey_manager(daemon: DaemonProtocol) -> None:
    """Descarta o HotkeyManager. Idempotente."""
    daemon._hotkey_manager = None


def start_mic_hotkey(daemon: DaemonProtocol) -> None:
    """Sobe os DOIS laços do microfone: as bordas com endereço, e a eleição."""
    from hefesto_dualsense4unix.daemon.subsystems.mic_da_mesa import start_mic_da_mesa
    from hefesto_dualsense4unix.integrations.audio_control import AudioControl

    if daemon._audio is None:
        daemon._audio = AudioControl()
    start_mic_da_mesa(daemon)
    for laco in (mic_button_loop, mic_do_jogo_loop):
        daemon._tasks.append(asyncio.create_task(laco(daemon), name=laco.__name__))
    # `state_full` roda a 20 Hz e só LÊ o que o laço já leu. O laço acorda pelo
    tarefa_do_canal = asyncio.create_task(
        canal_do_microfone_loop(daemon), name="canal_do_microfone_loop"
    )
    daemon._tasks.append(tarefa_do_canal)
    logger.info("mic_hotkey_iniciado")


CANAL_TTL_S: float = 2.0

#: varredura o `state_full` não publica as chaves, e ausência é a resposta
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

    `canal_ativo` aqui compara a fonte DESTE controle com a fonte ativa do
    sistema, pelos donos de sempre (`fonte_de_captura_do_uniq`, `fonte_ativa`);
    o laço o acende também para quem o ATO pôs no ar sem ser o padrão — ver
    `_ler_o_canal_deste` (OS-QUATRO-NO-AR-01). Escrever uma terceira régua aqui
    daria ao selo uma verdade diferente da do gesto.
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
    """`pactl get-source-mute` — `None` quando a pergunta não teve resposta."""
    import os
    import subprocess

    try:
        r = _mudo_pelo_retrato(fonte) or subprocess.run(
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
    """Relê o canal de cada controle quando o som muda, ou a cada `CANAL_TTL_S`."""
    while not daemon._is_stopping():
        await _esperar_o_som_mudar(CANAL_TTL_S, daemon)
        uniqs = _uniqs_conectados(daemon)
        if not uniqs:
            _a_mesa_vazia_esquece_o_canal(daemon)
            continue
        for uniq in uniqs:
            if daemon._is_stopping():
                return
            with contextlib.suppress(Exception):
                _CANAL_POR_UNIQ[uniq] = await _ler_o_canal_deste(daemon, uniq)
        for fora in [u for u in _CANAL_POR_UNIQ if u not in uniqs]:
            _CANAL_POR_UNIQ.pop(fora, None)
        await _conferir_no_prazo(daemon, uniqs)


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
                logger.warning("mic_da_mesa_sem_endereco")
                continue
            if not getattr(daemon.config, "mic_button_toggles_system", True):
                logger.debug("mic_hotkey_desligado_por_config")
                continue
            mudo = bool(payload.get("mudo"))
            if _borda_e_eco_do_ato(uniq, mudo):
                logger.debug("mic_da_mesa_eco_do_ato_engolido", uniq=uniq, mudo=mudo)
                continue
            ligado = _o_que_a_borda_pede(daemon, uniq, mudo)
            em = _instante_da_borda(payload.get("em"))
            resposta = _a_resposta_do_jogo(uniq, em)
            if resposta is not None:
                ligado = not resposta
                logger.info("mic_ato_segue_o_jogo", uniq=uniq, ligado=ligado)
            try:
                await ligar_o_microfone(daemon, uniq, ligado=ligado, em=em)
            except Exception as exc:
                logger.warning("mic_hotkey_falhou", err=str(exc))
    finally:
        daemon.bus.unsubscribe(EventTopic.MIC_DA_MESA, queue)


def _o_que_a_borda_pede(daemon: DaemonProtocol, uniq: str, mudo: bool) -> bool:
    """A borda do plástico traduzida em ATO. MIC-FASE-01 (17/09/2026)."""
    if not mudo:
        return True

    if _eleitor(daemon).eleito is not None:
        return False
    if not _no_ar_da_sessao(daemon).esta(uniq):
        logger.info("mic_da_mesa_fase_reancorada", uniq=uniq)
        return True
    return False


#: 548 ms** (duas medições, nos dois sentidos) até o `state_full` publicar o
CONFIRMACAO_DO_MUDO_S: float = 3.0

PASSO_DA_CONFIRMACAO_S: float = 0.1

ECO_DO_ATO_S: float = 2.0

_ECO_DO_ATO: dict[str, tuple[float, bool]] = {}


def _relogio() -> float:
    """O monotônico, isolado num nome para o teste poder congelá-lo."""
    import time

    return time.monotonic()


def _marcar_eco_do_ato(uniq: str, mudo: bool) -> None:
    """Anota que NÓS escrevemos este valor no byte do mudo deste controle."""
    _ECO_DO_ATO[uniq] = (_relogio(), bool(mudo))


def _borda_e_eco_do_ato(uniq: str, mudo: bool) -> bool:
    """A borda que chegou é o eco da nossa escrita, e não um gesto dela?"""
    marca = _ECO_DO_ATO.get(uniq)
    if marca is None:
        return False
    quando, escrito = marca
    if bool(mudo) != escrito:
        return False
    if (_relogio() - quando) >= ECO_DO_ATO_S:
        _ECO_DO_ATO.pop(uniq, None)
        return False
    _ECO_DO_ATO.pop(uniq, None)
    return True


@dataclass(frozen=True)
class MetadeDoAto:
    """Uma das duas metades do ato, e o motivo quando ela não aconteceu."""

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

        *"o botão fisico do mic se ligado no  # (noqa-acento: citação dela)
        microfone ele fica ligado tambem.  # (noqa-acento: citação dela)
        indepente se nativo ou virtual"*  # (noqa-acento: citação dela)
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
        """A frase que diz QUAL metade faltou — vazia quando o ato está feito."""
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
    daemon: DaemonProtocol, uniq: str, *, ligado: bool, em: float | None = None
) -> AtoDoMicrofone:
    """O ATO — e é a MESMA função para o botão do plástico e o da tela."""
    from hefesto_dualsense4unix.daemon.subsystems.luz_do_mic import a_pessoa_mandou

    a_pessoa_mandou(uniq, em)
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
    await _o_disco_guarda_o_ato(daemon, ato)
    return ato


async def _o_disco_guarda_o_ato(daemon: DaemonProtocol, ato: AtoDoMicrofone) -> None:
    """O último ato vale, e o DONO do mudo o guarda: o controle, no `maquina.json`."""
    if not (ato.canal_no_sistema.feita or ato.firmware.feita):
        logger.info("mic_ato_nao_gravado", uniq=ato.uniq, motivo="nada_ficou_de_pe")
        return
    from hefesto_dualsense4unix.utils.maquina import (
        chave_do_controle,
        gravar_o_mudo_do_microfone,
    )

    chave = chave_do_controle(str(ato.uniq or ""))
    if chave is None:
        logger.info("mic_ato_nao_gravado", uniq=ato.uniq, motivo="sem_endereco_de_controle")
        return
    mudo = not ato.ligado
    try:
        gravou = await daemon._run_blocking(gravar_o_mudo_do_microfone, chave, mudo)
    except Exception as exc:
        logger.warning("mic_ato_nao_gravado", uniq=chave, motivo="erro", err=str(exc))
        return
    if gravou:
        logger.info("mic_mudo_gravado_no_controle", uniq=chave, mudo=mudo)
    else:
        logger.info("mic_ato_nao_gravado", uniq=chave, motivo="o_disco_recusou")


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
    """O ato foi RECUSADO: o registro volta a ser o que era antes dele."""
    if not ligado:
        return
    if antes is None:
        esquecer_a_palavra(uniq)
    else:
        dizer_no_ar(uniq, antes)
    logger.info("mic_da_mesa_palavra_desfeita", uniq=uniq, voltou_para=antes)


async def _metade_do_firmware(
    daemon: DaemonProtocol,
    uniq: str,
    ligado: bool,
    *,
    marcar_eco: bool = True,
    recado: bool = True,
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
    if (
        isinstance(mudo_agora, bool)
        and mudo_agora == mudo_desejado
        and _a_posse_nao_desdiz(controller, uniq, mudo_desejado)
    ):
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
    if marcar_eco:
        _marcar_eco_do_ato(uniq, mudo_desejado)
    _agendar_a_devolucao_da_posse(daemon, uniq, mudo_desejado, recado=recado)
    return MetadeDoAto(True)


def _a_posse_nao_desdiz(controller: Any, uniq: str, mudo_desejado: bool) -> bool:
    """A posse do mudo deste controle é do kernel, ou já pede o mesmo que o ato?"""
    leitor = getattr(controller, "microphone_mute_for", None)
    if not callable(leitor):
        return True
    posse: Any = None
    with contextlib.suppress(Exception):
        posse = leitor(uniq)
    return posse is None or (isinstance(posse, bool) and posse == mudo_desejado)


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
    daemon: DaemonProtocol, uniq: str, mudo_desejado: bool, *, recado: bool = True
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
            _confirmar_e_devolver(daemon, uniq, mudo_desejado, recado=recado),
            name=f"mic_ato_confirma_{uniq}",
        )
        daemon._tasks.append(task)


async def _confirmar_e_devolver(
    daemon: DaemonProtocol, uniq: str, mudo_desejado: bool, *, recado: bool = True
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
                await daemon._run_blocking(_mutar, devolver, None, uniq)
            logger.info(
                "mic_ato_posse_devolvida", uniq=uniq, esperou_s=round(esperou, 2)
            )
            return
    logger.info("mic_ato_represado", uniq=uniq, mudo_desejado=mudo_desejado)
    if not recado:
        return
    # recado do represamento nunca chegou ao `state_full` — o log dizia
    with contextlib.suppress(Exception):
        recado_do_microfone.anotar(
            daemon,
            uniq,
            gesto="recusa",
            ok=False,
            motivo=MOTIVO_FIRMWARE_REPRESADO,
        )


MOTIVO_FIRMWARE_REPRESADO: Final[str] = (
    "o microfone foi ligado no canal deste controle, mas o Hefesto não "
    "conseguiu escrever o mudo no aparelho — enquanto um jogo estiver com o "
    "controle (Modo Nativo) quem manda no plástico é ele, e o pedido fica "
    "guardado até o Hefesto poder escrever"
)


async def _eleger_ou_devolver(
    daemon: DaemonProtocol, uniq: str, mudo: bool
) -> ResultadoDaEleicao:
    """O controle passou a NÃO-MUDO: elege. O ELEITO passou a MUDO: devolve."""
    eleitor = _eleitor(daemon)
    dono_antes = eleitor.eleito
    no_ar = _no_ar_da_sessao(daemon)
    fora_do_padrao = not _mesmo_controle(eleitor.eleito, uniq)
    if mudo:
        if fora_do_padrao and not no_ar.esta(uniq):
            # o `state_full` usa: `recado_do_microfone.mesa_de_agora`. Esta
            # faz: o MESMO `state_full` saía com `eleito_na_mesa: false` e o
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
        resultado: ResultadoDaEleicao
        if fora_do_padrao:
            resultado = ResultadoDaEleicao(ok=True)
        else:
            resultado = await _passar_o_padrao_ou_devolver(daemon, eleitor, no_ar, uniq)
        aceso = _mesmo_controle(eleitor.eleito, uniq)
        if not aceso:
            no_ar.saiu(uniq)
    else:
        conectados = _uniqs_conectados(daemon)
        resultado = await daemon._run_blocking(
            eleitor.eleger_o_controle, uniq, conectados
        )
        aceso = bool(resultado.ok)
        if resultado.ok:
            no_ar.entrou(uniq)
    logger.info(
        "mic_da_mesa_eleicao",
        uniq=uniq,
        mudo=mudo,
        ok=resultado.ok,
        ativo=resultado.ativo,
        motivo=resultado.motivo,
    )
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
    """O plástico de quem perdeu o microfone SEM TER TOCADO EM NADA."""
    # defeito é de FORMA, não de lógica. Medido na bancada dela com o DualSense
    # (noqa-acento: a citação literal dela vem na linha seguinte)
    antes = norm_mac(dono_antes) or dono_antes
    tocou = norm_mac(quem_tocou) or quem_tocou
    eleito_agora = norm_mac(eleitor.eleito) or eleitor.eleito
    if dono_antes is None or antes == tocou:
        return
    if eleito_agora == antes:
        return
    # em 10/09/2026 com dois DualSense no rádio: sem esta guarda, ligar o
    if _no_ar_da_sessao(daemon).esta(dono_antes):
        logger.info(
            "mic_da_mesa_ex_dono_continua_no_ar",
            ex_dono=dono_antes,
            por=quem_tocou,
            eleito_agora=eleitor.eleito,
        )
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
    """Chama `set_mic_led(aceso, uniq=...)`, tolerando backend sem endereço."""
    try:
        acender(aceso, uniq=uniq)
    except TypeError:
        logger.warning("mic_da_mesa_led_sem_endereco", uniq=uniq)
        acender(aceso)


def devolver_a_luz_ao_kernel(daemon: DaemonProtocol) -> int:
    """Devolve a POSSE do `common[8]` de todos os controles da mesa."""
    devolver = getattr(daemon.controller, "set_microphone_led", None)
    if not callable(devolver):
        # `PyDualSenseController`. Num daemon dublado a devolução não acontece,
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


def _mesmo_controle(a: str | None, b: str | None) -> bool:
    """Os dois endereços são o MESMO controle? Compara normalizado."""
    if not a or not b:
        return False
    return (norm_mac(a) or a) == (norm_mac(b) or b)


class MicrofonesNoAr:
    """Quem está com o microfone NO AR agora — por controle, em ordem de chegada."""

    #: e a nova sobe no mesmo nó (`bt_mic._aplicar_a_palavra_dela`). Com o laço
    LEITURAS_SEM_CANAL_ATE_SAIR: int = 2

    def __init__(self) -> None:
        self._ordem: list[str] = []
        self._sem_canal: dict[str, int] = {}
        self._canal_visto: set[str] = set()

    @staticmethod
    def _chave(uniq: str) -> str:
        return norm_mac(uniq) or uniq

    def entrou(self, uniq: str) -> None:
        """O ato conferiu: `uniq` está no ar, e é o mais novo."""
        chave = self._chave(uniq)
        self._ordem = [u for u in self._ordem if self._chave(u) != chave]
        self._ordem.append(uniq)
        self._sem_canal.pop(chave, None)
        self._canal_visto.discard(chave)

    def saiu(self, uniq: str) -> bool:
        """`uniq` saiu do ar. Devolve se ele estava."""
        chave = self._chave(uniq)
        antes = len(self._ordem)
        self._ordem = [u for u in self._ordem if self._chave(u) != chave]
        self._sem_canal.pop(chave, None)
        self._canal_visto.discard(chave)
        return len(self._ordem) != antes

    def esta(self, uniq: str | None) -> bool:
        if not uniq:
            return False
        chave = self._chave(uniq)
        return any(self._chave(u) == chave for u in self._ordem)

    def todos(self) -> list[str]:
        """Os que estão no ar, do mais velho ao mais novo. Cópia."""
        return list(self._ordem)

    def do_mais_novo_ao_mais_velho(self, exceto: str) -> list[str]:
        """Os candidatos a herdar o padrão de `exceto`, na ordem em que herdam."""
        chave = self._chave(exceto)
        return [u for u in reversed(self._ordem) if self._chave(u) != chave]

    def anotar_leitura(
        self, uniq: str, publicado: bool | None, *, na_mesa: bool | None = None
    ) -> bool:
        """Uma leitura do canal de `uniq`. `True` = ele saiu do ar DE FATO agora.

        `None` é *"não sei"* e não conta para nada — nem para sair, nem para
        zerar a conta de quem já faltou uma vez.

        **SÓ SOME O CANAL QUE JÁ SUBIU — 22/09/2026.** Medido no journal dela,
        com dois DualSense no rádio: o P2 nasceu no ar às 13:51:53, este laço
        contou duas faltas e o tirou às 13:51:56, e o canal dele só foi
        publicado às 13:52:01. O nascimento (`nascer_no_ar`) põe o controle
        aqui ANTES de a ponte publicar a fonte, e a falta de quem ainda não
        tinha canal era lida como *"o canal sumiu"*. O padrão escapava porque o
        `canal_ativo` dele vem da fonte padrão; o segundo, o terceiro e o
        quarto perdiam a palavra e o selo pintava DESLIGADO. Então a falta só
        conta depois de o canal ter sido visto de pé desde a entrada — menos
        quando o controle saiu da mesa (`na_mesa is False`), que é ausência de
        fato.
        """
        chave = self._chave(uniq)
        if publicado is None:
            return False
        if publicado:
            self._sem_canal.pop(chave, None)
            self._canal_visto.add(chave)
            return False
        if na_mesa is not False and chave not in self._canal_visto:
            return False
        vezes = self._sem_canal.get(chave, 0) + 1
        self._sem_canal[chave] = vezes
        return vezes >= self.LEITURAS_SEM_CANAL_ATE_SAIR


def _no_ar_da_sessao(daemon: Any) -> MicrofonesNoAr:
    """Quem está no ar nesta SESSÃO do daemon. Um só, pelo molde de `_eleitor`."""
    no_ar = getattr(daemon, "_microfones_no_ar", None)
    if not isinstance(no_ar, MicrofonesNoAr):
        no_ar = MicrofonesNoAr()
        daemon._microfones_no_ar = no_ar
    return no_ar


#     ativar e ele ser reconhecido. isso deveria ta  # (noqa-acento) dela
#     ativado por padrao"*  # (noqa-acento) dela, 17/09/2026
# `interface/cartao_do_controle.acao_mic` são LEITURA pura do que o `state_full`


def _o_firmware_esta_mudo(daemon: DaemonProtocol, uniq: str) -> bool:
    """O bit do mudo DESTE controle está ligado agora? `None` não é silêncio."""
    leitor = getattr(getattr(daemon, "controller", None), "audio_status_for", None)
    if not callable(leitor):
        return False
    try:
        estado = leitor(uniq)
    except Exception:
        logger.debug("mic_nascimento_leitura_do_mudo_falhou", exc_info=True)
        return False
    mudo = estado.get("mic_mudo") if isinstance(estado, dict) else None
    return mudo is True


async def _o_controle_pede_silencio(daemon: DaemonProtocol, uniq: str) -> bool:
    """Ela calou ESTE microfone? Pergunta ao dono da resposta."""
    controller = getattr(daemon, "controller", None)
    if controller is None:
        return False
    try:
        from hefesto_dualsense4unix.profiles.manager import ProfileManager

        manager = ProfileManager(controller=controller)
        correr = getattr(daemon, "_run_blocking", None)
        if callable(correr):
            return bool(await correr(manager.o_controle_pede_silencio, uniq))
        return bool(manager.o_controle_pede_silencio(uniq))
    except Exception:
        logger.debug("mic_nascimento_leitura_do_mudo_do_controle_falhou", exc_info=True)
        return False


def _fila_do_nascimento(daemon: Any) -> asyncio.Lock:
    """UM nascimento por vez nesta sessão do daemon. Molde de `_eleitor`."""
    fila = getattr(daemon, "_fila_do_nascimento_do_mic", None)
    if not isinstance(fila, asyncio.Lock):
        fila = asyncio.Lock()
        daemon._fila_do_nascimento_do_mic = fila
    return fila


async def nascer_no_ar(daemon: DaemonProtocol, uniq: str) -> bool:
    """O microfone deste controle NASCE NO AR, sem gesto nenhum dela."""
    if not uniq or not norm_mac(str(uniq)):
        logger.debug("mic_nascimento_sem_endereco", uniq=uniq)
        return False
    async with _fila_do_nascimento(daemon):
        return await _nascer_no_ar_na_vez(daemon, uniq)


def _ela_desligou_este_microfone(daemon: DaemonProtocol, uniq: str) -> bool:
    """O `maquina.json` diz `microfone: false` para ESTE controle?"""
    from hefesto_dualsense4unix.daemon.subsystems.bt_mic import uniqs_negados

    chave = norm_mac(str(uniq)) or ""
    return bool(chave) and chave in uniqs_negados(getattr(daemon, "config", None))


def _microfone_que_ja_e_da_maquina() -> str | None:
    """A captura que NÃO é o controle e que o nascimento não pode desalojar.

    `None` = o controle PODE virar a fonte padrão ao nascer. Um nome = existe
    outro microfone de verdade (headset, webcam, a entrada da placa) e a pessoa
    não pediu o do controle como padrão.

    **O DEFEITO, e ele só não aparecia na máquina dela.** Com a mesa sem dono o
    nascimento elegia pelo caminho de sempre, e eleger é `pactl
    set-default-source` — que vira o default CONFIGURADO do WirePlumber e vence
    a prioridade 1500 do drop-in 51. Numa máquina com headset, o primeiro
    DualSense de cada sessão do daemon tomava o microfone da pessoa, o contrário
    do que o passo 10/11 do `install.sh` promete. Na mesa dela o único
    microfone com porta usável é o do controle, e por isso nunca se viu.

    **DUAS PERGUNTAS, E AS DUAS TÊM DONO.** *"O controle como padrão foi
    pedido?"* é `system_check._dualsense_mic_intended` — os cinco degraus do
    `_prefere_mic_do_dualsense` do `doctor.sh`, inclusive a marca que o
    `install.sh --keep-dualsense-mic` grava. *"Existe outra captura?"* é
    `eleicao_de_microfone.outra_captura_elegivel`, o critério de porta usável do
    `doctor.sh` pelo mesmo script, e a mesma pergunta que a volta do microfone
    faz desde 29/09/2026 (`EleitorDeMicrofone.devolver_o_microfone`). Ler a
    marca ou o `pactl` à mão daqui seria uma segunda régua sobre cada uma.

    **E NÃO É A PERGUNTA DO INSTALL** (`--melhor-fonte-elegivel`), que foi a
    primeira escrita desta cura: aquela lista deixa o canal por controle
    (`hefesto_mic_<hex6>`) entrar de propósito (§D.2 da MIC-PADRAO-NO-CABO-01),
    e com ela o canal do primeiro controle passaria por headset. Lido no
    código, não medido: na mesa dela, com os canais do rádio de pé desde a
    partida, nenhum controle elegeria mais.

    **"NÃO DEU PARA PERGUNTAR" LEVANTA** `ConsultaIndisponivelError`, e não volta
    como `None`: `None` aqui quer dizer *"pode eleger"*, e o nascimento elegia
    na dúvida — sem o script, com um script velho, com a consulta estourando o
    tempo. Quem trata a exceção é `_o_nascimento_pode_tomar_o_padrao`, como
    *"não eleja"*.

    Bloqueia (disco e um `pactl` pelo script do WirePlumber): rode em worker.
    """
    from hefesto_dualsense4unix.core import system_check
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone

    if system_check._dualsense_mic_intended():
        return None
    return eleicao_de_microfone.outra_captura_elegivel()


def _a_escolha_gravada_e_de_outro_controle(uniq: str, conectados: list[str]) -> str | None:
    """O microfone padrão que ela GRAVOU é o de OUTRO controle que está na mesa?

    Devolve o nome gravado quando é, e `None` quando o nascimento de `uniq`
    pode seguir para as outras perguntas.

    **O DEFEITO, e ele nasceu com a partida que nasce no ar** (18/09/2026).
    Toda partida do daemon — o restart do `install.sh`, uma atualização, um
    tombo, o login — solta um nascimento por controle já na mesa, em ordem de
    `alvos_conectados`, e o primeiro, com a mesa sem dono, elegia. Com ela
    tendo escolhido o Controle 2, o `default.configured.audio.source` do
    WirePlumber dizia o canal DELE — e antes da partida nascer no ar essa
    escolha voltava sozinha quando o canal do Controle 2 subia. Com a partida
    nascendo, o Controle 1 a sobrescrevia a cada restart: a escolha dela
    morrendo antes do aparelho.

    **QUEM RESPONDE É O DONO DE CADA METADE.** O valor gravado é
    `system_check.fonte_configurada_do_wireplumber` — o mesmo leitor do aviso
    de boot. *"De que controle é este nó?"* é `escolher_fonte`, a mesma
    resolução da eleição: a identidade no nome (o canal por controle, a ponte
    do rádio, o `bluez_input` com o endereço) e, para o nó ALSA do cabo, que
    não traz identidade nenhuma no nome, o casamento pelo dispositivo USB. Um
    teste de prefixo escrito aqui pegaria o canal e deixaria o cabo de fora.

    **SÓ O CONTROLE QUE ESTÁ NA MESA SEGURA A VEZ, e é decisão.** Se a escolha
    gravada é de um controle que não veio hoje, recusar deixaria o microfone
    de quem está aqui sem ser o padrão da máquina até um toque no 🎙, e o
    nascimento existe para o microfone funcionar sem gesto. A escolha
    gravada de quem está na mesa, ao contrário, não custa nada a ninguém: o
    nascimento DELE vem na mesma fila e elege.

    Bloqueia (disco; e, só quando o nome gravado é de um DualSense sem
    identidade no nome, um `pactl list sources` e o sysfs): rode em worker.
    """
    from hefesto_dualsense4unix.core import system_check
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone
    from hefesto_dualsense4unix.integrations.fontes_de_captura import (
        MARCADORES_DUALSENSE,
        escolher_fonte,
        identidade_no_nome,
    )

    gravada = system_check.fonte_configurada_do_wireplumber()
    if not gravada:
        return None
    outros = [c for c in conectados if c and not _mesmo_controle(c, uniq)]
    if not outros:
        return None
    mesa = [*outros, uniq]
    usb = None
    baixa = gravada.lower()
    if not identidade_no_nome(gravada) and any(m in baixa for m in MARCADORES_DUALSENSE):
        usb = eleicao_de_microfone.casamento_usb_agora(mesa)
    for outro in outros:
        if escolher_fonte([gravada], outro, mesa, usb) == gravada:
            return gravada
    return None


async def _o_nascimento_pode_tomar_o_padrao(daemon: DaemonProtocol, uniq: str) -> bool:
    """`True` = este nascimento pode eleger o controle fonte padrão da máquina."""
    from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
        ConsultaIndisponivelError,
    )

    correr = getattr(daemon, "_run_blocking", None)

    async def _perguntar(pergunta: Any, *args: Any) -> Any:
        if callable(correr):
            return await correr(pergunta, *args)
        return pergunta(*args)

    try:
        gravada = await _perguntar(
            _a_escolha_gravada_e_de_outro_controle,
            uniq,
            recado_do_microfone.mesa_de_agora(daemon) or [],
        )
        if gravada:
            logger.info("mic_nasce_sem_tomar_o_padrao", uniq=uniq, escolha_gravada=gravada)
            return False
        outro = await _perguntar(_microfone_que_ja_e_da_maquina)
    except ConsultaIndisponivelError as exc:
        logger.info("mic_nasce_sem_tomar_o_padrao", uniq=uniq, consulta_indisponivel=str(exc))
        return False
    except Exception:
        logger.warning("mic_nascimento_pergunta_do_padrao_falhou", uniq=uniq, exc_info=True)
        return False
    if outro:
        logger.info("mic_nasce_sem_tomar_o_padrao", uniq=uniq, microfone_da_maquina=outro)
        return False
    return True


async def _nascer_no_ar_na_vez(daemon: DaemonProtocol, uniq: str) -> bool:
    """O corpo de `nascer_no_ar`, já com a vez na fila. Ver o docstring de lá."""
    if _ela_desligou_este_microfone(daemon, uniq):
        logger.info("mic_nasce_calado_por_recusa", uniq=uniq)
        return False
    if await _o_controle_pede_silencio(daemon, uniq):
        logger.info("mic_nasce_calado_pelo_controle", uniq=uniq)
        return False
    if _o_firmware_esta_mudo(daemon, uniq):
        logger.info("mic_nasce_calado_por_gesto", uniq=uniq)
        return False
    no_ar = _no_ar_da_sessao(daemon)
    if _eleitor(daemon).eleito is None and await _o_nascimento_pode_tomar_o_padrao(
        daemon, uniq
    ):
        metade, ativo = await _metade_do_canal(daemon, uniq, True)
        logger.info(
            "mic_nasceu_no_ar",
            uniq=uniq,
            padrao_da_maquina=True,
            feito=metade.feita,
            ativo=ativo,
            motivo=metade.motivo,
        )
        return bool(metade.feita)
    dizer_no_ar(uniq, True)
    if not no_ar.esta(uniq):
        no_ar.entrou(uniq)
    logger.info("mic_nasceu_no_ar", uniq=uniq, padrao_da_maquina=False, feito=True)
    return True


_NASCIMENTOS_EM_VOO: set[asyncio.Task[bool]] = set()


async def _nascimento_best_effort(daemon: DaemonProtocol, uniq: str) -> bool:
    """`nascer_no_ar` que nunca levanta — ele corre solto, sem ninguém esperando."""
    try:
        return await nascer_no_ar(daemon, uniq)
    except Exception:
        logger.warning("mic_nascimento_falhou", uniq=uniq, exc_info=True)
        return False


def agendar_o_nascimento_do_microfone(
    daemon: DaemonProtocol, *, uniq: str | None
) -> asyncio.Task[bool] | None:
    """Põe o nascimento NUM FIO PRÓPRIO. Devolve a tarefa, ou `None`."""
    if not uniq:
        return None
    try:
        laco = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("mic_nascimento_sem_laco", uniq=uniq)
        return None
    tarefa = laco.create_task(_nascimento_best_effort(daemon, uniq))
    _NASCIMENTOS_EM_VOO.add(tarefa)
    tarefa.add_done_callback(_NASCIMENTOS_EM_VOO.discard)
    return tarefa


def _quem_herda_o_padrao(
    daemon: DaemonProtocol, no_ar: MicrofonesNoAr, *, exceto: str | None
) -> list[str]:
    """Quem está no ar e pode herdar a fonte padrão, na ordem em que herda."""
    ordem = (
        no_ar.do_mais_novo_ao_mais_velho(exceto)
        if exceto
        else list(reversed(no_ar.todos()))
    )
    if not ordem:
        return []
    mesa = recado_do_microfone.mesa_de_agora(daemon)
    if not mesa:
        return ordem
    return [u for u in ordem if any(_mesmo_controle(u, m) for m in mesa)]


async def _passar_o_padrao_ou_devolver(
    daemon: DaemonProtocol, eleitor: Any, no_ar: MicrofonesNoAr, uniq: str
) -> ResultadoDaEleicao:
    """A PORTA DO BOTÃO: o eleito se calou, e a fonte padrão sai dele."""
    ordem = _quem_herda_o_padrao(daemon, no_ar, exceto=uniq)
    conectados = _uniqs_conectados(daemon) if ordem else []
    resultado: ResultadoDaEleicao = await daemon._run_blocking(
        eleitor.passar_o_padrao, ordem, conectados, uniq
    )
    return resultado


def _o_herdeiro_e_de_quem_esta_no_ar(
    herdeiro: str, no_ar: list[str], mesa: list[str]
) -> bool | None:
    """A fonte que o WirePlumber pôs no padrão é o canal de quem está no ar?"""
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone
    from hefesto_dualsense4unix.integrations.fontes_de_captura import (
        escolher_fonte,
        identidade_no_nome,
    )

    if not no_ar:
        return False
    todos = list(mesa) or list(no_ar)
    usb = None
    if not identidade_no_nome(herdeiro):
        usb = eleicao_de_microfone.casamento_usb_agora(todos)
        if usb is None:
            return None
    return any(escolher_fonte([herdeiro], uniq, todos, usb) == herdeiro for uniq in no_ar)


async def passar_o_padrao_do_no_morto(
    daemon: DaemonProtocol,
    eleitor: Any,
    herdeiro: str | None,
    *,
    herdeiro_e_de_controle: bool,
) -> ResultadoDaEleicao | None:
    """A PORTA DO NÓ QUE MORRE, do lado do laço. `None` = o padrão fica."""
    no_ar = _no_ar_da_sessao(daemon)
    if herdeiro_e_de_controle and herdeiro:
        mesa = recado_do_microfone.mesa_de_agora(daemon) or []
        do_ar: bool | None = await daemon._run_blocking(
            _o_herdeiro_e_de_quem_esta_no_ar, herdeiro, no_ar.todos(), list(mesa)
        )
        if do_ar is not False:
            logger.info(
                "mic_da_mesa_herdeiro_fica",
                herdeiro=herdeiro,
                no_ar=do_ar,
            )
            return None
    ordem = _quem_herda_o_padrao(daemon, no_ar, exceto=None)
    conectados = _uniqs_conectados(daemon) if ordem else []
    resultado: ResultadoDaEleicao = await daemon._run_blocking(
        eleitor.passar_o_padrao, ordem, conectados
    )
    return resultado


async def _ler_o_canal_deste(daemon: DaemonProtocol, uniq: str) -> dict[str, Any]:
    """`_ler_o_canal` numa thread — e o `canal_ativo` de quem está NO AR."""
    lido: dict[str, Any] = await daemon._run_blocking(_ler_o_canal, uniq)
    if lido.get("fonte") and _no_ar_da_sessao(daemon).esta(uniq):
        lido["canal_ativo"] = True
    return lido


async def _conferir_quem_saiu_do_ar(daemon: DaemonProtocol, uniqs: list[str]) -> list[str]:
    """Tira do ar quem saiu DE FATO — o canal sumiu, ou o controle saiu da mesa."""
    no_ar = _no_ar_da_sessao(daemon)
    if not no_ar.todos():
        return []
    try:
        from hefesto_dualsense4unix.integrations.eleicao_de_microfone import (
            canal_publicado,
        )

        mesa = recado_do_microfone.mesa_de_agora(daemon)
        sairam: list[str] = []
        for uniq in no_ar.todos():
            na_mesa = any(_mesmo_controle(uniq, m) for m in mesa) if mesa else None
            lido = next(
                (v for k, v in _CANAL_POR_UNIQ.items() if _mesmo_controle(k, uniq)), None
            )
            publicado: bool | None
            if na_mesa is False:
                publicado = False
            elif isinstance(lido, dict) and lido.get("fonte"):
                publicado = True
            else:
                resposta = await daemon._run_blocking(canal_publicado, uniq, list(uniqs))
                publicado = resposta if isinstance(resposta, bool) else None
            if not no_ar.anotar_leitura(uniq, publicado, na_mesa=na_mesa):
                continue
            no_ar.saiu(uniq)
            esquecer_a_palavra(uniq)
            acender = getattr(daemon.controller, "set_mic_led", None)
            if na_mesa is not False and callable(acender):
                await daemon._run_blocking(_acender, acender, False, uniq)
            logger.info("mic_da_mesa_saiu_do_ar_de_fato", uniq=uniq, na_mesa=na_mesa)
            sairam.append(uniq)
        return sairam
    except Exception as exc:
        logger.warning("mic_da_mesa_conferencia_do_ar_falhou", err=str(exc))
        return []


# modo porém para as máscaras. a ideia é que eu nao precise fechar o jogo (noqa-acento)

CICLO_DE_MASCARAS: tuple[str, ...] = ("dualsense", "xbox", "nintendo")

#: DualSense e Xbox repetem a cor do modo de mesmo nome, para a barra dizer uma
CORES_DA_MASCARA: dict[str, tuple[int, int, int]] = {
    "dualsense": CORES_DO_MODO[PONTE_DUALSENSE],
    "xbox": CORES_DO_MODO[PONTE_XBOX],
    "nintendo": (189, 147, 249),
}

_PULSOS_DE_RISCO: list[tuple[tuple[int, int, int], float]] = [
    (COR_AVISO_RISCO, PULSO_SEG),
    ((0, 0, 0), PULSO_SEG),
    (COR_AVISO_RISCO, PULSO_SEG),
    ((0, 0, 0), PULSO_SEG),
]


def _pulsos_de_falha() -> list[tuple[tuple[int, int, int], float]]:
    """Os pulsos do "pedi e não consegui", lidos na hora (a régua zera o pulso)."""
    return [
        (COR_AVISO_RISCO, PULSO_SEG),
        ((0, 0, 0), PULSO_SEG),
        (COR_AVISO_RISCO, PULSO_SEG),
        ((0, 0, 0), PULSO_SEG),
        (COR_AVISO_RISCO, PULSO_SEG * 3),
    ]


def mascara_atual(daemon: DaemonProtocol, uniq: str | None = None) -> str:
    """A máscara do cartão `uniq` AGORA: a que o vpad veste, ou a que ele vestiria."""
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
        mascara_efetiva,
        mascara_vestida,
    )
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import primary_identity

    vivo = mascara_vestida(daemon, uniq)
    if isinstance(vivo, str) and vivo in CICLO_DE_MASCARAS:
        return vivo
    sessao = getattr(getattr(daemon, "config", None), "gamepad_flavor", None)
    return mascara_efetiva(uniq if uniq is not None else primary_identity(daemon), sessao)


def _e_o_cartao_do_posto(daemon: DaemonProtocol, uniq: str) -> bool:
    """O cartão `uniq` é o do dono do posto de P1 (o vpad `_gamepad_device`)?"""
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mesma_identidade
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import primary_identity

    return mesma_identidade(uniq, primary_identity(daemon))


def _vpad_do_cartao_de_pe(daemon: DaemonProtocol, uniq: str) -> bool:
    """O vpad do cartão `uniq` está de pé? O do jogador 1 é o `_gamepad_device`."""
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascara_vestida

    if _e_o_cartao_do_posto(daemon, uniq):
        return getattr(daemon, "_gamepad_device", None) is not None
    return mascara_vestida(daemon, uniq) is not None


_ESPERA_DO_VPAD_DO_COOP_S = 3.0
_PASSO_DA_ESPERA_DO_VPAD_S = 0.02


async def _o_vpad_do_cartao_volta(daemon: DaemonProtocol, uniq: str) -> bool:
    """Espera, com prazo, o vpad do cartão `uniq` voltar de pé. True = voltou."""
    import time

    if _vpad_do_cartao_de_pe(daemon, uniq):
        return True
    if _e_o_cartao_do_posto(daemon, uniq):
        return False
    fim = time.monotonic() + _ESPERA_DO_VPAD_DO_COOP_S
    while time.monotonic() < fim:
        await asyncio.sleep(_PASSO_DA_ESPERA_DO_VPAD_S)
        if _vpad_do_cartao_de_pe(daemon, uniq):
            return True
    return False


def proxima_mascara(atual: str) -> str:
    """A máscara seguinte no ciclo, com volta. Desconhecida → a primeira."""
    if atual not in CICLO_DE_MASCARAS:
        return CICLO_DE_MASCARAS[0]
    indice = CICLO_DE_MASCARAS.index(atual)
    return CICLO_DE_MASCARAS[(indice + 1) % len(CICLO_DE_MASCARAS)]


def build_next_mask_callback(daemon: DaemonProtocol) -> Any:
    """Cria o callback do gesto PS + L3: PRÓXIMA MÁSCARA do cartão de quem o faz."""

    async def _ciclar_mascara() -> None:
        from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
            escolher_a_mascara,
            mascara_vestida,
        )
        from hefesto_dualsense4unix.daemon.subsystems.poll import quem_segura_os_atalhos

        store = getattr(daemon, "store", None)
        if store is not None and getattr(store, "native_mode_active", False):
            logger.info("mascara_ciclo_skip_native_mode")
            return
        identidade = quem_segura_os_atalhos(daemon)
        if not identidade:
            logger.warning("mascara_do_gesto_sem_cartao", identidade=identidade)
            await _sinalizar_lightbar(daemon, _pulsos_de_falha())
            return

        jogo_no_controle = getattr(daemon, "display_authority", "unknown") == "game"
        if mascara_vestida(daemon, identidade) is not None and jogo_no_controle:
            await _sinalizar_lightbar(daemon, _PULSOS_DE_RISCO)

        atual = mascara_atual(daemon, identidade)
        alvo = proxima_mascara(atual)
        vpad_antes = _vpad_do_cartao_de_pe(daemon, identidade)
        logger.info(
            "mascara_troca_pedida_por_gesto",
            de=atual,
            para=alvo,
            vpad=vpad_antes,
            jogo_com_autoridade=jogo_no_controle,
        )

        resposta: dict[str, Any] | None = None
        try:
            resposta = escolher_a_mascara(daemon, identidade, alvo)
        except Exception as exc:
            logger.warning("mascara_do_gesto_falhou", para=alvo, err=str(exc))

        vpad_depois = (
            await _o_vpad_do_cartao_volta(daemon, identidade)
            if vpad_antes
            else _vpad_do_cartao_de_pe(daemon, identidade)
        )
        efetiva = mascara_atual(daemon, identidade)
        if resposta is not None and efetiva == alvo and vpad_depois >= vpad_antes:
            if store is not None:
                with contextlib.suppress(Exception):
                    store.bump("hotkey.mascara.cycled")
            logger.info(
                "mascara_trocada_por_gesto",
                de=atual,
                para=alvo,
                perfil=resposta.get("perfil"),
                gravado=resposta.get("gravado"),
                motivo=resposta.get("motivo"),
                vestiu=resposta.get("vestiu"),
            )
            _disparar_piscada(daemon, CORES_DA_MASCARA[alvo], modo=f"mascara:{alvo}")
            return
        logger.warning(
            "mascara_nao_subiu", pedida=alvo, efetiva=efetiva, resposta=resposta
        )
        await _sinalizar_lightbar(daemon, _pulsos_de_falha())

    return _ciclar_mascara


class HotkeySubsystem:
    """Subsystem sentinela para hotkey no registry."""

    name = "hotkey"

    async def start(self, ctx: DaemonContext) -> None:
        """Noop: hotkey é iniciado diretamente pelo Daemon.run()."""
        logger.debug("hotkey_subsystem_start")

    async def stop(self) -> None:
        """Noop: daemon._hotkey_manager é limpado em _shutdown."""
        logger.debug("hotkey_subsystem_stop")

    def is_enabled(self, config: Any) -> bool:
        return True


_O_QUE_O_CANAL_LE: tuple[str, ...] = ("sources", "server")

_MARCA_DO_CANAL: list[int | None] = [None]


async def _esperar_o_som_mudar(prazo: float, daemon: Any = None) -> None:
    """Dorme até o retrato do som mudar nas fontes ou no padrão, ou até o prazo."""
    from hefesto_dualsense4unix.integrations.retrato_do_som import RETRATO

    conferido = getattr(daemon, "_canal_conferido_em", None)
    if isinstance(conferido, float):
        falta = conferido + CANAL_TTL_S - asyncio.get_running_loop().time()
        prazo = min(prazo, max(0.0, falta))
    vista = _MARCA_DO_CANAL[0]
    if vista is None:
        vista = RETRATO.marca(_O_QUE_O_CANAL_LE)
    _MARCA_DO_CANAL[0] = await RETRATO.esperar_async(vista, prazo, _O_QUE_O_CANAL_LE)


async def _conferir_no_prazo(daemon: Any, uniqs: list[str]) -> list[str]:
    """A conferência de quem saiu do ar, no máximo uma vez por `CANAL_TTL_S`."""
    agora = asyncio.get_running_loop().time()
    conferido = getattr(daemon, "_canal_conferido_em", None)
    if isinstance(conferido, float) and agora - conferido < CANAL_TTL_S:
        return []
    with contextlib.suppress(Exception):
        daemon._canal_conferido_em = agora
    return await _conferir_quem_saiu_do_ar(daemon, uniqs)


def _mudo_pelo_retrato(fonte: str) -> _sp.CompletedProcess[str] | None:
    """A resposta do retrato do som ao `get-source-mute`, na forma do `subprocess`.

    `None` = o retrato não responde neste processo (sem dono), e quem chama
    pergunta ao servidor. O «não sei» do retrato volta como rc≠0 — a mesma
    falha de um `pactl` que não respondeu, e o `_fonte_esta_muda` a lê como
    `None`.
    """
    from hefesto_dualsense4unix.integrations import retrato_do_som

    pergunta = ["pactl", "get-source-mute", fonte]
    resposta = retrato_do_som.responder(pergunta)
    if resposta is None:
        return None
    if isinstance(resposta, str):
        return _sp.CompletedProcess(pergunta, 0, stdout=resposta, stderr="")
    return _sp.CompletedProcess(pergunta, 1, stdout="", stderr="")


# ---------------------------------------------------------------------------
# Com pad virtual DualSense, o 0x10 do `common[9]` que o jogo pede cala ou abre

_MUDO_DO_JOGO: dict[str, tuple[float, bool]] = {}


def _instante_da_borda(em: Any) -> float | None:
    """O `em` do evento da borda, ou `None` quando ele não veio."""
    if isinstance(em, (int, float)) and not isinstance(em, bool):
        return float(em)
    return None


def _a_resposta_do_jogo(uniq: str, em_da_borda: float | None) -> bool | None:
    """O mudo que o jogo pediu DEPOIS deste aperto (a resposta a ele), ou `None`."""
    from hefesto_dualsense4unix.daemon.subsystems.luz_do_mic import chave_do_mic

    chave = chave_do_mic(uniq)
    pedido = _MUDO_DO_JOGO.get(chave) if chave else None
    if pedido is None or em_da_borda is None:
        return None
    quando, mudo = pedido
    return mudo if quando >= em_da_borda else None


async def o_jogo_pede_o_mudo(
    daemon: DaemonProtocol, uniq: str, mudo: bool, em: float
) -> MetadeDoAto | None:
    """O jogo pediu para calar (`True`) ou abrir o microfone deste controle."""
    from hefesto_dualsense4unix.daemon.subsystems.luz_do_mic import (
        chave_do_mic,
        quando_a_pessoa_mandou,
    )

    chave = chave_do_mic(uniq) or uniq
    _MUDO_DO_JOGO[chave] = (em, bool(mudo))
    ela = quando_a_pessoa_mandou(uniq)
    if ela is not None and em < ela:
        logger.info("mic_mudo_do_jogo_velho", uniq=chave, mudo=mudo)
        return None
    if mudo:
        dizer_no_ar(chave, False)
    elif palavra_no_ar(chave) is False:
        esquecer_a_palavra(chave)
    firmware = await _metade_do_firmware(
        daemon, chave, not mudo, marcar_eco=False, recado=False
    )
    logger.info("mic_mudo_do_jogo", uniq=chave, mudo=mudo, feito=firmware.feita)
    return firmware


async def mic_do_jogo_loop(daemon: DaemonProtocol) -> None:
    """Consome o `mudo` e o `solta` do `MIC_DO_JOGO`; a `luz` é do laço da luz."""
    from hefesto_dualsense4unix.core.events import EventTopic
    from hefesto_dualsense4unix.daemon.subsystems.luz_do_mic import chave_do_mic

    queue = daemon.bus.subscribe(EventTopic.MIC_DO_JOGO)
    try:
        while not daemon._is_stopping():
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            if not isinstance(payload, dict):
                continue
            chave = chave_do_mic(payload.get("uniq"))
            if chave is None:
                continue
            if payload.get("solta"):
                _MUDO_DO_JOGO.pop(chave, None)
                continue
            mudo = payload.get("mudo")
            if not isinstance(mudo, bool):
                continue
            em = _instante_da_borda(payload.get("em"))
            try:
                await o_jogo_pede_o_mudo(
                    daemon, chave, mudo, em if em is not None else _relogio()
                )
            except Exception as exc:
                logger.warning("mic_mudo_do_jogo_falhou", uniq=chave, err=str(exc))
    finally:
        daemon.bus.unsubscribe(EventTopic.MIC_DO_JOGO, queue)


def _a_mesa_vazia_esquece_o_canal(daemon: Any) -> None:
    """Com a mesa vazia, o canal esquece as leituras E o relógio da conferência.

    **O LAÇO DO SERVIÇO PARAVA QUANDO O ÚLTIMO CONTROLE SAÍA.** A espera do
    canal (:func:`_esperar_o_som_mudar`) não passa da hora da próxima
    conferência, e a hora sai de ``_canal_conferido_em``, que só a volta COM
    controle avança (:func:`_conferir_no_prazo`). Com a mesa vazia a volta
    pulava a conferência, a hora ficava no passado, a espera virava prazo
    zero, e o ``esperar_async`` de prazo zero volta sem ceder o laço: a
    corrotina girava sem um ``await`` que suspendesse, e o laço inteiro do
    serviço parava com ela. Sem IPC (a janela dela travada), sem o
    ``reconnect_loop`` (o controle que voltava não era aceito) e sem o
    SIGTERM, que o laço atende. Foi o que o diário dela mostrou em 30/09 às
    01h13 e em 01/10 às 13h28 e às 19h05, os três logo depois do
    ``controller_disconnected reason=probe_offline`` do último controle, e o
    que o daemon do produto repetiu num lar de mentira em 02/10, com o
    instrumento da sprint lendo o ``state_full`` a cada segundo: mudo um
    segundo depois do ``probe_offline`` e até o fim (75 s), os dois controles
    de volta sem ``controller_connected``, o SIGTERM sem resposta em 10 s, e a
    pilha do fio do laço em ``canal_do_microfone_loop``.

    **A CURA É O ESTADO DO BOOT**: sem controle não há conferência a fazer, e o
    relógio dela volta a ``None``, que é como o daemon nasce. A espera volta a
    ser o prazo inteiro (ou o evento do som), e o controle que chega é
    conferido na primeira volta, como depois de uma mesa vazia longa já era.
    Vale para o cabo e para o rádio, de um a quatro: a mesa vazia é uma só.
    """
    _CANAL_POR_UNIQ.clear()
    with contextlib.suppress(Exception):
        daemon._canal_conferido_em = None


# A tabela é `core/acoes_do_gesto.tabela(daemon._maquina)`, lida EM MEMÓRIA a

_NADA_DO_GESTO = "nada"


def _de_quem(quem: str | None) -> dict[str, str]:
    """O campo `de` do diário: o controle do gesto, quando se sabe qual."""
    return {"de": quem} if quem else {}


def _o_ps_do_computador(daemon: Any) -> Any:
    """A ``EscolhaDoGesto`` do PS sozinho, do ``maquina.json`` em memória."""
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag

    return ag.tabela(getattr(daemon, "_maquina", None))[ag.GESTO_DO_PS]


def _jogo_aberto_agora() -> int | None:
    """O appid do jogo do wrapper que está rodando agora, ou None. Nunca levanta."""
    try:
        from hefesto_dualsense4unix.profiles.autoswitch import jogo_do_wrapper_vivo

        return jogo_do_wrapper_vivo()
    except Exception as exc:
        logger.debug("jogo_aberto_ilegivel", err=str(exc))
        return None


def _o_laco_de_agora() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


def _o_ato_do_ps_para_o_fio(
    daemon: Any, quem_atende: list[Any], do_computador: Any
) -> dict[str, Any]:
    """O que o fio do PS precisa para fazer o ⑥ fora do laço."""
    from hefesto_dualsense4unix.integrations.hotkey_daemon import quem_faz_o_gesto

    if quem_atende[0] is None:
        quem_atende[0] = _AtosDoGesto(daemon)
    return {
        "atos": quem_atende[0],
        "escolha": do_computador,
        "quem": quem_faz_o_gesto(),
        "laco": _o_laco_de_agora(),
        "contexto": contextvars.copy_context(),
    }


class _AtosDoGesto:
    """Quem atende cada ato da tabela. Montado UMA vez, no ``start_hotkey_manager``."""

    def __init__(self, daemon: Any) -> None:
        self.daemon = daemon
        self._corrotinas: dict[str, Any] = {
            "perfil_seguinte": build_profile_cycle_callback(daemon, +1),
            "perfil_anterior": build_profile_cycle_callback(daemon, -1),
            "modo_seguinte": build_next_bridge_callback(daemon),
            "mascara_seguinte": build_next_mask_callback(daemon),
        }
        self._fios: dict[str, fora_do_servico.FioDeTrabalho] = {}

    def escolha(self, gesto: str) -> Any:
        from hefesto_dualsense4unix.core import acoes_do_gesto as ag

        return ag.tabela(getattr(self.daemon, "_maquina", None))[gesto]

    def resumo(self) -> dict[str, str]:
        """Gesto -> ato, para o diário do início."""
        from hefesto_dualsense4unix.core import acoes_do_gesto as ag

        return {g: e.faz for g, e in ag.tabela(getattr(self.daemon, "_maquina", None)).items()}

    def _fio(self, gesto: str) -> fora_do_servico.FioDeTrabalho:
        fio = self._fios.get(gesto)
        if fio is None:
            fio = self._fios[gesto] = fora_do_servico.FioDeTrabalho(
                f"hefesto-gesto-{gesto}",
                ao_falhar=lambda erro: logger.warning(
                    "gesto_falhou", gesto=gesto, err=str(erro)),
            )
        return fio

    def callback(self, gesto: str) -> Any:
        """O que o ``HotkeyManager`` chama para ``gesto``: lê a tabela e faz."""
        from hefesto_dualsense4unix.integrations.hotkey_daemon import quem_faz_o_gesto

        def _ato() -> Any:
            escolha = self.escolha(gesto)
            quem = quem_faz_o_gesto()
            logger.info("gesto_fez", gesto=gesto, acao=escolha.faz, **_de_quem(quem))
            return self.fazer(gesto, escolha, quem)

        _ato.__name__ = f"ato_do_gesto_{gesto}"
        return _ato

    def fazer(self, gesto: str, escolha: Any, quem: str | None) -> Any:
        """Faz o ato no laço; o que espera processo de fora vai ao fio do gesto."""
        faz = escolha.faz
        if faz == _NADA_DO_GESTO:
            return None
        if faz == "suspender_mouse_e_teclado":
            self.daemon.set_emulation_suppressed()
            return None
        if faz == "sair_do_modo_jogo":
            self.daemon.set_emulation_suppressed(False)
            return None
        corrotina = self._corrotinas.get(faz)
        if corrotina is not None:
            return corrotina()
        if not self._fio(gesto).disparar(lambda: self.fazer_no_fio(gesto, escolha, quem)):
            logger.info("gesto_em_voo", gesto=gesto, acao=faz)
        return None

    def fazer_no_fio(self, gesto: str, escolha: Any, quem: str | None) -> None:
        """Os atos que esperam processo de fora: a Steam, a bandeja e o script."""
        faz = escolha.faz
        if faz == "abrir_a_steam":
            from hefesto_dualsense4unix.integrations.steam_launcher import open_or_focus_steam

            open_or_focus_steam()
            return
        ato_da_bandeja = _ATO_DA_BANDEJA.get(faz)
        if ato_da_bandeja is not None:
            _abrir_o_ato_da_bandeja(ato_da_bandeja, gesto)
            return
        if faz == "script":
            _rodar_o_script_do_gesto(self.daemon, gesto, escolha.script, quem)
            return
        logger.warning("gesto_sem_atendente", gesto=gesto, acao=faz)

    def fazer_pelo_ps(
        self,
        faz: str,
        escolha: Any,
        quem: str | None,
        laco: asyncio.AbstractEventLoop | None,
        contexto: contextvars.Context | None,
    ) -> None:
        """O ⑥ que não é a Steam, já no fio do PS e depois da guarda do jogo."""
        from hefesto_dualsense4unix.core import acoes_do_gesto as ag

        if faz not in self._corrotinas and faz not in (
            "suspender_mouse_e_teclado", "sair_do_modo_jogo"
        ):
            self.fazer_no_fio(ag.GESTO_DO_PS, escolha, quem)
            return
        ctx = contexto if contexto is not None else contextvars.copy_context()

        def _no_laco() -> None:
            resultado = self.fazer(ag.GESTO_DO_PS, escolha, quem)
            if asyncio.iscoroutine(resultado):
                asyncio.get_running_loop().create_task(resultado)

        if laco is not None and not laco.is_closed():
            laco.call_soon_threadsafe(_no_laco, context=ctx)
            return
        resultado = ctx.run(self.fazer, ag.GESTO_DO_PS, escolha, quem)
        if asyncio.iscoroutine(resultado):
            ctx.run(asyncio.run, resultado)


_ATO_DA_BANDEJA: dict[str, str] = {
    "abrir_o_hefesto": "abrir",
    "reiniciar_o_servico": "reiniciar",
    "parar_o_servico": "parar",
}


def _abrir_o_ato_da_bandeja(ato: str, gesto: str) -> None:
    """Roda o ato da bandeja NOUTRO processo, fora do serviço."""
    from hefesto_dualsense4unix.app.actions.atos_da_bandeja import argv_do_ato
    from hefesto_dualsense4unix.integrations.ambiente_do_jogo import ambiente_limpo

    try:
        abertura = fora_do_servico.abrir(
            argv_do_ato(ato), env=ambiente_limpo(os.environ),
            aplicativo=f"hefesto-{ato}", popen=_sp.Popen,
        )
    except Exception as exc:
        logger.warning("gesto_da_bandeja_falhou", gesto=gesto, ato=ato, err=str(exc))
        return
    logger.info("gesto_da_bandeja_aberto", gesto=gesto, ato=ato,
                caminho=abertura.caminho, unidade=abertura.unidade)


def _quem_e_por_onde(daemon: Any, quem: str | None) -> tuple[int | None, str | None]:
    """O número do jogador e o transporte (`usb`/`bt`) de quem fez o gesto."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
    from hefesto_dualsense4unix.daemon.subsystems.base import numero_do_assento_na_mesa

    try:
        lista = getattr(getattr(daemon, "controller", None), "describe_controllers", None)
        conectados = [c for c in (lista() if callable(lista) else []) if c.get("connected")]
    except Exception as exc:
        logger.debug("gesto_sem_a_mesa", err=str(exc))
        return None, None
    chave = norm_mac(quem) if quem else None
    dele = next((c for c in conectados
                 if chave and norm_mac(str(c.get("uniq") or "")) == chave), None)
    if dele is None:
        dele = next((c for c in conectados if c.get("is_primary")), None)
    if dele is None:
        return None, None
    jogador = None
    if dele.get("uniq"):
        with contextlib.suppress(Exception):
            jogador = numero_do_assento_na_mesa(conectados, str(dele["uniq"]), daemon=daemon)
    transporte = dele.get("transport")
    return jogador, (str(transporte) if transporte in ("usb", "bt") else None)


def _o_script_falhou(nome: str, motivo: str, gesto: str) -> None:
    """O recado de quando o script não rodou ou falhou: fora da janela e no diário."""
    from hefesto_dualsense4unix.integrations.desktop_notifications import notify

    logger.warning("gesto_script_falhou", gesto=gesto, script=nome, motivo=motivo)
    with contextlib.suppress(Exception):
        notify(summary="O script do controle não rodou", body=f"{nome}: {motivo}.",
               icon="dialog-warning", timeout_ms=6000)


def _rodar_o_script_do_gesto(
    daemon: Any, gesto: str, caminho: str | None, quem: str | None
) -> None:
    """Roda o script que ela escolheu para ``gesto``, com as seis guardas."""
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag
    from hefesto_dualsense4unix.integrations.ambiente_do_jogo import ambiente_limpo

    nome = ag.nome_do_script(caminho)
    motivo = ag.conferir_o_script(caminho or "")
    if motivo is not None:
        _o_script_falhou(nome, motivo, gesto)
        return
    real = os.path.realpath(str(caminho))
    env = ambiente_limpo(os.environ)
    jogador, transporte = _quem_e_por_onde(daemon, quem)
    if jogador is not None:
        env[ag.VARIAVEL_DO_JOGADOR] = str(jogador)
    if transporte is not None:
        env[ag.VARIAVEL_DO_TRANSPORTE] = transporte
    desfecho = fora_do_servico.rodar_e_esperar(
        [real], env=env, teto_s=ag.TETO_DO_SCRIPT_S, aplicativo=nome)
    if desfecho.estourou:
        _o_script_falhou(nome, f"passou de {ag.TETO_DO_SCRIPT_S} s e foi parado", gesto)
    elif not desfecho.rodou:
        _o_script_falhou(nome, "não consegui rodar", gesto)
    elif desfecho.saiu_com not in (0, None):
        _o_script_falhou(nome, f"saiu com o código {desfecho.saiu_com}", gesto)
    else:
        logger.info("gesto_script_rodou", gesto=gesto, script=nome,
                    caminho=desfecho.caminho, jogador=jogador, transporte=transporte)


__all__ = [
    "CANAL_TTL_S",
    "CICLO_DE_MASCARAS",
    "CICLO_DE_PONTES",
    "CONFIRMACAO_DO_MUDO_S",
    "CORES_DA_MASCARA",
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
    "MicrofonesNoAr",
    "acao_do_ps_do_perfil",
    "avisar_troca_de_modo",
    "build_next_bridge_callback",
    "build_profile_cycle_callback",
    "build_ps_solo_callback",
    "canal_do_microfone",
    "definir_acao_do_ps",
    "devolver_a_luz_ao_kernel",
    "modo_vigente",
    "ponte_atual",
    "proxima_ponte",
    "start_hotkey_manager",
    "start_mic_hotkey",
    "stop_hotkey_manager",
]
