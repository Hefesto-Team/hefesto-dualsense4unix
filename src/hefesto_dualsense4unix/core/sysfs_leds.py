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

#: Raiz da classe `leds` no sysfs. Variável de ambiente p/ testes herméticos.
LEDS_ROOT: str = os.environ.get("HEFESTO_DUALSENSE4UNIX_LEDS_ROOT", "/sys/class/leds")

#: Sufixo do nó da lightbar RGB (multicolor) registrado pelo hid_playstation.
_INDICATOR_SUFFIX = ":rgb:indicator"


def norm_mac(value: str | None) -> str | None:
    """Normaliza um MAC/serial para só os dígitos hex em minúsculo.

    ``serial_number`` (hidapi) e ``uniq`` (sysfs) podem diferir em caixa e na
    presença de ``:`` — normalizar os dois lados garante o casamento. Retorna
    ``None`` quando não há nenhum dígito hex (ex.: ``key`` que é um ``path``).
    """
    if not value:
        return None
    s = "".join(ch for ch in value.lower() if ch in "0123456789abcdef")
    return s or None


class SysfsLedNode:
    """Nós sysfs (lightbar + player LEDs) de UM controle DualSense."""

    def __init__(self, indicator_dir: str, player_dirs: list[str]) -> None:
        #: Diretório do LED multicolor (contém ``multi_intensity`` e ``brightness``).
        self.indicator_dir = indicator_dir
        #: Diretórios dos LEDs de player, ordenados por número (1..5).
        self.player_dirs = player_dirs
        # GUERRA-01 item 3: cache do último (rgb, brightness) ESCRITO com
        # sucesso por esta instância — `reassert_resolved_outputs()` roda a
        # cada reconciliação (30s do reconnect_loop) e reescrevia a MESMA cor
        # incondicionalmente (o "flash azul de 30s" da guerra de escritores).
        # Nó recriado (wake/adoção BT) = instância nova = cache vazio =
        # escreve naturalmente.
        self._last_write: tuple[tuple[int, int, int], int] | None = None
        self._skip_logged = False
        # NUMA-03: log de escritor estrangeiro 1x POR EPISÓDIO (espelho de
        # `_skip_logged`, mas com re-arme: uma verificação LIMPA — cor lida
        # igual à esperada — encerra o episódio e re-arma o log).
        self._foreign_logged = False

    # --- introspecção ----------------------------------------------------

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

    # --- leitura (STATUS-01) ----------------------------------------------

    def get_rgb(self) -> tuple[int, int, int] | None:
        """Cor atual da classe LED (``multi_intensity``), ou None se ilegível.

        STATUS-01 — ATENÇÃO ao que isto significa (refutação 1 do sprint): o
        ``multi_intensity`` NÃO é "a verdade do hardware" — é o último valor
        escrito VIA CLASSE LED. O probe do kernel registra o LED multicolor com
        intensidades ZERADAS e acende a lightbar de azul por um caminho interno
        que nunca atualiza a classe; escrita por hidraw (pydualsense/jogo em
        Modo Nativo) também não a atualiza. Quem decide se esta leitura é
        confiável é o rastreio "escrito por nós" do backend
        (``_sysfs_written``) — nunca rotular ``(0, 0, 0)`` daqui como
        "apagada" sem essa prova de posse. Tolerante: nó que sumiu (replug/BT)
        devolve None em vez de levantar.
        """
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

    def is_on(self) -> bool:
        """True se o ``brightness`` do LED multicolor é > 0. Tolerante (nó pode sumir).

        Nota de semântica: o caminho de escrita do daemon fixa ``brightness``
        em 255 e apaga por ``multi_intensity "0 0 0"`` (ver ``set_rgb``), então
        "fisicamente apagada" = ``is_on() and get_rgb() == (0, 0, 0)`` com a
        escrita rastreada como nossa — quem compõe essa leitura é o handler IPC.
        """
        try:
            with open(self._indicator_brightness) as fh:
                raw = fh.read().strip()
        except OSError:
            return False
        try:
            return int(raw or "0") > 0
        except ValueError:
            return False

    # --- escrita ---------------------------------------------------------

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
                    # Verificação limpa (ou ilegível — trata como hoje):
                    # encerra o episódio de escritor estrangeiro, se havia.
                    self._foreign_logged = False
            if intruso is None:
                if not self._skip_logged:
                    # 1x por nó (telemetria da cura): o journal prova que o
                    # reassert parou de martelar o firmware com a mesma cor.
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
            # Cache invalidado: cai na reescrita abaixo (retoma a posse).
            self._last_write = None
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
        """Padrão ACESO dos LEDs de player, lido da classe (puro — testes/doctor).

        NUMA-03: leitura de ``brightness`` é memória do kernel (zero
        subcomando HID). ``None`` quando não há nós de player ou algum ficou
        ilegível (replug/BT drop) — o chamador trata como "sem leitura", nunca
        como padrão apagado. Mesma ressalva do ``get_rgb``: escrita crua por
        hidraw não atualiza a classe, então isto é o último valor VIA CLASSE.
        """
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
        """``set_players`` que SÓ escreve nos nós de brightness divergentes.

        NUMA-03 (defesa dirigida): re-lê cada ``brightness`` (memória do
        kernel) e reescreve apenas os LEDs cujo estado físico via classe
        difere do desejado — repinta um padrão rabiscado por escritor
        estrangeiro (o "player 3" da Steam no incidente 14:42) sem gerar
        output report quando está tudo certo. Nó ilegível é escrito sem
        verificação (não dá para provar que está certo — melhor a escrita
        idempotente do que confiar num nó mudo).
        """
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
            # real = .../<HID_DEVICE>/leds/inputN:rgb:indicator
            #   dirname        -> .../<HID_DEVICE>/leds
            #   dirname^2      -> .../<HID_DEVICE>   (tem uevent com HID_UNIQ=MAC)
            hid_dir = os.path.dirname(os.path.dirname(real))
            name = os.path.basename(real)  # inputN:rgb:indicator
            prefix = name[: -len(_INDICATOR_SUFFIX)] if name.endswith(_INDICATOR_SUFFIX) else name
            mac = _read_mac(hid_dir, prefix)
            players = sorted(
                glob.glob(os.path.join(LEDS_ROOT, f"{prefix}:white:player-*"))
            )
            node = SysfsLedNode(indicator, players)
            # Indexa por MAC quando disponível; senão por um pseudo-key derivado do
            # prefixo (o backend tem fallback single-controle quando não há MAC).
            key = mac if mac else f"prefix:{prefix}"
            out[key] = node
        except OSError as exc:
            logger.debug("sysfs_led_discover_node_falhou", node=indicator, err=str(exc))
    return out


def _read_mac(hid_dir: str, prefix: str) -> str | None:
    """Lê o MAC do controle dono do nó LED, normalizado (ou None).

    Fonte primária: ``HID_UNIQ`` no ``uevent`` do device HID (existe em USB E BT).
    Fallback: ``uniq`` do input device (``<hid_dir>/input/<prefix>/uniq``).
    """
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
