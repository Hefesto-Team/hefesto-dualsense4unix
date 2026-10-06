#!/usr/bin/env bash
# ci-local.sh — o CI do GitHub, rodado em casa pelo PRÓPRIO YAML.
#
# O `act` (nektos/act) lê `.github/workflows/*.yml` e roda cada job num container
# do runner. Aqui NÃO há uma função por job: o que o YAML manda, roda; o que o
# YAML muda, muda aqui junto, sem ninguém rever nada. O que esta casa decide
# mora em `scripts/ci-local/jobs.txt`, e uma régua
# (`tests/unit/test_o_ci_de_casa_e_o_do_github.py`) exige que TODO job dos
# workflows apareça lá, ou como `ROLA` (roda no `act`) ou como
# `FORA-DE-CASA|job|motivo` (o motivo é medida, não suposição).
#
# USO:
#     bash scripts/ci-local.sh --rapido          # os jobs de `rapido` (o que o fecho de toda leva roda)
#     bash scripts/ci-local.sh --completo        # todos os que rodam em casa (antes de release e da janela)
#     bash scripts/ci-local.sh --job NOME[,NOME] # só estes, para triar (o passo `PULA-NO-RAPIDO` não vale)
#     bash scripts/ci-local.sh --listar          # o que roda, o que fica fora e por quê
#     bash scripts/ci-local.sh --conferir        # diz o que rodaria e sai 1 se rodaria alguma coisa
#
# O log de cada job vai para `$CASA/ci-local/<data>/<job>.log`; o resumo é UMA
# linha (a última) e o detalhe mora nos logs. E NÃO RODADO NÃO É VERDE: job que
# devia rodar e não rodou (sem o `act`, sem o docker, sem a imagem) sai rc=2 e
# aparece no resumo, nunca como verde.
#
# O QUE O `act` NÃO É: o runner do GitHub. A imagem é a `catthehacker/ubuntu:act-24.04` mais o que
# o runner traz e ela não (`scripts/ci-local/Dockerfile`); o `ubuntu-latest` passa a ser o Ubuntu 26
# em 19/10/2026, e o 24.04 é o de hoje.
# O que ele não alcança (macOS, privilégio de kernel, publicar) é `FORA-DE-CASA`.
#
# O `act` roda a ÁRVORE DE TRABALHO (o que o GitHub vê é o commit): árvore suja
# aparece no resumo, e o verde que vale é o da árvore limpa, depois do commit.
#
# rc: 0 tudo verde · 1 algum vermelho (ou, no --conferir, algo a rodar) · 2 não rodou
# (sem act, sem docker, argumento ruim).
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASA="${HEFESTO_CASA:-$HOME/.local/state/hefesto-casa}"
JOBS_TXT="$RAIZ/scripts/ci-local/jobs.txt"
BASE="catthehacker/ubuntu:act-24.04"
IMAGEM="${CI_LOCAL_IMAGEM:-hefesto-ci-local:$(sha256sum "$RAIZ/scripts/ci-local/Dockerfile" 2>/dev/null | cut -c1-10)}"
PARALELO="${CI_LOCAL_PARALELO:-2}"
DATA="$(date +%Y-%m-%d_%H%M)"
SAIDA="${CI_LOCAL_SAIDA:-$CASA/ci-local/$DATA}"

modo=""; alvo=""; conferir=0; listar=0
while [ $# -gt 0 ]; do
  case "$1" in
    --rapido) modo=rapido ;;
    --completo) modo=completo ;;
    --job) shift; alvo="${1:-}"; modo=job ;;
    --listar) listar=1 ;;
    --conferir) conferir=1 ;;
    -h|--ajuda) sed -n '2,29p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "ci-local: argumento desconhecido: $1" >&2; exit 2 ;;
  esac
  shift
done
[ -s "$JOBS_TXT" ] || { echo "ci-local: não há $JOBS_TXT" >&2; exit 2; }

# O act: o do state da casa (onde o baixamos, com o sha256 conferido) ou o do PATH.
ACT=""
for c in "$CASA/bin/act" "$(command -v act 2>/dev/null || true)"; do
  [ -n "$c" ] && [ -x "$c" ] && { ACT="$c"; break; }
done

# --- a tabela ---------------------------------------------------------------------
# ROLA|job|rapido|completo        roda no act; `rapido` entra nos dois modos
# PULA-NO-RAPIDO|job|passo        no --rapido o passo de nome exato sai da cópia do YAML
# FORA-DE-CASA|job|motivo         não roda em casa, com o motivo medido
campo() { awk -F'|' -v t="$1" -v j="$2" -v n="$3" '$1==t && $2==j {print $n}' "$JOBS_TXT"; }
linhas() { grep -vE '^\s*(#|$)' "$JOBS_TXT"; }

arquivo_do_job() { # o workflow que declara o job (id exato, sob `jobs:`)
  local f
  for f in "$RAIZ"/.github/workflows/*.yml; do
    if awk -v j="$1" '/^jobs:/{d=1;next} d && /^[^ #]/{d=0} d && $0 ~ "^  " j ":[[:space:]]*$" {ok=1} END{exit !ok}' "$f"; then
      echo "$f"; return 0
    fi
  done
  return 1
}

jobs_do_modo() { # os jobs ROLA do modo
  case "$modo" in
    rapido) linhas | awk -F'|' '$1=="ROLA" && $3=="rapido" {print $2}' ;;
    completo) linhas | awk -F'|' '$1=="ROLA" {print $2}' ;;
    job) echo "$alvo" | tr ',' '\n' ;;
  esac
}

fora_de_casa() { linhas | awk -F'|' '$1=="FORA-DE-CASA" {print $2}'; }

if [ "$listar" = 1 ]; then
  echo "roda no act:"
  linhas | awk -F'|' '$1=="ROLA" {printf "  %-24s %s\n", $2, $3}'
  echo "fora de casa:"
  linhas | awk -F'|' '$1=="FORA-DE-CASA" {printf "  %-24s %s\n", $2, $3}'
  exit 0
fi
[ -n "$modo" ] || { echo "ci-local: diga --rapido, --completo ou --job NOME (--ajuda)" >&2; exit 2; }
[ "$modo" != job ] || [ -n "$alvo" ] || { echo "ci-local: --job pede o nome" >&2; exit 2; }

mapfile -t JOBS < <(jobs_do_modo)
if [ "$conferir" = 1 ]; then
  echo "ci-local --conferir ($modo): rodaria ${#JOBS[@]} job(s): ${JOBS[*]}"
  [ "${#JOBS[@]}" -gt 0 ] && exit 1
  exit 0
fi

# --- o que tem de existir ------------------------------------------------------------
[ -n "$ACT" ] || { echo "ci-local: não há act (esperado em $CASA/bin/act ou no PATH); nada rodou, e nada rodado não é verde" >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo "ci-local: o docker não responde; nada rodou, e nada rodado não é verde" >&2; exit 2; }
if ! docker image inspect "$IMAGEM" >/dev/null 2>&1; then
  echo "ci-local: montando a imagem $IMAGEM sobre $BASE (uma vez só; a base baixa uns 570 MB)" >&2
  docker build -q -t "$IMAGEM" -f "$RAIZ/scripts/ci-local/Dockerfile" "$RAIZ/scripts/ci-local" >/dev/null 2>&1 \
    || { echo "ci-local: a imagem $IMAGEM não montou; nada rodou" >&2; exit 2; }
fi

mkdir -p "$SAIDA" "$CASA/ci-local/artefatos"
TMP="$(mktemp -d /tmp/cil.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

# O `.git` desta árvore é um ponteiro (worktree) para o diretório comum: dentro do
# container ele tem de existir no MESMO caminho, ou o `fetch-depth: 0` e os portões da
# história não acham o repositório. Só leitura; o `safe.directory` evita a recusa por dono.
GITCOMUM="$(cd "$RAIZ" && git rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
OPCOES_DOCKER=()
[ -n "$GITCOMUM" ] && [ -d "$GITCOMUM" ] && OPCOES_DOCKER=(--container-options "-v $GITCOMUM:$GITCOMUM:ro")

# O YAML a rodar: o próprio, ou (no --rapido) uma cópia sem os passos declarados
# `PULA-NO-RAPIDO` — a suíte inteira do lint-test tem a sua casa em `rodar-a-suite.sh`.
yaml_de() { # job -> caminho do YAML (o original, ou a cópia filtrada)
  local job="$1" f passos p
  f="$(arquivo_do_job "$job")" || return 1
  passos="$(campo PULA-NO-RAPIDO "$job" 3)"
  if [ "$modo" != rapido ] || [ -z "$passos" ]; then echo "$f"; return 0; fi
  local copia="$TMP/$job.yml"
  cp "$f" "$copia"
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    awk -v job="$job" -v passo="$p" '
      /^jobs:/ {emjobs=1}
      emjobs && /^  [A-Za-z0-9_-]+:[[:space:]]*$/ {atual=$1; sub(/:$/, "", atual)}
      pula && (/^      - / || /^  [A-Za-z0-9_-]+:/ || /^[^ #]/) {pula=0}
      atual==job && $0 == "      - name: " passo {pula=1}
      !pula {print}' "$copia" > "$copia.n" && mv "$copia.n" "$copia"
  done <<< "$passos"
  echo "$copia"
}

SUJA=""
[ -n "$(cd "$RAIZ" && git status --porcelain 2>/dev/null | head -1)" ] && SUJA=" (árvore suja: o act roda o que está no disco)"

rodar_job() { # job
  local job="$1" yml log rc
  log="$SAIDA/$job.log"
  yml="$(yaml_de "$job")" || { echo "ci-local: o job '$job' não está em workflow nenhum" > "$log"; echo 2 > "$SAIDA/$job.rc"; return 2; }
  (
    cd "$RAIZ" || exit 2
    "$ACT" push -W "$yml" -j "$job" \
      -P "ubuntu-latest=$IMAGEM" -P "ubuntu-24.04=$IMAGEM" \
      --pull=false --container-architecture linux/amd64 \
      --artifact-server-path "$CASA/ci-local/artefatos" \
      --concurrent-jobs "$PARALELO" \
      --env GIT_CONFIG_COUNT=1 --env GIT_CONFIG_KEY_0=safe.directory --env 'GIT_CONFIG_VALUE_0=*' \
      "${OPCOES_DOCKER[@]}" >"$log" 2>&1
  )
  rc=$?
  echo "$rc" > "$SAIDA/$job.rc"
  return "$rc"
}

VERDE=(); VERMELHO=(); NAO_RODOU=()
for j in "${JOBS[@]}"; do
  [ -n "$j" ] || continue
  rodar_job "$j"; rc=$?
  if [ "$rc" = 0 ]; then VERDE+=("$j"); echo "ci-local: $j verde" >&2
  elif [ "$rc" = 2 ]; then NAO_RODOU+=("$j"); echo "ci-local: $j NÃO RODOU (log $SAIDA/$j.log)" >&2
  else VERMELHO+=("$j"); echo "ci-local: $j VERMELHO rc=$rc (log $SAIDA/$j.log)" >&2; fi
done

FORA=$(fora_de_casa | wc -l)
RES="ci-local --$modo: ${#VERDE[@]} verde(s), ${#VERMELHO[@]} vermelho(s)"
[ "${#VERMELHO[@]}" -gt 0 ] && RES="$RES [${VERMELHO[*]}]"
RES="$RES, ${#NAO_RODOU[@]} não rodado(s)"
[ "${#NAO_RODOU[@]}" -gt 0 ] && RES="$RES [${NAO_RODOU[*]}]"
RES="$RES; $FORA fora de casa declarado(s); logs em $SAIDA$SUJA"
echo "$RES"
[ "${#VERMELHO[@]}" -gt 0 ] && exit 1
[ "${#NAO_RODOU[@]}" -gt 0 ] && exit 2
exit 0
