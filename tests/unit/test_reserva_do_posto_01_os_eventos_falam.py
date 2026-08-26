"""RESERVA-DO-POSTO-01 §5 — os três desfechos da reserva falam no journal.

O defeito, medido em 26/08/2026: dos três eventos do mecanismo que decide QUEM
é o Jogador 1 depois de uma piscada no rádio, só o BEM-SUCEDIDO aparecia numa
instalação normal.

    primario_deposto_reservado   -> logger.debug   (invisível em INFO)
    primario_reserva_caducou     -> logger.debug   (invisível em INFO)
    primario_retomou_o_posto     -> logger.info    (o único que aparecia)

O nível padrão do produto é INFO (`utils/logging_config.py`). Perguntar a esse
journal com que frequência o posto se perde seria contar apenas as amostras que
confirmam a resposta desejada — e a decisão que espera essa medição é o valor
de `PRIMARIO_RESERVA_SEC`, que **não se mexe aqui**: ele só se decide depois da
bancada, e a bancada é dela.

A régua deste arquivo é o CONFIG REAL do produto, no nível PADRÃO: se os
eventos voltarem a `debug`, eles somem daqui exatamente como sumiam do journal
dela.
"""
from __future__ import annotations

import io
import json
import threading
from collections.abc import Iterator

import pytest
import structlog

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.backend_pydualsense import (
    PRIMARIO_RESERVA_SEC,
    PyDualSenseController,
)

#: Endereços didáticos da casa — máscara de octetos 4 e 5 zerados.
P1 = "aabbcc0000f1"
P2 = "aabbcc0000f2"


class _HandleFalso:
    connected = True

    def close(self) -> None:
        return None


class _EvdevMudo:
    def __init__(self) -> None:
        self.alvos: list[str | None] = []

    def retarget(self, uniq: str | None) -> None:
        self.alvos.append(uniq)

    def refresh_device(self) -> None:
        return None

    def is_available(self) -> bool:
        return False


class _Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


def _backend(handles: dict[str, _HandleFalso], primario: str | None) -> PyDualSenseController:
    """Um `PyDualSenseController` com a mesa montada e nada mais.

    `__new__` de propósito: os métodos medidos aqui são os REAIS
    (`_reservar_o_posto_de_primario`, `_posto_reservado_de_volta`,
    `_recompute_primary`), e o `__init__` abriria hidraw, evdev e threads.
    """
    ctrl = PyDualSenseController.__new__(PyDualSenseController)
    ctrl._io_lock = threading.RLock()
    ctrl._handles = handles
    ctrl._primary_key = primario
    ctrl._primario_deposto = None
    ctrl._primary_change_observer = None
    ctrl._motion_reader = None
    ctrl._evdev = _EvdevMudo()
    ctrl._transport = None
    ctrl._relogio = _Relogio()
    # O transporte real abriria o handle; aqui o que se mede é o journal.
    ctrl._detect_transport = lambda handle: "bt"  # type: ignore[method-assign]
    return ctrl


@pytest.fixture
def journal(monkeypatch: pytest.MonkeyPatch) -> Iterator[io.StringIO]:
    """O `logger` do backend, com o FILTRO DE NÍVEL REAL do produto, num buffer.

    O `wrapper_class` vem de `structlog.get_config()` — é o mesmo objeto que o
    `configure_logging` do produto instalou (`make_filtering_bound_logger` no
    nível padrão, INFO). É ele, e só ele, que decide o que passa: trocamos o
    destino da escrita, nunca a régua.

    **Nada de reconfigurar o structlog global**, e isto é cicatriz de hoje: uma
    primeira versão desta régua chamava `reset_for_tests()` +
    `configure_logging(stream=...)`, o que troca a LISTA de processadores por
    outra. O `structlog.testing.capture_logs()` — que outros testes desta suíte
    usam — mexe naquela lista NO LUGAR justamente para alcançar os loggers já
    cacheados (`cache_logger_on_first_use=True`); com a lista trocada, ele
    passa a mexer numa lista que ninguém mais lê, e
    `test_session_persist.py::test_boot_marker_orfao_cai_no_session_json`
    reprovava a dez arquivos de distância. Instrumento que estraga a medição do
    vizinho não é instrumento.
    """
    buf = io.StringIO()
    monkeypatch.setattr(
        bp,
        "logger",
        structlog.wrap_logger(
            structlog.PrintLogger(file=buf),
            wrapper_class=structlog.get_config()["wrapper_class"],
            processors=[
                structlog.processors.add_log_level,
                structlog.processors.JSONRenderer(),
            ],
        ),
    )
    yield buf


def _eventos(buf: io.StringIO) -> list[dict[str, object]]:
    linhas = [linha for linha in buf.getvalue().splitlines() if linha.strip()]
    return [json.loads(linha) for linha in linhas]


def _nomes(buf: io.StringIO) -> list[str]:
    return [str(evento.get("event")) for evento in _eventos(buf)]


def test_a_regua_recusa_o_que_esta_abaixo_do_padrao(journal: io.StringIO) -> None:
    """Valida o INSTRUMENTO antes de acreditar nele: em INFO, `debug` não passa.

    Sem esta linha, um buffer que capturasse TUDO faria os três eventos
    aparecerem mesmo em `debug`, e a régua diria "verde" para o defeito.

    Se ESTA linha reprovar, o produto não está no nível padrão: alguém exportou
    `HEFESTO_DUALSENSE4UNIX_LOG_LEVEL=DEBUG`, e a pergunta deste arquivo — "o
    que o journal dela guarda sem ninguém pedir nada" — não tem como ser feita.
    """
    bp.logger.info("evento_de_teste_em_info", key=P1)
    bp.logger.debug("evento_de_teste_em_debug", key=P1)

    assert "evento_de_teste_em_info" in _nomes(journal)
    assert "evento_de_teste_em_debug" not in _nomes(journal), (
        "o buffer está capturando DEBUG — a régua não distingue o nível e não "
        "mede nada"
    )


def test_a_queda_aparece_no_nivel_padrao(journal: io.StringIO) -> None:
    """A MORDIDA: os três desfechos da reserva, todos visíveis em INFO.

    Devolvendo qualquer um deles a `logger.debug`, sobra só o desfecho
    bem-sucedido e o teste reprova nomeando os que sumiram.
    """
    # 1. o primário cai e o posto fica reservado a ele
    reserva = _backend({P1: _HandleFalso()}, primario=P1)
    reserva._reservar_o_posto_de_primario(P1)

    # 2. ele não volta a tempo — a reserva caduca
    caduca = _backend({P2: _HandleFalso()}, primario=P2)
    caduca._reservar_o_posto_de_primario(P1)
    caduca._relogio.agora += PRIMARIO_RESERVA_SEC + 1.0
    assert caduca._posto_reservado_de_volta() is None

    # 3. e o desfecho que sempre apareceu: ele volta dentro da janela
    handles = {P2: _HandleFalso(), P1: _HandleFalso()}
    retoma = _backend(handles, primario=P1)
    retoma._reservar_o_posto_de_primario(P1)
    retoma._primary_key = P2  # o outro sentou no posto enquanto ele estava fora
    retoma._recompute_primary()
    assert retoma._primary_key == P1

    esperados = {
        "primario_deposto_reservado",
        "primario_reserva_caducou",
        "primario_retomou_o_posto",
    }
    vistos = set(_nomes(journal))
    faltando = sorted(esperados - vistos)
    assert not faltando, (
        f"no nível padrão (INFO) o journal não guardou {faltando} — só "
        f"{sorted(esperados & vistos)} aparece, e medir a reserva com esse "
        "instrumento é contar apenas as amostras que confirmam o resultado bom"
    )


def test_os_tres_eventos_correlacionam_pelo_mesmo_endereco(
    journal: io.StringIO,
) -> None:
    """Os três carregam a chave `key` — é ela que casa reserva com desfecho.

    Sem a chave em comum, três linhas soltas no journal não dizem se o controle
    que caiu foi o mesmo que voltou.
    """
    handles = {P2: _HandleFalso(), P1: _HandleFalso()}
    backend = _backend(handles, primario=P1)
    backend._reservar_o_posto_de_primario(P1)
    backend._primary_key = P2
    backend._recompute_primary()

    caduca = _backend({P2: _HandleFalso()}, primario=P2)
    caduca._reservar_o_posto_de_primario(P1)
    caduca._relogio.agora += PRIMARIO_RESERVA_SEC + 1.0
    caduca._posto_reservado_de_volta()

    dos_tres = [
        evento
        for evento in _eventos(journal)
        if str(evento.get("event")).startswith("primario_")
    ]
    assert len(dos_tres) == 4  # duas reservas + a retomada + a caducidade
    sem_chave = [e["event"] for e in dos_tres if e.get("key") != P1]
    assert not sem_chave, (
        f"{sem_chave} não trouxe `key={P1}` — sem a chave de correlação as "
        "linhas não se casam no journal"
    )
