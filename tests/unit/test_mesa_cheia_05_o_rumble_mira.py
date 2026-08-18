"""MESA-CHEIA-05 (E0) — o rumble FIXADO não migra de dono.

O defeito, medido em 13/08/2026 e nunca escrito antes: ela fixa 160/220 no
Controle 2, troca o seletor para o Controle 3 por outro motivo qualquer, e
200 ms depois o 3 leva o valor do 2. A cadeia é curta e temporal:

    rumble.set        -> config.rumble_active = (160, 220)   (par GLOBAL)
    controller.target -> _output_target_key = <key do 3>     (ponteiro MUTÁVEL)
    reassert_rumble   -> set_rumble -> _for_each_com_key honra o alvo DE AGORA

A cura é o par carregar o DONO em que foi fixado (`config.rumble_active_uniq`)
e o reassert escrever por MAC (`set_rumble_for`, a rota que já existia e só o
co-op e o force-feedback usavam).

**Por que o backend é REAL aqui.** Um dublê de backend só teria o alvo que
quem o escreveu já sabia existir; o defeito mora justamente na resolução de
alvo do `PyDualSenseController`. O que é dublê são os handles (motores viram
lista) — como em `test_backend_output_target.py`.

**A mesa é a de 14/08**: os quatro MACs, cores e transportes saem do payload
real versionado em `tests/fixtures/state_full_quatro_controles.json`, não de
uma mesa inventada.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.evdev_reader import EvdevReader
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import APLICADO, Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.daemon.subsystems.rumble import (
    escrever_rumble_no_dono,
    reassert_rumble,
    silenciar_dono_abandonado,
)
from hefesto_dualsense4unix.profiles.manager import ProfileManager

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "state_full_quatro_controles.json"
)


def _uniqs_da_mesa_cheia() -> list[str]:
    """Os quatro MACs medidos em 14/08 — dois USB, dois BT."""
    dados = json.loads(FIXTURE.read_text(encoding="utf-8"))
    uniqs = [c["uniq"] for c in dados["controllers"]]
    assert len(uniqs) == 4, "a mesa cheia tem quatro; o fixture mudou"
    return uniqs


def _key_de(uniq: str) -> str:
    """A key do handle no formato MAC que o backend normaliza de volta."""
    return ":".join(uniq[i : i + 2] for i in range(0, 12, 2)).upper()


class _FakeHandle:
    """Handle mínimo: os motores viram lista, e é só isso que se mede aqui."""

    def __init__(self) -> None:
        self.connected = True
        self.conType = type("CT", (), {"name": "USB"})()
        self.motors: list[tuple[str, int]] = []

    def setLeftMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        self.motors.append(("left", intensity))

    def setRightMotor(self, intensity: int) -> None:  # noqa: N802 — API pydualsense
        self.motors.append(("right", intensity))


def _null_evdev() -> EvdevReader:
    reader = EvdevReader(device_path=None)
    reader._device_path = None
    return reader


class _Mesa:
    """A mesa cheia montada: backend real, quatro handles, um IpcServer."""

    def __init__(self, tmp_path: Path) -> None:
        self.uniqs = _uniqs_da_mesa_cheia()
        self.backend = PyDualSenseController(evdev_reader=_null_evdev())
        self.handles = {u: _FakeHandle() for u in self.uniqs}
        self.backend._handles = {  # type: ignore[assignment]
            _key_de(u): h for u, h in self.handles.items()
        }
        self.backend._primary_key = _key_de(self.uniqs[0])

        self.store = StateStore()
        self.store.update_controller_state(
            ControllerState(
                battery_pct=100, l2_raw=0, r2_raw=0, connected=True, transport="usb"
            )
        )
        self.config = DaemonConfig()
        # "balanceado" = 1,0: a conta da política não entra no caminho da
        # medição, e o que sai do motor é o que ela fixou.
        self.config.rumble_policy = "balanceado"

        self.daemon = MagicMock()
        self.daemon.config = self.config
        self.daemon.store = self.store
        self.daemon.controller = self.backend
        self.daemon._rumble_engine = None
        self.daemon._last_auto_mult = 1.0
        self.daemon._last_auto_change_at = 0.0

        self.server = IpcServer(
            controller=self.backend,
            store=self.store,
            profile_manager=ProfileManager(controller=self.backend, store=self.store),
            socket_path=tmp_path / "mesa_cheia_05.sock",
            daemon=self.daemon,
        )

    def indice_de(self, uniq: str) -> int:
        return self.uniqs.index(uniq)

    def motores_de(self, uniq: str) -> list[tuple[str, int]]:
        return self.handles[uniq].motors

    def limpar_motores(self) -> None:
        for handle in self.handles.values():
            handle.motors.clear()

    def ticks(self, quantos: int = 3) -> None:
        """Os ciclos do poll loop — o defeito é temporal, não da chamada."""
        for i in range(quantos):
            reassert_rumble(self.daemon, float(i))

    def daemon_de_verdade(self) -> Daemon:
        """Um `Daemon` REAL sobre a MESMA mesa (backend, store e config).

        Dois dos sítios de cura moram em `lifecycle` — a troca de POLÍTICA e as
        duas solturas do par —, e o `MagicMock` que serve ao `reassert_rumble`
        não executa nenhum deles: com ele, arrancar a cura de lá não reprovava
        nada. O backend é o mesmo objeto, então o que este daemon escrever
        aparece nos mesmos quatro handles.
        """
        return Daemon(controller=self.backend, store=self.store, config=self.config)


@pytest.fixture
def mesa(tmp_path: Path) -> _Mesa:
    return _Mesa(tmp_path)


class TestOParFixadoNaoMigra:
    """MORDIDA 0 — a que não espera decisão nenhuma (a D-4 é outra leva)."""

    @pytest.mark.asyncio
    async def test_trocar_o_seletor_nao_leva_o_valor_do_dois_para_o_tres(
        self, mesa: _Mesa
    ) -> None:
        dois, tres = mesa.uniqs[1], mesa.uniqs[2]

        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})
        assert mesa.motores_de(dois), "o gesto tem de vibrar o alvo escolhido"

        # O gesto que NÃO fala de vibração: ela troca de controle no cabeçalho.
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(tres)})
        mesa.limpar_motores()
        mesa.ticks()

        assert mesa.motores_de(tres) == [], (
            "o Controle 3 recebeu o valor que ela fixou no 2 — o par MIGROU de "
            "dono por um gesto que não fala de vibração"
        )
        assert mesa.motores_de(dois) == [("left", 220), ("right", 160)] * 3, (
            "o dono do par tem de continuar recebendo os três reasserts"
        )

    @pytest.mark.asyncio
    async def test_o_dono_fica_gravado_no_gesto(self, mesa: _Mesa) -> None:
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})
        assert mesa.config.rumble_active == (160, 220)
        assert mesa.config.rumble_active_uniq == dois

    @pytest.mark.asyncio
    async def test_o_silencio_deliberado_tambem_tem_dono(self, mesa: _Mesa) -> None:
        """"Parar" cala UM controle — não quem entrar no seletor depois."""
        dois, tres = mesa.uniqs[1], mesa.uniqs[2]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_stop({})
        assert mesa.config.rumble_active == (0, 0)
        assert mesa.config.rumble_active_uniq == dois

        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(tres)})
        mesa.limpar_motores()
        mesa.ticks()
        assert mesa.motores_de(tres) == [], (
            "o silêncio fixado no 2 foi reescrito no 3"
        )


class TestOsCasosQueNaoMudam:
    """Hipótese tem de explicar o que JÁ funcionava."""

    @pytest.mark.asyncio
    async def test_com_o_alvo_em_todos_o_reassert_continua_broadcast(
        self, mesa: _Mesa
    ) -> None:
        await mesa.server._handle_controller_target_set({"index": None})
        await mesa.server._handle_rumble_set({"weak": 100, "strong": 200})
        assert mesa.config.rumble_active_uniq is None, (
            "«Todos» não é um dono — inventar um aqui calaria três controles"
        )
        mesa.limpar_motores()
        mesa.ticks(1)
        for uniq in mesa.uniqs:
            assert mesa.motores_de(uniq) == [("left", 200), ("right", 100)], uniq

    @pytest.mark.asyncio
    async def test_devolver_ao_jogo_esquece_o_dono(self, mesa: _Mesa) -> None:
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})
        await mesa.server._handle_rumble_passthrough({"enabled": True})
        assert mesa.config.rumble_active is None
        assert mesa.config.rumble_active_uniq is None
        mesa.limpar_motores()
        mesa.ticks()
        for uniq in mesa.uniqs:
            assert mesa.motores_de(uniq) == [], uniq


class TestODonoQueSaiDaMesa:
    @pytest.mark.asyncio
    async def test_dono_desconectado_nao_vira_broadcast(self, mesa: _Mesa) -> None:
        """Cair no broadcast seria o mesmo defeito pela outra porta."""
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})

        del mesa.backend._handles[_key_de(dois)]  # o Controle 2 sai da mesa
        mesa.limpar_motores()
        mesa.ticks()
        for uniq in mesa.uniqs:
            if uniq == dois:
                continue
            assert mesa.motores_de(uniq) == [], (
                f"{uniq} levou a vibração de um controle que nem está na mesa"
            )

    @pytest.mark.asyncio
    async def test_quando_o_dono_volta_o_proximo_tick_o_reencontra(
        self, mesa: _Mesa
    ) -> None:
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})

        handle = mesa.backend._handles.pop(_key_de(dois))
        mesa.ticks(1)
        mesa.backend._handles[_key_de(dois)] = handle  # replug
        mesa.limpar_motores()
        mesa.ticks(1)
        assert mesa.motores_de(dois) == [("left", 220), ("right", 160)]


class TestEscreverRumbleNoDono:
    """A função que sabe desviar do seletor — um lugar só, dois chamadores."""

    def test_sem_dono_cai_no_set_rumble(self) -> None:
        chamadas: list[tuple[int, int]] = []
        controller = SimpleNamespace(
            set_rumble=lambda weak, strong: chamadas.append((weak, strong)),
            set_rumble_for=lambda uniq, weak, strong: pytest.fail(
                "sem dono não se mira ninguém"
            ),
        )
        escrever_rumble_no_dono(controller, None, 10, 20)
        assert chamadas == [(10, 20)]

    def test_backend_sem_a_rota_por_mac_cai_no_historico(self) -> None:
        """FakeController e single-instance não têm `set_rumble_for`."""
        chamadas: list[tuple[int, int]] = []
        controller = SimpleNamespace(
            set_rumble=lambda weak, strong: chamadas.append((weak, strong))
        )
        escrever_rumble_no_dono(controller, "aabbcc000003", 10, 20)
        assert chamadas == [(10, 20)]

    def test_com_dono_nao_chama_o_broadcast_nem_quando_o_mac_falha(self) -> None:
        controller = SimpleNamespace(
            set_rumble=lambda weak, strong: pytest.fail(
                "MAC que não casa não vira broadcast — é no-op"
            ),
            set_rumble_for=lambda uniq, weak, strong: False,
        )
        escrever_rumble_no_dono(controller, "aabbcc0000ff", 10, 20)


# ---------------------------------------------------------------------------
# As OUTRAS PORTAS do mesmo defeito (14/08/2026)
#
# A cura da E0 tocou QUATRO famílias de sítio, e a primeira leva de testes só
# guardava DUAS (a aba Rumble e o reassert do poll loop). As duas de baixo
# sobreviviam a ser arrancadas com a suíte INTEIRA verde — e uma delas, meio
# aplicada, é ESTRITAMENTE pior que não ter feito nada: o «Aplicar» do rodapé
# grava o par novo e deixa o dono rançoso no controle do gesto anterior, então
# o reassert marreta um controle que ela não escolheu e o que ela escolheu não
# recebe nada. Antes da cura, o valor pelo menos ia para o seletor.
# ---------------------------------------------------------------------------


class TestOAplicarDoRodapeTambemTemDono:
    """Sítio órfão 1 — `ipc_draft_applier.DraftApplier._apply_rumble`.

    O botão «Aplicar» do rodapé mira o MESMO seletor do cabeçalho que a aba
    Rumble mira, e por isso tem de congelar o dono pelo mesmo critério. A rota
    é outra (`profile.apply_draft`, não `rumble.set`), e era por ela que o
    defeito voltava inteiro.
    """

    @pytest.mark.asyncio
    async def test_aplicar_mirado_no_tres_nao_marreta_o_dois(
        self, mesa: _Mesa
    ) -> None:
        dois, tres = mesa.uniqs[1], mesa.uniqs[2]

        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})

        # Ela troca de controle no cabeçalho e clica «Aplicar» com outro par.
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(tres)})
        resposta = await mesa.server._handle_profile_apply_draft(
            {"rumble": {"weak": 40, "strong": 80}}
        )
        assert "rumble" in resposta["applied"]
        assert mesa.config.rumble_active == (40, 80)

        mesa.limpar_motores()
        mesa.ticks()
        assert mesa.motores_de(dois) == [], (
            "o reassert marretou o Controle 2 com o valor que ela mandou para o "
            "3 — o dono ficou rançoso do gesto anterior"
        )
        assert mesa.motores_de(tres) == [("left", 80), ("right", 40)] * 3, (
            "o controle que ela escolheu no «Aplicar» não recebeu nada"
        )
        assert mesa.config.rumble_active_uniq == tres, (
            "o «Aplicar» do rodapé gravou o par NOVO e deixou o dono RANÇOSO no "
            "controle do gesto anterior"
        )

    @pytest.mark.asyncio
    async def test_aplicar_com_os_sliders_em_zero_esquece_o_dono(
        self, mesa: _Mesa
    ) -> None:
        """(0,0) no «Aplicar» é passthrough — solta o par E o endereço dele."""
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})

        await mesa.server._handle_profile_apply_draft(
            {"rumble": {"weak": 0, "strong": 0}}
        )
        assert mesa.config.rumble_active is None
        assert mesa.config.rumble_active_uniq is None, (
            "o par foi solto e o dono ficou para trás — endereço sem par é lixo "
            "que sobrevive ao gesto"
        )

        mesa.limpar_motores()
        mesa.ticks()
        for uniq in mesa.uniqs:
            assert mesa.motores_de(uniq) == [], uniq


class TestATrocaDePoliticaNaoTrocaDeControle:
    """Sítio órfão 2 — `lifecycle.Daemon._reapply_rumble_policy_to_active`.

    Trocar a INTENSIDADE re-escala o par que já está fixado e o reescreve na
    hora. Enquanto isso passava por `set_rumble` seco, a re-escala caía no
    seletor DE AGORA: a §1.c inteira de volta, por uma porta que não fala de
    escolher controle nenhum.
    """

    @pytest.mark.asyncio
    async def test_trocar_para_max_reescala_no_dono_e_nao_no_seletor(
        self, mesa: _Mesa
    ) -> None:
        dois, tres = mesa.uniqs[1], mesa.uniqs[2]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(tres)})

        daemon = mesa.daemon_de_verdade()
        mesa.limpar_motores()
        assert daemon.apply_profile_rumble_policy("max") == APLICADO

        # 160 e 220 vezes 1,5 -> 240 e 255 (o teto corta o segundo).
        assert mesa.motores_de(tres) == [], (
            "a re-escala da política caiu no controle do SELETOR — trocar a "
            "intensidade virou gesto de trocar de controle"
        )
        assert mesa.motores_de(dois) == [("left", 255), ("right", 240)], (
            "o dono do par não recebeu a re-escala da política nova"
        )


class TestSoltarOParEsqueceODono:
    """Sítios órfãos 3 e 4 — as duas solturas do par em `lifecycle`.

    `rumble_active_uniq` é o endereço DAQUELE par; quando o par é solto o
    endereço deixa de significar coisa alguma. A invariante é curta: **par
    solto, dono esquecido** — nenhum caminho pode deixar um endereço rançoso
    esperando o próximo par, que é como o defeito da §1.c nasceu (um ponteiro
    de um gesto valendo para o gesto seguinte).
    """

    @pytest.mark.asyncio
    async def test_o_release_do_modo_nativo_esquece_o_dono(
        self, mesa: _Mesa
    ) -> None:
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})
        assert mesa.config.rumble_active_uniq == dois

        mesa.daemon_de_verdade()._release_controller_to_game()
        assert mesa.config.rumble_active is None
        assert mesa.config.rumble_active_uniq is None, (
            "o Modo Nativo devolveu a vibração ao jogo e guardou o endereço do "
            "par que soltou"
        )

    @pytest.mark.asyncio
    async def test_o_passthrough_do_perfil_esquece_o_dono(
        self, mesa: _Mesa
    ) -> None:
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})

        mesa.daemon_de_verdade().apply_profile_rumble_passthrough(True)
        assert mesa.config.rumble_active is None
        assert mesa.config.rumble_active_uniq is None, (
            "a ativação de perfil soltou o par e guardou o endereço dele"
        )

    @pytest.mark.asyncio
    async def test_o_silencio_deliberado_conserva_par_e_dono(
        self, mesa: _Mesa
    ) -> None:
        """Hipótese tem de explicar o que JÁ funcionava: o «Parar» sobrevive."""
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_stop({})

        mesa.daemon_de_verdade().apply_profile_rumble_passthrough(True)
        assert mesa.config.rumble_active == (0, 0)
        assert mesa.config.rumble_active_uniq == dois


# ---------------------------------------------------------------------------
# A ROTA DE VOLTA DO CONTROLE ABANDONADO (14/08/2026, terceira rodada)
#
# Congelar o dono matou a migração do par — e criou o ABANDONO. As duas rodadas
# anteriores mediram só o INSTANTE do clique, onde HEAD e árvore são idênticos;
# um gesto depois eles DIVERGEM, e divergem para pior. Medido nos dois mundos
# com a mesma sonda (`git archive HEAD` num diretório separado, não emulação):
#
#     1. fixa 160/220 no Controle 2   -> dono = 2, motor do 2 em 220/160
#     2. move o seletor para o 3
#     3. clica «Parar»                -> os zeros vão para o 3; o 2 segue em 220/160
#     4. VOLTA o seletor para o controle que continua vibrando, para ver o que há
#
#     HEAD ....: o 2 recebe [(left,0),(right,0)] x3  -> SILENCIADO
#     Árvore ..: o 2 recebe []                       -> vibra em 220/160 PARA SEMPRE
#
# O reassert passou a mirar eternamente o 3, e voltar o seletor ao 2 deixou de
# significar coisa alguma: a cura tinha arrancado a única rota de resgate que
# ela tinha num controle abandonado vibrando.
#
# E O «PARAR» NÃO É A ÚNICA PORTA — foi o que sustentou a escolha da cura. A
# mesma sonda mostra `rumble.set` mirado no 3 (e o «Aplicar» do rodapé) deixando
# o 2 em 220/160 do mesmo jeito. Por isso a cura tem DOIS chamadores e não um
# remendo no «Parar»:
#
#   * o «Parar» resgata NA HORA (parar quer dizer «cale o que está vibrando»);
#   * o poll loop resgata a cada tick — `lifecycle.py:3953` marca
#     `tick_started + 0.200`, cinco ticks por segundo —, e é a rede que apanha
#     as outras portas, inclusive as que não estão nesta cerca.
#
# Por isso os testes abaixo RODAM O POLL LOOP entre os gestos: é o que a máquina
# dela faz. Sem tick nenhum entre dois gestos de rumble — 200 ms, impossível a
# mão — só o «Parar» resgata.
# ---------------------------------------------------------------------------


class TestOAbandonadoTemRotaDeVolta:
    """§5 da sprint: *"a volta ao neutro vale tanto quanto a ida"*."""

    @pytest.mark.asyncio
    async def test_o_parar_mirado_no_tres_cala_o_dois_que_estava_vibrando(
        self, mesa: _Mesa
    ) -> None:
        """O roteiro inteiro, com o GESTO 4 — o que ninguém tinha medido."""
        dois, tres = mesa.uniqs[1], mesa.uniqs[2]

        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})
        mesa.ticks(2)  # o poll loop roda enquanto ela sente o controle vibrar
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(tres)})

        mesa.limpar_motores()
        await mesa.server._handle_rumble_stop({})
        assert mesa.motores_de(dois) == [("left", 0), ("right", 0)], (
            "o «Parar» calou o controle do seletor e deixou o Controle 2 "
            "sacudindo em 220/160 — o gesto que quer dizer «cale» não calou "
            "quem estava vibrando"
        )
        assert mesa.motores_de(tres) == [("left", 0), ("right", 0)], (
            "o controle do seletor também recebe os zeros do gesto"
        )

        # GESTO 4: ela volta o seletor para o controle que vibrava.
        mesa.limpar_motores()
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        mesa.ticks(3)
        assert mesa.motores_de(dois) == [], (
            "o Controle 2 já estava calado — resgate repetido é escrita HID à "
            "toa, e o par de agora tem dono, não segue o seletor"
        )

    @pytest.mark.asyncio
    async def test_o_set_mirado_no_tres_cala_o_dois_pelo_poll_loop(
        self, mesa: _Mesa
    ) -> None:
        """A segunda porta: fixar OUTRO par também abandona o dono anterior."""
        dois, tres = mesa.uniqs[1], mesa.uniqs[2]

        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})
        mesa.ticks(2)
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(tres)})

        mesa.limpar_motores()
        await mesa.server._handle_rumble_set({"weak": 40, "strong": 90})
        mesa.ticks(3)
        assert mesa.motores_de(dois) == [("left", 0), ("right", 0)], (
            "o par mudou de dono e o Controle 2 ficou em 220/160 sem receber "
            "mais escrita nenhuma — uma vez, e só uma"
        )
        assert mesa.motores_de(tres) == [("left", 90), ("right", 40)] * 4, (
            "o dono novo recebe o gesto e os três reasserts"
        )

    @pytest.mark.asyncio
    async def test_o_aplicar_do_rodape_tambem_devolve_o_abandonado(
        self, mesa: _Mesa
    ) -> None:
        """A terceira porta: o «Aplicar» do rodapé, por `profile.apply_draft`."""
        dois, tres = mesa.uniqs[1], mesa.uniqs[2]

        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})
        mesa.ticks(2)
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(tres)})

        mesa.limpar_motores()
        await mesa.server._handle_profile_apply_draft(
            {"rumble": {"weak": 40, "strong": 80}}
        )
        mesa.ticks(3)
        assert mesa.motores_de(dois) == [("left", 0), ("right", 0)], (
            "o «Aplicar» do rodapé mudou o dono do par e abandonou o Controle 2 "
            "vibrando"
        )
        assert mesa.motores_de(tres) == [("left", 80), ("right", 40)] * 4, (
            "o controle que ela escolheu no «Aplicar» recebe o par e os reasserts"
        )


class TestOResgateNaoPiscaQuemNaoFoiAbandonado:
    """Hipótese tem de explicar o que JÁ funcionava — e não pode piscar motor."""

    @pytest.mark.asyncio
    async def test_o_dono_que_nao_muda_nunca_recebe_um_zero(
        self, mesa: _Mesa
    ) -> None:
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})
        mesa.limpar_motores()
        mesa.ticks(5)
        assert mesa.motores_de(dois) == [("left", 220), ("right", 160)] * 5, (
            "o resgate disparou sem ninguém ter sido abandonado — cada zero "
            "aqui é uma falha de vibração no meio da partida dela"
        )

    @pytest.mark.asyncio
    async def test_trocar_para_todos_nao_zera_ninguem_antes_do_broadcast(
        self, mesa: _Mesa
    ) -> None:
        """«Todos» alcança o abandonado junto — zerar antes só piscaria."""
        dois = mesa.uniqs[1]
        await mesa.server._handle_controller_target_set({"index": mesa.indice_de(dois)})
        await mesa.server._handle_rumble_set({"weak": 160, "strong": 220})
        mesa.ticks(2)

        await mesa.server._handle_controller_target_set({"index": None})
        mesa.limpar_motores()
        await mesa.server._handle_rumble_set({"weak": 10, "strong": 20})
        mesa.ticks(2)
        for uniq in mesa.uniqs:
            assert mesa.motores_de(uniq) == [("left", 20), ("right", 10)] * 3, (
                f"{uniq} levou um zero antes do broadcast — o motor PISCOU numa "
                "troca de alvo que alcança todo mundo de qualquer jeito"
            )


class TestSilenciarDonoAbandonado:
    """Os três no-ops deliberados, na função sozinha."""

    def test_sem_abandonado_nao_escreve(self) -> None:
        controller = SimpleNamespace(
            set_rumble=lambda weak, strong: pytest.fail("não há a quem voltar"),
            set_rumble_for=lambda uniq, weak, strong: pytest.fail(
                "não há a quem voltar"
            ),
        )
        assert silenciar_dono_abandonado(controller, None, "aabbcc000003") is False

    def test_o_mesmo_dono_nao_leva_zero(self) -> None:
        controller = SimpleNamespace(
            set_rumble=lambda weak, strong: pytest.fail("o par já reescreve nele"),
            set_rumble_for=lambda uniq, weak, strong: pytest.fail(
                "o par já reescreve nele"
            ),
        )
        assert (
            silenciar_dono_abandonado(controller, "aabbcc000003", "aabbcc000003")
            is False
        )

    def test_abandonado_de_verdade_leva_os_zeros_por_mac(self) -> None:
        miradas: list[tuple[str, int, int]] = []
        controller = SimpleNamespace(
            set_rumble=lambda weak, strong: pytest.fail("com dono não há broadcast"),
            set_rumble_for=lambda uniq, weak, strong: (
                miradas.append((uniq, weak, strong)) or True
            ),
        )
        assert (
            silenciar_dono_abandonado(controller, "aabbcc000003", "aabbcc0000f0")
            is True
        )
        assert miradas == [("aabbcc000003", 0, 0)]
