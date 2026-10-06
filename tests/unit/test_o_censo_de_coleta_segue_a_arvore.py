"""O censo de coleta segue a árvore: nenhum módulo de teste versionado some calado da coleta.

O passo «Censo de coleta» do lint-test comparava o tamanho da coleta com um número escrito
num dia (o piso 8100, de 15/08); a árvore foi de 472 a 1.668 módulos e o número ficou 65%
abaixo dela, de modo que qualquer módulo podia sumir sem o passo ver. O julgamento mora em
`scripts/check_a_coleta_sem_gtk.py` (`julgar`), módulo a módulo, e o `ci.yml` o chama; aqui
ele é medido sobre saídas de coleta sintéticas e, de ponta a ponta, sobre um projeto de
verdade com um `collect_ignore` plantado.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "check_a_coleta_sem_gtk.py"
CI_YML = RAIZ / ".github" / "workflows" / "ci.yml"


def _carregar() -> ModuleType:
    especificacao = importlib.util.spec_from_file_location("censo_de_coleta_sob_teste", SCRIPT)
    assert especificacao and especificacao.loader
    modulo = importlib.util.module_from_spec(especificacao)
    sys.modules[especificacao.name] = modulo
    especificacao.loader.exec_module(modulo)
    return modulo


censo = _carregar()

A, B, C = "tests/unit/test_a.py", "tests/unit/test_b.py", "tests/core/test_c.py"


def _saida(
    nos: dict[str, int],
    *,
    pulados: dict[str, str] | None = None,
    vazios: tuple[str, ...] = (),
    erros: tuple[str, ...] = (),
    erros_do_censo: dict[str, str] | None = None,
    com_censo: bool = True,
) -> str:
    linhas: list[str] = []
    for modulo, n in nos.items():
        linhas += [f"{modulo}::test_{i}" for i in range(n)]
    linhas.append("")
    if com_censo:
        linhas.append("CENSO ativo")
    for modulo, motivo in (pulados or {}).items():
        linhas.append(f"CENSO pulado {modulo} :: {motivo}")
    linhas += [f"CENSO vazio {m}" for m in vazios]
    linhas += [f"CENSO erro {m} :: {c}" for m, c in (erros_do_censo or {}).items()]
    linhas += list(erros)
    return "\n".join(linhas) + "\n"


def test_a_arvore_inteira_presente_passa() -> None:
    queixas, total, pulados = censo.julgar(_saida({A: 3, B: 1, C: 2}), [A, B, C])
    assert queixas == [] and total == 6 and pulados == 0


def test_o_modulo_que_sumiu_reprova_e_e_nomeado_mesmo_com_o_total_enorme() -> None:
    """O número não decide: com 23 mil nós sobrando o módulo que faltou ainda é achado."""
    queixas, total, _ = censo.julgar(_saida({A: 23000, C: 2}), [A, B, C])
    assert total == 23002
    assert any("SUMIRAM" in q for q in queixas) and f"  {B}" in queixas
    assert f"  {A}" not in queixas and f"  {C}" not in queixas


def test_o_pulo_com_motivo_passa() -> None:
    saida = _saida(
        {A: 1}, pulados={B: "GUARDA-GI-REAL-01: PyGObject real ausente [importa a interface]"}
    )
    queixas, _, pulados = censo.julgar(saida, [A, B])
    assert queixas == [] and pulados == 1


def test_o_pulo_sem_motivo_reprova() -> None:
    queixas, _, _ = censo.julgar(_saida({A: 1}, pulados={B: ""}), [A, B])
    assert any("SEM motivo" in q and B in q for q in queixas)


def test_o_erro_de_coleta_continua_reprovando_e_nao_vira_modulo_sumido() -> None:
    causa = "ModuleNotFoundError: No module named 'gi'"
    for saida in (
        _saida({A: 1}, erros_do_censo={B: causa}),  # a linha do plugin, que não depende do `-r`
        _saida({A: 1}, erros=(f"ERROR {B} - {causa}",)),  # o resumo do pytest, quando o `-r` o pede
    ):
        queixas, _, _ = censo.julgar(saida, [A, B])
        assert any("não coletam sem o GTK" in q for q in queixas)
        assert any(q.startswith(f"  {B} :: ") and "No module named 'gi'" in q for q in queixas)
        assert not any("SUMIRAM" in q for q in queixas), (
            "o erro já foi dito; dizê-lo de novo como «sumiu» confunde"
        )


def test_o_modulo_sem_nenhum_teste_reprova() -> None:
    queixas, _, _ = censo.julgar(_saida({A: 1}, vazios=(B,)), [A, B])
    assert any("NENHUM teste" in q for q in queixas) and f"  {B}" in queixas


def test_a_saida_sem_o_censo_nao_vale() -> None:
    """Sem o plugin, pulado e sumido se leem igual: a saída não pode ser julgada só pelos nós."""
    queixas, _, _ = censo.julgar(_saida({A: 1, B: 1}, com_censo=False), [A, B])
    assert any("não traz o censo" in q for q in queixas)


def test_coleta_que_nao_coletou_nada_reprova() -> None:
    queixas, total, _ = censo.julgar("CENSO ativo\n", [A])
    assert total == 0 and any("não coletou nada" in q for q in queixas)


def test_o_julgamento_so_olha_o_que_o_git_versiona() -> None:
    versionados = censo.versionados()
    assert versionados and all(
        p.startswith("tests/") and Path(p).name.startswith("test_") for p in versionados
    )
    assert "tests/conftest.py" not in versionados
    assert (RAIZ / versionados[0]).is_file()


# --- o passo do ci.yml ---------------------------------------------------------------------------


def _passo_do_censo() -> dict[str, Any]:
    jobs = yaml.safe_load(CI_YML.read_text(encoding="utf-8"))["jobs"]
    achados = [p for p in jobs["lint-test"]["steps"] if "Censo de coleta" in str(p.get("name", ""))]
    assert len(achados) == 1, "o lint-test tem de ter UM passo «Censo de coleta»"
    passo: dict[str, Any] = achados[0]
    return passo


def test_o_ci_chama_o_dono_do_julgamento_e_nao_tem_numero() -> None:
    corpo = _passo_do_censo()["run"]
    assert "scripts/check_a_coleta_sem_gtk.py --julgar" in corpo
    assert "-p scripts.check_a_coleta_sem_gtk" in corpo, "sem o plugin a saída não traz o censo"
    assert not re.search(r"\bPISO\s*=", corpo) and not re.search(
        r"-lt\s+\$\{?[A-Z_]*PISO", corpo
    ), "o passo voltou a julgar por um número escrito à mão"
    assert not re.search(r"\b\d{4,5}\b", corpo), f"número escrito no passo do censo: {corpo}"


def test_o_ci_ainda_reprova_o_erro_de_coleta_pelo_dono() -> None:
    """O passo não tem `|| true` no julgamento: o código de saída do script É o do passo."""
    ultima = [ln for ln in _passo_do_censo()["run"].splitlines() if ln.strip()][-1]
    assert "check_a_coleta_sem_gtk.py --julgar" in ultima and "||" not in ultima


# --- de ponta a ponta, num projeto de verdade ---------------------------------------------


def _projeto(
    base: Path, *, ignorar_no_conftest: str | None = None, quebrado: bool = False
) -> list[str]:
    tests = base / "tests"
    (tests / "unit").mkdir(parents=True)
    (tests / "__init__.py").write_text("", encoding="utf-8")
    (tests / "unit" / "__init__.py").write_text("", encoding="utf-8")
    (tests / "unit" / "test_a.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
    (tests / "unit" / "test_pulado.py").write_text(
        "import pytest\n"
        'pytest.importorskip("modulo_que_nao_existe_em_lugar_nenhum", reason="falta o pacote")\n'
        "def test_x():\n    assert True\n",
        encoding="utf-8",
    )
    (tests / "unit" / "test_que_vai_sumir.py").write_text(
        "def test_s():\n    assert True\n", encoding="utf-8"
    )
    # o pulo de módulo inteiro pela guarda do conftest, como o `exigir_gi_real()`:
    # o `-rs` o aponta para o conftest
    (tests / "unit" / "test_guardado.py").write_text(
        "from tests.conftest import guarda\nguarda()\ndef test_g():\n    assert True\n",
        encoding="utf-8",
    )
    ignorados = f"collect_ignore = [{ignorar_no_conftest!r}]\n" if ignorar_no_conftest else ""
    (tests / "conftest.py").write_text(
        "import pytest\n"
        + ignorados
        + "def guarda():\n"
        + "    pytest.skip('a interface não roda sem o GTK real', allow_module_level=True)\n",
        encoding="utf-8",
    )
    if quebrado:  # o `import gi` sem guarda: o furo que o CI vê e a máquina do usuário não
        (tests / "unit" / "test_quebrado.py").write_text(
            "import modulo_de_interface_que_o_runner_nao_tem\n\n\ndef test_q():\n    assert True\n",
            encoding="utf-8",
        )
    return [
        "tests/unit/test_a.py",
        "tests/unit/test_pulado.py",
        "tests/unit/test_que_vai_sumir.py",
        "tests/unit/test_guardado.py",
    ]


def _coletar(base: Path) -> str:
    ambiente = {"PYTHONPATH": f"{base}:{RAIZ}", "PATH": "/usr/bin:/bin", "HOME": str(base)}
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests",
            "--collect-only",
            "-q",
            "-rs",  # o `-r` com só o `s` tira o resumo padrão `fE`: o erro tem de vir do plugin
            "--continue-on-collection-errors",
            "-p",
            "no:cacheprovider",
            "-p",
            censo.PLUGIN,
        ],
        cwd=base,
        env=ambiente,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    ).stdout


def test_de_ponta_a_ponta_o_pulo_passa_e_o_modulo_no_collect_ignore_e_nomeado(
    tmp_path: Path,
) -> None:
    modulos = _projeto(tmp_path / "limpo")
    saida = _coletar(tmp_path / "limpo")
    queixas, total, pulados = censo.julgar(saida, modulos)
    assert queixas == [] and total == 2 and pulados == 2, saida
    # o pulo da guarda do conftest volta ao módulo certo, com a razão
    # (o `-rs` sozinho o apontaria para o conftest)
    assert (
        "CENSO pulado tests/unit/test_guardado.py :: a interface não roda sem o GTK real" in saida
    )
    assert "CENSO pulado tests/unit/test_pulado.py :: " in saida

    modulos = _projeto(tmp_path / "sujo", ignorar_no_conftest="unit/test_que_vai_sumir.py")
    saida = _coletar(tmp_path / "sujo")
    assert "test_que_vai_sumir" not in saida.replace("CENSO", ""), (
        "o collect_ignore não tirou o módulo da coleta"
    )
    queixas, total, _ = censo.julgar(saida, modulos)
    assert total == 1
    assert "  tests/unit/test_que_vai_sumir.py" in queixas, queixas


def test_de_ponta_a_ponta_o_import_sem_guarda_reprova_com_a_causa_e_sem_o_r_do_pytest(
    tmp_path: Path,
) -> None:
    """Sem `-r` o pytest não escreve o resumo `fE`: o erro tem de vir do plugin."""
    modulos = _projeto(tmp_path / "quebrado", quebrado=True)
    saida = _coletar(tmp_path / "quebrado")
    assert "ERROR tests/unit/test_quebrado.py" not in saida, "o teste deixou de medir sem o resumo"
    queixas, _, _ = censo.julgar(saida, [*modulos, "tests/unit/test_quebrado.py"])
    assert any("não coletam sem o GTK" in q for q in queixas), queixas
    assert any(
        q.startswith("  tests/unit/test_quebrado.py :: ") and "modulo_de_interface" in q
        for q in queixas
    ), queixas
    assert not any("SUMIRAM" in q for q in queixas)
