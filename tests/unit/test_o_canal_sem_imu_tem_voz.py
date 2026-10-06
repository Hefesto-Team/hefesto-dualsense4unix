"""CANAL-SEM-VOZ-01 (17/09/2026) — a régua R3, a do silêncio.

A QUEIXA QUE ORIGINOU ESTE ARQUIVO, e é do usuário
================================================
    **

O `pragmata.json` **não tem** a chave `caminho` — lido no disco do usuário. Ele herdou
o `config.gamepad_caminho` que o jogo anterior deixou de pé (o usuário escolheu Xbox
no DON'T SCREAM, de propósito, e funcionou lá). Com o caminho Xbox o vpad nasce
em `uinput`, e em `uinput` não há giroscópio: **dez linhas** do
`docs/data/mapa-controles.csv` saem do ar juntas.

NADA AQUI MUDA O CANAL. A herança do caminho é frente de outra leva. O que se
mede aqui é a VOZ: o par «máscara DualSense + caminho Xbox» parou de cair
calado.

POR QUE ISTO PRECISOU DE RÉGUA, e é a lição mais cara do dia
============================================================
O preço já estava escrito, medido, palavra por palavra, desde 19/08/2026 — em
`integrations/ponte_escada.py:231`, na justificativa do primeiro degrau:

    *"Errar aqui custa um aperto de botão; errar para Xbox custa as dez, e
    custa em silêncio."*

Estava num COMENTÁRIO. **Aviso em comentário ninguém lê**, e um mês depois ela
jogou um jogo de movimento e o controle não respondeu. Um canal que alguém lê —
o journal do launch e o `daemon.state_full` — é a diferença entre o produto
saber e o produto contar.

A MORDIDA DE CADA TESTE está no docstring dele. Foram arrancadas de verdade.

O QUE ESTA RÉGUA PROTEGE DOS DOIS LADOS, e o segundo lado é decisão de produto
========================================================================
PS-L3-MASCARA-01 (14/09/2026): *o uinput do caminho Xbox é ESCOLHA do usuário, não
degradação*. `gamepad.dedup_status` o isenta desde então
(`and caminho_do_vpad(device) != CAMINHO_XBOX`), e `degraded` no `state_full`
faz o mesmo.

`test_a_escolha_dela_continua_integra_e_o_campo_novo_fala` exige **as duas
coisas na mesma leitura**: `degraded`/`dedup_ok` dizendo íntegro (a decisão
de produto, intacta) **e** `canal_sem_imu` dizendo que as dez saíram do ar. Ele
reprova tanto para quem arrancar a voz nova quanto para quem tentar "curar"
isto reabrindo a decisão de 14/09 — que é o que aconteceria ao tirar a isenção
de `gamepad.py`.
"""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.cli.ipc_client import IpcClient
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.integrations import canal_sem_imu as sem_imu
from hefesto_dualsense4unix.integrations import ponte_escada as pe
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    MatchAny,
    PonteConfirmada,
    Profile,
    ProfileModeConfig,
)
from hefesto_dualsense4unix.testing import FakeController

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"


def _as_dez_do_mapa() -> tuple[str, ...]:
    """As dez, relidas AQUI a partir do CSV, sem passar pelo módulo medido."""
    with MAPA.open(encoding="utf-8", newline="") as arq:
        return tuple(
            sorted(
                (linha["chave"] or "").strip()
                for linha in csv.DictReader(arq)
                if (linha["controle"] or "").strip() == "dualsense"
                and (linha["ponte_alcanca"] or "").strip() == pe.ESCADA[0].ponte.chave
            )
        )


class TestAsDezVemDoMapa:
    def test_o_modulo_le_o_mapa_e_nao_uma_lista_decorada(self) -> None:
        """MORDA: troque uma chave em `DEZ_LINHAS_CONGELADAS` — este reprova."""
        do_mapa = _as_dez_do_mapa()
        assert len(do_mapa) == 10, (
            "o mapa deixou de declarar dez linhas com `ponte_alcanca = "
            f"{pe.ESCADA[0].ponte.chave}`; são elas que justificam o primeiro "
            "degrau da ESCADA, e a conta tem de mudar junto com a prosa de "
            "`integrations/ponte_escada.py`"
        )
        assert sem_imu.linhas_do_mapa() == do_mapa

    def test_a_copia_congelada_nao_pode_divergir_do_mapa(self) -> None:
        """A cópia existe porque o CSV não entra no wheel — não para divergir."""
        assert _as_dez_do_mapa() == sem_imu.DEZ_LINHAS_CONGELADAS, (
            "a cópia congelada de `integrations/canal_sem_imu.py` divergiu do "
            "mapa; o mapa manda, e a cópia existe só para o produto instalado, "
            "onde o CSV não está no disco"
        )

    def test_sem_mapa_no_disco_o_evento_nao_emudece(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """O cenário do wheel: sem CSV, as dez saem da cópia congelada."""
        monkeypatch.setattr(sem_imu, "MAPA", tmp_path / "nao-existe.csv")
        monkeypatch.setattr(sem_imu, "_DO_DISCO", sem_imu.linhas_do_mapa())

        assert sem_imu.linhas_do_mapa() == ()
        assert sem_imu.chaves_fora_do_ar() == sem_imu.DEZ_LINHAS_CONGELADAS
        assert "movimento.giroscopio.jogo" in sem_imu.chaves_fora_do_ar()


def _vpad(*, flavor: str, backend: str, caminho: str | None) -> SimpleNamespace:
    pad = SimpleNamespace(flavor=flavor, backend=backend)
    if caminho is not None:
        pad.caminho = caminho
    return pad


class TestOParQueTiraAsDezDoAr:
    @pytest.mark.parametrize(
        ("flavor", "backend", "caminho", "sem_dez", "porque"),
        [
            # O caso DO USUÁRIO: o jogo vê um DualSense, e o canal é o comum.
            ("dualsense", "uinput", "xbox", True, "o par do PRAGMATA"),
            # O canal do DualSense entrega as dez — nada a dizer.
            ("dualsense", "uhid", "dualsense", False, "o primeiro degrau"),
            ("xbox", "uinput", "xbox", False, "o segundo degrau, declarado"),
            # Sem caminho escolhido, a máscara DualSense resolve para o canal
            # DualSense (`caminho_resolvido`) — o produto de antes de 13/09.
            ("dualsense", "uhid", None, False, "sem escolha, a máscara decide"),
        ],
    )
    def test_so_o_par_da_queixa_dela_acende(
        self, flavor: str, backend: str, caminho: str | None, sem_dez: bool, porque: str
    ) -> None:
        """MORDA: tire o gate da máscara de `canal_sem_imu` e o terceiro caso"""
        pad = _vpad(flavor=flavor, backend=backend, caminho=caminho)
        assert sem_imu.canal_sem_imu_do_vpad(pad) is sem_dez, porque

    def test_uhid_sem_caminho_declarado_nunca_diz_que_perdeu_a_imu(self) -> None:
        """Um vpad `uhid` está com a IMU NO AR — diga o que disser o caminho."""
        pad = _vpad(flavor="dualsense", backend="uhid", caminho="xbox")
        assert sem_imu.canal_sem_imu_do_vpad(pad) is False

    def test_sem_vpad_nao_ha_o_que_dizer(self) -> None:
        assert sem_imu.canal_sem_imu_do_vpad(None) is False


class _RegistroDeLog:
    """Logger dublado que guarda o evento INTEIRO — nome e payload."""

    def __init__(self) -> None:
        self.eventos: list[tuple[str, str, dict[str, Any]]] = []

    def _anota(self, nivel: str) -> Any:
        def _log(evento: str, **kw: Any) -> None:
            self.eventos.append((nivel, evento, kw))

        return _log

    def __getattr__(self, nome: str) -> Any:
        return self._anota(nome)

    def avisos(self, evento: str) -> list[dict[str, Any]]:
        return [kw for n, e, kw in self.eventos if n == "warning" and e == evento]


class _DaemonFalso:
    """O mínimo que a materialização toca: modo, emulação, vpad e co-op."""

    def __init__(
        self,
        *,
        nativo: bool = False,
        emulacao: bool = True,
        flavor: str = "dualsense",
        backend: str = "uinput",
        caminho: str | None = "xbox",
        coop: tuple[tuple[int, str, str, str | None], ...] = (),
    ) -> None:
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=emulacao,
            gamepad_flavor=flavor,
            gamepad_caminho=caminho,
            rumble_active=None,
        )
        self._gamepad_device: Any = _vpad(
            flavor=flavor, backend=backend, caminho=caminho
        )
        jogadores = {
            f"aa:bb:cc:00:00:{i:02x}": SimpleNamespace(
                player_index=indice,
                vpad=_vpad(flavor=f, backend=b, caminho=c),
            )
            for i, (indice, f, b, c) in enumerate(coop)
        }
        self._coop_manager = (
            SimpleNamespace(_players=jogadores) if jogadores else None
        )
        self.controller = SimpleNamespace(set_rumble=lambda **_k: None)
        self._nativo = nativo

    def is_native_mode(self) -> bool:
        return self._nativo


@pytest.fixture()
def borda(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> _RegistroDeLog:
    """A borda de materialização isolada: nada de disco do usuário, nada de perfis."""
    from hefesto_dualsense4unix.daemon import launch_env as le

    registro = _RegistroDeLog()
    monkeypatch.setattr(le, "logger", registro)
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
    monkeypatch.setattr(le, "_load_profiles", lambda daemon: [])
    monkeypatch.setattr(le, "_fisicos_na_mesa", lambda daemon: 1)
    return registro


def _materializar(daemon: Any) -> None:
    from hefesto_dualsense4unix.daemon.launch_env import materialize_launch_env

    materialize_launch_env(daemon)


class TestOJournalNomeiaAsDez:
    def test_o_evento_sai_com_as_dez_linhas_nominadas(
        self, borda: _RegistroDeLog
    ) -> None:
        """A entrega desta frente, vista do journal do usuário."""
        _materializar(_DaemonFalso())

        avisos = borda.avisos(sem_imu.EVENTO)
        assert len(avisos) == 1, (
            "o par «máscara DualSense + caminho Xbox» armou um vpad uinput e o "
            "journal do launch não disse nada — é o silêncio da queixa dela"
        )
        payload = avisos[0]
        assert payload["quantas"] == 10
        assert payload["linhas"] == list(_as_dez_do_mapa()), (
            "o evento tem de NOMEAR as dez linhas do mapa, lidas dele; uma "
            "lista digitada aqui envelhece na primeira feature `uhid` nova"
        )
        assert "movimento.giroscopio.jogo" in payload["linhas"], (
            "a linha da queixa dela — o controle por movimento — tem de estar "
            "nomeada no evento"
        )
        assert payload["jogadores"] == ["1"]
        assert payload["caminho"] == "xbox"
        assert payload["mascara"] == "dualsense"

    def test_a_mesa_de_quatro_nomeia_os_quatro(self, borda: _RegistroDeLog) -> None:
        """O caminho é da SESSÃO, e o contágio leva os quatro juntos."""
        daemon = _DaemonFalso(
            coop=(
                (2, "dualsense", "uinput", "xbox"),
                (3, "dualsense", "uinput", "xbox"),
                (4, "dualsense", "uinput", "xbox"),
            )
        )
        _materializar(daemon)

        assert borda.avisos(sem_imu.EVENTO)[0]["jogadores"] == ["1", "2", "3", "4"]

    @pytest.mark.parametrize(
        ("daemon", "porque"),
        [
            (
                _DaemonFalso(backend="uhid", caminho="dualsense"),
                "o canal do DualSense entrega as dez — nada a avisar",
            ),
            (
                _DaemonFalso(flavor="xbox"),
                "máscara Xbox é escolha coerente, e o preço está na ESCADA",
            ),
            (
                _DaemonFalso(nativo=True),
                "em Modo Nativo o jogo fala com o plástico: a IMU está no ar",
            ),
            (
                _DaemonFalso(emulacao=False),
                "sem emulação não há vpad sobre o que falar",
            ),
        ],
    )
    def test_o_evento_nao_toca_onde_nao_ha_amputacao(
        self, daemon: Any, porque: str, borda: _RegistroDeLog
    ) -> None:
        _materializar(daemon)
        assert borda.avisos(sem_imu.EVENTO) == [], porque

    def test_o_aviso_nunca_derruba_a_materializacao(
        self, borda: _RegistroDeLog, tmp_path: Path
    ) -> None:
        """Telemetria, nunca portão: o `default.env` continua saindo."""
        _materializar(_DaemonFalso())
        assert (tmp_path / "default.env").exists()


# PARTE 4 — o `state_full`, com a decisão de produto intacta ao lado


@pytest.fixture
def perfis_isolados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


@pytest.fixture
async def servidor(tmp_path: Path, perfis_isolados: Path) -> Any:
    """Servidor IPC REAL com `FakeController` — o padrão de contrato da casa."""
    fc = FakeController(transport="usb")
    fc.connect()
    store = StateStore()
    gerente = ProfileManager(controller=fc, store=store)
    save_profile(Profile(name="fallback", match=MatchAny(), priority=0))

    daemon = MagicMock()
    daemon._last_state = None
    daemon._coop_manager = None
    daemon.is_native_mode = lambda: False
    daemon.config = MagicMock(
        mouse_emulation_enabled=False,
        mouse_speed=6,
        mouse_scroll_speed=1,
        rumble_policy="balanceado",
        rumble_policy_custom_mult=0.7,
        gamepad_emulation_enabled=True,
        gamepad_flavor="dualsense",
        gamepad_caminho="xbox",
    )

    socket_path = tmp_path / "hefesto-dualsense4unix.sock"
    servidor = IpcServer(
        controller=fc,
        store=store,
        profile_manager=gerente,
        socket_path=socket_path,
        daemon=daemon,
    )
    await servidor.start()
    try:
        yield socket_path, daemon
    finally:
        await servidor.stop()


async def _gamepad_emulation(socket_path: Path) -> dict[str, Any]:
    async with IpcClient.connect(socket_path) as cliente:
        estado = await cliente.call("daemon.state_full")
    assert isinstance(estado, dict)
    bloco = estado["gamepad_emulation"]
    assert isinstance(bloco, dict)
    return bloco


class TestOStateFullPublicaOCampoNovo:
    @pytest.mark.asyncio
    async def test_a_escolha_dela_continua_integra_e_o_campo_novo_fala(
        self, servidor: Any
    ) -> None:
        """A RÉGUA R3, e ela morde dos DOIS lados.

        As duas afirmações saem da MESMA leitura do `state_full`:

        1. `degraded` e `dedup_ok` dizem ÍNTEGRO — PS-L3-MASCARA-01
           (14/09/2026), decisão de produto: o uinput do caminho Xbox é ESCOLHA, não
           degradação. **Reponha a "cura" que tira a isenção
           `and caminho_do_vpad(device) != CAMINHO_XBOX` de
           `gamepad.dedup_status` e este teste reprova** — porque isso é
           reabrir uma decisão medida;
        2. `canal_sem_imu` diz que as dez saíram do ar. **Arranque o bloco
           CANAL-SEM-VOZ-01 de `ipc_handlers` e este teste reprova com
           `KeyError: 'canal_sem_imu'`** — e o que sobra é o produto de 17/09
           pela manhã: "integra" com a IMU fora do ar, e ninguém contando.
        """
        socket_path, daemon = servidor
        daemon._gamepad_device = _vpad(
            flavor="dualsense", backend="uinput", caminho="xbox"
        )

        bloco = await _gamepad_emulation(socket_path)

        assert bloco["degraded"] is False, (
            "o caminho Xbox NÃO é degradação — decisão dela de 14/09/2026 "
            "(PS-L3-MASCARA-01), e ela não se reabre por esta frente"
        )
        assert bloco["dedup_ok"] is True, (
            "o `dedup_status` continua isentando o caminho Xbox; é justamente "
            "este «integra» que o campo novo existe para acompanhar"
        )
        assert bloco["canal_sem_imu"] is True, (
            "o jogo vê um DualSense por um canal `uinput` e o `state_full` não "
            "tem onde dizer isso — é o silêncio que fez a queixa dela chegar "
            "até aqui"
        )
        assert bloco["canal_sem_imu_linhas"] == list(_as_dez_do_mapa())

    @pytest.mark.asyncio
    async def test_o_canal_do_dualsense_publica_o_campo_em_falso(
        self, servidor: Any
    ) -> None:
        """O campo sai SEMPRE que há vpad — ausência não pode virar resposta."""
        socket_path, daemon = servidor
        daemon._gamepad_device = _vpad(
            flavor="dualsense", backend="uhid", caminho="dualsense"
        )

        bloco = await _gamepad_emulation(socket_path)

        assert bloco["canal_sem_imu"] is False
        assert "canal_sem_imu_linhas" not in bloco


def _perfil(*, caminho: str | None, mascara: str, carimbo: str | None) -> Profile:
    """Um perfil de jogo com `mode` e (talvez) carimbo de ponte."""
    return Profile(
        name="pragmata",
        match=MatchAny(),
        priority=10,
        mode=ProfileModeConfig(
            kind="gamepad", gamepad_flavor=mascara, caminho=caminho
        ),
        ponte=(
            None
            if carimbo is None
            else PonteConfirmada(kind="gamepad", gamepad_flavor=carimbo)
        ),
    )


class TestOAlarmeSoComparaTermoComTermo:
    def test_perfil_sem_caminho_nao_diverge_de_carimbo_nenhum(self) -> None:
        """O ALARME FALSO DAS 10:45:02, medido no journal do usuário em 17/09/2026."""
        perfil = _perfil(caminho=None, mascara="xbox", carimbo="dualsense")

        assert (
            pe.divergencia_com_o_carimbo(
                perfil, pe.ponte_do_carimbo(perfil.ponte), na_allowlist=False
            )
            is None
        ), (
            "perfil que não declara `caminho` é SILÊNCIO sobre o canal, e "
            "silêncio não diverge de nada — comparar a máscara dele com o "
            "caminho carimbado é o alarme falso das 10:45:02"
        )

    def test_caminho_contra_caminho_continua_divergindo(self) -> None:
        """A cura não pode emudecer o alarme legítimo."""
        perfil = _perfil(caminho="dualsense", mascara="dualsense", carimbo="xbox")

        assert pe.divergencia_com_o_carimbo(
            perfil, pe.ponte_do_carimbo(perfil.ponte), na_allowlist=False
        ) == ("caminho", "dualsense", "xbox")

    def test_a_mascara_do_perfil_nunca_entra_na_conta(self) -> None:
        """Trocar só a MÁSCARA não pode acender o alarme do CARIMBO."""
        for mascara in ("dualsense", "xbox"):
            perfil = _perfil(caminho="xbox", mascara=mascara, carimbo="xbox")
            assert (
                pe.divergencia_com_o_carimbo(
                    perfil, pe.ponte_do_carimbo(perfil.ponte), na_allowlist=False
                )
                is None
            ), f"a máscara {mascara} entrou na conta do carimbo"

    def test_sem_carimbo_nao_ha_alarme(self) -> None:
        perfil = _perfil(caminho="xbox", mascara="dualsense", carimbo=None)
        assert (
            pe.divergencia_com_o_carimbo(perfil, None, na_allowlist=False) is None
        )

    def test_o_kind_continua_sendo_comparado(self) -> None:
        """`kind` existe com o mesmo significado dos dois lados — nunca saiu."""
        perfil = _perfil(caminho="xbox", mascara="dualsense", carimbo="xbox")
        carimbo = pe.Ponte(kind=pe.KIND_NATIVE)

        assert pe.divergencia_com_o_carimbo(
            perfil, carimbo, na_allowlist=False
        ) == ("kind", pe.KIND_GAMEPAD, pe.KIND_NATIVE)
