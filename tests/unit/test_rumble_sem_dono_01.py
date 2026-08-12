"""RUMBLE-SEM-DONO-01 — o keepalive que apagava o motor de outro dono.

O QUE ESTE ARQUIVO GUARDA
=========================
Duas faces do mesmo defeito, medido em 11/08/2026 com quatro DualSense na mesa
dela (dois no cabo, dois no rádio) e o olho dela como aceite.

**Face 1 — os BYTES.** A cura anterior (`keepalive neutro`, GUERRA-01 item 2)
apostava que DESLIGAR os bits de autorização de vibração bastava para o firmware
conservar o motor que outro dono deixou girando. A aposta caiu: com o daemon
parado, o EV_FF ligou o motor ESQUERDO, e UM único report com os bits de
vibração DESLIGADOS pedindo `common[2]=200` e `common[3]=0` fez o tremor **trocar
de lado na mão dela** (ensaio `keepalive-premissa-troca-de-lado`). O firmware
obedece aos BYTES. E os bytes de motor saem em TODO report, porque o report é
atômico — logo o keepalive, que reescrevia o mesmo report a cada 0,5 s, era um
apagador de vibração alheia rodando duas vezes por segundo. A dose-resposta
fechou a conta: com `OUT_REPORT_KEEPALIVE_SEC` em 8,0 s a vibração de terceiros
passou a durar oito segundos exatos nos dois transportes (`keepalive-dose-cabo`,
`keepalive-dose-radio`).

O par de testes de `test_paridade_transporte_rumble_em_par.py` morde os BITS.
Aqui se morde o que faltava: **os bytes que vão ao fio**, e quantas vezes.

**Face 2 — o quadrante silencioso.** Sem gamepad virtual E sem Modo Nativo ao
mesmo tempo, ninguém protege: o multiplicador de intensidade da GUI não age (ele
mora no `rumble_sink` do vpad) e o output do daemon não é mutado (só o Modo
Nativo o muta). O journal dela mostrava exatamente isso —
`launch_env_materializado ... backends=[] emulacao=False ... native=False` — e o
produto não contava a ninguém.

A MORDIDA DE CADA UM está no docstring do teste: qual linha arrancar para vê-lo
reprovar. Foram arrancadas de verdade antes desta leva.

O QUE ESTE ARQUIVO NÃO PROVA, DE PROPÓSITO
==========================================
Que a vibração do jogo sobrevive na mão dela. Isso é medição de bancada, e está
em `docs/data/ensaios.csv`. Aqui se prova o que o produto FAZ: para de mandar
bytes de motor quando não é dono da vibração, e diz em voz alta quando cai no
quadrante em que ninguém é dono.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydualsense.enums import ConnectionType
from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

from hefesto_dualsense4unix.core import backend_pydualsense as bp

# ---------------------------------------------------------------------------
# FACE 1 — os BYTES de motor que o keepalive punha no fio
# ---------------------------------------------------------------------------

#: Onde `common[2]` (motor direito) e `common[3]` (esquerdo) caem em cada
#: envelope: USB é `[0x02] + common`; BT é `[0x31, seq, 0x10] + common`.
_DESLOCAMENTO = {"cabo": 1, "radio": 3}
_MOTOR_DIREITO, _MOTOR_ESQUERDO = 2, 3

#: Passo do relógio falso: um tiquinho acima do keepalive, para que CADA ciclo
#: seja um candidato a reescrita. Assim o que limita o número de writes é a
#: cura, e nunca o relógio.
_PASSO_SEG = bp.OUT_REPORT_KEEPALIVE_SEC + 0.01

#: Ciclos por ensaio: 12 * 0,51 s = 6,1 s de relógio, o triplo da janela de
#: confirmação — sobra para ver o keepalive emudecer.
_CICLOS = 12


class _DispositivoFalso:
    """hidraw dublado: entrega leitura vazia e guarda tudo que foi escrito."""

    def __init__(self) -> None:
        self.escritos: list[bytes] = []

    def read(self, tamanho: int) -> bytes:
        return bytes(tamanho)

    def write(self, dados: bytes) -> int:
        self.escritos.append(bytes(dados))
        return len(dados)


def _handle(*, transporte: str, dono: bool = False) -> Any:
    """Um handle sem `init()` — nenhum hidraw de verdade, nenhum aparelho.

    O report é função pura do estado desejado, então é esse estado que se monta
    aqui. Os campos são os mesmos que o `__init__` real cria.
    """
    inst = bp._PinnedPyDualSense.__new__(bp._PinnedPyDualSense)
    inst.input_report_length = 64
    inst.connected = True
    inst.ds_thread = True
    inst.leftMotor = 200 if dono else 0
    inst.rightMotor = 0
    inst.light = DSLight()
    inst.audio = DSAudio()
    inst.triggerL = DSTrigger()
    inst.triggerR = DSTrigger()
    inst.conType = ConnectionType.BT if transporte == "radio" else ConnectionType.USB
    inst._suppress_leds = False
    inst._bt_seq = 0
    inst._throttle_sec = bp.REPORT_THREAD_THROTTLE_SEC
    inst._last_out_report = None
    inst._last_write_at = 0.0
    inst._last_change_at = float("-inf")
    inst._output_muted = False
    inst._rumble_active = dono
    inst._rumble_stop_pending = False
    inst.device = _DispositivoFalso()
    return inst


def _rodar(inst: Any, monkeypatch: pytest.MonkeyPatch, ciclos: int = _CICLOS) -> None:
    """Gira o `sendReport` por N ciclos com relógio e sono falsos."""
    monkeypatch.setattr(inst, "readInput", lambda _r: None)
    monkeypatch.setattr(inst, "_captura_status_audio", lambda: None)

    agora = {"t": 1000.0}
    voltas = {"n": 0}
    monkeypatch.setattr(bp.time, "monotonic", lambda: agora["t"])

    def _dormir(_segundos: float) -> None:
        voltas["n"] += 1
        agora["t"] += _PASSO_SEG
        if voltas["n"] >= ciclos:
            inst.ds_thread = False

    monkeypatch.setattr(bp.time, "sleep", _dormir)
    inst.sendReport()
    assert voltas["n"] == ciclos, "o laço encerrou cedo — o ensaio não vale"


@pytest.mark.parametrize("transporte", ["cabo", "radio"])
def test_sem_dono_o_keepalive_para_de_mandar_bytes_de_motor(
    transporte: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A MORDIDA: em `sendReport`, troque a condição de escrita de volta para
    `if mudou or vencido:` (o keepalive perpétuo). Este teste passa a contar 12
    writes em vez de 4 — doze reports carregando `common[2]=0`/`common[3]=0`
    por cima de quem estivesse vibrando.

    O que se afirma aqui, e é a face dos BYTES: o report que o keepalive
    repetiria carrega ZERO nos dois bytes de motor. Não existe valor neutro para
    esses bytes — não há report de entrada nem feature que devolva o que o outro
    dono pediu —, então o único write que não apaga vibração alheia é o write
    que não acontece. Passada a janela de confirmação, ele não acontece.
    """
    inst = _handle(transporte=transporte)
    _rodar(inst, monkeypatch)

    escritos = inst.device.escritos
    esperado = 1 + int(bp.OUT_REPORT_KEEPALIVE_CONFIRMACAO_SEC // _PASSO_SEG)
    assert len(escritos) == esperado, (
        f"em {transporte} saíram {len(escritos)} reports para um estado que "
        f"nunca mudou (esperados {esperado}: a mudança + as reconfirmações da "
        "janela). Cada report a mais é um apagador de vibração de terceiros — "
        "medido em 11/08/2026, ensaio keepalive-dose-cabo/radio"
    )

    deslocamento = _DESLOCAMENTO[transporte]
    for quadro in escritos:
        assert quadro[deslocamento + _MOTOR_DIREITO] == 0
        assert quadro[deslocamento + _MOTOR_ESQUERDO] == 0


@pytest.mark.parametrize("transporte", ["cabo", "radio"])
def test_com_rumble_nosso_o_keepalive_continua_para_sempre(
    transporte: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O outro lado da cura, e a restrição dura desta leva.

    Quando o rumble É nosso, o keepalive é o que faz a vibração dela persistir —
    e ele não pode ser tocado. Sem este par, alguém "curaria" o teste de cima
    calando o keepalive para sempre, e a vibração do produto morreria em 0,5 s
    sem nenhum teste reclamar.
    """
    inst = _handle(transporte=transporte, dono=True)
    _rodar(inst, monkeypatch)

    escritos = inst.device.escritos
    assert len(escritos) == _CICLOS, (
        "o keepalive emudeceu com rumble NOSSO ativo: a vibração dela para de "
        "persistir"
    )
    deslocamento = _DESLOCAMENTO[transporte]
    for quadro in escritos:
        assert quadro[deslocamento + _MOTOR_ESQUERDO] == 200


def test_a_janela_de_confirmacao_reescreve_a_mudanca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A MORDIDA: zere `OUT_REPORT_KEEPALIVE_CONFIRMACAO_SEC` (ou tire o
    `confirmando` da condição) e este teste reprova com um único write.

    É o que o keepalive JÁ curava, e a regra da casa manda explicar o que já
    funcionava: PERF-MULTI-CONTROLLER-01 o escreveu para *"cobrir perda de
    report e glitch de link"*. Um report que se perde no rádio some para sempre,
    porque o dedup já anotou que ele foi enviado. Reconfirmar a MUDANÇA algumas
    vezes cobre isso inteiro; reconfirmar para sempre não cobre nada a mais e
    apaga motor alheio.
    """
    inst = _handle(transporte="radio")
    _rodar(inst, monkeypatch)

    escritos = inst.device.escritos
    assert len(escritos) >= 2, (
        "a mudança foi ao fio uma única vez: um report perdido no rádio não "
        "tem mais como ser recuperado"
    )
    # Todos reconfirmam o MESMO estado. A comparação é do bloco `common`, e não
    # do quadro inteiro: por BT o `writeReport` carimba o contador de sequência
    # e recalcula o CRC a cada write, então dois quadros idênticos em conteúdo
    # nascem diferentes em bytes.
    from hefesto_dualsense4unix.core import ds_output_report as rep

    inicio = _DESLOCAMENTO["radio"]
    corpos = {bytes(q[inicio : inicio + rep.COMMON_LEN]) for q in escritos}
    assert len(corpos) == 1, "a janela reconfirmou estados diferentes"


# ---------------------------------------------------------------------------
# FACE 2 — o quadrante em que ninguém é dono da vibração
# ---------------------------------------------------------------------------


def test_o_quadrante_mortal_e_so_um_dos_quatro() -> None:
    """A tabela-verdade inteira, que é o motivo de o defeito parecer
    intermitente: nos outros três quadrantes uma das duas coisas protege."""
    from hefesto_dualsense4unix.daemon.subsystems.rumble import sem_dono_do_rumble

    assert sem_dono_do_rumble(native=False, backends=[]) is True
    assert sem_dono_do_rumble(native=True, backends=[]) is False
    assert sem_dono_do_rumble(native=False, backends=["uhid"]) is False
    assert sem_dono_do_rumble(native=True, backends=["uhid"]) is False


class _RegistroDeLog:
    """Coletor de eventos structlog — guarda (nível, evento)."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, str]] = []

    def _anota(self, nivel: str) -> Any:
        def _log(evento: str, **_kw: Any) -> None:
            self.eventos.append((nivel, evento))

        return _log

    def __getattr__(self, nome: str) -> Any:
        return self._anota(nome)


class _DaemonFalso:
    """O mínimo que `_snapshot` toca: modo nativo, emulação e vpads."""

    def __init__(self, *, nativo: bool, vpad: bool) -> None:
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=vpad,
            gamepad_flavor="dualsense",
            rumble_active=None,
        )
        self._gamepad_device: Any = (
            SimpleNamespace(backend="uhid", flavor="dualsense") if vpad else None
        )
        self._coop_manager = None
        self.controller = SimpleNamespace(set_rumble=lambda **_k: None)
        self._nativo = nativo

    def is_native_mode(self) -> bool:
        return self._nativo


@pytest.fixture()
def _borda_de_materializacao(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> _RegistroDeLog:
    """A borda isolada: nada de disco do usuário, nada de perfis reais."""
    from hefesto_dualsense4unix.daemon import launch_env as le

    registro = _RegistroDeLog()
    monkeypatch.setattr(le, "logger", registro)
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
    monkeypatch.setattr(le, "_load_profiles", lambda daemon: [])
    monkeypatch.setattr(le, "_fisicos_na_mesa", lambda daemon: 1)
    return registro


@pytest.mark.parametrize(
    ("nativo", "vpad", "avisa"),
    [
        (False, False, True),  # o quadrante mortal — o journal dela, 11/08
        (True, False, False),  # Modo Nativo muta o nosso output
        (False, True, False),  # o vpad põe o multiplicador dela no caminho
        (True, True, False),
    ],
)
def test_a_borda_grita_no_quadrante_sem_dono(
    nativo: bool,
    vpad: bool,
    avisa: bool,
    _borda_de_materializacao: _RegistroDeLog,
) -> None:
    """A MORDIDA: apague o `if sem_dono_do_rumble(...)` de
    `materialize_launch_env` e o primeiro caso reprova — que é o estado de hoje,
    em que o produto cai neste quadrante em silêncio.

    O aviso mora na borda de materialização de propósito: é a única chamada com
    o estado REAL da mesa, e é onde o `dedup_broken` já mora pelo mesmo motivo.
    """
    from hefesto_dualsense4unix.daemon.launch_env import materialize_launch_env

    materialize_launch_env(_DaemonFalso(nativo=nativo, vpad=vpad))  # type: ignore[arg-type]

    avisos = [e for n, e in _borda_de_materializacao.eventos if n == "warning"]
    if avisa:
        assert "rumble_sem_dono" in avisos, (
            "sem vpad e sem Modo Nativo, o multiplicador da GUI não age e o "
            "nosso output continua escrevendo — e o produto não avisa"
        )
    else:
        assert "rumble_sem_dono" not in avisos, (
            "aviso num quadrante protegido: alarme que sempre toca é alarme "
            "que ninguém escuta"
        )


def test_a_materializacao_nao_morre_por_causa_do_aviso(
    _borda_de_materializacao: _RegistroDeLog, tmp_path: Any
) -> None:
    """O aviso é telemetria, não portão: o `default.env` continua saindo.

    `materialize_launch_env` é best-effort por contrato (engole exceção) — um
    aviso que derrubasse a materialização deixaria o wrapper sem env nenhuma e
    trocaria um defeito silencioso por um barulhento.
    """
    from hefesto_dualsense4unix.daemon.launch_env import materialize_launch_env

    materialize_launch_env(_DaemonFalso(nativo=False, vpad=False))  # type: ignore[arg-type]

    assert (tmp_path / "default.env").exists()
