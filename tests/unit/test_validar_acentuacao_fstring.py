"""Regressão PORTÃO-VIVO-01 Bloco A: o gate de acento era cego a f-string.

A partir do Python 3.12 (PEP 701) o `tokenize` deixou de entregar a f-string
como um `STRING` único e passou a emitir `FSTRING_START`, `FSTRING_MIDDLE` e
`FSTRING_END`. Como `_mascara_codigo_python` só aceitava `COMMENT` e `STRING`,
o texto de toda f-string virava espaço antes da varredura — o gate não via
nada. Medido nesta máquina (3.12.3): o mesmo erro em duas linhas produzia três
apontamentos na string normal e **zero** na f-string.

E o efeito colateral caro: o job de acentuação do CI pinava 3.11, onde
f-string ainda é um `STRING` único e o gate enxerga. Verde na máquina dela,
vermelho na `main`, pelo mesmo arquivo.

Por isso os testes daqui têm de valer nos **dois** mundos: no 3.11 a simetria
já existia e continua valendo; no 3.12+ ela só existe com a correção.
"""
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


# O texto errado destas fixtures é deliberado: é o insumo do gate, não prosa
# desta casa. Cada linha carrega o `noqa` para não acusar o próprio arquivo.
_LINHA_FSTRING = 'msg = f"a configuracao nao tem acao"\n'  # (noqa-acento)
_LINHA_STRING = 'msg =  "a configuracao nao tem acao"\n'  # (noqa-acento)


def test_fstring_com_erro_de_acento_reprova(sandbox: Path) -> None:
    """O caso exato do sprint: erro dentro de f-string tem de ser visto."""
    alvo = _escreve(sandbox, "src/exemplo.py", _LINHA_FSTRING)

    res = _roda(["--check-file", str(alvo)], sandbox)

    assert res.returncode == 1, (
        "f-string com erro de acentuação passou batido:\n"
        + res.stdout
        + res.stderr
    )
    for errada in ("configuracao", "nao", "acao"):  # (noqa-acento)
        assert f":{errada} " in res.stdout, (
            f"o gate não apontou {errada!r} dentro da f-string:\n" + res.stdout
        )


def test_fstring_e_string_normal_pesam_igual(sandbox: Path) -> None:
    """A assimetria É o defeito: o mesmo texto errado, dois pesos.

    Vale nas duas versões. No 3.11 as duas linhas são `STRING` e a simetria
    já existia; no 3.12+ ela só existe com `FSTRING_MIDDLE` na máscara.
    """
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
    """A correção não pode ser larga demais.

    Dentro das chaves é CÓDIGO: `producao`, `acao`, `sessao` (noqa-acento) são
    nomes de variável, e identificador não leva acento. Aceitar o intervalo
    inteiro da f-string (ou os tokens de dentro das chaves) ressuscitaria o
    BUG-VALIDAR-ACENTUACAO-IDENTIFICADOR-PY-01, que deixou o gate vermelho de
    forma permanente com apontamentos que ninguém podia atender.
    """
    fonte = (
        "producao = 1\n"  # (noqa-acento)
        "acao = 2\n"  # (noqa-acento)
        "sessao = 3\n"  # (noqa-acento)
        'msg = f"{producao} {acao} {sessao}"\n'  # (noqa-acento)
        'esp = f"{sessao!r:>{producao}}"\n'  # (noqa-acento)
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
    """Simula o 3.11, onde `tokenize.FSTRING_MIDDLE` não existe.

    O CI ainda roda naquela versão. Ler o atributo direto levantaria
    `AttributeError` e derrubaria o gate inteiro justamente na versão que
    guarda a `main` — daí o `getattr` com padrão.
    """
    monkeypatch.delattr(tokenize, "FSTRING_MIDDLE", raising=False)

    conteudo = _LINHA_STRING
    linhas = conteudo.splitlines()

    mascarado = validador._mascara_codigo_python(conteudo, linhas)

    assert "configuracao" in mascarado[0], (  # (noqa-acento)
        "sem FSTRING_MIDDLE o mascaramento parou de devolver a string normal: "
        f"{mascarado!r}"
    )


def test_all_enxerga_arquivo_novo_ainda_nao_adicionado(sandbox: Path) -> None:
    """Bônus do Bloco A: `git ls-files -z` puro só lista o índice.

    Arquivo novo, ainda não adicionado, é exatamente o que ninguém revisou —
    e era o que o `--all` dava por verde.
    """
    _escreve(sandbox, "src/recem_nascido.py", _LINHA_STRING)
    # de propósito: nada de `git add`.

    res = _roda(["--all"], sandbox)

    assert res.returncode == 1, (
        "--all deu verde num arquivo novo fora do índice:\n"
        + res.stdout
        + res.stderr
    )
    assert "recem_nascido.py" in res.stdout, res.stdout + res.stderr
