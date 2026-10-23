#!/usr/bin/env bash
# A peça GDK do Hefesto, o GameInput da casa e as sondas deles, compilados de forma reprodutível.
#
#   construir.sh <saída>             compila xgameruntime.dll, gameinput.dll, sonda-gdk.exe e
#                                    sonda-gameinput.exe em <saída>, marca a xgameruntime como
#                                    builtin do Wine e imprime o sha256 de cada um
#   construir.sh <saída> --conferir  idem, e reprova se o sha256 não bate com o pino.txt
#   construir.sh --marcar <dll>      só escreve a marca builtin numa DLL já compilada
#
# O Wine só carrega como builtin (o `xgameruntime=b` da receita) o PE que traz
# «Wine builtin DLL\0» no offset 0x40 (medido no GE-Proton11-7). A marca se escreve aqui,
# sem winebuild, para o CI e a máquina de quem usa saírem com o mesmo binário. O gameinput.dll
# não leva marca: ele entra como nativa (gameinput=n,b), carregado pelo caminho inteiro.
# O compilador é o x86_64-w64-mingw32-gcc-posix do Ubuntu 24.04 (o CI usa o mesmo).
set -euo pipefail

aqui="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CC="${CC:-x86_64-w64-mingw32-gcc-posix}"
MARCA='Wine builtin DLL'

marcar() {
    local dll="$1" mz lfanew
    mz="$(head -c 2 "$dll")"
    [ "$mz" = "MZ" ] || { echo "construir: $dll não é um PE" >&2; return 1; }
    lfanew=$(od -An -t u4 -j 60 -N 4 "$dll" | tr -d ' ')
    # A marca ocupa 0x40..0x50; o cabeçalho PE tem de começar depois dela.
    if [ "$lfanew" -lt 81 ]; then
        echo "construir: o cabeçalho PE de $dll começa em $lfanew e a marca o cobriria" >&2
        return 1
    fi
    printf '%s\0' "$MARCA" | dd of="$dll" bs=1 seek=64 conv=notrunc status=none
}

sha() { sha256sum "$1" | cut -d' ' -f1; }

pino() { sed -n "s/^$1=//p" "$aqui/pino.txt"; }

if [ "${1:-}" = "--marcar" ]; then
    marcar "${2:?construir: falta a DLL}"
    exit 0
fi

saida="${1:?uso: construir.sh <saída> [--conferir]}"
conferir="${2:-}"
mkdir -p "$saida"

# Sem data, sem caminho da máquina e sem símbolos: o mesmo fonte dá o mesmo binário.
flags=(-O2 -s -Wall "-Wl,--no-insert-timestamp" "-Wl,--disable-auto-image-base" "-ffile-prefix-map=$aqui=." -fno-ident)
( cd "$aqui" && "$CC" -shared "${flags[@]}" -o "$saida/xgameruntime.dll" xgameruntime.c )
( cd "$aqui" && "$CC" "${flags[@]}" -o "$saida/sonda-gdk.exe" sonda-gdk.c )
( cd "$aqui" && "$CC" -shared "${flags[@]}" -o "$saida/gameinput.dll" gameinput.c -lhid -lsetupapi )
( cd "$aqui" && "$CC" "${flags[@]}" -o "$saida/sonda-gameinput.exe" sonda-gameinput.c )
marcar "$saida/xgameruntime.dll"

dll_sha="$(sha "$saida/xgameruntime.dll")"
sonda_sha="$(sha "$saida/sonda-gdk.exe")"
gi_sha="$(sha "$saida/gameinput.dll")"
echo "xgameruntime.dll sha256=$dll_sha"
echo "sonda-gdk.exe sha256=$sonda_sha"
echo "gameinput.dll sha256=$gi_sha"
echo "sonda-gameinput.exe sha256=$(sha "$saida/sonda-gameinput.exe")"

if [ "$conferir" = "--conferir" ]; then
    falhou=0
    [ "$dll_sha" = "$(pino sha256)" ] || { echo "construir: a DLL não bate com o pino ($(pino sha256))" >&2; falhou=1; }
    [ "$sonda_sha" = "$(pino sonda_sha256)" ] || { echo "construir: a sonda não bate com o pino ($(pino sonda_sha256))" >&2; falhou=1; }
    [ "$gi_sha" = "$(pino gameinput_sha256)" ] || { echo "construir: o gameinput.dll não bate com o pino ($(pino gameinput_sha256))" >&2; falhou=1; }
    exit "$falhou"
fi
