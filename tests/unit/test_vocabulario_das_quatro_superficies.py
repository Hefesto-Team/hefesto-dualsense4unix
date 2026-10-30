"""RADAR-01/E4 — a mesma coisa tem de ter o mesmo nome em toda superfície."""
from __future__ import annotations

import re
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]

_JANELA_INICIO = _RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "actions" / "home_actions.py"
_TELA_JOGAR = (
    _RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "pacotes" / "a01_jogar.py"
)
_BANDEJA = _RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "tray.py"


_SUPERFICIES_SECUNDARIAS = {
    "BANDEJA": _BANDEJA,
}


def _sem_comentarios(texto: str) -> str:
    """Descarta linhas de comentário."""
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
        f"a âncora {ancora!r} sumiu de {fonte.name} — se foi renomeada, "
        f"renomeie aqui também; se a lista sumiu, esta regra precisa de outro dono"
    )
    fim = texto.index("]", inicio + len(ancora))
    return _sem_comentarios(texto[inicio + len(ancora): fim])


def _rotulos_de_pares(bloco: str) -> list[str]:
    """Os rótulos de uma lista de pares ``("id", "Rótulo")``."""
    return [rotulo for _id, rotulo in re.findall(r'"([^"]*)"\s*,\s*"([^"]*)"', bloco)]


def test_as_mascaras_tem_os_nomes_da_aba_inicio() -> None:
    """Renomear ``Xbox 360`` ou ``DualSense (botões PlayStation)`` reprova aqui."""
    inicio = set(_rotulos_de_pares(_bloco(_JANELA_INICIO, "_FLAVOR_ITEMS = [")))

    assert inicio == {
        "Xbox 360",
        "DualSense (botões PlayStation)",
        "Nintendo Pro (botões da Nintendo)",
    }, f"a aba Início mudou o nome de uma máscara: {sorted(inicio)}"


def test_a_marca_do_item_ativo_da_bandeja() -> None:
    """``"> "`` na bandeja."""
    bandeja = re.search(
        r'^ACTIVE_MARKER\s*=\s*"([^"]*)"', _BANDEJA.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert bandeja is not None, "tray.ACTIVE_MARKER sumiu — esta regra perdeu o dono"
    marca = bandeja.group(1)
    assert marca == "> ", f"a bandeja mudou a marca do item ativo para {marca!r}"


def test_abrir_programa_e_a_frase_da_bandeja() -> None:
    """O menu do painel chama a ação de abrir a janela sempre igual."""
    assert '_("Abrir programa")' in _BANDEJA.read_text(encoding="utf-8"), (
        "a bandeja renomeou o item que abre a janela"
    )


_FRASE_DONA_DO_DESLIGADO = "O Hefesto está desligado"

_JARGAO_DE_DAEMON = ("daemon offline", "daemon desconectado")

_JARGAO_REGISTRADO_EM_01_08: list[tuple[str, str]] = []


def _frases_de_tela(caminho: Path) -> list[str]:
    """Toda frase literal fora de comentário, para os dois idiomas de fonte."""
    padrao = r'"([^"\n]*)"|\'([^\'\n]*)\''
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
    """Se a frase-dona mudar, a regra abaixo precisa de manutenção — não de fé.

    Desde 20/10/2026 (D-2010-O-SERVICO-PARADO-NAO-GANHA-FRASE) a tela não escreve que o serviço
    parou; a frase sobrevive na recusa do cadeado (`CADEADO_RECUSA`), que é gesto da pessoa.
    """
    jogar = _TELA_JOGAR.read_text(encoding="utf-8")
    assert "CADEADO_RECUSA = " in jogar

    assert _FRASE_DONA_DO_DESLIGADO in jogar, (
        f"a janela deixou de dizer {_FRASE_DONA_DO_DESLIGADO!r}. Se foi renomeação "
        "deliberada, a frase nova entra aqui E nas outras superfícies no "
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
