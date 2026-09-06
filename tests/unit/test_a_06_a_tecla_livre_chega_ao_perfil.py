#!/usr/bin/env python3
"""A RÉGUA DA `NAVEGACAO-TECLAS-01`: a tecla que ela escreve chega ao perfil.

O QUE ESTA FRENTE FECHOU, e é a linha `FALTA_NO_HTML` de
`docs/data/paridade-gtk-html.csv:208` — *Editar QUAL TECLA cada botão digita
(`Profile.key_bindings`, combinação livre)*:

    a janela ANTIGA   uma coluna EDITÁVEL EM TEXTO — `Alt + Tab`, `Ctrl + W`,
                      `F5`, qualquer combinação de `KEY_*`
    a tela NOVA       uma LISTA FECHADA de 26 ações, e `key_bindings` tocado
                      **só para ser zerado** pelo "Voltar ao padrão"

**ELA LÊ, NÃO DIGITA.** Nenhum nome de tecla, nenhum nome de botão e nenhuma
lista de domínio está escrita aqui: as teclas saem de
`input_actions.humanize_binding`, os botões de `input_actions.humanize_button`,
o domínio de `core.acoes_de_botao.DOMINIO_DO_TECLADO` e o de fábrica de
`acoes_de_botao.padrao()`. Esta casa pagou onze vezes em 26/08 por réguas que
digitavam o que deviam ler.

**E ELA MEDE O PRODUTO, não a frase.** As mordidas de gravação passam pelo gesto
inteiro — a `forma` que o piloto recolheria, o perfil real do esquema
(`profiles.schema.Profile`, e não um dublê mais frouxo que ele) e o
`resolver()` do motor, que é literalmente a chamada que
`profiles/manager.apply_button_actions` faz para alimentar o device.

AS TRÊS PERGUNTAS, uma por passo da sprint:

  Passo 1  uma combinação FORA das 26 chega a `Profile.key_bindings`, e uma que
           o teclado virtual não sabe digitar é RECUSADA DIZENDO, sem gravar e
           sem apagar a anterior;
  Passo 2  o "Voltar ao padrão" de UMA linha não encosta nas outras, e o
           "Guardar" das teclas não apaga o que está fora do alcance dele;
  Passo 3  o botão PS está na lista UMA vez (a `ONDA5-06-02` o pôs lá).

A MORDIDA, e ela é uma por caso: cada docstring abaixo diz o que arrancar.
"""
from __future__ import annotations

import pathlib
import re
import sys

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
         "via": "rádio", "cor": "starlight-blue", "mascara": "DualSense"}]

ESTADO = {
    "active_profile": "regua",
    "mouse_emulation": {"enabled": False, "speed": 6, "scroll_speed": 1,
                        "bloqueio": "desligada", "despachando": False},
    "keyboard_emulation": {"enabled": True, "osk_disponivel": True},
    "controllers": [FALSO],
}


class _PonteMuda:
    """Aceita tudo e ANOTA. É o que separa "não gravou" de "não chamou"."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict]] = []

    def chamar(self, metodo: str, **params: object) -> bool:
        self.chamadas.append((metodo, dict(params)))
        return True

    def __getattr__(self, _nome: str):
        return lambda *a, **k: True


def _bancada() -> str:
    import onde

    return onde.pagina(PAGINA, publicado=False).read_text(encoding="utf-8")


def _perfil(**campos):
    """Um `Profile` DE VERDADE — o do esquema, nunca um dublê mais frouxo.

    A RAZÃO É MEDIDA E É DESTA CASA: em 06/09/2026 um dublê de device com a
    assinatura antiga transformou um `TypeError` em "o produto falhou ao
    aplicar", e em 04/09 outro, mais frouxo que a função real, envenenou um
    arquivo inteiro por ordem de teste. Aqui o perfil é o pydantic do produto:
    se um campo desta frente não couber no esquema, a régua estoura na hora em
    vez de gravar um dicionário que o disco recusaria.
    """
    from hefesto_dualsense4unix.profiles.schema import Profile

    return Profile(name="regua", match={"type": "manual"}, **campos)


@pytest.fixture
def bancada(monkeypatch):
    """O pacote da 06 com um disco de mentira e a trava sempre limpa.

    A LIMPEZA É OBRIGATÓRIA: `_MEXENDO` é estado de MÓDULO, e um teste que a
    deixasse suja contaminaria o seguinte — o vazamento seria justamente o
    defeito que estes casos existem para medir.
    """
    import pacotes
    from pacotes import a06_navegacao as mod
    from pacotes import perfil
    from hefesto_dualsense4unix.profiles import loader

    disco: dict[str, object] = {}
    gravados: list[object] = []

    def _gravar(prof, **_):
        from hefesto_dualsense4unix.profiles.schema import Profile

        # O DISCO REVALIDA, e é de propósito: `model_copy` do pydantic **não**
        # valida, então um dublê que apenas guardasse o objeto seria mais
        # frouxo que o `save_profile` de verdade, que serializa e relê.
        disco[prof.name] = Profile.model_validate(prof.model_dump())
        gravados.append(disco[prof.name])

    monkeypatch.setattr(loader, "load_profile", lambda n: disco[n], raising=False)
    monkeypatch.setattr(loader, "save_profile", _gravar, raising=False)
    monkeypatch.setattr(
        perfil, "ativo",
        lambda nome: (disco[nome].model_dump() if nome in disco else {}))
    mod._MEXENDO.clear()
    monkeypatch.setattr(mod, "_ULTIMA_PINTURA", 0.0, raising=False)
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})
    yield ctx, mod, disco, gravados
    mod._MEXENDO.clear()


def _forma_das_teclas(mod, p, **trocas):
    """A `forma` que o piloto recolheria da tela de teclas, com trocas."""
    forma = {c: v for c, v in mod.teclas_dos_botoes(p).items()}
    for botao, texto in trocas.items():
        forma[f"{mod.PREFIXO_DA_TECLA}{botao}"] = texto
    return forma


def _fora_do_dominio() -> str:
    """Um botão que `key_bindings` NÃO alcança — perguntado ao motor."""
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    for botao in acoes.BOTOES:
        if botao not in acoes.DOMINIO_DO_TECLADO:
            return botao
    raise AssertionError("o domínio do teclado passou a ser TODOS os botões")


# ---------------------------------------------------------------------------
# PASSO 1 — a tela de escolher a tecla
# ---------------------------------------------------------------------------
def test_a_tela_oferece_um_campo_por_botao_do_dominio():
    """Um campo de texto para cada botão que `key_bindings` alcança, e só.

    O DOMÍNIO É DO PRODUTO, e a régua o pergunta: oferecer campo num botão fora
    dele gravaria no disco uma escolha que o `resolver()` não lê — a ausência de
    dado, que se lê como "a mudança não pegou".

    A MORDIDA: tire uma linha do laço que monta a `TELA_TECLAS` em `aba06.py`,
    ou troque `_DOMINIO_DO_TECLADO` por uma lista digitada — este caso nomeia o
    botão que ficou de fora.
    """
    from hefesto_dualsense4unix.core.acoes_de_botao import DOMINIO_DO_TECLADO

    doc = _bancada()
    achados = set(re.findall(r'data-campo="tecla-([^"]+)"', doc))
    assert achados == set(DOMINIO_DO_TECLADO), (
        f"a tela oferece campo de tecla para {sorted(achados)} e o produto "
        f"guarda `key_bindings` para {sorted(DOMINIO_DO_TECLADO)} — a mais: "
        f"{sorted(achados - set(DOMINIO_DO_TECLADO))}; a menos: "
        f"{sorted(set(DOMINIO_DO_TECLADO) - achados)}")
    for botao in DOMINIO_DO_TECLADO:
        assert f'data-tecla="{botao}"' in doc, (
            f"o ↺ do {botao} sumiu — voltar UMA linha ao de fábrica volta a "
            "custar o 'Voltar ao padrão' da tela inteira.")


def test_o_campo_de_texto_nao_ocupa_a_chave_da_lista():
    """O campo de tecla não pode ter `data-linha` — a `forma` colidiria.

    O DEFEITO QUE ISTO IMPEDE é de UMA linha de JavaScript e some sem barulho:
    o piloto monta a `forma` com `data-linha || data-campo` como chave
    (`hefesto_vivo`, o bloco `forma:`), e as vinte e duas listas de *o que cada
    botão faz* já ocupam a chave `<botão>` pelo `data-linha`. Um campo de texto
    com `data-linha` gravaria o texto dela NA CHAVE DA LISTA, e o
    `guardar-definicoes` leria "Ctrl + W" onde espera um rótulo de ação — recusa
    a tabela inteira, ou pior, apaga a escolha da lista.

    A MORDIDA: acrescente `data-linha="{botao}"` ao `<input>` de
    `aba06.linha_de_tecla` — este caso reprova nomeando o atributo.
    """
    doc = _bancada()
    tela = doc.split('id="teclas-do-teclado"', 1)[-1].split('class="tela-nova"', 1)[0]
    assert 'data-campo="tecla-' in tela, "não achei a tela de teclas na bancada"
    assert "data-linha=" not in tela, (
        "voltou um `data-linha` à tela de teclas — ele faria o campo de texto "
        "ocupar, na `forma`, a chave da lista de 'o que cada botão faz'.")
    # E O ↺ NÃO ENTRA NA FORMA. Sem `value`, o piloto gravaria o `textContent`
    # dele ("↺") na chave que ele carregasse.
    for linha in re.findall(r"<tr>(.*?)</tr>", tela, re.S):
        if "padrao-da-tecla" not in linha:
            continue
        ancora = linha.split("padrao-da-tecla", 1)[-1].split("</a>", 1)[0]
        assert "data-campo=" not in ancora and "data-linha=" not in ancora, (
            f"o ↺ ganhou um endereço de forma: {ancora!r}")


def test_uma_combinacao_fora_da_lista_chega_ao_key_bindings(bancada):
    """**A MORDIDA DO PASSO 1.** Ela digita `Ctrl + W`; o perfil passa a digitar.

    `Ctrl + W` NÃO É OPÇÃO DE LISTA NENHUMA — a régua confere isso antes de
    tudo, senão estaria medindo o caminho velho com nome novo.

    E A PROVA VAI ATÉ O DEVICE: não basta o campo aparecer no arquivo. O
    `resolver()` do motor é a chamada que `apply_button_actions` faz para
    alimentar o teclado virtual, e é ela que tem de devolver a combinação.

    A MORDIDA: tire o laço que escreve `atalhos[botao]` do `guardar_teclas` —
    este caso reprova dizendo que o perfil não guardou nada.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    ctx, mod, disco, gravados = bancada
    disco["regua"] = _perfil()
    alvo = sorted(acoes.DOMINIO_DO_TECLADO)[0]
    escrito = mod._atalho_em_palavras("KEY_LEFTCTRL+KEY_W")
    assert acoes.token_do_rotulo(escrito) is None, (
        f"{escrito!r} virou opção da lista de 26 — esta régua existe para medir "
        "o que a lista NÃO oferece, e passou a medir outra coisa.")

    mod.tecla_escrita(ctx, {"campo": f"{mod.PREFIXO_DA_TECLA}{alvo}",
                            "valor": escrito}, _PonteMuda())
    mod.guardar_teclas(ctx, {"forma": _forma_das_teclas(
        mod, disco["regua"].model_dump(), **{alvo: escrito})}, _PonteMuda())

    assert len(gravados) == 1, f"gravou {len(gravados)} vez(es), esperava uma"
    guardado = disco["regua"].key_bindings or {}
    assert guardado.get(alvo) == ["KEY_LEFTCTRL", "KEY_W"], (
        f"o perfil guardou {guardado.get(alvo)!r} para o {alvo} — ela escreveu "
        f"{escrito!r}, e o dono da tradução é `input_actions.dehumanize_binding`.")
    _mouse, do_teclado, _sem = acoes.resolver(
        disco["regua"].button_actions, disco["regua"].key_bindings)
    assert do_teclado.get(alvo) == ("KEY_LEFTCTRL", "KEY_W"), (
        f"o perfil guardou e o motor não entrega: `resolver()` devolve "
        f"{do_teclado.get(alvo)!r} — é a chamada que alimenta o teclado virtual, "
        "e o que ela não devolver o aparelho não digita.")


def test_uma_tecla_que_o_teclado_nao_sabe_e_recusada_dizendo(bancada):
    """**A SEGUNDA METADE DA MORDIDA DO PASSO 1.** Recusa, e a anterior fica.

    O DONO É `uinput_keyboard.SUPPORTED_KEYS` — a lista de capacidades que o
    device declara ao sistema quando nasce. `parse_binding` **não** basta: ele
    confere só o PREFIXO `KEY_`, e o device faz `getattr(u, key_name, None)` e
    **pula em silêncio** o que o módulo não conhece. Sem esta pergunta, a tela
    aceitaria uma tecla inventada, ela apareceria no perfil e no campo, e o
    botão não digitaria nada.

    A RECUSA É `RuntimeError` porque só ela CHEGA À TELA: o `_recusou_dizendo`
    do piloto leva a frase do `RuntimeError` e cala a do `ValueError`, que é a
    linguagem de quem programa.

    A MORDIDA: tire o bloco `if not virtuais:` de `tokens_da_tecla` — este caso
    reprova dizendo que a tecla inventada foi aceita.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes
    from hefesto_dualsense4unix.integrations.uinput_keyboard import SUPPORTED_KEYS

    ctx, mod, disco, gravados = bancada
    alvo = sorted(acoes.DOMINIO_DO_TECLADO)[0]
    antes = {alvo: ["KEY_F11"]}
    disco["regua"] = _perfil(key_bindings=dict(antes))

    invalida = next(f"KEY_KP{n}" for n in range(10)
                    if f"KEY_KP{n}" not in SUPPORTED_KEYS)
    with pytest.raises(RuntimeError) as caiu:
        mod.tecla_escrita(ctx, {"campo": f"{mod.PREFIXO_DA_TECLA}{alvo}",
                                "valor": invalida}, _PonteMuda())
    assert "não sabe digitar" in str(caiu.value), str(caiu.value)
    assert not gravados, "o gesto do campo não pode gravar em disco"
    # A TRAVA SOLTA NA RECUSA: sem isso a tela ficaria mostrando o texto
    # inválido para sempre e o Guardar recusaria a cada clique por causa dele.
    assert f"{mod.PREFIXO_DA_TECLA}{alvo}" not in mod._MEXENDO, (
        "a recusa segurou a trava — o tique nunca devolveria o valor do perfil.")

    with pytest.raises(RuntimeError) as caiu:
        mod.guardar_teclas(ctx, {"forma": _forma_das_teclas(
            mod, disco["regua"].model_dump(), **{alvo: invalida})}, _PonteMuda())
    assert "não gravei nada" in str(caiu.value), str(caiu.value)
    assert not gravados, "o Guardar gravou apesar da recusa"
    assert disco["regua"].key_bindings == antes, (
        f"a anterior não sobreviveu: {disco['regua'].key_bindings!r}")


def test_o_campo_vazio_cala_o_botao(bancada):
    """Campo em branco é `— Nada —`, e é a mesma palavra da lista ao lado.

    A REGRA É DO MOTOR, e a régua a confere no motor: dentro do domínio, uma
    chave AUSENTE de um `key_bindings` que já é dicionário vira `__NADA__`
    (`acoes_de_botao._tabela_efetiva`) — porque `resolve_key_bindings` devolve
    só as chaves do dict e é ele quem alimenta o device.

    A MORDIDA: faça o `guardar_teclas` gravar `[]` em vez de tirar a chave —
    este caso reprova dizendo que o botão continua falando.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    ctx, mod, disco, _gravados = bancada
    alvo = sorted(acoes.DOMINIO_DO_TECLADO)[0]
    disco["regua"] = _perfil(key_bindings={alvo: ["KEY_F11"]})

    mod.guardar_teclas(ctx, {"forma": _forma_das_teclas(
        mod, disco["regua"].model_dump(), **{alvo: ""})}, _PonteMuda())

    assert alvo not in (disco["regua"].key_bindings or {}), (
        f"o campo em branco deixou {alvo} no perfil: "
        f"{disco['regua'].key_bindings!r}")
    _m, do_teclado, _s = acoes.resolver(None, disco["regua"].key_bindings)
    assert alvo not in do_teclado, (
        f"o botão continua digitando {do_teclado.get(alvo)!r} depois de ela "
        "apagar o campo — é o botão que responde calado, pelo avesso.")


# ---------------------------------------------------------------------------
# PASSO 2 — "Voltar ao padrão" para de apagar o que ela escreveu
# ---------------------------------------------------------------------------
def test_o_padrao_da_linha_ao_lado_nao_apaga_a_dela(bancada):
    """**A MORDIDA DO PASSO 2.** O ↺ de uma linha não encosta na vizinha.

    A REGRA DELA: *"'Voltar ao padrão' devolve a LINHA ao padrão; ele não é um
    apagador de tudo o que ela escreveu na janela antiga."*

    E ESCREVER É O CERTO, APAGAR SERIA O ERRADO: dentro de um `key_bindings`
    que já é dicionário, tirar a chave devolve a linha ao SILÊNCIO, não ao de
    fábrica. Por isso o gesto ESCREVE `acoes.padrao()[botão]`, e por isso a
    régua confere a linha voltada contra o de fábrica do dono.

    A MORDIDA: faça `padrao_da_tecla` gravar `key_bindings = None` (o que o
    "Voltar ao padrão" da tela inteira faz) — este caso reprova nomeando o
    atalho da vizinha que sumiu.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    ctx, mod, disco, gravados = bancada
    dominio = sorted(acoes.DOMINIO_DO_TECLADO)
    minha, vizinha = dominio[0], dominio[1]
    disco["regua"] = _perfil(key_bindings={minha: ["KEY_LEFTCTRL", "KEY_W"],
                                           vizinha: ["KEY_F5"]})

    mod.padrao_da_tecla(ctx, {"tecla": vizinha}, _PonteMuda())

    assert len(gravados) == 1, f"gravou {len(gravados)} vez(es), esperava uma"
    guardado = disco["regua"].key_bindings or {}
    assert guardado.get(minha) == ["KEY_LEFTCTRL", "KEY_W"], (
        f"o ↺ do {vizinha} apagou o atalho do {minha}: {guardado.get(minha)!r} "
        "— é a perda de trabalho dela que este passo existe para fechar.")
    assert guardado.get(vizinha) == acoes.padrao()[vizinha].split("+"), (
        f"o {vizinha} não voltou ao de fábrica: {guardado.get(vizinha)!r}, e o "
        f"produto diz {acoes.padrao()[vizinha]!r}.")
    _m, do_teclado, _s = acoes.resolver(None, guardado)
    assert do_teclado.get(vizinha) == tuple(acoes.padrao()[vizinha].split("+")), (
        f"o motor entrega {do_teclado.get(vizinha)!r} para a linha que o botão "
        "acabou de dizer que voltou ao de fábrica.")


def test_o_guardar_das_teclas_nao_apaga_o_que_esta_fora_do_alcance(bancada):
    """O que ela escreveu num botão FORA do domínio sobrevive ao Guardar.

    ELA PODE TER ESCRITO `Ctrl + W` NO CROSS pela janela antiga, e nada nesta
    tela alcança essa linha — logo nada nesta tela tem o direito de apagá-la. O
    dicionário de partida é o do perfil, e só as chaves do domínio são
    reescritas.

    A MORDIDA: faça o `guardar_teclas` montar o dicionário do zero (`atalhos =
    {}` em vez de `_atalhos_de_hoje(prof)`) — este caso reprova nomeando o botão
    que sumiu.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    ctx, mod, disco, _gravados = bancada
    de_fora = _fora_do_dominio()
    alvo = sorted(acoes.DOMINIO_DO_TECLADO)[0]
    disco["regua"] = _perfil(key_bindings={de_fora: ["KEY_LEFTCTRL", "KEY_W"]})

    mod.guardar_teclas(ctx, {"forma": _forma_das_teclas(
        mod, disco["regua"].model_dump(),
        **{alvo: mod._atalho_em_palavras("KEY_F5")})}, _PonteMuda())

    guardado = disco["regua"].key_bindings or {}
    assert guardado.get(de_fora) == ["KEY_LEFTCTRL", "KEY_W"], (
        f"o Guardar das teclas apagou o {de_fora}, que ele nem oferece: "
        f"{guardado.get(de_fora)!r}")
    assert guardado.get(alvo) == ["KEY_F5"], guardado


def test_o_atalho_do_dominio_sobrevive_ao_guardar_das_definicoes(bancada):
    """O outro lado do `test_o_guardar_nomeia_os_atalhos_que_param_de_valer`.

    A CURA VEIO EM DOIS DEGRAUS, e este caso mede o segundo: a `ONDA3-MOTOR-01`
    fez o `resolver()` HERDAR `key_bindings`, e o chamador desta aba
    (`atalhos_que_param_de_valer`) continuava chamando `resolver(button_actions)`
    com um argumento só — a assinatura de antes, byte a byte, que aquela frente
    preservou de propósito. Com o campo passado, o atalho de um botão DO DOMÍNIO
    deixa de morrer no "Guardar" da tabela.

    A MORDIDA: tire o segundo argumento de `acoes.resolver(...)` em
    `atalhos_que_param_de_valer` — este caso reprova dizendo que o gesto ainda
    nomeia como perdido um atalho que sobrevive.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    _ctx, mod, _disco, _gravados = bancada
    alvo = sorted(acoes.DOMINIO_DO_TECLADO)[0]
    p = {"key_bindings": {alvo: ["KEY_LEFTCTRL", "KEY_W"]},
         "button_actions": {"square": "KEY_ESC"}}

    perdidos = dict(mod.atalhos_que_param_de_valer(p))
    assert alvo not in perdidos, (
        f"o {alvo} está no domínio de `key_bindings` e a aba ainda o nomeia "
        f"como perdido: {perdidos!r}")
    # E O DE FORA CONTINUA SE PERDENDO — a perda ENCOLHEU, não sumiu, e uma
    # régua que dissesse o contrário absolveria o defeito que resta.
    de_fora = _fora_do_dominio()
    p["key_bindings"][de_fora] = ["KEY_F5"]
    assert de_fora in dict(mod.atalhos_que_param_de_valer(p)), (
        f"o {de_fora} está FORA do domínio: o `apply_button_actions` reescreve "
        "o teclado inteiro sem consultá-lo, e a tela tem de dizer isso.")


def test_a_tira_nomeia_a_linha_que_a_lista_nao_sabe_dizer(bancada):
    """A tabela de 22 linhas para de mentir sobre a linha com tecla livre.

    O DEFEITO QUE ISTO IMPEDE nasceu COM o Passo 1: uma combinação livre não tem
    `<option>` na lista de 26, `acoes.rotulo()` devolve o token cru e o
    `escrever()` do piloto recusa em silêncio o texto que não casa com nenhuma
    opção — o que fica na tela é o rótulo que o DESENHO cravou, e a linha passa
    a AFIRMAR uma ação que o botão não faz.

    A MORDIDA: tire o ramo `if mudas:` de `_aviso_da_tabela` — este caso reprova
    dizendo que a tabela cala sobre a linha que ela não sabe mostrar.
    """
    from hefesto_dualsense4unix.app.actions.input_actions import humanize_button
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    _ctx, mod, _disco, _gravados = bancada
    alvo = sorted(acoes.DOMINIO_DO_TECLADO)[0]
    p = {"key_bindings": {alvo: ["KEY_LEFTCTRL", "KEY_W"]}}

    aviso = mod._aviso_da_tabela(p)
    assert humanize_button(alvo) in aviso, (
        f"a tira não nomeia o {alvo}, cuja tecla a lista não sabe mostrar: "
        f"{aviso!r}")
    assert mod._atalho_em_palavras("KEY_LEFTCTRL+KEY_W") in aviso, aviso
    # E ELA NÃO FALA DO QUE A LISTA SABE DIZER: a tira só ocupa espaço quando há
    # o que dizer, e nomear uma linha que a lista mostra certo seria ruído.
    p2 = {"key_bindings": {alvo: acoes.padrao()[alvo].split("+")}}
    assert humanize_button(alvo) not in mod.linhas_que_a_lista_nao_sabe_dizer(p2)


def test_o_tique_nao_apaga_o_que_ela_esta_digitando(bancada):
    """O campo em edição sobrevive à pintura — a exigência de tempo da sprint.

    O DEFEITO É DE 100 ms: o `escrever()` do piloto faz `el.value = t` assim que
    os dois diferem, e um campo em edição difere já na primeira letra. Sem a
    trava, o tique apagaria o que ela está digitando.

    O CLIQUE É QUEM ABRE A TRAVA, e não o `change`: um `<input>` só dispara
    `change` ao PERDER o foco, tarde demais. É por isso que o `<input>` leva
    `data-gesto` — o ouvinte de `click` do piloto sobe pelo `closest`.

    A MORDIDA: tire o `linhas.update(teclas_dos_botoes(p))` de
    `_o_que_a_tabela_mostra`, ou o `_MEXENDO[campo] = texto` de `tecla_escrita`
    — este caso reprova dizendo que a pintura mandou outro texto.
    """
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    ctx, mod, disco, _gravados = bancada
    alvo = sorted(acoes.DOMINIO_DO_TECLADO)[0]
    disco["regua"] = _perfil(key_bindings={alvo: ["KEY_F11"]})
    campo = f"{mod.PREFIXO_DA_TECLA}{alvo}"

    do_perfil = mod.pacote(ctx)["mesa"][campo]
    assert do_perfil == mod._atalho_em_palavras("KEY_F11"), do_perfil

    meio = mod._atalho_em_palavras("KEY_LEFTCTRL") + " + "
    mod.tecla_escrita(ctx, {"campo": campo, "valor": meio}, _PonteMuda())
    for _volta in range(15):  # 1,5 s de tique, que é a janela medida em 02/09
        agora = mod.pacote(ctx)["mesa"][campo]
        assert agora == meio, (
            f"o tique escreveu {agora!r} por cima do que ela está digitando "
            f"({meio!r}) — o campo é reconstruído sob os dedos dela.")


# ---------------------------------------------------------------------------
# PASSO 3 — o botão PS na lista (entregue pela ONDA5-06-02; aqui se CONFERE)
# ---------------------------------------------------------------------------
def test_o_botao_ps_esta_na_lista_uma_vez_so():
    """O PS é linha da tabela, e é UMA linha — não duas.

    O CUIDADO É O QUE A SPRINT MANDA: a `ONDA5-06-02` fecha antes desta frente e
    entrega *"a vigésima segunda linha"*. Acrescentar de novo daria duas linhas
    `ps`, e a segunda seria construída por quem não conferiu.

    A MORDIDA: acrescente uma segunda entrada `ps` a `aba06.BOTOES` — este caso
    reprova com a conta.
    """
    from hefesto_dualsense4unix.app.actions.input_actions import _BUTTON_LABELS
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes

    assert acoes.BOTAO_PS in acoes.BOTOES, (
        "o PS saiu da lista do produto — a decisão dela na 06-Q3 o pôs lá.")
    doc = _bancada()
    quantas = doc.count(f'data-linha="{acoes.BOTAO_PS}"')
    assert quantas == 1, (
        f"o desenho tem {quantas} linha(s) do PS — a régua da aba apanha duas, "
        "e uma delas teria sido construída por quem não conferiu a outra.")
    # O RÓTULO É O DO DONO, e não uma digitação desta tela.
    assert _BUTTON_LABELS[acoes.BOTAO_PS] == "Botão PS"
