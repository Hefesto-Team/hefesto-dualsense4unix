"""A bancada fala a forma A — A-FORJA-VALIDA-O-SOM-01, 24/09/2026.

A decisão dela de 23/09 mudou o nome que a lista de som mostra: a saída e a
entrada de cada controle passaram a se chamar «Alto-falante do Controle N
(DualSense Wireless Controller)» e «Microfone do Controle N (DualSense
Wireless Controller)». Os dois arquivos do gesto (`docs/method/…O-COMO-*`) são
DADO — a página da bancada os lê —, e um gesto que manda escolher «Alto-falante
do Controle 2» numa lista em que ele não existe mais com esse nome manda
procurar o que não está lá.

A RÉGUA PERGUNTA AO DONO: o nome esperado sai de
`alto_falante_bt.rotulo_do_alto_falante` e de
`vestido_de_dualsense.com_o_nome_da_sony`, não é digitado aqui. O gesto que
diz «a que COMEÇA com «Alto-falante do Controle 3»» continua certo em qualquer
forma, e fica de fora de propósito.

AS MORDIDAS: arrancar o sufixo do produto (o `com_o_nome_da_sony` devolvendo o
rótulo cru) reprova, porque o gesto fala a forma A; e devolver uma célula ao
nome velho reprova, porque o produto fala a forma A.
"""

from __future__ import annotations

import re
from pathlib import Path

from hefesto_dualsense4unix.integrations.alto_falante_bt import rotulo_do_alto_falante
from hefesto_dualsense4unix.integrations.vestido_de_dualsense import com_o_nome_da_sony

_RAIZ = Path(__file__).resolve().parents[2]
_GESTOS = (
    _RAIZ / "docs/method/2026-09-07-O-COMO-DO-MAPA-o-gesto-das-178-celulas.md",
    _RAIZ / "docs/method/2026-09-07-O-COMO-DAS-21-o-gesto-exato-de-cada-linha.md",
)

#: O rótulo citado entre aspas, com o número do jogador (ou o N genérico).
_CITADO = re.compile(r"«((Alto-falante|Microfone) do Controle ([1-4N]))([^»]*)»")
#: Quem cita pelo COMEÇO não depende da forma — e é a leitura certa para contar.
_PELO_COMECO = re.compile(r"(começa com|começam com|outra com) $")


def _esperado(base: str, qual: str, numero: str) -> str:
    if qual == "Alto-falante" and numero.isdigit():
        return rotulo_do_alto_falante(int(numero))
    return com_o_nome_da_sony(base)


def _citacoes() -> list[tuple[str, int, str, str]]:
    """`(arquivo, linha, citado, esperado)` de cada nome exato que um gesto manda achar."""
    fora = []
    for arquivo in _GESTOS:
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            for m in _CITADO.finditer(linha):
                if _PELO_COMECO.search(linha[: m.start()]):
                    continue
                citado = m.group(1) + m.group(4)
                fora.append((arquivo.name[:30], n, citado, _esperado(*m.group(1, 2, 3))))
    return fora


def test_o_gesto_manda_achar_o_nome_que_a_lista_mostra() -> None:
    citacoes = _citacoes()
    assert len(citacoes) >= 20, f"só {len(citacoes)} citações — a régua ficou cega"
    erradas = [c for c in citacoes if c[2] != c[3]]
    assert not erradas, "\n".join(
        f"{arq}:{n}: o gesto cita «{citado}» e a lista mostra «{esperado}»"
        for arq, n, citado, esperado in erradas
    )


def test_quem_conta_pelo_comeco_nao_depende_da_forma() -> None:
    """O contraste: «a que começa com …» sobrevive às duas formas, e é assim que se conta."""
    for base in ("Alto-falante do Controle 3", "Microfone do Controle 1"):
        assert com_o_nome_da_sony(base).startswith(base)
