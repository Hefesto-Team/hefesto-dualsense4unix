"""A-SUITE-INTEIRA-CABE-EM-VINTE-MINUTOS-01: o arquivo de teste novo não entra com espera longa.

A suíte soma 64 min porque os 100 arquivos mais lentos pesam 51% dela
(``docs/data/tempos-da-suite.csv``): cada um entrou barato e engordou sem que ninguém visse. O CSV
mede o arquivo que JÁ tem linha; o arquivo que entra sem linha ainda não foi medido, e é nele que a
espera longa passa. A régua lê o ``time.sleep`` e o ``asyncio.sleep`` de número literal (só o que o
teste executa, nunca o texto de um script que ele escreve) e reprova o arquivo sem linha que passa
dos tetos:

- uma espera sozinha acima de ``TETO_DE_UMA_ESPERA`` (2 s): espere pelo evento, não pelo relógio;
- a soma das esperas acima de ``TETO_DAS_ESPERAS`` (5 s): metade do p95 do arquivo da suíte (9,5 s).

O arquivo com linha no CSV não entra aqui: o tempo dele já é medido, e o fecho o reescreve. A régua
que precisa do tempo de verdade (a regressão dos 181 s da janela, por exemplo) entra em
``EXCECOES`` com o porquê, e a exceção que já não passa do teto reprova (a lista só encolhe).
"""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
UNIT = RAIZ / "tests" / "unit"
CSV = RAIZ / "docs" / "data" / "tempos-da-suite.csv"

TETO_DE_UMA_ESPERA = 2.0
TETO_DAS_ESPERAS = 5.0

#: Arquivo sem linha no CSV que precisa de espera acima do teto, e o porquê. Hoje nenhum precisa.
EXCECOES: dict[str, str] = {}


def esperas(texto: str) -> list[float]:
    """Os segundos de cada ``time.sleep(N)`` e ``asyncio.sleep(N)`` literal que o código executa."""
    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        return []
    achadas: list[float] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call) or len(no.args) < 1:
            continue
        func = no.func
        e_sleep = (
            isinstance(func, ast.Attribute)
            and func.attr == "sleep"
            and isinstance(func.value, ast.Name)
            and func.value.id in {"time", "asyncio"}
        ) or (isinstance(func, ast.Name) and func.id == "sleep")
        arg = no.args[0]
        if (
            e_sleep
            and isinstance(arg, ast.Constant)
            and isinstance(arg.value, (int, float))
            and not isinstance(arg.value, bool)
        ):
            achadas.append(float(arg.value))
    return achadas


def com_linha_no_csv(csv: str) -> set[str]:
    """Os caminhos que o CSV de tempos já mede."""
    nomes: set[str] = set()
    for linha in csv.splitlines():
        if linha.startswith("#") or linha.startswith("arquivo,") or "," not in linha:
            continue
        nomes.add(linha.split(",", 1)[0])
    return nomes


def excessos(arquivos: dict[str, str], medidos: set[str]) -> list[str]:
    """Cada arquivo sem linha no CSV, fora de ``EXCECOES``, com espera acima dos tetos."""
    achados: list[str] = []
    for caminho, texto in sorted(arquivos.items()):
        if caminho in medidos or caminho in EXCECOES:
            continue
        lista = esperas(texto)
        if lista and max(lista) > TETO_DE_UMA_ESPERA:
            achados.append(
                f"{caminho}: uma espera de {max(lista):g} s passa de {TETO_DE_UMA_ESPERA:g} s"
            )
        elif sum(lista) > TETO_DAS_ESPERAS:
            achados.append(
                f"{caminho}: as esperas somam {sum(lista):g} s e passam de {TETO_DAS_ESPERAS:g} s"
            )
    return achados


def _arquivos_de_teste() -> dict[str, str]:
    return {
        f"tests/unit/{p.name}": p.read_text(encoding="utf-8")
        for p in sorted(UNIT.glob("test_*.py"))
    }


def test_o_arquivo_novo_sem_linha_no_csv_nao_espera_alem_do_teto() -> None:
    achados = excessos(_arquivos_de_teste(), com_linha_no_csv(CSV.read_text(encoding="utf-8")))
    assert achados == [], (
        "arquivo de teste novo com espera longa (espere pelo evento, não pelo relógio; se o tempo "
        "de verdade é o que se mede, declare em EXCECOES com o porquê):\n  " + "\n  ".join(achados)
    )


def test_as_excecoes_apontam_arquivo_que_ainda_existe_e_ainda_precisa() -> None:
    for caminho in EXCECOES:
        alvo = RAIZ / caminho
        assert alvo.is_file(), f"a exceção {caminho} aponta arquivo que saiu"
        lista = esperas(alvo.read_text(encoding="utf-8"))
        assert lista and (max(lista) > TETO_DE_UMA_ESPERA or sum(lista) > TETO_DAS_ESPERAS), (
            f"a exceção {caminho} já não passa do teto: tire da lista"
        )


class TestMorde:
    """A régua só vale se reprova a volta: cada caso devolve o defeito e vê o vermelho."""

    def test_o_sleep_longo_de_um_arquivo_sintetico_sem_linha_reprova(self) -> None:
        sintetico = "import time\n\n\ndef test_x():\n    time.sleep(30)\n"
        assert excessos({"tests/unit/test_novo.py": sintetico}, set()) != []

    def test_as_esperas_curtas_que_somam_alto_reprovam(self) -> None:
        sintetico = (
            "import time\n\n\ndef test_x():\n    for _ in range(1):\n"
            + "        time.sleep(1.5)\n" * 4
        )
        assert esperas(sintetico) == [1.5, 1.5, 1.5, 1.5]
        assert excessos({"tests/unit/test_novo.py": sintetico}, set()) != []

    def test_o_asyncio_e_o_sleep_importado_contam(self) -> None:
        assert esperas("import asyncio\nasync def f():\n    await asyncio.sleep(9)\n") == [9.0]
        assert esperas("from time import sleep\nsleep(9)\n") == [9.0]

    def test_o_arquivo_com_linha_no_csv_e_a_excecao_declarada_ficam_de_fora(self) -> None:
        sintetico = "import time\ntime.sleep(30)\n"
        caminho = "tests/unit/test_medido.py"
        assert excessos({caminho: sintetico}, {caminho}) == []
        assert com_linha_no_csv(f"# nota\narquivo,milissegundos,fonte\n{caminho},900,medido\n") == {
            caminho
        }

    def test_o_sleep_dentro_de_texto_de_script_nao_conta(self) -> None:
        sintetico = (
            'SCRIPT = "import time\\ntime.sleep(30)\\n"\n\n\ndef test_x():\n    assert SCRIPT\n'
        )
        assert esperas(sintetico) == []
        assert excessos({"tests/unit/test_novo.py": sintetico}, set()) == []

    def test_a_espera_curta_passa(self) -> None:
        curto = "import time\n\n\ndef test_x():\n    time.sleep(0.2)\n    time.sleep(1)\n"
        assert excessos({"tests/unit/test_novo.py": curto}, set()) == []
