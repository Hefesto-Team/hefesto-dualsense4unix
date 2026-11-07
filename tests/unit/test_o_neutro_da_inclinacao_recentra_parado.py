"""O-NEUTRO-DA-INCLINACAO-RECENTRA-COM-O-CONTROLE-PARADO-01 — a peça parada não mira.

D-2909-O-CONTROLE-PARADO-NAO-INCLINA: parado por 3 s (o giro variando menos de 1,5 °/s de pico
a pico em cada eixo, e a gravidade andando menos de 2°), a mira cala; a mão que pega a devolve.
A inclinação saiu da mira em 06/11/2026 e a regra ficou, agora no giro; o «Mesmo parado» da
Calibrar nunca para.

Pura, sem aparelho: o relógio e o giro são de mentira, a 60 Hz. Endereços de rádio: a faixa
SINTÉTICA da casa (``aa:bb:cc``).
"""

from __future__ import annotations

import asyncio
import math
import random
import sys
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer

sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                       / "src" / "hefesto_dualsense4unix" / "interface"))

_P1, _P2, _P3, _P4 = (
    "aa:bb:cc:00:00:01",
    "aa:bb:cc:00:00:02",
    "aa:bb:cc:00:00:03",
    "aa:bb:cc:00:00:04",
)
_TIQUE = 1.0 / 60.0
_ESQUERDO = rot.ArranjoDeMovimento(destino=rot.DESTINO_ANALOGICO_ESQUERDO)


@pytest.fixture(autouse=True)
def _registro_limpo() -> Iterator[None]:
    REGISTRO.limpar()
    yield
    REGISTRO.limpar()


def _g(direita: float, para_tras: float = 0.0) -> tuple[float, float, float]:
    """A gravidade de um controle `direita`° de lado e `para_tras`° de frente do neutro `_g(0)`."""
    d, t = math.radians(direita), math.radians(para_tras)
    return (-math.sin(d), math.cos(d) * math.sin(t), math.cos(d) * math.cos(t))


_MAO = _g(0.0)
_MESA = _g(19.0, -14.0)


class _Corrida:
    """Uma peça sob o relógio de mentira, como o motor a chama (`gamepad.aplicar_o_movimento`)."""

    def __init__(self, uniq: str = _P2, store: Any = None, *, mesmo_parado: bool = False,
                 semente: int = 21) -> None:
        self.store = store if store is not None else SimpleNamespace()
        self.uniq = uniq
        self.t = 100.0
        self.mesmo_parado = mesmo_parado
        self._ruido = random.Random(semente)

    def tique(self, acel: tuple[float, float, float],
              giro: tuple[float, float, float]) -> bool:
        self.t += _TIQUE
        return rot.parada_agora(self.store, self.uniq, giro, acel, self.t,
                                mesmo_parado=self.mesmo_parado)

    def mesa(self, vies: tuple[float, float, float] = (0.0, 0.72, 0.0),
             ) -> tuple[float, float, float]:
        """O giro de mesa de 21/09: o viés e ±0,1 de ruído."""
        x, y, z = (v + self._ruido.uniform(-0.1, 0.1) for v in vies)
        return x, y, z

    def tremor(self) -> tuple[float, float, float]:
        """A mão: senoide de 9 Hz, ±1 °/s (pico a pico 2)."""
        s = math.sin(2 * math.pi * 9.0 * self.t)
        return (s, 0.5 * s, 0.3 * s)

    def segurar(self, acel: tuple[float, float, float], segundos: float) -> list[bool]:
        return [self.tique(acel, self.tremor()) for _ in range(round(segundos / _TIQUE))]

    def mover(self, de: tuple[float, float], para: tuple[float, float],
              graus_s: float = 80.0) -> list[bool]:
        """Leva a peça de `de` a `para` (graus de lado e de frente) a `graus_s`."""
        distancia = math.hypot(para[0] - de[0], para[1] - de[1])
        passos = max(1, math.ceil(distancia / graus_s / _TIQUE))
        saida = []
        for i in range(1, passos + 1):
            f = i / passos
            acel = _g(de[0] + (para[0] - de[0]) * f, de[1] + (para[1] - de[1]) * f)
            saida.append(self.tique(acel, (graus_s, 0.0, 0.0)))
        return saida

    def na_mesa(self, acel: tuple[float, float, float], segundos: float,
                vies: tuple[float, float, float] = (0.0, 0.72, 0.0),
                ) -> list[tuple[float, bool]]:
        """`(segundos desde o primeiro tique na mesa, parada)` de cada tique."""
        comeco = self.t + _TIQUE
        return [(self.t + _TIQUE - comeco, self.tique(acel, self.mesa(vies)))
                for _ in range(round(segundos / _TIQUE))]


def _largado_na_mesa(corrida: _Corrida, segundos: float = 3.5,
                     vies: tuple[float, float, float] = (0.0, 0.72, 0.0),
                     ) -> list[tuple[float, bool]]:
    corrida.segurar(_MAO, 1.0)
    corrida.mover((0.0, 0.0), (19.0, -14.0))
    return corrida.na_mesa(_MESA, segundos, vies)


def _parado_aos_tres(serie: list[tuple[float, bool]]) -> None:
    for s, parada in serie:
        if s <= 2.99:
            assert not parada, f"a {s:.2f} s a mira já calou"
        elif s >= 3.0 + 2 * _TIQUE:
            assert parada, f"a {s:.2f} s o controle largado segue mirando"


def test_1_o_controle_apoiado_noutro_angulo_para_aos_tres_segundos() -> None:
    """MORDIDA: o `parada_agora` sem a janela de 3 s → reprova."""
    _parado_aos_tres(_largado_na_mesa(_Corrida()))


def test_2_a_mesa_de_outro_controle_com_o_dobro_do_vies() -> None:
    """MORDIDA: medir o parado pela NORMA do giro contra 1,5 → 3,5 de norma nunca para."""
    _parado_aos_tres(_largado_na_mesa(_Corrida(), vies=(2.0, 2.0, 2.0)))


def test_3_a_mao_que_treme_nao_para() -> None:
    """MORDIDA: o limiar a 5 °/s → a mão de pico a pico 2 vira mesa e reprova."""
    corrida = _Corrida()
    assert not any(corrida.segurar(_g(20.0), 30.0)), "a mão firme virou mesa"


def test_4_o_giro_muito_lento_e_liso_nao_vira_parado() -> None:
    """MORDIDA: tirar a guarda da gravidade → o giro constante (pico a pico zero) para aos 3 s."""
    corrida = _Corrida()
    for i in range(round(25.0 / _TIQUE)):
        assert not corrida.tique(_g(0.8 * i * _TIQUE), (0.8, 0.0, 0.0)), (
            f"aos {i * _TIQUE:.1f} s o giro liso virou parado")


def test_6_a_batida_na_mesa_nao_tira_do_parado() -> None:
    """MORDIDA: sair do parado por pico de giro → a batida devolve a mira."""
    corrida = _Corrida()
    _largado_na_mesa(corrida)
    for _ in range(round(0.1 / _TIQUE)):
        assert corrida.tique(_MESA, (30.0, 0.0, 0.0)), "a batida tirou do parado"
    for _, parada in corrida.na_mesa(_MESA, 1.0):
        assert parada, "depois da batida, a peça voltou a mirar sozinha"


def test_7_a_mao_que_pega_devolve_pelo_giro_ou_pela_gravidade() -> None:
    """MORDIDA: sair só pela gravidade → quem pega sem inclinar segue calado."""
    girou = _Corrida()
    _largado_na_mesa(girou)
    pegou = [girou.tique(_MESA, (30.0, 0.0, 0.0))
             for _ in range(round(rot.TEMPO_DA_PEGADA_S / _TIQUE) + 2)]
    assert not pegou[-1], "o giro firme por 0,25 s não devolveu a mira"
    inclinou = _Corrida(semente=7)
    _largado_na_mesa(inclinou)
    assert not inclinou.mover((19.0, -14.0), (27.0, -14.0), graus_s=8.0)[-1], (
        "a gravidade andou 3° e a mira seguiu calada")


def test_9_p1_a_p4_sao_quatro_memorias() -> None:
    """MORDIDA: o estado do parado por mesa (uma chave só) → o P2 cala os outros, ou o contrário."""
    store = SimpleNamespace()
    corridas = {u: _Corrida(u, store, semente=n) for n, u in enumerate((_P1, _P2, _P3, _P4))}
    ultimo: dict[str, bool] = {}
    for _ in range(round(4.0 / _TIQUE)):
        for u, c in corridas.items():
            ultimo[u] = c.tique(_MESA, c.mesa()) if u == _P2 else c.tique(_g(20.0), c.tremor())
    assert ultimo == {_P1: False, _P2: True, _P3: False, _P4: False}


def test_o_mesmo_parado_segura_a_mira_do_controle_parado_e_so_dele() -> None:
    """MORDIDA: a regra ignorando o `mesmo_parado` → o do suporte cala aos 3 s."""
    store = SimpleNamespace()
    suporte = _Corrida(_P1, store, mesmo_parado=True)
    largado = _Corrida(_P2, store, semente=3)
    for c in (suporte, largado):
        c.segurar(_MAO, 1.0)
        c.mover((0.0, 0.0), (20.0, 0.0))
    for _ in range(round(5.0 / _TIQUE)):
        assert not suporte.tique(_g(20.0), suporte.mesa()), "o «Mesmo parado» parou"
        ultimo = largado.tique(_g(20.0), largado.mesa())
    assert ultimo, "o vizinho sem o «Mesmo parado» não parou"
    assert not rot.mira_parada(store, _P1, suporte.t)
    assert rot.mira_parada(store, _P2, largado.t)


class _Servidor:
    """O `mira.set` e o `_merge_mira` de verdade, sobre um `store` e sem perfil no disco."""

    _CAMPOS_DA_MIRA = IpcServer._CAMPOS_DA_MIRA
    _handle_mira_set = IpcServer._handle_mira_set
    _merge_mira = IpcServer._merge_mira
    _o_que_falta_ao_movimento = IpcServer._o_que_falta_ao_movimento

    def __init__(self) -> None:
        self.store = SimpleNamespace()
        self.daemon = None
        rot.definir_ativo(self.store, _ESQUERDO)

    def _uniq_do_primario(self) -> str:
        return _P1

    def _chave_de_peca_que_grava(self, uniq: str) -> str:
        return uniq.replace(":", "").lower()

    def _perfil_que_grava(self) -> None:
        return None


def test_o_state_full_diz_a_pausa(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: o `_merge_mira` sem a chave `parada` → a tela não teria o que pintar."""
    from hefesto_dualsense4unix.daemon import ipc_handlers

    servidor = _Servidor()
    p2 = _Corrida(_P2, servidor.store)
    p3 = _Corrida(_P3, servidor.store, semente=5)
    _largado_na_mesa(p2)
    p3.segurar(_MAO, 1.0)
    p3.t = p2.t
    p3.segurar(_g(20.0), _TIQUE)
    monkeypatch.setattr(ipc_handlers, "time", SimpleNamespace(monotonic=lambda: p2.t))
    entradas: list[dict[str, Any]] = [{"uniq": _P2}, {"uniq": _P3}]
    servidor._merge_mira(entradas)
    assert entradas[0]["mira"]["parada"] is True, entradas[0]["mira"]
    assert entradas[1]["mira"]["parada"] is False
    assert entradas[0]["mira"]["mesmo_parado"] is False
    corpo = asyncio.run(servidor._handle_mira_set({"uniq": _P2, "mesmo_parado": True}))
    assert corpo["status"] == "ok" and corpo["mesmo_parado"] is True
    for _ in range(round(4.0 / _TIQUE)):
        p2.mesmo_parado = True
        p2.tique(_MESA, p2.mesa())
        servidor._merge_mira(entradas)
        assert entradas[0]["mira"]["parada"] is False, "o «Mesmo parado» pausou"
    assert entradas[0]["mira"]["mesmo_parado"] is True
    with pytest.raises(ValueError, match="mesmo_parado"):
        asyncio.run(servidor._handle_mira_set({"uniq": _P2, "mesmo_parado": "sim"}))


class _Ponte:
    """A ponte de verdade (`ipc_bridge.mira_set_detalhado`), com o socket trocado."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hefesto_dualsense4unix.app import ipc_bridge

        self.pedidos: list[tuple[str, dict[str, Any]]] = []

        def _corpo(metodo: str, payload: dict[str, Any]) -> dict[str, Any]:
            self.pedidos.append((metodo, dict(payload)))
            return {"status": "ok"}

        monkeypatch.setattr(ipc_bridge, "_corpo_do_daemon", _corpo)
        self.mira_set_detalhado = ipc_bridge.mira_set_detalhado


def test_o_mesmo_parado_vai_e_volta_pela_lista(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: o valor novo fora da lista aceita pelo gesto → «não é um botão da lista»."""
    import calibrar
    from pacotes import a11_calibrar_sensores as a11

    assert calibrar._opcoes_do_segurar()[:2] == [
        (calibrar.SEMPRE, "Sempre"), (calibrar.MESMO_PARADO, "Mesmo parado")]
    for escolha, esperado in (
        (calibrar.MESMO_PARADO, {"gatilho": None, "mesmo_parado": True}),
        (calibrar.SEMPRE, {"gatilho": None, "mesmo_parado": False}),
        ("l2", {"gatilho": "l2", "mesmo_parado": False}),
    ):
        ponte = _Ponte(monkeypatch)
        a11.mira_segurar(None, {"uniq": _P3, "valor": escolha}, ponte)  # type: ignore[arg-type]
        assert ponte.pedidos == [("mira.set", {**esperado, "uniq": _P3})], (escolha, ponte.pedidos)
    for mira, lista, frase in (
        ({"gatilho": None, "mesmo_parado": True}, calibrar.MESMO_PARADO, "Mesmo parado"),
        ({"gatilho": None, "mesmo_parado": False}, calibrar.SEMPRE, "Sempre"),
        ({"gatilho": None}, calibrar.SEMPRE, "Sempre"),
    ):
        assert a11._campos_da_mira({"mira": mira})["mira-segurar"] == lista
        assert a11._o_segurar(mira) == frase


def test_o_mesmo_parado_so_vai_ao_disco_quando_escrito() -> None:
    from hefesto_dualsense4unix.profiles.schema import ProfileMovimentoConfig

    assert "mesmo_parado" not in ProfileMovimentoConfig().model_dump()
    escrito = ProfileMovimentoConfig(mesmo_parado=True)
    assert escrito.model_dump()["mesmo_parado"] is True
    assert rot.montar(escrito).mesmo_parado is True
    assert rot.arranjo_da_peca(escrito, ProfileMovimentoConfig(toque="cursor")).mesmo_parado


def test_nada_abre_na_tela_so_o_chip_apaga_pela_metade(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: a classe arrancada (o invólucro ou a regra da folha) deixa o chip aceso.

    O pacote só pinta o que a página PUBLICADA tem, e o publicado é o mockup depois do
    `--publicar` do fecho: a régua lê os endereços do MOCKUP, que é o desenho.
    """
    import re

    import aba02

    import pacotes.a02_controles as a02

    mockup = (Path(__file__).resolve().parents[2] / "mockup" / "02-controles.html").read_text(
        encoding="utf-8")
    monkeypatch.setattr(a02, "_ENDERECOS", frozenset(re.findall(r'data-campo="([^"]+)"', mockup)))

    for destino in (rot.DESTINO_ANALOGICO_ESQUERDO, rot.DESTINO_ANALOGICO_DIREITO):
        chip = aba02.chip_da_inclinacao(destino)
        assert chip.startswith(
            '<span class="pausa-da-inclinacao" data-campo="inclinacao-parada" '
            'data-hef-alvo="classe" data-hef-classe="parada" '
            f'data-hef-quando="{a02.INCLINACAO_PARADA}">'), chip
        assert "dialog" not in chip and "title=" not in chip and (
            'data-dica="' + aba02.DICA_DA_INCLINACAO[destino] + '"') in chip
    assert ".pausa-da-inclinacao.parada .chip-virtual.on>.sw{opacity:.5}" in aba02.CSS
    import pacotes

    def _ctx(**mira: Any) -> Any:
        dele = {"uniq": _P2, "transport": "bt", "connected": True, "inputs": {}, "audio": {},
                "speaker": {}, "mira": {"ligada": False, "destino": "nenhum",
                                        "inclinacao": "analogico_esquerdo", **mira}}
        return pacotes.Contexto(state={}, mesa=[], conectados=[dele], estados={})

    pintado = next(iter(a02.pacote(_ctx(parada=True))["cards"].values()))
    assert pintado["inclinacao-parada"] == a02.INCLINACAO_PARADA
    for mira in ({"parada": False}, {}):
        pintado = next(iter(a02.pacote(_ctx(**mira))["cards"].values()))
        assert pintado["inclinacao-parada"] != a02.INCLINACAO_PARADA
