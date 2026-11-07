"""A Calibrar mede o que a mira usa: o zero sem gravidade, o sinal e o início do analógico.

MORDIDAS: tirar a falha do `_a_conta_ou_a_falha` deixa o `mexeu` calado; devolver a gravidade ao
`zeros_para_gravar` faz o campo voltar ao disco; trocar o sinal esperado em `_veredito_do_eixo`
faz o gesto certo dar contrário; a rampa sem o `chave_de_sensor` move o pad de todo mundo; o
`andou` sem o `uniq` da peça grava o piso no vizinho.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
from hefesto_dualsense4unix.daemon import ipc_handlers
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
from hefesto_dualsense4unix.testing import FakeController
from tests.unit.test_a_mira_vale_nos_quatro import _Mesa, P1, P2, P3, P4, QUATRO

sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                       / "src" / "hefesto_dualsense4unix" / "interface"))

_DIR = rot.DESTINO_ANALOGICO_DIREITO
_EM_PE = (0.0, 1.0, 0.0)
_PASSO = 0.02
_A_ESQUERDA = (0.0, 120.0, 0.0)
_PARA_CIMA = (120.0, 0.0, 0.0)
_QUIETO = (0.0, 0.0, 0.0)


def _gesto(*giros: tuple[float, float, float]) -> list[Any]:
    return [(giro, _EM_PE) for giro in giros for _ in range(30)]


def _a_conta(estados: dict[str, str]) -> str:
    import pacotes.a11_calibrar_sensores as a11

    mesa = [{"pref": f"p{n}", "jogador": n} for n in range(1, len(estados) + 1)]
    colunas = {f"p{n}": {a11.CAMPO_DO_ZERO: estados[f"P{n}"]} for n in range(1, len(estados) + 1)}
    return a11._a_conta_ou_a_falha(mesa, colunas)


def test_o_mexeu_chega_a_tela_com_o_que_fazer() -> None:
    import calibrar

    frase = _a_conta({"P1": "pronto", "P2": "mexeu", "P3": "pronto", "P4": "mexeu"})
    assert frase == f"P2, P4: {calibrar.O_QUE_FAZER_QUANDO_MEXEU}"
    assert _a_conta({"P1": "pronto", "P2": "pronto"}) == calibrar.contagem(2)


def test_o_arquivo_com_gravidade_carrega_e_o_campo_nao_volta() -> None:
    dono = SimpleNamespace()
    antigo = {"aabbcc000002": {"giro": [0.1, 0.2, 0.3], "gravidade": [0.0, 1.0, 0.0]}}
    assert rot.carregar_os_zeros(dono, antigo) == 1
    assert rot.zero_de(dono, P2).giro == (0.1, 0.2, 0.3)  # type: ignore[union-attr]
    assert "gravidade" not in json.dumps(rot.zeros_para_gravar(dono))


@pytest.mark.parametrize(
    ("giros", "arranjo", "esperado"),
    [
        ((_A_ESQUERDA, _PARA_CIMA), {}, ("bateu", "bateu", "bateu")),
        ((_PARA_CIMA, _A_ESQUERDA), {}, ("bateu", "bateu", "bateu")),
        (((0.0, -120.0, 0.0), _PARA_CIMA), {}, ("contrario", "contrario", "bateu")),
        ((_A_ESQUERDA, (-120.0, 0.0, 0.0)), {}, ("contrario", "bateu", "contrario")),
        ((_A_ESQUERDA, _QUIETO), {}, ("parado", "bateu", "parado")),
        ((_QUIETO,), {}, ("parado", "parado", "parado")),
        ((_A_ESQUERDA, _PARA_CIMA), {"inverter_horizontal": True},
         ("contrario", "contrario", "bateu")),
        ((_A_ESQUERDA, _PARA_CIMA), {"inverter_vertical": True},
         ("contrario", "bateu", "contrario")),
    ],
)
def test_o_sinal_diz_se_o_gesto_leva_o_analogico_para_o_lado_certo(
    giros: tuple[Any, ...], arranjo: dict[str, Any], esperado: tuple[str, str, str]
) -> None:
    veredito = rot.conferir_o_sinal(_gesto(*giros), rot.ArranjoDeMovimento(**arranjo), _PASSO)
    assert (veredito["estado"], veredito["horizontal"], veredito["vertical"]) == esperado


def test_ir_e_voltar_vale_pelo_primeiro_sentido() -> None:
    ida_e_volta = _gesto(_A_ESQUERDA, (0.0, -120.0, 0.0), _PARA_CIMA)
    assert rot.conferir_o_sinal(ida_e_volta, rot.ArranjoDeMovimento(), _PASSO)["estado"] == "bateu"


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        return alvo

    monkeypatch.setattr(loader, "profiles_dir", _dir)
    return alvo


class _Relogio:
    def __init__(self) -> None:
        self.agora = 500.0

    def monotonic(self) -> float:
        return self.agora


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> _Relogio:
    certo = _Relogio()
    monkeypatch.setattr(ipc_handlers, "time", certo)
    REGISTRO.definir_jogo(True)
    yield certo  # type: ignore[misc]
    REGISTRO.definir_jogo(False)


def _servidor(tmp_path: Path) -> IpcServer:
    loader.save_profile(Profile(name="Ensaio", match=MatchAny(type="any")))
    controle = FakeController(transport="usb")  # type: ignore[arg-type]
    controle.primary_uniq = P1  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(
        controller=controle, store=daemon.store, profile_manager=gerente,
        socket_path=tmp_path / "c.sock", daemon=daemon,
    )
    daemon.store.set_active_profile("Ensaio")
    return servidor


def _pede(servidor: IpcServer, metodo: str, **params: Any) -> dict[str, Any]:
    return asyncio.run(servidor._handlers[metodo](params))  # type: ignore[arg-type]


def test_a_rampa_grava_o_piso_so_na_peca_que_mediu(
    perfis: Path, tmp_path: Path, relogio: _Relogio
) -> None:
    servidor = _servidor(tmp_path)
    for uniq in (P2, P3):
        _pede(servidor, "mira.set", uniq=uniq, ligada=True)
    assert _pede(servidor, "motion.rampa", uniq=P3, pedido="comecar")["status"] == "subindo"
    relogio.agora += rot.TEMPO_DA_RAMPA_S / 2
    corpo = _pede(servidor, "motion.rampa", uniq=P3, pedido="andou")
    assert corpo["status"] == "ok" and corpo["piso"] == pytest.approx(rot.TETO_DA_RAMPA / 2)
    pecas = loader.load_profile("Ensaio").controllers
    assert pecas["aabbcc000003"].movimento.piso == pytest.approx(rot.TETO_DA_RAMPA / 2)
    assert "piso" not in pecas["aabbcc000002"].movimento.model_fields_set
    assert rot.rampa_agora(servidor.store, P3, relogio.agora) is None


@pytest.mark.parametrize(
    ("caso", "esperado"), [("nativo", "nativo"), ("sem_jogo", "sem_jogo"), ("sem_mira", "sem_mira")]
)
def test_a_rampa_recusa_sem_gravar(
    perfis: Path, tmp_path: Path, relogio: _Relogio, monkeypatch: pytest.MonkeyPatch,
    caso: str, esperado: str,
) -> None:
    servidor = _servidor(tmp_path)
    if caso != "sem_mira":
        _pede(servidor, "mira.set", uniq=P2, ligada=True)
    if caso == "nativo":
        monkeypatch.setattr(servidor.daemon, "is_native_mode", lambda: True)
    if caso == "sem_jogo":
        REGISTRO.definir_jogo(False)
    assert _pede(servidor, "motion.rampa", uniq=P2, pedido="comecar")["status"] == esperado
    assert rot.rampa_agora(servidor.store, P2, relogio.agora) is None


def test_ninguem_disse_que_andou_a_rampa_some_sem_gravar(
    perfis: Path, tmp_path: Path, relogio: _Relogio
) -> None:
    servidor = _servidor(tmp_path)
    _pede(servidor, "mira.set", uniq=P2, ligada=True)
    _pede(servidor, "motion.rampa", uniq=P2, pedido="comecar")
    relogio.agora += rot.TEMPO_DA_RAMPA_S + 0.1
    assert _pede(servidor, "motion.rampa", uniq=P2, pedido="andou")["status"] == "parada"
    assert "piso" not in loader.load_profile("Ensaio").controllers[
        "aabbcc000002"].movimento.model_fields_set


def test_o_estado_diz_o_sinal_e_a_rampa_de_cada_um(
    perfis: Path, tmp_path: Path, relogio: _Relogio
) -> None:
    servidor = _servidor(tmp_path)
    _pede(servidor, "mira.set", uniq=P2, ligada=True)
    _pede(servidor, "motion.rampa", uniq=P2, pedido="comecar")
    servidor._estados_do_sinal()["aabbcc000002"] = {"estado": "contrario"}
    entradas: list[dict[str, Any]] = [{"uniq": P2}, {"uniq": P3}, {"uniq": ""}]
    relogio.agora += 1.0
    servidor._merge_passos_da_calibrar(entradas)
    assert entradas[0]["sinal"]["estado"] == "contrario" and entradas[0]["rampa"]["subindo"]
    assert entradas[1]["sinal"]["estado"] == "nao_medido" and not entradas[1]["rampa"]["subindo"]
    assert entradas[2]["sinal"] is None and entradas[2]["rampa"] is None


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("quem", QUATRO)
def test_a_rampa_sai_so_no_pad_daquele_jogador(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str, quem: str
) -> None:
    pecas = {uniq: {"destino": _DIR} for uniq in QUATRO}
    mesa = _Mesa(monkeypatch, tmp_path, transporte, pecas)
    rot.comecar_a_rampa(mesa.daemon.store, quem, mesa.relogio.agora)
    mesa.segundos(rot.TEMPO_DA_RAMPA_S / 2)
    for uniq, pad in mesa.pads.items():
        if uniq == quem:
            assert pad.analog[-1]["rx"] > 128 and pad.analog[-1]["ry"] == 128
        else:
            assert pad.centro(), f"a rampa de {quem} andou o pad de {uniq}"
    mesa.segundos(rot.TEMPO_DA_RAMPA_S / 2 + 0.05)
    assert mesa.pads[quem].centro(), "a rampa não soltou o analógico no prazo"


def test_a_rampa_sobe_no_analogico_do_lado_da_peca(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mesa = _Mesa(monkeypatch, tmp_path, "bt", {P3: {"destino": "analogico_esquerdo"}})
    rot.comecar_a_rampa(mesa.daemon.store, P3, mesa.relogio.agora)
    mesa.segundos(rot.TEMPO_DA_RAMPA_S / 2)
    assert mesa.pads[P3].analog[-1]["lx"] > 128
    assert mesa.pads[P3].analog[-1]["rx"] == 128


def test_a_rampa_ignora_o_gatilho_e_a_peca_parada(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pecas = {P4: {"destino": _DIR, "gatilho": "l2"}}
    mesa = _Mesa(monkeypatch, tmp_path, "bt", pecas)
    mesa.segundos(rot.TEMPO_DO_PARADO_S + 0.1)
    rot.comecar_a_rampa(mesa.daemon.store, P4, mesa.relogio.agora)
    mesa.segundos(1.0)
    assert mesa.pads[P4].analog[-1]["rx"] > 128


def test_o_sinal_mede_a_peca_e_nao_grava_nada(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    servidor = _servidor(tmp_path)
    monkeypatch.setattr(rot, "SEGUNDOS_DO_SINAL", 0.4)
    monkeypatch.setattr(servidor, "_INTERVALO_DO_ZERO_S", 0.02, raising=False)

    class _Hub:
        def velocidade_do_movimento(self, uniq: str) -> tuple[float, float, float]:
            return (200.0, -200.0, 0.0) if uniq == P2 else _QUIETO

        def aceleracao_do_movimento(self, uniq: str) -> tuple[float, float, float]:
            return _EM_PE

    servidor._sensor_hub = _Hub()  # type: ignore[assignment]

    async def medir() -> None:
        for uniq in (P2, P3):
            await servidor._handlers["motion.sinal"]({"uniq": uniq})
        await asyncio.gather(*servidor._medidas_do_sinal_em_voo)

    asyncio.run(medir())
    estados = servidor._estados_do_sinal()
    assert estados["aabbcc000002"] == {
        "estado": "contrario", "horizontal": "contrario", "vertical": "bateu"}
    assert estados["aabbcc000003"]["estado"] == "parado"
    assert not loader.load_profile("Ensaio").controllers, "o sinal contrário gravou sozinho"


@pytest.mark.parametrize(
    "pedido",
    [{"piso": 1.5}, {"piso": -0.1}, {"piso": True}, {"velocidade_do_jogo": 0},
     {"velocidade_do_jogo": 2001}, {"sensibilidade_h": 11}, {"sensibilidade_v": -1},
     {"sensibilidade": 0}, {"sensibilidade": 13}],
)
def test_o_numero_fora_da_faixa_recusa(
    perfis: Path, tmp_path: Path, pedido: dict[str, Any]
) -> None:
    with pytest.raises(ValueError, match=r"mira\.set"):
        _pede(_servidor(tmp_path), "mira.set", uniq=P2, **pedido)
    assert not loader.load_profile("Ensaio").controllers


def test_o_sensibilidade_velho_escreve_os_dois_eixos(perfis: Path, tmp_path: Path) -> None:
    corpo = _pede(_servidor(tmp_path), "mira.set", uniq=P2, sensibilidade=12)
    assert (corpo["sensibilidade_h"], corpo["sensibilidade_v"]) == (10, 10)
    secao = loader.load_profile("Ensaio").controllers["aabbcc000002"].movimento
    assert (secao.sensibilidade_h, secao.sensibilidade_v) == (10, 10)


def test_o_inverter_apaga_o_veredito_que_ele_acabou_de_mudar(
    perfis: Path, tmp_path: Path
) -> None:
    servidor = _servidor(tmp_path)
    estados = servidor._estados_do_sinal()
    estados["aabbcc000002"] = {"estado": "contrario"}
    estados["aabbcc000003"] = {"estado": "contrario"}
    asyncio.run(servidor._handlers["mira.set"]({"uniq": P2, "inverter_horizontal": True}))
    assert "aabbcc000002" not in estados
    assert estados["aabbcc000003"] == {"estado": "contrario"}, "o de outro controle fica"
    estados["aabbcc000002"] = {"estado": "bateu"}
    asyncio.run(servidor._handlers["mira.set"]({"uniq": P2, "sensibilidade_h": 7}))
    assert estados["aabbcc000002"] == {"estado": "bateu"}, "só o inverter muda o sentido"


def test_os_gestos_pedem_pelo_controle_certo() -> None:
    import calibrar
    import pacotes.a11_calibrar_sensores as a11

    pedidos: list[tuple[str, dict[str, Any]]] = []

    class _Ponte:
        def __init__(self, status: str) -> None:
            self.status = status

        def resultado(self, metodo: str, **params: Any) -> dict[str, Any]:
            pedidos.append((metodo, params))
            return {"status": self.status}

    a11.calibrar_sinal(None, {"uniq": P3}, _Ponte("medindo"))  # type: ignore[arg-type]
    a11.calibrar_rampa(None, {"uniq": P4, "pedido": "comecar"},  # type: ignore[arg-type]
                       _Ponte("subindo"))
    assert pedidos == [("motion.sinal", {"uniq": P3}),
                       ("motion.rampa", {"uniq": P4, "pedido": "comecar"})]
    for status, frase in calibrar.RECUSAS_DA_RAMPA.items():
        with pytest.raises(RuntimeError, match=frase):
            a11.calibrar_rampa(None, {"uniq": P4, "pedido": "comecar"},  # type: ignore[arg-type]
                               _Ponte(status))
