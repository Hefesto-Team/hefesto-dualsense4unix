"""VPAD-NA-JANELA-DA-STEAM-01 (17/08/2026) — o alt-tab que matava o controle.

**O defeito, medido com par fechado na máquina dela.** Mesmo daemon, mesmo
minuto, mesmo controle no cabo. A única variável é qual perfil está ativo::

    profile activate "Dont Scream"   ->  /dev/hidraw4 NASCE   (gamepad: ligado)
    profile activate "Navegação"     ->  /dev/hidraw4 SOME    (gamepad: desligado)

E o journal do mesmo instante::

    uhid_motion_streaming on=False
    gamepad_controller_grab grab=False ok=True state=off
    gamepad_emulation_stopped
    profile_activated name=Navegação origin=autoswitch

O perfil de desktop dela (`Navegação`) casa com `steam` e `Steam` no
`window_class`. Logo: **alternar para a janela da Steam no meio da partida
destruía o controle virtual.** O jogo, que já tinha enumerado aquele nó, ficava
com um descritor órfão — um controle que existe e não se mexe.

**Não era regressão de 16/08.** A reversão por "perfil sem opinião" é de
13/07/2026 (`c106ee3`) e foi estreitada em 23/07 (`19bc7e9`), que pôs duas
guardas justamente contra este cenário. As duas deixavam passar:

- ``_perfil_tem_opiniao`` só barra catch-all, e `Navegação` é `criteria` com
  lista explícita de janelas — "tem opinião", passa reto;
- ``_janela_de_jogo_em_foco`` só reconhecia ``steam_app_<id>``. A janela do
  CLIENTE Steam é ``steam``, sem appid. **A guarda que existe para proteger a
  partida era cega justamente para a janela que se alterna durante a partida.**

**O que mudou em 16/08 e fez isso doer** é hipótese, não medição: os commits do
wrapper (`4de4762`, `912617a`, `045d3d0`) devolveram a ponte `hefesto-launch` às
LaunchOptions e os jogos voltaram a ENXERGAR o vpad. Enquanto o jogo não via o
controle de jeito nenhum, a morte do vpad no alt-tab era invisível.

**A decisão dela (17/08), com o preço na mesa:** a guarda passa a proteger o
cliente Steam. O preço aceito é que, com a Steam em foco, o modo vindo de
perfil não reverte nem sem jogo atrás — o que mantém o vpad de pé enquanto ela
navega na Steam, que é o estado normal desta máquina. Fora da Steam a reversão
continua imediata, e o teste de 23/07 que finca isso (`firefox`) continua verde.
"""

from __future__ import annotations

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.profiles.steam_app import (
    e_janela_do_cliente_steam,
    steam_appid_from_wm_class,
)
from hefesto_dualsense4unix.testing.fake_controller import FakeController


@pytest.fixture
def daemon() -> Daemon:
    """O mesmo daemon de bancada do `test_profile_mode.py`.

    Repetida aqui em vez de promovida ao `conftest.py`: este arquivo cobre um
    predicado e uma guarda, e o dia em que a fixture de lá mudar por causa de
    outro teste não pode arrastar este junto sem ninguém perceber.
    """
    return Daemon(controller=FakeController(), config=DaemonConfig())


class TestOPredicado:
    """`e_janela_do_cliente_steam` — a pergunta que faltava, isolada."""

    @pytest.mark.parametrize(
        "wm_class",
        ["steam", "Steam", "  Steam  ", "STEAM", "steamwebhelper", "SteamWebHelper"],
    )
    def test_o_cliente_steam_e_reconhecido(self, wm_class: str) -> None:
        """Insensível a caixa e tolerante a espaço — contrato do módulo.

        A caixa não é gosto: a `wm_class` chega do X/XWayland com a grafia que
        o toolkit escolheu e MUDA entre backends de detecção. Um predicado
        sensível aqui reabriria o buraco para `Steam` num backend e não no
        outro — que é a classe de defeito que este módulo nasceu para fechar.
        """
        assert e_janela_do_cliente_steam(wm_class) is True

    @pytest.mark.parametrize(
        "wm_class",
        ["firefox", "gnome-terminal", "steam_app_2497900", "", "steamy", "n"],
    )
    def test_o_que_nao_e_o_cliente_fica_de_fora(self, wm_class: str) -> None:
        assert e_janela_do_cliente_steam(wm_class) is False

    def test_nao_engole_none_nem_tipo_errado(self) -> None:
        assert e_janela_do_cliente_steam(None) is False
        assert e_janela_do_cliente_steam(123) is False  # type: ignore[arg-type]

    def test_as_duas_perguntas_sao_disjuntas_e_complementares(self) -> None:
        """Jogo tem appid; cliente não tem. Nenhuma wm_class é as duas coisas.

        É por isso que a guarda precisa das DUAS: `steam_appid_from_wm_class`
        sozinha responde `None` para o cliente, e foi essa resposta que
        autorizou a destruição do vpad.
        """
        assert steam_appid_from_wm_class("steam_app_2497900") == 2497900
        assert e_janela_do_cliente_steam("steam_app_2497900") is False

        assert steam_appid_from_wm_class("steam") is None
        assert e_janela_do_cliente_steam("steam") is True


class TestAGuardaNoDaemon:
    """`_janela_de_jogo_em_foco` — a guarda que protege a partida."""

    def test_a_janela_da_steam_protege_a_partida(self, daemon: Daemon) -> None:
        """A MORDIDA. Arranque o `e_janela_do_cliente_steam` da guarda e este

        teste fica vermelho — e com ele volta o defeito de 17/08 inteiro.
        """
        daemon.store.record_window_detect_read("teste", "steam")
        assert daemon._janela_de_jogo_em_foco() is True, (
            "a guarda não reconheceu a janela do cliente Steam — alternar para "
            "a Steam no meio do jogo volta a destruir o vpad"
        )

    def test_a_janela_do_jogo_continua_protegida(self, daemon: Daemon) -> None:
        """O caso de 23/07 não pode ter sido trocado pelo novo."""
        daemon.store.record_window_detect_read("teste", "steam_app_2497900")
        assert daemon._janela_de_jogo_em_foco() is True

    def test_o_desktop_de_verdade_continua_desprotegido(self, daemon: Daemon) -> None:
        """A reversão legítima continua existindo — senão o perfil GRUDA.

        Esta é a metade que impede a cura de virar o defeito oposto: se a
        guarda respondesse True para tudo, o perfil de jogo nunca sairia e o
        modo de desktop dela nunca voltaria.
        """
        for wm_class in ("firefox", "gnome-terminal", "brave-browser", ""):
            daemon.store.record_window_detect_read("teste", wm_class)
            assert daemon._janela_de_jogo_em_foco() is False, wm_class
