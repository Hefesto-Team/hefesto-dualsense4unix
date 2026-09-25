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
# Grava um `.snoop` com `btmon` por braço e decodifica dele, na hora, só o que
# decide a questão: os reports de SAÍDA (0x31) e, dentro deles, os bytes de
# lightbar e os bits que os autorizam. O `comparar` imprime os dois lado a lado.
# A leitura é a do `scripts/ensaios/o_formato_btsnoop.py`, que lê o arquivo
# binário: o `awk` sobre o `btmon -r` que estava aqui esperava um deslocamento
# de oito dígitos que o `btmon` não imprime, e não lia nada.
#
# A CAPTURA NASCE FECHADA E NÃO FICA (AS-CAPTURAS-DE-RADIO-NASCEM-FECHADAS-01):
# se um controle reconecta durante a gravação, o `btmon` grava a chave de
# pareamento em claro. Ela nasce 0600 num diretório 0700 do root, é lida logo
# depois de gravada e sai; o que fica em $DESTINO é só a leitura dos reports
# 0x31, entregue a quem chamou o `sudo` — e é por isso que o `comparar` roda
# sem root.
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
BRACO="${1:-}"
SEGUNDOS="${2:-40}"
# Quem chamou o `sudo` é quem lê a leitura depois, sem root.
DONO_UID="${SUDO_UID:-0}"
DONO_GID="${SUDO_GID:-0}"

# $DESTINO recebe só a leitura, escrita pelo root. Um link, um diretório de
# outro usuário, ou um em que qualquer um escreve, é recusado: o root não
# escreve por ali.
preparar_destino() {
    if [ -L "$DESTINO" ] || { [ -e "$DESTINO" ] && [ ! -d "$DESTINO" ]; }; then
        echo "erro: $DESTINO não é um diretório comum; recuso escrever nele como root." >&2
        return 1
    fi
    if [ ! -d "$DESTINO" ]; then
        install -d -m 0700 -o "$DONO_UID" -g "$DONO_GID" "$DESTINO" || return 1
    fi
    local dono
    dono=$(stat -c %u "$DESTINO") || return 1
    if [ "$dono" != "0" ] && [ "$dono" != "$DONO_UID" ]; then
        echo "erro: $DESTINO é de outro usuário (uid $dono); recuso escrever nele como root." >&2
        return 1
    fi
    # Num diretório em que qualquer um escreve (o próprio /tmp, uma pasta 0777),
    # outro usuário troca a leitura por um link entre o `rm` e a escrita do root.
    local modo
    modo=$(stat -c %a "$DESTINO") || return 1
    if (( 8#$modo & 8#002 )); then
        echo "erro: em $DESTINO qualquer um escreve (modo $modo); recuso escrever nele como root." >&2
        return 1
    fi
    # A versão anterior deixava a captura crua aqui, 0644 e do root.
    rm -f "$DESTINO/probe-limpo.snoop" "$DESTINO/probe-sujo.snoop"
}

mostrar() {
    if [ -f "$1" ]; then
        cat "$1"
    else
        echo "  (sem leitura: $1 — rode o braço com sudo)"
    fi
}

# Só biblioteca padrão, e isolado (`-I`): roda como root, e não importa nada
# da casa nem escreve bytecode na árvore.
FORMATO="$(dirname "$(readlink -f "$0")")/ensaios/o_formato_btsnoop.py"
decodificar() {
    local arquivo="$1"
    [ -f "$arquivo" ] || { echo "  (sem captura: $arquivo)"; return; }
    python3 -I -B "$FORMATO" --reports-de-saida "$arquivo"
}

case "$BRACO" in
limpo|sujo)
    if [ "$(id -u)" -ne 0 ]; then
        echo "erro: precisa de root — btmon lê o socket de monitor do BlueZ." >&2
        echo "  sudo $0 $BRACO" >&2
        exit 1
    fi
    umask 077
    preparar_destino || exit 1
    PRIVADO=$(mktemp -d -t hefesto-probe-lightbar.XXXXXX) || exit 1
    trap 'rm -rf "$PRIVADO"' EXIT
    ARQ="$PRIVADO/probe-$BRACO.snoop"
    LEITURA="$DESTINO/probe-$BRACO.txt"
    echo "instrumento: btmon (socket de monitor do BlueZ)"
    echo "braço      : $BRACO"
    echo "captura    : $ARQ (0600, apagada depois de lida)"
    echo "leitura    : $LEITURA"
    echo
    echo "  quem tem hidraw aberto AGORA:"
    # A lista sai numa variável: o `achou=1` de dentro do laço morria na
    # subshell do `| sort`, e o «(nenhum)» saía mesmo com a Steam listada.
    donos=$(for p in /proc/[0-9]*/fd/*; do
        alvo=$(readlink "$p" 2>/dev/null) || continue
        case "$alvo" in *hidraw*)
            pid=$(echo "$p" | cut -d/ -f3)
            echo "    $(cat "/proc/$pid/comm" 2>/dev/null) -> $alvo"
        ;; esac
    done | sort -u)
    if [ -n "$donos" ]; then
        echo "$donos"
    else
        echo "    (nenhum)"
    fi
    echo
    echo "  gravando por ${SEGUNDOS}s — RECONECTE OS CONTROLES AGORA"
    timeout "$SEGUNDOS" btmon -w "$ARQ" >/dev/null 2>&1
    echo "  gravado: $(stat -c '%s bytes, modo %a' "$ARQ" 2>/dev/null || echo 'nada')"
    rm -f "$LEITURA"
    decodificar "$ARQ" > "$LEITURA"
    chown "$DONO_UID:$DONO_GID" "$LEITURA"
    rm -f "$ARQ"
    echo "  captura apagada: $ARQ"
    ;;
comparar)
    echo "=== reports de SAÍDA (0x31) no braço LIMPO ==="
    mostrar "$DESTINO/probe-limpo.txt"
    echo
    echo "=== reports de SAÍDA (0x31) no braço SUJO ==="
    mostrar "$DESTINO/probe-sujo.txt"
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
