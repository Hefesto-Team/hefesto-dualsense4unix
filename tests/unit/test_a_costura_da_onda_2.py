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
    """Um por vez vale também para o arrastar. A palavra dela:

    *«moveriamos por exemplo 1 controle por vez»* <!-- noqa-acento: citação literal dela -->

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


# ---------------------------------------------------------------------------
# 4. o «Ligar aqui» vale enquanto o controle ficar naquele adaptador
# ---------------------------------------------------------------------------

ADAPTADOR_A = "aa:bb:cc:00:00:a1"
ADAPTADOR_B = "aa:bb:cc:00:00:b2"
ADAPTADOR_C = "aa:bb:cc:00:00:c3"
CONTROLE_1 = "aa:bb:cc:00:00:01"
CONTROLE_2 = "aa:bb:cc:00:00:02"
CONTROLE_3 = "aa:bb:cc:00:00:03"
CONTROLE_4 = "aa:bb:cc:00:00:04"


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


class _Diario:
    def __init__(self) -> None:
        self.entradas: list[dict[str, Any]] = []

    def __call__(self, quem: str, o_que: str, por_que: str, **campos: Any) -> None:
        self.entradas.append({"quem": quem, "o_que": o_que, "por_que": por_que, **campos})


def _governador(onde: dict[str, str], relogio: _Relogio, **extra: Any) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov

    def adaptador_de(uniq: str) -> str:
        valor = onde[uniq]
        if isinstance(valor, Exception):
            raise valor
        return valor

    return gov.GovernadorDoRadio(
        adaptador_de=adaptador_de, registrar=_Diario(), relogio=relogio, **extra
    )


def _ela_liga_aqui_o_terceiro(onde: dict[str, Any], relogio: _Relogio) -> Any:
    """Dois no A, um no B: o terceiro do A pergunta, e ela responde «Ligar aqui»."""
    from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov

    governador = _governador(onde, relogio)
    for uniq in (CONTROLE_1, CONTROLE_2, CONTROLE_4):
        vaga = governador.pedir_vaga(uniq, "som")
        assert isinstance(vaga, gov.Vaga)
        vaga.subiu("som")
    assert isinstance(governador.pedir_vaga(CONTROLE_3, "som"), gov.Recusa)
    assert governador.ligar_aqui(CONTROLE_3) is True
    vaga = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(vaga, gov.Vaga) and vaga.por_escolha_dela
    vaga.subiu("som")
    vaga.soltar("a fonte do som secou")
    return governador


@pytest.mark.parametrize("longe", [ADAPTADOR_C, ""], ids=["movido", "desconectou"])
def test_o_ligar_aqui_cai_quando_o_controle_sai_do_adaptador(longe: str) -> None:
    """Ele saiu do adaptador cheio — movido, ou desconectado —, e voltou: a R3
    pergunta de novo. A ponte que desceu no meio NÃO gastou a resposta; quem a
    gasta é a saída, e quem vê a saída é o tique, pelo ``HID_PHYS``.

    MORDIDA: tire do ``GovernadorDoRadio.tique`` a chamada a
    ``conferir_as_autorizacoes`` — ele volta ao A e a ponte sobe além do limite
    sem perguntar, e esta régua reprova.
    """
    from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov

    onde: dict[str, Any] = {
        CONTROLE_1: ADAPTADOR_A, CONTROLE_2: ADAPTADOR_A, CONTROLE_3: ADAPTADOR_A,
        CONTROLE_4: ADAPTADOR_B,
    }
    relogio = _Relogio()
    governador = _ela_liga_aqui_o_terceiro(onde, relogio)

    # Enquanto ele fica no A, a resposta vale — o tique não a derruba.
    relogio.agora += gov.INTERVALO_DAS_AUTORIZACOES_S
    governador.tique()
    vibracao = governador.pedir_vaga(CONTROLE_3, "haptica")
    assert isinstance(vibracao, gov.Vaga) and vibracao.por_escolha_dela
    vibracao.soltar("a vibração parou")

    onde[CONTROLE_3] = longe
    relogio.agora += gov.INTERVALO_DAS_AUTORIZACOES_S
    governador.tique()
    onde[CONTROLE_3] = ADAPTADOR_A
    relogio.agora += gov.INTERVALO_DAS_AUTORIZACOES_S

    de_volta = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(de_volta, gov.Recusa), (
        "ele saiu do adaptador e voltou, e a ponte subiu além do limite sem perguntar"
    )
    assert de_volta.motivo == gov.MOTIVO_CHEIO


def test_pedir_vaga_em_outro_adaptador_tambem_derruba_a_resposta() -> None:
    """Movido, ele pediu som no adaptador novo antes de o tique olhar: a
    resposta do A cai ali mesmo, e na volta ao A a pergunta vem.

    MORDIDA: tire do ``pedir_vaga`` o descarte das autorizações de outro
    adaptador — sem tique no meio, ele volta ao A sem pergunta, e esta régua
    reprova.
    """
    from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov

    onde: dict[str, Any] = {
        CONTROLE_1: ADAPTADOR_A, CONTROLE_2: ADAPTADOR_A, CONTROLE_3: ADAPTADOR_A,
        CONTROLE_4: ADAPTADOR_B,
    }
    governador = _ela_liga_aqui_o_terceiro(onde, _Relogio())

    onde[CONTROLE_3] = ADAPTADOR_B
    no_b = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(no_b, gov.Vaga) and not no_b.alem_do_limite
    no_b.soltar("a fonte do som secou")

    onde[CONTROLE_3] = ADAPTADOR_A
    assert isinstance(governador.pedir_vaga(CONTROLE_3, "som"), gov.Recusa)


def test_nao_sei_onde_ele_esta_nao_derruba_a_resposta_dela() -> None:
    """O sysfs que some sob a mão é «não sei», e «não sei» não decide nada."""
    from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov

    onde: dict[str, Any] = {
        CONTROLE_1: ADAPTADOR_A, CONTROLE_2: ADAPTADOR_A, CONTROLE_3: ADAPTADOR_A,
        CONTROLE_4: ADAPTADOR_B,
    }
    relogio = _Relogio()
    governador = _ela_liga_aqui_o_terceiro(onde, relogio)

    onde[CONTROLE_3] = OSError("o hidraw sumiu no meio da leitura")
    relogio.agora += gov.INTERVALO_DAS_AUTORIZACOES_S
    assert governador.conferir_as_autorizacoes() == 0
    onde[CONTROLE_3] = ADAPTADOR_A
    vaga = governador.pedir_vaga(CONTROLE_3, "som")
    assert isinstance(vaga, gov.Vaga) and vaga.por_escolha_dela


def test_o_sysfs_ilegivel_do_leitor_de_verdade_tambem_e_nao_sei(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O «não sei» com o LEITOR DE PRODUÇÃO, e não com um dublê que levanta.

    A régua de cima prova o «não sei» com um ``adaptador_de`` que levanta
    ``OSError`` — e o leitor de produção nunca levantava:
    ``radio_da_mesa.adaptador_por_uniq`` engole o erro do ``/sys`` e devolve
    ``""``, e ``""`` é justamente o que ``conferir_as_autorizacoes`` lê como
    «desconectou». O ramo da régua era inalcançável no produto, e o hidraw
    ilegível derrubava a resposta dela. Aqui o leitor é o de verdade, sobre
    uma árvore de ``/sys`` de mentira.

    MORDIDA: tire do ``_adaptador_pelo_hid_phys`` o ``listar`` que não engole
    o erro — a raiz ilegível vira «desconectou» e esta régua reprova.
    """
    from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio

    raiz = tmp_path / "hidraw"

    def plugar(controle: str, adaptador: str) -> None:
        no = raiz / f"hidraw{controle[-1]}" / "device"
        no.mkdir(parents=True, exist_ok=True)
        (no / "uevent").write_text(
            f"HID_NAME=Wireless Controller\nHID_PHYS={adaptador}\nHID_UNIQ={controle}\n",
            encoding="utf-8",
        )

    for controle, adaptador in (
        (CONTROLE_1, ADAPTADOR_A), (CONTROLE_2, ADAPTADOR_A), (CONTROLE_3, ADAPTADOR_A),
        (CONTROLE_4, ADAPTADOR_B),
    ):
        plugar(controle, adaptador)
    monkeypatch.setattr(dualsense_bt_audio, "_SYSFS_HIDRAW", str(raiz))
    relogio = _Relogio()
    governador = gov.GovernadorDoRadio(registrar=_Diario(), relogio=relogio)
    for uniq in (CONTROLE_1, CONTROLE_2, CONTROLE_4):
        vaga = governador.pedir_vaga(uniq, "som")
        # O leitor de verdade leu a árvore: cada um no adaptador do HID_PHYS.
        assert isinstance(vaga, gov.Vaga)
        assert vaga.adaptador == (ADAPTADOR_B if uniq == CONTROLE_4 else ADAPTADOR_A)
        vaga.subiu("som")
    assert isinstance(governador.pedir_vaga(CONTROLE_3, "som"), gov.Recusa)
    assert governador.ligar_aqui(CONTROLE_3) is True

    # O /sys que não se lê — a raiz deixou de ser uma pasta: «não sei».
    ilegivel = tmp_path / "nao-e-pasta"
    ilegivel.write_text("", encoding="utf-8")
    monkeypatch.setattr(dualsense_bt_audio, "_SYSFS_HIDRAW", str(ilegivel))
    assert governador.conferir_as_autorizacoes() == 0, (
        "o /sys ilegível foi lido como «desconectou» e a resposta dela caiu"
    )

    # O controle de verdade: legível, e ele foi para o B — agora cai.
    monkeypatch.setattr(dualsense_bt_audio, "_SYSFS_HIDRAW", str(raiz))
    plugar(CONTROLE_3, ADAPTADOR_B)
    assert governador.conferir_as_autorizacoes() == 1


# ---------------------------------------------------------------------------
# 5. as vagas na ordem da D8
# ---------------------------------------------------------------------------


class _MedidorDaMesa:
    """O ar dos três adaptadores, com os enlaces ACL que o kernel lista em cada um."""

    def __init__(self, enlaces: dict[str, tuple[str, ...]]) -> None:
        self.enlaces = enlaces

    def amostrar(self) -> dict[str, Any]:
        from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar

        return {
            endereco: ar.ArDoAdaptador(
                hci=numero,
                endereco=endereco,
                conexoes=tuple(
                    ar.Enlace(handle=i + 1, endereco=u, tipo=ar.TIPO_ACL, saida=False,
                              estado=1, link_mode=0)
                    for i, u in enumerate(self.enlaces.get(endereco, ()))
                ),
                janela_s=0.25,
            )
            for numero, endereco in enumerate((ADAPTADOR_A, ADAPTADOR_B, ADAPTADOR_C))
        }


def _mesa(
    dono: bd.DonoVivo,
    relogio: rm.Relogio,
    *,
    pontes: dict[str, str | None],
) -> tuple[Any, Any]:
    """A mesma mesa para o governador e para a central.

    ``pontes`` é ``{controle: modo ou None}``; o C1, o C2 e o C3 estão no A, o
    C4 no B, e o C também existe (vazio). O C3 é o que pede vaga.
    """
    from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov

    onde = {
        CONTROLE_1: ADAPTADOR_A, CONTROLE_2: ADAPTADOR_A, CONTROLE_3: ADAPTADOR_A,
        CONTROLE_4: ADAPTADOR_B,
    }
    enlaces: dict[str, tuple[str, ...]] = {}
    for controle, adaptador in onde.items():
        enlaces[adaptador] = (*enlaces.get(adaptador, ()), controle)
    governador = _governador(
        onde, _Relogio(), medidor=_MedidorDaMesa(enlaces), nomear={
            ADAPTADOR_A: "Entrada 1", ADAPTADOR_B: "Entrada 2", ADAPTADOR_C: "Entrada 3",
        }.get,
    )
    governador.tique()  # a amostra do ar entra no governador
    for controle, modo in pontes.items():
        if modo is not None:
            vaga = governador.pedir_vaga(controle, modo)
            assert isinstance(vaga, gov.Vaga), controle
            vaga.subiu(modo)

    central = cr.CentralDoRadio(
        dono=dono,
        onde_esta=lambda u: onde.get(":".join(u[i : i + 2] for i in range(0, 12, 2)), ""),
        relogio=relogio,
        dormir=relogio.dormir,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"},
    )
    central.conhecer([
        {
            "uniq": controle.replace(":", ""),
            "transport": "bt",
            "connected": True,
            "adaptador": adaptador,
            "ponte_do_radio": pontes.get(controle),
        }
        for controle, adaptador in onde.items()
    ])
    return governador, central


@pytest.mark.parametrize(
    ("pontes", "esperada"),
    [
        # O B tem uma ponte e o C nenhuma: mais vaga de ponte primeiro.
        ({CONTROLE_1: "som", CONTROLE_2: "som", CONTROLE_4: "som"},
         (ADAPTADOR_C, ADAPTADOR_B)),
        # Vaga igual; o B tem um controle e o C nenhum: menos controles primeiro.
        ({CONTROLE_1: "som", CONTROLE_2: "haptica", CONTROLE_4: None},
         (ADAPTADOR_C, ADAPTADOR_B)),
    ],
    ids=["mais-vaga", "menos-controles"],
)
def test_as_vagas_da_recusa_saem_na_ordem_da_d8_da_central(
    diario: Path,
    dono: bd.DonoVivo,
    relogio: rm.Relogio,
    pontes: dict[str, str | None],
    esperada: tuple[str, ...],
) -> None:
    """A tela pergunta «Mover para a primeira vaga?», e a central, sem destino
    pedido, escolhe pela D8. As duas respostas são a MESMA — e a frase diz os
    nomes nessa ordem.

    Nas duas mesas o endereço do B é menor que o do C, e é o C que a D8 escolhe.

    MORDIDA: devolva do ``_adaptadores_com_vaga`` as vagas por endereço (sem o
    ``_na_ordem_da_d8``) — o B vem primeiro, contra a central, e esta régua
    reprova.
    """
    from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov

    governador, central = _mesa(dono, relogio, pontes=pontes)

    recusa = governador.pedir_vaga(CONTROLE_3, "som")

    assert isinstance(recusa, gov.Recusa)
    assert recusa.vagas == esperada
    assert central.escolher_destino(CONTROLE_3) == recusa.vagas[0], (
        "a tela e a central divergem sobre «para onde»"
    )
    [pedido] = governador.publicar()[ADAPTADOR_A]["pedidos"]
    assert tuple(pedido["vagas"]) == esperada
    assert recusa.frase.endswith("Há vaga na Entrada 3 e na Entrada 2.")


# ---------------------------------------------------------------------------
# 6. um dono do nome da porta
# ---------------------------------------------------------------------------


class _DonoDoNome:
    """O ``entrada_a_entrada.nome_da_porta`` de mentira: responde «Sala» e anota."""

    def __init__(self, nomes: dict[str, str]) -> None:
        self.nomes = nomes
        self.perguntas: list[str] = []

    def __call__(self, chave: str, **_k: Any) -> str | None:
        self.perguntas.append(chave)
        return self.nomes.get(chave)


def test_o_governador_pergunta_o_nome_ao_dono_da_entrada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A frase da recusa diz o nome que o DONO diz — o que ela deu à porta.

    MORDIDA: volte o ``governador_do_radio.nome_da_porta`` a compor a palavra
    com o número do mapa ou o ``devpath`` — a porta vira «Entrada 4.1.4» em vez
    do nome dela, e esta régua reprova.
    """
    from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
    from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
    from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
    from hefesto_dualsense4unix.integrations import mesa_de_radio

    dono_do_nome = _DonoDoNome({"3-4.1.4": "Sala"})
    monkeypatch.setattr(ee, "nome_da_porta", dono_do_nome)
    monkeypatch.setattr(bd, "a_suite_esta_rodando", lambda: False)
    monkeypatch.setattr(bd, "enderecos_pelo_kernel", lambda *_a, **_k: {})
    monkeypatch.setattr(
        mesa_de_radio,
        "adaptadores_bluetooth",
        lambda **_k: [
            mesa_de_radio.Adaptador(interface="hci3", no="/x/3-4.1.4", busnum=3, devpath="4.1.4"),
            mesa_de_radio.Adaptador(interface="hci4", no="/x/3-1.4", busnum=3, devpath="1.4"),
        ],
    )
    amostra = {
        ADAPTADOR_A: ar.ArDoAdaptador(hci=3, endereco=ADAPTADOR_A),
        ADAPTADOR_B: ar.ArDoAdaptador(hci=4, endereco=ADAPTADOR_B),
    }

    assert gov.nome_da_porta(ADAPTADOR_A, amostra=amostra) == "Sala"
    # A porta que ela não nomeou não ganha nome inventado.
    assert gov.nome_da_porta(ADAPTADOR_B, amostra=amostra) == ""
    assert dono_do_nome.perguntas == ["3-4.1.4", "3-1.4"]

    recusa = gov.Recusa(
        CONTROLE_3, ADAPTADOR_A, "som", gov.MOTIVO_CHEIO, (ADAPTADOR_B,),
        nomear=lambda e: gov.nome_da_porta(e, amostra=amostra),
    )
    assert recusa.frase == (
        "O Sala já tem 2 controles com som ou vibração. Há vaga em outro adaptador."
    )


def test_a_secao_mesa_pergunta_o_nome_ao_dono_da_entrada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A coluna «Onde está» diz o nome que o dono diz — e a procedência continua
    no ``title``, com o número do mapa e o caminho do sistema.

    MORDIDA: volte o ``_onde_esta_o_adaptador`` a compor «Entrada N» com o
    número do mapa — a coluna ignora o dono, e esta régua reprova.
    """
    from tests.conftest import exigir_gi_real

    exigir_gi_real("a coluna 'Onde está' da secao_mesa")
    from hefesto_dualsense4unix.app.actions.config.secao_mesa import (
        _onde_esta_o_adaptador,
        _onde_esta_o_radio,
    )
    from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador, RadioUsb
    from hefesto_dualsense4unix.utils.maquina import MapaDaMesa, PortaDeclarada

    dono_do_nome = _DonoDoNome({"3-1.2": "Sala", "4-4": "Rack da TV"})
    monkeypatch.setattr(ee, "nome_da_porta", dono_do_nome)
    mapa = MapaDaMesa(
        portas={"9": PortaDeclarada(caminho="3-1.2"), "7": PortaDeclarada(caminho="4-4")}
    )
    adaptador = Adaptador(
        interface="hci0", no="/mentira/3-1.2", vid="2357", pid="0604", busnum=3,
        devpath="1.2", painel="right",
    )
    wifi = RadioUsb(no="/mentira/4-4", vid="2357", pid="012d", busnum=4, devpath="4")

    texto, dica = _onde_esta_o_adaptador(adaptador, mapa)
    assert texto == "Sala"
    assert dica is not None and "entrada 9" in dica and "3-1.2" in dica
    assert _onde_esta_o_radio(wifi, None, mapa) == "Rack da TV"
    assert dono_do_nome.perguntas == ["3-1.2", "4-4"]
    # Sem mapa, a seção nem pergunta: a frase de hoje, letra por letra.
    assert _onde_esta_o_adaptador(adaptador) == ("Barramento 3, porta 1.2 · Direita", None)


def test_a_frase_e_a_coluna_dizem_o_mesmo_nome_da_mesma_porta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A MESMA porta, as duas telas, o MESMO nome — com o dono de verdade.

    A régua de cima troca o dono por um dublê que ignora o que recebe, e por
    isso não via o que a coluna PERGUNTAVA: a ``secao_mesa`` montava um
    ``maquina.json`` só com o ``mapa`` e sem os barramentos, e o dono,
    perguntado sem os ``lugares``, não achava o nome que ela deu ao lugar.
    Medido em 23/09 na conferência: a frase da recusa dizia «o Extensor à
    esquerda já tem 2 controles…» e a coluna «Onde está», sobre o mesmo
    adaptador, dizia «Entrada 9». Dois nomes para uma porta é o segundo dono
    que o item 6 existe para matar.

    MORDIDA: volte o ``secao_mesa._nome_da_entrada`` a perguntar com
    ``MaquinaConfig(mapa=mapa)`` e ``controladores={}`` — a coluna diz
    «Entrada 9» e esta régua reprova.
    """
    from tests.conftest import exigir_gi_real

    exigir_gi_real("a coluna 'Onde está' da secao_mesa")
    from hefesto_dualsense4unix.app.actions.config import secao_mesa
    from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
    from hefesto_dualsense4unix.integrations import ar_do_adaptador as ar
    from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
    from hefesto_dualsense4unix.integrations import mesa_de_radio
    from hefesto_dualsense4unix.utils import maquina

    pci = "0000:0c:00.3"
    no_extensor = mesa_de_radio.Adaptador(
        interface="hci3", no="/mentira/3-4.1.4", vid="2357", pid="0604", busnum=3,
        devpath="4.1.4", controlador_pci=pci,
    )
    documento = maquina.MaquinaConfig(
        mapa=maquina.MapaDaMesa(portas={"9": maquina.PortaDeclarada(caminho="3-4.1.4")}),
        lugares={
            maquina.lugar_de(pci, "4.1.4"): maquina.LugarDeclarado(nome="Extensor à esquerda")
        },
    )
    # O disco dela e os barramentos deste boot, sem ler nada da máquina dela.
    monkeypatch.setattr(ee, "carregar_maquina", lambda: documento)
    monkeypatch.setattr(secao_mesa, "carregar_maquina", lambda: documento)
    monkeypatch.setattr(ee, "_controladores_do_sistema", lambda: {3: pci})
    # O governador acha o adaptador pelo kernel; a suíte o calaria.
    monkeypatch.setattr(bd, "a_suite_esta_rodando", lambda: False)
    monkeypatch.setattr(bd, "enderecos_pelo_kernel", lambda *_a, **_k: {})
    monkeypatch.setattr(mesa_de_radio, "adaptadores_bluetooth", lambda **_k: [no_extensor])
    amostra = {ADAPTADOR_A: ar.ArDoAdaptador(hci=3, endereco=ADAPTADOR_A)}

    na_frase = gov.nome_da_porta(ADAPTADOR_A, amostra=amostra)
    na_coluna, _dica = secao_mesa._onde_esta_o_adaptador(no_extensor, documento.mapa)

    assert na_frase == "Extensor à esquerda"
    assert na_coluna == na_frase, (
        f"a frase diz {na_frase!r} e a coluna diz {na_coluna!r} sobre a mesma porta"
    )


#: Quem pode compor o nome da porta, e por quê. Tudo o mais em ``src/`` que junte
#: a palavra «Entrada» com um número é um segundo dono.
_O_DONO = "integrations/entrada_a_entrada.py"
_OS_QUE_PODEM = {
    (_O_DONO, "define a palavra"): "é o dono (ENTRADA-A-ENTRADA-01)",
    (_O_DONO, "compõe com a palavra"): "é o dono (ENTRADA-A-ENTRADA-01)",
    ("app/widgets/calibrar_entradas.py", "define a palavra"): (
        "a cópia que o gerador da aba 08 lê por AST — não importa do dono sem "
        "quebrar o gerador; travada junto por test_entrada_a_entrada_grava.py"
    ),
    ("gui/aba_conexoes.py", "compõe uma f-string"): (
        "html_dos_adaptadores diz «Entrada <painel do kernel>». ACHADO DA "
        "A-COSTURA-DA-ONDA-2-01, fora da posse dela: o único chamador é o "
        "interface/conexoes_vivas.py, da TRANSPLANTE-DA-SECAO-01, que substitui "
        "a seção cx8-3 inteira. Quem a fechar tira esta linha."
    ),
}


def _composicoes_da_palavra(raiz: Path) -> set[tuple[str, str]]:
    """``(arquivo, forma)`` de toda string de CÓDIGO que junta «Entrada» a um valor.

    Docstring não conta: prosa que descreve o padrão não é o padrão.
    """
    import ast
    import itertools
    import re

    palavra_no_fim = re.compile(r"\bEntrada\s*$")
    achados: set[tuple[str, str]] = set()
    for arquivo in sorted(raiz.rglob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        docstrings = {
            id(no.body[0].value)
            for no in ast.walk(arvore)
            if isinstance(no, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            and no.body
            and isinstance(no.body[0], ast.Expr)
            and isinstance(no.body[0].value, ast.Constant)
        }
        nome = str(arquivo.relative_to(raiz))
        for no in ast.walk(arvore):
            if isinstance(no, ast.JoinedStr):
                partes = no.values
                for atual, seguinte in itertools.pairwise(partes):
                    if (
                        isinstance(atual, ast.Constant)
                        and isinstance(atual.value, str)
                        and palavra_no_fim.search(atual.value)
                        and isinstance(seguinte, ast.FormattedValue)
                    ):
                        achados.add((nome, "compõe uma f-string"))
                if any(
                    isinstance(p, ast.FormattedValue)
                    and isinstance(p.value, ast.Name)
                    and p.value.id == "PALAVRA_DA_ENTRADA"
                    for p in partes
                ):
                    achados.add((nome, "compõe com a palavra"))
            elif (
                isinstance(no, ast.Constant)
                and isinstance(no.value, str)
                and id(no) not in docstrings
                and re.search(r"\bEntrada \{", no.value)
            ):
                achados.add((nome, "tem um modelo de .format"))
            elif (
                isinstance(no, ast.BinOp)
                and isinstance(no.op, ast.Add)
                and isinstance(no.left, ast.Constant)
                and isinstance(no.left.value, str)
                and palavra_no_fim.search(no.left.value)
            ):
                achados.add((nome, "compõe por soma"))
            elif isinstance(no, (ast.Assign, ast.AnnAssign)):
                alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
                if any(isinstance(a, ast.Name) and a.id == "PALAVRA_DA_ENTRADA" for a in alvos):
                    achados.add((nome, "define a palavra"))
    return achados


def test_o_nome_da_porta_tem_um_dono_so() -> None:
    """Um dono do nome da porta: o da ENTRADA. Havia três compositores — o
    governador, a ``secao_mesa`` e o dono —, com três ``PALAVRA_DA_ENTRADA``.

    A lista de quem pode é FECHADA nos dois sentidos: um compositor novo
    reprova, e uma exceção que deixou de existir também (tire-a daqui).

    MORDIDA: devolva ao governador a ``PALAVRA_DA_ENTRADA`` e a composição com o
    ``devpath`` — esta régua reprova nomeando o arquivo.
    """
    achados = _composicoes_da_palavra(RAIZ / "src" / "hefesto_dualsense4unix")
    intrusos = sorted(achados - set(_OS_QUE_PODEM))
    caducos = sorted(set(_OS_QUE_PODEM) - achados)
    assert not intrusos, f"um segundo dono do nome da porta: {intrusos}"
    assert not caducos, f"a exceção deixou de existir — tire-a de _OS_QUE_PODEM: {caducos}"
