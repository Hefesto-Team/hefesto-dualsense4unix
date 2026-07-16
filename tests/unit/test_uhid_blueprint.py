"""Blueprint canônico USB embutido — o dump fossilizado dos sprints VPAD-03/BT-01.

O que estes testes travam (critérios de aceite dos dois sprint docs):

1. **Descriptor de exatamente 289 B, SEM o item `85 31`** (o input 0x01 de ~10 B
   do transporte BT — copiá-lo produzia vpad `BUS_USB` torto) e byte-idêntico ao
   capture de referência do repo.
2. **Features 0x05/0x20 com 41/64 B**, report id certo, byte-idênticos aos
   `.bin` de `captures/` (procedência fossilizada, conferível para sempre).
3. **0x09 NUNCA fossilizado com identidade**: template de exatamente 20 B com a
   assinatura `08 25 00` nos bytes 7-9 e as DUAS áreas de MAC zeradas (bytes
   1..6 = device, 10..15 = host pareado). O MAC de verdade é o forjado por
   jogador (`02:fe:00:00:00:0N`, LE), carimbado em runtime pelo `start()`.
4. O firmware do 0x20 induz o caminho `use_vibration_v2` do kernel (update
   version `0x0630` ≥ limiar `0x0215`) — é o caminho de vibração validado ao
   vivo; um template regenerado com fw antigo mudaria o caminho em silêncio.
"""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import uhid_blueprint, uhid_gamepad
from hefesto_dualsense4unix.integrations.uhid_blueprint import (
    CANONICAL_DESCRIPTOR_USB,
    CANONICAL_FEATURE_0X05,
    CANONICAL_FEATURE_0X20,
    TEMPLATE_FEATURE_0X09,
    canonical_blueprint,
)

_CAPTURES = Path(__file__).resolve().parents[2] / "captures"


class TestDescriptor:
    def test_tem_exatamente_289_bytes(self) -> None:
        assert len(CANONICAL_DESCRIPTOR_USB) == 289

    def test_nao_tem_o_item_de_input_bt(self) -> None:
        """`85 31` = report de input 0x01 do transporte BT (~10 B): um vpad
        BUS_USB com esse descriptor teria o report 0x01 dimensionado errado."""
        assert b"\x85\x31" not in CANONICAL_DESCRIPTOR_USB

    def test_byte_identico_ao_capture_de_referência(self) -> None:
        referência = (_CAPTURES / "dualsense_usb_descriptor_054c0ce6.bin").read_bytes()

        assert referência == CANONICAL_DESCRIPTOR_USB

    def test_e_um_descriptor_de_gamepad(self) -> None:
        """Começa em Usage Page (Generic Desktop) / Usage (Gamepad) e fecha a
        collection — o mínimo para não embutir um dump truncado por engano."""
        assert CANONICAL_DESCRIPTOR_USB[:4] == bytes.fromhex("05010905")
        assert CANONICAL_DESCRIPTOR_USB[-1] == 0xC0


class TestFeaturesFossilizados:
    def test_0x05_calibracao(self) -> None:
        assert len(CANONICAL_FEATURE_0X05) == 41
        assert CANONICAL_FEATURE_0X05[0] == 0x05

    def test_0x05_byte_identico_ao_capture(self) -> None:
        referência = (_CAPTURES / "dualsense_usb_feature_0x05_calibracao.bin").read_bytes()

        assert referência == CANONICAL_FEATURE_0X05

    def test_0x20_firmware(self) -> None:
        assert len(CANONICAL_FEATURE_0X20) == 64
        assert CANONICAL_FEATURE_0X20[0] == 0x20

    def test_0x20_byte_identico_ao_capture(self) -> None:
        referência = (_CAPTURES / "dualsense_usb_feature_0x20_firmware.bin").read_bytes()

        assert referência == CANONICAL_FEATURE_0X20

    def test_0x20_induz_o_caminho_de_vibracao_validado(self) -> None:
        """Update version nos bytes 44-45 (LE): ≥ 0x0215 liga `use_vibration_v2`
        no hid_playstation — o caminho de rumble validado ao vivo nesta base."""
        update_version = struct.unpack_from("<H", CANONICAL_FEATURE_0X20, 44)[0]

        assert update_version == 0x0630
        assert update_version >= 0x0215

    def test_tamanhos_batem_com_o_que_o_probe_pede(self) -> None:
        """`_FEATURE_SIZES` é o contrato do GET_REPORT do probe — template de
        tamanho errado é descartado calado pelo driver."""
        esperados = dict(uhid_gamepad._FEATURE_SIZES)
        blueprint = canonical_blueprint()

        assert {
            rid: len(payload) for rid, payload in blueprint["features"].items()
        } == esperados


class TestTemplate0x09SemIdentidade:
    """O 0x09 carrega MACs (device + host) — identidade NUNCA entra no repo."""

    def test_tem_exatamente_20_bytes_com_report_id(self) -> None:
        assert len(TEMPLATE_FEATURE_0X09) == 20
        assert TEMPLATE_FEATURE_0X09[0] == 0x09

    def test_assinatura_nos_bytes_7_a_9(self) -> None:
        """O report real exibe `08 25 00` nos bytes 7-9; o dump corrompido do
        estudo (21 B, um `00` extra) deslocava a assinatura para 8-10."""
        assert TEMPLATE_FEATURE_0X09[7:10] == bytes.fromhex("082500")

    def test_areas_de_mac_zeradas(self) -> None:
        assert TEMPLATE_FEATURE_0X09[1:7] == bytes(6)  # MAC do device
        assert TEMPLATE_FEATURE_0X09[10:16] == bytes(6)  # MAC do host pareado
        assert TEMPLATE_FEATURE_0X09[16:20] == bytes(4)

    def test_nao_existe_bin_fossilizado_do_0x09(self) -> None:
        """A regra de anonimato em forma de teste: o 0x09 é sempre gerado, nunca
        capturado para o repo — um `.bin` dele em captures/ seria identidade."""
        suspeitos = [p.name for p in _CAPTURES.glob("*0x09*")]

        assert suspeitos == []


class TestCanonicalBlueprint:
    def test_shape_e_conteudo(self) -> None:
        blueprint = canonical_blueprint()

        assert blueprint["descriptor"] is CANONICAL_DESCRIPTOR_USB
        assert blueprint["features"] == {
            0x05: CANONICAL_FEATURE_0X05,
            0x09: TEMPLATE_FEATURE_0X09,
            0x20: CANONICAL_FEATURE_0X20,
        }

    def test_cada_chamada_devolve_um_dict_novo(self) -> None:
        """Um caller que mutasse o dict compartilhado envenenaria os vpads
        seguintes (o co-op cria até 4)."""
        primeiro = canonical_blueprint()
        primeiro["features"][0x05] = b"\x00"

        assert canonical_blueprint()["features"][0x05] == CANONICAL_FEATURE_0X05


class TestMacForjadoPorJogador:
    @pytest.mark.parametrize("player", [1, 2, 4])
    def test_start_carimba_o_mac_do_jogador_no_template(self, player: int) -> None:
        """O template nasce sem MAC; quem o injeta é o vpad, por jogador, em LE
        (bytes 1..6 do 0x09 — o único campo que o probe USB lê)."""
        pad = uhid_gamepad.UhidDualSense(player=player, blueprint=canonical_blueprint())

        report09 = pad._features_com_mac_proprio()[0x09]

        assert len(report09) == 20
        assert report09[1:7] == bytes.fromhex(f"0{player}000000fe02")
        assert report09[7:10] == bytes.fromhex("082500")  # assinatura intacta
        assert report09[10:] == TEMPLATE_FEATURE_0X09[10:]  # host segue zerado

    def test_macs_distintos_por_indice(self) -> None:
        """MAC repetido = probe failed -17 do 2º jogador em diante."""
        reports = {
            uhid_gamepad.UhidDualSense(
                player=n, blueprint=canonical_blueprint()
            )._features_com_mac_proprio()[0x09][1:7]
            for n in range(1, 5)
        }

        assert len(reports) == 4

    def test_faixa_localmente_administrada(self) -> None:
        """`02:fe:...` (bit 1 do primeiro octeto) por definição não colide com
        hardware real — nenhum vpad pode nascer com MAC de controle de verdade."""
        assert uhid_blueprint.canonical_blueprint()["features"][0x09][1:7] == bytes(6)
        assert uhid_gamepad.player_mac(3).startswith("02:fe:")
