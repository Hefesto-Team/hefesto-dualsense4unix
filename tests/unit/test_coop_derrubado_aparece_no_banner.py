"""CONTAGEM-E-COOP-01 (E1a) — o banner AVISA que o jogo derrubou o co-op.

A outra metade já entrou em 29/07: o daemon emite o fato
(`gamepad.py:508-537`) e o `state_full` o publica em duas chaves
(`ipc_handlers.py:1657-1662`). O que faltava era a janela LER. Medido no HEAD
`7bd0cb7`, antes desta entrega::

    $ grep -rn "coop_derrubado" src/hefesto_dualsense4unix/app/
    (zero linhas)

O daemon gritava a 10 Hz e ninguém escutava — e enquanto a suspensão durava a
janela ficava ativamente enganosa, porque `CoopManager.disable()` não zera
`coop_enabled`: o `state_full` seguia dizendo `coop.enabled=True` com
`coop.players=1`, indistinguível de "ela desligou o co-op".

O caminho está QUENTE: 20 entradas na exceção de Steam Input em três dias,
todas no Pragmata. Nunca mordeu porque `jogadores_coop=0` em todas — ela jogou
sozinha. No dia dos quatro controles, os três secundários caem.

Nenhuma linha da LÓGICA de queda é tocada por esta frente, e não pode ser: o
cabeçalho de `test_coop_nao_cai_em_silencio.py` registra que mexer no gatilho
encosta na exceção de Steam Input, que é o caminho do defeito do R1.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: no topo, antes de qualquer import de `gi`. Só a classe
# `TestOBadgeNoBanner` precisa de widget; as de vocabulário são puras e ficam
# aqui junto por serem o MESMO contrato de texto.
exigir_gi_real("coop derrubado: o aviso no banner")

from typing import Any

from hefesto_dualsense4unix.app.actions.status_actions import (
    StatusActionsMixin,
    texto_do_coop_derrubado,
    tooltip_do_coop_derrubado,
)


def _coop(derrubado: bool, secundarios: int, players: int = 1) -> dict[str, Any]:
    """O bloco `coop` como o daemon o publica — inclusive as duas mentiras.

    `enabled=True` com `players=1` durante a queda NÃO é engano do teste: é o
    que `ipc_handlers.py:1613-1622` publica de verdade, porque `disable()` não
    toca em `coop_enabled` (`coop.py:1337-1345`).
    """
    return {
        "enabled": True,
        "players": players,
        "externals": 0,
        "derrubado_por_steam_input": derrubado,
        "secundarios_derrubados": secundarios,
    }


class TestAsTresPartesObrigatorias:
    """Cada parte desfaz uma mentira medida — nenhuma é enfeite."""

    def test_o_numero_vem_dos_secundarios_e_nao_de_players(self) -> None:
        """`players` já voltou a 1 no tique seguinte — é o defeito original."""
        texto = texto_do_coop_derrubado(_coop(True, 3, players=1))
        assert "3" in texto
        assert "1" not in texto

    def test_nega_que_foi_ela_que_desligou(self) -> None:
        """Desfaz a ambiguidade que `coop.enabled=True` cria."""
        assert "não foi você" in texto_do_coop_derrubado(_coop(True, 3))

    def test_promete_a_volta_e_a_promessa_e_verdadeira(self) -> None:
        """`resume_vpads_after_steam_input` chama `coop.sync(force=True)`."""
        assert "voltam sozinhos" in texto_do_coop_derrubado(_coop(True, 3))

    def test_nao_diz_so_o_fato(self) -> None:
        """"O co-op caiu" seria o FATO; a tela dela precisa do PREÇO."""
        texto = texto_do_coop_derrubado(_coop(True, 3))
        assert texto != "O co-op caiu"
        assert "jogadores" in texto and "não foi você" in texto

    def test_singular_com_um_jogador_so(self) -> None:
        texto = texto_do_coop_derrubado(_coop(True, 1))
        assert texto == "1 jogador saiu — não foi você; volta sozinho"

    def test_o_p1_nunca_entra_na_lista(self) -> None:
        """O P1 não é jogador do co-op: tem observável próprio (`vpad_suspenso`).

        A lista vive no tooltip (a linha do banner não a comporta com o badge
        de vibração aceso), e é lá que o P1 não pode aparecer.
        """
        assert "P1" not in tooltip_do_coop_derrubado(_coop(True, 3))
        assert "P2, P3 e P4" in tooltip_do_coop_derrubado(_coop(True, 3))

    def test_a_linha_do_banner_cabe_com_o_badge_de_vibracao_aceso(self) -> None:
        """Os DOIS badges no mesmo `header_bar` — a pergunta que a sprint abriu.

        Medido com o glade real na largura da janela dela (953px): com a lista
        de jogadores na frase, os dois juntos pediam 966px e o aviso era
        cortado no meio de "não foi vo…". A asserção aqui é o teto de
        caracteres, que é font-independente e é o que sustenta aquela medida.
        """
        assert len(texto_do_coop_derrubado(_coop(True, 3))) <= 52
        assert len(texto_do_coop_derrubado(_coop(True, 12))) <= 52


class TestOAvisoMorreQuandoOCoopVolta:
    def test_sem_queda_nao_ha_frase(self) -> None:
        assert texto_do_coop_derrubado(_coop(False, 0, players=4)) == ""

    def test_gatilho_aceso_com_zero_derrubados_nao_pendura_aviso(self) -> None:
        """As duas mortes do contador existem para isto (`gamepad.py:565`/:1401)."""
        assert texto_do_coop_derrubado(_coop(True, 0)) == ""

    def test_bloco_ausente_ou_estranho_nao_explode(self) -> None:
        for bloco in (None, "coop", 3, [], {}):
            assert texto_do_coop_derrubado(bloco) == ""

    def test_booleano_no_lugar_do_inteiro_nao_vira_um(self) -> None:
        """`True` é `int` em Python — sem a guarda o aviso diria "1 jogador"."""
        assert texto_do_coop_derrubado(_coop(True, True)) == ""  # type: ignore[arg-type]


class TestOTooltipDizOPrecoPorExtenso:
    def test_tem_as_tres_partes_e_o_motivo(self) -> None:
        texto = tooltip_do_coop_derrubado(_coop(True, 3))
        assert "O jogo assumiu o controle" in texto
        assert "P2, P3 e P4" in texto
        assert "Você não desligou nada" in texto
        assert "fechar o jogo" in texto

    def test_sem_queda_nao_ha_tooltip(self) -> None:
        assert tooltip_do_coop_derrubado(_coop(False, 0)) == ""


class TestOBadgeNoBanner:
    """A fiação: o badge acende, diz o número e SOME quando o co-op volta."""

    @staticmethod
    def _stub() -> Any:
        from gi.repository import Gtk

        class _Stub(StatusActionsMixin):
            def __init__(self) -> None:
                self._coop_badge = Gtk.Label()
                self._coop_badge.set_use_markup(True)
                self._coop_badge.set_no_show_all(True)
                self._coop_badge.hide()

        return _Stub()

    def test_acende_com_o_numero_e_apaga_quando_volta(self) -> None:
        stub = self._stub()

        stub._update_coop_badge({"coop": _coop(True, 3)})
        assert stub._coop_badge.get_visible()
        assert "3" in stub._coop_badge.get_text()
        assert "voltam sozinhos" in stub._coop_badge.get_text()
        assert "fechar o jogo" in (stub._coop_badge.get_tooltip_text() or "")

        # O co-op voltou: o daemon zerou o contador e o aviso tem de sumir NO
        # MESMO TIQUE, sem reiniciar a janela.
        stub._update_coop_badge({"coop": _coop(False, 0, players=4)})
        assert not stub._coop_badge.get_visible()

    def test_sem_o_widget_nao_explode(self) -> None:
        """Dublê/glade antigo sem o badge: o tique de 0,5 Hz não pode morrer."""

        class _SemBadge(StatusActionsMixin):
            pass

        _SemBadge()._update_coop_badge({"coop": _coop(True, 3)})

    def test_o_tique_lento_chama_o_badge(self) -> None:
        """Sem esta chamada o badge existiria e nunca acenderia."""
        import inspect

        fonte = inspect.getsource(StatusActionsMixin._render_slow_state)
        assert "_update_coop_badge(state)" in fonte
