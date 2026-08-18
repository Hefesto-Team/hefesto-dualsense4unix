"""CARONA-NO-GUARD-01 (16/08/2026) — o vigia já acordava na hora certa.

**O pedido dela**, ao sair para dormir em 15/08: *"pensa no qol do user,
automação de interface e pensa em aplicar cada uma das descobertas de forma
universal"*. E antes, sobre a cura do wrapper: *"nem precisa ter um botão na
gui, mas ele se auto corrigir"*.

**O problema que sobrava.** A Steam guarda UMA linha de `LaunchOptions` por
jogo, e qualquer coisa escrita nela substitui o wrapper em silêncio. Medido duas
vezes no PRAGMATA — a segunda às 05h de 16/08/2026, com a cura já escrita e o
jogo dela quebrado assim mesmo. Repor não resolve sozinho: **a Steam regrava o
`localconfig.vdf` ao SAIR e engole qualquer edição feita com ela viva.** Havia
cura e havia gatilho na GUI, e mesmo assim existia uma janela em que ninguém
repunha nada — a janela em que ela está jogando, que é o tempo todo.

**A descoberta.** O gatilho perfeito já existia e estava LIGADO nesta máquina:
`hefesto-steam-input-guard.path` vigia `~/.steam/steam/userdata` desde o
FEAT-STEAM-INPUT-SELF-HEAL-01, e acorda exatamente quando a Steam grava o vdf —
isto é, no instante em que ela ACABOU DE SAIR. Era só a sentinela do wrapper
pegar carona no mesmo `.service`. Nada de unit novo, nada de timer novo, nada
de botão: a casa já sabia acordar na hora certa e não estava usando isso.

É a contraparte feliz do defeito mais caro daqui ("a casa sabe e o produto não
faz"): dessa vez a casa sabia, e passou a fazer.

**O que este arquivo trava.** Que o segundo `ExecStart` não suma; que ele seja
tolerante a falha (`-`), porque ADIAR é o caso comum e não é erro; que o
`install.sh` renderize o placeholder novo; e que o passo do Steam Input continue
sendo o primeiro.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE = REPO_ROOT / "assets" / "hefesto-steam-input-guard.service"
PATH_UNIT = REPO_ROOT / "assets" / "hefesto-steam-input-guard.path"
INSTALL = REPO_ROOT / "install.sh"
SENTINELA = (
    REPO_ROOT / "src" / "hefesto_dualsense4unix" / "integrations" / "sentinela_do_wrapper.py"
)


@pytest.fixture(scope="module")
def service() -> str:
    return SERVICE.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def execstarts(service: str) -> list[str]:
    return [
        linha.split("=", 1)[1].strip()
        for linha in service.splitlines()
        if linha.startswith("ExecStart=")
    ]


class TestOSegundoPasso:
    def test_o_guard_repoe_o_wrapper(self, execstarts: list[str]) -> None:
        """A MORDIDA. Sem este passo, o Pragmata volta a ficar quebrado calado."""
        assert len(execstarts) == 2, execstarts
        assert "__SENTINELA__" in execstarts[1]
        assert "--reparar" in execstarts[1]

    def test_o_steam_input_continua_sendo_o_primeiro(self, execstarts: list[str]) -> None:
        """A ordem é a de sempre: o passo que já existia não foi deslocado."""
        assert "__SCRIPT__" in execstarts[0]
        assert "--apply-quiet" in execstarts[0]

    def test_adiar_nao_pode_derrubar_o_guard(self, service: str) -> None:
        """O `-` é o que separa "adiei" de "quebrei".

        `--reparar` sai com 3 quando a Steam ou um jogo estão abertos — o caso
        COMUM. Sem o `-`, o guard entraria em `failed` toda vez que ela
        estivesse jogando, e um serviço cronicamente vermelho é um serviço que
        ninguém mais lê.
        """
        assert re.search(r"^ExecStart=-/usr/bin/env python3 __SENTINELA__", service, re.M)

    def test_roda_no_python3_do_sistema(self, execstarts: list[str]) -> None:
        """O guard não tem venv. A sentinela é stdlib pura justamente por isto."""
        assert "python3" in execstarts[1]
        texto = SENTINELA.read_text(encoding="utf-8")
        assert "100% stdlib" in texto


class TestOGatilhoQueJaExistia:
    def test_o_path_unit_vigia_o_userdata(self) -> None:
        """É o `userdata` que a Steam reescreve ao sair — a hora certa de repor."""
        texto = PATH_UNIT.read_text(encoding="utf-8")
        assert texto.count("PathChanged=") >= 3
        assert "userdata" in texto

    def test_nenhum_unit_novo_foi_criado_para_isto(self) -> None:
        """A carona é o ponto: reaproveitar o gatilho, não multiplicar units."""
        novos = list((REPO_ROOT / "assets").glob("*wrapper*.path")) + list(
            (REPO_ROOT / "assets").glob("*wrapper*.timer")
        )
        assert novos == []


@pytest.fixture(scope="module")
def instalador() -> str:
    return INSTALL.read_text(encoding="utf-8")


class TestOInstallRenderizaOsDois:

    def test_o_placeholder_novo_e_substituido(self, instalador: str) -> None:
        """A MORDIDA do install: sem esta linha, o unit sai com `__SENTINELA__` cru."""
        assert "s#__SENTINELA__#" in instalador

    def test_o_caminho_apontado_existe_no_repositorio(self, instalador: str) -> None:
        achado = re.search(
            r"SENTINELA_PY=\"\$\{ROOT_DIR\}/([^\"]+)\"", instalador
        )
        assert achado is not None, "o install precisa dizer QUAL arquivo é a sentinela"
        assert (REPO_ROOT / achado.group(1)).is_file()

    def test_os_dois_placeholders_no_mesmo_sed(self, instalador: str) -> None:
        """Dois `sed` em sequência já deixaram um placeholder cru nesta casa."""
        trecho = instalador.split("hefesto-steam-input-guard.service", 1)[0][-600:]
        assert trecho.count("-e ") >= 2

    def test_a_cura_entra_sem_flag(self, instalador: str) -> None:
        """Regra dela, 08/08: nada à mão, nada opt-in.

        O único jeito de o guard NÃO ser instalado é o `--keep-steam-input`, que
        já existia e é a escolha dela de manter o Steam Input — não uma opção
        nova que este trabalho tenha criado.
        """
        pedaco = instalador.split("SENTINELA_PY=", 1)[1][:400]
        assert "--enable" not in pedaco
        assert "--with-wrapper" not in pedaco
