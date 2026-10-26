#!/usr/bin/env bash

set -euo pipefail

if ! command -v python3 >/dev/null 2>&1; then
    echo "ANONIMATO: python3 ausente — a varredura de MAC em BINÁRIO não pôde"
    echo "rodar. Isto NÃO é 'limpo': é 'não medido'. Reprovando."
    exit 1
fi

_listar_para_varredura_binaria() {
    if git rev-parse --git-dir >/dev/null 2>&1; then
        git ls-files -z --cached --others --exclude-standard 2>/dev/null
    else
        find . -type f -not -path './.git/*' -print0 2>/dev/null
    fi
}

MAC_BIN=$(_listar_para_varredura_binaria | python3 -c '
import sys

# ESPELHO de tests/unit/test_docs_mac_anonimato.py::_OUIS_REAIS_OCTETOS e de
# scripts/mascarar_btsnoop.py. tests/unit/test_mascarar_btsnoop.py reprova a
# divergência entre as três cópias.
OUIS = ("d84489", "a0fa9c", "e417d8", "e0f6b5",
        "48b25d", "143a9a", "d42f4b", "444648",
        "aca7f1")
# Imagem e catálogo compilado ficam de fora: três bytes casam por acaso em dado
# comprimido, e PNG que muda a cada captura de tela geraria alarme intermitente.
# `.svg` SAIU daqui em 26/08/2026, e a razão é a mesma que tirou o `.svg` do
# `EXCLUIR_SUFIXO` do irmão no mesmo dia: SVG é XML de TEXTO PURO, e o motivo
# escrito para os outros desta lista ("três bytes casam por acaso em dado
# comprimido") não vale para ele. Medido: um serial de fábrica de 17 caracteres
# dentro de um `<text>` de SVG COMMITADO saía rc=0; o mesmo conteúdo, byte a
# byte, num `.md` saía rc=1. São 49 SVGs versionados, todos texto (46 utf-8,
# 3 us-ascii). Duas réguas independentes é o que revela — e as duas estavam cegas.
PULA = (".png", ".mo", ".ico", ".gif", ".jpg", ".jpeg")

# 23/08/2026 — o portão passou a DESCOMPRIMIR em vez de pular o comprimido.
#
# Medido no dia em que os logs de frametime do Sackboy entraram na árvore
# (`docs/process/estudos/dados/2026-08-23-frametime-sackboy/*.csv.gz`): o
# portão acusou TRÊS MACs em dois `.gz`, e os arquivos descomprimidos não têm
# MAC nenhum — são só números de frametime e um cabeçalho de máquina. Eram os
# três bytes do OUI casando por acaso no envelope comprimido, exatamente o que
# o comentário do `PULA` acima já previa para dado de alta entropia.
#
# A cura NÃO é acrescentar ".gz" ao `PULA`: isso cegaria o portão para um MAC
# de verdade dentro de um comprimido, que é justamente o caso que ele existe
# para pegar. A cura é olhar o CONTEÚDO. Assim o portão fica mais forte nas
# duas pontas — sem o falso positivo do envelope, e enxergando dentro do
# arquivo.
#
# `.btsnoop.gz` (se um dia existir) cai aqui e é varrido como btsnoop cru.
def _conteudo(nome, caminho):
    """Bytes a varrer: o arquivo, ou o que ele contém quando é comprimido."""
    try:
        with open(nome, "rb") as fh:
            dados = fh.read()
    except OSError:
        return None
    if not caminho.lower().endswith(".gz"):
        return dados
    try:
        import gzip
        return gzip.decompress(dados)
    except (OSError, EOFError, ValueError):
        # Comprimido ilegível: varre o envelope mesmo, que é o lado seguro do
        # erro — melhor um alarme falso que um MAC entrando escondido.
        return dados

achados = []
for nome in sys.stdin.buffer.read().split(b"\0"):
    if not nome:
        continue
    caminho = nome.decode("utf-8", "surrogateescape")
    if caminho.lower().endswith(PULA):
        continue
    dados = _conteudo(nome, caminho)
    if dados is None:
        continue
    for oui in OUIS:
        be = bytes.fromhex(oui)
        le = be[::-1]
        pos = dados.find(be)
        while pos != -1:
            campo = dados[pos:pos + 6]
            if len(campo) == 6 and (campo[3] or campo[4]):
                achados.append(
                    "%s: offset %d (big-endian): %s" % (caminho, pos, campo.hex(":"))
                )
            pos = dados.find(be, pos + 1)
        pos = dados.find(le)
        while pos != -1:
            inicio = pos - 3
            if inicio >= 0:
                campo = dados[inicio:inicio + 6]
                if campo[1] or campo[2]:
                    achados.append(
                        "%s: offset %d (little-endian): %s"
                        % (caminho, inicio, campo[::-1].hex(":"))
                    )
            pos = dados.find(le, pos + 1)
for linha in sorted(achados):
    print(linha)
')

if [[ -n "$MAC_BIN" ]]; then
    echo "ANONIMATO VIOLADO — MAC de hardware REAL gravado em BINÁRIO:"
    echo "------------------------------------------------"
    echo "$MAC_BIN"
    echo "------------------------------------------------"
    echo ""
    echo "Nenhum portão de TEXTO enxerga isto: numa captura HCI o endereço vai"
    echo "em bytes crus e em ordem invertida (little-endian)."
    echo "Cura: scripts/mascarar_btsnoop.py ENTRADA -o SAIDA (captura .btsnoop),"
    echo "ou zere os octetos 4 e 5 dos seis bytes apontados. A máscara da casa"
    echo "é OUI:00:00:NN, e o tamanho do arquivo não pode mudar."
    exit 1
fi

SERIAL_HITS=$(_listar_para_varredura_binaria | python3 -c '
import re
import sys

# ESPELHO de tests/unit/test_docs_mac_anonimato.py::PADRAO_DE_SERIAL.
# test_o_check_anonymity_usa_o_mesmo_padrao_de_serial reprova a divergência.
PADRAO = (
    r"(?<![A-Z0-9])"
    r"[A-Z][0-9]{2}[A-Z0-9][0-9]{2}"
    r"[A-Z0-9]{11}"
    r"(?![A-Z0-9])"
)
SERIAL = re.compile(PADRAO)
PAR_HEX = re.compile(rb"(?<![0-9A-Fa-f])([0-9A-Fa-f]{2})(?![0-9A-Fa-f])")
HEX_COLADO = re.compile(rb"(?<![0-9A-Fa-f])((?:[0-9A-Fa-f]{2}){17,})(?![0-9A-Fa-f])")
# `.svg` SAIU daqui em 26/08/2026, e a razão é a mesma que tirou o `.svg` do
# `EXCLUIR_SUFIXO` do irmão no mesmo dia: SVG é XML de TEXTO PURO, e o motivo
# escrito para os outros desta lista ("três bytes casam por acaso em dado
# comprimido") não vale para ele. Medido: um serial de fábrica de 17 caracteres
# dentro de um `<text>` de SVG COMMITADO saía rc=0; o mesmo conteúdo, byte a
# byte, num `.md` saía rc=1. São 49 SVGs versionados, todos texto (46 utf-8,
# 3 us-ascii). Duas réguas independentes é o que revela — e as duas estavam cegas.
PULA = (".png", ".mo", ".ico", ".gif", ".jpg", ".jpeg")
PUBLICOS = 6


def mascarar(achado):
    return achado[:PUBLICOS] + "#" * (len(achado) - PUBLICOS)


achados = []
for nome in sys.stdin.buffer.read().split(b"\0"):
    if not nome:
        continue
    caminho = nome.decode("utf-8", "surrogateescape")
    if caminho.lower().endswith(PULA):
        continue
    try:
        with open(nome, "rb") as fh:
            dados = fh.read()
    except OSError:
        continue
    for m in SERIAL.finditer(dados.decode("latin-1")):
        achados.append("%s (texto): %s" % (caminho, mascarar(m.group(0))))
    fluxo = bytes(int(p, 16) for p in PAR_HEX.findall(dados))
    for m in SERIAL.finditer(fluxo.decode("latin-1")):
        achados.append("%s (hexdump): %s" % (caminho, mascarar(m.group(0))))
    for corrida in HEX_COLADO.finditer(dados):
        bruto = bytes.fromhex(corrida.group(1).decode("ascii")).decode("latin-1")
        for m in SERIAL.finditer(bruto):
            achados.append("%s (hex colado): %s" % (caminho, mascarar(m.group(0))))
for linha in sorted(set(achados)):
    print(linha)
')

if [[ -n "$SERIAL_HITS" ]]; then
    echo "ANONIMATO VIOLADO — SERIAL DE FÁBRICA real em arquivo versionado:"
    echo "------------------------------------------------"
    echo "$SERIAL_HITS"
    echo "------------------------------------------------"
    echo ""
    echo "O serial de 17 caracteres identifica a unidade tão bem quanto o MAC:"
    echo "é o número da etiqueta e o da garantia. Máscara da casa: os 6"
    echo "primeiros caracteres e o resto em '#' (A12B34###########). Os"
    echo "caracteres 5 e 6 — o código da COR — ficam preservados de propósito."
    echo "Em instrumento, use mascarar_serial() de scripts/ensaios/cor_do_plastico.py."
    echo "O achado acima já sai mascarado: o portão não republica o segredo."
    exit 1
fi

echo "OK: anonimato preservado."
exit 0
