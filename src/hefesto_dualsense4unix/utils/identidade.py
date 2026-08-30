"""A identidade do app — UMA fonte para os dois Hefestos.

Pedido dela, 29/08/2026: *"Ele é instalado como OUTRO APP com a logo alterada
em dev"*, e *"temos que garantir que eu possa DESLIGAR o impacto do outro
Hefesto por completo e RELIGAR ele"*.

O QUE ESTE MÓDULO RESOLVE
-------------------------
Antes dele, o nome do app estava cravado à mão em oito lugares que não se
conheciam: o slug do ``platformdirs`` (``utils/xdg_paths.py``), o ``prgname``
e o ``WM_CLASS`` (``app/main.py``, ``app/app.py``, ``app/compact_window.py``),
o nome da unit (``daemon/service_install.py``), os padrões de matança de
instância anterior (``app/main.py``) e a lista de janelas próprias do
autoswitch (``profiles/autoswitch.py``). Um segundo app só nasce se os oito
mudarem JUNTOS — e um que fique para trás não dá erro: dá estrago calado
(perfil dela reescrito, daemon dela morto, ícone trocado na dock).

COMO SE ESCOLHE A VARIANTE
--------------------------
Pela variável de ambiente ``HEFESTO_VARIANTE``. Ausente ou vazia = o app
estável, com TODOS os valores byte-idênticos ao que estava cravado antes —
``tests/unit/test_identidade_das_duas_casas.py`` trava isso literal por
literal, para que este módulo não possa mudar a máquina dela por descuido.
``HEFESTO_VARIANTE=dev`` = o app de desenvolvimento, com casa própria.

Quem seta a variável é o instalador de dev (``install-dev.sh``), no
``.desktop`` e no lançador — nunca o ambiente dela.

O SUFIXO FICA NO MEIO, E ISSO É REQUISITO, NÃO ESTILO
------------------------------------------------------
``app/main.py:_kill_previous_instances`` mata por ``pgrep -f``, que é
casamento por SUBSTRING, com ``SIGTERM`` e depois ``SIGKILL``. Se o app de dev
se chamasse ``hefesto-dualsense4unix-gui-dev``, a string do estável
(``hefesto-dualsense4unix-gui``) estaria DENTRO dela: abrir a GUI dela mataria
a de dev, e vice-versa. Com ``hefesto-dev-dualsense4unix-gui`` nenhum dos dois
nomes contém o outro. ``test_nenhum_padrao_de_matanca_alcanca_a_outra_casa``
é a régua que segura isso, e ela morde: renomear para o sufixo no fim reprova.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

#: Nome da variável que escolhe a variante. Só o instalador de dev a escreve.
VARIANTE_ENV = "HEFESTO_VARIANTE"

#: O valor que liga o app de desenvolvimento. Qualquer outro valor (inclusive
#: um typo) cai no estável — o padrão é NÃO se separar da casa dela por engano.
VARIANTE_DEV = "dev"


@dataclass(frozen=True)
class Identidade:
    """Tudo que distingue um Hefesto do outro, num objeto só."""

    #: ``""`` para o estável, ``"dev"`` para o de desenvolvimento.
    variante: str
    #: O slug do ``platformdirs``: config, data, cache, runtime, state e o
    #: socket IPC saem todos daqui. É a linha que separa os perfis dela do
    #: que o app de dev escreve.
    slug: str
    #: O basename do ``.desktop`` e o ``Icon=`` dele.
    app_id: str
    #: Primeiro campo do ``WM_CLASS`` (``res_name``). Vem do ``prgname``.
    wm_instance: str
    #: Segundo campo do ``WM_CLASS`` (``res_class``) — é ESTE que o cosmic-comp
    #: publica como ``app_id`` (``cosmic-comp/src/shell/element/surface.rs:237``
    #: → ``smithay/src/xwayland/xwm/surface.rs:1083``), e é o que tem de casar
    #: o ``StartupWMClass`` do ``.desktop``.
    wm_class: str
    #: O que aparece na barra de título e na dock.
    nome: str
    #: ``GLib.set_application_name`` — fallback de título de janela.
    nome_longo: str
    #: Nome do ícone no tema hicolor.
    icone: str
    #: A unit systemd ``--user`` do daemon.
    unit_daemon: str
    #: O console script da GUI (``pyproject.toml``) — entra nos padrões de
    #: matança.
    entrypoint_gui: str
    #: O console script da CLI; ``"<ele> daemon start"`` é o padrão de matança
    #: do daemon avulso.
    entrypoint_cli: str

    @property
    def padroes_de_matanca(self) -> tuple[str, ...]:
        """Os regexes que ``_kill_previous_instances`` passa ao ``pgrep -f``.

        Só alcançam processos DESTA variante. O do módulo
        (``hefesto_dualsense4unix.app.main``) é o único que não pode ser
        distinguido por nome — as duas variantes importam o mesmo pacote —,
        então ele SÓ entra no estável: o app de dev nasce por console script
        (``entrypoint_gui``) e nunca por ``python -m``, o que o mantém fora do
        alcance do ``pgrep`` da GUI dela. Ver
        ``test_nenhum_padrao_de_matanca_alcanca_a_outra_casa``.
        """
        padroes = [self.entrypoint_gui]
        if not self.variante:
            padroes.append(r"hefesto_dualsense4unix\.app\.main")
            # IDENTIDADE-01 (25/08/2026): os DOIS app-ids do Flatpak. Só o
            # estável tem Flatpak publicado; o de dev não empacota.
            padroes.append(r"io\.github\.hefesto_team\.hefesto_dualsense4unix")
            padroes.append(r"br\.andrefarias\.Hefesto")
        return tuple(padroes)

    @property
    def padrao_do_daemon(self) -> str:
        """O regex do daemon avulso, para o ``pgrep -f`` que checa systemd."""
        return f"{self.entrypoint_cli} daemon start"


#: O app dela. Cada literal aqui é o que estava cravado no código antes deste
#: módulo existir — mudar qualquer um muda a máquina dela.
ESTAVEL = Identidade(
    variante="",
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

#: O app de desenvolvimento. Note o ``dev`` no MEIO de cada nome — ver o
#: cabeçalho deste módulo.
DEV = Identidade(
    variante=VARIANTE_DEV,
    slug="hefesto-dev-dualsense4unix",
    app_id="hefesto-dev-dualsense4unix",
    wm_instance="hefesto-dev-dualsense4unix",
    wm_class="Hefesto-Dev-Dualsense4Unix",
    nome="Hefesto (dev)",
    nome_longo="Hefesto (dev) - Dualsense4Unix",
    icone="hefesto-dev-dualsense4unix",
    unit_daemon="hefesto-dev-dualsense4unix.service",
    entrypoint_gui="hefesto-dev-dualsense4unix-gui",
    entrypoint_cli="hefesto-dev-dualsense4unix",
)

#: As duas, para quem precisa varrer as duas casas — o autoswitch precisa
#: reter a janela das DUAS, senão alt-tab para a de dev troca perfil dela no
#: meio da partida (MISC-08, ``profiles/autoswitch.py``).
AS_DUAS: tuple[Identidade, ...] = (ESTAVEL, DEV)


def identidade_de(variante: str | None) -> Identidade:
    """A identidade de uma variante nomeada. Desconhecida cai no estável."""
    return DEV if (variante or "").strip().casefold() == VARIANTE_DEV else ESTAVEL


def atual() -> Identidade:
    """A identidade DESTE processo, lida do ambiente a cada chamada.

    Lê o ambiente toda vez em vez de congelar no import: o teste troca a
    variável com ``monkeypatch`` e mede as duas casas no mesmo processo, e um
    valor congelado no import tornaria isso impossível de medir. O custo é uma
    leitura de ``os.environ``, que os chamadores fazem uma vez no boot.
    """
    return identidade_de(os.environ.get(VARIANTE_ENV))


__all__ = [
    "AS_DUAS",
    "DEV",
    "ESTAVEL",
    "VARIANTE_DEV",
    "VARIANTE_ENV",
    "Identidade",
    "atual",
    "identidade_de",
]
