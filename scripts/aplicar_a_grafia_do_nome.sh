#!/usr/bin/env bash
# aplicar_a_grafia_do_nome.sh — o nome do produto se escreve `DualSense4Unix`.
#
# A CURA DE `scripts/check_a_grafia_do_nome.py`, e ela é IDEMPOTENTE: a segunda
# corrida não muda byte nenhum. Ela existe versionada porque a correção atravessa
# 174 arquivos, e quem costurar outra frente por cima precisa REAPLICAR sem
# refazer a medição do zero.
#
# O QUE ELE NÃO TOCA, e cada guarda protege um identificador técnico MEDIDO
# (a razão inteira de cada um está na docstring do portão):
#   (?<![-\w])     -> `Hefesto-Dualsense4Unix` (wm_class, StartupWMClass=, Icon=,
#                     last_class, window_class, nomes de .AppImage/.png/.flatpak)
#                     e `com.vitoriamaria.HefestoDualsense4Unix` (app-id Flatpak).
#   (?! Virtual )  -> os nós uinput `… Virtual Keyboard` / `… Virtual Mouse+Keyboard`.
#   (?! virtual\)) -> `… pad (Hefesto - Dualsense4Unix virtual)` e o Pro Controller:
#                     jogos sob Proton casam por SUBSTRING do nome do aparelho.
#
# Rode da RAIZ da árvore. Depois: `python3 scripts/check_a_grafia_do_nome.py`.
set -euo pipefail

cd "$(dirname "$0")/.."

# Os arquivos que NOMEIAM a grafia errada como defeito — a citação não se limpa.
# Tem de bater com `ISENTOS` de scripts/check_a_grafia_do_nome.py.
ISENTOS='^(docs/process/agentes/2026-09-11/ESQUELETO-C2-opus\.md'
ISENTOS+='|docs/process/sprints/2026-09-11-A-FILA-QUE-A-ONDA-ABRIU-INDICE\.md'
ISENTOS+='|docs/process/sprints/2026-09-11-F6-O-NOME-TEM-UM-DONO-e-a-barra-passa-a-ler\.md'
ISENTOS+='|scripts/check_a_grafia_do_nome\.py'
ISENTOS+='|scripts/aplicar_a_grafia_do_nome\.sh'
ISENTOS+='|tests/unit/test_portao_a_grafia_do_nome_morde\.py)$'

# `git grep -lI` já exclui binário: os .mo saem do .po, logo abaixo.
if git grep -lIz 'Dualsense4Unix' -- . | grep -zEv "$ISENTOS" \
    | xargs -0 --no-run-if-empty perl -CSD -pi -e \
        's/(?<![-\w])Dualsense4Unix(?! Virtual )(?! virtual\))/DualSense4Unix/g'
then
    :
fi

# Os `.mo` são compilados dos `.po`, e os msgid mudaram junto com os literais.
if command -v msgfmt >/dev/null 2>&1; then
    bash scripts/i18n_compile.sh >/dev/null
else
    echo "AVISO: msgfmt ausente — os .mo ficaram com os msgid velhos." >&2
fi

echo "grafia reaplicada. Confira: python3 scripts/check_a_grafia_do_nome.py"
