#!/usr/bin/env bash
set -uo pipefail
export LC_ALL=C
DESDE="${1:-today}"

J=$(journalctl --user -u hefesto-dualsense4unix.service --since "$DESDE" --no-pager 2>/dev/null)
if [ -z "$J" ]; then
  echo "SEM JOURNAL do daemon desde «$DESDE» — não sei dizer quem vibrou."
  echo "Ausência é resposta: não afirmo nada."
  exit 2
fi

echo "── quem ENTROU em modo háptica (som_radio_ponte_de_pe arranjo=0x32) ──"
printf '%s\n' "$J" | grep "som_radio_ponte_de_pe" | grep "0x32" \
  | grep -oE "uniq=[0-9a-f:]+" | sort | uniq -c | sort -rn \
  | sed 's/^/  /' || echo "  (nenhum)"

echo
echo "── quem TENTOU e foi recusado (haptica_sem_fonte) ──"
printf '%s\n' "$J" | grep "haptica_sem_fonte" \
  | grep -oE "uniq=[0-9a-f:]+" | sort | uniq -c | sort -rn \
  | sed 's/^/  /' || echo "  (nenhum)"

echo
echo "── quem ficou no SOM (arranjo=0x35), que é o certo para quem não joga ──"
printf '%s\n' "$J" | grep "som_radio_ponte_de_pe" | grep "0x35" \
  | grep -oE "uniq=[0-9a-f:]+" | sort | uniq -c | sort -rn \
  | sed 's/^/  /' || echo "  (nenhum)"

echo
echo "════════════════════════════════════════════════════════════════"
n=$(printf '%s\n' "$J" | grep "som_radio_ponte_de_pe" | grep -c "0x32" || true)
q=$(printf '%s\n' "$J" | grep "som_radio_ponte_de_pe" | grep "0x32" \
    | grep -oE "uniq=[0-9a-f:]+" | sort -u | wc -l)
echo "  entradas em háptica pelo rádio: $n"
echo "  controles DO RÁDIO que entraram em háptica: $q"
echo "  (o controle do CABO não passa por aqui — ele usa o endpoint REAL)"
