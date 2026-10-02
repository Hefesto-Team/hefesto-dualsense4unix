"""A-ABA-VIBRACAO-TEM-O-SENSOR-HAPTICO-E-DOIS-TESTES-01 — o desenho novo dela na aba 05."""

from __future__ import annotations

import asyncio
import json
import pathlib
import time
from html.parser import HTMLParser
from types import MappingProxyType, SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as af_sub
from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.interface import aba05, pacotes
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import (
    HAPTICA_PCT_MAX,
    MatchAny,
    Profile,
)
from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale
from tests.unit.test_a_haptica_chega_a_quem_entra_depois import mesa  # noqa: F401
from tests.unit.test_a_linha_da_haptica_por_audio_na_vibracao import (
    UNIQ,
    _PonteQueGrava,
    perfis,  # noqa: F401
)
from tests.unit.test_cada_motor_tem_o_seu_multiplicador import BRANCO, _Handlers
from tests.unit.test_no_modo_xbox_a_haptica_fina import (
    _ABERTO,
    _FECHADO,
    _QUATRO,
    _motores,
    _Mundo,
    _no_cabo_os_quatro,
    _no_radio_os_quatro,
    _PonteDeMentira,
    mundo,  # noqa: F401
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup/05-vibracao.html"
PAGINA = "05-vibracao.html"


class _Arvore(HTMLParser):
    """Cada elemento com as classes dos ancestrais, na ordem do documento."""

    VAZIOS = frozenset({"input", "br", "img", "meta", "link", "hr", "source", "wbr"})

    def __init__(self) -> None:
        super().__init__()
        self.pilha: list[tuple[str, str]] = []
        self.elementos: list[tuple[str, dict[str, str], list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        dados = {k: v or "" for k, v in attrs}
        self.elementos.append((tag, dados, [c for _, c in self.pilha]))
        if tag not in self.VAZIOS:
            self.pilha.append((tag, dados.get("class", "")))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elementos.append((tag, {k: v or "" for k, v in attrs}, [c for _, c in self.pilha]))

    def handle_endtag(self, tag: str) -> None:
        for i in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[i][0] == tag:
                del self.pilha[i:]
                return


def _arvore(html: str) -> _Arvore:
    arvore = _Arvore()
    arvore.feed(html)
    return arvore


def _celulas_da_coluna(html: str) -> list[dict[str, str]]:
    """Os filhos DIRETOS do ``.ctrl`` de uma coluna: as faixas da grade."""
    return [dados for _tag, dados, pais in _arvore(html).elementos
            if len(pais) == 1 and "camada" not in dados.get("class", "").split()]


def _faixas_da_grade() -> list[str]:
    """As faixas do ``grid-template-rows`` das colunas, lidas da folha do gerador."""
    regra = aba05.CSS.split(".vib > div{", 1)[1].split("}", 1)[0]
    linhas = regra.split("grid-template-rows:", 1)[1].split(";", 1)[0]
    return [p for p in linhas.split() if p.startswith("var(--r-")]


class TestOTrilhoMoraNaForca:
    @pytest.mark.parametrize("pref", [c["pref"] for c in aba05.MESA])
    def test_o_trilho_e_os_degraus_moram_na_mesma_celula(self, pref: str) -> None:
        """Régua 1, sobre o HTML que o GERADOR escreve, nos quatro lugares, cheios e vazios."""
        coluna = next(c for c in aba05.MESA if c["pref"] == pref)
        elementos = _arvore(aba05._coluna(coluna)).elementos
        (trilho,) = [pais for _t, d, pais in elementos if d.get("data-campo") == "mult-pos"]
        (degraus,) = [pais for _t, d, pais in elementos if d.get("data-campo") == "degrau-herdado"]
        assert "forca" in trilho, f"{pref}: o trilho do Personalizado saiu da Força: {trilho}"
        assert "forca" in degraus, f"{pref}: os degraus saíram da Força: {degraus}"

    def test_cada_coluna_tem_as_faixas_da_grade_e_nenhuma_a_mais(self) -> None:
        """Sete faixas na folha, sete células em cada coluna e sete rótulos."""
        faixas = _faixas_da_grade()
        assert faixas[:3] == ["var(--r-des)", "var(--r-nome)", "var(--r-forca)"]
        for c in aba05.MESA:
            assert len(_celulas_da_coluna(aba05._coluna(c))) == len(faixas), c["pref"]
        cabecas = [d for _t, d, pais in _arvore(aba05.MIOLO).elementos
                   if pais and pais[-1] == "rotulos"]
        assert len(cabecas) == len(faixas), len(cabecas)

    def test_a_faixa_do_personalizado_virou_a_sensor_haptico(self) -> None:
        """A quarta célula é a linha da háptica, e o rótulo dela é o dela."""
        html = MOCKUP.read_text(encoding="utf-8")
        assert '<span class="sec-rot">Sensor Háptico' in html
        assert '<span class="sec-rot">Personalizado' not in html
        assert '<span class="sec-rot">Háptica por áudio' not in html
        quarta = _celulas_da_coluna(aba05._coluna(aba05.MESA[0]))[3]
        assert quarta.get("data-campo") == "haptica-fora", quarta


def _ctx(state: dict[str, Any]) -> pacotes.Contexto:
    controle: dict[str, Any] = {"uniq": UNIQ, "connected": True, "player": 1,
                                "transport": "usb", "index": 0}
    item = {"uniq": UNIQ, "pref": "p1", "jogador": 1, "nome": "Prova",
            "cor": "", "transporte": "usb", "via": "cabo",
            "alvo": True, "mascara": "dualsense"}
    state = {"controllers": [controle], **state}
    return pacotes.Contexto(state=state, mesa=[item], conectados=[controle],
                            estados={}, externos=[])


def _coluna(state: dict[str, Any]) -> dict[str, Any]:
    (coluna,) = a05.pacote(_ctx(state))["colunas"].values()
    return coluna


def _esperado(valor: int) -> str:
    """O MAIOR degrau que o valor alcança, pela escada do produto — nada digitado."""
    alcancados = [k for k, m in RUMBLE_POLICY_MULT.items() if valor >= round(m * 100)]
    return max(alcancados, key=lambda k: RUMBLE_POLICY_MULT[k]) if alcancados else ""


@pytest.mark.parametrize("valor", [180, 130, 120, 70, 50, 10])
def test_o_degrau_aceso_e_o_maior_que_o_trilho_alcanca(valor: int) -> None:
    """Régua 2: com o personalizado no trilho, acende o maior degrau alcançado."""
    coluna = _coluna({"rumble_policy": "custom", "rumble_mult_applied": valor / 100})
    assert coluna["mult-pos"] == str(valor)
    assert coluna["degrau"] == _esperado(valor), (valor, coluna["degrau"])


def test_a_escada_da_regua_e_a_da_sprint() -> None:
    """A régua 2 com os números da sprint: 180 Máximo, 130 Balanceado, 70 Economia, 10 nada."""
    assert [_esperado(v) for v in (180, 130, 70, 10)] == ["max", "balanceado", "economia", ""]


@pytest.mark.parametrize("degrau", sorted(RUMBLE_POLICY_MULT))
def test_o_degrau_clicado_continua_aceso(degrau: str) -> None:
    """Cada degrau, escolhido pelo nome, acende ele mesmo: o valor dele cai na faixa dele."""
    assert _coluna({"rumble_policy": degrau})["degrau"] == degrau


def test_a_sensor_haptico_grava_o_ganho_no_perfil(perfis: pathlib.Path) -> None:  # noqa: F811
    """Régua 3: o arraste a 180 grava o ``haptica_pct``, relido do DISCO pelo esquema."""
    save_profile(Profile(name="Bancada", match=MatchAny()))
    ponte = _PonteQueGrava(_Handlers(ativo="Bancada", primario=BRANCO))
    gesto = pacotes.gesto_da_pagina(PAGINA, "haptica")
    assert gesto is not None
    gesto(_ctx({}), {"uniq": BRANCO, "valor": "180"}, ponte)
    dele = (o_que_vale(loader_module.load_profile("Bancada")).controllers or {})[BRANCO]
    assert dele.rumble is not None and dele.rumble.haptica_pct == 180


@pytest.mark.parametrize(("no_ar", "acesa"), [(True, "1"), (False, ""), (None, "")])
def test_a_luz_no_ar_acende_pelo_state_full(no_ar: bool | None, acesa: str) -> None:
    """A bolinha depois do `%` da «Sensor Háptico» é o ``haptica_no_ar`` do daemon."""
    controle: dict[str, Any] = {"uniq": UNIQ, "connected": True, "player": 1,
                                "transport": "usb", "index": 0}
    if no_ar is not None:
        controle["haptica_no_ar"] = no_ar
    ctx = _ctx({"rumble_policy": "balanceado"})
    ctx.state["controllers"] = [controle]
    (coluna,) = a05.pacote(ctx)["colunas"].values()
    assert coluna["haptica-no-ar"] == acesa
    html = MOCKUP.read_text(encoding="utf-8")
    assert html.count('data-campo="haptica-no-ar"') == len(aba05.MESA)


class _Ponte:
    """A ponte de mentira dos testes: guarda cada chamada, na ordem."""

    def __init__(self, *, haptica: dict[str, Any] | None = None) -> None:
        self.chamadas: list[tuple[Any, ...]] = []
        self.haptica = haptica

    def chamar(self, metodo: str, **k: Any) -> bool:
        self.chamadas.append(("chamar", metodo))
        return True

    def rumble_set_checked(self, weak: int, strong: int) -> tuple[bool, None]:
        self.chamadas.append(("rumble_set_checked", weak, strong))
        return True, None

    def rumble_stop_checked(self) -> tuple[bool, None]:
        self.chamadas.append(("rumble_stop_checked",))
        return True, None

    def rumble_passthrough(self, ligado: bool) -> bool:
        self.chamadas.append(("rumble_passthrough", ligado))
        return True

    def rumble_motores_set(self, **k: Any) -> tuple[bool, dict[str, str]]:
        self.chamadas.append(("rumble_motores_set", k))
        return True, {"status": "ok"}

    def haptica_testar(self, uniq: str, ligado: bool) -> tuple[bool, dict[str, Any]]:
        self.chamadas.append(("haptica_testar", uniq, ligado))
        return True, dict(self.haptica or {"status": "ok", "ligado": ligado})

    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]


@pytest.fixture(autouse=True)
def _sem_teste_ligado() -> Any:
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()
    yield
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()


def _clicar(papel: str, ponte: _Ponte, **o: Any) -> None:
    gesto = pacotes.gesto_da_pagina(PAGINA, papel)
    assert gesto is not None, papel
    gesto(_ctx({"rumble_policy": "balanceado"}), {"uniq": UNIQ, **o}, ponte)


class TestOsDoisTestes:
    def test_a_vibracao_treme_os_motores_e_nao_toca_a_haptica(self) -> None:
        ponte = _Ponte()
        _clicar("testar", ponte)
        assert "rumble_set_checked" in ponte.nomes()
        assert "haptica_testar" not in ponte.nomes()
        assert a05.em_teste() == UNIQ and a05.em_teste_da_haptica() == ""

    def test_a_haptica_toca_a_haptica_e_nenhum_par_de_motor(self) -> None:
        """Régua 4. MORDIDA: o «Háptica» chamando o teste de hoje → reprova."""
        ponte = _Ponte()
        _clicar("testar-haptica", ponte)
        assert ponte.chamadas == [("haptica_testar", UNIQ, True)]
        assert a05.em_teste_da_haptica() == UNIQ and a05.em_teste() == ""
        assert _coluna({"rumble_policy": "balanceado"})["em-teste-h"] == "1"

    def test_ligar_a_haptica_desliga_a_vibracao(self) -> None:
        ponte = _Ponte()
        _clicar("testar", ponte)
        ponte.chamadas.clear()
        _clicar("testar-haptica", ponte)
        assert ponte.nomes() == ["rumble_stop_checked", "rumble_passthrough", "haptica_testar"]
        assert a05.em_teste() == "" and a05.em_teste_da_haptica() == UNIQ

    def test_ligar_a_vibracao_desliga_a_haptica(self) -> None:
        ponte = _Ponte()
        _clicar("testar-haptica", ponte)
        ponte.chamadas.clear()
        _clicar("testar", ponte)
        assert ("haptica_testar", UNIQ, False) in ponte.chamadas
        assert ponte.nomes().index("haptica_testar") < ponte.nomes().index("rumble_set_checked")
        assert a05.em_teste_da_haptica() == "" and a05.em_teste() == UNIQ

    def test_o_parar_desliga_o_que_estiver_ligado(self) -> None:
        ponte = _Ponte()
        _clicar("testar-haptica", ponte)
        ponte.chamadas.clear()
        _clicar("parar", ponte)
        assert ("haptica_testar", UNIQ, False) in ponte.chamadas
        assert "rumble_stop_checked" in ponte.nomes() and "rumble_passthrough" in ponte.nomes()
        assert a05.em_teste_da_haptica() == "" and a05.em_teste() == ""

    def test_a_recusa_do_daemon_chega_dizendo_e_nao_acende(self) -> None:
        ponte = _Ponte(haptica={"status": "sem_controle", "motivo": "fora da mesa agora"})
        with pytest.raises(RuntimeError, match="fora da mesa agora"):
            _clicar("testar-haptica", ponte)
        assert a05.em_teste_da_haptica() == ""

    def test_o_arraste_da_sensor_rebate_o_teste_deste_controle(self) -> None:
        ponte = _Ponte()
        _clicar("testar-haptica", ponte)
        ponte.chamadas.clear()
        _clicar("haptica", ponte, valor="180")
        assert ponte.nomes() == ["rumble_motores_set", "haptica_testar"]
        assert ponte.chamadas[-1] == ("haptica_testar", UNIQ, True)

    def test_a_haptica_de_outra_coluna_cala_a_primeira(self) -> None:
        """Um teste só na mesa: o «Háptica» do segundo controle cala o do primeiro."""
        outro = "aa:bb:cc:00:00:07"
        ponte = _Ponte()
        _clicar("testar-haptica", ponte)
        ponte.chamadas.clear()
        _clicar("testar-haptica", ponte, uniq=outro)
        assert ponte.chamadas == [
            ("haptica_testar", UNIQ, False),
            ("haptica_testar", outro, True),
        ]
        assert a05.em_teste_da_haptica() == outro

    def test_sair_da_pagina_cala_o_teste_da_haptica(self) -> None:
        ponte = _Ponte()
        _clicar("testar-haptica", ponte)
        ponte.chamadas.clear()
        a05._largar_o_teste_da_haptica(ponte)
        assert ponte.chamadas == [("haptica_testar", UNIQ, False)]
        assert a05.em_teste_da_haptica() == ""

    def test_o_desenho_tem_os_tres_botoes_numa_linha(self) -> None:
        """«Vibração», «Háptica» e «Parar», nesta ordem, na célula do «Testar agora»."""
        bloco = aba05._coluna(aba05.MESA[0]).split('<div class="acoes-col">', 1)[1]
        papeis = [d.get("data-papel") for _t, d, _p in _arvore(bloco).elementos
                  if _t == "button"]
        assert papeis == ["testar", "testar-haptica", "parar"]
        assert ">Vibração</button>" in bloco and ">Háptica</button>" in bloco


def test_o_par_do_teste_no_teto_do_ganho_nao_corta() -> None:
    """Régua 5, a conta: o bloco do par a 200% fica em 0,996, abaixo de 1,0."""
    import array

    bloco = array.array("f", eh.bloco_da_haptica(*af_sub.PAR_DO_TESTE_DA_HAPTICA))
    pico = max(abs(x) for x in bloco) * HAPTICA_PCT_MAX / 100
    assert pico <= 1.0, pico
    assert pico > 0.99, f"o teste ficou fraco demais: {pico}"
    assert af_sub.PAR_DO_TESTE_DA_HAPTICA[0] == af_sub.PAR_DO_TESTE_DA_HAPTICA[1]


@pytest.mark.parametrize("lugar", [1, 2, 3, 4])
def test_no_cabo_o_teste_toca_o_par_no_tocador_dele_e_abre_so_o_laco_dele(
    mundo: _Mundo, lugar: int  # noqa: F811
) -> None:
    """Régua 5: o par vai ao tocador DAQUELE aparelho, e a volta abre só o laço dele."""
    controles = _no_cabo_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    uniq = _QUATRO[lugar - 1]
    resposta = mundo.sub.testar_a_haptica(uniq, True)
    assert resposta["status"] == "ok" and resposta["ligado"] is True
    tocador = mundo.tocador(uniq)
    assert (tocador.nivel, tocador.sink, tocador.dono) == (
        af_sub.PAR_DO_TESTE_DA_HAPTICA, eh.nome_do_endpoint(uniq), uniq
    )
    assert tocador.nivel == (127, 127)
    mundo.mesa.volta(*controles)
    for outro in _QUATRO:
        assert _motores(mundo, outro) == (_ABERTO if outro == uniq else _FECHADO), outro
    assert mundo.sub.testar_a_haptica(uniq, True)["leva"] is True
    assert mundo.sub.testar_a_haptica(uniq, False)["ligado"] is False
    assert tocador.nivel == (0, 0)
    assert dict(mundo.sub._teste_da_haptica) == {}


def test_no_radio_o_teste_sobe_a_ponte_da_haptica_de_quem_testa(mundo: _Mundo) -> None:  # noqa: F811
    controles = _no_radio_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    uniq = _QUATRO[2]
    mundo.sub.testar_a_haptica(uniq, True)
    mundo.mesa.lidos.clear()
    mundo.mesa.volta(*controles)
    hapticas = [no for no, papel in mundo.mesa.lidos if papel == "haptica"]
    assert hapticas == [eh.nome_do_endpoint(uniq)], hapticas
    assert [p.uniq for p in _PonteDeMentira.criadas] == [uniq]


def test_o_teste_que_ninguem_rebate_solta_sozinho(mundo: _Mundo) -> None:  # noqa: F811
    """A janela que fecha sem o «Parar» não deixa o controle vibrando."""
    from hefesto_dualsense4unix.daemon.subsystems.rumble import TETO_DO_RUMBLE_FIXADO_S

    controles = _no_cabo_os_quatro(mundo)
    mundo.mesa.volta(*controles)
    uniq = _QUATRO[0]
    mundo.sub.testar_a_haptica(uniq, True)
    mundo.mesa.volta(*controles)
    assert mundo.tocador(uniq).nivel == (127, 127), "o rebate em dia não pode soltar"
    mundo.sub._teste_da_haptica = MappingProxyType(
        {uniq: time.monotonic() - TETO_DO_RUMBLE_FIXADO_S - 1}
    )
    mundo.mesa.volta(*controles)
    assert mundo.tocador(uniq).nivel == (0, 0)
    assert dict(mundo.sub._teste_da_haptica) == {}


def test_o_controle_fora_da_mesa_e_recusado_dizendo(mundo: _Mundo) -> None:  # noqa: F811
    mundo.mesa.volta(*_no_cabo_os_quatro(mundo))
    resposta = mundo.sub.testar_a_haptica("aa:bb:cc:00:00:99", True)
    assert resposta["status"] == "sem_controle" and resposta["motivo"]


def test_o_metodo_do_daemon_leva_o_pedido_ao_subsystem() -> None:
    """``haptica.testar`` chega ao subsystem do som; sem ele, ``sem_som``; sem ``uniq``, erro."""
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    pedidos: list[tuple[str, bool]] = []

    def _testar(uniq: str, ligado: bool) -> dict[str, Any]:
        pedidos.append((uniq, ligado))
        return {"status": "ok", "uniq": uniq, "ligado": ligado, "leva": False}

    com_som = SimpleNamespace(daemon=SimpleNamespace(
        _alto_falante_subsystem=SimpleNamespace(testar_a_haptica=_testar)))
    resposta = asyncio.run(IpcHandlersMixin._handle_haptica_testar(
        com_som, {"uniq": UNIQ, "ligado": True}))  # type: ignore[arg-type]
    assert resposta["status"] == "ok" and pedidos == [(UNIQ, True)]
    sem_som = SimpleNamespace(daemon=SimpleNamespace())
    resposta = asyncio.run(IpcHandlersMixin._handle_haptica_testar(
        sem_som, {"uniq": UNIQ, "ligado": False}))  # type: ignore[arg-type]
    assert resposta["status"] == "sem_som"
    with pytest.raises(ValueError):
        asyncio.run(IpcHandlersMixin._handle_haptica_testar(
            com_som, {"ligado": True}))  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        asyncio.run(IpcHandlersMixin._handle_haptica_testar(
            com_som, {"uniq": UNIQ, "ligado": "sim"}))  # type: ignore[arg-type]


def test_a_ponte_do_app_manda_o_metodo(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.app import ipc_bridge

    mandados: list[tuple[str, dict[str, Any]]] = []

    def _corpo(metodo: str, params: dict[str, Any], **_k: Any) -> dict[str, Any]:
        mandados.append((metodo, dict(params)))
        return {"status": "ok"}

    monkeypatch.setattr(ipc_bridge, "_corpo_do_daemon", _corpo)
    assert ipc_bridge.haptica_testar(UNIQ, True) == (True, {"status": "ok"})
    assert mandados == [("haptica.testar", {"uniq": UNIQ, "ligado": True})]


MEDIDA = r"""
(function(){
  var m = document.querySelector('.janela > .miolo');
  var vib = document.querySelector('.vib');
  // A última CÉLULA da coluna: um filho fora do fluxo (a marca da camada,
  // `position:absolute`) não é célula da grade.
  var fundos = Array.prototype.map.call(vib.children, function(col){
    var celulas = Array.prototype.filter.call(col.children, function(e){
      return getComputedStyle(e).position !== 'absolute';
    });
    return Math.round(celulas[celulas.length - 1].getBoundingClientRect().bottom);
  });
  var mold = document.querySelector('[data-controle="p1"] .moldura');
  var linhas = Array.prototype.map.call(document.querySelectorAll('#vib-estado .est'), function(d){
    return Math.round(d.getBoundingClientRect().bottom);
  });
  return JSON.stringify({
    rola: m.scrollHeight - m.clientHeight,
    fundo_do_miolo: Math.round(m.getBoundingClientRect().bottom),
    folga: Math.round(m.getBoundingClientRect().bottom - vib.getBoundingClientRect().bottom),
    fundos: fundos,
    desenho: Math.round(mold.getBoundingClientRect().height),
    linhas: linhas,
  });
})()
"""

DESENHO_DE_ANTES = 124

CENAS = ("quieta", "navegacao", "vpad-nao-subiu")


@pytest.fixture(scope="module", params=CENAS)
def medida(request: Any) -> dict[str, Any]:
    """Abre o DESENHO (a bancada, ``mockup/``) num WebKit offscreen do tamanho do miolo."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre (rode no xvfb-run)")
    from hefesto_dualsense4unix.app.telas import vibracao as _tela
    from hefesto_dualsense4unix.gui.ponte_da_tela import TAMANHO_OCULTA
    from hefesto_dualsense4unix.interface import hefesto_vivo, onde

    pintar = ""
    if request.param != "quieta":
        from tests.unit.test_o_aviso_da_vibracao_cabe_na_aba import ESTADOS_DO_AVISO, _carga

        original = _tela._orcamento_da_maquina
        _tela._orcamento_da_maquina = lambda: None
        try:
            carga = _carga(ESTADOS_DO_AVISO[request.param])
        finally:
            _tela._orcamento_da_maquina = original
        pintar = hefesto_vivo.PEDIR_A_PINTURA.replace(
            "CARGA", json.dumps(carga, ensure_ascii=False))

    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(*TAMANHO_OCULTA)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def mediu(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(f"ERRO na medida: {e}")
        Gtk.main_quit()

    def medir(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO antes da medida: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(MEDIDA, -1, None, None, None, mediu)

    def instalou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        v.evaluate_javascript(pintar, -1, None, None, None, medir)

    def carregou(v: Any, evento: Any) -> None:
        if evento != WebKit2.LoadEvent.FINISHED:
            return
        if pintar:
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None, None, instalou)
        else:
            v.evaluate_javascript(MEDIDA, -1, None, None, None, mediu)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(PAGINA).as_uri())
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 20 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    lido = dict(json.loads(saiu[0]))
    lido["cena"] = request.param
    if request.param != "quieta":
        assert lido["linhas"], f"o aviso não acendeu na cena {request.param}: {lido}"
    return lido


def test_a_aba_nao_rola_e_as_colunas_acabam_no_mesmo_y(medida: dict[str, Any]) -> None:
    """Régua 6, com a mesa quieta e com o aviso aceso."""
    assert medida["rola"] <= 0, f"a aba 05 rola {medida['rola']} px: {medida}"
    assert len(set(medida["fundos"])) == 1, f"as colunas acabam em y diferentes: {medida}"
    assert all(b <= medida["fundo_do_miolo"] for b in medida["linhas"]), (
        f"o aviso passou da borda do miolo: {medida}")


def test_o_desenho_nao_encolhe(medida: dict[str, Any]) -> None:
    """O desenho volta ao tamanho de antes da linha da háptica, e a fala dela é essa."""
    assert medida["desenho"] >= DESENHO_DE_ANTES, (
        f"o desenho encolheu para {medida['desenho']} px: {medida}")
