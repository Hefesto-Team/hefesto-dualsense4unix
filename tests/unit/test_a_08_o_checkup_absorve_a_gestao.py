"""O CHECK-UP ABSORVE A GESTÃO — A-08-O-CHECKUP-ABSORVE-A-GESTAO-01, 25/09/2026.

Pedido dela: a Gestão de Controles entra no Check-up, e cada controle passa a
dizer o ESTADO dele agora (Mic, Som, Modo de conexão, Visto como, Conexão
estável, Bateria), com o nome do dono no lugar de «Player N» e o botão do Modo
Economia de Bateria. Tudo lido do daemon vivo e da declaração — de um a quatro
controles, USB, BT e misto.

A MORDIDA de cada parte está escrita no teste que a cobra.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

BANCADA = RAIZ / "mockup/08-conexoes.html"
PUBLICADA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html"

# A FAIXA SINTÉTICA DA CASA.
UNIQS = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]


def _pac() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


class _Controle:
    def __init__(self, microfone: bool | None = None, economia: bool | None = None) -> None:
        self.microfone = microfone
        self.economia = economia


class _Orcamento:
    def __init__(self, teto: str | None) -> None:
        self.teto = teto


class _Declaracao:
    """Dublê da `MaquinaConfig`: só os campos que a linha lê, com a MESMA forma."""

    def __init__(self, controles: dict[str, _Controle] | None = None,
                 teto: str | None = None) -> None:
        self.controles = controles or {}
        self.orcamento = _Orcamento(teto)


def _hex(uniq: str) -> str:
    return uniq.replace(":", "")


def _mesa(vias: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mesa, conectados = [], []
    for n, via in enumerate(vias, start=1):
        u = UNIQS[n - 1]
        mesa.append({"pref": f"p{n}", "uniq": u, "jogador": n, "cor": "", "nome": "DualSense",
                     "via": via.upper(), "transporte": via, "mascara": "Xbox 360"})
        conectados.append({"uniq": u, "transport": via, "connected": True,
                           "battery_pct": 50 + n, "hz_movimento": 480})
    return mesa, conectados


# ---------------------------------------------------------------------------
# O ESTADO DA LINHA — cada selo lê o daemon, de um a quatro, USB, BT e misto
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("vias", [["usb"], ["bt"], ["usb", "bt"], ["bt", "usb", "bt", "usb"]])
def test_os_seis_selos_saem_para_cada_controle(vias: list[str]) -> None:
    """MORDIDA: tire o `.update(estado_do_controle(...))` do `pacote()` → reprova."""
    pac = _pac()
    mesa, conectados = _mesa(vias)
    for c in conectados:
        c["speaker"] = {"volume": 100, "muted": False}
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    ctx = Contexto(state={"controllers": conectados, "native_mode": False,
                          "pontes_confirmadas": {u: True for u in UNIQS}},
                   mesa=mesa, conectados=conectados, estados={})
    original = pac._declaracao
    pac._declaracao = lambda recarregar=False: _Declaracao()  # type: ignore[assignment]
    try:
        saida = pac.pacote(ctx)
    finally:
        pac._declaracao = original  # type: ignore[assignment]
    assert len(saida["colunas"]) == len(vias)
    for n, u in enumerate(UNIQS[: len(vias)], start=1):
        col = saida["colunas"][u]
        for campo in ("est-mic", "est-som", "est-modo", "est-visto", "est-conexao",
                      "est-bateria", "economia", "economia-dica", "dono"):
            assert campo in col, f"o controle {n} ({vias[n - 1]}) não recebeu `{campo}`"
        assert "Xbox 360" in col["est-visto"]
        assert f"{50 + n}%" in col["est-bateria"]
        assert col["dono"] == f"P{n}", "sem nome, o campo do dono diz «P N»"
        assert "certo" in col["est-conexao"]


def test_o_mic_desligado_por_escolha_tambem_e_certo() -> None:
    """Pedido dela: *Mic ✓ (também com o mic desligado, se foi escolha)*."""
    pac = _pac()
    u = UNIQS[0]
    dec = _Declaracao({_hex(u): _Controle(microfone=False)})
    selo = pac.estado_do_controle({"uniq": u, "transport": "bt"}, {}, {}, dec)["est-mic"]
    assert "desligado" in selo and "certo" in selo


def test_o_mic_pelo_radio_sem_ponte_nao_e_certo() -> None:
    """Pelo rádio, sem ponte confirmada e sem voz medida, o mic não chega."""
    pac = _pac()
    u = UNIQS[1]
    selo = pac.estado_do_controle({"uniq": u, "transport": "bt"}, {}, {}, _Declaracao())["est-mic"]
    assert "warn" in selo and "certo" not in selo
    no_cabo = pac.estado_do_controle({"uniq": u, "transport": "usb"}, {}, {}, _Declaracao())
    assert "certo" in no_cabo["est-mic"]


def test_a_bateria_diz_carregando() -> None:
    pac = _pac()
    c = {"uniq": UNIQS[0], "transport": "usb", "battery_pct": 40,
         "battery_state": "carregando"}
    assert "carregando" in pac.estado_do_controle(c, {}, {}, _Declaracao())["est-bateria"]


def test_a_conexao_instavel_pelo_radio_e_laranja() -> None:
    pac = _pac()
    c = {"uniq": UNIQS[0], "transport": "bt", "hz_movimento": 20}
    selo = pac.estado_do_controle(c, {}, {}, _Declaracao())["est-conexao"]
    assert "warn" in selo and "instável" in selo


def test_o_modo_de_conexao_vem_do_daemon() -> None:
    pac = _pac()
    c = {"uniq": UNIQS[0], "transport": "usb"}
    assert pac.MODO_NATIVO in pac.estado_do_controle(c, {}, {"native_mode": True},
                                                     _Declaracao())["est-modo"]
    assert pac.MODO_PELO_HEFESTO in pac.estado_do_controle(c, {}, {"native_mode": False},
                                                           _Declaracao())["est-modo"]


# ---------------------------------------------------------------------------
# A ECONOMIA — o botão chama o contrato da O-MODO-ECONOMIA-POR-CONTROLE-01
# ---------------------------------------------------------------------------
class _Ponte:
    def __init__(self) -> None:
        self.declarado: list[dict[str, Any]] = []

    def machine_declare(self, corpo: dict[str, Any]) -> tuple[bool, str]:
        self.declarado.append(corpo)
        return True, ""


def _clicar_economia(dec: _Declaracao, uniq: str) -> _Ponte:
    pac = _pac()
    ponte = _Ponte()
    original, reler = pac._declaracao, pac._reler_a_declaracao
    pac._declaracao = lambda recarregar=False: dec  # type: ignore[assignment]
    pac._reler_a_declaracao = lambda: dec  # type: ignore[assignment]
    try:
        pac.economia_do_controle_gesto(None, {"uniq": uniq}, ponte)
    finally:
        pac._declaracao, pac._reler_a_declaracao = original, reler  # type: ignore[assignment]
    return ponte


def test_o_botao_liga_e_desliga_a_economia_deste_controle() -> None:
    """MORDIDA: troque `escolha is not True` por `True` → o desligar reprova."""
    from hefesto_dualsense4unix.profiles import schema

    u = UNIQS[2]
    ligar = _clicar_economia(_Declaracao(), u)
    assert ligar.declarado == [schema.declaracao_da_economia(u, True)]
    desligar = _clicar_economia(_Declaracao({_hex(u): _Controle(economia=True)}), u)
    assert desligar.declarado == [schema.declaracao_da_economia(u, False)]


def test_sob_a_bateria_longa_o_clique_recusa_e_nao_grava() -> None:
    pac = _pac()
    with pytest.raises(RuntimeError):
        _clicar_economia(_Declaracao(teto="economia"), UNIQS[0])
    assert pac.campos_da_economia(_Declaracao(teto="economia"), UNIQS[0])["economia"] == "mesa"


def test_o_estado_do_botao_segue_a_declaracao() -> None:
    """MORDIDA: faça `campos_da_economia` devolver sempre `""` → reprova."""
    pac = _pac()
    u = UNIQS[3]
    assert pac.campos_da_economia(_Declaracao(), u)["economia"] == ""
    assert pac.campos_da_economia(
        _Declaracao({_hex(u): _Controle(economia=True)}), u)["economia"] == "ligada"


# ---------------------------------------------------------------------------
# O NOME DO DONO — pelo dono do nome (o `Alias`), e «P N» quando apagado
# ---------------------------------------------------------------------------
def test_o_dono_mostra_o_nome_ou_p_n() -> None:
    pac = _pac()
    u = UNIQS[0]
    assert pac.dono_na_linha({pac._mac(u): "Vitória"}, u, 1) == "Vitória"
    assert pac.dono_na_linha({}, u, 3) == "P3"


@pytest.mark.parametrize("digitado, gravado", [("Ana", "Ana"), ("", ""), ("P2", ""), (" p 2 ", "")])
def test_escrever_o_dono_grava_no_alias_e_apagar_volta_ao_p_n(digitado: str, gravado: str) -> None:
    """MORDIDA: tire o `_SO_O_NUMERO` → «P2» vira nome gravado e reprova."""
    pac = _pac()
    chamadas: list[tuple[str, str]] = []

    class _Escrita:
        feita = True

    original_alias, original_nomes = pac._alias_do_aparelho, pac._nomes_dos_donos
    pac._alias_do_aparelho = lambda e, n: (chamadas.append((e, n)), _Escrita())[1]  # type: ignore[assignment]
    pac._nomes_dos_donos = lambda: {pac._mac(UNIQS[1]): "Antigo"}  # type: ignore[assignment]
    try:
        pac.dono_renomear(None, {"uniq": UNIQS[1], "valor": digitado}, None)
    finally:
        pac._alias_do_aparelho, pac._nomes_dos_donos = original_alias, original_nomes  # type: ignore[assignment]
    assert chamadas == [(UNIQS[1].upper(), gravado)]


# ---------------------------------------------------------------------------
# O MAPEAR — a tela pinta a foto do dono do mapa
# ---------------------------------------------------------------------------
def test_a_tela_do_mapear_pinta_a_foto_do_dono() -> None:
    pac = _pac()
    parado = pac.campos_do_mapear({"estado": "parado", "portas": []})
    assert parado["mapear-diz"] == pac.MAPEAR_DIZ["parado"]
    porta = {"rotulo": "Entrada 3", "usb": "2.0", "hub": "", "storm": 2,
             "lugar_no_gabinete": "Frente do gabinete"}
    na_porta = pac.campos_do_mapear({"estado": "porta", "porta": porta, "feitas": 1})
    assert "Entrada 3" in na_porta["mapear-porta"] and "USB 2.0" in na_porta["mapear-porta"]
    assert "2 quedas" in na_porta["mapear-porta"]
    assert na_porta["mapear-conta"].startswith("1 ")


def test_salvar_a_porta_chama_o_dono_com_a_face() -> None:
    """MORDIDA: mande `lugar=porta["lugar"]` em vez da face do formulário → reprova."""
    pac = _pac()
    visto: dict[str, Any] = {}

    class _Mapa:
        def gravar(self, **kw: Any) -> None:
            visto.update(kw)

    original, reler = pac._o_mapa, pac._reler_a_declaracao
    pac._o_mapa = lambda: _Mapa()  # type: ignore[assignment]
    pac._reler_a_declaracao = lambda: None  # type: ignore[assignment]
    try:
        pac.mapear_gravar(None, {"forma": {"nome": "Frente de cima",
                                           "lugar": "Frente do gabinete"}}, None)
    finally:
        pac._o_mapa, pac._reler_a_declaracao = original, reler  # type: ignore[assignment]
    assert visto == {"nome": "Frente de cima", "lugar": "Frente do gabinete"}


# ---------------------------------------------------------------------------
# A PÁGINA — uma seção só, os endereços novos, e o que saiu
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("pagina", [BANCADA, PUBLICADA])
def test_a_gestao_mora_dentro_do_check_up(pagina: pathlib.Path) -> None:
    """MORDIDA: devolva o quadro «Gestão de Controles» ao `MIOLO` → reprova."""
    html = pagina.read_text(encoding="utf-8")
    assert ">Gestão de Controles<" not in html
    checkup = html[html.index('id="cx8-2"'):html.index('id="rd-secao"')]
    assert 'class="gc"' in checkup and 'class="ferramentas"' in checkup
    for campo in ("est-mic", "est-som", "est-modo", "est-visto", "est-conexao",
                  "est-bateria", "economia", "economia-dica", "dono",
                  "mapear-diz", "mapear-porta", "mapear-conta"):
        assert f'data-campo="{campo}"' in html, f"a página não tem onde pintar `{campo}`"
    for gesto in ("economia-do-controle", "dono-renomear", "checkup-atualizar",
                  "mapear-comecar", "mapear-gravar", "mapear-parar", "examinar-portas"):
        assert f'data-gesto="{gesto}"' in html, f"o gesto `{gesto}` não tem botão"


@pytest.mark.parametrize("pagina", [BANCADA, PUBLICADA])
def test_o_mapear_e_um_botao_so_e_os_que_repetiam_sairam(pagina: pathlib.Path) -> None:
    html = pagina.read_text(encoding="utf-8")
    ancoras = re.findall(r'<a [^>]*href="#(mapear-[\w-]+)"', html)
    assert ancoras.count("mapear-portas") == 1
    assert "mapear-entrada-a-entrada" not in ancoras and "mapear-entradas" not in ancoras
    gc = html[html.index('class="gc"'):html.index('id="rd-secao"')]
    assert "Microfone e botões" not in gc and "Limite da vibração" not in gc


# ---------------------------------------------------------------------------
# O DESENHO DE QUEM COORDENA — 25-26/09/2026, depois de ela ver o acordeão:
# *«tá quebradíssima a 8»*. Um cartão por lugar, nada abre nem fecha; o Mapear
# em duas colunas; a ordem de serviço com título e instrução.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("pagina", [BANCADA, PUBLICADA])
def test_um_cartao_por_lugar_e_nada_abre_nem_fecha(pagina: pathlib.Path) -> None:
    """MORDIDA: devolva as setas do acordeão à `linha_do_controle` → reprova."""
    html = pagina.read_text(encoding="utf-8")
    gc = html[html.index('<div class="gc">'):html.index('id="rd-secao"')]
    lugares = re.findall(r'<div class="gc-item gc-(p\d)[^"]*" data-controle="(p\d)"', gc)
    assert [a for a, _b in lugares] == ["p1", "p2", "p3", "p4"], lugares
    assert "gc-seta" not in html, "a seta do acordeão voltou: o cartão não abre nem fecha"
    assert ".gc{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))" in html


def test_a_entrada_da_vez_sai_em_pares_e_a_lista_so_com_nome() -> None:
    """MORDIDA: devolva a entrada sem nome à lista → reprova."""
    pac = _pac()
    porta = {"rotulo": "Entrada 3", "usb": "3.0", "hub": "", "storm": 0}
    fatos = pac.html_da_porta_medida(porta)
    assert fatos.startswith('<dl class="mp-fatos">')
    assert "<dt>Velocidade</dt><dd>USB 3.0</dd>" in fatos
    assert "<dt>Quedas</dt><dd>nenhuma em 7 dias</dd>" in fatos
    assert "Onde fica" not in fatos, "o que não foi medido não entra"
    lista = pac.html_das_entradas_mapeadas([
        {"nome": "Frente de cima", "rotulo": "Entrada 1", "lugar": "Frente"},
        {"nome": "", "rotulo": "Entrada 2", "lugar": ""},
    ])
    assert "Frente de cima" in lista and "Entrada 2" not in lista
    assert pac.html_das_entradas_mapeadas([]) == '<li class="vazio">Nenhuma ainda.</li>'
    campos = pac.campos_do_mapear({"estado": "esperando", "portas": []})
    assert campos["mapear-estado"] == "esperando"


@pytest.mark.parametrize("pagina", [BANCADA, PUBLICADA])
def test_o_mapear_tem_onde_pintar_a_lista_e_o_passo(pagina: pathlib.Path) -> None:
    html = pagina.read_text(encoding="utf-8")
    for campo in ("mapear-lista", "mapear-estado"):
        assert f'data-campo="{campo}"' in html, f"a página não tem onde pintar `{campo}`"


def test_a_ordem_diz_o_que_e_e_o_que_mover() -> None:
    """MORDIDA: tire o título ou a `acao` do `_card_da_ordem` → reprova."""
    pac = _pac()
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import Identidade, Linha, Ordem

    vazio = Linha(texto="", selo="")
    ordem = Ordem(chave="teste", acao="Mova o adaptador Bluetooth para a Entrada 9",
                  o_que_eu_vi=vazio, por_que_importa=vazio, ganho_esperado=vazio,
                  alvo=Identidade(caminho="3-1"), destino="Entrada 9")
    card = pac._card_da_ordem(ordem)
    assert f'<div class="ordem-tit">{pac.TITULO_DA_ORDEM}</div>' in card
    assert '<div class="faca">Mova o adaptador Bluetooth para a Entrada 9</div>' in card
    assert pac.TITULO_DA_ORDEM == "Sugestão de conexão"
