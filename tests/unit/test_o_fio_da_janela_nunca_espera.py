"""O FIO DA JANELA NUNCA ESPERA — O-FIO-DA-JANELA-NUNCA-ESPERA-01.

O fio da janela é o do GTK. Medido no lar de mentira em 21/10/2026, antes da cura, ele
fazia em três minutos 6.103 aberturas no `/sys`, 178 no `/proc`, 187 varreduras do
`/sys/bus/usb/devices`, cinco subprocessos e uma conexão ao serviço; depois dela, nenhuma.
A régua de tempo roda o piloto oculto de verdade por três minutos, no relógio do
produto (a regressão de 29/08 só aparecia aos 181 s), e reprova o tique acima do teto e
a espera proibida no fio da janela. As outras são as de cada cura, sem a janela.
"""
from __future__ import annotations

import ast
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.unit.janela_aberta_comum import _args, _Estado, _gtk, _PonteDeMentira
from tests.unit.test_o_app_responde_na_hora import casa  # noqa: F401

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src/hefesto_dualsense4unix/interface"


def _as_abas() -> tuple[str, ...]:
    if str(INTERFACE) not in sys.path:
        sys.path.insert(0, str(INTERFACE))
    import monta

    return tuple(monta.as_abas_do_produto())


ABAS = _as_abas()

SEGUNDOS_POR_ABA = 20.0

TETO_DO_TIQUE_MS = 400.0

TIQUES_MINIMOS_POR_ABA = 90

ESPERAM = ("subprocess.Popen", "os.system", "os.posix_spawn", "os.exec", "socket.connect",
           "time.sleep")

LEEM = ("open", "os.listdir", "os.scandir", "glob.glob")

PROC_DO_PROPRIO_PROCESSO = "/proc/self/"

FIOS_FORA_DO_DONO = {"mesa_viva.py", "pacotes/a05_vibracao.py", "pacotes/fios.py"}


_VIGIA = SimpleNamespace(ligado=False, principal=threading.main_thread().ident, achados=[])


def _sitio() -> str:
    """De onde, no pacote, o evento saiu (as três chamadas mais próximas)."""
    f: Any = sys._getframe(2)
    cadeia: list[str] = []
    while f is not None and len(cadeia) < 3:
        nome = f.f_code.co_filename
        if "hefesto_dualsense4unix/" in nome:
            cadeia.append(f"{nome.split('hefesto_dualsense4unix/', 1)[1]}:{f.f_lineno}")
        f = f.f_back
    return " <- ".join(cadeia) or "(fora do pacote)"


def _proibido(evento: str, args: tuple[Any, ...]) -> str:
    """O alvo do evento, se ele espera no fio da janela; `""` se pode."""
    if evento.startswith(ESPERAM):
        return str(args[1] if evento == "socket.connect" else args[:1])[:80]
    if evento in LEEM and args:
        alvo = str(args[0])
        if alvo.startswith(("/sys/", "/proc/")) and not alvo.startswith(
                PROC_DO_PROPRIO_PROCESSO):
            return alvo[:80]
    return ""


def _gancho(evento: str, args: tuple[Any, ...]) -> None:
    if not _VIGIA.ligado or threading.get_ident() != _VIGIA.principal:
        return
    alvo = _proibido(evento, args)
    if alvo:
        _VIGIA.ligado = False
        try:
            _VIGIA.achados.append(f"{evento} {alvo} · {_sitio()}")
        finally:
            _VIGIA.ligado = True


sys.addaudithook(_gancho)


@contextmanager
def _vigiando() -> Iterator[list[str]]:
    """Liga o gancho no fio da janela e devolve o que ele achou."""
    _VIGIA.achados = []
    _VIGIA.ligado = True
    try:
        yield _VIGIA.achados
    finally:
        _VIGIA.ligado = False


def _tres_minutos(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """O piloto oculto passa pelas abas no relógio dele, com o gancho no fio da janela."""
    gtk = _gtk()
    from gi.repository import GLib

    from hefesto_dualsense4unix.app import audio_saida
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone as el
    from hefesto_dualsense4unix.integrations import ondas_de_som
    from hefesto_dualsense4unix.interface import hefesto_vivo as hv
    from hefesto_dualsense4unix.interface import mesa_viva

    monkeypatch.setattr(mesa_viva, "estado_do_daemon", _Estado(4))
    monkeypatch.setattr(hv, "ponte", _PonteDeMentira())
    monkeypatch.setattr(audio_saida, "rodar_leitura", lambda _argv: "")
    monkeypatch.setattr(el, "_rodar", lambda _argv: (1, ""))
    monkeypatch.setattr(ondas_de_som, "_LIGADO", [False])
    fora = SimpleNamespace(tiques={aba: [] for aba in ABAS}, achados=[], i=-1, acabou=False,
                           prazo=time.monotonic() + SEGUNDOS_POR_ABA * len(ABAS) + 60)
    with hv._o_processo_da_janela():
        piloto = hv.Piloto(_args(sem_ondas=True))
        tique_original = piloto._tique

        def tique() -> bool:
            if fora.acabou:
                return False
            t0 = time.perf_counter()
            volta = bool(tique_original())
            custo = (time.perf_counter() - t0) * 1000
            if 0 <= fora.i < len(ABAS) and piloto.pagina == ABAS[fora.i]:
                fora.tiques[ABAS[fora.i]].append(custo)
            if custo > TETO_DO_TIQUE_MS or time.monotonic() > fora.prazo:
                gtk.main_quit()
            return volta

        monkeypatch.setattr(piloto, "_tique", tique)

        def proxima() -> bool:
            fora.i += 1
            if fora.i >= len(ABAS):
                gtk.main_quit()
                return False
            piloto._ir(ABAS[fora.i])
            GLib.timeout_add(int(SEGUNDOS_POR_ABA * 1000), proxima)
            return False

        guarda = GLib.timeout_add(int((SEGUNDOS_POR_ABA * len(ABAS) + 60) * 1000),
                                  gtk.main_quit)
        GLib.idle_add(proxima)
        try:
            with _vigiando() as achados:
                gtk.main()
            fora.achados = list(achados)
        finally:
            fora.acabou = True
            piloto.pronto = False
            GLib.source_remove(guarda)
            piloto._estado_vivo.parar()
            piloto.tela.janela.destroy()
            ondas_de_som.o_de_sempre().seguir({})
    return fora


@pytest.mark.no_cover
def test_tres_minutos_sem_o_fio_da_janela_esperar(
    casa: SimpleNamespace, monkeypatch: pytest.MonkeyPatch  # noqa: F811
) -> None:
    """Nove abas, três minutos: nenhum tique acima do teto e nenhuma espera no fio da janela.

    Prova da D-2210-O-FIO-DA-JANELA-NUNCA-ESPERA.
    """
    assert sys.gettrace() is None, "a cobertura está ligada durante a medida"
    fora = _tres_minutos(monkeypatch)
    assert not fora.achados, (
        "o fio da janela esperou por fora do processo (subprocesso, IPC, `/sys`, `/proc`):\n  "
        + "\n  ".join(sorted(set(fora.achados))[:20]))
    acima = {aba: f"{max(t):.0f} ms" for aba, t in fora.tiques.items()
             if t and max(t) > TETO_DO_TIQUE_MS}
    assert not acima, f"tique acima do teto de {TETO_DO_TIQUE_MS:.0f} ms: {acima}"
    famintas = {aba: len(t) for aba, t in fora.tiques.items() if len(t) < TIQUES_MINIMOS_POR_ABA}
    assert not famintas, (
        f"abas com menos de {TIQUES_MINIMOS_POR_ABA} tiques em {SEGUNDOS_POR_ABA:.0f} s: "
        f"{famintas} (o tique parou, ou o laço andou devagar)")


def test_os_fios_da_interface_nascem_por_um_dono_so() -> None:
    """Fio novo da interface nasce por `fios.soltar`, com nome; `threading.Thread` direto, não."""
    soltos = []
    for caminho in sorted(INTERFACE.rglob("*.py")):
        rel = caminho.relative_to(INTERFACE).as_posix()
        if rel in FIOS_FORA_DO_DONO:
            continue
        for no in ast.walk(ast.parse(caminho.read_text(encoding="utf-8"))):
            if not isinstance(no, ast.Call):
                continue
            if (getattr(no.func, "attr", None) or getattr(no.func, "id", None)) == "Thread":
                soltos.append(f"{rel}:{no.lineno}")
    assert not soltos, (
        "fio da interface nascendo fora do dono (`pacotes.fios.soltar`): " + ", ".join(soltos))


def test_o_fio_sem_nome_e_recusado_e_o_com_nome_sai_com_ele() -> None:
    """Sem nome não sobe; com nome, o fio leva o nome e é `daemon`."""
    from hefesto_dualsense4unix.interface.pacotes import fios

    with pytest.raises(ValueError):
        fios.soltar("", lambda: None)
    visto: list[str] = []
    fio = fios.soltar("hefesto-da-regua", lambda: visto.append(threading.current_thread().name))
    fio.join(5)
    assert visto == ["hefesto-da-regua"] and fio.daemon


@pytest.fixture
def na_janela() -> Iterator[Any]:
    """A chave que o processo da janela liga, ligada só durante o teste."""
    from hefesto_dualsense4unix.interface.pacotes import fios

    fios.ligar_a_janela()
    try:
        yield fios
    finally:
        fios.ligar_a_janela(False)


def _leitura_presa(valor: Any) -> tuple[Any, threading.Event, list[str]]:
    """Uma leitura que só volta quando a régua solta, e anota em que fio rodou."""
    solta = threading.Event()
    fios_que_leram: list[str] = []

    def ler(*_a: Any, **_k: Any) -> Any:
        fios_que_leram.append(threading.current_thread().name)
        solta.wait(10)
        return valor

    return ler, solta, fios_que_leram


def _esperar(condicao: Any, prazo_s: float = 5.0) -> bool:
    fim = time.monotonic() + prazo_s
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return False


def test_a_primeira_faixa_lenta_da_09_nao_se_le_no_fio_da_janela(
        na_janela: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """No fio da janela, a primeira faixa lenta vai a um fio e o tique recebe o sinal."""
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    valor: tuple[Any, ...] = ("auto", [], "bateria", "online_systemd", None)
    ler, solta, quem = _leitura_presa(valor)
    monkeypatch.setattr(a09, "_ler_a_faixa_lenta", ler)
    monkeypatch.setattr(a09, "_LENTO", {})
    monkeypatch.setattr(a09, "_LENTO_EM_VOO", [False])
    t0 = time.perf_counter()
    with pytest.raises(na_janela.AindaNaoChegou):
        a09._faixa_lenta({}, [])
    assert (time.perf_counter() - t0) < 0.5, "a primeira faixa lenta esperou no fio da janela"
    assert _esperar(lambda: quem), "a leitura não saiu"
    assert threading.main_thread().name not in quem, quem
    solta.set()
    assert _esperar(lambda: "valor" in a09._LENTO), "a leitura não voltou ao escaninho"
    assert a09._faixa_lenta({}, []) == valor


def test_as_leituras_baratas_da_09_nao_se_leem_no_fio_da_janela(
        na_janela: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `/sys/class/bluetooth` e o arquivo do `HOME` da 09 também vão ao fundo."""
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09
    from hefesto_dualsense4unix.interface.pacotes import em_fundo

    ler, solta, quem = _leitura_presa(2)
    monkeypatch.setattr(a09, "_adaptadores", ler)
    monkeypatch.setattr(a09, "_sessao", lambda: "Wayland")
    monkeypatch.setattr(a09, "proton_fixado", lambda: False)
    monkeypatch.setattr(a09, "_BARATO", {})
    monkeypatch.setattr(em_fundo, "_FUNDO", {})
    monkeypatch.setattr(em_fundo, "_FUNDO_EM_VOO", set())
    monkeypatch.setattr(em_fundo, "LER_NA_HORA", False)
    with pytest.raises(na_janela.AindaNaoChegou):
        a09._leituras_baratas()
    assert _esperar(lambda: quem) and threading.main_thread().name not in quem, quem
    solta.set()
    assert _esperar(lambda: em_fundo.lido("baratas-da-09") is not None)
    assert a09._leituras_baratas()[0] == 2


def test_fora_da_janela_a_09_continua_lendo_na_hora(monkeypatch: pytest.MonkeyPatch) -> None:
    """O contrato das réguas fica: sem a janela, `_LENTO` vazio lê na hora, no fio de quem chama."""
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    quem: list[str] = []
    valor: tuple[Any, ...] = ("auto", [], "bateria", "offline", None)

    def ler(*_a: Any, **_k: Any) -> tuple[Any, ...]:
        quem.append(threading.current_thread().name)
        return valor

    monkeypatch.setattr(a09, "_ler_a_faixa_lenta", ler)
    monkeypatch.setattr(a09, "_LENTO", {})
    assert a09._faixa_lenta({}, []) == valor
    assert quem == [threading.current_thread().name]


def test_o_sinal_atravessa_o_pacote_da_09_sem_virar_nao_deu(
        na_janela: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `except Exception` do pacote pinta «não deu»; a leitura no ar não é falha e passa."""
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    ler, solta, _quem = _leitura_presa(("auto", [], "bateria", "offline", None))
    monkeypatch.setattr(a09, "_ler_a_faixa_lenta", ler)
    monkeypatch.setattr(a09, "_LENTO", {})
    monkeypatch.setattr(a09, "_LENTO_EM_VOO", [False])
    try:
        with pytest.raises(na_janela.AindaNaoChegou):
            pacotes.pacote_da_pagina("09-sistema.html", pacotes.Contexto(state={}))
    finally:
        solta.set()


def test_as_conferencias_da_08_nao_se_leem_no_fio_de_quem_pinta(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """As três conferências do `/sys` e do `/proc` voltam pela última leitura, lida num fio."""
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
    from hefesto_dualsense4unix.interface.pacotes import em_fundo

    ler, solta, quem = _leitura_presa(["conferida"])
    monkeypatch.setattr(a08, "_ler_as_conferencias", ler)
    monkeypatch.setattr(em_fundo, "_FUNDO", {})
    monkeypatch.setattr(em_fundo, "_FUNDO_EM_VOO", set())
    monkeypatch.setattr(em_fundo, "LER_NA_HORA", False)
    t0 = time.perf_counter()
    assert a08._conferencias() == []
    assert (time.perf_counter() - t0) < 0.5, "o tique esperou as conferências"
    assert _esperar(lambda: quem) and threading.main_thread().name not in quem, quem
    solta.set()
    assert _esperar(lambda: em_fundo.lido("conferencias") is not None)
    assert a08._conferencias() == ["conferida"]


def test_a_primeira_mesa_do_radio_da_08_nao_se_le_no_fio_de_quem_pinta(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A varredura do `/sys` dos adaptadores sai do tique; o botão continua relendo na hora."""
    from hefesto_dualsense4unix.integrations import mesa_de_radio
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
    from hefesto_dualsense4unix.interface.pacotes import em_fundo

    ler, solta, quem = _leitura_presa("mesa")
    monkeypatch.setattr(mesa_de_radio, "ler_a_mesa", ler)
    monkeypatch.setattr(a08, "_MESA_DO_RADIO", None)
    monkeypatch.setattr(em_fundo, "_FUNDO", {})
    monkeypatch.setattr(em_fundo, "_FUNDO_EM_VOO", set())
    monkeypatch.setattr(em_fundo, "LER_NA_HORA", False)
    assert a08._mesa_do_radio() is None
    assert _esperar(lambda: quem) and threading.main_thread().name not in quem, quem
    solta.set()
    assert _esperar(lambda: a08._MESA_DO_RADIO == "mesa")
    assert a08._mesa_do_radio() == "mesa"


def test_a_largada_da_troca_de_pagina_sai_do_fio_da_janela_e_fica_na_fila(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Com a mesa, a largada roda num fio, e o gesto seguinte do controle entra atrás dela."""
    from hefesto_dualsense4unix.interface import pacotes

    ordem: list[str] = []
    solta = threading.Event()

    def larga(_p: Any) -> None:
        ordem.append(f"largou em {threading.current_thread().name}")
        solta.wait(10)

    monkeypatch.setattr(pacotes, "LARGADAS", [larga])
    uniq = "aa:bb:cc:00:00:01"
    fio = pacotes.largar_o_que_as_abas_seguram(object(), mesa=[{"uniq": uniq}])
    assert fio is not None, "a troca de página largou no fio da janela"
    gesto = pacotes.na_fila([pacotes.fila_do_controle(uniq)], lambda: ordem.append("gesto"),
                            nome="gesto-da-regua")
    assert _esperar(lambda: ordem), "a largada não saiu"
    assert ordem == ["largou em largada"], ordem
    solta.set()
    gesto.join(5)
    assert ordem == ["largou em largada", "gesto"], ordem


def test_a_largada_da_saida_continua_no_fio_de_quem_fecha(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem `mesa` e sem fila no ar (o fim da janela), a largada continua na hora."""
    from hefesto_dualsense4unix.interface import pacotes

    quem: list[str] = []
    monkeypatch.setattr(pacotes, "LARGADAS",
                        [lambda _p: quem.append(threading.current_thread().name)])
    assert pacotes.largar_o_que_as_abas_seguram(object()) is None
    assert quem == [threading.current_thread().name]
