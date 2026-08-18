"""A cura da fonte padrão não pode eleger uma entrada sem porta usável.

FONTE-PADRÃO-01, segunda metade — medida em 30/07/2026 num `uninstall` +
`install` limpos na máquina da mantenedora, com o DualSense no cabo.

O `_source_porta_ativa_indisponivel` já existia no `doctor.sh`, com a medição
escrita ao lado dele, e **ninguém o chamava**. O `_melhor_source_de_captura`
pegava a primeira entrada não-DualSense e pronto. Nesta máquina isso elegia a
onboard `alsa_input.pci-...analog-stereo`, cujas TRÊS portas de captura estão
`not available` (nada plugado no jack).

O `pactl set-default-source` aceita esse nó. O WirePlumber, que não consegue
honrar uma fonte sem porta usável, reelege sozinho — e volta para o MONITOR. Ou
seja: a cura imprimia `[ OK ] fonte padrão trocada` e, três segundos depois, o
defeito estava de volta na tela. Isso é pior do que não curar, porque o relatório
mente.

Medição que decide o critério, na mesma máquina e no mesmo instante:

    analog-input-front-mic  (onboard)   -> not available
    analog-input-rear-mic   (onboard)   -> not available
    analog-input-linein     (onboard)   -> not available
    iec958-stereo-input     (DualSense) -> availability unknown

`unknown` conta como USÁVEL: é o caso da entrada do DualSense, que gravou pico
441 / RMS 73 num quarto silencioso (contra pico 0 — 327.680 bytes de silêncio
digital — do perfil analógico forçado, a cura que foi refutada em 26/07).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

DOCTOR = Path(__file__).resolve().parents[2] / "scripts" / "doctor.sh"

#: `pactl list sources` reduzido ao que as duas funções leem, com os nomes e a
#: disponibilidade EXATOS medidos na máquina dela em 30/07.
LISTA_COMPLETA = """\
Source #8240
	State: SUSPENDED
	Name: alsa_input.usb-Sony_Interactive_Entertainment_DualSense_\
Wireless_Controller-00.iec958-stereo
	Ports:
		iec958-stereo-input: Digital In (type: SPDIF, priority: 0, availability unknown)
	Active Port: iec958-stereo-input
Source #8242
	State: SUSPENDED
	Name: alsa_input.pci-0000_0c_00.4.analog-stereo
	Ports:
		analog-input-front-mic: Front Mic (type: Mic, priority: 8500, not available)
		analog-input-rear-mic: Rear Mic (type: Mic, priority: 8200, not available)
		analog-input-linein: Line In (type: Line, priority: 8100, not available)
	Active Port: analog-input-front-mic
"""

DS_MIC = (
    "alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.iec958-stereo"
)
ONBOARD = "alsa_input.pci-0000_0c_00.4.analog-stereo"


def _fonte(
    funcao: str, *args: str, entrada: str = ""
) -> subprocess.CompletedProcess[str]:
    """Roda UMA função do doctor.sh, com o script apenas carregado (sem main)."""
    argv = " ".join(f'"{a}"' for a in args)
    script = (
        "set -uo pipefail; "
        f'HEFESTO_DOCTOR_LIB_ONLY=1 source "{DOCTOR}" >/dev/null 2>&1 || true; '
        f"{funcao} {argv}"
    )
    return subprocess.run(
        ["bash", "-c", script],
        input=entrada,
        capture_output=True,
        text=True,
        check=False,
    )


class TestPortaIndisponivel:
    def test_onboard_sem_nada_plugado_e_detectada_como_indisponivel(self) -> None:
        r = _fonte("_source_porta_ativa_indisponivel", ONBOARD, entrada=LISTA_COMPLETA)
        assert r.returncode == 0, (
            "as três portas da onboard estão `not available` e a ativa é uma "
            f"delas — tinha de reprovar. stderr={r.stderr!r}"
        )

    def test_dualsense_com_availability_unknown_e_usavel(self) -> None:
        """`unknown` NÃO é `not available`. Confundir os dois descarta o único
        microfone de verdade da máquina dela e deixa só monitores na disputa."""
        r = _fonte("_source_porta_ativa_indisponivel", DS_MIC, entrada=LISTA_COMPLETA)
        assert r.returncode != 0, (
            "porta com disponibilidade DESCONHECIDA tem de contar como usável — "
            "é a do DualSense, que grava de verdade (pico 441 medido)"
        )


class TestMelhorFonte:
    """O seletor puro, alimentado com a lista já filtrada.

    Estes travam o contrato de quem escolhe; o filtro em si é do chamador
    (`fix_default_source_monitor`), e o teste dele é o de fiação abaixo.
    """

    CURTA_SO_DS = f"8240\t{DS_MIC}\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n"

    def test_monitor_nunca_entra(self) -> None:
        curta = (
            "8239\talsa_output.usb-Sony_Interactive_Entertainment_DualSense_"
            "Wireless_Controller-00.analog-surround-40.monitor\tPipeWire\ts16le\tSUSPENDED\n"
        )
        r = _fonte("_melhor_source_de_captura", "0", entrada=curta)
        assert r.stdout.strip() == "", "monitor é o defeito — não pode ser eleito"

    def test_com_a_onboard_filtrada_sobra_o_dualsense(self) -> None:
        r = _fonte("_melhor_source_de_captura", "0", entrada=self.CURTA_SO_DS)
        assert r.stdout.strip() == DS_MIC, (
            "com a onboard fora da disputa por porta indisponível, o mic do "
            "controle é a única entrada de verdade que sobra"
        )


class TestFiacao:
    """O portão que pega a regressão real: a função existir e não ser chamada.

    Foi exatamente esse o estado encontrado em 30/07 — o filtro escrito,
    documentado, testado por dentro, e desligado do caminho que decide.
    """

    #: A CHAMADA, não a menção. A primeira versão deste teste procurava o nome
    #: solto e passava com a chamada arrancada, porque o nome também aparece no
    #: comentário que explica o filtro logo acima — teste tautológico, o defeito
    #: que esta casa nomeia. O que prova a fiação é a invocação.
    INVOCACAO = '| _source_porta_ativa_indisponivel "'
    #: Idem para o seletor: comparar posição de MENÇÃO com posição de menção dá
    #: a resposta errada, porque o comentário que explica o filtro cita os dois
    #: nomes antes de qualquer código. Chamada contra chamada.
    INVOCACAO_ESCOLHA = '| _melhor_source_de_captura "'

    @staticmethod
    def _corpo_da_cura() -> str:
        fonte = DOCTOR.read_text(encoding="utf-8")
        inicio = fonte.index("fix_default_source_monitor()")
        fim = fonte.index("\n}\n", inicio)
        return fonte[inicio:fim]

    def test_a_cura_filtra_por_porta_antes_de_escolher(self) -> None:
        corpo = self._corpo_da_cura()

        assert self.INVOCACAO in corpo, (
            "`fix_default_source_monitor` voltou a escolher sem CHAMAR o filtro "
            "de porta usável: elege um nó que o WirePlumber não honra, reporta "
            "sucesso, e o monitor volta em segundos"
        )
        assert self.INVOCACAO_ESCOLHA in corpo, (
            "não achei a chamada do seletor — o padrão de busca envelheceu?"
        )
        pos_filtro = corpo.index(self.INVOCACAO)
        pos_escolha = corpo.index(self.INVOCACAO_ESCOLHA)
        assert pos_filtro < pos_escolha, (
            "o filtro tem de rodar ANTES da escolha, senão não filtra nada"
        )

    def test_a_funcao_de_filtro_nao_ficou_orfa_no_arquivo(self) -> None:
        fonte = DOCTOR.read_text(encoding="utf-8")
        assert fonte.count(self.INVOCACAO) >= 1, (
            "`_source_porta_ativa_indisponivel` existe e ninguém a INVOCA. "
            "Função de guarda sem chamador é guarda que não guarda — foi "
            "exatamente o estado encontrado em 30/07."
        )


@pytest.mark.parametrize("nome", [DS_MIC, ONBOARD])
def test_nenhuma_fonte_de_captura_e_classificada_como_monitor(nome: str) -> None:
    r = _fonte("_default_source_classe", nome)
    assert r.stdout.strip() == "captura"
