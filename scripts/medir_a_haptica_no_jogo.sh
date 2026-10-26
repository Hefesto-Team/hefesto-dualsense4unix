#!/usr/bin/env bash
set -uo pipefail
export LC_ALL=C

ESPERA="${1:-180}"
ALVO_PADRAO="PRAGMATA"
ALVO="${HEFESTO_ALVO:-$ALVO_PADRAO}"

echo "── à espera de «$ALVO» (até ${ESPERA}s) ─────────────────────────"
echo "   abra o jogo PELO ÍCONE, em modo produto. Não abro nada daqui."
echo

e_um_jogo() {
  local p="$1"
  [ "$p" = "$$" ] && return 1
  tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null | grep -q "^STEAM_COMPAT_DATA_PATH="
}

pid=""
for _ in $(seq 1 "$ESPERA"); do
  for cand in $(pgrep -f "$ALVO" 2>/dev/null); do
    if e_um_jogo "$cand"; then pid="$cand"; break; fi
  done
  [ -n "$pid" ] && break
  sleep 1
done

if [ -z "$pid" ]; then
  echo "NÃO ACHEI o processo de «$ALVO» em ${ESPERA}s."
  echo "Ausência é resposta: não afirmo nada sobre a háptica."
  exit 2
fi

echo "achei o jogo · pid=$pid"
echo

env_do_jogo=$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null)
if [ -z "$env_do_jogo" ]; then
  echo "NÃO CONSIGO LER o ambiente do pid $pid (permissão?)."
  echo "Ausência é resposta."
  exit 2
fi

falhas=0
diz() { printf '  %-52s %s\n' "$1" "$2"; }

echo "── 1. as duas opções do Proton, no ambiente DO JOGO ─────────────"
for v in PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE PROTON_ENABLE_MHWILDS_USB_AUDIO; do
  val=$(printf '%s\n' "$env_do_jogo" | grep "^$v=" | cut -d= -f2-)
  if [ "$val" = "1" ]; then diz "$v" "= 1   OK"
  else diz "$v" "= ${val:-<ausente>}   FALHA"; falhas=$((falhas+1)); fi
done

echo
echo "── 2. o marcador no registro do prefixo ─────────────────────────"
prefixo=$(printf '%s\n' "$env_do_jogo" | grep "^STEAM_COMPAT_DATA_PATH=" | cut -d= -f2-)
reg="$prefixo/pfx/system.reg"
if [ -z "$prefixo" ]; then
  diz "STEAM_COMPAT_DATA_PATH" "<ausente>   FALHA"; falhas=$((falhas+1))
elif [ ! -r "$reg" ]; then
  diz "system.reg" "ilegível em $prefixo   FALHA"; falhas=$((falhas+1))
else
  n=$(grep -c "HEFESTOKS" "$reg" 2>/dev/null || true)
  if [ "${n:-0}" -gt 0 ]; then diz "HEFESTOKS no system.reg" "$n bloco(s)   OK"
  else diz "HEFESTOKS no system.reg" "0 blocos   FALHA"; falhas=$((falhas+1)); fi
fi

echo
echo "── 3. o sink do controle abriu em 4 canais ──────────────────────"
espec=$(pactl --format=json list sinks 2>/dev/null | python3 -c '
import json, sys
try:
    sinks = json.load(sys.stdin)
except ValueError:
    sys.exit(0)
for sink in sinks:
    if "hefesto_som" in (sink.get("name") or ""):
        print("Sample Specification: %s" % sink.get("sample_specification", ""))
' | head -4)
if [ -z "$espec" ]; then
  diz "sink do controle" "<nenhum hefesto_som na lista>   FALHA"; falhas=$((falhas+1))
else
  printf '%s\n' "$espec" | sed 's/^/     /'
  if printf '%s\n' "$espec" | grep -q "4ch"; then diz "algum sink em 4 canais" "OK"
  else diz "algum sink em 4 canais" "nenhum   FALHA"; falhas=$((falhas+1)); fi
fi

echo
echo "════════════════════════════════════════════════════════════════"
if [ "$falhas" -eq 0 ]; then
  echo "A CORRENTE ESTÁ FECHADA — os três sinais automáticos batem."
  echo
  echo "FALTA O QUARTO, e ele é dela: O JOGO VIBRA?"
  echo "Nenhum destes três prova que a vibração CHEGOU à mão."
else
  echo "$falhas sinal(is) fora do lugar — a corrente está aberta."
  echo "A vibração não deve chegar; se chegar, é por outro caminho e"
  echo "o laudo desta casa sobre o caminho KS está errado."
fi
exit 0
