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
from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from hefesto_dualsense4unix.core.controller import IController
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol
    from hefesto_dualsense4unix.daemon.state_store import StateStore


def origem_do_pedido(params: dict[str, Any] | None) -> Literal["manual", "profile"]:
    """A origem declarada pelo cliente. Silêncio = automático, nunca "manual".

    ORIGEM-QUE-MENTE-01 (08/08/2026). Os setters do daemon tinham `origin`
    com default `"manual"`, e o protocolo IPC não expunha o campo — então o
    daemon lia a AUSÊNCIA de informação como a mão dela, e um cliente que
    apenas reconciliava estado era promovido a gesto humano.

    O custo, MEDIDO: com o Sackboy aberto e marcado na allowlist do Steam
    Input, isso furou o portão JOGO-01 (`gamepad.py`, `if origin != "manual"`),
    devolveu o gamepad virtual com o grab e o esconde-esconde pulados, e o jogo
    passou a ver o controle físico E o virtual. Ela fotografou um "Jogador 3"
    fantasma. Ver JOGADOR-3-FANTASMA-01.

    A regra aqui é assimétrica de propósito, e é a inversão do default antigo:
    **"manual" só quando o cliente DIZ que é manual.** Errar para "profile"
    custa, no pior caso, um gesto dela que não fura o portão — e o produto lhe
    diz por quê. Errar para "manual", como antes, custa o controle dela no meio
    da partida.
    """
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


#: STATUS-01: TTL (s) da leitura sysfs por nó LED no enriquecimento do
#: `state_full`. O tick da GUI é 10 Hz (`LIVE_POLL_INTERVAL_MS=100`) e
#: `multi_intensity`/`brightness` são I/O de arquivo — sem o cache seriam até
#: 20 opens/s POR CONTROLE. Cor de lightbar com 1 s de frescor é imperceptível.
_LIGHTBAR_READ_TTL_SEC = 1.0

#: Fix cross-cutting U x G/HANG-01 (2026-07-20, MEDIUM): teto (s) para
#: `identity.renumber` adquirir os `RLock` de instância de
#: `lock_for_renumber`. O MESMO lock é tomado por `ExternalLedSync.tick()`
#: (via `sync_connected`→`_save_locked`, I/O de disco) rodando no pool
#: dedicado `hefesto-ext` sob `EXTERNAL_TICK_TIMEOUT_SEC` — se aquele worker
#: travar segurando o lock, um `acquire()` sem teto aqui bloquearia o ÚNICO
#: event loop do daemon para sempre (zero read_state, zero rumble, zero
#: watchdog), a mesma classe de incidente que HANG-01 foi desenhado para
#: conter. `asyncio.wait_for` devolve erro ao IPC em vez de pendurar o loop.
_IDENTITY_RENUMBER_LOCK_TIMEOUT_SEC = 5.0

#: COOP-SEM-INTERRUPTOR-01 (06/08/2026): a razão que o `coop.set` devolve a
#: quem pede para DESLIGAR o co-op. Texto único, e é dela: *"se eu conecto 4
#: controles no PC eu espero, com 4 pessoas jogando, que cada um controle o
#: próprio personagem. Ninguém esperaria controlar o mesmo personagem com cada
#: controle."* Fica aqui, e não em `subsystems/coop.py`, porque é POLÍTICA da
#: superfície de comando — o mecanismo (grab, vpad por jogador, player-LED)
#: não mudou uma linha.
COOP_SEMPRE_LIGADO_MOTIVO = (
    "o co-op local é sempre ligado: cada controle conectado é um jogador. "
    "Para um controle de reserva, deixe-o desconectado."
)


class _RenumberAuthorityChangedError(Exception):
    """F3: um jogo abriu enquanto o renumber esperava os locks — abortar.

    Levantada por `_renumber_locked` (na thread do `to_thread`) quando a
    re-checagem de autoridade pós-acquire vê `display_authority == 'game'`.
    No caminho normal vira `{"ok": False, "reason": "sessao_de_jogo_aberta"}`;
    na thread-zumbi de um `lock_timeout` já respondido, morre silenciosa —
    que é exatamente o objetivo (o compact atrasado não roda).
    """


class _NumeroAlvoAusenteError(Exception):
    """PLAYER-01: pediram um número para um controle que não está na mesa.

    O número EXIBIDO só existe para quem está presente (NUM-01: é a
    colocação entre os presentes). Atribuir número a um ausente seria
    ressuscitar o defeito que a NUM-01 curou — um endereço desligado
    segurando um número e empurrando quem está jogando para cima. Vira
    ``{"ok": False, "reason": "controle_ausente"}``: falha VISÍVEL, nunca
    escrita silenciosa.
    """


class _NumeroForaDaMesaError(Exception):
    """PLAYER-01: pediram um número maior do que a quantidade de presentes.

    Carrega o teto real para a resposta poder dizê-lo (a janela pode ter
    desenhado quatro botões um instante antes de um controle cair). Vira
    ``{"ok": False, "reason": "numero_fora_da_mesa", "max": N}``.
    """

    def __init__(self, maximo: int) -> None:
        super().__init__(f"numero fora da mesa (max={maximo})")
        self.maximo = maximo


#: GUI-05 item 3: TTL (s) da leitura do marker `last_run` do wrapper no
#: `state_full` — leitura de arquivo, mesma justificativa do cache acima.
_WRAPPER_MARKER_TTL_SEC = 2.0


# ---------------------------------------------------------------------------
# CONTROLE-QUE-NAO-ENTROU-01 (09/08/2026): o controle que está LIGADO e que o
# sistema não conseguiu entregar ao Hefesto.
#
# Medido na máquina dela em 09/08: dois DualSense ligados e pareados, e a
# janela mostrava UM. O driver do kernel abortou o segundo na probe
# (`probe with driver playstation failed`) — e um controle assim conecta no
# rádio, acende a luz do próprio firmware e NÃO tem hidraw, nem nó de LED, nem
# dispositivo de entrada. Como `describe_controllers` devolve uma entrada por
# HANDLE ABERTO, ele simplesmente não existe para nós; a aba Início chegava a
# escrever "Nenhum controle conectado." para um controle ligado e pareado.
#
# Ele NÃO é um controle desconectado (está no rádio) e NÃO é um externo (não
# tem `/dev/input` para o inventário de externos enumerar): é um TERCEIRO
# estado, e era ele que o produto não sabia representar.
#
# A REGRA É DE UM DONO SÓ, e o dono é `scripts/bt_rebind_orphans.sh` — a cura
# que roda de 2 em 2 minutos pela vigia `bt_health_watchdog.sh`. O que está
# aqui é a MESMA leitura, para EXIBIR o que aquele script vai tentar curar; se
# os dois discordarem, a janela promete uma cura que não vem. É por isso que o
# teste desta leva confere estas três constantes contra o texto do script.
# ---------------------------------------------------------------------------

#: Onde o kernel lista os devices HID. Parametrizável só como COSTURA DE
#: TESTE (a suíte aponta para um diretório temporário) — em produção o default
#: é o que vale, exatamente como no script.
_HID_DEVICES_DIR = "/sys/bus/hid/devices"

#: Barramento 0005 = Bluetooth. É o único onde a contenção de probe medida
#: acontece, e é o que exclui por construção o gamepad virtual do próprio
#: Hefesto, que nasce por uhid no barramento 0003.
_HID_ORFAO_BUS = "0005"

#: Vendor 054C = Sony — o dono é o driver `playstation`. Device órfão de
#: qualquer outro fabricante é problema de outra pessoa, e o script não o toca.
_HID_ORFAO_VID = "054C"

#: TTL (s) da varredura do sysfs no `state_full`. O tick da GUI é 10 Hz e este
#: é um fato que muda por gesto humano (ligar/desligar controle) — sem o cache
#: seriam 10 `listdir` por segundo para responder a mesma pergunta. Mesmo
#: padrão e mesmo número do cache do marker do wrapper, logo acima.
_HID_ORFAOS_TTL_SEC = 2.0


def _e_dualsense_por_bluetooth(id_do_device: str) -> bool:
    """O nome do diretório é ``BUS:VID:PID.INSTANCIA`` — ex. ``0005:054C:0CE6.000F``.

    Mesmo `_e_candidato` do `bt_rebind_orphans.sh`, traduzido: barramento
    Bluetooth **e** vendor Sony. O `upper()` no vendor repete o `tr a-f A-F`
    do script — o kernel escreve em maiúsculas, mas a comparação não pode
    depender disso.
    """
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
        # `os.path.exists` e não `lexists`: o `[[ -e ]]` do script SEGUE o
        # symlink, e as duas leituras têm de dizer a mesma coisa.
        if os.path.exists(os.path.join(alvo, id_do_device, "driver")):
            continue  # tem driver: o sistema o adotou, nada a dizer
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
    """Uma idade em segundos saneada para o payload, ou None.

    MOTOR-QUE-NAO-SE-VE-01. `None` significa **nunca aconteceu**, e é
    diferente de `0.0`, que é "acabou de acontecer" — a mesma distinção que o
    `visto_ha_s` faz omitindo a categoria. Publicar zero para "nunca" apagaria
    a diferença e faria a tela dizer que os motores acabaram de girar num vpad
    que nunca vibrou.
    """
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
    """(flag0, flag1, flag2, weak, strong) do último descarte, nomeado.

    RUMBLE-QUE-NAO-SE-SENTE-01 — é o dado que diz QUAL codificação de vibração
    chegou sem o gate reconhecer. Vai nomeado, e não como lista de cinco
    números, porque quem vai ler isto numa madrugada precisa saber qual byte é
    qual sem abrir o código.
    """
    if not isinstance(cru, tuple) or len(cru) != 5:
        return None
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in cru):
        return None
    nomes = ("flag0", "flag1", "flag2", "weak", "strong")
    return dict(zip(nomes, (int(v) for v in cru), strict=True))


def _anel_de_vibracao(cru: Any) -> list[dict[str, Any]] | None:
    """Os últimos reports de vibração do vpad, nomeados (QUEM ESCREVEU-01).

    Cada item vira ``{ha_s, flag0, flag1, flag2, weak, strong, ramo}``. É a
    prova que os contadores não dão: *quem* escreveu o report e *o quê*. O
    caso medido em 09/08 (``plays=4`` com força zero em todas) tem dois
    autores possíveis — o jogo pelo hidraw e o ``hid_playstation`` do kernel
    traduzindo force-feedback do nó evdev —, e só os bytes os separam.

    ``None`` quando o vpad não expõe o anel (backend uinput, dublê de teste):
    lista vazia diria "nada chegou", e "não sei" é outra coisa.
    """
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
    """MAC 12-hex normalizado de uma key/serial do backend, ou None.

    Mesma normalização + guarda de comprimento do `_key_to_uniq` do backend
    (uma key de fallback por path contém dígitos hex soltos e viraria um
    pseudo-MAC sem a guarda). Vive aqui para o handler casar as keys de
    `_sysfs`/`_sysfs_written` (serial com `:`) com o `uniq` do
    `describe_controllers` sem depender de método privado do backend.
    """
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


# --- 8BIT-01: inventário de gamepads externos (opt-in do controller.list) ----

#: Orçamentos da sonda "quem segura o hidraw" (opcional e degradável): pgrep
#: com timeout curto e varredura de /proc/<pid>/fd com teto de tempo — o
#: estudo mediu ~6 ms para ~4600 fds, então 0.5 s é folga patológica. A sonda
#: roda na MESMA thread do inventário (nunca no event loop).
#:
#: ESCRITOR-CRU-01: os três números moram agora em `core/escritor_cru.py`
#: (`PGREP_TIMEOUT_S`, `ORCAMENTO_DA_VARREDURA_S`, `MAX_PIDS_DA_STEAM`), junto
#: com a sonda que os usa. Estes aliases ficam porque o número medido é o
#: mesmo e quem lia daqui não precisa saber que a casa mudou.
_HOLDERS_PGREP_TIMEOUT_SEC = _escritor_cru.PGREP_TIMEOUT_S
_HOLDERS_SCAN_BUDGET_SEC = _escritor_cru.ORCAMENTO_DA_VARREDURA_S
_HOLDERS_MAX_STEAM_PIDS = _escritor_cru.MAX_PIDS_DA_STEAM


def _steam_pids() -> list[int]:
    """PIDs do processo Steam via pgrep — padrões do `steam_running` canônico.

    ESCRITOR-CRU-01: a implementação MUDOU DE CASA para
    `core/escritor_cru.py`, e este nome ficou como porta (o inventário de
    externos e a suíte o conhecem). A razão de ter uma casa só é a de sempre:
    quando o vigia da lightbar passou a fazer a MESMA pergunta que o
    inventário de externos já fazia, duas cópias seriam duas verdades sobre
    quem segura o mesmo `/dev/hidrawN`.
    """
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
        # EXT-04: a MESMA identidade que o tick usa para numerar/acender o LED
        # (`ExternalLedSync.tick`) — hoje resolvida pela função ÚNICA
        # `identity_for_entry`. Um externo SEM MAC era resolvido por uniq=None
        # (sempre None) e caía no posicional, exibindo número != do LED aceso
        # quando havia slot de DualSense reservado.
        #
        # CLONE-01: ela é CARIMBADA no payload. Aqui é o único ponto do sistema
        # que a resolve com o sysfs do aparelho à mão E fala com a GUI; deixar a
        # GUI recalcular seria pedir a ela um `realpath` em `/sys` a cada
        # repintura de botão — de outro processo, sobre um aparelho que pode já
        # ter saído — para chegar (na melhor das hipóteses) na mesma string.
        identity = identity_for_entry(entry)
        entry[EXTERNAL_IDENTITY_FIELD] = identity
        slot: int | None = None
        if slot_resolver is not None:
            # `peek` continua assign=False (leitura pura).
            with contextlib.suppress(Exception):
                raw = slot_resolver(identity)
                if isinstance(raw, int) and not isinstance(raw, bool):
                    slot = raw
        # NUMA-05/R-24: o resolver é a fonte ÚNICA, mesmo devolvendo None (sem
        # opinião ainda) ou tendo levantado (suppress acima); SEM resolver o
        # campo é `None`, nunca o posicional — não existe segundo espaço de
        # numeração.
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

    #: GUI-05 item 3: cache TTL do marker `last_run` do wrapper (leitura de
    #: arquivo — o state_full roda a 10-20 Hz) e a PRIMEIRA detecção do appid
    #: em foco (base da janela de ~120s). Mesmo padrão do cache acima: class
    #: attributes (o mixin não é dataclass) com shadow por instância no 1º uso.
    _wrapper_marker_cache: tuple[float, tuple[int, int] | None] | None = None
    _wrapper_first_seen: tuple[int, float] | None = None

    #: CONTROLE-QUE-NAO-ENTROU-01: cache TTL da varredura de
    #: `/sys/bus/hid/devices` (ver `dualsense_sem_driver`). Mesmo padrão dos
    #: caches acima: class attribute (o mixin não é dataclass) com shadow por
    #: instância no primeiro uso.
    _hid_orfaos_cache: tuple[float, list[str]] | None = None

    #: S2 (sensores na aba Status): `SensorHub` lazy — os readers de
    #: giroscópio/touchpad só nascem quando alguém pede o `state_full` e
    #: morrem sozinhos quando param de ser pedidos. Mesmo padrão dos caches
    #: acima: class attribute (o mixin não é dataclass) com shadow por
    #: instância no primeiro uso.
    _sensor_hub: Any = None

    # --- perfis ----------------------------------------------------------

    async def _handle_profile_switch(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica perfil escolhido pelo usuário (entrada manual via IPC).

        Persistência (CLUSTER-IPC-STATE-PROFILE-01 Bug B):
          - `manager.activate(name, origin="manual")` grava `session.json`
            (canônico — usado pelo daemon em `restore_last_profile` no
            boot/reconnect). PERFIL-03: este handler é gesto MANUAL da
            usuária (GUI/CLI) — só os origins "manual" persistem a intenção.
          - Adicionalmente, escrevemos `active_profile.txt` para paridade com
            a CLI legada (`hefesto-dualsense4unix profile current` ainda lê esse marker).
          - Falha em escrever o marker é best-effort: loga warning mas não
            falha o IPC. Atomicidade do conjunto: se `activate` levantar,
            `active_profile.txt` NÃO é tocado.

        Lock manual (Bug C): após persistir, ativa lock de
        ``MANUAL_PROFILE_LOCK_SEC`` segundos no `StateStore` para suprimir
        autoswitch enquanto o usuário "respira" — autoswitch volta ao normal
        quando o lock expira.

        R-03 (auditoria 23/07): a resposta passou a contar a VERDADE. Antes ela
        era `{"active_profile": nome}` mesmo quando o lock de gesto manual fazia
        os appliers descartarem `mode`/`mouse`/supressão — a GUI dizia "perfil
        ativo" com a máscara errada e nada reaplicava depois. Campos ADITIVOS
        (`secoes`, `mode_aplicado`, `motivo`, `expira_em_sec`): GUI antiga com
        daemon novo continua lendo só `active_profile`.
        """
        name = params.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("profile.switch exige 'name' string")
        relatorio: dict[str, str] = {}
        # TRAVA-QUE-SOLTA-TARDE-01 (medido ao vivo, 05/08): o clear e o lock
        # vêm ANTES do `activate`. Até aqui eles vinham depois, e a ativação
        # inteira rodava com a trava ainda armada — `manager.apply` pulava as
        # categorias travadas (emitindo `None` no `OutputSpec`) e o handler
        # respondia "ativado". A trava era limpa tarde demais para a ativação
        # que a limpou: valia só para a PRÓXIMA. No journal dela, duas
        # ativações idênticas do mesmo perfil davam resultados diferentes.
        # O caminho automático (`autoswitch.py:505-518`) sempre fez assim —
        # limpa e SÓ ENTÃO aplica; eram os dois gestos EXPLÍCITOS que estavam
        # invertidos. Ver `tests/unit/test_trava_que_solta_tarde_01.py`.
        #
        # O lock sobe junto e pelo mesmo motivo: entre soltar a trava e
        # terminar o `activate` não pode existir janela em que nem a trava nem
        # o lock suprimam o autoswitch (Bug C).
        import time as _time

        from hefesto_dualsense4unix.daemon.state_store import (
            MANUAL_PROFILE_LOCK_SEC,
        )
        # `getattr` pelo mesmo motivo que `ProfileManager._categorias_travadas`
        # (`profiles/manager.py:384-387`): dublês de teste e stores parciais
        # continuam funcionando, e "não sei listar" vira "nada a restaurar".
        travadas_antes = getattr(self.store, "manual_override_categories", ()) or ()
        lock_antes = getattr(self.store, "_manual_profile_lock_until", 0.0)
        # Usuário escolheu perfil explícito: libera autoswitch de novo
        # (BUG-MOUSE-TRIGGERS-01).
        self.store.clear_manual_trigger_active()
        # Bug C: arma lock manual; autoswitch suprime por
        # MANUAL_PROFILE_LOCK_SEC segundos.
        self.store.mark_manual_profile_lock(
            _time.monotonic() + MANUAL_PROFILE_LOCK_SEC
        )
        try:
            profile = self.profile_manager.activate(
                name, origin="manual", relatorio=relatorio
            )
        except Exception:
            # Atomicidade (a mesma que a docstring já promete ao marker): uma
            # ativação que FALHOU não é gesto cumprido, e não pode custar a ela
            # a trava que ela tinha armado — `profile.switch` com nome
            # inexistente apagaria a configuração feita na mão.
            #
            # E o LOCK volta junto: sem isto, um nome errado congelava a troca
            # automática por MANUAL_PROFILE_LOCK_SEC (30 s) sem que gesto nenhum
            # tivesse sido cumprido. Borda aberta pela própria subida do lock
            # (TRAVA-QUE-SOLTA-TARDE-01) e apontada na revisão.
            for categoria in travadas_antes:
                self.store.mark_manual_trigger_active(categoria)
            self.store.mark_manual_profile_lock(lock_antes)
            raise
        # Bug B: paridade do marker da CLI legada com session.json.
        from hefesto_dualsense4unix.utils.session import save_active_marker
        save_active_marker(profile.name)
        # DEDUP-04: gatilho "mudança de perfil" — perfis com `steam_app_<id>`
        # no match materializam arquivo de env próprio; a troca manual também
        # pode ter mudado modo/máscara via apply do perfil.
        if self.daemon is not None:
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.launch_env import (
                    materialize_launch_env,
                )

                materialize_launch_env(self.daemon)
        # R-03: `mode` é a seção que a usuária SENTE (máscara do vpad + co-op).
        # Ausente no relatório = não havia applier de modo fiado (CLI/testes) —
        # aí não há o que desmentir, e o estado honesto é "aplicado".
        estado_modo = relatorio.get("mode", "aplicado")
        resposta: dict[str, Any] = {
            "active_profile": profile.name,
            "mode_aplicado": estado_modo == "aplicado",
            "secoes": dict(relatorio),
        }
        if estado_modo != "aplicado":
            resposta["motivo"] = estado_modo
            if estado_modo.startswith("adiado"):
                # Segundos até o dreno da pendência poder rodar (R-03). Só faz
                # sentido no adiamento por lock; `getattr` + isinstance porque o
                # daemon aqui pode ser um dublê (MagicMock devolve mock para
                # qualquer atributo).
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
        profiles = self.profile_manager.list_profiles()
        return {
            "profiles": [
                {
                    "name": p.name,
                    "priority": p.priority,
                    # R-12 item 3: o discriminador CRU, não um ternário — com o
                    # sentinel `manual` no schema, "tudo que não é any é
                    # criteria" faria a GUI escrever "Só neste programa" num
                    # perfil que nunca ativa sozinho.
                    "match_type": getattr(p.match, "type", "criteria"),
                }
                for p in profiles
            ]
        }

    async def _handle_profile_apply_draft(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Aplica draft completo em ordem canonica: leds -> triggers -> rumble -> mouse.

        Cada setor é aplicado de forma best-effort pelo `DraftApplier`: falha em
        um setor loga warning mas não bloqueia os demais. Retorna lista
        ``applied`` com setores que foram aplicados com sucesso
        (FEAT-PROFILE-STATE-01) e o mapa ``failed`` (setor -> motivo curto) com
        os que NÃO entraram (APLICAR-VERDADE-01).

        ``status`` continua sendo sempre ``"ok"`` de propósito: applet, CLI e
        TUI decidem por ele e passariam a dizer "daemon offline" para uma
        seção que simplesmente falhou. A verdade nova é ADITIVA — quem quiser
        saber o que ficou de fora lê ``failed``.
        """
        applier = DraftApplier(
            controller=self.controller,
            store=self.store,
            daemon=self.daemon,
        )
        applied = applier.apply(params)
        return {"status": "ok", "applied": applied, "failed": dict(applier.failed)}

    # --- triggers --------------------------------------------------------

    def _apply_por_uniq(self, params: dict[str, Any], **campos: Any) -> str | None:
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
        """
        alvo = params.get("uniq")
        if not isinstance(alvo, str) or not alvo:
            return None
        apply_for = getattr(self.controller, "apply_output_for", None)
        if not callable(apply_for):
            return None
        from hefesto_dualsense4unix.core.controller import OutputSpec

        resultado = apply_for(alvo, OutputSpec(**campos))
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
        except Exception as exc:  # observabilidade > silêncio
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

    def _registrar_em_todos(self, **campos: Any) -> list[str]:
        """Registra ``campos`` na camada da USUÁRIA de CADA controle conectado.

        BROADCAST-QUE-NAO-MENTE-01 (02/08), medido na máquina dela: ``led.set``
        SEM ``uniq`` respondia ``{"status": "ok"}`` e o sysfs NÃO mudava — os
        dois controles continuavam com a cor da paleta (azul do slot 1,
        vermelho do slot 2). Com ``uniq``, a mesma cor pegava e ficava.

        A causa é a ORDEM DAS CAMADAS do merge, não a escrita. ``set_led``
        escreve no hardware E grava o valor em ``_desired_default``
        (``_record_desired_locked`` com alvo ``None``,
        ``core/backend_pydualsense.py:1335``); o ``reassert_resolved_outputs``
        logo abaixo re-resolve por controle, e o ``_merged_desired_for_key``
        (``core/backend_pydualsense.py:1222``) põe a camada AUTOMÁTICA do slot
        (COR-03) EM CIMA do default — a paleta repinta por cima da cor que
        acabou de sair. O caminho por-``uniq`` SEMPRE funcionou pelo mesmo
        motivo, ao contrário: ``apply_output_for`` grava em ``_desired_by_uniq``,
        que no mesmo merge fica ACIMA da automática. E não adiantaria arrancar
        o reassert imediato: a defesa de exibição (NUMA-03, ``defend_display``)
        e o próximo hotplug re-resolvem pelo MESMO merge — a cor voltaria
        segundos depois em vez de instantes.

        A camada não é nova: é exatamente o que a GUI já faz desde a R-14
        (``app/actions/lightbar_actions.py:828`` ``_enviar_led_em_todos`` —
        "Todos" vira um pedido POR MAC, "sem desligar o automático"). O que
        faltava era o DAEMON fazer o mesmo para quem não é a GUI: a CLI
        (``hefesto test lightbar``) e qualquer chamada IPC direta continuavam
        caindo no broadcast cru e recebendo um "ok" que não valia nada.

        Roda DEPOIS da escrita clássica de propósito, nesta ordem: o broadcast
        grava o default (é ele que pinta quem chegar DEPOIS, no hotplug — a
        decisão "mudei todos para azul, repluguei e um voltou verde") e limpa o
        campo dos overrides; só então cada conectado recebe de volta o MESMO
        valor, agora na camada que sobrevive ao reassert. Inverter a ordem
        apagaria o que acabamos de registrar.

        O que NÃO muda: a camada GAME continua acima desta (o fix cross-cutting
        U x N segue valendo — sob ``display_authority=='game'`` o jogo vence no
        reassert), e a camada do CO-OP continua acima para ``player_leds``.

        Devolve os MACs em que o registro entrou — lista vazia quando o backend
        não expõe ``apply_output_for``/``describe_controllers`` ou a mesa está
        vazia. É essa lista que a resposta publica em ``aplicado_em``.
        """
        apply_for = getattr(self.controller, "apply_output_for", None)
        if not callable(apply_for):
            return []
        alvos = self._uniqs_conectados()
        if not alvos:
            return []
        from hefesto_dualsense4unix.core.controller import OutputSpec

        spec = OutputSpec(**campos)
        aplicados: list[str] = []
        for alvo in alvos:
            try:
                apply_for(alvo, spec)
            except Exception as exc:
                # Um controle que recusa não pode calar os outros (mesma
                # disciplina do fan-out de `_for_each` no backend).
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
        * **Não** promete ``guardado_em`` — pelo mesmo nivelamento não há
          promessa por-controle a publicar: o valor foi para o default, sem
          endereço. Publicar um MAC aqui seria mandar a usuária esperar por um
          controle que não é o dono do que ela pediu.
        * **Não** afirma nada em **Modo Nativo**: o ``report_thread`` está mudo
          e nenhum byte sai (CONSERTO 1.3). É onde a rota irmã ainda mente —
          medido em 14/08, ``led.set`` sem ``uniq`` com o output mutado responde
          ``aplicado_em`` com os dois MACs e ZERO byte no fio, porque
          ``_registrar_em_todos`` ignora a palavra que o backend devolve.
        * **Não** afirma quando não sabe: mesa vazia, backend que não diz quem
          está nela nem onde o seletor está, ou alvo do seletor sem MAC estável
          (key por path) devolvem as duas listas vazias — o "não sei dizer em
          quem" que o comentário do ``led.set`` já fixou.

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
        # PERFIL-05: `uniq` presente = gatilho por-MAC via apply_output_for
        # (override registrado + escrita só no controle selecionado).
        campos = (
            {"trigger_left": effect} if side == "left" else {"trigger_right": effect}
        )
        resultado = self._apply_por_uniq(params, **campos)
        if resultado is None:
            self.controller.set_trigger(side, effect)
            # Conserto 1.4: a rota clássica (sem `uniq`) respondia as duas
            # listas vazias MESMO TENDO ESCRITO — a rota irmã `led.set` dizia a
            # mesa inteira, e a tela lê as duas. Agora ela diz em quem pegou, e
            # só quando sabe; ver `_destinos_do_broadcast` para o que ela se
            # recusa a afirmar (Modo Nativo, mesa vazia, alvo sem MAC) e por que
            # `guardado_em` fica sempre vazio aqui.
            aplicado_em, guardado_em = self._destinos_do_broadcast()
        else:
            aplicado_em, guardado_em = self._destinos_por_uniq(
                resultado, str(params["uniq"])
            )
        # BUG-MOUSE-TRIGGERS-01: usuário aplicou trigger manual via GUI/IPC.
        # Marca override para o autoswitch não sobrescrever (especialmente
        # ao ligar emulação de mouse, cujo movimento muda foco de janela).
        self.store.mark_manual_trigger_active("trigger")
        # MESA-CHEIA-09 (E2): espelho do `led.set` — mesmo nome de campo, mesma
        # semântica de vazio. Era o único comando de saída que respondia
        # `{"status": "ok"}` seco, e a aba Gatilhos dizia "aplicado" em três
        # casos sem byte nenhum. Conserto 1.4 — os três da sprint são: alvo
        # DESCONECTADO, alvo SEM MAC estável, e MODO NATIVO com output mutado.
        # O comentário antigo trocava o Modo Nativo por "mesa vazia" e escondia
        # justamente o caso que só morreu no conserto 1.3 (quando
        # `apply_output_for` passou a devolver «registrado» sob o mute). Mesa
        # vazia é caso da rota CLÁSSICA, e mora em `_destinos_do_broadcast`.
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
            # Conserto 1.4: mesma rota clássica do `trigger.set` — "Desligar"
            # com "Todos" no seletor também escreve, e também dizia `[]`.
            aplicado_em, guardado_em = self._destinos_do_broadcast()
        else:
            aplicado_em, guardado_em = self._destinos_por_uniq(
                resultado, str(params["uniq"])
            )
        self.store.clear_manual_trigger_active("trigger")
        # MESA-CHEIA-09 (E2): mesmo contrato do `trigger.set` — "Desligar" num
        # controle fora da mesa é GUARDADO, não aplicado.
        return {
            "status": "ok",
            "aplicado_em": aplicado_em,
            "guardado_em": guardado_em,
        }

    # --- leds ------------------------------------------------------------

    async def _handle_led_set(self, params: dict[str, Any]) -> dict[str, Any]:
        rgb = params.get("rgb")
        if not isinstance(rgb, list) or len(rgb) != 3:
            raise ValueError("led.set: rgb precisa ser lista com 3 inteiros")
        for idx, v in enumerate(rgb):
            if not isinstance(v, int) or not (0 <= v <= 255):
                raise ValueError(f"led.set: rgb[{idx}] fora de byte")
        # brightness opcional (FEAT-LED-BRIGHTNESS-01): multiplicador 0.0-1.0.
        # Ausente ou inválido -> assume 1.0 (retrocompatível com chamadas v1).
        brightness_raw = params.get("brightness", 1.0)
        try:
            brightness = float(brightness_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("led.set: brightness precisa ser numerico") from exc
        if not (0.0 <= brightness <= 1.0):
            raise ValueError(
                f"led.set: brightness fora de [0.0, 1.0]: {brightness}"
            )
        r = max(0, min(255, int(rgb[0] * brightness)))
        g = max(0, min(255, int(rgb[1] * brightness)))
        b = max(0, min(255, int(rgb[2] * brightness)))
        # PERFIL-05 (22/07): com um controle selecionado no seletor, a GUI
        # manda o MAC (`uniq`) e a escrita vai por `apply_output_for` —
        # registra o override por-uniq (acima da paleta no merge, sobrevive
        # a hotplug) e escreve SÓ naquele controle. Antes, o caminho vivo por
        # índice (`_output_target_key`) caía em BROADCAST quando o alvo
        # desalinhava — "configurei o controle 2 e mudou todos".
        resultado = self._apply_por_uniq(params, led=(r, g, b))
        guardado_em: list[str] = []
        if resultado is not None:
            # MESA-CHEIA-09 (E1): era `[uniq]` SEMPRE — com o controle fora da
            # mesa, o campo criado para o daemon parar de mentir mentia.
            aplicado_em, guardado_em = self._destinos_por_uniq(
                resultado, str(params["uniq"])
            )
        else:
            self.controller.set_led((r, g, b))
            # BROADCAST-QUE-NAO-MENTE-01 (02/08): a escrita acima grava o
            # default e pinta o hardware, mas o default fica ABAIXO da paleta
            # automática no merge — sem a linha seguinte, o reassert logo
            # abaixo repinta a cor do slot por cima e o handler responderia
            # "ok" para uma cor que nunca ficou. Ver `_registrar_em_todos`.
            aplicado_em = self._registrar_em_todos(led=(r, g, b))
        # Fix cross-cutting U x N (2026-07-20, HIGH): `set_led` escreve CRU via
        # `_for_each_led` (gate só `_output_mute`, nunca `_game_wins`) — sem
        # isto a cor do JOGO ficava sobrescrita na hora, e a trava manual
        # logo abaixo impedia até o autoswitch corrigir no próximo alt-tab.
        # `reassert_resolved_outputs` (getattr defensivo, mesmo padrão de
        # `identity.renumber` e `DraftApplier._apply_leds`) reaplica o
        # RESOLVIDO por-controle já com a escrita acima registrada em
        # `_desired` — se `display_authority=='game'`, o merge devolve a cor
        # do jogo por cima; sem jogo com autoridade, a cor manual "gruda"
        # normalmente. O gate de N deixa de ser furável por aqui.
        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()
        # ONDA-U (Causa A): mesma trava de trigger.set — sem ela o
        # AutoSwitcher reescrevia a cor no próximo tick de troca de foco
        # ("perfil eterno", U9). Categoria "led" (F1): o fim do "Testar
        # motores" limpa só "rumble" e esta cor sobrevive.
        self.store.mark_manual_trigger_active("led")
        # APLICAR-VERDADE-01: `status` segue sempre "ok" (applet, CLI e TUI
        # decidem por ele e passariam a dizer "daemon offline"); a verdade nova
        # é ADITIVA. `aplicado_em` diz em QUE controles a intenção ficou
        # registrada na camada que sobrevive ao reassert — vazio significa
        # "escrita global sem registro por controle" (backend sem a API
        # por-uniq, ou mesa vazia), que era justamente o caso em que o "ok"
        # mentia.
        return {
            "status": "ok",
            "aplicado_em": aplicado_em,
            "guardado_em": guardado_em,
        }

    async def _handle_led_player_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica bitmask de 5 LEDs de player no controle.

        Params:
            bits: lista de 5 booleanos (LED1..LED5).
        """
        bits_raw = params.get("bits")
        if not isinstance(bits_raw, list) or len(bits_raw) != 5:
            raise ValueError("led.player_set: 'bits' precisa ser lista com exatamente 5 booleanos")
        for idx, v in enumerate(bits_raw):
            if not isinstance(v, bool):
                raise ValueError(f"led.player_set: bits[{idx}] precisa ser booleano")
        bits: tuple[bool, bool, bool, bool, bool] = (
            bits_raw[0], bits_raw[1], bits_raw[2], bits_raw[3], bits_raw[4]
        )
        # PERFIL-05: mesmo contrato do led.set — `uniq` presente = escrita
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
        # sob `display_authority=='game'`) corrigir a escrita crua acima
        # antes de a trava manual abaixo bloquear o autoswitch.
        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()
        # ONDA-U (Causa A): mesma trava de trigger.set (U9), categoria "led".
        self.store.mark_manual_trigger_active("led")
        # APLICAR-VERDADE-01, mesma decisão do `led.set`: `aplicado_em` é
        # aditivo e `bits` (contrato de quem já lê a resposta) fica intacto.
        return {
            "status": "ok",
            "bits": list(bits),
            "aplicado_em": aplicado_em,
            "guardado_em": guardado_em,
        }

    # --- identidade (numeração) -------------------------------------------

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

        # F3 (auditoria 21/07): `asyncio.to_thread` não é cancelável — no
        # timeout o handler responde `lock_timeout`, mas a thread segue presa
        # no acquire() e o compact RODAVA depois (minutos, se preciso) mesmo
        # com jogo já aberto, repintando LEDs no meio da partida. A autoridade
        # é re-checada DENTRO dos locks, pela própria thread, no instante em
        # que ela finalmente vai compactar — o zumbi vira abort limpo.
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

        reassert = getattr(self.controller, "reassert_resolved_outputs", None)
        if callable(reassert):
            reassert()
        schedule_external_tick = (
            getattr(self.daemon, "_schedule_external_tick", None)
            if self.daemon is not None
            else None
        )
        if callable(schedule_external_tick):
            schedule_external_tick()

        return {"ok": True, "renumbered": renumbered}

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
        # A key do registro é canônica (12-hex minúsculo). Um handle sem MAC
        # estável (fallback por path) não normaliza — cai no valor cru, que é
        # exatamente a key VOLÁTIL que o registro usa para ele.
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
            # Mesma repintura do renumber: o DualSense reafirma o output já
            # com o número novo; os externos são repintados pelo tick lento,
            # adiantado aqui para não esperar o intervalo cheio do poll.
            reassert = getattr(self.controller, "reassert_resolved_outputs", None)
            if callable(reassert):
                reassert()
            schedule_external_tick = (
                getattr(self.daemon, "_schedule_external_tick", None)
                if self.daemon is not None
                else None
            )
            if callable(schedule_external_tick):
                schedule_external_tick()

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

        A regra, em uma frase: **permutar os lugares que os PRESENTES já
        ocupam**, pondo o alvo na posição pedida.

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
           ``slot_for``, a ordem em que eles exibem 1..N;
        2. tira o alvo dessa lista e o reinsere no índice ``numero - 1``;
        3. redistribui os MESMOS lugares, na ordem crescente, para a lista
           reordenada;
        4. entrega a cada registro só a fatia de keys que é dele
           (``compact``, que persiste sob o ``CONTROLLERS_FILE_LOCK``).

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

            presentes: list[tuple[int, int, str, Any]] = []
            for ordem_kind, registry in enumerate(
                (identity_registry, external_registry)
            ):
                if registry is None:
                    continue
                conectados = IpcHandlersMixin._connected_keys(registry)
                presentes.extend(
                    (lugar, ordem_kind, key, registry)
                    for key, lugar in registry.snapshot().items()
                    if key in conectados
                )
            presentes.sort(key=lambda e: (e[0], e[1], e[2]))

            indice_atual = next(
                (pos for pos, e in enumerate(presentes) if e[2] == alvo), None
            )
            if indice_atual is None:
                raise _NumeroAlvoAusenteError()
            if numero > len(presentes):
                raise _NumeroForaDaMesaError(len(presentes))

            lugares = [e[0] for e in presentes]
            nova_ordem = list(presentes)
            movido = nova_ordem.pop(indice_atual)
            nova_ordem.insert(numero - 1, movido)

            mudou: dict[str, int] = {}
            por_registro: dict[int, dict[str, int]] = {}
            for pos, (lugar_atual, ordem_kind, key, registry) in enumerate(
                nova_ordem
            ):
                novo_lugar = lugares[pos]
                if novo_lugar != lugar_atual:
                    mudou[key] = novo_lugar
                por_registro.setdefault(ordem_kind, {})[key] = novo_lugar
                del registry  # a fatia é escolhida pelo índice, não pelo objeto

            if identity_registry is not None and por_registro.get(0):
                identity_registry.compact(por_registro[0])
            if external_registry is not None and por_registro.get(1):
                external_registry.compact(por_registro[1])

            return mudou

    @staticmethod
    def _connected_keys(registry: Any) -> set[str]:
        """Keys CONECTADAS de um registro de identidade (R-15), com fallback.

        Registro sem ``snapshot_connected`` (dublê de teste, versão anterior)
        devolve o ``snapshot()`` inteiro: todo mundo conta como conectado e o
        plano degrada para a compactação global do HEAD — nunca levanta e
        nunca perde controle do plano.
        """
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
        """Corpo BLOQUEANTE de `identity.renumber` — só via `asyncio.to_thread`.

        Extraído para nunca mais rodar direto no event loop (fix MEDIUM
        cross-cutting 2026-07-20, ver docstring do chamador). Devolve
        ``{}`` quando não há controle nenhum registrado (no-op seguro,
        idêntico ao HEAD). `authority_check` (F3): re-checagem da autoridade
        de exibição APÓS adquirir os locks — se um jogo abriu enquanto a
        thread esperava (inclusive a thread-zumbi de um `lock_timeout` já
        respondido), aborta com `_RenumberAuthorityChangedError` em vez de
        repintar LEDs no meio da partida.

        R-15 (auditoria 23/07), duas correções no PLANO da compactação:

        1. **Conectado primeiro.** Compactar o mapa inteiro incluía RESERVA
           de controle offline: com o 8BitDo desligado segurando um slot
           baixo, o "Renumerar agora" era um no-op — os conectados nunca
           desciam para a faixa 1..N porque a reserva já ocupava. Agora os
           CONECTADOS (``snapshot_connected``) descem para 1..N na ordem
           relativa atual e as reservas ausentes vão para N+1..M no MESMO
           mapping. A reserva não é dropada (a promessa D2 do sprint
           cores-e-led continua: replug recupera o número), só perde a fila.
           Registro sem ``snapshot_connected`` (dublê antigo) degrada para o
           comportamento anterior — todo mundo tratado como conectado.
        2. **Só o que mudou volta em ``renumbered``.** O retorno era o plano
           INTEIRO, então uma numeração já compacta respondia "4 controle(s)
           renumerado(s)" à GUI (que conta as chaves) — sucesso ruidoso de um
           no-op. O ``compact`` de cada registro já ignora chave sem mudança;
           aqui o relatório passa a dizer a mesma verdade, e o chamador pula
           o repaint/reassert quando nada mudou.

        NUM-01 (25/07) manteve as duas e trocou o que os inteiros SIGNIFICAM:
        o plano ordena e reescreve LUGARES NA FILA, não números de jogador.
        A consequência é que o item 1 deixou de ter efeito colateral. Antes,
        empurrar o ausente para N+1..M era rebaixá-lo de verdade — ele
        exibiria aquele número no replug, e era assim que "o gesto que
        conserta um controle estraga o outro" (o arquivo dela invertido
        dentro da mesma sessão). Agora empurrar o ausente só o põe atrás na
        fila: quem está na mesa conta 1..N sem ele, e quando ele voltar o
        número dele sai da contagem de novo. O algoritmo é o MESMO; o estrago
        morreu com a separação entre identidade e posição.
        """
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
                    # R-15: a 1ª chave da ordenação é "está offline?" — False
                    # ordena antes, então os conectados ocupam 1..N e as
                    # reservas seguem em N+1..M preservando a ordem relativa.
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
                    # R-15: relatório só do que MUDOU (a GUI conta as chaves
                    # para dizer quantos controles renumerou). NUM-01: o valor
                    # é o LUGAR NA FILA — para quem está na mesa ele coincide
                    # com o número exibido (os presentes ocupam 1..N), e para
                    # quem está fora é a posição na espera.
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

    # --- estado ----------------------------------------------------------

    async def _handle_daemon_status(self, params: dict[str, Any]) -> dict[str, Any]:
        snap = self.store.snapshot()
        controller = snap.controller
        return {
            "connected": bool(controller and controller.connected),
            "transport": controller.transport if controller else None,
            "active_profile": snap.active_profile,
            "battery_pct": controller.battery_pct if controller else None,
            # FEAT-DAEMON-PAUSE-RESUME-01: distingue pausado (vivo, sem input) de parado.
            "paused": bool(self.daemon is not None and self.daemon.is_paused()),
            # FEAT-AUTOSWITCH-LOCK-01: a GUI reflete o cadeado da troca de perfil.
            "autoswitch_locked": bool(self.store.autoswitch_locked),
            "native_mode": bool(
                self.daemon is not None and self.daemon.is_native_mode()
            ),
            # FEAT-EMULATION-GAMEMODE-LONGPRESS-01: modo jogo (emulacao suprimida).
            "emulation_suppressed": bool(
                self.daemon is not None
                and getattr(self.daemon, "_emulation_suppressed", False)
            ),
            # EMULACAO-NO-JOGO-01: estado do teclado emulado — o interruptor que
            # ele nunca teve, mais o MOTIVO de estar calado. Mesmo bloco do
            # `state_full` (mesma razão do `window_detect_*`: duas respostas que
            # divergem são duas verdades).
            "keyboard_emulation": self._keyboard_emulation_payload(),
            # JANELA-CEGA-01: o `daemon.status` não expunha campo
            # `window_detect_*` NENHUM — quem olhava o status não tinha como
            # saber que o perfil-por-jogo estava cego. Mesmo bloco do
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
                         `"modo_jogo"` (a supressão que ela chama de modo jogo),
                         `"vpad_suspenso_pelo_steam_input"` (o jogo assumiu a
                         ENTRADA — o defeito medido em 29/07; a saída continua
                         do Hefesto, MEDIDO em 06/08) ou `null` quando emite.

        A quinta chave é de outra natureza e entrou em 10/08/2026
        (TECLADO-QUE-NAO-DIGITA-01):

        - `osk_disponivel` -- há teclado na tela instalado na MÁQUINA. É o que
                         decide se o L3 (`__OPEN_OSK__`, o binding de fábrica)
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
        suprimido = bool(getattr(daemon, "_emulation_suppressed", False))
        motivo_jogo: str | None = None
        predicado = getattr(daemon, "_jogo_no_controle_do_desktop", None)
        if callable(predicado):
            with contextlib.suppress(Exception):
                bruto = predicado()
                motivo_jogo = bruto if isinstance(bruto, str) else None
        bloqueio: str | None
        if not enabled:
            bloqueio = "desligada"
        elif not device_ativo:
            bloqueio = "sem_device"
        elif suprimido:
            bloqueio = "modo_jogo"
        else:
            bloqueio = motivo_jogo
        # Pergunta ao `_OSKController` do daemon quando ele existe (o cache dele
        # já está quente) e cai na sonda de módulo quando não existe — que é o
        # caso enquanto a emulação de teclado está desligada, justamente quando
        # a janela mais precisa saber se ligar valeria alguma coisa. As duas
        # respostas têm o mesmo TTL e a mesma ordem de candidatos.
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

    def _steam_input_payload(self) -> dict[str, bool]:
        """O PAR "exceção ativa" + "vpad suspenso" (JOGO-01, Entrega 2).

        A docstring de `subsystems/gamepad.steam_input_vpad_suspenso` já descrevia
        este payload como pendência: quem for dizer à usuária por que a emulação
        aparece desligada com o jogo aberto precisa dos DOIS valores, porque eles
        distinguem os dois desfechos possíveis do opt-in —

          - `excecao_ativa=True` + `vpad_suspenso=True`  → o jogo da allowlist
            está rodando com a ENTRADA entregue a ele (é o regime em que o R1
            dela emitia Alt+Tab, e agora o que cala o desktop). Só a entrada:
            cor, gatilhos e vibração seguem sendo do Hefesto — MEDIDO em 06/08
            (`CONTROLE-SONY-MEDIDO-01`, *A INVERSÃO*), e quem escrever a frase
            da aba a partir daqui não pode prometer o contrário;
          - `excecao_ativa=True` + `vpad_suspenso=False` → o jogo da allowlist
            está rodando com o vpad DE PÉ porque a suspensão não pôde ser armada
            (ver `suspend_vpads_for_steam_input`).

        Publicado no `state_full` porque `mode_of_state` (app/actions) hoje chama
        de "Controlar o PC" exatamente o primeiro caso — `stop_gamepad_emulation`
        zera `config.gamepad_emulation_enabled` mesmo com `persist=False` — e
        deixa CINZA o único botão que curava o problema dela. A correção mora na
        GUI (dono diferente); o dado sai daqui para ela não precisar adivinhar.
        """
        daemon = self.daemon
        return {
            "excecao_ativa": bool(getattr(daemon, "_steam_input_excecao", False)),
            "vpad_suspenso": bool(
                getattr(daemon, "_steam_input_vpad_suspenso", False)
            ),
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

    async def _handle_autoswitch_lock(self, params: dict[str, Any]) -> dict[str, Any]:
        """Congela/descongela a troca AUTOMÁTICA de perfil (FEAT-AUTOSWITCH-LOCK-01).

        Pedido da mantenedora (23/07): poder dizer "usa o que eu escolhi, não
        troca sozinho" — para qualquer jogo. É o
        oposto de aplicar o perfil do jogo por foco de janela.

        `locked` opcional: ausente → toggle. Persiste em disco (sobrevive a
        reboot) e vale no tick seguinte do autoswitch — não mexe em gamepad/
        co-op/rumble, só na DECISÃO de perfil.
        """
        from hefesto_dualsense4unix.utils.session import save_autoswitch_locked

        pedido = params.get("locked")
        novo = not self.store.autoswitch_locked if pedido is None else bool(pedido)
        self.store.set_autoswitch_locked(novo)
        save_autoswitch_locked(novo)
        logger.info("autoswitch_lock_set", locked=novo)
        return {"status": "ok", "autoswitch_locked": novo}

    async def _handle_native_mode_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Liga/desliga o Modo Nativo — "release total" do controle (FEAT-NATIVE-MODE-01).

        `enabled` opcional: ausente → toggle. Solta o controle para o jogo
        (gatilhos Off, rumble passthrough, emulação off, autoswitch/hotkey
        gateados, pausado). Desligar restaura o último perfil.
        """
        if self.daemon is None:
            raise RuntimeError("daemon indisponível")
        raw = params.get("enabled")
        if raw is None:
            enabled = not self.daemon.is_native_mode()
        elif isinstance(raw, bool):
            enabled = raw
        else:
            raise ValueError("native.mode.set exige 'enabled' boolean ou omitido")
        new_state = self.daemon.set_native_mode(enabled, origin=origem_do_pedido(params))
        return {"status": "ok", "native_mode": bool(new_state)}

    async def _handle_daemon_state_full(self, params: dict[str, Any]) -> dict[str, Any]:
        """Estado completo pra GUI consumir a 20Hz.

        FEAT-CLI-PARITY-01: inclui bloco `mouse_emulation` com enabled/speed/
        scroll_speed para o subcomando `hefesto-dualsense4unix mouse status` consultar via IPC.
        Quando `self.daemon` for None (contextos de teste ou modos legados),
        o bloco é omitido e o cliente trata como "estado indisponível".

        CLUSTER-IPC-STATE-PROFILE-01 (Bug A): preferimos `daemon._last_state`
        (último tick do poll loop) sobre `store.snapshot().controller` quando
        ambos disponíveis. Buttons saem de `state.buttons_pressed` (já
        consolidado em `backend_pydualsense.read_state` — armadilha A-09:
        nada de novos snapshots evdev no async loop). Fallback gracioso:
        se daemon ausente (testes legados), cai em store.controller_state;
        se ambos None, devolve neutro como antes.
        """
        snap = self.store.snapshot()
        # Bug A: prioriza estado LIVE do poll loop (daemon._last_state) sobre
        # snapshot do store. Em testes legados sem daemon injetado, cai no
        # store. Em ambos cenários, evita ler `_evdev.snapshot()` aqui (já
        # consolidado em buttons_pressed pelo poll loop).
        state = (
            getattr(self.daemon, "_last_state", None) if self.daemon else None
        ) or snap.controller

        # Bug A — diagnóstico de "state estagnado" quando hardware está
        # conectado mas todos os campos chegam neutros (sticks=128, gatilhos=0,
        # buttons vazio). Indica evdev_reader não inicializado ou backend HID
        # estagnado. Threshold por chamadas IPC (não por ticks).
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
            # FEAT-DAEMON-PAUSE-RESUME-01: applet/GUI distinguem pausado de parado.
            "paused": bool(self.daemon is not None and self.daemon.is_paused()),
            # FEAT-AUTOSWITCH-LOCK-01: applet/GUI refletem o cadeado da troca de perfil.
            "autoswitch_locked": bool(self.store.autoswitch_locked),
            "native_mode": bool(
                self.daemon is not None and self.daemon.is_native_mode()
            ),
            # FEAT-PROFILE-MODE-01: origem do nativo ("manual"|"profile"|None) e
            # qual modo o perfil ativo ligou — a GUI mostra "Nativo (pelo
            # perfil)" e o comutador da aba Início reflete a origem.
            # `_as_str_or_none` blinda contra doubles de teste (MagicMock não é
            # serializável em JSON).
            "native_mode_origin": _as_str_or_none(
                getattr(self.store, "native_mode_origin", None)
            ),
            "mode_from_profile": _as_str_or_none(
                getattr(self.daemon, "_mode_from_profile", None)
                if self.daemon is not None
                else None
            ),
            # BUG-COOP-GRAB-SILENT-FAIL-01: estado observável do EVIOCGRAB do
            # primário ("off"|"pending"|"held"|"failed") — "failed" com gamepad
            # ligado = risco de input dobrado; a GUI/doctor avisam.
            "primary_grab_state": _as_str_or_none(
                getattr(
                    getattr(self.controller, "_evdev", None), "grab_state", None
                )
            ),
            # FEAT-EMULATION-GAMEMODE-LONGPRESS-01: modo jogo (emulacao suprimida).
            "emulation_suppressed": bool(
                self.daemon is not None
                and getattr(self.daemon, "_emulation_suppressed", False)
            ),
            # EMULACAO-NO-JOGO-01: interruptor do teclado emulado + motivo de ele
            # estar calado. Ver `_keyboard_emulation_payload` (mesmo bloco do
            # `daemon.status`).
            "keyboard_emulation": self._keyboard_emulation_payload(),
            # JOGO-01 (Entrega 2, pendência da docstring de
            # `steam_input_vpad_suspenso`): o par que explica "a emulação parece
            # desligada com o jogo aberto". Ver `_steam_input_payload`.
            "steam_input": self._steam_input_payload(),
            # FEAT-WINDOW-DETECT-DIAG-01 + JANELA-CEGA-01: saúde do detector de
            # janela do autoswitch (backend, sticky, leitura CRUA, idade da
            # última leitura útil e motivo da cegueira) — ver
            # `_window_detect_payload`.
            **self._window_detect_payload(),
        }
        # NUMA-05: sinal de autoridade de exibição (NUMA-01) para GUI/doctor —
        # a mesma leitura que o `defend_display`/merge-gate do backend usam,
        # SÓ exposição (nunca decide nada aqui).
        result["game_signal"] = self._game_signal_snapshot()

        # ABA-DO-JOGO-01 (10/08/2026): há jogo da Steam aberto AGORA, e qual.
        # Vem do store (sonda de 0,5 Hz do poll loop), NUNCA de um `pgrep` daqui
        # — este handler roda a 10 Hz e um subprocesso por chamada seria o poller
        # cego que esta casa já pagou uma vez.
        #
        # As duas chaves são o TRI-ESTADO inteiro, e viajam juntas de propósito
        # (ver `StateStore.set_steam_jogo_appid`): `lido=false` é "o daemon ainda
        # não perguntou", e é diferente de `lido=true, appid=null`, que é "não há
        # jogo". Quem consome — a visibilidade da aba "No jogo" — faz coisas
        # opostas nos dois casos.
        result["jogo_steam"] = self._jogo_steam_payload()

        # FEAT-DSX-MULTI-CONTROLLER-01: lista de controles conectados (uma entrada
        # por controle físico, com transporte e qual é o primário) para a GUI, o
        # tray e o applet mostrarem "N controles" sem uma chamada IPC separada.
        describe = getattr(self.controller, "describe_controllers", None)
        if callable(describe):
            controllers = describe()
            result["controllers"] = controllers
            # LEIGO-01b: o número do jogador de cada controle vem do daemon —
            # a GUI o rotulava por POSIÇÃO na lista (idx+1), que mente quando o
            # co-op está desligado (todos são o mesmo jogador) e quando um
            # índice é reusado depois de um jogador sair. `None` = não é jogador
            # agora; a UI omite o número em vez de inventar um.
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
            # STATUS-01 + COR-05 + BT-03: enriquecimento POR CONTROLE físico —
            # slot de sessão, cor da lightbar (com dono da escrita), inputs ao
            # vivo e backend/motivo do vpad por jogador. Mora AQUI (no handler,
            # a 10 Hz com cache TTL), NUNCA em `describe_controllers()` — que
            # roda no caminho quente do FF do jogo e não pode fazer I/O de
            # arquivo. O suppress é a última linha de defesa da serialização
            # (daemon/controller dublados em teste); cada seção interna já é
            # defensiva por conta própria.
            if isinstance(controllers, list):
                with contextlib.suppress(Exception):
                    self._enrich_controllers_per_controller(
                        [c for c in controllers if isinstance(c, dict)], state
                    )

        # DEDUP-06 (achado NOVO da revisão): físico em BT + Modo Nativo é
        # estruturalmente frágil — o SDL pode não enxergar o DualSense BT nem
        # SEM launch option (o backend evdev deferencia ao HIDAPI por VID/PID e
        # o HIDAPI não lê o hidraw BT). Fora do alcance do wrapper; a GUI e o
        # doctor avisam a partir DESTA flag.
        #
        # MESA-CHEIA-11/E1 (14/08/2026) — por que este bloco MUDOU DE LUGAR:
        # ele olhava só `result["transport"]`, que é o do PRIMÁRIO, e por isso
        # calava com o Controle 1 no cabo e os outros três no rádio (falso
        # negativo). Agora ele responde POR CONTROLE, e para isso precisa da
        # lista `controllers` já montada e já enriquecida com o `player_slot` —
        # daí ter descido para depois do bloco acima.
        entradas_de_controle = result.get("controllers")
        frageis = controles_bt_frageis(
            entradas_de_controle, native_mode=result["native_mode"]
        )
        # A mesa é conhecida quando a lista existe e traz alguém conectado.
        # Backend sem `describe_controllers` (fakes, MagicMock) não sabe QUEM
        # está na mesa: aí a flag antiga — o primário — continua valendo, e a
        # lista sai VAZIA de propósito, para a janela cair no texto genérico em
        # vez de nomear um controle que ela não sabe qual é.
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
        # conectado.".
        result["controles_sem_driver"] = self._controles_sem_driver_payload()

        # FEAT-DSX-CONTROLLER-SELECTOR-01: índice do controle-alvo de output
        # (None = TODOS / broadcast). getattr defensivo: backends sem o método
        # (FakeController) ou controller MagicMock em teste → None.
        get_target = getattr(self.controller, "get_output_target_index", None)
        target_index: int | None = None
        if callable(get_target):
            raw_target = get_target()
            if isinstance(raw_target, int) and not isinstance(raw_target, bool):
                target_index = raw_target
        result["output_target_index"] = target_index

        # Paridade CLI-GUI: expõe estado da emulação de mouse se o daemon
        # dono da IPC tiver config acessível (FEAT-CLI-PARITY-01).
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is not None:
            result["mouse_emulation"] = {
                "enabled": bool(getattr(daemon_cfg, "mouse_emulation_enabled", False)),
                "speed": int(getattr(daemon_cfg, "mouse_speed", 6)),
                "scroll_speed": int(getattr(daemon_cfg, "mouse_scroll_speed", 1)),
            }
            # FEAT-DSX-GAMEPAD-FLAVOR-01: estado do gamepad virtual p/ GUI/applet.
            result["gamepad_emulation"] = {
                "enabled": bool(getattr(daemon_cfg, "gamepad_emulation_enabled", False)),
                "flavor": str(getattr(daemon_cfg, "gamepad_flavor", "dualsense")),
            }
            # UHID-04: backend do vpad primário VIVO ("uhid" = DualSense Edge real
            # 0x0df2, "uinput" = Xbox/fallback). O botão de Launch Options escolhe a
            # variante por aqui: só o "uhid" tem PID próprio e desduplica por
            # IGNORE_DEVICES; no flavor dualsense com backend "uinput" (uhid não
            # subiu) não há launch option que desduplique — a GUI avisa em vez de
            # prometer. ff_supported/plays saem no bloco rumble_ff abaixo.
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
                # VPAD-05 — degradação NUNCA silenciosa: flavor dualsense em
                # backend uinput = vpad sem hidraw (vibração in-game morta) e
                # sem launch option segura. O dado honesto sai AQUI; o banner
                # da GUI (fase 2) e o doctor só consomem. `degraded_motivo` é
                # o que a factory pendurou no vpad ("uhid_indisponivel",
                # "uhid_start_falhou", "uhid_bind_falhou",
                # "uhid_vetado_pelo_chamador").
                with contextlib.suppress(Exception):
                    degraded = bool(
                        getattr(gp_dev, "flavor", None) == "dualsense"
                        and getattr(gp_dev, "backend", None) == "uinput"
                    )
                    result["gamepad_emulation"]["degraded"] = degraded
                    if degraded:
                        motivo = getattr(gp_dev, "fallback_motivo", None)
                        if isinstance(motivo, str) and motivo:
                            result["gamepad_emulation"]["degraded_motivo"] = motivo
            # DEDUP-06 — guard anti-veneno: `dedup_ok` agregado POR JOGADOR
            # (P1 + todos os vpads do co-op). `degraded` acima fala SÓ pelo
            # primário; um jogador do co-op em uinput com o IGNORE congelado
            # na env do jogo é AQUELE jogador com zero controle — o guard é
            # quem torna isso visível (GUI/doctor consomem daqui). O log de
            # transição (`dedup_broken`) sai na materialização do launch_env,
            # nunca aqui (o state_full roda a 20 Hz — seria flood).
            with contextlib.suppress(Exception):
                from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
                    dedup_status,
                )

                dedup_ok, motivos = dedup_status(self.daemon)
                result["gamepad_emulation"]["dedup_ok"] = dedup_ok
                if motivos:
                    result["gamepad_emulation"]["dedup_motivo"] = ", ".join(motivos)
            # GUI-05 item 3 — honestidade do dedup: `wrapper_used` responde se
            # o jogo em foco (janela `steam_app_N`) PASSOU pelo hefesto-launch
            # (marker `last_run` gravado pelo wrapper, janela de ~120s até a
            # 1ª detecção do appid). true = passou; false = jogo aberto SEM o
            # wrapper (as envs de dedup nunca chegaram ao processo); null =
            # nenhum jogo detectado. O FATO 0 do estudo 2026-07-18: o
            # `dedup_ok` sozinho era falso-tranquilizante — daqui em diante um
            # jogo sem wrapper também derruba o `dedup_ok` (com motivo),
            # exceto em Modo Nativo/emulação off (não há env que importe).
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
            # PERFIL-MUDO-01 (10/08/2026): o perfil DAQUELE jogo que não entrou.
            # O daemon já sabia e só contava ao journal — quatro linhas de
            # `profile_select_catch_all_sem_autoridade_em_jogo` enquanto ela
            # jogava o Pragmata com o controle duplicado, e a janela muda. Aqui
            # o fato vira estado, e a janela passa a poder dizer.
            result["perfil_do_jogo_que_nao_entrou"] = self._perfil_que_nao_entrou()
            # FEAT-DSX-COOP-LOCAL-01: estado do co-op local (toggle + nº de
            # jogadores ativos) p/ GUI/applet/CLI.
            coop_mgr = getattr(self.daemon, "_coop_manager", None)
            players_raw = coop_mgr.player_count() if coop_mgr is not None else 1
            result["coop"] = {
                "enabled": bool(getattr(daemon_cfg, "coop_enabled", False)),
                # coerção defensiva: em testes o daemon pode ser MagicMock e
                # player_count() devolver um mock não-serializável.
                "players": players_raw if isinstance(players_raw, int) else 1,
            }
            # QUEM-É-QUEM-01 (15/08/2026) — o número vira TABELA.
            # `players: 4` responde "quantos"; nunca respondeu "quem". Com os
            # quatro controles dela na mesa, "o vpad do jogador 2 é alimentado
            # por qual controle?" só se respondia apertando botão em cada um,
            # quatro vezes, à mão — e o daemon SABIA a resposta o tempo todo (é
            # ele que cria cada vpad a partir de um físico). A lista sai de
            # `CoopManager.mesa`, que documenta o contrato de cada campo, a
            # decisão de privacidade do MAC e a E3 (`nome_divergente`).
            #
            # `players` FICA, e não é redundância: ele é lido pela CLI, pelo
            # applet e por `status_actions` desde a FEAT-DSX-COOP-LOCAL-01, e
            # continua sendo a contagem barata. O que muda é que agora existe
            # a lista ao lado — a chave nova nunca substitui a velha.
            #
            # Lista SEMPRE presente (vazia no pior caso): shape estável para
            # GUI/CLI/applet, que assim nunca precisam distinguir "daemon
            # antigo" de "mesa vazia" — e uma lista vazia já diz a verdade.
            result["coop"]["mesa"] = []
            if coop_mgr is not None:
                with contextlib.suppress(Exception):
                    mesa = coop_mgr.mesa()
                    if isinstance(mesa, list):
                        result["coop"]["mesa"] = [
                            item for item in mesa if isinstance(item, dict)
                        ]
            # EXT-COUNT-01 (25/07): quantos controles EXTERNOS (Nintendo Pro,
            # 8BitDo…) o daemon numerou mas NÃO adota. `coop.players` conta só
            # quem tem vpad do hefesto — com 2 DualSense e 2 Pro vivos ele diz
            # "2", e quem lê de fora conclui que só há 2 controles. Os
            # externos são read-only POR DECISÃO DE PRODUTO (numerar e acender
            # o LED certo ≠ adotar o controle), então o número certo não é
            # inflar `players`: é dizer os dois. Leitura de um `set` em
            # memória mantido pelo tick lento — ZERO enumeração de /dev/input
            # neste caminho (o state_full roda a 10 Hz).
            registro_ext = getattr(self.daemon, "external_registry", None)
            conectados = getattr(registro_ext, "snapshot_connected", None)
            if callable(conectados):
                with contextlib.suppress(Exception):
                    vistos = conectados()
                    if isinstance(vistos, (set, frozenset)):
                        result["coop"]["externals"] = len(vistos)
            # CONTAGEM-E-COOP-01 (29/07): o co-op era derrubado EM SILÊNCIO.
            # Quando um jogo da allowlist de Steam Input entra em sessão,
            # `suspend_vpads_for_steam_input` chama `CoopManager.disable()` e
            # dois ou três jogadores desaparecem sem uma palavra — `players`
            # volta a 1 no tique seguinte e a janela não tinha como distinguir
            # "ela desligou o co-op" de "o jogo derrubou o co-op".
            #
            # Duas chaves porque são duas perguntas: `derrubado_por_steam_input`
            # é o gatilho do aviso; `secundarios_derrubados` é QUANTOS jogadores
            # extras caíram (P2+; o P1 não é jogador do co-op e a queda dele já
            # tem observável próprio em `steam_input.vpad_suspenso`). Vale
            # exatamente enquanto a suspensão vale — as duas saídas dela zeram o
            # contador (ver `subsystems/gamepad.steam_input_coop_derrubados`).
            #
            # Fora do bloco `steam_input` de propósito: aquele payload é
            # travado por igualdade exata em teste de outra frente, e o fato é
            # do co-op — o lugar dele é aqui, ao lado de `players`.
            derrubados = getattr(self.daemon, "_steam_input_coop_derrubados", 0)
            if not isinstance(derrubados, int) or isinstance(derrubados, bool):
                # Blindagem de serialização (mesma do `players` acima): daemon
                # dublado por MagicMock devolveria um mock não-serializável.
                derrubados = 0
            result["coop"]["derrubado_por_steam_input"] = derrubados > 0
            result["coop"]["secundarios_derrubados"] = derrubados
            # FEAT-RUMBLE-POLICY-01: expõe política e mult efetivo ao estado.
            # L1: a observabilidade vem da ORIGEM VIVA — `daemon._last_auto_mult`,
            # o multiplicador auto mais recente, atualizado pela política que de
            # fato roda (`reassert_rumble` no poll loop / `apply_rumble_policy`
            # no rumble.set). O antigo `_rumble_engine` NÃO é instanciado no
            # daemon real (não existe esse atributo), então a leitura caía sempre
            # no fallback 1.0 — código morto. O RumbleEngine segue em uso por
            # testes/legado; só deixou de ser a fonte aqui.
            rumble_mult_applied = float(getattr(self.daemon, "_last_auto_mult", 1.0))
            result["rumble_policy"] = str(getattr(daemon_cfg, "rumble_policy", "balanceado"))
            result["rumble_policy_custom_mult"] = float(
                getattr(daemon_cfg, "rumble_policy_custom_mult", 0.7)
            )
            result["rumble_mult_applied"] = rumble_mult_applied

            # SPRINT-GAME-RUMBLE-01: diagnóstico de rumble in-game + estado do
            # rumble. `plays` = nº de "play" de FF que o JOGO pediu nos vpads
            # (P1 + co-op) desde a criação. Em 0 durante o jogo = o jogo NÃO
            # enxerga o vpad (ex.: máscara DualSense atraindo o hidraw do
            # físico). `passthrough` (rumble_active is None) distingue "jogo
            # controla a vibração" de "fixo (teste pela GUI)" — a GUI não tinha
            # como saber em qual estado estava.
            # REPLICA-03: além do agregado (compat), expõe contadores POR VPAD
            # (`per_vpad`) — o agregado escondia QUAL vpad recebeu o quê
            # (telemetria cega do estudo 2026-07-18). `player` é o número do
            # JOGADOR dono deste vpad — ver o bloco MESA-CHEIA-12 logo abaixo.
            # GYRO-03: cada vpad viaja com o SEU espelho de motion (o
            # `PhysicalReportReader` do P1 mora em `daemon._motion_reader`;
            # o de cada jogador do co-op, em `player.motion_reader`) — é dele
            # que sai o `motion_hz` (taxa REAL de entrega ao /dev/uhid).
            vpads: list[tuple[int, Any, Any]] = []
            coop_mgr = getattr(self.daemon, "_coop_manager", None)
            # MESA-CHEIA-12 (15/08/2026): o `player` de cada bloco é o número do
            # CONTROLE que alimenta este vpad, e tem de sair da MESMA função que
            # produziu `controllers[].player` — é por esse inteiro que a GUI casa
            # card↔vpad (`controller_card._bloco_do_vpad`, dono único do
            # casamento). Enquanto o número publicado era o `player_index` cru,
            # os dois lados coincidiam por construção; agora que ele é a fila de
            # chegada, ler `player_index` aqui cruzaria os fios — o card de um
            # controle mostraria a telemetria do vpad de OUTRO. As condições
            # espelham `resolve_player_numbers`: sem co-op existe um vpad só e
            # ele é o jogador 1.
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
            # QUEM ESCREVEU-01: agregados dos dois silêncios que a tela lia
            # como "o jogo não pediu nada".
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
                    # RUMBLE-QUE-NAO-SE-SENTE-01: agregados irmãos do `plays`,
                    # somados na MESMA varredura (a tela lê o total; o
                    # `per_vpad` é quem responde "qual jogador").
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
                    # coerção defensiva: em testes o vpad pode ser MagicMock e
                    # `backend` devolver um mock não-serializável.
                    backend = getattr(vp, "backend", None)
                    # GYRO-03: `motion_streaming` = o vpad está no modo "o
                    # reader é o relógio" (gyro/accel/touch espelhados do
                    # físico); `motion_hz` = taxa de entrega do reader (EMA,
                    # pós-throttle) — 0.0 sem reader (uinput/sem físico) ou
                    # com o fluxo parado. Tipagem estrita nas duas leituras:
                    # um MagicMock nunca vira True/taxa fantasma no payload.
                    streaming = getattr(vp, "motion_streaming", False)
                    hz_raw = getattr(motion_reader, "emit_hz", 0.0)
                    # QUEM-É-QUEM-01 / E2: o bloco passa a carregar a IDENTIDADE
                    # do nó — `vpad_uniq` (o `02:fe:…` que sai no `HID_UNIQ` do
                    # sysfs), `vpad_nome` e `vpad_indice`. O objeto sempre soube
                    # os três e nunca os publicava, e por isso `player` era a
                    # única ponte entre esta lista e `controllers[]`: um inteiro
                    # que não diz em que dispositivo do kernel olhar. Vem da
                    # MESMA função que monta o `coop.mesa` — duas descrições do
                    # mesmo vpad se afastariam na primeira mudança. O
                    # `vpad_backend` dela é descartado aqui: `backend`, logo
                    # abaixo, já é esse mesmo fato com o nome que esta lista
                    # sempre usou.
                    identidade = identidade_do_vpad(vp)
                    per_vpad.append(
                        {
                            "player": player_num,
                            "vpad_uniq": identidade["vpad_uniq"],
                            "vpad_nome": identidade["vpad_nome"],
                            "vpad_indice": identidade["vpad_indice"],
                            "backend": backend if isinstance(backend, str) else None,
                            "ff_play_count": int(getattr(vp, "ff_play_count", 0) or 0),
                            # RUMBLE-QUE-NAO-SE-SENTE-01: `ff_play_count` sobe
                            # na PARADA também, então sozinho ele não separa
                            # "pediu e sumiu" de "pediu zero". Estes quatro
                            # separam — ver `integrations/uhid_gamepad`.
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
                            # QUEM ESCREVEU-01: os três buracos que faziam
                            # "ninguém pediu nada" e "chegou e nós descartamos
                            # na porta" saírem com o MESMO painel zerado.
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
                            # SENSOR-VIVO-01/E4: quantas vezes o clique do
                            # touchpad do físico saiu no report 0x01 do vpad —
                            # é o número que distingue "o dedo chega ao jogo"
                            # (que já acontecia) de "o clique chega ao jogo".
                            # Contador do vpad, e não do reader: o que importa
                            # é o que foi ESCRITO no /dev/uhid, não o que foi
                            # lido do físico.
                            "touchpad_clicks": int(
                                getattr(vp, "touchpad_click_count", 0) or 0
                            ),
                            # ORFAOS-QUE-VOLTAM-01 (09/08/2026) — o ESTADO ao
                            # lado da contagem. `touchpad_clicks` conta bordas;
                            # com o dedo APERTADO ele para de subir, e a tela,
                            # que decide por idade do carimbo, dizia "parou"
                            # com o botão ainda pressionado no jogo. A property
                            # `touchpad_click` existia desde a TOUCH-CLICK-01 e
                            # nunca tinha sido lida por ninguém.
                            "touchpad_pressionado": bool(
                                getattr(vp, "touchpad_click", False) is True
                            ),
                            # ORFAOS-QUE-VOLTAM-01: quantas JANELAS de motion o
                            # vpad de fato escreveu no /dev/uhid. Irmão do
                            # `motion_hz` e diferente dele: o Hz é a taxa do
                            # reader AGORA (morre em 1 s de silêncio), este é
                            # cumulativo e responde "já fluiu alguma vez?" —
                            # é ele que separa "o giroscópio nunca começou" de
                            # "o giroscópio parou", que a tela dizia igual.
                            "motion_forwards": _contador_do_vpad(
                                vp, "motion_forward_count"
                            ),
                            # JACK-QUE-NAO-LIGOU-01: o que o vpad DIZ AO JOGO
                            # sobre fone/microfone do controle (byte 53). Saía
                            # fixo em 0x00 desde sempre — o `forward_jack`
                            # existia desde 02/08 sem chamador e sem emissão.
                            "jack": _jack_do_vpad(vp),
                            "jack_forwards": _contador_do_vpad(
                                vp, "jack_forward_count"
                            ),
                            # BATERIA-QUE-NAO-CHEGOU-01: o que o vpad DIZ AO
                            # JOGO sobre a carga (byte 52). Diferente do
                            # `battery_pct` do controle FÍSICO que a aba Status
                            # já mostra: com o `forward_battery` órfão desde
                            # 15/07, o físico podia estar em 95% e o jogo lia
                            # "cheio e carregando" fixo — ou, antes disso, "5%
                            # descarregando" e alertava bateria fraca.
                            "bateria_no_jogo": _bateria_do_vpad(vp),
                            "battery_forwards": _contador_do_vpad(
                                vp, "battery_forward_count"
                            ),
                            # MOTOR-QUE-NAO-SE-VE-01: o par que foi AOS
                            # MOTORES, depois da política de intensidade. Todos
                            # os `ff_*` acima são o que o JOGO PEDIU; entre um
                            # e outro há uma multiplicação que a tela não via.
                            "rumble_no_fisico": _par_de_motores(
                                getattr(vp, "rumble_no_fisico", None)
                            ),
                            "rumble_no_fisico_ha_s": _idade_ou_none(
                                getattr(vp, "rumble_no_fisico_ha_s", None)
                            ),
                            # PAINEL-DA-VERDADE-01/E1 — o campo que faz a aba
                            # Status parar de confundir "já funcionou uma vez"
                            # com "está funcionando". Todos os contadores acima
                            # são CUMULATIVOS (zeram só no `start()`); este diz
                            # há quantos segundos cada categoria aconteceu pela
                            # última vez, e OMITE a categoria que nunca
                            # aconteceu — a tela diz frases diferentes para
                            # "parou" e para "nunca começou".
                            "visto_ha_s": _visto_ha_s(vp),
                            # PARIDADE-SONY-01 — o carimbo acima diz QUANDO o
                            # jogo pediu áudio; este diz O QUÊ. É a medição
                            # que a sprint exige antes de a E2 escrever uma
                            # linha de replicação, e sai do daemon pronta:
                            # basta ela jogar e olhar.
                            "audio_do_jogo_amostra": _audio_do_jogo_amostra(vp),
                        }
                    )
            result["rumble_ff"] = {
                "plays": ff_plays,
                # RUMBLE-QUE-NAO-SE-SENTE-01 — `plays` sozinho é ambíguo: ele
                # conta a PARADA junto com o pedido. `nao_nulos` é o número que
                # a aba Rumble usa para dizer QUAL das duas causas está viva.
                "nao_nulos": ff_nao_nulos,
                "descartados": ff_descartados,
                "v2": ff_v2,
                # QUEM ESCREVEU-01: `paradas` > 0 é PROVA de vibração viva
                # (ninguém manda parar o que nunca começou) e `estranhos` > 0 é
                # dado CHEGANDO e descartado na porta — o oposto exato da
                # conclusão "o jogo não enxergou o gamepad virtual".
                "paradas": ff_paradas,
                "estranhos": ff_estranhos,
                "last_weak": ff_last[0],
                "last_strong": ff_last[1],
                "vpads": len(vpads),
                "per_vpad": per_vpad,
            }
            # HOTKEY-EXPOSE-01 (25/07): a aba Emulação mostrava o buffer do
            # combo e o passthrough como TEXTO FIXO escrito uma vez na
            # construção do widget (`DEFAULT_BUFFER_MS` e "Não") — nunca o
            # valor em vigor. Nenhum dos dois subia no payload, então a GUI não
            # tinha como dizer a verdade nem se quisesse. A fonte é o
            # `HotkeyManager` VIVO (`daemon._hotkey_manager.config`), não os
            # defaults do módulo: `start_hotkey_manager` monta a config a
            # partir de `daemon.config` e é ela que governa o gesto.
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
            # MIC-EXPOSE-01: o botão de mic deixa de ser campo secreto do
            # lifecycle — a GUI/CLI leem o estado efetivo daqui.
            result["mic_button_toggles_system"] = bool(
                getattr(daemon_cfg, "mic_button_toggles_system", True)
            )
            # BT-MIC-REGISTRY-01: ponte de mic por BT — se o subsystem está de
            # pé AGORA (não só se a env var existe).
            result["bt_mic"] = {
                "enabled": bool(getattr(daemon_cfg, "bt_mic_enabled", False)),
                "running": getattr(self.daemon, "_bt_mic_subsystem", None) is not None,
            }
            rumble_active = getattr(daemon_cfg, "rumble_active", None)
            result["rumble_passthrough"] = rumble_active is None
            result["rumble_active"] = (
                [int(rumble_active[0]), int(rumble_active[1])]
                if rumble_active is not None
                else None
            )

        return result

    # --- STATUS-01 + COR-05 + BT-03: estado POR CONTROLE físico -----------

    def _enrich_controllers_per_controller(
        self, entries: list[dict[str, Any]], state: Any
    ) -> None:
        """Enriquece cada entrada de `controllers` com o estado POR CONTROLE.

        Campos novos (sempre presentes — shape estável para GUI/CLI/applet;
        os campos PRÉ-existentes não mudam):

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
          Modo Nativo: a matriz NÃO muda — o jogo escreve por hidraw (não
          toca a classe LED), então a fonte devolve a ÚLTIMA COR CONHECIDA; o
          campo global ``native_mode`` (já no payload) é o aviso da GUI ("o
          jogo é dono do LED") — nenhuma flag nova por controle.

        - ``lightbar_disputada`` (ESCRITOR-CRU-01): ``True`` quando outro
          processo — hoje só a Steam é reconhecida — segura o ``hidraw``
          DESTE controle. É o aviso de que ``lightbar_rgb`` acima é a cor
          PEDIDA e pode não ser a acesa: escrita crua por hidraw não atualiza
          a classe LED, e a madrugada de 16/08 mediu o mesmo ``[0 255 0]`` com
          a barra apagada e com ela verde. Sai da FOTO do sentinela do daemon
          (tique de 30 s) — este handler não toca ``/proc``.

          Contrato de cor (D8 — divergência fundamentada, decisão do
          orquestrador da onda): expõe-se UMA cor, a efetiva conhecida
          (pós-escala de brilho — o `_DesiredOutput.led` já é pós-escala; o
          manager pré-escala na borda). O par pré/pós-brilho do D8 original
          exigiria refactor do estado desejado fora do escopo; a legibilidade
          de cor escura (objetivo do D8) é da GUI via
          `utils/color_contrast.ensure_min_contrast`.
        - ``inputs``: ``{lx,ly,rx,ry,l2_raw,r2_raw,buttons}`` — mais as chaves
          OPCIONAIS ``gyro`` (``{x,y,z}`` em graus/s) e ``touchpad``
          (``{touching,x,y,width,height}``) quando o controle tem os nodes
          evdev correspondentes (S2, via `SensorHub`) — ou None. O
          PRIMÁRIO espelha o `state` do topo do payload (`daemon._last_state`
          — a MESMA fonte, nunca um snapshot evdev paralelo: armadilha A-09);
          secundários vêm de `CoopManager.live_snapshots()` (leitura
          não-destrutiva por MAC). Sem leitor → None (o card mostra "—",
          nunca um valor congelado fingindo vida).
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

        # ESCRITOR-CRU-01: o endereço com que se pergunta "quem mais segura
        # este controle?". Leitura de atributo do backend (`_pinned_path`) —
        # não re-enumera, não abre nada, não toca `/proc`: a FOTO de quem
        # segura é do sentinela do daemon, tirada no tique do reconnect_loop.
        nos_por_uniq: dict[str, str] = {}
        mapear = getattr(self.controller, "nos_hidraw_por_uniq", None)
        if callable(mapear):
            with contextlib.suppress(Exception):
                nos_por_uniq = dict(mapear() or {})

        snapshots = self._coop_live_snapshots()
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

            rgb, on, source = self._lightbar_for_uniq(
                uniq, node_by_uniq, written_by_uniq
            )
            entry["lightbar_rgb"] = list(rgb) if rgb is not None else None
            entry["lightbar_on"] = on
            entry["lightbar_source"] = source
            entry["lightbar_disputada"] = self._lightbar_disputada(uniq, nos_por_uniq)

            if entry.get("is_primary") and state is not None:
                entry["inputs"] = self._inputs_from_state(state)
            elif uniq is not None and uniq in snapshots:
                entry["inputs"] = self._inputs_from_snapshot(snapshots[uniq])
            else:
                entry["inputs"] = None
            self._merge_sensores(entry, uniq)
            self._merge_audio(entry, uniq)

            backend, motivo = (None, None)
            if entry.get("is_primary") and gp_dev is not None:
                backend, motivo = self._vpad_backend_motivo(gp_dev)
            elif uniq is not None and uniq in vpad_by_uniq:
                backend, motivo = vpad_by_uniq[uniq]
            entry["vpad_backend"] = backend
            entry["vpad_motivo"] = motivo

    def _merge_sensores(self, entry: dict[str, Any], uniq: str | None) -> None:
        """Acrescenta `gyro`/`touchpad` ao `inputs` deste controle (S2).

        Campos OPCIONAIS por contrato: quem não tem o node de motion (ou o do
        touchpad) sai sem a chave, e uma GUI antiga que não conheça nenhuma
        das duas continua lendo o `inputs` de sempre. O inverso também vale —
        é por isso que a GUI nova trata a ausência como "sem sensor" em vez de
        desenhar zero, que seria repouso mentiroso.

        Só há o que mesclar quando este controle TEM leitor de inputs: sem
        ele o card inteiro já mostra "—", e pendurar sensor num controle sem
        input seria a mesma mentira com outro nome. Controle sem MAC (`uniq`
        None) não tem como ser casado com um node e fica de fora.
        """
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
            # MIC-USB-01: a posse do mudo do firmware viaja DENTRO de `audio`
            # (é a mesma pergunta, vista do outro lado) e só quando o backend
            # sabe respondê-la — `getattr` defensivo pelo mesmo motivo dos
            # demais: FakeController e daemon antigo não têm o método.
            dono_fn = getattr(self.controller, "microphone_mute_for", None)
            if callable(dono_fn):
                desejado: Any = None
                with contextlib.suppress(Exception):
                    desejado = dono_fn(uniq)
                status["mic_mudo_desejado"] = (
                    bool(desejado) if isinstance(desejado, bool) else None
                )
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
        if isinstance(status, dict):
            bloco.update(status)
        entry["speaker"] = bloco
        # Espelha em `inputs` para a GUI achar a chave onde quer que ela leia
        # (o card lê ora `entry`, ora `entry["inputs"]`). MESMO dicionário de
        # origem, copiado — nunca duas verdades.
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
                    # `set_rgb` fixa brightness=255 e apaga por "0 0 0" — aceso
                    # de verdade = brightness > 0 E cor não-preta.
                    return rgb, bool(node_on and rgb != (0, 0, 0)), "sysfs"
                # Nó sumiu na corrida (replug) — cai para o desired abaixo.
            resolved = getattr(self.controller, "resolved_led_for", None)
            if callable(resolved):
                rgb = None
                with contextlib.suppress(Exception):
                    rgb = _rgb_or_none(resolved(uniq))
                if rgb is not None:
                    return rgb, rgb != (0, 0, 0), "desired"
        return None, False, "desconhecida"

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

        Leitura PURA: sai da foto que o sentinela do daemon já tirou (o tique
        de 30 s do `reconnect_loop`). O status é consultado a cada segundo pela
        GUI — sondar `/proc` aqui seria um `pgrep` por segundo, e o defeito que
        essa sonda existe para curar não vale esse preço.

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
        # e `bool(mock.veredito.segurado(no))` é True — um aviso na tela dela
        # nascido de um dublê de teste seria a pior estreia possível.
        if not isinstance(sentinela, _escritor_cru.SentinelaDeEscritorCru):
            return False
        return bool(sentinela.veredito.segurado(no))

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
            # Poda defensiva: replug infinito não pode crescer sem teto (o
            # conjunto real é 1-4 nós; 64 já é patológico).
            cache.clear()
        cache[cache_key] = (now, rgb, on)
        return rgb, on

    def _player_slot_for(self, uniq: str | None) -> int | None:
        """Slot de sessão do controle `uniq` via identity_registry (COR-01/D9).

        Consulta DEFENSIVA e só-leitura (``assign=False`` — expor estado nunca
        aloca slot novo). O registry é entregue pela frente de cores/perfis;
        daemon sem o atributo (ou dublê de teste devolvendo mock) → None.
        Controle sem MAC (uniq None) nunca tem slot (D9).
        """
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
        """MAC -> (vpad_backend, vpad_motivo) dos jogadores secundários (BT-03).

        Mesma fonte (`coop._players`, getattr defensivo) e mesmo critério de
        degradação do `dedup_status` da Fase 2 — aqui POR CONTROLE em vez de
        agregado. Jogador pendente (sem vpad) fica fora: não é jogador ainda.
        """
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

        Degradado = máscara DualSense servida por uinput (sem hidraw → sem
        vibração in-game, sem dedup por PID próprio); o motivo é o
        `fallback_motivo` da factory, com "sem_uhid" de piso. Máscara xbox é
        uinput POR DESIGN — nunca é degradação (invariante do `dedup_status`).
        """
        raw_backend = getattr(vpad, "backend", None)
        backend = raw_backend if isinstance(raw_backend, str) and raw_backend else None
        motivo: str | None = None
        if backend == "uinput" and getattr(vpad, "flavor", None) == "dualsense":
            raw = getattr(vpad, "fallback_motivo", None)
            motivo = raw if isinstance(raw, str) and raw else "sem_uhid"
        return backend, motivo

    # --- NUMA-05: sinal de autoridade de exibição (game/daemon/unknown) ----

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
        # unknown É o estado degradado/fail-safe por definição da síntese —
        # tanto o "não wireado" (wired=False) quanto o "classify() genuíno
        # devolveu unknown" (wired=True, authority=="unknown") contam.
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

    # --- GUI-05 item 3: honestidade do wrapper (`wrapper_used`) -----------

    #: PERFIL-MUDO-01 — cache do último cálculo, chaveado pela janela em foco.
    #: `state_full` roda a 10 Hz e `load_all_profiles()` lê o disco inteiro;
    #: sem isto seriam ~140 leituras de JSON por segundo com os 14 perfis dela.
    #: A chave é a tripla que o matcher consome, então a resposta só é
    #: recalculada quando a pergunta muda de verdade.
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
        """`wrapper_used` do momento: True/False com jogo em foco, None sem.

        Fonte da "janela de jogo": `store.window_detect_last_class` (a última
        wm_class ÚTIL do detector do autoswitch). Limitação documentada: se o
        jogo fechar direto para um desktop vazio ("unknown" não sobrescreve a
        última útil), o valor persiste até outra janela útil ganhar foco — a
        GUI já trata null como "sem jogo" e o marker segue datado.

        A PRIMEIRA detecção de cada appid é carimbada aqui (epoch) e é a base
        da janela de `WRAPPER_MARKER_WINDOW_SEC` contra o `last_run` do
        wrapper; a decisão em si é a função PURA `wrapper_used_state`.
        """
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

    # --- CONTROLE-QUE-NAO-ENTROU-01: o controle ligado que não entrou ------

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
        """
        external_raw = params.get("external", False)
        if not isinstance(external_raw, bool):
            raise ValueError("controller.list: 'external' precisa ser boolean")
        describe = getattr(self.controller, "describe_controllers", None)
        if callable(describe):
            result: dict[str, Any] = {"controllers": describe()}
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
            # (leitura PURA — quem escreve o LED é o tick lento, nunca este
            # handler); com o registry presente, `player_slot=None` (sem
            # opinião ainda) É o resultado — nunca mais o posicional. O
            # posicional ds_count+índice+1 só sobrevive sem `daemon`/registry
            # nenhum (daemon fake/legado — compat).
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

    async def _handle_controller_target_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Define o ALVO das ações de output (FEAT-DSX-CONTROLLER-SELECTOR-01).

        Params:
            index: int (posição em `controllers`, 0 = primário) ou null (TODOS).

        Com o alvo setado, lightbar/gatilhos/player-LED/rumble/mic-LED passam a
        mirar SÓ aquele controle — resolve o "ambos mostram Player 1". `index`
        null volta ao broadcast (padrão). Backends sem o método (FakeController,
        single-instance) são tolerados via getattr e tratados como broadcast.
        """
        index = params.get("index")
        # bool é subclasse de int — rejeitar True/False como índice.
        if index is not None and (isinstance(index, bool) or not isinstance(index, int)):
            raise ValueError("controller.target.set: 'index' precisa ser int ou null")
        setter = getattr(self.controller, "set_output_target", None)
        if not callable(setter):
            return {"status": "ok", "target_index": None}
        effective = setter(index)
        # Coerção defensiva: backend real devolve int|None; um mock devolveria
        # outra coisa — normaliza para int|None serializável.
        target_index = (
            effective if isinstance(effective, int) and not isinstance(effective, bool) else None
        )
        return {"status": "ok", "target_index": target_index}

    # --- rumble ----------------------------------------------------------

    async def _handle_lightbar_reset(self, params: dict[str, Any]) -> dict[str, Any]:
        """Manda o Reset LED state (0x08) sob demanda — INSTRUMENTO de medição.

        LIGHTBAR-MEDIR-O-0X08-01 (08/08/2026). Ver
        `backend_pydualsense.enviar_release_leds` para as três medições que este
        caminho existe para conciliar. Em uma linha: o 0x08 devolve o claim da
        lightbar ao host, e a suspeita é que ele só TRAVA quando mandado dentro
        da janela de ~3,4 s pós-conexão. Sem um gesto sob demanda, essa
        diferença não é falsificável sem brigar com o daemon pelo hidraw.

        ``uniq`` opcional restringe a um controle. A resposta traz o que foi
        enviado por handle — ``{}`` quer dizer "nenhum handle aberto", que é
        informação, não falha.
        """
        uniq = params.get("uniq")
        if uniq is not None and not isinstance(uniq, str):
            raise ValueError("lightbar.reset: 'uniq' precisa ser texto")
        # O backend é `self.controller` (o `IController` que o IpcServer
        # carrega), não `daemon.backend` — o primeiro tiro deste instrumento
        # errou exatamente aqui, e o defeito foi útil: provou que o handler
        # levanta ANTES de escrever no controle, então uma chamada que falha
        # não gasta a medição.
        enviar = getattr(self.controller, "enviar_release_leds", None)
        if not callable(enviar):
            raise RuntimeError("backend sem suporte a lightbar.reset")
        enviados = enviar(uniq=uniq)
        return {"status": "ok", "enviados": enviados}

    async def _handle_debug_player_leds(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga a escrita do LED de JOGADOR — INSTRUMENTO de eliminação.

        LIGHTBAR-ISOLAR-OS-PLAYERS-01 (08/08/2026), hipótese dela. Ver
        `backend_pydualsense.suprimir_player_leds` para o porquê e para as
        medições que apontam para cá.

        Comutável ao vivo de propósito: o experimento anterior se perdeu porque
        o instrumento exigia reiniciar o daemon, e o restart curou a barra antes
        do gesto que se queria medir.
        """
        suprimir = params.get("suprimir")
        if not isinstance(suprimir, bool):
            raise ValueError("debug.player_leds exige 'suprimir' booleano")
        alternar = getattr(self.controller, "suprimir_player_leds", None)
        if not callable(alternar):
            raise RuntimeError("backend sem suporte a debug.player_leds")
        return {"status": "ok", "suprimir": bool(alternar(suprimir))}

    async def _handle_rumble_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica rumble com política de intensidade (FEAT-RUMBLE-POLICY-01).

        Persiste (weak, strong) brutos em daemon.config.rumble_active para que
        o poll loop continue re-afirmando via _reassert_rumble. O multiplicador
        de política é aplicado antes de enviar ao hardware — tanto aqui quanto
        em _reassert_rumble.

        MESA-CHEIA-05 (E0): junto do par vai o DONO dele
        (`rumble_active_uniq`), congelado agora. Sem isso o reassert do poll
        loop reescrevia no alvo DE AGORA, e trocar o seletor levava o valor de
        um controle para outro.
        """
        weak = params.get("weak")
        strong = params.get("strong")
        if not isinstance(weak, int) or not isinstance(strong, int):
            raise ValueError("rumble.set exige 'weak' e 'strong' inteiros 0-255")
        weak = max(0, min(255, weak))
        strong = max(0, min(255, strong))
        # Persiste estado bruto antes de aplicar para o poll loop continuar re-afirmando.
        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        if daemon_cfg is not None:
            daemon_cfg.rumble_active = (weak, strong)
            daemon_cfg.rumble_active_uniq = uniq_do_alvo_de_output(self.controller)
        # Aplica política antes de enviar ao hardware.
        eff_weak, eff_strong = apply_rumble_policy(self.daemon, weak, strong)
        self.controller.set_rumble(weak=eff_weak, strong=eff_strong)
        # ONDA-U (Causa A): mesma trava de trigger.set — sem ela o
        # AutoSwitcher reescrevia o rumble no próximo tick de troca de foco
        # (U11). Categoria "rumble".
        self.store.mark_manual_trigger_active("rumble")
        return {"status": "ok", "weak": weak, "strong": strong}

    async def _handle_rumble_stop(self, params: dict[str, Any]) -> dict[str, Any]:
        """Para rumble e persiste estado (0, 0) (BUG-RUMBLE-APPLY-IGNORED-01).

        Zera os motores imediatamente e atualiza daemon.config.rumble_active para
        (0, 0) de forma que o poll loop re-afirme o silêncio, evitando que outro
        write HID re-ative motores inadvertidamente. Use rumble.passthrough para
        liberar controle completo ao jogo.

        MESA-CHEIA-05 (E0): o silêncio deliberado também tem dono — quem
        mandou calar UM controle não mandou calar o que entrar no seletor
        depois.

        MESA-CHEIA-05 (E0, terceira rodada) — **e cala quem está vibrando, não
        só quem está no seletor.** Medido em 14/08 contra `git archive HEAD`,
        com os quatro controles: ela fixa 160/220 no Controle 2, move o seletor
        para o 3 e clica «Parar». Os zeros iam para o 3 e o **2 continuava em
        220/160**; antes de o par ter dono, voltar o seletor ao 2 o silenciava,
        e com o dono congelado voltar o seletor deixou de significar coisa
        alguma — o gesto criava um beco sem saída. «Parar» quer dizer *cale o
        que está vibrando*, então o dono anterior leva os zeros ANTES de o
        endereço passar para o seletor de agora. A §5 da sprint, pelo nome: *"a
        volta ao neutro vale tanto quanto a ida"*.
        """
        # Import local, e o motivo foi MEDIDO em 14/08 (não é o ciclo do
        # reassert — no topo importa sem ciclo nenhum, nas cinco ordens de
        # entrada que testei): hoje `import ...daemon.ipc_handlers` carrega
        # ZERO módulos de `daemon.subsystems`, e puxar um deles executa o
        # `subsystems/__init__.py`, que importa TODOS — bt_mic, metrics,
        # plugins, udp, gamepad. Um handler de rumble não paga essa conta no
        # import de quem só quer falar IPC.
        from hefesto_dualsense4unix.daemon.subsystems.rumble import (
            silenciar_dono_abandonado,
        )

        daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
        dono_de_agora = uniq_do_alvo_de_output(self.controller)
        if daemon_cfg is not None:
            par_velho = getattr(daemon_cfg, "rumble_active", None)
            dono_velho = getattr(daemon_cfg, "rumble_active_uniq", None)
            daemon_cfg.rumble_active = (0, 0)
            daemon_cfg.rumble_active_uniq = dono_de_agora
            # Só quem vibrava por NOSSA conta é resgatado: par nenhum (o jogo
            # dirige) ou par (0,0) (já calado) não abandonam ninguém.
            if par_velho is not None and any(par_velho):
                silenciar_dono_abandonado(self.controller, dono_velho, dono_de_agora)
            # O par de agora é (0,0): ninguém mais vibra por nossa conta, e a
            # anotação do poll loop não pode ficar rançosa cobrando um resgate
            # que este gesto já pagou.
            daemon_cfg.rumble_dono_vibrando = None
        self.controller.set_rumble(weak=0, strong=0)
        # ONDA-U (Causa A): mesma trava de trigger.set (U11), categoria
        # "rumble".
        self.store.mark_manual_trigger_active("rumble")
        return {"status": "ok"}

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
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("rumble.passthrough exige 'enabled' boolean")
        if enabled:
            daemon_cfg = getattr(self.daemon, "config", None) if self.daemon else None
            if daemon_cfg is not None:
                daemon_cfg.rumble_active = None
                # MESA-CHEIA-05 (E0): sem par fixado não há dono a lembrar.
                daemon_cfg.rumble_active_uniq = None
            # F1 (auditoria 21/07): limpa SÓ a categoria "rumble" — o fim do
            # "Testar motores" não pode apagar um LED/gatilho deliberado
            # aplicado em outra aba (a trava era booleano único e o clear
            # aqui desarmava tudo).
            self.store.clear_manual_trigger_active("rumble")
        return {"status": "ok", "passthrough": enabled}

    async def _handle_rumble_policy_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Altera política global de intensidade de rumble (FEAT-RUMBLE-POLICY-01).

        Params:
            policy: "economia" | "balanceado" | "max" | "auto" | "custom"
        """
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
        # FEAT-RUMBLE-POLICY-PROFILE-01: gesto MANUAL da usuária na política —
        # carimba o lock de 30s e limpa a origem "perfil" (um perfil sem
        # opinião não reverte mais o que ela escolheu na mão).
        self._mark_rumble_policy_manual()
        logger.info("rumble_policy_alterada", policy=policy)
        return {"status": "ok", "policy": policy}

    async def _handle_rumble_policy_custom(self, params: dict[str, Any]) -> dict[str, Any]:
        """Define política "custom" com multiplicador explícito (FEAT-RUMBLE-POLICY-01).

        Params:
            mult: float 0.0-2.0 (acima de 1.0 AMPLIFICA o que o jogo pediu)

        HARM-19: a faixa era `0.0-1.0` aqui e `0.0-2.0` no esquema de perfil
        (`RumbleConfig.custom_mult`), com o slider da GUI indo até 200% — três
        donos, três faixas. O slider manda `valor/100`, então de 101% em diante a
        usuária recebia um erro de validação (que a aba ainda reportava como
        "daemon offline?"). Alinhado ao esquema, que é quem documenta a intenção:
        o `BUG-RUMBLE-CUSTOM-MULT-CAP-01` subiu o slider para 200% justamente
        porque "o schema aceita custom_mult até 2.0" — e esqueceu deste handler.
        """
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
        # FEAT-RUMBLE-POLICY-PROFILE-01: gesto MANUAL — mesma razão do
        # rumble.policy_set acima.
        self._mark_rumble_policy_manual()
        logger.info("rumble_policy_custom_definida", mult=mult)
        return {"status": "ok", "mult": mult}

    def _mark_rumble_policy_manual(self) -> None:
        """Propaga o gesto manual de política de rumble ao daemon.

        FEAT-RUMBLE-POLICY-PROFILE-01: delega a `Daemon.mark_rumble_policy_manual`
        (carimbo de `_emu_manual_ts` + limpeza da origem "perfil") via getattr —
        daemons dublados em teste (MagicMock/enxutos) não têm o método e o
        handler segue funcionando.
        """
        mark_manual = getattr(self.daemon, "mark_rumble_policy_manual", None)
        if callable(mark_manual):
            mark_manual()

    # --- daemon / mouse / plugins ----------------------------------------

    async def _handle_daemon_reload(self, params: dict[str, Any]) -> dict[str, Any]:
        """Aplica overrides parciais de config em runtime (REFACTOR-DAEMON-RELOAD-01).

        Params:
            config_overrides: dict com subset de campos de DaemonConfig.
                              Chaves inexistentes em DaemonConfig sao rejeitadas.

        Retorna:
            {status: "ok", config: <novo DaemonConfig como dict>}

        Erros:
            ValueError se daemon não disponível, ou se override contém chave
            desconhecida em DaemonConfig.
        """
        if self.daemon is None:
            raise ValueError("daemon não disponível para reload")

        from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

        overrides = params.get("config_overrides", {})
        if not isinstance(overrides, dict):
            raise ValueError("daemon.reload: 'config_overrides' deve ser objeto")

        # Validação antecipada: rejeita chaves que não existem em DaemonConfig.
        known_fields = set(DaemonConfig.__dataclass_fields__)
        unknown = set(overrides) - known_fields
        if unknown:
            raise ValueError(
                f"daemon.reload: campos desconhecidos em config_overrides: {sorted(unknown)}"
            )

        new_cfg = replace(self.daemon.config, **overrides)
        self.daemon.reload_config(new_cfg)
        # DEDUP-04: gatilho "mudança de config" da materialização das envs de
        # launch (o override pode ter trocado máscara/emulação sem passar
        # pelos hooks de start/stop).
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.launch_env import (
                materialize_launch_env,
            )

            materialize_launch_env(self.daemon)
        return {"status": "ok", "config": asdict(new_cfg)}

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

        Params: ``{volume?: 0-255, muted?: bool, release?: bool, uniq?: str}``.
        `uniq` escolhe o controle (MAC normalizado); omitido = o primário.

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
        if rota is not None:
            # SOM-ROTA-01/E3 — o caso do Zelda em um byte: `rota=2` manda o
            # canal esquerdo para o fone/TV e o DIREITO para o alto-falante do
            # controle. Ela descreveu assim: *"o speaker do controle faz os
            # barulhos da espada do Link enquanto na tela tem o som normal do
            # jogo"*.
            #
            # A faixa é 0-3 e o erro é de VALIDAÇÃO, não clamp: os quatro
            # valores significam coisas diferentes, e escolher um vizinho em
            # silêncio mandaria o áudio para outro lugar que não o pedido.
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
        if release and (volume is not None or muted is not None or rota is not None):
            raise ValueError(
                "speaker.set: 'release' não combina com 'volume'/'muted' — "
                "devolver a posse e mandar um valor na mesma chamada não tem "
                "significado honesto; mande dois pedidos"
            )

        if release:
            return await self._speaker_release(uniq)

        # O suporte do backend vem ANTES da guarda abaixo: num backend que nem
        # tem o método, "sem suporte" é a resposta verdadeira e "sem volume
        # conhecido" seria uma consequência dela vestida de causa.
        setter = getattr(self.controller, "set_speaker_volume", None)
        if not callable(setter):
            raise ValueError("backend sem suporte a volume de alto-falante")

        # SOM-02 (armadilha 2, medida): mudo como PRIMEIRA escrita tranca o
        # alto-falante em zero e o próprio mudo não o solta — o `muted=False`
        # restauraria uma preferência que vale 0. Sem volume conhecido, o pedido
        # é recusado com o caminho dito por extenso, em vez de virar um
        # `{'volume': 0, 'muted': True}` do qual não se sai. O backend recusa de
        # novo, na raiz (`set_speaker_volume`); aqui a recusa vira MENSAGEM, que
        # é o que o `status` sozinho não conseguiria dizer sem mentir
        # "sem_controle" para um controle que está conectado.
        sem_volume_conhecido = self._speaker_estado(uniq) is None
        if muted is not None and volume is None and sem_volume_conhecido:
            raise ValueError(
                "speaker.set: 'muted' sem volume conhecido — mande um 'volume' "
                "antes (mudo como primeira escrita tranca o alto-falante em "
                "zero e o próprio mudo não o solta)"
            )
        # A `rota` só é repassada QUANDO VEIO, e o kwarg nem aparece na
        # chamada sem ela. Duas razões, e a segunda é de contrato:
        #
        # 1. o backend trata `None` como "não tome a posse do common[7]", e é
        #    assim que o caminho do microfone (que mora no mesmo byte)
        #    continua intocado por omissão;
        # 2. o backend é TROCÁVEL (ADR-001), e um parâmetro novo não pode
        #    virar exigência retroativa para quem implementa a interface. Só
        #    quem pede a rota precisa de um backend que a conheça — e aí o
        #    `TypeError` é a resposta certa, não um silêncio.
        extras: dict[str, Any] = {} if rota is None else {"rota": rota}
        ok = bool(setter(volume, muted=muted, uniq=uniq, **extras))
        if ok:
            self._marcar_audio_manual()
        return {
            "status": "ok" if ok else "sem_controle",
            "speaker": self._speaker_estado(uniq),
        }

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
        if ok:
            self._marcar_audio_manual()
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

    def _marcar_audio_manual(self) -> None:
        """Arma a trava manual da categoria `audio` (SOM-02, decisão da E4).

        Mesma disciplina de `trigger.set`/`led.set`/`rumble.set`: um ajuste
        MANUAL dela não pode ser pisado pelo autoswitch reaplicando o perfil na
        próxima troca de janela. A alternativa considerada — deixar o volume
        fora da trava e fazer o aplicador de perfil rodar só em troca EXPLÍCITA
        de perfil — deixaria o furo aberto para todo caminho que reaplica perfil
        sem ser troca explícita. A razão está escrita junto da categoria em
        `daemon/state_store.py`.

        A devolução da posse também arma: parar de mandar é uma decisão dela
        tanto quanto mandar, e um perfil reaplicado logo depois retomaria a
        posse que ela acabou de soltar.
        """
        self.store.mark_manual_trigger_active("audio")

    async def _handle_mic_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """`mic.set` — mudo do microfone no FIRMWARE do controle (MIC-USB-01).

        Params: ``{muted: bool|null, uniq?: str}``. `uniq` escolhe o controle
        (MAC normalizado, mesmo roteamento por-uniq de `led.set`/`rumble.set`);
        omitido = o primário.

        POR QUE ESTE MÉTODO EXISTE. Em 25/07 o microfone da mantenedora estava
        mudo por TRÊS camadas empilhadas, e a aba Status dizia a verdade o
        tempo todo. Curadas as duas primeiras (o `mute:true` persistido por
        rota no estado do WirePlumber e o perfil da placa preso no S/PDIF sem
        sinal, ambas agora no `doctor --fix`), sobrou a terceira: o firmware do
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
            return {
                "status": "ok" if ok else "failed",
                "enabled": bool(
                    getattr(self.daemon.config, "mouse_emulation_enabled", False)
                ),
            }

        ok = self.daemon.set_mouse_emulation(
            enabled=enabled,
            speed=speed,
            scroll_speed=scroll_speed,
            origin=origem_do_pedido(params),
        )
        return {"status": "ok" if ok else "failed", "enabled": enabled and ok}

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

    async def _handle_gamepad_emulation_set(
        self, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Liga/desliga o gamepad virtual e define a máscara (FEAT-DSX-GAMEPAD-FLAVOR-01).

        Params:
            enabled: bool (obrigatório)
            flavor: "dualsense" | "xbox" e os sinônimos de
                `uinput_gamepad.FLAVOR_SINONIMOS` ("sony", "ps5", "ps",
                "playstation", "ds", "xbox360", "x360", "xinput") — opcional;
                ausente mantém a máscara atual. Nome fora dessa lista é
                **recusado** (`ValueError` → `invalid params`), nunca convertido
                em xbox por default (ver o comentário no corpo).

        Achado Onda S #6 — decisão registrada (desenho §9): o setter continua
        sendo chamado direto (síncrono) porque a parte BLOQUEANTE da cadeia —
        `_broker_sync_grab` → `client.hide/restore_all`, até ~4 s com broker
        lento — foi movida para o executor dedicado do broker
        (`broker_call_nonblocking`). Envolver o setter INTEIRO em
        `asyncio.to_thread` manteria o hide/restore bloqueando o start/stop
        dentro do worker (contra o §9) e criaria corrida real: o
        `coop.sync(force=True)` do setter passaria a mutar `_players` numa
        thread concorrente ao `coop.sync()` do poll loop (sem lock).
        """
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("gamepad.emulation.set exige 'enabled' boolean")
        flavor = params.get("flavor")
        if flavor is not None and not isinstance(flavor, str):
            raise ValueError("gamepad.emulation.set: 'flavor' precisa ser string")
        if flavor is not None:
            # NOME DESCONHECIDO É ERRO, NÃO DEFAULT (10/08/2026).
            #
            # Aqui embaixo o `normalize_flavor` é TOLERANTE: o que ele não
            # reconhece vira `DEFAULT_FLAVOR` == "xbox". Medido em runtime:
            # `--flavor sony` (a palavra dela) e `--flavor nintendo` chegavam ao
            # vpad como Xbox — a máscara OPOSTA à pedida no primeiro caso —, o
            # daemon respondia `status: "ok"` e devolvia `flavor: "xbox"` como se
            # fosse o pedido atendido. "sony"/"ps5" viraram sinônimos legítimos
            # (`FLAVOR_SINONIMOS`); o resto tem de RECUSAR em voz alta, senão a
            # tolerância do normalizador segue transformando erro de digitação em
            # troca silenciosa de máscara. Mesma lição do `or "xbox"` do editor de
            # perfis (ESCOLHE-DELA-VENCE-01, E1) e da `normalizar_mascara`
            # estrita do `external_mask`.
            #
            # A recusa vive AQUI, no portão de entrada de gente (GUI/CLI/applet
            # falam por este método), e não dentro do `normalize_flavor`: os
            # chamadores internos DEPENDEM do fallback — `uhid_gamepad.for_flavor`
            # lê "não é dualsense, logo não é meu" do default xbox, e
            # `coop`/`gamepad`/`virtual_pad` precisam de uma máscara sempre, até
            # com config de disco corrompida. Endurecer o normalizador quebraria
            # esses caminhos; endurecer o portão não toca em nenhum.
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
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar o gamepad virtual")

        ok = self.daemon.set_gamepad_emulation(
            enabled=enabled, flavor=flavor, origin=origem_do_pedido(params)
        )
        active_flavor = getattr(self.daemon.config, "gamepad_flavor", None)
        return {
            "status": "ok" if ok else "failed",
            "enabled": enabled and ok,
            "flavor": active_flavor,
        }

    async def _handle_coop_set(self, params: dict[str, Any]) -> dict[str, Any]:
        """Liga o co-op local; RECUSA desligar (FEAT-DSX-COOP-LOCAL-01).

        Params: enabled: bool (obrigatório). Com o gamepad virtual ativo + 2+
        controles, cada controle é um jogador (P1, P2, …).

        COOP-SEM-INTERRUPTOR-01 (06/08/2026, decisão da mantenedora): *"todos e
        tudo no Hefesto tem que tá com o permitir co-op ligado (…) se eu conecto
        4 controles no PC eu espero, com 4 pessoas jogando, que cada um controle
        o próprio personagem"*. O método SOBREVIVE porque a forma é contrato
        vivo (a CLI lê ``result["players"]``, e o "ligar" continua sendo o ciclo
        que reconcilia os jogadores), mas ``enabled: false`` passa a ser
        recusado EM VOZ ALTA — ``status: "recusado"`` com motivo legível, nunca
        um "ok" mentiroso. Quem quer um controle de reserva o deixa
        desconectado; quem quer suspender o co-op por Steam Input usa
        ``CoopManager.disable()``, que não depende desta flag.

        Achado Onda S #6: mesma decisão do `_handle_gamepad_emulation_set` —
        o hide/restore por jogador (`_broker_hide_player`/`_broker_restore_
        player`) roda no executor dedicado via `broker_call_nonblocking`; o
        setter em si fica no event loop (mover `coop.sync` para thread
        criaria corrida com o `sync` do poll loop em `_players`).
        """
        enabled = params.get("enabled")
        if not isinstance(enabled, bool):
            raise ValueError("coop.set exige 'enabled' boolean")
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar o co-op")
        if not enabled:
            # A forma do retorno é a MESMA (`players` continua lá): quem chama
            # não quebra, mas também não é enganado — `status` diz "recusado" e
            # `enabled` diz a verdade sobre o estado que ficou.
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
        """Roda UM ciclo cheio de reconciliação do co-op (`sync(force=True)`).

        COOP-SEM-INTERRUPTOR-01, entrega 5 (06/08/2026). Antes desta entrega o
        ciclo FORÇADO só existia em dois lugares automáticos (a troca de máscara
        em `set_gamepad_emulation` e a volta da exceção de Steam Input em
        `resume_vpads_after_steam_input`) e num gesto que ia sair da tela — o
        botão "Preparar co-op", que o disparava de carona no `coop.set`. Sem
        dono próprio, tirar o botão tiraria dela o ÚNICO gesto de recuperação do
        jogador que nasce e morre em dois segundos
        (COOP-QUE-NÃO-DESMONTA-01): o ciclo normal do poll loop só reenumera
        quando /dev/input muda, e um grab recusado ou um vpad morto podem
        esperar o próximo hotplug para sempre.

        Não liga nem desliga nada: não toca `config.coop_enabled`, não persiste
        preferência e não toma a posse do eixo `mode` (ao contrário do
        `coop.set`, que é gesto manual). Com o co-op inativo — sem gamepad
        virtual, ou dentro da exceção de Steam Input — `should_be_active()` é
        False e o ciclo apenas desmonta o que sobrou, que é o comportamento
        correto: reconciliar nunca ressuscita o que o jogo suspendeu.

        Retorno: ``{status: "ok", players: N, active: bool}``.
        """
        del params  # sem parâmetros: o gesto é "reconcilie agora".
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
        """Liga/desliga o modo jogo (suprime emulação mouse/teclado).

        FEAT-EMULATION-GAMEMODE-LONGPRESS-01. Param opcional `suppressed` (bool)
        define explicitamente; ausente faz toggle. Espelha o gesto de long-press
        do PS — usado por GUI/applet/CLI.
        """
        if self.daemon is None:
            raise ValueError("daemon não disponível para alterar modo jogo")
        suppressed = params.get("suppressed")
        if suppressed is not None and not isinstance(suppressed, bool):
            raise ValueError("emulation.suppress: 'suppressed' precisa ser bool")
        new_state = self.daemon.set_emulation_suppressed(suppressed)
        return {"status": "ok", "emulation_suppressed": new_state}

    async def _handle_plugin_list(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Lista plugins carregados no daemon (FEAT-PLUGIN-01).

        Retorna lista de dicts com: name, profile_match, disabled, classe.
        Requer plugins_enabled=True no daemon ou HEFESTO_DUALSENSE4UNIX_PLUGINS_ENABLED=1.
        """
        ps = getattr(self.daemon, "_plugins_subsystem", None) if self.daemon else None
        if ps is None:
            return []
        result: list[dict[str, Any]] = ps.list_plugins()
        return result

    async def _handle_plugin_reload(self, params: dict[str, Any]) -> dict[str, Any]:
        """Recarrega plugins do disco (FEAT-PLUGIN-01).

        Descarrega todos os plugins atuais, recarrega do diretório configurado
        e retorna o numero de plugins carregados.
        """
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


__all__ = ["DraftApplier", "IpcHandlersMixin"]
