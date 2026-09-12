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
        r"""Os regexes de ``pgrep -f`` que reconhecem uma TELA nossa viva.

        SÃO QUATRO PORQUE HÁ QUATRO JEITOS DE ABRIR A TELA: o console script,
        o envoltório que o ``.desktop`` roda, e os dois app-ids que o Flatpak já
        publicou. Um que falte deixa uma segunda janela viva falando com o mesmo
        daemon — e duas janelas escrevendo o mesmo perfil é o defeito que esta
        lista existe para não ter.

        O SEGUNDO PADRÃO MUDOU EM 06/09/2026 (`GTK-3`): era
        ``hefesto_dualsense4unix\.app\.main``, o ``python -m`` da janela GTK, e
        esse módulo foi apagado por decisão dela (`D-0609-GTK-LEVA-INTEIRA`) —
        um padrão que não casa mata coisa nenhuma, CALADO, que é exatamente o
        defeito que o ``PACKAGING-PRERM-PKILL-MODULO-ERRADO-01`` custou. O que a
        `.desktop` abre hoje é ``python3 <árvore>/scripts/abrir_interface.py``.

        **SEM CHAMADOR HOJE, e está escrito porque é medido:** o único era
        ``app/main._kill_previous_instances``, que morreu com a janela. A lista
        fica de pé porque o ``packaging/debian/prerm`` usa o mesmo padrão, e
        porque ela é a resposta única desta casa à pergunta *"como se reconhece
        um processo nosso?"*.
        """
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


#: O APP. Cada literal aqui é o que estava cravado no código antes deste módulo
#: existir — mudar qualquer um muda a máquina dela.
#:
#: A GRAFIA DO NOME DIVIDE ESTA LISTA EM DUAS, e a divisão é medida
#: (`F6-O-NOME-TEM-UM-DONO`, 11/09/2026):
#:
#: * ``nome_longo`` é TEXTO — é como o produto se apresenta, e a grafia certa é
#:   ``DualSense4Unix``, com o ``S`` do DualSense. Ele carrega o travessão
#:   porque é a string EXATA que a barra da janela mostra e que o ``<h1>`` das
#:   dez páginas já dizia; quem mostra o nome LÊ daqui, não digita.
#: * ``wm_class`` continua ``Hefesto-Dualsense4Unix``, com ``s`` minúsculo, e
#:   isso NÃO é esquecimento: ele é o elo que o ``StartupWMClass=`` do
#:   ``.desktop`` já instalado na máquina dela casa LETRA POR LETRA, o valor que
#:   o daemon gravou em ``last_class`` e o que os perfis de jogo guardam em
#:   ``window_class``. Trocar a caixa some com o ícone da dock e mata o perfil
#:   por janela — calado, que é o defeito que esta casa mais paga.
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
