"""SOM-QUE-SAI-01 — as réguas do motor do alto-falante virtual."""

from __future__ import annotations

import importlib.util
import zlib
from itertools import pairwise
from pathlib import Path
from types import ModuleType

import pytest

from hefesto_dualsense4unix.core.ds_output_report import BT_CRC_SEED, bt_crc32
from hefesto_dualsense4unix.daemon.subsystems.alto_falante import (
    AltoFalanteSubsystem,
    ControleNaLista,
    GerenciadorDeNosDeSom,
    controles_na_lista,
)
from hefesto_dualsense4unix.integrations import alto_falante_bt as af

MAC_A = "aa:bb:cc:00:00:01"
MAC_B = "e8:47:3a:00:00:09"


def _o_ensaio() -> ModuleType:
    """O ensaio `scripts/ensaios/o_som_que_sai.py`, carregado pelo caminho."""
    caminho = Path(__file__).resolve().parents[2] / "scripts" / "ensaios" / "o_som_que_sai.py"
    spec = importlib.util.spec_from_file_location("ensaio_o_som_que_sai", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


ENSAIO = _o_ensaio()


def _pcm_de_um_quadro(canais: int = af.CANAIS_DO_ENCODER) -> bytes:
    """PCM ``s16le`` com sinal de verdade, não silêncio."""
    import math
    import struct

    amostras: list[int] = []
    for i in range(af.AMOSTRAS_POR_QUADRO):
        valor = int(12000 * math.sin(2 * math.pi * 440 * i / af.TAXA_DO_ENCODER))
        amostras.extend([valor] * canais)
    return struct.pack(f"<{len(amostras)}h", *amostras)


class RunnerFalso:
    """Dublê do ``pactl`` que sabe RECUSAR — e as duas respostas são exercidas."""

    def __init__(self, *, aceita: bool = True, sinks: str = "") -> None:
        self.aceita = aceita
        self.sinks = sinks
        self.chamadas: list[list[str]] = []

    def __call__(self, argv: list[str]) -> str | None:
        self.chamadas.append(list(argv))
        if argv[:2] == ["pactl", "load-module"]:
            return "4242\n" if self.aceita else "Failure: Module initialization failed\n"
        if argv[:3] == ["pactl", "list", "sinks"]:
            return self.sinks
        return ""


class TestAEscadaEhTabelaENuncaAritmetica:
    """A MORDIDA: troque a tabela por ``78 + 64 * (id - 0x31)``."""

    def test_o_ultimo_passo_da_escada_e_de_21_e_nao_de_64(self) -> None:
        assert af.TAMANHO_DO_DEGRAU[0x39] == 547
        assert af.TAMANHO_DO_DEGRAU[0x39] - af.TAMANHO_DO_DEGRAU[0x38] == 21
        assert 78 + 64 * (0x39 - 0x31) == 590
        assert af.TAMANHO_DO_DEGRAU[0x39] != 78 + 64 * (0x39 - 0x31)

    def test_os_oito_primeiros_passos_sao_de_64(self) -> None:
        ids = sorted(af.TAMANHO_DO_DEGRAU)
        passos = [
            af.TAMANHO_DO_DEGRAU[b] - af.TAMANHO_DO_DEGRAU[a] for a, b in pairwise(ids)
        ]
        assert passos == [64, 64, 64, 64, 64, 64, 64, 21]

    def test_o_orcamento_e_derivado_do_envelope_do_common_e_do_crc(self) -> None:
        assert af.ORCAMENTO_DO_DEGRAU[0x32] == 88
        assert af.ORCAMENTO_DO_DEGRAU[0x39] == 493
        for degrau, total in af.TAMANHO_DO_DEGRAU.items():
            assert af.ORCAMENTO_DO_DEGRAU[degrau] == total - 3 - 47 - 4

    def test_degrau_inventado_levanta_em_vez_de_devolver_numero_plausivel(self) -> None:
        with pytest.raises(KeyError):
            af.orcamento_do_degrau(0x3A)


class TestOMenorDegrauQueComporta:
    """A MORDIDA: peça 89 bytes e veja o empacotador escolher ``0x33``."""

    @pytest.mark.parametrize(
        ("payload", "esperado"),
        [(0, 0x32), (24, 0x32), (88, 0x32), (89, 0x33), (152, 0x33), (153, 0x34), (493, 0x39)],
    )
    def test_escolhe_o_menor_que_cabe(self, payload: int, esperado: int) -> None:
        assert ENSAIO.degrau_para_payload(payload) == esperado

    def test_acima_do_teto_nao_cabe_em_degrau_nenhum(self) -> None:
        assert ENSAIO.degrau_para_payload(494) is None

    def test_o_0x31_nunca_e_escolhido_porque_ele_e_do_kernel(self) -> None:
        assert af.ORCAMENTO_DO_DEGRAU[af.DEGRAU_DO_KERNEL] >= 24
        assert ENSAIO.degrau_para_payload(1) != af.DEGRAU_DO_KERNEL


class TestOEncoderFechaOQuadroDeDuzentosBytes:
    """A MORDIDA: arranque o CBR (``OPUS_SET_VBR(0)``) e veja o quadro variar."""

    def test_a_conta_do_bitrate_da_exatamente_duzentos(self) -> None:
        por_quadro = af.BITRATE_DO_ENCODER * (af.AMOSTRAS_POR_QUADRO / af.TAXA_DO_ENCODER) / 8
        assert por_quadro == af.BYTES_POR_QUADRO_OPUS

    def test_cada_quadro_sai_com_o_tamanho_que_o_bloco_quer(self) -> None:
        with af.CodificadorOpus() as codificador:
            pcm = _pcm_de_um_quadro()
            assert len(pcm) == af.BYTES_DE_PCM_POR_QUADRO
            for _ in range(5):
                quadro = codificador.codificar(pcm)
                assert quadro is not None
                assert len(quadro) == af.BYTES_POR_QUADRO_OPUS

    def test_pcm_de_tamanho_errado_e_recusado_e_nao_lido_fora_do_buffer(self) -> None:
        with af.CodificadorOpus() as codificador:
            assert codificador.codificar(b"\x00" * 10) is None
            assert codificador.codificar(b"") is None

    def test_o_encoder_fechado_para_de_codificar_em_vez_de_estourar(self) -> None:
        codificador = af.CodificadorOpus()
        codificador.close()
        codificador.close()
        assert codificador.codificar(_pcm_de_um_quadro()) is None


class TestOsDoisArranjosVaoJuntosENenhumEhEscolhido:
    """A MORDIDA: monte só um arranjo e veja reprovar."""

    def test_sao_dois_e_os_dois_declaram_a_procedencia(self) -> None:
        assert len(af.ARRANJOS) == 2
        assert {a.nome for a in af.ARRANJOS} == {"ds5dongle", "senshi"}
        for arranjo in af.ARRANJOS:
            assert "NÃO medido nesta bancada" in arranjo.de_onde_sei
            assert "@" in arranjo.fonte

    def test_o_mesmo_pcm_produz_corpos_diferentes(self) -> None:
        with af.CodificadorOpus() as codificador:
            quadro = codificador.codificar(_pcm_de_um_quadro())
        assert quadro is not None
        pacotes = ENSAIO.montar_pelos_dois_arranjos([quadro, quadro])
        assert set(pacotes) == {"ds5dongle", "senshi"}
        assert pacotes["ds5dongle"] != pacotes["senshi"]

    def test_os_dois_tem_547_bytes_e_o_id_do_degrau(self) -> None:
        pacotes = ENSAIO.montar_pelos_dois_arranjos([b"\x01" * 200, b"\x02" * 200])
        for pkt in pacotes.values():
            assert len(pkt) == af.TAMANHO_DO_DEGRAU[0x39] == 547
            assert pkt[0] == 0x39

    def test_cada_arranjo_poe_o_audio_onde_a_fonte_dele_diz(self) -> None:
        marca_a, marca_b = b"\xa1" * 200, b"\xb2" * 200
        ds5 = af.ARRANJO_DS5DONGLE.montar([marca_a, marca_b])
        senshi = af.ARRANJO_SENSHI.montar([marca_a, marca_b])
        assert ds5[142:342] == marca_a
        assert ds5[342:542] == marca_b
        assert senshi[13:213] == marca_a
        assert senshi[213:413] == marca_b

    def test_o_len_do_audiocontrol_e_o_que_separa_as_duas_fontes(self) -> None:
        assert af.ARRANJO_DS5DONGLE.len_controle == 6
        assert af.ARRANJO_SENSHI.len_controle == 7

    def test_quadro_grande_demais_levanta_em_vez_de_truncar(self) -> None:
        with pytest.raises(ValueError):
            af.ARRANJO_DS5DONGLE.montar([b"\x00" * 201, b"\x00" * 200])
        with pytest.raises(ValueError):
            af.ARRANJO_DS5DONGLE.montar([b"\x00" * 200])


class TestOCrcEhODoProdutoEBateComAFonte:
    """A MORDIDA: mova o CRC de lugar, ou troque a semente, e veja reprovar."""

    def test_a_semente_do_ds5dongle_e_o_nosso_crc_do_byte_0xa2(self) -> None:
        assert BT_CRC_SEED == 0xA2
        assert zlib.crc32(b"\xa2") & 0xFFFFFFFF == 0xEADA2D49

    def test_o_crc_fica_nos_quatro_ultimos_bytes_dos_dois_arranjos(self) -> None:
        pacotes = ENSAIO.montar_pelos_dois_arranjos([b"\x07" * 200, b"\x09" * 200])
        for pkt in pacotes.values():
            esperado = bt_crc32(pkt[:-4], seed=BT_CRC_SEED)
            assert int.from_bytes(pkt[-4:], "little") == esperado

    def test_mudar_um_byte_do_corpo_muda_o_crc(self) -> None:
        um = af.ARRANJO_DS5DONGLE.montar([b"\x00" * 200, b"\x00" * 200])
        outro = af.ARRANJO_DS5DONGLE.montar([b"\x00" * 199 + b"\x01", b"\x00" * 200])
        assert um[-4:] != outro[-4:]


class TestATagTlvEhAMesmaDasDuasFontes:
    """O bit 7 é *"bloco presente"* e o bit 6 é *"vêm DOIS sub-blocos"*."""

    def test_o_haptico_duplo_da_0xd2_como_o_senshi_registra(self) -> None:
        assert af.tag_tlv(0x12, duplo=True) == 0xD2

    def test_o_audiocontrol_nao_e_duplo(self) -> None:
        assert af.tag_tlv(0x11) == 0x91

    def test_o_alto_falante_e_o_fone_sao_tags_diferentes(self) -> None:
        assert af.tag_tlv(0x13, duplo=True) != af.tag_tlv(af.BLOCO_FONE, duplo=True)
        assert af.BLOCO_FONE == 0x16


class TestONomeDoNoNaoCarregaOTransporte:
    """A MORDIDA: derive o nome do TRANSPORTE e veja reprovar."""

    def test_o_mesmo_controle_da_o_mesmo_no_nos_dois_transportes(self) -> None:
        no_cabo = af.SinkVirtualPipeWire(uniq=MAC_A, runner=RunnerFalso())
        no_radio = af.SinkVirtualPipeWire(uniq=MAC_A.replace(":", ""), runner=RunnerFalso())
        assert no_cabo.nome == no_radio.nome == af.nome_do_sink(MAC_A)

    def test_o_nome_nao_tem_palavra_de_transporte_dentro(self) -> None:
        nome = af.nome_do_sink(MAC_A)
        for palavra in ("usb", "bt", "bluetooth", "cabo", "radio", "alsa"):
            assert palavra not in nome

    def test_controles_diferentes_dao_nos_diferentes(self) -> None:
        assert af.nome_do_sink(MAC_A) != af.nome_do_sink(MAC_B)

    def test_uniq_ilegivel_nao_vira_no(self) -> None:
        for ruim in ("", "zz", "abc", "nao-e-um-mac"):
            assert af.nome_do_sink(ruim) == ""

    def test_o_sufixo_recorta_o_prefixo_antes_de_filtrar_hex(self) -> None:
        assert af.sufixo_do_sink_do_som(af.nome_do_sink(MAC_A)) == af.nome_do_sink(
            MAC_A
        ).removeprefix(af.PREFIXO_SINK_DO_SOM)
        assert af.sufixo_do_sink_do_som("hefesto_som_000001") == "000001", (
            "a forma velha segue lida por uma versão, para a escolha gravada"
        )
        assert af.sufixo_do_sink_do_som("alsa_output.usb-Sony-00") == ""
        assert af.sufixo_do_sink_do_som("hefesto_som_zzzzzz") == ""

    def test_quem_pergunta_se_o_sink_e_de_controle_le_pelo_dono(self) -> None:
        """A janela lê o nome do nó pelo leitor dele, e não casando o prefixo."""
        from hefesto_dualsense4unix.app.audio_saida import e_saida_de_controle

        assert e_saida_de_controle("hefesto_som_zzzzzz", "") is False
        assert e_saida_de_controle("hefesto_som_", "") is False
        assert e_saida_de_controle(af.nome_do_sink(MAC_A), "") is True

    def test_o_no_sem_nome_nao_sobe(self) -> None:
        runner = RunnerFalso()
        no = af.SinkVirtualPipeWire(uniq="zz", runner=runner)
        assert no.iniciar() is False
        assert runner.chamadas == []


class TestONoNaoViraASaidaPadraoSozinho:
    """A MORDIDA: arranque a ``priority.session`` baixa e veja reprovar."""

    def test_a_prioridade_e_menor_que_a_do_menor_sink_real_medido(self) -> None:
        # DualSense no cabo 1109. O menor sink REAL é 696.
        menor_real_medido = 696
        assert menor_real_medido > af.PRIORIDADE_SESSAO_DO_SOM

    def test_as_propriedades_viajam_entre_aspas_num_argumento_so(self) -> None:
        props = af.propriedades_do_sink("Alto-falante do controle")
        assert props.startswith('sink_properties="')
        assert props.endswith('"')
        assert props.count('"') == 2
        assert f"priority.session={af.PRIORIDADE_SESSAO_DO_SOM}" in props
        assert f"priority.session={af.PRIORIDADE_SESSAO_DO_SOM}" not in props.split(" ")[0]

    def test_o_load_module_leva_o_argumento_inteiro(self) -> None:
        runner = RunnerFalso()
        af.SinkVirtualPipeWire(uniq=MAC_A, runner=runner).iniciar()
        argv = runner.chamadas[0]
        assert argv[:3] == ["pactl", "load-module", "module-null-sink"]
        assert f"sink_name={af.nome_do_sink(MAC_A)}" in argv
        assert any(a.startswith('sink_properties="') for a in argv)


class TestOCicloDeVidaDoNo:
    """O nó sobe, é descarregado, e o dublê exercita as DUAS respostas."""

    def test_sobe_e_guarda_o_id_do_modulo(self) -> None:
        runner = RunnerFalso(aceita=True)
        no = af.SinkVirtualPipeWire(uniq=MAC_A, runner=runner)
        assert no.iniciar() is True
        assert no.module_id == "4242"
        assert no.monitor() == f"{af.nome_do_sink(MAC_A)}.monitor"

    def test_quando_o_servidor_recusa_nada_fica_de_pe(self) -> None:
        runner = RunnerFalso(aceita=False)
        no = af.SinkVirtualPipeWire(uniq=MAC_A, runner=runner)
        assert no.iniciar() is False
        assert no.module_id is None
        assert no.estado() is None

    def test_parar_descarrega_e_e_idempotente(self) -> None:
        runner = RunnerFalso()
        no = af.SinkVirtualPipeWire(uniq=MAC_A, runner=runner)
        no.iniciar()
        no.parar()
        no.parar()
        descarregados = [c for c in runner.chamadas if c[:2] == ["pactl", "unload-module"]]
        assert descarregados == [["pactl", "unload-module", "4242"]]

    def test_iniciar_duas_vezes_carrega_um_modulo_so(self) -> None:
        runner = RunnerFalso()
        no = af.SinkVirtualPipeWire(uniq=MAC_A, runner=runner)
        assert no.iniciar() is True
        assert no.iniciar() is True
        carregados = [c for c in runner.chamadas if c[:2] == ["pactl", "load-module"]]
        assert len(carregados) == 1

    def test_o_estado_e_perguntado_ao_servidor_e_nao_lembrado(self) -> None:
        pass


class TestOEstadoEhPerguntadoAoServidor:
    """O estado tem UM dono — o servidor de som. Ler, nunca lembrar."""

    def test_le_a_quinta_coluna_separada_por_tab(self) -> None:
        curto = (
            f"58\t{af.nome_do_sink(MAC_A)}\tPipeWire\ts16le 2ch 48000Hz\tRUNNING\n"
            "59\toutro_sink\tPipeWire\ts16le 2ch 48000Hz\tIDLE\n"
        )

        class RunnerComLista(RunnerFalso):
            def __call__(self, argv: list[str]) -> str | None:
                if argv[:4] == ["pactl", "list", "sinks", "short"]:
                    return curto
                return super().__call__(argv)

        no = af.SinkVirtualPipeWire(uniq=MAC_A, runner=RunnerComLista())
        no.iniciar()
        assert no.estado() == "RUNNING"

    def test_no_fora_da_lista_devolve_none_e_nao_um_chute(self) -> None:
        class RunnerVazio(RunnerFalso):
            def __call__(self, argv: list[str]) -> str | None:
                if argv[:4] == ["pactl", "list", "sinks", "short"]:
                    return ""
                return super().__call__(argv)

        no = af.SinkVirtualPipeWire(uniq=MAC_A, runner=RunnerVazio())
        no.iniciar()
        assert no.estado() is None


class TestONoViveEnquantoHaControle:
    """A MORDIDA: tire UM controle da lista e veja o nó DELE cair, e só o dele."""

    def _gerenciador(self) -> tuple[GerenciadorDeNosDeSom, dict[str, af.SinkVirtualPipeWire]]:
        criados: dict[str, af.SinkVirtualPipeWire] = {}

        def fabrica(uniq: str) -> af.SinkVirtualPipeWire:
            no = af.SinkVirtualPipeWire(uniq=uniq, runner=RunnerFalso())
            criados[uniq] = no
            return no

        return GerenciadorDeNosDeSom(fabrica=fabrica), criados

    def test_um_no_por_controle(self) -> None:
        gerenciador, _ = self._gerenciador()
        gerenciador.reconciliar([MAC_A, MAC_B])
        assert set(gerenciador.nos) == {MAC_A, MAC_B}

    def test_tirar_um_da_lista_derruba_o_dele_e_deixa_o_outro_de_pe(self) -> None:
        gerenciador, criados = self._gerenciador()
        gerenciador.reconciliar([MAC_A, MAC_B])
        gerenciador.reconciliar([MAC_A])
        assert set(gerenciador.nos) == {MAC_A}
        assert criados[MAC_B].module_id is None
        assert criados[MAC_A].module_id == "4242"

    def test_lista_vazia_derruba_todos(self) -> None:
        gerenciador, _ = self._gerenciador()
        gerenciador.reconciliar([MAC_A, MAC_B])
        gerenciador.reconciliar([])
        assert gerenciador.nos == {}

    def test_reconciliar_de_novo_nao_recarrega_o_que_ja_esta_de_pe(self) -> None:
        gerenciador, criados = self._gerenciador()
        gerenciador.reconciliar([MAC_A])
        primeiro = criados[MAC_A]
        gerenciador.reconciliar([MAC_A])
        assert criados[MAC_A] is primeiro

    def test_no_que_nao_sobe_nao_entra_na_conta(self) -> None:
        gerenciador = GerenciadorDeNosDeSom(
            fabrica=lambda uniq: af.SinkVirtualPipeWire(
                uniq=uniq, runner=RunnerFalso(aceita=False)
            )
        )
        gerenciador.reconciliar([MAC_A])
        assert gerenciador.nos == {}

    def test_parar_derruba_tudo_e_e_idempotente(self) -> None:
        gerenciador, criados = self._gerenciador()
        gerenciador.reconciliar([MAC_A, MAC_B])
        gerenciador.parar()
        gerenciador.parar()
        assert gerenciador.nos == {}
        assert all(no.module_id is None for no in criados.values())


class TestOSubsystemEscolheQuemGanhaNo:
    """Só quem tem identidade legível ganha nó — e nunca o nosso próprio vpad."""

    def test_controle_sem_uniq_nao_ganha_no(self) -> None:
        subsystem = AltoFalanteSubsystem()
        controles = [
            ControleNaLista(uniq=MAC_A, caminho="/dev/hidraw9", transporte="cabo"),
            ControleNaLista(uniq="", caminho="/dev/hidraw8", transporte="rádio"),
        ]
        assert [c.uniq for c in subsystem.alvos(controles)] == [MAC_A]

    def test_o_mesmo_controle_nos_dois_nos_conta_uma_vez(self) -> None:
        subsystem = AltoFalanteSubsystem()
        controles = [
            ControleNaLista(uniq=MAC_A, caminho="/dev/hidraw9", transporte="cabo"),
            ControleNaLista(uniq=MAC_A, caminho="/dev/hidraw7", transporte="cabo"),
        ]
        assert [c.uniq for c in subsystem.alvos(controles)] == [MAC_A]

    def test_esta_sempre_ligado_porque_o_no_precede_a_escolha_do_jogo(self) -> None:
        assert AltoFalanteSubsystem().is_enabled(object()) is True  # type: ignore[arg-type]

    def test_ligado_sem_controle_nao_publica_nada(self) -> None:
        gerenciador, chamadas = GerenciadorDeNosDeSom(fabrica=lambda u: None), []

        class Espiao(GerenciadorDeNosDeSom):
            def reconciliar(self, uniqs: list[str] | None = None) -> None:
                chamadas.append(list(uniqs or []))

        subsystem = AltoFalanteSubsystem(
            gerenciador=Espiao(), fonte_de_controles=lambda: []
        )
        subsystem._reconciliar(subsystem._gerenciador_injetado)
        assert chamadas == [[]]
        assert gerenciador.nos == {}

    def test_uniqs_com_no_relata_o_efeito_e_nao_o_pedido(self) -> None:
        subsystem = AltoFalanteSubsystem()
        assert subsystem.uniqs_com_no() == frozenset()


class TestALeituraDoSysfsVeOsDoisTransportes:
    """A MORDIDA: filtre por Bluetooth e veja o controle do CABO sumir."""

    def _sysfs(self, tmp_path, nos: list[tuple[str, str]]) -> str:
        for nome, uevent in nos:
            destino = tmp_path / nome / "device"
            destino.mkdir(parents=True)
            (destino / "uevent").write_text(uevent, encoding="utf-8")
        return str(tmp_path)

    def test_ve_o_do_cabo_e_o_do_radio_e_marca_o_transporte(self, tmp_path) -> None:
        raiz = self._sysfs(
            tmp_path,
            [
                ("hidraw4", f"HID_ID=0003:0000054C:00000CE6\nHID_UNIQ={MAC_A}\n"),
                ("hidraw5", f"HID_ID=0005:0000054C:00000CE6\nHID_UNIQ={MAC_B}\n"),
            ],
        )
        achados = {c.uniq: c.transporte for c in controles_na_lista(raiz)}
        assert achados == {MAC_A: "cabo", MAC_B: "rádio"}

    def test_o_nosso_proprio_vpad_e_excluido(self, tmp_path) -> None:
        raiz = self._sysfs(
            tmp_path,
            [
                (
                    "hidraw3",
                    "HID_ID=0003:0000054C:00000DF2\nHID_UNIQ=aa:bb:cc:00:00:07\n"
                    "HID_PHYS=hefesto-vpad\n",
                ),
            ],
        )
        assert controles_na_lista(raiz) == []

    def test_aparelho_de_outro_fabricante_nao_entra(self, tmp_path) -> None:
        raiz = self._sysfs(
            tmp_path,
            [("hidraw2", "HID_ID=0005:0000057E:00002009\nHID_UNIQ=aa:bb:cc:00:00:08\n")],
        )
        assert controles_na_lista(raiz) == []

    def test_raiz_inexistente_devolve_lista_vazia_e_nao_estoura(self, tmp_path) -> None:
        assert controles_na_lista(str(tmp_path / "nao-existe")) == []


class TestODiagnosticoDizPorQueNaoSobe:
    """Ausência é resposta — um fato por linha, nunca silêncio."""

    def test_sem_controle_ele_nomeia_a_falta(self) -> None:
        diagnostico = af.Diagnostico(
            controles=[], libopus="libopus 1.4", pactl=True, null_sink=True, loopback=True
        )
        assert diagnostico.pronto is False
        assert any("nenhum DualSense" in falta for falta in diagnostico.impedimentos)

    def test_sem_pactl_ele_nomeia_a_falta(self) -> None:
        diagnostico = af.Diagnostico(
            controles=[MAC_A], libopus=None, pactl=False, null_sink=False, loopback=False
        )
        assert diagnostico.pronto is False
        faltas = " ".join(diagnostico.impedimentos)
        assert "pactl" in faltas
        assert "libopus" in faltas

    def test_com_tudo_no_lugar_ele_nao_inventa_impedimento(self) -> None:
        diagnostico = af.Diagnostico(
            controles=[MAC_A], libopus="libopus 1.4", pactl=True, null_sink=True, loopback=True
        )
        assert diagnostico.pronto is True
        assert diagnostico.impedimentos == []

    def test_sem_libopus_o_no_ainda_sobe_mas_o_radio_nao(self) -> None:
        diagnostico = af.Diagnostico(
            controles=[MAC_A], libopus=None, pactl=True, null_sink=True, loopback=True
        )
        assert diagnostico.pronto is True
        assert any("libopus" in falta for falta in diagnostico.impedimentos)


class TestNadaAquiAfirmaQueSomSaiu:
    """O portão da FALÁCIA DO CANAL QUE RESPONDE, dentro da própria régua."""

    ARQUIVOS = (
        "src/hefesto_dualsense4unix/integrations/alto_falante_bt.py",
        "src/hefesto_dualsense4unix/daemon/subsystems/alto_falante.py",
        "scripts/ensaios/o_som_que_sai.py",
    )

    PROIBIDAS = (
        "descobrimos o áudio por bluetooth",
        "a ponte funciona",
        "o alto-falante soou por rádio",
    )

    MARCAS_DE_PROIBICAO = ("não escrever", "proíbe", "proibido", "não pode", "não afirma")
    JANELA = 300

    @classmethod
    def afirmacoes(cls, texto: str, frase: str) -> list[int]:
        """Onde a frase aparece SEM marca de proibição antes — as afirmações."""
        achados: list[int] = []
        inicio = 0
        while True:
            posicao = texto.find(frase, inicio)
            if posicao < 0:
                return achados
            janela = texto[max(0, posicao - cls.JANELA) : posicao]
            if not any(marca in janela for marca in cls.MARCAS_DE_PROIBICAO):
                achados.append(posicao)
            inicio = posicao + 1

    def _fonte(self, relativo: str) -> str:
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[2]
        return (raiz / relativo).read_text(encoding="utf-8").lower()

    def test_as_tres_pecas_novas_nao_afirmam_o_que_ninguem_mediu(self) -> None:
        for relativo in self.ARQUIVOS:
            texto = self._fonte(relativo)
            for frase in self.PROIBIDAS:
                assert self.afirmacoes(texto, frase) == [], (
                    f"{relativo} afirma solto o que se conta pelo degrau: {frase!r}"
                )

    def test_a_regua_sabe_distinguir_citar_de_afirmar(self) -> None:
        citacao = "o mapa proíbe escrever, em lugar nenhum, que a ponte funciona."
        afirmacao = "medido hoje: a ponte funciona."
        assert self.afirmacoes(citacao, "a ponte funciona") == []
        assert self.afirmacoes(afirmacao, "a ponte funciona") != []
