"""A régua das abas vivas: elas falam com o daemon DESTA casa, e leem DESTA árvore."""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
#: já divergiram 25 KB, então a régua media  (noqa-acento: verbo medir, imperfeito) verbo medir
#: (noqa-acento: verbo medir, imperfeito — "a régua media", não "a média") verbo medir
FERRAMENTAS = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

ABAS_VIVAS = (
    "controles_vivos.py",
    "jogar_vivo.py",
    "perfis_vivos.py",
    "conexoes_vivas.py",
    "sistema_viva.py",
    "mesa_viva.py",
)

ARVORE_DELA = "/mnt/Apate/Desenvolvimento/hefesto-dualsense4unix"


def _fonte(nome: str) -> str:
    return (FERRAMENTAS / nome).read_text(encoding="utf-8")


@pytest.mark.parametrize("nome", ABAS_VIVAS)
def test_nenhuma_aba_viva_crava_a_arvore_dela(nome: str) -> None:
    """Um caminho absoluto de árvore em CÓDIGO faz a medição olhar o passado."""
    culpadas = [
        (n, linha.rstrip())
        for n, linha in enumerate(_fonte(nome).splitlines(), 1)
        if ARVORE_DELA in linha
        and not linha.lstrip().startswith(("#", "*", '"', "'"))
        and ":=" not in linha
    ]
    assert not culpadas, (
        f"{nome} crava uma árvore em código: {culpadas}. "
        "Derive do próprio arquivo — `pathlib.Path(__file__).resolve().parents[2]` "
        "—, senão rodar de uma árvore de trabalho lê a árvore do usuário."
    )


@pytest.mark.parametrize("nome", ABAS_VIVAS)
def test_toda_aba_viva_deriva_a_raiz_do_proprio_arquivo(nome: str) -> None:
    """A forma positiva da régua acima: não basta não cravar, tem de derivar."""
    fonte = _fonte(nome)
    assert "Path(__file__).resolve()" in fonte or "__file__" in fonte, (
        f"{nome} não deriva nada de `__file__`: não há como ele saber em que "
        "árvore está."
    )


def _mesa_viva_recarregado(monkeypatch: pytest.MonkeyPatch, slug: str | None = None):
    """`mesa_viva` importado do zero, opcionalmente com OUTRO slug de app."""
    from hefesto_dualsense4unix.utils import identidade

    importlib.reload(identidade)
    if slug is not None:
        from dataclasses import replace

        monkeypatch.setattr(
            identidade, "HEFESTO", replace(identidade.HEFESTO, slug=slug)
        )
    monkeypatch.syspath_prepend(str(FERRAMENTAS))
    xdg = importlib.import_module("hefesto_dualsense4unix.utils.xdg_paths")
    importlib.reload(xdg)
    mesa = importlib.import_module("mesa_viva")
    return importlib.reload(mesa)


@pytest.fixture(autouse=True)
def _devolver_os_modulos():
    """Recarregar módulo global num teste envenena o processo inteiro. Devolve."""
    yield
    from hefesto_dualsense4unix.utils import identidade, xdg_paths

    importlib.reload(identidade)
    importlib.reload(xdg_paths)
    sys.modules.pop("mesa_viva", None)


def test_o_socket_das_abas_segue_o_nome_do_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """Troque o slug em `utils/identidade.py` e o socket da aba TEM de mudar."""
    de_verdade = _mesa_viva_recarregado(monkeypatch).socket_do_daemon()
    inventado = _mesa_viva_recarregado(monkeypatch, "hefesto-de-mentira").socket_do_daemon()
    assert de_verdade != inventado, (
        "o socket da aba não mudou quando o nome do app mudou — ele está "
        f"cravado à mão em vez de sair de `xdg_paths` ({de_verdade})"
    )
    assert "hefesto-de-mentira" in inventado
    assert "hefesto-de-mentira" not in de_verdade


def test_o_socket_das_abas_e_o_mesmo_que_o_produto_usa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UM DONO SÓ. A aba não pode ter uma segunda opinião sobre onde o daemon está."""
    for slug in (None, "hefesto-de-mentira"):
        mesa = _mesa_viva_recarregado(monkeypatch, slug)
        xdg = importlib.import_module("hefesto_dualsense4unix.utils.xdg_paths")
        assert mesa.socket_do_daemon() == str(xdg.ipc_socket_path())


def test_o_socket_e_funcao_e_nao_constante() -> None:
    """Constante calculada no import congela o nome do primeiro importador."""
    fonte = _fonte("mesa_viva.py")
    assert re.search(r"^def socket_do_daemon\b", fonte, re.M), (
        "`socket_do_daemon()` sumiu — o socket voltou a ser constante?"
    )
    assert not re.search(r"^SOCKET\s*=", fonte, re.M), (
        "voltou a haver uma constante `SOCKET` no topo: ela congela o nome "
        "de quem importar primeiro."
    )


def test_a_prova_de_gesto_nao_crava_o_indice_do_card() -> None:
    """`--prova-gesto` clicava `.ctl[1]` — o SEGUNDO card, sempre."""
    codigo = "\n".join(
        linha for linha in _fonte("controles_vivos.py").splitlines()
        if not linha.lstrip().startswith("#")
    )
    assert "querySelectorAll('.ctl')[1]" not in codigo, (
        "a prova de gesto voltou a cravar o segundo card: numa mesa de um "
        "controle ela clica em `null` e passa calada."
    )
    assert "querySelectorAll('.ctl').length-1" in codigo, (
        "a prova de gesto tem de mirar um card que EXISTA em qualquer mesa."
    )


def test_o_unico_metodo_continua_sendo_leitura() -> None:
    """Esta leva não escreve, e a régua que diz isso tem de continuar de pé."""
    assert 'METODO = "daemon.state_full"' in _fonte("mesa_viva.py")
