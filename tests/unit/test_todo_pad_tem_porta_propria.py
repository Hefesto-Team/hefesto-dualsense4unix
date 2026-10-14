"""Todo pad tem porta USB virtual própria (TODO-PAD-TEM-PORTA-PROPRIA-01, 14/10/2026).

A decisão é a ``D-1410-TODO-PAD-TEM-PORTA-PROPRIA``, dela: o endpoint de háptica
com o nome da Sony só nasce, e só se adota, na interface do gadget do PRÓPRIO
pad. A âncora emprestada (um hub, um receptor, a porta de outro aparelho) saiu
do produto: com ela o jogo achava um áudio cujo ``ContainerId`` não casa com
HID nenhum, e a biblioteca da Sony o varria sem parar (o engasgo de 12/10 e de
14/10).

**A causa medida em 14/10, às 10h42:** o daemon tirava um retrato das âncoras
próprias no começo da volta, e o gadget que enumerava DEPOIS do retrato nascia
na âncora que a distribuição emprestava. Perdia quem enumerava dentro da janela
de uma volta, e não «o segundo de cada transporte»: a fila do ``vhci_hcd`` anda
~5,6 s por porta, e a volta roda a cada 5 s. O Cosmic Red enumerou às
10:42:15.65 e foi publicado na ``usb1/1-3`` às 10:42:19.03; o White enumerou
às 10:42:26.79 e foi publicado emprestado 93 ms depois. Fora da corrida o
produto emprestava sempre que o gadget não estava no registro (09h37, 10h05,
10h24, 10h45).

A régua vale para 1 a 4 controles, no cabo e no rádio, em qualquer ordem, com
qualquer subconjunto sem porta, antes e depois do jogo. Nada aqui depende de
quem sobe primeiro, do player 1 nem desta máquina.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.subsystems import alto_falante
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations import pad_usb
from tests.unit import porta_de_mentira as porta
from tests.unit import test_a_haptica_chega_a_quem_entra_depois as h

_TODOS = (h._P1, h._P2, h._P3, h._P4)
_LUGAR = {u: n for n, u in enumerate(_TODOS, start=1)}
#: Dois no cabo e dois no rádio: o caso obrigatório da tarefa.
_NO_CABO = {h._P1: ("3-8", 28), h._P3: ("3-7", 29)}
#: A âncora que a distribuição de antes emprestava (o receptor da bancada).
_EMPRESTADA = "/devices/pci0000:00/0000:00:14.0/usb1/1-3/1-3:1.0"


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    """A mesa da háptica, com o registro do gadget VAZIO: cada caso dá as portas."""
    m = h.mesa.__wrapped__(monkeypatch, tmp_path)  # type: ignore[attr-defined]
    monkeypatch.setattr(pad_usb, "_INTERFACE_DO_APARELHO", {})
    return m


def _chega(mesa: Any, uniq: str) -> Any:
    if uniq in _NO_CABO:
        aparelho, devnum = _NO_CABO[uniq]
        return h._no_cabo(mesa, uniq, _LUGAR[uniq], aparelho, devnum)
    mesa.assentos[uniq] = _LUGAR[uniq]
    return h._Controle(uniq, "bt", f"/dev/hidraw{_LUGAR[uniq]}")


def _ancoras_publicadas(mesa: Any) -> dict[str, str]:
    """``{uniq: sysfs.path}`` de todo endpoint desta casa no servidor de som."""
    por_nome = {eh.nome_do_endpoint(u): u for u in _TODOS}
    return {
        por_nome[s["nome"]]: str(s["props"].get("sysfs.path", ""))
        for s in mesa.servidor.sinks.values()
        if s["nome"] in por_nome
    }


def _a_regra(mesa: Any, com_porta: set[str], na_mesa: list[str]) -> None:
    """Quem tem porta tem o endpoint NELA; quem não tem, nenhum endpoint."""
    publicadas = _ancoras_publicadas(mesa)
    assert set(publicadas) == com_porta & set(na_mesa), publicadas
    for uniq, ancora in publicadas.items():
        assert ancora == pad_usb.interface_do_aparelho(uniq), (
            f"o endpoint de {uniq} está na porta de outro: {ancora}"
        )
    assert len(set(publicadas.values())) == len(publicadas), "uma porta serve a dois endpoints"


def _ditos(registros: Sequence[Mapping[str, Any]], evento: str) -> list[Mapping[str, Any]]:
    return [r for r in registros if r["event"] == evento]


_SUBCONJUNTOS = [
    frozenset(c) for n in range(len(_TODOS) + 1) for c in itertools.combinations(_TODOS, n)
]
_ORDENS = [_TODOS, tuple(reversed(_TODOS)), (h._P3, h._P1, h._P4, h._P2)]


_IDS_DOS_SUBCONJUNTOS = ["".join(u[-1] for u in sorted(s)) or "nenhum" for s in _SUBCONJUNTOS]


@pytest.mark.parametrize("ordem", _ORDENS, ids=["1234", "4321", "3142"])
@pytest.mark.parametrize("com_porta", _SUBCONJUNTOS, ids=_IDS_DOS_SUBCONJUNTOS)
def test_nenhum_endpoint_fora_da_porta_do_proprio_pad(
    mesa: Any, ordem: tuple[str, ...], com_porta: frozenset[str]
) -> None:
    """D-1410-TODO-PAD-TEM-PORTA-PROPRIA: 1 a 4 controles, dois no cabo e dois no rádio.

    As portas são dadas na ordem INVERSA da chegada, para que o número da porta
    nunca coincida com o lugar nem com a ordem. MORDIDA: devolva o empréstimo em
    ``_casar_as_pontes`` e arranque a guarda de ``EndpointDeHaptica.iniciar``.
    """
    for n, uniq in enumerate(reversed(ordem), start=1):
        if uniq in com_porta:
            porta.dar_porta(uniq, n)
    chegaram: list[Any] = []
    for uniq in ordem:
        chegaram.append(_chega(mesa, uniq))
        mesa.volta(*chegaram)
        _a_regra(mesa, set(com_porta), [c.uniq for c in chegaram])
    assert mesa.servidor.quedas == []


@pytest.mark.parametrize("uniq", _TODOS, ids=["p1-cabo", "p2-radio", "p3-cabo", "p4-radio"])
def test_sem_porta_nenhum_endpoint_e_o_log_diz_por_que_uma_vez(mesa: Any, uniq: str) -> None:
    """D-1410-TODO-PAD-TEM-PORTA-PROPRIA: sem porta, sem endpoint, e uma linha por motivo.

    Vale para qualquer um dos quatro, no cabo ou no rádio.
    """
    controle = _chega(mesa, uniq)
    pad_usb.anotar_sem_porta(uniq, "sem_contrato:vhci_hcd")
    with structlog.testing.capture_logs() as registros:
        for _ in range(3):
            mesa.volta(controle)
        pad_usb.anotar_sem_porta(uniq, "nao_enumerou")  # (noqa-acento): chave de máquina
        mesa.volta(controle)
    assert mesa.servidor.do_nome(eh.nome_do_endpoint(uniq)) == []
    assert [(r["uniq"], r["motivo"]) for r in _ditos(registros, "haptica_sem_porta_propria")] == [
        (uniq, "sem_contrato:vhci_hcd"),
        (uniq, "nao_enumerou"),  # (noqa-acento): chave de máquina
    ]


def test_o_motivo_que_ninguem_anotou_e_sem_gadget(mesa: Any) -> None:
    with structlog.testing.capture_logs() as registros:
        mesa.volta(_chega(mesa, h._P2))
    (dito,) = _ditos(registros, "haptica_sem_porta_propria")
    assert dito["motivo"] == pad_usb.SEM_GADGET


def test_a_porta_que_chega_faz_nascer_e_a_que_desce_leva_o_endpoint(mesa: Any) -> None:
    """O gadget que desce sem jogo tocando leva o endpoint, e o log diz."""
    controle = _chega(mesa, h._P2)
    mesa.volta(controle)
    assert mesa.servidor.do_nome(eh.nome_do_endpoint(h._P2)) == []
    interface = porta.dar_porta(h._P2, 6)
    mesa.volta(controle)
    assert h._ancora_do_aparelho(mesa.servidor, h._P2) == interface
    porta.tirar_porta(h._P2)
    with structlog.testing.capture_logs() as registros:
        mesa.volta(controle)
    assert mesa.servidor.do_nome(eh.nome_do_endpoint(h._P2)) == []
    assert _ditos(registros, "haptica_endpoint_desce_sem_a_porta")
    assert _ditos(registros, "haptica_sem_porta_propria"), "o log não disse por que ficou sem"


def test_com_o_jogo_tocando_a_porta_que_desce_nao_derruba_o_endpoint(mesa: Any) -> None:
    """A regra de 26/09 fica: o fluxo do jogo não perde o nó debaixo dele.

    O endpoint é o da porta que ERA do próprio pad: não vira empréstimo de outro.
    """
    controle = _chega(mesa, h._P4)
    interface = porta.dar_porta(h._P4, 2)
    mesa.volta(controle)
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(h._P4))
    porta.tirar_porta(h._P4)
    mesa.volta(controle)
    assert h._ancora_do_aparelho(mesa.servidor, h._P4) == interface
    assert mesa.servidor.quedas == []


@pytest.mark.parametrize("dono", [h._P1, h._P2])
def test_o_endpoint_emprestado_que_o_daemon_anterior_deixou_cai(mesa: Any, dono: str) -> None:
    """O daemon de antes do install deixou o endpoint numa âncora emprestada.

    Com a porta própria, ele cai e renasce nela; sem a porta, só cai.
    """
    herdado = mesa.servidor.modulo_herdado(eh.nome_do_endpoint(dono), _EMPRESTADA)
    com = dono == h._P1
    if com:
        porta.dar_porta(dono, 3)
    mesa.volta(_chega(mesa, dono))
    assert herdado in mesa.servidor.quedas
    _a_regra(mesa, {dono} if com else set(), [dono])


def test_a_porta_que_enumera_no_meio_da_volta_nao_vira_a_de_outro(
    mesa: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A corrida de 10h42: o White (cabo) enumera depois do retrato da volta.

    Os outros três já têm porta. O endpoint dele nasce na porta DELE, na mesma
    volta, e nunca na de quem já estava sentado.
    """
    portas = {u: porta.dar_porta(u, n) for n, u in enumerate((h._P1, h._P2, h._P4), start=1)}
    serial = pad_usb.serial_do_pad("02:fe:00:00:00:03")
    pad_usb.anotar_gadget_a_caminho(serial, h._P3, 30.0)
    na_ordem = alto_falante.AltoFalanteSubsystem._nos_na_ordem

    def _enumera_no_meio(self: Any, *a: Any, **k: Any) -> Any:
        portas[h._P3] = porta.dar_porta(h._P3, 4)
        pad_usb.gadget_chegou(serial)
        return na_ordem(self, *a, **k)

    monkeypatch.setattr(alto_falante.AltoFalanteSubsystem, "_nos_na_ordem", _enumera_no_meio)
    mesa.volta(*(_chega(mesa, u) for u in _TODOS))
    assert _ancoras_publicadas(mesa) == portas


class TestOEndpointRecusaAPortaAlheia:
    """A guarda na origem: quem cria o endpoint confere a porta, e não só quem chama."""

    def _iniciar(self, mesa: Any, uniq: str, interface: str) -> tuple[bool, list[Any]]:
        ancora = eh.ancora_da_interface(interface)
        assert ancora is not None
        with structlog.testing.capture_logs() as registros:
            ok = eh.EndpointDeHaptica(uniq=uniq, ancora=ancora, runner=mesa.servidor).iniciar()
        return ok, registros

    def test_a_porta_de_outro_pad_e_recusada(self, mesa: Any) -> None:
        porta.dar_porta(h._P1, 1)
        da_p2 = porta.dar_porta(h._P2, 2)
        ok, registros = self._iniciar(mesa, h._P1, da_p2)
        assert ok is False
        assert _ditos(registros, "haptica_endpoint_recusa_porta_alheia")
        assert mesa.servidor.cargas == []

    def test_sem_porta_nenhuma_ancora_e_aceita(self, mesa: Any) -> None:
        ok, _ = self._iniciar(mesa, h._P1, _EMPRESTADA)
        assert ok is False
        assert mesa.servidor.cargas == []

    def test_a_propria_porta_e_aceita(self, mesa: Any) -> None:
        ok, _ = self._iniciar(mesa, h._P1, porta.dar_porta(h._P1, 7))
        assert ok is True
        assert mesa.servidor.cargas == [eh.nome_do_endpoint(h._P1)]


def test_o_doctor_nao_conta_mais_ancoras_livres() -> None:
    """A conta de âncoras livres do doctor saiu com o empréstimo."""
    doctor = (h.RAIZ / "scripts" / "doctor.sh").read_text(encoding="utf-8")
    assert "check_ancoras_dos_lugares_da_haptica" not in doctor
    assert not hasattr(eh, "distribuir_ancoras")
