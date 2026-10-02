"""PARIDADE-QUENTE-01 — todo parâmetro que o uninstall DESARMA tem de ser"""

from __future__ import annotations

import re
from pathlib import Path

from tests.unit.fonte_do_instalador import texto_do_instalador

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL = texto_do_instalador()
UNINSTALL = (REPO_ROOT / "uninstall.sh").read_text(encoding="utf-8")
HOST_UDEV = (REPO_ROOT / "scripts" / "install-host-udev.sh").read_text(encoding="utf-8")

_PARAM = re.compile(
    r"(?:\btee\s+(?:-a\s+)?|>\s*)/sys/module/([a-z0-9_]+)/parameters/([a-z0-9_]+)"
)


def _sem_comentarios(texto: str) -> list[str]:
    """Linhas de código, sem as que são só comentário."""
    return [
        linha
        for linha in texto.splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]


def _params_escritos(texto: str) -> set[tuple[str, str]]:
    """Pares (módulo, parâmetro) que alguma linha EXECUTÁVEL do script escreve."""
    achados: set[tuple[str, str]] = set()
    for linha in _sem_comentarios(texto):
        for modulo, param in _PARAM.findall(linha):
            achados.add((modulo, param))
    return achados


EXCECAO_INSTALL_SH = {("snd_usb_audio", "quirk_flags")}

#: teste próprio, e não um `# noqa`.
CHAMADA_QUE_CUMPRE_A_EXCECAO = "install_snd_quirk.sh"


def _params_desarmados_pelo_uninstall() -> set[tuple[str, str]]:
    """O que o `uninstall.sh` devolve ao valor de fábrica."""
    return _params_escritos(UNINSTALL)


def test_o_uninstall_desarma_algo_senao_o_teste_e_um_carimbo() -> None:
    """Controle do próprio teste."""
    desarmados = _params_desarmados_pelo_uninstall()
    assert len(desarmados) >= 9, (
        "o uninstall.sh desarma menos parâmetros de módulo do que a casa "
        f"registrou ({len(desarmados)}) — os testes de paridade abaixo viraram "
        "carimbo. Confira se um bloco de desarme foi removido."
    )


def test_todo_param_desarmado_e_rearmado_pelos_dois() -> None:
    """A regra do `9c944a8`, estendida ao segundo instalador."""
    desarmados = _params_desarmados_pelo_uninstall()
    rearmados_install = _params_escritos(INSTALL) | EXCECAO_INSTALL_SH
    rearmados_host = _params_escritos(HOST_UDEV)

    orfaos_install = sorted(desarmados - rearmados_install)
    assert not orfaos_install, (
        "params que o uninstall.sh DESARMA e o install.sh NUNCA rearma: "
        f"{orfaos_install}. O ciclo uninstall+install deixa a cura desligada "
        "até o próximo boot, em silêncio — é o defeito do commit 9c944a8."
    )

    orfaos_host = sorted(desarmados - rearmados_host)
    assert not orfaos_host, (
        "params que o uninstall.sh DESARMA e o scripts/install-host-udev.sh "
        f"NUNCA rearma: {orfaos_host}. Quem instalou por pacote (.deb/.rpm/"
        "Arch/Flatpak) fica sem a cura até o próximo boot — o doctor manda "
        "rodar ESTE script (doctor.sh:3272 e :3271), e ele tem de curar tanto "
        "quanto o install.sh."
    )


def test_a_excecao_do_quirk_de_audio_e_cumprida_por_chamada_real() -> None:
    """A exceção declarada não pode virar buraco por omissão."""
    executaveis = "\n".join(_sem_comentarios(INSTALL))
    assert f"{CHAMADA_QUE_CUMPRE_A_EXCECAO}" in executaveis, (
        "install.sh não chama mais o scripts/install_snd_quirk.sh — a exceção "
        "de snd_usb_audio/quirk_flags deixou de ser cumprida"
    )
    assert "--runtime" in executaveis, (
        "install.sh chama o install_snd_quirk.sh mas não no modo --runtime — "
        "sem ele só a conf persistente é gravada, e o quirk zerado pelo "
        "uninstall só volta no próximo boot"
    )


def test_os_tres_params_do_clone_usb_andam_juntos_nos_dois() -> None:
    """Os três do patch 0003 são uma cura só e não podem ser rearmados pela"""
    trio = {
        ("hid_nintendo", "usb_cmd_pad_to_report"),
        ("hid_nintendo", "usb_send_conn_status"),
        ("hid_nintendo", "usb_probe_degrade"),
    }
    for nome, fonte in (("install.sh", INSTALL), ("install-host-udev.sh", HOST_UDEV)):
        escritos = _params_escritos(fonte)
        faltando = sorted(trio - escritos)
        assert not faltando, (
            f"{nome} rearma o handshake USB do clone 057E:2009 pela metade — "
            f"faltam {faltando}. Sem os três, o 8BitDo Pro clone no cabo morre "
            "na probe ('Failed to get joycon info; ret=-110')."
        )
