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

A MORDIDA, PROVADA EM 25/08/2026 — ver o relatório do agente E1.
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
#: `/proc/asound/cards` usa — copiado da bancada dela de 15/08/2026, sem
#: nenhum dado de identidade (o `/proc/asound/cards` não traz endereço).
CARDS_COM_DUALSENSE = """\
 0 [HDMI           ]: HDA-Intel - HDA ATI HDMI
                      HDA ATI HDMI at 0xfe960000 irq 66
 2 [Controller     ]: USB-Audio - DualSense Wireless Controller
                      Sony Interactive Entertainment DualSense Wireless Controller at usb-0000:0d
"""

#: A mesma máquina com os controles no RÁDIO: nenhuma placa do controle.
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


# ---------------------------------------------------------------------------
# O defeito
# ---------------------------------------------------------------------------
def test_sem_placa_do_controle_a_tela_nao_escreve_ligado_em_verde(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O caso exato do defeito: drop-ins no lugar, alvo nenhum.

    ARRANQUE A CURA: apague o ramo `if self._placas_de_microfone() == 0` de
    `_mic_state` e este caso REPROVA — a tela volta a `MIC_LIGADO` e ao verde.
    """
    obj, rotulo = _tela(tmp_path, monkeypatch, CARDS_SEM_DUALSENSE)
    obj._wp_dropin_dir().joinpath(PROMOTOR).write_text("x", encoding="utf-8")

    assert obj._mic_state() == Mixin.MIC_SEM_ALVO, (
        "a aba concluiu 'Ligado' sem ter olhado se existe microfone a ligar"
    )
    obj._refresh_mic_status()
    assert "#50fa7b" not in rotulo.markup, f"verde sem alvo: {rotulo.markup}"
    assert "Ligado" not in rotulo.markup, rotulo.markup


def test_com_placa_do_controle_o_verde_volta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O contrapeso, sem o qual "curar" viraria nunca mais dizer Ligado."""
    obj, rotulo = _tela(tmp_path, monkeypatch, CARDS_COM_DUALSENSE)
    obj._wp_dropin_dir().joinpath(PROMOTOR).write_text("x", encoding="utf-8")

    assert obj._mic_state() == Mixin.MIC_LIGADO
    obj._refresh_mic_status()
    assert rotulo.markup == '<span foreground="#50fa7b">Ligado</span>', rotulo.markup


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
    """O alvo fecha o ramo VERDE, e só ele.

    "Suprimido" é um drop-in que NÓS escrevemos: é verdade com placa e sem
    placa, e trocá-lo por "sem alvo" seria esconder uma escolha dela atrás de
    uma ausência de hardware.
    """
    obj, _rotulo = _tela(tmp_path, monkeypatch, cards)
    obj._wp_dropin_dir().joinpath(PROMOTOR).write_text("x", encoding="utf-8")
    obj._wp_dropin_dir().joinpath(DISABLE_SRC).write_text("x", encoding="utf-8")
    assert obj._mic_state() == esperado


def test_sem_promotor_continua_sendo_sem_promotor_mesmo_sem_placa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A outra metade da mesma regra — a LIGAR-QUE-APAGAVA-A-CURA-01 fica de pé."""
    obj, rotulo = _tela(tmp_path, monkeypatch, CARDS_SEM_DUALSENSE)
    assert obj._mic_state() == Mixin.MIC_SEM_PROMOTOR
    obj._refresh_mic_status()
    assert "sem prioridade" in rotulo.markup, rotulo.markup


# ---------------------------------------------------------------------------
# A frase — o que ela pode e o que ela NÃO pode dizer
# ---------------------------------------------------------------------------
def test_a_frase_nao_conclui_que_o_aparelho_esta_mudo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A régua mede a ROTA, e a frase não pode falar do APARELHO.

    Medido em 15/08/2026 e escrito no mapa (`assimetria_declarada`): os
    controles do rádio não têm placa ALSA nenhuma, o que prova que a rota ALSA
    não existe no rádio — **não** que o aparelho não capte por rádio. Uma frase
    que conclua "o microfone não funciona" transforma a medição no seu oposto.

    ARRANQUE A CURA: troque a dica por "o microfone deste controle não
    funciona" e este caso REPROVA.
    """
    obj, rotulo = _tela(tmp_path, monkeypatch, CARDS_SEM_DUALSENSE)
    obj._wp_dropin_dir().joinpath(PROMOTOR).write_text("x", encoding="utf-8")
    obj._refresh_mic_status()
    dica = rotulo.tooltip

    assert "placa de áudio" in dica, (
        f"a dica parou de dizer o que a régua realmente olhou: {dica!r}"
    )
    for proibido in (
        "não funciona",
        "não capta",
        "está mudo",
        "sem microfone no controle",
    ):
        assert proibido not in dica, (
            f"a dica conclui sobre o APARELHO a partir de uma medição de ROTA "
            f"({proibido!r}): {dica!r}"
        )
    # E diz o que fazer — a régua da casa para toda frase de diagnóstico.
    assert "cabo" in dica and "Atualizar" in dica, dica


def test_toda_dica_do_microfone_diz_de_qual_microfone_se_trata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E4, metade de tela: a palavra "microfone" ganha sobrenome.

    Em TODOS os quatro estados, não só no novo — o escopo não muda com o
    estado, e uma frase que só aparece num ramo é uma frase que a maioria das
    visitas não lê.

    ARRANQUE A CURA: tire o `ESCOPO_DO_MICROFONE_DESTA_ABA` do
    `set_tooltip_text` e este caso REPROVA nos quatro.
    """
    vistos = set()
    for cards, arquivos in (
        (CARDS_COM_DUALSENSE, (PROMOTOR,)),
        (CARDS_SEM_DUALSENSE, (PROMOTOR,)),
        (CARDS_COM_DUALSENSE, ()),
        (CARDS_COM_DUALSENSE, (PROMOTOR, DISABLE_SRC)),
    ):
        pasta = tmp_path / f"caso{len(vistos)}"
        obj, rotulo = _tela(pasta, monkeypatch, cards)
        for nome in arquivos:
            obj._wp_dropin_dir().joinpath(nome).write_text("x", encoding="utf-8")
        vistos.add(obj._mic_state())
        obj._refresh_mic_status()
        assert Mixin.ESCOPO_DO_MICROFONE_DESTA_ABA in rotulo.tooltip, (
            f"estado {obj._mic_state()!r} sem o escopo na dica: {rotulo.tooltip!r}"
        )
    assert vistos == {
        Mixin.MIC_LIGADO,
        Mixin.MIC_SEM_ALVO,
        Mixin.MIC_SEM_PROMOTOR,
        Mixin.MIC_SUPRIMIDO,
    }, f"os quatro estados não foram exercidos: {vistos}"


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
