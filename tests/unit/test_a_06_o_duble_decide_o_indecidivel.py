#!/usr/bin/env python3
"""A RÉGUA QUE DECIDE: com um DUBLÊ, nenhum campo da 06 pode ficar indecidível.

O BURACO QUE ELA FECHA, medido em 02/09/2026. A `--prova-de-mockup` classifica
cada campo da tela em três montes:

    PRODUTO      o valor mudou em relação ao cravado no arquivo publicado
    MOCKUP       igual ao cravado, e nenhum pacote declara este endereço
    INDECIDIVEL  igual ao cravado, e o pacote declara EXATAMENTE esse valor

A aba Navegação era **28 indecidíveis de 29 campos** — de longe a maior
concentração da casa. INDECIDÍVEL não é defeito: é o limite honesto de um
instrumento que lê a TELA. Se o desenho cravou `6` e o daemon dela diz `6`,
olhar a tela não separa *"pintou o valor certo"* de *"nunca pintou"*.

**A cura é fazer o valor MUDAR.** Esta régua troca o daemon por um DUBLÊ que
discorda do desenho em TODOS os 29 endereços — três controles em vez de dois, o
primário no segundo lugar, a velocidade do cursor em 11, o teclado desligado e
um `button_actions` que troca as vinte e uma linhas — e então pergunta ao
classificador da casa, sem abrir janela:

    sob este dublê, algum campo ainda cai em INDECIDIVEL?

Um `INDECIDIVEL` aqui é a régua confessando que aquele endereço continua sem
decisão — e nomeia qual. Zero é a única saída aceitável.

O QUE ESTA RÉGUA **NÃO** PROVA, e ela diz: que a tela acompanhou. Isso é do
piloto, e foi medido no mesmo dia com o mesmo dublê, pela
`--prova-de-mockup` com a fila reduzida à 06:

    mesa dela (2 controles)   produto  1 · mockup 0 · indecidível 28
    DUBLÊ (3 sintéticos)      produto 29 · mockup 0 · indecidível  0

Aqui fica a metade que roda no CI, sem GTK, sem display e sem daemon.

A MORDIDA: faça o dublê concordar com o desenho em qualquer campo — troque
`speed` para 6, ou tire o `button_actions` — e a régua nomeia o endereço que
voltou a ser indecidível.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo

#: TRÊS CONTROLES SINTÉTICOS, na faixa da casa — há dois portões de anonimato
#: nesta árvore e um endereço mascarado ainda carrega o OUI do aparelho dela.
#:
#: O `player_slot` NÃO É ENFEITE: é ele que ordena a mesa
#: (`mesa_viva._por_numero_de_identidade`), e sem ele a régua dependeria da
#: ordem de inserção — o dia em que a ordem mudasse, o `p1` cairia sobre o
#: mesmo valor que o desenho crava e o campo voltaria a INDECIDIVEL sem que
#: ninguém tivesse mexido no pacote.
#:
#: A MESA DO DUBLÊ DISCORDA DO DESENHO DE PROPÓSITO, campo a campo:
#:   · são TRÊS (o desenho crava "2 controles:" e "1 USB · 1 BT");
#:   · o `p1` está no RÁDIO e NÃO navega (o desenho crava "USB • Navega o PC");
#:   · o `p2` está no CABO e NAVEGA (o desenho crava "BT • Só a janela").
CONTROLES = [
    {"uniq": "aa:bb:cc:00:00:01", "connected": True, "transport": "bt",
     "player_slot": 1, "is_primary": False},
    {"uniq": "02:fe:00:00:00:02", "connected": True, "transport": "usb",
     "player_slot": 2, "is_primary": True},
    {"uniq": "e8:47:3a:00:00:03", "connected": True, "transport": "usb",
     "player_slot": 3, "is_primary": False},
]

#: O estado do daemon, escolhido para DISCORDAR do desenho em cada número:
#: o cursor vai a 11 (o desenho crava 6), a rolagem a 4 (crava 1) e o teclado
#: sai DESLIGADO (crava "Ligada — atalhos e teclado na tela").
ESTADO = {
    "active_profile": "Dublê da Navegação",
    "mouse_emulation": {"enabled": True, "speed": 11, "scroll_speed": 4,
                        "bloqueio": "", "despachando": True},
    "keyboard_emulation": {"enabled": False, "osk_disponivel": False},
    "controllers": CONTROLES,
}


def _button_actions() -> dict[str, str]:
    """Uma escolha DIFERENTE do de fábrica para cada uma das 21 linhas.

    O vocabulário é o do motor (`core.acoes_de_botao`), inteiro: as linhas que
    existem, o que cada uma faz de fábrica e a lista de opções saem de lá. Este
    dublê não digita rótulo nenhum — ele só escolhe, para cada botão, o
    primeiro token que NÃO é o de fábrica daquela linha.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    de_fabrica = acoes.padrao()
    fora: dict[str, str] = {}
    for botao in acoes.BOTOES:
        for token in acoes.ACOES:
            if token != de_fabrica.get(botao):
                fora[botao] = token
                break
    return fora


PERFIL = {"name": "Dublê da Navegação", "button_actions": _button_actions(),
          "key_bindings": {"l1": ["KEY_F11"]}}


@pytest.fixture
def sob_o_duble(monkeypatch):
    """`(cravados, declarados)` — o que o arquivo crava e o que o pacote emite.

    Os dois lados saem de quem já é dono deles: os cravados de
    `regua_do_mockup._campos_cravados` (o mesmo parser que a `--prova-de-mockup`
    usa) e os declarados de `regua_do_mockup._declarados_do_pacote` sobre a
    carga NORMALIZADA — isto é, exatamente o que iria para a tela naquele tique,
    cabeçalho incluído. Ler o código-fonte do pacote em vez da carga seria
    perguntar se o NOME do campo aparece, que é o erro que produziu o "77%".
    """
    import pacotes
    from pacotes import a06_navegacao, perfil

    from hefesto_dualsense4unix.interface import mesa_viva, onde, regua_do_mockup

    monkeypatch.setattr(perfil, "ativo", lambda nome: dict(PERFIL) if nome else {})

    mesa = mesa_viva.mesa_do_estado(ESTADO, {})
    ctx = pacotes.Contexto(state=ESTADO, mesa=mesa, conectados=CONTROLES, estados={})
    carga = pacotes.normalizar(a06_navegacao.pacote(ctx),
                               {str(c["uniq"]): c["pref"] for c in mesa})
    for chave, valor in pacotes.topo(ctx).items():
        carga["mesa"].setdefault(chave, valor)

    texto = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    return regua_do_mockup._campos_cravados(texto), \
        regua_do_mockup._declarados_do_pacote(carga)


def test_o_duble_nao_deixa_um_campo_indecidivel(sob_o_duble):
    """Nenhum dos 29 endereços pode concordar com o desenho sob este dublê.

    A tela dos `vivos` é o CRAVADO — isto é, a régua pergunta *"e se a pintura
    não tivesse acontecido?"*. Sob um dublê que discorda do desenho, todo campo
    tem de cair em `MOCKUP` com a nota de endereço morto; um `INDECIDIVEL` aqui
    quer dizer que o pacote declarou o MESMO valor que o desenho crava — e esse
    campo continua sem decisão na régua viva, para sempre.
    """
    from hefesto_dualsense4unix.interface import regua_do_mockup as r

    cravados, declarados = sob_o_duble
    vereditos = r._classificar(cravados, [c.valor for c in cravados], declarados)
    parados = [f"{v.campo.endereco} = {v.campo.valor!r}"
               for v in vereditos if v.classe == r.INDECIDIVEL]
    assert not parados, (
        "estes endereços da 06 concordam com o desenho ATÉ SOB O DUBLÊ, logo "
        "continuam indecidíveis na régua viva:\n  " + "\n  ".join(parados)
        + "\nOu o pacote não varia esse campo com o estado, ou o dublê acima "
          "escolheu por acaso o mesmo valor que o desenho crava — nos dois "
          "casos ler a tela não decide nada sobre ele.")


def test_o_duble_cobre_os_vinte_e_nove_enderecos(sob_o_duble):
    """Endereço sem dono nenhum é a outra metade — e não pode existir aqui.

    `MOCKUP` sem valor declarado é *"nenhum pacote declara este endereço"*, que
    é diferente de endereço morto: é campo órfão. A 06 não tem nenhum, e esta
    linha impede que ganhe um em silêncio.
    """
    from hefesto_dualsense4unix.interface import regua_do_mockup as r

    cravados, declarados = sob_o_duble
    vereditos = r._classificar(cravados, [c.valor for c in cravados], declarados)
    orfaos = [v.campo.endereco for v in vereditos if v.declarado is None]
    assert not orfaos, (
        f"{orfaos} existe(m) na página publicada e pacote nenhum os declara — "
        "a tela mostra o desenho e ninguém acusa.")
    assert len(cravados) == 29, (
        f"a página publicada tem {len(cravados)} endereços de campo; esta régua "
        "foi escrita sobre 29. Se o desenho mudou, confira se o dublê acima "
        "ainda discorda de TODOS eles antes de mexer neste número.")


def test_quando_a_tela_acompanha_tudo_vira_produto(sob_o_duble):
    """O outro lado da mesma moeda: se a pintura pousar, os 29 saem PRODUTO.

    Sem esta metade a régua acima passaria com um pacote que emitisse lixo: o
    que ela cobra é *diferente do desenho*, e lixo também é diferente. Aqui os
    `vivos` são o que o `escrever()` do bootstrap poria na tela para o valor
    declarado — a mesma tradução que a `--prova-de-mockup` usa —, e o veredito
    tem de ser PRODUTO em todos.
    """
    from hefesto_dualsense4unix.interface import regua_do_mockup as r

    cravados, declarados = sob_o_duble
    vivos = [r._como_a_tela_escreveria(
        declarados.get((c.dono, c.chave), declarados.get(("", c.chave))))
        for c in cravados]
    vereditos = r._classificar(cravados, vivos, declarados)
    contas = r._contar(vereditos)
    assert contas == {r.PRODUTO: 29, r.MOCKUP: 0, r.INDECIDIVEL: 0}, (
        f"com a tela acompanhando o dublê a régua diz {contas}, e o esperado é "
        "29 PRODUTO. Um campo fora disso é o pacote emitindo o valor do desenho.")


#: A REGRA DO `escrever()` PARA `data-hef-alvo="valor"`, e ela é do PILOTO:
#: um `<select>` só aceita o texto exato de uma `<option>` — fora disso a
#: pintura devolve `0` **em silêncio** (`hefesto_vivo.BOOTSTRAP`, ramo
#: `alvo === 'valor'`). Um valor que não casa é um campo que nunca anda, sem uma
#: linha de erro em lugar nenhum.
_SELECT = r'<select[^>]*data-campo="{}"[^>]*>(.*?)</select>'


def test_todo_valor_do_duble_existe_como_opcao(sob_o_duble):
    """As 21 escolhas do dublê têm de ser oferecidas pela lista daquela linha.

    O teste irmão (`test_a_06_nao_manda_para_o_vazio`) cobre isto para o
    **de fábrica**; aqui o alvo são as opções que só aparecem quando o perfil
    dela diverge — que é justamente o caso que nunca foi exercitado, e o que
    faria um campo ficar parado para sempre sem ninguém ver.
    """
    import onde

    doc = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    cravados, declarados = sob_o_duble
    conferidos = 0
    for campo in cravados:
        if campo.alvo != "valor":
            continue
        valor = declarados.get((campo.dono, campo.chave),
                               declarados.get(("", campo.chave)))
        bloco = re.search(_SELECT.format(re.escape(campo.chave)), doc, re.S)
        assert bloco, f"{campo.endereco}: sem `<select>` com esse endereço"
        opcoes = set(re.findall(r"<option[^>]*>(.*?)</option>", bloco.group(1)))
        assert str(valor) in opcoes, (
            f"{campo.endereco}: o dublê manda {valor!r} e a lista do desenho "
            "não oferece essa opção — a pintura se calaria e o campo ficaria "
            "parado para sempre.")
        conferidos += 1
    assert conferidos == 22, (
        f"conferi {conferidos} listas e a aba tem 22 (as 21 linhas de botão "
        "mais a 'Função do teclado') — se o número caiu, um `<select>` perdeu "
        "o endereço e saiu da conferência sem reprovar nada.")
