#!/usr/bin/env bash
# Diz QUAL aba do notebook está ativa, medindo o sublinhado da aba selecionada.
#
# O tema declara em gui/theme.css que o rosa da marca (#ff79c6) aparece em dois
# lugares apenas: a marca e a aba ativa. Isso faz do pixel rosa na faixa da barra
# de abas um sensor confiável de qual página está aberta -- e é o que permite
# fotografar as nove abas sem que a sequência saia deslocada.
#
# uso:   aba_ativa.sh <captura.png>
# saída: "<índice> <centro-x-do-sublinhado>"  ou  "-1 0" quando não encontra
#
# Requer ImageMagick e Python 3.
set -euo pipefail

IMAGEM="${1:-}"
if [ -z "$IMAGEM" ]; then
    echo "uso: $(basename "$0") <captura.png>" >&2
    exit 2
fi

python3 - "$IMAGEM" <<'PY'
import re
import subprocess
import sys

imagem = sys.argv[1]

# Faixa do sublinhado com a janela maximizada em 1920x1080: as nove abas cabem
# nos primeiros 1000 px, e o sublinhado fica entre y=245 e y=258.
saida = subprocess.check_output(
    ["convert", imagem, "-crop", "1000x14+0+245", "+repage", "-depth", "8", "txt:-"]
).decode()

colunas = []
for linha in saida.splitlines()[1:]:
    achado = re.match(r"(\d+),(\d+): \((\d+),(\d+),(\d+)", linha)
    if not achado:
        continue
    x, _y, vermelho, verde, azul = (int(v) for v in achado.groups())
    if vermelho > 200 and 90 < verde < 160 and azul > 170:
        colunas.append(x)

if not colunas:
    print("-1 0")
    raise SystemExit(0)

centro = (min(colunas) + max(colunas)) // 2

# Centros medidos das nove abas, janela maximizada em 1920x1080.
CENTROS = [56, 139, 232, 332, 429, 515, 602, 706, 840]
indice = min(range(len(CENTROS)), key=lambda i: abs(CENTROS[i] - centro))
print(f"{indice} {centro}")
PY
