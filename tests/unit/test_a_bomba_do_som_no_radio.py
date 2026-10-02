"""A BOMBA — as réguas do laço que faltava entre o nó e o fio (07/09/2026)."""

from __future__ import annotations

import importlib.util
import math
import os
import struct
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af

REPO_ROOT = Path(__file__).resolve().parents[2]

MAC_SINTETICO = "aa:bb:cc:00:00:07"


def _pcm(quantos: int) -> bytes:
    """PCM ``s16le`` estéreo com SINAL, nunca silêncio."""
    amostras: list[int] = []
    for i in range(quantos // 4):
        valor = int(12000 * math.sin(2 * math.pi * 440 * i / af.TAXA_DO_ENCODER))
        amostras.extend((valor, valor))
    return struct.pack(f"<{len(amostras)}h", *amostras)


def _fonte_infinita() -> Any:
    def _ler(quantos: int) -> bytes:
        return _pcm(quantos)

    return _ler


def _relogio(passo: float = 0.01) -> Any:
    """Um relógio de mentira, monotônico e determinístico."""
    estado = {"t": 0.0}

    def _agora() -> float:
        estado["t"] += passo
        return estado["t"]

    return _agora


@pytest.fixture
def arranjo() -> af.Arranjo:
    return af.ARRANJO_DS5DONGLE


class TestOContadorDaVoltaEhOQueOFirmwareExige:
    """ARRANQUE `self._seq = (self._seq + 1) % VOLTA_DA_SEQUENCIA` e veja passar."""

    def test_o_nibble_gira_e_da_a_volta(self, arranjo: af.Arranjo) -> None:
        bomba = af.BombaDeSomPeloRadio(arranjo=arranjo, fonte=_fonte_infinita())
        vistos = [(bomba.um_report() or b"\x00\x00")[1] >> 4 for _ in range(20)]
        assert vistos[: af.VOLTA_DA_SEQUENCIA] == list(range(af.VOLTA_DA_SEQUENCIA))
        assert vistos[af.VOLTA_DA_SEQUENCIA :] == [0, 1, 2, 3]

    def test_o_crc_acompanha_a_sequencia(self, arranjo: af.Arranjo) -> None:
        """Dois reports com o MESMO PCM e seq diferente têm CRC diferente."""
        bomba = af.BombaDeSomPeloRadio(arranjo=arranjo, fonte=_fonte_infinita())
        primeiro = bomba.um_report() or b""
        segundo = bomba.um_report() or b""
        assert primeiro[-4:] != segundo[-4:]


class TestALeituraCurtaEhContadaNuncaEngolida:
    """ARRANQUE o ramo do ``pcm_curto`` e veja a bomba parecer sã com a fonte agonizando."""

    def test_completa_com_silencio_e_conta(self, arranjo: af.Arranjo) -> None:
        pedacos = [_pcm(1000), b""]

        def _fonte(_quantos: int) -> bytes:
            return pedacos.pop(0) if pedacos else b""

        bomba = af.BombaDeSomPeloRadio(arranjo=arranjo, fonte=_fonte)
        report = bomba.um_report()
        assert report is not None and len(report) == arranjo.tamanho
        assert bomba.contagem.pcm_curto == 1
        assert bomba.contagem.pcm_lido == 1000
        assert bomba.um_report() is None, "fonte seca tem de parar o laço, não travar"


class TestSecoNaoEscreveUmByte:
    """ARRANQUE o ``if self.seco`` do :meth:`escrever` e veja o dublê explodir."""

    def test_seco_ignora_o_escritor(self, arranjo: af.Arranjo) -> None:
        def _bomba_atomica(_dados: bytes) -> int:
            raise AssertionError("o modo seco escreveu no aparelho")

        bomba = af.BombaDeSomPeloRadio(
            arranjo=arranjo, fonte=_fonte_infinita(), escritor=_bomba_atomica, seco=True
        )
        bomba.rodar(segundos=0.05, agora=_relogio())
        assert bomba.contagem.escritas_aceitas_pelo_kernel == 0
        assert bomba.contagem.reports_montados > 0, "seca ela ainda faz a conta inteira"

    def test_molhado_sem_escritor_continua_seco(self, arranjo: af.Arranjo) -> None:
        """``seco=False`` sem escritor não vira escrita: não há para onde."""
        bomba = af.BombaDeSomPeloRadio(
            arranjo=arranjo, fonte=_fonte_infinita(), escritor=None, seco=False
        )
        assert bomba.seco is True
        bomba.rodar(segundos=0.05, agora=_relogio())
        assert bomba.contagem.escritas_aceitas_pelo_kernel == 0


class TestAEscritaRecusadaEhContadaNaoEhCrash:
    """ARRANQUE o ``except OSError`` e veja o ensaio morrer no meio da bancada."""

    def test_conta_aceitas_e_recusadas(self, arranjo: af.Arranjo) -> None:
        chamadas = {"n": 0}

        def _escritor(dados: bytes) -> int:
            chamadas["n"] += 1
            if chamadas["n"] > 2:
                raise OSError(22, "Invalid argument")
            return len(dados)

        bomba = af.BombaDeSomPeloRadio(
            arranjo=arranjo, fonte=_fonte_infinita(), escritor=_escritor, seco=False
        )
        contagem = bomba.rodar(segundos=1.0, agora=_relogio())
        assert contagem.escritas_aceitas_pelo_kernel == 2
        assert contagem.escritas_recusadas == 1
        assert contagem.bytes_escritos == 2 * arranjo.tamanho


class TestONomeDoNumeroEhARessalva:
    """ARRANQUE a linha de ATENÇÃO do relatório e veja a régua passar mesmo assim."""

    def test_o_relatorio_diz_que_o_kernel_nao_e_o_firmware(self) -> None:
        linhas = "\n".join(af.ContagemDaBomba().linhas())
        assert "ACEITAS PELO KERNEL" in linhas
        assert "NÃO é 'o firmware obedeceu'" in linhas
        assert "orelha dela" in linhas

    def test_o_campo_se_chama_pelo_que_ele_mede(self) -> None:
        """O nome do atributo carrega a ressalva — renomear para "entregues"
        reprova aqui antes de chegar a um relatório."""
        assert hasattr(af.ContagemDaBomba(), "escritas_aceitas_pelo_kernel")
        assert not hasattr(af.ContagemDaBomba(), "reports_entregues")


class TestAFonteLeAteCompletar:
    """ARRANQUE o laço de :func:`fonte_de_arquivo` e veja 100% de recusa do encoder."""

    def test_junta_os_pedacos(self) -> None:
        """O PCM chega em DOIS tempos, e a leitura tem de esperar o segundo."""
        leitura, escrita = os.pipe()
        dados = _pcm(af.BYTES_DE_PCM_POR_QUADRO)
        metade = len(dados) // 2
        pronto = threading.Event()

        def _gotejar() -> None:
            os.write(escrita, dados[:metade])
            pronto.set()
            time.sleep(0.05)
            os.write(escrita, dados[metade:])
            os.close(escrita)

        goteira = threading.Thread(target=_gotejar, daemon=True)
        goteira.start()
        try:
            pronto.wait(timeout=2.0)
            assert len(af.fonte_de_arquivo(leitura)(len(dados))) == len(dados)
        finally:
            goteira.join(timeout=2.0)
            os.close(leitura)

    def test_fonte_seca_devolve_vazio(self) -> None:
        leitura, escrita = os.pipe()
        os.close(escrita)
        try:
            assert af.fonte_de_arquivo(leitura)(1920) == b""
        finally:
            os.close(leitura)


class TestOGravadorNaoCaiNaFontePadrao:
    """ARRANQUE o ``if not fonte`` e veja o instrumento ler o som da máquina dela."""

    def test_fonte_vazia_nao_gera_comando(self) -> None:
        assert af.argv_do_gravador("") == []

    def test_a_fonte_vai_como_argumento_proprio(self) -> None:
        argv = af.argv_do_gravador("hefesto_som_0000ab")
        if not argv:
            pytest.skip("nem pw-record nem parec nesta máquina")
        assert any("hefesto_som_0000ab" in a for a in argv)
        assert all(" " not in a or a.startswith("--") for a in argv), (
            "nada de shell=True: o nome vai inteiro, num argumento só"
        )


class TestORitmoImpedeAInundacao:
    """ARRANQUE :func:`fonte_com_ritmo` do ensaio e veja 53x o fio no rádio dela."""

    def test_cada_quadro_tem_prazo_e_o_prazo_nao_deriva(self) -> None:
        """O sono é o que FALTA para o prazo, não um intervalo fixo."""
        agora = {"t": 0.0}
        sonos: list[float] = []

        def _agora() -> float:
            return agora["t"]

        def _dormir(quanto: float) -> None:
            sonos.append(round(quanto, 6))
            agora["t"] += quanto

        def _fonte(_n: int) -> bytes:
            agora["t"] += 0.004
            return b"x"

        ler = af.fonte_com_ritmo(
            _fonte, ms_por_report=10, agora=_agora, dormir=_dormir
        )
        for _ in range(5):
            ler(1)
        assert sonos == [0.006, 0.006, 0.006, 0.006], sonos

    def test_quadro_atrasado_nao_dorme(self) -> None:
        """Trabalho mais longo que o intervalo não vira sono negativo."""
        agora = {"t": 0.0}
        sonos: list[float] = []

        def _fonte(_n: int) -> bytes:
            agora["t"] += 0.050
            return b"x"

        ler = af.fonte_com_ritmo(
            _fonte,
            ms_por_report=10,
            agora=lambda: agora["t"],
            dormir=sonos.append,
        )
        for _ in range(3):
            ler(1)
        assert sonos == [], "quadro atrasado não pode dormir"

    def test_o_ensaio_de_bancada_usa_o_ritmo(self) -> None:
        """A régua lê o FONTE do ensaio, e é o único jeito honesto."""
        fonte = (REPO_ROOT / "scripts" / "ensaios" / "o_som_que_sai.py").read_text(
            encoding="utf-8"
        )
        i = fonte.index("def escrever_no_aparelho")
        j = fonte.index("def main(", i)
        assert "af.fonte_com_ritmo(" in fonte[i:j]
        assert "escritor=af.escritor_de_hidraw(fd)" in fonte[i:j]


class TestABombaNaoEscolheOArranjo:
    """ARRANQUE a obrigatoriedade do ``arranjo`` e veja um default virar escolha."""

    def test_arranjo_e_obrigatorio(self) -> None:
        with pytest.raises(TypeError):
            af.BombaDeSomPeloRadio(fonte=_fonte_infinita())  # type: ignore[call-arg]

    def test_os_dois_continuam_registrados_sem_escolha(self) -> None:
        assert {a.nome for a in af.ARRANJOS} == {"ds5dongle", "senshi"}
        for arr in af.ARRANJOS:
            assert "NÃO medido nesta bancada" in arr.de_onde_sei


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


class _Controle:
    def __init__(self, uniq: str, caminho: str, transporte: str) -> None:
        self.uniq, self.caminho, self.transporte = uniq, caminho, transporte


class TestOEnsaioRecusaAntesDeEscrever:
    """ARRANQUE qualquer um dos degraus da cadeia e veja o ensaio escrever cedo."""

    @pytest.fixture
    def ensaio(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        modulo = _carregar("o_som_que_sai")
        import hefesto_dualsense4unix.daemon.subsystems.alto_falante as sub

        monkeypatch.setattr(
            sub,
            "controles_na_lista",
            lambda *a, **k: [
                _Controle(MAC_SINTETICO, "/dev/hidraw99", "rádio"),
                _Controle("e8:47:3a:00:00:09", "/dev/hidraw98", "cabo"),
            ],
        )
        return modulo

    def _args(self, ensaio: Any, **extra: Any) -> Any:
        import argparse

        base = {
            "exigir_mac": MAC_SINTETICO,
            "arranjo": "ds5dongle",
            "eu_estou_ouvindo": False,
            "segundos": ensaio.SEGUNDOS_PADRAO,
            "tag": af.BLOCO_SPEAKER,
        }
        base.update(extra)
        return argparse.Namespace(**base)

    def test_sem_mac_recusa(self, ensaio: Any) -> None:
        assert ensaio.escrever_no_aparelho(self._args(ensaio, exigir_mac="")) == 2

    def test_mac_fora_da_lista_recusa(self, ensaio: Any) -> None:
        assert (
            ensaio.escrever_no_aparelho(self._args(ensaio, exigir_mac="02:fe:00:00:00:01"))
            == 2
        )

    def test_no_cabo_recusa(self, ensaio: Any) -> None:
        args = self._args(ensaio, exigir_mac="e8:47:3a:00:00:09")
        assert ensaio.escrever_no_aparelho(args) == 2

    def test_sem_arranjo_recusa(self, ensaio: Any) -> None:
        assert ensaio.escrever_no_aparelho(self._args(ensaio, arranjo="")) == 2

    def test_sem_a_orelha_dela_para_em_tres(self, ensaio: Any, capsys: Any) -> None:
        """rc=3, e é o degrau que esta leva NÃO removeu."""
        assert ensaio.escrever_no_aparelho(self._args(ensaio)) == 3
        saida = capsys.readouterr().out
        assert "PARADO ANTES DE ESCREVER" in saida
        assert "--eu-estou-ouvindo" in saida
        assert "NÃO é a medição" in saida

    def test_o_teto_de_segundos_e_uma_trava(self, ensaio: Any) -> None:
        """Pedir 600 s não toca 600 s no aparelho dela."""
        assert ensaio.TETO_DE_SEGUNDOS <= 15.0
        assert ensaio.SEGUNDOS_PADRAO <= ensaio.TETO_DE_SEGUNDOS

    def test_o_timbre_e_o_que_ela_ja_relatou(self, ensaio: Any) -> None:
        """O pulsado, e não um tom contínuo — o relato dela carrega a resposta."""
        assert ensaio.BANCADA_PULSOS_HZ > 0
        ler = ensaio.pcm_pulsado()
        bloco = ler(af.BYTES_DE_PCM_POR_QUADRO * 100)
        amostras = struct.unpack(f"<{len(bloco) // 2}h", bloco)
        assert max(amostras) > 1000, "tem sinal"
        assert any(a == 0 for a in amostras), "e tem silêncio entre os pulsos"


class TestACapturaArmadaRecusaOReportDeAudio:
    """ARRANQUE a recusa do bit ``0x02`` e veja Opus virar marca dela.

    Com o microfone ligado, o DualSense manda áudio no MESMO report ``0x31``,
    com os MESMOS 78 bytes e CRC válido — a única diferença é o bit ``0x02`` do
    byte 1. Em 16/08/2026 um caminho sem essa recusa leu Opus como estado de
    botão: MIC e PS presos, a Steam sendo aberta dezenas de vezes por segundo,
    e ela desligando o controle. Aqui o estrago seria mais barato e mais
    traiçoeiro — **marcas que ela nunca fez, com a hora certa** — e nada é pior
    para um ensaio que já está inconclusivo há vinte dias.
    """

    @pytest.fixture
    def captura(self) -> Any:
        return _carregar("a_captura_armada_do_som_no_radio")

    def _report_de_audio(self, captura: Any) -> bytes:
        bruto = bytearray(78)
        bruto[0] = captura.INPUT_REPORT_BT
        bruto[1] = captura.INPUT_FLAG_AUDIO
        return bytes(bruto)

    def test_report_de_audio_nunca_vira_marca(self, captura: Any) -> None:
        classe, mudo = captura.classificar_report(self._report_de_audio(captura))
        assert classe == captura.E_AUDIO
        assert mudo is False

    def test_report_sem_crc_nao_vira_marca(self, captura: Any) -> None:
        """CRC ruim é ``E_NADA``, e quem recusa é o dono do extrator."""
        bruto = bytearray(78)
        bruto[0] = captura.INPUT_REPORT_BT
        classe, _ = captura.classificar_report(bytes(bruto))
        assert classe == captura.E_NADA

    def test_report_vazio_nao_explode(self, captura: Any) -> None:
        assert captura.classificar_report(b"") == (captura.E_NADA, False)

    def test_o_instrumento_nao_abre_para_escrita(self, captura: Any) -> None:
        """A assinatura diz ``escrita=False``. É leitura pura, e tem de continuar."""
        fonte = (
            REPO_ROOT / "scripts" / "ensaios" / "a_captura_armada_do_som_no_radio.py"
        ).read_text(encoding="utf-8")
        assert "abrir_no_hidraw(caminho, escrita=False)" in fonte
        assert "os.write" not in fonte
