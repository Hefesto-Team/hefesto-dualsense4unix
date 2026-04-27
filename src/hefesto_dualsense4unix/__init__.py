"""Hefesto - Dualsense4Unix — daemon Linux de gatilhos adaptativos para DualSense."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("hefesto-dualsense4unix")
except PackageNotFoundError:
    # Fallback para instalações sem metadata registrada
    # (.deb via build_deb.sh faz cp -r, não pip install — METADATA ausente).
    # Mantenha sincronizado com pyproject.toml [project].version a cada bump.
    # Regressão coberta pelo gate version-sync em .github/workflows/ci.yml
    # (CHORE-VERSION-SYNC-GATE-01, MERGED).
    __version__ = "3.0.0"


def _check_pydantic_v2() -> None:
    """Avisa se pydantic < 2 está instalado (BUG-DEB-SMOKE-PYDANTIC-V2-NOBLE-01).

    Ubuntu 22.04 (Jammy) e 24.04 (Noble) ainda empacotam python3-pydantic 1.x
    no apt. Hefesto - Dualsense4Unix usa API v2 (ConfigDict) e falhará em runtime. Warning
    ImportWarning aqui orienta o usuário antes do crash.
    """
    try:
        import pydantic
    except ImportError:
        return
    pv_str = getattr(pydantic, "VERSION", "") or getattr(pydantic, "__version__", "")
    if not pv_str:
        return
    major = pv_str.split(".", 1)[0]
    if major.isdigit() and int(major) < 2:
        import warnings

        warnings.warn(
            f"pydantic {pv_str} detectado; Hefesto - Dualsense4Unix requer pydantic >= 2.0. "
            "Instale via: pip install --user 'pydantic>=2'.",
            ImportWarning,
            stacklevel=2,
        )


_check_pydantic_v2()
del _check_pydantic_v2
