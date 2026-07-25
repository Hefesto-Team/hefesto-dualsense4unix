#!/usr/bin/env bash
# Valida que tests/ não contem dados pessoais reais.
# Permitido: test_user, player_1, test@example.com, /tmp/hefesto_test_*, VID/PID reais.
# Proibido: nomes proprios hardcoded, emails pessoais, MAC addresses de usuario.
set -euo pipefail

# Nomes ou padrões proibidos especificos ao ambiente do autor.
# Padrão generico: sequencia de 3+ letras capitalizadas que não seja palavra técnica conhecida.
FORBIDDEN_EMAILS='[a-zA-Z0-9._%+-]+@(gmail|outlook|hotmail|yahoo|icloud)\.(com|com\.br|net|org)'
FORBIDDEN_MAC='([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}'

# BUG-GATE-TEST-DATA-CONTRADIZ-O-GATE-DE-ANONIMATO-01 (25/07): este gate
# reprovava exatamente a convenção que o OUTRO gate do projeto EXIGE. O
# `tests/unit/test_docs_mac_anonimato.py` manda mascarar MAC como
# `OUI:00:00:NN` (preserva o fabricante, apaga o aparelho), e aqui esse padrão
# caía como "dado pessoal". Dois gates do mesmo repositório em contradição — e
# o desempate foi desligar este, que não roda em workflow NENHUM. Um gate que
# ninguém pode satisfazer não protege nada; só ensina a ignorá-lo.
#
# A allowlist agora cobre as três famílias sintéticas legítimas:
#   OUI:00:00:NN  — a máscara da casa, imposta pelo gate de anonimato;
#   02:fe:*       — o vpad do hefesto, MAC localmente administrado por
#                   construção (bit 1 do primeiro octeto), não existe em
#                   hardware de ninguém;
#   aa:bb:cc:*    — faixa de documentação já usada nos testes.
# Qualquer MAC fora dessas famílias continua reprovando, que é o ponto.
ALLOWED_MAC='00:00:00:00:00:00|FF:FF:FF:FF:FF:FF|([0-9a-fA-F]{2}:){2}[0-9a-fA-F]{2}:00:00:[0-9a-fA-F]{2}|02:[fF][eE]:|[aA][aA]:[bB][bB]:[cC][cC]:'

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
