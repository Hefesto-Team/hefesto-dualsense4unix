"""PARIDADE-QUENTE-01 — todo parâmetro que o uninstall DESARMA tem de ser
rearmado pelos DOIS instaladores.

A regra é da casa e já foi paga uma vez, em `9c944a8` (*"o ciclo uninstall+install
desligava SEIS curas de módulo em silêncio"*). A
[ARVORE-DIVERGENTE-01](../../docs/process/sprints/2026-07-30-ARVORE-DIVERGENTE-01-o-que-esta-na-main-e-nao-roda.md)
recontou a lista em 30/07 e achou **quatro órfãos** — params que o
`uninstall.sh` zerava e o `install.sh` nunca rearmava. Aqueles quatro foram
curados.

**O que ninguém tinha olhado é o SEGUNDO instalador.** A casa tem dois caminhos
que põem as curas de módulo numa máquina:

- `install.sh` — o checkout git;
- `scripts/install-host-udev.sh` — quem instalou por `.deb`, `.rpm`, Arch ou
  Flatpak (é o caminho que o próprio `scripts/doctor.sh` manda rodar, em
  `:3211` e `:3271`).

Em 07/08/2026 os dois conjuntos foram comparados e **divergiam em quatro
parâmetros**: os três do patch 0003 do `hid-nintendo` (o handshake USB do clone
057E:2009) e o `hang_reset` do `rtw88_usb`. Todos nasceram depois da paridade da
AUTO-01.7 e entraram só no `install.sh`.

Por que isso morde de verdade, e não é higiene: os params são lidos NA PROBE do
módulo, e recarregar módulo é **proibido** nos dois instaladores (derrubaria os
controles em uso). Então a conf do `modprobe.d` — que traz os três do 0003 — só
vale no próximo BOOT. Entre o `uninstall.sh`, que os zera de propósito
(`:874-876` e `:913`), e o boot seguinte, quem instalou por pacote ficava com o
8BitDo Pro clone morrendo na probe no cabo e com o reset de porta do fantasma do
dongle desligado — com o módulo patchado instalado e a cura dentro dele.

## A mordida, medida

Arrancando as três linhas novas de `install-host-udev.sh` (bloco
`HIDNINTENDO_SRC`), `test_todo_param_desarmado_e_rearmado_pelos_dois` reprova
nomeando `usb_cmd_pad_to_report`, `usb_send_conn_status` e `usb_probe_degrade`.
Arrancando o bloco do `hang_reset`, reprova nomeando `hang_reset`. Devolvidas,
verde. O teste não lê comentário: ele exige uma linha que **escreve** no
caminho do sysfs.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
UNINSTALL = (REPO_ROOT / "uninstall.sh").read_text(encoding="utf-8")
HOST_UDEV = (REPO_ROOT / "scripts" / "install-host-udev.sh").read_text(encoding="utf-8")

#: Caminho de parâmetro de módulo em `/sys`, ex.: hid_nintendo/bt_probe_retries.
_PARAM = re.compile(r"/sys/module/([a-z0-9_]+)/parameters/([a-z0-9_]+)")


def _sem_comentarios(texto: str) -> list[str]:
    """Linhas de código, sem as que são só comentário.

    Existe porque a armadilha desta família de teste é **medir ortografia**: um
    parâmetro citado num comentário passaria por rearme sem nenhuma escrita
    acontecer. Só sobram linhas que podem executar.
    """
    return [
        linha
        for linha in texto.splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]


def _params_escritos(texto: str) -> set[tuple[str, str]]:
    """Pares (módulo, parâmetro) que alguma linha EXECUTÁVEL do script escreve.

    O critério é a presença do caminho numa linha de código — os dois scripts
    escrevem por `sudo tee <caminho>` (install.sh) ou por `> <caminho>`
    (install-host-udev.sh, que monta um comando elevado como string).
    """
    achados: set[tuple[str, str]] = set()
    for linha in _sem_comentarios(texto):
        for modulo, param in _PARAM.findall(linha):
            achados.add((modulo, param))
    return achados


#: O `snd_usb_audio/quirk_flags` é a ÚNICA exceção do `install.sh`, e ela é
#: declarada aqui em vez de escondida numa lista de ignorados: o `install.sh`
#: rearma o quirk pelo `scripts/install_snd_quirk.sh --runtime` (`:903` e
#: `:1206`), que é o dono desse valor e o calcula a partir da própria conf —
#: duplicar o literal aqui criaria o segundo dono que a casa já pagou para
#: eliminar. O `install-host-udev.sh` escreve o literal porque monta UM comando
#: elevado só e não pode chamar outro script no meio.
EXCECAO_INSTALL_SH = {("snd_usb_audio", "quirk_flags")}

#: Como o `install.sh` cumpre a exceção acima. Se esta chamada sumir, o
#: parâmetro deixa de ser rearmado e a exceção vira buraco — por isso ela tem
#: teste próprio, e não um `# noqa`.
CHAMADA_QUE_CUMPRE_A_EXCECAO = "install_snd_quirk.sh"


def _params_desarmados_pelo_uninstall() -> set[tuple[str, str]]:
    """O que o `uninstall.sh` devolve ao valor de fábrica.

    É a lista que manda: quem desarma define quem tem de rearmar. Derivada do
    arquivo, nunca digitada — foi digitá-la à mão que deixou os quatro órfãos
    da ARVORE-DIVERGENTE-01 passarem despercebidos por semanas.
    """
    return _params_escritos(UNINSTALL)


def test_o_uninstall_desarma_algo_senao_o_teste_e_um_carimbo() -> None:
    """Controle do próprio teste.

    Se o `uninstall.sh` deixar de desarmar qualquer parâmetro, todos os testes
    abaixo passariam por vacuidade — verdes sem medir nada. Este aqui reprova
    antes disso acontecer.
    """
    desarmados = _params_desarmados_pelo_uninstall()
    assert len(desarmados) >= 9, (
        "o uninstall.sh desarma menos parâmetros de módulo do que a casa "
        f"registrou ({len(desarmados)}) — os testes de paridade abaixo viraram "
        "carimbo. Confira se um bloco de desarme foi removido."
    )


def test_todo_param_desarmado_e_rearmado_pelos_dois() -> None:
    """A regra do `9c944a8`, estendida ao segundo instalador.

    Cura arrancada (medida em 07/08/2026): tirar as três linhas do patch 0003
    do bloco `HIDNINTENDO_SRC` de `install-host-udev.sh` deixa este teste
    vermelho nomeando os três; tirar o bloco do `hang_reset`, idem.
    """
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
        "rodar ESTE script (doctor.sh:3211 e :3271), e ele tem de curar tanto "
        "quanto o install.sh."
    )


def test_a_excecao_do_quirk_de_audio_e_cumprida_por_chamada_real() -> None:
    """A exceção declarada não pode virar buraco por omissão.

    O `install.sh` não escreve `snd_usb_audio/quirk_flags` no literal porque
    delega ao dono do valor. Se a delegação sumir, o parâmetro fica órfão e
    nada acusaria — o teste acima o daria por rearmado pela exceção.
    """
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
    """Os três do patch 0003 são uma cura só e não podem ser rearmados pela
    metade: `usb_probe_degrade` DEPENDE do handshake que os outros dois mandam
    (o racional está em `assets/modprobe.d/hefesto-hid-nintendo.conf`)."""
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
