"""JOGO-01 — um controle físico produz exatamente UM dispositivo de jogo.

Medido ao vivo em 25/07 com o Mullet Mad Jack (`steam_app_2111190`, o único
appid da allowlist do Steam Input desta máquina) e UM DualSense no cabo:

    /dev/input/js0  ->  Hefesto Virtual DualSense P1   (o nosso gamepad virtual)
    /dev/input/js2  ->  DualSense Wireless Controller  (o controle físico dela)
    /dev/input/js4  ->  Microsoft X-Box 360 pad 0      (Steam Input)
    /dev/input/js5  ->  Microsoft X-Box 360 pad 1      (Steam Input)

O jogo dava jogador 1 ao primeiro que enumerou e jogador 2 ao seguinte, e o
relato dela descreve isso por fora: "ele muda a cor e vai pro player 2 e não
funciona". A causa não era a allowlist estar errada — era ela estar pela
metade: o ramo do `launch_env` omitia `SDL_GAMECONTROLLER_IGNORE_DEVICES` e
`PROTON_DISABLE_HIDRAW` (rótulo literal no código: "allowlist Steam Input (sem
dedup)") e o gamepad virtual CONTINUAVA DE PÉ. Cada metade estava certa
isoladamente; juntas produziam o duplicado.

Estas travas cobrem o invariante que passou a valer: a allowlist muda QUAL
dispositivo o jogo vê, nunca QUANTOS. E cobrem também o beco sem saída que a
cura poderia criar — o tick que traz o vpad de volta é o mesmo que a suspensão
apaga (`lifecycle._poll_loop` só despacha o gamepad com `_gamepad_device is not
None`), então sem a task-vigia o vpad não voltaria nem depois de fechar o jogo.

NOTA DATADA — 09/08/2026 (ESCONDER-EM-VEZ-DE-SAIR-01, decisão dela)
===================================================================
**O invariante ficou; o dispositivo escolhido virou o outro.** A JOGO-01 leu
certo o defeito (dois dispositivos onde há um controle) e escolheu curá-lo
retirando o VIRTUAL. O preço nunca foi declarado, e foi MEDIDO na máquina dela
em 08/08: **o jogador 2 é um gamepad virtual** — derrubar os virtuais para curar
o dobrado do jogador 1 derruba o jogador 2 junto
(`coop_derrubado_pela_excecao_steam_input`, vinte ocorrências num dia).

A decisão dela fecha a conta pelo outro lado: esconde-se o FÍSICO, e o Hefesto
fica. O que isso muda neste arquivo, teste a teste:

- **a suspensão continua existindo e continua sendo testada aqui**, porque não
  se apaga decisão medida e porque ela ainda tem uma entrada viva: um daemon que
  subiu ANTES desta cura pode estar com uma suspensão de pé agora, e as saídas
  são o caminho de volta dele. O que mudou é **quem a chama** — a borda da marca
  não chama mais, então os testes que passavam por `sync_steam_input_exception`
  passaram a chamar `suspend_vpads_for_steam_input` direto. Sem isso eles
  virariam tautologia: verdes porque a borda não faz mais nada;
- **os dois gates que existiam para PROTEGER a suspensão morreram** (o apply
  automático recusado e a rede de segurança do vpad recusada). Estão invertidos
  em `TestQuemTentaLevantarOVpadDeVolta`, com o motivo de cada um;
- **a env própria do appid marcado morreu inteira** — ver `TestEnvDaAllowlist`.

A borda de hoje está em `test_esconder_em_vez_de_sair_01.py`; o desenho, em
`docs/process/sprints/2026-08-09-ESCONDER-EM-VEZ-DE-SAIR-01-o-duplicado-cura-pelo-outro-lado.md`.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import hefesto_dualsense4unix.daemon.subsystems.gamepad as gp
from hefesto_dualsense4unix.daemon import launch_env as le

MMJ = 2111190
_IGNORE = "SDL_GAMECONTROLLER_IGNORE_DEVICES"


class _VpadFalso:
    """O mínimo que `start/stop_gamepad_emulation` toca num vpad."""

    def __init__(self, flavor: str = "dualsense", backend: str = "uhid") -> None:
        self.flavor = flavor
        self.backend = backend
        self._started = True
        self.parado = False

    def stop(self) -> None:
        self.parado = True
        self._started = False


class _CoopFalso:
    def __init__(self, jogadores: int = 0) -> None:
        self._players: dict[str, Any] = {
            f"AA:BB:CC:00:00:0{i}": SimpleNamespace(
                vpad=_VpadFalso(), player_index=i + 2
            )
            for i in range(jogadores)
        }
        self.desligado = 0
        self.syncs: list[bool] = []

    def disable(self) -> None:
        self.desligado += 1
        self._players.clear()

    def sync(self, *, force: bool = False) -> None:
        self.syncs.append(force)


class _StoreFalso:
    def __init__(self) -> None:
        self.contadores: list[str] = []
        self.window_detect_current_class: str | None = None

    def bump(self, chave: str) -> None:
        self.contadores.append(chave)


class _DaemonFalso:
    """Daemon dublado que observa grab, broker, co-op e vpad."""

    def __init__(self, *, jogadores: int = 0, nativo: bool = False) -> None:
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True,
            gamepad_flavor="dualsense",
            rumble_active=None,
        )
        self._gamepad_device: Any = _VpadFalso()
        self._coop_manager = _CoopFalso(jogadores)
        self._motion_reader: Any = None
        self._mouse_device: Any = None
        self._tasks: list[Any] = []
        self._nativo = nativo
        self.parando = False
        self.grabs: list[bool] = []
        self.restores = 0
        self.hides: list[str] = []
        self.store = _StoreFalso()
        pai = self

        class _Evdev:
            grab_state = None

            def set_grab(self, grab: bool) -> bool:
                pai.grabs.append(grab)
                return True

        self.controller = SimpleNamespace(
            _evdev=_Evdev(),
            hidraw_path=lambda *a: "/dev/hidraw0",
            set_rumble=lambda **k: None,
            primary_uniq="AA:BB:CC:00:00:FF",
        )

    def is_native_mode(self) -> bool:
        return self._nativo

    def _is_stopping(self) -> bool:
        return self.parando


@pytest.fixture()
def _broker_falso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cliente do broker dublado — nenhum socket real no teste."""
    import hefesto_dualsense4unix.integrations.hidraw_broker_client as bc

    def _client_for(daemon: Any) -> Any:
        class _C:
            def hide(self, node: str) -> None:
                daemon.hides.append(node)

            def restore_all(self) -> None:
                daemon.restores += 1

        return _C()

    monkeypatch.setattr(bc, "broker_client_for", _client_for)
    monkeypatch.setattr(bc, "broker_call_nonblocking", lambda daemon, fn: fn())


@pytest.fixture()
def _sem_disco(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Isola o ciclo do vpad de disco, kernel e threads.

    Devolve a lista de chamadas a `save_gamepad_emulation` — a PREFERÊNCIA dela
    em disco é a coisa que a suspensão não pode encostar, e a única forma de
    provar isso é observar quem escreve.
    """
    import hefesto_dualsense4unix.integrations.virtual_pad as vp
    import hefesto_dualsense4unix.utils.session as session

    salvos: list[Any] = []
    monkeypatch.setattr(gp, "_materialize_launch_env", lambda daemon: None)
    monkeypatch.setattr(gp, "start_motion_reader", lambda daemon, device: None)
    monkeypatch.setattr(
        vp, "make_virtual_pad", lambda key, **kwargs: _VpadFalso(flavor=key)
    )
    monkeypatch.setattr(
        session,
        "save_gamepad_emulation",
        lambda *a, **k: salvos.append((a, k)),
    )
    return salvos


async def _encerrar_vigia(daemon: Any) -> Any:
    """Cancela a task-vigia (se houver) e devolve a task para inspeção."""
    vigia = getattr(daemon, "_steam_input_vigia", None)
    if vigia is not None:
        vigia.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await vigia
    return vigia


class TestSuspensaoDoVpad:
    """NOTA DATADA — 09/08/2026: a marca não chama mais a suspensão.

    Estes quatro testes entravam por `sync_steam_input_exception`, porque era a
    borda da marca que suspendia. Não é mais (ESCONDER-EM-VEZ-DE-SAIR-01), e o
    caminho de hoje está travado em `test_esconder_em_vez_de_sair_01.py`. Eles
    passaram a chamar `suspend_vpads_for_steam_input` DIRETO — que é a função
    viva, ainda alcançável por um daemon que subiu antes desta cura — em vez de
    virarem verdes de graça: por aquela porta, hoje, não acontece nada, e um
    teste que afirma "não aconteceu nada" onde nada podia acontecer não prova
    coisa nenhuma.
    """

    async def test_a_suspensao_derruba_o_vpad_do_p1_e_o_coop(
        self,
        monkeypatch: pytest.MonkeyPatch,
        _broker_falso: None,
        _sem_disco: list[Any],
    ) -> None:
        """O que a suspensão faz — e o PREÇO dela, na mesma asserção.

        A linha do co-op é a que ficou famosa em 08/08: derrubar os secundários
        é derrubar o jogador 2. Ela continua aqui porque é o fato medido; o que
        mudou é que ninguém paga esse preço pela marca do Steam Input.
        """
        daemon = _DaemonFalso(jogadores=3)
        vpad = daemon._gamepad_device

        assert gp.suspend_vpads_for_steam_input(daemon, appid=MMJ) is True
        vigia = await _encerrar_vigia(daemon)

        assert daemon._gamepad_device is None
        assert vpad.parado is True
        assert daemon._coop_manager.desligado == 1, "P2+ caem junto — é o preço"
        assert gp.steam_input_vpad_suspenso(daemon) is True
        assert vigia is not None, "sem vigia o vpad nunca voltaria"
        assert vigia in daemon._tasks

    async def test_a_preferencia_em_disco_nao_e_tocada(
        self,
        _broker_falso: None,
        _sem_disco: list[Any],
    ) -> None:
        """R-07/HARM-06: só gesto manual escreve a preferência. A suspensão é
        decisão NOSSA e some com o jogo — em disco a emulação segue ligada, e é
        isso que devolve o vpad se o daemon morrer sujo no meio da partida."""
        daemon = _DaemonFalso()

        gp.suspend_vpads_for_steam_input(daemon, appid=MMJ)
        await _encerrar_vigia(daemon)

        assert _sem_disco == []
        assert daemon.config.gamepad_emulation_enabled is False, (
            "o False em MEMÓRIA é o que cala os revivedores automáticos"
        )

    def test_sem_event_loop_o_vpad_fica_de_pe_e_a_decisao_e_dita(
        self,
        _broker_falso: None,
        _sem_disco: list[Any],
    ) -> None:
        """Fail-safe declarado: sem quem devolva o vpad, não se retira o vpad.

        Teste SÍNCRONO de propósito — é justamente o caso "não há event loop
        rodando". Degradar para o duplicado é ruim; deixá-la sem gamepad virtual
        até reiniciar o daemon é pior, e ela não teria como desfazer.
        """
        daemon = _DaemonFalso()

        assert gp.suspend_vpads_for_steam_input(daemon, appid=MMJ) is False

        assert daemon._gamepad_device is not None
        assert gp.steam_input_vpad_suspenso(daemon) is False
        assert getattr(daemon, "_steam_input_vigia", None) is None

    async def test_sem_vpad_nem_jogadores_nao_arma_nada(
        self,
        _broker_falso: None,
        _sem_disco: list[Any],
    ) -> None:
        """Emulação já desligada: não há duplicado a remover (nem vigia a criar)."""
        daemon = _DaemonFalso()
        daemon._gamepad_device = None
        daemon.config.gamepad_emulation_enabled = False

        assert gp.suspend_vpads_for_steam_input(daemon, appid=MMJ) is False

        assert gp.steam_input_vpad_suspenso(daemon) is False
        assert getattr(daemon, "_steam_input_vigia", None) is None


class TestQuemTentaLevantarOVpadDeVolta:
    """NOTA DATADA — 09/08/2026: os dois gates que protegiam a suspensão caíram.

    Eles recusavam quem pudesse levantar o vpad durante a marca — o apply
    automático do perfil/autoswitch e a rede de segurança do VPAD-09 —, e a
    razão era uma só, escrita nos dois: *"nos appids da allowlist o dispositivo
    do jogo é o físico"*. **Essa premissa se inverteu.** No jogo marcado o
    dispositivo do jogo passou a ser o vpad, e recusá-lo ali é recusar
    justamente o que a marca promete entregar — pior: com o físico escondido,
    um vpad que morre e não volta é ZERO controles na mão dela.

    Os dois testes ficam, com a resposta de hoje. O do gesto manual não mudou de
    veredito: continua verde, agora pelo caminho que serve à suspensão HERDADA.
    """

    def test_apply_automatico_volta_a_ser_aceito_no_jogo_marcado(
        self, _broker_falso: None, _sem_disco: list[Any]
    ) -> None:
        """A MORDIDA: devolva o `if origin != "manual": return False` ao gate de
        `start_gamepad_emulation` e o autoswitch volta a ser recusado — no jogo
        marcado, isso é recusar o único dispositivo que sobrou.
        """
        daemon = _DaemonFalso()
        daemon._gamepad_device = None
        daemon._steam_input_excecao = True
        daemon._steam_input_vpad_suspenso = True

        assert gp.start_gamepad_emulation(daemon, "dualsense", origin="profile") is True

        assert daemon._gamepad_device is not None
        assert gp.steam_input_vpad_suspenso(daemon) is False, (
            "a suspensão herdada tem de morrer no apply, e não esperar um "
            "clique dela que pode nunca vir"
        )

    def test_gesto_manual_vence_e_encerra_a_suspensao(
        self, _broker_falso: None, _sem_disco: list[Any]
    ) -> None:
        """A última palavra é dela. Religar na mão devolve o vpad e a suspensão
        morre ali — a saída da exceção não pode tentar devolver um vpad que já
        está de pé."""
        daemon = _DaemonFalso()
        daemon._gamepad_device = None
        daemon._steam_input_excecao = True
        daemon._steam_input_vpad_suspenso = True

        assert gp.start_gamepad_emulation(daemon, "dualsense", origin="manual") is True

        assert daemon._gamepad_device is not None
        assert gp.steam_input_vpad_suspenso(daemon) is False

    def test_revive_pos_falha_total_vale_dentro_do_jogo_marcado(
        self, _broker_falso: None, _sem_disco: list[Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """VPAD-09 dispara em borda de CONEXÃO — a mais frequente desta máquina
        (BT reconectando no meio da partida). Com o físico escondido, é aqui que
        ela deixa de ficar sem controle nenhum.

        A MORDIDA: devolva o `if steam_input_excecao_ativa(daemon): return
        False` a `upgrade_primary_vpad_to_uhid`.
        """
        monkeypatch.setattr(gp, "controller_allows_uhid", lambda d: True)
        daemon = _DaemonFalso()
        daemon._gamepad_device = None
        daemon._steam_input_excecao = True

        assert gp.upgrade_primary_vpad_to_uhid(daemon) is True
        assert daemon._gamepad_device is not None


class TestDevolucaoDoVpad:
    @staticmethod
    def _suspenso(flavor: str = "dualsense") -> _DaemonFalso:
        daemon = _DaemonFalso()
        daemon._gamepad_device = None
        daemon.config.gamepad_emulation_enabled = False
        daemon._steam_input_excecao = True
        daemon._steam_input_vpad_suspenso = True
        daemon._steam_input_flavor_suspenso = flavor
        return daemon

    def test_sair_da_excecao_devolve_o_vpad_com_a_mascara_de_antes(
        self,
        monkeypatch: pytest.MonkeyPatch,
        _broker_falso: None,
        _sem_disco: list[Any],
    ) -> None:
        daemon = self._suspenso(flavor="xbox")
        monkeypatch.setattr(le, "steam_input_exception_appid", lambda d, **k: None)

        assert gp.sync_steam_input_exception(daemon) is False

        assert daemon._gamepad_device is not None
        assert daemon._gamepad_device.flavor == "xbox"
        assert daemon.config.gamepad_emulation_enabled is True
        assert gp.steam_input_vpad_suspenso(daemon) is False
        assert daemon._coop_manager.syncs == [True], "P2+ voltam junto com o P1"
        assert _sem_disco == [], "a volta também não escreve preferência nenhuma"
        assert daemon.grabs == [True] and daemon.hides == ["/dev/hidraw0"]

    def test_sem_mascara_gravada_a_devolucao_nao_inventa_um_vpad(
        self, _broker_falso: None, _sem_disco: list[Any]
    ) -> None:
        """Máscara `None` na suspensão = não havia vpad do P1 para derrubar.
        Criar um agora seria dar a ela um device que ela não tinha."""
        daemon = self._suspenso()
        daemon._steam_input_flavor_suspenso = None

        assert gp.resume_vpads_after_steam_input(daemon) is True

        assert daemon._gamepad_device is None
        assert gp.steam_input_vpad_suspenso(daemon) is False

    def test_modo_nativo_no_meio_da_sessao_vence_a_devolucao(
        self,
        monkeypatch: pytest.MonkeyPatch,
        _broker_falso: None,
        _sem_disco: list[Any],
    ) -> None:
        """No Modo Nativo o físico é o dispositivo por escolha dela: ressuscitar
        o vpad recriaria o duplicado pelo outro lado."""
        daemon = self._suspenso()
        daemon._nativo = True
        monkeypatch.setattr(le, "steam_input_exception_appid", lambda d, **k: None)

        assert gp.sync_steam_input_exception(daemon) is False

        assert daemon._gamepad_device is None
        assert gp.steam_input_vpad_suspenso(daemon) is False, (
            "estado pendurado voltaria a mentir na próxima borda"
        )


class TestVigiaDaExcecao:
    async def test_vigia_reconcilia_ate_a_excecao_cair_e_morre(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """É ela que substitui o tick do `dispatch_gamepad` enquanto não há vpad."""
        daemon = _DaemonFalso()
        daemon._steam_input_excecao = True
        chamadas: list[int] = []

        def _reconciliar(d: Any) -> None:
            chamadas.append(1)
            if len(chamadas) == 2:
                d._steam_input_excecao = False

        monkeypatch.setattr(gp, "STEAM_INPUT_VIGIA_INTERVAL_SEC", 0.001)
        monkeypatch.setattr(gp, "_reconciliar_launch", _reconciliar)

        await gp._vigia_da_excecao_steam_input(daemon)

        assert chamadas == [1, 1]
        assert daemon._steam_input_vigia is None, "a vigia não pode vazar"

    async def test_vigia_nao_reconcilia_com_o_daemon_parando(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        daemon = _DaemonFalso()
        daemon._steam_input_excecao = True
        daemon.parando = True
        chamadas: list[int] = []
        monkeypatch.setattr(gp, "STEAM_INPUT_VIGIA_INTERVAL_SEC", 0.001)
        monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: chamadas.append(1))

        await gp._vigia_da_excecao_steam_input(daemon)

        assert chamadas == []


class TestEnvDaAllowlist:
    def test_o_appid_marcado_deixou_de_ter_env_propria(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """NOTA DATADA — 09/08/2026: o rótulo virou obituário.

        Este teste afirmava que o `.env` do appid marcado declarava, em letras,
        *"allowlist Steam Input (físico é o único dispositivo)"*, e que o dedup
        NÃO podia estar lá — porque esconder o físico, com o vpad suspenso,
        seria zero controles. A regra que o rótulo afirma deixou de valer: no
        jogo marcado o único dispositivo passou a ser o do Hefesto.

        A MORDIDA: devolva o laço da allowlist a `materialize_launch_env`. A env
        renasce mandando o jogo olhar para o físico — e o daemon, do outro lado,
        acabou de escondê-lo. É o "Jogador 3" fantasma, inteiro.
        """
        monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
        monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {MMJ})
        daemon = _DaemonFalso()

        le.materialize_launch_env(daemon)

        assert not (tmp_path / f"steam_app_{MMJ}.env").exists()
        # O jogo marcado passa a ler o mesmo `default.env` de qualquer outro, e
        # com o dedup — o dispositivo dele é o vpad.
        texto = (tmp_path / "default.env").read_text(encoding="utf-8")
        assert _IGNORE in texto
        assert le.ESTADO_ALLOWLIST_STEAM_INPUT not in texto, (
            "o rótulo do desvio antigo voltou a ser escrito em algum arquivo"
        )
