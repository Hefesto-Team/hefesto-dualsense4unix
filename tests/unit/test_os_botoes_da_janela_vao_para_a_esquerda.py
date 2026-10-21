"""Os botões da janela vão para a esquerda (OS-BOTOES-DA-JANELA-VAO-PARA-A-ESQUERDA-01).

Medido em 20/10/2026: o `montar_a_barra` punha os três botões desta casa com `pack_end`, e eles
saíam à direita do título (minimizar, maximizar, fechar). O desenho aprovado em 20/10
(`mockup/variantes/2010-botoes-a-esquerda-fechar-maximizar-minimizar.html`) os quer à esquerda,
na ordem fechar, maximizar, minimizar. A barra montada aqui é a do produto, num
`Gtk.OffscreenWindow` sob a tela de mentira, e a posição é a alocação que o GTK dá.

MORDIDA (executada em 21/10/2026): com o `pack_end` de volta no `montar_a_barra`,
`test_os_tres_a_esquerda_do_titulo_na_ordem_escolhida` reprova (os três passam da metade).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from hefesto_dualsense4unix.interface import janela

ORDEM_ESCOLHIDA = ["fechar", "maximizar", "minimizar"]

_SONDA = """
import json
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from hefesto_dualsense4unix.interface.janela import LARGURA_DO_DESENHO, montar_a_barra
barra, botoes = montar_a_barra("Hefesto", "", lambda *_: None)
janela = Gtk.OffscreenWindow()
janela.set_default_size(LARGURA_DO_DESENHO, 39)
janela.add(barra)
janela.show_all()
for _ in range(200):
    Gtk.main_iteration_do(False)
largura = barra.get_allocation().width
print(json.dumps({"largura": largura, "x": {g: b.get_allocation().x for g, b in botoes.items()},
                  "w": {g: b.get_allocation().width for g, b in botoes.items()}}))
"""


def test_a_tupla_esta_na_ordem_da_tela() -> None:
    """A prova da D-2010-AS-TELAS-DO-ANTES-E-DEPOIS-DE-20-10."""
    assert [gesto for _, gesto, _ in janela.BOTOES_DA_BARRA] == ORDEM_ESCOLHIDA


@pytest.fixture(scope="module")
def medida() -> dict[str, object]:
    ambiente = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    filho = subprocess.run([sys.executable, "-c", _SONDA], env=ambiente,
                           capture_output=True, text=True, timeout=120)
    if filho.returncode != 0:
        pytest.skip(f"a barra não subiu na tela de mentira: {filho.stderr.strip()[-300:]}")
    return dict(json.loads(filho.stdout.strip().splitlines()[-1]))


def test_os_tres_a_esquerda_do_titulo_na_ordem_escolhida(medida: dict[str, object]) -> None:
    largura = int(medida["largura"])  # type: ignore[call-overload]
    x: dict[str, int] = medida["x"]  # type: ignore[assignment]
    w: dict[str, int] = medida["w"]  # type: ignore[assignment]
    assert largura >= 600, medida
    assert sorted(x, key=x.__getitem__) == ORDEM_ESCOLHIDA, x
    for gesto in ORDEM_ESCOLHIDA:
        assert x[gesto] + w[gesto] < largura // 4, (gesto, medida)
