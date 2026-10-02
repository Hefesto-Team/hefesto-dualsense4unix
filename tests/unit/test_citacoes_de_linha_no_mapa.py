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
