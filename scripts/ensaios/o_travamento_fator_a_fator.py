#!/usr/bin/env python3
"""o_travamento_fator_a_fator.py — o I-1 da O-TRAVAMENTO-SE-SEPARA-UM-FATOR-POR-VEZ-01.

A PERGUNTA QUE ELE RESPONDE
---------------------------
*Quando um controle do rádio cai abaixo de 50 pacotes de movimento por
segundo, o que mais estava acontecendo na mesma janela?* A bancada de 29/09
viu quatro colapsos (01:30, 02:02, 02:13 e 02:37) e não separou a causa: o
jogo, as duas Steam, a memória da placa de vídeo, o modo, a nossa saída e o
par no mesmo adaptador já saíram do «necessário»; a voz no ar, o adaptador 1
e o ar em volta dele, o controle e as vigias do Hefesto ficaram. Este
instrumento mede uma janela por vez (10 s por padrão) com TODOS os fatores na
mesma linha, e o ``resumo`` agrupa as janelas pelo que elas MEDIRAM, e não
pelo rótulo que alguém digitou.

O QUE ELE LÊ, A CADA SEGUNDO
----------------------------
- **o ``state_full``** do daemon, pelo cliente de IPC da casa, COM PRAZO: um
  ``state_full`` que não responde no segundo vale «-» naquele segundo, nunca
  0. (O ``cli.cmd_tray._chamar`` que a ``bancada_do_radio.py`` usa espera sem
  prazo; com o laço do serviço parado, o instrumento pararia junto.) Por
  controle: o jogador, o modelo, o transporte, o adaptador, ``hz_movimento``,
  ``hz_voz``, o mudo, a bateria e ``connected``; da mesa, o jogo da Steam e o
  ``radio_ar`` (o AFH e a entrada que o daemon mediu);
- **o ar, por um medidor PRÓPRIO** (``ar_do_adaptador.MedidorDeAr``, o
  ``HCIGETDEVINFO`` do kernel): a entrada e a saída de cada adaptador, a régua
  independente da do daemon;
- **a varredura**: o ``Discovering`` de cada adaptador
  (``varredura_do_radio.quem_esta_varrendo``);
- **os processos** (``/proc``): a Steam, classificada pelo ``HOME`` do
  ``environ`` (a dela, a de teste sob ``/pytest-of-``, ou outra), o
  ``winedevice.exe``, o pytest vivo e o ``giro_e_buraco.py`` (o I-3). O
  próprio instrumento e quem o chamou ficam FORA da conta: um ``pgrep -f``
  já casou o shell que perguntava;
- **a memória**: ``/proc/buddyinfo`` (ordem 7 a 10) a cada segundo, e o
  ``allocstall`` do ``/proc/vmstat`` no começo e no fim da janela.

E NO FIM DE CADA JANELA: o diário do kernel (NVRM, CRC falho, ``Unexpected
start frame`` e ``Output queue is full``) e o do sistema (os tiques da
``hefesto-bt-health-watchdog`` e da ``hefesto-wifi-usb-vigia``), contados pela
hora de cada linha DENTRO da janela; e o Wi-Fi (a banda e os bytes por
segundo de cada interface sem fio, do ``/proc/net/dev``).

O QUE A LINHA NUNCA LEVA
------------------------
Nenhum endereço: o adaptador sai numerado (1, 2, 3, pela ordem do endereço),
o controle pelo modelo e pelo número de chegada naquele modelo («White 1»,
«White 2», que não mudam enquanto o ``uniq`` for o mesmo), e a interface do
Wi-Fi por número («wifi 1»). Nenhum serial, nem o nome dos nós de som. A chave
de cada controle é o ``uniq``, e ele nunca sai do processo.

A JANELA FORA DO VEREDITO
-------------------------
Uma janela que falha uma condição da bancada não some: ela sai marcada, com o
motivo, e não conta como colapso nem como não-colapso. As condições: um
adaptador varrendo (ou o ``Discovering`` em «não sei»), um pytest vivo, a
Steam de teste viva, o daemon mudo a janela inteira, e **as réguas que
discordam**: a soma de movimento e voz dos controles de um adaptador longe da
entrada que o INSTRUMENTO mediu (e não da do daemon, que vem da mesma fonte
dos Hz) em mais de 25% **e** em mais de 50 pacotes/s. O piso absoluto existe
por causa do colapso: às 02:37, 36 contra 20 é 80% e só 16 pacotes/s.

ELE NÃO ESCREVE NADA NO APARELHO
--------------------------------
Lê o IPC, o ``/proc``, o kernel por ``ioctl`` de leitura e os diários. Nenhum
report, nenhum ``SET_FEATURE``, nenhum comando ao rádio.

USO
---
    o_travamento_fator_a_fator.py janela --segundos 10 --saida <jsonl> [--passo <rótulo>]
    o_travamento_fator_a_fator.py resumo <jsonl> [--json]

As réguas: ``tests/unit/test_o_travamento_fator_a_fator.py``.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import itertools
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

VERSAO = 1

PISO_DO_COLAPSO = 50.0

DISCORDA_RELATIVO = 0.25
DISCORDA_ABSOLUTO = 50.0

VOZ_NO_AR = 1.0

#: O prazo de cada ``state_full``: o segundo inteiro não cabe, porque o resto
PRAZO_DO_ESTADO_S = 0.8

CONTAGENS_DO_KERNEL: dict[str, re.Pattern[str]] = {
    "nvrm": re.compile(r"NVRM"),
    "crc": re.compile(r"DualSense input CRC's check failed"),
    "start_frame": re.compile(r"Unexpected start frame"),
    "fila_cheia": re.compile(r"Output queue is full"),
}

VIGIAS: dict[str, str] = {
    "vigia_do_radio": "hefesto-bt-health-watchdog.service",
    "vigia_do_wifi": "hefesto-wifi-usb-vigia.service",
}

MARCA_DA_STEAM_DE_TESTE = "/pytest-of-"


def _numero(valor: Any) -> float | None:
    """O valor como ``float``; ``None`` para o que não é número (o «-»)."""
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    numero = float(valor)
    return numero if math.isfinite(numero) else None


def _estatisticas(valores: Sequence[float]) -> dict[str, float] | None:
    """Média, mediana e mínimo, ou ``None`` sem nenhum valor (o «-», nunca 0)."""
    if not valores:
        return None
    return {
        "média": round(statistics.fmean(valores), 1),
        "mediana": round(statistics.median(valores), 1),
        "mínimo": round(min(valores), 1),
    }


def _mediana(valores: Sequence[float]) -> float | None:
    return round(statistics.median(valores), 1) if valores else None


def _media(valores: Sequence[float]) -> float | None:
    return round(statistics.fmean(valores), 1) if valores else None


class Rotulos:
    """Os nomes da linha, que valem o processo inteiro.

    O controle é chaveado pelo ``uniq`` e sai pelo modelo com o número de
    chegada naquele modelo: dois «White» são «White 1» e «White 2», e trocar a
    ordem deles no ``state_full`` não troca os números de ninguém. O adaptador
    sai numerado pela ordem do endereço (a mesma do ``passo.sh`` da bancada), e
    a interface do Wi-Fi por número.
    """

    def __init__(self) -> None:
        self._controles: dict[str, str] = {}
        self._chegadas: Counter[str] = Counter()
        self._adaptadores: dict[str, int] = {}
        self._wifi: dict[str, int] = {}

    def controle(self, uniq: str, modelo: str | None) -> str:
        rotulo = self._controles.get(uniq)
        if rotulo is None:
            nome = (modelo or "").strip() or "DualSense"
            self._chegadas[nome] += 1
            rotulo = f"{nome} {self._chegadas[nome]}"
            self._controles[uniq] = rotulo
        return rotulo

    def controles(self) -> list[str]:
        return list(self._controles.values())

    def conhecer_adaptadores(self, enderecos: Iterable[str]) -> None:
        for endereco in sorted({e for e in enderecos if e}):
            if endereco not in self._adaptadores:
                self._adaptadores[endereco] = len(self._adaptadores) + 1

    def adaptador(self, endereco: str | None) -> int | None:
        if not endereco:
            return None
        self.conhecer_adaptadores([endereco])
        return self._adaptadores[endereco]

    def wifi(self, interface: str) -> str:
        if interface not in self._wifi:
            self._wifi[interface] = len(self._wifi) + 1
        return f"wifi {self._wifi[interface]}"


def _ler(caminho: str) -> bytes | None:
    try:
        with open(caminho, "rb") as arquivo:
            return arquivo.read()
    except OSError:
        return None


def _home_do_processo(raiz: str, pid: str) -> str | None:
    bruto = _ler(os.path.join(raiz, pid, "environ"))
    if not bruto:
        return None
    for item in bruto.split(b"\0"):
        if item.startswith(b"HOME="):
            return item[5:].decode("utf-8", "replace")
    return None


def processos_da_mesa(raiz: str, home_dela: str, excluir: Iterable[int]) -> dict[str, int]:
    """A contagem dos processos que são fator, sem o instrumento nem quem o chamou."""
    fora = {int(p) for p in excluir}
    contagem: Counter[str] = Counter(
        {"steam_dela": 0, "steam_de_teste": 0, "steam_outra": 0, "winedevice": 0,
         "pytest": 0, "giro_e_buraco": 0}
    )
    try:
        nomes = os.listdir(raiz)
    except OSError:
        return dict(contagem)
    for pid in nomes:
        if not pid.isdigit() or int(pid) in fora:
            continue
        bruto = _ler(os.path.join(raiz, pid, "cmdline"))
        if not bruto:
            continue
        argv = [a.decode("utf-8", "replace") for a in bruto.split(b"\0") if a]
        if not argv:
            continue
        bases = [os.path.basename(a) for a in argv]
        if "steam" in bases:
            home = _home_do_processo(raiz, pid)
            if home is not None and home.rstrip("/") == home_dela.rstrip("/"):
                contagem["steam_dela"] += 1
            elif home is not None and MARCA_DA_STEAM_DE_TESTE in home:
                contagem["steam_de_teste"] += 1
            else:
                contagem["steam_outra"] += 1
        if any(b.lower().endswith("winedevice.exe") for b in bases):
            contagem["winedevice"] += 1
        if any(b in ("pytest", "py.test") for b in bases) or any(
            a == "-m" and b == "pytest" for a, b in itertools.pairwise(argv)
        ):
            contagem["pytest"] += 1
        if "giro_e_buraco.py" in bases:
            contagem["giro_e_buraco"] += 1
    return dict(contagem)


def blocos_livres(raiz: str) -> dict[str, int] | None:
    """Os blocos livres de ordem 7 a 10, somados nas zonas (``/proc/buddyinfo``)."""
    bruto = _ler(os.path.join(raiz, "buddyinfo"))
    if bruto is None:
        return None
    ordens = {str(o): 0 for o in range(7, 11)}
    for linha in bruto.decode("utf-8", "replace").splitlines():
        campos = linha.split()
        if "zone" not in campos:
            continue
        numeros = [c for c in campos[campos.index("zone") + 2:] if c.isdigit()]
        for ordem in range(7, 11):
            if ordem < len(numeros):
                ordens[str(ordem)] += int(numeros[ordem])
    return ordens


def allocstall(raiz: str) -> int | None:
    """A soma dos ``allocstall_*`` do ``/proc/vmstat``."""
    bruto = _ler(os.path.join(raiz, "vmstat"))
    if bruto is None:
        return None
    total = 0
    for linha in bruto.decode("utf-8", "replace").splitlines():
        nome, _, valor = linha.partition(" ")
        if nome.startswith("allocstall") and valor.strip().isdigit():
            total += int(valor)
    return total


def bytes_do_wifi(raiz: str) -> dict[str, int]:
    """``{interface: bytes recebidos + enviados}`` das interfaces sem fio (``wl*``)."""
    bruto = _ler(os.path.join(raiz, "net", "dev"))
    if bruto is None:
        return {}
    contas: dict[str, int] = {}
    for linha in bruto.decode("utf-8", "replace").splitlines():
        nome, sep, resto = linha.partition(":")
        nome = nome.strip()
        if not sep or not nome.startswith("wl"):
            continue
        campos = resto.split()
        if len(campos) >= 9 and campos[0].isdigit() and campos[8].isdigit():
            contas[nome] = int(campos[0]) + int(campos[8])
    return contas


def banda_pelo_iw(interface: str) -> str | None:
    """A banda em que a interface está associada, pelo ``iw dev <if> link``."""
    try:
        saida = subprocess.run(
            ["iw", "dev", interface, "link"], capture_output=True, text=True,
            timeout=1.0, check=False, env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    achado = re.search(r"freq:\s*(\d+)", saida.stdout or "")
    if saida.returncode != 0 or achado is None:
        return None
    mhz = int(achado.group(1))
    if 2400 <= mhz < 2500:
        return "2,4"
    if 4900 <= mhz < 5925:
        return "5"
    if 5925 <= mhz < 7125:
        return "6"
    return None


def _hora_da_linha(linha: str) -> float | None:
    """A hora (epoch) de uma linha ``-o short-iso-precise`` do ``journalctl``."""
    cabeca = linha.split(" ", 1)[0]
    try:
        return datetime.fromisoformat(cabeca).timestamp()
    except ValueError:
        return None


def linhas_da_janela(texto: str | None, inicio: float, fim: float) -> list[str] | None:
    """As linhas do diário cuja hora cai em ``[inicio, fim)``. ``None`` = não sei."""
    if texto is None:
        return None
    dentro: list[str] = []
    for linha in texto.splitlines():
        hora = _hora_da_linha(linha)
        if hora is not None and inicio <= hora < fim:
            dentro.append(linha)
    return dentro


def contar_no_kernel(linhas: list[str] | None) -> dict[str, int] | None:
    if linhas is None:
        return None
    return {nome: sum(1 for ln in linhas if padrao.search(ln))
            for nome, padrao in CONTAGENS_DO_KERNEL.items()}


def contar_as_vigias(linhas: list[str] | None) -> dict[str, int | None]:
    if linhas is None:
        return dict.fromkeys(VIGIAS)
    return {nome: sum(1 for ln in linhas if f"Starting {unidade}" in ln)
            for nome, unidade in VIGIAS.items()}


def _journalctl(argv: list[str]) -> str | None:
    try:
        saida = subprocess.run(argv, capture_output=True, text=True, timeout=5.0, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return saida.stdout if saida.returncode == 0 else None


def diario_do_kernel(inicio: float, fim: float) -> str | None:
    return _journalctl(["journalctl", "-k", "-q", "--no-pager", "-o", "short-iso-precise",
                        "--since", f"@{inicio:.3f}", "--until", f"@{fim:.3f}"])


def diario_do_sistema(inicio: float, fim: float) -> str | None:
    unidades: list[str] = []
    for unidade in VIGIAS.values():
        unidades += ["-u", unidade]
    return _journalctl(["journalctl", "-q", "--no-pager", "-o", "short-iso-precise",
                        *unidades, "--since", f"@{inicio:.3f}", "--until", f"@{fim:.3f}"])


@dataclass
class Amostra:
    """Um segundo da janela. ``estado`` é ``None`` quando o daemon não respondeu."""

    instante: float
    estado: dict[str, Any] | None
    ar: dict[str, dict[str, float | None]] = field(default_factory=dict)
    varrendo: int | None = 0
    processos: dict[str, int] = field(default_factory=dict)
    memoria: dict[str, int] | None = None


def ar_em_numeros(amostra: Mapping[str, Any] | None) -> dict[str, dict[str, float | None]]:
    """``MedidorDeAr.amostrar()`` → ``{endereço: {entrada, saida}}``, sem o «sem Bluetooth»."""
    fora: dict[str, dict[str, float | None]] = {}
    for endereco, ar in dict(amostra or {}).items():
        if not endereco:
            continue
        fora[str(endereco).lower()] = {
            "entrada": _numero(getattr(ar, "entrada_por_s", None)),
            "saida": _numero(getattr(ar, "saida_por_s", None)),
        }
    return fora


def varrendo_de(varredura: Any) -> int | None:
    """Quantos adaptadores varrem; ``None`` quando a leitura não ouviu a mesa toda."""
    if varredura is None:
        return None
    varrendo = len(getattr(varredura, "varrendo", ()) or ())
    if varrendo:
        return varrendo
    if getattr(varredura, "motivo", "") or getattr(varredura, "mudos", ()):
        return None
    return 0


@dataclass
class Portas:
    """Tudo o que o instrumento lê do mundo. A régua troca cada uma por um dublê."""

    estado: Callable[[], dict[str, Any] | None]
    ar: Callable[[], Mapping[str, Any] | None]
    varredura: Callable[[], Any]
    raiz_proc: str = "/proc"
    home_dela: str = field(default_factory=lambda: os.path.expanduser("~"))
    excluir: frozenset[int] = field(default_factory=lambda: frozenset({os.getpid(), os.getppid()}))
    banda_do_wifi: Callable[[str], str | None] = banda_pelo_iw
    diario_do_kernel: Callable[[float, float], str | None] = diario_do_kernel
    diario_do_sistema: Callable[[float, float], str | None] = diario_do_sistema
    relogio: Callable[[], float] = time.time
    monotonico: Callable[[], float] = time.monotonic
    dormir: Callable[[float], None] = time.sleep


def amostrar(portas: Portas) -> Amostra:
    """Um segundo: o ``state_full`` com prazo, o ar, a varredura, o ``/proc``."""
    instante = portas.relogio()
    estado = portas.estado()
    try:
        ar = ar_em_numeros(portas.ar())
    except Exception:
        ar = {}
    try:
        varrendo = varrendo_de(portas.varredura())
    except Exception:
        varrendo = None
    return Amostra(
        instante=instante,
        estado=estado if isinstance(estado, dict) else None,
        ar=ar,
        varrendo=varrendo,
        processos=processos_da_mesa(portas.raiz_proc, portas.home_dela, portas.excluir),
        memoria=blocos_livres(portas.raiz_proc),
    )


def _controles_do_estado(estado: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    fora: dict[str, dict[str, Any]] = {}
    for entrada in estado.get("controllers") or []:
        if not isinstance(entrada, dict):
            continue
        uniq = entrada.get("uniq")
        if not isinstance(uniq, str) or not uniq:
            continue
        bruto = entrada.get("audio")
        audio: dict[str, Any] = bruto if isinstance(bruto, dict) else {}
        fora[uniq] = {
            "conectado": entrada.get("connected") is not False,
            "movimento": _numero(entrada.get("hz_movimento")),
            "voz": _numero(entrada.get("hz_voz")),
            "transporte": entrada.get("transport"),
            "adaptador": str(entrada.get("adaptador") or "").lower() or None,
            "jogador": entrada.get("player"),
            "modelo": entrada.get("modelo") if isinstance(entrada.get("modelo"), str) else None,
            # O caminho do pad (``uinput`` no Xbox, ``uhid`` no DualSense): a MATRIZ.
            "pad": entrada.get("vpad_backend") if isinstance(entrada.get("vpad_backend"), str)
            else None,
            "bateria": _numero(entrada.get("battery_pct")),
            "mic_mudo": audio.get("mic_mudo"),
            "mic_mudo_desejado": audio.get("mic_mudo_desejado"),
        }
    return fora


def _jogo_do_estado(estado: Mapping[str, Any]) -> int | None:
    jogo = estado.get("jogo_steam")
    if not isinstance(jogo, dict):
        return None
    appid = jogo.get("appid")
    return int(appid) if isinstance(appid, int) and not isinstance(appid, bool) else None


def as_reguas_discordam(soma: float | None, entrada: float | None) -> bool:
    """A soma dos Hz longe da entrada do INSTRUMENTO em mais de 25% e de 50/s."""
    if soma is None or entrada is None:
        return False
    distancia = abs(soma - entrada)
    return distancia > DISCORDA_ABSOLUTO and distancia > DISCORDA_RELATIVO * entrada


@dataclass
class ContextoDaJanela:
    """O que a janela lê só no começo e no fim, e não a cada segundo."""

    passo: str = ""
    kernel: str | None = None
    sistema: str | None = None
    wifi_antes: dict[str, int] = field(default_factory=dict)
    wifi_depois: dict[str, int] = field(default_factory=dict)
    bandas: dict[str, str | None] = field(default_factory=dict)
    allocstall_antes: int | None = None
    allocstall_depois: int | None = None


def linha_da_janela(
    amostras: Sequence[Amostra],
    inicio: float,
    fim: float,
    rotulos: Rotulos,
    contexto: ContextoDaJanela,
) -> dict[str, Any]:
    """A linha JSON de UMA janela. Nenhum endereço entra nela."""
    respostas = [a for a in amostras if a.estado is not None]
    por_uniq: dict[str, list[dict[str, Any]]] = {}
    radio_ar: dict[str, list[Mapping[str, Any]]] = {}
    jogos: list[int] = []
    tiques: list[float] = []
    for amostra in respostas:
        estado = amostra.estado or {}
        for uniq, leitura in _controles_do_estado(estado).items():
            rotulos.controle(uniq, leitura["modelo"])
            por_uniq.setdefault(uniq, []).append(leitura)
        for endereco, ar in dict(estado.get("radio_ar") or {}).items():
            if endereco and isinstance(ar, dict):
                radio_ar.setdefault(str(endereco).lower(), []).append(ar)
        appid = _jogo_do_estado(estado)
        if appid is not None:
            jogos.append(appid)
        tique = _numero((estado.get("counters") or {}).get("poll.tick"))
        if tique is not None:
            tiques.append(tique)

    enderecos: set[str] = set(radio_ar)
    for amostra in amostras:
        enderecos.update(amostra.ar)
    for leituras in por_uniq.values():
        enderecos.update(ln["adaptador"] for ln in leituras if ln["adaptador"])
    rotulos.conhecer_adaptadores(enderecos)

    controles: dict[str, Any] = {}
    medias: dict[str, float] = {}
    rotulo_de: dict[str, str] = {}
    for uniq in list(por_uniq):
        rotulo_de[uniq] = rotulos.controle(uniq, None)
    for rotulo in rotulos.controles():
        controles[rotulo] = {
            "jogador": None, "transporte": None, "adaptador": None, "conectado": False,
            "segundos": 0, "movimento": None, "voz": None, "mic_mudo": None,
            "mic_mudo_desejado": None, "bateria": None, "pad": None,
        }
    for uniq, leituras in por_uniq.items():
        rotulo = rotulo_de[uniq]
        vivas = [ln for ln in leituras if ln["conectado"]]
        movimento = [ln["movimento"] for ln in vivas if ln["movimento"] is not None]
        voz = [ln["voz"] for ln in vivas if ln["voz"] is not None]
        ultima = leituras[-1]
        controles[rotulo] = {
            "jogador": ultima["jogador"],
            "transporte": ultima["transporte"],
            "adaptador": rotulos.adaptador(ultima["adaptador"]),
            "conectado": bool(vivas),
            "segundos": len(movimento),
            "movimento": _estatisticas(movimento),
            "voz": _estatisticas(voz),
            "mic_mudo": ultima["mic_mudo"],
            "mic_mudo_desejado": ultima["mic_mudo_desejado"],
            "bateria": ultima["bateria"],
            "pad": ultima["pad"],
        }
        if movimento:
            medias[rotulo] = (_media(movimento) or 0.0) + (_media(voz) or 0.0)

    adaptadores: dict[str, Any] = {}
    for endereco in sorted(enderecos, key=lambda e: rotulos.adaptador(e) or 0):
        numero = rotulos.adaptador(endereco)
        entradas = [e for a in amostras if (e := (a.ar.get(endereco) or {}).get("entrada")) is not None]
        saidas = [s for a in amostras if (s := (a.ar.get(endereco) or {}).get("saida")) is not None]
        afh = [float(len(ar["canais_evitados"])) for ar in radio_ar.get(endereco, [])
               if isinstance(ar.get("canais_evitados"), list)]
        do_daemon = [n for ar in radio_ar.get(endereco, [])
                     if (n := _numero(ar.get("entrada_por_s"))) is not None]
        nele = sorted({rotulo_de[u] for u, lns in por_uniq.items()
                       if any(ln["adaptador"] == endereco and ln["conectado"] for ln in lns)})
        somas = [medias[r] for r in nele if r in medias]
        soma = round(sum(somas), 1) if somas else None
        entrada = _media(entradas)
        adaptadores[str(numero)] = {
            "controles": nele,
            "entrada": entrada,
            "saida": _media(saidas),
            "entrada_do_daemon": _mediana(do_daemon),
            "afh": _mediana(afh),
            "soma_dos_hz": soma,
            "discordam": as_reguas_discordam(soma, entrada),
        }

    processos: Counter[str] = Counter()
    for amostra in amostras:
        for nome, n in amostra.processos.items():
            processos[nome] = max(processos[nome], n)
    maior = max((a.varrendo for a in amostras if a.varrendo is not None), default=0)
    varrendo: int | None = maior
    if not maior and any(a.varrendo is None for a in amostras):
        varrendo = None

    duracao = max(fim - inicio, 1e-9)
    wifi: dict[str, Any] = {}
    for interface in sorted(set(contexto.wifi_antes) | set(contexto.wifi_depois)):
        antes = contexto.wifi_antes.get(interface)
        depois = contexto.wifi_depois.get(interface)
        taxa = (round((depois - antes) / duracao, 1)
                if antes is not None and depois is not None and depois >= antes else None)
        wifi[rotulos.wifi(interface)] = {"banda": contexto.bandas.get(interface),
                                         "bytes_por_s": taxa}

    vigias = contar_as_vigias(linhas_da_janela(contexto.sistema, inicio, fim))
    kernel = contar_no_kernel(linhas_da_janela(contexto.kernel, inicio, fim))
    memorias = [a.memoria for a in amostras if a.memoria is not None]
    alloc = (contexto.allocstall_depois - contexto.allocstall_antes
             if contexto.allocstall_antes is not None and contexto.allocstall_depois is not None
             else None)

    fatores = {
        "steam_dela": processos["steam_dela"],
        "steam_de_teste": processos["steam_de_teste"],
        "steam_outra": processos["steam_outra"],
        "jogo": 1 if (jogos or processos["winedevice"]) else (0 if respostas else None),
        "jogo_appid": jogos[-1] if jogos else None,
        "winedevice": processos["winedevice"],
        "pytest": processos["pytest"],
        "varrendo": varrendo,
        "i3_giro_e_buraco": processos["giro_e_buraco"],
        **vigias,
        "wifi": wifi,
    }

    fora: list[str] = []
    if varrendo is None:
        fora.append("não sei se algum adaptador varria")
    elif varrendo > 0:
        fora.append("um adaptador varria")
    if processos["pytest"] > 0:
        fora.append("um pytest vivo")
    if processos["steam_de_teste"] > 0:
        fora.append("a Steam de teste viva")
    if not respostas:
        fora.append("o daemon não respondeu na janela")
    for chave, adaptador in adaptadores.items():
        if adaptador["discordam"]:
            fora.append(f"as réguas discordam no adaptador {chave}")

    colapso = sorted(
        rotulo for rotulo, c in controles.items()
        if c["conectado"] and c["movimento"] is not None
        and c["movimento"]["mediana"] < PISO_DO_COLAPSO
    )
    return {
        "instrumento": "o_travamento_fator_a_fator",
        "versão": VERSAO,
        "passo": contexto.passo,
        "inicio": datetime.fromtimestamp(inicio).isoformat(timespec="seconds"),
        "fim": datetime.fromtimestamp(fim).isoformat(timespec="seconds"),
        "segundos": len(amostras),
        "daemon": {
            "respostas": len(respostas),
            "sem_resposta": len(amostras) - len(respostas),
            "tiques": (tiques[-1] - tiques[0]) if len(tiques) >= 2 else None,
        },
        "controles": controles,
        "adaptadores": adaptadores,
        "fatores": fatores,
        "kernel": kernel,
        "memoria": {
            "blocos_7_10_min": min(sum(m.values()) for m in memorias) if memorias else None,
            "ordens_7_10": memorias[-1] if memorias else None,
            "allocstall": alloc,
        },
        "colapso": colapso,
        "veredito": not fora,
        "fora_do_veredito": fora,
    }


def medir(
    portas: Portas,
    *,
    segundos: int,
    janelas: int,
    passo: str,
    escrever: Callable[[dict[str, Any]], None],
    rotulos: Rotulos | None = None,
) -> int:
    """Mede ``janelas`` janelas de ``segundos`` amostras (0 = até o Ctrl-C)."""
    rotulos = rotulos if rotulos is not None else Rotulos()
    feitas = 0
    while janelas <= 0 or feitas < janelas:
        contexto = ContextoDaJanela(
            passo=passo,
            wifi_antes=bytes_do_wifi(portas.raiz_proc),
            allocstall_antes=allocstall(portas.raiz_proc),
        )
        inicio = portas.relogio()
        amostras: list[Amostra] = []
        proximo = portas.monotonico()
        for _ in range(max(1, segundos)):
            amostras.append(amostrar(portas))
            proximo += 1.0
            falta = proximo - portas.monotonico()
            if falta > 0:
                portas.dormir(falta)
            else:
                proximo = portas.monotonico()
        fim = portas.relogio()
        contexto.wifi_depois = bytes_do_wifi(portas.raiz_proc)
        contexto.allocstall_depois = allocstall(portas.raiz_proc)
        contexto.bandas = {i: portas.banda_do_wifi(i) for i in contexto.wifi_depois}
        contexto.kernel = portas.diario_do_kernel(inicio, fim)
        contexto.sistema = portas.diario_do_sistema(inicio, fim)
        escrever(linha_da_janela(amostras, inicio, fim, rotulos, contexto))
        feitas += 1
    return feitas


def fatores_do_grupo(linha: Mapping[str, Any]) -> dict[str, Any]:
    """O que a janela MEDIU e que separa um grupo do outro. O rótulo não entra."""
    fatores = linha.get("fatores") or {}
    controles = linha.get("controles") or {}
    arranjo = sorted(
        [str(numero), list(a.get("controles") or [])]
        for numero, a in (linha.get("adaptadores") or {}).items()
        if a.get("controles")
    )
    cabo = sorted(r for r, c in controles.items()
                  if c.get("conectado") and c.get("transporte") == "usb")
    voz = sorted(r for r, c in controles.items()
                 if c.get("conectado") and (c.get("voz") or {}).get("mediana") is not None
                 and c["voz"]["mediana"] > VOZ_NO_AR)
    pads = sorted({str(c["pad"]) for c in controles.values()
                   if c.get("conectado") and c.get("pad")})
    return {
        "steam_dela": 1 if fatores.get("steam_dela") else 0,
        "jogo": fatores.get("jogo"),
        "arranjo": arranjo,
        "cabo": cabo,
        "voz_no_ar": voz,
        "pads": pads,
    }


def resumir(linhas: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Os grupos de janelas, pelo que elas mediram, na ordem em que apareceram."""
    grupos: dict[str, dict[str, Any]] = {}
    for linha in linhas:
        fatores = fatores_do_grupo(linha)
        chave = json.dumps(fatores, sort_keys=True, ensure_ascii=False)
        grupo = grupos.setdefault(chave, {
            "fatores": fatores, "janelas": 0, "no_veredito": 0, "com_colapso": 0,
            "passos": [], "fora": Counter(), "_mov": {}, "_min": {}, "_entrada": {}, "_afh": {},
        })
        grupo["janelas"] += 1
        passo = linha.get("passo") or ""
        if passo and passo not in grupo["passos"]:
            grupo["passos"].append(passo)
        if not linha.get("veredito"):
            for motivo in linha.get("fora_do_veredito") or []:
                grupo["fora"][motivo] += 1
            continue
        grupo["no_veredito"] += 1
        if linha.get("colapso"):
            grupo["com_colapso"] += 1
        for rotulo, controle in (linha.get("controles") or {}).items():
            movimento = controle.get("movimento")
            if not controle.get("conectado") or not movimento:
                continue
            grupo["_mov"].setdefault(rotulo, []).append(movimento["mediana"])
            grupo["_min"].setdefault(rotulo, []).append(movimento["mínimo"])
        for numero, adaptador in (linha.get("adaptadores") or {}).items():
            if adaptador.get("entrada") is not None:
                grupo["_entrada"].setdefault(numero, []).append(adaptador["entrada"])
            if adaptador.get("afh") is not None:
                grupo["_afh"].setdefault(numero, []).append(adaptador["afh"])
    fora: list[dict[str, Any]] = []
    for grupo in grupos.values():
        controles = {
            rotulo: {"mediana": _mediana(grupo["_mov"][rotulo]),
                     "mínimo": min(grupo["_min"][rotulo])}
            for rotulo in grupo["_mov"]
        }
        adaptadores = {
            numero: {"entrada": _mediana(grupo["_entrada"].get(numero, [])),
                     "afh": _mediana(grupo["_afh"].get(numero, []))}
            for numero in sorted(set(grupo["_entrada"]) | set(grupo["_afh"]), key=int)
        }
        fora.append({
            "fatores": grupo["fatores"],
            "janelas": grupo["janelas"],
            "no_veredito": grupo["no_veredito"],
            "com_colapso": grupo["com_colapso"],
            "passos": grupo["passos"],
            "controles": controles,
            "adaptadores": adaptadores,
            "fora_do_veredito": dict(grupo["fora"]),
        })
    return fora


def _ou_traco(valor: Any) -> str:
    return "-" if valor is None else str(valor)


def resumo_em_texto(grupos: Sequence[Mapping[str, Any]]) -> str:
    partes: list[str] = []
    for n, grupo in enumerate(grupos, 1):
        f = grupo["fatores"]
        arranjo = "; ".join(f"{numero}: {' + '.join(nomes)}" for numero, nomes in f["arranjo"])
        partes.append(
            f"grupo {n} · Steam dela {f['steam_dela']} · jogo {_ou_traco(f['jogo'])} · "
            f"arranjo [{arranjo or '-'}] · cabo [{', '.join(f['cabo']) or '-'}] · "
            f"voz no ar [{', '.join(f['voz_no_ar']) or '-'}] · "
            f"pads [{', '.join(f['pads']) or '-'}]"
        )
        partes.append(
            f"  janelas {grupo['janelas']} · no veredito {grupo['no_veredito']} · "
            f"com colapso {grupo['com_colapso']} · passos {', '.join(grupo['passos']) or '-'}"
        )
        for rotulo, c in grupo["controles"].items():
            partes.append(f"  {rotulo}: mediana {_ou_traco(c['mediana'])} · "
                          f"mínimo {_ou_traco(c['mínimo'])}")
        for numero, a in grupo["adaptadores"].items():
            partes.append(f"  adaptador {numero}: entrada {_ou_traco(a['entrada'])} · "
                          f"AFH {_ou_traco(a['afh'])}")
        for motivo, quantas in grupo["fora_do_veredito"].items():
            partes.append(f"  fora do veredito: {motivo} ({quantas})")
    return "\n".join(partes)


def ler_jsonl(caminho: str) -> list[dict[str, Any]]:
    linhas: list[dict[str, Any]] = []
    with open(caminho, encoding="utf-8") as arquivo:
        for bruta in arquivo:
            bruta = bruta.strip()
            if not bruta:
                continue
            with contextlib.suppress(json.JSONDecodeError):
                linha = json.loads(bruta)
                if isinstance(linha, dict) and linha.get("instrumento") == "o_travamento_fator_a_fator":
                    linhas.append(linha)
    return linhas


def estado_pelo_ipc(
    prazo: float = PRAZO_DO_ESTADO_S, caminho: Path | None = None
) -> dict[str, Any] | None:
    """O ``state_full`` com prazo; ``None`` quando o daemon não respondeu nele.

    Com o laço do serviço parado o soquete ainda aceita a conexão (quem aceita
    é o kernel, até a fila encher) e a resposta nunca vem: sem prazo, o
    instrumento pararia junto com o daemon que ele mede.
    """
    from hefesto_dualsense4unix.cli.ipc_client import IpcClient

    async def _ir() -> Any:
        async with IpcClient.connect(caminho, timeout=prazo) as cliente:
            return await cliente.call("daemon.state_full", {}, timeout=prazo)

    try:
        resposta = asyncio.run(asyncio.wait_for(_ir(), prazo + 0.1))
    except Exception:
        return None
    return resposta if isinstance(resposta, dict) else None


def portas_de_verdade() -> Portas:
    from hefesto_dualsense4unix.integrations.ar_do_adaptador import MedidorDeAr
    from hefesto_dualsense4unix.integrations.varredura_do_radio import quem_esta_varrendo

    medidor = MedidorDeAr()
    return Portas(estado=estado_pelo_ipc, ar=medidor.amostrar, varredura=quem_esta_varrendo)


def _commit_da_mesa() -> str:
    try:
        import hefesto_dualsense4unix

        raiz = Path(hefesto_dualsense4unix.__file__).resolve().parents[2]
        saida = subprocess.run(["git", "-C", str(raiz), "rev-parse", "--short", "HEAD"],
                               capture_output=True, text=True, timeout=5.0, check=False)
        return f"{saida.stdout.strip() or 'não sei'} em {raiz}"
    except Exception:
        return "não sei"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="comando", required=True)
    janela = sub.add_parser("janela", help="mede janelas e escreve uma linha JSON por janela")
    janela.add_argument("--segundos", type=int, default=10)
    janela.add_argument("--janelas", type=int, default=0, help="0 = até o Ctrl-C")
    janela.add_argument("--saida", required=True)
    janela.add_argument("--passo", default="")
    resumo = sub.add_parser("resumo", help="agrupa as janelas pelo que elas mediram")
    resumo.add_argument("jsonl")
    resumo.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.comando == "resumo":
        grupos = resumir(ler_jsonl(args.jsonl))
        print(json.dumps(grupos, ensure_ascii=False, indent=2) if args.json
              else resumo_em_texto(grupos))
        return 0

    from comum import cabecalho_do_instrumento

    print(cabecalho_do_instrumento(
        "o_travamento_fator_a_fator.py",
        "o que mais estava acontecendo quando um controle do rádio caiu abaixo de 50/s?",
        bibliotecas=["hefesto_dualsense4unix"],
    ))
    print(f"  a mesa ............. {_commit_da_mesa()}")
    with open(args.saida, "a", encoding="utf-8", buffering=1) as saida:
        def escrever(linha: dict[str, Any]) -> None:
            saida.write(json.dumps(linha, ensure_ascii=False) + "\n")
            print(f"{linha['fim']}  respostas {linha['daemon']['respostas']}/"
                  f"{linha['segundos']}  colapso {linha['colapso'] or '-'}  "
                  f"fora {linha['fora_do_veredito'] or '-'}", flush=True)

        with contextlib.suppress(KeyboardInterrupt):
            medir(portas_de_verdade(), segundos=args.segundos, janelas=args.janelas,
                  passo=args.passo, escrever=escrever)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    raise SystemExit(main())
