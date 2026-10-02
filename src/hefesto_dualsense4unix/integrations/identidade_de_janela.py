"""A `wm_class` que um jogo VAI anunciar — e o «não sei», que é resposta."""

from __future__ import annotations

import json
import re
from pathlib import Path

__all__ = [
    "PREFIXO_UMU",
    "classe_de_janela",
    "classe_do_umu_id",
    "umu_por_chave_do_heroic",
]

PREFIXO_UMU = "umu-"

_UMU_RE = re.compile(rf"^{re.escape(PREFIXO_UMU)}(\d+)$", re.IGNORECASE)


def classe_do_umu_id(umu_id: str) -> str:
    """`umu-1088850` -> `steam_app_1088850`. `""` quando não é um id numérico."""
    achado = _UMU_RE.match(str(umu_id or "").strip())
    return f"steam_app_{achado.group(1)}" if achado else ""


def umu_por_chave_do_heroic(cache: Path) -> dict[str, str]:
    """`{app_name: "umu-<N>"}` lido do `store_cache/umu.json` do Heroic."""
    try:
        dado = json.loads((cache / "umu.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(dado, dict):
        return {}
    mapa: dict[str, str] = {}
    for chave, valor in dado.items():
        if not isinstance(valor, str) or str(chave).startswith("__"):
            continue
        crua = str(chave)
        nua = crua.split("_", 1)[1] if "_" in crua else crua
        mapa[nua] = valor
    return mapa


_EXTENSAO_DE_WINDOWS = ".exe"


def _palpite_do_executavel(executavel: str) -> str:
    """O basename do executável, **só quando ele não é um `.exe`**."""
    nome = str(executavel or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not nome or nome.lower().endswith(_EXTENSAO_DE_WINDOWS):
        return ""
    return nome


def classe_de_janela(
    *, umu_id: str = "", appid_da_steam: str = "", executavel: str = "",
) -> str:
    """A `wm_class` que este jogo vai anunciar — ou `""` quando não se sabe."""
    do_umu = classe_do_umu_id(umu_id)
    if do_umu:
        return do_umu
    numero = str(appid_da_steam or "").strip()
    if numero.isdigit():
        return f"steam_app_{numero}"
    return _palpite_do_executavel(executavel)
