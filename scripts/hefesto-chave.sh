#!/usr/bin/env bash
set -euo pipefail

APLICATIVOS="${HOME}/.local/share/applications"

UNITS=(
    "hefesto-dualsense4unix.service"
    "hefesto-dualsense4unix-storm-watch.service"
    "hefesto-dualsense4unix-gui-hotplug.service"
    "hefesto-steam-input-guard.path"
    "hefesto-steam-input-guard.timer"
    "hefesto-steam-input-guard.service"
)

uso() {
    cat <<'FIM'
uso:
  hefesto-chave off       desliga o Hefesto por completo
  hefesto-chave on        religa, exatamente como estava
  hefesto-chave estado    o que está ligado, e desde quando

Nada aqui pede sudo, e nada aqui apaga arquivo: `off` é inteiramente desfeito
por `on`.
FIM
}

SLUG="hefesto-dualsense4unix"
CONFIG="${XDG_CONFIG_HOME:-${HOME}/.config}/${SLUG}"
DESKTOP="${APLICATIVOS}/${SLUG}.desktop"

existe_unit() {
    systemctl --user cat "$1" >/dev/null 2>&1
}

estado() {
    local chave="${CONFIG}/DESLIGADO-pela-chave.flag"

    printf '\n== Hefesto ==\n'
    if [[ -f "$chave" ]]; then
        printf '  chave     : DESLIGADO\n'
        sed 's/^/              /' "$chave"
    else
        printf '  chave     : ligado (sem chave posta)\n'
    fi

    local achou=0 u
    for u in "${UNITS[@]}"; do
        existe_unit "$u" || continue
        achou=1
        printf '  %-42s %-10s %s\n' "$u" \
            "$(systemctl --user is-enabled "$u" 2>&1 | head -1)" \
            "$(systemctl --user is-active "$u" 2>&1 | head -1)"
    done
    [[ $achou -eq 1 ]] || printf '  (nenhuma unit instalada)\n'

    if [[ -f "$DESKTOP" ]]; then
        if grep -qx 'Hidden=true' "$DESKTOP"; then
            printf '  atalho    : escondido da dock\n'
        else
            printf '  atalho    : visível\n'
        fi
    else
        printf '  atalho    : não instalado\n'
    fi

    printf '\n== a camada da MÁQUINA (a chave nunca a toca) ==\n'
    local s
    for s in hefesto-hidraw-broker.socket hefesto-bt-agent.service; do
        printf '  %-38s %s\n' "$s" "$(systemctl is-active "$s" 2>&1 | head -1)"
    done
    printf '  regras udev em /etc/udev/rules.d : %s\n' \
        "$(find /etc/udev/rules.d -maxdepth 1 -name '*hefesto*' -o -maxdepth 1 \
            -name '*ps5*' -o -maxdepth 1 -name '*dualsense*' 2>/dev/null | wc -l)"
    printf '\n'
}

desligar() {
    local u

    printf 'desligando o Hefesto\n\n'

    for u in "${UNITS[@]}"; do
        if ! existe_unit "$u"; then
            printf '  %-42s (não instalada, pulei)\n' "$u"
            continue
        fi
        systemctl --user stop "$u" >/dev/null 2>&1 || true
        systemctl --user disable "$u" >/dev/null 2>&1 || true
        systemctl --user mask "$u" >/dev/null 2>&1 || true
        printf '  %-42s parada, desabilitada e mascarada\n' "$u"
    done

    mkdir -p "$CONFIG"
    {
        printf 'desligado em %s por hefesto-chave\n' "$(date -Is)"
        printf 'para religar:  hefesto-chave on\n'
    } > "${CONFIG}/DESLIGADO-pela-chave.flag"
    printf '  chave posta em %s\n' "${CONFIG}/DESLIGADO-pela-chave.flag"

    local runtime="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    local pid f
    for f in daemon gui; do
        local arq="${runtime}/${SLUG}/${f}.pid"
        [[ -f "$arq" ]] || continue
        pid="$(head -1 "$arq" 2>/dev/null | tr -dc '0-9')"
        [[ -n "$pid" ]] || continue
        if kill -TERM "$pid" 2>/dev/null; then
            printf '  SIGTERM em %s (pid %s, lido de %s)\n' "$f" "$pid" "$arq"
        fi
    done

    if [[ -f "$DESKTOP" ]] && ! grep -qx 'Hidden=true' "$DESKTOP"; then
        printf 'Hidden=true\n' >> "$DESKTOP"
        printf '  atalho escondido da dock (%s)\n' "$(basename "$DESKTOP")"
    fi
    command -v update-desktop-database >/dev/null 2>&1 &&
        update-desktop-database -q "$APLICATIVOS" 2>/dev/null || true

    printf '\npronto. Para religar exatamente como estava:\n'
    printf '    hefesto-chave on\n'
}

religar() {
    local u

    printf 'religando o Hefesto\n\n'

    rm -f "${CONFIG}/DESLIGADO-pela-chave.flag"
    printf '  chave retirada\n'

    if [[ -f "$DESKTOP" ]]; then
        sed -i '/^Hidden=true$/d' "$DESKTOP"
        printf '  atalho de volta à dock\n'
    fi
    command -v update-desktop-database >/dev/null 2>&1 &&
        update-desktop-database -q "$APLICATIVOS" 2>/dev/null || true

    for u in "${UNITS[@]}"; do
        systemctl --user unmask "$u" >/dev/null 2>&1 || true
        if ! existe_unit "$u"; then
            printf '  %-42s (não instalada, pulei)\n' "$u"
            continue
        fi
        if systemctl --user is-enabled "$u" 2>/dev/null | grep -qx 'static'; then
            printf '  %-42s desmascarada (static, sem enable)\n' "$u"
            continue
        fi
        systemctl --user enable "$u" >/dev/null 2>&1 || true
        systemctl --user start "$u" >/dev/null 2>&1 || true
        printf '  %-42s desmascarada, habilitada e no ar\n' "$u"
    done

    printf '\npronto. Confira com:  hefesto-chave estado\n'
}

case "${1:-}" in
    estado|status|"") estado ;;
    off|desligar)     desligar ;;
    on|religar)       religar ;;
    -h|--help|ajuda)  uso ;;
    *) uso; exit 2 ;;
esac
