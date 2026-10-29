"""AS-ABAS-DOS-CONTROLES-NA-ABA-JOGAR-01 — uma aba por controle conectado, da cor do plástico dele.

O desenho aprovado em 28/10/2026 (D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR): na Jogar, o
«Selecionar:», a fita e o «Todos» saem, e cada controle conectado ganha uma aba no topo do
cartão. A aba e o cartão se pintam pela mesma regra do plástico, o clique troca o cartão pelo
mesmo gesto da fita, e o lugar vazio não vira aba.

AS RÉGUAS:

1. o desenho (o mockup que o `--publicar 01` leva): sem fita, uma aba por lugar da mesa,
   o vazio apagado, com o gesto da fita e o endereço do nome, da via e da dica;
2. a folha do plástico é uma só e pinta a aba com o tom do plástico dela;
3. o pacote diz o nome, a via e a dica de cada aba;
4. o gesto da aba escolhe o controle do cartão;
5. na tela (WebKit, com o BOOTSTRAP do piloto): N controles, N abas, cada uma da cor do
   plástico; o clique troca o cartão; o que chega ganha aba, o que sai a perde, e o cartão
   escolhido que sai passa ao seguinte.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import pacotes  # isort:skip
from hefesto_dualsense4unix.interface import monta, onde
from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

from tests.conftest import skip_sem_gi_real

RAIZ = pathlib.Path(__file__).resolve().parents[2]

JOGAR = onde.BANCADA / "01-jogar.html"

PLASTICOS = {"p1": "midnight-black", "p2": "starlight-blue", "p3": "cosmic-red", "p4": "white"}

ABA = re.compile(r'<label class="aba-ctl( off)?" for="c-(p\d)" role="tab" data-gesto="([^"]+)" '
                 r'data-pref="\2" data-controle="\2">(.*?)</label>', re.S)


def _doc() -> str:
    return JOGAR.read_text(encoding="utf-8")


def _corpo() -> str:
    return _doc().split("<body", 1)[1]


def test_a_jogar_nao_tem_mais_a_fita_nem_o_todos() -> None:
    """O «Selecionar:», a fita e o rádio do «Todos» saem da Jogar; quem escolhe são as abas.

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    corpo = _corpo()
    assert "Selecionar:" not in corpo
    assert not re.search(r'class="fita[ "]', corpo)
    assert 'id="c-todos"' not in corpo
    assert "01-jogar" in monta.ABAS_SEM_A_FITA


def test_uma_aba_por_lugar_e_o_vazio_nasce_apagado() -> None:
    """Uma aba por lugar da mesa, na ordem; a do lugar vazio nasce com `off`.

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    abas = ABA.findall(_corpo())
    assert [p for _off, p, _g, _d in abas] == [c["pref"] for c in monta.MESA]
    vazios = {c["pref"] for c in monta.MESA if not c.get("conectado", True)}
    assert {p for off, p, _g, _d in abas if off} == vazios
    for _off, pref, gesto, dentro in abas:
        assert gesto == monta.GESTO_DA_FITA, f"a aba {pref} não escolhe pelo gesto da fita"
        for campo in ("aba-nome", "aba-via", "aba-dica", "jogador"):
            assert f'data-campo="{campo}"' in dentro, f"a aba {pref} perdeu o endereço `{campo}`"


def test_a_fileira_das_abas_abre_o_quadro_dos_controles() -> None:
    """As abas ficam no topo do quadro, antes do primeiro cartão, e cada uma abre o rádio dele."""
    quadro = _corpo().split('<div class="quadro estica">', 1)[1]
    assert 0 <= quadro.find('class="abas-ctl"') < quadro.find('<div class="ctl card')
    for c in monta.MESA:
        assert f'id="c-{c["pref"]}"' in quadro


def test_a_folha_do_plastico_pinta_a_aba_com_o_tom_dela() -> None:
    """A mesma regra pinta a caixa e a aba; o tom é o da borda do plástico, não o hexa cru.

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    mesa = [{"pref": p, "cor": s} for p, s in PLASTICOS.items()]
    folha = a02.folha_do_plastico(mesa)
    assert ".aba-ctl[data-controle]" in folha.splitlines()[0]
    for pref, slug in PLASTICOS.items():
        regra = next(linha for linha in folha.splitlines()
                     if f'.aba-ctl[data-controle="{pref}"]' in linha)
        assert f"--plastico:{a02.cor_da_borda(slug)};" in regra, regra
        assert f'.ctl[data-controle="{pref}"]' in regra, "a aba e o cartão por regras diferentes"


def test_o_pacote_diz_o_nome_a_via_e_a_dica_da_aba() -> None:
    """O nome dado ao controle vence; sem ele, a cor do plástico; a via vira o glifo.

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    casa = {"nome": "Midnight Black", "jogador": 1}
    assert a02.campos_da_aba({}, "aabbcc000001", casa, "USB") == {
        "aba-nome": "Midnight Black", "aba-via": "usb", "aba-dica": "Midnight Black · USB"}
    com_nome = a02.campos_da_aba({"AABBCC000002": "Ana & Bia"}, "aa:bb:cc:00:00:02",
                                 {"nome": "White", "jogador": 2}, "BT")
    assert com_nome == {"aba-nome": "Ana &amp; Bia", "aba-via": "bt", "aba-dica": "Ana & Bia · BT"}


def test_o_gesto_da_aba_escolhe_o_controle_do_cartao(monkeypatch: pytest.MonkeyPatch) -> None:
    """O clique na aba chega ao `_escolher_na_fita`, e o tique seguinte mira aquele controle.

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    from hefesto_dualsense4unix.interface import hefesto_vivo

    monkeypatch.setattr(hefesto_vivo.ESCOLHA_DA_FITA, "uniq", "")
    mesa = [{"pref": "p1", "uniq": "aa:bb:cc:00:00:01"},
            {"pref": "p2", "uniq": "aa:bb:cc:00:00:02"}]
    ctx = pacotes.Contexto(state={"controllers": mesa}, mesa=mesa, conectados=mesa)
    assert hefesto_vivo._pref_escolhido(mesa) == "p1"
    hefesto_vivo._escolher_na_fita(ctx, {"pref": "p2"}, None)
    assert hefesto_vivo._pref_escolhido(mesa) == "p2"
    assert hefesto_vivo._pref_escolhido(mesa[:1]) == "p1", "o escolhido que sai não passou adiante"


def _bootstrap() -> str:
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto"
    return m.group(1)


@pytest.fixture(scope="module")
def tela() -> Any:
    """O mockup da Jogar num WebView oculto, com o BOOTSTRAP do produto."""
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico: rode sob `xvfb-run -a` (pulo não é verde)")
    sys.path.insert(0, str(RAIZ / "scripts"))
    import regua_de_tela

    t = regua_de_tela.Tela(JOGAR, titulo_esperado="Hefesto", largura=1918, altura=840)
    t.executar(_bootstrap() + ";'ok'")
    yield t
    t.fechar()


LER = r"""
(function(){
  var abas = [];
  document.querySelectorAll('.aba-ctl').forEach(function(a){
    if(!a.getClientRects().length) return;
    abas.push([a.dataset.controle, getComputedStyle(a).borderTopColor]);
  });
  var cartoes = [];
  document.querySelectorAll('.ctl.card').forEach(function(c){
    if(c.getClientRects().length && getComputedStyle(c).display !== 'none')
      cartoes.push(c.dataset.controle);
  });
  var m = document.querySelector('.radio-mesa:checked');
  return JSON.stringify({abas: abas, cartoes: cartoes, marcado: m ? m.id : ''});
})()
"""


def _rgb(hexa: str) -> str:
    r, g, b = (int(hexa[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgb({r}, {g}, {b})"


def _pintar(tela: Any, prefs: list[str], alvo: str = "") -> dict[str, Any]:
    mesa = [{"pref": p, "cor": PLASTICOS[p]} for p in prefs]
    carga = {"mesa": {"plastico-css": a02.folha_do_plastico(mesa)}, "alvo": alvo,
             "ocupados": prefs, "vazios": [p for p in PLASTICOS if p not in prefs]}
    tela.executar(f"(function(){{window.__hef.pintar({json.dumps(carga)});return 'ok';}})()")
    tela.avancar(0.15)
    return dict(json.loads(tela.executar(LER)))


@skip_sem_gi_real
@pytest.mark.parametrize("prefs", [["p1"], ["p1", "p2"], ["p1", "p2", "p3", "p4"]])
def test_n_controles_n_abas_cada_uma_da_cor_dela(tela: Any, prefs: list[str]) -> None:
    """Com 1, 2 e 4 na mesa: uma aba visível por controle, com a borda do plástico dele.

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    lido = _pintar(tela, prefs, prefs[0])
    assert [p for p, _cor in lido["abas"]] == prefs
    for pref, cor in lido["abas"]:
        assert cor == _rgb(a02.cor_da_borda(PLASTICOS[pref])), (
            f"a aba {pref} está {cor}, e o plástico {PLASTICOS[pref]} pede "
            f"{a02.cor_da_borda(PLASTICOS[pref])}")
    assert lido["cartoes"] == [prefs[0]]


@skip_sem_gi_real
def test_o_clique_na_aba_troca_o_cartao_e_manda_o_gesto(tela: Any) -> None:
    """O clique troca o cartão na hora e manda o gesto da fita com o controle da aba.

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    _pintar(tela, ["p1", "p2", "p3"], "p1")
    tela.limpar_recados()
    tela.clicar('.aba-ctl[data-controle="p3"]')
    tela.avancar(0.15)
    lido = json.loads(tela.executar(LER))
    assert lido["cartoes"] == ["p3"] and lido["marcado"] == "c-p3", lido
    gestos = [r.objeto for r in tela.recados(monta.GESTO_DA_FITA)]
    assert gestos and gestos[-1].get("pref") == gestos[-1].get("controle") == "p3", gestos


@skip_sem_gi_real
def test_quem_chega_ganha_aba_e_o_escolhido_que_sai_passa_ao_seguinte(tela: Any) -> None:
    """No tempo: o P4 chega e ganha aba; o P2 escolhido sai, perde a aba, e o cartão passa.

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    _pintar(tela, ["p1", "p2"], "p2")
    tela.clicar('.aba-ctl[data-controle="p2"]')
    lido = _pintar(tela, ["p1", "p2", "p4"], "p2")
    assert [p for p, _c in lido["abas"]] == ["p1", "p2", "p4"]
    assert lido["cartoes"] == ["p2"]
    lido = _pintar(tela, ["p1", "p4"], "p1")
    assert [p for p, _c in lido["abas"]] == ["p1", "p4"]
    assert lido["cartoes"] == ["p1"] and lido["marcado"] == "c-p1", lido
    lido = _pintar(tela, ["p4"], "")
    assert lido["cartoes"] == ["p4"], "o escolhido saiu e nenhum cartão ficou à vista"


@skip_sem_gi_real
def test_sem_controle_nenhum_a_secao_diz_player_1_desconectado(tela: Any) -> None:
    """Sem aba nenhuma, o lugar aberto é a linha fechada do vazio, com o texto dela.

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    lido = _pintar(tela, [], "")
    assert lido["abas"] == []
    texto = tela.executar(
        "(function(){var c=document.querySelector('.quadro-corpo > .ctl:has(> input:checked)');"
        "return c ? c.innerText.replace(/\\s+/g,' ').trim() : '';})()")
    assert texto == "Player 1 • Desconectado"


@skip_sem_gi_real
def test_o_clique_do_piloto_com_alvo_acha_o_cartao_e_nao_para_na_aba(tela: Any) -> None:
    """A aba também é `[data-controle]`: o clique do piloto mirado no P3 cai no cartão do P3.

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    from hefesto_dualsense4unix.interface import hefesto_vivo

    _pintar(tela, ["p1", "p2", "p3"], "p1")
    js = hefesto_vivo.TOCAR + hefesto_vivo.CLIQUE_COM_ALVO % (json.dumps("mudo"),
                                                              json.dumps(["p3"]))
    assert tela.executar(js) == "no bloco de p3"


TRANSBORDA = r"""
(function(){
  var q = document.querySelector('.quadro.estica .quadro-corpo');
  var d = document.documentElement;
  return JSON.stringify({x: q.scrollWidth - q.clientWidth, y: q.scrollHeight - q.clientHeight,
                         doc: d.scrollHeight - d.clientHeight,
                         lateral: d.scrollWidth - d.clientWidth});
})()
"""


@skip_sem_gi_real
def test_na_vista_do_desenho_as_quatro_abas_e_a_faixa_cabem_sem_rolar() -> None:
    """Na janela mínima (a vista do desenho), quatro abas e a faixa cabem sem rolagem.

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico: rode sob `xvfb-run -a` (pulo não é verde)")
    sys.path.insert(0, str(RAIZ / "scripts"))
    import regua_de_tela

    from hefesto_dualsense4unix.interface.folha_da_casa import VISTA_DO_DESENHO

    largura, altura = VISTA_DO_DESENHO
    t = regua_de_tela.Tela(JOGAR, titulo_esperado="Hefesto", largura=largura, altura=altura)
    try:
        t.executar(_bootstrap() + ";'ok'")
        for alvo in PLASTICOS:
            _pintar(t, list(PLASTICOS), alvo)
            t.clicar(f'.aba-ctl[data-controle="{alvo}"]')
            t.avancar(0.15)
            lido = json.loads(t.executar(TRANSBORDA))
            assert lido == {"x": 0, "y": 0, "doc": 0, "lateral": 0}, alvo
    finally:
        t.fechar()


EXTERNOS = [
    {"name": "Pro Controller", "vid": "057e", "pid": "2009", "bus": "usb",
     "uniq": "aa:bb:cc:00:00:e1", "driver": "nintendo", "player_slot": 3},
    {"name": "Xbox Wireless Controller", "vid": "045e", "pid": "0b13", "bus": "bluetooth",
     "uniq": "aa:bb:cc:00:00:e2", "driver": "xpadneo", "player_slot": 4},
]


def _com_a_cor_do_pro(monkeypatch: pytest.MonkeyPatch) -> str:
    from hefesto_dualsense4unix.integrations.cor_do_plastico import tom_para_a_borda
    from hefesto_dualsense4unix.interface import mesa_viva
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    declaracao = MaquinaConfig.model_validate(
        {"controles": {"aabbcc0000e1": {"cor": "Galactic Purple"}}})
    monkeypatch.setattr(mesa_viva, "_declaracao_do_disco", lambda: declaracao)
    return tom_para_a_borda(a08_conexoes.a_declaracao_do_externo(EXTERNOS[0])["cor"])


def _os_externos(externos: list[dict[str, Any]]) -> dict[str, str]:
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar

    ctx = pacotes.Contexto(state={"connected": True}, mesa=[], conectados=[],
                           externos=list(externos))
    return {"externos": a01_jogar._html_dos_externos(ctx),
            "abas-externos": a01_jogar._abas_dos_externos(ctx)}


def test_o_externo_ganha_a_aba_dele_sem_marca_de_assento(monkeypatch: pytest.MonkeyPatch) -> None:
    """Xbox, Nintendo Pro e 8BitDo também são controles conectados: cada um ganha a aba dele.

    A aba abre o rádio do cartão do externo (`c-xN`, N o número do jogador), na ordem do
    número, e não leva `data-controle` nem gesto: o Hefesto não escreve no externo.
    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    tom = _com_a_cor_do_pro(monkeypatch)
    feito = _os_externos(EXTERNOS)
    abas = re.findall(r'<label class="aba-ctl aba-ext" for="c-(x\d)"[^>]*style="([^"]*)"',
                      feito["abas-externos"])
    assert [x for x, _s in abas] == ["x3", "x4"]
    assert f"--plastico:{tom};" in abas[0][1] and "order:3;" in abas[0][1]
    assert f"--plastico:{a02.BORDA_SEM_COR};" in abas[1][1]
    for marca in ("data-controle", "data-gesto", "data-uniq"):
        assert marca not in feito["abas-externos"], marca
    for x in ("x3", "x4"):
        assert re.search(rf'<div class="ext-cartao"[^>]*><input class="radio-mesa" type="radio" '
                         rf'name="mesa" id="c-{x}">', feito["externos"]), x
    assert ">Nintendo<" in feito["abas-externos"] and ">Xbox<" in feito["abas-externos"]
    assert _os_externos([])["abas-externos"] == monta.NADA_A_DIZER


def test_a_fileira_das_abas_tem_o_lugar_dos_externos() -> None:
    """O endereço das abas dos externos mora dentro da fileira, e o pacote o promete."""
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar

    fileira = _corpo().split('class="abas-ctl"', 1)[1].split("</div>", 1)[0]
    assert 'data-campo="abas-externos" data-hef-alvo="html"' in fileira
    assert "abas-externos" in a01_jogar.DA_PAGINA


LER_COM_EXTERNOS = r"""
(function(){
  function vis(e){
    return !!(e && e.getClientRects().length && getComputedStyle(e).display !== 'none');
  }
  function esq(a){ return a.getBoundingClientRect().left; }
  var abas = [];
  [...document.querySelectorAll('.aba-ctl')].filter(vis)
    .sort(function(a, b){ return esq(a) - esq(b); })
    .forEach(function(a){
      abas.push([a.getAttribute('for').slice(2), getComputedStyle(a).borderTopColor]);
    });
  var todos = '.quadro-corpo > .ctl.card, .quadro-corpo .ext-cartao';
  var abertos = [...document.querySelectorAll(todos)].filter(vis).map(function(c){
    return c.dataset.controle || c.querySelector('.radio-mesa').id.slice(2);
  });
  var m = document.querySelector('.radio-mesa:checked');
  return JSON.stringify({abas: abas, abertos: abertos, marcado: m ? m.id : ''});
})()
"""


def _pintar_com_externos(tela: Any, prefs: list[str], externos: list[dict[str, Any]],
                         alvo: str = "") -> dict[str, Any]:
    mesa_ds = [{"pref": p, "cor": PLASTICOS[p]} for p in prefs]
    carga = {"mesa": {"plastico-css": a02.folha_do_plastico(mesa_ds), **_os_externos(externos)},
             "alvo": alvo, "ocupados": prefs, "vazios": [p for p in PLASTICOS if p not in prefs]}
    tela.executar(f"(function(){{window.__hef.pintar({json.dumps(carga)});return 'ok';}})()")
    tela.avancar(0.15)
    return dict(json.loads(tela.executar(LER_COM_EXTERNOS)))


@pytest.fixture()
def tela_com_externos(tela: Any) -> Any:
    yield tela
    _pintar_com_externos(tela, ["p1"], [], "p1")


@skip_sem_gi_real
def test_o_externo_tem_aba_e_o_clique_abre_o_cartao_dele(
        tela_com_externos: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dois DualSense e dois externos dão quatro abas na ordem do número; o clique no Xbox
    abre o cartão dele, esconde o do DualSense e não manda gesto ao daemon.

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR e D-2810-O-EXTERNO-ENTRA-NA-SECAO-CONTROLES-DA-JOGAR.
    """
    tela = tela_com_externos
    tom = _com_a_cor_do_pro(monkeypatch)
    lido = _pintar_com_externos(tela, ["p1", "p2"], EXTERNOS, "p1")
    assert [a for a, _c in lido["abas"]] == ["p1", "p2", "x3", "x4"], lido
    assert dict(lido["abas"])["x3"] == _rgb(tom), lido
    assert lido["abertos"] == ["p1"], lido
    tela.limpar_recados()
    tela.clicar('.aba-ctl[for="c-x4"]')
    tela.avancar(0.15)
    lido = json.loads(tela.executar(LER_COM_EXTERNOS))
    assert lido["abertos"] == ["x4"] and lido["marcado"] == "c-x4", lido
    assert not tela.recados(monta.GESTO_DA_FITA), "a aba do externo mandou gesto ao daemon"


@skip_sem_gi_real
def test_a_escolha_do_externo_sobrevive_a_lista_que_muda(tela_com_externos: Any) -> None:
    """No tempo: o Xbox escolhido segue aberto quando o Pro sai e volta (a lista se reescreve),
    e quando o próprio Xbox sai, o cartão passa ao controle do alvo.

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    tela = tela_com_externos
    _pintar_com_externos(tela, ["p1", "p2"], EXTERNOS, "p1")
    tela.clicar('.aba-ctl[for="c-x4"]')
    tela.avancar(0.15)
    lido = _pintar_com_externos(tela, ["p1", "p2"], EXTERNOS[1:], "p1")
    assert [a for a, _c in lido["abas"]] == ["p1", "p2", "x4"]
    assert lido["abertos"] == ["x4"] and lido["marcado"] == "c-x4", lido
    lido = _pintar_com_externos(tela, ["p1", "p2"], EXTERNOS, "p1")
    assert lido["abertos"] == ["x4"], lido
    lido = _pintar_com_externos(tela, ["p1", "p2"], EXTERNOS[:1], "p1")
    assert lido["abertos"] == ["p1"] and lido["marcado"] == "c-p1", lido


@skip_sem_gi_real
def test_so_com_externos_o_primeiro_abre_e_o_dualsense_que_chega_toma_o_lugar(
        tela_com_externos: Any) -> None:
    """Sem DualSense, o cartão aberto é o do primeiro externo; o DualSense que chega, e é o
    alvo, abre o dele (a escolha automática do externo não prende o cartão).

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    tela = tela_com_externos
    tela.executar("(function(){window.__hef.abaSincronizada=false;"
                  "window.__hef.abaEscolhida='';return 'ok';})()")
    lido = _pintar_com_externos(tela, [], EXTERNOS, "")
    assert [a for a, _c in lido["abas"]] == ["x3", "x4"]
    assert lido["abertos"] == ["x3"], lido
    lido = _pintar_com_externos(tela, ["p1"], EXTERNOS, "p1")
    assert lido["abertos"] == ["p1"], lido


VISTAS = [(1920, 1080), (1918, 840), (1668, 730), (1212, 809)]


@skip_sem_gi_real
@pytest.mark.parametrize(("largura", "altura"), VISTAS)
def test_com_externos_nenhuma_vista_rola(largura: int, altura: int) -> None:
    """Dois DualSense e dois externos, cada aba aberta por vez: nada rola nas quatro vistas.

    D-2810-AS-ABAS-DOS-CONTROLES-NA-JOGAR.
    """
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico: rode sob `xvfb-run -a` (pulo não é verde)")
    sys.path.insert(0, str(RAIZ / "scripts"))
    import regua_de_tela

    t = regua_de_tela.Tela(JOGAR, titulo_esperado="Hefesto", largura=largura, altura=altura)
    try:
        t.executar(_bootstrap() + ";'ok'")
        for aba in ("p1", "p2", "x3", "x4"):
            _pintar_com_externos(t, ["p1", "p2"], EXTERNOS, "p1")
            t.clicar(f'.aba-ctl[for="c-{aba}"]')
            t.avancar(0.15)
            assert json.loads(t.executar(LER_COM_EXTERNOS))["abertos"] == [aba]
            lido = json.loads(t.executar(TRANSBORDA))
            assert lido == {"x": 0, "y": 0, "doc": 0, "lateral": 0}, (aba, lido)
    finally:
        t.fechar()
