"""O conferidor das extensões (`scripts/conferir_as_extensoes.py`), contra extensões de brinquedo.

Cada teste arruma uma extensão em ordem numa pasta e estraga UMA coisa: a versão do
``pyproject.toml``, a do topo do CHANGELOG, a licença, uma seção do README, o manifesto ou a forma
da saída do leitor. O conferidor tem de recusar a estragada e aceitar a que está em ordem.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "conferir_as_extensoes.py"

MANIFESTO = {
    "id": "brinquedo", "nome": "Brinquedo", "versao": "1.2.0", "api": ">=2,<3",  # (noqa-acento)
    "licenca": "MIT", "tipos": ["lancador"], "permissoes": ["lancador"],  # (noqa-acento)
    "lancador": {"rotulo": "Brinquedo", "atalhos": ["brinquedo"], "comandos": ["brinquedo"],
                 "leitor": {"executar": ["python3", "-I", "leitor.py"], "prazo_s": 5,
                            "fontes": [".config/brinquedo/config.ini"]}},
}
README = ("# hefesto-mod-brinquedo\n\n## O que faz\n\nNada.\n\n## Instalar\n\nUm comando.\n\n"
          "## Testes\n\n`pytest`.\n\n## Licença\n\nMIT.\n")
LICENSE_MIT = "MIT License\n\nCopyright (c) 2026\n"
CHANGELOG = "# Mudanças\n\n## Na próxima versão\n\n- nada\n\n## 1.2.0 (01/11/2026)\n\n- um\n"
PYPROJECT = ('[project]\nname = "hefesto-mod-brinquedo"\nversion = "1.2.0"\n\n'
             '[tool.ruff]\nline-length = 100\n')
LEITOR = "import json\nprint(json.dumps([]))\n"


@pytest.fixture(scope="module")
def conferidor() -> ModuleType:
    spec = importlib.util.spec_from_file_location("conferir_as_extensoes", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["conferir_as_extensoes"] = modulo
    spec.loader.exec_module(modulo)
    modulo._entrar_no_hefesto(RAIZ)
    return modulo


@pytest.fixture
def extensao(tmp_path: Path) -> Path:
    pasta = tmp_path / "ext"
    pasta.mkdir()
    (pasta / "hefesto-mod.json").write_text(json.dumps(MANIFESTO), encoding="utf-8")
    (pasta / "README.md").write_text(README, encoding="utf-8")
    (pasta / "LICENSE").write_text(LICENSE_MIT, encoding="utf-8")
    (pasta / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
    (pasta / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (pasta / "leitor.py").write_text(LEITOR, encoding="utf-8")
    return pasta


def _recusas(conferidor: ModuleType, pasta: Path) -> list[str]:
    nome, recusas = conferidor.conferir(pasta, False)
    assert nome == "brinquedo 1.2.0"
    return list(recusas)


def test_a_extensao_em_ordem_passa(conferidor: ModuleType, extensao: Path) -> None:
    """A extensão com versão, licença, README e leitor em ordem não recebe recusa."""
    assert _recusas(conferidor, extensao) == []


def test_o_pyproject_com_outra_versao_reprova(conferidor: ModuleType, extensao: Path) -> None:
    """D-2511-CADA-EXTENSAO-CONFERE-A-PROPRIA-VERSAO-NO-CI: pyproject com outra versão reprova."""
    (extensao / "pyproject.toml").write_text(PYPROJECT.replace("1.2.0", "1.0.0"), encoding="utf-8")
    [frase] = _recusas(conferidor, extensao)
    assert "pyproject.toml 1.0.0" in frase and "hefesto-mod.json 1.2.0" in frase


def test_o_changelog_com_outra_versao_no_topo_reprova(conferidor: ModuleType,
                                                      extensao: Path) -> None:
    """O topo numerado do CHANGELOG vale, e «Na próxima versão» não conta como versão."""
    (extensao / "CHANGELOG.md").write_text(
        CHANGELOG.replace("## 1.2.0", "## 1.1.0"), encoding="utf-8")
    [frase] = _recusas(conferidor, extensao)
    assert "CHANGELOG.md 1.1.0" in frase


def test_o_pyproject_sem_versao_nao_diverge(conferidor: ModuleType, extensao: Path) -> None:
    """Um pyproject só de ferramentas, sem a tabela [project], não entra na conta."""
    (extensao / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n", encoding="utf-8")
    assert _recusas(conferidor, extensao) == []


def test_a_licenca_do_arquivo_que_nao_e_a_do_manifesto_reprova(
        conferidor: ModuleType, extensao: Path) -> None:
    """O LICENSE em GPL com o manifesto em MIT reprova."""
    (extensao / "LICENSE").write_text("GNU GENERAL PUBLIC LICENSE\nVersion 3\n", encoding="utf-8")
    [frase] = _recusas(conferidor, extensao)
    assert "LICENSE" in frase and "MIT" in frase


@pytest.mark.parametrize(("linha", "aceita"), [("Version 3, 29 June 2007", True),
                                               ("Version 2, June 1991", False)])
def test_o_license_da_gpl_vale_so_na_gpl_3(conferidor: ModuleType, linha: str,
                                          aceita: bool) -> None:
    """O LICENSE da GPL 2 não passa por GPL-3.0 do manifesto; o da GPL 3 passa."""
    texto = f"                    GNU GENERAL PUBLIC LICENSE\n                       {linha}\n"
    assert ("GPL-3.0-or-later" in conferidor.licencas_do_arquivo(texto)) is aceita


def test_o_readme_que_diz_outra_licenca_reprova(conferidor: ModuleType, extensao: Path) -> None:
    """O README que não diz a licença do manifesto reprova."""
    (extensao / "README.md").write_text(README.replace("MIT.", "GPL-3.0-or-later."),
                                        encoding="utf-8")
    [frase] = _recusas(conferidor, extensao)
    assert "README.md" in frase and "MIT" in frase


def test_o_readme_sem_a_secao_de_testes_reprova_e_os_tres_nomes_valem(
        conferidor: ModuleType, extensao: Path) -> None:
    """Sem seção de testes o README reprova; «A suíte» e «Provas» valem como «Testes»."""
    (extensao / "README.md").write_text(README.replace("## Testes", "## Outra coisa"),
                                        encoding="utf-8")
    [frase] = _recusas(conferidor, extensao)
    assert "Testes" in frase
    for nome in ("A suíte", "Provas"):
        (extensao / "README.md").write_text(README.replace("## Testes", f"## {nome}"),
                                            encoding="utf-8")
        assert _recusas(conferidor, extensao) == []


def test_o_manifesto_que_o_hefesto_recusa_reprova(conferidor: ModuleType, extensao: Path) -> None:
    """O manifesto com uma permissão que o Hefesto não conhece reprova pela régua dele."""
    ruim = {**MANIFESTO, "permissoes": ["lancador", "inventada"]}  # (noqa-acento)
    (extensao / "hefesto-mod.json").write_text(json.dumps(ruim), encoding="utf-8")
    nome, recusas = conferidor.conferir(extensao, False)
    assert nome == extensao.name and len(recusas) == 1
    assert recusas[0].startswith("o manifesto não passa pelo Hefesto")


@pytest.mark.parametrize("saida", ["{\"jogos\": 3}", "not json", "{\"a\": 1}"])
def test_o_leitor_que_muda_a_forma_da_saida_reprova(
        conferidor: ModuleType, extensao: Path, saida: str) -> None:
    """O leitor cuja saída o Hefesto não lê como biblioteca reprova, com o motivo."""
    (extensao / "leitor.py").write_text(f"print({saida!r})\n", encoding="utf-8")
    [frase] = _recusas(conferidor, extensao)
    assert frase.startswith("o leitor não entrega uma biblioteca que o Hefesto leia")


def test_o_leitor_que_estoura_o_prazo_reprova(conferidor: ModuleType, extensao: Path) -> None:
    """O leitor que não termina no prazo declarado reprova em vez de pendurar o CI."""
    manifesto = json.loads(json.dumps(MANIFESTO))
    manifesto["lancador"]["leitor"]["prazo_s"] = 1
    (extensao / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    (extensao / "leitor.py").write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    [frase] = _recusas(conferidor, extensao)
    assert "o leitor não entrega" in frase


def test_a_linha_de_saida_e_o_codigo_de_retorno(extensao: Path, capsys: pytest.CaptureFixture[str],
                                               conferidor: ModuleType) -> None:
    """O `main` diz uma linha por extensão e devolve 1 quando alguma recusa."""
    assert conferidor.main(["--sem-caixa", str(extensao)]) == 0
    assert capsys.readouterr().out.strip() == "ok brinquedo 1.2.0"
    (extensao / "pyproject.toml").write_text(PYPROJECT.replace("1.2.0", "0.1.0"), encoding="utf-8")
    assert conferidor.main(["--sem-caixa", str(extensao)]) == 1
    assert capsys.readouterr().out.startswith("recusa brinquedo 1.2.0: a versão diverge")
