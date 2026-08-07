"""LUGAR-À-MESA-01/E0a — o `coop status` diz os DOIS números, nomeados.

A queixa medida em 06/08/2026, com três controles ligados na mesa dela:

    $ hefesto-dualsense4unix coop status
    co-op local: ligado
    jogadores ativos: 1

Um. Com um DualSense, um Pro Controller e um 8BitDo conectados — e os dois
externos já numerados e com o LED aceso pelo próprio daemon. A frase não era
falsa (o co-op conta quem tem controle virtual do Hefesto, e era mesmo um só);
ela era **verdadeira e enganosa**, que é pior, porque não dá à pessoa nenhuma
pista de que existe outra contagem.

O dado certo já estava no fio: `coop.externals` é publicado desde 25/07
(EXT-COUNT-01, `daemon/ipc_handlers.py`), com o comentário que já dizia a
doutrina inteira — *"o número certo não é inflar `players`: é dizer os dois"*.
Doze dias publicado e sem um único leitor.

O que este arquivo trava, e cada linha nasceu de um defeito:

1. **os dois números aparecem, e NOMEADOS** — "jogadores pelo Hefesto" e
   "controles na mesa" são perguntas diferentes e não podem dividir um rótulo;
2. **daemon antigo imprime `—`, nunca `0`** — `0 controles externos` seria
   trocar a mentira velha por uma NOVA, e com mais autoridade, porque tem
   número. Ausência de dado não é zero;
3. **a soma é a mesa inteira** — `players + externals`, senão a segunda linha
   repete a primeira com outro nome;
4. **a ressalva de quem numera dentro do jogo acompanha o número** — a
   LUGAR-À-MESA-01 PROÍBE qualquer boca de prometer que o número aceso é o do
   jogo (seção "O que fica ABERTO", item 1).
"""
from __future__ import annotations

import io
from typing import Any

import pytest
from rich.console import Console
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_coop
from hefesto_dualsense4unix.cli.app import app

runner = CliRunner()


def _texto(players: Any, externals: Any) -> str:
    return "\n".join(cmd_coop.linhas_de_contagem(players, externals))


class TestOsDoisNumerosNomeados:
    """A função pura — é ela que decide o que a boca pode dizer."""

    def test_a_mesa_dela_de_06_08_diz_um_e_tres(self) -> None:
        """1 DualSense adotado + 2 externos = 1 jogador, 3 controles."""
        linhas = cmd_coop.linhas_de_contagem(1, 2)
        assert linhas[0] == "jogadores pelo Hefesto: 1"
        assert linhas[1] == "controles na mesa: 3, sendo 2 externos"

    def test_os_dois_rotulos_sao_distintos(self) -> None:
        """Um rótulo só para duas perguntas foi o defeito inteiro."""
        texto = _texto(1, 2)
        assert "jogadores pelo Hefesto" in texto
        assert "controles na mesa" in texto
        assert "jogadores ativos" not in texto, (
            "o rótulo antigo não pode voltar: ele era a pergunta sem nome"
        )

    def test_um_externo_so_fala_no_singular(self) -> None:
        assert "sendo 1 externo" in _texto(2, 1)
        assert "sendo 1 externos" not in _texto(2, 1)

    def test_a_ressalva_de_quem_numera_acompanha_o_numero(self) -> None:
        """Proibição escrita da sprint: ninguém promete o número do jogo."""
        assert cmd_coop.NOTA_QUEM_NUMERA in _texto(1, 2)

    def test_sem_externo_nenhum_nao_inventa_soma(self) -> None:
        linhas = cmd_coop.linhas_de_contagem(2, 0)
        assert linhas[1] == "controles na mesa: 2 (nenhum externo)"


class TestDaemonAntigoImprimeTravessao:
    """O zero é a mentira nova; o travessão é a verdade sobre o que não se sabe."""

    def test_sem_a_chave_externals_a_mesa_e_travessao(self) -> None:
        linhas = cmd_coop.linhas_de_contagem(1, None)
        assert linhas[1] == f"controles na mesa: {cmd_coop.SEM_DADO}"

    @pytest.mark.parametrize("ausente", [None, "3", 1.5, True, -1])
    def test_nenhum_valor_invalido_vira_zero(self, ausente: Any) -> None:
        """Nem `None`, nem string, nem float, nem `bool`, nem negativo.

        `True` entra na lista de propósito: em Python `isinstance(True, int)`
        é verdadeiro, e um daemon que publicasse um booleano faria a mesa
        virar "1 externo" sem que ninguém tivesse contado nada.
        """
        texto = _texto(1, ausente)
        assert cmd_coop.SEM_DADO in texto
        assert "controles na mesa: 0" not in texto
        assert "0 externos" not in texto

    def test_players_ausente_tambem_e_travessao(self) -> None:
        texto = _texto(None, 2)
        assert f"jogadores pelo Hefesto: {cmd_coop.SEM_DADO}" in texto
        assert "controles na mesa: 2" not in texto, (
            "sem `players` não há soma: 2 seria a contagem de externos "
            "posando de contagem da mesa"
        )


class TestABocaDeVerdade:
    """O comando inteiro, pelo runner — a função pura poderia estar solta."""

    def _rodar(
        self, monkeypatch: pytest.MonkeyPatch, coop: dict[str, Any]
    ) -> str:
        buffer = io.StringIO()
        monkeypatch.setattr(
            cmd_coop, "console", Console(file=buffer, width=200, no_color=True)
        )

        def fake_run_call(
            method: str,
            params: dict[str, Any] | None = None,
            timeout: float | None = None,
        ) -> Any:
            assert method == "daemon.state_full"
            return {"coop": coop}

        monkeypatch.setattr(
            "hefesto_dualsense4unix.app.ipc_bridge._run_call", fake_run_call
        )
        resultado = runner.invoke(app, ["coop", "status"])
        assert resultado.exit_code == 0, resultado.output
        return buffer.getvalue()

    def test_status_imprime_as_duas_linhas(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        saida = self._rodar(
            monkeypatch, {"enabled": True, "players": 1, "externals": 2}
        )
        assert "jogadores pelo Hefesto: 1" in saida
        assert "controles na mesa: 3, sendo 2 externos" in saida

    def test_status_com_daemon_antigo_nao_imprime_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Daemon sem a chave `externals` — o caso de quem não atualizou."""
        saida = self._rodar(monkeypatch, {"enabled": True, "players": 1})
        assert f"controles na mesa: {cmd_coop.SEM_DADO}" in saida
        assert "controles na mesa: 1" not in saida
        assert "0 externos" not in saida
