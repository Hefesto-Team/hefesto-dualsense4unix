"""O script que fotografa as abas não pode fotografar dado REAL dela.

O `README.md` carrega este aviso, e ele é a razão deste arquivo existir:

    "Na aba Sistema, o bloco 'Detalhes técnicos' está borrado de propósito: o
     log mostra o endereço Bluetooth real dos controles desta máquina, e os
     gates de anonimato do projeto não varrem imagens."

Ou seja: uma foto da interface **já vazou endereço Bluetooth real** uma vez, e
a cura foi um borrão feito à mão. Agora que `scripts/gui-captura/retratar_abas.py`
grava direto em `docs/usage/assets/` — as imagens do README — um borrão manual
deixou de ser possível: ninguém revisa PNG a cada execução.

A segurança passa a vir da CONSTRUÇÃO: o script monta a janela do zero, do
`.glade`, e alimenta o card com os dublês da suíte, cujo MAC é falso. Ele
**nunca fala com o daemon**. Este arquivo trava isso.

**A mordida:** acrescentar ao script uma chamada a `daemon.state_full` (ou
qualquer leitura do daemon vivo) para "deixar a foto mais real" derruba estes
testes. E é exatamente o gesto tentador — a foto ficaria mais bonita, e
publicaria o MAC dela.
"""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "gui-captura" / "retratar_abas.py"

#: O que denuncia conversa com o daemon vivo. Não é lista de proibição
#: cosmética: cada um destes traz, no payload, MAC, nome de máquina ou caminho
#: de arquivo do computador de quem rodar.
_PORTAS_DO_DAEMON = (
    "state_full",
    "ipc_bridge",
    "_safe_call",
    "call_async",
    "daemon.status",
    "IPCClient",
    "ipc_socket_path",
)


def _fonte() -> str:
    assert SCRIPT.is_file(), f"{SCRIPT} sumiu — o retrato das abas é rotina desta casa"
    return SCRIPT.read_text(encoding="utf-8")


def test_o_script_nao_fala_com_o_daemon() -> None:
    """A foto não pode nascer de estado real: ela vai direto para `docs/`.

    A verificação é sobre o CÓDIGO, não sobre os comentários — a nota de
    privacidade do cabeçalho cita `daemon.state_full` de propósito, para
    explicar o que não fazer.
    """
    arvore = ast.parse(_fonte())
    # Só o código: docstrings e comentários ficam de fora por construção do AST.
    codigo = "\n".join(
        ast.unparse(no)
        for no in ast.walk(arvore)
        if isinstance(no, (ast.Call, ast.Attribute, ast.Import, ast.ImportFrom))
    )

    achados = [porta for porta in _PORTAS_DO_DAEMON if porta in codigo]

    assert not achados, (
        f"o retrato das abas passou a falar com o daemon ({', '.join(achados)}). "
        "O estado real carrega o MAC dos controles dela, e estas fotos vão "
        "DIRETO para docs/usage/assets/, que é o README — sem revisão humana e "
        "sem portão que varra imagens. Se a foto precisa de dado real, ela "
        "precisa de revisão antes de ser publicada, e o script não pode mais "
        "gravar em docs/."
    )


def test_o_card_e_alimentado_pelos_dubles_da_suite() -> None:
    """O MAC do dublê é falso por construção — é o que torna a foto segura."""
    fonte = _fonte()

    assert "test_status_faixa_blocos" in fonte, (
        "o script deixou de usar os dublês da suíte para alimentar o card. "
        "Um payload escrito à mão aqui vira um segundo dono do formato, e o "
        "primeiro que alguém copiar de uma sessão real traz o MAC dela junto."
    )


def test_o_duble_usado_tem_mac_falso() -> None:
    """Ancora a premissa: se o dublê ganhar MAC real, tudo acima cai.

    Este teste olha o DUBLÊ, não o script — porque a segurança do script
    depende inteiramente dele. A máscara da casa é octetos 4 e 5 zerados; o
    dublê vai além e usa um OUI que não existe.
    """
    from tests.unit.test_status_faixa_blocos import _ENTRY

    uniq = str(_ENTRY.get("uniq", ""))

    assert uniq, "o dublê perdeu o campo `uniq`"
    assert uniq.startswith(("aa:", "00:", "02:")), (
        f"o dublê da suíte passou a usar o MAC {uniq!r}, que não parece "
        "forjado. O retrato das abas o fotografa e publica em docs/."
    )
