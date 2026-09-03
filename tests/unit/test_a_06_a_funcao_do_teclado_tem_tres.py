#!/usr/bin/env python3
"""A RÉGUA DA DECISÃO 5: as três palavras da "Função do teclado".

DECISÃO DELA, 02/09/2026: *"`Só dentro do jogo` · `Só fora do jogo` ·
`Desativado`. O padrão de um perfil novo é `Só fora do jogo` — no jogo o L3 é o
clique do analógico e o teclado atrapalha; no desktop é onde ele serve."*

O FATO QUE ESTA RÉGUA DERRUBA, e ele estava escrito no pacote E no enunciado do
trabalho: *"'Só fora do jogo' não existe do outro lado"* e *"'Só dentro do jogo'
já existe, e é o `suppress_desktop_emulation`"*. **Os dois estão invertidos.**

    `Profile.suppress_desktop_emulation` (`profiles/schema.py:1036`)
        "True = ativar o perfil suprime a emulação de mouse/teclado no desktop
         (jogos de GAMEPAD que leem o controle cru)"

O perfil é ativado quando o JOGO casa; logo a supressão vale DURANTE o jogo, e o
teclado sobra FORA dele. E, sem perfil nenhum a dizer o contrário, o daemon já
cala a emulação de desktop quando um jogo assume — `_jogo_no_controle_do_desktop`
(`daemon/lifecycle.py:2263`, a cura da queixa dela de 29/07: *"aperto r1 e ele
muda de app ao invés de funcionar no jogo"*) e o `gamepad_dispatched` do laço
(`:4780`).

Logo o teclado emulado LIGADO **é** "só fora do jogo": a etiqueta velha
("Ligada — atalhos e teclado na tela") é que prometia um alcance maior do que o
produto tem. Quem não tem dono é o INVERSO — "só dentro do jogo" —, e ele pede
um campo novo no perfil, o portão com o sinal trocado.

O QUE ESTA RÉGUA COBRA:

1. as três palavras dela estão no desenho, e a lista nasce no padrão que ela
   escolheu;
2. as duas com dono chamam `keyboard.emulation.set` com o bool certo;
3. a terceira RECUSA DIZENDO, sem chamar nada — em vez de aceitar o clique e
   não fazer nada, que é o defeito mais caro desta casa;
4. o gesto casa pela palavra que DISTINGUE, e não pela primeira: com as três
   palavras dela, duas começam por "só";
5. **A DIREÇÃO DO ATO, e ela faltava** — 02/09/2026, corretivo. Para cada
   `<option>` que a página OFERECE, o gesto responde. E para cada estado do
   daemon, a pintura diz uma palavra que aquela página sabe receber. **Nas
   DUAS páginas**: a publicada, que é a que ela clica hoje, e a bancada, que é
   a que ela vai clicar depois de publicar;
6. os sinônimos da travessia TÊM PRAZO: cada um só vale enquanto a página
   publicada ainda o oferece.

O QUE A FALTA DO ITEM 5 CUSTOU, e é a razão deste corretivo. A régua anterior
olhava só a direção da PINTURA, e contra as constantes do PRÓPRIO pacote — ela
só podia concordar consigo mesma. Com ela verde, e com os 30 portões verdes:

    opção que a página publicada oferece      o que o gesto fazia
    'Ligada — atalhos e teclado na tela'  ->  ValueError (clique morto, calado)
    'Só fora do jogo'                     ->  keyboard.emulation.set enabled=true
    'Desligada'                           ->  ValueError (clique morto, calado)

    estado do daemon    o que a pintura emitia   o que ELA lia na tela
    LIGADO              'Só fora do jogo'        'Só fora do jogo'
    DESLIGADO           'Desativado'             'Ligada — atalhos e teclado na tela'

Duas das três opções viraram clique morto — e uma delas era a única forma de
DESLIGAR o teclado por esta aba. E com o teclado desligado a tela passou a
AFIRMAR que ele estava ligado, porque `escrever()` descarta em silêncio o texto
que não casa com nenhuma `<option>` e o que fica é a que o desenho crava.

A MORDIDA: devolva `_ESCOLHA` a casar pela primeira palavra
(`escolhido.split()[0]`) — o item 4 reprova, porque "Só dentro do jogo" passaria
a ligar o teclado como se fosse "Só fora do jogo". A do item 5 é esvaziar
`SINONIMOS_ATE_A_PUBLICACAO`, ou cravar a palavra da bancada na pintura.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo

#: O `<select>` da "Função do teclado", recortado antes das `<option>`: a página
#: tem outras 21 listas, e casar solto traria as 25 ações de botão junto.
_SELECT = r'<select[^>]*data-campo="teclado-estado"[^>]*>(.*?)</select>'

#: OS DOIS MUNDOS, e é o par que esta régua existe para atravessar. `True` é a
#: página que o piloto carrega HOJE (`hefesto_vivo.py` abre sempre
#: `publicado=True`); `False` é a bancada, que vira a tela dela no dia em que
#: ela publicar. Um teste que só olhasse um dos dois deixaria o outro quebrar
#: calado — foi o que aconteceu.
OS_DOIS_MUNDOS = [
    pytest.param(True, id="a-pagina-publicada-de-hoje"),
    pytest.param(False, id="a-bancada-do-dia-da-publicacao"),
]


def _opcoes(publicado: bool) -> list[str]:
    """As `<option>` da "Função do teclado", LIDAS do HTML — nunca digitadas."""
    import onde

    doc = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    bloco = re.search(_SELECT, doc, re.S)
    assert bloco, f"não achei o `<select>` do teclado em {PAGINA} (publicado={publicado})"
    return re.findall(r"<option[^>]*>(.*?)</option>", bloco.group(1))


class _PonteQueAnota:
    """Aceita tudo e ANOTA. É o que separa "recusou" de "chamou e não disse".

    ELE RESPONDE PELO CORPO DESDE 03/09/2026, e a mudança é do contrato: o gesto
    passou de `chamar` (devolve `bool`, joga fora a resposta) para `resultado`
    (devolve o que o daemon disse), porque era o `bool` que fazia um
    `{"status": "failed"}` voltar como sucesso e a recusa não chegar à tela
    dela. O dublê devolve o `ok` do daemon de verdade — inclusive o bloco
    `keyboard_emulation`, que é o que o handler manda para a janela não precisar
    de uma segunda chamada (`daemon/ipc_handlers.py:5279`).

    O `chamar` FICA, e não é enfeite: ele prova que nenhum gesto desta aba
    voltou ao caminho que perde o motivo — se alguém reintroduzir um `p.chamar`,
    ele aparece em `self.chamadas` com o nome errado e o `assert` do método
    acusa.
    """

    def __init__(self, status: str = "ok", bloqueio: str | None = None) -> None:
        self.chamadas: list[tuple[str, dict]] = []
        self.status = status
        self.bloqueio = bloqueio

    def chamar(self, metodo: str, **params: object) -> bool:
        self.chamadas.append((metodo, dict(params)))
        return True

    def resultado(self, metodo: str, **params: object) -> dict:
        self.chamadas.append((metodo, dict(params)))
        bloco: dict[str, object] = {"enabled": bool(params.get("enabled"))}
        if self.bloqueio is not None:
            bloco["bloqueio"] = self.bloqueio
        return {"status": self.status,
                "enabled": bool(params.get("enabled")),
                "keyboard_emulation": bloco}


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(state={"active_profile": "regua"})


def test_as_tres_palavras_dela_estao_no_desenho():
    """O gerador e o pacote falam a MESMA lista, e ela é a dela.

    A repetição entre `aba06.OPCOES_TECLADO` e as três constantes do pacote é
    declarada nos dois lados; o que não pode é as duas envelhecerem separadas —
    uma opção que o pacote emita e o desenho não ofereça vira um campo parado
    para sempre, porque `escrever()` se cala em silêncio quando não casa.
    """
    import aba06
    from pacotes import a06_navegacao as mod

    assert aba06.OPCOES_TECLADO == [mod.TECLADO_SO_DENTRO, mod.TECLADO_SO_FORA,
                                    mod.TECLADO_DESATIVADO], (
        f"o desenho oferece {aba06.OPCOES_TECLADO} e o pacote fala outra "
        "língua — a lista pararia de ser pintada sem uma linha de erro.")
    assert aba06.TECLADO_PADRAO == mod.TECLADO_SO_FORA, (
        "a lista não nasce no padrão que ela escolheu")


def test_o_desenho_nasce_no_padrao_dela():
    """`Só fora do jogo` marcada, e é a única das três com dono hoje.

    Nascer marcada na primeira (`Só dentro do jogo`) faria a tela prometer, nos
    500 ms anteriores ao primeiro tique, o que o Hefesto ainda não sabe fazer.

    A MORDIDA: tire o `escolhido=TECLADO_PADRAO` da chamada de `simples()` no
    gerador — esta linha reprova, e o `_conferir` do gerador reprova antes.
    """
    import onde
    from pacotes import a06_navegacao as mod

    doc = onde.pagina(PAGINA).read_text(encoding="utf-8")
    assert f"<option selected>{mod.TECLADO_SO_FORA}</option>" in doc
    for opcao in (mod.TECLADO_SO_DENTRO, mod.TECLADO_DESATIVADO):
        assert f"<option>{opcao}</option>" in doc, f"{opcao!r} sumiu do desenho"


@pytest.mark.parametrize("rotulo_e_bool", [("TECLADO_SO_FORA", True),
                                           ("TECLADO_DESATIVADO", False)])
def test_as_duas_com_dono_chamam_o_daemon(ctx, rotulo_e_bool):
    """Uma chamada, `keyboard.emulation.set`, e o bool que a opção quer dizer."""
    from pacotes import a06_navegacao as mod

    nome, esperado = rotulo_e_bool
    ponte = _PonteQueAnota()
    mod.teclado(ctx, {"valor": getattr(mod, nome)}, ponte)
    assert ponte.chamadas == [("keyboard.emulation.set", {"enabled": esperado})], (
        f"{nome}: o gesto chamou {ponte.chamadas}")


def test_a_terceira_recusa_dizendo_e_nao_chama_nada(ctx):
    """"Só dentro do jogo" não tem dono, e o botão DIZ isso.

    Um gesto que aceitasse o clique e não fizesse nada seria a
    `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` em miniatura: quem clicou concluiria que
    funcionou. `RuntimeError` é o produto recusando com o motivo.

    A MORDIDA: faça `_ESCOLHA["dentro"]` valer `True` — esta linha reprova
    dizendo que a opção sem dono passou a ligar o teclado calada.
    """
    from pacotes import a06_navegacao as mod

    ponte = _PonteQueAnota()
    with pytest.raises(RuntimeError) as caiu:
        mod.teclado(ctx, {"valor": mod.TECLADO_SO_DENTRO}, ponte)
    frase = str(caiu.value)
    assert mod.TECLADO_SO_DENTRO in frase, f"a recusa não diz qual opção: {frase!r}"
    assert mod.TECLADO_SO_FORA in frase, (
        "a recusa não diz o que o produto FAZ hoje, que é o outro lado — sem "
        f"isso ela é um 'não dá' sem saída: {frase!r}")
    assert not ponte.chamadas, f"recusou e ainda assim chamou {ponte.chamadas}"


def test_o_gesto_casa_pela_palavra_que_distingue(ctx):
    """Duas das três começam por "só" — casar pela primeira as confundiria.

    E o casamento é TOLERANTE ao resto da frase: reescrever o texto da tela não
    pode desligar o botão calado, que é o que aconteceria com a frase inteira
    como chave.
    """
    from pacotes import a06_navegacao as mod

    ponte = _PonteQueAnota()
    mod.teclado(ctx, {"valor": "Só fora do jogo — o teclado vale no desktop"}, ponte)
    assert ponte.chamadas == [("keyboard.emulation.set", {"enabled": True})]

    with pytest.raises(RuntimeError):
        mod.teclado(ctx, {"valor": "Só dentro do jogo, e mais nada"},
                    _PonteQueAnota())

    # O QUE CONTINUA SENDO CLIQUE INVÁLIDO, e é o que sobrou: uma frase que não
    # traz palavra nenhuma da lista, e uma que traz DUAS. A segunda é a que
    # importa — se o gesto escolhesse "a primeira que achar", uma opção nova mal
    # escrita ligaria o teclado sem ninguém pedir.
    #
    # ESTA LINHA JÁ USOU "Ligada — atalhos e teclado na tela", que era PALAVRA
    # POR PALAVRA a primeira `<option>` da página que o produto renderizava. O
    # teste cravava como CORRETO que o clique dela naquela opção fosse
    # clique-inválido, e assim o teste protegia o defeito: quem curasse o clique
    # morto veria esta linha ficar vermelha e concluiria que a cura é que estava
    # errada. O item 5 desta régua é o que ficou no lugar.
    #
    # E DEPOIS USOU "Ligada — só dentro do jogo" para o caso das DUAS palavras.
    # Com os sinônimos da travessia apagados (03/09/2026) `ligada` deixou de ser
    # palavra do gesto, e a frase passou a trazer UMA — o exemplo virava um
    # `RuntimeError`, e a régua deixava de medir o que prometia. O par de agora
    # traz as duas palavras que EXISTEM.
    for lixo in ("Modo turbo", "Só dentro do jogo e só fora do jogo"):
        with pytest.raises(ValueError, match="não reconheci"):
            mod.teclado(ctx, {"valor": lixo}, _PonteQueAnota())


@pytest.mark.parametrize("publicado", OS_DOIS_MUNDOS)
def test_toda_opcao_que_a_tela_oferece_tem_resposta(ctx, publicado):
    """A DIREÇÃO DO ATO: nenhuma opção da lista pode virar clique morto.

    A régua irmã (`test_todo_valor_do_duble_existe_como_opcao`) mede a direção
    da PINTURA — o valor que o pacote escreve existe como `<option>`. Faltava
    esta: **para cada `<option>` que a página oferece, o gesto entende?** Sem
    ela, mudar a lista da bancada transformou duas das três opções da tela dela
    em clique que não faz nada e não diz nada.

    "Entende" é UMA de duas coisas, e as duas são legítimas:

    * chama `keyboard.emulation.set` com um bool — a opção tem dono;
    * levanta `RuntimeError` — o produto RECUSA DIZENDO, e a frase vai para o
      desfecho que a régua do aparelho lê.

    `ValueError` é a terceira, e é a que não pode existir aqui: ele é o
    clique-inválido, o caminho de quem clicou em algo que a tela não oferece.
    Para uma opção que a tela OFERECE, ele é o botão morto e calado.
    """
    from pacotes import a06_navegacao as mod

    mudos = []
    for rotulo in _opcoes(publicado):
        ponte = _PonteQueAnota()
        try:
            mod.teclado(ctx, {"valor": rotulo}, ponte)
        except ValueError:
            mudos.append(rotulo)
        except RuntimeError:
            continue  # recusou dizendo, que é resposta
        else:
            assert ponte.chamadas, f"{rotulo!r}: aceitou o clique e não chamou nada"
    assert not mudos, (
        f"a lista {'publicada' if publicado else 'da bancada'} oferece "
        f"{mudos} e o gesto levanta clique-inválido nelas. A frase de um "
        "`ValueError` NÃO chega ao cartão dela — `hefesto_vivo._recusou_dizendo` "
        "leva só a do `RuntimeError`, porque clique-inválido fala com quem "
        "programa. Então ela clica e nada acontece, sem uma palavra do porquê.")


@pytest.mark.parametrize("publicado", OS_DOIS_MUNDOS)
def test_a_pintura_diz_a_palavra_que_aquela_pagina_sabe_receber(publicado, monkeypatch):
    """A pintura acompanha a página CARREGADA, e não uma constante cravada.

    `escrever()` com `data-hef-alvo="valor"` só aceita o texto exato de uma
    `<option>` e devolve `0` **em silêncio** fora disso (`hefesto_vivo.py`, ramo
    `alvo === 'valor'`). O que fica na tela quando ele se cala não é o vazio: é
    a `<option selected>` que o desenho crava — logo o campo passa a AFIRMAR o
    contrário, que é pior do que não dizer nada e é o lado que a decisão dela de
    02/09 fecha (*"se não tá mostrando agora, não tem info pra mostrar; mas
    quando tiver, aparece a info correta"*).

    Este teste NÃO digita a palavra esperada: ele lê a lista da página e cobra
    que o emitido esteja lá. Digitar a resposta é a régua concordando consigo
    mesma, que é como o defeito passou.
    """
    import pacotes
    from pacotes import a06_navegacao as mod

    ofertas = frozenset(_opcoes(publicado))
    monkeypatch.setattr(mod, "_o_que_a_pagina_oferece", lambda: ofertas)
    dito = {}
    for ligado in (True, False):
        estado = {"active_profile": None,
                  "keyboard_emulation": {"enabled": ligado}}
        mesa = mod.pacote(pacotes.Contexto(state=estado))["mesa"]
        valor = mesa["teclado-estado"]
        assert valor in ofertas, (
            f"teclado {'ligado' if ligado else 'desligado'}: o pacote emite "
            f"{valor!r} e a lista desta página é {sorted(ofertas)} — a escrita "
            "seria descartada em silêncio e a tela ficaria na opção do desenho.")
        dito[ligado] = valor
    assert dito[True] != dito[False], (
        f"os dois estados dizem a mesma palavra ({dito[True]!r}) — a linha "
        "pararia de distinguir teclado ligado de desligado.")

    # SEM O BLOCO, A CHAVE NÃO SAI — e é o que impede a tela de afirmar um
    # estado que ninguém mediu (daemon mudo, ou config inacessível).
    mudo = mod.pacote(pacotes.Contexto(state={"active_profile": None}))["mesa"]
    assert "teclado-estado" not in mudo, (
        "sem `keyboard_emulation` no estado, a tela afirmaria um estado que o "
        "daemon não disse")


def test_o_pacote_olha_mesmo_a_pagina_que_o_piloto_carrega():
    """SEM DUBLÊ NENHUM: o leitor real, contra o arquivo real.

    O BURACO QUE ELA FECHA, e ele apareceu na MORDIDA — 02/09/2026. As duas
    réguas dos dois mundos trocam `_o_que_a_pagina_oferece` por um dublê para
    escolher qual página está carregada. Com isso, **cegar o leitor de verdade
    (`return frozenset()` na primeira linha) passou com 19 verdes**: os testes
    mediam o mecanismo de escolha e nunca a leitura.

    Esta linha é a que não tem dublê. Ela pergunta ao pacote, sem intermediário,
    o que ele enxerga — e cobra que seja exatamente a lista do arquivo que o
    `WebView` abre.
    """
    from pacotes import a06_navegacao as mod

    mod._OFERTAS = None  # a lembrança de outra volta não pode responder por esta
    visto = mod._o_que_a_pagina_oferece()
    assert visto == frozenset(_opcoes(True)), (
        f"o pacote enxerga {sorted(visto)} e a página que o piloto carrega "
        f"oferece {_opcoes(True)}. Um leitor cego devolve a palavra dela em "
        "qualquer página, e volta o campo que afirma o contrário.")


def test_a_pintura_sem_duble_casa_com_a_pagina_do_produto():
    """A pintura de verdade, na página de verdade, nos dois estados do daemon.

    Irmã da de cima e pela mesma razão: aqui não se troca nada. O que o pacote
    emitiria no tique de agora tem de existir na lista que ela vê.
    """
    import pacotes
    from pacotes import a06_navegacao as mod

    mod._OFERTAS = None
    ofertas = frozenset(_opcoes(True))
    for ligado in (True, False):
        estado = {"active_profile": None, "keyboard_emulation": {"enabled": ligado}}
        valor = mod.pacote(pacotes.Contexto(state=estado))["mesa"]["teclado-estado"]
        assert valor in ofertas, (
            f"teclado {'ligado' if ligado else 'desligado'}: o pacote emitiria "
            f"{valor!r} na página do produto, que oferece {sorted(ofertas)}.")


@pytest.mark.parametrize("publicado", OS_DOIS_MUNDOS)
def test_a_palavra_que_a_tela_diz_e_a_que_o_clique_devolve(ctx, publicado, monkeypatch):
    """A IDA E VOLTA: o que a linha AFIRMA e o que o clique nela FAZ são o mesmo.

    A régua da ida (a pintura casa com a lista) e a régua da volta (toda opção
    tem resposta) passam as duas com o sentido de um sinônimo INVERTIDO —
    `{"desligada": True}` chamaria o daemon, e casar continuaria casando. Quem
    pega isso é o par: a palavra que a tela usa para dizer *desligado* tem de
    ser lida como *desligado* quando ela clica nela.

    É a mesma forma de defeito que a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` persegue,
    com o sinal trocado: a tela dizendo uma coisa e o botão fazendo outra.
    """
    from pacotes import a06_navegacao as mod

    import pacotes

    monkeypatch.setattr(mod, "_o_que_a_pagina_oferece",
                        lambda: frozenset(_opcoes(publicado)))
    for ligado in (True, False):
        estado = {"active_profile": None, "keyboard_emulation": {"enabled": ligado}}
        palavra = mod.pacote(pacotes.Contexto(state=estado))["mesa"]["teclado-estado"]
        ponte = _PonteQueAnota()
        mod.teclado(ctx, {"valor": palavra}, ponte)
        assert ponte.chamadas == [("keyboard.emulation.set", {"enabled": ligado})], (
            f"com o teclado {'ligado' if ligado else 'desligado'} a tela diz "
            f"{palavra!r}, e clicar nessa mesma palavra manda "
            f"{ponte.chamadas} — a linha afirma um estado e o clique nela faz "
            "outro.")


def test_a_travessia_acabou_e_nao_deixou_lapide():
    """A régua que existia para ficar vermelha CUMPRIU — e virou esta.

    A anterior, `test_os_sinonimos_da_travessia_tem_prazo`, cobrava que cada
    entrada de `SINONIMOS_ATE_A_PUBLICACAO` ainda existisse como `<option>` da
    página publicada, e reprovava no dia da publicação nomeando o que apagar.
    Ela ficou vermelha em 03/09/2026 e foi obedecida: os sinônimos e as
    constantes `TECLADO_*_HOJE` saíram.

    O QUE ESTA COBRA AGORA, e é o outro lado da mesma linha: que o vocabulário
    do gesto seja **exatamente** a decisão dela, e que ninguém volte a plantar
    uma tradução sem prazo. Um sinônimo novo é legítimo — durante uma travessia
    —, e o lugar dele é uma régua que o mate no dia seguinte, não um dicionário
    permanente.

    A MORDIDA: acrescente `{"ligada": True}` ao `_ESCOLHA` do pacote. Esta linha
    reprova dizendo que apareceu uma palavra que a tela não oferece.
    """
    from pacotes import a06_navegacao as mod

    assert not hasattr(mod, "SINONIMOS_ATE_A_PUBLICACAO"), (
        "`SINONIMOS_ATE_A_PUBLICACAO` voltou. Ele só se justifica enquanto a "
        "bancada e o publicado divergirem nos rótulos — e neste caso ele vem "
        "com a régua que o apaga no dia da publicação, como a anterior tinha.")
    # As palavras que o gesto entende têm de estar na tela, nos DOIS mundos —
    # a bancada é o que ela olha, o publicado é o que o produto renderiza.
    for mundo, publicado in (("publicada", True), ("bancada", False)):
        texto = " ".join(_opcoes(publicado)).lower()
        for palavra in mod._ESCOLHA:
            assert palavra in texto, (
                f"o gesto entende {palavra!r} e a página {mundo} não a oferece "
                f"({_opcoes(publicado)}) — ou é tradução sem prazo, ou é a "
                "bancada tendo andado sem ninguém perguntar o que a tela dela "
                "mostra hoje.")
