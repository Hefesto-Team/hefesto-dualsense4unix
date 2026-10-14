"""O nó e a ponte do som não nascem depois do stop.

Sprint O-NO-E-A-PONTE-DO-SOM-NAO-NASCEM-DEPOIS-DO-STOP-01. Quem cria (a volta
de reconciliação) e quem derruba (o stop) partilham uma porta: com ela
fechada, o gerenciador não ergue nó, e o que a volta sobe depois do `_parar`
desce no mesmo passo, sem entrar nos dicionários. As réguas prendem a volta
num `Event` para o stop cair no meio dela. Nada de servidor de som de
verdade: o nó, a ponte e o ouvido são dublês que contam o que subiram e o
que desceram.
"""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.daemon.subsystems.governador_do_radio import Vaga
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh

P1, P2, P3, P4 = (f"aa:bb:cc:00:00:0{i}" for i in range(1, 5))
NO_CABO = (P1, P2)
NO_RADIO = (P3, P4)
ESPERA = 5.0


class _Servidor:
    """Os módulos que os nós do Hefesto puseram no servidor de som de mentira."""

    def __init__(self) -> None:
        self.modulos: list[tuple[str, str]] = []

    def do_hefesto(self) -> list[tuple[str, str]]:
        return [m for m in self.modulos if m[0] in ("module-null-sink", "module-loopback")]


class _NoDeMentira:
    """O nó de um controle: no cabo, `module-null-sink` mais o `module-loopback`."""

    def __init__(self, uniq: str, servidor: _Servidor, *, segurar: Any = None) -> None:
        self.uniq = uniq
        self._servidor = servidor
        self._segurar = segurar
        self._meus = [("module-null-sink", uniq)]
        if uniq in NO_CABO:
            self._meus.append(("module-loopback", uniq))
        self.paradas = 0

    def iniciar(self) -> bool:
        if self._segurar is not None:
            self._segurar()
        self._servidor.modulos.extend(self._meus)
        return True

    def parar(self) -> None:
        self.paradas += 1
        self._servidor.modulos = [m for m in self._servidor.modulos if m not in self._meus]


class _PonteDeMentira:
    """A ponte do rádio: o hidraw e a vaga ficam presos enquanto ela está no ar."""

    criadas: ClassVar[list[_PonteDeMentira]] = []

    def __init__(self, **kw: Any) -> None:
        self.uniq = str(kw["uniq"])
        self.vaga = kw.get("vaga")
        self.no_ar = False
        self.descidas = 0
        self.motivo = ""

    def subir(self) -> bool:
        _PonteDeMentira.criadas.append(self)
        self.no_ar = True
        return True

    def descer(self, **_kw: Any) -> bool:
        self.no_ar = False
        self.descidas += 1
        return True


class _Ouvido:
    """O ouvido do rádio (Nativo) e o da placa (cabo), pela forma que a volta usa."""

    def __init__(self, **kw: Any) -> None:
        self.uniq = str(kw.get("uniq", ""))
        self.placa = kw.get("placa")
        self.vivo = False
        self.descidas = 0
        self.motivo = ""

    def subir(self) -> bool:
        self.vivo = True
        return True

    def descer(self) -> None:
        self.vivo = False
        self.descidas += 1


class _Governador:
    """O governador com a forma real: toda ponte do rádio pede a vaga dela."""

    ao_autorizar: Any = None

    def iniciar(self) -> None:
        return None

    def pedir_vaga(self, uniq: str, tipo: str) -> Vaga:
        return Vaga(uniq=uniq, adaptador="hci-de-mentira", tipo=tipo)

    def parar(self, *_a: Any, **_k: Any) -> None:
        return None


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O servidor de mentira com o som tocando nos nós do P3 e do P4 (rádio)."""
    from tests.unit.test_a_haptica_do_radio_obedece_ao_sinal import ServidorDeSom
    from tests.unit.test_haptica_por_radio_01_a_ponte_troca_de_modo import (
        _EndpointDeMentira,
    )

    servidor = ServidorDeSom()
    for uniq in NO_RADIO:
        servidor.tocar(af.nome_do_sink(uniq), "77")
    monkeypatch.setattr(af, "rodar_pactl", servidor)
    monkeypatch.setattr(af, "a_ponte_do_radio_pode_subir", lambda: (True, ""))
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(eh, "EndpointDeHaptica", _EndpointDeMentira)
    monkeypatch.setattr(eh, "endpoints_de_pe", lambda *a, **k: {})
    monkeypatch.setattr(eh, "varrer_endpoints_orfaos", lambda *a, **k: None)
    monkeypatch.setattr(mod, "ESPERA_DA_VOLTA_S", 0.05)
    _PonteDeMentira.criadas = []
    return servidor


def _controles() -> list[Any]:
    return [
        mod.ControleNaLista(
            uniq=u,
            caminho=f"/dev/hidraw-de-mentira{i}",
            transporte="usb" if u in NO_CABO else "rádio",
        )
        for i, u in enumerate((P1, P2, P3, P4))
    ]


def test_a_volta_que_passa_do_join_nao_ergue_no_nem_ponte(
    mesa: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A volta presa no `pactl` passa dos 2 s do `join`, e o stop segue sem ela.

    P1 e P2 no cabo, P3 e P4 no rádio. A volta fica presa na fonte do monitor
    do P3, antes de subir a ponte; o stop passa do `join` e, já descendo o que
    tinha, solta a volta e espera que ela acabe. Ela não pode deixar ponte nos
    dicionários nem mandar o servidor erguer nó. MORDIDAS: tirar o teste de
    `_parar` em `_casar_as_pontes` deixa a ponte do P3 e a do P4; tirar o
    `fechar()` do começo do `stop` faz o gerenciador erguer os quatro nós,
    com o `module-loopback` do P1 e do P2.
    """
    servidor = _Servidor()
    erguidos: list[str] = []

    def _fabrica(uniq: str) -> _NoDeMentira:
        erguidos.append(uniq)
        return _NoDeMentira(uniq, servidor)

    gerenciador = mod.GerenciadorDeNosDeSom(fabrica=_fabrica)
    na_fonte, solta = threading.Event(), threading.Event()

    def _fonte_presa(id_do_no: str, **kw: Any) -> tuple[Any, Any, str]:
        if not na_fonte.is_set():
            na_fonte.set()
            assert solta.wait(ESPERA), "a régua não soltou a volta"
        return bytes, None, ""

    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _fonte_presa)
    sub = mod.AltoFalanteSubsystem(
        gerenciador=gerenciador,
        fonte_de_controles=_controles,
        daemon=SimpleNamespace(),
        governador=_Governador(),
    )
    volta: dict[str, threading.Thread | None] = {}

    parar_o_governador = _Governador.parar

    def _parar_o_governador(self: Any, *a: Any, **k: Any) -> Any:
        """O passo do stop depois do `join`: a volta sai do `pactl` lento aqui."""
        solta.set()
        thread = volta["thread"]
        if thread is not None:
            thread.join(ESPERA)
        return parar_o_governador(self, *a, **k)

    monkeypatch.setattr(_Governador, "parar", _parar_o_governador)

    async def _cena() -> None:
        await sub.start(SimpleNamespace(controller=None, store=None))
        volta["thread"] = sub._thread
        assert await asyncio.to_thread(na_fonte.wait, ESPERA), "a volta não chegou à fonte"
        await sub.stop()

    asyncio.run(_cena())
    thread = volta["thread"]
    assert thread is not None
    thread.join(ESPERA)
    assert not thread.is_alive(), "a volta não terminou"

    sem_vaga = [p.uniq for p in _PonteDeMentira.criadas if not isinstance(p.vaga, Vaga)]
    assert sem_vaga == [], f"a ponte subiu sem pedir a vaga ao governador: {sem_vaga!r}"
    pontes_no_ar = [p.uniq for p in _PonteDeMentira.criadas if p.no_ar]
    assert pontes_no_ar == [], f"ponte do rádio no ar depois do stop: {pontes_no_ar!r}"
    assert sub._pontes == {}, f"pontes guardadas depois do stop: {sorted(sub._pontes)!r}"
    assert dict(sub._tocadores) == {} and dict(sub._estalos) == {}
    assert dict(sub._ouvidos_do_radio) == {} and dict(sub._ouvidos_das_placas) == {}
    assert servidor.do_hefesto() == [], f"módulos do Hefesto no servidor: {servidor.do_hefesto()!r}"
    assert gerenciador.nos == {}
    assert erguidos == [], f"o gerenciador ergueu nó depois do stop: {erguidos!r}"


def test_o_parar_e_depois_o_reconciliar_nao_ergue_nada() -> None:
    """A reprodução do auditor: `parar()`, depois `reconciliar([...])`.

    MORDIDA: tirar o teste da porta em `reconciliar` e em `_erguer` faz o
    nó subir (e, mesmo descendo em seguida pela descida tardia, o servidor
    recebeu o `load-module`).
    """
    servidor = _Servidor()
    erguidos: list[str] = []

    def _fabrica(uniq: str) -> _NoDeMentira:
        erguidos.append(uniq)
        return _NoDeMentira(uniq, servidor)

    gerenciador = mod.GerenciadorDeNosDeSom(fabrica=_fabrica)
    gerenciador.parar()
    gerenciador.reconciliar(["aabbcc0000ff"])
    gerenciador.reconciliar(_controles())

    assert gerenciador.nos == {}, f"nós de pé depois do parar: {gerenciador.nos!r}"
    assert erguidos == []
    assert servidor.do_hefesto() == []


def test_o_no_cujo_iniciar_termina_depois_do_parar_desce() -> None:
    """O `iniciar` (dois `load-module` no cabo) ainda corre quando o `parar` passa.

    O nó só entraria em `_nos` depois, e o `parar` já o tinha esvaziado: ele
    ficava no servidor, fora do alcance de qualquer stop. MORDIDA: tirar a
    descida do nó tardio.
    """
    servidor = _Servidor()
    entrou, segura = threading.Event(), threading.Event()
    nos: list[_NoDeMentira] = []

    def _segurar() -> None:
        entrou.set()
        assert segura.wait(ESPERA), "a régua não soltou o iniciar"

    def _fabrica(uniq: str) -> _NoDeMentira:
        no = _NoDeMentira(uniq, servidor, segurar=_segurar)
        nos.append(no)
        return no

    gerenciador = mod.GerenciadorDeNosDeSom(fabrica=_fabrica)
    volta = threading.Thread(target=gerenciador.reconciliar, args=([P1],))
    volta.start()
    assert entrou.wait(ESPERA)
    gerenciador.parar()
    segura.set()
    volta.join(ESPERA)
    assert not volta.is_alive()

    assert [n.paradas for n in nos] == [1], "o nó tardio não desceu"
    assert servidor.do_hefesto() == [], f"ficou no servidor: {servidor.do_hefesto()!r}"
    assert gerenciador.nos == {}


def test_o_stop_reabre_no_start_com_o_gerenciador_de_sempre() -> None:
    """A porta fechada pelo stop reabre no start seguinte: o nó volta a nascer."""
    servidor = _Servidor()

    def _fabrica(uniq: str) -> _NoDeMentira:
        return _NoDeMentira(uniq, servidor)

    gerenciador = mod.GerenciadorDeNosDeSom(fabrica=_fabrica)
    gerenciador.parar()
    abrir = getattr(gerenciador, "abrir", None)
    assert callable(abrir), "o gerenciador não tem como reabrir a porta"
    abrir()
    gerenciador.reconciliar([P1, P3])
    assert sorted(gerenciador.nos) == sorted([P1, P3])
    gerenciador.parar()
    assert servidor.do_hefesto() == []


def test_tocador_e_ouvidos_depois_do_parar_nao_ficam(monkeypatch: pytest.MonkeyPatch) -> None:
    """O tocador do rumble e os ouvidos (rádio no Nativo, placa no cabo) não nascem parados.

    MORDIDA: tirar o teste de `_parar` onde a volta guarda o ouvido deixa os
    dois ouvidos no ar e nos dicionários.
    """
    criados: list[_Ouvido] = []

    def _novo(**kw: Any) -> _Ouvido:
        ouvido = _Ouvido(**kw)
        criados.append(ouvido)
        return ouvido

    monkeypatch.setattr(af, "OuvidoDoNo", _novo)
    monkeypatch.setattr(af, "OuvidoDaPlaca", _novo)
    sub = mod.AltoFalanteSubsystem(daemon=SimpleNamespace())
    sub._parar.set()

    assert sub._tocador_do_aparelho("aparelho-1") is None
    assert dict(sub._tocadores) == {}
    sub._casar_os_ouvidos_do_radio({af.nome_do_sink(P3): (P3, 4, "ouvido-som")})
    sub._casar_os_ouvidos_das_placas({P1: "alsa_output.placa-de-mentira"})

    assert dict(sub._ouvidos_do_radio) == {} and dict(sub._ouvidos_das_placas) == {}
    assert [o.vivo for o in criados] == [False] * len(criados)
