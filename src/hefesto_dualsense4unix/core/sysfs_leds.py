"""Controle dos LEDs do DualSense pela interface sysfs do kernel `hid_playstation`.

O driver de kernel `hid_playstation` (mainline ≥5.12) expõe a lightbar RGB como
um LED *multicolor* (`<prefixo>:rgb:indicator`, atributo ``multi_intensity``) e os
5 LEDs de player como LEDs brancos (`<prefixo>:white:player-1..5`, atributo
``brightness`` 0/1). Escrever nesses nós DELEGA ao kernel a montagem do output
report — que difere entre USB e Bluetooth (no BT precisa de ``seq_tag`` monotônico
+ CRC-32). Por isso essa rota acende a cor IGUAL em USB e BT.

Contraste: a escrita crua por hidraw (pydualsense) usa ``seq_tag`` fixo e disputa
a lightbar/player-LED com o próprio kernel (que é dono desses LED class devices),
fazendo a cor "não colar" no BT — exatamente o sintoma de
BUG-MULTI-CONTROLLER-BT-CRC-CONTENTION-01 (lightbar-bt). FEAT-DSX-LIGHTBAR-SYSFS-01.

Mapeamento controle→nó: a ``key`` estável do backend (``serial`` == MAC, ou
``path``) é casada com o ``uniq`` (MAC) do input device do gamepad, que é o pai
dos nós LED no sysfs. A escrita só é considerada "disponível" quando o atributo é
GRAVÁVEL pelo usuário do daemon (regra udev `77-dualsense-leds.rules`); sem ela, o
backend cai no caminho pydualsense (sem regressão).
"""
from __future__ import annotations

import glob
import os

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

LEDS_ROOT: str = os.environ.get("HEFESTO_DUALSENSE4UNIX_LEDS_ROOT", "/sys/class/leds")

_INDICATOR_SUFFIX = ":rgb:indicator"


def norm_mac(value: str | None) -> str | None:
    """Normaliza um MAC/serial para só os dígitos hex em minúsculo."""
    if not value:
        return None
    s = "".join(ch for ch in value.lower() if ch in "0123456789abcdef")
    return s or None


class SysfsLedNode:
    """Nós sysfs (lightbar + player LEDs) de UM controle DualSense."""

    def __init__(self, indicator_dir: str, player_dirs: list[str]) -> None:
        self.indicator_dir = indicator_dir
        self.player_dirs = player_dirs
        self._last_write: tuple[tuple[int, int, int], int] | None = None
        self._skip_logged = False
        self._foreign_logged = False


    @property
    def _multi_intensity(self) -> str:
        return os.path.join(self.indicator_dir, "multi_intensity")

    @property
    def _indicator_brightness(self) -> str:
        return os.path.join(self.indicator_dir, "brightness")

    def writable(self) -> bool:
        """True se o usuário atual pode ESCREVER na lightbar (regra udev aplicada).

        Gate anti-regressão: o backend só usa a rota sysfs (e suprime a escrita de
        LED da pydualsense) quando isto é verdadeiro. Sem permissão, cai no
        caminho pydualsense — o comportamento histórico, sem piora.
        """
        return os.access(self._multi_intensity, os.W_OK)


    def get_rgb(self) -> tuple[int, int, int] | None:
        """Cor atual da classe LED (``multi_intensity``), ou None se ilegível."""
        try:
            with open(self._multi_intensity) as fh:
                parts = fh.read().split()
        except OSError:
            return None
        if len(parts) != 3:
            return None
        try:
            r, g, b = (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return None
        return (r, g, b)

    def _brightness_lido(self) -> int | None:
        """``brightness`` do LED multicolor como número, ou None se ilegível."""
        try:
            with open(self._indicator_brightness) as fh:
                raw = fh.read().strip()
        except OSError:
            return None
        try:
            return int(raw or "0")
        except ValueError:
            return None

    def is_on(self) -> bool:
        """True se o ``brightness`` do LED multicolor é > 0. Tolerante (nó pode sumir)."""
        valor = self._brightness_lido()
        return valor is not None and valor > 0


    @staticmethod
    def _write(path: str, data: str) -> bool:
        try:
            with open(path, "w") as fh:
                fh.write(data)
            return True
        except OSError as exc:
            logger.debug("sysfs_led_write_falhou", path=path, err=str(exc))
            return False

    def set_rgb(self, r: int, g: int, b: int, *, verify: bool = False) -> bool:
        """Acende a lightbar na cor ``(r, g, b)`` via kernel (USB e BT).

        A cor JÁ chega escalada pelo brilho do perfil (o daemon multiplica antes
        de chamar ``set_led``), então fixamos ``brightness`` no máximo (255) e o
        dimming vem do próprio RGB. Para apagar usamos ``multi_intensity "0 0 0"``
        (não ``brightness 0``) — "off" determinístico que não reacende no boot.

        LUZ-CEGA-01/F3 (22/08/2026): "fixar em 255" passou a ser *garantir* 255,
        não *reescrever* 255. Cada escrita na classe LED custa UM output report
        do kernel, e o `btmon` mediu os dois quadros de uma troca de cor saindo
        no mesmo milissegundo com bytes IDÊNTICOS — o report leva o estado
        inteiro do LED, então o quadro do ``brightness`` já dizia a cor nova.
        Com o valor divergente (um terceiro apagou pela classe) ou ILEGÍVEL (nó
        sumindo num replug), a escrita acontece como sempre aconteceu, e na
        MESMA ordem — o ``brightness`` antes da cor.

        GUERRA-01 item 3: escrita IGUAL à última bem-sucedida desta instância é
        pulada em silêncio (cache) — o reassert periódico do reconnect_loop
        deixa de gerar output report quando a cor resolvida não mudou. Escrita
        que falha NÃO cacheia (a próxima tentativa re-escreve). Posse retomada
        de terceiros (ex.: fim de sessão de jogo) usa ``invalidate_cache()``.

        NUMA-03 (``verify=True``): no cache-hit, re-lê ``get_rgb()`` (memória
        do kernel — zero subcomando HID) ANTES do skip; classe divergente do
        cache = escritor estrangeiro (incidente 14:42 medido: cliente Steam
        pintou verde com o cache acreditando em azul) ⇒ invalida, REESCREVE e
        loga ``lightbar_escritor_estrangeiro`` 1x por episódio (re-armado por
        uma verificação limpa). ``get_rgb()`` None/ilegível ⇒ comporta como
        hoje (skip, sem log, sem repaint) — veto 5 da síntese: nó que sumiu
        num BT drop NÃO pode virar falso estrangeiro. ``verify=False``
        (default) é byte-idêntico ao comportamento histórico.

        Limitação documentada (fato §2 do mapa): escrita CRUA por hidraw que
        não passa pela classe LED segue INVISÍVEL a esta re-leitura (o kernel
        não atualiza ``multi_intensity``) — cobertura parcial fica com o
        ``defend_display`` do backend (invalidate + reassert dirigido); a
        cura completa é a posse autoritativa dos fds (Onda S).
        """
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g)))
        b = max(0, min(255, int(b)))
        wanted = ((r, g, b), 255)
        if self._last_write == wanted:
            intruso: tuple[int, int, int] | None = None
            if verify:
                lido = self.get_rgb()
                if lido is not None and lido != (r, g, b):
                    intruso = lido
                else:
                    self._foreign_logged = False
            if intruso is None:
                if not self._skip_logged:
                    logger.info(
                        "lightbar_reassert_skip_cache",
                        node=self.indicator_dir,
                        rgb=(r, g, b),
                    )
                    self._skip_logged = True
                return True
            if not self._foreign_logged:
                logger.info(
                    "lightbar_escritor_estrangeiro",
                    node=self.indicator_dir,
                    lido=intruso,
                    esperado=(r, g, b),
                )
                self._foreign_logged = True
            self._last_write = None
        ok = True
        if self._brightness_lido() != 255:
            ok = self._write(self._indicator_brightness, "255")
        ok = self._write(self._multi_intensity, f"{r} {g} {b}") and ok
        self._last_write = wanted if ok else None
        return ok

    def invalidate_cache(self) -> None:
        """Esquece a última escrita — a próxima ``set_rgb`` escreve SEMPRE.

        Para os casos de posse retomada em que um terceiro (jogo via hidraw,
        kernel no resume) pode ter mudado a cor por fora da classe LED sem
        recriar o nó — o cache ficaria "certo" com o hardware errado.
        """
        self._last_write = None

    def set_players(self, bits: tuple[bool, bool, bool, bool, bool]) -> bool:
        """Acende/apaga os 5 LEDs de player (``bits[0]`` = LED 1, à esquerda)."""
        if not self.player_dirs:
            return False
        ok = True
        for i, directory in enumerate(self.player_dirs):
            on = "1" if (i < len(bits) and bits[i]) else "0"
            ok = self._write(os.path.join(directory, "brightness"), on) and ok
        return ok

    def get_players(self) -> tuple[bool, ...] | None:
        """Padrão ACESO dos LEDs de player, lido da classe (puro — testes/doctor)."""
        if not self.player_dirs:
            return None
        bits: list[bool] = []
        for directory in self.player_dirs:
            try:
                with open(os.path.join(directory, "brightness")) as fh:
                    raw = fh.read().strip()
                bits.append(int(raw or "0") > 0)
            except (OSError, ValueError):
                return None
        return tuple(bits)

    def set_players_verified(
        self, bits: tuple[bool, bool, bool, bool, bool]
    ) -> bool:
        """``set_players`` que SÓ escreve nos nós de brightness divergentes."""
        if not self.player_dirs:
            return False
        ok = True
        for i, directory in enumerate(self.player_dirs):
            want = bool(i < len(bits) and bits[i])
            atual: bool | None = None
            try:
                with open(os.path.join(directory, "brightness")) as fh:
                    atual = int(fh.read().strip() or "0") > 0
            except (OSError, ValueError):
                atual = None
            if atual is not None and atual == want:
                continue
            ok = self._write(
                os.path.join(directory, "brightness"), "1" if want else "0"
            ) and ok
        return ok


def discover() -> dict[str, SysfsLedNode]:
    """Descobre os nós LED de cada DualSense conectado, indexados por MAC normalizado.

    Retorna ``{}`` se o kernel não expôs nenhum nó (driver antigo, controle
    desconectado, ou rodando em ambiente sem `/sys/class/leds`). Só LEITURA — não
    exige permissão de escrita (a checagem de gravabilidade fica em
    ``SysfsLedNode.writable``).
    """
    out: dict[str, SysfsLedNode] = {}
    pattern = os.path.join(LEDS_ROOT, f"*{_INDICATOR_SUFFIX}")
    for indicator in glob.glob(pattern):
        try:
            real = os.path.realpath(indicator)
            hid_dir = os.path.dirname(os.path.dirname(real))
            name = os.path.basename(real)
            prefix = name[: -len(_INDICATOR_SUFFIX)] if name.endswith(_INDICATOR_SUFFIX) else name
            mac = _read_mac(hid_dir, prefix)
            players = sorted(
                glob.glob(os.path.join(LEDS_ROOT, f"{prefix}:white:player-*"))
            )
            node = SysfsLedNode(indicator, players)
            key = mac if mac else f"prefix:{prefix}"
            out[key] = node
        except OSError as exc:
            logger.debug("sysfs_led_discover_node_falhou", node=indicator, err=str(exc))
    return out


def _read_mac(hid_dir: str, prefix: str) -> str | None:
    """Lê o MAC do controle dono do nó LED, normalizado (ou None)."""
    uevent = os.path.join(hid_dir, "uevent")
    try:
        with open(uevent) as fh:
            for line in fh:
                if line.startswith("HID_UNIQ="):
                    mac = norm_mac(line.split("=", 1)[1].strip())
                    if mac:
                        return mac
    except OSError:
        pass
    uniq_path = os.path.join(hid_dir, "input", prefix, "uniq")
    try:
        with open(uniq_path) as fh:
            return norm_mac(fh.read().strip())
    except OSError:
        return None


__all__ = ["LEDS_ROOT", "SysfsLedNode", "discover", "norm_mac"]
