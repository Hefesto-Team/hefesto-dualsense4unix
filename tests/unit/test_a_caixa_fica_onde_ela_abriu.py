"""A caixa fica onde ela abriu — A-CAIXA-FICA-ONDE-ELA-ABRIU-01 (item 2 da auditoria de 26/09)."""

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
    Bancada,
    BuscaDePe,
    id_da_tela,
    onde_buscou,
    preparar_a_tela,
    preparar_o_diario,
)

CHIP = re.compile(r'<button class="op" aria-pressed="(true|false)"[^>]*'
                  r'data-gesto="escolher-adaptador" data-alvo="([0-9A-F]{12})"')
TRES = (SALA, QUARTO, VARANDA)
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
    """O caminho dela: o chip do destino, e o «Procurar» — a janela abre ali."""
    bancada.cena()
    bancada.gesto("escolher-adaptador", alvo=id_da_tela(destino))
    bancada.cena()
    assert bancada.gesto("radio-procurar") == {"armou": True}
    assert busca.dentro.wait(5.0), "a central não abriu a janela"
    (movimento,) = bancada.central.movimentos()
    assert (movimento.estado, movimento.passo, movimento.destino) == (
        cr.ESPERANDO, cr.PASSO_GESTO, destino)


CARTAO = re.compile(r'<div class="lugar[" ]')


def _cartao(sala: str, lid: str) -> str:
    """O cartão inteiro de um adaptador no HTML da sala."""
    comecos = [m.start() for m in CARTAO.finditer(sala)]
    inicio = max(c for c in comecos if c < sala.index(f'data-id="{lid}"'))
    fim = next((c for c in comecos if c > inicio), len(sala))
    return sala[inicio:fim]


@pytest.mark.parametrize("ordem", [TRES, (VARANDA, SALA, QUARTO), (QUARTO, VARANDA, SALA)])
def test_a_ordem_da_lista_nao_muda_o_dono(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, ordem: tuple[str, ...],
) -> None:
    """O dono é o clique, e não a posição: a busca no primeiro da lista e o"""
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


@pytest.mark.parametrize("onde_busca", TRES)
def test_sem_escolha_dela_a_caixa_da_busca_abre(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde_busca: str,
) -> None:
    """A busca que não nasceu de um clique na tela (o ``_ABERTO`` vazio): a"""
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
        classes = cartao.split('"', 2)[1].split()
        assert "aberto" in classes and "buscando" in classes and "Segure PS + Create" in cartao
    finally:
        busca.soltar()
        bancada.fechar()


@pytest.mark.parametrize("onde_busca", TRES)
def test_ela_fecha_a_caixa_da_busca_e_a_espera_fica_no_cabecalho(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde_busca: str,
) -> None:
    """Fechar a caixa da busca é escolha dela («nenhuma aberta»): nenhuma abre"""
    mundo, relogio = mundo_com(TRES), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    busca = BuscaDePe(relogio)
    try:
        _a_busca_abre_em(bancada, busca, onde_busca)
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(onde_busca))
        for _ in range(TIQUES):
            assert bancada.cena()["aberto"] is None, "a caixa da busca abriu por cima dela"
        campos = bancada.tique()
        cartao = _cartao(campos["radio-sala"], id_da_tela(onde_busca))
        classes = cartao.split('"', 2)[1].split()
        assert "aberto" not in classes and "buscando" in classes
        topo = cartao[:cartao.index('<div class="aparelhos"')]
        assert '<span class="espera busca"' in topo and "Segure PS + Create" in topo
        ids = [lug["id"] for lug in a08._CENA_NA_TELA["lugares"]]
        assert campos["radio-conectando"] == [
            "sim" if lid == id_da_tela(onde_busca) else "" for lid in ids]
    finally:
        busca.soltar()
        bancada.fechar()


@pytest.mark.parametrize("quantos", [2, 3])
def test_com_dois_ou_tres_adaptadores_o_clique_dela_fica(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, quantos: int,
) -> None:
    """Com dois ou três adaptadores o dono é o mesmo; com UM, a caixa única fica"""
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


@pytest.mark.parametrize(("onde_busca", "chip"), PARES)
def test_o_chip_de_outro_adaptador_pede_a_busca_ao_radio(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, onde_busca: str, chip: str,
) -> None:
    """Com a busca de pé, o chip de outro adaptador manda o ``radio.mover`` para"""
    mundo, relogio = mundo_com(TRES), rm.Relogio()
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    busca = BuscaDePe(relogio)
    try:
        _a_busca_abre_em(bancada, busca, onde_busca)
        bancada.cena()
        assert bancada.gesto("escolher-adaptador", alvo=id_da_tela(onde_busca)) == {
            "armou": True}
        assert len(bancada.ponte.chamadas) == 1, "o chip da busca pediu ao rádio"

        assert bancada.gesto("escolher-adaptador", alvo=id_da_tela(chip)) == {"armou": True}
        assert bancada.ponte.chamadas == [
            ("radio.busca.set", {"ligada": True, "destino": id_da_tela(onde_busca)}),
            ("radio.mover", {"destino": id_da_tela(chip)}),
        ], "o chip recusou sem perguntar ao rádio"
        assert a08._ABERTO["lugar"] == id_da_tela(chip)

        busca.soltar()
        bancada.esperar_a_central()
        assert onde_buscou(mundo) == [rm.HCIS[onde_busca], rm.HCIS[chip]]
        (movimento,) = bancada.central.movimentos()
        assert movimento.destino == chip
        cena = bancada.cena()
        assert cena["aberto"] == cena["destino_do_conectar"] == id_da_tela(chip)
    finally:
        busca.soltar()
        bancada.fechar()


class PonteQueAceita:
    """A resposta da central que MUDA a busca de adaptador — o ``ok`` do"""

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
    """Quando a central aceita, o chip é um gesto só, sem recusa: a caixa e o"""
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
    """A caixa aberta é dela, e o chip aceso do «Procurando» é do rádio: com a"""
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
    """Na tela, o pareamento sai por UM caminho: o X dela («Esquecer» da"""
    assert _quem_chama("_esquecer_o_pareamento") == {("a08_conexoes.py", "confirmar_esquecer")}
    assert _quem_chama("esquecer_o_pareamento") == {("a08_conexoes.py", "_esquecer_o_pareamento")}


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
    """Com o piloto no ar, o chip clicado não acende na página: quem acende é o"""
    fora = chip_no_webkit
    assert len(fora["no_molde"]) == 1
    assert fora["sem_piloto"] == [fora["clicado_sem_piloto"]], "o desenho perdeu o clique"
    assert fora["com_piloto"] == fora["no_molde"], "o chip acendeu antes do rádio responder"


MOVER = [(destino, dela) for destino in (QUARTO, VARANDA) for dela in TRES if dela != destino]


@pytest.mark.parametrize(("destino", "dela"), MOVER)
def test_o_mover_abre_a_caixa_do_destino_e_o_clique_seguinte_dela_fica(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, destino: str, dela: str,
) -> None:
    """O «Mover» (a pergunta da mudança, ``confirmar-mudanca``) é um clique dela"""
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
    """A caixa que ela abriu era a de um adaptador que saiu da máquina: aquela"""
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
