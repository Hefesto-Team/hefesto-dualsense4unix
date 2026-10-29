#!/usr/bin/env bash
# shellcheck shell=bash

declare -F warn >/dev/null 2>&1 || warn() { printf '      aviso: %s\n' "$*"; }
declare -F step >/dev/null 2>&1 || step() { printf '\n[%s] %s\n' "$1" "$2"; }

: "${ROOT_DIR:?camada_de_maquina.sh: defina ROOT_DIR (a raiz da árvore) antes do source}"
: "${SKIP_UDEV:=0}"
: "${NO_OSK:=0}"
: "${NO_DKMS:=0}"
: "${NO_UCM:=0}"
: "${NO_WIFI_USB:=0}"
: "${DESEMPENHO_PEDIDO:=}"
: "${DESEMPENHO_PROVADOS:=}"
: "${AUTO_YES:=0}"

declare -p _REINICIO_PENDENTE >/dev/null 2>&1 || _REINICIO_PENDENTE=()

anotar_reinicio_pendente() {
    local o
    for o in "${_REINICIO_PENDENTE[@]}"; do
        [[ "${o}" == "$1" ]] && return 0
    done
    _REINICIO_PENDENTE+=("$1")
    return 0
}

jogo_em_cena() {
    python3 -I "${ROOT_DIR}/src/hefesto_dualsense4unix/integrations/quem_o_jogo_le.py" \
        --ha-jogo --proc "${HEFESTO_RAIZ_PROC:-/proc}" >/dev/null 2>&1
}

arquivo_da_troca_adiada() {
    printf '%s\n' "${HEFESTO_TROCA_NO_FIM_DO_JOGO:-${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/hefesto-dualsense4unix/troca-no-fim-do-jogo}"
}

adiar_para_o_fim_do_jogo() {
    local _arq
    _arq="$(arquivo_da_troca_adiada)"
    mkdir -p "$(dirname "${_arq}")" 2>/dev/null || return 0
    grep -qsx "$1" "${_arq}" || printf '%s\n' "$1" >> "${_arq}"
}

cumprir_a_troca() {
    local _arq _resto
    _arq="$(arquivo_da_troca_adiada)"
    [[ -f "${_arq}" ]] || return 0
    _resto="$(grep -vx "$1" "${_arq}" 2>/dev/null || true)"
    if [[ -n "${_resto}" ]]; then
        printf '%s\n' "${_resto}" > "${_arq}"
    else
        rm -f "${_arq}"
    fi
    return 0
}

vigiar_o_fim_do_jogo() {
    local _arq _v _python="${1:-}"
    _arq="$(arquivo_da_troca_adiada)"
    [[ -s "${_arq}" && -x "${_python}" ]] || return 0
    command -v systemd-run >/dev/null 2>&1 || return 0
    local _env=("--setenv=HEFESTO_TROCA_NO_FIM_DO_JOGO=${_arq}")
    for _v in WAYLAND_DISPLAY DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS; do
        if [[ -n "${!_v:-}" ]]; then
            _env+=("--setenv=${_v}=${!_v}")
        fi
    done
    if systemd-run --user --quiet --collect --unit=hefesto-troca-no-fim-do-jogo \
            --description="Hefesto: a troca do install que espera o jogo fechar" \
            "${_env[@]}" "${_python}" -m hefesto_dualsense4unix.app.actions.troca_no_fim_do_jogo \
            --esperar >/dev/null 2>&1; then
        printf '      a troca sai sozinha quando o jogo fechar\n'
    fi
    return 0
}

modulo_pede_reinicio() {
    local nome="$1" raiz="${HEFESTO_SYS_MODULE:-/sys/module}" carregado arquivo novo
    carregado="$(cat "${raiz}/${nome//-/_}/srcversion" 2>/dev/null || true)"
    [[ -n "${carregado}" ]] || return 1
    arquivo="$(modinfo -F filename "${nome}" 2>/dev/null || true)"
    [[ "${arquivo}" == */updates/dkms/* ]] || return 1
    novo="$(modinfo -F srcversion "${nome}" 2>/dev/null || true)"
    [[ -n "${novo}" && "${novo}" != "${carregado}" ]]
}

grupo_pede_novo_login() {
    local membros
    membros="$(getent group hefesto 2>/dev/null | cut -d: -f4 || true)"
    [[ ",${membros}," == *",${USER:-$(id -un)},"* ]] || return 1
    [[ " $(id -nG 2>/dev/null) " != *" hefesto "* ]]
}

_PENDENTE_DO_CMDLINE="a linha de comando do kernel (usbcore: o microfone do DualSense no cabo e o autosuspend)"

dizer_o_reinicio_pendente() {
    if grupo_pede_novo_login; then
        anotar_reinicio_pendente "o grupo hefesto (o acesso ao controle virtual)"
    fi
    [[ "${#_REINICIO_PENDENTE[@]}" -gt 0 ]] || return 0
    printf '\n'
    printf ' Reinicie o computador para terminar a instalação. Esperam o reinício:\n'
    printf '   - %s\n' "${_REINICIO_PENDENTE[@]}"
    printf '─────────────────────────────────────────\n'
    return 0
}

opcao_do_modprobe() {
    awk -v p="$2" '
        $1 == "options" {
            for (i = 3; i <= NF; i++) {
                n = index($i, "=")
                if (n > 1 && substr($i, 1, n - 1) == p) v = substr($i, n + 1)
            }
        }
        END { if (v !~ /^[A-Za-z0-9_.,:-]+$/) exit 1; print v }
    ' "$1" 2>/dev/null
}

_render_broker_units() {
    local service_src="$1" socket_src="$2" out_dir="$3"
    local fechado="${4:-1}"
    sed -e "s/__NO_NASCE_FECHADO__/${fechado}/" \
        "${service_src}" \
        > "${out_dir}/hefesto-hidraw-broker.service"
    cat "${socket_src}" > "${out_dir}/hefesto-hidraw-broker.socket"
    if grep -q '__SESSION_\|__NO_NASCE_FECHADO__' \
            "${out_dir}/hefesto-hidraw-broker.service" \
            "${out_dir}/hefesto-hidraw-broker.socket"; then
        return 1
    fi
    return 0
}

install_udev_host() {
    local _udev_args=()
    if [[ "${ABRIR_O_NO:-0}" -eq 1 ]]; then
        _udev_args+=(--no-fechar-o-no)
    fi
    if [[ "${SKIP_UDEV}" -eq 1 ]]; then
        printf '      udev pulado (--no-udev) — rode depois: sudo bash scripts/install_udev.sh\n'
    elif command -v sudo >/dev/null 2>&1; then
        if bash "${ROOT_DIR}/scripts/install_udev.sh" "${_udev_args[@]}" >/dev/null 2>&1; then
            printf '      udev rules aplicadas + recarregadas\n'
            if jogo_em_cena; then
                printf '      com um jogo aberto, o controle não é reenumerado: as regras novas valem no próximo plugue\n'
            fi
        else
            warn "install_udev.sh falhou — rode manualmente: sudo bash scripts/install_udev.sh"
        fi
    else
        warn "sudo ausente — rode scripts/install_udev.sh como root depois"
    fi
}

install_osk_host() {
    if [[ "${NO_OSK}" -eq 1 ]]; then
        printf '      teclado na tela pulado (--no-osk) — o L3 do controle só avisa que não tem o que abrir\n'
        mkdir -p "${HOME}/.local/state/hefesto-dualsense4unix" 2>/dev/null || true
        {
            printf '# gravado por install.sh (--no-osk) — NÃO editar à mão.\n'
            printf 'resultado=pulado\n'
            printf 'motivo=--no-osk\n'
            printf 'data=%s\n' "$(date -Is 2>/dev/null || date)"
        } > "${HOME}/.local/state/hefesto-dualsense4unix/teclado-na-tela.conf" 2>/dev/null || true
        return 0
    fi
    if [[ ! -r "${ROOT_DIR}/scripts/install_osk.sh" ]]; then
        warn "scripts/install_osk.sh ausente — teclado na tela pulado"
        return 0
    fi
    if [[ "${AUTO_YES}" -eq 1 ]]; then
        bash "${ROOT_DIR}/scripts/install_osk.sh" --yes || true
    else
        bash "${ROOT_DIR}/scripts/install_osk.sh" || true
    fi
}

install_ucm_dualsense_host() {
    _pula_por_so_leitura ucm && return 0
    if [[ "${NO_UCM}" -eq 1 ]]; then
        printf '      perfil UCM do DualSense pulado (--no-ucm) — a vibração dos jogos da Sony não chega pelo cabo\n'
        return 0
    fi
    if [[ "${SKIP_UDEV}" -eq 1 ]]; then
        printf '      perfil UCM do DualSense pulado (--no-udev) — rode depois: bash scripts/install_ucm_dualsense.sh\n'
        return 0
    fi
    if ! bash "${ROOT_DIR}/scripts/install_ucm_dualsense.sh"; then
        warn "install_ucm_dualsense.sh falhou — rode: bash scripts/install_ucm_dualsense.sh"
    fi
}

install_broker_host() {
    if [[ "${SKIP_UDEV}" -eq 1 ]]; then
        printf '      broker pulado (--no-udev) — re-execute ./install.sh sem a flag para ativá-lo\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — broker hide-hidraw NÃO instalado (a cura de raiz do duplicado fica de fora)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — broker hide-hidraw pulado (re-execute ./install.sh)"
        return 0
    fi
    _broker_bin_src="${ROOT_DIR}/src/hefesto_dualsense4unix/broker/hidraw_broker.py"
    _broker_bin_dst="/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker"
    _broker_tmp="$(mktemp -d)"
    if [[ ! -f "${_broker_bin_src}" ]]; then
        warn "src/hefesto_dualsense4unix/broker/hidraw_broker.py ausente — broker NÃO instalado"
    elif ! _render_broker_units \
            "${ROOT_DIR}/assets/systemd/hefesto-hidraw-broker.service" \
            "${ROOT_DIR}/assets/systemd/hefesto-hidraw-broker.socket" \
            "${_broker_tmp}" \
            "$(( ${ABRIR_O_NO:-0} == 1 ? 0 : 1 ))"; then
        warn "render das units do broker deixou placeholder __SESSION_* sobrando — broker NÃO instalado"
    elif ! sudo install -Dm755 "${_broker_bin_src}" "${_broker_bin_dst}" 2>/dev/null; then
        warn "não consegui gravar ${_broker_bin_dst}"
    elif ! sudo install -Dm644 "${_broker_tmp}/hefesto-hidraw-broker.service" \
            /etc/systemd/system/hefesto-hidraw-broker.service 2>/dev/null \
         || ! sudo install -Dm644 "${_broker_tmp}/hefesto-hidraw-broker.socket" \
            /etc/systemd/system/hefesto-hidraw-broker.socket 2>/dev/null; then
        warn "não consegui gravar as units do broker em /etc/systemd/system"
    else
        sudo systemctl daemon-reload >/dev/null 2>&1 || true
        if sudo systemctl enable --now hefesto-hidraw-broker.socket >/dev/null 2>&1; then
            printf '      hefesto-hidraw-broker.socket habilitado (atende quem está na frente do computador — só o .socket; o .service sobe na 1ª conexão)\n'
            _broker_owner_file="${HOME}/.local/state/hefesto-dualsense4unix/broker-owner.conf"
            mkdir -p "$(dirname "${_broker_owner_file}")"
            {
                for _bp in "${_broker_bin_dst}" \
                           /etc/systemd/system/hefesto-hidraw-broker.service \
                           /etc/systemd/system/hefesto-hidraw-broker.socket; do
                    printf '%s=%s\n' "${_bp}" "$(sha256sum "${_bp}" 2>/dev/null | awk '{print $1}')"
                done
            } > "${_broker_owner_file}"
            if sudo systemctl enable hefesto-hidraw-broker.service >/dev/null 2>&1; then
                printf '      hefesto-hidraw-broker.service habilitado no boot\n'
            else
                warn "enable do hefesto-hidraw-broker.service falhou — o físico no cabo nasce aberto no boot até o daemon conectar"
            fi
            if sudo systemctl is-active --quiet hefesto-hidraw-broker.service && jogo_em_cena; then
                adiar_para_o_fim_do_jogo broker
                printf '      com um jogo aberto, o broker novo entra quando o jogo fechar\n'
            elif sudo systemctl is-active --quiet hefesto-hidraw-broker.service; then
                _marca=/run/hefesto-hidraw-broker/reinicio-sem-abrir
                if sudo install -Dm0644 -o root -g root /dev/null "${_marca}" 2>/dev/null \
                   && sudo systemctl kill -s SIGKILL hefesto-hidraw-broker.service >/dev/null 2>&1 \
                   && sudo systemctl restart hefesto-hidraw-broker.service >/dev/null 2>&1; then
                    printf '      hefesto-hidraw-broker reiniciado com o binário novo, sem abrir os nós\n'
                else
                    warn "o reinício do broker falhou — o piso abre os nós e o doctor diz o gesto"
                    sudo "${_broker_bin_dst}" --restore-all-and-exit >/dev/null 2>&1 || true
                fi
                sudo rm -f "${_marca}"
                cumprir_a_troca broker
            fi
        else
            warn "enable --now do hefesto-hidraw-broker.socket falhou — habilite manualmente"
        fi
    fi
    rm -rf "${_broker_tmp}"
}

install_trava_do_radio_host() {
    local _trava_fonte="${ROOT_DIR}/assets/tmpfiles.d/hefesto-dualsense4unix-radio.conf"
    local _trava_conf=/etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf
    local _trava_quem
    if [[ "${SKIP_UDEV}" -eq 1 ]]; then
        printf '      pulado (--no-udev) — o daemon segue com a trava da sessão, que o watchdog root não enxerga\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — a trava comum do rádio NÃO foi criada (o watchdog e o daemon não se enxergam)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — a trava comum do rádio pulada (re-execute ./install.sh)"
        return 0
    fi
    if ! command -v systemd-tmpfiles >/dev/null 2>&1; then
        warn "systemd-tmpfiles ausente — a trava comum do rádio NÃO foi criada (o watchdog e o daemon seguem cada um com a sua)"
        return 0
    fi
    if ! getent group hefesto >/dev/null 2>&1; then
        warn "o grupo 'hefesto' não existe (quem o cria são as regras udev: sudo bash scripts/install_udev.sh) — a trava comum do rádio NÃO foi criada"
        return 0
    fi
    if ! sudo install -Dm644 -o root -g root "${_trava_fonte}" \
            /etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf 2>/dev/null; then
        warn "não consegui gravar ${_trava_conf} — a trava comum do rádio NÃO foi criada"
        return 0
    fi
    if ! sudo systemd-tmpfiles --create /etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf >/dev/null 2>&1; then
        warn "systemd-tmpfiles --create falhou — a trava comum do rádio nasce no próximo boot"
        return 0
    fi
    printf '      trava comum do rádio de pé: /run/hefesto-dualsense4unix/radio.lock (0660, grupo hefesto) — o watchdog e o daemon disputam o mesmo arquivo\n'
    _trava_quem="${SUDO_USER:-$(id -un)}"
    local _trava_no_disco _trava_agora
    _trava_no_disco=" $(id -nG "${_trava_quem}" 2>/dev/null || true) "
    _trava_agora=" $(id -nG 2>/dev/null || true) "
    if [[ "${_trava_no_disco}" == *" hefesto "* && "${_trava_agora}" != *" hefesto "* ]]; then
        printf '        (você entrou no grupo hefesto agora: o daemon escreve o próprio nome na trava depois de sair e entrar na sessão; até lá ele a usa só para ler, e a fila funciona igual)\n'
    fi
    return 0
}

_render_dropin_do_watchdog() {
    local casa="$1" saida="$2"
    [[ "${casa}" =~ ^/[A-Za-z0-9._@+/-]+$ && "${casa}" != "/" ]] || return 1
    cat > "${saida}" <<DROPIN
# instalado por hefesto-dualsense4unix (install.sh) — remoção: uninstall.sh
# O watchdog do Bluetooth enxerga UM arquivo da casa de quem instalou: o
# maquina.json, de onde o bt_active_mode.sh lê o nome de cada lugar. A unit
# roda com ProtectHome=tmpfs; este bind é o único furo, e só de leitura.
[Service]
BindReadOnlyPaths=-${casa}/.config/hefesto-dualsense4unix/maquina.json
DROPIN
}

_ferramentas_que_faltam_ao_nome_do_lugar() {
    local caminho="${1:-}" f d achou pastas=()
    if [[ -z "${caminho}" ]]; then
        caminho="$(systemd-path search-binaries-default 2>/dev/null || true)"
        [[ -n "${caminho}" ]] || caminho=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
    fi
    IFS=: read -r -a pastas <<<"${caminho}"
    for f in python3 udevadm getent; do
        achou=0
        for d in ${pastas[@]+"${pastas[@]}"}; do
            [[ -n "${d}" && -x "${d}/${f}" ]] && { achou=1; break; }
        done
        [[ "${achou}" -eq 1 ]] || printf '%s\n' "${f}"
    done
}

install_bt_resilience_host() {
    if [[ "${SKIP_UDEV}" -eq 1 ]]; then
        printf '      resiliência do bluetoothd pulada (--no-udev) — sem os alvos, as regras 82 e 83 ficam INERTES pelo TEST== delas\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — resiliência do bluetoothd NÃO instalada (o crash do bluetoothd volta a comer bonds sem cópia)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — resiliência do bluetoothd pulada (re-execute ./install.sh)"
        return 0
    fi
    _btres_ok=1
    for _btres_s in bt_bonds_snapshot.sh bt_bonds_restore.sh bt_bonds_autorestore.sh bt_health_watchdog.sh bt_crash_capture.sh bt_active_mode.sh bt_nosniff_now.sh bt_rebind_orphans.sh; do
        sudo install -Dm755 "${ROOT_DIR}/scripts/${_btres_s}" \
            "/usr/local/lib/hefesto-dualsense4unix/${_btres_s}" 2>/dev/null || _btres_ok=0
    done
    sudo /usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh 2>/dev/null || true
    local _btres_falta
    _btres_falta="$(_ferramentas_que_faltam_ao_nome_do_lugar | tr '\n' ' ')"
    if [[ -n "${_btres_falta// /}" ]]; then
        warn "falta ${_btres_falta% } no PATH do root — o nome do lugar não chega aos adaptadores (o resto da resiliência vale)"
    fi
    sudo install -Dm644 "${ROOT_DIR}/assets/systemd/bluetooth-dropin-10-hefesto-resilience.conf" \
        /etc/systemd/system/bluetooth.service.d/10-hefesto-resilience.conf 2>/dev/null || _btres_ok=0
    for _btres_u in hefesto-bt-bonds-snapshot.service hefesto-bt-bonds-snapshot.timer \
                    hefesto-bt-health-watchdog.service hefesto-bt-health-watchdog.timer; do
        sudo install -Dm644 "${ROOT_DIR}/assets/systemd/${_btres_u}" \
            "/etc/systemd/system/${_btres_u}" 2>/dev/null || _btres_ok=0
    done
    local _btres_dropin
    _btres_dropin="$(mktemp)"
    if _render_dropin_do_watchdog "${HOME}" "${_btres_dropin}"; then
        sudo install -Dm644 "${_btres_dropin}" \
            /etc/systemd/system/hefesto-bt-health-watchdog.service.d/10-hefesto-maquina.conf \
            2>/dev/null || _btres_ok=0
    else
        warn "a casa '${HOME}' tem caractere que o systemd lê como separador — o watchdog do Bluetooth segue sem ver o nome dos lugares (o bluetoothd, no start, vê)"
    fi
    rm -f "${_btres_dropin}"
    sudo install -d -m700 /var/lib/hefesto-dualsense4unix/bt-bonds 2>/dev/null || true
    sudo systemctl daemon-reload >/dev/null 2>&1 || true
    if sudo systemctl enable --now hefesto-bt-bonds-snapshot.timer \
            hefesto-bt-health-watchdog.timer >/dev/null 2>&1; then
        printf '      timers ativos: snapshot de bonds (15 em 15 min) + watchdog de saúde (2 em 2 min)\n'
    else
        warn "enable dos timers de resiliência falhou — habilite manualmente (systemctl enable --now hefesto-bt-*.timer)"
        _btres_ok=0
    fi
    if [[ "${_btres_ok}" -eq 1 ]]; then
        printf '      drop-in de resiliência instalado (Restart reafirmado + WatchdogSec=0 + snapshot na parada)\n'
        printf '      restauro AUTOMÁTICO de bonds armado: se o bluetoothd morrer, os bonds que\n'
        printf '        ele comeu voltam sozinhos antes do próximo start (aditivo; nunca por cima\n'
        printf '        de chave viva). Nada a digitar, nenhum sudo.\n'
        printf '      as regras udev 82 e 83 acharam os alvos do RUN+= delas (no-sniff na borda + snapshot na conexão)\n'
        printf '      vale no próximo restart do bluetoothd; captura forense é OPT-IN: bt_crash_capture.sh --on\n'
    else
        warn "resiliência do bluetoothd instalada PARCIALMENTE — confira as mensagens acima"
    fi
}

_garantir_a_conta_no_grupo_hefesto() {
    local conta="$1"
    getent group hefesto >/dev/null 2>&1 \
        || sudo groupadd -f -r hefesto 2>/dev/null || return 1
    if [[ ",$(getent group hefesto | cut -d: -f4)," != *",${conta},"* ]]; then
        sudo usermod -aG hefesto "${conta}" 2>/dev/null || return 1
    fi
    return 0
}

install_bt_ponte_privilegiada_host() {
    local _ponte_fonte="${ROOT_DIR}/scripts/bt_ponte_privilegiada.sh"
    local _ponte_alvo=/usr/local/lib/hefesto-dualsense4unix/bt_ponte_privilegiada.sh
    local _ponte_regra=/etc/sudoers.d/49-hefesto-bt-ponte
    local _ponte_usuaria _ponte_tmp
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — ponte privilegiada do Bluetooth NÃO instalada (mover controle entre dongles seguirá sendo trabalho de terminal)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — ponte privilegiada do Bluetooth pulada (re-execute ./install.sh)"
        return 0
    fi
    _ponte_usuaria="${SUDO_USER:-$(id -un)}"
    if [[ "${_ponte_usuaria}" == "root" ]]; then
        warn "install rodando como root sem SUDO_USER — não sei para quem abrir a ponte; regra do sudoers NÃO gravada (rode ./install.sh como você, sem sudo)"
        return 0
    fi
    if ! sudo install -Dm755 -o root -g root "${_ponte_fonte}" "${_ponte_alvo}" 2>/dev/null; then
        warn "não consegui instalar ${_ponte_alvo} — ponte privilegiada indisponível"
        return 0
    fi
    if ! command -v visudo >/dev/null 2>&1; then
        warn "visudo ausente — a regra do sudoers NÃO foi gravada (sudoers inválido derruba o sudo da máquina inteira; não gravamos sem conferir)"
        return 0
    fi
    _ponte_tmp="$(mktemp)" || {
        warn "não consegui criar arquivo temporário — regra do sudoers NÃO gravada"
        return 0
    }
    if ! _garantir_a_conta_no_grupo_hefesto "${_ponte_usuaria}"; then
        warn "não consegui pôr '${_ponte_usuaria}' no grupo hefesto — regra do sudoers NÃO gravada (a regra é do grupo)"
        rm -f "${_ponte_tmp}"
        return 0
    fi
    if ! bash "${_ponte_alvo}" regra-sudo "%hefesto" "${_ponte_usuaria}" >"${_ponte_tmp}" 2>/dev/null; then
        warn "a ponte recusou gerar a regra para o grupo hefesto — nada gravado em ${_ponte_regra}"
        rm -f "${_ponte_tmp}"
        return 0
    fi
    if ! sudo visudo -cqf "${_ponte_tmp}" 2>/dev/null; then
        warn "a regra gerada NÃO passou no 'visudo -c' — nada gravado em ${_ponte_regra} (o sudo desta máquina segue intacto)"
        rm -f "${_ponte_tmp}"
        return 0
    fi
    if ! sudo install -Dm440 -o root -g root "${_ponte_tmp}" "${_ponte_regra}" 2>/dev/null; then
        warn "não consegui gravar ${_ponte_regra} — a janela vai precisar de senha para mover controle entre dongles"
        rm -f "${_ponte_tmp}"
        return 0
    fi
    rm -f "${_ponte_tmp}"
    printf '      ponte privilegiada instalada: mover controle entre dongles sem digitar senha\n'
    printf '        (%s, NOPASSWD só para o grupo hefesto e para %s; os verbos nomeados um a um, o endereço\n' \
        "${_ponte_regra}" "${_ponte_usuaria}"
    printf '         e o nome novo pelo stdin, e NENHUM verbo que execute comando livre)\n'
    if sudo -n -l -U "${_ponte_usuaria}" "${_ponte_alvo}" adaptadores >/dev/null 2>&1; then
        printf '      conferido no próprio sudo: a regra já vale para %s (não é só arquivo no disco)\n' "${_ponte_usuaria}"
    else
        warn "a regra foi gravada mas o sudo NÃO a reconheceu para ${_ponte_usuaria} — confira ${_ponte_regra} e o '#includedir /etc/sudoers.d' em /etc/sudoers"
    fi
}

install_placa_acordada_host() {
    local _placa_fonte="${ROOT_DIR}/scripts/hefesto_placa_acordada.sh"
    local _placa_alvo=/usr/local/lib/hefesto-dualsense4unix/hefesto_placa_acordada.sh
    local _placa_regra=/etc/sudoers.d/49-hefesto-placa
    local _placa_usuaria _placa_tmp
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — a placa acordada NÃO instalada (jogo leve segue com o clock que o driver escolher)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — a placa acordada pulada (re-execute ./install.sh)"
        return 0
    fi
    _placa_usuaria="${SUDO_USER:-$(id -un)}"
    if [[ "${_placa_usuaria}" == "root" ]]; then
        warn "install rodando como root sem SUDO_USER — não sei para quem abrir a placa acordada; regra do sudoers NÃO gravada (rode ./install.sh como você, sem sudo)"
        return 0
    fi
    if ! sudo install -Dm755 -o root -g root "${_placa_fonte}" "${_placa_alvo}" 2>/dev/null; then
        warn "não consegui instalar ${_placa_alvo} — a placa acordada indisponível"
        return 0
    fi
    if ! command -v visudo >/dev/null 2>&1; then
        warn "visudo ausente — a regra do sudoers da placa NÃO foi gravada (sudoers inválido derruba o sudo da máquina inteira; não gravamos sem conferir)"
        return 0
    fi
    _placa_tmp="$(mktemp)" || {
        warn "não consegui criar arquivo temporário — regra da placa NÃO gravada"
        return 0
    }
    if ! bash "${_placa_alvo}" regra-sudo "${_placa_usuaria}" >"${_placa_tmp}" 2>/dev/null; then
        warn "o script da placa recusou gerar a regra para '${_placa_usuaria}' — nada gravado em ${_placa_regra}"
        rm -f "${_placa_tmp}"
        return 0
    fi
    if ! sudo visudo -cqf "${_placa_tmp}" 2>/dev/null; then
        warn "a regra da placa NÃO passou no 'visudo -c' — nada gravado em ${_placa_regra} (o sudo desta máquina segue intacto)"
        rm -f "${_placa_tmp}"
        return 0
    fi
    if ! sudo install -Dm440 -o root -g root "${_placa_tmp}" "${_placa_regra}" 2>/dev/null; then
        warn "não consegui gravar ${_placa_regra} — o lançador não vai acordar a placa"
        rm -f "${_placa_tmp}"
        return 0
    fi
    rm -f "${_placa_tmp}"
    printf '      placa acordada instalada: o jogo pede o piso de clock da placa e o devolve ao sair\n'
    printf '        (%s, NOPASSWD só para %s, três verbos e o PID pelo stdin)\n' \
        "${_placa_regra}" "${_placa_usuaria}"
    if sudo -n -l -U "${_placa_usuaria}" "${_placa_alvo}" estado >/dev/null 2>&1; then
        printf '      conferido no próprio sudo: a regra já vale para %s (não é só arquivo no disco)\n' "${_placa_usuaria}"
    else
        warn "a regra da placa foi gravada mas o sudo NÃO a reconheceu para ${_placa_usuaria} — confira ${_placa_regra} e o '#includedir /etc/sudoers.d' em /etc/sudoers"
    fi
}

install_censo_do_gabinete_host() {
    local _gab_alvo="${HOME}/.local/state/hefesto-dualsense4unix/gabinete.json"
    local _gab_tmp _gab_saida
    if ! command -v python3 >/dev/null 2>&1; then
        warn "python3 ausente — censo do gabinete pulado (a aba Conexões vai pedir os números à mão, e funciona assim)"
        return 0
    fi
    _gab_tmp="$(mktemp)" || {
        warn "não consegui criar arquivo temporário — censo do gabinete pulado"
        return 0
    }
    if ! command -v dmidecode >/dev/null 2>&1; then
        warn "dmidecode ausente — o censo sai só com o barramento; a BIOS não foi consultada"
    elif ! command -v sudo >/dev/null 2>&1 || ! sudo -n true 2>/dev/null; then
        warn "sem root agora — a tabela de conectores da BIOS não foi lida; o censo sai com o barramento e a aba pergunta o resto (re-execute ./install.sh)"
    else
        # shellcheck disable=SC2024
        sudo -n dmidecode -t 8 >"${_gab_tmp}" 2>/dev/null || : >"${_gab_tmp}"
    fi
    _gab_saida="$(python3 - "${ROOT_DIR}" "${_gab_tmp}" "${_gab_alvo}" <<'PYEOF'
import os
import sys

raiz, texto_bruto, alvo = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, os.path.join(raiz, "src"))
from hefesto_dualsense4unix.integrations import censo_do_gabinete as cdg

try:
    with open(texto_bruto, encoding="utf-8", errors="ignore") as arquivo:
        do_dmidecode = arquivo.read()
except OSError:
    do_dmidecode = ""

censo = cdg.ler_o_gabinete(dmidecode=do_dmidecode)
censo = cdg.preservar_o_que_ela_disse(censo, cdg.ler_do_disco(alvo), cdg.ler_a_placa())
cdg.gravar(censo, alvo)
if censo.get("substituiu_outra_placa"):
    print("censo anterior era de OUTRA placa — substituído")
print(cdg.resumo(censo))
PYEOF
)" || _gab_saida=""
    rm -f "${_gab_tmp}"
    if [[ -s "${_gab_alvo}" ]]; then
        printf '      censo do gabinete gravado: %s\n' "${_gab_alvo}"
        while IFS= read -r _gab_linha; do
            [[ -n "${_gab_linha}" ]] && printf '        %s\n' "${_gab_linha}"
        done <<<"${_gab_saida}"
    else
        warn "não consegui gravar ${_gab_alvo} — a aba Conexões vai abrir pedindo os números à mão (e funciona assim)"
    fi
}

_distro_so_leitura() {
    declare -F _familia_pacotes >/dev/null 2>&1 || return 1
    [[ "$(_familia_pacotes)" == "imutavel" ]]
}

_efeito_so_leitura() {
    case "$1" in
        playstation) printf 'o microfone do DualSense pelo rádio fica desligado (vale o driver de fábrica, sem as curas da casa)' ;;
        nintendo)    printf 'o controle da Nintendo pode não subir pelo rádio (vale o driver de fábrica)' ;;
        rtw88)       printf 'o dongle Wi-Fi USB não ganha a cura do fantasma USB (vale o driver de fábrica)' ;;
        uhid)        printf 'o uhid de fábrica segue, sem a contrapressão' ;;
        usb_f_hid)   printf 'o usb_f_hid de fábrica segue: o jogo no Proton espera 5 s por pedido de feature e pode perder os controles virtuais' ;;
        initramfs)   printf 'nenhum módulo da casa entra, então não há o que regenerar' ;;
        ucm)         printf 'a vibração dos jogos da Sony pelo cabo depende do perfil UCM que a própria imagem trouxer' ;;
    esac
}

_pula_por_so_leitura() {
    _distro_so_leitura || return 1
    printf '      pulado (distro somente leitura) — %s\n' "$(_efeito_so_leitura "$1")"
}

install_dkms_hid_nintendo_host() {
    _pula_por_so_leitura nintendo && return 0
    if [[ "${NO_DKMS}" -eq 1 ]]; then
        printf '      pulado (--no-dkms)\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — patch DKMS do hid-nintendo NÃO instalado (driver in-tree continua, fail-safe)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — patch DKMS do hid-nintendo pulado (re-execute ./install.sh)"
        return 0
    fi
    # shellcheck source=scripts/dkms_lib.sh
    source "${ROOT_DIR}/scripts/dkms_lib.sh"
    dkms_warn_secureboot_once
    local _hidn_src="${ROOT_DIR}/assets/dkms/hid-nintendo"
    dkms_install_patched_module hefesto-hid-nintendo \
        "$(dkms_pkg_version "${_hidn_src}")" "${_hidn_src}" hid-nintendo
    local _hidn_conf="${ROOT_DIR}/assets/modprobe.d/hefesto-hid-nintendo.conf" _v _v2
    if sudo install -Dm644 "${ROOT_DIR}/assets/modprobe.d/hefesto-hid-nintendo.conf" \
            /etc/modprobe.d/hefesto-hid-nintendo.conf 2>/dev/null; then
        printf '      opções instaladas em /etc/modprobe.d/hefesto-hid-nintendo.conf (bt_probe_retries=%s + skip_tx_on_rate_exceeded=%s)\n' \
            "$(opcao_do_modprobe "${_hidn_conf}" bt_probe_retries)" \
            "$(opcao_do_modprobe "${_hidn_conf}" skip_tx_on_rate_exceeded)"
    else
        warn "não consegui gravar /etc/modprobe.d/hefesto-hid-nintendo.conf"
    fi
    if ! dkms_module_from_updates hid-nintendo; then
        warn "patch DKMS do hid-nintendo NÃO ficou staged (veja avisos acima) — driver in-tree continua (fail-safe); a conf do modprobe.d é inerte com o in-tree ('unknown parameter ignored')"
        return 0
    fi
    if modulo_pede_reinicio hid-nintendo; then
        anotar_reinicio_pendente "o driver dos controles Nintendo (hid-nintendo)"
    fi
    if [[ -d /sys/module/hid_nintendo/parameters ]]; then
        printf '      módulo patchado JÁ carregado (params visíveis em /sys/module/hid_nintendo/parameters)\n'
        if [[ -e /sys/module/hid_nintendo/parameters/bt_probe_retries ]]; then
            if _v="$(opcao_do_modprobe "${_hidn_conf}" bt_probe_retries)" \
               && _v2="$(opcao_do_modprobe "${_hidn_conf}" skip_tx_on_rate_exceeded)" \
               && printf '%s' "${_v}" | sudo tee /sys/module/hid_nintendo/parameters/bt_probe_retries >/dev/null 2>&1 \
               && printf '%s' "${_v2}" | sudo tee /sys/module/hid_nintendo/parameters/skip_tx_on_rate_exceeded >/dev/null 2>&1; then
                printf '      params aplicados a quente (valem no próximo plug, sem reboot)\n'
            else
                warn "não consegui escrever os params do hid-nintendo a quente — valem no próximo boot"
            fi
        fi
        if [[ -e /sys/module/hid_nintendo/parameters/usb_cmd_pad_to_report ]]; then
            _v="$(opcao_do_modprobe "${_hidn_conf}" usb_cmd_pad_to_report)" \
                && printf '%s' "${_v}" | sudo tee /sys/module/hid_nintendo/parameters/usb_cmd_pad_to_report >/dev/null 2>&1 || true
            _v="$(opcao_do_modprobe "${_hidn_conf}" usb_send_conn_status)" \
                && printf '%s' "${_v}" | sudo tee /sys/module/hid_nintendo/parameters/usb_send_conn_status >/dev/null 2>&1 || true
            _v="$(opcao_do_modprobe "${_hidn_conf}" usb_probe_degrade)" \
                && printf '%s' "${_v}" | sudo tee /sys/module/hid_nintendo/parameters/usb_probe_degrade >/dev/null 2>&1 || true
            printf '      handshake USB do clone rearmado a quente (vale no próximo plug)\n'
        fi
    elif [[ -d /sys/module/hid_nintendo ]]; then
        printf '      módulo in-tree em uso — NÃO recarregamos (derrubaria Pro/8BitDo conectados);\n'
        printf '      o patchado vale no próximo boot (replug re-liga no módulo já carregado)\n'
    else
        printf '      hid_nintendo descarregado — o patchado entra sozinho no próximo plug\n'
    fi
    return 0
}

install_dkms_uhid_host() {
    _pula_por_so_leitura uhid && return 0
    if [[ "${COM_UHID_CONTRAPRESSAO:-0}" -ne 1 ]]; then
        printf '      pulado (opt-in: ./install.sh --uhid-contrapressao)\n'
        return 0
    fi
    if [[ "${NO_DKMS}" -eq 1 ]]; then
        printf '      pulado (--no-dkms)\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — uhid com contrapressão NÃO instalado (o de fábrica continua, fail-safe)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — uhid com contrapressão pulado (re-execute ./install.sh --uhid-contrapressao)"
        return 0
    fi
    # shellcheck source=scripts/dkms_lib.sh
    source "${ROOT_DIR}/scripts/dkms_lib.sh"
    dkms_warn_secureboot_once
    local _uhid_src="${ROOT_DIR}/assets/dkms/uhid"
    dkms_install_patched_module hefesto-uhid \
        "$(dkms_pkg_version "${_uhid_src}")" "${_uhid_src}" uhid
    if ! dkms_module_from_updates uhid; then
        warn "uhid patchado NÃO ficou staged (veja avisos acima) — o de fábrica continua (fail-safe), e a conf do modprobe.d seria inerte nele"
        return 0
    fi
    if modulo_pede_reinicio uhid; then
        anotar_reinicio_pendente "o uhid com contrapressão"
    fi
    if sudo install -Dm644 "${ROOT_DIR}/assets/modprobe.d/hefesto-uhid.conf" \
            /etc/modprobe.d/hefesto-uhid.conf 2>/dev/null; then
        printf '      contrapressão pedida em /etc/modprobe.d/hefesto-uhid.conf\n'
    else
        warn "não consegui gravar /etc/modprobe.d/hefesto-uhid.conf"
    fi
    if [[ -e /sys/module/uhid/parameters/backpressure ]]; then
        local _v
        if _v="$(opcao_do_modprobe "${ROOT_DIR}/assets/modprobe.d/hefesto-uhid.conf" backpressure)" \
           && printf '%s' "${_v}" | sudo tee /sys/module/uhid/parameters/backpressure >/dev/null 2>&1; then
            printf '      módulo patchado JÁ carregado — contrapressão ligada a quente (vale já, sem recarregar o uhid)\n'
        else
            warn "não consegui ligar a contrapressão a quente — ela vale no próximo boot, pela conf do modprobe.d"
        fi
    else
        printf '      o de fábrica está carregado — o patchado entra no PRÓXIMO BOOT (recarregar o uhid derrubaria todo HID por Bluetooth)\n'
    fi
    return 0
}

install_dkms_hid_playstation_host() {
    _pula_por_so_leitura playstation && return 0
    if [[ "${NO_DKMS}" -eq 1 ]]; then
        printf '      pulado (--no-dkms)\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — patch DKMS do hid-playstation NÃO instalado (driver in-tree continua, fail-safe)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — patch DKMS do hid-playstation pulado (re-execute ./install.sh)"
        return 0
    fi
    # shellcheck source=scripts/dkms_lib.sh
    source "${ROOT_DIR}/scripts/dkms_lib.sh"
    dkms_warn_secureboot_once
    local _hidp_src="${ROOT_DIR}/assets/dkms/hid-playstation"
    dkms_install_patched_module hefesto-hid-playstation \
        "$(dkms_pkg_version "${_hidp_src}")" "${_hidp_src}" hid-playstation
    local _hidp_conf="${ROOT_DIR}/assets/modprobe.d/hefesto-hid-playstation.conf" _v
    if sudo install -Dm644 "${ROOT_DIR}/assets/modprobe.d/hefesto-hid-playstation.conf" \
            /etc/modprobe.d/hefesto-hid-playstation.conf 2>/dev/null; then
        printf '      opções instaladas em /etc/modprobe.d/hefesto-hid-playstation.conf (feature_retries=%s + ds4_* do clone no cabo)\n' \
            "$(opcao_do_modprobe "${_hidp_conf}" feature_retries)"
    else
        warn "não consegui gravar /etc/modprobe.d/hefesto-hid-playstation.conf"
    fi
    if ! dkms_module_from_updates hid-playstation; then
        warn "patch DKMS do hid-playstation NÃO ficou staged (veja avisos acima) — o driver de fábrica continua (fail-safe): o microfone do DualSense pelo rádio fica desligado, porque o de fábrica leria o áudio como botão e mexeria o cursor, e o 2º DualSense segue podendo se perder na probe; a conf do modprobe.d é inerte com ele ('unknown parameter ignored')"
        return 0
    fi
    if modulo_pede_reinicio hid-playstation; then
        anotar_reinicio_pendente "o driver do DualSense (hid-playstation)"
    fi
    if [[ -e /sys/module/hid_playstation/parameters/feature_retries ]]; then
        printf '      módulo patchado JÁ carregado (feature_retries visível em /sys/module/hid_playstation/parameters)\n'
        if [[ -e /sys/module/hid_playstation/parameters/feature_retries ]]; then
            if _v="$(opcao_do_modprobe "${_hidp_conf}" feature_retries)" \
               && printf '%s' "${_v}" | sudo tee /sys/module/hid_playstation/parameters/feature_retries >/dev/null 2>&1; then
                printf '      feature_retries=%s aplicado a quente (vale na próxima conexão, sem reboot)\n' "${_v}"
            else
                warn "não consegui escrever feature_retries a quente — vale no próximo boot"
            fi
        fi
        if [[ -e /sys/module/hid_playstation/parameters/ds4_short_pairing_info ]]; then
            if _v="$(opcao_do_modprobe "${_hidp_conf}" ds4_short_pairing_info)" \
               && printf '%s' "${_v}" | sudo tee /sys/module/hid_playstation/parameters/ds4_short_pairing_info >/dev/null 2>&1; then
                printf '      ds4_short_pairing_info aplicado a quente (clone no cabo; vale no próximo plug)\n'
            else
                warn "não consegui escrever ds4_short_pairing_info a quente — vale no próximo boot"
            fi
        fi
        if [[ -e /sys/module/hid_playstation/parameters/ds4_synthetic_mac ]]; then
            if _v="$(opcao_do_modprobe "${_hidp_conf}" ds4_synthetic_mac)" \
               && printf '%s' "${_v}" | sudo tee /sys/module/hid_playstation/parameters/ds4_synthetic_mac >/dev/null 2>&1; then
                printf '      ds4_synthetic_mac aplicado a quente (clone no cabo; vale no próximo plug)\n'
            else
                warn "não consegui escrever ds4_synthetic_mac a quente — vale no próximo boot"
            fi
        fi
    elif [[ -d /sys/module/hid_playstation ]]; then
        printf '      módulo in-tree em uso — NÃO recarregamos (derrubaria os DualSense, inclusive os por BT);\n'
        printf '      o patchado vale no próximo boot (reconectar NÃO troca módulo carregado)\n'
    else
        printf '      hid_playstation descarregado — o patchado entra sozinho na próxima conexão\n'
    fi
    return 0
}

install_dkms_usb_f_hid_host() {
    _pula_por_so_leitura usb_f_hid && return 0
    if [[ "${NO_DKMS}" -eq 1 ]]; then
        printf '      pulado (--no-dkms)\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — usb_f_hid patchado NÃO instalado (o de fábrica continua: o jogo no Proton espera 5 s por pedido de feature)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — usb_f_hid patchado pulado (re-execute ./install.sh)"
        return 0
    fi
    # shellcheck source=scripts/dkms_lib.sh
    source "${ROOT_DIR}/scripts/dkms_lib.sh"
    dkms_warn_secureboot_once
    local _fhid_src="${ROOT_DIR}/assets/dkms/usb-f-hid"
    dkms_install_patched_module hefesto-usb-f-hid \
        "$(dkms_pkg_version "${_fhid_src}")" "${_fhid_src}" usb_f_hid
    if ! dkms_module_from_updates usb_f_hid; then
        warn "usb_f_hid patchado NÃO ficou staged (veja avisos acima; fora dos KERNELS_VALIDADOS de assets/dkms/usb-f-hid/patch/BASELINE o DKMS pula) — o de fábrica continua, e o jogo no Proton espera 5 s por pedido de feature"
        return 0
    fi
    trocar_usb_f_hid_a_quente
    return 0
}

_usb_f_hid_tem_a_marca() {
    [[ -e "${HEFESTO_SYS_MODULE:-/sys/module}/usb_f_hid/parameters/get_report_sized" ]]
}

_usb_f_hid_refcnt() {
    cat "${HEFESTO_SYS_MODULE:-/sys/module}/usb_f_hid/refcnt" 2>/dev/null || printf '?'
}

trocar_usb_f_hid_a_quente() {
    local _sys="${HEFESTO_SYS_MODULE:-/sys/module}"
    local _gadgets="${HEFESTO_USB_GADGET_ROOT:-/sys/kernel/config/usb_gadget}"
    local _prazo="${HEFESTO_USB_F_HID_PRAZO_S:-15}"
    local _servico="hefesto-dualsense4unix.service"
    local _pendente="a função HID dos pads USB virtuais (usb_f_hid)"
    if [[ ! -d "${_sys}/usb_f_hid" ]]; then
        printf '      usb_f_hid descarregado — o curado entra no próximo carregamento\n'
        return 0
    fi
    if _usb_f_hid_tem_a_marca; then
        printf '      usb_f_hid curado JÁ carregado (get_report_sized visível) — nada a trocar\n'
        return 0
    fi
    local _g _nome _alheios="" _nossos=0
    for _g in "${_gadgets}"/*/; do
        [[ -d "${_g}" ]] || continue
        compgen -G "${_g}functions/hid.*" >/dev/null || continue
        _nome="$(basename "${_g}")"
        case "${_nome}" in
            hefesto-pad-*) _nossos=$((_nossos + 1)) ;;
            *) _alheios="${_alheios:+${_alheios} }${_nome}" ;;
        esac
    done
    if [[ -n "${_alheios}" ]]; then
        warn "o usb_f_hid de fábrica serve um gadget que não é do Hefesto (${_alheios}) — não troco; o curado vale no próximo boot"
        anotar_reinicio_pendente "${_pendente}"
        return 0
    fi
    local _daemon_parado=0 _espera=0
    if [[ "$(_usb_f_hid_refcnt)" != "0" ]]; then
        if [[ "${_nossos}" -eq 0 ]]; then
            warn "o usb_f_hid de fábrica está preso (refcnt $(_usb_f_hid_refcnt)) sem gadget do Hefesto — não troco; o curado vale no próximo boot"
            anotar_reinicio_pendente "${_pendente}"
            return 0
        fi
        if jogo_em_cena; then
            printf '      com um jogo aberto, os pads USB virtuais ficam de pé: o usb_f_hid curado vale no próximo boot\n'
            anotar_reinicio_pendente "${_pendente}"
            return 0
        fi
        if systemctl --user is-active --quiet "${_servico}" 2>/dev/null; then
            printf '      %s pad(s) USB virtual(is) no ar — paro o daemon para o broker soltá-los\n' "${_nossos}"
            systemctl --user stop "${_servico}" 2>/dev/null && _daemon_parado=1
        fi
        while [[ "$(_usb_f_hid_refcnt)" != "0" && "${_espera}" -lt $((_prazo * 2)) ]]; do
            sleep 0.5
            _espera=$((_espera + 1))
        done
    fi
    if [[ "$(_usb_f_hid_refcnt)" != "0" ]]; then
        warn "os pads USB virtuais não se soltaram em ${_prazo} s (refcnt $(_usb_f_hid_refcnt)) — não troco; o curado vale no próximo boot"
        anotar_reinicio_pendente "${_pendente}"
    elif sudo modprobe -r usb_f_hid 2>/dev/null && sudo modprobe usb_f_hid 2>/dev/null \
         && _usb_f_hid_tem_a_marca; then
        printf '      usb_f_hid trocado a quente: o curado já responde o GET_REPORT no tamanho certo\n'
    else
        warn "não consegui trocar o usb_f_hid a quente — o curado vale no próximo boot"
        anotar_reinicio_pendente "${_pendente}"
    fi
    if [[ "${_daemon_parado}" -eq 1 ]]; then
        systemctl --user start "${_servico}" 2>/dev/null \
            || warn "não consegui subir o ${_servico} de volta — systemctl --user start ${_servico}"
    fi
    return 0
}

flush_initramfs_host() {
    _pula_por_so_leitura initramfs && return 0
    if [[ "${NO_DKMS}" -eq 1 ]]; then
        printf '      pulado (--no-dkms)\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1 || ! sudo -n true 2>/dev/null; then
        warn "sudo indisponível — initramfs NÃO regenerado; se um módulo DKMS mudou, o próximo boot ainda carrega a cópia antiga (rode: sudo update-initramfs -u)"
        return 0
    fi
    # shellcheck source=scripts/dkms_lib.sh
    source "${ROOT_DIR}/scripts/dkms_lib.sh"
    dkms_flush_initramfs
    return 0
}

_rtw88_adaptadores_presentes() {
    local raiz="${HEFESTO_USB_SYS:-/sys}/bus/usb/devices" ifc dev alias mods mp achou=1
    mp="${HEFESTO_MODPROBE:-$(command -v modprobe 2>/dev/null || true)}"
    if [[ -z "${mp}" && -z "${HEFESTO_MODPROBE:-}" ]]; then
        for dev in /usr/sbin/modprobe /sbin/modprobe; do
            if [[ -x "${dev}" ]]; then mp="${dev}"; break; fi
        done
    fi
    [[ -n "${mp}" && -x "${mp}" ]] || return 2
    for ifc in "${raiz}"/*:*; do
        [[ -r "${ifc}/modalias" ]] || continue
        [[ "$(cat "${ifc}/bInterfaceClass" 2>/dev/null)" == "ff" ]] || continue
        alias="$(cat "${ifc}/modalias" 2>/dev/null)"
        mods="$("${mp}" -R "${alias}" 2>/dev/null)" || continue
        grep -Eq '^rtw(88)?_[0-9a-z]+u$' <<<"${mods}" || continue
        dev="${ifc%:*}"
        printf '%s:%s\n' "$(cat "${dev}/idVendor" 2>/dev/null)" "$(cat "${dev}/idProduct" 2>/dev/null)"
        achou=0
    done
    return "${achou}"
}

install_dkms_rtw88_usb_host() {
    _pula_por_so_leitura rtw88 && return 0
    if [[ "${NO_DKMS}" -eq 1 ]]; then
        printf '      pulado (--no-dkms)\n'
        return 0
    fi
    local _rtw_achados _rtw_rc=0
    _rtw_achados="$(_rtw88_adaptadores_presentes)" || _rtw_rc=$?
    case "${_rtw_rc}" in
        0) printf '      adaptador Wi-Fi USB Realtek (rtw88) presente: %s\n' "$(tr '\n' ' ' <<<"${_rtw_achados}" | sed 's/ $//')" ;;
        1) printf '      pulado — nenhum adaptador Wi-Fi USB que o rtw88_usb atenda nesta máquina (o patch cura o fantasma USB desse dongle); se plugar um, rode ./install.sh de novo\n'
           return 0 ;;
        *) printf '      pulado — não consegui perguntar ao kernel quais adaptadores o rtw88_usb atende (a ferramenta de módulos não respondeu); rode ./install.sh de novo num ambiente que a tenha\n'
           return 0 ;;
    esac
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — patch DKMS do rtw88_usb NÃO instalado (driver in-tree continua, fail-safe)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — patch DKMS do rtw88_usb pulado (re-execute ./install.sh)"
        return 0
    fi
    # shellcheck source=scripts/dkms_lib.sh
    source "${ROOT_DIR}/scripts/dkms_lib.sh"
    dkms_warn_secureboot_once
    local _rtw_src="${ROOT_DIR}/assets/dkms/rtw88-usb"
    dkms_install_patched_module hefesto-rtw88-usb \
        "$(dkms_pkg_version "${_rtw_src}")" "${_rtw_src}" rtw88_usb
    if ! dkms_module_from_updates rtw88_usb; then
        warn "patch DKMS do rtw88_usb NÃO ficou staged (veja avisos acima) — driver in-tree continua (fail-safe); sem device-gone/port-reset, o fantasma USB do dongle (device retido após disconnect perdido) segue possível"
        return 0
    fi
    if modulo_pede_reinicio rtw88_usb; then
        anotar_reinicio_pendente "o driver do Wi-Fi USB (rtw88_usb)"
    fi
    if [[ -e /sys/module/rtw88_usb/parameters/hang_reset ]]; then
        printf '      módulo patchado JÁ carregado (hang_reset visível em /sys/module/rtw88_usb/parameters)\n'
        printf 'Y' | sudo tee /sys/module/rtw88_usb/parameters/hang_reset >/dev/null 2>&1 || true
    elif [[ -d /sys/module/rtw88_usb ]]; then
        printf '      módulo in-tree em uso — NÃO recarregamos (derrubaria o WiFi ao vivo);\n'
        printf '      o patchado vale no próximo boot (replug NÃO troca módulo carregado)\n'
    else
        printf '      rtw88_usb descarregado — o patchado entra sozinho no próximo plug do dongle\n'
    fi
    return 0
}

_wifi_usb_agora() {
    bash "${ROOT_DIR}/scripts/wifi_usb.sh" --lista 2>/dev/null || true
}

install_wifi_usb_host() {
    if [[ "${NO_WIFI_USB}" -eq 1 ]]; then
        printf '      pulado (--no-wifi-usb)\n'
        return 0
    fi
    if [[ "${SKIP_UDEV}" -eq 1 ]]; then
        printf '      pulado (--no-udev) — o dongle Wi-Fi USB fica com o scan de fundo do NetworkManager e sem vigia\n'
        return 0
    fi
    if [[ -z "$(_wifi_usb_agora)" ]]; then
        printf '      pulado — nenhuma interface Wi-Fi sob o barramento USB nesta máquina (o vigia só faz falta a quem tem dongle); se plugar um, rode ./install.sh de novo\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — o vigia do Wi-Fi USB NÃO foi instalado"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — o vigia do Wi-Fi USB pulado (re-execute ./install.sh)"
        return 0
    fi
    local _wifi_ok=1 _wifi_u
    sudo install -Dm755 "${ROOT_DIR}/scripts/wifi_usb.sh" \
        /usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh 2>/dev/null || _wifi_ok=0
    if [[ -d "${HEFESTO_NM_ETC:-/etc/NetworkManager}" ]]; then
        sudo install -Dm755 -o root -g root "${ROOT_DIR}/scripts/wifi_usb.sh" \
            /etc/NetworkManager/dispatcher.d/90-hefesto-wifi-usb 2>/dev/null || _wifi_ok=0
    else
        printf '      sem NetworkManager nesta máquina — o dispatcher não vai; o vigia faz o reforço sozinho\n'
    fi
    for _wifi_u in hefesto-wifi-usb-vigia.service hefesto-wifi-usb-vigia.timer; do
        sudo install -Dm644 "${ROOT_DIR}/assets/systemd/${_wifi_u}" \
            "/etc/systemd/system/${_wifi_u}" 2>/dev/null || _wifi_ok=0
    done
    sudo systemctl daemon-reload >/dev/null 2>&1 || true
    if sudo systemctl enable --now hefesto-wifi-usb-vigia.timer >/dev/null 2>&1; then
        printf '      vigia do Wi-Fi USB ativo (1 em 1 min): scan de fundo desligado e a porta reiniciada no travamento mudo\n'
    else
        warn "enable do hefesto-wifi-usb-vigia.timer falhou — habilite: sudo systemctl enable --now hefesto-wifi-usb-vigia.timer"
        _wifi_ok=0
    fi
    { sudo /usr/local/lib/hefesto-dualsense4unix/wifi_usb.sh --ensure 2>&1 || true; } \
        | sed 's/^/      /' || true
    [[ "${_wifi_ok}" -eq 1 ]] || warn "vigia do Wi-Fi USB instalado PARCIALMENTE — confira as mensagens acima"
    return 0
}

_DESEMPENHO_QUER=""

_desempenho_tem_bateria() {
    compgen -G "${HEFESTO_DESEMPENHO_SYS:-/sys}/class/power_supply/BAT*" >/dev/null 2>&1
}

_desempenho_decidir() {
    case "${DESEMPENHO_PEDIDO}" in
        sim|sem) _DESEMPENHO_QUER="${DESEMPENHO_PEDIDO}"; return 0 ;;
    esac
    local padrao="y" quem="um computador sem bateria"
    if _desempenho_tem_bateria; then
        padrao="n"
        quem="um computador com bateria"
    fi
    printf '      Modo desempenho: o perfil de energia fica em Performance para jogar (custa bateria fora da tomada).\n'
    printf '      Esta máquina é %s: o padrão é "%s".\n' "${quem}" "$([[ "${padrao}" == "y" ]] && echo sim || echo não)"
    if declare -F ask_yn >/dev/null 2>&1; then
        ask_yn "Usar este computador no modo desempenho para jogar?" "${AUTO_YES}" "${padrao}"
    else
        REPLY="${padrao}"
    fi
    case "${REPLY}" in
        [YySs]*) _DESEMPENHO_QUER="sim" ;;
        *)       _DESEMPENHO_QUER="sem" ;;
    esac
}

install_desempenho_host() {
    if [[ "${SKIP_UDEV}" -eq 1 ]]; then
        printf '      pulado (--no-udev) — o modo desempenho escreve em /etc\n'
        return 0
    fi
    _desempenho_decidir
    if [[ "${_DESEMPENHO_QUER}" != "sim" ]]; then
        printf '      modo desempenho não pedido — nada foi alterado (para ligar depois: ./install.sh --desempenho)\n'
        if [[ -e "${HEFESTO_DESEMPENHO_RAIZ:-}/etc/systemd/system/hefesto-desempenho.service" ]]; then
            printf '      aviso: ficaram os ajustes de uma instalação anterior; para desfazer: bash %s/scripts/desempenho.sh remover\n' "${ROOT_DIR}"
        fi
        return 0
    fi
    if [[ -z "${HEFESTO_DESEMPENHO_RAIZ:-}" ]]; then
        if ! command -v sudo >/dev/null 2>&1; then
            warn "sudo ausente — o modo desempenho NÃO foi aplicado"
            return 0
        fi
        if ! sudo -n true 2>/dev/null; then
            warn "sudo recusado — o modo desempenho pulado (re-execute ./install.sh --desempenho)"
            return 0
        fi
    fi
    if ! HEFESTO_DESEMPENHO_PROVADOS="${DESEMPENHO_PROVADOS}" \
            bash "${ROOT_DIR}/scripts/desempenho.sh" aplicar; then
        warn "o modo desempenho não ficou inteiro — rode: bash ${ROOT_DIR}/scripts/desempenho.sh aplicar"
        return 0
    fi
    if [[ -n "${DESEMPENHO_PROVADOS//[[:space:]]/}" ]]; then
        anotar_reinicio_pendente "o modo desempenho (a NVIDIA, o áudio e o PCIe só mudam no próximo boot)"
    fi
    return 0
}

install_bt_agent_host() {
    if [[ "${SKIP_UDEV}" -ne 0 ]]; then
        printf '      pulado (--no-udev)\n'
        return 0
    fi
    if ! command -v sudo >/dev/null 2>&1; then
        warn "sudo ausente — agente de pareamento pulado (o bond meio-salvo continua)"
        return 0
    fi
    if ! sudo -n true 2>/dev/null; then
        warn "sudo recusado — agente de pareamento pulado (re-execute ./install.sh)"
    else
        if ! command -v bt-agent >/dev/null 2>&1; then
            printf '      bluez-tools ausente (fornece bt-agent) — instalando (sudo)\n'
            if declare -F run_pkg >/dev/null 2>&1; then
                if run_pkg bt-agent; then
                    printf '      bluez-tools instalado\n'
                else
                    warn "não consegui instalar o bt-agent — o bond meio-salvo pode voltar"
                    printf '      quando quiser: %s\n' "$(comando_manual_pkg bt-agent)"
                fi
            else
                warn "bluez-tools ausente (fornece bt-agent) e sem tabela de pacotes aqui — instale à mão (Debian/Ubuntu: sudo apt install bluez-tools) e rode de novo"
            fi
        else
            printf '      bluez-tools já presente (bt-agent em %s)\n' "$(command -v bt-agent)"
        fi
        if command -v bt-agent >/dev/null 2>&1; then
            if sudo install -Dm644 "${ROOT_DIR}/assets/systemd/hefesto-bt-agent.service" \
                    /etc/systemd/system/hefesto-bt-agent.service 2>/dev/null; then
                sudo systemctl daemon-reload >/dev/null 2>&1 || true
                sudo systemctl reset-failed hefesto-bt-agent.service >/dev/null 2>&1 || true
                if sudo systemctl enable --now hefesto-bt-agent.service >/dev/null 2>&1; then
                    printf '      hefesto-bt-agent.service habilitado (agente NoInputNoOutput persistente)\n'
                else
                    warn "enable --now do hefesto-bt-agent.service falhou — habilite manualmente"
                fi
            else
                warn "não consegui gravar /etc/systemd/system/hefesto-bt-agent.service"
            fi
        else
            warn "bt-agent ainda ausente — agente de pareamento NÃO habilitado"
        fi
    fi
    return 0
}
