"""O SOM E A HÁPTICA JUNTOS — as réguas do ensaio do passo 0 (01/10/2026)."""

from __future__ import annotations

import importlib.util
import itertools
import os
import sys
import zlib
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af

REPO_ROOT = Path(__file__).resolve().parents[2]

MAC_UM = "02:fe:00:00:00:01"
MAC_DOIS = "02:fe:00:00:00:02"

ASSENTO_DO_CONTROLE = (0x91, 4, 7)
ASSENTO_DO_SOM = (0x93, 13, 200)
ASSENTO_DO_HAPTICO = (0x92, 215, 64)


def _carregar(nome: str) -> Any:
    """`scripts/ensaios/` não é pacote — carrega pelo caminho, como os irmãos."""
    caminho = REPO_ROOT / "scripts" / "ensaios" / f"{nome}.py"
    pasta = str(caminho.parent)
    if pasta not in sys.path:
        sys.path.insert(0, pasta)
    espec = importlib.util.spec_from_file_location(f"{nome}_sob_ensaio", caminho)
    assert espec is not None and espec.loader is not None
    modulo = importlib.util.module_from_spec(espec)
    sys.modules[espec.name] = modulo
    espec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def ensaio() -> Any:
    return _carregar("o_som_e_a_haptica_juntos")


def _crc_independente(corpo: bytes) -> int:
    """O CRC do rádio sem o código do produto: o ``zlib`` com o ``0xA2`` na frente."""
    return zlib.crc32(b"\xa2" + corpo) & 0xFFFFFFFF


def problemas_do_report_junto(pkt: bytes, quadro: bytes, bloco: bytes) -> list[str]:
    """O parser independente: anda a cadeia de blocos e confere os três assentos."""
    erros: list[str] = []
    if len(pkt) != 334 or pkt[0] != 0x35:
        erros.append(f"o report não é o 0x35 de 334 B (id {pkt[0]:#04x}, {len(pkt)} B)")
        return erros
    vistos: list[tuple[int, int, int]] = []
    i = 2
    while i + 1 < len(pkt) - 4 and pkt[i] & 0x80:
        tag, tamanho = pkt[i], pkt[i + 1]
        vistos.append((tag, i + 2, tamanho))
        i += 2 + tamanho
    for esperado in (ASSENTO_DO_CONTROLE, ASSENTO_DO_SOM, ASSENTO_DO_HAPTICO):
        if esperado not in vistos:
            erros.append(f"falta o bloco {esperado[0]:#04x} em [{esperado[1]}] com {esperado[2]} B")
    _t, ini, n = ASSENTO_DO_SOM
    if pkt[ini : ini + len(quadro)] != quadro or any(pkt[ini + len(quadro) : ini + n]):
        erros.append("o Opus não está inteiro no assento do som")
    _t, ini, n = ASSENTO_DO_HAPTICO
    if pkt[ini : ini + n] != bloco:
        erros.append("o bloco háptico não está inteiro no assento dele")
    if int.from_bytes(pkt[-4:], "little") != _crc_independente(pkt[:-4]):
        erros.append("o CRC não bate")
    return erros


def _quadro_de_mentira() -> bytes:
    """Um quadro de Opus de mentira, de bytes distintos e mais curto que o assento."""
    return bytes((7 * k + 1) & 0xFF or 1 for k in range(180))


class TestOReportJuntoRelidoPorFora:
    """Mordida 1: o bloco háptico no assento do som → reprova."""

    def test_os_tres_blocos_inteiros_e_o_crc_certo(self, ensaio: Any) -> None:
        quadro = _quadro_de_mentira()
        bloco = ensaio.blocos_da_vibracao(1, frequencia=150, amplitude=100)[0]
        pkt = ensaio.montar_junto(quadro, bloco, seq=3, contador=9)
        assert problemas_do_report_junto(pkt, quadro, bloco) == []
        assert pkt[1] == 3 << 4
        assert pkt[4:11] == bytes((0xFE, 0, 0, 0, 0, 0xFF, 9))

    def test_o_relido_do_ensaio_concorda_com_o_de_fora(self, ensaio: Any) -> None:
        bloco = ensaio.blocos_da_vibracao(1, frequencia=150, amplitude=100)[0]
        pkt = ensaio.montar_junto(_quadro_de_mentira(), bloco, seq=1, contador=1)
        lido = ensaio.reler(pkt)
        assert lido.crc_ok and lido.id == 0x35
        assert lido.blocos == (ASSENTO_DO_CONTROLE, ASSENTO_DO_SOM, ASSENTO_DO_HAPTICO)

    def test_o_haptico_no_assento_do_som_reprova(self) -> None:
        """A passada azul de 18/09: o bloco ``0x92`` em [11], o som fora."""
        quadro = _quadro_de_mentira()
        bloco = bytes(range(64))
        pkt = bytearray(334)
        pkt[0], pkt[2], pkt[3] = 0x35, 0x91, 7
        pkt[11], pkt[12] = 0x92, 64
        pkt[13:77] = bloco
        pkt[-4:] = _crc_independente(bytes(pkt[:-4])).to_bytes(4, "little")
        erros = problemas_do_report_junto(bytes(pkt), quadro, bloco)
        assert any("0x93" in e for e in erros)
        assert any("0x92" in e for e in erros)

    def test_o_crc_errado_reprova(self, ensaio: Any) -> None:
        quadro = _quadro_de_mentira()
        bloco = bytes(64)
        pkt = ensaio.montar_junto(quadro, bloco, seq=1, contador=1, crc_errado=True)
        assert problemas_do_report_junto(pkt, quadro, bloco) == ["o CRC não bate"]
        assert not ensaio.reler(pkt).crc_ok

    def test_sem_o_haptico_e_o_0x35_de_hoje_byte_a_byte(self, ensaio: Any) -> None:
        """A mordida ``--sem-haptico`` é o report que tocou em 10/09, e não outro."""
        quadro = _quadro_de_mentira()
        pkt = ensaio.montar_junto(quadro, bytes(64), seq=5, contador=12, sem_haptico=True)
        hoje = af.ARRANJO_035.montar(
            [quadro], seq=5, controle=af.controle_de_audio_035(contador_de_quadros=12)
        )
        assert pkt == hoje

    def test_o_layout_cabe_no_arranjo_generico(self, ensaio: Any) -> None:
        """A cura depois do passo 0 é uma constante: o ``Arranjo`` monta o mesmo report."""
        quadro = _quadro_de_mentira()
        bloco = ensaio.blocos_da_vibracao(1, frequencia=150, amplitude=90)[0]
        junto = af.Arranjo(
            nome="0x35-junto (só nesta régua)",
            fonte="o ensaio do passo 0, NÃO medido",
            degrau=0x35,
            pos_tag_controle=2,
            len_controle=7,
            pos_tag_audio=11,
            len_audio=200,
            pos_audio=13,
            quadros_de_audio=1,
            pos_tag_haptico=213,
            len_haptico=64,
            pos_haptico=215,
            haptico_duplo=False,
        )
        pelo_arranjo = junto.montar(
            [quadro],
            seq=2,
            controle=af.controle_de_audio_035(contador_de_quadros=4),
            haptico=bloco,
        )
        assert ensaio.montar_junto(quadro, bloco, seq=2, contador=4) == pelo_arranjo


class TestOsSinais:
    def test_o_bloco_haptico_e_a_senoide_nos_dois_motores(self, ensaio: Any) -> None:
        blocos = ensaio.blocos_da_vibracao(3, frequencia=150, amplitude=100)
        assert all(len(b) == 64 for b in blocos)
        for b in blocos:
            assert b[0::2] == b[1::2]
        picos = [v - 256 if v > 127 else v for b in blocos for v in b]
        assert max(picos) == 100 and min(picos) == -100

    def test_o_tom_anda_na_taxa_da_fonte(self, ensaio: Any) -> None:
        """1300 Hz a 45 kHz: um período a cada ~34,6 amostras, e não ~36,9 (48 kHz)."""
        import struct

        quadros = ensaio.quadros_do_tom(10, frequencia=1300, amplitude=8000)
        assert all(len(q) == af.BYTES_DE_PCM_POR_QUADRO for q in quadros)
        esquerda = struct.unpack(f"<{len(b''.join(quadros)) // 2}h", b"".join(quadros))[0::2]
        subidas = sum(1 for a, b in itertools.pairwise(esquerda) if a < 0 <= b)
        esperadas = len(esquerda) * 1300 / af.TAXA_DA_FONTE_DO_SOM
        assert abs(subidas - esperadas) <= 1


class _Porta:
    """A porta de mentira: um pipe no lugar do hidraw, e a conta do fechar."""

    def __init__(self) -> None:
        self.leitura, self.fd = os.pipe()
        self.fechada = False

    def fechar(self) -> None:
        self.fechada = True
        os.close(self.fd)
        os.close(self.leitura)


class _Mundo:
    """O ``comum`` do ensaio, por dublês: nenhum broker, nenhum hidraw, nenhum daemon."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, ensaio: Any) -> None:
        import comum

        self.comum = comum
        self.monkeypatch = monkeypatch
        self.daemon_no_ar = False
        self.aparelhos: list[Any] = []
        self.abertas: list[_Porta] = []
        self.ensaio = ensaio
        monkeypatch.setattr(comum, "cabecalho_do_instrumento", lambda *a, **k: "cabeçalho")
        monkeypatch.setattr(
            comum,
            "estado_do_daemon",
            lambda: comum.EstadoDoDaemon(unidade_ativa=self.daemon_no_ar),
        )
        monkeypatch.setattr(comum, "descobrir_aparelhos", lambda: list(self.aparelhos))
        monkeypatch.setattr(comum, "abrir_no_hidraw", self._abrir)
        monkeypatch.setattr(af, "CodificadorOpus", _OpusDeMentira)

    def _abrir(self, caminho: str, *, escrita: bool = True) -> _Porta:
        assert escrita
        porta = _Porta()
        self.abertas.append(porta)
        return porta

    def com_controle(self, mac: str, n: int) -> None:
        self.aparelhos.append(
            self.comum.Aparelho(
                hidraw=f"hidraw{n}",
                caminho_hidraw=f"/dev/hidraw{n}",
                dir_device="/sys/de/mentira",
                mac=mac,
                nome="DualSense Wireless Controller",
                transporte=self.comum.RADIO,
                e_vpad=False,
                rotulo="",
            )
        )

    def rodar(self, *args: str) -> int:
        argv = ["o_som_e_a_haptica_juntos.py", "--segundos", "0.05", *args]
        self.monkeypatch.setattr(sys, "argv", argv)
        return int(self.ensaio.main())


class _OpusDeMentira:
    """O Opus de mentira: a régua não depende da libopus da máquina."""

    def codificar(self, _pcm: bytes) -> bytes:
        return bytes(b"\x01" * af.BYTES_POR_QUADRO_OPUS)


@pytest.fixture
def mundo(monkeypatch: pytest.MonkeyPatch, ensaio: Any) -> _Mundo:
    return _Mundo(monkeypatch, ensaio)


class TestAsGuardas:
    """Mordidas 2, 3 e 4: a leitura pura, a recusa e o controle devolvido."""

    def test_sem_tocar_nenhuma_porta_se_abre(self, mundo: _Mundo) -> None:
        mundo.com_controle(MAC_UM, 7)
        assert mundo.rodar() == 0
        assert mundo.abertas == []

    def test_com_o_daemon_no_ar_recusa(self, mundo: _Mundo) -> None:
        mundo.com_controle(MAC_UM, 7)
        mundo.daemon_no_ar = True
        assert mundo.rodar("--tocar") == 1
        assert mundo.abertas == []

    def test_a_passada_b_espera_sem_abrir_nada(self, mundo: _Mundo) -> None:
        mundo.com_controle(MAC_UM, 7)
        assert mundo.rodar("--tocar", "--passada", "B") == 1
        assert mundo.abertas == []

    def test_toca_e_devolve_o_controle(self, mundo: _Mundo) -> None:
        mundo.com_controle(MAC_UM, 7)
        assert mundo.rodar("--tocar") == 0
        assert len(mundo.abertas) == 1 and mundo.abertas[0].fechada

    def test_o_controle_volta_mesmo_quando_o_laco_cai(self, mundo: _Mundo) -> None:
        mundo.com_controle(MAC_UM, 7)

        ensaio = mundo.ensaio
        original = ensaio.montar_junto
        chamadas = []

        def _cai(*a: Any, **k: Any) -> bytes:
            chamadas.append(1)
            if len(chamadas) > 2:
                raise RuntimeError("o laço caiu no meio")
            return bytes(original(*a, **k))

        mundo.monkeypatch.setattr(ensaio, "montar_junto", _cai)
        with pytest.raises(RuntimeError):
            mundo.rodar("--tocar")
        assert len(mundo.abertas) == 1 and mundo.abertas[0].fechada

    def test_dois_no_radio_sem_escolha_recusa(self, mundo: _Mundo) -> None:
        mundo.com_controle(MAC_UM, 7)
        mundo.com_controle(MAC_DOIS, 8)
        assert mundo.rodar("--tocar") == 1
        assert mundo.abertas == []

    def test_o_ar_dos_quatro_abre_todos(self, mundo: _Mundo) -> None:
        mundo.com_controle(MAC_UM, 7)
        mundo.com_controle(MAC_DOIS, 8)
        assert mundo.rodar("--tocar", "--todos") == 0
        assert len(mundo.abertas) == 2 and all(p.fechada for p in mundo.abertas)

    def test_o_exigir_mac_escolhe_um(self, mundo: _Mundo) -> None:
        mundo.com_controle(MAC_UM, 7)
        mundo.com_controle(MAC_DOIS, 8)
        assert mundo.rodar("--tocar", "--exigir-mac", MAC_DOIS) == 0
        assert len(mundo.abertas) == 1
