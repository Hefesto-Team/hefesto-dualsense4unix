"""UM-GADGET-QUE-NAO-ENUMERA-NAO-CONDENA-OS-OUTROS-01 (12/10/2026).

Medido no diário do daemon de 12/10: às 14h26, 14h31 e 20h02 o P3 e o P4 deram
``pad_usb_nao_enumerou_fica_o_uhid``, a falha virou um contrato do PROCESSO, e
dali em diante todo pad nasceu em ``pad_usb_sem_contrato_fica_o_uhid``. A
leitura do gadget que caiu girou 22.155 vezes em um segundo
(``pad_usb_leitura_falhou err='[Errno 12]'``), uma linha por volta.

A régua usa a pergunta de VERDADE do contrato (``pad_usb.contrato_que_falta``,
com os módulos de mentira todos presentes), e não a lista fixa da bancada: é
ela que lia a falha da enumeração e condenava os pads seguintes.
"""

from __future__ import annotations

import errno
import itertools
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import pad_usb
from tests.unit.test_o_pad_nasce_no_mesmo_usb_do_som import (
    INTERFACE_DO_GADGET,
    BancadaDoGadget,
    _EspiaoDoDiario,
)

IDENTIDADE_P3 = "aa:bb:cc:00:00:33"
IDENTIDADE_P4 = "aa:bb:cc:00:00:44"
DOCTOR = Path(__file__).resolve().parents[2] / "scripts" / "doctor.sh"
APP_ID = "hefesto-dualsense4unix"


class Mesa:
    """A bancada do gadget com a pergunta real do contrato e o hidraw por serial."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        self.b = BancadaDoGadget(monkeypatch, tmp_path)
        self.ug = self.b.ug
        self.relogio = [100.0]
        #: ``{serial: (hidraw, interface)}``: quem enumerou pelo vhci.
        self.enumerados: dict[str, tuple[str, str]] = {}
        raiz = tmp_path / "module"
        raiz.mkdir()
        for nome in pad_usb.MODULOS_DO_GADGET:
            (raiz / nome).mkdir()
        lib = tmp_path / "lib-modules"
        lib.mkdir()
        (lib / "modules.dep").write_text("")
        (lib / "modules.builtin").write_text("")
        monkeypatch.setattr(
            self.ug, "CONTRATO_QUE_FALTA",
            lambda: pad_usb.contrato_que_falta(raiz_modulos=str(raiz), lib_modules=str(lib)),
        )
        monkeypatch.setattr(self.ug, "HIDRAW_DO_GADGET", self.enumerados.get)
        monkeypatch.setattr(self.ug, "_CONTRATOS_JA_AVISADOS", set())
        self.espiao = _EspiaoDoDiario(self.ug.logger)
        monkeypatch.setattr(self.ug, "logger", self.espiao)

    def pad(self, player: int, identidade: str) -> Any:
        return self.b.pad(player=player, identity=identidade, time_fn=lambda: self.relogio[0])

    def serial(self, pad: Any) -> str:
        return pad_usb.serial_do_pad(pad.mac, pad.player)

    def nao_enumera(self, pad: Any) -> None:
        """O prazo da enumeração vence sem o hidraw, e o tique devolve o pad ao uhid."""
        self.relogio[0] += 16.0 * (1 + len(self.ug._FILA_DA_ENUMERACAO))
        assert self.b.esperar(lambda: pad._gadget_falhou)
        pad.pump_ff()
        assert pad._gadget is None and pad.is_active

    def eventos(self, nome: str) -> int:
        return sum(1 for _nivel, evento in self.espiao.eventos if evento == nome)

    def tentar(self, pad: Any) -> None:
        """O tique da nova tentativa pede o gadget fora dele, e o tique seguinte lê a resposta."""
        pad.pump_ff()
        pedido = pad._pedido_ao_broker
        if pedido is not None:
            assert pedido.esperar(5.0), "o pedido ao broker não voltou"
            pad.pump_ff()


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Mesa:
    return Mesa(monkeypatch, tmp_path)


class TestAFalhaDeUmNaoViraAFalhaDeTodos:
    def test_o_p3_que_nao_enumera_volta_ao_uhid_e_o_p4_nasce_em_usb(self, mesa: Mesa) -> None:
        """Mordida: devolver o ``anotar_contrato_que_faltou`` da enumeração condena o P4."""
        p3 = mesa.pad(3, IDENTIDADE_P3)
        p4 = mesa.pad(4, IDENTIDADE_P4)
        try:
            assert p3.start() and p3._gadget is not None
            mesa.nao_enumera(p3)
            # (noqa-acento): chave de máquina
            assert pad_usb.porque_sem_porta(IDENTIDADE_P3) == "nao_enumerou"

            assert p4.start()
            assert p4._gadget is not None, "o P4 caiu no uhid pela falha do P3"
            mesa.enumerados[mesa.serial(p4)] = ("hidraw9", INTERFACE_DO_GADGET)
            assert mesa.b.esperar(lambda: p4.is_bound)
            assert mesa.eventos("pad_usb_sem_contrato_fica_o_uhid") == 0
            assert pad_usb.contrato_que_faltou_ao_montar() == []
        finally:
            p3.stop()
            p4.stop()

    def test_sem_jogo_o_p3_tenta_de_novo_uma_vez_e_com_jogo_espera(self, mesa: Mesa) -> None:
        p3 = mesa.pad(3, IDENTIDADE_P3)
        try:
            assert p3.start()
            mesa.nao_enumera(p3)
            assert len(mesa.b.pedidos) == 1
            mesa.b.jogo_aberto = True
            for _ in range(3):
                mesa.relogio[0] += 10.0
                p3.pump_ff()
            assert len(mesa.b.pedidos) == 1, "com o jogo aberto o pad não troca de pele"
            mesa.b.jogo_aberto = False
            mesa.relogio[0] += 10.0
            mesa.tentar(p3)
            assert len(mesa.b.pedidos) == 2 and p3._gadget is not None
            mesa.enumerados[mesa.serial(p3)] = ("hidraw7", INTERFACE_DO_GADGET)
            assert mesa.b.esperar(lambda: p3.is_bound)
            assert pad_usb.porta_fora(3) is False
        finally:
            p3.stop()

    def test_duas_falhas_seguidas_tiram_so_a_porta_do_p3(self, mesa: Mesa) -> None:
        p3 = mesa.pad(3, IDENTIDADE_P3)
        try:
            assert p3.start()
            mesa.nao_enumera(p3)
            assert mesa.eventos("pad_usb_porta_fora") == 0
            mesa.relogio[0] += 10.0
            mesa.tentar(p3)  # sem jogo: a nova tentativa
            assert len(mesa.b.pedidos) == 2
            mesa.nao_enumera(p3)
            assert mesa.eventos("pad_usb_porta_fora") == 1
            assert pad_usb.porta_fora(3) is True
            for _ in range(3):
                mesa.relogio[0] += 10.0
                p3.pump_ff()
            assert len(mesa.b.pedidos) == 2, "a porta fora não volta ao rodízio"
        finally:
            p3.stop()
        # O lançamento seguinte: o P3 renasce uhid, e o P4 segue em USB.
        p3 = mesa.pad(3, IDENTIDADE_P3)
        p4 = mesa.pad(4, IDENTIDADE_P4)
        try:
            assert p3.start() and p3._gadget is None
            assert pad_usb.porque_sem_porta(IDENTIDADE_P3) == "porta_fora"
            assert mesa.eventos("pad_usb_porta_fora") == 2, "o P3 novo fica no uhid calado"
            assert p4.start() and p4._gadget is not None
            assert len(mesa.b.pedidos) == 3
        finally:
            p3.stop()
            p4.stop()

    def test_o_p3_novo_do_lancamento_seguinte_tenta_o_gadget(self, mesa: Mesa) -> None:
        p3 = mesa.pad(3, IDENTIDADE_P3)
        try:
            assert p3.start()
            mesa.nao_enumera(p3)
        finally:
            p3.stop()
        p3 = mesa.pad(3, IDENTIDADE_P3)
        try:
            assert p3.start() and p3._gadget is not None
            mesa.enumerados[mesa.serial(p3)] = ("hidraw7", INTERFACE_DO_GADGET)
            assert mesa.b.esperar(lambda: p3.is_bound)
            mesa.relogio[0] += 20.0
            p3.pump_ff()
            # enumerou: a conta da porta zera, e uma falha futura não a tira de uma vez
            assert pad_usb.anotar_falha_da_porta(3) == 1
        finally:
            p3.stop()


class TestALeituraQueFalhaPerguntaEDorme:
    def test_vinte_enomem_dao_uma_linha_e_o_fio_dorme(
        self, mesa: Mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mordida: tirar a espera do fio volta a rajada; tirar a contagem volta as 20 linhas."""
        mesa.enumerados["*"] = ("hidraw9", INTERFACE_DO_GADGET)
        monkeypatch.setattr(mesa.ug, "HIDRAW_DO_GADGET", lambda _s: mesa.enumerados["*"])
        monkeypatch.setattr(mesa.ug, "_GADGET_VIGIA_S", 0.05)
        p1 = mesa.pad(1, "aa:bb:cc:00:00:11")
        tentativas: list[float] = []
        alvo: list[int] = []
        ler = os.read

        def ler_com_falha(fd: int, n: int) -> bytes:
            if alvo and fd == alvo[0] and len(tentativas) < 20:
                tentativas.append(time.monotonic())
                raise OSError(errno.ENOMEM, "Cannot allocate memory")
            return ler(fd, n)

        try:
            assert p1.start()
            assert mesa.b.esperar(lambda: p1.is_bound)
            assert mesa.b.jogo is not None
            alvo.append(p1._fd)
            monkeypatch.setattr(os, "read", ler_com_falha)
            mesa.b.jogo.send(bytes([0x02]) + bytes(47))
            assert mesa.b.esperar(lambda: len(tentativas) >= 20, segundos=6.0)
            assert mesa.b.esperar(lambda: p1.output_count >= 1, segundos=3.0)
        finally:
            monkeypatch.setattr(os, "read", ler)
            p1.stop()
        assert mesa.eventos("pad_usb_leitura_falhou") == 1, mesa.espiao.eventos
        intervalos = [b - a for a, b in itertools.pairwise(tentativas)]
        assert min(intervalos) >= 0.04, intervalos
        assert p1._gadget_caiu is False

    def test_a_rajada_que_nao_acaba_se_diz_durante_e_nao_so_no_fim(
        self, mesa: Mesa, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Mordida: sem a janela da rajada longa, o ENOMEM sem fim fica calado até o stop.

        Medido em 15/10/2026: uma rajada de mais de dois minutos com o gadget de pé.
        """
        monkeypatch.setattr(
            mesa.ug, "HIDRAW_DO_GADGET", lambda _s: ("hidraw9", INTERFACE_DO_GADGET)
        )
        monkeypatch.setattr(mesa.ug, "_GADGET_VIGIA_S", 0.02)
        monkeypatch.setattr(mesa.ug, "_GADGET_RAJADA_LONGA_S", 0.15)
        p1 = mesa.pad(1, "aa:bb:cc:00:00:11")
        alvo: list[int] = []
        ler = os.read

        def ler_com_falha(fd: int, n: int) -> bytes:
            if alvo and fd == alvo[0]:
                raise OSError(errno.ENOMEM, "Cannot allocate memory")
            return ler(fd, n)

        try:
            assert p1.start()
            assert mesa.b.esperar(lambda: p1.is_bound)
            assert mesa.b.jogo is not None
            alvo.append(p1._fd)
            monkeypatch.setattr(os, "read", ler_com_falha)
            mesa.b.jogo.send(bytes([0x02]) + bytes(47))
            assert mesa.b.esperar(
                lambda: mesa.eventos("pad_usb_leitura_falhou") >= 2, segundos=4.0
            ), "a rajada sem fim não se disse antes do stop"
        finally:
            monkeypatch.setattr(os, "read", ler)
            p1.stop()
        assert p1._gadget_caiu is False
        assert mesa.eventos("vpad_parou") == 1, "o doctor não sabe que o pad saiu"

    @pytest.mark.parametrize(
        ("erro", "linhas"), [(errno.ENOMEM, 0), (errno.EIO, 1)], ids=["enomem", "eio"]
    )
    def test_a_leitura_que_falha_com_o_gadget_sumido_derruba_o_pad(
        self, mesa: Mesa, monkeypatch: pytest.MonkeyPatch, erro: int, linhas: int
    ) -> None:
        # D-2210-O-ENOMEM-DA-QUEDA-E-O-HOST
        """Mordida: tirar a pergunta da leitura deixa o pad mudo num gadget que não existe.

        O ENOMEM da queda é o host que desligou a função do f_hid (medido em 22/10/2026:
        as 48 linhas de 18/10 a 21/10 caíram todas no `USB disconnect` do broker que
        reinicia). A queda tem a linha dela; a da leitura, com `vezes=1`, repetia a mesma
        notícia. Mordida: devolver o `_fechar_a_rajada` incondicional volta a linha. Um
        errno que a queda não explica (o EIO) continua escrevendo a dele: mordida, tirar
        o teste do errno cala o EIO.
        """
        achado: dict[str, tuple[str, str]] = {"*": ("hidraw9", INTERFACE_DO_GADGET)}
        monkeypatch.setattr(mesa.ug, "HIDRAW_DO_GADGET", lambda _s: achado.get("*"))
        monkeypatch.setattr(mesa.ug, "_GADGET_VIGIA_S", 0.02)
        p1 = mesa.pad(1, "aa:bb:cc:00:00:11")
        alvo: list[int] = []
        ler = os.read

        def ler_com_falha(fd: int, n: int) -> bytes:
            if alvo and fd == alvo[0]:
                raise OSError(erro, os.strerror(erro))
            return ler(fd, n)

        try:
            assert p1.start()
            assert mesa.b.esperar(lambda: p1.is_bound)
            assert mesa.b.jogo is not None
            alvo.append(p1._fd)
            achado.clear()
            monkeypatch.setattr(os, "read", ler_com_falha)
            mesa.b.jogo.send(bytes([0x02]) + bytes(47))
            assert mesa.b.esperar(lambda: p1._gadget_caiu, segundos=4.0)
            assert mesa.eventos("pad_usb_caiu_fica_o_uhid") == 1
            assert mesa.eventos("pad_usb_leitura_falhou") == linhas, mesa.espiao.eventos
        finally:
            monkeypatch.setattr(os, "read", ler)
            p1.stop()


def _linha(evento: str, campos: str = "", nivel: str = "info") -> str:
    """Uma linha do daemon no ``journalctl -o short-iso-precise``."""
    return (
        "2026-10-12T14:20:46.008817-03:00 maquina hefesto-dualsense4unix[1]: "
        f"2026-10-12T14:20:46.008729 [{nivel:<9}] {evento:<30} {campos}"
    ).rstrip()


SUBIDA = _linha("daemon_starting", "paused=False poll_hz=60")


class TestQuemFicouNoUhid:
    def test_o_diario_diz_cada_jogador_e_o_porque(self) -> None:
        linhas = [
            _linha("pad_usb_nao_enumerou_fica_o_uhid", "player=4 prazo_s=15.0", "warning"),
            SUBIDA,
            _linha("pad_usb_enumerou", "gadget=hefesto-pad-0 hidraw=hidraw8 player=1"),
            _linha("pad_usb_nao_enumerou_fica_o_uhid", "player=3 prazo_s=15.0", "warning"),
            _linha("uhid_device_created", "mac=02:fe:00:00:00:03 name=x player=3"),
            _linha("pad_usb_caiu_fica_o_uhid", "gadget=hefesto-pad-1 player=2", "warning"),
            _linha("pad_usb_porta_fora", "falhas=2 player=4", "warning"),
        ]
        assert pad_usb.quem_ficou_no_uhid(linhas) == {
            2: "caiu", 3: "nao_enumerou", 4: "porta_fora",  # (noqa-acento): chave de máquina
        }

    def test_o_que_enumerou_depois_sai_da_lista(self) -> None:
        linhas = [
            SUBIDA,
            _linha("pad_usb_nao_enumerou_fica_o_uhid", "player=3 prazo_s=15.0", "warning"),
            _linha("pad_usb_enumerou", "gadget=hefesto-pad-2 hidraw=hidraw9 player=3"),
        ]
        assert pad_usb.quem_ficou_no_uhid(linhas) == {}

    def test_o_pad_que_parou_sai_da_conta_e_a_porta_fora_volta_com_o_novo(self) -> None:
        linhas = [
            SUBIDA,
            _linha("pad_usb_nao_enumerou_fica_o_uhid", "player=3 prazo_s=15.0", "warning"),
            _linha("uhid_device_created", "mac=02:fe:00:00:00:03 name=x player=3"),
            _linha("pad_usb_nao_enumerou_fica_o_uhid", "player=4 prazo_s=15.0", "warning"),
            _linha("vpad_parou", "player=3"),
        ]
        so_o_p4 = {4: "nao_enumerou"}  # (noqa-acento): chave de máquina
        assert pad_usb.quem_ficou_no_uhid(linhas) == so_o_p4
        linhas += [
            _linha("pad_usb_porta_fora", "falhas=2 player=3"),
            _linha("uhid_device_created", "mac=02:fe:00:00:00:03 name=x player=3"),
        ]
        assert pad_usb.quem_ficou_no_uhid(linhas) == {
            3: "porta_fora", 4: "nao_enumerou",  # (noqa-acento): chave de máquina
        }

    def test_sem_contrato_vale_para_quem_nasce_depois(self) -> None:
        linhas = [
            SUBIDA,
            _linha("pad_usb_sem_contrato_fica_o_uhid", "contratos=['usbip_vudc']", "warning"),
            _linha("uhid_device_created", "mac=02:fe:00:00:00:01 name=x player=1"),
            _linha("uhid_device_created", "mac=02:fe:00:00:00:02 name=x player=2"),
        ]
        assert pad_usb.quem_ficou_no_uhid(linhas) == {1: "sem_contrato", 2: "sem_contrato"}

    def test_sem_a_subida_do_daemon_e_nao_sei(self) -> None:
        assert pad_usb.quem_ficou_no_uhid([]) is None
        assert pad_usb.quem_ficou_no_uhid(
            [_linha("pad_usb_nao_enumerou_fica_o_uhid", "player=3", "warning")]
        ) is None


def _doctor(lar: Path, diario: list[str]) -> str:
    binario = lar / "bin"
    binario.mkdir(exist_ok=True)
    (lar / "diario.txt").write_text("\n".join(diario) + "\n", encoding="utf-8")
    journal = binario / "journalctl"
    journal.write_text(f'#!/bin/sh\ncat "{lar}/diario.txt"\n', encoding="utf-8")
    journal.chmod(0o755)
    pasta = lar / APP_ID
    pasta.mkdir(exist_ok=True)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(str(pasta / f"{APP_ID}.sock"))
    sock.close()
    res = subprocess.run(
        ["bash", "-c",
         f'set --; source "{DOCTOR}"; '
         f"_python_do_produto() {{ printf '%s\\n' '{sys.executable}'; }}; "
         "check_o_pad_no_uhid"],
        capture_output=True, text=True, timeout=60, check=False,
        env={"PATH": f"{binario}:/usr/bin:/bin", "XDG_RUNTIME_DIR": str(lar), "HOME": str(lar)},
    )
    assert res.returncode == 0, res.stderr
    return res.stdout


@pytest.fixture
def lar() -> Iterator[Path]:
    """Diretório CURTO em ``/tmp``: o caminho de um socket AF_UNIX cabe em ~108 bytes."""
    d = Path(tempfile.mkdtemp(prefix="hf-uhid-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


class TestODoctorLeOQueODaemonViu:
    def test_o_p3_no_uhid_aparece_com_o_porque_e_o_efeito(self, lar: Path) -> None:
        saida = _doctor(lar, [
            SUBIDA,
            _linha("pad_usb_enumerou", "gadget=hefesto-pad-0 hidraw=hidraw8 player=1"),
            _linha("pad_usb_nao_enumerou_fica_o_uhid", "player=3 prazo_s=15.0", "warning"),
        ])
        assert "[WARN]" in saida and "jogador 3" in saida, saida
        assert "não enumerou" in saida and "varre o áudio" in saida, saida
        assert "jogador 1" not in saida, saida

    def test_o_diario_vazio_e_nao_sei(self, lar: Path) -> None:
        """Mordida: o ramo do «não sei» trocado por ``pass`` reprova aqui."""
        saida = _doctor(lar, [])
        assert "não sei" in saida, saida
        assert "[ OK ]" not in saida and "[WARN]" not in saida, saida

    def test_todos_em_usb_e_ok(self, lar: Path) -> None:
        saida = _doctor(lar, [
            SUBIDA,
            _linha("pad_usb_enumerou", "gadget=hefesto-pad-0 hidraw=hidraw8 player=1"),
        ])
        assert "[ OK ]" in saida and "[WARN]" not in saida, saida

    def test_o_pad_que_parou_nao_fica_no_uhid_do_doctor(self, lar: Path) -> None:
        """Mordida: o filtro do diário sem o ``vpad_parou`` deixa o P3 que saiu no uhid."""
        saida = _doctor(lar, [
            SUBIDA,
            _linha("pad_usb_nao_enumerou_fica_o_uhid", "player=3 prazo_s=15.0", "warning"),
            _linha("vpad_parou", "player=3"),
        ])
        assert "[ OK ]" in saida and "[WARN]" not in saida, saida
