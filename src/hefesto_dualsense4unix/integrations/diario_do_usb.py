"""diario_do_usb.py — o que entra, sai, volta e muda de velocidade no barramento USB.

Uma linha por evento em ``usb-diario.jsonl`` (o state do produto), com o ``boot_id``, pelo mesmo
anexar com trava e giro do :mod:`diario_do_radio`. A janela lê o arquivo sem IPC. Nunca o
``serial``: adaptador Bluetooth publica ali o endereço de rádio.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.integrations import diario_do_radio
from hefesto_dualsense4unix.integrations.censo_do_barramento import Censo, hubs_fisicos
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

#: o evento no log do daemon, em nome ASCII
_NO_LOG = {
    ENTROU: "usb_entrou",
    SAIU: "usb_saiu",
    VOLTOU: "usb_voltou",
    MUDOU_DE_VELOCIDADE: "usb_mudou_de_velocidade",
    NAO_APARECEU: "usb_ausente_neste_boot",
    COMECOU_A_OUVIR: "usb_ouvindo",
    PAROU_DE_OUVIR: "usb_parou_de_ouvir",
}

#: quanto depois da subida um adaptador ou hub de um boot anterior conta como «não apareceu»
AUSENTE_DEPOIS_DE_S = 60.0
#: os tipos cuja falta se diz: o que a pessoa não tira e põe a toda hora
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


#: os campos da :class:`Foto` sem padrão; um visto sem eles não vira aviso
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
) -> dict[str, Any]:
    """Uma linha no diário e a mesma no log do daemon."""
    entrada = diario_do_radio.registrar(
        QUEM, o_que, "", antes=antes, depois=depois, caminho=caminho, agora=agora,
        boot_id=boot_id, **dict(campos))
    logger.info(_NO_LOG.get(o_que, "usb_evento"), **{
        k: v for k, v in entrada.items() if k not in ("quem", "por_que", "quando")})
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


Registro = Callable[..., Any]


class Comparador:
    """Compara cada leitura com a anterior e diz o que mudou.

    A primeira leitura não registra entrada: o diário sabe desde que o Hefesto ouve. A volta se
    prova por duas vias: a saída e a entrada no mesmo caminho em até :data:`REENUMERA_EM_S`, ou o
    ``devnum`` que mudou no mesmo caminho entre duas leituras (a que o laço sem netlink acha).
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
    ) -> None:
        self.boot_id = boot_id
        self.vistos = vistos
        self._registro = registro
        self._subiu_em = subiu_em
        self._relogio = relogio
        self._agora = agora
        self._anterior: dict[str, Foto] | None = None
        self._saidas: dict[tuple[str, str], float] = {}
        self._ausentes_conferidos = False

    def _anotar(self, o_que: str, foto: Foto, **extras: Any) -> tuple[str, Foto]:
        self._registro(o_que, foto.campos(), **extras)
        return o_que, foto

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
                        eventos.append(self._anotar(VOLTOU, foto))
                    eventos += self._velocidade(foto)
                    continue
                saiu_em = self._saidas.pop((caminho, foto.vid_pid), None)
                volta = saiu_em is not None and agora - saiu_em <= REENUMERA_EM_S
                eventos.append(self._anotar(VOLTOU if volta else ENTROU, foto))
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
    "COMECOU_A_OUVIR",
    "ENTROU",
    "MUDOU_DE_VELOCIDADE",
    "NAO_APARECEU",
    "NOME_DO_DIARIO",
    "PAROU_DE_OUVIR",
    "REENUMERA_EM_S",
    "SAIU",
    "TIPOS_QUE_SE_ESPERAM",
    "VOLTOU",
    "Comparador",
    "Foto",
    "caminho_do_diario",
    "caminho_dos_vistos",
    "carregar_os_vistos",
    "fotos_do_censo",
    "gravar_os_vistos",
    "ler",
    "registrar",
]
