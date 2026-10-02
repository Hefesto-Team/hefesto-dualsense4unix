"""A chave que desliga um Hefesto por completo — e o religa."""
from __future__ import annotations

from pathlib import Path

# `portao_a_casa_sabe_e_o_produto_nao_faz` as reprovou, com razão: nenhum

NOME_DO_ARQUIVO = "DESLIGADO-pela-chave.flag"


def caminho_da_chave(config_dir: Path | None = None) -> Path:
    """Onde a chave mora: no ``config_dir()`` do app."""
    if config_dir is None:
        from hefesto_dualsense4unix.utils.xdg_paths import config_dir as _cfg

        config_dir = _cfg()
    return Path(config_dir) / NOME_DO_ARQUIVO


def motivo_do_desligamento(config_dir: Path | None = None) -> str | None:
    """O texto da chave, ou `None` quando não há chave nenhuma."""
    alvo = caminho_da_chave(config_dir)
    try:
        if not alvo.exists():
            return None
        texto = alvo.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        return f"a chave existe mas não pôde ser lida ({exc})"
    return texto or "sem motivo escrito"


def recado_da_recusa(motivo: str, comando: str = "hefesto-chave estavel on") -> str:
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
    "caminho_da_chave",
    "motivo_do_desligamento",
    "recado_da_recusa",
]
