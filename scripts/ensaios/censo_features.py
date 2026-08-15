#!/usr/bin/env python3
"""censo_features.py — lê os feature reports de cada controle, cabo x rádio.

A PERGUNTA QUE ELE RESPONDE
----------------------------
*Cada feature report é o MESMO byte a byte no cabo e no rádio, ou o transporte
muda o que o aparelho conta de si?*

E, de tabela, uma segunda pergunta que a casa carregava errada: *quantos feature
reports "ninguém nunca leu"?* Em 15/08/2026 os do rádio foram lidos nos quatro
controles, com retry e validação de id. A linha de índice que fala em "catorze
feature reports que ninguém nunca leu" está derrubada por medição.

NÃO EXISTE "A LISTA DOS FEATURE REPORTS DO DUALSENSE" (medido 15/08/2026)
--------------------------------------------------------------------------
Existe **uma por transporte**, e nenhuma é subconjunto da outra. O mesmo
controle declara 17 feature reports por rádio e 22 no cabo; o rádio tem
`0xf6` (547 B) e `0xf7`, o cabo tem `0x0a`, `0x0c`, `0x21`, `0x84`, `0x85`,
`0xa0`, `0xe0`, e até um id comum como `0xf5` muda de tamanho (8 B no rádio,
4 B no cabo).

Isso é uma armadilha real, e este instrumento já caiu nela: a primeira versão
tirava a lista de reports do PRIMEIRO aparelho e a aplicava a todos, de modo
que os reports exclusivos do outro transporte nunca eram pedidos. O erro só
aparece com os dois transportes na mesa **ao mesmo tempo** — que é precisamente
o que o desenho de ensaio 2+2 existe para pegar. Hoje ele usa a UNIÃO dos
descritores e imprime, antes de ler qualquer coisa, quem declara o quê.

AS TRÊS COISAS QUE ESTE INSTRUMENTO SABE E QUE CUSTARAM CARO
-------------------------------------------------------------
1. **Por rádio, o `GET_FEATURE` falha por TIMEOUT, não por erro.** O pedido sai
   pelo canal de controle L2CAP e bate no `REPORT_REQ_TIMEOUT` de 3 s do BlueZ.
   Cada falha custa ~3,2-3,7 s — essa é a assinatura, e é como se reconhece o
   caso. **A cura é REPETIR**: em 15/08/2026, dois dos quatro controles
   responderam na 1ª tentativa e um precisou de 5. É a mesma medição que
   justifica o `feature_retries` do DKMS desta casa.

2. **O aparelho pode devolver o report ERRADO.** Um controle respondeu com id
   `0x80` a um pedido de `0x20` — resposta TROCADA, não erro; o ioctl retornou
   sucesso. Por isso `buf[0] == report_id` é **obrigatório**: sem essa checagem
   se parseia lixo com convicção.

3. **Os tamanhos vêm do `report_descriptor`, nunca de chute.** O parser em
   `comum.tamanhos_do_descritor` foi conferido contra os 17 valores conhecidos e
   bate item a item, `0xf6` de 547 bytes incluído.

O DAEMON PRECISA ESTAR PARADO — e este é o ponto mais importante
-----------------------------------------------------------------
Sim. Com o daemon vivo, o `hefesto-hidraw-broker` deixa o hidraw do controle
FÍSICO em `0600 root:root` de propósito, para esconder o aparelho do jogo. O
instrumento então leva `PermissionError` e **não mede nada**. Isso não é defeito
do controle nem do instrumento: é o produto funcionando. O que seria defeito é
imprimir "o controle não respondeu", que é uma afirmação sobre o aparelho —
então ele não imprime isso: ele nomeia o broker.

A COR DO CONTROLE, E POR QUE ELA NÃO SAI DAQUI
-----------------------------------------------
A cor mora nos caracteres 5 e 6 do serial de fábrica, que se lê no `0x81` —
**mas só depois de um `SET_FEATURE 0x80`**, que é ESCRITA. Nesta rodada nada se
escreve no aparelho. Com `--mostrar-comando-da-cor` o instrumento imprime o
comando exato e para, para a decisão de escrever ser dela.

USO
    censo_features.py                      # lê todos os físicos que achar
    censo_features.py --tentativas 8       # mais paciência com o rádio
    censo_features.py --so 0x20 --so 0x22  # só alguns reports
    censo_features.py --mostrar-comando-da-cor
"""

from __future__ import annotations

import argparse
import array
import errno
import fcntl
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comum import (
    RADIO,
    Aparelho,
    cabecalho_do_instrumento,
    censo_da_mesa,
    descobrir_aparelhos,
    diagnostico_de_acesso,
    fisicos,
    resumo,
    tabela,
    tamanhos_do_descritor,
)

# HIDIOCGFEATURE: _IOC(_IOC_WRITE|_IOC_READ, 'H', 0x07, tamanho).
# Montado à mão de propósito — não há dependência nova aqui, e o número mágico
# fica visível em vez de escondido atrás de uma lib.
_IOC_WRITE_LEITURA = 3
_IOC_TIPO_HID = ord("H")
_IOC_NR_GETFEATURE = 0x07


def _hidiocgfeature(tamanho: int) -> int:
    return (
        (_IOC_WRITE_LEITURA << 30)
        | (tamanho << 16)
        | (_IOC_TIPO_HID << 8)
        | _IOC_NR_GETFEATURE
    )


# A assinatura do timeout do BlueZ. Abaixo disto a falha é outra coisa.
SEGUNDOS_DE_TIMEOUT_L2CAP = 2.5

# CRC-32 do DualSense: semente 0xA3 no primeiro byte, IEEE 802.3 no resto.
SEMENTE_CRC = 0xA3


def _crc32_dualsense(dados: bytes) -> int:
    import zlib

    return zlib.crc32(dados) & 0xFFFFFFFF


class Leitura:
    """O resultado de pedir UM feature report a UM aparelho."""

    def __init__(self, report_id: int, tamanho: int) -> None:
        self.report_id = report_id
        self.tamanho = tamanho
        self.dados: bytes = b""
        self.tentativas = 0
        self.segundos = 0.0
        self.erro = ""
        self.id_trocado = -1
        self.crc: str = "-"
        self.definitivo = False
        self.sumiu = False

    @property
    def ok(self) -> bool:
        return bool(self.dados) and not self.erro


def ler_feature(
    caminho: str,
    report_id: int,
    tamanho: int,
    tentativas: int,
    *,
    e_radio: bool = False,
) -> Leitura:
    """Pede um feature report, com retry e validação de id.

    Devolve SEMPRE — a falha vira campo, não exceção, porque uma tabela com
    buraco silencioso é pior que uma tabela com a palavra "falhou" escrita.

    **Nem toda falha merece retry, e insistir na errada custa tempo à toa.**
    Medido em 15/08/2026, com os controles no cabo: um report que o descritor
    DECLARA mas o firmware não implementa devolve `EPIPE` (stall do endpoint)
    na hora, sempre, nas seis tentativas. Isso é resposta DEFINITIVA do
    aparelho — "não tenho esse report" — e é categoria diferente do
    `REPORT_REQ_TIMEOUT` de 3 s do BlueZ, que é o rádio se perdendo e a única
    coisa que repetir de fato cura. Repetir um `EPIPE` seis vezes só faz o
    censo demorar seis vezes mais para chegar à mesma conclusão.
    """
    leitura = Leitura(report_id, tamanho)
    inicio = time.monotonic()
    fd = -1
    try:
        try:
            fd = os.open(caminho, os.O_RDWR)
        except PermissionError:
            fd = os.open(caminho, os.O_RDONLY)
    except OSError as erro:
        leitura.erro = f"{type(erro).__name__}: {diagnostico_de_acesso(caminho)}"
        leitura.segundos = time.monotonic() - inicio
        return leitura

    try:
        for numero in range(1, tentativas + 1):
            leitura.tentativas = numero
            buffer = array.array("B", [0] * tamanho)
            buffer[0] = report_id
            try:
                escritos = fcntl.ioctl(fd, _hidiocgfeature(tamanho), buffer, True)
            except OSError as erro:
                if erro.errno == errno.EPIPE:
                    # Stall: o firmware não implementa este report. Definitivo.
                    leitura.erro = "não implementado (EPIPE)"
                    leitura.definitivo = True
                    break
                if erro.errno in (errno.ENODEV, errno.ENOENT):
                    # O controle SUMIU no meio do ensaio. Medido em 15/08/2026:
                    # um controle de rádio caiu na metade do censo, e as falhas
                    # passaram a voltar em 0,01 s — o oposto da assinatura de
                    # ~3 s do timeout L2CAP. Sem esta separação, uma tabela
                    # inteira de "FALHOU" seria lida como "o aparelho recusa os
                    # reports", quando o aparelho simplesmente não está mais lá.
                    leitura.erro = "controle DESCONECTOU no meio do ensaio (ENODEV)"
                    leitura.definitivo = True
                    leitura.sumiu = True
                    break
                leitura.erro = f"ioctl: {erro.strerror or erro}"
                continue
            if escritos <= 0:
                leitura.erro = f"ioctl devolveu {escritos}"
                continue
            recebido = bytes(buffer[:escritos])
            if recebido[0] != report_id:
                # A resposta TROCADA de 15/08. Não é erro: é outro report.
                leitura.id_trocado = recebido[0]
                leitura.erro = f"veio id 0x{recebido[0]:02x} no lugar de 0x{report_id:02x}"
                continue
            leitura.dados = recebido
            leitura.erro = ""
            break
    finally:
        os.close(fd)

    leitura.segundos = time.monotonic() - inicio
    # O CRC-32 de semente 0xA3 é o enquadramento do BLUETOOTH. No cabo os quatro
    # últimos bytes são payload como qualquer outro, e conferi-los ali produz
    # "difere" em TODOS os reports — um alarme convincente e inteiramente falso,
    # que é a forma de erro mais cara desta casa. Por isso o CRC só é calculado
    # no rádio; no cabo a coluna diz que não se aplica, em vez de inventar.
    if leitura.ok and e_radio and len(leitura.dados) >= 5:
        esperado = int.from_bytes(leitura.dados[-4:], "little")
        if esperado == 0:
            # Trailer zerado: este report não CARREGA CRC. Chamar isso de
            # "difere" seria alarme falso — e alarme falso convincente é o
            # defeito mais caro desta casa. Um report todo zero tem os quatro
            # últimos bytes zero por ser todo zero, não por estar corrompido.
            leitura.crc = "sem trailer"
        else:
            calculado = _crc32_dualsense(bytes([SEMENTE_CRC]) + leitura.dados[:-4])
            leitura.crc = "confere" if esperado == calculado else "DIFERE"
    elif leitura.ok:
        leitura.crc = "n/a (cabo)"
    return leitura


def _amostra(dados: bytes, quantos: int = 12) -> str:
    return " ".join(f"{b:02x}" for b in dados[:quantos]) + (" …" if len(dados) > quantos else "")


def _classificar(dados: bytes) -> str:
    corpo = dados[1:]
    if not corpo:
        return "vazio"
    if not any(corpo):
        return "TODO ZERO"
    return "com dado"


def medir(alvos: list[Aparelho], ids: list[int], tentativas: int) -> dict[str, dict[int, Leitura]]:
    resultados: dict[str, dict[int, Leitura]] = {}
    for aparelho in alvos:
        print(f"\n  lendo {aparelho.apelido} ({aparelho.hidraw}, {aparelho.transporte}) …")
        tamanhos = tamanhos_do_descritor(aparelho.dir_device)["feature"]
        e_radio = aparelho.transporte == RADIO
        por_id: dict[int, Leitura] = {}
        for report_id in ids:
            tamanho = tamanhos.get(report_id)
            if tamanho is None:
                # Não é falha: este transporte simplesmente não DECLARA o report.
                # Dizer isso é o ponto — foi assim que se viu que os dois lados
                # declaram conjuntos diferentes.
                print(f"      0x{report_id:02x}    -   não declarado neste transporte")
                continue
            leitura = ler_feature(
                aparelho.caminho_hidraw, report_id, tamanho, tentativas, e_radio=e_radio
            )
            por_id[report_id] = leitura
            if leitura.ok:
                marca = "ok"
            elif leitura.sumiu:
                marca = "SUMIU"
            elif leitura.definitivo:
                marca = "NÃO TEM"
            else:
                marca = "FALHOU"
            lento = " <- timeout L2CAP" if leitura.segundos >= SEGUNDOS_DE_TIMEOUT_L2CAP else ""
            print(
                f"      0x{report_id:02x} {tamanho:>4}B  {marca:<8}"
                f"{leitura.tentativas} tentativa(s)  {leitura.segundos:5.2f}s{lento}"
            )
        resultados[aparelho.apelido] = por_id
    return resultados


def imprimir_o_que_cada_transporte_declara(alvos: list[Aparelho]) -> None:
    """Quais feature reports cada TRANSPORTE declara — antes de ler qualquer um.

    Esta tabela é o ensaio 2+2 em estado puro: ela sai do `report_descriptor`,
    de graça, e mostra que cabo e rádio **não expõem o mesmo conjunto**. A
    primeira versão deste instrumento tirava a lista de reports do PRIMEIRO
    aparelho e a aplicava a todos — e com isso nunca pedia os reports que só o
    rádio declara. O erro só aparece com os dois transportes na mesa ao mesmo
    tempo, que é exatamente o que este desenho de ensaio existe para pegar.
    """
    por_transporte: dict[str, set[int]] = {}
    for aparelho in alvos:
        declarados = set(tamanhos_do_descritor(aparelho.dir_device)["feature"])
        por_transporte.setdefault(aparelho.transporte, set()).update(declarados)

    print()
    print("  O QUE CADA TRANSPORTE DECLARA (do report_descriptor, sem ler nada)")
    print()
    todos = sorted(set().union(*por_transporte.values())) if por_transporte else []
    nomes = sorted(por_transporte)
    linhas = [
        [f"0x{rid:02x}"] + ["sim" if rid in por_transporte[t] else "—" for t in nomes]
        for rid in todos
    ]
    print(tabela(["report", *nomes], linhas))
    if len(nomes) >= 2:
        so_um = [
            f"0x{rid:02x}"
            for rid in todos
            if sum(1 for t in nomes if rid in por_transporte[t]) == 1
        ]
        if so_um:
            print()
            print(f"    {len(so_um)} report(s) declarados por UM transporte só: {', '.join(so_um)}")
            print("    Um conjunto não é subconjunto do outro — não existe 'a lista")
            print("    dos feature reports do DualSense'; existe uma por transporte.")


def imprimir_tabela_cabo_x_radio(
    alvos: list[Aparelho],
    resultados: dict[str, dict[int, Leitura]],
    ids: list[int],
) -> tuple[int, int]:
    """A tabela que ela lê. Devolve (reports iguais, reports que diferem)."""
    do_cabo = [a for a in alvos if a.transporte == "cabo"]
    do_radio = [a for a in alvos if a.transporte == "rádio"]

    cabecalho = ["report", "bytes", "tentativas", "CRC", "conteúdo", "cabo x rádio"]
    linhas: list[list[str]] = []
    iguais = difere = 0

    for report_id in ids:
        leituras = [resultados[a.apelido].get(report_id) for a in alvos]
        presentes = [x for x in leituras if x is not None]
        if not presentes:
            continue
        tamanho = presentes[0].tamanho
        boas = [x for x in presentes if x.ok]
        if not boas:
            motivos = {x.erro for x in presentes if x.erro}
            linhas.append(
                [
                    f"0x{report_id:02x}",
                    str(tamanho),
                    "-",
                    "-",
                    "NÃO LIDO",
                    "; ".join(sorted(motivos))[:44] or "falhou",
                ]
            )
            continue

        pior = max(x.tentativas for x in boas)
        # O CRC só existe no rádio, então só o veredito do rádio entra na coluna.
        # Misturar o "n/a (cabo)" ali produzia células como "confere/n/a (cabo)",
        # que obrigam quem lê a decidir qual metade vale.
        crcs = {x.crc for x in boas if x.crc != "n/a (cabo)"} or {"n/a (cabo)"}
        conteudo = _classificar(boas[0].dados)

        def _bytes_de(grupo: list[Aparelho], rid: int = report_id) -> set[bytes]:
            achados = set()
            for aparelho in grupo:
                leitura = resultados[aparelho.apelido].get(rid)
                if leitura is not None and leitura.ok:
                    achados.add(leitura.dados)
            return achados

        cabo_bytes = _bytes_de(do_cabo)
        radio_bytes = _bytes_de(do_radio)
        if not cabo_bytes or not radio_bytes:
            veredito = "sem par (um transporte só)"
        elif cabo_bytes == radio_bytes:
            veredito = "IDÊNTICO"
            iguais += 1
        else:
            veredito = "DIFERE"
            difere += 1

        linhas.append(
            [
                f"0x{report_id:02x}",
                str(tamanho),
                str(pior),
                "/".join(sorted(crcs)),
                conteudo,
                veredito,
            ]
        )

    print()
    print("  OS FEATURE REPORTS, LADO A LADO")
    print()
    print(tabela(cabecalho, linhas))
    return iguais, difere


def imprimir_por_unidade(
    alvos: list[Aparelho],
    resultados: dict[str, dict[int, Leitura]],
    ids: list[int],
) -> None:
    """Quais reports separam uma unidade da outra — a pergunta da identidade."""
    cabecalho = ["report", "difere entre unidades?", "amostra do 1º aparelho"]
    linhas: list[list[str]] = []
    for report_id in ids:
        boas = [
            r for a in alvos if (r := resultados[a.apelido].get(report_id)) is not None and r.ok
        ]
        if len(boas) < 2:
            continue
        distintos = {r.dados for r in boas}
        linhas.append(
            [
                f"0x{report_id:02x}",
                f"SIM ({len(distintos)} valores em {len(boas)})" if len(distintos) > 1 else "não",
                _amostra(boas[0].dados),
            ]
        )
    if linhas:
        print()
        print("  O QUE SEPARA UMA UNIDADE DA OUTRA")
        print()
        print(tabela(cabecalho, linhas))


COMANDO_DA_COR = """
  A COR DE FÁBRICA — CAMINHO IDENTIFICADO, NÃO MEDIDO (10/08 e 15/08/2026)
  ------------------------------------------------------------------------
  A cor está nos caracteres 5 e 6 do serial de 17 caracteres, e o serial só
  aparece DEPOIS de um SET_FEATURE — que é ESCRITA no aparelho. Este
  instrumento não escreve. O comando exato é:

      SET_FEATURE 0x80  com payload [0x01, 0x13]      (base=1, num=19)
      GET_FEATURE 0x81  -> 64 bytes
          exige buf[1]==1, buf[2]==19, buf[3]==2, senão é erro
          buf[4..20] = 17 chars ASCII = o serial impresso na traseira
          cor = serial[4:6]

      '00' White           '01' Midnight Black   '02' Cosmic Red
      '03' Nova Pink       '04' Galactic Purple  '05' Starlight Blue
      '06' Grey Camouflage '07' Volcanic Red     '08' Sterling Silver
      '09' Cobalt Blue     '10'-'12' Chroma Teal/Indigo/Pearl
      '30' 30th Anniversary            Z1..ZB especiais

  Fonte: dualshock-tools.github.io, js/controllers/ds5-controller.js:196-226 e
  :404-414, com o mantenedor confirmando na issue #210; duas implementações
  independentes concordam (nsfm/dualsense-ts, TechAntohere/Senshi).

  NÃO MEDIDO POR NÓS, e a honestidade aqui é o ponto: a leitura exige a escrita
  acima, que ela ainda não autorizou, e por RÁDIO ninguém no mundo demonstrou —
  o dualshock-tools recusa Bluetooth de saída. Registre como CAMINHO
  IDENTIFICADO, NÃO MEDIDO, e não como "o controle não sabe a própria cor":
  essa segunda frase seria a FALÁCIA DO PERFIL AUSENTE.
"""


def main() -> int:
    analisador = argparse.ArgumentParser(
        description="Censo dos feature reports do DualSense, cabo x rádio.",
    )
    analisador.add_argument(
        "--tentativas",
        type=int,
        default=6,
        help="quantas vezes repetir cada GET_FEATURE (o rádio precisa; padrão 6)",
    )
    analisador.add_argument(
        "--so",
        action="append",
        default=[],
        metavar="0xNN",
        help="limitar a estes reports (pode repetir)",
    )
    analisador.add_argument(
        "--mostrar-comando-da-cor",
        action="store_true",
        help="imprime o comando de ESCRITA que leria a cor, e para",
    )
    argumentos = analisador.parse_args()

    print(
        cabecalho_do_instrumento(
            "censo_features.py",
            "cada feature report é o mesmo byte a byte no cabo e no rádio?",
            bibliotecas=["fcntl", "array", "zlib"],
            escreve_no_aparelho=False,
            daemon_precisa_parar=True,
        )
    )

    if argumentos.mostrar_comando_da_cor:
        print(COMANDO_DA_COR)
        print(resumo("comando impresso; NADA foi escrito no aparelho. A decisão é dela."))
        return 0

    aparelhos = descobrir_aparelhos()
    alvos = fisicos(aparelhos)
    print(f"\n  {censo_da_mesa(aparelhos)}")

    if not alvos:
        print(resumo("nenhum DualSense físico encontrado — nada medido."))
        return 1

    cabecalho = ["aparelho", "hidraw", "transporte", "acesso"]
    linhas = [
        [a.apelido, a.hidraw, a.transporte, diagnostico_de_acesso(a.caminho_hidraw)] for a in alvos
    ]
    print()
    print(tabela(cabecalho, linhas))

    bloqueados = [a for a in alvos if diagnostico_de_acesso(a.caminho_hidraw) != "acessível"]
    if len(bloqueados) == len(alvos):
        print()
        print("  NENHUM hidraw físico abre. Isto NÃO é o controle não responder —")
        print("  é o broker do Hefesto escondendo o aparelho do jogo, como ele promete.")
        print("  Para medir, pare o daemon:  systemctl --user stop hefesto-dualsense4unix")
        print(resumo(f"0 de {len(alvos)} controles legíveis: broker no caminho. Nada medido."))
        return 2

    imprimir_o_que_cada_transporte_declara(alvos)

    # A UNIÃO dos declarados por todos os aparelhos, não os do primeiro: cabo e
    # rádio expõem conjuntos diferentes, e tirar a lista de um só deixaria os
    # reports exclusivos do outro sem nunca serem pedidos.
    disponiveis: set[int] = set()
    for aparelho in alvos:
        disponiveis.update(tamanhos_do_descritor(aparelho.dir_device)["feature"])
    ids = [int(x, 16) for x in argumentos.so] if argumentos.so else sorted(disponiveis)
    print(f"\n  {len(ids)} feature reports na UNIÃO dos descritores da mesa.")

    resultados = medir(alvos, ids, argumentos.tentativas)
    iguais, difere = imprimir_tabela_cabo_x_radio(alvos, resultados, ids)
    imprimir_por_unidade(alvos, resultados, ids)

    lidos = sum(1 for por_id in resultados.values() for r in por_id.values() if r.ok)
    total = sum(len(por_id) for por_id in resultados.values())
    trocados = sum(
        1 for por_id in resultados.values() for r in por_id.values() if r.id_trocado >= 0
    )

    transportes = {a.transporte for a in alvos}
    if len(transportes) < 2:
        veredito = (
            f"{lidos}/{total} leituras ok em {len(alvos)} controle(s), "
            f"TODOS no {next(iter(transportes))} — a coluna cabo x rádio não comparou nada. "
            "Para o ensaio 2+2, ponha dois controles no cabo."
        )
    else:
        veredito = (
            f"{lidos}/{total} leituras ok; {iguais} reports idênticos entre transportes, "
            f"{difere} diferentes."
        )
    if trocados:
        veredito += f" {trocados} resposta(s) com id trocado — a validação de buf[0] pegou."

    sumidos = sorted(
        {
            apelido
            for apelido, por_id in resultados.items()
            for r in por_id.values()
            if r.sumiu
        }
    )
    if sumidos:
        print()
        print("  >> ATENÇÃO: controle(s) DESCONECTARAM no meio do ensaio:")
        for apelido in sumidos:
            print(f"       {apelido}")
        print("  >> O que eles deixaram de responder NÃO é recusa do aparelho —")
        print("  >> o aparelho não estava mais lá. Reconecte e repita o censo.")
        veredito += f" {len(sumidos)} controle(s) sumiram no meio — censo INCOMPLETO."

    print(resumo(veredito))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
