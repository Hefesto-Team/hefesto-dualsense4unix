"""Hefesto — daemon Linux de gatilhos adaptativos para DualSense."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("hefesto")
except PackageNotFoundError:
    # Fallback para instalações sem metadata registrada
    # (.deb via build_deb.sh faz cp -r, não pip install — METADATA ausente).
    # Mantenha sincronizado com pyproject.toml [project].version a cada bump.
    # Regressão coberta por CHORE-VERSION-SYNC-GATE-01 (enfileirada).
    __version__ = "2.2.1"
