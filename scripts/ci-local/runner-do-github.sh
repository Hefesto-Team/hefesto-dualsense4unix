#!/usr/bin/env bash
set -euo pipefail
FERRAMENTAS="$1"
shift
MANIFESTO=https://raw.githubusercontent.com/actions/python-versions/main/versions-manifest.json

useradd --uid 1001 --create-home --shell /bin/bash runner
for grupo in adm users docker systemd-journal; do
  if getent group "$grupo" >/dev/null; then usermod --append --groups "$grupo" runner; fi
done
printf 'runner ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/runner
chmod 0440 /etc/sudoers.d/runner

pasta="$(mktemp -d)"
curl -fsSL --retry 3 -o "$pasta/manifesto.json" "$MANIFESTO"
sistema="$(sed -nE 's/^VERSION_ID="?([^"]+)"?$/\1/p' /etc/os-release)"
for alvo in "$@"; do
  url="$(python3 - "$pasta/manifesto.json" "$alvo" "$sistema" <<'PY'
import json
import sys

manifesto, alvo, sistema = sys.argv[1:4]
for lancamento in json.load(open(manifesto, encoding="utf-8")):
    numero = lancamento["version"]
    if not lancamento.get("stable") or not numero.startswith(alvo + "."):
        continue
    for arquivo in lancamento["files"]:
        if (arquivo["platform"], arquivo.get("platform_version"), arquivo["arch"]) == ("linux", sistema, "x64"):
            print(arquivo["download_url"])
            sys.exit(0)
sys.exit(f"o manifesto não tem o Python {alvo} para o Ubuntu {sistema}")
PY
)"
  mkdir "$pasta/$alvo"
  curl -fsSL --retry 3 "$url" | tar -xz -C "$pasta/$alvo"
  (cd "$pasta/$alvo" && LD_LIBRARY_PATH="$PWD/lib" AGENT_TOOLSDIRECTORY="$FERRAMENTAS" RUNNER_TOOL_CACHE="$FERRAMENTAS" bash ./setup.sh)
  instalado="$(ls -d "$FERRAMENTAS/Python/$alvo".*/x64)"
  patchelf --set-rpath "$instalado/lib" "$instalado/bin/python$alvo"
done
rm -rf "$pasta"
chown -R runner:runner "$FERRAMENTAS"
