#!/usr/bin/env python3
"""A RÉGUA QUE DECIDE: com um DUBLÊ, nenhum campo da 06 pode ficar indecidível.

O BURACO QUE ELA FECHA, medido em 02/09/2026. A `--prova-de-mockup` classifica
cada campo da tela em três montes:

    PRODUTO      o valor mudou em relação ao cravado no arquivo publicado
    MOCKUP       igual ao cravado, e nenhum pacote declara este endereço
    INDECIDIVEL  igual ao cravado, e o pacote declara EXATAMENTE esse valor

A aba Navegação era **28 indecidíveis de 29 campos** — de longe a maior
concentração da casa. INDECIDÍVEL não é defeito: é o limite honesto de um
instrumento que lê a TELA. Se o desenho cravou `6` e o daemon do usuário diz `6`,
olhar a tela não separa *"pintou o valor certo"* de *"nunca pintou"*.

**A cura é fazer o valor MUDAR.** Esta régua troca o daemon por um DUBLÊ que
discorda do desenho em TODOS os endereços — quatro controles em vez de dois,
cada um com uma cor de plástico que não é a do desenho, o primário no segundo
lugar, a velocidade do cursor em 11, o teclado desligado e um `button_actions`
que troca as vinte e uma linhas — e então pergunta ao classificador da casa, sem
abrir janela:

    sob este dublê, algum campo ainda cai em INDECIDIVEL?

Um `INDECIDIVEL` aqui é a régua confessando que aquele endereço continua sem
decisão — e nomeia qual. Zero é a única saída aceitável.

O QUE ESTA RÉGUA **NÃO** PROVA, e ela diz: que a tela acompanhou. Isso é do
piloto, e foi medido em 02/09 com o mesmo dublê, pela `--prova-de-mockup` com a
fila reduzida à 06:

    bancada (2 controles)   produto  1 · mockup 0 · indecidível 28

Aqui fica a metade que roda no CI, sem GTK, sem display e sem daemon.

A PÁGINA CRESCE, E OS NÚMEROS DESTE ARQUIVO SÃO LIDOS DO USUÁRIO — 29, depois 38,
depois 43 com a publicação das dez. As três asserções que digitavam o número
caíram no mesmo dia (03/09/2026) e viraram piso + comparação de conjuntos. A onda
IDENTIDADE-VEM-DE-CIMA acrescentou NOVE à `06-navegacao` publicada: os quatro
`plastico` da mesa, os dois `identidade` dos cartões, os dois `quem-navega` das
dicas e o `fita-chips` do topo. **Antes de mexer no número foi conferido o que a
mensagem da régua manda conferir** — que o dublê discorda de TODOS, um a um: a
saída campo a campo está no dump que gerou esta correção, e os dois casos que
NÃO discordavam viraram o quarto controle e as quatro cores lidas.

NO DESENHO DO TODO (15/10/2026) os cartões por controle, a troca, as teclas e as definições
saíram da página: o dublê continua discordando em tudo o que a tela ainda pinta (as 22 linhas
de botão, a Função do teclado, as duas barras, o tipo de navegação, quem navega, o perfil de
point and click e os gestos do PS). O cadeado da moldura
(O-BOTAO-QUE-TRAVA-A-NAVEGACAO-DOS-CONTROLES-01, 26/10/2026) crava `navegacao-travada = false`, e
o dublê o discorda com a Interna desligada (a `interna_ligada` que o cadeado escreve). O «Na
Steam» só tem uma escolha com dono (o Big Picture), e por isso é o único endereço que nenhum dublê
consegue mover (`SEM_VARIACAO`).

A MORDIDA: faça o dublê concordar com o desenho em qualquer campo — troque `speed` para 6, ligue
a `interna_ligada`, tire o `button_actions`, ou esvazie `CORES_LIDAS` — e a régua nomeia o
endereço que voltou a ser indecidível.
"""
from __future__ import annotations

import pathlib
import re
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "06-navegacao.html"

CONTROLES = [
    {"uniq": "aa:bb:cc:00:00:01", "connected": True, "transport": "bt",
     "player_slot": 2, "is_primary": False},
    {"uniq": "02:fe:00:00:00:02", "connected": True, "transport": "usb",
     "player_slot": 3, "is_primary": True},
    {"uniq": "e8:47:3a:00:00:03", "connected": True, "transport": "usb",
     "player_slot": 4, "is_primary": False},
    {"uniq": "aa:bb:cc:00:00:04", "connected": True, "transport": "usb",
     "player_slot": 5, "is_primary": False},
]


class _CorLida:
    """O que `integrations.cor_do_plastico` devolve: um código e um nome.

    `mesa_viva.mesa_do_estado` lê os dois por `getattr`, e é do CÓDIGO que sai o
    `colorway` — a tradução é do CSV dela (`mesa_viva.CORES`), nunca digitada
    aqui. Por isso o dublê declara o código, e não o slug.
    """

    def __init__(self, codigo: str, nome: str) -> None:
        self.codigo = codigo
        self.nome = nome


CORES_LIDAS = {
    "aa:bb:cc:00:00:01": _CorLida("00", "White"),
    "02:fe:00:00:00:02": _CorLida("04", "Galactic Purple"),
    "e8:47:3a:00:00:03": _CorLida("09", "Cobalt Blue"),
    "aa:bb:cc:00:00:04": _CorLida("07", "Volcanic Red"),
}

ESTADO = {
    "active_profile": "Dublê da Navegação",
    "mouse_emulation": {"enabled": True, "speed": 11, "scroll_speed": 4,
                        "bloqueio": "", "despachando": True},
    "keyboard_emulation": {"enabled": False, "osk_disponivel": False},
    "controllers": CONTROLES,
    "navegacao": {"interna_ligada": False, "tipo": "computador", "foco": False,
                  "big_picture": {"ligado": True, "agindo": False, "quem_le": "hefesto"}},
    "freestyle_ligado": True,
    "paused": True,
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
        oferece = [acoes.token_do_rotulo(r) for _grupo, rotulos in acoes.por_grupo(botao)
                   for r in rotulos]
        for token in oferece:
            if token != de_fabrica.get(botao):
                fora[botao] = token
                break
    return fora


PERFIL = {"name": "Dublê da Navegação", "button_actions": _button_actions()}

SEM_VARIACAO = {"na-steam"}


def _gestos_da_maquina() -> dict[str, dict[str, Any]]:
    """Um script para CADA gesto — 02/10/2026, conferência final dos gestos.

    Desde 16/10/2026 (AS-TELAS-QUE-ELA-PEDIU-EM-16-10-01, N8) a tabela tem também os gestos
    novos e o botão de tirar: o dublê tira os cinco de fábrica com combo e declara os cinco
    novos, e assim toda linha (`vale-`) e todo botão do «+ Gesto» (`livre-`) discordam do
    desenho.
    """
    from hefesto_dualsense4unix.core.acoes_do_gesto import (
        GESTO_DO_PS,
        GESTOS,
        SCRIPT,
        TODOS_OS_GESTOS,
    )

    return {g: {"faz": SCRIPT, "script": f"/opt/duble/gesto-{n}.sh",
                **({"removido": True} if g in GESTOS and g != GESTO_DO_PS else {})}
            for n, g in enumerate(TODOS_OS_GESTOS, 1)}


class _Maquina(dict):
    """O `maquina.json` do dublê: os gestos como dicionário e o computador como atributo."""

    computador = SimpleNamespace(global_=SimpleNamespace(
        mouse=SimpleNamespace(point_and_click="molde:visual_novel")))


def _a_maquina_do_duble() -> _Maquina:
    return _Maquina(gestos=_gestos_da_maquina())


def _no_mundo_de(monkeypatch, publicado: bool):
    """`(cravados, declarados)` NA PÁGINA QUE ESTIVER CARREGADA."""
    import pacotes
    from pacotes import a06_navegacao, perfil

    from hefesto_dualsense4unix.interface import mesa_viva, onde, regua_do_mockup

    monkeypatch.setattr(perfil, "ativo", lambda nome: dict(PERFIL) if nome else {})
    monkeypatch.setattr(a06_navegacao, "_a_maquina", _a_maquina_do_duble)
    monkeypatch.setattr(
        a06_navegacao, "_o_que_a_pagina_oferece",
        lambda: frozenset(_opcoes_da_pagina(publicado, "teclado-estado") or ()))

    mesa = mesa_viva.mesa_do_estado(ESTADO, CORES_LIDAS)
    ctx = pacotes.Contexto(state=ESTADO, mesa=mesa, conectados=CONTROLES, estados={})
    carga = pacotes.normalizar(a06_navegacao.pacote(ctx),
                               {str(c["uniq"]): c["pref"] for c in mesa})
    for chave, valor in pacotes.topo(ctx).items():
        carga["mesa"].setdefault(chave, valor)

    texto = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    return regua_do_mockup._campos_cravados(texto), \
        regua_do_mockup._declarados_do_pacote(carga)


def _cravados_que_afirmam(cravados):
    """Só os campos sobre os quais o desenho DIZ alguma coisa."""
    return [c for c in cravados if str(c.valor).strip()]


@pytest.fixture
def sob_o_duble(monkeypatch):
    """O mundo de HOJE: a página que o piloto carrega (`publicado=True`)."""
    cravados, declarados = _no_mundo_de(monkeypatch, publicado=True)
    return _cravados_que_afirmam(cravados), declarados


def test_o_duble_nao_deixa_um_campo_indecidivel(sob_o_duble):
    """Nenhum endereço que o desenho AFIRMA pode concordar com ele sob o dublê."""
    from hefesto_dualsense4unix.interface import regua_do_mockup as r

    cravados, declarados = sob_o_duble
    vereditos = r._classificar(cravados, [c.valor for c in cravados], declarados)
    parados = [f"{v.campo.endereco} = {v.campo.valor!r}"
               for v in vereditos
               if v.classe == r.INDECIDIVEL and v.campo.chave not in SEM_VARIACAO]
    assert not parados, (
        "estes endereços da 06 concordam com o desenho ATÉ SOB O DUBLÊ, logo "
        "continuam indecidíveis na régua viva:\n  " + "\n  ".join(parados)
        + "\nOu o pacote não varia esse campo com o estado, ou o dublê acima "
          "escolheu por acaso o mesmo valor que o desenho crava — nos dois "
          "casos ler a tela não decide nada sobre ele.")


_SELECT = r'<select[^>]*data-campo="{}"[^>]*>(.*?)</select>'

OS_DOIS_MUNDOS = [
    pytest.param(True, id="a-pagina-publicada-de-hoje"),
    pytest.param(False, id="a-bancada-do-dia-da-publicacao"),
]


def _opcoes_da_pagina(publicado: bool, chave: str) -> set[str] | None:
    """As `<option>` daquele `<select>`, na bancada ou no publicado."""
    import onde

    doc = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    bloco = re.search(_SELECT.format(re.escape(chave)), doc, re.S)
    if not bloco:
        return None
    textos = set(re.findall(r"<option[^>]*>(.*?)</option>", bloco.group(1)))
    return textos | set(re.findall(r'<option[^>]*\svalue="([^"]*)"', bloco.group(1)))


_TRILHO = r'<input[^>]*type="range"[^>]*data-campo="{}"[^>]*>'


_TEXTO = r'<input[^>]*type="text"[^>]*data-campo="{}"[^>]*>'


def _e_campo_de_texto(publicado: bool, chave: str) -> bool:
    """A página tem um `<input type=text>` com esse endereço?"""
    import onde

    doc = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    return re.search(_TEXTO.format(re.escape(chave)), doc) is not None


def _faixa_da_pagina(publicado: bool, chave: str) -> tuple[int, int] | None:
    """O `min`/`max` daquele `<input type=range>`, ou ``None`` se não é barra."""
    import onde

    doc = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    bloco = re.search(_TRILHO.format(re.escape(chave)), doc)
    if not bloco:
        return None
    tag = bloco.group(0)
    minimo = re.search(r'\bmin="(-?\d+)"', tag)
    maximo = re.search(r'\bmax="(-?\d+)"', tag)
    if not minimo or not maximo:
        return None
    return int(minimo.group(1)), int(maximo.group(1))


@pytest.mark.parametrize("publicado", OS_DOIS_MUNDOS)
def test_todo_valor_do_duble_existe_como_opcao(monkeypatch, publicado):
    """As 22 escolhas do dublê têm de ser oferecidas pela lista daquela linha."""
    cravados, declarados = _no_mundo_de(monkeypatch, publicado)
    onde_estou = "publicada" if publicado else "da bancada"
    conferidos: set[str] = set()
    for campo in cravados:
        if campo.alvo != "valor":
            continue
        valor = str(declarados.get((campo.dono, campo.chave),
                                   declarados.get(("", campo.chave))))
        faixa = _faixa_da_pagina(publicado, campo.chave)
        if faixa is not None:
            minimo, maximo = faixa
            assert minimo <= int(valor) <= maximo, (
                f"{campo.endereco}: na página {onde_estou} o dublê manda "
                f"{valor!r} e a barra vai de {minimo} a {maximo} — o navegador "
                "apara sem dizer nada, e a tela passa a AFIRMAR outro número.")
            conferidos.add(campo.endereco)
            continue
        if _e_campo_de_texto(publicado, campo.chave):
            conferidos.add(campo.endereco)
            continue
        oferece = _opcoes_da_pagina(publicado, campo.chave)
        assert oferece is not None, (
            f"{campo.endereco}: a página {onde_estou} não tem `<select>`, "
            "`<input type=range>` nem `<input type=text>` com esse endereço")
        if campo.chave.startswith("faz-"):
            script = declarados.get(("", "script-" + campo.chave[len("faz-"):]))
            if script is not None:
                oferece = set(oferece) | {str(script)}
        assert valor in oferece, (
            f"{campo.endereco}: na página {onde_estou} o dublê manda {valor!r} "
            f"e a lista oferece {sorted(oferece)} — o `escrever()` devolveria 0 "
            "em silêncio, e o que ficaria na tela é a `<option selected>` que o "
            "desenho crava. O campo não para: ele passa a AFIRMAR o contrário.")
        conferidos.add(campo.endereco)
    import onde

    doc = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
    da_pagina = (set(re.findall(r'<select[^>]*data-campo="([^"]+)"', doc))
                 | set(re.findall(r'<input[^>]*type="range"[^>]*data-campo="([^"]+)"', doc)))
    conferidos_chaves = {e.split("·")[-1] for e in conferidos}
    assert da_pagina and da_pagina <= conferidos_chaves, (
        f"a página {onde_estou} tem seletores e barras que a conferência não viu: "
        f"{sorted(da_pagina - conferidos_chaves)} — um endereço perdeu a guarda contra lixo.")
    from hefesto_dualsense4unix.core.acoes_de_botao import BOTOES

    assert sum(1 for c in conferidos_chaves if c.startswith("acao-")) == len(BOTOES), (
        f"a página {onde_estou} perdeu uma das {len(BOTOES)} linhas de botão: um seletor sem "
        "endereço sai da conferência sem reprovar nada.")


def test_os_sete_campos_de_texto_dizem_o_que_o_duble_diz(sob_o_duble):
    """Os 14 campos que NÃO são `<select>` têm de dizer o que o dublê mandou.

    O BURACO QUE ELA FECHA, medido em 02/09/2026 (corretivo). As duas metades
    acima reduzem ao mesmo predicado — *o declarado é diferente do cravado* — e
    LIXO também é diferente: com todo valor trocado por `'LIXO — ISTO NÃO É DADO'` as
    duas passam, com o mesmo veredito de sempre. Quem pegava lixo era só
    `test_todo_valor_do_duble_existe_como_opcao`, e só para os 22 `<select>`.

    ERAM SETE E SÃO CATORZE — 03/09/2026, número substituído, e o NOME desta
    função congelou o sete. Os outros sete chegaram com a onda
    IDENTIDADE-VEM-DE-CIMA e **todos ganharam linha aqui**, que é o que esta
    régua existe para exigir: `fita-chips`, `p1·identidade`, `p2·identidade`,
    `quem-navega` e os três endereços de `plastico` (os dois cartões e os dois
    lugares vazios compartilham a mesma lista de quatro cores). Subir o número
    sem escrever a guarda teria deixado sete campos sem defesa contra valor
    destruidor — o oposto do que a linha do número diz.

    O QUE ELA COBRA, e a distinção é a razão de ela existir: **o esperado sai do
    DUBLÊ, não do pacote**. Nada aqui chama `a06_navegacao` para descobrir a
    resposta — a contagem sai de `CONTROLES`, os números saem de `ESTADO`, o par
    via/papel de cada cartão sai do `transport`/`is_primary`, e a cor e o nome de
    cada modelo saem de `CORES_LIDAS` traduzidas pelos donos do dado
    (`mesa_viva.CORES`, que é o CSV dela, e `monta.cor_da_zona`, que lê o SVG).
    Uma régua que perguntasse ao pacote o que esperar do pacote é a forma de
    instrumento falso que esta casa mais achou.

    A MORDIDA: troque `speed` do dublê para 6, ou faça o pacote emitir qualquer outra coisa em
    `vel-cursor` — esta linha reprova nomeando o endereço.
    """
    import monta

    from hefesto_dualsense4unix.interface import mesa_viva

    cravados, declarados = sob_o_duble
    valor = {c.endereco: declarados.get((c.dono, c.chave),
                                        declarados.get(("", c.chave)))
             for c in cravados if c.alvo != "valor"}
    assert len(valor) >= 14, (
        f"a página caiu para {len(valor)} campos fora dos `<select>`, e esta "
        "régua confere 14 nominalmente. Se um endereço sumiu, ele perdeu a "
        "guarda contra valor destruidor — confira antes de baixar este piso.")

    rato = ESTADO["mouse_emulation"]

    assert "conta" not in valor and "conta-b" not in valor, (
        "o cabeçalho voltou a emitir o contador «N USB · N BT»: "
        f"{valor.get('conta')!r} {valor.get('conta-b')!r}")
    assert valor["perfil"] == ESTADO["active_profile"], (
        f"o perfil ativo do dublê é {ESTADO['active_profile']!r} e a tela "
        f"receberia {valor['perfil']!r}")
    assert str(valor["vel-cursor"]) == str(rato["speed"]), (
        f"o dublê manda `speed={rato['speed']}` e o campo diz "
        f"{valor['vel-cursor']!r}")
    assert str(valor["vel-rolagem"]) == str(rato["scroll_speed"]), (
        f"o dublê manda `scroll_speed={rato['scroll_speed']}` e o campo diz "
        f"{valor['vel-rolagem']!r}")

    fita = str(valor["fita-chips"])
    mesa = mesa_viva.mesa_do_estado(ESTADO, CORES_LIDAS)
    quantos = fita.count('class="chip')
    assert quantos == len(mesa) + 1, (
        f"a mesa do dublê tem {len(mesa)} controles e a fita traz {quantos} "
        f"chips (contando o 'Todos'): {fita!r}")
    for lugar in mesa:
        slug, nome = mesa_viva.CORES[CORES_LIDAS[str(lugar["uniq"])].codigo]
        assert f'P{lugar["jogador"]}' in fita and nome in fita, (
            f"a fita não traz o chip do {lugar['pref']} ({nome}): {fita!r}")
        assert monta.cor_da_zona(slug) is not None
