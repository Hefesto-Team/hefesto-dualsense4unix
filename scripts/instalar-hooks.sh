#!/usr/bin/env bash
set -euo pipefail
RAIZ="$(git rev-parse --show-toplevel)"
cd "$RAIZ"

CONFERIR=0
case "${1:-}" in
  --conferir) CONFERIR=1 ;;
  "") ;;
  *) echo "uso: bash scripts/instalar-hooks.sh [--conferir]" >&2; exit 2 ;;
esac

if [ "${EUID:-$(id -u)}" -eq 0 ]; then
  echo "não rode com sudo: o HOME vira /root e o gancho aponta para o lugar errado." >&2
  exit 1
fi

avisar_assinatura() {
  local assinar="scripts/github/assinar-commits.sh" saida
  [ "$CONFERIR" -eq 1 ] && [ -f "$assinar" ] || return 0
  if ! saida="$(bash "$assinar" --conferir 2>&1)"; then
    echo "AVISO: esta máquina não assina commit, e o dev e o main exigem commit assinado:"
    printf '%s\n' "$saida" | sed 's/^/  /'
    echo "  para configurar: bash scripts/github/assinar-commits.sh --aplicar"
  fi
}

POLITICA="scripts/check_autoria.py"
COMUM="$(git rev-parse --path-format=absolute --git-common-dir)"
CAMINHO_GLOBAL="$(git config --get core.hooksPath || true)"
FARIA=0

if [ "$(git config --local --get autoria.politica || true)" != "$POLITICA" ]; then
  FARIA=$((FARIA + 1))
  if [ "$CONFERIR" -eq 1 ]; then
    echo "faria: git config autoria.politica $POLITICA"
  else
    git config --local autoria.politica "$POLITICA"
    echo "gravado: autoria.politica = $POLITICA"
  fi
fi

if [ -n "$CAMINHO_GLOBAL" ]; then
  echo "core.hooksPath = $CAMINHO_GLOBAL: o git IGNORA os ganchos do repositório" \
       "quando essa opção existe, então nenhum gancho foi instalado."
  echo "  A política de autoria chega pelo gancho global, que lê autoria.politica."
  echo "  Gancho nenhum roda em cherry-pick, rebase ou --no-verify: a trava que"
  echo "  alcança esses caminhos é o portão \`autoria-historia\`, em \`bash scripts/portoes.sh\`."
  avisar_assinatura
  if [ "$CONFERIR" -eq 1 ]; then
    [ "$FARIA" -eq 0 ] && echo "conferido: nada a fazer." && exit 0
    exit 1
  fi
  exit 0
fi

GANCHOS="$COMUM/hooks"
[ "$CONFERIR" -eq 1 ] || mkdir -p "$GANCHOS"

ORIGEM="scripts/hooks/pre-push"
DESTINO="$GANCHOS/pre-push"
if [ -e "$DESTINO" ] || [ -L "$DESTINO" ]; then
  if [ -L "$DESTINO" ] && [ ! -e "$DESTINO" ]; then
    :
  elif ! grep -q "check_autoria.py" "$DESTINO" 2>/dev/null; then
    echo "RECUSADO: $DESTINO já existe e não é o gancho de autoria deste repositório." >&2
    echo "  Junte as duas coisas à mão: o gancho daqui só chama" >&2
    echo "    python3 \"\$(git rev-parse --show-toplevel)\"/$POLITICA pre-push \"\$@\"" >&2
    exit 1
  fi
fi
if [ -L "$DESTINO" ] || ! cmp -s "$ORIGEM" "$DESTINO" 2>/dev/null || [ ! -x "$DESTINO" ]; then
  FARIA=$((FARIA + 1))
  if [ "$CONFERIR" -eq 1 ]; then
    echo "faria: copiar $ORIGEM para $DESTINO"
  else
    rm -f "$DESTINO"
    cp "$ORIGEM" "$DESTINO"
    chmod +x "$DESTINO"
    echo "copiado: $ORIGEM -> $DESTINO"
  fi
fi

for gancho in scripts/hooks/*; do
  nome="$(basename "$gancho")"
  [ "$nome" = "pre-push" ] && continue
  if [ "$(readlink "$GANCHOS/$nome" 2>/dev/null || true)" != "$RAIZ/$gancho" ]; then
    FARIA=$((FARIA + 1))
    if [ "$CONFERIR" -eq 1 ]; then
      echo "faria: ligar $GANCHOS/$nome -> $gancho"
    else
      ln -sf "$RAIZ/$gancho" "$GANCHOS/$nome"
      echo "ligado: $GANCHOS/$nome -> $gancho"
    fi
  fi
done

echo
echo "Nota: gancho de commit-msg não roda em cherry-pick, rebase, merge"
echo "--no-edit nem sob --no-verify. A trava que alcança esses caminhos é o"
echo "portão \`autoria-historia\`, em \`bash scripts/portoes.sh\`."

avisar_assinatura
if [ "$CONFERIR" -eq 1 ]; then
  [ "$FARIA" -eq 0 ] && echo "conferido: nada a fazer." && exit 0
  echo "conferido: $FARIA passo(s) a fazer."
  exit 1
fi
echo "instalado: $FARIA passo(s) feitos."
