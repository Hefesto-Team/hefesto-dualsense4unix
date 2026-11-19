#!/usr/bin/env bash
set -uo pipefail

TETO_ARQUIVOS=5
TETO_LINHAS=150
RISCO=(install.sh uninstall.sh 'assets/systemd/*' 'assets/*.rules' 'assets/polkit/*' 'assets/dkms/*'
  'src/hefesto_dualsense4unix/broker/*' 'scripts/*_raiz.sh' '.github/*' pyproject.toml constraints.txt)
AMBIENTE_DO_INSTALL='^(HOME|USER|LOGNAME|SHELL|TERM|LANG|LC_[A-Z]+|PATH|TMPDIR|DISPLAY|XAUTHORITY|WAYLAND_DISPLAY|DBUS_SESSION_BUS_ADDRESS|SUDO_ASKPASS|XDG_[A-Z_]+|HEFESTO_[A-Z_]+)='

uso() {
  echo "uso: subir-mudanca-pequena.sh <arquivo>… [-m \"assunto\"] [--origem <id>]" >&2
  echo "     subir-mudanca-pequena.sh --de <commit>" >&2
  exit 2
}
recusa() { echo "recusado: $*" >&2; exit 2; }

[ "$(id -u)" -ne 0 ] || recusa "não rode como root: o install usa o HOME de quem chama"

ARQUIVOS=() ASSUNTO="" ORIGEM="" DE=""
while [ $# -gt 0 ]; do
  case "$1" in
    -m | --origem | --de)
      [ -n "${2:-}" ] || uso
      case "$1" in -m) ASSUNTO="$2" ;; --origem) ORIGEM="$2" ;; --de) DE="$2" ;; esac
      shift 2 ;;
    -*) uso ;;
    *) ARQUIVOS+=("$1"); shift ;;
  esac
done
{ [ -n "$DE" ] && [ ${#ARQUIVOS[@]} -eq 0 ]; } || { [ -z "$DE" ] && [ ${#ARQUIVOS[@]} -gt 0 ]; } || uso

TOPO="$(git rev-parse --show-toplevel)" || exit 2
NOMES=()
for a in ${ARQUIVOS[@]+"${ARQUIVOS[@]}"}; do
  r="$(realpath -ms --relative-to="$TOPO" -- "$a")"
  case "$r" in ../* | /*) recusa "$a está fora do repositório" ;; esac
  NOMES+=("$r")
done
cd "$TOPO" || exit 2

[ "$(git symbolic-ref --short -q HEAD)" = dev ] || recusa "a pista curta sobe só no dev"
[ -z "$(git diff --cached --name-only)" ] || recusa "o índice já tem mudança; commite ou tire do índice antes"

if [ -n "$DE" ]; then
  git rev-parse -q --verify "$DE^{commit}" >/dev/null || recusa "$DE não é um commit"
  [ "$(git rev-list --no-walk --count --min-parents=2 "$DE")" -eq 0 ] || recusa "$DE é um merge"
  mapfile -t NOMES < <(git diff --name-only "$DE^" "$DE")
  CONTA="$(git diff --numstat "$DE^" "$DE")"
else
  CONTA="$(git diff --numstat HEAD -- "${NOMES[@]}")"
  for n in "${NOMES[@]}"; do
    if [ -n "$(git ls-files --others --exclude-standard -- "$n")" ]; then
      CONTA+=$'\n'"$(wc -l < "$n") 0 $n"
    elif ! cut -f3 <<< "$CONTA" | grep -qxF -- "$n"; then
      recusa "$n não tem mudança a subir"
    fi
  done
fi
LINHAS="$(awk '$1 ~ /^[0-9]+$/ {s += $1 + $2} END {print s + 0}' <<< "$CONTA")"

[ ${#NOMES[@]} -le $TETO_ARQUIVOS ] || recusa "${#NOMES[@]} arquivos (o teto é $TETO_ARQUIVOS): isto é do fecho"
[ "$LINHAS" -le $TETO_LINHAS ] || recusa "$LINHAS linhas (o teto é $TETO_LINHAS): isto é do fecho"
for n in "${NOMES[@]}"; do
  for p in "${RISCO[@]}"; do
    # shellcheck disable=SC2254
    case "$n" in $p) recusa "$n é caminho de risco: isto é do fecho" ;; esac
  done
done

INTEGRACOES=()
while IFS=$'\t' read -r arvore ramo; do
  frente="$(git rev-list --count "dev..$ramo")"
  [ "$frente" -eq 0 ] || recusa "a integração em $arvore tem $frente commit(s) fora do dev: espere o fecho da leva"
  INTEGRACOES+=("$arvore")
done < <(git worktree list --porcelain | awk '/^worktree /{w=substr($0,10)} /^branch refs\/heads\/integra\//{print w "\t" substr($0,8)}')

PASTA="$(git rev-parse --path-format=absolute --git-common-dir)/hefesto-pista-curta"
mkdir -p "$PASTA"
LOG="$PASTA/$(date +%Y%m%d-%H%M%S).log"
diz() { echo "$*"; echo "== $*" >> "$LOG"; }
C=- R=- I=-
parede() { diz "parede: commit ${C}s, rápido ${R}s, install ${I}s"; diz "log: $LOG"; }
para() { diz "$*"; parede; exit 1; }

diz "subindo ${#NOMES[@]} arquivo(s), $LINHAS linha(s): ${NOMES[*]}"
t=$SECONDS
if [ -n "$DE" ]; then
  git cherry-pick "$DE" >> "$LOG" 2>&1 || { git cherry-pick --abort >> "$LOG" 2>&1; para "commit: o $DE não entrou limpo"; }
else
  MSG=(-m "${ASSUNTO:-chore: mudança pequena em ${NOMES[*]}}")
  [ -z "$ORIGEM" ] || MSG+=(-m "Origem: $ORIGEM")
  git add -- "${NOMES[@]}" >> "$LOG" 2>&1 || para "commit: o git add falhou"
  git commit "${MSG[@]}" >> "$LOG" 2>&1 || para "commit: os ganchos recusaram (os arquivos ficam no índice)"
fi
C=$((SECONDS - t))
diz "commit: $(git rev-parse --short HEAD)"

for arvore in ${INTEGRACOES[@]+"${INTEGRACOES[@]}"}; do
  if git -C "$arvore" merge --ff-only -q dev >> "$LOG" 2>&1; then
    diz "integração $arvore: andou junto"
  else
    diz "integração $arvore: NÃO andou, leve-a ao dev com merge --ff-only"
  fi
done

RAPIDO=(bash scripts/portoes.sh --rapido)
VEZ="docs/process/ferramentas-da-leva/vez-do-pytest.sh"
[ ! -f "$VEZ" ] || RAPIDO=(bash "$VEZ" --ate 3 "${RAPIDO[@]}")
t=$SECONDS
"${RAPIDO[@]}" >> "$LOG" 2>&1
rc=$?
R=$((SECONDS - t))
[ "$rc" -eq 0 ] || para "rápido: vermelho; sem install, e o commit fica local"
diz "rápido: verde"

read -r -a ARGS <<< "${HEFESTO_INSTALL_ARGS:---dev}"
mapfile -t AMBIENTE < <(env | grep -E "$AMBIENTE_DO_INSTALL")
t=$SECONDS
env -i "${AMBIENTE[@]}" ./install.sh --yes "${ARGS[@]}" >> "$LOG" 2>&1
rc=$?
I=$((SECONDS - t))
[ "$rc" -eq 0 ] || para "install: falhou (rc=$rc)"
diz "install: feito"
parede
