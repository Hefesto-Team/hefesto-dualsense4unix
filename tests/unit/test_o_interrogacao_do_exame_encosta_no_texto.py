"""O `?` de cada achado do Check-up encosta na última palavra da frase."""

from __future__ import annotations

import pathlib
import re

import pytest

PAGINA = (
    pathlib.Path(__file__).resolve().parents[2]
    / "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html"
)

DENTRO = re.compile(
    r'<span class="dito">\s*<span class="txt"[^>]*>.*?</span>\s*'
    r'<span class="ajuda">',
    re.S,
)


def linhas_do_exame() -> list[str]:
    if not PAGINA.exists():  # pragma: no cover — árvore sem a página publicada
        pytest.skip(f"{PAGINA.name} não está publicada nesta árvore")
    return re.findall(r'<div class="exame".*?</div>', PAGINA.read_text(encoding="utf-8"), re.S)


def test_ha_linhas_de_exame_para_medir() -> None:
    """Conjunto vazio não é verde — é a régua medindo o nada."""
    assert linhas_do_exame(), "nenhuma linha do exame na página publicada"


def test_toda_linha_traz_o_interrogacao_colado_ao_texto() -> None:
    """Em TODAS elas o `?` mora no mesmo invólucro do texto, depois dele."""
    soltas = [linha for linha in linhas_do_exame() if not DENTRO.search(linha)]
    assert not soltas, (
        f"{len(soltas)} linha(s) do exame com o `?` fora do `.dito` — ele volta a "
        "seguir a caixa do texto, e não a última palavra"
    )


def test_o_ignorar_encosta_no_interrogacao() -> None:
    """O `⊘` segue o `?`, e o `?` continua colado na última palavra."""
    raiz = pathlib.Path(__file__).resolve().parents[2]
    fonte = (raiz / "src/hefesto_dualsense4unix/interface/aba08.py").read_text(encoding="utf-8")
    for nome, texto in (("aba08.py", fonte), (PAGINA.name, PAGINA.read_text(encoding="utf-8"))):
        assert ".exame .ignora{margin-left:0}" in texto, (
            f"{nome}: o `⊘` voltou para a ponta da coluna — *«aproxima o botão de "
            "ignora pra deixar ele mais a esquerda»* é pedido dela, de 26/09")
        assert ".exame .ignora{margin-left:auto}" not in texto, nome
    assert ".exame .dito .ajuda{display:inline-block" in fonte, (
        "sem `inline-block` o `?` é um <span> de 17px que o navegador ignora"
    )
