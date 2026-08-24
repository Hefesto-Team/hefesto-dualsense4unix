#!/usr/bin/env bash
# scripts/instalar-hooks.sh — liga os ganchos versionados deste repositório.
#
# Rode UMA vez depois de clonar:  bash scripts/instalar-hooks.sh
#
# Por que um instalador e não um arquivo pronto: `.git/hooks/` não é versionado
# pelo git, então um gancho lá dentro não viaja para quem clona. O padrão é o
# script viajar em `scripts/hooks/` e um link o ligar.
#
# NUNCA com sudo — o `HOME` viraria `/root`, que é a mesma armadilha que o
# `install.sh` deste projeto documenta.
set -euo pipefail
RAIZ="$(git rev-parse --show-toplevel)"
cd "$RAIZ"

if [ "${EUID:-$(id -u)}" -eq 0 ]; then
  echo "não rode com sudo: o HOME vira /root e o gancho aponta para o lugar errado." >&2
  exit 1
fi

mkdir -p .git/hooks
for gancho in scripts/hooks/*; do
  nome="$(basename "$gancho")"
  ln -sf "../../$gancho" ".git/hooks/$nome"
  echo "ligado: .git/hooks/$nome -> $gancho"
done

echo
echo "Nota: os ganchos GLOBAIS dela (~/.config/git/hooks) continuam valendo e"
echo "rodam ANTES destes — o global encadeia o local. Nada foi mexido lá."
