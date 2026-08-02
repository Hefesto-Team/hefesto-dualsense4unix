"""BLUEZ-PADRAO-INVERTIDO-01 — desinstalar o Hefesto não pode piorar o Bluetooth.

Decisão dela, em 02/08/2026, ao ver que eu ia usar `--keep-bluez` para me
proteger de um padrão perigoso:

    "o uninstall deveria desfazer o negócio e deixar o bluez certo, não? e caso
     usássemos flag é que deveria voltar o bluez pro original do pop os"

**Ela tem razão, e o padrão estava invertido.** O `uninstall.sh` restaurava o
BlueZ do noble por OMISSÃO — um gesto que o próprio código chama de "REMOÇÃO
BRUTAL de propósito, pois reinicia o bluetoothd (...) e descarta os bonds
pareados outra vez".

Três coisas derrubaram a justificativa antiga (que era defensável, e por isso
fica registrada no arquivo):

1. **o gesto é destrutivo**, e a regra desta casa é que o PADRÃO seja o menos
   destrutivo — o explícito é que carrega o risco;
2. **a versão para a qual se voltava tem defeito MEDIDO nesta máquina**:
   `bluetoothd` crashando cronicamente e comendo bonds (estudo de 19/07);
3. **precedente no mesmo arquivo**: o `--remove-usb-quirk` já não removia por
   padrão, porque *"cmdline é sensível"*. O BlueZ é mais sensível que o
   cmdline.

Estes testes leem o `uninstall.sh` como TEXTO porque é um shell script: não há
como importá-lo, e rodá-lo de verdade num teste desinstalaria o Hefesto da
máquina de quem roda a suíte.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
UNINSTALL = RAIZ / "uninstall.sh"


@pytest.fixture(scope="module")
def fonte() -> str:
    return UNINSTALL.read_text(encoding="utf-8")


def test_o_backport_do_bluez_e_preservado_por_padrao(fonte: str) -> None:
    """O default é PRESERVAR — e o teste lê o valor inicial da variável.

    `KEEP_BLUEZ=1` é o que separa "o Bluetooth dela continua funcionando
    depois de desinstalar" de "o bluetoothd volta a crashar e a comer os
    bonds".

    Mordida: voltar para `KEEP_BLUEZ=0`.
    """
    achado = re.search(r"^KEEP_BLUEZ=(\d)", fonte, re.MULTILINE)

    assert achado is not None, "a variável KEEP_BLUEZ sumiu do uninstall.sh"
    assert achado.group(1) == "1", (
        "o padrão tem de PRESERVAR o backport do BlueZ: restaurar reinicia o "
        "bluetoothd, descarta os bonds e devolve uma versão com defeito "
        "medido nesta máquina"
    )


def test_existe_uma_flag_explicita_para_devolver_o_bluez_da_distro(
    fonte: str,
) -> None:
    """O gesto destrutivo continua possível — mas ele tem de ser pedido.

    Inverter o padrão sem oferecer o caminho de volta seria trocar um problema
    por outro: quem quiser o BlueZ original da distro (para desinstalar o
    Hefesto de vez, ou porque a distro alcançou a versão) tem de conseguir.

    Mordida: apagar o ramo `--restore-bluez` do parser de argumentos.
    """
    assert "--restore-bluez)" in fonte
    assert re.search(r"--restore-bluez\)\s*KEEP_BLUEZ=0", fonte), (
        "`--restore-bluez` tem de zerar o KEEP_BLUEZ — é ela que devolve o "
        "pacote da distro"
    )


def test_a_flag_antiga_continua_aceita_e_virou_no_op(fonte: str) -> None:
    """`--keep-bluez` não pode passar a dar erro.

    Ela está em roteiros, em documentação de processo e possivelmente na
    memória de quem já desinstalou uma vez. Quebrar um comando que alguém
    aprendeu para pedir a coisa CERTA seria punir quem acertou.

    Mordida: remover o ramo `--keep-bluez` do parser.
    """
    assert re.search(r"--keep-bluez\)\s*KEEP_BLUEZ=1", fonte)


def test_o_uninstall_aceita_as_duas_flags_sem_reclamar() -> None:
    """E o parser de verdade engole as duas — não é só o texto.

    O `--help` sai antes de qualquer ação destrutiva, então dá para exercitar
    o parser de verdade sem desinstalar nada. Um argumento desconhecido faria
    o script sair com erro, e é isso que se afere.

    Mordida: escrever `--restore-bluez` no `--help` sem pôr no `case`.
    """
    for flag in ("--restore-bluez", "--keep-bluez"):
        r = subprocess.run(
            ["bash", str(UNINSTALL), flag, "--help"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode == 0, f"{flag} não foi aceita: {r.stderr[:200]}"


def test_o_help_diz_qual_dos_dois_e_o_padrao(fonte: str) -> None:
    """Quem lê o `--help` tem de saber o que acontece se não passar nada.

    Esta casa tem defeito registrado de `--help` que calava flags reais
    (o comentário passou de 128 linhas e o `--help` truncou). Aqui o risco é
    outro e pior: um `--help` que descreva o padrão ERRADO faz alguém
    desinstalar achando que preserva.

    Mordida: trocar a frase do `--restore-bluez` por uma que não diga qual é o
    padrão.
    """
    ajuda = subprocess.run(
        ["bash", str(UNINSTALL), "--help"],
        capture_output=True,
        text=True,
        timeout=60,
    ).stdout

    linha = next(
        (ln for ln in ajuda.splitlines() if "--restore-bluez" in ln), ""
    )
    assert linha, "o --help não cita a flag que devolve o BlueZ da distro"

    bloco = ajuda[ajuda.index("--restore-bluez") :][:400]
    assert "padrão PRESERVA" in bloco, (
        "o --help tem de dizer que o PADRÃO preserva o backport — senão "
        "alguém desinstala achando que está preservando"
    )


def test_a_decisao_anterior_nao_foi_apagada(fonte: str) -> None:
    """A regra da casa: decisão medida não se reescreve, ganha nota datada.

    A justificativa antiga (*"ficar com um bluez de terceiro órfão (...) é pior
    do que voltar ao 5.72"*) era defensável, e é ela que explica por que o
    código tem toda a maquinaria de restauração. Apagá-la faria a próxima
    pessoa reabrir a discussão do zero.

    Mordida: apagar o parágrafo que cita a justificativa anterior.
    """
    assert "BLUEZ-PADRAO-INVERTIDO-01" in fonte
    assert "órfão" in fonte, (
        "a justificativa ANTIGA tem de continuar escrita — ela é o que explica "
        "a maquinaria de restauração que continua no arquivo"
    )
