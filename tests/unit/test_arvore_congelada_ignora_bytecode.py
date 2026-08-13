"""A ARVORE-CONGELADA-01 não confunde bytecode com produto mudado.

Defeito medido em 12/08/2026: cinco testes verdes e o `pytest` saindo com
código 1.

    $ .venv/bin/python -m pytest tests/unit/test_gravador_recusa_com_daemon_vivo.py -q
    5 passed in 0.22s
    ARVORE-CONGELADA-01: o PRODUTO mudou durante esta sessão (1 arquivo(s)):
      - APAGADO  scripts/__pycache__/record_hid_capture.cpython-312.pyc
    $ echo $?
    1

A cadeia, medida e não suposta: a cópia congelada nasce sem um único `.pyc`
(o `copytree` já ignora `__pycache__`); o teste do gravador IMPORTA
`scripts/record_hid_capture.py` de DENTRO do congelado pelo `importlib`, e o
CPython escreve o bytecode ao lado do fonte — isto é, dentro da cópia, depois
da foto. No fim da sessão a comparação varre a cópia, acha um `.pyc` sem par
na árvore viva e o chama de `APAGADO`. O job `lint-test` do CI roda
`tests/unit`, então o CI estava nesse estado desde 11/08/2026 e "a suíte
passou" tinha deixado de ser verificável nesta casa.

Isto explica o que JÁ funcionava: a guarda esteve correta por dias porque as
bancadas antigas só EXECUTAVAM os scripts congelados por `subprocess`, e o
`__main__` de um script não gera `__pycache__`. A primeira bancada a importar
de lá de dentro estreou o defeito.

A cura é a simetria: o filtro que a foto usa (`_CONGELAR_IGNORAR`) passa a
valer também na comparação. Nada de desligar a guarda.

A MORDIDA, provada em 12/08/2026
================================
Arrancado o `if _e_lixo_de_build(relativo): continue` de `_deltas_do_congelado`
em `tests/conftest.py`, `test_bytecode_nascido_dentro_do_congelado_nao_e_delta`
reprova acusando o `.pyc` fabricado. Devolvido, verde de novo. O caso
`test_arquivo_de_produto_de_verdade_continua_sendo_acusado` passa nos dois
estados de propósito: é ele que impede a cura de virar "desligar a guarda".
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests import conftest


@pytest.fixture
def congelado_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um berço que faz as vezes da cópia congelada da sessão.

    Trocar o global em vez de mexer na cópia real é o que mantém este teste
    inofensivo: a foto de verdade da sessão volta ao lugar quando o
    `monkeypatch` desfaz, e a árvore viva da usuária nunca é tocada.
    """
    berco = tmp_path / "congelado"
    berco.mkdir()
    monkeypatch.setattr(conftest, "_ARVORE_CONGELADA", [berco])
    return berco


def test_bytecode_nascido_dentro_do_congelado_nao_e_delta(congelado_de_mentira):
    """Um `.pyc` que só existe na cópia não é "o produto mudou"."""
    pycache = congelado_de_mentira / "scripts" / "__pycache__"
    pycache.mkdir(parents=True)
    (pycache / "record_hid_capture.cpython-312.pyc").write_bytes(b"\x00fake")

    deltas = conftest._deltas_do_congelado()

    assert deltas == [], (
        "a guarda chamou bytecode de produto e reprovaria a sessão inteira: "
        f"{deltas}"
    )


def test_pyc_solto_fora_do_pycache_tambem_e_ignorado(congelado_de_mentira):
    """O padrão `*.pyc` vale onde quer que o arquivo caia, não só no `__pycache__`."""
    scripts = congelado_de_mentira / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "solto.pyc").write_bytes(b"\x00fake")

    assert conftest._deltas_do_congelado() == []


def test_arquivo_de_produto_de_verdade_continua_sendo_acusado(congelado_de_mentira):
    """A cura filtra lixo de build — não afrouxa a guarda.

    Este é o caso que impede o conserto de virar "desligar a ARVORE-CONGELADA-01":
    um `.py` de produto que não tem par na árvore viva continua reprovando a
    sessão, e um que tem par mas com outro conteúdo também.
    """
    scripts = congelado_de_mentira / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "sumiu-da-arvore-viva.py").write_text("# produto\n", encoding="utf-8")

    viva = Path(conftest.__file__).resolve().parents[1]
    (congelado_de_mentira / "install.sh").write_text(
        (viva / "install.sh").read_text(encoding="utf-8") + "\n# mutação\n",
        encoding="utf-8",
    )

    deltas = conftest._deltas_do_congelado()

    assert "APAGADO  scripts/sumiu-da-arvore-viva.py" in deltas, deltas
    assert "MUDADO   install.sh" in deltas, deltas


def test_o_filtro_e_a_mesma_lista_que_a_foto_usa():
    """Se a foto e a comparação divergirem, o defeito volta pela outra ponta."""
    for padrao in ("__pycache__", "*.pyc", "target", "build", ".flatpak-builder"):
        assert padrao in conftest._CONGELAR_IGNORAR
        assert conftest._e_lixo_de_build(Path("scripts") / padrao.replace("*", "x"))
    assert not conftest._e_lixo_de_build(Path("scripts") / "record_hid_capture.py")
