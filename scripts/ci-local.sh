#!/usr/bin/env bash
set -uo pipefail
_ajuda() {
  cat <<'AJUDA'
ci-local.sh — o CI do GitHub, rodado em casa pelo PRÓPRIO YAML.

USO:
    bash scripts/ci-local.sh --rapido          # o que o fecho de toda leva roda
    bash scripts/ci-local.sh --completo        # tudo o que roda em casa (antes de release e da janela)
    bash scripts/ci-local.sh --job NOME[,NOME] # só estes, para triar (o `PULA-NO-RAPIDO` não vale)
    bash scripts/ci-local.sh --listar          # o que roda, o que fica fora e por quê
    bash scripts/ci-local.sh --conferir        # diz o que rodaria e sai 1 se rodaria alguma coisa
  para triar, com --job:  --sem-passo 'job|nome do passo' (repetível) tira um passo da cópia do YAML;
                          --perna ubuntu-22.04 roda só essa perna da matriz de runners
AJUDA
}

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CASA="${HEFESTO_CASA:-$HOME/.local/state/hefesto-casa}"
JOBS_TXT="$RAIZ/scripts/ci-local/jobs.txt"
DOCKERFILE="$RAIZ/scripts/ci-local/Dockerfile"
BASE="catthehacker/ubuntu:act-26.04-dev"
BASE_24="catthehacker/ubuntu:act-24.04"
BASE_22="catthehacker/ubuntu:act-22.04"
EM_PARALELO="${CI_LOCAL_JOBS:-2}"
PERNAS="${CI_LOCAL_PERNAS:-3}"
CACHE_ACOES="${CI_LOCAL_CACHE_ACOES:-$HOME/.cache/act}"
DATA="$(date +%Y-%m-%d_%H%M)"
SAIDA="${CI_LOCAL_SAIDA:-$CASA/ci-local/$DATA}"
REDE_PASSO='\]\s+\|\s+(W: Failed to fetch .*(Temporary failure resolving|Could not resolve)|Temporary failure resolving .|fatal: unable to access .*Could not resolve host|curl: \([67]\) |.*Failed to establish a new connection: \[Errno -[23]\]|(Error: )?getaddrinfo (EAI_AGAIN|ENOTFOUND))'
REDE_ACT='^Error: .*(no such host|dial tcp|Temporary failure in name resolution)'
DOCKER_CAIDO='^(Error: |\[[^]]*\] +(failed to remove container|Error while stop job container)).*(context deadline exceeded|Cannot connect to the Docker daemon)'

modo=""; alvo=""; conferir=0; listar=0; SEM_PASSO=(); SO_PERNA=""
while [ $# -gt 0 ]; do
  case "$1" in
    --rapido) modo=rapido ;;
    --completo) modo=completo ;;
    --job) shift; alvo="${1:-}"; modo=job ;;
    --sem-passo) shift; SEM_PASSO+=("${1:-}") ;;
    --perna) shift; SO_PERNA="${1:-}" ;;
    --listar) listar=1 ;;
    --conferir) conferir=1 ;;
    -h|--ajuda) _ajuda; exit 0 ;;
    *) echo "ci-local: argumento desconhecido: $1" >&2; exit 2 ;;
  esac
  shift
done

_LINHAS="$(grep -vE '^\s*(#|$)' "$JOBS_TXT" 2>/dev/null)"
linhas() { [ -z "$_LINHAS" ] || printf '%s\n' "$_LINHAS"; }
campo() { linhas | awk -F'|' -v t="$1" -v j="$2" -v n="$3" '$1==t && $2==j {print $n}'; }

[ -n "$_LINHAS" ] || { echo "ci-local: não há tabela de jobs ($JOBS_TXT)" >&2; exit 2; }

_jobs_do_yaml_lidos() {
  local f
  for f in "$RAIZ"/.github/workflows/*.yml; do
    [ -f "$f" ] || continue
    awk -v f="$(basename "$f")" '
      /^jobs:/ {d=1; next}
      d && /^[^ #]/ {d=0}
      d && /^  [A-Za-z0-9_-]+:[[:space:]]*$/ {j=$1; sub(/:$/, "", j); print f, j}' "$f"
  done
}
_JOBS_YAML="$(_jobs_do_yaml_lidos)"
declare -A ARQUIVO_DO_JOB=()
while read -r _arq _job; do
  [ -n "$_job" ] && [ -z "${ARQUIVO_DO_JOB[$_job]:-}" ] && ARQUIVO_DO_JOB[$_job]="$_arq"
done <<< "$_JOBS_YAML"

jobs_do_yaml() { [ -z "$_JOBS_YAML" ] || printf '%s\n' "$_JOBS_YAML"; }

arquivo_do_job() { [ -z "${ARQUIVO_DO_JOB[$1]:-}" ] || printf '%s\n' "${ARQUIVO_DO_JOB[$1]}"; }

conferir_tabela() {
  local erros=0 j dup t p n
  declare -A na_tabela=()
  while read -r j n; do na_tabela[$j]="$n"; done < <(
    linhas | awk -F'|' '$1=="ROLA" || $1=="FORA-DE-CASA" {n[$2]++} END {for (j in n) print j, n[j]}')
  while read -r _ j; do
    [ -n "$j" ] || continue
    t="${na_tabela[$j]:-0}"
    [ "$t" = 1 ] || { echo "ci-local: o job '$j' está $t vez(es) na tabela (tem de estar uma: ROLA ou FORA-DE-CASA)" >&2; erros=1; }
  done < <(jobs_do_yaml)
  dup="$(jobs_do_yaml | awk '{print $2}' | sort | uniq -d | head -1)"
  [ -z "$dup" ] || { echo "ci-local: o job '$dup' existe em mais de um workflow; a tabela o nomeia só pelo id" >&2; erros=1; }
  while IFS='|' read -r tipo j resto _; do
    [ -n "$j" ] || continue
    [ "$tipo" = EM-TAG ] || [ -n "${ARQUIVO_DO_JOB[$j]:-}" ] \
      || { echo "ci-local: a tabela cita o job '$j', que nenhum workflow tem" >&2; erros=1; }
    case "$tipo" in
      ROLA) case "$resto" in rapido|completo) ;; *) echo "ci-local: ROLA|$j|$resto: o modo é rapido ou completo" >&2; erros=1 ;; esac ;;
      FORA-DE-CASA) [ -n "$resto" ] || { echo "ci-local: FORA-DE-CASA|$j sem motivo" >&2; erros=1; } ;;
      PULA-NO-RAPIDO) passo_existe "$j" "$resto" || { echo "ci-local: PULA-NO-RAPIDO|$j|$resto: o job não tem esse passo" >&2; erros=1; } ;;
      EM-TAG)
        [ -f "$RAIZ/.github/workflows/$j" ] || { echo "ci-local: EM-TAG|$j: o workflow não existe" >&2; erros=1; }
        [ -n "$resto" ] || { echo "ci-local: EM-TAG|$j sem motivo" >&2; erros=1; } ;;
      SEM-NEEDS)
        [ -n "$resto" ] || { echo "ci-local: SEM-NEEDS|$j sem a lista de dependências" >&2; erros=1; }
        [ -n "$(linhas | awk -F'|' -v j="$j" '$1=="SEM-NEEDS" && $2==j {print $4}')" ] || { echo "ci-local: SEM-NEEDS|$j sem motivo" >&2; erros=1; } ;;
      *) echo "ci-local: linha de tipo desconhecido: $tipo|$j" >&2; erros=1 ;;
    esac
  done < <(linhas)
  for p in "${SEM_PASSO[@]:-}"; do
    [ -n "$p" ] || continue
    passo_existe "${p%%|*}" "${p#*|}" || { echo "ci-local: --sem-passo '$p': o job não tem esse passo" >&2; erros=1; }
  done
  return "$erros"
}

passo_existe() {
  local f; f="$(arquivo_do_job "$1")"; [ -n "$f" ] || return 1
  awk -v job="$1" -v passo="$2" '
    /^jobs:/ {d=1; next}
    d && /^  [A-Za-z0-9_-]+:[[:space:]]*$/ {a=$1; sub(/:$/, "", a)}
    d && a==job && $0 == "      - name: " passo {ok=1}
    END{exit !ok}' "$RAIZ/.github/workflows/$f"
}

jobs_do_modo() {
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
  linhas | awk -F'|' '$1=="FORA-DE-CASA" {m = $3; for (i = 4; i <= NF; i++) m = m "|" $i; printf "  %-22s %s\n", $2, (length(m) > 110 ? substr(m, 1, 110) "…" : m)}'
  echo "(o motivo inteiro está em scripts/ci-local/jobs.txt)"
  exit 0
fi
[ -n "$modo" ] || { echo "ci-local: diga --rapido, --completo ou --job NOME (--ajuda)" >&2; exit 2; }
[ "$modo" != job ] || [ -n "$alvo" ] || { echo "ci-local: --job pede o nome" >&2; exit 2; }
conferir_tabela || exit 2

mapfile -t JOBS < <(jobs_do_modo)
if [ "$modo" = job ]; then
  for j in "${JOBS[@]}"; do
    [ -n "$(campo ROLA "$j" 2)" ] || { echo "ci-local: o job '$j' não roda em casa (ou não existe): $(campo FORA-DE-CASA "$j" 3)" >&2; exit 2; }
  done
fi
if [ "$conferir" = 1 ]; then
  echo "ci-local --conferir ($modo): rodaria ${#JOBS[@]} job(s): ${JOBS[*]}"
  [ "${#JOBS[@]}" -gt 0 ] && exit 1
  exit 0
fi

ACT=""
for c in "$CASA/bin/act" "$(command -v act 2>/dev/null || true)"; do
  [ -n "$c" ] && [ -x "$c" ] && { ACT="$c"; break; }
done
[ -n "$ACT" ] || { echo "ci-local: não há act (esperado em $CASA/bin/act ou no PATH); nada rodou, e nada rodado não é verde" >&2; exit 2; }
docker info >/dev/null 2>&1 || { echo "ci-local: o docker não responde; nada rodou, e nada rodado não é verde" >&2; exit 2; }

imagem_de() {
  local base="$1" nome
  if [ ! -f "$DOCKERFILE" ]; then
    docker image inspect "$base" >/dev/null 2>&1 || docker pull -q "$base" >/dev/null 2>&1 \
      || { echo "ci-local: a imagem $base não baixou (rede?); nada rodou" >&2; return 2; }
    echo "$base"
    return 0
  fi
  nome="hefesto-ci-local:$({ cat "$DOCKERFILE"; echo "$base"; } | sha256sum | cut -c1-10)"
  if ! docker image inspect "$nome" >/dev/null 2>&1; then
    echo "ci-local: montando a imagem $nome sobre $base (uma vez só; a base baixa uns 570 MB)" >&2
    docker build -q --build-arg "BASE=$base" -t "$nome" -f "$DOCKERFILE" "$RAIZ/scripts/ci-local" >/dev/null 2>&1 \
      || { echo "ci-local: a imagem $nome não montou (rede?); nada rodou" >&2; return 2; }
  fi
  echo "$nome"
}

IMAGEM="${CI_LOCAL_IMAGEM:-}"
[ -n "$IMAGEM" ] || IMAGEM="$(imagem_de "$BASE")" || exit 2
usa_o_24() {
  local f
  f="$(arquivo_do_job "$1")"
  [ -n "$f" ] && [ -f "$RAIZ/.github/workflows/$f" ] || return 1
  awk -v job="$1" '
    /^jobs:/ {emjobs=1}
    emjobs && /^  [A-Za-z0-9_-]+:[[:space:]]*$/ {atual=$1; sub(/:$/, "", atual)}
    atual==job && /ubuntu-24\.04([^-.0-9]|$)/ {achou=1}
    END {exit !achou}' "$RAIZ/.github/workflows/$f"
}

IMAGEM_24="${CI_LOCAL_IMAGEM_24:-}"
if [ -z "$IMAGEM_24" ]; then
  for j in "${JOBS[@]}"; do
    usa_o_24 "$j" || continue
    IMAGEM_24="$(imagem_de "$BASE_24")" || exit 2
    break
  done
fi
IMAGEM_22=""
DOCKERFILE_22="$RAIZ/scripts/ci-local/Dockerfile.ubuntu-22.04"
for j in "${JOBS[@]}"; do
  [ "$(campo ROLA "$j" 4)" = ubuntu-22.04 ] || continue
  if [ -f "$DOCKERFILE_22" ]; then
    IMAGEM_22="hefesto-ci-local-22:$(sha256sum "$DOCKERFILE_22" | cut -c1-10)"
    if ! docker image inspect "$IMAGEM_22" >/dev/null 2>&1; then
      echo "ci-local: montando a imagem $IMAGEM_22 sobre $BASE_22 (uma vez só)" >&2
      docker build -q -t "$IMAGEM_22" -f "$DOCKERFILE_22" "$RAIZ/scripts/ci-local" >/dev/null 2>&1 \
        || { echo "ci-local: a imagem $IMAGEM_22 (do job $j) não montou (rede?); nada rodou" >&2; exit 2; }
    fi
  else
    docker image inspect "$BASE_22" >/dev/null 2>&1 || docker pull -q "$BASE_22" >/dev/null 2>&1 \
      || { echo "ci-local: a imagem $BASE_22 (do job $j) não baixou (rede?); nada rodou" >&2; exit 2; }
    IMAGEM_22="$BASE_22"
  fi
done

mkdir -p "$SAIDA" "$CASA/ci-local/artefatos"
TMP="$(mktemp -d /tmp/cil.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

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

tirar_passo() {
  awk -v job="$2" -v passo="$3" '
    /^jobs:/ {emjobs=1}
    emjobs && /^  [A-Za-z0-9_-]+:[[:space:]]*$/ {atual=$1; sub(/:$/, "", atual)}
    pula && (/^      - / || /^  [A-Za-z0-9_-]+:/ || /^[^ #]/) {pula=0}
    atual==job && $0 == "      - name: " passo {pula=1}
    !pula {print}' "$1" > "$1.n" && mv "$1.n" "$1"
}
tirar_needs() {
  awk -v job="$2" -v tirar="$3" '
    BEGIN {n = split(tirar, t, ","); for (i = 1; i <= n; i++) fora[t[i]] = 1}
    /^jobs:/ {emjobs=1}
    emjobs && /^  [A-Za-z0-9_-]+:[[:space:]]*$/ {atual=$1; sub(/:$/, "", atual)}
    atual==job && /^    needs:/ {
      v = $0; sub(/^    needs:[[:space:]]*/, "", v); gsub(/[\[\]]/, "", v)
      m = split(v, d, /[[:space:]]*,[[:space:]]*/); resto = ""
      for (i = 1; i <= m; i++) { gsub(/^[[:space:]]+|[[:space:]]+$/, "", d[i]); if (d[i] != "" && !(d[i] in fora)) resto = resto (resto == "" ? "" : ", ") d[i] }
      if (resto != "") print "    needs: [" resto "]"
      next
    }
    {print}' "$1" > "$1.n" && mv "$1.n" "$1"
}
REF_DO_RELEASE='^( +)ref: \$\{\{ github\.event\.inputs\.tag \|\| github\.ref \}\}[[:space:]]*$'
tirar_ref() { sed -E "s/$REF_DO_RELEASE/\1lfs: false/" "$1" > "$1.n" && mv "$1.n" "$1"; }
yaml_de() {
  local job="$1" f copia="$TMP/$1.yml" mudou=0 p
  f="$(arquivo_do_job "$job")"; [ -n "$f" ] || return 1
  f="$ARV/.github/workflows/$f"
  cp "$f" "$copia"
  if grep -qE "$REF_DO_RELEASE" "$copia"; then tirar_ref "$copia"; mudou=1; fi
  if [ "$modo" = rapido ]; then
    while IFS= read -r p; do [ -n "$p" ] && { tirar_passo "$copia" "$job" "$p"; mudou=1; }; done < <(campo PULA-NO-RAPIDO "$job" 3)
  fi
  for p in "${SEM_PASSO[@]:-}"; do
    [ -n "$p" ] && [ "${p%%|*}" = "$job" ] && { tirar_passo "$copia" "$job" "${p#*|}"; mudou=1; }
  done
  while IFS='|' read -r _ o_job deps _; do
    [ -n "$o_job" ] && { tirar_needs "$copia" "$o_job" "$deps"; mudou=1; }
  done < <(linhas | awk -F'|' '$1=="SEM-NEEDS"')
  if [ "$mudou" = 1 ]; then echo "$copia"; else echo "$f"; fi
}

SUJA=""
if ! git -C "$RAIZ" diff --cached --quiet HEAD -- 2>/dev/null; then SUJA=" (índice com mudança não commitada)"; fi

chamar_act() {
  local job="$1" yml="$2" log="$3" porta="$4" rotulo="${5:-}" extras=() cache rc
  cache="$TMP/acoes-$job${rotulo:+-$rotulo}"
  mkdir -p "$CACHE_ACOES"
  cp -a "$CACHE_ACOES/." "$cache/" 2>/dev/null || mkdir -p "$cache"
  [ -f "$TMP/tag-$job.json" ] && extras+=(-e "$TMP/tag-$job.json")
  [ -n "$IMAGEM_24" ] && extras+=(-P "ubuntu-24.04=$IMAGEM_24")
  if [ -n "$rotulo" ]; then
    extras+=(--matrix "os:$rotulo")
    [ "$rotulo" = ubuntu-22.04 ] && extras+=(-P "ubuntu-22.04=$IMAGEM_22")
  fi
  (
    cd "$ARV" || exit 2
    "$ACT" push -W "$yml" -j "$job" \
      -P "ubuntu-latest=$IMAGEM" -P "ubuntu-26.04=$IMAGEM" "${extras[@]}" \
      --pull=false --rm --container-architecture linux/amd64 "${OFFLINE[@]}" \
      --action-cache-path "$cache" \
      --artifact-server-path "$CASA/ci-local/artefatos" \
      --artifact-server-addr 127.0.0.1 --artifact-server-port "$porta" \
      --cache-server-addr 127.0.0.1 \
      --concurrent-jobs "$PERNAS" \
      --env RUNNER_TOOL_CACHE=/tmp/hostedtoolcache --env AGENT_TOOLSDIRECTORY=/tmp/hostedtoolcache \
      --env GIT_CONFIG_COUNT=1 --env GIT_CONFIG_KEY_0=safe.directory --env 'GIT_CONFIG_VALUE_0=*' \
      "${OPCOES[@]}" ${CI_LOCAL_ACT_EXTRA:-} >"$log" 2>&1
  )
  rc=$?
  ( flock 9; cp -an "$cache/." "$CACHE_ACOES/" 2>/dev/null ) 9>"$CACHE_ACOES/.trava"
  rm -rf "$cache"
  return "$rc"
}

INICIO_DO_PASSO=$'\xe2\xad\x90 Run '
FALHA_DO_PASSO=$'\xe2\x9d\x8c  Failure - '
so_a_rede_reprovou() {
  local log="$1" redes act_rede=0
  redes="$(grep -nE -e "$REDE_PASSO" "$log" | cut -d: -f1 | tr '\n' ' ')"
  grep -qE "$REDE_ACT" "$log" && act_rede=1
  awk -v redes="$redes" -v act="$act_rede" -v run="$INICIO_DO_PASSO" -v falha="$FALHA_DO_PASSO" '
    BEGIN { n = split(redes, r, " "); for (i = 1; i <= n; i++) eh[r[i]] = 1 }
    { p = ""; if (match($0, /^\[[^]]*\]/)) p = substr($0, 1, RLENGTH) }
    p != "" && index($0, run) { rede[p] = 0 }
    p != "" && (NR in eh) { rede[p] = 1 }
    p != "" && index($0, falha) { f++; if (rede[p] || (act && index($0, "Set up job"))) fr++ }
    END { exit !((f > 0 && f == fr) || (f == 0 && (n > 0 || act))) }' "$log"
}

rodar_job() {
  local job="$1" i="$2" yml log rc=0 r ini porta rot arquivo_do_yaml numero rotulos=("")
  log="$SAIDA/$job.log"
  ini=$(date +%s)
  yml="$(yaml_de "$job")" || { echo "ci-local: o job '$job' não está em workflow nenhum" > "$log"; echo 2 > "$SAIDA/$job.rc"; return 2; }
  porta=$((20000 + ($$ % 1000) * 40 + i % 40))
  arquivo_do_yaml="$(arquivo_do_job "$job")"
  if [ -n "$(campo EM-TAG "$arquivo_do_yaml" 3)" ]; then
    numero="$(sed -nE 's/^version *= *"([^"]+)".*/\1/p' "$ARV/pyproject.toml" 2>/dev/null | head -1)"
    printf '{"ref": "refs/tags/v%s"}\n' "${numero:-0.0.0-local}" > "$TMP/tag-$job.json"
  fi
  [ "$(campo ROLA "$job" 4)" = ubuntu-22.04 ] && rotulos=(ubuntu-24.04 ubuntu-22.04)
  [ -n "$SO_PERNA" ] && [ "${#rotulos[@]}" -gt 1 ] && rotulos=("$SO_PERNA")
  : > "$log"
  for rot in "${rotulos[@]}"; do
    if [ -z "$rot" ]; then
      chamar_act "$job" "$yml" "$log" "$porta"; r=$?
    else
      chamar_act "$job" "$yml" "$log.$rot" "$porta" "$rot"; r=$?
      { echo "=== a perna $rot (rc=$r)"; cat "$log.$rot"; } >> "$log"; rm -f "$log.$rot"
    fi
    if [ "$r" != 0 ]; then case "$rc" in 0 | 2) rc=$r ;; esac; fi
  done
  if [ "$rc" != 0 ] && [ "$rc" != 2 ] && so_a_rede_reprovou "$log"; then
    echo "ci-local: a rede caiu no meio deste job; ele não rodou de verdade (o log tem a linha)" >> "$log"
    echo rede > "$SAIDA/$job.motivo"; rc=2
  elif [ "$rc" != 0 ] && [ "$rc" != 2 ] && ! grep -qF "$FALHA_DO_PASSO" "$log" && grep -qE "$DOCKER_CAIDO" "$log"; then
    echo "ci-local: o docker não respondeu a tempo neste job; ele não rodou de verdade (o log tem a linha)" >> "$log"
    echo docker > "$SAIDA/$job.motivo"; rc=2
  fi
  echo "$rc" > "$SAIDA/$job.rc"
  echo $(( $(date +%s) - ini )) > "$SAIDA/$job.seg"
  return "$rc"
}

acoes_em_falta() {
  local j f u ref
  for j in "${JOBS[@]}"; do
    f="$(arquivo_do_job "$j")"; [ -n "$f" ] || continue
    grep -hoE 'uses: *[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+[^ ]*@[^ ]+' "$ARV/.github/workflows/$f"
  done | sed -E 's/^uses: *//' | sort -u | while read -r u; do
    case "$u" in actions/checkout@*) continue ;; esac
    ref="${u#*@}"; u="${u%%@*}"
    [ -d "$CACHE_ACOES/$(echo "$u" | cut -d/ -f1,2 | tr / -)@${ref//\//-}" ] || echo "$u@$ref"
  done
}
OFFLINE=()
if [ -z "$(acoes_em_falta)" ]; then OFFLINE=(--action-offline-mode); fi

needs_do_job() {
  local f tira; f="$(arquivo_do_job "$1")"; [ -n "$f" ] || return 0
  tira=",$(campo SEM-NEEDS "$1" 3),"
  awk -v job="$1" '
    /^jobs:/ {emjobs=1}
    emjobs && /^  [A-Za-z0-9_-]+:[[:space:]]*$/ {atual=$1; sub(/:$/, "", atual)}
    atual==job && /^    needs:/ {v=$0; sub(/^    needs:[[:space:]]*/, "", v); gsub(/[\[\]]/, "", v); n=split(v, d, /[[:space:]]*,[[:space:]]*/); for (i=1;i<=n;i++) if (d[i] != "") print d[i]}
  ' "$RAIZ/.github/workflows/$f" | while read -r d; do case "$tira" in *",$d,"*) ;; *) echo "$d" ;; esac; done
}
plano_do_job() {
  local fila=("$1") visto=" " atual d
  while [ "${#fila[@]}" -gt 0 ]; do
    atual="${fila[0]}"; fila=("${fila[@]:1}")
    case "$visto" in *" $atual "*) continue ;; esac
    visto="$visto$atual "
    while read -r d; do [ -n "$d" ] && fila+=("$d"); done < <(needs_do_job "$atual")
  done
  for d in $visto; do echo "$d"; done
}
declare -A COBERTO=()
for j in "${JOBS[@]}"; do
  for k in "${JOBS[@]}"; do
    [ "$j" != "$k" ] && plano_do_job "$k" | grep -qx "$j" && { COBERTO[$j]=$k; break; }
  done
done

INI=$(date +%s)
i=0
for j in "${JOBS[@]}"; do
  [ -n "$j" ] || continue
  [ -z "${COBERTO[$j]:-}" ] || continue
  while [ "$(jobs -rp | wc -l)" -ge "$EM_PARALELO" ]; do wait -n 2>/dev/null || true; done
  ( rodar_job "$j" "$i"; rc=$?
    if [ "$rc" = 0 ]; then echo "ci-local: $j verde ($(cat "$SAIDA/$j.seg")s)" >&2
    elif [ "$rc" = 2 ]; then echo "ci-local: $j NÃO RODOU$([ -f "$SAIDA/$j.motivo" ] && echo " ($(cat "$SAIDA/$j.motivo"))") (log $SAIDA/$j.log)" >&2
    else echo "ci-local: $j VERMELHO rc=$rc (log $SAIDA/$j.log)" >&2; fi ) &
  i=$((i + 1))
done
wait
for j in "${!COBERTO[@]}"; do
  k="${COBERTO[$j]}"
  cp "$SAIDA/$k.rc" "$SAIDA/$j.rc" 2>/dev/null || echo 2 > "$SAIDA/$j.rc"
  echo "rodou dentro do plano de $k: veja $SAIDA/$k.log" > "$SAIDA/$j.log"
  echo "ci-local: $j rodou dentro do plano de $k (rc=$(cat "$SAIDA/$j.rc"))" >&2
done

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
mkdir -p "$CASA/ci-local"
printf '%s|%s|%s\n' "$(date +%Y-%m-%dT%H:%M)" "$(git -C "$RAIZ" rev-parse --short=12 HEAD 2>/dev/null || echo -)" "$RES" \
  > "$CASA/ci-local/ultimo-$modo.txt"
echo "$RES"
[ "${#VERMELHO[@]}" -gt 0 ] && exit 1
[ "${#NAO_RODOU[@]}" -gt 0 ] && exit 2
exit 0
