"""A tabela de curvas próprias sai do CATÁLOGO — CURVA-TABELA-01.

A CR-02 escreveu a regra e o docstring de `gerar_tabela_markdown` a repete
literalmente: a tabela de `docs/protocol/curvas-proprias.md` é *"gerada a partir
dos perfis, não escrita à mão"*, porque *"registro mantido à mão desatualiza, e
registro desatualizado não defende ninguém"*.

MEDIDO em 12/08/2026 e registrado como dívida em
`tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py`: **ninguém chamava a
função**. Só `tests/`, e nada em `scripts/`. A tabela do documento era mantida à
mão — exatamente o que a CR-02 proibiu. A regra estava escrita e não valia.

A MORDIDA VEIO DO PORTÃO QUE A CASA JÁ TINHA
---------------------------------------------
Com `scripts/gerar-tabela-de-curvas.py` no lugar e a lápide ainda no registro de
lacunas, `test_nenhuma_lapide_sobreviveu_a_propria_cura` reprovou dizendo
*"_SEM_CAMINHO_HOJE declara estes símbolos como sem caminho, e ALGO em produção
já os alcança: ['profiles/curva_propria.py::gerar_tabela_markdown']"*. É a prova
de que o chamador é de PRODUÇÃO, e não mais um teste — que era a distinção
inteira daquele portão.

PROVA DE QUE MORDE (13/08/2026) — em `scripts/gerar-tabela-de-curvas.py`,
trocado o corpo de `divergencias` por `return []`: caíram
`test_uma_curva_no_catalogo_faz_o_check_reprovar` e
`test_a_tabela_editada_a_mao_e_acusada`, os dois com `saiu 0`. Cura devolvida,
os sete verdes.

O PORTÃO NASCE ANTES DO DADO, E ISSO É O DESENHO
-------------------------------------------------
Não existe curva própria nenhuma no repositório: quem as vai medir é a CR-04,
com a mão da mantenedora no gatilho. Com o catálogo vazio a função devolve
`_(nenhum ainda — ver CR-04)_`, que é a linha que o documento já tinha — então o
portão entra verde. Criado DEPOIS do dado ele nasceria vermelho e seria
desligado na mesma semana; criado antes, ele já está de pé no dia em que a
primeira curva chega.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_REAL = Path(__file__).resolve().parents[2]
GERADOR = RAIZ_REAL / "scripts" / "gerar-tabela-de-curvas.py"
DOC_REAL = RAIZ_REAL / "docs" / "protocol" / "curvas-proprias.md"
CI = RAIZ_REAL / ".github" / "workflows" / "ci.yml"

COMANDO = "scripts/gerar-tabela-de-curvas.py --check"

ABRE = "<!-- BLOCO GERADO por scripts/gerar-tabela-de-curvas.py — não edite à mão -->"
FECHA = "<!-- FIM DO BLOCO GERADO -->"
VAZIO = "_(nenhum ainda — ver CR-04)_"

#: Uma curva que PASSA nas recusas da CR-02: proveniência inteira, nota longa o
#: bastante, data depois da vigência do CLEAN-ROOM e sete bytes de curva.
CURVA = {
    "nome": "Tranco curto de teste",
    "medido_por": "vitoriamaria",
    "medido_em": "2026-08-13",
    "controle": "DualSense, cabo",
    "nota": "trava seco no começo e solta sem resíduo; parei aqui porque doeu.",
    "curva": [5, 200, 0, 0, 0, 0, 0],
}


@pytest.fixture
def arvore(tmp_path: Path) -> Path:
    """Árvore de brinquedo com o gerador e o `src/` real ao lado.

    O `src/` entra por symlink e não por cópia: o gerador IMPORTA
    `profiles/curva_propria.py`, e o que se está testando é justamente que ele
    use a função de verdade — copiar o módulo abriria a porta para o teste
    passar contra uma versão velha dele.
    """
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs" / "protocol").mkdir(parents=True)
    (tmp_path / "docs" / "data").mkdir(parents=True)
    shutil.copy(GERADOR, tmp_path / "scripts" / GERADOR.name)
    (tmp_path / "src").symlink_to(RAIZ_REAL / "src", target_is_directory=True)
    documento(tmp_path).write_text(
        f"# Curvas próprias\n\n## Efeitos\n\n{ABRE}\n\n{VAZIO}\n\n{FECHA}\n",
        encoding="utf-8")
    return tmp_path


def documento(arvore: Path) -> Path:
    return arvore / "docs" / "protocol" / "curvas-proprias.md"


def catalogo(arvore: Path) -> Path:
    return arvore / "docs" / "data" / "curvas-proprias.json"


def roda(arvore: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(arvore / "scripts" / GERADOR.name), *args],
        capture_output=True, text=True, cwd=arvore, check=False)


def confere(arvore: Path) -> subprocess.CompletedProcess[str]:
    return roda(arvore, "--check")


def test_o_catalogo_vazio_passa_e_devolve_a_linha_que_o_documento_ja_tinha(
    arvore: Path,
) -> None:
    """O portão nasce antes do dado, e verde. O controle de tudo o mais."""
    saida = confere(arvore)
    assert saida.returncode == 0, saida.stderr
    assert VAZIO in documento(arvore).read_text(encoding="utf-8")


def test_uma_curva_no_catalogo_faz_o_check_reprovar(arvore: Path) -> None:
    """A MORDIDA: o dado chegou e a tabela publicada não o traz.

    É o dia da CR-04 em miniatura. Sem este portão, a primeira curva medida
    entraria no catálogo e o documento continuaria dizendo "nenhum ainda" —
    que é a forma exata do defeito que a CR-02 nomeou.
    """
    catalogo(arvore).write_text(
        json.dumps({"curvas": [CURVA]}), encoding="utf-8")
    saida = confere(arvore)
    assert saida.returncode == 1, (
        "uma curva entrou no catálogo e a tabela publicada continuou vazia sem "
        f"ninguém reclamar. Disse: {saida.stdout!r}")
    assert "DESATUALIZADO" in saida.stderr
    assert "Tranco curto de teste" in saida.stderr, (
        "o erro não mostra a curva que passou a existir")


def test_gerar_materializa_a_curva_com_a_proveniencia_inteira(
    arvore: Path,
) -> None:
    """R3: o dado e a origem não se separam — nem na tabela publicada."""
    catalogo(arvore).write_text(
        json.dumps({"curvas": [CURVA]}), encoding="utf-8")
    assert roda(arvore).returncode == 0
    texto = documento(arvore).read_text(encoding="utf-8")
    for prometido in ("Tranco curto de teste", "vitoriamaria", "2026-08-13",
                      "DualSense, cabo", "`[5, 200, 0, 0, 0, 0, 0]`"):
        assert prometido in texto, f"a tabela gerada não traz {prometido!r}"
    assert VAZIO not in texto
    assert confere(arvore).returncode == 0


def test_a_tabela_editada_a_mao_e_acusada(arvore: Path) -> None:
    """O outro lado: mexer na tabela sem mexer no catálogo é a proibição da CR-02."""
    alvo = documento(arvore)
    alvo.write_text(
        alvo.read_text(encoding="utf-8").replace(VAZIO, "| um efeito inventado |"),
        encoding="utf-8")
    saida = confere(arvore)
    assert saida.returncode == 1, (
        f"a tabela foi escrita à mão e o portão passou. Disse: {saida.stdout!r}")
    assert "um efeito inventado" in saida.stderr


def test_catalogo_ilegivel_reprova_em_vez_de_virar_tabela_vazia(
    arvore: Path,
) -> None:
    """Catálogo quebrado tem de gritar; silêncio viraria "nenhuma curva ainda"."""
    catalogo(arvore).write_text("{isto não é json", encoding="utf-8")
    saida = confere(arvore)
    assert saida.returncode != 0
    assert "curvas-proprias.json" in saida.stderr


def test_marcadores_apagados_reprovam_em_voz_alta(arvore: Path) -> None:
    alvo = documento(arvore)
    texto = alvo.read_text(encoding="utf-8")
    alvo.write_text(texto[:texto.index(ABRE)], encoding="utf-8")
    saida = confere(arvore)
    assert saida.returncode == 1
    assert "SEM BLOCO GERADO" in saida.stderr


def test_a_arvore_de_verdade_esta_atualizada_e_o_portao_esta_no_ci() -> None:
    """Contra a árvore REAL, e a fiação.

    O `--check` das curvas vive no job `lint-test` e NÃO no pre-commit: ele
    importa um módulo pydantic, e o `language: system` do pre-commit roda o
    Python pelado de quem commita — um hook que explode no import é um hook
    desligado na semana seguinte. Quem o roda em toda máquina é este teste.
    """
    saida = subprocess.run(
        [sys.executable, str(GERADOR), "--check"],
        capture_output=True, text=True, cwd=RAIZ_REAL, check=False)
    assert saida.returncode == 0, (
        "a tabela de curvas publicada não é a que o catálogo produz:\n"
        f"{saida.stderr}")
    assert ABRE in DOC_REAL.read_text(encoding="utf-8"), (
        "o documento de verdade perdeu o marcador do bloco gerado — a tabela "
        "voltou a ser escrita à mão")

    yaml = pytest.importorskip("yaml")
    dados = yaml.safe_load(CI.read_text(encoding="utf-8"))
    passos = [
        {**passo, "__job__": nome}
        for nome, job in (dados.get("jobs") or {}).items()
        for passo in job.get("steps") or []
    ]
    rodam = [p for p in passos if COMANDO in " ".join(str(p.get("run", "")).split())]
    assert rodam, f"o CI não chama `{COMANDO}`"
    for passo in rodam:
        assert not passo.get("continue-on-error"), (
            f"o passo '{passo.get('name', passo['__job__'])}' relata, não protege")
