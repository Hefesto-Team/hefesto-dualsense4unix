"""diario_do_usb.py — o que entra, sai, volta e muda de velocidade no barramento USB.

Uma linha por evento em ``usb-diario.jsonl`` (o state do produto), com o ``boot_id``, pelo mesmo
anexar com trava e giro do :mod:`diario_do_radio`. A janela lê o arquivo sem IPC. Nunca o
``serial``: adaptador Bluetooth publica ali o endereço de rádio.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.integrations import diario_do_radio
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Censo,
    cadeia_de_hubs,
    hubs_fisicos,
    ler_o_barramento,
)
from hefesto_dualsense4unix.integrations.queda_do_wifi import REENUMERA_EM_S
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

NOME_DO_DIARIO = "usb-diario.jsonl"
NOME_DOS_VISTOS = "usb-vistos.json"
ENV_DIARIO = "HEFESTO_USB_DIARIO"
QUEM = "cadeia_usb"

ENTROU = "entrou"
SAIU = "saiu"
VOLTOU = "voltou"
MUDOU_DE_VELOCIDADE = "mudou de velocidade"
NAO_APARECEU = "não apareceu neste início"
COMECOU_A_OUVIR = "começou a ouvir"
PAROU_DE_OUVIR = "parou de ouvir"
RESETOU = "resetou"
CAIU = "caiu"

MOTIVO_RESET_USB = "reset_usb"
MOTIVO_QUEDA_USB = "queda_usb"
JANELA_DO_RESET_S = 15.0
PRAZO_DA_QUEDA_S = 30.0

_NO_LOG = {
    ENTROU: "usb_entrou",
    SAIU: "usb_saiu",
    VOLTOU: "usb_voltou",
    MUDOU_DE_VELOCIDADE: "usb_mudou_de_velocidade",
    NAO_APARECEU: "usb_ausente_neste_boot",
    COMECOU_A_OUVIR: "usb_ouvindo",
    PAROU_DE_OUVIR: "usb_parou_de_ouvir",
    RESETOU: "usb_resetou",
    CAIU: "usb_caiu",
}

AUSENTE_DEPOIS_DE_S = 60.0
TIPOS_QUE_SE_ESPERAM = frozenset({"Bluetooth", "Wi-Fi", "Hub"})
MAXIMO_DE_VISTOS = 256

@dataclass(frozen=True)
class Foto:
    """Um aparelho como o diário o registra: tipo, os dois nomes, driver, velocidade e lugar."""

    no: str
    vid: str
    pid: str
    tipo: str
    fabricante: str = ""
    produto: str = ""
    fabricante_da_base: str = ""
    produto_da_base: str = ""
    driver: str = ""
    velocidade_mbps: float = 0.0
    devnum: int = 0
    hub_fisico: str = ""

    @property
    def vid_pid(self) -> str:
        return f"{self.vid}:{self.pid}"

    @property
    def identidade(self) -> str:
        """«Já visto» é ``vid:pid`` + tipo + caminho no barramento (o nó)."""
        return f"{self.vid_pid}|{self.tipo}|{self.no}"

    def campos(self) -> dict[str, Any]:
        return asdict(self)


def fotos_do_censo(censo: Censo) -> dict[str, Foto]:
    """Cada aparelho conectado (sem os hubs-raiz), pelo caminho no barramento (``3-1.4``)."""
    representante = {
        no: Path(hub.representante).name for hub in hubs_fisicos(censo) for no in hub.nos
    }
    por_no = {a.no: a for a in censo.aparelhos}
    fotos: dict[str, Foto] = {}
    for aparelho in censo.conectados():
        hub = representante.get(aparelho.no, "")
        acima = por_no.get(aparelho.pai)
        while not hub and acima is not None and not acima.e_raiz:
            hub = representante.get(acima.no, "")
            acima = por_no.get(acima.pai)
        fotos[aparelho.nome_do_kernel] = Foto(
            no=aparelho.nome_do_kernel,
            vid=aparelho.vid,
            pid=aparelho.pid,
            tipo="Receptor 2.4G" if aparelho.receptor else aparelho.especie,
            fabricante=aparelho.fabricante,
            produto=aparelho.produto,
            fabricante_da_base=aparelho.fabricante_da_base,
            produto_da_base=aparelho.produto_da_base,
            driver=aparelho.driver,
            velocidade_mbps=aparelho.velocidade_mbps,
            devnum=aparelho.devnum,
            hub_fisico=hub,
        )
    return fotos


_OBRIGATORIOS = frozenset({"no", "vid", "pid", "tipo"})


def caminho_do_diario() -> Path:
    desvio = os.environ.get(ENV_DIARIO, "").strip()
    if desvio:
        return Path(desvio)
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    return state_dir() / NOME_DO_DIARIO


def caminho_dos_vistos(diario: Path) -> Path:
    return diario.with_name(NOME_DOS_VISTOS)


def registrar(
    o_que: str,
    campos: Mapping[str, Any],
    *,
    boot_id: str,
    caminho: Path,
    antes: Any = None,
    depois: Any = None,
    agora: float | None = None,
    por_que: str = "",
    fora_s: float | None = None,
) -> dict[str, Any]:
    """Uma linha no diário e a mesma no log do daemon; ``por_que`` é o motivo, quando se sabe.

    ``fora_s`` é o tempo que o aparelho ficou fora, pelo que o kernel avisou, quando a volta o diz.
    """
    entrada = diario_do_radio.registrar(
        QUEM, o_que, por_que, antes=antes, depois=depois, caminho=caminho, agora=agora,
        boot_id=boot_id, fora_s=fora_s, **dict(campos))
    logger.info(_NO_LOG.get(o_que, "usb_evento"), **{
        k: v for k, v in entrada.items() if k not in ("quem", "por_que", "quando")},
        **({"motivo": por_que} if por_que else {}))
    return entrada


def ler(caminho: Path | None = None, *, limite: int | None = None) -> list[dict[str, Any]]:
    """As linhas do diário (com o girado), em ordem de hora. Nunca levanta."""
    alvo = caminho or caminho_do_diario()
    return [
        e for e in diario_do_radio.ler(
            caminhos=[alvo.with_name(alvo.name + ".1"), alvo], limite=limite)
        if e.get("quem") == QUEM
    ]


def carregar_os_vistos(caminho: Path) -> dict[str, dict[str, Any]]:
    try:
        dado = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(dado, dict):
        return {}
    return {k: v for k, v in dado.items() if isinstance(k, str) and isinstance(v, dict)}


def gravar_os_vistos(caminho: Path, vistos: Mapping[str, Mapping[str, Any]]) -> None:
    mais_novos = sorted(vistos.items(), key=lambda kv: float(kv[1].get("visto_em") or 0.0))
    podado = dict(mais_novos[-MAXIMO_DE_VISTOS:])
    temporario = caminho.with_name(caminho.name + ".novo")
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        temporario.write_text(json.dumps(podado, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporario, caminho)
    except OSError:
        logger.warning("usb_vistos_nao_gravou", caminho=str(caminho), exc_info=True)
        with contextlib.suppress(OSError):
            temporario.unlink()


_RESET_DO_KERNEL = re.compile(
    r"^usb (?P<no>\d+-\d+(?:\.\d+)*): reset (?P<velocidade>.+?) USB device number "
    r"(?P<devnum>\d+) using (?P<host>\S+)\s*$"
)
_FUSO_SEM_DOIS_PONTOS = re.compile(r"([+-]\d{2})(\d{2})$")


@dataclass(frozen=True)
class ResetDoKernel:
    """A linha ``usb 3-4.4: reset high-speed USB device number 12 using xhci_hcd`` desmontada."""

    no: str
    velocidade: str
    devnum: int
    host: str


def ler_o_reset(mensagem: str) -> ResetDoKernel | None:
    """O reset de um aparelho USB numa mensagem do kernel, em qualquer velocidade, ou ``None``."""
    achado = _RESET_DO_KERNEL.match(mensagem.strip())
    if achado is None:
        return None
    return ResetDoKernel(
        no=achado["no"],
        velocidade=achado["velocidade"],
        devnum=int(achado["devnum"]),
        host=achado["host"],
    )


_QUEDA_DO_KERNEL = re.compile(
    r"^usb (?P<no>\d+-\d+(?:\.\d+)*): USB disconnect, device number (?P<antes>\d+), "
    r"voltou em (?P<ms>\d+) ms como new (?P<velocidade>.+?) USB device number "
    r"(?P<devnum>\d+) using (?P<host>\S+)\s*$"
)


@dataclass(frozen=True)
class QuedaDoKernel:
    """O par que o vigia entrega: ``USB disconnect`` e o ``new … USB device number`` da mesma porta.

    A queda de 21/11/2026, 18h10min28, na porta ``3-1.4``: o ``disconnect`` às 28,691 e o
    ``new high-speed USB device number 9`` às 29,044, 353 ms depois, sem reset no meio.
    """

    no: str
    devnum_antes: int
    fora_ms: int
    velocidade: str
    devnum: int
    host: str


def ler_a_queda(mensagem: str) -> QuedaDoKernel | None:
    """A queda que o vigia montou (``usb 3-1.4: USB disconnect, device number 8, voltou em …``)."""
    achado = _QUEDA_DO_KERNEL.match(mensagem.strip())
    if achado is None:
        return None
    return QuedaDoKernel(
        no=achado["no"],
        devnum_antes=int(achado["antes"]),
        fora_ms=int(achado["ms"]),
        velocidade=achado["velocidade"],
        devnum=int(achado["devnum"]),
        host=achado["host"],
    )


def carimbo_do_kernel(quando: str) -> float | None:
    """``2026-11-21T11:25:18-0300`` (ou ``-03:00``) em segundos.

    ``None`` quando não se lê, e a hora ilegível vai ao log.
    """
    try:
        normal = _FUSO_SEM_DOIS_PONTOS.sub(r"\1:\2", quando.strip())
        return datetime.fromisoformat(normal).timestamp()
    except ValueError as erro:
        logger.warning("usb_reset_hora_ilegivel", quando=quando, erro=str(erro))
        return None


def _aparelho_da_porta(censo: Censo, porta: str) -> Aparelho | None:
    return next((a for a in censo.aparelhos if a.nome_do_kernel == porta), None)


def _hubs_acima(censo: Censo, porta: str) -> tuple[str, ...]:
    """Os hubs físicos entre a porta e a raiz, do mais perto ao mais longe.

    Vazio quer dizer porta do computador. Com o aparelho já fora do censo, vale o primeiro
    ancestral que ainda está nele.
    """
    aparelho = _aparelho_da_porta(censo, porta)
    if aparelho is not None:
        return tuple(Path(h).name for h in cadeia_de_hubs(censo, aparelho.no))
    if "." not in porta:
        return ()
    pai = porta.rsplit(".", 1)[0]
    acima = _aparelho_da_porta(censo, pai)
    if acima is None:
        return _hubs_acima(censo, pai)
    cadeia = [Path(h).name for h in cadeia_de_hubs(censo, acima.no)]
    if acima.e_hub and not acima.e_raiz:
        representante = {n: h.representante for h in hubs_fisicos(censo) for n in h.nos}
        fisico = Path(representante.get(acima.no, acima.no)).name
        if fisico not in cadeia:
            cadeia.insert(0, fisico)
    return tuple(cadeia)


def _controladora_da_porta(censo: Censo, porta: str) -> str:
    aparelho = _aparelho_da_porta(censo, porta)
    if aparelho is not None and aparelho.controlador_pci:
        return aparelho.controlador_pci
    barramento = f"usb{porta.partition('-')[0]}"
    return next(
        (b.controlador_pci for b in censo.barramentos if b.nome_do_kernel == barramento), "")


def _boot_id_do_kernel() -> str:
    from hefesto_dualsense4unix.daemon.subsystems.identity import _read_boot_id

    return _read_boot_id() or ""


def _campos_da_porta(censo: Censo, porta: str) -> dict[str, Any]:
    """O que a porta tem no censo (``vid:pid``, tipo), os hubs acima e a controladora."""
    aparelho = _aparelho_da_porta(censo, porta)
    return {
        "no": porta,
        "vid": aparelho.vid if aparelho else "",
        "pid": aparelho.pid if aparelho else "",
        "tipo": ("Receptor 2.4G" if aparelho.receptor else aparelho.especie) if aparelho else "",
        "produto": aparelho.produto if aparelho else "",
        "hubs": list(_hubs_acima(censo, porta)),
        "controladora": _controladora_da_porta(censo, porta),
    }


def _ja_registrado(caminho: Path, o_que: str, no: str, quando: float) -> bool:
    return any(
        antiga.get("o_que") == o_que
        and antiga.get("no") == no
        and float(antiga.get("carimbo") or 0.0) == quando
        for antiga in ler(caminho)
    )


def registrar_o_reset(
    mensagem: str,
    *,
    quando: float,
    caminho: Path,
    censo: Censo,
    boot_id: str | None = None,
) -> dict[str, Any] | None:
    """O reset do kernel numa linha ``resetou`` do diário: a porta, os hubs acima e a controladora.

    Vale para todo aparelho: o que a porta tem agora (``vid:pid``, tipo) vem do censo; sem ele a
    linha leva só a porta. A mesma linha do kernel não entra duas vezes. O ``serial`` nunca entra.
    """
    reset = ler_o_reset(mensagem)
    if reset is None or _ja_registrado(caminho, RESETOU, reset.no, quando):
        return None
    campos = {
        **_campos_da_porta(censo, reset.no),
        "velocidade": reset.velocidade,
        "devnum": reset.devnum,
        "host": reset.host,
    }
    return registrar(
        RESETOU, campos, boot_id=_boot_id_do_kernel() if boot_id is None else boot_id,
        caminho=caminho, agora=quando)


def registrar_a_queda(
    mensagem: str,
    *,
    quando: float,
    caminho: Path,
    censo: Censo,
    boot_id: str | None = None,
) -> dict[str, Any] | None:
    """A queda do kernel numa linha ``caiu`` do diário: a porta, os hubs acima e a controladora.

    É o aparelho que sai e volta à MESMA porta de controladora física em até um segundo, sem
    reset: nenhuma mão tira e põe um cabo nesse tempo. Vale para todo aparelho, em toda porta; a
    linha leva ``fora_ms`` (o que o kernel mediu entre as duas linhas). A mesma queda não entra
    duas vezes. O ``serial`` nunca entra.
    """
    queda = ler_a_queda(mensagem)
    if queda is None or _ja_registrado(caminho, CAIU, queda.no, quando):
        return None
    campos = {
        **_campos_da_porta(censo, queda.no),
        "velocidade": queda.velocidade,
        "devnum": queda.devnum,
        "devnum_antes": queda.devnum_antes,
        "host": queda.host,
        "fora_ms": queda.fora_ms,
    }
    return registrar(
        CAIU, campos, boot_id=_boot_id_do_kernel() if boot_id is None else boot_id,
        caminho=caminho, agora=quando)


def _ultima_da_porta(entradas: Sequence[Mapping[str, Any]], o_que: str, no: str) -> float | None:
    horas = [
        float(e["carimbo"]) for e in entradas
        if e.get("o_que") == o_que and e.get("no") == no
    ]
    return max(horas) if horas else None


def ultimo_reset_da_porta(entradas: Sequence[Mapping[str, Any]], no: str) -> float | None:
    """A hora (``carimbo``) do último ``resetou`` desta porta, ou ``None``."""
    return _ultima_da_porta(entradas, RESETOU, no)


def ultima_queda_da_porta(entradas: Sequence[Mapping[str, Any]], no: str) -> float | None:
    """A hora (``carimbo``) da última ``caiu`` desta porta, ou ``None``."""
    return _ultima_da_porta(entradas, CAIU, no)


Registro = Callable[..., Any]


class Comparador:
    """Compara cada leitura com a anterior e diz o que mudou.

    A primeira leitura não registra entrada. A volta se prova por três vias: a saída e a entrada no
    mesmo caminho em até :data:`REENUMERA_EM_S` (contados até o ``add`` que o kernel avisou, por
    :meth:`chegou`, e não até a leitura do censo; sem aviso, até a leitura), o ``devnum`` que mudou
    no mesmo caminho, ou a entrada até :data:`PRAZO_DA_QUEDA_S` depois de uma ``caiu`` da porta.
    """

    def __init__(
        self,
        *,
        boot_id: str,
        vistos: dict[str, dict[str, Any]],
        registro: Registro,
        subiu_em: float,
        relogio: Callable[[], float] = time.monotonic,
        agora: Callable[[], float] = time.time,
        reset_da_porta: Callable[[str], float | None] | None = None,
        queda_da_porta: Callable[[str], float | None] | None = None,
    ) -> None:
        self.boot_id = boot_id
        self.vistos = vistos
        self._registro = registro
        self._subiu_em = subiu_em
        self._relogio = relogio
        self._agora = agora
        self._reset_da_porta = reset_da_porta
        self._queda_da_porta = queda_da_porta
        self._trava = threading.Lock()
        self._chegadas: dict[str, float] = {}
        self._partidas: dict[str, float] = {}
        self._anterior: dict[str, Foto] | None = None
        self._saidas: dict[tuple[str, str], float] = {}
        self._ausentes_conferidos = False

    def _anotar(self, o_que: str, foto: Foto, **extras: Any) -> tuple[str, Foto]:
        self._registro(o_que, foto.campos(), **extras)
        return o_que, foto

    def chegou(self, caminho: str, quando: float | None = None) -> None:
        """O kernel avisou o ``add`` de um aparelho neste caminho (pelo relógio do comparador)."""
        with self._trava:
            self._chegadas[caminho] = self._relogio() if quando is None else quando

    def partiu(self, caminho: str, quando: float | None = None) -> None:
        """O kernel avisou o ``remove`` de um aparelho neste caminho."""
        with self._trava:
            self._partidas[caminho] = self._relogio() if quando is None else quando

    def _fora_pelo_kernel(self, caminho: str, saiu_em: float | None) -> float | None:
        """Quanto o aparelho ficou fora, da saída à chegada que o kernel avisou; ``None`` sem aviso.

        A saída é o ``remove`` do kernel quando ele precede a leitura que a anotou em até
        :data:`REENUMERA_EM_S`; senão, a hora dessa leitura. Aviso fora de ordem não vale.
        """
        with self._trava:
            chegou = self._chegadas.pop(caminho, None)
            partiu = self._partidas.pop(caminho, None)
        if chegou is None:
            return None
        if partiu is not None and (saiu_em is None or 0.0 <= saiu_em - partiu <= REENUMERA_EM_S):
            ponto: float | None = partiu
        else:
            ponto = saiu_em
        if ponto is None or chegou < ponto:
            return None
        return chegou - ponto

    def _dentro(self, quando: float | None, janela: float) -> bool:
        return quando is not None and -1.0 <= self._agora() - quando <= janela

    def _motivo_da_queda(self, caminho: str) -> str:
        """``queda_usb`` quando o vigia viu a porta cair e voltar até :data:`PRAZO_DA_QUEDA_S`."""
        if self._queda_da_porta is None:
            return ""
        em = self._queda_da_porta(caminho)
        return MOTIVO_QUEDA_USB if self._dentro(em, PRAZO_DA_QUEDA_S) else ""

    def _motivo_da_volta(self, caminho: str) -> str:
        """``reset_usb`` quando o kernel resetou esta porta até :data:`JANELA_DO_RESET_S` antes.

        Sem reset, ``queda_usb`` quando a porta caiu e voltou (:meth:`_motivo_da_queda`).
        """
        if self._reset_da_porta is not None and self._dentro(
            self._reset_da_porta(caminho), JANELA_DO_RESET_S
        ):
            return MOTIVO_RESET_USB
        return self._motivo_da_queda(caminho)

    @staticmethod
    def _o_fora(fora_s: float | None) -> dict[str, float]:
        return {} if fora_s is None else {"fora_s": round(fora_s, 1)}

    def _velocidade(self, foto: Foto) -> list[tuple[str, Foto]]:
        visto = self.vistos.get(foto.identidade)
        antes = visto.get("velocidade_mbps") if visto else None
        if antes is None or float(antes) == foto.velocidade_mbps:
            return []
        return [self._anotar(
            MUDOU_DE_VELOCIDADE, foto, antes=float(antes), depois=foto.velocidade_mbps)]

    def _lembrar(self, foto: Foto) -> None:
        visto = self.vistos.get(foto.identidade, {})
        novo = {**foto.campos(), "boot_id": self.boot_id,
                "avisado_no_boot": visto.get("avisado_no_boot", "")}
        sem_hora = {k: v for k, v in visto.items() if k != "visto_em"}
        if sem_hora != novo:
            self.vistos[foto.identidade] = {**novo, "visto_em": self._agora()}

    def observar(self, fotos: Mapping[str, Foto]) -> list[tuple[str, Foto]]:
        agora = self._relogio()
        anterior, self._anterior = self._anterior, dict(fotos)
        eventos: list[tuple[str, Foto]] = []
        if anterior is None:
            for foto in fotos.values():
                eventos += self._velocidade(foto)
        else:
            for caminho, foto in anterior.items():
                atual = fotos.get(caminho)
                if atual is None or atual.vid_pid != foto.vid_pid:
                    eventos.append(self._anotar(SAIU, foto))
                    self._saidas[(caminho, foto.vid_pid)] = agora
            for caminho, foto in fotos.items():
                velho = anterior.get(caminho)
                if velho is not None and velho.vid_pid == foto.vid_pid:
                    if velho.devnum != foto.devnum:
                        eventos.append(self._anotar(
                            VOLTOU, foto, por_que=self._motivo_da_volta(caminho),
                            **self._o_fora(self._fora_pelo_kernel(caminho, None))))
                    eventos += self._velocidade(foto)
                    continue
                saiu_em = self._saidas.pop((caminho, foto.vid_pid), None)
                fora_s = self._fora_pelo_kernel(caminho, saiu_em)
                volta = False
                if saiu_em is not None:
                    fora = agora - saiu_em if fora_s is None else fora_s
                    volta = fora <= REENUMERA_EM_S or self._motivo_da_queda(caminho) != ""
                if volta:
                    eventos.append(self._anotar(
                        VOLTOU, foto, por_que=self._motivo_da_volta(caminho),
                        **self._o_fora(fora_s)))
                else:
                    eventos.append(self._anotar(ENTROU, foto))
                eventos += self._velocidade(foto)
        for foto in fotos.values():
            self._lembrar(foto)
        return eventos

    def conferir_ausentes(self) -> list[tuple[str, Foto]]:
        """Uma vez por boot, :data:`AUSENTE_DEPOIS_DE_S` depois da subida."""
        if self._ausentes_conferidos or self._relogio() - self._subiu_em < AUSENTE_DEPOIS_DE_S:
            return []
        self._ausentes_conferidos = True
        presentes = {f.identidade for f in (self._anterior or {}).values()}
        eventos: list[tuple[str, Foto]] = []
        for identidade, visto in self.vistos.items():
            if identidade in presentes or visto.get("tipo") not in TIPOS_QUE_SE_ESPERAM:
                continue
            if visto.get("boot_id") == self.boot_id or visto.get("avisado_no_boot") == self.boot_id:
                continue
            campos = {k: visto[k] for k in Foto.__dataclass_fields__ if k in visto}
            if not campos.keys() >= _OBRIGATORIOS:
                continue
            foto = Foto(**campos)
            visto["avisado_no_boot"] = self.boot_id
            eventos.append(self._anotar(NAO_APARECEU, foto))
        return eventos


__all__ = [
    "AUSENTE_DEPOIS_DE_S",
    "CAIU",
    "COMECOU_A_OUVIR",
    "ENTROU",
    "JANELA_DO_RESET_S",
    "MOTIVO_QUEDA_USB",
    "MOTIVO_RESET_USB",
    "MUDOU_DE_VELOCIDADE",
    "NAO_APARECEU",
    "NOME_DO_DIARIO",
    "PAROU_DE_OUVIR",
    "PRAZO_DA_QUEDA_S",
    "REENUMERA_EM_S",
    "RESETOU",
    "SAIU",
    "TIPOS_QUE_SE_ESPERAM",
    "VOLTOU",
    "Comparador",
    "Foto",
    "QuedaDoKernel",
    "ResetDoKernel",
    "caminho_do_diario",
    "caminho_dos_vistos",
    "carimbo_do_kernel",
    "carregar_os_vistos",
    "fotos_do_censo",
    "gravar_os_vistos",
    "ler",
    "ler_a_queda",
    "ler_o_reset",
    "main",
    "registrar",
    "registrar_a_queda",
    "registrar_o_reset",
    "ultima_queda_da_porta",
    "ultimo_reset_da_porta",
]


def main(argv: Sequence[str] | None = None) -> int:
    """``reset|queda --quando <hora do kernel> --mensagem <texto>``: grava no diário.

    Sai com 0 quando a linha entrou, 3 quando a mensagem não é um reset (ou uma queda) ou a linha
    já estava lá, 4 quando a hora do kernel não se lê (a linha não entrou, e o vigia diz isso) e 1
    quando o censo ou o diário falharam.
    """
    parser = argparse.ArgumentParser(prog="diario_do_usb")
    sub = parser.add_subparsers(dest="comando", required=True)
    leitores = {"reset": ler_o_reset, "queda": ler_a_queda}
    gravadores = {"reset": registrar_o_reset, "queda": registrar_a_queda}
    ajuda = {
        "reset": "grava o reset de um aparelho USB que o kernel disse",
        "queda": "grava a queda: o disconnect e o new da mesma porta em menos de um segundo",
    }
    for nome in leitores:
        filho = sub.add_parser(nome, help=ajuda[nome])
        filho.add_argument("--quando", required=True)
        filho.add_argument("--mensagem", required=True)
        filho.add_argument("--diario", default="")
        filho.add_argument("--raiz-usb", default="")
    args = parser.parse_args(argv)
    if leitores[args.comando](args.mensagem) is None:
        return 3
    quando = carimbo_do_kernel(args.quando)
    if quando is None:
        return 4
    try:
        entrada = gravadores[args.comando](
            args.mensagem, quando=quando,
            caminho=Path(args.diario) if args.diario else caminho_do_diario(),
            censo=ler_o_barramento(**({"raiz_usb": args.raiz_usb} if args.raiz_usb else {})))
    except Exception:
        logger.warning("usb_reset_nao_gravou", exc_info=True)
        return 1
    return 0 if entrada is not None else 3


if __name__ == "__main__":
    sys.exit(main())
