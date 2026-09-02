#!/usr/bin/env python3
"""A RÉGUA DA ABA 06: o que o pacote manda tem onde cair, e o que cai é inteiro.

POR QUE ELA EXISTE, medido em 02/09/2026 na aba Navegação — e o achado derruba
o enunciado do trabalho:

    o passeio reportava `06-navegacao.html  1 pintura  3 valores` num HTML com
    7 endereços, e disso se concluiu que a aba "MENCIONA 7 e PINTA 3".

**Ela pinta os 8 elementos endereçados.** O `3` é contagem de MUDANÇA: o
`escrever()` do piloto devolve `1` só quando o valor NOVO difere do que já
estava na tela, e cinco dos oito já coincidiam com o daemon dela (`2
controles:`, `1 USB · 1 BT`, `6`, `1`, `Ligada — atalhos e teclado na tela`).
Contar mudança e ler "pintura" é a mesma confusão entre a PALAVRA e o ATO que
produziu o "77%" falso desta casa, com o sinal trocado.

O QUE ESTA RÉGUA COBRA, e cada item é um defeito que a medição do mesmo dia
achou nesta aba:

1. **Chave emitida tem endereço na BANCADA**, ou está declarada em
   `SEM_ENDERECO` com a razão. `casamento.py` já imprimia os órfãos e reprovava
   só o ZERO — esta aba mandava 8 chaves para o vazio com o portão verde, e uma
   delas (`via`) não era falta de lugar: era o pacote mandando METADE de uma
   linha cujo endereço cobre a linha inteira.
2. **`SEM_ENDERECO` não guarda quem já tem casa** — declaração que envelhece é
   a régua se desligando sozinha.
3. **O cartão leva o transporte.** O endereço `data-campo="navega"` cobre
   `{via} • {papel}`; mandar só o papel APAGAVA o "USB •" no primeiro tique.
4. **As 21 linhas de *o que cada botão faz* saem do PERFIL**, e cada valor
   emitido existe como `<option>` daquele `<select>` — condição do
   `escrever()` com `data-hef-alvo="valor"`, que se cala calado quando não casa.
5. **O "Guardar" não apaga o que a tela não mostrou.**
6. **O produto nunca está à FRENTE do desenho** em endereço de pintura.

A MORDIDA: tire o `via` de `_linha_do_cartao`, ou o `campo=` da chamada de
`drop()` no gerador, ou a trava do `guardar_definicoes` — cada um reprova um
teste diferente, nomeando o que se perdeu.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: Um controle de mentira. MAC da faixa sintética da casa — há dois portões de
#: anonimato nesta árvore e eles não perdoam.
UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "bt",
         "battery_pct": 95, "is_primary": True, "inputs": {}, "audio": {},
         "speaker": {}}
#: A MESA é quem tem o `via` — `mesa_viva` traduz `transport` uma vez só, e o
#: pacote lê o traduzido. Aqui ela vem montada à mão, com a mesma forma.
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "BT", "cor": "starlight-blue", "mascara": "DualSense"}]

#: O estado do daemon como a aba o consome. Sem `keyboard_emulation` o pacote
#: NÃO emite `teclado-estado`, de propósito — ver o corpo de `pacote()`.
ESTADO = {
    "active_profile": "regua",
    "mouse_emulation": {"enabled": False, "speed": 6, "scroll_speed": 1,
                        "bloqueio": "desligada", "despachando": False},
    "keyboard_emulation": {"enabled": True, "osk_disponivel": True},
    "controllers": [FALSO],
}

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo
CAMPO = re.compile(r'data-(?:campo|papel|hef)="([^"]+)"')


def _perfil_de_mentira(tmp_path, **campos):
    """Grava um perfil no disco e aponta a `pacotes.perfil` para ele."""
    from pacotes import perfil

    corpo = {"name": "Régua", "version": 1, "priority": 50,
             "match": {"type": "criteria"}}
    corpo.update(campos)
    (tmp_path / "regua.json").write_text(json.dumps(corpo), encoding="utf-8")
    perfil.pasta = lambda: tmp_path
    return tmp_path


@pytest.fixture
def aba(tmp_path):
    """O pacote da 06 rodado contra o estado acima, com um perfil no disco."""
    import pacotes
    from pacotes import a06_navegacao

    _perfil_de_mentira(tmp_path)
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})
    bruto = a06_navegacao.pacote(ctx)
    pronto = pacotes.normalizar(bruto, {UNIQ: "p1"})
    for chave, valor in pacotes.topo(ctx).items():
        pronto["mesa"].setdefault(chave, valor)
    return ctx, a06_navegacao, pronto


def _enderecos(publicado: bool) -> set[str]:
    import onde

    return set(CAMPO.findall(
        onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")))


def test_toda_chave_emitida_tem_endereco_ou_esta_declarada(aba):
    """Órfão calado é o defeito; órfão DECLARADO é inventário.

    A mordida: acrescente uma chave qualquer ao `mesa` do pacote sem endereço no
    desenho e sem linha no `SEM_ENDERECO` — este teste a nomeia.
    """
    _, mod, pronto = aba
    emitidas = {k for k, v in pronto["mesa"].items() if not isinstance(v, (dict, list))}
    for campos in pronto["colunas"].values():
        emitidas |= {k for k, v in campos.items() if not isinstance(v, (dict, list))}
    # As estruturas também contam: o piloto as pula, e emiti-las é peso morto.
    emitidas |= {k for k, v in pronto["mesa"].items() if isinstance(v, (dict, list))}
    # O CABEÇALHO É DAS DEZ ABAS (`pacotes.topo`) e não é desta: cobrar dele
    # aqui faria esta régua reprovar por causa de um dono compartilhado.
    import pacotes

    ctx, _, _ = aba
    do_topo = set(pacotes.topo(ctx))
    orfaos = emitidas - _enderecos(publicado=False) - do_topo - set(mod.SEM_ENDERECO)
    assert not orfaos, (
        f"o pacote da 06 manda {sorted(orfaos)} e o desenho de hoje "
        f"(`mockup/{PAGINA}`) não tem onde pôr.\n"
        "Ou o gerador marca o campo, ou a chave entra em `SEM_ENDERECO` com a "
        "razão medida. Emitir para o vazio não aparece na tela nem no portão — "
        "foi assim que `via` mandou metade de uma linha por uma leva inteira.")


def test_o_sem_endereco_nao_guarda_quem_ja_tem_casa(aba):
    """Declaração que envelheceu é a régua desligada sem ninguém decidir isso."""
    _, mod, _ = aba
    tem_casa = set(mod.SEM_ENDERECO) & _enderecos(publicado=False)
    assert not tem_casa, (
        f"{sorted(tem_casa)} está em `SEM_ENDERECO` e o desenho JÁ tem endereço "
        "para essas chaves — tire-as da lista e deixe a pintura acontecer.")


def test_a_linha_do_cartao_leva_o_transporte(aba):
    """`navega` é a LINHA inteira, não o papel: o endereço cobre os dois.

    Medido em 02/09/2026, com a foto: o desenho escreve
    `USB <span class="pt">•</span> Navega o PC` e o pacote mandava só
    `Navega o PC` — o piloto escreve `textContent`, então o primeiro tique
    apagava o transporte do cartão. A tela nascia dizendo por onde o controle
    está ligado e parava de dizer meio segundo depois.
    """
    _, _, pronto = aba
    linha = pronto["colunas"]["p1"]["navega"]
    assert linha == "BT • Navega o PC", (
        f"o cartão do primário saiu {linha!r}. O `data-campo=\"navega\"` cobre "
        "a linha inteira do desenho — sem o transporte, a pintura o APAGA.")
    assert "via" not in pronto["colunas"]["p1"], (
        "`via` voltou a ser chave própria: ela não tem endereço no desenho, e "
        "quem a recebia era o `navega`.")


def test_a_linha_do_cartao_nao_inventa_transporte(aba):
    """Sem casa na mesa, sai só o papel — nunca um transporte adivinhado."""
    _, mod, _ = aba
    assert mod._linha_do_cartao({}, True) == "Navega o PC"
    assert mod._linha_do_cartao({}, False) == "Só a janela"


def test_as_vinte_e_uma_linhas_saem_do_perfil(tmp_path):
    """O que o perfil guarda vence o de fábrica, linha a linha.

    A mordida: faça `_linhas_dos_botoes` ignorar `button_actions` — este teste
    reprova, porque a tela voltaria a mostrar o de fábrica com o perfil dizendo
    outra coisa. Era exatamente o estado de 02/09, e era o que fazia o "Guardar"
    apagar.
    """
    import pacotes
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes  # noqa: F401
    from pacotes import a06_navegacao

    _perfil_de_mentira(tmp_path, button_actions={"cross": "KEY_ESC"})
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})
    mesa = a06_navegacao.pacote(ctx)["mesa"]
    assert mesa["acao-cross"] == "Esc", (
        "a linha do X saiu do de fábrica, e o perfil manda `KEY_ESC` — a tela "
        "estaria mostrando o desenho no lugar da escolha dela.")
    # As outras 20 continuam no de fábrica, que é o que `None` quer dizer.
    assert mesa["acao-square"] == "Esc"
    # O L3 ALTERNA desde 02/09/2026 (decisão dela), e por isso o rótulo mudou:
    # `core/keyboard_mappings.DEFAULT_BUTTON_BINDINGS["l3"]` é o `__TOGGLE_OSK__`.
    assert mesa["acao-l3"] == "Abrir e fechar o teclado na tela"


def test_todo_valor_emitido_existe_como_opcao_daquela_lista(aba):
    """`escrever()` com `data-hef-alvo="valor"` SE CALA quando o texto não casa.

    Um `<select>` só aceita o texto exato de uma `<option>` (`hefesto_vivo.py`,
    ramo `alvo === 'valor'`), e a pintura devolve `0` em silêncio quando não
    acha. Um valor que não casa é um campo que nunca anda, sem uma linha de erro
    em lugar nenhum — por isso a régua confere o casamento TEXTO a TEXTO.
    """
    import onde

    doc = onde.pagina(PAGINA, publicado=False).read_text(encoding="utf-8")
    _, _, pronto = aba
    for chave, valor in sorted(pronto["mesa"].items()):
        if not str(chave).startswith("acao-"):
            continue
        bloco = re.search(
            rf'<select[^>]*data-campo="{re.escape(str(chave))}"[^>]*>(.*?)</select>',
            doc, re.S)
        assert bloco, f"{chave}: o desenho não tem `<select>` com esse endereço"
        opcoes = set(re.findall(r"<option[^>]*>(.*?)</option>", bloco.group(1)))
        assert str(valor) in opcoes, (
            f"{chave}: o pacote manda {valor!r} e a lista do desenho não tem "
            f"essa opção — a pintura se calaria e o campo ficaria parado para "
            f"sempre.")


def test_a_cobertura_conta_so_o_que_tem_casa(aba):
    """Contador que soma chave EMITIDA é o mesmo erro que produziu o "77%"."""
    _, mod, _ = aba
    import pacotes

    ctx, _, _ = aba
    bruto = mod.pacote(ctx)
    pintados = bruto["cobertura"]["pintados"]
    emitidas = len(bruto["mesa"]) + sum(len(v) for v in bruto["colunas"].values())
    assert pintados < emitidas, (
        f"a cobertura diz {pintados} e o pacote emite {emitidas} chaves — se os "
        "dois números são iguais, o contador voltou a somar o que não tem "
        "endereço.")
    assert pintados == emitidas - len(mod.SEM_ENDERECO)
    del pacotes


class _PerfilDeMentira:
    """O mínimo de um `Profile` que o "Guardar" toca, no idioma do pydantic.

    Instanciar o modelo de verdade exigiria um `match` válido, e a régua
    passaria a medir o esquema em vez do botão — mesma disciplina do
    `test_o_padrao_dos_atalhos_volta_de_fabrica.py`.
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


def _forma_de_fabrica(**trocas):
    """As 21 linhas como a tela publicada as mostra HOJE: o de fábrica inteiro."""
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    forma = {b: acoes.rotulo(a) for b, a in acoes.padrao().items()}
    forma.update(trocas)
    return forma


def test_o_guardar_nao_apaga_o_que_a_tela_nao_mostrou(disco):
    """O "Guardar" com a forma toda no de fábrica e o perfil com escolhas: RECUSA.

    Medido em 02/09/2026 contra a página PUBLICADA: as 21 `<select>` não tinham
    `data-campo`, logo nunca eram pintadas, logo mostravam sempre o que o
    gerador cravou — que é **exatamente** `acoes_de_botao.padrao()`. O gesto
    calculava "nada mudou", gravava `button_actions = None` e APAGAVA a escolha
    dela, em silêncio, com o botão dizendo "Guardar".

    A mordida: tire a trava do `guardar_definicoes` — este teste reprova
    dizendo que o perfil perdeu o `cross`.
    """
    import pacotes
    from pacotes import a06_navegacao

    estado, gravados = disco
    estado["regua"] = _PerfilDeMentira("regua", button_actions={"cross": "KEY_ESC"})
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})

    with pytest.raises(RuntimeError, match="não guardei"):
        a06_navegacao.guardar_definicoes(ctx, {"forma": _forma_de_fabrica()},
                                         _PonteMuda())
    assert not gravados, (
        "o gesto GRAVOU. Com a tela mostrando o de fábrica e o perfil guardando "
        "uma escolha, gravar é apagar — e o botão diz 'Guardar'.")


def test_o_guardar_continua_gravando_o_que_mudou(disco):
    """A trava não pode virar um "Guardar" que nunca guarda.

    Uma linha diferente do de fábrica é escolha real e vai para o disco — é o
    que separa a trava de uma recusa em bloco.
    """
    import pacotes
    from pacotes import a06_navegacao

    estado, gravados = disco
    estado["regua"] = _PerfilDeMentira("regua")
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})

    a06_navegacao.guardar_definicoes(ctx, {"forma": _forma_de_fabrica(square="Enter")},
                                     _PonteMuda())
    assert len(gravados) == 1, f"gravou {len(gravados)} vez(es), esperava uma"
    assert gravados[0].button_actions == {"square": "KEY_ENTER"}


def test_o_guardar_nao_grava_quando_nao_ha_o_que_gravar(disco):
    """Nada a gravar não vira gravação — nem quando a trava não age.

    Aqui `prof.button_actions` já é `None` e a forma é o de fábrica: não há
    escolha a perder, logo a trava contra o apagador não tem o que travar. O
    disco continua intocado — se a trava passasse a recusar em bloco, ela
    viraria um botão que reclama do estado normal, e este caso reprova.
    """
    import pacotes
    from pacotes import a06_navegacao

    estado, gravados = disco
    estado["regua"] = _PerfilDeMentira("regua")
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})

    with pytest.raises(RuntimeError):
        a06_navegacao.guardar_definicoes(ctx, {"forma": _forma_de_fabrica()},
                                         _PonteMuda())
    assert not gravados


@pytest.mark.parametrize(
    ("guardado", "a_forma", "pedaco"),
    [
        # O SEGUNDO CLIQUE que a trava manda dar: a tabela já se preencheu e
        # mostra o que o perfil guarda.
        ({"square": "KEY_ENTER"}, {"square": "Enter"}, "1 escolha"),
        # E o mesmo botão com o perfil de fábrica e a tela de fábrica.
        (None, {}, "de fábrica"),
    ],
)
def test_o_guardar_sem_o_que_guardar_recusa_dizendo(disco, guardado, a_forma, pedaco):
    """O "Guardar" sem nada a gravar tem de DIZER que já está guardado.

    O DEFEITO QUE ESTA LINHA FECHA, encenado em 02/09/2026 com dublê de disco e
    ponte muda — e ele era cruel com quem estava usando:

        1º clique (tabela ainda no desenho)   → RuntimeError, e a frase manda
                                                 "espere a tabela se preencher
                                                  e clique de novo"
        2º clique (tabela cheia, = ao perfil) → voltou SEM levantar, devolveu
                                                 None, gravou 0, chamou 0

    Uma recusa que INSTRUI a repetir o gesto e depois não responde nada é pior
    que uma recusa seca: ela promete que a segunda tentativa funciona. E um
    gesto que devolve `None` não toca o DOM (`hefesto_vivo._deu_certo`), logo o
    segundo clique era o botão que responde calado.

    A MORDIDA: troque a recusa do `guardar_definicoes` de volta por um `return`
    — os dois casos reprovam dizendo que o botão voltou a ficar mudo.
    """
    import pacotes
    from pacotes import a06_navegacao

    estado, gravados = disco
    estado["regua"] = _PerfilDeMentira("regua", button_actions=guardado)
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})
    ponte = _PonteMuda()

    with pytest.raises(RuntimeError) as caiu:
        a06_navegacao.guardar_definicoes(ctx, {"forma": _forma_de_fabrica(**a_forma)},
                                         ponte)
    frase = str(caiu.value)
    assert "guardar" in frase.lower(), (
        f"a recusa não diz que não havia o que guardar: {frase!r}")
    assert pedaco in frase, (
        f"a recusa não diz o que o perfil já tem ({pedaco!r}): {frase!r}")
    assert not gravados, "recusou e ainda assim gravou"


def test_a_recusa_chama_o_botao_pelo_nome_que_ela_le(disco):
    """O "Guardar" nomeia as linhas sem dono com o rótulo do MOTOR, não o id cru.

    Medido em 02/09/2026 com dublê: trocar o `cross` faz o `l2` divergir do seu
    espelho (`acoes.resolver` — o L2 é o cross por tabela), e a frase que ia
    para a tela dizia *"ficaram sem quem as atenda: l2"*. `l2` e
    `touchpad_left_press` são jargão de kernel na cara de quem clicou, e o
    produto já tem os nomes em `app/actions/input_actions.humanize_button` desde
    o KBD-01 — é o que a GTK que ela usa mostra.

    FATO SUBSTITUÍDO — 02/09/2026, corretivo: este parágrafo citava `r3_direcao`
    como curado junto com os outros dois. **Não está** — o motor tem 20 nomes
    para 21 botões, e os que faltam são `l3_direcao` e `r3_direcao`. A cura é do
    motor e está relatada; o teste abaixo é quem cobra que ninguém a escreva
    aqui.

    A mordida: faça `_nome_do_botao` devolver o argumento — este teste reprova
    dizendo que a frase voltou a falar em `l2`.
    """
    import pacotes
    from pacotes import a06_navegacao

    estado, _ = disco
    estado["regua"] = _PerfilDeMentira("regua")
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})

    with pytest.raises(RuntimeError) as caiu:
        a06_navegacao.guardar_definicoes(
            ctx, {"forma": _forma_de_fabrica(cross="Esc")}, _PonteMuda())
    frase = str(caiu.value)
    assert "L2 (gatilho esquerdo)" in frase, (
        f"a recusa saiu {frase!r} — o nome do botão tem de ser o que ela lê.")
    assert not re.search(r"\bl2\b", frase), (
        f"a recusa ainda traz o id cru do kernel: {frase!r}")


def test_o_nome_do_botao_e_o_do_motor_e_nao_uma_segunda_tabela():
    """Os nomes já existem no produto; escrevê-los de novo é o defeito.

    LEI 0 desta migração, palavra dela: *"não temos que recriar nada, só
    aproveitar o que foi feito"*. Esta linha reprova no dia em que alguém
    copiar a tabela para dentro do pacote — as duas passariam a envelhecer
    separadas, e a tela e a GTK diriam nomes diferentes para o mesmo botão.

    A CONFERÊNCIA É DAS VINTE E UMA, e não de quatro escolhidas — corrigido em
    02/09/2026. Com quatro, a tentação de remendar no pacote justamente o que o
    motor não tem (`l3_direcao` e `r3_direcao`) passaria sem reprovar nada: são
    os dois botões que a amostra não olhava. O buraco é do motor
    (`app/actions/input_actions.py:129` tem 20 nomes para 21 botões) e a cura é
    lá; o que esta linha impede é a segunda tabela nascer AQUI.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes
    from hefesto_dualsense4unix.app.actions import input_actions
    from pacotes import a06_navegacao

    for botao in acoes.BOTOES:
        assert a06_navegacao._nome_do_botao(botao) == \
            input_actions.humanize_button(botao), (
            f"{botao}: o pacote respondeu um nome que o motor não deu — é a "
            "segunda tabela nascendo.")


def test_o_produto_nunca_esta_a_frente_do_desenho():
    """Endereço no publicado que a bancada não tem = alguém editou o produto.

    O fluxo tem UMA direção (`mockup/` → `paginas/`), e um endereço que só
    exista do lado publicado é a única forma de ele ter andado sozinho.
    """
    a_mais = _enderecos(publicado=True) - _enderecos(publicado=False)
    assert not a_mais, (
        f"{sorted(a_mais)} existe na página publicada e não no desenho de hoje.")


class _PonteMuda:
    """Uma ponte que aceita tudo e não fala com daemon nenhum.

    A gravação do perfil é de disco (`profiles/loader`); o que a ponte faria é
    o `profile.switch` da reaplicação, e ele não é o que estes testes medem.
    """

    def __getattr__(self, _nome):
        return lambda *a, **k: True
