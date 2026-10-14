"""O stop do som tem orçamento e não pergunta ao servidor mudo.

O-STOP-DO-SOM-TEM-ORCAMENTO-E-NAO-PERGUNTA-AO-SERVIDOR-MUDO-01. O servidor de som
é um dublê atrás do ``subprocess.run`` do ``_rodar`` de verdade: cada ``pactl``
«demora» num relógio de mentira, o mesmo do recuo e do orçamento, e estoura
quando a demora alcança o prazo que o ``_rodar`` lhe deu. A mesa é a do pior
caso: quatro nós, duas rotas cada.
"""
from __future__ import annotations

import asyncio
import inspect
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as sub_mod
from hefesto_dualsense4unix.integrations import alto_falante_bt as afb
from hefesto_dualsense4unix.integrations import dualsense_bt_audio, retrato_do_som
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import RecuoDoPactl

RAIZ = Path(__file__).resolve().parents[2]
UNIT_DAEMON = RAIZ / "assets" / "hefesto-dualsense4unix.service"
NOS = 4
#: Os dois ``join`` de 2,0 s do ``stop`` do som (a volta e o ouvinte).
JOINS_DO_SOM_S = 2 * 2.0
#: O ``join`` do ``bt_mic`` e o único estouro que ele paga (o piso do recuo).
BT_MIC_S = 2.0 + afb._TIMEOUT_PACTL_S
_SISTEMA = ("1", "module-native-protocol-unix", "")
_REAL_RUN = subprocess.run


class Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


class Servidor:
    """O servidor de som de mentira; ``demora`` é o custo de cada ``pactl``."""

    def __init__(self, relogio: Relogio, demora: float) -> None:
        self.relogio = relogio
        self.demora = demora
        self.modulos: dict[str, tuple[str, str]] = {_SISTEMA[0]: _SISTEMA[1:]}
        self.chamadas: list[tuple[str, ...]] = []
        self.descarregados: list[str] = []
        self._proximo = 100

    def carregar(self, modulo: str, argumentos: str) -> str:
        self._proximo += 1
        module_id = str(self._proximo)
        self.modulos[module_id] = (modulo, argumentos)
        return module_id

    def run(self, argv: Any, *args: Any, timeout: float | None = None, **kw: Any) -> Any:
        if not isinstance(argv, list) or argv[:1] != ["pactl"]:
            return _REAL_RUN(argv, *args, timeout=timeout, **kw)
        self.chamadas.append(tuple(argv))
        if timeout is not None and self.demora >= timeout:
            self.relogio.agora += timeout
            raise subprocess.TimeoutExpired(argv, timeout)
        self.relogio.agora += self.demora
        saida = ""
        if argv[1:4] == ["list", "short", "modules"]:
            saida = "".join(f"{i}\t{m}\t{a}\n" for i, (m, a) in self.modulos.items())
        elif argv[1] == "unload-module":
            self.modulos.pop(argv[2], None)
            self.descarregados.append(argv[2])
        return subprocess.CompletedProcess(argv, 0, stdout=saida, stderr="")

    def do_hefesto(self) -> list[str]:
        return [i for i, (_m, a) in self.modulos.items() if afb.PREFIXO_SINK_DO_SOM in a]


def _nome(uniq: str) -> str:
    return f"{afb.PREFIXO_SINK_DO_SOM}P{uniq[-1]}"


@pytest.fixture
def relogio(monkeypatch: pytest.MonkeyPatch) -> Relogio:
    r = Relogio()
    monkeypatch.setattr(afb, "relogio_do_orcamento", r)
    monkeypatch.setattr(dualsense_bt_audio, "PACTL", RecuoDoPactl(relogio=r))
    monkeypatch.setattr(afb, "nome_do_sink", _nome)
    monkeypatch.setattr(retrato_do_som, "responder", lambda _argv: None)
    monkeypatch.setattr(retrato_do_som, "escreveu", lambda _argv: None)
    monkeypatch.setattr(shutil, "which", lambda nome, *_a, **_k: f"/usr/bin/{nome}")
    return r


def _o_rodar_de_verdade() -> Any:
    """O ``_rodar`` do produto, por baixo da guarda do ``conftest`` que recusa a escrita.

    A guarda existe para o ``unload-module`` não chegar ao servidor de verdade; aqui
    o servidor é o dublê (o ``subprocess.run`` já trocado), e a escrita é o que se mede.
    """
    rodar = afb._rodar
    while rodar.__name__ != "_rodar":
        rodar = inspect.getclosurevars(rodar).nonlocals["real"]
    return rodar


def _servidor(monkeypatch: pytest.MonkeyPatch, relogio: Relogio, demora: float) -> Servidor:
    s = Servidor(relogio, demora)
    monkeypatch.setattr(subprocess, "run", s.run)
    monkeypatch.setattr(afb, "_rodar", _o_rodar_de_verdade())
    return s


def _no_de_pe(servidor: Servidor, uniq: str, *, rotas: int = 2) -> afb.SinkVirtualPipeWire:
    """Um nó como o ``iniciar`` o deixa: o módulo e as rotas no servidor e na memória."""
    no = afb.SinkVirtualPipeWire(uniq=uniq, descricao="Alto-falante")
    no._module_id = servidor.carregar(afb._MODULO_NULL_SINK, f"sink_name={no.nome} rate=48000")
    no._rotas = [
        servidor.carregar(afb._MODULO_LOOPBACK, f"source={no.nome}.monitor sink=placa_{n}")
        for n in range(rotas)
    ]
    return no


def _mesa(servidor: Servidor) -> sub_mod.GerenciadorDeNosDeSom:
    ger = sub_mod.GerenciadorDeNosDeSom(fabrica=lambda _u: None, runner=afb.rodar_pactl)
    for j in range(1, NOS + 1):
        uniq = f"aa:bb:cc:00:00:0{j}"
        ger._nos[uniq] = _no_de_pe(servidor, uniq)
    return ger


def _parar_o_som(ger: Any) -> None:
    sub = sub_mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [])
    sub._gerenciador = ger
    asyncio.run(sub.stop())


def _timeout_stop_da_unit() -> float:
    linhas = [ln for ln in UNIT_DAEMON.read_text(encoding="utf-8").splitlines()
              if ln.startswith("TimeoutStopSec=")]
    assert len(linhas) == 1, "a unit do daemon não declara o TimeoutStopSec"
    valor = linhas[0].split("=", 1)[1].strip()
    casou = re.fullmatch(r"(\d+)s?", valor)
    assert casou, f"TimeoutStopSec em forma que a régua não lê: {valor!r}"
    return float(casou.group(1))


# --- 1. O servidor travado ---------------------------------------------------------


def test_o_servidor_travado_paga_um_estouro_e_nada_mais(
    monkeypatch: pytest.MonkeyPatch, relogio: Relogio
) -> None:
    """MORDIDA: tirar a regra do servidor calado do ``parar`` ou da varredura.

    O stop já não devolve as placas: desde OS-QUATRO-EM-HARMONIA-01 (14/10/2026)
    o ganho da háptica mora no fluxo do laço, e a placa fica cheia.
    """
    servidor = _servidor(monkeypatch, relogio, demora=afb._TIMEOUT_PACTL_S)
    ger = _mesa(servidor)
    inicio = relogio.agora
    _parar_o_som(ger)
    assert relogio.agora - inicio <= afb.ORCAMENTO_DO_STOP_S
    assert len(servidor.chamadas) == 1, servidor.chamadas
    assert ger.nos == {}
    assert len(servidor.do_hefesto()) == NOS * 3, "o travado não descarrega: fica para a varredura"


# --- 2. O servidor lento, que nunca estoura --------------------------------------


def test_o_servidor_lento_cabe_no_orcamento(
    monkeypatch: pytest.MonkeyPatch, relogio: Relogio
) -> None:
    """MORDIDA: tirar o orçamento (17 perguntas de 4,9 s passam de 80 s)."""
    servidor = _servidor(monkeypatch, relogio, demora=afb._TIMEOUT_PACTL_S - 0.1)
    inicio = relogio.agora
    _parar_o_som(_mesa(servidor))
    assert relogio.agora - inicio <= afb.ORCAMENTO_DO_STOP_S
    assert servidor.chamadas, "o lento ainda é servidor: o stop começa a descarregar"


def test_o_orcamento_e_o_join_cabem_no_prazo_da_unit() -> None:
    """MORDIDA: tirar o ``TimeoutStopSec`` da unit."""
    gasto = afb.ORCAMENTO_DO_STOP_S + JOINS_DO_SOM_S + BT_MIC_S
    assert gasto < _timeout_stop_da_unit()


# --- 3. O servidor saudável não muda ----------------------------------------------


def test_o_servidor_saudavel_derruba_tudo_na_mesma_ordem(
    monkeypatch: pytest.MonkeyPatch, relogio: Relogio
) -> None:
    servidor = _servidor(monkeypatch, relogio, demora=0.0)
    ger = _mesa(servidor)
    esperado = [i for no in ger.nos.values() for i in (*reversed(no._rotas), no._module_id)]
    _parar_o_som(ger)
    assert servidor.descarregados == esperado
    assert servidor.do_hefesto() == []
    assert _SISTEMA[0] in servidor.modulos


def test_com_o_servidor_vivo_a_conferencia_ainda_roda(
    monkeypatch: pytest.MonkeyPatch, relogio: Relogio
) -> None:
    """MORDIDA: pular a conferência com o servidor vivo deixa a rota que a memória não tinha."""
    servidor = _servidor(monkeypatch, relogio, demora=0.0)
    no = _no_de_pe(servidor, "aa:bb:cc:00:00:01")
    sobra = servidor.carregar(afb._MODULO_LOOPBACK, f"source={no.nome}.monitor sink=velha")
    no.parar()
    assert sobra in servidor.descarregados
    assert servidor.do_hefesto() == []


def test_fora_do_stop_o_prazo_e_o_de_sempre(relogio: Relogio) -> None:
    assert afb._prazo_do_pactl() == afb._TIMEOUT_PACTL_S
    fim = afb.fim_do_orcamento_do_stop(3.0)
    vistos: list[float | None] = []
    afb.no_orcamento_do_stop(fim, lambda: vistos.append(afb._prazo_do_pactl()))
    relogio.agora += 3.0
    afb.no_orcamento_do_stop(fim, lambda: vistos.append(afb._prazo_do_pactl()))
    assert vistos == [3.0, None]
    assert afb._prazo_do_pactl() == afb._TIMEOUT_PACTL_S


# --- 4. O laço não espera o servidor -------------------------------------------------


class _GerenciadorDemorado:
    def __init__(self) -> None:
        self.prazos: list[float | None] = []

    def parar(self) -> None:
        self.prazos.append(afb._prazo_do_pactl())
        time.sleep(0.6)


def test_o_parar_dos_nos_corre_fora_do_laco() -> None:
    """MORDIDA: devolver o ``gerenciador.parar()`` ao laço."""
    ger = _GerenciadorDemorado()
    sub = sub_mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [])
    sub._gerenciador = ger

    async def _medir() -> float:
        batidas: list[float] = []
        chega = asyncio.Event()

        async def _batedor() -> None:
            while not chega.is_set():
                batidas.append(time.monotonic())
                await asyncio.sleep(0.01)

        tarefa = asyncio.create_task(_batedor())
        await asyncio.sleep(0.05)
        await sub.stop()
        fim = time.monotonic()
        chega.set()
        await tarefa
        serie = sorted([t for t in batidas if t <= fim] + [fim])
        return max(serie[i + 1] - serie[i] for i in range(len(serie) - 1))

    maior_silencio = asyncio.run(_medir())
    assert maior_silencio < 0.3, f"o laço ficou {maior_silencio:.2f} s parado no stop"
    (prazo,) = ger.prazos
    assert prazo is not None and prazo <= afb._TIMEOUT_PACTL_S, "o parar correu sem orçamento"
