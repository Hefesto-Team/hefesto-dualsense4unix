#!/usr/bin/env bash
set -euo pipefail
_ajuda() {
  cat <<'AJUDA'
scripts/github/assinar-commits.sh — configura o git desta conta para assinar commit e tag com a chave
SSH (o selo «Verified» do GitHub). O ruleset da história do `dev` e do `main` exige commit assinado
(`assinatura: exigida`, em `.github/repositorio.yml`), e quem empurra sem assinar é recusado.

  bash scripts/github/assinar-commits.sh                        o mesmo que --conferir
  bash scripts/github/assinar-commits.sh --conferir             diz o que falta; sai 1 se a máquina não assina
  bash scripts/github/assinar-commits.sh --aplicar              grava a configuração no git GLOBAL de quem roda
  bash scripts/github/assinar-commits.sh --aplicar --chave ~/.ssh/id_ed25519.pub
  bash scripts/github/assinar-commits.sh --conferir --provar   além da configuração, faz um commit de
                                                                brinquedo (descartável) e confere a assinatura
AJUDA
}

MODO=conferir
CHAVE=""
PROVAR=0
while [ $# -gt 0 ]; do
  case "$1" in
    --conferir) MODO=conferir ;;
    --aplicar) MODO=aplicar ;;
    --provar) PROVAR=1 ;;
    --chave)
      [ $# -ge 2 ] || { echo "uso: --chave <arquivo .pub>" >&2; exit 2; }
      CHAVE="$2"; shift ;;
    -h|--help) _ajuda; exit 0 ;;
    *) echo "uso: bash scripts/github/assinar-commits.sh [--conferir|--aplicar] [--provar] [--chave <arquivo .pub>]" >&2; exit 2 ;;
  esac
  shift
done

if [ "${EUID:-$(id -u)}" -eq 0 ]; then
  echo "não rode com sudo: o HOME vira /root e a configuração vai para a conta errada." >&2
  exit 2
fi

global() { git config --global --get "$1" 2>/dev/null || true; }

escolher_chave() {
  local c
  if [ -n "$CHAVE" ]; then printf '%s\n' "$CHAVE"; return; fi
  c="$(global user.signingkey)"
  if [ -n "$c" ]; then printf '%s\n' "$c"; return; fi
  for c in "$HOME/.ssh/id_ed25519.pub" "$HOME/.ssh/id_ecdsa.pub" "$HOME/.ssh/id_rsa.pub"; do
    if [ -f "$c" ]; then printf '%s\n' "$c"; return; fi
  done
  printf '\n'
}

provar() {
  local pub d email rc
  pub="${1/#\~/$HOME}"
  d="$(mktemp -d "${TMPDIR:-/tmp}/assinatura-XXXXXX")" || return 1
  email="$(global user.email)"
  email="${email:-assinatura@example.invalid}"
  printf '%s %s\n' "$email" "$(cut -d' ' -f1,2 "$pub")" > "$d/permitidas"
  (
    cd "$d" && git init -q brinquedo && cd brinquedo && mkdir "$d/sem-ganchos" \
      && printf 'brinquedo\n' > a.txt && git add a.txt \
      && timeout 30 git -c core.hooksPath="$d/sem-ganchos" -c user.email="$email" -c user.name=brinquedo \
           commit -q -m "o commit de brinquedo, assinado" </dev/null >/dev/null 2>&1 \
      && git cat-file commit HEAD | grep -q '^gpgsig ' \
      && git -c gpg.ssh.allowedSignersFile="$d/permitidas" verify-commit HEAD >/dev/null 2>&1
  )
  rc=$?
  rm -rf "$d"
  return "$rc"
}

provar_e_sair() {
  if provar "$atual"; then
    echo "um commit de brinquedo saiu assinado e a assinatura confere com $atual"
    exit 0
  fi
  echo "o commit de brinquedo NÃO saiu assinado com $atual (a chave privada tem senha e não foi carregada com ssh-add?)"
  exit 1
}

chave="$(escolher_chave)"
chave_em_disco="${chave/#\~/$HOME}"

falta=()
[ "$(global gpg.format)" = "ssh" ] || falta+=("gpg.format ssh")
atual="$(global user.signingkey)"
if [ -z "$atual" ]; then
  falta+=("user.signingkey")
elif [ ! -f "${atual/#\~/$HOME}" ]; then
  falta+=("user.signingkey aponta para um arquivo que não existe: $atual")
elif [ -n "$CHAVE" ] && [ "$atual" != "$CHAVE" ]; then
  falta+=("user.signingkey é $atual e a pedida é $CHAVE")
fi
[ "$(global commit.gpgsign)" = "true" ] || falta+=("commit.gpgsign true")
[ "$(global tag.gpgsign)" = "true" ] || falta+=("tag.gpgsign true")

if [ "$MODO" = "conferir" ]; then
  if [ "${#falta[@]}" -eq 0 ]; then
    echo "a máquina assina commit e tag (chave: $atual)"
    [ "$PROVAR" -eq 1 ] && provar_e_sair
    exit 0
  fi
  echo "a máquina não assina commit: faltam ${#falta[@]} item(ns):"
  for f in "${falta[@]}"; do echo "  - $f"; done
  if [ -z "$chave" ]; then
    echo "  nenhuma chave SSH pública encontrada em ~/.ssh; gere uma (ssh-keygen -t ed25519) e passe --chave"
  fi
  exit 1
fi

if [ "${#falta[@]}" -eq 0 ]; then
  echo "a máquina já assina commit e tag (chave: $atual): nada a fazer"
  [ "$PROVAR" -eq 1 ] && provar_e_sair
  exit 0
fi
if [ -z "$chave" ] || [ ! -f "$chave_em_disco" ]; then
  echo "não achei a chave pública (${chave:-nenhuma}): passe --chave <arquivo .pub>, ou gere uma" \
       "com ssh-keygen -t ed25519 e rode de novo" >&2
  exit 2
fi
case "$chave" in
  *.pub) ;;
  *) echo "a chave tem de ser a PÚBLICA (arquivo .pub): $chave" >&2; exit 2 ;;
esac
git config --global gpg.format ssh
git config --global user.signingkey "$chave"
git config --global commit.gpgsign true
git config --global tag.gpgsign true
echo "gravado no git global: gpg.format ssh, user.signingkey $chave, commit.gpgsign true, tag.gpgsign true"
echo "falta, se ainda não fez: pôr a chave $chave na conta do GitHub como «Signing key»"
if [ "$PROVAR" -eq 1 ]; then
  atual="$chave"
  provar_e_sair
fi
