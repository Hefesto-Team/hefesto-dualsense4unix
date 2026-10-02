"""RADIO-AFOGADO-01 — a ponte do som só existe enquanto há som. 22/09/2026."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink

MESA = [f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4)]


@dataclass
class _Controle:
    uniq: str
    caminho: str = "/dev/hidraw9"
    transporte: str = "bluetooth"


class _PonteDeMentira:
    criadas: ClassVar[list[Any]] = []
    falham: ClassVar[set[str]] = set()

    def __init__(self, **kw: Any) -> None:
        self.uniq = kw["uniq"]
        self.arranjo = kw.get("arranjo")
        self.motivo = ""
        self.desceu = False
        _PonteDeMentira.criadas.append(self)

    def subir(self) -> bool:
        return self.uniq not in _PonteDeMentira.falham

    def descer(self, **_: Any) -> bool:
        self.desceu = True
        return True

    def esta_de_pe(self) -> bool:
        return not self.desceu


class _EndpointDeMentira:
    """O endpoint do APARELHO (A-HAPTICA-E-POR-APARELHO-01, 02/10/2026)."""

    def __init__(self, *, uniq: str, ancora: Any = None, **_: Any) -> None:
        from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
            marca_do_aparelho,
        )

        self.uniq = uniq
        self.marca = marca_do_aparelho(uniq)
        self.ancora = ancora
        self.nome = f"endpoint::{uniq}"

    @property
    def monitor(self) -> str:
        return self.nome + ".monitor"

    def iniciar(self) -> bool:
        return True

    def parar(self) -> None:
        return None


@dataclass
class _Bancada:
    sub: Any
    tocando: dict[str, bool] = field(default_factory=dict)
    duvida: set[str] = field(default_factory=set)
    colhidos: list[Any] = field(default_factory=list)

    def toca(self, uniq: str, sim: bool = True) -> None:
        self.tocando[nome_do_sink(uniq)] = sim

    def o_jogo_toca_no_endpoint(self, uniq: str, sim: bool = True) -> None:
        """O jogo toca no endpoint do APARELHO deste controle."""
        self.tocando[f"endpoint::{uniq}"] = sim

    def volta(self, *uniqs: str) -> None:
        self.sub._casar_as_pontes([_Controle(u) for u in uniqs])

    @property
    def de_pe(self) -> list[str]:
        return sorted(self.sub._pontes)


@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch) -> _Bancada:
    from hefesto_dualsense4unix.integrations import alto_falante_bt as af
    from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
    from hefesto_dualsense4unix.integrations import filho_de_som as fs
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker

    _PonteDeMentira.criadas = []
    _PonteDeMentira.falham = set()
    b = _Bancada(sub=None)  # type: ignore[arg-type]

    def _toca(nome: Any, *_a: Any, **kw: Any) -> bool:
        if str(nome) in b.duvida:
            return bool(kw.get("na_duvida", False))
        return b.tocando.get(str(nome), False)

    monkeypatch.setattr(af, "sink_esta_tocando", _toca)
    monkeypatch.setattr(af, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(
        af,
        "fonte_do_monitor_do_no",
        lambda no, **kw: ((lambda _n: b""), f"gravador:{no}", ""),
    )
    monkeypatch.setattr(fs, "derrubar_leitor_de_pipe", lambda g, **_k: b.colhidos.append(g))
    monkeypatch.setattr(eh, "EndpointDeHaptica", _EndpointDeMentira)
    monkeypatch.setattr(
        eh,
        "ancoras",
        lambda *a, **k: [
            eh.Ancora(syspath=f"/d/{i}", declarado=f"/d/{i}/i:1.0") for i in range(4)
        ],
    )
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: type("N", (), {"fd": 7})())
    monkeypatch.setattr(
        mod.AltoFalanteSubsystem, "_quem_o_jogo_le", lambda self, controles: set()
    )
    monkeypatch.setattr(
        mod.AltoFalanteSubsystem,
        "_quem_mexeu_na_partida",
        lambda self, controles: {str(getattr(c, "uniq", "")).lower() for c in controles},
    )

    class _Ger:
        def reconciliar(self, *_a: Any, **_k: Any) -> None:
            return None

        def dormir(self, _s: float) -> bool:
            return False

        def parar(self) -> None:
            return None

    b.sub = mod.AltoFalanteSubsystem(gerenciador=_Ger(), fonte_de_controles=lambda: [])
    return b


def test_a_mesa_de_quatro_parada_nao_levanta_ponte_nenhuma(bancada: _Bancada) -> None:
    """Quatro controles ociosos escreviam 400 reports por segundo no rádio dela."""
    bancada.volta(*MESA)
    assert bancada.de_pe == [], "a ponte subiu sem ninguém tocando"
    assert _PonteDeMentira.criadas == []


def test_o_gravador_da_ponte_que_nao_sobe_nao_fica_vivo(bancada: _Bancada) -> None:
    """Desistir depois de abrir o `pw-record` deixaria um processo por volta."""
    bancada.volta(*MESA)
    assert bancada.colhidos == [], bancada.colhidos


def test_o_controle_com_som_ganha_a_ponte(bancada: _Bancada) -> None:
    """MORDIDA: faça o portão recusar sempre e o alto-falante fica mudo."""
    bancada.toca(MESA[1])
    bancada.volta(*MESA)
    assert bancada.de_pe == [MESA[1]]
    assert _PonteDeMentira.criadas[-1].arranjo is None, "o arranjo do som é o padrão"


def test_a_haptica_nao_passa_pelo_portao_do_som(bancada: _Bancada) -> None:
    """Quem vibra não precisa de alto-falante tocando — são dois nós."""
    from hefesto_dualsense4unix.integrations import alto_falante_bt as af

    bancada.o_jogo_toca_no_endpoint(MESA[0])
    bancada.volta(*MESA)
    assert bancada.de_pe == [MESA[0]]
    assert _PonteDeMentira.criadas[-1].arranjo is af.ARRANJO_HAPTICA_032


def test_o_som_que_acaba_derruba_a_ponte(bancada: _Bancada) -> None:
    """Sem isto a enxurrada seria só ADIADA: a primeira nota levantaria a ponte"""
    bancada.toca(MESA[0])
    bancada.volta(*MESA)
    primeira = _PonteDeMentira.criadas[-1]

    bancada.toca(MESA[0], False)
    bancada.volta(*MESA)

    assert bancada.de_pe == []
    assert primeira.desceu is True, "a ponte ociosa continuou escrevendo"
    assert bancada.sub._modo_da_ponte == {}, "o modo ficou lembrado sem ponte"


def test_o_servidor_mudo_nao_derruba_a_ponte_de_pe(bancada: _Bancada) -> None:
    """Um `pactl` que engasgou não pode calar o som de um jogo aberto."""
    bancada.toca(MESA[0])
    bancada.volta(*MESA)
    assert bancada.de_pe == [MESA[0]]

    bancada.duvida.add(nome_do_sink(MESA[0]))
    bancada.volta(*MESA)
    assert bancada.de_pe == [MESA[0]], "a dúvida derrubou a ponte de um jogo aberto"


def test_o_servidor_mudo_nao_levanta_ponte_nova(bancada: _Bancada) -> None:
    """O outro lado, e é o que salva a mesa: `na_duvida=True` fixo devolveria a"""
    bancada.duvida.update(nome_do_sink(u) for u in MESA)
    bancada.volta(*MESA)
    assert bancada.de_pe == []


class TestOLacoDoNoQueNaoNasce:
    """O nó de som só nasce com ROTA, e no rádio a rota era «a ponte está de pé»."""

    def _sub(self, bancada: _Bancada) -> Any:
        bancada.volta(*MESA)
        return bancada.sub

    def test_sem_ponte_de_pe_o_controle_do_radio_ainda_tem_caminho(
        self, bancada: _Bancada
    ) -> None:
        """MORDIDA: devolva `None` quando `self._pontes.get(uniq)` for `None` —"""
        sub = self._sub(bancada)
        assert sub._pontes == {}, "a bancada precisa começar SEM ponte"
        caminho = sub._ponte_do_radio_de(MESA[0])
        assert caminho is not None and caminho() is True

    def test_a_ponte_de_pe_continua_respondendo_por_si(
        self, bancada: _Bancada
    ) -> None:
        """Quando há ponte, quem responde é ela — não uma promessa."""
        bancada.toca(MESA[0])
        sub = self._sub(bancada)
        caminho = sub._ponte_do_radio_de(MESA[0])
        assert caminho is not None and caminho() is True
        assert caminho == sub._pontes[MESA[0]].esta_de_pe

    def test_a_ponte_que_nao_subiu_tira_o_caminho_e_o_prazo_devolve(
        self, bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A falha de verdade — com o som dela na mão — some com o nó."""
        agora = [1000.0]
        monkeypatch.setattr(mod.time, "monotonic", lambda: agora[0])
        _PonteDeMentira.falham.add(MESA[0])
        bancada.toca(MESA[0])
        sub = self._sub(bancada)
        assert _PonteDeMentira.criadas, "a ponte nem foi tentada"
        assert sub._pontes == {}, "a ponte que não subiu ficou guardada"

        assert sub._ponte_do_radio_de(MESA[0]) is None

        agora[0] += mod.RECUSA_DA_PONTE_S + 1
        caminho = sub._ponte_do_radio_de(MESA[0])
        assert caminho is not None and caminho() is True
        assert MESA[0] not in sub._ponte_recusada, "a recusa vencida ficou no dicionário"

    def test_a_ponte_que_sobe_apaga_a_recusa_velha(
        self, bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem isto, um controle que falhou uma vez carregaria a recusa por um"""
        agora = [1000.0]
        monkeypatch.setattr(mod.time, "monotonic", lambda: agora[0])
        _PonteDeMentira.falham.add(MESA[0])
        bancada.toca(MESA[0])
        bancada.volta(*MESA)
        assert MESA[0] in bancada.sub._ponte_recusada

        _PonteDeMentira.falham.clear()
        bancada.volta(*MESA)
        assert bancada.sub._pontes != {}, "a ponte não subiu na segunda volta"
        assert MESA[0] not in bancada.sub._ponte_recusada

    def test_sem_gravador_na_maquina_nao_ha_caminho(
        self, bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A `libopus` não é a única coisa que falta numa máquina recém-feita."""
        from hefesto_dualsense4unix.integrations import alto_falante_bt as af

        sub = self._sub(bancada)
        monkeypatch.setattr(af, "ha_gravador_de_monitor", lambda: False)
        assert sub._ponte_do_radio_de(MESA[0]) is None

    def test_sem_libopus_nao_ha_caminho(
        self, bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A promessa pergunta À MÁQUINA — é isso que a separa do `lambda: True`."""
        from hefesto_dualsense4unix.integrations import alto_falante_bt as af

        sub = self._sub(bancada)
        monkeypatch.setattr(
            af, "a_ponte_do_radio_pode_subir", lambda: (False, "sem libopus")
        )
        assert sub._ponte_do_radio_de(MESA[0]) is None


def test_a_haptica_sem_fonte_nao_vira_som_em_silencio(
    bancada: _Bancada, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A háptica que não consegue gravador cai para o modo som — e ali o portão"""
    from hefesto_dualsense4unix.integrations import alto_falante_bt as af

    def _so_o_som(no: str, **kw: Any) -> tuple[Any, Any, str]:
        if kw.get("papel") == "haptica":
            return None, None, "sem gravador para a háptica"
        return (lambda _n: b""), f"gravador:{no}", ""

    monkeypatch.setattr(af, "fonte_do_monitor_do_no", _so_o_som)
    bancada.o_jogo_toca_no_endpoint(MESA[0])
    bancada.volta(MESA[0])

    assert bancada.de_pe == []
    assert bancada.colhidos == ["gravador:hefesto_som_000001"], (
        "o gravador do som ficou vivo sem ponte — ninguém mais o colheria")
