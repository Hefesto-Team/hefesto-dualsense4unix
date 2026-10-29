"""A janela ladrilhada menor que o desenho mostra o rodapé, sem rolar.

Queixa de 29/10/2026: o rodapé (Aplicar, Salvar perfil, Importar, Exportar) sumiu de todas as
abas. O `interface.log` da sessão do usuário dizia «1172x768 ladrilhada»: o COSMIC ladrilha a janela
em 768 px de altura, e a janela GTK pedia no mínimo 1212x848 (`set_size_request`). O WebView
ficava com 809 px de vista numa janela de 768, e o compositor cortava a faixa de baixo, que é
onde mora o rodapé. A `max-height` do CSS (19/09) não alcança isso: a vista que o WebKit vê
nunca encolhia.

A cura (D-2910-O-TAMANHO-CEDE-ABAIXO-DE-100): a janela aceita encolher até `jn.PISO_DA_JANELA`,
e onde a vista é menor que o desenho o zoom cede abaixo de 100 % (`tamanho_que_cabe`).

A régua abre a janela de verdade (com barra, num Xvfb próprio, sem o `WAYLAND_DISPLAY`) sobre a
Gatilhos publicada, leva a janela a 1172x768 e mede no WebKit: a vista do GTK é a da janela,
o zoom cedeu, o documento não rola e o rodapé inteiro está dentro da vista.

MORDIDA (29/10/2026): devolver `set_size_request(LARGURA_DO_DESENHO, PISO_DA_VISTA +
ALTURA_DA_BARRA)` reprova a vista (a janela fica em 848); devolver o piso de 100 em
`tamanho_que_cabe` reprova o rodapé, que cai abaixo da vista.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import textwrap

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("O-RODAPE-SOME-NA-JANELA-LADRILHADA-01")

from hefesto_dualsense4unix.interface import janela as jn
from hefesto_dualsense4unix.interface import onde

RAIZ = pathlib.Path(__file__).resolve().parents[2]
LADRILHADA = (1172, 768)

FILHO = textwrap.dedent(
    """
    import json, pathlib, sys, time
    from gi.repository import GLib
    from hefesto_dualsense4unix.interface import janela as jn

    largura, altura = int(sys.argv[2]), int(sys.argv[3])
    tela = jn.JanelaDaAba(
        arquivo=pathlib.Path(sys.argv[1]), titulo_esperado="Hefesto",
        ao_carregar=lambda: None, oculta=False,
    )
    assert not tela.oculta, "a janela de verdade não abriu"

    def bombear(ate, prazo):
        contexto = GLib.MainContext.default()
        fim = time.monotonic() + prazo
        while not ate() and time.monotonic() < fim:
            while contexto.pending():
                contexto.iteration(False)
            time.sleep(0.004)
        return ate()

    bombear(lambda: not tela.view.is_loading() and tela.view.get_uri(), 30.0)
    bombear(lambda: False, 1.0)
    from gi.repository import GdkX11
    import subprocess
    xid = tela.janela.get_window().get_xid()
    subprocess.run(["xdotool", "windowsize", str(xid), str(largura), str(altura)], check=True)
    bombear(lambda: tela.view.get_allocated_height() == altura - jn.ALTURA_DA_BARRA, 8.0)
    bombear(lambda: False, 1.5)
    medida = {}
    tela.ponte.perguntar(
        "JSON.stringify((() => { const r = document.querySelector('.rodape');"
        " const b = r ? r.getBoundingClientRect() : null;"
        " return {vh: innerHeight, vw: innerWidth,"
        " rola: document.scrollingElement.scrollHeight - innerHeight,"
        " rodape: b ? [b.top, b.bottom, b.height] : null}; })())",
        lambda valor, erro: medida.update(js=valor, erro=repr(erro) if erro else None),
    )
    bombear(lambda: "js" in medida, 8.0)
    medida["gtk"] = [tela.view.get_allocated_width(), tela.view.get_allocated_height()]
    medida["zoom"] = tela.view.get_zoom_level()
    print("MEDIDA " + json.dumps(medida))
    print("FILHO-OK")
    """
)


@pytest.fixture(scope="module")
def medida(tmp_path_factory: pytest.TempPathFactory) -> dict:
    if shutil.which("xvfb-run") is None or shutil.which("xdotool") is None:  # pragma: no cover
        pytest.skip("sem `xvfb-run` e `xdotool` não há compositor de mentira que ladrilhe")
    lar = tmp_path_factory.mktemp("lar")
    script = lar / "filho.py"
    script.write_text(FILHO, encoding="utf-8")
    ambiente = dict(os.environ, PYTHONPATH=str(RAIZ / "src"), GDK_BACKEND="x11",
                    HOME=str(lar), XDG_CONFIG_HOME=str(lar / "config"),
                    XDG_CACHE_HOME=str(lar / "cache"), XDG_DATA_HOME=str(lar / "data"),
                    XDG_STATE_HOME=str(lar / "state"), NO_AT_BRIDGE="1")
    for nome in ("WAYLAND_DISPLAY", "DISPLAY", jn.SEM_JANELA_NA_TELA, "HEFESTO_NA_TELA"):
        ambiente.pop(nome, None)
    proc = subprocess.run(
        ["xvfb-run", "-a", "-s", "-screen 0 1920x1080x24", sys.executable, str(script),
         str(onde.PUBLICADO / "03-gatilhos.html"), str(LADRILHADA[0]), str(LADRILHADA[1])],
        env=ambiente, capture_output=True, text=True, timeout=120, check=False,
    )
    saida = proc.stdout + proc.stderr
    assert proc.returncode == 0 and "FILHO-OK" in proc.stdout, saida[-2000:]
    linha = next(x for x in proc.stdout.splitlines() if x.startswith("MEDIDA "))
    medido = json.loads(linha.removeprefix("MEDIDA "))
    assert medido["js"], medido
    medido["doc"] = json.loads(medido["js"])
    return medido


def test_a_vista_do_gtk_encolhe_com_a_janela_ladrilhada(medida: dict) -> None:
    largura, altura = LADRILHADA
    vl, va = medida["gtk"]
    assert vl <= largura and va <= altura - jn.ALTURA_DA_BARRA, (
        f"a janela segurou a vista em {medida['gtk']}: o compositor corta o que passa de "
        f"{largura}x{altura}")
    assert va < jn.PISO_DA_VISTA, medida


def test_a_janela_ladrilhada_mostra_o_rodape_sem_rolar(medida: dict) -> None:
    """Prova da D-2910-O-TAMANHO-CEDE-ABAIXO-DE-100."""
    doc = medida["doc"]
    assert medida["zoom"] < 1.0, f"o zoom não cedeu: {medida['zoom']}"
    assert doc["rola"] <= 0, f"o documento rola {doc['rola']} px: {doc}"
    assert doc["rodape"], "a página não tem rodapé"
    _topo, fundo, alto = doc["rodape"]
    assert alto > 30, doc
    assert fundo <= doc["vh"], f"o rodapé termina em {fundo}, abaixo da vista {doc['vh']}"


def test_o_piso_da_janela_e_o_do_menor_zoom() -> None:
    from hefesto_dualsense4unix.interface.folha_da_casa import MENOR_QUE_CEDE, VISTA_DO_DESENHO

    largura, altura = VISTA_DO_DESENHO
    esperado = (largura * MENOR_QUE_CEDE // 100,
                altura * MENOR_QUE_CEDE // 100 + jn.ALTURA_DA_BARRA)
    assert esperado == jn.PISO_DA_JANELA
    assert jn.PISO_DA_JANELA[1] < LADRILHADA[1]
