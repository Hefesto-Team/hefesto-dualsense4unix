#!/usr/bin/env python3
"""Portão: O GTK FICA SÓ NA MOLDURA E NA BANDEJA.

A janela GTK antiga saiu em 06/09/2026 (D-0609-GTK-LEVA-INTEIRA). Sobrou o GTK em
duas pontas que o produto usa de verdade: a MOLDURA da interface (a janela do
WebKit e os pilotos que a dirigem) e a BANDEJA. Todo o resto — a lógica de
`app/actions/`, o daemon, a linha de comando — roda sem o `gi`, e por isso se
testa sem ele.

Reprova, nomeando `arquivo:linha`, o `from gi.repository import Gtk/Gdk/WebKit2`, o
`import gi.repository.Gtk/Gdk/WebKit2` e o `gi.require_version("Gtk"/"Gdk"/"WebKit2", ...)`
(também como `require_version`, puxado por `from gi import`) em
qualquer arquivo de `src/hefesto_dualsense4unix/` que não esteja em
`DONOS_DO_GTK` ou nos `PADROES_DOS_PILOTOS`. A lista é a fonte, com o motivo de
cada entrada, e ela não envelhece calada: entrada cujo arquivo sumiu, ou que já
não importa Gtk/Gdk, também reprova.

O que fica de fora de propósito: `GLib`, `Gio` e `GdkPixbuf` (não são widget), e o
import dinâmico por `__import__`, que só a bandeja usa para sondar o que existe.

Uso:
    scripts/check_o_gtk_fica_na_moldura.py            confere a árvore deste script
    scripts/check_o_gtk_fica_na_moldura.py --raiz D   confere a árvore D (a mordida usa)
    scripts/check_o_gtk_fica_na_moldura.py --listar   a lista das duas pontas, com o motivo
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PACOTE = "src/hefesto_dualsense4unix"

#: Os módulos do GTK que fazem widget e janela. O `WebKit2` carrega o `Gtk` junto.
MODULOS_DE_WIDGET = frozenset({"Gtk", "Gdk", "WebKit2"})

#: `gi.require_version(...)` e o `require_version(...)` puxado por `from gi import`.
_PEDIDOS_DE_VERSAO = frozenset({"gi.require_version", "require_version"})

#: Os donos do GTK, relativos a `src/hefesto_dualsense4unix/`, cada um com o motivo.
DONOS_DO_GTK: dict[str, str] = {
    # A MOLDURA da interface.
    "interface/janela.py": "moldura: a janela do WebKit, a barra, o tema e a área de transferência",
    "interface/tema_da_sessao.py": "moldura: o tema e a barra da sessão, que só a janela adota",
    "interface/abrir.py": "moldura: o lançador que abre a janela e sobe a bandeja",
    "interface/ver.py": "moldura: o visor de uma página dentro do WebKit",
    "interface/hefesto_vivo.py": "moldura: o piloto das dez abas",
    # A BANDEJA.
    "app/tray.py": "bandeja: o ícone e o menu da área de notificação",
    "cli/cmd_tray.py": "bandeja: o comando que a sobe e sonda o que a sessão oferece",
}

#: Os pilotos de uma aba só, que dirigem o WebKit por dentro: nascem e morrem com a moldura.
PADROES_DOS_PILOTOS: dict[str, str] = {
    "interface/*_vivo.py": "moldura: piloto de uma aba (dirige o WebKit por dentro)",
    "interface/*_vivos.py": "moldura: piloto de uma aba (dirige o WebKit por dentro)",
    "interface/*_viva.py": "moldura: piloto de uma aba (dirige o WebKit por dentro)",
    "interface/*_vivas.py": "moldura: piloto de uma aba (dirige o WebKit por dentro)",
}


def _nome_do_modulo(no: ast.expr) -> str | None:
    """`gi.repository.Gtk` -> `gi.repository.Gtk`; outra coisa -> `None`."""
    partes: list[str] = []
    while isinstance(no, ast.Attribute):
        partes.append(no.attr)
        no = no.value
    if isinstance(no, ast.Name):
        partes.append(no.id)
        return ".".join(reversed(partes))
    return None


def _widget_de_modulo(nome: str) -> str | None:
    """`gi.repository.Gtk[.x]` -> `Gtk`; qualquer outro módulo -> `None`."""
    partes = nome.split(".")
    if partes[:2] == ["gi", "repository"] and len(partes) > 2 and partes[2] in MODULOS_DE_WIDGET:
        return partes[2]
    return None


def importacoes_de_widget(codigo: str) -> list[tuple[int, str]]:
    """`(linha, o que importa)` de cada Gtk/Gdk que o código puxa do `gi`."""
    achados: list[tuple[int, str]] = []
    for no in ast.walk(ast.parse(codigo)):
        if isinstance(no, ast.ImportFrom) and no.module == "gi.repository":
            achados += [(no.lineno, f"from gi.repository import {a.name}")
                        for a in no.names if a.name in MODULOS_DE_WIDGET]
        elif isinstance(no, ast.ImportFrom) and no.module and _widget_de_modulo(no.module):
            achados.append((no.lineno, f"from {no.module} import …"))
        elif isinstance(no, ast.Import):
            achados += [(no.lineno, f"import {a.name}")
                        for a in no.names if _widget_de_modulo(a.name)]
        elif isinstance(no, ast.Call) and no.args and _nome_do_modulo(no.func) in _PEDIDOS_DE_VERSAO:
            primeiro = no.args[0]
            if isinstance(primeiro, ast.Constant) and primeiro.value in MODULOS_DE_WIDGET:
                achados.append((no.lineno, f'gi.require_version("{primeiro.value}", …)'))
    return sorted(achados)


def _e_dono(relativo: str) -> bool:
    if relativo in DONOS_DO_GTK:
        return True
    return any(fnmatch.fnmatchcase(relativo, padrao) for padrao in PADROES_DOS_PILOTOS)


def conferir(raiz: Path) -> list[str]:
    """As falhas da árvore `raiz`, uma frase por falha."""
    base = raiz / PACOTE
    falhas: list[str] = []
    que_importam: set[str] = set()
    for arquivo in sorted(base.rglob("*.py")):
        relativo = arquivo.relative_to(base).as_posix()
        try:
            achados = importacoes_de_widget(arquivo.read_text(encoding="utf-8"))
        except SyntaxError as erro:
            falhas.append(f"{PACOTE}/{relativo}:{erro.lineno or 0}: não abre como Python ({erro.msg})")
            continue
        if achados:
            que_importam.add(relativo)
        if achados and not _e_dono(relativo):
            for linha, o_que in achados:
                falhas.append(
                    f"{PACOTE}/{relativo}:{linha}: `{o_que}` fora das duas pontas "
                    "(moldura e bandeja); a lógica roda sem o GTK"
                )
    for relativo in sorted(DONOS_DO_GTK):
        if not (base / relativo).is_file():
            falhas.append(f"DONOS_DO_GTK: `{relativo}` não existe mais; tire a entrada da lista")
        elif relativo not in que_importam:
            falhas.append(f"DONOS_DO_GTK: `{relativo}` já não importa Gtk nem Gdk; tire a entrada da lista")
    return falhas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raiz", type=Path, default=RAIZ, help="a árvore a conferir")
    ap.add_argument("--listar", action="store_true", help="imprime as duas pontas, com o motivo")
    args = ap.parse_args(argv)
    if args.listar:
        for relativo, motivo in {**DONOS_DO_GTK, **PADROES_DOS_PILOTOS}.items():
            print(f"{relativo}\t{motivo}")
        return 0
    falhas = conferir(args.raiz)
    if falhas:
        print("REPROVADO: o GTK saiu das duas pontas (a moldura e a bandeja).")
        for falha in falhas:
            print(f"  {falha}")
        return 1
    print(f"OK: o GTK mora só na moldura e na bandeja ({len(DONOS_DO_GTK)} arquivos e "
          f"{len(PADROES_DOS_PILOTOS)} padrões de piloto).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
