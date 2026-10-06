#!/usr/bin/env bash
# Verifica a privacidade de aparelho no repositório Hefesto - DualSense4Unix:
# endereço de rádio (MAC) em texto e em binário, e número de série de fábrica.
# Exit 0 se limpo, exit 1 se houver violação.
#
# A metade de vocabulário (quem assina, termos que não se publicam) é da régua
# única `scripts/check_autoria.py`, que lê a lista de fora do repositório.

set -euo pipefail

# ---------------------------------------------------------------------------
# MAC-BINARIO-EM-LITTLE-ENDIAN-01 (15/08/2026). MEDIDO.
# ---------------------------------------------------------------------------
#
# Em 15/08 a casa passou a versionar captura de rádio BINÁRIA
# (`docs/data/ensaios-brutos/*.btsnoop`), e o `btmon` grava o endereço do
# adaptador como seis bytes crus em ordem INVERTIDA: `d8:44:89:xx:xx:xx` vira
# `xx xx xx 89 44 d8`. Medido: nenhum portão desta casa via isso. Um `.btsnoop`
# de 238 KB entrou verde carregando o endereço duas vezes.
#
# Daqui em diante o portão também lê BYTES, e procura nas DUAS ordens — a
# big-endian dá zero nas capturas de hoje, e continua sendo procurada de
# propósito: zero é resultado declarado, não busca esquecida.
#
# A varredura é em Python porque `grep` quebra a entrada em LINHAS, e um
# endereço cujos octetos contenham 0x0a atravessaria a quebra sem ser visto.
# Fail-CLOSED se não houver python3: a mesma polaridade do guarda de CI —
# o que não dá para medir REPROVA.
#
# O portão AUTORITATIVO desta regra é `tests/unit/test_docs_mac_anonimato.py`
# (varre texto E bytes, com os testes de mordida). Este bloco é a segunda
# linha, para quem roda só o script.
if ! command -v python3 >/dev/null 2>&1; then
    echo "ANONIMATO: python3 ausente — a varredura de MAC em BINÁRIO não pôde"
    echo "rodar. Isto NÃO é 'limpo': é 'não medido'. Reprovando."
    exit 1
fi

# A lista vai por PIPE, e não por variável: `$(...)` DESCARTA byte nulo (o bash
# até avisa), e a lista é separada por nulo justamente para aguentar nome de
# arquivo com espaço. Medido em 15/08: com a lista numa variável, o python
# recebia um nome só, gigante, e a varredura devolvia verde sem ter aberto
# arquivo nenhum. O consumidor lê a entrada INTEIRA, então não há a corrida de
# SIGPIPE que o `pipefail` transformaria em veredito.
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
        "48b25d", "143a9a", "d42f4b", "444648")
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

# ---------------------------------------------------------------------------
# SERIAL-DE-FABRICA-01 (15/08/2026). MEDIDO.
# ---------------------------------------------------------------------------
#
# Terceira vez da mesma família nesta casa: o portão só reprova a forma que ele
# conhece. Foi assim no BURACO-DO-PORTAO-01 (06/08, o MAC colado) e no
# MAC-BINARIO-EM-LITTLE-ENDIAN-01 (o bloco logo acima).
#
# Hoje um SERIAL DE FÁBRICA real, dos 17 caracteres, entrou na docstring de
# `mascarar_serial()` em `scripts/ensaios/cor_do_plastico.py` — a função que
# mascara serial vazou um — e ESTE script passou VERDE. Motivo: tudo acima caça
# só a forma de um MAC. Antes desta linha,
# `grep -i serial scripts/check_anonymity.sh` devolvia ZERO.
#
# O serial identifica a unidade dela tão bem quanto o MAC: é o número da
# etiqueta, o da garantia, o que liga o aparelho à compra. A máscara da casa
# são os 6 primeiros caracteres e o resto em `#` — `A12B34###########`, num
# prefixo FORJADO: nem exemplo mascarado precisa carregar o prefixo dela — e ela
# preserva de propósito os caracteres 5 e 6, onde mora o código da COR, que é o
# que o ensaio E7 mede.
#
# A FORMA é a MEDIDA nos dois aparelhos que responderam ao E7, e não a que
# circulava de boca: o padrão `[A-Z]\d{2}[A-Z]\d{2}[A-Z]\d{10}` está ERRADO
# porque o segundo serial da bancada tem DÍGITO no caractere 4 (ver
# docs/data/ensaios-brutos/2026-08-15-E7-cor-do-plastico.csv, coluna
# `serial_mascarado`), e aquele padrão não casaria com ele.
#
# FALSO POSITIVO, MEDIDO na árvore de 15/08 (rastreados + novos): `[A-Z0-9]{17}`
# solto dá 12 reprovações em 8 arquivos, todas ruído (`INDEPENDENTEMENTE`,
# `MICROCASSYVOLTAGE`, `REDIMENSIONAMENTO`, ... e os dois seriais forjados
# legítimos). Exigir DÍGITO nas posições 2, 3, 5 e 6 leva o ruído a ZERO sem
# perder a forma real — palavra não tem dígito, e os forjados não têm dígito
# onde o serial verdadeiro tem.
#
# TRÊS FORMAS, porque duas já não bastaram: texto (inclusive dentro de
# binário), hexdump em pares (o serial de 17 caracteres ATRAVESSA a quebra de
# linha de um dump de 16 bytes) e corrida hexadecimal colada. A coluna de
# offset do dump (`0000`) e um `0x00001111` ficam de fora sozinhos, pela
# fronteira de hexadecimal dos pares.
#
# O portão AUTORITATIVO desta regra é `tests/unit/test_docs_mac_anonimato.py`
# (mesmo padrão, com os testes de mordida das três formas, e com um teste que
# reprova a divergência entre as duas cópias). Este bloco é a segunda linha,
# para quem roda só o script. O python3 já foi exigido no bloco acima.
#
# A mensagem NÃO imprime o serial achado: saída de portão vai para log de CI, e
# portão que republica o segredo para avisar do vazamento só mudou o vazamento
# de lugar. Saem os 6 públicos e a máscara, que bastam para achar a linha.
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
