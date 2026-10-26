#!/bin/sh

set -u

override_de_dll_valido() {
    od_resto="$1;"
    [ -n "$1" ] || return 1
    od_viu=0
    while [ -n "$od_resto" ]; do
        od_entrada="${od_resto%%;*}"
        od_resto="${od_resto#*;}"
        [ -n "$od_entrada" ] || continue
        od_nomes="${od_entrada%%=*}"
        case "$od_entrada" in *=*) ;; *) return 1 ;; esac
        od_modo="${od_entrada#*=}"
        case "$od_modo" in n|n,b|b|d) ;; *) return 1 ;; esac
        case "$od_nomes" in
            ''|,*|*,|*,,*|*[!A-Za-z0-9_.,-]*) return 1 ;;
        esac
        od_viu=1
    done
    [ "$od_viu" = 1 ]
}

receita_descartada() {
    if command -v logger >/dev/null 2>&1; then
        logger -t hefesto-launch "receita de ambiente descartada: $1" >/dev/null 2>&1 || true
    fi
}

receita_de_dll() {
    override_de_dll_valido "$1" && return 0
    receita_descartada "WINEDLLOVERRIDES fora da forma nome=n|n,b|b|d"
    return 1
}

override_pede_embutida() {
    case ";$1;" in *=b\;*) return 0 ;; esac
    return 1
}

pasta_da_receita() {
    case "$1" in
        @hefesto-wine) ;;
        *) receita_descartada "WINEDLLPATH fora do literal @hefesto-wine"; return 1 ;;
    esac
    [ -n "${HOME:-}" ] || return 1
    pr_pasta="$HOME/.local/share/hefesto-dualsense4unix/wine"
    for pr_dll in "$pr_pasta"/x86_64-windows/*.dll; do
        [ -f "$pr_dll" ] && { printf '%s\n' "$pr_pasta"; return 0; }
    done
    receita_descartada "a peça do Hefesto não está em $pr_pasta"
    return 1
}

receita_do_jogo() {
    case "$1" in */steam_app_*.env) ;; *) return 0 ;; esac
    rj_dll=""
    rj_pasta=""
    rj_quebrou=0
    while IFS= read -r rj_linha; do
        case "$rj_linha" in
            WINEDLLOVERRIDES=*)
                if receita_de_dll "${rj_linha#*=}"; then rj_dll="$rj_linha"; else rj_quebrou=1; fi ;;
            WINEDLLPATH=*)
                if rj_p="$(pasta_da_receita "${rj_linha#*=}")"; then
                    rj_pasta="WINEDLLPATH=$rj_p"
                else
                    rj_quebrou=1
                fi ;;
        esac
    done < "$1"
    [ -n "$rj_dll$rj_pasta" ] || [ "$rj_quebrou" = 1 ] || return 0
    if [ "${usuario_pos_dll:-0}" = 1 ] || [ -n "${WINEDLLOVERRIDES+x}" ] || [ -n "${WINEDLLPATH+x}" ]; then
        receita_descartada "o WINEDLLOVERRIDES ou o WINEDLLPATH já vem de quem lançou; o que ele pôs manda"
        return 0
    fi
    [ "$rj_quebrou" = 0 ] || return 0
    if [ -n "$rj_pasta" ] && [ -z "$rj_dll" ]; then
        receita_descartada "WINEDLLPATH sem o WINEDLLOVERRIDES do par"
        return 0
    fi
    if override_pede_embutida "${rj_dll#*=}" && [ -z "$rj_pasta" ]; then
        receita_descartada "=b sem a pasta da peça no WINEDLLPATH"
        return 0
    fi
    printf '%s\n' "$rj_dll"
    [ -z "$rj_pasta" ] || printf '%s\n' "$rj_pasta"
    return 0
}

decide_envs() {
    appid="${SteamAppId:-}"
    case "$appid" in
        ''|0) return 0 ;;
        *[!0-9]*) return 0 ;;
    esac

    state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/hefesto-dualsense4unix/launch_env"
    envfile="$state_dir/steam_app_${appid}.env"
    [ -f "$envfile" ] || envfile="$state_dir/default.env"
    [ -f "$envfile" ] || return 0

    command -v python3 >/dev/null 2>&1 || return 0

    runtime="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
    sock="$runtime/hefesto-dualsense4unix/hefesto-dualsense4unix.sock"
    [ -S "$sock" ] || return 0

    LD_LIBRARY_PATH= LD_PRELOAD= PYTHONPATH= PYTHONHOME= \
        python3 - "$sock" <<'PYEOF' >/dev/null 2>&1 || return 0
import json
import socket
import sys

s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(1.0)
s.connect(sys.argv[1])
s.sendall(
    json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": "daemon.status", "params": {}}
    ).encode("utf-8")
    + b"\n"
)
buf = b""
while not buf.endswith(b"\n"):
    chunk = s.recv(4096)
    if not chunk:
        raise SystemExit(1)
    buf += chunk
data = json.loads(buf.decode("utf-8"))
raise SystemExit(0 if isinstance(data, dict) and "result" in data else 1)
PYEOF

    while IFS= read -r line; do
        case "$line" in
            SDL_GAMECONTROLLER_IGNORE_DEVICES=*) printf '%s\n' "$line" ;;
            SDL_JOYSTICK_HIDAPI=*)               printf '%s\n' "$line" ;;
            SDL_GAMECONTROLLER_USE_BUTTON_LABELS=*) printf '%s\n' "$line" ;;
            SDL_ACCELEROMETER_AS_JOYSTICK=*)     printf '%s\n' "$line" ;;
            PROTON_DISABLE_HIDRAW=*)             printf '%s\n' "$line" ;;
            __GL_SHADER_DISK_CACHE=*)            printf '%s\n' "$line" ;;
            __GL_SHADER_DISK_CACHE_SKIP_CLEANUP=*) printf '%s\n' "$line" ;;
            PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE=*) printf '%s\n' "$line" ;;
            PROTON_ENABLE_MHWILDS_USB_AUDIO=*)   printf '%s\n' "$line" ;;
        esac
    done < "$envfile"
    receita_do_jogo "$envfile"
    return 0
}

record_last_run() {
    lr_appid="${SteamAppId:-}"
    case "$lr_appid" in
        ''|0) return 0 ;;
        *[!0-9]*) return 0 ;;
    esac
    lr_dir="${XDG_STATE_HOME:-$HOME/.local/state}/hefesto-dualsense4unix/launch_env"
    mkdir -p "$lr_dir" 2>/dev/null || return 0
    {
        printf 'appid=%s\n' "$lr_appid"
        printf 'epoch=%s\n' "$(date +%s)"
        printf 'pid=%s\n' "$$"
    } > "$lr_dir/last_run.tmp" 2>/dev/null || return 0
    mv -f "$lr_dir/last_run.tmp" "$lr_dir/last_run" 2>/dev/null || true
    return 0
}

record_last_exit() {
    le_dir="${XDG_STATE_HOME:-$HOME/.local/state}/hefesto-dualsense4unix/launch_env"
    mkdir -p "$le_dir" 2>/dev/null || return 0
    {
        printf 'epoch=%s\n' "$(date +%s)"
        printf 'pid=%s\n' "$$"
    } > "$le_dir/last_exit.tmp" 2>/dev/null || return 0
    mv -f "$le_dir/last_exit.tmp" "$le_dir/last_exit" 2>/dev/null || true
    return 0
}

registrar_audio_ks() {
    ra_appid="${SteamAppId:-}"
    case "$ra_appid" in
        *[!0-9]*) ra_appid="" ;;
    esac
    ra_dir="${XDG_STATE_HOME:-$HOME/.local/state}/hefesto-dualsense4unix/launch_env"
    mkdir -p "$ra_dir" 2>/dev/null || return 0
    {
        printf 'appid=%s\n' "$ra_appid"
        printf 'epoch=%s\n' "$(date +%s 2>/dev/null)"
        printf 'rc=%s\n' "$1"
        printf 'motivo=%s\n' "$2"
        printf 'tentativas=%s\n' "$3"
    } > "$ra_dir/audio_ks_ultimo.$$" 2>/dev/null || return 0
    mv -f "$ra_dir/audio_ks_ultimo.$$" "$ra_dir/audio_ks_ultimo" 2>/dev/null || true
    return 0
}

hefesto_gm_prev=""

_hefesto_on_exit() {
    [ -n "$hefesto_gm_prev" ] && gm_set_profile "$hefesto_gm_prev" 2>/dev/null
    record_last_exit
    return 0
}
trap '_hefesto_on_exit' EXIT

GM_BUS_DEST="com.system76.PowerDaemon"
GM_BUS_PATH="/com/system76/PowerDaemon"

gm_have_transport() {
    command -v system76-power >/dev/null 2>&1 && return 0
    command -v busctl >/dev/null 2>&1 && return 0
    command -v dbus-send >/dev/null 2>&1
}

gm_run() {
    if command -v timeout >/dev/null 2>&1; then
        timeout 2 "$@" 2>/dev/null
    else
        "$@" 2>/dev/null
    fi
}

gm_current_profile() {
    if command -v system76-power >/dev/null 2>&1; then
        gm_run system76-power profile \
            | sed -n 's/^Power Profile:[[:space:]]*//p'
    elif command -v busctl >/dev/null 2>&1; then
        gm_run busctl --system call \
            "$GM_BUS_DEST" "$GM_BUS_PATH" "$GM_BUS_DEST" GetProfile \
            | sed -n 's/^s[[:space:]]*"\(.*\)"$/\1/p'
    elif command -v dbus-send >/dev/null 2>&1; then
        gm_run dbus-send --system --print-reply --dest="$GM_BUS_DEST" \
            "$GM_BUS_PATH" "$GM_BUS_DEST.GetProfile" \
            | sed -n 's/.*string "\(.*\)".*/\1/p'
    fi | head -n 1 | tr '[:upper:]' '[:lower:]'
}

gm_pelo_transporte() {
    gm_quem="$1"
    case "$2" in
        battery) gm_method="Battery" ;;
        balanced) gm_method="Balanced" ;;
        performance) gm_method="Performance" ;;
        *) return 1 ;;
    esac
    if gm_bin="$(command -v system76-power)"; then
        $gm_quem "$gm_bin" profile "$2"
    elif gm_bin="$(command -v busctl)"; then
        $gm_quem "$gm_bin" --system call \
            "$GM_BUS_DEST" "$GM_BUS_PATH" "$GM_BUS_DEST" "$gm_method"
    elif gm_bin="$(command -v dbus-send)"; then
        $gm_quem "$gm_bin" --system --print-reply --dest="$GM_BUS_DEST" \
            "$GM_BUS_PATH" "$GM_BUS_DEST.$gm_method"
    else
        return 1
    fi
}

gm_set_profile() {
    gm_pelo_transporte gm_run "$1" >/dev/null
}

_RESTAURADOR='p=$1; t=$2; shift 2
while kill -0 "$p" 2>/dev/null; do sleep "$t" || break; done
printf "%s\n" "$p" | "$@"'

tem_quem_restaure() {
    command -v systemd-run >/dev/null 2>&1
}

_restaurar_quando_sair() {
    rq_pid="$1"
    shift
    tem_quem_restaure || return 1
    rq_poll="${HEFESTO_GM_POLL_SECS:-2}"
    if command -v timeout >/dev/null 2>&1; then
        timeout 5 systemd-run --user --collect --quiet -- /bin/sh -c "$_RESTAURADOR" \
            hefesto-restaurador "$rq_pid" "$rq_poll" "$@" </dev/null >/dev/null 2>&1
    else
        systemd-run --user --collect --quiet -- /bin/sh -c "$_RESTAURADOR" \
            hefesto-restaurador "$rq_pid" "$rq_poll" "$@" </dev/null >/dev/null 2>&1
    fi
}

enter_game_mode() {
    tem_quem_restaure || return 0
    gm_have_transport || return 0
    gm_prev="$(gm_current_profile)" || gm_prev=""
    case "$gm_prev" in
        battery|balanced) ;;
        *) return 0 ;;
    esac
    gm_set_profile performance || return 0
    if ! gm_pelo_transporte "_restaurar_quando_sair $$" "$gm_prev"; then
        gm_set_profile "$gm_prev"
        return 0
    fi
    hefesto_gm_prev="$gm_prev"
    return 0
}

PLACA_ACORDADA="${HEFESTO_PLACA_ACORDADA:-/usr/local/lib/hefesto-dualsense4unix/hefesto_placa_acordada.sh}"

acordar_a_placa() {
    [ -x "$PLACA_ACORDADA" ] || return 0
    pa_sudo="$(command -v sudo)" || return 0
    tem_quem_restaure || return 0
    if command -v timeout >/dev/null 2>&1; then
        printf '%s\n' "$$" | timeout 5 "$pa_sudo" -n "$PLACA_ACORDADA" acordar >/dev/null 2>&1 || return 0
    else
        printf '%s\n' "$$" | "$pa_sudo" -n "$PLACA_ACORDADA" acordar >/dev/null 2>&1 || return 0
    fi
    _restaurar_quando_sair "$$" "$pa_sudo" -n "$PLACA_ACORDADA" devolver && return 0
    printf '%s\n' "$$" | "$pa_sudo" -n "$PLACA_ACORDADA" devolver >/dev/null 2>&1
    return 0
}

camadas_da_steam_fora() {
    cs_envs=""
    cs_base="${XDG_CONFIG_HOME:-}"
    if [ -z "$cs_base" ]; then
        [ -n "${HOME:-}" ] || return 0
        cs_base="$HOME/.config"
    fi
    cs_arquivo="$cs_base/hefesto-dualsense4unix/camadas_da_steam_fora.env"
    [ -f "$cs_arquivo" ] || return 0
    cs_sobreposicao=""
    cs_gravador=""
    while IFS= read -r cs_linha || [ -n "$cs_linha" ]; do
        case "$cs_linha" in
            DISABLE_VK_LAYER_VALVE_steam_overlay_1=1) cs_sobreposicao="$cs_linha" ;;
            DISABLE_VK_LAYER_VALVE_steam_fossilize_1=1) cs_gravador="$cs_linha" ;;
        esac
    done < "$cs_arquivo"
    [ -n "$cs_sobreposicao" ] && [ -n "$cs_gravador" ] || return 0
    cs_envs="$cs_sobreposicao
$cs_gravador"
    return 0
}

xalia_fora() {
    xf_envs=""
    [ -z "${PROTON_USE_XALIA+x}" ] || return 0
    xf_envs="PROTON_USE_XALIA=0"
    return 0
}

curar_camadas_vulkan() {
    [ -n "${cs_envs:-}" ] || return 0
    prefixo="${STEAM_COMPAT_DATA_PATH:-}"
    [ -n "$prefixo" ] || return 0
    cv_jogo="${STEAM_COMPAT_INSTALL_PATH:-}"
    [ -n "$cv_jogo" ] || return 0
    reg="$prefixo/pfx/system.reg"
    [ -f "$reg" ] || return 0

    cv_secao="$(grep -FA 20 'Vulkan\\ImplicitLayers' "$reg" 2>/dev/null)" || cv_secao=""
    case "$cv_secao" in
        *"=dword:00000000"*) ;;
        *) return 0 ;;
    esac

    curador="$HOME/.local/share/hefesto-dualsense4unix/bin/hefesto-camadas"
    [ -x "$curador" ] || return 0
    command -v python3 >/dev/null 2>&1 || return 0

    if command -v timeout >/dev/null 2>&1; then
        cv_run="timeout 10"
    else
        cv_run=""
    fi
    LD_LIBRARY_PATH= LD_PRELOAD= PYTHONPATH= PYTHONHOME= \
        $cv_run python3 "$curador" --prefixo "$prefixo" --jogo "$cv_jogo" \
        --appid "${SteamAppId:-}" >/dev/null 2>&1
    return 0
}

dualsense_no_cabo() {
    for d in "${HEFESTO_SYSFS:-/sys}"/bus/usb/devices/*; do
        [ -r "$d/idVendor" ] && [ -r "$d/idProduct" ] || continue
        IFS= read -r ks_vid 2>/dev/null <"$d/idVendor" || continue
        [ "$ks_vid" = "054c" ] || continue
        IFS= read -r ks_pid 2>/dev/null <"$d/idProduct" || continue
        case "$ks_pid" in
            0ce6|0df2) ;;
            *) continue ;;
        esac
        for s in "$d"/*/sound/card*; do
            [ -e "$s" ] && return 0
        done
    done
    return 1
}

dualsense_no_radio() {
    for d in "${HEFESTO_SYSFS:-/sys}"/bus/hid/devices/*; do
        case "${d##*/}" in
            0005:054[Cc]:0[Cc][Ee]6.*|0005:054[Cc]:0[Dd][Ff]2.*) return 0 ;;
        esac
    done
    return 1
}

dualsense_fisico_na_mesa() {
    dualsense_no_cabo || dualsense_no_radio
}

curar_audio_ks() {
    prefixo="${STEAM_COMPAT_DATA_PATH:-}"
    [ -n "$prefixo" ] || return 0
    if ! command -v python3 >/dev/null 2>&1; then
        registrar_audio_ks 0 sem-python 0
        return 0
    fi
    reg="$prefixo/pfx/system.reg"
    ks_so_esquece=""
    case "$hefesto_envs" in
        *PROTON_ENABLE_MHWILDS_USB_AUDIO=1*) ks_modo="" ;;
        *)
            if [ ! -f "$reg" ]; then
                registrar_audio_ks 0 desligado 0
                return 0
            elif grep -qF 'HEFESTOKS' "$reg" 2>/dev/null; then
                ks_modo="--remover"
            elif grep -qF '&IG_' "$reg" 2>/dev/null || grep -qF 'WINEXINPUT' "$reg" 2>/dev/null; then
                ks_modo="--remover"
                ks_so_esquece=1
            else
                registrar_audio_ks 0 desligado 0
                return 0
            fi
            ;;
    esac
    if [ ! -f "$reg" ]; then
        registrar_audio_ks 0 sem-registro 0
        return 0
    fi
    curador="$HOME/.local/share/hefesto-dualsense4unix/bin/hefesto-audio-ks"
    if [ ! -x "$curador" ]; then
        registrar_audio_ks 0 sem-curador 0
        return 0
    fi
    if command -v timeout >/dev/null 2>&1; then
        ks_run="timeout 10"
    else
        ks_run=""
    fi
    ks_tentativas=1
    while :; do
        LD_LIBRARY_PATH= LD_PRELOAD= PYTHONPATH= PYTHONHOME= \
            $ks_run python3 "$curador" --prefixo "$prefixo" \
            --sysfs "${HEFESTO_SYSFS:-/sys}" $ks_modo >/dev/null 2>&1
        ks_rc=$?
        [ "$ks_rc" -eq 3 ] || break
        [ "$ks_tentativas" -le 5 ] || break
        sleep "${HEFESTO_KS_ESPERA_SECS:-1}" 2>/dev/null || break
        ks_tentativas=$((ks_tentativas + 1))
    done
    case "$ks_rc" in
        0) if [ -n "$ks_modo" ] && [ -z "$ks_so_esquece" ]; then ks_motivo="removido"
           elif [ -n "$ks_modo" ]; then ks_motivo="desligado"
           else ks_motivo="ok"; fi ;;
        3) ks_motivo="ocupado" ;;
        *) ks_motivo="erro" ;;
    esac
    registrar_audio_ks "$ks_rc" "$ks_motivo" "$ks_tentativas"
    return 0
}

podar_bins_do_interpretador() {
    la_novo=""
    [ -n "$1" ] || return 0
    la_resto="$1:"
    la_primeiro=1
    while [ -n "$la_resto" ]; do
        la_dir="${la_resto%%:*}"
        la_resto="${la_resto#*:}"
        la_cmp="${la_dir%/}"
        if [ -n "$la_cmp" ]; then
            [ "$la_cmp" = "$la_bin_venv" ] && continue
            [ "$la_cmp" = "$la_bin_conda" ] && continue
        fi
        if [ "$la_primeiro" = 1 ]; then
            la_novo="$la_dir"
            la_primeiro=0
        else
            la_novo="$la_novo:$la_dir"
        fi
    done
    return 0
}

limpar_ambiente_do_interpretador() {
    la_bin_venv=""
    la_bin_conda=""
    la_base="${VIRTUAL_ENV:-}"
    la_base="${la_base%/}"
    [ -n "$la_base" ] && la_bin_venv="$la_base/bin"
    la_base="${CONDA_PREFIX:-}"
    la_base="${la_base%/}"
    [ -n "$la_base" ] && la_bin_conda="$la_base/bin"
    unset VIRTUAL_ENV CONDA_PREFIX CONDA_DEFAULT_ENV CONDA_SHLVL PYTHONHOME PYTHONPATH PYENV_VERSION
    [ -n "$la_bin_venv$la_bin_conda" ] || return 0
    podar_bins_do_interpretador "${PATH:-}"
    [ -n "$la_novo" ] && PATH="$la_novo"
    podar_bins_do_interpretador "${SYSTEM_PATH:-}"
    [ -n "$la_novo" ] && export SYSTEM_PATH="$la_novo"
    return 0
}

jogo_excluido() {
    je_appid="${SteamAppId:-}"
    case "$je_appid" in
        ''|0) return 1 ;;
        *[!0-9]*) return 1 ;;
    esac
    je_base="${XDG_CONFIG_HOME:-}"
    if [ -z "$je_base" ]; then
        [ -n "${HOME:-}" ] || return 1
        je_base="$HOME/.config"
    fi
    je_lista="$je_base/hefesto-dualsense4unix/lista_de_exclusao.json"
    [ -f "$je_lista" ] || return 1
    while IFS= read -r je_linha || [ -n "$je_linha" ]; do
        case "$je_linha" in
            *'"chave": "steam_app_'"$je_appid"'"'*) return 0 ;;
        esac
    done < "$je_lista"
    return 1
}

if jogo_excluido; then
    exec env "$@"
fi

record_last_run || true

usuario_pos_dll=0
for ud_arg in "$@"; do
    case "$ud_arg" in
        WINEDLLOVERRIDES=*|WINEDLLPATH=*) usuario_pos_dll=1; break ;;
        *=*) continue ;;
        *) break ;;
    esac
done

hefesto_envs="$(decide_envs)" || hefesto_envs=""

case "$hefesto_envs" in
    *PROTON_ENABLE_MHWILDS_USB_AUDIO=1*)
        if ! dualsense_fisico_na_mesa; then
            ks_envs=""
            while IFS= read -r kv; do
                case "$kv" in
                    PROTON_ENABLE_MHWILDS_USB_AUDIO=1) kv="PROTON_ENABLE_MHWILDS_USB_AUDIO=0" ;;
                esac
                ks_envs="${ks_envs}${kv}
"
            done <<HEFESTO_KS_EOF
$hefesto_envs
HEFESTO_KS_EOF
            hefesto_envs="$ks_envs"
        fi
        ;;
esac

if [ -n "$hefesto_envs" ]; then
    while IFS= read -r kv; do
        [ -n "$kv" ] && set -- "$kv" "$@"
    done <<HEFESTO_EOF
$hefesto_envs
HEFESTO_EOF
fi

camadas_da_steam_fora || cs_envs=""
if [ -n "$cs_envs" ]; then
    while IFS= read -r kv; do
        [ -n "$kv" ] && set -- "$kv" "$@"
    done <<HEFESTO_CS_EOF
$cs_envs
HEFESTO_CS_EOF
fi
curar_camadas_vulkan || true

xalia_fora || xf_envs=""
[ -n "$xf_envs" ] && set -- "$xf_envs" "$@"

curar_audio_ks || true

enter_game_mode || true
acordar_a_placa || true

limpar_ambiente_do_interpretador || true

exec env "$@"
