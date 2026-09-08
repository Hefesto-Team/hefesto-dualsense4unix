"""A BOMBA — as réguas do laço que faltava entre o nó e o fio (07/09/2026).

CADA CLASSE AQUI É UMA MORDIDA, e o cabeçalho dela diz o que se arranca para
vê-la reprovar. Régua que passa com a cura arrancada não mede nada.

O QUE ESTAS RÉGUAS **NÃO** MEDEM, dito antes de qualquer asserção
------------------------------------------------------------------
Elas não medem que som saiu de aparelho nenhum, e não podem. O mapa proíbe a
conclusão com todas as letras (``audio.saida_dedicada.payload_do_degrau``):
*"NÃO ESCREVER, EM LUGAR NENHUM, que 'descobrimos o áudio por Bluetooth' ou que
a ponte funciona (…) FALÁCIA DO CANAL QUE RESPONDE"*. O que elas cobrem é o
nosso lado do fio — a rotação do contador, a leitura curta, a recusa por
transporte, e **o nome do número**, que é o que separa "o kernel aceitou" de
"o firmware obedeceu".

**Nenhuma toca o aparelho, o servidor de som nem a bancada.** Dublês, MACs
sintéticos e fontes de PCM geradas aqui: *"a régua não é a mesa desta casa"*.
"""

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

#: Faixa sintética da casa. Nada de MAC real em arquivo versionado — há dois
#: portões, e um deles pega por FORMA, sem consultar OUI nenhum.
MAC_SINTETICO = "aa:bb:cc:00:00:07"


def _pcm(quantos: int) -> bytes:
    """PCM ``s16le`` estéreo com SINAL, nunca silêncio.

    Silêncio em CBR também fecha 200 bytes — mediria o bitrate sem medir o
    codificador trabalhando, que é a diferença entre uma régua e um espelho.
    """
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
    """Um relógio de mentira, monotônico e determinístico.

    O laço da bomba anda no ritmo da FONTE, não de um `sleep` — então a régua
    não pode esperar tempo de verdade sem virar um teste lento e instável.
    """
    estado = {"t": 0.0}

    def _agora() -> float:
        estado["t"] += passo
        return estado["t"]

    return _agora


@pytest.fixture
def arranjo() -> af.Arranjo:
    return af.ARRANJO_DS5DONGLE


class TestOContadorDaVoltaEhOQueOFirmwareExige:
    """ARRANQUE `self._seq = (self._seq + 1) % VOLTA_DA_SEQUENCIA` e veja passar.

    Sem a rotação todo report sai com o mesmo nibble de sequência, **o firmware
    descarta tudo menos o primeiro, e o nosso lado conta 50 "escritas aceitas"
    por segundo** — o log dizendo "escrito" com o aparelho mudo. O preço dessa
    classe de defeito já está pago por escrito nesta casa, em
    ``core/backend_pydualsense.writeReport``: *"o firmware descarta o report
    fora de sequência e o log diz 'escrito'"*.

    É a régua mais importante deste arquivo justamente porque o sintoma dela é
    o silêncio — e silêncio é o que este trabalho inteiro está tentando ler.
    """

    def test_o_nibble_gira_e_da_a_volta(self, arranjo: af.Arranjo) -> None:
        bomba = af.BombaDeSomPeloRadio(arranjo=arranjo, fonte=_fonte_infinita())
        vistos = [(bomba.um_report() or b"\x00\x00")[1] >> 4 for _ in range(20)]
        assert vistos[: af.VOLTA_DA_SEQUENCIA] == list(range(af.VOLTA_DA_SEQUENCIA))
        assert vistos[af.VOLTA_DA_SEQUENCIA :] == [0, 1, 2, 3]

    def test_o_crc_acompanha_a_sequencia(self, arranjo: af.Arranjo) -> None:
        """Dois reports com o MESMO PCM e seq diferente têm CRC diferente.

        Se o CRC fosse calculado antes do carimbo, ele ficaria válido só para o
        seq 0 — e o firmware descartaria todos os outros por CRC, que é o mesmo
        silêncio pela outra porta.
        """
        bomba = af.BombaDeSomPeloRadio(arranjo=arranjo, fonte=_fonte_infinita())
        primeiro = bomba.um_report() or b""
        segundo = bomba.um_report() or b""
        assert primeiro[-4:] != segundo[-4:]


class TestALeituraCurtaEhContadaNuncaEngolida:
    """ARRANQUE o ramo do ``pcm_curto`` e veja a bomba parecer sã com a fonte agonizando.

    Uma fonte que devolve menos que um report inteiro é o fim de todo fluxo (e
    também o gravador morrendo no meio). Descartar faria o fim sumir sem
    número; completar em silêncio sem contar faria o relatório dizer "99
    reports" sobre 99 reports de silêncio.
    """

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
    """ARRANQUE o ``if self.seco`` do :meth:`escrever` e veja o dublê explodir.

    O modo seco é o que permite medir a bomba com ela na bancada sem que nada
    saia no fio, e é o modo em que a suíte roda. Ele é o padrão de propósito.
    """

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
        """``seco=False`` sem escritor não vira escrita: não há para onde.

        Sem esta trava, quem esquecesse o `escritor` teria um `None` chamado no
        caminho quente — um `TypeError` no meio do ensaio da bancada, com ela
        do outro lado esperando som.
        """
        bomba = af.BombaDeSomPeloRadio(
            arranjo=arranjo, fonte=_fonte_infinita(), escritor=None, seco=False
        )
        assert bomba.seco is True
        bomba.rodar(segundos=0.05, agora=_relogio())
        assert bomba.contagem.escritas_aceitas_pelo_kernel == 0


class TestAEscritaRecusadaEhContadaNaoEhCrash:
    """ARRANQUE o ``except OSError`` e veja o ensaio morrer no meio da bancada.

    Um hidraw que some (controle desligado, kernel recusando o tamanho) tem de
    virar NÚMERO e parar o laço — nunca um traceback com ela do outro lado.
    """

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
    """ARRANQUE a linha de ATENÇÃO do relatório e veja a régua passar mesmo assim.

    **Esta régua não mede código, mede a frase** — e é de propósito. O número
    ``escritas_aceitas_pelo_kernel`` é exatamente o número que alguém vai citar
    para dizer "a ponte funciona", e o mapa proíbe essa conclusão com todas as
    letras. A ressalva colada ao número é a única coisa entre o relatório e a
    FALÁCIA DO CANAL QUE RESPONDE.

    Ela nasce porque esta casa já pagou o inverso: um comentário que descrevia
    o padrão proibido virou a primeira ocorrência dele. Aqui a frase é o
    produto, não o comentário.
    """

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
    """ARRANQUE o laço de :func:`fonte_de_arquivo` e veja 100% de recusa do encoder.

    Um ``read()`` de pipe devolve o que JÁ chegou. Com um único read por
    report, todo quadro sairia de tamanho variável, a libopus recusaria cada um
    (ela exige exatamente 10 ms de PCM) e a bomba contaria recusa total sobre
    uma fonte perfeitamente sã — um instrumento apontando para si mesmo.
    """

    def test_junta_os_pedacos(self) -> None:
        """O PCM chega em DOIS tempos, e a leitura tem de esperar o segundo.

        Escrever as duas metades ANTES de ler não mede nada: o pipe as junta e
        um `read` só devolve tudo. Foi assim que esta régua passou com a cura
        arrancada na primeira escrita dela — e é por isso que aqui há uma
        thread segurando a segunda metade.
        """
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
    """ARRANQUE o ``if not fonte`` e veja o instrumento ler o som da máquina dela.

    ``pw-record --target=`` vazio cai na fonte PADRÃO do sistema. Um ensaio que
    lesse dali estaria medindo o que ela está ouvindo, achando que mede o nó do
    controle — e mandaria para o rádio o áudio da máquina dela sem que ninguém
    tivesse pedido.
    """

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
    """ARRANQUE :func:`fonte_com_ritmo` do ensaio e veja 53x o fio no rádio dela.

    A bomba anda no ritmo da FONTE, e isso está certo para o monitor de um nó
    do PipeWire: pedir 20 ms de som bloqueia 20 ms. **Uma fonte sintética não
    bloqueia nada.** Medido nesta árvore em 07/09/2026, antes de qualquer
    escrita: a montagem fecha ~2.660 reports/s contra os 50/s que o degrau
    ``0x39`` pede — quatro segundos de ensaio jogariam ~10.600 reports e
    ~5,8 MB no enlace que carrega os outros três controles dela.

    Não seria um ensaio: seria uma inundação medindo a fila do kernel.
    """

    def test_cada_quadro_tem_prazo_e_o_prazo_nao_deriva(self) -> None:
        """O sono é o que FALTA para o prazo, não um intervalo fixo.

        Dormir o intervalo inteiro depois de cada quadro soma o tempo de
        codificar e escrever — o fluxo atrasa um pouco a cada volta e a deriva
        cresce sem teto. Aqui o trabalho é simulado com 4 ms por quadro e os
        sonos têm de encolher para 6, não ficar em 10.
        """
        agora = {"t": 0.0}
        sonos: list[float] = []

        def _agora() -> float:
            return agora["t"]

        def _dormir(quanto: float) -> None:
            sonos.append(round(quanto, 6))
            agora["t"] += quanto

        def _fonte(_n: int) -> bytes:
            agora["t"] += 0.004  # o trabalho de codificar e escrever
            return b"x"

        ler = af.fonte_com_ritmo(
            _fonte, ms_por_report=10, agora=_agora, dormir=_dormir
        )
        for _ in range(5):
            ler(1)
        assert sonos == [0.006, 0.006, 0.006, 0.006], sonos

    def test_quadro_atrasado_nao_dorme(self) -> None:
        """Trabalho mais longo que o intervalo não vira sono negativo.

        Sem a guarda, um `sleep` de valor negativo levantaria no meio do ensaio
        de bancada — com ela do outro lado esperando som.
        """
        agora = {"t": 0.0}
        sonos: list[float] = []

        def _fonte(_n: int) -> bytes:
            agora["t"] += 0.050  # cinco vezes o intervalo
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
        """A régua lê o FONTE do ensaio, e é o único jeito honesto.

        Provar "não inundou" exigiria escrever no aparelho dela. O que se trava
        aqui é a chamada: se alguém tirar o `fonte_com_ritmo` do caminho de
        escrita, esta régua reprova antes de a bancada ser reservada.
        """
        fonte = (REPO_ROOT / "scripts" / "ensaios" / "o_som_que_sai.py").read_text(
            encoding="utf-8"
        )
        i = fonte.index("def escrever_no_aparelho")
        j = fonte.index("def main(", i)
        assert "af.fonte_com_ritmo(" in fonte[i:j]
        assert "escritor=af.escritor_de_hidraw(fd)" in fonte[i:j]


class TestABombaNaoEscolheOArranjo:
    """ARRANQUE a obrigatoriedade do ``arranjo`` e veja um default virar escolha.

    As duas fontes publicadas divergem sobre onde o áudio mora dentro do
    ``0x39``, e uma cita a outra — não são testemunhas independentes. Um valor
    padrão aqui seria esta árvore escolhendo por ela, em silêncio, num
    argumento de palavra-chave que ninguém lê.
    """

    def test_arranjo_e_obrigatorio(self) -> None:
        with pytest.raises(TypeError):
            af.BombaDeSomPeloRadio(fonte=_fonte_infinita())  # type: ignore[call-arg]

    def test_os_dois_continuam_registrados_sem_escolha(self) -> None:
        assert {a.nome for a in af.ARRANJOS} == {"ds5dongle", "senshi"}
        for arr in af.ARRANJOS:
            assert "NÃO medido nesta bancada" in arr.de_onde_sei


# ---------------------------------------------------------------------------
# O ENSAIO DE BANCADA — a cadeia de recusas, que é o instrumento inteiro
# ---------------------------------------------------------------------------


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
    """ARRANQUE qualquer um dos degraus da cadeia e veja o ensaio escrever cedo.

    O ensaio **não é escrever**; é escrever com a orelha dela do outro lado. Um
    instrumento que escreve sem isso mede o kernel aceitando uma entrega — e o
    próprio mapa avisa que o kernel aceitou até um pacote de tamanho errado que
    era o controle negativo.

    A régua exercita as recusas COM MAC sintético e lista dublê: ela nunca
    chega perto de um aparelho.
    """

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
        """rc=3, e é o degrau que esta leva NÃO removeu.

        Ele existia antes de haver caminho de escrita; agora que há, ele é a
        única coisa entre o instrumento e um `os.write` sem ninguém ouvindo.
        """
        assert ensaio.escrever_no_aparelho(self._args(ensaio)) == 3
        saida = capsys.readouterr().out
        assert "PARADO ANTES DE ESCREVER" in saida
        assert "--eu-estou-ouvindo" in saida
        assert "NÃO é a medição" in saida

    def test_o_teto_de_segundos_e_uma_trava(self, ensaio: Any) -> None:
        """Pedir 600 s não toca 600 s no aparelho dela.

        Ela está na bancada com quatro aparelhos; um timbre que não para
        atrapalha o ensaio seguinte tanto quanto atrapalharia o nosso.
        """
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
        """CRC ruim é ``E_NADA``, e quem recusa é o dono do extrator.

        Sem CRC, rádio corrompido viraria marca no meio da janela dela.
        """
        bruto = bytearray(78)
        bruto[0] = captura.INPUT_REPORT_BT
        classe, _ = captura.classificar_report(bytes(bruto))
        assert classe == captura.E_NADA

    def test_report_vazio_nao_explode(self, captura: Any) -> None:
        assert captura.classificar_report(b"") == (captura.E_NADA, False)

    def test_o_instrumento_nao_abre_para_escrita(self, captura: Any) -> None:
        """A assinatura diz ``escrita=False``. É leitura pura, e tem de continuar.

        A régua lê o FONTE porque não há como provar "não escreveu" sem um
        aparelho: o que se trava aqui é o argumento que autoriza a escrita.
        """
        fonte = (
            REPO_ROOT / "scripts" / "ensaios" / "a_captura_armada_do_som_no_radio.py"
        ).read_text(encoding="utf-8")
        assert "abrir_no_hidraw(caminho, escrita=False)" in fonte
        assert "os.write" not in fonte
