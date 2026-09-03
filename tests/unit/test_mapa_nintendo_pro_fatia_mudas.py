"""ONDA-MUDAS-NINTENDO-PRO — as 13 células de `mapa-controles.csv@pro` que esta
fatia respondeu (entrada, luz, movimento, energia, gatilho, áudio), e a
mordida que protege cada uma.

O QUE ESTE ARQUIVO GUARDA
--------------------------
Sem um Nintendo Pro Controller na mesa desta máquina (medido: `lsusb` e
`/sys/class/hidraw/*/device/uevent` não mostram vendor `057e`), as 13 células
que esta fatia respondeu vieram de LEITURA DE FONTE — o driver oficial
vendorizado (`assets/dkms/hid-nintendo/hid-nintendo.c`) e o código deste
produto (`daemon/subsystems/external_identity.py`) — nunca de bancada. Este
arquivo é a rede: se algum dos fatos que sustentam aquelas 13 células mudar
silenciosamente (o driver for atualizado, alguém reescrever um gate), a
próxima pessoa que ler `de_onde_sei = inferido-do-codigo` naquelas linhas
precisa de um jeito de saber que a inferência morreu.

TRÊS PARTES:

A. Fatos estruturais do driver oficial — protegem as sete células cujo valor
   nasce de "o driver não tem X" (áudio, bateria-percentual, gatilho
   adaptativo, calibração sem porteiro de bus, LED sem blink, ausência de
   turbo).
B. `ExternalImuEnabler` — protege a assimetria REAL e deliberada de
   `movimento.imu.ligar@pro` (cabo=parcial, rádio=não): o gate `bus == "usb"`
   é do PRODUTO, testável sem hardware nenhum.
C. As 13 células do CSV — protege contra a MESMA armadilha que o cabeçalho
   desta casa descreve: uma fusão de merge anexando texto numa coluna de
   domínio fechado, ou uma célula respondida voltando a muda sem ninguém
   notar.

MORDE? Arranque qualquer um dos fatos de A ou B (comente uma linha do driver,
afrouxe um gate) e o teste correspondente nomeia o que sumiu. Arranque uma
célula de C (esvazie ou troque o valor) e o teste de C nomeia a chave e o
valor esperado.

MORDIDA PROVADA: ver `mordida_provada` e `mordida_saidas` na saída estruturada
desta leva (o `StructuredOutput` do agente que escreveu este arquivo) — os
testes de A, B e C foram rodados com a linha-alvo comentada/trocada e
reprovaram, um a um, antes de a cura ser devolvida.
"""

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


# ---------------------------------------------------------------------------
# A — fatos estruturais do driver oficial
# ---------------------------------------------------------------------------


class TestDriverSemAudio:
    """`audio.jack.deteccao@pro`, `audio.jack.volume@pro`,
    `audio.leitura_de_volta@pro` — o driver não tem UMA linha de áudio.

    MORDE: escreva `jack` ou `headphone` em qualquer comentário do driver e
    este teste reprova, nomeando o achado.
    """

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
    """`energia.bateria.percentual@pro` — só `CAPACITY_LEVEL`, nunca `CAPACITY`.

    MORDE: adicione `POWER_SUPPLY_PROP_CAPACITY,` (sem `_LEVEL`) à lista de
    `joycon_battery_props` e este teste reprova.
    """

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
        # "CAPACITY," sem o sufixo "_LEVEL" é o percentual 0-100 que NÃO
        # existe — a vírgula/quebra depois do nome evita casar o prefixo de
        # CAPACITY_LEVEL por engano.
        assert not re.search(r"POWER_SUPPLY_PROP_CAPACITY\s*,", corpo), (
            "joycon_battery_props ganhou POWER_SUPPLY_PROP_CAPACITY — o "
            "Pro passaria a ter percentual, e "
            "energia.bateria.percentual@pro (nao-tem/não/não) ficaria "
            "desatualizada"
        )


class TestDriverGatilhoAdaptativoNaoExiste:
    """`gatilho.leitura@pro`, `gatilho.modos_firmware@pro` — nenhum
    subcomando de FORÇA/RESISTÊNCIA adaptativa existe no driver do Pro.

    ACHADO NESTA LEVA (o teste abaixo é o que achou): o driver DEFINE
    `JC_SUBCMD_TRIGGERS_ELAPSED` (0x04) — mas é outra pergunta de protocolo
    ("há quanto tempo o botão está segurado", não força adaptativa) e tem
    ZERO chamadores: 1 ocorrência no arquivo inteiro, o próprio `#define`.
    Código morto, nunca enviado, nunca com resposta parseada.

    MORDE: adicione um CHAMADOR de `JC_SUBCMD_TRIGGERS_ELAPSED` (o subcomando
    passaria a ser real) e o primeiro teste reprova; adicione uma constante
    `JC_SUBCMD_*TRIGGER*` NOVA e o segundo reprova.
    """

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
    """`entrada.stick.calibracao@pro` — quem lê a calibração é o DRIVER, no
    probe, sem checar `hdev->bus`.

    MORDE: envolva a chamada de `joycon_request_calibration` num
    `if (ctlr->hdev->bus == BUS_USB)` e este teste reprova.
    """

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
        # Nenhuma das duas macros de bus aparece entre a checagem de tipo e a
        # chamada — a única condição é joycon_has_joysticks (tipo do
        # controle), nunca hdev->bus.
        assert "BUS_USB" not in chamada.group(0)
        assert "BUS_BLUETOOTH" not in chamada.group(0)


class TestDriverLedDeJogadorNuncaPisca:
    """`luz.led_jogador.pisca@pro` — o firmware aceita `flash`, o driver
    manda sempre `0`.

    MORDE: troque `joycon_set_player_leds(ctlr, 0, val)` por uma chamada com
    `flash` não-zero e este teste reprova.
    """

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
        # O led_classdev do kernel só ganha capacidade de pisca-agendado com
        # um `blink_set` — o driver não registra um para os LEDs de jogador.
        assert "blink_set" not in DRIVER_SRC


class TestDriverSemTurbo:
    """`luz.recursos_proprios@pro` — sem turbo/LED de modo no driver oficial.

    MORDE: escreva `turbo` em qualquer lugar do driver e este teste reprova.
    """

    def test_driver_nao_menciona_turbo(self) -> None:
        assert not re.search(r"turbo", DRIVER_SRC, re.IGNORECASE)


# ---------------------------------------------------------------------------
# B — ExternalImuEnabler: a assimetria cabo/rádio de movimento.imu.ligar@pro
# ---------------------------------------------------------------------------


class TestExternalImuEnablerAssimetriaCaboRadio:
    """`movimento.imu.ligar@pro` — cabo tenta ligar a IMU (parcial), rádio
    NUNCA tenta (não). O gate é do PRODUTO (`_IMU_ENABLE_ALLOWED_BUS`), e é
    testável sem nenhum Pro Controller na mesa: só precisa que `enable_imu`
    seja chamado (ou não) conforme o `bus` do inventário.

    MORDE: apague o `if bus != _IMU_ENABLE_ALLOWED_BUS: continue` de
    `ExternalImuEnabler.tick` e o teste do rádio reprova (o mock passa a ser
    chamado); troque `_IMU_ENABLE_ALLOWED_BUS` para algo diferente de `"usb"`
    e o teste do cabo reprova.
    """

    #: OUI de teste, fora da faixa do clone conhecido (`e417d8`) e sem o
    #: prefixo sintetizado (`02`) — não é MAC real de aparelho nenhum, é
    #: fixture (mesmo espírito da máscara da casa: nada real em teste
    #: versionado).
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


# ---------------------------------------------------------------------------
# C — as 13 células que esta fatia respondeu no CSV
# ---------------------------------------------------------------------------

#: (chave, cabo_aciona esperado, radio_aciona esperado) — as 13 células que
#: esta fatia (entrada, luz, movimento, energia, gatilho, áudio) respondeu
#: para controle=pro. `entrada.combo.ponte` e `movimento.giroscopio.taxa`
#: ficaram DE PROPÓSITO fora desta lista — nenhum código lido nesta leva
#: sustenta uma resposta para as duas (ver o relatório desta leva).
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
    """Protege as 13 células contra a MESMA armadilha do cabeçalho desta
    casa: fusão de merge anexando texto numa coluna de domínio fechado, ou
    célula voltando a muda sem ninguém perceber.

    MORDE: esvazie `cabo_aciona`/`radio_aciona` de qualquer uma das 13
    linhas, ou troque o valor, e o teste parametrizado daquela chave reprova
    nomeando a chave e o valor achado.
    """

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
        """As 15 células mudas que a orquestração mediu antes de despachar
        esta fatia (7 famílias: entrada, luz, movimento, energia, gatilho,
        áudio, vibração) — 13 respondidas aqui, 2 deixadas explicitamente
        (`entrada.combo.ponte`, `movimento.giroscopio.taxa`: sem Pro na mesa
        e sem código que resolva a pergunta sem medição nova)."""
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
            assert row["cabo_aciona"] == "" and row["radio_aciona"] == "", (
                f"{chave}@pro: esta leva deixou a célula muda de propósito "
                "— se alguém a respondeu depois, atualize esta lista em vez "
                "de deixar o teste reprovar às cegas"
            )
