"""Se o efeito escolhido chegou ao controle: o campo pergunta ao recibo do daemon, nunca ao eco.

O recibo vem no `state_full` (`controllers[].efeitos`, de `daemon/o_recibo_dos_efeitos.py`). Um
dono só para as quatro listas de efeito (Gatilhos, Iluminação, Efeito háptico e Padrão dos
motores): o estado do campo, a dica e a marca HTML. Só `chegou` diz que o controle recebeu.
"""
from __future__ import annotations

from typing import Any

CHEGOU = "chegou"
A_CAMINHO = "a-caminho"
FORA_DO_AR = "fora-do-ar"
SEM_CONTROLE = "sem-controle"
JOGO = "jogo"
SEM_RECIBO = "sem-recibo"
CAMPOS = ("gatilho_e", "gatilho_d", "luz", "haptica", "motores")
PREFIXO = "chegada-"
PREFIXO_DA_DICA = "chegada-dica-"

DICAS = {
    CHEGOU: "O controle recebeu.",
    A_CAMINHO: "Ainda não chegou ao controle.",
    FORA_DO_AR: "O Hefesto não está rodando: nada chega ao controle.",
    SEM_CONTROLE: "O controle não está ligado.",
    JOGO: "O jogo decide agora.",
    SEM_RECIBO: "O controle não confirma este efeito.",
}

CSS = (
    ".chegada{position:absolute;top:-3px;right:-3px;z-index:2;display:block;width:8px;"
    "height:8px;border-radius:50%;background:transparent}"
    '.chegada[data-chegada="chegou"]{background:var(--green,#50fa7b)}'
    '.chegada[data-chegada="a-caminho"]{background:var(--yellow,#f1fa8c)}'
    '.chegada[data-chegada="fora-do-ar"]{background:var(--red,#ff5555)}'
    '.chegada[data-chegada="jogo"]{background:var(--cyan,#8be9fd)}'
    '.chegada[data-chegada="sem-recibo"]{box-shadow:inset 0 0 0 1px var(--comment,#6272a4)}'
)


def o_daemon_respondeu(state: dict[str, Any] | None) -> bool:
    """O tique leu o `state_full`: a folga do serviço mudo pinta `{}` quando ele não responde."""
    return isinstance(state, dict) and isinstance(state.get("controllers"), list)


def chegada(state: dict[str, Any] | None, entrada: dict[str, Any] | None, campo: str,
            *, anima: bool | None = None) -> str:
    """O estado do campo `campo` do controle `entrada` (a linha dele em `controllers`).

    ``anima`` é o que a escolha da luz pede (um efeito animado, ou a barra parada); ``None`` não
    confere.
    """
    if not o_daemon_respondeu(state):
        return FORA_DO_AR
    if not entrada or not entrada.get("connected", True):
        return SEM_CONTROLE
    efeitos = entrada.get("efeitos")
    recibo = efeitos.get(campo) if isinstance(efeitos, dict) else None
    if not isinstance(recibo, dict):
        return SEM_RECIBO
    porque = recibo.get("porque")
    if porque == "jogo":
        return JOGO
    if porque == "fora_do_fio":
        return SEM_CONTROLE
    if recibo.get("chegou") is not True:
        return A_CAMINHO
    if anima is not None and bool(recibo.get("anima")) != anima:
        return A_CAMINHO
    return CHEGOU


def campos_da_coluna(sufixo: str, estado: str) -> dict[str, str]:
    """As duas chaves que a pintura escreve na coluna: o estado do ponto e a frase da célula."""
    return {f"{PREFIXO}{sufixo}": estado, f"{PREFIXO_DA_DICA}{sufixo}": DICAS[estado]}


def do_lugar_vazio(state: dict[str, Any] | None, sufixos: tuple[str, ...]) -> dict[str, str]:
    """As marcas de um lugar sem controle: fora do ar se o daemon não respondeu ao tique."""
    estado = SEM_CONTROLE if o_daemon_respondeu(state) else FORA_DO_AR
    campos: dict[str, str] = {}
    for sufixo in sufixos:
        campos.update(campos_da_coluna(sufixo, estado))
    return campos


def marca(sufixo: str, estado: str = SEM_CONTROLE) -> str:
    """O ponto do campo, com o estado em `data-chegada`; a frase mora na célula (`dica`)."""
    return (f'<i class="chegada" data-campo="{PREFIXO}{sufixo}" data-hef-alvo="atributo" '
            f'data-hef-atributo="data-chegada" data-chegada="{estado}" aria-hidden="true"></i>')


def dica(sufixo: str, estado: str = SEM_CONTROLE) -> str:
    """Os atributos da frase na célula que contém a lista, que por isso não vira parada de foco.

    O ponto sozinho com `data-dica` ganharia `tabindex` (alvo de 8 px); a célula já tem a lista.
    """
    return (f' data-campo="{PREFIXO_DA_DICA}{sufixo}" data-hef-alvo="atributo" '
            f'data-hef-atributo="data-dica" data-dica="{DICAS[estado]}"')
