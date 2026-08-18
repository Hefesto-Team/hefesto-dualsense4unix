#!/usr/bin/env bash
# Percorre as nove abas da janela VERIFICANDO onde parou a cada passo, em vez de
# confiar numa rajada de teclas.
#
# Por que verificar: o `wtype` cria e destrói um teclado virtual a cada chamada,
# e em rajada o compositor perde eventos. O resultado é a sequência inteira sair
# deslocada em uma aba -- a foto chamada "gatilhos" mostrando "status". Aconteceu
# duas vezes antes de este laço existir.
#
# uso:  capturar_verificado.sh <diretório-de-saída>
#
# A janela precisa estar ABERTA, MAXIMIZADA e EM FOCO.
#
# O comando de captura é configurável, porque varia por ambiente. Ele deve
# imprimir na saída padrão o caminho do PNG gerado:
#   CAPTURA_CMD="minha-captura.sh" capturar_verificado.sh /tmp/abas
set -uo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DESTINO="${1:-}"
CAPTURA_CMD="${CAPTURA_CMD:-cosmic-screenshot --interactive=false --notify=false}"

if [ -z "$DESTINO" ]; then
    echo "uso: $(basename "$0") <diretório-de-saída>" >&2
    exit 2
fi
mkdir -p "$DESTINO"

NOMES=(
    00-inicio 01-status 02-gatilhos 03-lightbar 04-rumble
    05-perfis 06-sistema 07-emulacao 08-navegacao-dsx
)

capturar() { $CAPTURA_CMD; }

aba_atual() { "$AQUI/aba_ativa.sh" "$1" | cut -d' ' -f1; }

ir_para() {  # ir_para <índice-alvo> -> imprime o caminho da captura, ou vazio
    local alvo="$1" tentativas=0 imagem atual
    while [ "$tentativas" -lt 14 ]; do
        imagem="$(capturar)"
        atual="$(aba_atual "$imagem")"
        if [ "$atual" = "$alvo" ]; then
            echo "$imagem"
            return 0
        fi
        if [ "$atual" -lt "$alvo" ] 2>/dev/null; then
            wtype -M ctrl -k Next -m ctrl 2>/dev/null || true
        else
            wtype -M ctrl -k Prior -m ctrl 2>/dev/null || true
        fi
        # 0,45 s é o piso: abaixo disso o compositor perde a tecla.
        sleep 0.7
        tentativas=$((tentativas + 1))
    done
    echo ""
    return 1
}

for indice in $(seq 0 8); do
    imagem="$(ir_para "$indice")"
    if [ -n "$imagem" ]; then
        cp "$imagem" "$DESTINO/aba-${NOMES[$indice]}.png"
        echo "  ok   ${NOMES[$indice]}"
    else
        echo "  FALHOU  ${NOMES[$indice]}" >&2
    fi
done
