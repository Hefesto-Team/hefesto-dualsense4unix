"""O-NEUTRO-DA-INCLINACAO-RECENTRA-COM-O-CONTROLE-PARADO-01 — o controle parado não inclina.

D-2909-O-CONTROLE-PARADO-NAO-INCLINA (decidida pelo usuário no chat, 29/09 ~21h15, «Sai e
volta»; a tela, ~21h30, «Sem aviso, chip e opção»): parado por 3 s (o giro variando menos
de 1,5 °/s de pico a pico em cada eixo, e a gravidade andando menos de 2°), a inclinação
sai do analógico e o neutro da mão fica guardado; a gravidade que anda 3° a devolve. O
neutro que nasceu na mesa se reaprende quando a mão assenta, e o «Mesmo parado» da
Calibrar nunca para.

Pura, sem aparelho: o relógio e o giro são de mentira, a 60 Hz. As réguas 1 a 11 são as
da sprint, na ordem; as quatro do fim são as da resposta de produto das ~21h30. Endereços de
rádio: a faixa SINTÉTICA da casa (``aa:bb:cc``).
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
_ESQUERDO = rot.ArranjoDeMovimento(acelerometro=rot.DESTINO_ANALOGICO_ESQUERDO)


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


def _hoje(acel: tuple[float, float, float], neutro: tuple[float, float, float]) -> tuple[int, int]:
    return rot.deflexao_da_inclinacao(acel, neutro, _ESQUERDO)


class _Corrida:
    """Uma peça sob o relógio de mentira, como o motor a chama (`gamepad._a_inclinacao`)."""

    def __init__(self, uniq: str = _P2, store: Any = None, *, mesmo_parado: bool = False,
                 semente: int = 21) -> None:
        self.store = store if store is not None else SimpleNamespace()
        self.uniq = uniq
        self.t = 100.0
        self.mesmo_parado = mesmo_parado
        self._ruido = random.Random(semente)

    def tique(self, acel: tuple[float, float, float],
              giro: tuple[float, float, float] | None) -> tuple[int, int]:
        self.t += _TIQUE
        neutro = rot.neutro_da_inclinacao(self.store, self.uniq, acel, self.t, giro,
                                          mesmo_parado=self.mesmo_parado)
        parada = not rot.inclina_agora(self.store, self.uniq)
        return rot.deflexao_da_inclinacao(acel, neutro, _ESQUERDO, parada=parada)

    def mesa(self, vies: tuple[float, float, float] = (0.0, 0.72, 0.0),
             ) -> tuple[float, float, float]:
        """O giro de mesa de 21/09: o viés e ±0,1 de ruído."""
        x, y, z = (v + self._ruido.uniform(-0.1, 0.1) for v in vies)
        return x, y, z

    def tremor(self) -> tuple[float, float, float]:
        """A mão: senoide de 9 Hz, ±1 °/s (pico a pico 2)."""
        s = math.sin(2 * math.pi * 9.0 * self.t)
        return (s, 0.5 * s, 0.3 * s)

    def segurar(self, acel: tuple[float, float, float], segundos: float) -> list[tuple[int, int]]:
        return [self.tique(acel, self.tremor()) for _ in range(round(segundos / _TIQUE))]

    def mover(self, de: tuple[float, float], para: tuple[float, float], graus_s: float = 80.0,
              ) -> list[tuple[tuple[float, float, float], tuple[int, int]]]:
        """Leva a peça de `de` a `para` (graus de lado e de frente) a `graus_s`."""
        distancia = math.hypot(para[0] - de[0], para[1] - de[1])
        passos = max(1, math.ceil(distancia / graus_s / _TIQUE))
        saida = []
        for i in range(1, passos + 1):
            f = i / passos
            acel = _g(de[0] + (para[0] - de[0]) * f, de[1] + (para[1] - de[1]) * f)
            saida.append((acel, self.tique(acel, (graus_s, 0.0, 0.0))))
        return saida

    def na_mesa(self, acel: tuple[float, float, float], segundos: float,
                vies: tuple[float, float, float] = (0.0, 0.72, 0.0),
                ) -> list[tuple[float, tuple[int, int]]]:
        """`(segundos desde o primeiro tique na mesa, deflexão)` de cada tique."""
        comeco = self.t + _TIQUE
        return [(self.t + _TIQUE - comeco, self.tique(acel, self.mesa(vies)))
                for _ in range(round(segundos / _TIQUE))]


def _largado_na_mesa(corrida: _Corrida, segundos: float = 3.5,
                     vies: tuple[float, float, float] = (0.0, 0.72, 0.0),
                     ) -> list[tuple[float, tuple[int, int]]]:
    """O neutro nasce na mão (1 s de tremor), e a peça vai à mesa de 29/09."""
    corrida.segurar(_MAO, 1.0)
    corrida.mover((0.0, 0.0), (19.0, -14.0))
    return corrida.na_mesa(_MESA, segundos, vies)


def _parado_aos_tres(serie: list[tuple[float, tuple[int, int]]]) -> None:
    hoje = _hoje(_MESA, _MAO)
    assert hoje == (75, -55), f"a mesa de 29/09 não dá o esquerdo de 29/09: {hoje}"
    for s, deflexao in serie:
        if s <= 2.99:
            assert deflexao == hoje, f"a {s:.2f} s a mesa já saiu do analógico: {deflexao}"
        elif s >= 3.0 + 2 * _TIQUE:
            assert deflexao == (0, 0), (
                f"a {s:.2f} s o controle largado segue segurando o esquerdo em {deflexao}")


def test_1_o_controle_apoiado_noutro_angulo_sai_aos_tres_segundos() -> None:
    """MORDIDA: tirar o `parada` de `deflexao_da_inclinacao` → o largado segue em (+75, -55)."""
    _parado_aos_tres(_largado_na_mesa(_Corrida()))


def test_2_a_mesa_de_outro_controle_com_o_dobro_do_vies() -> None:
    """MORDIDA: medir o parado pela NORMA do giro contra 1,5 → 3,5 de norma nunca para."""
    _parado_aos_tres(_largado_na_mesa(_Corrida(), vies=(2.0, 2.0, 2.0)))


def test_3_a_inclinacao_lenta_e_firme_nao_some() -> None:
    """MORDIDA: o limiar a 5 °/s → a mão de pico a pico 2 vira mesa e reprova."""
    corrida = _Corrida()
    corrida.tique(_MAO, corrida.tremor())
    saidas: list[tuple[float, tuple[int, int]]] = []
    inicio = corrida.t
    for i in range(round(10.0 / _TIQUE)):
        angulo = 20.0 * (i + 1) * _TIQUE / 10.0
        giro = corrida.tremor()
        saidas.append((corrida.t + _TIQUE - inicio,
                       corrida.tique(_g(angulo), (giro[0] + 2.0, giro[1], giro[2]))))
    for _ in range(round(30.0 / _TIQUE)):
        d = corrida.tique(_g(20.0), corrida.tremor())
        saidas.append((corrida.t - inicio, d))
    passou = False
    for s, d in saidas:
        passou = passou or d != (0, 0)
        if passou:
            assert d != (0, 0), f"aos {s:.1f} s a inclinação firme da mão sumiu"
        if s >= 10.0 + _TIQUE:
            assert d == _hoje(_g(20.0), _MAO), f"aos {s:.1f} s, {d}: não é a de 20°"
    assert passou, "a inclinação de 20° nunca saiu da zona morta — régua cega"


def test_4_a_inclinacao_muito_lenta_e_lisa_nao_vira_parado() -> None:
    """MORDIDA: tirar a guarda da gravidade → o giro constante (pico a pico zero) para aos 3 s."""
    corrida = _Corrida()
    anterior = (0, 0)
    saiu = False
    acel = _MAO
    for i in range(round(25.0 / _TIQUE)):
        acel = _g(0.8 * i * _TIQUE)
        d = corrida.tique(acel, (0.8, 0.0, 0.0))
        if saiu:
            assert d != (0, 0) and d[0] >= anterior[0], (
                f"aos {i * _TIQUE:.1f} s a inclinação lisa voltou de {anterior} a {d}")
        saiu = saiu or d != (0, 0)
        anterior = d
    assert saiu and anterior == _hoje(acel, _MAO)


def test_5_pegar_de_volta_devolve_a_mao() -> None:
    """MORDIDA: recentrar o neutro na mesa no parado → no neutro antigo o analógico vai longe."""
    corrida = _Corrida()
    _largado_na_mesa(corrida)
    volta = corrida.mover((19.0, -14.0), (0.0, 0.0)) + corrida.mover((0.0, 0.0), (20.0, 0.0))
    devolveu = False
    for acel, d in volta:
        andou = math.degrees(math.acos(max(-1.0, min(1.0, sum(
            a * b for a, b in zip(acel, _MESA, strict=True))))))
        if andou >= rot.SAIDA_DO_PARADO_GRAUS + 0.01:
            devolveu = True
            assert d == _hoje(acel, _MAO), (
                f"a gravidade andou {andou:.1f}° e a inclinação não voltou contra a mão: {d}")
        elif andou < rot.SAIDA_DO_PARADO_GRAUS - 0.01:
            assert d == (0, 0), f"a {andou:.1f}° da mesa a peça já inclinava: {d}"
    assert devolveu
    assert corrida.tique(_MAO, corrida.tremor()) == (0, 0), "no neutro da mão, fora do centro"
    assert corrida.tique(_g(20.0), corrida.tremor()) == _hoje(_g(20.0), _MAO)


def test_6_a_batida_na_mesa_nao_tira_do_parado() -> None:
    """MORDIDA: sair do parado por pico de giro → o esquerdo vai a (+75, -55)."""
    corrida = _Corrida()
    _largado_na_mesa(corrida)
    for _ in range(round(0.1 / _TIQUE)):
        assert corrida.tique(_MESA, (30.0, 0.0, 0.0)) == (0, 0), "a batida tirou do parado"
    for _, d in corrida.na_mesa(_MESA, 1.0):
        assert d == (0, 0), "depois da batida, a peça voltou a inclinar sozinha"


def test_7_o_neutro_que_nasceu_na_mesa_se_reaprende_no_assento() -> None:
    """MORDIDA: sem o provisório → a 30° o analógico vai ao batente."""
    corrida = _Corrida()
    serie = corrida.na_mesa(_MAO, 3.2)
    assert all(d == (0, 0) for _, d in serie)
    assert rot.inclinacao_parada(corrida.store, corrida.uniq, corrida.t), "não parou aos 3 s"
    for _, d in corrida.mover((0.0, 0.0), (30.0, 0.0)):
        assert d == (0, 0), f"a mão pegando a peça de neutro provisório já inclinou: {d}"
    for d in corrida.segurar(_g(30.0), 0.6):
        assert d == (0, 0), f"a 30°, com a mão assentando, o analógico saiu do centro: {d}"
    corrida.mover((30.0, 0.0), (45.0, 0.0), graus_s=75.0)
    assert corrida.segurar(_g(45.0), 0.2)[-1] == _hoje(_g(45.0), _g(30.0)), (
        "a 45° a inclinação não é a de 15° desde a mão assentada")


def test_8_a_mao_que_para_no_neutro_nao_reaprende() -> None:
    """MORDIDA: marcar provisório em todo parado → a 20° dá zero."""
    corrida = _Corrida()
    corrida.segurar(_MAO, 1.0)
    for _, d in corrida.na_mesa(_MAO, 4.0):
        assert d == (0, 0)
    assert rot.inclinacao_parada(corrida.store, corrida.uniq, corrida.t)
    corrida.mover((0.0, 0.0), (20.0, 0.0))
    assert corrida.segurar(_g(20.0), 1.0)[-1] == _hoje(_g(20.0), _MAO), (
        "a mão que só descansou no neutro perdeu a inclinação seguinte")


def test_9_p1_a_p4_sao_quatro_memorias() -> None:
    """MORDIDA: o estado do parado por mesa (uma chave só) → o P2 cala os outros, ou o contrário."""
    store = SimpleNamespace()
    corridas = {u: _Corrida(u, store, semente=n) for n, u in enumerate((_P1, _P2, _P3, _P4))}
    for c in corridas.values():
        c.tique(_MAO, c.tremor())
    for _ in range(round(4.0 / _TIQUE)):
        for u, c in corridas.items():
            if u == _P2:
                ultimo_p2 = c.tique(_MESA, c.mesa())
            else:
                c.tique(_g(20.0), c.tremor())
    assert ultimo_p2 == (0, 0), "o P2 largado segue no analógico"
    for u in (_P1, _P3, _P4):
        c = corridas[u]
        assert c.tique(_g(20.0), c.tremor()) == _hoje(_g(20.0), _MAO), (
            f"o {u} inclinando perdeu a inclinação pelo parado do P2")


def _neutro_de_antes(dono: object, uniq: str, acel: tuple[float, float, float],
                     agora: float) -> tuple[float, float, float]:
    """A `neutro_da_inclinacao` de ba5896d78, colada aqui: a régua 10 não mede contra si."""
    if dono is None:
        return acel
    mapa = getattr(dono, "_neutro_de_antes", None)
    if not isinstance(mapa, dict):
        mapa = {}
        dono._neutro_de_antes = mapa  # type: ignore[attr-defined]
    from hefesto_dualsense4unix.core.virtual_motion import chave_de_sensor

    chave = chave_de_sensor(uniq)
    anterior = mapa.get(chave)
    if anterior is None or agora - anterior[1] > rot.SILENCIO_DA_DRENAGEM_S:
        neutro = acel
    else:
        neutro = anterior[0]
    mapa[chave] = (neutro, agora)
    return neutro


def test_10_sem_giro_e_o_hoje_byte_a_byte() -> None:
    """MORDIDA: tratar `None` como giro zero → vira parado aos 3 s e a tabela diverge."""
    store = SimpleNamespace()
    agora = 50.0
    tabela = []
    for i in range(60):
        agora += 0.6 if i == 50 else 0.08
        acel = _MAO if i == 0 or i == 50 else _g(20.0 + (i % 3) * 0.001, -3.0)
        velho = _neutro_de_antes(store, _P2, acel, agora)
        novo = rot.neutro_da_inclinacao(store, _P2, acel, agora)
        parada = not rot.inclina_agora(store, _P2)
        tabela.append((i, velho, novo, rot.deflexao_da_inclinacao(acel, velho, _ESQUERDO),
                       rot.deflexao_da_inclinacao(acel, novo, _ESQUERDO, parada=parada)))
    assert agora - 50.0 > rot.TEMPO_DO_PARADO_S + 1.0, "a tabela não cobre o parado"
    for i, velho, novo, d_velha, d_nova in tabela:
        assert novo == velho and d_nova == d_velha, (i, velho, novo, d_velha, d_nova)
    assert any(d != (0, 0) for *_, d in tabela[40:50]), "a tabela não inclina — régua cega"


@pytest.mark.parametrize("giroscopio", [True, False], ids=["giro-ligado", "giro-desligado"])
@pytest.mark.parametrize("uniq", [_P1, _P3], ids=["p1", "p3"])
def test_11_o_motor_passa_o_giro(
    monkeypatch: pytest.MonkeyPatch, uniq: str, giroscopio: bool
) -> None:
    """MORDIDA: `_a_inclinacao` sem ler o giro, ou lendo só com o giroscópio ligado → reprova."""
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    relogio = [500.0]
    monkeypatch.setattr(gp, "time", SimpleNamespace(monotonic=lambda: relogio[0]))
    monkeypatch.setattr(REGISTRO, "estado", lambda _u: SimpleNamespace(
        giroscopio=giroscopio, acelerometro=True))
    leitura: dict[str, Any] = {"acel": _MAO, "giro": (0.0, 0.0, 0.0)}

    class _Hub:
        """Tão rico quanto o `SensorHub`: os três métodos do motor."""

        def aceleracao_do_movimento(self, _u: str) -> tuple[float, float, float]:
            return leitura["acel"]

        def velocidade_do_movimento(self, _u: str) -> tuple[float, float, float]:
            return leitura["giro"]

        def angulo_do_movimento(self, _u: str) -> tuple[float, float, float]:
            return (0.0, 0.0, 0.0)

    store = SimpleNamespace()
    rot.definir_ativo(store, _ESQUERDO)
    hub = _Hub()
    daemon = SimpleNamespace(_garantir_sensor_hub=lambda: hub, store=store, _mouse_device=None)
    corrida = _Corrida(uniq)

    def tique(acel: tuple[float, float, float], giro: tuple[float, float, float]) -> Any:
        relogio[0] += _TIQUE
        corrida.t = relogio[0]
        leitura["acel"], leitura["giro"] = acel, giro
        return gp.aplicar_o_movimento(daemon, rot.ativo(store), uniq=uniq,
                                      lx=128, ly=128, rx=128, ry=128, botoes=frozenset())

    for _ in range(60):
        tique(_MAO, corrida.tremor())
    na_mesa = [tique(_MESA, corrida.mesa()) for _ in range(round(3.4 / _TIQUE))]
    assert na_mesa[30] != (128, 128, 128, 128), "a mesa nunca inclinou — régua cega"
    assert na_mesa[-1] == (128, 128, 128, 128), (
        f"o {uniq} parado há 3 s segue no esquerdo do jogo: {na_mesa[-1]}")


def test_o_mesmo_parado_segura_a_inclinacao_do_controle_parado_e_so_dele() -> None:
    """MORDIDA: a regra ignorando o `mesmo_parado` → o do suporte volta ao centro aos 3 s."""
    store = SimpleNamespace()
    suporte = _Corrida(_P1, store, mesmo_parado=True)
    largado = _Corrida(_P2, store, semente=3)
    for c in (suporte, largado):
        c.segurar(_MAO, 1.0)
        c.mover((0.0, 0.0), (20.0, 0.0))
    for _ in range(round(5.0 / _TIQUE)):
        d_suporte = suporte.tique(_g(20.0), suporte.mesa())
        d_largado = largado.tique(_g(20.0), largado.mesa())
        assert d_suporte == _hoje(_g(20.0), _MAO), "o «Mesmo parado» parou"
    assert d_largado == (0, 0), "o vizinho sem o «Mesmo parado» não parou"
    assert not rot.inclinacao_parada(store, _P1, suporte.t)
    assert rot.inclinacao_parada(store, _P2, largado.t)


class _Servidor:
    """O `mira.set` e o `_merge_mira` de verdade, sobre um `store` e sem perfil no disco."""

    _CAMPOS_DA_MIRA = IpcServer._CAMPOS_DA_MIRA
    _handle_mira_set = IpcServer._handle_mira_set
    _merge_mira = IpcServer._merge_mira

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
    """MORDIDA: o `_merge_mira` sem a chave `inclinacao_parada` → a tela não teria o que pintar."""
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
    assert entradas[0]["mira"]["inclinacao_parada"] is True, entradas[0]["mira"]
    assert entradas[1]["mira"]["inclinacao_parada"] is False
    assert entradas[0]["mira"]["mesmo_parado"] is False
    corpo = asyncio.run(servidor._handle_mira_set({"uniq": _P2, "mesmo_parado": True}))
    assert corpo["status"] == "ok" and corpo["mesmo_parado"] is True
    for _ in range(round(4.0 / _TIQUE)):
        p2.mesmo_parado = True
        p2.tique(_MESA, p2.mesa())
        servidor._merge_mira(entradas)
        assert entradas[0]["mira"]["inclinacao_parada"] is False, "o «Mesmo parado» pausou"
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

    pintado = next(iter(a02.pacote(_ctx(inclinacao_parada=True))["cards"].values()))
    assert pintado["inclinacao-parada"] == a02.INCLINACAO_PARADA
    for mira in ({"inclinacao_parada": False}, {}):
        pintado = next(iter(a02.pacote(_ctx(**mira))["cards"].values()))
        assert pintado["inclinacao-parada"] != a02.INCLINACAO_PARADA
