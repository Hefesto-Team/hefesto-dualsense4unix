"""O renderizador das units systemd de usuário: UM dono para todo formato de instalação.

As units de `assets/` são modelos. O `ExecStart` do daemon e da janela aponta para
`%h/.local/bin/` (o que o `install.sh` nativo cria) e a da presença pede o Python
por `__PYTHON__`. Cada formato (`.deb`, Arch, Fedora, Nix, `daemon install-service`)
tem o seu próprio lugar para os binários, e cada um vestia o modelo à sua maneira:
a lista fechada com `sed` do `.deb`, a cópia às cegas do Fedora e do Nix (a unit
chegava com um caminho que não existe), a lista curta do Arch (sem a presença, que
a unit do daemon chama no `OnFailure`). Aqui a vestimenta é uma só, e ela RECUSA
entregar uma unit com marcador sobrando.

Só biblioteca padrão: os empacotadores o rodam como arquivo
(`python3 src/hefesto_dualsense4unix/utils/units_de_usuario.py --assets assets ...`),
sem o pacote instalado.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

NOME_DO_PRODUTO = "hefesto-dualsense4unix"

UNITS_DE_PACOTE: tuple[str, ...] = (
    f"{NOME_DO_PRODUTO}.service",
    f"{NOME_DO_PRODUTO}-gui-hotplug.service",
    f"{NOME_DO_PRODUTO}-presenca.service",
)

_BIN_NATIVO = f"%h/.local/bin/{NOME_DO_PRODUTO}"
_MARCADOR = re.compile(r"__[A-Z][A-Z_]*__")
_CAMINHO_DO_NATIVO = "%h/.local/"


class UnitComMarcadorSobrandoError(ValueError):
    """A unit renderizada ainda carrega um marcador ou o caminho do install nativo."""


def sobras(texto: str) -> list[str]:
    """O que ficou sem vestir: marcadores `__X__` e `%h/.local/` fora de comentário."""
    achadas: list[str] = []
    for linha in texto.splitlines():
        if linha.lstrip().startswith("#"):
            continue
        achadas.extend(_MARCADOR.findall(linha))
        if _CAMINHO_DO_NATIVO in linha:
            achadas.append(_CAMINHO_DO_NATIVO)
    return achadas


def renderizar(texto: str, *, bin_dir: str | Path, python: str | Path) -> str:
    """Veste o modelo: os binários em `bin_dir` e o Python em `python`.

    O prefixo `%h/.local/bin/hefesto-dualsense4unix` casa o CLI e o `-gui`.
    """
    base = str(bin_dir).rstrip("/") or "/"
    saida = texto.replace(_BIN_NATIVO, f"{base}/{NOME_DO_PRODUTO}".replace("//", "/"))
    saida = saida.replace("__PYTHON__", str(python))
    restos = sobras(saida)
    if restos:
        raise UnitComMarcadorSobrandoError(
            "a unit renderizada ainda tem: " + ", ".join(sorted(set(restos)))
        )
    return saida


def renderizar_para(
    assets: Path,
    saida: Path,
    *,
    bin_dir: str | Path,
    python: str | Path,
    nomes: Iterable[str] = UNITS_DE_PACOTE,
) -> list[Path]:
    """Renderiza cada unit de `nomes` de `assets/` para `saida/`. Falta de modelo é erro."""
    saida.mkdir(parents=True, exist_ok=True)
    escritas: list[Path] = []
    for nome in nomes:
        origem = assets / nome
        if not origem.is_file():
            raise FileNotFoundError(f"modelo de unit ausente: {origem}")
        destino = saida / nome
        destino.write_text(
            renderizar(origem.read_text(encoding="utf-8"), bin_dir=bin_dir, python=python),
            encoding="utf-8",
        )
        destino.chmod(0o644)
        escritas.append(destino)
    return escritas


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Renderiza as units systemd de usuário do Hefesto para um formato de pacote."
    )
    ap.add_argument("--assets", required=True, type=Path, help="a pasta assets/ com os modelos")
    ap.add_argument("--out", required=True, type=Path, help="onde gravar as units prontas")
    ap.add_argument("--bin-dir", required=True, help="onde o pacote põe os binários (/usr/bin)")
    ap.add_argument("--python", required=True, help="o Python que a unit da presença chama")
    ap.add_argument(
        "--unit", action="append", help="só esta unit (repetível); padrão: as de pacote"
    )
    args = ap.parse_args(argv)
    try:
        escritas = renderizar_para(
            args.assets,
            args.out,
            bin_dir=args.bin_dir,
            python=args.python,
            nomes=args.unit or UNITS_DE_PACOTE,
        )
    except (FileNotFoundError, UnitComMarcadorSobrandoError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    for caminho in escritas:
        print(caminho)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
