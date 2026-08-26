"""Duas réguas saíam verdes por VACUIDADE, e diziam `OK` ao fazê-lo.

MEDIDO em 26/08/2026 (LEVA-4-E), com a máquina livre e a árvore parada:

* `scripts/validar-fala-de-tela.py --all` imprimia
  `OK: 1 Fala declarada(s), todas de acordo com …` — e o produto inteiro tem
  **uma** `Fala` (`app/widgets/external_card.py:97`) contra um mapa de **308**
  células, com **zero** abas em `ABAS_COM_FALA_DECLARADA`;
* `scripts/gerar-tabela-de-curvas.py --check` imprimia
  `atualizado (0 curva(s) no catálogo)` sobre um catálogo que **não existe no
  disco**.

Nos dois casos o `rc=0` é honesto e a PALAVRA é que mente: `OK` e `atualizado`
descrevem um ATO que não houve. É o padrão que a casa nomeou em 25/08 — *a
régua confunde a PALAVRA com o ATO* — e a saída que ela aplaudiu no mesmo dia
foi a régua do teclado, por dizer *"a régua não achou NENHUM valor produzível —
ela cegou"*.

**O `rc` NÃO muda, e é decisão consciente.** O tamanho dos dois conjuntos é
decisão de produto (quantas abas promover; quando a CR-04 produz a primeira
curva), e portão não reprova ninguém por uma fila que ele mesmo não enche. O
que muda é a frase, para que o verde não seja contado como medição.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

RAIZ_REAL = Path(__file__).resolve().parents[2]
FALA = RAIZ_REAL / "scripts" / "validar-fala-de-tela.py"
CURVAS = RAIZ_REAL / "scripts" / "gerar-tabela-de-curvas.py"


def _rodar(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=RAIZ_REAL,
        capture_output=True,
        text=True,
        check=False,
    )


# ─────────────────────────────────────────────────────────────────────────
# validar-fala-de-tela.py
# ─────────────────────────────────────────────────────────────────────────


def test_fala_de_tela_nao_diz_ok_com_uma_fala_so() -> None:
    """MORDIDA — a frase de sucesso não pode ser `OK` sobre conjunto de um."""
    processo = _rodar(FALA, "--all")
    assert processo.returncode == 0, processo.stdout + processo.stderr
    ultima = processo.stdout.strip().splitlines()[-1]
    assert not ultima.startswith("OK:"), (
        "a régua declarou OK sobre um conjunto que ela mesma diz ser de uma "
        "`Fala`:\n" + ultima
    )
    assert "NÃO MEDIU" in ultima or "QUASE NÃO MEDIU" in ultima, ultima


def test_fala_de_tela_diz_o_tamanho_do_conjunto_medido() -> None:
    """MORDIDA — o número de células do mapa tem de aparecer na frase.

    Sem ele, quem lê o verde do `portoes.sh` não tem como saber se a régua
    comparou uma frase ou trezentas.
    """
    processo = _rodar(FALA, "--all")
    ultima = processo.stdout.strip().splitlines()[-1]
    for pedaco in ("`Fala` declarada(s)", "célula(s)", "aba(s) promovida(s)"):
        assert pedaco in ultima, f"a frase não diz {pedaco!r}:\n{ultima}"


# ─────────────────────────────────────────────────────────────────────────
# gerar-tabela-de-curvas.py
# ─────────────────────────────────────────────────────────────────────────


def _modulo_das_curvas():
    spec = importlib.util.spec_from_file_location("gtc", CURVAS)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["gtc"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def test_curvas_nao_diz_atualizado_sobre_catalogo_inexistente() -> None:
    """MORDIDA — o catálogo não está no disco, e `atualizado` é a mentira."""
    processo = _rodar(CURVAS, "--check")
    assert processo.returncode == 0, processo.stdout + processo.stderr
    assert "NÃO MEDIU NADA" in processo.stdout, processo.stdout
    assert "curvas-proprias.json" in processo.stdout, processo.stdout


def test_a_frase_muda_com_o_tamanho_do_catalogo(tmp_path: Path) -> None:
    """As três respostas da régua, exercitadas uma a uma.

    Régua que só sabe dizer "não medi" é tão inútil quanto régua que só sabe
    dizer `OK` — este teste cobra as DUAS pontas.
    """
    modulo = _modulo_das_curvas()

    ausente = tmp_path / "nao-existe.json"
    assert "NÃO MEDIU NADA" in modulo.frase_do_tamanho(ausente, 0)

    vazio = tmp_path / "vazio.json"
    vazio.write_text("{}", encoding="utf-8")
    frase_vazia = modulo.frase_do_tamanho(vazio, 0)
    assert "NÃO MEDIU NADA" in frase_vazia
    assert "SEM CURVA" in frase_vazia

    frase_uma = modulo.frase_do_tamanho(vazio, 1)
    assert "QUASE NADA" in frase_uma
    assert "atualizado" not in frase_uma

    frase_cheia = modulo.frase_do_tamanho(vazio, 7)
    assert frase_cheia.startswith("atualizado")
    assert "7 curva(s)" in frase_cheia


def test_a_frase_cheia_nomeia_a_fonte(tmp_path: Path) -> None:
    """O tamanho sem o endereço da fonte não deixa ninguém conferir."""
    modulo = _modulo_das_curvas()
    fonte = tmp_path / "curvas.json"
    fonte.write_text("{}", encoding="utf-8")
    assert "curvas.json" in modulo.frase_do_tamanho(fonte, 7)
