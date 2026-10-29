"""A-ABA-DO-LUGAR-VAZIO-ABRE-SEM-RECUSA-01 — a aba de um lugar sem controle abre sem recusa.

Desde a D-2910-OS-QUATRO-LUGARES-TEM-ABA-NA-JOGAR, as quatro abas ficam à vista na Jogar. O clique
na aba de um lugar vazio caía no fim de `_escolher_na_fita` e levantava, dizendo que um controle
tinha saído; a aba ganhava o contorno de recusa. O gesto agora separa o lugar vazio do `pref` que
não é lugar nenhum.
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
from hefesto_dualsense4unix.interface import hefesto_vivo, monta, onde
from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

from tests.conftest import skip_sem_gi_real

RAIZ = pathlib.Path(__file__).resolve().parents[2]

MESA_DE_DOIS = [{"pref": "p1", "uniq": "aa:bb:cc:00:00:01"},
                {"pref": "p2", "uniq": "aa:bb:cc:00:00:02"}]


class _ServicoQueNaoSeChama:
    def __getattr__(self, nome: str) -> Any:
        raise AssertionError(f"o gesto do lugar vazio falou com o serviço ({nome})")


def _ctx() -> pacotes.Contexto:
    return pacotes.Contexto(state={"controllers": MESA_DE_DOIS}, mesa=MESA_DE_DOIS,
                            conectados=MESA_DE_DOIS)


def test_a_aba_do_lugar_vazio_abre_sem_recusa_e_sem_servico(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Com dois controles, o P4 devolve recado de lugar vazio, sem IPC e sem mudar a escolha.

    D-2910-A-ABA-DO-LUGAR-VAZIO-ABRE-SEM-RECUSA.
    """
    assert "p4" in [c["pref"] for c in monta.MESA]
    monkeypatch.setattr(hefesto_vivo.ESCOLHA_DA_FITA, "uniq", "aa:bb:cc:00:00:02")
    resposta = hefesto_vivo._escolher_na_fita(_ctx(), {"pref": "p4"}, _ServicoQueNaoSeChama())
    assert resposta == {"recado": "O P4 está vazio: nenhum controle neste lugar."}
    assert hefesto_vivo.ESCOLHA_DA_FITA.uniq == "aa:bb:cc:00:00:02"


def test_o_pref_que_nao_e_lugar_nenhum_continua_recusado(monkeypatch: pytest.MonkeyPatch) -> None:
    """Um `pref` fora dos quatro lugares levanta, e a escolha fica onde estava."""
    monkeypatch.setattr(hefesto_vivo.ESCOLHA_DA_FITA, "uniq", "aa:bb:cc:00:00:01")
    with pytest.raises(ValueError, match="'p9'"):
        hefesto_vivo._escolher_na_fita(_ctx(), {"pref": "p9"}, _ServicoQueNaoSeChama())
    assert hefesto_vivo.ESCOLHA_DA_FITA.uniq == "aa:bb:cc:00:00:01"


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
    t = regua_de_tela.Tela(onde.BANCADA / "01-jogar.html", titulo_esperado="Hefesto",
                           largura=1918, altura=840)
    t.executar(m.group(1) + ";'ok'")
    yield t
    t.fechar()


def _pintar(tela: Any, prefs: list[str], alvo: str) -> str:
    carga: dict[str, Any] = {"alvo": alvo, "colunas": {p: {} for p in prefs},
                             pacotes.LUGAR_VAZIO: dict(a02.ABA_DO_LUGAR_VAZIO)}
    carga = pacotes.apagar_os_lugares_sem_dono(carga, prefs, pagina="01-jogar.html")
    tela.executar(f"(function(){{window.__hef.pintar({json.dumps(carga)});return 'ok';}})()")
    tela.avancar(hefesto_vivo.TIQUE_MS / 1000)
    return str(tela.executar(
        "(function(){var m=document.querySelector('.radio-mesa:checked');"
        "return m ? m.id : '';})()"))


def _ao_longo(tela: Any, prefs: list[str], alvo: str, segundos: float) -> set[str]:
    vistas: set[str] = set()
    for _tique in range(int(segundos * 1000 / hefesto_vivo.TIQUE_MS)):
        vistas.add(_pintar(tela, prefs, alvo))
    return vistas


def _apagado(tela: Any, pref: str) -> bool:
    return str(tela.executar(
        f"(function(){{var c=document.querySelector('.ctl[data-controle=\"{pref}\"]');"
        "return String(!!(c && c.classList.contains('off')));})()")) == "true"


@skip_sem_gi_real
def test_no_tempo_a_aba_do_lugar_vazio_fica_aberta_ate_outro_clique(tela: Any) -> None:
    """Ao longo de segundos de tique, a aba do P4 vazio fica aberta; o controle que chega ao P4
    aparece nela, e quando ele sai a aba passa ao escolhido; o clique noutra aba e a saída do
    escolhido voltam à regra de sempre.

    D-2910-A-ABA-DO-LUGAR-VAZIO-ABRE-SEM-RECUSA.
    """
    dois, tres = ["p1", "p2"], ["p1", "p2", "p4"]
    assert _pintar(tela, dois, "p1") == "c-p1"
    tela.clicar('.aba-ctl[data-controle="p4"]')
    assert _ao_longo(tela, dois, "p1", 3.0) == {"c-p4"}, "o tique fechou o lugar vazio"
    assert _ao_longo(tela, tres, "p1", 1.0) == {"c-p4"}, "o controle que chegou não ficou na aba"
    assert not _apagado(tela, "p4"), "a aba do P4 não mostra o controle que chegou"
    assert _pintar(tela, dois, "p1") == "c-p1", "o controle do P4 saiu e a aba ficou presa no vazio"
    assert _ao_longo(tela, dois, "p1", 1.0) == {"c-p1"}
    tela.clicar('.aba-ctl[data-controle="p4"]')
    assert _ao_longo(tela, dois, "p1", 1.0) == {"c-p4"}
    tela.clicar('.aba-ctl[data-controle="p2"]')
    assert _ao_longo(tela, dois, "p1", 1.0) == {"c-p2"}
    assert _pintar(tela, ["p1"], "p1") == "c-p1", "o escolhido que sai não passou adiante"
