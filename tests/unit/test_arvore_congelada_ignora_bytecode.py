"""A ARVORE-CONGELADA-01 não confunde bytecode com produto mudado."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests import conftest


@pytest.fixture
def congelado_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um berço que faz as vezes da cópia congelada da sessão."""
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
    """A cura filtra lixo de build — não afrouxa a guarda."""
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
