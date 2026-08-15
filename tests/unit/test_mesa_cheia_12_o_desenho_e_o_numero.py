"""MESA-CHEIA-12 — o desenho aceso na barra É o número publicado.

A medição de **15/08/2026, 01h00**, com os QUATRO DualSense dela no rádio. De
um lado o `daemon.state_full` pelo socket, do outro o `/sys/class/leds` da
máquina, lidos no mesmo minuto:

Os controles vão pelo LUGAR NA FILA (o `rank` do `controllers.json` dela) —
nenhum endereço real entra em arquivo versionado:

| controle   | `player` publicado | `player_slot` | LEDs acesos  | = jogador |
|------------|--------------------|---------------|--------------|-----------|
| 1º da fila | 1                  | 1             | `[3]`        | 1         |
| 4º da fila | 2                  | 4             | `[1,2,4,5]`  | **4**     |
| 2º da fila | 3                  | 2             | `[2,4]`      | **2**     |
| 3º da fila | 4                  | 3             | `[1,3,5]`    | **3**     |

Três dos quatro controles acendiam um número e eram chamados de outro. Não era
resíduo de estado velho: um `coop.sync` por IPC devolveu
`{"status":"ok","players":4,"active":true}` e os LEDs ficaram idênticos — o
daemon reescrevia ativamente o desenho, e o desenho batia 4/4 com o
`player_slot` e 1/4 com o `player`.

## Por que eram dois números

- **a lâmpada** saía de `CoopManager._numero_exibido` →
  `identity_registry.slot_for`: a FILA DE CHEGADA (`controllers.json`),
  colocação entre os presentes;
- **o número publicado** saía de `CoopManager.player_indexes()` →
  `_SecondaryPlayer.player_index`: o índice de ALOCAÇÃO do vpad do co-op
  (`_next_player_index`, menor livre ≥2), que é a ordem em que o EVIOCGRAB de
  cada secundário confirmou nesta sessão.

Duas ordens diferentes do mesmo MAC. Na mesa dela elas estavam separadas nos
três secundários porque o co-op os promoveu na ordem 4º/2º/3º da fila
(journal: `coop_player_added player=2/3/4`), enquanto a fila da casa punha o
quarto em 4 e o segundo em 2.

A verdade única é a FILA DE CHEGADA, por decisão dela
(`docs/process/sprints/2026-08-14-INDICE-a-cor-do-controle-e-o-som-de-cada-jogador.md`:
*"a ordem deve ser por ordem de conexão daquele momento"*, e essa ordem
prevalece). A cura foi tirar o número publicado do `player_index` e pô-lo em
`CoopManager.numeros_de_jogador()` — a MESMA função que escolhe o desenho.

## O que este arquivo morde

Nada de dublê no meio do caminho: a lâmpada é ESCRITA num `/sys/class/leds`
falso pelo escritor de produção (`core/sysfs_leds`), e depois LIDA de volta e
decodificada em número. Se o desenho voltar a divergir do número publicado em
QUALQUER um dos quatro jogadores, o teste cai.

Nenhum endereço real: os quatro usam a faixa forjada `aa:bb:cc:…`, a mesma
allowlist de `test_anonimato_de_fixtures.py`. A ORDEM dos MACs reproduz a mesa
dela; os bytes, não.
"""
from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import sysfs_leds
from hefesto_dualsense4unix.core.led_control import player_led_pattern
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.daemon.subsystems.identity import ControllerIdentityRegistry
from hefesto_dualsense4unix.testing import FakeController

# --- a mesa dela, mascarada -------------------------------------------------
#
# O sufixo de cada constante é o LUGAR NA FILA (o `rank` do `controllers.json`
# dela), e o nome diz quem era: `PRIMARIO` é o que o backend elegeu.
#: rank 1 — o primário (o único cujo número já batia antes da cura).
FILA1_PRIMARIO = "aa:bb:cc:00:00:01"
#: rank 2 — o co-op o promoveu em TERCEIRO (publicava 3, acendia 2).
FILA2 = "aa:bb:cc:00:00:02"
#: rank 3 — o co-op o promoveu em QUARTO (publicava 4, acendia 3).
FILA3 = "aa:bb:cc:00:00:03"
#: rank 4 — o co-op o promoveu em PRIMEIRO (publicava 2, acendia 4).
FILA4 = "aa:bb:cc:00:00:04"

#: MAC -> lugar na fila de chegada. É a resposta certa para TODAS as
#: superfícies: a lâmpada, o rótulo e o `state_full`.
FILA = {FILA1_PRIMARIO: 1, FILA2: 2, FILA3: 3, FILA4: 4}

#: A ordem em que o co-op promoveu os secundários naquela sessão — a ordem que
#: gerava o `player_index` 2/3/4 e, com ele, o número errado.
ORDEM_DE_PROMOCAO = (FILA4, FILA2, FILA3)

#: Um quinto controle que NUNCA ganhou lugar na fila — o caso do número
#: duplicado (ver `TestNumeroRepetidoEProibido`). Fica fora de `FILA` de
#: propósito: é isso que ele é.
SEM_FILA = "aa:bb:cc:00:00:09"

#: Prefixo do nó de LED de cada controle no sysfs falso (a forma que o
#: `sysfs_leds.discover()` espera: `<bus>:<vid>:<pid>.<n>`).
PREFIXO = {
    mac: f"0005:054C:0CE6.000{n}"
    for n, mac in enumerate([*FILA, SEM_FILA], start=1)
}


# --- o /sys/class/leds falso, com o escritor/leitor de PRODUÇÃO -------------


@pytest.fixture
def raiz_leds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um `/sys/class/leds` só deste teste, na forma que o `discover()` lê."""
    leds = tmp_path / "leds"
    leds.mkdir()
    monkeypatch.setattr(sysfs_leds, "LEDS_ROOT", str(leds))
    for mac, prefixo in PREFIXO.items():
        # `discover()` resolve o dono por realpath do `:rgb:indicator` ->
        # .../<HID>/leds/<prefixo>:rgb:indicator, e lê o MAC do `uevent` do
        # <HID>. O sysfs falso tem de ter essa forma exata.
        hid = tmp_path / "devices" / prefixo
        (hid / "leds" / f"{prefixo}:rgb:indicator").mkdir(parents=True)
        (hid / "uevent").write_text(f"HID_UNIQ={mac}\n", encoding="utf-8")
        os.symlink(
            hid / "leds" / f"{prefixo}:rgb:indicator",
            leds / f"{prefixo}:rgb:indicator",
        )
        for i in range(1, 6):
            (leds / f"{prefixo}:white:player-{i}").mkdir()
    return tmp_path


def acender(mac: str, numero: int) -> None:
    """Escreve a barra deste controle com o escritor de PRODUÇÃO."""
    nodes = sysfs_leds.discover()
    node = nodes[sysfs_leds.norm_mac(mac) or ""]
    assert node.set_players(player_led_pattern(numero))


def numero_aceso(mac: str) -> int | None:
    """Lê a barra de volta e decodifica o NÚMERO. None = padrão de ninguém."""
    nodes = sysfs_leds.discover()
    bits = nodes[sysfs_leds.norm_mac(mac) or ""].get_players()
    if bits is None:
        return None
    for n in range(1, 9):
        if tuple(bits) == player_led_pattern(n):
            return n
    return None


# --- a fiação: registros de produção, dublê só de APARELHO ------------------


class _ControllerFalso:
    """Só o que o co-op lê do backend: quem é o primário."""

    def __init__(self, primary: str) -> None:
        self.primary_uniq = primary


class _DaemonFalso:
    def __init__(self, registro: ControllerIdentityRegistry, primary: str) -> None:
        self.identity_registry = registro
        self.controller = _ControllerFalso(primary)


def montar_a_mesa_de_15_08() -> CoopManager:
    """A mesa exata das 01h00: fila 1..4, co-op promovendo em 4/2/3."""
    registro = ControllerIdentityRegistry()
    for mac in FILA:  # a fila nasce na ordem de PRIMEIRA aparição
        registro.slot_for(mac)
    registro.sync_connected(list(FILA))
    coop = CoopManager.__new__(CoopManager)
    coop._daemon = _DaemonFalso(registro, FILA1_PRIMARIO)  # type: ignore[assignment]
    coop._players = {
        mac: _SecondaryPlayer(
            identity=mac,
            evdev_path=f"/dev/input/event{200 + i}",
            reader=None,  # type: ignore[arg-type]
            # o `player_index` histórico: menor livre ≥2 na ordem de promoção
            player_index=i + 2,
            vpad=object(),  # type: ignore[arg-type]
        )
        for i, mac in enumerate(ORDEM_DE_PROMOCAO)
    }
    return coop


# --- a mordida --------------------------------------------------------------


class TestODesenhoEONumeroSaoOMesmo:
    """O invariante inteiro, varrendo os QUATRO jogadores — não só um."""

    def test_o_retrato_de_01h00_esta_montado(self) -> None:
        """Ancoragem: se a mesa não for a dela, o resto não prova nada.

        O `player_index` reproduzido aqui é o que o journal registrou
        (`coop_player_added player=2` no 4º da fila, `3` no 2º e `4` no 3º)
        — a fresta só existe porque ele discorda da fila.
        """
        coop = montar_a_mesa_de_15_08()
        assert {
            mac: p.player_index for mac, p in coop._players.items()
        } == {FILA4: 2, FILA2: 3, FILA3: 4}
        assert coop._daemon.identity_registry.snapshot() == {  # type: ignore[attr-defined]
            "aabbcc000001": 1,
            "aabbcc000002": 2,
            "aabbcc000003": 3,
            "aabbcc000004": 4,
        }

    def test_o_numero_publicado_e_o_da_fila_de_chegada(self) -> None:
        """O que o `state_full`, a GUI e a CLI leem — 1..4 pela FILA."""
        assert montar_a_mesa_de_15_08().player_indexes() == FILA

    def test_a_barra_acende_o_numero_que_o_daemon_publica(
        self, raiz_leds: Path
    ) -> None:
        """A mordida: escreve as quatro barras e lê as quatro de volta.

        Um por um, nos QUATRO — o defeito de 15/08 acertava o primário e
        errava os outros três, então um teste de um jogador só passaria com a
        cura arrancada.
        """
        coop = montar_a_mesa_de_15_08()
        publicado = coop.player_indexes()
        for mac, numero in coop.numeros_de_jogador().items():
            acender(mac, numero)
        aceso = {mac: numero_aceso(mac) for mac in FILA}
        assert aceso == publicado, (
            f"o desenho aceso discorda do número publicado: "
            f"aceso={aceso} publicado={publicado}"
        )
        # E os dois são a fila de chegada, não outra ordem qualquer.
        assert aceso == FILA

    def test_nenhum_par_de_controles_acende_o_mesmo_desenho(
        self, raiz_leds: Path
    ) -> None:
        """O caso do número DUPLICADO, proibido explicitamente.

        Dois controles com o mesmo desenho é o defeito que a pessoa lê como
        "não sei qual é qual" — pior que um número trocado, porque nem
        contando dá para desempatar. `None` (padrão de ninguém) entra na
        conta: dois controles apagados também são dois iguais.
        """
        coop = montar_a_mesa_de_15_08()
        for mac, numero in coop.numeros_de_jogador().items():
            acender(mac, numero)
        donos: dict[int | None, list[str]] = {}
        for mac in FILA:
            donos.setdefault(numero_aceso(mac), []).append(mac)
        repetidos = {n: macs for n, macs in donos.items() if len(macs) > 1}
        assert not repetidos, f"desenho repetido entre controles: {repetidos}"
        assert sorted(d for d in donos if d is not None) == [1, 2, 3, 4]

    def test_o_desenho_de_cada_numero_e_o_canonico_da_sony(
        self, raiz_leds: Path
    ) -> None:
        """Os quatro desenhos oficiais, conferidos no nó do sysfs.

        1=`[3]`, 2=`[2,4]`, 3=`[1,3,5]`, 4=`[1,2,4,5]` — a tabela contra a
        qual a medição de 01h00 foi decodificada. Sem isto, um erro no
        `player_led_pattern` faria os testes acima concordarem entre si e
        divergirem do aparelho.
        """
        coop = montar_a_mesa_de_15_08()
        for mac, numero in coop.numeros_de_jogador().items():
            acender(mac, numero)
        raiz = raiz_leds / "leds"
        oficiais = {1: [3], 2: [2, 4], 3: [1, 3, 5], 4: [1, 2, 4, 5]}
        for mac, esperado in FILA.items():
            acesos = [
                n
                for n in range(1, 6)
                if int(
                    (raiz / f"{PREFIXO[mac]}:white:player-{n}" / "brightness")
                    .read_text()
                    .strip()
                )
            ]
            assert acesos == oficiais[esperado], (
                f"{mac} deveria acender o desenho do jogador {esperado}"
            )


class TestNumeroRepetidoEProibido:
    """Dois controles com o MESMO desenho — o estado que não pode existir.

    O caso que a mesa de 15/08 quase produziu e que a memória desta casa já
    viu ("os dois controles aparecem como player 1"): número repetido não vem
    de dois números trocados, vem de um controle SEM LUGAR NA FILA caindo no
    `fallback` — e o `fallback` é o `player_index` do co-op, que vive no outro
    espaço de numeração e colide sem avisar.

    A mesa aqui é a mínima que produz a colisão: o backend elegeu como
    primário o SEGUNDO da fila (colocação 2) e o co-op promoveu primeiro um
    controle que nunca foi registrado — cujo `player_index` é, justamente, 2.
    """

    def montar(self) -> CoopManager:
        registro = ControllerIdentityRegistry()
        for mac in (FILA1_PRIMARIO, FILA2, FILA3):
            registro.slot_for(mac)
        registro.sync_connected([FILA1_PRIMARIO, FILA2, FILA3])
        coop = CoopManager.__new__(CoopManager)
        # primário = o SEGUNDO da fila (ordem de enumeração do hidapi)
        coop._daemon = _DaemonFalso(registro, FILA2)  # type: ignore[assignment]
        coop._players = {
            mac: _SecondaryPlayer(
                identity=mac,
                evdev_path=f"/dev/input/event{300 + i}",
                reader=None,  # type: ignore[arg-type]
                player_index=indice,
                vpad=object(),  # type: ignore[arg-type]
            )
            # ordem de promoção: o sem-fila primeiro, e por isso ele fica com
            # o menor `player_index` livre — 2, o mesmo número do primário.
            for i, (mac, indice) in enumerate(
                ((SEM_FILA, 2), (FILA1_PRIMARIO, 3), (FILA3, 4))
            )
        }
        return coop

    def test_o_sem_fila_colide_com_o_primario_no_papel(self) -> None:
        """Ancoragem: sem a guarda, os dois pediriam o número 2.

        O primário está em 2 pela fila; o sem-fila cai no `fallback`, que é
        `player_index=2`. É a colisão inteira, em dois inteiros.
        """
        coop = self.montar()
        registro = coop._daemon.identity_registry  # type: ignore[attr-defined]
        assert registro.slot_for(FILA2, assign=False) == 2
        assert registro.slot_for(SEM_FILA, assign=False) is None
        assert coop._players[SEM_FILA].player_index == 2

    def test_ninguem_acende_o_desenho_de_outro(self, raiz_leds: Path) -> None:
        """A mordida do duplicado, lida no sysfs — cinco lâmpadas, cinco donos."""
        coop = self.montar()
        numeros = coop.numeros_de_jogador()
        for mac, numero in numeros.items():
            acender(mac, numero)
        donos: dict[int | None, list[str]] = {}
        for mac in numeros:
            donos.setdefault(numero_aceso(mac), []).append(mac)
        repetidos = {n: macs for n, macs in donos.items() if len(macs) > 1}
        assert not repetidos, (
            f"dois controles acendem o mesmo desenho: {repetidos} "
            f"(mesa inteira: {numeros})"
        )

    def test_o_numero_publicado_tambem_nao_repete(self) -> None:
        """A mesma proibição do lado do rótulo — publicado e aceso são um só."""
        coop = self.montar()
        publicado = coop.player_indexes()
        assert len(set(publicado.values())) == len(publicado), publicado
        assert publicado == coop.numeros_de_jogador()


class TestQuandoNaoHaFilaNadaMuda:
    """Sem `identity_registry` o comportamento histórico fica de pé.

    FakeController, backend legado e dublê de teste não têm fila; a cura não
    pode inventar número para eles. É o mesmo `fallback` que `_numero_exibido`
    já usava — e a garantia de que a mordida acima é sobre a FILA, não sobre
    ter trocado uma constante por outra.
    """

    def test_o_fallback_e_o_player_index_do_coop(self) -> None:
        coop = CoopManager.__new__(CoopManager)

        class _SemRegistro:
            controller = _ControllerFalso(FILA1_PRIMARIO)

        coop._daemon = _SemRegistro()  # type: ignore[assignment]
        coop._players = {
            mac: _SecondaryPlayer(
                identity=mac,
                evdev_path=f"/dev/input/event{200 + i}",
                reader=None,  # type: ignore[arg-type]
                player_index=i + 2,
                vpad=object(),  # type: ignore[arg-type]
            )
            for i, mac in enumerate(ORDEM_DE_PROMOCAO)
        }
        assert coop.player_indexes() == {
            FILA1_PRIMARIO: 1,
            FILA4: 2,
            FILA2: 3,
            FILA3: 4,
        }


# --- o casamento card <-> vpad, que a mudança de fonte podia cruzar ---------
#
# `controller_card._bloco_do_vpad` (dono ÚNICO do casamento) acha o vpad de um
# controle comparando `controllers[].player` com `rumble_ff.per_vpad[].player`.
# Enquanto o número publicado ERA o `player_index`, os dois lados coincidiam
# por construção. Com a fila de chegada como fonte, o `per_vpad` tem de mudar
# de fonte JUNTO — senão o card de um controle passa a mostrar a telemetria do
# vpad de OUTRO, que é pior que não mostrar nada.


class _ControllerDeQuatro(FakeController):
    """FakeController que ainda anuncia os quatro físicos e o primário."""

    def __init__(self) -> None:
        super().__init__(transport="bt")
        self.primary_uniq = FILA1_PRIMARIO

    def describe_controllers(self) -> list[dict[str, object]]:
        return [
            {
                "index": i,
                "connected": True,
                "transport": "bt",
                "is_primary": mac == FILA1_PRIMARIO,
                "uniq": mac,
            }
            # a ordem da lista é a de ENUMERAÇÃO do backend, de propósito
            # diferente da fila: é ela que enganava a GUI antes do LEIGO-01b.
            for i, mac in enumerate([FILA1_PRIMARIO, *ORDEM_DE_PROMOCAO])
        ]


def _vpad_ns(player: int) -> SimpleNamespace:
    return SimpleNamespace(
        backend="uhid",
        flavor="dualsense",
        ff_supported=True,
        ff_play_count=0,
        output_count=0,
        trigger_replicas=0,
        lightbar_replicas=0,
        player_led_replicas=0,
        ff_last_sent=(0, 0),
        motion_streaming=False,
        player=player,
    )


@pytest.fixture
def perfis_isolados(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from hefesto_dualsense4unix.profiles import loader as loader_module

    alvo = tmp_path / "profiles"
    alvo.mkdir()
    monkeypatch.setattr(loader_module, "profiles_dir", lambda ensure=False: alvo)
    return alvo


@pytest.fixture
async def servidor_da_mesa_cheia(tmp_path: Path, perfis_isolados: Path) -> Any:
    """`IpcServer` vivo com a mesa de 15/08: co-op real + fila real."""
    from unittest.mock import MagicMock

    from hefesto_dualsense4unix.cli.ipc_client import IpcClient  # noqa: F401
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    fc = _ControllerDeQuatro()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)

    coop = montar_a_mesa_de_15_08()
    registro = coop._daemon.identity_registry  # type: ignore[attr-defined]
    for jogador in coop._players.values():
        jogador.vpad = _vpad_ns(jogador.player_index)  # type: ignore[assignment]

    daemon = MagicMock()
    daemon._last_state = None
    daemon.controller = fc
    daemon.identity_registry = registro
    daemon.external_registry = None
    daemon.config = MagicMock(
        coop_enabled=True,
        mouse_emulation_enabled=False,
        mouse_speed=6,
        mouse_scroll_speed=1,
        rumble_policy="balanceado",
        rumble_policy_custom_mult=0.7,
        rumble_active=None,
    )
    daemon._gamepad_device = _vpad_ns(1)
    daemon._motion_reader = None
    daemon._coop_manager = coop
    coop._daemon = daemon  # o co-op passa a ler o daemon de verdade

    socket_path = tmp_path / "hefesto-dualsense4unix.sock"
    server = IpcServer(
        controller=fc,
        store=store,
        profile_manager=manager,
        socket_path=socket_path,
        daemon=daemon,
    )
    await server.start()
    try:
        yield socket_path
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_o_card_acha_o_vpad_do_proprio_controle(
    servidor_da_mesa_cheia: Any,
) -> None:
    """Os dois lados do casamento saem da mesma fonte — e o card não cruza.

    Morde de duas formas: o conjunto de números publicados tem de ser o mesmo
    dos vpads (senão algum card fica órfão), e o casamento tem de ser uma
    BIJEÇÃO (senão dois cards leem o mesmo bloco).
    """
    from hefesto_dualsense4unix.cli.ipc_client import IpcClient

    async with IpcClient.connect(servidor_da_mesa_cheia) as client:
        estado = await client.call("daemon.state_full")

    controles = estado["controllers"]
    per_vpad = estado["rumble_ff"]["per_vpad"]
    numeros = {c["uniq"]: c["player"] for c in controles}
    assert numeros == FILA, numeros
    # cada controle publica o mesmo número que o seu `player_slot` — a fila.
    assert {c["uniq"]: c["player_slot"] for c in controles} == FILA
    dos_vpads = sorted(item["player"] for item in per_vpad)
    assert dos_vpads == sorted(numeros.values()), (
        f"card órfão ou cruzado: controles={numeros} vpads={dos_vpads}"
    )
    assert len(set(dos_vpads)) == len(dos_vpads), dos_vpads
