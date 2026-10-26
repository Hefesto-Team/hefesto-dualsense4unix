"""O-START-SALVA-O-PERFIL-ATE-COM-O-MOUSE-LIGADO-01 — o Options salva com o mouse ligado também.

22/10/2026, escolha do usuário («Start sempre salva»): com a Interna agindo (ligada e a janela
na frente) o Start de TODO controle guarda e aplica o perfil, o de quem navega o PC com o mouse
ligado inclusive. Duas metades, as duas medidas aqui:

  * o daemon: o Start desse controle conta como toque e NÃO sai como Super por cima da janela;
  * a janela: o toque vira o ``Ato("salvar")``, que chama o gesto de guardar e aplicar.

MORDIDAS:
  * devolva ``BOTOES_DO_ALT_TAB`` ao ``calar_o_alt_tab`` com o mouse ligado: o Start sai como Super;
  * devolva ``if u not in fora`` ao ``any(...)`` de ``Navegador.atos``: o Start do primário some.
"""
from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import navegacao_interna as dono
from hefesto_dualsense4unix.interface import navegacao_interna as nav
from hefesto_dualsense4unix.interface.pacotes import a06_navegacao
from tests.unit.test_o_start_de_quem_navega_a_interna import _teclas_do_laco

JOGADORES = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]
DEZ = ["02-controles.html", "03-gatilhos.html"]
COM_O_MOUSE: dict[str, Any] = {"mouse_emulation": {"enabled": True}}
SEM_BLOCO: dict[str, Any] = {}


class _Relogio:
    def __call__(self) -> float:
        return 100.0


def _interna() -> dono.NavegacaoInterna:
    n = dono.NavegacaoInterna(ligada=True, tipo=dono.TIPO_INTERNA, relogio=_Relogio())
    n.declarar_foco(True)
    return n


@pytest.mark.parametrize("estado", [COM_O_MOUSE, SEM_BLOCO], ids=["mouse-ligado", "de-nascenca"])
@pytest.mark.parametrize("quem", range(4), ids=["p1", "p2", "p3", "p4"])
def test_o_start_de_cada_jogador_vira_o_salvar_com_o_mouse_ligado(
    quem: int, estado: dict[str, Any]
) -> None:
    """Do aperto no evdev ao ato da janela, no que o ``_navegar`` monta: P1 a P4.

    Prova da D-2210-O-START-SALVA-ATE-COM-O-MOUSE-LIGADO.
    """
    interna = _interna()
    zero = {u: {"options": 0} for u in JOGADORES}
    interna.contar(zero)
    assert a06_navegacao.o_mouse_navega(estado)
    sem = {JOGADORES[0]}
    navegador = nav.Navegador(relogio=_Relogio())
    navegador.atos(pagina=DEZ[0], dez=DEZ, toques=interna.toques(), ativa=True, sem_selecao=sem)
    apertado = {u: {"options": 1 if i == quem else 0} for i, u in enumerate(JOGADORES)}
    interna.contar(apertado)
    atos = navegador.atos(
        pagina=DEZ[0], dez=DEZ, toques=interna.toques(), ativa=True, sem_selecao=sem)
    assert nav.Ato("salvar") in atos, f"o Options de P{quem + 1} não chamou o salvar: {atos}"


@pytest.mark.parametrize("mouse_ligado", [True, False])
def test_o_start_so_conta_com_a_interna_agindo(mouse_ligado: bool) -> None:
    """Com a janela atrás o Start é do jogo: não vira toque, com o mouse ligado ou não."""
    n = dono.NavegacaoInterna(ligada=True, tipo=dono.TIPO_INTERNA, relogio=_Relogio())
    n.declarar_foco(False)
    n.contar({JOGADORES[0]: {"options": 0}})
    n.contar({JOGADORES[0]: {"options": 1}})
    assert n.toques()[JOGADORES[0]]["start"] == 0
    assert "options" in n.calar_o_alt_tab(frozenset({"options"}), mouse_ligado=mouse_ligado)


@pytest.mark.asyncio
@pytest.mark.parametrize("transporte", ["usb", "bt"])
async def test_no_cabo_e_no_radio_o_start_nao_sai_como_super_com_o_mouse_ligado(
    monkeypatch: pytest.MonkeyPatch, transporte: str
) -> None:
    """O laço real do daemon: a janela na frente, o mouse ligado, o Start apertado."""
    teclas = await _teclas_do_laco(
        monkeypatch, agindo=True, mouse_ligado=True, transporte=transporte)
    assert "KEY_LEFTMETA" not in teclas, f"o Start guardou e abriu a visão geral: {teclas}"
    assert "KEY_ENTER" in teclas, f"o clique do perfil sumiu de quem navega o PC: {teclas}"
