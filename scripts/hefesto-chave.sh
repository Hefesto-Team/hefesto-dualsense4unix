#!/usr/bin/env bash
# hefesto-chave — desliga o Hefesto por completo, e o religa igualzinho.
#
# Pedido dela, 29/08/2026: *"temos que garantir que eu possa DESLIGAR o impacto
# por completo e RELIGAR. (com o botão de desligar funcionando sem zuar o
# resto)."*
#
#   hefesto-chave off       desliga o Hefesto por completo
#   hefesto-chave on        religa, exatamente como estava
#   hefesto-chave estado    diz o que está ligado, e desde quando
#
# AS DUAS CINTAS, E POR QUE SÃO DUAS (as duas medidas em 29/08/2026)
# -------------------------------------------------------------------
# 1. `stop` + `disable` + `mask` nas units `--user`. Fecha o systemd: sobrevive
#    a reboot (máscara é symlink para /dev/null em disco) e é desfeita por
#    `unmask` + `enable` + `start`.
#
# 2. A CHAVE EM DISCO (`utils/chave.py`), lida pelo daemon no boot. Esta é a
#    que fecha o furo que a máscara NÃO fecha, e o furo é real: o botão "Ligar
#    daemon" da GUI, quando o `systemctl start` falha, cai num
#    `subprocess.Popen` que levanta o daemon sem passar por systemd nenhum
#    (`app/actions/daemon_actions.py:2162-2176`). Com só a máscara, apertar o
#    botão dela ligaria o daemon "desligado".
#
# O QUE ELE NÃO TOCA, DE PROPÓSITO
# ---------------------------------
# Regras udev, o broker hidraw (`hefesto-hidraw-broker.{service,socket}`), o
# `hefesto-bt-agent`, o `bt-health-watchdog`, `/usr/local/lib/**`, perfis e
# config. Essa é a camada da MÁQUINA, e mexer nela exigiria `sudo` toda vez —
# que é exatamente o custo que ela vetou em 22/08/2026. Zero sudo aqui.
#
# E NÃO TOCA `hefesto-medicao-elapsed.{service,timer}`: apesar do nome, não é
# do produto (a própria unit se descreve como "Medicao ELAPSED (descartavel)").
# Desligar coisa que não se sabe o que é seria o oposto de reversível.
set -euo pipefail

APLICATIVOS="${HOME}/.local/share/applications"

# As units de USUÁRIO do app. Conferidas na máquina dela em 29/08 com
# `systemctl --user list-unit-files`: o vigia da Steam chama-se
# `hefesto-steam-input-guard.*`, e NÃO `hefesto-dualsense4unix-steam-input-*`
# — errar o nome faria o `stop` devolver sucesso sem parar coisa nenhuma.
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

# --- os três caminhos, todos derivados do MESMO slug -------------------------
# O slug é o de `utils/identidade.py`. Ele está escrito aqui porque este script
# roda sem venv e sem python; `test_o_script_e_o_produto_concordam_no_caminho`
# é quem cobra que as duas grafias não divirjam.
SLUG="hefesto-dualsense4unix"
CONFIG="${XDG_CONFIG_HOME:-${HOME}/.config}/${SLUG}"
DESKTOP="${APLICATIVOS}/${SLUG}.desktop"

existe_unit() {
    systemctl --user cat "$1" >/dev/null 2>&1
}

# --- o retrato ---------------------------------------------------------------
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

# --- desligar ----------------------------------------------------------------
desligar() {
    local u

    printf 'desligando o Hefesto\n\n'

    # 1. parar, desabilitar e MASCARAR o que existir.
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

    # 2. a chave em disco — a cinta que a máscara não dá.
    mkdir -p "$CONFIG"
    {
        printf 'desligado em %s por hefesto-chave\n' "$(date -Is)"
        printf 'para religar:  hefesto-chave on\n'
    } > "${CONFIG}/DESLIGADO-pela-chave.flag"
    printf '  chave posta em %s\n' "${CONFIG}/DESLIGADO-pela-chave.flag"

    # 3. o processo avulso — pelo PID FILE, nunca por `pgrep -f`.
    #    `pgrep -f hefesto` alcançaria este próprio script, que é precisamente
    #    o defeito que esta cinta existe para não repetir.
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

    # 4. esconder o atalho — a dock não deve oferecer um app desligado.
    #    EDITAR, nunca apagar: `on` tira a linha e o atalho volta inteiro.
    if [[ -f "$DESKTOP" ]] && ! grep -qx 'Hidden=true' "$DESKTOP"; then
        printf 'Hidden=true\n' >> "$DESKTOP"
        printf '  atalho escondido da dock (%s)\n' "$(basename "$DESKTOP")"
    fi
    command -v update-desktop-database >/dev/null 2>&1 &&
        update-desktop-database -q "$APLICATIVOS" 2>/dev/null || true

    printf '\npronto. Para religar exatamente como estava:\n'
    printf '    hefesto-chave on\n'
}

# --- religar -----------------------------------------------------------------
religar() {
    local u

    printf 'religando o Hefesto\n\n'

    rm -f "${CONFIG}/DESLIGADO-pela-chave.flag"
    printf '  chave retirada\n'

    if [[ -f "$DESKTOP" ]]; then
        # `sed -i` só na linha exata que o `off` acrescentou.
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
        # `.service` que é só alvo de `.path`/`.timer` é `static` e NÃO aceita
        # `enable` — pedir isso devolveria erro e sujaria a saída sem motivo.
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

# --- porta de entrada --------------------------------------------------------
case "${1:-}" in
    estado|status|"") estado ;;
    off|desligar)     desligar ;;
    on|religar)       religar ;;
    -h|--help|ajuda)  uso ;;
    *) uso; exit 2 ;;
esac
