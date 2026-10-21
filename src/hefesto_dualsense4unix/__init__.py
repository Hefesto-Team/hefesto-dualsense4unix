"""Hefesto - DualSense4Unix — gerenciador DualSense para Linux."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # o mypy lê o nome declarado; um `__getattr__` visível a ele aceitaria qualquer atributo
    __version__: str
else:

    def __getattr__(nome: str) -> str:
        """A versão só se lê quando alguém pede (o `importlib.metadata` custa 27 ms no import).

        O fallback literal é o que `check_version_consistency.py` e o CI conferem contra o
        pyproject.
        """
        if nome != "__version__":
            raise AttributeError(f"module {__name__!r} has no attribute {nome!r}")
        from importlib.metadata import PackageNotFoundError, version

        try:
            __version__ = version("hefesto-dualsense4unix")
        except PackageNotFoundError:
            __version__ = "0.9.5"
        globals()["__version__"] = __version__
        return __version__


def _check_pydantic_v2() -> None:
    """Avisa se pydantic < 2 está instalado (BUG-DEB-SMOKE-PYDANTIC-V2-NOBLE-01).

    Ubuntu 22.04 (Jammy) e 24.04 (Noble) ainda empacotam python3-pydantic 1.x
    no apt. Hefesto - DualSense4Unix usa API v2 (ConfigDict) e falhará em runtime. Warning
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
            f"pydantic {pv_str} detectado; Hefesto - DualSense4Unix requer pydantic >= 2.0. "
            "Instale via: pip install --user 'pydantic>=2'.",
            ImportWarning,
            stacklevel=2,
        )


_check_pydantic_v2()
del _check_pydantic_v2
