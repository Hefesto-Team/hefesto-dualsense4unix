"""NO-MODO-XBOX-TUDO-FUNCIONA-01 — no modo Xbox, o jogo vê o pad.

A ordem dela, 27/09 à noite: *«tá errado se tiver no modo xbox é pra
literalmente tudo isso funcionar.»* <!-- noqa-acento: citação literal dela -->

O QUE SE MEDIU NA SESSÃO DELA (27/09, `medidas/sessao/G1-…` e `G3-…`): o modo
Xbox com a máscara DualSense fazia o pad «Sony … DualSense Edge» no `uinput`,
sem hidraw, e com a Nintendo o «Pro Controller (Hefesto …)», também sem
hidraw. Sob o Proton o jogo não usa nenhum dos dois: o PRAGMATA segurou só o
mouse e o teclado, e o Future Knight abriu o Pro sem entendê-lo. O Xbox 360
funcionava (L4, 21:17).

A CURA, num dono só: `virtual_pad.mascara_no_jogo`. Com o modo Xbox escolhido,
a fábrica veste todo pad de Xbox 360 (`045e:028e`); o `flavor` do pad continua
sendo a máscara do cartão, que é o que os juízes de recriação comparam.

Os pads nascem pela FÁBRICA de verdade (`make_virtual_pad` e o `UinputGamepad`
real), com um `evdev` de mentira que GRAVA o que o kernel receberia: nome,
VID/PID e capacidades. Nenhum nó de kernel nasce. Os MACs são da faixa forjada.

MORDIDAS (cada classe diz a sua): tire a chamada de `_vestir_o_aparelho` da
fábrica; troque `normalizar_caminho` por `caminho_resolvido` na regra; devolva
ao `UinputGamepad` a tabela e as capacidades pelo `flavor`.

A DÍVIDA QUE FICOU EM 28/09 FECHOU NA ONDA 3: a troca de modo com o pad
Nintendo de pé não o recriava (os juízes comparavam o canal, e não o aparelho).
Os dois juízes perguntam agora a `virtual_pad.o_aparelho_mudou`, juntos, e as
duas réguas que estavam em `xfail(strict=True)` passaram a valer. MORDIDA:
faça `o_aparelho_mudou` devolver `False` e as duas reprovam; tire a pergunta de
UM dos juízes e a régua do laço reprova.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar, NamedTuple

import pytest

from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer
from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
    _zerar_registro_de_mascaras,
    registro_de_mascaras,
    vpad_ficou_para_tras,
)
from hefesto_dualsense4unix.integrations import uhid_gamepad
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    NINTENDO_VENDOR,
    XBOX360_NAME,
    XBOX360_PRODUCT,
    XBOX360_VENDOR,
    UinputGamepad,
)
from hefesto_dualsense4unix.integrations.virtual_pad import (
    CAMINHO_DUALSENSE,
    CAMINHO_XBOX,
    make_virtual_pad,
    mascara_no_jogo,
    motivo_da_degradacao,
)
from hefesto_dualsense4unix.testing.fake_controller import FakeController
from hefesto_dualsense4unix.utils import session as session_mod

#: A mesa forjada da casa: quatro controles, octetos 4 e 5 zerados.
MACS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
MASCARAS = ("dualsense", "xbox", "nintendo")
SONY_VENDOR = 0x054C


class _AbsInfo(NamedTuple):
    value: int
    min: int
    max: int
    fuzz: int
    flat: int
    resolution: int


class _EC:
    """Os códigos reais de `linux/input-event-codes.h` que as três máscaras usam."""

    EV_SYN, EV_KEY, EV_ABS, EV_FF, EV_UINPUT = 0x00, 0x01, 0x03, 0x15, 0x0101
    UI_FF_UPLOAD, UI_FF_ERASE = 1, 2
    ABS_X, ABS_Y, ABS_Z, ABS_RX, ABS_RY, ABS_RZ = 0x00, 0x01, 0x02, 0x03, 0x04, 0x05
    ABS_HAT0X, ABS_HAT0Y = 0x10, 0x11
    BTN_A = BTN_SOUTH = 0x130
    BTN_B = BTN_EAST = 0x131
    BTN_X = BTN_NORTH = 0x133
    BTN_Y = BTN_WEST = 0x134
    BTN_Z = 0x135
    BTN_TL, BTN_TR, BTN_TL2, BTN_TR2 = 0x136, 0x137, 0x138, 0x139
    BTN_SELECT, BTN_START, BTN_MODE = 0x13A, 0x13B, 0x13C
    BTN_THUMBL, BTN_THUMBR = 0x13D, 0x13E
    FF_RUMBLE, FF_PERIODIC, FF_SQUARE, FF_TRIANGLE, FF_SINE, FF_GAIN = (
        0x50, 0x51, 0x58, 0x59, 0x5A, 0x60)


#: As onze teclas e os oito eixos do Xbox 360 (`_capacidades_padrao`), que é o
#: conjunto em que a libSDL2 casa o mapeamento do `xpad`.
TECLAS_DO_XBOX = frozenset({
    _EC.BTN_A, _EC.BTN_B, _EC.BTN_X, _EC.BTN_Y, _EC.BTN_TL, _EC.BTN_TR,
    _EC.BTN_SELECT, _EC.BTN_START, _EC.BTN_MODE, _EC.BTN_THUMBL, _EC.BTN_THUMBR,
})
EIXOS_DO_XBOX = frozenset({
    _EC.ABS_X, _EC.ABS_Y, _EC.ABS_Z, _EC.ABS_RX, _EC.ABS_RY, _EC.ABS_RZ,
    _EC.ABS_HAT0X, _EC.ABS_HAT0Y,
})


class _NoGravado:
    """O `evdev.UInput` sem kernel: guarda o que o kernel registraria e o que se escreve."""

    criados: ClassVar[list[_NoGravado]] = []

    def __init__(self, events: dict[int, list[Any]], **kwargs: Any) -> None:
        self.events = events
        self.kwargs = kwargs
        self.fd = -1  # sem fd de verdade: o fio da vibração não sobe
        self.escritas: list[tuple[int, int, int]] = []
        type(self).criados.append(self)

    @property
    def teclas(self) -> frozenset[int]:
        return frozenset(self.events.get(_EC.EV_KEY, ()))

    @property
    def eixos(self) -> frozenset[int]:
        return frozenset(codigo for codigo, _info in self.events.get(_EC.EV_ABS, ()))

    @property
    def vidpid(self) -> tuple[int, int]:
        return int(self.kwargs["vendor"]), int(self.kwargs["product"])

    def write(self, etype: int, code: int, value: int) -> None:
        self.escritas.append((etype, code, value))

    def syn(self) -> None:
        return

    def close(self) -> None:
        return

    def read_one(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _hermetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """O disco em tmp (o registro de máscaras e o flag) e o registro zerado."""
    from hefesto_dualsense4unix.utils import xdg_paths

    alvo = tmp_path / "config"

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(xdg_paths, "config_dir", _config_dir)
    monkeypatch.setattr(session_mod, "config_dir", _config_dir)
    _zerar_registro_de_mascaras()
    yield
    _zerar_registro_de_mascaras()


@pytest.fixture(autouse=True)
def _evdev_que_grava(monkeypatch: pytest.MonkeyPatch) -> None:
    """A fábrica real com o `uinput` gravado; o `uhid` fora do ar."""
    _NoGravado.criados = []
    mod = types.ModuleType("evdev")
    mod.UInput = _NoGravado  # type: ignore[attr-defined]
    mod.AbsInfo = _AbsInfo  # type: ignore[attr-defined]
    mod.ecodes = _EC  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "evdev", mod)
    monkeypatch.setattr(uhid_gamepad, "uhid_available", lambda: False)


def _no_de(pad: Any) -> _NoGravado:
    no = pad._device
    assert isinstance(no, _NoGravado), "o pad não nasceu pelo `UinputGamepad` real"
    return no


def _pad(mascara: str | None, caminho: str | None, **kw: Any) -> Any:
    pad = make_virtual_pad(mascara, caminho=caminho, **kw)
    assert pad is not None, "a fábrica não entregou pad nenhum"
    return pad


# ===========================================================================
# 1 — a fábrica: no modo Xbox, o aparelho é o Xbox 360
# ===========================================================================


class TestNoModoXboxOAparelhoEOXbox360:
    """MORDIDA: tire a chamada de `_vestir_o_aparelho` de `make_virtual_pad` e
    as máscaras DualSense e Nintendo voltam a registrar `054c:0df2` e
    `057e:2009` no `uinput` — o pad que o jogo não usa."""

    @pytest.mark.parametrize("jogador", [1, 2, 3, 4])
    @pytest.mark.parametrize("mascara", MASCARAS)
    def test_toda_mascara_nasce_xbox_360(self, mascara: str, jogador: int) -> None:
        pad = _pad(mascara, CAMINHO_XBOX, player=jogador)
        try:
            no = _no_de(pad)
            assert no.vidpid == (XBOX360_VENDOR, XBOX360_PRODUCT), (
                f"P{jogador} com a máscara {mascara} no modo Xbox registrou "
                f"{no.vidpid[0]:04x}:{no.vidpid[1]:04x} no uinput, sem hidraw: "
                "é o pad que o PRAGMATA e o Future Knight não usaram"
            )
            assert no.kwargs["name"] == XBOX360_NAME
            assert (no.teclas, no.eixos) == (TECLAS_DO_XBOX, EIXOS_DO_XBOX), (
                "o nó tem o VID/PID do Xbox com as capacidades de outra máscara: "
                "a SDL aplicaria o mapeamento do xpad a botões e eixos trocados"
            )
            assert pad.flavor == mascara, "o eixo da máscara (o cartão) não se perde"
            assert pad.mascara_no_jogo == "xbox"
            assert pad.caminho == CAMINHO_XBOX
            assert motivo_da_degradacao(pad) is None, "o modo Xbox é escolha, não queda"
        finally:
            pad.stop()

    def test_o_cartao_de_cada_controle_nao_escapa_do_modo(self) -> None:
        """Os quatro cartões com máscaras diferentes, a sessão em DualSense: no
        modo Xbox os quatro são Xbox 360, e cada um guarda o seu cartão."""
        cartoes = dict(zip(MACS, ("dualsense", "nintendo", "xbox", "dualsense"), strict=True))
        for mac, mascara in cartoes.items():
            registro_de_mascaras().set_mask(mac, mascara)
        for jogador, (mac, mascara) in enumerate(cartoes.items(), start=1):
            pad = _pad("dualsense", CAMINHO_XBOX, identity=mac, player=jogador)
            try:
                assert _no_de(pad).vidpid == (XBOX360_VENDOR, XBOX360_PRODUCT), mac
                assert pad.flavor == mascara, mac
            finally:
                pad.stop()


class TestForaDoModoXboxNadaMuda:
    """MORDIDA: troque `normalizar_caminho` por `caminho_resolvido` em
    `mascara_no_jogo` e a máscara Nintendo sem modo escolhido (que resolve para
    o caminho Xbox, o produto de antes de 13/09) vira Xbox 360 — a máscara que
    ela pediu em 07/09 some sem ninguém escolher o modo Xbox."""

    @pytest.mark.parametrize("caminho", [None, CAMINHO_DUALSENSE])
    @pytest.mark.parametrize(
        ("mascara", "vendor"),
        [("dualsense", SONY_VENDOR), ("xbox", XBOX360_VENDOR), ("nintendo", NINTENDO_VENDOR)],
    )
    def test_a_mascara_e_o_aparelho(self, caminho: str | None, mascara: str, vendor: int) -> None:
        pad = _pad(mascara, caminho)
        try:
            assert _no_de(pad).vidpid[0] == vendor, (caminho, mascara)
            assert pad.mascara_no_jogo == mascara
        finally:
            pad.stop()

    def test_a_regra_tem_um_dono_e_so_o_modo_escolhido_veste(self) -> None:
        assert mascara_no_jogo(CAMINHO_XBOX, "dualsense") == "xbox"
        assert mascara_no_jogo(CAMINHO_XBOX, "nintendo") == "xbox"
        assert mascara_no_jogo(" XBOX ", "nintendo") == "xbox"
        for caminho in (None, "", "qualquer", CAMINHO_DUALSENSE):
            for mascara in MASCARAS:
                assert mascara_no_jogo(caminho, mascara) == mascara, (caminho, mascara)


def test_a_combinacao_invisivel_nao_nasce_em_par_nenhum() -> None:
    """A régua da sprint numa linha: nenhum par com o modo Xbox registra pad
    Sony ou Nintendo no `uinput`. Mordida: a mesma da classe 1."""
    invisiveis = []
    for caminho in (None, CAMINHO_DUALSENSE, CAMINHO_XBOX):
        for mascara in MASCARAS:
            pad = _pad(mascara, caminho)
            try:
                vendor = _no_de(pad).vidpid[0]
                if caminho == CAMINHO_XBOX and vendor in (SONY_VENDOR, NINTENDO_VENDOR):
                    invisiveis.append((caminho, mascara, hex(vendor)))
            finally:
                pad.stop()
    assert invisiveis == []


# ===========================================================================
# 2 — o pad vestido fala a língua do Xbox
# ===========================================================================


class TestOPadVestidoFalaXbox:
    """MORDIDA: devolva `self.flavor` ao `_resolve_evdev` e ao `forward_analog`
    do `UinputGamepad`: o cartão Nintendo no modo Xbox manda o quadrado como
    `BTN_WEST` (o Y do Xbox) e o L2 como botão, que o nó nem declara."""

    @pytest.mark.parametrize(
        ("botao", "tecla"),
        [("cross", _EC.BTN_A), ("circle", _EC.BTN_B), ("square", _EC.BTN_X),
         ("triangle", _EC.BTN_Y)],
    )
    def test_os_botoes_saem_na_tabela_do_xbox(self, botao: str, tecla: int) -> None:
        """Um botão por vez: o quadrado é o X do Xbox (`0x133`) e o triângulo
        o Y (`0x134`) — a tabela do Pro os troca de lugar."""
        pad = _pad("nintendo", CAMINHO_XBOX)
        try:
            no = _no_de(pad)
            pad.forward_buttons(frozenset({botao}))
            apertos = [code for tipo, code, valor in no.escritas if tipo == _EC.EV_KEY and valor]
            assert apertos == [tecla], f"{botao} saiu como {[hex(c) for c in apertos]}"
            assert tecla in no.teclas, "escreveu tecla que o nó não declara"
        finally:
            pad.stop()

    def test_o_gatilho_continua_analogico(self) -> None:
        pad = _pad("nintendo", CAMINHO_XBOX)
        try:
            no = _no_de(pad)
            pad.forward_analog(lx=128, ly=128, rx=128, ry=128, l2=200, r2=0)
            assert (_EC.EV_ABS, _EC.ABS_Z, 200) in no.escritas
            assert not any(code in (_EC.BTN_TL2, _EC.BTN_TR2) for _t, code, _v in no.escritas)
        finally:
            pad.stop()

    def test_a_vibracao_do_jogo_tem_por_onde_chegar(self) -> None:
        """O Xbox 360 declara `FF_RUMBLE`, e o rumble do jogo segue para o
        físico daquele jogador pelo `rumble_sink` (a prova com a mão é dela)."""

        def _sink(_fraco: int, _forte: int) -> None:
            return

        pad = _pad("dualsense", CAMINHO_XBOX, rumble_sink=_sink)
        try:
            assert _EC.FF_RUMBLE in _no_de(pad).events.get(_EC.EV_FF, ())
            assert pad.rumble_sink is _sink and pad.ff_supported
        finally:
            pad.stop()

    def test_vestir_depois_de_nascer_recusa(self) -> None:
        pad = UinputGamepad.for_flavor("dualsense")
        assert pad.start()
        try:
            with pytest.raises(RuntimeError):
                pad.vestir("xbox")
        finally:
            pad.stop()


# ===========================================================================
# 3 — nenhum juiz recria o pad vestido em laço (P1 e P2 a P4)
# ===========================================================================


def _daemon_do_p1(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env", lambda _d: None
    )
    monkeypatch.setattr(gp, "_set_controller_grab", lambda *_a: None)
    d = Daemon(
        controller=FakeController(transport="usb"),
        config=DaemonConfig(ipc_enabled=False, udp_enabled=False),
    )
    d.controller.primary_uniq = MACS[0]
    d._coop_manager = SimpleNamespace(
        sync=lambda **_k: None,
        disable=lambda: None,
        player_count=lambda: 1,
        algum_boneco_ficou_para_tras=lambda: False,
    )
    d._game_signal = SimpleNamespace(authority="daemon")
    return d


class TestNenhumJuizRecriaEmLaco:
    """O aparelho é função do par (caminho, máscara), e os juízes comparam os
    dois. MORDIDA: faça a fábrica pendurar no `flavor` o aparelho vestido
    (`xbox`) e o juiz do P1 recria o pad a cada compasso do co-op."""

    @pytest.mark.parametrize("cartao", ["dualsense", "nintendo"])
    def test_o_p1_do_modo_xbox_fica_de_pe(
        self, cartao: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registro_de_mascaras().set_mask(MACS[0], cartao)
        d = _daemon_do_p1(monkeypatch)
        gp.start_gamepad_emulation_desfecho(d, "dualsense", origin="profile", caminho="xbox")
        pad = d._gamepad_device
        assert _no_de(pad).vidpid == (XBOX360_VENDOR, XBOX360_PRODUCT), "premissa"
        try:
            for _ in range(10):
                assert gp.reconciliar_as_mascaras(d) is None
            assert (
                gp.start_gamepad_emulation_desfecho(
                    d, "dualsense", origin="profile", caminho="xbox"
                )
                == gp.EMU_JA_ESTAVA
            )
            assert d._gamepad_device is pad, "o juiz recriou o P1 do modo Xbox"
            assert len(_NoGravado.criados) == 1
        finally:
            gp.stop_gamepad_emulation(d, persist=False)

    def test_os_jogadores_2_a_4_do_modo_xbox_ficam_de_pe(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "hefesto_dualsense4unix.daemon.launch_env.materialize_launch_env", lambda _d: None
        )
        for mac, cartao in zip(MACS[1:], ("dualsense", "nintendo", "xbox"), strict=True):
            registro_de_mascaras().set_mask(mac, cartao)
        daemon = SimpleNamespace(
            config=SimpleNamespace(
                coop_enabled=True,
                gamepad_flavor="dualsense",
                gamepad_caminho=CAMINHO_XBOX,
                gamepad_emulation_enabled=True,
            ),
            is_native_mode=lambda: False,
            _gamepad_device=None,
            controller=SimpleNamespace(hidraw_path=lambda uniq=None: None),
            bus=SimpleNamespace(publish=lambda _t, _d: None),
        )
        manager = CoopManager(daemon)
        daemon._coop_manager = manager
        for numero, mac in enumerate(MACS[1:], start=2):
            leitor = SimpleNamespace(
                grab_state="held", set_grab=lambda g: True, stop=lambda: None,
                snapshot=lambda: None,
            )
            jogador = _SecondaryPlayer(
                identity=mac, evdev_path=f"/dev/input/event{numero}", reader=leitor,
                player_index=numero,
            )
            manager._players[mac] = jogador
            manager._promote_player(jogador)
        try:
            for mac in MACS[1:]:
                vpad = manager._players[mac].vpad
                assert vpad is not None, mac
                assert _no_de(vpad).vidpid == (XBOX360_VENDOR, XBOX360_PRODUCT), mac
            assert manager.algum_boneco_ficou_para_tras() is False, (
                "o juiz do co-op quer recriar um pad que já está no aparelho certo"
            )
        finally:
            for mac in MACS[1:]:
                vpad = manager._players[mac].vpad
                if vpad is not None:
                    vpad.stop()

    def test_voltar_ao_modo_dualsense_recria_o_cartao_dualsense(self) -> None:
        """A volta do PS + R3: o cartão DualSense tem de sair do Xbox 360."""
        registro_de_mascaras().set_mask(MACS[0], "dualsense")
        pad = _pad("dualsense", CAMINHO_XBOX, identity=MACS[0])
        try:
            assert not vpad_ficou_para_tras(
                pad.flavor, MACS[0], "dualsense", vpad=pad, caminho=CAMINHO_XBOX
            )
            assert vpad_ficou_para_tras(
                pad.flavor, MACS[0], "dualsense", vpad=pad, caminho=CAMINHO_DUALSENSE
            )
        finally:
            pad.stop()


# ===========================================================================
# 3b — a troca de modo com o pad de pé (o PS + R3, o lançamento que arma o modo)
# ===========================================================================


def _vidpid_do_p1(d: Any) -> tuple[int, int]:
    return _no_de(d._gamepad_device).vidpid


class TestATrocaDeModoComOPadDePe:
    """O pad nasce certo; aqui, o que acontece quando o MODO muda com ele vivo.

    É o caso do L4 (27/09): a mesa estava no modo DualSense antes do jogo, e o
    lançamento do Future Knight armou o modo Xbox com os pads de pé.

    MORDIDA do cartão DualSense: a da classe 1 (sem o vestir, o pad recriado no
    modo Xbox volta a ser o Edge no `uinput`).
    """

    def test_o_cartao_dualsense_vai_ao_xbox_360_e_volta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        registro_de_mascaras().set_mask(MACS[0], "dualsense")
        d = _daemon_do_p1(monkeypatch)
        try:
            gp.start_gamepad_emulation_desfecho(
                d, "dualsense", origin="profile", caminho=CAMINHO_DUALSENSE
            )
            assert _vidpid_do_p1(d)[0] == SONY_VENDOR, "premissa: o Edge (sem uhid aqui)"
            assert (
                gp.start_gamepad_emulation_desfecho(
                    d, "dualsense", origin="profile", caminho=CAMINHO_XBOX
                )
                == gp.EMU_APLICADO
            )
            assert _vidpid_do_p1(d) == (XBOX360_VENDOR, XBOX360_PRODUCT), (
                "o modo Xbox chegou com o pad de pé e o P1 ficou no Edge sem hidraw"
            )
            gp.start_gamepad_emulation_desfecho(
                d, "dualsense", origin="profile", caminho=CAMINHO_DUALSENSE
            )
            assert _vidpid_do_p1(d)[0] == SONY_VENDOR, "a volta ao modo DualSense"
        finally:
            gp.stop_gamepad_emulation(d, persist=False)

    def test_o_cartao_nintendo_vira_xbox_360_quando_o_modo_muda(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O juiz pelo aparelho, no P1 — e sem laço depois dele.

        Era `xfail(strict=True)` até a onda 3 (28/09). A segunda metade é a que
        prova os dois juízes JUNTOS: dez compassos do `reconciliar_as_mascaras`
        e um apply idêntico não recriam o Xbox 360 recém-vestido. MORDIDA: tire
        o `o_aparelho_mudou` do `ja_estava` do P1 e ele passa a discordar do
        juiz do compasso (o Pro fica; o compasso pede o start e ouve «já
        estava»); tirado do `vpad_ficou_para_tras`, reprova a régua do co-op.
        """
        registro_de_mascaras().set_mask(MACS[0], "nintendo")
        d = _daemon_do_p1(monkeypatch)
        try:
            gp.start_gamepad_emulation_desfecho(
                d, "dualsense", origin="profile", caminho=CAMINHO_DUALSENSE
            )
            assert _vidpid_do_p1(d)[0] == NINTENDO_VENDOR, "premissa: o Pro"
            gp.start_gamepad_emulation_desfecho(
                d, "dualsense", origin="profile", caminho=CAMINHO_XBOX
            )
            gp.reconciliar_as_mascaras(d)
            assert _vidpid_do_p1(d) == (XBOX360_VENDOR, XBOX360_PRODUCT), (
                "o modo Xbox chegou com o Pro de pé e ele ficou Pro no `uinput`, "
                "sem hidraw: o P4 azul do G3"
            )
            vestido = d._gamepad_device
            criados = len(_NoGravado.criados)
            for _ in range(10):
                assert gp.reconciliar_as_mascaras(d) is None, (
                    "o juiz do compasso quer recriar o Xbox 360 que o P1 acabou de vestir"
                )
            assert (
                gp.start_gamepad_emulation_desfecho(
                    d, "dualsense", origin="profile", caminho=CAMINHO_XBOX
                )
                == gp.EMU_JA_ESTAVA
            )
            assert d._gamepad_device is vestido
            assert len(_NoGravado.criados) == criados, "o P1 entrou em laço de recriação"
        finally:
            gp.stop_gamepad_emulation(d, persist=False)

    def test_o_pro_sem_modo_escolhido_fica_pro_e_nao_entra_em_laco(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem modo escolhido o Pro segue Pro, e o juiz não o recria em laço.

        A armadilha que a pergunta AO PAD evita: a fábrica pendura o caminho
        RESOLVIDO, e o Pro sem escolha nasce com o caminho Xbox pendurado. Um
        juiz que fizesse a conta pelo caminho pendurado veria «Xbox 360» onde
        há um Pro, e o recriaria a cada compasso. MORDIDA: troque, em
        `o_aparelho_mudou`, a pergunta ao pad por
        `mascara_no_jogo(caminho_do_vpad(vpad), vpad.flavor)`.
        """
        registro_de_mascaras().set_mask(MACS[0], "nintendo")
        d = _daemon_do_p1(monkeypatch)
        try:
            gp.start_gamepad_emulation_desfecho(d, "dualsense", origin="profile", caminho=None)
            assert _vidpid_do_p1(d)[0] == NINTENDO_VENDOR, "premissa: o Pro"
            pad = d._gamepad_device
            for _ in range(10):
                assert gp.reconciliar_as_mascaras(d) is None
            assert (
                gp.start_gamepad_emulation_desfecho(d, "dualsense", origin="profile", caminho=None)
                == gp.EMU_JA_ESTAVA
            )
            assert d._gamepad_device is pad
            assert len(_NoGravado.criados) == 1
        finally:
            gp.stop_gamepad_emulation(d, persist=False)

    def test_o_juiz_do_coop_ve_o_pro_ficar_para_tras(self) -> None:
        registro_de_mascaras().set_mask(MACS[1], "nintendo")
        pad = _pad("dualsense", CAMINHO_DUALSENSE, identity=MACS[1], player=2)
        try:
            assert _no_de(pad).vidpid[0] == NINTENDO_VENDOR, "premissa: o Pro"
            assert vpad_ficou_para_tras(
                pad.flavor, MACS[1], "dualsense", vpad=pad, caminho=CAMINHO_XBOX
            ), "o modo Xbox chegou e o juiz do co-op deixou o Pro de pé"
        finally:
            pad.stop()


# ===========================================================================
# 4 — a Mira Virtual vale no modo Xbox
# ===========================================================================


def test_a_mira_virtual_chega_ao_xbox_360(monkeypatch: pytest.MonkeyPatch) -> None:
    """O giroscópio do físico vira analógico direito no pad que o jogo usa.

    A `A-MIRA-POR-MOVIMENTO-NA-TELA-01` já traduz em qualquer máscara; aqui se
    confere o que faltava: o pad do modo Xbox recebe a mira e a escreve no eixo
    `ABS_RX` que o nó declara. MORDIDA: a da classe 1 (o pad nasce Edge, que o
    jogo não abre, e a mira escreve num nó que ninguém lê) — e, no motor, tire
    a chamada de `aplicar_o_movimento` do `dispatch_gamepad`.
    """
    from hefesto_dualsense4unix.core import roteador_de_movimento as rot
    from hefesto_dualsense4unix.core.virtual_motion import REGISTRO
    from tests.unit.test_o_movimento_vale_em_qualquer_mascara import (
        _arranjo,
        _daemon_do_tamanho_do_real,
        _Hub,
    )

    pad = _pad("dualsense", CAMINHO_XBOX, identity=MACS[0])
    no = _no_de(pad)
    try:
        monkeypatch.setattr(gp, "_reconciliar_launch", lambda _d: None)
        monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda _d: None)
        monkeypatch.setattr(gp, "primary_identity", lambda _d: MACS[0])
        monkeypatch.setattr(REGISTRO, "estado", lambda _u: SimpleNamespace(giroscopio=True))
        store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
        rot.definir_ativo(store, _arranjo(sensibilidade=12))
        daemon = _daemon_do_tamanho_do_real(
            _Hub(velocidade=(0.0, 120.0, 0.0)), store=store, _gamepad_device=pad,
            _mouse_device=None,
        )
        estado = SimpleNamespace(raw_lx=128, raw_ly=128, raw_rx=128, raw_ry=128,
                                 l2_raw=0, r2_raw=0)
        gp.dispatch_gamepad(daemon, estado, frozenset())
        rx = [valor for tipo, code, valor in no.escritas
              if tipo == _EC.EV_ABS and code == _EC.ABS_RX]
        assert no.vidpid == (XBOX360_VENDOR, XBOX360_PRODUCT)
        assert rx and rx[-1] != 128, f"o analógico direito do Xbox 360 saiu em {rx}"
    finally:
        pad.stop()
