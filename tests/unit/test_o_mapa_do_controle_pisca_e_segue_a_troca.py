"""O mapa do controle pisca, segue a troca de botões e diz qual controle mostra.

O-MAPA-DO-CONTROLE-PISCA-E-SEGUE-O-REMAPEAMENTO-01. A fala dela, 29/09/2026:
*«Mesmo Sistema que implementamos na aba Controles para cada botão piscar
quando apertarmos ele no controle fisico deve ser implementado no Mapa do  (noqa-acento: dela)
Controle. (…) Falta um filtro pro controle conectado que está sendo visto
ali.»*

A MESA É DE MENTIRA, nas faixas sintéticas da casa (`aa:bb:cc`), e o esperado
de cada régua sai do que a régua montou, nunca do que o pacote escreveu:

1. o pisca é do controle escolhido (`Contexto.escolhido`);
2. «Todos» é a união;
3. a troca diz o que a Navegação diz, com o nome da peça do mapa;
3b. a troca aparece no desenho, no motor dela (WebKit);
4. o endereço existe dos dois lados (pacote e página);
5. a classe acende a peça, no motor dela (WebKit);
6. a fita é uma só: o chip do mapa leva o gesto das abas, e a escolha feita no
   mapa chega ao contexto das abas, pelo `hefesto_vivo._contexto`;
7. o desenho nunca fica com o controle de outro chip: a mesa sem controle apaga
   as lâmpadas e a barra, e o «Todos» desenha o primeiro da mesa (WebKit).

A PÁGINA LIDA: enquanto o mapa estiver declarado em trabalho no
`mockup/DIVERGENCIAS.md` (a licença do portão `desenho-aprovado`), a bancada;
depois do `--publicar`, a publicada.

AS MORDIDAS: o pacote ler o primeiro da mesa no lugar do escolhido (1, 2); a
troca com o id cru (3); tirar a regra da marca tracejada, ou emitir
`trocada-` para toda peça (3b); tirar o endereço de um item do gerador (4);
tirar a regra `.on` do laço (5); um gesto local do mapa, ou o `escolhido` fora do
`pacotes.Contexto` do `hefesto_vivo._contexto` (6); o `segue` sem a
queda no «Nenhum», ou o `desenha` do «Todos» sem o primeiro da mesa (7).

Sem tela o WebKit não abre e as réguas 3b, 5 e 7 PULAM: rode com `xvfb-run -a`.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import pathlib
import re
import sys
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.interface import hefesto_vivo, mesa_viva, monta, onde, pacotes
from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13
from hefesto_dualsense4unix.interface.pacotes import perfil

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PAGINA = a13.PAGINA

#: A mesa de quatro, nas faixas sintéticas. P1 no cabo, os outros no rádio.
UNIQS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03",
         "aa:bb:cc:00:00:04")
#: O que cada um aperta: o P1 a Cruz, o P3 o Triângulo e o clique do analógico
#: esquerdo (o `l3` do leitor, que o mapa chama `stick_l`).
APERTA = {1: ["cross"], 3: ["triangle", "l3"]}
#: O que acende, pelo nome do mapa.
ACENDE_P1 = {"cross"}
ACENDE_P3 = {"triangle", "stick_l"}


def _declaradas() -> set[str]:
    alvo = RAIZ / "scripts/check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("check_desenho_do_mapa_vivo", alvo)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_desenho_do_mapa_vivo"] = mod
    spec.loader.exec_module(mod)
    return set(mod.declaradas())


def _a_pagina() -> pathlib.Path:
    return onde.pagina(PAGINA, publicado=PAGINA not in _declaradas())


def _contexto(escolhido: str = "") -> pacotes.Contexto:
    mesa, conectados = [], []
    for n, uniq in enumerate(UNIQS, start=1):
        via = "USB" if n == 1 else "BT"
        mesa.append({"pref": f"p{n}", "jogador": n, "uniq": uniq, "cor": "",
                     "nome": "Não sei", "via": via, "transporte": via.lower(),
                     "conectado": True})
        conectados.append({"uniq": uniq, "connected": True, "is_primary": n == 1,
                           "transport": via.lower(), "player_slot": n,
                           "inputs": {"buttons": APERTA.get(n, [])}})
    return pacotes.Contexto(state={"active_profile": "regua", "controllers": conectados},
                            mesa=mesa, conectados=conectados, estados={},
                            escolhido=escolhido)


def _acesos(escolhido: str) -> set[str]:
    carga = pacotes.pacote_da_pagina(PAGINA, _contexto(escolhido)) or {}
    return {k[len(a13.ACESO):] for k, v in carga["mesa"].items()
            if k.startswith(a13.ACESO) and v == "sim"}


@pytest.fixture
def com_troca(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """O perfil ativo com o Triângulo trocado pela Cruz — a fala dela, na régua."""
    p = {"name": "regua", "remapeamento": {"triangle": "cross"}}
    monkeypatch.setattr(perfil, "ativo", lambda _nome=None: dict(p))
    return p


# --------------------------------------------------------------------------
# 1 e 2. o pisca é do escolhido, e «Todos» é a união
# --------------------------------------------------------------------------
def test_o_pisca_e_do_controle_escolhido() -> None:
    assert _acesos("p3") == ACENDE_P3, (
        f"com o P3 escolhido acendeu {_acesos('p3')}; o P3 aperta {ACENDE_P3}")
    assert _acesos("p1") == ACENDE_P1


def test_todos_e_a_uniao() -> None:
    assert _acesos("todos") == ACENDE_P1 | ACENDE_P3


def test_sem_escolha_e_o_primeiro_da_mesa() -> None:
    """O contexto que não disse cai no primeiro da mesa, como a fita das abas."""
    assert _acesos("") == ACENDE_P1


# --------------------------------------------------------------------------
# 3. a troca diz o que a Navegação diz
# --------------------------------------------------------------------------
def _nome_da_peca(pid: str) -> str:
    linhas = [x for x in (RAIZ / "docs/data/pecas-do-dualsense.csv").read_text(
        encoding="utf-8").splitlines() if x and not x.startswith("#")]
    return next(p["nome"] for p in csv.DictReader(linhas) if p["id"] == pid)


def test_a_troca_diz_o_que_a_navegacao_diz(com_troca: dict[str, Any]) -> None:
    ctx = _contexto("p1")
    mapa = (pacotes.pacote_da_pagina(PAGINA, ctx) or {})["mesa"]
    nav = (pacotes.pacote_da_pagina("06-navegacao.html", ctx) or {})["mesa"]
    destino = com_troca["remapeamento"]["triangle"]
    assert mapa[f"{a13.TROCA}triangle"] == nav["troca-triangle"], (
        "o mapa e a tela «Trocar os botões» dizem destinos diferentes")
    assert mapa[f"{a13.TROCA}triangle"] == _nome_da_peca(destino)
    assert mapa[f"{a13.TROCADA}triangle"] == "sim"
    sem_troca = {k for k, v in mapa.items() if k.startswith(a13.TROCADA) and not v}
    assert f"{a13.TROCADA}cross" in sem_troca and len(sem_troca) == len(a13.TROCAM) - 1


# --------------------------------------------------------------------------
# 4. o endereço existe dos dois lados
# --------------------------------------------------------------------------
def test_o_endereco_existe_dos_dois_lados() -> None:
    texto = _a_pagina().read_text(encoding="utf-8")
    na_pagina = set(re.findall(r'data-campo="([^"]+)"', texto))
    carga = pacotes.pacote_da_pagina(PAGINA, _contexto("p1")) or {}
    no_pacote = set(carga["mesa"])
    assert no_pacote - na_pagina == set(), (
        f"o pacote pinta o que a página ({_a_pagina().parent.name}) não tem: "
        f"{sorted(no_pacote - na_pagina)}")
    assert na_pagina - no_pacote == set(), (
        f"a página tem endereço sem dono no pacote: {sorted(na_pagina - no_pacote)}")
    for seletor in carga["blocos"]:
        nome = re.fullmatch(r'\[data-bloco="([^"]+)"\]', seletor)
        assert nome and f'data-bloco="{nome.group(1)}"' in texto, seletor


# --------------------------------------------------------------------------
# 6. a fita é uma só
# --------------------------------------------------------------------------
def test_o_chip_do_mapa_e_o_gesto_da_fita_das_abas() -> None:
    gesto = pacotes.gesto_da_pagina(PAGINA, monta.GESTO_DA_FITA)
    assert gesto is not None, "o chip do mapa não tem quem o atenda"
    assert gesto is pacotes.gesto_da_pagina("06-navegacao.html", monta.GESTO_DA_FITA), (
        "o mapa tem uma escolha própria: a fita deixou de ser uma só")
    bloco = (pacotes.pacote_da_pagina(PAGINA, _contexto("p1")) or {})["blocos"]
    chips = "".join(bloco.values())
    for n in range(1, 5):
        assert f'data-gesto="{monta.GESTO_DA_FITA}" data-pref="p{n}"' in chips, chips


@pytest.fixture
def escolha_limpa() -> Any:
    mod = sys.modules[pacotes.gesto_da_pagina(PAGINA, monta.GESTO_DA_FITA).__module__]
    antes = mod.ESCOLHA_DA_FITA.uniq
    yield mod
    mod.ESCOLHA_DA_FITA.uniq = antes


def test_a_escolha_feita_no_mapa_chega_ao_contexto_das_abas(escolha_limpa: Any) -> None:
    mod = escolha_limpa
    st = _contexto().state

    class _Piloto:
        def __init__(self) -> None:
            self.leitor = mesa_viva.LeitorDeCor(ligado=False)
            self._externos: list[dict[str, Any]] = []

    def montar() -> pacotes.Contexto:
        ctx, _ = mod.Piloto._contexto(_Piloto(), st, perguntar=False)
        return ctx

    gesto = pacotes.gesto_da_pagina(PAGINA, monta.GESTO_DA_FITA)
    gesto(montar(), {"pref": "p3"}, None)
    assert montar().escolhido == "p3"


# --------------------------------------------------------------------------
# 3b e 5. no motor dela
# --------------------------------------------------------------------------
MEDIDA = r"""
(function(){
  const vis = s => { const e = document.querySelector(s);
                     return e ? getComputedStyle(e).display : null; };
  const fill = s => { const e = document.querySelector(s);
                      return e ? getComputedStyle(e).fill : null; };
  return JSON.stringify({
    marca_tri: vis('.m-triangle'), marca_cruz: vis('.m-cross'),
    linha_tri: vis('.item-triangle .troca'), linha_cruz: vis('.item-cross .troca'),
    texto_tri: (document.querySelector('[data-campo="troca-triangle"]') || {}).textContent,
    peca_tri: fill('#mp-triangle .peca'), peca_cruz: fill('#mp-cross .peca'),
    leds: [1, 2, 3, 4, 5].filter(i => document.querySelector('#mp-led-jogador-' + i)
                                     .classList.contains('led-on')),
    luz: fill('#mp-lightbar *'), apagada: getComputedStyle(document.documentElement)
                                         .getPropertyValue('--luz-apagada').trim(),
    nenhum_on: !!document.querySelector('[data-bloco="controles-do-mapa"] [data-jogador="0"].on')
  });
})()
"""
ROSA = "rgb(255, 121, 198)"


def _no_webkit(cargas: list[Any]) -> list[dict[str, Any]]:
    """Abre a página, instala a ponte e mede depois de cada carga pintada.

    Uma carga que é texto é um gesto (JavaScript) da pessoa na página, e não uma
    pintura do produto: a medida vem depois dele do mesmo jeito.
    """
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre (rode com xvfb-run -a)")

    saiu: list[str] = []
    fila = list(cargas)
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1600, 900)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def proxima() -> None:
        if not fila:
            Gtk.main_quit()
            return
        carga = fila.pop(0)
        pedido = carga if isinstance(carga, str) else hefesto_vivo.PEDIR_A_PINTURA.replace(
            "CARGA", json.dumps(carga, ensure_ascii=False))
        view.evaluate_javascript(pedido, -1, None, None, None, pintou)

    def mediu(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(f"ERRO na medida: {e}")
        proxima()

    def pintou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO na pintura: {e}")
            Gtk.main_quit()
            return
        GLib.timeout_add(150, lambda: (v.evaluate_javascript(
            MEDIDA, -1, None, None, None, mediu), False)[1])

    def instalou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        proxima()

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None, None, instalou)

    view.connect("load-changed", carregou)
    view.load_uri(_a_pagina().as_uri())
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert len(saiu) == len(cargas), f"o WebKit não respondeu: {saiu}"
    assert not any(s.startswith("ERRO") for s in saiu), saiu
    return [json.loads(s) for s in saiu]


def _carga(escolhido: str) -> dict[str, Any]:
    ctx = _contexto(escolhido)
    return pacotes.normalizar(pacotes.pacote_da_pagina(PAGINA, ctx) or {},
                              {u: f"p{n}" for n, u in enumerate(UNIQS, start=1)})


def test_a_troca_e_o_pisca_aparecem_no_desenho(com_troca: dict[str, Any]) -> None:
    """3b e 5: a marca tracejada e a linha «No jogo» da peça trocada, e a peça
    apertada acesa — e as duas coisas apagam quando o fato some."""
    com_p3, com_p1 = _no_webkit([_carga("p3"), _carga("p1")])
    destino = _nome_da_peca(com_troca["remapeamento"]["triangle"])
    assert com_p3["marca_tri"] != "none" and com_p3["linha_tri"] != "none", com_p3
    assert com_p3["texto_tri"] == destino, com_p3
    assert com_p3["marca_cruz"] == "none" and com_p3["linha_cruz"] == "none", (
        f"a Cruz não tem troca e ganhou a marca: {com_p3}")
    # o P3 aperta o Triângulo: aceso; o P1 aperta a Cruz, que no P3 não acende
    assert com_p3["peca_tri"] == ROSA and com_p3["peca_cruz"] != ROSA, com_p3
    # trocando para o P1, o Triângulo apaga e a Cruz acende
    assert com_p1["peca_tri"] != ROSA and com_p1["peca_cruz"] == ROSA, com_p1


def _rgb(cor: str) -> str:
    r, g, b = (int(cor.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgb({r}, {g}, {b})"


def test_a_mesa_sem_controle_e_o_desenho_sem_controle() -> None:
    """7: sem controle na mesa, o bloco do produto chega só com o «Nenhum», e o
    desenho apaga as lâmpadas e a barra; antes ficava o chip da bancada aceso."""
    ctx = pacotes.Contexto(state={"controllers": []}, mesa=[], conectados=[], estados={})
    vazia = pacotes.normalizar(pacotes.pacote_da_pagina(PAGINA, ctx) or {}, {})
    (medida,) = _no_webkit([vazia])
    assert medida["leds"] == [], f"sem controle, lâmpadas acesas: {medida}"
    assert medida["luz"] == _rgb(medida["apagada"]), f"sem controle, a barra acesa: {medida}"
    assert medida["nenhum_on"], f"sem controle, o «Nenhum» não ficou aceso: {medida}"


def test_o_todos_desenha_o_primeiro_da_mesa() -> None:
    """7: o «Todos» depois de outro chip desenha o primeiro da mesa, de quem o
    produto pinta a barra, e não as lâmpadas do chip anterior."""
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    def acesas(n: int) -> list[int]:
        return [i + 1 for i, on in enumerate(player_led_pattern(n)) if on]

    primeiro = int(monta.MESA[0]["jogador"])
    outro = next(c for c in monta.MESA if int(c["jogador"]) != primeiro)
    assert acesas(int(outro["jogador"])) != acesas(primeiro), "a régua seria cega"
    bloco = '[data-bloco="controles-do-mapa"] '
    clicar = ("(function(){document.querySelector('%s.bt[data-pref=\"%s\"]').click();"
              "return 1;})()")
    no_outro, no_todos = _no_webkit([clicar % (bloco, outro["pref"]), clicar % (bloco, "todos")])
    assert no_outro["leds"] == acesas(int(outro["jogador"])), no_outro
    assert no_todos["leds"] == acesas(primeiro), (
        f"o «Todos» ficou com as lâmpadas do chip anterior: {no_todos}")
