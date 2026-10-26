"""O perfil de evento entra quando o evento chega.

OS-EVENTOS-DO-PERFIL-ENTRAM-PELO-QUE-O-DAEMON-JA-SABE-01.

MORDIDAS:
  * tire o `bus.subscribe` de `ouvir_as_conexoes`: o «Controle conectado» não entra;
  * troque `create_subprocess_exec` por `create_subprocess_shell(texto)`: a injeção cria o arquivo;
  * tire o `not p.so_entra_por_evento` da escolha por janela: o perfil de evento entra pela janela.
  * tire o `try` de `_entrar` ou de `_perfis_do`: a falha de ativar ou de ler derruba o laço.
  * tire o `_publicar_quem_entrou` de `connection.anunciar_bordas_por_alvo`: o segundo controle
    conecta calado, e o «Controle conectado» só vale para o primeiro.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

import hefesto_dualsense4unix.daemon.connection as conn_mod
from hefesto_dualsense4unix.core.events import EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems.eventos_do_perfil import (
    EventosDoPerfil,
    argv_do_comando,
    rodar_o_comando,
)
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile


def _perfil(nome: str, evento: str | None, *, comando: str | None = None,
            classe: str | None = None, prioridade: int = 0) -> Profile:
    match = MatchCriteria(window_class=[classe] if classe else [])
    return Profile(name=nome, match=match, alvo="eventos", evento=evento,
                   evento_comando=comando, priority=prioridade)


class Daemon(SimpleNamespace):
    """O serviço de mentira: o barramento de verdade, o perfil ativo e o jogo em cena."""

    def __init__(self, ativo: str = "Navegação", appid: int | None = None) -> None:
        store = MagicMock(active_profile=ativo, native_mode_active=False)
        store.manual_profile_lock_active.return_value = False
        super().__init__(bus=EventBus(), store=store, appid_em_cena=appid)


def _motor(daemon: Daemon, perfis: list[Profile], rodar: Any = rodar_o_comando
           ) -> tuple[EventosDoPerfil, list[str]]:
    ativados: list[str] = []

    async def ativar(nome: str) -> None:
        ativados.append(nome)
        daemon.store.active_profile = nome

    return EventosDoPerfil(daemon, ativar, lambda: perfis, rodar=rodar), ativados


async def _publicar_e_esperar(daemon: Daemon, motor: EventosDoPerfil) -> None:
    tarefa = asyncio.create_task(motor.ouvir_as_conexoes())
    for _ in range(50):
        if daemon.bus.subscriber_count(EventTopic.CONTROLLER_CONNECTED):
            break
        await asyncio.sleep(0.01)
    daemon.bus.publish(EventTopic.CONTROLLER_CONNECTED, {"transport": "bt"})
    for _ in range(50):
        await asyncio.sleep(0.01)
    tarefa.cancel()
    with pytest.raises(asyncio.CancelledError):
        await tarefa


def test_o_controle_conectado_ativa_o_perfil_de_evento() -> None:
    daemon = Daemon()
    motor, ativados = _motor(daemon, [_perfil("Ao conectar", "controle_conectado"),
                                      _perfil("Cena", "cena")])
    asyncio.run(_publicar_e_esperar(daemon, motor))
    assert ativados == ["Ao conectar"]


def test_com_jogo_em_cena_o_evento_nao_troca_o_perfil() -> None:
    daemon = Daemon(ativo="Elden Ring", appid=1245620)
    motor, ativados = _motor(daemon, [_perfil("Ao conectar", "controle_conectado")])
    asyncio.run(_publicar_e_esperar(daemon, motor))
    assert ativados == []


def test_a_escolha_dela_recente_e_o_modo_nativo_seguram_o_perfil() -> None:
    for como in ("trava", "nativo"):
        daemon = Daemon()
        if como == "trava":
            daemon.store.manual_profile_lock_active.return_value = True
        else:
            daemon.store.native_mode_active = True
        motor, ativados = _motor(daemon, [_perfil("Ao conectar", "controle_conectado")])
        assert asyncio.run(motor.ao_conectar()) is False and ativados == [], como


def test_vale_o_de_maior_prioridade() -> None:
    daemon = Daemon()
    motor, ativados = _motor(daemon, [_perfil("B", "controle_conectado"),
                                      _perfil("A", "controle_conectado", prioridade=5)])
    asyncio.run(motor.ao_conectar())
    assert ativados == ["A"]


def test_o_perfil_de_evento_nao_entra_pela_janela_sozinho() -> None:
    """Só o «Programa aberto» entra pelo `match`; os outros momentos esperam o evento."""
    loader.save_profile(_perfil("Ao conectar", "controle_conectado", classe="kate"),
                        origem="régua")
    loader.save_profile(_perfil("Abriu o Kate", "programa_aberto", classe="kate"),
                        origem="régua")
    manager = ProfileManager(controller=MagicMock())
    escolhido = manager.select_for_window({"wm_class": "kate", "title": "", "exe": ""})
    assert escolhido is not None and escolhido.name == "Abriu o Kate"
    loader.delete_profile("Abriu o Kate")
    assert manager.select_for_window({"wm_class": "kate", "title": "", "exe": ""}) is None


def test_o_meu_comando_entra_com_zero_e_so_na_passagem() -> None:
    daemon = Daemon()
    certo = _perfil("Deu certo", "meu_comando", comando="true")
    errado = _perfil("Deu errado", "meu_comando", comando="false", prioridade=9)
    motor, ativados = _motor(daemon, [errado, certo])
    assert asyncio.run(motor.ver_os_comandos()) == ["Deu certo"]
    daemon.store.active_profile = "Navegação"
    assert asyncio.run(motor.ver_os_comandos()) == [], "entrou de novo sem o comando mudar"
    assert ativados == ["Deu certo"]


def test_o_comando_que_dorme_estoura_o_prazo_sem_travar() -> None:
    inicio = time.monotonic()
    certo, porque = asyncio.run(rodar_o_comando("sleep 20", prazo=0.3))
    assert not certo and "prazo" in porque
    assert time.monotonic() - inicio < 3


def test_o_comando_nao_passa_por_shell(tmp_path: Path) -> None:
    """A prova da D-2010-O-COMANDO-DO-EVENTO-RODA-COMO-AJUDANTE."""
    alvo = tmp_path / "x"
    certo, _ = asyncio.run(rodar_o_comando(f"a; touch {alvo}"))
    assert not certo and not alvo.exists(), "o «;» foi lido por um shell"
    with pytest.raises(ValueError):
        argv_do_comando("echo 'aberto")
    assert argv_do_comando("   ") == []


def test_o_sh_de_caminho_absoluto_roda_por_bash(tmp_path: Path) -> None:
    script = tmp_path / "pronto.sh"
    script.write_text("exit 0\n", encoding="utf-8")
    assert argv_do_comando(str(script)) == ["bash", str(script)]
    assert asyncio.run(rodar_o_comando(str(script)))[0] is True


def test_o_comando_ausente_nao_entra() -> None:
    certo, porque = asyncio.run(rodar_o_comando("comando-que-nao-existe-na-maquina"))
    assert not certo and "não abriu" in porque


def test_a_falha_de_ler_ou_de_ativar_nao_derruba_o_laco() -> None:
    """O laço do «Meu comando» não tem `try`: a leitura e a ativação dizem a própria falha."""
    daemon = Daemon()

    async def ativar_que_falha(_nome: str) -> None:
        raise RuntimeError("o perfil não carregou")

    def ler_que_falha() -> list[Profile]:
        raise OSError("disco fora")

    certo = [_perfil("Deu certo", "meu_comando", comando="true")]
    sem_disco = EventosDoPerfil(daemon, ativar_que_falha, ler_que_falha)
    assert asyncio.run(sem_disco.ver_os_comandos()) == []
    assert asyncio.run(sem_disco.ao_conectar()) is False
    sem_ativar = EventosDoPerfil(daemon, ativar_que_falha, lambda: certo)
    assert asyncio.run(sem_ativar.ver_os_comandos()) == []

    async def duas_voltas() -> None:
        tarefa = asyncio.create_task(sem_ativar.perguntar_os_comandos(intervalo=0.01))
        await asyncio.sleep(0.2)
        assert not tarefa.done(), "o laço do comando morreu na falha"
        tarefa.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarefa

    asyncio.run(duas_voltas())


def test_as_aspas_abertas_dizem_o_porque() -> None:
    certo, porque = asyncio.run(rodar_o_comando("echo 'aberto"))
    assert not certo and porque.startswith("aspas abertas")
    assert asyncio.run(rodar_o_comando("  ")) == (False, "comando vazio")


P1 = "aabbcc0000f1"
P2 = "aabbcc0000f2"
P3 = "aabbcc0000f3"


class _MesaDeQuatro:
    """O backend enxuto: quem está na mesa, por qual fio, e quem está trocando de fio."""

    def __init__(self, transportes: dict[str, str], trocando: frozenset[str] = frozenset()
                 ) -> None:
        self.transportes = dict(transportes)
        self.trocando = trocando

    def transportes_dos_alvos(self) -> dict[str, str]:
        return dict(self.transportes)

    def em_troca_de_transporte(self, uniq: str | None) -> bool:
        return uniq in self.trocando


async def _bordas(daemon: Any, antes: dict[str, str | None], agora: dict[str, str | None],
                  **kw: Any) -> list[dict[str, Any]]:
    fila = daemon.bus.subscribe(EventTopic.CONTROLLER_CONNECTED)
    await conn_mod.anunciar_bordas_por_alvo(daemon, antes, agora, **kw)
    vistos = []
    while not fila.empty():
        vistos.append(fila.get_nowait())
    return vistos


@pytest.fixture
def sem_som(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _nada(*_a: Any, **_k: Any) -> None:
        return None

    monkeypatch.setattr(conn_mod, "reapply_speaker_after_connect", _nada)
    monkeypatch.setattr(conn_mod, "reapply_mic_after_connect", _nada)
    monkeypatch.setattr(conn_mod, "nascer_o_microfone_ao_conectar", lambda *_a, **_k: None)
    monkeypatch.setattr(conn_mod, "anunciar_a_chegada", lambda *_a, **_k: 0)


def test_o_segundo_ao_quarto_controle_tambem_e_controle_conectado(sem_som: None) -> None:
    """Com um controle de pé, o que entra ganha o `controller.connected` dele, cabo ou rádio.

    (D-2010-CADA-CONTROLE-QUE-ENTRA-E-CONTROLE-CONECTADO)
    """
    daemon = SimpleNamespace(bus=EventBus(),
                             controller=_MesaDeQuatro({P1: "usb", P2: "bt", P3: "usb"}))
    vistos = asyncio.run(_bordas(daemon, {P1: P1}, {P1: P1, P2: P2, P3: P3}))
    assert vistos == [{"transport": "bt", "uniq": P2}, {"transport": "usb", "uniq": P3}], (
        "o segundo e o terceiro controle entraram calados: o «Controle conectado» só vale "
        "para o primeiro")
    assert asyncio.run(_bordas(daemon, {P1: P1, P2: P2}, {P1: P1, P2: P2})) == []


def test_a_troca_de_transporte_nao_e_controle_conectado(sem_som: None) -> None:
    """O mesmo controle em outro fio não conecta de novo: a queda dele também foi calada."""
    daemon = SimpleNamespace(bus=EventBus(), controller=_MesaDeQuatro({P2: "usb"}))
    assert asyncio.run(_bordas(daemon, {}, {P2: P2}, troca_de_transporte=True)) == []
    assert asyncio.run(_bordas(daemon, {"/dev/hidraw7": P2}, {P2: P2})) == []
    daemon.controller.trocando = frozenset({P2})
    assert asyncio.run(_bordas(daemon, {}, {P2: P2})) == []


def test_o_segundo_controle_ativa_o_perfil_de_evento(sem_som: None) -> None:
    """De ponta a ponta: a borda do segundo controle chega ao motor e o perfil entra."""
    daemon = Daemon()
    daemon.controller = _MesaDeQuatro({P1: "usb", P2: "bt"})
    motor, ativados = _motor(daemon, [_perfil("Ao conectar", "controle_conectado")])

    async def roteiro() -> None:
        tarefa = asyncio.create_task(motor.ouvir_as_conexoes())
        for _ in range(50):
            if daemon.bus.subscriber_count(EventTopic.CONTROLLER_CONNECTED):
                break
            await asyncio.sleep(0.01)
        await conn_mod.anunciar_bordas_por_alvo(daemon, {P1: P1}, {P1: P1, P2: P2})
        for _ in range(50):
            await asyncio.sleep(0.01)
        tarefa.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarefa

    asyncio.run(roteiro())
    assert ativados == ["Ao conectar"]
