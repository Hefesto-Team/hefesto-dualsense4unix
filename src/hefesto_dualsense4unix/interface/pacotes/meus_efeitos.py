"""Os efeitos que a pessoa cria: UM dono, uma chave por feature (A-BASE-COMUM-DAS-ABAS-01).

A biblioteca mora em `app/gui_prefs.py`, a caixa de preferências da própria interface. Cada
feature tem a sua chave, e a dos gatilhos (`gatilhos_meus_efeitos`) é a que já existia: mudar o
nome dela perderia o que a pessoa guardou. O item dos gatilhos segue o seu formato antigo
(`left`/`right`); o das outras features é `{nome, base, parametros}`.

Ausente quer dizer «ainda não guardou nenhum», e é diferente de «guardou e apagou todos»: por isso
as chaves não estão nos `_DEFAULTS` do `gui_prefs`.
"""
from __future__ import annotations

from typing import Any

from . import Contexto, gesto

#: A opção `meu:<nome>` das listas de efeito pronto é um efeito da biblioteca.
PREFIXO_DO_MEU = "meu:"

SEPARADOR_DOS_MEUS = "Meus efeitos"

GESTO_DE_CRIAR = "criar-efeito"

#: feature → chave na caixa de preferências. A dos gatilhos fica como era.
CHAVES: dict[str, str] = {
    "gatilhos": "gatilhos_meus_efeitos",
    "imersao": "imersao_meus_efeitos",
    "luz": "luz_meus_efeitos",
    "vibracao": "vibracao_meus_efeitos",
    "controles": "controles_meus_efeitos",
}

#: As features que criam pelo gesto `criar-efeito`; os gatilhos guardam pelo «Guardar» da aba.
CRIAM_PELO_GESTO = ("imersao", "luz", "vibracao", "controles")

TETO_DO_NOME = 40

TETO_DOS_PARAMETROS = 32

CHAVE_DOS_GATILHOS = CHAVES["gatilhos"]


def _chave(feature: str) -> str:
    if feature not in CHAVES:
        raise ValueError(
            f"{GESTO_DE_CRIAR}: a feature {feature!r} não tem biblioteca. "
            f"As que têm: {', '.join(sorted(CHAVES))}")
    return CHAVES[feature]


def meus_efeitos(feature: str = "gatilhos") -> dict[str, Any]:
    """Os efeitos que a pessoa guardou naquela feature, do disco. `{}` quando não há nenhum.

    NUNCA LEVANTA por causa do arquivo: `load_gui_prefs` engole `JSONDecodeError` e `OSError` e
    devolve os padrões. Um arquivo corrompido não pode derrubar a pintura da aba inteira.
    """
    chave = _chave(feature)
    try:
        from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs

        guardado = load_gui_prefs().get(chave)
    except Exception:
        return {}
    if not isinstance(guardado, dict):
        return {}
    return {str(nome): valor for nome, valor in guardado.items()
            if isinstance(valor, dict) and str(nome).strip()}


def guardar_meus_efeitos(todos: dict[str, Any], feature: str = "gatilhos") -> None:
    """Escreve a biblioteca de volta, PRESERVANDO o resto das preferências.

    O `load` antes do `save` não é cerimônia: `save_gui_prefs` grava o dicionário INTEIRO, e
    escrever só a nossa chave apagaria o `advanced_editor` e o `ambiente_corrigido` dela.
    """
    from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs, save_gui_prefs

    chave = _chave(feature)
    prefs = load_gui_prefs()
    prefs[chave] = todos
    save_gui_prefs(prefs)


def _parametros_limpos(cru: Any) -> dict[str, Any] | list[Any]:
    """Os parâmetros do efeito: um dicionário ou uma lista de valores simples, e pequenos."""
    simples = (bool, int, float, str)
    if isinstance(cru, dict):
        limpo = {str(k): v for k, v in cru.items() if isinstance(v, simples)}
        if len(limpo) != len(cru) or len(limpo) > TETO_DOS_PARAMETROS:
            raise ValueError("os parâmetros do efeito têm de ser valores simples e poucos")
        return limpo
    if isinstance(cru, list):
        if len(cru) > TETO_DOS_PARAMETROS or not all(isinstance(v, simples) for v in cru):
            raise ValueError("os parâmetros do efeito têm de ser valores simples e poucos")
        return list(cru)
    raise ValueError("os parâmetros do efeito vêm como lista ou como dicionário")


def criar_efeito(feature: str, nome: str, base: str, parametros: Any) -> dict[str, Any]:
    """Guarda um efeito novo na biblioteca da feature e devolve o item `{nome, base, parametros}`.

    O mesmo nome sobrescreve o antigo: é a pessoa refinando o efeito que criou.
    """
    if feature not in CRIAM_PELO_GESTO:
        raise ValueError(
            f"{GESTO_DE_CRIAR}: a feature {feature!r} não cria por aqui. "
            f"As que criam: {', '.join(CRIAM_PELO_GESTO)}")
    apelido = str(nome or "").strip()
    if not apelido or len(apelido) > TETO_DO_NOME:
        raise ValueError(
            f"{GESTO_DE_CRIAR}: o nome do efeito tem de ter de 1 a {TETO_DO_NOME} letras")
    origem = str(base or "").strip()
    if not origem:
        raise ValueError(f"{GESTO_DE_CRIAR}: o efeito não disse em cima de qual ele nasce")
    item = {"nome": apelido, "base": origem, "parametros": _parametros_limpos(parametros)}
    todos = meus_efeitos(feature)
    todos[apelido] = item
    guardar_meus_efeitos(todos, feature)
    return item


@gesto("*", GESTO_DE_CRIAR, grava="guardar_meus_efeitos")
def criar_efeito_novo(ctx: Contexto, o: dict[str, Any], p: Any) -> None:
    """A área «Criar efeitos novos» das abas: guarda na biblioteca da feature da própria aba.

    O clique manda `feature` (`imersao`, `luz`, `vibracao` ou `controles`), `nome`, `base` e
    `parametros`. Grava só a caixa de preferências da interface: nenhum perfil, nenhum aparelho.
    """
    criar_efeito(str(o.get("feature") or ""), str(o.get("nome") or ""),
                 str(o.get("base") or ""), o.get("parametros"))
