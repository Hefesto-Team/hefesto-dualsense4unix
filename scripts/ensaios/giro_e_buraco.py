#!/usr/bin/env python3
"""giro_e_buraco.py — o giroscópio mede zero? e some report na janela? (E-8)

AS DUAS PERGUNTAS QUE ELE RESPONDE
-----------------------------------
1. `movimento.giroscopio@dualsense` — cabo e rádio, os DOIS lados em
   `inferido-do-codigo`: *o giroscópio entrega número calibrado, em cada
   transporte?* A régua é ABSOLUTA: um controle parado na mesa **não gira**.
   Nenhuma conclusão depende de comparar um braço com o outro.
2. `movimento.imu.perda@dualsense` — cabo e rádio, também os dois em
   `inferido-do-codigo`: *dentro de uma janela, some report?* A célula do cabo
   dizia, em 14/08, que o `sensor_timestamp` "É a régua que falta — ele é
   repassado VERBATIM e nunca parseado. NÃO TENTADO: contar buraco por delta de
   `sensor_timestamp`". Este instrumento tenta — e acha uma régua melhor.

O CONTADOR DE REPORTS QUE O DRIVER JOGA FORA (a descoberta desta leva)
-----------------------------------------------------------------------
O `struct dualsense_input_report` do `hid-playstation.c:295-315` tem um
`seq_number` em `corpo[6]` e um `reserved[4]` em `corpo[11..14]`. Medido em
15/08/2026 nos quatro aparelhos da mesa 2+2:

  `corpo[6]`      (`seq_number`) .... anda de 1 em 1 **SÓ NO CABO**. No rádio
                  ele fica **constante em 1**: delta zero em **1628 de 1628
                  pares** no bruto versionado
                  `2026-08-15-E8-A-unidade-no-radio-que-dormiu-e-caiu.csv`, e
                  o mesmo em janelas mais curtas nos dois aparelhos de rádio.
                  Como régua de perda por rádio, ele é MUDO.
  `corpo[11..14]` (`reserved`) ...... lido como `__le32` é um **contador de
                  reports de 32 bits**, e anda de 1 em 1 em **100% dos pares,
                  nos quatro aparelhos, NOS DOIS TRANSPORTES**.

O kernel chama de `reserved` e nunca olha. É, hoje, a única régua de perda que
funciona igual no cabo e no rádio — e é ela que fecha a assimetria que o mapa
declara ("uma degradação de link no CABO é invisível para a telemetria").

A RÉGUA DO GIROSCÓPIO É DERIVADA DO PRÓPRIO APARELHO — e a de antes ERRAVA 62x
------------------------------------------------------------------------------
`DS_GYRO_RES_PER_DEG_S = 1024` é a resolução **DE SAÍDA**, depois da
calibração: é a escala do `ABS_RX/RY/RZ` que o kernel publica. O número CRU do
fio **não está nessa escala**. O driver converte
(`hid-playstation.c:1196-1213, :1670-1686`):

    graus_por_s = cru * speed_2x / sens_denom_do_eixo

com `speed_2x` e `sens_denom` lidos do **feature report 0x05** de CADA unidade.
Medido nos quatro aparelhos: `speed_2x = 1080` e `sens_denom ~ 17700`, ou seja
**~16,4 LSB por grau/s** no fio — e não 1024.

Dividir o cru por 1024 encolhe a leitura por **62,5x**. Isso não é imprecisão:
é a `A-3` desta casa em estado puro, porque a régua errada **torna o controle
negativo impossível de reprovar** — com ela, um controle girando a 60 graus/s
leria "0,96 graus/s" e passaria por parado. O `imu_no_cabo.py` imprimia o
giroscópio assim, e o bruto `2026-08-15-E4-imu_no_cabo.csv` guarda os números
errados; a correção está datada na docstring dele.

O CONTROLE POSITIVO E O NEGATIVO — os dois, e sem pedir a mão dela (Lei 2)
---------------------------------------------------------------------------
POSITIVO 1: no MESMO report, o acelerômetro tem de dar 1 g. É o que prova que
  os offsets e o transporte estão certos — se o corpo estivesse deslocado, o
  módulo da gravidade não sairia.
POSITIVO 2: a conta feita AQUI (cru x `speed_2x`/`sens_denom`, do feature 0x05)
  tem de bater com o `ABS_RX/RY/RZ` que o KERNEL publica no nó *Motion
  Sensors*. São duas implementações independentes da mesma régua; se elas
  divergirem, quem está errado sou eu, e o ensaio para.
NEGATIVO: o giroscópio decodificado no offset do ACELERÔMETRO, com a régua boa,
  tem de dar **centenas** de graus/s (a gravidade vale ~8192 LSB, que na escala
  do giro são ~500 graus/s). Sem ele, "deu perto de zero" não valeria nada:
  seria preciso mostrar que a régua CONSEGUE produzir número grande.
NEGATIVO do instrumento: a maior parada do próprio laço de leitura é medida e
  impressa. Um buraco na fila que coincida com o laço parado é MEU, não do
  enlace — e a tabela separa os dois.

A PORTA, DECLARADA
-------------------
**Broker**, nos quatro físicos, por `comum.abrir_no_hidraw`, com o daemon VIVO
(Lei 1). Os hidraw dos físicos estão `0600 root:root` — é o próprio Hefesto
escondendo-os do jogo — e um `open()` direto ali mede `EACCES`, não o aparelho.

O nó evdev *Motion Sensors* é aberto **só para o controle positivo 2**, em
`O_RDONLY`, **sem `EVIOCGRAB`**: ler dali não rouba evento de ninguém, e o
estado do grab vai no cabeçalho.

O QUE ELE NUNCA FAZ (Lei 3)
----------------------------
**Não escreve no aparelho.** Nem um byte, em transporte nenhum. O feature 0x05
sai por `HIDIOCGFEATURE` num fd **`O_RDONLY`** (conferido: o kernel aceita), que
é GET_REPORT — leitura. Nada de `SET_FEATURE`, nada de output report.

PRECISA DO DAEMON PARADO? **Não** — e não pode pedir: parar o daemon derruba os
quatro vpads e o co-op, que é a mesa inteira.

USO
    giro_e_buraco.py                          # 20 s, os quatro físicos
    giro_e_buraco.py --segundos 60 --csv /tmp/e8.csv
    giro_e_buraco.py --sem-mascara            # MAC inteiro na TELA (nunca em arquivo)
"""

from __future__ import annotations

import argparse
import csv
import fcntl
import math
import os
import selectors
import struct
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comum import (
    CABO,
    RADIO,
    Aparelho,
    NoAberto,
    PortaFechadaError,
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    censo_da_mesa,
    descobrir_aparelhos,
    estado_do_grab,
    fisicos,
    ler_texto,
    resumo,
    tabela,
)

# A régua do acelerômetro, os offsets por transporte e a máscara de MAC são
# REUSADOS do E-4, nunca recopiados: uma régua só na casa. Foi assim que o
# `identidade_do_vpad.py` nasceu, e é a mesma disciplina.
from imu_no_cabo import (
    DS_ACC_RES_PER_G,
    DS_GYRO_RES_PER_DEG_S,
    OFFSET_ACEL_NO_CORPO,
    OFFSET_GIRO_NO_CORPO,
    PERFIL_DO_TRANSPORTE,
    _no_de_movimento,
    mascarar,
)

#: `corpo[6]` — o `seq_number` do `struct dualsense_input_report`. MEDIDO em
#: 15/08/2026: anda de 1 em 1 no CABO e fica CONSTANTE no rádio. Fica aqui como
#: régua declarada e como o CONTRA-exemplo do contador de baixo.
OFFSET_SEQ_NO_CORPO = 6

#: `corpo[11..14]` — o `reserved[4]` que o driver ignora, e que lido como
#: `__le32` é um contador de reports que anda de 1 em 1 nos DOIS transportes.
#: É a régua de perda deste instrumento.
OFFSET_CONTADOR_NO_CORPO = 11

#: `corpo[27..30]` — o `sensor_timestamp`, `__le32`, em unidades de 0,33 us
#: (`hid-playstation.c:1688-1702`: o driver divide por 3 para virar us). É o
#: relógio DO CONTROLE, e serve para separar "o firmware calou" de "o enlace
#: comeu": os dois produzem silêncio no relógio do host, e só este campo diz
#: qual dos dois foi.
OFFSET_TS_NO_CORPO = 27

#: Quantos ticks do `sensor_timestamp` valem um microssegundo.
TICKS_POR_US = 3

#: Feature report da calibração da IMU (`DS_FEATURE_REPORT_CALIBRATION` /
#: `_SIZE`, `hid-playstation.c`). Sai por GET_REPORT — leitura pura.
FEATURE_CALIBRACAO = 0x05
TAMANHO_CALIBRACAO = 41

#: `HIDIOCGFEATURE(len)` = `_IOC(READ|WRITE, 'H', 0x07, len)`. O `WRITE` do
#: nome é a direção do BUFFER do ioctl (o report id entra), não escrita no
#: aparelho: é um GET_REPORT, e roda num fd `O_RDONLY`.
def _hidiocgfeature(tamanho: int) -> int:
    return (3 << 30) | (tamanho << 16) | (ord("H") << 8) | 0x07


#: `EVIOCGABS(code)` — a `resolution` que o kernel publica para cada eixo.
_TAMANHO_ABSINFO = 24


def _eviocgabs(codigo: int) -> int:
    return (2 << 30) | (_TAMANHO_ABSINFO << 16) | (0x45 << 8) | (0x40 + codigo)


#: Códigos evdev dos seis eixos do nó *Motion Sensors*: ABS_X/Y/Z é o
#: acelerômetro, ABS_RX/RY/RZ é o giroscópio (`hid-playstation.c` os registra
#: nessa ordem em `gyro_calib_data`/`accel_calib_data`).
ABS_ACEL = (0x00, 0x01, 0x02)
ABS_GIRO = (0x03, 0x04, 0x05)

_BYTES_POR_LEITURA = 256

#: O teto abaixo do qual um controle parado conta como PARADO. Não é chute
#: estatístico: 5 graus/s é ~0,24% do fundo de escala (+-2048 graus/s), e o
#: negativo deste ensaio (o giro lido no offset do acelerômetro) dá ~500
#: graus/s — cem vezes acima. Entre os dois cabe qualquer bias de fábrica.
TETO_DE_PARADO_DPS = 5.0

#: O teto do controle positivo do acelerômetro, o mesmo do E-4.
FAIXA_DE_1G = (0.90, 1.10)


def alimentacao(aparelho: Aparelho) -> tuple[str, str]:
    """(`status`, `capacity`) da bateria deste controle, do sysfs. Leitura pura.

    Entra no ensaio porque em 15/08/2026, às 22h17, dois DualSense no MESMO
    rádio, no MESMO host e na MESMA janela deram 352,5 Hz e ZERO Hz. O que os
    separava não era o enlace: um estava `Charging` e o outro `Discharging`. Um
    instrumento que não imprimisse isto teria oferecido "o rádio às vezes cala"
    como se fosse propriedade do transporte.
    """
    raiz = os.path.join(aparelho.dir_device, "power_supply")
    if not os.path.isdir(raiz):
        return ("?", "?")
    for entrada in sorted(os.listdir(raiz)):
        dentro = os.path.join(raiz, entrada)
        estado = ler_texto(os.path.join(dentro, "status")).strip()
        carga = ler_texto(os.path.join(dentro, "capacity")).strip()
        if estado or carga:
            return (estado or "?", carga or "?")
    return ("?", "?")


@dataclass
class Calibracao:
    """A régua do giroscópio DESTA unidade, lida do feature 0x05 dela.

    `bias` NÃO entra: o driver lê `gyro_pitch_bias` e companhia e depois faz
    `bias = 0` de propósito (`hid-playstation.c:1200, :1206, :1212`). Repetir a
    escolha dele é o que permite comparar o número daqui com o `ABS_R*` que ele
    publica — que é o controle positivo 2.
    """

    ok: bool = False
    motivo: str = ""
    speed_2x: int = 0
    denom: tuple[int, int, int] = (0, 0, 0)
    bias_lido: tuple[int, int, int] = (0, 0, 0)

    @property
    def dps_por_lsb(self) -> tuple[float, float, float]:
        """Quantos graus/s vale UM LSB cru, por eixo. Zero se não pude ler."""
        if not self.ok:
            return (0.0, 0.0, 0.0)
        return tuple(  # type: ignore[return-value]
            (self.speed_2x / d) if d else 0.0 for d in self.denom
        )

    @property
    def lsb_por_dps(self) -> float:
        """A régua em uma linha: LSB crus por grau/s, no eixo X. Para a tabela."""
        f = self.dps_por_lsb[0]
        return (1.0 / f) if f else 0.0


def ler_calibracao(aparelho: Aparelho) -> Calibracao:
    """O feature 0x05 desta unidade -> a régua do giroscópio dela.

    Pela porta do broker e em `O_RDONLY`: `HIDIOCGFEATURE` é GET_REPORT, e o
    kernel o aceita num fd de leitura (conferido em 15/08/2026). Pedir um fd
    de escrita para ler seria abrir a porta que a Lei 3 fecha.
    """
    try:
        no = abrir_no_hidraw(aparelho.caminho_hidraw, escrita=False)
    except (PortaFechadaError, OSError) as erro:
        return Calibracao(motivo=f"não abriu: {erro}")
    try:
        buf = bytearray(TAMANHO_CALIBRACAO)
        buf[0] = FEATURE_CALIBRACAO
        lidos = fcntl.ioctl(no.fd, _hidiocgfeature(TAMANHO_CALIBRACAO), buf, True)
    except OSError as erro:
        return Calibracao(motivo=f"GET_FEATURE 0x05 falhou: {erro.strerror or erro}")
    finally:
        no.fechar()

    if lidos < 23:
        return Calibracao(motivo=f"feature 0x05 curto ({lidos} B)")

    corpo = bytes(buf[1:lidos])

    def s16(deslocamento: int) -> int:
        return struct.unpack_from("<h", corpo, deslocamento)[0]

    bias = (s16(0), s16(2), s16(4))
    mais = (s16(6), s16(10), s16(14))
    menos = (s16(8), s16(12), s16(16))
    speed_2x = s16(18) + s16(20)
    denom = tuple(abs(mais[i] - bias[i]) + abs(menos[i] - bias[i]) for i in range(3))
    if speed_2x == 0 or 0 in denom:
        return Calibracao(
            motivo=f"calibração inválida (speed_2x={speed_2x}, denom={denom})",
            speed_2x=speed_2x,
            denom=denom,  # type: ignore[arg-type]
            bias_lido=bias,
        )
    return Calibracao(
        ok=True,
        motivo="feature 0x05 lido por GET_REPORT (fd O_RDONLY)",
        speed_2x=speed_2x,
        denom=denom,  # type: ignore[arg-type]
        bias_lido=bias,
    )


@dataclass
class Medida:
    """O que se acumulou de UM controle numa janela. Nada de opinião aqui."""

    aparelho: Aparelho
    calib: Calibracao = field(default_factory=Calibracao)
    porta: str = ""
    erro: str = ""
    segundos: float = 0.0
    energia: str = "?"
    bateria: str = "?"

    lidos: int = 0
    aproveitados: int = 0
    curtos: int = 0
    ids_vistos: dict[int, int] = field(default_factory=dict)

    # --- o giroscópio -------------------------------------------------------
    #: Os triplos CRUS, guardados como vieram do fio. A conversão para graus/s
    #: acontece em `finalizar`, DEPOIS da janela, porque a régua (feature 0x05)
    #: só é lida depois — ver `main`.
    giros_crus: list[tuple[int, int, int]] = field(default_factory=list)
    aceis_crus: list[tuple[int, int, int]] = field(default_factory=list)
    giros_dps: list[float] = field(default_factory=list)       # régua boa
    giros_ingenuos: list[float] = field(default_factory=list)  # cru/1024 (A-3)
    giros_no_offset_errado: list[float] = field(default_factory=list)  # negativo
    somas_giro_lsb: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    modulos_g: list[float] = field(default_factory=list)       # positivo 1

    def finalizar(self) -> None:
        """Converte o cru guardado para graus/s, com a régua já lida.

        Existe porque a régua é lida DEPOIS da janela: um `GET_REPORT` por
        Bluetooth é tráfego no enlace, e este instrumento mede justamente
        silêncio de enlace. Ler a calibração antes seria cutucar o aparelho e
        depois medir se ele está quieto.
        """
        fator = self.calib.dps_por_lsb
        for gx, gy, gz in self.giros_crus:
            self.giros_ingenuos.append(
                math.sqrt(gx * gx + gy * gy + gz * gz) / DS_GYRO_RES_PER_DEG_S
            )
            if not self.calib.ok:
                continue
            dx, dy, dz = (gx * fator[0], gy * fator[1], gz * fator[2])
            self.giros_dps.append(math.sqrt(dx * dx + dy * dy + dz * dz))
        if not self.calib.ok:
            return
        for ax, ay, az in self.aceis_crus:
            # NEGATIVO: o acelerômetro lido COMO SE fosse giroscópio. A
            # gravidade vale ~8192 LSB, que nesta escala são centenas de graus/s.
            nx, ny, nz = (ax * fator[0], ay * fator[1], az * fator[2])
            self.giros_no_offset_errado.append(math.sqrt(nx * nx + ny * ny + nz * nz))

    # --- a perda -----------------------------------------------------------
    contador_anterior: int | None = None
    seq_anterior: int | None = None
    ts_anterior: int | None = None
    pares: int = 0
    saltos_do_contador: list[int] = field(default_factory=list)  # (delta-1) > 0
    reports_perdidos: int = 0
    saltos_do_seq: int = 0
    seq_parado: int = 0
    deltas_ts_us: list[float] = field(default_factory=list)
    intervalos_host_ms: list[float] = field(default_factory=list)
    #: intervalo do host no par EXATO em que o contador saltou — é o que separa
    #: "o enlace comeu" de "eu estava parado".
    host_ms_nos_saltos: list[float] = field(default_factory=list)
    ultimo_ns: int = 0
    #: O silêncio da CAUDA: do último report até o fim da janela. Sem ele o
    #: instrumento mentia por omissão — medido em 15/08/2026 às 22h21, um
    #: controle que calou nos últimos 55 s de uma janela de 60 s apareceu com
    #: "silêncio máximo 19 ms", porque um silêncio que nunca termina não fecha
    #: nenhum par e nenhum par é nenhuma amostra.
    cauda_muda_ms: float = 0.0

    # --- o controle positivo 2 (o kernel fazendo a mesma conta) -------------
    evdev_no: str = ""
    evdev_grab: str = ""
    evdev_resolucao_giro: int | None = None
    evdev_amostras: int = 0
    evdev_giros_dps: list[float] = field(default_factory=list)
    evdev_motivo: str = ""

    @staticmethod
    def _percentil(valores: list[float], fracao: float) -> float:
        if not valores:
            return 0.0
        ordenados = sorted(valores)
        indice = min(len(ordenados) - 1, int(len(ordenados) * fracao))
        return ordenados[indice]

    @property
    def giro_mediano_dps(self) -> float:
        return self._percentil(self.giros_dps, 0.5)

    @property
    def giro_maximo_dps(self) -> float:
        return max(self.giros_dps) if self.giros_dps else 0.0

    @property
    def giro_ingenuo_mediano(self) -> float:
        return self._percentil(self.giros_ingenuos, 0.5)

    @property
    def negativo_mediano_dps(self) -> float:
        return self._percentil(self.giros_no_offset_errado, 0.5)

    @property
    def evdev_giro_mediano_dps(self) -> float:
        return self._percentil(self.evdev_giros_dps, 0.5)

    @property
    def modulo_g_mediano(self) -> float:
        return self._percentil(self.modulos_g, 0.5)

    @property
    def eixos_giro_dps(self) -> list[float]:
        """A média por eixo, na régua boa — é o bias de repouso da unidade."""
        if not self.aproveitados or not self.calib.ok:
            return [0.0, 0.0, 0.0]
        fator = self.calib.dps_por_lsb
        return [self.somas_giro_lsb[i] / self.aproveitados * fator[i] for i in range(3)]

    @property
    def taxa_hz(self) -> float:
        return self.aproveitados / self.segundos if self.segundos > 0 else 0.0

    @property
    def silencio_p95_ms(self) -> float:
        return self._percentil(self.intervalos_host_ms, 0.95)

    @property
    def silencio_maximo_ms(self) -> float:
        """O maior silêncio da janela, JÁ INCLUINDO a cauda que nunca fechou."""
        entre = max(self.intervalos_host_ms) if self.intervalos_host_ms else 0.0
        return max(entre, self.cauda_muda_ms)

    @property
    def fracao_da_janela_medida(self) -> float:
        """Quanto da janela está coberto por intervalo medido, de 0 a 1.

        Muito abaixo de 1 quer dizer que o aparelho passou a maior parte da
        janela calado — e que qualquer p95 acima é o p95 do pedaço em que ele
        falou, não da janela.
        """
        if self.segundos <= 0:
            return 0.0
        return min(1.0, sum(self.intervalos_host_ms) / 1000.0 / self.segundos)

    @property
    def cadencia_do_controle_hz(self) -> float:
        """A taxa pelo relógio DO CONTROLE — independente do relógio do host."""
        mediano = self._percentil(self.deltas_ts_us, 0.5)
        return (1e6 / mediano) if mediano > 0 else 0.0

    @property
    def apelido_mascarado(self) -> str:
        return mascarar(self.aparelho.mac) or self.aparelho.hidraw


def _consumir(medida: Medida, bruto: bytes, agora_ns: int) -> None:
    """Um report cru -> giroscópio nas três réguas, e o par de perda."""
    medida.lidos += 1
    if not bruto:
        return
    identificador = bruto[0]
    medida.ids_vistos[identificador] = medida.ids_vistos.get(identificador, 0) + 1
    perfil = PERFIL_DO_TRANSPORTE.get(medida.aparelho.transporte)
    if perfil is None or identificador != perfil["report_id"]:
        return
    corpo = perfil["corpo"]
    if len(bruto) < corpo + OFFSET_TS_NO_CORPO + 4:
        medida.curtos += 1
        return

    medida.aproveitados += 1

    gx, gy, gz = struct.unpack_from("<3h", bruto, corpo + OFFSET_GIRO_NO_CORPO)
    ax, ay, az = struct.unpack_from("<3h", bruto, corpo + OFFSET_ACEL_NO_CORPO)

    for indice, valor in enumerate((gx, gy, gz)):
        medida.somas_giro_lsb[indice] += valor
    medida.giros_crus.append((gx, gy, gz))
    medida.aceis_crus.append((ax, ay, az))

    # Controle positivo 1: o mesmo report tem de trazer 1 g. Esta é a única
    # conta que roda DENTRO da janela, porque a régua dela (8192 LSB/g) não
    # depende de perguntar nada ao aparelho.
    medida.modulos_g.append(math.sqrt(ax * ax + ay * ay + az * az) / DS_ACC_RES_PER_G)

    # --- a perda -----------------------------------------------------------
    contador = struct.unpack_from("<I", bruto, corpo + OFFSET_CONTADOR_NO_CORPO)[0]
    seq = bruto[corpo + OFFSET_SEQ_NO_CORPO]
    carimbo = struct.unpack_from("<I", bruto, corpo + OFFSET_TS_NO_CORPO)[0]

    if medida.contador_anterior is not None:
        medida.pares += 1
        delta = (contador - medida.contador_anterior) % (1 << 32)
        intervalo_ms = (agora_ns - medida.ultimo_ns) / 1e6
        medida.intervalos_host_ms.append(intervalo_ms)
        if delta > 1:
            medida.saltos_do_contador.append(delta - 1)
            medida.reports_perdidos += delta - 1
            medida.host_ms_nos_saltos.append(intervalo_ms)
        delta_seq = (seq - (medida.seq_anterior or 0)) % 256
        if delta_seq == 0:
            medida.seq_parado += 1
        elif delta_seq > 1:
            medida.saltos_do_seq += 1
        if medida.ts_anterior is not None:
            medida.deltas_ts_us.append(
                ((carimbo - medida.ts_anterior) % (1 << 32)) / TICKS_POR_US
            )

    medida.contador_anterior = contador
    medida.seq_anterior = seq
    medida.ts_anterior = carimbo
    medida.ultimo_ns = agora_ns


def _abrir_evdev(medida: Medida) -> int | None:
    """O nó *Motion Sensors* deste controle, em `O_RDONLY` e SEM `EVIOCGRAB`.

    Ler dali não rouba evento de ninguém. Se o nó não abrir, ou estiver pego por
    terceiro, isso vira MOTIVO na tabela — nunca um zero silencioso, que é o
    modo de falha que o `leitura_de_zero` desta casa existe para impedir.
    """
    caminho = _no_de_movimento(medida.aparelho)
    medida.evdev_no = caminho
    if not caminho:
        medida.evdev_motivo = "não achei o nó Motion Sensors"
        return None
    medida.evdev_grab = estado_do_grab(caminho)
    try:
        fd = os.open(caminho, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    except OSError as erro:
        medida.evdev_motivo = f"{caminho}: {erro.strerror or erro}"
        return None
    try:
        bruto = fcntl.ioctl(fd, _eviocgabs(ABS_GIRO[0]), bytes(_TAMANHO_ABSINFO))
    except OSError as erro:
        medida.evdev_motivo = f"{caminho}: EVIOCGABS falhou ({erro.strerror or erro})"
        os.close(fd)
        return None
    resolucao = struct.unpack("6i", bruto)[5] or DS_GYRO_RES_PER_DEG_S
    medida.evdev_resolucao_giro = resolucao
    medida.evdev_motivo = f"{caminho}, resolution={resolucao}, sem EVIOCGRAB"
    return fd


def _consumir_evdev(medida: Medida, dados: bytes, atual: dict[int, int]) -> None:
    """Eventos crus do nó de movimento -> |w| pela conta DO KERNEL."""
    resolucao = medida.evdev_resolucao_giro or DS_GYRO_RES_PER_DEG_S
    for i in range(0, len(dados) - 23, 24):
        _s, _us, tipo, codigo, valor = struct.unpack_from("QQHHi", dados, i)
        if tipo == 0x03:  # EV_ABS
            atual[codigo] = valor
        elif tipo == 0x00 and codigo == 0 and all(c in atual for c in ABS_GIRO):
            # SYN_REPORT com os três eixos já vistos = uma amostra completa.
            medida.evdev_amostras += 1
            medida.evdev_giros_dps.append(
                math.sqrt(sum(atual[c] ** 2 for c in ABS_GIRO)) / resolucao
            )


def medir(medidas: list[Medida], segundos: float) -> float:
    """Lê hidraw E evdev dos quatro físicos na MESMA janela; devolve a parada do laço.

    A MESMA janela não é elegância: o controle positivo 2 compara a minha conta
    com a do kernel, e duas janelas em fila não comparam nada. Medido em
    15/08/2026 às 22h15, com o evdev numa janela separada de 2 s: um aparelho
    foi encostado durante a janela do hidraw e não durante a do evdev, e o
    instrumento acusou 1,15 contra 26,18 graus/s — divergência de instrumento
    sem nenhum instrumento errado. Este parágrafo é o preço daquele minuto.

    A maior parada do laço é o controle negativo do próprio instrumento: se ela
    for da ordem de um buraco medido, o buraco pode ser meu. Ela sai na tabela
    ao lado do silêncio de cada aparelho, e não num comentário.
    """
    seletor = selectors.DefaultSelector()
    de_hidraw: dict[int, Medida] = {}
    de_evdev: dict[int, tuple[Medida, dict[int, int]]] = {}
    fechar: list[NoAberto] = []
    fds_evdev: list[int] = []

    for medida in medidas:
        try:
            no = abrir_no_hidraw(medida.aparelho.caminho_hidraw, escrita=False)
        except PortaFechadaError as erro:
            medida.erro = str(erro)
            continue
        except OSError as erro:
            medida.erro = f"{erro.strerror or erro}"
            continue
        medida.porta = no.porta
        os.set_blocking(no.fd, False)
        seletor.register(no.fd, selectors.EVENT_READ)
        de_hidraw[no.fd] = medida
        fechar.append(no)

        fd_evdev = _abrir_evdev(medida)
        if fd_evdev is not None:
            seletor.register(fd_evdev, selectors.EVENT_READ)
            de_evdev[fd_evdev] = (medida, {})
            fds_evdev.append(fd_evdev)

    if not de_hidraw:
        seletor.close()
        return 0.0

    inicio = time.monotonic()
    fim = inicio + segundos
    maior_parada_ms = 0.0
    volta_anterior_ns = time.monotonic_ns()
    while True:
        restante = fim - time.monotonic()
        if restante <= 0:
            break
        eventos = seletor.select(min(restante, 0.05))
        agora_volta = time.monotonic_ns()
        if eventos:
            maior_parada_ms = max(maior_parada_ms, (agora_volta - volta_anterior_ns) / 1e6)
        volta_anterior_ns = agora_volta
        for chave, _ in eventos:
            no_hidraw = de_hidraw.get(chave.fd)
            try:
                if no_hidraw is not None:
                    bruto = os.read(chave.fd, _BYTES_POR_LEITURA)
                else:
                    bruto = os.read(chave.fd, 24 * 256)
            except BlockingIOError:
                continue
            except OSError as erro:
                if no_hidraw is not None:
                    no_hidraw.erro = f"leitura interrompida: {erro.strerror or erro}"
                seletor.unregister(chave.fd)
                continue
            if no_hidraw is not None:
                _consumir(no_hidraw, bruto, time.monotonic_ns())
            else:
                medida, atual = de_evdev[chave.fd]
                _consumir_evdev(medida, bruto, atual)

    decorrido = time.monotonic() - inicio
    fim_ns = time.monotonic_ns()
    for medida in de_hidraw.values():
        medida.segundos = decorrido
        if medida.ultimo_ns:
            medida.cauda_muda_ms = (fim_ns - medida.ultimo_ns) / 1e6

    seletor.close()
    for no in fechar:
        no.fechar()
    for fd in fds_evdev:
        os.close(fd)
    return maior_parada_ms


def _nome(medida: Medida, *, sem_mascara: bool) -> str:
    if sem_mascara:
        return medida.aparelho.mac or medida.aparelho.hidraw
    return medida.apelido_mascarado


def _escrever_csv(caminho: str, medidas: list[Medida], quando: str, laco_ms: float) -> None:
    """A tabela que vira lembrança. MAC sempre mascarado, mesmo com --sem-mascara."""
    with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo, lineterminator="\n")
        escritor.writerow(
            [
                "quando",
                "mac_mascarado",
                "transporte",
                "hidraw",
                "porta",
                "energia",
                "bateria_pct",
                "segundos",
                "reports",
                "taxa_host_hz",
                "cadencia_do_controle_hz",
                "giro_dps_mediano",
                "giro_dps_maximo",
                "giro_x_dps",
                "giro_y_dps",
                "giro_z_dps",
                "giro_pela_regua_ingenua_1024",
                "giro_no_offset_do_acelerometro_dps",
                "evdev_no",
                "evdev_amostras",
                "evdev_giro_dps_mediano",
                "evdev_resolution",
                "acel_modulo_g_mediano",
                "regua_lsb_por_dps",
                "speed_2x",
                "sens_denom",
                "pares",
                "saltos_do_contador",
                "reports_perdidos",
                "seq_parado_pares",
                "silencio_p95_ms",
                "silencio_max_ms",
                "cauda_muda_ms",
                "fracao_da_janela_medida",
                "maior_parada_do_laco_ms",
                "erro",
            ]
        )
        for medida in medidas:
            eixos = medida.eixos_giro_dps
            escritor.writerow(
                [
                    quando,
                    mascarar(medida.aparelho.mac),
                    medida.aparelho.transporte,
                    medida.aparelho.hidraw,
                    medida.porta or "-",
                    medida.energia,
                    medida.bateria,
                    f"{medida.segundos:.3f}",
                    medida.aproveitados,
                    f"{medida.taxa_hz:.1f}",
                    f"{medida.cadencia_do_controle_hz:.1f}",
                    f"{medida.giro_mediano_dps:.4f}",
                    f"{medida.giro_maximo_dps:.4f}",
                    f"{eixos[0]:.4f}",
                    f"{eixos[1]:.4f}",
                    f"{eixos[2]:.4f}",
                    f"{medida.giro_ingenuo_mediano:.5f}",
                    f"{medida.negativo_mediano_dps:.1f}",
                    medida.evdev_no or "-",
                    medida.evdev_amostras,
                    f"{medida.evdev_giro_mediano_dps:.4f}",
                    medida.evdev_resolucao_giro if medida.evdev_resolucao_giro else "-",
                    f"{medida.modulo_g_mediano:.4f}",
                    f"{medida.calib.lsb_por_dps:.2f}",
                    medida.calib.speed_2x,
                    " ".join(str(d) for d in medida.calib.denom),
                    medida.pares,
                    len(medida.saltos_do_contador),
                    medida.reports_perdidos,
                    medida.seq_parado,
                    f"{medida.silencio_p95_ms:.3f}",
                    f"{medida.silencio_maximo_ms:.3f}",
                    f"{medida.cauda_muda_ms:.3f}",
                    f"{medida.fracao_da_janela_medida:.3f}",
                    f"{laco_ms:.3f}",
                    medida.erro,
                ]
            )


def veredicto(medidas: list[Medida], laco_ms: float) -> str:
    """A linha final — e ela reprova o INSTRUMENTO antes de julgar o aparelho."""
    com_amostra = [m for m in medidas if m.aproveitados]
    if not com_amostra:
        return (
            "NENHUM controle produziu amostra. Não há veredicto sobre aparelho "
            "nenhum: o que está medido é a porta, não a IMU."
        )

    sem_calib = [m for m in com_amostra if not m.calib.ok]
    if sem_calib:
        quais = "; ".join(f"{m.apelido_mascarado}: {m.calib.motivo}" for m in sem_calib)
        return (
            "SEM RÉGUA em pelo menos uma unidade — o feature 0x05 não veio, e sem "
            f"ele o giroscópio só teria a régua ingênua, que erra 62x. Nada vira "
            f"célula `medido`. ({quais})"
        )

    fora_de_1g = [
        m for m in com_amostra if not FAIXA_DE_1G[0] <= m.modulo_g_mediano <= FAIXA_DE_1G[1]
    ]
    if fora_de_1g:
        quais = "; ".join(f"{m.apelido_mascarado}: {m.modulo_g_mediano:.4f} g" for m in fora_de_1g)
        return (
            "CONTROLE POSITIVO 1 REPROVADO: o acelerômetro do MESMO report não deu "
            f"1 g ({quais}). Os offsets ou o transporte estão errados — o braço do "
            "giroscópio não vale, e este ensaio para aqui."
        )

    fracos = [
        m
        for m in com_amostra
        if m.giros_no_offset_errado and m.negativo_mediano_dps < 10 * TETO_DE_PARADO_DPS
    ]
    if fracos:
        return (
            "CONTROLE NEGATIVO REPROVADO: o giroscópio lido no offset do "
            "ACELERÔMETRO deveria dar centenas de graus/s e não deu. Uma régua que "
            "não consegue produzir número grande faz 'perto de zero' não valer nada."
        )

    conferiveis = [m for m in com_amostra if m.evdev_amostras]
    divergentes = [
        m
        for m in conferiveis
        if abs(m.giro_mediano_dps - m.evdev_giro_mediano_dps) > 0.5
    ]
    if divergentes:
        quais = "; ".join(
            f"{m.apelido_mascarado}: eu {m.giro_mediano_dps:.3f} contra kernel "
            f"{m.evdev_giro_mediano_dps:.3f} graus/s"
            for m in divergentes
        )
        return (
            "CONTROLE POSITIVO 2 REPROVADO: a minha conta e a do KERNEL divergem "
            f"({quais}). Duas implementações da mesma régua têm de bater; enquanto "
            "não baterem, quem está errado sou eu."
        )

    girando = [m for m in com_amostra if m.giro_mediano_dps > TETO_DE_PARADO_DPS]
    perdedores = [m for m in com_amostra if m.reports_perdidos]

    partes = []
    for transporte in (CABO, RADIO):
        deste = [m for m in com_amostra if m.aparelho.transporte == transporte]
        if not deste:
            continue
        giro = "; ".join(f"{m.giro_mediano_dps:.2f}" for m in deste)
        perda = "; ".join(f"{m.reports_perdidos}/{m.pares}" for m in deste)
        partes.append(f"{transporte}: giro parado {giro} graus/s, perdidos {perda}")

    cabeca = (
        "GIRA (acima do teto de parado) em "
        + "; ".join(f"{m.apelido_mascarado} {m.giro_mediano_dps:.2f} graus/s" for m in girando)
        if girando
        else f"os {len(com_amostra)} que falaram estão PARADOS pela régua absoluta"
    )
    cauda = (
        "SEM report perdido em nenhum deles"
        if not perdedores
        else "com perda em "
        + "; ".join(
            f"{m.apelido_mascarado} ({m.reports_perdidos} reports)" for m in perdedores
        )
    )

    # Um aparelho que não falou NÃO pode desaparecer da linha final. "Todos
    # parados" com um mudo na mesa é a frase que faz a próxima pessoa achar que
    # mediu quatro quando mediu três — e o mudo é justamente o caso interessante.
    mudos = [m for m in medidas if not m.aproveitados and not m.erro]
    aviso_mudo = ""
    if mudos:
        quais = "; ".join(
            f"{m.apelido_mascarado} ({m.aparelho.transporte}, {m.energia})" for m in mudos
        )
        aviso_mudo = (
            f" ATENÇÃO: {len(mudos)} aparelho(s) NÃO EMITIRAM NADA na janela ({quais}). "
            "O nó abriu e o contador não andou nem uma vez: não é perda, é AUSÊNCIA de "
            "emissão. Nenhuma frase acima vale para eles."
        )

    return (
        f"{cabeca}; {cauda}. "
        + " | ".join(partes)
        + f". Maior parada do MEU laço: {laco_ms:.2f} ms — "
        "comparar com o silêncio máximo de cada aparelho antes de culpar o enlace."
        + aviso_mudo
    )


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="E-8: o giroscópio em repouso e o buraco na fila de reports, cabo e rádio.",
    )
    analisador.add_argument("--segundos", type=float, default=20.0, help="janela (padrão 20 s)")
    analisador.add_argument("--csv", default="", help="onde escrever a tabela")
    analisador.add_argument(
        "--sem-mascara",
        action="store_true",
        help="mostra o MAC inteiro na TELA (o CSV continua mascarado, sempre)",
    )
    argumentos = analisador.parse_args()

    aparelhos = descobrir_aparelhos()
    alvos = fisicos(aparelhos)
    nos_evdev = [c for c in (_no_de_movimento(a) for a in alvos) if c]

    print(
        cabecalho_do_instrumento(
            "giro_e_buraco.py",
            "o giroscópio dá zero parado, e some report na janela? (E-8 da mesa 2+2)",
            bibliotecas=["os", "struct", "fcntl", "selectors"],
            escreve_no_aparelho=False,
            daemon_precisa_parar=False,
            nos_evdev=nos_evdev,
        )
    )

    quando_inicio = datetime.now().isoformat(timespec="milliseconds")
    print(f"  T0 (hora de parede) ... {quando_inicio}")
    print(f"\n  {censo_da_mesa(aparelhos)}")
    if not alvos:
        print(resumo("nenhum DualSense físico na mesa — nada a medir."))
        return 1

    medidas = [Medida(aparelho=a) for a in alvos]

    print("\n  OS CAMPOS QUE VOU LER, POR TRANSPORTE (offsets do fonte do driver)")
    print()
    print(
        tabela(
            [
                "transporte",
                "report id",
                "corpo em",
                "giro",
                "acel",
                "seq",
                "contador le32",
                "carimbo",
            ],
            [
                [
                    transporte,
                    f"0x{perfil['report_id']:02x}",
                    f"data[{perfil['corpo']}]",
                    str(perfil["corpo"] + OFFSET_GIRO_NO_CORPO),
                    str(perfil["corpo"] + OFFSET_ACEL_NO_CORPO),
                    str(perfil["corpo"] + OFFSET_SEQ_NO_CORPO),
                    str(perfil["corpo"] + OFFSET_CONTADOR_NO_CORPO),
                    str(perfil["corpo"] + OFFSET_TS_NO_CORPO),
                ]
                for transporte, perfil in PERFIL_DO_TRANSPORTE.items()
            ],
        )
    )

    print(
        f"\n  medindo {len(medidas)} controle(s) por {argumentos.segundos:.0f} s, "
        "na MESMA janela."
    )
    print("  >> NÃO mexa nos controles: parado é a condição do ensaio, e a régua")
    print("  >> do giroscópio é o ZERO — absoluta, sem comparar um braço com o outro.")
    print()
    laco_ms = medir(medidas, argumentos.segundos)

    print("  A RÉGUA DO GIROSCÓPIO, LIDA DE CADA APARELHO (feature 0x05, GET_REPORT)")
    print("  Lida AGORA, DEPOIS da janela, e nunca antes: um GET_REPORT por rádio é")
    print("  tráfego no enlace, e este instrumento mede silêncio de enlace. Cutucar o")
    print("  aparelho e depois perguntar se ele está quieto seria medir a mim mesmo.")
    print("  A resolução 1024 do driver é a de SAÍDA, depois da calibração — o número")
    print("  CRU do fio está noutra escala, e é esta tabela que diz qual.")
    print()
    for medida in medidas:
        medida.calib = ler_calibracao(medida.aparelho)
        medida.energia, medida.bateria = alimentacao(medida.aparelho)
        medida.finalizar()
    print(
        tabela(
            [
                "aparelho",
                "transporte",
                "speed_2x",
                "sens_denom (x y z)",
                "LSB por grau/s",
                "de onde",
            ],
            [
                [
                    _nome(m, sem_mascara=argumentos.sem_mascara),
                    m.aparelho.transporte,
                    str(m.calib.speed_2x),
                    " ".join(str(d) for d in m.calib.denom),
                    f"{m.calib.lsb_por_dps:.2f}" if m.calib.ok else "-",
                    m.calib.motivo,
                ]
                for m in medidas
            ],
        )
    )
    print(
        f"\n  >> a régua INGÊNUA (cru / {DS_GYRO_RES_PER_DEG_S}) encolheria a leitura por "
        f"~{DS_GYRO_RES_PER_DEG_S / (medidas[0].calib.lsb_por_dps or 1):.0f}x."
    )


    print("  O GIROSCÓPIO EM REPOUSO — três réguas na mesma janela")
    print()
    print(
        tabela(
            [
                "aparelho",
                "transporte",
                "reports",
                "|w| mediano",
                "|w| máximo",
                "eixos (graus/s)",
                "kernel (evdev)",
                "régua ingênua",
                "NEGATIVO",
            ],
            [
                [
                    _nome(m, sem_mascara=argumentos.sem_mascara),
                    m.aparelho.transporte,
                    str(m.aproveitados) if m.aproveitados else (m.erro or "SEM AMOSTRA"),
                    f"{m.giro_mediano_dps:.3f}",
                    f"{m.giro_maximo_dps:.3f}",
                    ", ".join(f"{v:+.3f}" for v in m.eixos_giro_dps),
                    f"{m.evdev_giro_mediano_dps:.3f} ({m.evdev_amostras})"
                    if m.evdev_amostras
                    else (m.evdev_motivo or "-"),
                    f"{m.giro_ingenuo_mediano:.4f}",
                    f"{m.negativo_mediano_dps:.0f}",
                    ]
                for m in medidas
            ],
        )
    )
    print("  |w| e eixos em graus/s pela régua do próprio aparelho. `régua ingênua` é o")
    print("  MESMO dado dividido por 1024 — está aí para mostrar o tamanho do erro.")
    print("  `NEGATIVO` é o acelerômetro lido COMO SE fosse giroscópio: tem de ser enorme.")

    print("\n  CONTROLE POSITIVO 1 — o acelerômetro do MESMO report tem de dar 1 g")
    print()
    print(
        tabela(
            ["aparelho", "transporte", "|v| mediano", "veredito"],
            [
                [
                    _nome(m, sem_mascara=argumentos.sem_mascara),
                    m.aparelho.transporte,
                    f"{m.modulo_g_mediano:.4f} g" if m.aproveitados else "-",
                    "CONFERE"
                    if m.aproveitados and FAIXA_DE_1G[0] <= m.modulo_g_mediano <= FAIXA_DE_1G[1]
                    else "NÃO CONFERE",
                ]
                for m in medidas
            ],
        )
    )

    print("\n  A PERDA — o contador de reports que o driver chama de `reserved`")
    print()
    print(
        tabela(
            [
                "aparelho",
                "transporte",
                "energia",
                "pares",
                "saltos",
                "reports perdidos",
                "seq_number parado",
                "taxa host",
                "cadência do controle",
            ],
            [
                [
                    _nome(m, sem_mascara=argumentos.sem_mascara),
                    m.aparelho.transporte,
                    f"{m.energia} {m.bateria}%",
                    str(m.pares),
                    str(len(m.saltos_do_contador)),
                    str(m.reports_perdidos),
                    f"{m.seq_parado}/{m.pares}" if m.pares else "-",
                    f"{m.taxa_hz:.1f} Hz",
                    f"{m.cadencia_do_controle_hz:.1f} Hz",
                ]
                for m in medidas
            ],
        )
    )
    print("  `seq_number parado` é o CONTRA-exemplo: no rádio o corpo[6] não anda, e")
    print("  quem contasse perda por ele veria zero para sempre — inclusive perdendo.")

    print("\n  O SILÊNCIO — e a parada do MEU laço, que é o negativo do instrumento")
    print()
    print(
        tabela(
            [
                "aparelho",
                "transporte",
                "silêncio p95",
                "silêncio máximo",
                "cauda muda",
                "janela coberta",
                "host nos saltos",
            ],
            [
                [
                    _nome(m, sem_mascara=argumentos.sem_mascara),
                    m.aparelho.transporte,
                    f"{m.silencio_p95_ms:.2f} ms",
                    f"{m.silencio_maximo_ms:.2f} ms",
                    f"{m.cauda_muda_ms:.2f} ms",
                    f"{100 * m.fracao_da_janela_medida:.0f}%",
                    ", ".join(f"{v:.1f}" for v in m.host_ms_nos_saltos[:6]) or "não houve salto",
                ]
                for m in medidas
            ],
        )
    )
    print(f"  maior parada do MEU laço na janela inteira: {laco_ms:.2f} ms")
    print("  `cauda muda` é do ÚLTIMO report ao fim da janela, e `janela coberta` é")
    print("  quanto da janela tem intervalo medido: bem abaixo de 100% quer dizer que")
    print("  o p95 acima é do pedaço em que o aparelho falou, não da janela toda.")

    descartes = [m for m in medidas if m.lidos != m.aproveitados and not m.erro]
    if descartes:
        print("\n  REPORTS DESCARTADOS (contados, nunca escondidos):")
        for medida in descartes:
            vistos = ", ".join(f"0x{i:02x}x{n}" for i, n in sorted(medida.ids_vistos.items()))
            print(
                f"    - {mascarar(medida.aparelho.mac)}: {medida.lidos} lidos, "
                f"{medida.aproveitados} aproveitados, {medida.curtos} curtos. ids: {vistos}"
            )

    print(f"\n  T1 (hora de parede) ... {datetime.now().isoformat(timespec='milliseconds')}")
    if argumentos.csv:
        _escrever_csv(argumentos.csv, medidas, quando_inicio, laco_ms)
        print(f"  CSV ................... {argumentos.csv}")

    print(resumo(veredicto(medidas, laco_ms)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
