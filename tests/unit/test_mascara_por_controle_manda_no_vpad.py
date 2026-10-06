"""A MÁSCARA POR CONTROLE CHEGOU AO VPAD — a corrente ligada, medida ponta a ponta.

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
from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
    _zerar_registro_de_mascaras,
    registro_de_mascaras,
)
from hefesto_dualsense4unix.integrations import virtual_pad as vp
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    DUALSENSE_VENDOR,
    XBOX360_VENDOR,
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
    """``config_dir`` em tmp + registro do processo ZERADO antes e depois."""
    from hefesto_dualsense4unix.utils import xdg_paths

    target = tmp_path / "config"

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    _zerar_registro_de_mascaras()
    yield target
    _zerar_registro_de_mascaras()


@pytest.fixture(autouse=True)
def _sem_no_de_kernel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nenhum `/dev/uinput` e nenhum `/dev/uhid` são tocados nesta bateria."""
    monkeypatch.setattr(UinputGamepad, "start", lambda self: True)


def _cria(flavor: str | None, identity: str | None) -> Any:
    """Um vpad pela factory REAL, sem uhid (`allow_uhid=False`, VPAD-08)."""
    pad = make_virtual_pad(flavor, identity=identity, allow_uhid=False)
    assert pad is not None, "a factory devolveu None — o stub do start caiu"
    return pad


def test_dois_controles_com_mascaras_diferentes_nascem_com_flavors_diferentes() -> None:
    """A mordida. Mesma sessão, mesma chamada, DOIS resultados — pela escolha.

    É a decisão de produto funcionando: o P2 marcado `dualsense` aparece como
    DualSense no jogo enquanto o P1 marcado `xbox` aparece como Xbox 360, e a
    máscara da sessão (`"xbox"`, o argumento posicional) é só o padrão herdado.
    """
    registro_de_mascaras().set_mask(MAC_P1, "xbox")
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    pad1 = _cria("xbox", UNIQ_P1)
    pad2 = _cria("xbox", UNIQ_P2)

    assert pad1.flavor == "xbox"
    assert pad2.flavor == "dualsense"
    assert pad1.flavor != pad2.flavor, (
        "dois controles com máscaras DIFERENTES gravadas nasceram com o MESMO "
        "flavor — a identidade não chegou ao `mascara_efetiva`"
    )
    assert (pad1.vendor, pad2.vendor) == (XBOX360_VENDOR, DUALSENSE_VENDOR)
    assert pad1.product != pad2.product
    assert pad1.name != pad2.name


def test_arrancar_a_identidade_faz_os_dois_nascerem_iguais() -> None:
    """A MORDIDA, provada por arrancar a cura — com os números."""
    registro_de_mascaras().set_mask(MAC_P1, "xbox")
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

    com = {_cria("xbox", UNIQ_P1).flavor, _cria("xbox", UNIQ_P2).flavor}
    sem = {_cria("xbox", None).flavor, _cria("xbox", None).flavor}

    assert com == {"xbox", "dualsense"}, f"com a identidade: {sorted(com)}"
    assert len(com) == 2
    assert sem == {"xbox"}, f"sem a identidade: {sorted(sem)}"
    assert len(sem) == 1, (
        "sem `identity` os dois vpads TÊM de nascer iguais — se este número "
        "for 2, a resolução está vazando de outro lugar e a régua não mede o "
        "que promete"
    )


def test_quem_nao_escolheu_herda_a_mascara_do_jogo_mesmo_com_a_mesa_marcada() -> None:
    """O contrato do padrão herdado, com a mesa toda marcada em volta."""
    registro_de_mascaras().set_mask(MAC_P1, "xbox")
    registro_de_mascaras().set_mask(MAC_P2, "xbox")

    assert _cria("dualsense", UNIQ_P3).flavor == "dualsense"
    assert _cria("dualsense", UNIQ_P1).flavor == "xbox"


def test_o_gate_do_uhid_recebe_a_mascara_efetiva_e_nao_a_do_jogo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A armadilha que `external_mask.py:59-68` descreveu, medida.

    Um jogador que escolheu `dualsense` numa sessão `xbox`: o `_try_uhid` tem
    de receber `"dualsense"`, senão o gate dele veta o uhid e o jogador cai no uinput COM máscara
    DualSense — o par
    degradado em que a vibração do jogo morre. O defeito seria invisível aqui
    (o `flavor` sai certo!) e apareceria só com o controle na mão, como
    "escolhi DualSense e o jogo parou de vibrar".

    Com o `key = normalize_flavor(flavor)` que estava nesta linha até 29/08, o
    valor abaixo seria `"xbox"`.
    """
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")
    recebido: list[str] = []

    def _espiao(flavor: str, **kwargs: Any) -> tuple[None, None]:
        recebido.append(flavor)
        return None, None

    monkeypatch.setattr(vp, "_try_uhid", _espiao)

    pad = make_virtual_pad("xbox", identity=UNIQ_P2, allow_uhid=True)

    assert recebido == ["dualsense"], (
        f"o gate do uhid recebeu {recebido!r} — se for ['xbox'], a resolução "
        "está DEPOIS da escolha do backend e o jogador cai no par degradado "
        "(uinput + máscara DualSense = rumble do jogo morto)"
    )
    assert pad is not None
    assert pad.flavor == "dualsense"


def test_o_uhid_e_vetado_para_quem_escolheu_xbox_numa_sessao_dualsense(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O outro lado da armadilha: a escolha também diz NÃO.

    Sessão `dualsense`, aparelho marcado `xbox`. O `_try_uhid` recebe `"xbox"`
    e devolve `(None, None)` — uinput por DESIGN, não degradação. Se recebesse
    a máscara do jogo, subiria um DualSense Edge REAL no kernel para um
    controle que o usuário pediu para aparecer como Xbox.
    """
    registro_de_mascaras().set_mask(MAC_P1, "xbox")
    recebido: list[str] = []

    def _espiao(flavor: str, **kwargs: Any) -> tuple[None, None]:
        recebido.append(flavor)
        return None, None

    monkeypatch.setattr(vp, "_try_uhid", _espiao)

    pad = make_virtual_pad("dualsense", identity=UNIQ_P1, allow_uhid=True)

    assert recebido == []
    assert pad is not None
    assert pad.flavor == "xbox"
    assert getattr(pad, "fallback_motivo", None) is None


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
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")

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
    assert flavors == ["dualsense", "xbox"], (
        "o P2 escolheu dualsense e o P3 herdou a sessão xbox — se os dois "
        "saírem iguais a identidade não chegou ao co-op"
    )
    assert not any(v.stopped for v in criados), (
        "nenhum vpad podia ter sido parado: parar é a primeira metade da "
        "recriação, e ela não pode acontecer fora do Aplicar"
    )


def test_arrancar_o_ficou_para_tras_faz_o_churn_aparecer(
    coop: CoopManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cura arrancada, com os números — e o custo por segundo."""
    registro_de_mascaras().set_mask(MAC_P2, "dualsense")
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.external_mask.vpad_ficou_para_tras",
        lambda flavor_do_vpad, identity, flavor_do_jogo, **_kw: (
            flavor_do_vpad != flavor_do_jogo
        ),
    )
    voltas = 20

    for _ in range(voltas):
        coop.sync(force=True)

    criados = len(_VpadDeMentira.criados)
    assert criados > 2, (
        "com a cura arrancada a régua TINHA de acusar churn e não acusou — "
        f"{criados} criações em {voltas} voltas. Se este número for 2, o "
        "teste de cima não morde e a corrente não está sendo medida."
    )
    assert criados >= voltas, (
        f"o churn é por TIQUE: esperado ~{voltas + 1} criações, medido "
        f"{criados}. Menos que uma por volta significa que o laço não está "
        "chegando na comparação de flavor."
    )
    do_p3 = [v for v in _VpadDeMentira.criados if v.identity == UNIQ_P3]
    assert len(do_p3) == 1, f"o P3 (sem escolha) foi recriado {len(do_p3)}x"


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

    registro_de_mascaras().set_mask(MAC_P1, "dualsense")

    primeiro = start_gamepad_emulation_desfecho(p1, "xbox", origin="manual")
    assert primeiro == EMU_APLICADO
    device = p1._gamepad_device
    assert device.flavor == "dualsense", (
        "o vpad do P1 nasceu com a máscara da SESSÃO — a identidade do "
        "primário não chegou à factory"
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


def test_o_aplicar_recria_quando_a_escolha_dela_muda(p1: Any) -> None:
    """E o Aplicar CONTINUA aplicando — a decisão de produto vale no gesto.
    (D-A-MASCARA-POR-CONTROLE-VALE-NO-APLICAR)
    """
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
        EMU_APLICADO,
        start_gamepad_emulation_desfecho,
    )

    registro_de_mascaras().set_mask(MAC_P1, "dualsense")
    start_gamepad_emulation_desfecho(p1, "xbox", origin="manual")
    primeiro = p1._gamepad_device
    assert primeiro.flavor == "dualsense"

    registro_de_mascaras().set_mask(MAC_P1, "xbox")
    assert start_gamepad_emulation_desfecho(p1, "xbox", origin="manual") == EMU_APLICADO

    assert len(_VpadDeMentira.criados) == 2
    assert primeiro.stopped, "o vpad anterior tinha de ser parado na troca"
    assert p1._gamepad_device.flavor == "xbox"


def test_a_escolha_do_aparelho_nao_vira_a_mascara_da_sessao(p1: Any) -> None:
    """SÃO DUAS MÁSCARAS, e confundi-las destrói dado dela."""
    from hefesto_dualsense4unix.daemon.subsystems.gamepad import (
        start_gamepad_emulation_desfecho,
    )

    registro_de_mascaras().set_mask(MAC_P1, "dualsense")
    start_gamepad_emulation_desfecho(p1, "xbox", origin="manual")

    assert p1._gamepad_device.flavor == "dualsense"
    assert p1.config.gamepad_flavor == "xbox", (
        "a escolha do APARELHO vazou para a máscara da SESSÃO — o próximo "
        "`save_gamepad_emulation` gravaria a escolha errada em disco"
    )


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
    registro_de_mascaras().set_mask(MAC_P1, "dualsense")

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

    registro_de_mascaras().set_mask(MAC_P1, "dualsense")
    daemon = _daemon_do_p1(None, "xbox")

    assert primary_identity(daemon) is None
    start_gamepad_emulation_desfecho(daemon, "xbox", origin="manual")

    assert daemon._gamepad_device.flavor == "xbox"
    assert daemon._gamepad_device.identity is None
