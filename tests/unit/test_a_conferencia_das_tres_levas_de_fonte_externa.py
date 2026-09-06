"""Prende os fatos que a conferência de 03/09/2026 verificou na FONTE.

As três levas de levantamento externo (entrada, luz, energia/vibração) escreveram
endereços no `docs/data/mapa-controles.csv` a partir de repositórios públicos.
Este arquivo não confere o CSV — confere o CHÃO: o driver que roda nesta máquina
e a `pydualsense` que este projeto importa. São as duas fontes que viajam com a
árvore e que podem ser lidas sem rede.

POR QUE ELE EXISTE: a conferência achou um endereço errado no mapa que a fonte
citada desmente (os botões de trás do DualSense Edge). Um teste que lê a fonte
pega isso na hora; um teste que lê o mapa só repete o erro do mapa.

A MORDIDA: troque qualquer número do `hid-playstation.c` ou o `states[10]` da
`pydualsense` e o teste correspondente cai.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DRIVER = RAIZ / "assets" / "dkms" / "hid-playstation" / "hid-playstation.c"


@pytest.fixture(scope="module")
def fonte_do_driver() -> str:
    if not DRIVER.exists():  # pragma: no cover - a cópia DKMS é versionada
        pytest.skip(f"cópia DKMS ausente: {DRIVER}")
    return DRIVER.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def fonte_da_pydualsense() -> str:
    try:
        import pydualsense
    except Exception:  # pragma: no cover - venv sem a biblioteca
        pytest.skip("pydualsense não está importável nesta venv")
    alvo = Path(os.path.dirname(pydualsense.__file__)) / "pydualsense.py"
    if not alvo.exists():  # pragma: no cover
        pytest.skip(f"fonte da pydualsense ausente: {alvo}")
    return alvo.read_text(encoding="utf-8", errors="replace")


class TestOsBotoesDeTrasDoEdge:
    """O achado mais grave da conferência de 03/09/2026.

    O mapa afirmou que os quatro botões de trás do DualSense Edge moram em
    `payload[10]` (o `buttons[3]` do driver, que ninguém lê), citando a
    `pydualsense`. A `pydualsense` diz o contrário: ela os lê de `states[10]`,
    que é `payload[9]` — o `buttons[2]`, o MESMO byte do PS, do touchpad e do
    mudo. O documento da própria leva acertou; a célula do mapa, não.
    """

    def test_a_pydualsense_le_as_costas_do_edge_do_mesmo_byte_do_ps(
        self, fonte_da_pydualsense: str
    ) -> None:
        # O bloco `if self.is_edge:` que decodifica L4/R4/L5/R5.
        bloco = re.search(
            r"misc2\s*=\s*states\[(?P<indice>\d+)\](?P<corpo>.*?)# trackpad touch",
            fonte_da_pydualsense,
            re.S,
        )
        assert bloco is not None, "a decodificação de `misc2` mudou de forma"

        # `misc2` tem de ser o byte 10 do report — payload[9], buttons[2].
        assert bloco.group("indice") == "10", (
            "a pydualsense mudou o índice de `misc2`; o mapa depende dele "
            "para dizer onde o Edge põe os botões de trás"
        )

        corpo = bloco.group("corpo")
        # No MESMO byte estão o PS, o touchpad e o mudo — a prova de que não é
        # um byte reservado só do Edge.
        for campo in ("self.state.ps", "self.state.touchBtn", "self.state.micBtn"):
            assert campo in corpo, f"{campo} saiu de `misc2`"
        # E os quatro do Edge, nos bits 4 a 7.
        for campo, mascara in (
            ("L4", "0x10"),
            ("R4", "0x20"),
            ("L5", "0x40"),
            ("R5", "0x80"),
        ):
            assert re.search(
                rf"self\.state\.{campo}\s*=\s*\(misc2\s*&\s*{mascara}\)", corpo
            ), f"o {campo} do Edge não sai mais de `misc2` & {mascara}"

    def test_o_driver_nunca_le_o_quarto_byte_de_botao(
        self, fonte_do_driver: str
    ) -> None:
        """`buttons[3]` existe na struct e ninguém o lê — nem para o Edge."""
        assert "u8 buttons[4];" in fonte_do_driver, "a struct de entrada mudou"
        # Nenhuma LEITURA de buttons[3] — `->buttons[3]` ou `.buttons[3]`.
        # (O `u8 buttons[3];` solto é a DECLARAÇÃO da struct do DualShock 4,
        # que tem três bytes de botão em vez de quatro; não é leitura.)
        assert not re.search(r"[.>]buttons\[3\]", fonte_do_driver), (
            "o driver passou a ler `buttons[3]`; a afirmação de que as costas "
            "do Edge não chegam por evdev nesta máquina caducou"
        )
        # E os índices que ele REALMENTE lê são só 0, 1 e 2.
        lidos = sorted(set(re.findall(r"[.>]buttons\[(\d)\]", fonte_do_driver)))
        assert lidos == ["0", "1", "2"], f"o driver passou a ler buttons{lidos}"
        # E o byte que ELES usam (buttons[2]) só tem três máscaras, todas <= bit2.
        mascaras = re.findall(r"#define\s+DS_BUTTONS2_\w+\s+BIT\((\d)\)", fonte_do_driver)
        assert sorted(mascaras) == ["0", "1", "2"], (
            "as máscaras de `buttons[2]` mudaram; se alguma alcançar os bits "
            "4-7, o Edge passou a chegar por evdev"
        )


class TestOLimiarDeFirmwareDaVibracaoV2:
    """A contradição que a leva de energia achou, e que a conferência confirmou.

    O driver desta máquina liga a vibração v2 em 0x0215; a SDL, o SpecialK e o
    DS5Dongle exigem 0x0224. Os três leem o mesmo campo. Fica em aberto até
    alguém ler a versão de firmware dos controles dela.
    """

    def test_o_macro_de_versao_monta_o_minor_no_byte_baixo(
        self, fonte_do_driver: str
    ) -> None:
        assert "DS_FEATURE_VERSION_MINOR\t\tGENMASK(7, 0)" in fonte_do_driver.expandtabs(
            8
        ).replace("        ", "\t\t", 1) or re.search(
            r"DS_FEATURE_VERSION_MINOR\s+GENMASK\(7,\s*0\)", fonte_do_driver
        ), "o campo MINOR da versão de firmware saiu do byte baixo"
        assert re.search(
            r"DS_FEATURE_VERSION_MAJOR\s+GENMASK\(15,\s*8\)", fonte_do_driver
        ), "o campo MAJOR da versão de firmware saiu do byte alto"

    def test_o_limiar_da_v2_continua_sendo_2_21_ou_seja_0x0215(
        self, fonte_do_driver: str
    ) -> None:
        achado = re.search(
            r"use_vibration_v2\s*=\s*ds->update_version\s*>=\s*DS_FEATURE_VERSION\((\d+),\s*(\d+)\)",
            fonte_do_driver,
        )
        assert achado is not None, "o driver mudou como decide a vibração v2"
        maior, menor = int(achado.group(1)), int(achado.group(2))
        assert (maior, menor) == (2, 21), (
            "o limiar do driver mudou; confira contra o 0x0224 de fora"
        )
        # É esta conta que faz o limiar divergir do 0x0224 das fontes externas.
        assert (maior << 8) | menor == 0x0215

    def test_a_versao_de_firmware_sai_do_byte_44(self, fonte_do_driver: str) -> None:
        assert re.search(
            r"update_version\s*=\s*get_unaligned_le16\(&buf\[44\]\)", fonte_do_driver
        ), "o campo de versão mudou de offset; as três fontes liam o byte 44"


class TestOCorpoDoReportDeSaida:
    """Os 47 bytes de que dependem a leva da luz e a de vibração."""

    def test_o_corpo_comum_tem_quarenta_e_sete_bytes(
        self, fonte_do_driver: str
    ) -> None:
        assert re.search(
            r"static_assert\(sizeof\(struct dualsense_output_report_common\)\s*==\s*47\)",
            fonte_do_driver,
        ), (
            "o corpo do report de saída mudou de tamanho; a prova de que "
            "nenhum dos 47 bytes é frequência de rumble depende deste número"
        )

    def test_o_brilho_e_as_lampadas_ficam_em_42_e_43(
        self, fonte_do_driver: str
    ) -> None:
        """Confere o offset CONTANDO a struct, não confiando num comentário."""
        corpo = re.search(
            r"struct dualsense_output_report_common \{(.*?)\} __packed;",
            fonte_do_driver,
            re.S,
        )
        assert corpo is not None, "a struct de saída mudou de forma"

        offset = 0
        posicoes: dict[str, int] = {}
        for linha in corpo.group(1).splitlines():
            achado = re.match(r"\s*u8\s+(\w+)(?:\[(\d+)\])?\s*;", linha)
            if not achado:
                continue
            nome, quantos = achado.group(1), int(achado.group(2) or 1)
            posicoes[nome] = offset
            offset += quantos

        assert offset == 47, f"a soma dos campos deu {offset}, não 47"
        assert posicoes["led_brightness"] == 42, "o brilho saiu do common[42]"
        assert posicoes["player_leds"] == 43, "as lâmpadas saíram do common[43]"
        assert posicoes["lightbar_red"] == 44
        assert posicoes["mute_button_led"] == 8, (
            "o LED do mudo saiu do common[8] — e é ele que ancora a conta de "
            "+3 do envelope de rádio, medida no aparelho em 02/09/2026"
        )

    def test_o_envelope_de_radio_tem_tres_bytes_antes_do_corpo(
        self, fonte_do_driver: str
    ) -> None:
        """A wiki externa mostra DOIS; o driver mostra três, e a medição da casa
        (`luz.led_microfone`: common[8] = report[11]) confirma os três."""
        corpo = re.search(
            r"struct dualsense_output_report_bt \{(.*?)\} __packed;",
            fonte_do_driver,
            re.S,
        )
        assert corpo is not None, "a struct de saída por rádio mudou de forma"
        antes = corpo.group(1).split("struct dualsense_output_report_common")[0]
        campos = re.findall(r"\s*u8\s+(\w+);", antes)
        assert campos == ["report_id", "seq_tag", "tag"], (
            f"o envelope de rádio virou {campos}; se ele encolher para dois "
            "bytes, todo offset de rádio do mapa anda um"
        )
