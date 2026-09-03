"""A régua da aba 03: o que o mapa dela NÃO diz em hexadecimal não vira borda.

A LEI, e ela é dela (03/09/2026)::

    "imagina que cada pessoa tenha um dualsense diferente. eu mapeei as cores,
     glifos, controles, id e tudo mais. é pro projeto usar esse meu trabalho"

O DEFEITO QUE ESTA RÉGUA MORDE, e ele estava vivo até hoje: o chip da coluna
escrevia no `--plastico` **o que quer que `monta.cor_da_zona` devolvesse**. Em
vinte dos vinte e oito modelos isso é um hexadecimal e está certo. Nos outros
OITO o mapa dela responde a HACHURA DO SEM-HEX — `url(#hachura-sem-hex)` —, que
é a ausência declarada: *"o acabamento não cabe num hexadecimal (iridescente,
metálico, camuflado, arte)"*.

    Grey Camouflage · Chroma Teal · Chroma Indigo · Chroma Pearl
    Ghost of Yōtei · Marathon · Genshin Impact · 007 First Light

O QUE ISSO FAZIA NA TELA, medido no WebKit desta máquina em 03/09/2026 com a
regra que o `topo.html` declara
(`.chip.plastico{border-color:var(--plastico, var(--border-forte))}`)::

    --plastico:#ae335a                → rgb(174, 51, 90)   a cor do plástico
    --plastico ausente                → rgb(98, 114, 164)  a QUEDA declarada
    --plastico:url(#hachura-sem-hex)  → rgb(139, 233, 253) a cor do TEXTO

A terceira linha é o defeito. Uma `var()` que resolve para algo que a
propriedade não aceita fica **inválida no tempo de valor computado**, e aí o
navegador NÃO usa a queda escrita ao lado: ele volta ao valor herdado, que numa
`border-color` é o `currentColor`. Quem tivesse um Chroma Teal veria a borda
com a cor da LETRA e a dica ao lado dizendo *"a borda é a cor do plástico"*.
Uma cor na tela que ninguém mediu, com uma frase confirmando que mediu.

AS DUAS AUSÊNCIAS SÃO DIFERENTES, e a tela tem de saber dizer qual é qual —
porque uma se conserta lendo o aparelho e a outra não se conserta::

    o mapa RESPONDEU e não é cor    o acabamento não cabe num hexadecimal
    ninguém leu a cor               pelo rádio ela pode não chegar nunca, hoje

A segunda já tem régua (`test_sem_cor_lida_o_chip_nao_veste_plastico`, no
`test_aba03_a_identidade_vem_de_cima.py`). Esta é a primeira — e a frase que
acompanha as duas.

COMO ARRANCAR A CURA E VER ESTA RÉGUA REPROVAR: em
`pacotes/a03_gatilhos.cor_de_borda`, troque o corpo por `return tinta`.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
sys.path.insert(0, str(INTERFACE))

#: A FRASE QUE SÓ PODE SER DITA COM COR. Ela é a agulha desta régua: onde não há
#: hexadecimal, esta afirmação é falsa, e uma dica falsa é pior que uma dica
#: ausente — ela confirma para quem lê que a borda foi medida.
AFIRMA_A_COR = "a borda é a cor do plástico"


@pytest.fixture(scope="module")
def a03():
    import pacotes  # noqa: F401  (registra os dez)
    from pacotes import a03_gatilhos

    return a03_gatilhos


@pytest.fixture(scope="module")
def mapa_das_cores() -> list[tuple[str, str, str]]:
    """`(slug, nome, tinta)` dos VINTE E OITO modelos que ela mapeou.

    A lista sai de `mesa_viva.CORES` (código de fábrica → colorway) e a tinta de
    `monta.cor_da_zona`, que LÊ a folha gerada de
    `docs/data/cores-do-dualsense.csv`. Nenhuma cor é digitada aqui: uma tabela
    nesta régua seria a segunda verdade que o CSV existe para matar, e ela
    envelheceria calada no dia em que ela mapear o vigésimo nono modelo.
    """
    import monta

    from hefesto_dualsense4unix.interface import mesa_viva

    return [(slug, nome, monta.cor_da_zona(slug))
            for _cod, (slug, nome) in sorted(mesa_viva.CORES.items())]


def test_o_mapa_tem_os_dois_casos(mapa_das_cores):
    """A régua abaixo tem o que morder — nos dois lados.

    Sem esta, o dia em que o mapa passar a ter hex para todo modelo (ou para
    nenhum) esta régua ficaria VERDE sem medir nada, e ninguém saberia. É o
    defeito de instrumento que esta casa mais paga: *régua que passa com a cura
    arrancada não mede nada* — e uma régua sem caso também não.
    """
    com_hex = [n for _s, n, t in mapa_das_cores if t.startswith("#")]
    sem_hex = [n for _s, n, t in mapa_das_cores if not t.startswith("#")]
    assert len(mapa_das_cores) == 28, (
        f"o mapa dela tem {len(mapa_das_cores)} modelos, e esta régua foi "
        f"escrita sobre 28. Se ela mapeou mais, o número aqui acompanha; se "
        f"caiu, alguém apagou trabalho dela.")
    assert com_hex, "nenhum modelo tem hex — não há o que pintar, e a régua cega"
    assert sem_hex, (
        "nenhum modelo responde a hachura do SEM-HEX. Ou o mapa ganhou "
        "hexadecimal para os oito acabamentos que não cabem num, ou a hachura "
        "mudou de forma — e esta régua parou de ter caso para morder.")


def test_so_o_hexadecimal_vira_borda(a03, mapa_das_cores):
    """O chip veste `--plastico` EXATAMENTE nos modelos que têm hex.

    Nos dois sentidos, e isso importa: um a menos e um controle que ela mapeou
    perde a identidade na tela; um a mais e a borda diz uma cor que ninguém
    mediu.
    """
    for slug, nome, tinta in mapa_das_cores:
        chip = a03.chip_do_controle(1, nome, "USB", a03._cor_do_plastico(slug))
        tem = "--plastico:" in chip
        assert tem == tinta.startswith("#"), (
            f"{nome} ({slug}): o mapa responde {tinta!r} e o chip "
            f"{'vestiu' if tem else 'não vestiu'} a borda de plástico. "
            f"{chip!r}")


def test_nenhum_chip_leva_url_para_dentro_do_style(a03, mapa_das_cores):
    """Nem hachura nem gradiente entram numa `border-color`.

    É a forma DIRETA do defeito medido no WebKit: `url(...)` não é cor, a
    `var()` fica inválida no tempo de valor computado, e a borda cai no
    `currentColor` em vez da queda declarada. A régua acima já cobre o caso pelo
    mapa de hoje; esta cobre a FORMA, e por isso alcança o gradiente de casca
    partida se um dia ele chegar à `casca-solida`.
    """
    for slug, nome, _tinta in mapa_das_cores:
        chip = a03.chip_do_controle(1, nome, "USB", a03._cor_do_plastico(slug))
        assert "url(" not in chip, (
            f"{nome} ({slug}) levou uma referência de SVG para dentro do "
            f"`style`: {chip!r}. Numa `border-color` isso não pinta hachura — "
            f"pinta a cor da letra.")


def test_a_dica_acompanha_a_cor(a03):
    """Três estados, três frases — e só um deles pode afirmar a cor.

    A dica dizia *"a borda é a cor do plástico"* nos TRÊS, e nos dois últimos
    era mentira: sem hex a borda é a neutra do tema, não o plástico de ninguém.
    """
    com_cor = a03.chip_do_controle(1, "White", "USB", "#e4e0d8")
    assert AFIRMA_A_COR in com_cor, (
        f"o chip com hex parou de dizer de onde vem a borda: {com_cor!r}")

    sem_hex = a03.chip_do_controle(2, "Chroma Teal", "BT",
                                   "url(#hachura-sem-hex)")
    assert AFIRMA_A_COR not in sem_hex, (
        f"o chip de um modelo sem hexadecimal continua afirmando que a borda é "
        f"a cor do plástico: {sem_hex!r}")
    assert "hexadecimal" in sem_hex, (
        f"a dica não diz POR QUE não há cor: {sem_hex!r}. Ausência sem razão é "
        f"a mesma coisa que campo quebrado, para quem lê.")
    assert "Chroma Teal" in sem_hex, (
        f"o NOME do modelo é identidade LIDA, e ele fica: {sem_hex!r}. Não ter "
        f"o hexadecimal não é não saber qual controle está na mesa.")

    nao_lida = a03.chip_do_controle(2, "", "BT", "")
    assert AFIRMA_A_COR not in nao_lida, (
        f"o chip sem leitura de cor continua afirmando a borda: {nao_lida!r}")
    assert "lida" in nao_lida, (
        f"a dica não separa 'ninguém leu' de 'o mapa não tem hex': "
        f"{nao_lida!r}. As duas ausências se consertam de formas diferentes.")
    assert "hexadecimal" not in nao_lida, (
        f"a dica de quem não teve a cor lida culpa o mapa: {nao_lida!r}")


def test_o_endereco_acompanha_a_cor(a03, mapa_das_cores):
    """Sem cor no `style`, sem `data-hef` no `<span>`.

    É o mesmo invariante que o gerador já cobra (`enderecados == com_cor`), e
    ele tem de continuar valendo para os oito modelos sem hex: um endereço a
    mais é um campo que a régua do mockup cobra sem que o produto possa selá-lo
    — o `<span>` é filho de um pai que se troca inteiro e nunca recebe a visita.
    """
    for slug, nome, _t in mapa_das_cores:
        chip = a03.chip_do_controle(1, nome, "USB", a03._cor_do_plastico(slug))
        assert (a03.HEF_DO_CHIP in chip) == ("--plastico:" in chip), (
            f"{nome} ({slug}): o endereço do `<span>` deixou de acompanhar a "
            f"cor. {chip!r}")


def test_cor_de_borda_recusa_o_que_o_mapa_nao_diz_em_hex(a03):
    """A peneira, nas TRÊS formas que `gerar_cores_do_dualsense._tinta` escreve.

    O gradiente de casca partida não chega à `casca-solida` hoje — ela existe
    justamente para dar UMA cor a quem precisa de uma. Ele está aqui porque a
    peneira é sobre a FORMA, e uma régua que só conhecesse a hachura passaria
    calada no dia em que a forma mudasse.
    """
    assert a03.cor_de_borda("#ae335a") == "#ae335a"
    assert a03.cor_de_borda("  #ae335a  ") == "#ae335a"
    assert a03.cor_de_borda("url(#hachura-sem-hex)") == ""
    assert a03.cor_de_borda("url(#casca-Z2)") == ""
    assert a03.cor_de_borda("") == ""
