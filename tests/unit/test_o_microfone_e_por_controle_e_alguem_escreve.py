"""QUATRO-MICROFONES-01 — a ponte de microfone tem escritor, e é POR CONTROLE.

O DEFEITO QUE ESTE ARQUIVO TRAVA
---------------------------------

Até 22/08/2026 o `DaemonConfig.bt_mic_enabled` era **lido por três lugares e
escrito por nenhum**: `lifecycle.py` declarava, `bt_mic.py` lia, `ipc_handlers`
relatava, e a única forma de subir a ponte era exportar
`HEFESTO_DUALSENSE4UNIX_BT_MIC=1` no ambiente do daemon, à mão. É a família
A-CASA-SABE-E-O-PRODUTO-NAO-FAZ, e é exatamente o que o
`portao_a_casa_sabe_e_o_produto_nao_faz` mede.

A decisão dela, textual em 22/08: *"por controle"*. Um `bool` não sustenta
quatro independentes — ele só sabe dizer "todos" ou "nenhum" —, e por isso o
gate virou um CONJUNTO de `uniq`, com a ausência valendo desligado.

O QUE CADA CASO GUARDA, E POR QUE ELE PRECISA EXISTIR
------------------------------------------------------

A cadeia inteira tem cinco elos, e acertar quatro deles parece certo e não faz
nada — foi assim que o campo ficou órfão por um mês:

1. o `maquina.json` guarda `microfone: true` por controle (`uniqs_declarados`);
2. o `run()` fia a FONTE no `DaemonConfig` (`bt_mic_uniqs`);
3. o subsystem sobe quando ao menos um pediu (`is_enabled`);
4. o laço entrega ao gerenciador **só os nós que ela ligou** (`alvos`) — é aqui
   que o "por controle" acontece de verdade;
5. o `state_full` relata de quais controles a ponte SUBIU (`bt_mic.uniqs`), que
   é o que o medidor de rádio consome.

AS MORDIDAS, EXERCIDAS EM 23/08/2026 — a saída real está no relatório da leva
------------------------------------------------------------------------------

1. **`if self.config.bt_mic_uniqs is None:` → nunca fiar a fonte** em
   `lifecycle.run()`. Reprovou `test_o_run_fia_a_fonte_no_maquina_json`: o campo
   volta a `None` e o defeito-mãe está de volta, com todo o resto verde.
2. **`alvos()` devolvendo `list(nos)` sem filtrar.** Reprovou
   `test_so_o_controle_que_ela_ligou_ganha_ponte` com os quatro `uniq` na lista
   — ligar UM microfone ligaria os quatro, que é o oposto da decisão dela.
3. **`"uniqs": com_ponte` fora do bloco do `state_full`.** Reprovou
   `test_o_state_full_diz_de_quais_controles_a_ponte_subiu`, e é a régua cega
   que deixava a barra de rádio pintar áudio zero com a ponte de pé.
4. **`reconciliar_bt_mic` sem a chamada no `machine.declare`.** Reprovou
   `test_o_aplicar_reconcilia_a_ponte_sem_reiniciar_o_daemon` — a escolha dela
   gravada no disco e nenhum efeito na mesa até o próximo início do Hefesto.
"""
from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.bt_mic import (
    BtMicSubsystem,
    RegistroDePedidosDeCanal,
    uniqs_declarados,
    uniqs_pedidos,
)
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils.maquina import ControleDeclarado, MaquinaConfig

#: Os quatro da mesa dela, na faixa sintética que o portão de anonimato exige em
#: `tests/` — a máscara da casa não basta aqui (`test_anonimato_de_fixtures`).
UM = "aabbcc000001"
DOIS = "aabbcc000002"
TRES = "aabbcc000003"
QUATRO = "aabbcc000004"


class _No:
    """Um `NoDualSenseBT` o bastante para o filtro — só o que `alvos` lê."""

    def __init__(self, uniq: str, caminho: str = "") -> None:
        self.uniq = uniq
        self.caminho = caminho or f"/dev/{uniq}"


class _Ponte:
    def __init__(self, no: _No) -> None:
        self.no = no


class _Gerenciador:
    """Gerenciador de pontes falso: guarda a ÚLTIMA lista que recebeu."""

    def __init__(self) -> None:
        self.chamadas: list[list[Any]] = []
        self.pontes: dict[str, Any] = {}
        self.parado = False

    def reconciliar(self, nos: list[Any] | None = None) -> None:
        self.chamadas.append(list(nos or []))
        self.pontes = {no.caminho: _Ponte(no) for no in (nos or [])}

    def dormir(self, _s: float) -> bool:
        return True

    def parar(self) -> None:
        self.parado = True


def _state() -> ControllerState:
    return ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
        transport="usb", buttons_pressed=frozenset(),
    )


def _config(**over: object) -> DaemonConfig:
    base: dict[str, object] = dict(
        poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
        autoswitch_enabled=False, mouse_emulation_enabled=False,
        keyboard_emulation_enabled=False, ps_button_action="none",
        mic_button_toggles_system=False,
    )
    base.update(over)
    return DaemonConfig(**base)  # type: ignore[arg-type]


def _maquina(**controles: ControleDeclarado) -> MaquinaConfig:
    return MaquinaConfig(controles=dict(controles))


# ===========================================================================
# 1. A declaração da mesa — e só `True` conta
# ===========================================================================


class TestADeclaracaoDaMesa:
    def test_so_true_liga_a_ponte(self) -> None:
        """`False` e ausência deixam a ponte no chão do mesmo jeito.

        É por isso que DESLIGAR grava `None` e não `False`: um `false` em disco
        seria um valor de catálogo para o silêncio, e é por essa porta que o
        default entra disfarçado de escolha dela.
        """
        maquina = _maquina(
            **{
                UM: ControleDeclarado(microfone=True),
                DOIS: ControleDeclarado(microfone=False),
                TRES: ControleDeclarado(microfone=None),
                QUATRO: ControleDeclarado(cor="Cosmic Red"),
            }
        )
        assert uniqs_declarados(maquina) == frozenset({UM})

    def test_maquina_vazia_nao_liga_ninguem(self) -> None:
        """Máquina nova nasce sem microfone nenhum — a regra de privacidade."""
        assert uniqs_declarados(MaquinaConfig()) == frozenset()
        assert uniqs_declarados(None) == frozenset()

    def test_a_fonte_que_explode_vale_como_ninguem_pediu(self) -> None:
        """Erro de leitura NUNCA sobe um microfone. O lado seguro é o silêncio."""

        def _explode() -> frozenset[str]:
            raise RuntimeError("disco sumiu")

        assert uniqs_pedidos(_config(bt_mic_uniqs=_explode)) == frozenset()

    def test_um_magicmock_no_lugar_da_fonte_nao_liga_microfone(self) -> None:
        """Dublê de teste que responde tudo é o caso mais fácil de vazar.

        `MagicMock()` é chamável e devolve outro `MagicMock` — se `uniqs_pedidos`
        aceitasse qualquer retorno, meia bateria desta casa passaria a subir
        microfone sem pedir.
        """
        assert uniqs_pedidos(MagicMock()) == frozenset()


# ===========================================================================
# 2. O gate — o `bool` não servia, e é por isso que ele saiu
# ===========================================================================


class TestOGate:
    """CONTRATO SUBSTITUÍDO — CANAL-POR-CONTROLE-01, 03/09/2026.

    Estes três mediam `is_enabled` como *"alguém declarou um `uniq`?"*, e era
    essa resposta que trancava o rádio: sem declaração o subsystem não existia,
    então não havia a quem PEDIR canal, e o primeiro toque no botão do
    microfone caía no vazio. Agora `is_enabled` é sempre `True` — o supervisor
    tem de estar de pé para atender o pedido.

    **O que eles mediam continua medido, e no lugar certo:** quem responde
    "ninguém pediu, então nada sobe" é `alvos()`, e é ele que estas linhas
    checam agora. O `is_enabled` verdadeiro sem `alvos()` vazio seria o
    microfone ligando sozinho — é essa a dupla que a privacidade exige.
    """

    def test_conjunto_vazio_nao_sobe_ponte_nenhuma(self) -> None:
        subsystem = BtMicSubsystem(registro=RegistroDePedidosDeCanal())
        config = _config(bt_mic_uniqs=frozenset)
        assert subsystem.is_enabled(config) is True
        subsystem._config = config
        assert subsystem.alvos([_No(UM), _No(DOIS)]) == []

    def test_um_uniq_basta_para_subir_o_subsystem(self) -> None:
        config = _config(bt_mic_uniqs=lambda: frozenset({UM}))
        assert BtMicSubsystem().is_enabled(config) is True

    def test_sem_fonte_nenhuma_nao_sobe_ponte_nenhuma(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`None` é o contrato de "não há fonte", e vale como ninguém pediu."""
        monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", raising=False)
        subsystem = BtMicSubsystem(registro=RegistroDePedidosDeCanal())
        assert subsystem.is_enabled(_config()) is True
        subsystem._config = _config()
        assert subsystem.alvos([_No(UM), _No(DOIS)]) == []


# ===========================================================================
# 3. O CORAÇÃO: ligar um microfone não liga os quatro
# ===========================================================================


class TestPorControle:
    def test_so_o_controle_que_ela_ligou_ganha_ponte(self) -> None:
        """A decisão dela, exercida contra a mesa cheia.

        Quatro DualSense no rádio, UM declarado. O gerenciador tem de receber um
        nó — e o nó certo. Sem o filtro de `alvos`, ele recebe os quatro, e o
        interruptor "por controle" vira uma chave de mesa inteira que mente
        sobre ser por controle.
        """
        subsystem = BtMicSubsystem()
        subsystem._config = _config(bt_mic_uniqs=lambda: frozenset({TRES}))
        nos = [_No(UM), _No(DOIS), _No(TRES), _No(QUATRO)]

        escolhidos = subsystem.alvos(nos)

        assert [no.uniq for no in escolhidos] == [TRES]

    def test_dois_ligados_sobem_dois_e_os_outros_dois_ficam_no_chao(self) -> None:
        """O caso do adaptador de DOIS controles da mesa dela."""
        subsystem = BtMicSubsystem()
        subsystem._config = _config(bt_mic_uniqs=lambda: frozenset({UM, QUATRO}))

        escolhidos = subsystem.alvos([_No(UM), _No(DOIS), _No(TRES), _No(QUATRO)])

        assert sorted(no.uniq for no in escolhidos) == [UM, QUATRO]

    def test_nenhum_ligado_nao_entrega_no_nenhum(self) -> None:
        subsystem = BtMicSubsystem()
        subsystem._config = _config(bt_mic_uniqs=frozenset)
        assert subsystem.alvos([_No(UM), _No(DOIS)]) == []

    def test_o_no_sem_endereco_nunca_entra(self) -> None:
        """Sem `HID_UNIQ` não há como saber de quem é o microfone.

        Subir a ponte no escuro é o oposto do gesto explícito — e um controle
        recém-pareado por BT chega assim de vez em quando
        (`dualsense_bt_audio.NoDualSenseBT.nome_curto` conhece o caso).
        """
        subsystem = BtMicSubsystem()
        subsystem._config = _config(bt_mic_uniqs=lambda: frozenset({UM}))
        assert subsystem.alvos([_No("")]) == []

    def test_o_mac_com_dois_pontos_casa_com_os_doze_hex(self) -> None:
        """O uevent escreve `aa:bb:cc:00:00:01`; o `maquina.json` escreve 12 hex.

        Sem normalizar os dois lados, o conjunto nunca casa e o microfone nunca
        sobe — falha CALADA, que é a pior classe.
        """
        subsystem = BtMicSubsystem()
        subsystem._config = _config(bt_mic_uniqs=lambda: frozenset({UM}))
        assert [no.uniq for no in subsystem.alvos([_No("aa:bb:cc:00:00:01")])] == [
            "aa:bb:cc:00:00:01"
        ]

    def test_a_env_a_mao_vale_para_a_mesa_inteira(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A env sempre significou "a mesa inteira", e continua significando.

        Quem a exporta está pedindo os quatro de propósito. Ela não filtra por
        `uniq` porque não tem como: é uma variável de ambiente, não uma escolha
        por aparelho.
        """
        monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", "1")
        subsystem = BtMicSubsystem()
        subsystem._config = _config(bt_mic_uniqs=frozenset)

        escolhidos = subsystem.alvos([_No(UM), _No(DOIS)])

        assert sorted(no.uniq for no in escolhidos) == [UM, DOIS]


# ===========================================================================
# 4. O relato — o produto responde pelo EFEITO, não pelo pedido
# ===========================================================================


class TestOQueOProdutoRelata:
    def test_a_ponte_relatada_e_a_que_subiu_e_nao_a_que_ela_pediu(self) -> None:
        """Uma ponte pedida que não subiu não ocupa fatia de rádio nenhuma.

        libopus ausente, hidraw recusado: o pedido está no `maquina.json` e o
        rádio está limpo. Pintar áudio na barra nesse caso seria o produto
        respondendo pelo pedido em vez de pelo efeito — o padrão que a queixa do
        Sackboy revelou em 22/08.
        """
        subsystem = BtMicSubsystem()
        subsystem._config = _config(bt_mic_uniqs=lambda: frozenset({UM, DOIS}))
        gerenciador = _Gerenciador()
        # Só o UM subiu de verdade.
        gerenciador.reconciliar([_No(UM)])
        subsystem._gerenciador = gerenciador

        assert uniqs_pedidos(subsystem._config) == frozenset({UM, DOIS})
        assert subsystem.uniqs_com_ponte() == frozenset({UM})

    def test_sem_gerenciador_o_relato_e_vazio_e_nao_levanta(self) -> None:
        assert BtMicSubsystem().uniqs_com_ponte() == frozenset()

    def test_um_gerenciador_que_explode_nao_derruba_o_state_full(self) -> None:
        """O relato é best-effort: o tique de 20 Hz não cai por causa dele."""

        class _Quebrado:
            @property
            def pontes(self) -> dict[str, Any]:
                raise RuntimeError("morreu")

        subsystem = BtMicSubsystem()
        subsystem._gerenciador = _Quebrado()
        assert subsystem.uniqs_com_ponte() == frozenset()


# ===========================================================================
# 5. O elo que faltava: alguém ESCREVE
# ===========================================================================


class TestAlguemEscreve:
    @pytest.mark.asyncio
    async def test_o_run_fia_a_fonte_no_maquina_json(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A mordida principal: sem esta linha o campo volta a ser órfão.

        O `run()` tem de fiar `DaemonConfig.bt_mic_uniqs` a partir do
        `maquina.json`, e a fonte tem de ser CHAMÁVEL — o `machine.declare`
        rebinda `daemon._maquina` no "Aplicar", e uma cópia tirada no boot
        ficaria velha no instante exato em que ela acabou de escolher.
        """
        monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", raising=False)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.session.load_paused_state", lambda: False
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.maquina.carregar_maquina",
            lambda: _maquina(**{DOIS: ControleDeclarado(microfone=True)}),
        )
        gerenciador = _Gerenciador()
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.dualsense_bt_audio."
            "GerenciadorMicBluetooth",
            lambda *a, **k: gerenciador,
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.dualsense_bt_audio."
            "nos_dualsense_bluetooth",
            lambda *a, **k: [_No(UM), _No(DOIS)],
        )
        store = StateStore()
        config = _config()
        assert config.bt_mic_uniqs is None, "o default do campo tem de ser 'sem fonte'"
        daemon = Daemon(
            controller=FakeController(transport="usb", states=[_state()]),
            bus=EventBus(), store=store, config=config,
        )
        run_task = asyncio.create_task(daemon.run())
        for _ in range(500):
            if store.counter("poll.tick") >= 1:
                break
            await asyncio.sleep(0.01)
        daemon.stop()
        await run_task

        assert callable(config.bt_mic_uniqs), (
            "`bt_mic_uniqs` continua `None` depois do boot: o campo está órfão "
            "de novo, e a ponte só sobe por variável de ambiente"
        )
        assert config.bt_mic_uniqs() == frozenset({DOIS})
        # E o "por controle" chegou até o gerenciador: dois nós no rádio, um só
        # declarado, uma ponte.
        assert gerenciador.chamadas, "o laço nunca reconciliou"
        assert [no.uniq for no in gerenciador.chamadas[0]] == [DOIS]

    @pytest.mark.asyncio
    async def test_uma_fonte_ja_montada_nao_e_sobrescrita(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Quem fia a própria fonte manda — e é o que a bateria faz.

        Sobrescrever aqui apagaria a única forma de exercer o gate sem escrever
        um `maquina.json` no disco de quem roda os testes.
        """
        monkeypatch.delenv("HEFESTO_DUALSENSE4UNIX_BT_MIC", raising=False)
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.session.load_paused_state", lambda: False
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.dualsense_bt_audio."
            "GerenciadorMicBluetooth",
            lambda *a, **k: _Gerenciador(),
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.integrations.dualsense_bt_audio."
            "nos_dualsense_bluetooth",
            lambda *a, **k: [],
        )
        store = StateStore()
        config = _config(bt_mic_uniqs=lambda: frozenset({QUATRO}))
        daemon = Daemon(
            controller=FakeController(transport="usb", states=[_state()]),
            bus=EventBus(), store=store, config=config,
        )
        run_task = asyncio.create_task(daemon.run())
        for _ in range(500):
            if store.counter("poll.tick") >= 1:
                break
            await asyncio.sleep(0.01)
        daemon.stop()
        await run_task

        assert config.bt_mic_uniqs is not None
        assert config.bt_mic_uniqs() == frozenset({QUATRO})


# ===========================================================================
# 6. O "Aplicar" vale AGORA — sobe e desce sem reiniciar o daemon
# ===========================================================================


class TestOAplicarValeAgora:
    @pytest.mark.asyncio
    async def test_reconciliar_sobe_uma_vez_e_o_laco_cuida_do_resto(self) -> None:
        """CONTRATO SUBSTITUÍDO — CANAL-POR-CONTROLE-01, 03/09/2026.

        Este método cobrava *"sobe no primeiro, desce no último"*, e o "desce" só
        existia porque `is_enabled` era a declaração. Com o canal subindo por
        PROCURA, o supervisor fica de pé para atender o próximo pedido e quem
        derruba o microfone de quem ela desmarcou é `alvos()`, na varredura
        seguinte — o que DESLIGA o microfone do mesmo jeito, porque
        `PonteMicBluetooth.parar()` sempre escreve o `0x32` de desligar.

        **A garantia não se perdeu, ela mudou de dono**, e o dono novo é medido
        em `TestOPedidoDeCanal.test_desmarcar_no_aplicar_vence_o_pedido`.
        """
        ligados: set[str] = set()
        daemon = Daemon.__new__(Daemon)
        daemon.config = _config(bt_mic_uniqs=lambda: frozenset(ligados))
        daemon._bt_mic_subsystem = None
        subidas: list[str] = []

        async def _sobe() -> None:
            subidas.append("start")
            daemon._bt_mic_subsystem = object()

        async def _desce() -> None:
            subidas.append("stop")
            daemon._bt_mic_subsystem = None

        daemon._start_bt_mic = _sobe  # type: ignore[method-assign]
        daemon._stop_bt_mic = _desce  # type: ignore[method-assign]

        # O supervisor sobe já — é o que faz o primeiro toque no botão ter a
        # quem pedir canal.
        await daemon.reconciliar_bt_mic()
        assert subidas == ["start"]

        # Ela liga o primeiro e o segundo: já está de pé, e o laço cuida.
        ligados.add(UM)
        await daemon.reconciliar_bt_mic()
        ligados.add(DOIS)
        await daemon.reconciliar_bt_mic()
        assert subidas == ["start"]

        # Ela desliga os dois: o supervisor FICA, e quem derruba as pontes é o
        # `alvos()` da varredura seguinte.
        ligados.clear()
        await daemon.reconciliar_bt_mic()
        assert subidas == ["start"]

    @pytest.mark.asyncio
    async def test_uma_ponte_que_falha_nao_vira_nao_consegui_gravar(self) -> None:
        """O "Aplicar" já gravou. Falha de ponte não pode virar erro de gravação."""
        daemon = Daemon.__new__(Daemon)
        daemon.config = _config(bt_mic_uniqs=lambda: frozenset({UM}))
        daemon._bt_mic_subsystem = None

        async def _explode() -> None:
            raise RuntimeError("libopus sumiu")

        daemon._start_bt_mic = _explode  # type: ignore[method-assign]
        await daemon.reconciliar_bt_mic()  # não levanta

    @pytest.mark.asyncio
    async def test_o_aplicar_reconcilia_a_ponte_sem_reiniciar_o_daemon(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """O `machine.declare` CHAMA a reconciliação depois de gravar.

        Sem esta chamada a escolha dela só valeria no próximo início do Hefesto —
        a forma mais cara do defeito-mãe desta casa: gravado no disco, nenhum
        efeito na mesa.
        """
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        chamou: list[str] = []

        class _DaemonFalso:
            _maquina = MaquinaConfig()

            async def reconciliar_bt_mic(self) -> None:
                chamou.append("reconciliou")

        class _Servidor(IpcHandlersMixin):
            def __init__(self) -> None:
                self.daemon = _DaemonFalso()

        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.maquina.gravar_maquina",
            lambda _d: True,
        )
        monkeypatch.setattr(
            "hefesto_dualsense4unix.utils.maquina.carregar_maquina",
            lambda: _maquina(**{UM: ControleDeclarado(microfone=True)}),
        )

        resposta = await _Servidor()._handle_machine_declare(
            {"maquina": {"controles": {UM: {"microfone": True}}}}
        )

        assert resposta == {"ok": True}
        assert chamou == ["reconciliou"], (
            "o `machine.declare` gravou e não reconciliou a ponte: o "
            "interruptor da aba só valeria no próximo início do Hefesto"
        )
