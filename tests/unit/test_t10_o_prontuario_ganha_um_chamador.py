"""T-10 (SISTEMA-O-VIGIA-VIVO-01) — 1.037 linhas, zero chamadores."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_t10_o_prontuario_ganha_um_chamador: importa código da janela GTK")

from dataclasses import dataclass, field

from hefesto_dualsense4unix.app.actions.daemon_actions import (
    interpretar_prontuario_dos_jogos,
    medir_prontuario_dos_jogos,
)


@dataclass
class _JogoFalso:
    """Só os dois atributos que a linha do cartão lê."""

    nome: str
    ponte_divergente: bool = False


@dataclass
class _CensoFalso:
    jogos: list[_JogoFalso] = field(default_factory=list)


class TestOCartaoSoFalaQuandoHaDivergencia:
    def test_sem_jogo_nenhum_fica_calado(self) -> None:
        assert interpretar_prontuario_dos_jogos(_CensoFalso()) is None

    def test_tudo_alinhado_fica_calado(self) -> None:
        """A metade que impede o cartão de virar paisagem."""
        censo = _CensoFalso(
            jogos=[_JogoFalso("Sackboy"), _JogoFalso("Pragmata")]
        )

        assert interpretar_prontuario_dos_jogos(censo) is None

    def test_divergencia_vira_aviso_com_o_nome_do_jogo(self) -> None:
        """A mordida: nomeia, nunca só conta."""
        censo = _CensoFalso(
            jogos=[
                _JogoFalso("Sackboy"),
                _JogoFalso("DON'T SCREAM", ponte_divergente=True),
            ]
        )

        achado = interpretar_prontuario_dos_jogos(censo)

        assert achado is not None
        tag, texto = achado
        assert tag == "[WARN]"
        assert "DON'T SCREAM" in texto
        assert "Sackboy" not in texto

    def test_a_frase_diz_o_que_fazer(self) -> None:
        """Regra desta casa: o quê, por quê e o que fazer."""
        censo = _CensoFalso(jogos=[_JogoFalso("Pragmata", ponte_divergente=True)])

        _, texto = interpretar_prontuario_dos_jogos(censo)  # type: ignore[misc]

        assert "aba Perfis" in texto
        assert "caixinha" in texto

    def test_muitos_divergentes_nomeiam_tres_e_contam_o_resto(self) -> None:
        """O cartão não pode virar uma parede de nomes — nem esconder o total."""
        censo = _CensoFalso(
            jogos=[
                _JogoFalso(f"Jogo {i}", ponte_divergente=True) for i in range(5)
            ]
        )

        _, texto = interpretar_prontuario_dos_jogos(censo)  # type: ignore[misc]

        assert "Jogo 0" in texto
        assert "e mais 2" in texto


class TestNuncaDerrubaOResto:
    """Best-effort: o cartão inteiro não pode cair por causa desta linha."""

    def test_censo_estranho_nao_levanta(self) -> None:
        """Objeto sem `jogos` — daemon velho, dublê antigo, o que for."""
        assert interpretar_prontuario_dos_jogos(object()) is None
        assert interpretar_prontuario_dos_jogos(None) is None

    def test_jogo_sem_os_atributos_nao_levanta(self) -> None:
        censo = _CensoFalso()
        censo.jogos = [object()]  # type: ignore[list-item]

        assert interpretar_prontuario_dos_jogos(censo) is None

    def test_censo_que_explode_vira_silencio(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """Sem Steam instalada, sem perfis, disco ilegível: calado, não vermelho."""
        from hefesto_dualsense4unix.integrations import prontuario_dos_jogos

        def _explode(*_a: object, **_kw: object) -> None:
            raise OSError("sem Steam por aqui")

        monkeypatch.setattr(prontuario_dos_jogos, "levantar_censo", _explode)

        assert medir_prontuario_dos_jogos() is None


class TestOModuloDeixouDeSerOrfao:
    def test_o_prontuario_tem_chamador_de_producao(self) -> None:
        """A mordida da OUTRA metade: o órfão deixou de ser órfão."""
        import ast
        from pathlib import Path

        from hefesto_dualsense4unix.app.actions import daemon_actions

        fonte = Path(daemon_actions.__file__).read_text(encoding="utf-8")
        importa = [
            no
            for no in ast.walk(ast.parse(fonte))
            if isinstance(no, ast.ImportFrom)
            and no.module == "hefesto_dualsense4unix.integrations"
            and any(a.name == "prontuario_dos_jogos" for a in no.names)
        ]

        assert importa, (
            "a aba Sistema voltou a não chamar o prontuário — 1.037 linhas "
            "sem chamador de produção é a família F2, e este módulo já passou "
            "um mês assim"
        )

    def test_o_cartao_de_saude_consulta_o_prontuario(self) -> None:
        """O import não basta: o cartão tem de CHAMAR a medição."""
        import inspect

        from hefesto_dualsense4unix.app.actions.daemon_actions import (
            DaemonActionsMixin,
        )

        corpo = inspect.getsource(DaemonActionsMixin._refresh_storm_diag)

        assert "medir_prontuario_dos_jogos()" in corpo
