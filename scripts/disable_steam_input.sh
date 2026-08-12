#!/usr/bin/env bash
# disable_steam_input.sh — desliga Steam Input PSSupport no DualSense para
# evitar conflito com o daemon Hefesto (FEAT-DISABLE-STEAM-INPUT-PSSUPPORT-01).
#
# Por quê: a Steam, com "PlayStation Controller Support" em modo "Always
# enabled" (SteamController_PSSupport=2), pega o /dev/hidraw* do DualSense
# exclusivamente e re-injeta como "Steam Virtual Gamepad" com bindings de
# desktop_ps4.vdf — mapeia touchpad como mouse absoluto, botões como teclas
# globais, em qualquer janela em background. Isso conflita com o daemon
# Hefesto, que também quer ler o controle, e (sem o daemon) é a causa dos
# 3 sintomas clássicos: touchpad move cursor, mic muting spam, botões em
# background. No Windows o driver Sony nativo evita esse caminho.
#
# Onda R (2026-07-19) — SteamController_SwitchSupport: mesmo mecanismo, mas
# para os controles Nintendo/8BitDo em modo Switch (co-op misto, 8BIT-02). Com
# "Nintendo Switch Controller Support" em "Always enabled" (=2), a Steam pega
# o hidraw do controle Switch do mesmo jeito e o mesmo conflito com o daemon
# se aplica. Tratado JUNTO do PSSupport (mesmo grep/sed/status) desde então.
#
# As keys ficam em `localconfig.vdf` per-user em Steam moderno (não no
# config.vdf global como nas versões antigas). Por padrão este script
# itera por TODOS os installs de Steam conhecidos (.deb, Flatpak, Snap,
# Steam tarball) e por TODOS os user-ids dentro de cada um.
#
# Uso:
#   scripts/disable_steam_input.sh [--apply|--apply-quiet|--status|--restore]
#     --apply       (default) fecha Steam, edita os .vdf, reabre Steam se
#                   estava rodando. Backup automático ao lado de cada .vdf.
#     --apply-quiet edita SÓ se a Steam NÃO estiver rodando; se estiver, ADIA
#                   (loga e sai 0) sem fechar a Steam. Usado pelo guard (path/timer)
#                   para nunca matar a Steam no meio de um jogo — a reescrita
#                   acontece quando a Steam já saiu (que é quando ela grava o vdf).
#     --status      só relata o estado atual (PSSupport / SwitchSupport /
#                   UseSteamControllerConfig) em cada .vdf. Não modifica nada.
#     --restore     reverte o último backup (.bak.steam-input-<ts>) de cada .vdf.
#
# Backups: `<localconfig.vdf>.bak.steam-input-<unix-ts>`. Idempotente.
#
# HONESTIDADE-STEAM-01 (25/07) — contrato de SAÍDA legível por máquina.
# O bug curado: a GUI mostrava "desligando Steam Input (fecha e reabre a
# Steam)…", rodava `--apply-quiet` (que por contrato NUNCA fecha a Steam: se
# ela está viva, ADIA e sai 0) e em seguida anunciava "Steam Input desligado"
# incondicionalmente — afirmava sucesso sobre um no-op. Agora toda execução
# que mexe (ou que decide NÃO mexer) termina numa linha canônica
#
#     [steam-input] resultado=<tag>
#
# com tag em: nada-a-fazer | aplicado | adiado-steam-aberta |
#             recusado-jogo-aberto | steam-nao-fechou | erro |
#             restaurado | precisa-corrigir
#
# Exit codes:
#     0  nada a fazer, ação aplicada com sucesso, OU adiado no --apply-quiet
#        (o "adiado" sai 0 DE PROPÓSITO: o guard do systemd
#        hefesto-steam-input-guard.service é Type=oneshot e trataria != 0 como
#        unit FAILED — e adiar com a Steam viva é o caminho NORMAL dele. Quem
#        precisa distinguir "adiado" de "aplicado" lê a tag `resultado=`.)
#     1  erro (sed/cp/awk falharam num .vdf)
#     4  recusado: há um JOGO da Steam aberto (fechar a Steam o MATARIA)
#     5  a Steam não fechou — nada foi editado (edição com ela viva é perdida)

set -uo pipefail   # sem -e: cada usuário tem o seu vdf, falha de um não derruba os outros.

MODE="apply"
for arg in "$@"; do
    case "$arg" in
        --apply)       MODE="apply" ;;
        --apply-quiet) MODE="apply-quiet" ;;
        --status)      MODE="status" ;;
        --restore)     MODE="restore" ;;
        -h|--help)
            # HONESTIDADE-STEAM-01: o range acompanha o cabeçalho (que cresceu
            # com o contrato `resultado=`/exit codes) — help truncado no meio
            # da tabela de códigos seria mais uma mentira pequena.
            sed -n '2,60p' "${BASH_SOURCE[0]}" | sed 's/^# //; s/^#//'
            exit 0
            ;;
        *) printf '[steam-input] aviso: argumento desconhecido: %s\n' "$arg" ;;
    esac
done

log() { printf '[steam-input] %s\n' "$*"; }

# HONESTIDADE-STEAM-01: ÚLTIMA linha de toda execução que muda (ou recusa
# mudar) o estado. É o único jeito de um chamador distinguir "apliquei" de
# "adiei sem tocar em nada" quando os dois saem 0 — a ambiguidade que fazia a
# GUI cantar vitória sobre um no-op. Sempre a última linha, sempre uma só.
resultado() { printf '[steam-input] resultado=%s\n' "$1"; }

# Globs de localconfig.vdf cobrindo formatos comuns de Steam no Linux.
# Bash globbing: matches que não existem são removidos via nullglob.
shopt -s nullglob
VDF_GLOBS=(
    "${HOME}/.steam/steam/userdata/"*/config/localconfig.vdf
    "${HOME}/.local/share/Steam/userdata/"*/config/localconfig.vdf
    "${HOME}/.var/app/com.valvesoftware.Steam/.steam/steam/userdata/"*/config/localconfig.vdf
    "${HOME}/snap/steam/common/.steam/steam/userdata/"*/config/localconfig.vdf
)
# Dedup: paths via symlink (ex: ~/.steam/steam -> ~/.steam/debian-installation)
# podem aparecer duplicados; resolvemos via readlink -f e mantemos só uniques.
VDFS=()
declare -A SEEN
for vdf in "${VDF_GLOBS[@]}"; do
    real="$(readlink -f -- "$vdf" 2>/dev/null || true)"
    [[ -n "${real}" && -f "${real}" ]] || continue
    [[ -n "${SEEN[$real]:-}" ]] && continue
    SEEN[$real]=1
    VDFS+=("$real")
done
shopt -u nullglob

if [[ "${#VDFS[@]}" -eq 0 ]]; then
    log "nenhum localconfig.vdf encontrado — Steam pode não estar instalada ou nunca foi logada"
    resultado "nada-a-fazer"
    exit 0
fi

# Retorna 0 se o vdf tem PSSupport, SwitchSupport ou UseSteamControllerConfig
# em "1" OU "2"; 1 caso contrário. "[12]" pega tanto o "Always enabled" (=2)
# quanto o per-game "1" que o legado aurora-steam-input-fix escrevia (e que
# antes escapava daqui). SwitchSupport (Onda R) replica exatamente o padrão
# do PSSupport para os controles Nintendo/8BitDo em modo Switch.
needs_fix() {
    local vdf="$1"
    grep -qE '"(SteamController_PSSupport|SteamController_SwitchSupport|UseSteamControllerConfig)"[[:space:]]+"[12]"' "$vdf" 2>/dev/null
}

# Lê e mostra contagem por arquivo.
report_state() {
    local vdf="$1" pss sws uscc
    pss="$(grep -E '"SteamController_PSSupport"[[:space:]]+"[12]"' "$vdf" 2>/dev/null | wc -l)"
    sws="$(grep -E '"SteamController_SwitchSupport"[[:space:]]+"[12]"' "$vdf" 2>/dev/null | wc -l)"
    uscc="$(grep -E '"UseSteamControllerConfig"[[:space:]]+"[12]"' "$vdf" 2>/dev/null | wc -l)"
    printf '  %s\n' "$vdf"
    printf '    SteamController_PSSupport="1"|"2": %s\n' "$pss"
    printf '    SteamController_SwitchSupport="1"|"2": %s\n' "$sws"
    printf '    UseSteamControllerConfig="1"|"2": %s\n' "$uscc"
}

# Steam estava rodando antes? Usado para decidir se reabrimos depois.
#
# BUG-STEAM-DETECT-EARLYOOM-FALSE-POSITIVE-01: o steamwebhelper é casado por NOME
# EXATO de processo (pgrep -x, campo comm) em vez da cmdline inteira (-f). Com -f,
# QUALQUER processo que apenas MENCIONE "steamwebhelper" na linha de comando dava
# falso-positivo — em especial o earlyoom, cujo regex `--avoid ^(...|steam|
# steamwebhelper|...)$` lista o nome. O efeito: a Steam "parecia" viva mesmo
# parada (o desligar do Steam Input travava com "Steam ainda rodando") e, pior, o
# fallback `pkill -f` mirava o próprio earlyoom (só não o matou porque roda como
# root). O steam do runtime segue casado pelo PATH (steamrt64/steam), que não
# aparece em listas de nomes-a-evitar.
steam_running() {
    pgrep -af 'steamrt64/steam' >/dev/null 2>&1 || pgrep -x steamwebhelper >/dev/null 2>&1
}

# HONESTIDADE-STEAM-01: espelho EXATO de
# integrations/steam_launch_options.steam_game_running(). O `--apply` fechava a
# Steam sem nunca perguntar se havia um JOGO aberto — e `steam -shutdown` com
# jogo aberto MATA o jogo (progresso não salvo perdido; é o mesmo risco que o
# DEDUP-05 já tratava do lado Python, e que a GUI passa a checar antes de
# clicar). O gate mora AQUI também porque install.sh/purge.sh chamam `--apply`
# direto: a recusa não pode depender de quem chama lembrar de checar.
#
# O `pgrep -f` é seguro aqui: a string `SteamLaunch AppId=` só aparece em
# cmdline de launch REAL da Steam. O falso-positivo histórico
# (BUG-STEAM-DETECT-EARLYOOM-FALSE-POSITIVE-01) era com NOMES de processo.
#
# 12/08/2026 — o `[ ]` e o `[0-9]` NÃO são enfeite, e a frase acima só é
# verdadeira com eles. Duas razões, ambas medidas:
#
#  1. `pgrep -f` compara a regex contra a cmdline de TODO processo, e a cmdline
#     do próprio `pgrep` contém o padrão procurado. Ele exclui o próprio pid —
#     mas não o de OUTRO `pgrep` caçando o mesmo texto, e há um rodando a cada
#     15 s nesta máquina (`~/.local/bin/aurora-game-watch-daemon.sh`). Dois
#     desses se enxergam e ambos respondem "há jogo" com zero jogos abertos.
#  2. Esta linha também virava ISCA para quem procura a mesma agulha: o daemon
#     varre `/proc/*/cmdline` atrás de `SteamLaunch AppId=` e encontrava ESTE
#     `pgrep`, devolvendo uma cmdline sem appid nenhum — o que fazia
#     `steam_game_running_appid()` responder None com o jogo aberto.
#
# `[ ]` casa um espaço literal sem que a regex o contenha; `[0-9]` exige um
# appid de verdade depois do `=`. É o idioma do `ps aux | grep [p]attern`.
steam_game_running() {
    pgrep -f 'SteamLaunch[ ]AppId=[0-9]' >/dev/null 2>&1
}

stop_steam() {
    if ! steam_running; then
        return 0
    fi
    log "fechando Steam (steam -shutdown)..."
    if command -v steam >/dev/null 2>&1; then
        steam -shutdown >/dev/null 2>&1 &
        # Aguarda Steam realmente sair (até 30s). Polling barato.
        local i
        for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
            sleep 2
            steam_running || break
        done
    fi
    if steam_running; then
        log "steam -shutdown não fechou em 30s — fallback pkill"
        # steamwebhelper por nome EXATO (-x), NUNCA -f: senão o pkill mira
        # qualquer processo que só cite "steamwebhelper" na cmdline (ex.: earlyoom).
        pkill -TERM -f 'steamrt64/steam' 2>/dev/null || true
        pkill -TERM -x steamwebhelper 2>/dev/null || true
        sleep 3
        pkill -KILL -f 'steamrt64/steam' 2>/dev/null || true
        pkill -KILL -x steamwebhelper 2>/dev/null || true
    fi
    sleep 2  # margem para Steam terminar de gravar últimos arquivos
    if steam_running; then
        log "ERRO: Steam ainda rodando — não vou arriscar editar enquanto está vivo"
        return 1
    fi
    return 0
}

reopen_steam() {
    if ! command -v steam >/dev/null 2>&1; then
        log "binário 'steam' fora do PATH — não consigo reabrir; abra manualmente"
        return 0
    fi
    log "reabrindo Steam"
    setsid nohup steam </dev/null >/dev/null 2>&1 &
    disown 2>/dev/null || true
}

# Edita um único .vdf inplace, com backup. Idempotente.
# Trocas:
#   "SteamController_PSSupport"\t\t"2"    -> "0"   (global, sempre)
#   "SteamController_SwitchSupport"\t\t"2"-> "0"   (global, sempre)
#   "UseSteamControllerConfig"\t\t"2"     -> "0"   (EXCETO apps da allowlist)
# (Steam usa tabs literais entre key e value no VDF; preservamos exatamente.)
#
# STEAM-INPUT-ALLOWLIST-01 (22/07): há jogos cuja via OFICIAL de DualSense é
# o Steam Input per-app — ex.: Mullet Mad Jack (AppID 2111190) chama
# SetDualSenseTriggerEffect da API Steamworks, que SÓ funciona com o Steam
# Input do jogo ligado (o badge "DualSense Controller" da página é essa via).
# O guard antigo revertia o opt-in per-app silenciosamente e matava o caminho.
# Agora o `UseSteamControllerConfig` dentro de `apps/<appid>` é PRESERVADO
# quando o appid está na allowlist (uma linha por appid; '#' comenta):
ALLOWLIST_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/hefesto-dualsense4unix/steam_input_apps.txt"

# stdin -> stdout: aplica as trocas respeitando a allowlist por-app (pilha de
# blocos do VDF: uma linha `"nome"` seguida de `{` abre um bloco; o appid do
# bloco corrente decide se o UseSteamControllerConfig dele fica em paz).
_transform_vdf() {
    awk -v allowfile="${ALLOWLIST_FILE}" '
    BEGIN {
        if (allowfile != "") {
            while ((getline linha < allowfile) > 0) {
                sub(/#.*$/, "", linha)
                gsub(/[[:space:]]/, "", linha)
                if (linha != "") allow[linha] = 1
            }
            close(allowfile)
        }
        depth = 0
        pending = ""
    }
    {
        line = $0
        if (line ~ /^[[:space:]]*"[^"]*"[[:space:]]*$/) {
            nome = line
            gsub(/^[[:space:]]*"/, "", nome)
            gsub(/"[[:space:]]*$/, "", nome)
            pending = nome
            print line
            next
        }
        if (line ~ /^[[:space:]]*\{[[:space:]]*$/) {
            depth++
            stack[depth] = pending
            pending = ""
            print line
            next
        }
        if (line ~ /^[[:space:]]*\}[[:space:]]*$/) {
            if (depth > 0) { delete stack[depth]; depth-- }
            print line
            next
        }
        gsub(/"SteamController_PSSupport"\t\t"[12]"/, "\"SteamController_PSSupport\"\t\t\"0\"", line)
        gsub(/"SteamController_SwitchSupport"\t\t"[12]"/, "\"SteamController_SwitchSupport\"\t\t\"0\"", line)
        if (line ~ /"UseSteamControllerConfig"\t\t"[12]"/) {
            if (!(depth > 0 && (stack[depth] in allow))) {
                gsub(/"UseSteamControllerConfig"\t\t"[12]"/, "\"UseSteamControllerConfig\"\t\t\"0\"", line)
            }
        }
        print line
    }'
}

apply_vdf() {
    local vdf="$1"
    if ! needs_fix "$vdf"; then
        log "ok (nada a fazer): $vdf"
        return 0
    fi
    local tmp="${vdf}.hefesto-tmp"
    if ! _transform_vdf < "$vdf" > "$tmp"; then
        log "ERRO: transformação falhou em $vdf"
        rm -f -- "$tmp"
        return 1
    fi
    # Idempotência real: com um appid da allowlist ligado, o needs_fix acusa
    # "[12]" para sempre — o cmp decide se há edição DE VERDADE (sem ele o
    # guard geraria backup novo + rewrite a cada rodada).
    if cmp -s -- "$vdf" "$tmp"; then
        log "ok (restante é allowlist per-app, preservada): $vdf"
        rm -f -- "$tmp"
        return 0
    fi
    local ts bak
    ts="$(date +%s)"
    bak="${vdf}.bak.steam-input-${ts}"
    if ! cp -a -- "$vdf" "$bak"; then
        log "ERRO: cp falhou ao criar backup: $bak"
        rm -f -- "$tmp"
        return 1
    fi
    # `cat > vdf` (e não mv) preserva dono/permissões/inode do original.
    if ! cat -- "$tmp" > "$vdf"; then
        log "ERRO: escrita falhou em $vdf — restaurando do backup"
        cp -a -- "$bak" "$vdf" || true
        rm -f -- "$tmp"
        return 1
    fi
    rm -f -- "$tmp"
    log "editado (backup em $bak): $vdf"
}

# Reverte um único .vdf do backup mais recente.
restore_vdf() {
    local vdf="$1"
    local latest
    latest="$(ls -1t "${vdf}.bak.steam-input-"* 2>/dev/null | head -1 || true)"
    if [[ -z "${latest}" ]]; then
        log "sem backup para restaurar: $vdf"
        return 0
    fi
    if cp -a -- "$latest" "$vdf"; then
        log "restaurado de $latest -> $vdf"
    else
        log "ERRO: falha ao restaurar $vdf"
        return 1
    fi
}

# STEAM-INPUT-ALLOWLIST-01: "precisa de correção DE VERDADE" = a transformação
# (que preserva o opt-in per-app da allowlist) mudaria o arquivo. O needs_fix
# clássico segue como pré-filtro rápido; este decide o veredito do --status —
# sem ele, ligar o Steam Input do MMJ (deliberado) acusaria 'ação sugerida'
# para sempre.
needs_real_fix() {
    local vdf="$1"
    needs_fix "$vdf" || return 1
    local tmp
    tmp="$(mktemp)"
    if ! _transform_vdf < "$vdf" > "$tmp" 2>/dev/null; then
        rm -f -- "$tmp"
        return 0
    fi
    if cmp -s -- "$vdf" "$tmp"; then
        rm -f -- "$tmp"
        return 1
    fi
    rm -f -- "$tmp"
    return 0
}

case "${MODE}" in
    status)
        log "${#VDFS[@]} localconfig.vdf encontrado(s):"
        any_needs=0
        any_allow=0
        for vdf in "${VDFS[@]}"; do
            report_state "$vdf"
            if needs_real_fix "$vdf"; then
                any_needs=1
            elif needs_fix "$vdf"; then
                any_allow=1
            fi
        done
        if [[ "${any_needs}" -eq 1 ]]; then
            log "ação sugerida: scripts/disable_steam_input.sh --apply"
            resultado "precisa-corrigir"
        else
            if [[ "${any_allow}" -eq 1 ]]; then
                log "nota: Steam Input per-app ATIVO só em apps da allowlist (deliberado — ex.: MMJ)"
            fi
            log "tudo limpo — PSSupport/SwitchSupport não estão em modo 1|2 em nenhum arquivo (fora da allowlist)"
            resultado "nada-a-fazer"
        fi
        ;;
    restore)
        # HONESTIDADE-STEAM-01: o restore também fecha a Steam — logo também
        # precisa do gate de JOGO aberto (antes ele derrubaria o jogo junto).
        if steam_game_running; then
            log "RECUSADO: há um JOGO da Steam em execução — fechar a Steam agora o MATARIA"
            resultado "recusado-jogo-aberto"
            exit 4
        fi
        log "revertendo do backup mais recente em cada arquivo"
        was_running=0
        steam_running && was_running=1
        if [[ "${was_running}" -eq 1 ]]; then
            if ! stop_steam; then
                resultado "steam-nao-fechou"
                exit 5
            fi
        fi
        rc=0
        for vdf in "${VDFS[@]}"; do
            restore_vdf "$vdf" || rc=1
        done
        [[ "${was_running}" -eq 1 ]] && reopen_steam
        if [[ "${rc}" -eq 0 ]]; then resultado "restaurado"; else resultado "erro"; fi
        exit "${rc}"
        ;;
    apply)
        # HONESTIDADE-STEAM-01: gate de JOGO aberto ANTES de qualquer decisão
        # sobre a Steam (mesma ordem do steam_launch_options.main). Sem ele o
        # `--apply` do install/purge/GUI mataria um jogo em andamento.
        if steam_game_running; then
            log "RECUSADO: há um JOGO da Steam em execução — fechar a Steam agora o MATARIA"
            log "  feche o jogo e rode de novo (nada foi tocado)"
            resultado "recusado-jogo-aberto"
            exit 4
        fi
        # Pré-flight: alguém precisa fix? Se ninguém, evita fechar Steam à toa.
        #
        # D-32 (05/08/2026): este pré-voo usava o `needs_fix`, que casa também
        # o opt-in per-app da allowlist. Com SÓ appids da allowlist ligados ele
        # dizia "sim, precisa" — e o `--apply` FECHAVA E REABRIA a Steam dela
        # para não mudar byte nenhum, terminando em `resultado=aplicado`, que a
        # janela traduzia para "a Steam não sequestra mais o seu controle".
        # Quem decide aqui é o `needs_real_fix`: precisa = a transformação
        # MUDARIA o arquivo. Mesmo critério do `--status`.
        any_needs=0
        for vdf in "${VDFS[@]}"; do
            needs_real_fix "$vdf" && any_needs=1
        done
        if [[ "${any_needs}" -eq 0 ]]; then
            log "nada a fazer — Steam Input já está OFF em todos os ${#VDFS[@]} vdf(s)"
            resultado "nada-a-fazer"
            exit 0
        fi
        was_running=0
        steam_running && was_running=1
        if [[ "${was_running}" -eq 1 ]]; then
            if ! stop_steam; then
                resultado "steam-nao-fechou"
                exit 5
            fi
        fi
        rc=0
        for vdf in "${VDFS[@]}"; do
            apply_vdf "$vdf" || rc=1
        done
        [[ "${was_running}" -eq 1 ]] && reopen_steam
        if [[ "${rc}" -eq 0 ]]; then resultado "aplicado"; else resultado "erro"; fi
        exit "${rc}"
        ;;
    apply-quiet)
        # Nunca fecha a Steam. Se ela está viva, adia (a reescrita pega quando sair).
        if steam_running; then
            log "Steam rodando — adiado (não vou fechar; reaplico quando a Steam sair)"
            # Sai 0 (contrato do guard oneshot) mas DIZ que adiou: é esta tag
            # que impede a GUI de anunciar "Steam Input desligado" sobre um no-op.
            resultado "adiado-steam-aberta"
            exit 0
        fi
        # D-32, mesma cura do `--apply` acima: este é o modo que o guarda de
        # 30 em 30 minutos roda, e é dele que saiu o `resultado=aplicado` das
        # 02:13:13 de 05/08 sobre um arquivo que ninguém tocou. O `--apply-quiet`
        # não fecha a Steam, mas a tag mentirosa chega igual à janela (o botão
        # "Aplicar correções" e o "Deixar tudo pronto" leem esta linha).
        any_needs=0
        for vdf in "${VDFS[@]}"; do
            needs_real_fix "$vdf" && any_needs=1
        done
        if [[ "${any_needs}" -eq 0 ]]; then
            log "nada a fazer — Steam Input já está OFF em todos os ${#VDFS[@]} vdf(s)"
            resultado "nada-a-fazer"
            exit 0
        fi
        rc=0
        for vdf in "${VDFS[@]}"; do
            apply_vdf "$vdf" || rc=1
        done
        # Steam não estava rodando — nada a reabrir.
        if [[ "${rc}" -eq 0 ]]; then resultado "aplicado"; else resultado "erro"; fi
        exit "${rc}"
        ;;
esac
