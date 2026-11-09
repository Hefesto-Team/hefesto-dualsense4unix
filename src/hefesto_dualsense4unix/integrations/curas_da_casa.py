"""As curas da casa que uma atualização do sistema pode desfazer, numa resposta só.

Quatro perguntas, lidas como o doctor lê: os módulos DKMS (o ``fonte-<kernel>.txt`` e o
``srcversion`` do módulo carregado), as MARCA_ do BlueZ no ``bluetoothd`` que o systemd executa,
a versão do PipeWire contra o ``BASELINE`` e a MARCA_ do portal de captura. Só lê, nunca levanta,
e responde «não se aplica» onde a cura não vale (outra distribuição, peça opt-in que não está).
"""
from __future__ import annotations

import contextlib
import json
import mmap
import os
import re
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

VALE = "vale"
CAIU = "caiu"
NAO_SE_APLICA = "nao_se_aplica"
ROTULO = "Correções do sistema"
RODE_O_INSTALADOR = "Rode o instalador do Hefesto de novo."
REINICIE = "Reinicie o computador."
FONTE_BOM = ("cache", "fabrica")
PRAZO_S = 10.0
VALIDADE_S = 30.0
ARQUIVO_DO_AVISO = "curas-avisadas.json"
MODULOS = (
    ("hefesto-hid-playstation", "hid_playstation", "O driver do DualSense"),
    ("hefesto-hid-nintendo", "hid_nintendo", "O driver do controle Nintendo"),
    ("hefesto-rtw88-usb", "rtw88_usb", "O driver do Wi-Fi USB"),
    ("hefesto-usb-f-hid", "usb_f_hid", "A função dos pads USB virtuais"),
)


def _rodar(argv: Sequence[str]) -> str | None:
    try:
        feito = subprocess.run(list(argv), capture_output=True, text=True, timeout=PRAZO_S,
                               check=False, stdin=subprocess.DEVNULL,
                               env={**os.environ, "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired) as erro:
        logger.debug("curas_comando_mudo", comando=argv[0], err=str(erro))
        return None
    return feito.stdout if feito.returncode == 0 else None


@dataclass(frozen=True)
class Maquina:
    """Onde as perguntas leem. O lar de mentira desvia cada raiz e o executor dos comandos."""

    sys_module: Path = Path("/sys/module")
    dkms: Path = Path("/var/lib/dkms")
    assets: Path = Path(__file__).resolve().parents[3] / "assets"
    cache: Path | None = None
    kernel: str = ""
    comando: Callable[[Sequence[str]], str | None] = _rodar

    def o_kernel(self) -> str:
        return self.kernel or os.uname().release

    def o_cache(self) -> Path:
        return self.cache or Path.home() / ".cache" / "hefesto-dualsense4unix"


MAQUINA = Maquina()


@dataclass(frozen=True)
class Cura:
    """Uma cura: ``estado`` é :data:`VALE`, :data:`CAIU` ou :data:`NAO_SE_APLICA`."""

    id: str
    nome: str
    estado: str
    frase: str = ""
    dica: str = ""


def _baseline(caminho: Path) -> dict[str, str]:
    valores: dict[str, str] = {}
    try:
        texto = caminho.read_text(encoding="utf-8")
    except OSError:
        return valores
    for linha in texto.splitlines():
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            valores.setdefault(chave, valor)
    return valores


def _contem(binario: Path, marca: bytes) -> bool | None:
    try:
        with binario.open("rb") as arquivo:
            if os.fstat(arquivo.fileno()).st_size == 0:
                return False
            with mmap.mmap(arquivo.fileno(), 0, access=mmap.ACCESS_READ) as mapa:
                return mapa.find(marca) >= 0
    except (OSError, ValueError) as erro:
        logger.debug("curas_binario_ilegivel", binario=str(binario), err=str(erro))
        return None


def _ordem(versao: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", versao))


def _modinfo(maquina: Maquina, kernel: str, nome: str) -> dict[str, str]:
    campos: dict[str, str] = {}
    for linha in (maquina.comando(["modinfo", "-k", kernel, nome]) or "").splitlines():
        chave, _, valor = linha.partition(":")
        if chave in ("filename", "srcversion"):
            campos.setdefault(chave, valor.strip())
    return campos


def _versao_do_dkms(pasta: Path) -> str | None:
    try:
        versoes = [p.name for p in pasta.iterdir()
                   if p.is_dir() and re.fullmatch(r"\d+(?:\.\d+)*", p.name)]
    except OSError as erro:
        logger.debug("curas_sem_o_dkms", pasta=str(pasta), err=str(erro))
        return None
    return max(versoes, key=_ordem) if versoes else None


def modulo(maquina: Maquina, pacote: str, nome: str, rotulo: str) -> Cura:
    """O módulo da casa vale no kernel que roda? Sem o pacote no DKMS, não se aplica."""
    kernel = maquina.o_kernel()
    versao = _versao_do_dkms(maquina.dkms / pacote)
    if versao is None:
        return Cura(nome, rotulo, NAO_SE_APLICA)
    estado = ""
    with contextlib.suppress(OSError):
        estado = ((maquina.dkms / pacote / versao / f"fonte-{kernel}.txt")
                  .read_text(encoding="utf-8").splitlines() or [""])[0].strip()
    if estado and estado not in FONTE_BOM:
        return Cura(nome, rotulo, CAIU, f"{rotulo} do Hefesto ficou de fora no kernel {kernel}",
                    RODE_O_INSTALADOR)
    info = _modinfo(maquina, kernel, nome)
    arquivo = info.get("filename", "")
    if not arquivo:
        return Cura(nome, rotulo, NAO_SE_APLICA)
    if "/updates/dkms/" not in arquivo:
        return Cura(nome, rotulo, CAIU, f"{rotulo} é o de fábrica no kernel {kernel}",
                    RODE_O_INSTALADOR)
    carregado = ""
    with contextlib.suppress(OSError):
        carregado = (maquina.sys_module / nome / "srcversion").read_text(encoding="utf-8").strip()
    instalado = info.get("srcversion", "")
    if carregado and instalado and carregado != instalado:
        return Cura(nome, rotulo, CAIU, f"{rotulo} em uso não é o do Hefesto", REINICIE)
    return Cura(nome, rotulo, VALE)


def modulos_da_casa(maquina: Maquina | None = None) -> Cura:
    maquina = maquina or MAQUINA
    todos = [modulo(maquina, *m) for m in MODULOS]
    caidos = [c for c in todos if c.estado == CAIU]
    if caidos:
        return Cura("dkms", "Módulos do kernel", CAIU, caidos[0].frase, caidos[0].dica)
    if all(c.estado == NAO_SE_APLICA for c in todos):
        return Cura("dkms", "Módulos do kernel", NAO_SE_APLICA)
    return Cura("dkms", "Módulos do kernel", VALE)


def driver_do_dualsense(maquina: Maquina | None = None) -> Cura:
    """O ``hid_playstation`` da casa, sozinho: o «Suporte ao controle» lê esta resposta."""
    return modulo(maquina or MAQUINA, *MODULOS[0])


def _instalado(maquina: Maquina, pacote: str) -> str:
    texto = maquina.comando(["dpkg-query", "-W", "-f", "${db:Status-Abbrev}|${Version}\n",
                             pacote]) or ""
    for linha in texto.splitlines():
        estado, _, versao = linha.partition("|")
        if estado.startswith("ii"):
            return versao.strip()
    return ""


def bluetooth(maquina: Maquina | None = None) -> Cura:
    """As MARCA_ do BASELINE estão no ``bluetoothd`` que o systemd executa?"""
    maquina = maquina or MAQUINA
    marcas = [v for k, v in _baseline(maquina.assets / "bluez-backport" / "BASELINE").items()
              if k.startswith("MARCA_") and v]
    if not marcas or not _instalado(maquina, "bluez"):
        return Cura("bluetooth", "Bluetooth", NAO_SE_APLICA)
    achado = re.search(r"path=(\S+)", maquina.comando(
        ["systemctl", "show", "bluetooth.service", "-p", "ExecStart", "--value"]) or "")
    if achado is None:
        return Cura("bluetooth", "Bluetooth", NAO_SE_APLICA)
    tem = [_contem(Path(achado.group(1)), m.encode()) for m in marcas]
    if None in tem:
        return Cura("bluetooth", "Bluetooth", NAO_SE_APLICA)
    if not all(tem):
        return Cura("bluetooth", "Bluetooth", CAIU,
                    "O Bluetooth voltou ao da distribuição, sem as correções do Hefesto",
                    RODE_O_INSTALADOR)
    return Cura("bluetooth", "Bluetooth", VALE)


def som(maquina: Maquina | None = None) -> Cura:
    """O PipeWire é o da casa, ou um da distribuição que já passou o do ``BASELINE``?"""
    maquina = maquina or MAQUINA
    alvo = _baseline(maquina.assets / "pipewire-backport" / "BASELINE").get("PW_VERSAO_UPSTREAM")
    versao = _instalado(maquina, "libpipewire-0.3-modules") if alvo else ""
    if not alvo or not versao:
        return Cura("som", "Som", NAO_SE_APLICA)
    if "~hefesto" in versao:
        return Cura("som", "Som", VALE)
    if _ordem(re.sub(r"^\d+:", "", versao).split("-", 1)[0]) >= _ordem(alvo):
        return Cura("som", "Som", VALE)
    return Cura("som", "Som", CAIU,
                "O som voltou ao da distribuição, mais velho que o do Hefesto", RODE_O_INSTALADOR)


def portal(maquina: Maquina | None = None) -> Cura:
    """A MARCA_ do cosmic-protocols#92 está no portal de captura do COSMIC?"""
    maquina = maquina or MAQUINA
    base = _baseline(maquina.assets / "portal-cosmic-backport" / "BASELINE")
    pacote, programa = base.get("PORTAL_PACOTE", ""), base.get("PORTAL_EXEC", "")
    marca = next((v for k, v in base.items() if k.startswith("MARCA_") and v), "")
    versao = _instalado(maquina, pacote) if pacote and programa and marca else ""
    if not versao or not _instalado(maquina, "cosmic-comp"):
        return Cura("portal", "Portal de captura", NAO_SE_APLICA)
    tem = _contem(Path(programa), marca.encode())
    if tem is None:
        return Cura("portal", "Portal de captura", NAO_SE_APLICA)
    de_cima = re.sub(r"\+0~hefesto.*$", "", versao)
    curadas = ""
    with contextlib.suppress(OSError):
        curadas = (maquina.o_cache() / "portal-cosmic-backport" / "A-ORIGEM-JA-CURA.txt") \
            .read_text(encoding="utf-8")
    if tem or de_cima in curadas.splitlines():
        return Cura("portal", "Portal de captura", VALE)
    return Cura("portal", "Portal de captura", CAIU,
                "A captura de tela voltou à da distribuição, sem a correção do Hefesto",
                RODE_O_INSTALADOR)


def curas(maquina: Maquina | None = None) -> list[Cura]:
    """As quatro respostas, na ordem da tela: módulos, Bluetooth, som e portal."""
    maquina = maquina or MAQUINA
    return [modulos_da_casa(maquina), bluetooth(maquina), som(maquina), portal(maquina)]


_lembradas: dict[int, tuple[float, list[Cura]]] = {}
_trava = threading.Lock()


def curas_de_agora(agora: Callable[[], float] = time.monotonic) -> list[Cura]:
    """As :func:`curas` da :data:`MAQUINA`, lembradas por :data:`VALIDADE_S`: a tela pergunta
    sem reler os binários a cada volta."""
    chave = id(MAQUINA)
    with _trava:
        lembrada = _lembradas.get(chave)
        if lembrada is not None and agora() - lembrada[0] < VALIDADE_S:
            return list(lembrada[1])
    respostas = curas(MAQUINA)
    with _trava:
        _lembradas.clear()
        _lembradas[chave] = (agora(), respostas)
    return list(respostas)


def resumo(respostas: Sequence[Cura]) -> Cura:
    """A linha «Correções do sistema»: verde com todas de pé, aviso com a frase da que caiu."""
    caidas = [c for c in respostas if c.estado == CAIU]
    if caidas:
        frase = caidas[0].frase if len(caidas) == 1 else (
            f"{caidas[0].frase} (e mais {len(caidas) - 1})")
        return Cura("sistema", ROTULO, CAIU, frase, caidas[0].dica)
    if all(c.estado == NAO_SE_APLICA for c in respostas):
        return Cura("sistema", ROTULO, NAO_SE_APLICA)
    return Cura("sistema", ROTULO, VALE, "As correções do Hefesto valem")


def linhas_de_aviso(respostas: Sequence[Cura] | None = None) -> list[str]:
    """Uma linha por cura caída, com a cura: o que o aviso do boot escreve."""
    lidas = curas_de_agora() if respostas is None else respostas
    return [f"{c.frase} — {c.dica}" for c in lidas if c.estado == CAIU]


def avisar_uma_vez_por_kernel(
    respostas: Sequence[Cura] | None = None,
    *,
    maquina: Maquina | None = None,
    estado: Path | None = None,
    notificar: Callable[[str, str], bool] | None = None,
) -> bool | None:
    """A notificação do sistema, uma vez por kernel. ``None``: nada a dizer, ou já dito neste
    kernel; ``False``: a área de trabalho recusou, e o aviso fica para a próxima tentativa."""
    total = resumo(curas_de_agora() if respostas is None else respostas)
    if total.estado != CAIU:
        return None
    kernel = (maquina or MAQUINA).o_kernel()
    if estado is None:
        from hefesto_dualsense4unix.utils.xdg_paths import state_dir

        estado = state_dir(ensure=True) / ARQUIVO_DO_AVISO
    try:
        visto = json.loads(estado.read_text(encoding="utf-8")).get("kernel")
    except (OSError, ValueError, AttributeError):
        visto = None
    if visto == kernel:
        return None
    if notificar is None:
        from hefesto_dualsense4unix.integrations.desktop_notifications import notify

        def notificar(titulo: str, corpo: str) -> bool:
            return notify(titulo, corpo, icon="dialog-warning", timeout_ms=15000)

    if not notificar(ROTULO, f"{total.frase}. {total.dica}"):
        return False
    with contextlib.suppress(OSError):
        estado.parent.mkdir(parents=True, exist_ok=True)
        estado.write_text(json.dumps({"kernel": kernel, "frase": total.frase},
                                     ensure_ascii=False), encoding="utf-8")
    return True


__all__ = [
    "CAIU",
    "MAQUINA",
    "NAO_SE_APLICA",
    "ROTULO",
    "VALE",
    "Cura",
    "Maquina",
    "avisar_uma_vez_por_kernel",
    "bluetooth",
    "curas",
    "curas_de_agora",
    "driver_do_dualsense",
    "linhas_de_aviso",
    "modulos_da_casa",
    "portal",
    "resumo",
    "som",
]
