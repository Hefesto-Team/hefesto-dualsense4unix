"""Onda T — scripts/dkms_lib.sh (infra DKMS genérica, reusada pela Onda W)."""

from __future__ import annotations

import gzip
import lzma
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_PATH = REPO_ROOT / "scripts" / "dkms_lib.sh"
LIB = LIB_PATH.read_text(encoding="utf-8") if LIB_PATH.exists() else ""


def _sem_comentarios(texto: str) -> str:
    """Remove comentários de linha (# no início ou precedido de espaço) —"""
    linhas = [re.sub(r"(^|\s)#.*$", r"\1", linha) for linha in texto.splitlines()]
    return "\n".join(linhas)


def _stub(diretorio: Path, nome: str, corpo: str) -> None:
    caminho = diretorio / nome
    caminho.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
    caminho.chmod(0o755)


def _roda(
    script: str, path: str, env_extra: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = path
    env["HEFESTO_EFIVARS_ROOT"] = "/nao-existe/efivars-sem-secure-boot"
    env["HEFESTO_SYS_MODULE"] = "/nao-existe/sys-module"
    env.update(env_extra or {})
    completo = f"source '{LIB_PATH}'\n{script}\n"
    return subprocess.run(
        [BASH, "-c", completo], capture_output=True, text=True, check=False, env=env
    )


class TestContratoDeTexto:
    def test_lib_existe(self) -> None:
        assert LIB_PATH.exists(), "scripts/dkms_lib.sh ausente (lote install da Onda T)"

    def test_bash_n_limpo(self) -> None:
        resultado = subprocess.run(
            ["bash", "-n", str(LIB_PATH)], capture_output=True, text=True, check=False
        )
        assert resultado.returncode == 0, resultado.stderr

    def test_proibido_modprobe_rmmod_insmod(self) -> None:
        codigo = _sem_comentarios(LIB)
        assert not re.search(r"\b(modprobe|rmmod|insmod)\b", codigo), (
            "dkms_lib.sh NUNCA pode carregar/descarregar módulo"
        )

    def test_api_completa_das_quatro_funcoes(self) -> None:
        for funcao in (
            "dkms_install_patched_module",
            "dkms_remove_patched_module",
            "dkms_modulo_da_casa",
            "dkms_module_loaded",
        ):
            assert re.search(rf"^{funcao}\(\) \{{", LIB, re.MULTILINE), (
                f"função {funcao} ausente da API"
            )

    def test_idempotencia_resincroniza_so_se_mudou_e_leva_a_serie(self) -> None:
        assert "diff -rq -x LICENSES" in LIB, (
            "re-sincronizar /usr/src só quando os assets mudaram (idempotente)"
        )
        assert 'rm -rf "${_srcdst}/patch"' not in LIB, (
            "o patch/ é a série que o PRE_BUILD aplica no fonte de fábrica do kernel que roda"
        )

    def test_build_e_install_tolerantes_a_reexecucao(self) -> None:
        """Idempotência lida SEM cano — a régua envelheceu em 01/09/2026."""
        assert re.search(
            r'\[\[\s*!\s*"\$\(_dkms_status_texto[^)]*\)"\s*=~\s*\(built\|installed\)', LIB
        ), "dkms build só roda se ainda não construído, e lido sem cano (idempotente)"
        assert re.search(
            r'\[\[\s*"\$\(_dkms_status_texto[^)]*\)"\s*!=\s*\*installed\*', LIB
        ), "dkms install só roda se ainda não instalado, e lido sem cano (idempotente)"
        assert not re.search(r"dkms status[^\n|]*\|\s*grep", _sem_comentarios(LIB)), (
            "SIGPIPE: `dkms status | grep` devolve 141 quando ACHA, sob pipefail — "
            "leia para variável (_dkms_status_texto) e pergunte à variável"
        )

    def test_validacao_pela_copia_do_dkms_nunca_srcversion(self) -> None:
        assert "modinfo -F filename" in LIB
        assert 'cmp -s "${_link}/module/${_ko##*/}"' in LIB
        fora = re.sub(
            r"_dkms_srcversion_do_modulo\(\) \{.*?\n\}\n|_dkms_carregado_e_da_casa\(\) \{.*?\n\}\n",
            "", LIB, flags=re.S,
        )
        assert "srcversion" not in fora, (
            "srcversion não distingue in-tree de DKMS (armadilha do estudo): só serve para "
            "comparar o carregado com o arquivo que a cópia do DKMS já provou ser da casa"
        )
        carregado = LIB[LIB.index("_dkms_carregado_e_da_casa() {"):]
        carregado = carregado[:carregado.index("\n}\n")]
        assert carregado.index("dkms_ko_da_casa") < carregado.index(
            "_dkms_srcversion_do_modulo")

    def test_fail_safe_documenta_as_curas_nos_avisos(self) -> None:
        assert "sudo apt install dkms" in LIB
        assert "sudo apt install linux-headers-" in LIB
        assert "sem dkms.conf" in LIB, "source incompleto também é warn + return 0"


class TestFailSafeSemEscalar:
    """Branches de pré-requisito: warn honesto, return 0, sudo NUNCA chamado."""

    def test_dkms_ausente_avisa_retorna_0_e_nao_escala(self, tmp_path: Path) -> None:
        stubs = tmp_path / "bin"
        stubs.mkdir()
        log_sudo = tmp_path / "sudo.log"
        _stub(stubs, "uname", 'echo "0.0.0-hefesto-teste"')
        _stub(stubs, "sudo", f'echo "sudo $@" >> "{log_sudo}"\nexit 0')
        resultado = _roda(
            "dkms_install_patched_module hefesto-teste 9.9.9 /caminho/inexistente hid-teste\n"
            'printf "RC=%s\\n" "$?"',
            path=str(stubs),
        )
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "dkms ausente" in resultado.stdout
        assert not log_sudo.exists(), "fail-safe não pode escalar privilégio"

    def test_headers_ausentes_avisa_retorna_0_e_nao_escala(self, tmp_path: Path) -> None:
        stubs = tmp_path / "bin"
        stubs.mkdir()
        log_sudo = tmp_path / "sudo.log"
        _stub(stubs, "uname", 'echo "0.0.0-hefesto-fake"')
        _stub(stubs, "dkms", "exit 0")
        _stub(stubs, "sudo", f'echo "sudo $@" >> "{log_sudo}"\nexit 0')
        resultado = _roda(
            "dkms_install_patched_module hefesto-teste 9.9.9 /caminho/inexistente hid-teste\n"
            'printf "RC=%s\\n" "$?"',
            path=str(stubs),
        )
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "headers do kernel 0.0.0-hefesto-fake ausentes" in resultado.stdout
        assert not log_sudo.exists(), "fail-safe não pode escalar privilégio"


class TestRemocao:
    def test_remove_sem_dkms_limpa_usr_src_e_roda_depmod(self, tmp_path: Path) -> None:
        stubs = tmp_path / "bin"
        stubs.mkdir()
        log_sudo = tmp_path / "sudo.log"
        _stub(stubs, "sudo", f'echo "sudo $@" >> "{log_sudo}"\nexit 0')
        resultado = _roda(
            "dkms_remove_patched_module hefesto-teste 9.9.9\n"
            'printf "RC=%s\\n" "$?"',
            path=str(stubs),
        )
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "removido" in resultado.stdout
        registro = log_sudo.read_text(encoding="utf-8")
        assert "rm -rf /usr/src/hefesto-teste-9.9.9" in registro
        assert "depmod -a" in registro
        assert "modprobe" not in registro, "in-tree volta SOZINHO no boot — sem reload"

    def test_remove_com_pkg_registrado_chama_dkms_remove_all(self, tmp_path: Path) -> None:
        stubs = tmp_path / "bin"
        stubs.mkdir()
        log_sudo = tmp_path / "sudo.log"
        marcador = tmp_path / "dkms-remove-rodou"
        _stub(
            stubs,
            "sudo",
            f'echo "sudo $@" >> "{log_sudo}"\n'
            'case "$1" in\n  dkms) exec "$@" ;;\n  *) exit 0 ;;\nesac',
        )
        _stub(
            stubs,
            "dkms",
            f'echo "dkms $@" >> "{log_sudo}"\n'
            'case "$1" in\n'
            '  status) echo "hefesto-teste/9.9.9: added" ;;\n'
            f'  remove) touch "{marcador}" ;;\n'
            "esac\nexit 0",
        )
        resultado = _roda(
            "dkms_remove_patched_module hefesto-teste 9.9.9\n"
            'printf "RC=%s\\n" "$?"',
            path=f"{stubs}:/usr/bin:/bin",
        )
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert marcador.exists(), "dkms remove precisa ser invocado quando registrado"
        registro = log_sudo.read_text(encoding="utf-8")
        assert "dkms remove hefesto-teste/9.9.9 --all" in registro, (
            "--all desregistra de TODOS os kernels (simetria total)"
        )
        assert "modprobe" not in registro


class TestConsultas:
    def test_modulo_da_casa_e_a_copia_que_o_dkms_guarda(self, tmp_path: Path) -> None:
        arvore = tmp_path / "dkms" / "hefesto-hid-nintendo" / "kernel-x-x86_64" / "module"
        arvore.mkdir(parents=True)
        (arvore / "hid-nintendo.ko").write_bytes(b"o do Hefesto")
        ko = tmp_path / "updates" / "dkms" / "hid-nintendo.ko"
        ko.parent.mkdir(parents=True)
        ko.write_bytes(b"o do Hefesto")
        stubs = tmp_path / "bin"
        stubs.mkdir()
        _stub(stubs, "modinfo", f'echo "{ko}"')
        resultado = _roda(
            'dkms_modulo_da_casa hid_nintendo; printf "RC=%s\\n" "$?"',
            path=f"{stubs}:/usr/bin:/bin",
            env_extra={"HEFESTO_DKMS_TREE": str(tmp_path / "dkms")},
        )
        assert "RC=0" in resultado.stdout, resultado.stderr
        ko.write_bytes(b"o de fabrica")
        resultado = _roda(
            'dkms_modulo_da_casa hid_nintendo; printf "RC=%s\\n" "$?"',
            path=f"{stubs}:/usr/bin:/bin",
            env_extra={"HEFESTO_DKMS_TREE": str(tmp_path / "dkms")},
        )
        assert "RC=1" in resultado.stdout, resultado.stderr

    def test_modulo_da_casa_falha_se_modinfo_falha(self, tmp_path: Path) -> None:
        stubs = tmp_path / "bin"
        stubs.mkdir()
        _stub(stubs, "modinfo", "exit 1")
        resultado = _roda(
            'dkms_modulo_da_casa hid_nintendo; printf "RC=%s\\n" "$?"',
            path=str(stubs),
        )
        assert "RC=0" not in resultado.stdout
        assert "RC=1" in resultado.stdout

    def test_module_loaded_nome_inexistente_e_falso(self, tmp_path: Path) -> None:
        stubs = tmp_path / "bin"
        stubs.mkdir()
        resultado = _roda(
            'dkms_module_loaded hefesto-mod-inexistente-xyz; printf "RC=%s\\n" "$?"',
            path=str(stubs),
        )
        assert "RC=1" in resultado.stdout, resultado.stderr

    def test_module_loaded_converte_hifen_para_underscore(self) -> None:
        assert "${1//-/_}" in LIB


def _prepara_e2e(
    tmp_path: Path, build_falha: bool = False, destino: str = "updates/dkms"
) -> dict[str, Path | str]:
    """Ambiente de execução real da lib SEM root: raízes em tmp (costura"""
    stubs = tmp_path / "bin"
    stubs.mkdir(exist_ok=True)
    log = tmp_path / "calls.log"
    estado = tmp_path / "estado"
    estado.mkdir(exist_ok=True)
    src_root = tmp_path / "usr-src"
    src_root.mkdir(exist_ok=True)
    kver = "0.0.0-hefesto-e2e"
    (tmp_path / "modules" / kver / "build").mkdir(parents=True, exist_ok=True)
    assets = tmp_path / "assets-dkms"
    (assets / "patch").mkdir(parents=True, exist_ok=True)
    (assets / "dkms.conf").write_text(
        'PACKAGE_NAME="hefesto-teste"\nPACKAGE_VERSION="9.9.9"\n', encoding="utf-8"
    )
    (assets / "hid-teste.c").write_text("// fonte patchada\n", encoding="utf-8")
    (assets / "patch" / "0001-ref.patch").write_text("referência\n", encoding="utf-8")
    _stub(stubs, "uname", f'echo "{kver}"')
    _stub(stubs, "sudo", f'echo "sudo $@" >> "{log}"\nexec "$@"')
    for dono in ("chown", "chmod"):
        _stub(stubs, dono, "exit 0")
    ko = tmp_path / "modules" / kver / destino / "hid-teste.ko"
    guardado = tmp_path / "dkms" / "hefesto-teste" / f"kernel-{kver}-x86_64" / "module"
    _stub(stubs, "modinfo", f'echo "{ko}"')
    build_acao = "exit 1" if build_falha else f'touch "{estado}/built"'
    _stub(
        stubs,
        "dkms",
        f'echo "dkms $@" >> "{log}"\n'
        'case "$1" in\n'
        "  status)\n"
        f'    [ -f "{estado}/added" ] || exit 0\n'
        f'    if [ -f "{estado}/installed" ]; then echo "hefesto-teste/9.9.9: installed"\n'
        f'    elif [ -f "{estado}/built" ]; then echo "hefesto-teste/9.9.9: built"\n'
        '    else echo "hefesto-teste/9.9.9: added"; fi ;;\n'
        f'  add) touch "{estado}/added" ;;\n'
        f"  build) {build_acao} ;;\n"
        f'  install) touch "{estado}/installed"; mkdir -p "{guardado}" "{ko.parent}"\n'
        f'    echo ko > "{guardado}/hid-teste.ko"; cp "{guardado}/hid-teste.ko" "{ko}" ;;\n'
        f'  remove) rm -f "{estado}/added" "{estado}/built" "{estado}/installed" ;;\n'
        "esac\nexit 0",
    )
    return {
        "path": f"{stubs}:/usr/bin:/bin",
        "log": log,
        "src_root": src_root,
        "assets": assets,
    }


def _roda_e2e(
    tmp_path: Path, script: str, build_falha: bool = False, destino: str = "updates/dkms"
) -> tuple[subprocess.CompletedProcess[str], str, Path]:
    cena = _prepara_e2e(tmp_path, build_falha=build_falha, destino=destino)
    resultado = _roda(
        script,
        path=str(cena["path"]),
        env_extra={
            "HEFESTO_DKMS_SRC_ROOT": str(cena["src_root"]),
            "HEFESTO_DKMS_MODULES_ROOT": str(tmp_path / "modules"),
            "HEFESTO_DKMS_TREE": str(tmp_path / "dkms"),
        },
    )
    log = Path(str(cena["log"]))
    registro = log.read_text(encoding="utf-8") if log.exists() else ""
    return resultado, registro, Path(str(cena["src_root"]))


class TestExecucaoDePontaAPonta:
    """Achado #4 do corretor: os contratos "2º install = no-op" e "build"""

    SCRIPT_DUAS_CHAMADAS = (
        "dkms_install_patched_module hefesto-teste 9.9.9 {assets} hid-teste\n"
        'printf "RC1=%s\\n" "$?"\n'
        "dkms_install_patched_module hefesto-teste 9.9.9 {assets} hid-teste\n"
        'printf "RC2=%s\\n" "$?"\n'
    )

    @pytest.mark.parametrize("destino", ["updates/dkms", "extra", "updates"])
    def test_primeira_chamada_faz_add_build_install_e_valida(
        self, tmp_path: Path, destino: str
    ) -> None:
        """O destino é o que o dkms dá a cada distro; o initramfs se marca em todos."""
        script = (
            "dkms_install_patched_module hefesto-teste 9.9.9 "
            f"{tmp_path / 'assets-dkms'} hid-teste\n"
            'printf "RC=%s STALE=%s\\n" "$?" "${_DKMS_INITRAMFS_STALE}"\n'
        )
        resultado, registro, src_root = _roda_e2e(tmp_path, script, destino=destino)
        assert "RC=0 STALE=1" in resultado.stdout, resultado.stdout + resultado.stderr
        assert registro.count("sudo dkms add hefesto-teste/9.9.9") == 1
        assert registro.count("sudo dkms build hefesto-teste/9.9.9") == 1
        assert registro.count("sudo dkms install hefesto-teste/9.9.9") == 1
        assert "ok: modinfo resolve" in resultado.stdout
        destino = src_root / "hefesto-teste-9.9.9"
        assert (destino / "hid-teste.c").exists(), "source sincronizado no *_SRC_ROOT"
        assert (destino / "patch").is_dir(), "a série de patch/ viaja para o PRE_BUILD"

    def test_segunda_chamada_e_no_op_real(self, tmp_path: Path) -> None:
        script = self.SCRIPT_DUAS_CHAMADAS.format(assets=tmp_path / "assets-dkms")
        resultado, registro, _ = _roda_e2e(tmp_path, script)
        assert "RC1=0" in resultado.stdout and "RC2=0" in resultado.stdout, resultado.stderr
        assert "já sincronizado" in resultado.stdout, (
            "a 2ª chamada precisa reconhecer o source já em dia (diff -rq)"
        )
        assert registro.count("sudo dkms remove") == 1
        copias_de_source = [
            linha
            for linha in registro.splitlines()
            if "sudo cp -a" in linha and "LICENSES" not in linha
        ]
        assert len(copias_de_source) == 1, copias_de_source
        assert registro.count("sudo dkms add") == 1
        assert registro.count("sudo dkms build hefesto-teste/9.9.9") == 1
        assert registro.count("sudo dkms install hefesto-teste/9.9.9") == 1

    def test_build_falho_pula_install_e_nao_valida_sucesso(self, tmp_path: Path) -> None:
        script = (
            "dkms_install_patched_module hefesto-teste 9.9.9 "
            f"{tmp_path / 'assets-dkms'} hid-teste\n"
            'printf "RC=%s\\n" "$?"\n'
        )
        resultado, registro, _ = _roda_e2e(tmp_path, script, build_falha=True)
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "dkms build FALHOU" in resultado.stdout, "warn honesto do fail-safe"
        assert "sudo dkms install" not in registro, (
            "build falho NUNCA pode seguir para o dkms install (fail-safe)"
        )
        assert "ok: modinfo resolve" not in resultado.stdout, (
            "sem build não há validação de sucesso (mensagem seria falsa)"
        )


class TestRemocaoFalhasNaoMentem:
    """Achados #7 e #8 do corretor: a remoção era o único caminho com"""

    def test_dkms_remove_falho_preserva_registro_e_source_sem_anunciar_sucesso(
        self, tmp_path: Path
    ) -> None:
        stubs = tmp_path / "bin"
        stubs.mkdir()
        log = tmp_path / "calls.log"
        _stub(
            stubs,
            "sudo",
            f'echo "sudo $@" >> "{log}"\n'
            'case "$1" in\n  dkms) exec "$@" ;;\n  *) exit 0 ;;\nesac',
        )
        _stub(
            stubs,
            "dkms",
            f'echo "dkms $@" >> "{log}"\n'
            'case "$1" in\n'
            '  status) echo "hefesto-teste/9.9.9: installed"; exit 0 ;;\n'
            "  remove) exit 1 ;;\n"
            "esac\nexit 0",
        )
        resultado = _roda(
            "dkms_remove_patched_module hefesto-teste 9.9.9\n"
            'printf "RC=%s\\n" "$?"',
            path=f"{stubs}:/usr/bin:/bin",
        )
        assert "RC=0" in resultado.stdout, resultado.stderr
        registro = log.read_text(encoding="utf-8")
        assert "sudo rm -rf" not in registro, (
            "com o registro DKMS de pé, o source em /usr/src é do dkms — "
            "apagá-lo impede a convergência do próximo uninstall"
        )
        assert "removido — o módulo in-tree" not in resultado.stdout, (
            "'dkms status' ainda lista o pacote: anunciar sucesso é mentira"
        )
        assert "remova à mão" in resultado.stdout, "warn aponta a cura manual"

    def test_rm_falho_nao_aborta_o_chamador_com_set_e(self, tmp_path: Path) -> None:
        stubs = tmp_path / "bin"
        stubs.mkdir()
        log = tmp_path / "calls.log"
        _stub(
            stubs,
            "sudo",
            f'echo "sudo $@" >> "{log}"\n'
            'case "$1" in\n  rm) exit 1 ;;\n  *) exit 0 ;;\nesac',
        )
        script = (
            "set -euo pipefail\n"
            f"source '{LIB_PATH}'\n"
            "dkms_remove_patched_module hefesto-teste 9.9.9\n"
            'printf "SOBREVIVEU=%s\\n" "$?"\n'
        )
        env = dict(os.environ)
        env["PATH"] = str(stubs)
        resultado = subprocess.run(
            [BASH, "-c", script], capture_output=True, text=True, check=False, env=env
        )
        assert "SOBREVIVEU=0" in resultado.stdout, (
            f"set -e matou o uninstall no rm -rf: {resultado.stderr}"
        )
        assert "não consegui apagar" in resultado.stdout, "warn honesto do resto"


class TestOFonteJaInstaladoFicaSoDoRoot:
    """O fonte em /usr/src/hefesto-* que já existia vira root:root sem escrita de grupo e outros.

    MORDIDA (feita, com a cura devolvida): sem o chown e o chmod da `dkms_fontes_so_do_root`, o
    sudo de mentira não ouve nada e o caso reprova; sem a chamada no install-host-udev.sh, o caso
    da chamada reprova.
    """

    def _lar(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        bin_ = tmp_path / "bin"
        bin_.mkdir()
        chamadas = tmp_path / "chamadas.log"
        _stub(bin_, "sudo", f'echo "sudo $*" >> "{chamadas}"')
        src = tmp_path / "src"
        for nome in ("hefesto-hid-playstation-1.0.0", "hefesto-uhid-1.0.0", "outra-coisa-1.0"):
            (src / nome).mkdir(parents=True)
        (src / "hefesto-link-1.0.0").symlink_to(tmp_path)
        return bin_, chamadas, src

    def test_toda_pasta_hefesto_vira_so_do_root_a_cada_corrida(self, tmp_path: Path) -> None:
        bin_, chamadas, src = self._lar(tmp_path)
        for _ in range(2):
            feito = _roda("dkms_fontes_so_do_root", f"{bin_}:/usr/bin:/bin",
                          {"HEFESTO_DKMS_SRC_ROOT": str(src)})
            assert feito.returncode == 0, feito.stderr
        linhas = chamadas.read_text(encoding="utf-8").splitlines()
        for nome in ("hefesto-hid-playstation-1.0.0", "hefesto-uhid-1.0.0"):
            assert linhas.count(f"sudo chown -R root:root {src / nome}") == 2
            assert linhas.count(f"sudo chmod -R go-w {src / nome}") == 2
        assert not any("outra-coisa" in x or "hefesto-link" in x for x in linhas)

    def test_o_sudo_que_falha_avisa_e_devolve_erro(self, tmp_path: Path) -> None:
        bin_, _chamadas, src = self._lar(tmp_path)
        _stub(bin_, "sudo", "exit 1")
        feito = _roda("dkms_fontes_so_do_root", f"{bin_}:/usr/bin:/bin",
                      {"HEFESTO_DKMS_SRC_ROOT": str(src)})
        assert feito.returncode != 0
        assert "não ficou só do root" in feito.stdout + feito.stderr

    def test_o_install_normaliza_a_cada_corrida(self) -> None:
        udev = (REPO_ROOT / "scripts" / "install-host-udev.sh").read_text(encoding="utf-8")
        fim = udev[udev.rindex('source "${DKMS_LIB_SH}"'):]
        assert fim.index("dkms_fontes_so_do_root") < fim.index("dkms_flush_initramfs")


SECURE_BOOT = "SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
CHAVE = b"0\x82\x03\x1bCHAVE-DE-MENTIRA-DO-DKMS\x00\x01\x02"
PREPARADOR = REPO_ROOT / "assets" / "dkms" / "hid-playstation" / "preparar-o-fonte.py"
CINCO_PREPARADORES = sorted((REPO_ROOT / "assets" / "dkms").glob("*/preparar-o-fonte.py"))


def _estado_do_secure_boot(
    raiz: Path, *, ligado: bool | None, inscrita: bool, leitura: str = "completa",
    chave_privada: bool = True,
) -> dict[str, str]:
    """efivars, chave e lista do shim de mentira, no formato que as duas leituras recebem.

    ``leitura`` diz o que as leituras alcançam: ``completa``, ``sem-chave-publica`` (a chave que
    o DKMS assina não está onde se lê) ou ``sem-lista`` (nenhuma lista da MOK se lê). O
    ``mokutil`` da máquina fica atrás de um que não responde: ver ``_sem_mokutil``. A chave
    privada que o DKMS assina existe (``mok.key``, dita no ``framework.conf`` de mentira) salvo
    com ``chave_privada=False``.
    """
    efivars = raiz / "efivars"
    efivars.mkdir()
    calado = raiz / "mokutil-calado"
    calado.mkdir()
    _stub(calado, "mokutil", "exit 1")
    if ligado is not None:
        (efivars / SECURE_BOOT).write_bytes(b"\x06\x00\x00\x00" + (b"\x01" if ligado else b"\x00"))
    (raiz / "mok.pub").write_bytes(CHAVE)
    (raiz / "MokListRT").write_bytes(CHAVE if inscrita else b"outra-chave")
    if chave_privada:
        (raiz / "mok.key").write_bytes(b"CHAVE-PRIVADA-DE-MENTIRA")
    (raiz / "framework-da-chave.conf").write_text(
        f'mok_signing_key="{raiz / "mok.key"}"\n', encoding="utf-8")
    return {
        "HEFESTO_DKMS_FRAMEWORK_CONFS": str(raiz / "framework-da-chave.conf"),
        "HEFESTO_EFIVARS_ROOT": str(efivars),
        "HEFESTO_DKMS_MOK_PUB": str(raiz / ("sem-chave.pub" if leitura == "sem-chave-publica"
                                            else "mok.pub")),
        "HEFESTO_MOK_LISTAS": str(raiz / ("sem-lista" if leitura == "sem-lista"
                                          else "MokListRT")),
        "HEFESTO_SYS_MODULE": str(raiz / "sem-modulo-carregado"),
    }


def _sem_mokutil(estado: dict[str, str], resto: str = "/usr/bin:/bin") -> str:
    """O ``PATH`` em que o ``mokutil`` da máquina não responde pela leitura de mentira."""
    return f"{Path(estado['HEFESTO_EFIVARS_ROOT']).parent / 'mokutil-calado'}:{resto}"


ESTADOS = [(True, False), (True, True), (False, False), (None, False)]
ESTADOS_IDS = ["ligado-sem-chave", "ligado-com-chave", "desligado", "sem-efi"]
SEM_LEITURA = ["sem-chave-publica", "sem-lista"]


class TestSecureBootLigadoDevolveODriverDeFabrica:
    """O-SECURE-BOOT-LIGADO-DEVOLVE-O-DRIVER-DE-FABRICA-01: sem a chave o módulo da casa sai.

    Sai pelo ``dkms remove`` de cada kernel em que está instalado ou só construído: o ``dkms
    uninstall`` deixava o construído, o ``--exclusivo`` não exclui o kernel que já tem construção, e
    o ``autoinstall`` (o do boot no Fedora, o do pacote do kernel refeito) o reinstalava.
    """

    STATUS = (
        "hefesto-teste/9.9.9, 7.1.5-generic, x86_64: installed\n"
        "hefesto-teste/9.9.9, 7.0.1-generic, x86_64: installed (WARNING! Diff between built "
        "and installed module!)\n"
        "hefesto-teste/9.9.9, 6.9.0-generic, x86_64: built\n"
    )

    def _instalar(
        self, tmp_path: Path, estado: dict[str, str], status: str, modinfo: str = ""
    ) -> tuple[str, str]:
        bin_ = tmp_path / "bin"
        bin_.mkdir()
        if modinfo:
            _stub(bin_, "modinfo", modinfo)
        chamadas = tmp_path / "chamadas.log"
        _stub(bin_, "uname", 'echo "7.1.5-generic"')
        _stub(bin_, "mokutil", "exit 1")
        _stub(bin_, "sudo", f'echo "sudo $*" >> "{chamadas}"\nexec "$@"')
        _stub(bin_, "depmod", f'echo "depmod $*" >> "{chamadas}"')
        _stub(
            bin_, "dkms",
            f'echo "dkms $*" >> "{chamadas}"\n'
            f'[ "$1" = status ] && cat "{tmp_path / "status.txt"}"\nexit 0',
        )
        (tmp_path / "status.txt").write_text(status, encoding="utf-8")
        modulos = tmp_path / "modules"
        (modulos / "7.1.5-generic" / "build").mkdir(parents=True)
        fonte = tmp_path / "fonte"
        fonte.mkdir()
        (fonte / "dkms.conf").write_text('PACKAGE_VERSION="9.9.9"\n', encoding="utf-8")
        feito = _roda(
            f"dkms_install_patched_module hefesto-teste 9.9.9 '{fonte}' hid-teste\n"
            'printf "STALE=%s\\n" "${_DKMS_INITRAMFS_STALE}"',
            f"{bin_}:/usr/bin:/bin",
            {"HEFESTO_DKMS_MODULES_ROOT": str(modulos),
             "HEFESTO_DKMS_SRC_ROOT": str(tmp_path / "usr-src"), **estado},
        )
        assert feito.returncode == 0, feito.stderr
        lidas = chamadas.read_text(encoding="utf-8") if chamadas.exists() else ""
        return feito.stdout + feito.stderr, lidas

    def test_sem_a_chave_o_modulo_instalado_sai_de_cada_kernel_e_o_initramfs_se_refaz(
        self, tmp_path: Path
    ) -> None:
        """D-2011-SEM-A-CHAVE-NA-MOK-O-MODULO-DA-CASA-SAI."""
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False)
        saida, lidas = self._instalar(tmp_path, estado, self.STATUS)
        for kernel in ("7.1.5-generic", "7.0.1-generic", "6.9.0-generic"):
            assert f"dkms remove hefesto-teste/9.9.9 -k {kernel}" in lidas, lidas
            assert f"depmod -a {kernel}" in lidas, lidas
        assert "dkms uninstall" not in lidas, lidas
        for verbo in ("dkms add", "dkms build", "dkms install"):
            assert verbo not in lidas, lidas
        assert "STALE=1" in saida and "mokutil --import" in saida, saida
        assert "Wi-Fi USB" in saida and "driver de fábrica" in saida, saida

    def test_sem_nada_instalado_nao_tira_nada_e_diz_que_o_de_fabrica_continua(
        self, tmp_path: Path
    ) -> None:
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False)
        saida, lidas = self._instalar(tmp_path, estado, "")
        assert "dkms remove" not in lidas, lidas
        assert "STALE=0" in saida and "o driver de fábrica continua" in saida, saida

    @pytest.mark.parametrize(("ligado", "inscrita"), ESTADOS[1:], ids=ESTADOS_IDS[1:])
    def test_fora_desse_estado_o_modulo_instala_e_nada_sai(
        self, tmp_path: Path, ligado: bool | None, inscrita: bool
    ) -> None:
        estado = _estado_do_secure_boot(tmp_path, ligado=ligado, inscrita=inscrita)
        _saida, lidas = self._instalar(tmp_path, estado, self.STATUS)
        assert "-k 7.0.1-generic" not in lidas.replace("status", ""), lidas
        assert "sudo chown -R root:root" in lidas, lidas

    def test_o_atualizador_no_mesmo_estado_tira_o_modulo_em_vez_de_refazer(
        self, tmp_path: Path
    ) -> None:
        if os.geteuid() == 0:
            pytest.skip("o ajudante como root usa os caminhos de verdade")
        from tests.unit.test_o_ajudante_do_atualizador import Lar

        (tmp_path / "lar").mkdir()
        lar = Lar(tmp_path / "lar")
        pasta = lar.src / "hefesto-hid-playstation-1.0.0"
        pasta.mkdir()
        shutil.copy(PREPARADOR, pasta / "preparar-o-fonte.py")
        (pasta / "dkms.conf").write_text(
            'BUILT_MODULE_NAME[0]="hid-playstation"\n', encoding="utf-8")
        pasta.chmod(0o755)
        (pasta / "preparar-o-fonte.py").chmod(0o755)
        (pasta / "dkms.conf").chmod(0o644)
        (lar.modulos / "7.2.18-generic" / "build").mkdir(parents=True)
        lar.duble(
            "dkms",
            '[ "$1" = status ] && printf "%s\\n" "hefesto-hid-playstation/1.0.0, 7.2.18-generic, '
            'x86_64: installed" "hefesto-hid-playstation/1.0.0, 7.2.17-generic, x86_64: built"\n'
            'exit 0',
        )
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False)
        lar.duble("mokutil", "exit 1")
        feito = lar.rodar("dkms-refazer", **estado)
        assert feito.returncode == 0, feito.stderr
        lidas = lar.lidas()
        for kernel in ("7.2.18-generic", "7.2.17-generic"):
            assert f"dkms remove -m hefesto-hid-playstation -v 1.0.0 -k {kernel}" in lidas, lidas
        assert not [x for x in lidas if x.startswith(("dkms install", "dkms build"))], lidas
        assert any(x.startswith("update-initramfs") for x in lidas), lidas

    def test_o_exclusivo_dos_cinco_devolve_o_padrao_que_nenhum_kernel_casa(
        self, tmp_path: Path
    ) -> None:
        veredito = tmp_path / "dkms" / "pacote" / "1.0.0"
        veredito.mkdir(parents=True)
        for preparador in CINCO_PREPARADORES:
            for ligado, inscrita in ESTADOS:
                raiz = tmp_path / f"{preparador.parent.name}-{ligado}-{inscrita}"
                raiz.mkdir()
                estado = _estado_do_secure_boot(raiz, ligado=ligado, inscrita=inscrita)
                feito = subprocess.run(
                    ["python3", str(preparador), "--exclusivo", "7.1.5-generic",
                     str(tmp_path / "sem-fonte"), str(veredito)],
                    capture_output=True, text=True, check=False, timeout=60,
                    env={**os.environ, **estado, "PATH": _sem_mokutil(estado, os.environ["PATH"])},
                )
                esperado = "^/" if (ligado and not inscrita) else ""
                assert feito.stdout.strip() == esperado, (preparador, ligado, inscrita, feito)

    @pytest.mark.parametrize("leitura", ["completa", *SEM_LEITURA])
    @pytest.mark.parametrize(("ligado", "inscrita"), ESTADOS, ids=ESTADOS_IDS)
    def test_a_leitura_do_python_e_a_do_bash_dizem_o_mesmo(
        self, tmp_path: Path, ligado: bool | None, inscrita: bool, leitura: str
    ) -> None:
        """D-2111-A-CHAVE-QUE-NAO-SE-LE-NAO-TIRA-O-MODULO: os três estados, dos dois lados."""
        estado = _estado_do_secure_boot(
            tmp_path, ligado=ligado, inscrita=inscrita, leitura=leitura)
        ambiente = {**os.environ, **estado, "PATH": _sem_mokutil(estado, os.environ["PATH"])}

        def python(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["python3", str(PREPARADOR), *args], env=ambiente, capture_output=True,
                text=True, check=False, timeout=60,
            )

        estado_em_bash = _roda("dkms_estado_da_chave", _sem_mokutil(estado), estado).stdout
        assert estado_em_bash == python("--estado-da-chave").stdout, (ligado, inscrita, leitura)
        esperado = "inscrita" if (inscrita and leitura == "completa") else (
            "nao-sei" if leitura != "completa" else "fora")
        assert estado_em_bash == esperado, (ligado, inscrita, leitura, estado_em_bash)
        em_bash = _roda(
            "dkms_secure_boot_ligado && dkms_chave_mok_fora", _sem_mokutil(estado), estado
        ).returncode
        assert em_bash == python("--sem-a-chave").returncode, (ligado, inscrita, leitura)
        garantida = _roda(
            "dkms_sem_a_chave_garantida", _sem_mokutil(estado), estado).returncode
        assert garantida == python("--chave-nao-garantida").returncode, (ligado, inscrita, leitura)

    @pytest.mark.parametrize(
        ("os_release", "framework"),
        [
            ('ID=pop\nID_LIKE="ubuntu debian"\n', "# mok_signing_key=/x\n"),
            ("ID=ubuntu\nID_LIKE=debian\n", ""),
            ("ID=debian\n", ""),
            ("ID=fedora\n", 'mok_signing_key="/k.priv"\nmok_certificate="/k.der"\n'),
            ("ID=ubuntu\n", "mok_signing_key=/root/chave.priv\n"),
        ],
        ids=["pop", "ubuntu", "debian", "chave-propria", "ubuntu-so-a-chave"],
    )
    def test_o_python_acha_a_chave_onde_o_bash_acha(
        self, tmp_path: Path, os_release: str, framework: str
    ) -> None:
        (tmp_path / "os-release").write_text(os_release, encoding="utf-8")
        (tmp_path / "framework.conf").write_text(framework, encoding="utf-8")
        env = {
            "HEFESTO_OS_RELEASE": str(tmp_path / "os-release"),
            "HEFESTO_DKMS_FRAMEWORK_CONFS": str(tmp_path / "framework.conf"),
        }
        em_bash = _roda("_dkms_mok_pub", "/usr/bin:/bin", env).stdout
        roteiro = (
            "import importlib.util, sys\n"
            f"spec = importlib.util.spec_from_file_location('preparador', {str(PREPARADOR)!r})\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            "print(mod._chave_do_dkms(), end='')\n"
        )
        em_python = subprocess.run(
            ["python3", "-c", roteiro], env={**os.environ, **env}, capture_output=True, text=True,
            check=False, timeout=60,
        ).stdout
        assert em_bash == em_python


class TestChaveQueNaoSeLeNaoTiraOModulo:
    """O-SECURE-BOOT-SO-TIRA-O-MODULO-COM-A-CHAVE-FORA-DE-CERTEZA-01.

    D-2111-A-CHAVE-QUE-NAO-SE-LE-NAO-TIRA-O-MODULO: sem ler a chave nada se instala nem se tira.
    """

    instalar = TestSecureBootLigadoDevolveODriverDeFabrica._instalar
    STATUS = TestSecureBootLigadoDevolveODriverDeFabrica.STATUS

    def _modulo_carregado(
        self, tmp_path: Path, estado: dict[str, str], srcversion_carregado: str
    ) -> tuple[str, str]:
        from tests.unit.dkms_de_mentira import ko_do_dkms

        arvore = tmp_path / "arvore"
        ko_do_dkms(tmp_path / "ko", arvore, "hefesto-teste", "hid-teste.ko", kernel="7.1.5-generic")
        sysmod = tmp_path / "sysmod" / "hid_teste"
        sysmod.mkdir(parents=True)
        (sysmod / "srcversion").write_text(srcversion_carregado + "\n", encoding="utf-8")
        modinfo = (
            f'case "$*" in *filename*) echo "{tmp_path / "ko"}/lib/modules/7.1.5-generic/'
            'updates/dkms/hid-teste.ko";; *srcversion*) echo SRC123;; esac'
        )
        ambiente = {
            **estado, "HEFESTO_DKMS_TREE": str(arvore),
            "HEFESTO_SYS_MODULE": str(tmp_path / "sysmod"),
        }
        return self.instalar(tmp_path, ambiente, self.STATUS, modinfo)

    @pytest.mark.parametrize("leitura", SEM_LEITURA)
    def test_sem_ler_a_chave_nada_se_instala_nem_se_tira_e_o_resumo_diz_que_nao_leu(
        self, tmp_path: Path, leitura: str
    ) -> None:
        """D-2111-A-CHAVE-QUE-NAO-SE-LE-NAO-TIRA-O-MODULO."""
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False, leitura=leitura)
        saida, lidas = self.instalar(tmp_path, estado, self.STATUS)
        assert "dkms remove" not in lidas, lidas
        for verbo in ("dkms add", "dkms build", "dkms install", "dkms uninstall"):
            assert verbo not in lidas, lidas
        assert "STALE=0" in saida, saida
        assert "não consegui ler a chave do DKMS" in saida, saida
        assert "nem trocados" in saida and "Para ler a chave:" in saida, saida
        assert "saem e o driver de fábrica volta" not in saida, saida
        assert "instale o mokutil" not in saida, saida
        if leitura == "sem-lista":
            assert "mokutil --test-key" in saida and "mokutil --import" not in saida, saida
        else:
            assert "devolva o certificado da chave" in saida, saida
            assert "mokutil --import" not in saida, saida

    def test_o_modulo_da_casa_carregado_desmente_o_fora_e_nada_se_instala_nem_sai(
        self, tmp_path: Path
    ) -> None:
        """O carregado prova a chave que o assinou, não a que assina o próximo módulo."""
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False)
        saida, lidas = self._modulo_carregado(tmp_path, estado, "SRC123")
        assert "dkms remove" not in lidas, lidas
        for verbo in ("dkms add", "dkms build", "dkms install", "sudo chown"):
            assert verbo not in lidas, lidas
        assert "STALE=0" in saida, saida
        assert "não consegui ler a chave do DKMS" in saida, saida
        assert "mokutil --test-key" in saida and "mokutil --import" not in saida, saida
        assert "instale o mokutil" not in saida, saida

    def test_o_carregado_se_compara_com_o_arquivo_do_kernel_que_roda(self, tmp_path: Path) -> None:
        """O /sys/module é do kernel que roda: o arquivo do kernel alvo não prova nada dele."""
        from tests.unit.dkms_de_mentira import ko_do_dkms

        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False)
        arvore = tmp_path / "arvore"
        da_casa = ko_do_dkms(tmp_path / "ko", arvore, "hefesto-teste", "hid-teste.ko",
                             kernel="7.2.0-novo")
        de_fabrica = tmp_path / "fabrica" / "hid-teste.ko"
        de_fabrica.parent.mkdir()
        de_fabrica.write_bytes(b"o de fabrica")
        sysmod = tmp_path / "sysmod" / "hid_teste"
        sysmod.mkdir(parents=True)
        (sysmod / "srcversion").write_text("SRC123\n", encoding="utf-8")
        bin_ = tmp_path / "bin"
        bin_.mkdir()
        _stub(bin_, "modinfo", f'case "$*" in *srcversion*) echo SRC123;; '
                                f'*-k*) echo "{da_casa}";; *) echo "{de_fabrica}";; esac')
        caminho = _sem_mokutil(estado, f"{bin_}:/usr/bin:/bin")
        feito = _roda("dkms_estado_da_chave hid-teste", caminho,
                      {**estado, "HEFESTO_DKMS_KERNEL": "7.2.0-novo",
                       "HEFESTO_DKMS_TREE": str(arvore),
                       "HEFESTO_SYS_MODULE": str(tmp_path / "sysmod")})
        assert feito.stdout == "fora", feito

    def test_o_python_tambem_so_desmente_o_fora_com_o_carregado(self, tmp_path: Path) -> None:
        from tests.unit.dkms_de_mentira import ko_do_dkms

        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False)
        arvore = tmp_path / "arvore"
        ko = ko_do_dkms(tmp_path / "ko", arvore, "hefesto-hid-playstation",
                        "hid-playstation.ko", kernel="7.1.5-generic")
        sysmod = tmp_path / "sysmod" / "hid_playstation"
        sysmod.mkdir(parents=True)
        (sysmod / "srcversion").write_text("SRC123\n", encoding="utf-8")
        bin_ = tmp_path / "bin"
        bin_.mkdir()
        _stub(bin_, "modinfo", f'case "$*" in *filename*) echo "{ko}";; '
                                '*srcversion*) echo SRC123;; esac')
        _stub(bin_, "mokutil", "exit 1")
        ambiente = {**os.environ, **estado, "PATH": f"{bin_}:/usr/bin:/bin",
                    "HEFESTO_DKMS_TREE": str(arvore),
                    "HEFESTO_SYS_MODULE": str(tmp_path / "sysmod")}
        def python(arg: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(["python3", str(PREPARADOR), arg], env=ambiente,
                                  capture_output=True, text=True, check=False, timeout=60)

        assert python("--estado-da-chave").stdout == "nao-sei"
        assert python("--sem-a-chave").returncode == 1
        assert python("--chave-nao-garantida").returncode == 0
        com_a_chave = {**ambiente, "HEFESTO_MOK_LISTAS": str(tmp_path / "mok.pub")}
        feito = subprocess.run(["python3", str(PREPARADOR), "--estado-da-chave"],
                               env=com_a_chave, capture_output=True, text=True, check=False,
                               timeout=60)
        assert feito.stdout == "inscrita", feito

    def test_o_carregado_que_nao_e_o_da_casa_nao_prova_nada(self, tmp_path: Path) -> None:
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False)
        _saida, lidas = self._modulo_carregado(tmp_path, estado, "OUTRA999")
        assert "dkms remove hefesto-teste/9.9.9 -k 7.1.5-generic" in lidas, lidas

    @pytest.mark.parametrize("leitura", SEM_LEITURA)
    def test_o_exclusivo_dos_cinco_so_pula_a_construcao_no_nao_sei(
        self, tmp_path: Path, leitura: str
    ) -> None:
        veredito = tmp_path / "dkms" / "pacote" / "1.0.0"
        veredito.mkdir(parents=True)
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False, leitura=leitura)
        for preparador in CINCO_PREPARADORES:
            env = {**os.environ, **estado, "PATH": _sem_mokutil(estado, os.environ["PATH"])}
            feito = subprocess.run(
                ["python3", str(preparador), "--exclusivo", "7.1.5-generic",
                 str(tmp_path / "sem-fonte"), str(veredito)],
                capture_output=True, text=True, check=False, timeout=60, env=env,
            )
            assert feito.stdout.strip() == "^/", (preparador, feito)
            fora = subprocess.run(
                ["python3", str(preparador), "--sem-a-chave"], capture_output=True, check=False,
                timeout=60, env=env,
            )
            assert fora.returncode == 1, (preparador, fora)

    @pytest.mark.parametrize("leitura", SEM_LEITURA)
    def test_o_atualizador_no_nao_sei_nao_tira_nem_refaz(
        self, tmp_path: Path, leitura: str
    ) -> None:
        if os.geteuid() == 0:
            pytest.skip("o ajudante como root usa os caminhos de verdade")
        from tests.unit.test_o_ajudante_do_atualizador import Lar

        (tmp_path / "lar").mkdir()
        lar = Lar(tmp_path / "lar")
        pasta = lar.src / "hefesto-hid-playstation-1.0.0"
        pasta.mkdir()
        shutil.copy(PREPARADOR, pasta / "preparar-o-fonte.py")
        (pasta / "dkms.conf").write_text(
            'BUILT_MODULE_NAME[0]="hid-playstation"\n', encoding="utf-8")
        pasta.chmod(0o755)
        (pasta / "preparar-o-fonte.py").chmod(0o755)
        (pasta / "dkms.conf").chmod(0o644)
        (lar.modulos / "7.2.18-generic" / "build").mkdir(parents=True)
        lar.duble(
            "dkms",
            '[ "$1" = status ] && printf "%s\\n" "hefesto-hid-playstation/1.0.0, 7.2.18-generic, '
            'x86_64: installed"\nexit 0',
        )
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False, leitura=leitura)
        lar.duble("mokutil", "exit 1")
        feito = lar.rodar("dkms-refazer", **estado)
        assert feito.returncode == 0, feito.stderr
        lidas = lar.lidas()
        assert not [x for x in lidas if x.startswith(("dkms remove", "dkms install",
                                                      "dkms build", "update-initramfs"))], lidas
        assert "não li a chave do DKMS" in feito.stdout + feito.stderr

    @pytest.mark.parametrize(
        ("leitura", "frase"),
        [("completa", "não está inscrita"), ("sem-lista", "não consegui ler a chave do DKMS")],
    )
    def test_o_doctor_e_o_install_dizem_o_mesmo_estado(
        self, tmp_path: Path, leitura: str, frase: str
    ) -> None:
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False, leitura=leitura)
        dito = _roda("dkms_chave_e_o_passo; echo; dkms_titulo_da_chave", _sem_mokutil(estado),
                     estado)
        assert frase in dito.stdout, dito
        if leitura == "sem-lista":
            assert "Para ler a chave:" in dito.stdout, dito


MOK_NEW = "MokNew-605dab50-e046-4300-abb6-3dd810dd8b23"


def _com_a_inscricao_pedida(
    raiz: Path, *, ligado: bool | None = True, via: str = "efivar", inscrita: bool = False
) -> tuple[dict[str, str], str]:
    """A chave já pedida para a MOK: a variável do pedido a traz, ou o ``mokutil`` o diz."""
    estado = _estado_do_secure_boot(raiz, ligado=ligado, inscrita=inscrita)
    if via == "efivar":
        (Path(estado["HEFESTO_EFIVARS_ROOT"]) / MOK_NEW).write_bytes(b"\x07\x00\x00\x00" + CHAVE)
        return estado, _sem_mokutil(estado)
    pasta = raiz / "mokutil-do-pedido"
    pasta.mkdir()
    _stub(pasta, "mokutil", 'echo "/etc/dkms/mok.pub is already in the enrollment request"\nexit 1')
    return estado, f"{pasta}:/usr/bin:/bin"


class TestInscricaoPedidaEAindaNaoReiniciada:
    """A-INSCRICAO-PEDIDA-E-NAO-REINICIADA-NAO-TIRA-O-MODULO-01.

    D-2111-A-INSCRICAO-PEDIDA-ESPERA-O-REINICIO: a chave já pedida para a MOK espera o reinício e
    não tira nem instala módulo.
    """

    instalar = TestSecureBootLigadoDevolveODriverDeFabrica._instalar
    STATUS = TestSecureBootLigadoDevolveODriverDeFabrica.STATUS

    @pytest.mark.parametrize("ligado", [True, False], ids=["ligado", "desligado"])
    @pytest.mark.parametrize("via", ["efivar", "mokutil"])
    def test_a_leitura_do_python_e_a_do_bash_dizem_pedida(
        self, tmp_path: Path, via: str, ligado: bool
    ) -> None:
        """D-2111-A-INSCRICAO-PEDIDA-ESPERA-O-REINICIO: o quarto estado, dos dois lados."""
        estado, caminho = _com_a_inscricao_pedida(tmp_path, ligado=ligado, via=via)
        ambiente = {**os.environ, **estado, "PATH": caminho}

        def python(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["python3", str(PREPARADOR), *args], env=ambiente, capture_output=True,
                text=True, check=False, timeout=60,
            )

        assert _roda("dkms_estado_da_chave", caminho, estado).stdout == "pedida", via
        assert python("--estado-da-chave").stdout == "pedida", via
        assert python("--sem-a-chave").returncode == 1
        em_bash = _roda("dkms_secure_boot_ligado && dkms_chave_mok_fora", caminho, estado)
        assert em_bash.returncode != 0
        esperado = 0 if ligado else 1
        assert python("--chave-nao-garantida").returncode == esperado
        assert _roda("dkms_sem_a_chave_garantida", caminho, estado).returncode == esperado

    @pytest.mark.parametrize(("outras", "esperado"), [
        ([b"0\x82\x02\x10CHAVE-DO-DRIVER-DE-VIDEO"], "fora"),
        ([b"0\x82\x02\x10CHAVE-DO-DRIVER-DE-VIDEO", CHAVE], "pedida"),
    ], ids=["so-outra-chave-pedida", "outra-e-a-da-casa-pedidas"])
    def test_o_pedido_de_outra_chave_nao_e_o_da_casa(
        self, tmp_path: Path, outras: list[bytes], esperado: str
    ) -> None:
        """A variável do pedido guarda todas as chaves pedidas: só a da casa vale `pedida`."""
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False)
        corpo = b"".join(b"\xa1\x59\xc0\xa5" + b"\x00" * 24 + chave for chave in outras)
        (Path(estado["HEFESTO_EFIVARS_ROOT"]) / MOK_NEW).write_bytes(b"\x07\x00\x00\x00" + corpo)
        caminho = _sem_mokutil(estado)
        assert _roda("dkms_estado_da_chave", caminho, estado).stdout == esperado
        feito = subprocess.run(
            ["python3", str(PREPARADOR), "--estado-da-chave"],
            env={**os.environ, **estado, "PATH": caminho},
            capture_output=True, text=True, check=False, timeout=60,
        )
        assert feito.stdout == esperado, feito

    def test_a_chave_inscrita_vence_o_pedido(self, tmp_path: Path) -> None:
        estado, caminho = _com_a_inscricao_pedida(tmp_path, inscrita=True)
        ambiente = {**os.environ, **estado, "PATH": caminho}
        assert _roda("dkms_estado_da_chave", caminho, estado).stdout == "inscrita"
        feito = subprocess.run(
            ["python3", str(PREPARADOR), "--estado-da-chave"], env=ambiente,
            capture_output=True, text=True, check=False, timeout=60,
        )
        assert feito.stdout == "inscrita", feito

    def test_o_install_nao_tira_nem_instala_e_diz_para_reiniciar(self, tmp_path: Path) -> None:
        """D-2111-A-INSCRICAO-PEDIDA-ESPERA-O-REINICIO."""
        estado, _caminho = _com_a_inscricao_pedida(tmp_path)
        saida, lidas = self.instalar(tmp_path, estado, self.STATUS)
        assert "dkms remove" not in lidas, lidas
        for verbo in ("dkms add", "dkms build", "dkms install", "dkms uninstall"):
            assert verbo not in lidas, lidas
        assert "STALE=0" in saida, saida
        assert "espera o reinício" in saida and "Enroll MOK" in saida, saida
        assert "mokutil --import" not in saida, saida
        assert "saem e o driver de fábrica volta" not in saida, saida
        assert "não consegui ler a chave" not in saida, saida

    @pytest.mark.parametrize("via", ["efivar", "mokutil"])
    def test_o_exclusivo_dos_cinco_pula_a_construcao(self, tmp_path: Path, via: str) -> None:
        veredito = tmp_path / "dkms" / "pacote" / "1.0.0"
        veredito.mkdir(parents=True)
        estado, caminho = _com_a_inscricao_pedida(tmp_path, via=via)
        for preparador in CINCO_PREPARADORES:
            feito = subprocess.run(
                ["python3", str(preparador), "--exclusivo", "7.1.5-generic",
                 str(tmp_path / "sem-fonte"), str(veredito)],
                capture_output=True, text=True, check=False, timeout=60,
                env={**os.environ, **estado, "PATH": caminho},
            )
            assert feito.stdout.strip() == "^/", (preparador, feito)

    def test_o_atualizador_nao_tira_nem_refaz_e_diz_para_reiniciar(self, tmp_path: Path) -> None:
        if os.geteuid() == 0:
            pytest.skip("o ajudante como root usa os caminhos de verdade")
        from tests.unit.test_o_ajudante_do_atualizador import Lar

        (tmp_path / "lar").mkdir()
        lar = Lar(tmp_path / "lar")
        pasta = lar.src / "hefesto-hid-playstation-1.0.0"
        pasta.mkdir()
        shutil.copy(PREPARADOR, pasta / "preparar-o-fonte.py")
        (pasta / "dkms.conf").write_text(
            'BUILT_MODULE_NAME[0]="hid-playstation"\n', encoding="utf-8")
        pasta.chmod(0o755)
        (pasta / "preparar-o-fonte.py").chmod(0o755)
        (pasta / "dkms.conf").chmod(0o644)
        (lar.modulos / "7.2.18-generic" / "build").mkdir(parents=True)
        lar.duble(
            "dkms",
            '[ "$1" = status ] && printf "%s\\n" "hefesto-hid-playstation/1.0.0, 7.2.18-generic, '
            'x86_64: installed"\nexit 0',
        )
        estado, _caminho = _com_a_inscricao_pedida(tmp_path)
        lar.duble("mokutil", "exit 1")
        feito = lar.rodar("dkms-refazer", **estado)
        assert feito.returncode == 0, feito.stderr
        lidas = lar.lidas()
        assert not [x for x in lidas if x.startswith(("dkms remove", "dkms install",
                                                      "dkms build", "update-initramfs"))], lidas
        saida = feito.stdout + feito.stderr
        assert "espera o reinício" in saida and "não li a chave do DKMS" not in saida, saida

    def test_o_texto_do_install_e_o_do_doctor_dizem_o_mesmo_estado(self, tmp_path: Path) -> None:
        estado, caminho = _com_a_inscricao_pedida(tmp_path)
        dito = _roda("dkms_chave_e_o_passo; echo; dkms_titulo_da_chave", caminho, estado)
        assert "espera o reinício" in dito.stdout and "Enroll MOK" in dito.stdout, dito
        assert "mokutil --import" not in dito.stdout, dito


MARCA_DE_ASSINATURA = b"~Module signature appended~\n"
KERNEL_DO_TESTE = "7.1.5-generic"
CONFIG_QUE_ASSINA = 'CONFIG_MODULE_SIG=y\nCONFIG_MODULE_SIG_HASH="sha512"\n'
CONFIG_QUE_NAO_ASSINA = "# CONFIG_MODULE_SIG is not set\nCONFIG_MODULES=y\n"


def _escreve_o_ko(destino: Path, nome: str, *, assinado: bool) -> None:
    dados = b"ELF-de-mentira" + b"\x00" * 12 + (MARCA_DE_ASSINATURA if assinado else b"")
    if nome.endswith(".xz"):
        dados = lzma.compress(dados)
    elif nome.endswith(".gz"):
        dados = gzip.compress(dados)
    elif nome.endswith(".zst"):
        zstd = shutil.which("zstd")
        if not zstd:
            pytest.skip("sem zstd nesta máquina")
        dados = subprocess.run(
            [zstd, "-c"], input=dados, capture_output=True, check=True, timeout=60
        ).stdout
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(dados)


class TestModuloSemAssinaturaComAChaveInscrita:
    """O-MODULO-DA-CASA-SEM-ASSINATURA-SE-RECONSTROI-COM-A-CHAVE-INSCRITA-01.

    D-2111-O-MODULO-SEM-ASSINATURA-SE-REFAZ-COM-A-CHAVE-INSCRITA: com a chave inscrita de certeza e
    o módulo da casa instalado sem a assinatura, o install o refaz; em qualquer outro estado, não.
    """

    def _instalar(
        self, tmp_path: Path, estado: dict[str, str], *, arquivo: str = "hid-teste.ko",
        assinado: bool = False, corrompido: bool = False, chave_privada: bool = True,
        dubles: dict[str, str] | None = None, ambiente: dict[str, str] | None = None,
        config: str | None = CONFIG_QUE_ASSINA,
    ) -> str:
        bin_ = tmp_path / "bin"
        bin_.mkdir()
        chamadas = tmp_path / "chamadas.log"
        arvore = tmp_path / "arvore"
        privada = tmp_path / "mok.key"
        if chave_privada:
            privada.write_bytes(b"CHAVE-PRIVADA-DE-MENTIRA")
        framework = tmp_path / "framework.conf"
        framework.write_text(f'mok_signing_key="{privada}"\n', encoding="utf-8")
        ko = tmp_path / "lib" / "modules" / KERNEL_DO_TESTE / "updates" / "dkms" / arquivo
        guardado = (arvore / "hefesto-teste" / "1.0.0" / KERNEL_DO_TESTE / "x86_64" / "module"
                    / arquivo)
        _escreve_o_ko(ko, arquivo, assinado=assinado)
        if corrompido:
            ko.write_bytes("isto não é um arquivo comprimido".encode())
        guardado.parent.mkdir(parents=True)
        shutil.copy(ko, guardado)
        (arvore / "hefesto-teste" / f"kernel-{KERNEL_DO_TESTE}-x86_64").symlink_to(
            f"1.0.0/{KERNEL_DO_TESTE}/x86_64")
        _stub(bin_, "modinfo", f'echo "{ko}"')
        _stub(bin_, "uname", f'echo "{KERNEL_DO_TESTE}"')
        _stub(bin_, "mokutil", "exit 1")
        for nome in ("chown", "chmod", "depmod"):
            _stub(bin_, nome, f'echo "{nome} $*" >> "{chamadas}"')
        _stub(bin_, "sudo", f'echo "sudo $*" >> "{chamadas}"\nexec "$@"')
        _stub(
            bin_, "dkms",
            f'echo "dkms $*" >> "{chamadas}"\n'
            '[ "$1" = status ] && echo '
            f'"hefesto-teste/9.9.9, {KERNEL_DO_TESTE}, x86_64: installed"\n'
            "exit 0",
        )
        for nome, corpo in (dubles or {}).items():
            _stub(bin_, nome, corpo)
        modulos = tmp_path / "modules"
        (modulos / KERNEL_DO_TESTE / "build").mkdir(parents=True)
        if config is not None:
            (modulos / KERNEL_DO_TESTE / "build" / ".config").write_text(config, encoding="utf-8")
        fonte = tmp_path / "fonte"
        sincronizado = tmp_path / "usr-src" / "hefesto-teste-9.9.9"
        for pasta in (fonte, sincronizado):
            pasta.mkdir(parents=True)
            (pasta / "dkms.conf").write_text('PACKAGE_VERSION="9.9.9"\n', encoding="utf-8")
        feito = _roda(
            f"dkms_install_patched_module hefesto-teste 9.9.9 '{fonte}' hid-teste",
            f"{bin_}:/usr/bin:/bin",
            {"HEFESTO_DKMS_SRC_ROOT": str(tmp_path / "usr-src"),
             "HEFESTO_DKMS_MODULES_ROOT": str(modulos), "HEFESTO_DKMS_TREE": str(arvore),
             "HEFESTO_DKMS_BOOT_ROOT": str(tmp_path / "boot-de-mentira"),
             "HEFESTO_DKMS_KERNEL": KERNEL_DO_TESTE, **estado,
             "HEFESTO_DKMS_FRAMEWORK_CONFS": str(framework), **(ambiente or {})},
        )
        assert feito.returncode == 0, feito.stderr
        self.dito = feito.stdout + feito.stderr
        return chamadas.read_text(encoding="utf-8") if chamadas.exists() else ""

    @pytest.mark.parametrize("arquivo", ["hid-teste.ko", "hid-teste.ko.xz", "hid-teste.ko.gz",
                                         "hid-teste.ko.zst"])
    def test_sem_a_marca_e_com_a_chave_inscrita_o_modulo_se_refaz(
        self, tmp_path: Path, arquivo: str
    ) -> None:
        """D-2111-O-MODULO-SEM-ASSINATURA-SE-REFAZ-COM-A-CHAVE-INSCRITA."""
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=True)
        lidas = self._instalar(tmp_path, estado, arquivo=arquivo)
        assert f"dkms build hefesto-teste/9.9.9 -k {KERNEL_DO_TESTE} --force" in lidas, lidas
        assert f"dkms install hefesto-teste/9.9.9 -k {KERNEL_DO_TESTE} --force" in lidas, lidas

    @pytest.mark.parametrize("arquivo", ["hid-teste.ko", "hid-teste.ko.xz", "hid-teste.ko.gz",
                                         "hid-teste.ko.zst"])
    def test_com_a_marca_o_modulo_assinado_fica_como_esta(
        self, tmp_path: Path, arquivo: str
    ) -> None:
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=True)
        lidas = self._instalar(tmp_path, estado, arquivo=arquivo, assinado=True)
        assert "dkms build" not in lidas and "dkms install" not in lidas, lidas

    @pytest.mark.parametrize(
        ("ligado", "inscrita", "leitura"),
        [(False, True, "completa"), (True, False, "sem-lista"), (True, False, "sem-chave-publica")],
        ids=["secure-boot-desligado", "chave-nao-lida-nas-listas", "chave-publica-ausente"],
    )
    def test_fora_da_chave_inscrita_de_certeza_o_modulo_sem_marca_nao_se_refaz(
        self, tmp_path: Path, ligado: bool, inscrita: bool, leitura: str
    ) -> None:
        estado = _estado_do_secure_boot(
            tmp_path, ligado=ligado, inscrita=inscrita, leitura=leitura)
        lidas = self._instalar(tmp_path, estado)
        assert "dkms build" not in lidas and "dkms install" not in lidas, lidas

    def test_a_chave_pedida_e_nao_reiniciada_nao_refaz_o_modulo_sem_marca(
        self, tmp_path: Path
    ) -> None:
        estado, _caminho = _com_a_inscricao_pedida(tmp_path)
        lidas = self._instalar(tmp_path, estado)
        assert "dkms build" not in lidas and "dkms install" not in lidas, lidas

    @pytest.mark.parametrize("arquivo", ["hid-teste.ko.xz", "hid-teste.ko.gz"])
    def test_o_arquivo_que_nao_se_le_nao_se_refaz(self, tmp_path: Path, arquivo: str) -> None:
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=True)
        lidas = self._instalar(tmp_path, estado, arquivo=arquivo, corrompido=True)
        assert "dkms build" not in lidas and "dkms install" not in lidas, lidas

    @pytest.mark.parametrize(("arquivo", "biblioteca"), [("hid-teste.ko.xz", "lzma"),
                                                         ("hid-teste.ko.gz", "gzip")])
    def test_sem_o_descompressor_do_python_nao_se_refaz(
        self, tmp_path: Path, arquivo: str, biblioteca: str
    ) -> None:
        """O Python sem o módulo que descomprime não sabe ler a marca: nada se refaz."""
        falsos = tmp_path / "python-sem-descompressor"
        falsos.mkdir()
        (falsos / f"{biblioteca}.py").write_text(
            "raise ImportError('módulo ausente nesta máquina')\n", encoding="utf-8")
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=True)
        lidas = self._instalar(tmp_path, estado, arquivo=arquivo,
                               ambiente={"PYTHONPATH": str(falsos)})
        assert "dkms build" not in lidas and "dkms install" not in lidas, lidas

    def test_sem_o_zstd_o_modulo_zst_nao_se_refaz(self, tmp_path: Path) -> None:
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=True)
        lidas = self._instalar(tmp_path, estado, arquivo="hid-teste.ko.zst",
                               dubles={"zstd": "exit 1"})
        assert "dkms build" not in lidas and "dkms install" not in lidas, lidas
        so_python = tmp_path / "so-python"
        so_python.mkdir()
        python = shutil.which("python3")
        assert python
        (so_python / "python3").symlink_to(python)
        ko = (tmp_path / "lib" / "modules" / KERNEL_DO_TESTE / "updates" / "dkms"
              / "hid-teste.ko.zst")
        feito = _roda(f"_dkms_marca_de_assinatura '{ko}'", str(so_python))
        assert feito.returncode == 2, feito

    def test_sem_a_chave_privada_nao_se_refaz_e_diz_por_que(self, tmp_path: Path) -> None:
        """D-2111-O-MODULO-SEM-ASSINATURA-SE-REFAZ-COM-A-CHAVE-INSCRITA: sem a chave privada o
        DKMS não assina, e refazer daria o mesmo módulo sem marca a cada install."""
        estado = _estado_do_secure_boot(
            tmp_path, ligado=True, inscrita=True, chave_privada=False)
        lidas = self._instalar(tmp_path, estado, chave_privada=False)
        assert "dkms build" not in lidas and "dkms install" not in lidas, lidas
        assert "falta a chave privada do DKMS" in self.dito, self.dito
        assert str(tmp_path / "mok.key") in self.dito, self.dito

    def test_a_chave_privada_que_so_o_root_le_se_confere_pelo_sudo(self, tmp_path: Path) -> None:
        if os.geteuid() == 0:
            pytest.skip("o root lê qualquer arquivo")
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=True)
        cofre = tmp_path / "cofre"
        cofre.mkdir()
        (cofre / "mok.key").write_bytes(b"CHAVE-PRIVADA-DE-MENTIRA")
        (tmp_path / "framework-do-cofre.conf").write_text(
            f'mok_signing_key="{cofre / "mok.key"}"\n', encoding="utf-8")
        cofre.chmod(0)
        chamadas = tmp_path / "chamadas.log"
        root = (
            f'echo "sudo $*" >> "{chamadas}"\n[ "$1" = -n ] && shift\n'
            f'/bin/chmod 700 "{cofre}"\n"$@"\nrc=$?\n/bin/chmod 000 "{cofre}"\nexit $rc'
        )
        try:
            lidas = self._instalar(
                tmp_path, estado, chave_privada=False, dubles={"sudo": root},
                ambiente={
                    "HEFESTO_DKMS_FRAMEWORK_CONFS": str(tmp_path / "framework-do-cofre.conf")})
        finally:
            cofre.chmod(0o700)
        assert "sudo -n sh -c" in lidas and str(cofre / "mok.key") in lidas, lidas
        assert f"dkms build hefesto-teste/9.9.9 -k {KERNEL_DO_TESTE} --force" in lidas, lidas


class TestAvisoDaChaveNomeiaOModuloELeUmaVez:
    """O-AVISO-DA-CHAVE-DIZ-O-MODULO-E-A-LEITURA-SE-FAZ-UMA-VEZ-01.

    D-2111-O-AVISO-DA-CHAVE-NOMEIA-O-MODULO-E-LE-UMA-VEZ: o aviso diz o que acontece com o módulo
    da casa carregado agora, e a chave se lê uma vez por execução, com os textos recebendo o estado.
    """

    instalar = TestSecureBootLigadoDevolveODriverDeFabrica._instalar
    STATUS = TestSecureBootLigadoDevolveODriverDeFabrica.STATUS
    _modulo_carregado = TestChaveQueNaoSeLeNaoTiraOModulo._modulo_carregado

    def test_o_aviso_do_install_diz_que_o_modulo_carregado_segue_como_esta(
        self, tmp_path: Path
    ) -> None:
        """D-2111-O-AVISO-DA-CHAVE-NOMEIA-O-MODULO-E-LE-UMA-VEZ."""
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False)
        saida, lidas = self._modulo_carregado(tmp_path, estado, "SRC123")
        assert "dkms remove" not in lidas, lidas
        assert "O módulo hid-teste do Hefesto carregado agora segue como está." in saida, saida
        assert "saem e o driver de fábrica volta" not in saida, saida

    def test_sem_modulo_carregado_o_aviso_nao_fala_de_carregado(self, tmp_path: Path) -> None:
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False)
        saida, _lidas = self.instalar(tmp_path, estado, self.STATUS)
        assert "carregado agora" not in saida, saida
        assert "saem e o driver de fábrica volta" in saida, saida

    @pytest.mark.parametrize("nome", ["hid-a", "hid-b", ""])
    def test_a_chave_se_le_uma_vez_e_os_textos_recebem_o_estado(
        self, tmp_path: Path, nome: str
    ) -> None:
        """D-2111-O-AVISO-DA-CHAVE-NOMEIA-O-MODULO-E-LE-UMA-VEZ: um `mokutil` por execução."""
        estado = _estado_do_secure_boot(tmp_path, ligado=True, inscrita=False)
        pasta = tmp_path / "mokutil-contado"
        pasta.mkdir()
        contador = tmp_path / "mokutil.log"
        _stub(pasta, "mokutil", f'echo x >> "{contador}"\necho "chave is not enrolled"\nexit 1')
        feito = _roda(
            f"dkms_warn_secureboot_once hid-a\ndkms_ler_a_chave '{nome}'\n"
            f"dkms_titulo_da_chave '{nome}'; dkms_modulos_sem_a_chave '{nome}'\n"
            f"dkms_efeito_do_estado '{nome}'; dkms_passo_da_chave '{nome}'\n"
            f"dkms_chave_e_o_passo '{nome}'",
            f"{pasta}:/usr/bin:/bin", estado,
        )
        assert "não está inscrita" in feito.stdout + feito.stderr, feito
        assert len(contador.read_text(encoding="utf-8").split()) == 1, feito

    def test_os_cinco_pontos_do_aviso_dizem_o_modulo_que_se_instala_logo_depois(self) -> None:
        texto = (REPO_ROOT / "scripts" / "lib" / "camada_de_maquina.sh").read_text(
            encoding="utf-8")
        pontos = re.findall(
            r"dkms_warn_secureboot_once([^\n]*)\n    local \w+=\"[^\"]*\"\n"
            r"    dkms_install_patched_module [^\n]*\n\s+\"[^\n]*\" (\S+)\n", texto)
        assert len(pontos) == 5, pontos
        for dito, instalado in pontos:
            assert dito.strip() == instalado, (dito, instalado)
        assert not re.search(r"dkms_warn_secureboot_once\s*\n", texto)
        install = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
        assert 'dkms_titulo_da_chave "${DKMS_MODULO}"' in install
        assert "dkms_chave_mok_inscrita" not in install


class TestCertificadoQueFaltaNaoMandaGerarChaveNova:
    """O-CERTIFICADO-QUE-FALTA-NAO-MANDA-GERAR-CHAVE-NOVA-01.

    D-2611-O-CERTIFICADO-QUE-FALTA-NAO-MANDA-GERAR-CHAVE-NOVA: com a chave privada do DKMS presente
    e o certificado ausente, nenhum passo do install manda gerar chave; só com as duas ausentes o
    passo manda gerar e inscrever.
    """

    PASSOS = (
        "dkms_passo_da_mok", "dkms_passo_para_ler_a_chave", "dkms_chave_e_o_passo",
        "dkms_passo_da_chave",
    )

    def _passo(self, tmp_path: Path, função: str, *, privada: bool) -> str:
        estado = _estado_do_secure_boot(
            tmp_path, ligado=True, inscrita=False, leitura="sem-chave-publica",
            chave_privada=privada)
        feito = _roda(f"{função} ''", _sem_mokutil(estado), estado)
        assert feito.returncode == 0, feito
        return feito.stdout

    @pytest.mark.parametrize("função", PASSOS)
    def test_com_a_privada_e_sem_o_certificado_o_passo_nomeia_o_certificado(
        self, tmp_path: Path, função: str
    ) -> None:
        """D-2611-O-CERTIFICADO-QUE-FALTA-NAO-MANDA-GERAR-CHAVE-NOVA."""
        saida = self._passo(tmp_path, função, privada=True)
        assert "devolva o certificado da chave" in saida, saida
        assert str(tmp_path / "sem-chave.pub") in saida, saida
        assert "generate_mok" not in saida and "--new-key" not in saida, saida
        assert "mokutil --import" not in saida, saida

    @pytest.mark.parametrize("função", ["dkms_passo_da_mok", "dkms_chave_e_o_passo"])
    def test_sem_a_privada_e_sem_o_certificado_o_passo_manda_gerar_e_inscrever(
        self, tmp_path: Path, função: str
    ) -> None:
        """D-2611-O-CERTIFICADO-QUE-FALTA-NAO-MANDA-GERAR-CHAVE-NOVA."""
        saida = self._passo(tmp_path, função, privada=False)
        assert "sudo dkms generate_mok" in saida, saida
        assert "devolva o certificado" not in saida, saida

    def test_a_privada_que_so_o_root_ve_tambem_nao_manda_gerar(self, tmp_path: Path) -> None:
        """D-2611-O-CERTIFICADO-QUE-FALTA-NAO-MANDA-GERAR-CHAVE-NOVA: «não sei» não é «falta»."""
        if os.geteuid() == 0:
            pytest.skip("o root lê a pasta trancada")
        estado = _estado_do_secure_boot(
            tmp_path, ligado=True, inscrita=False, leitura="sem-chave-publica")
        trancada = tmp_path / "trancada"
        trancada.mkdir()
        (trancada / "mok.key").write_bytes(b"CHAVE-PRIVADA-DE-MENTIRA")
        (tmp_path / "framework-da-chave.conf").write_text(
            f'mok_signing_key="{trancada / "mok.key"}"\n', encoding="utf-8")
        sudo = tmp_path / "sudo-que-nao-sabe"
        sudo.mkdir()
        _stub(sudo, "sudo", "exit 1")
        trancada.chmod(0o000)
        try:
            feito = _roda("dkms_passo_da_mok", f"{sudo}:{_sem_mokutil(estado)}", estado)
        finally:
            trancada.chmod(0o755)
        assert "devolva o certificado da chave" in feito.stdout, feito
        assert "generate_mok" not in feito.stdout, feito
        assert "existe," not in feito.stdout, feito
        assert "só o root abre" in feito.stdout, feito

    def test_o_certificado_que_so_o_root_ve_nao_se_da_por_perdido(self, tmp_path: Path) -> None:
        """D-2611-O-CERTIFICADO-QUE-FALTA-NAO-MANDA-GERAR-CHAVE-NOVA: o certificado numa pasta que
        só o root abre é «não sei», e o passo pede para deixá-lo legível, sem mandar devolver o
        que pode estar lá nem gerar chave."""
        if os.geteuid() == 0:
            pytest.skip("o root lê a pasta trancada")
        estado = _estado_do_secure_boot(
            tmp_path, ligado=True, inscrita=False, leitura="sem-chave-publica")
        trancada = tmp_path / "trancada"
        trancada.mkdir()
        (trancada / "mok.pub").write_bytes(CHAVE)
        estado["HEFESTO_DKMS_MOK_PUB"] = str(trancada / "mok.pub")
        sudo = tmp_path / "sudo-que-nao-sabe"
        sudo.mkdir()
        _stub(sudo, "sudo", "exit 1")
        trancada.chmod(0o000)
        try:
            saidas = {
                f: _roda(f"{f} ''", f"{sudo}:{_sem_mokutil(estado)}", estado).stdout
                for f in self.PASSOS
            }
        finally:
            trancada.chmod(0o755)
        for função, saida in saidas.items():
            assert f"deixe a chave {trancada / 'mok.pub'} legível" in saida, (função, saida)
            assert "devolva o certificado" not in saida, (função, saida)
            assert "generate_mok" not in saida and "--new-key" not in saida, (função, saida)


def test_os_cinco_preparadores_sao_o_mesmo_arquivo() -> None:
    assert len(CINCO_PREPARADORES) == 5
    assert len({p.read_bytes() for p in CINCO_PREPARADORES}) == 1
