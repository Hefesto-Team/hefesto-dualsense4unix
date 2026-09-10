"""O quadro de microfone não é estado de gamepad — nem para nós, nem para o driver.

O DEFEITO, achado em 10/09/2026 e com endereço nos dois lados
--------------------------------------------------------------
Quando o microfone do DualSense está no ar, o firmware manda os quadros de
áudio Opus **com o mesmo `reportID` `0x31`, o mesmo tamanho de 78 bytes e um
CRC-32 válido** que um report de estado de gamepad. Nada disso distingue os
dois: **só o bit 1 do byte 1**, que o firmware liga nos reports de áudio.

Esta casa sabia disso desde 16/08/2026 — `INPUT_FLAG_AUDIO` em
`core/physical_report_reader.py`, do PS-PRESO-01. **O `hid-playstation` não
sabia**, e é ele quem cria o evdev.

O que o driver fazia com um quadro de áudio (`assets/dkms/hid-playstation/
hid-playstation.c`, lido no fonte desta árvore):

* `ds_report->buttons[2]` cai sobre payload Opus, e o bit `DS_BUTTONS2_MIC_MUTE`
  oscila com ele. Na borda de subida o driver inverte `ds->mic_muted` e agenda
  o trabalho que escreve `POWER_SAVE_CONTROL_MIC_MUTE` — **desligando o
  microfone sozinho**;
* os eixos e os botões recebem valores de áudio, e o cursor e o teclado dela se
  mexem sozinhos.

**A segunda consequência é a entrada fantasma que ela relatou duas vezes**
(*"o teclado fica se mexendo quando vc dá o comando"*). E a medição de 10/09
que deu ZERO em 120 s não a derruba: naquela corrida **o microfone não estava
no ar**, logo não havia quadro de áudio a ser lido como botão.

E ela explica o `BT-MIC-GATING-01`, aberto no cabeçalho de
`integrations/dualsense_bt_audio.py` desde agosto: o bit `MicMuted` oscilando a
~16,7 Hz com o mic ligado, e estável com ele desligado. **É o kernel
oscilando** — muta na borda falsa, o firmware obedece, a próxima borda falsa
desmuta. O «principal suspeito» registrado lá (o nosso daemon escrevendo
`common[9]` a 60 Hz) não era o culpado.

O QUE ESTE ARQUIVO TRAVA
-------------------------
Que as DUAS metades façam a mesma guarda, com o MESMO bit. Uma casa que sabe a
resposta em Python e a esquece em C paga o defeito inteiro do mesmo jeito.

A MORDIDA: apague o `if (data[1] & DS_INPUT_BT_FLAG_AUDIO) return 0;` do
driver e `test_o_driver_descarta_o_report_de_audio` reprova; troque o valor da
constante e `test_as_duas_metades_usam_o_mesmo_bit` reprova.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.core.physical_report_reader import INPUT_FLAG_AUDIO

#: O driver que ESTE produto instala — a cópia versionada, não a do sistema.
DRIVER = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "dkms"
    / "hid-playstation"
    / "hid-playstation.c"
)


@pytest.fixture(scope="module")
def fonte_do_driver() -> str:
    if not DRIVER.exists():  # pragma: no cover - a árvore sem o DKMS
        pytest.skip(f"o driver não está nesta árvore: {DRIVER}")
    return DRIVER.read_text(encoding="utf-8", errors="replace")


def test_as_duas_metades_usam_o_mesmo_bit(fonte_do_driver: str) -> None:
    """`INPUT_FLAG_AUDIO` (Python) e `DS_INPUT_BT_FLAG_AUDIO` (C) são o MESMO.

    Dois números que precisam concordar e moram em arquivos diferentes é a
    família de defeito que esta casa já nomeia. Aqui a régua LÊ os dois.
    """
    achado = re.search(
        r"#define\s+DS_INPUT_BT_FLAG_AUDIO\s+(0x[0-9A-Fa-f]+|\d+)", fonte_do_driver
    )
    assert achado, (
        "o driver não declara `DS_INPUT_BT_FLAG_AUDIO` — a guarda que separa "
        "áudio de estado de gamepad não existe nele"
    )
    do_driver = int(achado.group(1), 0)
    assert do_driver == INPUT_FLAG_AUDIO, (
        f"o driver usa 0x{do_driver:02x} e o Python usa 0x{INPUT_FLAG_AUDIO:02x} "
        "— um dos dois lados vai ler áudio como botão"
    )


def test_o_driver_descarta_o_report_de_audio(fonte_do_driver: str) -> None:
    """A guarda existe, e ela está NO CAMINHO DO PARSE por Bluetooth.

    Não basta a constante existir: ela tem de ser consultada antes de o
    `ds_report` ser apontado para o payload.
    """
    assert "DS_INPUT_BT_FLAG_AUDIO" in fonte_do_driver

    corpo = fonte_do_driver[fonte_do_driver.index("DS_INPUT_REPORT_BT_SIZE) {") :]
    trecho = corpo[: corpo.index("ds_report = (struct dualsense_input_report *)&data[2];")]
    assert "DS_INPUT_BT_FLAG_AUDIO" in trecho, (
        "a guarda não está entre a checagem de CRC e o apontamento do "
        "`ds_report` — um quadro de áudio ainda seria parseado como gamepad"
    )
    assert re.search(r"if\s*\(data\[1\]\s*&\s*DS_INPUT_BT_FLAG_AUDIO\)", trecho), (
        "a guarda tem de ler o BYTE 1 do report cru; ler outro byte mediria "
        "outra coisa e passaria neste teste por acidente"
    )


def test_a_guarda_devolve_consumido_e_nao_erro(fonte_do_driver: str) -> None:
    """`return 0`, nunca `-EILSEQ`.

    Um report de áudio não é malformado — ele é de outro tipo. Devolver erro
    encheria o `dmesg` dela a ~100 linhas por segundo com o microfone ligado,
    que é um segundo defeito em cima do primeiro.
    """
    corpo = fonte_do_driver[fonte_do_driver.index("DS_INPUT_BT_FLAG_AUDIO)") :]
    depois = corpo[: corpo.index("ds_report =")]
    assert "return 0;" in depois, (
        "a guarda não devolve `return 0` — ver a razão na docstring deste teste"
    )
    assert "EILSEQ" not in depois


def test_a_razao_viaja_com_a_cura(fonte_do_driver: str) -> None:
    """O comentário da guarda diz as DUAS consequências, não só uma.

    Quem ler só *«o microfone desliga»* vai achar que a entrada fantasma é
    outro defeito, e vai medi-la de novo — foi o que aconteceu em 10/09, com
    quatro medições e uma hipótese errada.
    """
    trecho = fonte_do_driver[
        fonte_do_driver.index("MIC-NAO-E-BOTAO-01") : fonte_do_driver.index(
            "if (data[1] & DS_INPUT_BT_FLAG_AUDIO)"
        )
    ]
    assert "MIC_MUTE" in trecho, "falta a consequência do microfone se desligar"
    for palavra in ("cursor", "teclado"):
        assert palavra in trecho, (
            f"falta a consequência da entrada fantasma (a palavra {palavra!r})"
        )
    assert "physical_report_reader" in trecho, (
        "a cura tem de apontar para a metade em Python que já fazia isto — "
        "senão a próxima pessoa reimplementa em vez de reusar"
    )
