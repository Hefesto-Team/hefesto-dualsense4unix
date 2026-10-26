"""O 232% e o custo de 928,4 por controle não voltam aos textos (08/10/2026).

O «232% de uma antena» saiu de uma estimativa do mockup de 23/09: a entrada contada como
custo fixo e a ponte a quatro fatias. A entrada é elástica e a ponte tira dela, então o número
por controle sai de ``Hz = (C_eff - custo das pontes) / 2 / n`` com o custo da ponte a medir
(``A-PONTE-SE-CONTA-EM-FATIAS-NO-AR-01``). Nenhuma régua ligava o texto à constante; esta liga.

Três réguas da mesma família:

1. nenhum texto vivo de ``docs/``, ``src/`` e ``mockup/`` diz ``232 %`` ou ``928,4``, fora de uma
   lista de isenções declarada, cada uma com a razão (e a isenção que não tem mais o número que
   isenta reprova: isenção morta é régua frouxa);
2. a linha da caixa e do fone do mockup cai no intervalo «300 a 375 fatias» do CSV do orçamento
   de ar, e a conta do comentário (pacote de 5 fatias mais a resposta) é a do código;
3. as linhas da ponte no CSV falam do ``0x36`` (398 B, 403 no ar), o relatório que o produto
   escreve, e não do ``0x35`` aposentado.

``docs/process/`` é ignorado pelo git: num clone limpo ele não existe e a varredura anda só pelo
que existe. O que o git carrega (``src/``, ``mockup/``, ``docs/data``) é varrido sempre.
"""

from __future__ import annotations

import csv
import io
import os
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

PADRAO = re.compile(r"(?<![\d.])(?:232 *%|928,4(?!\d))")

SUFIXOS_DE_TEXTO = frozenset({
    ".md", ".html", ".csv", ".py", ".txt", ".json", ".js", ".sh", ".toml", ".yaml", ".yml",
    ".css", ".svg", ".rs",
})

PASTAS_QUE_NAO_SE_ANDA = frozenset(
    {"__pycache__", ".git", ".venv", "node_modules", ".pytest_cache"})

ISENCOES_DE_ARQUIVO: dict[str, str] = {
    "docs/process/sprints/": (
        "a sprint escreve o defeito que cura e cita o número que manda tirar; o texto dela é "
        "a história da troca, não uma afirmação"),
    "docs/process/estudos/2026-09-23-a-leva-do-radio-os-relatos/": (
        "relato bruto da leva de 23/09, guardado como foi escrito"),
    "docs/process/estudos/2026-09-23-radio/criticos.md": (
        "citação literal de um crítico de 23/09 sobre a mordida circular do P3"),
    "docs/process/estudos/2026-09-23-radio/mapa-do-radio-aprovado-23-09.html": (
        "cópia do desenho que ela aprovou em 23/09, intocável"),
}

ISENCOES_DE_LINHA: dict[str, tuple[str, str]] = {}

ESTE_ARQUIVO = "tests/unit/test_o_232_nao_volta_aos_textos.py"


def _isento_por_arquivo(rel: str) -> bool:
    if rel == ESTE_ARQUIVO:
        return True
    return any(rel == chave or (chave.endswith("/") and rel.startswith(chave))
               for chave in ISENCOES_DE_ARQUIVO)


def varrer(raiz: Path) -> list[str]:
    """Cada ocorrência fora das isenções, como ``arquivo:linha: trecho``."""
    achados: list[str] = []
    for topo in ("docs", "src", "mockup"):
        base = raiz / topo
        if not base.is_dir():
            continue
        for pasta, subpastas, arquivos in os.walk(base):
            subpastas[:] = sorted(
                s for s in subpastas
                if s not in PASTAS_QUE_NAO_SE_ANDA
                and not _isento_por_arquivo(
                    (Path(pasta) / s).relative_to(raiz).as_posix() + "/"))
            for nome in sorted(arquivos):
                caminho = Path(pasta) / nome
                rel = caminho.relative_to(raiz).as_posix()
                if caminho.suffix not in SUFIXOS_DE_TEXTO or _isento_por_arquivo(rel):
                    continue
                trecho_isento = ISENCOES_DE_LINHA.get(rel, ("", ""))[0]
                texto = caminho.read_text(encoding="utf-8", errors="ignore")
                for n, linha in enumerate(texto.splitlines(), 1):
                    if PADRAO.search(linha) and not (trecho_isento and trecho_isento in linha):
                        achados.append(f"{rel}:{n}: {linha.strip()[:100]}")
    return achados


def test_nenhum_texto_vivo_diz_232_por_cento_nem_928_virgula_4() -> None:
    achados = varrer(RAIZ)
    assert not achados, (
        "o número que saiu voltou: a entrada é elástica e a ponte tira dela; o número por "
        "controle é Hz = (C_eff - custo das pontes) / 2 / n, com o custo a medir "
        "(A-PONTE-SE-CONTA-EM-FATIAS-NO-AR-01):\n  " + "\n  ".join(achados))


def test_a_regua_morde_o_numero_plantado_e_respeita_as_isencoes(tmp_path: Path) -> None:
    """A régua não é cega: planta o número e ela o acha; planta na isenção e ela cala."""
    pasta = tmp_path / "docs" / "process" / "estudos" / "2026-10-08-o-tato-vivo"
    pasta.mkdir(parents=True)
    estudo = pasta / "ESTUDO.md"
    estudo.write_text("a antena já passa (232%, memória)\n", encoding="utf-8")
    assert [a.split(":")[0] for a in varrer(tmp_path)] == [
        "docs/process/estudos/2026-10-08-o-tato-vivo/ESTUDO.md"]
    estudo.write_text("um controle custa 928,4 fatias\n", encoding="utf-8")
    assert len(varrer(tmp_path)) == 1
    estudo.write_text("sem o número\n", encoding="utf-8")
    assert varrer(tmp_path) == []

    bruto = tmp_path / "docs/process/estudos/2026-09-23-radio/criticos.md"
    bruto.parent.mkdir(parents=True)
    bruto.write_text("«928 fatias, 232%»\n", encoding="utf-8")
    assert varrer(tmp_path) == [], "o arquivo bruto isento tem de calar"

    mockup = tmp_path / "mockup" / "mapa-do-radio.html"
    mockup.parent.mkdir()
    mockup.write_text(
        "/* «PONTES N DE 2» no lugar do «232%». */\nconst x = '232 %';\n", encoding="utf-8")
    achados = varrer(tmp_path)
    assert [a.split(":")[1] for a in achados] == ["1", "2"], (
        "o comentário que negava o número saiu com o código sem comentário: nenhuma linha é isenta")


def test_a_regua_nao_le_o_numero_dentro_de_outro_numero(tmp_path: Path) -> None:
    """O CSV de medida bruta tem ``5.34928,4957…``: dois campos, e nenhum é o 928,4."""
    medida = tmp_path / "docs" / "process" / "estudos" / "medidas" / "JOGO.csv"
    medida.parent.mkdir(parents=True)
    medida.write_text("60.17,16.61,0,66,0,5.34928,49577862239\n1232%,7\n", encoding="utf-8")
    assert varrer(tmp_path) == []
    medida.write_text("custo,928,4\nuso,232%\n", encoding="utf-8")
    assert len(varrer(tmp_path)) == 2, "o número inteiro, mesmo num CSV, ainda reprova"

def test_nenhuma_isencao_esta_morta() -> None:
    """Isenção cujo arquivo já não tem o número é régua frouxa: sai da lista."""
    mortas: list[str] = []
    for chave in ISENCOES_DE_ARQUIVO:
        alvo = RAIZ / chave
        if not alvo.exists():
            continue
        arquivos = ([p for p in alvo.rglob("*") if p.is_file()] if alvo.is_dir() else [alvo])
        if not any(PADRAO.search(a.read_text(encoding="utf-8", errors="ignore"))
                   for a in arquivos if a.suffix in SUFIXOS_DE_TEXTO):
            mortas.append(chave)
    for rel, (trecho, _razao) in ISENCOES_DE_LINHA.items():
        texto = (RAIZ / rel).read_text(encoding="utf-8")
        if not any(trecho in linha and PADRAO.search(linha) for linha in texto.splitlines()):
            mortas.append(rel)
    assert not mortas, f"isenção sem o número que isenta: {mortas}"


MOCKUP = RAIZ / "mockup" / "mapa-do-radio.html"
ORCAMENTO = RAIZ / "docs" / "data" / "orcamento-de-ar.csv"


def _intervalo_da_caixa_no_csv() -> tuple[int, int]:
    with ORCAMENTO.open(encoding="utf-8", newline="") as arquivo:
        linha = next(
            r for r in csv.DictReader(arquivo) if r["consumidor"].startswith("caixa ou fone"))
    pares = re.findall(r"(\d+) a (\d+) fatias\b", linha["fonte"])
    assert pares, f"o CSV não diz «N a M fatias» na linha da caixa: {linha['fonte']!r}"
    baixo, alto = pares[-1]
    return int(baixo), int(alto)


def _dados_do_mockup() -> list[list[str]]:
    texto = MOCKUP.read_text(encoding="utf-8")
    achado = re.search(r'<script type="text/csv" id="dados">\n(.*?)</script>', texto, re.S)
    assert achado, "o mockup do rádio perdeu o bloco de dados"
    return list(csv.reader(io.StringIO(achado.group(1))))


def test_a_caixa_e_o_fone_do_mockup_caem_no_intervalo_do_csv() -> None:
    baixo, alto = _intervalo_da_caixa_no_csv()
    linhas = [r for r in _dados_do_mockup() if r[:1] == ["aparelho"] and r[3] in {"caixa", "fone"}]
    assert {r[3] for r in linhas} == {"caixa", "fone"}, "o mockup perdeu a caixa ou o fone"
    for r in linhas:
        fatias = float(r[6])
        assert baixo <= fatias <= alto, (
            f"{r[1]}: o mockup diz {fatias:g} fatias e o CSV do orçamento diz {baixo} a {alto}")


def test_a_conta_da_caixa_no_mockup_e_a_do_pacote_de_cinco_fatias() -> None:
    texto = MOCKUP.read_text(encoding="utf-8")
    assert "2-DH5 (3 fatias)" not in texto, "o 2-DH5 ocupa cinco fatias, não três"
    divisor = re.search(r"const FATIAS_DO_PACOTE_A2DP = (\d+);", texto)
    assert divisor and int(divisor.group(1)) == 5 + 1, (
        "a linha da caixa divide as fatias pelo pacote de 5 mais a resposta")
    linhas = [r for r in _dados_do_mockup() if r[:1] == ["aparelho"] and r[3] in {"caixa", "fone"}]
    for r in linhas:
        assert round(float(r[6]) / int(divisor.group(1))) == 61, (
            "61 pacotes por segundo: SBC a 328 kbit/s, ~672 B por pacote")


def test_o_csv_da_ponte_fala_do_0x36_e_nao_do_0x35_aposentado() -> None:
    from hefesto_dualsense4unix.integrations import alto_falante_bt as bomba

    texto = ORCAMENTO.read_text(encoding="utf-8")
    assert "0x35" not in texto, "o produto escreve só o 0x36 desde 03/10/2026"
    tamanho = bomba.TAMANHO_DO_DEGRAU[bomba.DEGRAU_COMBINADO]
    assert (bomba.DEGRAU_COMBINADO, tamanho) == (0x36, 398)
    with ORCAMENTO.open(encoding="utf-8", newline="") as arquivo:
        k = next(r for r in csv.DictReader(arquivo)
                 if r["consumidor"].startswith("fatias por relatório"))
    assert f"{tamanho} B" in k["fonte"] and f"{tamanho + 5} no ar" in k["fonte"], (
        "a linha do k diz o tamanho do 0x36 e o que vai no ar (+5 de L2CAP e HIDP)")
    assert "2-DH5 (5 fatias)" in k["fonte"], "o 2-DH5 ocupa cinco fatias, aqui como no mockup"
