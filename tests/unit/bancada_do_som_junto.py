"""A bancada de mentira do nó de som — o `pactl` que ACEITA, GUARDA e LÊ."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod

#: destes é um controle desta bancada: régua que só passa com os DualSense dela
P1 = "aa:bb:cc:00:00:c1"
P2 = "aa:bb:cc:00:00:c2"

HDMI = "alsa_output.pci-0000_0a_00.1.hdmi-stereo"
FONE = "alsa_output.pci-0000_0a_00.3.analog-stereo"

SINK_P1 = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)

PERFIL = "mesa-do-som-junto"


class Pactl:
    """Um ``pactl`` que aceita, guarda o que está carregado, e sabe LER."""

    def __init__(self, *, placas: tuple[str, ...] = ()) -> None:
        self.argvs: list[list[str]] = []
        self.carregados: dict[str, list[str]] = {}
        self.padrao = HDMI
        self._placas = list(placas)
        self._proximo = 500

    def __call__(self, argv: list[str]) -> str | None:
        self.argvs.append(list(argv))
        if argv[:2] == ["pactl", "load-module"]:
            self._proximo += 1
            self.carregados[str(self._proximo)] = list(argv)
            return f"{self._proximo}\n"
        if argv[:2] == ["pactl", "unload-module"]:
            self.carregados.pop(argv[2], None)
            return ""
        if "get-default-sink" in argv:
            return f"{self.padrao}\n"
        if argv[:4] == ["pactl", "list", "sinks", "short"]:
            vivos = [*self._placas, HDMI, FONE, *self.publicados]
            return "".join(
                f"{60 + i}\t{nome}\tPipeWire\ts16le 2ch 48000Hz\tIDLE\n"
                for i, nome in enumerate(vivos)
            )
        return ""


    @property
    def publicados(self) -> list[str]:
        """Os ``sink_name`` dos ``module-null-sink`` de pé."""
        return [
            a[len("sink_name=") :]
            for argv in self.carregados.values()
            if "module-null-sink" in argv
            for a in argv
            if a.startswith("sink_name=")
        ]

    @property
    def loopbacks(self) -> list[tuple[str, str]]:
        """``(source, sink)`` de cada ``module-loopback`` DE PÉ."""
        fios: list[tuple[str, str]] = []
        for argv in self.carregados.values():
            if "module-loopback" not in argv:
                continue
            campos = {a.split("=", 1)[0]: a.split("=", 1)[1] for a in argv if "=" in a}
            fios.append((campos.get("source", ""), campos.get("sink", "")))
        return fios

    @property
    def descarregados(self) -> list[str]:
        """Os ids que passaram por ``unload-module``, na ordem."""
        return [a[2] for a in self.argvs if a[:2] == ["pactl", "unload-module"]]


class Store:
    """O pedacinho do ``StateStore`` que o subsystem pergunta: o perfil ativo."""

    def __init__(self, perfil: str | None) -> None:
        self.active_profile = perfil


def _caminho_do_perfil(nome: str) -> Path:
    from hefesto_dualsense4unix.profiles.loader import profiles_dir

    return Path(profiles_dir(ensure=True)) / f"{nome}.json"


def escrever_perfil(fontes: dict[str, str], nome: str = PERFIL) -> str:
    """Um perfil DE VERDADE no lar de mentira. Devolve o nome."""
    corpo: dict[str, Any] = {
        "name": nome,
        "match": {"type": "any"},
        "controllers": {
            mod._uniq_de_perfil(uniq): {"speaker": {"volume": 180, "fonte": fonte}}
            for uniq, fonte in fontes.items()
        },
    }
    _caminho_do_perfil(nome).write_text(json.dumps(corpo), encoding="utf-8")
    return nome


def ela_clica(uniq: str, fonte: str, nome: str = PERFIL) -> None:
    """O gesto dela nos três botões: grava a fonte no perfil, e o mtime anda."""
    alvo = _caminho_do_perfil(nome)
    corpo = json.loads(alvo.read_text(encoding="utf-8"))
    corpo["controllers"].setdefault(mod._uniq_de_perfil(uniq), {}).setdefault(
        "speaker", {"volume": 180}
    )["fonte"] = fonte
    alvo.write_text(json.dumps(corpo), encoding="utf-8")
    agora = alvo.stat().st_mtime_ns + 1_000_000
    os.utime(alvo, ns=(agora, agora))


def cabo(uniq: str) -> mod.ControleNaLista:
    return mod.ControleNaLista(uniq=uniq, caminho="/dev/hidraw0", transporte="cabo")


def radio(uniq: str) -> mod.ControleNaLista:
    return mod.ControleNaLista(uniq=uniq, caminho="/dev/hidraw1", transporte="rádio")


def subsystem_e_gerenciador(nome: str | None, **kw: Any) -> tuple[Any, Any]:
    """A fiação de PRODUÇÃO: ``fonte_por_controle=sub._fonte_do_controle``."""
    sub = mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [])
    sub._store = Store(nome)
    return sub, mod.GerenciadorDeNosDeSom(
        fonte_por_controle=sub._fonte_do_controle, **kw
    )
