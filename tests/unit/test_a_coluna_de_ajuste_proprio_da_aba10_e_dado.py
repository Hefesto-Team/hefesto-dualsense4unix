"""A coluna "Ajuste próprio" da aba Perfis mostra DADO, e não o desenho.

Ela é a linha de cinco glifos que responde *"o que este perfil guarda só deste
controle?"*. Até 03/09/2026 ela era desenho puro: as dezesseis células nasciam
acesas ou apagadas pelo `GUARDA` fixo do gerador e nada as tocava depois — a
régua do mockup as acusava uma a uma, e eram **dezesseis dos dezessete** campos
que aquela aba ainda devia.

O QUE ESTAVA QUEBRADO, e eram três coisas empilhadas
-----------------------------------------------------
1. **O pacote emitia os NOMES das seções, não os estados.** A linha era
   ``[s for g in guarda for s in (g.get("secoes") or [])]``, e ``secoes`` é um
   **dicionário** — iterá-lo devolve as chaves. Com um perfil que guarda só o
   ``rumble`` do P1, o dicionário é
   ``{'leds': False, 'triggers': False, 'rumble': True, 'speaker': False}`` e a
   emissão mandava as quatro palavras, todas verdadeiras. Pintada, a coluna
   acenderia TUDO para todo mundo — a mentira que a legenda da própria aba
   avisa ser pior que a tela apagada.
2. **A página não sabia receber a pintura.** Sem ``data-hef-alvo``, o pintor cai
   no ramo do texto e ``textContent`` apaga os filhos-elemento: o glifo SVG
   morreria dentro do ``<span>``. Era o que ``a10_perfis.NAO_PINTAVEIS``
   segurava, e com razão.
3. **A régua irmã tinha envelhecido.** ``ALVOS_SEGUROS``, em
   ``test_a_guarda_do_perfil_nao_apaga_a_tabela``, nomeava quatro alvos quando o
   piloto já tinha oito — e por isso reprovava quem PUSESSE o alvo certo.

A CURA, e as três metades chegam juntas: o desenho ganhou
``data-hef-alvo="classe"`` (um ENDEREÇO, que
``check_o_desenho_aprovado.INVISIVEIS`` deixa chegar ao produto sem passar por
ela), o pacote passou a ler o dicionário POR NOME, e ``guarda.secao`` saiu de
``NAO_PINTAVEIS``.

AS DUAS DECISÕES DELA QUE ESTE ARQUIVO SEGURA — 03/09/2026
-----------------------------------------------------------
- **nº4, as oito dicas das células SAEM.** *"Meu Deus melhor nenhuma assim.
  Auto falante é auto falante, gatilho é gatilho."* Eram quatro pares (um texto
  por estado) que repetiam a dica do cabeçalho e ainda re-explicavam o que cada
  peça é. A régua olha o ELEMENTO, não a frase: proibir os oito textos deixaria
  o nono entrar livre.
- **nº20, o microfone é o QUINTO ajuste por controle.** A tela ganhou a coluna
  no mesmo dia em que ``ControllerOverrides`` ganhou o campo — e por um dia os
  dois não se falaram.

O DIA EM QUE ESTE ARQUIVO NÃO BASTOU — 03/09/2026
--------------------------------------------------
Este docstring dizia *"a tela mostra cinco antes de o esquema guardar cinco, e
isso é declaração, não invenção"*. Não era mais verdade quando foi escrito:
``3f757b77`` (02:50) pôs o ``mic`` em ``ControllerOverrides`` e ``7e64c2e3``
(02:56), noutra worktree, desenhou a coluna afirmando no commit que o campo
*"ainda não existe"*. O merge levou os dois e ninguém releu a isenção.

O resultado ficou vivo por um dia: o daemon aplicava o mudo só daquele controle
(``manager.apply_controller_mics``), e a coluna que existe para dizer *"este
controle tem ajuste próprio"* ficava **apagada à força** — ``pintaGuarda`` faz
``!!linha.secoes['mic']`` e a chave não saía de ``SECOES_POR_CONTROLE``, que era
digitada à mão.

**As duas réguas que faltavam, e elas fecham a direção que ninguém guardava:**
``test_o_produto_mostra_todo_campo_do_esquema`` (o produto não pode esconder um
campo que o perfil guarda) e ``test_nenhuma_isencao_desta_lista_ja_caducou``
(uma isenção que já foi atendida tem de sumir). ``SECOES_POR_CONTROLE`` deixou
de ser digitada e passa a sair de ``ControllerOverrides.model_fields``.

A MORDIDA (as quatro, e cada uma acusa uma metade diferente):

    devolva `"guarda.secao"` a `a10_perfis.NAO_PINTAVEIS`
        -> `test_o_produto_acende_a_celula_do_controle_certo` reprova: a coluna
           voltou a ser desenho.
    troque a emissão de volta para `for s in (g.get("secoes") or [])`
        -> o mesmo teste reprova nomeando o P2, que passaria a acender tudo.
    devolva um `title=` a uma célula em `aba10.linha_do_controle`
        -> `test_a_celula_nao_tem_dica_nenhuma` reprova.
    tire o `mic` de `SECOES_DA_COLUNA` sem tirar do desenho
        -> `test_a_ordem_das_celulas_e_a_do_desenho` reprova: a distribuição
           passaria a casar célula com vizinha.
"""
from __future__ import annotations

import re
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import perfis_web
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis

#: A MESA DA RÉGUA — dois controles, com os endereços já MASCARADOS (octetos 4 e
#: 5 zerados, a máscara desta casa). Nenhum endereço real de rádio em arquivo
#: versionado.
MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1,
     "cor": "cosmic-red", "nome": "Cosmic Red", "via": "BT",
     "transporte": "bt", "alvo": True, "mascara": "DualSense"},
    {"pref": "p2", "uniq": "aabbcc000002", "jogador": 2,
     "cor": "starlight-blue", "nome": "Starlight Blue", "via": "USB",
     "transporte": "usb", "alvo": False, "mascara": "DualSense"},
]

#: A CÉLULA DA COLUNA, no HTML gerado. O `class="gr"` e o `data-hef` juntos: só
#: o `data-hef` casaria também o `<td>` vizinho num dia de reorganização.
CELULA = re.compile(r'<span class="gr[^"]*" data-hef="guarda\.secao"[^>]*>')


def _perfil_de_regua() -> Any:
    """Um perfil que guarda ajuste próprio de UM controle só, e de UMA seção.

    O DISCO NÃO SERVE: no lar de mentira do `conftest.py`,
    `load_all_profiles()` devolve zero perfis, e uma régua que dependesse dele
    daria verde por vacuidade — sem perfil, `pacote_da_aba` devolve `guarda=[]`
    e a coluna nunca é medida.

    UM SÓ, E NÃO TODOS, e é o ponto da régua: é a assimetria que distingue "o
    produto leu o perfil" de "o produto acendeu tudo". Com os dois controles
    guardando as mesmas seções, a emissão errada (as CHAVES do dicionário) e a
    certa (os VALORES) teriam a mesma cara.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        MatchAny,
        Profile,
    )

    return Profile(
        name="régua", match=MatchAny(),
        controllers={MESA[0]["uniq"]: ControllerOverrides(
            rumble={"policy": "economia"})},
    )


@pytest.fixture(autouse=True)
def _perfil_no_lugar_do_disco(monkeypatch: pytest.MonkeyPatch) -> None:
    """O perfil da régua no lugar da pasta dela — e o `_ESCOLHIDO` limpo.

    O `_ESCOLHIDO` é estado de MÓDULO (é a linha aberta no editor, e vive no
    Python de propósito). Sem limpá-lo, um teste herdaria a escolha do anterior.
    """
    from hefesto_dualsense4unix.profiles import loader

    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(
        loader, "load_all_profiles", lambda *a, **k: [_perfil_de_regua()])


def _emitidos() -> dict[str, Any]:
    """O que `a10_perfis.pacote()` manda pintar, com uma mesa de dois."""
    ctx = Contexto(state={"active_profile": "régua"}, mesa=list(MESA),
                   conectados=list(MESA), estados={})
    return a10_perfis.pacote(ctx)


def _celulas(publicado: bool) -> list[str]:
    """As células da coluna, na ordem do documento."""
    html = onde.pagina("10-perfis.html", publicado=publicado).read_text(
        encoding="utf-8")
    return CELULA.findall(html)


def test_o_produto_acende_a_celula_do_controle_certo() -> None:
    """A régua-mãe: um perfil que guarda `rumble` só do P1 acende UMA célula.

    Ela mede as duas metades de uma vez — que o endereço SAI do pacote (se
    voltar a `NAO_PINTAVEIS`, não sai) e que ele sai com os ESTADOS, não com os
    nomes das seções.
    """
    emitido = _emitidos().get("guarda.secao")
    assert emitido is not None, (
        "`guarda.secao` não é emitido: a coluna `Ajuste próprio` voltou a ser "
        "desenho. Se ele foi devolvido a `NAO_PINTAVEIS`, o motivo tem de estar "
        "escrito lá — o alvo `classe` existe no piloto desde 03/09/2026.")

    largura = len(a10_perfis.SECOES_DA_COLUNA)
    assert len(emitido) == len(MESA) * largura, (
        f"a emissão tem {len(emitido)} valores para {len(MESA)} controles x "
        f"{largura} seções. O bootstrap distribui a lista pela ordem do "
        f"documento: um bloco a menos casa a célula de um controle com a do "
        f"vizinho.")

    # UMA LINHA POR CONTROLE, na ordem da mesa.
    linhas = [emitido[i * largura:(i + 1) * largura] for i in range(len(MESA))]
    aceso = {
        secao
        for secao, valor in zip(a10_perfis.SECOES_DA_COLUNA, linhas[0], strict=True)
        if valor
    }
    assert aceso == {"rumble"}, (
        f"o P1 guarda só `rumble` neste perfil, e a coluna acendeu {aceso or 'nada'}")
    assert not any(linhas[1]), (
        f"o P2 não guarda NADA neste perfil e a coluna dele acendeu "
        f"{[s for s, v in zip(a10_perfis.SECOES_DA_COLUNA, linhas[1], strict=True) if v]}. "
        f"É o defeito de 02/09: emitir as CHAVES do dicionário `secoes` em vez "
        f"dos valores acende tudo para todo mundo.")


def test_a_pagina_publicada_sabe_receber_a_pintura() -> None:
    """Toda célula do PRODUTO tem `data-hef-alvo="classe"`.

    Sem o alvo, o pintor escreve `textContent` e apaga o glifo SVG de dentro do
    `<span>` — o defeito que ela fotografou em 02/09 na coluna ao lado. Esta
    régua lê a página PUBLICADA de propósito: é ela que recebe a pintura, e
    medir a bancada daria verde sobre um HTML que o produto não renderiza.
    """
    celulas = _celulas(publicado=True)
    assert celulas, "a página publicada não tem célula de `guarda.secao` nenhuma"
    sem_alvo = [c for c in celulas if 'data-hef-alvo="classe"' not in c]
    assert not sem_alvo, (
        f"{len(sem_alvo)} de {len(celulas)} células publicadas sem "
        f'`data-hef-alvo="classe"`. Enquanto for assim, `guarda.secao` tem de '
        f"voltar para `a10_perfis.NAO_PINTAVEIS`: pintá-las apaga o glifo.")


def test_a_celula_nao_tem_dica_nenhuma() -> None:
    """DECISÃO DELA nº4 — as oito dicas das células saíram, e não voltam.

    A régua olha o ELEMENTO, e não as frases que saíram: proibir os oito textos
    um a um deixaria a nona dica entrar livre.

    ELA MEDE A BANCADA, E SÓ ELA — e isso não é frouxidão, é onde a decisão
    mora. Tirar uma dica MUDA O QUE ELA VÊ, então é desenho; e desenho só chega
    ao produto pelo `--publicar` DELA (`check_o_desenho_aprovado.py`, e o
    contrário disso é o defeito que o `onde.py` inteiro existe para impedir).
    Até lá a página publicada continua com as oito, e a espera está declarada em
    `mockup/DIVERGENCIAS.md`, que é o portão que a policia. Cobrar o publicado
    aqui seria esta régua reprovando a página por não ter recebido uma decisão
    que ainda é dela para tomar.
    """
    com_dica = [c for c in _celulas(publicado=False) if "title=" in c]
    assert not com_dica, (
        f"{len(com_dica)} célula(s) de `Ajuste próprio` com dica. Ela mandou as "
        f"oito saírem em 03/09/2026: \"Meu Deus melhor nenhuma assim. Auto "
        f"falante é auto falante, gatilho é gatilho.\" A dica do CABEÇALHO "
        f"explica o conceito uma vez, e o glifo já diz o nome da peça.")


def test_a_ordem_das_celulas_e_a_do_desenho() -> None:
    """`SECOES_DA_COLUNA` é a ordem em que as células saem no HTML.

    A lista vive duas vezes — no gerador (`aba10.SECOES`) e no pacote — porque o
    gerador é um script que lê o repositório no import e não pode ser importado
    por um pacote instalado. O preço da segunda cópia é esta régua: a
    distribuição do bootstrap é POSICIONAL, então uma divergência de ordem faz a
    célula de uma seção mostrar o estado de outra, calada.
    """
    secoes = [re.search(r'data-hef-secao="([^"]+)"', c).group(1)
              for c in _celulas(publicado=False)]
    largura = len(a10_perfis.SECOES_DA_COLUNA)
    assert secoes[:largura] == list(a10_perfis.SECOES_DA_COLUNA), (
        f"a primeira linha do desenho traz {secoes[:largura]} e o pacote "
        f"distribui na ordem {list(a10_perfis.SECOES_DA_COLUNA)}")
    # E TODA LINHA REPETE A MESMA ORDEM: o bloco de N valores só vale se as
    # linhas forem iguais entre si.
    assert secoes == list(a10_perfis.SECOES_DA_COLUNA) * (len(secoes) // largura), (
        "as linhas da tabela não repetem a mesma ordem de seções")


def test_nenhum_campo_do_perfil_fica_sem_coluna() -> None:
    """Tudo o que o perfil SABE guardar por controle tem célula na tela.

    É o sentido que precisa morder: um campo em `ControllerOverrides` sem coluna
    é um ajuste que o perfil guarda e a tela esconde — ela não teria como saber
    que aquele controle tem opinião própria. O sentido contrário (coluna sem
    campo) é legítimo e declarado: ver `ESPERANDO_O_ESQUEMA`.
    """
    faltando = set(perfis_web.SECOES_POR_CONTROLE) - set(a10_perfis.SECOES_DA_COLUNA)
    assert not faltando, (
        f"o perfil guarda {sorted(faltando)} por controle e a coluna `Ajuste "
        f"próprio` não os mostra — ajuste guardado que a tela esconde")


def test_toda_coluna_sem_campo_esta_declarada() -> None:
    """Uma coluna que o esquema ainda não guarda é DECLARAÇÃO, nunca invenção.

    ELA NÃO REPROVA QUANDO O CAMPO CHEGA, de propósito: no dia em que
    `ControllerOverrides` ganhar o `mic`, a seção passa a estar no esquema e a
    conta fecha sem ninguém mexer aqui. Uma régua que ficasse vermelha ao
    receber a cura seria uma armadilha para a frente seguinte.
    """
    sem_campo = set(a10_perfis.SECOES_DA_COLUNA) - set(perfis_web.SECOES_POR_CONTROLE)
    nao_declaradas = sem_campo - a10_perfis.ESPERANDO_O_ESQUEMA
    assert not nao_declaradas, (
        f"a coluna mostra {sorted(nao_declaradas)}, que o perfil não guarda e "
        f"ninguém declarou. Uma coluna assim é a tela prometendo um ajuste que "
        f"nada aplica — declare em `a10_perfis.ESPERANDO_O_ESQUEMA` com a "
        f"decisão que a pediu, ou tire do desenho.")


def test_a_coluna_do_microfone_existe_na_tela() -> None:
    """DECISÃO DELA nº20 — o microfone é o quinto ajuste por controle.

    *"É justamente o `Virtual` que faz o mic soar igual no cabo e no rádio, ou
    seja: é o ajuste que faz o CANAL daquele controle funcionar."* A tela vem
    antes do campo por decisão dela, e a célula fica apagada em todo perfil real
    enquanto o campo não existir — o que `test_toda_coluna_sem_campo_esta_declarada`
    mantém honesto.
    """
    assert "mic" in a10_perfis.SECOES_DA_COLUNA, (
        "o microfone saiu da coluna `Ajuste próprio` (decisão dela nº20)")
    secoes = {re.search(r'data-hef-secao="([^"]+)"', c).group(1)
              for c in _celulas(publicado=False)}
    assert "mic" in secoes, "o desenho perdeu a célula do microfone"


# ---------------------------------------------------------------------------
# A DIREÇÃO QUE NINGUÉM GUARDAVA — o ESQUEMA contra o PRODUTO
#
# As duas réguas acima comparam o produto com o DESENHO, e as duas estavam
# verdes enquanto a coluna do microfone ficava apagada à força: o desenho tinha
# as cinco células e o produto emitia quatro chaves. Faltava perguntar ao
# ESQUEMA, que é quem decide o que existe no disco.
# ---------------------------------------------------------------------------
def test_o_produto_mostra_todo_campo_do_esquema() -> None:
    """O que o perfil GUARDA por controle, a coluna MOSTRA. Nome a nome, na ordem.

    A ORDEM entra no ``assert`` de propósito: ``pintaGuarda`` casa por NOME
    (``linha.secoes[g.dataset.hefSecao]``), mas o pacote emite uma LISTA que o
    piloto distribui pela ordem do documento. Duas listas com os mesmos nomes em
    ordens diferentes acendem a luz onde a vibração está guardada, e o número de
    valores continua batendo — ninguém acusaria.

    MORDIDA: devolva ``perfis_web.SECOES_POR_CONTROLE`` à tupla digitada de
    quatro nomes (sem o ``mic``) e esta régua reprova nomeando o campo
    escondido.
    """
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    do_esquema = tuple(ControllerOverrides.model_fields)
    assert do_esquema == perfis_web.SECOES_POR_CONTROLE, (
        "o que o perfil guarda por controle e o que a coluna `Ajuste próprio` "
        "mostra deixaram de ser a mesma lista:\n"
        f"  esquema (ControllerOverrides)  {do_esquema}\n"
        f"  produto (SECOES_POR_CONTROLE)  {perfis_web.SECOES_POR_CONTROLE}\n"
        "Um campo do esquema que não sai daqui fica APAGADO À FORÇA na tela: "
        "`pintaGuarda` faz `!!linha.secoes[nome]`, e chave ausente é `false`.")


def test_nenhuma_isencao_desta_lista_ja_caducou() -> None:
    """Uma coluna declarada *"o campo está a caminho"* some quando ele chega.

    ``ESPERANDO_O_ESQUEMA`` é isenção com prazo, e a régua que a guardava é de
    uma direção só de propósito — ``test_toda_coluna_sem_campo_esta_declarada``
    diz, com todas as letras, que *"ela não reprova quando o campo chega"*. Isso
    evita uma armadilha para a frente seguinte e cria outra: a isenção nunca
    caduca sozinha. Foi assim que o ``mic`` ficou declarado como ausente por um
    dia depois de ter chegado, cobrindo a coluna apagada.

    Esta fecha a outra direção. Ela não pede que ninguém lembre — reprova.

    MORDIDA: ponha ``"mic"`` de volta em ``a10_perfis.ESPERANDO_O_ESQUEMA`` e
    esta régua reprova mandando apagá-lo.
    """
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides

    caducas = set(a10_perfis.ESPERANDO_O_ESQUEMA) & set(
        ControllerOverrides.model_fields)
    assert not caducas, (
        f"`ESPERANDO_O_ESQUEMA` ainda declara {sorted(caducas)} como *a "
        "caminho*, e o campo JÁ está em `ControllerOverrides`. Apague o nome "
        "da lista: enquanto ele estiver lá, a isenção cobre uma coluna que "
        "deveria estar acendendo com o dado dela.")


def test_a_frase_da_linha_sem_ajuste_conta_os_ajustes_certos() -> None:
    """*"herda os cinco ajustes do perfil"* — e a palavra sai da lista.

    A frase trazia ``quatro`` digitado. Com a quinta coluna na tela, a linha de
    um controle sem ajuste próprio mostrava cinco glifos apagados e dizia
    *"herda os quatro"* — o número ao lado do que o desmente. Para quem lê a
    tela contando, são duas afirmações contrárias na mesma linha.

    MORDIDA: volte a escrever ``"herda os quatro ajustes do perfil"`` em
    ``perfis_web._linhas_da_guarda`` e esta régua reprova.
    """
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile

    esperado = {4: "quatro", 5: "cinco", 6: "seis"}[
        len(perfis_web.SECOES_POR_CONTROLE)]
    sem_nada = Profile(name="sem nada", match=MatchAny(), controllers={})
    linhas = perfis_web._linhas_da_guarda([dict(MESA[0])], sem_nada)
    assert f"herda os {esperado} ajustes do perfil" in linhas[0]["dica"], (
        f"a linha sem ajuste próprio não diz `herda os {esperado} ajustes`; "
        f"a dica é {linhas[0]['dica']!r}")
