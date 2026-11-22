"""A subida do serviço não semeia perfis no fio do laço.

A-SUBIDA-DO-SERVICO-NAO-SEMEIA-PERFIS-NO-FIO-DO-LACO-01 (22/11/2026). O corpo de `Daemon.run`
lia os perfis e o caminho do pad no fio do laço (`o_perfil_de_fora_do_jogo`, o perfil que grava e
o arquivo de máscaras, o caminho do pad, o perfil que o boot restaura), e a auditoria dos perfis
(`_audit_config_on_boot`) parava o tique e atrasava o primeiro `connect`. Medido no `servico.log`
de 21/11: 24 `laco_lento` com `tarefa=vigiado` nos 2,5 s de cada subida, até 777 ms.

O ENSAIO é a subida de verdade (`Daemon.run` com o `FakeController`, o laço de verdade e o tique de
verdade); só os subsistemas que tocariam aparelho são dublados, e cada leitura de perfil dorme 1 s
no fio em que roda. O batimento do laço mede o maior intervalo entre dois acordares. O que a
subida deixa no `config` é o mesmo de antes.

MORDIDAS (md5 conferido na volta): devolver `o_perfil_de_fora_do_jogo`, o arquivo de máscaras, o
caminho do pad ou o perfil do boot ao fio do laço reprova «a subida parou o laço»; devolver o
`_audit_config_on_boot` ao fio do laço reprova a régua da auditoria.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon import connection, lifecycle, subsystems
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import external_mask
from hefesto_dualsense4unix.profiles import loader, o_padrao_do_computador
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils import session

LEITURA_LENTA_S = 1.0
TETO_DO_LACO_PARADO_S = 0.4
PRAZO_S = 20.0


def _estados() -> list[ControllerState]:
    return [
        ControllerState(battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="usb")
        for _ in range(5)
    ]


class _Ensaio:
    """A subida inteira, com as leituras de perfil dormindo, e o batimento do laço."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.maior_parada_s = 0.0
        self.onde_dormiu: dict[str, list[bool]] = {}
        self.conectou_em: float | None = None
        self.auditoria_acabou_em: float | None = None
        self.laco_pronto = asyncio.Event()
        self.controle = _ControleQueAnota(self)

        def dormir(nome: str, devolve: Any) -> Any:
            def lento(*_a: Any, **_kw: Any) -> Any:
                try:
                    asyncio.get_running_loop()
                    no_laco = True
                except RuntimeError:
                    no_laco = False
                self.onde_dormiu.setdefault(nome, []).append(no_laco)
                time.sleep(LEITURA_LENTA_S)
                return devolve

            return lento

        def auditar(*_a: Any, **_kw: Any) -> list[tuple[str, str]]:
            time.sleep(LEITURA_LENTA_S)
            self.auditoria_acabou_em = time.monotonic()
            return []

        async def _subir(_daemon: Any, *, depois_do_controle: bool = False) -> None:
            return None

        async def _perfil(_daemon: Any) -> None:
            return None

        async def _som(_daemon: Any) -> None:
            return None

        def _religar(_daemon: Any) -> Any:
            self.laco_pronto.set()
            return asyncio.sleep(0)

        monkeypatch.setattr(lifecycle, "_importar_o_que_a_subida_usa", lambda: None)
        monkeypatch.setattr(o_padrao_do_computador, "migrar_uma_vez", lambda: None)
        monkeypatch.setattr(subsystems, "subir", _subir)
        monkeypatch.setattr(connection, "restore_last_profile", _perfil)
        monkeypatch.setattr(connection, "reaplicar_som_em_todos_os_alvos", _som)
        monkeypatch.setattr(connection, "reconnect_loop", _religar)
        monkeypatch.setattr(loader, "o_perfil_de_fora_do_jogo", dormir("de_fora", "Freestyle"))
        monkeypatch.setattr(
            external_mask, "o_arquivo_de_mascaras_vira_o_modo", dormir("mascaras", None)
        )
        monkeypatch.setattr(
            session, "load_gamepad_caminho_com_origem", dormir("caminho", ("xbox", "gesto"))
        )
        monkeypatch.setattr(
            connection, "perfil_que_o_boot_restaura", dormir("boot", None)
        )
        monkeypatch.setattr(loader, "audit_profiles", auditar)
        monkeypatch.setattr(session, "load_paused_state", lambda: False)

    async def batimento(self) -> None:
        anterior = time.monotonic()
        while True:
            await asyncio.sleep(0.01)
            agora = time.monotonic()
            self.maior_parada_s = max(self.maior_parada_s, agora - anterior)
            anterior = agora

    async def subir(self) -> Daemon:
        daemon = Daemon(
            controller=self.controle,
            config=DaemonConfig(
                poll_hz=120, ipc_enabled=False, udp_enabled=False, autoswitch_enabled=False,
            ),
        )
        pulso = asyncio.create_task(self.batimento())
        subida = asyncio.create_task(daemon.run())
        try:
            await asyncio.wait_for(self.laco_pronto.wait(), PRAZO_S)
            await asyncio.sleep(0.05)
            daemon.stop()
            await asyncio.wait_for(subida, PRAZO_S)
            for _ in range(int(3 * LEITURA_LENTA_S / 0.05)):
                if self.auditoria_acabou_em is not None:
                    break
                await asyncio.sleep(0.05)
        finally:
            pulso.cancel()
        return daemon


class _ControleQueAnota(FakeController):
    def __init__(self, ensaio: _Ensaio) -> None:
        super().__init__(transport="usb", states=_estados())
        self._ensaio = ensaio

    def connect(self) -> None:
        super().connect()
        self._ensaio.conectou_em = time.monotonic()


@pytest.mark.asyncio
async def test_a_subida_nao_para_o_laco_com_a_leitura_dos_perfis_lenta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Quatro leituras de 1 s e a auditoria: o laço nunca passa do teto parado."""
    ensaio = _Ensaio(monkeypatch)

    daemon = await ensaio.subir()

    assert ensaio.maior_parada_s < TETO_DO_LACO_PARADO_S, (
        f"a subida parou o laço {ensaio.maior_parada_s:.2f} s "
        f"(teto {TETO_DO_LACO_PARADO_S} s); leituras no fio do laço: "
        f"{[nome for nome, lidas in ensaio.onde_dormiu.items() if True in lidas]}"
    )
    assert ensaio.onde_dormiu == {
        "de_fora": [False], "mascaras": [False], "caminho": [False], "boot": [False, False],
    }, "uma leitura de perfil rodou no fio do laço, ou não rodou"
    assert daemon.config.gamepad_caminho_global == "xbox"


@pytest.mark.asyncio
async def test_a_auditoria_dos_perfis_nao_para_o_tique_nem_atrasa_o_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A auditoria dorme 1 s: o `connect` sai antes do fim da leitura e o laço segue."""
    ensaio = _Ensaio(monkeypatch)

    await ensaio.subir()

    assert ensaio.conectou_em is not None
    assert ensaio.auditoria_acabou_em is not None, "a auditoria dos perfis não chegou a rodar"
    assert ensaio.conectou_em < ensaio.auditoria_acabou_em, (
        "o `controller.connect` esperou a auditoria dos perfis"
    )


@pytest.mark.asyncio
async def test_o_que_a_subida_deixa_no_config_e_o_mesmo_de_antes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O caminho do pad e o perfil do boot, com as leituras fora do laço, chegam ao config."""
    ensaio = _Ensaio(monkeypatch)
    monkeypatch.setattr(
        connection, "perfil_que_o_boot_restaura", lambda *a, **kw: None
    )
    monkeypatch.setattr(
        session, "load_gamepad_caminho_com_origem", lambda: ("dualsense", "gesto")
    )

    daemon = await ensaio.subir()

    assert daemon.config.gamepad_caminho_global == "dualsense"
    assert daemon.config.gamepad_caminho is None
