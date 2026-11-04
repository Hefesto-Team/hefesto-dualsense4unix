"""O portão pytest grava o `rc` do pytest ao lado do `rc` do invólucro (vaga, bus e tela).

Medido em 01/11/2026 (ci-local, job GTK real): `portao-tem-chamador VERMELHO rc=1` com a saída
terminando em `11 passed in 0.64s`, e as outras três pernas `ok`. O `portoes.sh` só guardava o `rc`
da cadeia inteira (`vez-do-pytest.sh` > `dbus-run-session` > `xvfb-run` > `pytest`). Agora o `bash`
mais interno grava o `rc` do pytest ao lado; se o invólucro sai com outro, isso fica escrito na
saída do portão e na corrida (`involucro-mentiu.txt`), que é o instrumento para provar a causa.

O portão reprova se qualquer um dos dois sai com erro: o invólucro que mente não se esconde.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[2]
TABELA = "rapido|pytest-tela|pytest|tests/test_tela.py"


def _paralelo() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_portoes_em_paralelo_do_rc",
        RAIZ / "tests" / "unit" / "test_os_portoes_rodam_em_paralelo.py",
    )
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_portoes_em_paralelo_do_rc"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _corre(
    tmp_path: Path, involucro: str, *, tela: str = "limpo\n", portoes: str | None = None
) -> tuple[dict[str, str], str]:
    """Roda o portão pytest atrás de um semáforo de mentira; devolve (status, saída da corrida)."""
    paralelo = _paralelo()
    vez = tmp_path / "vez-do-pytest.sh"
    vez.write_text("#!/usr/bin/env bash\n" + involucro, encoding="utf-8")
    repo = paralelo._monta(tmp_path, TABELA, arquivos={"dados/tela.txt": tela}, portoes=portoes)
    r = paralelo._corre(repo, "--rapido", "--sem-memoria", env={"HEFESTO_VEZ_DO_PYTEST": str(vez)})
    return paralelo._status(r.stdout), r.stdout


def test_o_involucro_com_1_e_o_pytest_verde_reprova_e_diz_a_camada(tmp_path: Path) -> None:
    status, saida = _corre(tmp_path, '"$@"\nexit 1\n')

    assert status == {"pytest-tela": "VERMELHO"}, saida
    assert "invólucro com rc diferente do pytest" in saida, saida
    assert "pytest-tela rc=1" in saida, saida


def test_o_pytest_vermelho_reprova_mesmo_com_o_involucro_saindo_com_0(tmp_path: Path) -> None:
    status, saida = _corre(tmp_path, '"$@"\nexit 0\n', tela="MORDIDA\n")

    assert status == {"pytest-tela": "VERMELHO"}, saida


def test_o_pytest_vermelho_reprova_com_o_involucro_igual(tmp_path: Path) -> None:
    status, saida = _corre(tmp_path, 'exec "$@"\n', tela="MORDIDA\n")

    assert status == {"pytest-tela": "VERMELHO"}, saida
    assert "invólucro com rc diferente" not in saida, saida


def test_o_involucro_que_cai_antes_de_o_pytest_rodar_reprova(tmp_path: Path) -> None:
    """Sem o `rc` do pytest gravado, vale o da cadeia: o portão nem chegou a rodar."""
    status, saida = _corre(tmp_path, "exit 1\n")

    assert status == {"pytest-tela": "VERMELHO"}, saida


def test_morde_o_pytest_vermelho_atras_do_involucro_verde(tmp_path: Path) -> None:
    """A mordida: sem ler o `rc` do pytest, o invólucro de `rc` 0 esconde o pytest vermelho."""
    texto = (RAIZ / "scripts" / "portoes.sh").read_text(encoding="utf-8")
    velho = '      [ "$prc" != 0 ] && [ "$rc" -eq 0 ] && rc=1\n'
    assert texto.count(velho) == 1
    status, saida = _corre(
        tmp_path, '"$@"\nexit 0\n', tela="MORDIDA\n", portoes=texto.replace(velho, "      :\n")
    )

    assert status == {"pytest-tela": "ok"}, saida
