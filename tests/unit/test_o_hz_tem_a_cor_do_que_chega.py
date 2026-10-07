"""O Hz tem a cor do que chega — O-HZ-TEM-A-COR-DA-DISTANCIA-01.

O que o usuário disse em 30/09/2026, ~02h, com a aba Conexões aberta e os quatro
DualSense no rádio:
*«naquela sessão do hertz eles precisam ter os
numeros com fontes mudando de cores do vermelho <!-- noqa-acento: citação literal -->
branco e verde pra indicar o quão bom a sua
distancia tá daquele conector.»* <!-- noqa-acento: citação literal -->
E às ~03h, sobre quais números: *«isso. um pra cada conector»* — o Hz de cada
controle e o «N/79» de cada adaptador.

MEDIDO antes da cura (02/10, sobre ``cba4c97ab``, o mesmo instrumento antes e
depois): o 359, o 180 e o «sem número» saíam na mesma cor, e só o 60 mudava
(laranja); os «N/79» 74, 44 e 20 saíam os três laranja; o ``.hz`` tinha
opacidade 0,8; o glifo tinha um par de arcos só; e o ``a08`` atribuía o
``CANAIS_DO_BT = 79`` e o ``HZ_QUE_ENGASGA = 125.0`` à mão.

As decisões (decisão de produto, 30/09/2026, a validar pelo usuário):
D-3009-O-HZ-SE-PINTA-PELO-QUE-O-JOGO-RECEBE e
D-3009-OS-CANAIS-SE-PINTAM-PELO-PISO-DO-SALTO. A distância de verdade é o RSSI
do enlace (D-3009-A-DISTANCIA-E-O-RSSI-E-ESPERA-A-PROVA), e o leitor dele
espera a prova 0 na bancada.

Nenhuma régua espera o que a própria função devolve: os números de entrada são
os medidos pela casa (a sprint cita as fontes), e os cortes vêm de donos que
não são a tela.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

import ast
import copy
import gc
import json
import re
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
MOCKUP = RAIZ / "mockup" / "08-conexoes.html"

MEDIO = "medio"  # (noqa-acento): nome de máquina, o valor do `data-nivel`
U = ["aabbcc000011", "aabbcc000022", "aabbcc000033", "aabbcc000044", "aabbcc000055"]


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    monkeypatch.setattr(a08_conexoes, "_NIVEL_NA_TELA", {})
    monkeypatch.setattr(a08_conexoes, "_SALA_NA_TELA", {})
    return a08_conexoes


def _atribuicoes(caminho: Path) -> dict[str, ast.expr]:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    saida: dict[str, ast.expr] = {}
    for no in arvore.body:
        alvos = (no.targets if isinstance(no, ast.Assign)
                 else [no.target] if isinstance(no, ast.AnnAssign) and no.value else [])
        for alvo in alvos:
            if isinstance(alvo, ast.Name) and no.value is not None:
                saida[alvo.id] = no.value
    return saida


def test_os_cortes_tem_dono_e_o_dono_nao_e_a_tela() -> None:
    """O ``HZ_DO_JOGO`` é o NOME do teto do pad virtual, e não um 250 digitado"""
    from hefesto_dualsense4unix.core import physical_report_reader as prr
    from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
    from hefesto_dualsense4unix.integrations import radio_da_mesa as dono
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    assert dono.HZ_DO_JOGO == prr.MOTION_EMIT_MAX_HZ
    do_dono = _atribuicoes(SRC / "integrations" / "radio_da_mesa.py")
    jogo = do_dono.get("HZ_DO_JOGO")
    assert isinstance(jogo, ast.Name) and jogo.id == "MOTION_EMIT_MAX_HZ", (
        "o `HZ_DO_JOGO` não lê o teto do pad virtual pelo nome")
    assert dono.HZ_QUE_ENGASGA * 8 == 1000
    assert ar.CANAIS_MINIMOS_DO_AFH == 20
    assert a08_conexoes.CANAIS_DO_BT is ar.CANAIS_DO_BT
    da_tela = _atribuicoes(SRC / "interface" / "pacotes" / "a08_conexoes.py")
    for nome in ("HZ_QUE_ENGASGA", "HZ_DO_JOGO", "CANAIS_DO_BT", "CANAIS_CALMOS",
                 "CANAIS_MINIMOS_DO_AFH"):
        assert nome not in da_tela, f"o `{nome}` voltou a ser atribuído na tela"
    numeros = {nome: ast.literal_eval(valor) for nome, valor in da_tela.items()
               if isinstance(valor, ast.Constant) and isinstance(valor.value, int | float)
               and not isinstance(valor.value, bool)}
    assert not {n: v for n, v in numeros.items() if v in (125, 250, 79)}, numeros


HZ_LISO = [250.0, 250.88,
           312.0, 523.0, 575.0, 728.0,
           338.0, 393.0,
           258.0, 293.0,
           333.0, 359.0, 387.0]
HZ_MEDIO = [214.0, 171.0, 198.0, 126.0,
            170.5]
HZ_ENGASGA = [28.0, 97.0, 35.0, 13.5,
              55.4, 0.0]


@pytest.mark.parametrize(("hz", "nivel"), [
    *((x, "liso") for x in HZ_LISO), *((x, MEDIO) for x in HZ_MEDIO),
    *((x, "engasga") for x in HZ_ENGASGA),
    (125.0, MEDIO), (124.9, "engasga"), (250.0, "liso"), (249.9, MEDIO),
    (None, ""), (True, ""), ("359", ""), (float("nan"), ""),
])
def test_o_nivel_do_movimento_pelos_numeros_da_casa(hz: Any, nivel: str) -> None:
    """MORDIDAS: o verde cortado no ``HZ_INPUT_SEM_MIC`` (260,4) em vez do teto"""
    from hefesto_dualsense4unix.integrations import radio_da_mesa as dono

    assert dono.nivel_do_movimento(hz) == nivel


@pytest.mark.parametrize(("usados", "nivel"), [
    (79, "liso"), (74, "liso"), (60, "liso"),
    (59, MEDIO), (52, MEDIO), (44, MEDIO), (24, MEDIO), (21, MEDIO),
    (20, "engasga"), (0, "engasga"), (None, ""), (True, ""), ("74", ""),
])
def test_o_nivel_dos_canais_pelo_piso_do_salto(usados: Any, nivel: str) -> None:
    """79, 74 e 60 calmos; 59, 52 (02:30), 44, 24 e 21 (01:23) fugindo; 20 no"""
    from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar

    assert ar.nivel_dos_canais(usados) == nivel


def _cena_dos_quatro(hz: dict[str, Any] | None = None) -> dict[str, Any]:
    """Direita com dois (359 e 180), Esquerda com um (60), Meio com um sem"""
    from hefesto_dualsense4unix.interface import aba08

    cena = copy.deepcopy(aba08.CENA_DO_RADIO)
    direita, esquerda, meio = (lug["id"] for lug in cena["lugares"][:3])
    valores = {U[0]: 359.0, U[1]: 180.0, U[2]: None, U[3]: 60.0, U[4]: 250.0,
               **(hz or {})}

    def controle(u: str, lugar: str) -> dict[str, Any]:
        return {"id": u, "aparelho": u, "tipo": "controle", "lugar": lugar,
                "nome": "", "rotulo": "DualSense", "cor": "", "cor_nome": "",
                "mic": False, "luz": True, "fixo": False, "ponte": None, "alem": False,
                "esperando": False, "hz_mov": valores[u], "hz_voz": None, "sinal": -30,
                "hz_referencia": 360.0}

    cena["aparelhos"] = [controle(U[0], direita), controle(U[1], direita),
                         controle(U[2], meio), controle(U[3], esquerda)]
    if U[4] in valores and valores[U[4]] is not None:
        cena["aparelhos"].append({**controle(U[4], ""), "usb": True})
    cena["evitados"], cena["proposta"], cena["pedido"] = [], None, None
    return cena


def _alvos(sala: str, campo: str) -> list[str]:
    return re.findall(rf'data-campo="{campo}" [^>]*?data-alvo="([^"]+)"', sala)


def test_cada_controle_tem_o_nivel_dele_na_ordem_da_sala(a08: Any) -> None:
    """``hz-nivel`` sai na ordem dos elementos da sala (é assim que o piloto o"""
    from hefesto_dualsense4unix.integrations.radio_da_mesa import PALAVRAS_DE_CULPA

    campos = a08.campos_da_secao(_cena_dos_quatro())
    sala = campos["radio-sala"]
    ordem = _alvos(sala, "hz-movimento")
    assert ordem == [U[0], U[1], U[3], U[2]], ordem
    assert _alvos(sala, "hz-nivel") == ordem and _alvos(sala, "hz-dica") == ordem
    assert campos["hz-nivel"] == ["liso", MEDIO, "engasga", ""], campos["hz-nivel"]
    assert len(campos["hz-dica"]) == 4
    causa = a08.FRASE_DA_CAUSA["interferencia"]  # o sinal é bom: quem cai, cai por interferência
    assert campos["hz-dica"] == [a08.DICA_DO_MOVIMENTO["liso"], causa, causa,
                                 a08.DICA_DO_MOVIMENTO[""]]
    assert U[4] not in sala, "o controle do cabo apareceu na seção do rádio"
    for dica in {*a08.DICA_DO_MOVIMENTO.values(), *a08.FRASE_DA_CAUSA.values()}:
        palavras = set(re.findall(r"\w+", dica.lower()))
        assert not palavras & PALAVRAS_DE_CULPA, dica
        assert "distância" not in palavras and "cabo" not in palavras, dica


def test_a_sala_que_nasce_ja_traz_o_nivel(a08: Any) -> None:
    """A sala refeita (um aparelho a mais na caixa) já vem com o nível de cada"""
    a08.campos_da_secao(_cena_dos_quatro(), segurar=True)
    cena = _cena_dos_quatro()
    cena["aparelhos"].append({**cena["aparelhos"][0], "id": "aabbcc000066",
                              "aparelho": "aabbcc000066", "hz_mov": 300.0})
    sala = a08.campos_da_secao(cena, segurar=True)["radio-sala"]
    niveis = dict(re.findall(r'data-hef-atributo="data-nivel" data-alvo="([^"]+)"'
                             r'(?: data-nivel="([^"]*)")?', sala))
    assert niveis == {U[0]: "liso", U[1]: MEDIO, U[3]: "engasga", U[2]: "",
                      "aabbcc000066": "liso"}, niveis


def _tique(a08: Any, monkeypatch: pytest.MonkeyPatch, t: float, hz: dict[str, Any],
           sem: tuple[str, ...] = ()) -> dict[str, str]:
    monkeypatch.setattr(a08, "_RELOGIO_DO_NIVEL", lambda: t)
    cena = _cena_dos_quatro(hz)
    cena["aparelhos"] = [a for a in cena["aparelhos"] if a["id"] not in sem]
    campos = a08.campos_da_secao(cena, segurar=True)
    return dict(zip(_alvos(campos["radio-sala"], "hz-nivel"), campos["hz-nivel"],
                    strict=True))


def test_a_cor_piora_na_hora_e_melhora_depois_de_tres_segundos(
    a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O vermelho entra na janela em que o Hz cai e só sai com 3 s sem janela"""
    linha = [(0.0, 359.0, "liso"), (1.0, 60.0, "engasga"), (2.0, 359.0, "engasga"),
             (3.9, 359.0, "engasga"), (4.1, 359.0, "liso")]
    for t, hz, esperado in linha:
        niveis = _tique(a08, monkeypatch, t, {U[1]: hz, U[0]: 359.0})
        assert niveis[U[1]] == esperado, (t, niveis)
        assert niveis[U[0]] == "liso", (t, niveis)


def test_o_segura_e_por_controle(a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O mesmo, com o vizinho de antes na lista saindo da cena aos 2 s: o"""
    for t, hz, esperado, sem in [(0.0, 359.0, "liso", ()), (1.0, 60.0, "engasga", ()),
                                 (2.0, 359.0, "engasga", (U[0],)),
                                 (3.9, 359.0, "engasga", (U[0],)),
                                 (4.1, 359.0, "liso", (U[0],))]:
        niveis = _tique(a08, monkeypatch, t, {U[1]: hz}, sem)
        assert niveis[U[1]] == esperado, (t, niveis)
        assert niveis[U[3]] == "engasga" and niveis[U[2]] == "", niveis


_ROTEIRO = r"""
(() => {
  const sala = document.querySelector('[data-campo="radio-sala"]');
  if (!sala) return JSON.stringify({erro: 'a página não tem a sala'});
  sala.innerHTML = SALA_AQUI;
  const raiz = getComputedStyle(document.documentElement);
  const tokens = {};
  for (const t of ['--green', '--fg', '--red', '--texto-mudo', '--panel'])
    tokens[t] = raiz.getPropertyValue(t).trim();
  const partes = [];
  for (const p of sala.querySelectorAll('.parte.movimento')) {
    const hz = p.querySelector('.hz');
    const nivel = p.querySelector('.nivel');
    const svg = nivel && nivel.querySelector('svg');
    const cs = svg ? getComputedStyle(svg) : null;
    partes.push({
      alvo: p.dataset.alvo, nivel: p.getAttribute('data-nivel'),
      cor: getComputedStyle(hz).color, opacidade: getComputedStyle(hz).opacity,
      arcos: cs ? [cs.getPropertyValue('--arco-1').trim(),
                   cs.getPropertyValue('--arco-2').trim()] : null,
      dica: nivel ? nivel.getAttribute('title') : null,
    });
  }
  const sinal = document.querySelector('#rd-sinal');
  const caminhos = sinal ? Array.from(sinal.querySelectorAll('path'))
    .map(c => c.getAttribute('style') || '') : [];
  return JSON.stringify({tokens, partes, caminhos});
})()
"""


def _rodar_no_webkit(sala: str) -> dict[str, Any]:
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    roteiro = _ROTEIRO.replace("SALA_AQUI", json.dumps(sala))
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def guardou(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        Gtk.main_quit()

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    view.connect("load-changed", carregou)
    view.load_uri(MOCKUP.as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
        view = janela = None
        gc.collect()
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
    assert saiu, "o WebKit não respondeu em 30 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    dados = json.loads(saiu[0])
    assert "erro" not in dados, dados
    return dict(dados)


def _rgb(css: str) -> tuple[int, int, int]:
    css = css.strip()
    if css.startswith("#"):
        h = css[1:]
        h = "".join(c * 2 for c in h) if len(h) == 3 else h[:6]
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r, g, b = (int(float(x)) for x in re.findall(r"[\d.]+", css)[:3])
    return r, g, b


def test_a_cor_de_cada_nivel_na_tela(a08: Any) -> None:
    """No WebKit, com a folha da página: a cor do número de cada nível é a do"""
    from hefesto_dualsense4unix.utils.color_contrast import razao_contraste

    sala = a08.html_da_sala(_cena_dos_quatro(), com_hz=True)
    medido = _rodar_no_webkit(sala)
    tokens = {k: _rgb(v) for k, v in medido["tokens"].items()}
    painel = tokens["--panel"]
    por_nivel = {"liso": ("--green", ["1", "1"]), MEDIO: ("--fg", ["1", "0"]),
                 "engasga": ("--red", ["0", "0"]), None: ("--texto-mudo", ["1", "0"])}
    vistos = set()
    for parte in medido["partes"]:
        if parte["alvo"] not in U:
            continue
        token, arcos = por_nivel[parte["nivel"]]
        vistos.add(parte["nivel"])
        cor = _rgb(parte["cor"])
        assert cor == tokens[token], (parte, token, medido["tokens"][token])
        assert float(parte["opacidade"]) == 1.0, parte
        alfa = float(parte["opacidade"])
        visto = tuple(round(alfa * c + (1 - alfa) * f) for c, f in zip(cor, painel, strict=True))
        assert razao_contraste(visto, painel) >= 4.5, (parte, razao_contraste(visto, painel))
        assert [a or "1" for a in parte["arcos"]] == arcos, parte
        assert parte["dica"] == a08.DICA_DO_MOVIMENTO[parte["nivel"] or ""], parte
    assert vistos == {"liso", MEDIO, "engasga", None}, vistos
    assert any("var(--arco-1" in c for c in medido["caminhos"]), medido["caminhos"]
    assert any("var(--arco-2" in c for c in medido["caminhos"]), medido["caminhos"]
