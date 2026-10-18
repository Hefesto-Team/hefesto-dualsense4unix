"""Os gestos que a régua das quatro respostas lê do fonte são os do registro dos pacotes.

`scripts/check_cabo_bt_perfil_controle.py` lê os `@gesto(...)` dos pacotes por `ast`, sem
importá-los (eles carregam o GTK, e o job do CI que roda a régua só tem o `pytest`). Esta régua
confere a leitura contra o outro instrumento: `interface.pacotes.GESTOS`, o registro que o
produto monta ao importar. Dois instrumentos, e o de `ast` não mede a própria saída
(AS-REGUAS-DO-RAMO-INTEIRO-E-DAS-QUATRO-RESPOSTAS-MORDEM-01).

MORDIDA: em `registro_do_fonte`, trocar `_texto(a, arquivo, src)` por
`(a.value if isinstance(a, ast.Constant) else None)` (só os literais, como uma regex): os
decoradores com página ou nome por constante somem da leitura e esta régua reprova nomeando.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import pacotes

RAIZ = Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_cabo_bt_perfil_controle.py"

_spec = importlib.util.spec_from_file_location("_regua_das_quatro_do_registro", PORTAO)
assert _spec and _spec.loader
regua = importlib.util.module_from_spec(_spec)
sys.modules["_regua_das_quatro_do_registro"] = regua
_spec.loader.exec_module(regua)

#: o pacote cujos módulos registram os gestos; o piloto registra um gesto seu (`escolher-na-fita`)
#: no mesmo dicionário quando roda no processo, e esse não é do fonte dos pacotes
_DOS_PACOTES = "hefesto_dualsense4unix.interface.pacotes"


def _do_registro() -> set[tuple[str, str]]:
    return {
        chave for chave, fn in pacotes.GESTOS.items()
        if str(getattr(fn, "__module__", "")).startswith(_DOS_PACOTES)
    }


def test_o_fonte_e_o_registro_dizem_os_mesmos_gestos() -> None:
    lidos, sem_texto = regua.registro_do_fonte()
    assert not sem_texto, "gesto(...) que a leitura do fonte não resolve:\n" + "\n".join(sem_texto)
    registro = _do_registro()
    assert len(registro) > 100, f"só {len(registro)} gestos no registro: os pacotes não carregaram"
    so_no_registro = sorted(registro - lidos)
    so_no_fonte = sorted(lidos - registro)
    assert not so_no_registro, f"gestos que o produto registra e a régua não lê: {so_no_registro}"
    assert not so_no_fonte, f"gestos que a régua lê e o produto não registra: {so_no_fonte}"


def test_os_gestos_por_constante_estao_na_leitura() -> None:
    """Os que uma regex de literais perderia: página por `PAGINA`, nome por constante de módulo
    (`GESTO_DO_APELIDO`) e por atributo de módulo importado (`desenho.ADICIONAR`)."""
    lidos, _sem_texto = regua.registro_do_fonte()
    for par in (
        ("calibrar-sensores.html", "mira-sensibilidade"),
        ("08-conexoes.html", "adaptador-renomear"),
        ("07-lancadores.html", "adicionar-lancador"),
    ):
        assert par in lidos, f"{par} não está na leitura do fonte"
        assert par in _do_registro(), f"{par} não está no registro do produto"
