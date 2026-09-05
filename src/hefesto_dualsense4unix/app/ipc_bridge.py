"""Cliente IPC síncrono/assíncrono para a GUI GTK.

`_run_call` é síncrono e bloqueante — NÃO chamar da thread principal GTK.
`call_async` despacha para um ThreadPoolExecutor (1 worker) e re-posta os
callbacks via `GLib.idle_add`, mantendo a thread GTK livre durante I/O.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.cli.ipc_client import IpcClient, IpcError
from hefesto_dualsense4unix.daemon.ipc_server import CODE_INVALID_PARAMS
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

# Executor lazy-init — criado na primeira chamada de call_async.
_EXECUTOR: concurrent.futures.ThreadPoolExecutor | None = None

# Exceções esperadas de transporte/disponibilidade do daemon. Capturar apenas
# essas nos wrappers públicos mantém a trilha visível quando o daemon está
# offline (resultado False legítimo) e deixa bugs reais (ValueError, TypeError,
# RuntimeError inesperados) propagarem — AUDIT-FINDING-IPC-BRIDGE-BARE-EXCEPT-01.
_IPC_TRANSPORT_ERRORS: tuple[type[BaseException], ...] = (
    FileNotFoundError,
    ConnectionError,
    IpcError,
    OSError,
)

#: ATIVAR-NAO-MENTE-01 (leva 2, 05/08): quanto esperar por um `profile.switch`.
#:
#: O default de 250 ms desta ponte é o timeout de LEITURA — cabe num
#: `daemon.state_full`, e é curto de propósito para a janela não pendurar
#: esperando um daemon morto. Só que `profile.switch` não é leitura: o handler
#: faz `activate` + `save_active_marker` + `materialize_launch_env` e levou
#: ~1,2 s MEDIDOS no journal dela. Resultado: TODA ativação estourava o
#: timeout, a janela dizia "Falha (daemon offline?)" com o perfil JÁ ativo, e
#: ela clicava de novo — cada clique uma ativação real.
#:
#: Mesma família (e mesma cura) do `MODE_IPC_TIMEOUT_S` de
#: `app/actions/mode_transition.py`: a chamada que MUDA o mundo ganha a folga
#: que a leitura não pode ter. O applet COSMIC espelha este número em
#: `packaging/cosmic-applet/src/ipc.rs` (`SWITCH_IPC_TIMEOUT`) — os dois falam
#: com o MESMO daemon, e divergir aqui é reabrir o defeito de um lado só.
PROFILE_SWITCH_TIMEOUT_S: float = 3.0


def _get_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Retorna (criando se necessário) o executor IPC compartilhado."""
    global _EXECUTOR  # necessário: lazy singleton
    if _EXECUTOR is None:
        _EXECUTOR = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="hefesto-ipc",
        )
    return _EXECUTOR


def _run_call(
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float | None = 0.25,
) -> Any:
    """Executa RPC de forma síncrona com timeout.

    ATENÇÃO: função bloqueante. Não deve ser chamada da thread principal GTK.
    Indicada para uso em CLI, TUI ou dentro do worker do executor.
    """
    async def _do() -> Any:
        async with IpcClient.connect(timeout=timeout) as client:
            # BUG-IPC-READ-NO-TIMEOUT-01: o timeout precisa cobrir TAMBÉM a
            # leitura da resposta, não só o connect — um daemon que aceita a
            # conexão mas trava ao responder bloquearia o worker eternamente.
            # IpcClient.call envolve o readline em asyncio.wait_for e converte
            # TimeoutError em IpcError(-1, "conexão timeout") (já capturado).
            return await client.call(method, params or {}, timeout=timeout)

    return asyncio.run(_do())


def _safe_call(
    method: str,
    params: dict[str, Any] | None = None,
    timeout: float | None = 0.25,
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
        result = _run_call(method, params, timeout=timeout)
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
    timeout_s: float = 0.25,
) -> None:
    """Despacha RPC para thread worker; callbacks re-postados via GLib.idle_add.

    - `on_success(result)` é chamado na thread principal GTK após conclusão.
    - `on_failure(exc)` é chamado na thread principal GTK em caso de erro.
    - Ambos os callbacks DEVEM retornar `False` para não serem repetidos
      pelo GLib (contrato de `GLib.idle_add`).

    A função não bloqueia a thread GTK em nenhuma circunstância.
    """
    # Import adiado para permitir testes sem GTK instalado.
    from gi.repository import GLib

    def _worker() -> None:
        try:
            result = _run_call(method, params, timeout=timeout_s)
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
    """Roda ``fn()`` em thread worker; callbacks re-postados via GLib.idle_add.

    Generaliza ``call_async`` para qualquer função bloqueante fora de IPC (ex.:
    ler perfis do disco com ``load_all_profiles``), mantendo a thread GTK livre.
    Reusa o mesmo executor de 1 worker. Os callbacks DEVEM retornar ``False``
    (contrato de ``GLib.idle_add``).
    """
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


# ---------------------------------------------------------------------------
# Helpers síncronos de alto nível (usados por CLI e código legado da GUI que
# já está em thread worker ou contexto de teste).
# ---------------------------------------------------------------------------


def daemon_state_full() -> dict[str, Any] | None:
    """Retorna estado completo via IPC; None se daemon offline."""
    ok, result = _safe_call("daemon.state_full")
    if ok and isinstance(result, dict):
        return result
    return None


def autoswitch_lock_set(locked: bool | None = None) -> bool | None:
    """Congela/descongela a troca automática de perfil (FEAT-AUTOSWITCH-LOCK-01).

    `locked=None` faz toggle no daemon. Devolve o estado resultante
    (True=congelado), ou None se o daemon está offline.
    """
    params: dict[str, Any] = {}
    if locked is not None:
        params["locked"] = bool(locked)
    ok, result = _safe_call("autoswitch.lock", params)
    if ok and isinstance(result, dict):
        estado = result.get("autoswitch_locked")
        return bool(estado) if isinstance(estado, bool) else None
    return None


def daemon_status_basic() -> dict[str, Any] | None:
    """Retorna status básico via IPC; None se daemon offline."""
    ok, result = _safe_call("daemon.status")
    if ok and isinstance(result, dict):
        return result
    return None


def profile_list() -> list[dict[str, Any]]:
    """Lista perfis. Preferência: daemon (traz 'active'); fallback: disco."""
    ok, result = _safe_call("profile.list")
    if ok and isinstance(result, dict):
        profiles = list(result.get("profiles", []))
        if profiles:
            return profiles

    try:
        from hefesto_dualsense4unix.profiles.loader import load_all_profiles

        return [
            {
                "name": p.name,
                "priority": p.priority,
                "match_type": p.match.type,
                "active": False,
            }
            for p in load_all_profiles()
        ]
    except (FileNotFoundError, PermissionError, OSError) as exc:
        # PROFILE-LOADER-UX-01: load_all_profiles agora pula perfis corrompidos
        # internamente; aqui só sobram falhas de I/O do diretório de perfis
        # (permissão negada, FS desmontado etc.). Logar com exc_info para a
        # GUI mostrar diretório vazio + investigador ter trilha.
        logger.warning(
            "profile_load_fallback_failed",
            err=str(exc),
            err_type=type(exc).__name__,
            exc_info=True,
        )
        return []


def active_profile_name() -> str | None:
    """Nome do perfil ATIVO no daemon (``state_full.active_profile``) ou None.

    PERFIL-SAVE-APPLY-01: usado pelo Salvar da aba Perfis para decidir se o
    perfil recém-gravado precisa ser reaplicado na hora (daemon não relê
    JSON de perfil por conta própria). Best-effort: offline = None.
    """
    ok, res = _safe_call("daemon.state_full", {})
    if ok and isinstance(res, dict):
        nome = res.get("active_profile")
        if isinstance(nome, str) and nome:
            return nome
    return None


def profile_switch(name: str) -> bool:
    """Ativa um perfil no daemon; ``False`` quando ele não confirmou.

    ATIVAR-NAO-MENTE-01: com o timeout de leitura (250 ms) esta função devolvia
    ``False`` para uma ativação que o daemon estava CUMPRINDO — os ~1,2 s do
    handler não cabiam. Quem lê o ``False`` são a CLI (`cmd_profile`), o
    ciclador de perfil e o Salvar da aba Perfis, e os três passaram a anunciar
    falha de uma troca que aconteceu. Ver `PROFILE_SWITCH_TIMEOUT_S`.
    """
    ok, _ = _safe_call(
        "profile.switch", {"name": name}, timeout=PROFILE_SWITCH_TIMEOUT_S
    )
    return ok


def _corpo_do_daemon(
    method: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """RPC que entrega o CORPO da resposta, ou ``None`` quando não houve corpo.

    ELO-MUDO-01 (23/08/2026). É a forma que ``apply_draft_detalhado`` já usava
    sozinha desde 22/08, promovida a peça: ``None`` significa "NÃO HOUVE
    RESPOSTA utilizável" (daemon offline, transporte, resposta que não é
    dicionário) e um ``dict`` significa "o daemon falou — leia o que ele disse".

    A distinção é o produto inteiro desta função: hoje meia dúzia de invólucros
    desta ponte estreitam para ``bool`` um corpo que o daemon montou com
    cuidado, e a tela do outro lado passa a re-DEDUZIR o que já sabia — foi
    assim que "aplicado" apareceu com ``aplicado_em: []`` e ``guardado_em: []``
    na mesa vazia.

    **Sem parâmetro de ``timeout``, de propósito.** As cinco rotas que passam
    por aqui são as de leitura curta (250 ms), e a chamada sai com a MESMA forma
    de sempre — ``_safe_call(method, params)``, dois argumentos posicionais.
    Isso não é detalhe: há dublês de ``_safe_call`` em testes de outras abas
    escritos como uma lambda de DOIS parâmetros, e acrescentar um ``timeout=``
    aqui os quebra sem que nada do produto tenha mudado (medido em 23/08, dois
    testes da SOM-02). Quem precisar de folga — ``apply_draft_detalhado`` e
    ``machine_declare``, que escrevem em disco — continua chamando o
    ``_safe_call`` direto com o teto dele.
    """
    ok, result = _safe_call(method, params)
    if ok and isinstance(result, dict):
        return result
    return None


def _call_checked_detalhado(
    method: str,
    params: dict[str, Any],
    timeout: float | None = 0.25,
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """``_call_checked`` que NÃO joga fora o corpo da resposta (ELO-MUDO-01).

    Retorna ``(ok, motivo, corpo)``, onde ``ok`` e ``motivo`` são exatamente os
    de :func:`_call_checked` — que passou a ser um invólucro desta — e ``corpo``
    é o dicionário que o daemon devolveu, ou ``None`` quando ele não respondeu
    (ou respondeu algo que não é dicionário).

    Por que a função nova em vez de trocar a assinatura de ``_call_checked``:
    o mesmo motivo escrito em ``apply_draft_detalhado`` — a forma de hoje tem
    chamadores vivos em arquivos que outras frentes estão editando, e uma
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
        resultado = _run_call(method, params, timeout=timeout)
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
    timeout: float | None = 0.25,
) -> tuple[bool, str | None]:
    """RPC que distingue "o daemon RECUSOU" de "o daemon não respondeu".

    Retorna ``(ok, motivo)``. ``motivo`` só vem preenchido quando o daemon
    respondeu e recusou por parâmetro inválido (``CODE_INVALID_PARAMS``): ele
    está VIVO, o pedido é que não serve — a UI tem de mostrar o motivo dele, não
    acusar o daemon de estar morto. Falha de transporte (offline, socket ausente,
    timeout) volta como ``(False, None)``.

    Existe porque ``_safe_call`` colapsa os dois casos em ``(False, None)``
    (ver o docstring dele) e a UI pintava recusa de validação como "daemon
    offline?".

    Invólucro de :func:`_call_checked_detalhado`, que é onde o RPC acontece —
    esta aqui só descarta o corpo, para os chamadores de hoje continuarem
    desempacotando duas coisas.
    """
    ok, motivo, _corpo = _call_checked_detalhado(method, params, timeout=timeout)
    return ok, motivo


def _payload_trigger_set(
    side: str, mode: str, params: list[int], uniq: str | None
) -> dict[str, Any]:
    """Payload do ``trigger.set`` — um dono só, para as duas portas não divergirem."""
    payload: dict[str, Any] = {"side": side, "mode": mode, "params": params}
    if uniq:
        payload["uniq"] = uniq
    return payload


def trigger_set_detalhado(
    side: str, mode: str, params: list[int], uniq: str | None = None
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
    """
    ok, motivo, corpo = _call_checked_detalhado(
        "trigger.set", _payload_trigger_set(side, mode, params, uniq)
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


def _payload_trigger_reset(side: str | None, uniq: str | None) -> dict[str, Any]:
    """Payload do ``trigger.reset`` — um dono só, para as duas portas não divergirem."""
    payload: dict[str, Any] = {}
    if side:
        payload["side"] = side
    if uniq:
        payload["uniq"] = uniq
    return payload


def trigger_reset_detalhado(
    side: str | None = None, uniq: str | None = None
) -> tuple[bool, str | None, dict[str, Any] | None]:
    """LIBERA a trava manual e devolve o gatilho ao perfil (`trigger.reset`).

    Mesmo contrato de :func:`trigger_set_detalhado` — e o mesmo corpo
    (``status``/``aplicado_em``/``guardado_em``), porque os dois handlers foram
    escritos como espelho um do outro (ELO-MUDO-01, 23/08).

    R-19 (auditoria 23/07): o RPC já existia e já estava roteado
    (`ipc_server.py:102`), mas a GUI não o expunha — então o botão "Desligar" da
    aba Gatilhos mandava outro `trigger.set` com modo "Off". A diferença é
    decisiva: `trigger.set` **ARMA** `mark_manual_trigger_active`, então o botão
    que a usuária usa para "voltar ao normal" era mais um jeito de PAUSAR a
    troca automática de perfil. É a queixa "estado armado que nunca é liberado".

    ABAS-06 (25/07): `uniq` — MAC do controle escolhido no seletor. Este era o
    ÚNICO comando de saída da janela sem alvo: com "Controle 2" selecionado,
    "Desligar" zerava o gatilho dos QUATRO, enquanto o "Aplicar" ao lado
    mandava para um só. Omitido = comportamento global clássico.

    ABAS-05 (25/07): o clear das TRÊS categorias (documentado como "contrato
    deliberado" até 24/07) foi estreitado para a categoria `trigger` —
    desligar um gatilho apagava a trava de LED e de vibração de outras abas e
    reabria a troca automática para reescrever a cor recém-aplicada.

    Estes três parágrafos moraram no invólucro `trigger_reset`, podado em
    26/08/2026 por não ter chamador nenhum: quem aperta "Desligar" é
    `app/actions/triggers_actions.py:697`, e chama esta.
    """
    ok, motivo, corpo = _call_checked_detalhado(
        "trigger.reset", _payload_trigger_reset(side, uniq)
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
    """Lê a recusa que vem no CORPO de uma resposta bem-sucedida.

    NATIVO-RUMBLE-01 (19/08/2026). Esta casa tem DOIS jeitos de o daemon dizer
    "não": o erro JSON-RPC ``CODE_INVALID_PARAMS`` — que ``_call_checked`` já
    sabe ler — e o campo ``status`` do resultado, usado quando o pedido é
    *válido* e mesmo assim não se realiza (o ``coop.set`` que recusa desligar, o
    vocabulário ``EMU_*`` do gamepad, e agora o rumble sob Modo Nativo).

    A diferença importa porque para o segundo caso o ``_call_checked`` responde
    ``(True, None)``: o RPC foi bem-sucedido. Sem esta leitura, a recusa medida
    do daemon chegaria na tela como "Vibração travada (fraca=…, forte=…)" com o
    motor parado — a mentira que o NATIVO-RUMBLE-01 mediu, e a mesma classe de
    defeito do HARM-19 pelo avesso.

    **E não é só recusa** (20/08/2026, censo das nove abas). O ``rumble.stop``
    dentro do Modo Nativo devolve ``status: "ok"`` — porque ele REALIZOU parte do
    pedido: soltou o par que o Hefesto segurava. O que ele não consegue é calar o
    motor que o JOGO está tocando pelo hidraw, e é isso que o ``motivo`` diz. Ler
    só o ``status`` deixava a aba anunciar "Vibração parada (travada em
    silêncio)" com o motor girando.

    Então a regra é: **se o daemon mandou uma frase, ela é para ela.** O produto
    não põe ``motivo`` numa resposta sem ter o que explicar.

    Devolve o ``motivo`` quando houver um, e ``None`` quando o pedido valeu sem
    ressalva.
    """
    if not isinstance(resultado, dict):
        return None
    motivo = resultado.get("motivo")
    return motivo if isinstance(motivo, str) and motivo else None


def rumble_set_checked(weak: int, strong: int) -> tuple[bool, str | None]:
    """Fixa a vibração devolvendo o MOTIVO quando o daemon RECUSA.

    Recusa típica: o Modo Nativo está ligado e o jogo é o dono dos motores
    (NATIVO-RUMBLE-01). Ver ``_recusa_no_corpo`` para por que a recusa não vem
    como erro JSON-RPC — e por que ``_call_checked`` não serve aqui.
    """
    ok, resultado = _safe_call("rumble.set", {"weak": weak, "strong": strong})
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


def rumble_stop_checked() -> tuple[bool, str | None]:
    """Para a vibração devolvendo a FRASE do daemon quando ele tem uma.

    NATIVO-RUMBLE-01, segunda metade (20/08/2026). Dentro do Modo Nativo este
    gesto não trava silêncio: ele SOLTA o par que o Hefesto segurava e devolve
    ``status: "ok"`` com o motivo, porque calar o motor que o jogo toca pelo
    hidraw não está ao alcance do produto. A aba anunciava "Vibração parada
    (travada em silêncio)" nesse caso — a mesma mentira que o "Aplicar" e o
    "Testar" já não contam desde 19/08, e que ficou aqui por eu ter parado nos
    dois primeiros botões.
    """
    ok, resultado = _safe_call("rumble.stop", {})
    if not ok:
        return False, None
    return True, _recusa_no_corpo(resultado)


def rumble_stop() -> bool:
    """Para rumble e FIXA (0, 0) — **isto não devolve a vibração ao jogo**.

    Descarta a frase do daemon — use ``rumble_stop_checked`` para tê-la.

    **"PARAR" NÃO É "DESFAZER", e a diferença tem consequência medida**
    (04/09/2026, no aparelho, pelo ensaio
    `scripts/ensaios/o_multiplicador_chega_ao_motor.py`). O par ``(0, 0)`` é um
    par FIXADO, e não `None`: enquanto ele estiver de pé,
    `daemon.subsystems.gamepad.apply_game_rumble` **descarta o FF de todo
    jogo** na primeira linha (`rumble_active is not None` → `return None`). Um
    instrumento que chamou `rumble_stop` achando que estava "limpando a
    bagunça" deixou a máquina dela **sem vibração em jogo nenhum, em
    silêncio** — e não havia uma palavra aqui que avisasse.

    **A FIXAÇÃO É DELIBERADA, e não é defeito** (`_handle_rumble_stop`,
    HARM-16): o poll loop re-afirma o silêncio para que outra escrita HID não
    reative os motores por acidente. O que faltava era esta frase.

    **Quem quer devolver a vibração ao jogo chama `rumble_passthrough(True)`.**
    """
    ok, _motivo = rumble_stop_checked()
    return ok


def rumble_passthrough(enabled: bool = True) -> bool:
    """Devolve a vibração ao JOGO (BUG-RUMBLE-APPLY-IGNORED-01).

    É o par simétrico de `rumble_stop`, e é ELE — não o "parar" — que solta o
    par fixado (`rumble_active = None`). Ver a advertência em `rumble_stop`.
    """
    ok, _ = _safe_call("rumble.passthrough", {"enabled": bool(enabled)})
    return ok


def rumble_motores_set(
    *,
    forte_pct: int | None = None,
    fraco_pct: int | None = None,
    uniq: str | None = None,
) -> tuple[bool, dict[str, Any] | None]:
    """A BARRA de cada motor, no perfil, POR PEÇA (VIBRACAO-POR-MOTOR-01).

    Decisão dela, 04/09/2026: a barra não manda o par `rumble.set` agora — ela
    é POLÍTICA, e MULTIPLICA o degrau da coluna. ``efetivo(motor) = degrau x
    barra(motor)``.

    ``None`` em um dos dois = **não mexe naquela barra**; passar os dois em
    `None` é erro (não haveria o que gravar). ``uniq`` omitido = o primário.

    Devolve ``(ok, corpo)``, e o corpo é o do daemon — ele traz `status`
    (`"ok"`, `"sem_controle"`, `"sem_endereco"`, `"sem_perfil"`), o `motivo`
    quando recusa, o `perfil` em que gravou, se `gravado` de fato (regravar
    perfil idêntico troca a data do arquivo e faz o daemon reaplicá-lo), e os
    `forte_pct`/`fraco_pct` que **passaram a valer** — que é o que a tela pinta
    de volta. Corpo `None` quer dizer daemon fora do ar.

    **A tela NÃO deve digitar a faixa nem o padrão:** quem recusa fora de 0-100
    é a borda do esquema, com a frase que explica, e o 100 do "sem opinião"
    chega no `state_full` como `rumble_motor_pct_padrao`.
    """
    params: dict[str, Any] = {}
    if forte_pct is not None:
        params["forte_pct"] = int(forte_pct)
    if fraco_pct is not None:
        params["fraco_pct"] = int(fraco_pct)
    if uniq:
        params["uniq"] = uniq
    corpo = _corpo_do_daemon("rumble.motores.set", params)
    return corpo is not None, corpo


def rumble_policy_set_checked(
    policy: str, *, timeout: float | None = 0.25
) -> tuple[bool, str | None]:
    """Altera a intensidade devolvendo o MOTIVO quando o daemon RECUSA.

    ``policy`` é um de "economia", "balanceado", "max", "auto", "custom"
    (FEAT-RUMBLE-POLICY-01).

    Mesmo tratamento dos gatilhos (ver ``_call_checked``): a aba Rumble afirmava
    "O Hefesto não está rodando" também para erro JSON-RPC — daemon VIVO que
    recusou o pedido. ``timeout`` é do chamador: a folga de leitura de estado
    mora em ``app.actions.mode_transition``, que importa este módulo (importá-lo
    aqui seria ciclo).

    Esta é a ÚNICA porta do ``rumble.policy_set`` desde 26/08/2026, e as duas
    que caíram deixaram medição: o invólucro ``rumble_policy_set`` descartava o
    motivo da recusa (nunca teve chamador de produção), e o
    ``rumble_policy_set_detalhado`` existia pela uniformidade das três rotas de
    ``_call_checked``, mas o corpo deste RPC é ECO — ``{"status": "ok",
    "policy": <a pedida>}``, medido em 23/08/2026 — então não havia verdade
    nenhuma escondida no corpo para a aba recuperar. Se um dia o daemon passar
    a resolver a política EFETIVA (``auto`` virando um valor concreto), é aqui
    que a forma ``(ok, motivo, corpo)`` volta.
    """
    return _call_checked("rumble.policy_set", {"policy": policy}, timeout=timeout)


def rumble_policy_custom(mult: float) -> bool:
    """Define política "custom" com multiplicador explícito (FEAT-RUMBLE-POLICY-01).

    ``mult`` deve ser float em ``[0.0, RUMBLE_CUSTOM_MULT_MAX]`` — a faixa mora
    em ``profiles.schema`` e o handler do daemon recusa fora dela (HARM-19).
    Este texto dizia ``[0.0, 1.0]`` à mão e ficou mentindo de 11/08/2026, quando
    o teto voltou a 2.0 por decisão dela: acima de 1.0 o multiplicador
    AMPLIFICA o que o jogo pediu.

    Retorna True se o daemon confirmou; False se offline ou parâmetro inválido.
    """
    ok, _ = _safe_call("rumble.policy_custom", {"mult": float(mult)})
    return ok


#: PLAYER-01: motivos de recusa do ``identity.number.set`` traduzidos para a
#: frase que a janela mostra. Mapa explícito (não f-string do ``reason``) para
#: a usuária nunca ler um identificador do protocolo na barra de status.
_MOTIVOS_NUMERO: dict[str, str] = {
    "sessao_de_jogo_aberta": (
        "Feche o jogo antes de trocar o número — trocar agora repintaria "
        "o controle no meio da partida"
    ),
    "controle_ausente": (
        "Este controle não está na mesa agora — só quem está ligado tem número"
    ),
    "numero_fora_da_mesa": (
        "Esse número é maior do que a quantidade de controles ligados"
    ),
    "lock_timeout": "O Hefesto está ocupado — tente de novo em um instante",
}


def identity_number_set(uniq: str, number: int) -> tuple[bool, str | None]:
    """Atribui o NÚMERO EXIBIDO do controle ``uniq`` (PLAYER-01, 25/07).

    O comando que faltava no projeto inteiro: até 25/07 não havia forma
    nenhuma de dizer "este controle é o 2". Só existia ``identity.renumber``,
    que compacta TODOS preservando a ordem relativa e mora na aba Início — e
    era por isso que a expectativa dela ("escolho o player e o cabeçalho
    acompanha") não tinha como se realizar: ela clicava num controle de
    APARÊNCIA (o desenho das 5 luzes) esperando mudar IDENTIDADE.

    Devolve ``(ok, motivo)``. ``motivo`` só vem preenchido quando o daemon
    RESPONDEU e RECUSOU — cada ``reason`` do protocolo já traduzido para a
    frase da janela (:data:`_MOTIVOS_NUMERO`). Daemon offline volta como
    ``(False, None)``: a distinção existe porque a tela precisa dizer coisas
    diferentes em "o Hefesto está desligado" e "o jogo está aberto".

    ``number`` é 1..N entre os controles PRESENTES (NUM-01: o número exibido
    é a colocação entre quem está na mesa). Não confundir com o número de
    JOGADOR do co-op — ver ``app/actions/base.py:26``.
    """
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


#: CONFIG-03: motivos de recusa do ``machine.declare`` traduzidos para a frase
#: que a janela mostra. Mapa explícito pela mesma razão do
#: :data:`_MOTIVOS_NUMERO`: a usuária nunca lê identificador de protocolo na
#: barra de status.
_MOTIVOS_MAQUINA: dict[str, str] = {
    "versao_desconhecida": (
        "O arquivo com o que você declarou sobre a mesa foi escrito por uma "
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


#: CONFIG-06 (23/08/2026): campo de topo do ``MaquinaConfig`` → o módulo de
#: seção que o declara na aba Configurações. Mesma fronteira e mesma razão do
#: :data:`_MOTIVOS_MAQUINA`: quando um campo é descartado, a frase do rodapé
#: precisa nomear o que se perdeu, e ela nunca pode nomeá-lo ``orcamento``.
#:
#: AQUI FICA O VÍNCULO, NUNCA A PALAVRA. Até 25/08/2026 este mapa guardava os
#: rótulos por CÓPIA — ``{"mesa": "A mesa", "orcamento": "Orçamento"}`` — com um
#: comentário dizendo que "os rótulos são os ``TITULO`` de
#: ``app/actions/config/``". Eram, mas por cópia: renomear a seção sem tocar
#: aqui fazia o rodapé acusar a perda de "A mesa" numa aba onde a seção se chama
#: outra coisa, e nenhum portão via a divergência, porque os dois lados passavam
#: em separado. A LEX-1 da CONFIGURAÇÕES-O-LÉXICO-01 (25/08/2026) troca a cópia
#: pela derivação: o ``TITULO`` do módulo vira o único dono da palavra.
_SECAO_DO_CAMPO: dict[str, str] = {
    "mesa": "secao_mesa",
    "controles": "secao_controles",
    "orcamento": "secao_orcamento",
}

#: Os campos que NÃO derivam de um ``TITULO``, com a razão de cada um.
#:
#: CONEXÕES · MAPA 2D 01 (25/08/2026). O ``mapa`` é o único assim: ele não tem
#: seção própria — mora numa janela que abre de dentro de "A mesa". O rótulo
#: nomeia o que se PERDE, que é o desenho do gabinete, e não a seção de onde ele
#: é aberto: dizer "A mesa" aqui faria a frase do rodapé acusar a perda de outra
#: coisa.
_ROTULOS_SEM_SECAO: dict[str, str] = {
    "mapa": "O desenho da mesa",
}


def _rotulos_dos_campos() -> dict[str, str]:
    """``{campo do schema: rótulo de tela}``, LIDO das seções, nunca copiado.

    O import é PREGUIÇOSO, e é obrigatório que seja: ``secao_janela`` importa
    este módulo no topo (``secao_janela.py:54``), então um import de
    ``config.secoes`` no topo daqui fecharia o ciclo e derrubaria a janela na
    abertura. Preguiçoso, ele só roda quando o rodapé precisa da frase — muito
    depois de todos os módulos estarem de pé.

    Campo sem rótulo cai no nome cru, e há portão que exige uma entrada para
    cada campo do schema — e que reprova entrada SOBRANDO, que foi o que pegou
    ``ambiente`` quando ele saiu do schema (T2, CONFIGURAÇÕES-FECHA-01,
    24/08/2026). Esconder seria pior: a pessoa perderia o único aviso do que
    sumiu do arquivo dela.
    """
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


def __getattr__(nome: str) -> Any:
    """``ipc_bridge._CAMPOS_DA_MAQUINA`` continua existindo, agora DERIVADO.

    Ele deixou de ser uma atribuição de módulo e passou a ser calculado na hora
    da leitura (PEP 562). Duas razões, e as duas são de fronteira:

    * como atribuição no topo, a derivação rodaria na IMPORTAÇÃO do módulo, que
      é exatamente o instante em que o ciclo com ``secao_janela`` se fecha;
    * três arquivos de teste leem ``ipc_bridge._CAMPOS_DA_MAQUINA`` como
      dicionário (``test_descartados_chegam_ao_rodape.py:374``,
      ``test_o_teto_da_mesa_diz_o_que_faz.py:96``). Trocar a forma do nome
      público quebraria portões de outras frentes por uma mudança que é de
      redação — e a regra desta fronteira é aditiva, não destrutiva.
    """
    if nome == "_CAMPOS_DA_MAQUINA":
        return _rotulos_dos_campos()
    raise AttributeError(f"module {__name__!r} has no attribute {nome!r}")


def _rotulos_dos_descartados(result: dict[str, Any]) -> tuple[str, ...]:
    """Os campos descartados do corpo do daemon, já em rótulo de tela.

    Defensiva por contrato de fronteira: o corpo vem de outro processo, e um
    daemon mais velho (que não conhece a chave) ou um valor torto não podem
    derrubar o "Aplicar" de quem gravou com sucesso.
    """
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
    recusa. Vem em RÓTULO de tela (:data:`_CAMPOS_DA_MAQUINA`), e é **vazio no
    caso comum**: a chave nem aparece no corpo quando não há nada a dizer.

    Duas funções em vez de trocar o tipo de retorno da :func:`machine_declare`
    pela mesma razão do par ``apply_draft``/``apply_draft_detalhado``: a
    ``machine_declare`` está no ``__all__`` e a dupla ``(ok, motivo)`` é o
    contrato de quem já a chama. Aditivo — ninguém quebra, e quem precisa da
    verdade inteira pede por ela.

    ``_safe_call`` e não ``_call_checked`` pela razão de sempre nesta fronteira:
    a recusa vem no CORPO, não como ``CODE_INVALID_PARAMS`` — ver
    ``_handle_machine_declare``. E 1,0 s de teto em vez dos 250 ms de leitura
    porque este pedido escreve em disco; o gesto é raro e já congela a janela.
    """
    ok, result = _safe_call("machine.declare", {"maquina": maquina}, timeout=1.0)
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
    """Aplica bitmask de 5 LEDs de player no hardware via IPC (FEAT-PLAYER-LEDS-APPLY-01).

    ``bits[0]`` = LED 1 (extremo esquerdo), ``bits[4]`` = LED 5 (extremo direito).
    Retorna True se o daemon confirmou; False se offline ou erro.
    ``uniq`` (PERFIL-05): MAC do controle selecionado — aplica SÓ nele.

    **Não diz ONDE acendeu** — para isso existe :func:`player_leds_set_detalhado`.
    """
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


def apply_draft_detalhado(draft_dict: dict) -> dict | None:  # type: ignore[type-arg]
    """Envia ``profile.apply_draft`` e devolve a RESPOSTA INTEIRA do daemon.

    APLICAR-VERDADE-01/E2. Esta é a ÚNICA porta do ``profile.apply_draft``
    desde 26/08/2026 — quem decide "deu ou não deu" passa o retorno por
    :func:`aplicacao_confirmada`, que é o dono único da regra R-18.

    Houve um invólucro ``apply_draft`` que já fazia essas duas coisas e
    devolvia só o ``bool``. Ele foi podado por não ter chamador de produção
    nenhum, mas a medição que o justificava fica: um ``dict`` devolvido no
    lugar do ``bool`` é SEMPRE verdadeiro num ``if``, então trocar o tipo de
    retorno de uma porta booleana faria qualquer chamador não migrado dizer
    "aplicado" para um no-op — ``{"status": "ok", "applied": []}`` significa
    "nada entrou" e TEM de valer False. Por isso a forma detalhada nasceu como
    função nova em vez de reescrever a antiga, e por isso o ``bool`` nunca
    volta a esta assinatura sem passar pela ``aplicacao_confirmada``.

    ``draft_dict`` segue o contrato definido em ``DraftConfig.to_ipc_dict()``:
    chaves triggers/leds/rumble/mouse.

    Devolve o dicionário da resposta — que carrega ``status`` (sempre ``"ok"``,
    ver ``aplicacao_confirmada``), ``applied`` (as seções que entraram) e
    ``failed`` (mapa ``seção -> motivo curto`` das que não entraram). Devolve
    ``None`` quando NÃO HOUVE RESPOSTA utilizável: daemon offline, erro de
    transporte, resposta que não é um dicionário. A distinção existe porque a
    tela precisa dizer coisas diferentes em "o Hefesto está desligado" e "a
    seção de luzes não entrou" — mandar procurar o daemon quando ele está vivo
    é o defeito que esta sprint existe para eliminar.
    """
    ok, result = _safe_call("profile.apply_draft", draft_dict, timeout=1.0)
    if ok and isinstance(result, dict):
        return result
    return None


def aplicacao_confirmada(resposta: Any) -> bool:
    """A resposta do ``profile.apply_draft`` confirma que algo entrou? (R-18).

    Dono ÚNICO da regra de sucesso da aplicação — todo chamador de
    :func:`apply_draft_detalhado` decide por aqui, para não nascerem duas
    leituras do mesmo payload.

    R-18 (auditoria 23/07): `status` é SEMPRE "ok" — o handler responde isso
    mesmo quando o applier não aplicou seção nenhuma, e a GUI toastava "aplicado"
    para um no-op. Agora exigimos também que o daemon diga o que aplicou: uma
    resposta com `applied` vazio é um no-op honesto, não sucesso.

    O `status:"ok"` foi mantido de propósito (em vez de "partial"/"failed"): a
    GUI atual traduz status != "ok" como "daemon offline?", e essa mensagem
    mandaria a usuária caçar o problema no lugar errado. A honestidade entra
    pelo campo `applied`, que já viajava na resposta e ninguém lia.
    """
    if not isinstance(resposta, dict):
        return False
    if resposta.get("status") != "ok":
        return False
    aplicado = resposta.get("applied")
    if isinstance(aplicado, list):
        return bool(aplicado)
    # Daemon antigo, sem o campo: preserva o contrato v1.
    return True


def destinos_da_aplicacao(resposta: Any) -> tuple[list[str], list[str]]:
    """``(aplicado_em, guardado_em)`` de uma resposta do daemon (ELO-MUDO-01).

    Dono ÚNICO da leitura desses dois campos do lado da janela, pelo mesmo
    motivo de :func:`aplicacao_confirmada`: quatro rotas os publicam
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
    perfil da placa preso em ``input:iec958-stereo``, que é S/PDIF e não carrega
    sinal nenhum) são do WirePlumber, não do controle, e se curam pelo
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
    """``mic.set`` que entrega a RESPOSTA do daemon (ELO-MUDO-01, 23/08).

    Mesmo pedido do :func:`mic_set`; o que muda é o que volta. O corpo traz
    ``status`` (``"ok"`` ou ``"sem_controle"``), ``audio`` e
    ``mic_mudo_desejado``. ``None`` = daemon não respondeu.

    A diferença que este corpo permite é a que o ``bool`` apagava:
    ``sem_controle`` (o Hefesto está VIVO e não há controle na mesa) chegava na
    janela como o mesmo ``False`` de "o Hefesto está desligado".
    """
    if muted is None:
        # A PORTA DA POSSE continua sendo o `mic.set` cru, e ela é a única
        # coisa que o ato NÃO faz: `muted: null` devolve o byte ao
        # `hid-playstation`. Mandá-la pelo ato não faria sentido — o ato liga
        # ou desliga o microfone, e "devolver a posse" não é nenhum dos dois.
        payload: dict[str, Any] = {"muted": None}
        if uniq:
            payload["uniq"] = uniq
        return _corpo_do_daemon("mic.set", payload)
    # O 🎙 PASSA A SER O ATO INTEIRO — MICROFONE-UM-ATO-01 (04/09/2026).
    #
    # Esta função mandava `mic.set` e mais nada: o MUDO do firmware, metade do
    # gesto. A outra metade — a fonte de captura deste controle eleita e
    # ouvida — acontecia por EFEITO COLATERAL, e o efeito colateral foi medido
    # na bancada em 04/09: um `mic.set {muted: false}` mudava o bit, o laço das
    # bordas via a mudança e elegia o canal, e o microfone padrão do sistema
    # dela trocava sem que método nenhum tivesse dito isso.
    #
    # O conceito é dela, e derrubou a pergunta que eu tinha feito: *"o botão é
    # pra ligar o microfone e ele ser ouvido no canal específico dele"*. Um
    # ato só, com as duas metades declaradas.
    #
    # **O `status` NÃO MUDOU DE SIGNIFICADO**, e isso é deliberado: ele sempre
    # quis dizer *"o backend aceitou o pedido do firmware"*, e é o que os
    # chamadores de hoje leem para decidir se levantam a frase de recusa.
    # Trocá-lo por *"as duas metades aconteceram"* mudaria, em silêncio, o
    # comportamento de um botão que outra frente está editando neste momento.
    # A verdade inteira viaja nos campos NOVOS (`canal_feito`, `motivo`…) e em
    # :func:`mic_canal_set_detalhado`, que nasce sem chamador e por isso pode
    # nascer com o contrato inteiro.
    corpo = mic_canal_set_detalhado(not muted, uniq)
    if corpo is None:
        return None
    corpo = dict(corpo)
    corpo["mic_mudo_desejado"] = muted
    corpo["status"] = "ok" if corpo.get("firmware_pedido") else corpo.get("status")
    return corpo


def mic_canal_set(ligado: bool, uniq: str | None = None) -> bool:
    """O ATO do microfone: o canal DESTE controle, e o mudo do firmware.

    Decisão dela, 04/09/2026: *"o botão é pra ligar o microfone e ele ser
    ouvido no canal específico dele"* — e, ao meio-dia:

        *"o botão fisico do mic se ligado no  # noqa-acento: citação dela
        microfone ele fica ligado tambem.  # noqa-acento: citação dela
        indepente se nativo ou  # noqa-acento: citação dela
    virtual"*.  # noqa-acento: citação literal dela

    ``True`` só quando as DUAS metades aconteceram. Quem precisa saber QUAL
    faltou — e é quem pinta o cartão — chama
    :func:`mic_canal_set_detalhado` e lê a frase com
    :func:`frase_do_ato_do_microfone`.
    """
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
    return _corpo_do_daemon("mic.canal.set", payload)


def sensor_set_detalhado(
    *,
    giroscopio: bool | None = None,
    acelerometro: bool | None = None,
    uniq: str | None = None,
) -> dict[str, Any] | None:
    """``sensor.set`` com a RESPOSTA inteira do daemon — o giro e o accel.

    SENSOR-DE-VERDADE-01, decisão dela: *"ele tem que funcionar de verdade.
    ambos independente do modo e da mascara."*
    <!-- noqa-acento: citação literal dela -->

    Campo ``None`` **não é enviado** — e por isso não mexe naquele sensor. É o
    mesmo contrato de ``rumble_motores_set``, e a razão é a mesma: desligar o
    giroscópio não pode ligar o acelerômetro de volta pelas costas dela.

    O corpo traz ``status``, ``giroscopio``/``acelerometro`` (o que passou a
    valer), ``gravado`` (foi ao perfil?), ``alcance`` (``report`` e ``evdev``,
    separados) e ``ressalva`` — a frase para a tela quando o interruptor pegou
    só pela metade. ``None`` = daemon não respondeu.

    **A ressalva não é decoração.** Medido em 04/09/2026: em Modo Nativo o
    jogo lê o movimento pelo ``hidraw`` do controle físico, onde o daemon não
    escreve — o interruptor esconde o sensor de quem lê evdev e não de quem lê
    hidraw. Uma ponte que devolvesse só ``True`` faria a tela dizer "aplicado"
    sobre um giro que continua chegando ao jogo.
    """
    payload: dict[str, Any] = {}
    if giroscopio is not None:
        payload["giroscopio"] = bool(giroscopio)
    if acelerometro is not None:
        payload["acelerometro"] = bool(acelerometro)
    if not payload:
        return None
    if uniq:
        payload["uniq"] = uniq
    return _corpo_do_daemon("sensor.set", payload)


def frase_do_interruptor_de_sensor(corpo: Any) -> str | None:
    """A frase que vai para o CARTÃO daquele controle — ``None`` se deu certo.

    Irmã de :func:`frase_do_ato_do_microfone`, e pelo mesmo motivo: o corpo do
    daemon tem tudo, e é a TELA que precisa de uma linha. Quem a desenha é a
    aba 02 (`interface/pacotes/a02_controles.py`), que não é desta frente — ver
    a dívida declarada na entrega da ONDA1-D3.

    ``None`` significa **nada a dizer**: o interruptor pegou inteiro, ou ela
    LIGOU o sensor (ligar nunca é parcial — o dado volta a fluir por todos os
    caminhos de uma vez).
    """
    if not isinstance(corpo, dict):
        return "o daemon não respondeu ao interruptor do sensor"
    status = corpo.get("status")
    if status != "ok":
        motivo = corpo.get("motivo")
        return str(motivo) if motivo else f"o daemon recusou: {status}"
    ressalva = corpo.get("ressalva")
    return str(ressalva) if ressalva else None


def sensor_set(
    *,
    giroscopio: bool | None = None,
    acelerometro: bool | None = None,
    uniq: str | None = None,
) -> bool:
    """``sensor.set`` estreitado a ``bool`` — só para quem não vai ler a frase.

    ``True`` = o daemon aceitou. **Não** significa "o jogo parou de ver": para
    isso é o ``alcance`` de :func:`sensor_set_detalhado`, e é por isso que esta
    função existe estreita e documentada em vez de ser a porta principal.
    """
    corpo = sensor_set_detalhado(
        giroscopio=giroscopio, acelerometro=acelerometro, uniq=uniq
    )
    return isinstance(corpo, dict) and corpo.get("status") == "ok"


def frase_do_ato_do_microfone(corpo: Any) -> str | None:
    """A frase que vai para o CARTÃO daquele controle — ``None`` se deu certo.

    Ela existe porque o ato falha pela METADE, e "não deu" não diz nada a quem
    está com o controle na mão: o canal pode ter sido eleito e o mudo do
    firmware ter ficado represado (Modo Nativo), ou o firmware ter obedecido
    sem haver canal nenhum para onde apontar (o rádio sem a ponte).

    ``None`` também quando o daemon não respondeu: aí a frase é a de daemon
    parado, que já é de quem chama, e inventar outra aqui daria duas frases
    para o mesmo silêncio.
    """
    if not isinstance(corpo, dict):
        return None
    if corpo.get("status") == "ok":
        return None
    motivo = corpo.get("motivo")
    return motivo if isinstance(motivo, str) and motivo else None


def mic_volume_set(volume: int, uniq: str | None = None) -> bool:
    """Volume da CAPTURA do microfone, no sistema (MIC-VOLUME-01, 16/08/2026).

    Pedido dela: *"um slicer de microfone pra definir o volume do microfone
    real (independente de saber se tá via bt ou via cabo), o app deve ser
    inteligente pra saber qual caminho usar"*.

    **Não confundir com `mic_set`.** São camadas diferentes e não se substituem:

    ===============  ====================================================
    `mic_set`        o MUDO no firmware do controle (camada 3). É o único
                     que apaga a luz vermelha do microfone, e enquanto
                     vigorar o botão físico deixa de valer.
    `mic_volume_set` o GANHO da fonte de captura no PipeWire (camada 1).
                     Não toca no firmware, não tira o botão físico, e não
                     apaga luz nenhuma.
    ===============  ====================================================

    **Por que ele é universal.** O DualSense não expõe registrador de ganho de
    microfone — nem no cabo nem no rádio. O que existe nos dois casos é uma
    FONTE no sistema, e é nela que este pedido mexe. Por isso o mesmo controle
    deslizante vale nos dois transportes sem que ela precise saber qual está
    valendo, que era exatamente o pedido.

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
    """``mic.volume.set`` que entrega a RESPOSTA do daemon (ELO-MUDO-01, 23/08).

    Mesmo pedido do :func:`mic_volume_set`; o que muda é o que volta. O corpo
    traz ``status`` (``"ok"``, ``"erro"`` ou ``"sem_fonte"``), ``fonte``,
    ``volume`` (a LEITURA de volta, não o que mandamos) e ``por_uniq`` — leia o
    último com :func:`alvo_honrado`. ``None`` = daemon não respondeu.

    As três coisas que o ``bool`` apagava, medidas na bancada em 23/08:

    1. ``sem_fonte`` chegava como o mesmo ``False`` de daemon offline — e a
       promessa escrita em :func:`mic_volume_set` (*"o controle deslizante fica
       insensível com a dica dizendo por quê"*) não tinha por onde se cumprir,
       porque nenhum código de janela recebia a palavra ``sem_fonte``;
    2. o volume LIDO de volta não chegava, então a janela só podia mostrar o
       número que ela mesma mandou;
    3. ``por_uniq: False`` era indistinguível de ``True`` — o gesto que caiu na
       rota global (o microfone de OUTRA pessoa) voltava ``True`` e era gravado
       no rascunho como se o controle escolhido tivesse sido honrado.

    **O que fazer com a palavra ``sem_fonte`` na tela é desenho, e é dela** —
    esta função só faz a palavra chegar.
    """
    volume = max(0, min(100, int(volume)))
    payload: dict[str, Any] = {"volume": volume}
    if uniq:
        payload["uniq"] = uniq
    return _corpo_do_daemon("mic.volume.set", payload)


def speaker_set(
    volume: int | None = None,
    muted: bool | None = None,
    uniq: str | None = None,
    release: bool = False,
    rota: int | None = None,
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
    corpo = speaker_set_detalhado(volume, muted, uniq, release, rota)
    return corpo is not None and corpo.get("status") == "ok"


def speaker_set_detalhado(
    volume: int | None = None,
    muted: bool | None = None,
    uniq: str | None = None,
    release: bool = False,
    rota: int | None = None,
) -> dict[str, Any] | None:
    """``speaker.set`` que entrega a RESPOSTA do daemon (ELO-MUDO-01, 23/08).

    Mesmo pedido e as MESMAS regras do :func:`speaker_set` — inclusive o
    ``ValueError`` de ``release`` com ``volume``/``muted``, que mora aqui porque
    é aqui que o payload se monta. O corpo traz ``status`` (``"ok"`` ou
    ``"sem_controle"``) e ``speaker``, o bloco de posse que só existe depois do
    primeiro pedido. ``None`` = daemon não respondeu.
    """
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
        # SOM-CANAL-01: a rota de SAÍDA (`OUTPUT_PATH_SEL`, byte 7). Ela vai
        # junto do volume porque é o mesmo bloco de posse — e sozinha quando o
        # seletor de canal muda sem mexer no número.
        payload["rota"] = int(rota)
    return _corpo_do_daemon("speaker.set", payload)


# PODA DE 26/08/2026 (BG-07) — cinco pontes públicas sem NENHUM chamador em
# `src/` foram apagadas daqui, e o `__all__` abaixo é o registro do que ficou:
# `apply_draft`, `rumble_policy_set`, `rumble_policy_set_detalhado`,
# `trigger_reset` e `mouse_emulation_set`. As quatro primeiras deixaram a
# medição delas na docstring da irmã que ficou. A quinta não tem irmã, e a
# medição dela é esta: a aba Mouse fala `mouse.emulation.set` por `call_async`
# DIRETO, em DOIS pontos (`app/actions/mouse_actions.py:462` — o interruptor —
# e `:560` — o controle deslizante), sem passar por invólucro. A rota
# speed-only do daemon (BUG-MOUSE-GUI-SYNC-01 A4, que atualiza só as
# velocidades omitindo `enabled` do payload) continua viva: é o `:560`. E a
# ponte podada não podia ser usada nem se alguém quisesse — ela não sabia
# mandar `origin: "manual"`, o campo que a ORIGEM-QUE-MENTE-01 exige dos dois
# pontos vivos. Duas pontes para o mesmo método IPC é como uma delas apodrece
# sem ninguém ver, e era esta que estava apodrecendo.
#
# A trava que segurava a poda desde 12/08/2026 — "a assinatura pode estar
# sendo importada pelo applet do COSMIC" — CAIU, e está medida em 26/08/2026:
# o applet mora em `packaging/cosmic-applet/src/{app,ipc,main}.rs`, fala
# JSON-RPC por socket Unix (`ipc.rs:3`: "Espelha `cli/ipc_client.py`"), e
# `grep` pelos cinco nomes ali devolve ZERO. Um processo Rust não importa
# função Python; o que ele espelha é o PROTOCOLO, e nenhum método IPC foi
# tocado por esta poda.

__all__ = [
    "PROFILE_SWITCH_TIMEOUT_S",
    "active_profile_name",
    "alvo_honrado",
    "aplicacao_confirmada",
    "apply_draft_detalhado",
    "autoswitch_lock_set",
    "call_async",
    "daemon_state_full",
    "daemon_status_basic",
    "destinos_da_aplicacao",
    "frase_do_ato_do_microfone",
    "frase_do_interruptor_de_sensor",
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
    "sensor_set",
    "sensor_set_detalhado",
    "speaker_set",
    "speaker_set_detalhado",
    "trigger_reset_detalhado",
    "trigger_set",
    "trigger_set_checked",
    "trigger_set_detalhado",
]

# "O segredo de ter sucesso é saber o que descartar." — Charlie Munger
