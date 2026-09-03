"""A pele do cartão não pode ficar com a cor de OUTRO modelo.

O DEFEITO, achado pelos DOIS auditores independentes da leva de 03/09/2026 e
medido no WebKit desta máquina:

    Com um **Grey Camouflage** no cabo do P1, o ``data-colorway`` do desenho
    vira ``grey-camouflage`` — e a pele três centímetros ao lado fica
    ``rgb(174, 51, 90)``, que é ``#ae335a``: **o Cosmic Red do MOCKUP**.

**A causa.** Oito dos vinte e oito modelos dela não têm hexa amostrado — Grey
Camouflage, Chroma Teal, Chroma Indigo, Chroma Pearl, Ghost of Yōtei, Marathon,
Genshin Impact e 007 First Light. Para eles ``monta.cor_da_zona`` devolve
``url(#hachura-sem-hex)``, que pinta um ``fill`` de SVG e **não é uma cor**.
Esse valor viajava até o alvo ``cor`` do piloto, que faz
``el.style.color = v``; o CSSOM **recusa em silêncio** o que não é cor, e o que
sobrava na tela era o hexa congelado no HTML do mockup.

**É a queixa dela literal, com os donos trocados** — *"os svgs do dualsense (…)
mudam de acordo com o controle identificado no canto superior (…) isso tá
errado"*. E é pior que não pintar: não pintar é uma lacuna; pintar OUTRO MODELO
é uma afirmação falsa. São 8 de 28 — **29% do mapa dela**.

A CURA TEM UM DONO SÓ, :func:`monta.cor_de_css`, e o discriminador é a FORMA do
valor — quem não começa por ``#`` não é cor. Nenhuma lista de oito é digitada,
então ele continua certo no dia em que ela amostrar mais um modelo.

A MORDIDA: troque `cor_de_css` de volta por `cor_da_zona` em qualquer das
quatro abas e :func:`test_nenhuma_aba_manda_url_para_campo_de_cor` reprova
nomeando a aba e o modelo.
"""

from __future__ import annotations

import sys
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

# O `sys.path` acima é o mesmo que o `pacotes/__init__` monta.
import monta

from hefesto_dualsense4unix.interface.pacotes import (
    a01_jogar,
    a03_gatilhos,
    a04_iluminacao,
    a06_navegacao,
)

#: AS QUATRO ABAS QUE PINTAM A PELE, e a função de cada uma. Nomear as quatro é
#: o que faz este teste alcançar a aba que alguém esquecer de migrar.
QUEM_PINTA = {
    "01-jogar": a01_jogar._cor_do_plastico,
    "03-gatilhos": a03_gatilhos._cor_do_plastico,
    "04-iluminacao": a04_iluminacao._cor_do_plastico,
    "06-navegacao": a06_navegacao.cor_do_plastico,
}

#: OS VINTE E OITO, e a lista NÃO se digita: sai de `monta.DS`, que é a folha
#: que `scripts/gerar_cores_do_dualsense.py` escreveu a partir do CSV dela.
#: Digitá-la aqui seria a segunda verdade que esta casa persegue — e ela
#: envelheceria no dia em que ela catalogar o vigésimo nono.
TODOS = tuple(monta.DS_SLUGS) if hasattr(monta, "DS_SLUGS") else ()


def _todos_os_modelos() -> list[str]:
    """Os slugs que a folha publica, lidos dela."""
    import re

    return sorted(set(re.findall(r'svg\[data-colorway="([^"]+)"\]', monta.DS)))


@pytest.mark.parametrize("aba", sorted(QUEM_PINTA))
def test_nenhuma_aba_manda_url_para_campo_de_cor(aba: str) -> None:
    """Nenhum dos 28 modelos faz a aba emitir algo que o CSS recusa.

    O alvo ``cor`` do piloto escreve em ``style.color``. Qualquer valor que não
    seja uma cor é recusado EM SILÊNCIO, e o silêncio é o defeito: a tela fica
    com o que estava — o hexa do mockup.
    """
    pinta = QUEM_PINTA[aba]
    ruins = {m: v for m in _todos_os_modelos()
             if (v := pinta(m)) and not v.startswith("#")}
    assert not ruins, (
        f"a aba {aba} manda para um campo de COR um valor que o CSS não "
        f"aceita: {ruins}. O CSSOM recusa em silêncio e a pele fica com o hexa "
        "do mockup — outro modelo, afirmado com confiança")


@pytest.mark.parametrize("aba", sorted(QUEM_PINTA))
def test_os_oito_sem_amostragem_calam_em_vez_de_mentir(aba: str) -> None:
    """Sem hexa amostrado, a resposta é `""` — a regra dela.

    *Campo sem informação não mostra nada.* O `""` faz o alvo `cor` APAGAR a
    declaração em linha, e a pele cai no neutro da folha: um controle sem cor
    de plástico, que é o honesto quando a amostragem não existe.
    """
    sem_hexa = [m for m in _todos_os_modelos()
                if not str(monta.cor_da_zona(m)).startswith("#")]
    assert sem_hexa, "nenhum modelo sem hexa — a folha mudou de forma"
    for modelo in sem_hexa:
        assert QUEM_PINTA[aba](modelo) == "", (
            f"{aba} responde algo para {modelo}, que não tem hexa amostrado")


@pytest.mark.parametrize("aba", sorted(QUEM_PINTA))
def test_quem_tem_hexa_continua_vestindo(aba: str) -> None:
    """A cura não pode ter calado quem TINHA cor.

    Uma guarda que devolvesse `""` para tudo passaria os dois testes de cima e
    deixaria os 28 modelos sem cor nenhuma — o oposto da lei dela.
    """
    com_hexa = [m for m in _todos_os_modelos()
                if str(monta.cor_da_zona(m)).startswith("#")]
    assert len(com_hexa) >= 20, f"só {len(com_hexa)} modelos com hexa"
    for modelo in com_hexa:
        assert QUEM_PINTA[aba](modelo) == monta.cor_da_zona(modelo), (
            f"{aba} deixou de vestir {modelo}, que TEM hexa no mapa dela")


def test_as_quatro_abas_respondem_igual() -> None:
    """As quatro leem o mesmo dado, então não podem divergir.

    Elas são gêmeas deliberadas — cada aba tem a sua para não acoplar-se ao
    arquivo que outra frente edita no mesmo dia —, mas o DADO tem um dono só.
    Divergirem é o sinal de que uma delas parou de chamá-lo.
    """
    for modelo in _todos_os_modelos():
        respostas = {aba: f(modelo) for aba, f in QUEM_PINTA.items()}
        assert len(set(respostas.values())) == 1, (
            f"as abas discordam sobre {modelo}: {respostas}")


def test_o_desenho_continua_recebendo_os_oito() -> None:
    """Calar a PELE não pode ter calado o DESENHO.

    O ``<pattern>`` vale no contexto em que ele é válido — o ``fill`` do SVG —,
    e é ali que os oito modelos ganham a hachura. Se o ``data-colorway`` também
    tivesse sido calado, a cura teria trocado um defeito por outro maior: o
    controle sem identidade nenhuma.
    """
    sem_hexa = [m for m in _todos_os_modelos()
                if not str(monta.cor_da_zona(m)).startswith("#")]
    for modelo in sem_hexa:
        assert a01_jogar._colorway_do_desenho(modelo) == modelo, (
            f"o desenho deixou de receber {modelo} — a hachura vale no SVG")
