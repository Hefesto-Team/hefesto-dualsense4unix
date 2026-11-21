"""O-MAPA-DO-CONTROLE-DIZ-DE-QUEM-E-CADA-TROCA-01: o «Vale para» e o «Usar em» dizem a verdade.

Com a fita em «Todos» os chips acendem todos e o dono da troca é o perfil; com um controle
escolhido, acende ele e o dono é ele. A tecla e o mouse vão ao perfil, a troca ao controle. O
clique que mudaria o dono com edição por guardar recusa dizendo, em vez de largar a edição. O jogo
da Steam aparece pelo nome, com o número na dica.

A mordida de cada cura: voltar a `ativo == pref` cru reprova os de chips; tirar o gesto da fita do
mapa reprova os de recusa; voltar ao `simple_extra` cru reprova os do nome do jogo.
"""
from __future__ import annotations

import pathlib
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.integrations import steam_launch_options
from hefesto_dualsense4unix.interface.pacotes import GESTOS, Contexto
from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MACS = ("aabbcc000001", "aabbcc000002", "aabbcc000003", "aabbcc000004")
NOMES = ("Cosmic Red", "Starlight Blue", "Galactic Purple", "White")
CORES = ("cosmic-red", "starlight-blue", "galactic-purple", "white")
NOME = "Regua"


def _ctx(controles: int, escolhido: str) -> Any:
    def uniq(n: int) -> str:
        return ":".join(MACS[n][i:i + 2] for i in range(0, 12, 2))

    mesa: list[dict[str, Any]] = [
        {"pref": f"p{n + 1}", "uniq": uniq(n), "nome": NOMES[n],
         "via": "USB" if n % 2 == 0 else "BT", "jogador": n + 1, "cor": CORES[n]}
        for n in range(controles)]
    conectados: list[dict[str, Any]] = [
        {"uniq": m["uniq"], "inputs": {"buttons": []}} for m in mesa]
    return Contexto(state={"active_profile": NOME}, mesa=mesa, conectados=conectados,
                    escolhido=escolhido)


@pytest.fixture
def mapa() -> Any:
    a13._largar()
    yield a13
    a13._largar()


def _perfil_no_disco(**campos: Any) -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile

    loader.save_profile(Profile(name=NOME, match=MatchManual(), **campos))


def _acesos(html_dos_chips: str) -> list[bool]:
    import re

    return [" on" in marca for marca in re.findall(r'<button class="chip plastico([^"]*)"',
                                                   html_dos_chips)]


@pytest.mark.parametrize("controles", [2, 4])
def test_com_a_fita_em_todos_todos_os_chips_acendem_e_o_dono_e_o_perfil(
        mapa: Any, controles: int) -> None:
    _perfil_no_disco()
    ctx = _ctx(controles, "todos")

    blocos = mapa.pacote(ctx)["blocos"][mapa.BLOCO_DOS_CONTROLES]

    assert _acesos(blocos) == [True] * controles
    assert mapa._peca_do_vale_para(ctx) is None


@pytest.mark.parametrize("controles", [2, 4])
def test_com_um_controle_escolhido_so_ele_acende_e_e_o_dono(mapa: Any, controles: int) -> None:
    _perfil_no_disco()
    ctx = _ctx(controles, "p2")

    blocos = mapa.pacote(ctx)["blocos"][mapa.BLOCO_DOS_CONTROLES]

    assert _acesos(blocos) == [n == 1 for n in range(controles)]
    assert mapa._peca_do_vale_para(ctx) == MACS[1]


def test_a_tecla_vai_ao_perfil_inteiro_e_a_troca_ao_controle_escolhido(mapa: Any) -> None:
    from hefesto_dualsense4unix.profiles import loader

    _perfil_no_disco()
    ctx = _ctx(4, "p3")
    mapa.mapa_botao(ctx, {"b": "square"}, None)
    mapa.mapa_escolher(ctx, {"v": "troca:circle"}, None)
    mapa.mapa_botao(ctx, {"b": "triangle"}, None)
    mapa.mapa_escolher(ctx, {"v": "acao:KEY_SPACE"}, None)  # (noqa-acento)
    mapa.mapa_guardar(ctx, {}, MagicMock())

    gravado = loader.load_profile(NOME)

    assert gravado.button_actions == {"triangle": "KEY_SPACE"}
    assert gravado.remapeamento is None
    assert gravado.controllers is not None and set(gravado.controllers) == {MACS[2]}
    assert gravado.controllers[MACS[2]].remapeamento == {"square": "circle"}


def test_o_chip_com_troca_por_guardar_avisa_na_dica_e_o_dono_nao(mapa: Any) -> None:
    _perfil_no_disco()
    ctx = _ctx(2, "p1")
    mapa.mapa_botao(ctx, {"b": "square"}, None)
    mapa.mapa_escolher(ctx, {"v": "troca:circle"}, None)

    blocos = mapa.pacote(ctx)["blocos"][mapa.BLOCO_DOS_CONTROLES]

    dono, outro = blocos.split("<button")[1:]
    assert mapa.AVISO_DO_DONO not in dono
    assert mapa.AVISO_DO_DONO in outro


def test_sem_troca_por_guardar_nenhum_chip_avisa(mapa: Any) -> None:
    _perfil_no_disco()

    blocos = mapa.pacote(_ctx(2, "p1"))["blocos"][mapa.BLOCO_DOS_CONTROLES]

    assert mapa.AVISO_DO_DONO not in blocos


@pytest.fixture
def fita_das_abas(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    escolhidos: list[str] = []

    def escolher(ctx: Any, o: dict[str, Any], ipc: Any) -> dict[str, Any]:
        escolhidos.append(str(o.get("pref")))
        return {}

    monkeypatch.setitem(GESTOS, ("*", a13.GESTO_DA_FITA), escolher)
    return escolhidos


def test_o_gesto_do_chip_e_o_da_fita_que_a_monta_declara() -> None:
    import monta

    assert a13.GESTO_DA_FITA == monta.GESTO_DA_FITA


def test_escolher_outro_controle_com_troca_por_guardar_recusa_e_guarda_a_edicao(
        mapa: Any, fita_das_abas: list[str]) -> None:
    _perfil_no_disco()
    ctx = _ctx(2, "p1")
    mapa.pacote(ctx)
    mapa.mapa_botao(ctx, {"b": "square"}, None)
    mapa.mapa_escolher(ctx, {"v": "troca:circle"}, None)

    with pytest.raises(RuntimeError, match="Guarde ou cancele"):
        GESTOS[(mapa.PAGINA, a13.GESTO_DA_FITA)](ctx, {"pref": "p2"}, None)

    assert fita_das_abas == []
    assert mapa._estado()["edicoes"], "a edição que não se guardou foi largada"


def test_escolher_o_mesmo_controle_ou_sem_edicao_segue_o_gesto_da_fita(
        mapa: Any, fita_das_abas: list[str]) -> None:
    _perfil_no_disco()
    ctx = _ctx(2, "p1")
    mapa.pacote(ctx)
    GESTOS[(mapa.PAGINA, a13.GESTO_DA_FITA)](ctx, {"pref": "p2"}, None)
    mapa.mapa_botao(ctx, {"b": "square"}, None)
    mapa.mapa_escolher(ctx, {"v": "troca:circle"}, None)
    GESTOS[(mapa.PAGINA, a13.GESTO_DA_FITA)](ctx, {"pref": "p1"}, None)

    assert fita_das_abas == ["p2", "p1"]


def _perfil_de_jogo(appid: str) -> Any:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import Profile
    from hefesto_dualsense4unix.profiles.simple_match import from_simple_choice

    loader.save_profile(Profile(name=NOME, match=from_simple_choice("steam_game", appid),
                                button_actions={"cross": "KEY_ENTER"}))
    return _ctx(2, "todos")


def test_usar_em_mostra_o_nome_do_jogo_e_o_numero_na_dica(
        mapa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(steam_launch_options, "nome_do_appid",
                        lambda appid, home=None: {"2527500": "MiSide"}.get(appid))
    ctx = _perfil_de_jogo("2527500")
    mapa._estado()["chave"] = f"{mapa.PERFIL}{NOME}"

    usar_em = mapa._usar_em(ctx, mapa._estado())

    assert 'data-dica="Steam 2527500">MiSide</span>' in usar_em
    assert ">2527500<" not in usar_em


def test_usar_em_com_jogo_sem_nome_mostra_o_numero(
        mapa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(steam_launch_options, "nome_do_appid", lambda appid, home=None: None)
    ctx = _perfil_de_jogo("9900480")
    mapa._estado()["chave"] = f"{mapa.PERFIL}{NOME}"

    usar_em = mapa._usar_em(ctx, mapa._estado())

    assert '<span class="jogo">9900480</span>' in usar_em


def test_usar_em_nao_muda_o_que_se_grava_no_perfil(
        mapa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.simple_match import simple_extra

    monkeypatch.setattr(steam_launch_options, "nome_do_appid",
                        lambda appid, home=None: "MiSide")
    ctx = _perfil_de_jogo("2527500")
    mapa._estado()["chave"] = f"{mapa.PERFIL}{NOME}"
    mapa._usar_em(ctx, mapa._estado())

    assert simple_extra(loader.load_profile(NOME).match) == "2527500"


def test_o_desenho_nao_afirma_que_cada_controle_guarda_o_seu() -> None:
    texto = (RAIZ / "mockup" / "mapa-do-controle.html").read_text(encoding="utf-8")

    assert "cada controle guarda o seu" not in texto
    assert "A tecla e o mouse valem para todos, pelo perfil." in texto
    assert texto.count('class="chip plastico on"') == 4


def test_o_clique_no_chip_nao_acende_o_que_o_pacote_nao_pintou() -> None:
    """D-2909-O-SELECIONAR-ACENDE-QUEM-ESTA-ESCOLHIDO: só o pacote acende o chip do mapa."""
    chrome = pathlib.Path("/usr/bin/google-chrome")
    if not chrome.exists():
        pytest.skip("sem o Chrome do sistema")
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(chrome), args=["--no-sandbox"])
        pg = nav.new_page(viewport={"width": 1212, "height": 809})
        pg.goto((RAIZ / "mockup" / "mapa-do-controle.html").as_uri())
        pg.evaluate("document.querySelectorAll('.mc-chips .chip')[1].click()")
        acesos = pg.evaluate("[...document.querySelectorAll('.mc-chips .chip')]"
                             ".map(c => c.classList.contains('on'))")
        nav.close()

    assert acesos == [True] * 4, "o clique recusado apagou os chips que a fita acende"
