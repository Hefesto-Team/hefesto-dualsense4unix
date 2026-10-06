"""DECISAO-SEM-DONO-01: o portão que cobra a decisão decidida tem de MORDER.

`scripts/check_a_decisao_tem_prova.py` liga cada linha de `decisoes-de-produto.csv` a uma
função de teste que cita o id. Verde dele mede a EXISTÊNCIA da prova e a ligação
com o id, nunca a qualidade: a mordida de cada regra está aqui, e cada teste
monta a árvore mínima em que só aquela regra reprova.
"""

from __future__ import annotations

import csv
import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_a_decisao_tem_prova.py"

COLUNAS = (
    "id", "titulo", "a_pergunta", "caminhos", "recomendacao", "preco_do_outro_lado",
    "por_que_espera", "onde_mora", "foto_antes", "foto_depois", "custo", "aberta_em",
    "estado", "escolha", "decidida_em", "nasceu_de", "quem_decidiu", "revoga",
    "prova", "marca",
)

UM_TESTE = '''def test_a_cura_de_d_a():
    """Mede a D-A."""
    assert True
'''


def _modulo():
    spec = importlib.util.spec_from_file_location("_portao_a_decisao_tem_prova", PORTAO)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_portao_a_decisao_tem_prova"] = mod
    spec.loader.exec_module(mod)
    return mod


def _escreve_csv(raiz: Path, linhas: list[dict[str, str]], colunas=COLUNAS) -> None:
    destino = raiz / "docs" / "data" / "decisoes-de-produto.csv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="") as fp:
        w = csv.DictWriter(fp, fieldnames=list(colunas), lineterminator="\n")
        w.writeheader()
        for linha in linhas:
            w.writerow({c: linha.get(c, "") for c in colunas})


def _escreve_piso(raiz: Path, ids: list[str]) -> None:
    (raiz / "docs" / "data" / "decisoes-sem-prova.txt").write_text(
        "# piso de mentira\n" + "".join(f"{i}\n" for i in ids), encoding="utf-8")


def _escreve_teste(raiz: Path, nome: str, fonte: str) -> None:
    destino = raiz / "tests" / "unit" / nome
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(fonte, encoding="utf-8")


@pytest.fixture
def arvore(tmp_path):
    """D-A com prova que abre, D-B de processo, D-C sem prova e no piso."""
    _escreve_teste(tmp_path, "test_a.py", UM_TESTE)
    _escreve_csv(tmp_path, [
        {"id": "D-A", "estado": "decidida", "prova": "tests/unit/test_a.py::test_a_cura_de_d_a"},
        {"id": "D-B", "estado": "decidida", "marca": "processo"},
        {"id": "D-C", "estado": "decidida"},
        {"id": "D-D", "estado": "caduca"},
    ])
    _escreve_piso(tmp_path, ["D-C"])
    return tmp_path, _modulo()


def _rodar(mod, raiz: Path, *extra: str) -> int:
    return mod.main(["--raiz", str(raiz), *extra])


def test_a_arvore_de_partida_passa(arvore, capsys):
    raiz, mod = arvore
    assert _rodar(mod, raiz) == 0
    saida = capsys.readouterr().out
    assert "NÃO QUER DIZER FEITO" in saida, "o verde tem de dizer em voz alta o que não mede"


def test_decisao_nova_sem_prova_reprova_nomeada(arvore, capsys):
    raiz, mod = arvore
    linhas = list(csv.DictReader((raiz / "docs/data/decisoes-de-produto.csv").open(encoding="utf-8")))
    linhas.append({"id": "D-NOVA", "estado": "decidida"})
    _escreve_csv(raiz, linhas)
    assert _rodar(mod, raiz) == 1
    assert "D-NOVA" in capsys.readouterr().out


def test_a_marca_processo_dispensa_a_prova(arvore):
    raiz, mod = arvore
    linhas = list(csv.DictReader((raiz / "docs/data/decisoes-de-produto.csv").open(encoding="utf-8")))
    linhas.append({"id": "D-NOVA", "estado": "decidida", "marca": "processo"})
    _escreve_csv(raiz, linhas)
    assert _rodar(mod, raiz) == 0


def test_marca_fora_do_vocabulario_reprova(arvore, capsys):
    raiz, mod = arvore
    linhas = list(csv.DictReader((raiz / "docs/data/decisoes-de-produto.csv").open(encoding="utf-8")))
    linhas.append({"id": "D-NOVA", "estado": "decidida", "marca": "tanto-faz"})
    _escreve_csv(raiz, linhas)
    assert _rodar(mod, raiz) == 1
    assert "tanto-faz" in capsys.readouterr().out


def test_prova_em_arquivo_que_nao_existe_reprova(arvore, capsys):
    raiz, mod = arvore
    (raiz / "tests/unit/test_a.py").unlink()
    assert _rodar(mod, raiz) == 1
    assert "não existe" in capsys.readouterr().out


def test_prova_em_funcao_que_nao_existe_reprova(arvore, capsys):
    raiz, mod = arvore
    _escreve_teste(raiz, "test_a.py", UM_TESTE.replace("test_a_cura_de_d_a", "test_outra"))
    assert _rodar(mod, raiz) == 1
    assert "não é uma função" in capsys.readouterr().out


def test_prova_que_nao_cita_a_decisao_reprova(arvore, capsys):
    """A função existe, e o id foi para o cabeçalho do arquivo: não é a régua dela."""
    raiz, mod = arvore
    _escreve_teste(raiz, "test_a.py",
                   '"""Nasceu da D-A."""\n\ndef test_a_cura_de_d_a():\n    assert True\n')
    assert _rodar(mod, raiz) == 1
    assert "NÃO cita a decisão" in capsys.readouterr().out


def test_o_id_dentro_da_funcao_so_conta_com_a_borda_do_id(arvore, capsys):
    """`D-AB` dentro da função não é a `D-A`."""
    raiz, mod = arvore
    _escreve_teste(raiz, "test_a.py",
                   'def test_a_cura_de_d_a():\n    """Mede a D-AB."""\n')
    assert _rodar(mod, raiz) == 1
    assert "NÃO cita a decisão" in capsys.readouterr().out


def test_prova_fora_de_tests_ou_sem_a_forma_reprova(arvore, capsys):
    raiz, mod = arvore
    linhas = list(csv.DictReader((raiz / "docs/data/decisoes-de-produto.csv").open(encoding="utf-8")))
    linhas[0]["prova"] = "scripts/qualquer.py::test_a_cura_de_d_a"
    _escreve_csv(raiz, linhas)
    assert _rodar(mod, raiz) == 1
    assert "não tem a forma" in capsys.readouterr().out


def test_o_degrau_implementada_exige_prova(arvore, capsys):
    raiz, mod = arvore
    linhas = list(csv.DictReader((raiz / "docs/data/decisoes-de-produto.csv").open(encoding="utf-8")))
    linhas[1]["estado"] = "implementada"
    linhas[1]["marca"] = "processo"
    _escreve_csv(raiz, linhas)
    assert _rodar(mod, raiz) == 1, "a marca de processo não substitui a prova num degrau acima"
    assert "sem o campo `prova`" in capsys.readouterr().out


@pytest.mark.parametrize("degrau", ["implementada", "feita", "no ar"])
def test_cada_degrau_com_prova_que_abre_passa(arvore, degrau):
    raiz, mod = arvore
    linhas = list(csv.DictReader((raiz / "docs/data/decisoes-de-produto.csv").open(encoding="utf-8")))
    linhas[0]["estado"] = degrau
    _escreve_csv(raiz, linhas)
    assert _rodar(mod, raiz) == 0


def test_estado_fora_da_escada_reprova(arvore, capsys):
    raiz, mod = arvore
    linhas = list(csv.DictReader((raiz / "docs/data/decisoes-de-produto.csv").open(encoding="utf-8")))
    linhas[2]["estado"] = "quase-feita"
    _escreve_csv(raiz, linhas)
    assert _rodar(mod, raiz) == 1
    assert "quase-feita" in capsys.readouterr().out


def test_piso_velho_reprova_e_o_aceitar_desce(arvore, capsys):
    """D-C ganhou prova: ela tem de sair do piso, senão a vaga serviria a uma decisão nova."""
    raiz, mod = arvore
    linhas = list(csv.DictReader((raiz / "docs/data/decisoes-de-produto.csv").open(encoding="utf-8")))
    linhas[2]["prova"] = "tests/unit/test_a.py::test_a_cura_de_d_a"
    _escreve_csv(raiz, linhas)
    _escreve_teste(raiz, "test_a.py", UM_TESTE.replace("Mede a D-A.", "Mede a D-A e a D-C."))
    assert _rodar(mod, raiz) == 1
    assert "D-C" in capsys.readouterr().out
    assert _rodar(mod, raiz, "--aceitar") == 0
    assert "D-C" not in (raiz / "docs/data/decisoes-sem-prova.txt").read_text()
    assert _rodar(mod, raiz) == 0


def test_o_aceitar_nao_sobe_o_piso(arvore, capsys):
    raiz, mod = arvore
    linhas = list(csv.DictReader((raiz / "docs/data/decisoes-de-produto.csv").open(encoding="utf-8")))
    linhas.append({"id": "D-NOVA", "estado": "decidida"})
    _escreve_csv(raiz, linhas)
    antes = (raiz / "docs/data/decisoes-sem-prova.txt").read_text()
    assert _rodar(mod, raiz, "--aceitar") == 2
    assert (raiz / "docs/data/decisoes-sem-prova.txt").read_text() == antes
    assert "D-NOVA" in capsys.readouterr().out


def test_o_semear_so_vale_no_primeiro_piso(arvore):
    raiz, mod = arvore
    assert _rodar(mod, raiz, "--semear") == 2, "piso com decisão dentro não se semeia de novo"
    (raiz / "docs/data/decisoes-sem-prova.txt").write_text("", encoding="utf-8")
    assert _rodar(mod, raiz, "--semear") == 0
    assert "D-C" in (raiz / "docs/data/decisoes-sem-prova.txt").read_text()


def test_sem_o_arquivo_do_piso_toda_decisao_sem_prova_e_nova(arvore, capsys):
    raiz, mod = arvore
    (raiz / "docs/data/decisoes-sem-prova.txt").unlink()
    assert _rodar(mod, raiz) == 1
    assert "D-C" in capsys.readouterr().out


def test_coluna_que_some_do_csv_reprova(arvore, capsys):
    """Sem a coluna `prova` toda decisão pareceria sem prova, ou toda prova ausente."""
    raiz, mod = arvore
    _escreve_csv(raiz, [{"id": "D-C", "estado": "decidida"}],
                 colunas=tuple(c for c in COLUNAS if c != "prova"))
    assert _rodar(mod, raiz) == 1
    assert "perdeu a(s) coluna(s) prova" in capsys.readouterr().out


def test_id_repetido_no_csv_reprova(arvore, capsys):
    raiz, mod = arvore
    linhas = list(csv.DictReader((raiz / "docs/data/decisoes-de-produto.csv").open(encoding="utf-8")))
    linhas.append(dict(linhas[2]))
    _escreve_csv(raiz, linhas)
    assert _rodar(mod, raiz) == 1
    assert "repetido" in capsys.readouterr().out


def test_o_csv_de_verdade_passa(capsys):
    assert _modulo().main([]) == 0, capsys.readouterr().out


def test_a_prova_de_verdade_arrancada_reprova(tmp_path, capsys):
    """Mordida no registro real: a função que prova uma decisão some, e ele reprova nomeando-a."""
    mod = _modulo()
    real = list(csv.DictReader((RAIZ / "docs/data/decisoes-de-produto.csv").open(encoding="utf-8")))
    com_prova = next(r for r in real if r["prova"] and r["estado"] == "decidida")
    rel, _, nome = com_prova["prova"].split(" | ")[0].partition("::")
    destino = tmp_path / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(RAIZ / rel, destino)
    for pasta in ("docs/data",):
        (tmp_path / pasta).mkdir(parents=True, exist_ok=True)
    for arquivo in ("decisoes-de-produto.csv", "decisoes-sem-prova.txt"):
        shutil.copy(RAIZ / "docs/data" / arquivo, tmp_path / "docs/data" / arquivo)
    for r in real:
        for parte in (r["prova"] or "").split(" | "):
            relx = parte.partition("::")[0]
            if relx and relx != rel:
                alvo = tmp_path / relx
                alvo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(RAIZ / relx, alvo)
    assert mod.main(["--raiz", str(tmp_path)]) == 0, capsys.readouterr().out
    fonte = destino.read_text(encoding="utf-8")
    destino.write_text(fonte.replace(f"def {nome}(", "def renomeada("), encoding="utf-8")
    assert mod.main(["--raiz", str(tmp_path)]) == 1
    saida = capsys.readouterr().out
    assert com_prova["id"] in saida and nome in saida
