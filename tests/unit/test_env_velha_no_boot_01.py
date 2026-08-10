"""ENV-VELHA-NO-BOOT-01 — o daemon subia novo e servia o arquivo do daemon velho.

A PERGUNTA DELA, 10/08/2026
==========================
Depois de eu explicar que o `launch_env` só é regravado quando o gamepad virtual
muda de estado, ela respondeu:

    *"temos soluções que não dependam desse feito manual? Tipo mais automático
    de fato?"*

Tinha razão, e o buraco era estrutural.

O QUE FOI MEDIDO
================
Todos os gatilhos de `materialize_launch_env` eram de TRANSIÇÃO — start/stop do
gamepad (`subsystems/gamepad.py`), Modo Nativo (`lifecycle.set_native_mode`),
co-op (`subsystems/coop.py`) e os handlers de IPC. **Nenhum no start do daemon.**

Provado no disco dela: apagado o `steam_app_3357650.env`, reiniciado o daemon, o
arquivo **não voltou**. O `launch_env_materializado` do journal continuou datado
do ciclo anterior.

POR QUE ISSO É PIOR DO QUE PARECE
=================================
O preço aparecia exatamente no pior momento: **quando uma cura acabava de
entrar.** O daemon subia com o código novo e continuava servindo ao wrapper o
arquivo escrito pelo daemon ANTIGO — então a cura do TRES-CONTROLES-01 (esconder
o espelho do Steam Input) nasceu inerte na máquina dela, e só valeria no próximo
plug do controle.

É a versão em ARQUIVO do padrão que esta casa já conhecia com processos: quem
estava velho não era o daemon, era o que ele tinha deixado no disco.
"""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LIFECYCLE = RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "lifecycle.py"


def _corpo_do_start() -> ast.AsyncFunctionDef:
    """A corotina que sobe o daemon — a que termina esperando o stop_event."""
    arvore = ast.parse(LIFECYCLE.read_text(encoding="utf-8"), filename=str(LIFECYCLE))
    for no in ast.walk(arvore):
        if not isinstance(no, ast.AsyncFunctionDef):
            continue
        fonte = ast.dump(no)
        if "_stop_event" in fonte and "daemon_starting" in fonte:
            return no
    raise AssertionError("não achei a corotina de start do daemon")


def _chama(no: ast.AST, nome: str) -> bool:
    return any(
        isinstance(c, ast.Call)
        and (
            (isinstance(c.func, ast.Name) and c.func.id == nome)
            or (isinstance(c.func, ast.Attribute) and c.func.attr == nome)
        )
        for c in ast.walk(no)
    )


def test_o_boot_do_daemon_materializa_o_launch_env() -> None:
    """A cura. Morde ao arrancar a chamada do `start`.

    Arranque para ver reprovar: apagar o bloco `materialize_launch_env(self)` do
    fim do `start`. É o estado do produto até 10/08/2026 — e o efeito é o
    arquivo do daemon ANTIGO continuar valendo depois de um restart.

    O teste é por AST e não por execução porque subir o daemon de verdade num
    unitário exigiria backend, IPC e laço de eventos; o que se afirma aqui é
    estrutural e é exatamente o que faltava: **existe uma chamada no caminho de
    boot**.
    """
    assert _chama(_corpo_do_start(), "materialize_launch_env"), (
        "o start do daemon não materializa o launch_env — o arquivo do ciclo "
        "anterior continua valendo até a primeira transição do gamepad"
    )


def test_a_materializacao_vem_depois_do_perfil_restaurado() -> None:
    """A ordem é a cura; inverter troca um defeito por outro.

    O conteúdo do `.env` sai do estado REAL — modo, máscara, backends e perfil
    ativo. Materializar antes do `restore_last_profile` gravaria um estado
    provisório, e regravar com dado provisório é pior que não regravar: o
    wrapper leria uma máscara que ela não escolheu.

    Morde ao subir a chamada para antes do `connect` inicial.
    """
    start = _corpo_do_start()
    linha_restore = max(
        (n.lineno for n in ast.walk(start) if _chama(n, "restore_last_profile")),
        default=None,
    )
    linha_materialize = max(
        (n.lineno for n in ast.walk(start) if _chama(n, "materialize_launch_env")),
        default=None,
    )
    assert linha_restore is not None, "o boot não restaura mais o perfil?"
    assert linha_materialize is not None
    assert linha_materialize > linha_restore, (
        "materializar antes de restaurar o perfil grava um estado provisório"
    )


def test_a_materializacao_do_boot_nao_derruba_o_start() -> None:
    """Materialização quebrada não pode custar o daemon inteiro.

    É a regra que a própria `materialize_launch_env` já declara ("NUNCA propaga
    exceção"), e aqui ela é reafirmada do lado de fora: a chamada do boot mora
    dentro de um `contextlib.suppress`. Sem isso, um disco cheio ou um
    `~/.local/state` sem permissão passaria a impedir o Hefesto de subir — um
    arquivo de 200 bytes derrubando o produto.

    Morde ao tirar o `with contextlib.suppress(Exception):` de volta.
    """
    start = _corpo_do_start()
    protegidas = [
        n
        for n in ast.walk(start)
        if isinstance(n, ast.With) and _chama(n, "materialize_launch_env")
    ]
    assert protegidas, "a chamada do boot não está dentro de um `with`"
    assert any(_chama(w.items[0].context_expr, "suppress") for w in protegidas), (
        "a materialização do boot tem de estar sob `contextlib.suppress`"
    )
