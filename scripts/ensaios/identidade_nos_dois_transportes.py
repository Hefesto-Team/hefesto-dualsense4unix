#!/usr/bin/env python3
"""identidade_nos_dois_transportes.py — existe crachá que sirva no cabo E no rádio?

A PERGUNTA, E ELA É DELA
------------------------
15/08/2026, textual: *"nos 4 controles via cabo e bt vamos ter sempre
identificado né?"*

Traduzida para uma pergunta que uma máquina responde:

    existe um identificador que
      (a) distingue as 4 unidades,
      (b) é LEGÍVEL nos DOIS transportes, e
      (c) não exige escrita nenhuma?

A cor do plástico (`cor_do_plastico.py`) responde (a) e (c) mal: ela distingue,
mas **exige uma escrita** — `SET_FEATURE 0x80` —, e essa escrita foi RECUSADA
com `EIO` pelo rádio em 15/08. Este instrumento procura o que sobra quando a
escrita sai da mesa.

POR QUE ELE NÃO É O `censo_features.py`
---------------------------------------
O censo responde *"este report é o mesmo byte a byte no cabo e no rádio?"* — e,
com dois aparelhos por braço, essa pergunta é **confundida**: dois MAC
diferentes fazem o `0x09` "diferir por transporte" sem que o transporte tenha
nada a ver com isso. É a Lei 4 do PLANO-DA-MESA-2-2.

A escapatória que este instrumento usa é a mesma do E-4 (o acelerômetro contra
1 g): **régua absoluta, não comparação entre braços.** O `HID_UNIQ` que o
sysfs publica é a régua externa. Se o conteúdo de um report CONTÉM o MAC da
própria unidade que o emitiu, então o valor daquele report não é uma opinião do
braço — é o aparelho dizendo o próprio nome, e a conferência vale unidade por
unidade, em qualquer transporte, sem precisar de rodada anterior para comparar.

O QUE ELE MEDE, E COMO CADA CRITÉRIO É DECIDIDO POR MÁQUINA
------------------------------------------------------------
1. **Legível nos dois transportes.** O descritor daquele transporte declara o
   report, E o `GET_FEATURE` volta com dado. Declarado sem lido é promessa;
   lido é medida.
2. **Distingue as unidades.** Quantos valores distintos o report assume entre
   os aparelhos da mesa. `4 em 4` distingue; `2 em 4` não serve de crachá.
3. **Estável.** O mesmo report lido duas vezes, com `--intervalo` segundos de
   distância, tem de sair IGUAL byte a byte. Um número que muda entre duas
   leituras não identifica ninguém — e essa checagem é barata demais para
   ficar de fora.
4. **Ancorado no MAC.** O conteúdo contém os seis bytes do `HID_UNIQ` daquela
   unidade (em qualquer das duas ordens)? Se contém, o report é um portador do
   MAC, e herda dele a invariância de transporte — que é o único jeito de
   provar (b) sem uma segunda rodada com os braços trocados.
5. **Não exige escrita.** Todos os candidatos daqui são `GET_FEATURE` puro.
   Este arquivo **não sabe escrever**: não há `HIDIOCSFEATURE` nele, e isso é
   estrutural, não promessa.

A MÁSCARA, E POR QUE ELA É MAIS LARGA QUE A DA CASA
----------------------------------------------------
O `0x09` e o `0x0b` carregam MAC em BINÁRIO, e em ordem invertida. A regra da
casa fala do MAC em arquivo versionado, não da palavra "MAC": seis bytes em
hexadecimal são o endereço dela tanto quanto os seis pares separados por
dois-pontos. A máscara daqui varre o buffer procurando os seis bytes de **todo**
MAC conhecido da mesa, nas duas ordens, e zera os octetos 4 e 5 em cada
ocorrência antes de o hexadecimal virar texto. Na TELA sai inteiro (é a máquina
dela); no ARQUIVO, nunca. É o mesmo desenho do `cor_do_plastico.py`.

**O MAC DO HOST ENTRA NA MÁSCARA, E ELE NÃO ESTÁ NO SYSFS.** O `0x09` carrega,
depois do endereço do controle, o endereço do ADAPTADOR pareado — que é a
máquina dela, e é tão identificador quanto. Não há `address` em
`/sys/class/bluetooth/hci0` nesta versão do kernel, então perguntar ao sysfs
devolveria vazio e a máscara passaria por cima calada. Este arquivo o descobre
do PRÓPRIO buffer, no offset conhecido, e o adiciona à lista de agulhas antes de
imprimir qualquer coisa — assim ele não depende de um caminho de sysfs existir.
Escrito depois de o vazamento ter acontecido de verdade, em 15/08/2026: a
primeira versão deste instrumento perguntou a um caminho inexistente, recebeu
vazio, e gravou o endereço do adaptador em hexadecimal num arquivo versionado.
"""

from __future__ import annotations

import argparse
import array
import csv
import errno
import fcntl
import os
import sys
import time
from dataclasses import dataclass, field

_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)

from comum import (  # noqa: E402
    Aparelho,
    PortaFechadaError,
    abrir_no_hidraw,
    cabecalho_do_instrumento,
    censo_da_mesa,
    descobrir_aparelhos,
    diagnostico_de_acesso,
    fisicos,
    ler_texto,
    resumo,
    tabela,
    tamanhos_do_descritor,
)

#: Os candidatos a crachá. Os cinco primeiros são os que o censo de 15/08 às
#: 19h26 apurou como "difere em 4 de 4 unidades"; o `0x81` NÃO está aqui de
#: propósito — sem o `SET_FEATURE 0x80` antes, ele responde um buffer velho, e
#: pedir escrita é justamente o que esta pergunta quer evitar.
CANDIDATOS = (0x05, 0x09, 0x0B, 0x20, 0x22)

#: A âncora de sanidade do censo: se ele sair diferente do que 15/08 registrou,
#: quem mudou foi o instrumento. É o controle negativo do E-8.
ANCORA = 0x20

# HIDIOCGFEATURE: _IOC(WRITE|READ, 'H', 0x07, tamanho). Montado à mão, como em
# `censo_features.py` e `cor_do_plastico.py`. **Não existe o de ESCRITA aqui**,
# e a ausência é a trava: este arquivo não tem como mandar byte a aparelho
# nenhum, nem por engano de quem o editar depois.
_IOC_ESCRITA_E_LEITURA = 3
_IOC_TIPO_HID = ord("H")
_IOC_NR_GETFEATURE = 0x07


def _hidiocgfeature(tamanho: int) -> int:
    return (
        (_IOC_ESCRITA_E_LEITURA << 30)
        | (tamanho << 16)
        | (_IOC_TIPO_HID << 8)
        | _IOC_NR_GETFEATURE
    )


def bytes_do_mac(mac: str) -> bytes:
    """`aa:bb:cc:dd:ee:ff` -> `aa bb cc dd ee ff`. Vazio se não for um MAC.

    O exemplo é forjado, e isso não é estilo: em 15/08/2026 esta docstring foi
    escrita com o endereço REAL de um controle da bancada dos dois lados da
    seta, e o portão de anonimato não a pegou. A função que converte MAC em
    bytes era, ela mesma, o vazamento — o mesmo defeito que
    `cor_do_plastico.py::mascarar` já registra ter cometido no mesmo dia.
    """
    partes = mac.strip().split(":")
    if len(partes) != 6:
        return b""
    try:
        return bytes(int(p, 16) for p in partes)
    except ValueError:
        return b""


def mascarar(mac: str) -> str:
    """`aa:bb:cc:dd:ee:ff` -> `aa:bb:cc:00:00:ff` — a máscara da casa."""
    partes = mac.split(":")
    if len(partes) != 6:
        return mac
    return ":".join([*partes[:3], "00", "00", partes[5]])


def mascarar_no_buffer(dados: bytes, macs: list[bytes]) -> bytes:
    """Zera os octetos 4 e 5 de todo MAC conhecido achado DENTRO do buffer.

    Nas duas ordens, porque o firmware guarda o endereço invertido: procurar só
    a ordem "de leitura" deixaria passar exatamente a forma que o aparelho usa.
    """
    saida = bytearray(dados)
    for cru in macs:
        if len(cru) != 6:
            continue
        for agulha, indices in ((cru, (3, 4)), (bytes(reversed(cru)), (1, 2))):
            inicio = 0
            while True:
                achado = saida.find(agulha, inicio)
                if achado < 0:
                    break
                for deslocamento in indices:
                    saida[achado + deslocamento] = 0
                inicio = achado + 1
    return bytes(saida)


#: Onde o `0x09` guarda o endereço do ADAPTADOR pareado: seis bytes
#: invertidos, logo depois do endereço do controle e da constante `08 25 00`.
#: Conferido nos quatro controles em 15/08/2026, nos dois transportes.
OFFSET_DO_HOST_NO_0X09 = slice(10, 16)


def mac_do_host_no_buffer(dados: bytes, report_id: int) -> bytes:
    """O endereço do adaptador, tirado do PRÓPRIO relatório — não do sysfs.

    Existe porque o sysfs desta máquina não publica `address` para o `hci0`, e
    uma máscara que pergunta a um caminho inexistente recebe vazio e deixa
    passar. Aqui a fonte é o buffer que se vai imprimir, então não há como a
    agulha faltar: se o endereço está no que se imprime, ele está na lista.
    """
    if report_id != 0x09 or len(dados) < OFFSET_DO_HOST_NO_0X09.stop:
        return b""
    return bytes(reversed(dados[OFFSET_DO_HOST_NO_0X09]))


def contem_o_mac(dados: bytes, cru: bytes) -> str:
    """O buffer carrega estes seis bytes? Devolve como, ou "" se não carrega."""
    if len(cru) != 6:
        return ""
    if cru in dados:
        return f"sim, na ordem de leitura, no byte {dados.find(cru)}"
    invertido = bytes(reversed(cru))
    if invertido in dados:
        return f"sim, INVERTIDO, no byte {dados.find(invertido)}"
    return ""


@dataclass
class Leitura:
    """Um `GET_FEATURE` — com a falha como campo, e não como exceção."""

    report_id: int
    dados: bytes = b""
    erro: str = ""
    segundos: float = 0.0

    @property
    def ok(self) -> bool:
        return bool(self.dados) and not self.erro


def pedir_feature(fd: int, report_id: int, tamanho: int, *, tentativas: int = 4) -> Leitura:
    """`GET_FEATURE` com validação de id e retry. Leitura pura, sempre.

    A validação de id não é zelo: em 15/08/2026 esta casa mediu um pedido de
    `0x20` voltar com `0x80` no byte 0. Aceitar resposta trocada aqui seria
    julgar um crachá a partir de outro report.
    """
    leitura = Leitura(report_id)
    inicio = time.monotonic()
    for _ in range(tentativas):
        buffer = array.array("B", [0] * tamanho)
        buffer[0] = report_id
        try:
            escritos = fcntl.ioctl(fd, _hidiocgfeature(tamanho), buffer, True)
        except OSError as erro:
            if erro.errno == errno.EPIPE:
                leitura.erro = "não implementado (EPIPE)"
                break
            if erro.errno in (errno.ENODEV, errno.ENOENT):
                leitura.erro = "o controle DESCONECTOU (ENODEV)"
                break
            leitura.erro = f"ioctl: {erro.strerror or erro}"
            continue
        if escritos <= 0:
            leitura.erro = f"ioctl devolveu {escritos}"
            continue
        recebido = bytes(buffer[:escritos])
        if recebido[0] != report_id:
            leitura.erro = f"veio id 0x{recebido[0]:02x} no lugar de 0x{report_id:02x}"
            continue
        leitura.dados = recebido
        leitura.erro = ""
        break
    leitura.segundos = time.monotonic() - inicio
    return leitura


@dataclass
class Medida:
    """O que se apurou de UM report em UM aparelho."""

    mac: str
    transporte: str
    hardware_version: str
    report_id: int
    declarado: bool
    primeira: Leitura
    segunda: Leitura
    ancora_no_mac: str = ""

    @property
    def estavel(self) -> str:
        if not self.primeira.ok or not self.segunda.ok:
            return "não medida"
        return "IGUAL" if self.primeira.dados == self.segunda.dados else "MUDOU"


def medir_um(aparelho: Aparelho, ids: list[int], intervalo: float) -> list[Medida]:
    """Duas passadas no mesmo aparelho, com `intervalo` segundos entre elas."""
    tamanhos = tamanhos_do_descritor(aparelho.dir_device)["feature"]
    hw = ler_texto(os.path.join(aparelho.dir_device, "hardware_version")).strip()
    cru = bytes_do_mac(aparelho.mac)

    try:
        no = abrir_no_hidraw(aparelho.caminho_hidraw, escrita=False)
    except PortaFechadaError as erro:
        motivo = f"{diagnostico_de_acesso(aparelho.caminho_hidraw)} | {erro}"
        return [
            Medida(
                aparelho.mac, aparelho.transporte, hw, rid,
                rid in tamanhos,
                Leitura(rid, erro=motivo), Leitura(rid, erro=motivo),
            )
            for rid in ids
        ]

    medidas: list[Medida] = []
    try:
        primeiras = {
            rid: (
                pedir_feature(no.fd, rid, tamanhos[rid])
                if rid in tamanhos
                else Leitura(rid, erro="não declarado neste transporte")
            )
            for rid in ids
        }
        time.sleep(intervalo)
        for rid in ids:
            segunda = (
                pedir_feature(no.fd, rid, tamanhos[rid])
                if rid in tamanhos
                else Leitura(rid, erro="não declarado neste transporte")
            )
            medida = Medida(
                aparelho.mac, aparelho.transporte, hw, rid,
                rid in tamanhos, primeiras[rid], segunda,
            )
            if medida.primeira.ok:
                medida.ancora_no_mac = contem_o_mac(medida.primeira.dados, cru)
            medidas.append(medida)
    finally:
        no.fechar()
    return medidas


@dataclass
class Veredito:
    """O julgamento de UM candidato, contra os cinco critérios."""

    report_id: int
    unidades_lidas: int = 0
    valores_distintos: int = 0
    lido_no_cabo: int = 0
    lido_no_radio: int = 0
    declarado_no_cabo: int = 0
    declarado_no_radio: int = 0
    instaveis: int = 0
    ancorados_no_mac: int = 0
    onde_ancora: str = ""
    unidades_totais: int = 0
    unidades_cabo: int = 0
    unidades_radio: int = 0
    discordantes: list[str] = field(default_factory=list)

    @property
    def distingue(self) -> bool:
        return self.unidades_lidas > 0 and self.valores_distintos == self.unidades_lidas

    @property
    def nos_dois(self) -> bool:
        return (
            self.lido_no_cabo == self.unidades_cabo
            and self.lido_no_radio == self.unidades_radio
            and self.unidades_cabo > 0
            and self.unidades_radio > 0
        )

    @property
    def serve(self) -> bool:
        return self.distingue and self.nos_dois and self.instaveis == 0

    @property
    def frase(self) -> str:
        if self.serve and self.ancorados_no_mac == self.unidades_lidas:
            return "SERVE — e é ancorado no MAC"
        if self.serve:
            return "SERVE"
        faltas = []
        if not self.distingue:
            faltas.append(f"só {self.valores_distintos} valores em {self.unidades_lidas}")
        if not self.nos_dois:
            faltas.append("não sai nos dois transportes")
        if self.instaveis:
            faltas.append(f"{self.instaveis} unidade(s) mudaram entre duas leituras")
        return "NÃO SERVE — " + "; ".join(faltas)


def julgar(medidas: list[Medida], ids: list[int], unidades: list[Aparelho]) -> list[Veredito]:
    cabo = sum(1 for a in unidades if a.transporte == "cabo")
    radio = sum(1 for a in unidades if a.transporte == "rádio")
    vereditos = []
    for rid in ids:
        do_report = [m for m in medidas if m.report_id == rid]
        boas = [m for m in do_report if m.primeira.ok]
        veredito = Veredito(
            report_id=rid,
            unidades_lidas=len(boas),
            valores_distintos=len({m.primeira.dados for m in boas}),
            lido_no_cabo=sum(1 for m in boas if m.transporte == "cabo"),
            lido_no_radio=sum(1 for m in boas if m.transporte == "rádio"),
            declarado_no_cabo=sum(
                1 for m in do_report if m.declarado and m.transporte == "cabo"
            ),
            declarado_no_radio=sum(
                1 for m in do_report if m.declarado and m.transporte == "rádio"
            ),
            instaveis=sum(1 for m in boas if m.estavel == "MUDOU"),
            ancorados_no_mac=sum(1 for m in boas if m.ancora_no_mac),
            unidades_totais=len(unidades),
            unidades_cabo=cabo,
            unidades_radio=radio,
        )
        ancoras = {m.ancora_no_mac for m in boas if m.ancora_no_mac}
        veredito.onde_ancora = "; ".join(sorted(ancoras))
        veredito.discordantes = [
            f"{mascarar(m.mac)} (hw {m.hardware_version})"
            for m in do_report
            if not m.primeira.ok
        ]
        vereditos.append(veredito)
    return vereditos


def em_hexadecimal(dados: bytes, *, quantos: int = 24) -> str:
    return " ".join(f"{b:02x}" for b in dados[:quantos]) + ("…" if len(dados) > quantos else "")


def main() -> int:
    analisador = argparse.ArgumentParser(
        description=(
            "Existe um crachá que distinga as unidades, saia nos DOIS "
            "transportes e não exija escrita?"
        )
    )
    analisador.add_argument(
        "--intervalo",
        type=float,
        default=2.0,
        help="segundos entre a 1ª e a 2ª leitura (a prova de estabilidade)",
    )
    analisador.add_argument(
        "--so", action="append", default=[], metavar="0xNN",
        help="limitar a estes reports (pode repetir)",
    )
    analisador.add_argument(
        "--sem-mascara", action="store_true",
        help="mostra MAC inteiro na TELA (arquivo nenhum sai sem máscara)",
    )
    analisador.add_argument("--csv", default="", help="grava o resultado, já mascarado, aqui")
    argumentos = analisador.parse_args()

    ids = [int(v, 16) for v in argumentos.so] if argumentos.so else list(CANDIDATOS)
    if ANCORA not in ids:
        ids.append(ANCORA)
    ids.sort()

    aparelhos = descobrir_aparelhos()
    unidades = fisicos(aparelhos)

    print(
        cabecalho_do_instrumento(
            "identidade_nos_dois_transportes.py",
            "existe crachá que distinga as unidades nos DOIS transportes, sem escrita?",
            bibliotecas=["fcntl", "array", "csv"],
            escreve_no_aparelho=False,
            daemon_precisa_parar=False,
        )
    )
    print("\n  ESTE ARQUIVO NÃO SABE ESCREVER: não há HIDIOCSFEATURE nele.")
    print(f"\n{censo_da_mesa(aparelhos)}\n")

    if not unidades:
        print(resumo("nenhum DualSense físico na mesa. Nada a medir."))
        return 2

    todos_os_macs = [bytes_do_mac(a.mac) for a in unidades]

    medidas: list[Medida] = []
    for aparelho in unidades:
        print(f"  lendo {mascarar(aparelho.mac)} ({aparelho.hidraw}, {aparelho.transporte}) …")
        medidas.extend(medir_um(aparelho, ids, argumentos.intervalo))

    # A lista de agulhas se completa DEPOIS de ler e ANTES de imprimir. O
    # endereço do adaptador sai do próprio 0x09 — ver `mac_do_host_no_buffer`.
    for medida in medidas:
        if medida.primeira.ok:
            achado = mac_do_host_no_buffer(medida.primeira.dados, medida.report_id)
            if achado and achado not in todos_os_macs:
                todos_os_macs.append(achado)

    print("\n  O QUE CADA APARELHO DEVOLVEU (duas leituras, "
          f"{argumentos.intervalo:.1f}s de distância)\n")
    linhas = []
    for medida in medidas:
        visivel = medida.mac if argumentos.sem_mascara else mascarar(medida.mac)
        conteudo = (
            em_hexadecimal(mascarar_no_buffer(medida.primeira.dados, todos_os_macs))
            if medida.primeira.ok
            else medida.primeira.erro
        )
        linhas.append([
            visivel, medida.transporte, medida.hardware_version,
            f"0x{medida.report_id:02x}",
            f"{len(medida.primeira.dados)}B" if medida.primeira.ok else "-",
            medida.estavel,
            medida.ancora_no_mac or "—",
            conteudo,
        ])
    print(tabela(
        ["aparelho", "transporte", "hardware", "report", "bytes", "2ª leitura",
         "contém o MAC dele?", "conteúdo (MAC mascarado no buffer)"],
        linhas,
    ))

    vereditos = julgar(medidas, ids, unidades)
    print("\n  O JULGAMENTO — os três critérios da pergunta dela\n")
    print(tabela(
        ["report", "(a) distingue", "(b) nos dois transportes", "(c) sem escrita",
         "estável", "veredito"],
        [[
            f"0x{v.report_id:02x}",
            f"{v.valores_distintos} valores em {v.unidades_lidas}",
            f"cabo {v.lido_no_cabo}/{v.unidades_cabo}, rádio {v.lido_no_radio}/{v.unidades_radio}",
            "sim (GET_FEATURE)",
            "sim" if v.instaveis == 0 else f"NÃO ({v.instaveis})",
            v.frase,
        ] for v in vereditos],
    ))

    print("\n  A ÂNCORA ABSOLUTA — quem carrega o MAC da própria unidade\n")
    for v in vereditos:
        if v.ancorados_no_mac:
            print(
                f"    0x{v.report_id:02x}: {v.ancorados_no_mac}/{v.unidades_lidas} "
                f"unidades — {v.onde_ancora}"
            )

    if argumentos.csv:
        os.makedirs(os.path.dirname(os.path.abspath(argumentos.csv)), exist_ok=True)
        with open(argumentos.csv, "w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.writer(arquivo)
            escritor.writerow([
                "mac_mascarado", "transporte", "hardware_version", "report",
                "declarado", "bytes", "segunda_leitura", "contem_o_mac_dele",
                "conteudo_mascarado", "erro",
            ])
            for m in medidas:
                escritor.writerow([
                    mascarar(m.mac), m.transporte, m.hardware_version,
                    f"0x{m.report_id:02x}", "sim" if m.declarado else "não",
                    len(m.primeira.dados) if m.primeira.ok else "",
                    m.estavel, m.ancora_no_mac or "",
                    em_hexadecimal(
                        mascarar_no_buffer(m.primeira.dados, todos_os_macs), quantos=64
                    ) if m.primeira.ok else "",
                    m.primeira.erro,
                ])
        print(f"\n  CSV (mascarado) em {argumentos.csv}")

    servem = [f"0x{v.report_id:02x}" for v in vereditos if v.serve]
    if servem:
        print(resumo(
            f"{len(servem)} candidato(s) passam nos três critérios: {', '.join(servem)}. "
            f"Medido em {len(unidades)} unidade(s), "
            f"{sum(1 for a in unidades if a.transporte == 'cabo')} no cabo e "
            f"{sum(1 for a in unidades if a.transporte == 'rádio')} no rádio."
        ))
        return 0
    print(resumo("NENHUM candidato passa nos três critérios. Leia a tabela do julgamento."))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
