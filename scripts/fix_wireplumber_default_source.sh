#!/usr/bin/env bash
# fix_wireplumber_default_source.sh — impede o DualSense de virar o microfone
# padrão do sistema (FEAT-WIREPLUMBER-DUALSENSE-NOT-DEFAULT-SOURCE-01).
#
# Instala um drop-in do WirePlumber que rebaixa a prioridade da fonte de áudio
# do DualSense e reseta a fonte padrão JÁ persistida para uma fonte sã (ex.: o
# microfone da webcam ou o onboard). Cobre o sintoma "o controle fica
# diminuindo/mexendo no microfone" — que é o WirePlumber elegendo o mic do
# controle como entrada padrão ao conectar, não o daemon do Hefesto.
#
# Uso:
#   scripts/fix_wireplumber_default_source.sh [--install|--disable-source|--reset-only|--status]
#     --install         (default) instala o drop-in que REBAIXA + reset + restart.
#     --disable-source  DESABILITA a source do DualSense (node.disabled; só-HID).
#                       Remove o mic do controle de vez — vence até escassez de fonte.
#     --reset-only      só reelege a fonte padrão e reinicia (sem (re)instalar drop-in).
#     --enable-mic      REMOVE os drop-ins de supressão e deixa o mic do DualSense
#                       utilizável/elegível como padrão (o oposto de --install).
#     --promote-source  PROMOÇÃO EXPLÍCITA (MIC-USB-01): faz o mic do controle ser
#                       o microfone PADRÃO e persiste a escolha. É o --enable-mic
#                       mais a cura das camadas 1 e 2 e a eleição de fato.
#     --unmute-routes   SÓ tira o `"mute":true` persistido das rotas do DualSense
#                       (camada 1) — sem mexer em drop-in nem em fonte padrão.
#     --status          mostra a fonte padrão atual e sai.
#
#   Env: HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED=1 faz --install/--disable
#        virarem --enable-mic automaticamente (a usuária QUER o mic do DualSense).
#
# Exit code (modos install/disable-source): 0 = microfone ativo != DualSense (OK);
#   2 = DualSense ainda ativo por ser a ÚNICA fonte disponível (aviso, não falha);
#   1 = DualSense ativo COM outra fonte available (falha real — drop-in não pegou).
# (FEAT-WIREPLUMBER-DISABLE-SOURCE-MODE-01, BUG-WIREPLUMBER-FIX-FALSE-SUCCESS-01, ADR-019.)

set -euo pipefail

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly DROPIN_NAME="51-hefesto-dualsense-no-default-source.conf"
readonly DROPIN_SRC="${ROOT_DIR}/assets/wireplumber/${DROPIN_NAME}"
readonly DROPIN_DIR="${HOME}/.config/wireplumber/wireplumber.conf.d"
readonly DROPIN_DST="${DROPIN_DIR}/${DROPIN_NAME}"
readonly DROPIN_DISABLE_NAME="52-hefesto-dualsense-disable-source.conf"
readonly DROPIN_DISABLE_SRC="${ROOT_DIR}/assets/wireplumber/${DROPIN_DISABLE_NAME}"
readonly DROPIN_DISABLE_DST="${DROPIN_DIR}/${DROPIN_DISABLE_NAME}"
# FEAT-WIREPLUMBER-DISABLE-SOURCE-MODE-01 (reforço): 53 desabilita a SAÍDA do
# DualSense, para o '.monitor' do sink não reaparecer como default-source.
readonly DROPIN_OUTPUT_NAME="53-hefesto-dualsense-disable-output.conf"
readonly DROPIN_OUTPUT_SRC="${ROOT_DIR}/assets/wireplumber/${DROPIN_OUTPUT_NAME}"
readonly DROPIN_OUTPUT_DST="${DROPIN_DIR}/${DROPIN_OUTPUT_NAME}"
readonly STATE_FILE="${HOME}/.local/state/wireplumber/default-nodes"

MODE="install"
for arg in "$@"; do
    case "$arg" in
        --install)        MODE="install" ;;
        --disable-source) MODE="disable" ;;
        --reset-only)     MODE="reset" ;;
        --enable-mic)     MODE="enable-mic" ;;
        --promote-source) MODE="promote" ;;
        --unmute-routes)  MODE="unmute-routes" ;;
        --status)         MODE="status" ;;
        *) printf '[wp-fix] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

log() { printf '[wp-fix] %s\n' "$*"; }

# FEAT-DUALSENSE-MIC-INTENDED-01: se a usuária declarou que QUER o mic do DualSense
# (env HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED=1), suprimir o mic é o oposto do
# desejado — então qualquer install/disable vira "enable-mic" (remove os drop-ins de
# supressão e deixa o mic utilizável/elegível como padrão).
if [[ "${HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED:-}" =~ ^(1|true|yes|TRUE|YES)$ ]]; then
    if [[ "${MODE}" == "install" || "${MODE}" == "disable" ]]; then
        log "DUALSENSE_MIC_INTENDED=1 — mic do DualSense é desejado; não suprimo (modo enable-mic)"
        MODE="enable-mic"
    fi
fi

show_status() {
    if command -v wpctl >/dev/null 2>&1; then
        log "Default Configured Devices (wpctl):"
        wpctl status 2>/dev/null | sed -n '/Default Configured/,$p' | sed -n '1,6p' || true
    fi
    if [[ -f "${STATE_FILE}" ]]; then
        local persisted
        persisted="$(grep '^default.configured.audio.source=' "${STATE_FILE}" 2>/dev/null || true)"
        log "persistido: ${persisted:-(default.configured.audio.source não definido)}"
    fi
}

# Lê a seção Sources do `wpctl status` e devolve o ID de uma fonte que NÃO seja
# o DualSense — preferindo a marcada como default (*), senão a primeira.
pick_target_source_id() {
    wpctl status 2>/dev/null | awk '
        /Sources:/ {insrc=1; next}
        insrc && (/Filters:/ || /Sinks:/ || /Streams:/ || /Video/) {insrc=0}
        insrc {
            isdef = ($0 ~ /\*/)
            if (match($0, /[0-9]+\./)) {
                id = substr($0, RSTART, RLENGTH - 1)
                desc = substr($0, RSTART + RLENGTH)
                if (desc !~ /[Dd]ual[Ss]ense/) {
                    if (first == "") first = id
                    if (isdef) def = id
                }
            }
        }
        END { if (def != "") print def; else print first }
    '
}

install_dropin() {
    if [[ ! -f "${DROPIN_SRC}" ]]; then
        log "ERRO: asset não encontrado: ${DROPIN_SRC}"
        return 1
    fi
    mkdir -p "${DROPIN_DIR}"
    cp -f "${DROPIN_SRC}" "${DROPIN_DST}"
    log "drop-in instalado: ${DROPIN_DST}"
}

install_disable_dropin() {
    if [[ ! -f "${DROPIN_DISABLE_SRC}" ]]; then
        log "ERRO: asset não encontrado: ${DROPIN_DISABLE_SRC}"
        return 1
    fi
    mkdir -p "${DROPIN_DIR}"
    cp -f "${DROPIN_DISABLE_SRC}" "${DROPIN_DISABLE_DST}"
    log "drop-in DISABLE instalado: ${DROPIN_DISABLE_DST}"
    # Reforço: desabilita também a SAÍDA do DualSense (53) — sem ela, o
    # '.monitor' do sink surround reaparece como default-source pós-reboot
    # (o "mic que voltou"). Best-effort.
    if [[ -f "${DROPIN_OUTPUT_SRC}" ]]; then
        cp -f "${DROPIN_OUTPUT_SRC}" "${DROPIN_OUTPUT_DST}"
        log "drop-in DISABLE-OUTPUT instalado: ${DROPIN_OUTPUT_DST}"
        log "AVISO: o 53 desabilita também o SINK (saida) do DualSense — o"
        log "       alto-falante e o fone no jack do controle ficam MUDOS, e o"
        log "       canal de haptic-de-audio some. O rumble do jogo NAO usa esse"
        log "       canal (vai por HID/vpad), entao a vibracao in-game continua."
        log "       Reverter: bash scripts/fix_wireplumber_default_source.sh --enable-mic"
        log "       + systemctl --user restart wireplumber."
    fi
}

# Remove a chave de fonte padrão persistida que aponta para o DualSense, para que
# o WirePlumber não tente reeleger o mic do controle no próximo boot. Preserva o
# resto do state. Idempotente.
#
# PILHA-TRUNCADA-01 — MEDIDO em 06/08/2026, no código do WirePlumber 0.5.12
# instalado nesta máquina. O `sed` que estava aqui apagava só a chave-BASE:
#
#     sed -i.bak '/^default\.configured\.audio\.source=.*[Dd]ual[Ss]ense/Id'
#
# O `=` logo depois de `source` faz o padrão casar `...source=` e NÃO casar
# `...source.0=` / `...source.1=`. E o histórico de fontes padrão não é um
# conjunto de chaves independentes: é uma PILHA CONTÍGUA, lida assim em
# `/usr/share/wireplumber/scripts/default-nodes/state-default-nodes.lua`
# (`collectStored`, linhas 141-155):
#
#     key = key_base                      -- default.configured.audio.source
#     repeat
#       local v = state_table [key]
#       table.insert (stored, v)
#       key = key_base .. "." .. tostring (index)
#       index = index + 1
#     until v == nil                      -- PARA no primeiro buraco
#
# Apagada a base, a leitura para na primeira volta e `.0`/`.1` ficam
# INALCANÇÁVEIS: some o histórico INTEIRO de preferência de microfone dela, não
# só a linha do DualSense.
#
# São DOIS defeitos, não um, e o estado real desta máquina exibe os dois — ele
# tem três níveis (base = onboard, `.0` = mic do DualSense, `.1` = um sink que
# já foi fonte, assinatura de "um monitor já foi eleito aqui"):
#
#   - quando a base NÃO é o DualSense (o caso de hoje), o `grep`/`sed` antigo
#     não casa nada e a função é um NO-OP: as duas entradas do DualSense que ela
#     existe para tirar ficam exatamente onde estavam;
#   - quando a base É o DualSense, ela casa, apaga a base, e leva junto todo o
#     resto da pilha por truncamento.
#
# Falhar em fazer o trabalho e destruir o histórico são os dois lados da mesma
# linha, e nenhum deles aparecia no log: os dois terminavam com a função
# devolvendo 0.
#
# A correção reescreve a pilha CONTÍGUA sem as entradas do DualSense, em ordem:
# quem sobra vira base, `.0`, `.1`, ... É o que o comentário sempre prometeu
# ("preserva o resto do state") e o que o código não fazia.
#
# GRAU: MEDIDO no código dos dois lados (o `sed` e o `collectStored`);
# SUSPEITA COM MECANISMO no efeito em produção, porque esta função edita o
# arquivo com o WirePlumber VIVO — e o próprio script documenta, em
# `unmute_dualsense_routes`, que o WirePlumber GRAVA o estado ao sair e
# sobrescreveria a edição. Ou o `sed` era sobrescrito (no-op silencioso) ou
# vencia e truncava. Essa ordem NÃO foi mexida aqui: virou item de sprint.
_pilha_sem_dualsense() {   # PURA: state na stdin, state corrigido na stdout
    awk '
        BEGIN { base = "default.configured.audio.source" }
        {
            linha = $0
            p = index(linha, "=")
            chave = (p > 1) ? substr(linha, 1, p - 1) : ""
            valor = (p > 0) ? substr(linha, p + 1) : ""
            if (chave != base && chave !~ ("^" base "\\.[0-9]+$")) { print; next }
            if (tolower(valor) ~ /dualsense/) next
            pilha[n++] = valor
        }
        END {
            for (i = 0; i < n; i++) {
                if (i == 0) print base "=" pilha[i]
                else        print base "." (i - 1) "=" pilha[i]
            }
        }
    '
}

remove_configured_dualsense() {
    [[ -f "${STATE_FILE}" ]] || return 0
    if grep -qiE '^default\.configured\.audio\.source(\.[0-9]+)?=.*[Dd]ual[Ss]ense' "${STATE_FILE}" 2>/dev/null; then
        cp -f "${STATE_FILE}" "${STATE_FILE}.bak" 2>/dev/null || true
        local tmp
        tmp="$(mktemp "${STATE_FILE}.hefesto.XXXXXX")" || return 1
        if _pilha_sem_dualsense < "${STATE_FILE}" > "${tmp}"; then
            mv -f "${tmp}" "${STATE_FILE}"
            log "entradas do DualSense removidas da pilha de fonte padrão, resto do histórico preservado (backup .bak)"
        else
            rm -f "${tmp}"
            log "ERRO: não consegui reescrever ${STATE_FILE} — nada foi alterado"
            return 1
        fi
    fi
}

# Nome do default-source ATIVO (pactl preferido; fallback ao '*' do wpctl).
active_default_source() {
    if command -v pactl >/dev/null 2>&1; then
        local p
        p="$(pactl get-default-source 2>/dev/null || true)"
        [[ -n "${p}" ]] && { printf '%s\n' "${p}"; return 0; }
    fi
    wpctl status 2>/dev/null | awk '
        /Sources:/ {insrc=1; next}
        insrc && (/Filters:/ || /Sinks:/ || /Streams:/ || /Video/) {insrc=0}
        insrc && /\*/ { sub(/.*\*[[:space:]]+[0-9]+\.[[:space:]]*/, ""); print; exit }'
}

# 0 se há alguma fonte de captura available que NÃO seja o DualSense.
other_source_available() {
    wpctl status 2>/dev/null | awk '
        /Sources:/ {insrc=1; next}
        insrc && (/Filters:/ || /Sinks:/ || /Streams:/ || /Video/) {insrc=0}
        insrc && /[0-9]+\./ && $0 !~ /[Dd]ual[Ss]ense/ { found=1 }
        END { exit (found ? 0 : 1) }'
}

# O que importa é o MIC do DualSense (alsa_input). O '.monitor' do sink (loopback
# da saída) também casa "DualSense" no nome, mas é inofensivo — não é o microfone
# nem o sintoma de "controle mexendo no mic". Tratamos monitor como OK.
is_dualsense_mic() {
    [[ "$1" =~ [Dd]ual[Ss]ense ]] && [[ "$1" != *[Mm]onitor* ]]
}

# Verifica que o microfone ATIVO não é o MIC do DualSense (settle ~2s).
# Exit: 0 OK; 2 ÚNICO (DualSense por escassez — aviso); 1 FALHA real.
verify_active_not_dualsense() {
    local i cur=""
    for i in 1 2 3 4 5 6 7 8; do          # ~2s (8 x 250ms)
        cur="$(active_default_source || true)"
        is_dualsense_mic "${cur}" || break
        sleep 0.25
    done
    if ! is_dualsense_mic "${cur}"; then
        if [[ "${cur}" =~ [Dd]ual[Ss]ense ]]; then
            log "OK: mic do DualSense desabilitado (ativo é só o monitor do sink: ${cur})"
        else
            log "OK: microfone padrão ativo = ${cur:-<nenhum>} (DualSense fora)"
        fi
        return 0
    fi
    if other_source_available; then
        log "FALHA: o MIC (alsa_input) do DualSense ainda é o ativo, com outra fonte disponível (drop-in não aplicou?)"
        return 1
    fi
    log "AVISO: DualSense é a única fonte de captura disponível — por isso segue ativo."
    log "       conecte webcam/mic, ou use --disable-source para removê-lo de vez."
    return 2
}

reset_default_source() {
    if ! command -v wpctl >/dev/null 2>&1; then
        log "wpctl ausente — pulei o reset da fonte padrão"
        return 0
    fi
    local target
    target="$(pick_target_source_id || true)"
    if [[ -n "${target}" ]]; then
        if wpctl set-default "${target}" 2>/dev/null; then
            log "fonte padrão reeleita para o id ${target} (não-DualSense)"
        else
            log "aviso: 'wpctl set-default ${target}' falhou"
        fi
    else
        log "aviso: nenhuma fonte não-DualSense encontrada para eleger como padrão"
    fi
}

restart_wireplumber() {
    if command -v systemctl >/dev/null 2>&1; then
        if systemctl --user restart wireplumber 2>/dev/null; then
            log "WirePlumber reiniciado"
        else
            log "aviso: falha ao reiniciar WirePlumber — reinicie a sessão para aplicar"
        fi
    fi
}

# BUG-MIC-MUDO-PERSISTIDO-01: tirar os drop-ins de supressão NÃO devolve o
# microfone — ele volta MUDO.
#
# São dois estados diferentes, em dois arquivos diferentes, e o script só
# conhecia um. `default-nodes` guarda QUEM é a fonte padrão (o que os drop-ins
# e o reset governam); `default-routes` guarda o MUTE e o volume de cada rota
# do card, e sobrevive a tudo. Medido na máquina da mantenedora:
#
#   alsa_card.usb-...DualSense...:input:iec958-stereo-input={"mute":true, ...}
#   alsa_card.usb-...DualSense...:output:analog-output={"mute":true, ...}
#
# Com isso, `--enable-mic` removia os drop-ins, reiniciava o WirePlumber, e ele
# restaurava fielmente o mute salvo: "o microfone sumiu" sem nada no log. Era o
# elo que faltava entre "já funcionou antes" e "não funciona mais".
#
# A ordem importa: o WirePlumber GRAVA o estado ao sair, então editar com ele
# vivo seria sobrescrito no shutdown. Paramos, saneamos, e deixamos o
# `restart_wireplumber` subir lendo o arquivo já corrigido.
unmute_dualsense_routes() {
    local rotas="${HOME}/.local/state/wireplumber/default-routes"
    [[ -f "$rotas" ]] || { log "sem default-routes — nada a desmutar"; return 0; }
    grep -qiE 'dualsense.*"mute":true' "$rotas" || {
        log "rotas do DualSense já sem mute"
        return 0
    }
    command -v systemctl >/dev/null 2>&1 && systemctl --user stop wireplumber 2>/dev/null || true
    cp -f "$rotas" "${rotas}.hefesto.bak" 2>/dev/null || true
    # Só as linhas do DualSense: o mute dos OUTROS devices é escolha da usuária.
    sed -i -E '/[Dd]ual[Ss]ense/ s/"mute":true/"mute":false/g' "$rotas"
    log "mute persistido do DualSense removido (backup em ${rotas}.hefesto.bak)"
}

# BUG-MIC-ON-SEM-QUIRK-REABRE-STORM-01: o quirk de áudio USB
# (usbcore.quirks=054c:0ce6:gn) é o que segura o "storm -71" COM o mic ligado.
# Só ATIVO (/proc/cmdline) ou armado em RUNTIME (sysfs) protege a SESSÃO ATUAL —
# o agendado no bootloader (kernelstub/grub) só vale no PRÓXIMO boot, então não
# conta aqui. Espelha o check_usb_quirk do doctor.sh, restrito aos dois sinais
# que valem agora. Retorna 0 se ativo nesta sessão.
usb_quirk_active_session() {
    local marker="054c:0ce6:gn"
    grep -q "${marker}" /proc/cmdline 2>/dev/null && return 0
    { [[ -r /sys/module/usbcore/parameters/quirks ]] \
        && grep -q "${marker}" /sys/module/usbcore/parameters/quirks 2>/dev/null; } && return 0
    return 1
}

enable_mic_dualsense() {
    # BUG-MIC-ON-SEM-QUIRK-REABRE-STORM-01: ligar o mic SEM o quirk de áudio USB
    # ativo nesta sessão pode REABRIR o storm -71 (o controle começa a cair no
    # meio do jogo). Avisamos no stderr e PROSSEGUIMOS — a usuária pode querer o
    # mic mesmo assim. NÃO tocamos no cmdline (gerido pela toolchain pessoal).
    if ! usb_quirk_active_session; then
        printf '[wp-fix] AVISO: ligar o mic do DualSense SEM o quirk de áudio USB ativo nesta sessão pode REABRIR o storm -71 (o controle cai no meio do jogo).\n' >&2
        printf '[wp-fix]        fix: aplique o quirk com `scripts/install_usb_quirk.sh` (efetivo só no próximo boot/replug).\n' >&2
    fi
    # Remove os drop-ins que suprimem/desabilitam o mic do DualSense, deixando-o
    # utilizável e elegível como fonte padrão (a persistência do default fica por
    # conta do estado do WirePlumber + profile pro-audio do card). Idempotente.
    local f removed=0
    for f in "${DROPIN_DST}" "${DROPIN_DISABLE_DST}" "${DROPIN_OUTPUT_DST}"; do
        if [[ -f "$f" ]]; then
            rm -f "$f" && { log "removido drop-in de supressão: $f"; removed=1; }
        fi
    done
    [[ "$removed" -eq 0 ]] && log "nenhum drop-in de supressão presente (mic já livre)"
    # BUG-MIC-MUDO-PERSISTIDO-01: sem isto o mic volta, mas volta MUDO.
    unmute_dualsense_routes
    restart_wireplumber
}

# ID da fonte de CAPTURA do DualSense no `wpctl status` (vazio se não houver).
# Espelho de pick_target_source_id com o critério invertido, e com o mesmo
# cuidado: o '.monitor' do sink também casa "DualSense" no nome, mas é o
# loopback da SAÍDA — elegê-lo como microfone é o bug clássico "gravei o som do
# sistema em vez da minha voz".
pick_dualsense_source_id() {
    wpctl status 2>/dev/null | awk '
        /Sources:/ {insrc=1; next}
        insrc && (/Filters:/ || /Sinks:/ || /Streams:/ || /Video/) {insrc=0}
        insrc {
            if (match($0, /[0-9]+\./)) {
                id = substr($0, RSTART, RLENGTH - 1)
                desc = substr($0, RSTART + RLENGTH)
                if (desc ~ /[Dd]ual[Ss]ense/ && desc !~ /[Mm]onitor/) {
                    if (first == "") first = id
                }
            }
        }
        END { print first }
    '
}

# MIC-USB-01 (entrega 3) — PROMOÇÃO EXPLÍCITA do mic do controle a padrão.
#
# O drop-in 51 REBAIXA a prioridade da fonte (priority.session = 50) para o
# DualSense não virar microfone padrão sozinho ao conectar. Isso está CERTO e
# nunca foi o culpado do mute — a queixa "o controle fica mexendo no microfone"
# é exatamente o que ele resolve. Mas rebaixar por default e não oferecer a
# subida transformou uma política em uma proibição: com o 51 no lugar, o
# `set-default-source` da usuária era sobrescrito de volta para o monitor da
# saída no próximo settle, e não havia caminho nenhum de escolher o DualSense.
#
# Promover é um gesto EXPLÍCITO, então ele desfaz explicitamente as três coisas
# que segurariam o microfone: os drop-ins de supressão (51/52/53), as camadas 1
# e 2 do mudo (delegadas ao `doctor.sh --fix-mic`, que é o dono dessa cura) e a
# ausência de eleição. O caminho de volta é o `--install` de sempre.
promote_source_dualsense() {
    # Reusa o enable-mic inteiro: remove 51/52/53, desmuta as rotas, avisa sobre
    # o quirk de áudio USB e reinicia o WirePlumber.
    enable_mic_dualsense
    # Camadas 1 e 2 têm UM dono: o doctor. Promover uma fonte cujo perfil está no
    # S/PDIF seria promover silêncio — o pior resultado possível para este modo,
    # porque a usuária veria "DualSense é o microfone padrão" e pico 0.
    if [[ -x "${ROOT_DIR}/scripts/doctor.sh" ]]; then
        bash "${ROOT_DIR}/scripts/doctor.sh" --fix-mic --quiet || true
    fi
    if ! command -v wpctl >/dev/null 2>&1; then
        log "wpctl ausente — não consegui eleger o DualSense como fonte padrão"
        return 1
    fi
    # Settle: o restart do WirePlumber + a troca de perfil recriam o nó, e o ID
    # muda junto. Eleger o ID velho falha calado.
    local i alvo=""
    for i in 1 2 3 4 5 6 7 8 9 10; do
        alvo="$(pick_dualsense_source_id || true)"
        [[ -n "${alvo}" ]] && break
        sleep 0.3
    done
    if [[ -z "${alvo}" ]]; then
        log "nenhuma fonte de captura do DualSense apareceu — o controle está no cabo?"
        log "  (por Bluetooth não existe fonte para promover: o áudio vem como Opus"
        log "   dentro dos reports HID e precisa da ponte — 'hefesto-dualsense4unix mic bt')"
        return 1
    fi
    if wpctl set-default "${alvo}" 2>/dev/null; then
        log "mic do DualSense promovido a fonte padrão (id ${alvo}) e persistido"
    else
        log "aviso: 'wpctl set-default ${alvo}' falhou"
        return 1
    fi
}

# `source scripts/fix_wireplumber_default_source.sh` carrega as funções SEM
# despachar — é o que permite testar `_pilha_sem_dualsense` executando a função
# de verdade, em vez de reimplementá-la no teste. Mesmo molde do `scripts/doctor.sh`
# (que faz `if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then main; fi` no fim).
# A execução direta segue idêntica: MODE já foi resolvido acima.
[[ "${BASH_SOURCE[0]}" == "${0}" ]] || return 0

case "${MODE}" in
    status)
        show_status
        ;;
    enable-mic)
        enable_mic_dualsense
        show_status
        ;;
    unmute-routes)
        # MIC-USB-01 camada 1, isolada: o doctor --fix chama por aqui para não
        # duplicar o sed (e o stop/start do WirePlumber que ele exige) do lado
        # de lá. NÃO toca em drop-in nem em fonte padrão — a política que a
        # usuária escolheu continua exatamente como estava.
        unmute_dualsense_routes
        restart_wireplumber
        ;;
    promote)
        rc=0; promote_source_dualsense || rc=$?
        show_status
        exit "${rc}"
        ;;
    reset)
        reset_default_source
        restart_wireplumber
        show_status
        ;;
    install)
        install_dropin
        reset_default_source
        restart_wireplumber
        show_status
        # BUG-WIREPLUMBER-FIX-FALSE-SUCCESS-01: validar o ATIVO, não só o configured.
        sleep 0.5
        rc=0; verify_active_not_dualsense || rc=$?
        exit "${rc}"
        ;;
    disable)
        install_disable_dropin
        remove_configured_dualsense
        restart_wireplumber
        # após o disable o mic some; elege a onboard como default (evita cair no
        # monitor do sink do DualSense) e confirma que o ativo != mic do DualSense.
        sleep 1
        reset_default_source
        sleep 0.5
        rc=0; verify_active_not_dualsense || rc=$?
        show_status
        exit "${rc}"
        ;;
esac
