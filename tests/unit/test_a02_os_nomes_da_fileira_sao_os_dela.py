"""O-BOTAO-ENTREGA-O-QUE-PROMETE-01 — os nomes da fileira do som são DELA.

**A DECISÃO É DE PALAVRA, e decisão de palavra só morde quando a régua DIGITA
a decisão e LÊ a tela.** Ela derrubou o enunciado anterior em 20/09/2026, e o
que ela derrubou era conceito, não vocabulário:

    "não gosto do termo jogo pra se referir ao canal especifico pro sfx do
    controle, pq hdmi tecnicamente é jogo que manda pra lá também. além disso
    não curto sfx e hdmi queria algo melhor"
    <!-- noqa-acento: citação literal dela -->

Os dois primeiros nomes são os que ela escreveu, com estas letras:

    | 1 | Efeitos do Jogo                              |
    | 2 | Efeitos do Jogo e Áudio da TV no Controle    |

**POR QUE ESTE ARQUIVO EXISTE, com o `_conferir` do gerador ao lado.** Porque
o `_conferir` roda dentro do `__main__` de `interface/aba02.py`: ele só morde
**quem regera**. Um nome apagado direto no HTML da bancada, ou uma bancada que
envelhece enquanto o gerador anda, atravessa o portão inteiro sem uma palavra.
Medido em 20/09/2026, trocando `ROTULO_SO_OS_EFEITOS` por «Sons do jogo»:
**150 réguas desta área verdes**.

**AS DUAS METADES, e as duas mordem por razões diferentes:**

* o que está NO DESENHO que ela aprovou (`mockup/02-controles.html`) — pega
  quem edita o HTML à mão;
* o que o GERADOR emite (`aba02.ROTULO_*`) — pega quem troca a constante e
  ainda não rodou nada.

**OS LITERAIS SÃO DIGITADOS AQUI DE PROPÓSITO.** Lê-los de `ROTULO_*` faria
esta régua medir a própria saída — a trava que não trava nada (07/09/2026).

**O QUE ESTA RÉGUA NÃO MEDE:** a página PUBLICADA. A aprovação dela foi sobre
a foto da BANCADA, e publicar é ato de quem coordena, com a palavra dela
(`scripts/check_o_desenho_aprovado.py --publicar 02`). Exigir os nomes no
publicado seria esta régua mandando publicar.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: A PALAVRA DELA, digitada. `data-rota` → o rótulo que o botão tem de dizer.
DELA: dict[str, str] = {
    "jogo": "Efeitos do Jogo",
    "junto": "Efeitos do Jogo e Áudio da TV no Controle",
    "nada": "Tudo na TV e Nada no Controle",
}

#: **O TERCEIRO PASSOU A SER DELA — 21/09/2026.**
#:
#: Ele ficou dois dias com o rótulo de espera (`"Só no controle"`) porque o
#: nome que ela escreveu — «Tudo na TV e Nada no Controle» — descrevia o
#: OPOSTO do que o botão fazia: ele mandava o som do PC para o controle e
#: calava a televisão.
#:
#: **O ATO MUDOU PRIMEIRO, que é a ordem certa das duas coisas**, e a régua de
#: espera fez exatamente o que o comentário dela prometia: *"o dia em que o ATO
#: mudar, ela reprova e cobra a troca do rótulo junto"*. O botão hoje devolve a
#: saída padrão ao sistema **e** põe o firmware na rota 0, com o alto-falante
#: fora do caminho — os dois lados do próprio nome.
#:
#: A ordem dela que fechou isto, 21/09: *"os 3 botões de som tem que ter saídas
#: diferenciadas (…) controle e tv na tv faz ab na tv"*.
#: O RÓTULO DE ESPERA, guardado para ser RECUSADO. Ele viveu de 20 a 21/09 no
#: terceiro botão, enquanto o ato não batia com o nome dela. Apagá-lo daqui
#: deixaria a régua sem o que procurar — e é procurando por ele que ela impede
#: a volta do arranjo que mentia.
EM_ESPERA = "Só no controle"

#: O que ela NÃO quer ver na tela: os nomes internos das duas camadas. Eles
#: continuam existindo no código (`FONTE_MIX`/`FONTE_SFX`) — o que a decisão
#: proíbe é que cheguem ao BOTÃO.
NOMES_INTERNOS = ("sfx", "mix", "HDMI", "hdmi")

#: Um `<button …data-rota="X"…>TEXTO</button>`, com o texto do botão.
BOTAO = r'<button[^>]*data-rota="{rota}"[^>]*>([^<]*)</button>'


def _bancada() -> str:
    """O DESENHO que ela aprovou, pelo dono do caminho — nunca digitado.

    `interface.onde` é o único módulo que escreve `mockup/` e `paginas/`, e é
    regra desta casa que o que tem dono não se digita: oito arquivos já
    cravaram o caminho da árvore dela, e rodar uma cópia reescrevia o mockup.
    """
    from hefesto_dualsense4unix.interface import onde

    return (onde.BANCADA / "02-controles.html").read_text(encoding="utf-8")


def _rotulos(doc: str, rota: str) -> list[str]:
    return re.findall(BOTAO.format(rota=rota), doc)


# ===========================================================================
# 1. O DESENHO — o que está no arquivo que ela olhou
# ===========================================================================


@pytest.mark.parametrize("rota", sorted(DELA))
def test_o_desenho_diz_a_palavra_dela_em_todos_os_cartoes(rota: str) -> None:
    """Todo cartão da mesa, e não só o primeiro.

    MORDIDA: troque UM dos dois rótulos no `mockup/02-controles.html`. O
    `_conferir` do gerador continua verde — ele só roda quando alguém regera —
    e esta régua reprova nomeando o botão.
    """
    vistos = _rotulos(_bancada(), rota)

    assert vistos, (
        f"o botão `{rota}` sumiu do desenho: nenhum `data-rota={rota}` com "
        f"rótulo na bancada")
    assert set(vistos) == {DELA[rota]}, (
        f"o botão `{rota}` diz {sorted(set(vistos))} e a palavra dela de "
        f"20/09 é {DELA[rota]!r}")


def test_o_botao_de_espera_nao_voltou() -> None:
    """O rótulo de espera saiu com o ato que o justificava.

    Enquanto o terceiro botão CALAVA a televisão, o nome dela mentiria — e a
    régua travava o `"Só no controle"` até o ato mudar. O ato mudou em 21/09.

    MORDIDA: devolva `data-rota="pc"` e o rótulo de espera ao gerador. Esta
    régua reprova, e com ela o nome dela some da tela outra vez.
    """
    doc = _bancada()

    assert not _rotulos(doc, "pc"), (
        "o botão `pc` voltou à fileira — ele calava a televisão, e o nome que "
        "ela escreveu para essa posição diz o contrário")
    # **OS COMENTÁRIOS SAEM ANTES, e os DOIS tipos** — a página guarda lápide
    # em comentário HTML (o estado que ela viu em 03/09, citado quatro vezes) e
    # em comentário de CSS (as duas medições de largura). Comentário não chega
    # a tela nenhuma, e uma régua que varresse o documento cru reprovaria a
    # MEMÓRIA do defeito junto com ele — o avesso do que esta casa faz com
    # decisão medida.
    vivo = re.sub(r"<!--.*?-->|/\*.*?\*/", "", doc, flags=re.S)
    assert EM_ESPERA not in vivo, (
        f"o rótulo de espera {EM_ESPERA!r} voltou à TELA; o ato mudou e o "
        f"nome dela é {DELA['nada']!r}")


def test_a_fileira_tem_os_tres_botoes_no_mesmo_numero_de_cartoes() -> None:
    """Os três são UM estado: nenhum pode faltar num cartão que tem os outros.

    MORDIDA: apague o botão do meio de um dos cartões. A fileira daquele
    controle ficaria sem o modo que ela acabou de nomear, e o `aceso_da_fileira`
    emitiria `"junto"` para um botão que não existe — a fileira apaga inteira,
    sem uma palavra.
    """
    doc = _bancada()
    quantos = {rota: len(_rotulos(doc, rota)) for rota in DELA}

    assert len(set(quantos.values())) == 1, (
        f"a fileira do som não tem os três botões nos mesmos cartões: {quantos}")
    assert all(quantos.values()), f"a fileira do som sumiu do desenho: {quantos}"


@pytest.mark.parametrize("rota", ["jogo", "junto", "nada"])
def test_o_nome_interno_nao_chega_ao_botao(rota: str) -> None:
    """A tela nunca diz «sfx» nem «mix» — é metade da correção dela.

    *"além disso não curto sfx e hdmi queria algo melhor"*
    <!-- noqa-acento: citação literal dela -->

    MORDIDA: devolva um dos nomes internos ao rótulo. O `_conferir` do gerador
    o pegaria SE alguém regerasse; aqui ele reprova no ato.
    """
    for rotulo in _rotulos(_bancada(), rota):
        for interno in NOMES_INTERNOS:
            assert interno not in rotulo, (
                f"o botão `{rota}` diz {rotulo!r}, e {interno!r} é nome "
                f"interno — a tela fala a língua dela")


# ===========================================================================
# 2. O GERADOR — o que a próxima regeração vai escrever
# ===========================================================================


@pytest.mark.parametrize("rota", sorted(DELA))
def test_o_gerador_guarda_a_palavra_dela(rota: str) -> None:
    """A constante que o `abaNN.py` emite, contra a palavra dela DIGITADA.

    Sem esta metade, trocar `ROTULO_SO_OS_EFEITOS` passa verde até alguém
    regerar — e quem regera é uma pessoa, um dia qualquer, longe daqui.

    MORDIDA: troque `aba02.ROTULO_SO_OS_EFEITOS` por «Sons do jogo».
    """
    import aba02

    das_constantes = {
        "jogo": aba02.ROTULO_SO_OS_EFEITOS,
        "junto": aba02.ROTULO_EFEITOS_MAIS_A_TV,
        "nada": aba02.ROTULO_NADA_NO_CONTROLE,
    }
    assert das_constantes[rota] == DELA[rota], (
        f"o gerador emite {das_constantes[rota]!r} para o botão `{rota}` e a "
        f"palavra dela é {DELA[rota]!r}")


def test_o_gerador_e_o_desenho_nao_divergiram() -> None:
    """A bancada é o que o gerador escreveu — e as duas envelhecem juntas.

    É a lição de 31/08/2026, nas palavras dela: *"se alteramos no layout final
    a referência do mockup se perde."* <!-- noqa-acento: citação literal dela -->
    Uma bancada que não bate com o gerador é uma referência que já se perdeu, e
    ninguém vê até a próxima regeração desfazer o desenho aprovado.

    MORDIDA: troque a constante do gerador OU o rótulo no HTML. Esta régua
    reprova nos dois sentidos, que é o que as duas metades acima não fazem
    sozinhas.
    """
    import aba02

    doc = _bancada()
    for rota, constante in (("jogo", aba02.ROTULO_SO_OS_EFEITOS),
                            ("junto", aba02.ROTULO_EFEITOS_MAIS_A_TV),
                            ("nada", aba02.ROTULO_NADA_NO_CONTROLE)):
        assert set(_rotulos(doc, rota)) == {constante}, (
            f"o gerador diz {constante!r} para o botão `{rota}` e o desenho "
            f"aprovado diz {sorted(set(_rotulos(doc, rota)))}")
