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
ALLOWED_EMAIL='test@example\.com|noreply@'

# GATE-TEST-DATA-CEGO-POR-VIZINHO-01 (26/08/2026). MEDIDO.
# ---------------------------------------------------------------------------
# A allowlist era aplicada com `grep -vE`, que descarta a LINHA e não o
# CASAMENTO. Um MAC real ao lado de um permitido sumia junto com o vizinho —
# medido num tests/ de mentira, com uma linha só:
#
#   PERMITIDO = "aa:bb:cc:11:22:33"; REAL = "<endereço de aparência real>"
#   ->  "OK: dados de teste neutros."   rc=0
#
# E não era caso raro: a convenção desta casa é escrever o par mascarado e o
# "antes" na mesma linha para explicar a máscara. A cura é `grep -o`, que
# devolve um casamento por linha de saída — aí a allowlist decide sobre o
# ENDEREÇO, e não sobre a companhia dele. O mesmo valia para os dois `grep -v`
# do bloco de e-mail, e por isso os dois viraram um `ALLOWED_EMAIL`.
#
# `grep -on` imprime `caminho:linha:casamento`, e o casamento é o RABO da
# saída: MAC tem 17 caracteres, e o e-mail é o que vem depois do último `:`
# que separa o número de linha. O `${var: -17}` do MAC é seguro porque a forma
# é de tamanho fixo; o e-mail usa `sed` porque não é.
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

# GATE-TEST-DATA-SO-DUAS-EXTENSOES-01 (26/08/2026).
# ---------------------------------------------------------------------------
# A varredura era `--include="*.py" --include="*.json"`, uma allowlist de DUAS
# extensões. Hoje `git ls-files tests/` devolve py, json, js e bin — e os dois
# últimos moram em `tests/fixtures/`, que já está fora. Ou seja: **nenhum
# arquivo desta árvore escapava hoje**, e é por isso que o buraco atravessou um
# mês sem sintoma. Ele é LATENTE, não vivo: no dia em que um `.yaml`, um `.csv`
# ou um `.conf` de teste entrar em `tests/`, ele nasce invisível a este portão.
#
# Allowlist de extensão é a forma errada da régua — ela erra em silêncio a cada
# arquivo novo. A denylist erra do lado seguro: alarme falso, que se vê.
# O `-I` do grep já pula binário sozinho; a lista abaixo é só para o que é
# texto e onde hexadecimal é ruído de propósito.
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

# "Prefiro a verdade nua ao ornamento mentiroso." — Sêneca
