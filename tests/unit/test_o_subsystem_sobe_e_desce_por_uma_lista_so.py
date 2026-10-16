"""O-SUBSYSTEM-SOBE-E-DESCE-POR-UMA-LISTA-SO-01 — a lista é a única fonte de partida e de parada.

Antes, `SUBSYSTEM_REGISTRY` era uma lista que nenhum código percorria, e o `run()` e o
`shutdown()` chamavam cada subsystem pelo nome. Foi assim que o `BtMicSubsystem` e o
`AltoFalanteSubsystem` nasceram órfãos, e que oito classes ficaram vivas só nos testes.
Hoje o `run()` percorre a lista (`subir`) e o `shutdown()` a percorre pela ordem de parada
declarada em cada entrada (`parar`).

O que esta régua mede, sempre pelo EFEITO:

1. um `Daemon` de verdade sobe e para, e a sequência das partidas é a da lista e a das
   paradas é a declarada nela (som e microfone antes do IPC, controle por último);
2. um subsystem de mentira acrescentado SÓ à lista sobe e para sem outra linha;
3. nenhuma chamada a `_safe_start` mora fora da lista, e o `shutdown` não nomeia subsystem.

MORDIDAS (cada uma foi feita, vista reprovar e devolvida):
- `await self._safe_start("fora", ...)` no `run()` reprova (1) e (3);
- a parada de uma entrada arrancada (`parada=_parar_bt_mic`) reprova (1);
- `parar()` presa a uma cópia da lista de import reprova (2);
- `parar_em` de uma entrada trocado de lugar reprova (1);
- a parada do broker sem o `finally` (o executor que falha pula o cliente) reprova (4).
"""
from __future__ import annotations

import ast
import asyncio
import dataclasses
import inspect
import re
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon import subsystems as lista
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import SUBSYSTEM_REGISTRY, Passo
from hefesto_dualsense4unix.testing.fake_controller import FakeController

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
LISTA = SRC / "daemon" / "subsystems" / "__init__.py"


# -- a lista em si: o que toda entrada tem de ser --------------------------------


def test_os_nomes_da_lista_sao_unicos() -> None:
    nomes = [p.nome for p in SUBSYSTEM_REGISTRY]
    assert len(nomes) == len(set(nomes)), f"nome repetido na lista: {nomes}"


def test_a_ordem_de_parada_e_declarada_e_sem_empate() -> None:
    """Quem para declara ONDE (`parar_em`), e dois não dividem a mesma posição."""
    com_parada = [p for p in SUBSYSTEM_REGISTRY if p.parada is not None]
    sem_posicao = [p.nome for p in com_parada if not isinstance(p.parar_em, int)]
    assert not sem_posicao, f"param sem dizer em que posição: {sem_posicao}"
    sobra = [p.nome for p in SUBSYSTEM_REGISTRY if p.parada is None and p.parar_em is not None]
    assert not sobra, f"declaram posição de parada sem parada: {sobra}"
    posicoes = [p.parar_em for p in com_parada]
    assert len(posicoes) == len(set(posicoes)), f"posição de parada repetida: {posicoes}"


def test_toda_entrada_sobe_ou_para_e_so_quem_sobe_tem_fase_e_essencial() -> None:
    for passo in SUBSYSTEM_REGISTRY:
        assert passo.partida is not None or passo.parada is not None, (
            f"`{passo.nome}` não sobe nem para: entrada que não faz nada"
        )
        if passo.partida is None:
            assert not passo.depois_do_controle, f"`{passo.nome}` tem fase sem partida"
            assert passo.essencial is None, f"`{passo.nome}` é essencial sem partida"
            assert passo.quando is None, f"`{passo.nome}` tem condição sem partida"


def test_a_ordem_de_parada_do_motor_e_a_declarada() -> None:
    declarada = [p.nome for p in sorted(
        (p for p in SUBSYSTEM_REGISTRY if p.parada is not None),
        key=lambda p: p.parar_em or 0,
    )]
    assert [p.nome for p in lista.a_ordem_de_parada()] == declarada


def _nome_da_lista(classe: str) -> str:
    """`AltoFalanteSubsystem` -> `alto_falante`."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", classe.removesuffix("Subsystem")).lower()


def test_toda_classe_subsystem_do_pacote_esta_na_lista() -> None:
    """A classe que ninguém lista nasce órfã (foi o BtMic e o AltoFalante)."""
    nomes = {p.nome for p in SUBSYSTEM_REGISTRY}
    orfas: list[str] = []
    for arquivo in sorted((SRC / "daemon" / "subsystems").glob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if (
                isinstance(no, ast.ClassDef)
                and no.name.endswith("Subsystem")
                and no.name != "Subsystem"
                and _nome_da_lista(no.name) not in nomes
            ):
                orfas.append(f"{arquivo.name}::{no.name}")
    assert not orfas, f"classe(s) Subsystem fora da lista: {orfas}"


# -- (3) nenhuma chamada por nome fora da lista -----------------------------------


def _chamadas_de_safe_start() -> list[str]:
    achados: list[str] = []
    for arquivo in sorted(SRC.rglob("*.py")):
        if arquivo == LISTA:
            continue
        texto = arquivo.read_text(encoding="utf-8")
        if "_safe_start" not in texto:
            continue
        for no in ast.walk(ast.parse(texto)):
            if (
                isinstance(no, ast.Call)
                and isinstance(no.func, ast.Attribute)
                and no.func.attr == "_safe_start"
            ):
                achados.append(f"{arquivo.relative_to(RAIZ)}:{no.lineno}")
    return achados


def test_nenhum_safe_start_mora_fora_da_lista() -> None:
    fora = _chamadas_de_safe_start()
    assert not fora, (
        f"`_safe_start` chamado fora de `daemon/subsystems/__init__.py`: {fora}. "
        "Subsystem novo é UMA entrada na lista, não uma linha no `run()`."
    )


def test_a_lista_chama_o_safe_start_uma_vez_so_e_pelo_nome_da_entrada() -> None:
    arvore = ast.parse(LISTA.read_text(encoding="utf-8"))
    chamadas = [
        no for no in ast.walk(arvore)
        if isinstance(no, ast.Call)
        and isinstance(no.func, ast.Attribute)
        and no.func.attr == "_safe_start"
    ]
    assert len(chamadas) == 1
    primeiro = chamadas[0].args[0]
    assert isinstance(primeiro, ast.Attribute) and primeiro.attr == "nome"


def test_o_shutdown_nao_nomeia_subsystem_nenhum() -> None:
    from hefesto_dualsense4unix.daemon import connection

    fonte = inspect.getsource(connection.shutdown)
    assert "_stop_" not in fonte and "getattr" not in fonte
    assert "parar(" in fonte


def test_o_run_nao_nomeia_start_nem_stop_de_subsystem() -> None:
    fonte = inspect.getsource(Daemon.run)
    assert "_safe_start" not in fonte
    assert not re.findall(r"self\._(?:start|stop)_\w+\(", fonte), "chama start/stop por nome"
    assert "subir(self)" in fonte


# -- (1) e (2) o Daemon de verdade ------------------------------------------------


def _estado() -> ControllerState:
    return ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb",
        buttons_pressed=frozenset(),
    )


def _config() -> DaemonConfig:
    """Tudo o que tem condição de config, ligado: a lista inteira passa a querer subir."""
    return DaemonConfig(
        poll_hz=120, auto_reconnect=False, ipc_enabled=True, udp_enabled=True,
        dsu_enabled=True, autoswitch_enabled=True, mouse_emulation_enabled=True,
        gamepad_emulation_enabled=True, keyboard_emulation_enabled=True,
        mic_button_toggles_system=True,
    )


def _gravador(passo: Passo, partidas: list[str], paradas: list[str]) -> Passo:
    """O mesmo passo, com a partida de mentira (não toca o aparelho) e a parada que anota
    e DEPOIS roda a de verdade (a limpeza real das tarefas e do controle tem de acontecer)."""
    original = passo.parada

    async def parada(daemon: Any) -> None:
        paradas.append(passo.nome)
        if original is not None:
            resultado = original(daemon)
            if inspect.isawaitable(resultado):
                await resultado

    return dataclasses.replace(
        passo,
        partida=(lambda daemon: partidas.append(passo.nome)) if passo.partida else None,
        parada=parada if original is not None else None,
    )


def _passo_de_mentira(partidas: list[str], paradas: list[str]) -> Passo:
    async def para(daemon: Any) -> None:
        paradas.append("de_mentira")

    return Passo(
        "de_mentira",
        partida=lambda daemon: partidas.append("de_mentira"),
        parada=para,
        parar_em=5,
    )


async def _sobe_e_para(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
    *,
    mais: bool = False,
) -> tuple[Daemon, list[str], list[str], list[str]]:
    """Sobe um `Daemon` real com a lista de gravadores e o derruba.

    Devolve (daemon, nomes pedidos ao `_safe_start`, partidas gravadas, paradas gravadas).
    """
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path_factory.mktemp("hsd", numbered=True)))
    from hefesto_dualsense4unix.utils import session

    monkeypatch.setattr(session, "load_paused_state", lambda: False)
    monkeypatch.setattr(session, "load_mouse_emulation", lambda: (False, None, None))
    monkeypatch.setattr(session, "load_gamepad_emulation", lambda: (False, None))
    monkeypatch.setattr(session, "load_keyboard_preference", lambda: None)

    partidas: list[str] = []
    paradas: list[str] = []
    registro = [_gravador(p, partidas, paradas) for p in SUBSYSTEM_REGISTRY]
    if mais:
        registro.append(_passo_de_mentira(partidas, paradas))
    monkeypatch.setattr(lista, "SUBSYSTEM_REGISTRY", tuple(registro))

    pedidos: list[str] = []
    safe_start = Daemon._safe_start

    async def _anota(self: Daemon, name: str, *args: Any, **kw: Any) -> None:
        pedidos.append(name)
        await safe_start(self, name, *args, **kw)

    monkeypatch.setattr(Daemon, "_safe_start", _anota)

    daemon = Daemon(
        controller=FakeController(transport="usb", states=[_estado()]),
        bus=EventBus(),
        config=_config(),
    )
    run_task = asyncio.create_task(daemon.run())
    try:
        for _ in range(500):
            if daemon._reconnect_task is not None:
                break
            await asyncio.sleep(0.02)
        assert daemon._reconnect_task is not None, "o run() não chegou ao fim da subida"
        assert paradas == [], "algo parou antes de o daemon ser parado"
    finally:
        daemon.stop()
        await asyncio.wait_for(run_task, timeout=20)
    return daemon, pedidos, partidas, paradas


def _o_que_sobe(daemon: Daemon) -> list[str]:
    """Os nomes que a lista manda subir com a config de agora, na ordem em que estão."""
    return [
        p.nome for p in SUBSYSTEM_REGISTRY
        if p.partida is not None and (p.quando is None or p.quando(daemon.config))
    ]


@pytest.mark.asyncio
async def test_o_daemon_sobe_pela_ordem_da_lista_e_para_pela_ordem_declarada(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory,
) -> None:
    daemon, pedidos, partidas, paradas = await _sobe_e_para(monkeypatch, tmp_path_factory)

    esperado = _o_que_sobe(daemon)
    assert "mods" in esperado and "ipc" in esperado and "bt_mic" in esperado
    assert pedidos == esperado, "o `_safe_start` recebeu algo que a lista não mandou subir"
    assert partidas == esperado, "a partida gravada não é a da lista"
    assert pedidos[-1] == "mods", "as modificações sobem DEPOIS do controle"

    declarada = [p.nome for p in lista.a_ordem_de_parada()]
    assert paradas == declarada, "a parada não seguiu a ordem declarada na lista"

    def antes(a: str, b: str) -> None:
        assert paradas.index(a) < paradas.index(b), f"`{a}` tem de parar antes de `{b}`"

    for som in ("mods", "bt_mic", "alto_falante", "conexoes", "central_do_radio", "plugins"):  # noqa-acento: nome do subsystem, a chave do diário
        antes(som, "ipc")
    antes("ipc", "tarefas")
    antes("tarefas", "controle")
    assert paradas[0] == "mods"
    assert paradas[-1] == "controle", "o controle é a última coisa a ir"


@pytest.mark.asyncio
async def test_um_subsystem_de_mentira_acrescentado_so_a_lista_sobe_e_para(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """A entrada nova não pede outra linha no `run()` nem no `shutdown()`."""
    daemon, pedidos, partidas, paradas = await _sobe_e_para(
        monkeypatch, tmp_path_factory, mais=True
    )
    assert "de_mentira" in pedidos
    assert partidas.count("de_mentira") == 1
    assert paradas.count("de_mentira") == 1
    assert paradas.index("de_mentira") < paradas.index("bt_mic"), (
        "`parar_em=5` é antes de todas: a posição declarada na entrada manda"
    )
    assert paradas[-1] == "controle"
    assert daemon._failed_subsystems == {}


# -- a parada que falha não pula a seguinte, e deixa rastro ----------------------


@pytest.mark.asyncio
async def test_a_parada_do_broker_com_o_executor_quebrado_ainda_solta_o_cliente() -> None:
    """O executor que levanta não pode deixar o cliente aberto; a falha chega ao `parar`,
    que a escreve no diário e segue para o passo seguinte."""
    fechou: list[str] = []

    class _Executor:
        def shutdown(self, **_: Any) -> None:
            raise RuntimeError("executor quebrado")

    class _Cliente:
        def close(self) -> None:
            fechou.append("cliente")

    daemon = type("D", (), {})()
    daemon._hidraw_broker_executor = _Executor()
    daemon._hidraw_broker_client = _Cliente()
    broker = next(p for p in SUBSYSTEM_REGISTRY if p.nome == "broker")
    outro: list[str] = []
    passos = (
        broker,
        Passo("depois", parada=lambda d: outro.append("seguiu"),
              parar_em=(broker.parar_em or 0) + 1),
    )
    original = lista.SUBSYSTEM_REGISTRY
    lista.SUBSYSTEM_REGISTRY = passos  # type: ignore[assignment]
    try:
        await lista.parar(daemon)
    finally:
        lista.SUBSYSTEM_REGISTRY = original
    assert fechou == ["cliente"], "o cliente do broker ficou aberto"
    assert daemon._hidraw_broker_executor is None
    assert daemon._hidraw_broker_client is None
    assert outro == ["seguiu"], "a parada seguinte não rodou"
