"""EMULACAO-UM-DONO-SO-01/E3 — o verde que não tinha alvo.

O DEFEITO
==========
``_mic_state`` decidia entre três estados olhando **só** a presença de três
arquivos em ``~/.config/wireplumber/wireplumber.conf.d/``. Sem nenhuma placa de
áudio do controle no sistema o ramo era exatamente o mesmo, e a aba escrevia
**Ligado** em ``#50fa7b`` com a dica *"o microfone do controle está livre e com
prioridade acima do eco da saída"*. Verde sobre um alvo que a aba nunca olhou —
e o caso mais comum dele não é exótico: **é o controle no rádio**, onde não
existe placa ALSA nenhuma (medido 15/08/2026, ``audio.microfone@dualsense``,
``assimetria_declarada``).

A RÉGUA DO ALVO, E O QUE ELA NÃO PROVA
=======================================
A régua é a presença de placa ALSA do DualSense em ``/proc/asound/cards``,
contada pela função pura ``storm_doctor.contar_placas_dualsense``. A sprint
exige que a régua seja declarada, e exige mais: *"se for a presença de placa
ALSA, isso prova que a ROTA ALSA não existe, não que o aparelho não capte"*. É
a mesma distinção que o mapa escreve com todas as letras, e o caso
``test_a_frase_nao_conclui_que_o_aparelho_esta_mudo`` a guarda — porque
formulação errada aqui vira fato falso amanhã.

POR QUE O ALVO SÓ FECHA O RAMO VERDE
=====================================
Os dois estados laranja descrevem a NOSSA configuração (um drop-in que
escrevemos está lá, ou o promotor está faltando) e continuam verdadeiros com
placa ou sem placa. O ramo verde descreve **o aparelho**, e é só ele que
precisa de alvo para não mentir.

A MORDIDA, PROVADA EM 25/08/2026 — ver o relatório da mordida E1.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("gi")

from hefesto_dualsense4unix.app.actions.emulation_actions import (
    EmulationActionsMixin as Mixin,
)

PROMOTOR = "51-hefesto-dualsense-no-default-source.conf"
DISABLE_SRC = "52-hefesto-dualsense-disable-source.conf"

#: Duas placas DualSense, no formato de duas linhas por placa que o
CARDS_COM_DUALSENSE = """\
 0 [HDMI           ]: HDA-Intel - HDA ATI HDMI
                      HDA ATI HDMI at 0xfe960000 irq 66
 2 [Controller     ]: USB-Audio - DualSense Wireless Controller
                      Sony Interactive Entertainment DualSense Wireless Controller at usb-0000:0d
"""

CARDS_SEM_DUALSENSE = """\
 0 [HDMI           ]: HDA-Intel - HDA ATI HDMI
                      HDA ATI HDMI at 0xfe960000 irq 66
"""


class _RotuloFalso:
    def __init__(self) -> None:
        self.markup = ""
        self.tooltip = ""

    def set_markup(self, m: str) -> None:
        self.markup = m

    def set_tooltip_text(self, t: str) -> None:
        self.tooltip = t


def _tela(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cards: str
) -> tuple[Mixin, _RotuloFalso]:
    """A aba com um `wireplumber.conf.d` de mentira e um `cards` declarado.

    O `cards` é parâmetro, e é assim de propósito: um teste cujo resultado
    depende de haver um DualSense no cabo desta bancada é o vício de bancada
    que a NO-MEU-FUNCIONA-01 nomeia.
    """
    dropins = tmp_path / "wireplumber.conf.d"
    dropins.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Mixin, "_wp_dropin_dir", staticmethod(lambda: dropins))
    arquivo = tmp_path / "cards"
    arquivo.write_text(cards, encoding="utf-8")
    monkeypatch.setattr(Mixin, "_PLACAS_ALSA", str(arquivo))
    obj = Mixin()
    rotulo = _RotuloFalso()
    monkeypatch.setattr(obj, "_get", lambda _id: rotulo, raising=False)
    return obj, rotulo


@pytest.mark.parametrize(
    ("cards", "esperado"),
    [
        (CARDS_SEM_DUALSENSE, Mixin.MIC_SUPRIMIDO),
        (CARDS_COM_DUALSENSE, Mixin.MIC_SUPRIMIDO),
    ],
)
def test_o_alvo_nao_apaga_o_que_a_nossa_configuracao_ja_sabia(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cards: str, esperado: str
) -> None:
    """O alvo fecha o ramo VERDE, e só ele."""
    obj, _rotulo = _tela(tmp_path, monkeypatch, cards)
    obj._wp_dropin_dir().joinpath(PROMOTOR).write_text("x", encoding="utf-8")
    obj._wp_dropin_dir().joinpath(DISABLE_SRC).write_text("x", encoding="utf-8")
    assert obj._mic_state() == esperado


def test_o_escopo_nomeia_as_outras_duas_superficies_do_mesmo_nome() -> None:
    """O sobrenome só serve se disser de qual dos três microfones NÃO se trata."""
    escopo = Mixin.ESCOPO_DO_MICROFONE_DESTA_ABA
    assert "perfil" in escopo, escopo
    assert "Bluetooth" in escopo, escopo


def test_a_regua_do_alvo_le_o_arquivo_e_nao_um_veredito_cravado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A contagem muda com o arquivo — inclusive quando ele não dá para ler."""
    monkeypatch.setattr(Mixin, "_PLACAS_ALSA", str(tmp_path / "nao-existe"))
    assert Mixin._placas_de_microfone() == 0

    arquivo = tmp_path / "cards"
    arquivo.write_text(CARDS_COM_DUALSENSE, encoding="utf-8")
    monkeypatch.setattr(Mixin, "_PLACAS_ALSA", str(arquivo))
    assert Mixin._placas_de_microfone() == 1

    arquivo.write_text(CARDS_SEM_DUALSENSE, encoding="utf-8")
    assert Mixin._placas_de_microfone() == 0
