"""O grau forte do mapa exige ensaio no caderno de bancada — ou o portão reprova.

O DEFEITO QUE ORIGINOU ESTE ARQUIVO, medido em 12/08/2026 por mutação numa cópia
da árvore: um agente escreveu a afirmação mais forte que o vocabulário da casa
permite — `cabo_ate_onde_foi = radio_ate_onde_foi = O APARELHO OBEDECEU`,
`provado_por =
olho-dela`, `provado_em` de hoje — numa linha com ZERO ensaios em
`docs/data/ensaios.csv`, e `scripts/check_paridade_transporte.py` devolveu
exatamente o mesmo número de reprovações de antes. A mentira passou inteira,
porque o portão não mencionava o caderno de bancada uma única vez.

O caso central deste arquivo é literalmente aquela mutação. E junto vem o caso
SIMÉTRICO — linha com grau forte E ensaio correspondente passa —, sem o qual a
regra viraria "grau é proibido", que é uma forma de o portão mentir ao contrário.

PROVA DE QUE MORDEM (arrancar, ver reprovar, devolver), 12/08/2026: está na
docstring de cada teste, uma cura de cada vez.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

# Reuso deliberado do arquivo irmão (o dos testes das regras 1 a 5, 7 e 8): o
# jeito de importar o script como módulo, o `tests/` de mentira e o cabeçalho
# mínimo já estão medidos lá, e duas cópias divergiriam no dia em que uma coluna
# entrasse. O que este arquivo acrescenta é o CADERNO — que o irmão não escreve.
from tests.unit.test_check_paridade_transporte import (
    CABECALHO as CABECALHO_DO_IRMAO,
)
from tests.unit.test_check_paridade_transporte import (
    RAIZ_REAL,
    SCRIPT,
    TESTE_FALSO,
    modulo_do_censo,
)

ENSAIOS_REAIS = RAIZ_REAL / "docs" / "data" / "ensaios.csv"
CSV_REAL = RAIZ_REAL / "docs" / "data" / "mapa-controles.csv"

#: O cabeçalho do irmão mais a coluna que a regra 11 lê. Ela fica FORA do
#: mínimo exigido de propósito — regra de aviso não derruba árvore que ainda não
#: tem a coluna —, então é aqui que ela entra.
CABECALHO = [*CABECALHO_DO_IRMAO, "mordida_provada_em"]

#: As colunas do caderno de bancada, na ordem do arquivo real. `linha_id` e
#: `transporte` são as que fazem o casamento; `resultado` e `observado_por` são
#: as que as regras 9 e 10 leem.
CABECALHO_DO_CADERNO = [
    "id",
    "linha_id",
    "transporte",
    "quando",
    "suspeito",
    "presente",
    "resultado",
    "observado_por",
    "fonte",
    "nota",
]


def ensaio(
    linha_id: str,
    transporte: str,
    *,
    resultado: str = "obedece",
    observado_por: str = "olho-dela",
    identificador: str = "ensaio-de-mentira",
) -> dict[str, str]:
    """Uma linha do caderno, com o mínimo que o casamento e as regras leem."""
    return {
        "id": identificador,
        "linha_id": linha_id,
        "transporte": transporte,
        "quando": "2026-08-12T10:00:00",
        "suspeito": "o suspeito de mentira deste ensaio",
        "presente": "sim",
        "resultado": resultado,
        "observado_por": observado_por,
        "fonte": "bancada de mentira",
        "nota": "escrito por um teste",
    }


def linha_com_grau(**mudancas: str) -> dict[str, str]:
    """A linha da mutação de 12/08: o degrau mais alto, nos dois transportes.

    A chave é a mesma que o agente usou (`audio.jack.deteccao@pro`), e o
    `teste_que_morde` aponta um teste REAL de outra feature — que é o que fazia
    a mentira atravessar as regras 1 e 2 sem um arranhão.
    """
    base = {
        "chave": "audio.jack.deteccao",
        "controle": "pro",
        "existe": "tem",
        "cabo_aciona": "sim",
        "radio_aciona": "sim",
        "cabo_de_onde_sei": "medido",
        "radio_de_onde_sei": "medido",
        "cabo_canal": "hidraw",
        "radio_canal": "hidraw",
        "cabo_ate_onde_foi": "O APARELHO OBEDECEU",
        "radio_ate_onde_foi": "O APARELHO OBEDECEU",
        "teste_que_morde": "tests/unit/test_exemplo.py::test_a_lightbar_acende",
        "provado_em": "2026-08-12",
        "id": "audio.jack.deteccao@pro",
    }
    base.update(mudancas)
    return base


def monta_arvore(
    tmp_path: Path,
    linhas: list[dict[str, str]],
    ensaios: list[dict[str, str]] | None,
    *,
    cabecalho: list[str] | None = None,
) -> Path:
    """Uma árvore mínima com CADERNO: o mapa, o `tests/`, o `specs.html` e os ensaios.

    `ensaios=None` significa "esta árvore não tem caderno nenhum" — que é o caso
    em que a regra 6 tem de se DESLIGAR em voz alta, e não acusar todo mundo.
    """
    colunas = cabecalho if cabecalho is not None else CABECALHO
    caminho_csv = tmp_path / "docs" / "data" / "mapa-controles.csv"
    caminho_csv.parent.mkdir(parents=True, exist_ok=True)
    with caminho_csv.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=colunas)
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({coluna: linha.get(coluna, "") for coluna in colunas})

    if ensaios is not None:
        caminho_caderno = tmp_path / "docs" / "data" / "ensaios.csv"
        with caminho_caderno.open("w", encoding="utf-8", newline="") as arquivo:
            escritor = csv.DictWriter(arquivo, fieldnames=CABECALHO_DO_CADERNO)
            escritor.writeheader()
            for registro in ensaios:
                escritor.writerow(registro)

    pasta_de_testes = tmp_path / "tests" / "unit"
    pasta_de_testes.mkdir(parents=True, exist_ok=True)
    (pasta_de_testes / "test_exemplo.py").write_text(TESTE_FALSO, encoding="utf-8")

    (tmp_path / "specs.html").write_text(
        "<html><body>" + " ".join(linha.get("id", "") for linha in linhas) + "</body></html>",
        encoding="utf-8",
    )
    return caminho_csv


def rodar(caminho_csv: Path, raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), "--csv", str(caminho_csv)],
        capture_output=True,
        text=True,
        check=False,
    )


# --------------------------------------------------------------------------
# REGRA 6 — grau-sem-ensaio. O caso central é a mutação de 12/08.
# --------------------------------------------------------------------------
def test_o_aparelho_obedeceu_sem_um_ensaio_no_caderno_reprova(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: trocado o `if not ensaios:` de `_regra_do_caderno` por
    `if False:` (o grau forte deixa de cobrar bancada). Reprovaram TRÊS testes:
    este, o do ensaio que é do outro transporte, e o
    `test_o_censo_conta_o_mesmo_que_uma_regua_independente_de_grau`, que viu a
    régua achar zero onde a contagem à mão, feita contra o mapa real na hora,
    achava quatro. Cura devolvida.

    O caderno DESTA árvore não está vazio: ele tem um ensaio de outra linha. Sem
    isso o teste passaria pelo motivo errado — o de a regra estar desligada por
    falta de caderno.
    """
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau()],
        [ensaio("luz.lightbar.cor@dualsense", "radio")],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert processo.stdout.count("FALHA grau-sem-ensaio:") == 2, processo.stdout
    assert "audio.jack.deteccao@pro" in processo.stdout
    assert "docs/data/ensaios.csv" in processo.stdout


def test_grau_forte_com_ensaio_dos_dois_lados_passa(tmp_path: Path) -> None:
    """O caso SIMÉTRICO, sem o qual a regra viraria "grau é proibido".

    Um portão que reprova toda afirmação forte não protege nada: ele só ensina a
    baixar o grau para calar o portão, que é a mesma mentira ao contrário.
    """
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(mordida_provada_em="2026-08-12")],
        [
            ensaio("audio.jack.deteccao@pro", "cabo", identificador="ensaio-cabo"),
            ensaio("audio.jack.deteccao@pro", "radio", identificador="ensaio-radio"),
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "grau-sem-ensaio" not in processo.stdout


def test_ensaio_do_radio_nao_sustenta_o_grau_do_cabo(tmp_path: Path) -> None:
    """O casamento é por transporte, e é o coração deste mapa.

    A frase dela que fez este mapa existir foi "tínhamos algo para o cabo e na
    hora do vamos ver a versão de BT não funcionava". Aceitar ensaio de um lado
    como prova do outro seria escrever essa regressão dentro do portão.
    """
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau()],
        [ensaio("audio.jack.deteccao@pro", "radio")],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert processo.stdout.count("FALHA grau-sem-ensaio:") == 1, processo.stdout
    assert "[cabo]" in processo.stdout


def test_saiu_no_fio_se_sustenta_com_ensaio_que_nega(tmp_path: Path) -> None:
    """O degrau do meio pede que ALGUÉM tenha posto no fio — não que tenha dado certo.

    `SAIU NO FIO` é "o byte saiu, algo voltou". Um ensaio cujo resultado é `não
    obedece` é exatamente isso: o byte saiu e o aparelho não fez. Cobrar
    obediência aqui confundiria os dois degraus da escada.
    """
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(cabo_ate_onde_foi="SAIU NO FIO", radio_ate_onde_foi="SAIU NO FIO")],
        [
            ensaio("audio.jack.deteccao@pro", "cabo", resultado="não obedece"),
            ensaio(
                "audio.jack.deteccao@pro",
                "radio",
                resultado="não obedece",
                identificador="outro",
            ),
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout


def test_montou_nao_pede_ensaio_nenhum(tmp_path: Path) -> None:
    """`MONTOU` é o que a suíte prova sozinha: pedir bancada para ele seria cobrar
    aparelho por algo que o pytest já morde."""
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(cabo_ate_onde_foi="MONTOU", radio_ate_onde_foi="MONTOU")],
        [],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout


def test_sem_caderno_a_regra_se_desliga_em_vez_de_acusar_tudo(tmp_path: Path) -> None:
    """Caderno ausente não pode virar "todo grau é mentira".

    É a mesma decisão do índice de testes por AST: um gate que reprova tudo
    quando tropeça é pior que gate nenhum. E o desligamento é DITO no resumo.
    """
    caminho = monta_arvore(tmp_path, [linha_com_grau()], None)
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "regra DESLIGADA" in processo.stdout
    assert "grau-sem-ensaio" in processo.stdout


# --------------------------------------------------------------------------
# REGRA 4 — o domínio do grau, que é a porta lateral da mentira
# --------------------------------------------------------------------------
def test_grau_fora_da_escada_reprova(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: apagada a entrada `"ate_onde_foi"` de `DOMINIO_POR_SUFIXO`.
    Reprovaram os dois casos deste teste, e mais nenhum. Cura devolvida.

    O caso minúsculo é o que importa: sem domínio, `o aparelho obedeceu` escrito
    em caixa baixa não casaria com `GRAUS_QUE_EXIGEM_ENSAIO` e sairia pela porta
    que a régua não olha — afirmação máxima, custo zero.
    """
    for valor in ("FUNCIONA", "o aparelho obedeceu"):
        caminho = monta_arvore(
            tmp_path,
            [linha_com_grau(cabo_ate_onde_foi=valor, radio_ate_onde_foi="MONTOU")],
            [],
        )
        processo = rodar(caminho, tmp_path)
        assert processo.returncode == 1, f"{valor}\n{processo.stdout}"
        assert "fora do domínio" in processo.stdout
        assert "cabo_ate_onde_foi" in processo.stdout


def test_a_coluna_de_grau_que_some_do_cabecalho_reprova(tmp_path: Path) -> None:
    """Regra dura não se desliga em silêncio: sem a coluna, não há régua."""
    cabecalho = [coluna for coluna in CABECALHO if coluna != "radio_ate_onde_foi"]
    caminho = monta_arvore(tmp_path, [linha_com_grau()], [], cabecalho=cabecalho)
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "integridade" in processo.stdout
    assert "radio_ate_onde_foi" in processo.stdout


# --------------------------------------------------------------------------
# REGRA 9 — o resultado que nega (AVISO hoje, FALHA quando alguém mandar)
# --------------------------------------------------------------------------
def test_obedeceu_sustentado_so_por_ensaio_que_nega_avisa_e_nao_derruba(
    tmp_path: Path,
) -> None:
    """AVISO, e o motivo está no cabeçalho do portão: `resultado` é texto livre e
    a semântica dele é do SUSPEITO, não da feature.

    O caso real é o `gatilho-lado-nao-esta-invertido`: gravado como `não
    obedece` (o suspeito "o mapeamento está invertido" foi eliminado) enquanto a
    nota do mesmo ensaio diz que o R2 endureceu. Reprovar isso seria derrubar
    uma afirmação verdadeira por causa de uma coluna que responde outra
    pergunta.
    """
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(radio_ate_onde_foi="MONTOU")],
        [ensaio("audio.jack.deteccao@pro", "cabo", resultado="não obedece")],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "AVISO grau-sem-ensaio-que-obedeca" in processo.stdout
    assert "não obedece" in processo.stdout


def test_a_promocao_do_resultado_e_uma_constante_que_funciona(tmp_path: Path) -> None:
    """A promoção prometida no cabeçalho tem de ser real, não decorativa.

    Sem este teste, `RESULTADO_REPROVA` seria mais uma cura escrita e nunca
    ligada — o defeito mais caro desta casa.
    """
    censo = modulo_do_censo()
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(radio_ate_onde_foi="MONTOU")],
        [ensaio("audio.jack.deteccao@pro", "cabo", resultado="não obedece")],
    )
    censo.RESULTADO_REPROVA = True
    achados, _, _ = censo.censo(caminho, tmp_path, censo.date(2026, 8, 12))
    niveis = {a.nivel for a in achados if a.regra == "grau-sem-ensaio-que-obedeca"}
    assert niveis == {censo.FALHA}


# --------------------------------------------------------------------------
# REGRA 10 — o olho dela (AVISO hoje; hoje ele custa zero reprovação)
# --------------------------------------------------------------------------
def test_ensaio_sem_o_olho_dela_avisa_e_nao_derruba(tmp_path: Path) -> None:
    """`METODO-DE-ISOLAMENTO.md` diz que só `olho-dela` sustenta o degrau mais
    alto. Ele AVISA e não reprova porque ela aprovou uma frase — "grau forte
    exige ensaio correspondente" — e cobrar QUEM observou é uma segunda regra,
    que ninguém pediu.
    """
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(radio_ate_onde_foi="MONTOU")],
        [ensaio("audio.jack.deteccao@pro", "cabo", observado_por="bancada")],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "AVISO grau-sem-olho-dela" in processo.stdout


def test_a_promocao_do_olho_dela_e_uma_constante_que_funciona(tmp_path: Path) -> None:
    censo = modulo_do_censo()
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(radio_ate_onde_foi="MONTOU")],
        [ensaio("audio.jack.deteccao@pro", "cabo", observado_por="bancada")],
    )
    censo.OLHO_DELA_REPROVA = True
    achados, _, _ = censo.censo(caminho, tmp_path, censo.date(2026, 8, 12))
    niveis = {a.nivel for a in achados if a.regra == "grau-sem-olho-dela"}
    assert niveis == {censo.FALHA}


# --------------------------------------------------------------------------
# REGRA 11 — a mordida que ninguém provou (a coluna que existia e ninguém lia)
# --------------------------------------------------------------------------
def test_grau_forte_com_teste_sem_mordida_provada_avisa(tmp_path: Path) -> None:
    """MORDIDA MEDIDA: trocado o `if (linha.get("mordida_provada_em") or "").strip():`
    de `_regra_da_mordida_nao_provada` por `if True:` (nunca avisa). Reprovaram
    este teste e mais nenhum. Cura devolvida.

    Medido em 12/08/2026: `mordida_provada_em` estava vazia em 293 de 293 linhas
    e nenhuma regra a lia. Um teste apontado e nunca arrancado é a regra da casa
    escrita e não cumprida.
    """
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau()],
        [
            ensaio("audio.jack.deteccao@pro", "cabo", identificador="a"),
            ensaio("audio.jack.deteccao@pro", "radio", identificador="b"),
        ],
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "AVISO mordida-nao-provada" in processo.stdout


def test_a_data_da_mordida_silencia_o_aviso(tmp_path: Path) -> None:
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau(mordida_provada_em="2026-08-12")],
        [
            ensaio("audio.jack.deteccao@pro", "cabo", identificador="a"),
            ensaio("audio.jack.deteccao@pro", "radio", identificador="b"),
        ],
    )
    processo = rodar(caminho, tmp_path)
    # O `returncode` vem ANTES da busca no texto de propósito: sem ele, um
    # portão que estourasse devolveria stdout vazio e este teste — o único
    # negativo da regra 11 — passaria justamente quando tudo quebrou.
    assert processo.returncode == 0, processo.stdout
    assert "mordida-nao-provada" not in processo.stdout


def test_sem_a_coluna_da_mordida_a_regra_onze_se_desliga(tmp_path: Path) -> None:
    """Regra de AVISO se desliga quando falta a coluna; a DURA reprova.

    A distinção é deliberada: derrubar uma árvore inteira por causa de uma
    coluna que só alimenta aviso seria cobrar caro por pouco.
    """
    cabecalho = [coluna for coluna in CABECALHO if coluna != "mordida_provada_em"]
    caminho = monta_arvore(
        tmp_path,
        [linha_com_grau()],
        [
            ensaio("audio.jack.deteccao@pro", "cabo", identificador="a"),
            ensaio("audio.jack.deteccao@pro", "radio", identificador="b"),
        ],
        cabecalho=cabecalho,
    )
    processo = rodar(caminho, tmp_path)
    assert processo.returncode == 0, processo.stdout
    assert "regra DESLIGADA" in processo.stdout
    assert "mordida-nao-provada" in processo.stdout


# --------------------------------------------------------------------------
# A ÁRVORE REAL — a régua conferida contra uma contagem independente
# --------------------------------------------------------------------------
def test_o_censo_conta_o_mesmo_que_uma_regua_independente_de_grau() -> None:
    """O instrumento mente mais que o produto: esta é a contraprova dele.

    A contagem à mão aqui NÃO usa o `eliminacao.py` — ela relê o caderno com um
    `csv.DictReader` próprio, justamente para não repetir o mesmo erro dos dois
    lados. Nenhum número fica escrito: os dois são medidos na hora.
    """
    processo = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        cwd=RAIZ_REAL,
    )
    assert processo.returncode in (0, 1), processo.stdout + processo.stderr

    with ENSAIOS_REAIS.open(encoding="utf-8", newline="") as arquivo:
        lados_com_ensaio = {
            ((registro["linha_id"] or "").strip(), (registro["transporte"] or "").strip())
            for registro in csv.DictReader(arquivo)
        }
    with CSV_REAL.open(encoding="utf-8", newline="") as arquivo:
        linhas = list(csv.DictReader(arquivo))

    esperado = sum(
        1
        for linha in linhas
        for lado in ("cabo", "radio")
        if (linha[f"{lado}_ate_onde_foi"] or "").strip()
        in ("SAIU NO FIO", "O APARELHO OBEDECEU")
        and ((linha["id"] or "").strip(), lado) not in lados_com_ensaio
    )
    achadas = processo.stdout.count("FALHA grau-sem-ensaio:")
    assert achadas == esperado, (
        f"a régua achou {achadas} grau(s) forte(s) sem ensaio e a contagem "
        f"independente achou {esperado}"
    )
