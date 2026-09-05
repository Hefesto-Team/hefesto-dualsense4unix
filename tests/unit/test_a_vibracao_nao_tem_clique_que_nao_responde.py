#!/usr/bin/env python3
"""A ABA VIBRAÇÃO: todo `data-papel` tem quem atenda — e o endereço não se perde.

MEDIDO EM 03/09/2026, clicando a aba PUBLICADA no WebKit, com o daemon dela
vivo e um DualSense White no cabo. O ouvinte de clique do piloto lê **qualquer**
``data-papel`` como o NOME DE UM GESTO::

    gesto: d.gesto || d.hefGesto || d.papel || doRodape || 'clique'
    #  hefesto_vivo.py, `manda_do_alvo`

Esta aba tinha QUATRO nomes assim que nenhum pacote registra. Cliquei os quatro
pela ponte, um por vez, e li o DOM depois de cada um::

    [gesto sem dono] 05-vibracao.html · desenho    · '/* Fonte: docs/data/…'
    [gesto sem dono] 05-vibracao.html · identidade · 'P1 · White · USB'
    [gesto sem dono] 05-vibracao.html · motor      · 'Motor de vibração esquerdo…—/255'
    [gesto sem dono] 05-vibracao.html · lado       · 'Motor de vibração esquerdo'

    desfechos:  05-vibracao.html:desenho    -> ('sem dono', '')
                05-vibracao.html:identidade -> ('sem dono', '')
                05-vibracao.html:motor      -> ('sem dono', '')
                05-vibracao.html:lado       -> ('sem dono', '')
    tela depois de cada clique:  recados: []

A frase vai para o **terminal de quem lançou a janela**, e quem clica na janela
não lê esse terminal. Na tela: nada. As áreas, medidas no DOM vivo com
``getBoundingClientRect``:

    ===========  =========  =============
    `data-papel` elementos  área clicável
    ===========  =========  =============
    `desenho`            4     98.332 px²
    `motor`              4     28.548 px²
    `identidade`         2      6.740 px²
    `lado`               4      5.184 px²
    ===========  =========  =============

138.804 px² — perto de um quarto do miolo desta aba, e o maior deles é o próprio
DESENHO DO CONTROLE. É a forma que o `_gesto` do piloto nomeia por escrito:
*"um botão que responde calado quando não há quem atenda"*.

**A CURA É O ATRIBUTO.** Os três endereços de pintura são ``data-campo``,
``data-papel`` e ``data-hef`` (``regua_do_mockup.ATRIBUTOS_DE_CAMPO``), e o
ouvinte de clique só lê o do meio. Trocar ``data-papel`` por ``data-hef`` deixa
o endereço EXATAMENTE onde estava — o pintor continua achando por
``[data-hef=X]``, a régua do mockup continua contando o campo — e tira o clique
fantasma. **Nem um pixel muda**: a regeração da bancada dá 10 linhas de diff, e
as dez trocam só o nome do atributo.

A MORDIDA — as duas, e cada uma pega uma metade:

* devolva ``data-papel`` a qualquer um dos quatro em ``aba05.py`` (ou tire o
  nome de :data:`aba05.PAPEIS_QUE_SAO_GESTO`), rode o gerador, e
  ``test_nenhum_papel_desta_aba_fica_sem_gesto`` reprova — junto com a régua 11
  do próprio ``aba05._conferir``, que faz a geração falhar antes;
* apague o ``data-hef`` em vez de trocá-lo, e
  ``test_os_quatro_enderecos_continuam_existindo`` reprova: uma cura que
  resolvesse o clique morto SUMINDO com o endereço deixaria a régua do mockup
  cega para quatro campos, que é comprar silêncio com cegueira.

ONDE ELA MEDE: na **BANCADA**, que é onde o gerador escreve. A publicação é ato
DELA (``--publicar 05``), e até lá a página que o produto renderiza continua com
os quatro cliques mortos — está em ``mockup/DIVERGENCIAS.md``.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.interface import regua_do_mockup as _regua

PAGINA = "05-vibracao.html"

#: OS NOMES QUE ERAM CLIQUE MORTO, e continuam sendo ENDEREÇO. A lista é o que
#: impede a cura de virar uma remoção: se um deles sumir do desenho, a régua do
#: mockup perde um campo e ninguém percebe.
#:
#: **ERAM QUATRO E HOJE SÃO TRÊS — 04/09/2026, e `motor` saiu pela porta certa:
#: ele GANHOU GESTO.** A decisão dela sobre a barra por motor (*"os slcers do
#: botão esquerdo e direito se multiplicam"*) fez a linha virar AJUSTE, e o
#: `data-papel="motor"` voltou ao desenho — desta vez no `<input type=range>`,
#: com `a05_vibracao.motor` para atender. Não é a régua perdendo um campo: os
#: dois endereços que a linha usa agora (`barra-e`/`barra-d`, mais o
#: `motor-<lado>-pedido` do `title`) são contados no lugar dele, e
#: `test_nenhum_papel_desta_aba_fica_sem_gesto` continua exigindo que todo
#: `data-papel` tenha dono.
ENDERECOS_QUE_SO_PINTAM = ("desenho", "identidade", "lado")


@pytest.fixture(scope="module")
def bancada() -> str:
    import onde

    arq = onde.pagina(PAGINA)
    assert arq.exists(), f"a bancada não tem {PAGINA} — rode `python3 aba05.py`"
    return arq.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def gerador(tmp_path_factory: pytest.TempPathFactory):
    """O módulo `aba05`, importado com a escrita DESVIADA para um temporário.

    Importar o gerador RODA o gerador — o `monta(...)` do fim do arquivo é
    código de módulo. Sem o desvio, um `pytest` desta régua reescreveria a
    bancada DELA, que é a pasta que ela olha. `HEFESTO_BANCADA` existe
    exatamente para isso (`interface/onde._DESVIO`), e é o que
    `test_os_dez_geradores_rodam` já usa.
    """
    import importlib
    import os

    destino = tmp_path_factory.mktemp("bancada-da-regua")
    antes = os.environ.get("HEFESTO_BANCADA")
    os.environ["HEFESTO_BANCADA"] = str(destino)
    try:
        mod = importlib.import_module("aba05")
        yield mod
    finally:
        if antes is None:
            os.environ.pop("HEFESTO_BANCADA", None)
        else:
            os.environ["HEFESTO_BANCADA"] = antes


def _gestos_registrados() -> set[str]:
    """Os gestos que o pacote desta aba REGISTRA — lidos, nunca digitados.

    Digitar a lista aqui seria a segunda cópia do registro, e o dia em que um
    gesto nascesse no pacote esta régua o acusaria de órfão.
    """
    import pacotes

    return {nome for pagina, nome in pacotes.GESTOS if pagina in (PAGINA, "*")}


# --------------------------------------------------------------------------
# 1. NENHUM CLIQUE SEM DONO
# --------------------------------------------------------------------------

def test_nenhum_papel_desta_aba_fica_sem_gesto(bancada: str) -> None:
    """Todo `data-papel` da bancada é um gesto que o pacote atende.

    É a régua que faltava ao lado da que já existe: ``aba05._conferir`` §6 pega
    o nome que é VALOR e CLIQUE ao mesmo tempo; esta pega o nome que é CLIQUE e
    NINGUÉM ATENDE.
    """
    papeis = {g.nome for g in _regua._papeis_cravados(bancada)}
    assert papeis, ("a bancada não tem `data-papel` nenhum — ou o desenho mudou "
                    "de vocabulário, ou esta régua virou vácuo")
    orfaos = papeis - _gestos_registrados()
    assert not orfaos, (
        f"`data-papel` sem gesto que atenda: {sorted(orfaos)}. O ouvinte do "
        f"piloto lê todo `data-papel` como nome de gesto, e um nome que nenhum "
        f"pacote registra vira `[gesto sem dono]` no terminal e SILÊNCIO na "
        f"tela. Endereço que é só pintura sai em `data-hef`")


def test_o_gerador_reprova_um_papel_orfao(gerador, bancada: str) -> None:
    """A régua 11 do `aba05._conferir` faz a GERAÇÃO falhar, não só o teste.

    Sem isto a cura dependeria de alguém lembrar de rodar a suíte; quem edita o
    gerador roda o gerador, e é ali que o barulho tem de sair.

    A MORDIDA É FEITA AQUI, no documento que o gerador acabou de escrever: um
    ``data-papel="lado"`` de volta, e ``_conferir`` tem de levantar. Se ele
    passar, a régua 11 é enfeite.
    """
    envenenado = bancada.replace('data-hef="lado"', 'data-papel="lado"', 1)
    assert envenenado != bancada, 'o desenho não tem mais `data-hef="lado"`'
    with pytest.raises(SystemExit):
        gerador._conferir(envenenado)
    # E o documento LIMPO passa — senão a reprovação acima seria por outro
    # motivo qualquer, e a régua estaria acusando o ar.
    gerador._conferir(bancada)


# --------------------------------------------------------------------------
# 2. E O ENDEREÇO NÃO SE PERDEU
# --------------------------------------------------------------------------

def test_os_quatro_enderecos_continuam_existindo(bancada: str) -> None:
    """A cura tirou o CLIQUE, não o endereço.

    ``regua_do_mockup.ATRIBUTOS_DE_CAMPO`` é ``("data-campo", "data-papel",
    "data-hef")`` — os três valem para a pintura e para a régua do mockup. Se um
    dos quatro sumisse, a régua passaria a contar menos campos nesta aba e o
    número melhoraria por CEGUEIRA.
    """
    campos = {c.chave for c in _regua._campos_cravados(bancada)}
    for nome in ENDERECOS_QUE_SO_PINTAM:
        assert nome in campos, (
            f"o endereço `{nome}` sumiu do desenho — a régua do mockup deixou "
            f"de contá-lo, e um campo a menos não é um defeito a menos")


def test_o_atributo_que_sobrou_e_o_que_nao_dispara_clique(bancada: str) -> None:
    """Os quatro saem em `data-hef`, que é o único dos três fora do ouvinte.

    O seseletor do ouvinte (`manda_do_alvo`) nomeia `data-gesto`, `data-modo`,
    `data-hef-gesto`, `data-papel`, `data-forca`, `data-player`, `data-sensor`,
    `data-rota`, `data-mudo`, `data-mic-modo` e `data-v` — e `data-hef` não está
    lá. Trocar por `data-campo` também tiraria o clique, mas `data-campo` é o
    endereço do VALOR: pôr `desenho` nele faria a pintura procurar um valor
    chamado `desenho` e escrever texto DENTRO do SVG no dia em que alguém o
    emitisse. É o defeito da régua 6, um andar acima.
    """
    for nome in ENDERECOS_QUE_SO_PINTAM:
        assert f'data-hef="{nome}"' in bancada, (
            f"`{nome}` não sai em `data-hef` — ver a razão no cabeçalho")
        assert f'data-papel="{nome}"' not in bancada, (
            f"`{nome}` voltou a ser `data-papel` e volta a ser clique sem dono")


def test_os_dois_botoes_de_verdade_continuam_clicaveis(bancada: str) -> None:
    """"Testar", "Parar" e os quatro degraus NÃO podem perder o `data-papel`.

    Uma cura que calasse a aba inteira seria mais fácil e mais errada: estes
    seis TÊM gesto registrado, com desfecho relatado pelo piloto. A régua os
    fixa para que a próxima varredura de `data-papel` não os leve junto.
    """
    for nome in ("testar", "parar", "forca"):
        assert f'data-papel="{nome}"' in bancada, (
            f"`{nome}` perdeu o `data-papel` — ele TEM gesto, e sem o atributo o "
            f"clique dela para de chegar ao daemon")
        assert nome in _gestos_registrados(), (
            f"`{nome}` está no desenho como clique e o pacote não o registra — "
            f"esta régua acabou de virar do avesso")
