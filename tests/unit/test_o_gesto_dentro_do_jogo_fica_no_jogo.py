"""O gesto dentro de um jogo grava no perfil do jogo, e não na escolha global.

CAMINHO-CONTAGIO-01, pontos 1 e 3 do escopo de 19/09/2026. Decisão dela ao ver
a causa:

    *"tá mas isso é claramente um vazamento."*  ·  *"sim tudo dualsense, tudo
    ligado mascara dualsense por default mas esse vazamento me preocupa"*
    <!-- noqa-acento: citação literal dela -->

**O DEFEITO, medido no log dela de 18/09/2026:**

    11:18:21  hotkey_fired buttons=['ps','r3'] combo=ponte
    11:18:23  modo_do_gesto_gravado_no_perfil caminho=xbox profile="DON'T SCREAM"
              gamepad_caminho.flag = xbox (mtime 18/09 11:18)      ← o vazamento

Um aperto dentro de um jogo virou lei sobre os outros 26 perfis que não têm
`mode.caminho` — o PRAGMATA entre eles, com giroscópio e touchpad fora do jogo.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp


class _Config:
    def __init__(self) -> None:
        self.gamepad_caminho: str | None = None
        self.gamepad_caminho_global: str | None = None


class _Daemon:
    """O mínimo que `_guardar_o_caminho` toca, e o detector de janela."""

    def __init__(self, *, jogo_em_foco: bool) -> None:
        self.config = _Config()
        self._jogo = jogo_em_foco

    def _janela_de_jogo_em_foco(self) -> bool:
        return self._jogo


def _gesto_manual(daemon: Any, caminho: str) -> None:
    gp._guardar_o_caminho(daemon, caminho, origin="manual")


# ---------------------------------------------------------------------------
# Ponto 1 — o gesto dentro do jogo fica no jogo
# ---------------------------------------------------------------------------


def test_com_jogo_em_foco_a_escolha_global_nao_e_tocada() -> None:
    """É o defeito de 18/09, medido: o PS + R3 no DON'T SCREAM não vaza."""
    daemon = _Daemon(jogo_em_foco=True)
    daemon.config.gamepad_caminho_global = "dualsense"

    _gesto_manual(daemon, "xbox")

    assert daemon.config.gamepad_caminho_global == "dualsense", (
        "o gesto dentro do jogo escreveu na escolha global — é o vazamento"
    )
    # e o slot da SESSÃO recebeu, porque é dele que vivem a tela e o wrapper
    assert daemon.config.gamepad_caminho == "xbox"


def test_sem_jogo_em_foco_a_escolha_global_e_escrita() -> None:
    """O outro lado, e ele não pode cair junto: no desktop, ela escolhe.

    Sem esta régua a cura viraria *"o gesto nunca escreve no global"*, e o chip
    de modo dela deixaria de valer no boot seguinte sem ninguém notar.
    """
    daemon = _Daemon(jogo_em_foco=False)

    _gesto_manual(daemon, "xbox")

    assert daemon.config.gamepad_caminho_global == "xbox"


def test_o_detector_que_levanta_falha_para_o_lado_de_escrever() -> None:
    """Sem detector confiável, escreve — perder escolha dela é pior."""

    class _DaemonQuebrado(_Daemon):
        def _janela_de_jogo_em_foco(self) -> bool:
            raise RuntimeError("sem servidor de janelas")

    daemon = _DaemonQuebrado(jogo_em_foco=True)
    _gesto_manual(daemon, "xbox")
    assert daemon.config.gamepad_caminho_global == "xbox"


def test_daemon_sem_detector_nenhum_escreve_como_antes() -> None:
    """Um daemon que não tem o método (dublês antigos) não pode quebrar."""

    class _Pelado:
        def __init__(self) -> None:
            self.config = _Config()

    daemon = _Pelado()
    _gesto_manual(daemon, "xbox")
    assert daemon.config.gamepad_caminho_global == "xbox"


@pytest.mark.parametrize("origem", ["profile", "autoswitch", "hotplug", "boot"])
def test_so_o_gesto_manual_escreve_no_global(origem: str) -> None:
    """A regra de 17/09 continua: perfil, boot e autoswitch nunca escrevem."""
    daemon = _Daemon(jogo_em_foco=False)
    gp._guardar_o_caminho(daemon, "xbox", origin=origem)  # type: ignore[arg-type]
    assert daemon.config.gamepad_caminho_global is None


# ---------------------------------------------------------------------------
# Ponto 3 — o arquivo global volta ao default, uma vez
# ---------------------------------------------------------------------------


def test_o_xbox_do_vazamento_e_devolvido(monkeypatch: pytest.MonkeyPatch) -> None:
    """O flag dela diz `xbox` desde 18/09 por causa do vazamento, não de escolha."""
    escritos: list[str | None] = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_gamepad_caminho",
        lambda c: escritos.append(c),
    )
    assert lifecycle._a_escolha_dela_sem_o_vazamento("xbox") == "dualsense"
    assert escritos == ["dualsense"], "a devolução tem de chegar ao DISCO"


@pytest.mark.parametrize("valor", ["dualsense", None, "", "lixo"])
def test_o_que_nao_e_o_xbox_do_vazamento_passa_intacto(
    valor: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A assimetria é de propósito — só o valor que o vazamento escreve volta."""
    escritos: list[str | None] = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_gamepad_caminho",
        lambda c: escritos.append(c),
    )
    antes = lifecycle._a_escolha_dela_sem_o_vazamento(valor)
    assert antes != "dualsense" or valor == "dualsense"
    assert escritos == [], "nada a devolver não pode escrever no disco dela"
