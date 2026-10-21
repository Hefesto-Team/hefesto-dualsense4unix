"""A Experimental maximizada não quebra com as extensões de verdade.

Sprint A-EXPERIMENTAL-MAXIMIZADA-NAO-QUEBRA-COM-AS-EXTENSOES-DE-VERDADE-01.

Medido em 21/10/2026 no piloto (WebKitGTK, lar de mentira, cópia das sete extensões e dos atalhos
de lançador da máquina do usuário): a fila dos lançadores tinha onze linhas (seis fileiras); a
grade, com o piso de cada fileira, passava do quadro sem rolar por dentro, e o miolo da aba
rolava 662 > 649 na janela maximizada (1918x840) e 638 > 618 no piso (1212x809), com «Adicionar
um lançador» atrás da barra do Aplicar. E o ⋮ aberto com as permissões, na última fileira da
lista das extensões, nascia 8 px abaixo do fim da lista (menu até 478, lista até 470): cortado.

A cura: a fila rola por dentro (`.lanc-fila`, a mesma barra fina da lista), o piso da fileira desce
para 32 px até 860 px de altura, e a lista das extensões rola só o que falta para o ⋮ aberto
aparecer (`comportamento.js`), a cada vez que o produto troca a lista. A barra da fila é sobreposta
no WebKitGTK (largura 0 no `clientWidth`): a régua prova a rolagem rolando até o fim.

A sonda abre o desenho num WebKit de verdade, sob a tela de mentira, nas duas vistas, e põe as
linhas como o produto põe (o `innerHTML` de `.ext-lista` e de `.lanc-fila`, gerado pelas mesmas
funções do desenho).

MORDIDA (executada em 21/10/2026): sem o `overflow-y:auto` da `.lanc-fila`,
`test_a_fila_que_nao_cabe_rola_por_dentro` reprova nos três casos e o ⋮ aberto também (o miolo
rola); com o piso de volta em 38 px e o vão em 8, `test_a_fila_dela_cabe_inteira_na_maximizada`
reprova; sem o vigia do ⋮ no `comportamento.js`,
`test_o_menu_com_as_permissoes_da_ultima_fileira_fica_a_vista` reprova nas duas vistas.; sem a
dica na frase da extensão (`ext-faz`), seis dos sete reprovam pelo texto cortado.
"""

from __future__ import annotations

import json
import re
import os
import pathlib
import subprocess
import sys

import pytest

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "mockup" / "07-lancadores.html"
#: A janela maximizada no monitor do usuário e o piso da janela
#: (`LARGURA_DO_DESENHO` x `PISO_DA_VISTA`).
VISTAS = ((1918, 840), (1212, 809))

_DICA = ("O {n} na aba Experimental do Hefesto, com os jogos das pastas e das listas dele, "
         "abertos com o perfil do controle")
_PERMISSAO = "Acrescentar um lançador de jogos e abrir os jogos que ele lista."
_NOMES = ("Azahar", "Dolphin", "Buttplug", "KytyPS5", "Lutris", "mGBA", "RetroArch")


def _extensoes(aberta: int, n: int = len(_NOMES)) -> str:
    """``n`` linhas como as dela; a de índice ``aberta`` com o ⋮ e as permissões à vista."""
    exts = []
    for i in range(n):
        nome = _NOMES[i % len(_NOMES)] + ("" if i < len(_NOMES) else f" {i + 1}")
        menu = exp.menu_html(nome.lower(), [_PERMISSAO]) if i == aberta else ""
        exts.append(exp.Extensao(nome.lower(), nome, _DICA.format(n=nome), "#", selo="Local",
                                 versao="1.0.0", menu=menu))
    return str(exp.extensoes_html(exts))


def _fila(n: int) -> str:
    """``n`` lançadores e, no fim, a linha que adiciona outro."""
    return str(exp.fila_com_novo_html([exp.Fila(f"l{i}", f"Lançador {i + 1}", "", True, "#")
                                       for i in range(n)]))


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
POR = '''(function(fila, lista){
  document.querySelector('.lanc-fila').innerHTML = fila;
  document.querySelector('.ext-lista').innerHTML = lista;
  return 'ok';
})(%s, %s)'''
MEDIR = '''(function(){
  const r = e => { const x = e.getBoundingClientRect();
    return [Math.round(x.top), Math.round(x.bottom)]; };
  const m = document.querySelector('.janela > .miolo');
  const lanc = [...document.querySelectorAll('.quadro')].find(
    q => /Lançadores/.test(q.querySelector('.quadro-titulo')?.textContent || ''));
  const fila = document.querySelector('.lanc-fila');
  const lista = document.querySelector('.ext-lista');
  const menu = lista.querySelector('.ext-pop.aberto');
  const novo = [...fila.querySelectorAll('.lf')].pop();
  return JSON.stringify({miolo: [m.scrollHeight, m.clientHeight], miolo_caixa: r(m),
    lanc: r(lanc), fila: [fila.scrollHeight, fila.clientHeight], fila_caixa: r(fila), novo: r(novo),
    lista_caixa: r(lista), menu: menu ? r(menu) : null,
    cortes: [...m.querySelectorAll('*')].filter(e => {
      const s = e.closest('.ext-lista, .lanc-fila');
      if (s) { const a = e.getBoundingClientRect(), b = s.getBoundingClientRect();
        if (a.bottom <= b.top + 1 || a.top >= b.bottom - 1) return false; }
      const direto = [...e.childNodes].some(x => x.nodeType === 3 && x.textContent.trim());
      if (!direto || e.clientWidth === 0 || e.scrollWidth <= e.clientWidth + 1) return false;
      return !e.closest('[data-dica],[title],[data-hef-dica]');
    }).map(e => e.textContent.trim().slice(0, 40)),
    fim: (fila.scrollTop = fila.scrollHeight, r(novo))});
})()'''

def esperar(caixa, segundos):
    fim = GLib.get_monotonic_time() + int(segundos * 1_000_000)
    while "v" not in caixa and GLib.get_monotonic_time() < fim:
        Gtk.main_iteration_do(False)

saida = {}
for chave, (largura, altura, fila, lista) in CASOS.items():
    ponte = PonteDaTela(folha=None)
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(largura, altura)
    janela.add(ponte.view)
    janela.show_all()
    ponte.view.load_uri(PAGINA.as_uri())
    esperar({}, 4)
    pos = {}
    ponte.perguntar(POR % (json.dumps(fila), json.dumps(lista)),
                    lambda v, e: pos.update(v=v, e=repr(e) if e else ""))
    esperar(pos, 8)
    esperar({}, 0.5)
    caixa = {}
    ponte.perguntar(MEDIR, lambda v, e: caixa.update(v=v, e=repr(e) if e else ""))
    esperar(caixa, 8)
    saida[chave] = json.loads(caixa["v"]) if caixa.get("v") else {"erro": caixa, "pos": pos}
    janela.destroy()
print(json.dumps(saida))
"""


def _casos() -> dict[str, tuple[int, int, str, str]]:
    casos = {}
    for w, h in VISTAS:
        casos[f"{w}x{h}-dela"] = (w, h, _fila(10), _extensoes(-1))
        casos[f"{w}x{h}-mais"] = (w, h, _fila(17), _extensoes(-1, 12))
        casos[f"{w}x{h}-perm"] = (w, h, _fila(10), _extensoes(len(_NOMES) - 1))
    return casos


@pytest.fixture(scope="module")
def medida() -> dict[str, dict[str, list[int] | None]]:
    ambiente = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    comando = [sys.executable, "-c", _SONDA, str(DESENHO)]
    filho = subprocess.run(comando, input=json.dumps(_casos()), env=ambiente,
                           capture_output=True, text=True, timeout=300)
    if filho.returncode != 0:
        pytest.skip(f"o WebKit não subiu na tela de mentira: {filho.stderr.strip()[-300:]}")
    return dict(json.loads(filho.stdout.strip().splitlines()[-1]))


def _caixas(m: dict[str, list[int] | None], *nomes: str) -> list[list[int]]:
    valores = [m.get(n) for n in nomes]
    assert all(isinstance(v, list) for v in valores), f"a sonda não leu {nomes}: {m}"
    return [v for v in valores if isinstance(v, list)]


def _sem_rolar_o_miolo(m: dict[str, list[int] | None]) -> None:
    miolo, caixa, lanc, fila_caixa = _caixas(m, "miolo", "miolo_caixa", "lanc", "fila_caixa")
    assert miolo[0] <= miolo[1] + 1, f"o conteúdo da aba rola: {m}"
    assert caixa[0] <= lanc[0] and lanc[1] <= caixa[1] + 1, f"o «Lançadores» sai da vista: {m}"
    assert fila_caixa[1] <= lanc[1], f"a fila passa da borda do quadro: {m}"
    assert m.get("cortes") == [], f"texto cortado sem a dica: {m.get('cortes')}"


def test_a_fila_dela_cabe_inteira_na_maximizada(
        medida: dict[str, dict[str, list[int] | None]]) -> None:
    """Dez lançadores e a linha do «Adicionar» (a fila dela), na janela maximizada: tudo à vista."""
    m = medida["1918x840-dela"]
    _sem_rolar_o_miolo(m)
    fila, fila_caixa, novo = _caixas(m, "fila", "fila_caixa", "novo")
    assert fila[0] <= fila[1] + 1, f"a fila dela rola na maximizada: {m}"
    assert novo[1] <= fila_caixa[1] + 1, f"o «Adicionar um lançador» fica escondido: {m}"


@pytest.mark.parametrize("caso", [f"{w}x{h}-mais" for w, h in VISTAS] + ["1212x809-dela"])
def test_a_fila_que_nao_cabe_rola_por_dentro(
        medida: dict[str, dict[str, list[int] | None]], caso: str) -> None:
    """Doze extensões e dezoito linhas nas duas vistas, e a fila dela no piso da janela: o miolo
    fica parado e a fila rola por dentro até o «Adicionar um lançador»."""
    m = medida[caso]
    _sem_rolar_o_miolo(m)
    fila, fila_caixa, fim = _caixas(m, "fila", "fila_caixa", "fim")
    assert fila[0] > fila[1], f"a fila cabe sem rolar? a sonda não mede o caso: {m}"
    assert fila_caixa[0] - 1 <= fim[0] and fim[1] <= fila_caixa[1] + 1, \
        f"rolada até o fim, a fila não mostra o «Adicionar um lançador»: {m}"


@pytest.mark.parametrize("vista", [f"{w}x{h}" for w, h in VISTAS])
def test_o_menu_com_as_permissoes_da_ultima_fileira_fica_a_vista(
        medida: dict[str, dict[str, list[int] | None]], vista: str) -> None:
    m = medida[f"{vista}-perm"]
    _sem_rolar_o_miolo(m)
    menu, lista = _caixas(m, "menu", "lista_caixa")
    assert lista[0] <= menu[0] and menu[1] <= lista[1] + 1, f"o ⋮ aberto é cortado pela lista: {m}"


def test_a_barra_da_fila_usa_a_mesma_cor_da_lista() -> None:
    """A barra fina da fila é a da lista das extensões, com as fichas que o tema troca."""

    def regra(seletor: str) -> str:
        achadas = re.findall(re.escape(seletor) + r"\s*\{([^}]*)\}", exp.CSS)
        return " ".join(achadas)

    for parte in ("::-webkit-scrollbar-track", "::-webkit-scrollbar-thumb"):
        fila = re.findall(r"var\(--[\w-]+\)", regra(".lanc-fila" + parte))
        lista = re.findall(r"var\(--[\w-]+\)", regra(".ext-lista" + parte))
        assert fila and fila == lista, (parte, fila, lista)
