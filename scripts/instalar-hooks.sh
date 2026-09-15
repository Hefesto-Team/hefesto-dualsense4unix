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

# DOIS DEFEITOS MEDIDOS NESTE INSTALADOR, em 15/09/2026, e o segundo custou
# caro:
#
#   1. `.git` É UM ARQUIVO NUMA WORKTREE, não um diretório. O `mkdir -p
#      .git/hooks` falhava com *"Não é um diretório"* e o instalador morria sem
#      ligar nada. Quem sabe onde o repositório mora é o git: `--git-dir`.
#
#   2. `git rev-parse --git-path hooks` NÃO devolve o diretório do repositório
#      quando `core.hooksPath` está configurado — devolve o caminho GLOBAL. A
#      primeira tentativa de cura usou esse comando e o `ln -sf` SOBRESCREVEU os
#      ganchos globais dela (`~/.config/git/hooks/pre-commit`, 21 KB, e
#      `commit-msg`), trocando-os por links para os daqui. Foram restaurados da
#      fonte canônica (`~/.config/zsh/hooks/`), byte a byte. **Um instalador de
#      repositório não escreve fora do repositório**, e este agora RECUSA em vez
#      de escrever.
CAMINHO_GLOBAL="$(git config --get core.hooksPath || true)"
if [ -n "$CAMINHO_GLOBAL" ]; then
  echo "RECUSADO: esta máquina tem core.hooksPath = $CAMINHO_GLOBAL" >&2
  echo "  O git IGNORA os ganchos do repositório quando essa opção existe, e" >&2
  echo "  escrever lá seria mexer na configuração global de quem está usando a" >&2
  echo "  máquina — foi o que este script fez por engano em 15/09/2026." >&2
  echo "" >&2
  echo "  Se você QUER os ganchos deste repositório valendo globalmente, copie-os" >&2
  echo "  à mão, sabendo o que sobrescreve:" >&2
  echo "    ls -la $CAMINHO_GLOBAL" >&2
  echo "    cp scripts/hooks/<gancho> $CAMINHO_GLOBAL/<gancho>" >&2
  echo "" >&2
  echo "  E lembre: gancho nenhum roda em cherry-pick, rebase ou --no-verify." >&2
  echo "  A trava que alcança esses caminhos é o portão \`historia-sem-ia\`," >&2
  echo "  em \`bash scripts/portoes.sh\`." >&2
  exit 1
fi

GANCHOS="$(git rev-parse --git-dir)/hooks"
mkdir -p "$GANCHOS"
for gancho in scripts/hooks/*; do
  nome="$(basename "$gancho")"
  ln -sf "$RAIZ/$gancho" "$GANCHOS/$nome"
  echo "ligado: $GANCHOS/$nome -> $gancho"
done

# `core.hooksPath` DESLIGA `.git/hooks` INTEIRO — medido em 15/09/2026. Quando
# essa opção está configurada (a máquina dela aponta para `~/.config/git/hooks`),
# o git NÃO consulta `.git/hooks`, e os links criados acima não rodam. Dizer isso
# é obrigatório: um instalador que anuncia sucesso sobre gancho que não roda é o
# defeito-mãe desta casa — a guarda que existe, roda, e não guarda nada.
echo
echo "Nota: gancho de commit-msg não roda em cherry-pick, rebase, merge"
echo "--no-edit nem sob --no-verify. A trava que alcança esses caminhos é o"
echo "portão \`historia-sem-ia\`, em \`bash scripts/portoes.sh\`."
