"""A porta de entrada das specs parou de digitar número à mão.

`docs/data/LEIA-PRIMEIRO.md` é o caminho barato até o mapa, e ele publica um
censo: o tamanho de dez arquivos, quantas colunas o CSV tem, quantos pares
`cabo_*`/`radio_*` existem, até onde vai a docstring do portão. Tudo isso era
DIGITADO À MÃO, com um carimbo de data que dizia *"este carimbo é a data da
última medição"* — e o próprio arquivo já confessava a cura de raiz que ninguém
tinha feito.

O preço, medido em 26/08/2026, quatro dias depois do carimbo de 22/08: **sete
dos dez tamanhos estavam errados** (o mapa em 700.602 contra 696.546
publicados; o portão em 102.818 contra 85.063; o METODO em 63.404 contra
60.445), as colunas diziam 47 contra as 49 que o `csv.reader` devolve, os pares
diziam 13 contra 14, `177 ensaios` contra 178, e o `specs.html` era listado na
raiz, de onde saiu em 25/08. Corrigir os números à mão seria pagar o mesmo
preço de novo amanhã — é literalmente o que já se fez uma vez.

A cura: cada número mora entre marcas HTML que a renderização não mostra, e
quem o mede é `check_paridade_transporte.py --leia-primeiro`. Este arquivo é a
régua que cobra o frescor — ela vive na SUÍTE, e não na lista de portões, que
tem dono único (`scripts/portoes.sh`).

PROVA DE QUE MORDE (arrancar, ver reprovar, devolver) — 26/08/2026, colada em
`docs/process/agentes/2026-08-26/LEVA-4-D.md`. Cura arrancada: as marcas do
documento desfeitas (os números de volta a literal). Reprovaram
`test_nenhum_numero_do_censo_e_literal` e
`test_o_documento_confere_com_a_medicao_de_agora`. Cura devolvida, tudo verde.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ_REAL / "scripts" / "check_paridade_transporte.py"
DOCUMENTO = RAIZ_REAL / "docs" / "data" / "LEIA-PRIMEIRO.md"

_MARCA = re.compile(r"<!--@([A-Za-z0-9:/._-]+)-->(.*?)<!--/-->")

#: Os números que a seção 2 publica fora da tabela e que também têm de ser
#: gerados. Lista fechada de propósito: uma régua que exigisse "todo número"
#: brigaria com a prosa, onde número é argumento, não censo.
CHAVES_EXIGIDAS = {
    "colunas-do-mapa",
    "colunas-em-pares",
    "pares-de-transporte",
    "linhas-do-mapa",
    "linhas-do-caderno",
    "ultima-linha-da-docstring-do-portao",
}


def _tabela_da_secao_1(texto: str) -> list[str]:
    """As linhas da tabela de arquivos, que é a que publica os dez tamanhos."""
    inicio = texto.index("\n## 1.")
    fim = texto.index("\n## 2.")
    return [
        linha
        for linha in texto[inicio:fim].splitlines()
        if linha.startswith("| `") and "---" not in linha
    ]


def _rodar(*extra: str, raiz: Path = RAIZ_REAL) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), "--leia-primeiro", *extra],
        capture_output=True,
        text=True,
        check=False,
    )


def _arvore_de_brinquedo(tmp_path: Path) -> Path:
    """Uma cópia do que o gerador lê: o documento, e todo arquivo que ele mede.

    A lista de arquivos sai das PRÓPRIAS marcas do documento — nunca de uma
    cópia à mão aqui dentro, que é o defeito que este arquivo inteiro existe
    para curar.
    """
    texto = DOCUMENTO.read_text(encoding="utf-8")
    relativos = {"docs/data/mapa-controles.csv", "docs/data/ensaios.csv"}
    relativos |= {
        chave.removeprefix("bytes:") for chave, _ in _MARCA.findall(texto) if ":" in chave
    }
    for relativo in relativos:
        destino = tmp_path / relativo
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(RAIZ_REAL / relativo, destino)

    documento = tmp_path / "docs" / "data" / "LEIA-PRIMEIRO.md"
    documento.parent.mkdir(parents=True, exist_ok=True)
    documento.write_text(texto, encoding="utf-8")
    return documento


def _troca_a_mao(documento: Path, chave: str, valor: str) -> None:
    """Digita um número à mão dentro da marca — a cura arrancada, em miniatura."""
    texto = documento.read_text(encoding="utf-8")
    abre = f"<!--@{chave}-->"
    assert abre in texto, (
        f"o documento não tem mais a marca `{chave}`: o número voltou a ser "
        "literal digitado à mão, que é a doença que esta régua cura"
    )
    inicio = texto.index(abre) + len(abre)
    fim = texto.index("<!--/-->", inicio)
    documento.write_text(texto[:inicio] + valor + texto[fim:], encoding="utf-8")


# --------------------------------------------------------------------------
# A régua da ordem
# --------------------------------------------------------------------------
def test_nenhum_numero_do_censo_e_literal() -> None:
    """Os dez tamanhos, as colunas e os pares vêm de geração, não de literal.

    Reprova NOMEANDO: se alguém acrescentar uma linha à tabela com o tamanho
    digitado, a mensagem diz qual linha, e se alguém tirar uma marca da seção
    2, a mensagem diz qual chave sumiu.
    """
    texto = DOCUMENTO.read_text(encoding="utf-8")

    sem_marca = []
    for linha in _tabela_da_secao_1(texto):
        celulas = [pedaco.strip() for pedaco in linha.strip().strip("|").split("|")]
        caminho = celulas[0].strip("`")
        esperada = f"<!--@bytes:{caminho}-->"
        if len(celulas) < 2 or esperada not in celulas[1]:
            sem_marca.append(f"{caminho}: o tamanho está digitado à mão ({celulas[1]!r})")
    assert not sem_marca, (
        "cada linha da tabela de arquivos tem de tirar o tamanho da medição:\n"
        + "\n".join(sem_marca)
    )
    assert len(sem_marca) == 0 and len(_tabela_da_secao_1(texto)) >= 10

    presentes = {chave for chave, _ in _MARCA.findall(texto)}
    faltando = sorted(CHAVES_EXIGIDAS - presentes)
    assert not faltando, f"números do censo digitados à mão (marca ausente): {faltando}"


def test_o_documento_confere_com_a_medicao_de_agora() -> None:
    """O portão do próprio documento: publicado == medido, hoje."""
    processo = _rodar()
    assert processo.returncode == 0, processo.stdout + processo.stderr


# --------------------------------------------------------------------------
# A mordida da régua: ela tem de saber RECUSAR
# --------------------------------------------------------------------------
def test_numero_trocado_a_mao_reprova_nomeando(tmp_path: Path) -> None:
    """As colunas de volta às 47 que o documento publicava — e ele grita."""
    documento = _arvore_de_brinquedo(tmp_path)
    _troca_a_mao(documento, "colunas-do-mapa", "47")
    processo = _rodar(raiz=tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "numero-caduco" in processo.stdout
    assert "colunas-do-mapa" in processo.stdout
    assert "47" in processo.stdout


def test_tamanho_trocado_a_mao_reprova_nomeando(tmp_path: Path) -> None:
    documento = _arvore_de_brinquedo(tmp_path)
    _troca_a_mao(documento, "bytes:docs/data/ensaios.csv", "149.862")
    processo = _rodar(raiz=tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "bytes:docs/data/ensaios.csv" in processo.stdout
    assert "149.862" in processo.stdout


def test_caminho_que_nao_existe_reprova(tmp_path: Path) -> None:
    """Endereço podre na tabela: o documento manda abrir o que ninguém abre."""
    documento = _arvore_de_brinquedo(tmp_path)
    documento.write_text(
        documento.read_text(encoding="utf-8")
        + "\n| `specs.html` | <!--@bytes:specs.html-->1<!--/--> | mudou de lugar |\n",
        encoding="utf-8",
    )
    processo = _rodar(raiz=tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "chave-de-geracao" in processo.stdout
    assert "não existe nesta árvore" in processo.stdout


def test_escrever_conserta_e_diz_o_que_mudou(tmp_path: Path) -> None:
    documento = _arvore_de_brinquedo(tmp_path)
    _troca_a_mao(documento, "linhas-do-caderno", "1")

    escrita = _rodar("--escrever", raiz=tmp_path)
    assert escrita.returncode == 0, escrita.stdout
    assert "atualizado `linhas-do-caderno`" in escrita.stdout
    assert _rodar(raiz=tmp_path).returncode == 0


def test_documento_sem_marca_nenhuma_reprova(tmp_path: Path) -> None:
    """A régua tem de gritar quando a cura é ARRANCADA, não só quando caduca."""
    documento = _arvore_de_brinquedo(tmp_path)
    documento.write_text(
        _MARCA.sub(lambda casamento: casamento.group(2), documento.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    processo = _rodar(raiz=tmp_path)
    assert processo.returncode == 1, processo.stdout
    assert "literal digitado" in processo.stdout
