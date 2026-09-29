"""HAPTICA-POR-RADIO-01 (P4) — o daemon publica o endpoint e troca de modo.

O escritor do controle é **UM SÓ**: dois disputam o nibble de sequência e os
enables, e foi assim que o microfone dela ficou desligado 93 vezes por segundo
em 10/09 — e foi assim que ela sentiu atraso em TODOS os inputs do jogo na
bancada de 18/09, com o ensaio escrevendo por fora.

Então a mesma ponte manda som OU háptica, e troca quando o jogo abre o
endpoint. Estas réguas medem a FIAÇÃO: quem é construído, com o quê, e em que
ordem cai. O comportamento da bomba está em
``test_haptica_por_radio_01_a_bomba_que_vibra.py``.

O ENDPOINT É DO LUGAR DESDE 28/09/2026 (A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01):
eram um por controle no rádio, e passaram a ser quatro, um por lugar, de pé
desde o primeiro DualSense da mesa, em qualquer transporte. O dublê abaixo é
construído pelo LUGAR, e as réguas que diziam «um endpoint por controle no
rádio» e «o cabo não ganha endpoint» foram trocadas pelo fato de agora.
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
    quedas: ClassVar[list[int]] = []

    def __init__(self, *, lugar: int, ancora: Any, **_: Any) -> None:
        self.lugar = lugar
        self.ancora = ancora
        self.nome = f"endpoint::{lugar}"
        self.subiu = False
        _EndpointDeMentira.criados.append(self)

    @property
    def monitor(self) -> str:
        return self.nome + ".monitor"

    def iniciar(self) -> bool:
        self.subiu = True
        return True

    def parar(self) -> None:
        _EndpointDeMentira.quedas.append(self.lugar)


@dataclass
class _Estado:
    sub: Any
    controles: list[_Controle]
    tocando: dict[str, bool]
    monitores: list[str]

    def o_alto_falante_toca(self, uniq: str, sim: bool = True) -> None:
        """Alguém está tocando no `hefesto_som_<hex6>` daquele controle.

        **RADIO-AFOGADO-01, 22/09/2026, e sem isto estas réguas mediriam outro
        produto.** Até este dia a ponte do som subia em silêncio, e as réguas
        daqui herdaram esse mundo: elas chamam `_casar_as_pontes` e esperam uma
        `PonteDeSomPorRadio` do outro lado. Agora a ponte do som só existe com
        som — então quem mede o ARRANJO tem de dizer que há som, senão mede a
        desistência e não a troca de modo.
        """
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
    #
    # **E O VOTO MUDOU DE DONO — A-HAPTICA-QUEM-JOGA-02, 26/09/2026.** Quem
    # joga é quem mexeu desde que o jogo abriu (`_quem_mexeu_na_partida`); o
    # evdev que o jogo segura (`_quem_o_jogo_le`) virou pista e não vota. O
    # dublê do voto põe todo controle jogando; o da pista segue, para a
    # varredura não ler o `/proc` da máquina.
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


def test_os_quatro_lugares_sobem_com_o_primeiro_controle(bancada: _Estado) -> None:
    """FATO QUE CAIU (28/09/2026): o endpoint era um por controle no rádio."""
    bancada.sub._casar_as_pontes(bancada.controles)
    assert [e.lugar for e in _EndpointDeMentira.criados] == [1, 2, 3, 4]
    assert all(e.subiu for e in _EndpointDeMentira.criados)


def test_sem_o_jogo_tocando_a_ponte_e_a_do_som(bancada: _Estado) -> None:
    """O endpoint fica publicado; o escritor continua sendo o do alto-falante."""
    bancada.o_alto_falante_toca(bancada.controles[0].uniq)
    bancada.sub._casar_as_pontes(bancada.controles)
    ponte = _PonteDeMentira.criadas[-1]
    assert ponte.arranjo is None, "arranjo None = o padrão do som"
    assert ponte.fonte_de_haptica is None


def test_com_o_jogo_tocando_a_ponte_vira_a_da_haptica(bancada: _Estado) -> None:
    from hefesto_dualsense4unix.integrations import alto_falante_bt as af

    # O único controle da mesa senta no lugar 1 (sem daemon, o primeiro livre).
    bancada.tocando["endpoint::1"] = True
    bancada.sub._casar_as_pontes(bancada.controles)
    ponte = _PonteDeMentira.criadas[-1]
    assert ponte.arranjo is af.ARRANJO_HAPTICA_032
    assert ponte.fonte_de_haptica is not None


def test_a_fonte_da_haptica_pede_quatro_canais(bancada: _Estado) -> None:
    """Dois canais dariam a voz do jogo aos motores e nenhum motor."""
    # O único controle da mesa senta no lugar 1 (sem daemon, o primeiro livre).
    bancada.tocando["endpoint::1"] = True
    bancada.sub._casar_as_pontes(bancada.controles)
    assert any(m.endswith("#4") for m in bancada.monitores), bancada.monitores


def test_o_jogo_abrindo_no_meio_derruba_e_sobe_de_novo(bancada: _Estado) -> None:
    """Trocar o arranjo com a bomba rodando mudaria o corpo do report no meio."""
    bancada.o_alto_falante_toca(bancada.controles[0].uniq)
    bancada.sub._casar_as_pontes(bancada.controles)
    primeira = _PonteDeMentira.criadas[-1]
    # O único controle da mesa senta no lugar 1 (sem daemon, o primeiro livre).
    bancada.tocando["endpoint::1"] = True
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


def test_o_ultimo_controle_que_sai_leva_a_ponte_e_os_lugares(bancada: _Estado) -> None:
    """Sem DualSense e sem jogo tocando, os quatro lugares caem com a ponte."""
    bancada.o_alto_falante_toca(bancada.controles[0].uniq)
    bancada.sub._casar_as_pontes(bancada.controles)
    bancada.sub._casar_as_pontes([])
    assert _PonteDeMentira.criadas[-1].desceu is True
    assert sorted(_EndpointDeMentira.quedas) == [1, 2, 3, 4]


def test_cada_lugar_ganha_uma_ancora_propria(bancada: _Estado) -> None:
    """Âncoras iguais são ContainerIds iguais, e o jogo confunde os lugares."""
    quatro = [
        _Controle(f"aa:bb:cc:00:00:0{i}", f"/dev/hidraw{i}", "bluetooth") for i in range(1, 5)
    ]
    bancada.sub._casar_as_pontes(quatro)
    assert len({e.ancora.syspath for e in _EndpointDeMentira.criados}) == 4


def test_o_controle_no_cabo_tambem_sobe_os_lugares(bancada: _Estado) -> None:
    """FATO QUE CAIU (28/09/2026): «no cabo o endpoint é a placa de verdade».

    O jogo casa o LUGAR, e o cabo passa por ele (um laço do endpoint do lugar à
    placa, ``integrations/haptica_do_cabo``). Nenhuma ponte do rádio sobe.
    """
    bancada.sub._casar_as_pontes([_Controle("aa:bb:cc:00:00:09", "/dev/hidraw9", "usb")])
    assert [e.lugar for e in _EndpointDeMentira.criados] == [1, 2, 3, 4]
    assert _PonteDeMentira.criadas == []
