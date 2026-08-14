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

O FIXTURE DA MESA CHEIA, E POR QUE ELE NÃO É A MESMA COISA (14/08/2026)
-----------------------------------------------------------------------

O modo `--mesa-cheia` alimenta as abas com
`tests/fixtures/state_full_quatro_controles.json`. **Isso não afrouxa nada, e a
distinção é a que este arquivo inteiro protege:**

* o que a garantia proíbe é **estado VIVO** entrar numa imagem versionada sem
  revisão humana — o MAC, o nome de rede e o caminho de arquivo da máquina de
  quem rodar o script, que chegariam por IPC no instante da foto;
* o fixture é **arquivo do repositório**. Ele entrou por um commit, e a máscara
  dele é a de `tests/`, que é mais severa que a de `docs/`: o portão de
  fixtures é allowlist de PREFIXO, e reprova até OUI de fabricante real.

Por isso o proibido aqui é o nome do MÉTODO de IPC (`daemon.state_full`) e
todo transporte que o alcança — nunca o pedaço de texto `state_full`, que é
também o nome do arquivo versionado. Um teste que reprovasse pelo nome do
arquivo ensinaria a esconder o nome, que é o contrário de tudo isto.

O `test_a_unica_fonte_de_estado_e_o_fixture_versionado` fecha o outro lado:
todo caminho de dado que o script lê tem de morar em `tests/fixtures/`.
"""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "gui-captura" / "retratar_abas.py"

#: O que denuncia conversa com o daemon vivo. Não é lista de proibição
#: cosmética: cada um destes traz, no payload, MAC, nome de máquina ou caminho
#: de arquivo do computador de quem rodar.
#:
#: `daemon.state_full` entra com o prefixo do MÉTODO, e não como `state_full`
#: solto: desde 14/08 o script lê um fixture VERSIONADO com esse nome, e barrar
#: o texto puro reprovaria o arquivo do repositório junto com a chamada de IPC
#: — ver a nota do cabeçalho. Todo transporte que alcança o daemon continua
#: aqui, então a chamada não tem por onde entrar disfarçada.
#:
#: `ipc_client`/`IpcClient` foram acrescentados no mesmo dia, e não por
#: simetria: a classe real chama-se `IpcClient` (`cli/ipc_client.py`), e a
#: lista só tinha `IPCClient`, com outra caixa. `from ... .ipc_client import
#: IpcClient` passava VERDE por esse buraco — a porta mais direta de todas
#: estava aberta.
_PORTAS_DO_DAEMON = (
    "daemon.state_full",
    "ipc_bridge",
    "ipc_client",
    "IpcClient",
    "_safe_call",
    "call_async",
    "daemon.status",
    "IPCClient",
    "ipc_socket_path",
)

#: Onde um dado de entrada do script pode morar. Só o repositório, e só a
#: pasta que os portões de anonimato de `tests/` varrem.
_PASTA_DOS_FIXTURES = "tests/fixtures/"


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


def test_a_unica_fonte_de_estado_e_o_fixture_versionado() -> None:
    """Todo `.json` que o script lê tem de morar em `tests/fixtures/`.

    O outro lado da moeda do teste acima. Aquele barra a conversa com o daemon;
    este barra o atalho de ler um payload de qualquer outro lugar — um arquivo
    solto em `/tmp`, um despejo dentro de `~/.config`, um caminho da máquina
    dela. Sob `tests/fixtures/` o dado passa pelos portões de anonimato da
    suíte; fora de lá, por nenhum.
    """
    fonte = _fonte()
    caminhos = [
        trecho
        for trecho in fonte.split('"')
        if trecho.endswith(".json") and "/" in trecho
    ]

    assert caminhos, (
        "o script parou de citar qualquer arquivo de dados. Se o modo mesa "
        "cheia sumiu, some com este teste junto; se ele passou a receber o "
        "payload por outro caminho, este teste tem de aprender o caminho novo."
    )
    fora = [c for c in caminhos if not c.startswith(_PASTA_DOS_FIXTURES)]
    assert not fora, (
        f"o retrato das abas passou a ler dado de fora de "
        f"{_PASTA_DOS_FIXTURES}: {fora}. Só ali os portões de anonimato de "
        "`tests/` garantem a máscara — e estas fotos vão para o repositório "
        "sem revisão humana."
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
