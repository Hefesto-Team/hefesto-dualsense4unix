#!/usr/bin/env python3
"""O contrato da peça GDK: a sonda roda num prefixo de teste e cada prova vira uma linha JSON.

Compila a peça e a sonda (`assets/gdk-runtime/construir.sh`), põe uma DLL forjada ao lado do
exe da sonda, como a do usuário fica ao lado do exe do jogo, e roda a sonda com a receita do
Hefesto (`xgameruntime=b` e o `WINEDLLPATH` na pasta da peça). Julga as seis provas:

- `peca_carregada`: o processo carregou a peça (marca builtin no 0x40 e a exportação de identidade),
  não a forjada;
- `fila_nula`: o `XAsyncBegin` de fila nula entrega ao provedor uma cópia com a fila do processo;
- `sem_fila_do_processo`: depois do `SetCurrentProcessTaskQueue(NULL)`, 0x800701AB sem provedor;
- `duplicate_close`: cem pares num composto, e o `CreateComposite` sobre ele dá S_OK;
- `composto_de_composto`: o trabalho e a conclusão andam;
- `terminate_espera`: o `XTaskQueueTerminate(wait)` volta só depois da conclusão.

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
from collections.abc import Iterable
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
FONTE = RAIZ / "assets" / "gdk-runtime"
WINE_PADRAO = Path.home() / ".steam/steam/compatibilitytools.d/GE-Proton11-7-x86_64/files/bin/wine"

PROVAS = (
    "peca_carregada",
    "fila_nula",
    "sem_fila_do_processo",
    "duplicate_close",
    "composto_de_composto",
    "terminate_espera",
)

MORDIDAS: dict[str, tuple[str, str, str, str]] = {
    "V1": (
        "xgameruntime.c",
        "    data.async = &st->prov;\n    data.context = context;\n    hr = provider(OP_BEGIN, &data);",
        "    data.async = async;\n    data.context = context;\n    hr = provider(OP_BEGIN, &data);",
        "fila_nula",
    ),
    "V2": (
        "xgameruntime.c",
        "    if (queue_live(q)) {\n        InterlockedIncrement(&q->refs);\n        *out = q;",
        "    if (queue_live(q)) {\n        *out = q;",
        "duplicate_close",
    ),
    "marca": (
        "construir.sh",
        'marcar "$saida/xgameruntime.dll"\n',
        ": sem marca\n",
        "peca_carregada",
    ),
    "dllpath": ("", "", "", "peca_carregada"),
}

FORJADA_C = r"""
#include <windows.h>
__declspec(dllexport) const char *WINAPI HefestoPecaGdk(void) { return "forjada-ao-lado"; }
__declspec(dllexport) HRESULT WINAPI QueryApiImpl(const void *a, const void *b, void **o)
{ (void)a; (void)b; if (o) *o = 0; return E_FAIL; }
BOOL WINAPI DllMain(HINSTANCE h, DWORD r, LPVOID p) { (void)h; (void)r; (void)p; return TRUE; }
"""


def julgar(linhas: Iterable[str]) -> dict[str, bool]:
    """Cada prova -> passou. Prova que não apareceu conta como reprovada."""
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
    return {p: vistas.get(p, False) for p in PROVAS}


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
    env = {k: v for k, v in os.environ.items() if k not in ("DISPLAY", "WAYLAND_DISPLAY", "WINEDLLPATH")}
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
    if mordida and MORDIDAS[mordida][0]:
        arquivo, cura, quebrado, _ = MORDIDAS[mordida]
        alvo = src / arquivo
        alvo.write_text(quebrar(alvo.read_text(encoding="utf-8"), cura, quebrado), encoding="utf-8")
    saida = trabalho / "saida"
    env = dict(os.environ)
    if cc:
        env["CC"] = cc
    subprocess.run(["bash", str(src / "construir.sh"), str(saida)], env=env, check=True)
    (trabalho / "forjada.c").write_text(FORJADA_C, encoding="utf-8")
    subprocess.run([env.get("CC", "x86_64-w64-mingw32-gcc-posix"), "-shared", "-O2", "-s",
                    "-o", str(trabalho / "forjada.dll"), str(trabalho / "forjada.c")], env=env, check=True)
    return saida


def rodar(wine: Path, prefixo: Path, trabalho: Path, saida: Path, mordida: str | None) -> list[str]:
    pasta = trabalho / "wine"
    (pasta / "x86_64-windows").mkdir(parents=True)
    shutil.copy2(saida / "xgameruntime.dll", pasta / "x86_64-windows" / "xgameruntime.dll")
    jogo = trabalho / "jogo"
    jogo.mkdir()
    shutil.copy2(saida / "sonda-gdk.exe", jogo / "sonda-gdk.exe")
    shutil.copy2(trabalho / "forjada.dll", jogo / "xgameruntime.dll")
    env = ambiente_wine(prefixo)
    env["WINEDLLOVERRIDES"] = "xgameruntime=b;mscoree,mshtml,winemenubuilder.exe="
    if mordida != "dllpath":
        env["WINEDLLPATH"] = str(pasta)
    proc = subprocess.run([str(wine), "sonda-gdk.exe"], cwd=jogo, env=env, check=False, timeout=180,
                          capture_output=True, text=True, errors="replace")
    subprocess.run([str(wine.with_name("wineserver")), "-w"], env=env, check=False, timeout=120)
    return [linha.replace("\r", "") for linha in proc.stdout.splitlines()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--wine", type=Path, default=WINE_PADRAO)
    ap.add_argument("--prefixo", type=Path, help="prefixo de teste para reaproveitar (fora do HOME)")
    ap.add_argument("--cc", help="o x86_64-w64-mingw32-gcc-posix, se não está no PATH")
    ap.add_argument("--mordida", choices=sorted(MORDIDAS))
    ap.add_argument("--julgar", type=Path, help="só julga um arquivo de linhas JSON já gravado")
    ap.add_argument("--manter", action="store_true", help="não apaga a pasta de trabalho")
    args = ap.parse_args(argv)

    if args.julgar:
        linhas = args.julgar.read_text(encoding="utf-8").splitlines()
    else:
        if not args.wine.exists():
            print(f"sem o Wine em {args.wine}", file=sys.stderr)
            return 2
        trabalho = Path(tempfile.mkdtemp(prefix="peca-gdk-"))
        prefixo = prefixo_seguro(args.prefixo or trabalho / "pfx")
        try:
            preparar_prefixo(args.wine, prefixo)
            saida = construir(trabalho, args.mordida, args.cc)
            linhas = rodar(args.wine, prefixo, trabalho, saida, args.mordida)
        finally:
            if not args.manter:
                shutil.rmtree(trabalho, ignore_errors=True)
        for linha in linhas:
            print(linha)

    veredito = julgar(linhas)
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
