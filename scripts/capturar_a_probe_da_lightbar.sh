#!/usr/bin/env bash
set -uo pipefail

DESTINO="${HEFESTO_CAPTURA_DIR:-/tmp/hefesto-probe-lightbar}"
BRACO="${1:-}"
SEGUNDOS="${2:-40}"
DONO_UID="${SUDO_UID:-0}"
DONO_GID="${SUDO_GID:-0}"

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
    local modo
    modo=$(stat -c %a "$DESTINO") || return 1
    if (( 8#$modo & 8#002 )); then
        echo "erro: em $DESTINO qualquer um escreve (modo $modo); recuso escrever nele como root." >&2
        return 1
    fi
    rm -f "$DESTINO/probe-limpo.snoop" "$DESTINO/probe-sujo.snoop"
}

mostrar() {
    if [ -f "$1" ]; then
        cat "$1"
    else
        echo "  (sem leitura: $1 — rode o braço com sudo)"
    fi
}

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
