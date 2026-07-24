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

1. :class:`ExternalIdentityRegistry` — slots ESTÁVEIS por ``uniq`` (MAC),
   análogo ao ``ControllerIdentityRegistry`` dos DualSense: menor slot livre
   ACIMA da reserva dos DualSense, slot RESERVADO no disconnect (replug
   recupera o número), persistência POR BOOT no MESMO ``controllers.json``
   (namespace separado ``externals`` — cada registro preserva o namespace do
   outro no read-modify-write, serializado pelo ``CONTROLLERS_FILE_LOCK``
   COMPARTILHADO de ``identity.py`` — NUMA-04, fecha o lost-update entre os
   dois escritores independentes). Cross-check UNILATERAL no ``load``:
   colisão de SLOT entre ``slots``/``externals`` no mesmo arquivo (corrupção
   por lost-update pretérito) é resolvida a favor do DualSense — a entrada
   externa colidente é DROPADA, nunca realocada.
2. :class:`ExternalLedSync` — o LED é aplicado pelo TICK do daemon (poll
   lento ~2s do lifecycle), com cache por-VALOR (escreve SÓ em mudança) +
   rate-limit de ``LED_MIN_INTERVAL_SEC`` por dispositivo + telemetria INFO
   ``external_led_written`` (antes era silencioso via contextlib.suppress).
3. A leitura IPC (`_external_inventory`) vira PURA: consulta ``peek`` (nunca
   atribui, nunca escreve LED).

Hermeticidade: a fiação do daemon (`_wire_external_registry`) só liga isto
quando o ``identity_registry`` dos DualSense existe (backend real) — com o
FakeController nada de /dev/input é enumerado e nenhum LED é tocado.

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

from hefesto_dualsense4unix.daemon.subsystems.identity import CONTROLLERS_FILE_LOCK
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Iterable

logger = get_logger(__name__)

#: Mesmo arquivo do registro dos DualSense — namespace separado (``externals``).
_CONTROLLERS_FILE = "controllers.json"

#: MAC "de verdade" (mesma regra estrita do registro DualSense): 12 hex, com
#: ou sem ``:``/``-``. Qualquer outra key é identidade VOLÁTIL de sessão.
_MAC_RE = re.compile(
    r"^(?:[0-9a-fA-F]{12}|(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2})$"
)

#: Rate-limit mínimo entre escritas de LED no MESMO dispositivo (EXT-04c).
#: O hid-nintendo tem enforcement de taxa de subcomando BT
#: (``joycon_enforce_subcmd_rate``) e firmware clone estoura fácil — 2s por
#: device é ordens de magnitude abaixo do bombardeio de 4-5 nós por poll que
#: matou o 8BitDo ao vivo.
LED_MIN_INTERVAL_SEC = 2.0

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
    """boot_id do kernel (None se ilegível) — sessão morta se difere no load."""
    try:
        with open("/proc/sys/kernel/random/boot_id", encoding="utf-8") as fh:
            value = fh.read().strip()
        return value or None
    except OSError:
        return None


class ExternalIdentityRegistry:
    """``uniq`` de externo → slot GLOBAL de co-op, com reserva de sessão.

    Espelha o desenho do ``ControllerIdentityRegistry`` (D1/D2/D9), com duas
    diferenças de domínio:

    - o menor slot livre respeita a RESERVA dos DualSense (``reserve``):
      externos continuam a contagem (1º externo = reserva+1) — mas um slot já
      atribuído NUNCA é renumerado quando a reserva muda depois (estabilidade
      vence: é o fim do "LED muda sozinho");
    - sem expiração por sessão-esvaziou: a persistência é POR BOOT (o load
      ignora arquivo de outro boot) e o disconnect apenas RESERVA o slot.

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
        self._slots: dict[str, int] = {}
        self._volatile: set[str] = set()
        self._connected: set[str] = set()
        self._dirty = False
        self._loaded = False

    @staticmethod
    def _canonical(uniq: str) -> tuple[str, bool]:
        """``(key, persistível)`` — MAC 12-hex canônico ou key volátil crua."""
        value = uniq.strip()
        if _MAC_RE.match(value):
            return value.lower().replace(":", "").replace("-", ""), True
        return value, False

    def slot_for(
        self, uniq: str | None, *, reserve: int = 0, assign: bool = True
    ) -> int | None:
        """Slot do externo ``uniq``; atribui o menor livre > ``reserve`` na 1ª vez.

        ``assign=False`` é leitura pura (não atribui, não marca conectado) —
        é o modo da rota IPC. SEM I/O de disco (a persistência fica com
        ``sync_connected``, no tick lento).
        """
        if not uniq or not isinstance(uniq, str):
            return None
        key, persistable = self._canonical(uniq)
        if not key:
            return None
        with self._lock:
            slot = self._slots.get(key)
            if slot is not None:
                if assign:
                    self._connected.add(key)
                return slot
            if not assign:
                return None
            used = set(self._slots.values())
            slot = max(1, int(reserve) + 1)
            while slot in used:
                slot += 1
            self._slots[key] = slot
            if persistable:
                self._dirty = True
            else:
                self._volatile.add(key)
            self._connected.add(key)
            logger.info(
                "external_slot_atribuido",
                uniq=key,
                slot=slot,
                reserva_dualsense=reserve,
                volatil=not persistable,
            )
            return slot

    def peek(self, uniq: str | None) -> int | None:
        """Leitura PURA do slot (rota IPC): nunca atribui, nunca persiste."""
        return self.slot_for(uniq, assign=False)

    def sync_connected(self, uniqs: Iterable[str]) -> None:
        """Reconcilia com os uniqs presentes AGORA (tick ~2s) e persiste.

        Quem saiu vira RESERVA (slot preso ao uniq — replug recupera o
        número). Diferente do registro DualSense, não há expiração por
        sessão-esvaziou: um externo BT que dorme não pode perder o número
        (era exatamente o sintoma). ÚNICO ponto de escrita em disco fora do
        ``load()``.
        """
        vivos: set[str] = set()
        for uniq in uniqs:
            if not uniq or not isinstance(uniq, str):
                continue
            key, _ = self._canonical(uniq)
            vivos.add(key)
        with self._lock:
            self._connected = vivos
            if self._dirty:
                self._save_locked()
                self._dirty = False

    def snapshot(self) -> dict[str, int]:
        """Cópia do mapa key→slot (conectados + reservas). Leitura pura."""
        with self._lock:
            return dict(self._slots)

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
        """Reatribui slots conforme ``mapping`` (``identity.renumber``, ONDA-U/U2).

        Espelho do ``ControllerIdentityRegistry.compact`` — mesma
        justificativa (reescrita EXPLÍCITA, gate de sessão vazia é do
        CHAMADOR; só troca chaves já presentes NESTE registro). O
        ``ExternalLedSync.tick()`` seguinte repinta o LED sozinho: o cache
        por-valor (``_last_value``) compara contra ``slot_for``, que passa a
        devolver o número novo já aqui — sem precisar limpar cache.
        """
        with self._lock:
            changed = False
            for key, new_slot in mapping.items():
                if key in self._slots and self._slots[key] != new_slot:
                    self._slots[key] = new_slot
                    changed = True
            if changed:
                self._dirty = True
                self._save_locked()
                self._dirty = False

    # -- persistência (namespace ``externals`` do controllers.json) -------

    def load(self) -> None:
        """Carrega o namespace ``externals`` — só se do MESMO boot da máquina.

        NUMA-04: a leitura roda sob ``CONTROLLERS_FILE_LOCK`` (compartilhado
        com ``identity.py``). Cross-check UNILATERAL contra o namespace
        ``slots`` do MESMO arquivo: um SLOT que aparece nos DOIS namespaces
        só pode ter chegado lá por um lost-update pretérito (o bug que o
        lock agora fecha) — o DualSense VENCE, a entrada externa colidente é
        DROPADA (nunca realocada, nunca poda o lado DualSense) + log WARN
        ``controllers_json_colisao_descartada``; o externo ganha slot novo
        na próxima atribuição, ainda com a sessão vazia (D2 permite).
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
            boot_id = _read_boot_id()
            if not isinstance(data, dict):
                return
            if not boot_id or data.get("boot_id") != boot_id:
                return
            externals = data.get("externals")
            if not isinstance(externals, dict):
                return
            slots_dualsense = data.get("slots")
            slots_em_uso_pelo_dualsense: set[int] = set()
            if isinstance(slots_dualsense, dict):
                for raw_slot_ds in slots_dualsense.values():
                    if (
                        isinstance(raw_slot_ds, int)
                        and not isinstance(raw_slot_ds, bool)
                        and raw_slot_ds >= 1
                    ):
                        slots_em_uso_pelo_dualsense.add(raw_slot_ds)
            usados: set[int] = set()
            for raw_key, raw_slot in externals.items():
                if not isinstance(raw_key, str) or not isinstance(raw_slot, int):
                    continue
                if isinstance(raw_slot, bool) or raw_slot < 1:
                    continue
                if raw_slot in slots_em_uso_pelo_dualsense:
                    logger.warning(
                        "controllers_json_colisao_descartada",
                        slot=raw_slot,
                        externo=raw_key,
                    )
                    continue
                key, persistable = self._canonical(raw_key)
                if not persistable:
                    continue
                if key in self._slots or raw_slot in usados:
                    continue
                self._slots[key] = raw_slot
                usados.add(raw_slot)
            if self._slots:
                logger.info(
                    "external_slots_restaurados", slots=dict(self._slots)
                )

    @staticmethod
    def _path() -> Path:
        """Path do ``controllers.json`` — import LAZY (monkeypatch dos testes)."""
        from hefesto_dualsense4unix.utils.xdg_paths import config_dir

        return config_dir(ensure=True) / _CONTROLLERS_FILE

    def _save_locked(self) -> None:
        """Read-modify-write atômico: grava ``externals`` preservando o resto.

        O ``ControllerIdentityRegistry`` (DualSense) grava ``boot_id`` +
        ``slots`` no mesmo arquivo — cada lado preserva o namespace do outro.
        Nunca propaga exceção: perder um save = renumerar no próximo boot.
        NUMA-04: o span INTEIRO read→``os.replace`` roda sob o
        ``CONTROLLERS_FILE_LOCK`` de ``identity.py`` (importado, nunca um
        lock novo) — fecha o lost-update com o save do lado DualSense.
        """
        try:
            with CONTROLLERS_FILE_LOCK:
                path = self._path()
                data: dict[str, Any] = {}
                with contextlib.suppress(Exception):
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        data = loaded
                data["boot_id"] = _read_boot_id()
                data["externals"] = {
                    key: slot
                    for key, slot in self._slots.items()
                    if key not in self._volatile
                }
                payload = json.dumps(data, ensure_ascii=False)
                fd, tmp = tempfile.mkstemp(
                    dir=os.path.dirname(os.fspath(path)), prefix=".controllers_"
                )
                try:
                    os.write(fd, payload.encode())
                finally:
                    os.close(fd)
                os.replace(tmp, path)
                logger.debug(
                    "external_slots_salvos", externals=data["externals"]
                )
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

    - ``daemon``: antes do skip por-valor, RE-LÊ o padrão físico via classe
      (:func:`read_player_pattern` — memória do kernel, zero subcomando BT);
      padrão ≠ slot = escritor estrangeiro ⇒ repinta DENTRO do rate-limit de
      2s + log ``external_led_repintado`` (o cache por-VALOR sozinho era o
      ponto cego S5: terceiro escrevia o LED e o daemon não repintava);
    - ``game``/``unknown``: device já cacheado NÃO é corrigido (externos não
      são disputados em jogo), mas device NOVO sem cache ainda recebe a
      numeração 1x (atribuição ≠ disputa — 8BitDo chegando mid-game não
      fica apagado);
    - queda para ``daemon``: re-arm (caches limpos) — o próximo tick
      reacende os slots do daemon.

    Simetria ``auto_player_colors`` (o MESMO flag do provider DualSense):
    OFF ⇒ PARA DE AFIRMAR (zero escritas, sem apagar ativamente — simétrico
    ao provider que devolve None) + cache limpo; OFF→ON reescreve os slots.
    """

    def __init__(self, daemon: Any, registry: ExternalIdentityRegistry) -> None:
        self._daemon = daemon
        self._registry = registry
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

        NOTA: isto governa atribuições NOVAS. Números já persistidos em
        `controllers.json` só mudam com "Renumerar agora" — a numeração é
        deliberadamente estável entre replugs (COR-01/D6).
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

    def _display_authority(self) -> str:
        """Autoridade CORRENTE ('game'/'daemon'/'unknown'), com fail-safe.

        Atributo ausente no ``daemon`` (fake de teste, backend velho) ou
        valor fora da tabela ⇒ ``'unknown'`` — o MESMO default de
        ``Daemon.display_authority`` (lifecycle.py) antes de qualquer fiação.
        """
        valor = getattr(self._daemon, "display_authority", "unknown")
        return valor if valor in ("game", "daemon", "unknown") else "unknown"

    def _auto_player_colors_enabled(self) -> bool:
        """Espelha o MESMO flag do provider DualSense (NUMA-03c).

        ``identity_registry.auto_enabled`` — ausência do registro/atributo
        (FakeController, daemon sem fiação) preserva o default ``True`` do
        próprio ``ControllerIdentityRegistry`` (identity.py:152): fail-safe,
        sem o registro nada muda.
        """
        registry = getattr(self._daemon, "identity_registry", None)
        if registry is None:
            return True
        return bool(getattr(registry, "auto_enabled", True))

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
        self._registry.sync_connected(
            e["uniq"] for e in inventory if isinstance(e.get("uniq"), str)
        )

        # GYRO-02/fix MEDIUM cross-cutting (2026-07-20): enable-IMU do
        # Nintendo Pro REAL continua INDEPENDENTE do flag `auto_player_colors`
        # e da autoridade de exibição (nunca levanta) — mas agora roda no
        # `finally`, DEPOIS do laço de repintura/numeração de LED abaixo (e
        # também depois do `return` antecipado do auto-colors OFF), nunca
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

            if not self._auto_player_colors_enabled():
                # NUMA-03c: automático OFF ⇒ PARA DE AFIRMAR (zero escritas,
                # sem apagar ativamente) + cache limpo — OFF->ON reescreve tudo
                # no primeiro tick seguinte (cache vazio = "nunca escrito").
                if self._last_value or self._last_write_at:
                    self._last_value.clear()
                    self._last_write_at.clear()
                return

            vivos: set[tuple[str, str]] = set()
            for entry in inventory:
                uniq = entry.get("uniq")
                uniq = uniq if isinstance(uniq, str) and uniq else None
                hidraw = entry.get("hidraw")
                # Identidade volátil (sem MAC): o evdev_path vale pela sessão.
                identity = uniq or f"path:{entry.get('evdev_path')}"
                slot = self._registry.slot_for(identity, reserve=reserve)
                if slot is None or not isinstance(hidraw, str) or not hidraw:
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
                    # (a)/(c) daemon: re-lê o padrão físico ANTES do skip por-
                    # valor — escritor estrangeiro é detectado por CLASSE LED
                    # (zero subcomando BT), nunca por sonda.
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
    "IMU_ENABLE_BACKOFF_SEC",
    "IMU_ENABLE_MAX_ATTEMPTS",
    "LED_MIN_INTERVAL_SEC",
    "NINTENDO_REAL_OUI",
    "ExternalIdentityRegistry",
    "ExternalImuEnabler",
    "ExternalLedSync",
]
