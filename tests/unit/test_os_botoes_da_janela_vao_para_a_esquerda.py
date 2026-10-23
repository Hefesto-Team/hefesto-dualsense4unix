"""Os botões da janela vão para a esquerda (OS-BOTOES-DA-JANELA-VAO-PARA-A-ESQUERDA-01).

Medido em 20/10/2026: o `montar_a_barra` punha os três botões desta casa com `pack_end`, e eles
saíam à direita do título (minimizar, maximizar, fechar). O desenho aprovado em 20/10 os quer
à esquerda, na ordem fechar, maximizar, minimizar. A barra montada aqui é a do produto, num
`Gtk.OffscreenWindow` sob a tela de mentira, e a posição é a alocação que o GTK dá.

Desde 22/10/2026 (O-TEMA-DA-EXTENSAO-ESCOLHE-O-LADO-DOS-BOTOES-DA-JANELA-01) a esquerda é
escolha da extensão de tema: sem ela o produto segue o lado do sistema (no COSMIC, a direita;
`test_o_tema_da_extensao_escolhe_o_lado_dos_botoes.py`). Aqui a sonda liga uma extensão de tema
que diz `botoes: esquerda`, num `XDG_*` de mentira, e monta a barra no lado que a janela escolhe.

MORDIDA (executada em 21/10/2026): com o `pack_end` de volta no `montar_a_barra`,
`test_os_tres_a_esquerda_do_titulo_na_ordem_escolhida` reprova (os três passam da metade).
MORDIDA (22/10/2026): com o `botoes=` do `tema_da_casa` arrancado, a sonda monta a barra no lado do
sistema (a direita) e o mesmo teste reprova.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa a `interface.janela`, que carrega o GTK")

from hefesto_dualsense4unix.interface import janela

ORDEM_ESCOLHIDA = ["fechar", "maximizar", "minimizar"]

_SONDA = """
import json
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from hefesto_dualsense4unix.interface.janela import (
    LARGURA_DO_DESENHO, lado_dos_botoes, montar_a_barra)
from hefesto_dualsense4unix.mods import instalador
lg = instalador.Lugares.do_xdg()
pasta = lg.codigo / "so-lado"
pasta.mkdir(parents=True)
(pasta / "hefesto-mod.json").write_text(json.dumps({
    "id": "so-lado", "nome": "So lado", "api": ">=2,<3", "licenca": "MIT",
    "versao": "1.0.0",  # (noqa-acento): chave
    "tipos": ["tema"], "tema": {"botoes": "esquerda"},
    "permissoes": ["tema"]}), encoding="utf-8")  # (noqa-acento): chave
instalador.gravar_registro(lg.registro, {"so-lado": instalador.Entrada(
    id="so-lado", nome="So lado", versao="1.0.0", origem="local", endereco=str(pasta),
    permissoes_aceitas=["tema"], ligada=True, ligada_em="2026-10-22T10:00:00")})
lado = lado_dos_botoes()
barra, botoes = montar_a_barra("Hefesto", "", lambda *_: None, lado=lado)
janela = Gtk.OffscreenWindow()
janela.set_default_size(LARGURA_DO_DESENHO, 39)
janela.add(barra)
janela.show_all()
for _ in range(200):
    Gtk.main_iteration_do(False)
largura = barra.get_allocation().width
print(json.dumps({
    "lado": lado, "largura": largura,
    "x": {g: b.get_allocation().x for g, b in botoes.items()},
    "w": {g: b.get_allocation().width for g, b in botoes.items()}}))
"""


def test_a_tupla_esta_na_ordem_da_tela() -> None:
    """A prova da D-2010-AS-TELAS-DO-ANTES-E-DEPOIS-DE-20-10: à esquerda, fechar primeiro."""
    assert [gesto for _, gesto, _ in janela.BOTOES_DA_BARRA] == ORDEM_ESCOLHIDA
    assert [gesto for _, gesto, _ in janela.ORDEM_DA_DIREITA] == ORDEM_ESCOLHIDA[::-1]


@pytest.fixture(scope="module")
def medida(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    raiz = tmp_path_factory.mktemp("esquerda")
    ambiente = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", XDG_CURRENT_DESKTOP="COSMIC",
                    XDG_CONFIG_HOME=str(raiz / "config"), XDG_DATA_HOME=str(raiz / "dados"),
                    XDG_STATE_HOME=str(raiz / "estado"))
    filho = subprocess.run([sys.executable, "-c", _SONDA], env=ambiente,
                           capture_output=True, text=True, timeout=120)
    if filho.returncode != 0:
        # só a falta de tela pula; qualquer outro erro da sonda é vermelho, e não silêncio
        if "display" not in filho.stderr.lower():
            pytest.fail(f"a sonda quebrou: {filho.stderr.strip()[-600:]}")
        pytest.skip(f"a barra não subiu na tela de mentira: {filho.stderr.strip()[-300:]}")
    return dict(json.loads(filho.stdout.strip().splitlines()[-1]))


def test_os_tres_a_esquerda_do_titulo_na_ordem_escolhida(medida: dict[str, object]) -> None:
    assert medida["lado"] == "esquerda", medida
    largura = int(medida["largura"])  # type: ignore[call-overload]
    x: dict[str, int] = medida["x"]  # type: ignore[assignment]
    w: dict[str, int] = medida["w"]  # type: ignore[assignment]
    assert largura >= 600, medida
    assert sorted(x, key=x.__getitem__) == ORDEM_ESCOLHIDA, x
    for gesto in ORDEM_ESCOLHIDA:
        assert x[gesto] + w[gesto] < largura // 4, (gesto, medida)
