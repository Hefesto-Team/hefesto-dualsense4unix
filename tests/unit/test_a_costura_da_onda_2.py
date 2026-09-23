"""O que a MOVER, a GOVERNADOR-02 e a ENTRADA deixaram entre si — A-COSTURA-DA-ONDA-2-01.

As três foram aprovadas e integradas em 23/09; as conferências deixaram
costuras entre elas, e quem coordena decidiu todas. Uma régua por item, e cada
uma MORDE:

1. **um por vez vale também para o arrastar** — com um movimento em curso,
   nenhum outro começa (``status: "ocupado"``, o botão treme);
2. **uma chave, um sentido** — no ``radio_central``, ``controle`` é o ``uniq``
   da proposta; o booleano dos movimentos se chama ``e_controle``;
3. **o desligamento fecha a central** — o ``Pairable`` do destino não fica
   ``true`` quando o daemon para no meio da janela;
4. **o «Ligar aqui» vale enquanto o controle ficar naquele adaptador** — a
   ponte que desce e sobe não pergunta de novo; o controle que sai, sim;
5. **as vagas na ordem da D8** — a mesma ``ordem_dos_destinos`` da central;
6. **um dono do nome da porta** — o da ENTRADA; o governador e a
   ``secao_mesa`` perguntam a ele.

O mundo é o ``radio_de_mentira`` da MOVER, com o ``DonoVivo`` de verdade por
cima. Nada aqui fala com o rádio, o BlueZ, o daemon ou o diário dela.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import diario_do_radio
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, SALA, VARANDA, VERDE, VERMELHO

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trava e o diário numa pasta de teste — nunca os dela, em ``/run``."""
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    caminho = tmp_path / "radio-diario.jsonl"
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(caminho))
    return caminho


@pytest.fixture()
def mundo() -> rm.RadioDeMentira:
    """A sala com o vermelho e o azul; o quarto e a varanda livres."""
    radio = rm.RadioDeMentira()
    radio.pareado(SALA, VERMELHO)
    radio.pareado(SALA, AZUL)
    return radio


@pytest.fixture()
def dono(mundo: rm.RadioDeMentira) -> Iterator[bd.DonoVivo]:
    vivo = bd.DonoVivo(mundo)
    assert vivo.ligar()
    yield vivo
    vivo.fechar()


@pytest.fixture()
def relogio() -> rm.Relogio:
    return rm.Relogio()


def _central(
    dono: bd.LeitorDoBluez, mundo: rm.RadioDeMentira, relogio: rm.Relogio, **extra: Any
) -> cr.CentralDoRadio:
    return cr.CentralDoRadio(
        dono=dono,
        onde_esta=mundo.onde_esta,
        movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte,
        relogio=relogio,
        dormir=relogio.dormir,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"},
        **extra,
    )


def _handlers(daemon: Any) -> Any:
    from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

    class _Handlers(IpcHandlersMixin):
        def __init__(self, alvo: Any) -> None:
            self.daemon = alvo

    return _Handlers(daemon)


def _o_vermelho_fica_esperando(
    mundo: rm.RadioDeMentira, relogio: rm.Relogio, central: cr.CentralDoRadio
) -> cr.Movimento:
    """O ``Pair`` diz que deu e o controle não chega: «esperando», e a trava livre."""
    mundo.pair_mente = True
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))
    feito = central.mover(VERMELHO, QUARTO)
    assert (feito.estado, feito.passo) == (cr.ESPERANDO, cr.PASSO_CONFERINDO)
    return feito


# ---------------------------------------------------------------------------
# 1. um por vez vale também para o arrastar
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_com_um_movimento_esperando_nenhum_outro_comeca(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """A palavra dela: *«moveriamos por exemplo 1 controle por vez»*. <!-- noqa-acento: citação literal dela -->

    O vermelho foi pareado no quarto e espera a conferência — a trava já está
    livre. Arrastar o azul, conectar um controle novo ou mandar o próprio
    vermelho para outro lugar volta «ocupado» na hora: sem fio, sem janela,
    sem uma escrita no rádio. O mesmo pedido de novo segue devolvendo o mesmo
    movimento (a idempotência da MOVER não muda).

    MORDIDA: faça o ``CentralDoRadio._ocupada`` responder só pelo ``_parar``
    (sem o ``em_curso``) — o azul abre a janela na varanda e esta régua reprova.
    """
    from types import SimpleNamespace

    central = _central(dono, mundo, relogio)
    primeiro = _o_vermelho_fica_esperando(mundo, relogio, central)
    chamadas, escritas = len(mundo.chamadas), len(mundo.escritas)

    recusas = {
        "o azul, arrastado": central.comecar_a_mover(AZUL, VARANDA),
        "um controle novo": central.comecar_a_conectar(VARANDA),
        "o vermelho, para outro lugar": central.comecar_a_mover(VERMELHO, VARANDA),
        "o corpo do fio, direto": central.mover(AZUL, VARANDA),
        "o conectar, direto": central.conectar(VARANDA),
    }
    for quem, recusa in recusas.items():
        assert (recusa.estado, recusa.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_OCUPADO), quem

    # O mesmo pedido devolve o mesmo movimento.
    assert central.comecar_a_mover(VERMELHO, QUARTO) == primeiro
    # A tela lê «ocupado»: o botão treme.
    resposta = await _handlers(SimpleNamespace(_central_do_radio=central))._handle_radio_mover(
        {"aparelho": rm.uniq(AZUL), "destino": VARANDA}
    )
    assert resposta["status"] == "ocupado"

    # Nada mudou: a recusa não fica guardada, nenhum fio nasceu, o rádio calado.
    assert [m.aparelho for m in central.movimentos()] == [VERMELHO]
    assert central.movimento_de(VERMELHO) == primeiro
    assert set(central._fios) <= {VERMELHO}, "a recusa abriu um fio"
    assert mundo.chamadas[chamadas:] == []
    assert mundo.escritas[escritas:] == []
    assert [c for c, _a in mundo.metodos("StartDiscovery")] == [rm.HCIS[QUARTO]]
    central.fechar()


def test_quem_esperou_a_trava_confere_de_novo_com_ela_na_mao(
    diario: Path,
    mundo: rm.RadioDeMentira,
    dono: bd.DonoVivo,
    relogio: rm.Relogio,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dois pedidos quase juntos: os dois passam pela primeira olhada, e só um move.

    Outro motor segura a trava; o vermelho e o azul pedem e ficam esperando
    por ela — nenhum dos dois viu movimento em curso. A trava sai: o primeiro
    pareia e fica «esperando» a conferência, já sem a trava; o segundo, com a
    trava na mão, olha de novo e recusa. Uma janela só.

    MORDIDA: tire do :meth:`CentralDoRadio.mover` a segunda olhada (a de
    dentro da trava) — o segundo abre outra janela e esta régua reprova.
    """
    central = _central(dono, mundo, relogio)
    mundo.pair_mente = True
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(AZUL))

    chegaram = threading.Semaphore(0)
    de_verdade = bd.na_trava

    @contextlib.contextmanager
    def contando(quem: str = bd.QUEM_PADRAO, *, prazo_s: float | None = None) -> Iterator[float]:
        chegaram.release()
        with de_verdade(quem, prazo_s=prazo_s) as esperou:
            yield esperou

    monkeypatch.setattr(bd, "na_trava", contando)
    fins: dict[str, cr.Movimento] = {}
    fios = [
        threading.Thread(target=lambda a=a, d=d: fins.__setitem__(a, central.mover(a, d)))
        for a, d in ((VERMELHO, QUARTO), (AZUL, VARANDA))
    ]
    with diario_do_radio.trava_do_radio("vigia"):
        for fio in fios:
            fio.start()
        # Os dois passaram pela primeira olhada e esperam a trava.
        assert chegaram.acquire(timeout=5) and chegaram.acquire(timeout=5)
    for fio in fios:
        fio.join(timeout=10)

    desfechos = sorted((m.estado, m.motivo) for m in fins.values())
    assert desfechos == [
        (cr.ESPERANDO, cr.MOTIVO_SEM_CONFIRMACAO),
        (cr.NAO_CHEGOU, cr.MOTIVO_OCUPADO),
    ], desfechos
    assert len(mundo.metodos("StartDiscovery")) == 1, "duas janelas abriram"


# ---------------------------------------------------------------------------
# 2. uma chave, um sentido
# ---------------------------------------------------------------------------


def _controle(u: str, adaptador: str, ponte: str | None = None) -> dict[str, Any]:
    return {
        "uniq": rm.uniq(u),
        "transport": "bt",
        "connected": True,
        "adaptador": adaptador,
        "ponte_do_radio": ponte,
    }


def _chaves(no: Any, nome: str) -> list[Any]:
    """Todo valor da chave ``nome``, em qualquer fundura do publicado."""
    achados: list[Any] = []
    if isinstance(no, dict):
        for chave, valor in no.items():
            if chave == nome:
                achados.append(valor)
            achados.extend(_chaves(valor, nome))
    elif isinstance(no, list):
        for item in no:
            achados.extend(_chaves(item, nome))
    return achados


def test_no_radio_central_controle_e_sempre_o_uniq(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo, relogio: rm.Relogio
) -> None:
    """``controle`` quer dizer UMA coisa no ``state_full["radio_central"]``.

    Na ``proposta`` do «Equilibrar» é o ``uniq`` de quem se move — é o que a
    tela manda de volta em ``radio.mover``. Nos ``movimentos[]`` era um
    booleano com o mesmo nome; agora é ``e_controle``.

    MORDIDA: volte o ``Movimento.publicar`` a escrever ``"controle"`` — a mesma
    chave aparece booleana e esta régua reprova.
    """
    mundo.pareado(SALA, VERDE)
    mundo.pareado(SALA, rm.ROXO)
    dono._fotografar()
    central = _central(dono, mundo, relogio)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))
    assert central.mover(VERMELHO, QUARTO).estado == cr.CHEGOU

    publicado = central.publicar([
        _controle(VERMELHO, QUARTO, "som"),
        _controle(AZUL, SALA, "som"),
        _controle(VERDE, SALA, "haptica"),
        _controle(rm.ROXO, SALA, "som"),
    ])

    [movimento] = publicado["movimentos"]
    assert movimento["e_controle"] is True
    assert "controle" not in movimento
    assert publicado["proposta"] is not None, "a régua precisa da proposta para medir"
    sentidos = _chaves(publicado, "controle")
    assert sentidos, "nenhuma chave `controle` para conferir"
    for valor in sentidos:
        assert isinstance(valor, str) and len(valor) == 12, (
            f"`controle` com outro sentido no radio_central: {valor!r}"
        )
    assert all(isinstance(v, bool) for v in _chaves(publicado, "e_controle"))


# ---------------------------------------------------------------------------
# 3. o desligamento fecha a central
# ---------------------------------------------------------------------------


def _daemon_de_mentira() -> Any:
    """O ``Daemon`` de verdade, com o controle de mentira e nada ligado."""
    from hefesto_dualsense4unix.core.controller import ControllerState
    from hefesto_dualsense4unix.core.events import EventBus
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    estado = ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb"
    )
    return Daemon(
        controller=FakeController(transport="usb", states=[estado]),
        bus=EventBus(),
        config=DaemonConfig(
            poll_hz=120,
            auto_reconnect=False,
            ipc_enabled=False,
            udp_enabled=False,
            autoswitch_enabled=False,
            mouse_emulation_enabled=False,
            keyboard_emulation_enabled=False,
            mic_button_toggles_system=False,
            plugins_enabled=False,
        ),
    )


def _esperar(condicao: Any, teto: float = 5.0) -> bool:
    import time

    fim = time.monotonic() + teto
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return bool(condicao())


@pytest.mark.asyncio
async def test_o_desligamento_fecha_a_central_e_o_pairable_volta(
    diario: Path, mundo: rm.RadioDeMentira, dono: bd.DonoVivo
) -> None:
    """O daemon para no meio da janela: o ``Pairable`` do destino volta a ``false``.

    A janela de pareamento liga o ``Pairable`` SÓ durante o gesto, e quem o
    devolve é o fio da central — que só solta a espera do PS + Create quando vê
    o ``fechar()``. O relógio aqui é o de verdade, e a janela é de um minuto:
    sem o ``shutdown`` fechar a central, ela seguiria aberta depois do daemon.

    MORDIDA: tire do ``connection.shutdown`` o bloco da central — o
    ``Pairable`` do quarto fica ``true`` e esta régua reprova.
    """
    import asyncio

    from hefesto_dualsense4unix.daemon.connection import shutdown

    daemon = _daemon_de_mentira()
    central = cr.CentralDoRadio(
        dono=dono,
        onde_esta=mundo.onde_esta,
        movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"},
        segundos_da_janela=60,
    )
    daemon._central_do_radio = central
    try:
        feito = await asyncio.to_thread(central.comecar_a_mover, VERMELHO, QUARTO)
        assert feito.estado == cr.ESPERANDO
        assert await asyncio.to_thread(
            _esperar, lambda: mundo.propriedade_do_adaptador(QUARTO, "Pairable") is True
        ), "a janela não abriu"

        await shutdown(daemon)

        assert mundo.propriedade_do_adaptador(QUARTO, "Pairable") is False, (
            "o daemon parou e o Pairable do destino ficou ligado"
        )
        assert central.movimento_de(VERMELHO).estado == cr.NAO_CHEGOU
        assert not any(fio.is_alive() for fio in central._fios.values())
        # Fechada, a central não abre outra janela.
        assert central.comecar_a_mover(AZUL, VARANDA).motivo == cr.MOTIVO_OCUPADO
        assert mundo.escritas_no(VARANDA, "Pairable") == []
    finally:
        central.fechar()
