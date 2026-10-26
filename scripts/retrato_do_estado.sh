#!/usr/bin/env bash

set -uo pipefail

_RAIZ_DO_PRODUTO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

_python_do_produto() {
    local py
    for py in "${_RAIZ_DO_PRODUTO}/.venv/bin/python" \
              "${HOME}/.local/share/hefesto-dualsense4unix/venv/bin/python" \
              "/opt/hefesto-dualsense4unix/venv/bin/python"; do
        [[ -x "${py}" ]] && { printf '%s\n' "${py}"; return 0; }
    done
    command -v python3 2>/dev/null
}

_mascarar() {
    local py; py="$(_python_do_produto)"
    [[ -n "${py}" ]] || return 1
    PYTHONPATH="${_RAIZ_DO_PRODUTO}/src${PYTHONPATH:+:${PYTHONPATH}}" "${py}" -c '
import sys
from hefesto_dualsense4unix.core.formas_do_endereco import mascarar
sys.stdout.write(mascarar(sys.stdin.read()))'
}

_capturar() {
    local destino="$1" descricao="$2"
    shift 2
    if [[ -z "$(_python_do_produto)" ]]; then
        echo "retrato: sem o Python do produto não há máscara, e saída crua não vai ao disco (${destino})" >&2
        return 1
    fi
    {
        echo "# ${descricao}"
        echo "# comando: $*"
        echo
        "$@" 2>/dev/null | _mascarar
    } > "${destino}"
}

retratar() {
    local raiz="${1}"
    mkdir -p "${raiz}"

    {
        echo "# Retrato do estado — $(date '+%Y-%m-%d %H:%M:%S')"
        echo "# host: $(hostname)"
        echo "# kernel: $(uname -r)"
        echo "# usuário: ${USER}"
    } > "${raiz}/00-cabecalho.txt"

    _capturar "${raiz}/10-units-sistema.txt" "unidades de sistema da casa" \
        bash -c "systemctl list-unit-files 'hefesto*' --no-pager --plain 2>/dev/null | grep -E '^hefesto' | sort"
    _capturar "${raiz}/11-units-usuario.txt" "unidades de usuário da casa" \
        bash -c "systemctl --user list-unit-files 'hefesto*' --no-pager --plain 2>/dev/null | grep -E '^hefesto' | sort"
    _capturar "${raiz}/12-timers.txt" "timers da casa (só nome e unidade, sem relógio)" \
        bash -c "systemctl list-timers 'hefesto*' --all --no-pager 2>/dev/null | awk 'NF>3 {print \$(NF-1), \$NF}' | sort"
    _capturar "${raiz}/13-ativos.txt" "estado ativo de cada unidade da casa" \
        bash -c "for u in \$(systemctl list-unit-files 'hefesto*' --no-pager --plain 2>/dev/null | awk '/^hefesto/{print \$1}'); do
                     printf '%-52s %s\n' \"\$u\" \"\$(systemctl is-enabled \"\$u\" 2>/dev/null)/\$(systemctl is-active \"\$u\" 2>/dev/null)\"
                 done | sort"

    _capturar "${raiz}/20-dropins-bluetooth.txt" "drop-ins nossos no bluetooth.service" \
        bash -c "for f in /etc/systemd/system/bluetooth.service.d/*.conf; do
                     [ -f \"\$f\" ] || continue
                     echo \"### \$f\"; grep -vE '^\s*#|^\s*\$' \"\$f\"; echo
                 done"
    _capturar "${raiz}/21-main.conf.txt" "o /etc/bluetooth/main.conf efetivo (sem comentário)" \
        bash -c "grep -vE '^\s*#|^\s*\$' /etc/bluetooth/main.conf 2>/dev/null"
    _capturar "${raiz}/22-main.conf.d.txt" "drop-ins de main.conf.d" \
        bash -c "for f in /etc/bluetooth/main.conf.d/*; do
                     [ -f \"\$f\" ] || continue
                     echo \"### \$f\"; grep -vE '^\s*#|^\s*\$' \"\$f\"; echo
                 done"
    _capturar "${raiz}/23-watchdogsec.txt" "o WatchdogSec efetivo do bluetooth.service (o que MATA o daemon)" \
        bash -c "systemctl show bluetooth -p WatchdogUSec -p RestartUSec -p StartLimitBurst 2>/dev/null"

    _capturar "${raiz}/30-udev-arquivos.txt" "regras de udev da casa (nome e tamanho)" \
        bash -c "ls -la /etc/udev/rules.d/ 2>/dev/null | grep -iE 'hefesto|dualsense' | awk '{print \$NF, \$5}' | sort"
    _capturar "${raiz}/31-udev-conteudo.txt" "conteúdo das regras da casa" \
        bash -c "for f in /etc/udev/rules.d/*hefesto* /etc/udev/rules.d/*dualsense*; do
                     [ -f \"\$f\" ] || continue
                     echo \"### \$f\"; grep -vE '^\s*#|^\s*\$' \"\$f\"; echo
                 done"

    _capturar "${raiz}/40-dkms.txt" "módulos DKMS da casa" \
        bash -c "dkms status 2>/dev/null | grep -i hefesto | sort"
    _capturar "${raiz}/41-modulos-carregados.txt" "de onde vem cada módulo HID carregado" \
        bash -c "for m in hid_playstation hid_nintendo; do
                     printf '%-18s %s\n' \"\$m\" \"\$(modinfo -n \"\$m\" 2>/dev/null || echo '(ausente)')\"
                 done"

    _capturar "${raiz}/50-binarios.txt" "executáveis instalados" \
        bash -c "for d in /usr/local/bin /usr/bin; do
                     ls -1 \"\$d\" 2>/dev/null | grep -i hefesto | sed \"s#^#\$d/#\"
                 done | sort"
    _capturar "${raiz}/51-libexec.txt" "scripts auxiliares instalados" \
        bash -c "ls -1 /usr/local/lib/hefesto-dualsense4unix/ 2>/dev/null | sort"
    _capturar "${raiz}/52-pacote.txt" "instalação Python (editable ou não)" \
        bash -c "pip show hefesto-dualsense4unix 2>/dev/null | grep -E '^(Name|Version|Location|Editable)'"

    _capturar "${raiz}/60-grupos.txt" "grupos do usuário (o 'input' decide touchpad e giroscópio)" \
        bash -c "id -Gn | tr ' ' '\n' | sort"
    _capturar "${raiz}/61-state.txt" "arquivos de estado do produto" \
        bash -c "ls -1 ~/.local/state/hefesto-dualsense4unix/ 2>/dev/null | sort"
    _capturar "${raiz}/62-config.txt" "configuração dela (só nomes — o conteúdo é dela)" \
        bash -c "ls -1 ~/.config/hefesto-dualsense4unix/ 2>/dev/null | sort"
    _capturar "${raiz}/63-salva-vidas.txt" "snapshots de pareamento (o que o uninstall não pode levar)" \
        bash -c "ls -1 /var/lib/hefesto-dualsense4unix/bt-bonds/ 2>/dev/null | sort | tail -20"

    _capturar "${raiz}/70-audio-cards.txt" "cards de áudio" \
        bash -c "pactl list short cards 2>/dev/null | awk '{print \$2}' | sort"
    _capturar "${raiz}/71-audio-perfis.txt" "perfil ativo de cada card" \
        bash -c "pactl --format=json list cards 2>/dev/null | python3 -c 'import json,sys
try:
    cartoes = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
for c in cartoes:
    print(\"Name: %s  Active Profile: %s\" % (c.get(\"name\", \"\"), c.get(\"active_profile\") or \"\"))
'"
    _capturar "${raiz}/72-audio-nos.txt" "sinks e sources (sem monitor)" \
        bash -c "{ pactl list short sinks 2>/dev/null | awk '{print \"sink   \", \$2}'
                   pactl list short sources 2>/dev/null | grep -v monitor | awk '{print \"source \", \$2}'; } | sort"
    _capturar "${raiz}/73-audio-dropins.txt" "drop-ins de WirePlumber (nossos e de terceiros)" \
        bash -c "for d in /usr/share/wireplumber/wireplumber.conf.d /etc/wireplumber/wireplumber.conf.d ~/.config/wireplumber/wireplumber.conf.d; do
                     [ -d \"\$d\" ] || continue
                     ls -1 \"\$d\" 2>/dev/null | sed \"s#^#\$d/#\"
                 done | sort"

    _capturar "${raiz}/80-bonds.txt" "pareamentos que o BlueZ conhece" \
        bash -c "busctl tree org.bluez 2>/dev/null | grep -oE 'dev_[0-9A-F_]{17}' | sed 's/dev_//;s/_/:/g' | sort"
    _capturar "${raiz}/81-hid.txt" "aparelhos HID no kernel (só o par VID:PID, sem a instância)" \
        bash -c "ls -1 /sys/bus/hid/devices/ 2>/dev/null | sed -E 's/\.[0-9A-F]+$//' | sort | uniq -c | awk '{print \$2, \"x\" \$1}'"

    echo "${raiz}"
}

_veredito_eixo() {
    local antes="$1" depois="$2" nome="$3"
    if [[ ! -f "${antes}" && ! -f "${depois}" ]]; then
        printf '  %-34s %s\n' "${nome}" "— (não capturado)"
        return
    fi
    local a="${antes}" d="${depois}"
    [[ -f "${a}" ]] || a=/dev/null
    [[ -f "${d}" ]] || d=/dev/null
    if diff -q <(grep -vE '^#' "${a}") <(grep -vE '^#' "${d}") >/dev/null 2>&1; then
        printf '  %-34s IGUAL\n' "${nome}"
    else
        printf '  %-34s DIFERENTE\n' "${nome}"
        diff <(grep -vE '^#' "${a}") <(grep -vE '^#' "${d}") 2>/dev/null \
            | grep -E '^[<>]' | sed 's/^/      /' | head -14
    fi
}

comparar() {
    local antes="$1" depois="$2"
    echo "# Comparação de estado"
    echo "#   antes:  ${antes}"
    echo "#   depois: ${depois}"
    echo
    echo "Regra de leitura: DIFERENTE não é reprovação por si. O que reprova é o instalador"
    echo "NÃO recriar o que o desinstalador levou — as linhas '<' que não voltaram."
    echo

    local nomes=(
        "10-units-sistema:unidades de sistema"
        "11-units-usuario:unidades de usuário"
        "12-timers:timers"
        "13-ativos:enabled/active"
        "20-dropins-bluetooth:drop-ins do bluetooth"
        "21-main.conf:main.conf do BlueZ"
        "22-main.conf.d:drop-ins de main.conf.d"
        "23-watchdogsec:WatchdogSec efetivo"
        "30-udev-arquivos:regras de udev (arquivos)"
        "31-udev-conteudo:regras de udev (conteúdo)"
        "40-dkms:módulos DKMS"
        "41-modulos-carregados:módulos carregados"
        "50-binarios:executáveis"
        "51-libexec:scripts auxiliares"
        "52-pacote:instalação Python"
        "60-grupos:grupos do usuário"
        "61-state:estado do produto"
        "62-config:configuração dela"
        "63-salva-vidas:snapshots de pareamento"
        "70-audio-cards:cards de áudio"
        "71-audio-perfis:perfis de áudio"
        "72-audio-nos:sinks e sources"
        "73-audio-dropins:drop-ins de áudio"
        "80-bonds:pareamentos"
        "81-hid:aparelhos HID"
    )
    for par in "${nomes[@]}"; do
        _veredito_eixo "${antes}/${par%%:*}.txt" "${depois}/${par%%:*}.txt" "${par#*:}"
    done

    echo
    echo "## O que o instalador NÃO recriou (as linhas que sumiram e não voltaram)"
    local achou=0
    for par in "${nomes[@]}"; do
        local f="${par%%:*}"
        [[ -f "${antes}/${f}.txt" && -f "${depois}/${f}.txt" ]] || continue
        local perdidas
        perdidas="$(diff <(grep -vE '^#' "${antes}/${f}.txt") <(grep -vE '^#' "${depois}/${f}.txt") 2>/dev/null | grep -E '^<' | sed 's/^< //')"
        if [[ -n "${perdidas}" ]]; then
            achou=1
            echo "  [${par#*:}]"
            echo "${perdidas}" | sed 's/^/      /'
        fi
    done
    [[ "${achou}" -eq 0 ]] && echo "  (nada — o instalador recriou tudo o que existia antes)"
}

main() {
    if [[ "${1:-}" == "--comparar" ]]; then
        [[ $# -eq 3 ]] || { echo "uso: $0 --comparar ANTES/ DEPOIS/" >&2; exit 2; }
        comparar "$2" "$3"
        exit 0
    fi
    local saida="${1:-retratos-de-estado/$(date +%Y%m%d-%H%M%S)}"
    retratar "${saida}"
}

main "$@"
