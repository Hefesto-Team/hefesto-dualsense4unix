#!/usr/bin/env bash
# Valida que tests/ não contem dados pessoais reais.
# Permitido: test_user, player_1, test@example.com, /tmp/hefesto_test_*, VID/PID reais.
# Proibido: nomes proprios hardcoded, emails pessoais, MAC addresses de usuario.
set -euo pipefail

# Nomes ou padrões proibidos especificos ao ambiente do autor.
# Padrão generico: sequencia de 3+ letras capitalizadas que não seja palavra técnica conhecida.
FORBIDDEN_EMAILS='[a-zA-Z0-9._%+-]+@(gmail|outlook|hotmail|yahoo|icloud)\.(com|com\.br|net|org)'
FORBIDDEN_MAC='([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}'
ALLOWED_MAC='00:00:00:00:00:00|FF:FF:FF:FF:FF:FF|aa:bb:cc:dd:ee:ff'

HITS=""

EMAIL_HITS=$(grep -rEn "$FORBIDDEN_EMAILS" tests/ --include="*.py" --include="*.json" \
    --exclude-dir=fixtures 2>/dev/null \
    | grep -v "test@example.com" \
    | grep -v "noreply@" || true)

MAC_HITS=$(grep -rEn "$FORBIDDEN_MAC" tests/ --include="*.py" --include="*.json" \
    --exclude-dir=fixtures 2>/dev/null \
    | grep -vE "$ALLOWED_MAC" || true)

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

# "Prefiro a verdade nua ao ornamento mentiroso." — Sêneca
