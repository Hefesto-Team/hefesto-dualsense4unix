"""BG-02 — o daemon aprende a dizer NÃO, e o mouse ganha razão.

*"Ela liga o mouse pelo controle, o cursor não anda, e a aba não diz por quê."*

As três razões reais o produto conhecia UMA A UMA e não contava nenhuma: o
interruptor desligado, a permissão de `/dev/uinput` (sem ela o device não sobe)
e o modo jogo. O bloco `mouse_emulation` do `state_full` publicava três chaves —
`enabled`, `speed`, `scroll_speed` — e nenhuma delas responde "por que o cursor
está parado".

Do lado da janela o texto já estava pronto e MORTO: a tabela
`app/actions/mouse_actions.BLOQUEIO_DO_MOUSE_EM_PORTUGUES` foi commitada em
25/08 e não era alcançada por ninguém, porque `mouse.emulation.set` respondia
`{"status": "failed"}` sem dizer o motivo, e `frase_da_recusa_do_mouse` caía
sempre em `RECUSA_SEM_MOTIVO`. É a A-CASA-SABE-E-O-PRODUTO-NÃO-FAZ na forma
mais barata de consertar: um campo no payload.

Aqui mora o lado do DAEMON. O lado da janela está em
`test_bg02_a_aba_do_mouse_sabe_do_device.py` (aquele precisa do gi real).

Cada teste MORDE. As curas, e o que reprova ao arrancar cada uma:

- `_bloqueio_do_mouse` → sem ele o payload não tem o que publicar;
- as três chaves novas no `mouse_emulation` → `test_a_mordida_*` reprova;
- o `bloqueio` no `failed` de `mouse.emulation.set` → a recusa volta a ser muda;
- o desvio `"desligada"` → `"sem_device"` quando LIGAR falha → o motivo passa a
  ser o próprio pedido dela ("está desligada" para quem acabou de tentar ligar);
- `pontes_confirmadas` no `state_full` → o editor de perfil volta a precisar de
  uma segunda ida ao daemon por gesto.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon import ipc_handlers as ih
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.lifecycle import (
    CALADA_VPAD_SUSPENSO,
    Daemon,
    DaemonConfig,
)
from hefesto_dualsense4unix.testing import FakeController


class _FakeDaemonMouse:
    """Dublê mínimo do daemon para o payload do mouse.

    Molde de `_FakeDaemonIpc` (test_emulacao_no_jogo_teclado.py), com o par
    trocado: `_mouse_device` no lugar de `_keyboard_device`. Sabe RECUSAR —
    `ok=False` é o device que não sobe, que é o caso da permissão ausente em
    `/dev/uinput`.
    """

    def __init__(self, enabled: bool = True, ok: bool = True) -> None:
        self.config = DaemonConfig(mouse_emulation_enabled=enabled)
        self._mouse_device: Any = MagicMock() if enabled else None
        self._emulation_suppressed = False
        self._steam_input_vpad_suspenso = False
        self._ok = ok
        self.chamadas: list[tuple[bool, int | None, int | None]] = []
        self.velocidades: list[tuple[int | None, int | None]] = []

    def set_mouse_emulation(
        self,
        enabled: bool,
        speed: int | None = None,
        scroll_speed: int | None = None,
        *,
        origin: str = "manual",
    ) -> bool:
        self.chamadas.append((enabled, speed, scroll_speed))
        if not enabled:
            self._mouse_device = None
            self.config.mouse_emulation_enabled = False
            return True
        # É o contrato de `subsystems/mouse.start_mouse_emulation`: a config só
        # é marcada DEPOIS de o device subir. Com `ok=False` ela fica em False,
        # e é justamente essa ordem que o desvio do handler precisa cobrir.
        if not self._ok:
            return False
        self._mouse_device = MagicMock()
        self.config.mouse_emulation_enabled = True
        return True

    def set_mouse_speed(
        self, speed: int | None = None, scroll_speed: int | None = None
    ) -> bool:
        self.velocidades.append((speed, scroll_speed))
        return self._ok

    def _jogo_no_controle_do_desktop(self) -> str | None:
        return CALADA_VPAD_SUSPENSO if self._steam_input_vpad_suspenso else None


class _Handlers(IpcHandlersMixin):
    def __init__(self, daemon: object) -> None:
        self.daemon = daemon  # type: ignore[assignment]


class _HandlersCompletos(IpcHandlersMixin):
    def __init__(self, daemon: object, store: Any, controller: Any) -> None:
        self.daemon = daemon  # type: ignore[assignment]
        self.store = store
        self.controller = controller


# ---------------------------------------------------------------------------
# O motivo, um a um
# ---------------------------------------------------------------------------


def test_o_bloqueio_do_mouse_percorre_os_cinco_estados() -> None:
    """Os cinco desfechos, na ordem em que quem lê a tela os encontra."""
    d = _FakeDaemonMouse(enabled=True)
    h = _Handlers(d)

    assert h._bloqueio_do_mouse() is None, "ligado e andando não é bloqueio"

    d._emulation_suppressed = True
    assert h._bloqueio_do_mouse() == "modo_jogo"
    d._emulation_suppressed = False

    d._steam_input_vpad_suspenso = True
    assert h._bloqueio_do_mouse() == CALADA_VPAD_SUSPENSO
    d._steam_input_vpad_suspenso = False

    # A RAZÃO DESTA FRENTE: interruptor em pé, device fora do ar. É o que
    # acontece com `/dev/uinput` sem permissão — a flag persistida religa no
    # boot e `UinputMouseDevice.start()` falha.
    d._mouse_device = None
    assert h._bloqueio_do_mouse() == "sem_device"

    d.config.mouse_emulation_enabled = False
    assert h._bloqueio_do_mouse() == "desligada"


def test_o_interruptor_vence_o_device_na_ordem_dos_motivos() -> None:
    """Desligada com device fora do ar diz "desligada", nunca "sem_device".

    A ordem não é estética: "sem_device" manda ela abrir a aba Sistema e
    clicar em "Aplicar correções". Dizer isso para quem simplesmente desligou o
    mouse é mandar consertar o que não está quebrado.
    """
    d = _FakeDaemonMouse(enabled=False)
    assert d._mouse_device is None
    assert _Handlers(d)._bloqueio_do_mouse() == "desligada"


def test_o_predicado_que_estoura_nao_derruba_o_payload() -> None:
    """O `state_full` roda a 10-20 Hz: um predicado torto não pode apagar a aba."""
    d = _FakeDaemonMouse(enabled=True)

    def _explode() -> str:
        raise RuntimeError("janela sumiu")

    d._jogo_no_controle_do_desktop = _explode  # type: ignore[method-assign]
    assert _Handlers(d)._bloqueio_do_mouse() is None


def test_o_mouse_e_o_teclado_leem_a_MESMA_conjuncao() -> None:  # noqa: N802  # noqa-acento: maiúsculas para destacar o ponto
    """Um dono só para o gate do poll loop — ver `_bloqueio_da_emulacao_de_desktop`.

    O `lifecycle._poll_loop` cala os dois no MESMO `if`. Duas leituras próprias
    da mesma conjunção é como as duas respostas divergem: o teclado dizendo
    "modo jogo" e o mouse dizendo "ligado e feliz" sobre o mesmo controle, no
    mesmo instante.
    """
    d = _FakeDaemonMouse(enabled=True)
    d.config.keyboard_emulation_enabled = True
    d._keyboard_device = MagicMock()  # type: ignore[attr-defined]
    h = _Handlers(d)

    for suprimido, suspenso, esperado in (
        (False, False, None),
        (True, False, "modo_jogo"),
        (False, True, CALADA_VPAD_SUSPENSO),
    ):
        d._emulation_suppressed = suprimido
        d._steam_input_vpad_suspenso = suspenso
        assert h._bloqueio_do_mouse() == esperado
        assert h._keyboard_emulation_payload()["bloqueio"] == esperado


# ---------------------------------------------------------------------------
# A MORDIDA — o payload do estado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_mordida_o_state_full_diz_por_que_o_cursor_nao_anda() -> None:
    """Interruptor LIGADO, `/dev/uinput` sem permissão: o estado tem a razão.

    Arrancar `bloqueio`/`despachando` do `_mouse_emulation_payload` faz o
    `state_full` voltar a publicar só `enabled: true` — que, com o cursor
    parado, é a tela afirmando o contrário do que ela está vendo.
    """
    daemon = Daemon(controller=FakeController(transport="usb"))
    daemon.config.mouse_emulation_enabled = True
    daemon._mouse_device = None  # o device NÃO subiu
    h = _HandlersCompletos(daemon, daemon.store, daemon.controller)

    bloco = (await h._handle_daemon_state_full({}))["mouse_emulation"]

    faltando = {"device_ativo", "despachando", "bloqueio"} - set(bloco)
    assert not faltando, (
        f"o `mouse_emulation` do state_full não publica {sorted(faltando)} — o "
        "cursor está parado com o interruptor em pé e a aba não tem o que dizer"
    )
    assert bloco["enabled"] is True, "o interruptor dela continua em pé"
    assert bloco["device_ativo"] is False
    assert bloco["despachando"] is False
    assert bloco["bloqueio"] == "sem_device", (
        "o estado não diz POR QUE o cursor está parado — a aba volta a calar"
    )


@pytest.mark.asyncio
async def test_o_state_full_nao_perdeu_as_tres_chaves_antigas() -> None:
    """FEAT-CLI-PARITY-01: o `mouse status` da CLI lê deste mesmo bloco."""
    daemon = Daemon(controller=FakeController(transport="usb"))
    daemon.config.mouse_emulation_enabled = True
    daemon.config.mouse_speed = 9
    daemon.config.mouse_scroll_speed = 3
    daemon._mouse_device = MagicMock()
    h = _HandlersCompletos(daemon, daemon.store, daemon.controller)

    bloco = (await h._handle_daemon_state_full({}))["mouse_emulation"]

    assert bloco == {
        "enabled": True,
        "speed": 9,
        "scroll_speed": 3,
        "device_ativo": True,
        "despachando": True,
        "bloqueio": None,
    }


@pytest.mark.asyncio
async def test_sem_config_acessivel_o_bloco_continua_OMITIDO() -> None:  # noqa: N802  # noqa-acento: maiúsculas para destacar o ponto
    """Contrato desde o FEAT-CLI-PARITY-01: ausência = "estado indisponível"."""
    daemon = Daemon(controller=FakeController(transport="usb"))
    h = _HandlersCompletos(None, daemon.store, daemon.controller)
    assert "mouse_emulation" not in await h._handle_daemon_state_full({})


# ---------------------------------------------------------------------------
# A MORDIDA — a recusa com motivo
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_mordida_ligar_e_falhar_devolve_o_motivo_certo() -> None:
    """A recusa deixa de ser muda — e não devolve o pedido dela como motivo.

    Arrancar o `resposta["bloqueio"]` faz `frase_da_recusa_do_mouse` cair em
    `RECUSA_SEM_MOTIVO` ("recusou e não disse por quê"), que é exatamente o
    estado de antes desta frente.

    Arrancar só o desvio `"desligada"` → `"sem_device"` é mais sutil e mais
    cruel: a resposta passa a mandar LIGAR o mouse para quem acabou de tentar
    ligar o mouse.
    """
    d = _FakeDaemonMouse(enabled=False, ok=False)
    res = await _Handlers(d)._handle_mouse_emulation_set({"enabled": True})

    assert res["status"] == "failed"
    assert res["enabled"] is False
    assert res.get("bloqueio") == "sem_device", (
        "a recusa de `mouse.emulation.set` voltou a ser muda (ou diz "
        f"{res.get('bloqueio')!r}, que manda LIGAR quem acabou de pedir para "
        "ligar) — `frase_da_recusa_do_mouse` cai em RECUSA_SEM_MOTIVO"
    )
    assert d.config.mouse_emulation_enabled is False, (
        "a régua depende de a config NÃO ter sido marcada — se este dublê "
        "parar de imitar `start_mouse_emulation`, o desvio deixa de ser medido"
    )


@pytest.mark.asyncio
async def test_o_sucesso_nao_carrega_bloqueio() -> None:
    """`bloqueio` aqui responde "por que a resposta foi NÃO" — num "sim" não há.

    O contrato antigo da resposta continua intacto (o `==` é de propósito): quem
    já lia esta resposta não ganhou chave nenhuma para tratar.
    """
    d = _FakeDaemonMouse(enabled=False)
    res = await _Handlers(d)._handle_mouse_emulation_set(
        {"enabled": True, "speed": 7, "scroll_speed": 2}
    )
    assert res == {"status": "ok", "enabled": True}


@pytest.mark.asyncio
async def test_desligar_continua_sendo_sempre_um_sim() -> None:
    d = _FakeDaemonMouse(enabled=True)
    res = await _Handlers(d)._handle_mouse_emulation_set({"enabled": False})
    assert res == {"status": "ok", "enabled": False}


@pytest.mark.asyncio
async def test_a_rota_speed_only_tambem_diz_o_motivo_quando_falha() -> None:
    """A rota dos controles deslizantes (A4) não pode ser a única muda."""
    d = _FakeDaemonMouse(enabled=True, ok=False)
    d._mouse_device = None
    res = await _Handlers(d)._handle_mouse_emulation_set({"speed": 9})
    assert res["status"] == "failed"
    assert res.get("bloqueio") == "sem_device", (
        "a rota speed-only recusou sem motivo — a mesma mudez de antes, no "
        "caminho que ela usa arrastando o controle deslizante"
    )
    assert d.velocidades == [(9, None)]


# ---------------------------------------------------------------------------
# A ponte confirmada viaja no estado
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_mordida_a_ponte_confirmada_chega_no_state_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O editor de perfil sabe do carimbo no MESMO estado que já lê no tique.

    Arrancar `result["pontes_confirmadas"]` devolve a aba de perfil à segunda
    ida ao daemon por gesto (`_buscar_as_pontes_confirmadas`).
    """
    carimbo = {"2054970": {"kind": "gamepad", "gamepad_flavor": "dualsense"}}
    monkeypatch.setattr(ih, "_pontes_confirmadas_seguro", lambda: dict(carimbo))
    daemon = Daemon(controller=FakeController(transport="usb"))
    h = _HandlersCompletos(daemon, daemon.store, daemon.controller)

    estado = await h._handle_daemon_state_full({})
    assert "pontes_confirmadas" in estado, (
        "o `state_full` não leva mais o carimbo — o editor de perfil volta a "
        "precisar de uma segunda ida ao daemon por gesto para saber se aquele "
        "jogo já tem ponte"
    )
    assert estado["pontes_confirmadas"] == carimbo


@pytest.mark.asyncio
async def test_o_tique_paga_cache_e_o_gesto_paga_o_disco(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O teto existe porque a leitura é a mais cara deste arquivo.

    `manager.pontes_confirmadas` chama `load_all_profiles()`, que abre CADA
    `.json` sob `FileLock`. Sem teto, o `state_full` leria a biblioteca inteira
    de perfis 10 a 20 vezes por segundo dentro do único event loop do daemon.

    E o gesto NÃO paga o cache: a caixa do jogo precisa ver o carimbo no
    instante seguinte a confirmá-lo.
    """
    leituras: list[int] = []

    def _contar() -> dict[str, Any]:
        leituras.append(1)
        return {}

    monkeypatch.setattr(ih, "_pontes_confirmadas_seguro", _contar)
    daemon = Daemon(controller=FakeController(transport="usb"))
    h = _HandlersCompletos(daemon, daemon.store, daemon.controller)

    for _ in range(5):
        await h._handle_daemon_state_full({})
    assert leituras == [1], f"o tique varreu o disco {len(leituras)} vezes"

    await h._handle_daemon_status({})
    await h._handle_daemon_status({})
    assert len(leituras) == 3, "o gesto passou a ler um carimbo velho"


@pytest.mark.asyncio
async def test_o_cache_vence_quando_o_tempo_passa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O teto é teto, não congelamento: passado o TTL, o disco manda de novo."""
    leituras: list[int] = []
    monkeypatch.setattr(
        ih, "_pontes_confirmadas_seguro", lambda: (leituras.append(1), {})[1]
    )
    relogio = [1000.0]
    monkeypatch.setattr(ih.time, "monotonic", lambda: relogio[0])
    daemon = Daemon(controller=FakeController(transport="usb"))
    h = _HandlersCompletos(daemon, daemon.store, daemon.controller)

    await h._handle_daemon_state_full({})
    relogio[0] += ih._PONTES_CONFIRMADAS_TTL_SEC + 0.1
    await h._handle_daemon_state_full({})
    assert len(leituras) == 2


def test_o_cache_e_por_instancia_e_nao_da_classe() -> None:
    """Class attribute com shadow na instância — o padrão dos vizinhos.

    Se ele virasse estado de CLASSE, dois daemons no mesmo processo (a suíte
    monta vários) leriam o carimbo um do outro.
    """
    assert IpcHandlersMixin._pontes_confirmadas_cache is None
    h = _Handlers(_FakeDaemonMouse())
    h._pontes_confirmadas_no_tique()
    assert h.__dict__["_pontes_confirmadas_cache"] is not None
    assert IpcHandlersMixin._pontes_confirmadas_cache is None


# "Conhece-te a ti mesmo." — Sócrates
