"""Os contratos de fora no doctor: o que o Hefesto assume do mundo do outro, por capacidade.

O censo (``docs/data/contratos-de-fora.csv``) lista cada ponto de contato com o BlueZ, o
PipeWire, o systemd, a Steam, o Proton, o kernel e o COSMIC. Aqui moram as perguntas que o
``doctor`` faz a cada um, e a regra é a do censo: **a capacidade, nunca a versão**. Nenhuma
sonda compara número de versão; todas perguntam se a porta existe e responde do jeito que o
Hefesto usa (a interface D-Bus, o formato JSON do ``pactl``, o nó do kernel, o arquivo que a
Steam promete).

Quando uma sonda não converge, a linha do doctor nomeia o CONTRATO que quebrou e o comando
para conferir, em vez de falha calada. Dono que não existe nesta máquina (sem Steam, sem
COSMIC) é ``[INFO]``: o produto é para qualquer computador, e ausência não é defeito.

Só leitura: nenhuma sonda escreve no BlueZ, no servidor de som, na Steam nem no kernel. O
``busctl`` só faz ``tree``; o ``pactl``, só ``info``; o ``wpctl``, só ``status``.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

ESPERA_S = 3.0

OK = "ok"
QUEBROU = "quebrou"
AUSENTE = "ausente"


@dataclass(frozen=True)
class Falta:
    """A ferramenta não respondeu. ``ausente`` separa as duas causas, que não são a mesma coisa.

    ``ausente=True``: a ferramenta não existe nesta máquina (o dono não está aqui, ``[INFO]``).
    ``ausente=False``: ela existe e não respondeu (o tempo esgotou, a permissão faltou): o
    contrato quebrou, e isso nunca se lê como ausência.
    """

    motivo: str
    ausente: bool = True


Rodar = Callable[[Sequence[str]], "tuple[int, str] | Falta"]


def rodar_de_verdade(argv: Sequence[str]) -> tuple[int, str] | Falta:
    """``(rc, saída)``, ou a ``Falta`` quando a ferramenta não existe (ou não respondeu a tempo)."""
    ambiente = dict(os.environ)
    ambiente["LC_ALL"] = "C"
    try:
        feito = subprocess.run(
            list(argv), capture_output=True, text=True, timeout=ESPERA_S, check=False, env=ambiente
        )
    except FileNotFoundError as erro:
        return Falta(f"{type(erro).__name__}: {erro}")
    except (OSError, subprocess.SubprocessError) as erro:
        return Falta(f"{type(erro).__name__}: {erro}", ausente=False)
    return feito.returncode, feito.stdout


def _sem_resposta(falta: Falta, ferramenta: str) -> Resultado:
    """Ferramenta que não existe é ``[INFO]``; ferramenta que existe e não respondeu quebrou."""
    if falta.ausente:
        return Resultado(AUSENTE, f"sem {ferramenta} nesta máquina")
    return Resultado(QUEBROU, f"o {ferramenta} não respondeu ({falta.motivo})")


@dataclass(frozen=True)
class Ambiente:
    """O que as sondas enxergam do mundo. Cada campo se troca por um dublê nos testes."""

    rodar: Rodar = rodar_de_verdade
    home: Path = field(default_factory=Path.home)
    env: dict[str, str] = field(default_factory=lambda: dict(os.environ))
    raiz: Path = Path("/")

    def caminho(self, absoluto: str) -> Path:
        return self.raiz / absoluto.lstrip("/")


@dataclass(frozen=True)
class Resultado:
    estado: str
    detalhe: str = ""


@dataclass(frozen=True)
class Contrato:
    """Uma promessa do outro lado. ``id`` é o que o censo cita em ``contrato:<id>``."""

    id: str
    dono: str
    promessa: str
    conferir: str
    sonda: Callable[[Ambiente], Resultado]
    #: os alvos de porta interna (ou de pergunta por versão) que a sonda pergunta DE FATO. Uma
    #: linha frágil do censo só cita este contrato se o alvo dela estiver aqui: a sonda da porta
    #: oficial não vê a interna quebrar, e dizer que vê é dar [ OK ] sobre o que mudou.
    cobre: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# As sondas. Cada uma pergunta uma capacidade e devolve o que faltou, com nome.


def _sonda_bluez(amb: Ambiente) -> Resultado:
    saida = amb.rodar(["busctl", "--system", "tree", "org.bluez"])
    if isinstance(saida, Falta):
        return _sem_resposta(saida, "busctl")
    rc, texto = saida
    if rc == 0 and "/org/bluez" in texto:
        return Resultado(OK)
    return Resultado(QUEBROU, "o nome org.bluez não responde no barramento do sistema")


def _sonda_pactl_json(amb: Ambiente) -> Resultado:
    saida = amb.rodar(["pactl", "--format=json", "info"])
    if isinstance(saida, Falta):
        return _sem_resposta(saida, "pactl")
    rc, texto = saida
    if rc != 0:
        return Resultado(QUEBROU, f"o pactl respondeu rc={rc} ao formato JSON")
    try:
        lido = json.loads(texto)
    except ValueError as erro:
        return Resultado(QUEBROU, f"o pactl não entrega o formato JSON que o Hefesto lê ({erro})")
    if isinstance(lido, dict):
        return Resultado(OK)
    return Resultado(QUEBROU, "o pactl entrega JSON, mas não o objeto que o Hefesto lê")


def _sonda_wpctl(amb: Ambiente) -> Resultado:
    saida = amb.rodar(["wpctl", "status"])
    if isinstance(saida, Falta):
        return _sem_resposta(saida, "wpctl")
    return (
        Resultado(OK) if saida[0] == 0 else Resultado(QUEBROU, "o wpctl não fala com o WirePlumber")
    )


def _sonda_systemd(amb: Ambiente) -> Resultado:
    saida = amb.rodar(["systemctl", "--user", "show-environment"])
    if isinstance(saida, Falta):
        return _sem_resposta(saida, "systemctl")
    return (
        Resultado(OK) if saida[0] == 0 else Resultado(QUEBROU, "o systemd de usuário não responde")
    )


def _sonda_nos_do_kernel(amb: Ambiente) -> Resultado:
    faltam = [
        nome
        for nome, caminho in (
            ("/dev/uinput", "/dev/uinput"),
            ("/dev/uhid", "/dev/uhid"),
            ("/sys/class/hidraw", "/sys/class/hidraw"),
            ("/dev/input", "/dev/input"),
        )
        if not amb.caminho(caminho).exists()
    ]
    if not faltam:
        return Resultado(OK)
    return Resultado(QUEBROU, "faltam " + ", ".join(faltam))


def _sonda_driver_sony(amb: Ambiente) -> Resultado:
    """O kernel TEM o driver: ligado ao barramento agora, ou disponível para carregar.

    O ``hid_playstation`` é módulo que o kernel carrega quando o primeiro controle Sony chega;
    numa máquina sem controle desde o boot a pasta do driver não existe, e isso não é defeito.
    A pergunta à porta oficial (o ``modinfo`` do kmod) é se o kernel em uso sabe carregá-lo.
    """
    if amb.caminho("/sys/bus/hid/drivers/playstation").is_dir():
        return Resultado(OK)
    saida = amb.rodar(["modinfo", "-F", "filename", "hid_playstation"])
    if isinstance(saida, Falta):
        if saida.ausente:
            return Resultado(
                AUSENTE, "sem controle Sony ligado desde o boot e sem modinfo para perguntar"
            )
        return _sem_resposta(saida, "modinfo")
    if saida[0] == 0 and saida[1].strip():
        return Resultado(OK)
    return Resultado(QUEBROU, "o kernel em uso não tem o driver playstation (hid_playstation)")


def _raizes_da_steam(amb: Ambiente) -> list[Path]:
    return [
        r
        for r in (amb.home / ".steam" / "steam", amb.home / ".local" / "share" / "Steam")
        if r.is_dir()
    ]


def _perderam_o_wrapper(amb: Ambiente, texto: str) -> list[str]:
    """Os jogos que o Hefesto JÁ viu com o wrapper e que a Steam devolveu sem ele.

    O registro é o da sentinela (``wrapper-visto.json``): a Steam é a dona do arquivo e já apagou
    o ``hefesto-launch`` de um jogo sem aviso (17/09/2026). Jogo que ela recusou fica de fora, e
    leitura sem nenhum app (a Steam no meio da regravação) não conclui nada.
    """
    from .sentinela_do_wrapper import ler_registro
    from .steam_launch_options import (
        WRAPPER_PREFIX,
        ler_jogos_sem_wrapper,
        read_apps_by_appid,
        sem_wrapper_path,
    )

    apps = read_apps_by_appid(texto)
    recusados = set(ler_jogos_sem_wrapper(sem_wrapper_path(amb.home / ".config")))
    vistos = ler_registro(home=amb.home)
    return sorted(
        appid
        for appid, valor in apps.items()
        if appid in vistos and appid not in recusados and WRAPPER_PREFIX not in (valor or "")
    )


def _sonda_steam(amb: Ambiente) -> Resultado:
    raizes = _raizes_da_steam(amb)
    if not raizes:
        return Resultado(AUSENTE, "a Steam não está instalada para este usuário")
    ilegiveis: list[str] = []
    abriu = False
    perderam: list[str] = []
    for raiz in raizes:
        for conf in sorted((raiz / "userdata").glob("*/config/localconfig.vdf")):
            try:
                texto = conf.read_text(encoding="utf-8", errors="replace")
            except OSError as erro:
                ilegiveis.append(f"{conf.name}: {erro.strerror}")
                continue
            if '"UserLocalConfigStore"' in texto[:4096]:
                abriu = True
                perderam += _perderam_o_wrapper(amb, texto)
    if abriu and perderam:
        mostrados = ", ".join(sorted(set(perderam))[:5])
        return Resultado(
            QUEBROU,
            f"{len(set(perderam))} jogo(s) que tinham o wrapper do Hefesto voltaram sem ele "
            f"(a Steam reescreveu o localconfig.vdf): {mostrados}",
        )
    if abriu:
        return Resultado(OK)
    detalhe = "nenhum localconfig.vdf com a raiz UserLocalConfigStore que o Hefesto lê"
    if ilegiveis:
        detalhe += " (ilegíveis: " + ", ".join(ilegiveis) + ")"
    return Resultado(QUEBROU, detalhe)


def _sonda_proton(amb: Ambiente) -> Resultado:
    pastas = [raiz / "compatibilitytools.d" for raiz in _raizes_da_steam(amb)]
    if not pastas:
        return Resultado(AUSENTE, "a Steam não está instalada para este usuário")
    achados = [
        p
        for pasta in pastas
        if pasta.is_dir()
        for p in sorted(pasta.glob("*/compatibilitytool.vdf"))
    ]
    if not achados:
        return Resultado(AUSENTE, "nenhum Proton de terceiros em compatibilitytools.d")
    sem_proton = [p.parent.name for p in achados if not (p.parent / "proton").exists()]
    if sem_proton:
        return Resultado(QUEBROU, "sem o executável `proton` em " + ", ".join(sem_proton))
    return Resultado(OK)


def _sonda_cosmic(amb: Ambiente) -> Resultado:
    if "COSMIC" not in amb.env.get("XDG_CURRENT_DESKTOP", "").upper():
        return Resultado(AUSENTE, "a sessão não é COSMIC")
    if (amb.home / ".config" / "cosmic").is_dir():
        return Resultado(OK)
    return Resultado(QUEBROU, "a sessão é COSMIC e ~/.config/cosmic não existe")


CONTRATOS: tuple[Contrato, ...] = (
    Contrato(
        id="bluez-dbus",
        dono="bluez",
        promessa="o BlueZ atende em org.bluez pelo D-Bus do sistema",
        conferir="busctl --system tree org.bluez",
        sonda=_sonda_bluez,
    ),
    Contrato(
        id="pipewire-pactl-json",
        dono="pipewire",
        promessa="o pactl entrega JSON (`--format=json`)",
        conferir="LC_ALL=C pactl --format=json info",
        sonda=_sonda_pactl_json,
    ),
    Contrato(
        id="pipewire-wpctl",
        dono="pipewire",
        promessa="o wpctl fala com o WirePlumber",
        conferir="wpctl status",
        sonda=_sonda_wpctl,
    ),
    Contrato(
        id="systemd-usuario",
        dono="systemd",
        promessa="o systemd de usuário responde ao systemctl --user",
        conferir="systemctl --user show-environment",
        sonda=_sonda_systemd,
    ),
    Contrato(
        id="kernel-nos",
        dono="kernel",
        promessa="uinput, uhid, hidraw e evdev existem como nós",
        conferir="ls -l /dev/uinput /dev/uhid /dev/input /sys/class/hidraw",
        sonda=_sonda_nos_do_kernel,
    ),
    Contrato(
        id="kernel-driver-sony",
        dono="kernel",
        promessa="o kernel em uso tem o driver playstation, ligado ou pronto para carregar",
        conferir="modinfo -F filename hid_playstation",
        sonda=_sonda_driver_sony,
    ),
    Contrato(
        id="steam-localconfig",
        dono="steam",
        promessa=(
            "o localconfig.vdf da Steam abre com a raiz UserLocalConfigStore e guarda o wrapper "
            "dos jogos que o Hefesto aplicou"
        ),
        conferir=(
            "head -c 200 ~/.steam/steam/userdata/*/config/localconfig.vdf; "
            "grep -c hefesto-launch ~/.steam/steam/userdata/*/config/localconfig.vdf"
        ),
        sonda=_sonda_steam,
        cobre=("cfg:localconfig.vdf",),
    ),
    Contrato(
        id="proton-de-terceiros",
        dono="proton",
        promessa="cada Proton em compatibilitytools.d traz compatibilitytool.vdf e o `proton`",
        conferir="ls ~/.steam/steam/compatibilitytools.d/*/",
        sonda=_sonda_proton,
    ),
    Contrato(
        id="cosmic-config",
        dono="cosmic",
        promessa="a configuração pública do COSMIC está em ~/.config/cosmic",
        conferir="ls ~/.config/cosmic",
        sonda=_sonda_cosmic,
    ),
)


def linhas_do_doctor(
    amb: Ambiente | None = None, contratos: Sequence[Contrato] = CONTRATOS
) -> list[tuple[str, str]]:
    """``[(tag, mensagem)]`` no formato do doctor. Quebrou nomeia o contrato e o comando."""
    amb = amb or Ambiente()
    linhas: list[tuple[str, str]] = []
    for c in contratos:
        r = c.sonda(amb)
        if r.estado == OK:
            linhas.append(("[ OK ]", f"{c.id} ({c.dono}): {c.promessa}"))
        elif r.estado == AUSENTE:
            linhas.append(("[INFO]", f"{c.id} ({c.dono}): não se aplica aqui ({r.detalhe})"))
        else:
            linhas.append(
                (
                    "[WARN]",
                    f"o contrato {c.id} ({c.dono}) quebrou: {r.detalhe}. Prometia: {c.promessa}. "
                    f"Confira: {c.conferir}",
                )
            )
    return linhas
