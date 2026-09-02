#!/usr/bin/env bash
# camada_de_maquina.sh — as ONZE curas de HOST, em casa própria.
#
# POR QUE ESTE ARQUIVO NASCEU (31/08/2026)
# ========================================
# Ela desinstalou o Hefesto estável e decidiu ficar só com o de
# desenvolvimento: *"eu desinstalei a versão antiga e vamos deixar só a dev"*.
# No mesmo instante o app de dev parou de funcionar — e o motivo estava escrito
# no cabeçalho do `install-dev.sh` desde que ele nasceu, em 29/08:
#
#     "O app de dev DEPENDE do Hefesto estável para essa camada."
#
# A premissa caiu. Sem o estável, ninguém instalava as regras udev, o grupo
# `hefesto`, o broker, a resiliência do bluetoothd nem a ponte privilegiada — e
# o sintoma foi o de sempre nesta casa, a AUSÊNCIA de dado: `/dev/uhid` nascia
# `crw------- root root`, o daemon caía para uinput em silêncio
# (`vpad_degradado motivo=uhid_indisponivel`), o teclado virtual não abria
# (`uinput_keyboard_create_failed [Errno 13]`) e nada disso era erro — era
# aviso, no meio do log.
#
# ESTA CAMADA É DA MÁQUINA, NÃO DO APP. É a razão de o `install-dev.sh` não a
# ter: dois instaladores escrevendo por cima de
# `/etc/udev/rules.d/70-ps5-controller.rules` fariam o app de uma pessoa rodar
# sob a regra da outra sem uma linha dizendo isso. O que mudou não é essa
# razão — é que agora existe UM app só, e ele precisa da camada.
#
# QUEM SOURCEIA ESTE ARQUIVO
# --------------------------
#   install.sh       — o instalador do app estável, dono histórico destas
#                      funções (elas moravam nele, linhas 873-893 e 989-1677);
#   install-dev.sh   — `--camada-de-maquina`, a porta que 31/08 abriu.
#
# É biblioteca de DEFINIÇÕES: sourceá-la não instala nada. Quem chama, decide.
# O `install-dev.sh` NUNCA executa o `install.sh` — sourcear esta lib é o que
# torna isso possível, e a regra do `CLAUDE.md` ("nunca rode install.sh na
# árvore de dev") continua de pé, literal.
#
# O QUE NÃO MUDA AO LER DAQUI
# ---------------------------
# As funções são as MESMAS, byte por byte. O portão
# `tests/unit/test_install_serve_os_dois_lados_da_cerca.py` continua exigindo
# que cada `*_host` alcance os dois lados da cerca do `install.sh` — ele passou
# a ler os corpos DAQUI e as regiões DE LÁ.
#
# shellcheck shell=bash

# --- o que a lib espera de quem a sourceia --------------------------------
# `warn` é a única função de fora que estas dez usam (medido: 43 chamadas).
# Definida aqui só se quem sourceia não tiver a sua — o `install.sh` tem
# (linha 325); um roteiro avulso que sourceie esta lib pode não ter.
declare -F warn >/dev/null 2>&1 || warn() { printf '      aviso: %s\n' "$*"; }
declare -F step >/dev/null 2>&1 || step() { printf '\n[%s] %s\n' "$1" "$2"; }

# Os gates. O `install.sh` já os define no parser de argumentos (linhas
# 200-245) e o `:=` abaixo não os toca; quem sourceia sem eles herda os
# defaults.
: "${ROOT_DIR:?camada_de_maquina.sh: defina ROOT_DIR (a raiz da árvore) antes do source}"
: "${SKIP_UDEV:=0}"
: "${NO_OSK:=0}"
: "${NO_DKMS:=0}"
: "${AUTO_YES:=0}"

# Render das units do broker root hide-hidraw (BROKER-01/Onda S): substitui
# __SESSION_UID__/__SESSION_GROUP__ pelos valores reais da sessão e GARANTE
# que nenhum placeholder sobra (guarda pós-render — lição 6 da auditoria:
# nunca instalar unit com __SESSION_* literal, que autorizaria um uid
# inválido no .service ou deixaria o .socket sem grupo). Escreve os 2
# arquivos renderizados em "${out_dir}" e devolve 0; devolve 1 SEM escrever
# nada utilizável se o placeholder sobrar (ex.: asset editado errado). Função
# isolada de propósito — testável sem sudo/systemctl (tests/unit/
# test_install_broker_step.py).
_render_broker_units() {
    local service_src="$1" socket_src="$2" out_dir="$3" uid="$4" grupo="$5"
    sed "s/__SESSION_UID__/${uid}/" "${service_src}" \
        > "${out_dir}/hefesto-hidraw-broker.service"
    sed "s/__SESSION_GROUP__/${grupo}/" "${socket_src}" \
        > "${out_dir}/hefesto-hidraw-broker.socket"
    if grep -q '__SESSION_' "${out_dir}/hefesto-hidraw-broker.service" \
            "${out_dir}/hefesto-hidraw-broker.socket"; then
        return 1
    fi
    return 0
}

# udev no host — compartilhado por todos os formatos (o pacote .deb já cobre
# via postinst; flatpak/appimage/native precisam desta chamada explícita).
install_udev_host() {
    if [[ "${SKIP_UDEV}" -eq 1 ]]; then
        printf '      udev pulado (--no-udev) — rode depois: sudo bash scripts/install_udev.sh\n'
    elif command -v sudo >/dev/null 2>&1; then
        if bash "${ROOT_DIR}/scripts/install_udev.sh" >/dev/null 2>&1; then
            printf '      udev rules aplicadas + recarregadas\n'
        else
            warn "install_udev.sh falhou — rode manualmente: sudo bash scripts/install_udev.sh"
        fi
    else
        warn "sudo ausente — rode scripts/install_udev.sh como root depois"
    fi
}

# TECLADO-QUE-NAO-DIGITA-01: o teclado na tela é DEFAULT em TODO formato, pela
# mesma razão do broker logo abaixo — e pelo mesmo furo. O `exit 0` do bloco de
# formatos (poucas linhas adiante) deixa doze passos de cura para trás, e um
# passo escrito só no fluxo native cairia do lado errado da cerca: flatpak,
# appimage e deb sairiam sem o único caminho do produto para ESCREVER TEXTO,
# em silêncio. Por isso a função nasce AQUI, acima da bifurcação, e é chamada
# dos DOIS lados — é o mesmo molde do `install_broker_host`.
#
# Best-effort integral: o `scripts/install_osk.sh` sai 0 mesmo quando não
# consegue instalar (sem sudo, sem rede, distro sem o pacote) e grava o que
# aconteceu na sentinela; o `if` aqui é só o cinto contra o `set -e`.
install_osk_host() {
    if [[ "${NO_OSK}" -eq 1 ]]; then
        printf '      teclado na tela pulado (--no-osk) — o L3 do controle só avisa que não tem o que abrir\n'
        # A escolha dela também vira sentinela: sem isto, "ela não quis" e "o
        # install não instalou" ficariam com a MESMA cara para o doctor — a
        # armadilha do commit 108b711, palavra por palavra.
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

# BROKER-01 (Onda S — achado #7): o broker root hide-hidraw é DEFAULT em TODO
# formato de instalação, não só no native. flatpak/appimage/deb davam `exit 0`
# ANTES do passo 3h e ficavam sem a cura de raiz do controle duplicado, em
# silêncio. Função compartilhada: o passo 3h (native) e o bloco dos formatos
# de pacote chamam o MESMO caminho (render por-máquina + enable do .socket).
# Best-effort integral: qualquer falha vira warn e o install segue (broker
# ausente degrada para o comportamento de hoje — duplicado, nunca zero).
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
    _broker_uid="${SUDO_UID:-$(id -u)}"
    if [[ "${_broker_uid}" == "0" ]]; then
        # Lição 6 (auditoria): renderizar uid 0 criaria um broker que só
        # autoriza ROOT — nenhum daemon de usuária conseguiria conectar.
        # Aborta SÓ este passo (nunca o install inteiro).
        warn "SESSION_UID resolveu 0 (root) — o broker autorizaria ROOT e nenhum daemon de usuária conectaria. Rode ./install.sh da SESSÃO da usuária (sudo é pedido internamente). Passo ABORTADO."
        return 0
    fi
    _broker_grupo="$(id -gn -- "${_broker_uid}")"
    _broker_bin_src="${ROOT_DIR}/src/hefesto_dualsense4unix/broker/hidraw_broker.py"
    _broker_bin_dst="/usr/local/lib/hefesto-dualsense4unix/hefesto-hidraw-broker"
    _broker_tmp="$(mktemp -d)"
    if [[ ! -f "${_broker_bin_src}" ]]; then
        warn "src/hefesto_dualsense4unix/broker/hidraw_broker.py ausente — broker NÃO instalado"
    elif ! _render_broker_units \
            "${ROOT_DIR}/assets/systemd/hefesto-hidraw-broker.service" \
            "${ROOT_DIR}/assets/systemd/hefesto-hidraw-broker.socket" \
            "${_broker_tmp}" "${_broker_uid}" "${_broker_grupo}"; then
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
            printf '      hefesto-hidraw-broker.socket habilitado (uid %s, grupo %s — só o .socket; o .service sobe na 1ª conexão)\n' \
                "${_broker_uid}" "${_broker_grupo}"
            # Registro de posse p/ uninstall (mesma disciplina do
            # cmdline-owners PLAT-03): caminhos + sha256, p/ o
            # uninstall remover SÓ o que fomos NÓS que instalamos.
            _broker_owner_file="${HOME}/.local/state/hefesto-dualsense4unix/broker-owner.conf"
            mkdir -p "$(dirname "${_broker_owner_file}")"
            {
                for _bp in "${_broker_bin_dst}" \
                           /etc/systemd/system/hefesto-hidraw-broker.service \
                           /etc/systemd/system/hefesto-hidraw-broker.socket; do
                    printf '%s=%s\n' "${_bp}" "$(sha256sum "${_bp}" 2>/dev/null | awk '{print $1}')"
                done
            } > "${_broker_owner_file}"
        else
            warn "enable --now do hefesto-hidraw-broker.socket falhou — habilite manualmente"
        fi
    fi
    rm -rf "${_broker_tmp}"
}

# ---------------------------------------------------------------------------
# ONDA-R2: resiliência do bluetoothd — DEFAULT EM TODO FORMATO
# (camada 2 da sprint 2026-07-21-sprint-pesquisa-bluez-estabilidade.md)
# ---------------------------------------------------------------------------
# O crash de heap do bluetoothd destrói bonds e deixa o daemon renascido
# "doente" (recusa devices pareados em loop — medido 21/07). Quatro entregas:
#   1. scripts de sistema em /usr/local/lib/hefesto-dualsense4unix/ (mesma
#      casa do broker root): snapshot/restore de bonds, watchdog de saúde e
#      captura forense (esta última NUNCA ligada por default);
#   2. drop-in do bluetooth.service: Restart=on-failure reafirmado (o template
#      upstream traz comentado — bump futuro do pacote pode regredir) +
#      WatchdogSec=0 (BLUETOOTHD-MORTO-POR-NOS-01: era 30 e o systemd MATOU o
#      bluetoothd dela com SIGABRT em 08/08, levando os quatro pareamentos)
#      + snapshot de bonds a cada parada;
#   3. timer de snapshot (15min, deduplicado por conteúdo, NUNCA fotografa
#      estado vazio, e a poda nunca joga fora o MELHOR snapshot) + a VOLTA
#      automática (bt_bonds_autorestore.sh no ExecStopPost do drop-in), que é a
#      decisão dela de 08/08: "restauro de bonds tem de ser automático; manual
#      com sudo não é produto". A volta só corre quando o daemon MORREU
#      (SERVICE_RESULT != success), é ADITIVA (nunca escreve por cima de uma
#      [LinkKey] viva — é assim que a chave rotacionada deixa de ser risco) e
#      tem quarentena por boot. O bt_bonds_restore.sh continua existindo para o
#      restauro completo decidido à mão;
#   4. timer do watchdog (2min): estado doente → restart rate-limitado (só com
#      0 devices conectados); bond Paired-sem-Bonded (temporário, evapora no
#      disconnect — medido 22/07) → promoção via Pair() explícito 1x/boot.
#
# A FUNÇÃO NASCE AQUI, ACIMA DA BIFURCAÇÃO, PORQUE ISTO É MUDANÇA DE SISTEMA
# (22/08/2026). Até hoje o passo 3e-bis morava ~600 linhas abaixo do `exit 0`
# do ramo dos formatos: quem instalava por `--flatpak`, `--appimage` ou `--deb`
# saía sem a camada, sem uma linha dizendo isso, e ainda LEVAVA as regras udev
# 82 e 83 — que só existem para chamar dois alvos desta camada. Resultado
# medido no estudo de 07/08 (cobertura do install, item 9): a regra 83 apontava
# para uma unit inexistente e falhava a cada conexão Bluetooth, e o salva-vidas
# de bonds nunca gravou nada para essas pessoas. Mesmo defeito, com o mesmo
# molde de conserto, do achado #7 da Onda S (`install_broker_host`), do
# TECLADO-QUE-NAO-DIGITA-01 (`install_osk_host`) e do MIC-EM-TODO-FORMATO-01.
# Portão: `tests/unit/test_install_serve_os_dois_lados_da_cerca.py` (que enxerga
# toda função `*_host`) e `tests/unit/test_regra_udev_nao_fica_orfa_do_alvo_do_run.py`.
#
# ORDEM no fluxo nativo: o chamador de lá fica ANTES do 3f, porque o postinst do
# backport do BlueZ reinicia o bluetoothd — o drop-in precisa existir para armar
# nesse restart.
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
    # BT-NINTENDO-ACTIVE-01: aplica JÁ (nome "Nintendo*" + link policy sem
    # SNIFF) — cura de raiz da queda do Pro/8BitDo sob carga (pesquisa
    # 2026-07-22). Idempotente; o drop-in reaplica a cada start do
    # bluetoothd e o watchdog reafirma a cada 2 min.
    sudo /usr/local/lib/hefesto-dualsense4unix/bt_active_mode.sh 2>/dev/null || true
    sudo install -Dm644 "${ROOT_DIR}/assets/systemd/bluetooth-dropin-10-hefesto-resilience.conf" \
        /etc/systemd/system/bluetooth.service.d/10-hefesto-resilience.conf 2>/dev/null || _btres_ok=0
    for _btres_u in hefesto-bt-bonds-snapshot.service hefesto-bt-bonds-snapshot.timer \
                    hefesto-bt-health-watchdog.service hefesto-bt-health-watchdog.timer; do
        sudo install -Dm644 "${ROOT_DIR}/assets/systemd/${_btres_u}" \
            "/etc/systemd/system/${_btres_u}" 2>/dev/null || _btres_ok=0
    done
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

# PONTE-PRIVILEGIADA-01 (22/08/2026) — a infraestrutura que faz o botão de mover
# um controle de dongle existir SEM a janela pedir senha.
#
# Decisão dela, do mesmo dia: "a ideia é que usemos o sudo só na hora do install
# e isso vai valer sempre no nosso app. não tem como não usar se tratando de bt.
# zero problemas."
#
# O gesto de migrar um controle (GUIA-RADIO-DA-SALA.md §6.3) tem uma linha que
# só root faz — `rm /var/lib/bluetooth/*/cache/<MAC>`, o SDP-CACHE-01 que o
# `scripts/doctor.sh` documenta. Sem ela o pareamento novo nasce com SDP vazio,
# o BlueZ recusa a reconexão como *unknown device*, e parece defeito do
# controle. Sem esta função, o botão dessa migração teria de pedir senha a cada
# clique — ou não existir.
#
# O RACIONAL DA ESCOLHA (sudoers.d contra polkit contra unit contra daemon) está
# no cabeçalho de `scripts/bt_ponte_privilegiada.sh`, junto com as três
# contenções que pagam o preço de um NOPASSWD. Aqui ficam só as decisões DESTE
# arquivo, que são três:
#
#   1. NADA É GRAVADO EM /etc/sudoers.d SEM PASSAR PELO `visudo -c`. Um sudoers
#      inválido derruba o sudo da máquina inteira — inclusive o sudo que seria
#      preciso para consertá-lo. Sem `visudo` na máquina, a regra NÃO vai;
#   2. O TEXTO DA REGRA NÃO MORA AQUI. Ele sai de `bt_ponte_privilegiada.sh
#      regra-sudo <usuária>`, que é o dono único da lista de verbos. Duplicar a
#      lista aqui garantiria que um dia ela ficaria mais larga que o script;
#   3. A CONFERÊNCIA É `sudo -l`, NÃO A EXISTÊNCIA DO ARQUIVO. "A casa sabe e o
#      produto não faz" é o defeito mais caro daqui: arquivo gravado não é
#      permissão concedida (ordem de leitura do sudoers.d, `#includedir`
#      ausente, nome com ponto). Perguntamos ao próprio sudo.
#
# ACIMA DA BIFURCAÇÃO e chamada dos DOIS lados, como a resiliência acima: isto é
# mudança de SISTEMA, ortogonal ao formato do aplicativo. Portão:
# `tests/unit/test_install_serve_os_dois_lados_da_cerca.py`.
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
    # A regra é NOMINAL: precisa saber para QUEM abrir. Rodar o install com sudo
    # é proibido nesta casa (o HOME vira /root e o venv nasce errado), mas se
    # alguém rodar assim mesmo, `SUDO_USER` diz quem é de verdade. Sem nenhum
    # dos dois, gravar `root ALL=NOPASSWD` seria uma regra inútil e barulhenta.
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
    if ! bash "${_ponte_alvo}" regra-sudo "${_ponte_usuaria}" >"${_ponte_tmp}" 2>/dev/null; then
        warn "a ponte recusou gerar a regra para '${_ponte_usuaria}' — nada gravado em ${_ponte_regra}"
        rm -f "${_ponte_tmp}"
        return 0
    fi
    if ! sudo visudo -cqf "${_ponte_tmp}" 2>/dev/null; then
        warn "a regra gerada NÃO passou no 'visudo -c' — nada gravado em ${_ponte_regra} (o sudo desta máquina segue intacto)"
        rm -f "${_ponte_tmp}"
        return 0
    fi
    # 0440 root:root é o modo que o sudo EXIGE de um arquivo em sudoers.d — com
    # qualquer outro ele ignora o arquivo em silêncio.
    if ! sudo install -Dm440 -o root -g root "${_ponte_tmp}" "${_ponte_regra}" 2>/dev/null; then
        warn "não consegui gravar ${_ponte_regra} — a janela vai precisar de senha para mover controle entre dongles"
        rm -f "${_ponte_tmp}"
        return 0
    fi
    rm -f "${_ponte_tmp}"
    printf '      ponte privilegiada instalada: mover controle entre dongles sem digitar senha\n'
    printf '        (%s, NOPASSWD só para %s; sete linhas de comando, MAC com forma fixa,\n' \
        "${_ponte_regra}" "${_ponte_usuaria}"
    printf '         nome novo pelo stdin e NENHUM verbo que execute comando livre)\n'
    if sudo -n -l -U "${_ponte_usuaria}" "${_ponte_alvo}" adaptadores >/dev/null 2>&1; then
        printf '      conferido no próprio sudo: a regra já vale para %s (não é só arquivo no disco)\n' "${_ponte_usuaria}"
    else
        warn "a regra foi gravada mas o sudo NÃO a reconheceu para ${_ponte_usuaria} — confira ${_ponte_regra} e o '#includedir /etc/sudoers.d' em /etc/sudoers"
    fi
}

# MOTOR-7 (25/08/2026) — o install lê o firmware, e a aba abre com o gabinete
# JÁ DESENHADO.
#
# Pedido dela, deste dia: *"manda isso tudo pro nosso install viu. não podemos
# deixar isso passar. a ideia é que o install faça o trampo sujo todo pro user
# sempre ter facilidade"*. É a regra da casa (toda cura entra no install, sem
# flag) aplicada ao censo do gabinete.
#
# O QUE SÓ O INSTALL CONSEGUE. A tabela SMBIOS **tipo 8** — *Port Connector
# Information*, o inventário de conectores que o fabricante escreveu — mora em
# `/sys/firmware/dmi/tables/DMI` e em `/sys/firmware/dmi/entries/8-*/raw`, os
# dois `400 root`. O install passa por root UMA vez; a janela nunca pede senha.
# Sem este passo, os três números da §7.1 da sprint teriam de ser digitados por
# ela — e digitados de novo a cada máquina.
#
# ESTA FUNÇÃO NUNCA DESISTE, e é o que a separa das *_host acima. A
# `install_bt_ponte_privilegiada_host` sem sudo não tem o que fazer e volta;
# esta tem METADE do trabalho que não precisa de root nenhum:
#
#   - os soquetes e os buracos do barramento (`/sys/bus/usb/devices`) — 22 e 15
#     nesta bancada, medidos em 25/08/2026 às 21h18;
#   - a identificação da placa (`/sys/class/dmi/id/`, legível por todo mundo);
#   - e a CONTAGEM da tabela 8, que sai do `ls` do diretório mesmo com o `raw`
#     ilegível. É ela que separa *"a sua placa não tem tabela de conectores"* de
#     *"tem 18 entradas e eu não tive root para lê-las"* — duas frases que mandam
#     a pessoa fazer coisas diferentes.
#
# Sem root o `gabinete.json` sai com `tabela_8_respondeu: false` e a aba abre
# perguntando; com root ele sai com os conectores. Nos dois casos ele EXISTE, e a
# aba não precisa saber qual foi o caso: ela lê o selo de cada campo.
#
# A BIOS DESTA PLACA MENTE, e é por isso que este passo não elege ninguém.
# MEDIDO em 25/08/2026 na Gigabyte B450M S2H: a tabela declara **5** conectores
# USB onde a traseira entrega **8**, e inventa um `USB-C` que esta placa não tem
# — gabarito genérico do fabricante, copiado sem ajustar. O kernel, do outro
# lado, conta **22** soquetes, porque conta cabeçote interno e a duplicação
# 2.0/3.0 do mesmo furo. As três contagens divergem e NENHUMA é autoritativa: o
# módulo grava as três, marca `divergem`, e a aba PERGUNTA. Divergência
# declarada é informação; divergência escondida é o defeito de forma F6.
#
# E ELE NÃO GRAVA POR CIMA DA RESPOSTA DELA. Este arquivo tem dois escritores —
# o install, que traz o firmware, e a aba, onde ela diz quantos buracos a
# traseira tem. Reinstalar apagando isso perderia o trabalho dela em silêncio;
# `preservar_o_que_ela_disse` carrega a declaração adiante, e só a descarta
# quando a PLACA mudou (aí as faces descreveriam outro metal).
#
# Quem DECIDE é o módulo puro `integrations/censo_do_gabinete.py` (100% stdlib,
# testável sem root e sem placa nenhuma); aqui só conseguimos o texto e
# escolhemos o destino — a mesma política do `kernel_cmdline.py` no passo 3e.
#
# ACIMA DA BIFURCAÇÃO e chamada dos DOIS lados: ler firmware é trabalho de HOST,
# ortogonal ao formato do aplicativo. Portão:
# `tests/unit/test_install_serve_os_dois_lados_da_cerca.py`.
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
    # As três razões de o texto sair vazio são a MESMA resposta para o módulo —
    # "não respondeu" — e NENHUMA delas interrompe o passo: o que o kernel dá de
    # graça continua valendo, e é a maior parte do arquivo.
    if ! command -v dmidecode >/dev/null 2>&1; then
        warn "dmidecode ausente — o censo sai só com o barramento; a BIOS não foi consultada"
    elif ! command -v sudo >/dev/null 2>&1 || ! sudo -n true 2>/dev/null; then
        warn "sem root agora — a tabela de conectores da BIOS não foi lida; o censo sai com o barramento e a aba pergunta o resto (re-execute ./install.sh)"
    else
        # SC2024 avisa que o `sudo` não alcança o redirecionamento — e aqui isso
        # é o desejado, não um descuido: o `mktemp` acima é da USUÁRIA, e quem
        # precisa de privilégio é só o `dmidecode`. Escrever com `sudo tee`
        # deixaria no disco um arquivo de root que este passo teria de apagar
        # com sudo depois.
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

# Onda T (desenho: docs/process/estudos/2026-07-20-desenho-onda-t-patch-dkms.md):
# módulo hid-nintendo patchado (probe BT resiliente + module params) via DKMS
# genérico (scripts/dkms_lib.sh — reusado pela Onda W/rtw88). DEFAULT ON (regra
# da casa: install SEM FLAGS aplica), opt-out --no-dkms. Compartilhada entre o
# passo 3i (native) e o bloco dos formatos de pacote (mesmo padrão do broker
# acima) — DKMS é uma mudança de SISTEMA/kernel, ortogonal ao formato do app.
# Contrato fail-safe fica TODO dentro de dkms_lib.sh (ver seu cabeçalho): esta
# função só decide SE chama (flag/sudo) e a mensagem de ativação, nunca
# recarrega/descarrega o módulo.
install_dkms_hid_nintendo_host() {
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
    dkms_warn_secureboot_once  # PKG-1: avisa (não aborta) se SB pode barrar o .ko
    # PKG-3: versão do dkms.conf (fonte da verdade), não literal hardcoded.
    local _hidn_src="${ROOT_DIR}/assets/dkms/hid-nintendo"
    dkms_install_patched_module hefesto-hid-nintendo \
        "$(dkms_pkg_version "${_hidn_src}")" "${_hidn_src}" hid-nintendo
    if sudo install -Dm644 "${ROOT_DIR}/assets/modprobe.d/hefesto-hid-nintendo.conf" \
            /etc/modprobe.d/hefesto-hid-nintendo.conf 2>/dev/null; then
        printf '      opções instaladas em /etc/modprobe.d/hefesto-hid-nintendo.conf (bt_probe_retries=3 + skip_tx_on_rate_exceeded=1)\n'
    else
        warn "não consegui gravar /etc/modprobe.d/hefesto-hid-nintendo.conf"
    fi
    # dkms_install_patched_module é fail-safe POR DESENHO: retorna 0 em TODOS
    # os ramos (sucesso E falha). O único juiz de "staged de verdade" é o
    # modinfo resolver p/ updates/dkms — sem esta checagem, o install
    # anunciava ativação futura mesmo com dkms ausente/build falho (mensagem
    # FALSA: nada foi staged e o próximo plug carrega o in-tree vanilla).
    if ! dkms_module_from_updates hid-nintendo; then
        warn "patch DKMS do hid-nintendo NÃO ficou staged (veja avisos acima) — driver in-tree continua (fail-safe); a conf do modprobe.d é inerte com o in-tree ('unknown parameter ignored')"
        return 0
    fi
    # ATIVAÇÃO FAIL-SAFE (mesmo princípio do btusb/broker acima): NUNCA
    # recarregamos um módulo em uso — a mantenedora joga com Pro Controller e
    # 8BitDo conectados AGORA, e substituir o módulo carregado os derrubaria.
    # Nota de precisão (diferente do btusb): substituição de módulo NÃO pega
    # em replug — se o in-tree está CARREGADO, o replug o re-liga a ele
    # mesmo; só o próximo BOOT troca. Mensagem honesta nos dois ramos.
    if [[ -d /sys/module/hid_nintendo/parameters ]]; then
        printf '      módulo patchado JÁ carregado (params visíveis em /sys/module/hid_nintendo/parameters)\n'
        # AUTO-01.7: com o patchado carregado, escreve os params A QUENTE —
        # paridade com o caminho de instalação por PACOTE
        # (scripts/install-host-udev.sh), que já fazia isto e o install.sh não.
        # Os dois são lidos A CADA PROBE, então a cura vale no próximo PLUG do
        # controle, sem esperar reboot; e é a única janela possível, porque
        # recarregar o módulo é proibido (derrubaria Pro/8BitDo em uso).
        # Best-effort: param read-only ou sudo expirado não interrompe nada.
        # O portão é de EXISTÊNCIA (`-e`) e nunca `-w`: os arquivos em
        # /sys/module são root:root 0644 e o install roda SEM sudo (com sudo o
        # HOME vira /root e o venv nasce errado), então `-w` é sempre falso e o
        # passo vira silêncio — quem escreve abaixo é o `sudo tee`, não quem
        # testa o portão.
        if [[ -e /sys/module/hid_nintendo/parameters/bt_probe_retries ]]; then
            # A ESCRITA É CONFERIDA, e não declarada — 01/09/2026. O portão
            # acima é de EXISTÊNCIA (`-e`), por decisão declarada, logo ele NÃO
            # pode saber se a escrita passou: com o ticket do sudo expirado ou
            # param read-only, o `|| true` engolia e a frase mentia.
            if printf '3' | sudo tee /sys/module/hid_nintendo/parameters/bt_probe_retries >/dev/null 2>&1 \
               && printf '1' | sudo tee /sys/module/hid_nintendo/parameters/skip_tx_on_rate_exceeded >/dev/null 2>&1; then
                printf '      params aplicados a quente (valem no próximo plug, sem reboot)\n'
            else
                warn "não consegui escrever os params do hid-nintendo a quente — valem no próximo boot"
            fi
        fi
        # Os três do patch 0003 (handshake USB do clone 057E:2009) são lidos NA
        # PROBE, então valem do próximo plug em diante. O uninstall os devolve a
        # 0, logo o rearme aqui é obrigatório: sem ele o ciclo uninstall+install
        # deixa o 8BitDo no cabo sem cura até o boot seguinte. Portão próprio
        # porque o módulo patchado ANTIGO não tem estes params. A simetria com o
        # uninstall é cobrada por teste.
        if [[ -e /sys/module/hid_nintendo/parameters/usb_cmd_pad_to_report ]]; then
            printf '1' | sudo tee /sys/module/hid_nintendo/parameters/usb_cmd_pad_to_report >/dev/null 2>&1 || true
            printf '1' | sudo tee /sys/module/hid_nintendo/parameters/usb_send_conn_status >/dev/null 2>&1 || true
            printf '1' | sudo tee /sys/module/hid_nintendo/parameters/usb_probe_degrade >/dev/null 2>&1 || true
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

# Contenção BT (25/07): módulo hid-playstation patchado (retry opcional nos
# feature reports da probe) via a MESMA lib genérica scripts/dkms_lib.sh (3ª
# instância — hid-nintendo é a 1ª, rtw88_usb a 2ª; ZERO ajuste na lib).
# DEFAULT ON (regra da casa: install SEM FLAGS aplica), mesmo gate NO_DKMS.
# Motivo: com dois DualSense pareando com ~1 s de diferença, o 2º perde o
# canal de controle L2CAP, o GET_REPORT expira no BlueZ (REPORT_REQ_TIMEOUT,
# 3 s), o uhid entrega -EIO ao driver e o controle inteiro é perdido. Detalhe
# completo em assets/dkms/hid-playstation/README.md.
install_dkms_hid_playstation_host() {
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
    dkms_warn_secureboot_once  # PKG-1: avisa (não aborta) se SB pode barrar o .ko
    local _hidp_src="${ROOT_DIR}/assets/dkms/hid-playstation"
    dkms_install_patched_module hefesto-hid-playstation \
        "$(dkms_pkg_version "${_hidp_src}")" "${_hidp_src}" hid-playstation
    if sudo install -Dm644 "${ROOT_DIR}/assets/modprobe.d/hefesto-hid-playstation.conf" \
            /etc/modprobe.d/hefesto-hid-playstation.conf 2>/dev/null; then
        printf '      opções instaladas em /etc/modprobe.d/hefesto-hid-playstation.conf (feature_retries=2 + ds4_* do clone no cabo)\n'
    else
        warn "não consegui gravar /etc/modprobe.d/hefesto-hid-playstation.conf"
    fi
    # Mesmo achado #5 do hid-nintendo: dkms_install_patched_module é fail-safe
    # POR DESENHO (retorna 0 em TODOS os ramos) — o único juiz de "staged de
    # verdade" é o modinfo resolver p/ updates/dkms.
    if ! dkms_module_from_updates hid-playstation; then
        warn "patch DKMS do hid-playstation NÃO ficou staged (veja avisos acima) — driver in-tree continua (fail-safe); a conf do modprobe.d é inerte com o in-tree ('unknown parameter ignored') e o 2º DualSense segue podendo se perder na probe"
        return 0
    fi
    # ATIVAÇÃO FAIL-SAFE — aqui a regra é MAIS dura que a do hid-nintendo:
    # recarregar o hid_playstation derruba TODOS os DualSense, e os por
    # Bluetooth perdem o link. NUNCA recarregamos. O marcador de "patchado
    # carregado" é o parâmetro NOVO feature_retries (o in-tree tem zero
    # params, então o diretório parameters/ sequer existe nele).
    if [[ -e /sys/module/hid_playstation/parameters/feature_retries ]]; then
        printf '      módulo patchado JÁ carregado (feature_retries visível em /sys/module/hid_playstation/parameters)\n'
        # AUTO-01.7: param A QUENTE — paridade com o caminho por PACOTE
        # (scripts/install-host-udev.sh). `feature_retries` é lido A CADA
        # PROBE, e o probe roda a cada CONEXÃO do controle: escrever aqui faz a
        # cura do "segundo DualSense que some" valer no próximo pareamento, sem
        # reboot e sem reload (proibido: derrubaria os DualSense por BT).
        # Portão de EXISTÊNCIA, nunca `-w`: /sys/module é root:root 0644 e o
        # install roda SEM sudo, então `-w` é sempre falso e a escrita por
        # `sudo tee` logo abaixo nunca aconteceria (mesma restrição do
        # hid-nintendo acima).
        if [[ -e /sys/module/hid_playstation/parameters/feature_retries ]]; then
            if printf '2' | sudo tee /sys/module/hid_playstation/parameters/feature_retries >/dev/null 2>&1; then
                printf '      feature_retries aplicado a quente (vale na próxima conexão, sem reboot)\n'
            else
                warn "não consegui escrever feature_retries a quente — vale no próximo boot"
            fi
        fi
        # Mesma lógica para a cura do CLONE no cabo (pairing info de 9 bytes
        # em vez de 16): lidos a cada probe, valem no próximo plug. Ausentes
        # no módulo patchado antigo (só tinha feature_retries) — por isso cada
        # um é decidido pela sua própria EXISTÊNCIA, sem avisar à toa. Caminhos
        # LITERAIS de propósito: a paridade com o install-host-udev.sh é
        # verificada por grep (AUTO-01.7).
        if [[ -e /sys/module/hid_playstation/parameters/ds4_short_pairing_info ]]; then
            if printf 'Y' | sudo tee /sys/module/hid_playstation/parameters/ds4_short_pairing_info >/dev/null 2>&1; then
                printf '      ds4_short_pairing_info aplicado a quente (clone no cabo; vale no próximo plug)\n'
            else
                warn "não consegui escrever ds4_short_pairing_info a quente — vale no próximo boot"
            fi
        fi
        if [[ -e /sys/module/hid_playstation/parameters/ds4_synthetic_mac ]]; then
            if printf 'Y' | sudo tee /sys/module/hid_playstation/parameters/ds4_synthetic_mac >/dev/null 2>&1; then
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

# INITRAMFS-01 (25/07): fecha o furo entre `dkms install` e o BOOT. O initramfs
# leva uma CÓPIA do .ko e não é regenerado pelo dkms — o boot seguia carregando
# o módulo da geração anterior. Compartilhada entre o passo 3k (native) e o
# bloco dos formatos de pacote, igual às duas funções DKMS acima; roda UMA vez
# porque a lib coalesce (dkms_mark_initramfs_stale × dkms_flush_initramfs).
# Silenciosa e no-op quando nenhum módulo DKMS ficou staged (--no-dkms, dkms
# ausente, build falho): quem marca é só o ramo de sucesso da lib.
flush_initramfs_host() {
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

# Onda W (desenho: docs/process/estudos/2026-07-20-desenho-onda-w-patch-dkms.md):
# módulo rtw88_usb patchado (device-gone + queue de port reset — cura do
# fantasma USB do dongle WiFi) via a MESMA lib genérica scripts/dkms_lib.sh
# (2ª instância — hid-nintendo é a 1ª; ZERO ajuste na lib). DEFAULT ON (regra
# da casa: install SEM FLAGS aplica), mesmo gate NO_DKMS do hid-nintendo
# acima (--no-dkms desliga AMBOS). Compartilhada entre o passo 3j (native) e
# o bloco dos formatos de pacote (mesmo padrão do broker/hid-nintendo acima)
# — DKMS é mudança de SISTEMA/kernel, ortogonal ao formato do app. Contrato
# fail-safe fica TODO dentro de dkms_lib.sh: esta função só decide SE chama
# (flag/sudo) e a mensagem de ativação, nunca recarrega/descarrega o módulo.
#
# Diferente do hid-nintendo (sem conf de /etc/modprobe.d): o gate da parte
# agressiva do patch (usb_queue_reset_device) É o próprio module param
# `hang_reset`, com default Y JÁ embutido no .ko (assets/dkms/rtw88-usb/
# usb.c) — não há arquivo externo a instalar/remover para ativá-lo.
install_dkms_rtw88_usb_host() {
    if [[ "${NO_DKMS}" -eq 1 ]]; then
        printf '      pulado (--no-dkms)\n'
        return 0
    fi
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
    dkms_warn_secureboot_once  # PKG-1: avisa (não aborta) se SB pode barrar o .ko
    # PKG-3: versão do dkms.conf (fonte da verdade), não literal hardcoded.
    local _rtw_src="${ROOT_DIR}/assets/dkms/rtw88-usb"
    dkms_install_patched_module hefesto-rtw88-usb \
        "$(dkms_pkg_version "${_rtw_src}")" "${_rtw_src}" rtw88_usb
    # Mesmo achado #5 do hid-nintendo: dkms_install_patched_module é
    # fail-safe POR DESENHO (retorna 0 em TODOS os ramos) — o único juiz de
    # "staged de verdade" é o modinfo resolver p/ updates/dkms.
    if ! dkms_module_from_updates rtw88_usb; then
        warn "patch DKMS do rtw88_usb NÃO ficou staged (veja avisos acima) — driver in-tree continua (fail-safe); sem device-gone/port-reset, o fantasma USB do dongle (device retido após disconnect perdido) segue possível"
        return 0
    fi
    # ATIVAÇÃO FAIL-SAFE (mesmo princípio do hid-nintendo acima): NUNCA
    # recarregamos um módulo em uso — a mantenedora depende do WiFi AGORA, e
    # substituir o módulo carregado o derrubaria. Diferente do hid_nintendo
    # (0 params no in-tree), o rtw88_usb in-tree JÁ expõe `switch_usb_mode`
    # — a presença do diretório parameters/ sozinha NÃO distingue patchado
    # de in-tree. O marcador é o PARÂMETRO NOVO `hang_reset` (só o patch
    # tem). Nota de precisão (igual ao hid-nintendo): substituição de módulo
    # NÃO pega em replug do dongle — se o in-tree está CARREGADO, o replug
    # o re-liga a ele mesmo; só o próximo BOOT troca. "Entra no próximo
    # plug" só é verdade quando o módulo está DESCARREGADO agora (3º ramo).
    if [[ -e /sys/module/rtw88_usb/parameters/hang_reset ]]; then
        printf '      módulo patchado JÁ carregado (hang_reset visível em /sys/module/rtw88_usb/parameters)\n'
        # O uninstall devolve `hang_reset` a 0 de propósito (driver menos
        # agressivo até o boot), e sem este rearme o ciclo uninstall+install
        # deixa o reset de porta do fantasma do dongle desligado, com o default
        # Y do .ko só voltando no próximo boot. O param é lido em tempo de
        # execução, então escrever aqui vale agora. Simetria cobrada por teste.
        printf 'Y' | sudo tee /sys/module/rtw88_usb/parameters/hang_reset >/dev/null 2>&1 || true
    elif [[ -d /sys/module/rtw88_usb ]]; then
        printf '      módulo in-tree em uso — NÃO recarregamos (derrubaria o WiFi ao vivo);\n'
        printf '      o patchado vale no próximo boot (replug NÃO troca módulo carregado)\n'
    else
        printf '      rtw88_usb descarregado — o patchado entra sozinho no próximo plug do dongle\n'
    fi
    return 0
}

# ---------------------------------------------------------------------------
# ONDA-R: agente de pareamento BT persistente — DEFAULT (bond meio-salvo)
# ---------------------------------------------------------------------------
# "No agent available for request type 2" = nenhum agente de pareamento D-Bus
# registrado no momento em que o BlueZ pede confirmação → autenticação nunca
# completa → nasce o bond "meio-salvo" (Paired: yes / Bonded: no), que trava o
# controle até um re-pareamento manual. Cura: bt-agent (pacote bluez-tools do
# noble) como serviço de SISTEMA persistente com --capability=NoInputNoOutput
# (aceita automaticamente pareamentos sem PIN/senha — o caso do DualSense/
# 8BitDo/Nintendo Pro). Ver estudo §4. `--now` aqui é seguro: habilita/inicia
# SÓ o agente, nunca mexe no bluetoothd.
#
# VIROU FUNÇÃO `*_host` EM 31/08/2026, e o motivo é o defeito que o sufixo
# existe para pegar. Este bloco era código de topo do lado NATIVE — medido: a
# cerca abre na `install.sh:1192` e o `exit 0` dos formatos está na `:1309`, e
# ele morava na `:2070`. Logo, quem instalava por `--flatpak`, `--appimage` ou
# `--deb` saía SEM o agente de pareamento, e sem uma linha dizendo isso — o
# mesmo achado #7 da Onda S, o mesmo TECLADO-QUE-NAO-DIGITA-01, o mesmo
# MIC-EM-TODO-FORMATO-01, os três já curados. Ele escapou do portão
# `tests/unit/test_install_serve_os_dois_lados_da_cerca.py` por um detalhe de
# FORMA: o portão ancora no sufixo `_host`, e um bloco solto não tem nome.
#
# Sem o agente, todo bond novo nasce meio-salvo (`Paired: yes / Bonded: no`) e
# some — que é o "conectam sozinhos e desligam em sequência" que ela relatou.
install_bt_agent_host() {
    # QUEM ANUNCIA O PASSO É O CHAMADOR, e esta função NÃO repete o `step`.
    # Curado em 01/09/2026: quando o bloco de topo do `install.sh` virou função
    # (commit `a53f44e2`), o `step` veio junto e o do chamador ficou — o
    # cabeçalho `[3g]` saía DUAS VEZES no caminho normal. E com `--no-udev`
    # saía UMA e mais nada: o único passo do instalador que anunciava e ficava
    # calado, enquanto todos os vizinhos dizem `pulado (--no-udev)`.
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
            # DEPS-UNIVERSAIS-01: nome canônico. No Fedora a tabela está
            # VAZIA de propósito (não há `bluez-tools` com esse nome), e o
            # `run_pkg` diz isso em voz alta em vez de instalar outra coisa.
            # `run_pkg`/`comando_manual_pkg` são do `install.sh` — a tabela de
            # pacotes por distro é dele e NÃO viaja para esta lib. Quem sourceia
            # sem elas (o `install-dev.sh --camada-de-maquina`) não adivinha o
            # gerenciador da distro: diz o que falta, em voz alta, em vez de
            # fingir que instalou.
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
                # AGENTE-EM-FAILED-NAO-VOLTA-PELO-INSTALL-01 (15/08/2026) — MEDIDO.
                #
                # `enable --now` NÃO tira uma unit do estado `failed`: o systemd
                # recusa iniciar quem bateu o `StartLimitBurst`, e o install
                # terminava com "habilitado" no texto e o agente morto de fato.
                #
                # O preço disso foi medido em 14/08: o agente ficou `failed` das
                # 16:17 às 00:31 e, sem ele, TODO bond novo nasce meio-salvo
                # (`Paired: yes / Bonded: no`) e some — que é o "conectam sozinhos
                # e desligam em sequência" que ela relatou. Reinstalar não
                # resolveria; só um `reset-failed` explícito resolve.
                #
                # O `KillSignal=SIGKILL` da unit (mesma data) impede que ele
                # ENTRE em `failed`. Esta linha cuida de quem JÁ está — as duas
                # são necessárias, e nenhuma substitui a outra.
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
