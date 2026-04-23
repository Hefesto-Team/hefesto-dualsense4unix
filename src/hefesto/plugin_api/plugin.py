"""ABC Plugin — interface base para todos os plugins do Hefesto.

Cada plugin Python em ~/.config/hefesto/plugins/*.py deve definir
exatamente uma subclasse de Plugin. A subclasse é instanciada pelo
loader; os hooks sao chamados pelo PluginsSubsystem no poll loop.

Convencoes:
  - `name` (str): identificador único do plugin (slug snake_case).
  - `profile_match` (list[str]): lista de slugs de perfis em que o plugin
    deve ser ativado. Lista vazia = ativo em todos os perfis.
  - Todos os hooks tem implementacao no-op por padrao; o plugin soh
    precisa sobrescrever o que usar.

Aviso de seguranca:
    Plugins rodam com os mesmos privilegios do daemon (usuario comum).
    Não ha sandbox forte. O usuario e responsavel pelo codigo que instalar
    em ~/.config/hefesto/plugins/. Ver ADR-017.
"""
from __future__ import annotations

from abc import ABC
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from hefesto.core.controller import ControllerState
    from hefesto.plugin_api.context import PluginContext


class Plugin(ABC):
    """Classe base para plugins do Hefesto.

    Atributos de classe obrigatorios:
        name: slug único do plugin (snake_case, sem espacos).

    Atributos de classe opcionais:
        profile_match: lista de slugs de perfis. Se vazia, o plugin
            recebe on_tick independente do perfil ativo.
    """

    name: str
    profile_match: ClassVar[list[str]] = []

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def on_load(self, ctx: PluginContext) -> None:  # noqa: B027
        """Chamado uma vez quando o plugin e carregado pelo daemon.

        Use para guardar referencia ao ctx e realizar inicializacoes.
        """

    def on_unload(self) -> None:  # noqa: B027
        """Chamado quando o plugin e descarregado (shutdown do daemon
        ou reload manual).

        Use para liberar recursos (fechar arquivos, sockets, etc.).
        """

    # ------------------------------------------------------------------
    # Hooks de estado
    # ------------------------------------------------------------------

    def on_tick(self, state: ControllerState) -> None:  # noqa: B027
        """Chamado a cada tick do poll loop (~30-120 Hz por padrao).

        IMPORTANTE: manter rapido (< 1 ms ideal, < 5 ms maximo).
        Hooks lentos sao logados como warning e o plugin pode ser
        desativado automaticamente pelo watchdog do PluginsSubsystem.

        Args:
            state: snapshot imutavel do controle neste tick.
        """

    def on_button_down(self, name: str) -> None:  # noqa: B027
        """Chamado quando um botao e pressionado.

        Args:
            name: nome canonico do botao (ex.: "cross", "l1", "mic_btn").
        """

    def on_battery_change(self, pct: int) -> None:  # noqa: B027
        """Chamado quando o nivel de bateria muda (apos debounce).

        Args:
            pct: percentual 0-100.
        """

    def on_profile_change(self, from_name: str | None, to_name: str) -> None:  # noqa: B027
        """Chamado quando o perfil ativo muda (autoswitch ou manual).

        Args:
            from_name: slug do perfil anterior (None se era o primeiro).
            to_name: slug do perfil novo.
        """


__all__ = ["Plugin"]
