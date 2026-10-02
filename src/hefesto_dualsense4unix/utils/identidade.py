"""A identidade do app: os dez nomes por que ele se chama, num lugar só."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Identidade:
    """Os nomes do app, num objeto só."""

    slug: str
    app_id: str
    wm_instance: str
    wm_class: str
    nome: str
    nome_longo: str
    icone: str
    unit_daemon: str
    entrypoint_gui: str
    entrypoint_cli: str

    @property
    def padroes_de_matanca(self) -> tuple[str, ...]:
        r"""Os regexes de ``pgrep -f`` que reconhecem uma TELA nossa viva."""
        return (
            self.entrypoint_gui,
            r"scripts/abrir_interface\.py",
            r"io\.github\.hefesto_team\.hefesto_dualsense4unix",
            r"br\.andrefarias\.Hefesto",
        )

    @property
    def padrao_do_daemon(self) -> str:
        """O regex do daemon avulso, para o ``pgrep -f`` que checa systemd."""
        return f"{self.entrypoint_cli} daemon start"


#:   ``DualSense4Unix``, com o ``S`` do DualSense. Ele carrega o travessão
HEFESTO = Identidade(
    slug="hefesto-dualsense4unix",
    app_id="hefesto-dualsense4unix",
    wm_instance="hefesto-dualsense4unix",
    wm_class="Hefesto-Dualsense4Unix",
    nome="Hefesto",
    nome_longo="Hefesto — DualSense4Unix",
    icone="hefesto-dualsense4unix",
    unit_daemon="hefesto-dualsense4unix.service",
    entrypoint_gui="hefesto-dualsense4unix-gui",
    entrypoint_cli="hefesto-dualsense4unix",
)


def atual() -> Identidade:
    """A identidade deste processo."""
    return HEFESTO


__all__ = [
    "HEFESTO",
    "Identidade",
    "atual",
]
