#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

ISENTOS='^(scripts/check_a_grafia_do_nome\.py'
ISENTOS+='|scripts/aplicar_a_grafia_do_nome\.sh'
ISENTOS+='|tests/unit/test_portao_a_grafia_do_nome_morde\.py)$'

if git grep -lIz 'Dualsense4Unix' -- . | grep -zEv "$ISENTOS" \
    | xargs -0 --no-run-if-empty perl -CSD -pi -e \
        's/(?<![-\w])Dualsense4Unix(?! Virtual )(?! virtual\))/DualSense4Unix/g'
then
    :
fi

if command -v msgfmt >/dev/null 2>&1; then
    bash scripts/i18n_compile.sh >/dev/null
else
    echo "AVISO: msgfmt ausente — os .mo ficaram com os msgid velhos." >&2
fi

echo "grafia reaplicada. Confira: python3 scripts/check_a_grafia_do_nome.py"
