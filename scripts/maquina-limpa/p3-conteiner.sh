#!/usr/bin/env bash

set -euo pipefail
_ajuda() {
  cat <<'AJUDA'
p3-conteiner.sh — o degrau P3 da escada da máquina limpa: o install como
USUÁRIA COMUM em outra distro, num contêiner. Muda a distro e o pip.

Uso:
  bash scripts/maquina-limpa/p3-conteiner.sh [--imagem IMG]... [--saida DIR]
       [--dkms] [--bluez] [--ref REF]
AJUDA
}

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SAIDA="${TMPDIR:-/tmp}/hefesto-maquina-limpa/p3"
REF="HEAD"
IMAGENS=()
COM_DKMS=0
COM_BLUEZ=0

while (( $# )); do
    case "$1" in
        --imagem) IMAGENS+=("$2"); shift 2 ;;
        --saida)  SAIDA="$2"; shift 2 ;;
        --ref)    REF="$2"; shift 2 ;;
        --dkms)   COM_DKMS=1; shift ;;
        --bluez)  COM_BLUEZ=1; shift ;;
        -h|--help) _ajuda; exit 0 ;;
        *) printf 'argumento desconhecido: %s\n' "$1" >&2; exit 2 ;;
    esac
done
(( ${#IMAGENS[@]} )) || IMAGENS=(ubuntu:24.04 fedora:42 archlinux:latest debian:12)

command -v docker >/dev/null 2>&1 || { echo "falta o docker" >&2; exit 2; }
mkdir -p "${SAIDA}"
TARBALL="${SAIDA}/arvore.tgz"
git -C "${RAIZ}" archive --format=tar.gz -o "${TARBALL}" "${REF}"

DENTRO="${SAIDA}/p3-dentro.sh"
cat > "${DENTRO}" <<'EOF'
#!/bin/bash
# Roda DENTRO do contêiner, como root; quem instala é a usuária comum.
set -u
COM_DKMS="$1"; COM_BLUEZ="$2"; FONTES="$3"
mkdir -p /opt/hefesto && tar -xzf /arvore.tgz -C /opt/hefesto
. /etc/os-release
[ -n "${FONTES}" ] && bash /opt/hefesto/scripts/ci/instalar_como_usuaria.sh --fontes "${FONTES}" --so-fontes
case " ${ID} ${ID_LIKE:-} " in
  *" debian "*|*" ubuntu "*)
    apt-get update -qq && apt-get install -y -qq python3 python3-venv git sudo bash >/dev/null ;;
  *" fedora "*) dnf install -y -q python3 git sudo >/dev/null ;;
  *" arch "*) pacman -Sy --noconfirm --needed python git sudo >/dev/null ;;
esac
find / -xdev -newer /arvore.tgz -not -path '/proc/*' 2>/dev/null | sort > /tmp/antes-do-install.txt
HEFESTO_CI_FLAGS="--no-proton-pin" bash /opt/hefesto/scripts/ci/instalar_como_usuaria.sh
echo "rc_install=$?"
echo "--- avisos que a usuária viu:"
grep -E '^\s+aviso:|FALHA|\[FAIL\]|Reinicie' /tmp/install-como-usuaria.log || true
echo "--- versões (o constraints.txt manda):"
su - jogadora -c '/opt/hefesto/.venv/bin/python -m pip list 2>/dev/null' \
    | grep -iE '^(evdev|hidapi-usb|pydualsense|pydantic|PyGObject) ' || true
echo "--- doctor sem aparelho:"
su - jogadora -c 'bash /opt/hefesto/scripts/doctor.sh 2>&1' | grep -E '^\[(FAIL|WARN)\]' || true
find / -xdev -newer /arvore.tgz -not -path '/proc/*' 2>/dev/null | sort > /tmp/pos-install.txt
if [ "${COM_DKMS}" = 1 ]; then
  echo "--- cada módulo contra os headers desta distro (L6), o mesmo passo do CI:"
  bash /opt/hefesto/scripts/ci/instalar_como_usuaria.sh --so-dkms
  echo "rc_dkms_build=$? (1 = algum módulo não compila; o rc 77 de um módulo é o pino, de propósito)"
  k="$(ls /lib/modules | sort -V | tail -1)"
  b=/tmp/make-direto; rm -rf "$b"; cp -a /opt/hefesto/assets/dkms/hid-playstation "$b"
  make -C "/lib/modules/${k}/build" M="$b" modules >/tmp/make-direto.txt 2>&1 \
    || make -C "/usr/src/kernels/${k}" M="$b" modules >>/tmp/make-direto.txt 2>&1
  echo "rc_make_direto=$? (o fonte compila neste kernel, com ou sem o pino)"
  tail -5 /tmp/make-direto.txt
fi
if [ "${COM_BLUEZ}" = 1 ]; then
  echo "--- a receita do BlueZ (L2):"
  su - jogadora -c 'bash /opt/hefesto/scripts/construir_bluez_backport.sh' > /tmp/bluez.txt 2>&1
  echo "rc_bluez=$? (3 = faltam dependências de build, listadas)"
  tail -8 /tmp/bluez.txt
fi
echo "--- o que o uninstall deixa (M4):"
su - jogadora -c '/opt/hefesto/uninstall.sh --yes' > /tmp/uninstall.txt 2>&1
echo "rc_uninstall=$?"
find / -xdev -newer /arvore.tgz -not -path '/proc/*' 2>/dev/null | sort > /tmp/pos-uninstall.txt
comm -12 /tmp/pos-install.txt /tmp/pos-uninstall.txt | comm -23 - /tmp/antes-do-install.txt \
    | grep -vE '^/(tmp|var/(log|cache|lib/(apt|dpkg|dnf|pacman)))/|^/opt/hefesto' || true
EOF

rc_geral=0
for img in "${IMAGENS[@]}"; do
    nome="${img%%:*}"
    montagens=(-v "${TARBALL}:/arvore.tgz:ro" -v "${DENTRO}:/p3.sh:ro")
    fontes=""
    if [[ "${img}" == ubuntu:24.04 ]]; then
        fontes="pop"
        nome="pop"
    fi
    bluez=0
    [[ "${COM_BLUEZ}" -eq 1 && "${img}" == ubuntu:24.04 ]] && bluez=1
    printf 'P3 %s …\n' "${img}"
    docker run --rm "${montagens[@]}" "${img}" bash /p3.sh "${COM_DKMS}" "${bluez}" "${fontes}" \
        > "${SAIDA}/p3-${nome}.txt" 2>&1 || rc_geral=1
    printf '   %s\n' "$(grep -E '^rc_(install|uninstall)=' "${SAIDA}/p3-${nome}.txt" | tr '\n' ' ')"
    grep -q '^rc_install=0$' "${SAIDA}/p3-${nome}.txt" || rc_geral=1
done
printf 'relatos em %s\n' "${SAIDA}"
exit "${rc_geral}"
