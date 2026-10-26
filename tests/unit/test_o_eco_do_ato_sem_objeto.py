"""O eco do ato sem objeto — O-ECO-DO-ATO-SEM-OBJETO-01.

O DEFEITO, medido nesta árvore com o handle de produção e o laço de produção
-------------------------------------------------------------------------
O 🎙 da tela cala o controle (o mudo vai ao firmware e demora a confirmar). O
dedo do usuário aperta o botão do plástico ANTES de o bit confirmar. O aperto sempre
pediu «o contrário do bit lido», e o bit lido ainda era o velho: pedia o MESMO
que o 🎙. Quem decidia o que o dedo pediu era um relógio — o `_ECO_DO_ATO`
(2 s), que engolia o aperto calado, com log só em debug, e que perdeu o objeto
quando o gesto virou o botão (nada que o Hefesto escreve aperta o botão).

A CURA, NA ORIGEM: o aperto se lê contra o que o firmware vai segurar (a
posse nossa, com a escrita viva), não contra o bit do report; e o aperto que
chega com a escrita em voo termina com o firmware no pedido, sem a
idempotência pular sobre o bit velho. Sai o eco inteiro: uma guarda de tempo
só (o sossego de 1,0 s).

As réguas valem nos dois transportes e para os quatro jogadores.
"""

from __future__ import annotations

import asyncio
import subprocess
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import backend_pydualsense as bp
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon import lifecycle
from hefesto_dualsense4unix.daemon.subsystems import (
    hotkey,
    mic_da_mesa,
    recado_do_microfone,
)
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import STATUS_MIC_MUDO
from tests.unit.test_o_botao_do_mic_so_obedece_a_mao import _backend, _Handle, _report
from tests.unit.test_os_quatro_microfones_ficam_no_ar import (
    MESA_DELA,
    P1,
    P2,
    P3,
    P4,
    _GerenciadorDeMentira,
    _n,
    _PipeWire,
)

MUDO = STATUS_MIC_MUDO
LIVRE = 0x00

_QUATRO = ("aabbcc000001", "aabbcc000002", "aabbcc000003", "aabbcc000004")
_TRANSPORTES = pytest.mark.parametrize("transporte", ["cabo", "radio"])


def _segurar(h: Any, transporte: str, *, status: int, botao: bool = False, n: int = 20) -> None:
    for _ in range(n):
        h._consumir_report(_report(transporte, status=status, botao=botao))


def _borda(backend: Any, uniq: str) -> tuple[int, bool, bool | None]:
    """`(seq, pedido, em_voo)` da borda; `em_voo` é `None` se a tupla não o traz."""
    cru = tuple(backend.bordas_do_mic()[uniq])
    return (cru[0], cru[1], cru[3] if len(cru) > 3 else None)


def _apertar(h: Any, transporte: str, *, bit: int) -> None:
    """O dedo desce e sobe com o bit do report em `bit` (o do instante do aperto)."""
    _segurar(h, transporte, status=bit, botao=True, n=5)
    _segurar(h, transporte, status=bit, botao=False, n=20)


@_TRANSPORTES
@pytest.mark.parametrize("jogador", range(4))
def test_o_pedido_do_aperto_e_o_contrario_da_posse_em_voo(transporte: str, jogador: int) -> None:
    """Posse `True` (o 🎙 calou), bit ainda livre: o aperto pede LIGAR."""
    uniq = _QUATRO[jogador]
    h = _Handle()
    backend = _backend({uniq: h})
    _segurar(h, transporte, status=LIVRE)
    backend.set_microphone_mute(True, uniq=uniq)

    _apertar(h, transporte, bit=LIVRE)

    seq, pedido, em_voo = _borda(backend, uniq)
    assert seq == 1
    assert pedido is False, (
        "o 🎙 calou, o bit ainda não confirmou, e o aperto pediu o contrário do "
        "bit velho — o MESMO que o 🎙: calar de novo"
    )
    assert em_voo is True, "a escrita estava em voo e o ato não ficou sabendo"


@_TRANSPORTES
@pytest.mark.parametrize("jogador", range(4))
def test_o_pedido_com_a_posse_ja_confirmada_e_o_de_sempre(transporte: str, jogador: int) -> None:
    """Posse e bit concordam: nada muda — o aperto pede o contrário dos dois."""
    uniq = _QUATRO[jogador]
    h = _Handle()
    backend = _backend({uniq: h})
    _segurar(h, transporte, status=MUDO)
    backend.set_microphone_mute(True, uniq=uniq)

    _apertar(h, transporte, bit=MUDO)

    _seq, pedido, em_voo = _borda(backend, uniq)
    assert pedido is False
    assert em_voo is False, "bit e posse concordam: não há escrita em voo"


@_TRANSPORTES
def test_com_a_posse_ao_contrario_do_bit_o_pedido_ainda_e_o_da_posse(transporte: str) -> None:
    """A posse `False` (o 🎙 ligou) com o bit ainda mudo: o aperto pede CALAR."""
    uniq = _QUATRO[0]
    h = _Handle()
    backend = _backend({uniq: h})
    _segurar(h, transporte, status=MUDO)
    backend.set_microphone_mute(False, uniq=uniq)

    _apertar(h, transporte, bit=MUDO)

    _seq, pedido, em_voo = _borda(backend, uniq)
    assert pedido is True
    assert em_voo is True


@_TRANSPORTES
def test_onde_o_jogo_e_dono_do_hidraw_a_referencia_e_o_bit(transporte: str) -> None:
    """Com `_output_muted` a posse não vai ao fio: o aperto pede o contrário do bit."""
    uniq = _QUATRO[1]
    h = _Handle()
    h._output_muted = True
    backend = _backend({uniq: h})
    _segurar(h, transporte, status=LIVRE)
    backend.set_microphone_mute(True, uniq=uniq)

    _apertar(h, transporte, bit=LIVRE)

    _seq, pedido, em_voo = _borda(backend, uniq)
    assert pedido is True, "a posse que não vai ao fio decidiu o que o dedo pediu"
    assert em_voo is False


@_TRANSPORTES
def test_sem_posse_o_pedido_e_o_contrario_do_bit(transporte: str) -> None:
    uniq = _QUATRO[2]
    h = _Handle()
    backend = _backend({uniq: h})
    _segurar(h, transporte, status=LIVRE)
    _apertar(h, transporte, bit=LIVRE)
    _seq, pedido, em_voo = _borda(backend, uniq)
    assert pedido is True
    assert em_voo is False


LATENCIA_S = 0.03


class _Aparelho:
    """O firmware e o kernel do P3, no tempo: o bit só confirma depois da latência."""

    def __init__(self, handle: Any) -> None:
        self.h = handle
        self.bit = False
        self.kernel = False
        self.botao = False
        self._posse_vista: bool | None = None
        self._desde = 0.0
        self._rodando = True

    async def correr(self) -> None:
        relogio = asyncio.get_running_loop().time
        while self._rodando:
            posse = getattr(self.h, "_mic_mute_desejado", None)
            if posse != self._posse_vista:
                self._posse_vista = posse
                self._desde = relogio()
            if posse is not None and relogio() - self._desde >= LATENCIA_S:
                self.bit = posse
            self.h._consumir_report(
                _report("cabo", status=MUDO if self.bit else LIVRE, botao=self.botao)
            )
            await asyncio.sleep(0.005)

    async def apertar(self) -> None:
        """O dedo: o kernel alterna o seu mudo e o escreve já."""
        self.botao = True
        await asyncio.sleep(0.02)
        self.kernel = not self.kernel
        self.bit = self.kernel
        await asyncio.sleep(0.03)
        self.botao = False

    def parar(self) -> None:
        self._rodando = False


class _Mesa(bp.PyDualSenseController):
    """O controlador de produção sobre handles de produção, sem aparelho."""

    def __new__(cls, *_a: Any) -> Any:
        return object.__new__(cls)

    def __init__(self, handles: dict[str, Any]) -> None:
        self._handles = handles
        self._io_lock = _Lock()
        self._mic_mute_by_uniq: dict[str, bool] = {}
        self.leds: dict[str, bool] = {}

    def describe_controllers(self) -> list[dict[str, Any]]:
        return [{"uniq": u, "connected": True, "transport": t} for u, t in MESA_DELA]

    def set_mic_led(self, aceso: Any, *, uniq: str | None = None) -> None:
        self.leds[_n(uniq or "")] = bool(aceso)


class _Lock:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *_a: Any) -> None:
        return None


class _Daemon:
    def __init__(self, controller: Any) -> None:
        self.controller = controller
        self.bus = EventBus()
        self._tasks: list[Any] = []
        self.config = SimpleNamespace(mic_button_toggles_system=True)
        self._parando = False

    def _is_stopping(self) -> bool:
        return self._parando

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)


@pytest.fixture()
def mundo(monkeypatch: pytest.MonkeyPatch) -> Any:
    from hefesto_dualsense4unix.daemon.subsystems import bt_mic
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone as ele

    def _recusa(*a: Any, **k: Any) -> Any:
        raise AssertionError(f"processo no teste: {a!r}")

    monkeypatch.setattr(subprocess, "run", _recusa)
    monkeypatch.setattr(subprocess, "Popen", _recusa)
    monkeypatch.setattr(lifecycle, "INPUT_GRACE_SEC", 0.05)
    monkeypatch.setattr(mic_da_mesa, "INTERVALO_S", 0.01)
    monkeypatch.setattr(hotkey, "MIC_SOSSEGO_S", 0.3)
    hotkey._CANAL_POR_UNIQ.clear()
    pipewire = _PipeWire(monkeypatch)
    registro = bt_mic.RegistroDePedidosDeCanal()
    sub = bt_mic.BtMicSubsystem(registro=registro)
    sub._gerenciador = _GerenciadorDeMentira()
    handles = {_n(u): _Handle() for u, _ in MESA_DELA}
    mesa = _Mesa(handles)
    sub._backend = mesa
    anteriores = ele.registrar_dizedor_do_no_ar(
        sub.no_ar, sub.esquecer_a_palavra, sub.palavra_no_ar
    )
    pedidor_anterior = ele.registrar_pedidor_de_canal(sub.pedir_canal)
    recados: list[dict[str, Any]] = []

    def _anotar(_daemon: Any, uniq: str, **kw: Any) -> None:
        recados.append({"uniq": uniq, **kw})

    monkeypatch.setattr(recado_do_microfone, "anotar", _anotar)
    try:
        yield SimpleNamespace(
            pipewire=pipewire,
            registro=registro,
            mesa=mesa,
            handles=handles,
            daemon=_Daemon(mesa),
            recados=recados,
        )
    finally:
        ele.registrar_dizedor_do_no_ar(*anteriores)
        ele.registrar_pedidor_de_canal(pedidor_anterior)
        hotkey._CANAL_POR_UNIQ.clear()


async def _corrida(mundo: Any, *, aperto_em_s: float) -> _Aparelho:
    """O 🎙 cala o P3; o dedo aperta `aperto_em_s` depois; o laço inteiro corre."""
    d = mundo.daemon
    aparelho = _Aparelho(mundo.handles[_n(P3)])
    tarefas = [
        asyncio.create_task(aparelho.correr()),
        asyncio.create_task(mic_da_mesa.mic_da_mesa_loop(d)),
        asyncio.create_task(hotkey.mic_button_loop(d)),
    ]
    try:
        for outro in (P1, P2, P4):
            mundo.handles[_n(outro)]._consumir_report(_report("cabo", status=LIVRE, botao=False))
        await asyncio.sleep(0.15)
        assert (await hotkey.ligar_o_microfone(d, P3, ligado=True)).feito
        assert (await hotkey.ligar_o_microfone(d, P2, ligado=True)).feito
        await asyncio.sleep(0.3)
        assert aparelho.bit is False
        mundo.recados.clear()

        await hotkey.ligar_o_microfone(d, P3, ligado=False)
        await asyncio.sleep(aperto_em_s)
        await aparelho.apertar()
        await asyncio.sleep(0.4)
    finally:
        d._parando = True
        aparelho.parar()
        for t in tarefas:
            t.cancel()
        await asyncio.gather(*tarefas, return_exceptions=True)
        for t in list(d._tasks):
            t.cancel()
        await asyncio.gather(*d._tasks, return_exceptions=True)
    return aparelho


@pytest.mark.parametrize("aperto_em_s", [0.0, 0.4])
def test_o_aperto_dentro_da_escrita_e_depois_dela_dao_o_mesmo_ato(
    mundo: Any, aperto_em_s: float
) -> None:
    """Logo após o 🎙 (bit velho) ou a 0,4 s (confirmado): P3 no ar, sem recado, firmware ligado."""
    aparelho = asyncio.run(_corrida(mundo, aperto_em_s=aperto_em_s))

    no_ar = mundo.registro.no_ar()
    assert no_ar.get(_n(P3)) is True, f"o aperto não pôs o P3 de volta no ar: {no_ar}"
    assert no_ar.get(_n(P2)) is True, f"o P2 saiu do ar com a corrida do P3: {no_ar}"
    recusas = [r for r in mundo.recados if not r["ok"] or r["motivo"]]
    assert recusas == [], f"o aperto deixou frase em cartão: {recusas}"
    assert aparelho.bit is False, (
        "o dedo pediu LIGAR e o firmware terminou mudo: quem escreveu por último "
        "foi o toggle do kernel, não o pedido"
    )
    assert mundo.handles[_n(P3)]._mic_mute_desejado is None, (
        "a posse do mudo não voltou ao kernel depois do ato"
    )


_NOMES_DO_ECO = ("_ECO_DO_ATO", "ECO_DO_ATO_S", "_marcar_eco_do_ato", "_borda_e_eco_do_ato")


def test_o_laco_do_botao_nao_carrega_o_eco() -> None:
    """Os nomes que o laço consulta não incluem o eco; o módulo não o define."""
    nomes = set(hotkey.mic_button_loop.__code__.co_names)
    achados = [n for n in _NOMES_DO_ECO if n in nomes]
    assert achados == [], f"o laço do botão ainda consulta o eco: {achados}"
    ainda = [n for n in _NOMES_DO_ECO if hasattr(hotkey, n)]
    assert ainda == [], f"o eco segue definido em hotkey: {ainda}"
    assert "ECO_DO_ATO_S" not in hotkey.__all__


def test_a_metade_do_firmware_nao_tem_mais_o_parametro_do_eco() -> None:
    import inspect

    assert "marcar_eco" not in inspect.signature(hotkey._metade_do_firmware).parameters


class _ControleQueMudouDeDono:
    """A posse já é de OUTRO ato (o aperto soltou a velha e tomou uma nova)."""

    def __init__(self, posse: bool | None) -> None:
        self.posse = posse
        self.escritas: list[bool | None] = []

    def audio_status_for(self, uniq: str | None = None) -> dict[str, bool]:
        return {"mic_mudo": True}

    def microphone_mute_for(self, uniq: str | None = None) -> bool | None:
        return self.posse

    def set_microphone_mute(self, muted: bool | None, *, uniq: str | None = None) -> bool:
        self.escritas.append(muted)
        return True


@pytest.mark.parametrize("posse", [False, None])
def test_a_confirmacao_do_ato_velho_nao_devolve_a_posse_do_ato_novo(
    posse: bool | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O bit confirmou o calar velho, mas a posse já pede LIGAR (ou é do kernel)."""
    monkeypatch.setattr(hotkey, "PASSO_DA_CONFIRMACAO_S", 0.001)
    controle = _ControleQueMudouDeDono(posse)
    daemon = SimpleNamespace(
        controller=controle,
        _is_stopping=lambda: False,
        _tasks=[],
    )

    async def _run_blocking(fn: Any, *args: Any) -> Any:
        return fn(*args)

    daemon._run_blocking = _run_blocking  # type: ignore[attr-defined]
    recados: list[Any] = []
    monkeypatch.setattr(recado_do_microfone, "anotar", lambda *a, **k: recados.append(k))

    asyncio.run(hotkey._confirmar_e_devolver(daemon, P3, True))  # type: ignore[arg-type]

    assert controle.escritas == [], (
        "a confirmação do ato velho devolveu a posse que o ato novo tinha tomado: "
        f"o pedido novo não vai ao fio ({controle.escritas})"
    )
    assert recados == [], "o ato superado deixou recado de represamento"


def test_a_confirmacao_do_proprio_ato_devolve_a_posse() -> None:
    """O outro lado: a posse ainda é a deste ato e o bit confirmou — devolve."""
    controle = _ControleQueMudouDeDono(True)
    daemon = SimpleNamespace(
        controller=controle,
        _is_stopping=lambda: False,
        _tasks=[],
    )

    async def _run_blocking(fn: Any, *args: Any) -> Any:
        return fn(*args)

    daemon._run_blocking = _run_blocking  # type: ignore[attr-defined]
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(hotkey, "PASSO_DA_CONFIRMACAO_S", 0.001)
        asyncio.run(hotkey._confirmar_e_devolver(daemon, P3, True))  # type: ignore[arg-type]
    assert controle.escritas == [None]
