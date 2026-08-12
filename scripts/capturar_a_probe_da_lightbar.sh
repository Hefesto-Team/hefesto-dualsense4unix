#!/usr/bin/env bash
# capturar_a_probe_da_lightbar.sh — quem manda apagar a barra na probe?
#
# POR QUE ESTE INSTRUMENTO EXISTE
# -------------------------------
# Em 11-12/08/2026, com quatro DualSense na mesa dela, ficou medido que uma
# conexão de rádio nasce com a lightbar ACESA quando ninguém tem o hidraw
# aberto, e nasce APAGADA quando a Steam está viva. Também ficou medido que o
# firmware GUARDA a cor entre conexões — um controle voltou de uma desconexão
# completa exibindo o magenta escrito minutos antes. Logo, "apagada" não é
# esquecimento: alguém MANDA apagar, e este instrumento lê o fio para ver quem.
#
# Suspeitos já ELIMINADOS por ensaio, para ninguém remedi-los: o report 0x08
# (removido do produto em 04/08 e a barra travava igual), o keepalive do daemon
# (com o daemon parado o comportamento não muda), o `lightbar_reassert_skip_cache`,
# a revisão de hardware (as três da mesa se comportaram igual em ensaio limpo), a
# ordem de subida, a falha de feature na probe (houve falha numa instância que
# obedeceu) e a personalização por controle (com a configuração vazia o defeito
# continua).
#
# O QUE ELE FAZ
# -------------
# Grava dois `.snoop` com `btmon`, um por braço, e decodifica de cada um só o
# que decide a questão: os reports de SAÍDA (0x31) e, dentro deles, os bytes de
# lightbar e os bits que os autorizam. Depois imprime os dois lado a lado.
#
#   braço LIMPO  — nenhum processo com o hidraw aberto durante a probe
#   braço SUJO   — a Steam viva durante a probe
#
# A leitura é a diferença: um report presente no sujo e ausente no limpo é o
# que apaga a barra.
#
# OFFSETS, do fonte do driver desta máquina
# -----------------------------------------
# No envelope BT (report 0x31, 78 bytes): valid_flag1 = byte 4,
# valid_flag2 = byte 41, lightbar_setup = byte 44, R/G/B = bytes 47/48/49.
# Ver assets/dkms/hid-playstation/hid-playstation.c e
# docs/protocol/driver-hid-playstation.md.
#
# Uso (precisa de root — btmon lê o socket de monitor do BlueZ):
#   sudo scripts/capturar_a_probe_da_lightbar.sh limpo
#   sudo scripts/capturar_a_probe_da_lightbar.sh sujo
#   scripts/capturar_a_probe_da_lightbar.sh comparar      # sem root
set -uo pipefail

DESTINO="${HEFESTO_CAPTURA_DIR:-/tmp/hefesto-probe-lightbar}"
mkdir -p "$DESTINO"
BRACO="${1:-}"
SEGUNDOS="${2:-40}"

decodificar() {
    local arquivo="$1"
    [ -f "$arquivo" ] || { echo "  (sem captura: $arquivo)"; return; }
    btmon -r "$arquivo" 2>/dev/null | awk '
        /ACL Data TX/ { emissao = 1 }
        /ACL Data RX/ { emissao = 0 }
        emissao && /^ *[0-9a-f]{8} / {
            linha = $0
            sub(/^ *[0-9a-f]{8} +/, "", linha)
            sub(/ +\.\..*$/, "", linha)
            bytes = bytes linha " "
        }
        /^> |^< / {
            if (bytes ~ /^a2 31|^31 /) { print "    " bytes }
            bytes = ""
        }
    ' | head -40
}

case "$BRACO" in
limpo|sujo)
    if [ "$(id -u)" -ne 0 ]; then
        echo "erro: precisa de root — btmon lê o socket de monitor do BlueZ." >&2
        echo "  sudo $0 $BRACO" >&2
        exit 1
    fi
    ARQ="$DESTINO/probe-$BRACO.snoop"
    echo "instrumento: btmon (socket de monitor do BlueZ)"
    echo "braço      : $BRACO"
    echo "saída      : $ARQ"
    echo
    echo "  quem tem hidraw aberto AGORA:"
    achou=0
    for p in /proc/[0-9]*/fd/*; do
        alvo=$(readlink "$p" 2>/dev/null) || continue
        case "$alvo" in *hidraw*)
            pid=$(echo "$p" | cut -d/ -f3)
            echo "    $(cat "/proc/$pid/comm" 2>/dev/null) -> $alvo"
            achou=1
        ;; esac
    done | sort -u
    [ "$achou" = "0" ] && echo "    (nenhum)"
    echo
    echo "  gravando por ${SEGUNDOS}s — RECONECTE OS CONTROLES AGORA"
    timeout "$SEGUNDOS" btmon -w "$ARQ" >/dev/null 2>&1
    echo "  gravado: $(stat -c %s "$ARQ" 2>/dev/null || echo 0) bytes"
    ;;
comparar)
    echo "=== reports de SAÍDA (0x31) no braço LIMPO ==="
    decodificar "$DESTINO/probe-limpo.snoop"
    echo
    echo "=== reports de SAÍDA (0x31) no braço SUJO ==="
    decodificar "$DESTINO/probe-sujo.snoop"
    echo
    echo "Leitura: no envelope BT, valid_flag1 = byte 4 (bit 0x04 autoriza a cor),"
    echo "valid_flag2 = byte 41 (bit 0x02 é o LIGHTBAR_SETUP), lightbar_setup = byte 44,"
    echo "e R/G/B = bytes 47/48/49. Um report presente só no sujo é o que apaga."
    ;;
*)
    echo "uso: $0 {limpo|sujo} [segundos]   (com sudo)"
    echo "     $0 comparar                  (sem sudo)"
    exit 2
    ;;
esac
