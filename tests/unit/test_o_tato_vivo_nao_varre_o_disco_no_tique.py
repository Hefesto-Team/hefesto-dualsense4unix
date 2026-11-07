"""O tato vivo não varre o disco no tique (O-TATO-VIVO-NAO-VARRE-O-DISCO-NO-TIQUE-01).

``ha_jogo``, a pergunta de 60 Hz do tato e da luz, lê o último caderno pronto, e a assinatura
e a releitura correm num relógio lento, em fio próprio.

Mordidas (arranque a cura, veja reprovar, devolva):

- `_caderno_das_janelas` sempre por `_reler_o_caderno`: a assinatura volta ao tique;
- `teto.estourou` nunca posto: o caderno de leitura pela metade substitui o anterior;
- `ler_por_processo` com o `leitor.prazo_s` inteiro: seis leitores passam do teto.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.subsystems import luz_animada, tato_vivo
from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.integrations import jogos_locais as jl

CLASSE = "jogo-de-fora"
HERTZ = 240
TETO_DA_PERGUNTA_S = 0.02


def _jogo(chave: str = CLASSE) -> jl.JogoLocal:
    return jl.JogoLocal(appid="", nome="Jogo de Fora", fonte="heroic", lancador="Heroic",
                        chave=chave)


def _daemon(classe: str = CLASSE) -> Any:
    daemon = SimpleNamespace(
        display_authority="desktop",
        store=SimpleNamespace(window_detect_current_class=classe),
    )
    daemon._janela_de_jogo_em_foco = MethodType(Daemon._janela_de_jogo_em_foco, daemon)
    return daemon


@pytest.fixture(autouse=True)
def _caderno_limpo(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(jl, "_NOMES_DAS_JANELAS", None)
    monkeypatch.setattr(jl, "_relendo", False)
    monkeypatch.setattr(jl, "_relido_em", float("-inf"))
    monkeypatch.setattr(jl, "_assinatura_que_estourou", None)
    yield
    prazo = time.monotonic() + 8.0
    while jl._relendo and time.monotonic() < prazo:
        time.sleep(0.01)


def _esperar_a_releitura(prazo_s: float = 8.0) -> None:
    fim = time.monotonic() + prazo_s
    while jl._relendo:
        assert time.monotonic() < fim, "a releitura de fundo não terminou"
        time.sleep(0.01)


def _perguntar(daemon: Any, segundos: float, *, jogo_de: Any = tato_vivo.ha_jogo) -> list[bool]:
    """A pergunta do tique no fio do laço, por ``segundos``, sem deixar o relógio parar."""

    async def corpo() -> list[bool]:
        respostas: list[bool] = []
        fim = time.monotonic() + segundos
        while time.monotonic() < fim:
            antes = time.perf_counter()
            respostas.append(jogo_de(daemon))
            assert time.perf_counter() - antes < TETO_DA_PERGUNTA_S, "a pergunta esperou o disco"
            await asyncio.sleep(1 / HERTZ)
        return respostas

    return asyncio.run(corpo())


def test_a_assinatura_roda_no_relogio_lento_e_fora_do_fio_do_laco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Um segundo de perguntas a 240 Hz: no máximo uma assinatura por relógio, e fora do laço.

    MORDIDA: faça `_caderno_das_janelas` sempre chamar `_reler_o_caderno`.
    """
    monkeypatch.setattr(jl, "RELOGIO_DO_CADERNO_S", 0.2)
    fios: list[str] = []

    def assinar(*_a: Any, **_k: Any) -> tuple[object, ...]:
        fios.append(threading.current_thread().name)
        return ("a mesma",)

    monkeypatch.setattr(jl, "assinatura_das_janelas", assinar)
    jl._publicar_o_caderno(("a mesma",), [_jogo()])

    respostas = _perguntar(_daemon(), 1.0)

    assert len(respostas) >= 100, "o laço parou"
    assert all(respostas)
    assert 1 <= len(fios) <= 6, fios
    assert set(fios) == {"hefesto-caderno-das-janelas"}, fios


def test_a_resposta_segue_certa_com_a_janela_mudando() -> None:
    jl._publicar_o_caderno(("x",), [_jogo()])
    daemon = _daemon("firefox")

    async def corpo() -> list[bool]:
        vistas = [tato_vivo.ha_jogo(daemon)]
        daemon.store.window_detect_current_class = CLASSE.upper()
        vistas.append(tato_vivo.ha_jogo(daemon))
        daemon.store.window_detect_current_class = "steam_app_123"
        vistas.append(tato_vivo.ha_jogo(daemon))
        daemon.store.window_detect_current_class = "firefox"
        vistas.append(tato_vivo.ha_jogo(daemon))
        daemon.display_authority = "game"
        vistas.append(tato_vivo.ha_jogo(daemon))
        return vistas

    assert asyncio.run(corpo()) == [False, True, True, False, True]


def test_a_biblioteca_nova_entra_no_relogio_seguinte(monkeypatch: pytest.MonkeyPatch) -> None:
    """A resposta anda sozinha: o jogo instalado agora vira jogo sem ninguém reler à mão."""
    monkeypatch.setattr(jl, "RELOGIO_DO_CADERNO_S", 0.05)
    monkeypatch.setattr(jl, "assinatura_das_janelas", lambda *_a, **_k: ("nova",))
    monkeypatch.setattr(jl, "jogos_com_janela", lambda *_a, **_k: [_jogo("instalado-agora")])
    jl._publicar_o_caderno(("velha",), [_jogo()])

    respostas = _perguntar(_daemon("instalado-agora"), 0.4)

    assert respostas[0] is False and respostas[-1] is True, respostas


def test_leitor_preso_nao_para_a_pergunta_e_o_caderno_anterior_responde(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Os dois laços, tato e luz, perguntam com a releitura presa: responde o caderno anterior.

    MORDIDA: devolva a releitura ao fio do laço em `_caderno_das_janelas`.
    """
    monkeypatch.setattr(jl, "RELOGIO_DO_CADERNO_S", 0.05)
    monkeypatch.setattr(jl, "assinatura_das_janelas", lambda *_a, **_k: ("nova",))
    solta = threading.Event()
    releu: list[str] = []

    def ler_preso(*_a: Any, **_k: Any) -> list[jl.JogoLocal]:
        releu.append(threading.current_thread().name)
        solta.wait(5.0)
        return []

    monkeypatch.setattr(jl, "jogos_com_janela", ler_preso)
    jl._publicar_o_caderno(("velha",), [_jogo()])
    daemon = _daemon()

    try:
        do_tato = _perguntar(daemon, 0.3, jogo_de=tato_vivo.ha_jogo)
        da_luz = _perguntar(daemon, 0.3, jogo_de=luz_animada.ha_jogo)
    finally:
        solta.set()

    assert all(do_tato) and all(da_luz)
    assert releu == ["hefesto-caderno-das-janelas"], releu


def _leitores_presos(tmp_path: Path, quantos: int) -> list[censo.LeitorPorProcesso]:
    pasta = tmp_path / "leitor"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "ler.py").write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    return [censo.LeitorPorProcesso(f"m{i}", f"M{i}", (sys.executable, "ler.py"), pasta, 5.0, "")
            for i in range(quantos)]


def test_seis_leitores_presos_terminam_dentro_do_teto_conjunto(tmp_path: Path) -> None:
    """Prazo de 5 s cada e sem teto seriam 30 s; o teto é um só para os seis.

    MORDIDA: leia com `leitor.prazo_s` em vez do resto do teto, e a régua espera 30 s.
    """
    leitores = _leitores_presos(tmp_path, 6)
    inicio = time.monotonic()

    with censo.teto_conjunto(0.6) as teto:
        lidas = [censo.ler_por_processo(leitor, bwrap=False) for leitor in leitores]

    assert time.monotonic() - inicio < 2.0
    assert teto.estourou
    assert all(lida.estado == censo.ILEGIVEL for lida in lidas), lidas


def test_fora_do_teto_o_leitor_segue_com_o_prazo_dele(tmp_path: Path) -> None:
    leitor = _leitores_presos(tmp_path, 1)[0]
    leitor = censo.LeitorPorProcesso("m", "M", leitor.comando, leitor.pasta, 0.3, "")

    lida = censo.ler_por_processo(leitor, bwrap=False)

    assert lida.estado == censo.ILEGIVEL and "0.3 s" in lida.erros[0], lida


def test_teto_estourado_deixa_o_caderno_anterior_e_nao_insiste(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A leitura pela metade não vira caderno, e a mesma assinatura não refaz a espera.

    MORDIDA: tire o `teto.estourou = True` de `ler_por_processo`.
    """
    monkeypatch.setattr(jl, "RELOGIO_DO_CADERNO_S", 0.0)
    monkeypatch.setattr(jl, "TETO_DA_RELEITURA_S", 0.2)
    monkeypatch.setattr(jl, "assinatura_das_janelas", lambda *_a, **_k: ("nova",))
    leitores = _leitores_presos(tmp_path, 2)
    voltas: list[int] = []

    def ler(*_a: Any, **_k: Any) -> list[jl.JogoLocal]:
        voltas.append(1)
        for leitor in leitores:
            censo.ler_por_processo(leitor, bwrap=False)
        return []

    monkeypatch.setattr(jl, "jogos_com_janela", ler)
    jl._publicar_o_caderno(("velha",), [_jogo()])

    jl._pedir_a_releitura()
    _esperar_a_releitura()
    jl._pedir_a_releitura()
    _esperar_a_releitura()

    assert voltas == [1], "a mesma assinatura estourada voltou a esperar"
    assert jl.jogos_de_janela() == [_jogo()], "o caderno anterior não ficou valendo"
    assert jl._NOMES_DAS_JANELAS is not None and jl._NOMES_DAS_JANELAS[0] == ("velha",)


def test_quem_chega_antes_do_primeiro_caderno_no_laco_nao_espera(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No laço, sem caderno, a resposta é «ainda não» e a leitura vai a um fio próprio."""
    solta = threading.Event()
    monkeypatch.setattr(jl, "assinatura_das_janelas", lambda *_a, **_k: ("nova",))
    monkeypatch.setattr(jl, "jogos_com_janela", lambda *_a, **_k: [solta.wait(5.0), _jogo()][1:])

    respostas = _perguntar(_daemon(), 0.1)
    solta.set()
    _esperar_a_releitura()

    assert not any(respostas)
    assert jl.jogos_de_janela() == [_jogo()]


def test_quem_nomeia_o_lar_le_na_hora(tmp_path: Path) -> None:
    """A interface que pede um lar específico quer aquela leitura, na hora."""
    assert jl.jogos_de_janela(lar=tmp_path, pastas=[tmp_path]) == []


@pytest.mark.parametrize("modo", ["xbox", "dualsense"])
@pytest.mark.parametrize(
    "mesa",
    [
        ("usb", "usb", "usb", "bt"),
        ("usb", "bt", "bt", "bt"),
        ("usb", "usb", "bt", "bt"),
    ],
    ids=["3-cabos-1-radio", "1-cabo-3-radios", "2-e-2"],
)
def test_ha_jogo_e_a_mesma_resposta_para_o_tato_de_cada_um(
    mesa: tuple[str, ...], modo: str,
) -> None:
    """A pergunta é do daemon, não de um jogador: os quatro leem a mesma, em qualquer posição."""
    jl._publicar_o_caderno(("x",), [_jogo()])
    daemon = _daemon()
    controles = [
        tato_vivo.Controle(f"aa:bb:cc:00:00:0{n}", SimpleNamespace(flavor=modo, transporte=meio))
        for n, meio in enumerate(mesa, start=1)
    ]

    async def corpo() -> list[bool]:
        jogo = tato_vivo.ha_jogo(daemon)
        return [tato_vivo.estado_do_controle(c, jogo).ha_jogo for c in controles]

    assert asyncio.run(corpo()) == [True] * 4
