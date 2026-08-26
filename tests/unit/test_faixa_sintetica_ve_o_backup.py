"""O varredor da ÁRVORE tem de enxergar o backup, e não só o nome exato.

O DEFEITO, medido em 26/08/2026 (LEVA-4-E). A cura do ponto cego de backup foi
escrita em 25/08 — ``_vale_varrer``, que troca ``Path.suffix`` por
``Path.suffixes`` — e foi ligada em :func:`achados`, o varredor ``--casa``. O
próprio cabeçalho de ``scripts/check_faixa_sintetica.py`` diz que o ``--casa``
**não REPROVA em lugar nenhum**, de propósito. Quem reprova é
:func:`achados_na_arvore`, o modo ``--arvore``, que o CI roda — e ele iterava
``NOMES_DE_TEMPO_DE_EXECUCAO`` com ``rglob(nome)``, casamento EXATO, sem nunca
chamar ``_vale_varrer``.

Ou seja: a cura existia e o portão que reprova não a usava. É a família
*"a casa sabe e o produto não faz"* dentro da própria régua.

O QUE ESTÁ EM JOGO. Foi a faixa ``aabbcc`` vazando para o ``controllers.json``
vivo dela que empurrou os quatro DualSense REAIS para os slots 1, 6, 7 e 8
(T-06, medido na bancada em 23/08/2026). E a poluição foi encontrada, em
25/08, num arquivo de **backup** — exatamente a classe que este varredor não
enxergava.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "check_faixa_sintetica.py"

#: A grafia medida no `controllers.json` de 23/08: sem `:` entre os octetos.
LINHA_SUJA = '{"mac": "aabbcc112233", "slot": 1}\n'


def rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--arvore", "--raiz", str(raiz)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_controllers_json_com_sufixo_de_backup_e_pego(tmp_path: Path) -> None:
    """MORDIDA — o nome exato de 25/08, com a data de hoje no sufixo."""
    alvo = tmp_path / "controllers.json.antes-de-tirar-fixtures-20260826"
    alvo.write_text(LINHA_SUJA, encoding="utf-8")

    processo = rodar(tmp_path)

    assert processo.returncode == 1, (
        "o varredor --arvore ficou VERDE sobre um backup do controllers.json "
        "com faixa sintética dentro:\n" + processo.stdout
    )
    assert "aabbcc" in processo.stdout
    assert alvo.name in processo.stdout


def test_o_nome_exato_continua_pego(tmp_path: Path) -> None:
    """A régua velha não podia REGREDIR ao ganhar alcance."""
    (tmp_path / "controllers.json").write_text(LINHA_SUJA, encoding="utf-8")
    processo = rodar(tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "controllers.json" in processo.stdout


def test_prefixo_parecido_de_outra_familia_nao_e_varrido(tmp_path: Path) -> None:
    """O alcance por PREFIXO não pode virar alcance por qualquer coisa.

    ``controllers.jsonl`` é outro formato (JSON Lines), não um backup: os
    ``suffixes`` dele são ``['.jsonl']``, e ``.jsonl`` não está na lista de
    extensões varridas. Sem este teste, "varrer por prefixo" seria licença para
    o varredor abrir binário e inventar achado.
    """
    (tmp_path / "controllers.jsonl").write_text(LINHA_SUJA, encoding="utf-8")
    processo = rodar(tmp_path)
    assert processo.returncode == 0, processo.stdout


def test_arvore_limpa_continua_verde(tmp_path: Path) -> None:
    """Régua que só sabe reprovar também não é régua."""
    (tmp_path / "controllers.json.bak").write_text(
        '{"slot": 1, "nome": "um controle sem endereço nenhum escrito"}\n',
        encoding="utf-8",
    )
    processo = rodar(tmp_path)
    assert processo.returncode == 0, processo.stdout


def test_pasta_ignorada_continua_ignorada(tmp_path: Path) -> None:
    """`tests/` é onde a faixa sintética É legítima — e o backup dela também."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "controllers.json.bak").write_text(
        LINHA_SUJA, encoding="utf-8"
    )
    processo = rodar(tmp_path)
    assert processo.returncode == 0, processo.stdout
