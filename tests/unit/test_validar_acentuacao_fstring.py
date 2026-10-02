"""Regressão PORTÃO-VIVO-01 Bloco A: o gate de acento era cego a f-string."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tokenize
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "validar-acentuacao.py"


def _carrega_validador():
    """Carrega scripts/validar-acentuacao.py como módulo (o nome tem hífen)."""
    spec = importlib.util.spec_from_file_location("validar_acentuacao", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["validar_acentuacao"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


validador = _carrega_validador()


def _roda(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )


@pytest.fixture()
def sandbox(tmp_path: Path) -> Path:
    """Repositório de mentira, para o modo --all achar uma raiz própria."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    return tmp_path


def _escreve(sandbox: Path, nome: str, conteudo: str) -> Path:
    alvo = sandbox / nome
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(conteudo, encoding="utf-8")
    return alvo


# desta casa. Cada linha carrega o `noqa` para não acusar o próprio arquivo.
_LINHA_FSTRING = 'msg = f"a configuracao nao tem acao"\n'  # fixture errada (noqa-acento)
_LINHA_STRING = 'msg =  "a configuracao nao tem acao"\n'  # fixture errada (noqa-acento)


def test_fstring_com_erro_de_acento_reprova(sandbox: Path) -> None:
    """O caso exato do sprint: erro dentro de f-string tem de ser visto."""
    alvo = _escreve(sandbox, "src/exemplo.py", _LINHA_FSTRING)

    res = _roda(["--check-file", str(alvo)], sandbox)

    assert res.returncode == 1, (
        "f-string com erro de acentuação passou batido:\n"
        + res.stdout
        + res.stderr
    )
    for errada in ("configuracao", "nao", "acao"):  # fixture errada (noqa-acento)
        assert f":{errada} " in res.stdout, (
            f"o gate não apontou {errada!r} dentro da f-string:\n" + res.stdout
        )


def test_fstring_e_string_normal_pesam_igual(sandbox: Path) -> None:
    """A assimetria É o defeito: o mesmo texto errado, dois pesos."""
    so_fstring = _escreve(sandbox, "src/a.py", _LINHA_FSTRING)
    so_string = _escreve(sandbox, "src/b.py", _LINHA_STRING)

    saida_f = _roda(["--check-file", str(so_fstring)], sandbox).stdout
    saida_s = _roda(["--check-file", str(so_string)], sandbox).stdout

    achados_f = sorted(li.split(":")[-1] for li in saida_f.splitlines() if "->" in li)
    achados_s = sorted(li.split(":")[-1] for li in saida_s.splitlines() if "->" in li)

    assert achados_f == achados_s, (
        "f-string e string normal foram medidas com pesos diferentes.\n"
        f"f-string: {achados_f}\nstring:   {achados_s}"
    )
    assert achados_s, "a fixture parou de errar — o teste virou tautologia"


def test_nome_de_variavel_dentro_das_chaves_nao_vira_apontamento(
    sandbox: Path,
) -> None:
    """A correção não pode ser larga demais."""
    fonte = (
        "producao = 1\n"  # fixture errada (noqa-acento)
        "acao = 2\n"  # fixture errada (noqa-acento)
        "sessao = 3\n"  # fixture errada (noqa-acento)
        'msg = f"{producao} {acao} {sessao}"\n'  # fixture errada (noqa-acento)
        'esp = f"{sessao!r:>{producao}}"\n'  # fixture errada (noqa-acento)
    )
    alvo = _escreve(sandbox, "src/nomes.py", fonte)

    res = _roda(["--check-file", str(alvo)], sandbox)

    assert res.returncode == 0, (
        "nome de variável dentro das chaves virou violação de acentuação:\n"
        + res.stdout
        + res.stderr
    )


def test_mascara_sobrevive_a_tokenize_sem_fstring_middle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simula o 3.11, onde `tokenize.FSTRING_MIDDLE` não existe."""
    monkeypatch.delattr(tokenize, "FSTRING_MIDDLE", raising=False)

    conteudo = _LINHA_STRING
    linhas = conteudo.splitlines()

    mascarado = validador._mascara_codigo_python(conteudo, linhas)

    assert "configuracao" in mascarado[0], (  # fixture errada (noqa-acento)
        "sem FSTRING_MIDDLE o mascaramento parou de devolver a string normal: "
        f"{mascarado!r}"
    )


def test_all_enxerga_arquivo_novo_ainda_nao_adicionado(sandbox: Path) -> None:
    """Bônus do Bloco A: `git ls-files -z` puro só lista o índice."""
    _escreve(sandbox, "src/recem_nascido.py", _LINHA_STRING)

    res = _roda(["--all"], sandbox)

    assert res.returncode == 1, (
        "--all deu verde num arquivo novo fora do índice:\n"
        + res.stdout
        + res.stderr
    )
    assert "recem_nascido.py" in res.stdout, res.stdout + res.stderr


def test_o_codigo_longe_da_chave_tem_a_mesma_resposta_nas_tres_versoes(
    sandbox: Path,
) -> None:
    """25/09/2026: o 3.10, o 3.11 e o 3.12 dizem a mesma coisa."""
    fonte = (
        'a = f"o total de {len(unicos)} textos"\n'  # fixture errada (noqa-acento)
        "b = f\"{', '.join(paginas)}\"\n"  # fixture errada (noqa-acento)
        'c = f"{len(x)} nao tem"\n'  # fixture errada (noqa-acento)
        "d = f\"{'acao' if x else y}\"\n"  # fixture errada (noqa-acento)
    )
    alvo = _escreve(sandbox, "src/chaves.py", fonte)

    res = _roda(["--check-file", str(alvo)], sandbox)

    achados = sorted(
        ":".join(li.split(" -> ")[0].rsplit(":", 2)[1:])
        for li in res.stdout.splitlines()
        if " -> " in li
    )
    assert achados == ["3:nao", "4:acao"], (  # fixture errada (noqa-acento)
        f"Python {sys.version.split()[0]}: o gate leu código das chaves ou "
        f"perdeu texto da f-string.\n{res.stdout}{res.stderr}"
    )
