"""O OITAVO CONFLITO de 04/09/2026 — a proibição olhava o lugar errado.

Ela, 31/08/2026, sobre o aviso do Modo Nativo: *"qualquer coisa fora isso tá
incorreta"*. A regra que sobrou é **NENHUM ALARME SEM MEDIÇÃO**: as três frases
banidas alarmavam sobre número que ensaio nenhum deste repositório mede.

A PROIBIÇÃO EXISTIA, E MESMO ASSIM O CAMINHO ESTAVA ABERTO. Ela vivia dentro de
`aba01._conferir`, que lê o **HTML ESTÁTICO** da página gerada. A coluna Atenção
é escrita em **tempo de execução**, pelo `_json` do piloto. Um agente cumprindo
a decisão [01] ao pé da letra (*"o aviso do Modo Nativo na coluna Atenção"*)
poria a frase na tela dela **com o gerador VERDE** — e foi a frente da aba 01
que viu isso e RECUSOU escrever, em vez de cumprir a decisão e passar o portão.

É a mesma família dos sete conflitos do `O-PO-DECIDE`, e a decisão de PO é a
mesma: **a decisão dela de 31/08 vence a recomendação de 04/09**. A coluna
Atenção pode dizer o ESTADO MEDIDO; não pode profetizar consequência.

Esta régua tem as três metades que faltavam:
  1. a lista mora em UM lugar e as duas guardas a LEEM;
  2. a guarda de EXECUÇÃO existe e recusa;
  3. a guarda estática continua de pé.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
    FRASES_BANIDAS,
    frase_banida_em,
)

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"


def test_a_lista_tem_as_tres_e_a_busca_e_por_substring() -> None:
    assert set(FRASES_BANIDAS) == {
        "derrubam o controle",
        "resultado é ZERO",
        "duros como no PS5",
    }
    assert frase_banida_em("Alguns jogos derrubam o controle no meio") == (
        "derrubam o controle"
    )
    assert frase_banida_em("Modo Nativo ligado · Ponte com o jogo desligada") is None


def test_o_funil_de_execucao_recusa_a_frase() -> None:
    """A METADE QUE FALTAVA: o caminho de RUNTIME, não o HTML estático."""
    import sys

    sys.path.insert(0, str(INTERFACE))
    import hefesto_vivo as hv

    assert hv._json({"mesa": {"aviso-texto": ["tudo certo"]}})
    with pytest.raises(ValueError) as erro:
        hv._json({"colunas": {"aviso-texto": ["Alguns jogos derrubam o controle"]}})
    assert "derrubam o controle" in str(erro.value)
    assert "NENHUM ALARME SEM MEDIÇÃO" in str(erro.value)


def test_a_guarda_estatica_continua_de_pe_e_le_a_lista() -> None:
    """E ela não pode voltar a DIGITAR a lista — foi assim que divergiu."""
    fonte = (INTERFACE / "aba01.py").read_text(encoding="utf-8")
    assert "for frase in FRASES_BANIDAS:" in fonte, (
        "o `_conferir` voltou a digitar as frases; com duas cópias, uma "
        "quarta frase banida entraria só numa delas."
    )
    for frase in FRASES_BANIDAS:
        assert re.search(rf'"{re.escape(frase)}"[,)]', fonte) is None, (
            f"a frase {frase!r} está DIGITADA em aba01.py — a lista é uma só."
        )


def test_nenhuma_aba_publicada_carrega_a_frase() -> None:
    """E o estático de verdade: as dez páginas do produto e as dez do mockup."""
    sujas = []
    for pasta in (INTERFACE / "paginas", RAIZ / "mockup"):  # (noqa-acento) diretório
        for pagina in sorted(pasta.glob("*.html")):
            achada = frase_banida_em(pagina.read_text(encoding="utf-8"))
            if achada:
                sujas.append(f"{pagina.relative_to(RAIZ)}: {achada!r}")
    assert not sujas, "frase banida numa página:\n  " + "\n  ".join(sujas)
