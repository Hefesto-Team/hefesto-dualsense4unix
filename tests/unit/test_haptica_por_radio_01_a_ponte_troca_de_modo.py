"""HAPTICA-POR-RADIO-01 (P4) — o daemon publica o endpoint e troca de modo.

O escritor do controle é **UM SÓ**: dois disputam o nibble de sequência e os
enables, e foi assim que o microfone dela ficou desligado 93 vezes por segundo
em 10/09 — e foi assim que ela sentiu atraso em TODOS os inputs do jogo na
bancada de 18/09, com o ensaio escrevendo por fora.

Então a mesma ponte manda som OU háptica, e troca quando o jogo abre o
endpoint. Estas réguas medem a FIAÇÃO: quem é construído, com o quê, e em que
ordem cai. O comportamento da bomba está em
``test_haptica_por_radio_01_a_bomba_que_vibra.py``.
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
        self.arranjo = kw.get("arranjo")
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


class _EndpointDeMentira:
    criados: ClassVar[list[Any]] = []
    quedas: ClassVar[list[str]] = []

    def __init__(self, *, uniq: str, ancora: Any, **_: Any) -> None:
        self.uniq = uniq
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

    # **O GATE DA HÁPTICA GANHOU UM SEGUNDO LADO, e a fixture foi atrás —
    # 21/09/2026.** A QUEM-JOGA-E-QUEM-VIBRA-01 acrescentou *"o jogo está
    # LENDO aquele controle"* ao *"o jogo abriu o canal do endpoint"*, porque
    # só o primeiro fazia três controles vibrarem num jogo de um jogador.
    #
    # Estas réguas medem a FIAÇÃO do alto-falante, não a leitura de `/proc` —
    # essa tem dono e réguas próprias (`integrations/quem_o_jogo_le.py`). Sem
    # este dublê elas reprovavam por AMBIENTE (a máquina da suíte não tem jogo
    # aberto), e um vermelho de ambiente se lê como regressão: foi o que
    # aconteceu, e ficou vermelho na árvore por dias.
    monkeypatch.setattr(
        mod.AltoFalanteSubsystem, "_quem_o_jogo_le",
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


def test_o_endpoint_sobe_por_controle_no_radio(bancada: _Estado) -> None:
    bancada.sub._casar_as_pontes(bancada.controles)
    assert [e.uniq for e in _EndpointDeMentira.criados] == ["aa:bb:cc:00:00:01"]
    assert _EndpointDeMentira.criados[0].subiu is True


def test_sem_o_jogo_tocando_a_ponte_e_a_do_som(bancada: _Estado) -> None:
    """O endpoint fica publicado; o escritor continua sendo o do alto-falante."""
    bancada.sub._casar_as_pontes(bancada.controles)
    ponte = _PonteDeMentira.criadas[-1]
    assert ponte.arranjo is None, "arranjo None = o padrão do som"
    assert ponte.fonte_de_haptica is None


def test_com_o_jogo_tocando_a_ponte_vira_a_da_haptica(bancada: _Estado) -> None:
    from hefesto_dualsense4unix.integrations import alto_falante_bt as af

    bancada.tocando["endpoint::aa:bb:cc:00:00:01"] = True
    bancada.sub._casar_as_pontes(bancada.controles)
    ponte = _PonteDeMentira.criadas[-1]
    assert ponte.arranjo is af.ARRANJO_HAPTICA_032
    assert ponte.fonte_de_haptica is not None


def test_a_fonte_da_haptica_pede_quatro_canais(bancada: _Estado) -> None:
    """Dois canais dariam a voz do jogo aos motores e nenhum motor."""
    bancada.tocando["endpoint::aa:bb:cc:00:00:01"] = True
    bancada.sub._casar_as_pontes(bancada.controles)
    assert any(m.endswith("#4") for m in bancada.monitores), bancada.monitores


def test_o_jogo_abrindo_no_meio_derruba_e_sobe_de_novo(bancada: _Estado) -> None:
    """Trocar o arranjo com a bomba rodando mudaria o corpo do report no meio."""
    bancada.sub._casar_as_pontes(bancada.controles)
    primeira = _PonteDeMentira.criadas[-1]
    bancada.tocando["endpoint::aa:bb:cc:00:00:01"] = True
    bancada.sub._casar_as_pontes(bancada.controles)
    assert primeira.desceu is True
    assert len(_PonteDeMentira.criadas) == 2
    assert _PonteDeMentira.criadas[-1] is not primeira


def test_o_modo_que_nao_muda_nao_reconstroi_nada(bancada: _Estado) -> None:
    """Reconstruir a cada tique cortaria o som e a vibração a cada volta."""
    bancada.sub._casar_as_pontes(bancada.controles)
    bancada.sub._casar_as_pontes(bancada.controles)
    bancada.sub._casar_as_pontes(bancada.controles)
    assert len(_PonteDeMentira.criadas) == 1


def test_o_controle_que_sai_leva_a_ponte_e_o_endpoint(bancada: _Estado) -> None:
    bancada.sub._casar_as_pontes(bancada.controles)
    bancada.sub._casar_as_pontes([])
    assert _PonteDeMentira.criadas[-1].desceu is True
    assert _EndpointDeMentira.quedas == ["aa:bb:cc:00:00:01"]


def test_cada_controle_ganha_uma_ancora_propria(bancada: _Estado) -> None:
    """Âncoras iguais são ContainerIds iguais, e o jogo confunde os controles."""
    quatro = [
        _Controle(f"aa:bb:cc:00:00:0{i}", f"/dev/hidraw{i}", "bluetooth") for i in range(1, 5)
    ]
    bancada.sub._casar_as_pontes(quatro)
    assert len({e.ancora.syspath for e in _EndpointDeMentira.criados}) == 4


def test_o_controle_no_cabo_nao_ganha_endpoint(bancada: _Estado) -> None:
    """No cabo o endpoint é a placa de som DE VERDADE do controle."""
    bancada.sub._casar_as_pontes([_Controle("aa:bb:cc:00:00:09", "/dev/hidraw9", "usb")])
    assert _EndpointDeMentira.criados == []
