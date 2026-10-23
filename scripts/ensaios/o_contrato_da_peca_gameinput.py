#!/usr/bin/env python3
"""O contrato do GameInput da casa: a sonda pede a vibração como o Wwise pede, num prefixo de teste.

Compila as peças e a sonda (`assets/gdk-runtime/construir.sh`), põe a xgameruntime em
`<pasta>/x86_64-windows/` e o gameinput em `<pasta>/nativa/`, como o install põe, e roda a sonda
com a receita do Hefesto (`xgameruntime=b`, `gameinput=n,b` e o `WINEDLLPATH` na pasta). Ao lado
do exe fica uma xgameruntime forjada, como a do jogo fica ao lado do exe dele: o Wine só troca pela
builtin a DLL que achou no caminho de busca. O
aparelho é um dublê: dois arquivos comuns, um do cabo (`.usb`) e um do rádio (`.bt`), que recebem
os reports de saída, cada um com um report de entrada ao lado (`.entrada`). Nenhum hidraw,
uinput, uhid, gadget ou rádio de verdade. Julga:

- da sonda: `preload` (o LoadLibrary("GameInput.dll") do jogo recebe a peça da casa), `qi_v2`,
  `aparelhos` (a enumeração bloqueante lista os dois), `motores` (o supportedRumbleMotors do v0
  no 0x6c), `device_id` (estável, igual no v0 e no v2) e `leitura` (o Gamepad do cabo e do rádio);
- dos bytes que chegaram ao dublê: `bytes_usb` (o report 0x02 com flag0 = 0x03, fraco e forte no
  lugar), `bytes_bt` (o 0x31 de 78 bytes com o CRC32 certo), `reenvio` (o rumble parado se
  repete antes dos 3 s do pad virtual) e `zero_no_fim` (o zero chega uma vez só);
- de uma segunda rodada, sem DualSense: `sem_aparelho` (a peça carregada responde E_NOTIMPL, como
  o GameInput do Proton, e o jogo que lê a entrada pelo GameInput cai na XInput como hoje).

`--mordida` quebra a cura numa cópia do fonte (nunca no repo) e confere que a prova dela reprova.
O prefixo é sempre de teste, fora do HOME: nunca o do jogo, nunca o `~/.wine`. Nada abre janela.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zlib
from collections.abc import Iterable
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
FONTE = RAIZ / "assets" / "gdk-runtime"
WINE_PADRAO = Path.home() / ".steam/steam/compatibilitytools.d/GE-Proton11-7-x86_64/files/bin/wine"

PROVAS_DA_SONDA = ("preload", "qi_v2", "aparelhos", "motores", "device_id", "leitura")
PROVAS_DOS_BYTES = ("bytes_usb", "bytes_bt", "reenvio", "zero_no_fim")
PROVAS = PROVAS_DA_SONDA + PROVAS_DOS_BYTES + ("sem_aparelho",)

#: O HRESULT do GameInputCreate do Proton fora do KCD2 (E_NOTIMPL): o que o jogo recebe hoje.
E_NOTIMPL = "80004001"

#: Cada mordida: (arquivo, trecho da cura, trecho quebrado) e a prova que tem de reprovar.
MORDIDAS: dict[str, tuple[str, str, str, str]] = {
    "qi-v2": (
        "gameinput.c",
        "    if (guid_eq(riid, &IID_v2_IGameInput)) { *out = &g_gi.i2; return S_OK; }\n",
        "",
        "qi_v2",
    ),
    "motores": (
        "gameinput.c",
        "#define MOTORES_DE_RUMBLE (RUMBLE_LOW | RUMBLE_HIGH | RUMBLE_LT | RUMBLE_RT)\n",
        "#define MOTORES_DE_RUMBLE 0u\n",
        "motores",
    ),
    "rumble": (
        "gameinput.c",
        "    if (fraco != a->fraco || forte != a->forte) {\n",
        "    if (0) {\n",
        "bytes_usb",
    ),
    "flags": (
        "gameinput.c",
        "#define FLAG0_VIBRACAO 0x03\n",
        "#define FLAG0_VIBRACAO 0x0F\n",
        "bytes_usb",
    ),
    "leitura": (
        "gameinput.c",
        "    *state = l->pad;\n",
        "    memset(state, 0, sizeof *state);\n",
        "leitura",
    ),
    "preload": (
        "xgameruntime.c",
        "            HMODULE h = LoadLibraryW(dos);\n",
        "            HMODULE h = NULL;\n",
        "preload",
    ),
    "reenvio": (
        "gameinput.c",
        "            if ((a->fraco || a->forte) && GetTickCount64() - a->ultima_escrita_ms >= REENVIO_MS)\n",
        "            if (0)\n",
        "reenvio",
    ),
    "crc": (
        "gameinput.c",
        "        crc = crc32_continua(crc32_continua(0, &semente, 1), r, 74);\n",
        "        crc = crc32_continua(0, r, 74); (void)semente;\n",
        "bytes_bt",
    ),
    "ordem": (
        "gameinput.c",
        "    forte = p ? para_byte(p->lowFrequency) : 0;\n",
        "    forte = p ? para_byte(p->highFrequency) : 0;\n",
        "bytes_usb",
    ),
    "sem-aparelho": (
        "gameinput.c",
        "    if (iniciar()) return 0;\n",
        "    iniciar();\n    return 0;\n",
        "sem_aparelho",
    ),
}

#: O que a sonda manda: o cabo a 1,0 no forte e 0,5 no fraco; o rádio a 0,25 e 0,75.
USB_FRACO, USB_FORTE = 0x80, 0xFF
BT_FRACO, BT_FORTE = 0xBF, 0x40

#: A xgameruntime que o jogo traz ao lado do exe; o Wine a troca pela builtin da peça.
FORJADA_C = r"""
#include <windows.h>
__declspec(dllexport) const char *WINAPI HefestoPecaGdk(void) { return "forjada-ao-lado"; }
BOOL WINAPI DllMain(HINSTANCE h, DWORD r, LPVOID p) { (void)h; (void)r; (void)p; return TRUE; }
"""

#: Os reports de entrada do dublê. O cabo: direcional esquerdo à direita, R2 no fundo e a cruz.
#: O rádio: direcional esquerdo à esquerda, o hat para cima e o triângulo.
ENTRADA_USB = bytes([0x01, 0xFF, 0x80, 0x80, 0x80, 0x00, 0xFF, 0x01, 0x08 | 0x20, 0x00, 0x00]) + bytes(53)
ENTRADA_BT = bytes([0x31, 0x00, 0x00, 0x80, 0x80, 0x80, 0x00, 0x00, 0x01, 0x00 | 0x80, 0x00, 0x00]) + bytes(66)


def julgar(linhas: Iterable[str]) -> dict[str, bool]:
    """Cada prova da sonda -> passou. Prova que não apareceu conta como reprovada."""
    vistas: dict[str, bool] = {}
    for linha in linhas:
        linha = linha.strip()
        if not linha.startswith("{"):
            continue
        try:
            obj = json.loads(linha)
        except json.JSONDecodeError:
            continue
        prova = obj.get("prova")
        if isinstance(prova, str):
            vistas[prova] = obj.get("ok") is True
    return {p: vistas.get(p, False) for p in PROVAS_DA_SONDA}


def julgar_sem_aparelho(linhas: Iterable[str]) -> bool:
    """Sem DualSense, a peça da casa está no processo e o GameInputCreate devolve E_NOTIMPL."""
    vistas: dict[str, dict[str, object]] = {}
    for linha in linhas:
        linha = linha.strip()
        if not linha.startswith("{"):
            continue
        try:
            obj = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(obj.get("prova"), str):
            vistas[str(obj["prova"])] = obj
    preload, qi = vistas.get("preload", {}), vistas.get("qi_v2", {})
    return preload.get("ok") is True and qi.get("ok") is False and qi.get("hr") == E_NOTIMPL


def _pedacos(dados: bytes, tamanho: int) -> list[bytes]:
    if not dados or len(dados) % tamanho:
        return []
    return [dados[i:i + tamanho] for i in range(0, len(dados), tamanho)]


def crc_do_radio(report: bytes) -> bool:
    """O 0x31 leva o CRC32 (semente 0xA2) dos 74 primeiros bytes nos quatro últimos, little-endian."""
    if len(report) != 78:
        return False
    return zlib.crc32(b"\xa2" + report[:74]) == int.from_bytes(report[74:], "little")


def julgar_bytes(usb: bytes, bt: bytes) -> dict[str, bool]:
    """Os reports que chegaram ao aparelho dublê."""
    cabo = _pedacos(usb, 48)
    radio = _pedacos(bt, 78)
    esperado_usb = bytes([0x02, 0x03, 0x00, USB_FRACO, USB_FORTE]) + bytes(43)
    bytes_usb = bool(cabo) and cabo[0] == esperado_usb
    bytes_bt = (
        bool(radio)
        and all(crc_do_radio(r) for r in radio)
        and radio[0][0] == 0x31
        and radio[0][2] == 0x10
        and radio[0][3:7] == bytes([0x03, 0x00, BT_FRACO, BT_FORTE])
        and not any(radio[0][7:74])
    )
    reenvio = bool(cabo) and sum(1 for r in cabo if r == esperado_usb) >= 2

    def zero(r: bytes, i: int) -> bool:
        return r[i] == 0 and r[i + 1] == 0

    zero_no_fim = (
        bool(cabo) and bool(radio)
        and zero(cabo[-1], 3) and sum(1 for r in cabo if zero(r, 3)) == 1
        and zero(radio[-1], 5) and sum(1 for r in radio if zero(r, 5)) == 1
    )
    return {"bytes_usb": bytes_usb, "bytes_bt": bytes_bt, "reenvio": reenvio, "zero_no_fim": zero_no_fim}


def quebrar(texto: str, cura: str, quebrado: str) -> str:
    """Troca o trecho da cura UMA vez; se ele não está lá, a mordida não mede nada e reprova."""
    if texto.count(cura) != 1:
        raise SystemExit(f"mordida: o trecho da cura aparece {texto.count(cura)} vez(es), não 1")
    return texto.replace(cura, quebrado)


def prefixo_seguro(caminho: Path) -> Path:
    """O prefixo de teste mora no /tmp ou no TMPDIR, nunca no HOME (onde estão os prefixos reais)."""
    p = caminho.resolve()
    home = Path.home().resolve()
    tmp = Path(tempfile.gettempdir()).resolve()
    if p == home or home in p.parents or not (p == tmp or tmp in p.parents or Path("/tmp") in p.parents):
        raise SystemExit(f"recuso o prefixo {p}: só prefixo de teste fora do HOME")
    return p


def ambiente_wine(prefixo: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if k not in ("DISPLAY", "WAYLAND_DISPLAY", "WINEDLLPATH", "HEFESTO_GAMEINPUT_DUBLE_DE_TESTE")}
    env.update(WINEPREFIX=str(prefixo), WINEDEBUG="-all", WINEARCH="win64")
    return env


def preparar_prefixo(wine: Path, prefixo: Path) -> None:
    if (prefixo / "system.reg").exists():
        return
    env = ambiente_wine(prefixo)
    env["WINEDLLOVERRIDES"] = "mscoree,mshtml,winemenubuilder.exe="
    subprocess.run([str(wine), "wineboot", "-i"], env=env, check=False, timeout=300,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([str(wine.with_name("wineserver")), "-w"], env=env, check=False, timeout=120)


def construir(trabalho: Path, mordida: str | None, cc: str | None) -> Path:
    src = trabalho / "fonte"
    shutil.copytree(FONTE, src)
    if mordida:
        arquivo, cura, quebrado, _ = MORDIDAS[mordida]
        alvo = src / arquivo
        alvo.write_text(quebrar(alvo.read_text(encoding="utf-8"), cura, quebrado), encoding="utf-8")
    saida = trabalho / "saida"
    env = dict(os.environ)
    if cc:
        env["CC"] = cc
    subprocess.run(["bash", str(src / "construir.sh"), str(saida)], env=env, check=True,
                   stdout=subprocess.DEVNULL)
    (trabalho / "forjada.c").write_text(FORJADA_C, encoding="utf-8")
    subprocess.run([env.get("CC", "x86_64-w64-mingw32-gcc-posix"), "-shared", "-O2", "-s",
                    "-o", str(saida / "forjada.dll"), str(trabalho / "forjada.c")], env=env, check=True)
    return saida


def caminho_dos(p: Path) -> str:
    return "Z:" + str(p).replace("/", "\\")


def rodar(
    wine: Path, prefixo: Path, trabalho: Path, saida: Path, *, com_aparelhos: bool = True
) -> tuple[list[str], bytes, bytes]:
    # O mesmo arranjo do install: a xgameruntime em <pasta>/x86_64-windows/, o gameinput em
    # <pasta>/nativa/, o WINEDLLPATH na <pasta>. Sem aparelhos, o dublê aponta para um arquivo
    # que não existe: a peça não lista nada, como numa máquina sem DualSense.
    trabalho = trabalho / ("com" if com_aparelhos else "sem")
    pasta = trabalho / "wine"
    (pasta / "x86_64-windows").mkdir(parents=True)
    (pasta / "nativa").mkdir()
    shutil.copy2(saida / "xgameruntime.dll", pasta / "x86_64-windows" / "xgameruntime.dll")
    shutil.copy2(saida / "gameinput.dll", pasta / "nativa" / "gameinput.dll")
    jogo = trabalho / "jogo"
    jogo.mkdir()
    shutil.copy2(saida / "sonda-gameinput.exe", jogo / "sonda-gameinput.exe")
    shutil.copy2(saida / "forjada.dll", jogo / "xgameruntime.dll")
    aparelhos = trabalho / "aparelhos"
    aparelhos.mkdir()
    usb, bt = aparelhos / "pad1.usb", aparelhos / "pad2.bt"
    for arquivo, entrada in ((usb, ENTRADA_USB), (bt, ENTRADA_BT)):
        arquivo.write_bytes(b"")
        arquivo.with_name(arquivo.name + ".entrada").write_bytes(entrada)
    env = ambiente_wine(prefixo)
    env["WINEDLLOVERRIDES"] = "xgameruntime=b;gameinput=n,b;mscoree,mshtml,winemenubuilder.exe="
    env["WINEDLLPATH"] = str(pasta)
    env["HEFESTO_GAMEINPUT_DUBLE_DE_TESTE"] = (
        f"{caminho_dos(usb)};{caminho_dos(bt)}" if com_aparelhos
        else caminho_dos(aparelhos / "nenhum.usb")
    )
    proc = subprocess.run([str(wine), "sonda-gameinput.exe"], cwd=jogo, env=env, check=False, timeout=180,
                          capture_output=True, text=True, errors="replace")
    subprocess.run([str(wine.with_name("wineserver")), "-w"], env=env, check=False, timeout=120)
    linhas = [linha.replace("\r", "") for linha in proc.stdout.splitlines()]
    return linhas, usb.read_bytes(), bt.read_bytes()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--wine", type=Path, default=WINE_PADRAO)
    ap.add_argument("--prefixo", type=Path, help="prefixo de teste para reaproveitar (fora do HOME)")
    ap.add_argument("--cc", help="o x86_64-w64-mingw32-gcc-posix, se não está no PATH")
    ap.add_argument("--mordida", choices=sorted(MORDIDAS))
    ap.add_argument("--manter", action="store_true", help="não apaga a pasta de trabalho")
    args = ap.parse_args(argv)

    if not args.wine.exists():
        print(f"sem o Wine em {args.wine}", file=sys.stderr)
        return 2
    trabalho = Path(tempfile.mkdtemp(prefix="peca-gameinput-"))
    prefixo = prefixo_seguro(args.prefixo or trabalho / "pfx")
    try:
        preparar_prefixo(args.wine, prefixo)
        saida = construir(trabalho, args.mordida, args.cc)
        linhas, usb, bt = rodar(args.wine, prefixo, trabalho, saida)
        sem, _, _ = rodar(args.wine, prefixo, trabalho, saida, com_aparelhos=False)
    finally:
        if args.manter:
            print(f"pasta de trabalho: {trabalho}")
        else:
            shutil.rmtree(trabalho, ignore_errors=True)
    for linha in linhas:
        print(linha)
    print(f"cabo: {len(usb)} B; rádio: {len(bt)} B")
    if usb:
        print(f"cabo, o primeiro report: {usb[:8].hex(' ')}")
    if bt:
        print(f"rádio, o primeiro report: {bt[:8].hex(' ')}")

    for linha in sem:
        print(f"sem aparelho: {linha}")
    veredito = {**julgar(linhas), **julgar_bytes(usb, bt), "sem_aparelho": julgar_sem_aparelho(sem)}
    for prova, ok in veredito.items():
        print(f"{'PASSA' if ok else 'REPROVA'}  {prova}")
    if args.mordida:
        alvo = MORDIDAS[args.mordida][3]
        morde = not veredito[alvo]
        print(f"mordida {args.mordida}: a prova {alvo} {'reprovou (morde)' if morde else 'PASSOU (não morde)'}")
        return 0 if morde else 1
    return 0 if all(veredito.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
