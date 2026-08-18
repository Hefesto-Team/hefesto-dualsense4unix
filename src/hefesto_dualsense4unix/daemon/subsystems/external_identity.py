"""Identidade e LED dos controles EXTERNOS (EXT-04, sprint 2026-07-18).

Bug grave provado ao vivo (estudo §P3-BÔNUS): `_external_inventory` escrevia
os LEDs como efeito colateral de TODA leitura `controller.list{external:true}`
e a GUI polla a cada 4s sem comparar estado → bombardeio de subcomandos BT no
firmware clone → `joycon_enforce_subcmd_rate: exceeded max attempts` em loop →
o hid-nintendo DESREGISTROU o 8BitDo (a "morte por BT" era agravada por nós).
E o slot era `ds_count + índice-do-poll + 1`, recalculado a cada enumeração —
o LED mudava sozinho a cada poll/replug (ao vivo: o 8BitDo foi 2 de madrugada
e 4 à noite sem ninguém pedir).

A cura, em três peças:

1. :class:`ExternalIdentityRegistry` — lugares ESTÁVEIS por ``uniq`` (MAC),
   análogo ao ``ControllerIdentityRegistry`` dos DualSense: entra no FIM da
   fila, sempre ACIMA da reserva dos DualSense; o lugar FICA com o uniq no
   disconnect (replug recupera o número), com persistência que ATRAVESSA O
   BOOT (R-23 — era "por boot", e o reboot renumerando era metade da queixa
   "nunca sei o que é o quê") no MESMO ``controllers.json`` (as entradas de
   ``kind`` ``external`` da fila ÚNICA — cada registro preserva as do outro
   no read-modify-write, serializado pelo ``CONTROLLERS_FILE_LOCK``
   COMPARTILHADO de ``identity.py`` — NUMA-04, fecha o lost-update entre os
   dois escritores independentes). Cross-check UNILATERAL no ``load``:
   colisão de LUGAR entre os dois ``kind`` do mesmo arquivo (corrupção
   por lost-update pretérito) é resolvida a favor do DualSense — a entrada
   externa colidente é DROPADA, nunca realocada.

   NUM-01 (25/07): o número EXIBIDO deixou de ser esse lugar. Ele passa a ser
   a colocação do externo entre os controles PRESENTES da mesa — DualSense
   inclusive, porque a contagem 1..N é uma só. O lugar na fila continua sendo
   o que sobrevive ao desligar; o que ele já não faz é segurar um número
   enquanto o aparelho está fora (era assim que o controle sozinho na mesa
   exibia 2). A parte DualSense dessa contagem chega por
   :meth:`ExternalIdentityRegistry.set_dualsense_presence_provider`, fiado
   por :class:`ExternalLedSync` — o único componente que enxerga os dois
   registros. HIERARQUIA DE LOCKS (ver ``identity.py``): este lado resolve
   tudo o que precisa do lado DualSense ANTES de adquirir o próprio
   ``_lock``, porque o lado de lá chama providers daqui já segurando o dele.
2. :class:`ExternalLedSync` — o LED é aplicado pelo TICK do daemon (poll
   lento ~2s do lifecycle), com cache por-VALOR (escreve SÓ em mudança) +
   rate-limit de ``LED_MIN_INTERVAL_SEC`` por dispositivo + telemetria INFO
   ``external_led_written`` (antes era silencioso via contextlib.suppress).
3. A leitura IPC (`_external_inventory`) vira PURA: consulta ``peek`` (nunca
   atribui, nunca escreve LED).

Hermeticidade: a fiação do daemon (`_wire_external_registry`) só liga isto
quando o ``identity_registry`` dos DualSense existe (backend real) — com o
FakeController nada de /dev/input é enumerado e nenhum LED é tocado.

MODO-01 (2026-07-25) — um controle, DUAS identidades. O 8BitDo Pro se
apresenta conforme o MODO em que é ligado: em modo Switch no cabo o
``hid-nintendo`` degrada (``usb_probe_degrade``) e SINTETIZA um "MAC"
``0x02`` + VID + PID + bus; em modo PS4 por Bluetooth ele chega pelo
``hid-playstation`` com o MAC de verdade. O kernel vê dois aparelhos e o
registro também via: as duas entradas foram parar no ``controllers.json``, e
a do modo ausente segurava um slot — com 4 jogadores na mesa, o controle
CONECTADO caiu no slot 5 (medido ao vivo; o DualSense só tem 5 LEDs de
player, então empurrar alguém para lá é bug visível). A cura NÃO é adivinhar
que os dois são o mesmo plástico (não há nada em comum entre eles: OUI,
VID/PID e driver diferem) — é reconhecer que a identidade sintética não é
identidade: ver :data:`_SYNTHESIZED_MAC_FIRST_OCTET` e
:meth:`ExternalIdentityRegistry._prune_volatile_locked`.

GYRO-02 (2026-07-19, FASEADO): :class:`ExternalImuEnabler` reusa o MESMO
tick/inventário para ligar a IMU do Nintendo Pro REAL (OUI
:data:`NINTENDO_REAL_OUI`), que o hid-nintendo deixa em STANDBY. Mesmo
território de subcomando do incidente acima — por isso a disciplina é
ainda mais estrita: só ``bus == "usb"`` (fase 1), envio único por adoção,
backoff de :data:`IMU_ENABLE_MAX_ATTEMPTS` tentativas ≥
:data:`IMU_ENABLE_BACKOFF_SEC` segundos, nunca loop.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.daemon.subsystems.identity import (
    CONTROLLERS_FILE_LOCK,
    CONTROLLERS_SCHEMA_VERSION,
    KIND_DUALSENSE,
    KIND_EXTERNAL,
    ORDER_FIELD,
    _read_machine_id,
    merged_order_payload,
    order_entries,
)
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

logger = get_logger(__name__)

#: Mesmo arquivo do registro dos DualSense — namespace separado (``externals``).
_CONTROLLERS_FILE = "controllers.json"

#: MAC "de verdade" (mesma regra estrita do registro DualSense): 12 hex, com
#: ou sem ``:``/``-``. Qualquer outra key é identidade VOLÁTIL de sessão.
_MAC_RE = re.compile(
    r"^(?:[0-9a-fA-F]{12}|(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2})$"
)

#: MODO-01 (25/07): primeiro octeto dos endereços que NÓS MESMOS sintetizamos
#: — unicast administrado LOCALMENTE (bit 0x02 do 1º octeto, IEEE 802). Duas
#: fontes do projeto escrevem exatamente aqui:
#:
#: - o vpad uhid, que forja ``02:fe:...`` por jogador (``uhid_gamepad``);
#: - o ``usb_probe_degrade`` do nosso DKMS do ``hid-nintendo``: com o
#:   ``REQ_DEV_INFO`` mudo no cabo, o driver SINTETIZA a identidade em vez de
#:   perder o device — ``mac_addr[0] = 0x02``, depois VID (2 bytes), PID (2
#:   bytes) e bus (1 byte), ver ``patch/0003-*``.
#:
#: A segunda é a raiz do bug desta frente. Esse "MAC" não carrega NENHUM bit
#: do aparelho: é a tupla (VID, PID, bus) fantasiada de endereço. O 8BitDo Pro
#: ligado em modo Switch no cabo nasce com essa identidade sintética; o MESMO
#: plástico em modo PS4 por Bluetooth nasce com o MAC de verdade. O registro
#: guardava as DUAS como se fossem dois aparelhos, e a AUSENTE segurava um
#: slot: com 4 jogadores na mesa, o controle CONECTADO foi empurrado para o
#: slot 5 (medido ao vivo em 25/07, e o DualSense só tem 5 LEDs de player).
#: Pior que o fantasma: como o valor sai de (VID, PID, bus), dois controles
#: Nintendo-class DIFERENTES degradados no cabo recebem o MESMO endereço — o
#: próprio comentário do patch admite ("two identical clones plugged at once
#: would share it"). Persistir isso é gravar em disco uma FUSÃO de aparelhos.
#:
#: Por isso um endereço destes vale como identidade de SESSÃO (o controle
#: precisa de número enquanto está na mesa) e NUNCA como identidade
#: persistida. O critério é o octeto ``02`` EXATO, não "qualquer bit 0x02
#: ligado": a faixa forjada das fixtures (``aa:bb:cc:*``) e os endereços BLE
#: random-static (1º octeto ≥ 0xC0) também têm o bit ligado sem serem síntese
#: nossa, e um MAC de hardware com OUI atribuído nunca começa com ``02``.
_SYNTHESIZED_MAC_FIRST_OCTET = "02"

#: MODO-01: quantos ``sync_connected`` CONSECUTIVOS sem ver uma identidade
#: VOLÁTIL antes de soltar o slot dela. Uma ausência bastaria para o caso real
#: (trocar o 8BitDo de modo leva segundos), mas ``discover_external_gamepads``
#: engole exceção POR DEVICE (``except Exception: continue``) — um ``open`` que
#: falhe faz o controle sumir do inventário por um ciclo só. Exigir DUAS
#: ausências seguidas (~4 s no poll lento) troca "o fantasma some um tick
#: depois" por "um hiccup de enumeração não renumera ninguém".
VOLATILE_ABSENCE_LIMIT = 2

#: Rate-limit mínimo entre escritas de LED no MESMO dispositivo (EXT-04c).
#: O hid-nintendo tem enforcement de taxa de subcomando BT
#: (``joycon_enforce_subcmd_rate``) e firmware clone estoura fácil — 2s por
#: device é ordens de magnitude abaixo do bombardeio de 4-5 nós por poll que
#: matou o 8BitDo ao vivo.
LED_MIN_INTERVAL_SEC = 2.0

#: LUGAR-À-MESA-01 / E0 — **DECISÃO DELA, 07/08/2026: "calar a luz até a
#: entrega existir"** (resposta 12 do painel, em
#: ``docs/process/2026-08-07-DECISOES-DELA-as-onze-respostas-do-painel.md``).
#: Enquanto o controle externo NÃO for jogador de verdade dentro do jogo, o
#: Hefesto **não acende número de jogador nele**.
#:
#: **O que "calar" é, e por que não é "apagar".** Com este interruptor em
#: ``False`` o tick faz ZERO escritas — não apaga a barra do Pro nem a lightbar
#: do 8BitDo. O critério dela é *"o produto não pode AFIRMAR jogador"*, e apagar
#: também é afirmar: seria a nossa mão, no mesmo nó, dizendo "este controle não
#: tem jogador", destruindo o padrão que o firmware/kernel põe ali sozinho (na
#: lightbar do 8BitDo em modo DS4, acesa é o sinal de "ligado"; apagá-la trocaria
#: uma mentira por outra, "sem bateria"). Zero escritas deixa o plástico
#: EXATAMENTE como ficaria com o Hefesto desinstalado — e isso é falseável:
#: pare o daemon e a luz não muda. Três razões a mais: o rádio fica sem tráfego
#: de LED na direção do firmware mais frágil da mesa (o clone do 8BitDo morre
#: sob bombardeio — `daemon/ipc_handlers.py:286-291`); o precedente MEDIDO desta
#: casa já traduz "parar de afirmar" como *"zero escritas, sem apagar
#: ativamente"* (o gate ``auto_numbers`` logo abaixo, R-14/NUMA-03c), e ter duas
#: doutrinas para a mesma frase é como se perde uma; e o custo de voltar é uma
#: linha.
#:
#: **O caminho de volta é UMA LINHA: trocar para ``True``.** A capacidade não
#: foi enterrada — ``core/external_leds.py`` continua inteiro e testado, e o
#: gate limpa os caches ao passar, então o primeiro tick com a luz de volta
#: reescreve todos os slots. A ATRIBUIÇÃO de slot NÃO é afetada (numerar é
#: identidade; este interruptor governa só a APARÊNCIA).
#:
#: **Condição de volta, objetiva:** quando o externo virar jogador de verdade —
#: a `E3` da LUGAR-À-MESA-01, que ela autorizou **só depois da MASCARA-01**.
#: Não é "quando alguém achar que já dá".
#:
#: **Custo declarado (GRAU: SUSPEITA COM MECANISMO).** O nó de LED guarda o
#: último valor escrito enquanto o device segue vinculado: num daemon que
#: REINICIA com o controle já conectado, o número que a versão anterior acendeu
#: FICA aceso — resíduo nosso, não afirmação nova. Reconectar o controle (ou
#: religá-lo) devolve o padrão do firmware. Apagar uma vez na transição foi
#: recusado de propósito: é exatamente a escrita que o critério dela proíbe.
EXTERNAL_PLAYER_LED_ENABLED = False

#: GYRO-02: OUI (6 hex, sem ``:``) do Nintendo Pro Controller GENUÍNO — o
#: ÚNICO gatilho do enable-IMU. NÃO confundir com o 8BitDo em modo Switch
#: (mesmo VID/PID 057e:2009, IMU nativa já viva — nada a fazer nele); a OUI
#: é a fonte da verdade (mapa 2026-07-19 §OUI), nunca VID/PID/driver.
NINTENDO_REAL_OUI = "e0f6b5"

#: FASE 1 (GYRO-02): só USB. BT é o MESMO território de subcomando que matou
#: o 8BitDo (`joycon_enforce_subcmd_rate`) — falta medição de campo com o
#: kernel-watch `[JOYCON]` limpo antes de liberar por rádio.
_IMU_ENABLE_ALLOWED_BUS = "usb"

#: Nunca loop: no máximo 2 tentativas por adoção, espaçadas ≥2s (mesmo
#: espírito do `LED_MIN_INTERVAL_SEC`, mas um subcomando DIFERENTE — conta
#: separada da dos LEDs).
IMU_ENABLE_MAX_ATTEMPTS = 2
IMU_ENABLE_BACKOFF_SEC = 2.0


def _read_boot_id() -> str | None:
    """boot_id do kernel (None se ilegível). R-23: anotação, não mais gate."""
    try:
        with open("/proc/sys/kernel/random/boot_id", encoding="utf-8") as fh:
            value = fh.read().strip()
        return value or None
    except OSError:
        return None


def _is_synthesized_mac(key: str) -> bool:
    """True quando a key 12-hex é endereço SINTETIZADO por software (MODO-01).

    Ver :data:`_SYNTHESIZED_MAC_FIRST_OCTET` para o porquê do critério ser o
    octeto ``02`` exato. Recebe a key JÁ canônica (minúscula, sem separadores).
    """
    return key[:2] == _SYNTHESIZED_MAC_FIRST_OCTET


def _present_ranks_of(registry: Any) -> set[int]:
    """Lugares da fila ocupados AGORA por um registro qualquer (NUM-01).

    Usado para ler o lado DualSense sem acoplar a classe concreta (dublês de
    teste entregam ``SimpleNamespace``). Ordem de degradação:

    1. ``present_ranks()`` — a resposta exata (só os presentes);
    2. ``snapshot()`` + ``snapshot_connected()`` — a mesma conta feita fora;
    3. só ``snapshot()`` — registro de versão anterior, que não sabe dizer
       quem está ligado: conta TODOS. Conservador de propósito (buraco na
       numeração é aceitável; dois controles com o mesmo número, não).

    Nunca levanta: sem nada legível devolve conjunto vazio.
    """
    fn = getattr(registry, "present_ranks", None)
    if callable(fn):
        with contextlib.suppress(Exception):
            return {int(r) for r in fn()}
    snap = getattr(registry, "snapshot", None)
    if not callable(snap):
        return set()
    mapa: dict[str, int] = {}
    with contextlib.suppress(Exception):
        bruto = snap()
        if isinstance(bruto, dict):
            mapa = {
                str(k): int(v)
                for k, v in bruto.items()
                if isinstance(v, int) and not isinstance(v, bool)
            }
    conectados = getattr(registry, "snapshot_connected", None)
    if callable(conectados):
        with contextlib.suppress(Exception):
            vivos = {str(k) for k in conectados()}
            return {rank for key, rank in mapa.items() if key in vivos}
    return set(mapa.values())


def _session_anchor() -> str | None:
    """Âncora resiliente boot_id → machine-id (R-23) — espelho de ``identity``.

    Os dois registros gravam o MESMO campo ``boot_id`` do MESMO arquivo; se
    calculassem a âncora por regras diferentes, cada save sobrescreveria o do
    outro com um valor divergente. Por isso o 2º degrau é literalmente a
    função do ``identity`` (``_read_machine_id``), não uma cópia.
    """
    valor = _read_boot_id()
    if valor:
        return valor
    machine_id = _read_machine_id()
    return f"machine:{machine_id}" if machine_id else None


#: CLONE-01 (25/07): campo em que uma entrada do inventário de externos CARREGA
#: a identidade de aparelho JÁ calculada (ver :func:`identity_for_entry`). Quem
#: enumerou o aparelho é quem sabe resolvê-la — o cálculo depende do sysfs vivo
#: —, então ela viaja no payload em vez de ser recalculada por cada consumidor.
#: É por este campo que a GUI (outro PROCESSO, do outro lado do JSON-RPC) recebe
#: a mesma string que o daemon usou para numerar, sem tocar em ``/sys``.
EXTERNAL_IDENTITY_FIELD = "identity"


def _vid_pid_de(entry: dict[str, Any]) -> tuple[int, int] | None:
    """``(vendor, product)`` inteiros da entrada, ou ``None`` se ilegíveis.

    O inventário publica ``vid``/``pid`` como hex de 4 dígitos minúsculo
    (``"057e"``); a detecção do endereço sintético precisa deles como INTEIRO
    (a fórmula do kernel é literalmente ``02`` + VID + PID + bus). Entrada
    montada à mão sem esses campos (dublê de teste, payload de daemon antigo)
    devolve ``None`` — o chamador degrada, nunca levanta.
    """
    try:
        return int(str(entry["vid"]), 16), int(str(entry["pid"]), 16)
    except (KeyError, TypeError, ValueError):
        return None


def identity_for_entry(entry: dict[str, Any]) -> str:
    """Identidade de APARELHO de uma entrada do inventário de externos.

    FONTE ÚNICA da string com que este projeto numera um controle externo. Os
    consumidores são três e precisam enxergar exatamente a MESMA coisa, senão o
    número que a GUI exibe deixa de ser o número que o LED acende:

    - :meth:`ExternalLedSync.tick` — quem ATRIBUI o slot e acende o LED;
    - ``ipc_handlers._external_inventory`` — quem responde o ``player_slot`` à
      GUI (leitura pura, via ``peek``);
    - ``app.actions.external_controllers.external_key`` — quem casa o botão do
      seletor com a entrada, do outro lado do JSON-RPC.

    Ordem de resolução:

    1. o campo :data:`EXTERNAL_IDENTITY_FIELD`, quando a entrada já o carrega —
       calcular DE NOVO é o que faz duas camadas divergirem, e a GUI nem teria
       como (o cálculo lê o sysfs do aparelho, que é do daemon, não dela);
    2. :func:`~hefesto_dualsense4unix.core.evdev_reader._external_dedup_key` —
       a MESMA função com que a enumeração deduplica o inventário: MAC quando
       ele identifica o aparelho, ``dev:<instância HID>`` quando o ``uniq``
       falta ou é o endereço SINTÉTICO que o ``hid-nintendo`` degradado fabrica
       (``02`` + VID + PID + bus, igual para dois clones — CLONE-01), e
       ``path:<node>`` de último recurso;
    3. sem VID/PID legíveis não há como julgar se o ``uniq`` é sintético (a
       fórmula do kernel É o VID+PID): vale o MAC canônico e, sem ele, o node.

    CLONE-01 é o motivo de o degrau 2 não ser mais "``uniq`` ou ``path:``": dois
    Nintendo-class degradados no cabo (Pro genuíno + 8BitDo, ambos 057e:2009)
    entregam o MESMO ``uniq`` ao kernel. Os dois já APARECEM no inventário desde
    a correção da enumeração, mas aqui recebiam a mesma chave — logo o mesmo
    slot e o mesmo LED de jogador. Com o dono no sysfs eles são dois.

    A identidade continua VOLÁTIL nesse caso (``dev:``/``path:`` não casam com
    :data:`_MAC_RE`, e o endereço sintético que sobreviva ao degrau 3 casa
    :func:`_is_synthesized_mac`): ganha número na sessão, some do disco na
    ausência. O que muda é que agora são DOIS voláteis distintos, não um.
    """
    pronta = entry.get(EXTERNAL_IDENTITY_FIELD)
    if isinstance(pronta, str) and pronta:
        return pronta

    from hefesto_dualsense4unix.core.evdev_reader import _external_dedup_key
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    bruto_path = entry.get("evdev_path")
    caminho = bruto_path if isinstance(bruto_path, str) else ""
    bruto_uniq = entry.get("uniq")
    uniq = bruto_uniq if isinstance(bruto_uniq, str) else ""
    par = _vid_pid_de(entry)
    if par is None:
        return norm_mac(uniq) or f"path:{caminho}"
    return _external_dedup_key(caminho, uniq, par[0], par[1])


class ExternalIdentityRegistry:
    """``uniq`` de externo → slot GLOBAL de co-op, com reserva de sessão.

    Espelha o desenho do ``ControllerIdentityRegistry`` (D1/D2/D9), com duas
    diferenças de domínio:

    - o menor slot livre respeita a RESERVA dos DualSense (``reserve``):
      externos continuam a contagem (1º externo = reserva+1) — mas um slot já
      atribuído NUNCA é renumerado quando a reserva muda depois (estabilidade
      vence: é o fim do "LED muda sozinho");
    - sem expiração por sessão-esvaziou: a persistência ATRAVESSA o boot
      (R-23) e o disconnect apenas RESERVA o slot — para MAC de HARDWARE.
      MODO-01: identidade VOLÁTIL (endereço sintetizado, key ``path:...``)
      não ganha essa promessa; ausente, ela solta o slot.

    Thread-safety: os métodos são chamados pelo tick do lifecycle (via
    executor) e pela leitura IPC (``asyncio.to_thread``) — RLock próprio.
    O save é read-modify-write no ``controllers.json``: preserva ``slots``
    (namespace dos DualSense) e grava só ``externals``. NUMA-04: ``load`` e
    ``_save_locked`` adquirem o ``CONTROLLERS_FILE_LOCK`` de ``identity.py``
    (o MESMO lock, importado — nunca um novo) em volta do read→
    ``os.replace`` — o ``RLock`` de instância protege só ESTE objeto; sem o
    lock de módulo, o RMW deste registro podia intercalar com o do
    ``ControllerIdentityRegistry`` e um dos dois namespaces sumia do disco.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        #: NUM-01: key canônica → LUGAR NA FILA global (não o número
        #: exibido; esse sai de ``slot_for``, que conta os presentes).
        self._ordem: dict[str, int] = {}
        self._volatile: set[str] = set()
        self._connected: set[str] = set()
        #: MODO-01: key VOLÁTIL → nº de ``sync_connected`` consecutivos sem
        #: ela. Só identidade volátil entra aqui — reserva de MAC de hardware
        #: não expira nunca (D2/R-15).
        self._volatile_absences: dict[str, int] = {}
        self._dirty = False
        self._loaded = False
        #: NUM-01: provider OPCIONAL dos lugares dos DualSense PRESENTES —
        #: a metade da contagem 1..N que mora do outro lado. ``None`` (sem
        #: fiação, dublê de teste) degrada para o ``reserve`` mais recente,
        #: que superestima: pode abrir um buraco na numeração, nunca dá o
        #: mesmo número a dois controles.
        self._ds_presence: Callable[[], set[int]] | None = None
        #: Último ``reserve`` visto — é o piso que ``peek`` usa quando não há
        #: provider de presença (a rota IPC não tem de onde tirar um).
        self._ultimo_piso = 0

    @staticmethod
    def _canonical(uniq: str) -> tuple[str, bool]:
        """``(key, persistível)`` — MAC 12-hex canônico ou key volátil crua.

        MODO-01: persistível = MAC de HARDWARE. Um endereço SINTETIZADO
        (:func:`_is_synthesized_mac`) é bem-formado, mas não é identidade de
        aparelho nenhum — entra como VOLÁTIL, na mesma classe da key
        ``path:...`` de firmware sem serial. Isto sozinho já expulsa do disco a
        entrada fantasma que o :meth:`load` encontrar (o filtro
        ``if not persistable: continue`` já existia lá): não há migração de
        schema a escrever, e nenhum controle de verdade perde o número por
        causa de um bump de versão que não precisou acontecer.
        """
        value = uniq.strip()
        if _MAC_RE.match(value):
            key = value.lower().replace(":", "").replace("-", "")
            return key, not _is_synthesized_mac(key)
        return value, False

    def set_dualsense_presence_provider(
        self, provider: Callable[[], set[int]] | None
    ) -> None:
        """Injeta os lugares dos DualSense PRESENTES agora (NUM-01).

        A contagem 1..N é da MESA, não de cada registro: se dois DualSense
        estão ligados, o primeiro externo é o jogador 3. Antes de NUM-01 esse
        deslocamento vinha embutido no próprio número gravado (o externo
        nascia acima da reserva e ficava lá); agora ele é recalculado a cada
        consulta, senão um DualSense desligado continuaria empurrando o
        externo para cima — o mesmo defeito, do outro lado da mesa.

        Fiado por :class:`ExternalLedSync`. ``None`` = sem fiação: cai no
        último ``reserve`` visto (ver :meth:`_ds_present_ranks`).
        """
        with self._lock:
            self._ds_presence = provider

    def present_ranks(self) -> set[int]:
        """Lugares da fila ocupados por externos PRESENTES agora (NUM-01).

        Espelho de ``ControllerIdentityRegistry.present_ranks`` — é o que o
        lado DualSense consome para contar a mesa inteira.
        """
        with self._lock:
            return {
                rank
                for key, rank in self._ordem.items()
                if key in self._connected
            }

    def _ds_present_ranks(self, reserve: int = 0) -> set[int]:
        """Lugares dos DualSense que contam na exibição (NUM-01).

        NUNCA chamar com ``self._lock`` tomado: esta função consulta o
        registro dos DualSense, e a hierarquia de locks é DualSense →
        externos → arquivo (ver docstring de ``identity.py``). Inverter aqui
        fecharia um ciclo com o ``identity.renumber``, que toma os dois na
        ordem canônica.

        Sem provider de presença, o piso é o ``reserve`` mais recente (o
        maior lugar que os DualSense detêm, vindo de ``_ds_reserve``): supõe
        que todos os lugares até ele estão na mesa. É a suposição
        CONSERVADORA — deixa um buraco na numeração quando um DualSense está
        desligado, em vez de arriscar dois controles com o mesmo número.
        Lugares que são DESTE registro saem da conta: a fila é uma só, então
        sobreposição é corrupção (ou dublê), nunca gente de verdade à frente.
        """
        prov = self._ds_presence
        brutos: set[int] | None = None
        if prov is not None:
            with contextlib.suppress(Exception):
                brutos = {int(r) for r in prov()}
        with self._lock:
            if reserve and int(reserve) > 0:
                self._ultimo_piso = int(reserve)
            piso = self._ultimo_piso
            meus = set(self._ordem.values())
        if brutos is None:
            brutos = set(range(1, piso + 1))
        return brutos - meus

    def _posicao_locked(self, key: str, ds_presentes: set[int]) -> int | None:
        """Colocação de ``key`` entre os PRESENTES da mesa (sob ``self._lock``).

        Empate de lugar com um DualSense (só possível por corrupção) resolve
        a favor do DualSense — mesma regra do cross-check do ``load`` e da
        gravação da fila, para a ordem exibida nunca discordar da gravada.
        """
        rank = self._ordem.get(key)
        if rank is None:
            return None
        antes = sum(
            1
            for outra in self._connected
            if outra != key and self._ordem.get(outra, rank + 1) < rank
        )
        antes += sum(1 for r in ds_presentes if r <= rank)
        return antes + 1

    def slot_for(
        self, uniq: str | None, *, reserve: int = 0, assign: bool = True
    ) -> int | None:
        """Número EXIBIDO do externo ``uniq``; entra no FIM da fila na 1ª vez.

        NUM-01: o que se guarda é o lugar na fila (sempre acima de
        ``reserve``, o piso dos DualSense — EXT-04); o que se devolve é a
        colocação entre os controles PRESENTES da mesa, DualSense inclusive.
        Com dois DualSense ligados o primeiro externo exibe 3; com um deles
        desligado, exibe 2 — sem que o lugar dele na fila mude.

        ``assign=False`` é leitura pura (não atribui, não marca conectado) —
        é o modo da rota IPC. SEM I/O de disco (a persistência fica com
        ``sync_connected``, no tick lento).
        """
        if not uniq or not isinstance(uniq, str):
            return None
        key, persistable = self._canonical(uniq)
        if not key:
            return None
        # Hierarquia de locks: o lado DualSense é consultado ANTES de tomar
        # o lock deste registro (ver `_ds_present_ranks`).
        ds_presentes = self._ds_present_ranks(reserve)
        with self._lock:
            if key not in self._ordem:
                if not assign:
                    return None
                ocupados = set(self._ordem.values())
                rank = max([*ocupados, int(reserve), 0]) + 1
                self._ordem[key] = rank
                if persistable:
                    self._dirty = True
                else:
                    self._volatile.add(key)
                logger.info(
                    "external_lugar_atribuido",
                    uniq=key,
                    rank=rank,
                    reserva_dualsense=reserve,
                    volatil=not persistable,
                )
            if assign:
                self._connected.add(key)
            return self._posicao_locked(key, ds_presentes)

    def peek(self, uniq: str | None) -> int | None:
        """Leitura PURA do número exibido (rota IPC): nunca atribui/persiste."""
        return self.slot_for(uniq, assign=False)

    def sync_connected(self, uniqs: Iterable[str]) -> None:
        """Reconcilia com os uniqs presentes AGORA (tick ~2s) e persiste.

        Quem saiu vira RESERVA (slot preso ao uniq — replug recupera o
        número). Diferente do registro DualSense, não há expiração por
        sessão-esvaziou: um externo BT que dorme não pode perder o número
        (era exatamente o sintoma). ÚNICO ponto de escrita em disco fora do
        ``load()``.

        MODO-01 (25/07): a reserva eterna vale para MAC de HARDWARE. Uma
        identidade VOLÁTIL ausente solta o slot (ver
        :meth:`_prune_volatile_locked`) — ela não é aparelho nenhum, então
        não há promessa de estabilidade a honrar, e segurar slot era
        exatamente o que empurrava o controle CONECTADO para o número 5.
        """
        vivos: set[str] = set()
        for uniq in uniqs:
            if not uniq or not isinstance(uniq, str):
                continue
            key, _ = self._canonical(uniq)
            vivos.add(key)
        with self._lock:
            self._connected = vivos
            self._prune_volatile_locked(vivos)
            if self._dirty:
                self._save_locked()
                self._dirty = False

    def _prune_volatile_locked(self, vivos: set[str]) -> None:
        """Solta o slot de identidade VOLÁTIL ausente (já sob ``self._lock``).

        MODO-01 — a assimetria é deliberada e é a cura:

        - MAC de HARDWARE ausente segue RESERVADO para sempre (D2/R-15): "o
          controle que eu deixo desligado tem que voltar com o mesmo número"
          é requisito antigo, e nada aqui o toca;
        - identidade VOLÁTIL (endereço sintetizado pelo ``usb_probe_degrade``,
          key ``path:...`` de firmware sem serial) não identifica aparelho
          nenhum, então "replug recupera o número" não significa nada para
          ela — mas o slot que ela segurava significava, e muito: era ele que
          fazia o 8BitDo CONECTADO cair no slot 5 enquanto a identidade do
          modo Switch, DESCONECTADA, ocupava o 4.

        Ausência é contada, não instantânea (:data:`VOLATILE_ABSENCE_LIMIT`)
        — a enumeração pode perder um device por um ciclo sem ele ter saído.
        Nunca marca ``_dirty``: chave volátil jamais esteve no disco.
        """
        for key in list(self._volatile):
            if key in vivos:
                self._volatile_absences.pop(key, None)
                continue
            faltas = self._volatile_absences.get(key, 0) + 1
            if faltas < VOLATILE_ABSENCE_LIMIT:
                self._volatile_absences[key] = faltas
                continue
            self._volatile_absences.pop(key, None)
            self._volatile.discard(key)
            rank = self._ordem.pop(key, None)
            logger.info(
                "external_lugar_volatil_liberado", uniq=key, rank=rank
            )

    def snapshot(self) -> dict[str, int]:
        """Cópia do mapa key→LUGAR NA FILA (presentes + ausentes). Leitura pura.

        NUM-01: o valor NÃO é o número exibido (esse é ``slot_for``/``peek``,
        que contam os presentes) — é o posto na fila global compartilhada com
        os DualSense. Quem consome: o plano do "Renumerar agora" e o
        cross-check de colisão.
        """
        with self._lock:
            return dict(self._ordem)

    def snapshot_connected(self) -> set[str]:
        """Keys presentes no último ``sync_connected``. Leitura pura (R-15).

        Espelho de ``ControllerIdentityRegistry.snapshot_connected``: o
        "Renumerar agora" compacta os CONECTADOS em 1..N e só depois anexa as
        reservas offline — sem isto, o 8BitDo dormindo num slot baixo tornava
        a compactação um no-op que ainda toastava sucesso.
        """
        with self._lock:
            return set(self._connected)

    def lock_for_renumber(self) -> threading.RLock:
        """Expõe o `RLock` de instância — SÓ para `identity.renumber` (fix TOCTOU).

        Espelho de `ControllerIdentityRegistry.lock_for_renumber` — mesmo
        achado MEDIUM (2026-07-20): sem isto, um `slot_for(assign=True)`
        concorrente do `ExternalLedSync.tick()` (executor) podia reivindicar,
        entre o `snapshot()` e o `compact()` do handler IPC, o slot-alvo que
        a compactação global estava prestes a atribuir a outra chave. Não
        usar para mais nada.
        """
        return self._lock

    def compact(self, mapping: dict[str, int]) -> None:
        """Reordena a FILA conforme ``mapping`` (``identity.renumber``, ONDA-U).

        Espelho do ``ControllerIdentityRegistry.compact`` — mesma
        justificativa (reescrita EXPLÍCITA, gate de sessão vazia é do
        CHAMADOR; só troca chaves já presentes NESTE registro). O
        ``ExternalLedSync.tick()`` seguinte repinta o LED sozinho: o cache
        por-valor (``_last_value``) compara contra ``slot_for``, que passa a
        devolver o número novo já aqui — sem precisar limpar cache.

        NUM-01: os valores de ``mapping`` são LUGARES NA FILA, não números
        exibidos (o exibido pode nem mudar — ele já contava só os presentes).
        """
        with self._lock:
            changed = False
            for key, novo_rank in mapping.items():
                if key in self._ordem and self._ordem[key] != novo_rank:
                    self._ordem[key] = novo_rank
                    changed = True
            if changed:
                self._dirty = True
                self._save_locked()
                self._dirty = False

    # -- persistência (entradas ``external`` da fila do controllers.json) --

    def load(self) -> None:
        """Carrega as entradas EXTERNAS da fila — ATRAVESSA o boot (R-23).

        Espelha ponto a ponto o ``ControllerIdentityRegistry.load``: o gate
        deixou de ser o ``boot_id`` (que renumerava o 8BitDo/Pro a cada
        reboot, e a cada restart do daemon sem ``/proc``) e passou a ser o
        :data:`CONTROLLERS_SCHEMA_VERSION`. A simetria é obrigatória — os
        dois lados dividem uma fila só (R-24/NUM-01); se um restaurasse e o
        outro não, o que sobrasse escolheria lugares por cima de reservas
        invisíveis e nasceriam as duplicatas de novo.

        NUMA-04: a leitura roda sob ``CONTROLLERS_FILE_LOCK`` (compartilhado
        com ``identity.py``). Cross-check UNILATERAL contra as entradas
        ``kind`` :data:`KIND_DUALSENSE` da MESMA fila: um LUGAR que aparece
        nos dois lados só pode ter chegado lá por um lost-update pretérito (o
        bug que o lock agora fecha) — o DualSense VENCE, a entrada externa
        colidente é DROPADA (nunca realocada, nunca poda o lado DualSense) +
        log WARN ``controllers_json_colisao_descartada``; o externo ganha
        lugar novo na próxima atribuição, ainda com a sessão vazia (D2
        permite).
        """
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            with CONTROLLERS_FILE_LOCK:
                try:
                    data = json.loads(self._path().read_text(encoding="utf-8"))
                except (FileNotFoundError, json.JSONDecodeError, OSError):
                    return
                except Exception as exc:  # defensivo — load jamais derruba
                    logger.debug("external_identity_load_falhou", err=str(exc))
                    return
            if not isinstance(data, dict):
                return
            if data.get("version") != CONTROLLERS_SCHEMA_VERSION:
                logger.info(
                    "external_arquivo_de_schema_antigo_descartado",
                    versao_arquivo=data.get("version"),
                    versao_atual=CONTROLLERS_SCHEMA_VERSION,
                )
                return
            entradas = order_entries(data)
            if not entradas:
                return
            lugares_do_dualsense = {
                rank for _addr, kind, rank in entradas if kind == KIND_DUALSENSE
            }
            usados: set[int] = set()
            descartadas = 0
            for raw_key, kind, raw_rank in entradas:
                if kind != KIND_EXTERNAL:
                    continue
                if raw_rank in lugares_do_dualsense:
                    logger.warning(
                        "controllers_json_colisao_descartada",
                        rank=raw_rank,
                        externo=raw_key,
                    )
                    continue
                key, persistable = self._canonical(raw_key)
                if not persistable:
                    # MODO-01: identidade SINTETIZADA (ou volátil) que uma
                    # versão anterior gravou. Não volta — e o arquivo é
                    # reescrito sem ela no primeiro save (ver `_dirty` abaixo).
                    descartadas += 1
                    logger.info(
                        "external_identidade_nao_persistivel_descartada", uniq=key
                    )
                    continue
                if key in self._ordem or raw_rank in usados:
                    continue
                self._ordem[key] = raw_rank
                usados.add(raw_rank)
            if descartadas:
                # MODO-01: a MIGRAÇÃO. `_save_locked` reescreve as entradas
                # externas INTEIRAS a partir de `_ordem`, então marcar sujo
                # aqui faz o próximo `sync_connected` (tick lento) limpar o
                # disco sozinho. Sem isto o fantasma ficava inerte no arquivo
                # até que outra coisa sujasse o registro — inofensivo (o load
                # já o ignora), mas ninguém entenderia por que ele continua
                # lá. Não havia bump de `CONTROLLERS_SCHEMA_VERSION` na época:
                # bumpar renumeraria TODO mundo para expulsar uma entrada só.
                self._dirty = True
            if self._ordem:
                logger.info(
                    "external_fila_restaurada", ordem=dict(self._ordem)
                )

    @staticmethod
    def _path() -> Path:
        """Path do ``controllers.json`` — import LAZY (monkeypatch dos testes)."""
        from hefesto_dualsense4unix.utils.xdg_paths import config_dir

        return config_dir(ensure=True) / _CONTROLLERS_FILE

    def _save_locked(self) -> None:
        """Read-modify-write atômico: grava a fatia EXTERNA da fila (NUM-01).

        O ``ControllerIdentityRegistry`` (DualSense) grava ``boot_id`` + as
        entradas ``kind`` :data:`KIND_DUALSENSE` do MESMO campo
        :data:`ORDER_FIELD` — cada lado preserva as entradas do outro via
        :func:`merged_order_payload`. Nunca propaga exceção: perder um save =
        renumerar no próximo boot. NUMA-04: o span INTEIRO
        read→``os.replace`` roda sob o ``CONTROLLERS_FILE_LOCK`` de
        ``identity.py`` (importado, nunca um lock novo) — fecha o
        lost-update com o save do lado DualSense.
        """
        try:
            with CONTROLLERS_FILE_LOCK:
                path = self._path()
                data: dict[str, Any] = {}
                existente: Any = None
                with contextlib.suppress(Exception):
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                    # R-23 (espelho do lado DualSense): arquivo de OUTRO
                    # schema é descartado inteiro, não só a fatia deste
                    # registro — carregar a fila velha e recarimbá-la com
                    # a versão nova daria selo de válido a uma numeração que
                    # o `load` acabou de recusar.
                    if (
                        isinstance(loaded, dict)
                        and loaded.get("version") == CONTROLLERS_SCHEMA_VERSION
                    ):
                        data = loaded
                        existente = loaded
                # R-23: mesma dupla (versão decide, âncora só anota) do lado
                # DualSense — os dois escrevem os MESMOS dois campos.
                data["version"] = CONTROLLERS_SCHEMA_VERSION
                data["boot_id"] = _session_anchor()
                data[ORDER_FIELD] = merged_order_payload(
                    existente,
                    KIND_EXTERNAL,
                    {
                        key: rank
                        for key, rank in self._ordem.items()
                        if key not in self._volatile
                    },
                )
                payload = json.dumps(data, ensure_ascii=False)
                fd, tmp = tempfile.mkstemp(
                    dir=os.path.dirname(os.fspath(path)), prefix=".controllers_"
                )
                try:
                    os.write(fd, payload.encode())
                finally:
                    os.close(fd)
                os.replace(tmp, path)
                logger.debug("external_fila_salva", ordem=data[ORDER_FIELD])
        except Exception as exc:
            logger.debug("external_identity_save_falhou", err=str(exc))


class ExternalImuEnabler:
    """Liga a IMU do Nintendo Pro REAL na ADOÇÃO (GYRO-02, FASEADO — só USB).

    Contexto medido (estudo 2026-07-19-estudo-gyro-universal-vpad.md §Parte
    2): o Pro REAL (OUI :data:`NINTENDO_REAL_OUI`) declara os eixos da IMU
    (o hid-nintendo lê a calibração de fábrica) mas o sensor fica em STANDBY
    — accel/gyro travados em 0. O candidato de cura é o subcomando
    Enable-IMU (0x40, arg 0x01) — o MESMO território de subcomando que
    estourou o rate e derrubou o 8BitDo por Bluetooth (EXT-04). Por isso:

    - gatilho ESTRITO: ``uniq`` cuja OUI é EXATAMENTE
      :data:`NINTENDO_REAL_OUI` (nunca o 8BitDo, que mente VID/PID mas nunca
      o MAC) **E** ``bus == "usb"`` (fase 1 — BT fica bloqueado até haver
      medição de campo com o kernel-watch ``[JOYCON]`` limpo);
    - envio ÚNICO por adoção, com backoff: no máximo
      :data:`IMU_ENABLE_MAX_ATTEMPTS` tentativas, espaçadas por
      :data:`IMU_ENABLE_BACKOFF_SEC` — sucesso em qualquer tentativa encerra
      a série (nunca reenvia depois); esgotadas as tentativas, também para
      (nunca loop);
    - "adoção" = o ``uniq`` some do inventário (replug/disconnect) e volta —
      a poda ao fim de :meth:`tick` esquece as tentativas antigas, então o
      replug conta como adoção NOVA;
    - telemetria ``external_imu_enable_enviado`` (sucesso) ou
      ``external_imu_enable_falhou`` (fracasso) a cada tentativa; a escrita
      em si NUNCA propaga exceção (suppress + warn) — um `enable_imu` que
      falhe não pode derrubar o tick de LED que corre no mesmo poll.

    Instanciado e chamado de dentro de :class:`ExternalLedSync` — reusa o
    MESMO inventário do tick de LED (sem enumeração extra de /dev/input).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        #: uniq canônico → nº de tentativas já feitas NESTA adoção.
        self._attempts: dict[str, int] = {}
        #: uniq canônico → monotonic da última tentativa (para o backoff).
        self._last_attempt_at: dict[str, float] = {}
        #: uniq canônico → True se já teve UMA escrita bem-sucedida (nunca
        #: reenvia, mesmo que o inventário continue trazendo o device).
        self._done: set[str] = set()

    def tick(self, inventory: Iterable[dict[str, Any]], *, now: float | None = None) -> None:
        """Percorre ``inventory`` (o MESMO do tick de LED) e tenta o enable-IMU.

        Nunca levanta — enumeração/escrita ruins só deixam o Nintendo real
        no STANDBY de hoje (sem regressão em cima do LED/co-op).
        """
        from hefesto_dualsense4unix.core.external_leds import enable_imu

        agora = time.monotonic() if now is None else now
        vivos: set[str] = set()
        with self._lock:
            for entry in inventory:
                uniq = entry.get("uniq")
                if not isinstance(uniq, str) or not uniq:
                    continue
                key, persistable = ExternalIdentityRegistry._canonical(uniq)
                if not persistable:
                    continue  # sem MAC de verdade não há OUI para checar
                vivos.add(key)
                if key in self._done:
                    continue
                if key[:6] != NINTENDO_REAL_OUI:
                    continue
                bus = str(entry.get("bus") or "").lower()
                if bus != _IMU_ENABLE_ALLOWED_BUS:
                    continue  # FASE 1: BT bloqueado
                tentativas = self._attempts.get(key, 0)
                if tentativas >= IMU_ENABLE_MAX_ATTEMPTS:
                    continue  # esgotado nesta adoção — nunca loop
                ultima = self._last_attempt_at.get(key)
                if ultima is not None and (agora - ultima) < IMU_ENABLE_BACKOFF_SEC:
                    continue  # backoff entre tentativas
                hidraw = entry.get("hidraw")
                if not isinstance(hidraw, str) or not hidraw:
                    continue
                self._attempts[key] = tentativas + 1
                self._last_attempt_at[key] = agora
                ok = False
                with contextlib.suppress(Exception):
                    ok = bool(enable_imu(hidraw))
                if ok:
                    self._done.add(key)
                    logger.info(
                        "external_imu_enable_enviado",
                        uniq=key,
                        bus=bus,
                        tentativa=tentativas + 1,
                    )
                else:
                    logger.warning(
                        "external_imu_enable_falhou",
                        uniq=key,
                        bus=bus,
                        tentativa=tentativas + 1,
                    )
            # Poda: quem saiu do inventário esquece as tentativas — o
            # replug conta como ADOÇÃO nova (reenvia do zero).
            for key in list(self._attempts):
                if key not in vivos:
                    self._attempts.pop(key, None)
                    self._last_attempt_at.pop(key, None)
                    self._done.discard(key)


class ExternalLedSync:
    """Aplica o LED de posição dos externos no TICK do daemon (EXT-04, item 3).

    **CALADO desde 07/08/2026** (E0 da LUGAR-À-MESA-01, DECISÃO DELA): o
    interruptor de módulo :data:`EXTERNAL_PLAYER_LED_ENABLED` está ``False``, e
    com ele o tick faz ZERO escritas de LED — enquanto o externo não for
    jogador de verdade no jogo, o produto não acende número nele. **Tudo o que
    esta docstring descreve abaixo continua implementado, testado e intacto**,
    esperando a `E3`; é o gate que muda, e voltar é trocar aquela constante para
    ``True``. A ATRIBUIÇÃO de slot, a reconciliação do registro e o enable-IMU
    seguem rodando normalmente.

    ``tick()`` é BLOQUEANTE (enumeração evdev de 10-40 ms + sysfs) — o
    lifecycle a despacha via ``_run_blocking`` (executor), nunca no event
    loop. Disciplina de escrita, na ordem:

    a. cache por-VALOR: escreve SÓ quando o slot a exibir mudou para aquele
       dispositivo (a chave inclui o hidraw — replug ganha nó novo e o LED
       renasce naturalmente);
    b. rate-limit ``LED_MIN_INTERVAL_SEC`` entre escritas no MESMO
       dispositivo (mesmo quando o valor mudou);
    c. telemetria INFO ``external_led_written slot=N uniq=...`` a cada
       escrita EFETIVA (nunca mais silencioso).

    Falha de escrita (sem a regra udev 79) não entra no cache — o retry
    natural do tick fica limitado pelo rate-limit e custa só um
    ``os.path.exists`` False (nenhum tráfego HID).

    NUMA-03 (autoridade de exibição, sprint 2026-07-19): o tick consulta
    ``daemon.display_authority`` ('game'|'daemon'|'unknown'; atributo ausente
    = sem fiação = comportamento HEAD):

    - ``daemon``: antes do skip por-valor, RE-LÊ o padrão via classe LED
      (:func:`read_player_pattern` — memória do kernel, zero subcomando BT);
      padrão ≠ slot ⇒ repinta DENTRO do rate-limit de 2s + log
      ``external_led_repintado`` (o cache por-VALOR sozinho era o ponto cego
      S5: terceiro escrevia o LED e o daemon não repintava). **O rótulo
      "escritor estrangeiro" desta divergência CADUCOU — ver a nota datada no
      fim deste docstring;**
    - ``game``/``unknown``: device já cacheado NÃO é corrigido (externos não
      são disputados em jogo), mas device NOVO sem cache ainda recebe a
      numeração 1x (atribuição ≠ disputa — 8BitDo chegando mid-game não
      fica apagado);
    - queda para ``daemon``: re-arm (caches limpos) — o próximo tick
      reacende os slots do daemon.

    Simetria com o provider DualSense, agora no eixo CERTO (R-14): quem
    governa este LED é ``auto_numbers_enabled`` (numeração), não
    ``auto_player_colors`` (cor) — o que se escreve aqui é o NÚMERO do
    jogador. OFF ⇒ PARA DE AFIRMAR (zero escritas, sem apagar ativamente —
    simétrico ao provider, que deixa de emitir ``player_leds``) + cache
    limpo; OFF→ON reescreve os slots. A ATRIBUIÇÃO de slot roda sempre,
    antes do gate.

    .. warning::

       **NOTA DATADA — 07/08/2026 21h04: ``external_led_repintado`` NÃO
       significa "escritor estrangeiro".** Em **11 de 11** ocorrências do lado
       A de 07/08, o "intruso" que este tick acusou era **a nossa própria
       escrita anterior** — as repinturas são o daemon perseguindo o próprio
       eco.

       **O mecanismo:** :func:`read_player_pattern` lê o ``brightness`` da
       classe LED, que é memória do valor **PEDIDO**; o kernel o grava antes de
       tentar o hardware e nunca o reverte na falha. Uma escrita que morreu no
       rádio (``-110``) continua sendo relida como o número pedido. Logo esta
       comparação **não pode** distinguir firmware de terceiro: ela só enxerga
       escrita de **outro processo** pelo mesmo ``sysfs`` (a Steam pintando
       "player 1+3"), que é tudo o que ela sempre pôde enxergar.

       **Quem for contar repinturas em qualquer janela do journal precisa ler
       isto antes:** o número não mede disputa de LED. A medição, e a correção
       de uma linha que devolveria o nome ao log (S3), estão em
       ``docs/process/sprints/2026-08-07-A-LUZ-QUE-CUROU-01-calar-parou-o-bombardeio-e-voltar-tem-preco.md``,
       seções 2.1 a 2.3 e 6. GRAU: MEDIDO.
    """

    def __init__(self, daemon: Any, registry: ExternalIdentityRegistry) -> None:
        self._daemon = daemon
        self._registry = registry
        self._wire_presence_providers()
        #: (uniq-ou-vazio, hidraw) → último slot ESCRITO com sucesso.
        self._last_value: dict[tuple[str, str], int] = {}
        #: (uniq-ou-vazio, hidraw) → monotonic da última TENTATIVA de escrita.
        self._last_write_at: dict[tuple[str, str], float] = {}
        #: NUMA-03d: autoridade vista no tick anterior — detecta a queda
        #: `game|unknown → daemon` para re-armar os caches.
        self._last_authority: str | None = None
        #: GYRO-02: reusa o MESMO inventário deste tick para o enable-IMU do
        #: Nintendo Pro REAL (fase 1, USB) — sem enumeração extra.
        self._imu_enabler = ExternalImuEnabler()

    def _wire_presence_providers(self) -> None:
        """Casa os DOIS registros na EXIBIÇÃO — mão dupla de presença (NUM-01).

        A contagem "1..N entre quem está na mesa" é global, mas cada registro
        só enxerga a própria metade; este objeto é o ÚNICO que segura os dois
        (é ele que já lê o ``identity_registry`` para calcular o piso em
        :meth:`_ds_reserve`), então é aqui que a ponte é feita — nos dois
        sentidos, porque as duas metades precisam contar a outra.

        Não confundir com o provider de RESERVA que o lifecycle injeta
        (``set_external_reserve_provider``): aquele responde "que lugares da
        fila estão tomados" e por isso conta os ausentes, o que é certo para
        ATRIBUIR e errado para EXIBIR.

        Best-effort de ponta a ponta (``getattr`` + ``suppress``): daemon sem
        ``identity_registry`` (FakeController) ou registro de outra versão
        seguem sem a ponte, com a degradação conservadora documentada em
        :meth:`ExternalIdentityRegistry._ds_present_ranks`.
        """
        ds = getattr(self._daemon, "identity_registry", None)
        if ds is None:
            return
        externo = self._registry
        set_ext = getattr(ds, "set_external_presence_provider", None)
        if callable(set_ext):
            with contextlib.suppress(Exception):
                set_ext(externo.present_ranks)
        set_ds = getattr(externo, "set_dualsense_presence_provider", None)
        if callable(set_ds):
            with contextlib.suppress(Exception):
                set_ds(lambda: _present_ranks_of(ds))

    def _ds_reserve(self) -> int:
        """Piso dos externos: maior slot DualSense **ou** o alcance do co-op.

        R-13 item 2 (auditoria 23/07): considerar só os slots do registry
        deixava os externos colidirem com a numeração que o CO-OP acende.

        O co-op numera 1..N sobre os DualSense (primário = 1, secundários
        2..N) e escreve isso direto nos nós sysfs de player-LED. Se o piso dos
        externos ignora esse alcance, um Pro Nintendo ou 8BitDo pode receber um
        número que o co-op também está acendendo em outro controle — os "dois
        player 1 / dois player 2" que ela vê.

        Tomar o máximo dos dois empurra os externos para depois do último
        jogador de co-op. `player_count()` é leitura de um dict em memória
        (`1 + len(self._players)`), sem I/O — barato para o tick.

        R-24 (auditoria 25/07) — quem garante que este piso não seja 0 no
        primeiro tick: o `ControllerIdentityRegistry.sync_connected` passou a
        ATRIBUIR slot a todo DualSense conectado, e o poll loop o chama ANTES
        de agendar este tick no MESMO ciclo. Antes, a atribuição do lado
        DualSense era só LAZY (via provider de cor), o registro estava vazio
        no boot e o piso lido aqui era 0: o Pro Nintendo USB abocanhava o
        slot 1 e os dois DualSense nasciam 2 e 3 — "não existe Controle 1",
        medido no `controllers.json` dela. A ordem daquele laço é, portanto,
        parte do contrato desta função.

        NOTA: isto governa atribuições NOVAS. Lugares já persistidos em
        `controllers.json` só mudam com "Renumerar agora" — a fila é
        deliberadamente estável entre replugs (COR-01/D6) e agora também
        entre BOOTS (R-23).

        NUM-01: o que este piso devolve é o maior LUGAR NA FILA que os
        DualSense detêm — incluindo os desligados, e é isso mesmo: o piso
        serve para ATRIBUIR sem colidir, e um lugar reservado a quem está
        fora continua ocupado. Quem conta a EXIBIÇÃO é outro caminho
        (`_wire_presence_providers`), que só olha para quem está na mesa.
        """
        piso = 0
        registry = getattr(self._daemon, "identity_registry", None)
        snap = getattr(registry, "snapshot", None) if registry is not None else None
        if callable(snap):
            with contextlib.suppress(Exception):
                slots = snap()
                if isinstance(slots, dict) and slots:
                    piso = max(int(v) for v in slots.values())
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.daemon.subsystems.coop import get_coop_manager

            coop = get_coop_manager(self._daemon)
            # `player_count()` = 1 + secundários; só conta quando há SECUNDÁRIO
            # de verdade (com um DualSense só, o co-op não acende nada — R-13
            # item 4), senão o piso subiria para 1 sem ninguém usando o número.
            if coop is not None and coop.should_be_active():
                jogadores = int(coop.player_count())
                if jogadores >= 2:
                    piso = max(piso, jogadores)
        return piso

    @staticmethod
    def _identity_for(entry: dict[str, Any]) -> str:
        """Identidade com que ESTE tick numera o externo — FONTE ÚNICA (MODO-01).

        Delega a :func:`identity_for_entry`, que é a fonte única do PROJETO
        inteiro (tick, rota IPC e GUI). Existia como método porque os DOIS
        consumidores do inventário DENTRO do tick precisam enxergar a MESMA
        string: o ``sync_connected`` (quem está presente) e o laço de atribuição
        (quem recebe número). Eles divergiam — o ``sync_connected`` recebia só
        as entradas com ``uniq`` string, então um externo sem MAC nunca entrava
        no conjunto de CONECTADOS. Consequências: o "Renumerar agora" já o
        tratava como offline e o jogava para o fim da fila
        (``snapshot_connected``), e a poda de identidade volátil o derrubaria a
        cada tick. Hoje o tick resolve a identidade UMA vez por entrada (ver
        :meth:`tick`) e passa a MESMA lista para os dois.
        """
        return identity_for_entry(entry)

    def _display_authority(self) -> str:
        """Autoridade CORRENTE ('game'/'daemon'/'unknown'), com fail-safe.

        Atributo ausente no ``daemon`` (fake de teste, backend velho) ou
        valor fora da tabela ⇒ ``'unknown'`` — o MESMO default de
        ``Daemon.display_authority`` (lifecycle.py) antes de qualquer fiação.
        """
        valor = getattr(self._daemon, "display_authority", "unknown")
        return valor if valor in ("game", "daemon", "unknown") else "unknown"

    def _auto_numbers_enabled(self) -> bool:
        """Eixo NUMERAÇÃO do automático (R-14) — é o que rege o LED daqui.

        O LED que este tick escreve é ``apply_player_number``: o NÚMERO do
        jogador, não uma cor. Ele era gateado por ``auto_enabled``
        (``auto_player_colors``), então um clique de cor na GUI — que desliga
        aquele flag — congelava a numeração dos externos junto com a paleta
        dos DualSense (a queixa "dois player 1, dois player 2", com o
        ``fps.json`` dela salvo com ``auto_player_colors:false``). Agora lê
        ``identity_registry.auto_numbers_enabled``.

        Ausência do registro/atributo (FakeController, daemon sem fiação,
        registro de versão anterior) preserva o default ``True`` do próprio
        ``ControllerIdentityRegistry``: fail-safe, sem o registro nada muda.
        """
        registry = getattr(self._daemon, "identity_registry", None)
        if registry is None:
            return True
        return bool(getattr(registry, "auto_numbers_enabled", True))

    def tick(self, *, now: float | None = None) -> None:
        """Enumera, reconcilia o registro e aplica LEDs (com cache/rate-limit).

        NUMA-03.4: a disciplina de escrita agora é MODULADA pela autoridade de
        exibição corrente (ver docstring da classe) — sem fiação (autoridade
        ausente/``'unknown'``) o comportamento é o de HEAD, byte a byte.
        """
        from hefesto_dualsense4unix.core.evdev_reader import (
            discover_external_gamepads,
        )
        from hefesto_dualsense4unix.core.external_leds import (
            apply_player_number,
            hid_instance_for_hidraw,
            read_player_pattern,
        )

        try:
            inventory = discover_external_gamepads()
        except Exception as exc:  # nunca derruba o poll loop
            logger.debug("external_led_tick_enumeracao_falhou", err=str(exc))
            return
        agora = time.monotonic() if now is None else now
        reserve = self._ds_reserve()
        # CLONE-01: UMA resolução por entrada, reusada pelos dois consumidores
        # abaixo. Resolver duas vezes não seria só desperdício de um `realpath`:
        # o degrau `dev:<instância HID>` lê o sysfs VIVO, então um aparelho que
        # se despedisse ENTRE as duas chamadas entraria no `sync_connected` com
        # uma chave e receberia slot com outra — exatamente o buraco de
        # divergência que esta função existe para fechar.
        identidades = [identity_for_entry(entry) for entry in inventory]
        self._registry.sync_connected(identidades)

        # R-14 §1 (auditoria 23/07): ATRIBUIÇÃO antes de qualquer flag. O
        # `slot_for` morava lá embaixo, DEPOIS do early-return do automático —
        # com o auto desligado o externo não recebia sequer um número no
        # registro. Ele voltava a nascer sem slot no tick seguinte a religar o
        # flag, e enquanto isso o espaço de numeração global tinha um buraco
        # (o `used` do lado DualSense também consulta estas reservas). Numerar
        # é identidade; o flag governa APARÊNCIA (escrever no LED).
        atribuidos: list[tuple[str | None, str | None, int]] = []
        for entry, identity in zip(inventory, identidades, strict=True):
            uniq_raw = entry.get("uniq")
            uniq = uniq_raw if isinstance(uniq_raw, str) and uniq_raw else None
            hidraw_raw = entry.get("hidraw")
            hidraw = hidraw_raw if isinstance(hidraw_raw, str) and hidraw_raw else None
            slot = self._registry.slot_for(identity, reserve=reserve)
            if slot is None:
                continue
            atribuidos.append((uniq, hidraw, slot))

        # GYRO-02/fix MEDIUM cross-cutting (2026-07-20): enable-IMU do
        # Nintendo Pro REAL continua INDEPENDENTE dos flags do automático
        # e da autoridade de exibição (nunca levanta) — mas agora roda no
        # `finally`, DEPOIS do laço de repintura/numeração de LED abaixo (e
        # também depois do `return` antecipado do automático OFF), nunca
        # ANTES. `enable_imu` escreve CRU no hidraw (`os.write` sem timeout
        # próprio); rodando antes do laço, um travamento nessa escrita para
        # UM Nintendo Pro prendia o único worker do pool `hefesto-ext` sem
        # que a defesa de LED (NUMA-03.4) chegasse a rodar para NENHUM outro
        # externo conectado nesse tick. Com a ordem invertida, a repintura de
        # todo mundo já terminou antes de a escrita de IMU (a parte nova e
        # menos testada) arriscar travar.
        try:
            autoridade = self._display_authority()
            if autoridade == "daemon" and self._last_authority in ("game", "unknown"):
                # NUMA-03d: queda `game|unknown -> daemon` — re-arma os caches
                # para que ESTE tick reacenda os slots do daemon incondicional-
                # mente (não dá pra confiar no que ficou aceso sem disputa).
                self._last_value.clear()
                self._last_write_at.clear()
            self._last_authority = autoridade

            if not EXTERNAL_PLAYER_LED_ENABLED:
                # E0 da LUGAR-À-MESA-01 — DECISÃO DELA de 07/08/2026: "calar a
                # luz até a entrega existir". Enquanto o externo não for jogador
                # dentro do jogo, o Hefesto não acende número nele: ZERO
                # escritas, sem apagar (ver a docstring de
                # `EXTERNAL_PLAYER_LED_ENABLED`, que diz por que apagar também
                # seria afirmar). O caminho de volta é aquela constante.
                #
                # A leitura da constante mora AQUI, e não em `apply_player_number`,
                # de propósito: a capacidade tem de continuar viva e testável no
                # `core/external_leds.py` esperando a E3 — um "calar" que apagasse
                # o código custaria a leva inteira para desfazer.
                #
                # Cache limpo pelo mesmo motivo do gate de automático abaixo:
                # OFF→ON reescreve tudo no primeiro tick seguinte.
                if self._last_value or self._last_write_at:
                    self._last_value.clear()
                    self._last_write_at.clear()
                return

            if not self._auto_numbers_enabled():
                # NUMA-03c: automático OFF ⇒ PARA DE AFIRMAR (zero escritas,
                # sem apagar ativamente) + cache limpo — OFF->ON reescreve tudo
                # no primeiro tick seguinte (cache vazio = "nunca escrito").
                # R-14: o gate agora é o eixo NUMERAÇÃO; a ATRIBUIÇÃO de slot
                # já rodou acima e não é pulada por flag nenhum.
                if self._last_value or self._last_write_at:
                    self._last_value.clear()
                    self._last_write_at.clear()
                return

            vivos: set[tuple[str, str]] = set()
            for uniq, hidraw, slot in atribuidos:
                if hidraw is None:
                    continue
                key = (uniq or "", hidraw)
                vivos.add(key)
                ja_cacheado = key in self._last_value
                if autoridade != "daemon" and ja_cacheado:
                    # (b) game/unknown: device já numerado não é disputado — só
                    # o device NOVO (ainda sem cache) recebe o número 1x abaixo.
                    continue

                intruso: int | None = None
                if autoridade == "daemon" and ja_cacheado:
                    # (a)/(c) daemon: re-lê o padrão ANTES do skip por-valor,
                    # por CLASSE LED (zero subcomando BT), nunca por sonda.
                    # NOTA DATADA 07/08/2026: o que se detecta aqui NÃO é
                    # "escritor estrangeiro" — é divergência no sysfs, e em 11
                    # de 11 casos ela era a nossa própria escrita anterior.
                    # Ver a nota datada no docstring do ExternalLedSync.
                    hid_instance = hid_instance_for_hidraw(hidraw)
                    if hid_instance:
                        padrao = read_player_pattern(hid_instance)
                        if padrao is not None and padrao != slot:
                            intruso = padrao  # leitura falha (None) = skip, hoje

                if self._last_value.get(key) == slot and intruso is None:
                    continue  # (a) cache por-valor: nada mudou, nada a escrever
                if agora - self._last_write_at.get(key, float("-inf")) < (
                    LED_MIN_INTERVAL_SEC
                ):
                    continue  # (b) rate-limit por dispositivo (vale p/ o repaint)
                self._last_write_at[key] = agora
                escreveu = False
                with contextlib.suppress(Exception):
                    escreveu = bool(apply_player_number(hidraw, slot))
                if escreveu:
                    self._last_value[key] = slot
                    logger.info(
                        "external_led_written", slot=slot, uniq=uniq, hidraw=hidraw
                    )
                    if intruso is not None:
                        logger.info(
                            "external_led_repintado", uniq=uniq, intruso=intruso
                        )
            # Poda: devices que sumiram saem do cache — o replug (nó novo ou o
            # mesmo nome reusado) reescreve o LED naturalmente.
            for key in list(self._last_value):
                if key not in vivos:
                    self._last_value.pop(key, None)
                    self._last_write_at.pop(key, None)
        finally:
            with contextlib.suppress(Exception):
                self._imu_enabler.tick(inventory, now=agora)


__all__ = [
    "EXTERNAL_IDENTITY_FIELD",
    "EXTERNAL_PLAYER_LED_ENABLED",
    "IMU_ENABLE_BACKOFF_SEC",
    "IMU_ENABLE_MAX_ATTEMPTS",
    "LED_MIN_INTERVAL_SEC",
    "NINTENDO_REAL_OUI",
    "VOLATILE_ABSENCE_LIMIT",
    "ExternalIdentityRegistry",
    "ExternalImuEnabler",
    "ExternalLedSync",
    "identity_for_entry",
]
