#!/usr/bin/env bash
# shellcheck shell=bash

declare -F _janela_diz >/dev/null 2>&1 || _janela_diz() { printf '%s\n' "$*"; }
declare -F _janela_avisa >/dev/null 2>&1 || _janela_avisa() { printf 'aviso: %s\n' "$*"; }

_steam_fechada_por_nos=0
_vigia_parado_por_nos=0

parar_o_vigia_da_steam() {
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "parar o vigia da Steam durante os passos da Steam (ele escreve os mesmos arquivos) e religá-lo no fim"
        return 0
    fi
    systemctl --user stop hefesto-steam-input-guard.path hefesto-steam-input-guard.timer >/dev/null 2>&1 || true
    _vigia_parado_por_nos=1
}

religar_o_vigia_se_parei() {
    [[ "${_vigia_parado_por_nos:-0}" -eq 1 ]] || return 0
    _vigia_parado_por_nos=0
    systemctl --user start hefesto-steam-input-guard.path hefesto-steam-input-guard.timer >/dev/null 2>&1 || true
}

fechar_a_steam_uma_vez() {
    local rc=0
    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        _faria "FECHAR a Steam, se estiver aberta, UMA vez para os passos da Steam (a Steam regrava os arquivos ao sair, e com a Steam viva as edições seriam engolidas), e reabri-la no fim. Com um JOGO aberto, nada é fechado e esses passos adiam."
    elif [[ -f "${LAUNCH_MIGRATE_PY}" ]] && command -v python3 >/dev/null 2>&1; then
        _janela_diz "se a Steam estiver aberta, a Steam fecha agora UMA vez e reabre no fim"
        _janela_diz "dos passos da Steam — pause downloads antes de seguir."
        _janela_diz "(com um jogo aberto, nada é fechado e esses passos adiam.)"
        python3 "${LAUNCH_MIGRATE_PY}" --fechar-steam || rc=$?
        case "${rc}" in
            0) _steam_fechada_por_nos=1 ;;
            4) : ;;
            *) _janela_avisa "a Steam segue aberta (jogo aberto, ou a Steam não fechou) — os passos da Steam adiam o que precisar da Steam fechada, cada um com o comando" ;;
        esac
    else
        _janela_avisa "steam_launch_options.py ausente ou sem python3 — cada passo da Steam cuida da própria janela"
    fi
}

reabrir_a_steam_se_fechei() {
    [[ "${_steam_fechada_por_nos:-0}" -eq 1 ]] || return 0
    _steam_fechada_por_nos=0
    python3 "${LAUNCH_MIGRATE_PY}" --reabrir-steam >/dev/null 2>&1 || true
}
