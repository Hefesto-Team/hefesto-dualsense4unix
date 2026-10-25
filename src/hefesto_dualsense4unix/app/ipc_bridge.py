"""Cliente IPC síncrono/assíncrono para a GUI GTK."""
from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError
from hefesto_dualsense4unix.daemon.protocolo_do_ipc import (
    CODE_INVALID_PARAMS,
    TETO_DO_GESTO_QUE_PEDE_O_P1_S,
)
from hefesto_dualsense4unix.integrations.central_do_radio import (
    PRAZO_DA_TRAVA_DO_GESTO_S,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

_EXECUTOR: concurrent.futures.ThreadPoolExecutor | None = None

_IPC_TRANSPORT_ERRORS: tuple[type[BaseException], ...] = (
    FileNotFoundError,
    ConnectionError,
    IpcError,
    OSError,
)

#: ATIVAR-NAO-MENTE-01 (leva 2, 05/08): quanto esperar por um `profile.switch`.
#: `daemon.state_full`, e é curto de propósito para a janela não pendurar
#: esperando um daemon morto. Só que `profile.switch` não é leitura: o handler
PROFILE_SWITCH_TIMEOUT_S: float = 3.0

#: O ato de áudio leva o que o serviço leva para achar a fonte e escrever nela.
_TETO_DO_ATO_DE_AUDIO = 6.0

#: Quanto esperar por cada método: um dono só, para a janela e para a linha de
#: comando. Leitura espera o padrão de 0,25 s, curto para a janela não pendurar
#: num serviço morto; o método que muda estado espera o que o serviço leva para
#: aplicar, porque o prazo vencido com o modo JÁ aplicado vira «falhou» na tela
#: e «nada foi ativado» no terminal. A ponte da janela reexporta esta tabela.
TETOS: dict[str, float] = {
    # O gesto que pede o P1 espera o desfecho dele (o prazo do daemon), com folga.
    "gamepad.emulation.set": TETO_DO_GESTO_QUE_PEDE_O_P1_S, "native.mode.set": 2.0,
    "mouse.emulation.set": 2.0, "keyboard.emulation.set": 2.0,
    "desktop.status.set": 2.0,
    # A Navegação Interna: o interruptor e a lista gravam uma flag; o foco é o
    # pulso de cada tique da janela, e um teto curto não segura a linha de fundo.
    "navegacao.interna.set": 2.0, "navegacao.foco": 0.5,
    "mouse.emulation.restore": 2.0, "daemon.emulation.suppress": 2.0,
    # O arranjo da área de trabalho regrava os atalhos do perfil e pode criar o
    # teclado virtual: a família do `profile.switch`.
    "desktop.arranjo.apply": 3.0, "desktop.arranjo.repor": 3.0,
    "profile.switch": PROFILE_SWITCH_TIMEOUT_S,
    # Ligar o Freestyle roda o `profile.switch` do perfil dele; desligar devolve
    # o jogo ou a escolha pelo mesmo caminho.
    "freestyle.set": PROFILE_SWITCH_TIMEOUT_S,
    # O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01 (01/10/2026): o «Aplicar» roda a
    # cadeia da ativação, e por isso o teto é o do `profile.switch`.
    "profile.reaplicar": PROFILE_SWITCH_TIMEOUT_S,
    "coop.set": 2.0, "coop.sync": 2.0, "identity.renumber": 2.0,
    "gamepad.mask.set": TETO_DO_GESTO_QUE_PEDE_O_P1_S,
    "identity.number.set": 2.0,
    # O pedido do «Procurar» espera a busca SUBIR no serviço (o BlueZ abre a janela:
    # 107 a 366 ms medidos no diário da bancada em 03/10), e o serviço espera, no pior caso,
    # o prazo da trava mais 1 s. O prazo de tela de 0,25 s dava «não respondeu» sobre
    # uma busca que subia.
    "radio.busca.set": PRAZO_DA_TRAVA_DO_GESTO_S + 2.0,
    # Medido no daemon do usuário em 01/09: `daemon.reload` leva 9,5 SEGUNDOS.
    "daemon.reload": 15.0,
    # O `machine.declare` grava em disco; o gesto é raro e já congela a janela.
    "machine.declare": 1.0,
    # O reset da barra reenvia o 0x08 a cada controle aberto, e o comutador do
    # LED de jogador repinta todos: os dois prazos que a linha de comando já usava.
    "lightbar.reset": 2.0,
    "debug.player_leds": 3.0,
    # O ato do microfone e o volume da captura: o prazo que a janela já usa, que
    # o terminal herda em vez de dizer «sem resposta» sobre um ato em andamento.
    "mic.canal.set": _TETO_DO_ATO_DE_AUDIO, "mic.volume.set": _TETO_DO_ATO_DE_AUDIO,
    # O volume e o mudo do alto-falante: o prazo que a janela já passa à mão e que o
    # terminal, sem prazo nenhum até aqui, herda da tabela.
    "speaker.set": _TETO_DO_ATO_DE_AUDIO,
}

#: O padrão de um método fora da tabela: o de uma leitura.
TETO_PADRAO_S: float = 0.25

#: A linha de comando espera ao menos isto por qualquer método. Quem digitou
#: espera a resposta, e não há janela para pendurar.
PISO_DA_LINHA_DE_COMANDO_S: float = 1.0

#: O que o terminal diz quando o prazo de um método que muda estado vence: o
#: serviço pode ter aplicado logo depois, e dizer «nada foi ativado» mentiria.
FRASE_DO_PRAZO_VENCIDO = (
    "sem resposta a tempo; confira com `hefesto-dualsense4unix status`"
)


def teto(metodo: str) -> float:
    """Quanto tempo esperar por aquele método."""
    return TETOS.get(metodo, TETO_PADRAO_S)


def teto_da_linha_de_comando(metodo: str) -> float:
    """O teto do método, nunca abaixo do piso da linha de comando."""
    return max(teto(metodo), PISO_DA_LINHA_DE_COMANDO_S)


def _prazo(metodo: str, timeout: float | None) -> float:
    """O prazo pedido, ou o teto do método quando ninguém pediu."""
    return teto(metodo) if timeout is None else timeout


#: O prazo vencido do `asyncio.wait_for`: no 3.10 ele levanta o
#: `asyncio.TimeoutError`, que só vira o `TimeoutError` embutido a partir do 3.11.
PRAZO_VENCIDO = (TimeoutError, asyncio.TimeoutError)


def prazo_vencido(exc: BaseException) -> bool:
    """``True`` quando o erro é o prazo vencido, e não a recusa do serviço."""
    return isinstance(exc, IpcError) and isinstance(exc.__cause__, PRAZO_VENCIDO)


def _get_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Retorna (criando se necessário) o executor IPC compartilhado."""
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="hefesto-ipc",
        )
    return _EXECUTOR


def _run_call(
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> Any:
    """Executa RPC de forma síncrona; sem ``timeout``, espera o ``teto(method)``."""
    prazo = _prazo(method, timeout)

    async def _do() -> Any:
        async with IpcClient.connect(timeout=prazo) as client:
            return await client.call(method, params or {}, timeout=prazo)

    return asyncio.run(_do())


def _safe_call(
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> tuple[bool, Any]:
    """Executa RPC capturando apenas erros de transporte/disponibilidade.

    Retorna ``(True, resultado)`` quando o daemon confirma a chamada;
    ``(False, None)`` quando a falha é esperada (daemon offline, socket ausente,
    timeout de conexão, erro JSON-RPC do servidor). Exceções inesperadas
    (``ValueError``, ``TypeError``, ``RuntimeError``, bugs internos) **propagam**
    — o chamador precisa saber que há um defeito para reportar.

    Loga em nível ``debug`` porque daemon offline é cenário esperado em
    muitos pontos da GUI; ``warning`` causaria poluição de log.

    AUDIT-FINDING-IPC-BRIDGE-BARE-EXCEPT-01.
    """
    try:
        result = _run_call(method, params, timeout=_prazo(method, timeout))
    except _IPC_TRANSPORT_ERRORS as exc:
        logger.debug(
            "ipc_bridge falha esperada de transporte",
            method=method,
            erro_tipo=type(exc).__name__,
            erro=str(exc),
        )
        return False, None
    return True, result


def call_async(
    method: str,
    params: dict[str, Any] | None,
    on_success: Callable[[Any], bool],
    on_failure: Callable[[Exception], bool] | None = None,
    timeout_s: float | None = None,
) -> None:
    """Despacha RPC para thread worker; callbacks re-postados via GLib.idle_add."""
    from gi.repository import GLib

    def _worker() -> None:
        try:
            result = _run_call(method, params, timeout=_prazo(method, timeout_s))
        except Exception as exc:
            if on_failure is not None:
                GLib.idle_add(on_failure, exc)
            else:
                logger.warning(
                    "ipc_bridge.call_async falhou sem handler de erro",
                    method=method,
                    erro=str(exc),
                )
            return
        GLib.idle_add(on_success, result)

    _get_executor().submit(_worker)


def run_in_thread(
    fn: Callable[[], Any],
    on_success: Callable[[Any], bool],
    on_failure: Callable[[Exception], bool] | None = None,
) -> None:
    """Roda ``fn()`` em thread worker; callbacks re-postados via GLib.idle_add."""
    from gi.repository import GLib

    def _worker() -> None:
        try:
            result = fn()
        except Exception as exc:
            if on_failure is not None:
                GLib.idle_add(on_failure, exc)
            else:
                logger.warning(
                    "ipc_bridge.run_in_thread falhou sem handler de erro",
                    erro=str(exc),
                )
            return
        GLib.idle_add(on_success, result)

    _get_executor().submit(_worker)


def daemon_state_full() -> dict[str, Any] | None:
    """Retorna estado completo via IPC; None se daemon offline."""
    ok, result = _safe_call("daemon.state_full")
    if ok and isinstance(result, dict):
        return result
    return None


def freestyle_set(ligado: bool | None = None) -> bool | None:
    """Liga/desliga o Modo Freestyle (O-FREESTYLE-E-UMA-CAMADA-SO-01)."""
    params: dict[str, Any] = {}
    if ligado is not None:
        params["ligado"] = bool(ligado)
    ok, result = _safe_call("freestyle.set", params)
    if ok and isinstance(result, dict):
        estado = result.get("freestyle_ligado")
        return bool(estado) if isinstance(estado, bool) else None
    return None


def daemon_status_basic() -> dict[str, Any] | None:
    """Retorna status básico via IPC; None se daemon offline."""
    ok, result = _safe_call("daemon.status")
    if ok and isinstance(result, dict):
        return result
    return None


def profile_list() -> list[dict[str, Any]]:
    """Os perfis a escolher, sem o Freestyle (02/10). Daemon primeiro; reserva: disco."""
    ok, result = _safe_call("profile.list")
    if ok and isinstance(result, dict):
        profiles = list(result.get("profiles", []))
        if profiles:
            return profiles

    try:
        from hefesto_dualsense4unix.profiles.loader import load_all_profiles
        from hefesto_dualsense4unix.profiles.manager import os_perfis_de_escolher
        return [
            {
                "name": p.name,
                "priority": p.priority,
                "match_type": p.match.type,
                "active": False,
            }
            for p in os_perfis_de_escolher(load_all_profiles())
        ]
    except (FileNotFoundError, PermissionError, OSError) as exc:
        logger.warning(
            "profile_load_fallback_failed",
            err=str(exc),
            err_type=type(exc).__name__,
            exc_info=True,
        )
        return []


def profile_switch(name: str) -> bool:
    """Ativa um perfil no daemon; ``False`` quando ele não confirmou."""
    ok, _ = _safe_call("profile.switch", {"name": name})
    return ok


def _corpo_do_daemon(
    method: str,
    params: dict[str, Any] | None = None,
    *,
    timeout: float | None = None,
) -> dict[str, Any] | None:
    """RPC que entrega o CORPO da resposta, ou ``None`` quando não houve corpo."""
    if timeout is None:
        ok, result = _safe_call(method, params)
    else:
        ok, result = _safe_call(method, params, timeout=timeout)
    if ok and isinstance(result, dict):
        return result
    return None


def _call_checked_detalhado(
    method: str,
    params: dict[str, Any],
    timeout: float | None = None,
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """``_call_checked`` que NÃO joga fora o corpo da resposta (ELO-MUDO-01).

    Retorna ``(ok, motivo, corpo)``, onde ``ok`` e ``motivo`` são exatamente os
    de :func:`_call_checked` — que passou a ser um invólucro desta — e ``corpo``
    é o dicionário que o daemon devolveu, ou ``None`` quando ele não respondeu
    (ou respondeu algo que não é dicionário).

    Por que a função nova em vez de trocar a assinatura de ``_call_checked``:
    a forma de hoje tem chamadores vivos em arquivos que outras frentes estão editando, e uma
    3-tupla desempacotada num ``ok, motivo = …`` levanta ``ValueError`` em
    tempo de execução, não em tempo de revisão. Aditivo: ninguém quebra, e quem
    precisa da verdade inteira pede por ela.

    O que se perdia aqui era LITERAL: a linha do RPC era
    ``_run_call(method, params, timeout=timeout)`` **sem atribuição** — o corpo
    não chegava nem a ganhar um nome. Três rotas pagavam por isso
    (``trigger.set``, ``trigger.reset``, ``rumble.policy_set``), e as duas
    primeiras são justamente as que carregam ``aplicado_em``/``guardado_em``.

    ``motivo`` aqui é SÓ o do erro JSON-RPC, igualzinho ao de ``_call_checked``:
    esta função é a mesma, mais o corpo. A outra forma de o daemon dizer não —
    a frase dentro de um corpo bem-sucedido, ver :func:`_recusa_no_corpo` — é
    dobrada pelos invólucros públicos ``*_detalhado``, que nascem sem chamador e
    por isso podem nascer com o contrato inteiro.

    ``IpcError`` é capturado ANTES de ``_IPC_TRANSPORT_ERRORS``, que o contém.
    """
    try:
        resultado = _run_call(method, params, timeout=_prazo(method, timeout))
    except IpcError as exc:
        if exc.code == CODE_INVALID_PARAMS:
            return False, exc.message, None
        logger.debug(
            "ipc_bridge falha esperada de transporte",
            method=method,
            erro_tipo=type(exc).__name__,
            erro=str(exc),
        )
        return False, None, None
    except _IPC_TRANSPORT_ERRORS as exc:
        logger.debug(
            "ipc_bridge falha esperada de transporte",
            method=method,
            erro_tipo=type(exc).__name__,
            erro=str(exc),
        )
        return False, None, None
    corpo = resultado if isinstance(resultado, dict) else None
    return True, None, corpo


def _call_checked(
    method: str,
    params: dict[str, Any],
    timeout: float | None = None,
) -> tuple[bool, str | None]:
    """RPC que distingue "o daemon RECUSOU" de "o daemon não respondeu"."""
    ok, motivo, _corpo = _call_checked_detalhado(method, params, timeout=timeout)
    return ok, motivo


def _payload_trigger_set(
    side: str, mode: str, params: list[int], uniq: str | None, todos: bool = False
) -> dict[str, Any]:
    """Payload do ``trigger.set`` — um dono só, para as duas portas não divergirem."""
    payload: dict[str, Any] = {"side": side, "mode": mode, "params": params}
    if uniq:
        payload["uniq"] = uniq
    if todos:
        payload["todos"] = True
    return payload


def trigger_set_detalhado(
    side: str,
    mode: str,
    params: list[int],
    uniq: str | None = None,
    *,
    todos: bool = False,
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """``trigger.set`` que entrega a RESPOSTA do daemon (ELO-MUDO-01, 23/08).

    Devolve ``(ok, motivo, corpo)``. O ``corpo`` traz ``aplicado_em`` e
    ``guardado_em`` — as duas listas que o daemon monta em
    ``_handle_trigger_set`` e que morriam nesta ponte. Use
    :func:`destinos_da_aplicacao` para lê-las sem repetir a regra.

    Por que a existência desta função é uma dívida paga, e não um recurso novo:
    medido na bancada viva em 23/08, com a mesa VAZIA, o daemon respondeu
    ``{"status": "ok", "aplicado_em": [], "guardado_em": []}`` — ZERO destino,
    nenhum byte no fio, nada guardado — e a aba Gatilhos disse *"SimpleRigid
    aplicado"*, porque a ponte entregava ``(True, None)`` e a janela
    re-DEDUZIA o destino do próprio estado dela. A heurística da janela cobre
    duas das três razões que o daemon conhece; a rota clássica de mesa vazia
    não é uma delas.

    ``motivo`` junta as DUAS formas de o daemon dizer não: o erro JSON-RPC de
    parâmetro inválido (Fim <= Início, HARM-19) e a frase no corpo de uma
    resposta bem-sucedida (:func:`_recusa_no_corpo`).

    ``uniq`` (PERFIL-05): MAC do controle selecionado no seletor — o daemon
    aplica SÓ nele (override por-MAC); omitido = comportamento global clássico.

    ``todos``: o «Em todos» da aba Gatilhos. O daemon escreve em CADA controle
    da mesa, ignorando o destino da aba Conexões, grava o padrão que um
    controle novo herda e solta o bloco do jogo, como o gesto por controle.
    """
    ok, motivo, corpo = _call_checked_detalhado(
        "trigger.set", _payload_trigger_set(side, mode, params, uniq, todos)
    )
    return ok, motivo or _recusa_no_corpo(corpo), corpo


def trigger_set_checked(
    side: str, mode: str, params: list[int], uniq: str | None = None
) -> tuple[bool, str | None]:
    """Aplica gatilho devolvendo o MOTIVO quando o daemon RECUSA (HARM-19).

    Recusa típica: Fim <= Início. Ver ``_call_checked`` para o contrato.
    ``uniq`` (PERFIL-05): MAC do controle selecionado no seletor — o daemon
    aplica SÓ nele (override por-MAC); omitido = comportamento global clássico.

    **Não diz ONDE aplicou** — para isso existe :func:`trigger_set_detalhado`,
    que entrega ``aplicado_em``/``guardado_em``.
    """
    return _call_checked("trigger.set", _payload_trigger_set(side, mode, params, uniq))


def trigger_set(side: str, mode: str, params: list[int]) -> bool:
    """Aplica gatilho; True se o daemon confirmou. Descarta o motivo da recusa."""
    ok, _motivo = trigger_set_checked(side, mode, params)
    return ok


def _payload_trigger_reset(
    side: str | None, uniq: str | None, todos: bool = False
) -> dict[str, Any]:
    """Payload do ``trigger.reset`` — um dono só, para as duas portas não divergirem."""
    payload: dict[str, Any] = {}
    if side:
        payload["side"] = side
    if uniq:
        payload["uniq"] = uniq
    if todos:
        payload["todos"] = True
    return payload


def trigger_reset_detalhado(
    side: str | None = None, uniq: str | None = None, *, todos: bool = False
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """Grava ``Off`` no gatilho (`trigger.reset`): sem efeito, e o jogo decide.

    Mesmo contrato de :func:`trigger_set_detalhado` — e o mesmo corpo
    (``status``/``aplicado_em``/``guardado_em``), porque os dois handlers foram
    escritos como espelho um do outro (ELO-MUDO-01, 23/08).

    O ``Off`` é carimbado com a camada ``usuaria`` daquele controle: o gesto
    solta o que o jogo tinha pintado no gatilho, e o jogo que mandar efeito
    depois vence.

    ABAS-06 (25/07): `uniq` — MAC do controle escolhido no seletor. Este era o
    ÚNICO comando de saída da janela sem alvo: com "Controle 2" selecionado,
    "Desligar" zerava o gatilho dos QUATRO, enquanto o "Aplicar" ao lado
    mandava para um só. Omitido = comportamento global clássico.

    ``todos``: o mesmo «Em todos» de :func:`trigger_set_detalhado`.
    """
    ok, motivo, corpo = _call_checked_detalhado(
        "trigger.reset", _payload_trigger_reset(side, uniq, todos)
    )
    return ok, motivo or _recusa_no_corpo(corpo), corpo


def led_set(
    rgb: tuple[int, int, int],
    brightness: float | None = None,
    uniq: str | None = None,
) -> bool:
    """Aplica cor RGB (opcionalmente escalada) no lightbar via IPC.

    ``brightness`` (0.0-1.0) é repassado ao daemon quando fornecido; omitido
    preserva o contrato v1 (sem multiplicador). Ver FEAT-LED-BRIGHTNESS-01.
    ``uniq`` (PERFIL-05): MAC do controle selecionado — aplica SÓ nele.

    **Não diz ONDE acendeu** — para isso existe :func:`led_set_detalhado`.
    """
    ok, _ = _safe_call("led.set", _payload_led_set(rgb, brightness, uniq))
    return ok


def _payload_led_set(
    rgb: tuple[int, int, int], brightness: float | None, uniq: str | None
) -> dict[str, Any]:
    """Payload do ``led.set`` — um dono só, para as duas portas não divergirem."""
    payload: dict[str, Any] = {"rgb": list(rgb)}
    if brightness is not None:
        payload["brightness"] = float(brightness)
    if uniq:
        payload["uniq"] = uniq
    return payload


def led_set_detalhado(
    rgb: tuple[int, int, int],
    brightness: float | None = None,
    uniq: str | None = None,
) -> dict[str, Any] | None:
    """``led.set`` que entrega a RESPOSTA do daemon (ELO-MUDO-01, 23/08).

    Mesmo payload e mesma rota do :func:`led_set`; o que muda é o que volta.
    O corpo traz ``aplicado_em`` e ``guardado_em`` — leia com
    :func:`destinos_da_aplicacao`. ``None`` = daemon não respondeu (ver
    :func:`_corpo_do_daemon`).

    O ``led.set`` e o ``led.player_set`` são o MESMO defeito do ``trigger.set``
    noutro arquivo de aba: o daemon já publica os dois destinos desde a
    APLICAR-VERDADE-01, e a aba Lightbar re-deduzia o "guardado" do estado da
    janela porque o ``bool`` desta ponte não tinha como carregá-los.
    """
    return _corpo_do_daemon("led.set", _payload_led_set(rgb, brightness, uniq))


def _recusa_no_corpo(resultado: Any) -> str | None:
    """Lê a recusa que vem no CORPO de uma resposta bem-sucedida."""
    if not isinstance(resultado, dict):
        return None
    motivo = resultado.get("motivo")
    return motivo if isinstance(motivo, str) and motivo else None


def _com_o_controle(params: dict[str, Any], uniq: str | None) -> dict[str, Any]:
    """O pedido de vibração leva ``uniq`` só quando o gesto é de UM controle."""
    if uniq:
        params["uniq"] = uniq
    return params


def rumble_set_checked(
    weak: int, strong: int, uniq: str | None = None
) -> tuple[bool, str | None]:
    """Fixa a vibração devolvendo o MOTIVO quando o daemon RECUSA.

    Com ``uniq`` o par é DAQUELE controle e os dos outros seguem como estavam;
    sem ele é o par da mesa, no alvo escolhido.
    """
    ok, resultado = _safe_call(
        "rumble.set", _com_o_controle({"weak": weak, "strong": strong}, uniq)
    )
    if not ok:
        return False, None
    recusou = isinstance(resultado, dict) and resultado.get("status") == "recusado"
    return (not recusou), _recusa_no_corpo(resultado)


def rumble_set(weak: int, strong: int) -> bool:
    """Aplica rumble persistente via IPC (BUG-RUMBLE-APPLY-IGNORED-01).

    O daemon persiste (weak, strong) em daemon.config.rumble_active e
    re-afirma a cada 200ms — vibração contínua até rumble_stop() ou
    rumble_passthrough().

    Descarta o motivo da recusa — use ``rumble_set_checked`` para tê-lo.
    """
    ok, _motivo = rumble_set_checked(weak, strong)
    return ok


def rumble_stop_checked(uniq: str | None = None) -> tuple[bool, str | None]:
    """Para a vibração devolvendo a FRASE do daemon quando ele tem uma.

    Com ``uniq`` só aquele controle para.
    """
    ok, resultado = _safe_call("rumble.stop", _com_o_controle({}, uniq))
    if not ok:
        return False, None
    return True, _recusa_no_corpo(resultado)


def rumble_stop(uniq: str | None = None) -> bool:
    """Para rumble e FIXA (0, 0) — **isto não devolve a vibração ao jogo**.

    Descarta a frase do daemon — use ``rumble_stop_checked`` para tê-la.

    **"PARAR" NÃO É "DESFAZER", e a diferença tem consequência medida**
    (04/09/2026, no aparelho, pelo ensaio
    `scripts/ensaios/o_multiplicador_chega_ao_motor.py`). O par ``(0, 0)`` é um
    par FIXADO, e não `None`: enquanto ele estiver de pé,
    `daemon.subsystems.gamepad.apply_game_rumble` **descarta o FF de todo
    jogo** na primeira linha (`rumble_active is not None` → `return None`). Um
    instrumento que chamou `rumble_stop` achando que estava "limpando a
    bagunça" deixou a máquina do usuário **sem vibração em jogo nenhum, em
    silêncio** — e não havia uma palavra aqui que avisasse.

    **A FIXAÇÃO É DELIBERADA, e não é defeito** (`_handle_rumble_stop`,
    HARM-16): o poll loop re-afirma o silêncio para que outra escrita HID não
    reative os motores por acidente. O que faltava era esta frase.

    **Quem quer devolver a vibração ao jogo chama `rumble_passthrough(True)`.**
    """
    ok, _motivo = rumble_stop_checked(uniq)
    return ok


def rumble_passthrough(enabled: bool = True, uniq: str | None = None) -> bool:
    """Devolve a vibração ao JOGO (BUG-RUMBLE-APPLY-IGNORED-01).

    É o par simétrico de `rumble_stop`, e é ELE — não o "parar" — que solta o
    par fixado (`rumble_active = None`). Ver a advertência em `rumble_stop`.
    """
    ok, _ = _safe_call(
        "rumble.passthrough", _com_o_controle({"enabled": bool(enabled)}, uniq)
    )
    return ok


def rumble_motores_set(
    *,
    forte_pct: int | None = None,
    fraco_pct: int | None = None,
    uniq: str | None = None,
    haptica_pct: int | None = None,
    efeito_haptico: str | None = None,
    efeito_imersao: str | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    """As barras de cada motor, a háptica e as duas listas de efeito, no perfil, POR PEÇA.

    ``None`` em um campo = não mexe nele (todos em `None` é erro). ``uniq`` omitido = o primário.
    ``efeito_haptico`` e ``efeito_imersao`` levam a chave da escolha; ``"do_estilo"`` volta ao
    automático e o daemon recusa chave que não existe. Devolve ``(ok, corpo)``: o corpo é o do
    daemon (`status`, `motivo` quando recusa, `perfil`, `gravado` e os valores que passaram a
    valer); `None` quer dizer daemon fora do ar. A faixa 0-100 (0-200 na háptica) é da borda do
    esquema, e o porquê está em docs/research/o-porque-dos-modulos.md.
    """
    params: dict[str, Any] = {}
    if forte_pct is not None:
        params["forte_pct"] = int(forte_pct)
    if fraco_pct is not None:
        params["fraco_pct"] = int(fraco_pct)
    if haptica_pct is not None:
        params["haptica_pct"] = int(haptica_pct)
    if efeito_haptico is not None:
        params["efeito_haptico"] = str(efeito_haptico)
    if efeito_imersao is not None:
        params["efeito_imersao"] = str(efeito_imersao)
    if uniq:
        params["uniq"] = uniq
    corpo = _corpo_do_daemon("rumble.motores.set", params)
    return corpo is not None, corpo


def rumble_policy_set_checked(
    policy: str, *, timeout: float | None = None
) -> tuple[bool, str | None]:
    """Altera a intensidade devolvendo o MOTIVO quando o daemon RECUSA."""
    return _call_checked("rumble.policy_set", {"policy": policy}, timeout=timeout)


def rumble_policy_custom(mult: float) -> bool:
    """Define política "custom" com multiplicador explícito (FEAT-RUMBLE-POLICY-01).

    ``mult`` deve ser float em ``[0.0, RUMBLE_CUSTOM_MULT_MAX]`` — a faixa mora
    em ``profiles.schema`` e o handler do daemon recusa fora dela (HARM-19).
    Este texto dizia ``[0.0, 1.0]`` à mão e ficou mentindo de 11/08/2026, quando
    o teto voltou a 2.0 por decisão de produto: acima de 1.0 o multiplicador
    AMPLIFICA o que o jogo pediu.

    Retorna True se o daemon confirmou; False se offline ou parâmetro inválido.
    """
    ok, _ = _safe_call("rumble.policy_custom", {"mult": float(mult)})
    return ok


_MOTIVOS_NUMERO: dict[str, str] = {
    "sessao_de_jogo_aberta": (
        "Feche o jogo antes de trocar o número — trocar agora repintaria "
        "o controle no meio da partida"
    ),
    "controle_ausente": (
        "Este controle não está ligado agora — só quem está ligado tem número"
    ),
    "numero_fora_da_mesa": (
        "Esse número é maior do que a quantidade de controles ligados"
    ),
    "lock_timeout": "O Hefesto está ocupado — tente de novo em um instante",
}


def identity_number_set(uniq: str, number: int) -> tuple[bool, str | None]:
    """Atribui o NÚMERO EXIBIDO do controle ``uniq`` (PLAYER-01, 25/07)."""
    ok, result = _safe_call(
        "identity.number.set", {"uniq": uniq, "number": int(number)}
    )
    if not ok or not isinstance(result, dict):
        return False, None
    if result.get("ok"):
        return True, None
    reason = result.get("reason")
    motivo = _MOTIVOS_NUMERO.get(reason) if isinstance(reason, str) else None
    return False, motivo or "Não consegui trocar o número — tente de novo"


_MOTIVOS_MAQUINA: dict[str, str] = {
    "versao_desconhecida": (
        "O arquivo com o que você declarou sobre as entradas foi escrito por uma "
        "versão mais nova do Hefesto — não vou sobrescrever o que está lá"
    ),
    "falha_ao_gravar": (
        "Não consegui gravar o que você declarou — confira o espaço em disco"
    ),
    "declaracao_invalida": (
        "O Hefesto não entendeu o que você declarou. Isto é defeito nosso, e "
        "nada foi gravado"
    ),
}


_SECAO_DO_CAMPO: dict[str, str] = {
    "mesa": "secao_mesa",
    "controles": "secao_controles",
    "orcamento": "secao_orcamento",
}

_ROTULOS_SEM_SECAO: dict[str, str] = {
    "mapa": "O desenho das entradas",
    "lancadores": "Onde estão os seus lançadores",
    "adaptadores": "O nome de cada adaptador Bluetooth",
    "aparelhos": "O tipo de cada aparelho Bluetooth",
    "gestos": "O que cada gesto do controle faz",
    "computador": "O padrão do computador",
}


def _rotulos_dos_campos() -> dict[str, str]:
    """``{campo do schema: rótulo de tela}``, LIDO das seções, nunca copiado."""
    from hefesto_dualsense4unix.app.actions.config import secoes

    por_modulo = {
        secao.__name__.rsplit(".", 1)[-1]: secao.TITULO
        for secao in secoes.SECOES_DA_ABA
    }
    rotulos = {
        campo: por_modulo[modulo]
        for campo, modulo in _SECAO_DO_CAMPO.items()
        if modulo in por_modulo
    }
    rotulos.update(_ROTULOS_SEM_SECAO)
    return rotulos


def _rotulos_dos_descartados(result: dict[str, Any]) -> tuple[str, ...]:
    """Os campos descartados do corpo do daemon, já em rótulo de tela."""
    descartados = result.get("descartados")
    if not isinstance(descartados, list):
        return ()
    rotulos = _rotulos_dos_campos()
    return tuple(
        rotulos.get(campo, campo)
        for campo in descartados
        if isinstance(campo, str) and campo
    )


def machine_declare(maquina: dict[str, Any]) -> tuple[bool, str | None]:
    """Grava a declaração de MESA (CONFIG-03, 22/08). Devolve ``(ok, motivo)``.

    **Não diz o que foi DESCARTADO** — para isso existe
    :func:`machine_declare_detalhado`, e este invólucro estreita o resultado
    dela para a dupla de sempre.
    """
    ok, motivo, _descartados = machine_declare_detalhado(maquina)
    return ok, motivo


def machine_declare_detalhado(
    maquina: dict[str, Any],
) -> tuple[bool, str | None, tuple[str, ...]]:
    """``machine.declare`` inteiro: ``(ok, motivo, descartados)``.

    ``maquina`` é uma declaração **parcial** no formato do ``MaquinaConfig``
    (``utils/maquina.py``) — só o que mudou. O daemon funde contra o disco sob
    lock, então duas seções da mesma janela não apagam uma a outra.

    ``motivo`` só vem preenchido quando o daemon RESPONDEU e RECUSOU, já
    traduzido para a frase da janela (:data:`_MOTIVOS_MAQUINA`). Daemon offline
    volta ``(False, None, ())``: a tela diz coisas diferentes em "o Hefesto está
    desligado" e "não vou sobrescrever o que está lá".

    ``descartados`` (CONFIG-06, 23/08/2026) é o que a gravação teve de deixar
    para trás — campo de topo que já estava em disco com valor que o schema
    recusa. Vem em RÓTULO de tela (:func:`_rotulos_dos_campos`), e é **vazio no
    caso comum**: a chave nem aparece no corpo quando não há nada a dizer.

    Duas funções em vez de trocar o tipo de retorno da :func:`machine_declare`:
    a ``machine_declare`` está no ``__all__`` e a dupla ``(ok, motivo)`` é o
    contrato de quem já a chama. Aditivo — ninguém quebra, e quem precisa da
    verdade inteira pede por ela.

    ``_safe_call`` e não ``_call_checked`` pela razão de sempre nesta fronteira:
    a recusa vem no CORPO, não como ``CODE_INVALID_PARAMS`` — ver
    ``_handle_machine_declare``. E 1,0 s de teto em vez dos 250 ms de leitura
    porque este pedido escreve em disco; o gesto é raro e já congela a janela.
    """
    ok, result = _safe_call("machine.declare", {"maquina": maquina})
    if not ok or not isinstance(result, dict):
        return False, None, ()
    if result.get("ok"):
        return True, None, _rotulos_dos_descartados(result)
    reason = result.get("reason")
    motivo = _MOTIVOS_MAQUINA.get(reason) if isinstance(reason, str) else None
    return False, motivo or "Não consegui gravar o que você declarou", ()


def player_leds_set(
    bits: tuple[bool, bool, bool, bool, bool], uniq: str | None = None
) -> bool:
    """Aplica bitmask de 5 LEDs de player no hardware via IPC (FEAT-PLAYER-LEDS-APPLY-01)."""
    ok, _ = _safe_call("led.player_set", _payload_player_leds(bits, uniq))
    return ok


def _payload_player_leds(
    bits: tuple[bool, bool, bool, bool, bool], uniq: str | None
) -> dict[str, Any]:
    """Payload do ``led.player_set`` — um dono só, para as portas não divergirem."""
    payload: dict[str, Any] = {"bits": list(bits)}
    if uniq:
        payload["uniq"] = uniq
    return payload


def player_leds_set_detalhado(
    bits: tuple[bool, bool, bool, bool, bool], uniq: str | None = None
) -> dict[str, Any] | None:
    """``led.player_set`` que entrega a RESPOSTA do daemon (ELO-MUDO-01, 23/08).

    Irmão de :func:`led_set_detalhado`, com o mesmo corpo mais o campo ``bits``
    que o daemon ecoa. ``None`` = daemon não respondeu.
    """
    return _corpo_do_daemon("led.player_set", _payload_player_leds(bits, uniq))


def player_led_brightness_set_detalhado(
    brilho: str, uniq: str | None = None
) -> dict[str, Any] | None:
    """``led.player_brightness_set`` com a RESPOSTA do daemon (24/09/2026)."""
    payload: dict[str, Any] = {"brilho": brilho}
    if uniq:
        payload["uniq"] = uniq
    return _corpo_do_daemon("led.player_brightness_set", payload)


def destinos_da_aplicacao(resposta: Any) -> tuple[list[str], list[str]]:
    """``(aplicado_em, guardado_em)`` de uma resposta do daemon (ELO-MUDO-01).

    Dono ÚNICO da leitura desses dois campos do lado da janela, pelo mesmo
    motivo de todo dono único desta ponte: quatro rotas os publicam
    (``trigger.set``, ``trigger.reset``, ``led.set``, ``led.player_set``) e cada
    aba que os lesse por conta própria seria mais uma chance de nascerem duas
    leituras do mesmo payload.

    O vocabulário é do daemon (``_destinos_por_uniq``, MESA-CHEIA-09):

    * ``aplicado_em`` — os MACs em que o byte SAIU no fio;
    * ``guardado_em`` — os MACs em que a intenção ficou GUARDADA sem sair
      (alvo desconectado, alvo sem MAC estável, Modo Nativo com output mutado).

    **As duas vazias significam que nada aconteceu**, e é o caso que a bancada
    mediu em 23/08 com a mesa vazia — aquele em que a tela dizia "aplicado".
    Resposta ausente ou sem os campos volta como duas listas vazias: quem não
    respondeu não aplicou.
    """
    if not isinstance(resposta, dict):
        return [], []
    aplicado = resposta.get("aplicado_em")
    guardado = resposta.get("guardado_em")
    return (
        [m for m in aplicado if isinstance(m, str)] if isinstance(aplicado, list) else [],
        [m for m in guardado if isinstance(m, str)] if isinstance(guardado, list) else [],
    )


def alvo_honrado(resposta: Any) -> bool | None:
    """O daemon mexeu no controle ESCOLHIDO, ou caiu na rota global? (``por_uniq``).

    MIC-DA-MESA-CHEIA-01: com dois DualSense no cabo há DUAS placas de som, e a
    rota global devolve a PRIMEIRA — o microfone de outra pessoa. O daemon já
    responde ``por_uniq`` justamente para a tela poder saber a diferença, e ele
    morria nesta ponte.

    Devolve ``True``/``False`` quando o daemon se pronunciou, e ``None`` quando
    ele não disse nada a respeito (rota sem o campo, ou sem resposta). ``None``
    não é ``False``: "não sei" e "não honrei" mandam a janela dizer coisas
    diferentes.
    """
    if not isinstance(resposta, dict):
        return None
    valor = resposta.get("por_uniq")
    return valor if isinstance(valor, bool) else None


def mic_set(muted: bool | None, uniq: str | None = None) -> bool:
    """Muta/desmuta o microfone no FIRMWARE do controle (MIC-USB-01).

    ``muted=True`` muta, ``muted=False`` DESMUTA e ``muted=None`` devolve a
    posse do registrador ao `hid-playstation` (o botão físico do controle volta
    a mandar). Os três são pedidos EXPLÍCITOS e diferentes: ``False`` não é "não
    mexer" — é a ordem "desmuta", e enquanto ela vigorar o botão físico deixa de
    valer. Confundir os dois foi o defeito dos dois escritores do byte de mute
    (`3d9bb7e`), então o parâmetro não tem default: quem chama declara.

    Esta é a CAMADA 3 do achado de 25/07. As outras duas (o ``mute:true``
    persistido por rota em ``~/.local/state/wireplumber/default-routes`` e o
    perfil da placa preso em ``input:iec958-stereo``, que capta: o «sem sinal» de
    25/07 era o mudo do firmware) são do WirePlumber, não do controle, e se curam pelo
    ``scripts/doctor.sh --fix``. Nenhum ``mic_set`` do mundo as alcança — se o
    medidor continuar parado depois de desmutar aqui, é uma delas.

    PONTO EXATO DE FIAÇÃO (deixado pronto, não fiado — a GUI está sendo mexida
    por outra frente): o botão de microfone da aba Status, ao lado do medidor
    montado por ``app/mic_monitor.py``, chamando daqui via
    ``app/actions/status_actions.py``. Depois do pedido, RELER
    ``daemon.state_full`` e pintar o selo a partir de ``audio.mic_mudo``
    (leitura do firmware) + ``audio.mic_mudo_desejado`` (quem manda) — jamais
    guardar o valor mandado como se fosse leitura, que é justamente o hábito que
    fez a tela parecer mentirosa quando ela nunca mentiu.

    Retorna True se o daemon confirmou; False se offline ou sem controle.
    **Os dois casos voltam False** — quem precisa separá-los chama
    :func:`mic_set_detalhado`.
    """
    corpo = mic_set_detalhado(muted, uniq)
    return corpo is not None and corpo.get("status") == "ok"


def mic_set_detalhado(
    muted: bool | None, uniq: str | None = None
) -> dict[str, Any] | None:
    """``mic.set`` que entrega a RESPOSTA do daemon (ELO-MUDO-01, 23/08)."""
    if muted is None:
        payload: dict[str, Any] = {"muted": None}
        if uniq:
            payload["uniq"] = uniq
        return _corpo_do_daemon("mic.set", payload)
    corpo = mic_canal_set_detalhado(not muted, uniq)
    if corpo is None:
        return None
    corpo = dict(corpo)
    corpo["mic_mudo_desejado"] = muted
    corpo["status"] = "ok" if corpo.get("firmware_pedido") else corpo.get("status")
    return corpo


def mic_canal_set(ligado: bool, uniq: str | None = None) -> bool:
    """O ATO do microfone: o canal DESTE controle, e o mudo do firmware."""
    corpo = mic_canal_set_detalhado(ligado, uniq)
    return corpo is not None and corpo.get("status") == "ok"


def mic_canal_set_detalhado(
    ligado: bool, uniq: str | None = None
) -> dict[str, Any] | None:
    """``mic.canal.set`` com a RESPOSTA inteira do daemon.

    O corpo traz ``status`` (``"ok"`` só com as duas metades feitas,
    ``"incompleto"`` quando faltou uma, ``"sem_controle"`` com a mesa vazia),
    ``canal_feito`` / ``canal_motivo``, ``firmware_pedido`` /
    ``firmware_motivo``, ``ativo`` (a fonte que ficou valendo) e ``motivo`` —
    a junção das frases que faltaram. ``None`` = daemon não respondeu.

    **Por que as duas metades viajam separadas.** Elas falham por razões
    diferentes e em transportes diferentes: no rádio o DualSense não publica
    fonte de captura sem a ponte de microfone de pé (`mapa-controles.csv`,
    `audio.microfone.mudo` do dualsense: cabo=sim, rádio=parcial), e em Modo
    Nativo o hidraw é do jogo e o mudo do firmware fica represado (medido na
    bancada em 04/09: o `mic.set` respondia ``ok`` com o aparelho parado).
    Um ``False`` só diria "não deu"; a pessoa precisa saber qual metade.
    """
    payload: dict[str, Any] = {"ligado": bool(ligado)}
    if uniq:
        payload["uniq"] = uniq
    return _corpo_do_daemon("mic.canal.set", payload,
                             timeout=_TETO_DO_ATO_DE_AUDIO)


def sensor_set_detalhado(
    *,
    giroscopio: bool | None = None,
    acelerometro: bool | None = None,
    touchpad: str | None = None,
    uniq: str | None = None,
) -> dict[str, Any] | None:
    """``sensor.set`` com a RESPOSTA inteira do daemon — o giro, o accel e o touchpad."""
    payload: dict[str, Any] = {}
    if giroscopio is not None:
        payload["giroscopio"] = bool(giroscopio)
    if acelerometro is not None:
        payload["acelerometro"] = bool(acelerometro)
    if touchpad is not None:
        payload["touchpad"] = touchpad
    if not payload:
        return None
    if uniq:
        payload["uniq"] = uniq
    return _corpo_do_daemon("sensor.set", payload)


def frase_do_interruptor_de_sensor(corpo: Any) -> str | None:
    """A frase que vai para o CARTÃO daquele controle — ``None`` se deu certo."""
    if not isinstance(corpo, dict):
        return "o daemon não respondeu ao interruptor do sensor"
    status = corpo.get("status")
    if status != "ok":
        motivo = corpo.get("motivo")
        return str(motivo) if motivo else f"o daemon recusou: {status}"
    ressalva = corpo.get("ressalva")
    return str(ressalva) if ressalva else None


def frase_do_ato_do_microfone(corpo: Any) -> str | None:
    """A frase que vai para o CARTÃO daquele controle — ``None`` se deu certo."""
    if not isinstance(corpo, dict):
        return None
    if corpo.get("status") == "ok":
        return None
    motivo = corpo.get("motivo")
    return motivo if isinstance(motivo, str) and motivo else None


def mic_volume_set(volume: int, uniq: str | None = None) -> bool:
    """Volume da CAPTURA do microfone, no sistema (MIC-VOLUME-01, 16/08/2026).

    Pedido: *"um slicer de microfone pra definir o volume do microfone
    real (independente de saber se tá via bt ou via cabo), o app deve ser
    inteligente pra saber qual caminho usar"*.

    **Não confundir com `mic_set`.** São camadas diferentes e não se substituem:

    ===============  ====================================================
    `mic_set`        o MUDO no firmware do controle (camada 3). É o único
                     que apaga a luz vermelha do microfone, e enquanto
                     vigorar o botão físico deixa de valer.
    `mic_volume_set` o GANHO da fonte de captura no PipeWire (camada 1) e,
                     desde 09/09/2026, o `common[6]` do aparelho. Não tira
                     o botão físico, e não apaga luz nenhuma.
    ===============  ====================================================

    **Por que ele é universal.** O que existe nos dois transportes é uma FONTE
    de captura no sistema, e é nela que este pedido mexe primeiro. Por isso o
    mesmo controle deslizante vale nos dois transportes sem que ela precise
    saber qual está valendo, que era exatamente o pedido.

    **FATO SUBSTITUÍDO EM 09/09/2026 (MIC-VOLUME-02).** Esta linha dizia que *"o
    DualSense não expõe registrador de ganho de microfone — nem no cabo nem no
    rádio"*. **Expõe**: é o `common[6]`, nomeado pelo `hid-playstation`
    (`mic_volume`, `0x0 - 0x40`), e a bancada mediu a captura mudando com
    ele no cabo. O daemon passou a escrevê-lo no mesmo pedido, por `uniq`, logo
    depois da fonte — quem chama daqui continua não escolhendo caminho, e ganhou
    o segundo degrau de graça.

    **A ressalva honesta, e ela é do rádio.** Por Bluetooth o DualSense não
    expõe placa de áudio (medido em 16/08: `pactl list cards` traz só as duas
    placas da máquina). A fonte de captura no rádio só existe com a ponte de
    `integrations/dualsense_bt_audio.py` de pé — e em 16/08 ela ainda **não é
    segura** (ver o estudo `2026-08-16-O-PS-PRESO-*`). Sem fonte, o daemon
    responde `sem_fonte` e o controle deslizante fica insensível com a dica
    dizendo por quê. Um controle cinza não promete nada; um controle que aceita
    o gesto e não faz nada é a tela mentindo.

    `volume` é por cento (0-100), a escala do sistema — e não os 0-255 do
    alto-falante, que escreve um byte do report.

    Retorna True se o daemon confirmou; False se offline, sem controle ou sem
    fonte de captura — **os três colapsados no mesmo ``False``**. Quem precisa
    separá-los (e a ressalva do rádio acima é exatamente isso) chama
    :func:`mic_volume_set_detalhado`.
    """
    corpo = mic_volume_set_detalhado(volume, uniq)
    return corpo is not None and corpo.get("status") == "ok"


def mic_volume_set_detalhado(
    volume: int, uniq: str | None = None
) -> dict[str, Any] | None:
    """``mic.volume.set`` que entrega a RESPOSTA do daemon (ELO-MUDO-01, 23/08)."""
    volume = max(0, min(100, int(volume)))
    payload: dict[str, Any] = {"volume": volume}
    if uniq:
        payload["uniq"] = uniq
    return _corpo_do_daemon("mic.volume.set", payload,
                             timeout=_TETO_DO_ATO_DE_AUDIO)


def speaker_set(
    volume: int | None = None,
    muted: bool | None = None,
    uniq: str | None = None,
    release: bool = False,
    rota: int | None = None,
    fonte: str | None = None,
) -> bool:
    """Volume/mudo/devolução do alto-falante e do fone (D4 / MIC-USB-01 / SOM-02).

    DECISÃO DA MIC-USB-01, registrada aqui de propósito: o ``speaker.set``
    existia no IPC desde a D4 **sem um único chamador no produto** — método de
    protocolo que ninguém chama é dívida com aparência de recurso, e a sprint
    deu duas saídas, ganhar superfície ou sair. Ele FICA, e ganha superfície
    junto com o microfone, por uma razão de substância e não de simpatia: mic e
    alto-falante do DualSense são o MESMO bloco de posse do report de saída
    (``common[4..9]``, AUDIO-OWNER-01). Expor só metade deixaria a outra metade
    como um escritor sem dono à espera de virar o próximo bug dos dois
    escritores — que é exatamente a classe de defeito que a MIC-USB-01 foi
    fechar. Sair custaria uma quebra de protocolo e apagaria a única forma de
    baixar o alto-falante do controle, que é alto de fábrica.

    ``volume`` 0-255 (None mantém o vigente); ``muted=True`` manda 0 sem perder
    o volume preferido e ``muted=False`` o restaura. A primeira chamada faz o
    hefesto assumir a posse dos bytes de volume: o DualSense não devolve esse
    registrador, então ``daemon.state_full`` só passa a trazer a chave
    ``speaker`` DEPOIS de um ``speaker.set`` — antes disso publicar um número
    seria inventá-lo.

    ``release=True`` (SOM-02/E3) DEVOLVE a posse: o hefesto PARA de mandar o
    volume, os bits de áudio do report voltam a sair zerados e a chave
    ``speaker`` some do ``daemon.state_full`` no tique seguinte. O que ele
    devolve é o CONTROLE, não o valor — não existe leitura desse registrador,
    então ninguém pode saber qual era o volume antes de nós; o firmware fica com
    o ÚLTIMO número que mandamos. Prometer restauração na tela seria mentira.

    ``release`` NÃO se mistura com ``volume``/``muted``: a combinação levanta
    ``ValueError`` aqui e é erro de validação no daemon. "Pare de mandar E mande
    isto" não tem significado honesto, e escolher um vencedor em silêncio
    esconderia um chamador confuso.

    NUNCA chamar sem ``volume``, ``muted`` ou ``release``: medido na SOM-02, a
    chamada vazia toma a posse e manda ZERO (armadilha 1). "Assumir sem mudar
    nada" seria uma chave nova e explícita, não o payload vazio.

    Retorna True se o daemon confirmou; False se offline ou sem controle —
    **os dois no mesmo ``False``**. Quem precisa separá-los chama
    :func:`speaker_set_detalhado`.
    """
    corpo = speaker_set_detalhado(volume, muted, uniq, release, rota, fonte)
    return corpo is not None and corpo.get("status") == "ok"


def speaker_set_detalhado(
    volume: int | None = None,
    muted: bool | None = None,
    uniq: str | None = None,
    release: bool = False,
    rota: int | None = None,
    fonte: str | None = None,
) -> dict[str, Any] | None:
    """``speaker.set`` que entrega a RESPOSTA do daemon (ELO-MUDO-01, 23/08)."""
    if release and (volume is not None or muted is not None):
        raise ValueError(
            "speaker_set: 'release' não combina com volume/muted — devolver a "
            "posse e mandar um valor na mesma chamada não tem significado "
            "honesto; faça duas chamadas"
        )
    payload: dict[str, Any] = {}
    if release:
        payload["release"] = True
    if volume is not None:
        payload["volume"] = int(volume)
    if muted is not None:
        payload["muted"] = bool(muted)
    if uniq:
        payload["uniq"] = uniq
    if rota is not None:
        payload["rota"] = int(rota)
    if fonte is not None:
        payload["fonte"] = str(fonte)
    return _corpo_do_daemon("speaker.set", payload,
                             timeout=_TETO_DO_ATO_DE_AUDIO)


def mira_set_detalhado(
    *,
    ligada: bool | None = None,
    sensibilidade: int | None = None,
    zona_morta_graus_s: float | None = None,
    uniq: str | None = None,
    gatilho: str | None = None,
    inverter_horizontal: bool | None = None,
    inverter_vertical: bool | None = None,
    inclinacao: str | None = None,
    toque: str | None = None,
    mesmo_parado: bool | None = None,
    lado: str | None = None,
) -> dict[str, Any] | None:
    """``mira.set`` com a RESPOSTA inteira — o chip «Analógico Virtual» e a Calibrar."""
    payload: dict[str, Any] = {}
    if ligada is not None:
        payload["ligada"] = bool(ligada)
    if sensibilidade is not None:
        payload["sensibilidade"] = int(sensibilidade)
    if zona_morta_graus_s is not None:
        payload["zona_morta_graus_s"] = float(zona_morta_graus_s)
    if gatilho is not None:
        payload["gatilho"] = gatilho or None
    if inverter_horizontal is not None:
        payload["inverter_horizontal"] = bool(inverter_horizontal)
    if inverter_vertical is not None:
        payload["inverter_vertical"] = bool(inverter_vertical)
    if inclinacao is not None:
        payload["inclinacao"] = str(inclinacao)
    if toque is not None:
        payload["toque"] = str(toque)
    if mesmo_parado is not None:
        payload["mesmo_parado"] = bool(mesmo_parado)
    if lado is not None:
        payload["lado"] = str(lado)
    if not payload:
        return None
    if uniq:
        payload["uniq"] = uniq
    return _corpo_do_daemon("mira.set", payload)


def haptica_testar(uniq: str, ligado: bool) -> tuple[bool, dict[str, Any] | None]:
    """``haptica.testar`` — o botão «Háptica» da aba Vibração, num controle."""
    corpo = _corpo_do_daemon("haptica.testar", {"uniq": uniq, "ligado": bool(ligado)})
    return corpo is not None, corpo


# A medição é esta: a aba Mouse fala `mouse.emulation.set` por `call_async`

__all__ = [
    "PROFILE_SWITCH_TIMEOUT_S",
    "alvo_honrado",
    "call_async",
    "daemon_state_full",
    "daemon_status_basic",
    "destinos_da_aplicacao",
    "frase_do_ato_do_microfone",
    "frase_do_interruptor_de_sensor",
    "freestyle_set",
    "haptica_testar",
    "identity_number_set",
    "led_set",
    "led_set_detalhado",
    "machine_declare",
    "machine_declare_detalhado",
    "mic_canal_set",
    "mic_canal_set_detalhado",
    "mic_set",
    "mic_set_detalhado",
    "mic_volume_set_detalhado",
    "mira_set_detalhado",
    "player_leds_set",
    "player_leds_set_detalhado",
    "profile_list",
    "profile_switch",
    "rumble_motores_set",
    "rumble_passthrough",
    "rumble_policy_custom",
    "rumble_policy_set_checked",
    "rumble_set",
    "rumble_stop",
    "run_in_thread",
    "sensor_set_detalhado",
    "speaker_set",
    "speaker_set_detalhado",
    "trigger_reset_detalhado",
    "trigger_set",
    "trigger_set_checked",
    "trigger_set_detalhado",
]

