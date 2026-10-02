"""CARONA-NO-GUARD-01 (16/08/2026) — o vigia já acordava na hora certa."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE = REPO_ROOT / "assets" / "hefesto-steam-input-guard.service"
PATH_UNIT = REPO_ROOT / "assets" / "hefesto-steam-input-guard.path"
INSTALL = REPO_ROOT / "install.sh"
SENTINELA = (
    REPO_ROOT / "src" / "hefesto_dualsense4unix" / "integrations" / "sentinela_do_wrapper.py"
)


@pytest.fixture(scope="module")
def service() -> str:
    return SERVICE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def execstarts(service: str) -> list[str]:
    return [
        linha.split("=", 1)[1].strip()
        for linha in service.splitlines()
        if linha.startswith("ExecStart=")
    ]


class TestOSegundoPasso:
    def test_o_guard_repoe_o_wrapper(self, execstarts: list[str]) -> None:
        """A MORDIDA. Sem este passo, o Pragmata volta a ficar quebrado calado."""
        assert len(execstarts) >= 2, execstarts
        assert "__SENTINELA__" in execstarts[1]
        assert "--reparar" in execstarts[1]

    def test_o_steam_input_continua_sendo_o_primeiro(self, execstarts: list[str]) -> None:
        """A ordem é a de sempre: o passo que já existia não foi deslocado."""
        assert "__SCRIPT__" in execstarts[0]
        assert "--apply-quiet" in execstarts[0]

    def test_adiar_nao_pode_derrubar_o_guard(self, service: str) -> None:
        """O `-` é o que separa "adiei" de "quebrei"."""
        assert re.search(r"^ExecStart=-/usr/bin/env python3 __SENTINELA__", service, re.M)

    def test_roda_no_python3_do_sistema(self, execstarts: list[str]) -> None:
        """O guard não tem venv. A sentinela é stdlib pura justamente por isto."""
        assert "python3" in execstarts[1]
        texto = SENTINELA.read_text(encoding="utf-8")
        assert "100% stdlib" in texto


class TestOGatilhoQueJaExistia:
    def test_o_path_unit_vigia_o_userdata(self) -> None:
        """É o `userdata` que a Steam reescreve ao sair — a hora certa de repor."""
        texto = PATH_UNIT.read_text(encoding="utf-8")
        assert texto.count("PathChanged=") >= 3
        assert "userdata" in texto

    def test_nenhum_unit_novo_foi_criado_para_isto(self) -> None:
        """A carona é o ponto: reaproveitar o gatilho, não multiplicar units."""
        novos = list((REPO_ROOT / "assets").glob("*wrapper*.path")) + list(
            (REPO_ROOT / "assets").glob("*wrapper*.timer")
        )
        assert novos == []


@pytest.fixture(scope="module")
def instalador() -> str:
    return INSTALL.read_text(encoding="utf-8")


class TestOInstallRenderizaOsDois:

    def test_o_placeholder_novo_e_substituido(self, instalador: str) -> None:
        """A MORDIDA do install: sem esta linha, o unit sai com `__SENTINELA__` cru."""
        assert "s#__SENTINELA__#" in instalador

    def test_o_caminho_apontado_existe_no_repositorio(self, instalador: str) -> None:
        achado = re.search(
            r"SENTINELA_PY=\"\$\{ROOT_DIR\}/([^\"]+)\"", instalador
        )
        assert achado is not None, "o install precisa dizer QUAL arquivo é a sentinela"
        assert (REPO_ROOT / achado.group(1)).is_file()

    def test_os_dois_placeholders_no_mesmo_sed(self, instalador: str) -> None:
        """Dois `sed` em sequência já deixaram um placeholder cru nesta casa."""
        trecho = instalador.split("hefesto-steam-input-guard.service", 1)[0][-600:]
        assert trecho.count("-e ") >= 2

    def test_a_cura_entra_sem_flag(self, instalador: str) -> None:
        """Regra dela, 08/08: nada à mão, nada opt-in."""
        pedaco = instalador.split("SENTINELA_PY=", 1)[1][:400]
        assert "--enable" not in pedaco
        assert "--with-wrapper" not in pedaco
