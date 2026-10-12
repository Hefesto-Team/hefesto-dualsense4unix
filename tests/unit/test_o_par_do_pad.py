"""O par do pad: todo pad que o jogo vê tem a háptica presa à porta USB dele.

A tarefa é a O-PAR-DO-PAD (12/10/2026). Medido ao vivo com os quatro DualSense
no rádio e o Sackboy: com o endpoint de háptica do primeiro controle numa âncora
emprestada (um hub), o acumulador do jogo crescia 8,2 passos/s e os quadros
caíam a 4 fps; com os quatro casados no gadget, 0,00/s por dez minutos e 60 fps.

Tudo aqui roda num sysfs, num gadget e num servidor de som DE MENTIRA. O que se
prova, nesta ordem:

1. **A identidade que chega depois** — o pad que monta sem dono (o P1 do boot,
   com o ``primary_uniq`` vazio) registra a âncora quando o dono chega, antes
   ou depois da enumeração; «não sei» não apaga o dono.
2. **A identidade que muda** — o posto de P1 que passa a outro controle leva a
   âncora junto, sem apagar o registro novo do aparelho antigo.
3. **Quem avisa o pad** — o relógio da identidade do laço do daemon.
4. **O endpoint nasce casado** — com o gadget do aparelho a caminho, o som não
   cria o endpoint numa emprestada; o 1º e o 4º, no rádio e no cabo. O aparelho
   sem gadget (o 5º pad, a máquina sem os módulos) segue com a emprestada.
5. **O pad nosso não é aparelho** — o ``hidraw`` do gadget sai da lista do som
   pelo dono único, e não ganha endpoint órfão.
6. **A fila, o dono único e o número** (a Tarefa 2) — os gadgets montados juntos
   esperam a fila da enumeração; o P1 que enumera sem dono larga o som em 3 s; o
   co-op é o dono único de «este aparelho vai ganhar pad»; o serial leva o número.
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations import pad_usb
from tests.unit import test_a_haptica_chega_a_quem_entra_depois as h
from tests.unit.test_o_pad_nasce_no_mesmo_usb_do_som import (
    IDENTIDADE,
    INTERFACE_DO_GADGET,
    BancadaDoGadget,
    _usb_da_mesa,
)

# Faixas forjadas da casa (``aa:bb:cc`` e ``02:fe``); nunca um endereço real.
OUTRA = "aa:bb:cc:00:00:12"
INTERFACE_DA_OUTRA = "/devices/platform/vhci_hcd.0/usb3/3-2/3-2:1.0"
ENUMERADO = ("hidraw9", INTERFACE_DO_GADGET)


@pytest.fixture
def bancada(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> BancadaDoGadget:
    return BancadaDoGadget(monkeypatch, tmp_path)


# --- 1. A identidade que chega depois -----------------------------------------


class TestAIdentidadeQueChegaDepois:
    """MORDIDA: em ``ancorar_no_aparelho``, devolva ``False`` logo na entrada."""

    def test_o_pad_sem_dono_registra_a_ancora_quando_o_dono_chega(
        self, bancada: BancadaDoGadget
    ) -> None:
        bancada.enumerado = ENUMERADO
        pad = bancada.pad(identity=None)
        try:
            assert pad.start()
            assert bancada.esperar(lambda: pad.is_bound)
            assert bancada.pedidos[0][2] == ""
            assert pad_usb.interface_do_aparelho(IDENTIDADE) is None
            assert pad.ancorar_no_aparelho(IDENTIDADE) is True
            assert pad_usb.interface_do_aparelho(IDENTIDADE) == INTERFACE_DO_GADGET
            assert pad.ancorar_no_aparelho(IDENTIDADE) is False
        finally:
            pad.stop()
        assert pad_usb.interface_do_aparelho(IDENTIDADE) is None

    def test_o_dono_que_chega_antes_da_enumeracao_registra_nela(
        self, bancada: BancadaDoGadget
    ) -> None:
        pad = bancada.pad(identity=None)
        try:
            assert pad.start()
            assert pad_usb.gadget_a_caminho(IDENTIDADE) is True
            assert pad.ancorar_no_aparelho(IDENTIDADE) is True
            assert pad_usb.interface_do_aparelho(IDENTIDADE) is None
            assert pad_usb.gadget_a_caminho(IDENTIDADE) is True
            assert pad_usb.gadget_a_caminho(OUTRA) is False
            bancada.enumerado = ENUMERADO
            assert bancada.esperar(lambda: pad.is_bound)
            assert pad_usb.interface_do_aparelho(IDENTIDADE) == INTERFACE_DO_GADGET
            assert pad_usb.gadget_a_caminho(IDENTIDADE) is False
        finally:
            pad.stop()

    def test_nao_sei_nao_apaga_o_dono(self, bancada: BancadaDoGadget) -> None:
        bancada.enumerado = ENUMERADO
        pad = bancada.pad()
        try:
            assert pad.start()
            assert bancada.esperar(lambda: pad.is_bound)
            for nao_sei in (None, "", "path:/dev/input/event3"):
                assert pad.ancorar_no_aparelho(nao_sei) is False
            assert pad_usb.interface_do_aparelho(IDENTIDADE) == INTERFACE_DO_GADGET
            assert pad.identity == IDENTIDADE
        finally:
            pad.stop()

    def test_o_p1_que_ganhou_dono_estaciona_com_o_jogo_aberto(
        self, bancada: BancadaDoGadget
    ) -> None:
        """Sem dono o gadget descia com o jogo aberto, e o GUID do device KS mudava."""
        bancada.enumerado = ENUMERADO
        bancada.jogo_aberto = True
        pad = bancada.pad(identity=None)
        assert pad.start()
        assert bancada.esperar(lambda: pad.is_bound)
        pad.ancorar_no_aparelho(IDENTIDADE)
        pad.stop()
        assert bancada.clientes[0].desmontados == []
        assert bancada.ug._GADGETS_ESTACIONADOS.quantos() == 1
        assert pad_usb.interface_do_aparelho(IDENTIDADE) == INTERFACE_DO_GADGET
        bancada.jogo_aberto = False
        assert bancada.ug._GADGETS_ESTACIONADOS.varrer() == 1
        assert pad_usb.interface_do_aparelho(IDENTIDADE) is None

    def test_o_gadget_que_desce_sem_enumerar_nao_fica_a_caminho(
        self, bancada: BancadaDoGadget
    ) -> None:
        pad = bancada.pad(identity=None)
        assert pad.start()
        assert pad_usb.gadget_a_caminho(OUTRA) is True
        pad.stop()
        assert pad_usb.gadget_a_caminho(OUTRA) is False


# --- 2. A identidade que muda --------------------------------------------------


class TestAIdentidadeQueMuda:
    def test_o_posto_que_passa_a_outro_controle_leva_a_ancora(
        self, bancada: BancadaDoGadget
    ) -> None:
        bancada.enumerado = ENUMERADO
        pad = bancada.pad()
        try:
            assert pad.start()
            assert bancada.esperar(lambda: pad.is_bound)
            assert pad.ancorar_no_aparelho(OUTRA) is True
            assert pad_usb.interface_do_aparelho(OUTRA) == INTERFACE_DO_GADGET
            assert pad_usb.interface_do_aparelho(IDENTIDADE) is None
            assert pad.identity == OUTRA
        finally:
            pad.stop()
        assert pad_usb.interface_do_aparelho(OUTRA) is None

    def test_o_registro_novo_do_aparelho_antigo_fica(self, bancada: BancadaDoGadget) -> None:
        """O aparelho que saiu do posto já ganhou o pad dele: o velho não o apaga.

        MORDIDA: em ``pad_usb.esquecer_gadget``, ignore a ``interface`` e
        apague sempre — o registro do pad novo do aparelho antigo some.
        """
        bancada.enumerado = ENUMERADO
        pad = bancada.pad()
        assert pad.start()
        assert bancada.esperar(lambda: pad.is_bound)
        pad_usb.registrar_gadget(IDENTIDADE, INTERFACE_DA_OUTRA)
        assert pad.ancorar_no_aparelho(OUTRA) is True
        assert pad_usb.interface_do_aparelho(IDENTIDADE) == INTERFACE_DA_OUTRA
        pad.stop()
        assert pad_usb.interface_do_aparelho(OUTRA) is None
        assert pad_usb.interface_do_aparelho(IDENTIDADE) == INTERFACE_DA_OUTRA

    def test_o_registro_novo_nao_cruza_a_desmontagem(
        self, bancada: BancadaDoGadget, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A âncora nova entra sob a trava em que o ``_destruir_o_device`` solta o gadget.

        Fora dela, o gadget lido podia descer entre a leitura e o registro, e a
        âncora ficava numa interface morta. MORDIDA: em ``ancorar_no_aparelho``,
        chame o ``_ancorar_o_gadget`` fora do ``with self._lock``.
        """
        import threading

        bancada.enumerado = ENUMERADO
        pad = bancada.pad()
        assert pad.start()
        assert bancada.esperar(lambda: pad.is_bound)
        registrar = pad_usb.registrar_gadget
        livre: list[bool] = []

        def registrar_vendo_a_trava(identidade: str, interface: str) -> None:
            def outro_fio() -> None:
                pegou = pad._lock.acquire(blocking=False)
                if pegou:
                    pad._lock.release()
                livre.append(pegou)

            fio = threading.Thread(target=outro_fio)
            fio.start()
            fio.join()
            registrar(identidade, interface)

        monkeypatch.setattr(pad_usb, "registrar_gadget", registrar_vendo_a_trava)
        try:
            assert pad.ancorar_no_aparelho(OUTRA) is True
        finally:
            pad.stop()
        assert livre == [False]


# --- 3. Quem avisa o pad --------------------------------------------------------


class _PadQueOuve:
    def __init__(self) -> None:
        self.ouviu: list[str | None] = []

    def ancorar_no_aparelho(self, identidade: str | None) -> bool:
        self.ouviu.append(identidade)
        return True


class TestQuemAvisaOPad:
    def test_o_dono_do_posto_vai_ao_pad_do_p1(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import ancorar_o_p1_no_aparelho

        pad = _PadQueOuve()
        daemon: Any = SimpleNamespace(
            controller=SimpleNamespace(primary_uniq=None), _gamepad_device=pad
        )
        assert ancorar_o_p1_no_aparelho(daemon) is False
        assert pad.ouviu == []
        daemon.controller.primary_uniq = IDENTIDADE
        assert ancorar_o_p1_no_aparelho(daemon) is True
        assert pad.ouviu == [IDENTIDADE]

    def test_o_pad_sem_gadget_e_a_falta_de_pad_nao_quebram(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.gamepad import ancorar_o_p1_no_aparelho

        for device in (None, object()):
            daemon: Any = SimpleNamespace(
                controller=SimpleNamespace(primary_uniq=IDENTIDADE), _gamepad_device=device
            )
            assert ancorar_o_p1_no_aparelho(daemon) is False

    def test_o_laco_do_daemon_pergunta_no_relogio_da_identidade(self) -> None:
        """MORDIDA: tire a chamada do ``_poll_loop`` e veja reprovar."""
        from hefesto_dualsense4unix.daemon.lifecycle import Daemon

        fonte = inspect.getsource(Daemon._poll_loop)
        relogio = fonte.split("identity_sync_next_at = tick_started + 2.0", 1)[1]
        relogio = relogio.split("if tick_started >=", 1)[0]
        assert "ancorar_o_p1_no_aparelho(self)" in relogio


# --- 4. O endpoint nasce casado ------------------------------------------------

_PADS = {h._P1: 1, h._P4: 4}
_NO_CABO = {h._P1: ("3-8", 28), h._P4: ("3-5", 31)}


def _mesa_com_gadgets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    mesa = h.mesa.__wrapped__(monkeypatch, tmp_path)  # type: ignore[attr-defined]
    monkeypatch.setattr(pad_usb, "_INTERFACE_DO_APARELHO", {})
    for n in range(1, 5):
        _usb_da_mesa(mesa.sysfs, "devices/platform/vhci_hcd.0/usb5", f"5-{n}", vid="054c",
                     pid="0df2", dev=f"189:{512 + n}",
                     serial=pad_usb.serial_do_pad(f"02:fe:00:80:00:0{n}"))
    return mesa


def _interface(n: int) -> str:
    return f"/devices/platform/vhci_hcd.0/usb5/5-{n}/5-{n}:1.0"


def _chega(mesa: Any, uniq: str, transporte: str) -> Any:
    lugar = _PADS[uniq]
    if transporte == "cabo":
        aparelho, devnum = _NO_CABO[uniq]
        return h._no_cabo(mesa, uniq, lugar, aparelho, devnum)
    mesa.assentos[uniq] = lugar
    return h._Controle(uniq, "bt", f"/dev/hidraw{lugar}")


@pytest.mark.parametrize("transporte", ["bt", "cabo"])
@pytest.mark.parametrize("uniq", list(_PADS), ids=["primeiro", "quarto"])
@pytest.mark.parametrize("dono", ["do-aparelho", "sem-dono"])
def test_com_o_gadget_a_caminho_o_endpoint_nasce_casado(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, transporte: str, uniq: str, dono: str
) -> None:
    """A ordem: o pad monta, a âncora registra, e SÓ ENTÃO o endpoint nasce.

    MORDIDA: em ``_casar_as_pontes``, tire o ``gadget_a_caminho`` — o endpoint
    nasce na emprestada, e a âncora do gadget vira uma reancoragem (uma queda).
    """
    mesa = _mesa_com_gadgets(monkeypatch, tmp_path)
    n = _PADS[uniq]
    serial = pad_usb.serial_do_pad(f"02:fe:00:80:00:0{n}")
    pad_usb.anotar_gadget_a_caminho(serial, uniq if dono == "do-aparelho" else "", 30.0)
    controle = _chega(mesa, uniq, transporte)
    mesa.volta(controle)
    assert mesa.servidor.do_nome(eh.nome_do_endpoint(uniq)) == []
    pad_usb.registrar_gadget(uniq, _interface(n))
    pad_usb.gadget_chegou(serial)
    mesa.volta(controle)
    assert h._ancora_do_aparelho(mesa.servidor, uniq) == _interface(n)
    assert mesa.servidor.quedas == []


def test_o_gadget_a_caminho_de_um_nao_segura_o_outro(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    mesa = _mesa_com_gadgets(monkeypatch, tmp_path)
    pad_usb.anotar_gadget_a_caminho(pad_usb.serial_do_pad("02:fe:00:80:00:04"), h._P4, 30.0)
    um, quatro = _chega(mesa, h._P1, "bt"), _chega(mesa, h._P4, "bt")
    mesa.volta(um, quatro)
    assert mesa.servidor.do_nome(eh.nome_do_endpoint(h._P4)) == []
    assert "/vhci_hcd." not in h._ancora_do_aparelho(mesa.servidor, h._P1)


def test_o_aparelho_sem_gadget_segue_com_a_emprestada_na_hora(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O 5º pad e a máquina sem os módulos: o endpoint de mentira de hoje fica."""
    mesa = _mesa_com_gadgets(monkeypatch, tmp_path)
    mesa.volta(_chega(mesa, h._P1, "bt"))
    emprestada = h._ancora_do_aparelho(mesa.servidor, h._P1)
    assert emprestada.startswith("/devices/pci0000:00/")


def test_o_prazo_vencido_empresta(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """O gadget que não enumera não deixa o aparelho sem háptica para sempre."""
    mesa = _mesa_com_gadgets(monkeypatch, tmp_path)
    pad_usb.anotar_gadget_a_caminho(pad_usb.serial_do_pad("02:fe:00:80:00:01"), "", 0.0)
    mesa.volta(_chega(mesa, h._P1, "bt"))
    assert h._ancora_do_aparelho(mesa.servidor, h._P1).startswith("/devices/pci0000:00/")


def test_a_ancora_que_chega_depois_reancora_sem_jogo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O endpoint que nasceu antes do pad (a janela antes da montagem) se corrige."""
    mesa = _mesa_com_gadgets(monkeypatch, tmp_path)
    controle = _chega(mesa, h._P1, "bt")
    mesa.volta(controle)
    assert "/vhci_hcd." not in h._ancora_do_aparelho(mesa.servidor, h._P1)
    pad_usb.registrar_gadget(h._P1, _interface(1))
    mesa.volta(controle)
    assert h._ancora_do_aparelho(mesa.servidor, h._P1) == _interface(1)


def test_com_o_jogo_tocando_na_emprestada_o_endpoint_fica(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A regra que fica (e por que o endpoint tem de NASCER casado).

    Descarregar o null-sink debaixo de um fluxo do jogo move o fluxo para a
    saída padrão (a háptica do jogo sai na caixa de som) e o device KS que o
    Proton gravou no lançamento aponta para o ``sysfs.path`` velho.
    """
    mesa = _mesa_com_gadgets(monkeypatch, tmp_path)
    controle = _chega(mesa, h._P1, "bt")
    mesa.volta(controle)
    emprestada = h._ancora_do_aparelho(mesa.servidor, h._P1)
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(h._P1))
    pad_usb.registrar_gadget(h._P1, _interface(1))
    mesa.volta(controle)
    assert h._ancora_do_aparelho(mesa.servidor, h._P1) == emprestada
    assert mesa.servidor.quedas == []


# --- 5. O pad nosso não é aparelho ---------------------------------------------


def _hidraw(classe: Path, nome: str, hid: Path, uevent: str) -> None:
    hid.mkdir(parents=True, exist_ok=True)
    (hid / "uevent").write_text(uevent, encoding="utf-8")
    (classe / nome).mkdir(parents=True)
    os.symlink(hid, classe / nome / "device")


@pytest.mark.parametrize(
    "uniq_do_gadget",
    ["02:fe:00:80:00:01", "hefesto-pad-02fe00800001", "hefesto-pad-01-02fe00800001", ""],
    ids=["mac-forjado", "serial-antes-do-probe", "serial-com-o-numero", "so-o-serial"],
)
def test_o_hidraw_do_gadget_nao_e_aparelho(tmp_path: Path, uniq_do_gadget: str) -> None:
    """MORDIDA: volte ao filtro por ``HID_PHYS == hefesto-vpad`` e o gadget entra."""
    from hefesto_dualsense4unix.daemon.subsystems.alto_falante import controles_na_lista

    sys_ = tmp_path / "sys"
    classe = sys_ / "class" / "hidraw"
    usb = sys_ / "devices" / "platform" / "vhci_hcd.0" / "usb5" / "5-1"
    usb.mkdir(parents=True)
    (usb / "serial").write_text("hefesto-pad-02fe00800001\n", encoding="utf-8")
    _hidraw(classe, "hidraw7", usb / "5-1:1.0" / "0003:054C:0DF2.0020",
            "HID_ID=0003:0000054C:00000DF2\nHID_PHYS=usb-vhci_hcd.0-1/input0\n"
            f"HID_UNIQ={uniq_do_gadget}\n")
    _hidraw(classe, "hidraw4", sys_ / "devices/virtual/misc/uhid/0005:054C:0CE6.0004",
            f"HID_ID=0005:0000054C:00000CE6\nHID_PHYS=aa:bb:cc:00:00:10\nHID_UNIQ={h._P1}\n")
    _hidraw(classe, "hidraw5", sys_ / "devices/pci0000:00/usb1/1-2/1-2:1.3/0003:054C:0CE6.0005",
            f"HID_ID=0003:0000054C:00000CE6\nHID_PHYS=usb-0000:00:14.0-2/input3\n"
            f"HID_UNIQ={h._P2}\n")
    _hidraw(classe, "hidraw6", sys_ / "devices/virtual/misc/uhid/0003:054C:0DF2.0006",
            "HID_ID=0003:0000054C:00000DF2\nHID_PHYS=hefesto-vpad\n"
            "HID_UNIQ=02:fe:00:80:00:05\n")
    achados = {c.uniq: c.transporte for c in controles_na_lista(str(classe))}
    assert achados == {h._P1: "rádio", h._P2: "cabo"}


# --- 6. A fila, o dono único e o número -----------------------------------------


def test_o_terceiro_gadget_da_fila_espera_a_vez_dele(bancada: BancadaDoGadget) -> None:
    """Medido em 12/10/2026: o hub enumera um gadget por vez, ~5,6 s cada.

    Os quatro montavam no mesmo ms com 15 s cada; o terceiro foi achado aos
    14,85 s e morto aos 15,0 s, e o quarto nunca começou. Com dois à frente, o
    prazo é de três enumerações. MORDIDA: tire a fila de ``_o_pad_em_usb`` e o
    pad falha aos 16 s.
    """
    relogio = [100.0]
    bancada.ug._FILA_DA_ENUMERACAO.update({"hefesto-pad-01-x", "hefesto-pad-02-y"})
    pad = bancada.pad(time_fn=lambda: relogio[0], player=3)
    try:
        assert pad.start()
        assert pad._gadget_prazo == pytest.approx(145.0)
        relogio[0] += 16.0
        assert not bancada.esperar(lambda: pad._gadget_falhou, segundos=0.4)
        bancada.enumerado = ENUMERADO
        assert bancada.esperar(lambda: pad.is_bound)
        assert pad._gadget_falhou is False
        assert pad.mac and not any(
            s.endswith(pad_usb._so_hex(pad.mac)) for s in bancada.ug._FILA_DA_ENUMERACAO
        ), "enumerado, sai da fila"
    finally:
        pad.stop()


def test_o_p1_que_enumera_sem_dono_larga_o_som_em_tres_segundos(
    bancada: BancadaDoGadget,
) -> None:
    """O P1 do boot sem dono segurava o endpoint de TODO aparelho por 19 s.

    MORDIDA: tire o ``encurtar_a_caminho`` de ``_vigiar_a_enumeracao`` e o prazo
    volta aos 19 s.
    """
    import time

    pad = bancada.pad(identity=None)
    try:
        assert pad.start()
        serial = bancada.pedidos[0][0]
        assert pad_usb._A_CAMINHO[serial][1] - time.monotonic() > 10.0
        bancada.enumerado = ENUMERADO
        assert bancada.esperar(lambda: pad.is_bound)
        assert pad_usb.gadget_a_caminho(OUTRA) is True, "o relógio da identidade tem a vez"
        assert pad_usb._A_CAMINHO[serial][1] - time.monotonic() <= 3.0
        assert pad_usb.gadget_a_caminho(OUTRA, agora=time.monotonic() + 3.1) is False
    finally:
        pad.stop()


def test_o_co_op_e_o_dono_unico_de_este_aparelho_vai_ganhar_pad() -> None:
    """O controle que entra com o jogo aberto: o som espera o co-op decidir.

    MORDIDA: devolva só o laço do ``_A_CAMINHO`` em ``gadget_a_caminho`` (sem o
    ``_por_decidir_locked``) e o aparelho não visto não espera.
    """
    import time

    agora = time.monotonic()
    assert pad_usb.gadget_a_caminho(OUTRA) is False, "sem co-op no ar, ninguém espera"
    pad_usb.a_mesa_viu(None, 5.0)
    assert pad_usb.gadget_a_caminho(OUTRA) is False, "renovar o que nunca foi lido não vale"

    pad_usb.a_mesa_viu([IDENTIDADE], 5.0)
    assert pad_usb.gadget_a_caminho(IDENTIDADE) is False, "visto e sem pad a caminho"
    assert pad_usb.gadget_a_caminho(OUTRA, agora=agora) is True, "o co-op ainda não o viu"
    assert pad_usb.gadget_a_caminho(OUTRA, agora=agora + 4.9) is True
    assert pad_usb.gadget_a_caminho(OUTRA, agora=agora + 5.1) is False, "espera no máximo 5 s"

    pad_usb.anotar_pad_a_caminho(OUTRA, 10.0)
    assert pad_usb.gadget_a_caminho(OUTRA) is True, "na mesa, com o pad por nascer"
    assert pad_usb.gadget_a_caminho(IDENTIDADE) is False, "a espera é só dele"
    pad_usb.pad_decidido(OUTRA)
    pad_usb.a_mesa_viu([IDENTIDADE, OUTRA], 5.0)
    assert pad_usb.gadget_a_caminho(OUTRA) is False

    pad_usb.a_mesa_saiu()
    pad_usb.a_mesa_viu(None, 5.0)
    assert pad_usb.gadget_a_caminho("aa:bb:cc:00:00:13") is False, "co-op fora: nada espera"


def test_o_co_op_anota_ao_assentar_e_limpa_quando_o_pad_nasce() -> None:
    """Os três pontos do co-op que falam com o dono único. MORDIDA: tire um e reprova."""
    from hefesto_dualsense4unix.daemon.subsystems import coop

    fonte = inspect.getsource(coop.CoopManager._spawn_player)
    assert "anotar_pad_a_caminho" in fonte
    assert "pad_decidido" in inspect.getsource(coop.CoopManager._promote_player)
    assert "pad_decidido" in inspect.getsource(coop.CoopManager._teardown_player)
    assert "_publicar_a_mesa" in inspect.getsource(coop.CoopManager.sync)


def test_o_serial_leva_o_numero_e_o_jogo_os_ve_na_ordem() -> None:
    """O jogo numerou pela ordem alfabética do serial, 4 de 4 nas três rodadas de 12/10.

    MORDIDA: ``serial_do_pad`` ignorando o número e a ordem volta a ser a do MAC.
    """
    from hefesto_dualsense4unix.broker import hidraw_broker as broker

    macs = {1: "02:fe:00:80:00:09", 2: "02:fe:00:80:00:01", 3: "02:fe:00:80:00:05",
            4: "02:fe:00:80:00:03"}
    seriais = {n: pad_usb.serial_do_pad(mac, n) for n, mac in macs.items()}
    assert seriais[1] == "hefesto-pad-01-02fe00800009"
    assert [n for n, _s in sorted(seriais.items(), key=lambda par: par[1].upper())] == [1, 2, 3, 4]
    assert pad_usb.serial_do_pad(macs[1]) == "hefesto-pad-02fe00800009"
    for serial in (*seriais.values(), pad_usb.serial_do_pad(macs[1])):
        assert broker._SERIAL_DO_PAD_RE.match(serial), serial
        assert pad_usb.e_pad_nosso("/sys/nada", uniq=serial, ler=lambda _c: "")
    for torto in ("hefesto-pad-1-02fe00800009", "hefesto-pad-001-02fe00800009"):
        assert broker._SERIAL_DO_PAD_RE.match(torto) is None
