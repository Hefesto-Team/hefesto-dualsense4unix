#!/usr/bin/env python3
"""A RÉGUA DA ONDA2-06: o que a aba Navegação passou a DIZER, e por que é verdade.

Ela cobre as cinco decisões do PO de 04/09/2026 sobre esta aba
(`docs/process/2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md` §2
`06-navegacao`) e a metade DITA dos dois defeitos da §3 — os que apagam o que
ela escreveu:

    [01] o portão de modo apaga o interruptor e escreve ao lado
    [02] as três regiões do touchpad ficam, com a marca de que não disparam
    [03] o botão PS fica fora, e a razão vira dica
    [04] uma tira de aviso sob a tabela, com o que vai ser APAGADO
    [05] uma frase permanente enquanto o teclado estiver desativado

**ELA LÊ, NÃO DIGITA.** Nenhum nome de botão, nenhum rótulo de tecla e nenhuma
lista de mapas está escrita aqui: os nomes saem de `input_actions`, o que cada
linha faz sai de `core/acoes_de_botao`, os mapas saem de `uinput_mouse` e o
desenho sai da BANCADA. Esta casa pagou onze vezes em 26/08 por réguas que
digitavam o que deviam ler — elas reprovavam a MELHORA em vez do defeito.

E DUAS DELAS MEDEM O PRODUTO, não a frase: `test_o_que_o_nada_nao_cala…` chama
o `set_button_actions` DE VERDADE e compara com o que a tela afirma; e
`test_o_aviso_nomeia_o_que_o_guardar_vai_substituir` compara a frase com o que
`acoes_de_botao.resolver()` realmente devolve. **As duas continuam verdes no dia
em que o produto for curado** — o que elas cobram é a igualdade entre o que a
tela diz e o que o produto faz, nos dois sentidos.

A MORDIDA, e ela é uma por caso: cada docstring abaixo diz o que arrancar.
"""
from __future__ import annotations

import pathlib
import re
import sys
import types

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo

#: Um controle de mentira, na faixa sintética da casa — há dois portões de
#: anonimato nesta árvore e eles não perdoam.
UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "bt",
         "battery_pct": 95, "is_primary": True, "inputs": {}, "audio": {},
         "speaker": {}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "BT", "cor": "starlight-blue", "mascara": "DualSense"}]

#: O estado com o portão ABERTO: sem `gamepad_emulation` nem `native_mode`,
#: `mode_of_state` responde `desktop` — que é o modo em que o mouse pode ligar.
NO_DESKTOP = {
    "active_profile": "regua",
    "mouse_emulation": {"enabled": False, "speed": 6, "scroll_speed": 1,
                        "bloqueio": "desligada", "despachando": False},
    "keyboard_emulation": {"enabled": True, "osk_disponivel": True},
    "controllers": [FALSO],
}
#: E o mesmo estado com o portão FECHADO. A chave é a do produto
#: (`mode_transition.mode_of_state` lê `gamepad_emulation.enabled`), não uma
#: inventada aqui.
NO_JOGO = {**NO_DESKTOP, "gamepad_emulation": {"enabled": True}}


@pytest.fixture
def aba():
    """O pacote da 06, importado uma vez."""
    from pacotes import a06_navegacao

    return a06_navegacao


def _carga(mod, estado, perfil_cru, monkeypatch):
    """A `mesa` que iria para a tela naquele tique, com um perfil de mentira."""
    import pacotes
    from pacotes import perfil

    monkeypatch.setattr(perfil, "ativo", lambda nome: dict(perfil_cru) if nome else {})
    ctx = pacotes.Contexto(state=estado, mesa=MESA, conectados=[FALSO], estados={})
    return mod.pacote(ctx)["mesa"]


def _bancada() -> str:
    import onde

    return onde.pagina(PAGINA, publicado=False).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# [01] O PORTÃO DE MODO — apaga o interruptor e escreve ao lado
# ---------------------------------------------------------------------------
def test_a_razao_do_portao_e_a_mesma_no_aviso_e_na_recusa(aba, monkeypatch):
    """Um fato, uma frase: a linha permanente e o `RuntimeError` são o MESMO texto.

    O DEFEITO QUE ISTO IMPEDE é o que a decisão do PO chama de segundo canal:
    duas grafias do mesmo fato divergem na primeira correção, e quem clicasse
    leria uma coisa depois de ter lido outra ao lado do interruptor.

    A MORDIDA: escreva um literal no `raise` do gesto `modo` em vez de
    `RAZAO_DO_PORTAO` — este caso reprova mostrando as duas frases.
    """
    import pacotes

    linha = _carga(aba, NO_JOGO, {}, monkeypatch)["modo-portao"]
    assert aba.RAZAO_DO_PORTAO in linha, (
        f"a linha da tira saiu {linha!r} e não carrega a razão do portão.")

    ctx = pacotes.Contexto(state=NO_JOGO, mesa=MESA, conectados=[FALSO], estados={})
    with pytest.raises(RuntimeError) as caiu:
        aba.modo(ctx, {}, _PonteMuda())
    assert str(caiu.value) == aba.RAZAO_DO_PORTAO, (
        "a recusa do gesto e o aviso da tela deixaram de ser a mesma frase:\n"
        f"  tela  : {aba.RAZAO_DO_PORTAO!r}\n  recusa: {str(caiu.value)!r}")


def test_a_linha_do_portao_so_nasce_quando_ha_portao(aba, monkeypatch):
    """Fora do modo "Controlar o PC" ela fala; dentro dele, some.

    É a metade que faz o interruptor voltar ao normal: o cinza sai desta MESMA
    linha, por `:has()` na folha da aba, então uma linha que não some deixaria o
    interruptor apagado para sempre.

    A MORDIDA: faça `_a_razao_do_portao` devolver a frase sempre — este caso
    reprova dizendo que a tela afirma um bloqueio que não existe.
    """
    aberto = _carga(aba, NO_DESKTOP, {}, monkeypatch)["modo-portao"]
    assert aberto == aba.NADA_A_DIZER, (
        f"no modo desktop a linha do portão saiu {aberto!r} — ela tem de sumir, "
        "e com ela o cinza do interruptor.")
    # E SEM ESTADO ela também não afirma: um daemon que não respondeu não é um
    # portão fechado. Apagar o interruptor por silêncio seria inventar o fato.
    assert aba._a_razao_do_portao({}) == aba.NADA_A_DIZER


def test_a_folha_apaga_o_interruptor_pela_propria_linha():
    """O cinza do interruptor sai da linha da tira — UM endereço, zero divergência.

    A régua lê o CSS gerado, e não o Python: é a folha que decide, e é ela que
    tem de mencionar as duas pontas na mesma regra.

    A MORDIDA: tire a regra `.quadro-corpo:has(.estado.portao .laranja)` do CSS
    da aba e rode — este caso reprova nomeando o que sumiu. (A prova de que a
    regra PINTA está no relatório da frente, medida no WebKit: `cursor` vai de
    `pointer` a `not-allowed` e a borda de `--border-forte` a `--border-sutil`.)
    """
    doc = _bancada()
    regra = re.search(
        r"\.quadro-corpo:has\(\.estado\.portao \.laranja\)[^{]*\{([^}]*)\}", doc)
    assert regra is not None, (
        "a folha da aba perdeu a regra que apaga o interruptor a partir da "
        "linha do portão — sem ela a razão aparece e o interruptor continua "
        "com cara de clicável.")
    assert "not-allowed" in regra.group(1), regra.group(1)
    assert 'data-campo="modo-portao"' in doc, (
        "a linha do portão perdeu o endereço; sem ele o pacote não tem onde "
        "escrever a razão nem como apagar o interruptor.")


# ---------------------------------------------------------------------------
# [02] AS TRÊS REGIÕES DO TOUCHPAD — ficam, com a marca
# ---------------------------------------------------------------------------
def test_a_marca_esta_nas_tres_regioes_do_touchpad_e_so_nelas():
    """A marca acompanha as três linhas do touchpad, e nenhuma outra.

    AS TRÊS SÃO LIDAS DO PRODUTO (`input_actions.REGIOES_DO_TOUCHPAD`), nunca
    digitadas: uma lista à mão aqui envelheceria no dia em que uma quarta
    região nascesse, e a régua daria verde sobre a linha nova sem marca.

    SEIS OCORRÊNCIAS E NÃO TRÊS: a primeira coluna é a MESMA nas duas telas de
    botões (Definições e Remapeamento) — é a segunda metade do pedido dela de
    28/08, e o que muda de uma para a outra é a segunda coluna.

    A MORDIDA: tire o `+ MARCA_DO_TOUCHPAD` de uma das três linhas de `BOTOES`
    — este caso reprova com a conta errada.
    """
    from hefesto_dualsense4unix.app.actions.input_actions import REGIOES_DO_TOUCHPAD

    doc = _bancada()
    quantas = doc.count('class="marca-nao-dispara"')
    assert quantas == 2 * len(REGIOES_DO_TOUCHPAD), (
        f"achei {quantas} marca(s) e as duas telas de botões pedem "
        f"{2 * len(REGIOES_DO_TOUCHPAD)} — uma por região do touchpad em cada.")
    # E ELA NÃO PROMETE: a marca diz que a região NÃO dispara. Uma marca que
    # dissesse o contrário seria pior que nenhuma.
    assert "não dispara" in doc


def test_a_marca_nao_encosta_em_linha_que_dispara():
    """Nenhuma das outras dezoito linhas leva a marca.

    A régua parte a tabela em linhas e confere botão a botão — marcar o Círculo
    seria a tela mentindo pelo outro lado.

    A MORDIDA: ponha a marca numa linha qualquer de `BOTOES` — este caso a
    nomeia.
    """
    from hefesto_dualsense4unix.app.actions.input_actions import REGIOES_DO_TOUCHPAD
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    doc = _bancada()
    for linha in re.findall(r"<tr>(.*?)</tr>", doc, re.S):
        alvo = re.search(r'data-linha="([^"]+)"', linha)
        if alvo is None or alvo.group(1) not in acoes.BOTOES:
            continue
        marcada = "marca-nao-dispara" in linha
        devia = alvo.group(1) in REGIOES_DO_TOUCHPAD
        assert marcada == devia, (
            f"a linha de {alvo.group(1)} {'tem' if marcada else 'não tem'} a "
            f"marca, e devia ser o contrário.")


# ---------------------------------------------------------------------------
# [03] O BOTÃO PS — fica fora, e a razão vira dica
# ---------------------------------------------------------------------------
def test_a_dica_da_tela_de_botoes_diz_por_que_o_ps_fica_fora():
    """A tabela para de parecer incompleta sem custar uma linha de tela.

    O `ps` CONTINUA FORA — é a decisão —, e quem confere isso é a lista do
    produto: `acoes_de_botao.BOTOES`. A régua não digita "ps não está lá"; ela
    pergunta ao dono.

    A MORDIDA: tire o parágrafo do PS de `D_DEFINICOES` — este caso reprova
    dizendo que a razão sumiu.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    assert "ps" not in acoes.BOTOES, (
        "o `ps` entrou na lista das linhas: a decisão do PO é que ele fica "
        "FORA, porque dar-lhe uma tecla o faria digitar sem parar de abrir a "
        "Steam.")
    doc = _bancada()
    dica = re.search(
        r'<span class="tn-tit">Definições Controle e Mouse</span>\s*'
        r'<span class="ajuda">\?<span class="dica"[^>]*>(.*?)</span></span>',
        doc, re.S)
    assert dica is not None, "não achei a dica da tela de Definições na bancada"
    texto = dica.group(1)
    assert "botão PS" in texto and "Steam" in texto, (
        f"a dica não diz por que o PS fica fora: {texto!r}")


# ---------------------------------------------------------------------------
# [04] A TIRA SOB A TABELA — e o defeito §3-1 dito
# ---------------------------------------------------------------------------
def test_o_aviso_nomeia_o_que_o_guardar_vai_substituir(aba, monkeypatch):
    """A tira nomeia os atalhos que `apply_button_actions` vai reescrever.

    **ELA MEDE O PRODUTO E A TELA JUNTOS, e é o que a impede de virar lápide.**
    Quem decide o que se perde é `acoes_de_botao.resolver()` — a MESMA chamada
    que `profiles/manager.apply_button_actions` faz. A régua pergunta a ele o
    que sobrevive e cobra que a tela nomeie o resto.

    NO DIA EM QUE `resolver()` HERDAR `key_bindings` nada se perde, a lista fica
    vazia e a tela NÃO PODE ameaçar — a segunda asserção cobra esse lado. Assim
    o caso continua verde depois da cura, em vez de reprovar quem a fez.

    A MORDIDA: faça `atalhos_que_param_de_valer` devolver `[]` sempre — este
    caso reprova nomeando o atalho que a tela deixou de citar.
    """
    from hefesto_dualsense4unix.app.actions.input_actions import humanize_button
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    escolhas = {"cross": "KEY_ESC"}
    atalhos = {"r1": ("KEY_LEFTCTRL", "KEY_W"), "l1": ("KEY_F5",)}
    perfil = {"key_bindings": {b: list(v) for b, v in atalhos.items()},
              "button_actions": escolhas}

    _do_mouse, do_teclado, _sem = acoes.resolver(escolhas)
    perdidos = [b for b, toks in atalhos.items() if do_teclado.get(b) != toks]

    aviso = _carga(aba, NO_DESKTOP, perfil, monkeypatch)["aviso-da-tabela"]
    for botao in perdidos:
        assert humanize_button(botao) in aviso, (
            f"o produto vai apagar o atalho de {botao!r} e a tira não o nomeia:\n"
            f"{aviso!r}")
    if not perdidos:
        assert "substitui o conjunto inteiro" not in aviso, (
            "nada se perde e a tela continua ameaçando — a cura de "
            "`resolver()` chegou e esta frase ficou para trás.")


def test_o_que_o_nada_nao_cala_e_dito_e_o_produto_e_quem_decide(aba, monkeypatch):
    """A tela nomeia os botões que "— Nada —" não cala — e o DEVICE é o juiz.

    O DEFEITO, medido em 04/09/2026: `set_button_actions` reconstrói
    `_mapa_dpad` e `_mapa_tap` do DE FÁBRICA menos `do_mouse`, e um botão em
    `— Nada —` nunca entra em `do_mouse` — logo ele não é subtraído e continua
    emitindo. São seis das 21 linhas.

    ELA CHAMA O MÉTODO DE VERDADE, sobre um objeto nu: `set_button_actions` só
    escreve `self._mapa_*`, não toca device nenhum e não precisa de `uinput`.
    É a diferença entre medir o produto e medir uma cópia da regra dele.

    E ELA SOBREVIVE À CURA: se o dia em que o device aprender a calar chegar, os
    mapas ficam vazios, a lista fica vazia, e a segunda asserção cobra que a
    tela pare de avisar.

    A MORDIDA: faça `_mapas_que_sobrevivem_ao_nada` devolver `frozenset()` —
    este caso reprova nomeando o botão que continua digitando e a tela calou.
    """
    from hefesto_dualsense4unix.app.actions.input_actions import humanize_button
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes
    from hefesto_dualsense4unix.integrations.uinput_mouse import UinputMouseDevice

    calados = {"dpad_up": acoes.TOKEN_NADA, "circle": acoes.TOKEN_NADA,
               "options": acoes.TOKEN_NADA}
    do_mouse, do_teclado, _sem = acoes.resolver(calados)

    device = types.SimpleNamespace()
    UinputMouseDevice.set_button_actions(device, do_mouse)
    ainda_falam = sorted(
        b for b in calados
        if b in device._mapa_botoes or b in device._mapa_dpad
        or b in device._mapa_tap or b in do_teclado)

    aviso = _carga(aba, NO_DESKTOP, {"button_actions": calados},
                   monkeypatch)["aviso-da-tabela"]
    # A FRASE CERTA, e não qualquer frase: um nome que aparecesse só na linha
    # de "não acendem nada" diria o CONTRÁRIO — que o botão calou. A régua
    # recorta o `<div>` que fala de não-calar e cobra ali.
    dita = next((x for x in re.findall(r"<div>(.*?)</div>", aviso)
                 if "ainda não cala" in x), "")
    for botao in ainda_falam:
        assert humanize_button(botao) in dita, (
            f"{botao} continua emitindo com a tela em “— Nada —” e a tira não "
            f"o nomeia na frase que fala disso:\n{aviso!r}")
    if not ainda_falam:
        assert not dita, (
            "o device passou a calar de verdade e a tela continua avisando que "
            "não cala.")
    else:
        # E O CONTRÁRIO TAMBÉM: quem continua falando não pode aparecer na
        # frase que promete silêncio.
        calou = next((x for x in re.findall(r"<div>(.*?)</div>", aviso)
                      if "Não acendem nada hoje" in x), "")
        for botao in ainda_falam:
            assert humanize_button(botao) not in calou, (
                f"{botao} continua emitindo e a tira o põe entre os que não "
                f"acendem nada:\n{aviso!r}")


def test_a_confirmacao_do_voltar_ao_padrao_usa_a_palavra_atalhos():
    """O defeito §3-2 dito na tela: o botão apaga atalhos e a pergunta dizia outra coisa.

    O ATO NÃO MUDOU — zerar os dois campos continua sendo o certo, porque zerar
    só um deixaria a tabela metade de fábrica. O que estava errado era a
    PERGUNTA: ela falava só das "21 linhas de o que cada botão faz" e nunca
    usava a palavra atalhos, sendo que apaga `key_bindings` inteiro, direto no
    disco e sem desfazer.

    A MORDIDA: tire a frase dos atalhos do `confirma` de `TELA_DEFINICOES` —
    este caso reprova.
    """
    doc = _bancada()
    tela = re.search(r'<div class="tela-nova" id="definicoes-mouse">(.*?)\n</div>',
                     doc, re.S)
    assert tela is not None, "não achei a tela de Definições na bancada"
    confirma = re.search(r'<div class="confirma">\s*<span>(.*?)</span>',
                         tela.group(1), re.S)
    assert confirma is not None, "a tela de Definições perdeu a confirmação"
    frase = confirma.group(1)
    assert "atalhos de teclado" in frase, (
        "a confirmação do “Voltar ao padrão” apaga os atalhos do perfil e não "
        f"diz a palavra: {frase!r}")


# ---------------------------------------------------------------------------
# [05] O CUSTO DE DESLIGAR O TECLADO
# ---------------------------------------------------------------------------
def test_o_custo_do_teclado_e_o_que_a_gtk_diz():
    """A frase desta aba não pode divergir do toast da janela antiga.

    A DUPLICAÇÃO É DECLARADA e não evitável sem tocar arquivo de outra frente:
    o original é um literal DENTRO de
    `emulation_actions.on_keyboard_toggle_set`. Esta régua lê o FONTE da GTK e
    reprova no dia em que a lista de lá mudar — que é o que impede as duas
    janelas do mesmo produto de dizerem coisas diferentes.

    A MORDIDA: troque uma palavra em `O_QUE_SAI_COM_O_TECLADO` — este caso
    reprova mostrando as duas.
    """
    from pacotes import a06_navegacao

    fonte = (RAIZ / "src/hefesto_dualsense4unix/app/actions/emulation_actions.py"
             ).read_text(encoding="utf-8")
    # O toast quebra a frase em duas linhas de fonte; a comparação é feita sobre
    # o texto sem quebra, que é o que chega à tela dela nos dois lados.
    achatado = re.sub(r'"\s*\n\s*"', "", fonte)
    assert a06_navegacao.O_QUE_SAI_COM_O_TECLADO in achatado, (
        "o que esta aba diz que sai com o teclado não está mais escrito na "
        f"GTK: {a06_navegacao.O_QUE_SAI_COM_O_TECLADO!r}")


@pytest.mark.parametrize(
    ("bloco", "fala"),
    [({"enabled": False, "osk_disponivel": True}, True),
     ({"enabled": True, "osk_disponivel": True}, False),
     ({}, False)],
)
def test_a_linha_do_custo_e_tri_estado(aba, bloco, fala):
    """Ela só fala com o teclado DESATIVADO — e cala quando ninguém perguntou.

    O terceiro caso é o que separa esta linha de uma afirmação: sem o bloco
    `keyboard_emulation` no estado, ninguém perguntou ao Hefesto, e a tela não
    inventa que o teclado está desligado.

    A MORDIDA: troque o `if not isinstance(ligado, bool) or ligado` por
    `if ligado` — o terceiro caso reprova.
    """
    saiu = aba._o_custo_de_desligar_o_teclado(bloco)
    if fala:
        assert aba.O_QUE_SAI_COM_O_TECLADO in saiu
    else:
        assert saiu == aba.NADA_A_DIZER, saiu


# ---------------------------------------------------------------------------
# OS DOIS GESTOS QUE GRAVAM — e o recibo do que eles apagam
# ---------------------------------------------------------------------------
class _PerfilDeMentira:
    """O mínimo de um `Profile` que os dois gestos tocam.

    Instanciar o modelo do pydantic exigiria um `match` válido, e a régua
    passaria a medir o esquema em vez do botão — mesma disciplina de
    `test_a_06_nao_manda_para_o_vazio.py`.
    """

    def __init__(self, nome, button_actions=None, key_bindings=None):
        self.name = nome
        self.button_actions = button_actions
        self.key_bindings = key_bindings

    def model_copy(self, *, update):
        novo = _PerfilDeMentira(self.name, self.button_actions, self.key_bindings)
        for k, v in update.items():
            setattr(novo, k, v)
        return novo


class _PonteMuda:
    """Uma ponte que aceita tudo e não fala com daemon nenhum."""

    def __getattr__(self, _nome):
        return lambda *a, **k: True


@pytest.fixture
def disco(monkeypatch):
    """Um disco de mentira: guarda o que o gesto mandou gravar."""
    from hefesto_dualsense4unix.profiles import loader

    gravados: list[_PerfilDeMentira] = []
    estado: dict[str, _PerfilDeMentira] = {}
    monkeypatch.setattr(loader, "load_profile", lambda n: estado[n], raising=False)
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **_: gravados.append(prof), raising=False)
    return estado, gravados


def test_o_voltar_ao_padrao_da_recibo_do_que_apagou(aba, disco):
    """Quem apaga diz o que apagou — pelo canal de SUCESSO da D-01.

    ATÉ 04/09/2026 ele zerava os `key_bindings` que ela escreveu na janela
    antiga e voltava sem uma palavra: o piloto imprimia `aplicado` no terminal
    de quem lançou a janela, e quem clica não lê terminal.

    A MORDIDA: faça o gesto voltar `None` sempre — este caso reprova dizendo
    que o botão voltou a apagar calado.
    """
    import pacotes
    from hefesto_dualsense4unix.app.actions.input_actions import humanize_button

    estado, gravados = disco
    estado["regua"] = _PerfilDeMentira(
        "regua", key_bindings={"r1": ["KEY_LEFTCTRL", "KEY_W"]})
    ctx = pacotes.Contexto(state=NO_DESKTOP, mesa=MESA, conectados=[FALSO],
                           estados={})

    saiu = aba.padrao_definicoes(ctx, {}, _PonteMuda())
    assert len(gravados) == 1 and gravados[0].key_bindings is None
    assert isinstance(saiu, dict) and saiu.get("recado"), (
        f"o gesto apagou um atalho e não devolveu recado nenhum: {saiu!r}")
    assert humanize_button("r1") in saiu["recado"], saiu["recado"]


def test_o_voltar_ao_padrao_sem_atalhos_nao_inventa_recibo(aba, disco):
    """Sem atalho guardado não há o que dizer — e o piloto diz "Pronto." sozinho.

    Um recibo que nomeasse zero atalhos seria ruído com cara de dado, que é o
    mesmo defeito do travessão solto na linha de estado.
    """
    import pacotes

    estado, gravados = disco
    estado["regua"] = _PerfilDeMentira("regua", button_actions={"cross": "KEY_ESC"})
    ctx = pacotes.Contexto(state=NO_DESKTOP, mesa=MESA, conectados=[FALSO],
                           estados={})
    assert aba.padrao_definicoes(ctx, {}, _PonteMuda()) is None
    assert len(gravados) == 1


def test_o_guardar_nomeia_os_atalhos_que_param_de_valer(aba, disco):
    """Ele GRAVA e diz o que este mesmo clique fez parar de valer.

    É a metade dita do defeito §3-1, no instante em que ele acontece: o perfil
    continua MOSTRANDO os dois campos, como se os dois valessem, e o efeito de
    `key_bindings` morre na próxima ativação.

    A MORDIDA: tire o ramo `if perdidos` do `guardar_definicoes` — este caso
    reprova dizendo que o gesto gravou e calou.
    """
    import pacotes
    from hefesto_dualsense4unix.app.actions.input_actions import humanize_button
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    estado, gravados = disco
    estado["regua"] = _PerfilDeMentira(
        "regua", key_bindings={"r1": ["KEY_LEFTCTRL", "KEY_W"]})
    ctx = pacotes.Contexto(state=NO_DESKTOP, mesa=MESA, conectados=[FALSO],
                           estados={})
    forma = {b: acoes.rotulo(a) for b, a in acoes.padrao().items()}
    forma["square"] = "Enter"

    with pytest.raises(RuntimeError) as caiu:
        aba.guardar_definicoes(ctx, {"forma": forma}, _PonteMuda())
    assert len(gravados) == 1, "gravou o quê? o recado não pode custar a gravação"
    assert humanize_button("r1") in str(caiu.value), str(caiu.value)


# ---------------------------------------------------------------------------
# A TIRA NÃO MENTE POR EXCESSO
# ---------------------------------------------------------------------------
def test_a_tira_so_diz_o_que_o_perfil_de_hoje_justifica(aba, monkeypatch):
    """Com um perfil de fábrica ela não fala de atalhos nem de linhas caladas.

    A decisão do PO é explícita: *"a tira só ocupa espaço nos perfis em que há
    mesmo algo a perder"*. O que sobra num perfil de fábrica é a colisão do R3,
    que é verdade sempre — e é a primeira das três verdades que a tabela
    escondia.

    A MORDIDA: faça as três frases nascerem sem condição — este caso reprova
    nomeando a que sobrou.
    """
    aviso = _carga(aba, NO_DESKTOP, {}, monkeypatch)["aviso-da-tabela"]
    assert "Dois donos" in aviso, aviso
    assert "atalhos que esta lista não diz" not in aviso, aviso
    assert "Não acendem nada hoje" not in aviso, aviso
    assert "ainda não cala" not in aviso, aviso
