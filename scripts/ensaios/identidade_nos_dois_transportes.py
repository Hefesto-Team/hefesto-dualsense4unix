#!/usr/bin/env python3
"""identidade_nos_dois_transportes.py — existe crachá que sirva no cabo E no rádio?"""

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

from comum import (
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

CANDIDATOS = (0x05, 0x09, 0x0B, 0x20, 0x22)

ANCORA = 0x20

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
    """`aa:bb:cc:dd:ee:ff` -> `aa bb cc dd ee ff`. Vazio se não for um MAC."""
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
    """Zera os octetos 4 e 5 de todo MAC conhecido achado DENTRO do buffer."""
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


OFFSET_DO_HOST_NO_0X09 = slice(10, 16)


def mac_do_host_no_buffer(dados: bytes, report_id: int) -> bytes:
    """O endereço do adaptador, tirado do PRÓPRIO relatório — não do sysfs."""
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
    """`GET_FEATURE` com validação de id e retry. Leitura pura, sempre."""
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
