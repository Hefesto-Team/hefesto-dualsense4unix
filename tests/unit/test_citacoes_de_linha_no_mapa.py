"""O portão de citação de linha alcança as planilhas de `docs/data/`."""
from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "validar-citacoes-de-linha.py"

FONTE = ("\n".join(f"linha_{n} = {n}" for n in range(1, 11))
         + "\nFLAG_DE_AUDIO = 0x01\n")

CABECALHO = ["id", "chave", "nota", "cabo_evidencia"]


DUBLES = {
    "assets/dkms/hid-nintendo/hid-nintendo.c": "a\nb\nc\n",
    "src/hefesto_dualsense4unix/core/led_control.py": "a\nb\nc\n",
    "terceiros/SDL/SDL_hidapi_ps5.c": "a\nb\nc\n",
    "terceiros/SDL/utils.h": "a\nb\nc\n",
}


@pytest.fixture
def arvore(tmp_path: Path) -> Path:
    """Árvore de brinquedo com o módulo citado e a pasta `docs/data/` vazia."""
    modulo = tmp_path / "src" / "hefesto_dualsense4unix" / "core"
    modulo.mkdir(parents=True)
    (modulo / "exemplo.py").write_text(FONTE, encoding="utf-8")
    for relativo, corpo in DUBLES.items():
        alvo = tmp_path / relativo
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text(corpo, encoding="utf-8")
    (tmp_path / "docs" / "protocol").mkdir(parents=True)
    (tmp_path / "docs" / "data").mkdir(parents=True)
    return tmp_path


def planilha(arvore: Path, *celulas: str, nome: str = "mapa-controles.csv") -> Path:
    """Escreve UMA linha de mapa com o módulo `csv` — aspas e tudo."""
    caminho = arvore / "docs" / "data" / nome
    with caminho.open("w", encoding="utf-8", newline="") as fluxo:
        escritor = csv.writer(fluxo)
        escritor.writerow(CABECALHO)
        linha = list(celulas) + [""] * (len(CABECALHO) - 1 - len(celulas))
        escritor.writerow(["luz.lightbar@dualsense", *linha])
    return caminho


def rodar(raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(raiz), *args],
        capture_output=True, text=True, check=False)


def test_a_citacao_boa_no_csv_passa(arvore: Path) -> None:
    """O controle. Sem ele, os outros poderiam estar reprovando por nada."""
    planilha(arvore, "o bit sai de core/exemplo.py:3-5, e é só isso")
    saida = rodar(arvore, "--all")
    assert saida.returncode == 0, saida.stdout
    assert "1 planilha(s)" in saida.stdout, (
        f"a planilha não foi varrida. Disse: {saida.stdout!r}")


def test_a_citacao_alem_do_fim_no_csv_reprova(arvore: Path) -> None:
    """A MORDIDA. É o defeito inteiro que este alcance existe para pegar."""
    planilha(arvore, "o bit sai de core/exemplo.py:900, medido em 11/08")
    saida = rodar(arvore, "--all")
    assert saida.returncode == 1, (
        "citação do mapa apontando além do fim do arquivo passou — o mapa "
        f"propagaria uma afirmação forte e falsa. Disse: {saida.stdout!r}")
    assert "tem 11 linha(s)" in saida.stdout, (
        "o erro não diz quantas linhas o arquivo tem — quem for consertar "
        f"precisa disso. Disse: {saida.stdout!r}")


def test_o_achado_nomeia_a_linha_do_mapa_e_a_coluna(arvore: Path) -> None:
    """Uma célula não se acha por número de linha física: acha-se por id+coluna."""
    planilha(arvore, "luz.lightbar", "prosa\ncom quebra", "core/exemplo.py:900")
    saida = rodar(arvore, "--all")
    assert saida.returncode == 1, saida.stdout
    assert "luz.lightbar@dualsense" in saida.stdout, (
        f"o achado não diz QUAL linha do mapa. Disse: {saida.stdout!r}")
    assert "cabo_evidencia" in saida.stdout, (
        f"o achado não diz QUAL coluna. Disse: {saida.stdout!r}")
    assert "mapa-controles.csv:2 " in saida.stdout, (
        f"o número da linha não é o começo do registro. Disse: {saida.stdout!r}")


def test_a_faixa_com_o_fim_alem_do_arquivo_reprova(arvore: Path) -> None:
    """447 das 762 citações do mapa são faixas `:N-M`. O `M` é que tem de abrir."""
    planilha(arvore, "o bloco em core/exemplo.py:9-40 diz isso")
    saida = rodar(arvore, "--all")
    assert saida.returncode == 1, (
        "faixa com o fim além do arquivo passou — é a forma mais comum de "
        f"citação no mapa. Disse: {saida.stdout!r}")


def test_a_faixa_que_abre_inteira_passa(arvore: Path) -> None:
    """O outro lado: régua que só sabe reprovar não é régua."""
    planilha(arvore, "o bloco em core/exemplo.py:9-11 diz isso")
    assert rodar(arvore, "--all").returncode == 0


def test_a_promessa_nomeada_dentro_da_celula_e_conferida(arvore: Path) -> None:
    """A pergunta 2 também vale no CSV: a faixa abre e não contém o que promete."""
    planilha(arvore, "com o `FLAG_DE_AUDIO` em `core/exemplo.py:3-5`, medido")
    saida = rodar(arvore, "--all")
    assert saida.returncode == 1, (
        "a faixa não contém o símbolo prometido e o portão calou. Disse: "
        f"{saida.stdout!r}")
    assert "FLAG_DE_AUDIO" in saida.stdout


def test_o_csv_nomeado_a_mao_deixou_de_ser_recusado(arvore: Path) -> None:
    """Antes de 31/08 o script recusava o CSV até quando nomeado, em silêncio."""
    caminho = planilha(arvore, "core/exemplo.py:900")
    saida = rodar(arvore, str(caminho))
    assert saida.returncode == 1, saida.stdout
    assert "Nenhum documento para varrer" not in saida.stdout, (
        "o CSV nomeado à mão continua descartado sem uma palavra de recusa — "
        "recusa silenciosa é a forma mais barata de um portão mentir.")


def test_planilha_nova_em_docs_data_nasce_coberta(arvore: Path) -> None:
    """Defeito de FORMA, o mesmo que o `rglob` da canônica fechou em 26/08."""
    planilha(arvore, "core/exemplo.py:900", nome="planilha-que-ainda-nao-existe.csv")
    saida = rodar(arvore, "--all")
    assert saida.returncode == 1, (
        "planilha nova em docs/data/ nasceu fora do portão. Disse: "
        f"{saida.stdout!r}")


EXTENSOES_QUE_A_LISTA_ESQUECIA = (
    "assets/modprobe.d/hefesto-exemplo.conf",
    "assets/hefesto-exemplo.service",
    "docs/data/ensaios-brutos/exemplo.txt",
    "src/hefesto_dualsense4unix/interface/paginas/exemplo.html",
)


@pytest.mark.parametrize("relativo", EXTENSOES_QUE_A_LISTA_ESQUECIA)
def test_extensao_que_ninguem_listou_nasce_coberta(arvore: Path, relativo: str) -> None:
    """A MORDIDA da O-MAPA-QUE-A-6E-DEIXOU-01 (25/09/2026).

    A conferência da O-MAPA-OUVE-AS-RESPOSTAS-DE-24-09-01 achou as 35 citações
    de `assets/modprobe.d/*.conf` do mapa FORA do portão — `conf` não estava na
    lista de extensões — e uma delas além do fim do arquivo. A cura não
    acrescentou `conf` à lista: a lista saiu, e quem decide o que se cobra é a
    RESOLUÇÃO, como já decidia para o caminho. MORDA ASSIM: devolva a lista
    digitada a `EXTENSOES` e os quatro casos passam calados.
    """
    alvo = arvore / relativo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text("um\ndois\ntrês\n", encoding="utf-8")

    planilha(arvore, f"o valor mora em {relativo}:2-3, e é só isso")
    saida = rodar(arvore, "--all")
    assert saida.returncode == 0, (
        f"a citação de {relativo} que ABRE foi acusada. Disse: {saida.stdout!r}")

    planilha(arvore, f"o valor mora em {relativo}:81, e é só isso")
    saida = rodar(arvore, "--all")
    assert saida.returncode == 1, (
        f"a citação de {relativo} além do fim do arquivo passou calada — a "
        f"extensão ficou fora do portão. Disse: {saida.stdout!r}")
    assert "tem 3 linha(s)" in saida.stdout, saida.stdout


def test_a_celula_com_virgula_e_quebra_de_linha_nao_despedaca_o_endereco(
    arvore: Path,
) -> None:
    """MORDIDA DA FORMA: por que se lê com o módulo `csv`, e não com regex."""
    planilha(arvore, 'nota: um, dois, três\ne aí o bit em core/exemplo.py:9-40,\n'
                     'com o resto da frase depois da vírgula')
    saida = rodar(arvore, "--all")
    assert saida.returncode == 1, (
        "o endereço dentro de uma célula com vírgula e quebra de linha não foi "
        f"conferido. Disse: {saida.stdout!r}")


def test_repositorio_de_fora_fica_calado(arvore: Path) -> None:
    """11 citações do mapa apontam para repo alheio, com repo e tag ao lado."""
    planilha(arvore, "libsdl-org/SDL release-3.4.14 "
                     "src/joystick/hidapi/SDL_hidapi_ps5.c:391-403; "
                     "e src/utils.h:12-99999")
    saida = rodar(arvore, "--all")
    assert saida.returncode == 0, (
        "acusou repositório de fora — reprovar por ler o SDL é o falso "
        f"positivo que desliga o portão. Disse: {saida.stdout!r}")


def test_basename_solto_fica_calado(arvore: Path) -> None:
    """28 citações do mapa são basename sem caminho."""
    planilha(arvore, "o driver faz isso em hid-nintendo.c:99999, e o nosso "
                     "em led_control.py:99999")
    saida = rodar(arvore, "--all")
    assert saida.returncode == 0, (
        f"acusou por um basename sem caminho. Disse: {saida.stdout!r}")


def test_a_forma_curta_no_csv_fica_calada(arvore: Path) -> None:
    """A conservadoria que a HORA DO RELÓGIO obriga."""
    planilha(arvore, "o bloco em core/exemplo.py:1-5, e também :99999 — "
                     "a das 01:51:25 passou 27 s depois da recusa às 01:50:58")
    saida = rodar(arvore, "--all")
    assert saida.returncode == 0, (
        "o portão resolveu uma forma curta dentro da célula e acusou por ela — "
        f"hora de relógio viraria endereço podre. Disse: {saida.stdout!r}")


def test_a_promessa_nao_atravessa_o_separador_de_bloco(arvore: Path) -> None:
    """O ` · ` separa blocos na célula, e o símbolo de um não é promessa do outro."""
    planilha(arvore, "o `FLAG_DE_AUDIO` está em outro lugar · "
                     "e o bloco de hoje é `core/exemplo.py:3-5`")
    saida = rodar(arvore, "--all")
    assert saida.returncode == 0, (
        "colou o símbolo de um bloco no endereço do bloco seguinte. Disse: "
        f"{saida.stdout!r}")


def test_a_isencao_nominal_funciona_e_esta_vazia(arvore: Path) -> None:
    """A porta de saída do portão existe, morde, e hoje não tem ninguém dentro."""
    import ast

    fonte = (RAIZ_REAL / "scripts" / "validar-citacoes-de-linha.py").read_text(
        encoding="utf-8"
    )
    isencao = None
    for no in ast.walk(ast.parse(fonte)):
        alvo = getattr(no, "target", None)
        if isinstance(no, ast.AnnAssign) and getattr(alvo, "id", "") == "CSV_FORA_DO_PORTAO":
            isencao = ast.literal_eval(no.value)
    assert isencao == {}, (
        "alguém isentou um CSV do portão de citações: confira se a razão está "
        f"escrita junto — {isencao}"
    )

    planilha(arvore, "core/exemplo.py:99999", nome="um-csv-qualquer.csv")
    assert rodar(arvore, "--all").returncode != 0, (
        "o portão deixou passar um endereço podre num CSV NÃO isento"
    )


def test_o_mapa_de_verdade_esta_sob_o_portao() -> None:
    """Alcance declarado não é alcance: este teste sente o portão encolher."""
    saida = subprocess.run(
        [sys.executable, str(SCRIPT), str(RAIZ_REAL / "docs/data/mapa-controles.csv")],
        capture_output=True, text=True, cwd=RAIZ_REAL, check=False)
    assert saida.returncode == 0, (
        "há citação de linha podre no mapa — o endereço deixou de abrir:\n"
        + saida.stdout)
    assert "1 planilha(s)" in saida.stdout, (
        f"o mapa não foi varrido. Disse: {saida.stdout!r}")

    conferidas = int(saida.stdout.split()[1])
    assert conferidas >= 700, (
        f"o portão conferiu só {conferidas} citações do mapa, contra as 723 "
        "medidas em 31/08/2026 — o alcance encolheu.")
