"""A lâmpada de jogador segue o número — e a ORDEM das três repinturas.

Segunda frente do mesmo arquivo (`daemon/ipc_handlers.py`), achada por outra
onda e medida no aparelho: **renumerar trocava o `player_slot` e não movia
lâmpada nenhuma.**

A medição, com os dois DualSense dela e o daemon vivo, lendo
`/sys/class/leds`:

    identity.number.set sozinho ....... o `player_slot` troca, lâmpada
                                        NENHUMA se move
    + player_leds_set por uniq ........ o daemon responde "aplicado_em" — e
                                        nenhuma lâmpada se move
    + coop.sync ....................... as duas seguem o número

A causa, lida no código: com `coop_enabled=True` a camada do co-op fica ACIMA
do override por-uniq no merge do backend, e ela só é republicada por
`_apply_coop_player_leds`, que roda no FIM de um ciclo CHEIO de `sync()`. E o
`sync()` só faz o ciclo cheio quando `self._watch.poll() or activated or
grab_degraded or vpad_morto or retry_needed or force` — **renumerar não é
nenhum desses**, porque trocar um número não mexe em `/dev/input`. O
`reassert_resolved_outputs()` do próprio handler reafirmava então a camada
VELHA, e ficava assim até o próximo hotplug.

**A cura mora no DONO, não em quem clica.** A aba 04 tinha ganhado um contorno
próprio (um ramo que chama `coop.sync` quando o co-op está mandando); com a
linha no handler, a **janela GTK antiga fica curada junto** — o cabeçalho dela
tem exatamente o mesmo defeito e nenhum dos dois lados acendia.

**E o defeito era GÊMEO:** `identity.renumber` escreve a MESMA fila e tinha o
MESMO bloco de repintura incompleto. Curar só um dos dois deixaria metade do
defeito vivo — e é por isso que os dois passaram a chamar
`_repintar_apos_renumeracao`.

O que estes testes travam:

  * `coop.sync(force=True)` é chamado nos DOIS handlers quando algo mudou;
  * ele vem **ANTES** do `reassert_resolved_outputs` — a ordem é o conserto,
    não um detalhe: reafirmar antes de republicar reafirma o valor velho;
  * `force=True` e não `sync()` seco — sem ele o ciclo cheio não roda;
  * um no-op não repinta nada (não se paga uma varredura de `/dev/input` por
    um gesto que não mudou fila nenhuma);
  * nada disso pode derrubar a renumeração, que já aconteceu no disco.

Hermético: `config_dir` em `tmp_path`, `boot_id` fixo, MACs forjados na faixa
`aa:bb:cc` (regra da casa). Nenhum `/sys/class/leds` real é tocado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
)
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.testing import FakeController

UNIQ_A = "aabbcc000001"
UNIQ_B = "aabbcc000002"
UNIQ_C = "aabbcc000003"

BOOT = "boot-teste-lampada"


class _CoopEspiao:
    """`CoopManager` de mentira que anota COMO foi chamado, e QUANDO."""

    def __init__(self, diario: list[str]) -> None:
        self._diario = diario
        self.chamadas: list[bool] = []

    def sync(self, *, force: bool = False) -> None:
        self.chamadas.append(force)
        self._diario.append("coop.sync")


@dataclass
class _FakeDaemon:
    display_authority: str = "daemon"
    identity_registry: Any = None
    external_registry: Any = None
    _coop_manager: Any = None
    diario: list[str] = field(default_factory=list)

    def _schedule_external_tick(self) -> None:
        self.diario.append("external_tick")


@pytest.fixture
def config_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``config_dir`` em tmp + âncora fixa nos dois registros (mesmo arquivo)."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


def _servidor(
    tmp_path: Path, ds: ControllerIdentityRegistry
) -> tuple[IpcServer, _FakeDaemon, _CoopEspiao, list[str]]:
    """Servidor com os TRÊS passos instrumentados no MESMO diário.

    O diário é o instrumento inteiro: um `set` de nomes provaria que os três
    rodaram e não provaria a ORDEM — que é justamente o que estava errado.
    """
    diario: list[str] = []
    fc = FakeController(transport="usb")
    fc.connect()
    fc.reassert_resolved_outputs = lambda: diario.append("reassert")  # type: ignore[method-assign]
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)
    coop = _CoopEspiao(diario)
    daemon = _FakeDaemon(
        identity_registry=ds, external_registry=None, _coop_manager=coop, diario=diario
    )
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=tmp_path / "lampada.sock",
        daemon=daemon,
    )
    return server, daemon, coop, diario


def _mesa_de_dois(tmp_path: Path) -> tuple[IpcServer, _CoopEspiao, list[str]]:
    ds = ControllerIdentityRegistry()
    ds.sync_connected([UNIQ_A, UNIQ_B])
    server, _daemon, coop, diario = _servidor(tmp_path, ds)
    return server, coop, diario


# ---------------------------------------------------------------------------
# identity.number.set — o gesto que ela faz na aba
# ---------------------------------------------------------------------------


class TestONumeroAcendeALampada:
    @pytest.mark.asyncio
    async def test_number_set_republica_a_camada_do_coop(
        self, config_isolado: Path
    ) -> None:
        """Sem isto, o `player_slot` troca e a lâmpada não se move."""
        server, coop, _diario = _mesa_de_dois(config_isolado)

        resultado = await server._handle_identity_number_set(
            {"uniq": UNIQ_B, "number": 1}
        )

        assert resultado["ok"] is True
        assert coop.chamadas, (
            "renumerar não republicou a camada do co-op — a lâmpada fica no "
            "número velho até o próximo hotplug"
        )

    @pytest.mark.asyncio
    async def test_o_sync_e_forcado(self, config_isolado: Path) -> None:
        """`sync()` seco volta na porta: renumerar não mexe em `/dev/input`.

        O ciclo cheio (o único que chama `_apply_coop_player_leds`) exige
        `watch.poll() or activated or grab_degraded or vpad_morto or
        retry_needed or force`. Renumerar não é nenhum dos cinco primeiros.
        """
        server, coop, _diario = _mesa_de_dois(config_isolado)

        await server._handle_identity_number_set({"uniq": UNIQ_B, "number": 1})

        assert coop.chamadas == [True], (
            f"o co-op foi sincronizado sem `force=True`: {coop.chamadas}"
        )

    @pytest.mark.asyncio
    async def test_o_coop_vem_antes_do_reassert(self, config_isolado: Path) -> None:
        """A ORDEM é o conserto, não um detalhe.

        `reassert_resolved_outputs` reafirma o MERGE do backend, e a camada do
        co-op fica acima do override por-uniq nele. Reafirmar antes de
        republicar reafirma o valor VELHO — que é exatamente o defeito que
        estava no ar, com o `reassert` já no lugar.
        """
        server, _coop, diario = _mesa_de_dois(config_isolado)

        await server._handle_identity_number_set({"uniq": UNIQ_B, "number": 1})

        assert diario == ["coop.sync", "reassert", "external_tick"], (
            f"a ordem das três repinturas mudou: {diario}"
        )

    @pytest.mark.asyncio
    async def test_no_op_nao_repinta_nada(self, config_isolado: Path) -> None:
        """Pedir o número que o controle JÁ tem não paga varredura nenhuma.

        `sync(force=True)` custa uma `discover_dualsense_evdevs()` (~10-40 ms,
        PERF-MULTI-CONTROLLER-01) no event loop. Um gesto que não mudou fila
        não pode cobrá-la.
        """
        server, coop, diario = _mesa_de_dois(config_isolado)

        resultado = await server._handle_identity_number_set(
            {"uniq": UNIQ_A, "number": 1}
        )

        assert resultado["ok"] is True
        assert resultado["changed"] == {}
        assert coop.chamadas == []
        assert diario == []

    @pytest.mark.asyncio
    async def test_recusa_nao_repinta(self, config_isolado: Path) -> None:
        """Pedido inválido não move lâmpada — não houve renumeração."""
        server, coop, diario = _mesa_de_dois(config_isolado)

        resultado = await server._handle_identity_number_set(
            {"uniq": UNIQ_B, "number": 9}
        )

        assert resultado["ok"] is False
        assert resultado["reason"] == "numero_fora_da_mesa"
        assert coop.chamadas == []
        assert diario == []


# ---------------------------------------------------------------------------
# identity.renumber — o GÊMEO, com o mesmo defeito
# ---------------------------------------------------------------------------


class TestOGemeoRenumber:
    @pytest.mark.asyncio
    async def test_renumber_republica_a_camada_do_coop_na_mesma_ordem(
        self, config_isolado: Path
    ) -> None:
        """Ele escreve a MESMA fila; tinha o MESMO bloco incompleto.

        Curar só o `number.set` deixaria metade do defeito vivo — e a metade
        que sobra é a que a aba Início usa.
        """
        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B, UNIQ_C])
        # Abre um buraco na fila para o "Renumerar agora" ter o que compactar.
        ds.sync_connected([UNIQ_A, UNIQ_C])
        server, _daemon, coop, diario = _servidor(config_isolado, ds)

        resultado = await server._handle_identity_renumber({})

        assert resultado["ok"] is True
        if not resultado["renumbered"]:
            pytest.skip("nada a compactar nesta fila — o ramo não é exercitado")
        assert coop.chamadas == [True]
        assert diario == ["coop.sync", "reassert", "external_tick"]

    @pytest.mark.asyncio
    async def test_renumber_no_op_nao_repinta(self, config_isolado: Path) -> None:
        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B])
        server, _daemon, coop, diario = _servidor(config_isolado, ds)

        resultado = await server._handle_identity_renumber({})

        assert resultado["ok"] is True
        assert resultado["renumbered"] == {}
        assert coop.chamadas == []
        assert diario == []


# ---------------------------------------------------------------------------
# A renumeração já aconteceu no disco: repintar não pode derrubá-la
# ---------------------------------------------------------------------------


class TestARepinturaNaoDerrubaARenumeracao:
    @pytest.mark.asyncio
    async def test_coop_que_levanta_nao_perde_o_numero(
        self, config_isolado: Path
    ) -> None:
        """Um co-op quebrado não pode reverter o que já foi gravado.

        Os três passos são defensivos DE PROPÓSITO: quando eles rodam, a fila
        nova já está no disco. Deixar a exceção subir transformaria "a lâmpada
        não acendeu" em "o comando falhou", que é trocar um defeito por um
        pior.
        """
        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B])
        server, daemon, _coop, diario = _servidor(config_isolado, ds)

        class _CoopQuebrado:
            def sync(self, *, force: bool = False) -> None:
                raise RuntimeError("uhid morreu no meio")

        daemon._coop_manager = _CoopQuebrado()

        resultado = await server._handle_identity_number_set(
            {"uniq": UNIQ_B, "number": 1}
        )

        assert resultado["ok"] is True
        assert ds.slot_for(UNIQ_B, assign=False) == 1
        assert ds.slot_for(UNIQ_A, assign=False) == 2
        # E os passos SEGUINTES continuam rodando — a lâmpada do co-op falhou,
        # o resto da repintura não tem culpa.
        assert diario == ["reassert", "external_tick"]

    @pytest.mark.asyncio
    async def test_daemon_ausente_nao_quebra_o_handler(
        self, config_isolado: Path
    ) -> None:
        """Sem daemon não há co-op a sincronizar, e isso não é erro."""
        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B])
        fc = FakeController(transport="usb")
        fc.connect()
        store = StateStore()
        server = IpcServer(
            controller=fc,
            store=store,
            profile_manager=ProfileManager(controller=fc, store=store),
            socket_path=config_isolado / "sem-daemon.sock",
            daemon=None,
        )
        # Sem daemon o handler não tem registro: o que se afere aqui é que ele
        # RESPONDE em vez de levantar.
        resultado = await server._handle_identity_number_set(
            {"uniq": UNIQ_B, "number": 1}
        )

        assert isinstance(resultado, dict)
        assert "ok" in resultado
