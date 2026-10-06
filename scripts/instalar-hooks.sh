#!/usr/bin/env bash
# scripts/instalar-hooks.sh — liga os ganchos versionados deste repositório.
#
# Rode UMA vez depois de clonar:  bash scripts/instalar-hooks.sh
#         ver o que faria, sem mexer: bash scripts/instalar-hooks.sh --conferir
#         (sai 1 quando faria alguma coisa; sem argumento é idempotente)
#
# O `--conferir` também avisa quando a máquina não assina commit (o `dev` e o `main` exigem o selo
# «Verified»). É só aviso: não muda o código de saída e nunca configura nada. Quem configura a chave é
# `bash scripts/github/assinar-commits.sh --aplicar`.
#
# Por que um instalador e não um arquivo pronto: `.git/hooks/` não é versionado
# pelo git, então um gancho lá dentro não viaja para quem clona.
#
# A POLÍTICA DE AUTORIA tem dois pontos de entrada, e o instalador liga os dois:
#   1. o `pre-push` deste repositório, COPIADO para o diretório comum do git
#      (`git rev-parse --git-common-dir`), que toda árvore do repositório
#      enxerga. Copiado e NÃO ligado por link: um link cujo alvo some (a árvore
#      de voo apagada) desliga a política calado, e o `pre-push` copiado só
#      depende de `scripts/check_autoria.py` da árvore em que o push acontece;
#   2. a chave `autoria.politica` na configuração do repositório, que o gancho
#      GLOBAL de quem tem `core.hooksPath` lê para chamar a mesma régua.
#
# NUNCA com sudo — o `HOME` viraria `/root`, que é a mesma armadilha que o
# `install.sh` deste projeto documenta.
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

# Avisa (nunca aplica) quando o git global desta conta não assina commit. Só no `--conferir`, e só se o
# conferidor existe nesta árvore.
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

# 1. `autoria.politica`: grava sempre, com ou sem `core.hooksPath`.
if [ "$(git config --local --get autoria.politica || true)" != "$POLITICA" ]; then
  FARIA=$((FARIA + 1))
  if [ "$CONFERIR" -eq 1 ]; then
    echo "faria: git config autoria.politica $POLITICA"
  else
    git config --local autoria.politica "$POLITICA"
    echo "gravado: autoria.politica = $POLITICA"
  fi
fi

# DOIS DEFEITOS MEDIDOS NESTE INSTALADOR, em 15/09/2026, e o segundo custou
# caro:
#
#   1. `.git` É UM ARQUIVO NUMA WORKTREE, não um diretório. O `mkdir -p
#      .git/hooks` falhava com *"Não é um diretório"* e o instalador morria sem
#      ligar nada. Quem sabe onde o repositório mora é o git: `--git-common-dir`.
#
#   2. `git rev-parse --git-path hooks` NÃO devolve o diretório do repositório
#      quando `core.hooksPath` está configurado — devolve o caminho GLOBAL. A
#      primeira tentativa de cura usou esse comando e o `ln -sf` SOBRESCREVEU os
#      ganchos globais dela (`~/.config/git/hooks/pre-commit`, 21 KB, e
#      `commit-msg`), trocando-os por links para os daqui. Foram restaurados da
#      fonte canônica (`~/.config/zsh/hooks/`), byte a byte. **Um instalador de
#      repositório não escreve fora do repositório**, e este NÃO instala gancho
#      nenhum quando há `core.hooksPath`: grava só a política, que o gancho
#      global lê.
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

# 2. O `pre-push`: copiado, e nunca por cima de um gancho de outra autoria.
ORIGEM="scripts/hooks/pre-push"
DESTINO="$GANCHOS/pre-push"
if [ -e "$DESTINO" ] || [ -L "$DESTINO" ]; then
  if [ -L "$DESTINO" ] && [ ! -e "$DESTINO" ]; then
    :  # link morto: é o desligamento calado que a cópia existe para evitar; troca
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

# 3. Os outros ganchos versionados seguem como eram: ligados por link, no
# diretório comum. O `pre-push` fica de fora do laço (já foi tratado acima) e o
# `pre-commit` só liga onde já ligava: reativá-lo em toda worktree é decisão à
# parte, com medição.
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
