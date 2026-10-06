"""HAPTICA-POR-RADIO-01 (P4) — o daemon publica o endpoint e troca de modo.

O escritor do controle é **UM SÓ**: dois disputam o nibble de sequência e os
enables, e foi assim que o microfone do usuário ficou desligado 93 vezes por segundo
em 10/09 — e foi assim que ela sentiu atraso em TODOS os inputs do jogo na
bancada de 18/09, com o ensaio escrevendo por fora.

Então a mesma ponte manda som OU háptica, e troca quando o jogo abre o
endpoint. Estas réguas medem a FIAÇÃO: quem é construído, com o quê, e em que
ordem cai. O comportamento da bomba está em
``test_haptica_por_radio_01_a_bomba_que_vibra.py``.

O ENDPOINT É DO APARELHO DESDE 02/10/2026 (A-HAPTICA-E-POR-APARELHO-01): um por
DualSense da mesa, em qualquer transporte (de 28/09 a 02/10 eram quatro, um por
lugar). O dublê abaixo é construído pelo ``uniq``, e a régua que dizia «o cabo
não ganha endpoint» segue trocada pelo fato de agora.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod


@dataclass
class _Controle:
    uniq: str
    caminho: str
    transporte: str


class _PonteDeMentira:
    criadas: ClassVar[list[Any]] = []

    def __init__(self, **kw: Any) -> None:
        self.kw = kw
        self.uniq = kw["uniq"]
        self.fonte_de_haptica = kw.get("fonte_de_haptica")
        self.motivo = ""
        self.subiu = False
        self.desceu = False
        _PonteDeMentira.criadas.append(self)

    def subir(self) -> bool:
        self.subiu = True
        return True

    def descer(self, **_: Any) -> bool:
        self.desceu = True
        return True

    def esta_de_pe(self) -> bool:
        return self.subiu and not self.desceu

    @property
    def leva(self) -> bool:
        """O bloco da háptica vai ao fio agora (o ``leva_a_haptica`` que a ponte lê)."""
        leva = self.kw.get("leva_a_haptica", False)
        return bool(leva() if callable(leva) else leva)


class _EndpointDeMentira:
    """O endpoint do APARELHO (A-HAPTICA-E-POR-APARELHO-01): nasce pelo ``uniq``."""

    criados: ClassVar[list[Any]] = []
    quedas: ClassVar[list[str]] = []

    def __init__(self, *, uniq: str, ancora: Any, **_: Any) -> None:
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            marca_do_aparelho,
        )

        self.uniq = uniq
        self.marca = marca_do_aparelho(uniq)
        self.ancora = ancora
        self.nome = f"endpoint::{uniq}"
        self.subiu = False
        _EndpointDeMentira.criados.append(self)

    @property
    def monitor(self) -> str:
        return self.nome + ".monitor"

    def iniciar(self) -> bool:
        self.subiu = True
        return True

    def parar(self) -> None:
        _EndpointDeMentira.quedas.append(self.uniq)


@dataclass
class _Estado:
    sub: Any
    controles: list[_Controle]
    tocando: dict[str, bool]
    monitores: list[str]

    def o_alto_falante_toca(self, uniq: str, sim: bool = True) -> None:
        """Alguém está tocando no `hefesto_som_<hex6>` daquele controle."""
        from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

        self.tocando[nome_do_sink(uniq)] = sim


@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch) -> _Estado:
    from hefesto_dualsense4unix.integrations import alto_falante_bt as af
    from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker

    _PonteDeMentira.criadas = []
    _EndpointDeMentira.criados = []
    _EndpointDeMentira.quedas = []
    monitores: list[str] = []
    tocando: dict[str, bool] = {}

    def _fonte(id_do_no: str, **kw: Any) -> tuple[Any, Any, str]:
        monitores.append(f"{id_do_no}#{kw.get('canais', 2)}")
        return (lambda _n: b""), f"gravador:{id_do_no}", ""

    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _fonte)
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(af, "sink_esta_tocando", lambda nome, *a, **k: tocando.get(nome, False))
    monkeypatch.setattr(eh, "EndpointDeHaptica", _EndpointDeMentira)
    monkeypatch.setattr(
        eh, "ancoras", lambda *a, **k: [eh.Ancora(syspath=f"/d/{i}", declarado=f"/d/{i}/i:1.0")
                                        for i in range(4)]
    )
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: type("N", (), {"fd": 7})())

    monkeypatch.setattr(
        mod.AltoFalanteSubsystem, "_quem_o_jogo_le", lambda self, controles: set()
    )
    monkeypatch.setattr(
        mod.AltoFalanteSubsystem, "_quem_mexeu_na_partida",
        lambda self, controles: {
            str(getattr(c, "uniq", "")).lower() for c in controles},
    )

    controles = [_Controle("aa:bb:cc:00:00:01", "/dev/hidraw1", "bluetooth")]

    class _Ger:
        def reconciliar(self, *_a: Any, **_k: Any) -> None:
            return None

        def dormir(self, _s: float) -> bool:
            return False

        def parar(self) -> None:
            return None

    sub = mod.AltoFalanteSubsystem(gerenciador=_Ger(), fonte_de_controles=lambda: list(controles))
    return _Estado(sub=sub, controles=controles, tocando=tocando, monitores=monitores)


def test_o_controle_sobe_o_endpoint_dele(bancada: _Estado) -> None:
    """Um por aparelho (A-HAPTICA-E-POR-APARELHO-01; de 28/09 a 02/10, os quatro lugares)."""
    bancada.sub._casar_as_pontes(bancada.controles)
    assert [e.uniq for e in _EndpointDeMentira.criados] == ["aa:bb:cc:00:00:01"]
    assert all(e.subiu for e in _EndpointDeMentira.criados)


def test_sem_o_jogo_tocando_a_ponte_e_a_do_som(bancada: _Estado) -> None:
    """O endpoint fica publicado; o escritor continua sendo o do alto-falante."""
    bancada.o_alto_falante_toca(bancada.controles[0].uniq)
    bancada.sub._casar_as_pontes(bancada.controles)
    ponte = _PonteDeMentira.criadas[-1]
    assert ponte.leva is False, "sem o jogo, a háptica não vai ao fio"
    assert ponte.fonte_de_haptica is None


def test_com_o_jogo_tocando_a_ponte_leva_a_haptica(bancada: _Estado) -> None:
    bancada.tocando[f"endpoint::{bancada.controles[0].uniq}"] = True
    bancada.sub._casar_as_pontes(bancada.controles)
    ponte = _PonteDeMentira.criadas[-1]
    assert ponte.leva is True
    assert ponte.fonte_de_haptica is not None


def test_a_fonte_da_haptica_pede_quatro_canais(bancada: _Estado) -> None:
    """Dois canais dariam a voz do jogo aos motores e nenhum motor."""
    bancada.tocando[f"endpoint::{bancada.controles[0].uniq}"] = True
    bancada.sub._casar_as_pontes(bancada.controles)
    assert any(m.endswith("#4") for m in bancada.monitores), bancada.monitores


def test_o_jogo_abrindo_no_meio_derruba_e_sobe_de_novo(bancada: _Estado) -> None:
    """A ponte que subiu sem ler o endpoint sobe de novo lendo: uma vez, para ganhar a háptica."""
    bancada.o_alto_falante_toca(bancada.controles[0].uniq)
    bancada.sub._casar_as_pontes(bancada.controles)
    primeira = _PonteDeMentira.criadas[-1]
    bancada.tocando[f"endpoint::{bancada.controles[0].uniq}"] = True
    bancada.sub._casar_as_pontes(bancada.controles)
    assert primeira.desceu is True
    assert len(_PonteDeMentira.criadas) == 2
    assert _PonteDeMentira.criadas[-1] is not primeira


def test_o_modo_que_nao_muda_nao_reconstroi_nada(bancada: _Estado) -> None:
    """Reconstruir a cada tique cortaria o som e a vibração a cada volta."""
    bancada.o_alto_falante_toca(bancada.controles[0].uniq)
    bancada.sub._casar_as_pontes(bancada.controles)
    bancada.sub._casar_as_pontes(bancada.controles)
    bancada.sub._casar_as_pontes(bancada.controles)
    assert len(_PonteDeMentira.criadas) == 1


def test_o_ultimo_controle_que_sai_leva_a_ponte_e_o_endpoint(bancada: _Estado) -> None:
    """Sem DualSense e sem jogo tocando, o endpoint do aparelho cai com a ponte."""
    bancada.o_alto_falante_toca(bancada.controles[0].uniq)
    bancada.sub._casar_as_pontes(bancada.controles)
    bancada.sub._casar_as_pontes([])
    assert _PonteDeMentira.criadas[-1].desceu is True
    assert _EndpointDeMentira.quedas == [bancada.controles[0].uniq]


def test_cada_aparelho_ganha_uma_ancora_propria(bancada: _Estado) -> None:
    """Âncoras iguais são ContainerIds iguais, e o jogo confunde os controles."""
    quatro = [
        _Controle(f"aa:bb:cc:00:00:0{i}", f"/dev/hidraw{i}", "bluetooth") for i in range(1, 5)
    ]
    bancada.sub._casar_as_pontes(quatro)
    assert len({e.ancora.syspath for e in _EndpointDeMentira.criados}) == 4


def test_o_controle_no_cabo_tambem_sobe_o_endpoint_dele(bancada: _Estado) -> None:
    """FATO QUE CAIU (28/09/2026): «no cabo o endpoint é a placa de verdade»."""
    bancada.sub._casar_as_pontes([_Controle("aa:bb:cc:00:00:09", "/dev/hidraw9", "usb")])
    assert [e.uniq for e in _EndpointDeMentira.criados] == ["aa:bb:cc:00:00:09"]
    assert _PonteDeMentira.criadas == []
