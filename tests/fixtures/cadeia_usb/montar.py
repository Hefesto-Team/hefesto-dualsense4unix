"""O ``/sys`` de mentira da cadeia USB, montado numa pasta com links de verdade.

A forma é a de ``barramento.json``; o teste muda os nós (tira, põe, troca a velocidade ou o
``devnum``) e monta de novo. A base do sistema entra por :meth:`SysDeMentira.base`, o dublê da
libudev.
"""

from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path
from typing import Any

DADOS = Path(__file__).with_name("barramento.json")

SERIAL_FORJADO = "E8473A" + "C0FFEE"

_ATRIBUTOS_DA_TRIPLA = ("bInterfaceClass", "bInterfaceSubClass", "bInterfaceProtocol")
_PORTA = re.compile(r"^(.+)-port[0-9]+$")


def carregar() -> dict[str, Any]:
    """Os dados da forma medida, numa cópia que o teste pode mudar."""
    return copy.deepcopy(json.loads(DADOS.read_text(encoding="utf-8")))


class SysDeMentira:
    """Um ``/sys/bus/usb/devices`` numa pasta temporária."""

    def __init__(self, raiz: Path, dados: dict[str, Any] | None = None) -> None:
        self.raiz = raiz
        self.dados = carregar() if dados is None else dados
        self.barramento = raiz / "bus" / "usb" / "devices"
        self._geracao = 0
        self.montar()

    @property
    def _base(self) -> Path:
        return self.raiz / f"geracao-{self._geracao}"

    @property
    def aparelhos(self) -> Path:
        return self._base / "devices" / "pci0000:00" / "0000:aa:00.0"

    @property
    def drivers(self) -> Path:
        return self._base / "drivers"

    @property
    def nos(self) -> dict[str, Any]:
        return self.dados["nos"]  # type: ignore[no-any-return]

    def caminho(self, nome: str) -> Path:
        """A pasta real de um nó: ``usb3/3-1/3-1.4``."""
        partes: list[str] = []
        atual = nome
        while atual:
            partes.insert(0, atual)
            atual = self.nos[atual]["pai"]
        return self.aparelhos.joinpath(*partes)

    def tirar(self, nome: str) -> None:
        """O nó e tudo o que pendura nele saem do barramento."""
        for filho in [n for n, no in self.nos.items() if no["pai"] == nome]:
            self.tirar(filho)
        self.nos.pop(nome, None)
        self.montar()

    def por(self, nome: str, no: dict[str, Any]) -> None:
        self.nos[nome] = copy.deepcopy(no)
        self.montar()

    def mudar(self, nome: str, **atributos: str) -> None:
        self.nos[nome]["attrs"].update(atributos)
        self.montar()

    def base(self, syspath: str, propriedade: str) -> str | None:
        """O dublê da libudev: a linha da base pelo nome do nó."""
        return self.dados["base"].get(Path(syspath).name, {}).get(propriedade)  # type: ignore[no-any-return]

    def montar(self) -> None:
        """Monta a forma numa geração nova e troca o barramento para ela de uma vez.

        O ouvido relê numa thread enquanto o caso muda o ``/sys``. Apagar e refazer no lugar
        abria uma janela sem aparelho nenhum, e a releitura que caía nela registrava todos como
        «saiu»; no ``/sys`` de verdade cada aparelho sai sozinho. A troca é o ``rename`` de um
        link, e a geração velha fica no disco para quem ainda a lê.
        """
        self._geracao += 1
        barramento = self._base / "bus" / "usb" / "devices"
        barramento.mkdir(parents=True)
        portas: dict[str, Path] = {}
        pares: dict[str, str] = {}
        for nome in sorted(self.nos, key=lambda n: len(self.caminho(n).parts)):
            no = self.nos[nome]
            pasta = self.caminho(nome)
            pasta.mkdir(parents=True, exist_ok=True)
            for atributo, valor in no["attrs"].items():
                _escrever(pasta / atributo, f"{valor}\n")
            if no.get("bos"):
                (pasta / "bos_descriptors").write_bytes(bytes.fromhex(no["bos"]))
            if no.get("serial_forjado"):
                _escrever(pasta / "serial", SERIAL_FORJADO + "\n")
            (barramento / nome).symlink_to(pasta)
            for interface, dados in no.get("interfaces", {}).items():
                dentro = pasta / interface
                dentro.mkdir()
                tripla = dados["tripla"]
                for i, atributo in enumerate(_ATRIBUTOS_DA_TRIPLA):
                    _escrever(dentro / atributo, tripla[2 * i:2 * i + 2] + "\n")
                if dados.get("driver"):
                    driver = self.drivers / dados["driver"]
                    driver.mkdir(parents=True, exist_ok=True)
                    (dentro / "driver").symlink_to(driver)
                for pendura in dados.get("pendura", ()):
                    (dentro / pendura).mkdir()
                for porta, par in dados.get("portas", {}).items():
                    (dentro / porta).mkdir()
                    portas[porta] = dentro / porta
                    pares[porta] = par
                (barramento / interface).symlink_to(dentro)
        for porta, par in pares.items():
            dono = _PORTA.match(par)
            if par in portas and dono is not None and dono.group(1) in self.nos:
                (portas[porta] / "peer").symlink_to(portas[par])
        self.barramento.parent.mkdir(parents=True, exist_ok=True)
        ponteiro = self.barramento.with_name(f".devices-{self._geracao}")
        ponteiro.symlink_to(barramento)
        os.replace(ponteiro, self.barramento)

    def fontes(self) -> dict[str, Any]:
        """Os argumentos de ``ler_o_barramento`` para este ``/sys``."""
        return {"raiz_usb": str(self.barramento), "base": self.base}


def _escrever(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")
