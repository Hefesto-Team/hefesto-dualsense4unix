"""O portão que ABRE cada `arquivo:linha` de `docs/protocol/` — CITACOES-DERIVADAS-01.

O `validar-referencias-docs.py` confere o ARQUIVO. Nenhuma refatoração renomeia
`core/backend_pydualsense.py`; toda refatoração move o que estava na linha 789
dele. A metade que apodrece sozinha não tinha portão nenhum.

O CASO MEDIDO, em 13/08/2026, antes de qualquer conserto — o portão novo rodado
contra `docs/protocol/` inteiro acusou DOIS endereços, e nenhum falso positivo:

    docs/protocol/dualsense-referencia-canonica.md:361:
      `core/backend_pydualsense.py:789` -- a faixa não contém
      `VALID_FLAG1_AUDIO_CONTROL2_ENABLE`, que a citação promete
    docs/protocol/dualsense-referencia-canonica.md:894:
      `core/physical_report_reader.py:854-865` -- a faixa não contém
      `_observe_jack`, que a citação promete

O primeiro sustentava um grau **ALTA — lido no código**: quem fosse conferir
abriria `:789`, cairia no meio de um docstring e não acharia flag nenhum (ele
mora em `:937`). A afirmação continuava verdadeira; o endereço é que caducou.

PROVA DE QUE MORDE — as três rodadas estão em cada teste daqui, mas a mordida
principal é esta: com a régua da promessa nomeada arrancada de
`scripts/validar-citacoes-de-linha.py` (a chamada a `nomes_prometidos`
substituída por `set()`), o portão devolve `OK: 122 citação(ões) de linha
conferida(s)` para a árvore de 13/08, endereços podres e tudo — que é o
estado exato em que a casa estava.

Os testes de forma rodam contra árvore de brinquedo; o último roda contra a
árvore REAL, e é ele que impede o portão de ser enfraquecido em silêncio.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "validar-citacoes-de-linha.py"
CI = RAIZ_REAL / ".github" / "workflows" / "ci.yml"
PRE_COMMIT = RAIZ_REAL / ".pre-commit-config.yaml"

COMANDO = "scripts/validar-citacoes-de-linha.py --all"


def rodar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--all", "--root", str(raiz)],
        capture_output=True, text=True, cwd=raiz, check=False)


@pytest.fixture
def arvore(tmp_path: Path) -> Path:
    """Uma árvore de brinquedo com um módulo de dez linhas e um documento vazio."""
    modulo = tmp_path / "src" / "hefesto_dualsense4unix" / "core"
    modulo.mkdir(parents=True)
    (modulo / "exemplo.py").write_text(
        "\n".join(f"linha_{n} = {n}" for n in range(1, 11)) + "\n"
        "FLAG_DE_AUDIO = 0x01\n",
        encoding="utf-8")
    (tmp_path / "docs" / "protocol").mkdir(parents=True)
    return tmp_path


def documento(arvore: Path, texto: str) -> None:
    (arvore / "docs" / "protocol" / "exemplo.md").write_text(texto, encoding="utf-8")


def test_a_citacao_que_abre_passa(arvore: Path) -> None:
    """O controle. Sem ele, os outros poderiam estar reprovando por nada."""
    documento(arvore, "O valor sai de `core/exemplo.py:3-5`, e é só isso.\n")
    saida = rodar(arvore)
    assert saida.returncode == 0, saida.stdout


def test_a_linha_que_nao_existe_reprova(arvore: Path) -> None:
    """A pergunta 1: o arquivo encolheu e o endereço ficou apontando o vazio."""
    documento(arvore, "O valor sai de `core/exemplo.py:900`.\n")
    saida = rodar(arvore)
    assert saida.returncode == 1, (
        f"citação para além do fim do arquivo passou. Disse: {saida.stdout!r}")
    assert "tem 11 linha(s)" in saida.stdout, (
        "o erro não diz quantas linhas o arquivo tem — quem for consertar "
        f"precisa disso. Disse: {saida.stdout!r}")


def test_a_promessa_nomeada_que_a_faixa_nao_cumpre_reprova(arvore: Path) -> None:
    """A pergunta 2, e é a que pegou o caso real do pré-amp.

    A faixa EXISTE — `:3-5` abre. O que ela não tem é o nome que a citação
    promete, que é exatamente a forma do defeito de 13/08: `:789` existia, e o
    `VALID_FLAG1_AUDIO_CONTROL2_ENABLE` estava em `:937`.
    """
    documento(arvore, "com o `FLAG_DE_AUDIO` em `core/exemplo.py:3-5` | ALTA\n")
    saida = rodar(arvore)
    assert saida.returncode == 1, (
        "a faixa não contém o símbolo prometido e o portão passou — é o defeito "
        f"inteiro que ele existe para pegar. Disse: {saida.stdout!r}")
    assert "FLAG_DE_AUDIO" in saida.stdout, "o erro não nomeia o que foi prometido"


def test_a_promessa_nomeada_cumprida_passa(arvore: Path) -> None:
    """O outro lado da moeda: reapontado para onde a coisa está, ele cala."""
    documento(arvore, "com o `FLAG_DE_AUDIO` em `core/exemplo.py:11` | ALTA\n")
    saida = rodar(arvore)
    assert saida.returncode == 0, saida.stdout


def test_o_nome_entre_parenteses_depois_do_endereco_tambem_e_promessa(
    arvore: Path,
) -> None:
    """A segunda forma que a casa escreve: `arquivo:N-M` (`SIMBOLO`)."""
    documento(arvore, "a entrega em `core/exemplo.py:1-2` (`FLAG_DE_AUDIO`)\n")
    saida = rodar(arvore)
    assert saida.returncode == 1, (
        f"a forma com parênteses não é conferida. Disse: {saida.stdout!r}")


def test_a_fonte_de_fora_da_arvore_e_ignorada(arvore: Path) -> None:
    """136 dos 204 endereços de `docs/protocol/` citam kernel, SDL e wine.

    Reprovar por eles seria reprovar a casa por ter LIDO o driver — que é o
    trabalho mais caro já feito aqui. Eles saem contados, não acusados.
    """
    documento(arvore, "o driver faz isso em `hid-nintendo.c:99999`.\n")
    saida = rodar(arvore)
    assert saida.returncode == 0, (
        f"acusou uma fonte que esta árvore não versiona. Disse: {saida.stdout!r}")
    assert "fora desta árvore" in saida.stdout


def test_a_continuacao_curta_ancorada_na_mesma_linha_e_conferida(
    arvore: Path,
) -> None:
    """`:N` herda o arquivo do endereço explícito da MESMA linha.

    É a forma do defeito real: `core/backend_pydualsense.py:783-790`, com o
    `VALID_FLAG1_AUDIO_CONTROL2_ENABLE` em `:789`.
    """
    documento(arvore,
              "o bloco em `core/exemplo.py:1-5`, com o `FLAG_DE_AUDIO` em `:2`\n")
    saida = rodar(arvore)
    assert saida.returncode == 1, (
        "a continuação `:2` ancorada na mesma linha não foi conferida — era "
        f"essa a forma do endereço podre de 13/08. Disse: {saida.stdout!r}")


def test_a_continuacao_curta_sem_ancora_na_linha_nao_e_adivinhada(
    arvore: Path,
) -> None:
    """A conservadoria medida, e ela custou seis acusações falsas para nascer.

    Resolver `:N` pela "última citação vista no documento" acusou de uma vez
    `:1644-1646`, `:1718-1725`, `:1219-1250`, `:2466-2510`, `:2547` e `:2586` em
    `externos-referencia-canonica.md` — todas do `hid-nintendo.c`, todas
    resolvidas contra o `core/external_leds.py:155` que aparecia dez linhas
    acima. Portão que inventa âncora acusa o documento certo pelo motivo errado.
    """
    documento(arvore,
              "primeiro `core/exemplo.py:1`.\n\n"
              "muito depois, falando de outro arquivo, `:99999`.\n")
    saida = rodar(arvore)
    assert saida.returncode == 0, (
        "o portão adivinhou a âncora de uma continuação solta e acusou por ela. "
        f"Disse: {saida.stdout!r}")


def test_a_arvore_de_verdade_esta_limpa() -> None:
    """Contra a árvore REAL: depois do reaponte de 13/08, ela abre inteira.

    Este é o teste que sente uma refatoração futura mover um endereço citado —
    e é por isso que ele roda contra a árvore de verdade e não contra brinquedo.
    """
    saida = subprocess.run(
        [sys.executable, str(SCRIPT), "--all"],
        capture_output=True, text=True, cwd=RAIZ_REAL, check=False)
    assert saida.returncode == 0, (
        "há citação de linha podre em docs/protocol/ — o endereço deixou de "
        f"abrir no que promete:\n{saida.stdout}")


def test_o_portao_esta_ligado_no_ci_e_no_pre_commit() -> None:
    """PORTÃO-VIVO-01: gate que ninguém roda não é gate, é arquivo."""
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

    hooks = yaml.safe_load(PRE_COMMIT.read_text(encoding="utf-8"))
    entradas = [
        hook.get("entry", "")
        for repositorio in hooks.get("repos") or []
        for hook in repositorio.get("hooks") or []
    ]
    assert any(COMANDO in entrada for entrada in entradas), (
        f"nenhum hook do pre-commit roda `{COMANDO}`")
