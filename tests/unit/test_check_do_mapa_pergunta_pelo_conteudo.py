"""O `--check` do mapa pergunta pelo CONTEÚDO — ou este arquivo reprova.

O defeito, medido na árvore de verdade em 12/08/2026: o `specs.html` publicado
divergia do `docs/data/ensaios.csv` do MESMO commit em quatorze linhas — a
página mostrava os dezesseis dias de isolamento da lightbar como "os ensaios se
contradizem" enquanto o caderno já tinha o culpado isolado — e
`python3 scripts/gerar-mapa.py --check` respondia `specs.html: atualizado`.

Verde falso por duas causas, as duas no `--check`:

1. a lista de fontes era `[CSV, *SVGS, este arquivo]` e NÃO trazia o
   `docs/data/ensaios.csv`, que alimenta a página desde o caderno de
   eliminação: editar o caderno nunca fazia o portão reclamar;
2. a comparação era de MTIME, e mtime não responde à pergunta do portão. O
   `specs.html` publicado tinha o selo de 11/08 23:04 e o commit que o publica
   é de 12/08 00:38 — qualquer ferramenta que TOQUE o arquivo depois da
   geração (o `--fix` do `scripts/validar-acentuacao.py` reescreve arquivos) o
   deixa "mais novo" que as fontes, e o portão passa. No CI é pior: o
   `actions/checkout` escreve em ordem de caminho e o `specs.html` da raiz
   nasce sempre depois de `docs/` e de `scripts/`.

Cada teste daqui roda o CLI de verdade contra uma árvore de brinquedo com a
mesma FORMA da real (os mesmos desenhos, o mesmo cabeçalho de CSV, um bloco de
três linhas). Árvore de brinquedo e não a de verdade por um motivo: a de
verdade tem hoje o `specs.html` desatualizado que originou tudo isto, e um
teste que dependesse dela mediria a hora da última regeração, não o portão.

PROVA DE QUE MORDE (12/08/2026) — em `scripts/gerar-mapa.py`, trocado o corpo
do `--check` pela comparação de mtime que havia antes
(`velhos = [f for f in [CSV, *SVGS.values(), Path(__file__)] if
f.stat().st_mtime > SAIDA.stat().st_mtime]`): caíram os três testes que cobram
o conteúdo — `test_mexer_no_caderno_de_ensaios_faz_o_check_reprovar`,
`test_mexer_no_csv_do_mapa_faz_o_check_reprovar` e
`test_pagina_divergente_com_mtime_mais_novo_e_acusada` —, todos com
`saiu 0, dizendo 'specs.html: atualizado'`. Cura devolvida, os seis verdes.
"""
from __future__ import annotations

import csv
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
GERADOR = RAIZ / "scripts" / "gerar-mapa.py"

#: Um bloco inteiro do mapa: a mesma chave nos três controles. Menos que isto
#: geraria uma página que o gerador nunca produz de verdade.
LINHAS_DO_BRINQUEDO = 3


@pytest.fixture
def arvore(tmp_path: Path) -> Path:
    """Uma árvore de brinquedo, já com o `specs.html` recém-gerado nela.

    Os desenhos são os de verdade (copiados) porque é deles que vem o espaço no
    fim da linha dentro dos `<style>` — a armadilha que um comparador ingênuo
    não sobrevive. Os dois CSV são recortes dos de verdade: cabeçalho real,
    poucas linhas.
    """
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs" / "data").mkdir(parents=True)
    (tmp_path / "assets" / "control-svg").mkdir(parents=True)

    for script in ("gerar-mapa.py", "eliminacao.py"):
        shutil.copy(RAIZ / "scripts" / script, tmp_path / "scripts" / script)
    for desenho in (RAIZ / "assets" / "control-svg").glob("*.svg"):
        shutil.copy(desenho, tmp_path / "assets" / "control-svg" / desenho.name)

    original = (RAIZ / "docs" / "data" / "mapa-controles.csv").read_text(encoding="utf-8")
    cabecalho, *linhas = original.splitlines(keepends=True)
    (tmp_path / "docs" / "data" / "mapa-controles.csv").write_text(
        cabecalho + "".join(linhas[:LINHAS_DO_BRINQUEDO]), encoding="utf-8")

    caderno = (RAIZ / "docs" / "data" / "ensaios.csv").read_text(encoding="utf-8")
    (tmp_path / "docs" / "data" / "ensaios.csv").write_text(
        caderno.splitlines(keepends=True)[0], encoding="utf-8")

    gera(tmp_path)
    return tmp_path


def roda(arvore: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(arvore / "scripts" / "gerar-mapa.py"), *args],
        capture_output=True, text=True, cwd=arvore, check=False)


def gera(arvore: Path) -> None:
    saida = roda(arvore)
    assert saida.returncode == 0, saida.stderr


def confere(arvore: Path) -> subprocess.CompletedProcess:
    return roda(arvore, "--check")


def pagina(arvore: Path) -> Path:
    return arvore / "specs.html"


def envelhece_as_fontes(arvore: Path) -> None:
    """Deixa o `specs.html` mais NOVO que tudo — o verde falso do mtime.

    É o estado em que o portão antigo passava sempre, e é o estado em que a
    árvore de verdade estava: página publicada mais nova que as fontes, e
    divergente delas.
    """
    ontem = time.time() - 86400
    for fonte in list(arvore.rglob("*.csv")) + list(arvore.rglob("*.svg")):
        os.utime(fonte, (ontem, ontem))
    agora = time.time()
    os.utime(pagina(arvore), (agora, agora))


def um_ensaio_novo(arvore: Path) -> None:
    """Acrescenta ao caderno um ensaio da primeira linha do mapa.

    Um ensaio só já muda a página: o lado sai de `nunca-investigado` para
    `inconclusivo`, e o rodapé conta uma linha ensaiada a mais.
    """
    mapa = arvore / "docs" / "data" / "mapa-controles.csv"
    with open(mapa, encoding="utf-8", newline="") as fh:
        primeira = next(csv.DictReader(fh))
    caderno = arvore / "docs" / "data" / "ensaios.csv"
    with open(caderno, encoding="utf-8", newline="") as fh:
        colunas = next(csv.reader(fh))
    with open(caderno, "a", encoding="utf-8", newline="") as fh:
        csv.DictWriter(fh, colunas).writerow({
            "id": "ensaio-de-teste-1",
            "linha_id": primeira["id"],
            "transporte": "radio",
            "quando": "2026-08-12T10:00:00",
            "suspeito": "o suspeito que este teste levanta",
            "presente": "sim",
            "resultado": "não obedece",
        })


def test_a_pagina_recem_gerada_passa_no_check(arvore: Path) -> None:
    """O controle. Sem ele, os outros cinco poderiam estar reprovando por nada.

    É aqui que a armadilha do espaço no fim da linha apareceria: se a
    comparação fosse byte a byte, nem a página recém-escrita pelo próprio
    gerador passaria.
    """
    saida = confere(arvore)
    assert saida.returncode == 0, saida.stderr
    assert "atualizado" in saida.stdout


def test_mexer_no_caderno_de_ensaios_faz_o_check_reprovar(arvore: Path) -> None:
    """A causa 1: o `ensaios.csv` alimenta a página e ninguém o vigiava."""
    um_ensaio_novo(arvore)
    envelhece_as_fontes(arvore)   # e ainda assim tem de reprovar
    saida = confere(arvore)
    assert saida.returncode == 1, (
        "editar o caderno de ensaios não fez o `--check` reclamar — foi assim "
        f"que a lightbar ficou publicada como 'confuso'. Disse: {saida.stdout!r}")
    assert "DESATUALIZADO" in saida.stderr
    assert "docs/data/ensaios.csv" in saida.stderr, (
        "o erro não diz que o caderno de ensaios é fonte da página")


def test_mexer_no_csv_do_mapa_faz_o_check_reprovar(arvore: Path) -> None:
    """A fonte principal, pela mesma régua: conteúdo, não relógio."""
    mapa = arvore / "docs" / "data" / "mapa-controles.csv"
    mapa.write_text(mapa.read_text(encoding="utf-8").replace(
        "audio", "audio-mexido", 1), encoding="utf-8")
    envelhece_as_fontes(arvore)
    saida = confere(arvore)
    assert saida.returncode == 1, (
        f"o CSV do mapa mudou e o portão passou. Disse: {saida.stdout!r}")


def test_pagina_divergente_com_mtime_mais_novo_e_acusada(arvore: Path) -> None:
    """O CORAÇÃO: é o defeito que aconteceu de verdade, na árvore dela.

    O `specs.html` publicado era mais novo que todas as fontes — e não era a
    página que elas produzem. Trocar uma palavra do rodapé é a versão mínima
    disso: nada nas fontes mudou, o relógio diz que a página é a mais recente,
    e mesmo assim ela mente sobre o dado.
    """
    alvo = pagina(arvore)
    texto = alvo.read_text(encoding="utf-8")
    assert "rede contra regressão" in texto
    alvo.write_text(texto.replace("rede contra regressão", "outra coisa qualquer"),
                    encoding="utf-8")
    envelhece_as_fontes(arvore)

    saida = confere(arvore)
    assert saida.returncode == 1, (
        "a página publicada divergia das fontes e o portão passou porque o "
        f"mtime dela era o mais novo. Disse: {saida.stdout!r}")
    assert "outra coisa qualquer" in saida.stderr, (
        "o erro não mostra QUAL linha divergiu")


def test_o_espaco_no_fim_da_linha_nao_derruba_o_check(arvore: Path) -> None:
    """A armadilha medida: alguma ferramenta da casa apara o espaço sobrando.

    A saída do gerador tem linhas com espaço no fim dentro dos `<style>` vindos
    dos SVG, e o arquivo commitado não tem. Um portão que reprovasse por isso
    reprovaria em toda árvore limpa — e portão que reprova sempre é portão
    desligado.
    """
    alvo = pagina(arvore)
    texto = alvo.read_text(encoding="utf-8")
    aparado = "\n".join(linha.rstrip() for linha in texto.splitlines()) + "\n"
    assert aparado != texto, (
        "a página gerada não tem espaço no fim de linha nenhum — este teste "
        "perdeu o objeto e precisa de outra armadilha")
    alvo.write_text(aparado, encoding="utf-8")

    saida = confere(arvore)
    assert saida.returncode == 0, (
        f"o `--check` reprovou por espaço no fim da linha: {saida.stderr}")


def test_a_hora_da_geracao_nao_derruba_o_check(arvore: Path) -> None:
    """O selo do rodapé é a única parte da página que não vem do dado."""
    alvo = pagina(arvore)
    texto = alvo.read_text(encoding="utf-8")
    trocado, quantos = re.subn(r"gerado em \d{2}/\d{2}/\d{4} \d{2}:\d{2} a partir de",
                               "gerado em 01/01/2020 03:04 a partir de", texto)
    assert quantos == 1, "o selo do rodapé sumiu da página — este teste ficou cego"
    alvo.write_text(trocado, encoding="utf-8")

    saida = confere(arvore)
    assert saida.returncode == 0, (
        f"o `--check` voltou a comparar relógio: {saida.stderr}")


def test_o_gerador_existe_onde_os_portoes_o_chamam() -> None:
    """Portão que chama script inexistente reprova por engano."""
    assert GERADOR.is_file()


# --------------------------------------------------------------------------
# PECA-ORFA-01 (13/08/2026) — o id de desenho que sumiu do SVG
#
# A peça é o alvo que a página acende no desenho quando alguém clica na linha.
# Até 13/08 a órfã era acumulada, impressa em stderr como "aviso" e o processo
# devolvia 0 — inclusive no `--check`, que é o passo do pre-commit e do CI.
# --------------------------------------------------------------------------
def orfana_a_primeira_peca(arvore: Path) -> str:
    """Troca a `peca` da primeira linha por um id que nenhum desenho tem.

    Devolve o id inventado. Ele carrega `ERRADO` no nome de propósito: se algum
    dia um desenho ganhar essa peça, o teste morre com uma mensagem que se lê.
    """
    mapa = arvore / "docs" / "data" / "mapa-controles.csv"
    with open(mapa, encoding="utf-8", newline="") as fh:
        linhas = list(csv.reader(fh))
    coluna = linhas[0].index("peca")
    inventado = "dpad_up_ERRADO"
    for desenho in (arvore / "assets" / "control-svg").glob("*.svg"):
        assert inventado not in desenho.read_text(encoding="utf-8"), (
            f"o id {inventado!r} passou a existir em {desenho.name}: este teste "
            "perdeu o objeto e precisa de outro id inventado")
    linhas[1][coluna] = inventado
    with open(mapa, "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh, lineterminator="\n").writerows(linhas)
    return inventado


def test_peca_orfa_faz_o_check_reprovar(arvore: Path) -> None:
    """A cura: `--check` sai 1 quando o CSV cita peça que sumiu do desenho.

    MORDE? Arrancar o `return 1` do bloco `if orfas:` em `main()` faz este teste
    reprovar com `saiu 0` — que é literalmente o estado da árvore antes de
    13/08/2026. Medido: com a órfã publicada e o `return 1` fora, o `--check`
    imprimia as duas linhas de aviso em stderr e devolvia EXIT=0.
    """
    inventado = orfana_a_primeira_peca(arvore)
    # A página é regerada COM a órfã, para que sobre UMA variável só: sem isto o
    # `--check` reprovaria por `DESATUALIZADO` mesmo com a cura arrancada, e o
    # teste passaria sem medir nada. O gerador escreve a página e SÓ ENTÃO
    # reprova — é por isso que aqui se ignora o código de saída dele.
    roda(arvore)
    assert inventado in pagina(arvore).read_text(encoding="utf-8"), (
        "o gerador reprovou ANTES de escrever a página: a órfã não chegou ao "
        "specs.html, e este teste voltaria a medir a divergência de conteúdo")

    saida = confere(arvore)
    assert saida.returncode == 1, (
        "o CSV cita uma peça que nenhum desenho tem e o `--check` passou — é o "
        f"aviso em stderr que ninguém lê. Disse: {saida.stdout!r}")
    assert "PEÇA ÓRFÃ" in saida.stderr
    assert inventado in saida.stderr, "o erro não diz QUAL peça sumiu"


def test_peca_orfa_reprova_tambem_na_geracao(arvore: Path) -> None:
    """O outro modo, pela mesma razão: dado quebrado não devolve 0.

    Regerar não conserta uma órfã — ela é defeito do CSV, não da página. Um
    gerador que dissesse "952 KB, 293 linhas" e saísse 0 mandaria a pessoa
    embora achando que estava tudo certo.
    """
    orfana_a_primeira_peca(arvore)
    saida = roda(arvore)
    assert saida.returncode == 1, (
        f"o gerador devolveu 0 sobre um CSV com peça órfã: {saida.stdout!r}")
    assert "PEÇA ÓRFÃ" in saida.stderr


def test_sem_orfa_o_gerador_e_o_check_seguem_saindo_zero(arvore: Path) -> None:
    """O contrapeso. Portão que reprova sempre é portão desligado.

    Medido na árvore REAL em 13/08/2026, antes de ligar a reprovação: ZERO
    linhas órfãs nas 293 do mapa. Ligar isto custou zero reprovações.
    """
    assert roda(arvore).returncode == 0
    assert confere(arvore).returncode == 0


def test_o_mapa_real_nao_tem_peca_orfa() -> None:
    """Contra a ÁRVORE REAL, com régua independente da do gerador.

    O teste relê os ids de cada SVG por conta própria em vez de importar
    `pecas_orfas`: se a régua do gerador começar a enxergar de menos — uma
    expressão regular que perca um id, um `strip()` que suma —, os dois lados
    divergem aqui em vez de daqui a três levas. Nesta casa o instrumento já
    mentiu mais que o produto.
    """
    desenhos = {
        "dualsense": "dualsense.svg",
        "pro": "nintendo-pro.svg",
        "sn30": "8bitdo-sn30-pro.svg",
    }
    ids = {
        controle: set(re.findall(
            r'\bid="([^"]+)"',
            (RAIZ / "assets" / "control-svg" / nome).read_text(encoding="utf-8")))
        for controle, nome in desenhos.items()
    }
    with open(RAIZ / "docs" / "data" / "mapa-controles.csv", encoding="utf-8",
              newline="") as fh:
        linhas = list(csv.DictReader(fh))
    orfas = [
        (lin["controle"], lin["chave"], peca)
        for lin in linhas
        for peca in lin["peca"].split()
        if peca not in ids.get(lin["controle"], set())
    ]
    assert not orfas, (
        "o mapa cita peça(s) que sumiram dos desenhos: "
        + "; ".join(f"{c}: {ch} pede {p}" for c, ch, p in orfas))
