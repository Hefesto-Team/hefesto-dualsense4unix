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

import ast
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
    "cabo_de_onde_sei",
    "radio_de_onde_sei",
    "cabo_canal",
    "radio_canal",
    # O par do degrau entrou em 12/08/2026, quando a regra 6 (`grau-sem-ensaio`)
    # passou a exigir ensaio no caderno de bancada para os dois degraus altos.
    # Ele é EXIGIDO no cabeçalho, e não apenas lido: sem a coluna, a régua da
    # regra dura morreria em silêncio. Vazio aqui, que é o que estes casos
    # querem — nenhum deles fala de grau.
    "cabo_ate_onde_foi",
    "radio_ate_onde_foi",
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
        "cabo_de_onde_sei": "medido",
        "radio_de_onde_sei": "medido",
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
                cabo_de_onde_sei="inferido-do-codigo",
                radio_de_onde_sei="inferido-do-codigo",
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
        tmp_path, [linha_forte(radio_aciona="", radio_de_onde_sei="", teste_que_morde="")]
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
        ("radio_de_onde_sei", "quase-medido"),
        ("cabo_aciona", "sim?"),
    ],
)
def test_valor_fora_do_dominio_reprova(tmp_path: Path, coluna: str, valor: str) -> None:
    """MORDIDA MEDIDA: desligado o `if valor not in dominio:` do laço que
    confere `DOMINIO_POR_SUFIXO`. Reprovaram os TRÊS casos de coluna com sufixo
    (`cabo_canal`, `radio_de_onde_sei`, `cabo_aciona`) e o caso de `existe`
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
    REAL afirmam `aciona = sim` com `de_onde_sei = medido` sem `teste_que_morde`,
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
        and (linha[f"{lado}_de_onde_sei"] or "").strip() == "medido"
        and not (linha["teste_que_morde"] or "").strip()
    )
    achadas = processo.stdout.count("FALHA sem-mordida:")
    assert achadas == esperado, (
        f"a régua achou {achadas} afirmação(ões) forte(s) sem rede e a contagem "
        f"independente achou {esperado}"
    )


# --------------------------------------------------------------------------
# REGRA 9 + REGRA 12 — o veredicto da FEATURE, separado do veredicto do SUSPEITO
#
# A cura de 13/08/2026: `resultado` responde pelo SUSPEITO da linha, e há
# ensaio em que as duas respostas são OPOSTAS sem que nenhuma esteja errada.
# Estes casos existem para provar as DUAS metades do contrato — que a coluna
# nova é lida, e que ela não é o botão de desligar a regra 9.
# --------------------------------------------------------------------------
#: Cabeçalho do caderno de bancada, com a coluna de 13/08/2026 no lugar dela:
#: logo depois de `resultado`, que é o par que ela desambigua.
CABECALHO_DO_CADERNO = [
    "id",
    "linha_id",
    "transporte",
    "quando",
    "suspeito",
    "presente",
    "resultado",
    "resultado_da_feature",
    "observado_por",
    "fonte",
    "nota",
]


def escreve_caderno(raiz: Path, ensaios: list[dict[str, str]]) -> None:
    """O caderno de mentira. Sem ele as regras 6, 9, 10 e 12 se desligam."""
    caminho = raiz / "docs" / "data" / "ensaios.csv"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CABECALHO_DO_CADERNO)
        escritor.writeheader()
        for ensaio in ensaios:
            escritor.writerow({c: ensaio.get(c, "") for c in CABECALHO_DO_CADERNO})


def ensaio_do_cabo(**mudancas: str) -> dict[str, str]:
    """Um ensaio de cabo da linha que `linha_forte()` descreve."""
    base = {
        "id": "ensaio-de-mentira",
        "linha_id": "luz.lightbar.cor@dualsense",
        "transporte": "cabo",
        "quando": "2026-08-13T10:00:00",
        "suspeito": "um suspeito qualquer",
        "presente": "sim",
        "resultado": "obedece",
        "observado_por": "olho-dela",
        "nota": "",
    }
    base.update(mudancas)
    return base


def linha_que_obedeceu(**mudancas: str) -> dict[str, str]:
    """A linha forte com o degrau mais alto no cabo — o que pede o caderno."""
    return linha_forte(cabo_ate_onde_foi="O APARELHO OBEDECEU", **mudancas)


def test_resultado_do_suspeito_sozinho_ainda_avisa(tmp_path: Path) -> None:
    """O estado ANTES da cura: `resultado` nega e não há coluna que o desminta.

    Este é o contrapeso do teste seguinte. Sem ele, um `resultado_da_feature`
    lido de qualquer jeito passaria despercebido, porque nada afirmaria que a
    régua ainda enxerga a negação quando ela é a única coisa escrita.
    """
    caminho = monta_arvore(tmp_path, [linha_que_obedeceu()])
    escreve_caderno(tmp_path, [ensaio_do_cabo(resultado="não obedece")])
    processo = rodar(caminho, tmp_path)
    assert "grau-sem-ensaio-que-obedeca" in processo.stdout, processo.stdout


def test_a_coluna_da_feature_desmente_o_resultado_do_suspeito(tmp_path: Path) -> None:
    """A cura: o `resultado` é do SUSPEITO, e a coluna nova diz o que a feature fez.

    MORDE? Trocar `veredicto_da_feature(ensaio)` de volta por
    `(ensaio.get("resultado") or "").strip()` em `_regra_do_caderno` faz este
    teste reprovar — o aviso volta a sair para um ensaio em que o aparelho
    obedeceu, que é o defeito que a cura de 13/08/2026 tirou do portão.
    """
    caminho = monta_arvore(tmp_path, [linha_que_obedeceu()])
    escreve_caderno(
        tmp_path,
        [
            ensaio_do_cabo(
                resultado="não obedece",
                resultado_da_feature="obedece",
                nota="o suspeito caiu na mesma rodada; o R2 endureceu",
            )
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert "grau-sem-ensaio-que-obedeca" not in processo.stdout, processo.stdout


def test_a_feature_que_de_fato_nao_obedeceu_continua_avisando(tmp_path: Path) -> None:
    """A GUARDA: a cura não pode ter virado "desligar a regra 9".

    O ensaio aqui é genuinamente contraditório — a linha jura `O APARELHO
    OBEDECEU` e o caderno diz, na coluna da FEATURE, que ela não obedeceu. Se
    este aviso sumir, o portão parou de fazer a única pergunta que ele existe
    para fazer, e a coluna nova virou a saída em vez da régua.
    """
    caminho = monta_arvore(tmp_path, [linha_que_obedeceu()])
    escreve_caderno(
        tmp_path,
        [
            ensaio_do_cabo(
                resultado="obedece",
                resultado_da_feature="não obedece",
                nota="o suspeito se sustentou, mas o aparelho não fez nada",
            )
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert "grau-sem-ensaio-que-obedeca" in processo.stdout, processo.stdout
    assert "'não obedece'" in processo.stdout, processo.stdout


def test_veredicto_da_feature_fora_do_vocabulario_reprova(tmp_path: Path) -> None:
    """Regra 12, primeira metade: valor novo na coluna nova é FALHA, não silêncio.

    Sem isto, `resultado_da_feature = talvez` desligaria a regra 9 sem dizer
    nada — o `talvez` não está em `RESULTADOS_QUE_SUSTENTAM`, mas também não
    está em lugar nenhum que alguém leia.
    """
    caminho = monta_arvore(tmp_path, [linha_que_obedeceu()])
    escreve_caderno(
        tmp_path,
        [
            ensaio_do_cabo(
                resultado="obedece",
                resultado_da_feature="talvez",
                nota="uma nota qualquer",
            )
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "FALHA veredicto-da-feature-mal-declarado" in processo.stdout
    assert "vocabulário do caderno" in processo.stdout


def test_veredicto_da_feature_que_diverge_sem_nota_reprova(tmp_path: Path) -> None:
    """Regra 12, segunda metade: divergir sem explicar é o botão de desligar.

    É esta metade que faz a coluna ser CARA. Quem quiser calar a regra 9 tem de
    escrever no caderno, na mesma linha, o que o aparelho fez — que é o preço
    que a casa cobra em toda parte.
    """
    caminho = monta_arvore(tmp_path, [linha_que_obedeceu()])
    escreve_caderno(
        tmp_path,
        [
            ensaio_do_cabo(
                resultado="não obedece",
                resultado_da_feature="obedece",
                nota="",
            )
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "FALHA veredicto-da-feature-mal-declarado" in processo.stdout
    assert "`nota` está vazia" in processo.stdout


def test_caderno_sem_a_coluna_nova_segue_lendo_o_resultado(tmp_path: Path) -> None:
    """Compatibilidade: 76 dos 77 ensaios reais não têm a coluna preenchida.

    Um caderno SEM a coluna no cabeçalho — que é o de qualquer árvore anterior a
    13/08/2026 — tem de continuar sendo lido por `resultado`, sem estourar e sem
    mudar de veredicto. Coluna nova que quebra o dado velho não é cura.
    """
    caminho = monta_arvore(tmp_path, [linha_que_obedeceu()])
    caderno = tmp_path / "docs" / "data" / "ensaios.csv"
    caderno.parent.mkdir(parents=True, exist_ok=True)
    antigas = [c for c in CABECALHO_DO_CADERNO if c != "resultado_da_feature"]
    with caderno.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=antigas)
        escritor.writeheader()
        escritor.writerow(
            {c: ensaio_do_cabo(resultado="não obedece").get(c, "") for c in antigas}
        )
    processo = rodar(caminho, tmp_path)
    assert "grau-sem-ensaio-que-obedeca" in processo.stdout, processo.stdout
    assert "veredicto-da-feature" not in processo.stdout, processo.stdout


def test_o_caderno_real_declara_a_coluna_da_feature() -> None:
    """Contra a ÁRVORE REAL: a coluna existe, e quem a preenche explica por quê.

    Sem este caso, alguém poderia apagar a coluna do `docs/data/ensaios.csv` e
    os testes acima — todos contra caderno de mentira — continuariam verdes,
    enquanto o portão real voltaria a ler o veredicto do SUSPEITO como se fosse
    o da feature. Nenhuma contagem fica escrita aqui: tudo é medido na hora.
    """
    caderno_real = RAIZ_REAL / "docs" / "data" / "ensaios.csv"
    with caderno_real.open(encoding="utf-8", newline="") as arquivo:
        ensaios = list(csv.DictReader(arquivo))
    assert ensaios and "resultado_da_feature" in ensaios[0]

    declarados = [e for e in ensaios if (e.get("resultado_da_feature") or "").strip()]
    for ensaio in declarados:
        veredicto = ensaio["resultado_da_feature"].strip()
        assert veredicto in {"obedece", "não obedece", "parcial", "inconclusivo"}, (
            f"o ensaio `{ensaio['id']}` usa um veredicto fora do vocabulário "
            f"do caderno: {veredicto!r}"
        )
        if veredicto != (ensaio.get("resultado") or "").strip():
            assert (ensaio.get("nota") or "").strip(), (
                f"o ensaio `{ensaio['id']}` diverge de `resultado` e não explica "
                "na `nota` — é exatamente o que a regra 12 cobra"
            )


#: Quem, além da bancada, ESCREVE no caderno com a lista de colunas na mão. A
#: bancada já tem o seu par em `test_bancada_nomeia_coluna_que_o_csv_nao_tem.py`;
#: estes dois não tinham nenhum, e foi assim que a coluna de 13/08/2026 quase
#: passou deixando os dois desalinhados EM SILÊNCIO — o `csv.writer` do
#: `ensaio_rumble_um_bit_por_vez.py` escreve por POSIÇÃO, então uma coluna a
#: menos não estoura: ela empurra `fonte` para dentro de `observado_por`.
ESCRITORES_DO_CADERNO = (
    "scripts/ensaio_rumble_um_bit_por_vez.py",
    "scripts/migrar-mapa-v2.py",
)


def _listas_literais_de_colunas(fonte: Path) -> list[list[str]]:
    """Toda lista literal de strings do arquivo que tenha cara de cabeçalho.

    Por AST, não por texto: uma expressão regular acharia a lista dentro de um
    comentário ou de uma docstring e passaria a medir prosa.
    """
    achadas = []
    for no in ast.walk(ast.parse(fonte.read_text(encoding="utf-8"))):
        if not isinstance(no, ast.List):
            continue
        valores = [
            item.value for item in no.elts
            if isinstance(item, ast.Constant) and isinstance(item.value, str)
        ]
        if len(valores) == len(no.elts) and {"linha_id", "observado_por"} <= set(valores):
            achadas.append(valores)
    return achadas


@pytest.mark.parametrize("relativo", ESCRITORES_DO_CADERNO)
def test_quem_escreve_no_caderno_conhece_todas_as_colunas(relativo: str) -> None:
    """Escritor que não conhece uma coluna desalinha o caderno inteiro, calado.

    A régua é o cabeçalho REAL de `docs/data/ensaios.csv`, lido na hora — nunca
    uma lista escrita aqui, que envelheceria junto com as que ela vigia.
    """
    with (RAIZ_REAL / "docs" / "data" / "ensaios.csv").open(
        encoding="utf-8", newline=""
    ) as arquivo:
        cabecalho = next(csv.reader(arquivo))

    listas = _listas_literais_de_colunas(RAIZ_REAL / relativo)
    assert listas, (
        f"{relativo} não tem mais nenhuma lista de colunas do caderno: ou ele "
        "parou de escrever nele, e sai desta lista, ou este teste ficou cego"
    )
    for lista in listas:
        assert lista == cabecalho, (
            f"{relativo} escreve o caderno com as colunas {lista}, e o cabeçalho "
            f"de docs/data/ensaios.csv é {cabecalho}. O `csv.writer` grava por "
            "POSIÇÃO: uma coluna faltando não estoura, ela empurra todo o resto"
        )
