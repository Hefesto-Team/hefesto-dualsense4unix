#!/usr/bin/env python3
"""o_que_o_ensaio_de_jogo_nao_media.py — uma linha por nota de sessão de jogo sem régua.

O ensaio de jogo sem régua (31/10/2026). Cinco notas de sessão de jogo
nasceram na mão e nunca ganharam script que as repita. Cada subcomando mede uma e imprime
``item N  <nome>  medido=<x>  limite=<sentido><y>  ok|reprovou``; sem dado bastante, ``sem-medida``.

- ``quadro`` (itens 1 e 6, o quadro): os instantes do ``thunk64_vkQueuePresentKHR`` do
  ``winevulkan.so``, com e sem o Hefesto; mede quanto o quadro mediano cresce com ele.
- ``cpu`` (item 6, a CPU): as amostras do ``coletar-cpu`` dos processos do jogo, com e sem o
  Hefesto; mede quanto o pico cresce com ele.
- ``teclado`` (item 2): lê o evdev do teclado virtual do ensaio (``ensaio-teclado``) e conta as
  teclas que chegaram contra as que se mandaram.
- ``roupa`` (item 4): no diário do daemon, entre dois ``launch_arm_roupa`` da mesma roupa, conta
  ``roupa_do_pad``, ``launch_arm_roupa`` e as recriações do pad (``gamepad_emulation_started`` e
  ``coop_player_roupa_trocada``).
- ``gdk`` (item 5): lista os nós de entrada que os processos do jogo têm abertos e diz se o vpad
  pedido (``Hefesto P3``) está entre eles.

O QUE ELE NUNCA FAZ: escrever no aparelho, falar com o daemon ou subir o ``bpftrace``. Ler o evdev é
``O_RDONLY`` sem ``EVIOCGRAB``; o ``/proc`` e o ``/sys`` só se leem, e as raízes se trocam por
``--proc`` e ``--sys``. O ``bpftrace`` pede ``sudo``: o subcomando ``receita-do-quadro`` imprime a
linha exata para quem coordena o ensaio rodar.
"""

from __future__ import annotations

import argparse
import itertools
import math
import os
import re
import select
import struct
import sys
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

LIMITE_DO_QUADRO_PCT = 5.0
LIMITE_DA_CPU_PCT = 10.0
LIMITE_DE_RECRIACOES = 1
ROUPA_DOS_DOIS_JOGOS = "0ce6"
VPAD_DO_P3 = "Hefesto P3"
TECLADO_DO_ENSAIO = "ensaio-teclado"

EVENTOS_DA_ROUPA = ("roupa_do_pad", "launch_arm_roupa")
EVENTOS_DE_RECRIACAO = ("gamepad_emulation_started", "coop_player_roupa_trocada")

EV_KEY = 0x01
FORMATO_DO_EVENTO = "llHHi"
TAMANHO_DO_EVENTO = struct.calcsize(FORMATO_DO_EVENTO)

_LINHA_DO_DIARIO = re.compile(r"\[\s*[a-z]+\s*\]\s+(?P<evento>[a-z_0-9]+)\s*(?P<resto>.*)$")
_PAR = re.compile(r"(\w+)=('[^']*'|\"[^\"]*\"|\S+)")


@dataclass(frozen=True)
class Linha:
    """Uma medida: ``medido`` contra ``limite`` no ``sentido`` dado (``<=`` ou ``>=``)."""

    item: int
    nome: str
    medido: float | None
    limite: float
    sentido: str
    unidade: str = ""
    nota: str = ""

    @property
    def veredito(self) -> str:
        if self.medido is None or math.isnan(self.medido):
            return "sem-medida"
        return "ok" if dentro_do_limite(self.medido, self.limite, self.sentido) else "reprovou"

    def texto(self) -> str:
        medido = "—" if self.medido is None else f"{self.medido:.2f}{self.unidade}"
        partes = [
            f"item {self.item}",
            self.nome,
            f"medido={medido}",
            f"limite={self.sentido}{self.limite:g}{self.unidade}",
            self.veredito,
        ]
        if self.nota:
            partes.append(f"({self.nota})")
        return "  ".join(partes)


def dentro_do_limite(medido: float, limite: float, sentido: str) -> bool:
    if sentido == "<=":
        return medido <= limite
    if sentido == ">=":
        return medido >= limite
    raise ValueError(f"sentido desconhecido: {sentido!r}")


def mediana(valores: Sequence[float]) -> float:
    if not valores:
        return math.nan
    ordem = sorted(valores)
    meio = len(ordem) // 2
    if len(ordem) % 2:
        return ordem[meio]
    return (ordem[meio - 1] + ordem[meio]) / 2


def crescimento_pct(com: float, sem: float) -> float:
    if math.isnan(com) or math.isnan(sem) or sem <= 0:
        return math.nan
    return (com / sem - 1.0) * 100.0


def instantes_do_quadro(linhas: Iterable[str]) -> list[int]:
    """Os instantes em ns que o ``bpftrace`` imprime, um por linha; o resto da saída fica fora."""
    return [int(linha.strip()) for linha in linhas if linha.strip().isdigit()]


def quadros_em_ms(instantes_ns: Sequence[int]) -> list[float]:
    return [(b - a) / 1e6 for a, b in itertools.pairwise(instantes_ns) if b > a]


def linha_do_quadro(com_ms: Sequence[float], sem_ms: Sequence[float]) -> Linha:
    com, sem = mediana(com_ms), mediana(sem_ms)
    nota = "" if math.isnan(com) or math.isnan(sem) else f"mediana com {com:.1f} ms, sem {sem:.1f} ms"
    return Linha(1, "quadro-mediano-com-o-hefesto", crescimento_pct(com, sem),
                 LIMITE_DO_QUADRO_PCT, "<=", "%", nota)


def amostras_da_cpu(linhas: Iterable[str]) -> list[tuple[float, int]]:
    """As amostras do ``coletar-cpu``: ``<segundos> <ticks>`` por linha."""
    amostras: list[tuple[float, int]] = []
    for linha in linhas:
        campos = linha.split()
        if len(campos) != 2:
            continue
        try:
            amostras.append((float(campos[0]), int(campos[1])))
        except ValueError:
            continue
    return amostras


def cpu_por_intervalo(amostras: Sequence[tuple[float, int]], hz: int) -> list[float]:
    """A CPU de cada intervalo entre amostras, em % de um núcleo."""
    fora: list[float] = []
    for (t0, k0), (t1, k1) in itertools.pairwise(amostras):
        if t1 > t0 and k1 >= k0:
            fora.append((k1 - k0) / hz / (t1 - t0) * 100.0)
    return fora


def linha_da_cpu(com_pct: Sequence[float], sem_pct: Sequence[float]) -> Linha:
    com = max(com_pct) if com_pct else math.nan
    sem = max(sem_pct) if sem_pct else math.nan
    nota = "" if math.isnan(com) or math.isnan(sem) else f"pico com {com:.0f}%, sem {sem:.0f}%"
    return Linha(6, "pico-da-cpu-do-jogo-com-o-hefesto", crescimento_pct(com, sem),
                 LIMITE_DA_CPU_PCT, "<=", "%", nota)


def teclas_que_chegaram(bruto: bytes, codigo: int) -> int:
    """Quantos ``EV_KEY`` do código pedido com valor 1 (apertou) há nos ``input_event`` lidos."""
    chegaram = 0
    for inicio in range(0, len(bruto) - TAMANHO_DO_EVENTO + 1, TAMANHO_DO_EVENTO):
        _s, _us, tipo, cod, valor = struct.unpack_from(FORMATO_DO_EVENTO, bruto, inicio)
        if tipo == EV_KEY and cod == codigo and valor == 1:
            chegaram += 1
    return chegaram


def linha_do_teclado(chegaram: int | None, mandadas: int) -> Linha:
    return Linha(2, "teclas-do-teclado-virtual-no-evdev",
                 None if chegaram is None else float(chegaram), float(mandadas), ">=",
                 nota=f"mandadas {mandadas}")


def eventos_do_diario(linhas: Iterable[str]) -> list[tuple[str, dict[str, str]]]:
    """``(evento, campos)`` de cada linha do diário do daemon, no formato do ``journalctl``."""
    fora: list[tuple[str, dict[str, str]]] = []
    for linha in linhas:
        achado = _LINHA_DO_DIARIO.search(linha)
        if achado is None:
            continue
        campos = {k: v.strip("'\"") for k, v in _PAR.findall(achado.group("resto"))}
        fora.append((achado.group("evento"), campos))
    return fora


def contar_a_roupa(
    eventos: Sequence[tuple[str, dict[str, str]]], roupa: str = ROUPA_DOS_DOIS_JOGOS,
) -> dict[str, int] | None:
    """Entre o 1º e o 2º ``launch_arm_roupa`` da ``roupa`` (o 2º incluído), quantos de cada evento.

    ``None`` sem dois lançamentos da roupa no diário.
    """
    marcos = [
        i for i, (evento, campos) in enumerate(eventos)
        if evento == "launch_arm_roupa" and campos.get("roupa", "").lower() == roupa.lower()
    ]
    if len(marcos) < 2:
        return None
    janela = eventos[marcos[0] + 1: marcos[1] + 1]
    contagem = {nome: 0 for nome in (*EVENTOS_DA_ROUPA, *EVENTOS_DE_RECRIACAO)}
    for evento, _campos in janela:
        if evento in contagem:
            contagem[evento] += 1
    contagem["recriacoes"] = sum(contagem[nome] for nome in EVENTOS_DE_RECRIACAO)
    return contagem


def linha_da_roupa(contagem: dict[str, int] | None, roupa: str = ROUPA_DOS_DOIS_JOGOS) -> Linha:
    if contagem is None:
        return Linha(4, f"recriacoes-entre-dois-{roupa}", None, LIMITE_DE_RECRIACOES, "<=",
                     nota=f"o diário não tem dois launch_arm_roupa roupa={roupa}")
    nota = ", ".join(f"{k}={v}" for k, v in contagem.items() if k != "recriacoes")
    return Linha(4, f"recriacoes-entre-dois-{roupa}", float(contagem["recriacoes"]),
                 LIMITE_DE_RECRIACOES, "<=", nota=nota)


def _ler(caminho: Path) -> str:
    try:
        return caminho.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def nome_do_no(no: str, sys_raiz: Path) -> str:
    """O nome do aparelho de ``/dev/input/eventN`` ou ``/dev/hidrawN``, pelo ``/sys``."""
    base = os.path.basename(no)
    if base.startswith("event"):
        return _ler(sys_raiz / "class" / "input" / base / "device" / "name")
    if base.startswith("hidraw"):
        for linha in _ler(sys_raiz / "class" / "hidraw" / base / "device" / "uevent").splitlines():
            if linha.startswith("HID_NAME="):
                return linha.split("=", 1)[1]
    return ""


def nos_abertos(pids: Sequence[int], proc_raiz: Path, sys_raiz: Path) -> list[tuple[int, str, str]]:
    """``(pid, nó, nome)`` de cada ``/dev/input/event*`` e ``/dev/hidraw*`` aberto pelos ``pids``."""
    fora: list[tuple[int, str, str]] = []
    for pid in pids:
        fds = proc_raiz / str(pid) / "fd"
        try:
            entradas = sorted(fds.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        vistos: set[str] = set()
        for fd in entradas:
            try:
                alvo = os.readlink(fd)
            except OSError:
                continue
            if not (alvo.startswith("/dev/input/event") or alvo.startswith("/dev/hidraw")):
                continue
            if alvo in vistos:
                continue
            vistos.add(alvo)
            fora.append((pid, alvo, nome_do_no(alvo, sys_raiz)))
    return fora


def linha_do_gdk(nos: Sequence[tuple[int, str, str]], vpad: str = VPAD_DO_P3) -> Linha:
    do_vpad = [no for _pid, no, nome in nos if nome == vpad]
    nota = f"{len(nos)} nós de entrada abertos" + (f"; {vpad}: {', '.join(do_vpad)}" if do_vpad else "")
    return Linha(5, "o-jogo-gdk-abre-o-vpad", float(len(do_vpad)), 1.0, ">=", nota=nota)


def ticks_do_processo(pid: int, proc_raiz: Path) -> int | None:
    """``utime + stime`` de ``/proc/<pid>/stat`` (todas as threads), ou ``None`` se o processo saiu."""
    texto = _ler(proc_raiz / str(pid) / "stat")
    if not texto or ")" not in texto:
        return None
    campos = texto.rsplit(")", 1)[1].split()
    try:
        return int(campos[11]) + int(campos[12])
    except (IndexError, ValueError):
        return None


def coletar_cpu(pids: Sequence[int], segundos: float, intervalo: float, proc_raiz: Path) -> list[str]:
    linhas: list[str] = []
    inicio = time.monotonic()
    while True:
        agora = time.monotonic() - inicio
        ticks = [ticks_do_processo(pid, proc_raiz) for pid in pids]
        vivos = [t for t in ticks if t is not None]
        if not vivos:
            break
        linhas.append(f"{agora:.3f} {sum(vivos)}")
        if agora >= segundos:
            break
        time.sleep(intervalo)
    return linhas


def ler_o_teclado(dispositivo: str, segundos: float) -> bytes:
    fd = os.open(dispositivo, os.O_RDONLY | os.O_NONBLOCK)
    try:
        bruto = bytearray()
        fim = time.monotonic() + segundos
        while (falta := fim - time.monotonic()) > 0:
            prontos, _w, _x = select.select([fd], [], [], falta)
            if prontos:
                try:
                    bruto += os.read(fd, TAMANHO_DO_EVENTO * 64)
                except BlockingIOError:
                    continue
        return bytes(bruto)
    finally:
        os.close(fd)


def receita_do_quadro(pid: int, winevulkan: str) -> str:
    return (
        "sudo -A bpftrace -e "
        f"'uprobe:/proc/{pid}/root{winevulkan}:thunk64_vkQueuePresentKHR /pid == {pid}/ "
        "{ printf(\"%llu\\n\", nsecs); }' > quadros-<com|sem>.txt"
    )


def _imprimir(linhas: Sequence[Linha]) -> int:
    for linha in linhas:
        print(linha.texto())
    vereditos = {linha.veredito for linha in linhas}
    if "reprovou" in vereditos:
        return 1
    if "sem-medida" in vereditos:
        return 2
    return 0


def _ler_linhas(caminho: str) -> list[str]:
    return Path(caminho).read_text(encoding="utf-8", errors="replace").splitlines()


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    sub = ap.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("quadro", help="itens 1 e 6: o quadro mediano com e sem o Hefesto")
    q.add_argument("--com", required=True)
    q.add_argument("--sem", required=True)

    r = sub.add_parser("receita-do-quadro", help="imprime a linha do bpftrace (não a roda)")
    r.add_argument("--pid", type=int, required=True)
    r.add_argument("--winevulkan", required=True)

    c = sub.add_parser("cpu", help="item 6: o pico da CPU do jogo com e sem o Hefesto")
    c.add_argument("--com", required=True)
    c.add_argument("--sem", required=True)
    c.add_argument("--hz", type=int, default=os.sysconf("SC_CLK_TCK"))

    cc = sub.add_parser("coletar-cpu", help="amostra /proc/<pid>/stat dos processos do jogo")
    cc.add_argument("--pid", type=int, action="append", required=True)
    cc.add_argument("--segundos", type=float, default=60.0)
    cc.add_argument("--intervalo", type=float, default=0.5)
    cc.add_argument("--proc", default="/proc")

    t = sub.add_parser("teclado", help="item 2: as teclas que chegaram ao evdev do teclado virtual")
    t.add_argument("--dispositivo")
    t.add_argument("--gravacao", help="input_event lidos antes, em vez do dispositivo")
    t.add_argument("--codigo", type=int, required=True)
    t.add_argument("--mandadas", type=int, required=True)
    t.add_argument("--segundos", type=float, default=10.0)

    rp = sub.add_parser("roupa", help="item 4: as recriações entre dois lançamentos da mesma roupa")
    rp.add_argument("--diario", required=True)
    rp.add_argument("--roupa", default=ROUPA_DOS_DOIS_JOGOS)

    g = sub.add_parser("gdk", help="item 5: os nós de entrada que o jogo GDK tem abertos")
    g.add_argument("--pid", type=int, action="append", required=True)
    g.add_argument("--vpad", default=VPAD_DO_P3)
    g.add_argument("--proc", default="/proc")
    g.add_argument("--sys", default="/sys")

    a = ap.parse_args(argv)

    if a.cmd == "quadro":
        com = quadros_em_ms(instantes_do_quadro(_ler_linhas(a.com)))
        sem = quadros_em_ms(instantes_do_quadro(_ler_linhas(a.sem)))
        return _imprimir([linha_do_quadro(com, sem)])
    if a.cmd == "receita-do-quadro":
        print(receita_do_quadro(a.pid, a.winevulkan))
        return 0
    if a.cmd == "cpu":
        com_pct = cpu_por_intervalo(amostras_da_cpu(_ler_linhas(a.com)), a.hz)
        sem_pct = cpu_por_intervalo(amostras_da_cpu(_ler_linhas(a.sem)), a.hz)
        return _imprimir([linha_da_cpu(com_pct, sem_pct)])
    if a.cmd == "coletar-cpu":
        for linha in coletar_cpu(a.pid, a.segundos, a.intervalo, Path(a.proc)):
            print(linha)
        return 0
    if a.cmd == "teclado":
        if a.gravacao:
            bruto = Path(a.gravacao).read_bytes()
        elif a.dispositivo:
            nome = nome_do_no(a.dispositivo, Path("/sys"))
            if nome != TECLADO_DO_ENSAIO:
                print(f"recusado: {a.dispositivo} é «{nome}», não o {TECLADO_DO_ENSAIO}", file=sys.stderr)
                return 3
            bruto = ler_o_teclado(a.dispositivo, a.segundos)
        else:
            ap.error("teclado pede --dispositivo ou --gravacao")
        return _imprimir([linha_do_teclado(teclas_que_chegaram(bruto, a.codigo), a.mandadas)])
    if a.cmd == "roupa":
        contagem = contar_a_roupa(eventos_do_diario(_ler_linhas(a.diario)), a.roupa)
        return _imprimir([linha_da_roupa(contagem, a.roupa)])
    if a.cmd == "gdk":
        nos = nos_abertos(a.pid, Path(a.proc), Path(a.sys))
        for pid, no, nome in nos:
            print(f"pid {pid}  {no}  {nome or '?'}")
        return _imprimir([linha_do_gdk(nos, a.vpad)])
    return 2


if __name__ == "__main__":
    sys.exit(main())
