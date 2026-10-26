#!/usr/bin/env bash
set -euo pipefail

FORBIDDEN_EMAILS='[a-zA-Z0-9._%+-]+@(gmail|outlook|hotmail|yahoo|icloud)\.(com|com\.br|net|org)'
FORBIDDEN_MAC='([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}'

ALLOWED_MAC='00:00:00:00:00:00|FF:FF:FF:FF:FF:FF|([0-9a-fA-F]{2}:){2}[0-9a-fA-F]{2}:00:00:[0-9a-fA-F]{2}|02:[fF][eE]:|[aA][aA]:[bB][bB]:[cC][cC]:'
ALLOWED_EMAIL='test@example\.com|noreply@'

_filtrar_macs_permitidos() {
    local hit mac
    while IFS= read -r hit; do
        [[ -z "$hit" ]] && continue
        mac="${hit: -17}"
        if [[ "$mac" =~ ^($ALLOWED_MAC) ]]; then
            continue
        fi
        printf '%s\n' "$hit"
    done
}

_filtrar_emails_permitidos() {
    local hit email
    while IFS= read -r hit; do
        [[ -z "$hit" ]] && continue
        email=$(printf '%s' "$hit" | sed -E 's/^.*:[0-9]+://')
        if printf '%s' "$email" | grep -qE "^($ALLOWED_EMAIL)"; then
            continue
        fi
        printf '%s\n' "$hit"
    done
}

EXCLUIR_EXTENSAO=(
    --exclude="*.png" --exclude="*.jpg" --exclude="*.jpeg" --exclude="*.gif"
    --exclude="*.ico" --exclude="*.pdf" --exclude="*.zip" --exclude="*.gz"
    --exclude="*.xz" --exclude="*.mo" --exclude="*.woff" --exclude="*.woff2"
    --exclude="*.sha256" --exclude="*.bin" --exclude="*.btsnoop"
)

HITS=""

EMAIL_HITS=$(grep -rEonI "$FORBIDDEN_EMAILS" tests/ \
    "${EXCLUIR_EXTENSAO[@]}" --exclude-dir=fixtures 2>/dev/null \
    | _filtrar_emails_permitidos || true)

MAC_HITS=$(grep -rEonI "$FORBIDDEN_MAC" tests/ \
    "${EXCLUIR_EXTENSAO[@]}" --exclude-dir=fixtures 2>/dev/null \
    | _filtrar_macs_permitidos || true)

if [[ -n "$EMAIL_HITS" ]]; then
    echo "DADOS PESSOAIS EM TESTES (emails):"
    echo "$EMAIL_HITS"
    HITS="yes"
fi

if [[ -n "$MAC_HITS" ]]; then
    echo "DADOS PESSOAIS EM TESTES (MAC addresses):"
    echo "$MAC_HITS"
    HITS="yes"
fi

if [[ -n "$HITS" ]]; then
    echo ""
    echo "Use dados de teste neutros: test@example.com, 00:00:00:00:00:00, test_user."
    exit 1
fi

echo "OK: dados de teste neutros."
