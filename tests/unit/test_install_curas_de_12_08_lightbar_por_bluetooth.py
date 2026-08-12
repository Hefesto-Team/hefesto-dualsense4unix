"""GATILHO-DA-COR-INSTALA-01: o install tem de entregar hidraw GRAVÁVEL no rádio.

- **Escrito em:** 12/08/2026, junto das três curas da bancada de 11-12/08.
- **A regra da casa que este arquivo defende** (decisão dela, 08/08/2026): toda
  cura entra no `install.sh`, sem flag e sem opt-in — e a prova é por ciclo
  `uninstall` -> `install`.

O QUE ESTAVA FURADO
===================
O gatilho da cor (`core/lightbar_gatilho.py`) repinta a lightbar **por hidraw**
depois que a rajada da Steam passa. Para isso o daemon precisa ESCREVER no
`/dev/hidrawN` do DualSense que está no rádio, e quem entrega essa permissão é
a `assets/70-ps5-controller.rules` (`MODE="0660"` + `TAG+="uaccess"`).

Os dois instaladores de udev traziam esta linha:

    udevadm trigger --subsystem-match=hidraw --attr-match=idVendor=054c

que casa **ZERO dispositivos, em toda máquina**. O `--attr-match` só olha os
sysattrs do PRÓPRIO nó, e um `hidraw` não tem `idVendor`: esse atributo mora no
pai USB — e no Bluetooth não existe pai USB nenhum, porque o BlueZ cria o HID
por `uhid` (`/sys/devices/virtual/misc/uhid/0005:054C:0CE6.*`).

Medido na máquina dela em 12/08/2026, três DualSense no rádio e um no cabo:

    udevadm trigger --dry-run --verbose --subsystem-match=hidraw       -> 8
    ... o mesmo + --attr-match=idVendor=054c                           -> 0

Consequência numa instalação limpa com o controle já conectado no rádio: a
regra 70 não era reaplicada ao nó que já existia, o daemon subia (passo 7a do
`install.sh`) sem poder escrever naquele hidraw, e a lightbar por Bluetooth
nascia morta **até alguém desconectar e reconectar o controle à mão**. O
`install-host-udev.sh` (.deb/flatpak) escapava por acidente, porque termina com
um `udevadm trigger` global; o `scripts/install_udev.sh`, que é o caminho do
`install.sh`, não tinha esse global.

COMO ESTES TESTES MORDEM
========================
- Os dois primeiros leem os arquivos REAIS e sempre rodam: devolver a linha
  antiga, ou apagar o trigger de hidraw, reprova.
- Os dois últimos passam o seletor pelo `udevadm` DE VERDADE, em `--dry-run`
  (não precisa de root, não muda nada): o do produto tem de selecionar pelo
  menos um `hidraw`, e o antigo tem de selecionar zero. O segundo é o controle
  negativo — sem ele, um seletor que casasse tudo passaria pelo primeiro sem
  provar nada sobre o defeito que existiu.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

#: Os dois caminhos de instalação de udev do produto. O primeiro é o que o
#: `install.sh` chama (source/native); o segundo é o do .deb, do flatpak e do
#: AppImage. A cura tem de estar nos DOIS — foi o furo de paridade que deixou o
#: nativo sem trigger de hidraw nenhum.
INSTALADORES = (
    REPO / "scripts" / "install_udev.sh",
    REPO / "scripts" / "install-host-udev.sh",
)

#: O filtro impossível. `hidraw` não tem sysattr `idVendor`.
FILTRO_IMPOSSIVEL = "attr-match"


def _linhas_de_trigger_hidraw(script: Path) -> list[str]:
    """As linhas de `udevadm trigger` que mencionam `subsystem-match=hidraw`.

    Comentários ficam de fora de propósito: a explicação do defeito CITA a
    linha antiga (é o registro da medição), e um teste que lesse comentário
    reprovaria a própria documentação da cura.
    """
    linhas: list[str] = []
    for bruta in script.read_text(encoding="utf-8").splitlines():
        linha = bruta.strip()
        if linha.startswith("#"):
            continue
        # No install-host-udev.sh o comando é montado como string (`cmd+="..."`),
        # então basta a linha conter as duas marcas.
        if "udevadm trigger" in linha and "subsystem-match=hidraw" in linha:
            linhas.append(linha)
    return linhas


@pytest.mark.parametrize("script", INSTALADORES, ids=lambda p: p.name)
def test_o_instalador_redispara_hidraw(script: Path) -> None:
    """Sem trigger de hidraw, a regra 70 só valeria no próximo replug.

    É a cura de 08/08 furada: "nada à mão, nada opt-in". Um controle já
    conectado no rádio no instante do install ficaria sem escrita até a usuária
    descobrir sozinha que precisa reconectar.
    """
    assert script.exists(), f"instalador ausente: {script}"
    linhas = _linhas_de_trigger_hidraw(script)
    assert linhas, (
        f"{script.relative_to(REPO)} não dispara "
        "'udevadm trigger --subsystem-match=hidraw': a regra 70 "
        "(MODE 0660 + uaccess) não chega ao hidraw que JÁ existe, e o gatilho "
        "da cor não tem onde escrever no Bluetooth."
    )


@pytest.mark.parametrize("script", INSTALADORES, ids=lambda p: p.name)
def test_o_trigger_de_hidraw_nao_usa_o_filtro_impossivel(script: Path) -> None:
    """`--attr-match` num trigger de hidraw casa zero dispositivos, sempre."""
    assert script.exists(), f"instalador ausente: {script}"
    culpadas = [
        linha
        for linha in _linhas_de_trigger_hidraw(script)
        if FILTRO_IMPOSSIVEL in linha
    ]
    assert not culpadas, (
        f"{script.relative_to(REPO)} filtra o trigger de hidraw por "
        f"--attr-match: {culpadas}\n"
        "Um nó hidraw não tem sysattr próprio — idVendor mora no pai USB, e no "
        "Bluetooth não há pai USB (o BlueZ cria o HID por uhid). O filtro casa "
        "ZERO dispositivos: medido 0 de 8 na máquina dela em 12/08/2026."
    )


def _argumentos_do_trigger_de_hidraw() -> list[str]:
    """Extrai do `install_udev.sh` REAL os argumentos do trigger de hidraw.

    O teste empírico abaixo roda o que o produto roda — não uma cópia escrita à
    mão que poderia divergir do arquivo e mentir verde.
    """
    linhas = _linhas_de_trigger_hidraw(INSTALADORES[0])
    assert linhas, "install_udev.sh sem trigger de hidraw (ver teste acima)"
    linha = linhas[0]
    # Tira o `sudo `, o redirecionamento e o `|| true` do fim.
    corpo = re.sub(r"\s*2>/dev/null.*$", "", linha)
    corpo = corpo.replace("sudo ", "", 1).strip()
    partes = corpo.split()
    assert partes[:2] == ["udevadm", "trigger"], corpo
    return partes[2:]


def _selecionados(argumentos: list[str]) -> list[str]:
    """Quantos dispositivos o seletor casa NESTA máquina, sem mudar nada.

    `--dry-run` não dispara evento nenhum e não pede root — é leitura pura do
    banco do udev.
    """
    saida = subprocess.run(
        ["udevadm", "trigger", "--dry-run", "--verbose", *argumentos],
        capture_output=True,
        text=True,
        check=False,
    )
    return [linha for linha in saida.stdout.splitlines() if linha.strip()]


requer_udev = pytest.mark.skipif(
    shutil.which("udevadm") is None or not Path("/sys/class/hidraw").is_dir(),
    reason="sem udevadm ou sem /sys/class/hidraw (CI em contêiner)",
)


@requer_udev
def test_o_seletor_do_produto_casa_hidraw_de_verdade() -> None:
    """O seletor que o install usa tem de alcançar os nós que existem agora."""
    todos = _selecionados(["--subsystem-match=hidraw"])
    if not todos:
        pytest.skip("esta máquina não tem nenhum nó hidraw para redisparar")
    do_produto = _selecionados(_argumentos_do_trigger_de_hidraw())
    assert do_produto, (
        "o trigger de hidraw do scripts/install_udev.sh não selecionou "
        f"NENHUM dos {len(todos)} nós hidraw desta máquina — é o defeito de "
        "12/08/2026 de volta: o install anuncia sucesso e o controle já "
        "conectado fica sem permissão de escrita."
    )


@requer_udev
def test_controle_negativo_o_filtro_antigo_nao_casa_nada() -> None:
    """A mordida não é vazia: o seletor antigo seleciona zero, aqui e agora.

    Item C3/E do METODO-DE-ISOLAMENTO — o controle negativo é o que separa "o
    teste passou" de "o teste discrimina". Se um dia o kernel passar a expor
    `idVendor` no próprio nó hidraw, este teste cai e avisa que o teste de cima
    deixou de provar o que se pensa que ele prova.
    """
    todos = _selecionados(["--subsystem-match=hidraw"])
    if not todos:
        pytest.skip("esta máquina não tem nenhum nó hidraw para redisparar")
    antigo = _selecionados(
        ["--subsystem-match=hidraw", "--attr-match=idVendor=054c"]
    )
    assert not antigo, (
        f"o filtro antigo selecionou {len(antigo)} nós — a premissa desta cura "
        "mudou nesta máquina, e a explicação escrita no install_udev.sh "
        "precisa ser remedida antes de qualquer conclusão."
    )
