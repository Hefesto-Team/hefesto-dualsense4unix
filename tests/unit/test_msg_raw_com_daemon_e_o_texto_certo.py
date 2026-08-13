"""MSG-RAW-01 — o teste que o comentário de `cmd_test.py` prometia e não existia.

A constante ``MSG_RAW_COM_DAEMON`` carrega, em cima, o comentário
*"Constante e não literal porque um teste a compara — o texto É a entrega"*
(`src/hefesto_dualsense4unix/cli/cmd_test.py`). Em 13/08/2026 esse teste **não
existia em lugar nenhum** — `grep -rn MSG_RAW_COM_DAEMON tests/` devolvia zero
linhas. Ou seja: a rede que o comentário anunciava era imaginária, e o texto
pôde envelhecer sem ninguém ver.

E envelheceu. O parágrafo do MECANISMO dizia, no presente, que *"o report_thread
do daemon sobrescreve o efeito em menos de 0,5 s (é o keepalive dele)"*. O
keepalive **perpétuo** acabou em 11/08/2026 (`RUMBLE-SEM-DONO-01`): ele passou a
valer só na janela de confirmação que segue cada mudança real
(``OUT_REPORT_KEEPALIVE_CONFIRMACAO_SEC``, em `core/backend_pydualsense.py`).

**A recusa continua certa, e é ela que estes testes protegem.** O que mudou foi
o prazo, não o veredito: o report OUT do DualSense é atômico, então o primeiro
write do daemon depois do seu leva o efeito cru junto. As três saídas
continuam as mesmas três.

O que estes testes travam:

- **o mecanismo derrubado não volta** — nem a frase, nem a afirmação no
  presente de que o daemon sobrescreve a cada 0,5 s;
- **a correção é datada e nomeia o que caducou** — regra da casa;
- **as três saídas seguem lá, e nessa ordem** — é o que a pessoa faz depois de
  ler a recusa;
- **a janela de confirmação existe no código** — se alguém devolver o
  keepalive perpétuo, este teste reprova e obriga a rever a mensagem, em vez
  de deixar produto e texto divergirem em silêncio;
- **a recusa continua ligada** — a mensagem sai e o comando sai com código 1.

Nada aqui abre controle, socket ou hidraw: só leitura da constante, do fonte do
backend, e uma chamada da função de recusa com o probe de daemon dublado.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import typer

from hefesto_dualsense4unix.cli import cmd_test

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_PATH = (
    REPO_ROOT / "src" / "hefesto_dualsense4unix" / "core" / "backend_pydualsense.py"
)

MSG = cmd_test.MSG_RAW_COM_DAEMON

#: A frase exata que estava no ar até 13/08/2026 e o núcleo dela. O keepalive
#: perpétuo saiu em 11/08; dizer isto no presente manda a pessoa depurar um
#: mecanismo que o produto não tem mais.
MECANISMO_DERRUBADO = (
    "é o keepalive dele",
    "sobrescreve o efeito em menos de 0,5",
)

#: As três saídas, na ordem em que a mensagem as oferece.
SAIDAS_EM_ORDEM = (
    "aba Gatilhos",
    "--mode com NOME de preset",
    "systemctl --user stop hefesto-dualsense4unix",
)


def test_a_mensagem_nao_afirma_o_keepalive_perpetuo_no_presente() -> None:
    for trecho in MECANISMO_DERRUBADO:
        assert trecho not in MSG, (
            f"MSG_RAW_COM_DAEMON ainda afirma o mecanismo derrubado ({trecho!r}): "
            "o keepalive perpétuo acabou em 11/08/2026 (RUMBLE-SEM-DONO-01) e "
            "hoje só vale na janela de confirmação depois de cada mudança real"
        )


def test_a_correcao_e_datada_e_diz_o_que_caducou() -> None:
    assert "11/08/2026" in MSG, (
        "a correção do mecanismo tem de trazer a data — nesta casa fato "
        "substituído ganha data, e sem ela a próxima pessoa não sabe o que caducou"
    )
    assert re.search(r"keepalive\s+PERPÉTUO", MSG), (
        "a correção precisa nomear o que caiu: o keepalive PERPÉTUO"
    )
    assert "janela de confirmação" in MSG, (
        "a correção precisa dizer o que existe HOJE no lugar: a janela de "
        "confirmação que segue cada mudança real"
    )


def test_a_recusa_continua_e_o_motivo_e_a_disputa_pelo_hidraw() -> None:
    # O veredito não mudou com o prazo: dois donos no mesmo /dev/hidraw.
    assert "SEGUNDO controlador" in MSG
    assert "/dev/hidraw" in MSG
    assert "ATÔMICO" in MSG, (
        "é a atomicidade do report OUT que sustenta a recusa depois de o "
        "keepalive perpétuo sair — sem ela a mensagem fica sem mecanismo"
    )


def test_as_tres_saidas_continuam_na_ordem() -> None:
    posicoes = []
    for saida in SAIDAS_EM_ORDEM:
        idx = MSG.find(saida)
        assert idx != -1, f"a saída {saida!r} sumiu da mensagem"
        posicoes.append(idx)
    assert posicoes == sorted(posicoes), (
        "as saídas estão em ordem de preferência — a ordem é a entrega"
    )


def test_a_janela_de_confirmacao_que_a_mensagem_cita_existe_no_codigo() -> None:
    """Âncora: a mensagem descreve o produto de hoje, não uma lembrança."""
    fonte = BACKEND_PATH.read_text(encoding="utf-8")
    assert "OUT_REPORT_KEEPALIVE_CONFIRMACAO_SEC" in fonte, (
        "a mensagem diz que o keepalive só vale na janela de confirmação; se a "
        "constante que implementa essa janela sumir, o keepalive voltou a ser "
        "perpétuo e o texto precisa ser revisto"
    )


def test_a_recusa_imprime_a_mensagem_e_sai_com_codigo_1(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Com o daemon "vivo" (dublê), o `--raw` é recusado — sem tocar em hardware."""
    import hefesto_dualsense4unix.app.ipc_bridge as ipc_bridge

    monkeypatch.setattr(ipc_bridge, "daemon_status_basic", lambda: {"status": "ok"})
    with pytest.raises(typer.Exit) as excinfo:
        cmd_test._recusar_raw_com_daemon_vivo()
    assert excinfo.value.exit_code == 1
    saida = capsys.readouterr().out
    assert "--raw recusado" in saida
    for trecho in MECANISMO_DERRUBADO:
        assert trecho not in saida, (
            f"a mensagem impressa ainda traz o mecanismo derrubado: {trecho!r}"
        )


def test_sem_daemon_o_raw_passa(monkeypatch: pytest.MonkeyPatch) -> None:
    """Contrapositivo: sem socket, o `--raw` tem o hidraw só para ele."""
    import hefesto_dualsense4unix.app.ipc_bridge as ipc_bridge

    monkeypatch.setattr(ipc_bridge, "daemon_status_basic", lambda: None)
    cmd_test._recusar_raw_com_daemon_vivo()  # não levanta
