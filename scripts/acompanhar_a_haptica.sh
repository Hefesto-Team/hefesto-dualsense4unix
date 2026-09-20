#!/usr/bin/env bash
# Acompanha os três sinais da háptica ENQUANTO o jogo roda, em vez de medir um
# instante. Nasceu em 20/09/2026 porque o irmão `medir_a_haptica_no_jogo.sh`
# mediu no segundo em que o jogo abriu — antes de o sink de 4 canais subir — e
# reprovou o que ainda não tinha acontecido.
#
# E ele olha TODOS os processos do jogo, não o primeiro: sob Proton há o
# lançador, o reaper e o .exe, e as opções do Proton só estão em alguns.
#
# Só lê. Não abre jogo, não abre Steam, não escreve nada.
#
#   bash scripts/acompanhar_a_haptica.sh [segundos] [passo]
set -uo pipefail
export LC_ALL=C

TOTAL="${1:-600}"
PASSO="${2:-10}"
ALVO="${HEFESTO_ALVO:-PRAGMATA}"

# Um candidato só vale se o ambiente dele disser que é um jogo sob Proton.
# `pgrep -f` sozinho casa o próprio shell — medido em 20/09.
jogos() {
  local p
  for p in $(pgrep -f "$ALVO" 2>/dev/null); do
    [ "$p" = "$$" ] && continue
    tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null \
      | grep -q "^STEAM_COMPAT_DATA_PATH=" && echo "$p"
  done
}

tem_opcoes() {
  local e; e=$(tr '\0' '\n' < "/proc/$1/environ" 2>/dev/null)
  printf '%s\n' "$e" | grep -q "^PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE=1" &&
  printf '%s\n' "$e" | grep -q "^PROTON_ENABLE_MHWILDS_USB_AUDIO=1"
}

canais4() { pactl list sinks 2>/dev/null | grep -A 14 "hefesto_som" | grep -q "4ch"; }

echo "── acompanhando «$ALVO» · ${TOTAL}s, amostra a cada ${PASSO}s ──"
echo

anterior=""
melhor_opcoes=0
viu4ch=0
voltas=$((TOTAL / PASSO))

for _ in $(seq 1 "$voltas"); do
  lista=$(jogos)
  n=$(printf '%s\n' "$lista" | grep -c . || true)

  com_opcoes=0
  for p in $lista; do tem_opcoes "$p" && com_opcoes=$((com_opcoes+1)); done
  [ "$com_opcoes" -gt "$melhor_opcoes" ] && melhor_opcoes=$com_opcoes

  if canais4; then c4="SIM"; viu4ch=1; else c4="não"; fi

  agora="proc=$n  com-as-duas-opcoes=$com_opcoes  sink-4ch=$c4"
  if [ "$agora" != "$anterior" ]; then
    echo "$(date +%H:%M:%S)  $agora"
    anterior="$agora"
  fi
  sleep "$PASSO"
done

echo
echo "════════════════════════════════════════════════════════════════"
echo "  processos do jogo com as DUAS opções, no pico: $melhor_opcoes"
echo "  sink em 4 canais visto alguma vez:             $([ $viu4ch -eq 1 ] && echo SIM || echo NAO)"
echo
if [ "$melhor_opcoes" -eq 0 ]; then
  echo "AS OPÇÕES DO PROTON NÃO CHEGARAM A PROCESSO NENHUM do jogo."
  echo "É o elo que o wrapper deveria fechar — ver launch_env.py:1634."
elif [ "$viu4ch" -eq 0 ]; then
  echo "As opções chegaram, mas o sink NUNCA abriu em 4 canais."
  echo "O jogo não pediu háptica, ou o endpoint KS não foi aceito."
else
  echo "A CORRENTE FECHOU. Falta o quarto sinal, e ele é dela: VIBROU?"
fi
