"""Registro de identidade MAC→slot de SESSÃO (COR-01, sprint cores-e-led).

O "Controle N" que a usuária vê (rótulos, cor automática da lightbar, LED do
número do controle) era a POSIÇÃO no dict de handles do backend (+1) — replug
reinsere no fim e o número embaralhava. Este registro dá a cada DualSense um
slot ESTÁVEL DE SESSÃO, keyed pelo MAC normalizado (12 hex — o mesmo
``norm_mac`` do backend, estável entre USB e BT):

- 1ª aparição de um MAC → MENOR slot livre (1..N), atribuição LAZY na
  primeira consulta (``slot_for``) — é isto que faz a cor automática nascer
  certa no MESMO tick de hotplug em que o backend abre o handle (D1);
- desconectar RESERVA o slot ao MAC dentro da sessão — replug recupera o
  mesmo número (D2). Sem roubo LRU (cortado: YAGNI);
- quando NENHUM controle está conectado, a sessão esvaziou: as reservas
  expiram e a próxima sessão renumera do 1 (D2 — o PS5 numera por sessão).
  Quem observa o esvaziamento é ``sync_connected`` (tick lento ~2s do
  daemon), nunca o caminho quente por evento;
- o vpad (MAC forjado ``02:fe:...``) NUNCA ganha slot (D9) — o filtro
  existe aqui além do filtro de enumeração do backend, porque outros
  chamadores (describe/co-op) também consultam;
- key sem MAC 12-hex (fallback ``path:...`` de firmware sem serial) ganha
  slot VOLÁTIL: vale na sessão, nunca é persistido (D9 — path muda entre
  boots);
- DualSense-only (D10) é garantido pelo CHAMADOR por construção: os uniqs
  que chegam aqui vêm dos handles físicos do backend (a enumeração filtra
  por VID/PID da Sony e descarta hidraw virtual). O registro não conhece
  hardware — só strings.

Separação D3 (Refutado 2 do sprint): este slot é EXIBIÇÃO/LED. O índice de
alocação do vpad do co-op (``_next_player_index`` + ``player=1`` do
primário) fica intacto — slot repetido no MAC do vpad uhid mataria o probe
com ``-EEXIST`` e degradaria o co-op em silêncio.

Persistência (``controllers.json`` no config do app, escrita atômica
mkstemp+os.replace — padrão ``utils/session.py``): cobre APENAS o restart do
daemon com controles ainda presentes. O arquivo carrega o ``boot_id`` da
máquina: um arquivo de outro boot é sessão MORTA e é ignorado no load (a
próxima sessão renumera do 1, D2). A expiração em runtime regrava o arquivo
vazio. O ``config_dir`` é importado LAZY dentro das funções de I/O — preserva
o ponto de monkeypatch dos testes (``xdg_paths.config_dir``), padrão
``save_active_marker``.

Config do automático (COR-03): o registro também guarda o estado vigente do
toggle ``auto_player_colors`` e do brilho do perfil ativo (D11), configurados
pelo ``ProfileManager.apply`` a cada ativação e consultados pelo provider de
cor injetado no backend (``make_auto_output_provider``).
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from hefesto_dualsense4unix.core.backend_pydualsense import _DesiredOutput

logger = get_logger(__name__)

#: Arquivo de persistência (no ``config_dir`` do app — padrão ``session.json``).
_CONTROLLERS_FILE = "controllers.json"

#: MAC "de verdade": 12 dígitos hex, com ou sem separadores ``:``/``-``.
#: Mais estrito que o ``norm_mac`` do backend de propósito: um PATH exótico
#: pode conter 12 chars hex espalhados e viraria um pseudo-MAC persistível.
_MAC_RE = re.compile(
    r"^(?:[0-9a-fA-F]{12}|(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2})$"
)

#: Prefixo (canônico, 12-hex) dos MACs forjados dos vpads uhid — D9.
_VPAD_MAC_PREFIX = "02fe"


def _read_boot_id() -> str | None:
    """boot_id do kernel — identifica ESTE boot da máquina (None se ilegível).

    Um ``controllers.json`` gravado noutro boot é sessão morta: os controles
    foram desligados junto com a máquina, e restaurar os slots antigos
    quebraria o D2 ("sessão nova renumera do 1"). Monkeypatchável nos testes.
    """
    try:
        with open("/proc/sys/kernel/random/boot_id", encoding="utf-8") as fh:
            value = fh.read().strip()
        return value or None
    except OSError:
        return None


class ControllerIdentityRegistry:
    """MAC normalizado → slot de exibição (1..N), com reserva de SESSÃO (D2).

    Thread-safe (RLock próprio): o provider de cor consulta ``slot_for`` sob
    o ``_io_lock`` do backend (thread do executor) enquanto ``sync_connected``
    roda no event loop. Nenhum método faz I/O de disco EXCETO ``load()``
    (chamado uma vez na fiação do daemon, fora do caminho quente) e o save
    interno do ``sync_connected`` (tick lento ~2s, só quando algo mudou) —
    ``slot_for`` apenas marca o estado como sujo (o provider roda sob o
    ``_io_lock`` do backend e DEVE ser barato, sem I/O).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        #: key canônica (MAC 12-hex, ou a key volátil crua) → slot. Contém
        #: conectados E reservados — a reserva É a permanência aqui (D2).
        self._slots: dict[str, int] = {}
        #: keys de slots VOLÁTEIS (sem MAC 12-hex) — nunca persistidas (D9).
        self._volatile: set[str] = set()
        #: keys atualmente conectadas (subset das que reportaram presença).
        self._connected: set[str] = set()
        #: True depois de observar ≥1 controle conectado NESTA execução —
        #: arma a expiração por esvaziamento. Sem isto, o sync vazio do boot
        #: (antes de o backend abrir os handles) expiraria as entradas
        #: recém-carregadas do disco e mataria o caso restart-com-controles.
        self._saw_connected = False
        #: mapa mudou desde o último save (o sync persiste no tick lento).
        self._dirty = False
        self._loaded = False
        #: vpads já logados (evita spam — o provider consulta a cada reassert).
        self._vpad_logged: set[str] = set()
        #: provider OPCIONAL dos slots já reservados pelos EXTERNOS (EXT-04):
        #: o espaço de numeração é ÚNICO entre DualSense e externos, então a
        #: atribuição une essas reservas ao ``used`` — um DualSense que entra
        #: DEPOIS de um externo numerado pula o slot dele. None (não fiado /
        #: FakeController) = comportamento histórico, hermético.
        self._extra_reserved: Callable[[], set[int]] | None = None
        # -- estado do automático (COR-03, configurado pelo ProfileManager) --
        self._auto_enabled = True
        self._auto_brightness = 1.0

    # ------------------------------------------------------------------
    # Config do automático (COR-03 / D11)
    # ------------------------------------------------------------------

    def configure(
        self,
        *,
        enabled: bool | None = None,
        brightness: float | None = None,
    ) -> None:
        """Configura o estado vigente do automático (chamado na ativação de perfil).

        ``enabled`` = ``profile.leds.auto_player_colors``; ``brightness`` =
        ``profile.leds.lightbar_brightness`` (a cor automática respeita o
        brilho do perfil — D11). ``None`` preserva o valor atual (chamada
        parcial). Perfil SEM seção ``leds`` no JSON valida com os defaults do
        schema (``LedsConfig()``) → auto ON e brilho 1.0 — decisão documentada
        do COR-03: sem seção = sem opinião = o default do campo (True).
        """
        with self._lock:
            if enabled is not None:
                self._auto_enabled = bool(enabled)
            if brightness is not None:
                self._auto_brightness = max(0.0, min(1.0, float(brightness)))

    @property
    def auto_enabled(self) -> bool:
        """True quando as cores automáticas por controle estão ligadas."""
        with self._lock:
            return self._auto_enabled

    @property
    def auto_brightness(self) -> float:
        """Brilho vigente [0.0, 1.0] que escala a cor automática (D11)."""
        with self._lock:
            return self._auto_brightness

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @staticmethod
    def _canonical(uniq: str) -> tuple[str, bool]:
        """Devolve ``(key, persistível)`` — MAC 12-hex canônico ou key volátil.

        Persistível = a string INTEIRA parece um MAC (12 hex, com ou sem
        ``:``/``-``). Qualquer outra coisa (``path:...``, node de device) é
        identidade VOLÁTIL de sessão — vale para numerar, nunca para gravar
        em disco (D9: path muda entre boots).
        """
        value = uniq.strip()
        if _MAC_RE.match(value):
            return value.lower().replace(":", "").replace("-", ""), True
        return value, False

    def set_external_reserve_provider(
        self, provider: Callable[[], set[int]] | None
    ) -> None:
        """Injeta o provider dos slots já detidos pelos EXTERNOS (EXT-04).

        A numeração global é um espaço ÚNICO: os externos já leem o piso dos
        DualSense (``reserve``) ao numerar; este provider fecha o laço no
        sentido inverso — a atribuição de um DualSense NOVO une os slots
        reservados pelos externos ao ``used``, para não colidir com um externo
        que numerou antes. Fiado por ``lifecycle._wire_external_registry`` só
        no backend real; ``None`` (FakeController) preserva o comportamento
        histórico. NÃO renumera quem já tem slot — só evita colisões NOVAS.
        """
        with self._lock:
            self._extra_reserved = provider

    def slot_for(self, uniq: str | None, *, assign: bool = True) -> int | None:
        """Slot do controle ``uniq`` — atribui o MENOR livre na 1ª consulta.

        LAZY por decisão (D1): a primeira consulta de um uniq válido (feita
        pelo provider de cor dentro do reconcile do backend, ou por quem
        rotula) é o que atribui o slot — a cor/número nascem certos no MESMO
        tick de hotplug. ``assign=False`` só consulta (leitura pura: não
        atribui, não marca conectado).

        Guardas: ``None``/vazio → None; MAC de vpad (``02:fe:...``) → None
        com log (D9 — o vpad jamais é "Controle N"). SEM I/O de disco — o
        provider roda sob o ``_io_lock`` do backend; a persistência fica com
        o ``sync_connected`` (tick lento).
        """
        if not uniq or not isinstance(uniq, str):
            return None
        key, persistable = self._canonical(uniq)
        if not key:
            return None
        if key.startswith(_VPAD_MAC_PREFIX) and persistable:
            with self._lock:
                if key not in self._vpad_logged:
                    self._vpad_logged.add(key)
                    logger.warning("identity_slot_vpad_ignorado", uniq=key)
            return None
        with self._lock:
            slot = self._slots.get(key)
            if slot is not None:
                if assign:
                    self._connected.add(key)
                    self._saw_connected = True
                return slot
            if not assign:
                return None
            used = set(self._slots.values())
            prov = self._extra_reserved
            if prov is not None:
                # EXT-04: numeração global ÚNICA — pula os slots que os
                # externos já detêm (um DualSense que conecta DEPOIS de um
                # externo numerado não pode reivindicar o slot dele).
                with contextlib.suppress(Exception):
                    used |= {int(s) for s in prov()}
            slot = 1
            while slot in used:
                slot += 1
            self._slots[key] = slot
            if persistable:
                self._dirty = True
            else:
                self._volatile.add(key)
            self._connected.add(key)
            self._saw_connected = True
            logger.info(
                "identity_slot_atribuido",
                uniq=key,
                slot=slot,
                volatil=not persistable,
            )
            return slot

    def mark_disconnected(self, uniq: str | None) -> None:
        """Marca ``uniq`` desconectado — o slot fica RESERVADO ao MAC (D2).

        Replug dentro da sessão recupera o mesmo número. A EXPIRAÇÃO (sessão
        esvaziou → renumera do 1) não acontece aqui: é o ``sync_connected``
        (tick lento) quem observa o conjunto — assim um flap rápido de BT
        entre dois ticks nem chega a derrubar a reserva.
        """
        if not uniq or not isinstance(uniq, str):
            return
        key, _ = self._canonical(uniq)
        with self._lock:
            self._connected.discard(key)

    def sync_connected(self, uniqs: Iterable[str]) -> None:
        """Reconcilia com o conjunto de uniqs CONECTADOS agora (tick ~2s).

        - quem saiu do conjunto vira RESERVA (slot preso ao MAC — D2);
        - conjunto vazio APÓS a sessão ter tido alguém conectado = sessão
          esvaziou → TODAS as reservas (e voláteis) expiram e o arquivo é
          regravado vazio — a próxima sessão renumera do 1 (D2);
        - persiste (atômico) quando o mapa mudou desde o último save. É o
          ÚNICO ponto de escrita em disco fora do ``load()`` — nunca no
          caminho quente por evento.
        """
        vivos: set[str] = set()
        for uniq in uniqs:
            if not uniq or not isinstance(uniq, str):
                continue
            key, persistable = self._canonical(uniq)
            if persistable and key.startswith(_VPAD_MAC_PREFIX):
                continue  # D9: vpad não é controle
            vivos.add(key)
        with self._lock:
            self._connected = {k for k in self._connected if k in vivos} | vivos
            if vivos:
                self._saw_connected = True
            elif self._saw_connected:
                # Transição observada para ZERO conectados: sessão esvaziou.
                if self._slots:
                    logger.info(
                        "identity_sessao_esvaziou_reservas_expiradas",
                        slots=dict(self._slots),
                    )
                    self._slots.clear()
                    self._volatile.clear()
                    self._dirty = True
                self._saw_connected = False
            if self._dirty:
                self._save_locked()
                self._dirty = False

    def snapshot(self) -> dict[str, int]:
        """Cópia do mapa key→slot atual (conectados + reservas). Leitura pura."""
        with self._lock:
            return dict(self._slots)

    # ------------------------------------------------------------------
    # Persistência (restart do daemon com controles presentes)
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Carrega ``controllers.json`` — só entradas do MESMO boot da máquina.

        Chamado UMA vez na fiação do daemon (fora do caminho quente).
        Entradas carregadas entram como RESERVAS: o primeiro reconcile com
        controles presentes as reivindica (restart do daemon preserva os
        números); um boot novo da máquina (boot_id difere) é sessão morta e
        o arquivo é ignorado. Idempotente; nunca propaga exceção.
        """
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            try:
                data = json.loads(self._path().read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                return
            except Exception as exc:  # defensivo — load jamais derruba o boot
                logger.debug("identity_load_falhou", err=str(exc))
                return
            boot_id = _read_boot_id()
            if not isinstance(data, dict):
                return
            if not boot_id or data.get("boot_id") != boot_id:
                logger.debug(
                    "identity_arquivo_de_outro_boot_ignorado",
                    arquivo_boot=data.get("boot_id"),
                )
                return
            slots = data.get("slots")
            if not isinstance(slots, dict):
                return
            usados: set[int] = set()
            for raw_key, raw_slot in slots.items():
                if not isinstance(raw_key, str) or not isinstance(raw_slot, int):
                    continue
                if isinstance(raw_slot, bool) or raw_slot < 1:
                    continue
                key, persistable = self._canonical(raw_key)
                if not persistable or key.startswith(_VPAD_MAC_PREFIX):
                    continue  # voláteis/vpad jamais deveriam estar no disco
                if key in self._slots or raw_slot in usados:
                    continue  # arquivo degenerado: 1º ganha, sem duplicatas
                self._slots[key] = raw_slot
                usados.add(raw_slot)
            if self._slots:
                logger.info("identity_slots_restaurados", slots=dict(self._slots))

    @staticmethod
    def _path() -> Path:
        """Path do ``controllers.json`` — import LAZY do ``config_dir``.

        Lazy para preservar o ponto de monkeypatch dos testes
        (``monkeypatch.setattr(xdg_paths, "config_dir", ...)``), o mesmo
        padrão de ``utils.session.save_active_marker``.
        """
        from hefesto_dualsense4unix.utils.xdg_paths import config_dir

        return config_dir(ensure=True) / _CONTROLLERS_FILE

    def _save_locked(self) -> None:
        """Grava o mapa persistível (atômico: mkstemp + os.replace). Sob lock.

        Só entradas com MAC 12-hex (voláteis ficam de fora — D9). Nunca
        propaga exceção (paridade com ``utils.session``): perder um save
        significa, no pior caso, renumerar no próximo boot — inócuo.

        EXT-04: o arquivo é COMPARTILHADO com o registro dos externos
        (namespace ``externals`` — ``subsystems/external_identity.py``);
        read-modify-write para preservar o namespace do outro lado.
        """
        try:
            path = self._path()
            payload: dict[str, Any] = {}
            with contextlib.suppress(Exception):
                existente = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(existente, dict) and isinstance(
                    existente.get("externals"), dict
                ):
                    payload["externals"] = existente["externals"]
            payload["boot_id"] = _read_boot_id()
            payload["slots"] = {
                key: slot
                for key, slot in self._slots.items()
                if key not in self._volatile
            }
            data = json.dumps(payload, ensure_ascii=False)
            fd, tmp = tempfile.mkstemp(
                dir=os.path.dirname(os.fspath(path)), prefix=".controllers_"
            )
            try:
                os.write(fd, data.encode())
            finally:
                os.close(fd)
            os.replace(tmp, path)
            logger.debug("identity_slots_salvos", slots=payload["slots"])
        except Exception as exc:
            logger.debug("identity_save_falhou", err=str(exc))


def make_auto_output_provider(
    registry: ControllerIdentityRegistry,
) -> Callable[[str], _DesiredOutput | None]:
    """Provider de cor automática por controle para o backend (COR-03).

    Injetado via ``PyDualSenseController.set_auto_output_provider`` na fiação
    do daemon. O backend o chama em ``_merged_desired_for_key`` — SOB o
    ``_io_lock``, portanto ele é barato e sem I/O de disco (o ``slot_for``
    lazy só toca memória; a persistência fica com o ``sync_connected``).

    Devolve um ``_DesiredOutput`` com APENAS ``led`` (cor do slot, escalada
    pelo brilho vigente — D11, pelo MESMO caminho do global:
    ``LedSettings.apply_brightness``) e ``player_leds`` (padrão canônico do
    NÚMERO DO CONTROLE — D7; o co-op vence por construção, reescrevendo por
    cima via sysfs no ciclo dele). ``None`` = sem opinião (auto desligado,
    uniq sem slot, vpad) → o merge cai no default global (comportamento
    histórico, D5).
    """
    from hefesto_dualsense4unix.core.backend_pydualsense import _DesiredOutput
    from hefesto_dualsense4unix.core.led_control import (
        LedSettings,
        player_led_pattern,
        player_slot_color,
    )

    def provider(uniq: str) -> _DesiredOutput | None:
        if not registry.auto_enabled:
            return None
        slot = registry.slot_for(uniq)
        if slot is None:
            return None
        brilho = registry.auto_brightness
        settings = LedSettings(
            lightbar=player_slot_color(slot), brightness_level=brilho
        )
        return _DesiredOutput(
            led=settings.apply_brightness(brilho).lightbar,
            player_leds=player_led_pattern(slot),
        )

    return provider


_registry: ControllerIdentityRegistry | None = None
_registry_lock = threading.Lock()


def get_identity_registry() -> ControllerIdentityRegistry:
    """Registro de identidade do processo (singleton, criado sob demanda).

    Singleton deliberado: o ``ProfileManager`` é instanciado em ≥3 lugares
    (restore de boot, hotkey, IPC) e todos precisam configurar o MESMO
    estado do automático que o provider (injetado no backend pela fiação do
    daemon) consulta — sem parâmetro novo em cada callsite. A criação não
    faz I/O (o ``load()`` é chamado explicitamente só pela fiação do
    daemon), então testes que ativam perfis continuam herméticos.
    """
    global _registry
    with _registry_lock:
        if _registry is None:
            _registry = ControllerIdentityRegistry()
        return _registry


def reset_identity_registry() -> None:
    """Descarta o singleton (APENAS testes — isola estado entre casos)."""
    global _registry
    with _registry_lock:
        _registry = None


__all__ = [
    "ControllerIdentityRegistry",
    "get_identity_registry",
    "make_auto_output_provider",
    "reset_identity_registry",
]
