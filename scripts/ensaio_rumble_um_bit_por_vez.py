#!/usr/bin/env python3
"""ensaio_rumble_um_bit_por_vez.py — apaga UM bit de autorização por vez.

O que falta depois da bancada de 10/08/2026
-------------------------------------------
Naquele ensaio ficou provado, com o controle na mão dela: `common[3]` (strong)
é o motor esquerdo, `common[2]` (weak) é o direito, e o zero para de fato.
Sabemos que o CONJUNTO funciona. Não sabemos **de quantos bits o aparelho
precisa** — e essa é a poda que sobra (`docs/process/METODO-DE-ISOLAMENTO.md`,
Passo 7).

Os bits estão em `core/backend_pydualsense.py:761-767`::

    if not rumble_asserted:
        flag0 &= ~(COMPATIBLE_VIBRATION | HAPTICS_SELECT)   # 0x01 e 0x02
        flag1 &= ~MOTOR_POWER                               # 0x40
        flag2 &= ~COMPATIBLE_VIBRATION2                     # 0x04

São QUATRO no código. **MEDIDO aqui, montando o report com o construtor do
próprio produto: só TRÊS chegam ao fio.** Com rumble ativo e supressão de LED
(o estado normal desta casa) o produto emite `flag0=0x0F`, `flag1=0x41`,
`flag2=0x00` — o bit v2 (`VALID_FLAG2_COMPATIBLE_VIBRATION2`, 0x04) **nunca
acende**, porque `flag2` nasce de `int(self.light.ledOption.value)` e a enum
`LedOptions` da pydualsense vai no máximo até `Both = 0x03`. A linha que
"limpa" o v2 limpa um bit que nunca esteve ligado.

Este instrumento não acredita nesse parágrafo: ele **mede a linha de base
chamando o `_build_common` do produto**, sem hardware, e imprime o que mediu
antes de qualquer disparo. Se o produto mudar, o número muda aqui junto.

O caminho — e por que ele NÃO passa pelo IPC
--------------------------------------------
A armadilha nº 1 desta casa é o instrumento que disputa o hidraw com o daemon
e imprime "aplicado" sem ter aplicado. A pergunta foi feita e MEDIDA:

* `app.ipc_bridge.rumble_set` → `rumble.set` carrega **só** `weak` e `strong`;
* nenhum handler do daemon aceita flags (`grep '"rumble\\.'` em
  `daemon/ipc_handlers.py`: `set`, `stop`, `passthrough`, `policy_set`,
  `policy_custom` — e mais nada);
* os bits são fixos dentro do `_build_common`, sem parâmetro nenhum.

**Não existe caminho limpo pelo IPC para variar os bits.** Então este
instrumento faz o que a regra manda quando não há: PARA o daemon, avisa que
parou, confere que ninguém mais está com o hidraw aberto, e o religa no fim.
Enquanto ele roda, o Hefesto está desligado — a vibração de jogo, o perfil e o
keepalive do daemon não existem. Isso é dito na tela, não escondido.

A parada do motor é a primeira obrigação
----------------------------------------
Com o daemon parado, NINGUÉM zera um motor preso: o keepalive do daemon sai com
os bits de vibração desligados de propósito (GUERRA-01), então religá-lo **não
para** um motor que ficou girando. Quem para é este instrumento. Por isso:

* todo pulso vive dentro de `try/finally`;
* a parada é uma SEQUÊNCIA com **autorização máxima** (v1 + HAPTICS_SELECT +
  MOTOR_POWER + v2, motores 0), depois com os flags da própria condição, e
  depois a máxima de novo — porque se o ensaio acabou de provar que um bit era
  necessário, parar com os flags reduzidos poderia não parar nada;
* `SIGINT` (Ctrl+C), `SIGTERM` e `atexit` chamam a mesma parada;
* e existe o modo de pânico, que só para e sai::

      .venv/bin/python scripts/ensaio_rumble_um_bit_por_vez.py parar

Uso
---
    # o ensaio seco — não abre hidraw, não para o daemon, não vibra nada.
    # Serve para conferir os bytes e os flags antes de encostar no controle.
    .venv/bin/python scripts/ensaio_rumble_um_bit_por_vez.py seco

    # a bancada, com ela e o controle na mão:
    .venv/bin/python scripts/ensaio_rumble_um_bit_por_vez.py ensaio \\
        --confirmo-parar-o-daemon

    # uma condição só (o roteiro inteiro é o recomendado — a base repetida no
    # fim é o que controla bateria caindo e mão acostumando):
    .venv/bin/python scripts/ensaio_rumble_um_bit_por_vez.py ensaio \\
        --confirmo-parar-o-daemon --condicao sem-motor-power

    # o pânico:
    .venv/bin/python scripts/ensaio_rumble_um_bit_por_vez.py parar

Este instrumento NÃO conserta nada e NÃO toca em `src/`. O irmão dele,
`scripts/ensaio_rumble_bits.py`, faz o contraste produto-contra-kernel sem
desligar nada; este aqui é o que apaga bit a bit.
"""
from __future__ import annotations

import argparse
import atexit
import contextlib
import csv
import glob
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent / "ensaios"))
import identidade_do_vpad  # noqa: E402  — a régua única do vpad
from comum import PortaFechadaError, abrir_no_hidraw, declaracao_da_porta  # noqa: E402

SERVICO = "hefesto-dualsense4unix.service"
CADERNO = RAIZ / "docs" / "data" / "ensaios.csv"

VID_SONY = "0000054C"
PID_DUALSENSE = "00000CE6"

#: Onde este instrumento enumera os nós hidraw. É parâmetro só para o teste
#: poder montar uma mesa de mentira em `tmp_path` — a medição de verdade não
#: tem por que apontar para outro lugar.
RAIZ_SYSFS_HIDRAW = "/sys/class/hidraw"


# --------------------------------------------------------------------------
# Os quatro bits — o que cada um autoriza, e quem os manda lá fora
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Bit:
    """Um bit de autorização sob julgamento."""

    chave: str
    nome: str
    flag: int          # 0, 1 ou 2 — qual byte de valid_flag
    mascara: int
    autoriza: str
    externos: str


BITS: dict[str, Bit] = {
    "v1": Bit(
        chave="v1",
        nome="VALID_FLAG0_COMPATIBLE_VIBRATION",
        flag=0,
        mascara=0x01,
        autoriza="o ramo v1 da vibração (a emulação anterior a 2021)",
        externos="kernel e SDL só o mandam em firmware ANTIGO — e nunca junto do v2",
    ),
    "haptics": Bit(
        chave="haptics",
        nome="VALID_FLAG0_HAPTICS_SELECT",
        flag=0,
        mascara=0x02,
        autoriza="trocar os voice-coil de 'PCM do jogo' para 'rumble emulado'",
        externos="kernel e SDL mandam SEMPRE (o comentário do SDL: 'Disable audio haptics')",
    ),
    "motor_power": Bit(
        chave="motor_power",
        nome="VALID_FLAG1_MOTOR_POWER",
        flag=1,
        mascara=0x40,
        autoriza="o common[36] (reduce_motor_power) — byte que este projeto nunca escreve",
        externos="NENHUM dos dois manda; o bit nem existe no hid-playstation",
    ),
    "v2": Bit(
        chave="v2",
        nome="VALID_FLAG2_COMPATIBLE_VIBRATION2",
        flag=2,
        mascara=0x04,
        autoriza="o ramo v2 da vibração (o clássico que a Sony tornou padrão)",
        externos="kernel (>= 0x0215) e SDL (>= 0x0224) mandam SÓ ele em firmware novo",
    ),
}

CONJUNTO_KERNEL = "o conjunto que o kernel manda (haptics + v2, sem v1, sem motor power)"


# --------------------------------------------------------------------------
# As condições — a ordem dos ensaios, e o porquê de cada posição
# --------------------------------------------------------------------------


@dataclass
class Condicao:
    """Uma linha do ensaio: um bit mexido, uma pergunta, uma previsão."""

    ordem: int
    chave: str
    rotulo: str
    #: (flag, máscara, ligar?) — o que muda em relação à linha de base.
    deltas: tuple[tuple[int, int, bool], ...]
    previsao: str
    o_que_prova: str
    #: (suspeito, presente) que esta linha registra no caderno.
    registros: tuple[tuple[str, bool], ...] = ()
    pergunta_extra: str = ""


def _todos_os_registros_da_base() -> tuple[tuple[str, bool], ...]:
    """A base registra o lado PRESENTE de tudo que está no fio hoje.

    O v2 entra como AUSENTE, porque é isso que ele é hoje — e o caderno precisa
    dos dois lados para sair de `inconclusivo` (`scripts/eliminacao.py`).
    """
    return (
        (BITS["v1"].nome, True),
        (BITS["haptics"].nome, True),
        (BITS["motor_power"].nome, True),
        (BITS["v2"].nome, False),
        (CONJUNTO_KERNEL, False),
    )


ROTEIRO: tuple[Condicao, ...] = (
    Condicao(
        ordem=1,
        chave="base",
        rotulo="LINHA DE BASE — os bits como o produto manda hoje",
        deltas=(),
        previsao="vibra (é o que ela sente todo dia)",
        o_que_prova=(
            "prova que a bancada está de pé com o daemon PARADO. Se não vibrar "
            "aqui, nada abaixo vale: o problema é o link, não os bits."
        ),
        registros=_todos_os_registros_da_base(),
    ),
    Condicao(
        ordem=2,
        chave="sem-motor-power",
        rotulo="SEM o MOTOR_POWER (flag1 bit6)",
        deltas=((1, 0x40, False),),
        previsao="vibra igual",
        o_que_prova=(
            "é o bit mais barato de podar: nem o kernel nem o SDL o mandam, e ele "
            "autoriza um byte que nunca escrevemos. Se vibrar igual, a poda tem "
            "prova. Se PARAR de vibrar, minha leitura do report está errada e o "
            "resto do roteiro fica sob suspeita — por isso ele vem primeiro."
        ),
        registros=((BITS["motor_power"].nome, False),),
    ),
    Condicao(
        ordem=3,
        chave="sem-v1",
        rotulo="SEM o COMPATIBLE_VIBRATION (flag0 bit0) — nenhum ramo autorizado",
        deltas=((0, 0x01, False),),
        previsao="NÃO vibra (nem v1 nem v2 estão autorizados)",
        o_que_prova=(
            "é o discriminador: responde se o firmware exige um ramo declarado ou "
            "se os bytes de intensidade bastam. 'não vibrou' explica o que já "
            "funcionava — é o v1 que segura a feature hoje."
        ),
        registros=((BITS["v1"].nome, False),),
    ),
    Condicao(
        ordem=4,
        chave="sem-haptics",
        rotulo="SEM o HAPTICS_SELECT (flag0 bit1), com o v1 de volta",
        deltas=((0, 0x02, False),),
        previsao="incerto — as três fontes dizem que ele é obrigatório, ninguém mediu",
        o_que_prova=(
            "o HAPTICS_SELECT tem urgência própria: ele desliga o haptic de áudio "
            "do jogo, e o produto o reafirma em TODO report enquanto vibra. Se o "
            "motor girar sem ele, o jogo pode ficar com as duas coisas."
        ),
        registros=((BITS["haptics"].nome, False),),
    ),
    Condicao(
        ordem=5,
        chave="com-v2",
        rotulo="COM o v2 LIGADO (flag2 bit2) — o bit que o produto nunca mandou",
        deltas=((2, 0x04, True),),
        previsao="vibra; a pergunta é se muda o CARÁTER",
        o_que_prova=(
            "aqui a poda inverte: o v2 não precisa ser apagado, precisa ser ACESO "
            "pela primeira vez. O controle desta casa (update_version 0x0630) é "
            "justamente o que o kernel e o SDL mandariam no ramo novo."
        ),
        registros=((BITS["v2"].nome, True),),
        pergunta_extra="Em relação à base, o jeito de vibrar foi IGUAL ou DIFERENTE?",
    ),
    Condicao(
        ordem=6,
        chave="so-o-kernel",
        rotulo="COMO O KERNEL MANDA — haptics + v2, sem v1, sem motor power",
        deltas=((0, 0x01, False), (1, 0x40, False), (2, 0x04, True)),
        previsao="vibra (é o que o hid-playstation faria neste firmware)",
        o_que_prova=(
            "se vibrar, a cura tem destino: dois bits, escolhidos pelo "
            "update_version, exatamente como os dois projetos externos fazem."
        ),
        registros=((CONJUNTO_KERNEL, True),),
        pergunta_extra="Em relação à base, o jeito de vibrar foi IGUAL ou DIFERENTE?",
    ),
    Condicao(
        ordem=7,
        chave="base-de-novo",
        rotulo="LINHA DE BASE DE NOVO — o controle contra bateria e cansaço",
        deltas=(),
        previsao="vibra igual à primeira linha",
        o_que_prova=(
            "se esta linha não repetir a primeira, o ensaio mediu a bateria caindo "
            "(ou a mão acostumando) e NENHUMA resposta acima vale."
        ),
        registros=(),
    ),
)


# --------------------------------------------------------------------------
# As perguntas do método, respondidas por medição — antes de qualquer disparo
# --------------------------------------------------------------------------


@dataclass
class Fisico:
    """O controle físico como o sistema o enxerga AGORA."""

    hidraw: str
    transporte: str  # "bluetooth" | "cabo" | outro


def achar_fisico(raiz: str = RAIZ_SYSFS_HIDRAW) -> Fisico | None:
    """Acha o DualSense e DECLARA o transporte lendo o uevent, não a memória.

    `HID_ID=0005:...` é Bluetooth; `0003:...` é cabo. O MAC do uevent NÃO é
    lido nem impresso — regra da casa, nada de endereço real na saída.

    VPAD-NO-ESPELHO-01 (12/08/2026): o vpad do PRÓPRIO produto é recusado
    explicitamente, por `identidade_do_vpad`. Hoje ele já não chegava aqui, mas
    por acidente e não por régua: o filtro de `PID_DUALSENSE` só aceita `0CE6`,
    e o vpad se apresenta como `0DF2` (DualSense Edge). O Edge REAL existe, e
    acrescentar o PID dele a este instrumento é uma coisa razoável de se querer
    fazer — no dia em que alguém fizer, sem esta linha o ensaio passaria a
    mirar no vpad, que tem força-feedback e aceita o efeito calado, sem que
    motor nenhum gire. A medição sairia falsa sem avisar.
    """
    for caminho in sorted(glob.glob(os.path.join(raiz, "hidraw*"))):
        uevent = os.path.join(caminho, "device", "uevent")
        try:
            with open(uevent, encoding="utf-8", errors="replace") as fh:
                texto = fh.read()
        except OSError:
            continue
        if VID_SONY not in texto.upper() or PID_DUALSENSE not in texto.upper():
            continue
        if identidade_do_vpad.e_vpad_do_hefesto(
            identidade_do_vpad.campos_do_uevent(texto)
        ):
            continue
        transporte = "desconhecido"
        for linha in texto.splitlines():
            if linha.startswith("HID_ID="):
                bus = linha.split("=", 1)[1].split(":")[0]
                transporte = {"0005": "bluetooth", "0003": "cabo"}.get(bus, bus)
        return Fisico(hidraw="/dev/" + os.path.basename(caminho), transporte=transporte)
    return None


def daemon_ativo() -> bool:
    saida = subprocess.run(
        ["systemctl", "--user", "is-active", SERVICO],
        capture_output=True,
        text=True,
        check=False,
    )
    return saida.stdout.strip() in ("active", "activating")


def donos_do_hidraw(caminho: str) -> list[str]:
    """Quem está com o hidraw ABERTO agora (processos deste usuário).

    É a defesa medida contra a armadilha nº 1: se alguém além de nós tem o nó
    aberto, o ensaio mede a briga entre escritores, não o bit. Só enxerga os
    processos do próprio usuário — o que é suficiente, porque o daemon e o
    Steam rodam como ela.
    """
    donos: list[str] = []
    for proc in glob.glob("/proc/[0-9]*"):
        pid = os.path.basename(proc)
        if pid == str(os.getpid()):
            continue
        try:
            for fd in glob.glob(os.path.join(proc, "fd", "*")):
                if os.readlink(fd) == caminho:
                    with open(os.path.join(proc, "comm"), encoding="utf-8") as fh:
                        donos.append(f"pid {pid} ({fh.read().strip()})")
                    break
        except OSError:
            continue
    return donos


def idade_do_daemon() -> str:
    """Pergunta 2 do método: o daemon vivo pode ser mais velho que o código."""
    inicio = subprocess.run(
        ["systemctl", "--user", "show", SERVICO, "-p", "ActiveEnterTimestamp"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    commit = subprocess.run(
        ["git", "-C", str(RAIZ), "log", "-1", "--format=%cd", "--", "src/"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if not inicio and not commit:
        return "(não consegui medir)"
    return f"daemon subiu [{inicio.split('=', 1)[-1]}] · último commit em src/ [{commit}]"


# --------------------------------------------------------------------------
# A linha de base — medida no PRODUTO, não digitada por mim
# --------------------------------------------------------------------------


def linha_de_base_do_produto(
    weak: int, strong: int, *, bt: bool, suprimir_leds: bool
) -> bytearray:
    """O `common` de 47 bytes que o PRODUTO montaria para este rumble.

    Chama o `_build_common` de `core/backend_pydualsense.py` numa instância sem
    `init()` — o mesmo truque de `tests/unit/test_backend_keepalive_neutro.py`,
    que não abre hardware nenhum. Assim os gatilhos, o áudio e os LEDs saem
    byte a byte como o produto os manda, e a ÚNICA variável do ensaio é o bit
    de autorização que a condição mexe.
    """
    from pydualsense.enums import ConnectionType
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    from hefesto_dualsense4unix.core import backend_pydualsense as bp

    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.leftMotor = 0
    inst.rightMotor = 0
    inst.light = DSLight()
    inst.audio = DSAudio()
    inst.triggerL = DSTrigger()
    inst.triggerR = DSTrigger()
    inst.conType = ConnectionType.BT if bt else ConnectionType.USB
    inst._suppress_leds = suprimir_leds
    inst._rumble_active = False
    inst._rumble_stop_pending = False
    inst._bt_seq = 0
    inst.device = None
    inst.setLeftMotor(int(strong) & 0xFF)
    inst.setRightMotor(int(weak) & 0xFF)
    return inst._build_common(rumble_asserted=True)


def flags_de(common: bytearray) -> tuple[int, int, int]:
    from hefesto_dualsense4unix.core import ds_output_report as rep

    return common[0], common[1], common[rep.COMMON_VALID_FLAG2]


def aplicar_deltas(
    flags: tuple[int, int, int], deltas: tuple[tuple[int, int, bool], ...]
) -> tuple[int, int, int]:
    valores = list(flags)
    for indice, mascara, ligar in deltas:
        if ligar:
            valores[indice] |= mascara
        else:
            valores[indice] &= ~mascara & 0xFF
    return valores[0], valores[1], valores[2]


def descrever_flags(flags: tuple[int, int, int]) -> str:
    f0, f1, f2 = flags
    ligados = [
        bit.chave
        for bit in BITS.values()
        if (f0, f1, f2)[bit.flag] & bit.mascara
    ]
    return (
        f"flag0=0x{f0:02X} flag1=0x{f1:02X} flag2=0x{f2:02X}"
        f"  [{', '.join(ligados) if ligados else 'NENHUM bit de vibração'}]"
    )


def hexdump(dados: bytes) -> str:
    return " ".join(f"{b:02X}" for b in dados)


# --------------------------------------------------------------------------
# A bancada — quem escreve, e quem PARA
# --------------------------------------------------------------------------


@dataclass
class Bancada:
    """O único escritor do hidraw durante o ensaio. Sabe parar o motor."""

    fisico: Fisico
    base: bytearray
    seco: bool = False
    keepalive: bool = True
    fd: int | None = None
    #: Por onde o hidraw foi aberto, já na frase do relatório. Nasce vazia e é
    #: preenchida no `abrir`; o modo seco nunca abre nada e a mantém vazia.
    porta: str = ""
    seq: int = 0
    escritas: int = 0
    # RLock, e não Lock, de propósito: o Ctrl+C pode chegar com o laço do pulso
    # DENTRO da trava, e o tratador de sinal roda na mesma linha de execução —
    # com um Lock simples a parada travaria justamente com o motor girando.
    _trava: threading.RLock = field(default_factory=threading.RLock)
    _parar_keepalive: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None
    _ultimos_flags: tuple[int, int, int] | None = None
    _fechada: bool = False

    # -- montagem ---------------------------------------------------------

    def montar(
        self, flags: tuple[int, int, int], weak: int, strong: int
    ) -> tuple[bytearray, bytes]:
        """Devolve (common, report). O report usa o construtor DO PRODUTO."""
        from hefesto_dualsense4unix.core import ds_output_report as rep

        common = bytearray(self.base)
        common[0], common[1] = flags[0], flags[1]
        common[rep.COMMON_VALID_FLAG2] = flags[2]
        common[2] = int(weak) & 0xFF
        common[3] = int(strong) & 0xFF
        if self.fisico.transporte == "bluetooth":
            return common, bytes(rep.build_bt_report(common, seq=self.seq))
        return common, bytes(rep.build_usb_report(common))

    def montar_inerte(self) -> bytes:
        """Keepalive de link: TODOS os flags zerados — não autoriza nada.

        Com o daemon parado, o rádio pode entrar em sniff e atrasar o pulso; o
        daemon mantinha um keepalive a 2 Hz e é isso que estamos repondo. Como
        nenhum bit está ligado, ele não pode influenciar o ensaio.
        """
        from hefesto_dualsense4unix.core import ds_output_report as rep

        common = bytearray(rep.COMMON_LEN)
        if self.fisico.transporte == "bluetooth":
            return bytes(rep.build_bt_report(common, seq=self.seq))
        return bytes(rep.build_usb_report(common))

    # -- escrita ----------------------------------------------------------

    def abrir(self) -> None:
        """Abre o hidraw PELA PORTA DO BROKER — e guarda por onde entrou.

        O `os.open` que estava aqui colhia `EACCES` em toda mesa com o co-op
        ligado (A-PORTA-QUE-A-CASA-CONSTRUIU-01): o Hefesto esconde o físico
        do jogo de propósito, e este instrumento é, para o kernel, mais um
        processo da sessão. O `O_NONBLOCK` vira `set_blocking(False)` porque o
        fd pode ter vindo do broker, já aberto — a flag se põe depois, e o
        efeito é o mesmo.
        """
        if self.seco:
            return
        aberto = abrir_no_hidraw(self.fisico.hidraw, escrita=True)
        self.fd = aberto.fd
        self.porta = aberto.linha_de_relatorio
        os.set_blocking(self.fd, False)
        atexit.register(self.parar, "atexit")
        if self.keepalive and self.fisico.transporte == "bluetooth":
            self._thread = threading.Thread(target=self._laco_keepalive, daemon=True)
            self._thread.start()

    def _escrever(self, report: bytes) -> int:
        if self.seco or self.fd is None:
            return len(report)
        with self._trava:
            escrito = os.write(self.fd, report)
            self.seq = (self.seq + 1) & 0x0F
            self.escritas += 1
        return escrito

    def _laco_keepalive(self) -> None:
        while not self._parar_keepalive.wait(0.5):
            try:
                self._escrever(self.montar_inerte())
            except OSError:
                return

    # -- os dois gestos ---------------------------------------------------

    def pulso(
        self, flags: tuple[int, int, int], weak: int, strong: int, segundos: float
    ) -> None:
        """Vibra `segundos` com estes flags — e PARA, aconteça o que acontecer."""
        self._ultimos_flags = flags
        common, report = self.montar(flags, weak, strong)
        print(f"    MANDANDO  {descrever_flags(flags)}")
        print(f"      motores  common[2] (weak/direito)={weak}  "
              f"common[3] (strong/esquerdo)={strong}")
        print(f"      envelope 0x{report[0]:02X}, {len(report)} bytes"
              f"{' (CRC-32 nos 4 últimos)' if report[0] == 0x31 else ''}")
        print(f"      common   {hexdump(common)}")
        try:
            fim = time.monotonic() + segundos
            while time.monotonic() < fim:
                # remontado a cada volta: no BT o nibble de sequência e o CRC
                # mudam a cada write (é o que o `writeReport` do produto faz).
                self._escrever(self.montar(flags, weak, strong)[1])
                time.sleep(0.1)
        finally:
            self.parar("fim do pulso")

    def parar(self, motivo: str) -> None:
        """A sequência de parada. Idempotente, e chamada de todo lado.

        Manda motores 0 com AUTORIZAÇÃO MÁXIMA (todos os quatro bits), depois
        com os flags da última condição, depois a máxima de novo. Se o ensaio
        acabou de mostrar que um bit era necessário, parar só com os flags
        reduzidos poderia não parar coisa nenhuma.
        """
        if self._fechada:
            return
        if not self.seco and self.fd is None:
            return
        f0, f1, f2 = flags_de(self.base)
        maxima = (f0 | 0x03, f1 | 0x40, f2 | 0x04)
        sequencia: list[tuple[str, tuple[int, int, int]]] = [
            ("autorização máxima", maxima),
        ]
        if self._ultimos_flags is not None:
            sequencia.append(("os flags da própria condição", self._ultimos_flags))
        sequencia.append(("autorização máxima de novo", maxima))
        print(f"    PARADA ({motivo}){' — modo seco, nada é escrito' if self.seco else ''}:")
        for rotulo, flags in sequencia:
            common, report = self.montar(flags, 0, 0)
            try:
                self._escrever(report)
            except OSError as erro:  # nunca deixar de tentar as outras
                print(f"      ! falhou o stop '{rotulo}': {erro}")
                continue
            print(f"      {rotulo}: {descrever_flags(flags)} · motores 0")
            print(f"        common[0..3]={hexdump(common[:4])} · "
                  f"envelope 0x{report[0]:02X}, {len(report)} bytes")
            time.sleep(0.06)

    def fechar(self) -> None:
        self._parar_keepalive.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        if self.fd is not None and not self._fechada:
            self.parar("fechamento")
            self._fechada = True
            with contextlib.suppress(OSError):
                os.close(self.fd)
        self.fd = None


# --------------------------------------------------------------------------
# O caderno
# --------------------------------------------------------------------------


def linhas_de_caderno(
    condicao: Condicao,
    resultado: str,
    nota: str,
    *,
    linha_id: str,
    lado: str,
    fonte: str,
    quando: str,
    contador: list[int],
) -> list[list[str]]:
    linhas: list[list[str]] = []
    for suspeito, presente in condicao.registros:
        contador[0] += 1
        linhas.append(
            [
                f"rumble-bits-{contador[0]}",
                linha_id,
                lado,
                # `degrau` VAZIO, e de propósito: este ensaio mede a SAÍDA (o
                # motor girou), não a volta. Declarar degrau que não se mediu é a
                # fabricação que a ENSAIO-QUE-NAO-DIZ-O-DEGRAU-01 existe para
                # impedir. Posicional, como as outras colunas deste escritor.
                "",
                # `ponte` VAZIA, pela mesma razão e no mesmo lugar
                # (ENSAIO-QUE-NAO-DIZ-A-PONTE-01, 20/08/2026): este ensaio fala
                # com o aparelho pelo hidraw, sem jogo e sem vpad no meio, então
                # não há ponte a declarar. Vazio aqui quer dizer "não declarou",
                # nunca "serve para toda ponte". Posicional, como o `degrau`.
                "",
                quando,
                suspeito,
                "sim" if presente else "não",
                resultado,
                # `resultado_da_feature`, vazia (13/08/2026): aqui o `resultado`
                # JÁ é o que a feature fez — o motor girou ou não —, e vazio
                # quer dizer exatamente isso. A coluna existe para o caso em que
                # o `resultado` fala do SUSPEITO, que não é o deste ensaio.
                # Ela é POSICIONAL neste escritor: o lugar dela é entre
                # `resultado` e `observado_por`, como no cabeçalho.
                "",
                "olho-dela",
                fonte,
                nota,
                "",
            ]
        )
    return linhas


def gravar_no_caderno(linhas: list[list[str]]) -> None:
    novo = not CADERNO.exists()
    with CADERNO.open("a", encoding="utf-8", newline="") as fh:
        escritor = csv.writer(fh)
        if novo:
            escritor.writerow(
                # `degrau` e `ponte` entram depois de `transporte` porque são o
                # mesmo tipo de eixo: o que a medição estava medindo
                # (ENSAIO-QUE-NAO-DIZ-O-DEGRAU-01, 20/08/2026) e POR ONDE ela
                # chegou (ENSAIO-QUE-NAO-DIZ-A-PONTE-01, 20/08/2026). Este
                # ensaio mede SAÍDA e fala direto com o aparelho, então os dois
                # saem VAZIOS — declarar degrau ou ponte que não se mediu é a
                # fabricação que a regra existe para impedir.
                ["id", "linha_id", "transporte", "degrau", "ponte", "quando",
                 "suspeito",
                 "presente", "resultado", "resultado_da_feature", "observado_por",
                 "fonte", "nota", "linha_id_v1"]
            )
        escritor.writerows(linhas)


# --------------------------------------------------------------------------
# Os modos
# --------------------------------------------------------------------------


def cabecalho(fisico: Fisico, base: bytearray, args: argparse.Namespace) -> None:
    f0, f1, f2 = flags_de(base)
    print("=" * 78)
    print("  ENSAIO — UM BIT DE AUTORIZAÇÃO POR VEZ")
    print("=" * 78)
    print(f"  hidraw ............ {fisico.hidraw}")
    print(f"  transporte ........ {fisico.transporte} (lido do uevent, não da memória)")
    # A porta vai ao lado da biblioteca pelo mesmo motivo que ela: medir no nó
    # escondido produz zero convincente e falso, como medir contra a biblioteca
    # errada produz alarme convincente e falso.
    print(f"  {declaracao_da_porta()}")
    print(f"  daemon ............ {'ATIVO' if daemon_ativo() else 'parado'}")
    print(f"  idade ............. {idade_do_daemon()}")
    print(f"  supressão de LED .. {'ligada' if args.suprimir_leds else 'DESLIGADA'} "
          "(ligada é o estado normal: o kernel é dono da barra)")
    print()
    print("  A LINHA DE BASE, MEDIDA NO PRODUTO (core/backend_pydualsense.py):")
    print(f"    {descrever_flags((f0, f1, f2))}")
    if not f2 & BITS["v2"].mascara:
        print("    ATENÇÃO, e é medição: o bit v2 NÃO está na base. O produto escreve")
        print("    QUATRO bits no código e TRÊS no fio — `flag2` nasce do `ledOption`,")
        print("    que nunca chega a 0x04. Por isso a condição 5 LIGA o v2 em vez de")
        print("    apagá-lo: não se apaga o que nunca esteve aceso.")
    print(f"    common inteiro: {hexdump(base)}")
    if f0 & 0x0C:
        print("    AVISO: a base do produto também autoriza os GATILHOS (flag0 0x0C) e")
        print("    o bloco de gatilho sai com modo 0 — durante o ensaio os efeitos de")
        print("    gatilho ficam desligados. O daemon os devolve ao religar (ele")
        print("    reativa o perfil do disco). Para não encostar neles: --sem-mexer-nos-gatilhos")
    print()


def imprimir_condicao(condicao: Condicao, base: bytearray) -> tuple[int, int, int]:
    flags = aplicar_deltas(flags_de(base), condicao.deltas)
    print("-" * 78)
    print(f"  passo {condicao.ordem} de {len(ROTEIRO)} · {condicao.rotulo}")
    print(f"    previsão ...... {condicao.previsao}")
    print(f"    o que prova ... {condicao.o_que_prova}")
    return flags


def escolher_condicoes(chaves: list[str] | None) -> tuple[Condicao, ...]:
    """O roteiro inteiro, ou só as condições pedidas — na ORDEM do roteiro."""
    if not chaves:
        return ROTEIRO
    return tuple(c for c in ROTEIRO if c.chave in set(chaves))


def modo_seco(fisico: Fisico, base: bytearray, args: argparse.Namespace) -> int:
    """O ensaio inteiro SEM tocar no aparelho: os bytes, os flags, a parada.

    É o que dá para testar sem hardware — e é o que se roda antes de chamar
    ela para a bancada.
    """
    bancada = Bancada(fisico=fisico, base=base, seco=True)
    print("  MODO SECO: nada é aberto, nada é escrito, o daemon segue de pé.")
    print()
    for condicao in escolher_condicoes(args.condicoes):
        flags = imprimir_condicao(condicao, base)
        bancada.pulso(flags, args.weak, args.strong, 0.0)
        for suspeito, presente in condicao.registros:
            print(f"    caderno ....... {suspeito} · presente={'sim' if presente else 'não'}")
        print()
    print("=" * 78)
    print("  A parada acima é a mesma que roda na bancada — inclusive no Ctrl+C.")
    print("  O que só o APARELHO responde: se o motor gira. Nenhuma linha deste")
    print("  modo prova vibração; elas provam o que o instrumento MANDA.")
    print("=" * 78)
    return 0


def modo_parar(fisico: Fisico, base: bytearray) -> int:
    """Pânico: só manda a sequência de parada e sai."""
    if daemon_ativo():
        print("  O daemon está ATIVO — ele é o dono do hidraw. Para parar um motor")
        print("  preso pelo caminho do produto, use a aba Rumble ('Parar') ou:")
        print("    .venv/bin/hefesto test rumble --weak 0 --strong 0")
        print("  Este modo é para quando o daemon está PARADO (durante o ensaio).")
        print("  Rode assim mesmo? Ctrl+C para desistir.")
        input("    [enter] para mandar a parada mesmo com o daemon vivo ")
    bancada = Bancada(fisico=fisico, base=base)
    try:
        bancada.abrir()
        print(f"  {bancada.porta}")
        bancada.parar("pânico")
    except PortaFechadaError as erro:
        print(f"  {erro}")
        return 4
    finally:
        bancada.fechar()
    print("  Sequência de parada mandada. Confirme com ela que o controle está mudo.")
    return 0


def modo_ensaio(fisico: Fisico, base: bytearray, args: argparse.Namespace) -> int:
    if not args.confirmado:
        print("  ESTE MODO PARA O DAEMON. Não há caminho pelo IPC para variar os")
        print("  bits (medido: `rumble.set` só carrega weak/strong), e escrever no")
        print("  hidraw com o daemon vivo mede a briga entre dois escritores.")
        print("  Enquanto o ensaio roda, o Hefesto está DESLIGADO: sem perfil, sem")
        print("  vibração de jogo, sem keepalive.")
        print()
        print("  Rode de novo com --confirmo-parar-o-daemon, com ela na bancada.")
        return 2

    estava_ativo = daemon_ativo()
    if estava_ativo:
        print(f"  PARANDO {SERVICO} — o produto fica desligado até o fim do ensaio.")
        subprocess.run(["systemctl", "--user", "stop", SERVICO], check=False)
        time.sleep(1.5)
    if daemon_ativo():
        print("  O daemon NÃO parou. Abortando: escrever agora seria medir a briga.")
        return 2
    donos = donos_do_hidraw(fisico.hidraw)
    if donos:
        print(f"  Alguém ainda está com {fisico.hidraw} aberto: {', '.join(donos)}")
        print("  Feche o Steam/jogo (ou o que for) e rode de novo — dois escritores")
        print("  no mesmo nó é exatamente a armadilha que faz o instrumento mentir.")
        if estava_ativo:
            subprocess.run(["systemctl", "--user", "start", SERVICO], check=False)
        return 2
    print("  hidraw livre: nenhum outro processo deste usuário o tem aberto.")
    print()

    condicoes = escolher_condicoes(args.condicoes)
    if len(condicoes) < len(ROTEIRO):
        print(f"  RECORTE: só {len(condicoes)} de {len(ROTEIRO)} condições. Sem a base no")
        print("  começo e no fim, nada controla bateria caindo nem mão acostumando —")
        print("  a resposta vale menos, e isso fica dito aqui.")
        print()
    bancada = Bancada(fisico=fisico, base=base, keepalive=not args.sem_keepalive)
    respostas: list[tuple[Condicao, str, str]] = []
    quando = datetime.now().isoformat(timespec="seconds")

    def _sinal(_num: int, _frame: object) -> None:
        bancada.parar("sinal recebido")
        bancada.fechar()
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, _sinal)
    signal.signal(signal.SIGTERM, _sinal)

    try:
        try:
            bancada.abrir()
        except PortaFechadaError as erro:
            print(f"  {erro}")
            return 4
        # A porta REALMENTE usada, depois de aberta — o cabeçalho declarou a
        # provável; esta é a que valeu para este nó.
        print(f"  {bancada.porta}\n")
        for condicao in condicoes:
            flags = imprimir_condicao(condicao, base)
            input("    [enter] para disparar ")
            bancada.pulso(flags, args.weak, args.strong, args.segundos)
            pergunta = "    VIBROU? (s = vibrou / n = não vibrou / ? = não sei) "
            resposta = ""
            while resposta not in ("s", "n", "?"):
                resposta = input(pergunta).strip().lower()
            resultado = {"s": "vibrou", "n": "não vibrou", "?": "sem resposta"}[resposta]
            nota = ""
            if condicao.pergunta_extra:
                nota = input(f"    {condicao.pergunta_extra} ").strip()
            outra = input("    Alguma observação? (enter para nenhuma) ").strip()
            nota = " · ".join([p for p in (nota, outra) if p])
            respostas.append((condicao, resultado, nota))
            print(f"    registrado: {resultado}{' — ' + nota if nota else ''}")
            print()
            time.sleep(0.4)
    except KeyboardInterrupt:
        print()
        print("  INTERROMPIDO — a parada já foi mandada.")
    finally:
        bancada.fechar()
        if estava_ativo:
            print(f"  religando {SERVICO} ...")
            subprocess.run(["systemctl", "--user", "start", SERVICO], check=False)
        print("  Lembrete honesto: religar o daemon NÃO para motor preso — o")
        print("  keepalive dele sai sem os bits de vibração de propósito. Quem")
        print("  parou o motor foi a sequência de parada acima. Se ainda vibrar:")
        print(f"    .venv/bin/python {Path(__file__).name} parar")

    print()
    print("=" * 78)
    print("  O QUE FOI OBSERVADO")
    for condicao, resultado, nota in respostas:
        print(f"    {condicao.ordem}. {condicao.chave:<16} {resultado}"
              f"{'  (' + nota + ')' if nota else ''}")
    print()

    contador = [0]
    linhas: list[list[str]] = []
    fonte = f"bancada {datetime.now():%d/%m} — bits do rumble, daemon parado"
    # O caderno do v2 aponta para o GRÃO (chave@controle) e guarda o transporte
    # em coluna própria. Sem a coluna, os ensaios de cabo e de rádio cairiam no
    # mesmo balde e um contradiria o outro — foi assim que a lightbar quase
    # perdeu o culpado isolado.
    linha_id = args.linha_id or "vibracao.rumble.esquerdo@dualsense"
    lado = {"bluetooth": "radio", "cabo": "cabo"}.get(fisico.transporte, "")
    for condicao, resultado, nota in respostas:
        if resultado == "sem resposta":
            continue
        linhas.extend(
            linhas_de_caderno(
                condicao, resultado, nota,
                linha_id=linha_id, lado=lado, fonte=fonte, quando=quando,
                contador=contador,
            )
        )
    print("  PARA O CADERNO (docs/data/ensaios.csv):")
    for linha in linhas:
        print("    " + ",".join(f'"{c}"' if "," in c else c for c in linha))
    if args.registrar and linhas:
        gravar_no_caderno(linhas)
        print(f"  gravadas {len(linhas)} linhas em {CADERNO}")
        print("  o veredicto quem calcula é: .venv/bin/python scripts/eliminacao.py")
    elif linhas:
        print("  (não gravei nada — rode com --registrar para acrescentar ao caderno)")
    print("=" * 78)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Apaga um bit de autorização do rumble por vez, com o controle na mão.",
    )
    ap.add_argument("modo", choices=("seco", "ensaio", "parar"))
    ap.add_argument("--weak", type=int, default=200, help="common[2] — motor DIREITO (0-255)")
    ap.add_argument("--strong", type=int, default=200, help="common[3] — motor ESQUERDO (0-255)")
    ap.add_argument("--segundos", type=float, default=1.5, help="duração de cada pulso")
    ap.add_argument("--confirmo-parar-o-daemon", action="store_true", dest="confirmado",
                    help="obrigatório no modo `ensaio`: ele desliga o produto enquanto roda")
    ap.add_argument("--sem-keepalive", action="store_true",
                    help="não repor o keepalive de link a 2 Hz (só para depurar o rádio)")
    ap.add_argument("--sem-supressao-de-led", action="store_false", dest="suprimir_leds",
                    help="montar a base SEM supressão de LED (não é o estado normal)")
    ap.add_argument("--sem-mexer-nos-gatilhos", action="store_true", dest="poupar_gatilhos",
                    help="apaga a autorização de gatilho (flag0 0x0C) da base — o pulso "
                         "deixa de desligar os efeitos de gatilho dela")
    ap.add_argument("--condicao", action="append", default=None, dest="condicoes",
                    choices=[c.chave for c in ROTEIRO],
                    help="roda só estas condições (repetível). Sem isto, roda o "
                         "roteiro inteiro, que é o recomendado: a base no começo e "
                         "no fim são os controles do ensaio")
    ap.add_argument("--registrar", action="store_true",
                    help="acrescenta as respostas a docs/data/ensaios.csv")
    ap.add_argument("--linha-id", default=None,
                    help="linha_id do caderno no formato chave@controle "
                         "(padrão: vibracao.rumble.esquerdo@dualsense)")
    args = ap.parse_args(argv)

    for nome, valor in (("--weak", args.weak), ("--strong", args.strong)):
        if not 0 <= valor <= 255:
            print(f"{nome} fora da faixa 0-255: {valor}")
            return 2

    fisico = achar_fisico()
    if fisico is None:
        print("Nenhum DualSense (054c:0ce6) em /sys/class/hidraw — o controle está ligado?")
        return 2

    base = linha_de_base_do_produto(
        args.weak, args.strong,
        bt=fisico.transporte == "bluetooth",
        suprimir_leds=args.suprimir_leds,
    )
    if args.poupar_gatilhos:
        base[0] &= ~0x0C & 0xFF
    cabecalho(fisico, base, args)

    if args.modo == "seco":
        return modo_seco(fisico, base, args)
    if args.modo == "parar":
        return modo_parar(fisico, base)
    return modo_ensaio(fisico, base, args)


if __name__ == "__main__":
    raise SystemExit(main())
