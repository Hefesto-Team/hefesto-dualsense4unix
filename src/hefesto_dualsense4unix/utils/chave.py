"""A chave que desliga um Hefesto por completo — e o religa."""
from __future__ import annotations

from pathlib import Path

NOME_DO_ARQUIVO = "DESLIGADO-pela-chave.flag"


def caminho_da_chave(config_dir: Path | None = None) -> Path:
    """Onde a chave mora: no ``config_dir()`` do app."""
    if config_dir is None:
        from hefesto_dualsense4unix.utils.xdg_paths import config_dir as _cfg

        config_dir = _cfg()
    return Path(config_dir) / NOME_DO_ARQUIVO


class PastaIlegivel(Exception):  # noqa: N818 — o projeto é em português
    """A pasta da chave não deixa o Hefesto olhar: não se sabe se há chave."""

    def __init__(self, pasta: Path, erro: OSError) -> None:
        self.pasta = pasta
        self.erro = erro
        super().__init__(
            f"a pasta {pasta} não deixa o Hefesto ler (dono ou permissão): {erro}"
        )

    def recado(self) -> str:
        """O quê, por quê e o que fazer, para quem roda o daemon na mão."""
        return (
            "O daemon NÃO subiu: o Hefesto não consegue olhar a pasta de configuração.\n"
            f"  {self}\n"
            "Isto é permissão ou dono da pasta, não a chave de desligar.\n"
            f"Confira com:  ls -ld {self.pasta}"
        )


def motivo_do_desligamento(config_dir: Path | None = None) -> str | None:
    """O texto da chave, ou `None` quando não há chave nenhuma.

    Levanta `PastaIlegivel` quando a pasta não deixa olhar: sem olhar não se sabe
    se a chave existe, e isso não é a decisão gravada de desligar.
    """
    alvo = caminho_da_chave(config_dir)
    try:
        alvo.stat()
    except OSError as exc:
        if isinstance(exc, FileNotFoundError):
            return None
        raise PastaIlegivel(alvo.parent, exc) from exc
    try:
        texto = alvo.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        return f"a chave existe mas não pôde ser lida ({exc})"
    return texto or "sem motivo escrito"


def recado_da_recusa(motivo: str, comando: str = "hefesto-chave on") -> str:
    """A frase que o daemon imprime ao recusar — o quê, por quê e o que fazer."""
    return (
        "O daemon NÃO subiu: este Hefesto está desligado pela chave.\n"
        f"  {motivo}\n"
        "Isso é uma decisão gravada em disco, não uma falha — alguém desligou\n"
        "esta instalação de propósito para que a outra rodasse sozinha.\n"
        f"Para religar:  {comando}"
    )


__all__ = [
    "NOME_DO_ARQUIVO",
    "PastaIlegivel",
    "caminho_da_chave",
    "motivo_do_desligamento",
    "recado_da_recusa",
]
