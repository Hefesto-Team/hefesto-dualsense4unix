"""ONDA-MUDAS-NINTENDO-PRO — as 13 células de `mapa-controles.csv@pro` que esta"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVER_PATH = REPO_ROOT / "assets" / "dkms" / "hid-nintendo" / "hid-nintendo.c"
CSV_PATH = REPO_ROOT / "docs" / "data" / "mapa-controles.csv"

DRIVER_SRC = DRIVER_PATH.read_text(encoding="utf-8")


def _linhas_csv() -> list[dict[str, str]]:
    with CSV_PATH.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _linha_pro(chave: str) -> dict[str, str]:
    for row in _linhas_csv():
        if row["chave"] == chave and row["controle"] == "pro":
            return row
    raise AssertionError(f"linha {chave}@pro sumiu do CSV")


class TestDriverSemAudio:
    """`audio.jack.deteccao@pro`, `audio.jack.volume@pro`,"""

    def test_driver_nao_menciona_audio_jack_ou_headphone(self) -> None:
        achados = [
            palavra
            for palavra in ("jack", "headphone", "speaker", "audio", "snd_")
            if re.search(palavra, DRIVER_SRC, re.IGNORECASE)
        ]
        assert not achados, (
            f"hid-nintendo.c passou a mencionar {achados} — a célula "
            "audio.*@pro deste mapa afirma driver SEM áudio; se isso mudou, "
            "as três células precisam de nova auditoria, não só este teste"
        )


class TestDriverBateriaSoTemDegraus:
    """`energia.bateria.percentual@pro` — só `CAPACITY_LEVEL`, nunca `CAPACITY`."""

    def test_joycon_battery_props_nao_tem_capacity_lisa(self) -> None:
        bloco = re.search(
            r"joycon_battery_props\[\]\s*=\s*\{(.*?)\};",
            DRIVER_SRC,
            re.DOTALL,
        )
        assert bloco is not None, (
            "joycon_battery_props sumiu do driver — a célula "
            "energia.bateria.percentual@pro cita esta constante por endereço"
        )
        corpo = bloco.group(1)
        assert "POWER_SUPPLY_PROP_CAPACITY_LEVEL" in corpo
        assert not re.search(r"POWER_SUPPLY_PROP_CAPACITY\s*,", corpo), (
            "joycon_battery_props ganhou POWER_SUPPLY_PROP_CAPACITY — o "
            "Pro passaria a ter percentual, e "
            "energia.bateria.percentual@pro (nao-tem/não/não) ficaria "
            "desatualizada"
        )


class TestDriverGatilhoAdaptativoNaoExiste:
    """`gatilho.leitura@pro`, `gatilho.modos_firmware@pro` — nenhum"""

    def test_triggers_elapsed_e_definido_mas_nunca_chamado(self) -> None:
        ocorrencias = DRIVER_SRC.count("JC_SUBCMD_TRIGGERS_ELAPSED")
        assert ocorrencias == 1, (
            f"JC_SUBCMD_TRIGGERS_ELAPSED aparece {ocorrencias}x — esperava 1 "
            "(só o #define, ZERO chamadores). Se cresceu, o driver passou a "
            "usar o subcomando, e gatilho.leitura@pro precisa de nova "
            "auditoria: pode não ser mais nao-tem"
        )

    def test_sem_outra_constante_de_gatilho_alem_da_ja_conhecida(self) -> None:
        achados = set(re.findall(r"JC_SUBCMD_\w*TRIGGER\w*", DRIVER_SRC, re.IGNORECASE))
        assert achados == {"JC_SUBCMD_TRIGGERS_ELAPSED"}, (
            f"driver ganhou constante(s) de gatilho nova(s): "
            f"{achados - {'JC_SUBCMD_TRIGGERS_ELAPSED'}} — "
            "gatilho.leitura@pro e gatilho.modos_firmware@pro (nao-tem) "
            "citam a lista fechada de hoje"
        )


class TestDriverCalibracaoSemPorteiroDeBus:
    """`entrada.stick.calibracao@pro` — quem lê a calibração é o DRIVER, no"""

    def test_joycon_request_calibration_chamada_sem_ramo_de_bus(self) -> None:
        chamada = re.search(
            r"if \(joycon_has_joysticks\(ctlr\)\) \{\s*"
            r"/\*[^*]*\*/\s*"
            r"ret = joycon_request_calibration\(ctlr\);",
            DRIVER_SRC,
        )
        assert chamada is not None, (
            "o call-site de joycon_request_calibration mudou de forma — "
            "entrada.stick.calibracao@pro cita este trecho exato "
            "(hid-nintendo.c, dentro de joycon_probe)"
        )
        assert "BUS_USB" not in chamada.group(0)
        assert "BUS_BLUETOOTH" not in chamada.group(0)


class TestDriverLedDeJogadorNuncaPisca:
    """`luz.led_jogador.pisca@pro` — o firmware aceita `flash`, o driver"""

    def test_joycon_set_player_leds_e_chamado_sempre_com_flash_zero(self) -> None:
        chamadas = re.findall(r"joycon_set_player_leds\(ctlr,\s*([^,]+),", DRIVER_SRC)
        assert chamadas, (
            "nenhuma chamada de joycon_set_player_leds encontrada — "
            "luz.led_jogador.pisca@pro conta com pelo menos uma"
        )
        for flash_arg in chamadas:
            assert flash_arg.strip() == "0", (
                f"joycon_set_player_leds chamado com flash={flash_arg!r} — "
                "luz.led_jogador.pisca@pro (não/não) afirma que o driver "
                "NUNCA aciona o nibble de flash"
            )

    def test_led_classdev_do_player_nao_registra_blink_set(self) -> None:
        assert "blink_set" not in DRIVER_SRC


class TestDriverSemTurbo:
    """`luz.recursos_proprios@pro` — sem turbo/LED de modo no driver oficial."""

    def test_driver_nao_menciona_turbo(self) -> None:
        assert not re.search(r"turbo", DRIVER_SRC, re.IGNORECASE)


class TestExternalImuEnablerAssimetriaCaboRadio:
    """`movimento.imu.ligar@pro` — cabo tenta ligar a IMU (parcial), rádio"""

    _UNIQ_USB = "aa:bb:cc:00:00:01"
    _UNIQ_BT = "aa:bb:cc:00:00:02"
    _UNIQ_CLONE_USB = "e4:17:d8:00:00:03"

    @staticmethod
    def _entrada(*, uniq: str, bus: str, hidraw: str) -> dict[str, str]:
        return {
            "uniq": uniq,
            "name": "Pro Controller",
            "vid": "057e",
            "pid": "2009",
            "bus": bus,
            "hidraw": hidraw,
        }

    def test_pro_genuino_no_cabo_aciona_enable_imu(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hefesto_dualsense4unix.core import external_leds
        from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
            ExternalImuEnabler,
        )

        chamadas: list[str | None] = []
        monkeypatch.setattr(
            external_leds,
            "enable_imu",
            lambda hidraw, **_kw: chamadas.append(hidraw) or True,
        )

        enabler = ExternalImuEnabler()
        enabler.tick(
            [self._entrada(uniq=self._UNIQ_USB, bus="usb", hidraw="/dev/hidraw97")]
        )

        assert chamadas == ["/dev/hidraw97"], (
            "ExternalImuEnabler não chamou enable_imu para um Pro genuíno "
            "no cabo — movimento.imu.ligar@pro (cabo_aciona=parcial) conta "
            "com esta chamada acontecer"
        )

    def test_pro_genuino_no_radio_nunca_aciona_enable_imu(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.core import external_leds
        from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
            ExternalImuEnabler,
        )

        chamadas: list[str | None] = []
        monkeypatch.setattr(
            external_leds,
            "enable_imu",
            lambda hidraw, **_kw: chamadas.append(hidraw) or True,
        )

        enabler = ExternalImuEnabler()
        enabler.tick(
            [
                self._entrada(
                    uniq=self._UNIQ_BT, bus="bluetooth", hidraw="/dev/hidraw96"
                )
            ]
        )

        assert chamadas == [], (
            "ExternalImuEnabler chamou enable_imu por RÁDIO — "
            "movimento.imu.ligar@pro (radio_aciona=não) afirma que o "
            "produto NUNCA tenta isso por bluetooth, de propósito "
            "(o driver já liga a IMU sozinho lá)"
        )

    def test_clone_8bitdo_no_cabo_nunca_aciona_enable_imu(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Controle: o gate por OUI é o que separa pro@sn30 — não é só bus."""
        from hefesto_dualsense4unix.core import external_leds
        from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
            ExternalImuEnabler,
        )

        chamadas: list[str | None] = []
        monkeypatch.setattr(
            external_leds,
            "enable_imu",
            lambda hidraw, **_kw: chamadas.append(hidraw) or True,
        )

        enabler = ExternalImuEnabler()
        enabler.tick(
            [
                self._entrada(
                    uniq=self._UNIQ_CLONE_USB, bus="usb", hidraw="/dev/hidraw95"
                )
            ]
        )

        assert chamadas == [], (
            "ExternalImuEnabler chamou enable_imu para uma OUI de clone "
            "conhecido no cabo — o gate e_pro_genuino() deveria ter barrado"
        )


CELULAS_RESPONDIDAS: tuple[tuple[str, str, str], ...] = (
    ("audio.jack.deteccao", "não", "não"),
    ("audio.jack.volume", "não", "não"),
    ("audio.leitura_de_volta", "não", "não"),
    ("energia.bateria.jogo", "não", "não"),
    ("energia.bateria.leitura_hefesto", "não", "não"),
    ("energia.bateria.percentual", "não", "não"),
    ("entrada.bruta", "sim", "sim"),
    ("entrada.stick.calibracao", "não", "não"),
    ("gatilho.leitura", "não", "não"),
    ("gatilho.modos_firmware", "não", "não"),
    ("luz.led_jogador.pisca", "não", "não"),
    ("luz.recursos_proprios", "não", "não"),
    ("movimento.imu.ligar", "parcial", "não"),
)


class TestCelulasDoMapaNaoRegridemNemDivergem:
    """Protege as 13 células contra a MESMA armadilha do cabeçalho desta"""

    @pytest.mark.parametrize(
        ("chave", "cabo_esperado", "radio_esperado"), CELULAS_RESPONDIDAS
    )
    def test_aciona_bate_com_o_que_esta_leva_respondeu(
        self, chave: str, cabo_esperado: str, radio_esperado: str
    ) -> None:
        row = _linha_pro(chave)
        assert row["cabo_aciona"] == cabo_esperado, (
            f"{chave}@pro: cabo_aciona = {row['cabo_aciona']!r}, "
            f"esperado {cabo_esperado!r}"
        )
        assert row["radio_aciona"] == radio_esperado, (
            f"{chave}@pro: radio_aciona = {radio_esperado!r}, "
            f"esperado {radio_esperado!r}"
        )

    @pytest.mark.parametrize(
        ("chave", "_cabo", "_radio"), CELULAS_RESPONDIDAS
    )
    def test_toda_celula_respondida_tem_evidencia_e_de_onde_sei_dos_dois_lados(
        self, chave: str, _cabo: str, _radio: str
    ) -> None:
        row = _linha_pro(chave)
        for lado in ("cabo", "radio"):
            assert row[f"{lado}_de_onde_sei"], (
                f"{chave}@pro: {lado}_de_onde_sei vazio com {lado}_aciona "
                f"respondido — regra 19 (lado-sem-régua) do portão "
                "check_paridade_transporte.py reprovaria isto"
            )
            tem_conteudo = any(
                row.get(f"{lado}_{sufixo}")
                for sufixo in ("evidencia", "detalhe", "ressalva")
            )
            assert tem_conteudo, (
                f"{chave}@pro: {lado} não tem evidência, detalhe nem "
                "ressalva — uma resposta forte sem NENHUM rastro de onde "
                "veio é pior que a célula muda"
            )

    def test_as_quinze_mudas_originais_da_fatia_tem_treze_respondidas_e_duas_declaradas(
        self,
    ) -> None:
        """As 15 células mudas que a orquestração mediu antes de despachar"""
        mudas_originais = {
            "audio.jack.deteccao",
            "audio.jack.volume",
            "audio.leitura_de_volta",
            "energia.bateria.jogo",
            "energia.bateria.leitura_hefesto",
            "energia.bateria.percentual",
            "entrada.bruta",
            "entrada.combo.ponte",
            "entrada.stick.calibracao",
            "gatilho.leitura",
            "gatilho.modos_firmware",
            "luz.led_jogador.pisca",
            "luz.recursos_proprios",
            "movimento.giroscopio.taxa",
            "movimento.imu.ligar",
        }
        respondidas = {chave for chave, *_ in CELULAS_RESPONDIDAS}
        deixadas_de_proposito = {"entrada.combo.ponte", "movimento.giroscopio.taxa"}
        assert mudas_originais == respondidas | deixadas_de_proposito
        assert len(respondidas) == 13
        assert len(deixadas_de_proposito) == 2

        for chave in deixadas_de_proposito:
            row = _linha_pro(chave)
            for lado in ("cabo", "radio"):
                assert row[f"{lado}_de_onde_sei"].strip(), (
                    f"{chave}@pro: `{lado}_aciona` foi respondido e "
                    f"`{lado}_de_onde_sei` está vazio — resposta sem "
                    "procedência é pior que célula muda"
                )
                assert row[f"{lado}_de_onde_sei"].strip() != "medido", (
                    f"{chave}@pro: `{lado}_de_onde_sei` virou `medido` sem Pro "
                    "na mesa. O teto do que se afirma lendo fonte é "
                    "`inferido-do-codigo`."
                )
            assert row["cabo_ressalva"].strip(), (
                f"{chave}@pro: respondida por leitura de fonte e sem ressalva "
                "— é a ressalva que diz o que o aparelho ainda deve"
            )
