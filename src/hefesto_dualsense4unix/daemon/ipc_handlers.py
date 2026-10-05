"""Handlers JSON-RPC do `IpcServer` (AUDIT-FINDING-IPC-SERVER-SPLIT-01).

Separado de `ipc_server.py` para manter o dispatcher de IO enxuto (<500 LOC)
e concentrar a lógica de cada método em um único lugar. Exposto como mixin
`IpcHandlersMixin` — `IpcServer` herda dele e o dispatcher continua
registrando os handlers em `__post_init__` via `self._handle_*`.

Helper `DraftApplier` extrai as 4 seções do `profile.apply_draft` (leds,
triggers, rumble, mouse) em métodos isolados, reduzindo o tamanho do handler
orquestrador para muito abaixo do limite de 100 LOC por método.
"""
from __future__ import annotations

import asyncio
import contextlib
import inspect
import json
import os
import time
from collections.abc import Callable
from dataclasses import asdict, replace
from typing import TYPE_CHECKING, Any, Literal, cast

from hefesto_dualsense4unix.core import escritor_cru as _escritor_cru
from hefesto_dualsense4unix.core.trigger_effects import build_from_name
from hefesto_dualsense4unix.core.trigger_effects import off as trigger_off
from hefesto_dualsense4unix.daemon.ipc_draft_applier import DraftApplier
from hefesto_dualsense4unix.daemon.ipc_rumble_policy import (
    apply_rumble_policy,
    uniq_do_alvo_de_output,
)
from hefesto_dualsense4unix.daemon.subsystems import recado_do_microfone
from hefesto_dualsense4unix.integrations import sinal_da_barra as _sinal_da_barra
from hefesto_dualsense4unix.integrations.no_do_vpad import (
    NO_DESCONHECIDO,
    no_ainda_vale,
    resolver_no_do_vpad,
)
from hefesto_dualsense4unix.profiles.schema import (
    MOTOR_PCT_PADRAO,
    RUMBLE_CUSTOM_MULT_MAX,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger


def _config_que_viaja(cfg: object) -> dict[str, Any]:
    """`asdict(cfg)` sem os campos que não atravessam JSON.

    DEFEITO VIVO, achado em 03/09/2026 lendo o journal do daemon dela:

        ipc_client_error  err='Object of type function is not JSON serializable'

    `daemon.reload` FAZIA O TRABALHO — `reload_config` roda, a config nova
    vale — e a resposta NUNCA CHEGAVA: o `asdict` do `DaemonConfig` arrasta o
    `orcamento_da_mesa`, que em runtime é uma `lambda` que o daemon injeta, e
    `json.dumps` explode em cima dela. O cliente fica pendurado até o timeout, e
    o daemon cospe um traceback de 40 linhas no journal.

    **O PIOR DESFECHO NÃO É O ERRO — É O TRABALHO FEITO SEM RESPOSTA.** Quem
    chama não sabe se recarregou; quem tenta de novo recarrega duas vezes.

    POR QUE NÃO SE LISTA O CAMPO A EXCLUIR: uma lista de nomes envelheceria no
    dia em que o `DaemonConfig` ganhasse o oitavo applier — e envelheceria em
    silêncio, porque só o journal acusaria. Aqui se PERGUNTA ao `json`: o que
    ele não sabe serializar não viaja, e o nome do campo sai no lugar com a
    marca, para quem lê a resposta saber que algo ficou de fora e o quê.
    """
    fora: dict[str, Any] = {}
    for chave, valor in asdict(cfg).items():  # type: ignore[call-overload]
        try:
            json.dumps(valor)
        except (TypeError, ValueError):
            fora[chave] = "<não viaja por IPC>"
            continue
        fora[chave] = valor
    return fora


def _caminho_publicado(daemon: object) -> str | None:
    """O MODO de pé, na forma que a tela lê — MODO-DE-CONEXAO-01, 13/09/2026.

    O escolhido (`config.gamepad_caminho`) ou, sem escolha, o de fábrica
    (`dualsense`, CAMINHO-CONTAGIO-01). ``None`` só sem config legível (um
    daemon dublado sem nada).

    NOTA DATADA — 27/09/2026 (O-MODO-XBOX-NAO-E-QUEDA-02): sem escolha, isto
    publicava o caminho que sai da máscara do pad do P1. Com o cartão do P1 em
    Xbox e os outros três em DualSense no `uhid`, o chip de modo dizia «Xbox»
    para a mesa inteira. O modo, a máscara e a conexão são três eixos: a
    máscara de cada controle sai em `por_aparelho`, e o modo não se deduz dela.
    """
    from hefesto_dualsense4unix.integrations.virtual_pad import (
        CAMINHO_DUALSENSE,
        normalizar_caminho,
    )

    cfg = getattr(daemon, "config", None)
    if cfg is None:
        return None
    return normalizar_caminho(getattr(cfg, "gamepad_caminho", None)) or CAMINHO_DUALSENSE


def _mascaras_por_aparelho(handlers: object) -> dict[str, str]:
    """`{uniq: máscara efetiva}` para cada controle conectado agora.

    MASCARA-NA-TELA-01, 03/09/2026 — o pedido é dela: *"é uma máscara por
    controle. Mesmo caso do anterior."*

    O REGISTRO JÁ EXISTIA. `external_mask.mascara_efetiva` decide desde
    15/08/2026 (MÁSCARA-POR-JOGADOR-01, decisão dela) e é consultada na criação
    de todo gamepad virtual; os três degraus do daemon que faltavam —
    `virtual_pad`, `coop` e `gamepad` — fecharam em 29/08. **O que nunca
    chegou foi a TELA:** `mesa_viva` lia o `flavor` da SESSÃO e escrevia o
    mesmo valor nos quatro cartões, então a escolha por aparelho vivia no disco
    e não aparecia em lugar nenhum.

    A HERANÇA NÃO SE REESCREVE AQUI: quem não tem escolha registrada recebe a
    máscara da sessão, e é `mascara_efetiva` quem diz isso. Repetir a regra
    neste arquivo faria duas verdades sobre o mesmo fato — e a daqui
    envelheceria no dia em que a herança mudasse.

    NUNCA LEVANTA. Um registro que não abre não pode derrubar o `state_full`
    inteiro: sem ele a tela mostra a máscara da sessão, que é o comportamento
    de antes deste campo existir.
    """
    fora: dict[str, str] = {}
    try:
        from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
            mascara_efetiva,
        )

        daemon_cfg = getattr(getattr(handlers, "daemon", None), "config", None)
        da_sessao = str(getattr(daemon_cfg, "gamepad_flavor", "dualsense"))
        describe = getattr(getattr(handlers, "controller", None),
                           "describe_controllers", None)
        if not callable(describe):
            return fora
        for entrada in describe() or ():
            if not isinstance(entrada, dict) or not entrada.get("connected"):
                continue
            uniq = str(entrada.get("uniq") or "")
            if not uniq:
                continue
            fora[uniq] = str(mascara_efetiva(uniq, da_sessao))
    except Exception:  # pragma: no cover - defesa; ver a docstring
        return fora
    return fora


if TYPE_CHECKING:
    from hefesto_dualsense4unix.core.controller import IController
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol, GravaOModo
    from hefesto_dualsense4unix.daemon.state_store import StateStore


def _porta_que_grava(origem: str) -> GravaOModo:
    """A porta que o setter do modo recebe: ``"ipc"`` para o pedido à mão."""
    return "ipc" if origem == "manual" else False


def origem_do_pedido(params: dict[str, Any] | None) -> Literal["manual", "profile"]:
    """A origem declarada pelo cliente. Silêncio = automático, nunca "manual"."""
    bruto = (params or {}).get("origin")
    if bruto is None:
        return "profile"
    if bruto not in ("manual", "profile"):
        raise ValueError("'origin' precisa ser 'manual' ou 'profile'")
    return cast('Literal["manual", "profile"]', bruto)


logger = get_logger(__name__)


def _as_str_or_none(value: Any) -> str | None:
    """Normaliza campos informativos do state_full para str | None.

    Blindagem de serialização: com daemon/controller dublados em teste
    (MagicMock), um getattr devolve um mock — que estoura no json.dumps do
    servidor. Só strings reais passam; o resto vira None.
    """
    return value if isinstance(value, str) else None


#: `state_full`. O tick da GUI é 10 Hz (`LIVE_POLL_INTERVAL_MS=100`) e
_LIGHTBAR_READ_TTL_SEC = 1.0

_IDENTITY_RENUMBER_LOCK_TIMEOUT_SEC = 5.0

COOP_SEMPRE_LIGADO_MOTIVO = (
    "o co-op local é sempre ligado: cada controle conectado é um jogador. "
    "Para um controle de reserva, deixe-o desconectado."
)


def _pontes_confirmadas_seguro() -> dict[str, Any]:
    """As pontes confirmadas, e NUNCA uma exceção.

    O `state_full` é lido pela janela a cada tique; uma leitura de disco que
    levante aqui apagaria a aba inteira por causa de um perfil malformado. O
    padrão é o dos vizinhos deste arquivo: devolve vazio e segue.
    """
    try:
        from hefesto_dualsense4unix.profiles import manager as _pm

        fn = getattr(_pm, "pontes_confirmadas", None)
        if fn is None:
            return {}
        return dict(fn() or {})
    except Exception:
        return {}


class _RenumberAuthorityChangedError(Exception):
    """F3: um jogo abriu enquanto o renumber esperava os locks — abortar."""


class _NumeroAlvoAusenteError(Exception):
    """PLAYER-01: pediram um número para um controle que não está na mesa."""


class _NumeroForaDaMesaError(Exception):
    """PLAYER-01: pediram um número maior do que a quantidade de presentes.

    Carrega o teto real para a resposta poder dizê-lo (a janela pode ter
    desenhado quatro botões um instante antes de um controle cair). Vira
    ``{"ok": False, "reason": "numero_fora_da_mesa", "max": N}``.
    """

    def __init__(self, maximo: int) -> None:
        super().__init__(f"numero fora da mesa (max={maximo})")
        self.maximo = maximo


#: `state_full` — leitura de arquivo, mesma justificativa do cache acima.
_WRAPPER_MARKER_TTL_SEC = 2.0

#: BG-02 (25/08/2026): TTL (s) das pontes confirmadas NO TIQUE do `state_full`.
#: chama `load_all_profiles()`, que varre `profiles_dir()` e abre CADA `.json`
#: sob `FileLock`. Sem teto, publicar o carimbo no `state_full` significaria a
_PONTES_CONFIRMADAS_TTL_SEC = 5.0


# Medido na máquina dela em 09/08: dois DualSense ligados e pareados, e a

_HID_DEVICES_DIR = "/sys/bus/hid/devices"

_HID_ORFAO_BUS = "0005"

_HID_ORFAO_VID = "054C"

#: TTL (s) da varredura do sysfs no `state_full`. O tick da GUI é 10 Hz e este
_HID_ORFAOS_TTL_SEC = 2.0

_NO_DO_VPAD_TTL_SEC = 2.0


def _e_dualsense_por_bluetooth(id_do_device: str) -> bool:
    """O nome do diretório é ``BUS:VID:PID.INSTANCIA`` — ex. ``0005:054C:0CE6.000F``."""
    partes = id_do_device.split(":")
    if len(partes) < 3:
        return False
    return partes[0] == _HID_ORFAO_BUS and partes[1].upper() == _HID_ORFAO_VID


def dualsense_sem_driver(devices_dir: str | None = None) -> list[str]:
    """Os DualSense presentes no sistema e SEM driver — a lista de ids do sysfs.

    O critério é o do `bt_rebind_orphans.sh`, e é cirúrgico: **órfão é o que
    NÃO tem o symlink `driver`**. Um controle que perdeu a probe fica em
    `/sys/bus/hid/devices` sem `driver`, e por isso sem hidraw, sem input, sem
    LED e sem bateria — invisível para todo o resto do produto.

    ``devices_dir=None`` resolve `_HID_DEVICES_DIR` **na hora da chamada**, e
    não no `def`: assim a constante do módulo continua sendo o único lugar
    onde o caminho está escrito, e a suíte a troca por um diretório temporário
    sem precisar mexer no default da função.

    Devolve lista vazia quando o diretório não existe ou não pode ser lido:
    este caminho roda dentro do `state_full`, e um `OSError` aqui derrubaria a
    aba Status inteira por causa da linha menos importante dela.
    """
    alvo = devices_dir if devices_dir is not None else _HID_DEVICES_DIR
    try:
        entradas = sorted(os.listdir(alvo))
    except OSError:
        return []
    achados: list[str] = []
    for id_do_device in entradas:
        if os.path.exists(os.path.join(alvo, id_do_device, "driver")):
            continue
        if _e_dualsense_por_bluetooth(id_do_device):
            achados.append(id_do_device)
    return achados


def _visto_ha_s(vp: Any) -> dict[str, float]:
    """O ``visto_ha_s`` do vpad, saneado para o payload de IPC.

    PAINEL-DA-VERDADE-01/E1. O `getattr` com default existe pelo motivo de
    sempre neste arquivo: o vpad pode ser um `uinput` (que não tem hidraw e
    portanto não tem o que carimbar) ou um dublê de teste — e o `state_full`
    nunca pode morrer por causa de um campo de telemetria.

    Os valores são forçados a `float` e os não-numéricos caem fora: o payload
    vira JSON, e um valor exótico aqui derrubaria a serialização inteira por
    causa da linha menos importante dela.
    """
    cru = getattr(vp, "visto_ha_s", None)
    if not isinstance(cru, dict):
        return {}
    return {
        str(k): float(v)
        for k, v in cru.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def _audio_do_jogo_amostra(vp: Any) -> dict[str, int] | None:
    """A amostra de áudio do vpad, saneada para o payload de IPC.

    PARIDADE-SONY-01 — o dado que destranca a E2: quais dos quatro bytes de
    `common[4..7]` o jogo escreveu, e com que valores.

    Mesmas duas defesas do `_visto_ha_s` logo acima, e pelos mesmos motivos: o
    vpad pode ser um `uinput` (sem hidraw, nada a amostrar) ou um dublê de
    teste, e o `state_full` não pode morrer pela linha menos importante dele.
    Valores exóticos caem fora antes de virarem JSON.
    """
    cru = getattr(vp, "audio_do_jogo_amostra", None)
    if not isinstance(cru, dict):
        return None
    return {
        str(k): int(v)
        for k, v in cru.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def _par_de_motores(cru: Any) -> list[int] | None:
    """Um par (weak, strong) do vpad saneado para o payload, ou None.

    RUMBLE-QUE-NAO-SE-SENTE-01. Mesmas defesas dos dois helpers acima: o vpad
    pode ser um `uinput` (que não tem esta propriedade) ou um dublê de teste
    devolvendo `MagicMock`, e o `state_full` não pode morrer por causa de uma
    linha de diagnóstico. Sai como `list` porque JSON não tem tupla — e o
    consumidor (aba Rumble) já trata os dois casos.
    """
    if not isinstance(cru, tuple) or len(cru) != 2:
        return None
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in cru):
        return None
    return [int(cru[0]), int(cru[1])]


def _contador_do_vpad(vp: Any, nome: str) -> int:
    """Um contador cumulativo do vpad, com tipagem ESTRITA; 0 quando não há.

    ORFAOS-QUE-VOLTAM-01. Os contadores vizinhos usam ``int(getattr(...) or 0)``
    e isso basta para eles, porque um número a mais num diagnóstico só engana
    quem está lendo o log. Estes dois não: ``motion_forwards`` decide a FRASE
    do card (é ele que separa "o giroscópio parou" de "nunca começou"), e
    ``int()`` de um `MagicMock` devolve **1** — um vpad dublado, ou um uinput
    que não tem a property, publicaria "já fluiu uma vez" e a tela diria
    "parou" num caminho que nunca existiu.

    A disciplina é a mesma que o `motion_streaming` deste payload já aplica, e
    pelo mesmo motivo escrito lá: um MagicMock nunca vira dado.
    """
    valor = getattr(vp, nome, 0)
    if isinstance(valor, bool) or not isinstance(valor, int):
        return 0
    return valor


def _idade_ou_none(cru: Any) -> float | None:
    """Uma idade em segundos saneada para o payload, ou None."""
    if isinstance(cru, bool) or not isinstance(cru, (int, float)):
        return None
    return float(cru)


def _jack_do_vpad(vp: Any) -> dict[str, bool] | None:
    """O `jack` do vpad (fone/microfone/mudo) saneado para o payload, ou None.

    JACK-QUE-NAO-LIGOU-01. Mesmas defesas dos helpers acima: o vpad pode ser
    um `uinput` (que não tem report 0x01 e portanto não tem byte 53) ou um
    dublê devolvendo `MagicMock`, e o `state_full` não pode morrer por causa
    de uma linha de diagnóstico. `None` = este vpad não fala de jack.
    """
    cru = getattr(vp, "jack", None)
    if not isinstance(cru, dict):
        return None
    return {
        str(k): bool(v) for k, v in cru.items() if isinstance(v, bool)
    }


def _bateria_do_vpad(vp: Any) -> dict[str, Any] | None:
    """A bateria que o vpad ANUNCIA ao jogo, saneada para o payload, ou None.

    BATERIA-QUE-NAO-CHEGOU-01. Mesmas defesas do `_jack_do_vpad`: o vpad pode
    ser um `uinput` (que não tem report 0x01 nem byte 52) ou um dublê de teste
    devolvendo `MagicMock`, e o `state_full` não pode morrer por causa de uma
    linha de diagnóstico.

    `pct` é `None` quando o vpad está em `_STATUS_DESCONHECIDO` — o "não sei"
    honesto do byte, que é diferente de zero e não pode virar zero aqui: zero
    é bateria crítica, e "não sei" é justamente o estado que existe para não
    acender alerta nenhum.
    """
    cru = getattr(vp, "bateria_anunciada", None)
    if not isinstance(cru, tuple) or len(cru) != 2:
        return None
    pct, carregando = cru
    if pct is not None and (isinstance(pct, bool) or not isinstance(pct, int)):
        return None
    if not isinstance(carregando, bool):
        return None
    return {"pct": pct, "carregando": carregando}


def _amostra_de_descarte(cru: Any) -> dict[str, int] | None:
    """(flag0, flag1, flag2, weak, strong) do último descarte, nomeado."""
    if not isinstance(cru, tuple) or len(cru) != 5:
        return None
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in cru):
        return None
    nomes = ("flag0", "flag1", "flag2", "weak", "strong")
    return dict(zip(nomes, (int(v) for v in cru), strict=True))


def _anel_de_vibracao(cru: Any) -> list[dict[str, Any]] | None:
    """Os últimos reports de vibração do vpad, nomeados (QUEM ESCREVEU-01)."""
    if not isinstance(cru, list):
        return None
    nomes = ("ha_s", "flag0", "flag1", "flag2", "weak", "strong", "ramo")
    itens: list[dict[str, Any]] = []
    for entrada in cru:
        if not isinstance(entrada, tuple) or len(entrada) != 7:
            return None
        *numeros, ramo = entrada
        if not isinstance(ramo, str):
            return None
        if not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in numeros
        ):
            return None
        itens.append(dict(zip(nomes, (*numeros, ramo), strict=True)))
    return itens


def _report_estranho(cru: Any) -> dict[str, int] | None:
    """(report_id, tamanho) do último output com envelope que não lemos."""
    if not isinstance(cru, tuple) or len(cru) != 2:
        return None
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in cru):
        return None
    return {"report_id": int(cru[0]), "tamanho": int(cru[1])}


def _norm_uniq(value: Any) -> str | None:
    """MAC 12-hex normalizado de uma key/serial do backend, ou None."""
    if not isinstance(value, str):
        return None
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    normalized = norm_mac(value)
    if normalized is None or len(normalized) != 12:
        return None
    return normalized


def _rgb_or_none(value: Any) -> tuple[int, int, int] | None:
    """Coerção defensiva de um RGB vindo de backend/fake para tupla de ints."""
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        return None
    try:
        return (int(value[0]), int(value[1]), int(value[2]))
    except (TypeError, ValueError):
        return None


def _numero_de_exibicao(entry: dict[str, Any]) -> int:
    """Número "Controle N" de UMA entrada de ``controllers``.

    MESA-CHEIA-11/E1. É a MESMA regra de
    `app/actions/base.numero_do_controle` (slot de sessão; sem slot, posição
    1-based): o slot é a identidade estável, e é o número que a janela imprime
    no título do card. A regra mora lá porque é da interface — e `base.py`
    importa `gi`, que o daemon não pode importar. Para que as duas cópias não
    divirjam existe portão: `test_mesa_cheia_11_a_janela_conta_quatro.py`
    compara as duas sobre o payload REAL de quatro controles, onde `player_slot`
    e `player` são listas DIFERENTES ([4,1,3,2] contra [1,2,3,4]) — foi essa
    medição que mostrou que a escolha do número importa.
    """
    slot = entry.get("player_slot")
    if isinstance(slot, int) and not isinstance(slot, bool):
        return slot
    indice = entry.get("index")
    if isinstance(indice, int) and not isinstance(indice, bool):
        return indice + 1
    return 1


def controles_bt_frageis(controllers: Any, *, native_mode: bool) -> list[int]:
    """Números dos controles frágeis por BT no Modo Nativo — função pura.

    MESA-CHEIA-11/E1, e o defeito que ela corrige é FALSO NEGATIVO: a flag
    olhava só o `transport` do PRIMÁRIO, então com o Controle 1 no cabo e os
    outros três no rádio o aviso **calava justamente para os três frágeis** —
    a situação de co-op mais comum, porque o primeiro plugado é o dela.

    Frágil é cada controle CONECTADO em ``transport == "bt"`` enquanto o Modo
    Nativo está ligado (fora do Modo Nativo não há fragilidade a avisar: o
    jogo vê o gamepad virtual, não o físico). Os números saem CRESCENTES, e
    não na ordem dos handles: quem lê a frase procura o card pelo número, e
    "Controles 3 e 2" faria ela varrer a fileira duas vezes.

    Devolve `[]` — e não levanta — para `controllers` ausente ou dublado: o
    handler roda com backends de teste e com o `describe_controllers` de um
    MagicMock, e um aviso de tela nunca pode derrubar o `state_full`.
    """
    if not native_mode or not isinstance(controllers, list):
        return []
    numeros: list[int] = []
    for entry in controllers:
        if not isinstance(entry, dict):
            continue
        if not entry.get("connected"):
            continue
        transporte = entry.get("transport")
        if not isinstance(transporte, str) or transporte.lower() != "bt":
            continue
        numero = _numero_de_exibicao(entry)
        if numero not in numeros:
            numeros.append(numero)
    return sorted(numeros)


_HOLDERS_PGREP_TIMEOUT_SEC = _escritor_cru.PGREP_TIMEOUT_S
_HOLDERS_SCAN_BUDGET_SEC = _escritor_cru.ORCAMENTO_DA_VARREDURA_S
_HOLDERS_MAX_STEAM_PIDS = _escritor_cru.MAX_PIDS_DA_STEAM


def _steam_pids() -> list[int]:
    """PIDs do processo Steam via pgrep — padrões do `steam_running` canônico."""
    from hefesto_dualsense4unix.core.escritor_cru import pids_da_steam

    return pids_da_steam()


def _steam_hidraw_holders() -> dict[str, list[int]]:
    """Mapa `/dev/hidrawN` -> PIDs do Steam que seguram o nó (8BIT-01).

    Sonda OPCIONAL e degradável, restrita aos PIDs do Steam (nunca
    `/proc/*/fd` de todos os processos) — funciona sem sudo para processos do
    mesmo usuário (readlink em /proc/<pid>/fd, provado ao vivo no estudo).
    Estourou o orçamento/permissão -> devolve o que tem; quem consome trata
    ausência como "não sondado", NUNCA como "ninguém segura". Lembrete de
    honestidade do sprint: fd aberto pelo Steam é estado NORMAL, não
    assinatura de conflito.

    ESCRITOR-CRU-01: o corpo mora em `core/escritor_cru.holders_de_hidraw`
    (ver `_steam_pids` acima). Aqui sem filtro de nós — o inventário quer
    TODOS os hidraw que a Steam segura, e é ele quem cruza com os seus.
    """
    from hefesto_dualsense4unix.core.escritor_cru import holders_de_hidraw

    return holders_de_hidraw()


def _external_inventory(
    dualsense_count: int = 0,
    slot_resolver: Callable[[str | None], int | None] | None = None,
) -> list[dict[str, Any]]:
    """Inventário de externos + sonda de holders — roda FORA do event loop.

    Composição síncrona chamada via `asyncio.to_thread` pelo
    `_handle_controller_list`: a enumeração evdev custa 10-40 ms
    (PERF-MULTI-CONTROLLER-01) e a sonda faz subprocess/readlink — nada disso
    pode bloquear o loop do daemon (congelaria o input no meio do jogo).

    O campo `holders` só aparece quando a sonda RODOU e achou o Steam
    segurando aquele hidraw ({"steam_pids": [...]}); sonda falha/vazia =
    campo ausente, sem erro (não é critério de aceite do 8BIT-01).

    CLONE-01 — o campo `identity` (:data:`EXTERNAL_IDENTITY_FIELD`) é
    SEMPRE carimbado: é a identidade de APARELHO com que o daemon numerou
    aquele controle, resolvida aqui (com o sysfs à mão) e levada pronta à
    GUI. Sem ela, dois clones Nintendo-class degradados no cabo — que o
    kernel entrega com o MESMO `uniq` sintético — eram indistinguíveis do
    outro lado do JSON-RPC: mesmo botão no seletor, mesmo número.

    EXT-04 — leitura PURA: esta função NUNCA MAIS escreve LED (a escrita a
    cada poll de 4s da GUI bombardeava o firmware clone do 8BitDo até o
    hid-nintendo desregistrá-lo — `joycon_enforce_subcmd_rate` ao vivo).
    Quem numera E acende é o tick lento do daemon (`ExternalLedSync`);
    `player_slot` aqui vem do registry (via `slot_resolver`, leitura pura por
    uniq).

    NUMA-05 (fim do posicional): a opinião do `slot_resolver` é a fonte ÚNICA
    de `player_slot` — inclusive quando a opinião é "nenhuma ainda" (``None``,
    registry sem sessão pra aquele device ou exceção suprimida).

    R-24 (auditoria 25/07): o posicional `dualsense_count + índice + 1` foi
    REMOVIDO até do caminho "sem resolver". Ele sobrevivia como compat do
    daemon pré-8BIT-02, mas era um SEGUNDO espaço de numeração escrevendo no
    MESMO campo que a GUI e a CLI exibem: um DualSense sumindo do `ds_count`
    deslocava TODOS os externos de uma vez (o ponto cego do incidente de
    14:42) e o número exibido divergia do LED aceso. Sem registro não existe
    número — `None` (null honesto > número errado). `dualsense_count` fica na
    assinatura só para não quebrar chamadores; não é mais lido.
    """
    from hefesto_dualsense4unix.core.evdev_reader import discover_external_gamepads
    from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
        EXTERNAL_IDENTITY_FIELD,
        identity_for_entry,
    )

    inventory = discover_external_gamepads()
    holders: dict[str, list[int]] = {}
    with contextlib.suppress(Exception):
        holders = _steam_hidraw_holders()
    for entry in inventory:
        hidraw = entry.get("hidraw")
        if holders and isinstance(hidraw, str) and hidraw in holders:
            entry["holders"] = {"steam_pids": holders[hidraw]}
        # quando havia slot de DualSense reservado.
        identity = identity_for_entry(entry)
        entry[EXTERNAL_IDENTITY_FIELD] = identity
        slot: int | None = None
        if slot_resolver is not None:
            with contextlib.suppress(Exception):
                raw = slot_resolver(identity)
                if isinstance(raw, int) and not isinstance(raw, bool):
                    slot = raw
        entry["player_slot"] = slot
    return inventory


class IpcHandlersMixin:
    """Mixin com os 19 métodos `_handle_*` do IpcServer.

    Não instanciável isolado — espera atributos `controller`, `store`,
    `profile_manager`, `daemon` providos pela classe concreta (IpcServer).
    """

    # Atributos fornecidos pela classe concreta. Declarados para o mypy.
    controller: IController
    store: StateStore
    profile_manager: Any
    daemon: DaemonProtocol

    #: STATUS-01: cache TTL das leituras sysfs de lightbar (lazy, por
    #: instância — ver `_lightbar_read_cached`). Class attribute com default
    #: None de propósito: o mixin não é dataclass, então isto NÃO vira field
    #: do `IpcServer` (não muda o __init__ dele); a instância faz shadow na
    #: primeira leitura.
    _lightbar_read_cache: (
        dict[str, tuple[float, tuple[int, int, int] | None, bool]] | None
    ) = None

    #: arquivo — o state_full roda a 10-20 Hz) e a PRIMEIRA detecção do appid
    _wrapper_marker_cache: tuple[float, tuple[int, int] | None] | None = None
    _wrapper_first_seen: tuple[int, float] | None = None

    _pontes_confirmadas_cache: tuple[float, dict[str, Any]] | None = None

    _hid_orfaos_cache: tuple[float, list[str]] | None = None

    #: QUEM-SEGURA-O-NOSSO-NO-01: o nó de cada vpad (`_no_do_vpad_cached`), por
    #: `(uniq, nome)`: `(quando, ficha do dono do evento ou None, bloco)`.
    _no_do_vpad_cache: (
        dict[tuple[str, str], tuple[float, tuple[int, ...] | None, dict[str, Any]]] | None
    ) = None

    #: MASCARA-01: a task do arming de launch em voo (ver
    _launch_arm_task: Any = None

    #: trava de uma pergunta em voo por controle, porque o `state_full` roda a
    _identidade_de_fabrica_cache: dict[str, dict[str, str | None]] | None = None
    _agenda_da_identidade: Any = None

    #: giroscópio/touchpad só nascem quando alguém pede o `state_full` e
    _sensor_hub: Any = None


    async def _handle_profile_switch(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica perfil escolhido pelo usuário (entrada manual via IPC)."""
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("profile.switch exige 'name' string")
        relatorio: dict[str, str] = {}
        import time as _time

        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )
        lock_antes = getattr(self.store, "_manual_profile_lock_until", 0.0)
        self.store.mark_manual_profile_lock(
            _time.monotonic() + MANUAL_PROFILE_LOCK_SEC
        )
        try:
            profile = self.profile_manager.activate(
                name, origin="manual", relatorio=relatorio
            )
        except Exception:
            # Atomicidade (a mesma que a docstring já promete ao marker): uma
            # a trava que ela tinha armado — `profile.switch` com nome
            self.store.mark_manual_profile_lock(lock_antes)
            raise
        if self.daemon is not None:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.launch_env import (
                    materialize_launch_env,
                )

                materialize_launch_env(self.daemon)
        estado_modo = relatorio.get("mode", "aplicado")
        resposta: dict[str, Any] = {
            "active_profile": profile.name,
            "mode_aplicado": estado_modo == "aplicado",
            "secoes": dict(relatorio),
        }
        if estado_modo != "aplicado":
            resposta["motivo"] = estado_modo
            if estado_modo.startswith("adiado"):
                deadline = getattr(
                    getattr(self.daemon, "_mode_pendente", None), "nao_antes_de", None
                )
                if isinstance(deadline, int | float):
                    import time as _t

                    resposta["expira_em_sec"] = round(
                        max(0.0, float(deadline) - _t.monotonic()), 1
                    )
        return resposta

    async def _handle_profile_list(self, params: dict[str, Any]) -> dict[str, Any]:
        from hefesto_dualsense4unix.profiles.manager import os_perfis_de_escolher

        profiles = os_perfis_de_escolher(self.profile_manager.list_profiles())
        return {
            "profiles": [
                {
                    "name": p.name,
                    "priority": p.priority,
                    "match_type": getattr(p.match, "type", "criteria"),
                }
                for p in profiles
            ]
        }

    async def _handle_profile_apply_draft(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Aplica draft completo em ordem canonica: leds -> triggers -> rumble -> mouse."""
        applier = DraftApplier(
            controller=self.controller,
            store=self.store,
            daemon=self.daemon,
        )
        applied = applier.apply(params)
        return {"status": "ok", "applied": applied, "failed": dict(applier.failed)}

    async def _handle_profile_reaplicar(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """O «Aplicar»: o perfil inteiro de novo aos controles, sem virar escolha.

        O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01 (01/10/2026). A MESMA cadeia do
        `profile.switch` (`ProfileManager.reaplicar`), com todas as camadas; o
        que fica de fora é só o que é da escolha: a sessão, o marcador, o Modo
        Freestyle e a trava da troca à mão. A resposta tem a forma da do
        `profile.switch`.
        """
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("profile.reaplicar exige 'name' string")
        relatorio: dict[str, str] = {}
        profile = self.profile_manager.reaplicar(name, relatorio=relatorio)
        if self.daemon is not None:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.launch_env import (
                    materialize_launch_env,
                )

                materialize_launch_env(self.daemon)
        estado_modo = relatorio.get("mode", "aplicado")
        resposta: dict[str, Any] = {
            "active_profile": profile.name,
            "mode_aplicado": estado_modo == "aplicado",
            "secoes": dict(relatorio),
        }
        if estado_modo != "aplicado":
            resposta["motivo"] = estado_modo
        return resposta


    def _apply_por_uniq(
        self,
        params: dict[str, Any],
        *,
        brilho_da_cor: float | None = None,
        **campos: Any,
    ) -> str | None:
        """Aplica ``campos`` SÓ no controle do MAC ``params["uniq"]``, se houver.

        PERFIL-05 (22/07): alinha o eixo da escrita VIVA com o da persistência
        (ambos por MAC, via ``apply_output_for`` — que registra o override
        por-uniq e escreve só naquele controle).

        MESA-CHEIA-09 (E1/E2): devolve **o que o backend fez** — uma palavra de
        ``core.controller.ResultadoDeSaida`` — em vez de um booleano que só
        dizia "esta rota foi usada". ``None`` continua querendo dizer "esta
        rota NÃO se aplica" (sem ``uniq`` no pedido, ou backend sem
        ``apply_output_for``), e o chamador segue o caminho clássico por
        índice/broadcast, intacto.

        **Backend que não sabe dizer** (dublê antigo que devolve ``None``)
        vira ``"escreveu"``: é a resposta histórica, e trocá-la por "guardado"
        faria a tela dizer que ficou pendente um ajuste que o dublê aplicou.
        Quem quiser a verdade implementa o retorno.

        `brilho_da_cor` viaja com a cor do `led.set` (A-04-PERGUNTA-AO-DAEMON-VIVO-01):
        o backend o guarda ao lado dela, e é o que o `state_full` publica como
        `brilho_da_barra`. O backend de outra árvore, sem o parâmetro, recebe a
        cor igual — sem o carimbo, a tela cai no disco, como antes.
        """
        alvo = params.get("uniq")
        if not isinstance(alvo, str) or not alvo:
            return None
        apply_for = getattr(self.controller, "apply_output_for", None)
        if not callable(apply_for):
            return None
        from hefesto_dualsense4unix.core.controller import OutputSpec

        spec = OutputSpec(**campos)
        if brilho_da_cor is None:
            resultado = apply_for(alvo, spec)
        else:
            try:
                resultado = apply_for(alvo, spec, brilho_da_cor=brilho_da_cor)
            except TypeError:
                resultado = apply_for(alvo, spec)
        return resultado if isinstance(resultado, str) and resultado else "escreveu"

    @staticmethod
    def _destinos_por_uniq(resultado: str | None, uniq: str) -> tuple[list[str], list[str]]:
        """``(aplicado_em, guardado_em)`` a partir do que o backend fez.

        MESA-CHEIA-09 (E1/E2). ``aplicado_em`` passa a significar **o byte
        saiu** — a mesma coisa que já significava no ramo broadcast, onde a
        lista só tem quem está CONECTADO. Antes, no ramo por-``uniq``, ele era
        ``[uniq]`` sempre: com o controle fora da mesa a resposta afirmava
        escrita onde só houve registro, e a janela repetia a afirmação.

        ``guardado_em`` é o campo novo, e existe porque "não escreveu" tem
        DUAS causas com destinos opostos na tela: o override que ficou
        guardado e pega no hotplug (D-9 — *"Guardado — vai valer quando o
        Controle N voltar"*) e o pedido que não guardou nada (sem MAC
        estável). Sem o segundo campo, a tela teria de escolher entre chamar
        de "guardado" o que se perdeu ou de "falhou" o que ficou.

        Conserto 1.3: ``"registrado"`` passou a cobrir também o **Modo Nativo**
        (o backend guarda e o desmute aplica), e por isso a aba Gatilhos parou
        de dizer "aplicado" ali sem que nada mude aqui — este mapa já dava o
        destino certo. E ``"falhou"`` (escrita que levantou) entra nas duas
        listas VAZIAS: não escreveu, e prometer "guardado" seria mandá-la
        esperar um evento que pode nunca vir.

        Conserto 1.4: o default deixou de ser OTIMISTA. Era ``[uniq], []`` para
        QUALQUER palavra fora das listas — a sexta palavra que o backend
        aprendesse a dizer entraria calada como "aplicado", que é a mentira que
        esta sprint existe para matar. Agora só ``"escreveu"`` afirma; palavra
        desconhecida não afirma nem promete, e sai no log.
        """
        if resultado == "escreveu":
            return [uniq], []
        if resultado == "registrado":
            return [], [uniq]
        if resultado in (None, "sem_alvo", "nada_a_fazer", "falhou"):
            return [], []
        logger.warning(
            "destino_por_uniq_palavra_desconhecida", resultado=resultado, uniq=uniq
        )
        return [], []

    def _uniqs_conectados(self) -> list[str]:
        """MACs dos controles CONECTADOS, na ordem do backend.

        Fonte: ``describe_controllers`` — só getattrs baratos, sem HID I/O (a
        mesma que o ``controller.list`` usa). Lista VAZIA quando o backend não
        sabe dizer quem está na mesa (``FakeController``, backend legado) ou
        quando não há ninguém: o chamador segue pelo caminho clássico, intacto.
        """
        describe = getattr(self.controller, "describe_controllers", None)
        if not callable(describe):
            return []
        try:
            entradas = describe()
        except Exception as exc:
            logger.debug("uniqs_conectados_falhou", err=str(exc))
            return []
        if not isinstance(entradas, list):
            return []
        alvos: list[str] = []
        for entrada in entradas:
            if not isinstance(entrada, dict) or not entrada.get("connected"):
                continue
            uniq = entrada.get("uniq")
            if isinstance(uniq, str) and uniq and uniq not in alvos:
                alvos.append(uniq)
        return alvos

    def _registrar_em_todos(
        self, *, brilho_da_cor: float | None = None, **campos: Any
    ) -> list[str]:
        """Registra ``campos`` na camada da USUÁRIA de CADA controle conectado."""
        apply_for = getattr(self.controller, "apply_output_for", None)
        if not callable(apply_for):
            return []
        alvo_uniq_fn = getattr(self.controller, "get_output_target_uniq", None)
        alvo_presente = alvo_uniq_fn() if callable(alvo_uniq_fn) else None
        if isinstance(alvo_presente, str) and alvo_presente:
            return [alvo_presente]
        alvo_ausente_fn = getattr(self.controller, "alvo_de_output_ausente", None)
        alvo_ausente = alvo_ausente_fn() if callable(alvo_ausente_fn) else None
        if isinstance(alvo_ausente, str) and alvo_ausente:
            return []
        alvos = self._uniqs_conectados()
        if not alvos:
            return []
        from hefesto_dualsense4unix.core.controller import OutputSpec
        from hefesto_dualsense4unix.core.led_control import DO_BROADCAST

        spec = OutputSpec(**campos)
        aplicados: list[str] = []
        for alvo in alvos:
            try:
                if brilho_da_cor is None:
                    apply_for(alvo, spec, procedencia_da_cor=DO_BROADCAST)
                else:
                    # é o que o `state_full` publica como `brilho_da_barra`.
                    apply_for(
                        alvo, spec, procedencia_da_cor=DO_BROADCAST,
                        brilho_da_cor=brilho_da_cor,
                    )
            except TypeError:
                apply_for(alvo, spec)
            except Exception as exc:
                logger.warning(
                    "registrar_em_todos_falhou", uniq=alvo, err=str(exc)
                )
                continue
            aplicados.append(alvo)
        return aplicados

    def _destinos_do_broadcast(self) -> tuple[list[str], list[str]]:
        """``(aplicado_em, guardado_em)`` da rota CLÁSSICA — o pedido SEM ``uniq``.

        Conserto 1.4. O ``trigger.set``/``trigger.reset`` sem ``uniq`` devolvia
        as duas listas vazias **mesmo tendo escrito**, enquanto a rota irmã
        ``led.set`` respondia ``aplicado_em`` com a mesa inteira — duas rotas
        irmãs, respostas opostas, e a tela lê as duas ("Todos" no seletor da
        aba Gatilhos manda o pedido sem ``uniq``). Aqui a rota do gatilho passa
        a dizer em QUEM pegou, com o mesmo teto de verdade do ramo por-``uniq``.

        O que este método **não** faz, e cada "não" é medido, não suposto:

        * **Não** registra nada por controle. O espelho LITERAL do ``led.set``
          seria chamar ``_registrar_em_todos``, e isso mudaria a ESCRITA, não a
          resposta: ``_record_desired_locked(None, ...)`` limpa o campo em todos
          os overrides por-uniq e SOLTA o carimbo de dono, porque "Todos" é
          gesto de NIVELAR. Medido (14/08): depois de ``apply_output_for`` o
          campo fica com dono ``usuaria``; depois de um ``set_trigger``
          broadcast o override some e o dono vira ``None``. Re-registrar por
          controle desfaria o nivelamento que a própria rota promete.
        * ``guardado_em`` só é prometido no caso do alvo AUSENTE (abaixo) —
          para "Todos" continua sem promessa por-controle: o valor foi para o
          default, sem endereço, e publicar um MAC aqui mandaria a usuária
          esperar por um controle que não é o dono do que ela pediu.
        * **Não** afirma nada em **Modo Nativo**: o ``report_thread`` está mudo
          e nenhum byte sai (CONSERTO 1.3). É onde a rota irmã ainda mente —
          medido em 14/08, ``led.set`` sem ``uniq`` com o output mutado responde
          ``aplicado_em`` com os dois MACs e ZERO byte no fio, porque
          ``_registrar_em_todos`` ignora a palavra que o backend devolve.
        * **Não** afirma quando não sabe: mesa vazia, backend que não diz quem
          está nela nem onde o seletor está, ou alvo do seletor sem MAC estável
          (key por path) devolvem as duas listas vazias — o "não sei dizer em
          quem" que o comentário do ``led.set`` já fixou.

        BROADCAST-PROIBIDO-01 (24/08/2026): antes de ler
        ``get_output_target_index`` — que MASCARA "Todos" e "alvo sumiu" no
        MESMO ``None`` (o próprio getter documenta a ambiguidade) — este
        método pergunta ``alvo_de_output_ausente``. Alvo escolhido e FORA da
        mesa devolve ``([], [alvo])``: a escrita clássica (``set_trigger``, via
        ``_for_each``/``_resolver_escopo``) não foi a ninguém, e o valor ficou
        guardado no override por-uniq dele — a mesma dupla verdade que
        ``output_alvo_ausente_noop`` já loga. Fundir os dois destinos aqui era
        exatamente a fusão que o F4 desfez um andar abaixo, só que nomeando os
        TRÊS conectados como se tivessem recebido o gatilho do jogador ausente.

        O teto de verdade é o MESMO do ramo por-``uniq``: ``_apply_trigger`` só
        arma o estado no handle (``trigger.mode``/``setForce``, sem I/O nenhum)
        e quem escreve no fio é o ``report_thread``. "Aplicado" aqui quer dizer,
        como lá, que o desejado está armado e o fio não está mudo.
        """
        alvos = self._uniqs_conectados()
        if not alvos:
            return [], []
        if self.daemon is not None and self.daemon.is_native_mode():
            return [], []
        alvo_ausente_fn = getattr(self.controller, "alvo_de_output_ausente", None)
        alvo_ausente = alvo_ausente_fn() if callable(alvo_ausente_fn) else None
        if isinstance(alvo_ausente, str) and alvo_ausente:
            return [], [alvo_ausente]
        onde_mira = getattr(self.controller, "get_output_target_index", None)
        if not callable(onde_mira):
            return [], []
        try:
            indice = onde_mira()
        except Exception as exc:  # observabilidade > silêncio
            logger.debug("destinos_do_broadcast_falhou", err=str(exc))
            return [], []
        if indice is None:
            return alvos, []
        # Seletor mirando UM controle: o `_for_each` do backend escreve só nele,
        # e afirmar a mesa inteira aqui seria a mentira antiga com outro nome.
        nomear = getattr(self.controller, "get_output_target_uniq", None)
        alvo = nomear() if callable(nomear) else None
        if not isinstance(alvo, str) or not alvo:
            return [], []
        return [alvo], []

    async def _handle_trigger_set(self, params: dict[str, Any]) -> dict[str, Any]:
        side = params.get("side")
        mode = params.get("mode")
        trigger_params = params.get("params", [])
        if side not in ("left", "right"):
            raise ValueError("trigger.set: side precisa ser 'left' ou 'right'")
        if not isinstance(mode, str):
            raise ValueError("trigger.set: mode precisa ser string")
        if not isinstance(trigger_params, list):
            raise ValueError("trigger.set: params precisa ser lista")
        effect = build_from_name(mode, trigger_params)
        campos: dict[str, Any] = (
            {"trigger_left": effect} if side == "left" else {"trigger_right": effect}
        )
        resultado = self._apply_por_uniq(params, **campos)
        if resultado is None:
            self.controller.set_trigger(side, effect)
            aplicado_em, guardado_em = self._destinos_do_broadcast()
        else:
            aplicado_em, guardado_em = self._destinos_por_uniq(
                resultado, str(params["uniq"])
            )
        return {
            "status": "ok",
            "aplicado_em": aplicado_em,
            "guardado_em": guardado_em,
        }

    async def _handle_trigger_reset(self, params: dict[str, Any]) -> dict[str, Any]:
        """Devolve o gatilho ao perfil e LIBERA a trava manual dele (R-19).

        ABAS-06 (25/07): ``uniq`` presente = reset por-MAC, pela mesma rota do
        ``trigger.set`` (``apply_output_for``). Era o ÚNICO comando de saída da
        janela que ainda ia em broadcast: com "Controle 2" escolhido no seletor,
        "Desligar" zerava o gatilho dos QUATRO enquanto o "Aplicar" logo ao lado
        mandava para um só. O mesmo defeito já tinha sido corrigido no "Apagar"
        da aba Lightbar (R-17) e não fora replicado aqui.

        ABAS-05 (25/07): a trava manual é limpa SÓ na categoria ``trigger``. O
        clear sem categoria apagava ``led`` e ``rumble`` junto — desligar UM
        gatilho reabria a troca automática de perfil para reescrever a cor que a
        aba Lightbar tinha acabado de aplicar. É a queixa histórica "a config
        que eu deixo não fica", e a granularidade por categoria (ONDA-U/F1)
        existe exatamente para isso não acontecer: o próprio ``state_store``
        documenta que o fim do "Testar motores" não pode apagar o LED de outra
        aba — não havia razão para o botão "Desligar" dos gatilhos poder.

        Quem quer soltar TUDO de uma vez continua tendo o caminho explícito e
        rotulado: ativar um perfil (``profile.switch``), que limpa as três.
        """
        target = params.get("side", "both")
        if target not in ("left", "right", "both"):
            raise ValueError("trigger.reset: side deve ser left|right|both")
        campos: dict[str, Any] = {}
        if target in ("left", "both"):
            campos["trigger_left"] = trigger_off()
        if target in ("right", "both"):
            campos["trigger_right"] = trigger_off()
        resultado = self._apply_por_uniq(params, **campos)
        if resultado is None:
            for lado in ("left", "right"):
                if f"trigger_{lado}" in campos:
                    self.controller.set_trigger(lado, campos[f"trigger_{lado}"])
            aplicado_em, guardado_em = self._destinos_do_broadcast()
        else:
            aplicado_em, guardado_em = self._destinos_por_uniq(
                resultado, str(params["uniq"])
            )
        return {
            "status": "ok",
            "aplicado_em": aplicado_em,
            "guardado_em": guardado_em,
        }


    async def _handle_led_set(self, params: dict[str, Any]) -> dict[str, Any]:
        rgb = params.get("rgb")
        if not isinstance(rgb, list) or len(rgb) != 3:
            raise ValueError("led.set: rgb precisa ser lista com 3 inteiros")
        for idx, v in enumerate(rgb):
            if not isinstance(v, int) or not (0 <= v <= 255):
                raise ValueError(f"led.set: rgb[{idx}] fora de byte")
        brightness_raw = params.get("brightness", 1.0)
        try:
            brightness = float(brightness_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("led.set: brightness precisa ser numerico") from exc
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(
                f"led.set: brightness fora de [0.0, 1.0]: {brightness}"
            )
        from hefesto_dualsense4unix.core.led_control import LedSettings

        r, g, b = LedSettings(
            lightbar=(int(rgb[0]), int(rgb[1]), int(rgb[2]))
        ).apply_brightness(brightness).lightbar
        resultado = self._apply_por_uniq(params, brilho_da_cor=brightness, led=(r, g, b))
        guardado_em: list[str] = []
        if resultado is not None:
            aplicado_em, guardado_em = self._destinos_por_uniq(
                resultado, str(params["uniq"])
            )
        else:
            self.controller.set_led((r, g, b))
            aplicado_em = self._registrar_em_todos(brilho_da_cor=brightness, led=(r, g, b))
        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()
        return {
            "status": "ok",
            "aplicado_em": aplicado_em,
            "guardado_em": guardado_em,
        }

    async def _handle_led_player_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica bitmask de 5 LEDs de player no controle."""
        bits_raw = params.get("bits")
        if not isinstance(bits_raw, list) or len(bits_raw) != 5:
            raise ValueError("led.player_set: 'bits' precisa ser lista com exatamente 5 booleanos")
        for idx, v in enumerate(bits_raw):
            if not isinstance(v, bool):
                raise ValueError(f"led.player_set: bits[{idx}] precisa ser booleano")
        bits: tuple[bool, bool, bool, bool, bool] = (
            bits_raw[0], bits_raw[1], bits_raw[2], bits_raw[3], bits_raw[4]
        )
        # por-MAC via apply_output_for (só naquele controle).
        resultado = self._apply_por_uniq(params, player_leds=bits)
        guardado_em: list[str] = []
        if resultado is not None:
            aplicado_em, guardado_em = self._destinos_por_uniq(
                resultado, str(params["uniq"])
            )
        else:
            self.controller.set_player_leds(bits)
            # BROADCAST-QUE-NAO-MENTE-01: MESMO defeito do `led.set` e pela
            # MESMA razão — a numeração automática (COR-03/D7) também entra no
            # merge acima do default, então o broadcast cru era desfeito pelo
            # reassert. É o "sucesso mentiroso" que a PLAYER-01 (entrega 6) já
            # tinha diagnosticado e que a GUI resolvia RECUSANDO o pedido
            # quando não sabia quem estava conectado; aqui o daemon, que SABE,
            # registra por MAC em vez de recusar. A camada do co-op continua
            # acima desta (R-13) — ligado o co-op, o número dele segue vencendo.
            aplicado_em = self._registrar_em_todos(player_leds=bits)
        # Fix cross-cutting U x N (2026-07-20, HIGH) — mesmo raciocínio de
        # `_handle_led_set`: reassert imediato para o merge de N (jogo vence
        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()
        return {
            "status": "ok",
            "bits": list(bits),
            "aplicado_em": aplicado_em,
            "guardado_em": guardado_em,
        }

    async def _handle_led_player_brightness_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """O brilho das cinco luzes de número: Fraco, Médio ou Forte.

        DECISÃO DELA, 24/09/2026 (`D-2409-AS-LUZES-DE-NUMERO-TEM-TRES-BRILHOS`):
        *"Fraco, Médio e Forte na linha LEDs, nascendo no Fraco"*. Quem clica é
        a linha LEDs da aba Iluminação, uma pílula por controle.

        Params:
            brilho: ``"fraco"``, ``"medio"`` ou ``"forte"`` — a PALAVRA do (noqa-acento)
                perfil. A tradução para o degrau do firmware é de
                ``core/led_control.degrau_do_brilho_das_luzes``, e a palavra
                desconhecida é recusada ali, com a lista das três.
            uniq: o MAC do controle. Presente = SÓ nele (a camada da usuária,
                pela mesma porta do ``led.player_set``); ausente = «Todos»: o
                padrão de quem chegar depois E cada conectado.

        Nos dois casos o brilho sai pelos caminhos do número, nos dois
        transportes — ver ``PyDualSenseController._levar_o_brilho_das_luzes``.
        """
        from hefesto_dualsense4unix.core.led_control import (
            BRILHOS_DAS_LUZES,
            degrau_do_brilho_das_luzes,
        )

        brilho = params.get("brilho")
        if not isinstance(brilho, str):
            palavras = ", ".join(BRILHOS_DAS_LUZES)
            raise ValueError(
                f"led.player_brightness_set: 'brilho' precisa ser um de: {palavras}"
            )
        degrau = degrau_do_brilho_das_luzes(brilho)
        resultado = self._apply_por_uniq(params, player_led_brightness=degrau)
        guardado_em: list[str] = []
        if resultado is not None:
            aplicado_em, guardado_em = self._destinos_por_uniq(
                resultado, str(params["uniq"])
            )
        else:
            from hefesto_dualsense4unix.core.controller import OutputSpec

            spec = OutputSpec(player_led_brightness=degrau)
            padrao = getattr(self.controller, "apply_output_defaults", None)
            if callable(padrao):
                padrao(spec)
            aplicado_em = []
            apply_for = getattr(self.controller, "apply_output_for", None)
            if callable(apply_for):
                for alvo in self._uniqs_conectados():
                    try:
                        if apply_for(alvo, spec) == "escreveu":
                            aplicado_em.append(alvo)
                    except Exception as exc:
                        logger.warning(
                            "brilho_das_luzes_em_todos_falhou", uniq=alvo, err=str(exc)
                        )
        return {
            "status": "ok",
            "brilho": brilho,
            "aplicado_em": aplicado_em,
            "guardado_em": guardado_em,
        }

    async def _handle_led_auto_release(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Devolve a luz ao automático: solta a trava manual de `"led"` — e SÓ ela.

        A-TRAVA-DO-LED-NÃO-SOLTA-01 (06/09/2026). O PAR QUE FALTAVA. Até aqui
        `led.set` e `led.player_set` ARMAVAM a trava (`:1468` e `:1524`) e
        nenhuma linha de `src/` a soltava: a única saída era ela trocar de
        perfil na mão — um gesto que a pessoa não tem como saber que precisa
        fazer. `trigger` tinha o `trigger.reset` e `rumble` tinha o
        `rumble.passthrough`; a luz não tinha nada.

        SÓ `"led"`, e o `clear` sem argumento seria a regressão do ABAS-05:
        soltar as quatro apagaria um gatilho ou uma vibração deliberada de
        outra aba. É a razão escrita da assinatura por categoria em
        `state_store.clear_manual_trigger_active`, e ela vale aqui em dobro —
        este método é chamado por UM botão de UMA aba.

        POR QUE UMA ROTA PRÓPRIA, e não um parâmetro no `led.set`: é ORDEM. O
        gesto "Automático" da aba Iluminação (`interface/pacotes/a04_iluminacao`)
        faz duas coisas, nesta ordem medida em 02/09 — larga o claim da barra
        (`lightbar.reset`) e SÓ ENTÃO pinta a cor do slot, para a barra não
        ficar preta. Essa segunda escrita é um `led.set`, que ARMA. Pendurar o
        clear em qualquer das duas o deixaria antes da escrita que o desfaz;
        pendurado aqui, ele é o ÚLTIMO ato do gesto e nada o re-arma.

        ELE NÃO ESCREVE BYTE NENHUM no controle, e é por isso que não tem
        `uniq`: a trava é do `StateStore` e não tem dono por controle
        (`_manual_override_categories` é um dicionário categoria → carimbo,
        um por daemon). Aceitar um `uniq` e ignorá-lo seria o "sucesso
        mentiroso" que a APLICAR-VERDADE-01 nomeia. `escopo` diz isso na
        resposta, em vez de deixar quem chama supor.

        Soltar a trava não pinta nada: só devolve ao `AutoSwitcher` o direito
        de decidir no próximo tique de troca de janela — que é exatamente o que
        "voltar ao automático" promete por escrito na tela.
        """
        logger.info("led_auto_release", categoria="led")
        return {"status": "ok", "categoria": "led", "escopo": "o daemon inteiro"}


    async def _handle_identity_renumber(self, params: dict[str, Any]) -> dict[str, Any]:
        """Reordena a FILA de preferência (DualSense + externos) — ONDA-U/NUM-01.

        Cura o "sony 1 / sony 4" com só 2 controles: lugares de sessões
        anteriores continuam do MAC (D2) e nunca encolhem sozinhos. Gate:
        recusa com uma sessão de jogo ABERTA (``display_authority ==
        'game'``) — repintar o LED do controle que o jogo está usando NO
        MEIO da partida é o mesmo erro que o NUMA-03 já resolveu para o tick
        automático; aqui é uma ação EXPLÍCITA da usuária, então o gate é o
        mesmo critério, não uma cópia frouxa.

        A fila é ÚNICA entre DualSense (``identity.py``) e externos
        (``external_identity.py`` — EXT-04), então a reordenação é GLOBAL:
        junta os dois ``snapshot()``, ordena pelo lugar ATUAL (preserva a
        ORDEM RELATIVA — quem já estava na frente continua na frente) e
        reescreve 1..N: cada registro só recebe de volta a fatia de chaves
        que é dele (``ControllerIdentityRegistry.compact`` /
        ``ExternalIdentityRegistry.compact``, ambos sob o
        ``CONTROLLERS_FILE_LOCK`` de NUMA-04 via ``_save_locked``). Sem
        controle nenhum registrado (nenhum dos dois registros fiado, ou
        ambos vazios) devolve ``renumbered`` vazio — no-op seguro.

        NUM-01 mudou o SIGNIFICADO deste botão sem mudar o algoritmo, e é
        essa distinção que importa: o que ele reescreve deixou de ser o
        NÚMERO de cada controle e passou a ser o LUGAR NA FILA. O estrago
        antigo era exatamente esse acoplamento — com um DualSense desligado,
        o gesto que consertava o controle na mesa carimbava o ausente como
        "o segundo" para sempre, porque lugar e número eram o mesmo inteiro
        (foi assim que o ``controllers.json`` dela apareceu invertido no
        mesmo dia). Hoje o ausente só perde a fila; o número dele volta a
        ser calculado quando ele voltar para a mesa.

        Repintura: ``reassert_resolved_outputs`` (getattr defensivo, mesmo
        padrão do apply_draft) reafirma o LED do DualSense já com o slot
        novo; os externos são repintados pelo PRÓPRIO tick lento seguinte
        (``ExternalLedSync.tick`` compara contra o slot atualizado — sem
        precisar de escrita síncrona aqui), mas o agendamento é adiantado
        via ``daemon._schedule_external_tick`` (getattr defensivo) para não
        esperar o intervalo cheio do poll.

        Atomicidade plan→apply (fix TOCTOU, achado MEDIUM 2026-07-20): o
        span inteiro ``snapshot()`` → plano em memória → ``compact()`` roda
        com os DOIS ``RLock`` de instância (``lock_for_renumber``, quando o
        registro os expõe) tomados o tempo todo — sem isto, um
        ``slot_for(assign=True)`` concorrente (hotplug real sob o
        ``_io_lock`` do backend, ou o tick do ``ExternalLedSync``) podia ler
        o estado AINDA não-compactado entre as duas chamadas e reivindicar
        exatamente o slot-alvo que o ``compact()`` estava prestes a devolver
        a outro controle — dois "Controle 1" simultâneos. Ordem de aquisição
        fixa (identity antes de external, sempre) evita deadlock.

        CORREÇÃO NUM-01 de uma invariante MORTA: esta docstring afirmava que
        "nenhum outro caminho do código toma os dois locks ao mesmo tempo".
        Isso deixou de ser verdade quando o provider de reserva foi
        introduzido (EXT-04) — ``identity._assign_locked`` chama o provider
        dos externos JÁ segurando o próprio ``_lock``, e NUM-01 acrescentou o
        provider de presença pelo mesmo caminho. O que protege de deadlock
        não é a exclusividade (que não existe), é a HIERARQUIA, hoje
        documentada nos dois módulos: ``identity._lock`` → ``external
        _identity._lock`` → ``CONTROLLERS_FILE_LOCK``. Este handler a
        respeita; o lado externo é proibido de consultar o lado DualSense
        segurando o próprio lock (``_ds_present_ranks`` resolve antes de
        adquirir). Invariante documentada e morta é pior que invariante
        ausente: era ela que dizia "pode chamar de qualquer lugar". Getattr
        defensivo: fakes/backends antigos sem o método seguem sem a trava
        (mesmo risco de HEAD, nunca pior).

        Isolamento do lock (fix MEDIUM cross-cutting U x HANG-01, 2026-07-20):
        a aquisição dos dois ``RLock`` + o plano + o ``compact()`` rodam via
        ``asyncio.to_thread`` sob ``asyncio.wait_for`` — nunca mais direto
        neste método `async`, que é despachado no ÚNICO event loop do
        daemon. O MESMO lock de ``external_registry`` é tomado por
        ``ExternalLedSync.tick()`` (``sync_connected``→``_save_locked``, I/O
        de disco) no pool dedicado ``hefesto-ext`` sob
        ``EXTERNAL_TICK_TIMEOUT_SEC`` (HANG-01) — se aquele worker travar
        segurando o lock, um ``acquire()`` sem teto aqui pendurava o loop
        inteiro para sempre (zero ``read_state``, zero rumble, zero
        watchdog), reproduzindo a classe de incidente que o HANG-01 foi
        desenhado para conter, por um caminho novo que o fix de HANG-01 não
        cobria. Offload no executor PADRÃO do loop (não o ``hefesto-ext``
        dedicado — enfileirar atrás de um worker já travado não ajudaria) +
        timeout devolve erro ao IPC em vez de travar o daemon inteiro.
        """
        authority = (
            getattr(self.daemon, "display_authority", "unknown")
            if self.daemon is not None
            else "unknown"
        )
        if authority == "game":
            return {"ok": False, "reason": "sessao_de_jogo_aberta"}

        identity_registry = (
            getattr(self.daemon, "identity_registry", None)
            if self.daemon is not None
            else None
        )
        external_registry = (
            getattr(self.daemon, "external_registry", None)
            if self.daemon is not None
            else None
        )

        daemon = self.daemon

        def _authority_now() -> str:
            return (
                getattr(daemon, "display_authority", "unknown")
                if daemon is not None
                else "unknown"
            )

        try:
            renumbered = await asyncio.wait_for(
                asyncio.to_thread(
                    self._renumber_locked,
                    identity_registry,
                    external_registry,
                    authority_check=_authority_now,
                ),
                timeout=_IDENTITY_RENUMBER_LOCK_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "identity_renumber_lock_timeout",
                timeout_sec=_IDENTITY_RENUMBER_LOCK_TIMEOUT_SEC,
            )
            return {"ok": False, "reason": "lock_timeout"}
        except _RenumberAuthorityChangedError:
            logger.info("identity_renumber_abortado_por_jogo")
            return {"ok": False, "reason": "sessao_de_jogo_aberta"}

        if not renumbered:
            return {"ok": True, "renumbered": {}}

        self._despachar_repintura("identity.renumber")

        return {"ok": True, "renumbered": renumbered}

    def _despachar_repintura(self, de_onde: str) -> None:
        """Manda repintar SEM segurar a resposta — RESPOSTA-QUE-CHEGA-TARDE-01."""
        try:
            laco = asyncio.get_running_loop()
        except RuntimeError:
            self._repintar_apos_renumeracao()
            return

        def _no_fio() -> None:
            try:
                self._repintar_apos_renumeracao(laco_do_daemon=laco)
            except Exception as exc:
                logger.warning("repintura_apos_renumeracao_falhou",
                               de_onde=de_onde, err=str(exc))

        tarefa = laco.create_task(asyncio.to_thread(_no_fio))
        em_voo = getattr(self, "_repinturas_em_voo", None)
        if em_voo is None:
            em_voo = set()
            self._repinturas_em_voo = em_voo
        em_voo.add(tarefa)
        tarefa.add_done_callback(em_voo.discard)

    def _repintar_apos_renumeracao(
        self, laco_do_daemon: asyncio.AbstractEventLoop | None = None
    ) -> None:
        """As TRÊS repinturas de quem mexeu na fila de números. Nesta ordem.

        ``laco_do_daemon`` é o laço de eventos do daemon, e ele é
        **obrigatório quando este corpo roda fora da thread do laço** — que é
        o caso normal desde a RESPOSTA-QUE-CHEGA-TARDE-01, em que
        `_despachar_repintura` o joga num `asyncio.to_thread`. Só o passo 3 o
        usa; ver o comentário lá embaixo para a medição que o exige. ``None``
        significa "estou na thread do laço, ou não há laço nenhum" — o
        caminho síncrono dos dublês da suíte.

        Compartilhada por `identity.renumber` e `identity.number.set` porque o
        defeito é o mesmo nos dois: os dois escrevem a MESMA fila
        (`identity_registry`), e é dela que sai a lâmpada de jogador —
        `_apply_coop_player_leds` → `numeros_de_jogador()` → `_numero_exibido`
        → `slot_for`.

        1. **`coop.sync(force=True)` PRIMEIRO, e a ordem é o conserto.** Com
           `coop_enabled=True` a camada do co-op fica ACIMA do override
           por-uniq no merge do backend, e ela só é republicada no FIM de um
           ciclo CHEIO de `sync()` — que o `sync` só roda com
           `self._watch.poll() or activated or grab_degraded or vpad_morto or
           retry_needed or force` (`subsystems/coop.py`). **Renumerar não é
           nenhum desses**: o `/dev/input` não muda quando alguém troca um
           número. Sem o `force`, o passo 2 reafirmava a camada VELHA e a
           lâmpada só acertava no próximo hotplug.

           MEDIDO com os dois DualSense dela e o daemon vivo, lendo
           `/sys/class/leds`:

               identity.number.set sozinho ....... o `player_slot` troca,
                                                   lâmpada NENHUMA se move
               + player_leds_set por uniq ........ o daemon responde
                                                   "aplicado_em" — e nenhuma
                                                   lâmpada se move
               + coop.sync ....................... as duas seguem o número

           **Cura a janela GTK antiga junto**, e é por isso que ela mora aqui e
           não na aba: o cabeçalho da GTK tem exatamente o mesmo defeito, e um
           ramo "chama `coop.sync` quando o co-op está mandando" do lado de
           quem CLICA seria contorno — a hipótese tem de explicar o que já
           funcionava, e o que já funcionava era o hotplug.

        2. `reassert_resolved_outputs`: o DualSense reafirma o output já com o
           número novo — agora sobre a camada fresca do passo 1.
        3. `_schedule_external_tick`: os externos são repintados pelo tick
           lento, adiantado aqui para não esperar o intervalo cheio do poll.

        Custo: o `sync(force=True)` paga uma `discover_dualsense_evdevs()`
        (~10-40 ms, PERF-MULTI-CONTROLLER-01) no event loop. É o mesmo preço
        que o handler `coop.sync` já cobra, e renumerar é gesto MANUAL e raro —
        não é caminho quente. Nada aqui pode derrubar a renumeração, que já
        aconteceu: os três passos são defensivos.
        """
        if self.daemon is not None:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.subsystems.coop import (
                    get_coop_manager,
                )

                get_coop_manager(self.daemon).sync(force=True)

        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()
        schedule_external_tick = (
            getattr(self.daemon, "_schedule_external_tick", None)
            if self.daemon is not None
            else None
        )
        if not callable(schedule_external_tick):
            return
        if laco_do_daemon is None:
            schedule_external_tick()
            return
        # dos DualSense acertavam e o defeito passou despercebido.
        try:
            laco_do_daemon.call_soon_threadsafe(schedule_external_tick)
        except RuntimeError as exc:
            # Laço já fechado (desligamento). Não pode derrubar a repintura:
            logger.warning("tique_externo_nao_agendado", err=str(exc))

    async def _handle_identity_number_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Atribui o NÚMERO EXIBIDO de UM controle (PLAYER-01, 25/07).

        O comando que faltava. Até aqui, o projeto inteiro não tinha nenhuma
        forma de dizer "este controle é o 2": só existia o
        ``identity.renumber``, que COMPACTA todo mundo preservando a ordem
        relativa e mora na aba Início. A mantenedora clicava em "Player 2" na
        moldura de LEDs — que é APARÊNCIA, o desenho das 5 luzinhas —
        esperando trocar a IDENTIDADE, e o rótulo da tela prometia isso. Sem
        este handler, renomear o rótulo apenas pararia de prometer o que não
        existe; com ele, a expectativa dela ("escolho o número e o cabeçalho
        acompanha") passa a ser realizável.

        Nome: fica no namespace ``identity.`` porque escreve exatamente o
        mesmo estado que o ``identity.renumber`` (a fila de preferência dos
        dois registros, sob a mesma hierarquia de locks). E é ``number``, não
        ``player``, de propósito: ``app/actions/base.py:26`` adverte que
        "jogador" é OUTRO número — o do co-op, que o daemon aloca por vpad e
        que a aba Status exibe LADO A LADO com este. Batizar o comando de
        ``player`` seria acrescentar um sexto sentido à mesma palavra, que é
        o defeito de fundo que esta sprint existe para fechar.

        Params:
            uniq: MAC normalizado do controle (o mesmo campo ``uniq`` que o
                ``state_full`` publica e que ``led.set``/``trigger.set`` já
                aceitam como alvo).
            number: número desejado, 1..N entre os PRESENTES.

        Retorno ``{"ok": True, "number": N, "changed": {key: lugar}}`` ou
        ``{"ok": False, "reason": ...}``. ``changed`` traz só quem MUDOU de
        lugar na fila (mesma disciplina do R-15 no ``renumber``: relatório
        que não infla um no-op).

        O que ele escreve (NUM-01): a fila de preferência, nunca um "número
        absoluto". O número exibido é a COLOCAÇÃO do lugar entre quem está
        presente, então atribuir o número 2 a um controle é PERMUTAR os
        lugares que os presentes já ocupam — ver ``_set_number_locked``. Os
        lugares de quem está AUSENTE ficam intocados: diferente do
        "Renumerar agora", este gesto não rebaixa ninguém que não está na
        mesa.

        Gate de jogo aberto, teto de lock, offload em ``asyncio.to_thread`` e
        re-checagem de autoridade DENTRO dos locks: os quatro são os mesmos
        do ``identity.renumber`` e pelas mesmas razões (ver a docstring
        dele). Repintar o LED do controle que o jogo está usando no meio da
        partida é o mesmo erro do NUMA-03; e um ``acquire()`` sem teto neste
        método ``async`` penduraria o ÚNICO event loop do daemon, que é a
        classe de incidente do HANG-01.
        """
        uniq_raw = params.get("uniq")
        if not isinstance(uniq_raw, str) or not uniq_raw.strip():
            raise ValueError("identity.number.set: 'uniq' precisa ser string não vazia")
        numero = params.get("number")
        if not isinstance(numero, int) or isinstance(numero, bool) or numero < 1:
            raise ValueError(
                "identity.number.set: 'number' precisa ser inteiro >= 1"
            )
        alvo = _norm_uniq(uniq_raw) or uniq_raw.strip()

        authority = (
            getattr(self.daemon, "display_authority", "unknown")
            if self.daemon is not None
            else "unknown"
        )
        if authority == "game":
            return {"ok": False, "reason": "sessao_de_jogo_aberta"}

        identity_registry = (
            getattr(self.daemon, "identity_registry", None)
            if self.daemon is not None
            else None
        )
        external_registry = (
            getattr(self.daemon, "external_registry", None)
            if self.daemon is not None
            else None
        )
        daemon = self.daemon

        def _authority_now() -> str:
            return (
                getattr(daemon, "display_authority", "unknown")
                if daemon is not None
                else "unknown"
            )

        try:
            changed = await asyncio.wait_for(
                asyncio.to_thread(
                    self._set_number_locked,
                    identity_registry,
                    external_registry,
                    alvo,
                    numero,
                    authority_check=_authority_now,
                ),
                timeout=_IDENTITY_RENUMBER_LOCK_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "identity_number_set_lock_timeout",
                timeout_sec=_IDENTITY_RENUMBER_LOCK_TIMEOUT_SEC,
            )
            return {"ok": False, "reason": "lock_timeout"}
        except _RenumberAuthorityChangedError:
            logger.info("identity_number_set_abortado_por_jogo")
            return {"ok": False, "reason": "sessao_de_jogo_aberta"}
        except _NumeroAlvoAusenteError:
            logger.info("identity_number_set_alvo_ausente", uniq=alvo)
            return {"ok": False, "reason": "controle_ausente"}
        except _NumeroForaDaMesaError as exc:
            logger.info(
                "identity_number_set_numero_fora_da_mesa",
                uniq=alvo,
                pedido=numero,
                maximo=exc.maximo,
            )
            return {
                "ok": False,
                "reason": "numero_fora_da_mesa",
                "max": exc.maximo,
            }

        if changed:
            self._despachar_repintura("identity.number.set")

        return {"ok": True, "number": numero, "changed": changed}

    @staticmethod
    def _set_number_locked(
        identity_registry: Any,
        external_registry: Any,
        alvo: str,
        numero: int,
        authority_check: Callable[[], str] | None = None,
    ) -> dict[str, int]:
        """Corpo BLOQUEANTE do ``identity.number.set`` — só via ``to_thread``.

        A regra, em uma frase: **trocar de lugar o alvo e quem tem o número
        pedido** — os dois, e mais ninguém.

        **CORREÇÃO DE FATO, 29/08/2026 (TROCA-DE-PLAYER-01).** Este parágrafo
        dizia "pondo o alvo na posição pedida", e o corpo fazia
        ``pop``+``insert`` — um RODÍZIO, que empurra todos entre a origem e o
        destino. A tela prometia outra coisa em dezessete lugares do mockup
        aprovado (os 16 tooltips de botão e a legenda: *"Os dois trocam, os
        outros não se mexem"*), e a palavra dela de 28/08 é *"Trocar é TROCA,
        não fila"*. Quem estava errado era o daemon.

        Por que permutar em vez de reescrever 1..N (que é o que o
        ``identity.renumber`` faz): o conjunto de lugares dos presentes é
        deixado EXATAMENTE como estava — só muda quem ocupa qual. Assim, os
        lugares de quem está ausente não são tocados nem invadidos, e o gesto
        "quero que este seja o 2" não rebaixa em silêncio um controle que
        está guardado na gaveta (o efeito colateral que o "Renumerar agora"
        tem por construção, e que a mantenedora já mediu).

        Passo a passo, com os dois registros juntos (a fila é ÚNICA entre
        DualSense e externos — EXT-04/NUM-01, e é dessa unicidade que sai a
        garantia de nunca haver dois "Controle 1"):

        1. junta os PRESENTES dos dois registros como ``(lugar, key,
           registro)`` e ordena por lugar — esta é, por definição de
           ``slot_for``, a ordem em que eles exibem 1..N; **as duas recusas
           saem daqui, antes de qualquer escrita**, porque pertinência e
           contagem não dependem da ordem;
        1a. manda o registro dos DualSense ALINHAR o gravado com a tela
           (``alinhar_gravado_com_a_tela``) — sem isso o plano é calculado
           sobre uma mesa que não é a que ela está vendo — e relê a mesa se
           algo mudou de lugar;
        2. TROCA as posições ``indice_atual`` e ``numero - 1`` dessa lista;
        3. redistribui os MESMOS lugares, na ordem crescente, para a lista
           reordenada;
        4. entrega a cada registro só a fatia de keys que é dele — do lado
           DualSense por ``escolha_da_mao``, que faz a fila do momento
           concordar com a escolha (senão o congelamento a apaga em 4,0 s);
           do lado dos externos por ``compact``, que é onde eles moram.
           Os dois persistem sob o ``CONTROLLERS_FILE_LOCK``.

        Empate de lugar entre os dois lados (só possível por corrupção do
        arquivo) desempata a favor do DualSense — a MESMA regra do
        cross-check do ``load``, do ``merged_order_payload`` e do
        ``_posicao_locked``, para a ordem gravada e a exibida nunca
        discordarem.

        Erros (todos ANTES de qualquer escrita): alvo fora dos presentes →
        :class:`_NumeroAlvoAusenteError`; número acima da quantidade de
        presentes → :class:`_NumeroForaDaMesaError`. ``authority_check`` é a
        re-checagem F3 pós-acquire, idêntica à do ``_renumber_locked``.
        """
        with contextlib.ExitStack() as locks:
            for reg in (identity_registry, external_registry):
                acquire = getattr(reg, "lock_for_renumber", None)
                if callable(acquire):
                    locks.enter_context(acquire())

            if callable(authority_check) and authority_check() == "game":
                raise _RenumberAuthorityChangedError()

            def _mesa_presente() -> list[tuple[int, int, str, Any]]:
                """Os ASSENTOS dos dois registros (ligados e guardados), por lugar."""
                mesa: list[tuple[int, int, str, Any]] = []
                for ordem_kind, registry in enumerate(
                    (identity_registry, external_registry)
                ):
                    if registry is None:
                        continue
                    conectados = _chaves_dos_assentos(registry)
                    mesa.extend(
                        (lugar, ordem_kind, key, registry)
                        for key, lugar in registry.snapshot().items()
                        if key in conectados
                    )
                mesa.sort(key=lambda e: (e[0], e[1], e[2]))
                return mesa

            presentes = _mesa_presente()

            # pertinência e "o número cabe?" é contagem — e o alinhamento
            if not any(e[2] == alvo and _ligado(e) for e in presentes):
                raise _NumeroAlvoAusenteError()
            if _fora_da_mesa(presentes, numero):
                raise _NumeroForaDaMesaError(sum(1 for e in presentes if _ligado(e)))

            alinhar = getattr(identity_registry, "alinhar_gravado_com_a_tela", None)
            if callable(alinhar) and alinhar():
                presentes = _mesa_presente()

            indice_atual = next(
                pos for pos, e in enumerate(presentes) if e[2] == alvo
            )

            lugares = [e[0] for e in presentes]
            nova_ordem = list(presentes)
            indice_alvo = numero - 1
            nova_ordem[indice_atual], nova_ordem[indice_alvo] = (
                nova_ordem[indice_alvo],
                nova_ordem[indice_atual],
            )

            mudou: dict[str, int] = {}
            por_registro: dict[int, dict[str, int]] = {}
            for pos, (lugar_atual, ordem_kind, key, registry) in enumerate(
                nova_ordem
            ):
                novo_lugar = lugares[pos]
                if novo_lugar != lugar_atual:
                    mudou[key] = novo_lugar
                por_registro.setdefault(ordem_kind, {})[key] = novo_lugar
                del registry

            if identity_registry is not None and por_registro.get(0):
                aplicar = getattr(identity_registry, "escolha_da_mao", None)
                if not callable(aplicar):
                    aplicar = identity_registry.compact
                aplicar(por_registro[0])
            if external_registry is not None and por_registro.get(1):
                external_registry.compact(por_registro[1])

            return mudou

    @staticmethod
    def _connected_keys(registry: Any) -> set[str]:
        """Keys CONECTADAS de um registro de identidade (R-15), com fallback."""
        if registry is None:
            return set()
        fn = getattr(registry, "snapshot_connected", None)
        if callable(fn):
            with contextlib.suppress(Exception):
                return {str(key) for key in fn()}
        with contextlib.suppress(Exception):
            return {str(key) for key in registry.snapshot()}
        return set()

    @staticmethod
    def _renumber_locked(
        identity_registry: Any,
        external_registry: Any,
        authority_check: Callable[[], str] | None = None,
    ) -> dict[str, int]:
        """Corpo BLOQUEANTE de `identity.renumber` — só via `asyncio.to_thread`."""
        with contextlib.ExitStack() as locks:
            for reg in (identity_registry, external_registry):
                acquire = getattr(reg, "lock_for_renumber", None)
                if callable(acquire):
                    locks.enter_context(acquire())

            if callable(authority_check) and authority_check() == "game":
                raise _RenumberAuthorityChangedError()

            entries: list[tuple[bool, int, str, Any]] = []
            for registry in (identity_registry, external_registry):
                if registry is None:
                    continue
                conectados = IpcHandlersMixin._connected_keys(registry)
                entries.extend(
                    (key not in conectados, slot, key, registry)
                    for key, slot in registry.snapshot().items()
                )
            if not entries:
                return {}

            entries.sort(key=lambda entry: (entry[0], entry[1]))
            renumbered: dict[str, int] = {}
            identity_map: dict[str, int] = {}
            external_map: dict[str, int] = {}
            for novo_lugar, (_offline, lugar_atual, key, registry) in enumerate(
                entries, start=1
            ):
                if lugar_atual != novo_lugar:
                    renumbered[key] = novo_lugar
                if registry is identity_registry:
                    identity_map[key] = novo_lugar
                else:
                    external_map[key] = novo_lugar

            if identity_registry is not None and identity_map:
                identity_registry.compact(identity_map)
            if external_registry is not None and external_map:
                external_registry.compact(external_map)

            return renumbered


    async def _handle_daemon_status(self, params: dict[str, Any]) -> dict[str, Any]:
        self._agendar_arming_do_launch()
        snap = self.store.snapshot()
        # teste medindo essa divergência aqui (ao contrário do `state_full`,
        # fonte (store) que `state_full` usa é o que evita as três rotas
        controller = snap.controller
        return {
            "connected": bool(controller and controller.connected),
            "transport": controller.transport if controller else None,
            "active_profile": snap.active_profile,
            # BG-02 (25/08): a MESMA chave viaja no `state_full` desde hoje, e
            "pontes_confirmadas": _pontes_confirmadas_seguro(),
            "battery_pct": controller.battery_pct if controller else None,
            "paused": bool(self.daemon is not None and self.daemon.is_paused()),
            "freestyle_ligado": bool(self.store.freestyle_ligado),
            "native_mode": bool(
                self.daemon is not None and self.daemon.is_native_mode()
            ),
            "emulation_suppressed": bool(
                self.daemon is not None
                and getattr(self.daemon, "_emulation_suppressed", False)
            ),
            # `state_full` (mesma razão do `window_detect_*`: duas respostas que
            "keyboard_emulation": self._keyboard_emulation_payload(),
            # `state_full`, para as duas respostas nunca divergirem.
            **self._window_detect_payload(),
        }

    def _keyboard_emulation_payload(self) -> dict[str, Any]:
        """Bloco `keyboard_emulation` publicado por `state_full` e `daemon.status`.

        EMULACAO-NO-JOGO-01. Ela desligou "o modo mouse teclado" e o teclado
        continuou emitindo Alt+Tab dentro do jogo — porque aquele interruptor
        governa só o mouse e o teclado não tinha interruptor NENHUM, nem chave
        neste payload. As quatro chaves respondem, em ordem, às quatro perguntas
        que a aba Emulação precisa fazer:

        - `enabled`   -- o interruptor (`config.keyboard_emulation_enabled`,
                         persistido em `keyboard_emulation.flag`);
        - `device_ativo` -- o teclado virtual existe agora (`_keyboard_device`);
        - `despachando`  -- ele emitiria tecla NESTE instante (é a conjunção
                         completa do gate do poll loop);
        - `bloqueio`  -- POR QUE não emitiria: `"desligada"`, `"sem_device"`,
                         `"modo_jogo"` (a supressão que ela chama de modo jogo)
                         ou `null` quando emite.

        A quinta chave é de outra natureza e entrou em 10/08/2026
        (TECLADO-QUE-NAO-DIGITA-01):

        - `osk_disponivel` -- há teclado na tela instalado na MÁQUINA. É o que
                         decide se o L3 (`__TOGGLE_OSK__`, o de fábrica)
                         abre alguma coisa ou só avisa que não tem o que abrir —
                         e, como nenhum dos nove atalhos de fábrica digita uma
                         LETRA, é também o que decide se existe algum caminho
                         para ESCREVER TEXTO com o controle.

        Por que sai DAQUI e não de um `shutil.which` na janela: num Flatpak a
        janela olharia dentro do sandbox e responderia sobre uma máquina que não
        é a dela. O daemon é quem enxerga o host e é quem vai spawnar o
        processo — a resposta tem de vir de quem executa.

        `getattr` defensivo em tudo: daemon/config dublados em teste não precisam
        conhecer os campos novos, e este handler roda a 10-20 Hz.
        """
        daemon = self.daemon
        cfg = getattr(daemon, "config", None) if daemon is not None else None
        enabled = bool(getattr(cfg, "keyboard_emulation_enabled", False))
        device_ativo = bool(getattr(daemon, "_keyboard_device", None) is not None)
        bloqueio = self._bloqueio_da_emulacao_de_desktop(
            enabled=enabled, device_ativo=device_ativo
        )
        osk_disponivel = False
        with contextlib.suppress(Exception):
            controlador = getattr(daemon, "_osk_controller", None)
            if controlador is not None:
                osk_disponivel = bool(controlador.disponivel())
            else:
                from hefesto_dualsense4unix.daemon.subsystems.keyboard import (
                    osk_disponivel_no_sistema,
                )

                osk_disponivel = bool(osk_disponivel_no_sistema())
        return {
            "enabled": enabled,
            "device_ativo": device_ativo,
            "despachando": bloqueio is None,
            "bloqueio": bloqueio,
            "osk_disponivel": osk_disponivel,
        }

    def _bloqueio_da_emulacao_de_desktop(
        self, *, enabled: bool, device_ativo: bool
    ) -> str | None:
        """Por que a emulação de DESKTOP não emitiria agora, ou `None` se emite.

        UM DONO SÓ, e é este método. O mouse e o teclado de desktop são calados
        pela MESMA conjunção — `lifecycle._poll_loop` decide os dois no mesmo
        `if` (`emu_active = not self._emulation_suppressed`) e só então pergunta,
        para cada um, se o device existe. Escrever a leitura duas vezes é como as duas
        respostas divergem: o teclado dizendo "modo jogo" e o mouse dizendo
        "ligado e feliz" no mesmo instante, sobre o mesmo controle.

        Só os dois termos que DIFEREM entram por parâmetro (`enabled` é a flag
        de cada um na config; `device_ativo` é `_mouse_device` ou
        `_keyboard_device`). A ordem das respostas é a de quem lê a tela: o
        interruptor primeiro, depois o device, depois o jogo — a primeira coisa
        a consertar é a primeira que aparece.

        Vocabulário (o mesmo dos dois payloads, e o que
        `app/actions/mouse_actions.BLOQUEIO_DO_MOUSE_EM_PORTUGUES` traduz):
        `"desligada"`, `"sem_device"` e `"modo_jogo"`.
        """
        daemon = self.daemon
        if not enabled:
            return "desligada"
        if not device_ativo:
            return "sem_device"
        if bool(getattr(daemon, "_emulation_suppressed", False)):
            return "modo_jogo"
        return None

    def _bloqueio_do_mouse(self) -> str | None:
        """Por que o cursor NÃO andaria agora, ou `None` se ele anda.

        MOUSE-SEM-RAZÃO-01 (25/08/2026, BG-02). *"Ela liga o mouse pelo
        controle, o cursor não anda, e a aba não diz por quê."* As três razões
        reais — o interruptor desligado, a permissão de `/dev/uinput` e o modo
        jogo — o daemon conhecia uma a uma e não publicava nenhuma.

        A permissão de `uinput` entra por `device_ativo`, e é a peça que a
        janela não tem como olhar sozinha: `UinputMouseDevice.start()` falha sem
        acesso ao nó e `_mouse_device` fica `None` com o interruptor EM PÉ (a
        flag persistida religa no boot; o device não sobe). Uma sonda de
        `os.access` na janela responderia pelo processo dela — dentro de um
        Flatpak, pelo sandbox — e não por quem abre o device.

        `getattr` defensivo: daemon/config dublados em teste não conhecem os
        campos, e isto roda no caminho do `state_full` (10-20 Hz).
        """
        daemon = self.daemon
        cfg = getattr(daemon, "config", None) if daemon is not None else None
        return self._bloqueio_da_emulacao_de_desktop(
            enabled=bool(getattr(cfg, "mouse_emulation_enabled", False)),
            device_ativo=getattr(daemon, "_mouse_device", None) is not None,
        )

    def _mouse_emulation_payload(self) -> dict[str, Any]:
        """Bloco `mouse_emulation` do `state_full` — o estado E a razão.

        As três chaves de sempre são FEAT-CLI-PARITY-01 (o `mouse status` da
        CLI lê daqui). As três novas são BG-02, e são o molde do vizinho
        `_keyboard_emulation_payload`, chave por chave, de propósito:

        - `device_ativo` -- o mouse virtual existe AGORA;
        - `despachando`  -- ele moveria o cursor neste instante;
        - `bloqueio`     -- por que não moveria (ver `_bloqueio_do_mouse`).

        Chamado sob o guard `daemon_cfg is not None` do `state_full`: sem config
        acessível o bloco continua OMITIDO, e o cliente lê a ausência como
        "estado indisponível" — que é o contrato desde o FEAT-CLI-PARITY-01.
        """
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        bloqueio = self._bloqueio_do_mouse()
        return {
            "enabled": bool(getattr(daemon_cfg, "mouse_emulation_enabled", False)),
            "speed": int(getattr(daemon_cfg, "mouse_speed", 6)),
            "scroll_speed": int(getattr(daemon_cfg, "mouse_scroll_speed", 1)),
            "device_ativo": getattr(self.daemon, "_mouse_device", None) is not None,
            "despachando": bloqueio is None,
            "bloqueio": bloqueio,
        }

    def _steam_input_payload(self) -> dict[str, bool]:
        """A exceção do Steam Input ativa agora (JOGO-01): o jogo da allowlist aberto."""
        daemon = self.daemon
        return {
            "excecao_ativa": bool(getattr(daemon, "_steam_input_excecao", False)),
        }

    def _jogo_steam_payload(self) -> dict[str, Any]:
        """Bloco `jogo_steam` do `state_full` — o TRI-ESTADO, inteiro.

        ABA-DO-JOGO-01. `lido` é a peça que não pode faltar: sem ela, `appid:
        null` responderia "não há jogo" e "o daemon acabou de subir e ainda não
        perguntou" com a mesma palavra, e a aba "No jogo" piscaria a cada
        restart do daemon (ver `StateStore.set_steam_jogo_appid`).

        Coerção defensiva nos dois campos, e ela é o de sempre nesta função:
        store dublado por `MagicMock` devolve um mock para qualquer atributo, e
        um mock no `result` estoura na serialização JSON do IPC — não aqui, mas
        no cliente, que é onde o defeito fica caro de achar.
        """
        lido = getattr(self.store, "steam_jogo_lido", None) is True
        appid_raw = getattr(self.store, "steam_jogo_appid", None)
        appid = (
            int(appid_raw)
            if isinstance(appid_raw, int) and not isinstance(appid_raw, bool)
            else None
        )
        return {"lido": lido, "appid": appid if lido else None}

    def _window_detect_payload(self) -> dict[str, Any]:
        """Bloco `window_detect_*` publicado por `state_full` e `daemon.status`.

        FEAT-WINDOW-DETECT-DIAG-01 (backend/healthy/last_class) + JANELA-CEGA-01
        (current_class, useful_age_sec, seeing, reason). Os quatro novos existem
        porque os três antigos, sozinhos, MENTIAM: medido ao vivo em 28/07, o
        daemon publicava `last_class="Hefesto-Dualsense4Unix"` (a própria
        janela) e `healthy=True` enquanto o backend devolvia `None` a 2 Hz, com
        `get_input_focus()` em `X.NONE` nas 10 amostras. `last_class` é STICKY e
        nunca decai; `healthy` é um trinco de mão única (ver a property no
        `StateStore` para o porquê de ele NÃO poder cair ainda).

        - `current_class`  -- a leitura CRUA do último tick (inclusive
                              "unknown"/None): a classe que o detector vê AGORA;
        - `useful_age_sec` -- há quantos segundos foi a última leitura ÚTIL
                              (None = nunca houve): é ela que denuncia a
                              cegueira ao lado do sticky;
        - `seeing`         -- houve leitura útil dentro da janela de
                              `WINDOW_DETECT_BLIND_AFTER_SEC` (decai e volta);
        - `reason`         -- POR QUE a última leitura não foi útil.

        `getattr` defensivo em tudo: store dublado em teste não precisa
        conhecer os campos novos.
        """
        idade_fn = getattr(self.store, "window_detect_useful_age", None)
        idade = idade_fn() if callable(idade_fn) else None
        seeing_fn = getattr(self.store, "window_detect_seeing", None)
        return {
            "window_detect_backend": _as_str_or_none(
                getattr(self.store, "window_detect_backend", None)
            ),
            "window_detect_healthy": bool(
                getattr(self.store, "window_detect_healthy", False)
            ),
            "window_detect_last_class": _as_str_or_none(
                getattr(self.store, "window_detect_last_class", None)
            ),
            "window_detect_current_class": _as_str_or_none(
                getattr(self.store, "window_detect_current_class", None)
            ),
            "window_detect_useful_age_sec": (
                round(float(idade), 1) if isinstance(idade, (int, float)) else None
            ),
            "window_detect_seeing": (
                bool(seeing_fn()) if callable(seeing_fn) else False
            ),
            "window_detect_reason": _as_str_or_none(
                getattr(self.store, "window_detect_reason", None)
            ),
        }

    async def _handle_daemon_pause(self, params: dict[str, Any]) -> dict[str, Any]:
        """Pausa o despacho de input sem matar o daemon (FEAT-DAEMON-PAUSE-RESUME-01)."""
        self.daemon.pause()
        return {"status": "ok", "paused": True}

    async def _handle_daemon_resume(self, params: dict[str, Any]) -> dict[str, Any]:
        """Retoma o despacho de input (FEAT-DAEMON-PAUSE-RESUME-01)."""
        self.daemon.resume()
        return {"status": "ok", "paused": False}

    async def _handle_freestyle_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Liga/desliga o Modo Freestyle — o botão «Modo Freestyle» da aba Jogar.

        O-FREESTYLE-E-UMA-CAMADA-SO-01 (28/09/2026), no lugar do `autoswitch.lock`
        (o cadeado de 23/07, que cedia a todo perfil de jogo). A palavra dela:
        *«Aperto o botão do freestyle e o jogo que eu tiver jogando vai ter essa
        config independente do perfil do jogo.»*  (noqa-acento: citação dela)

        `ligado` opcional: ausente → inverte.

        **LIGAR É O «ATIVAR» DO FREESTYLE NA ABA PERFIS**, e é o mesmo caminho:
        o `profile.switch` dele, com a ativação à mão, que liga o modo SEMPRE
        (`profiles.manager`, `D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`). Ligado,
        nenhum caminho automático troca o perfil.

        **DESLIGAR DEVOLVE A ESCOLHA DELA NA HORA** (item 3 da decisão), sem
        depender do leitor de janela — no COSMIC sem portal o autoswitch não
        acha janela nunca. Com jogo vivo, o jogo volta por cima
        (`origin="launch"`), e a escolha fica a de antes; sem jogo, a escolha
        (`origin="system"`); sem escolha, nenhum perfil ativo (item 10, «Fica
        sem perfil», dela em 29/09 ~20h35). A trava da troca à mão solta junto,
        com a linha no diário.
        """
        from hefesto_dualsense4unix.profiles.loader import NOME_DO_PADRAO
        from hefesto_dualsense4unix.profiles.manager import (
            o_freestyle_manda,
            soltar_a_trava_da_mao,
        )

        pedido = params.get("ligado")
        if pedido is not None and not isinstance(pedido, bool):
            raise ValueError("freestyle.set: 'ligado' precisa ser boolean")
        novo = (not o_freestyle_manda(self.store)) if pedido is None else pedido
        if novo:
            resposta = await self._handle_profile_switch({"name": NOME_DO_PADRAO})
        else:
            soltar_a_trava_da_mao(self.store, "freestyle_desligado")
            resposta = await self._o_que_volta_sem_o_freestyle()
        resposta["status"] = "ok"
        resposta["freestyle_ligado"] = o_freestyle_manda(self.store)
        logger.info("freestyle_set", ligado=resposta["freestyle_ligado"])
        return resposta

    async def _o_que_volta_sem_o_freestyle(self) -> dict[str, Any]:
        """O botão apagado: o jogo vivo, ou a escolha dela, ou nenhum perfil."""
        from hefesto_dualsense4unix.profiles.autoswitch import jogo_do_wrapper_vivo
        from hefesto_dualsense4unix.profiles.manager import perfil_do_appid
        from hefesto_dualsense4unix.utils.session import a_escolha_dela

        perfil = None
        with contextlib.suppress(Exception):
            appid = jogo_do_wrapper_vivo()
            perfil = perfil_do_appid(appid) if appid is not None else None
        nome, origem = (perfil.name, "launch") if perfil is not None else (
            a_escolha_dela(freestyle_ligado=False), "system")
        relatorio: dict[str, str] = {}
        self.profile_manager.apagar_o_freestyle(nome, origin=origem, relatorio=relatorio)
        if self.daemon is not None:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.launch_env import (
                    materialize_launch_env,
                )

                materialize_launch_env(self.daemon)
        return {"active_profile": self.store.active_profile, "secoes": dict(relatorio)}

    async def _handle_native_mode_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Liga/desliga o Modo Nativo — "release total" do controle (FEAT-NATIVE-MODE-01)."""
        if self.daemon is None:
            raise RuntimeError("daemon indisponível")
        raw = params.get("enabled")
        if raw is None:
            enabled = not self.daemon.is_native_mode()
        elif isinstance(raw, bool):
            enabled = raw
        else:
            raise ValueError("native.mode.set exige 'enabled' boolean ou omitido")
        origem = origem_do_pedido(params)
        if enabled and origem == "manual":
            new_state = self.daemon.set_native_mode(
                enabled, origin=origem, grava_o_modo=_porta_que_grava(origem)
            )
        else:
            new_state = self.daemon.set_native_mode(enabled, origin=origem)
        return {"status": "ok", "native_mode": bool(new_state)}

    async def _handle_daemon_state_full(self, params: dict[str, Any]) -> dict[str, Any]:
        """Estado completo pra GUI consumir a 20Hz."""
        snap = self.store.snapshot()
        state = (
            getattr(self.daemon, "_last_state", None) if self.daemon else None
        ) or snap.controller

        stale_warn_threshold = 3
        if (
            state is not None
            and self.controller.is_connected()
            and state.raw_lx == 128
            and state.raw_ly == 128
            and state.raw_rx == 128
            and state.raw_ry == 128
            and state.l2_raw == 0
            and state.r2_raw == 0
            and not state.buttons_pressed
        ):
            stale_count = self.store.bump("state_full.stale_neutral")
            if stale_count == stale_warn_threshold:
                logger.warning(
                    "state_stale_neutral_warning",
                    state_full_calls=stale_count,
                    hint="evdev_reader pode não ter conectado; HID-raw fallback estagnado",
                )

        buttons: list[str] = sorted(state.buttons_pressed) if state else []
        # `battery_pct` para ler `self.controller.describe_controllers()`
        result: dict[str, Any] = {
            "connected": bool(state and state.connected),
            "transport": state.transport if state else None,
            "active_profile": snap.active_profile,
            "battery_pct": state.battery_pct if state else None,
            "l2_raw": state.l2_raw if state else 0,
            "r2_raw": state.r2_raw if state else 0,
            "lx": state.raw_lx if state else 128,
            "ly": state.raw_ly if state else 128,
            "rx": state.raw_rx if state else 128,
            "ry": state.raw_ry if state else 128,
            "buttons": buttons,
            "counters": snap.counters,
            "paused": bool(self.daemon is not None and self.daemon.is_paused()),
            "freestyle_ligado": bool(self.store.freestyle_ligado),
            "native_mode": bool(
                self.daemon is not None and self.daemon.is_native_mode()
            ),
            "native_mode_origin": _as_str_or_none(
                getattr(self.store, "native_mode_origin", None)
            ),
            "mode_from_profile": _as_str_or_none(
                getattr(self.daemon, "_mode_from_profile", None)
                if self.daemon is not None
                else None
            ),
            "primary_grab_state": _as_str_or_none(
                getattr(
                    getattr(self.controller, "_evdev", None), "grab_state", None
                )
            ),
            "emulation_suppressed": bool(
                self.daemon is not None
                and getattr(self.daemon, "_emulation_suppressed", False)
            ),
            # estar calado. Ver `_keyboard_emulation_payload` (mesmo bloco do
            "keyboard_emulation": self._keyboard_emulation_payload(),
            "steam_input": self._steam_input_payload(),
            **self._window_detect_payload(),
        }
        result["game_signal"] = self._game_signal_snapshot()

        result["jogo_steam"] = self._jogo_steam_payload()

        result["pontes_confirmadas"] = self._pontes_confirmadas_no_tique()

        describe = getattr(self.controller, "describe_controllers", None)
        if callable(describe):
            controllers = describe()
            result["controllers"] = controllers
            if self.daemon is not None and isinstance(controllers, list):
                from hefesto_dualsense4unix.daemon.subsystems.coop import (
                    resolve_player_numbers,
                )

                entries = [c for c in controllers if isinstance(c, dict)]
                with contextlib.suppress(Exception):
                    for entry, number in zip(
                        entries,
                        resolve_player_numbers(self.daemon, entries),
                        strict=True,
                    ):
                        entry["player"] = number
            if isinstance(controllers, list):
                with contextlib.suppress(Exception):
                    self._enriquecer_e_medir_o_ar(
                        result, [c for c in controllers if isinstance(c, dict)], state
                    )

        # estruturalmente frágil — o SDL pode não enxergar o DualSense BT nem
        # lista `controllers` já montada e já enriquecida com o `player_slot` —
        entradas_de_controle = result.get("controllers")
        frageis = controles_bt_frageis(
            entradas_de_controle, native_mode=result["native_mode"]
        )
        conhece_a_mesa = isinstance(entradas_de_controle, list) and any(
            isinstance(e, dict) and e.get("connected") for e in entradas_de_controle
        )
        result["native_bt_fragil_controles"] = frageis
        result["native_bt_fragil"] = bool(
            frageis
            if conhece_a_mesa
            else (result["native_mode"] and result["transport"] == "bt")
        )

        # CONTROLE-QUE-NAO-ENTROU-01 (09/08/2026): fica AO LADO do bloco
        # `controllers` de propósito — é a resposta à pergunta que aquele bloco
        # não consegue responder. `controllers` tem uma entrada por handle
        # ABERTO; um controle cuja probe abortou no kernel não tem handle
        # nenhum, e some da lista sem deixar rastro. Sem esta chave, a única
        # coisa que o produto tinha a dizer sobre ele era "Nenhum controle
        result["controles_sem_driver"] = self._controles_sem_driver_payload()

        get_target = getattr(self.controller, "get_output_target_index", None)
        target_index: int | None = None
        if callable(get_target):
            raw_target = get_target()
            if isinstance(raw_target, int) and not isinstance(raw_target, bool):
                target_index = raw_target
        result["output_target_index"] = target_index

        from hefesto_dualsense4unix.daemon.subsystems.ouvinte_do_som import (
            som_do_sistema_payload,
        )

        result["som_do_sistema"] = som_do_sistema_payload(self.daemon)

        # `keyboard_emulation` acima, porque é o mesmo gate do poll loop.
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is not None:
            result["mouse_emulation"] = self._mouse_emulation_payload()
            _flavor_da_sessao = str(getattr(daemon_cfg, "gamepad_flavor", "dualsense"))
            result["gamepad_emulation"] = {
                "enabled": bool(getattr(daemon_cfg, "gamepad_emulation_enabled", False)),
                "flavor": _flavor_da_sessao,
                "por_aparelho": _mascaras_por_aparelho(self),
                # cartão do P1 em Xbox 360 o chip «Sony DualSense» ficava aceso
                # `backend` abaixo não separa o Xbox escolhido do DualSense que
                "caminho": _caminho_publicado(self.daemon),
            }
            # UHID-04: backend do vpad primário VIVO ("uhid" = DualSense Edge real
            gp_dev = getattr(self.daemon, "_gamepad_device", None)
            if gp_dev is not None:
                with contextlib.suppress(Exception):
                    result["gamepad_emulation"]["backend"] = str(
                        getattr(gp_dev, "backend", "") or ""
                    )
                with contextlib.suppress(Exception):
                    result["gamepad_emulation"]["ff_supported"] = bool(
                        getattr(gp_dev, "ff_supported", False)
                    )
                with contextlib.suppress(Exception):
                    # MODO-DE-CONEXAO-01: e só quem PEDIU o canal do DualSense
                    from hefesto_dualsense4unix.integrations.virtual_pad import (
                        motivo_da_degradacao,
                    )

                    motivo = motivo_da_degradacao(gp_dev)
                    result["gamepad_emulation"]["degraded"] = motivo is not None
                    if motivo is not None:
                        result["gamepad_emulation"]["degraded_motivo"] = motivo
                # respondia: *"o jogo está vendo um DualSense por um canal que
                # DualSense de pé e o caminho Xbox, a tela diz «Sony DualSense»
                with contextlib.suppress(Exception):
                    from hefesto_dualsense4unix.integrations import (
                        canal_sem_imu as _sem_imu,
                    )

                    sem_imu = _sem_imu.canal_sem_imu_do_vpad(gp_dev)
                    result["gamepad_emulation"]["canal_sem_imu"] = sem_imu
                    if sem_imu:
                        result["gamepad_emulation"]["canal_sem_imu_linhas"] = list(
                            _sem_imu.chaves_fora_do_ar()
                        )
            # nunca aqui (o state_full roda a 20 Hz — seria flood).
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                    dedup_status,
                )

                dedup_ok, motivos = dedup_status(self.daemon)
                result["gamepad_emulation"]["dedup_ok"] = dedup_ok
                if motivos:
                    result["gamepad_emulation"]["dedup_motivo"] = ", ".join(motivos)
            result["gamepad_emulation"]["wrapper_used"] = None
            with contextlib.suppress(Exception):
                wrapper_used = self._wrapper_used_now()
                result["gamepad_emulation"]["wrapper_used"] = wrapper_used
                if (
                    wrapper_used is False
                    and result["gamepad_emulation"].get("enabled")
                    and not result.get("native_mode")
                    and result["gamepad_emulation"].get("dedup_ok", False)
                ):
                    result["gamepad_emulation"]["dedup_ok"] = False
                    motivo_atual = result["gamepad_emulation"].get("dedup_motivo")
                    result["gamepad_emulation"]["dedup_motivo"] = (
                        f"{motivo_atual}, jogo_sem_wrapper"
                        if motivo_atual
                        else "jogo_sem_wrapper"
                    )
            # handler — o `state_full` roda a 10-20 Hz e ler perfis do disco
            result["gamepad_emulation"]["mascara_divergente"] = None
            result["gamepad_emulation"]["mascara_divergencias"] = []
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.launch_env import (
                    divergencias_publicadas,
                )

                divergencias = divergencias_publicadas(self.daemon)
                result["gamepad_emulation"]["mascara_divergencias"] = divergencias
                em_cena = [d for d in divergencias if d.get("em_cena")]
                if em_cena:
                    result["gamepad_emulation"]["mascara_divergente"] = em_cena[0]
            result["perfil_do_jogo_que_nao_entrou"] = self._perfil_que_nao_entrou()
            coop_mgr = getattr(self.daemon, "_coop_manager", None)
            players_raw = coop_mgr.player_count() if coop_mgr is not None else 1
            result["coop"] = {
                "enabled": bool(getattr(daemon_cfg, "coop_enabled", False)),
                "players": players_raw if isinstance(players_raw, int) else 1,
            }
            result["coop"]["mesa"] = []
            if coop_mgr is not None:
                with contextlib.suppress(Exception):
                    mesa = coop_mgr.mesa()
                    if isinstance(mesa, list):
                        result["coop"]["mesa"] = [
                            item for item in mesa if isinstance(item, dict)
                        ]
            # quem tem vpad do hefesto — com 2 DualSense e 2 Pro vivos ele diz
            # neste caminho (o state_full roda a 10 Hz).
            registro_ext = getattr(self.daemon, "external_registry", None)
            conectados = getattr(registro_ext, "snapshot_connected", None)
            if callable(conectados):
                with contextlib.suppress(Exception):
                    vistos = conectados()
                    if isinstance(vistos, (set, frozenset)):
                        result["coop"]["externals"] = len(vistos)
            rumble_mult_applied = float(getattr(self.daemon, "_last_auto_mult", 1.0))
            result["rumble_policy"] = str(getattr(daemon_cfg, "rumble_policy", "balanceado"))
            result["rumble_policy_custom_mult"] = float(
                getattr(daemon_cfg, "rumble_policy_custom_mult", 0.7)
            )
            result["rumble_mult_applied"] = rumble_mult_applied
            result["rumble_motores"] = {}
            result["rumble_motor_pct_padrao"] = MOTOR_PCT_PADRAO
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                    _motores_do_perfil_ativo,
                )

                result["rumble_motores"] = {
                    uniq: {"forte_pct": par[0], "fraco_pct": par[1]}
                    for uniq, par in _motores_do_perfil_ativo(self.daemon).items()
                }

            # enxerga o vpad (ex.: máscara DualSense atraindo o hidraw do
            vpads: list[tuple[int, Any, Any]] = []
            coop_mgr = getattr(self.daemon, "_coop_manager", None)
            # chegada, ler `player_index` aqui cruzaria os fios — o card de um
            # controle mostraria a telemetria do vpad de OUTRO. As condições
            numeros_por_mac: dict[str, int] = {}
            if (
                bool(getattr(getattr(self.daemon, "config", None), "coop_enabled", False))
                and coop_mgr is not None
            ):
                with contextlib.suppress(Exception):
                    numeros_por_mac = dict(coop_mgr.player_indexes())
            gp_device = getattr(self.daemon, "_gamepad_device", None)
            if gp_device is not None:
                primario = _as_str_or_none(
                    getattr(self.controller, "primary_uniq", None)
                )
                vpads.append(
                    (
                        int(numeros_por_mac.get(primario or "", 1) or 1),
                        gp_device,
                        getattr(self.daemon, "_motion_reader", None),
                    )
                )
            if coop_mgr is not None:
                players = getattr(coop_mgr, "_players", {})
                if isinstance(players, dict):
                    vpads.extend(
                        (
                            int(
                                numeros_por_mac.get(
                                    mac, getattr(p, "player_index", 0) or 0
                                )
                                or 0
                            ),
                            p.vpad,
                            getattr(p, "motion_reader", None),
                        )
                        for mac, p in players.items()
                        if getattr(p, "vpad", None) is not None
                    )
            ff_plays = 0
            ff_nao_nulos = 0
            ff_descartados = 0
            ff_v2 = 0
            ff_paradas = 0
            ff_estranhos = 0
            ff_last: tuple[int, int] = (0, 0)
            per_vpad: list[dict[str, Any]] = []
            from hefesto_dualsense4unix.daemon.subsystems.coop import (
                identidade_do_vpad,
            )

            for player_num, vp, motion_reader in vpads:
                with contextlib.suppress(Exception):
                    ff_plays += int(getattr(vp, "ff_play_count", 0) or 0)
                    ff_nao_nulos += int(getattr(vp, "ff_nao_nulo_count", 0) or 0)
                    ff_descartados += int(getattr(vp, "ff_descartado_count", 0) or 0)
                    ff_v2 += int(getattr(vp, "ff_v2_count", 0) or 0)
                    ff_paradas += int(getattr(vp, "ff_parada_sdl_count", 0) or 0)
                    ff_estranhos += int(
                        getattr(vp, "ff_report_estranho_count", 0) or 0
                    )
                    last = getattr(vp, "ff_last_sent", None)
                    if isinstance(last, tuple) and len(last) == 2 and last != (0, 0):
                        ff_last = (int(last[0]), int(last[1]))
                with contextlib.suppress(Exception):
                    backend = getattr(vp, "backend", None)
                    streaming = getattr(vp, "motion_streaming", False)
                    hz_raw = getattr(motion_reader, "emit_hz", 0.0)
                    # do nó — `vpad_uniq` (o `02:fe:…` que sai no `HID_UNIQ` do
                    # sysfs), `vpad_nome` e `vpad_indice`. O objeto sempre soube
                    identidade = identidade_do_vpad(vp)
                    no_do_vpad = self._no_do_vpad_cached(
                        identidade["vpad_uniq"], identidade["vpad_nome"]
                    )
                    per_vpad.append(
                        {
                            "player": player_num,
                            "vpad_uniq": identidade["vpad_uniq"],
                            "vpad_nome": identidade["vpad_nome"],
                            "vpad_indice": identidade["vpad_indice"],
                            "evdev": no_do_vpad["evdev"],
                            "hidraw": no_do_vpad["hidraw"],
                            "ino": no_do_vpad["ino"],
                            "hidraw_ino": no_do_vpad["hidraw_ino"],
                            "game_open": getattr(vp, "game_open", False) is True,
                            "backend": backend if isinstance(backend, str) else None,
                            "ff_play_count": int(getattr(vp, "ff_play_count", 0) or 0),
                            "ff_nao_nulo_count": int(
                                getattr(vp, "ff_nao_nulo_count", 0) or 0
                            ),
                            "ff_maior_pedido": _par_de_motores(
                                getattr(vp, "ff_maior_pedido", None)
                            ),
                            "ff_descartado_count": int(
                                getattr(vp, "ff_descartado_count", 0) or 0
                            ),
                            "ff_descartado_amostra": _amostra_de_descarte(
                                getattr(vp, "ff_descartado_amostra", None)
                            ),
                            "ff_v2_count": int(getattr(vp, "ff_v2_count", 0) or 0),
                            "ff_parada_sdl_count": int(
                                getattr(vp, "ff_parada_sdl_count", 0) or 0
                            ),
                            "ff_report_estranho_count": int(
                                getattr(vp, "ff_report_estranho_count", 0) or 0
                            ),
                            "ff_report_estranho_amostra": _report_estranho(
                                getattr(vp, "ff_report_estranho_amostra", None)
                            ),
                            "ff_ultimos_reports": _anel_de_vibracao(
                                getattr(vp, "ff_ultimos_reports", None)
                            ),
                            "output_count": int(getattr(vp, "output_count", 0) or 0),
                            "trigger_replicas": int(
                                getattr(vp, "trigger_replicas", 0) or 0
                            ),
                            "lightbar_replicas": int(
                                getattr(vp, "lightbar_replicas", 0) or 0
                            ),
                            "player_led_replicas": int(
                                getattr(vp, "player_led_replicas", 0) or 0
                            ),
                            "motion_streaming": (
                                streaming if isinstance(streaming, bool) else False
                            ),
                            "motion_hz": (
                                float(hz_raw)
                                if isinstance(hz_raw, (int, float))
                                and not isinstance(hz_raw, bool)
                                else 0.0
                            ),
                            "touchpad_clicks": int(
                                getattr(vp, "touchpad_click_count", 0) or 0
                            ),
                            "touchpad_pressionado": bool(
                                getattr(vp, "touchpad_click", False) is True
                            ),
                            "motion_forwards": _contador_do_vpad(
                                vp, "motion_forward_count"
                            ),
                            "jack": _jack_do_vpad(vp),
                            "jack_forwards": _contador_do_vpad(
                                vp, "jack_forward_count"
                            ),
                            # `battery_pct` do controle FÍSICO que a aba Status
                            "bateria_no_jogo": _bateria_do_vpad(vp),
                            "battery_forwards": _contador_do_vpad(
                                vp, "battery_forward_count"
                            ),
                            "mic_button_forwards": _contador_do_vpad(
                                vp, "mic_button_count"
                            ),
                            **_o_microfone_do_jogo_no_vpad(vp),
                            "rumble_no_fisico": _par_de_motores(
                                getattr(vp, "rumble_no_fisico", None)
                            ),
                            "rumble_no_fisico_ha_s": _idade_ou_none(
                                getattr(vp, "rumble_no_fisico_ha_s", None)
                            ),
                            "visto_ha_s": _visto_ha_s(vp),
                            "audio_do_jogo_amostra": _audio_do_jogo_amostra(vp),
                        }
                    )
            result["rumble_ff"] = {
                "plays": ff_plays,
                "nao_nulos": ff_nao_nulos,
                "descartados": ff_descartados,
                "v2": ff_v2,
                "paradas": ff_paradas,
                "estranhos": ff_estranhos,
                "last_weak": ff_last[0],
                "last_strong": ff_last[1],
                "vpads": len(vpads),
                "per_vpad": per_vpad,
            }
            hotkey_cfg = getattr(
                getattr(self.daemon, "_hotkey_manager", None), "config", None
            )
            if hotkey_cfg is not None:
                buffer_ms = getattr(hotkey_cfg, "buffer_ms", None)
                passthrough = getattr(hotkey_cfg, "passthrough_in_emulation", None)
                if isinstance(buffer_ms, int) and not isinstance(buffer_ms, bool):
                    result["hotkey"] = {
                        "buffer_ms": buffer_ms,
                        "passthrough_in_emulation": bool(passthrough),
                    }
            result["mic_button_toggles_system"] = bool(
                getattr(daemon_cfg, "mic_button_toggles_system", True)
            )
            from hefesto_dualsense4unix.daemon.subsystems.bt_mic import (
                habilitado_por_env,
                uniqs_pedidos,
            )

            bt_mic_sub = getattr(self.daemon, "_bt_mic_subsystem", None)
            com_ponte: list[str] = []
            motivo = ""
            if bt_mic_sub is not None:
                with contextlib.suppress(Exception):
                    com_ponte = sorted(bt_mic_sub.uniqs_com_ponte())
                with contextlib.suppress(Exception):
                    motivo = str(bt_mic_sub.motivo)
            result["bt_mic"] = {
                "enabled": bool(uniqs_pedidos(daemon_cfg)) or habilitado_por_env(),
                "running": bt_mic_sub is not None,
                "uniqs": com_ponte,
                "motivo": motivo,
            }
            rumble_active = getattr(daemon_cfg, "rumble_active", None)
            result["rumble_passthrough"] = rumble_active is None
            result["rumble_active"] = (
                [int(rumble_active[0]), int(rumble_active[1])]
                if rumble_active is not None
                else None
            )

        # casa: a `audio` sumia do `state_full` no hotplug-out e `bool(None)`
        result["mic_da_mesa"] = recado_do_microfone.publicar(self.daemon)

        return result


    def _enrich_controllers_per_controller(
        self, entries: list[dict[str, Any]], state: Any
    ) -> None:
        """Enriquece cada entrada de `controllers` com o estado POR CONTROLE.

        Campos novos (sempre presentes — shape estável para GUI/CLI/applet;
        os campos PRÉ-existentes não mudam):

        - ``serial``/``modelo``/``nome_declarado`` (ROTA-A, 02/09/2026): QUEM É
          este aparelho, e nunca a posição dele na lista. Ver
          :meth:`_identidade_publicada` — os três nascem ``None`` e só saem do
          ``None`` com fonte.
        - ``player_slot``: número de sessão do CONTROLE (COR-01/D6), do
          `identity_registry` do daemon — consulta DEFENSIVA com
          ``assign=False`` (ler estado nunca aloca slot). O registry é
          entregue por outra frente; ausente → None.
        - ``lightbar_rgb``/``lightbar_on``/``lightbar_source``: a cor efetiva
          CONHECIDA (o que está/estaria aceso), decidida pelo DONO DA ESCRITA:
          * ``"sysfs"`` — nó gravável (mapa `_sysfs` do backend) E escrito por
            nós (rastreio `_sysfs_written`, com o priming do
            `_refresh_sysfs_leds` garantindo o frescor): a leitura da classe
            LED é a verdade. SÓ neste estado ``(0, 0, 0)`` significa
            "apagada" (refutação 1 do sprint).
          * ``"desired"`` — nó não-gravável/fora do mapa (a escrita foi por
            hidraw → classe stale POR CONSTRUÇÃO) mas o backend conhece a
            última cor mandada aplicar (`resolved_led_for`).
          * ``"desconhecida"`` — nada conhecido (rgb None; NUNCA rotular de
            "apagada" — o LED pode estar brilhando o azul-kernel agora).
          Modo Nativo: a matriz NÃO muda, e a tela também não — desde a
          `D-2309-NO-NATIVO-A-LUZ-E-O-NUMERO-SAO-DO-HEFESTO` a barra é do
          Hefesto no Nativo, e o «o jogo é dono do LED» saiu da tela em
          24/09/2026 (`D-2409-NO-NATIVO-A-TELA-MOSTRA-A-COR`).

        - ``lightbar_disputada`` (ESCRITOR-CRU-01): ``True`` quando outro
          processo — hoje só a Steam é reconhecida — segura o ``hidraw``
          DESTE controle. É o aviso de que ``lightbar_rgb`` acima é a cor
          PEDIDA e pode não ser a acesa: escrita crua por hidraw não atualiza
          a classe LED, e a madrugada de 16/08 mediu o mesmo ``[0 255 0]`` com
          a barra apagada e com ela verde. Sai da FOTO do sentinela do daemon
          (tique de 30 s) — este handler não toca ``/proc``.

          Contrato de cor (D8 — divergência fundamentada, registrada
          na onda): expõe-se UMA cor, a efetiva conhecida
          (pós-escala de brilho — o `_DesiredOutput.led` já é pós-escala; o
          manager pré-escala na borda). O par pré/pós-brilho do D8 original
          exigiria refactor do estado desejado fora do escopo; a legibilidade
          de cor escura (objetivo do D8) é da tela, pela borda de
          `integrations/cor_do_plastico.tom_para_a_borda`.
        - ``brilho_da_barra``/``brilho_das_luzes`` (A-04-PERGUNTA-AO-DAEMON-VIVO-01):
          o brilho em que ``lightbar_rgb`` foi acesa e o degrau das luzes de
          número que o merge manda, com a camada da usuária. ``None`` = não
          sei. Ver :meth:`_brilhos_acesos`.
        - ``nascimento`` (SINAL-NO-NASCIMENTO-01/E2): como a CONEXÃO deste
          controle nasceu, ou ``None`` = **não carimbei** (nunca "limpa"). É a
          RAZÃO que faltava ao botão "A luz não acende" do card: enquanto o
          veredito condena esta instância, a tela pode dizer por quê. Sai do
          cartório que o tique de hotplug já carimbou — ver
          :meth:`_nascimento_para` para as chaves e para o custo (zero).

        - ``inputs``: ``{lx,ly,rx,ry,l2_raw,r2_raw,buttons}`` — mais as chaves
          OPCIONAIS ``gyro`` (``{x,y,z}`` em graus/s) e ``touchpad``
          (``{touching,x,y,width,height}``) quando o controle tem os nodes
          evdev correspondentes (S2, via `SensorHub`) — ou None.

          **TRÊS FONTES, nesta ordem, e a ordem é o contrato:**

          1. O PRIMÁRIO espelha o `state` do topo do payload
             (`daemon._last_state` — a MESMA fonte, nunca um snapshot evdev
             paralelo: armadilha A-09). Quando `state` é None ele fica em
             None e NÃO cai para a fonte 3: o card e o topo do payload têm de
             dizer a mesma coisa sobre o mesmo controle.
          2. Secundário que o co-op promoveu: `CoopManager.live_snapshots()`
             (leitura não-destrutiva por MAC).
          3. **STATUS-04 (04/09/2026)** — qualquer outro controle conectado:
             um `EvdevReader` PASSIVO, sem grab, do `SensorHub`
             (:meth:`_inputs_passivos`). É o que cura a mesa pela metade nos
             modos em que o co-op está desmontado — modo Nativo, emulação
             off, suspensão por Steam Input —, em que o secundário publicava
             `inputs: None` **por desenho**, não por falta de dado.

          Sem nenhuma das três → None (o card mostra "—", nunca um valor
          congelado fingindo vida).
        - ``vpad_backend``/``vpad_motivo`` (BT-03): backend real do vpad DO
          JOGADOR deste controle ("uhid" | "uinput") e o motivo quando
          degradado (máscara DualSense em uinput — `fallback_motivo` que a
          factory pendurou: "uhid_indisponivel", "uhid_start_falhou",
          "uhid_bind_falhou", "uhid_vetado_pelo_chamador"; ou "sem_uhid").
          Estende o `dedup_status` (DEDUP-06), que agrega por jogador — aqui
          o dado sai POR CONTROLE: primário → `_gamepad_device`; secundário
          promovido → o vpad dele no co-op; controle que não é jogador com
          vpad próprio (co-op off/pending/emulação off) → None. Máscara xbox
          é uinput POR DESIGN → nunca tem motivo.

        Custo: leituras sysfs no MÁXIMO 1x/s por nó (`_lightbar_read_cached`);
        o resto é leitura de atributos. Nada aqui toca hardware.
        """
        sysfs_map = getattr(self.controller, "_sysfs", None)
        written_map = getattr(self.controller, "_sysfs_written", None)
        node_by_uniq: dict[str, Any] = {}
        written_by_uniq: dict[str, tuple[int, int, int]] = {}
        if isinstance(sysfs_map, dict):
            for key, node in sysfs_map.items():
                uniq = _norm_uniq(key)
                if uniq is not None and node is not None:
                    node_by_uniq[uniq] = node
        if isinstance(written_map, dict):
            for key, raw in written_map.items():
                uniq = _norm_uniq(key)
                rgb = _rgb_or_none(raw)
                if uniq is not None and rgb is not None:
                    written_by_uniq[uniq] = rgb

        nos_por_uniq: dict[str, str] = {}
        mapear = getattr(self.controller, "nos_hidraw_por_uniq", None)
        if callable(mapear):
            with contextlib.suppress(Exception):
                nos_por_uniq = dict(mapear() or {})

        snapshots = self._coop_live_snapshots()
        com_leitor_coop = self._coop_uniqs_com_leitor()
        vpad_by_uniq = self._coop_vpads_by_uniq()
        gp_dev = (
            getattr(self.daemon, "_gamepad_device", None)
            if self.daemon is not None
            else None
        )

        for entry in entries:
            uniq = entry.get("uniq")
            uniq = uniq if isinstance(uniq, str) and uniq else None

            entry["player_slot"] = self._player_slot_for(uniq)

            entry.update(self._identidade_publicada(entry, uniq))

            rgb, on, source = self._lightbar_for_uniq(
                uniq, node_by_uniq, written_by_uniq
            )
            entry["lightbar_rgb"] = list(rgb) if rgb is not None else None
            entry["lightbar_on"] = on
            entry["lightbar_source"] = source
            entry["lightbar_disputada"] = self._lightbar_disputada(uniq, nos_por_uniq)
            entry["nascimento"] = self._nascimento_para(uniq)
            entry.update(self._brilhos_acesos(uniq))
            entry["luz_do_jogo"] = self._luz_do_jogo(uniq)

            if entry.get("is_primary") and state is not None:
                entry["inputs"] = self._inputs_from_state(state)
            elif uniq is not None and uniq in snapshots:
                entry["inputs"] = self._inputs_from_snapshot(snapshots[uniq])
            else:
                entry["inputs"] = self._inputs_passivos(entry, uniq, com_leitor_coop)
            self._merge_sensores(entry, uniq)
            self._merge_audio(entry, uniq)

            backend, motivo = (None, None)
            if entry.get("is_primary") and gp_dev is not None:
                backend, motivo = self._vpad_backend_motivo(gp_dev)
            elif uniq is not None and uniq in vpad_by_uniq:
                backend, motivo = vpad_by_uniq[uniq]
            entry["vpad_backend"] = backend
            entry["vpad_motivo"] = motivo

        self._agenda_de_identidade().esquecer_ausentes(
            {
                str(entry["uniq"])
                for entry in entries
                if entry.get("connected") and isinstance(entry.get("uniq"), str)
            }
        )

    def _identidade_publicada(
        self, entry: dict[str, Any], uniq: str | None
    ) -> dict[str, str | None]:
        """``{serial, modelo, nome_declarado}`` deste controle. ``None`` = não sei.

        ROTA-A (02/09/2026). O defeito que ela viu: com UM controle o do cabo
        chamava-se "Starlight Blue"; com DOIS, o MESMO cabo virou "Cosmic Red".
        **O nome vinha da POSIÇÃO na lista**, porque o daemon publicava `uniq`,
        `transport`, `battery_pct`, `player`, `player_slot`, `lightbar_*`,
        `inputs`, `audio`, `speaker`, `vpad_*` — e NADA que identificasse o
        aparelho. Quem desenha a tela não tinha alternativa senão inventar.

        As três chaves, e cada uma tem fonte diferente:

        * ``nome_declarado`` — **o que ELA nomeou**, de `maquina.json`
          (`controles[<uniq>].cor`, texto livre, decisão C2). Zero I/O aqui: o
          daemon já carrega o documento em `_maquina` no boot e o REBINDA no
          "Aplicar" do `machine.declare`;
        * ``modelo`` — o nome de fábrica decodificado dos caracteres 5 e 6 do
          serial (`integrations/cor_do_plastico`);
        * ``serial`` — o serial de fábrica de 17 caracteres, cru.

        **A DISCIPLINA É `None`, e ela é o ponto inteiro desta onda.** Um
        ``modelo=None`` honesto vira travessão na tela; um modelo inventado é
        exatamente o defeito que se está curando. Não há default, não há queda
        para "DualSense", não há tabela por VID/PID.

        **POR QUE A LEITURA É DAQUI, e não de um instrumento paralelo:** ler o
        serial é um `SET_FEATURE` da família `0x80`, e a armadilha nº 3 desta
        casa é o instrumento que disputa o hidraw com o daemon e imprime
        "aplicado" sem ter aplicado. O daemon é quem tem o aparelho.

        **E POR QUE ELA NÃO ACONTECE NESTA FUNÇÃO:** este handler roda a 10 Hz.
        A leitura sai numa thread, uma em voo por `uniq`, e o tique publica o
        que já se sabe. Enquanto não voltar, sai ``None``, que é a verdade
        daquele instante.
        """
        declarado: str | None = None
        maquina = getattr(self.daemon, "_maquina", None) if self.daemon else None
        controles = getattr(maquina, "controles", None)
        if uniq and isinstance(controles, dict):
            declaracao = controles.get(uniq)
            bruto = getattr(declaracao, "cor", None)
            declarado = bruto.strip() if isinstance(bruto, str) and bruto.strip() else None

        de_fabrica = self._identidade_de_fabrica(uniq, entry)
        return {
            "serial": de_fabrica["serial"],
            "modelo": de_fabrica["modelo"],
            "nome_declarado": declarado,
        }

    def _identidade_de_fabrica(
        self, uniq: str | None, entry: dict[str, Any]
    ) -> dict[str, str | None]:
        """``{serial, modelo}`` do cache de sessão, disparando a leitura se for a hora."""
        vazio: dict[str, str | None] = {"serial": None, "modelo": None}
        if not uniq or not entry.get("connected"):
            return dict(vazio)
        cache = self._identidade_de_fabrica_cache
        if cache is None:
            cache = {}
            self._identidade_de_fabrica_cache = cache
        pronto = cache.get(uniq)
        if pronto is not None:
            return dict(pronto)
        # chega, e este `state_full` lê o MESMO cache, sem uma segunda
        # com um objeto verdadeiro, e ele iria parar no JSON do `state_full`.
        dono = getattr(self, "daemon", None)
        registro: Any = getattr(dono, "identity_registry", None) if dono else None
        if getattr(registro, "pergunta_de_fabrica_armada", False) is True:
            achado = registro.identidade_de_fabrica(uniq)
            if achado is None:
                registro.agendar_a_pergunta_de_fabrica(uniq)
                return dict(vazio)
            serial = getattr(achado, "serial", None)
            nome = getattr(getattr(achado, "cor", None), "nome", None)
            return {
                "serial": serial if isinstance(serial, str) else None,
                "modelo": nome if isinstance(nome, str) else None,
            }
        if self._agenda_de_identidade().reservar(uniq):
            try:
                import threading

                threading.Thread(
                    target=self._perguntar_identidade,
                    args=(uniq,),
                    name=f"identidade-{uniq[:6]}",
                    daemon=True,
                ).start()
            except Exception:
                with contextlib.suppress(Exception):
                    from hefesto_dualsense4unix.integrations.cor_do_plastico import (
                        IdentidadeDeFabrica,
                    )

                    self._agenda_de_identidade().registrar(
                        uniq, IdentidadeDeFabrica(motivo="a thread não nasceu")
                    )
        return dict(vazio)

    def _agenda_de_identidade(self) -> Any:
        """A `AgendaDaPergunta` desta instância, criada no primeiro uso."""
        agenda = getattr(self, "_agenda_da_identidade", None)
        if agenda is None:
            from hefesto_dualsense4unix.integrations.cor_do_plastico import (
                AgendaDaPergunta,
            )

            agenda = AgendaDaPergunta()
            self._agenda_da_identidade = agenda
        return agenda

    def _perguntar_identidade(self, uniq: str) -> None:
        """A leitura, fora do laço. Só a RESPOSTA entra no cache."""
        from hefesto_dualsense4unix.integrations.cor_do_plastico import (
            IdentidadeDeFabrica,
            ler_identidade_pelo_cabo,
        )

        achado = IdentidadeDeFabrica(motivo="a leitura não devolveu")
        try:
            achado = ler_identidade_pelo_cabo(uniq)
        except Exception as erro:
            achado = IdentidadeDeFabrica(motivo=f"a leitura levantou {type(erro).__name__}")
        finally:
            if achado.definitiva:
                cache = self._identidade_de_fabrica_cache
                if cache is None:
                    cache = {}
                    self._identidade_de_fabrica_cache = cache
                cache[uniq] = {
                    "serial": achado.serial,
                    "modelo": None if achado.cor is None else achado.cor.nome,
                }
            self._agenda_de_identidade().registrar(uniq, achado)

    def _merge_sensores(self, entry: dict[str, Any], uniq: str | None) -> None:
        """Acrescenta `gyro`/`touchpad` ao `inputs` deste controle (S2)."""
        inputs = entry.get("inputs")
        if uniq is None or not isinstance(inputs, dict):
            return
        hub = self._sensor_hub
        if hub is None:
            from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub

            hub = SensorHub()
            self._sensor_hub = hub
        leitura: Any = None
        with contextlib.suppress(Exception):
            leitura = hub.leitura(uniq)
        if isinstance(leitura, dict):
            inputs.update(leitura)
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.core.virtual_motion import REGISTRO

            estado = REGISTRO.estado(uniq)
            entry["sensores"] = {
                "giroscopio_ligado": estado.giroscopio,
                "acelerometro_ligado": estado.acelerometro,
                "grab_do_movimento": self._grab_do_movimento(hub, uniq),
            }

    @staticmethod
    def _grab_do_movimento(hub: Any, uniq: str) -> str:
        """`off|pending|held|failed|sem_reader` do nó de movimento de `uniq`.

        Via `getattr` porque o hub é dublado em régua (`_HandlerFalso` e
        amigos): um hub sem o método é "não sei", nunca uma exceção que
        derrube o `state_full` inteiro por causa de um selo.
        """
        perguntar = getattr(hub, "grab_do_movimento", None)
        if not callable(perguntar):
            return "desconhecido"
        try:
            return str(perguntar(uniq))
        except Exception:
            return "desconhecido"

    def _garantir_sensor_hub(self) -> Any:
        """O `SensorHub` desta sessão, criado no primeiro uso (S2/STATUS-04)."""
        hub = self._sensor_hub
        if hub is None:
            from hefesto_dualsense4unix.daemon.sensor_hub import SensorHub

            hub = SensorHub()
            self._sensor_hub = hub
        return hub

    def _inputs_passivos(
        self, entry: dict[str, Any], uniq: str | None, com_leitor_coop: set[str]
    ) -> dict[str, Any] | None:
        """Entrega STATUS-04: `inputs` de quem não tem NENHUMA outra fonte.

        Escrita em 17/07/2026 e adiada com razão medida — *"co-op é DEFAULT ON
        (…) no estado normal da máquina dela, TODO secundário já tem reader
        (…) O buraco real é o modo Nativo e emulação-off"*. A razão continua
        de pé (medido em 04/09/2026 com os dois DualSense dela em USB e co-op
        ligado: os dois já traziam `inputs`, e este caminho não abriu reader
        nenhum). O que caducou foi tratar o buraco como hipotético: nos modos
        em que o co-op se desmonta, metade da mesa ficava muda — e nesses
        modos ela está JOGANDO, que é quando o card importa.

        As TRÊS recusas, e cada uma evita uma mentira diferente:

        - **primário** — cair aqui seria publicar um snapshot evdev paralelo
          ao `state` do topo do payload (armadilha A-09): dois números para o
          mesmo controle no mesmo tique. `state is None` significa "o daemon
          não está lendo", e o card tem de dizer isso.
        - **desconectado** — abrir node de quem saiu da mesa.
        - **controle que o co-op já segura** (inclusive o pendente de grab,
          que o `live_snapshots` exclui de propósito): o node está sob
          `EVIOCGRAB` do reader dele e um fd passivo não recebe evento NENHUM.
          É a entrega (c) do STATUS-04 — *"ceder o leitor quando o co-op
          assume"* — e MEDIDO no hardware dela em 04/09/2026 é pior do que
          parece: o reader passivo abre sem erro e publica a posição REAL de
          repouso lida do `absinfo` (`lx=129 ly=130 rx=127 ry=130`), parada
          para sempre. Não é um zero reconhecível — é um número plausível e
          congelado, e um card alimentado por ele parece um controle que
          ninguém está tocando.

        Custo quando não há o que fazer: um `set` de MACs e três `if`. Nada de
        I/O — a descoberta e a abertura moram na thread de manutenção do hub.
        """
        if uniq is None or entry.get("is_primary") or not entry.get("connected"):
            return None
        if uniq in com_leitor_coop:
            return None
        leitura: Any = None
        with contextlib.suppress(Exception):
            leitura = self._garantir_sensor_hub().entradas(uniq)
        return leitura if isinstance(leitura, dict) else None

    def _coop_uniqs_com_leitor(self) -> set[str]:
        """MACs cujo node de gamepad o co-op já abriu (promovido OU pendente)."""
        coop = (
            getattr(self.daemon, "_coop_manager", None)
            if self.daemon is not None
            else None
        )
        players = getattr(coop, "_players", None) if coop is not None else None
        if not isinstance(players, dict):
            return set()
        return {
            mac
            for mac in players
            if isinstance(mac, str) and mac and not mac.startswith("path:")
        }

    def _merge_audio(self, entry: dict[str, Any], uniq: str | None) -> None:
        """Acrescenta `audio` e `speaker` a ESTE controle (AUDIO-STATUS-01 / D4).

        Duas chaves independentes, as duas OPCIONAIS (a GUI esconde o bloco em
        vez de desenhar valor inventado — mesma disciplina do `gyro`/`touchpad`):

        - ``audio`` = ``{fone_plugado, mic_externo, mic_mudo}``. É LEITURA de
          verdade: sai do byte de estado que vem em todo report de INPUT do
          controle (o mesmo que a ponte de mic por BT já decodificava e
          consumia internamente sem nunca publicar). Ausente enquanto nenhum
          report tiver sido lido daquele controle.
        - ``audio.mic_mudo_desejado`` (MIC-USB-01) = QUEM MANDA no mudo do
          firmware, e não o que está valendo. ``true``/``false`` = o hefesto é
          o dono e está afirmando esse valor em todo report (veio de um
          `mic.set`); ``null`` = a posse é do `hid-playstation`, que alterna o
          mudo na borda do botão físico. A chave só entra quando o backend sabe
          responder (`microphone_mute_for`) — daemon/dublê sem o método deixa a
          ausência falar, como o resto do bloco. Sem ela a aba Status não tem
          como escolher entre "aperte o botão do controle" e "desmute pela
          janela": as duas frases descrevem `mic_mudo: true`, e só uma resolve.
        - ``speaker`` = ``{volume: 0-255, muted: bool}`` (+ as chaves de
          ``audio``, quando conhecidas). **Só aparece quando o hefesto é o dono
          do volume**, e a razão é dura: o DualSense NÃO devolve o volume — não
          há report de input nem feature report que o leia. Só sabemos o volume
          que NÓS mandamos. Antes de o primeiro `speaker.set` acontecer, o dono
          é o firmware e qualquer número que publicássemos aqui seria chute.

        `_enrich_controllers_per_controller` já roda dentro de um `suppress`,
        mas cada leitura é defensiva por conta própria (controller dublado em
        teste, backend sem os métodos).
        """
        status: Any = None
        status_fn = getattr(self.controller, "audio_status_for", None)
        if callable(status_fn):
            with contextlib.suppress(Exception):
                status = status_fn(uniq)
        if isinstance(status, dict):
            dono_fn = getattr(self.controller, "microphone_mute_for", None)
            if callable(dono_fn):
                desejado: Any = None
                with contextlib.suppress(Exception):
                    desejado = dono_fn(uniq)
                status["mic_mudo_desejado"] = (
                    bool(desejado) if isinstance(desejado, bool) else None
                )
            # roda no tique do `state_full`, a 20 Hz, dentro do loop do daemon.
            from hefesto_dualsense4unix.daemon.subsystems.hotkey import (
                canal_do_microfone,
            )

            lido = canal_do_microfone(uniq)
            if isinstance(lido, dict):
                status["canal_ativo"] = bool(lido.get("canal_ativo"))
                status["canal_mudo"] = lido.get("canal_mudo")
                status["volume_captura"] = lido.get("volume_captura")
                status["canal_fonte"] = lido.get("fonte")
            from hefesto_dualsense4unix.daemon.subsystems.luz_do_mic import (
                estado_da_luz_do_mic,
                quem_ouve_este_mic,
            )

            luz = estado_da_luz_do_mic(str(uniq or ""))
            if luz is not None:
                status["luz_do_mic"] = int(luz)
            _a_luz_do_jogo_no_controle(status, uniq)
            ouvintes = quem_ouve_este_mic(str(uniq or ""))
            if ouvintes is not None:
                status["ouvintes_do_mic"] = list(ouvintes)
            entry["audio"] = status

        speaker: Any = None
        speaker_fn = getattr(self.controller, "speaker_state_for", None)
        if callable(speaker_fn):
            with contextlib.suppress(Exception):
                speaker = speaker_fn(uniq)
        if not isinstance(speaker, dict):
            return
        volume = speaker.get("volume")
        if not isinstance(volume, int) or isinstance(volume, bool):
            return
        bloco: dict[str, Any] = {
            "volume": max(0, min(255, volume)),
            "muted": bool(speaker.get("muted")),
        }
        # "rota": 0}}`) e o `state_full` não a publicava. Quem trocasse a saída
        rota = speaker.get("rota")
        if isinstance(rota, int) and not isinstance(rota, bool):
            bloco["rota"] = rota
        from hefesto_dualsense4unix.integrations.alto_falante_bt import (
            fonte_publicada,
        )

        fonte = fonte_publicada(str(uniq or ""))
        if fonte:
            bloco["fonte"] = fonte
        if isinstance(status, dict):
            bloco.update(status)
        entry["speaker"] = bloco
        inputs = entry.get("inputs")
        if isinstance(inputs, dict):
            inputs["speaker"] = dict(bloco)

    def _lightbar_for_uniq(
        self,
        uniq: str | None,
        node_by_uniq: dict[str, Any],
        written_by_uniq: dict[str, tuple[int, int, int]],
    ) -> tuple[tuple[int, int, int] | None, bool, str]:
        """(rgb, on, source) de UM controle, pelo dono da escrita (STATUS-01)."""
        if uniq is not None:
            node = node_by_uniq.get(uniq)
            if node is not None and uniq in written_by_uniq:
                rgb, node_on = self._lightbar_read_cached(node)
                if rgb is not None:
                    return rgb, bool(node_on and rgb != (0, 0, 0)), "sysfs"
            resolved = getattr(self.controller, "resolved_led_for", None)
            if callable(resolved):
                rgb = None
                with contextlib.suppress(Exception):
                    rgb = _rgb_or_none(resolved(uniq))
                if rgb is not None:
                    return rgb, rgb != (0, 0, 0), "desired"
        return None, False, "desconhecida"

    def _brilhos_acesos(self, uniq: str | None) -> dict[str, Any]:
        """Os dois brilhos que ESTE controle acende agora — sempre as duas chaves.

        A-04-PERGUNTA-AO-DAEMON-VIVO-01, 25/09/2026. A regra da casa é
        *pergunte ao daemon vivo, não ao perfil*, e a aba Iluminação lia os dois
        do disco. A camada da usuária (R-20) atravessa a troca AUTOMÁTICA de
        perfil, e medido na mesa de quatro real: o P3 clicado em Forte seguia
        Forte no aparelho depois do autoswitch para um perfil que diz Fraco, e
        a pílula acendia Fraco; o P1 a 60% pelo trilho seguia a 60%, e o
        trilho dizia 82%.

        - ``brilho_da_barra``: ``0.0``-``1.0``, o brilho em que a cor publicada
          em ``lightbar_rgb`` foi acesa (`brilho_da_barra_para` do backend);
        - ``brilho_das_luzes``: ``"fraco"``, ``"medio"`` ou ``"forte"``, o (noqa-acento)
          degrau das luzes de número que o merge manda ao aparelho
          (`brilho_das_luzes_para`), na palavra do perfil.

        QUEM DECIDE É O DONO DO MERGE; aqui só se lê. ``None`` é «não sei» —
        backend sem as leituras, controle sem MAC, perfil que não publicou o
        brilho, ou a cor que chegou sem ele —, e quem lê cai no disco, como
        fazia antes. Nada aqui toca hardware.
        """
        from hefesto_dualsense4unix.core.led_control import BRILHOS_DAS_LUZES

        saida: dict[str, Any] = {"brilho_da_barra": None, "brilho_das_luzes": None}
        if uniq is None:
            return saida
        barra = getattr(self.controller, "brilho_da_barra_para", None)
        if callable(barra):
            with contextlib.suppress(Exception):
                brilho = barra(uniq)
                if isinstance(brilho, (int, float)) and not isinstance(brilho, bool):
                    saida["brilho_da_barra"] = max(0.0, min(1.0, float(brilho)))
        luzes = getattr(self.controller, "brilho_das_luzes_para", None)
        if callable(luzes):
            with contextlib.suppress(Exception):
                degrau = luzes(uniq)
                if isinstance(degrau, int) and not isinstance(degrau, bool):
                    saida["brilho_das_luzes"] = next(
                        (p for p, d in BRILHOS_DAS_LUZES.items() if d == degrau), None
                    )
        return saida

    def _luz_do_jogo(self, uniq: str | None) -> bool:
        """``True`` quando o JOGO pinta a barra deste controle agora (sempre publicado).

        O-DESLIGADO-DEIXA-O-JOGO-DECIDIR-01, item 3 (04/10/2026): a aba Iluminação diz «Agora: a cor
        do jogo» só com isto. Quem decide é o dono do merge (`luz_do_jogo_para`); aqui só se lê, e
        backend sem a leitura, ou controle sem endereço, é ``False`` — nunca um «talvez».
        """
        leitor = getattr(self.controller, "luz_do_jogo_para", None)
        if uniq is None or not callable(leitor):
            return False
        with contextlib.suppress(Exception):
            return leitor(uniq) is True
        return False

    def _lightbar_disputada(
        self, uniq: str | None, nos_por_uniq: dict[str, str]
    ) -> bool:
        """True quando OUTRO processo segura o hidraw DESTE controle.

        ESCRITOR-CRU-01 — o campo existe porque a aba Status estava mentindo, e
        a mentira era honesta: com nó gravável e escrita nossa registrada, ela
        mostra a leitura de ``multi_intensity`` como "a cor efetiva". A
        madrugada de 16/08 mediu que esse valor é o mesmo `[0 255 0]` com a
        barra APAGADA e com ela VERDE — o sysfs guarda o PEDIDO, nunca o
        aceso. Enquanto houver escritor cru, o que a tela pode afirmar é *"esta
        é a cor que o Hefesto pediu"*, e é isso que este booleano diz à GUI.

        Sai da foto que o sentinela do daemon já tirou (o tique de 30 s do
        `reconnect_loop`). O status é consultado a cada segundo pela GUI —
        SONDAR `/proc` aqui seria um `pgrep` por segundo, e o defeito que essa
        sonda existe para curar não vale esse preço.

        **ESCRITOR-CRU-03 (19/09/2026): a foto é CONFERIDA, não repetida.** Ela
        era devolvida crua, e então este campo contava o passado no presente:
        medido em 19/09, a Steam levou SIGTERM, `pgrep` devolveu zero, e sete
        segundos depois o `state_full` ainda dizia ``True``. Pior, há estados
        em que ninguém zera a foto NUNCA — em Modo Nativo o vigia não sonda, e
        sem nó mapeado ele desiste antes.

        `segurado_de_fato` não sonda: ele confere se os PIDs que a foto já
        guarda ainda EXISTEM, a um `stat` em `/proc/<pid>` cada. É a diferença
        entre medir e lembrar, e só pode apagar um aviso — nunca acender um.

        ``False`` também é a resposta quando NADA foi sondado ainda. É
        deliberado e é a disciplina desta casa: ausência de sonda não é prova
        de que ninguém segura, e um aviso ligado por falta de dado treinaria a
        usuária a ignorá-lo.
        """
        if uniq is None:
            return False
        no = nos_por_uniq.get(uniq)
        if not no or self.daemon is None:
            return False
        sentinela = getattr(self.daemon, "_sentinela_de_escritor_cru", None)
        # `isinstance`, e não pato: o daemon é MagicMock em boa parte da suíte,
        if not isinstance(sentinela, _escritor_cru.SentinelaDeEscritorCru):
            return False
        return bool(sentinela.veredito.segurado_de_fato(no))

    def _nascimento_para(self, uniq: str | None) -> dict[str, Any] | None:
        """Como a conexão DESTE controle nasceu; ``None`` = **não carimbei**."""
        if uniq is None or self.daemon is None:
            return None
        cartorio = getattr(self.daemon, "_cartorio_do_nascimento", None)
        if not isinstance(cartorio, _sinal_da_barra.CartorioDoNascimento):
            return None
        carimbo = cartorio.do_uniq(uniq)
        if carimbo is None:
            return None
        return {
            "confianca": str(carimbo.confianca),
            "porque": str(carimbo.porque),
            "pede_reconexao": bool(carimbo.pede_reconexao),
            "instancia": str(carimbo.instancia),
            "hw_version": str(carimbo.hw_version),
            "firme": bool(carimbo.firme),
        }

    def _lightbar_read_cached(
        self, node: Any
    ) -> tuple[tuple[int, int, int] | None, bool]:
        """Leitura (rgb, brightness>0) de um nó LED com cache TTL por nó.

        STATUS-01: o `state_full` roda a 10 Hz e `get_rgb`/`is_on` são I/O de
        arquivo — o cache garante no máximo 1 leitura/s por nó
        (`_LIGHTBAR_READ_TTL_SEC`). Keyed pelo `indicator_dir` (estável por nó
        e muda quando o kernel recria o nó — invalidação natural no replug).
        """
        cache = self._lightbar_read_cache
        if cache is None:
            cache = {}
            self._lightbar_read_cache = cache
        cache_key = str(getattr(node, "indicator_dir", "") or f"id:{id(node)}")
        now = time.monotonic()
        hit = cache.get(cache_key)
        if hit is not None and (now - hit[0]) < _LIGHTBAR_READ_TTL_SEC:
            return hit[1], hit[2]
        rgb: tuple[int, int, int] | None = None
        on = False
        with contextlib.suppress(Exception):
            rgb = _rgb_or_none(node.get_rgb())
        with contextlib.suppress(Exception):
            on = bool(node.is_on())
        if len(cache) > 64:
            cache.clear()
        cache[cache_key] = (now, rgb, on)
        return rgb, on

    def _player_slot_for(self, uniq: str | None) -> int | None:
        """Slot de sessão do controle `uniq` via identity_registry (COR-01/D9)."""
        if uniq is None or self.daemon is None:
            return None
        registry = getattr(self.daemon, "identity_registry", None)
        slot_for = getattr(registry, "slot_for", None) if registry is not None else None
        if not callable(slot_for):
            return None
        raw: Any = None
        with contextlib.suppress(Exception):
            raw = slot_for(uniq, assign=False)
        if isinstance(raw, int) and not isinstance(raw, bool):
            return raw
        return None

    @staticmethod
    def _inputs_from_state(state: Any) -> dict[str, Any] | None:
        """Inputs do PRIMÁRIO a partir do `state` do topo (`daemon._last_state`)."""
        try:
            return {
                "lx": int(state.raw_lx),
                "ly": int(state.raw_ly),
                "rx": int(state.raw_rx),
                "ry": int(state.raw_ry),
                "l2_raw": int(state.l2_raw),
                "r2_raw": int(state.r2_raw),
                "buttons": sorted(state.buttons_pressed),
            }
        except (AttributeError, TypeError, ValueError):
            return None

    @staticmethod
    def _inputs_from_snapshot(snap: Any) -> dict[str, Any] | None:
        """Inputs de um secundário a partir do `EvdevSnapshot` do reader dele."""
        try:
            return {
                "lx": int(snap.lx),
                "ly": int(snap.ly),
                "rx": int(snap.rx),
                "ry": int(snap.ry),
                "l2_raw": int(snap.l2_raw),
                "r2_raw": int(snap.r2_raw),
                "buttons": sorted(snap.buttons_pressed),
            }
        except (AttributeError, TypeError, ValueError):
            return None

    def _coop_live_snapshots(self) -> dict[str, Any]:
        """`CoopManager.live_snapshots()` com blindagem de dublês de teste."""
        coop = (
            getattr(self.daemon, "_coop_manager", None)
            if self.daemon is not None
            else None
        )
        live = getattr(coop, "live_snapshots", None) if coop is not None else None
        if not callable(live):
            return {}
        out: Any = None
        with contextlib.suppress(Exception):
            out = live()
        return out if isinstance(out, dict) else {}

    def _coop_vpads_by_uniq(self) -> dict[str, tuple[str | None, str | None]]:
        """MAC -> (vpad_backend, vpad_motivo) dos jogadores secundários (BT-03)."""
        coop = (
            getattr(self.daemon, "_coop_manager", None)
            if self.daemon is not None
            else None
        )
        players = getattr(coop, "_players", None) if coop is not None else None
        if not isinstance(players, dict):
            return {}
        out: dict[str, tuple[str | None, str | None]] = {}
        for mac, player in players.items():
            if not isinstance(mac, str) or mac.startswith("path:"):
                continue
            vpad = getattr(player, "vpad", None)
            if vpad is None:
                continue
            out[mac] = self._vpad_backend_motivo(vpad)
        return out

    @staticmethod
    def _vpad_backend_motivo(vpad: Any) -> tuple[str | None, str | None]:
        """(backend, motivo) de UM vpad — motivo só quando degradado (BT-03).

        Quem diz se degradou é `virtual_pad.motivo_da_degradacao`, o mesmo dono
        do `dedup_status` e do diário: a máscara DualSense no uinput quando o
        caminho é o do DualSense. O caminho Xbox em uinput é escolha dela.
        """
        from hefesto_dualsense4unix.integrations.virtual_pad import motivo_da_degradacao

        raw_backend = getattr(vpad, "backend", None)
        backend = raw_backend if isinstance(raw_backend, str) and raw_backend else None
        return backend, motivo_da_degradacao(vpad)


    _AUTHORITY_VALUES = ("game", "daemon", "unknown")

    def _game_signal_snapshot(self) -> dict[str, Any]:
        """`game_signal` do `state_full` — quem manda na exibição AGORA.

        Contrato (NUMA-01, `daemon/lifecycle.py`): `daemon.display_authority`
        é property PÚBLICA 'game'|'daemon'|'unknown' — a MESMA leitura que o
        merge-gate do backend (`_game_wins`) e o `ExternalLedSync.tick`
        consultam, nunca uma segunda fonte da verdade. ``degradado`` é
        derivado da PRÓPRIA autoridade: ``authority == "unknown"`` já É o
        estado degradado/fail-safe da síntese da Onda N (ambiguidade —
        detector cego, marker ilegível, ou o sinal simplesmente ainda não
        foi fiado nesta versão do daemon) — nunca inventa 'game'/'daemon'.

        Diagnóstico rico opcional (evidência/motivo/timestamp da última
        transição) é best-effort via `daemon._game_signal.diagnostico()` —
        ponto de extensão forward-compatible; a casca `GameSignal` atual
        (NUMA-01) não o expõe ainda, então ``evidencia``/``motivo``/``desde``
        ficam ``None`` na prática, exceto o `motivo="sinal_nao_wireado"`
        quando `display_authority` nem existe (versão anterior ao NUMA-01).
        Exceção em `diagnostico()` não derruba o `state_full` — a
        `authority` já foi lida antes, independente do diagnóstico.
        """
        authority_raw = (
            getattr(self.daemon, "display_authority", None)
            if self.daemon is not None
            else None
        )
        wired = isinstance(authority_raw, str) and authority_raw in self._AUTHORITY_VALUES
        authority = authority_raw if wired else "unknown"

        evidencia: str | None = None
        motivo: str | None = None if wired else "sinal_nao_wireado"
        desde: float | None = None
        degradado = authority == "unknown"

        diag_source = (
            getattr(self.daemon, "_game_signal", None)
            if self.daemon is not None
            else None
        )
        diagnostico = getattr(diag_source, "diagnostico", None)
        if callable(diagnostico):
            with contextlib.suppress(Exception):
                raw_diag = diagnostico()
                if isinstance(raw_diag, dict):
                    evidencia = _as_str_or_none(raw_diag.get("evidencia"))
                    motivo = _as_str_or_none(raw_diag.get("motivo")) or motivo
                    desde_raw = raw_diag.get("desde")
                    if isinstance(desde_raw, (int, float)) and not isinstance(
                        desde_raw, bool
                    ):
                        desde = float(desde_raw)
                    degradado_raw = raw_diag.get("degradado")
                    if isinstance(degradado_raw, bool):
                        degradado = degradado_raw

        return {
            "authority": authority,
            "evidencia": evidencia,
            "motivo": motivo,
            "desde": desde,
            "degradado": degradado,
        }


    #: `state_full` roda a 10 Hz e `load_all_profiles()` lê o disco inteiro;
    _perfil_mudo_cache: tuple[tuple[str, str, str], list[dict[str, str]]] | None = None

    def _perfil_que_nao_entrou(self) -> list[dict[str, str]]:
        """Perfis que são regra DESTE jogo e mesmo assim não entraram.

        Só as regras do jogo em foco (`e_regra_deste_jogo`), e essa poda é a
        diferença entre informação e ruído: com 14 perfis no disco, doze
        "não entraram" a cada janela de desktop, e todos por funcionarem como
        deveriam. O que ela precisa ver é o perfil que ela escreveu PARA aquele
        jogo e que o jogo abriu sem.

        Fora de janela de jogo devolve `[]` sem tocar em disco: o predicado
        `e_regra_deste_jogo` exige um appid em foco, então não há resposta
        possível — e pagar `load_all_profiles()` para descobrir isso, a 10 Hz e
        com ela no desktop, seria o poller cego que esta casa já pagou uma vez.
        """
        from hefesto_dualsense4unix.daemon.launch_env import steam_appid_from_wm_class

        def _txt(nome: str) -> str:
            valor = getattr(self.store, nome, None)
            return valor if isinstance(valor, str) else ""

        wm_class = _txt("window_detect_current_class")
        if steam_appid_from_wm_class(wm_class) is None:
            self._perfil_mudo_cache = None
            return []
        chave = (wm_class, _txt("window_detect_current_name"), _txt("window_detect_current_exe"))
        cache = self._perfil_mudo_cache
        if cache is not None and cache[0] == chave:
            return cache[1]

        from hefesto_dualsense4unix.profiles.loader import load_all_profiles
        from hefesto_dualsense4unix.profiles.porque_nao_entrou import (
            frase_do_perfil_que_nao_entrou,
            perfis_que_nao_entraram,
        )

        info = {"wm_class": chave[0], "wm_name": chave[1], "exe_basename": chave[2]}
        achados = [
            {"nome": a.nome, "frase": frase_do_perfil_que_nao_entrou(a)}
            for a in perfis_que_nao_entraram(info, load_all_profiles())
            if a.e_regra_deste_jogo
        ]
        self._perfil_mudo_cache = (chave, achados)
        return achados

    def _wrapper_used_now(self) -> bool | None:
        """`wrapper_used` do momento: True/False com jogo em foco, None sem."""
        from hefesto_dualsense4unix.daemon.launch_env import (
            steam_appid_from_wm_class,
            wrapper_used_state,
        )

        wm_class = getattr(self.store, "window_detect_last_class", None)
        appid = steam_appid_from_wm_class(
            wm_class if isinstance(wm_class, str) else None
        )
        if appid is None:
            self._wrapper_first_seen = None
            return None
        first = self._wrapper_first_seen
        if first is None or first[0] != appid:
            first = (appid, time.time())
            self._wrapper_first_seen = first
        return wrapper_used_state(
            appid=appid,
            marker=self._wrapper_marker_cached(),
            first_seen_epoch=first[1],
        )

    def _agendar_arming_do_launch(self) -> None:
        """Arma o modo do perfil quando o ping veio de um launch em curso."""
        if self.daemon is None:
            return
        marker = self._wrapper_marker_cached()
        if marker is None:
            return
        from hefesto_dualsense4unix.daemon.launch_env import LAUNCH_ARM_WINDOW_SEC

        if (time.time() - marker[1]) > LAUNCH_ARM_WINDOW_SEC:
            return
        if getattr(self.daemon, "_launch_armed_for", None) == marker:
            return
        with contextlib.suppress(RuntimeError):
            tarefa = asyncio.get_running_loop().create_task(self._armar_launch())
            self._launch_arm_task = tarefa
            tarefa.add_done_callback(lambda _t: setattr(self, "_launch_arm_task", None))

    async def _armar_launch(self) -> None:
        """Corpo do arming agendado — best-effort, nunca derruba o loop."""
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.launch_env import arm_launch_profile

            resultado = arm_launch_profile(self.daemon)
            if isinstance(resultado, dict) and resultado.get("armado"):
                logger.info(
                    "launch_arm_pelo_ping_do_wrapper",
                    appid=resultado.get("appid"),
                    profile=resultado.get("profile"),
                    convergiu=resultado.get("convergiu"),
                    divergente=resultado.get("divergente"),
                )

    def _pontes_confirmadas_no_tique(self) -> dict[str, Any]:
        """As pontes confirmadas para o `state_full`, com cache TTL.

        BG-02 (25/08/2026). O carimbo existia só no `daemon.status` desde
        19/08, e o preço disso era medido e visível: a aba de perfil precisava
        de uma SEGUNDA ida ao daemon por gesto só para saber se aquele jogo já
        tem ponte (`app/actions/profiles_actions._buscar_as_pontes_confirmadas`
        diz isso com todas as letras). No `state_full` o editor de perfil sabe
        no MESMO estado que já lê no tique.

        A leitura crua é `_pontes_confirmadas_seguro` — a mesma que o
        `daemon.status` usa, e é isso que evita duas respostas para a mesma
        pergunta. O que muda aqui é só o TETO: ver
        `_PONTES_CONFIRMADAS_TTL_SEC` para por que o tique paga cache e o gesto
        paga o disco.
        """
        now = time.monotonic()
        hit = self._pontes_confirmadas_cache
        if hit is not None and (now - hit[0]) < _PONTES_CONFIRMADAS_TTL_SEC:
            return hit[1]
        pontes = _pontes_confirmadas_seguro()
        self._pontes_confirmadas_cache = (now, pontes)
        return pontes

    def _wrapper_marker_cached(self) -> tuple[int, int] | None:
        """Marker `last_run` com cache TTL — o state_full roda a 10-20 Hz."""
        now = time.monotonic()
        hit = self._wrapper_marker_cache
        if hit is not None and (now - hit[0]) < _WRAPPER_MARKER_TTL_SEC:
            return hit[1]
        from hefesto_dualsense4unix.daemon.launch_env import read_last_run_marker

        marker = read_last_run_marker()
        self._wrapper_marker_cache = (now, marker)
        return marker

    def _no_do_vpad_cached(
        self, uniq: str | None, nome: str | None
    ) -> dict[str, Any]:
        """`{evdev, hidraw, ino, hidraw_ino}` do vpad, preso ao evento + `stat`.

        QUEM-SEGURA-O-NOSSO-NO-01. A resposta só muda quando um nó nasce ou some
        em `/dev/input` ou nos `hidraw*` de `/dev` (as duas raízes: a entrada
        nasce antes do hidraw). Com o dono do evento armado ela vale até uma das
        duas gerações mudar (O-REPOUSO-ESPERA-O-EVENTO-01, família 1); sem ele,
        o TTL de sempre. A pergunta ao dono é pelas raízes que a varredura usa
        (`no_do_vpad`), e o dono só responde pelas que olha: a raiz desviada da
        suíte cai no TTL. O `no_ainda_vale` segue barrando o nó que mudou de
        inode.
        """
        chave = ((uniq or "").strip().casefold(), (nome or "").strip())
        if chave == ("", ""):
            return dict(NO_DESCONHECIDO)
        from hefesto_dualsense4unix.core import o_dono_do_evento as _ode
        from hefesto_dualsense4unix.integrations import no_do_vpad as _ndv

        dono = _ode.dono_armado()
        ficha = None if dono is None else dono.ficha(
            (_ndv.RAIZ_DEV_INPUT, _ode.NOMES), (_ndv.RAIZ_DEV, _ode.NOMES)
        )
        cache = self._no_do_vpad_cache
        if cache is None:
            cache = self._no_do_vpad_cache = {}
        hit, now = cache.get(chave), time.monotonic()
        valido = hit is not None and (
            hit[1] == ficha if ficha is not None else now - hit[0] < _NO_DO_VPAD_TTL_SEC
        )
        if hit is not None and valido and no_ainda_vale(hit[2]):
            return dict(hit[2])
        no = resolver_no_do_vpad(uniq=uniq, nome=nome)
        cache[chave] = (now, ficha, no)
        return dict(no)


    def _controles_sem_driver_payload(self) -> dict[str, Any]:
        """Quantos DualSense estão ligados e o sistema NÃO conseguiu adotar.

        Derivado do SISTEMA a cada leitura (`dualsense_sem_driver`), nunca de
        um segundo campo mantido em paralelo. A distinção é a lição da
        `ESTADO-QUE-MENTE-01` (03/08), que segue aberta neste mesmo payload: o
        topo do `state_full` é mantido ao lado da lista de controles em vez de
        derivado dela, e por isso a aba afirma "Conectado · USB · 85%" com a
        mesa vazia. Este campo novo não pode nascer com o mesmo defeito.

        `ids` são os nomes de diretório do sysfs (``0005:054C:0CE6.000F`` —
        barramento, fabricante, produto e instância; **não** há MAC neles).
        Vão para o payload porque é o que o `doctor` e o log precisam citar
        para casar com a linha do `bt_rebind_orphans.sh`; a janela usa só a
        quantidade.
        """
        now = time.monotonic()
        hit = self._hid_orfaos_cache
        if hit is not None and (now - hit[0]) < _HID_ORFAOS_TTL_SEC:
            ids = hit[1]
        else:
            ids = dualsense_sem_driver()
            self._hid_orfaos_cache = (now, ids)
        return {"quantidade": len(ids), "ids": list(ids)}

    async def _handle_controller_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Lista os controles do daemon; opt-in `external` soma o inventário 8BIT-01.

        FEAT-DSX-MULTI-CONTROLLER-01: `controllers` segue com UMA entrada por
        controle físico ADOTADO (DualSense) — shape intocado. O backend real
        expõe `describe_controllers`; backends sem o método (FakeController)
        caem no resumo single-entry.

        8BIT-01 — decisão documentada: o handler é sync-fast (só leitura de
        atributos), então o inventário de gamepads EXTERNOS (read-only, todos
        os vendors) entra SÓ sob `{"external": true}` — quem não pediu não
        paga os 10-40 ms da enumeração. Mesmo sob opt-in, a enumeração roda
        FORA do event loop via `asyncio.to_thread` (pool default do loop, não
        o `daemon._executor` de 2 workers "hefesto-hid" — roubar um worker do
        HID atrasaria output de rumble/led; e `self.daemon` pode ser None).
        NADA disso entra no `state_full` (caminho quente).

        Resposta com opt-in: chave nova `external` = lista de
        `{name, vid, pid, bus, uniq, driver, evdev_path, hidraw[, holders]}`.
        Sem opt-in, a chave nem aparece (payload byte-idêntico ao legado).

        **O NÚMERO ENTRA — 18/09/2026, UM-NUMERO-SO-01.** Até aqui esta lista
        publicava o ``index`` e mais nada sobre quem é quem, enquanto o
        ``daemon.state_full`` (o mesmo daemon, a mesma mesa) publicava
        ``player_slot`` e ``player``. As duas listas discordavam, e a discordância
        foi MEDIDA na mesa dela com os quatro DualSense ligados::

            controller.list   índices  0=vermelho 1=azul  2=roxo 3=branco
            as lâmpadas       jogador  2=vermelho 1=azul  3=roxo 4=branco

        Quem lesse só esta lista chamaria de "Controle 1" o controle que acende
        **jogador 2** na mão dela. O ``index`` não é um número de jogador: é a
        ordem dos HANDLES, e a fila de identidade é outra lista sobre a mesma
        mesa (o bloco *"Listas diferentes sobre a mesma mesa"* em
        ``daemon/subsystems/base.numero_do_assento_na_mesa`` mede a mesma
        divergência pelo lado do som).

        ``player_slot`` e ``numero`` saem pelos MESMOS donos do ``state_full``
        (:meth:`_player_slot_for` e :func:`_numero_de_exibicao`) — nunca uma
        conta nova aqui, que seria a quarta. Leitura pura (``assign=False``):
        listar controle jamais aloca lugar na fila. Sem registry, ``player_slot``
        é ``None`` e ``numero`` cai no ``index + 1``, que é a regra da casa.
        """
        external_raw = params.get("external", False)
        if not isinstance(external_raw, bool):
            raise ValueError("controller.list: 'external' precisa ser boolean")
        describe = getattr(self.controller, "describe_controllers", None)
        if callable(describe):
            result: dict[str, Any] = {"controllers": describe()}
            self._carimbar_o_numero(result["controllers"])
        else:
            connected = self.controller.is_connected()
            result = {
                "controllers": [
                    {
                        "connected": connected,
                        "transport": self.controller.get_transport() if connected else None,
                    }
                ]
            }
        if external_raw:
            # 8BIT-02/EXT-04/NUMA-05: os externos numeram CONTINUANDO os
            # DualSense. A fonte do slot é o registry persistente do daemon
            # handler); com o registry presente, `player_slot=None` (sem
            ds_count = sum(
                1
                for c in result["controllers"]
                if isinstance(c, dict) and c.get("connected")
            )
            registry = (
                getattr(self.daemon, "external_registry", None)
                if self.daemon is not None
                else None
            )
            peek = getattr(registry, "peek", None) if registry is not None else None
            resolver = peek if callable(peek) else None
            result["external"] = await asyncio.to_thread(
                _external_inventory, ds_count, resolver
            )
        return result

    def _indice_do_alvo(self, *, jogador: int | None, uniq: str | None) -> int:
        """Traduz «jogador N» / endereço para o índice dos handles.

        UM-NUMERO-SO-01. A tradução mora no DAEMON porque as duas listas são
        dele: a dos handles (``describe_controllers``) e a da fila de
        identidade (``identity_registry``). Ver a docstring de
        :meth:`_handle_controller_target_set` para o que custava não traduzir.

        RECUSA com frase quando o alvo não está na mesa. A alternativa — cair
        no broadcast — pintaria os quatro controles no gesto em que ela pediu
        UM, que é exatamente o defeito que o seletor existe para matar.
        """
        describe = getattr(self.controller, "describe_controllers", None)
        entradas = describe() if callable(describe) else []
        if not isinstance(entradas, list):
            entradas = []
        entradas = [e for e in entradas if isinstance(e, dict)]
        self._carimbar_o_numero(entradas)
        if uniq is not None:
            from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

            procurado = (norm_mac(uniq) or "").lower()
            for entrada in entradas:
                if (norm_mac(str(entrada.get("uniq") or "")) or "").lower() == procurado:
                    indice = entrada.get("index")
                    if isinstance(indice, int) and not isinstance(indice, bool):
                        return indice
            raise ValueError(
                "controller.target.set: este controle não está na mesa"
            )
        for entrada in entradas:
            if entrada.get("numero") == jogador:
                indice = entrada.get("index")
                if isinstance(indice, int) and not isinstance(indice, bool):
                    return indice
        na_mesa = sorted(
            n for n in (e.get("numero") for e in entradas) if isinstance(n, int)
        )
        raise ValueError(
            f"controller.target.set: não há Controle {jogador} na mesa"
            + (f" — há {na_mesa}" if na_mesa else "")
        )

    def _carimbar_o_numero(self, entries: Any) -> None:
        """Põe ``player_slot`` e ``numero`` em cada entrada — UM-NUMERO-SO-01.

        Os dois donos são os do ``state_full``; aqui não há conta nenhuma. O
        ``numero`` é o carimbo que faltava: ``player_slot`` pode ser ``None``
        (registry ausente, controle que ainda não estreou na fila) e quem lê
        precisaria repetir a regra de queda para saber o "Controle N". Repetir
        é como nasceram as três contas que a MESA-CHEIA-11 matou.

        Defensivo por inteiro: esta lista é publicada para a GUI, a CLI e o
        applet, e nenhum deles pode ficar sem mesa porque um registry dublado
        levantou.
        """
        if not isinstance(entries, list):
            return
        for entrada in entries:
            if not isinstance(entrada, dict):
                continue
            with contextlib.suppress(Exception):
                if not isinstance(entrada.get("player_slot"), int) or isinstance(
                    entrada.get("player_slot"), bool
                ):
                    entrada["player_slot"] = self._player_slot_for(
                        entrada.get("uniq")
                    )
                entrada["numero"] = _numero_de_exibicao(entrada)

    async def _handle_controller_target_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Define o ALVO das ações de output (FEAT-DSX-CONTROLLER-SELECTOR-01)."""
        index = params.get("index")
        jogador = params.get("jogador")
        uniq = params.get("uniq")
        if index is not None and (isinstance(index, bool) or not isinstance(index, int)):
            raise ValueError("controller.target.set: 'index' precisa ser int ou null")
        if jogador is not None and (
            isinstance(jogador, bool) or not isinstance(jogador, int)
        ):
            raise ValueError("controller.target.set: 'jogador' precisa ser int ou null")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("controller.target.set: 'uniq' precisa ser texto ou null")
        dados = [p for p in ("index", "jogador", "uniq") if params.get(p) is not None]
        if len(dados) > 1:
            raise ValueError(
                "controller.target.set: mande UM alvo só — "
                + ", ".join(dados)
                + " vieram juntos"
            )
        if jogador is not None or uniq is not None:
            index = self._indice_do_alvo(jogador=jogador, uniq=uniq)
        setter = getattr(self.controller, "set_output_target", None)
        if not callable(setter):
            return {"status": "ok", "target_index": None}
        effective = setter(index)
        target_index = (
            effective if isinstance(effective, int) and not isinstance(effective, bool) else None
        )
        return {"status": "ok", "target_index": target_index}


    async def _handle_lightbar_reset(self, params: dict[str, Any]) -> dict[str, Any]:
        """Manda o Reset LED state (0x08) sob demanda — INSTRUMENTO de medição."""
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("lightbar.reset: 'uniq' precisa ser texto")
        enviar = getattr(self.controller, "enviar_release_leds", None)
        if not callable(enviar):
            raise RuntimeError("backend sem suporte a lightbar.reset")
        enviados = enviar(uniq=uniq)
        return {"status": "ok", "enviados": enviados}

    async def _handle_debug_player_leds(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga a escrita do LED de JOGADOR — INSTRUMENTO de eliminação."""
        suprimir = params.get("suprimir")
        if not isinstance(suprimir, bool):
            raise ValueError("debug.player_leds exige 'suprimir' booleano")
        alternar = getattr(self.controller, "suprimir_player_leds", None)
        if not callable(alternar):
            raise RuntimeError("backend sem suporte a debug.player_leds")
        return {"status": "ok", "suprimir": bool(alternar(suprimir))}

    async def _handle_rumble_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Fixa a vibração; RECUSA no Modo Nativo (FEAT-RUMBLE-POLICY-01 + NATIVO-RUMBLE-01).

        Persiste (weak, strong) brutos em daemon.config.rumble_active para que
        o poll loop continue re-afirmando via _reassert_rumble. O multiplicador
        de política é aplicado antes de enviar ao hardware — tanto aqui quanto
        em _reassert_rumble.

        MESA-CHEIA-05 (E0): junto do par vai o DONO dele
        (`rumble_active_uniq`), congelado agora. Sem isso o reassert do poll
        loop reescrevia no alvo DE AGORA, e trocar o seletor levava o valor de
        um controle para outro.

        NATIVO-RUMBLE-01 (19/08/2026): no Modo Nativo o pedido é RECUSADO, com
        motivo — ver o bloco de comentário em `daemon.subsystems.rumble`. A
        forma da resposta é a mesma (`weak`/`strong` continuam lá, dizendo o que
        FICOU valendo); o que muda é o `status`, que passa a "recusado", e o
        `desfecho`, que nomeia o porquê. Mesmo desenho do `coop.set` que recusa
        desligar e do vocabulário `EMU_*` do gamepad.

        BROADCAST-PROIBIDO-01 (24/08/2026): o alvo escolhido no seletor e FORA
        da mesa também RECUSA, pela mesma ordem e o mesmo molde da recusa de
        Modo Nativo três linhas acima — `app/ipc_bridge.py:459`
        (`rumble_set_checked`) já lê esse molde, então nenhuma ponte precisa
        nascer. É o chamador de produção que faltava a
        `PyDualSenseController.alvo_de_output_ausente` (zero antes desta
        leva): sem consultar, `daemon_cfg.rumble_active` era armado e
        `set_rumble` chamado incondicionalmente, e o `_for_each_com_key` (já
        curado pelo F4) escrevia zero no ausente — mas o handler respondia
        "ok" mesmo assim, e o reassert de 5 Hz insistia num par que nunca
        chegou a lugar nenhum.
        """
        from hefesto_dualsense4unix.daemon.subsystems.rumble import (
            MOTIVO_ALVO_FORA_DA_MESA,
            MOTIVO_MODO_NATIVO_MANDA_NOS_MOTORES,
            RUMBLE_APLICADO,
            RUMBLE_RECUSADO_ALVO_AUSENTE,
            RUMBLE_RECUSADO_MODO_NATIVO,
            escrever_rumble_no_dono,
            fixar_par,
            modo_nativo_manda_nos_motores,
        )

        weak = params.get("weak")
        strong = params.get("strong")
        if not isinstance(weak, int) or not isinstance(strong, int):
            raise ValueError("rumble.set exige 'weak' e 'strong' inteiros 0-255")
        weak = max(0, min(255, weak))
        strong = max(0, min(255, strong))
        uniq = _uniq_do_rumble(params, "rumble.set")
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if modo_nativo_manda_nos_motores(self.daemon):
            par_de_pe = getattr(daemon_cfg, "rumble_active", None)
            logger.warning(
                "rumble_set_recusado_modo_nativo",
                weak=weak,
                strong=strong,
                par_de_pe=par_de_pe,
            )
            return {
                "status": "recusado",
                "desfecho": RUMBLE_RECUSADO_MODO_NATIVO,
                "motivo": MOTIVO_MODO_NATIVO_MANDA_NOS_MOTORES,
                "weak": par_de_pe[0] if par_de_pe else 0,
                "strong": par_de_pe[1] if par_de_pe else 0,
                "passthrough": par_de_pe is None,
            }
        if uniq is not None:
            # O gesto de UM controle (a aba Vibração): o pedido leva o endereço,
            # o seletor global não é tocado e os pares dos outros seguem de pé.
            eff_weak, eff_strong = apply_rumble_policy(self.daemon, weak, strong)
            mirar = getattr(self.controller, "set_rumble_for", None)
            if not callable(mirar) or not mirar(uniq, eff_weak, eff_strong):
                logger.warning(
                    "rumble_set_recusado_alvo_ausente", weak=weak, strong=strong,
                    alvo=uniq, par_de_pe=None,
                )
                return {
                    "status": "recusado",
                    "desfecho": RUMBLE_RECUSADO_ALVO_AUSENTE,
                    "motivo": MOTIVO_ALVO_FORA_DA_MESA,
                    "weak": 0,
                    "strong": 0,
                    "passthrough": True,
                }
            if daemon_cfg is not None:
                fixar_par(
                    daemon_cfg, uniq, weak, strong, time.monotonic(), so_este=True
                )
            return {
                "status": "ok",
                "desfecho": RUMBLE_APLICADO,
                "weak": weak,
                "strong": strong,
            }
        alvo_ausente_fn = getattr(self.controller, "alvo_de_output_ausente", None)
        alvo_ausente = alvo_ausente_fn() if callable(alvo_ausente_fn) else None
        if isinstance(alvo_ausente, str) and alvo_ausente:
            # Mesma ordem da recusa de Modo Nativo: nada é armado.
            par_de_pe = getattr(daemon_cfg, "rumble_active", None)
            logger.warning(
                "rumble_set_recusado_alvo_ausente",
                weak=weak,
                strong=strong,
                alvo=alvo_ausente,
                par_de_pe=par_de_pe,
            )
            return {
                "status": "recusado",
                "desfecho": RUMBLE_RECUSADO_ALVO_AUSENTE,
                "motivo": MOTIVO_ALVO_FORA_DA_MESA,
                "weak": par_de_pe[0] if par_de_pe else 0,
                "strong": par_de_pe[1] if par_de_pe else 0,
                "passthrough": par_de_pe is None,
            }
        if daemon_cfg is not None:
            dono = uniq_do_alvo_de_output(self.controller)
            for largado in fixar_par(
                daemon_cfg, dono, weak, strong, time.monotonic(), so_este=False
            ):
                escrever_rumble_no_dono(self.controller, largado, 0, 0)
        eff_weak, eff_strong = apply_rumble_policy(self.daemon, weak, strong)
        self.controller.set_rumble(weak=eff_weak, strong=eff_strong)
        return {
            "status": "ok",
            "desfecho": RUMBLE_APLICADO,
            "weak": weak,
            "strong": strong,
        }

    async def _handle_rumble_stop(self, params: dict[str, Any]) -> dict[str, Any]:
        """Para o rumble e fixa (0, 0); no Modo Nativo SOLTA o par (NATIVO-RUMBLE-01)."""
        from hefesto_dualsense4unix.daemon.subsystems.rumble import (
            MOTIVO_MODO_NATIVO_SOLTOU_O_PAR,
            RUMBLE_PARADO,
            RUMBLE_SOLTO_NO_MODO_NATIVO,
            escrever_rumble_no_dono,
            fixar_par,
            modo_nativo_manda_nos_motores,
            silenciar_dono_abandonado,
            soltar_todos,
        )

        uniq = _uniq_do_rumble(params, "rumble.stop")
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        dono_de_agora = uniq if uniq is not None else uniq_do_alvo_de_output(self.controller)
        if modo_nativo_manda_nos_motores(self.daemon):
            par_solto = getattr(daemon_cfg, "rumble_active", None)
            if daemon_cfg is not None:
                soltar_todos(daemon_cfg)
                daemon_cfg.rumble_dono_vibrando = None
            with contextlib.suppress(Exception):
                self.controller.set_rumble(weak=0, strong=0)
            logger.warning(
                "rumble_stop_soltou_o_par_no_modo_nativo",
                par_solto=par_solto,
            )
            return {
                "status": "ok",
                "desfecho": RUMBLE_SOLTO_NO_MODO_NATIVO,
                "motivo": MOTIVO_MODO_NATIVO_SOLTOU_O_PAR,
                "passthrough": True,
            }
        if uniq is not None:
            # O «Parar» de UM controle: o par dele vira (0, 0) e os outros
            # pares seguem de pé.
            if daemon_cfg is not None:
                fixar_par(daemon_cfg, uniq, 0, 0, time.monotonic(), so_este=True)
            escrever_rumble_no_dono(self.controller, uniq, 0, 0)
            return {"status": "ok", "desfecho": RUMBLE_PARADO}
        if daemon_cfg is not None:
            par_velho = getattr(daemon_cfg, "rumble_active", None)
            dono_velho = getattr(daemon_cfg, "rumble_active_uniq", None)
            for largado in fixar_par(
                daemon_cfg, dono_de_agora, 0, 0, time.monotonic(), so_este=False
            ):
                escrever_rumble_no_dono(self.controller, largado, 0, 0)
            if par_velho is not None and any(par_velho):
                silenciar_dono_abandonado(self.controller, dono_velho, dono_de_agora)
            daemon_cfg.rumble_dono_vibrando = None
        self.controller.set_rumble(weak=0, strong=0)
        return {"status": "ok", "desfecho": RUMBLE_PARADO}

    async def _handle_rumble_passthrough(self, params: dict[str, Any]) -> dict[str, Any]:
        """Libera controle de rumble para jogo/UDP (BUG-RUMBLE-APPLY-IGNORED-01).

        Zera daemon.config.rumble_active, desativando a re-asserção do poll loop.
        O jogo retoma controle via UDP ou emulação Xbox360. Use rumble.set para
        retomar controle manual.

        Params:
            enabled: bool — True = habilitar passthrough (zerar rumble_active).
                            False = sem efeito; para fixar valores use rumble.set.

        ONDA-U (Causa A, fix HIGH 2026-07-20 — "trava sem fim"): `rumble.set`/
        `rumble.stop` armam `mark_manual_trigger_active()` (silêncio ou valor
        fixo são overrides DELIBERADOS, que devem sobreviver a uma troca de
        foco — mesma semântica de `trigger.set`). Mas este handler é o gesto
        SIMÉTRICO de liberação ("Devolver ao jogo" da aba Rumble e o fim do
        "Testar motores" em `_rumble_test_stop`, que sempre termina chamando
        `rumble_passthrough(True)`) — o único par de `clear_manual_trigger_
        active()` do repo vivia em `profile.switch`/`trigger.reset`; sem este
        `elif`, armar aqui TAMBÉM deixava a trava permanentemente ligada (sem
        timeout, sem indicador na GUI) até a usuária ir na aba Perfis clicar
        "Ativar" — silenciando o autoswitch por engano numa ação pensada para
        NÃO deixar rastro. `enabled=False` é documentado como sem efeito (nem
        rumble_active é tocado) — não mexe na trava por coerência.
        """
        from hefesto_dualsense4unix.daemon.subsystems.rumble import (
            soltar_par,
            soltar_todos,
        )

        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("rumble.passthrough exige 'enabled' boolean")
        uniq = _uniq_do_rumble(params, "rumble.passthrough")
        if enabled:
            daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
            if daemon_cfg is not None:
                if uniq is not None:
                    soltar_par(daemon_cfg, uniq)
                else:
                    soltar_todos(daemon_cfg)
        return {"status": "ok", "passthrough": enabled}

    async def _handle_rumble_policy_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Altera política global de intensidade de rumble (FEAT-RUMBLE-POLICY-01)."""
        policy = params.get("policy")
        valid_policies = ("economia", "balanceado", "max", "auto", "custom")
        if policy not in valid_policies:
            raise ValueError(
                f"rumble.policy_set: policy deve ser um de {valid_policies}"
            )
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is None:
            raise ValueError("daemon não disponível para alterar política de rumble")
        daemon_cfg.rumble_policy = policy
        self._mark_rumble_policy_manual()
        logger.info("rumble_policy_alterada", policy=policy)
        return {"status": "ok", "policy": policy}

    async def _handle_rumble_policy_custom(self, params: dict[str, Any]) -> dict[str, Any]:
        """Define política "custom" com multiplicador explícito (FEAT-RUMBLE-POLICY-01)."""
        mult_raw = params.get("mult")
        try:
            mult = float(mult_raw)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ValueError("rumble.policy_custom: 'mult' precisa ser float") from exc
        if not (0.0 <= mult <= RUMBLE_CUSTOM_MULT_MAX):
            raise ValueError(
                f"rumble.policy_custom: mult fora de [0.0, {RUMBLE_CUSTOM_MULT_MAX}]: {mult}"
            )
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is None:
            raise ValueError("daemon não disponível para alterar política de rumble")
        daemon_cfg.rumble_policy = "custom"
        daemon_cfg.rumble_policy_custom_mult = mult
        self._mark_rumble_policy_manual()
        logger.info("rumble_policy_custom_definida", mult=mult)
        return {"status": "ok", "mult": mult}

    @staticmethod
    def _chave_de_peca_que_grava(alvo: str) -> str | None:
        """A chave sob a qual é SEGURO gravar no perfil, ou `None`."""
        from hefesto_dualsense4unix.profiles.manager import chave_de_peca_que_grava

        return chave_de_peca_que_grava(alvo)

    def _perfil_que_grava(self) -> str | None:
        """Em que perfil uma escolha POR PEÇA vai ser gravada — `None` quando nenhum.

        A-PERNA-QUE-FALTA-01, 11/09/2026. **DUAS PERNAS, e a segunda é a do
        próprio boot deste daemon.**

        O QUE ESTA FUNÇÃO CURA, e foi medido na conferência da
        `O-SALVAR-DA-JOGAR-01`: com `self.store.active_profile` em `None` e os
        marcadores em disco valendo — *o estado da máquina dela*, descrito em
        `profiles_actions.perfil_que_esta_valendo` — os três gravadores deste
        arquivo respondiam `sem_perfil` e **não gravavam byte nenhum**. O
        `gamepad.mask.set` fazia isso CALADO: o registro de sessão guardava a
        máscara, a tela acendia o chip, e o `.json` do perfil ficava
        byte-idêntico. Amanhã a escolha não estava lá.

        A SEGUNDA PERNA NÃO INVENTA POLÍTICA NOVA — `utils/session.
        resolve_boot_profile` é o MESMO resolvedor que `daemon/connection.py`
        usa para restaurar o perfil ao ligar (`session.json` + o marker
        `active_profile.txt`, com a regra de desempate escrita lá). Curar aqui é
        devolver a simetria que o boot já tem, não criar uma terceira leitura —
        e é por isso que `utils/session.py` não é tocado.

        **O NOME DO DISCO SÓ VALE SE ELE CARREGAR**, e esta guarda é a razão de
        a função existir em vez de três `or resolve_boot_profile()`. A docstring
        do resolvedor avisa: *"esta função só resolve NOMES — não valida se o
        perfil carrega"*, e quem cobre marker órfão é o `restore_last_profile`.
        Sem a confirmação, um marker apontando para um perfil apagado trocaria o
        `sem_perfil` calado de hoje por um `FileNotFoundError` estourando no
        meio de um gesto dela — que é piorar, não curar.

        NUNCA LEVANTA: quem chama é rota de escrita de um clique. Uma exceção
        aqui derrubaria o gesto inteiro por causa de um arquivo de sessão, que é
        a doença que o `nome_do_ativo` da interface já trata do outro lado.
        """
        from hefesto_dualsense4unix.profiles.manager import nome_do_perfil_que_grava

        return nome_do_perfil_que_grava(getattr(self.store, "active_profile", None))

    async def _handle_rumble_motores_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`rumble.motores.set` — a barra de CADA motor, no perfil (VIBRACAO-POR-MOTOR-01)."""
        from hefesto_dualsense4unix.daemon.ganho_da_haptica import GANHO
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
            chave_no_perfil,
            gravar_pelo_gesto,
        )
        from hefesto_dualsense4unix.profiles.schema import (
            HAPTICA_PCT_MAX,
            HAPTICA_PCT_PADRAO,
            MOTOR_PCT_MAX,
            ControllerOverrides,
            ControllerRumbleOverride,
            pct_da_haptica,
        )

        pedidos: dict[str, int] = {}
        for campo, chave_ipc, teto in (
            ("motor_forte_pct", "forte_pct", MOTOR_PCT_MAX),
            ("motor_fraco_pct", "fraco_pct", MOTOR_PCT_MAX),
            ("haptica_pct", "haptica_pct", HAPTICA_PCT_MAX),
        ):
            if chave_ipc not in params:
                continue
            valor = params.get(chave_ipc)
            if not isinstance(valor, int) or isinstance(valor, bool):
                raise ValueError(
                    f"rumble.motores.set: '{chave_ipc}' precisa ser inteiro 0-{teto}"
                )
            pedidos[campo] = valor
        if not pedidos:
            raise ValueError(
                "rumble.motores.set exige ao menos um de 'forte_pct', "
                "'fraco_pct' ou 'haptica_pct' — campo omitido NÃO mexe naquela barra"
            )
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("rumble.motores.set: 'uniq' precisa ser string ou omitido")
        ControllerRumbleOverride.model_validate(pedidos)

        alvo = uniq or self._uniq_do_primario()
        if not alvo:
            return {
                "status": "sem_controle",
                "uniq": None,
                "motivo": (
                    "não há controle na mesa para guardar a barra de motor — a "
                    "barra é POR PEÇA, e cair no primeiro da lista é o que "
                    "faria a mesa cheia escrever sempre no mesmo"
                ),
            }
        chave = self._chave_de_peca_que_grava(alvo)
        if not chave:
            return {
                "status": "sem_endereco",
                "uniq": alvo,
                "motivo": (
                    f"{alvo!r} não é um endereço de rádio de uma peça de "
                    "plástico — sem MAC não há como mirar uma peça, e gravar "
                    "sob uma chave que o motor nunca casa faria a escolha "
                    "sumir calada"
                ),
            }
        nome = self._perfil_que_grava() or ""
        visto: dict[str, Any] = {}

        def _com_as_barras(perfil: Any) -> Any:
            atuais = dict(perfil.controllers or {})
            original = chave_no_perfil(perfil, chave)
            dele = atuais.get(original) or ControllerOverrides()
            antes = dele.rumble
            campos = dict(antes.model_dump(exclude_unset=True)) if antes is not None else {}
            for campo, valor in pedidos.items():
                padrao = HAPTICA_PCT_PADRAO if campo == "haptica_pct" else MOTOR_PCT_PADRAO
                if valor == padrao:
                    campos.pop(campo, None)
                else:
                    campos[campo] = valor
            novo = ControllerRumbleOverride.model_validate(campos) if campos else None
            visto["novo"] = novo
            antes_campos = (
                dict(antes.model_dump(exclude_unset=True)) if antes is not None else None
            )
            if antes_campos == (dict(campos) if campos else None):
                return None
            visto["gravado"] = True
            atuais[original] = dele.model_copy(update={"rumble": novo})
            return perfil.model_copy(update={"controllers": atuais})

        onde, _ = gravar_pelo_gesto("vibracao", nome, _com_as_barras, uniq=chave,
                                    origem="rumble.motores.set")
        efetivos = self._pcts_efetivos(visto.get("novo"))
        haptica = pct_da_haptica(visto.get("novo"))
        if not visto.get("gravado"):
            logger.info("rumble_motores_sem_mudanca", uniq=chave, perfil=nome, onde=onde)
            return {
                "status": "ok",
                "uniq": alvo,
                "perfil": nome or None,
                "onde": onde,
                "gravado": False,
                "forte_pct": efetivos[0],
                "fraco_pct": efetivos[1],
                "haptica_pct": haptica,
            }
        # executa o `__init__` que importa TODOS eles, e o `state_full` já paga
        if self.daemon is not None:
            from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                esquecer_motores_do_perfil,
            )

            esquecer_motores_do_perfil(self.daemon)
        GANHO.ler_do_daemon(self.daemon, forcar=True)
        logger.info(
            "rumble_motores_gravados",
            uniq=chave,
            perfil=nome,
            onde=onde,
            forte_pct=efetivos[0],
            fraco_pct=efetivos[1],
            haptica_pct=haptica,
        )
        return {
            "status": "ok",
            "uniq": alvo,
            "perfil": nome or None,
            "onde": onde,
            "gravado": True,
            "forte_pct": efetivos[0],
            "fraco_pct": efetivos[1],
            "haptica_pct": haptica,
        }

    async def _handle_sensor_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`sensor.set` — desliga giroscópio e acelerômetro DE VERDADE.

        Params: ``{uniq?: str, giroscopio?: bool, acelerometro?: bool}``.
        `uniq` omitido = o primário; campo omitido = **não mexe naquele
        sensor**. Decisão dela, 04/09/2026, depois de eu recomendar virar
        leitura:

            *"ele tem que funcionar de verdade. ambos independente do modo e
            da mascara."* <!-- noqa-acento: citação literal dela -->

        O ATO INTEIRO SÃO TRÊS ESCRITAS, e a ordem é o contrato:

        1. **o registro vivo** (`core/virtual_motion.REGISTRO`) — é ele que o
           caminho do report consulta a ~250 Hz, e é o que faz a escolha valer
           AGORA. Primeiro porque é o único que o jogo sente;
        2. **o perfil** (`ControllerOverrides.sensores`) — é o que faz a
           escolha sobreviver ao replug e à troca de perfil;
        3. **o `EVIOCGRAB`** no nó "Motion Sensors", pelo `SensorHub` — o
           braço que alcança quem lê evdev direto.

        A RESPOSTA DIZ QUAL METADE PEGOU, e essa é a entrega tanto quanto o
        interruptor. A medição de 04/09/2026 (SDL 2.30 headless, um DualSense
        no cabo), corrigida pela SENSORES-NO-JOGO-02 (13/09/2026, §1), diz:

        * o zero em Modo Virtual era da libSDL2 2.30.0 do sistema; nas bibliotecas
          dos runtimes da Steam o vpad expõe os dois sensores, e o SDL pareia o nó
          «Motion Sensors» pelo `uniq` — e os bytes do vpad são os deste daemon;
        * em **Nativo** o giro chega ao SDL pelo **`hidraw`** do FÍSICO — e ali o
          daemon não está no caminho, porque o kernel entrega o report direto.

        Logo, em Nativo o alcance é PARCIAL, e a resposta o diz com todas as
        letras em vez de responder "aplicado" sobre um giro que continua
        chegando — que é exatamente o verde falso que esta sprint existe para
        não cometer.
        """
        from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
        from hefesto_dualsense4unix.profiles.schema import (
            ControllerOverrides,
            ControllerSensoresOverride,
        )

        pedidos: dict[str, bool] = {}
        for campo in ("giroscopio", "acelerometro"):
            if campo not in params:
                continue
            valor = params.get(campo)
            if not isinstance(valor, bool):
                raise ValueError(
                    f"sensor.set: '{campo}' precisa ser boolean — true liga o "
                    "sensor para o jogo, false o desliga"
                )
            pedidos[campo] = valor
        if not pedidos:
            raise ValueError(
                "sensor.set exige ao menos um de 'giroscopio' ou "
                "'acelerometro' — campo omitido NÃO mexe naquele sensor"
            )
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("sensor.set: 'uniq' precisa ser string ou omitido")

        alvo = uniq or self._uniq_do_primario()
        if not alvo:
            return {
                "status": "sem_controle",
                "uniq": None,
                "motivo": (
                    "não há controle na mesa para desligar sensor — o "
                    "interruptor é POR PEÇA, e cair no primeiro da lista é o "
                    "que faria a mesa cheia desligar sempre o mesmo giro"
                ),
            }
        chave = self._chave_de_peca_que_grava(alvo)
        if not chave:
            return {
                "status": "sem_endereco",
                "uniq": alvo,
                "motivo": (
                    f"{alvo!r} não é um endereço de rádio de uma peça de "
                    "plástico — sem MAC não há como mirar um sensor, e "
                    "desligar sob uma chave que o report nunca casa faria a "
                    "escolha sumir calada"
                ),
            }

        estado = REGISTRO.definir(
            chave,
            giroscopio=pedidos.get("giroscopio"),
            acelerometro=pedidos.get("acelerometro"),
        )

        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import (
            chave_no_perfil,
            gravar_pelo_gesto,
        )

        nome = self._perfil_que_grava() or ""
        visto: dict[str, Any] = {}

        def _com_os_sensores(perfil: Any) -> Any:
            atuais = dict(perfil.controllers or {})
            original = chave_no_perfil(perfil, chave)
            dele = atuais.get(original) or ControllerOverrides()
            antes = dele.sensores
            campos = dict(antes.model_dump(exclude_unset=True)) if antes else {}
            for campo, valor in pedidos.items():
                if valor:
                    campos.pop(campo, None)
                else:
                    campos[campo] = False
            novo = ControllerSensoresOverride.model_validate(campos) if campos else None
            antes_campos = dict(antes.model_dump(exclude_unset=True)) if antes else None
            if antes_campos == (dict(campos) if campos else None):
                return None
            visto["gravado"] = True
            atuais[original] = dele.model_copy(update={"sensores": novo})
            return perfil.model_copy(update={"controllers": atuais})

        onde, _ = gravar_pelo_gesto("sensores", nome, _com_os_sensores, uniq=chave,
                                    origem="sensor.set")
        gravado = bool(visto.get("gravado"))

        hub = self._garantir_sensor_hub()
        with contextlib.suppress(Exception):
            hub.reconciliar()
        grab = self._grab_do_movimento(hub, chave)

        nativo = bool(
            self.daemon is not None and getattr(self.daemon, "is_native_mode", bool)()
        )
        alcance = {
            "report": "nao_se_aplica" if nativo else "aplicado",
            "evdev": grab,
        }
        ressalva: str | None = None
        if nativo and not estado.tudo_ligado:
            ressalva = (
                "Modo Nativo: o jogo lê o movimento pelo hidraw do controle "
                "FÍSICO, e nesse caminho o daemon não escreve byte nenhum — o "
                "kernel entrega o report direto. O sensor fica escondido de "
                "quem lê o nó evdev, e continua chegando a quem lê pelo hidraw "
                "(o SDL lê por ali). Para desligar de verdade, o Modo Virtual."
            )
        elif not estado.tudo_ligado and grab not in ("held", "pending"):
            ressalva = (
                f"o nó de movimento não ficou exclusivo (grab={grab}): o jogo "
                "não recebe mais o sensor pelo vpad, mas quem ler o nó evdev "
                "do controle físico ainda o vê"
            )

        logger.info(
            "sensor_set",
            uniq=chave,
            perfil=nome,
            onde=onde,
            gravado=gravado,
            giroscopio=estado.giroscopio,
            acelerometro=estado.acelerometro,
            grab=grab,
            nativo=nativo,
        )
        return {
            "status": "ok",
            "uniq": alvo,
            "perfil": nome or None,
            "onde": onde,
            "gravado": gravado,
            "giroscopio": estado.giroscopio,
            "acelerometro": estado.acelerometro,
            "alcance": alcance,
            "ressalva": ressalva,
        }

    @staticmethod
    def _pcts_efetivos(rumble: Any) -> tuple[int, int]:
        """`(forte_pct, fraco_pct)` que passam a valer — 100 quando sem opinião."""
        from hefesto_dualsense4unix.profiles.schema import pcts_dos_motores

        return pcts_dos_motores(rumble)

    def _mark_rumble_policy_manual(self) -> None:
        """Propaga o gesto manual de política de rumble ao daemon."""
        mark_manual = getattr(self.daemon, "mark_rumble_policy_manual", None)
        if callable(mark_manual):
            mark_manual()


    async def _handle_daemon_reload(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica overrides parciais de config em runtime (REFACTOR-DAEMON-RELOAD-01)."""
        if self.daemon is None:
            raise ValueError("daemon não disponível para reload")

        from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

        overrides = params.get("config_overrides", {})
        if not isinstance(overrides, dict):
            raise ValueError("daemon.reload: 'config_overrides' deve ser objeto")

        known_fields = set(DaemonConfig.__dataclass_fields__)
        unknown = set(overrides) - known_fields
        if unknown:
            raise ValueError(
                f"daemon.reload: campos desconhecidos em config_overrides: {sorted(unknown)}"
            )

        new_cfg = replace(self.daemon.config, **overrides)
        self.daemon.reload_config(new_cfg)
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.launch_env import (
                materialize_launch_env,
            )

            materialize_launch_env(self.daemon)
        return {"status": "ok", "config": _config_que_viaja(new_cfg)}

    async def _handle_launch_env_refresh(
        self, _params: dict[str, Any]
    ) -> dict[str, Any]:
        """Rematerializa as envs de launch do wrapper (DEDUP-04) sob demanda.

        Gatilho que os hooks de transição NÃO cobrem (achado MED da revisão
        adversarial da Fase 2): criar/editar/apagar perfil pela GUI grava
        DIRETO no disco (processo da GUI) e o daemon nunca fica sabendo — o
        `steam_app_<appid>.env` de antecipação ficaria ausente/rançoso
        exatamente na PRIMEIRA sessão do jogo novo (perfil nativo recém-criado
        + launch em seguida = IGNORE congelado + autoswitch derrubando a
        emulação = zero controles). A GUI chama este método best-effort após
        save/delete/import de perfil; daemon dublado sem materialização
        responde `failed` em vez de estourar.
        """
        if self.daemon is None:
            return {"status": "failed"}
        from hefesto_dualsense4unix.daemon.launch_env import materialize_launch_env

        materialize_launch_env(self.daemon)
        return {"status": "ok"}

    async def _handle_speaker_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`speaker.set` — volume/mudo/devolução do alto-falante (D4 + SOM-02).

        Params: ``{volume?: 0-255, muted?: bool, rota?: 0-3,
        fonte?: "mix"|"sfx", release?: bool, uniq?: str}``.
        `uniq` escolhe o controle (MAC normalizado); omitido = o primário —
        **menos para a `fonte`**, que é por controle e recusa o pedido sem
        endereço.

        AS DUAS CAMADAS, E ELAS NÃO SE CONFUNDEM: a ``rota`` é o byte do
        firmware (por onde o PLÁSTICO toca o que saiu do nó) e a ``fonte`` é o
        PipeWire (o que ENTRA no nó). Um pedido só de ``fonte`` não toma a
        posse do volume e não manda byte nenhum ao aparelho; a resposta traz
        ``fonte`` com o que ficou valendo, e a chave não aparece quando
        ninguém a executou.

        Escrever é o ÚNICO jeito de o volume ser conhecido: o controle não tem
        caminho de leitura para esse registrador. A primeira chamada faz o
        hefesto assumir a posse dos bytes de volume do report de saída — antes
        dela o firmware é o dono e o daemon não toca no bloco (AUDIO-OWNER-01).
        Por isso `daemon.state_full` só passa a trazer a chave `speaker` DEPOIS
        de um `speaker.set`: até lá, publicar um número seria inventá-lo.

        `release: true` (SOM-02/E3) DEVOLVE a posse: os quatro bytes voltam a
        "sem dono", os bits de áudio do flag0 saem zerados e a chave `speaker`
        some do estado. O que ele devolve é o CONTROLE, não o valor — o firmware
        conserva o último número que mandamos, porque ninguém pode ler qual era
        o de antes.

        POR QUE `release` É CHAVE PRÓPRIA, e não `muted: null` como no `mic.set`:
        aqui `muted` é OPCIONAL e a ausência já significa "não mexer"; lá a
        chave é obrigatória e a ausência é erro. Reaproveitar o `null` daria
        DUAS leituras para o mesmo payload — o `{}` seria ao mesmo tempo "não
        mexer no mudo" e "devolver a posse".

        PRECEDÊNCIA (decidida na SOM-02, entrega 3): `release` junto de
        `volume`/`muted` é ERRO DE VALIDAÇÃO, não uma ordem com vencedor. A
        mistura não tem significado honesto — "pare de mandar E mande isto" —, e
        escolher um vencedor em silêncio esconderia um chamador confuso. São
        dois pedidos, e quem quer os dois manda dois.
        """
        volume = params.get("volume")
        muted = params.get("muted")
        release = params.get("release")
        uniq = params.get("uniq")
        rota = params.get("rota")
        fonte = params.get("fonte")
        if rota is not None:
            if not isinstance(rota, int) or isinstance(rota, bool):
                raise ValueError("speaker.set: 'rota' precisa ser int 0-3")
            if not 0 <= rota <= 3:
                raise ValueError(
                    "speaker.set: 'rota' fora de 0-3 (0=estéreo no fone, "
                    "1=mono no fone, 2=L no fone e R no alto-falante, "
                    "3=só no alto-falante)"
                )
        if volume is not None:
            if not isinstance(volume, int) or isinstance(volume, bool):
                raise ValueError("speaker.set: 'volume' precisa ser int 0-255")
            if not 0 <= volume <= 255:
                raise ValueError("speaker.set: 'volume' fora de 0-255")
        if muted is not None and not isinstance(muted, bool):
            raise ValueError("speaker.set: 'muted' precisa ser boolean ou omitido")
        if release is not None and not isinstance(release, bool):
            raise ValueError("speaker.set: 'release' precisa ser boolean ou omitido")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("speaker.set: 'uniq' precisa ser string ou omitido")
        if fonte is not None:
            # A `fonte` É A CAMADA 1, E ELA FALTAVA AQUI — 20/09/2026,
            # `O-BOTAO-ENTREGA-O-QUE-PROMETE-01`. A `rota` logo acima escolhe
            # por onde o PLÁSTICO toca o que saiu do nó; a `fonte` escolhe o
            # que ENTRA nele. São camadas diferentes de propósito
            # (`profiles/schema.SpeakerOverrides.fonte` escreve a separação por
            # extenso), e a tela só tinha como pedir a segunda.
            #
            # O QUE ISSO CUSTAVA: a escolha dela ia ao perfil e o daemon só a
            # lia do perfil ATIVO. Sem perfil ativo, ou antes do "Salvar", o
            # nó ficava no padrão e o clique dela não movia uma nota de som.
            from hefesto_dualsense4unix.integrations.alto_falante_bt import (
                FONTE_MIX,
                FONTE_SFX,
            )

            if not isinstance(fonte, str) or fonte not in (FONTE_MIX, FONTE_SFX):
                raise ValueError(
                    f"speaker.set: 'fonte' precisa ser {FONTE_SFX!r} (só o que "
                    f"o jogo mandar para este controle) ou {FONTE_MIX!r} (todo "
                    f"o som da máquina cai nele também)"
                )
        if release and (
            volume is not None
            or muted is not None
            or rota is not None
            or fonte is not None
        ):
            raise ValueError(
                "speaker.set: 'release' não combina com 'volume'/'muted' — "
                "devolver a posse e mandar um valor na mesma chamada não tem "
                "significado honesto; mande dois pedidos"
            )

        if release:
            return await self._speaker_release(uniq)

        fonte_feita: str | None = None
        if fonte is not None:
            fonte_feita = self._speaker_fonte(uniq, str(fonte))

        if volume is None and muted is None and rota is None:
            corpo: dict[str, Any] = {
                "status": "ok" if fonte_feita else "sem_controle",
                "speaker": self._speaker_estado(uniq),
            }
            if fonte_feita:
                corpo["fonte"] = fonte_feita
            return corpo

        setter = getattr(self.controller, "set_speaker_volume", None)
        if not callable(setter):
            raise ValueError("backend sem suporte a volume de alto-falante")

        sem_volume_conhecido = self._speaker_estado(uniq) is None
        if muted is not None and volume is None and sem_volume_conhecido:
            raise ValueError(
                "speaker.set: 'muted' sem volume conhecido — mande um 'volume' "
                "antes (mudo como primeira escrita tranca o alto-falante em "
                "zero e o próprio mudo não o solta)"
            )
        extras: dict[str, Any] = {} if rota is None else {"rota": rota}
        ok = bool(setter(volume, muted=muted, uniq=uniq, **extras))
        corpo = {
            "status": "ok" if ok else "sem_controle",
            "speaker": self._speaker_estado(uniq),
        }
        if fonte_feita:
            corpo["fonte"] = fonte_feita
        return corpo

    def _speaker_fonte(self, uniq: str | None, fonte: str) -> str | None:
        """Entrega a `fonte` ao dono do nó, e devolve a que ficou valendo."""
        sub = getattr(self.daemon, "_alto_falante_subsystem", None)
        escolher = getattr(sub, "escolher_a_fonte", None)
        valendo = getattr(sub, "fonte_escolhida", None)
        if not uniq or not callable(escolher) or not callable(valendo):
            return None
        try:
            if not escolher(uniq, fonte):
                return None
            return str(valendo(uniq))
        except Exception:  # pragma: no cover - defensivo
            logger.debug("som_fonte_nao_escolhida", uniq=uniq, exc_info=True)
            return None

    async def _speaker_release(self, uniq: str | None) -> dict[str, Any]:
        """Devolve a posse dos bytes de volume (SOM-02/E3) e relê o estado.

        A releitura tem de sair `None`: `speaker_state_for` devolve None assim
        que o byte do alto-falante fica sem dono, e o `_merge_audio` só publica
        dicionário — é assim que a chave `speaker` SOME do `daemon.state_full` e
        a janela volta a dizer "não ajustado" no tique seguinte.
        """
        soltar = getattr(self.controller, "release_speaker_volume", None)
        if not callable(soltar):
            raise ValueError("backend sem suporte a devolução do alto-falante")
        ok = bool(soltar(uniq=uniq))
        return {
            "status": "ok" if ok else "sem_controle",
            "speaker": self._speaker_estado(uniq),
        }

    def _speaker_estado(self, uniq: str | None) -> dict[str, Any] | None:
        """Leitura tolerante do `speaker_state_for` (None = sem volume conhecido).

        `getattr` defensivo pelo mesmo motivo do resto do bloco de áudio:
        FakeController e daemon antigo não têm o método, e ausência é resposta.
        """
        leitor = getattr(self.controller, "speaker_state_for", None)
        if not callable(leitor):
            return None
        estado: Any = None
        with contextlib.suppress(Exception):
            estado = leitor(uniq)
        return estado if isinstance(estado, dict) else None


    async def _handle_mic_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`mic.set` — mudo do microfone no FIRMWARE do controle (MIC-USB-01).

        Params: ``{muted: bool|null, uniq?: str}``. `uniq` escolhe o controle
        (MAC normalizado, mesmo roteamento por-uniq de `led.set`/`rumble.set`);
        omitido = o primário.

        POR QUE ESTE MÉTODO EXISTE. Em 25/07 o microfone da mantenedora estava
        mudo por TRÊS camadas empilhadas, e a aba Status dizia a verdade o
        tempo todo. Curadas as duas primeiras (o `mute:true` persistido por
        rota no estado do WirePlumber e o perfil da placa preso no iec958 —
        que capta —, ambas agora no `doctor --fix`), sobrou a terceira: o firmware do
        controle. O backend já tinha `set_microphone_mute` desde o
        AUDIO-OWNER-01, mas ele NÃO estava exposto em lugar nenhum — entre os
        31 métodos do IPC havia `speaker.set` e não havia `mic.set`. O único
        jeito de desmutar era apertar o botão físico do controle.

        OS TRÊS ESTADOS, e por que `False` não é "não mexer":

          - ``muted: true``  — MUTA: passamos a mandar o bit `MIC_MUTE` ligado,
            com o `POWER_SAVE_CONTROL_ENABLE` asserido, em todo report;
          - ``muted: false`` — DESMUTA: mandamos o mesmo campo com o bit
            apagado. É uma ORDEM, e enquanto ela vigorar o botão físico não
            manda mais — nós somos os donos do registrador;
          - ``muted: null``  — DEVOLVE A POSSE ao `hid-playstation`, que é
            quem alterna o mudo na borda do botão físico. O bit de validação
            sai apagado do report e o firmware conserva o que tinha.

        Confundir o segundo com o terceiro foi exatamente o defeito dos dois
        escritores do byte de mute (commit `3d9bb7e`): o keepalive do upstream
        mandava `common[9]=0x00` — ou seja, "desmuta" — a 60 Hz por cima do
        kernel, e o botão do controle parecia não funcionar. Por isso a chave
        `muted` é OBRIGATÓRIA aqui: omiti-la levanta erro em vez de virar um
        `False` silencioso. Quem chama tem de dizer o que quer.

        A resposta traz o estado LIDO (`audio`, do byte que vem no report de
        INPUT) e a posse (`mic_mudo_desejado`). O `audio` pode estar um report
        atrás da escrita — ele é a leitura do que o firmware DECLARA, não o eco
        do que acabamos de mandar; a aba Status converge no tick seguinte.

        PONTO DE FIAÇÃO DA GUI (deliberadamente não fiado nesta sprint): o
        botão de microfone da aba Status deve chamar
        `app.ipc_bridge.mic_set(...)` de dentro de
        `app/actions/status_actions.py`, no mesmo lugar em que o medidor de
        `app/mic_monitor.py` já é montado, e reler `daemon.state_full` para
        pintar o selo — nunca guardar o valor mandado como se fosse leitura.
        """
        if "muted" not in params:
            raise ValueError(
                "mic.set: 'muted' é obrigatório — true muta, false desmuta, "
                "null devolve a posse ao kernel"
            )
        muted = params.get("muted")
        uniq = params.get("uniq")
        if muted is not None and not isinstance(muted, bool):
            raise ValueError("mic.set: 'muted' precisa ser boolean ou null")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("mic.set: 'uniq' precisa ser string ou omitido")
        setter = getattr(self.controller, "set_microphone_mute", None)
        if not callable(setter):
            raise ValueError("backend sem suporte a mudo de microfone")
        ok = bool(setter(muted, uniq=uniq))
        estado: Any = None
        leitor = getattr(self.controller, "audio_status_for", None)
        if callable(leitor):
            with contextlib.suppress(Exception):
                estado = leitor(uniq)
        return {
            "status": "ok" if ok else "sem_controle",
            "audio": estado if isinstance(estado, dict) else None,
            "mic_mudo_desejado": muted,
        }

    async def _handle_mic_canal_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`mic.canal.set` — O ATO INTEIRO do microfone (MICROFONE-UM-ATO-01)."""
        if "ligado" not in params:
            raise ValueError(
                "mic.canal.set: 'ligado' é obrigatório — true liga o microfone "
                "deste controle no canal dele, false o desliga"
            )
        ligado = params.get("ligado")
        if not isinstance(ligado, bool):
            raise ValueError("mic.canal.set: 'ligado' precisa ser boolean")
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("mic.canal.set: 'uniq' precisa ser string ou omitido")
        if self.daemon is None:
            raise RuntimeError("daemon indisponível")
        alvo = uniq or self._uniq_do_primario()
        if not alvo:
            return {
                "status": "sem_controle",
                "uniq": None,
                "ligado": ligado,
                "motivo": (
                    "não há controle na mesa para ligar o microfone — o ato "
                    "precisa de um endereço, e cair no primeiro da lista é o "
                    "que faria a mesa cheia eleger sempre o mesmo"
                ),
            }
        from hefesto_dualsense4unix.daemon.subsystems.hotkey import ligar_o_microfone

        ato = await ligar_o_microfone(self.daemon, alvo, ligado=ligado)
        return ato.como_corpo()

    def _uniq_do_alvo_de_saida(self) -> str | None:
        """O endereço do alvo de `controller.target.set`, ou `None` para TODOS.

        Dono único da pergunta *"ela apontou para alguém?"*, e ele existe
        separado de :meth:`_uniq_do_primario` porque os dois caminhos que o
        consultam querem quedas DIFERENTES quando a resposta é `None`:

        * os atos por controle (`sensor.set`, `mic.canal.set`,
          `rumble.motores.set`) caem no primário — a conveniência de quem tem
          um controle só;
        * o `mic.volume.set` cai na ROTA GLOBAL do servidor de som, que não é
          a mesma coisa: é a fonte padrão do sistema, e trocá-la pelo primário
          mudaria o gesto de quem tem um controle só (ver a docstring dele).

        Misturar os dois seria a cura larga demais — a que conserta a queixa e
        quebra o caso de um controle.
        """
        alvo = getattr(self.controller, "get_output_target_uniq", None)
        if not callable(alvo):
            return None
        with contextlib.suppress(Exception):
            escolhido = alvo()
            if isinstance(escolhido, str) and escolhido:
                return escolhido
        return None

    def _uniq_do_primario(self) -> str | None:
        """Em quem o ato cai quando ela não disse o endereço.

        **O ALVO DE SAÍDA ENTROU — 18/09/2026, UM-NUMERO-SO-01, e ele vem
        primeiro.** MEDIDO na mesa dela com os quatro DualSense: mandar
        `controller.target.set` e depois `sensor.set` devolvia o MESMO `uniq`
        as quatro vezes — o do primário. O seletor não alcançava este caminho,
        e a queixa dela foi exatamente essa: *"a mudança dos leds e afins não
        foram aplicadas pros demais controles do app (deveriam ser 4)"*.

        **Havia DUAS línguas de alvo dentro do mesmo daemon**, e a pessoa não
        tinha como saber qual botão falava qual:

        =============================================  ===================
        `led.set` · `rumble.set` · `trigger.*`         o alvo de saída
        `speaker.set`
        `sensor.set` · `mic.canal.set`                 **o primário, sempre**
        `rumble.motores.set`
        =============================================  ===================

        A ordem agora é uma só, e ela vai do mais explícito ao menos: o `uniq`
        do próprio pedido (resolvido pelo chamador), depois o alvo de saída
        DESTA sessão, e só então o primário — que continua sendo a conveniência
        de quem tem um controle só, que é como este método nasceu.

        Resolver aqui, e não dentro de cada ato, mantém cada ato com uma regra
        só — e é o que fez esta cura alcançar os três chamadores de uma vez.
        """
        escolhido = self._uniq_do_alvo_de_saida()
        if escolhido:
            return escolhido
        listar = getattr(self.controller, "describe_controllers", None)
        if not callable(listar):
            return None
        with contextlib.suppress(Exception):
            for entrada in listar() or []:
                if not isinstance(entrada, dict):
                    continue
                if not entrada.get("connected"):
                    continue
                endereco = entrada.get("uniq")
                if isinstance(endereco, str) and endereco:
                    return endereco
        return None

    async def _handle_mic_led_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`mic.led.set` — o LED do botão de mudo, e a DEVOLUÇÃO da posse dele.

        Params: ``{aceso: bool|null, uniq?: str}``, no molde exato do
        `mic.set`. `uniq` omitido = o primário.

        MIC-DA-MESA-ELEICAO-01 (01/09/2026) — POR QUE ESTE MÉTODO EXISTE.

        O `common[8]` (LED) e o `common[9]` (mudo) são campos SEPARADOS, com
        bits de autorização diferentes (`MIC_MUTE_LED_CONTROL_ENABLE` 0x01 e
        `POWER_SAVE_CONTROL_ENABLE` 0x02). Acender o LED **não muta nada** — é
        por isso que a inversão que ela pediu (*"aceso = o mic está
        funcionando"*) cabe sem escrever uma linha no byte do mudo, e por isso
        as três recusas medidas (BT-E-VPAD-01, MIC-BT-DONO-01,
        MIC-DOIS-DONOS-01) continuam inteiras: as três são sobre o `common[9]`.

        OS TRÊS ESTADOS, e `false` NÃO é `null`:

          - ``aceso: true``  — ACENDE, e a posse do byte passa a ser nossa;
          - ``aceso: false`` — APAGA. É uma ORDEM, e enquanto ela vigorar o
            kernel não manda mais na luz;
          - ``aceso: null``  — DEVOLVE A POSSE ao `hid-playstation`, que
            escreve `mute_button_led = ds->mic_muted` a cada borda do botão
            (`hid-playstation.c:1538-1540`). O bit `0x01` do flag1 sai apagado
            e `common[8]` viaja inerte. **Antes de soltar, a luz é REPINTADA
            com o mudo de fato** (LUZ-DO-MIC-01 §2): o kernel não repinta em
            regime, só na borda do botão, então largar o byte deixava a luz
            presa no último valor que escrevemos — *"ambos tão ligados. e
            ficaram."* Quem repinta é o backend
            (`core/backend_pydualsense.py`, `_repintar_antes_de_soltar`), e é
            de propósito que seja lá: assim os três caminhos da devolução (este
            IPC, o `mic led-release` da CLI e o desligamento do daemon) ganham
            a repintura por um só lugar, e este handler continua fazendo UMA
            chamada ao backend.

        Confundir o segundo com o terceiro é o defeito do commit `3d9bb7e`, no
        byte vizinho: "apaga" mandado a 60 Hz por cima do kernel. Por isso
        `aceso` é chave OBRIGATÓRIA — omiti-la levanta erro em vez de virar um
        `False` silencioso.

        Esta é a PORTA DE EMERGÊNCIA da inversão: sem ela, tomada a posse do
        LED numa sessão, a única forma de o kernel voltar a mandar na luz seria
        ela desligar o controle.
        """
        if "aceso" not in params:
            raise ValueError(
                "mic.led.set: 'aceso' é obrigatório — true acende, false apaga, "
                "null devolve a posse ao kernel"
            )
        aceso = params.get("aceso")
        uniq = params.get("uniq")
        if aceso is not None and not isinstance(aceso, int):
            raise ValueError(
                "mic.led.set: 'aceso' precisa ser boolean, int 0-255 ou null"
            )
        if isinstance(aceso, int) and not isinstance(aceso, bool) and not 0 <= aceso <= 255:
            raise ValueError("mic.led.set: 'aceso' como nível vai de 0 a 255")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("mic.led.set: 'uniq' precisa ser string ou omitido")
        setter = getattr(self.controller, "set_microphone_led", None)
        if not callable(setter):
            raise ValueError("backend sem suporte a LED de microfone")
        ok = bool(setter(aceso, uniq=uniq))
        return {"status": "ok" if ok else "sem_controle", "aceso": aceso}

    async def _handle_mic_volume_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """`mic.volume.set` — volume da CAPTURA no sistema (MIC-VOLUME-01).

        Params: ``{volume: int 0-100, uniq?: str}``.

        **Camada diferente do `mic.set`, e por isso um método diferente.** O
        `mic.set` mexe no MUDO do firmware (camada 3): é o único que apaga a luz
        vermelha do microfone, e enquanto vigorar o botão físico do controle
        deixa de valer. Este aqui mexe no ganho da FONTE no PipeWire (camada 1):
        não toca no firmware, não tira o botão físico, não apaga luz nenhuma.
        Somar os dois num método só faria a interface prometer uma coisa e
        entregar outra.

        **Por que ele é universal**, que era o pedido dela — *"independente de
        saber se tá via bt ou via cabo, o app deve ser inteligente pra saber
        qual caminho usar"*: o que existe nos dois transportes é uma fonte de
        captura no sistema, e quem a encontra é
        `integrations/audio_control.fonte_de_captura_do_controle` — no cabo, o
        source ALSA do controle; no rádio, o source publicado pela ponte de
        áudio. Quem chama não escolhe caminho.

        **FATO SUBSTITUÍDO EM 09/09/2026.** Esta docstring dizia que *"o
        DualSense não expõe registrador de ganho de microfone em transporte
        nenhum"*, e era com essa frase que ela justificava mexer SÓ na fonte do
        sistema. **O registrador existe**: é o `common[6]`, que o
        `hid-playstation` desta máquina NOMEIA (`mic_volume`, `0x0 - 0x40`), e
        a bancada dela mediu a captura mudando com ele no cabo — *"Deu certo.
        funciona"* (`docs/data/ensaios.csv`,
        `folha-mic-volume-o-byte-age-cabo-0909`). O que a frase tinha de certo
        continua de pé e é o que sustenta a UNIVERSALIDADE: a fonte no sistema é
        o degrau que vale nos dois transportes, e o byte do aparelho é medido só
        no cabo. Por isso os dois, e nesta ordem.

        **`sem_fonte` não é falha, é resposta.** Por Bluetooth, sem a ponte de
        pé, não existe fonte de captura nenhuma (medido em 16/08/2026: `pactl
        list cards` traz só as duas placas da máquina). A interface precisa
        dessa resposta para deixar o controle deslizante INSENSÍVEL com a dica
        explicando — um controle que aceita o gesto e não faz nada é a tela
        mentindo, e um controle cinza não promete nada.

        **O `uniq` ROTEIA desde 20/08/2026 (MIC-DA-MESA-CHEIA-01).** Até então
        esta docstring dizia que não, apoiada na premissa de que *"há uma fonte
        de captura por máquina para o controle, não uma por controle"* — e essa
        premissa a própria casa já havia derrubado: com dois DualSense no cabo há
        DUAS placas de som, cada uma pendurada no seu dispositivo USB, e foi
        exatamente por isso que `usb_pai_por_uniq` nasceu em 15/08. O medidor de
        cada card já casava certo; só este controle deslizante não casava, e o
        gesto ia para a primeira placa da lista — o microfone de outra pessoa.

        **E A QUEDA PARA A ROTA GLOBAL ACABOU — ONDA5-02-01, 06/09/2026.** Aqui
        estava escrito que *"quando o alvo não se resolve a rota global continua
        valendo, e o campo `por_uniq` diz qual das duas foi usada, para a tela
        não precisar adivinhar"*. **Ela adivinhava certo e o gesto continuava
        errado.** A palavra dela, sobre este caminho:

            *"Esse erro não deveria acontecer. Deveria ser só pro controle em
            questao. Parece um bug"* — 02-Q8

        Com endereço, agora não há rota global: se a fonte daquele controle não
        se resolve, a resposta é ``sem_fonte`` e ninguém escreve em placa
        nenhuma. **O `por_uniq` FICA na resposta** — ele deixa de poder disparar
        contra ESTE daemon e continua sendo a última trava contra um daemon
        INSTALADO mais velho que a janela, que é o caso que aconteceu de verdade
        em 04/09 com o `mic.canal.set`.

        A REGRA JÁ ESTAVA ESCRITA UM ARQUIVO AO LADO: `lifecycle.py`, na
        aplicação de perfil, recusa cair para a primeira da lista desde 03/09.
        Duas réguas sobre a mesma pergunta com dois vereditos é como esta casa
        fabrica divergência silenciosa — e a porta que ficara aberta era
        justamente a que ela CLICA.

        **SEM A MESA ISTO SERIA REGRESSÃO**, e é por isso que os dois passos são
        um só: a mesa de UM controle com `pactl list sources` ilegível resolvia
        pela rota global (certa por acaso) e passaria a responder ``sem_fonte``.
        A mesa entra por `recado_do_microfone.mesa_de_agora`, a única leitura de
        "tem card na tela", e com ela a regra 4 do `escolher_fonte` (um-para-um)
        responde o mesmo caso — certo por REGRA. `None` dali é "não perguntei", e
        mantém o comportamento de antes.

        Sem `uniq` (quem tem um controle só e não manda endereço) a rota global
        continua valendo, que é o que ela sempre foi: a conveniência de uma mesa
        de um.
        """
        if "volume" not in params:
            raise ValueError("mic.volume.set: 'volume' é obrigatório (0-100)")
        volume = params.get("volume")
        if isinstance(volume, bool) or not isinstance(volume, int):
            raise ValueError("mic.volume.set: 'volume' precisa ser inteiro")
        if not (0 <= volume <= 100):
            raise ValueError("mic.volume.set: 'volume' fora de 0-100")
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("mic.volume.set: 'uniq' precisa ser string ou omitido")
        if not uniq:
            uniq = self._uniq_do_alvo_de_saida()

        from hefesto_dualsense4unix.integrations.audio_control import (
            definir_volume_da_captura,
            fonte_de_captura_do_controle,
            fonte_de_captura_do_uniq,
            volume_da_captura,
        )

        # Com dois DualSense no cabo há DUAS placas de som, e a rota global
        if uniq:
            fonte = fonte_de_captura_do_uniq(
                uniq, mesa=recado_do_microfone.mesa_de_agora(self.daemon))
            if not fonte:
                return {"status": "sem_fonte", "fonte": None, "volume": None,
                        "por_uniq": True}
            por_uniq = True
        else:
            fonte = fonte_de_captura_do_controle()
            por_uniq = False
        if not fonte:
            return {"status": "sem_fonte", "fonte": None, "volume": None}
        ok = definir_volume_da_captura(volume, fonte=fonte)
        aparelho = None
        escritor = getattr(self.controller, "set_microphone_volume", None)
        if callable(escritor):
            try:
                aparelho = bool(escritor(volume, uniq=uniq))
            except Exception as exc:  # pragma: no cover - defensivo
                aparelho = False
                logger.warning("mic_volume_aparelho_falhou", err=str(exc))
        return {
            "status": "ok" if ok else "erro",
            "fonte": fonte,
            "volume": volume_da_captura(fonte=fonte),
            "por_uniq": por_uniq,
            "aparelho": aparelho,
        }

    async def _handle_mouse_emulation_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga emulação de mouse+teclado (FEAT-MOUSE-01).

        Params:
            enabled: bool (opcional — ausente ativa a rota speed-only)
            speed: int 1-12 (opcional)
            scroll_speed: int 1-5 (opcional)

        Sem ``enabled`` (BUG-MOUSE-GUI-SYNC-01 A4): atualiza SÓ as velocidades
        na config e no device vivo (se existir), sem start/stop e sem persistir
        o flag — os sliders da GUI não conseguem religar uma emulação desligada.

        BG-02 (25/08/2026) — **a recusa passa a ter motivo.** Quando a resposta
        é `failed`, ela leva também `bloqueio`, e é ele que
        `app/actions/mouse_actions.frase_da_recusa_do_mouse` traduz para a
        statusbar. Sem o campo, aquela função caía em `RECUSA_SEM_MOTIVO` — *"O
        Hefesto recusou o pedido e não disse por quê"* — e a tabela
        `BLOQUEIO_DO_MOUSE_EM_PORTUGUES`, commitada e pronta desde 25/08, não
        era alcançada por ninguém.

        O campo só viaja no `failed` de propósito: aqui `bloqueio` responde
        *"por que a resposta foi NÃO"*, e num `ok` não houve não. O `bloqueio`
        que descreve o ESTADO — ligado e mesmo assim calado, por modo jogo ou
        pelo Steam Input — é o do bloco `mouse_emulation` do `state_full`, que
        a aba lê no tique.
        """
        enabled = params.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            raise ValueError("mouse.emulation.set: 'enabled' precisa ser boolean ou omitido")
        speed = params.get("speed")
        scroll_speed = params.get("scroll_speed")
        if speed is not None and not isinstance(speed, int):
            raise ValueError("mouse.emulation.set: 'speed' precisa ser int")
        if scroll_speed is not None and not isinstance(scroll_speed, int):
            raise ValueError("mouse.emulation.set: 'scroll_speed' precisa ser int")

        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar emulação de mouse")

        if enabled is None:
            ok = self.daemon.set_mouse_speed(speed=speed, scroll_speed=scroll_speed)
            resposta: dict[str, Any] = {
                "status": "ok" if ok else "failed",
                "enabled": bool(
                    getattr(self.daemon.config, "mouse_emulation_enabled", False)
                ),
            }
            if not ok:
                resposta["bloqueio"] = self._bloqueio_do_mouse()
            return resposta

        ok = self.daemon.set_mouse_emulation(
            enabled=enabled,
            speed=speed,
            scroll_speed=scroll_speed,
            origin=origem_do_pedido(params),
        )
        resposta = {"status": "ok" if ok else "failed", "enabled": enabled and ok}
        if not ok:
            resposta["bloqueio"] = self._bloqueio_da_recusa_do_mouse(enabled)
        return resposta

    def _bloqueio_da_recusa_do_mouse(self, pedia_ligar: bool) -> str | None:
        """POR QUE o daemon disse não ao liga/desliga do mouse, lido depois do fato.

        Um dono para os dois métodos que ligam o mouse à mão:
        `mouse.emulation.set` e `desktop.status.set` (o «Status do Modo»,
        O-MOUSE-SEGUE-A-NAVEGACAO-01).
        """
        bloqueio = self._bloqueio_do_mouse()
        if pedia_ligar and bloqueio == "desligada":
            bloqueio = "sem_device"
        return bloqueio

    async def _handle_mouse_emulation_restore(
        self, _params: dict[str, Any]
    ) -> dict[str, Any]:
        """Restaura a emulação de mouse conforme a preferência persistida (HARM-06).

        Params: nenhum — quem sabe qual é a preferência é o daemon, que a
        gravou. É o passo que faz "Controlar o PC" LIGAR o mouse em vez de só
        desligar gamepad/nativo; entra na transição de modo
        (`app/actions/mode_transition.py`), nunca em um botão solto.

        Daemon dublado em teste (sem o método) responde `failed` em vez de
        estourar: o modo desktop continua valendo sem o mouse.
        """
        if self.daemon is None:
            raise ValueError("daemon não disponível para restaurar emulação de mouse")
        restore = getattr(self.daemon, "restore_mouse_preference", None)
        if not callable(restore):
            return {"status": "failed", "enabled": False}
        enabled = bool(restore())
        return {"status": "ok", "enabled": enabled}

    async def _handle_desktop_arranjo_apply(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Carrega no aparelho o que a aba Navegação gravou no perfil ATIVO.

        POINT-AND-CLICK-01 (17/09/2026). É o TERCEIRO passo da transição para o
        `MODE_DESKTOP`, no lugar do `mouse.emulation.restore` — que lia a flag
        de sessão da máquina e descartava as cinco coisas que a aba Navegação
        grava no perfil. Toda a política mora em
        `Daemon.aplicar_o_arranjo_do_desktop`, em cópia única; aqui não há
        regra nenhuma a repetir.

        Params:
            origin: "manual"|"profile" — a origem da ATIVAÇÃO, que é o que fura
                o lock de 30 s do gesto manual. **O silêncio é "profile"**
                (ORIGEM-QUE-MENTE-01): quem quer o gesto dela tem de DECLARAR,
                e é o que o plano da transição de modo faz.

        Resposta: ``{"status": "ok", "arranjo": {seção: estado}}`` — o relatório
        inteiro, e não um `bool`. A distinção entre *"não havia o que aplicar"*
        e *"não deu"* é o que o botão que responde calado não tem.

        A ENTRADA LIGA O MOUSE (O-MOUSE-SEGUE-A-NAVEGACAO-01, 29/09/2026,
        D-2909-A-NAVEGACAO-LIGA-O-MOUSE): o `forcar_mouse` do PS + R3 saiu, e
        as duas portas fazem o mesmo. Um cliente antigo que o mande não muda
        nada: a chave é ignorada.

        Daemon dublado em teste (sem o método) responde `failed` em vez de
        estourar: o modo desktop continua valendo sem o arranjo.
        """
        if self.daemon is None:
            raise ValueError("daemon não disponível para aplicar o arranjo do desktop")
        aplicar = getattr(self.daemon, "aplicar_o_arranjo_do_desktop", None)
        if not callable(aplicar):
            return {"status": "failed", "arranjo": {}}
        origem = origem_do_pedido(params)
        modo: dict[str, Any] = (
            {"grava_o_modo": _porta_que_grava(origem)} if origem == "manual" else {}
        )
        arranjo = aplicar(origin=origem, **modo)
        return {"status": "ok", "arranjo": dict(arranjo or {})}

    async def _handle_desktop_status_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """O «Status do Modo» da aba Navegação: mouse e teclado, e o perfil.

        O-MOUSE-SEGUE-A-NAVEGACAO-01 (29/09/2026), commit 3. O interruptor
        chamava `mouse.emulation.set` e `keyboard.emulation.set` e gravava o
        perfil pela janela; agora chama este método uma vez, e o ato e a
        gravação moram em `Daemon.definir_o_status_da_navegacao`.

        Params:
            enabled: bool (obrigatório)
            origin: "manual"|"profile" — só o pedido que DIZ ``manual`` grava
                ``mouse.enabled`` e ``teclado_emulado`` no perfil ativo; o
                silêncio é reconciliação (ORIGEM-QUE-MENTE-01).

        Resposta: ``{"status", "enabled", "mouse_emulation",
        "keyboard_emulation", "perfil", "gravado"}``. Os dois blocos são os do
        `state_full`, cada um com o `status` do seu lado, para a janela seguir
        dizendo por que não deu: o do mouse leva o `bloqueio` DA RECUSA quando
        falhou (a leitura de `mouse.emulation.set`); o do teclado diz
        ``nao_tentado`` quando o mouse falhou antes dele.
        """
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("desktop.status.set exige 'enabled' boolean")
        if self.daemon is None:
            raise ValueError("daemon não disponível para o Status do Modo")
        definir = getattr(self.daemon, "definir_o_status_da_navegacao", None)
        if not callable(definir):
            raise ValueError("daemon sem suporte ao Status do Modo")
        origem = origem_do_pedido(params)
        desfecho = definir(enabled, origin=origem, grava=_porta_que_grava(origem))

        mouse_ok = bool(desfecho.get("mouse"))
        bloco_do_mouse = {
            **self._mouse_emulation_payload(),
            "status": "ok" if mouse_ok else "failed",
        }
        if not mouse_ok:
            bloco_do_mouse["bloqueio"] = self._bloqueio_da_recusa_do_mouse(enabled)
        teclado = desfecho.get("teclado")
        bloco_do_teclado = {
            **self._keyboard_emulation_payload(),
            "status": "nao_tentado" if teclado is None else ("ok" if teclado else "failed"),
        }
        ok = mouse_ok and bool(teclado)
        return {
            "status": "ok" if ok else "failed",
            "enabled": bool(enabled and ok),
            "mouse_emulation": bloco_do_mouse,
            "keyboard_emulation": bloco_do_teclado,
            "perfil": desfecho.get("perfil"),
            "gravado": bool(desfecho.get("gravado")),
        }

    async def _handle_keyboard_emulation_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga a emulação de TECLADO (EMULACAO-NO-JOGO-01).

        Params:
            enabled: bool (obrigatório)

        Molde do `mouse.emulation.set`, e a razão de existir é a queixa dela de
        29/07: ela desligou "o modo mouse teclado", o mouse obedeceu (tem flag em
        disco desde o FEAT-MOUSE-PERSIST-01) e o teclado seguiu emitindo Alt+Tab
        no R1 dentro da partida — não havia lugar nenhum onde desligá-lo.

        Resposta: `{"status": "ok"|"failed", "enabled": bool, "keyboard_emulation":
        {...}}` — o bloco é o MESMO de `daemon.status`/`daemon.state_full`
        (`_keyboard_emulation_payload`), para a janela não precisar de uma segunda
        chamada só para saber se o device subiu.

        Aviso que a interface tem de repassar: desligar tira também o teclado
        virtual do sistema em L3/R3 e as três regiões do touchpad.
        """
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("keyboard.emulation.set exige 'enabled' boolean")
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar o teclado emulado")
        setter = getattr(self.daemon, "set_keyboard_emulation", None)
        if not callable(setter):
            raise ValueError("daemon sem suporte a alternar o teclado emulado")
        ok = bool(setter(enabled))
        return {
            "status": "ok" if ok else "failed",
            "enabled": bool(enabled and ok),
            "keyboard_emulation": self._keyboard_emulation_payload(),
        }

    async def _handle_gamepad_mask_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """A máscara de UM aparelho: `gamepad.mask.set {uniq, flavor}`.

        MASCARA-NA-TELA-01, 03/09/2026 — o pedido é dela: *"é uma máscara por
        controle. Mesmo caso do anterior."*

        ESTE ERA O ÚNICO DEGRAU QUE FALTAVA, e o próprio `external_mask` o
        nomeava desde 15/08/2026: *"Falta também o lado da escrita: quem grava a
        escolha dela é a rota IPC, que ainda só conhece a máscara da sessão."*
        Os outros três — `virtual_pad`, `coop` e `gamepad` — fecharam em 29/08.
        `set_mask` e `clear_mask` existiam no registro e não tinham UM chamador
        em `src/`.

        **O GESTO GRAVA NO PERFIL DESDE 08/09/2026** (MASCARA-NO-PERFIL-01,
        decisão dela: *"pode entrar sim"*). A forma do gesto **não mudou** — o
        chip do cartão continua chamando `gamepad.mask.set {uniq, flavor}` —, e
        o que mudou é onde a escolha para: `controllers[uniq].mascara` do perfil
        ATIVO, que é a mesma estrada que o `rumble.motores.set` já usava. Não
        nasceu uma segunda.

        SÃO DUAS ESCRITAS, e a ordem é o contrato:

        1. **o registro vivo** (`external_mask.registro_de_mascaras`) — é ele
           que `mascara_efetiva` consulta na criação de todo vpad e no tique do
           co-op, e é o que faz a escolha valer AGORA. Sem esta escrita, a
           máscara nova só entraria na próxima ativação de perfil, com a tela
           dizendo "aplicado" sobre um vpad que não mudou;
        2. **o perfil ativo**, que é o DONO — é o que faz a escolha sobreviver à
           troca de perfil e voltar amanhã.

        SEM PERFIL ATIVO (ou com um `uniq` que não é MAC de peça) a escrita 2
        não acontece e a 1 acontece do mesmo jeito: a resposta diz `gravado:
        false` com o `motivo`, em vez de recusar o gesto inteiro. Recusar
        deixaria a tela sem máscara nenhuma em uma máquina sem perfil, que é
        pior que uma escolha que dura a sessão.

        `flavor` VAZIO LIMPA a escolha, e o aparelho volta a herdar a do perfil.
        É a mesma semântica de `ControllerOverrides`: campo em branco = sem
        opinião. Sem isso não haveria como desfazer uma escolha pela tela — e
        um registro em que só se entra é uma armadilha.

        A RECUSA É EM VOZ ALTA, pela mesma razão do irmão de baixo: a
        `normalizar_mascara` do `external_mask` é estrita, e o que ela não
        reconhece devolve `None` — que aqui vira erro, não `xbox` calado.

        O QUE ESTE MÉTODO NÃO PROMETE, e está medido no `external_mask`:
        **ninguém verificou** se um jogo aceita dois vpads com máscaras
        diferentes ao mesmo tempo. O registro guarda a escolha; se o jogo
        embaralha os jogadores, isso é um aviso na tela, não um defeito nosso.

        A ROTA É A CASCA — TROCA-DENTRO-DO-JOGO-01, 14/09/2026. O ato mora em
        `external_mask.escolher_a_mascara`, e é o MESMO que o gesto PS + L3
        chama. Enquanto ele morava aqui, o gesto o alcançava por
        `daemon._ipc_server._handle_gamepad_mask_set` — um método privado achado
        por string. Lá também mudou a ORDEM: o perfil só recebe a escolha depois
        de o aparelho vestir, como o PS + R3 já fazia com o modo.
        """
        from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
            escolher_a_mascara,
        )

        uniq = str(params.get("uniq") or "").strip()
        if not uniq:
            raise ValueError(
                "gamepad.mask.set exige 'uniq' — a máscara é de UM aparelho, e "
                "sem o endereço dele a escrita iria para o registro errado")

        return escolher_a_mascara(
            self.daemon, uniq, params.get("flavor"), store=self.store
        )

    async def _handle_gamepad_emulation_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga o gamepad virtual e define a máscara (FEAT-DSX-GAMEPAD-FLAVOR-01)."""
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("gamepad.emulation.set exige 'enabled' boolean")
        flavor = params.get("flavor")
        if flavor is not None and not isinstance(flavor, str):
            raise ValueError("gamepad.emulation.set: 'flavor' precisa ser string")
        if flavor is not None:
            from hefesto_dualsense4unix.integrations.uinput_gamepad import (
                nomes_de_flavor_aceitos,
                resolver_flavor,
            )

            if resolver_flavor(flavor) is None:
                aceitos = ", ".join(nomes_de_flavor_aceitos())
                raise ValueError(
                    f"gamepad.emulation.set: máscara desconhecida {flavor!r} — "
                    f"aceito: {aceitos}"
                )
        caminho = params.get("caminho")
        if caminho is not None:
            from hefesto_dualsense4unix.integrations.virtual_pad import (
                CAMINHOS,
                normalizar_caminho,
            )

            if normalizar_caminho(caminho) is None:
                raise ValueError(
                    f"gamepad.emulation.set: caminho desconhecido {caminho!r} — "
                    f"aceito: {', '.join(CAMINHOS)}"
                )
            caminho = normalizar_caminho(caminho)
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar o gamepad virtual")

        modo: dict[str, Any] = {"caminho": caminho} if caminho is not None else {}
        # O-FREESTYLE-E-UMA-CAMADA-SO-01 (28/09/2026), a porta que a conferência
        # (CAMINHO-CONTAGIO-01): subia DualSense com o perfil ativo em Xbox — o
        if enabled and caminho is None:
            do_dono = self._caminho_do_perfil_ativo()
            if do_dono is not None:
                modo = {"caminho": do_dono, "caminho_e_escolha": False}
        origem = origem_do_pedido(params)
        if enabled and origem == "manual":
            modo["grava_o_modo"] = _porta_que_grava(origem)
        ok = self.daemon.set_gamepad_emulation(
            enabled=enabled,
            flavor=flavor,
            origin=origem,
            **modo,
        )
        active_flavor = getattr(self.daemon.config, "gamepad_flavor", None)
        resposta: dict[str, Any] = {
            "status": "ok" if ok else "failed",
            "enabled": enabled and ok,
            "flavor": active_flavor,
        }
        if caminho is not None:
            resposta["caminho"] = _caminho_publicado(self.daemon)
        return resposta

    def _caminho_do_perfil_ativo(self) -> str | None:
        """O MODO que o perfil ativo declara (`dualsense`/`xbox`), ou ``None``."""
        from hefesto_dualsense4unix.integrations.virtual_pad import normalizar_caminho

        nome = getattr(getattr(self, "store", None), "active_profile", None)
        if not isinstance(nome, str) or not nome:
            return None
        try:
            mode = self.profile_manager.get(nome).mode
        except Exception:
            return None
        if getattr(mode, "kind", None) != "gamepad":
            return None
        return normalizar_caminho(getattr(mode, "caminho", None))

    async def _handle_coop_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Liga o co-op local; RECUSA desligar (FEAT-DSX-COOP-LOCAL-01)."""
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("coop.set exige 'enabled' boolean")
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar o co-op")
        if not enabled:
            coop_recusa = getattr(self.daemon, "_coop_manager", None)
            players_recusa = (
                coop_recusa.player_count() if coop_recusa is not None else 1
            )
            logger.warning(
                "coop_set_desligar_recusado",
                motivo="coop_sempre_ligado",
                players=players_recusa,
            )
            return {
                "status": "recusado",
                "enabled": True,
                "players": players_recusa,
                "motivo": COOP_SEMPRE_LIGADO_MOTIVO,
            }
        effective = self.daemon.set_coop_enabled(
            enabled, origin=origem_do_pedido(params)
        )
        coop = getattr(self.daemon, "_coop_manager", None)
        players = coop.player_count() if coop is not None else 1
        return {"status": "ok", "enabled": bool(effective), "players": players}

    async def _handle_coop_sync(self, params: dict[str, Any]) -> dict[str, Any]:
        """Roda UM ciclo cheio de reconciliação do co-op (`sync(force=True)`)."""
        del params
        if self.daemon is None:
            raise ValueError("daemon não disponível para reconciliar o co-op")
        from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager

        coop = get_coop_manager(self.daemon)
        coop.sync(force=True)
        players = coop.player_count()
        return {
            "status": "ok",
            "players": players if isinstance(players, int) else 1,
            "active": bool(coop.should_be_active()),
        }

    async def _handle_emulation_suppress(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga o modo jogo (suprime emulação mouse/teclado)."""
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar modo jogo")
        suppressed = params.get("suppressed")
        if suppressed is not None and not isinstance(suppressed, bool):
            raise ValueError("emulation.suppress: 'suppressed' precisa ser bool")
        new_state = self.daemon.set_emulation_suppressed(suppressed)
        return {"status": "ok", "emulation_suppressed": new_state}

    async def _handle_machine_declare(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Grava no `maquina.json` o que ela DECLAROU sobre a mesa (CONFIG-03).

        A aba Configurações é o lugar do que o Hefesto **não tem como medir** —
        altura da antena, linha de visada, o que é o rádio vizinho, o modo da
        chave física de um controle genérico, a cor do plástico quando a leitura
        do firmware falha. Este é o único gesto que escreve aquele arquivo.

        Params: `{"maquina": {...}}`, uma declaração **parcial** no formato do
        `MaquinaConfig` (`utils/maquina.py`). Parcial de propósito: cada seção
        da aba manda só o que mudou, e a fusão acontece contra o disco sob o
        lock — assim duas seções da mesma janela não se apagam.

        Retorno `{"ok": True}` ou `{"ok": False, "reason": ...}`, com três
        motivos: `declaracao_invalida`, `versao_desconhecida` e
        `falha_ao_gravar`.

        **`descartados`** (CONFIG-06, 23/08/2026) entra no sucesso quando o
        `maquina.json` em disco tinha CAMPO de topo com valor que o schema
        recusa: a gravação resgata o resto e deixa aquele campo para trás
        (`utils/maquina.py:_o_que_ainda_vale`), e a lista é o único jeito de a
        janela dizer O QUE se perdeu em vez de apagar calado. A chave é
        **aditiva e só aparece quando há algo a dizer**: lista vazia não vai no
        corpo, porque "descartei zero campos" é ruído — e assim o
        `{"ok": True}` de sempre continua sendo o corpo do caso comum. Nomes
        CRUS do schema; a tradução para o rótulo da tela é da ponte da GUI
        (`_rotulos_dos_campos`, `app/ipc_bridge.py`), pela mesma razão do
        `_MOTIVOS_MAQUINA`: o daemon não conhece o texto da janela.

        **Toda recusa vem no CORPO, nunca como erro JSON-RPC**, e as três pela
        mesma razão: a ponte da GUI usa `_safe_call`, que colapsa erro de
        protocolo e daemon morto em `(False, None)` — a janela anunciaria
        "daemon offline?" para uma recusa de um daemon vivíssimo. É a doutrina
        do commit `d614d04` ("o daemon recusa, e diz por quê"). A frase de tela
        mora do lado da GUI (`_MOTIVOS_MAQUINA`, `app/ipc_bridge.py`): o daemon
        não conhece o texto da janela.

        `versao_desconhecida` é a recusa que importa: um `maquina.json` escrito
        por uma versão futura não é lido **nem sobrescrito**, e os bytes ficam
        intactos. Escolha de alguém não se destrói para registrar outra.

        Fora do `daemon.state_full` de propósito — aquilo é o tique de 20 Hz, e
        a declaração muda por gesto dela, não por quadro.
        """
        from hefesto_dualsense4unix.utils.maquina import (
            carregar_maquina,
            gravar_maquina_com_descartes,
        )

        declaracao = params.get("maquina")
        if not isinstance(declaracao, dict):
            return {"ok": False, "reason": "declaracao_invalida"}
        try:
            resultado = await asyncio.to_thread(
                gravar_maquina_com_descartes, declaracao
            )
        except ValueError as exc:
            logger.info("machine_declare_recusada_schema", err=str(exc))
            return {"ok": False, "reason": "declaracao_invalida"}
        except OSError as exc:
            logger.warning("machine_declare_falha_de_escrita", err=str(exc))
            return {"ok": False, "reason": "falha_ao_gravar"}
        if not resultado.gravou:
            return {"ok": False, "reason": "versao_desconhecida"}
        vivo: Any = self.daemon
        antes = getattr(vivo, "_maquina", None)
        vivo._maquina = await asyncio.to_thread(carregar_maquina)
        with contextlib.suppress(Exception):
            vivo.reaplicar_se_a_economia_mudou(antes)
        reconciliar = getattr(vivo, "reconciliar_bt_mic", None)
        if callable(reconciliar):
            try:
                _reconciliacao = reconciliar()
                if inspect.isawaitable(_reconciliacao):
                    await _reconciliacao
            except Exception as exc:
                logger.warning("machine_declare_bt_mic_nao_reconciliou", err=str(exc))
        if resultado.descartados:
            return {"ok": True, "descartados": list(resultado.descartados)}
        return {"ok": True}

    async def _handle_plugin_list(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Lista plugins carregados no daemon (FEAT-PLUGIN-01)."""
        ps = getattr(self.daemon, "_plugins_subsystem", None) if self.daemon else None
        if ps is None:
            return []
        result: list[dict[str, Any]] = ps.list_plugins()
        return result

    async def _handle_plugin_reload(self, params: dict[str, Any]) -> dict[str, Any]:
        """Recarrega plugins do disco (FEAT-PLUGIN-01)."""
        from hefesto_dualsense4unix.daemon.context import DaemonContext

        ps = getattr(self.daemon, "_plugins_subsystem", None) if self.daemon else None
        if ps is None:
            raise ValueError("plugins não habilitados neste daemon")

        ctx = DaemonContext(
            controller=self.controller,
            bus=getattr(self.daemon, "bus", None),  # type: ignore[arg-type]
            store=self.store,
            config=getattr(self.daemon, "config", None),
            executor=getattr(self.daemon, "_executor", None),
        )
        total = ps.reload(ctx)
        return {"status": "ok", "total": total}

    # AR-MEDIDO-01 (23/09/2026), R10 e R11 dela — o ar no `state_full`
    # deslocaria todas as âncoras de baixo. O gancho no `state_full` é uma

    _medidor_de_ar: Any = None
    _adaptadores_em_cache: tuple[float, frozenset[str], dict[str, str]] | None = None
    _afh_evitados: dict[str, tuple[int, ...] | None] | None = None
    _enlaces_lidos: dict[str, dict[str, Any]] | None = None
    _ler_qualidade: Any = None
    _afh_lido_em: float = float("-inf")
    _afh_em_voo: bool = False
    _ler_afh: Any = None
    _sinal_dos_enlaces: dict[str, int | None] | None = None
    _sinal_lido_em: float = float("-inf")
    _sinal_em_voo: bool = False
    _ler_sinal: Any = None
    _monitor_de_receptores: Any = None
    _varrer_os_receptores: Any = None

    def _enriquecer_e_medir_o_ar(
        self, result: dict[str, Any], entries: list[dict[str, Any]], state: Any
    ) -> None:
        """O enriquecimento POR CONTROLE e, depois dele, o ar."""
        with contextlib.suppress(Exception):
            self._enrich_controllers_per_controller(entries, state)
        with contextlib.suppress(Exception):
            self._merge_radio(entries)
            result["radio_ar"] = self._ar_por_adaptador(entries)
        with contextlib.suppress(Exception):
            result["radio_receptores"] = self._os_receptores_publicam()
        from hefesto_dualsense4unix.profiles.schema import HAPTICA_PCT_PADRAO

        result["haptica_pct_padrao"] = HAPTICA_PCT_PADRAO
        with contextlib.suppress(Exception):
            result["radio_governador"] = self._o_governador_publica()
        with contextlib.suppress(Exception):
            result["radio_central"] = self._a_central_publica(entries)
        with contextlib.suppress(Exception):
            self._merge_mira(entries)

    def _os_receptores_publicam(self) -> dict[str, Any]:
        """``state_full["radio_receptores"]``: a saúde de cada receptor 2.4G (a última hora).

        Só números: teclas que ficaram apertadas repetindo e buracos no movimento do mouse, por
        ``usb:vid:pid``; nunca o código de uma tecla (``integrations/receptor_sem_fio``). O
        monitor nasce na primeira pergunta e lê o evdev numa thread. Sob a suíte e no modo falso
        não há nó de verdade: nada abre e a chave sai vazia, salvo a régua que injeta o dela.
        """
        monitor = self._monitor_de_receptores
        if monitor is None:
            from hefesto_dualsense4unix.integrations import bluez_dbus, receptor_sem_fio
            from hefesto_dualsense4unix.utils.xdg_paths import fake_mode_enabled

            varrer = self._varrer_os_receptores
            if varrer is None:
                if bluez_dbus.a_suite_esta_rodando() or fake_mode_enabled():
                    return {}
                varrer = self._receptores_do_censo
            monitor = receptor_sem_fio.MonitorDosReceptores(varrer)
            self._monitor_de_receptores = monitor
            monitor.iniciar()
        publicado: dict[str, Any] = monitor.publicar()
        return publicado

    @staticmethod
    def _receptores_do_censo() -> dict[str, tuple[str, ...]]:
        """``{usb:vid:pid: (/dev/input/eventN, …)}`` dos receptores que o censo reconheceu."""
        from hefesto_dualsense4unix.integrations import receptor_sem_fio
        from hefesto_dualsense4unix.integrations.censo_do_barramento import ler_o_barramento

        achados: dict[str, tuple[str, ...]] = {}
        for a in ler_o_barramento().conectados():
            if a.receptor and a.eventos:
                chave = receptor_sem_fio.chave_do_aparelho(a.vid, a.pid)
                achados[chave] = (*achados.get(chave, ()), *(f"/dev/input/{e}" for e in a.eventos))
        return achados

    @staticmethod
    def _hz_ou_none(valor: Any) -> float | None:
        """Um Hz publicável, ou ``None`` — bool e texto não são taxa."""
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            return None
        return float(valor)

    _ADAPTADOR_TTL_S = 2.0
    _AFH_PERIODO_S = 10.0
    _SINAL_PERIODO_S = 1.0

    def _merge_radio(self, entries: list[dict[str, Any]]) -> None:
        """Quatro chaves por controle, SEMPRE presentes, ``None`` = não sei."""
        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

        def chave(valor: Any) -> str:
            return (norm_mac(str(valor)) or "") if isinstance(valor, str) else ""

        no_radio = [
            e["uniq"] for e in entries
            if e.get("transport") == "bt" and isinstance(e.get("uniq"), str) and e["uniq"]
        ]
        enderecos = self._adaptadores_do_radio(no_radio)
        hub = self._sensor_hub
        if hub is None:
            from hefesto_dualsense4unix.utils.xdg_paths import fake_mode_enabled

            if not fake_mode_enabled():
                hub = self._garantir_sensor_hub()
        voz = getattr(getattr(self.daemon, "_bt_mic_subsystem", None), "hz_de_voz", None)
        pontes: dict[str, str] = {}
        pontes_fn = getattr(
            getattr(self.daemon, "_alto_falante_subsystem", None), "pontes_de_pe", None
        )
        if callable(pontes_fn):
            with contextlib.suppress(Exception):
                pontes = {chave(u): m for u, m in dict(pontes_fn()).items() if chave(u)}
        perguntar_hz = getattr(hub, "hz_do_movimento", None)
        from hefesto_dualsense4unix.daemon.ganho_da_haptica import GANHO

        nativo = False
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.subsystems import rumble

            nativo = bool(rumble.modo_nativo_manda_nos_motores(self.daemon))
        no_ar_fn = getattr(
            getattr(self.daemon, "_alto_falante_subsystem", None), "haptica_no_ar", None
        )
        for entry in entries:
            uniq = entry.get("uniq") if isinstance(entry.get("uniq"), str) else None
            radio = entry.get("transport") == "bt"
            vivo = bool(uniq) and entry.get("connected", True) is not False
            entry["adaptador"] = (enderecos.get(uniq) or None) if radio and uniq else None
            hz: Any = None
            if vivo and callable(perguntar_hz):
                with contextlib.suppress(Exception):
                    hz = perguntar_hz(uniq)
            entry["hz_movimento"] = self._hz_ou_none(hz)
            hz_voz: Any = None
            if vivo and radio and callable(voz):
                with contextlib.suppress(Exception):
                    hz_voz = voz(uniq)
            entry["hz_voz"] = self._hz_ou_none(hz_voz)
            modo = pontes.get(chave(uniq)) if radio and uniq else None
            entry["ponte_do_radio"] = modo if modo in ("som", "haptica") else None
            entry["sinal_dbm"] = (
                (self._sinal_dos_enlaces or {}).get(chave(uniq)) if radio and uniq else None
            )
            entry["haptica_pct"] = GANHO.pct_guardado(uniq)
            entry["haptica_alcanca"] = not (radio and nativo and modo is None)
            entry["haptica_vale_pct"] = GANHO.pct_que_vale(uniq)
            no_ar = False
            if vivo and callable(no_ar_fn):
                with contextlib.suppress(Exception):
                    no_ar = no_ar_fn(uniq) is True
            entry["haptica_no_ar"] = no_ar

    def _adaptadores_do_radio(self, uniqs: list[str]) -> dict[str, str]:
        """``{uniq: endereço do adaptador | ""}``, relido no máximo a cada 2 s."""
        from hefesto_dualsense4unix.integrations import radio_da_mesa

        agora = time.monotonic()
        alvo = frozenset(uniqs)
        cache = self._adaptadores_em_cache
        if cache is not None and cache[1] == alvo and agora - cache[0] < self._ADAPTADOR_TTL_S:
            return cache[2]
        enderecos = radio_da_mesa.adaptador_por_uniq(sorted(alvo)) if alvo else {}
        self._adaptadores_em_cache = (agora, alvo, dict(enderecos))
        return dict(enderecos)

    def _ar_por_adaptador(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        """``state_full["radio_ar"]``: o orçamento de ar por adaptador.

        Sai de ``radio_da_mesa.orcamento_por_adaptador`` — o dono. Aqui só se
        junta o que o daemon mede: as chaves de :meth:`_merge_radio`, a
        amostra de ar e o AFH.

        **O AMOSTRADOR TEM UM DONO — GOVERNADOR-DO-RADIO-01, 23/09/2026.** Até
        esta data este método criava um ``MedidorDeAr`` próprio, e o daemon
        passaria a ter DOIS — o daemon e o governador fotografando o mesmo
        contador em janelas diferentes, cada um com a sua verdade. Agora a
        amostra é a do governador (``AltoFalanteSubsystem.governador``), que
        mede a cada 250 ms. Sem governador — ou no modo falso, onde ele não
        mede — não há amostra: «não sei», nunca um segundo medidor.
        ``_medidor_de_ar`` fica como porta da régua, que injeta um dublê.
        """
        from hefesto_dualsense4unix.integrations import radio_da_mesa

        amostra: Any = None
        medidor = self._medidor_de_ar
        if medidor is not None:
            amostra = medidor.amostrar()
        else:
            governador = self._o_governador()
            if governador is not None:
                amostra = governador.ultima_amostra()
        ar: dict[str, Any] | None = None
        if amostra is not None:
            ar = {e: a for e, a in dict(amostra).items() if e}
            self._talvez_ler_o_afh(ar)
            self._talvez_ler_o_sinal(ar)
        orcamento = radio_da_mesa.orcamento_por_adaptador(
            entries,
            ar=ar,
            canais_evitados=dict(self._afh_evitados or {}),
            enlaces=dict(self._enlaces_lidos or {}),
            sinais=dict(self._sinal_dos_enlaces or {}),
        )
        return {endereco: o.publicar() for endereco, o in orcamento.items()}

    def _talvez_ler_o_afh(self, ar: dict[str, Any]) -> None:
        """Pergunta o AFH de cada enlace numa thread, no máximo a cada 10 s."""
        agora = time.monotonic()
        if self._afh_em_voo or agora - self._afh_lido_em < self._AFH_PERIODO_S:
            return
        ler = self._ler_afh
        if ler is None:
            from hefesto_dualsense4unix.utils.xdg_paths import fake_mode_enabled

            if fake_mode_enabled():
                return
            from hefesto_dualsense4unix.integrations.ar_do_adaptador import ler_mapa_afh

            ler = ler_mapa_afh
        self._afh_em_voo = True
        self._afh_lido_em = agora
        leituras = dict(ar)

        a_qualidade = self._ler_qualidade
        if a_qualidade is None and self._ler_afh is not None:
            # quem injeta o AFH (a régua) não pergunta ao rádio de verdade nem a qualidade do enlace
            def a_qualidade(_hci: int, _handle: int) -> int | None:
                return None
        elif a_qualidade is None:
            from hefesto_dualsense4unix.integrations.ar_do_adaptador import ler_qualidade

            a_qualidade = ler_qualidade

        def perguntar() -> None:
            from hefesto_dualsense4unix.integrations.ar_do_adaptador import (
                canais_evitados_pelo_adaptador,
                enlaces_do_adaptador,
            )

            evitados: dict[str, tuple[int, ...] | None] = {}
            enlaces: dict[str, dict[str, Any]] = {}
            try:
                for endereco, leitura in leituras.items():
                    lidos = enlaces_do_adaptador(leitura, ler_mapa=ler, ler_qual=a_qualidade)
                    enlaces[endereco] = lidos
                    evitados[endereco] = canais_evitados_pelo_adaptador(lidos)
                self._afh_evitados = evitados
                self._enlaces_lidos = enlaces
            except Exception:  # pragma: no cover - defensivo, jamais derruba o daemon
                logger.debug("radio_afh_nao_lido", exc_info=True)
            finally:
                self._afh_em_voo = False

        try:
            import threading

            threading.Thread(target=perguntar, name="radio-afh", daemon=True).start()
        except Exception:
            self._afh_em_voo = False


    def _talvez_ler_o_sinal(self, ar: dict[str, Any]) -> None:
        """Pergunta o sinal (RSSI) de cada enlace numa thread, no máximo a cada segundo."""
        agora = time.monotonic()
        if self._sinal_em_voo or agora - self._sinal_lido_em < self._SINAL_PERIODO_S:
            return
        from hefesto_dualsense4unix.utils.xdg_paths import fake_mode_enabled

        if self._ler_sinal is None and fake_mode_enabled():
            return
        self._sinal_em_voo = True
        self._sinal_lido_em = agora
        leituras = dict(ar)

        def perguntar() -> None:
            from hefesto_dualsense4unix.integrations import radio_da_mesa

            try:
                self._sinal_dos_enlaces = radio_da_mesa.sinais_dos_enlaces(
                    leituras, ler=self._ler_sinal)
            except Exception:  # pragma: no cover - defensivo, jamais derruba o daemon
                logger.debug("radio_sinal_nao_lido", exc_info=True)
            finally:
                self._sinal_em_voo = False

        try:
            import threading

            threading.Thread(target=perguntar, name="radio-sinal", daemon=True).start()
        except Exception:
            self._sinal_em_voo = False

    def _o_governador(self) -> Any:
        """O governador do rádio, que mora no subsystem do som — ou ``None``."""
        subsystem = getattr(self.daemon, "_alto_falante_subsystem", None)
        return getattr(subsystem, "governador", None)

    def _o_governador_publica(self) -> dict[str, Any]:
        """``state_full["radio_governador"]``: as pontes com a marca «além do
        limite», quem está cedendo, e os pedidos que a tela tem de perguntar."""
        governador = self._o_governador()
        if governador is None:
            return {}
        publicado = governador.publicar()
        return dict(publicado) if isinstance(publicado, dict) else {}

    async def _handle_radio_ponte_ligar_aqui(self, params: dict[str, Any]) -> dict[str, Any]:
        """«Ligar aqui»: a ponte deste controle sobe além do limite do adaptador."""
        uniq = params.get("uniq")
        if not isinstance(uniq, str) or not uniq.strip():
            raise ValueError("radio.ponte.ligar_aqui pede `uniq` do controle")
        governador = self._o_governador()
        if governador is None:
            return {"status": "sem_governador", "uniq": uniq}
        ligou = await asyncio.to_thread(governador.ligar_aqui, uniq.strip())
        return {"status": "ok" if ligou else "sem_adaptador", "uniq": uniq}


    def _a_central(self) -> Any:
        """A central do rádio, que o daemon sobe no arranque — ou ``None``."""
        return getattr(self.daemon, "_central_do_radio", None)

    def _a_central_publica(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        """``state_full["radio_central"]``: os movimentos (``esperando``,
        ``chegou``, ``nao_chegou``) e a proposta do «Equilibrar», UMA ou nenhuma.

        ``entries`` já passou pelo :meth:`_merge_radio`: cada controle traz o
        ``adaptador`` do ``HID_PHYS`` e a ``ponte_do_radio`` — é o que a proposta
        pesa. Nunca abre o dono do BlueZ nem espera o rádio: o tique não pode.
        """
        central = self._a_central()
        if central is None:
            return {}
        publicado = central.publicar(entries)
        return dict(publicado) if isinstance(publicado, dict) else {}

    async def _handle_radio_mover(self, params: dict[str, Any]) -> dict[str, Any]:
        """«Mover» um aparelho para um adaptador, ou o «Conectar» (D8).

        ``aparelho``: o endereço (``aa:bb:…``) ou o ``uniq`` de 12 hex — o que o
        «Equilibrar» publica em ``proposta.controle``. Sem ele, é o «Conectar»:
        a janela abre no destino com mais vaga de ponte, e o controle que ela
        segurar em PS + Create é o que chega. ``destino``: o endereço do
        adaptador; sem ele, a D8 escolhe.

        Volta assim que a trava do rádio vem — no máximo 5 s de espera, decisão
        registrada —, com o movimento «esperando»; o resto segue num fio e
        chega pelo ``state_full["radio_central"]``. ``status: "ocupado"`` é a
        recusa, e ela tem DUAS causas com a mesma resposta: a trava do rádio não
        veio no prazo do gesto, ou OUTRO MOVIMENTO ESTÁ EM CURSO — um por vez
        (``central_do_radio.MOTIVO_OCUPADO``). Nas duas o botão treme, sem
        recado, e nada mudou; a tela já apaga os botões de mover enquanto um
        movimento espera (``a08_conexoes._ocupado``), e esta recusa é a segunda
        trava, para o pedido que chega entre dois tiques.
        """
        from hefesto_dualsense4unix.integrations.central_do_radio import MOTIVO_OCUPADO

        aparelho = params.get("aparelho")
        destino = params.get("destino")
        if aparelho is not None and not isinstance(aparelho, str):
            raise ValueError("radio.mover: `aparelho` é o endereço do aparelho")
        if destino is not None and not isinstance(destino, str):
            raise ValueError("radio.mover: `destino` é o endereço do adaptador")
        central = self._a_central()
        if central is None:
            return {"status": "sem_central"}
        if aparelho and aparelho.strip():
            movimento = await asyncio.to_thread(
                central.comecar_a_mover, aparelho.strip(), destino or None
            )
        else:
            movimento = await asyncio.to_thread(central.comecar_a_conectar, destino or None)
        status = "ocupado" if movimento.motivo == MOTIVO_OCUPADO else "ok"
        return {"status": status, "movimento": movimento.publicar()}


    _CAMPOS_DA_MIRA = ("ligada", "sensibilidade", "zona_morta_graus_s",
                       "gatilho", "inverter_horizontal", "inverter_vertical",
                       "inclinacao", "toque")

    def _merge_mira(self, entries: list[dict[str, Any]]) -> None:
        """``entry["mira"]`` de cada controle: o chip e o bloco da Calibrar."""
        from hefesto_dualsense4unix.core import roteador_de_movimento as rot

        store = getattr(self, "store", None)
        mesa = rot.ativo(store)
        for entry in entries:
            uniq = entry.get("uniq")
            if not isinstance(uniq, str) or not uniq:
                continue
            vale = rot.da_peca(store, uniq, mesa)
            numeros = rot.parametros_da_peca(store, uniq)
            mira = vale if vale is not None and vale.ligado else None
            entry["mira"] = {
                "ligada": mira is not None,
                "destino": mira.destino if mira is not None else rot.DESTINO_NENHUM,
                "toque": vale.toque if vale is not None else rot.DESTINO_NENHUM,
                "inclinacao": vale.acelerometro if vale is not None else rot.DESTINO_NENHUM,
                "sensibilidade": numeros.sensibilidade,
                "zona_morta_graus_s": numeros.zona_morta_graus_s,
                "gatilho": numeros.gatilho,
                "inverter_horizontal": numeros.inverter_horizontal,
                "inverter_vertical": numeros.inverter_vertical,
            }

    async def _handle_mira_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`mira.set` — o chip «Mira Virtual» e os ajustes da Calibrar, POR CONTROLE."""
        from hefesto_dualsense4unix.core import roteador_de_movimento as rot
        from hefesto_dualsense4unix.profiles.schema import (
            ControllerOverrides,
            ProfileMovimentoConfig,
        )

        desconhecidos = sorted(set(params) - {"uniq", *self._CAMPOS_DA_MIRA})
        if desconhecidos:
            raise ValueError(
                f"mira.set não conhece {desconhecidos}: a tela oferece o chip "
                "(`ligada`), os dois deslizantes (`sensibilidade`, "
                "`zona_morta_graus_s`), o `gatilho`, os dois `inverter_*`, a "
                "`inclinacao` e o `toque`, e o resto do arranjo mora no perfil"
            )
        pedidos: dict[str, Any] = {}
        if "ligada" in params:
            ligada = params["ligada"]
            if not isinstance(ligada, bool):
                raise ValueError(
                    "mira.set: 'ligada' precisa ser boolean — true acende a mira "
                    "no analógico direito, false a apaga"
                )
            pedidos["destino"] = (
                rot.DESTINO_ANALOGICO_DIREITO if ligada else rot.DESTINO_NENHUM
            )
        if "sensibilidade" in params:
            valor = params["sensibilidade"]
            if isinstance(valor, bool) or not isinstance(valor, int):
                raise ValueError("mira.set: 'sensibilidade' é um inteiro de 1 a 12")
            pedidos["sensibilidade"] = valor
        if "zona_morta_graus_s" in params:
            valor = params["zona_morta_graus_s"]
            if isinstance(valor, bool) or not isinstance(valor, (int, float)):
                raise ValueError(
                    "mira.set: 'zona_morta_graus_s' é o «Ignorar tremor até», "
                    "em graus por segundo"
                )
            pedidos["zona_morta_graus_s"] = float(valor)
        if "gatilho" in params:
            valor = params["gatilho"]
            if valor is not None and not isinstance(valor, str):
                raise ValueError(
                    "mira.set: 'gatilho' é o botão do «Só enquanto eu segurar», "
                    "ou null para a mira andar sempre"
                )
            pedidos["gatilho"] = valor or None
        for lado in ("inverter_horizontal", "inverter_vertical"):
            if lado in params:
                valor = params[lado]
                if not isinstance(valor, bool):
                    raise ValueError(f"mira.set: '{lado}' precisa ser boolean")
                pedidos[lado] = valor
        if "inclinacao" in params:
            valor = params["inclinacao"]
            if not isinstance(valor, str) or valor not in rot.DESTINOS_DA_INCLINACAO:
                raise ValueError(
                    "mira.set: 'inclinacao' é um de "
                    f"{', '.join(rot.DESTINOS_DA_INCLINACAO)} — o analógico que a "
                    "inclinação move, ou nenhum"
                )
            pedidos["acelerometro"] = valor
        if "toque" in params:
            valor = params["toque"]
            if valor not in rot.TOQUES:
                raise ValueError(
                    f"mira.set: 'toque' é um de {', '.join(rot.TOQUES)} — o "
                    "touchpad do computador, o cursor ou as zonas"
                )
            pedidos["toque"] = valor
        if not pedidos:
            raise ValueError(
                f"mira.set exige ao menos um de {', '.join(self._CAMPOS_DA_MIRA)} "
                "— campo omitido NÃO mexe na mira"
            )
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("mira.set: 'uniq' precisa ser string ou omitido")

        alvo = uniq or self._uniq_do_primario()
        if not alvo:
            return {
                "status": "sem_controle",
                "uniq": None,
                "motivo": (
                    "não há controle na mesa para mirar — a mira é POR PEÇA, e "
                    "cair no primeiro da lista faria a mesa cheia mirar sempre "
                    "com o mesmo controle"
                ),
            }
        chave = self._chave_de_peca_que_grava(alvo)
        if not chave:
            return {
                "status": "sem_endereco",
                "uniq": alvo,
                "motivo": (
                    f"{alvo!r} não é um endereço de rádio de uma peça de "
                    "plástico — sem MAC não há como mirar por um controle"
                ),
            }

        nativo = bool(
            self.daemon is not None and getattr(self.daemon, "is_native_mode", bool)()
        )
        if nativo and {"ligada", "inclinacao", "toque"} & set(params):
            logger.info("mira_set_recusado_no_nativo", uniq=chave)
            return {
                "status": "nativo",
                "uniq": alvo,
                "motivo": (
                    "Modo Nativo: o jogo lê o controle físico direto e não há "
                    "gamepad virtual onde a mira escreva — o chip não grava"
                ),
            }

        nome = self._perfil_que_grava()
        perfil: Any = None
        escritos: dict[str, Any] = {}
        if nome:
            from hefesto_dualsense4unix.profiles.loader import load_profile

            perfil = load_profile(nome)
            dele = (perfil.controllers or {}).get(chave)
            antes = getattr(dele, "movimento", None)
            escritos = dict(antes.model_dump(exclude_unset=True)) if antes else {}
        campos = {**escritos, **pedidos}
        try:
            secao = ProfileMovimentoConfig.model_validate(campos)
            mesa = (perfil.movimento if perfil is not None
                    else rot.parametros_da_peca(self.store, chave))
            arranjo = rot.arranjo_da_peca(mesa, secao)
        except ValueError as exc:
            raise ValueError(f"mira.set recusado: {exc}") from exc

        gravado = False
        if perfil is not None and escritos != campos:
            from hefesto_dualsense4unix.profiles.loader import save_profile

            atuais = dict(perfil.controllers or {})
            dele = atuais.get(chave) or ControllerOverrides()
            atuais[chave] = dele.model_copy(update={"movimento": secao})
            save_profile(perfil.model_copy(update={"controllers": atuais}))
            gravado = True

        rot.definir_da_peca(self.store, chave, arranjo)
        rot.sincronizar_o_filtro(self.store)

        ressalva: str | None = None
        if nativo:
            ressalva = (
                "Modo Nativo: o jogo lê o controle FÍSICO direto e não há gamepad "
                "virtual onde a mira escreva. Os ajustes ficam guardados e valem "
                "quando o modo voltar a Virtual ou Xbox."
            )
        logger.info(
            "mira_set",
            uniq=chave,
            perfil=nome,
            gravado=gravado,
            ligada=arranjo.ligado,
            sensibilidade=arranjo.sensibilidade,
            zona_morta_graus_s=arranjo.zona_morta_graus_s,
            gatilho=arranjo.gatilho,
            inverter_horizontal=arranjo.inverter_horizontal,
            inverter_vertical=arranjo.inverter_vertical,
            toque=arranjo.toque,
            acelerometro=arranjo.acelerometro,
            nativo=nativo,
        )
        return {
            "status": "ok",
            "uniq": alvo,
            "perfil": nome if isinstance(nome, str) else None,
            "gravado": gravado,
            "ligada": arranjo.ligado,
            "sensibilidade": arranjo.sensibilidade,
            "zona_morta_graus_s": arranjo.zona_morta_graus_s,
            "gatilho": arranjo.gatilho,
            "inverter_horizontal": arranjo.inverter_horizontal,
            "inverter_vertical": arranjo.inverter_vertical,
            "toque": arranjo.toque,
            "inclinacao": arranjo.acelerometro,
            "alcance": {"tique": "nao_se_aplica" if nativo else "aplicado"},
            "ressalva": ressalva,
        }

    async def _handle_haptica_testar(self, params: dict[str, Any]) -> dict[str, Any]:
        """`haptica.testar` — o botão «Háptica» da aba Vibração, num controle.

        A-ABA-VIBRACAO-TEM-O-SENSOR-HAPTICO-E-DOIS-TESTES-01 (02/10/2026).
        Params: ``{uniq: str, ligado: bool}``. Ligado, o tocador do aparelho
        daquele controle toca o par de teste (``alto_falante.PAR_DO_TESTE_DA_HAPTICA``)
        no endpoint dele, com o ganho da linha «Sensor Háptico»; desligado,
        cala. A janela rebate o ligado a cada segundo, e o teste que ninguém
        rebate solta sozinho. Mora no fim da classe para nenhuma citação
        ``arquivo:linha`` deste arquivo andar.

        Responde ``{status, uniq, ligado, leva}``: ``leva`` diz se o caminho
        até o controle está de pé agora (o laço do cabo, a ponte do rádio em
        háptica). ``sem_som`` quando o subsystem do som não está no ar.
        """
        uniq = params.get("uniq")
        if not isinstance(uniq, str) or not uniq.strip():
            raise ValueError("haptica.testar exige 'uniq': o teste é de um controle")
        ligado = params.get("ligado")
        if not isinstance(ligado, bool):
            raise ValueError("haptica.testar exige 'ligado' verdadeiro ou falso")
        sub = getattr(self.daemon, "_alto_falante_subsystem", None)
        testar = getattr(sub, "testar_a_haptica", None)
        if not callable(testar):
            return {
                "status": "sem_som",
                "motivo": "o som do Hefesto não está no ar; reinicie o serviço",
            }
        resposta = testar(uniq.strip(), ligado)
        return dict(resposta) if isinstance(resposta, dict) else {"status": "sem_som"}


    async def _handle_radio_busca_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """O «Procurar»: liga ou desliga a busca do rádio, com valor absoluto."""
        ligada = params.get("ligada")
        destino = params.get("destino")
        if not isinstance(ligada, bool):
            raise ValueError("radio.busca.set: `ligada` é true ou false")
        if destino is not None and not isinstance(destino, str):
            raise ValueError("radio.busca.set: `destino` é o endereço do adaptador")
        central = self._a_central()
        if central is None:
            return {"status": "sem_central", "busca": None}
        resposta = await asyncio.to_thread(
            central.ligar_a_busca, ligada, (destino or "").strip() or None)
        return dict(resposta)

    async def _handle_radio_dispensar(self, params: dict[str, Any]) -> dict[str, Any]:
        """O X do «Não Conectou»: o movimento acabado do aparelho sai da publicação."""
        aparelho = params.get("aparelho")
        if not isinstance(aparelho, str) or not aparelho.strip():
            raise ValueError("radio.dispensar: `aparelho` é o endereço do aparelho")
        central = self._a_central()
        if central is None:
            return {"status": "sem_central", "dispensado": False}
        atual = central.movimento_de(aparelho)
        if atual is not None and atual.em_curso:
            return {"status": "ocupado", "dispensado": False}
        return {"status": "ok", "dispensado": central.dispensar(aparelho) is not None}


def _uniq_do_rumble(params: dict[str, Any], metodo: str) -> str | None:
    """O ``uniq`` opcional do pedido de vibração: ausente é «o alvo de agora»."""
    uniq = params.get("uniq")
    if uniq is None:
        return None
    if not isinstance(uniq, str) or not uniq.strip():
        raise ValueError(f"{metodo}: 'uniq' precisa ser o endereço do controle")
    return uniq.strip()


def _chaves_dos_assentos(registry: Any) -> set[str]:
    """As chaves com ASSENTO na mesa de ``registry``: as ligadas e as guardadas."""
    ligados = IpcHandlersMixin._connected_keys(registry)
    lugares = getattr(registry, "lugares_da_mesa", None)
    if not callable(lugares):
        return ligados
    try:
        na_mesa = {int(r) for r in lugares()}
        postos = registry.snapshot().items()
    except Exception:
        return ligados
    return ligados | {str(k) for k, r in postos if r in na_mesa}


def _ligado(entrada: tuple[int, int, str, Any]) -> bool:
    """A entrada da mesa é de um controle LIGADO (e não de um lugar guardado)."""
    return entrada[2] in IpcHandlersMixin._connected_keys(entrada[3])


def _fora_da_mesa(mesa: list[tuple[int, int, str, Any]], numero: int) -> bool:
    """O número pedido não cabe — a MESMA conta do botão cinza da aba 04.

    A aba desenha o número como fora da mesa quando ele passa da quantidade de
    ligados E ninguém ligado o tem (``a04_iluminacao.um_botao_de_player``). Um
    número acima da conta que um ligado tem é troca; um que só um lugar
    guardado tem, ou que ninguém tem, é recusa — o daemon e a tela dizem a
    mesma coisa.
    """
    if numero <= sum(1 for e in mesa if _ligado(e)):
        return False
    return numero > len(mesa) or not _ligado(mesa[numero - 1])


def _amostra_da_luz_do_mic(cru: Any) -> int | None:
    """O `common[8]` do último pedido de luz do jogo, ou None (nunca um mock)."""
    if isinstance(cru, bool) or not isinstance(cru, int):
        return None
    return int(cru)


def _o_microfone_do_jogo_no_vpad(vp: Any) -> dict[str, Any]:
    """As chaves do microfone do jogo no bloco de um pad virtual."""
    mudo = getattr(vp, "mic_mudo_do_jogo_amostra", None)
    return {
        "mic_led_do_jogo": _contador_do_vpad(vp, "mic_led_do_jogo"),
        "mic_led_do_jogo_amostra": _amostra_da_luz_do_mic(
            getattr(vp, "mic_led_do_jogo_amostra", None)
        ),
        "mic_mudo_do_jogo": _contador_do_vpad(vp, "mic_mudo_do_jogo"),
        "mic_mudo_do_jogo_amostra": mudo if isinstance(mudo, bool) else None,
        "mic_eco_do_driver": _contador_do_vpad(vp, "mic_eco_do_driver"),
        "mic_do_jogo_retido": _contador_do_vpad(vp, "mic_do_jogo_retido"),
    }


def _a_luz_do_jogo_no_controle(status: dict[str, Any], uniq: Any) -> None:
    """`luz_do_mic_do_jogo` no `audio` do controle, só com o pedido de pé."""
    from hefesto_dualsense4unix.daemon.subsystems.luz_do_mic import luz_do_mic_do_jogo

    do_jogo = luz_do_mic_do_jogo(str(uniq or ""))
    if do_jogo is not None:
        status["luz_do_mic_do_jogo"] = int(do_jogo)


__all__ = ["DraftApplier", "IpcHandlersMixin"]
