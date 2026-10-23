"""Os cartões dos lançadores ficam do tamanho do que mostram.

Sprint OS-CARTOES-DOS-LANCADORES-NAO-ESTICAM-01.

Medido em 22/10/2026 no WebKit, no desenho da aba 07, com as extensões postas como o produto põe (o
`innerHTML` de `.ext-lista`): com `grid-auto-rows:minmax(48px,1fr)` na `.lanc-fila`, a fileira
repartia a sobra do quadro, e cada cartão tinha 134 px com duas extensões, 115 com quatro e 76
com oito (1600x855), para uma linha só. A cura: a fileira tem altura própria (42 px; 32 até 860
px de altura) e o quadro fica do tamanho da fila, com a sobra no fundo da janela, fora dele.

As duas metades da cura seguram cada uma o cartão: com o quadro sem esticar, a fileira não tem sobra
a repartir; com a fileira de altura própria, o quadro que estica não estica o cartão.

MORDIDA (executada em 22/10/2026): com a regra de antes inteira (o `1fr` e o quadro que estica),
`test_a_altura_do_cartao_nao_depende_das_extensoes` reprova nas três vistas, e a régua da fonte
também; só com o `1fr` de volta, `test_a_fileira_da_fila_nao_reparte_a_sobra` reprova; só
sem o `flex-grow:0` do quadro, `test_a_sobra_fica_fora_do_quadro` reprova nas três (o quadro estica
até o rodapé, vazio, embaixo do último cartão); sem o nome compacto da fileira de 32 px,
`test_o_que_o_cartao_mostra_cabe_nele` reprova a 1212 e a 1600 (o nome de duas linhas mede 32
para os 30 de dentro do cartão).
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

import pytest

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "mockup" / "07-lancadores.html"
#: O piso da janela, a foto da documentação e a janela mais alta (o teto da vista).
VISTAS = ((1212, 809), (1600, 855), (1900, 887))
QUANTAS = (2, 4, 8)
_NOMES = ("Azahar", "Dolphin", "Buttplug", "KytyPS5", "Lutris", "mGBA", "RetroArch", "Cemu")


def _extensoes(n: int) -> str:
    return str(exp.extensoes_html([exp.Extensao(nome.lower(), nome, f"O {nome}", "#", selo="Local",
                                                versao="1.0.0") for nome in _NOMES[:n]]))


_SONDA = r"""
import json, pathlib, sys
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from hefesto_dualsense4unix.interface.janela import PonteDaTela

PAGINA = pathlib.Path(sys.argv[1])
CASOS = json.loads(sys.stdin.read())
POR = '''(function(lista){
  document.querySelector('.ext-lista').innerHTML = lista;
  return 'ok';
})(%s)'''
MEDIR = '''(function(){
  const r = e => { const x = e.getBoundingClientRect(); return [x.top, x.bottom]; };
  const lanc = [...document.querySelectorAll('.quadro')].find(
    q => /Lançadores/.test(q.querySelector('.quadro-titulo')?.textContent || ''));
  const fila = document.querySelector('.lanc-fila');
  const m = document.querySelector('.janela > .miolo');
  const lf = [...fila.querySelectorAll('.lf')].map(e => e.getBoundingClientRect().height);
  const cabe = [...fila.querySelectorAll('.lf')].map(e => [e.scrollHeight, e.clientHeight]);
  return JSON.stringify({lf: lf, cabe: cabe,
    lanc: r(lanc), fim: r(fila.querySelector('.lf:last-child')),
    rola: [fila.scrollHeight, fila.clientHeight],
    miolo: [m.scrollHeight, m.clientHeight]});
})()'''

def esperar(caixa, segundos):
    fim = GLib.get_monotonic_time() + int(segundos * 1_000_000)
    while "v" not in caixa and GLib.get_monotonic_time() < fim:
        Gtk.main_iteration_do(False)

saida = {}
for chave, (largura, altura, lista) in CASOS.items():
    ponte = PonteDaTela(folha=None)
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(largura, altura)
    janela.add(ponte.view)
    janela.show_all()
    ponte.view.load_uri(PAGINA.as_uri())
    esperar({}, 4)
    pos = {}
    ponte.perguntar(POR % json.dumps(lista), lambda v, e: pos.update(v=v, e=repr(e) if e else ""))
    esperar(pos, 8)
    esperar({}, 0.5)
    caixa = {}
    ponte.perguntar(MEDIR, lambda v, e: caixa.update(v=v, e=repr(e) if e else ""))
    esperar(caixa, 8)
    saida[chave] = json.loads(caixa["v"]) if caixa.get("v") else {"erro": caixa, "pos": pos}
    janela.destroy()
print(json.dumps(saida))
"""


@pytest.fixture(scope="module")
def medida() -> dict[str, dict[str, list[float]]]:
    casos = {f"{w}x{h}-{n}": (w, h, _extensoes(n)) for w, h in VISTAS for n in QUANTAS}
    ambiente = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    filho = subprocess.run([sys.executable, "-c", _SONDA, str(DESENHO)], input=json.dumps(casos),
                           env=ambiente, capture_output=True, text=True, timeout=300)
    if filho.returncode != 0:
        pytest.skip(f"o WebKit não subiu na tela de mentira: {filho.stderr.strip()[-300:]}")
    return dict(json.loads(filho.stdout.strip().splitlines()[-1]))


def _alturas(m: dict[str, list[float]]) -> list[float]:
    alturas = m.get("lf")
    assert isinstance(alturas, list) and len(alturas) == len(exp.LANCADORES) + 1, \
        f"a sonda não leu os cartões da fila: {m}"
    return alturas


@pytest.mark.parametrize("vista", [f"{w}x{h}" for w, h in VISTAS])
def test_a_altura_do_cartao_nao_depende_das_extensoes(
        medida: dict[str, dict[str, list[float]]], vista: str) -> None:
    """Prova da D-2210-OS-CARTOES-DOS-LANCADORES-TEM-A-ALTURA-DO-CONTEUDO.

    Com 2, 4 e 8 extensões, cada `.lf` tem a mesma altura (2 px de tolerância).
    """
    por_n = {n: _alturas(medida[f"{vista}-{n}"]) for n in QUANTAS}
    todas = [a for alturas in por_n.values() for a in alturas]
    assert max(todas) - min(todas) <= 2, f"a altura do cartão muda com as extensões: {por_n}"


@pytest.mark.parametrize("vista", [f"{w}x{h}" for w, h in VISTAS])
def test_a_sobra_fica_fora_do_quadro(
        medida: dict[str, dict[str, list[float]]], vista: str) -> None:
    """Com poucas extensões, o quadro «Lançadores» acaba logo depois da fila, e a aba não rola."""
    m = medida[f"{vista}-2"]
    assert all(isinstance(m.get(k), list) for k in ("lanc", "fim", "rola", "miolo")), \
        f"a sonda não leu: {m}"
    lanc, fim, rola, miolo = m["lanc"], m["fim"], m["rola"], m["miolo"]
    assert rola[0] <= rola[1] + 1, f"a fila dos lançadores rola com duas extensões: {m}"
    assert miolo[0] <= miolo[1] + 1, f"a aba rola: {m}"
    # Embaixo do último cartão, só o respiro do `.quadro-corpo` (14 px) e a borda.
    assert lanc[1] - fim[1] <= 20, f"o quadro estica além da fila, com a sobra dentro dele: {m}"


def test_a_fileira_da_fila_nao_reparte_a_sobra() -> None:
    """A regra da fonte, sem WebKit: nenhuma `grid-auto-rows` da `.lanc-fila` leva `fr`."""
    filas = re.findall(r"\.lanc-fila\s*\{([^}]*)\}", exp.CSS)
    linhas = [d for d in filas if "grid-auto-rows" in d]
    assert linhas, "a `.lanc-fila` perdeu a altura própria da fileira"
    com_fr = [d for d in linhas if re.search(r"grid-auto-rows:[^;]*\dfr", d)]
    assert not com_fr, f"a fileira reparte a sobra do quadro: {com_fr}"


@pytest.mark.parametrize("vista", [f"{w}x{h}" for w, h in VISTAS])
def test_o_que_o_cartao_mostra_cabe_nele(
        medida: dict[str, dict[str, list[float]]], vista: str) -> None:
    """O nome de duas linhas (o lançador e os jogos) cabe na fileira, sem vazar pela borda."""
    for n in QUANTAS:
        m = medida[f"{vista}-{n}"]
        cabe = m.get("cabe")
        assert isinstance(cabe, list) and cabe, f"a sonda não leu os cartões: {m}"
        vazam = [par for par in cabe
                 if not isinstance(par, list) or len(par) != 2 or par[0] > par[1]]
        assert not vazam, f"vaza do cartão com {n} extensões ([conteúdo, cartão]): {cabe}"
