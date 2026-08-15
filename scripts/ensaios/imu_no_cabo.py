#!/usr/bin/env python3
"""imu_no_cabo.py — o acelerômetro entrega número calibrado no CABO? (E-4)

A PERGUNTA QUE ELE RESPONDE
----------------------------
*O acelerômetro do controle NO CABO entrega número calibrado?* A célula
`movimento.acelerometro@dualsense`, coluna `cabo_de_onde_sei`, está em
`inferido-do-codigo` desde que o mapa nasceu, e o motivo estava escrito:
**nunca houve controle no cabo para medir**. A mesa 2+2 de 15/08/2026 pôs dois,
e o braço do rádio já foi medido em 14/08 (0,9945 g e 0,9823 g) — então dá para
fechar o par no MESMO minuto, que é o pedido dela: *"giroscópio, acelerômetro
também. todos via cabo e bt"*.

A RÉGUA É ABSOLUTA, E É POR ISSO QUE NINGUÉM PRECISA MEXER NO CONTROLE
----------------------------------------------------------------------
Um acelerômetro parado na mesa mede **a gravidade**, e o módulo do vetor de
gravidade é **1 g em qualquer orientação**. Não é preciso girar, sacudir nem
cronometrar nada: o controle deitado já é a condição de ensaio.

Isso não é conveniência — é a **Lei 2** do plano da mesa 2+2. Pedir movimento a
mão humana é a armadilha `A-8`/`A-9`/`A-21` desta casa, que já custou duas
rodadas em 11/08. O desenho que precisasse dela estaria errado.

E é também a escapatória da **Lei 4** (o confundimento braço/unidade): 1 g é
referência absoluta. Nenhuma conclusão deste instrumento depende de comparar um
braço com o outro — cada controle é julgado contra a gravidade, sozinho.

A PORTA, DECLARADA
-------------------
**Broker**, nos quatro físicos, por `comum.abrir_no_hidraw`. Com o co-op ligado
os quatro DualSense estão `0600 root:root` — o próprio Hefesto os esconde do
jogo —, e um `open()` direto ali mede `EACCES`, não o aparelho.

**Não é evdev de propósito.** O co-op faz `EVIOCGRAB` nos evdev físicos, que é
exclusivo: um leitor ingênuo lê zero evento e conclui que o aparelho está
calado. O hidraw não tem esse problema — cada fd tem fila de entrada própria, e
este instrumento não escreve um byte.

A RÉGUA, DECLARADA (a fuga da `A-3`)
-------------------------------------
`DS_ACC_RES_PER_G = 8192` LSB/g (faixa +-4 g), do `hid-playstation.c`, o mesmo
número que a canônica §5 registra. Para que a régua não seja um número copiado
de documentação, o instrumento **confere o valor contra o kernel desta máquina**
por `EVIOCGABS` no nó *Motion Sensors* de cada controle (ioctl puro, sem
`python-evdev`) e imprime os dois lado a lado. Essa conferência **não entra na
conta**: ela existe para que uma divergência apareça na tela em vez de virar
resultado.

OS OFFSETS, IMPRESSOS — porque cabo e rádio NÃO são o mesmo deslocamento
------------------------------------------------------------------------
O corpo do report é o mesmo `struct dualsense_input_report` nos dois
transportes, mas ele é ancorado em endereços diferentes
(`hid-playstation.c:1580-1595`):

  cabo  (report `0x01`, 64 B) .... corpo em `data[1]`  -> accel em 22..27
  rádio (report `0x31`, 78 B) .... corpo em `data[2]`  -> accel em 23..28

Usar o offset de um no outro produz número absurdo com cara de medida. Por isso
os offsets usados vão na tabela, por transporte, e não num comentário.

O CONTROLE NEGATIVO, OBRIGATÓRIO
---------------------------------
Os dois do **rádio** são medidos na MESMA janela e têm de reproduzir os
0,98-0,99 g de 14/08. Se não reproduzirem, quem mudou foi o instrumento, e nada
do braço do cabo vale — o ensaio para ali, e o réu é a régua, não o aparelho.

O QUE ELE NUNCA FAZ
--------------------
**Não escreve no aparelho.** Nem um byte, em transporte nenhum. Ele abre o nó,
lê, conta e fecha.

PRECISA DO DAEMON PARADO? **Não** — e não pode pedir isso: parar o daemon
derruba os quatro vpads e o co-op, que é a mesa inteira.

USO
    imu_no_cabo.py                       # 10 s, os quatro físicos
    imu_no_cabo.py --segundos 20 --csv /tmp/imu-2-2.csv
    imu_no_cabo.py --sem-mascara         # MAC inteiro na tela (NUNCA em arquivo)
"""

from __future__ import annotations

import argparse
import csv
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
    fisicos,
    ler_texto,
    resumo,
    tabela,
)

#: `DS_ACC_RES_PER_G`, de `hid-playstation.c` (faixa +-4 g). É a régua, e ela é
#: DECLARADA, não escolhida: a conta inteira deste instrumento é dividir por
#: este número. A conferência contra o `EVIOCGABS` do kernel desta máquina está
#: em `_resolucao_do_kernel`.
DS_ACC_RES_PER_G = 8192

#: `DS_GYRO_RES_PER_DEG_S`. O giroscópio entra como acompanhante: parado na
#: mesa ele tem de dar perto de ZERO graus/s, que é o negativo natural do
#: acelerômetro (um controle imóvel não gira, mas continua sob gravidade).
DS_GYRO_RES_PER_DEG_S = 1024

#: Report ID de entrada e o deslocamento do corpo, POR TRANSPORTE.
#: `hid-playstation.c:140-154` e `:1580-1595`. O `corpo` é onde começa o
#: `struct dualsense_input_report` dentro do buffer lido do hidraw (que já vem
#: com o byte do report id em `data[0]`).
PERFIL_DO_TRANSPORTE = {
    CABO: {"report_id": 0x01, "corpo": 1, "tamanho": 64},
    RADIO: {"report_id": 0x31, "corpo": 2, "tamanho": 78},
}

#: Offsets DENTRO do corpo (`struct dualsense_input_report`), do fonte do
#: driver: `gyro[3]` em 15-20 e `accel[3]` em 21-26, ambos `__le16` com sinal.
OFFSET_GIRO_NO_CORPO = 15
OFFSET_ACEL_NO_CORPO = 21

#: `EVIOCGABS(ABS_X)` = `_IOR('E', 0x40 + ABS_X, struct input_absinfo)`.
#: `struct input_absinfo` são seis `__s32`: value, minimum, maximum, fuzz,
#: flat, resolution. É a única conferência independente da régua que não custa
#: uma biblioteca a mais.
_TAMANHO_ABSINFO = 24
_EVIOCGABS_ABS_X = (2 << 30) | (_TAMANHO_ABSINFO << 16) | (0x45 << 8) | 0x40

#: Quanto se lê de uma vez. O maior report de entrada tem 78 B (rádio); 256 é
#: folga barata e garante que nenhum report chegue truncado.
_BYTES_POR_LEITURA = 256


def mascarar(mac: str) -> str:
    """`aa:bb:cc:dd:ee:ff` -> `aa:bb:cc:00:00:ff` — a máscara da casa.

    Octetos 4 e 5 zerados: preserva o fabricante (que é informação técnica útil)
    e apaga o aparelho dela. Há portão que reprova MAC real em arquivo
    versionado, e a saída bruta deste ensaio É versionada.

    O exemplo acima é forjado de propósito. Ele já foi escrito com o endereço
    REAL de um dos controles da bancada — a docstring da função que mascara era,
    ela mesma, o vazamento, e passou verde porque o portão não conhecia aquele
    OUI (15/08/2026; ver a nota datada em `tests/unit/test_docs_mac_anonimato.py`).
    """
    partes = mac.split(":")
    if len(partes) != 6:
        return mac
    return ":".join([*partes[:3], "00", "00", partes[5]])


@dataclass
class Medida:
    """O que se acumulou de um controle numa janela — e nada além disso."""

    aparelho: Aparelho
    porta: str = ""
    motivo_da_porta: str = ""
    erro: str = ""
    lidos: int = 0
    aproveitados: int = 0
    ids_vistos: dict[int, int] = field(default_factory=dict)
    curtos: int = 0
    modulos: list[float] = field(default_factory=list)
    somas_acel: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    somas_giro: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    segundos: float = 0.0
    resolucao_do_kernel: int | None = None
    motivo_da_resolucao: str = ""

    @property
    def modulo_mediano(self) -> float:
        if not self.modulos:
            return 0.0
        ordenados = sorted(self.modulos)
        meio = len(ordenados) // 2
        if len(ordenados) % 2:
            return ordenados[meio]
        return (ordenados[meio - 1] + ordenados[meio]) / 2

    @property
    def desvio(self) -> float:
        """Desvio-padrão do módulo. Um controle parado tem de ter desvio ~0.

        Serve de detector de mentira do próprio instrumento: se os offsets
        estiverem errados, o "módulo" vira ruído e o desvio explode junto com
        a média — os dois sintomas aparecem na mesma linha da tabela.
        """
        if len(self.modulos) < 2:
            return 0.0
        media = sum(self.modulos) / len(self.modulos)
        variancia = sum((x - media) ** 2 for x in self.modulos) / (len(self.modulos) - 1)
        return math.sqrt(variancia)

    @property
    def eixos_em_g(self) -> list[float]:
        if not self.aproveitados:
            return [0.0, 0.0, 0.0]
        return [s / self.aproveitados / DS_ACC_RES_PER_G for s in self.somas_acel]

    @property
    def giro_em_graus_por_s(self) -> list[float]:
        if not self.aproveitados:
            return [0.0, 0.0, 0.0]
        return [s / self.aproveitados / DS_GYRO_RES_PER_DEG_S for s in self.somas_giro]

    @property
    def taxa(self) -> float:
        return self.aproveitados / self.segundos if self.segundos > 0 else 0.0

    @property
    def apelido_mascarado(self) -> str:
        """Como este controle aparece na tabela — com o MAC já mascarado.

        A máscara é aplicada AQUI, na fonte, e não no ponto de impressão: a
        saída bruta deste ensaio é versionada, e a regra da casa é que MAC real
        não entra em arquivo do repositório. Quem quiser o MAC inteiro na tela
        pede `--sem-mascara`, e ainda assim o CSV sai mascarado.
        """
        return mascarar(self.aparelho.mac) or self.aparelho.hidraw


def _no_de_movimento(aparelho: Aparelho) -> str:
    """O `/dev/input/eventN` do nó *Motion Sensors* deste controle, ou "".

    Resolvido a cada chamada pelo sysfs do próprio aparelho: os números de nó
    NÃO são estáveis, e em 15/08/2026 um controle reapareceu com outro `eventN`
    entre duas leituras com segundos de diferença.
    """
    raiz = os.path.join(aparelho.dir_device, "input")
    if not os.path.isdir(raiz):
        return ""
    for entrada in sorted(os.listdir(raiz)):
        if not entrada.startswith("input"):
            continue
        dir_input = os.path.join(raiz, entrada)
        nome = ler_texto(os.path.join(dir_input, "name")).strip()
        if "Motion Sensors" not in nome:
            continue
        for sub in sorted(os.listdir(dir_input)):
            if sub.startswith("event"):
                return f"/dev/input/{sub}"
    return ""


def _resolucao_do_kernel(aparelho: Aparelho) -> tuple[int | None, str]:
    """A `resolution` que o kernel publica para `ABS_X` — a régua, conferida.

    Isto NÃO participa da conta. Existe porque "8192" copiado de documentação é
    exatamente a `A-3` que esta casa paga desde sempre: medir contra a régua
    errada produz alarme convincente e falso. Se o kernel desta máquina disser
    outro número, ele aparece ao lado do nosso, e quem lê decide.

    `EVIOCGABS` é ioctl de LEITURA de propriedade: não pega o nó, não compete
    com o `EVIOCGRAB` do co-op e não lê evento nenhum.
    """
    caminho = _no_de_movimento(aparelho)
    if not caminho:
        return None, "não achei o nó Motion Sensors deste controle"
    import fcntl  # local: só esta função precisa, e ela é opcional por desenho

    try:
        fd = os.open(caminho, os.O_RDONLY | os.O_CLOEXEC)
    except OSError as erro:
        return None, f"{caminho}: {erro.strerror or erro}"
    try:
        bruto = fcntl.ioctl(fd, _EVIOCGABS_ABS_X, bytes(_TAMANHO_ABSINFO))
    except OSError as erro:
        return None, f"{caminho}: EVIOCGABS falhou ({erro.strerror or erro})"
    finally:
        os.close(fd)
    campos = struct.unpack("6i", bruto)
    return campos[5], f"{caminho} publica resolution={campos[5]} para ABS_X"


def _consumir(medida: Medida, bruto: bytes) -> None:
    """Um report cru -> as três acelerações e os três giros, ou nada.

    O report é DESCARTADO em silêncio (contado, não usado) quando o id não é o
    do transporte ou quando ele veio curto. Descartar sem contar seria a mesma
    coisa que mentir devagar: o rodapé imprime `ids_vistos` e `curtos`.
    """
    medida.lidos += 1
    if not bruto:
        return
    identificador = bruto[0]
    medida.ids_vistos[identificador] = medida.ids_vistos.get(identificador, 0) + 1
    perfil = PERFIL_DO_TRANSPORTE.get(medida.aparelho.transporte)
    if perfil is None or identificador != perfil["report_id"]:
        return
    corpo = perfil["corpo"]
    fim = corpo + OFFSET_ACEL_NO_CORPO + 6
    if len(bruto) < fim:
        medida.curtos += 1
        return

    inicio_giro = corpo + OFFSET_GIRO_NO_CORPO
    gx, gy, gz = struct.unpack_from("<3h", bruto, inicio_giro)
    inicio_acel = corpo + OFFSET_ACEL_NO_CORPO
    ax, ay, az = struct.unpack_from("<3h", bruto, inicio_acel)

    medida.aproveitados += 1
    for indice, valor in enumerate((ax, ay, az)):
        medida.somas_acel[indice] += valor
    for indice, valor in enumerate((gx, gy, gz)):
        medida.somas_giro[indice] += valor
    medida.modulos.append(math.sqrt(ax * ax + ay * ay + az * az) / DS_ACC_RES_PER_G)


def medir(medidas: list[Medida], segundos: float) -> None:
    """Lê os quatro físicos na MESMA janela, por `select`, e conta.

    A mesma janela importa: o pedido dela é o par cabo/rádio fechado *no mesmo
    minuto*, e duas janelas em fila não são coexistência — são dois ensaios
    diferentes com o mesmo nome.
    """
    seletor = selectors.DefaultSelector()
    abertos: dict[int, Medida] = {}
    fechar: list[NoAberto] = []

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
        medida.motivo_da_porta = no.motivo
        os.set_blocking(no.fd, False)
        seletor.register(no.fd, selectors.EVENT_READ)
        abertos[no.fd] = medida
        fechar.append(no)

    if not abertos:
        seletor.close()
        return

    inicio = time.monotonic()
    fim = inicio + segundos
    while True:
        restante = fim - time.monotonic()
        if restante <= 0:
            break
        for chave, _ in seletor.select(min(restante, 0.25)):
            medida = abertos[chave.fd]
            try:
                _consumir(medida, os.read(chave.fd, _BYTES_POR_LEITURA))
            except BlockingIOError:
                continue
            except OSError as erro:
                medida.erro = f"leitura interrompida: {erro.strerror or erro}"
                seletor.unregister(chave.fd)

    decorrido = time.monotonic() - inicio
    for medida in abertos.values():
        medida.segundos = decorrido

    seletor.close()
    for no in fechar:
        no.fechar()


def _linha_da_tabela(medida: Medida) -> list[str]:
    perfil = PERFIL_DO_TRANSPORTE.get(medida.aparelho.transporte, {})
    if medida.erro:
        return [
            medida.apelido_mascarado,
            medida.aparelho.transporte,
            "-",
            "-",
            "NÃO ABRIU",
            "-",
            "-",
        ]
    if not medida.aproveitados:
        vistos = ", ".join(f"0x{i:02x}x{n}" for i, n in sorted(medida.ids_vistos.items()))
        return [
            medida.apelido_mascarado,
            medida.aparelho.transporte,
            f"0x{perfil.get('report_id', 0):02x}",
            f"{medida.lidos} lidos",
            "SEM AMOSTRA",
            vistos or "nada chegou",
            "-",
        ]
    eixos = ", ".join(f"{v:+.3f}" for v in medida.eixos_em_g)
    return [
        medida.apelido_mascarado,
        medida.aparelho.transporte,
        f"0x{perfil.get('report_id', 0):02x}",
        str(medida.aproveitados),
        f"{medida.modulo_mediano:.4f} g",
        f"+-{medida.desvio:.4f}",
        eixos,
    ]


def _nome(medida: Medida, *, sem_mascara: bool) -> str:
    """O rótulo do controle na TELA. O CSV nunca passa por aqui — ele mascara sempre."""
    if sem_mascara:
        return medida.aparelho.mac or medida.aparelho.hidraw
    return medida.apelido_mascarado


def _escrever_csv(caminho: str, medidas: list[Medida], quando: str) -> None:
    """Ensaio que não vira linha de tabela vira lembrança. MAC mascarado."""
    # `lineterminator="\n"` porque o padrão do módulo `csv` é CRLF, e o
    # `.gitattributes` desta casa é `eol=lf` em tudo: sem isto o arquivo entra
    # com fim de linha que o git reescreve na primeira vez que tocar nele.
    with open(caminho, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.writer(arquivo, lineterminator="\n")
        escritor.writerow(
            [
                "quando",
                "mac_mascarado",
                "transporte",
                "hidraw",
                "porta",
                "report_id",
                "offset_accel",
                "offset_gyro",
                "reports_aproveitados",
                "segundos",
                "taxa_hz",
                "modulo_g_mediano",
                "desvio_g",
                "accel_x_g",
                "accel_y_g",
                "accel_z_g",
                "giro_x_dps",
                "giro_y_dps",
                "giro_z_dps",
                "regua_lsb_por_g",
                "regua_do_kernel",
                "erro",
            ]
        )
        for medida in medidas:
            perfil = PERFIL_DO_TRANSPORTE.get(medida.aparelho.transporte, {})
            corpo = perfil.get("corpo", 0)
            eixos = medida.eixos_em_g
            giro = medida.giro_em_graus_por_s
            escritor.writerow(
                [
                    quando,
                    mascarar(medida.aparelho.mac),
                    medida.aparelho.transporte,
                    medida.aparelho.hidraw,
                    medida.porta or "-",
                    f"0x{perfil.get('report_id', 0):02x}",
                    corpo + OFFSET_ACEL_NO_CORPO,
                    corpo + OFFSET_GIRO_NO_CORPO,
                    medida.aproveitados,
                    f"{medida.segundos:.3f}",
                    f"{medida.taxa:.1f}",
                    f"{medida.modulo_mediano:.4f}",
                    f"{medida.desvio:.4f}",
                    f"{eixos[0]:.4f}",
                    f"{eixos[1]:.4f}",
                    f"{eixos[2]:.4f}",
                    f"{giro[0]:.3f}",
                    f"{giro[1]:.3f}",
                    f"{giro[2]:.3f}",
                    DS_ACC_RES_PER_G,
                    medida.resolucao_do_kernel if medida.resolucao_do_kernel else "-",
                    medida.erro,
                ]
            )


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="E-4: o módulo do vetor de gravidade em cada DualSense, cabo e rádio.",
    )
    analisador.add_argument("--segundos", type=float, default=10.0, help="janela (padrão 10 s)")
    analisador.add_argument("--csv", default="", help="onde escrever a tabela")
    analisador.add_argument(
        "--sem-mascara",
        action="store_true",
        help="mostra o MAC inteiro na TELA (o CSV continua mascarado, sempre)",
    )
    argumentos = analisador.parse_args()

    print(
        cabecalho_do_instrumento(
            "imu_no_cabo.py",
            "o acelerômetro entrega número calibrado no CABO? (E-4 do plano da mesa 2+2)",
            bibliotecas=["os", "struct", "selectors"],
            escreve_no_aparelho=False,
            daemon_precisa_parar=False,
        )
    )

    quando_inicio = datetime.now().isoformat(timespec="milliseconds")
    print(f"  T0 (hora de parede) ... {quando_inicio}")
    print(f"  régua declarada ....... DS_ACC_RES_PER_G = {DS_ACC_RES_PER_G} LSB/g")
    print("                          de hid-playstation.c (faixa +-4 g), canônica §5")
    print(f"  régua do giroscópio ... DS_GYRO_RES_PER_DEG_S = {DS_GYRO_RES_PER_DEG_S}")

    aparelhos = descobrir_aparelhos()
    alvos = fisicos(aparelhos)
    print(f"\n  {censo_da_mesa(aparelhos)}")
    if not alvos:
        print(resumo("nenhum DualSense físico na mesa — nada a medir."))
        return 1

    medidas = [Medida(aparelho=a) for a in alvos]

    print("\n  CONFERÊNCIA DA RÉGUA contra o kernel desta máquina (EVIOCGABS, fora da conta)")
    print()
    linhas_regua = []
    for medida in medidas:
        valor, motivo = _resolucao_do_kernel(medida.aparelho)
        medida.resolucao_do_kernel = valor
        medida.motivo_da_resolucao = motivo
        if valor is None:
            veredito = "não pude conferir"
        elif valor == DS_ACC_RES_PER_G:
            veredito = "CONFERE"
        else:
            veredito = f"DIVERGE (kernel diz {valor})"
        linhas_regua.append(
            [
                _nome(medida, sem_mascara=argumentos.sem_mascara),
                medida.aparelho.transporte,
                str(valor) if valor is not None else "-",
                veredito,
                motivo,
            ]
        )
    print(tabela(["aparelho", "transporte", "resolution", "veredito", "de onde"], linhas_regua))

    print("\n  OS OFFSETS QUE VOU USAR (do fonte do driver, por transporte)")
    print()
    linhas_offset = []
    for transporte, perfil in PERFIL_DO_TRANSPORTE.items():
        acel = perfil["corpo"] + OFFSET_ACEL_NO_CORPO
        giro = perfil["corpo"] + OFFSET_GIRO_NO_CORPO
        linhas_offset.append(
            [
                transporte,
                f"0x{perfil['report_id']:02x}",
                f"{perfil['tamanho']} B",
                f"data[{perfil['corpo']}]",
                f"{acel}..{acel + 5}",
                f"{giro}..{giro + 5}",
            ]
        )
    print(
        tabela(
            ["transporte", "report id", "tamanho", "corpo em", "accel em", "gyro em"],
            linhas_offset,
        )
    )

    print(
        f"\n  medindo {len(medidas)} controle(s) por {argumentos.segundos:.0f} s, "
        "na MESMA janela."
    )
    print("  >> NÃO mexa nos controles: parados na mesa eles medem a gravidade,")
    print("  >> e é o módulo dela (1 g) que é a régua deste ensaio.")
    print()
    medir(medidas, argumentos.segundos)

    print("  A MEDIDA — módulo do vetor de gravidade, por controle")
    print()
    linhas = []
    for medida in medidas:
        linha = _linha_da_tabela(medida)
        linha[0] = _nome(medida, sem_mascara=argumentos.sem_mascara)
        linhas.append(linha)
    print(
        tabela(
            ["aparelho", "transporte", "id", "reports", "|v|", "desvio", "eixos (g)"],
            linhas,
        )
    )

    print()
    print("  PORTA USADA, POR NÓ (medir no nó escondido produz zero convincente e falso)")
    print()
    print(
        tabela(
            ["aparelho", "hidraw", "porta", "motivo"],
            [
                [
                    _nome(m, sem_mascara=argumentos.sem_mascara),
                    m.aparelho.hidraw,
                    m.porta or "NÃO ABRIU",
                    m.motivo_da_porta or m.erro or "-",
                ]
                for m in medidas
            ],
        )
    )

    descartes = [m for m in medidas if m.lidos != m.aproveitados and not m.erro]
    if descartes:
        print()
        print("  REPORTS DESCARTADOS (contados, nunca escondidos):")
        for medida in descartes:
            vistos = ", ".join(f"0x{i:02x}x{n}" for i, n in sorted(medida.ids_vistos.items()))
            print(
                f"    - {mascarar(medida.aparelho.mac)}: {medida.lidos} lidos, "
                f"{medida.aproveitados} aproveitados, {medida.curtos} curtos. ids: {vistos}"
            )

    print()
    print("  O GIROSCÓPIO, COMO ACOMPANHANTE (parado tem de dar perto de zero)")
    print()
    print(
        tabela(
            ["aparelho", "transporte", "giro médio (graus/s)", "taxa de report"],
            [
                [
                    _nome(m, sem_mascara=argumentos.sem_mascara),
                    m.aparelho.transporte,
                    ", ".join(f"{v:+.2f}" for v in m.giro_em_graus_por_s)
                    if m.aproveitados
                    else "-",
                    f"{m.taxa:.1f} Hz" if m.aproveitados else "-",
                ]
                for m in medidas
            ],
        )
    )

    quando_fim = datetime.now().isoformat(timespec="milliseconds")
    print(f"\n  T1 (hora de parede) ... {quando_fim}")

    if argumentos.csv:
        _escrever_csv(argumentos.csv, medidas, quando_inicio)
        print(f"  CSV ................... {argumentos.csv}")

    do_cabo = [m for m in medidas if m.aparelho.transporte == CABO and m.aproveitados]
    do_radio = [m for m in medidas if m.aparelho.transporte == RADIO and m.aproveitados]

    if not do_radio:
        veredito = (
            "SEM CONTROLE NEGATIVO: nenhum controle do rádio produziu amostra. "
            "O braço do cabo pode até ter medido, mas sem os 0,98-0,99 g de 14/08 "
            "reproduzidos aqui não há como saber se o instrumento é o mesmo. "
            "Nada disto vira célula `medido`."
        )
    else:
        radio_ok = all(0.90 <= m.modulo_mediano <= 1.10 for m in do_radio)
        if not radio_ok:
            pedacos = "; ".join(f"{m.modulo_mediano:.4f} g" for m in do_radio)
            veredito = (
                f"CONTROLE NEGATIVO REPROVADO: o rádio deu {pedacos}, e em 14/08 deu "
                "0,9945 g e 0,9823 g. Quem mudou foi o INSTRUMENTO — o braço do cabo "
                "não vale, e este ensaio para aqui."
            )
        elif not do_cabo:
            veredito = (
                "o rádio reproduziu 14/08, mas nenhum controle do CABO produziu amostra. "
                "A célula `cabo_de_onde_sei` continua sem medição."
            )
        else:
            cabo_txt = "; ".join(f"{m.modulo_mediano:.4f} g" for m in do_cabo)
            radio_txt = "; ".join(f"{m.modulo_mediano:.4f} g" for m in do_radio)
            erro_max = max(abs(m.modulo_mediano - 1.0) for m in do_cabo) * 100
            veredito = (
                f"cabo: {cabo_txt} (erro máximo {erro_max:.1f}% contra 1 g). "
                f"rádio, como controle negativo: {radio_txt}. "
                "A régua é absoluta e nenhum braço foi comparado com o outro."
            )
    print(resumo(veredito))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
