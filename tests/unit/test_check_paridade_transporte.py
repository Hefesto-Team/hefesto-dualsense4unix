"""Testes do censo do mapa de canais — a camada 0 do portão (PARIDADE-PORTAO-01).

Um por regra de reprovação, todos contra CSV de mentira em `tmp_path`, mais um
que roda contra a ÁRVORE REAL e confere o instrumento contra uma contagem
independente: nesta casa o instrumento já mentiu mais que o produto, e uma
régua que ninguém confere é a mesma doença que o portão existe para curar.

PROVA DE QUE MORDEM (arrancar, ver reprovar, devolver) — feita em 11/08/2026,
uma cura de cada vez, com este arquivo e o `test_portao_do_mapa_esta_ligado.py`
rodando juntos. Dez arrancamentos no censo, quatro no que o liga: TODOS
reprovaram, cada um derrubando só os testes da sua própria regra, e com as
curas devolvidas a rodada de controle voltou inteira verde. O que cada
arrancamento derrubou está escrito na docstring do teste correspondente.
"""
from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "check_paridade_transporte.py"
CSV_REAL = RAIZ_REAL / "docs" / "data" / "mapa-controles.csv"

#: Cabeçalho mínimo: as colunas exigidas mais um par `cabo_*`/`radio_*` de cada
#: sufixo que as regras leem. De propósito NÃO é o cabeçalho real — o portão
#: descobre os pares lendo o arquivo, e um teste que copiasse as 45 colunas de
#: hoje estaria fixando uma contagem que muda toda leva.
CABECALHO = [
    "chave",
    "controle",
    "existe",
    "cabo_aciona",
    "radio_aciona",
    "cabo_confianca",
    "radio_confianca",
    "cabo_canal",
    "radio_canal",
    "teste_que_morde",
    "provado_em",
    "validade_dias",
    "assimetria_declarada",
    "id",
]

#: Um teste de verdade, na árvore falsa, para a regra 2 ter o que indexar.
TESTE_FALSO = '''\
"""Arquivo de teste de mentira, só para o índice por AST ter o que ler."""


def test_a_lightbar_acende():
    assert True


def ajudante_que_o_pytest_ignora():
    return True


class TestOEnvelope:
    def test_o_crc_bate(self):
        assert True
'''


def modulo_do_censo():
    """Importa o script como módulo, para os testes que precisam da constante.

    O registro em `sys.modules` ANTES do `exec_module` não é enfeite: sem ele o
    `@dataclass` do módulo estoura `AttributeError: 'NoneType' object has no
    attribute '__dict__'` ao resolver a anotação em string do `from __future__
    import annotations`, porque o `dataclasses` procura o módulo pelo nome e não
    o acha. Medido aqui em 11/08.
    """
    spec = importlib.util.spec_from_file_location("censo_do_mapa", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    try:
        spec.loader.exec_module(modulo)
    except Exception:  # pragma: no cover - defensivo
        sys.modules.pop(spec.name, None)
        raise
    return modulo


def escreve_mapa(caminho: Path, linhas: list[dict[str, str]]) -> None:
    """Escreve o CSV de mentira, completando com vazio o que a linha não disser."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CABECALHO)
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({coluna: linha.get(coluna, "") for coluna in CABECALHO})


def monta_arvore(
    tmp_path: Path,
    linhas: list[dict[str, str]],
    *,
    publicar: bool = True,
    cabecalho: list[str] | None = None,
) -> Path:
    """Uma árvore mínima: o mapa, um `tests/` indexável e o `specs.html`."""
    caminho_csv = tmp_path / "docs" / "data" / "mapa-controles.csv"
    if cabecalho is None:
        escreve_mapa(caminho_csv, linhas)
    else:
        caminho_csv.parent.mkdir(parents=True, exist_ok=True)
        with caminho_csv.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=cabecalho)
            escritor.writeheader()
            for linha in linhas:
                escritor.writerow({c: linha.get(c, "") for c in cabecalho})

    pasta_de_testes = tmp_path / "tests" / "unit"
    pasta_de_testes.mkdir(parents=True, exist_ok=True)
    (pasta_de_testes / "test_exemplo.py").write_text(TESTE_FALSO, encoding="utf-8")
    (pasta_de_testes / "ajudantes.py").write_text("VALOR = 1\n", encoding="utf-8")

    publicados = [linha.get("id", "") for linha in linhas] if publicar else []
    (tmp_path / "specs.html").write_text(
        "<html><body>" + " ".join(publicados) + "</body></html>", encoding="utf-8"
    )
    return caminho_csv


def rodar(caminho_csv: Path, raiz: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), "--csv", str(caminho_csv), *extra],
        capture_output=True,
        text=True,
        check=False,
    )


def linha_forte(**mudancas: str) -> dict[str, str]:
    """Uma célula que AFIRMA: aciona por cabo, e alguém mediu."""
    base = {
        "chave": "luz.lightbar.cor",
        "controle": "dualsense",
        "existe": "tem",
        "cabo_aciona": "sim",
        "radio_aciona": "sim",
        "cabo_confianca": "medido",
        "radio_confianca": "medido",
        "cabo_canal": "hidraw",
        "radio_canal": "hidraw",
        "teste_que_morde": "tests/unit/test_exemplo.py::test_a_lightbar_acende",
        "id": "luz.lightbar.cor@dualsense",
    }
    base.update(mudancas)
    return base


# --------------------------------------------------------------------------
# O caso legítimo. Um portão que reprova tudo é tão inútil quanto um que não
# reprova nada — este teste é o contrapeso de todos os de baixo.
# --------------------------------------------------------------------------
def test_mapa_com_afirmacao_forte_e_teste_que_morde_passa(tmp_path: Path) -> None:
    caminho = monta_arvore(tmp_path, [linha_forte()])
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "OK:" in processo.stdout
    assert "Resumo do censo" in processo.stdout


# --------------------------------------------------------------------------
# REGRA 1 — sem-mordida
# --------------------------------------------------------------------------
def test_afirmacao_forte_sem_teste_que_morda_reprova(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: trocado, no script, o `if not mordidas:` da regra 1 por
    `if False:` (a afirmação forte deixa de cobrar rede). Reprovaram DOIS
    testes: este, e o `test_o_censo_conta_o_mesmo_que_uma_regua_independente`,
    que viu a régua achar zero onde a contagem à mão, feita contra o mapa real
    na hora, achava muitas. Cura devolvida.
    """
    caminho = monta_arvore(tmp_path, [linha_forte(teste_que_morde="")])
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1
    assert "sem-mordida" in processo.stdout
    assert "luz.lightbar.cor@dualsense" in processo.stdout


def test_afirmacao_fraca_sem_teste_nao_reprova(tmp_path: Path) -> None:
    """`inferido-do-codigo` sem teste é honestidade, não defeito: não reprova."""
    caminho = monta_arvore(
        tmp_path,
        [
            linha_forte(
                teste_que_morde="",
                cabo_confianca="inferido-do-codigo",
                radio_confianca="inferido-do-codigo",
            )
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout


# --------------------------------------------------------------------------
# REGRA 2 — mordida-fantasma
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("alvo", "pedaco_esperado"),
    [
        ("tests/unit/test_que_nao_existe.py::test_x", "não existe nesta árvore"),
        ("tests/unit/test_exemplo.py::test_inventado", "não tem `test_inventado`"),
        (
            "tests/unit/test_exemplo.py::ajudante_que_o_pytest_ignora",
            "não tem `ajudante_que_o_pytest_ignora`",
        ),
        ("tests/unit/ajudantes.py::VALOR", "o pytest NÃO o coleta"),
        (
            "tests/unit/test_exemplo.py::TestOEnvelope::test_inventado",
            "não tem o teste `test_inventado`",
        ),
        ("tests/unit/test_exemplo.py::TestQueNaoExiste", "não tem `TestQueNaoExiste`"),
        ("o pareamento por rádio, medido à mão", "não é alvo de pytest"),
    ],
)
def test_mordida_que_o_pytest_nao_coleta_reprova(
    tmp_path: Path, alvo: str, pedaco_esperado: str
) -> None:
    """MORDIDA MEDIDA: posto um `return None` na primeira linha de
    `motivo_de_o_pytest_nao_coletar` (todo alvo passa a valer). Os SETE casos
    deste parametrize reprovaram de uma vez, e nenhum outro teste caiu junto.
    Cura devolvida.

    Os sete cobrem as formas de mentira que a coluna aceita sem piscar: arquivo
    inexistente, função inexistente, função que existe mas o pytest não coleta
    (não começa com `test`), arquivo que existe mas está fora da convenção de
    nome, método inexistente dentro de classe que existe, classe inexistente, e
    prosa em vez de id de nó — que é a forma mais provável de alguém preencher
    a coluna com boa intenção e rede nenhuma.
    """
    caminho = monta_arvore(tmp_path, [linha_forte(teste_que_morde=alvo)])
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "mordida-fantasma" in processo.stdout
    assert pedaco_esperado in processo.stdout


def test_alvos_aceitos_pelo_pytest_passam(tmp_path: Path) -> None:
    """As quatro formas legítimas de id de nó, e duas na mesma célula."""
    aceitos = [
        "tests/unit/test_exemplo.py",
        "tests/unit/test_exemplo.py::test_a_lightbar_acende",
        "tests/unit/test_exemplo.py::test_a_lightbar_acende[cabo-vermelho]",
        "tests/unit/test_exemplo.py::TestOEnvelope::test_o_crc_bate",
        "tests/unit/test_exemplo.py::test_a_lightbar_acende; "
        "tests/unit/test_exemplo.py::TestOEnvelope::test_o_crc_bate",
    ]
    for alvo in aceitos:
        caminho = monta_arvore(tmp_path, [linha_forte(teste_que_morde=alvo)])
        processo = rodar(caminho, tmp_path)
        assert processo.returncode == 0, f"{alvo}\n{processo.stdout}"


def test_sem_pasta_de_testes_a_regra_dois_se_desliga_em_vez_de_acusar_tudo(
    tmp_path: Path,
) -> None:
    """Índice vazio não pode virar "todo alvo é fantasma".

    É a mesma decisão do `validar-referencias-docs.py`: um gate que reprova
    tudo quando tropeça é pior que gate nenhum. E o desligamento é DITO, não
    calado — o resumo imprime a regra desligada.
    """
    caminho = monta_arvore(tmp_path, [linha_forte()])
    for arquivo in sorted((tmp_path / "tests").rglob("*.py")):
        arquivo.unlink()
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "regra DESLIGADA" in processo.stdout
    assert "mordida-fantasma" in processo.stdout


# --------------------------------------------------------------------------
# REGRA 3 — prova-vencida
# --------------------------------------------------------------------------
def test_prova_vencida_reprova(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: trocado `if vence < hoje:` por `if False:`. Reprovou
    este teste, e só ele — a regra é isolada das outras. Cura devolvida.
    """
    caminho = monta_arvore(
        tmp_path, [linha_forte(provado_em="2026-07-01", validade_dias="7")]
    )
    processo = rodar(caminho, tmp_path, "--hoje", "2026-08-11")
    assert processo.returncode == 1, processo.stdout
    assert "prova-vencida" in processo.stdout
    assert "2026-07-08" in processo.stdout


def test_prova_dentro_do_prazo_passa(tmp_path: Path) -> None:
    caminho = monta_arvore(
        tmp_path, [linha_forte(provado_em="2026-08-10", validade_dias="30")]
    )
    processo = rodar(caminho, tmp_path, "--hoje", "2026-08-11")
    assert processo.returncode == 0, processo.stdout


def test_as_duas_colunas_vazias_nao_reprovam(tmp_path: Path) -> None:
    """A política de validade ainda é decisão dela (seção 8 do índice da sprint).

    Enquanto ela não existir, cobrar prazo seria castigar quem não prometeu
    nada — e portão que castiga a honestidade é pior que portão nenhum.
    """
    caminho = monta_arvore(tmp_path, [linha_forte(provado_em="", validade_dias="")])
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "prova-vencida" not in processo.stdout


@pytest.mark.parametrize(
    ("provado_em", "validade_dias", "pedaco"),
    [
        ("ontem", "7", "ilegível"),
        ("2026-08-10", "uma semana", "não é um número inteiro"),
        ("2026-08-10", "-3", "é negativo"),
    ],
)
def test_prazo_ilegivel_reprova_em_vez_de_se_desligar(
    tmp_path: Path, provado_em: str, validade_dias: str, pedaco: str
) -> None:
    """Régua que não se consegue ler é regra desligada em silêncio — reprova."""
    caminho = monta_arvore(
        tmp_path, [linha_forte(provado_em=provado_em, validade_dias=validade_dias)]
    )
    processo = rodar(caminho, tmp_path, "--hoje", "2026-08-11")
    assert processo.returncode == 1, processo.stdout
    assert pedaco in processo.stdout


def test_validade_sem_data_e_aviso_nao_falha(tmp_path: Path) -> None:
    caminho = monta_arvore(tmp_path, [linha_forte(provado_em="", validade_dias="30")])
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "AVISO validade-sem-data" in processo.stdout


# --------------------------------------------------------------------------
# REGRA 6 — assimetria não declarada (AVISO hoje, FALHA quando ela mandar)
# --------------------------------------------------------------------------
def test_assimetria_nao_declarada_avisa_e_nao_derruba(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: apagada a chamada de `_regra_da_assimetria` no laço do
    censo. Reprovaram TRÊS testes — este, o do lado mudo e o da promoção pela
    constante. Cura devolvida.
    """
    caminho = monta_arvore(tmp_path, [linha_forte(radio_aciona="não")])
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "AVISO assimetria-nao-declarada" in processo.stdout
    assert "o cabo diz `sim` e o rádio diz `não`" in processo.stdout


def test_lado_mudo_conta_como_assimetria(tmp_path: Path) -> None:
    """É a forma exata da regressão dela: consolidado no cabo, ninguém olhou o rádio."""
    caminho = monta_arvore(
        tmp_path, [linha_forte(radio_aciona="", radio_confianca="", teste_que_morde="")]
    )
    processo = rodar(caminho, tmp_path)
    assert "AVISO assimetria-nao-declarada" in processo.stdout
    assert "não foi respondido" in processo.stdout


def test_assimetria_declarada_silencia_o_aviso(tmp_path: Path) -> None:
    caminho = monta_arvore(
        tmp_path,
        [
            linha_forte(
                radio_aciona="não",
                assimetria_declarada="o rádio não carrega o bloco de áudio",
            )
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert "assimetria-nao-declarada" not in processo.stdout


def test_a_promocao_da_assimetria_e_uma_constante_que_funciona(tmp_path: Path) -> None:
    """A promoção prometida no cabeçalho tem de ser real, não decorativa.

    Sem este teste, `ASSIMETRIA_REPROVA` seria mais uma cura escrita e nunca
    ligada — que é o defeito mais caro desta casa.
    """
    censo = modulo_do_censo()
    caminho = monta_arvore(tmp_path, [linha_forte(radio_aciona="não")])

    censo.ASSIMETRIA_REPROVA = True
    achados, _, _ = censo.censo(caminho, tmp_path, censo.date(2026, 8, 11))
    niveis = {a.nivel for a in achados if a.regra == "assimetria-nao-declarada"}
    assert niveis == {censo.FALHA}


# --------------------------------------------------------------------------
# REGRA 4 — integridade do CSV
# --------------------------------------------------------------------------
def test_coluna_que_some_do_cabecalho_reprova(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: trocado `if faltando:` por `if False:`. Reprovaram este
    teste e o do par de transporte, e o INTERESSANTE é que reprovaram de
    maneiras diferentes — que é a razão de os dois existirem:

      - aqui o script ainda saiu 1, mas por `sem-mordida`: sem a coluna
        `teste_que_morde` no cabeçalho, TODA célula vira "afirmação sem rede".
        O portão acusava a coisa certa pelo motivo errado, e o
        `assert "integridade" in stdout` foi o que pegou isso;
      - no do par de transporte ele EXPLODIU: `KeyError: 'radio_aciona'`,
        stdout vazio, traceback no lugar de relatório.

    Cura devolvida. Reprovar e explodir não são a mesma coisa, e a conferência
    de cabeçalho existe para o portão nunca fazer o segundo.
    """
    cabecalho = [c for c in CABECALHO if c != "teste_que_morde"]
    caminho = monta_arvore(tmp_path, [linha_forte()], cabecalho=cabecalho)
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "integridade" in processo.stdout
    assert "teste_que_morde" in processo.stdout


def test_par_de_transporte_que_some_reprova(tmp_path: Path) -> None:
    """Sem `radio_aciona` não há paridade a medir — o portão diz isso alto."""
    cabecalho = [c for c in CABECALHO if c != "radio_aciona"]
    caminho = monta_arvore(tmp_path, [linha_forte()], cabecalho=cabecalho)
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "radio_aciona" in processo.stdout


def test_id_duplicado_reprova(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: trocado `elif ident in vistos:` por `elif False:`.
    Reprovou só este teste. O mesmo com `if not ident:` derrubou só o de `id`
    vazio. Curas devolvidas. O `id` é a chave que liga o CSV ao `specs.html`:
    duplicado, ele publica uma linha e esconde a outra.
    """
    caminho = monta_arvore(tmp_path, [linha_forte(), linha_forte()])
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "`id` duplicado" in processo.stdout


def test_id_vazio_reprova(tmp_path: Path) -> None:
    caminho = monta_arvore(tmp_path, [linha_forte(id="")])
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "`id` vazio" in processo.stdout


@pytest.mark.parametrize(
    ("coluna", "valor"),
    [
        ("existe", "talvez"),
        ("cabo_canal", "usb-magico"),
        ("radio_confianca", "quase-medido"),
        ("cabo_aciona", "sim?"),
    ],
)
def test_valor_fora_do_dominio_reprova(tmp_path: Path, coluna: str, valor: str) -> None:
    """MORDIDA MEDIDA: desligado o `if valor not in dominio:` do laço que
    confere `DOMINIO_POR_SUFIXO`. Reprovaram os TRÊS casos de coluna com sufixo
    (`cabo_canal`, `radio_confianca`, `cabo_aciona`) e o caso de `existe`
    continuou VERDE — prova de que as duas conferências são independentes.
    Desligando a de `existe` (`if existe not in DOMINIO_EXISTE:`), acontece o
    inverso: cai só o caso de `existe`. Curas devolvidas.

    `cabo_aciona` está na lista porque um valor novo ali desligaria a regra 1
    e a 6 em silêncio, que é a pior forma de um portão morrer.
    """
    caminho = monta_arvore(tmp_path, [linha_forte(**{coluna: valor})])
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "fora do domínio" in processo.stdout
    assert coluna in processo.stdout


# --------------------------------------------------------------------------
# REGRA 5 — mapa não publicado
# --------------------------------------------------------------------------
def test_linha_que_nao_chegou_ao_specs_reprova(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: trocado `if nao_publicados:` por `if False:`. Reprovou
    só este teste. Cura devolvida.

    Esta regra existe porque `gerar-mapa.py --check` compara MTIME, e no runner
    mtime é ordem de checkout: lá ele passa sempre. Aqui se compara conteúdo.
    """
    caminho = monta_arvore(tmp_path, [linha_forte()], publicar=False)
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "mapa-nao-publicado" in processo.stdout
    assert "gerar-mapa.py" in processo.stdout


def test_sem_specs_a_regra_cinco_se_desliga(tmp_path: Path) -> None:
    caminho = monta_arvore(tmp_path, [linha_forte()])
    (tmp_path / "specs.html").unlink()
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "regra DESLIGADA" in processo.stdout


# --------------------------------------------------------------------------
# A ÁRVORE REAL — a régua conferida contra uma contagem independente
# --------------------------------------------------------------------------
def test_o_censo_conta_o_mesmo_que_uma_regua_independente() -> None:
    """O instrumento mente mais que o produto: esta é a contraprova dele.

    O teste recalcula, com um `csv.DictReader` próprio, quantas células do mapa
    REAL afirmam `aciona = sim` com `confianca = medido` sem `teste_que_morde`,
    e exige que o script tenha reprovado exatamente esse número de vezes por
    `sem-mordida`. Se a régua começar a enxergar de menos — um sufixo que ela
    deixe de descobrir, um `strip()` que suma — os dois números divergem aqui,
    e não daqui a três levas.

    Nenhuma contagem fica ESCRITA: o número é medido nos dois lados na hora.
    """
    processo = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        cwd=RAIZ_REAL,
    )
    assert processo.returncode in (0, 1), processo.stdout + processo.stderr
    assert "Resumo do censo" in processo.stdout

    with CSV_REAL.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))
    esperado = sum(
        1
        for linha in linhas
        for lado in ("cabo", "radio")
        if (linha[f"{lado}_aciona"] or "").strip() == "sim"
        and (linha[f"{lado}_confianca"] or "").strip() == "medido"
        and not (linha["teste_que_morde"] or "").strip()
    )
    achadas = processo.stdout.count("FALHA sem-mordida:")
    assert achadas == esperado, (
        f"a régua achou {achadas} afirmação(ões) forte(s) sem rede e a contagem "
        f"independente achou {esperado}"
    )
