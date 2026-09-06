#!/usr/bin/env python3
"""A palavra do transporte tem UM dono — e quem CONTA não a lê.

ONDA4-S10, 06/09/2026. A decisão é dela (D-05), verbatim: *"cabo / rádio, pela
função que já existe."* A função é a dona da frase longa da janela estável,
em ``app/actions/home_actions.py:1407``; esta régua mede que a interface nova a
CHAMA em vez de reescrever a tradução, e — o que é mais caro — que **nenhuma
conta desta casa depende da palavra**.

O DEFEITO QUE ELA EXISTE PARA IMPEDIR não é a palavra errada: é o NÚMERO errado
em silêncio. Até 06/09 duas somas comparavam o texto da tela:

    interface/mesa_viva.py          o cabeçalho: `X USB · Y BT`
    interface/pacotes/a07_…         o "?" da Lançadores: `(1 no cabo, 0 no rádio)`

Trocar a palavra sem tocar nelas faria a tela dizer ``● 2 controles: 0 USB ·
2 BT`` com os dois no cabo — o número errado, sem erro, sem log e sem uma linha
vermelha. É a família de defeito que esta casa persegue: *o mesmo fato com dois
donos, e o segundo envelhece calado.*

**A SEPARAÇÃO É A CURA**, e o dado para fazê-la já existia: a mesa publica
``transporte`` (a chave CRUA do daemon, ``usb``/``bt``) ao lado da palavra.
Quem conta lê ``transporte``; quem escreve na tela pergunta à dona.

O QUE A CONTAGEM DO CABEÇALHO **NÃO** FAZ: ela não muda de língua. ``X USB ·
Y BT`` fica, por decisão dela de 06/09 e por gramática — *"2 cabo · 0 rádio"*
não é português. É a única exceção declarada em
``docs/A-LINGUA-DESTA-CASA-o-glossario-que-a-tela-e-o-codigo-falam.md`` §1.

COMO CADA RÉGUA MORDE, e as mordidas foram feitas:

* **1 e 2** — troque a tabela da sigla (``pacotes.VIA_DO_TRANSPORTE``) e as duas
  contagens continuam certas. Antes da cura elas viravam ``0 USB · 2 BT`` e
  ``0 no cabo, 2 no rádio`` com os dois controles no cabo;
* **3** — troque a palavra NA DONA e as quatro superfícies da tela acompanham.
  Com qualquer cópia viva (o ``.upper()`` da 01, o ``"cabo" if …`` da 09, a
  sigla da mesa) a superfície fica com a palavra de ontem;
* **4** — o terceiro estado da dona chega à tela: transporte que o mapa não
  conhece volta CRU (para alguém o ver) e transporte AUSENTE vira *"não sei por
  onde"*. Nenhuma das cópias tinha os dois: o ``.upper()`` gritava o cru e
  devolvia vazio, e o ``if/else`` afirmava rádio sobre o que ninguém leu;
* **5** — o descarte do último degrau da 09 acompanha ``identidade_de`` em vez
  de um conjunto congelado no import.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.interface import mesa_viva
from hefesto_dualsense4unix.interface import pacotes as _pacotes
from hefesto_dualsense4unix.interface.pacotes import (
    Contexto,
    a01_jogar,
    a07_lancadores,
    a09_sistema,
)

#: DOIS ENDEREÇOS DE MENTIRA, com a máscara da casa (octetos 4 e 5 zerados).
#: Uma mesa de UM controle não distingue as duas palavras, e foi por isso que
#: este defeito sobreviveu a quatro leituras.
UNIQ_A = "aa:bb:cc:00:00:01"
UNIQ_B = "aa:bb:cc:00:00:02"

#: A palavra que a dona NÃO diz hoje. Ela entra no lugar de `cabo` para provar
#: que a tela SEGUE a dona em vez de repetir o que decorou.
#: OS GERADORES JÁ CURADOS — os que põem a escrita da bancada debaixo do
#: `if __name__ == "__main__":`. Lista explícita, e não um glob: a `aba06` e a
#: `aba09` ainda escrevem no nível do módulo, e um `aba*.py` as reprovaria sem
#: que ninguém tivesse decidido curá-las. Acrescentar um nome aqui é um ato que
#: se vê no diff — que é o oposto de um glob que passa a cobrar (ou a deixar de
#: cobrar) sozinho.
_GERADORES_JA_CURADOS = ("aba01.py", "aba02.py", "aba03.py", "aba04.py",
                         "aba05.py", "aba07.py", "aba08.py", "aba10.py")

SENTINELA = "por um fio"


def _estado(*transportes: str) -> dict[str, Any]:
    """A resposta do daemon com um controle por transporte pedido."""
    return {
        "controllers": [
            {"uniq": u, "connected": True, "player_slot": i, "transport": t,
             "serial": f"SN-DE-MENTIRA-{i}"}
            for i, (u, t) in enumerate(zip((UNIQ_A, UNIQ_B), transportes, strict=False),
                                       start=1)
        ],
    }


def _mesa(*transportes: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """`(estado, mesa)` — a mesa sai do DONO dela, nunca montada à mão aqui.

    Montá-la à mão escreveria uma segunda vez as regras de ordem, de cor e de
    transporte, e a cópia daqui envelheceria sozinha — que é exatamente o
    defeito que esta régua mede.
    """
    estado = _estado(*transportes)
    return estado, mesa_viva.mesa_do_estado(estado, {})


# ---------------------------------------------------------------------------
# 1 e 2 — QUEM CONTA LÊ O TRANSPORTE, NUNCA A PALAVRA
# ---------------------------------------------------------------------------
def test_a_contagem_do_cabecalho_nao_se_mexe_quando_a_palavra_muda(monkeypatch) -> None:
    """A mordida do P1: a palavra muda, a conta não.

    A troca é feita na tabela que alimenta a chave `via` — o texto que a tela
    escreve. Com a contagem lendo `via`, esta régua reprovava com
    `0 USB · 2 BT` e os dois controles no CABO.
    """
    _, mesa = _mesa("usb", "usb")
    assert mesa_viva.texto_da_contagem(mesa) == ("● 2 controles: ", "2 USB · 0 BT")

    # O PONTO DE INJEÇÃO MUDOU NA COSTURA DA ONDA B (06/09/2026), e a PERGUNTA
    # não. A `via` deixou de vir da tabela `VIA_DO_TRANSPORTE` e passou a vir da
    # dona da frase — `home_actions.palavra_do_transporte` —, que é o que a
    # própria ONDA4-S10 desenhou e não pôde executar (os cinco pontos que
    # COMPARAVAM a chave não eram da posse dela). Com a injeção no lugar velho
    # esta régua parava de morder, e foi ELA quem acusou: a asserção do meio,
    # *"a troca não chegou à mesa"*, reprovou primeiro.
    monkeypatch.setattr(
        mesa_viva, "_via_do_transporte", lambda _t: SENTINELA)
    _, mesa_depois = _mesa("usb", "usb")
    assert [c["via"] for c in mesa_depois] == [SENTINELA, SENTINELA], (
        "a troca não chegou à mesa — a mordida não estaria mordendo nada")
    assert mesa_viva.texto_da_contagem(mesa_depois) == ("● 2 controles: ", "2 USB · 0 BT"), (
        "a contagem do cabeçalho seguiu a PALAVRA da tela. Ela tem de somar "
        "`transporte`, a chave crua do daemon: a palavra é decisão dela e pode "
        "mudar de novo — a conta, não")


def test_a_contagem_do_cabecalho_separa_os_dois_transportes() -> None:
    """A outra metade: apagar a conta também passaria no teste de cima."""
    _, mesa = _mesa("usb", "bt")
    assert mesa_viva.texto_da_contagem(mesa)[1] == "1 USB · 1 BT"
    _, so_radio = _mesa("bt", "bt")
    assert mesa_viva.texto_da_contagem(so_radio)[1] == "0 USB · 2 BT"


def test_a_mesa_do_desenho_tambem_publica_a_chave_crua() -> None:
    """A conta lê `transporte`, e a mesa do DESENHO tem de publicá-la também.

    **O DEFEITO QUE ESTA RÉGUA NASCEU MEDINDO, e ele foi vivo — 06/09/2026.**
    As duas réguas acima mediam a mesa VIVA (`mesa_viva.mesa_do_estado`) e
    passavam verdes enquanto os dez geradores escreviam `0 USB · 0 BT` no
    cabeçalho de TODA página regerada: a conta somava `transporte`, e
    `monta.MESA` — a mesa do DESENHO, que é outra tabela — só tinha `via`.

    Não apareceu na hora porque ninguém rodou um gerador entre a costura e o
    fecho. Apareceu quando o `pytest` **coletou** um teste que importava
    `aba05` e o arquivo dela mudou no disco.

    A MORDIDA: tire `"transporte"` de qualquer linha de `monta.MESA` e esta
    régua reprova nomeando a linha. Antes da cura ela reprovava nas quatro.
    """
    import monta

    sem = [c["pref"] for c in monta.MESA if not str(c.get("transporte") or "")]
    assert not sem, (
        f"a mesa do DESENHO não publica `transporte` em {sem} — o cabeçalho "
        "de toda página regerada sairia com a contagem zerada, porque quem "
        "conta lê a chave crua e não a palavra")

    usb = sum(1 for c in monta.CONECTADOS
              if str(c.get("transporte")).lower() == "usb")
    bt = sum(1 for c in monta.CONECTADOS
             if str(c.get("transporte")).lower() == "bt")
    assert (usb, bt) == (1, 1), (
        f"a mesa do desenho conta {usb} USB e {bt} BT; o desenho aprovado diz "
        "`2 controles: 1 USB · 1 BT` e é ele que manda")

    # E AS DUAS CHAVES TÊM DE CONCORDAR: a `via` desta tabela ainda é a SIGLA
    # (seis geradores a escrevem direto na tela), e uma tabela que diga `USB`
    # numa chave e `bt` na outra publicaria dois fatos sobre o mesmo controle.
    for c in monta.MESA:
        assert str(c["via"]).lower() == str(c["transporte"]).lower(), (
            f'{c["pref"]}: `via`={c["via"]!r} e `transporte`={c["transporte"]!r} '
            "discordam — a mesa do desenho estaria dizendo duas coisas")


def test_o_gerador_nao_escreve_a_bancada_como_efeito_de_import() -> None:
    """Importar um gerador NÃO pode reescrever o desenho dela no disco.

    **MEDIDO EM 06/09/2026:** bastava o `pytest` COLETAR
    `test_a_vibracao_diz_qual_degrau_esta_aceso.py`, que importava `aba05` no
    topo, para `mockup/05-vibracao.html` mudar no disco — com a contagem viva
    de controles dentro. A ironia estava escrita: aquele mesmo teste avisa, na
    docstring, que *"importar `aba05` REESCREVE a bancada dela como efeito de
    um `import`, e uma régua não mexe no que mede"*.

    A MORDIDA: tire o `if __name__ == "__main__":` de qualquer arquivo de
    `CURADOS` e esta régua reprova nomeando o arquivo.
    """
    import pathlib as _pl
    import re as _re

    raiz = _pl.Path(__file__).resolve().parents[2]
    faltam = []
    for nome in _GERADORES_JA_CURADOS:
        arq = raiz / "src/hefesto_dualsense4unix/interface" / nome
        texto = arq.read_text(encoding="utf-8")
        if not _re.search(r'^if __name__ == "__main__":$', texto, _re.M):
            faltam.append(arq.name)
    assert not faltam, (
        f"{faltam} escrevem a bancada dela no nível do módulo: qualquer "
        "`import` — inclusive a COLETA do pytest — reescreve o desenho "
        "aprovado no disco, com o estado vivo da mesa dentro")


def test_o_quantos_da_lancadores_nao_se_mexe_quando_a_palavra_muda(monkeypatch) -> None:
    """A mesma mordida na segunda conta — a frase do "?" da aba Lançadores."""
    _, mesa = _mesa("usb", "bt")
    antes = a07_lancadores.quantos_da_mesa(mesa)
    assert "1 no cabo" in antes and "1 no rádio" in antes, antes

    monkeypatch.setitem(_pacotes.VIA_DO_TRANSPORTE, "usb", SENTINELA)
    _, depois = _mesa("usb", "bt")
    frase = a07_lancadores.quantos_da_mesa(depois)
    assert "1 no cabo" in frase and "1 no rádio" in frase, (
        f"o '?' da Lançadores contou pela palavra da tela: {frase!r}. O "
        "cabeçalho, no mesmo quadro, continuaria dizendo '1 USB · 1 BT'")


# ---------------------------------------------------------------------------
# 3 — A PALAVRA DA TELA SAI DA DONA, nas quatro superfícies
# ---------------------------------------------------------------------------
def _superficies(estado: dict[str, Any], mesa: list[dict[str, Any]]) -> dict[str, str]:
    """As quatro superfícies em que a palavra mora, numa leitura só."""
    ctx = Contexto(state=estado, mesa=mesa, conectados=estado["controllers"], estados={})
    cartoes = a01_jogar.pacote(ctx)["cartoes"]
    return {
        "cartão da Jogar": str(cartoes[UNIQ_A]["identidade"]),
        "chip da Lançadores": a07_lancadores._chip(mesa[0]),
        "chip da Sistema": a09_sistema._um_chip(mesa[0]),
        "linha da Sistema": a09_sistema._linha_de_identidade(estado["controllers"][0], mesa),
    }


def test_as_quatro_superficies_seguem_a_dona(monkeypatch) -> None:
    """Troque a palavra NA DONA e as quatro acompanham — nenhuma tem cópia.

    A 09 é o caso que fecha o argumento: a foto da mesa dela de 03/09/2026 pegou
    a fita e o painel logo abaixo, na MESMA tela, em duas línguas. As duas estão
    aqui, e as duas têm de trocar juntas.
    """
    monkeypatch.setitem(home_actions._PALAVRA_DO_TRANSPORTE, "usb", SENTINELA)
    estado, mesa = _mesa("usb", "bt")
    for onde, texto in _superficies(estado, mesa).items():
        assert SENTINELA in texto, (
            f"{onde} não seguiu a dona da palavra: {texto!r}. Alguém reescreveu "
            "a tradução aqui — a palavra vem de `home_actions` e de mais lugar "
            "nenhum")


def test_as_quatro_superficies_dizem_a_palavra_dela_hoje() -> None:
    """E o que elas dizem HOJE é a decisão dela: `cabo` e `rádio`.

    Sem este caso, uma superfície que escrevesse a sentinela em qualquer
    situação passaria no teste de cima.
    """
    estado, mesa = _mesa("usb", "bt")
    for onde, texto in _superficies(estado, mesa).items():
        assert "cabo" in texto, f"{onde} não diz a palavra dela: {texto!r}"
        assert "USB" not in texto, (
            f"{onde} ainda escreve a sigla de máquina: {texto!r}. `USB` é o nome "
            "do barramento, não palavra de quem quer jogar")


def test_a_contagem_e_a_unica_excecao_e_ela_continua_em_sigla() -> None:
    """O cabeçalho fica em `USB`/`BT` — decisão dela, 06/09/2026.

    A razão é gramática: *"2 cabo · 0 rádio"* não é português. Esta régua existe
    para que a próxima leva não "termine o trabalho" traduzindo a contagem.
    """
    _, mesa = _mesa("usb", "bt")
    assert mesa_viva.texto_da_contagem(mesa)[1] == "1 USB · 1 BT"


# ---------------------------------------------------------------------------
# 4 — O TERCEIRO ESTADO DA DONA CHEGA À TELA
# ---------------------------------------------------------------------------
def test_o_transporte_ausente_diz_que_nao_se_sabe() -> None:
    """Um `·` seguido de nada não é resposta, e `rádio` sobre o vazio é mentira.

    As duas cópias que morreram erravam aqui de formas opostas: o `.upper()` da
    aba 01 devolvia `""`, e o `if/else` da aba 09 afirmava **rádio** sobre um
    campo que o daemon nunca publicou.
    """
    estado = {"controllers": [{"uniq": UNIQ_A, "connected": True, "player_slot": 1}]}
    mesa = mesa_viva.mesa_do_estado(estado, {})
    frase = home_actions.PALAVRA_DE_TRANSPORTE_DESCONHECIDO

    ctx = Contexto(state=estado, mesa=mesa, conectados=estado["controllers"], estados={})
    assert frase in str(a01_jogar.pacote(ctx)["cartoes"][UNIQ_A]["identidade"])
    assert frase in a09_sistema._linha_de_identidade(estado["controllers"][0], mesa)


def test_um_transporte_que_o_mapa_nao_conhece_aparece_cru() -> None:
    """Transporte novo TEM de aparecer, e não sumir atrás de uma frase genérica.

    É a razão escrita na dona, e é o que separa "não sei" de "não conheço":
    um daemon mais recente com um transporte novo precisa ser VISTO por alguém.
    """
    estado, mesa = _mesa("thunderbolt")
    ctx = Contexto(state=estado, mesa=mesa, conectados=estado["controllers"], estados={})
    cartao = str(a01_jogar.pacote(ctx)["cartoes"][UNIQ_A]["identidade"])
    assert "thunderbolt" in cartao, cartao
    assert home_actions.PALAVRA_DE_TRANSPORTE_DESCONHECIDO not in cartao, (
        "um transporte que o mapa não conhece virou 'não sei por onde'. Ele "
        "existe, o daemon o publicou, e esconder isso é a tela encolhendo os "
        "ombros sobre um fato que ela leu")


# ---------------------------------------------------------------------------
# 5 — O DESCARTE DO ÚLTIMO DEGRAU PERGUNTA AO DONO
# ---------------------------------------------------------------------------
def test_o_descarte_da_09_segue_o_ultimo_degrau_de_identidade(monkeypatch) -> None:
    """`P2 · BT · rádio` afirma o mesmo fato duas vezes — e o descarte tem de
    acompanhar quem produz o degrau, não uma lista congelada no import.

    A MORDIDA: troque a tabela da sigla. Com o conjunto congelado
    (`frozenset({TRAVESSAO, *VIA_DO_TRANSPORTE.values()})`, montado no import) o
    nome novo NÃO está na lista, escapa do descarte e a linha da aba Sistema
    volta a dizer o transporte duas vezes.
    """
    sem_nome = {"uniq": UNIQ_B, "transport": "bt"}
    assert a09_sistema._nome_do_plastico(sem_nome, []) == ""

    monkeypatch.setitem(_pacotes.VIA_DO_TRANSPORTE, "bt", SENTINELA)
    assert a09_sistema._nome_do_plastico(sem_nome, []) == "", (
        "o último degrau de `identidade_de` mudou de língua e o descarte ficou "
        "com a palavra de ontem — a linha da Sistema volta a repetir o "
        "transporte")


def test_o_descarte_nao_come_um_nome_de_verdade() -> None:
    """A outra metade: descartar tudo passaria no teste de cima."""
    com_nome = {"uniq": UNIQ_A, "transport": "usb", "modelo": "White"}
    assert a09_sistema._nome_do_plastico(com_nome, []) == "White"


# ---------------------------------------------------------------------------
# 6 — NENHUM ARQUIVO DESTA POSSE REDIGITA A TRADUÇÃO
# ---------------------------------------------------------------------------
#: A tabela da SIGLA continua viva, e é dívida DECLARADA: a chave `via` da mesa
#: é COMPARADA em `interface/monta.py:877` e em quatro linhas de
#: `interface/pacotes/a08_conexoes.py`, nenhum dos dois da posse desta sprint.
#: Trocar a palavra dela sem tocar nesses cinco pontos faria a aba Conexões
#: mostrar ZERO controles no rádio com os dois no rádio.
DONOS_DA_PALAVRA = (
    "src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py",
    "src/hefesto_dualsense4unix/interface/pacotes/a07_lancadores.py",
    "src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py",
)


@pytest.mark.parametrize("caminho", DONOS_DA_PALAVRA)
def test_nenhuma_aba_desta_posse_escreve_a_traducao(caminho: str) -> None:
    """A palavra não se digita em CÓDIGO — ela se pergunta.

    A varredura é por LINHA DE CÓDIGO e pula comentário e prosa: uma docstring
    que explique a cura (e há três) não pode reprovar a cura que ela explica —
    foi assim que um aviso virou o defeito que descrevia, em 05/09/2026.
    """
    fonte = (RAIZ / caminho).read_text(encoding="utf-8")
    dentro_de_prosa = False
    acusados: list[str] = []
    for numero, linha in enumerate(fonte.splitlines(), start=1):
        nua = linha.strip()
        if nua.count('"""') == 1:
            dentro_de_prosa = not dentro_de_prosa
            continue
        if dentro_de_prosa or nua.startswith("#") or not nua:
            continue
        codigo = nua.split("#", 1)[0]
        # `set` E NÃO os valores crus: a tabela da dona mapeia SEIS chaves em
        # duas palavras, e sem isto a mesma linha sairia acusada cinco vezes.
        if any(f'"{p}"' in codigo or f"'{p}'" in codigo
               for p in set(home_actions._PALAVRA_DO_TRANSPORTE.values())):
            acusados.append(f"{caminho}:{numero}: {nua}")
    assert not acusados, (
        "a tradução do transporte foi redigitada em código:\n  "
        + "\n  ".join(acusados)
        + "\nA palavra vem da dona (`app/actions/home_actions.py:1407`) e de "
          "mais lugar nenhum — foi a QUARTA cópia dela que esta sprint matou"
    )
