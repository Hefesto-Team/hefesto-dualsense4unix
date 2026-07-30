"""BUG-INSTALL-ATROPELA-O-NAO-DO-AUTOSTART-01 + BUG-INSTALL-HELP-TRUNCADO-01.

Dois defeitos medidos em 29/07/2026 no `install.sh`:

(A) o passo 7a (unit do daemon) copiava, habilitava e reiniciava a unit do
    daemon SEM olhar nem `--no-systemd` nem a resposta ao prompt do passo 6.
    Os dois passos escrevem o MESMO arquivo, então o "não" dela era atropelado
    três linhas depois de o passo 6 dizer "pulado"/"auto-start desativado".
    Aqui o passo 7a e EXECUTADO de verdade (bloco extraido, bash real, stub de
    systemctl, HOME em tmp) nos quatro cenarios: default, `--no-systemd`,
    resposta "não" com daemon parado e resposta "não" com daemon no ar.
    Cuidado histórico: esta casa ja teve o bug OPOSTO
    (BUG-INSTALL-NAO-INSTALA-A-UNIT-DO-DAEMON-01), por isso o cenario default
    exige copia + enable + restart.

(B) o `--help` imprimia uma faixa FIXA do cabecalho (`sed -n '2,128p'`) que
    envelheceu: a flag real `--force-xwayland` ficava invisivel. Aqui o
    comando de ajuda e extraido do próprio script e EXECUTADO contra o
    install.sh, exigindo que TODA flag documentada no cabecalho apareca.

Molde: tests/unit/test_install_dkms_default.py e test_install_headless.py
(leem o texto do install.sh; execução real de trechos extraidos).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_PATH = REPO_ROOT / "install.sh"
DOC_PATH = REPO_ROOT / "docs" / "usage" / "instalacao.md"
INSTALL = INSTALL_PATH.read_text(encoding="utf-8")
DOC = DOC_PATH.read_text(encoding="utf-8")

UNIT = "hefesto-dualsense4unix.service"


def _sem_comentarios(texto: str) -> str:
    return "\n".join(re.sub(r"(^|\s)#.*$", r"\1", linha) for linha in texto.splitlines())


def _bloco_passo(marcador: str) -> str:
    """Texto de um passo do install.sh: do `step "N/11"` ate a linha de regua
    (`# ---...`) que abre o passo seguinte."""
    inicio = INSTALL.index(marcador)
    fim = re.search(r"^# -{10,}", INSTALL[inicio:], re.MULTILINE)
    assert fim is not None, f"fim do bloco {marcador} não encontrado"
    return INSTALL[inicio : inicio + fim.start()]


BLOCO_7A = _bloco_passo('step "7a/11"')


def _roda_passo_7a(
    tmp_path: Path, skip_systemd: int, enable_daemon: int, daemon_ativo: bool
) -> subprocess.CompletedProcess[str]:
    """Executa o passo 7a real com HOME em tmp e `systemctl` stubado."""
    stubs = tmp_path / "bin"
    stubs.mkdir(exist_ok=True)
    log = tmp_path / "systemctl.log"
    is_active_rc = 0 if daemon_ativo else 1
    stub = stubs / "systemctl"
    stub.write_text(
        "#!/bin/sh\n"
        f'printf "%s\\n" "$*" >> "{log}"\n'
        'case "$*" in\n'
        f'  *"is-active"*) exit {is_active_rc} ;;\n'
        "esac\n"
        "exit 0\n",
        encoding="utf-8",
    )
    stub.chmod(0o755)

    casa = tmp_path / "home"
    casa.mkdir(exist_ok=True)
    script = (
        "set -euo pipefail\n"
        'step() { printf "STEP %s | %s\\n" "$1" "$2"; }\n'
        'warn() { printf "WARN: %s\\n" "$*"; }\n'
        f"SKIP_SYSTEMD={skip_systemd}\n"
        f"enable_daemon={enable_daemon}\n"
        f"ROOT_DIR='{REPO_ROOT}'\n"
        f"{BLOCO_7A}\n"
    )
    env = dict(os.environ)
    env["PATH"] = f"{stubs}:{env.get('PATH', '/usr/bin:/bin')}"
    env["HOME"] = str(casa)
    resultado = subprocess.run(
        [BASH, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        timeout=30,
    )
    resultado.log_systemctl = (  # type: ignore[attr-defined]
        log.read_text(encoding="utf-8") if log.exists() else ""
    )
    resultado.unit_target = casa / ".config" / "systemd" / "user" / UNIT  # type: ignore[attr-defined]
    return resultado


class TestPasso7aObedece:
    """(A) — o passo 7a honra --no-systemd e a resposta do passo 6."""

    def test_default_sem_flag_copia_habilita_e_sobe(self, tmp_path: Path) -> None:
        # Guarda contra o bug OPOSTO (install NUNCA instalava a unit do daemon):
        # sem flag e com "sim" no passo 6, tudo continua acontecendo.
        r = _roda_passo_7a(tmp_path, skip_systemd=0, enable_daemon=1, daemon_ativo=False)
        assert r.returncode == 0, r.stderr
        assert r.unit_target.exists(), "unit do daemon não foi copiada no default"
        assert f"enable {UNIT}" in r.log_systemctl
        assert f"restart {UNIT}" in r.log_systemctl
        assert "daemon habilitado e no ar" in r.stdout

    def test_no_systemd_nao_copia_nem_habilita(self, tmp_path: Path) -> None:
        r = _roda_passo_7a(tmp_path, skip_systemd=1, enable_daemon=0, daemon_ativo=False)
        assert r.returncode == 0, r.stderr
        assert not r.unit_target.exists(), (
            "--no-systemd: o passo 7a copiou a unit que o passo 6 disse ter pulado"
        )
        assert "enable" not in r.log_systemctl, (
            "--no-systemd: o passo 7a habilitou o daemon a revelia da flag"
        )
        assert "restart" not in r.log_systemctl
        assert "pulado (--no-systemd)" in r.stdout

    def test_resposta_nao_copia_mas_nao_habilita_nem_inicia(self, tmp_path: Path) -> None:
        r = _roda_passo_7a(tmp_path, skip_systemd=0, enable_daemon=0, daemon_ativo=False)
        assert r.returncode == 0, r.stderr
        # A unit CONTINUA sendo copiada (simetria com o uninstall, que a remove).
        assert r.unit_target.exists(), "a unit precisa ser copiada mesmo sem auto-start"
        assert f"enable {UNIT}" not in r.log_systemctl, (
            'ela respondeu "não" ao auto-start no boot e o passo 7a habilitou'
        )
        assert f"restart {UNIT}" not in r.log_systemctl, (
            'ela respondeu "não" e o passo 7a subiu o daemon parado'
        )
        assert f"start {UNIT}" not in r.log_systemctl
        assert "auto-start NÃO habilitado" in r.stdout

    def test_resposta_nao_com_daemon_no_ar_so_reinicia(self, tmp_path: Path) -> None:
        # Reinstalacao por cima: o daemon em memoria e o binário ANTIGO. Trocar
        # o binário e legitimo; habilitar no boot, não.
        r = _roda_passo_7a(tmp_path, skip_systemd=0, enable_daemon=0, daemon_ativo=True)
        assert r.returncode == 0, r.stderr
        assert f"restart {UNIT}" in r.log_systemctl
        assert f"enable {UNIT}" not in r.log_systemctl
        assert "unit atualizada" in r.stdout


class TestPasso7aContratoDeTexto:
    """(A) — o gate precisa existir no texto, antes de qualquer acao."""

    def test_enable_daemon_nasce_fora_do_if_do_passo_6(self) -> None:
        # Sob `set -u`, se `enable_daemon` so existisse dentro do ramo `else` do
        # passo 6, o passo 7a mataria o install com --no-systemd.
        assert re.search(r"^enable_daemon=0$", INSTALL, re.MULTILINE), (
            "enable_daemon precisa nascer em coluna 0 (fora do if do passo 6)"
        )
        assert INSTALL.index("\nenable_daemon=0\n") < INSTALL.index('step "7a/11"')

    def test_gate_vem_antes_do_enable_e_do_restart(self) -> None:
        codigo = _sem_comentarios(BLOCO_7A)
        assert '"${SKIP_SYSTEMD}"' in codigo, "passo 7a sem gate de --no-systemd"
        assert '"${enable_daemon}"' in codigo, (
            "passo 7a sem gate da resposta dada no passo 6"
        )
        primeiro_enable = codigo.index("systemctl --user enable")
        assert codigo.index('"${SKIP_SYSTEMD}"') < primeiro_enable
        assert codigo.index('"${enable_daemon}"') < primeiro_enable

    def test_cabecalho_nao_mente_mais_sobre_o_default(self) -> None:
        cabecalho = "\n".join(INSTALL.splitlines()[:200])
        assert "unit do daemon é COPIADA mas NÃO habilitada" not in cabecalho, (
            "o cabecalho afirmava um default falso desde que o passo 7a nasceu"
        )
        assert "HABILITADA no boot" in cabecalho


def _roda_help() -> subprocess.CompletedProcess[str]:
    """Executa o comando de ajuda extraido do próprio install.sh."""
    inicio = INSTALL.index("-h|--help)")
    fim = INSTALL.index("exit 0", inicio)
    corpo = INSTALL[inicio + len("-h|--help)") : fim]
    corpo = corpo.replace('"${BASH_SOURCE[0]}"', f"'{INSTALL_PATH}'")
    assert "BASH_SOURCE" not in corpo, "o corpo do --help ficou com BASH_SOURCE solto"
    return subprocess.run(
        [BASH, "-c", "set -euo pipefail\n" + corpo],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _flags_do_cabecalho() -> list[str]:
    """Flags documentadas na coluna de flags do cabecalho (`#   --alguma-coisa`)."""
    cabecalho = INSTALL[: INSTALL.index("\nset -euo pipefail")]
    achadas = re.findall(r"(?m)^#\s{2,}(--[a-z0-9-]+)", cabecalho)
    return sorted(set(achadas))


class TestHelpCompleto:
    """(B) — o --help imprime o cabecalho INTEIRO, sem numero magico."""

    def test_help_nao_usa_faixa_fixa(self) -> None:
        codigo = _sem_comentarios(INSTALL)
        assert not re.search(r"sed -n '2,\d+p'", codigo), (
            "a faixa do --help não pode ser um numero magico que envelhece"
        )

    def test_help_termina_no_fim_do_bloco_de_comentario(self) -> None:
        r = _roda_help()
        assert r.returncode == 0, r.stderr
        assert "Reexecutável (idempotente)." in r.stdout, (
            "o --help não chega a última linha do cabecalho"
        )
        # E não passa dele: a primeira linha de código não pode sair no help.
        assert "set -euo pipefail" not in r.stdout

    @pytest.mark.parametrize("flag", ["--force-xwayland", "--no-snd-quirk"])
    def test_flags_antes_invisiveis_aparecem(self, flag: str) -> None:
        r = _roda_help()
        assert r.returncode == 0, r.stderr
        assert flag in r.stdout, f"{flag} e flag REAL e não aparece no --help"

    def test_toda_flag_do_cabecalho_sai_no_help(self) -> None:
        r = _roda_help()
        assert r.returncode == 0, r.stderr
        flags = _flags_do_cabecalho()
        assert "--force-xwayland" in flags, "extracao de flags do cabecalho quebrou"
        faltando = [f for f in flags if f not in r.stdout]
        assert not faltando, f"flags documentadas e ausentes do --help: {faltando}"

    def test_no_snd_quirk_esta_documentada_no_cabecalho(self) -> None:
        assert "--no-snd-quirk" in _flags_do_cabecalho(), (
            "--no-snd-quirk existe no parser e precisa estar no cabecalho"
        )


class TestFlagSugeridaExiste:
    """(C) — o install não pode sugerir flag que ele mesmo rejeita."""

    def test_mensagem_da_regra_75_aponta_o_comando_que_funciona(self) -> None:
        linha = next(
            linha
            for linha in INSTALL.splitlines()
            if "áudio-off" in linha and "printf" in linha
        )
        assert "--disable-usb-audio" in linha
        assert "install_udev.sh --disable-usb-audio" in linha, (
            "a flag e do scripts/install_udev.sh; sugerida solta, o install aborta "
            "com 'argumento desconhecido' e nada e instalado"
        )

    def test_parser_do_install_realmente_nao_conhece_a_flag(self) -> None:
        # A prova de que a sugestao antiga era veneno: o parser de flags não tem
        # case para ela, entao ela cai no `*)` que aborta com código 2.
        inicio = INSTALL.index('for arg in "$@"; do')
        parser = _sem_comentarios(INSTALL[inicio : INSTALL.index("\ndone\n", inicio)])
        assert "--disable-usb-audio" not in parser
        assert "exit 2" in parser, "o desconhecido continua abortando (nada instalado)"


class TestDocumentacaoHonesta:
    """(D) — docs/usage/instalacao.md não pode mentir nos pontos medidos."""

    def test_aponta_a_versao_corrente_e_nao_a_branch_antiga(self) -> None:
        assert "sprint/harmonia-uhid" not in DOC
        assert "alfa 0.1.1" not in DOC
        assert "git checkout v0.3.0" in DOC

    def test_no_udev_nao_promete_cobrir_todo_etc(self) -> None:
        assert "e todos os passos que escrevem em `/etc`" not in DOC, (
            "os passos de DKMS escrevem em /etc/modprobe.d e sao gateados por --no-dkms"
        )
        assert "hefesto-hid-playstation.conf" in DOC

    def test_cmdline_declara_o_quirk_que_entra_por_default(self) -> None:
        linha = next(linha for linha in DOC.splitlines() if "cmdline do kernel |" in linha)
        assert "usbcore.quirks=054c:0ce6:gn,054c:0df2:gn" in linha, (
            "o passo 3e grava os quirks POR DEFAULT — a tabela omitia"
        )

    def test_curas_de_bluetooth_default_estao_nomeadas(self) -> None:
        for termo in ("5.86", "bt-agent", "hefesto-bt-health-watchdog.timer", "bt-bonds"):
            assert termo in DOC, f"cura de BT default ausente da página: {termo}"
