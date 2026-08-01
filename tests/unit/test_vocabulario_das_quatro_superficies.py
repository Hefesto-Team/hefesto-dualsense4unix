"""RADAR-01/E4 — a mesma coisa tem de ter o mesmo nome nas QUATRO superfícies.

Este projeto tem quatro superfícies de interface, e a auditoria de 31/07 mediu
que três nunca foram olhadas por sprint nenhuma:

  - a janela GTK   (``src/hefesto_dualsense4unix/app/`` + ``gui/main.glade``);
  - o applet COSMIC (``packaging/cosmic-applet/src/app.rs``, Rust);
  - a bandeja      (``src/hefesto_dualsense4unix/app/tray.py``);
  - a janela compacta (``src/hefesto_dualsense4unix/app/compact_window.py``).

O custo de nunca terem sido comparadas está medido na
``docs/process/sprints/2026-07-31-RADAR-01-as-tres-superficies-que-ninguem-nunca-olhou.md``:
uma renomeação entra na janela, não entra nas outras três, e elas passam a
contradizê-la em silêncio na frente de quem usa. Este arquivo é a regra
executável que a E4 daquela sprint pediu.

A técnica é a que já está provada nesta casa e é feia de propósito: um teste
Python que LÊ o fonte das outras superfícies como TEXTO. O precedente é o
``test_flavor_parity_superficies.py`` (linhas 14-16: *"O default do applet é
Rust e não dá para importar: este teste lê o fonte e casa a constante"*) e o
``test_applet_paridade_modo.py``, que extrai um ramo do Rust por regex.

Por que TEXTO e não ``import``, inclusive para as superfícies em Python: a
``tray.py`` (linhas 28-31) e a ``compact_window.py`` (linhas 42-45) fazem
``gi.require_version("Gtk", "3.0")`` no TOPO do módulo, e o job ``lint-test``
roda sem PyGObject por decisão registrada no próprio ``ci.yml``
(``CI-GUI-PULAVA-CALADO-01``). Importá-las aqui derrubaria a COLETA de um
módulo inteiro — e o censo de coleta do CI reprova exatamente por isso.

Disciplina contra a fragilidade, herdada da própria E4: **casar a frase, nunca
a formatação em volta dela.** Todo bloco é achado por uma âncora curta (um nome
de constante, um nome de variável) e as frases saem de dentro dele; um
``rustfmt`` ou um ``ruff format`` que quebre uma linha não muda nenhum
resultado.

--------------------------------------------------------------------------
Por que este arquivo nasce VERDE, e o que a E4 pedia
--------------------------------------------------------------------------

A E4 escreveu que o teste *"já reprova antes de qualquer conserto"* e ficaria
verde depois das entregas E1 e E3 — as que consertam o applet e a janela
compacta. Essas duas entregas **não foram feitas**: a E1 exige o applet
construído e o olho dela no painel (o popover é a única superfície que
``Gtk.OffscreenWindow`` não fotografa), e as duas dependem de decisão de
produto que ninguém tomou ainda.

Um arquivo de teste vermelho dentro de ``pytest tests/unit`` derruba o job
``lint-test`` para todo mundo, e a lição da
``2026-07-27-PORTAO-VIVO-01-os-gates-que-ninguem-roda.md`` é que um gate que
incomoda sem entregar decisão é um gate que alguém desliga. Então as
divergências já medidas entram aqui como **livro de divergências** — uma trava
de crescimento, no mesmo espírito do piso de coleta do ``ci.yml``:

  - se aparecer uma divergência NOVA, o teste reprova (é a mordida de hoje, e é
    o que impede a próxima renomeação de esquecer as outras superfícies);
  - se alguém CONSERTAR uma das registradas, o teste também reprova, com a
    mensagem dizendo qual linha do livro apagar.

Nenhuma divergência medida some daqui em silêncio, e nenhuma nova entra calada.

--------------------------------------------------------------------------
O que ficou de fora desta entrega, e por quê
--------------------------------------------------------------------------

- **A segunda mordida da E4** — acrescentar ``.rs`` ao ``EXTENSOES_ALVO`` do
  ``scripts/validar-acentuacao.py``, para que o Rust do applet passe pelo gate
  de acentuação (achado G1 da RADAR-01). É mudança em ``scripts/``, fora do
  alcance de quem escreveu este arquivo. Continua pendente e continua medida:
  o ``app.rs`` de hoje passaria, então o risco é prospectivo.
- **A geometria do popover.** ``Gtk.OffscreenWindow`` não alcança o
  ``cosmic-panel``; nada aqui mede pixel de applet.
- **A TUI** (``tui/app.py``) é uma quinta superfície, chamada pela CLI e não
  pelo painel. A RADAR-01 a deixou de fora por escrito, e este arquivo segue a
  mesma linha.
- **As frases da CLI.** ``cli/`` diz ``daemon offline`` em quinze lugares, e
  está certo: é saída de terminal para quem digitou um comando, não rótulo de
  tela. O inventário abaixo é das superfícies gráficas.
"""
from __future__ import annotations

import re
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]

#: A janela GTK. Duas das nove abas donas de vocabulário compartilhado.
_JANELA_INICIO = _RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions" / "home_actions.py"
_JANELA_PERFIS = (
    _RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions" / "profiles_actions.py"
)
_JANELA_EMULACAO = (
    _RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions" / "emulation_actions.py"
)
#: O applet COSMIC — a superfície que mora no painel dela (Rust).
_APPLET = _RAIZ / "packaging" / "cosmic-applet" / "src" / "app.rs"
#: A bandeja GTK.
_BANDEJA = _RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "tray.py"
#: A janela compacta (opt-in, desligada por default).
_COMPACTA = _RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "compact_window.py"

#: As três superfícies que NÃO são a janela. A janela é a dona das frases; são
#: estas que não podem contradizê-la.
_SUPERFICIES_SECUNDARIAS = {
    "APPLET": _APPLET,
    "BANDEJA": _BANDEJA,
    "COMPACTA": _COMPACTA,
}


# ---------------------------------------------------------------------------
# Leitura de fonte como texto — as duas ferramentas de todo teste deste arquivo
# ---------------------------------------------------------------------------

def _sem_comentarios(texto: str) -> str:
    """Descarta linhas de comentário (Python e Rust).

    Sem isto, uma frase citada dentro de um comentário conta como frase de
    tela — e um comentário que explica a divergência passaria a ser a
    divergência.
    """
    vivas = [
        linha
        for linha in texto.splitlines()
        if not linha.strip().startswith(("#", "//", "*", "<!--"))
    ]
    return "\n".join(vivas)


def _bloco(fonte: Path, ancora: str) -> str:
    """Corpo de uma lista literal, da âncora até o primeiro ``]``.

    A âncora é curta e estável de propósito (um nome de constante ou de
    variável local); tudo o que estiver entre ela e o fecho é lido sem que a
    quebra de linha importe.
    """
    texto = fonte.read_text(encoding="utf-8")
    inicio = texto.find(ancora)
    assert inicio >= 0, (
        f"a âncora {ancora!r} sumiu de {fonte.name} — se ela foi renomeada, "
        f"renomeie aqui também; se a lista sumiu, esta regra precisa de outro dono"
    )
    fim = texto.index("]", inicio + len(ancora))
    return _sem_comentarios(texto[inicio + len(ancora): fim])


def _rotulos_de_pares(bloco: str) -> list[str]:
    """Os rótulos de uma lista de pares ``("id", "Rótulo")`` — Python ou Rust."""
    return [rotulo for _id, rotulo in re.findall(r'"([^"]*)"\s*,\s*"([^"]*)"', bloco)]


def _frases_soltas(bloco: str) -> list[str]:
    """Toda frase entre aspas duplas do bloco, na ordem em que aparece."""
    return re.findall(r'"([^"]*)"', bloco)


# ---------------------------------------------------------------------------
# Conceito 1 — os três modos ("O QUE O CONTROLE FAZ")
# ---------------------------------------------------------------------------

def test_os_tres_modos_tem_a_mesma_frase_e_a_mesma_ordem_na_janela_e_no_applet() -> None:
    """A frase-dona é a da aba Início; o applet reimplementa em Rust.

    ``home_actions._MODE_ITEMS`` contra o ``let entries`` do ``mode_block`` do
    applet. O comentário do próprio Rust promete a paridade
    (*"UX-MODE-TERMS-01: rótulos pela ação, em paridade com a GUI"*); aqui ela
    deixa de ser promessa.
    """
    janela = _rotulos_de_pares(_bloco(_JANELA_INICIO, "_MODE_ITEMS = ["))
    applet = _frases_soltas(_bloco(_APPLET, "let entries = ["))

    assert len(janela) == 3, f"a aba Início deixou de ter três modos: {janela}"
    assert janela == applet, (
        "os três modos divergiram entre a janela e o applet do painel.\n"
        f"  janela (home_actions._MODE_ITEMS): {janela}\n"
        f"  applet (app.rs, let entries):      {applet}\n"
        "Quem renomeia um modo renomeia nas duas superfícies — ela vê as duas."
    )


def test_a_janela_nao_tem_duas_listas_de_modo_divergentes() -> None:
    """A aba Perfis repete os mesmos três rótulos; repetir é poder divergir.

    ``profiles_actions._MODE_KIND_ITEMS`` acrescenta um quarto item no topo
    (``"Não mexer no modo"``, que é ausência de modo, não modo) e depois repete
    os três da Início. Os três têm de continuar iguais e na mesma ordem.
    """
    inicio = _rotulos_de_pares(_bloco(_JANELA_INICIO, "_MODE_ITEMS = ["))
    perfis = _rotulos_de_pares(
        _bloco(_JANELA_PERFIS, "_MODE_KIND_ITEMS: list[tuple[str, str]] = [")
    )

    assert perfis[0] == "Não mexer no modo", (
        f"a aba Perfis mudou o item de ausência de modo: {perfis!r}"
    )
    assert perfis[1:] == inicio, (
        "as abas Início e Perfis dizem os três modos de jeitos diferentes.\n"
        f"  Início: {inicio}\n"
        f"  Perfis: {perfis[1:]}"
    )


# ---------------------------------------------------------------------------
# Conceito 2 — as duas máscaras do gamepad virtual
# ---------------------------------------------------------------------------

def test_as_duas_mascaras_tem_as_mesmas_frases_nas_tres_listas() -> None:
    """As frases (não a ordem — a ordem está no livro de divergências, D1).

    Três listas dizem as mesmas duas máscaras: a aba Início, a aba Perfis e o
    ``mode_block`` do applet. Renomear ``Xbox 360`` ou
    ``DualSense (botões PlayStation)`` em uma só reprova aqui.
    """
    inicio = set(_rotulos_de_pares(_bloco(_JANELA_INICIO, "_FLAVOR_ITEMS = [")))
    perfis = set(
        _rotulos_de_pares(_bloco(_JANELA_PERFIS, "_MODE_FLAVOR_ITEMS: list[tuple[str, str]] = ["))
    )
    applet = set(_rotulos_de_pares(_bloco(_APPLET, "let flavors = [")))

    assert inicio == {"Xbox 360", "DualSense (botões PlayStation)"}, (
        f"a aba Início mudou o nome de uma máscara: {sorted(inicio)}"
    )
    assert inicio == perfis == applet, (
        "as máscaras têm nomes diferentes conforme a superfície.\n"
        f"  aba Início:  {sorted(inicio)}\n"
        f"  aba Perfis:  {sorted(perfis)}\n"
        f"  applet:      {sorted(applet)}"
    )


#: D1 da RADAR-01, remedida em 01/08/2026 e AINDA ABERTA — e a remedição achou
#: uma terceira lista que a sprint não tinha aberto: a aba **Perfis** concorda
#: com o applet e discorda da aba **Início**. Não é o applet contra a janela; é
#: a janela contra si mesma, com o applet do lado de uma das duas metades.
#: Quem decide a ordem canônica é a E1 daquela sprint, com o painel aberto na
#: frente dela — não este teste.
_ORDEM_DAS_MASCARAS_MEDIDA_EM_01_08 = {
    "janela/Início (home_actions._FLAVOR_ITEMS)": ["Xbox 360", "DualSense (botões PlayStation)"],
    "janela/Perfis (profiles_actions._MODE_FLAVOR_ITEMS)": [
        "DualSense (botões PlayStation)",
        "Xbox 360",
    ],
    "applet (app.rs, let flavors)": ["DualSense (botões PlayStation)", "Xbox 360"],
}


def test_o_livro_da_ordem_das_mascaras_esta_exato() -> None:
    """Trava de crescimento da D1: nem piora calada, nem cura calada.

    Enquanto a E1 não decide a ordem canônica, ela fica registrada aqui. Se uma
    quarta lista nascer divergente, ou se a ordem de qualquer uma das três
    mudar, este teste conta qual. E no dia em que as três se alinharem, ele
    reprova pedindo que este bloco vire uma igualdade simples — que é o que a
    E4 pediu desde o começo.
    """
    hoje = {
        "janela/Início (home_actions._FLAVOR_ITEMS)": _rotulos_de_pares(
            _bloco(_JANELA_INICIO, "_FLAVOR_ITEMS = [")
        ),
        "janela/Perfis (profiles_actions._MODE_FLAVOR_ITEMS)": _rotulos_de_pares(
            _bloco(_JANELA_PERFIS, "_MODE_FLAVOR_ITEMS: list[tuple[str, str]] = [")
        ),
        "applet (app.rs, let flavors)": _rotulos_de_pares(_bloco(_APPLET, "let flavors = [")),
    }

    if len({tuple(ordem) for ordem in hoje.values()}) == 1:
        raise AssertionError(
            "boa notícia: as três listas de máscara concordam na ordem — a D1 da "
            "RADAR-01 foi curada.\n"
            "Apague o _ORDEM_DAS_MASCARAS_MEDIDA_EM_01_08 e este teste, e troque "
            "os dois por uma igualdade de ordem no "
            "test_as_duas_mascaras_tem_as_mesmas_frases_nas_tres_listas."
        )

    assert hoje == _ORDEM_DAS_MASCARAS_MEDIDA_EM_01_08, (
        "a ordem das máscaras mudou em alguma superfície sem passar pela E1 da "
        "RADAR-01.\n"
        f"  medido em 01/08: {_ORDEM_DAS_MASCARAS_MEDIDA_EM_01_08}\n"
        f"  medido agora:    {hoje}"
    )


# ---------------------------------------------------------------------------
# Conceito 3 — a marca do item ativo numa lista
# ---------------------------------------------------------------------------

def test_a_marca_do_item_ativo_e_a_mesma_nas_tres_superficies_que_listam() -> None:
    """``"> "`` na bandeja, na janela compacta e no applet.

    A marca é ASCII de propósito nas três (o comentário da ``compact_window``
    diz: *"ASCII marker para não conflitar com sanitizer global"*), e o
    higienizador de glifos desta casa já comeu marca de item ativo antes — foi
    o que deixou o modo ativo do applet sem marca nenhuma, registrado no
    comentário do próprio ``mode_block``.
    """
    bandeja = re.search(
        r'^ACTIVE_MARKER\s*=\s*"([^"]*)"', _BANDEJA.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert bandeja is not None, "tray.ACTIVE_MARKER sumiu — esta regra perdeu o dono"
    marca = bandeja.group(1)
    assert marca == "> ", f"a bandeja mudou a marca do item ativo para {marca!r}"

    compacta = re.search(r'f"([^"{}]*)\{name\}"', _COMPACTA.read_text(encoding="utf-8"))
    assert compacta is not None, "a janela compacta perdeu o rótulo marcado do perfil ativo"
    assert compacta.group(1) == marca, (
        f"a janela compacta marca o item ativo com {compacta.group(1)!r} e a "
        f"bandeja com {marca!r}"
    )

    no_applet = set(
        re.findall(r'if is_active \{\s*"([^"]*)"', _APPLET.read_text(encoding="utf-8"))
    )
    assert no_applet, "o applet perdeu a marca do item ativo (era `if is_active { \"> \" }`)"
    assert no_applet == {marca}, (
        f"o applet marca o item ativo com {sorted(no_applet)} e a bandeja com {marca!r}"
    )


# ---------------------------------------------------------------------------
# Conceito 4 — a frase do botão que abre a janela
# ---------------------------------------------------------------------------

def test_abrir_painel_e_a_mesma_frase_na_bandeja_e_no_applet() -> None:
    """Os dois menus do painel oferecem a mesma ação; têm de a chamar igual."""
    assert '_("Abrir painel")' in _BANDEJA.read_text(encoding="utf-8"), (
        "a bandeja renomeou o item que abre a janela — confira o applet junto"
    )
    assert '"Abrir painel"' in _APPLET.read_text(encoding="utf-8"), (
        "o applet renomeou o item que abre a janela — confira a bandeja junto"
    )


# ---------------------------------------------------------------------------
# Conceito 5 — a frase de "o programa não está no ar"
# ---------------------------------------------------------------------------

#: A frase-dona, na janela. Ela fala do produto ("o Hefesto"), não do processo
#: ("o daemon"), que é a régua da PALAVRA-01.
_FRASE_DONA_DO_DESLIGADO = "O Hefesto está desligado"

#: Jargão de processo em rótulo de tela. Só as superfícies GRÁFICAS entram —
#: a CLI diz `daemon offline` de propósito, para quem digitou um comando.
_JARGAO_DE_DAEMON = ("daemon offline", "daemon desconectado")

#: Inventário MEDIDO em 01/08/2026 nas três superfícies secundárias, por
#: ``(superfície, frase)``. São exatamente as três que a RADAR-01 mediu em
#: 31/07 e que a E1 e a E3 daquela sprint decidem — nenhuma foi consertada
#: aqui, porque consertar exige tocar código de produto e o olho dela no
#: painel. A lista existe para que a QUARTA não entre calada.
_JARGAO_REGISTRADO_EM_01_08 = sorted(
    [
        ("APPLET", "Daemon desconectado"),
        ("APPLET", "Indisponível (daemon offline)"),
        ("COMPACTA", "Daemon offline"),
    ]
)


def _frases_de_tela(caminho: Path) -> list[str]:
    """Toda frase literal fora de comentário, para os dois idiomas de fonte.

    No Rust só aspas duplas são frase (aspas simples são ``char`` e tempo de
    vida); no Python valem as duas.
    """
    padrao = r'"([^"\n]*)"' if caminho.suffix == ".rs" else r'"([^"\n]*)"|\'([^\'\n]*)\''
    achados: list[str] = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        despida = linha.strip()
        if despida.startswith(("#", "//", "*", '"""', "'''")):
            continue
        for grupos in re.findall(padrao, linha):
            texto = grupos if isinstance(grupos, str) else next(g for g in grupos if g is not None)
            achados.append(texto)
    return achados


def test_a_janela_continua_dona_da_frase_do_desligado() -> None:
    """Se a frase-dona mudar, a regra abaixo precisa de manutenção — não de fé."""
    inicio = _JANELA_INICIO.read_text(encoding="utf-8")
    emulacao = _JANELA_EMULACAO.read_text(encoding="utf-8")

    assert _FRASE_DONA_DO_DESLIGADO in inicio and _FRASE_DONA_DO_DESLIGADO in emulacao, (
        f"a janela deixou de dizer {_FRASE_DONA_DO_DESLIGADO!r}. Se foi renomeação "
        "deliberada, a frase nova entra aqui E nas outras três superfícies no "
        "mesmo passo — que é a razão de existir deste arquivo."
    )


def test_nenhuma_superficie_nova_troca_o_hefesto_pelo_daemon() -> None:
    """Trava de crescimento do jargão de processo nas superfícies gráficas.

    A janela diz ``O Hefesto está desligado``. O applet diz
    ``Daemon desconectado`` e ``Indisponível (daemon offline)``; a janela
    compacta diz ``Daemon offline``. São três frases para um estado só, em três
    superfícies que ela pode ter abertas ao mesmo tempo.

    Consertar as três é a E1 e a E3 da RADAR-01 (decisão de produto, com o
    painel aberto na frente dela). O que este teste garante hoje é que não
    nasce uma quarta — e que, quando uma for curada, ninguém esquece de apagar
    a linha correspondente daqui.
    """
    hoje = sorted(
        (nome, frase)
        for nome, caminho in _SUPERFICIES_SECUNDARIAS.items()
        for frase in _frases_de_tela(caminho)
        if any(jargao in frase.lower() for jargao in _JARGAO_DE_DAEMON)
    )

    novas = [par for par in hoje if par not in _JARGAO_REGISTRADO_EM_01_08]
    assert not novas, (
        "jargão de daemon NOVO num rótulo de tela: "
        f"{novas}.\n"
        f"A janela chama este estado de {_FRASE_DONA_DO_DESLIGADO!r} — use a "
        "mesma frase, ou leve a divergência para a E1/E3 da RADAR-01 antes de "
        "registrá-la aqui."
    )

    curadas = [par for par in _JARGAO_REGISTRADO_EM_01_08 if par not in hoje]
    assert not curadas, (
        f"boa notícia: {curadas} saiu das superfícies — apague a linha "
        "correspondente do _JARGAO_REGISTRADO_EM_01_08 para que a trava não "
        "afrouxe."
    )
