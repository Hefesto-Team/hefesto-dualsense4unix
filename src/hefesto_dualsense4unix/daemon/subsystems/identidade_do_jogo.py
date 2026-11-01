"""A identidade do jogo em cena, publicada como estado no barramento.

`{chave, executavel, buildid, loja, emulador}`: a chave é a do `perfil.jogo`, o `buildid` sai do
`appmanifest_<N>.acf` e o executável do `/proc` dos processos que a Steam abriu com aquele appid.
O PID nunca entra na carga.
"""
from __future__ import annotations

import asyncio
import pathlib
import re
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:  # pragma: no cover
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

INTERVALO_S = 2.0
TENTATIVAS_DO_EXECUTAVEL = 15
LOJA_STEAM = "steam"
CHAVES_DO_APPID = ("SteamAppId", "STEAM_COMPAT_APP_ID", "SteamGameId")

EMULADORES: dict[str, str] = {
    "retroarch": "retroarch",
    "dolphin-emu": "dolphin",
    "dolphin": "dolphin",
    "pcsx2": "pcsx2",
    "pcsx2-qt": "pcsx2",
    "rpcs3": "rpcs3",
    "azahar": "azahar",
    "citra": "citra",
    "citra-qt": "citra",
    "ryujinx": "ryujinx",
    "yuzu": "yuzu",
    "ppsspp": "ppsspp",
    "ppssppsdl": "ppsspp",
    "ppssppqt": "ppsspp",
    "duckstation": "duckstation",
    "duckstation-qt": "duckstation",
    "cemu": "cemu",
    "xemu": "xemu",
    "melonds": "melonds",
    "mgba": "mgba",
    "mgba-qt": "mgba",
    "flycast": "flycast",
}

INVOLUCROS = frozenset({
    "reaper", "steam-launch-wrapper", "pv-adverb", "pressure-vessel-wrap", "srt-bwrap",
    "bwrap", "bash", "sh", "dash", "env", "python", "python3", "wine", "wine64",
    "wine-preloader", "wine64-preloader", "wineserver", "proton", "umu-run", "mangohud",
    "gamemoderun", "gamescope", "steam", "steamwebhelper", "steam.exe", "explorer.exe",
    "services.exe", "winedevice.exe", "plugplay.exe", "svchost.exe", "rpcss.exe",
    "tabtip.exe", "conhost.exe", "start.exe", "rundll32.exe", "winedbg.exe",
    "steamerrorreporter.exe", "steamerrorreporter64.exe", "crashpad_handler.exe",
})

_BUILDID = re.compile(r'"buildid"\s+"(\d+)"', re.IGNORECASE)


def chave_do_appid(appid: int | None) -> str | None:
    return f"steam_app_{appid}" if isinstance(appid, int) and appid > 0 else None


def buildid_do_acf(texto: str) -> str | None:
    achado = _BUILDID.search(texto)
    return achado.group(1) if achado else None


def _texto(arquivo: pathlib.Path) -> str:
    try:
        return arquivo.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def buildid_do_appid(appid: int, pastas: Iterable[pathlib.Path]) -> str | None:
    """O `buildid` do `appmanifest_<appid>.acf` da primeira biblioteca que o tem."""
    for pasta in pastas:
        buildid = buildid_do_acf(_texto(pasta / f"appmanifest_{appid}.acf"))
        if buildid:
            return buildid
    return None


def _nome(caminho: str) -> str:
    return caminho.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def executavel_de(argvs: Iterable[Sequence[str]]) -> str | None:
    """O arquivo do jogo entre os processos do appid: o `.exe` antes do nativo, sem invólucro."""
    candidatos: list[str] = []
    for argv in argvs:
        if not argv or not argv[0]:
            continue
        caminho = argv[0].replace("\\", "/")
        nome = _nome(caminho)
        if not nome or nome.lower() in INVOLUCROS or "/windows/" in caminho.lower():
            continue
        candidatos.append(nome)
    candidatos.sort(key=lambda nome: not nome.lower().endswith(".exe"))
    return candidatos[0] if candidatos else None


def emulador_de(nomes: Iterable[str]) -> str | None:
    for nome in nomes:
        raiz = _nome(nome).lower()
        raiz = raiz[:-4] if raiz.endswith(".exe") else raiz
        raiz = raiz.split(".", 1)[0] if raiz.endswith(".appimage") else raiz
        if raiz in EMULADORES:
            return EMULADORES[raiz]
    return None


def _ambiente(pid_dir: pathlib.Path) -> str:
    try:
        return "\0" + (pid_dir / "environ").read_bytes().decode("utf-8", "replace")
    except OSError:
        return ""


def _argv(pid_dir: pathlib.Path) -> list[str]:
    try:
        cru = (pid_dir / "cmdline").read_bytes().decode("utf-8", "replace")
    except OSError:
        return []
    return [parte for parte in cru.split("\0") if parte]


def argvs_do_appid(appid: int, raiz_proc: pathlib.Path | str = "/proc") -> list[list[str]]:
    """O argv de cada processo que a Steam abriu com este appid, pelo ambiente."""
    raiz = pathlib.Path(raiz_proc)
    marcas = tuple(f"\0{chave}={appid}\0" for chave in CHAVES_DO_APPID)
    try:
        entradas = sorted(
            (e for e in raiz.iterdir() if e.name.isdigit()), key=lambda e: int(e.name))
    except OSError:
        return []
    achados: list[list[str]] = []
    for entrada in entradas:
        ambiente = _ambiente(entrada) + "\0"
        if any(marca in ambiente for marca in marcas):
            argv = _argv(entrada)
            if argv:
                achados.append(argv)
    return achados


def identidade(
    appid: int | None,
    *,
    raiz_proc: pathlib.Path | str = "/proc",
    pastas: Iterable[pathlib.Path] | None = None,
) -> dict[str, Any]:
    """A carga de `jogo.identidade` para o appid em cena (ou a de fora de jogo)."""
    chave = chave_do_appid(appid)
    if chave is None or appid is None:
        return {"chave": None, "executavel": None, "buildid": None, "loja": None, "emulador": None}
    if pastas is None:
        from hefesto_dualsense4unix.integrations.steam_launch_options import pastas_steamapps

        pastas = pastas_steamapps()
    argvs = argvs_do_appid(appid, raiz_proc)
    return {
        "chave": chave,
        "executavel": executavel_de(argvs),
        "buildid": buildid_do_appid(appid, pastas),
        "loja": LOJA_STEAM,
        "emulador": emulador_de(argv[0] for argv in argvs),
    }


class Identificador:
    """Republica só na mudança; com o executável ainda sem processo, tenta de novo por um tempo."""

    def __init__(self, publicar: Any, calcular: Any = identidade) -> None:
        self._publicar = publicar
        self._calcular = calcular
        self._publicada: dict[str, Any] | None = None
        self._appid: int | None = None
        self._tentativas = 0

    def precisa(self, appid: int | None) -> bool:
        if self._publicada is None or appid != self._appid:
            return True
        return (
            appid is not None and self._publicada.get("executavel") is None
            and self._tentativas < TENTATIVAS_DO_EXECUTAVEL)

    def receber(self, appid: int | None, carga: dict[str, Any]) -> bool:
        self._tentativas = 0 if appid != self._appid else self._tentativas + 1
        self._appid = appid
        if carga == self._publicada:
            return False
        self._publicada = carga
        self._publicar(carga)
        return True


def _appid(daemon: Any) -> int | None:
    valor = getattr(daemon, "appid_em_cena", None)
    return valor if isinstance(valor, int) and not isinstance(valor, bool) and valor > 0 else None


async def identidade_do_jogo_loop(daemon: DaemonProtocol) -> None:
    bus = getattr(daemon, "bus", None)
    if bus is None:
        return
    quem = Identificador(lambda carga: bus.publish(EventTopic.JOGO_IDENTIDADE, carga))
    while not daemon._is_stopping():
        appid = _appid(daemon)
        if quem.precisa(appid):
            quem.receber(appid, await asyncio.to_thread(identidade, appid))
        await asyncio.sleep(INTERVALO_S)


def start_identidade_do_jogo(daemon: DaemonProtocol) -> None:
    task = asyncio.create_task(identidade_do_jogo_loop(daemon), name="identidade_do_jogo_loop")
    daemon._tasks.append(task)
    logger.info("identidade_do_jogo_iniciada")
