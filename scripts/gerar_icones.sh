#!/usr/bin/env bash
# Gera TODOS os ícones do projeto a partir do SVG canônico.
#
# Pedido dela, literal, em 01/08/2026:
#   "então o PNG tem que tá automatizado pra sempre refletir o SVG — tipo, se eu
#    voltar a abrir e mudar o desenho dele, eu quero ver isso refletido em tudo
#    que faça uso dele"
#
#   uso:  scripts/gerar_icones.sh            # gera e sobrescreve
#         scripts/gerar_icones.sh --check    # só confere (não escreve nada)
#
# QUEM RODA O `--check` (corrigido em 03/08/2026 — ÍCONE-VIVO-01)
# ---------------------------------------------------------------
# Esta linha afirmava "é o que o CI roda", e era FALSO: `grep gerar_icones` em
# `.github/workflows/` não devolvia nada. A proteção existia só de lado, pelo
# `tests/unit/test_icones_refletem_o_svg.py`, que chama este script de dentro
# do pytest — funcionava, mas por um caminho diferente do declarado, e só
# avisava minutos depois do commit. É a família do PORTÃO-VIVO-01: o gate que
# se anuncia e não roda.
#
# Hoje rodam, de verdade, três:
#   1. o hook `icones-refletem-o-svg` do `.pre-commit-config.yaml` (avisa ANTES
#      do commit, que é onde o gesto acontece);
#   2. o job `icones` do `.github/workflows/ci.yml`;
#   3. o teste da suíte, que continua como rede.
#
# A FONTE CANÔNICA É UMA SÓ: assets/hefesto-logo.svg
# Mexeu no desenho? Rode isto. Todos os derivados nascem dele.
#
# O QUE ESTE SCRIPT NÃO GERA, E POR QUÊ — 07/08/2026 (APPLET-MONOCROMÁTICO-01)
# ---------------------------------------------------------------------------
# `assets/simbolico/*.svg` (o ícone do painel) fica DE FORA, de propósito, e
# isso é decisão, não esquecimento. O simbólico não é derivável por escala da
# logo colorida: a logo cheia a 20 px — que é o tamanho real do painel dela —
# vira borrão, e o formato exige o oposto do que a logo é (uma cor só,
# acromática, fundo transparente, contorno feito de preenchimento). Rodar
# `compare -metric AE` entre ele e a logo reprovaria SEMPRE, por construção.
#
# Mas ele NÃO ficou sem dono, que é como o `-symbolic` antigo chegou a 07/08
# instalado sob um nome que ninguém pedia. Quem o trava:
#   - `tests/unit/test_simbolico_do_painel.py` — grade 16x16, uma cor só,
#     acromática e clara, sem `currentColor`, sem `stroke`, sem fundo opaco, e
#     o contrato de nome (`-symbolic`) em tray.py, app.rs e no .desktop;
#   - `scripts/check_packaging_parity.sh` — os quatro formatos instalam o
#     arquivo, e o desenho da bandeja e o do applet são o mesmo.
#
# O QUE ESTE SCRIPT CUROU
# -----------------------
# Antes dele, o `install.sh` copiava `assets/appimage/Hefesto-Dualsense4Unix.png`
# — um arquivo que NÃO EXISTE nesta árvore. O `cp -f` falhava em silêncio
# (o `|| true` do passo engolia), e o ícone que aparecia no sistema vinha, por
# acidente, do PNG do applet COSMIC. Ou seja: havia DOIS caminhos e o que a
# documentação descrevia era o quebrado.
#
# O comentário do `install.sh` também mentia por estar velho: dizia que o SVG
# era "um PLACEHOLDER simples (chama laranja + texto HEFESTO), não a logo real".
# Medido em 01/08: o SVG TEM o martelo, a bigorna e a chama, e gera um PNG
# indistinguível do que estava versionado. O placeholder foi substituído em
# algum momento e ninguém atualizou o comentário.
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$AQUI"

SVG="assets/hefesto-logo.svg"
CHECK=0
[[ "${1:-}" == "--check" ]] && CHECK=1

if [[ ! -f "$SVG" ]]; then
    echo "ERRO: $SVG não existe — é a fonte canônica de todos os ícones." >&2
    exit 1
fi

if ! command -v rsvg-convert >/dev/null 2>&1; then
    echo "ERRO: rsvg-convert ausente. Instale: sudo apt install librsvg2-bin" >&2
    exit 1
fi

# Os destinos, e quem consome cada um. Formato: caminho:tamanho
#
# O ícone de 256x256 do applet é o que o `install.sh` copia para
# /usr/share/icons e o que o COSMIC mostra na barra — é o mais visível dos três.
DESTINOS=(
    "packaging/cosmic-applet/data/icons/hicolor/256x256/apps/com.vitoriamaria.HefestoDualsense4Unix.png:256"
    "assets/appimage/Hefesto-Dualsense4Unix.png:256"
)

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

divergiu=0
for entrada in "${DESTINOS[@]}"; do
    destino="${entrada%%:*}"
    tamanho="${entrada##*:}"
    gerado="$TMP/$(basename "$destino")"

    rsvg-convert -w "$tamanho" -h "$tamanho" "$SVG" -o "$gerado"

    if [[ $CHECK -eq 1 ]]; then
        # A comparação é por PIXEL, não por bytes: dois PNGs do mesmo desenho
        # podem diferir em metadados (data, compressão) sem diferir na tela.
        if [[ ! -f "$destino" ]]; then
            echo "  FALTA    $destino"
            divergiu=1
        elif command -v compare >/dev/null 2>&1 &&
             ! compare -metric AE "$gerado" "$destino" null: 2>&1 |
               grep -qE '^0( |$)'; then
            echo "  DIVERGE  $destino (o SVG mudou e o PNG não acompanhou)"
            divergiu=1
        else
            echo "  ok       $destino"
        fi
    else
        mkdir -p "$(dirname "$destino")"
        cp -f "$gerado" "$destino"
        echo "  gerado   $destino  (${tamanho}x${tamanho})"
    fi
done

if [[ $CHECK -eq 1 ]]; then
    if [[ $divergiu -eq 1 ]]; then
        echo ""
        echo "Os ícones não refletem o SVG. Rode: scripts/gerar_icones.sh" >&2
        exit 1
    fi
    echo ""
    echo "OK: todos os ícones refletem $SVG."
else
    echo ""
    echo "Todos os ícones vêm de $SVG."
    echo "Para o sistema pegar o ícone novo, reinstale (./install.sh --yes) ou:"
    echo "  gtk-update-icon-cache -f ~/.local/share/icons/hicolor"
fi
