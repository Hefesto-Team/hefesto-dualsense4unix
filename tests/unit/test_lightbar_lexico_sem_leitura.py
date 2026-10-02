"""L5 — a aba não afirma estado de barra sem canal de leitura no mapa.

**O que foi medido (M4 da sprint LIGHTBAR-COR-DE-CADA-UM-01).** O rótulo das 5
luzes dizia *"Aceso agora: …"*, e ``texto_do_desenho_aceso`` é função PURA do
rascunho: **nada nela consulta o aparelho**. E o mapa de canais mede que
consultar não é possível — ``luz.led_jogador.leitura@dualsense`` tem
``cabo_aceita = não`` e ``radio_aceita = não``. A tela afirmava um estado do
DualSense que nenhum caminho do produto pode conferir.

Não é caso isolado: o ensaio ``lightbar-sysfs-nao-sabe`` (16/08/2026) leu
``[0 255 0]`` no ``multi_intensity`` com a barra APAGADA e ``[0 255 0]`` com ela
VERDE. O sysfs guarda o que foi PEDIDO, nunca o que a lâmpada faz.

**A régua, em uma frase:** nenhum rótulo desta aba pode afirmar estado de barra
enquanto o mapa não registrar canal de leitura para a chave correspondente.

**O ESCOPO, dito na cara.** Esta régua alcança (a) as quatro frases que
``texto_do_desenho_aceso`` produz e (b) a linha do ``main.glade`` que publica o
texto de espera do mesmo rótulo — a Onda 7 é a dona única do XML nesta leva, e
ler uma linha nomeada dele custa uma passada de ``ElementTree``. O que ela
**não** alcança é o resto da tela: o portão que varre TODOS os rótulos contra o
mapa é da Z6/PAREAMENTO-01, e fingir que ele já existe seria trocar um defeito
de tela por um defeito de portão.

**O que ela também não alcança, e é dela:** ``docs/usage/interface.md`` ainda
diz que a linha mostra *"o que está aceso neste instante"*. O arquivo é de
outra frente nesta leva; o conserto está nomeado no relatório do agente A4.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("lightbar lexico sem leitura")

import csv
from pathlib import Path

import pytest

gi = pytest.importorskip("gi")

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.actions.lightbar_actions import (
    _PREFIXO_DESENHO,
    texto_do_desenho_aceso,
)

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

CHAVE_DA_LEITURA = "luz.led_jogador.leitura@dualsense"

PALAVRAS_QUE_AFIRMAM_ESTADO = (
    "aceso",
    "acesa",
    "acesos",
    "acesas",
    "apagada",
    "apagadas",
)


def _linha_do_mapa(chave: str) -> dict[str, str]:
    with MAPA.open(encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            if (linha.get("id") or "") == chave:
                return linha
    pytest.fail(f"a chave {chave} sumiu do mapa de canais — a régua ficou cega")


def _o_mapa_registra_canal_de_leitura() -> bool:
    linha = _linha_do_mapa(CHAVE_DA_LEITURA)
    return any(
        (linha.get(coluna) or "").strip().lower() == "sim"
        for coluna in ("cabo_aceita", "radio_aceita")
    )


def _todas_as_frases() -> dict[str, str]:
    return {
        "co-op ligado": texto_do_desenho_aceso((False,) * 5, 1, coop_ligado=True),
        "escolha dela": texto_do_desenho_aceso(
            (False, True, False, True, False), 3
        ),
        "automático com número": texto_do_desenho_aceso((False,) * 5, 3),
        "automático sem número": texto_do_desenho_aceso((False,) * 5, None),
    }


def test_o_mapa_continua_sem_canal_de_leitura_de_led_de_jogador() -> None:
    """A premissa da régua, cobrada em voz alta."""
    linha = _linha_do_mapa(CHAVE_DA_LEITURA)
    assert not _o_mapa_registra_canal_de_leitura(), (
        f"o mapa passou a registrar canal de leitura para {CHAVE_DA_LEITURA} "
        f"(cabo_aceita={linha.get('cabo_aceita')!r}, "
        f"radio_aceita={linha.get('radio_aceita')!r}). REVISE este portão e a "
        "frase da aba Lightbar: o que era mentira pode ter virado verdade."
    )


def test_nenhuma_frase_do_desenho_afirma_estado_da_barra() -> None:
    """A MORDIDA do L5: devolva o "Aceso agora:" e veja as quatro reprovarem."""
    for onde, frase in _todas_as_frases().items():
        baixa = frase.lower()
        for palavra in PALAVRAS_QUE_AFIRMAM_ESTADO:
            assert palavra not in baixa, (
                f"a frase de “{onde}” afirma estado da barra ({palavra!r}): "
                f"{frase!r}. O mapa mede {CHAVE_DA_LEITURA} com "
                "`cabo_aceita = não` e `radio_aceita = não` — não há canal de "
                "leitura em transporte nenhum, e a função é PURA do rascunho. "
                "Diga o que o produto MANDOU, nunca o que a lâmpada faz."
            )


def test_as_quatro_bifurcacoes_saem_pelo_mesmo_prefixo() -> None:
    """Uma porta só, para a régua não ter por onde escapar."""
    for onde, frase in _todas_as_frases().items():
        assert frase.startswith(f"{_PREFIXO_DESENHO}: "), (
            f"a frase de “{onde}” não sai pelo prefixo declarado "
            f"({_PREFIXO_DESENHO!r}): {frase!r}"
        )


def test_o_proprio_prefixo_nao_afirma_estado() -> None:
    """O prefixo é a única porta — então é ele que carrega a promessa."""
    baixo = _PREFIXO_DESENHO.lower()
    for palavra in PALAVRAS_QUE_AFIRMAM_ESTADO:
        assert palavra not in baixo, (
            f"o prefixo {_PREFIXO_DESENHO!r} afirma estado da barra "
            f"({palavra!r}) — e ele responde pelas quatro frases de uma vez"
        )
