#!/usr/bin/env bash
# hefesto-chave — desliga um Hefesto por completo, e o religa igualzinho.
#
# Pedido dela, 29/08/2026: *"temos que garantir que eu possa DESLIGAR o impacto
# do outro Hefesto por completo e RELIGAR ele. Não quero manchar o nosso novo
# produto. E quero garantir que ele funcione enquanto eu tenho a versão estável
# instalada (com o botão de desligar funcionando sem zuar o resto)."*
#
#   hefesto-chave estavel off    desliga o Hefesto ESTÁVEL
#   hefesto-chave estavel on     religa o Hefesto ESTÁVEL
#   hefesto-chave dev off|on     idem, para o de desenvolvimento
#   hefesto-chave estado         diz quem está ligado, e desde quando
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
# config. Essa é a camada COMPARTILHADA: o app de desenvolvimento PRECISA dela
# para enxergar o aparelho, e mexer nela exigiria `sudo` toda vez — que é
# exatamente o custo que ela vetou em 22/08/2026. Zero sudo aqui.
#
# E NÃO TOCA `hefesto-medicao-elapsed.{service,timer}`: apesar do nome, não é
# do produto (a própria unit se descreve como "Medicao ELAPSED (descartavel)").
# Desligar coisa que não se sabe o que é seria o oposto de reversível.
set -euo pipefail

APLICATIVOS="${HOME}/.local/share/applications"

# As units de USUÁRIO de cada casa. Conferidas na máquina dela em 29/08 com
# `systemctl --user list-unit-files`: o vigia da Steam chama-se
# `hefesto-steam-input-guard.*`, e NÃO `hefesto-dualsense4unix-steam-input-*`
# — errar o nome faria o `stop` devolver sucesso sem parar coisa nenhuma.
UNITS_ESTAVEL=(
    "hefesto-dualsense4unix.service"
    "hefesto-dualsense4unix-storm-watch.service"
    "hefesto-dualsense4unix-gui-hotplug.service"
    "hefesto-steam-input-guard.path"
    "hefesto-steam-input-guard.timer"
    "hefesto-steam-input-guard.service"
)
UNITS_DEV=(
    "hefesto-dev-dualsense4unix.service"
)

uso() {
    cat <<'FIM'
uso:
  hefesto-chave estavel off    desliga o Hefesto estável por completo
  hefesto-chave estavel on     religa o Hefesto estável
  hefesto-chave dev off|on     o mesmo, para o Hefesto de desenvolvimento
  hefesto-chave estado         quem está ligado, e desde quando

Nada aqui pede sudo, e nada aqui apaga arquivo: `off` é inteiramente desfeito
por `on`.
FIM
}

# --- onde mora a config de cada casa ----------------------------------------
config_de() {
    local casa="$1" base="${XDG_CONFIG_HOME:-${HOME}/.config}"
    case "$casa" in
        estavel) printf '%s/hefesto-dualsense4unix\n' "$base" ;;
        dev)     printf '%s/hefesto-dev-dualsense4unix\n' "$base" ;;
        *)       return 1 ;;
    esac
}

desktop_de() {
    case "$1" in
        estavel) printf '%s/hefesto-dualsense4unix.desktop\n' "$APLICATIVOS" ;;
        dev)     printf '%s/hefesto-dev-dualsense4unix.desktop\n' "$APLICATIVOS" ;;
        *)       return 1 ;;
    esac
}

units_de() {
    case "$1" in
        estavel) printf '%s\n' "${UNITS_ESTAVEL[@]}" ;;
        dev)     printf '%s\n' "${UNITS_DEV[@]}" ;;
        *)       return 1 ;;
    esac
}

existe_unit() {
    systemctl --user cat "$1" >/dev/null 2>&1
}

# --- o retrato ---------------------------------------------------------------
estado() {
    local casa
    for casa in estavel dev; do
        local cfg chave desk
        cfg="$(config_de "$casa")"
        chave="${cfg}/DESLIGADO-pela-chave.flag"
        desk="$(desktop_de "$casa")"

        printf '\n== Hefesto %s ==\n' "$casa"
        if [[ -f "$chave" ]]; then
            printf '  chave     : DESLIGADO\n'
            sed 's/^/              /' "$chave"
        else
            printf '  chave     : ligado (sem chave posta)\n'
        fi

        local achou=0 u
        while IFS= read -r u; do
            existe_unit "$u" || continue
            achou=1
            printf '  %-42s %-10s %s\n' "$u" \
                "$(systemctl --user is-enabled "$u" 2>&1 | head -1)" \
                "$(systemctl --user is-active "$u" 2>&1 | head -1)"
        done < <(units_de "$casa")
        [[ $achou -eq 1 ]] || printf '  (nenhuma unit desta casa instalada)\n'

        if [[ -f "$desk" ]]; then
            if grep -qx 'Hidden=true' "$desk"; then
                printf '  atalho    : escondido da dock\n'
            else
                printf '  atalho    : visível\n'
            fi
        else
            printf '  atalho    : não instalado\n'
        fi
    done

    printf '\n== a camada COMPARTILHADA (a chave nunca a toca) ==\n'
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
    local casa="$1" cfg desk u
    cfg="$(config_de "$casa")" || { uso; exit 2; }
    desk="$(desktop_de "$casa")"

    printf 'desligando o Hefesto %s\n\n' "$casa"

    # 1. parar, desabilitar e MASCARAR o que existir.
    while IFS= read -r u; do
        if ! existe_unit "$u"; then
            printf '  %-42s (não instalada, pulei)\n' "$u"
            continue
        fi
        systemctl --user stop "$u" >/dev/null 2>&1 || true
        systemctl --user disable "$u" >/dev/null 2>&1 || true
        systemctl --user mask "$u" >/dev/null 2>&1 || true
        printf '  %-42s parada, desabilitada e mascarada\n' "$u"
    done < <(units_de "$casa")

    # 2. a chave em disco — a cinta que a máscara não dá.
    mkdir -p "$cfg"
    {
        printf 'desligado em %s por hefesto-chave\n' "$(date -Is)"
        printf 'para religar:  hefesto-chave %s on\n' "$casa"
    } > "${cfg}/DESLIGADO-pela-chave.flag"
    printf '  chave posta em %s\n' "${cfg}/DESLIGADO-pela-chave.flag"

    # 3. o processo avulso — pelo PID FILE, nunca por `pgrep -f`.
    #    `pgrep -f hefesto` alcançaria o OUTRO Hefesto (e este script), que é
    #    precisamente o defeito que esta leva existe para não repetir.
    local runtime="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    local slug pid f
    case "$casa" in
        estavel) slug="hefesto-dualsense4unix" ;;
        dev)     slug="hefesto-dev-dualsense4unix" ;;
    esac
    for f in daemon gui; do
        local arq="${runtime}/${slug}/${f}.pid"
        [[ -f "$arq" ]] || continue
        pid="$(head -1 "$arq" 2>/dev/null | tr -dc '0-9')"
        [[ -n "$pid" ]] || continue
        if kill -TERM "$pid" 2>/dev/null; then
            printf '  SIGTERM em %s (pid %s, lido de %s)\n' "$f" "$pid" "$arq"
        fi
    done

    # 4. esconder o atalho — a dock não deve oferecer um app desligado.
    #    EDITAR, nunca apagar: `on` tira a linha e o atalho volta inteiro.
    if [[ -f "$desk" ]] && ! grep -qx 'Hidden=true' "$desk"; then
        printf 'Hidden=true\n' >> "$desk"
        printf '  atalho escondido da dock (%s)\n' "$(basename "$desk")"
    fi
    command -v update-desktop-database >/dev/null 2>&1 &&
        update-desktop-database -q "$APLICATIVOS" 2>/dev/null || true

    printf '\npronto. Para religar exatamente como estava:\n'
    printf '    hefesto-chave %s on\n' "$casa"
}

# --- religar -----------------------------------------------------------------
religar() {
    local casa="$1" cfg desk u
    cfg="$(config_de "$casa")" || { uso; exit 2; }
    desk="$(desktop_de "$casa")"

    printf 'religando o Hefesto %s\n\n' "$casa"

    rm -f "${cfg}/DESLIGADO-pela-chave.flag"
    printf '  chave retirada\n'

    if [[ -f "$desk" ]]; then
        # `sed -i` só na linha exata que o `off` acrescentou.
        sed -i '/^Hidden=true$/d' "$desk"
        printf '  atalho de volta à dock\n'
    fi
    command -v update-desktop-database >/dev/null 2>&1 &&
        update-desktop-database -q "$APLICATIVOS" 2>/dev/null || true

    while IFS= read -r u; do
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
    done < <(units_de "$casa")

    printf '\npronto. Confira com:  hefesto-chave estado\n'
}

# --- porta de entrada --------------------------------------------------------
case "${1:-}" in
    estado|status|"") estado ;;
    estavel|dev)
        case "${2:-}" in
            off|desligar) desligar "$1" ;;
            on|religar)   religar "$1" ;;
            *) uso; exit 2 ;;
        esac
        ;;
    -h|--help|ajuda) uso ;;
    *) uso; exit 2 ;;
esac
