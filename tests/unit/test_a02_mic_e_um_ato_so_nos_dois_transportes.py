"""A queixa 15 dela, em forma de régua — e ela é sobre uma frase INVERTIDA.

<!-- noqa-acento: citação literal -->
**  # noqa-acento: citação

O aviso que ela leu na aba 02, disparado pelo botão "Virtual" do microfone:

    "Só vale no rádio. Pelo cabo o microfone deste controle é uma placa de som
     USB e não passa por esta ponte — ele já funciona sem ela."

**A FÍSICA ESTAVA CERTA E A CONCLUSÃO DE PRODUTO, ERRADA.** O
`docs/data/mapa-controles.csv` diz o contrário linha por linha:

    audio.microfone         cabo_aciona=sim   radio_aciona=parcial
    audio.microfone.mudo    cabo_aciona=sim   radio_aciona=parcial

Quem é PARCIAL no microfone é o RÁDIO. A frase promovia o transporte mais fraco
e recusava o mais forte — e o que "não vale no cabo" nunca foi a feature: é uma
IMPLEMENTAÇÃO dela, a `PonteMicBluetooth`. A frase deu à ponte o nome da
capacidade.

O botão «Virtual | Nativo» saiu da aba 02 (decisão de 02/10/2026, um microfone
por controle, sempre) com o gesto `mic-modo` e a regra que o guardava
(`pode_ligar_o_mic`, `dica_do_microfone`, `tem_canal_de_captura`), que ficaram sem
chamador e saíram em 04/10/2026. Sobra o que a queixa 15 provou e o mapa sustenta: o
microfone é um ato só (o 🎙), e quem é PARCIAL é o rádio, não o cabo.
"""
from __future__ import annotations

import csv
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.config`, que carrega o GTK")

CSV = RAIZ / "docs/data/mapa-controles.csv"


def _linha_do_csv(chave: str) -> dict[str, str]:
    with CSV.open(newline="", encoding="utf-8") as f:
        for linha in csv.DictReader(f):
            if linha["chave"] == chave and linha["controle"] == "dualsense":
                return linha
    raise AssertionError(f"{chave!r} sumiu do mapa-controles.csv")


def test_o_csv_diz_que_quem_e_parcial_no_microfone_e_o_radio() -> None:
    """A medição que derruba a frase. Se ela mudar, esta régua muda junto."""
    for chave in ("audio.microfone", "audio.microfone.mudo"):
        linha = _linha_do_csv(chave)
        assert linha["cabo_aciona"] == "sim", (
            f"{chave}: o cabo deixou de acionar — a frase 'só vale no rádio' "
            f"voltaria a fazer sentido, e isso é notícia, não detalhe"
        )
        assert linha["radio_aciona"] == "parcial", (
            f"{chave}: o rádio deixou de ser parcial"
        )


def test_o_alto_falante_age_pelo_radio_e_o_canal_continua_declarado() -> None:
    """No rádio o alto-falante AGE — e a diferença de canal continua declarada."""
    linha = _linha_do_csv("audio.alto_falante")
    assert linha["radio_aciona"] == "sim", (
        "o alto-falante voltou a não acionar no rádio — o `0x35` e a háptica "
        "pelo `0x32` provaram o canal em 10/09 e 18/09")
    assert linha["cabo_canal"] != linha["radio_canal"]
    assert linha["assimetria_declarada"].strip(), (
        "a assimetria de CANAL do alto-falante perdeu a declaração — sem ela o "
        "portão de paridade não sabe por que cabo e rádio usam canais diferentes"
    )


def test_a_aba_02_nao_condiciona_mais_o_microfone_ao_transporte() -> None:
    """A varredura: nenhuma frase da aba recusa o microfone por transporte."""
    import aba02

    import pacotes.a02_controles as a02

    textos = " ".join(
        str(getattr(mod, nome))
        for mod in (aba02, a02)
        for nome in dir(mod)
        if nome.startswith(("DICA_", "ROTULO_", "TEXTO_", "SEM_"))
        and isinstance(getattr(mod, nome), str)
    ).lower()
    for proibida in ("só vale no rádio. pelo cabo o microfone",
                     "não passa por esta ponte"):
        assert proibida not in textos, (
            f"{proibida!r} voltou aos textos da aba 02 — é a frase invertida da "
            f"queixa 15 dela"
        )
