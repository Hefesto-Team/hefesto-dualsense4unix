#!/usr/bin/env bash
# shellcheck shell=bash

python_do_sistema() {
    if [[ -x /usr/bin/python3 ]]; then
        printf '/usr/bin/python3\n'
    else
        printf 'python3\n'
    fi
}

_versao_da_venv() {
    local venv="$1" achado pasta
    achado="$(sed -n 's/^version\(_info\)\{0,1\}[[:space:]]*=[[:space:]]*\([0-9][0-9]*\.[0-9][0-9]*\).*/\2/p' \
        "${venv}/pyvenv.cfg" | head -n 1)"
    if [[ -z "${achado}" ]]; then
        for pasta in "${venv}"/lib/python[0-9]*.[0-9]*; do
            [[ -d "${pasta}" ]] && achado="${pasta##*/python}"
        done
    fi
    printf '%s\n' "${achado}"
}

venv_doente() {
    local venv="$1" sistema="$2" casa versao_do_sistema
    [[ -d "${venv}" ]] || return 1
    if [[ ! -r "${venv}/pyvenv.cfg" ]]; then
        printf 'a .venv não tem o pyvenv.cfg (ficou pela metade)\n'
        return 0
    fi
    if ! "${venv}/bin/python" -c '' >/dev/null 2>&1; then
        printf 'o python da .venv não roda (o link sumiu ou ficou pela metade)\n'
        return 0
    fi
    casa="$(sed -n 's/^home[[:space:]]*=[[:space:]]*//p' "${venv}/pyvenv.cfg" | head -n 1)"
    if [[ "${sistema}" == /usr/bin/python3 && -n "${casa}" && "${casa}" != /usr/bin ]]; then
        printf 'a .venv foi criada com um Python que não é o do sistema (%s)\n' "${casa}"
        return 0
    fi
    versao_do_sistema="$("${sistema}" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || true)"
    casa="$(_versao_da_venv "${venv}")"
    if [[ -n "${versao_do_sistema}" && -n "${casa}" && "${casa}" != "${versao_do_sistema}" ]]; then
        printf 'a .venv é do Python %s, e o sistema agora está no %s\n' "${casa}" "${versao_do_sistema}"
        return 0
    fi
    return 1
}
