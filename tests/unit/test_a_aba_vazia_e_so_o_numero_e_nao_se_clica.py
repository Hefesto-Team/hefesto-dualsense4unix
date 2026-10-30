"""A-ABA-VAZIA-E-SO-O-NUMERO-E-NAO-SE-CLICA-01 — a aba de um lugar vazio é só o número.

Desde a D-2910-OS-QUATRO-LUGARES-TEM-ABA-NA-JOGAR, as quatro abas ficam à vista na Jogar. O usuário
escolheu no chat, em 29/10/2026, «Vazias pequenas, sem clique»: a aba de um lugar sem controle é só
o disco do número, apagado e estreito, sem «Desconectado», e o clique nela não abre nada. Quando
um controle chega ao lugar, a aba fica cheia no tique seguinte; quando sai, encolhe, e se era a
aberta a aberta passa ao primeiro conectado.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("o hefesto_vivo importa o GTK e o WebKit")

from hefesto_dualsense4unix.interface import pacotes  # isort:skip
from hefesto_dualsense4unix.interface import hefesto_vivo, monta, onde
from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

from tests.conftest import skip_sem_gi_real

RAIZ = pathlib.Path(__file__).resolve().parents[2]

JOGAR = onde.BANCADA / "01-jogar.html"

MESA_DE_DOIS = [{"pref": "p1", "uniq": "aa:bb:cc:00:00:01"},
                {"pref": "p2", "uniq": "aa:bb:cc:00:00:02"}]

ABA = re.compile(r'<label class="aba-ctl( off)?"([^>]*)>(.*?)</label>', re.S)


class _ServicoQueNaoSeChama:
    def __getattr__(self, nome: str) -> Any:
        raise AssertionError(f"o gesto do lugar vazio falou com o serviço ({nome})")


def _ctx() -> pacotes.Contexto:
    return pacotes.Contexto(state={"controllers": MESA_DE_DOIS}, mesa=MESA_DE_DOIS,
                            conectados=MESA_DE_DOIS)


def test_o_pref_que_nao_esta_na_mesa_recusa_sem_servico(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com dois controles, o P4 que chegasse ao gesto recusa, sem IPC e sem mudar a escolha.

    Nenhum clique o alcança: a aba vazia não tem gesto. D-2910-A-ABA-VAZIA-E-SO-O-NUMERO.
    """
    monkeypatch.setattr(hefesto_vivo.ESCOLHA_DA_FITA, "uniq", "aa:bb:cc:00:00:02")
    for pref in ("p4", "p9"):
        with pytest.raises(ValueError, match="não está na mesa"):
            hefesto_vivo._escolher_na_fita(_ctx(), {"pref": pref}, _ServicoQueNaoSeChama())
    assert hefesto_vivo.ESCOLHA_DA_FITA.uniq == "aa:bb:cc:00:00:02"


def test_o_desenho_e_o_tique_dao_so_o_numero_ao_lugar_vazio() -> None:
    """No desenho, a aba vazia não tem `for` nem gesto, tem `aria-disabled`, e o único texto é
    o número; o tique escreve nome, via e dica vazios, sem «Desconectado».

    D-2910-A-ABA-VAZIA-E-SO-O-NUMERO.
    """
    corpo = JOGAR.read_text(encoding="utf-8").split("<body", 1)[1]
    abas = ABA.findall(corpo)
    assert len(abas) == len(monta.MESA)
    vazios = {c["pref"] for c in monta.MESA if not c.get("conectado", True)}
    assert vazios, "o desenho perdeu o lugar vazio que esta régua mede"
    for off, atributos, dentro in abas:
        pref = re.search(r'data-controle="(p\d)"', atributos).group(1)
        texto = re.sub(r"<[^>]+>", "", dentro).strip()
        if off:
            assert pref in vazios
            assert "for=" not in atributos and "data-gesto" not in atributos, atributos
            assert 'aria-disabled="true"' in atributos, atributos
            assert texto == pref[1:], f"a aba vazia {pref} diz {texto!r}"
            assert "data-dica" not in dentro.replace('data-hef-atributo="data-dica"', "")
        else:
            assert f'for="c-{pref}"' in atributos
            assert f'data-gesto="{monta.GESTO_DA_FITA}"' in atributos
            assert "aria-disabled" not in atributos
    assert a02.ABA_DO_LUGAR_VAZIO == {"aba-nome": "", "aba-via": "", "aba-dica": ""}


def test_o_bootstrap_devolve_a_aba_o_gesto_da_fita() -> None:
    """A aba que se enche ganha o gesto da fita: o nome no BOOTSTRAP é o do `monta`."""
    assert f"const GESTO_DA_ABA = '{monta.GESTO_DA_FITA}';" in hefesto_vivo.BOOTSTRAP


@pytest.fixture(scope="module")
def tela() -> Any:
    """A Jogar num WebView oculto, com o BOOTSTRAP do piloto."""
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        pytest.skip("sem servidor gráfico: rode sob `xvfb-run -a` (pulo não é verde)")
    sys.path.insert(0, str(RAIZ / "scripts"))
    import regua_de_tela

    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text(
        encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto"
    t = regua_de_tela.Tela(JOGAR, titulo_esperado="Hefesto", largura=1212, altura=809)
    t.executar(m.group(1) + ";'ok'")
    yield t
    t.fechar()


LER = r"""
(function(){
  var fora = {};
  document.querySelectorAll('.aba-ctl[data-controle]').forEach(function(a){
    var r = a.getBoundingClientRect();
    fora[a.dataset.controle] = {
      off: a.classList.contains('off'), para: a.getAttribute('for'),
      gesto: a.getAttribute('data-gesto'), desligada: a.getAttribute('aria-disabled'),
      texto: a.textContent.replace(/\s+/g, ' ').trim(), largura: Math.round(r.width),
      cursor: getComputedStyle(a).cursor,
      dica: (a.querySelector('[data-campo="aba-dica"]') || a).getAttribute('data-dica')};
  });
  var m = document.querySelector('.radio-mesa:checked');
  fora.aberta = m ? m.id : '';
  return JSON.stringify(fora);
})()
"""


def _pintar(tela: Any, prefs: list[str], alvo: str) -> dict[str, Any]:
    carga: dict[str, Any] = {"alvo": alvo, "colunas": {p: {} for p in prefs},
                             pacotes.LUGAR_VAZIO: dict(a02.ABA_DO_LUGAR_VAZIO)}
    for pref in prefs:
        carga["colunas"][pref] = {"aba-nome": f"Controle {pref[1:]}", "aba-via": "usb",
                                  "aba-dica": f"Controle {pref[1:]} · USB"}
    carga = pacotes.apagar_os_lugares_sem_dono(carga, prefs, pagina="01-jogar.html")
    tela.executar(f"(function(){{window.__hef.pintar({json.dumps(carga)});return 'ok';}})()")
    tela.avancar(hefesto_vivo.TIQUE_MS / 1000)
    return dict(json.loads(tela.executar(LER)))


def _ao_longo(tela: Any, prefs: list[str], alvo: str, segundos: float) -> list[dict[str, Any]]:
    return [_pintar(tela, prefs, alvo)
            for _tique in range(int(segundos * 1000 / hefesto_vivo.TIQUE_MS))]


def _so_o_numero(lido: dict[str, Any], pref: str) -> None:
    aba = lido[pref]
    assert aba["off"] and aba["texto"] == pref[1:], aba
    assert aba["para"] is None and aba["gesto"] is None, f"a aba vazia {pref} se clica: {aba}"
    assert aba["desligada"] == "true" and aba["cursor"] == "default" and not aba["dica"], aba
    assert aba["largura"] <= 40, f"a aba vazia {pref} não encolheu: {aba['largura']} px"


def _cheia(lido: dict[str, Any], pref: str) -> None:
    aba = lido[pref]
    assert not aba["off"] and aba["texto"] == f"{pref[1:]}Controle {pref[1:]}", aba
    assert aba["para"] == f"c-{pref}" and aba["gesto"] == monta.GESTO_DA_FITA, aba
    assert aba["desligada"] is None, aba


@skip_sem_gi_real
def test_no_tempo_a_aba_vazia_e_so_o_numero_e_o_clique_nao_a_abre(tela: Any) -> None:
    """Ao longo de segundos de tique, com dois controles: as abas 3 e 4 são só o número, sem
    `for` nem gesto, e clicá-las não muda a aberta nem manda gesto; o controle que chega ao P3
    enche a aba no tique seguinte, o clique a abre, e quando ele sai a aba encolhe e a aberta
    passa ao primeiro conectado.

    D-2910-A-ABA-VAZIA-E-SO-O-NUMERO.
    """
    dois, tres = ["p1", "p2"], ["p1", "p2", "p3"]
    lido = _pintar(tela, dois, "")
    assert lido["aberta"] == "c-p1", lido
    for pref in dois:
        _cheia(lido, pref)
    tela.limpar_recados()
    for pref in ("p3", "p4"):
        tela.clicar(f'.aba-ctl[data-controle="{pref}"]')
        for lido in _ao_longo(tela, dois, "", 1.5):
            assert lido["aberta"] == "c-p1", f"o clique no {pref} vazio abriu: {lido}"
            _so_o_numero(lido, "p3")
            _so_o_numero(lido, "p4")
    assert not tela.recados(monta.GESTO_DA_FITA), "a aba vazia mandou o gesto da fita"

    lido = _pintar(tela, tres, "")
    _cheia(lido, "p3")
    _so_o_numero(lido, "p4")
    assert lido["aberta"] == "c-p1", "o controle que chegou tomou a aba aberta sem clique"
    tela.clicar('.aba-ctl[data-controle="p3"]')
    assert {v["aberta"] for v in _ao_longo(tela, tres, "", 1.0)} == {"c-p3"}
    assert [r.objeto.get("pref") for r in tela.recados(monta.GESTO_DA_FITA)] == ["p3"]

    lido = _pintar(tela, dois, "")
    _so_o_numero(lido, "p3")
    assert lido["aberta"] == "c-p1", f"o P3 aberto saiu e a aberta não passou ao P1: {lido}"
    for lido in _ao_longo(tela, dois, "", 1.0):
        assert lido["aberta"] == "c-p1"
        _so_o_numero(lido, "p3")
