"""RADAR-01/E4 — a mesma coisa tem de ter o mesmo nome nas QUATRO superfícies."""
from __future__ import annotations

import re
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]

_JANELA_INICIO = _RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions" / "home_actions.py"
_TELA_JOGAR = (
    _RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "pacotes" / "a01_jogar.py"
)
_APPLET = _RAIZ / "packaging" / "cosmic-applet" / "src" / "app.rs"
_BANDEJA = _RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "tray.py"


_SUPERFICIES_SECUNDARIAS = {
    "APPLET": _APPLET,
    "BANDEJA": _BANDEJA,
}


def _sem_comentarios(texto: str) -> str:
    """Descarta linhas de comentário (Python e Rust)."""
    vivas = [
        linha
        for linha in texto.splitlines()
        if not linha.strip().startswith(("#", "//", "*", "<!--"))
    ]
    return "\n".join(vivas)


def _bloco(fonte: Path, ancora: str) -> str:
    """Corpo de uma lista literal, da âncora até o primeiro ``]``."""
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


def test_os_tres_modos_tem_a_mesma_frase_e_a_mesma_ordem_na_janela_e_no_applet() -> None:
    """A frase-dona é a da aba Início; o applet reimplementa em Rust."""
    janela = _rotulos_de_pares(_bloco(_JANELA_INICIO, "_MODE_ITEMS = ["))
    applet = _frases_soltas(_bloco(_APPLET, "let entries = ["))

    assert len(janela) == 3, f"a aba Início deixou de ter três modos: {janela}"
    assert janela == applet, (
        "os três modos divergiram entre a janela e o applet do painel.\n"
        f"  janela (home_actions._MODE_ITEMS): {janela}\n"
        f"  applet (app.rs, let entries):      {applet}\n"
        "Quem renomeia um modo renomeia nas duas superfícies — ela vê as duas."
    )


def test_as_mascaras_tem_as_mesmas_frases_nas_duas_listas() -> None:
    """As frases (não a ordem — a ordem está no livro de divergências, D1).

    Duas listas dizem as mesmas máscaras: a aba Início e o ``mode_block`` do
    applet (a lista da aba Perfis da janela GTK saiu com ela em 02/10/2026).
    Renomear ``Xbox 360`` ou ``DualSense (botões PlayStation)`` em uma só reprova
    aqui.

    NOTA DATADA — 07/09/2026: eram DUAS, e a régua as digitava. A máscara
    **Nintendo Pro** nasceu por ordem de produto e teve de entrar nas três listas —
    inclusive no ``app.rs``, que é a superfície que ninguém lembra, e que só
    apareceu porque esta régua reprovou. É a razão de ela existir.
    """
    inicio = set(_rotulos_de_pares(_bloco(_JANELA_INICIO, "_FLAVOR_ITEMS = [")))
    applet = set(_rotulos_de_pares(_bloco(_APPLET, "let flavors = [")))

    assert inicio == {
        "Xbox 360",
        "DualSense (botões PlayStation)",
        "Nintendo Pro (botões da Nintendo)",
    }, f"a aba Início mudou o nome de uma máscara: {sorted(inicio)}"
    assert inicio == applet, (
        "as máscaras têm nomes diferentes conforme a superfície.\n"
        f"  aba Início:  {sorted(inicio)}\n"
        f"  applet:      {sorted(applet)}"
    )


#: de continuar medindo o que media  # (noqa-acento: verbo medir, imperfeito)
_ORDEM_DAS_MASCARAS_MEDIDA_EM_01_08 = {
    "janela/Início (home_actions._FLAVOR_ITEMS)": [
        "Xbox 360",
        "DualSense (botões PlayStation)",
        "Nintendo Pro (botões da Nintendo)",
    ],
    "applet (app.rs, let flavors)": [
        "DualSense (botões PlayStation)",
        "Xbox 360",
        "Nintendo Pro (botões da Nintendo)",
    ],
}


def test_o_livro_da_ordem_das_mascaras_esta_exato() -> None:
    """Trava de crescimento da D1: nem piora calada, nem cura calada."""
    hoje = {
        "janela/Início (home_actions._FLAVOR_ITEMS)": _rotulos_de_pares(
            _bloco(_JANELA_INICIO, "_FLAVOR_ITEMS = [")
        ),
        "applet (app.rs, let flavors)": _rotulos_de_pares(_bloco(_APPLET, "let flavors = [")),
    }

    if len({tuple(ordem) for ordem in hoje.values()}) == 1:
        raise AssertionError(
            "boa notícia: as duas listas de máscara concordam na ordem — a D1 da "
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


def test_a_marca_do_item_ativo_e_a_mesma_nas_duas_superficies_que_listam() -> None:
    """``"> "`` na bandeja e no applet."""
    bandeja = re.search(
        r'^ACTIVE_MARKER\s*=\s*"([^"]*)"', _BANDEJA.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert bandeja is not None, "tray.ACTIVE_MARKER sumiu — esta regra perdeu o dono"
    marca = bandeja.group(1)
    assert marca == "> ", f"a bandeja mudou a marca do item ativo para {marca!r}"

    no_applet = set(
        re.findall(r'if is_active \{\s*"([^"]*)"', _APPLET.read_text(encoding="utf-8"))
    )
    assert no_applet, "o applet perdeu a marca do item ativo (era `if is_active { \"> \" }`)"
    assert no_applet == {marca}, (
        f"o applet marca o item ativo com {sorted(no_applet)} e a bandeja com {marca!r}"
    )


def test_abrir_painel_e_a_mesma_frase_na_bandeja_e_no_applet() -> None:
    """Os dois menus do painel oferecem a mesma ação; têm de a chamar igual."""
    assert '_("Abrir painel")' in _BANDEJA.read_text(encoding="utf-8"), (
        "a bandeja renomeou o item que abre a janela — confira o applet junto"
    )
    assert '"Abrir painel"' in _APPLET.read_text(encoding="utf-8"), (
        "o applet renomeou o item que abre a janela — confira a bandeja junto"
    )


_FRASE_DONA_DO_DESLIGADO = "O Hefesto está desligado"

_JARGAO_DE_DAEMON = ("daemon offline", "daemon desconectado")

_JARGAO_REGISTRADO_EM_01_08 = sorted(
    [
        ("APPLET", "Daemon desconectado"),
        ("APPLET", "Indisponível (daemon offline)"),
    ]
)


def _frases_de_tela(caminho: Path) -> list[str]:
    """Toda frase literal fora de comentário, para os dois idiomas de fonte."""
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
    jogar = _TELA_JOGAR.read_text(encoding="utf-8")

    assert _FRASE_DONA_DO_DESLIGADO in jogar, (
        f"a janela deixou de dizer {_FRASE_DONA_DO_DESLIGADO!r}. Se foi renomeação "
        "deliberada, a frase nova entra aqui E nas outras três superfícies no "
        "mesmo passo — que é a razão de existir deste arquivo."
    )


def test_nenhuma_superficie_nova_troca_o_hefesto_pelo_daemon() -> None:
    """Trava de crescimento do jargão de processo nas superfícies gráficas."""
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
