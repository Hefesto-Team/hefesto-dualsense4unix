#!/bin/bash
# Entrypoint do AppImage Hefesto - Dualsense4Unix.
# $APPDIR é definido pelo AppRun do python-appimage.
#
# IMPORTANTE: este AppImage expõe APENAS a CLI. A GUI GTK3 requer
# PyGObject + GTK3 bundlados que python-appimage (ferramenta usada pra
# gerar o bundle) não inclui — só Python puro + deps Python puras.
# Para a GUI use .deb (apt install ./hefesto-dualsense4unix_*.deb) ou
# Flatpak (flatpak install Hefesto-Dualsense4Unix.flatpak).
#
# Sem args: imprime ajuda da CLI e sai. Com subcomando: roteia.

set -e

# APPIMAGE-BANNER-VERSAO-DERIVADA-01 (30/07): o banner e o nome do .deb
# sugerido saem da versão REAL do pacote embutido, nunca digitados. Antes eram
# os literais "v3.0.0" e "hefesto-dualsense4unix_3.0.0_amd64.deb" — um nome de
# arquivo que não existe mais (o build_deb.sh gera
# _<versão>_amd64_py<tag>.deb) — e este banner é o PRIMEIRO texto que alguém
# novo lê ao rodar o AppImage sem argumento.
#
# Este literal é o ÚNICO, e existe porque a consulta ao metadata pode falhar
# num bundle incompleto. Mesmo papel do fallback de __version__ em
# src/.../__init__.py: é ALVO do scripts/check_version_consistency.py, logo o
# portão de release reprova se o pyproject subir e este número ficar atrás.
HEFESTO_VERSION_FALLBACK="0.3.0"

PYTHON=""
for candidate in "$APPDIR"/opt/python*/bin/python3.*; do
    if [[ -x "$candidate" ]]; then
        PYTHON="$candidate"
        break
    fi
done

if [[ -z "$PYTHON" ]]; then
    echo "python embutido não encontrado no AppImage" >&2
    exit 1
fi

# Sem args, mostrar mensagem clara de uso CLI + ponteiros pra GUI.
if [[ $# -eq 0 ]]; then
    # Versão real do pacote instalado dentro do bundle. Se o metadata não
    # estiver lá, cai no literal acima em vez de imprimir vazio.
    HEFESTO_VERSION="$("$PYTHON" -c 'from importlib.metadata import version
print(version("hefesto-dualsense4unix"))' 2>/dev/null || true)"
    if [[ -z "$HEFESTO_VERSION" ]]; then
        HEFESTO_VERSION="$HEFESTO_VERSION_FALLBACK"
    fi
    # O .deb carrega a tag do Python no nome (_py312 / _py310), que depende de
    # em qual distro ele foi construído — por isso o glob no fim.
    cat <<BANNER >&2
Hefesto - Dualsense4Unix v${HEFESTO_VERSION} — AppImage (CLI only)

Para a GUI GTK3 use:
  - .deb       sudo apt install ./hefesto-dualsense4unix_${HEFESTO_VERSION}_amd64_py*.deb
  - Flatpak    flatpak install --user Hefesto-Dualsense4Unix.flatpak

Subcomandos CLI disponíveis abaixo:
BANNER
    exec "$PYTHON" -m hefesto_dualsense4unix --help
fi

exec "$PYTHON" -m hefesto_dualsense4unix "$@"
