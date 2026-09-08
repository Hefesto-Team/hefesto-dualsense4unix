#!/usr/bin/env python3
"""A coluna Atenção saiu da Jogar — e as onze fontes NÃO saíram com ela.

ORDEM DELA, 07/09/2026: *"em jogar remover essa seção do atenção, nenhum aviso
esse — deixar só o reconectar controles."*

**ESTA RÉGUA TEM DUAS METADES, e a segunda é a que importa.** Uma régua que só
cobrasse a ausência da faixa ficaria verde no dia em que alguém apagasse
`_avisos` inteiro — e aí a tela do produto deixaria de ter, em qualquer aba,
onde dizer que o serviço não responde, que o detector de janela está cego, que a
ponte com o jogo caiu ou que a cura do travamento do USB não está de pé.

**O NÚMERO QUE DECIDIU ISSO, medido antes de apagar:** das onze fontes de
`a01_jogar._avisos`, **só uma** tem segunda casa publicada — o exame da mesa, que
vem da aba Conexões e continua lá. As outras dez chegavam à tela SÓ pela coluna
que saiu. A proposta de destino está escrita no docstring de `_avisos`, e é a
aba **Sistema**: é o que a própria frase viva já manda, com estas palavras — *A
aba Sistema diz por quê*.

AS MORDIDAS, uma por régua, escritas no docstring de cada uma.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a01_jogar as aba

#: O daemon em **Navegação** — o mesmo payload das réguas irmãs desta aba.
VIVO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
    "paused": False,
    "controllers": [{"uniq": "aa:bb:cc:00:00:01", "connected": True,
                     "player_slot": 1}],
}

#: OS ENDEREÇOS QUE A COLUNA TINHA. A lista não se digita duas vezes: ela é o
#: que saiu de `DA_PAGINA`, e é o que as duas metades desta régua cobram.
DA_COLUNA = ("atencao-conta", "aviso-selo", "aviso-texto", "aviso-vivo")


def _ctx(state: dict[str, Any] | None = None) -> Contexto:
    return Contexto(state=dict(state if state is not None else VIVO),
                    mesa=[], conectados=[], estados={})


# ---------------------------------------------------------------------------
# 1. A METADE QUE ELA PEDIU — a faixa sai, o botão fica
# ---------------------------------------------------------------------------
def test_a_faixa_da_atencao_saiu_das_duas_paginas() -> None:
    """Nem na bancada nem no publicado — e o publicado é o que ela abre.

    Uma régua que olhasse só o `mockup/` daria verde com o produto dela ainda
    mostrando a faixa: publicar é ato à parte nesta casa, e é justamente o passo
    que se esquece.

    A MORDIDA: devolva o bloco `<div class="col-atencao">` ao `MIOLO` de
    `aba01.py`, rode o gerador e publique — as dez asserções reprovam.
    """
    for publicado in (False, True):
        corpo = onde.pagina("01-jogar.html", publicado=publicado).read_text(
            encoding="utf-8")
        onde_ = "publicado" if publicado else "bancada"
        # `class="…"` E NÃO A PALAVRA SOLTA: `.aviso-item` é regra do ESQUELETO
        # (`monta.py`), das dez abas — cobrar a palavra crua acusaria a folha
        # compartilhada, mandando consertar o que esta aba não pode.
        assert 'class="col-atencao"' not in corpo, f"{onde_}: a faixa voltou"
        assert 'class="aviso-item' not in corpo, f"{onde_}: as linhas voltaram"
        assert 'data-lista="avisos"' not in corpo, f"{onde_}: a lista voltou"
        for campo in DA_COLUNA:
            assert f'data-campo="{campo}"' not in corpo, (
                f"{onde_}: o endereço {campo!r} voltou à página")


def test_o_botao_que_ela_mandou_deixar_ficou() -> None:
    """*"deixar só o reconectar controles"* — e "só" não quer dizer "nenhum".

    Sem esta régua a de cima passa com a seção INTEIRA apagada, botão incluído:
    uma régua que só proíbe fica mais verde quanto mais se apaga. É o mesmo
    par de sinais que esta casa exige desde a fileira de modos.

    A MORDIDA: apague a `.faixa-final` do `MIOLO` — esta reprova e a de cima
    continua verde.
    """
    for publicado in (False, True):
        corpo = onde.pagina("01-jogar.html", publicado=publicado).read_text(
            encoding="utf-8")
        onde_ = "publicado" if publicado else "bancada"
        assert corpo.count('data-gesto="reconectar"') == 1, (
            f"{onde_}: o botão Reconectar Controles não está exatamente uma vez")
        assert "Reconectar Controles" in corpo, f"{onde_}: o rótulo dele sumiu"


def test_o_pacote_parou_de_emitir_os_quatro_enderecos() -> None:
    """Endereço emitido sem elemento onde pousar é ÓRFÃO, e tem quem o acuse.

    O `casamento.py` é a régua que o vê — foi assim que o `recado` da aba 04 foi
    pego em 02/09, depois de a régua do mockup passar por cima dele (ela varre
    os endereços do ARQUIVO, e um campo sem lugar não sai em arquivo nenhum).

    A MORDIDA: devolva `"atencao-conta"` a `DA_PAGINA` e emita-o de volta em
    `pacote()` — esta régua reprova nas duas metades.
    """
    fora = aba.pacote(_ctx())
    for campo in DA_COLUNA:
        assert campo not in fora, (
            f"`pacote()` voltou a emitir {campo!r}, e a página não tem onde "
            f"pousá-lo — é o órfão que o `casamento.py` acusa")
        assert campo not in aba.DA_PAGINA, (
            f"{campo!r} voltou a `DA_PAGINA`: a `cobertura` passaria a prometer "
            f"um endereço que a página não tem")


def test_o_travessao_solto_dos_externos_morreu() -> None:
    """O `—` que ela viu logo abaixo dos quatro cartões, na mesma ordem.

    ELE NÃO ERA A LINHA DE RESSALVA nem parte da faixa Atenção — medido no DOM
    vivo, com os quatro DualSense na mesa: era o campo `externos`, que devolvia
    `""`. `escrever()` troca vazio por travessão de propósito, a `.ext-vaga` é
    `display:contents`, e o traço virava um item anônimo da grade `.pecas` — um
    quinto assento, na linha de baixo, encostado à esquerda.

    A MORDIDA está na régua dona do campo
    (`test_a_interface_ve_os_controles_que_o_hefesto_so_ve`): devolva `""` em
    qualquer um dos DOIS `return` de `_html_dos_externos`. Aqui a cobrança é a
    da TELA — o que a página publicada mostra entre os cartões e o botão.
    """
    import monta

    assert aba.pacote(_ctx())["externos"] == monta.NADA_A_DIZER, (
        "sem externo o campo voltou a ser `''`, e o piloto escreve `—` nele")
    corpo = onde.pagina("01-jogar.html", publicado=True).read_text(encoding="utf-8")
    # ENTRE OS CARTÕES E O BOTÃO NÃO SOBROU ELEMENTO NENHUM: com a faixa fora, o
    # que houvesse aqui apareceria solto, sem cabeçalho que o explicasse.
    meio = corpo.split('data-lista="cartoes"', 1)[-1].split(
        '<div class="faixa-final', 1)[0]
    assert "ext-vaga" in meio, "o bloco dos externos saiu da grade dos assentos"
    assert 'data-campo="aviso' not in meio, "sobrou endereço de aviso no meio"


# ---------------------------------------------------------------------------
# 2. A METADE QUE NINGUÉM PEDIU — o canal não morre com a tela
# ---------------------------------------------------------------------------
def test_as_onze_fontes_continuam_de_pe_e_com_porta_propria() -> None:
    """`coluna_de_atencao` responde o que a coluna pintava — sem página nenhuma.

    É o handoff para quem der casa a estas linhas: a frente recebe a conta do
    produto, os selos, os textos e o acendedor, já ordenados pela gravidade e já
    cortados em `AVISOS_NA_COLUNA` com o `+N`.

    A MORDIDA: apague `coluna_de_atencao` (ou `_avisos`) e esta régua reprova —
    que é exatamente o que se quer, porque apagar qualquer um dos dois fecha o
    único caminho por que dez das onze fontes já souberam chegar a uma tela.
    """
    fora = aba.coluna_de_atencao(_ctx())
    assert set(fora) == set(DA_COLUNA), (
        f"a porta do canal mudou de vocabulário: {sorted(fora)}")
    assert len(fora["aviso-selo"]) == aba.AVISOS_VIVOS
    assert len(fora["aviso-texto"]) == aba.AVISOS_VIVOS
    assert len(fora["aviso-vivo"]) == aba.AVISOS_VIVOS


def test_o_servico_calado_ainda_encontra_o_canal() -> None:
    """A fonte que fala quando TODAS as outras calam continua respondendo.

    Ela é a única das onze que responde sobre a AUSÊNCIA de estado, e por isso é
    a que mede se o canal sobreviveu à saída da tela: com `state={}` nenhuma
    outra tem o que dizer.

    A MORDIDA: troque `_aviso_do_servico_calado` por `return None` — esta régua
    reprova, e a da faixa lá em cima continua verde. É por isso que as duas
    existem.
    """
    fora = aba.coluna_de_atencao(_ctx({}))
    assert aba.SELO_DO_SERVICO in fora["aviso-selo"], (
        "o canal perdeu a fonte do serviço calado quando a tela saiu")
    assert fora["atencao-conta"] != painel.texto_da_conta(0), (
        "a conta voltou a dizer 'nenhum aviso' sobre um estado que ninguém leu")


def test_a_unica_fonte_com_segunda_casa_e_o_exame() -> None:
    """O número que autorizou a remoção, trancado para não envelhecer calado.

    Das onze fontes, só o exame da mesa (`a08_conexoes._exame`) é publicado
    noutra aba — a Conexões, de onde ele vem. As outras dez perderam a tela e
    esperam a aba Sistema, e é ISSO que faz esta remoção uma dívida declarada e
    não um esquecimento.

    A MORDIDA: dê casa a uma das dez numa aba publicada e esta régua reprova —
    reprovar aqui é BOA notícia, e o conserto é apagar o nome dela da lista.
    """
    pacotes = INTERFACE / "pacotes"
    fontes = {
        "texto_do_cadeado_cego": "o detector de janela cego",
        "aviso_de_opt_out_antigo": "o opt-out antigo",
        "cura_do_travamento": "a cura do travamento do USB",
        "divergencia_de_mascara": "a divergência de máscara",
        "servico_calado": "o serviço calado",
        "AVISOS_DA_TELA": "as seis de `painel`",
    }
    for fonte, oque in fontes.items():
        casas = sorted(
            p.name for p in pacotes.glob("a??_*.py")
            if fonte in p.read_text(encoding="utf-8"))
        # A `a07_lancadores` CITA `AVISOS_DA_TELA` NUM COMENTÁRIO e não a
        # consome — por isso a régua olha quem CHAMA, e não quem escreve o nome.
        chamam = [c for c in casas
                  if f"{fonte}(" in (pacotes / c).read_text(encoding="utf-8")
                  or f"{fonte}:" in (pacotes / c).read_text(encoding="utf-8")]
        assert chamam in ([], ["a01_jogar.py"]), (
            f"{oque} ganhou casa em {chamam} — se for uma aba PUBLICADA, o "
            f"canal achou destino e o docstring de `_avisos` tem de dizê-lo")
