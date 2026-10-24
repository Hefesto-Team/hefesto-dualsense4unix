"""Subsystem de poll loop — leitura de estado do controle e publicação de eventos."""
from __future__ import annotations

from typing import NamedTuple

from hefesto_dualsense4unix.integrations.bluez_dbus import observar_o_gesto_da_vaga
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

BATTERY_DEBOUNCE_SEC = 5.0
BATTERY_MIN_INTERVAL_SEC = 0.1
BATTERY_DELTA_THRESHOLD_PCT = 1


class BatteryDebouncer:
    """Debounce de eventos de bateria (V2-17 + ADR-008)."""

    def __init__(self) -> None:
        self.last_emitted_value: int | None = None
        self.last_emit_at: float = 0.0

    def should_emit(self, value: int, now: float) -> bool:
        if self.last_emitted_value is None:
            return True
        interval = now - self.last_emit_at
        if interval < BATTERY_MIN_INTERVAL_SEC:
            return False
        delta = abs(value - self.last_emitted_value)
        return delta >= BATTERY_DELTA_THRESHOLD_PCT or interval >= BATTERY_DEBOUNCE_SEC

    def mark_emitted(self, value: int, now: float) -> None:
        self.last_emitted_value = value
        self.last_emit_at = now


def evdev_buttons_once(daemon: object) -> frozenset[str]:
    """Snapshot dos botões físicos via evdev — chamado 1x por tick no poll loop.

    Retorna frozenset vazio se evdev não está disponível ou falha.
    Exceções são logadas em debug para não poluir logs de produção.
    """
    evdev = getattr(getattr(daemon, "controller", None), "_evdev", None)
    if evdev is None or not evdev.is_available():
        return frozenset()
    try:
        return frozenset(evdev.snapshot().buttons_pressed)
    except Exception as exc:
        logger.debug("evdev_snapshot_falhou", err=str(exc))
        return frozenset()


def observar_os_atalhos(
    daemon: object,
    buttons_pressed: frozenset[str],
    *,
    now: float,
    gatilhos_do_posto: tuple[int, int] | None = None,
) -> str | None:
    """Entrega ao `HotkeyManager` os botões de CADA controle na mesa.

    Chamado pelo `_poll_loop` a cada tique, no lugar em que ele chamava o
    `observe` com os botões do primário. Devolve o nome do primeiro gesto que
    disparou neste tique (ou None), e None sem gerente de atalhos.

    **O PS E AS COMBINAÇÕES VALEM EM QUALQUER UM DOS QUATRO.** O PS + R3 é
    decisão de 27/09 (resposta 11, `D-2709-O-PS-R3-EM-QUALQUER-CONTROLE`);
    o item 5 da O-MODO-XBOX-NAO-E-QUEDA-02 estende a regra ao PS sozinho e às
    outras combinações. Medido na sessão do usuário (G0 e G9 de 27/09): só o «primário» era
    lido, e o PS do branco, que acende o «1», não abria a Steam. Cada controle
    é lido com o aperto DELE (`observe(..., de=<MAC>)`), e o ato do gesto
    pergunta de quem ele é (:func:`quem_segura_os_atalhos`).

    `buttons_pressed` continua sendo o que o laço leu do leitor do primário
    (`evdev_buttons_once`) e mandou ao vpad do P1 — esta função não o muda
    para ninguém além dos atalhos.
    """
    gerente = getattr(daemon, "_hotkey_manager", None)
    if gerente is None:
        return None
    maos = botoes_de_cada_controle(daemon, buttons_pressed)
    observar_o_gesto_da_vaga(maos)
    gatilhos = _gatilhos_dos_gestos(daemon, gerente, maos, gatilhos_do_posto)
    resultado: str | None = None
    for quem, botoes in maos.items():
        pressao = gatilhos.get(quem)
        if pressao is None:
            disparou: str | None = gerente.observe(botoes, now=now, de=quem)
        else:
            disparou = gerente.observe(botoes, now=now, de=quem, gatilhos=pressao)
        if resultado is None:
            resultado = disparou
    soltar = getattr(gerente, "soltar_quem_saiu", None)
    if callable(soltar):
        soltar(maos)
    return resultado


def _gatilhos_dos_gestos(
    daemon: object,
    gerente: object,
    maos: dict[str | None, frozenset[str]],
    do_posto: tuple[int, int] | None,
) -> dict[str | None, tuple[int, int]]:
    """A pressão `(L2, R2)` de cada controle lido, só quando há gesto dos acessórios a medir.

    O primeiro controle lido é o dono do posto (a pressão vem do `state` do laço); os outros, dos
    mesmos leitores que a tabela do jogo usa. Sem modificação de acessórios, é um dicionário vazio.
    """
    valem = getattr(gerente, "gestos_valem_agora", None)
    if not callable(valem) or not valem():
        return {}
    saida: dict[str | None, tuple[int, int]] = {}
    dono = _mac_ou_none(getattr(getattr(daemon, "controller", None), "primary_uniq", None))
    if do_posto is not None:
        saida[dono] = do_posto
    for uniq, (_botoes, l2, r2) in gatilhos_de_cada_controle(daemon).items():
        saida[uniq] = (l2, r2)
    return saida


def botoes_de_cada_controle(
    daemon: object, botoes_do_posto: frozenset[str]
) -> dict[str | None, frozenset[str]]:
    """Os botões que os atalhos do PS leem neste tique, por controle: `{MAC: botões}`.

    Três fontes, e cada controle lê de uma só — a mesma ordem do `inputs` do
    `state_full` (`_enrich_controllers_per_controller` do IPC), que já resolve a
    pergunta «o que este controle aperta agora» sem ler um nó duas vezes:

    1. **o dono do posto de P1** (`primary_uniq`): `botoes_do_posto`, o que o
       laço leu do leitor do primário. Na vaga do posto (o P1 fora dentro do
       prazo do lugar guardado) ele não tem nó e a mão vem vazia;
    2. **quem está sentado no co-op**: o leitor DELE
       (`CoopManager.live_snapshots`). O co-op segura o nó com `EVIOCGRAB`, e
       um leitor passivo ali não recebe evento nenhum. Quem renasce (sentado,
       com o grab pendente, fora dos `live_snapshots`) fica com a mão vazia
       até o leitor abrir o device;
    3. **qualquer outro controle na mesa** — o co-op desmontado: mouse e
       teclado, o co-op desligado, a suspensão pelo Steam Input: o leitor
       PASSIVO do `SensorHub` (`entradas`, STATUS-04), sem grab. A primeira
       pergunta devolve None (o leitor nasce na volta seguinte da thread do
       hub), e a mão vem vazia nesse tique.

    O MODO NATIVO NÃO PASSA POR AQUI: o `_poll_loop` congela o tique antes
    dos atalhos (`input_ready` com `not self._native_mode`), para o P1 e para
    os outros — é o beco sem saída que o `build_next_bridge_callback` descreve.

    A chave é o MAC; a do dono do posto é None quando o backend não tem MAC
    (o `FakeController`). Nunca levanta: uma fonte que falha deixa a mão
    daquele controle vazia neste tique, e o laço segue.
    """
    controller = getattr(daemon, "controller", None)
    dono = _mac_ou_none(getattr(controller, "primary_uniq", None))
    maos: dict[str | None, frozenset[str]] = {dono: botoes_do_posto}
    vivos = _botoes_do_coop(daemon)
    outros = [u for u in dict.fromkeys([*_na_mesa(controller), *vivos]) if u != dono]
    if not outros:
        return maos
    sem_leitor = [u for u in outros if u not in vivos]
    sentados = _sentados_no_coop(daemon) if sem_leitor else frozenset()
    passivos = [u for u in sem_leitor if u not in sentados]
    entradas = _entradas_do_hub(daemon) if passivos else None
    for uniq in outros:
        if uniq in vivos:
            maos[uniq] = vivos[uniq]
        elif uniq in sentados or entradas is None:
            maos[uniq] = frozenset()
        else:
            maos[uniq] = _botoes_passivos(entradas, uniq)
    return maos


class EntradasDoControle(NamedTuple):
    """O que um controle faz agora: os botões, os analógicos e os gatilhos, de 0 a 255."""

    botoes: frozenset[str]
    lx: int
    ly: int
    rx: int
    ry: int
    l2: int
    r2: int


#: O controle parado, ou sem leitura neste tique: nada apertado, os analógicos no centro.
PARADO = EntradasDoControle(frozenset(), 128, 128, 128, 128, 0, 0)


def entradas_de_cada_controle(daemon: object) -> dict[str, EntradasDoControle]:
    """O que os OUTROS controles fazem agora: `{MAC: EntradasDoControle}`.

    A tabela que age junto com o jogo (`subsystems/mouse.TabelaNoJogo`) precisa do
    gatilho ANALÓGICO de cada controle, e o tópico `entradas` das extensões, dos
    analógicos também; :func:`botoes_de_cada_controle` só entrega o botão digital.
    As fontes são as mesmas, na mesma ordem — o co-op (`live_snapshots`) e o
    leitor passivo do `SensorHub` —, e o dono do posto de P1 fica de fora: o laço
    já tem o `state` dele. Quem não tem leitura neste tique fica :data:`PARADO`.
    Nunca levanta.
    """
    controller = getattr(daemon, "controller", None)
    dono = _mac_ou_none(getattr(controller, "primary_uniq", None))
    vivos = _snapshots_do_coop(daemon)
    outros = [u for u in dict.fromkeys([*_na_mesa(controller), *vivos]) if u != dono]
    if not outros:
        return {}
    sem_leitor = [u for u in outros if u not in vivos]
    sentados = _sentados_no_coop(daemon) if sem_leitor else frozenset()
    passivos = [u for u in sem_leitor if u not in sentados]
    entradas = _entradas_do_hub(daemon) if passivos else None
    maos: dict[str, EntradasDoControle] = {}
    for uniq in outros:
        if uniq in vivos:
            snap = vivos[uniq]
            maos[uniq] = _entradas_de(
                getattr(snap, "buttons_pressed", ()),
                {campo: getattr(snap, campo, None) for campo in _CAMPOS_DAS_ENTRADAS},
            )
        elif uniq in sentados or entradas is None:
            maos[uniq] = PARADO
        else:
            maos[uniq] = _entradas_passivas(entradas, uniq)
    return maos


def gatilhos_de_cada_controle(
    daemon: object,
) -> dict[str, tuple[frozenset[str], int, int]]:
    """O que os OUTROS controles apertam agora: `{MAC: (botões, L2 0-255, R2 0-255)}`.

    A parte das :func:`entradas_de_cada_controle` que a tabela que age junto com o
    jogo lê. Nunca levanta.
    """
    return {u: (e.botoes, e.l2, e.r2) for u, e in entradas_de_cada_controle(daemon).items()}


#: Os campos do leitor (o snapshot do co-op e a leitura do hub), na ordem de `EntradasDoControle`.
_CAMPOS_DAS_ENTRADAS = ("lx", "ly", "rx", "ry", "l2_raw", "r2_raw")


def _como_inteiro(valor: object, padrao: int = 0) -> int:
    if not isinstance(valor, int) or isinstance(valor, bool):
        return padrao
    return min(255, max(0, valor))


def _entradas_de(botoes: object, campos: dict[str, object]) -> EntradasDoControle:
    conjunto = (
        frozenset(str(b) for b in botoes)
        if isinstance(botoes, (list, tuple, set, frozenset)) else frozenset()
    )
    return EntradasDoControle(conjunto, *(
        _como_inteiro(campos.get(campo), padrao)
        for campo, padrao in zip(_CAMPOS_DAS_ENTRADAS, PARADO[1:], strict=True)
    ))


def _entradas_passivas(entradas: object, uniq: str) -> EntradasDoControle:
    """Botões, analógicos e gatilhos de `uniq` pelo leitor passivo do hub; parado sem leitura."""
    if not callable(entradas):
        return PARADO
    try:
        leitura = entradas(uniq)
    except Exception as exc:
        logger.debug("leitura_passiva_das_entradas_falhou", identity=uniq, err=str(exc))
        return PARADO
    if not isinstance(leitura, dict):
        return PARADO
    return _entradas_de(leitura.get("buttons"), leitura)


def quem_segura_os_atalhos(daemon: object) -> str | None:
    """O MAC de quem fez o gesto em curso — o DONO ÚNICO da pergunta «de quem é o gesto»."""
    from hefesto_dualsense4unix.integrations.hotkey_daemon import quem_faz_o_gesto

    feito_por = quem_faz_o_gesto()
    if feito_por is not None:
        return feito_por
    if _o_posto_esta_vago(daemon):
        return _o_proximo_da_fila(daemon)
    return _mac_ou_none(getattr(getattr(daemon, "controller", None), "primary_uniq", None))


def _mac_ou_none(valor: object) -> str | None:
    return valor if isinstance(valor, str) and valor else None


def _o_posto_esta_vago(daemon: object) -> bool:
    """O posto de P1 está VAGO agora? A pergunta é a do backend (`_posto_vago_de`)."""
    controller = getattr(daemon, "controller", None)
    return isinstance(getattr(controller, "_posto_vago_de", None), str)


def _na_mesa(controller: object) -> list[str]:
    """Os MACs dos controles conectados agora (`alvos_conectados`, sem I/O)."""
    alvos = getattr(controller, "alvos_conectados", None)
    if not callable(alvos):
        return []
    try:
        conectados = alvos()
    except Exception as exc:
        logger.debug("atalhos_sem_a_mesa", err=str(exc))
        return []
    if not isinstance(conectados, dict):
        return []
    return [u for u in conectados.values() if isinstance(u, str) and u]


def _snapshots_do_coop(daemon: object) -> dict[str, object]:
    """`{MAC: snapshot}` dos jogadores do co-op com o vpad de pé (`live_snapshots`)."""
    coop = getattr(daemon, "_coop_manager", None)
    vivos_de = getattr(coop, "live_snapshots", None)
    if not callable(vivos_de):
        return {}
    try:
        vivos = vivos_de()
        if not isinstance(vivos, dict):
            return {}
        return {mac: snap for mac, snap in vivos.items() if isinstance(mac, str) and mac}
    except Exception as exc:
        logger.debug("atalhos_sem_o_coop", err=str(exc))
        return {}


def _botoes_do_coop(daemon: object) -> dict[str, frozenset[str]]:
    """`{MAC: botões}` dos jogadores do co-op com o vpad de pé (`live_snapshots`)."""
    return {
        mac: frozenset(getattr(snap, "buttons_pressed", ()) or ())
        for mac, snap in _snapshots_do_coop(daemon).items()
    }


def _sentados_no_coop(daemon: object) -> frozenset[str]:
    """Quem o co-op numera — sentado, com o vpad de pé ou renascendo (`numeros_de_jogador`)."""
    coop = getattr(daemon, "_coop_manager", None)
    numeros_de = getattr(coop, "numeros_de_jogador", None)
    if not callable(numeros_de):
        return frozenset()
    try:
        numeros = numeros_de()
    except Exception as exc:
        logger.debug("atalhos_sem_os_numeros", err=str(exc))
        return frozenset()
    if not isinstance(numeros, dict):
        return frozenset()
    return frozenset(m for m in numeros if isinstance(m, str))


def _entradas_do_hub(daemon: object) -> object | None:
    """O `SensorHub.entradas` da sessão (o MESMO do IPC), ou None sem hub."""
    garantir = getattr(daemon, "_garantir_sensor_hub", None)
    if not callable(garantir):
        return None
    try:
        entradas = getattr(garantir(), "entradas", None)
    except Exception as exc:
        logger.debug("atalhos_sem_o_hub", err=str(exc))
        return None
    return entradas if callable(entradas) else None


def _botoes_passivos(entradas: object, uniq: str) -> frozenset[str]:
    """Os botões de `uniq` pelo leitor passivo do hub; vazio sem leitura."""
    if not callable(entradas):
        return frozenset()
    try:
        leitura = entradas(uniq)
    except Exception as exc:
        logger.debug("atalhos_leitura_passiva_falhou", identity=uniq, err=str(exc))
        return frozenset()
    if not isinstance(leitura, dict):
        return frozenset()
    botoes = leitura.get("buttons")
    if not isinstance(botoes, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(str(b) for b in botoes)


def _o_proximo_da_fila(daemon: object) -> str | None:
    """Na vaga do posto de P1: o MAC do próximo da fila na mesa. Fora dela, None."""
    if not _o_posto_esta_vago(daemon):
        return None
    coop = getattr(daemon, "_coop_manager", None)
    if coop is None:
        return None
    try:
        dono = getattr(getattr(daemon, "controller", None), "primary_uniq", None)
        # Quem caiu e espera no vpad guarda o número, mas não tem mão para segurar.
        esperam = getattr(coop, "quem_espera_no_lugar", None)
        fora = esperam() if callable(esperam) else frozenset()
        sentados = {
            mac: numero
            for mac, numero in coop.numeros_de_jogador().items()
            if mac != dono and mac not in fora
        }
        if not sentados:
            return None
        return _mac_ou_none(min(sentados, key=sentados.__getitem__))
    except Exception as exc:
        logger.debug("atalhos_na_vaga_sem_fila", err=str(exc))
        return None


__all__ = [
    "BATTERY_DEBOUNCE_SEC",
    "BATTERY_DELTA_THRESHOLD_PCT",
    "BATTERY_MIN_INTERVAL_SEC",
    "PARADO",
    "BatteryDebouncer",
    "EntradasDoControle",
    "botoes_de_cada_controle",
    "entradas_de_cada_controle",
    "evdev_buttons_once",
    "gatilhos_de_cada_controle",
    "observar_os_atalhos",
    "quem_segura_os_atalhos",
]
