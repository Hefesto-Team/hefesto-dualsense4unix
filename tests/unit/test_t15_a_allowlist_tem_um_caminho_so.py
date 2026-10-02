"""T-15 (SISTEMA-O-VIGIA-VIVO-01) — a allowlist do Steam Input tem UM caminho."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

NOME_DO_ARQUIVO = "steam_input_apps.txt"

DONO_DO_CAMINHO = SRC / "integrations" / "steam_launch_options.py"

LEITORES_EM_SHELL = (
    RAIZ / "scripts" / "disable_steam_input.sh",
    RAIZ / "scripts" / "doctor.sh",
)

EXPANSAO_XDG = "${XDG_CONFIG_HOME:-$HOME/.config}"


class TestOsResolvedoresConcordam:
    """A igualdade que a divergência de 23/08 quebrava."""

    def _caminhos(self) -> dict[str, Path]:
        from hefesto_dualsense4unix.integrations.steam_launch_options import (
            steam_input_allowlist_path,
        )
        from hefesto_dualsense4unix.integrations.storm_doctor import _allowlist_path

        return {
            "storm_doctor._allowlist_path": _allowlist_path(),
            "steam_input_allowlist_path": steam_input_allowlist_path(),
        }

    def test_com_xdg_config_home_os_dois_apontam_para_o_mesmo_arquivo(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """O cenário exato do achado de 18h31 de 23/08."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))

        caminhos = self._caminhos()
        assert len(set(caminhos.values())) == 1, caminhos
        assert str(tmp_path / "cfg") in str(next(iter(caminhos.values())))

    def test_sem_xdg_config_home_os_dois_continuam_iguais(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A régua tem de valer também no caminho de produção (HOME puro)."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "casa"))

        caminhos = self._caminhos()
        assert len(set(caminhos.values())) == 1, caminhos
        assert str(tmp_path / "casa") in str(next(iter(caminhos.values())))

    def test_o_daemon_le_o_mesmo_arquivo_que_a_janela_escreve(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """O elo que faltava: `launch_env.steam_input_appids`."""
        from hefesto_dualsense4unix.daemon import launch_env
        from hefesto_dualsense4unix.integrations.steam_launch_options import (
            steam_input_allowlist_path,
        )

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
        destino = steam_input_allowlist_path()
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text("2111190\n# comentário\n", encoding="utf-8")

        assert launch_env.steam_input_appids() == {2111190}


class TestNinguemMontaOCaminhoPorContaPropria:
    """O portão que impede o sexto resolvedor de nascer de novo."""

    def _linhas_de_codigo_com_o_nome(self, arquivo: Path) -> list[str]:
        """Strings que SÃO o caminho da allowlist — não as que o mencionam."""
        texto = arquivo.read_text(encoding="utf-8")
        if NOME_DO_ARQUIVO not in texto:
            return []

        docstrings: set[int] = set()
        arvore = ast.parse(texto)
        for no in ast.walk(arvore):
            if not isinstance(
                no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                continue
            corpo = getattr(no, "body", [])
            if (
                corpo
                and isinstance(corpo[0], ast.Expr)
                and isinstance(corpo[0].value, ast.Constant)
                and isinstance(corpo[0].value.value, str)
            ):
                alvo = corpo[0]
                fim = alvo.end_lineno or alvo.lineno
                docstrings.update(range(alvo.lineno, fim + 1))

        achados: list[str] = []
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Constant) or not isinstance(no.value, str):
                continue
            valor = no.value
            if valor != NOME_DO_ARQUIVO and not valor.endswith(
                "/" + NOME_DO_ARQUIVO
            ):
                continue
            if no.lineno in docstrings:
                continue
            achados.append(
                f"{arquivo.relative_to(RAIZ)}:{no.lineno}: {valor!r}"
            )
        return achados

    def test_so_o_dono_escreve_o_nome_do_arquivo_em_codigo(self) -> None:
        """Todo o resto chama `steam_input_allowlist_path()`."""
        infratores: list[str] = []
        for arquivo in sorted(SRC.rglob("*.py")):
            if arquivo == DONO_DO_CAMINHO:
                continue
            infratores.extend(self._linhas_de_codigo_com_o_nome(arquivo))

        assert not infratores, (
            "código montando o caminho da allowlist fora de "
            f"{DONO_DO_CAMINHO.relative_to(RAIZ)}:\n  "
            + "\n  ".join(infratores)
            + "\n\nChame `steam_input_allowlist_path()`. Dois resolvedores do "
            "mesmo caminho divergem em silêncio — o botão grava num arquivo, "
            "a tela lê outro, e ninguém vê erro nenhum."
        )

    def test_o_dono_realmente_define_o_caminho(self) -> None:
        """Régua que sabe ACEITAR: o dono existe e é ele mesmo."""
        texto = DONO_DO_CAMINHO.read_text(encoding="utf-8")
        assert NOME_DO_ARQUIVO in texto
        assert "def steam_input_allowlist_path" in texto


class TestOsLeitoresEmShellRespeitamOXdg:
    @pytest.mark.parametrize(
        "script", LEITORES_EM_SHELL, ids=lambda p: p.name
    )
    def test_shell_expande_xdg_config_home(self, script: Path) -> None:
        """`$HOME/.config` cravado no shell é a mesma divergência, de novo."""
        linhas = [
            linha.strip()
            for linha in script.read_text(encoding="utf-8").splitlines()
            if NOME_DO_ARQUIVO in linha and not linha.lstrip().startswith("#")
        ]
        assert linhas, f"{script.name} deixou de ler a allowlist?"
        for linha in linhas:
            assert EXPANSAO_XDG in linha, (
                f"{script.name} monta o caminho da allowlist sem respeitar "
                f"XDG_CONFIG_HOME:\n  {linha}"
            )
