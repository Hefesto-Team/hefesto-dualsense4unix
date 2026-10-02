"""LUZ-CEGA-01/E2 — o card diz o que o campo MEDE, e não o que ele deduz.

O `lightbar_disputada` está CERTO: medido com `fuser`, a Steam segura os oito
`hidraw` da bancada (quatro DualSense + quatro vpads nossos). O que estava
errado era a frase que a tela derivava dele — *"a Steam também escreve nesta
barra"* —, porque **segurar não é escrever**, e o fio já disse quem escreve:

===========================  ==========================
janela de 32 s com `btmon`   reports de saída
===========================  ==========================
daemon PARADO                **1**
daemon RODANDO               **426**
===========================  ==========================

Steam aberta nos dois lados. A frase antiga mandava a pessoa procurar o defeito
na Steam, que é o lugar onde ele não está — a família ELO-MUDO-01 (o produto
afirmando o que não mediu).

MORDIDA (conferida nos dois sentidos, 22/08/2026):

- devolvendo a frase antiga em `rotulo_lightbar`: reprovam **3 de 4**;
- trocando o rótulo por um genérico sem a Steam ("Outro programa tem este
  controle aberto"): reprova **1 de 4** — o caso que amarra a frase ao alcance
  da sonda.

E a régua se valida sozinha: `test_a_regua_reconhece_a_frase_antiga` cobra que
o detector de acusação REPROVE a frase que existiu de verdade. Sem esse caso,
uma lista de verbos vazia deixaria o arquivo inteiro verde sem medir nada.
"""
from __future__ import annotations

from typing import Any

from hefesto_dualsense4unix.app.widgets.controller_card import (
    ROTULO_LIGHTBAR_SEGURADA,
    rotulo_lightbar,
)

VERBOS_DE_ESCRITA = (
    "escreve",
    "escrevendo",
    "escreveu",
    "pinta",
    "pintando",
    "repinta",
    "sobrescreve",
    "rouba",
    "roubou",
    "apaga",
    "apagou",
)

FRASE_ANTIGA = "A Steam também escreve nesta barra"

ENTRY_DISPUTADA: dict[str, Any] = {
    "lightbar_rgb": [0, 255, 0],
    "lightbar_on": True,
    "lightbar_source": "sysfs",
    "lightbar_disputada": True,
}


def acusa_escrita(frase: str) -> bool:
    """True quando a frase atribui a ESCRITA da barra a um terceiro."""
    baixa = frase.lower()
    return any(verbo in baixa for verbo in VERBOS_DE_ESCRITA)


def test_a_regua_reconhece_a_frase_antiga() -> None:
    """O detector tem de REPROVAR a frase que existiu — senão não mede nada."""
    assert acusa_escrita(FRASE_ANTIGA), (
        "a régua deixou passar a própria frase que motivou o achado F2"
    )
    assert not acusa_escrita("A Steam tem este controle aberto")


def test_o_card_nao_acusa_ninguem_de_escrever_na_barra() -> None:
    """Com o `fd` segurado, o card não pode afirmar quem ESCREVEU."""
    rotulo, base = rotulo_lightbar(dict(ENTRY_DISPUTADA), {})
    assert rotulo is not None
    assert not acusa_escrita(rotulo), (
        f"o card voltou a atribuir a escrita a um terceiro: {rotulo!r}"
    )
    assert base == (0, 255, 0)


def test_o_card_afirma_exatamente_o_que_o_fuser_viu() -> None:
    """O que foi medido é um `fd` ABERTO. É isso, e só isso, que a frase diz."""
    rotulo, _base = rotulo_lightbar(dict(ENTRY_DISPUTADA), {})
    assert rotulo is not None
    assert "aberto" in rotulo.lower(), (
        "a frase perdeu o único fato medido (o controle está aberto por outro "
        f"processo): {rotulo!r}"
    )
    assert rotulo == ROTULO_LIGHTBAR_SEGURADA


def test_a_frase_nomeia_quem_a_sonda_sabe_reconhecer() -> None:
    """A frase e o ALCANCE da sonda andam juntos — F6 não passa em silêncio."""
    from hefesto_dualsense4unix.core import escritor_cru

    rotulo, _base = rotulo_lightbar(dict(ENTRY_DISPUTADA), {})
    assert rotulo is not None and "steam" in rotulo.lower()

    criterios = [
        escritor_cru._AGULHA_DA_STEAM_NA_CMDLINE,
        escritor_cru._COMM_EXATO_DA_STEAM,
    ]
    assert all(criterios), "a sonda ficou sem critério — a régua ficou cega"
    assert all("steam" in c.lower() for c in criterios), (
        f"a sonda passou a reconhecer escritor fora da Steam ({criterios}) e a "
        f"frase do card continua nomeando a Steam: {rotulo!r}"
    )
