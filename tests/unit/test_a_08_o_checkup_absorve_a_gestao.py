"""O CHECK-UP ABSORVE A GESTÃO — A-08-O-CHECKUP-ABSORVE-A-GESTAO-01, 25/09/2026.

Pedido dela: a Gestão de Controles entra no Check-up, e cada controle passa a
dizer o ESTADO dele agora (Mic, Som, Modo de conexão, Visto como, Conexão
estável, Bateria), com o nome do dono no lugar de «Player N» e o Perfil de
Desempenho dele (o botão do Modo Economia virou os três perfis em 26/09/2026,
A-GESTAO-DOS-CONTROLES-NO-PRODUTO-01; as réguas dele moram em
`test_o_perfil_de_desempenho_e_de_cada_controle.py`). Tudo lido do daemon vivo e
da declaração — de um a quatro controles, USB, BT e misto.

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
                      "est-bateria", "perfil", "dono"):
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


def test_o_modo_de_conexao_e_o_chip_aceso_da_jogar(monkeypatch: pytest.MonkeyPatch) -> None:
    """*«Modo de conexão (DualSense)»*: o nome do chip que a aba Jogar acende.

    MORDIDA: devolva o ``MODO_PELO_HEFESTO`` fixo em `modo_da_fileira` → reprova.
    """
    pac = _pac()
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar

    c = {"uniq": UNIQS[0], "transport": "usb"}

    def modo(st: dict[str, Any]) -> str:
        return pac.estado_do_controle(c, {}, st, _Declaracao())["est-modo"]

    assert pac.MODO_NATIVO in modo({"native_mode": True})
    monkeypatch.setattr(a01_jogar, "_estado_da_tela",
                        lambda st: {"modo-aceso": "xbox", "steam-input-aceso": ""})
    assert "<b>Xbox</b>" in modo({"native_mode": False})
    monkeypatch.setattr(a01_jogar, "_estado_da_tela",
                        lambda st: {"modo-aceso": "", "steam-input-aceso": "steam"})
    assert "<b>Steam Input</b>" in modo({"native_mode": False})
    monkeypatch.setattr(a01_jogar, "_estado_da_tela",
                        lambda st: {"modo-aceso": "dualsense", "steam-input-aceso": ""})
    assert "<b>Sony DualSense</b>" in modo({"native_mode": False})
    # e o modo lido uma vez para a mesa inteira chega igual a cada controle
    assert "<b>Navegação</b>" in pac.estado_do_controle(
        c, {}, {"native_mode": False}, _Declaracao(), "Navegação")["est-modo"]


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
@pytest.mark.parametrize("arquivo", [BANCADA, PUBLICADA])
def test_a_gestao_mora_dentro_do_check_up(arquivo: pathlib.Path) -> None:
    """MORDIDA: devolva o quadro «Gestão de Controles» ao `MIOLO` → reprova.

    A SEÇÃO QUE ABSORVEU SE CHAMA «Gestão de Controles» desde 26/09/2026
    (`D-2609-O-CHECKUP-VIRA-GESTAO-DOS-CONTROLES`): o nome é UM título só, o da
    primeira seção, e não um segundo quadro.
    """
    html = arquivo.read_text(encoding="utf-8")
    titulos = re.findall(r'<label class="quadro-titulo" for="([\w-]+)">Gestão de Controles<', html)
    assert titulos == ["cx8-2"], titulos
    assert ">Check-up<" not in html, "o nome velho da seção voltou"
    checkup = html[html.index('id="cx8-2"'):html.index('id="rd-secao"')]
    assert 'class="gc"' in checkup and 'class="ferramentas"' in checkup
    for campo in ("est-mic", "est-som", "est-modo", "est-visto", "est-conexao",
                  "est-bateria", "perfil", "dono",
                  "mapear-diz", "mapear-porta", "mapear-conta"):
        assert f'data-campo="{campo}"' in html, f"a página não tem onde pintar `{campo}`"
    for gesto in ("perfil-do-controle", "dono-renomear",
                  "mapear-comecar", "mapear-gravar", "mapear-parar", "examinar-portas"):
        assert f'data-gesto="{gesto}"' in html, f"o gesto `{gesto}` não tem botão"
    # `D-2609-O-ATUALIZAR-ENTRA-NO-EXAMINAR`: um botão só relê e examina.
    for saiu in ("economia-do-controle", "checkup-atualizar"):
        assert f'data-gesto="{saiu}"' not in html, f"o gesto `{saiu}` voltou"


@pytest.mark.parametrize("arquivo", [BANCADA, PUBLICADA])
def test_o_mapear_e_um_botao_so_e_os_que_repetiam_sairam(arquivo: pathlib.Path) -> None:
    html = arquivo.read_text(encoding="utf-8")
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
@pytest.mark.parametrize("arquivo", [BANCADA, PUBLICADA])
def test_um_cartao_por_lugar_e_nada_abre_nem_fecha(arquivo: pathlib.Path) -> None:
    """MORDIDA: devolva as setas do acordeão à `linha_do_controle` → reprova."""
    html = arquivo.read_text(encoding="utf-8")
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


@pytest.mark.parametrize("arquivo", [BANCADA, PUBLICADA])
def test_o_mapear_tem_onde_pintar_a_lista_e_o_passo(arquivo: pathlib.Path) -> None:
    html = arquivo.read_text(encoding="utf-8")
    for campo in ("mapear-lista", "mapear-estado"):
        assert f'data-campo="{campo}"' in html, f"a página não tem onde pintar `{campo}`"


def test_a_ordem_diz_o_que_e_e_o_que_mover() -> None:
    """MORDIDA: tire a instrução do `_card_da_ordem` → reprova.

    O TÍTULO SAIU DA LINHA em 26/09/2026: ele mora fora do campo que o tique
    repinta (`.sugestao > .ordem-tit`), e cada linha é numerada. A página que
    o traz é cobrada em `test_a_sugestao_de_conexao_diz_cada_ajuste.py`.
    """
    pac = _pac()
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import Identidade, Linha, Ordem

    vazio = Linha(texto="", selo="")
    instrucao = "Mova o adaptador Bluetooth para a Entrada 9"
    ordem = Ordem(chave="teste", acao=instrucao,  # (noqa-acento) campo da Ordem
                  o_que_eu_vi=vazio, por_que_importa=vazio, ganho_esperado=vazio,
                  alvo=Identidade(caminho="3-1"), destino="Entrada 9")
    card = pac._card_da_ordem(ordem)
    assert "ordem-tit" not in card, "o título voltou para dentro da linha que o tique repinta"
    assert ('<div class="faca"><span class="n">1</span>'
            'Mova o adaptador Bluetooth para a Entrada 9</div>') in card
    assert pac.TITULO_DA_ORDEM == "Sugestão de Conexão"


def test_o_examinar_tambem_rele_os_controles(monkeypatch: pytest.MonkeyPatch) -> None:
    """`D-2609-O-ATUALIZAR-ENTRA-NO-EXAMINAR`: o «Atualizar» saiu, e o «Examinar
    Entradas» faz o que ele fazia — os nomes dos donos no BlueZ e o rascunho do
    mapa das portas lidos de novo — além de refazer o exame (que relê a
    declaração). Achado sem régua pela conferência de 26/09/2026.

    MORDIDA: tire o `_esquecer("bluez")` ou o `_LOGICA = None` de
    `examinar_portas` → reprova.
    """
    pac = _pac()
    corridas: list[bool] = []
    monkeypatch.setattr(pac, "_correr_o_exame_completo", lambda: corridas.append(True))
    monkeypatch.setattr(pac, "_LOGICA", object())
    antes = pac._GERACAO.get("bluez", 0)
    pac.examinar_portas(None, {}, None)
    assert corridas == [True], "o «Examinar Entradas» não refez o exame"
    assert pac._LOGICA is None, "o rascunho do mapa das portas não foi relido"
    assert pac._GERACAO.get("bluez", 0) == antes + 1, "os nomes no BlueZ não foram relidos"
