"""T-04 (SISTEMA-O-VIGIA-VIVO-01) — "Travar Proton validado" e a recusa muda.

Medido em 23/08: `lock_games_to_pinned_proton` devolvia
``status="recusado"`` com o motivo, e `lock_proton_for_all_games` traduzia o
retorno **jogando os dois fora** — sobrava
``"errors": 1 if status == "erro" else 0``, e recusa não é erro para essa
conta. O dicionário que chegava à tela era ``{locked:0, skipped:0,
errors:0}``, byte-idêntico ao de *"não havia nada a fazer"*, e o ramo
``elif errors == 0`` de `format_proton_lock_result` respondia:

    Nada a mudar — os jogos já estão no Proton validado (GE-Proton10-34)…

logo depois de o gate ter recusado por causa de um jogo aberto. **A verdade
estava calculada e a ponte a descartava** — a família F1 na forma mais pura.

O vocabulário da recusa não é novo: é o mesmo de `_frase_steam_input`, na
mesma aba (*"NÃO mudou — havia um jogo aberto."*). Um botão que inventasse o
seu ensinaria a usuária a decifrar duas maneiras de dizer a mesma coisa.
"""
from __future__ import annotations

import pytest

from hefesto_dualsense4unix.app.actions.daemon_actions import (
    format_proton_lock_result,
)

#: O dicionário EXATO que a recusa produzia antes da cura — as três contagens
#: em zero. Ele é o corpo de delito: nada aqui distingue recusa de "nada a
#: fazer", e é por isso que `status` precisou atravessar a ponte.
RECUSA_COMO_ERA = {"locked": 0, "skipped": 0, "errors": 0, "tool": "GE-Proton10-34"}


class TestARecusaNaoViraComemoracao:
    @pytest.mark.parametrize(
        "motivo, pedaco_esperado",
        [
            ("jogo_da_steam_aberto", "havia um jogo aberto"),
            ("steam_aberta", "a Steam continuou aberta"),
        ],
    )
    def test_recusa_diz_o_motivo_em_portugues(
        self, motivo: str, pedaco_esperado: str
    ) -> None:
        """Os dois motivos que o `_steam_gate` sabe devolver."""
        frase = format_proton_lock_result(
            {**RECUSA_COMO_ERA, "status": "recusado", "reason": motivo}
        )

        assert pedaco_esperado in frase
        assert "já estão travados" not in frase
        assert "já estão no Proton validado" not in frase

    def test_recusa_diz_o_que_fazer_a_seguir(self) -> None:
        """Regra desta casa: o quê, por quê e O QUE FAZER.

        Uma recusa que só recusa deixa a pessoa parada na frente do botão.
        """
        frase = format_proton_lock_result(
            {
                **RECUSA_COMO_ERA,
                "status": "recusado",
                "reason": "jogo_da_steam_aberto",
            }
        )

        assert "clique de novo" in frase

    def test_motivo_desconhecido_nao_inventa_causa(self) -> None:
        """`_steam_gate` pode ganhar um motivo novo; a frase não pode chutar.

        Dizer "havia um jogo aberto" para um motivo que a tela não conhece
        seria trocar uma mentira por outra. A frase confessa a recusa e manda
        para os Detalhes técnicos.
        """
        frase = format_proton_lock_result(
            {**RECUSA_COMO_ERA, "status": "recusado", "reason": "motivo_do_futuro"}
        )

        assert "NÃO travei nada" in frase
        assert "Detalhes técnicos" in frase
        assert "jogo aberto" not in frase
        assert "já estão no Proton validado" not in frase


class TestOsOutrosDesfechosNaoMudaram:
    """A régua tem de saber ACEITAR — senão vira "tudo é recusa"."""

    def test_nada_a_fazer_de_verdade_continua_dizendo_nada_a_fazer(self) -> None:
        """`status="noop"` é o caso REAL de "já estavam travados".

        Se a cura tivesse transformado toda contagem zerada em recusa, ela
        teria trocado uma mentira por outra na direção oposta.
        """
        frase = format_proton_lock_result(
            {**RECUSA_COMO_ERA, "status": "noop", "reason": "ja_travado"}
        )

        assert "Nada a mudar" in frase
        assert "NÃO travei nada" not in frase

    def test_sucesso_continua_comemorando(self) -> None:
        frase = format_proton_lock_result(
            {
                "locked": 3,
                "skipped": 0,
                "errors": 0,
                "status": "locked",
                "reason": "",
                "tool": "GE-Proton10-34",
            }
        )

        assert "Pronto" in frase
        assert "3 jogo(s)" in frase

    def test_dicionario_sem_status_se_comporta_como_antes(self) -> None:
        """Compatibilidade: `status` é opcional no contrato.

        Um chamador antigo (ou um teste de terceiro) que ainda não manda a
        chave não pode passar a receber recusa por omissão.
        """
        frase = format_proton_lock_result(RECUSA_COMO_ERA)

        assert "Nada a mudar" in frase


class TestOStatusAtravessaAPonte:
    """O outro lado da cura: `lock_proton_for_all_games` para de jogar fora."""

    def test_o_tradutor_repassa_status_e_reason(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Sem estas duas chaves, a frase de cima nunca teria o que ler."""
        from hefesto_dualsense4unix.integrations import proton_pin

        monkeypatch.setattr(
            proton_pin, "_load_conf", lambda _p: {"name": "GE-Proton10-34"}
        )
        monkeypatch.setattr(proton_pin, "list_installed_appids", lambda _h: ["440"])
        monkeypatch.setattr(
            proton_pin,
            "lock_games_to_pinned_proton",
            lambda **_kw: {
                "status": "recusado",
                "reason": "jogo_da_steam_aberto",
                "changes": {},
                "vdf": "/tmp/config.vdf",
                "backup": "",
            },
        )

        saida = proton_pin.lock_proton_for_all_games()

        assert saida["status"] == "recusado"
        assert saida["reason"] == "jogo_da_steam_aberto"
        # E o caminho inteiro, ponta a ponta: o que o botão realmente exibe.
        assert "havia um jogo aberto" in format_proton_lock_result(saida)
