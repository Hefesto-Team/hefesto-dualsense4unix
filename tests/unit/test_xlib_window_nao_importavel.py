"""CODIGO-MORTO-01: a lápide do `xlib_window` tem de MORDER quem importar.

O módulo `integrations/xlib_window.py` guardava 111 linhas que nenhum código de
produção importava e que liam o `_NET_ACTIVE_WINDOW` SEM gate de foco — o
defeito que o UX-02/FOCO-01 curaram no backend vivo. Enquanto ele importava
limpo, era armadilha carregada: bastava alguém achar e usar.

Estes testes fixam as duas metades da cura:
  1. importar levanta `ImportError` (toda vez, não só na primeira);
  2. a mensagem aponta o substituto (`window_detect.build_window_reader`);
  3. a mecânica da leitura cega saiu do arquivo (nem `XlibClient`, nem
     `intern_atom`/`get_full_property` sobraram como código).
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_MODULO = "hefesto_dualsense4unix.integrations.xlib_window"


def _importar() -> None:
    """Tenta importar o módulo com o cache do interpretador limpo."""
    sys.modules.pop(_MODULO, None)
    importlib.import_module(_MODULO)


def _fonte_do_modulo() -> str:
    import hefesto_dualsense4unix.integrations as integrations

    caminho = Path(str(integrations.__file__)).parent / "xlib_window.py"
    return caminho.read_text(encoding="utf-8")


def test_importar_levanta_import_error():
    with pytest.raises(ImportError):
        _importar()


def test_mensagem_aponta_o_substituto():
    with pytest.raises(ImportError) as exc:
        _importar()
    msg = str(exc.value)
    assert "window_detect" in msg
    assert "build_window_reader" in msg


def test_import_falha_de_novo_na_segunda_tentativa():
    """Import que falha não pode deixar meio-módulo em `sys.modules`."""
    for _ in range(2):
        with pytest.raises(ImportError):
            _importar()
    assert _MODULO not in sys.modules


def test_a_leitura_cega_saiu_do_arquivo():
    """Nenhuma cópia viva do defeito: só a lápide sobrou."""
    fonte = _fonte_do_modulo()
    assert "class XlibClient" not in fonte
    assert "intern_atom" not in fonte
    assert "get_full_property" not in fonte
    assert "raise ImportError" in fonte


def test_nenhum_modulo_de_producao_importa_o_xlib_window():
    """Se algum módulo de src/ importar a lápide, o pacote quebra no import."""
    import hefesto_dualsense4unix

    raiz = Path(str(hefesto_dualsense4unix.__file__)).parent
    culpados: list[str] = []
    for arquivo in sorted(raiz.rglob("*.py")):
        if arquivo.name == "xlib_window.py":
            continue
        texto = arquivo.read_text(encoding="utf-8")
        for numero, linha in enumerate(texto.splitlines(), start=1):
            despido = linha.strip()
            if despido.startswith("#"):
                continue
            if "xlib_window" not in despido:
                continue
            if despido.startswith(("import ", "from ")) or " import " in despido:
                culpados.append(f"{arquivo.name}:{numero}: {despido}")
    assert culpados == []
