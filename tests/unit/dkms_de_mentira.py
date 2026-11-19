"""O ``.ko`` que o DKMS instalou, de mentira: o arquivo que o ``modinfo`` resolve e a cópia
igual que a árvore do DKMS guarda em ``<pacote>/kernel-<kernel>-<arch>/module/``."""
from __future__ import annotations

from pathlib import Path


def ko_do_dkms(
    raiz: Path,
    arvore: Path,
    pacote: str,
    arquivo: str,
    *,
    destino: str = "updates/dkms",
    kernel: str = "k",
) -> Path:
    """Escreve o ``.ko`` em ``<raiz>/lib/modules/<kernel>/<destino>`` e a cópia na ``arvore``."""
    ko = raiz / "lib" / "modules" / kernel / destino / arquivo
    guardado = arvore / pacote / "1.0.0" / kernel / "x86_64" / "module" / arquivo
    for caminho in (ko, guardado):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(f"o {arquivo} do Hefesto".encode())
    ligacao = arvore / pacote / f"kernel-{kernel}-x86_64"
    if not ligacao.is_symlink():
        ligacao.symlink_to(f"1.0.0/{kernel}/x86_64")
    return ko
