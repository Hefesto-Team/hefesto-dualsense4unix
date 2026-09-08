"""O retratista das abas não pode fotografar dado REAL dela.

O `README.md` carrega este aviso, e ele é a razão deste arquivo existir:

    "Na aba Sistema, o bloco 'Detalhes técnicos' está borrado de propósito: o
     log mostra o endereço Bluetooth real dos controles desta máquina, e os
     gates de anonimato do projeto não varrem imagens."

Ou seja: uma foto da interface **já vazou endereço Bluetooth real** uma vez, e
a cura foi um borrão feito à mão. Quem grava direto em `docs/usage/assets/` —
as imagens do README — não pode contar com borrão: ninguém revisa PNG a cada
execução, e os portões de anonimato desta casa **não leem imagem** (o `-I` do
`check_anonymity.sh` existe justamente porque eles nunca souberam).

A segurança vem da CONSTRUÇÃO, e a construção mudou de dono — 08/09/2026
------------------------------------------------------------------------

**A CAUSA MEDIDA:** até hoje este arquivo apontava para
`scripts/gui-captura/retratar_abas.py`, que montava a JANELA GTK do `.glade` e
alimentava o card com os dublês da suíte. **A janela saiu inteira em 06/09/2026
por decisão dela** (`D-0609-GTK-LEVA-INTEIRA`) e o retratista saiu com ela — o
Passo 2 da `GTK-3` removeu o script, e o Passo 1 ("os 62 testes, um a um") não
alcançou este arquivo. O resultado foi uma régua de ANONIMATO apontada para um
caminho que não existe: `_fonte()` morria no `assert SCRIPT.is_file()` e os
três testes ficavam vermelhos — que é o pior estado possível para um portão de
vazamento, porque vermelho constante se lê como ruído e se desliga.

**O fato não caducou; o dono mudou.** Quem grava em `docs/usage/assets/` hoje é
`src/hefesto_dualsense4unix/interface/olhar.py --todas --publicado --doc`, e o
`CLAUDE.md` já manda rodá-lo antes de commitar. Ele fotografa PÁGINA HTML num
Chrome headless, e é por isso que a garantia continua valendo — e continua
podendo ser quebrada pelo mesmo gesto tentador de sempre: ligar o retratista ao
daemon vivo para "deixar a foto mais real", e publicar o MAC dela junto.

O QUE MUDOU NA FORMA DA GARANTIA, e é o que faz esta régua morder hoje
----------------------------------------------------------------------

A janela lia estado por IPC no instante da foto. A página HTML não lê nada: ela
é um arquivo do repositório, e o retratista abre `file://`. Então a régua tem
duas metades, e a segunda é nova:

1. **nenhuma porta do daemon no código** — a lista abaixo é a mesma de sempre,
   e cada nome dela traz no payload MAC, nome de máquina ou caminho de arquivo
   de quem rodar;
2. **a foto só nasce de página do repositório** — nenhum literal executável do
   retratista aponta para `$HOME`, para a rede ou para `/proc`. É o outro lado
   da moeda: barrada a conversa com o daemon, o atalho que sobra é abrir
   qualquer outra coisa e fotografar.

E o que a página CONTÉM não se mede aqui de propósito: ela é arquivo versionado
e passa pelos DOIS portões de anonimato desta casa — o `test_docs_mac_anonimato`
(por OUI) e o `check_endereco_de_radio.py` (por FORMA), que varrem todo arquivo
que o `git ls-files` lista. Uma terceira régua sobre o mesmo texto seria
verbosidade; o buraco que só ESTE arquivo pode tapar é o do instrumento.

O QUE SAIU JUNTO COM A JANELA, e quem herdou
---------------------------------------------

* `test_a_unica_fonte_de_estado_e_o_fixture_versionado` cobrava que todo `.json`
  lido morasse em `tests/fixtures/`. O retratista de hoje não lê `.json`
  nenhum — o modo `--mesa-cheia` era da janela. **Herdeiro:**
  `test_a_foto_so_nasce_de_pagina_do_repositorio`, que é a mesma pergunta
  ("de onde vem o dado da foto?") sobre o instrumento que existe.
* `test_o_card_e_alimentado_pelos_dubles_da_suite` e
  `test_o_duble_usado_tem_mac_falso` ancoravam o dublê que alimentava o
  `controller_card` do GTK. Não há card montado em widget nesta foto.
  **Herdeiro:** os dois portões de anonimato do parágrafo acima, que medem a
  página — o que de fato é fotografado hoje.

A MORDIDA
---------

Aplicada em 08/09/2026, as duas, e as duas reprovaram:

* acrescente `from hefesto_dualsense4unix.cli.ipc_client import IpcClient` ao
  `olhar.py` — `test_o_script_nao_fala_com_o_daemon` reprova nomeando
  `ipc_client, IpcClient`;
* troque o `pg.goto(f"file://{alvo}")` por `pg.goto("http://localhost:8080")` —
  `test_a_foto_so_nasce_de_pagina_do_repositorio` reprova nomeando o literal.
"""

from __future__ import annotations

import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

#: QUEM GRAVA EM `docs/usage/assets/` HOJE. O caminho está no `CLAUDE.md` e no
#: `test_as_fotos_acompanham_a_versao`, que cobra o gesto de rodá-lo.
SCRIPT = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "olhar.py"

#: O que denuncia conversa com o daemon vivo. Não é lista de proibição
#: cosmética: cada um destes traz, no payload, MAC, nome de máquina ou caminho
#: de arquivo do computador de quem rodar.
#:
#: `ipc_client`/`IpcClient` não estão aqui por simetria com `IPCClient`: a
#: classe real chama-se `IpcClient` (`cli/ipc_client.py`), e enquanto a lista
#: só tinha a caixa `IPCClient` um `from ... .ipc_client import IpcClient`
#: passava VERDE — a porta mais direta de todas estava aberta.
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

#: De onde uma foto NÃO pode nascer. `/home/` e `~` são a máquina de quem roda;
#: `http`/`https` é a rede (um servidor local servindo a página viva do piloto
#: é o atalho mais plausível de todos); `/proc`, `/sys` e `/run` são o estado do
#: sistema, e `/run` é onde mora o socket do daemon.
_FONTES_PROIBIDAS = ("/home/", "~/", "http://", "https://", "/proc/", "/sys/", "/run/")


def _fonte() -> str:
    assert SCRIPT.is_file(), (
        f"{SCRIPT} sumiu. Se o retratista mudou de casa de novo, este portão "
        "muda com ele — apagá-lo é deixar a próxima foto publicar o MAC dela."
    )
    return SCRIPT.read_text(encoding="utf-8")


def _arvore() -> ast.Module:
    return ast.parse(_fonte())


def test_o_script_nao_fala_com_o_daemon() -> None:
    """A foto não pode nascer de estado real: ela vai direto para `docs/`.

    A verificação é sobre o CÓDIGO, não sobre os comentários — a nota de
    privacidade do cabeçalho cita `daemon.state_full` de propósito, para
    explicar o que não fazer. (E é a mesma armadilha de prosa que já mordeu
    esta casa três vezes: um comentário que CITA o padrão proibido vira a
    primeira ocorrência dele. Aqui o `ast` a desarma por construção.)
    """
    # Só o código: docstrings e comentários ficam de fora por construção do AST.
    codigo = "\n".join(
        ast.unparse(no)
        for no in ast.walk(_arvore())
        if isinstance(no, (ast.Call, ast.Attribute, ast.Import, ast.ImportFrom))
    )

    achados = [porta for porta in _PORTAS_DO_DAEMON if porta in codigo]

    assert not achados, (
        f"o retratista das abas passou a falar com o daemon ({', '.join(achados)}). "
        "O estado real carrega o MAC dos controles dela, e estas fotos vão "
        "DIRETO para docs/usage/assets/, que é o README — sem revisão humana e "
        "sem portão que varra imagens. Se a foto precisa de dado real, ela "
        "precisa de revisão antes de ser publicada, e o script não pode mais "
        "gravar em docs/."
    )


def test_a_foto_so_nasce_de_pagina_do_repositorio() -> None:
    """Todo caminho que o retratista abre tem de ser do repositório.

    O outro lado da moeda do teste acima. Aquele barra a conversa com o daemon;
    este barra o atalho de fotografar qualquer outra coisa — a página servida
    por um servidor local, um despejo em `~/.config`, um caminho da máquina de
    quem roda. A página do repositório passa pelos dois portões de anonimato da
    casa; nada mais passa por nenhum.

    Mede LITERAL EXECUTÁVEL, e não o texto do arquivo: a docstring cita
    `http://localhost:8080` logo acima, e um teste que lesse o arquivo cru
    reprovaria a própria explicação.
    """
    suspeitos: list[str] = []
    for no in ast.walk(_arvore()):
        if not isinstance(no, ast.Constant) or not isinstance(no.value, str):
            continue
        texto = no.value
        if texto.startswith(_FONTES_PROIBIDAS):
            suspeitos.append(f"linha {no.lineno}: {texto!r}")

    assert not suspeitos, (
        "o retratista passou a abrir caminho de fora do repositório:\n  "
        + "\n  ".join(suspeitos)
        + "\n\nA foto vai direto para docs/usage/assets/ sem revisão humana. "
        "Só a página versionada passa pelos portões de anonimato desta casa "
        "(test_docs_mac_anonimato, por OUI; check_endereco_de_radio.py, por "
        "forma) — o que vier de $HOME, da rede ou de /proc não passa por "
        "nenhum."
    )


def test_a_pagina_fotografada_tem_um_dono_so() -> None:
    """O retratista pergunta a `onde` onde a página mora — não digita o caminho.

    É a regra da casa (*"o que tem dono não se digita"*) aplicada ao ponto que
    importa para o anonimato: enquanto a origem da foto sai de `onde.pagina` /
    `onde.paginas`, ela é uma página do repositório por construção, e o teste
    acima tem o que vigiar. Um `RAIZ / "layout" / nome` montado à mão aqui seria
    um segundo dono do caminho — e o dia em que ele apontasse para fora, a régua
    de cima continuaria verde, porque o literal proibido não estaria escrito.
    """
    codigo = "\n".join(
        ast.unparse(no)
        for no in ast.walk(_arvore())
        if isinstance(no, (ast.Call, ast.Attribute))
    )

    assert "onde.pagina" in codigo or "onde.paginas" in codigo, (
        "o retratista deixou de pedir a página ao módulo `onde`, que é o dono "
        "único das duas pastas (bancada e publicado). Se ele passou a montar o "
        "caminho sozinho, este portão tem de aprender o caminho novo — e quem "
        "o escrever precisa provar que ele não sai do repositório."
    )
