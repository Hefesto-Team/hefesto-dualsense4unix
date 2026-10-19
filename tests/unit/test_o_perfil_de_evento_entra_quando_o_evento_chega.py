"""O perfil de evento entra quando o evento chega.

OS-EVENTOS-DO-PERFIL-ENTRAM-PELO-QUE-O-DAEMON-JA-SABE-01.

MORDIDAS:
  * tire o `bus.subscribe` de `ouvir_as_conexoes`: o «Controle conectado» não entra;
  * troque `create_subprocess_exec` por `create_subprocess_shell(texto)`: a injeção cria o arquivo;
  * tire o `not p.so_entra_por_evento` da escolha por janela: o perfil de evento entra pela janela.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

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
    alvo = tmp_path / "x"
    certo, _ = asyncio.run(rodar_o_comando(f"a; touch {alvo}"))
    assert not certo and not alvo.exists(), "o «;» foi lido por um shell"
    assert argv_do_comando("echo 'aberto") is None
    assert argv_do_comando("   ") is None


def test_o_sh_de_caminho_absoluto_roda_por_bash(tmp_path: Path) -> None:
    script = tmp_path / "pronto.sh"
    script.write_text("exit 0\n", encoding="utf-8")  # sem bit de execução: só o bash o roda
    assert argv_do_comando(str(script)) == ["bash", str(script)]
    assert asyncio.run(rodar_o_comando(str(script)))[0] is True


def test_o_comando_ausente_nao_entra() -> None:
    certo, porque = asyncio.run(rodar_o_comando("comando-que-nao-existe-na-maquina"))
    assert not certo and "não abriu" in porque
