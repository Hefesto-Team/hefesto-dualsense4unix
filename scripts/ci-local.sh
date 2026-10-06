#!/usr/bin/env bash
# ci-local.sh — o CI do GitHub, rodado em casa pelo PRÓPRIO YAML.
#
# O `act` (nektos/act) lê `.github/workflows/*.yml` e roda cada job num container do
# runner. Aqui NÃO há uma função por job: o que o YAML manda, roda; o que o YAML muda,
# muda aqui junto, sem ninguém rever nada. O que esta casa decide mora em
# `scripts/ci-local/jobs.txt`, e a régua `tests/unit/test_o_ci_de_casa_e_o_do_github.py`
# (e este script, a cada corrida) exige que TODO job dos workflows apareça lá, ou como
# `ROLA` (roda no `act`) ou como `FORA-DE-CASA|job|motivo` (o motivo é medida).
#
# USO:
#     bash scripts/ci-local.sh --rapido          # o que o fecho de toda leva roda
#     bash scripts/ci-local.sh --completo        # tudo o que roda em casa (antes de release e da janela)
#     bash scripts/ci-local.sh --job NOME[,NOME] # só estes, para triar (o `PULA-NO-RAPIDO` não vale)
#     bash scripts/ci-local.sh --listar          # o que roda, o que fica fora e por quê
#     bash scripts/ci-local.sh --conferir        # diz o que rodaria e sai 1 se rodaria alguma coisa
#   para triar, com --job:  --sem-passo 'job|nome do passo' (repetível) tira um passo da cópia do YAML
#
# O QUE RODA: a ÁRVORE DO ÍNDICE (`git checkout-index`, só arquivo versionado), exportada
# para uma pasta de /tmp. É o que o runner do GitHub vê depois do `actions/checkout`: arquivo
# ignorado e arquivo novo sem `git add` NÃO existem lá, e o verde de casa não pode contar
# com eles. Árvore com o índice diferente do HEAD aparece no resumo («índice com mudança
# não commitada»): o verde que vale é o do commit.
#
# O log de cada job vai para `$CASA/ci-local/<data>/<job>.log`; o resumo é UMA linha (a
# última) e o detalhe mora nos logs. NÃO RODADO NÃO É VERDE: job que devia rodar e não
# rodou (sem o `act`, sem o docker, sem a imagem, ou a REDE caída no meio) sai rc=2 e
# aparece no resumo, nunca como verde nem como vermelho.
#
# O QUE O `act` NÃO É: o runner do GitHub. A imagem é a `catthehacker/ubuntu:act-24.04` mais o
# que o runner traz e ela não (`scripts/ci-local/Dockerfile`); o `ubuntu-latest` passa a ser o
# Ubuntu 26 em 19/10/2026, e o 24.04 é o de hoje. O que o `act` não alcança (privilégio de
# kernel, FUSE, publicar, perguntar ao servidor) é `FORA-DE-CASA`, com a medida.
#
# O servidor de artefato e o de cache do `act` ficam em 127.0.0.1 (o padrão dele é o IP da
# rede local).
#
# rc: 0 tudo verde · 1 algum vermelho (ou, no --conferir, algo a rodar) · 2 não rodou
# (sem act, sem docker, rede, tabela fora do YAML, argumento ruim).
set -uo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASA="${HEFESTO_CASA:-$HOME/.local/state/hefesto-casa}"
JOBS_TXT="$RAIZ/scripts/ci-local/jobs.txt"
DOCKERFILE="$RAIZ/scripts/ci-local/Dockerfile"
BASE="catthehacker/ubuntu:act-24.04"
BASE_22="catthehacker/ubuntu:act-22.04"
EM_PARALELO="${CI_LOCAL_JOBS:-2}"        # quantos jobs do act ao mesmo tempo
PERNAS="${CI_LOCAL_PERNAS:-3}"           # quantas pernas de matriz por job
DATA="$(date +%Y-%m-%d_%H%M)"
SAIDA="${CI_LOCAL_SAIDA:-$CASA/ci-local/$DATA}"
# O texto que o log tem quando a REDE caiu: o job reprovou, mas não por defeito dele.
REDE_CAIDA='Temporary failure resolving|Could not resolve host|Name or service not known|EAI_AGAIN|Network is unreachable|Temporary failure in name resolution'

modo=""; alvo=""; conferir=0; listar=0; SEM_PASSO=()
while [ $# -gt 0 ]; do
  case "$1" in
    --rapido) modo=rapido ;;
    --completo) modo=completo ;;
    --job) shift; alvo="${1:-}"; modo=job ;;
    --sem-passo) shift; SEM_PASSO+=("${1:-}") ;;
    --listar) listar=1 ;;
    --conferir) conferir=1 ;;
    -h|--ajuda) sed -n '2,36p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "ci-local: argumento desconhecido: $1" >&2; exit 2 ;;
  esac
  shift
done

# --- a tabela ---------------------------------------------------------------------
# ROLA|job|rapido|imagem       roda no act; `rapido` entra nos dois modos, `completo` só no completo;
#                              `imagem` (opcional) = ubuntu-22.04 manda baixar a imagem do runner 22.04
# PULA-NO-RAPIDO|job|passo     no --rapido o passo de nome exato sai da cópia do YAML
# SEM-NEEDS|job|motivo         o `needs:` do job sai da cópia (o act o seguiria e rodaria o job de que ele depende)
# FORA-DE-CASA|job|motivo      não roda em casa, com o motivo medido
linhas() {
  if [ -n "${TABELA:-}" ]; then printf '%s\n' "$TABELA"; else cat "$JOBS_TXT" 2>/dev/null; fi | grep -vE '^\s*(#|$)'
}
campo() { linhas | awk -F'|' -v t="$1" -v j="$2" -v n="$3" '$1==t && $2==j {print $n}'; }

[ -n "$(linhas)" ] || { echo "ci-local: não há tabela de jobs ($JOBS_TXT)" >&2; exit 2; }

jobs_do_yaml() { # "arquivo job" de cada job de cada workflow (id exato, sob `jobs:`)
  local f
  for f in "$RAIZ"/.github/workflows/*.yml; do
    [ -f "$f" ] || continue
    awk -v f="$(basename "$f")" '
      /^jobs:/ {d=1; next}
      d && /^[^ #]/ {d=0}
      d && /^  [A-Za-z0-9_-]+:[[:space:]]*$/ {j=$1; sub(/:$/, "", j); print f, j}' "$f"
  done
}

arquivo_do_job() { jobs_do_yaml | awk -v j="$1" '$2==j {print $1; exit}'; }

# A tabela e os workflows têm de dizer a mesma coisa: job novo sem decisão, job que sumiu
# da tabela, passo `PULA-NO-RAPIDO` que o YAML já não tem (o `--rapido` rodaria a suíte
# inteira sem ninguém notar) e `FORA-DE-CASA` sem motivo são recusados, rc=2.
conferir_tabela() {
  local erros=0 j dup t p
  while read -r _ j; do
    [ -n "$j" ] || continue
    t="$(linhas | awk -F'|' -v j="$j" '($1=="ROLA" || $1=="FORA-DE-CASA") && $2==j' | wc -l)"
    [ "$t" = 1 ] || { echo "ci-local: o job '$j' está $t vez(es) na tabela (tem de estar uma: ROLA ou FORA-DE-CASA)" >&2; erros=1; }
  done < <(jobs_do_yaml)
  dup="$(jobs_do_yaml | awk '{print $2}' | sort | uniq -d | head -1)"
  [ -z "$dup" ] || { echo "ci-local: o job '$dup' existe em mais de um workflow; a tabela o nomeia só pelo id" >&2; erros=1; }
  while IFS='|' read -r tipo j resto _; do
    [ -n "$j" ] || continue
    jobs_do_yaml | awk -v j="$j" '$2==j {ok=1} END{exit !ok}' \
      || { echo "ci-local: a tabela cita o job '$j', que nenhum workflow tem" >&2; erros=1; }
    case "$tipo" in
      ROLA) case "$resto" in rapido|completo) ;; *) echo "ci-local: ROLA|$j|$resto: o modo é rapido ou completo" >&2; erros=1 ;; esac ;;
      FORA-DE-CASA) [ -n "$resto" ] || { echo "ci-local: FORA-DE-CASA|$j sem motivo" >&2; erros=1; } ;;
      PULA-NO-RAPIDO) passo_existe "$j" "$resto" || { echo "ci-local: PULA-NO-RAPIDO|$j|$resto: o job não tem esse passo" >&2; erros=1; } ;;
      SEM-NEEDS) [ -n "$resto" ] || { echo "ci-local: SEM-NEEDS|$j sem motivo" >&2; erros=1; } ;;
      *) echo "ci-local: linha de tipo desconhecido: $tipo|$j" >&2; erros=1 ;;
    esac
  done < <(linhas)
  for p in "${SEM_PASSO[@]:-}"; do
    [ -n "$p" ] || continue
    passo_existe "${p%%|*}" "${p#*|}" || { echo "ci-local: --sem-passo '$p': o job não tem esse passo" >&2; erros=1; }
  done
  return "$erros"
}

passo_existe() { # job, nome do passo (exato)
  local f; f="$(arquivo_do_job "$1")"; [ -n "$f" ] || return 1
  awk -v job="$1" -v passo="$2" '
    /^jobs:/ {d=1; next}
    d && /^  [A-Za-z0-9_-]+:[[:space:]]*$/ {a=$1; sub(/:$/, "", a)}
    d && a==job && $0 == "      - name: " passo {ok=1}
    END{exit !ok}' "$RAIZ/.github/workflows/$f"
}

jobs_do_modo() { # os jobs ROLA do modo
  case "$modo" in
    rapido) linhas | awk -F'|' '$1=="ROLA" && $3=="rapido" {print $2}' ;;
    completo) linhas | awk -F'|' '$1=="ROLA" {print $2}' ;;
    job) echo "$alvo" | tr ',' '\n' ;;
  esac
}

if [ "$listar" = 1 ]; then
  conferir_tabela || exit 2
  echo "roda no act:"
  linhas | awk -F'|' '$1=="ROLA" {printf "  %-22s %s\n", $2, $3}'
  echo "fora de casa:"
  linhas | awk -F'|' '$1=="FORA-DE-CASA" {printf "  %-22s %s\n", $2, $3}'
  exit 0
fi
[ -n "$modo" ] || { echo "ci-local: diga --rapido, --completo ou --job NOME (--ajuda)" >&2; exit 2; }
[ "$modo" != job ] || [ -n "$alvo" ] || { echo "ci-local: --job pede o nome" >&2; exit 2; }
conferir_tabela || exit 2

mapfile -t JOBS < <(jobs_do_modo)
if [ "$modo" = job ]; then # nome que a tabela não tem, ou que ela deixa fora de casa, não roda calado
  for j in "${JOBS[@]}"; do
    [ -n "$(campo ROLA "$j" 2)" ] || { echo "ci-local: o job '$j' não roda em casa (ou não existe): $(campo FORA-DE-CASA "$j" 3)" >&2; exit 2; }
  done
fi
if [ "$conferir" = 1 ]; then
  echo "ci-local --conferir ($modo): rodaria ${#JOBS[@]} job(s): ${JOBS[*]}"
  [ "${#JOBS[@]}" -gt 0 ] && exit 1
  exit 0
fi

# --- o que tem de existir ------------------------------------------------------------
# O act: o do state da casa (onde o baixamos, com o sha256 da release conferido) ou o do PATH.
ACT=""
for c in "$CASA/bin/act" "$(command -v act 2>/dev/null || true)"; do
  [ -n "$c" ] && [ -x "$c" ] && { ACT="$c"; break; }
done
[ -n "$ACT" ] || { echo "ci-local: não há act (esperado em $CASA/bin/act ou no PATH); nada rodou, e nada rodado não é verde" >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo "ci-local: o docker não responde; nada rodou, e nada rodado não é verde" >&2; exit 2; }

IMAGEM="${CI_LOCAL_IMAGEM:-}"
if [ -z "$IMAGEM" ]; then
  if [ -f "$DOCKERFILE" ]; then
    IMAGEM="hefesto-ci-local:$(sha256sum "$DOCKERFILE" | cut -c1-10)"
    if ! docker image inspect "$IMAGEM" >/dev/null 2>&1; then
      echo "ci-local: montando a imagem $IMAGEM sobre $BASE (uma vez só; a base baixa uns 570 MB)" >&2
      docker build -q -t "$IMAGEM" -f "$DOCKERFILE" "$RAIZ/scripts/ci-local" >/dev/null 2>&1 \
        || { echo "ci-local: a imagem $IMAGEM não montou (rede?); nada rodou" >&2; exit 2; }
    fi
  else
    IMAGEM="$BASE"
    docker image inspect "$IMAGEM" >/dev/null 2>&1 || docker pull -q "$IMAGEM" >/dev/null 2>&1 \
      || { echo "ci-local: a imagem $IMAGEM não baixou (rede?); nada rodou" >&2; exit 2; }
  fi
fi
IMAGEM_22=""
for j in "${JOBS[@]}"; do
  [ "$(campo ROLA "$j" 4)" = ubuntu-22.04 ] || continue
  docker image inspect "$BASE_22" >/dev/null 2>&1 || docker pull -q "$BASE_22" >/dev/null 2>&1 \
    || { echo "ci-local: a imagem $BASE_22 (do job $j) não baixou (rede?); nada rodou" >&2; exit 2; }
  IMAGEM_22="$BASE_22"
done

mkdir -p "$SAIDA" "$CASA/ci-local/artefatos"
TMP="$(mktemp -d /tmp/cil.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

# --- a árvore: o índice, exportado ------------------------------------------------------
# O `.git` dela é um ponteiro; o diretório do git tem de existir no MESMO caminho dentro do
# container (só leitura), ou o `fetch-depth: 0` e os portões da história não acham o repositório.
ARV="$TMP/arvore"
mkdir -p "$ARV"
git -C "$RAIZ" checkout-index -a -f --prefix="$ARV/" 2>/dev/null \
  || { echo "ci-local: não exportou o índice de $RAIZ; nada rodou" >&2; exit 2; }
GITDIR="$(git -C "$RAIZ" rev-parse --absolute-git-dir 2>/dev/null || true)"
GITCOMUM="$(git -C "$RAIZ" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || true)"
OPCOES_DOCKER=()
if [ -n "$GITDIR" ] && [ -d "$GITDIR" ]; then
  printf 'gitdir: %s\n' "$GITDIR" > "$ARV/.git"
  OPCOES_DOCKER+=("-v $GITDIR:$GITDIR:ro")
  if [ -n "$GITCOMUM" ] && [ -d "$GITCOMUM" ] && [ "$GITCOMUM" != "$GITDIR" ]; then OPCOES_DOCKER+=("-v $GITCOMUM:$GITCOMUM:ro"); fi
fi
OPCOES=()
[ "${#OPCOES_DOCKER[@]}" -gt 0 ] && OPCOES=(--container-options "${OPCOES_DOCKER[*]}")

# O YAML a rodar: o próprio, ou uma cópia sem o que a tabela manda tirar: os passos
# `PULA-NO-RAPIDO` (só no --rapido: a suíte inteira tem a casa dela em `rodar-a-suite.sh`),
# os passos de `--sem-passo` e o `needs:` dos jobs `SEM-NEEDS`.
tirar_passo() { # arquivo job passo
  awk -v job="$2" -v passo="$3" '
    /^jobs:/ {emjobs=1}
    emjobs && /^  [A-Za-z0-9_-]+:[[:space:]]*$/ {atual=$1; sub(/:$/, "", atual)}
    pula && (/^      - / || /^  [A-Za-z0-9_-]+:/ || /^[^ #]/) {pula=0}
    atual==job && $0 == "      - name: " passo {pula=1}
    !pula {print}' "$1" > "$1.n" && mv "$1.n" "$1"
}
tirar_needs() { # arquivo job
  awk -v job="$2" '
    /^jobs:/ {emjobs=1}
    emjobs && /^  [A-Za-z0-9_-]+:[[:space:]]*$/ {atual=$1; sub(/:$/, "", atual)}
    atual==job && /^    needs:/ {next}
    {print}' "$1" > "$1.n" && mv "$1.n" "$1"
}
yaml_de() { # job -> caminho do YAML (o original, ou a cópia filtrada)
  local job="$1" f copia="$TMP/$1.yml" mudou=0 p
  f="$(arquivo_do_job "$job")"; [ -n "$f" ] || return 1
  f="$ARV/.github/workflows/$f"
  cp "$f" "$copia"
  if [ "$modo" = rapido ]; then
    while IFS= read -r p; do [ -n "$p" ] && { tirar_passo "$copia" "$job" "$p"; mudou=1; }; done < <(campo PULA-NO-RAPIDO "$job" 3)
  fi
  for p in "${SEM_PASSO[@]:-}"; do
    [ -n "$p" ] && [ "${p%%|*}" = "$job" ] && { tirar_passo "$copia" "$job" "${p#*|}"; mudou=1; }
  done
  if [ -n "$(campo SEM-NEEDS "$job" 2)" ]; then tirar_needs "$copia" "$job"; mudou=1; fi
  if [ "$mudou" = 1 ]; then echo "$copia"; else echo "$f"; fi
}

SUJA=""
if ! git -C "$RAIZ" diff --cached --quiet HEAD -- 2>/dev/null; then SUJA=" (índice com mudança não commitada)"; fi

rodar_job() { # job índice
  local job="$1" i="$2" yml log rc ini extras=() porta
  log="$SAIDA/$job.log"
  ini=$(date +%s)
  yml="$(yaml_de "$job")" || { echo "ci-local: o job '$job' não está em workflow nenhum" > "$log"; echo 2 > "$SAIDA/$job.rc"; return 2; }
  porta=$((30000 + ($$ % 3000) * 10 + i % 10))
  [ -n "$IMAGEM_22" ] && extras+=(-P "ubuntu-22.04=$IMAGEM_22")
  # shellcheck disable=SC2086
  (
    cd "$ARV" || exit 2
    "$ACT" push -W "$yml" -j "$job" \
      -P "ubuntu-latest=$IMAGEM" -P "ubuntu-24.04=$IMAGEM" "${extras[@]}" \
      --pull=false --rm --container-architecture linux/amd64 \
      --artifact-server-path "$CASA/ci-local/artefatos" \
      --artifact-server-addr 127.0.0.1 --artifact-server-port "$porta" \
      --cache-server-addr 127.0.0.1 \
      --concurrent-jobs "$PERNAS" \
      --env GIT_CONFIG_COUNT=1 --env GIT_CONFIG_KEY_0=safe.directory --env 'GIT_CONFIG_VALUE_0=*' \
      "${OPCOES[@]}" ${CI_LOCAL_ACT_EXTRA:-} >"$log" 2>&1
  )
  rc=$?
  # Reprovou porque a rede caiu: não é defeito do job, e não rodar não é verde.
  if [ "$rc" != 0 ] && [ "$rc" != 2 ] && grep -qE "$REDE_CAIDA" "$log"; then
    echo "ci-local: a rede caiu no meio deste job; ele não rodou de verdade (o log tem a linha)" >> "$log"
    echo rede > "$SAIDA/$job.motivo"; rc=2
  fi
  echo "$rc" > "$SAIDA/$job.rc"
  echo $(( $(date +%s) - ini )) > "$SAIDA/$job.seg"
  return "$rc"
}

INI=$(date +%s)
i=0
for j in "${JOBS[@]}"; do
  [ -n "$j" ] || continue
  while [ "$(jobs -rp | wc -l)" -ge "$EM_PARALELO" ]; do wait -n 2>/dev/null || true; done
  ( rodar_job "$j" "$i"; rc=$?
    if [ "$rc" = 0 ]; then echo "ci-local: $j verde ($(cat "$SAIDA/$j.seg")s)" >&2
    elif [ "$rc" = 2 ]; then echo "ci-local: $j NÃO RODOU$([ -f "$SAIDA/$j.motivo" ] && echo " (rede)") (log $SAIDA/$j.log)" >&2
    else echo "ci-local: $j VERMELHO rc=$rc (log $SAIDA/$j.log)" >&2; fi ) &
  i=$((i + 1))
done
wait

VERDE=(); VERMELHO=(); NAO_RODOU=()
for j in "${JOBS[@]}"; do
  [ -n "$j" ] || continue
  rc="$(cat "$SAIDA/$j.rc" 2>/dev/null || echo 2)"
  case "$rc" in 0) VERDE+=("$j") ;; 2) NAO_RODOU+=("$j") ;; *) VERMELHO+=("$j") ;; esac
done

FORA=$(linhas | awk -F'|' '$1=="FORA-DE-CASA"' | wc -l)
RES="ci-local --$modo: ${#VERDE[@]} verde(s), ${#VERMELHO[@]} vermelho(s)"
[ "${#VERMELHO[@]}" -gt 0 ] && RES="$RES [${VERMELHO[*]}]"
RES="$RES, ${#NAO_RODOU[@]} não rodado(s)"
[ "${#NAO_RODOU[@]}" -gt 0 ] && RES="$RES [${NAO_RODOU[*]}]"
RES="$RES; $FORA fora de casa declarado(s); $(( $(date +%s) - INI ))s; logs em $SAIDA$SUJA"
# O recibo: a corrida, para o fecho e para quem confere o `--completo` antes da janela.
mkdir -p "$CASA/ci-local"
printf '%s|%s|%s\n' "$(date +%Y-%m-%dT%H:%M)" "$(git -C "$RAIZ" rev-parse --short=12 HEAD 2>/dev/null || echo -)" "$RES" \
  > "$CASA/ci-local/ultimo-$modo.txt"
echo "$RES"
[ "${#VERMELHO[@]}" -gt 0 ] && exit 1
[ "${#NAO_RODOU[@]}" -gt 0 ] && exit 2
exit 0
