"""A MÁSCARA POR CONTROLE CHEGOU AO VPAD — a corrente ligada, medida ponta a ponta.

NOTA DATADA, 27/10/2026: desde a D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES a máscara é
o modo único, igual para todos, e as réguas da DIFERENÇA entre controles (os itens 1, 2 e 5
abaixo) saíram: não há diferença a medir. Ficam a identidade chegando à fábrica, o vpad que
não se recria fora do gesto (3) e o que ficou para trás de verdade (4).

Decisão, 29/08/2026: ``D-A-MASCARA-POR-CONTROLE-VALE-NO-APLICAR`` — *"a
máscara por controle vale ao clicar em Aplicar, mesmo com jogo aberto"*.

O registro por aparelho existe desde 15/08 (``daemon/subsystems/external_mask.py``,
arquivo próprio ``controller_masks.json``) e os DOIS backends de vpad já sabiam
consultá-lo (``uinput_gamepad.for_flavor``, ``uhid_gamepad.for_flavor``). O que
faltava era **um parâmetro**: ``make_virtual_pad`` não aceitava ``identity``, e
os dois chamadores não a passavam — o MAC do jogador estava literalmente na
linha de baixo da chamada, no ``rumble_sink`` (``coop.py``). Ligado em
29/08/2026.

O QUE ESTA BATERIA MEDE, e por que cada peça existe
----------------------------------------------------

1. **A MORDIDA** — dois controles com máscaras DIFERENTES gravadas nascem com
   vpads de flavors diferentes. Com ``identity`` arrancado da chamada os dois
   nascem IGUAIS, e o teste da mordida mostra isso com os números na mão
   (``test_arrancar_a_identidade_faz_os_dois_nascerem_iguais``).

2. **A ARMADILHA que ``external_mask.py:59-68`` deixou escrita** para quem
   fosse escrever este degrau: a máscara efetiva tem de ser resolvida **ANTES**
   de escolher o backend. O gate do ``_try_uhid`` decide pela máscara que RECEBE; recebendo a do
   jogo, um jogador que
   escolheu ``dualsense`` numa sessão ``xbox`` teria o uhid vetado e cairia no
   uinput com máscara DualSense — o par degradado em que a vibração do jogo
   MORRE (VPAD-05 / SPRINT-GAME-RUMBLE-01). É um defeito que só aparece com o
   controle na mão; aqui ele aparece numa asserção.

3. **O VPAD NÃO É RECRIADO FORA DO APLICAR** — o coração do risco desta
   entrega. Trocar a máscara destrói e recria o vpad, e há medição ao vivo
   (20:15 de 2026-07-18) de que isso invalida o handle do jogo aberto: a Steam
   nunca reabre o hidraw do vpad do P1. A decisão de produto aceita esse preço **no
   Aplicar**; o que não pode existir é recriação em NENHUM outro momento. Duas
   réguas, porque são dois laços diferentes:

   - ``test_duzentos_tiques_do_coop_nao_recriam_o_vpad_de_quem_escolheu`` — o
     tique do co-op, 200 voltas, contando criações;
   - ``test_cinquenta_aplicares_identicos_nao_recriam_o_vpad_do_p1`` — o
     ``start_gamepad_emulation``, 50 applies, contando criações e comparando a
     IDENTIDADE do objeto.

   **Duzentas voltas, e não uma.** Regra desta casa, aprendida hoje: *uma régua
   que roda o tique UMA VEZ mede um instante, não um comportamento* — foi assim
   que uma leva de 29/08 introduziu uma regressão visível só aos 181 segundos,
   com 67 testes verdes. Uma volta só passaria com o defeito de churn vivo,
   porque na PRIMEIRA volta o vpad ainda não existe para ser derrubado.

4. **A CURA DA SPRINT-GAME-RUMBLE-01 SOBREVIVE** — o vpad que ficou para trás
   de verdade (a máscara mudou e ele nasceu na anterior) AINDA é recriado.
   Sem isto, P2+ ficariam presos no flavor antigo, com rumble morto e prompts
   divergentes do P1. Trocar um defeito por outro não é cura.

5. **A MÁSCARA DA SESSÃO NÃO É CONTAMINADA** pela escolha de um aparelho. São
   duas máscaras e confundi-las destrói dado dela: ``config.gamepad_flavor`` e
   o ``save_gamepad_emulation`` são a máscara do JOGO; a escolha do aparelho
   mora no arquivo próprio. Carimbar uma como a outra apagaria a escolha do usuário
   do disco — o defeito do Sackboy (22/08) pelo avesso — e ainda contaminaria
   todo secundário, que herda ``config.gamepad_flavor`` no ``_flavor()``.

Bancada hermética, no mesmo padrão de ``test_mascara_por_jogador_01.py``: faixa
forjada ``aa:bb:cc:00:00:*`` (regra da casa — nada de MAC real em arquivo
versionado), ``config_dir`` em ``tmp_path``, **nenhum** ``/dev/uinput``,
**nenhum** ``/dev/uhid``, nenhum aparelho, nenhum GTK.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    UinputGamepad,
)
from hefesto_dualsense4unix.integrations.virtual_pad import make_virtual_pad

MAC_P1 = "aa:bb:cc:00:00:01"
MAC_P2 = "aa:bb:cc:00:00:02"
MAC_P3 = "aa:bb:cc:00:00:03"

UNIQ_P1 = "aabbcc000001"
UNIQ_P2 = "aabbcc000002"
UNIQ_P3 = "aabbcc000003"

VOLTAS = 200
APLICARES = 50


@pytest.fixture(autouse=True)
def _hermetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``config_dir`` em tmp."""
    from hefesto_dualsense4unix.utils import xdg_paths

    target = tmp_path / "config"

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    return target


@pytest.fixture(autouse=True)
def _sem_no_de_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum `/dev/uinput` e nenhum `/dev/uhid` são tocados nesta bateria."""
    monkeypatch.setattr(UinputGamepad, "start", lambda self: True)


def _cria(flavor: str | None, identity: str | None) -> Any:
    """Um vpad pela factory REAL, sem uhid (`allow_uhid=False`, VPAD-08)."""
    pad = make_virtual_pad(flavor, identity=identity, allow_uhid=False)
    assert pad is not None, "a factory devolveu None — o stub do start caiu"
    return pad


@pytest.mark.parametrize("modo", ["dualsense", "xbox", "nintendo"])
def test_dois_controles_nascem_no_modo_unico(modo: str) -> None:
    """A identidade chega à fábrica e não muda a máscara: os dois nascem no modo."""
    p1 = _cria(modo, MAC_P1)
    p2 = _cria(modo, MAC_P2)
    assert (p1.flavor, p2.flavor) == (modo, modo)


class _VpadDeMentira:
    """Vpad falso — nunca um nó de kernel. Conta as criações na classe."""

    criados: ClassVar[list[_VpadDeMentira]] = []

    def __init__(self, flavor: str, identity: str | None) -> None:
        self.flavor = flavor
        self.identity = identity
        self.stopped = False
        type(self).criados.append(self)

    def stop(self) -> None:
        self.stopped = True

    def forward_analog(self, **kw: int) -> None:
        return

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        return

    def pump_ff(self) -> None:
        return


class _ReaderDeMentira:
    """Reader evdev falso (mesmo contrato do `test_coop_player_leds`)."""

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.target_uniq = target_uniq
        self.grab_state = "off"
        self.stopped = False

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        self.grab_state = "held" if grab else "off"
        return True

    def stop(self) -> None:
        self.stopped = True

    def snapshot(self) -> Any:
        return SimpleNamespace(
            lx=128, ly=128, rx=128, ry=128, l2_raw=0, r2_raw=0,
            buttons_pressed=frozenset(),
        )


@pytest.fixture()
def coop(monkeypatch: pytest.MonkeyPatch) -> CoopManager:
    """Um `CoopManager` REAL com dois secundários na mesa, sem tocar em nada."""
    _VpadDeMentira.criados = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll",
        lambda self: True,
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _ReaderDeMentira
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: {UNIQ_P1: "/dev/input/event90",
                 UNIQ_P2: "/dev/input/event91",
                 UNIQ_P3: "/dev/input/event92"},
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
        lambda flavor, *, identity=None, **_kw: _VpadDeMentira(
            _mascara_efetiva_de_teste(identity, flavor),
            identity,
        ),
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {}
    )
    monkeypatch.setattr(
        CoopManager, "_calibration_pronta", lambda self, identity: (True, None)
    )
    daemon = SimpleNamespace(
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="xbox"),
        _gamepad_device=object(),
        controller=SimpleNamespace(primary_uniq=UNIQ_P1),
        _coop_manager=None,
    )
    return CoopManager(daemon)  # type: ignore[arg-type]


def _mascara_efetiva_de_teste(identity: str | None, flavor: str | None) -> str:
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import mascara_efetiva

    return mascara_efetiva(identity, flavor)


def test_duzentos_tiques_do_coop_nao_recriam_o_vpad_de_quem_escolheu(
    coop: CoopManager,
) -> None:
    """O CORAÇÃO DO RISCO: 200 voltas, e as criações continuam sendo 2."""

    for _ in range(VOLTAS):
        coop.sync(force=True)

    criados = _VpadDeMentira.criados
    flavors = sorted(v.flavor for v in criados)
    assert len(criados) == 2, (
        f"{VOLTAS} tiques criaram {len(criados)} vpads (esperado: 2, um por "
        f"secundário). Flavors criados: {flavors}. Mais que 2 significa "
        "teardown+respawn em tique quieto — a recriação que a R-04 mediu como "
        "'abri o jogo e o controle morreu no meio da partida'."
    )
    assert flavors == ["xbox", "xbox"], "os dois secundários nascem no modo único"
    assert not any(v.stopped for v in criados), (
        "nenhum vpad podia ter sido parado: parar é a primeira metade da "
        "recriação, e ela não pode acontecer fora do Aplicar"
    )


def test_a_mascara_que_ficou_para_tras_de_verdade_ainda_recria(
    coop: CoopManager,
) -> None:
    """A cura da SPRINT-GAME-RUMBLE-01 SOBREVIVE — trocar defeito por defeito não vale."""
    for _ in range(5):
        coop.sync(force=True)
    antes = len(_VpadDeMentira.criados)
    assert antes == 2

    coop._daemon.config.gamepad_flavor = "dualsense"  # type: ignore[attr-defined]
    coop.sync(force=True)

    criados = _VpadDeMentira.criados
    assert len(criados) == 4, (
        f"a máscara do jogo mudou e só {len(criados) - antes} vpad(s) foram "
        "recriados — os dois secundários ficariam presos no flavor antigo"
    )
    assert all(v.stopped for v in criados[:2])
    assert [v.flavor for v in criados[2:]] == ["dualsense", "dualsense"]

    coop.sync(force=True)
    coop.sync(force=True)
    assert len(_VpadDeMentira.criados) == 4


class _ControleComMac:
    """Backend mínimo com `primary_uniq` — o que `primary_identity` lê.

    Sem `hidraw_path` de propósito: é a declaração "sem uhid" do VPAD-08, e
    garante que nenhum DualSense Edge real seja registrado no kernel desta
    máquina por causa de um teste.
    """

    def __init__(self, uniq: str | None) -> None:
        self.primary_uniq = uniq

    def set_grab(self, grab: bool) -> bool:
        return True

    def set_rumble(self, weak: int, strong: int) -> None:
        return


def _daemon_do_p1(uniq: str | None, flavor: str) -> Any:
    return SimpleNamespace(
        config=SimpleNamespace(
            gamepad_flavor=flavor,
            gamepad_emulation_enabled=False,
            coop_enabled=False,
            rumble_active=(0, 0),
        ),
        controller=_ControleComMac(uniq),
        _gamepad_device=None,
        _mouse_device=None,
        _coop_manager=None,
        store=None,
    )


@pytest.fixture()
def p1(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Bancada do `start_gamepad_emulation_desfecho` sem tocar em disco nem kernel."""
    _VpadDeMentira.criados = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
        lambda flavor, *, identity=None, **_kw: _VpadDeMentira(
            _mascara_efetiva_de_teste(identity, flavor), identity
        ),
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env",
        lambda daemon: None,
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_gamepad_emulation",
        lambda *a, **k: None,
    )
    return _daemon_do_p1(UNIQ_P1, "xbox")


def test_cinquenta_aplicares_identicos_nao_recriam_o_vpad_do_p1(p1: Any) -> None:
    """A OUTRA metade do risco: o Aplicar repetido, com o P1 marcado."""
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
        EMU_APLICADO,
        EMU_JA_ESTAVA,
        start_gamepad_emulation_desfecho,
    )

    primeiro = start_gamepad_emulation_desfecho(p1, "xbox", origin="manual")
    assert primeiro == EMU_APLICADO
    device = p1._gamepad_device
    assert (device.flavor, device.identity) == ("xbox", UNIQ_P1), (
        "o vpad do P1 nasceu fora do modo, ou sem a identidade do primário"
    )

    desfechos = [
        start_gamepad_emulation_desfecho(p1, "xbox", origin="manual")
        for _ in range(APLICARES)
    ]

    assert set(desfechos) == {EMU_JA_ESTAVA}, (
        f"{APLICARES} applies idênticos deram {sorted(set(desfechos))} — "
        "qualquer 'aplicado' aqui é um vpad destruído e recriado com o jogo "
        "possivelmente aberto"
    )
    assert len(_VpadDeMentira.criados) == 1, (
        f"{APLICARES} applies criaram {len(_VpadDeMentira.criados)} vpads "
        "(esperado: 1)"
    )
    assert p1._gamepad_device is device, "o objeto do vpad TROCOU sem ninguém pedir"
    assert not device.stopped


def test_o_aplicar_recria_quando_o_modo_muda(p1: Any) -> None:
    """E o gesto CONTINUA aplicando (D-A-MASCARA-POR-CONTROLE-VALE-NO-APLICAR)."""
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
        EMU_APLICADO,
        start_gamepad_emulation_desfecho,
    )

    start_gamepad_emulation_desfecho(p1, "dualsense", origin="manual")
    primeiro = p1._gamepad_device
    assert primeiro.flavor == "dualsense"

    assert start_gamepad_emulation_desfecho(p1, "xbox", origin="manual") == EMU_APLICADO

    assert len(_VpadDeMentira.criados) == 2
    assert primeiro.stopped, "o vpad anterior tinha de ser parado na troca"
    assert p1._gamepad_device.flavor == "xbox"


def test_o_que_o_disco_recebe_e_a_mascara_do_jogo(
    p1: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mesma verdade, medida no ponto onde o dano seria permanente."""
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    gravado: list[tuple[bool, str]] = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_gamepad_emulation",
        lambda ativo, flavor=None: gravado.append((ativo, str(flavor))),
    )
    gp.start_gamepad_emulation_desfecho(p1, "xbox", origin="manual")

    assert gravado == [(True, "xbox")], (
        f"o disco recebeu {gravado!r} — se for 'dualsense', a escolha de "
        "máscara dela some no boot seguinte"
    )


def test_sem_mac_do_primario_o_p1_segue_a_sessao(monkeypatch: pytest.MonkeyPatch) -> None:
    """`primary_uniq` None (boot antes do connect, `run.sh --fake`) = máscara do jogo."""
    _VpadDeMentira.criados = []
    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad",
        lambda flavor, *, identity=None, **_kw: _VpadDeMentira(
            _mascara_efetiva_de_teste(identity, flavor), identity
        ),
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env",
        lambda daemon: None,
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.session.save_gamepad_emulation",
        lambda *a, **k: None,
    )
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
        primary_identity,
        start_gamepad_emulation_desfecho,
    )

    daemon = _daemon_do_p1(None, "xbox")

    assert primary_identity(daemon) is None
    start_gamepad_emulation_desfecho(daemon, "xbox", origin="manual")

    assert daemon._gamepad_device.flavor == "xbox"
    assert daemon._gamepad_device.identity is None
