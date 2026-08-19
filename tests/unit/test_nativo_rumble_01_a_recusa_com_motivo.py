"""NATIVO-RUMBLE-01 — no Modo Nativo o daemon RECUSA fixar vibração, com motivo.

**O defeito, medido em 19/08/2026.** No Modo Nativo o backend muta TODA escrita
de output, e o mute é a única porta antes do `sendReport`. Um `rumble.set`
dentro do modo produzia ZERO write no fio e o daemon respondia `status: "ok"` —
a aba dizia "Vibração travada (fraca=…, forte=…)" com o motor parado.

**E a parte destrutiva não é a tela que mente.** Gravar `rumble_active` DESARMA
a cura HARM-16 (`zero_motors_on_mode_exit` só zera em passthrough): o controle
sai do Modo Nativo vibrando com o que o JOGO deixou nos motores, e ninguém mais
zera. Três portas gravavam — `rumble.set`, `rumble.stop` (com `(0,0)`, que
também não é `None`) e o "Aplicar" do RODAPÉ, que emite a seção rumble em toda
edição e não passa por handler de rumble nenhum.

**A decisão dela (19/08/2026):** o daemon recusa, com motivo — *"a aba Gatilhos
já sabe exibir recusa vinda do daemon"*. Impedir o clique na tela foi
descartado: contraria a regra de que a vontade da GUI prevalece.

O que cada teste MORDE está na docstring dele.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    RUMBLE_APLICADO,
    RUMBLE_PARADO,
    RUMBLE_RECUSADO_MODO_NATIVO,
    RUMBLE_SOLTO_NO_MODO_NATIVO,
)
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController


@pytest.fixture
async def servidor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """IpcServer + Daemon com FakeController. Devolve (server, daemon, fc)."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    store.update_controller_state(
        ControllerState(
            battery_pct=90, l2_raw=0, r2_raw=0, connected=True, transport="usb"
        )
    )
    cfg = DaemonConfig(
        poll_hz=60,
        ipc_enabled=False,
        udp_enabled=False,
        autoswitch_enabled=False,
        auto_reconnect=False,
    )
    daemon = Daemon(controller=fc, store=store, config=cfg)
    # Re-aplicar perfil na saída do modo é outro assunto e traz disco junto.
    monkeypatch.setattr(daemon, "_reapply_last_profile", lambda: None)
    manager = ProfileManager(controller=fc, store=store)
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "hefesto_test.sock",
        daemon=daemon,
    )
    await server.start()
    try:
        yield server, daemon, fc
    finally:
        await server.stop()


def _rumbles(fc: FakeController) -> list[tuple[int, int]]:
    return [c.payload for c in fc.commands if c.kind == "set_rumble"]


# --- 1. A recusa em si -----------------------------------------------------


@pytest.mark.asyncio
async def test_rumble_set_no_modo_nativo_e_recusado_com_motivo(
    servidor: Any,
) -> None:
    """A porta 1 das três: "Testar motores"/"Aplicar" da aba Rumble.

    MORDE: sem a guarda, `status` volta "ok" e `rumble_active` vira (160, 220)
    — a resposta que fazia a aba anunciar vibração com zero byte no fio.
    """
    server, daemon, fc = servidor
    daemon.set_native_mode(True, origin="manual")
    fc.commands.clear()

    r = await server._handle_rumble_set({"weak": 160, "strong": 220})

    assert r["status"] == "recusado"
    assert r["desfecho"] == RUMBLE_RECUSADO_MODO_NATIVO
    assert "Modo Nativo" in r["motivo"]
    # A verdade sobre o que FICOU, não sobre o que foi pedido.
    assert (r["weak"], r["strong"]) == (0, 0)
    assert r["passthrough"] is True
    # Nada foi armado: nem o par do daemon, nem o handle do backend.
    assert daemon.config.rumble_active is None
    assert _rumbles(fc) == []


@pytest.mark.asyncio
async def test_a_recusa_e_distinguivel_do_aplicado(servidor: Any) -> None:
    """VERDADE-01 aplicada ao rumble: um `status: "ok"` que valia para tudo foi
    a mentira que fez um laço destruir o vpad dela no meio da partida.

    MORDE: sem o campo `desfecho`, quem chama não distingue "fixei o par" de
    "recusei" a não ser adivinhando pelo `status` — e a resposta fora do modo
    perde o único carimbo que a diferencia da de dentro.
    """
    server, daemon, _fc = servidor

    fora = await server._handle_rumble_set({"weak": 160, "strong": 220})
    daemon.set_native_mode(True, origin="manual")
    dentro = await server._handle_rumble_set({"weak": 160, "strong": 220})

    assert fora["desfecho"] == RUMBLE_APLICADO
    assert dentro["desfecho"] == RUMBLE_RECUSADO_MODO_NATIVO
    assert fora["desfecho"] != dentro["desfecho"]


@pytest.mark.asyncio
async def test_fora_do_modo_nativo_o_rumble_set_continua_fixando(
    servidor: Any,
) -> None:
    """A guarda não pode cobrar pedágio de quem nunca entrou no modo.

    Hipótese tem de explicar o que JÁ funcionava: fixar vibração fora do Modo
    Nativo é o caminho normal da aba e segue intacto.
    """
    server, daemon, _fc = servidor

    r = await server._handle_rumble_set({"weak": 50, "strong": 100})

    assert r["status"] == "ok"
    assert (r["weak"], r["strong"]) == (50, 100)
    assert daemon.config.rumble_active == (50, 100)


# --- 2. O pedaço DESTRUTIVO: a HARM-16 continua armada ---------------------


@pytest.mark.asyncio
async def test_a_recusa_mantem_a_harm_16_armada_para_a_saida(
    servidor: Any,
) -> None:
    """O pedaço destrutivo, e a razão de a recusa existir.

    `zero_motors_on_mode_exit` (HARM-16) só zera os motores em passthrough
    (`rumble_active is None`), porque com par FIXADO o dono é a usuária. Um par
    gravado durante o modo desarma essa cura — e quem estava vibrando era o
    JOGO, pelo hidraw. Sem a guarda, sair do Modo Nativo deixava o controle
    vibrando para sempre.

    MORDE: sem a guarda, `rumble_active` é (160, 220) na saída e a lista de
    `set_rumble` volta VAZIA — nenhum zero chega ao hardware.
    """
    server, daemon, fc = servidor
    daemon.set_native_mode(True, origin="manual")
    await server._handle_rumble_set({"weak": 160, "strong": 220})
    fc.commands.clear()

    daemon.set_native_mode(False, origin="manual")

    assert (0, 0) in _rumbles(fc)


# --- 3. O "Parar" dentro do modo: solta o par, não fixa (0,0) --------------


@pytest.mark.asyncio
async def test_parar_no_modo_nativo_solta_o_par_em_vez_de_fixar_zero(
    servidor: Any,
) -> None:
    """A porta mais traiçoeira das três: `(0,0)` não é `None`.

    Ela clica "Parar" achando que está calando o controle, e era justamente
    esse clique que desarmava a HARM-16 e deixava o motor do jogo girando na
    saída do modo. Aqui o gesto solta o par (volta ao passthrough) e diz em voz
    alta o que NÃO consegue fazer.

    MORDE: sem a guarda, `rumble_active` fica (0, 0) e o `assert is None`
    reprova.
    """
    server, daemon, _fc = servidor
    daemon.set_native_mode(True, origin="manual")
    daemon.config.rumble_active = (120, 200)

    r = await server._handle_rumble_stop({})

    assert r["status"] == "ok"
    assert r["desfecho"] == RUMBLE_SOLTO_NO_MODO_NATIVO
    assert "Modo Nativo" in r["motivo"]
    assert r["passthrough"] is True
    assert daemon.config.rumble_active is None


@pytest.mark.asyncio
async def test_parar_no_modo_nativo_deixa_a_saida_zerar_o_hardware(
    servidor: Any,
) -> None:
    """O corolário do teste acima, e o que ele existe para proteger.

    MORDE: sem a guarda, o (0,0) fixado pelo "Parar" bloqueia a HARM-16 e a
    lista de `set_rumble` da saída volta vazia.
    """
    server, daemon, fc = servidor
    daemon.set_native_mode(True, origin="manual")
    daemon.config.rumble_active = (120, 200)
    await server._handle_rumble_stop({})
    fc.commands.clear()

    daemon.set_native_mode(False, origin="manual")

    assert (0, 0) in _rumbles(fc)


@pytest.mark.asyncio
async def test_fora_do_modo_nativo_o_parar_continua_fixando_o_silencio(
    servidor: Any,
) -> None:
    """O silêncio DELIBERADO fora do modo é `(0,0)` e continua sendo.

    Explica o que já funcionava: `rumble.stop` fixa o silêncio para o reassert
    do poll loop o re-afirmar, e é isso que impede outro write HID de reacender
    os motores.
    """
    server, daemon, _fc = servidor
    await server._handle_rumble_set({"weak": 120, "strong": 200})

    r = await server._handle_rumble_stop({})

    assert r["desfecho"] == RUMBLE_PARADO
    assert daemon.config.rumble_active == (0, 0)


# --- 4. O vazamento silencioso: o "Aplicar" do RODAPÉ ----------------------


@pytest.mark.asyncio
async def test_aplicar_do_rodape_nao_grava_rumble_active_no_modo_nativo(
    servidor: Any,
) -> None:
    """A porta 2, que não passa por handler de rumble nenhum.

    O rodapé emite a seção `rumble` em TODO "Aplicar" — mexer só no brilho já
    basta (ABAS-04). Sem esta guarda, a recusa do `rumble.set` vazaria por
    aqui e a HARM-16 seguiria desarmada.

    MORDE: sem a guarda, `rumble_active` vira (160, 220) e a seção aparece em
    `applied`.
    """
    server, daemon, _fc = servidor
    daemon.set_native_mode(True, origin="manual")

    r = await server._handle_profile_apply_draft(
        {"rumble": {"weak": 160, "strong": 220}}
    )

    assert daemon.config.rumble_active is None
    assert "rumble" not in r["applied"]
    assert "Modo Nativo" in r["failed"]["rumble"]


@pytest.mark.asyncio
async def test_aplicar_do_rodape_no_modo_nativo_nao_apaga_par_alheio(
    servidor: Any,
) -> None:
    """Recusar SEM ESCREVER, e não "gravar passthrough".

    Como a seção viaja de carona em qualquer edição, zerar aqui apagaria um par
    fixado por outro caminho num gesto que não era sobre vibração.
    """
    server, daemon, _fc = servidor
    daemon.set_native_mode(True, origin="manual")
    daemon.config.rumble_active = (10, 20)

    await server._handle_profile_apply_draft({"rumble": {"weak": 0, "strong": 0}})

    assert daemon.config.rumble_active == (10, 20)


@pytest.mark.asyncio
async def test_fora_do_modo_nativo_o_rodape_continua_aplicando(
    servidor: Any,
) -> None:
    """Explica o que já funcionava: o "Aplicar" do rodapé com par não-nulo."""
    server, daemon, _fc = servidor

    r = await server._handle_profile_apply_draft(
        {"rumble": {"weak": 160, "strong": 220}}
    )

    assert "rumble" in r["applied"]
    assert r["failed"] == {}
    assert daemon.config.rumble_active == (160, 220)
