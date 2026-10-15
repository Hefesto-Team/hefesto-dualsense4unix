"""O WirePlumber só reinicia quando algo que ele lê MUDOU (D-1410-O-APLICAR-SEGURA, parte 3).

O usuário mandou, em 14/10/2026: «Reinicia só se mudou». O `--install` do
`scripts/fix_wireplumber_default_source.sh` reiniciava o WirePlumber a CADA volta, mesmo com
os drop-ins já iguais; o `install.sh`, o `doctor --fix` e o `doctor --fix-safe` passam todos por
ele, então o dono da pergunta é um só: `restart_wireplumber_se_alterou`. O «Refazer os consertos»
da aba Sistema não chama este script (o `CONSERTOS` dela é só o `disable_steam_input.sh`): ele não
reinicia o WirePlumber em volta nenhuma.
Reiniciar o WirePlumber recria os nós de áudio da sessão (endpoints de háptica, laços), e
repetir o gesto não tem motivo para isso.

Roda o script DE VERDADE num lar de mentira, com `systemctl`, `pactl` e `wpctl` de mentira que só
anotam a chamada: nada toca o áudio, o `~/.config` nem o WirePlumber de quem roda a suíte.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
WP_FIX = RAIZ / "scripts" / "fix_wireplumber_default_source.sh"
NOME_51 = "51-hefesto-dualsense-no-default-source.conf"
NOME_54 = "54-hefesto-dualsense-alto-falante-nunca-dorme.conf"


class Lar:
    """Um HOME de mentira, com as três ferramentas de áudio trocadas por dublês que anotam."""

    def __init__(self, base: Path) -> None:
        self.casa = base / "casa"
        self.casa.mkdir()
        self.anotacao = base / "chamadas"
        #: A hora em que o WirePlumber de mentira «subiu»; o reinício a reescreve.
        self.subiu = base / "subiu"
        binario = base / "bin"
        binario.mkdir()
        for nome in ("systemctl", "pactl", "wpctl"):
            alvo = binario / nome
            vivo = (
                f'case "$*" in\n'
                f'  *"restart wireplumber"*) date +%s > "{self.subiu}" ;;\n'
                f'  *"show wireplumber"*) [[ -f "{self.subiu}" ]] && '
                f'printf "@%s\\n" "$(cat "{self.subiu}")" ;;\n'
                f'esac\n'
                if nome == "systemctl" else ""
            )
            alvo.write_text(
                f'#!/bin/bash\nprintf "{nome} %s\\n" "$*" >> "{self.anotacao}"\n{vivo}exit 0\n',
                encoding="utf-8",
            )
            alvo.chmod(0o755)
        self.ucm = base / "ucm2"
        self.env = {
            "PATH": f"{binario}:/usr/bin:/bin",
            "HOME": str(self.casa),
            "XDG_CONFIG_HOME": str(self.casa / ".config"),
            "XDG_STATE_HOME": str(self.casa / ".local" / "state"),
            "XDG_RUNTIME_DIR": str(base / "rt"),
            "HEFESTO_RAIZ_UCM": str(self.ucm),
        }
        (base / "rt").mkdir()
        self.dropins = self.casa / ".config" / "wireplumber" / "wireplumber.conf.d"

    def wireplumber_subiu_ha(self, segundos: int) -> int:
        """Faz o WirePlumber de mentira ter subido há ``segundos``; devolve a época."""
        quando = int(time.time()) - segundos
        self.subiu.write_text(f"{quando}\n", encoding="utf-8")
        return quando

    def envelhecer_os_dropins(self, segundos: int) -> None:
        agora = time.time()
        for f in self.dropins.glob("*.conf"):
            os.utime(f, (agora - segundos, agora - segundos))

    def gancho_ucm(self, idade: int) -> Path:
        """O gancho UCM do DualSense que o `install_ucm_dualsense.sh` grava, com ``idade`` s."""
        pasta = self.ucm / "conf.d" / "USB-Audio"
        pasta.mkdir(parents=True, exist_ok=True)
        gancho = pasta / (
            "Sony Interactive Entertainment DualSense Wireless Controller at usb-0000:0c:00..conf")
        gancho.write_text("# hefesto-ucm-dualsense\n", encoding="utf-8")
        agora = time.time()
        os.utime(gancho, (agora - idade, agora - idade))
        return gancho

    def rodar(self, modo: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(WP_FIX), modo],
            capture_output=True, text=True, timeout=90, check=False, env=self.env,
        )

    def reinicios(self) -> int:
        if not self.anotacao.exists():
            return 0
        texto = self.anotacao.read_text(encoding="utf-8")
        return len(re.findall(r"^systemctl --user restart wireplumber$", texto, re.M))


@pytest.fixture()
def lar(tmp_path: Path) -> Lar:
    return Lar(tmp_path)


@pytest.mark.parametrize("vivo", [False, True], ids=["sem-hora", "com-a-hora-da-subida"])
@pytest.mark.parametrize("modo", ["--install", "--disable-source"])
def test_a_segunda_volta_nao_reinicia(lar: Lar, modo: str, vivo: bool) -> None:
    """Duas voltas: a primeira escreve e reinicia; a segunda, igual, deixa o áudio quieto.

    ``com-a-hora-da-subida``: o `systemctl` de mentira sabe quando o WirePlumber subiu (o
    reinício da primeira volta a reescreve), e o drop-in recém-gravado não é mais novo que ele.
    """
    # Prova da D-1410-O-APLICAR-SEGURA.
    if vivo:
        lar.wireplumber_subiu_ha(3600)
    primeira = lar.rodar(modo)
    assert primeira.returncode in (0, 2), primeira.stdout + primeira.stderr
    assert lar.reinicios() == 1, (
        "a primeira volta escreveu os drop-ins e tinha de reiniciar o WirePlumber uma vez"
    )

    segunda = lar.rodar(modo)
    assert segunda.returncode in (0, 2), segunda.stdout + segunda.stderr
    assert lar.reinicios() == 1, (
        "a segunda volta reiniciou o WirePlumber com os drop-ins iguais: o áudio da sessão "
        "foi recriado à toa"
    )
    assert "nada a reiniciar" in segunda.stderr + segunda.stdout


def test_o_dropin_mexido_a_mao_faz_reiniciar_de_novo(lar: Lar) -> None:
    """O outro lado: se o 51 instalado diverge do asset, a volta o repõe E reinicia."""
    # Prova da D-1410-O-APLICAR-SEGURA.
    lar.rodar("--install")
    antes = lar.reinicios()
    (lar.dropins / NOME_51).write_text("# mexido a mão\n", encoding="utf-8")

    lar.rodar("--install")

    assert lar.reinicios() == antes + 1, (
        "o drop-in foi reposto e o WirePlumber continuou rodando com a regra velha"
    )
    assert (lar.dropins / NOME_51).read_text(encoding="utf-8") != "# mexido a mão\n"


def test_o_nunca_dorme_mudou_reinicia_no_install(lar: Lar) -> None:
    """O 54 também conta: quem o instala de novo no meio do `--install` pede o reinício."""
    # Prova da D-1410-O-APLICAR-SEGURA.
    lar.rodar("--install")
    antes = lar.reinicios()
    (lar.dropins / NOME_54).unlink()

    lar.rodar("--install")

    assert lar.reinicios() == antes + 1


def test_a_forma_velha_do_dropin_tirada_faz_reiniciar(lar: Lar) -> None:
    """Uma troca de WirePlumber deixa a outra forma no disco; tirá-la muda o que ele lê."""
    # Prova da D-1410-O-APLICAR-SEGURA.
    lar.rodar("--install")
    antes = lar.reinicios()
    velha = lar.casa / ".config" / "wireplumber" / "main.lua.d"
    velha.mkdir(parents=True)
    (velha / NOME_51.replace(".conf", ".lua")).write_text("-- forma velha\n", encoding="utf-8")

    lar.rodar("--install")

    assert not (velha / NOME_51.replace(".conf", ".lua")).exists()
    assert lar.reinicios() == antes + 1


@pytest.mark.parametrize("modo", ["--install", "--disable-source"])
def test_o_ucm_gravado_depois_da_subida_faz_reiniciar(lar: Lar, modo: str) -> None:
    """O install e o `doctor --fix` gravam o gancho UCM ANTES deste script, e contam com o reinício
    dele para a placa do controle reabrir pelo perfil (a háptica pelo cabo). Os drop-ins iguais não
    podem calar isso: o gancho mais novo que o WirePlumber vivo reinicia; o mais velho, não.

    MORDIDA: tire o ``|| _wp_nao_leu_o_disco`` do ``restart_wireplumber_se_alterou``.
    """
    # Prova da D-1410-O-APLICAR-SEGURA.
    lar.rodar(modo)
    lar.envelhecer_os_dropins(7200)
    lar.wireplumber_subiu_ha(3600)
    antes = lar.reinicios()

    lar.gancho_ucm(idade=5400)
    lar.rodar(modo)
    assert lar.reinicios() == antes, "o gancho que o WirePlumber já leu fez reiniciar"

    lar.gancho_ucm(idade=60)
    lar.rodar(modo)
    assert lar.reinicios() == antes + 1, (
        "o gancho UCM gravado depois da subida não reiniciou o WirePlumber: a placa do controle "
        "fica sem o perfil até um replug"
    )

    lar.rodar(modo)
    assert lar.reinicios() == antes + 1, "depois do reinício, o mesmo gancho reiniciou de novo"


def test_o_install_e_o_disable_nao_reiniciam_por_conta_propria() -> None:
    """Estrutura: os ramos `install)` e `disable)` perguntam ao dono, não chamam o reinício nu."""
    # Prova da D-1410-O-APLICAR-SEGURA.
    texto = WP_FIX.read_text(encoding="utf-8")
    for ramo in ("install", "disable"):
        achado = re.search(rf"^    {ramo}\)\n(.*?)^        exit \"\$\{{rc\}}\"", texto, re.M | re.S)
        assert achado, f"não achei o ramo {ramo}) do script"
        corpo = achado.group(1)
        assert "restart_wireplumber_se_alterou" in corpo, ramo
        assert not re.search(r"^\s*restart_wireplumber\s*$", corpo, re.M), (
            f"o ramo {ramo}) reinicia sem perguntar se algo mudou"
        )


def test_o_ambiente_do_teste_nao_tem_o_systemctl_real(lar: Lar) -> None:
    """Trava do próprio teste: o `systemctl` que o script acha primeiro é o dublê."""
    achado = subprocess.run(
        ["bash", "-c", "command -v systemctl"],
        capture_output=True, text=True, env=lar.env, check=False,
    ).stdout.strip()
    assert achado.startswith(str(lar.casa.parent)), achado
    assert os.path.exists(achado)
