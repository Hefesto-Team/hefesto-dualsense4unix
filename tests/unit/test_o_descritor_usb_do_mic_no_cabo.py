"""MIC-CABO-SPDIF-01 — o descritor USB responde «é S/PDIF?», e a resposta é NÃO.

A porta de captura que o PipeWire mostrava em 17/09/2026 chamava-se
`iec958-stereo-input` e dizia «Entrada digital S/PDIF». A pergunta da sprint era
se o aparelho expõe mesmo o microfone por um endpoint digital.

**Quem responde é o descritor, não a tela do sistema.** O DualSense declara, com
as letras do padrão UAC, um terminal de entrada **0x0402 («Headset»)**; os dois
códigos que significariam digital — `0x0602` («Digital audio interface») e
`0x0605` («S/PDIF interface») — não aparecem em lugar nenhum. A palavra `iec958`
é invenção do host: o aparelho falta na tabela
`cards.USB-Audio.pcm.iec958_device` do `alsa-lib`, então `iec958:CARD=…` cai no
`default 0` e **é** `hw:CARD,0` — o mesmo e único PCM da placa
(`/proc/asound/pcm` da placa do DualSense traz UMA linha).

O QUE ESTES TESTES MEDEM, e por que eles não precisam do aparelho: a leitura é
sobre a gravação de `tests/fixtures/mic-cabo/descritores-usb-dualsense-*.bin`,
245 bytes tirados de `/sys/bus/usb/devices/<X>/descriptors` em 20/09/2026. O
valor vem do aparelho; só o NOME de cada código vem da tabela do padrão, que
mora dentro do instrumento. Um `--descritor` que digitasse «0x0402 é Headset»
não mediria nada.

A MORDIDA de cada régua está escrita na própria régua.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]
ENSAIO = RAIZ / "scripts" / "ensaios" / "o_caminho_do_mic_no_cabo.py"
FIXTURE = (
    RAIZ / "tests" / "fixtures" / "mic-cabo"
    / "descritores-usb-dualsense-2026-09-20.bin"
)


def _carregar() -> ModuleType:
    """Importa o ensaio pelo caminho — ele mora em `scripts/`, fora do pacote."""
    spec = importlib.util.spec_from_file_location("ensaio_mic_no_cabo", ENSAIO)
    if spec is None or spec.loader is None:  # pragma: no cover - ambiente quebrado
        pytest.skip(f"não deu para carregar {ENSAIO}")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


pytestmark = [
    pytest.mark.skipif(not ENSAIO.exists(), reason="o ensaio do cabo não está aqui"),
    pytest.mark.skipif(not FIXTURE.exists(), reason="o descritor gravado não está aqui"),
]


@pytest.fixture(scope="module")
def ensaio() -> ModuleType:
    return _carregar()


@pytest.fixture(scope="module")
def unidades(ensaio: ModuleType) -> dict[int, dict]:
    achadas, _fluxo = ensaio._ler_uac(FIXTURE.read_bytes())
    return achadas


class TestOQueOAparelhoDeclara:
    def test_a_captura_sai_por_um_terminal_headset(
        self, ensaio: ModuleType, unidades: dict[int, dict]
    ) -> None:
        """O veredito da sprint, medido: 0x0402, «Headset».

        MORDIDA: faça `_terminal_da_captura` devolver o primeiro terminal de
        entrada em vez de seguir a corrente a partir do `USB Streaming` de
        SAÍDA. Ele devolve 0x0101 (a unidade 1, que é a saída de áudio PARA o
        controle) e este teste reprova — que é o ponto: o instrumento tem de
        SEGUIR o que o descritor liga, nunca escolher pelo índice.
        """
        codigo = ensaio._terminal_da_captura(unidades)
        assert codigo == 0x0402, f"esperava 0x0402, veio {codigo!r}"
        assert ensaio._nome_do_terminal(codigo) == "Headset"

    def test_nenhum_terminal_declara_interface_digital(
        self, ensaio: ModuleType, unidades: dict[int, dict]
    ) -> None:
        """A pergunta do enunciado, fechada.

        MORDIDA: acrescente 0x0101 (USB Streaming) à lista de tipos digitais —
        o descritor tem dois deles, o teste passa a achar digital e reprova.
        `USB Streaming` é o fluxo para o host, não uma interface S/PDIF.
        """
        digitais = [
            u["terminal"] for u in unidades.values()
            if u["terminal"] in ensaio._TIPOS_DIGITAIS
        ]
        assert digitais == [], (
            "o descritor não declara 0x0602 nem 0x0605; se declarar, a palavra "
            f"«S/PDIF» deixa de ser rótulo do host. Achados: {digitais!r}"
        )

    def test_o_microfone_e_um_par_de_verdade(self, unidades: dict[int, dict]) -> None:
        """Dois canais, FL|FR — e é isso que torna o remix 2→1 uma MÉDIA.

        O `wChannelConfig` do terminal de captura é 0x0003 (front-left |
        front-right). Não é mono duplicado: a média `(L+R)/2` de dois
        microfones melhora o SNR em cerca de 3 dB, e por isso a H2 do ensaio
        («o remix que ninguém escolheu») saiu de candidata forte.
        """
        captura = [u for u in unidades.values() if u["terminal"] == 0x0402]
        assert len(captura) == 1, "há de haver exatamente um terminal de captura"
        assert captura[0]["canais"] == 2
        assert captura[0]["mapa"] == 0x0003

    def test_a_saida_e_de_quatro_canais(self, unidades: dict[int, dict]) -> None:
        """E ela é a razão de trocar o perfil de ENTRADA mexer na saída dela.

        0x0033 = FL|FR|RL|RR. Os canais 3-4 são os motores da háptica
        (HAPTICA-NATIVA-01): mexer no perfil da placa para caçar microfone
        mexe na vibração no mesmo ato.
        """
        entrada_usb = [u for u in unidades.values() if u["terminal"] == 0x0101]
        origem = [u for u in entrada_usb if u["tipo"] == "entrada"]
        assert len(origem) == 1
        assert origem[0]["canais"] == 4
        assert origem[0]["mapa"] == 0x0033

    def test_o_ganho_de_captura_controla_os_dois_canais_juntos(
        self, unidades: dict[int, dict]
    ) -> None:
        """Por que o `amixer` mostra `Mono: Capture` e não há balanço L/R.

        A Feature Unit que nasce do terminal de captura declara **dois** bytes
        de `bmaControls`: o *master*, com mute+volume, e UM byte por canal, que
        é zero. É essa unidade que carrega o `Headset Capture Volume`,
        0…+48 dB.

        **DOIS, e não três** — o terminal tem dois canais, e o padrão pediria
        um byte por canal além do master. O aparelho declara um só
        (`bLength=9`, `bmaControls=03 00`), e é o que ele declara que o host
        lê. Medido no descritor gravado, 20/09/2026.

        MORDIDA 1: troque a unidade lida (a de fonte 4) pela de fonte 1 — o
        `bmaControls` tem cinco bytes em vez de dois e o teste reprova. As duas
        Feature Units existem e são de coisas diferentes.

        MORDIDA 2: acrescente um `0x00` ao fim do `bmaControls` desta unidade.
        Sem a conta do COMPRIMENTO, um byte a mais de valor zero passa
        despercebido — e foi exatamente assim que a transcrição do descritor
        ganhou o `iFeature` como se fosse controle de canal.
        """
        ganhos = [u for u in unidades.values() if u["tipo"] == "ganho"]
        do_mic = [u for u in ganhos if u["fonte"] == 4]
        assert len(do_mic) == 1, f"uma Feature Unit alimentada pelo 0x0402; achei {ganhos!r}"
        controles = do_mic[0]["controles"]
        assert len(controles) == 2, (
            "o aparelho declara master + UM byte de canal; um byte a mais "
            f"significa que o `iFeature` entrou junto. Veio {controles!r}"
        )
        assert controles[0] == 0x03, "master com mute+volume"
        assert set(controles[1:]) == {0x00}, (
            "o byte POR CANAL é zero — por isso não há balanço L/R a ajustar"
        )

    def test_a_feature_unit_da_saida_nao_se_confunde_com_a_do_microfone(
        self, unidades: dict[int, dict]
    ) -> None:
        """As duas existem, e a do alto-falante é a de CINCO bytes.

        `bLength=12`, `bmaControls=03 00 00 00 00` — master mais quatro canais,
        que são os quatro da saída (FL|FR e os dois motores da háptica). Ela
        fica aqui escrita com o comprimento porque a transcrição de 17/09
        contava seis: o último byte é o `iFeature`, e não controla canal nenhum.
        """
        da_saida = [
            u for u in unidades.values()
            if u["tipo"] == "ganho" and u["fonte"] == 1
        ]
        assert len(da_saida) == 1
        controles = da_saida[0]["controles"]
        assert len(controles) == 5, f"master + quatro canais; veio {controles!r}"
        assert controles[0] == 0x03
        assert set(controles[1:]) == {0x00}


class TestOInstrumentoNaoInventa:
    def test_lixo_nao_vira_veredito(self, ensaio: ModuleType) -> None:
        """Bytes que não são descritor não podem produzir um terminal.

        MORDIDA: faça `_ler_uac` seguir em frente com `bLength` zero — o laço
        nunca anda, o instrumento trava, e um instrumento travado é pior que um
        vermelho.
        """
        unidades, fluxo = ensaio._ler_uac(b"\x00\x00\x00\x00")
        assert unidades == {}
        assert fluxo == []
        assert ensaio._terminal_da_captura(unidades) is None

    def test_descritor_truncado_no_meio_nao_estoura(self, ensaio: ModuleType) -> None:
        """Meio descritor é resposta parcial, nunca exceção.

        Uma leitura de `/sys` pode vir curta. O instrumento para no último
        descritor inteiro — e quem chama distingue «não achei» de «não é
        S/PDIF», que é a diferença entre não saber e saber.
        """
        bruto = FIXTURE.read_bytes()
        unidades, _ = ensaio._ler_uac(bruto[: len(bruto) // 2])
        assert isinstance(unidades, dict)

    def test_o_nome_de_um_codigo_fora_da_tabela_e_declarado(
        self, ensaio: ModuleType
    ) -> None:
        """Código desconhecido não pode virar nome bonito por acidente."""
        assert ensaio._nome_do_terminal(0x0EEE) == "(fora da tabela do padrão)"
