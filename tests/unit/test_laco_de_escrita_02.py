"""LACO-DE-ESCRITA-02 — os dois defeitos do laço de saída, achados por leitura
de código em 15/08/2026 e descritos em
`docs/process/sprints/2026-08-15-O-LACO-DE-ESCRITA-01-o-suspeito-que-sobrou.md`.

**Defeito A — o contador de sequência do rádio sem lock.** `writeReport` fazia um
*read-modify-write* de `_bt_seq` sem exclusão mútua, e há mais de uma thread
escrevendo no mesmo handle (a `report_thread` em regime, e as escritas avulsas de
lightbar vindas do IPC e do poll loop). Duas threads podiam carimbar o MESMO
`seq`: o firmware descarta o quadro fora de sequência e o nosso log diz
"escrito". É defeito só do rádio — o `0x02` do cabo não tem `seq` nem CRC.

**Defeito B — a leitura vazia matando a thread de saída.** O handle é
não-bloqueante, então `hidapi.Device.read` devolve `None` quando não há dado; o
`readInput` do upstream começa com `list(inReport)` e levanta `TypeError`, que o
laço não capturava. A thread morria e o controle ficava SEM SAÍDA — sem rumble,
sem lightbar, sem gatilho — sem uma linha estruturada no journal e sem
`connected = False`.
"""
from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core import ds_output_report as rep


class _LoggerDeMentira:
    """Registra as linhas do `logger` do backend, com nível e campos."""

    def __init__(self) -> None:
        self.linhas: list[tuple[str, str, dict[str, Any]]] = []

    def _guardar(self, nivel: str, evento: str, **campos: Any) -> None:
        self.linhas.append((nivel, evento, campos))

    def debug(self, evento: str, **campos: Any) -> None:
        self._guardar("debug", evento, **campos)

    def info(self, evento: str, **campos: Any) -> None:
        self._guardar("info", evento, **campos)

    def warning(self, evento: str, **campos: Any) -> None:
        self._guardar("warning", evento, **campos)

    def error(self, evento: str, **campos: Any) -> None:
        self._guardar("error", evento, **campos)

    def eventos(self, nome: str) -> list[dict[str, Any]]:
        return [campos for _n, evento, campos in self.linhas if evento == nome]


# --------------------------------------------------------------------------
# DEFEITO A — a corrida do `_bt_seq`
# --------------------------------------------------------------------------


def _handle_do_radio() -> bp._PinnedPyDualSense:
    """Um handle com só o que `writeReport` usa (o resto é dublê)."""
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst._bt_seq = 0
    # Espelha o que o `__init__` real dá a cada instância — sem isto o teste
    # passaria pelo default de CLASSE, que serializa por acidente e não pela
    # cura que se quer provar.
    inst._write_lock = threading.Lock()
    return inst


def test_escritores_concorrentes_no_radio_nunca_repetem_o_seq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quatro threads escrevendo no MESMO handle BT produzem quatro `seq`
    distintos, na ordem em que chegam ao fio.

    A janela da corrida é aberta de propósito: o `stamp_bt_seq` do teste dorme
    entre LER `_bt_seq` e INCREMENTÁ-LO, que é exatamente onde a segunda thread
    entrava. Sem o lock em `writeReport`, as quatro leem zero e carimbam zero —
    três dos quatro quadros são descartados pelo firmware e o log diz "escrito"
    nos quatro.

    A ordem de chegada ao fio também é asserida, porque `seq` distintos
    entregues fora de ordem seriam descartados pelo firmware do mesmo jeito.
    **Mas este teste não é a rede contra a cura pela metade** (lock só no
    contador, `write` fora): tentei, e ele PASSA nessa variante — a janela que
    ele abre está dentro da seção crítica dos dois desenhos. Quem morde essa
    variante é `test_o_write_acontece_com_o_lock_na_mao`, logo abaixo.
    """
    inst = _handle_do_radio()
    report = list(rep.build_bt_report(bytearray(rep.COMMON_LEN), seq=0))
    assert len(report) == 78 and report[0] == 0x31

    vistos: list[int] = []
    trava_do_registro = threading.Lock()

    class _DispositivoDeMentira:
        def write(self, dados: bytes) -> None:
            with trava_do_registro:
                vistos.append(dados[1] >> 4)  # o nibble ALTO de [1] é o seq

    inst.device = _DispositivoDeMentira()

    carimbo_real = rep.stamp_bt_seq

    def _carimbo_lento(buf: Any, seq: int) -> None:
        carimbo_real(buf, seq)
        time.sleep(0.02)

    monkeypatch.setattr(rep, "stamp_bt_seq", _carimbo_lento)

    largada = threading.Event()

    def _escritor() -> None:
        largada.wait(timeout=5)
        inst.writeReport(list(report))

    threads = [threading.Thread(target=_escritor) for _ in range(4)]
    for t in threads:
        t.start()
    largada.set()
    for t in threads:
        t.join(timeout=10)
        assert not t.is_alive()

    assert len(vistos) == 4
    assert len(set(vistos)) == 4, f"seq repetido entre escritores: {vistos}"
    assert vistos == [0, 1, 2, 3], f"quadros entregues fora de ordem: {vistos}"
    assert inst._bt_seq == 4


def test_o_write_acontece_com_o_lock_na_mao() -> None:
    """O `write` está DENTRO da seção crítica, não só o contador.

    Uma thread só, e a asserção é estrutural em vez de temporal: o dispositivo
    de mentira confere, de dentro do `write`, que o lock está tomado. É esta a
    rede contra a cura pela metade — serializar apenas o incremento produz
    `seq` distintos que podem chegar ao fio FORA DE ORDEM, e report fora de
    sequência é exatamente o que o firmware descarta. O que precisa ser atômico
    é o par carimbo+entrega.
    """
    inst = _handle_do_radio()
    visto = {"com_o_lock": None}

    class _DispositivoDeMentira:
        def write(self, _dados: bytes) -> None:
            visto["com_o_lock"] = inst._write_lock.locked()

    inst.device = _DispositivoDeMentira()
    inst.writeReport(list(rep.build_bt_report(bytearray(rep.COMMON_LEN), seq=0)))
    assert visto["com_o_lock"] is True, "o write do rádio saiu fora do lock"

    visto["com_o_lock"] = None
    inst.writeReport(list(rep.build_usb_report(bytearray(rep.COMMON_LEN))))
    assert visto["com_o_lock"] is True, "o write do cabo saiu fora do lock"


def test_cada_handle_tem_o_seu_proprio_lock() -> None:
    """O lock é POR HANDLE, e é isso que impede um `hid_write` pendurado num
    controle de calar os outros três da mesa.

    O default de CLASSE existe só para os dublês da suíte (construídos com
    `__new__`); handle de produção não pode cair nele.
    """
    a = bp._PinnedPyDualSense(b"/dev/hidraw-teste-a", is_edge=False)
    b = bp._PinnedPyDualSense(b"/dev/hidraw-teste-b", is_edge=False)

    assert a._write_lock is not b._write_lock
    assert a._write_lock is not bp._PinnedPyDualSense._write_lock
    assert b._write_lock is not bp._PinnedPyDualSense._write_lock


def test_o_cabo_tambem_passa_pelo_lock_e_sai_sem_carimbo() -> None:
    """O `0x02` não ganha `seq` (não tem campo para ele) mas continua saindo —
    a serialização não pode ter mudado o que vai ao fio pelo cabo.
    """
    inst = _handle_do_radio()
    enviados: list[bytes] = []

    class _DispositivoDeMentira:
        def write(self, dados: bytes) -> None:
            enviados.append(dados)

    inst.device = _DispositivoDeMentira()
    usb = list(rep.build_usb_report(bytearray(rep.COMMON_LEN)))
    inst.writeReport(usb)

    assert enviados == [bytes(usb)]
    assert inst._bt_seq == 0  # o contador é do rádio, e o cabo não o mexe


# --------------------------------------------------------------------------
# DEFEITO B — a leitura vazia
# --------------------------------------------------------------------------


def _handle_do_laco() -> bp._PinnedPyDualSense:
    """Um handle com o que o `sendReport` usa (mesmo molde do throttle)."""
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.input_report_length = 64
    inst.connected = True
    inst.ds_thread = True
    inst._throttle_sec = bp.REPORT_THREAD_THROTTLE_SEC
    inst._last_out_report = None
    inst._last_write_at = 0.0
    inst._last_change_at = float("-inf")
    inst._output_muted = False
    inst._rumble_active = False
    inst._rumble_stop_pending = False
    inst._write_lock = threading.Lock()
    return inst


def _read_input_do_upstream(in_report: Any) -> None:
    """A PRIMEIRA linha do `readInput` do upstream, e só ela.

    `list(inReport)` é onde o `None` da leitura não-bloqueante vira `TypeError`.
    O dublê a reproduz literalmente para que arrancar a cura reprove de verdade,
    e não por causa de um dublê complacente.
    """
    list(in_report)[1:]


def test_leitura_vazia_nao_mata_a_thread_e_a_saida_continua(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`read` devolvendo `None` é resposta legítima da leitura não-bloqueante:
    o ciclo pula a interpretação da ENTRADA e segue direto para a SAÍDA.

    A prova é dupla: a thread chega ao fim dos quatro ciclos (não morreu) e o
    write OUT aconteceu TAMBÉM nos ciclos mudos — que é o que significa "o
    controle continua tendo saída".
    """
    inst = _handle_do_laco()
    inst.conType = None

    contas = {"read": 0, "write": 0, "sleep": 0}
    # Ciclos 1 e 2 mudos; 3 e 4 com dado.
    respostas: list[bytes | None] = [None, None, bytes(64), bytes(64)]

    class _DispositivoDeMentira:
        def read(self, _n: int) -> bytes | None:
            resposta = respostas[min(contas["read"], len(respostas) - 1)]
            contas["read"] += 1
            return resposta

    inst.device = _DispositivoDeMentira()
    monkeypatch.setattr(inst, "readInput", _read_input_do_upstream)
    monkeypatch.setattr(inst, "_captura_status_audio", lambda: None)
    # Report SEMPRE diferente: cada ciclo é um write, então contar writes é
    # contar ciclos que chegaram à metade de saída.
    monkeypatch.setattr(
        inst, "prepareReport", lambda: [contas["sleep"] & 0xFF] + [0] * 63
    )

    def _conta_write(_r: object) -> None:
        contas["write"] += 1

    monkeypatch.setattr(inst, "writeReport", _conta_write)

    def _sono_de_mentira(_secs: float) -> None:
        contas["sleep"] += 1
        if contas["sleep"] >= 4:
            inst.ds_thread = False

    monkeypatch.setattr(bp.time, "sleep", _sono_de_mentira)

    inst.sendReport()

    assert contas["sleep"] == 4, "a thread não chegou ao fim dos ciclos"
    assert inst.connected is True, "leitura vazia não é desconexão"
    assert contas["write"] == 4, "os ciclos mudos ficaram sem SAÍDA"


def test_o_silencio_da_entrada_deixa_rastro_no_journal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """UMA linha de aviso por episódio de silêncio, e uma de volta quando a
    entrada fala de novo.

    Uma por episódio, não uma por ciclo: com a mesa cheia são ~31 ciclos por
    segundo, e um aviso por ciclo afogaria o journal justo quando ele mais
    precisa ser lido. E não pode ser NENHUMA: a memória desta casa já pagou
    caro por defeito cujo sintoma é a AUSÊNCIA de dado.
    """
    inst = _handle_do_laco()
    inst.conType = None
    inst._pinned_path = b"/dev/hidraw-teste"

    registro = _LoggerDeMentira()
    monkeypatch.setattr(bp, "logger", registro)

    relogio = {"t": 1000.0}
    contas = {"read": 0, "sleep": 0}
    # Seis ciclos mudos (3,0 s de silêncio no relógio de mentira) e o sétimo
    # com dado — a volta.
    mudos = 6

    class _DispositivoDeMentira:
        def read(self, _n: int) -> bytes | None:
            contas["read"] += 1
            return None if contas["read"] <= mudos else bytes(64)

    inst.device = _DispositivoDeMentira()
    monkeypatch.setattr(inst, "readInput", _read_input_do_upstream)
    monkeypatch.setattr(inst, "_captura_status_audio", lambda: None)
    monkeypatch.setattr(inst, "prepareReport", lambda: [0] * 64)
    monkeypatch.setattr(inst, "writeReport", lambda _r: None)
    monkeypatch.setattr(bp.time, "monotonic", lambda: relogio["t"])

    def _sono_de_mentira(_secs: float) -> None:
        contas["sleep"] += 1
        relogio["t"] += 0.5
        if contas["sleep"] >= mudos + 1:
            inst.ds_thread = False

    monkeypatch.setattr(bp.time, "sleep", _sono_de_mentira)

    inst.sendReport()

    avisos = registro.eventos("report_thread_entrada_muda")
    voltas = registro.eventos("report_thread_entrada_voltou")
    assert len(avisos) == 1, f"esperado UM aviso por episódio, veio {len(avisos)}"
    assert len(voltas) == 1, "a volta da entrada não foi registrada"
    assert avisos[0]["segundos"] >= bp.LEITURA_VAZIA_AVISO_SEC
    assert voltas[0]["segundos"] >= bp.LEITURA_VAZIA_AVISO_SEC
    assert inst.connected is True


def test_silencio_curto_nao_polui_o_journal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Um ciclo mudo isolado não é notícia — e não pode virar linha."""
    inst = _handle_do_laco()
    inst.conType = None

    registro = _LoggerDeMentira()
    monkeypatch.setattr(bp, "logger", registro)

    relogio = {"t": 500.0}
    contas = {"read": 0, "sleep": 0}

    class _DispositivoDeMentira:
        def read(self, _n: int) -> bytes | None:
            contas["read"] += 1
            return None if contas["read"] == 1 else bytes(64)

    inst.device = _DispositivoDeMentira()
    monkeypatch.setattr(inst, "readInput", _read_input_do_upstream)
    monkeypatch.setattr(inst, "_captura_status_audio", lambda: None)
    monkeypatch.setattr(inst, "prepareReport", lambda: [0] * 64)
    monkeypatch.setattr(inst, "writeReport", lambda _r: None)
    monkeypatch.setattr(bp.time, "monotonic", lambda: relogio["t"])

    def _sono_de_mentira(_secs: float) -> None:
        contas["sleep"] += 1
        relogio["t"] += 0.032
        if contas["sleep"] >= 3:
            inst.ds_thread = False

    monkeypatch.setattr(bp.time, "sleep", _sono_de_mentira)

    inst.sendReport()

    assert registro.eventos("report_thread_entrada_muda") == []
    assert registro.eventos("report_thread_entrada_voltou") == []


def test_excecao_inesperada_no_laco_deixa_linha_antes_de_morrer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rede: exceção que ninguém previu não pode matar a `report_thread` em
    silêncio.

    O desfecho é o mesmo do `OSError` (fim de vida do handle), de propósito —
    seguir o laço depois de uma exceção que não se sabe nomear é girar sem saber
    em quê, e este laço escreve no aparelho dela. O que muda é que agora fica
    escrito, e `connected` para de mentir.
    """
    inst = _handle_do_laco()
    registro = _LoggerDeMentira()
    monkeypatch.setattr(bp, "logger", registro)

    class _DispositivoDeMentira:
        def read(self, _n: int) -> bytes:
            raise ValueError("algo que ninguém previu")

    inst.device = _DispositivoDeMentira()

    inst.sendReport()

    assert inst.connected is False
    mortes = registro.eventos("report_thread_morreu_por_excecao")
    assert len(mortes) == 1
    assert mortes[0]["tipo"] == "ValueError"
