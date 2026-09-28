"""A caixa fica onde ela abriu — A-CAIXA-FICA-ONDE-ELA-ABRIU-01 (item 2 da auditoria de 26/09).

A foto 34 dela, 26/09/2026:

    *«toda hora mesmo selecionando meio o negocio vai pra outra aba da direita
    mesmo comigo tentando sincroniZar o controle.»* <!-- noqa-acento: citação literal dela -->

MEDIDO antes da cura (28/09, com o pacote e a central reais): com o «Conectar»
esperando PS + Create na Direita e o clique dela no Meio, o ``_o_aberto``
devolvia a Direita em 30 de 30 tiques; o chip do Meio recusava sem perguntar a
ninguém; e o ``radio.mover`` para o Meio, pelo tratador real do daemon até a
``CentralDoRadio`` real, responde ``ocupado`` — a central de hoje não muda a
busca de adaptador no meio (a metade dela é pendência da central).

O que esta régua segura, com o rádio de mentira, o ``DonoVivo`` real por cima
dele, o tratador real do daemon e a central real, e a busca DE PÉ (a central
segura a janela aberta, esperando o gesto):

1. um dono para «qual caixa está aberta»: o clique dela, em 30 tiques, com a
   busca em qualquer um dos outros adaptadores, em qualquer ordem da lista e
   com qualquer número de jogador;
2. sem escolha dela, a caixa da busca abre (a regra de 25/09 continua);
3. ela fecha todas: nada abre sozinho, e o cabeçalho do adaptador da busca
   mostra a espera;
4. o chip de outro adaptador pede ao rádio (``radio.mover`` para ele) e não
   recusa por conta própria; a central decide, e o chip aceso diz onde a busca
   está.

MORDIDA: devolva a espera para antes do ``_ABERTO`` no ``_o_aberto`` — o caso 1
reprova em todos os pares.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

import ast
import re
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import central_do_radio as cr
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import QUARTO, SALA, VARANDA, VERDE, VERMELHO
from tests.unit.test_o_conectar_pareia_no_adaptador_escolhido import (
    JOGADORES,
    Bancada,
    BuscaDePe,
    id_da_tela,
    onde_buscou,
    preparar_a_tela,
    preparar_o_diario,
)

#: O chip do «Procurando» no molde do painel: (aceso, adaptador).
CHIP = re.compile(r'<button class="op" aria-pressed="(true|false)"[^>]*'
                  r'data-gesto="escolher-adaptador" data-alvo="([0-9A-F]{12})"')
TRES = (SALA, QUARTO, VARANDA)
#: Todo par (onde a busca está, a caixa que ela abre), nos três adaptadores.
PARES = [(busca, dela) for busca in TRES for dela in TRES if busca != dela]
TIQUES = 30


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    return preparar_a_tela(monkeypatch)


def mundo_com(adaptadores: tuple[str, ...]) -> rm.RadioDeMentira:
    """O vermelho no ar no primeiro adaptador, e o verde novo na mão dela."""
    mundo = rm.RadioDeMentira(adaptadores=adaptadores)
    mundo.pareado(adaptadores[0], VERMELHO)
    mundo.fisicos[VERDE] = rm.Fisico(VERDE, rm.CLASSE_DE_CONTROLE)
    return mundo


def _a_busca_abre_em(bancada: Bancada, busca: BuscaDePe, destino: str) -> None:
    """O caminho dela: o chip do destino, e o «Conectar» — a janela abre ali."""
    bancada.cena()
    bancada.gesto("escolher-adaptador", alvo=id_da_tela(destino))
    bancada.cena()
    assert bancada.gesto("conectar-aparelho") == {"armou": True}
    assert busca.dentro.wait(5.0), "a central não abriu a janela"
    (movimento,) = bancada.central.movimentos()
    assert (movimento.estado, movimento.passo, movimento.destino) == (
        cr.ESPERANDO, cr.PASSO_GESTO, destino)


#: O começo de um cartão de adaptador (e não do `lugar-topo` de dentro dele).
CARTAO = re.compile(r'<div class="lugar[" ]')


def _cartao(sala: str, lid: str) -> str:
    """O cartão inteiro de um adaptador no HTML da sala."""
    comecos = [m.start() for m in CARTAO.finditer(sala)]
    inicio = max(c for c in comecos if c < sala.index(f'data-id="{lid}"'))
    fim = next((c for c in comecos if c > inicio), len(sala))
    return sala[inicio:fim]


# ---------------------------------------------------------------------------
# 1. o clique dela é o dono da caixa aberta
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("jogadores", sorted(JOGADORES))
@pytest.mark.parametrize(("onde_busca", "onde_ela_abre"), PARES)
def test_a_caixa_que_ela_abriu_fica_com_a_busca_noutro_adaptador(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
    onde_busca: str, onde_ela_abre: str, jogadores: str,
) -> None:
    """A cena da foto 34: a busca de pé num adaptador, e o clique dela no ▶ de
    outro. A caixa dela fica aberta nos 30 tiques seguintes (mais que o prazo de
    60 s não cabe numa régua; 30 voltas cobrem a regra de nível que se
    reavaliava a cada uma), e a busca continua onde estava."""
    mundo, relogio = mundo_com(TRES), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio, ordem=TRES,
                      jogadores=JOGADORES[jogadores])
    busca = BuscaDePe(relogio)
    try:
        _a_busca_abre_em(bancada, busca, onde_busca)
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(onde_ela_abre))
        abertos = [bancada.cena()["aberto"] for _ in range(TIQUES)]
        assert abertos == [id_da_tela(onde_ela_abre)] * TIQUES, "o tique desfez o clique dela"
        sala = bancada.tique()["radio-sala"]
        assert 'class="lugar aberto"' in _cartao(sala, id_da_tela(onde_ela_abre))
        assert onde_buscou(mundo) == [rm.HCIS[onde_busca]], "a busca saiu do lugar"
    finally:
        busca.soltar()
        bancada.fechar()


@pytest.mark.parametrize("ordem", [TRES, (VARANDA, SALA, QUARTO), (QUARTO, VARANDA, SALA)])
def test_a_ordem_da_lista_nao_muda_o_dono(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, ordem: tuple[str, ...],
) -> None:
    """O dono é o clique, e não a posição: a busca no primeiro da lista e o
    clique no último, em três ordens."""
    mundo, relogio = mundo_com(TRES), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio, ordem=ordem)
    busca = BuscaDePe(relogio)
    try:
        _a_busca_abre_em(bancada, busca, ordem[0])
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(ordem[-1]))
        for _ in range(TIQUES):
            assert bancada.cena()["aberto"] == id_da_tela(ordem[-1])
    finally:
        busca.soltar()
        bancada.fechar()


# ---------------------------------------------------------------------------
# 2. sem escolha dela, a caixa da busca abre (a regra de 25/09)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("onde_busca", TRES)
def test_sem_escolha_dela_a_caixa_da_busca_abre(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde_busca: str,
) -> None:
    """A busca que não nasceu de um clique na tela (o ``_ABERTO`` vazio): a
    caixa dela abre sozinha, com o «Segure PS + Create» à vista — o que ela
    precisa fazer não custa um clique."""
    mundo, relogio = mundo_com(TRES), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    busca = BuscaDePe(relogio)
    try:
        bancada.central.comecar_a_conectar(onde_busca)
        assert busca.dentro.wait(5.0)
        assert "lugar" not in a08._ABERTO
        for _ in range(TIQUES):
            assert bancada.cena()["aberto"] == id_da_tela(onde_busca)
        cartao = _cartao(bancada.tique()["radio-sala"], id_da_tela(onde_busca))
        assert "aberto" in cartao.split('"', 2)[1] and "Segure PS + Create" in cartao
    finally:
        busca.soltar()
        bancada.fechar()


# ---------------------------------------------------------------------------
# 3. ela fecha todas: nada abre por cima da escolha dela
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("onde_busca", TRES)
def test_ela_fecha_a_caixa_da_busca_e_a_espera_fica_no_cabecalho(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde_busca: str,
) -> None:
    """Fechar a caixa da busca é escolha dela («nenhuma aberta»): nenhuma abre
    nos 30 tiques, e o cabeçalho daquele adaptador — que aparece fechado —
    mostra a espera, piscando, como já mostra o «varrendo»."""
    mundo, relogio = mundo_com(TRES), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    busca = BuscaDePe(relogio)
    try:
        _a_busca_abre_em(bancada, busca, onde_busca)
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(onde_busca))
        for _ in range(TIQUES):
            assert bancada.cena()["aberto"] is None, "a caixa da busca abriu por cima dela"
        cartao = _cartao(bancada.tique()["radio-sala"], id_da_tela(onde_busca))
        classes = cartao.split('"', 2)[1].split()
        assert "aberto" not in classes and "esperando" in classes
        topo = cartao[:cartao.index('<div class="aparelhos"')]
        assert '<span class="espera"' in topo and "Segure PS + Create" in topo
    finally:
        busca.soltar()
        bancada.fechar()


@pytest.mark.parametrize("quantos", [2, 3])
def test_com_dois_ou_tres_adaptadores_o_clique_dela_fica(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, quantos: int,
) -> None:
    """Com dois ou três adaptadores o dono é o mesmo; com UM, a caixa única fica
    aberta com a busca dentro (a decisão dela de 25/09), e o ▶ não a fecha."""
    adaptadores = TRES[:quantos]
    mundo, relogio = mundo_com(adaptadores), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio, ordem=adaptadores)
    busca = BuscaDePe(relogio)
    try:
        _a_busca_abre_em(bancada, busca, adaptadores[-1])
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(adaptadores[0]))
        for _ in range(TIQUES):
            assert bancada.cena()["aberto"] == id_da_tela(adaptadores[0])
    finally:
        busca.soltar()
        bancada.fechar()


def test_com_um_adaptador_so_a_caixa_da_busca_fica_aberta(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    mundo, relogio = mundo_com((SALA,)), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio, ordem=(SALA,))
    busca = BuscaDePe(relogio)
    try:
        _a_busca_abre_em(bancada, busca, SALA)
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(SALA))
        for _ in range(TIQUES):
            assert bancada.cena()["aberto"] == id_da_tela(SALA)
    finally:
        busca.soltar()
        bancada.fechar()


# ---------------------------------------------------------------------------
# 4. o chip de outro adaptador pergunta ao rádio
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("onde_busca", "chip"), PARES)
def test_o_chip_de_outro_adaptador_pede_a_busca_ao_radio(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde_busca: str, chip: str,
) -> None:
    """Com a busca de pé, o chip de outro adaptador manda o ``radio.mover`` para
    ELE — o mesmo pedido do «Conectar» —, e quem responde é a central. A de hoje
    responde ``ocupado`` (MEDIDO): o chip treme, a busca fica onde estava, e a
    caixa aberta continua a dela. O chip do adaptador da busca só abre a caixa,
    sem pedido nenhum."""
    mundo, relogio = mundo_com(TRES), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    busca = BuscaDePe(relogio)
    try:
        _a_busca_abre_em(bancada, busca, onde_busca)
        bancada.cena()
        with pytest.raises(RuntimeError, match="ocupado"):
            bancada.gesto("escolher-adaptador", alvo=id_da_tela(chip))
        assert bancada.ponte.chamadas == [
            ("radio.mover", {"destino": id_da_tela(onde_busca)}),
            ("radio.mover", {"destino": id_da_tela(chip)}),
        ], "o chip recusou sem perguntar ao rádio"
        assert a08._ABERTO["lugar"] == id_da_tela(onde_busca)
        assert onde_buscou(mundo) == [rm.HCIS[onde_busca]]

        assert bancada.gesto("escolher-adaptador", alvo=id_da_tela(onde_busca)) == {
            "armou": True}
        assert len(bancada.ponte.chamadas) == 2
    finally:
        busca.soltar()
        bancada.fechar()


class PonteQueAceita:
    """A resposta da central que MUDA a busca de adaptador — o ``ok`` do
    tratador real, com o movimento novo esperando no destino pedido. A central
    de hoje não a dá com a busca de pé (a metade dela está pendente); esta é a
    régua do lado da tela, para quando der."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        self.chamadas.append((metodo, dict(params)))
        movimento = cr.Movimento(cr.CONECTANDO, str(params["destino"]), cr.ESPERANDO,
                                 cr.PASSO_PREPARANDO, quando=time.time())
        return {"status": "ok", "movimento": movimento.publicar()}


@pytest.mark.parametrize(("onde_busca", "chip"), PARES)
def test_aceito_pela_central_o_chip_leva_a_caixa_e_o_destino(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde_busca: str, chip: str,
) -> None:
    """Quando a central aceita, o chip é um gesto só, sem recusa: a caixa e o
    destino do «Conectar» vão para o adaptador do chip na hora."""
    mundo, relogio = mundo_com(TRES), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    busca = BuscaDePe(relogio)
    try:
        _a_busca_abre_em(bancada, busca, onde_busca)
        bancada.cena()
        bancada.ponte = PonteQueAceita()  # type: ignore[assignment]
        assert bancada.gesto("escolher-adaptador", alvo=id_da_tela(chip)) == {"armou": True}
        assert bancada.ponte.chamadas == [("radio.mover", {"destino": id_da_tela(chip)})]
        assert a08._ABERTO["lugar"] == id_da_tela(chip)
        assert a08._CENA_NA_TELA["aberto"] == id_da_tela(chip)
        assert a08._CENA_NA_TELA["destino_do_conectar"] == id_da_tela(chip)
    finally:
        busca.soltar()
        bancada.fechar()


@pytest.mark.parametrize(("onde_busca", "onde_ela_abre"), PARES)
def test_o_chip_aceso_diz_onde_a_busca_esta(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
    onde_busca: str, onde_ela_abre: str,
) -> None:
    """A caixa aberta é dela, e o chip aceso do «Procurando» é do rádio: com a
    busca de pé na Direita e o Meio aberto, o chip aceso é o da Direita. Acabada
    a busca, o chip volta ao destino do «Conectar», que é a caixa dela."""
    mundo, relogio = mundo_com(TRES), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    busca = BuscaDePe(relogio)
    try:
        _a_busca_abre_em(bancada, busca, onde_busca)
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(onde_ela_abre))
        chips = CHIP.findall(bancada.tique()["radio-moldes"])
        assert sorted(lid for _, lid in chips) == sorted(map(id_da_tela, TRES))
        assert [lid for aceso, lid in chips if aceso == "true"] == [id_da_tela(onde_busca)]
        assert bancada.cena()["destino_do_conectar"] == id_da_tela(onde_ela_abre)
    finally:
        busca.soltar()
        bancada.fechar()


# ---------------------------------------------------------------------------
# 5. a meia chave tem um dono só: a central (achado 8 da auditoria de 26/09)
# ---------------------------------------------------------------------------

INTERFACE = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix" / "interface"


def _quem_chama(nome: str) -> set[tuple[str, str]]:
    """``(arquivo, função)`` de toda chamada a ``nome`` no pacote da interface."""
    achados: set[tuple[str, str]] = set()
    for arquivo in sorted(INTERFACE.rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for funcao in ast.walk(arvore):
            if not isinstance(funcao, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for no in ast.walk(funcao):
                if not isinstance(no, ast.Call):
                    continue
                alvo = no.func
                chamado = (alvo.attr if isinstance(alvo, ast.Attribute)
                           else alvo.id if isinstance(alvo, ast.Name) else "")
                if chamado == nome:
                    achados.add((arquivo.name, funcao.name))
    return achados


def test_so_o_x_dela_esquece_um_pareamento_pela_tela() -> None:
    """Na tela, o pareamento sai por UM caminho: o X dela («Esquecer» da
    pergunta, ``confirmar_esquecer``). A meia chave do «Não Conectou» é da
    central (``central_do_radio._esquecer_a_meia_chave``); o fio da tela que a
    tirava de novo, a partir de um retrato do BlueZ de até 3 s, podia apagar o
    objeto ``Paired`` do «Tentar de Novo» feito logo depois do veredito.

    MORDIDA: devolva o ``_esquecer_as_meias_chaves`` (o fio que chama
    ``_esquecer_o_pareamento`` a cada «não chegou») — um segundo chamador
    aparece e esta régua reprova.
    """
    assert _quem_chama("_esquecer_o_pareamento") == {("a08_conexoes.py", "confirmar_esquecer")}
    assert _quem_chama("esquecer_o_pareamento") == {("a08_conexoes.py", "_esquecer_o_pareamento")}


# ---------------------------------------------------------------------------
# 6. no motor: com o piloto, o chip não acende no clique (o desenho, na bancada)
# ---------------------------------------------------------------------------

#: O roteiro no WebKit: abre o «Procurando» pelo molde (o mesmo que o
#: `abrirPainel('conectar')` da página põe no painel) e clica um chip apagado —
#: primeiro SEM piloto (o desenho aberto no navegador), depois COM ele.
ROTEIRO_DO_CHIP = r"""
(function(){
  function abrir(){
    const m = document.querySelector('.radio template.painel-molde[data-painel="conectar"]');
    const corpo = document.getElementById('rd-painel-corpo');
    corpo.innerHTML = ''; corpo.appendChild(m.content.cloneNode(true));
    document.getElementById('rd-painel').classList.add('aberto');
  }
  function acesos(){
    return [...document.querySelectorAll('#rd-painel .op')]
      .filter(c => c.getAttribute('aria-pressed') === 'true').map(c => c.dataset.alvo);
  }
  function apagado(){
    return document.querySelector('#rd-painel .op[aria-pressed="false"]');
  }
  const fora = {};
  abrir();
  fora.no_molde = acesos();
  let c = apagado(); fora.clicado_sem_piloto = c.dataset.alvo; c.click();
  fora.sem_piloto = acesos();
  window.__hef = window.__hef || {}; window.__hef.ouvindo = true;
  abrir();
  c = apagado(); fora.clicado_com_piloto = c.dataset.alvo;
  try { c.click(); } catch (e) { fora.erro = String(e); }
  fora.com_piloto = acesos();
  return JSON.stringify(fora);
})()
"""


@pytest.fixture(scope="module")
def chip_no_webkit() -> dict[str, Any]:
    """A bancada da 08 num WebKit offscreen — o motor que ela usa."""
    import json

    from hefesto_dualsense4unix.interface import onde

    pagina = onde.pagina("08-conexoes.html")
    if not pagina.is_file():
        pytest.skip("a bancada da 08 não está no disco — rode o gerador")
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    saiu: list[str] = []
    # Offscreen: sob Xvfb não há gerenciador de janelas, e ela tem UMA tela.
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
            v.evaluate_javascript(ROTEIRO_DO_CHIP, -1, None, None, None, guardou)

    view.connect("load-changed", carregou)
    view.load_uri(pagina.as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu, "o WebKit não respondeu em 30 s"
    assert not saiu[0].startswith("ERRO"), saiu[0]
    return dict(json.loads(saiu[0]))


def test_no_motor_com_o_piloto_o_chip_nao_acende_no_clique(chip_no_webkit: dict[str, Any]) -> None:
    """Com o piloto no ar, o chip clicado não acende na página: quem acende é o
    molde, quando o rádio responde. Aceso no clique, o chip que a central
    recusava ficava aceso sobre a busca de pé noutro adaptador (medido na prova
    de tela, 28/09). Sem piloto — o desenho aberto no navegador —, ele acende
    no clique, como no desenho aprovado.

    MORDIDA: tire o ``if(comPiloto()) return;`` do clique do chip no ``aba08.py``
    e regere a bancada — o chip acende com o piloto e esta régua reprova.
    """
    fora = chip_no_webkit
    assert len(fora["no_molde"]) == 1
    assert fora["sem_piloto"] == [fora["clicado_sem_piloto"]], "o desenho perdeu o clique"
    assert fora["com_piloto"] == fora["no_molde"], "o chip acendeu antes do rádio responder"


# ---------------------------------------------------------------------------
# 7. o «Mover» também é o clique dela (a conferência, 28/09/2026)
# ---------------------------------------------------------------------------

#: O vermelho mora na Esquerda (``mundo_com``): o «Mover» dele vai para um dos
#: outros dois, e a caixa que ela deixou aberta antes é qualquer outra.
MOVER = [(destino, dela) for destino in (QUARTO, VARANDA) for dela in TRES if dela != destino]


@pytest.mark.parametrize(("destino", "dela"), MOVER)
def test_o_mover_abre_a_caixa_do_destino_e_o_clique_seguinte_dela_fica(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, destino: str, dela: str,
) -> None:
    """O «Mover» (a pergunta da mudança, ``confirmar-mudanca``) é um clique dela
    num destino, como o «Conectar» e o «Tentar de Novo»: a caixa do destino
    abre, com a linha que diz «Segure PS + Create» e o nome do controle movido
    dentro. Até 28/09 quem a abria era a espera, a cada tique e por cima de
    tudo; com o clique dela como dono, o «Mover» ficava com a caixa de antes
    aberta e o controle movido escondido atrás de um clique.

    E a busca de um aparelho conhecido (a linha ``esperando``, e não o
    «Conectar» sem alvo) também não vence o ▶ que ela der depois.

    MORDIDA: tire o ``_abrir_na_tela(destino)`` do ``confirmar_mudanca`` — a
    caixa de antes fica aberta nos 30 tiques e esta régua reprova.
    """
    mundo, relogio = mundo_com(TRES), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    busca = BuscaDePe(relogio)
    try:
        bancada.cena()
        if a08._CENA_NA_TELA.get("aberto") != id_da_tela(dela):
            bancada.gesto("abrir-adaptador", alvo=id_da_tela(dela))
        assert bancada.cena()["aberto"] == id_da_tela(dela)
        assert bancada.gesto("confirmar-mudanca", alvo=VERMELHO,
                             destino=id_da_tela(destino)) == {"armou": True}
        assert busca.dentro.wait(5.0), "a central não começou o «Mover»"
        for _ in range(TIQUES):
            cena = bancada.cena()
            assert cena["aberto"] == id_da_tela(destino), "o «Mover» deixou o destino fechado"
        (linha,) = [a for a in cena["aparelhos"] if a.get("esperando")]
        assert linha["lugar"] == id_da_tela(destino)

        outra = next(a for a in TRES if a != destino)
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(outra))
        abertos = [bancada.cena()["aberto"] for _ in range(TIQUES)]
        assert abertos == [id_da_tela(outra)] * TIQUES, "a espera do «Mover» desfez o clique dela"
    finally:
        busca.soltar()
        bancada.fechar()


def test_a_escolha_de_um_adaptador_que_saiu_nao_segura_a_caixa(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A caixa que ela abriu era a de um adaptador que saiu da máquina: aquela
    escolha não é sobre as caixas de agora, e a busca que começa abre a dela
    (a regra de sem escolha). Quando ele volta, a escolha dela volta junto.

    MORDIDA: faça o ``_o_aberto`` devolver o ``_ABERTO`` sem conferir que o
    adaptador está na lista — nenhuma caixa abre, e esta régua reprova.
    """
    mundo, relogio = mundo_com((SALA, QUARTO)), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio, ordem=(SALA, QUARTO))
    busca = BuscaDePe(relogio)
    try:
        bancada.cena()
        a08._ABERTO["lugar"] = id_da_tela(VARANDA)
        bancada.central.comecar_a_conectar(QUARTO)
        assert busca.dentro.wait(5.0)
        for _ in range(TIQUES):
            assert bancada.cena()["aberto"] == id_da_tela(QUARTO)
    finally:
        busca.soltar()
        bancada.fechar()
