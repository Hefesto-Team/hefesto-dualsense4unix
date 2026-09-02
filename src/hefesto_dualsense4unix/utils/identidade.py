"""A identidade do app: os dez nomes por que ele se chama, num lugar só.

O QUE ISTO RESOLVE. O nome do app não é um nome — são dez, e eles têm de
concordar: o slug do ``platformdirs`` (``utils/xdg_paths.py``), o ``prgname`` e
os dois campos do ``WM_CLASS`` (``app/main.py``), o nome da unit
(``daemon/service_install.py``), o nome do ícone e do ``.desktop``
(``packaging/``), os dois console scripts (``pyproject.toml``) e os padrões que
o ``pgrep -f`` usa para matar a instância anterior.

Dez literais que precisam concordar são dez lugares para um deles ficar para
trás — e um que fique para trás **não dá erro**: dá estrago calado. Perfil dela
escrito na pasta errada, daemon dela morto por um ``pgrep`` que casou demais,
ícone que a dock não acha porque o ``StartupWMClass`` diverge de uma letra. Em
01/09/2026 foi um desses que fez a aba Sistema afirmar ``not-found`` sobre uma
unit ``enabled``: alguém digitou o nome da unit em vez de perguntar aqui.

**A regra é uma: o nome do app não se digita.** Pergunte ao :func:`atual`.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Identidade:
    """Os nomes do app, num objeto só."""

    #: O slug do ``platformdirs``: config, data, cache, runtime, state e o
    #: socket IPC saem todos daqui.
    slug: str
    #: O id do ``.desktop`` e do ícone.
    app_id: str
    #: O primeiro campo do ``WM_CLASS``.
    wm_instance: str
    #: O segundo campo do ``WM_CLASS`` — é ele que o ``StartupWMClass`` do
    #: ``.desktop`` tem de casar LETRA POR LETRA para a dock achar o app.
    wm_class: str
    #: O nome curto, para a tela.
    nome: str
    #: O nome por extenso, para o ``.desktop`` e o ``--version``.
    nome_longo: str
    #: O nome do ícone no tema ``hicolor``.
    icone: str
    #: O nome da unit systemd do usuário.
    unit_daemon: str
    #: O console script da janela; ele é também um padrão de matança.
    entrypoint_gui: str
    #: O console script da CLI; ``"<ele> daemon start"`` é o padrão de matança
    #: do daemon avulso.
    entrypoint_cli: str

    @property
    def padroes_de_matanca(self) -> tuple[str, ...]:
        """Os regexes que ``_kill_previous_instances`` passa ao ``pgrep -f``.

        SÃO QUATRO PORQUE HÁ QUATRO JEITOS DE ABRIR A JANELA: o console script,
        o ``python -m`` do módulo, e os dois app-ids que o Flatpak já publicou.
        Um que falte deixa uma segunda janela viva falando com o mesmo daemon —
        e duas janelas escrevendo o mesmo perfil é o defeito que esta lista
        existe para não ter.
        """
        return (
            self.entrypoint_gui,
            r"hefesto_dualsense4unix\.app\.main",
            r"io\.github\.hefesto_team\.hefesto_dualsense4unix",
            r"br\.andrefarias\.Hefesto",
        )

    @property
    def padrao_do_daemon(self) -> str:
        """O regex do daemon avulso, para o ``pgrep -f`` que checa systemd."""
        return f"{self.entrypoint_cli} daemon start"


#: O APP. Cada literal aqui é o que estava cravado no código antes deste módulo
#: existir — mudar qualquer um muda a máquina dela.
HEFESTO = Identidade(
    slug="hefesto-dualsense4unix",
    app_id="hefesto-dualsense4unix",
    wm_instance="hefesto-dualsense4unix",
    wm_class="Hefesto-Dualsense4Unix",
    nome="Hefesto",
    nome_longo="Hefesto - Dualsense4Unix",
    icone="hefesto-dualsense4unix",
    unit_daemon="hefesto-dualsense4unix.service",
    entrypoint_gui="hefesto-dualsense4unix-gui",
    entrypoint_cli="hefesto-dualsense4unix",
)


def atual() -> Identidade:
    """A identidade deste processo.

    A FUNÇÃO EXISTE, e a constante também, de propósito: os chamadores
    perguntam por aqui, e o dia em que a identidade depender de algo (um
    empacotamento, um ambiente) é esta função que passa a decidir, sem que
    nenhum deles mude.
    """
    return HEFESTO


__all__ = [
    "HEFESTO",
    "Identidade",
    "atual",
]
