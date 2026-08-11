#!/usr/bin/env bash
# TRES-CONTROLES-01 / SDL-ATALHO-01 — mede se a cura do espelho está agindo.
#
# A DÚVIDA, aberta em 11/08/2026 pela leitura do fonte do SDL: em SDL2 e SDL3
# (mesmo corpo), `SDL_ShouldIgnoreGamepad` tem um atalho —
#
#     if (SDL_IsJoystickSteamVirtualGamepad(...))
#         return !allow_steam_virtual_gamepad;
#
# — que decide o gamepad virtual da Steam (`0x28de/0x11ff`) ANTES de consultar
# a lista de `SDL_GAMECONTROLLER_IGNORE_DEVICES`. Para aquele par, a lista NUNCA
# é lida. Se a Steam exportar `SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD=1`
# — e a string existe no `steamclient.so` desta máquina —, a cura da
# TRES-CONTROLES-01 não age pelo caminho do SDL, e o espelho Xbox continua
# visível para o jogo.
#
# Isto é LEITURA PURA: só `/proc/<pid>/environ` de processos do próprio usuário.
# Não escreve nada, não pede sudo, não toca em controle nenhum.
#
# Uso: com a Steam aberta (e, de preferência, um jogo em sessão),
#
#     bash scripts/medir_steam_virtual_gamepad.sh
#
set -uo pipefail

azul()  { printf '\033[1;36m%s\033[0m\n' "$*"; }
ok()    { printf '  [OK]   %s\n' "$*"; }
falhou() { printf '  [NAO]  %s\n' "$*"; }
info()  { printf '         %s\n' "$*"; }

# `steam` casa com processos que apenas MENCIONAM a palavra (o earlyoom, por
# exemplo, a traz na lista de proteção). Por isso o filtro é pelo executável.
pids_da_steam() {
    local p
    for p in $(pgrep -u "$(id -u)" -x steam steamwebhelper 2>/dev/null); do
        printf '%s\n' "$p"
    done
    # o processo do jogo herda o ambiente da Steam e é onde a variável mais
    # importa — é ele que o SDL do jogo lê.
    for p in $(pgrep -u "$(id -u)" -f 'reaper SteamLaunch|proton|pv-bwrap' 2>/dev/null); do
        printf '%s\n' "$p"
    done
}

le_env() {  # le_env <pid> <NOME> -> imprime o valor, ou nada
    tr '\0' '\n' < "/proc/$1/environ" 2>/dev/null | sed -n "s/^$2=//p" | head -1
}

azul "== quem está de pé =="
mapfile -t PIDS < <(pids_da_steam | sort -un)
if [[ "${#PIDS[@]}" -eq 0 ]]; then
    falhou "Steam não está aberta — abra-a (e um jogo, se puder) e rode de novo."
    info "Sem ela não há ambiente para ler, e a pergunta continua em aberto."
    exit 2
fi
for p in "${PIDS[@]}"; do
    info "pid $p  $(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null | cut -c1-70)"
done

azul ""
azul "== PERGUNTA 1: a Steam liga o atalho do gamepad virtual? =="
achou_allow=0
for p in "${PIDS[@]}"; do
    v="$(le_env "$p" SDL_GAMECONTROLLER_ALLOW_STEAM_VIRTUAL_GAMEPAD)"
    if [[ -n "${v}" ]]; then
        achou_allow=1
        if [[ "${v}" == "1" ]]; then
            falhou "pid $p: ALLOW_STEAM_VIRTUAL_GAMEPAD=1 — o atalho do SDL VENCE"
            info "A lista de IGNORE_DEVICES não é consultada para 0x28de/0x11ff."
            info "A cura da TRES-CONTROLES-01 NÃO age por este caminho."
        else
            ok "pid $p: ALLOW_STEAM_VIRTUAL_GAMEPAD=${v} — o atalho não bloqueia"
        fi
    fi
done
[[ "${achou_allow}" -eq 0 ]] && {
    ok "a variável não está exportada em nenhum processo"
    info "Sem ela, allow_steam_virtual_gamepad fica no default do SDL."
    info "ATENÇÃO: isto NÃO prova que a cura age — prova que a Steam não a"
    info "desligou explicitamente. O default do SDL decide o resto."
}

azul ""
azul "== PERGUNTA 2: a nossa lista de ignorados chegou ao jogo? =="
for p in "${PIDS[@]}"; do
    v="$(le_env "$p" SDL_GAMECONTROLLER_IGNORE_DEVICES)"
    [[ -n "${v}" ]] && { ok "pid $p: ${v}"; }
done | sort -u || true
if ! for p in "${PIDS[@]}"; do le_env "$p" SDL_GAMECONTROLLER_IGNORE_DEVICES; done | grep -q .; then
    falhou "IGNORE_DEVICES não chegou a processo nenhum"
    info "É o que o wrapper hefesto-launch deveria injetar nas Launch Options."
fi

azul ""
azul "== PERGUNTA 3: o Proton está com o hidraw desligado? =="
for p in "${PIDS[@]}"; do
    v="$(le_env "$p" PROTON_DISABLE_HIDRAW)"
    [[ -n "${v}" ]] && ok "pid $p: PROTON_DISABLE_HIDRAW=${v}"
done | sort -u || true
if ! for p in "${PIDS[@]}"; do le_env "$p" PROTON_DISABLE_HIDRAW; done | grep -q .; then
    info "não exportada (só importa com um jogo Proton em sessão)"
fi

azul ""
azul "== o espelho existe AGORA? =="
espelho=0
for d in /sys/class/input/input*; do
    [[ -r "$d/name" ]] || continue
    n="$(cat "$d/name" 2>/dev/null)"
    case "$n" in
        *"X-Box 360 pad"*|*"Microsoft X-Box"*)
            espelho=1
            info "espelho: ${n}  ($(basename "$d"))"
            ;;
    esac
done
[[ "${espelho}" -eq 0 ]] && ok "nenhum espelho Xbox da Steam em /sys/class/input"

azul ""
info "Leitura pura: nada foi escrito. Registre o resultado em"
info "docs/protocol/pilha-steam-input-xpad-sdl.md, seção do atalho do SDL."
