#!/usr/bin/env python3
"""a_entrada_que_nasce_sozinha.py — quem mexe no cursor e no teclado dela."""

from __future__ import annotations

import argparse
import collections
import contextlib
import functools
import os
import re
import select
import stat
import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)
_SRC = os.path.join(os.path.dirname(os.path.dirname(_AQUI)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from comum import (
    GRAB_DE_TERCEIRO,
    PORTA_DIRETA,
    cabecalho_do_instrumento,
    estado_do_grab,
    leitura_de_zero,
    linha_do_grab,
    resumo,
)

try:
    from hefesto_dualsense4unix.core.evdev_reader import (
        EvdevReader,
        abrir_input_device,
        faixas_de_eixo,
        normalizar_eixo,
    )
    from hefesto_dualsense4unix.daemon.subsystems.quem_mexe import teve_entrada
    from hefesto_dualsense4unix.integrations.hidraw_broker_client import PORTA_BROKER

    DONOS_IMPORTAVEIS = ""
except ImportError as _erro:  # pragma: no cover - só fora do venv do projeto
    DONOS_IMPORTAVEIS = str(_erro)

INTERESSA = ("hefesto", "dualsense", "virtual", "wireless controller")


def mascarar(uniq: str) -> str:
    """A máscara da casa: octetos 4 e 5 zerados."""
    return re.sub(r"^(..):(..):(..):..:..:(..)$", r"\1:\2:\3:00:00:\4", uniq)


def nos_de_entrada() -> list[tuple[str, str, str]]:
    """`(caminho, nome, uniq mascarado)` de todo nó que interessa."""
    fora: list[tuple[str, str, str]] = []
    try:
        with open("/proc/bus/input/devices", encoding="utf-8") as arq:
            blocos = arq.read().split("\n\n")
    except OSError:
        return fora
    for b in blocos:
        n = re.search(r'N: Name="([^"]+)"', b)
        e = re.search(r"(event\d+)", b)
        if not (n and e):
            continue
        nome = n.group(1)
        if not any(k in nome.lower() for k in INTERESSA):
            continue
        u = re.search(r"U: Uniq=(\S*)", b)
        uniq = (u.group(1) if u else "") or ""
        fora.append((f"/dev/input/{e.group(1)}", nome, mascarar(uniq) if uniq else "—"))
    return fora


RAIZ_DO_BANCO_DO_UDEV = "/run/udev/data"

TELA = "tela"
PAD = "pad"
IMU = "IMU"
CHAVE = "chave"
NAO_SEI = "não sei"

MARCAS_DA_TELA = (
    "ID_INPUT_KEY",
    "ID_INPUT_KEYBOARD",
    "ID_INPUT_MOUSE",
    "ID_INPUT_TOUCHPAD",
    "ID_INPUT_TOUCHSCREEN",
    "ID_INPUT_TABLET",
    "ID_INPUT_TABLET_PAD",
    "ID_INPUT_POINTINGSTICK",
    "ID_INPUT_TRACKBALL",
)
MARCA_DO_PAD = "ID_INPUT_JOYSTICK"
MARCA_DA_IMU = "ID_INPUT_ACCELEROMETER"
MARCA_DA_CHAVE = "ID_INPUT_SWITCH"
MARCAS_DE_CLASSE = (*MARCAS_DA_TELA, MARCA_DO_PAD, MARCA_DA_IMU, MARCA_DA_CHAVE)


def propriedades_do_udev(
    caminho: str,
    *,
    raiz: str = RAIZ_DO_BANCO_DO_UDEV,
    estat: Callable[[str], Any] = os.stat,
) -> dict[str, str] | None:
    """As propriedades `E:` que o udev guardou para o nó; None se ilegíveis."""
    try:
        info = estat(caminho)
    except OSError:
        return None
    if not stat.S_ISCHR(info.st_mode):
        return None
    arquivo = os.path.join(raiz, f"c{os.major(info.st_rdev)}:{os.minor(info.st_rdev)}")
    try:
        with open(arquivo, encoding="utf-8", errors="replace") as fh:
            texto = fh.read()
    except OSError:
        return None
    propriedades: dict[str, str] = {}
    for linha in texto.splitlines():
        if linha.startswith("E:") and "=" in linha:
            chave, _, valor = linha[2:].partition("=")
            propriedades[chave] = valor
    return propriedades


def classe_do_no(propriedades: dict[str, str] | None) -> str:
    """A classe que o compositor dá ao nó, pelas marcas de classe do udev."""
    if not propriedades:
        return NAO_SEI
    marcas = {m for m in MARCAS_DE_CLASSE if propriedades.get(m) == "1"}
    if MARCA_DA_IMU in marcas:
        return IMU
    if marcas & set(MARCAS_DA_TELA):
        return TELA
    if MARCA_DO_PAD in marcas:
        return PAD
    if MARCA_DA_CHAVE in marcas:
        return CHAVE
    return NAO_SEI


def numero(n: int) -> str:
    """O número com o ponto de milhar da casa: 1.199, e não 1199."""
    return f"{n:,}".replace(",", ".")


def rotulo_do_evento(ecodes: Any, tipo: int, codigo: int) -> str:
    """O rótulo leva o TIPO: «EV_FF efeito 0», nunca um `0` puro."""
    nome_do_tipo = ecodes.EV.get(tipo, f"EV_{tipo}")
    if tipo in (ecodes.EV_FF, ecodes.EV_FF_STATUS):
        return f"{nome_do_tipo} efeito {codigo}"
    nome = ecodes.bytype.get(tipo, {}).get(codigo, str(codigo))
    if isinstance(nome, list):
        nome = nome[0]
    return f"{nome_do_tipo} {nome}"


@functools.cache
def tipos_de_entrada(ecodes: Any) -> frozenset[int]:
    return frozenset({ecodes.EV_KEY, ecodes.EV_REL, ecodes.EV_ABS, ecodes.EV_SW})


@functools.cache
def tipos_de_eco(ecodes: Any) -> frozenset[int]:
    """Saída pedida ao nó, que o kernel entrega de volta a todo leitor."""
    return frozenset({ecodes.EV_FF, ecodes.EV_FF_STATUS, ecodes.EV_LED, ecodes.EV_SND})


@dataclass
class NoVigiado:
    """Um nó, com a classe, a porta, o grab e o que ele emitiu."""

    caminho: str
    nome: str
    uniq: str
    classe: str
    porta: str | None = None
    grab: str = ""
    dispositivo: Any = None
    entradas: int = 0
    ecos: collections.Counter[str] = field(default_factory=collections.Counter)
    rotulos: collections.Counter[str] = field(default_factory=collections.Counter)
    eixos: dict[str, int] = field(default_factory=dict)
    botoes: set[str] = field(default_factory=set)
    faixas: dict[int, Any] = field(default_factory=dict)
    vistos: dict[str, tuple[int, int]] = field(default_factory=dict)
    dentro_da_zona: int = 0
    quadros_com_mao: int = 0
    primeiro_com_mao: str = ""
    _quadro: list[str] = field(default_factory=list)
    _quadro_sem_zona: bool = False

    @property
    def lido(self) -> bool:
        """Aberto, e ninguém segura o nó: o que ele emitir chega aqui."""
        return self.porta is not None and self.grab != GRAB_DE_TERCEIRO

    @property
    def segura_o_veredito(self) -> bool:
        """Nó da tela ou do pad que ninguém leu e nenhum terceiro segura."""
        if self.classe == NAO_SEI:
            return True
        return self.classe in (TELA, PAD) and not self.lido and self.grab != GRAB_DE_TERCEIRO

    def semear(self, dispositivo: Any, ecodes: Any) -> None:
        """O estado do pad nasce do `absinfo` na abertura, como o repouso do leitor."""
        try:
            self.faixas = faixas_de_eixo(dispositivo.capabilities(), ecodes.EV_ABS)
        except Exception:
            self.faixas = {}
        for nome_evdev, campo in EvdevReader._CAMPOS_DE_EIXO:
            codigo = getattr(ecodes, nome_evdev, None)
            if codigo is None:
                continue
            try:
                cru = int(dispositivo.absinfo(int(codigo)).value)
            except Exception:
                continue
            valor = normalizar_eixo(cru, self.faixas.get(int(codigo)))
            self.eixos[campo] = valor
            self.vistos[campo] = (valor, valor)

    def registrar(self, evento: Any, ecodes: Any) -> None:
        """Um evento lido do nó. O `SYN_REPORT` fecha o quadro do pad."""
        tipo, codigo, valor = int(evento.type), int(evento.code), int(evento.value)
        if tipo == ecodes.EV_SYN:
            if codigo == ecodes.SYN_REPORT:
                self.fechar_quadro()
            return
        rotulo = rotulo_do_evento(ecodes, tipo, codigo)
        if tipo in tipos_de_eco(ecodes):
            self.ecos[rotulo] += 1
            return
        if tipo not in tipos_de_entrada(ecodes):
            return
        self.entradas += 1
        self.rotulos[rotulo] += 1
        if self.classe == PAD:
            self._no_quadro_do_pad(tipo, codigo, valor, rotulo, ecodes)

    def _no_quadro_do_pad(
        self, tipo: int, codigo: int, valor: int, rotulo: str, ecodes: Any
    ) -> None:
        self._quadro.append(f"{rotulo}={valor}")
        if tipo == ecodes.EV_ABS:
            campo = _campo_do_codigo(ecodes).get(codigo)
            if campo is not None:
                normal = normalizar_eixo(valor, self.faixas.get(codigo))
                self.eixos[campo] = normal
                menor, maior = self.vistos.get(campo, (normal, normal))
                self.vistos[campo] = (min(menor, normal), max(maior, normal))
            elif codigo in _codigos_do_chapeu(ecodes):
                (self.botoes.add if valor else self.botoes.discard)(rotulo)
            else:
                self._quadro_sem_zona = True
        elif tipo in (ecodes.EV_KEY, ecodes.EV_SW):
            (self.botoes.add if valor else self.botoes.discard)(rotulo)
        else:
            self._quadro_sem_zona = True

    def fechar_quadro(self) -> None:
        """Pergunta ao dono da zona se a mão estava no pad neste quadro."""
        if not self._quadro:
            return
        eventos, self._quadro = self._quadro, []
        sem_zona, self._quadro_sem_zona = self._quadro_sem_zona, False
        e = self.eixos
        com_mao = sem_zona or teve_entrada(
            botoes=frozenset(self.botoes),
            lx=e.get("lx", 128),
            ly=e.get("ly", 128),
            rx=e.get("rx", 128),
            ry=e.get("ry", 128),
            l2=e.get("l2_raw", 0),
            r2=e.get("r2_raw", 0),
        )
        if com_mao:
            self.quadros_com_mao += 1
            if not self.primeiro_com_mao:
                self.primeiro_com_mao = ", ".join(eventos[:4])
        else:
            self.dentro_da_zona += len(eventos)

    def celula(self) -> str:
        """A contagem, ou a frase do dono para o zero, que depende do grab."""
        if self.entradas:
            return numero(self.entradas)
        return leitura_de_zero(self.grab)

    def amplitude(self) -> str:
        partes = [
            f"{campo} {maior - menor}"
            for campo, (menor, maior) in sorted(self.vistos.items())
            if maior != menor
        ]
        return ", ".join(partes) or "nenhum eixo trocou de valor"


@functools.cache
def _campo_do_codigo(ecodes: Any) -> dict[int, str]:
    """O par código → campo do leitor da casa, e não uma cópia."""
    return {
        int(getattr(ecodes, nome)): campo
        for nome, campo in EvdevReader._CAMPOS_DE_EIXO
        if getattr(ecodes, nome, None) is not None
    }


@functools.cache
def _codigos_do_chapeu(ecodes: Any) -> frozenset[int]:
    return frozenset(
        int(getattr(ecodes, f"ABS_HAT{n}{eixo}"))
        for n in range(4)
        for eixo in "XY"
        if getattr(ecodes, f"ABS_HAT{n}{eixo}", None) is not None
    )


def ler_o_grab(caminho: str, fd: int | None = None, *, ioctl: Any = None) -> str:
    """O grab do nó, perguntado NO FD que se tem quando o nó abriu."""
    if fd is None:
        return estado_do_grab(caminho, ioctl=ioctl)
    return estado_do_grab(caminho, abrir=lambda *_a, **_k: os.dup(fd), ioctl=ioctl)


def montar_os_nos(
    alvos: Iterable[tuple[str, str, str]],
    ecodes: Any,
    *,
    abrir: Callable[[str], Any] | None = None,
    propriedades: Callable[[str], dict[str, str] | None] | None = None,
    acesso: Callable[[str, int], bool] = os.access,
    ioctl: Any = None,
) -> list[NoVigiado]:
    """Classifica, abre pelo dono da porta e pergunta o grab de cada alvo."""
    abrir = abrir or abrir_input_device
    propriedades = propriedades or propriedades_do_udev
    nos: list[NoVigiado] = []
    for caminho, nome, uniq in alvos:
        no = NoVigiado(caminho, nome, uniq, classe_do_no(propriedades(caminho)))
        direto = acesso(caminho, os.R_OK)
        try:
            dispositivo = abrir(caminho)
        except Exception:
            no.grab = ler_o_grab(caminho, ioctl=ioctl)
        else:
            no.dispositivo = dispositivo
            no.porta = PORTA_DIRETA if direto else PORTA_BROKER
            no.grab = ler_o_grab(caminho, int(dispositivo.fd), ioctl=ioctl)
            if no.classe == PAD:
                no.semear(dispositivo, ecodes)
        nos.append(no)
    return nos


def medir(
    nos: list[NoVigiado],
    segundos: float,
    ecodes: Any,
    *,
    relogio: Callable[[], float] = time.monotonic,
    selecionar: Callable[..., Any] = select.select,
) -> None:
    """Lê todo nó aberto ao mesmo tempo, pelo tempo pedido."""
    por_fd = {int(no.dispositivo.fd): no for no in nos if no.dispositivo is not None}
    fim = relogio() + segundos
    while por_fd and relogio() < fim:
        prontos, _, _ = selecionar(list(por_fd), [], [], 1.0)
        for fd in prontos:
            no = por_fd[fd]
            try:
                eventos = list(no.dispositivo.read())
            except OSError:
                continue
            for evento in eventos:
                no.registrar(evento, ecodes)
    for no in nos:
        no.fechar_quadro()


def fechar(nos: list[NoVigiado]) -> None:
    for no in nos:
        if no.dispositivo is not None:
            with contextlib.suppress(Exception):
                no.dispositivo.close()


def relatorio(nos: list[NoVigiado], segundos: float) -> list[str]:
    """Uma linha por NÓ (o caminho), e o contexto de cada um logo abaixo."""
    linhas = [f"EVENTOS DE ENTRADA EM {segundos:g} s, POR NÓ:"]
    for no in nos:
        porta = no.porta or "não abriu"
        linhas.append(
            f"  {no.caminho:20s} {no.classe:7s} {porta:20s} {no.celula():>32}  {no.nome[:48]}"
        )
        if no.classe == PAD and no.entradas:
            if no.dentro_da_zona:
                linhas.append(
                    f"      dentro da zona (o chiado do aparelho): {numero(no.dentro_da_zona)} "
                    f"evento(s); amplitude: {no.amplitude()}"
                )
            if no.quadros_com_mao:
                linhas.append(
                    f"      COM MÃO: {numero(no.quadros_com_mao)} quadro(s); o primeiro: "
                    f"{no.primeiro_com_mao}"
                )
        for rotulo, quantos in sorted(no.ecos.items()):
            linhas.append(f"      saída ecoada, não é entrada: {rotulo}: {numero(quantos)}")
    detalhe = collections.Counter(
        {(no.caminho, r): q for no in nos for r, q in no.rotulos.items()}
    )
    if detalhe:
        linhas.append("")
        linhas.append("os que mais apareceram:")
        for (caminho, rotulo), quantos in detalhe.most_common(12):
            linhas.append(f"  {numero(quantos):>7}  {rotulo:24s} em {caminho}")
    return linhas


def _quem(no: NoVigiado) -> str:
    return f"{no.caminho} ({no.nome}, {no.classe})"


def veredito(
    nos: list[NoVigiado],
    *,
    sumiram: Iterable[str] = (),
    nasceram_sem_leitura: Iterable[str] = (),
) -> tuple[int, str]:
    """`(rc, frase)`: 2 inválida, 1 alguém mexeu, 3 não sei, 0 zero."""
    sumiram = list(sumiram)
    nasceram_sem_leitura = list(nasceram_sem_leitura)
    total = sum(no.entradas for no in nos)
    if sumiram:
        return 2, (
            f"MEDIÇÃO INVÁLIDA — {len(sumiram)} nó(s) saíram durante a corrida. "
            "Desligar o BT do controle é o gesto com que ela CURA o defeito, "
            "então o que sobrou aqui é o estado curado. "
            f"{total} evento(s) medido(s), e eles NÃO respondem à pergunta. "
            "Refaça com o aparelho na mesa do começo ao fim."
        )
    na_tela = [no for no in nos if no.classe == TELA and no.entradas]
    com_mao = [no for no in nos if no.classe == PAD and no.quadros_com_mao]
    if na_tela or com_mao:
        eventos = sum(no.entradas for no in na_tela)
        quadros = sum(no.quadros_com_mao for no in com_mao)
        return 1, (
            f"{numero(eventos)} evento(s) NO QUE MEXE NA TELA e {numero(quadros)} "
            "quadro(s) com mão nos pads. O culpado: "
            + "; ".join(_quem(no) for no in na_tela + com_mao)
            + "."
        )
    sem_leitura = [no for no in nos if no.segura_o_veredito]
    if sem_leitura or nasceram_sem_leitura:
        nomes = [f"{_quem(no)}: {no.celula()}" for no in sem_leitura]
        nomes += [f"{caminho} (nasceu no meio e ninguém o leu)" for caminho in nasceram_sem_leitura]
        return 3, (
            f"NÃO SEI — {len(nomes)} nó(s) da tela ou do pad não foram lidos nem "
            "estão presos por grab de terceiro, ou a classe deles não se leu: "
            + "; ".join(nomes)
            + ". Zero de quem não foi lido não é zero."
        )
    chiado = sum(no.dentro_da_zona for no in nos)
    imu = sum(no.entradas for no in nos if no.classe == IMU)
    chave = sum(no.entradas for no in nos if no.classe == CHAVE)
    eco = sum(sum(no.ecos.values()) for no in nos)
    return 0, (
        "ZERO no que mexe na tela e zero com mão nos pads, com todo nó da tela e "
        f"do pad lido ou preso por grab de terceiro (contexto: {numero(chiado)} "
        f"evento(s) de chiado dentro da zona, {numero(imu)} de IMU, {numero(chave)} "
        f"de chave e {numero(eco)} de saída ecoada). Se o defeito estava acontecendo "
        "agora, ele não nasce em nó de entrada — olhe o compositor, o teclado na "
        "tela ou o aplicativo em foco."
    )


def classes_dos_que_nasceram(
    nasceram: Iterable[str],
    propriedades: Callable[[str], dict[str, str] | None] | None = None,
) -> list[str]:
    """Os nós que nasceram no meio e cuja classe segura o veredito."""
    propriedades = propriedades or propriedades_do_udev
    return [
        caminho
        for caminho in nasceram
        if classe_do_no(propriedades(caminho)) in (TELA, PAD, NAO_SEI)
    ]


def importar_evdev() -> Any:
    """O `evdev`, importado ANTES do cabeçalho, para que ele diga de onde veio."""
    try:
        import evdev
    except ImportError:
        return None
    return evdev


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--segundos", type=float, default=30.0)
    ap.add_argument("--listar", action="store_true", help="só diz o que vigiaria")
    args = ap.parse_args(argv)

    evdev = importar_evdev()
    alvos = nos_de_entrada()
    nos: list[NoVigiado] = []
    if evdev is not None and not DONOS_IMPORTAVEIS and alvos and not args.listar:
        nos = montar_os_nos(alvos, evdev.ecodes)

    print(cabecalho_do_instrumento(
        "a_entrada_que_nasce_sozinha",
        "qual nó mexe no cursor e no teclado dela quando ninguém encosta no controle?",
        bibliotecas=["evdev"],
        escreve_no_aparelho=False,
        nos_evdev=[no.caminho for no in nos if no.porta == PORTA_DIRETA]))
    for no in nos:
        if no.porta == PORTA_BROKER:
            print(f"  {linha_do_grab(no.caminho, no.grab)} (perguntado no fd do broker)")

    if DONOS_IMPORTAVEIS:
        print(resumo(f"NÃO SEI — os donos da casa não são importáveis aqui ({DONOS_IMPORTAVEIS})."))
        return 3
    if not alvos:
        print(resumo("NÃO SEI — nenhum nó de controle na mesa, nada a vigiar."))
        return 3
    print("O QUE ELE VIGIA:")
    for caminho, nome, uniq in alvos:
        classe = classe_do_no(propriedades_do_udev(caminho))
        print(f"  {caminho:20s} {classe:7s} {nome[:48]:50s} uniq={uniq}")

    if args.listar:
        print(resumo("leitura pura — nenhum nó aberto nesta corrida."))
        return 0
    if evdev is None:
        print(resumo("NÃO SEI — o `evdev` não está nesta venv (`pip install evdev`)."))
        return 3
    if not any(no.porta for no in nos):
        print("\n".join(relatorio(nos, 0)))
        print(resumo("NÃO SEI — nenhum nó abriu, nem pelo caminho nem pelo broker."))
        return 3

    print(f"\n>>> MEDINDO {args.segundos:g} s. Se o cursor andar sozinho agora, "
          f"o culpado sai nomeado abaixo.", flush=True)
    try:
        medir(nos, args.segundos, evdev.ecodes)
    finally:
        fechar(nos)

    depois = {c for c, _n, _u in nos_de_entrada()}
    sumiram = [n for c, n, _u in alvos if c not in depois]
    nasceram = sorted(depois - {c for c, _n, _u in alvos})

    print()
    print("\n".join(relatorio(nos, args.segundos)))
    for nome in sumiram:
        print(f"\n  !! SAIU DA MESA NO MEIO: {nome}")
    if nasceram:
        print(f"\n  (nasceram no meio: {', '.join(nasceram)})")

    rc, frase = veredito(
        nos, sumiram=sumiram, nasceram_sem_leitura=classes_dos_que_nasceram(nasceram)
    )
    print(resumo(frase))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
