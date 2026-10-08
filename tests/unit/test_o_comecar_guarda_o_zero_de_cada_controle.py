"""O «COMEÇAR» GUARDA O ZERO DE CADA CONTROLE.

A sprint: O-COMECAR-DA-CALIBRAR-GUARDA-O-ZERO-DE-CADA-CONTROLE-01.

O defeito medido em 06/10/2026: o «Começar» da Calibrar não tinha gesto nem dono no
daemon, e um controle com viés de giro andava sozinho com a zona morta baixa.

O contrato que esta régua mede:

1. o roteador mede o zero com a MESMA régua do parado (a peça que mexe não guarda nada)
   e desconta o viés antes da Mira e da inclinação; sem zero, o giro é o mesmo objeto;
2. o zero é por controle: o do P2 não muda o P1 nem o P3, e o mesmo endereço pelo cabo
   e pelo BT acha o mesmo zero;
3. `motion.calibrate {uniq}` responde «medindo», e o `state_full` diz «pronto» ou «mexeu»;
   o zero vai a um arquivo do Hefesto e volta no boot;
4. a Calibrar tem o gesto `calibrar-comecar`, o selo de cada cartão e a fita dos três passos.

AS MORDIDAS (rodadas em 08/10/2026 e devolvidas): com o `descontar_o_vies` devolvendo o
giro cru, as réguas do desconto e do motor reprovam; com o `data-gesto` do «Começar»
arrancado do gerador, a régua da página reprova.

Endereços de rádio: a faixa SINTÉTICA da casa (``aa:bb:cc``), nunca um OUI real.
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

sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                       / "src" / "hefesto_dualsense4unix" / "interface"))

_P1, _P2, _P3 = (f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3))
_GRAVIDADE = (0.0, 0.0, 1.0)
_VIES = (0.6, -2.4, 1.1)


def _parado(n: int = 100, vies: tuple[float, float, float] = _VIES) -> list[Any]:
    """Amostras de uma peça na mesa: o viés com um tremor de 0,1 °/s."""
    return [((vies[0] + 0.1 * (i % 2), vies[1], vies[2] - 0.1 * (i % 2)), _GRAVIDADE)
            for i in range(n)]


# ---------------------------------------------------------------- 1. o roteador


def test_a_peca_parada_guarda_o_vies_e_a_gravidade() -> None:
    zero = rot.medir_o_zero(_parado())
    assert zero is not None
    assert zero.giro == pytest.approx((0.65, -2.4, 1.05))
    assert zero.gravidade == pytest.approx(_GRAVIDADE)


def test_a_peca_que_mexe_nao_guarda_nada() -> None:
    """A régua do parado: o giro variando 1,5 °/s de pico a pico recomeça a janela."""
    amostras = _parado()
    amostras[50] = ((_VIES[0] + 4.0, _VIES[1], _VIES[2]), _GRAVIDADE)
    assert rot.medir_o_zero(amostras) is None
    inclinada = _parado()
    inclinada[60] = (_VIES, (0.0, 0.2, 0.98))
    assert rot.medir_o_zero(inclinada) is None, "a gravidade andou e o zero ficou"


def test_poucas_amostras_nao_sao_medida() -> None:
    assert rot.medir_o_zero(_parado(rot.MINIMO_DE_AMOSTRAS_DO_ZERO - 1)) is None


def test_o_desconto_zera_o_vies_e_sem_zero_e_o_mesmo_giro() -> None:
    dono = SimpleNamespace()
    cru = (_VIES[0], _VIES[1], _VIES[2])
    assert rot.descontar_o_vies(dono, _P1, cru) is cru, "sem zero, o giro mudou"
    assert rot.descontar_o_vies(dono, _P1, None) is None
    rot.definir_o_zero(dono, _P1, rot.ZeroDoControle(giro=_VIES, gravidade=_GRAVIDADE))
    assert rot.descontar_o_vies(dono, _P1, cru) == pytest.approx((0.0, 0.0, 0.0))


def test_o_zero_do_p2_nao_vale_para_o_p1_nem_o_p3() -> None:
    dono = SimpleNamespace()
    rot.definir_o_zero(dono, _P2, rot.ZeroDoControle(giro=_VIES, gravidade=_GRAVIDADE))
    assert rot.zero_de(dono, _P1) is None and rot.zero_de(dono, _P3) is None
    assert rot.descontar_o_vies(dono, _P3, _VIES) == _VIES


def test_o_cabo_e_o_bt_acham_o_mesmo_zero() -> None:
    """A chave é a de sensor: o endereço com ou sem dois-pontos, em qualquer caixa."""
    dono = SimpleNamespace()
    rot.definir_o_zero(dono, _P2, rot.ZeroDoControle(giro=_VIES, gravidade=_GRAVIDADE))
    for grafia in (_P2.upper(), _P2.replace(":", ""), _P2.replace(":", "").upper()):
        assert rot.zero_de(dono, grafia) is not None, grafia


def test_o_arquivo_vai_e_volta_e_a_entrada_torta_fica_de_fora() -> None:
    dono = SimpleNamespace()
    rot.definir_o_zero(dono, _P2, rot.ZeroDoControle(giro=_VIES, gravidade=_GRAVIDADE))
    dados = json.loads(json.dumps(rot.zeros_para_gravar(dono)))
    dados["torto"] = {"giro": [1, 2], "gravidade": "x"}
    outro = SimpleNamespace()
    assert rot.carregar_os_zeros(outro, dados) == 1
    zero = rot.zero_de(outro, _P2)
    assert zero is not None and zero.giro == pytest.approx(_VIES)


# ---------------------------------------------------------------- 2. o motor, P1 a P3


class _Hub:
    """O `SensorHub` mínimo: o giro de cada controle, e a gravidade de pé."""

    def __init__(self, giros: dict[str, tuple[float, float, float]]) -> None:
        self.giros = giros

    def aceleracao_do_movimento(self, _u: str) -> tuple[float, float, float]:
        return _GRAVIDADE

    def velocidade_do_movimento(self, u: str) -> tuple[float, float, float] | None:
        return self.giros.get(u)

    def angulo_do_movimento(self, _u: str) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)


def test_o_motor_desconta_o_vies_so_de_quem_tem_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Mira com a zona morta no mínimo: o P2 calibrado para, o P1 e o P3 seguem andando.

    É o MESMO `aplicar_o_movimento` que o `coop` chama para o P2 a P4.
    MORDIDA: o `descontar_o_vies` devolvendo o giro cru — o P2 anda sozinho.
    """
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
    from hefesto_dualsense4unix.profiles.schema import ProfileMovimentoConfig

    monkeypatch.setattr(REGISTRO, "estado", lambda _u: SimpleNamespace(
        giroscopio=True, acelerometro=True))
    store = SimpleNamespace()
    arranjo = rot.montar(ProfileMovimentoConfig.model_validate(
        {"destino": rot.DESTINO_ANALOGICO_DIREITO, "zona_morta_graus_s": 0.0,
         "teto_graus_s": 20.0, "sensibilidade": 12}))
    rot.definir_ativo(store, arranjo)
    vies_forte = (0.0, 6.0, 0.0)
    hub = _Hub({_P1: vies_forte, _P2: vies_forte, _P3: vies_forte})
    rot.definir_o_zero(store, _P2, rot.ZeroDoControle(giro=vies_forte, gravidade=_GRAVIDADE))
    daemon = SimpleNamespace(_garantir_sensor_hub=lambda: hub, store=store, _mouse_device=None)
    saida = {u: gp.aplicar_o_movimento(daemon, arranjo, uniq=u, lx=128, ly=128, rx=128, ry=128,
                                       botoes=frozenset()) for u in (_P1, _P2, _P3)}
    assert saida[_P2] == (128, 128, 128, 128), saida
    assert saida[_P1][2:] != (128, 128) and saida[_P3][2:] != (128, 128), saida


# ---------------------------------------------------------------- 3. o daemon de verdade


def _servidor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, hub: Any) -> Any:
    """O `Daemon` e o `IpcServer` do produto, com o hub dublê e a configuração num tmp."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.testing import FakeController
    from hefesto_dualsense4unix.utils import session

    casa = tmp_path / "config"

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            casa.mkdir(parents=True, exist_ok=True)
        return casa

    monkeypatch.setattr(session, "config_dir", _config_dir)
    monkeypatch.setattr(rot, "SEGUNDOS_DO_ZERO", 0.6)
    controle = FakeController(transport="bt")  # type: ignore[arg-type]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(controller=controle, store=daemon.store, profile_manager=gerente,
                         socket_path=tmp_path / "zero.sock", daemon=daemon)
    monkeypatch.setattr(servidor, "_garantir_sensor_hub", lambda: hub)
    return servidor


class _HubDaMesa:
    """O P1 parado com viés; o P3 mexe no meio da medida."""

    def __init__(self) -> None:
        self.n = 0

    def velocidade_do_movimento(self, u: str) -> tuple[float, float, float] | None:
        if u == _P3:
            self.n += 1
            return (40.0 if self.n % 7 == 0 else 0.0, 0.0, 0.0)
        return _VIES if u == _P1 else None

    def aceleracao_do_movimento(self, u: str) -> tuple[float, float, float] | None:
        return _GRAVIDADE if u in (_P1, _P3) else None


def _estados(servidor: Any) -> dict[str, Any]:
    entradas = [{"uniq": u} for u in (_P1, _P2, _P3)] + [{"uniq": None}]
    servidor._merge_zero(entradas)
    return {e["uniq"]: e["zero"] for e in entradas}


def test_o_comecar_mede_guarda_e_o_state_full_diz(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """P1 parado → «pronto» e no arquivo; P2 sem leitura → «parado»; P3 mexeu → «mexeu»."""
    servidor = _servidor(tmp_path, monkeypatch, _HubDaMesa())
    calibrar = servidor._handlers["motion.calibrate"]

    async def _a_medida() -> list[Any]:
        respostas = [await calibrar({"uniq": u}) for u in (_P1, _P2, _P3)]
        respostas.append(await calibrar({"uniq": _P1}))
        meio = _estados(servidor)
        await asyncio.gather(*list(servidor._medidas_do_zero_em_voo))
        return [respostas, meio]

    respostas, meio = asyncio.run(_a_medida())
    assert [r["status"] for r in respostas] == ["medindo"] * 4
    assert all(z["estado"] == "medindo" for u, z in meio.items() if u)
    fim = _estados(servidor)
    assert fim[_P1] == {"estado": "pronto", "guardado": True}
    assert fim[_P2] == {"estado": "parado", "guardado": False}
    assert fim[_P3] == {"estado": "mexeu", "guardado": False}
    assert fim[None] is None
    gravado = json.loads((tmp_path / "config" / "zeros-dos-sensores.json").read_text("utf-8"))
    assert set(gravado) == {"aabbcc000001"}
    assert gravado["aabbcc000001"]["giro"] == pytest.approx(list(_VIES))
    assert rot.descontar_o_vies(servidor.store, _P1, _VIES) == pytest.approx((0.0, 0.0, 0.0))


def test_o_zero_volta_no_boot_e_o_state_full_diz_pronto(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.utils import session

    servidor = _servidor(tmp_path, monkeypatch, _HubDaMesa())
    session.gravar_os_zeros({"aabbcc000002": {"giro": list(_VIES), "gravidade": [0, 0, 1]}})
    assert rot.carregar_os_zeros(servidor.store, session.ler_os_zeros()) == 1
    assert _estados(servidor)[_P2] == {"estado": "pronto", "guardado": True}


def test_o_boot_le_os_zeros_do_disco() -> None:
    """O `run` do daemon devolve os zeros ao roteador antes do primeiro tique."""
    import inspect

    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    fonte = inspect.getsource(Daemon.run)
    assert "carregar_os_zeros(self.store, ler_os_zeros())" in fonte


def test_o_pedido_sem_endereco_e_recusado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    servidor = _servidor(tmp_path, monkeypatch, _HubDaMesa())
    for torto in ({}, {"uniq": ""}, {"uniq": "::"}, {"uniq": 3}):
        with pytest.raises(ValueError):
            asyncio.run(servidor._handlers["motion.calibrate"](torto))


# ---------------------------------------------------------------- 4. a tela


def _ctx(zeros: dict[str, Any]) -> Any:
    import pacotes

    entradas = [{"uniq": u, "connected": True, "inputs": {}, "zero": z}
                for u, z in zeros.items()]
    mesa = [{"pref": f"p{i + 1}", "jogador": i + 1, "uniq": e["uniq"], "nome": "DualSense",
             "via": "BT", "transporte": "bt", "conectado": True}
            for i, e in enumerate(entradas)]
    return pacotes.Contexto(state={}, mesa=mesa, conectados=entradas, estados={})


class _Ponte:
    def __init__(self, status: str = "medindo") -> None:
        self.status = status
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        self.chamadas.append((metodo, params))
        return {"status": self.status, "uniq": params.get("uniq"), "segundos": 5.0}


def test_o_comecar_pede_a_medida_de_cada_controle_conectado() -> None:
    import pacotes

    fn = pacotes.gesto_da_pagina("calibrar-sensores.html", "calibrar-comecar")
    assert fn is not None, "o «Começar» continua sem dono"
    p = _Ponte()
    fn(_ctx({_P1: None, _P2: None}), {}, p)
    assert p.chamadas == [("motion.calibrate", {"uniq": _P1}),
                          ("motion.calibrate", {"uniq": _P2})]
    with pytest.raises(ValueError):
        fn(_ctx({}), {}, _Ponte())
    with pytest.raises(RuntimeError):
        fn(_ctx({_P1: None}), {}, _Ponte(status="erro"))


def test_o_comecar_pela_ponte_chega_ao_daemon(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O gesto pela ponte de verdade, com o `_safe_call` ligado ao servidor do produto."""
    import pacotes
    from pacotes import ponte

    from hefesto_dualsense4unix.app import ipc_bridge

    servidor = _servidor(tmp_path, monkeypatch, _HubDaMesa())

    def _safe_call(method: str, params: Any = None, **_kw: Any) -> tuple[bool, Any]:
        return True, asyncio.run(servidor._handlers[method](dict(params or {})))

    monkeypatch.setattr(ipc_bridge, "_safe_call", _safe_call)
    fn = pacotes.gesto_da_pagina("calibrar-sensores.html", "calibrar-comecar")
    assert fn is not None
    fn(_ctx({_P1: None}), {}, ponte)


def test_o_selo_e_a_fita_seguem_o_estado_de_cada_controle() -> None:
    import pacotes.a11_calibrar_sensores as a11

    carga = a11.pacote(_ctx({
        _P1: {"estado": "pronto", "guardado": True},
        _P2: {"estado": "medindo", "guardado": False},
        _P3: None,
    }))
    assert [carga["colunas"][p]["zero-estado"] for p in ("p1", "p2", "p3")] == [
        "pronto", "medindo", "parado"]
    assert (carga["passo-parado"], carga["passo-medindo"], carga["passo-pronto"]) == (
        "", "sim", "")
    assert "calibrar" not in (carga.get("sem_dono") or {})
    todos = a11.pacote(_ctx({_P1: {"estado": "pronto"}, _P2: {"estado": "pronto"}}))
    assert todos["passo-pronto"] == "sim" and todos["passo-parado"] == ""
    mexeu = a11.pacote(_ctx({_P1: {"estado": "pronto"}, _P2: {"estado": "mexeu"}}))
    assert mexeu["colunas"]["p2"]["zero-estado"] == "mexeu"
    assert mexeu["passo-parado"] == "sim", "um controle mexeu e a fita não voltou ao 1"


def test_a_pagina_tem_o_gesto_o_selo_e_a_fita() -> None:
    """MORDIDA: o `data-gesto` do «Começar» arrancado do gerador."""
    import calibrar

    doc = calibrar.documento([{"pref": "p1", "jogador": 1, "uniq": _P1, "nome": "DualSense",
                               "via": "BT", "cor": ""}])
    assert doc.count('data-gesto="calibrar-comecar"') == 1
    assert 'data-campo="zero-estado" data-hef-alvo="atributo" data-hef-atributo="data-zero"' in doc
    for estado in (calibrar.ZERO_PARADO, calibrar.ZERO_MEDINDO, calibrar.ZERO_PRONTO):
        assert f'data-campo="passo-{estado}" data-hef-alvo="marcado"' in doc
    assert ">Mexeu<" in doc
    mockup = (Path(__file__).resolve().parents[2] / "mockup" / "calibrar-sensores.html")
    assert 'data-gesto="calibrar-comecar"' in mockup.read_text(encoding="utf-8"), (
        "o mockup não foi regerado")
