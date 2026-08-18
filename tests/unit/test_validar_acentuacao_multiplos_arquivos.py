"""Regressão GATE-ACENTO-MULTIARQUIVO-01: o gate checava UM arquivo por vez.

O `pre-commit` apenda TODOS os nomes de arquivo staged ao entry do hook
(`.pre-commit-config.yaml`: `validar-acentuacao.py --check-file`). Enquanto
`--check-file` aceitava um valor só, o argparse ficava com o primeiro nome e
empurrava os demais para o positional `paths` — que o `main()` descartava em
silêncio, porque `if args.check_file:` vencia e os alvos eram exatamente
`[Path(args.check_file)]`. Resultado medido: com N arquivos no commit, N-1
passavam sem checagem alguma, e o commit saía verde por sorte de ordem.

O gate irmão de glifos nunca teve o defeito porque o hook dele chama o script
sem flag, e o caminho dos positionais sempre percorreu todos os alvos.

Os testes daqui cobrem as duas metades do contrato: o comportamento novo
(checar TODOS os arquivos recebidos e reprovar se QUALQUER um falhar) e o
comportamento antigo que não pode quebrar (um arquivo só, e o modo `--all`).
"""
from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "validar-acentuacao.py"
CONFIG_PRE_COMMIT = RAIZ / ".pre-commit-config.yaml"

# O texto errado destas fixtures é deliberado: é o insumo do gate, não prosa
# desta casa. Cada linha carrega o `noqa` para não acusar o próprio arquivo.
LINHA_SUJA = 'msg = "a configuracao nao tem acao"\n'  # (noqa-acento)
LINHA_LIMPA = 'msg = "a configuração não tem ação"\n'


def _roda(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )


@pytest.fixture()
def sandbox(tmp_path: Path) -> Path:
    """Repositório de mentira, para o validador achar uma raiz própria."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
    return tmp_path


def _escreve(sandbox: Path, nome: str, conteudo: str) -> Path:
    alvo = sandbox / nome
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(conteudo, encoding="utf-8")
    return alvo


def test_segundo_arquivo_sujo_reprova(sandbox: Path) -> None:
    """O caso exato do defeito: o primeiro limpo escondia o segundo sujo."""
    limpo = _escreve(sandbox, "src/limpo.py", LINHA_LIMPA)
    sujo = _escreve(sandbox, "src/sujo.py", LINHA_SUJA)

    res = _roda(["--check-file", str(limpo), str(sujo)], sandbox)

    assert res.returncode == 1, (
        "o segundo arquivo passou sem ser lido — o gate voltou a checar um só:\n"
        + res.stdout
        + res.stderr
    )
    assert "src/sujo.py" in res.stdout, res.stdout + res.stderr


def test_primeiro_arquivo_sujo_tambem_reprova(sandbox: Path) -> None:
    """A ordem não pode decidir nada: sujo na frente reprova igual."""
    sujo = _escreve(sandbox, "src/sujo.py", LINHA_SUJA)
    limpo = _escreve(sandbox, "src/limpo.py", LINHA_LIMPA)

    res = _roda(["--check-file", str(sujo), str(limpo)], sandbox)

    assert res.returncode == 1, res.stdout + res.stderr
    assert "src/sujo.py" in res.stdout, res.stdout + res.stderr


def test_todos_os_arquivos_recebidos_sao_lidos(sandbox: Path) -> None:
    """Reprovar não basta: os três têm de aparecer no relatório."""
    alvos = [
        _escreve(sandbox, "src/a.py", LINHA_SUJA),
        _escreve(sandbox, "src/b.md", "A configuracao nao tem acao.\n"),  # (noqa-acento)
        _escreve(sandbox, "src/c.py", LINHA_SUJA),
    ]

    res = _roda(["--check-file", *[str(p) for p in alvos]], sandbox)

    assert res.returncode == 1, res.stdout + res.stderr
    for nome in ("src/a.py", "src/b.md", "src/c.py"):
        assert nome in res.stdout, (
            f"{nome} não foi lido — arquivo descartado em silêncio:\n" + res.stdout
        )


def test_varios_arquivos_limpos_passam(sandbox: Path) -> None:
    """A cura não pode ser um reprovador cego: limpo em lote é verde."""
    a = _escreve(sandbox, "src/a.py", LINHA_LIMPA)
    b = _escreve(sandbox, "src/b.py", LINHA_LIMPA)

    res = _roda(["--check-file", str(a), str(b)], sandbox)

    assert res.returncode == 0, res.stdout + res.stderr


def test_positional_junto_de_check_file_nao_e_descartado(sandbox: Path) -> None:
    """Rede de segurança: o que cai no positional também é lido.

    Chamada em que o arquivo sujo chega como positional e o limpo como valor da
    flag. Antes, `if args.check_file:` vencia e o positional era jogado fora.
    """
    sujo = _escreve(sandbox, "src/sujo.py", LINHA_SUJA)
    limpo = _escreve(sandbox, "src/limpo.py", LINHA_LIMPA)

    res = _roda([str(sujo), "--check-file", str(limpo)], sandbox)

    assert res.returncode == 1, (
        "o arquivo do positional foi descartado:\n" + res.stdout + res.stderr
    )
    assert "src/sujo.py" in res.stdout, res.stdout + res.stderr


def test_um_arquivo_so_continua_valendo(sandbox: Path) -> None:
    """Contrato antigo intacto: uma flag, um caminho, um veredito."""
    sujo = _escreve(sandbox, "src/sujo.py", LINHA_SUJA)
    limpo = _escreve(sandbox, "src/limpo.py", LINHA_LIMPA)

    assert _roda(["--check-file", str(sujo)], sandbox).returncode == 1
    res_limpo = _roda(["--check-file", str(limpo)], sandbox)
    assert res_limpo.returncode == 0, res_limpo.stdout + res_limpo.stderr


def _entry_do_hook(hook_id: str) -> str:
    """Extrai o `entry:` do hook pedido lendo o texto do .pre-commit-config.yaml.

    De propósito sem PyYAML: nenhum outro teste desta suíte depende dele, e o
    portão não pode passar a exigir dependência nova para rodar.
    """
    dentro = False
    for linha in CONFIG_PRE_COMMIT.read_text(encoding="utf-8").splitlines():
        despido = linha.strip()
        if despido.startswith("- id:"):
            dentro = despido.split("- id:", 1)[1].strip() == hook_id
            continue
        if dentro and despido.startswith("entry:"):
            return despido.split("entry:", 1)[1].strip()
    raise AssertionError(f"hook {hook_id!r} sem entry em {CONFIG_PRE_COMMIT}")


def test_entry_do_hook_reprova_lote_com_um_arquivo_sujo(tmp_path: Path) -> None:
    """O que roda de verdade é o entry do hook — então é ele que se mede.

    O `pre-commit` monta a linha de comando assim: o `entry` como está no
    arquivo de config, mais os nomes dos arquivos staged no fim.
    """
    limpo = tmp_path / "limpo.py"
    limpo.write_text(LINHA_LIMPA, encoding="utf-8")
    sujo = tmp_path / "sujo.py"
    sujo.write_text(LINHA_SUJA, encoding="utf-8")

    comando = shlex.split(_entry_do_hook("acentuacao-strict"))
    comando[0] = sys.executable  # não depende de qual python3 está no PATH
    res = subprocess.run(
        [*comando, str(limpo), str(sujo)],
        cwd=str(RAIZ),
        text=True,
        capture_output=True,
    )

    assert res.returncode == 1, (
        "o hook deu verde num lote com arquivo sujo — os nomes apendados pelo "
        "pre-commit voltaram a ser descartados:\n" + res.stdout + res.stderr
    )
    assert "sujo.py" in res.stdout, res.stdout + res.stderr


def test_modo_all_continua_varrendo_o_repo(sandbox: Path) -> None:
    """`--all` não pode ter virado refém dos argumentos posicionais."""
    _escreve(sandbox, "src/sujo.py", LINHA_SUJA)

    res = _roda(["--all"], sandbox)

    assert res.returncode == 1, res.stdout + res.stderr
    assert "src/sujo.py" in res.stdout, res.stdout + res.stderr
