"""Onda T — scripts/dkms_lib.sh (infra DKMS genérica, reusada pela Onda W).

Desenho: docs/process/estudos/2026-07-20-desenho-onda-t-patch-dkms.md §infra.

Contrato inviolável da lib, testado em dois níveis (falha-sem/passa-com):

1. Comportamental REAL (bash de verdade, PATH de stubs, SEM root, SEM tocar
   no kernel): os caminhos de fail-safe retornam 0 com aviso honesto e NUNCA
   escalam (o stub de sudo registra qualquer invocação — a ausência do log é
   a prova); a remoção pede `dkms remove --all` + limpa /usr/src via sudo.

2. Contrato de texto: `bash -n` limpo; PROIBIDO modprobe/rmmod/insmod (a
   ativação é do chamador — recarregar módulo derrubaria Pro/8BitDo em uso);
   idempotência via `diff -rq -x patch`; validação por `modinfo -F filename`
   em updates/dkms (NUNCA srcversion — armadilha documentada no estudo).

3. Execução de PONTA A PONTA (achado #4 do corretor): os dois contratos
   centrais — 2ª chamada é no-op limpo e build falho cai em fail-safe sem
   tentar install — provados por EXECUÇÃO com um dkms stub COM ESTADO e as
   raízes parametrizadas (HEFESTO_DKMS_SRC_ROOT/HEFESTO_DKMS_MODULES_ROOT,
   costura de teste da lib) apontando p/ tmp — sem root, sem tocar no
   sistema. Também: remoção com `dkms remove` falho preserva registro e
   source sem anunciar sucesso (achado #8) e a função de remoção sobrevive
   a `set -euo pipefail` do uninstall com `rm -rf` falhando (achado #7).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_PATH = REPO_ROOT / "scripts" / "dkms_lib.sh"
LIB = LIB_PATH.read_text(encoding="utf-8") if LIB_PATH.exists() else ""


def _sem_comentarios(texto: str) -> str:
    """Remove comentários de linha (# no início ou precedido de espaço) —
    suficiente para a lib, que não usa '#' dentro de strings."""
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
        # Ativação é do CHAMADOR e a mensagem é "vale no próximo boot" —
        # recarregar módulo com Pro/8BitDo conectados os derrubaria.
        codigo = _sem_comentarios(LIB)
        assert not re.search(r"\b(modprobe|rmmod|insmod)\b", codigo), (
            "dkms_lib.sh NUNCA pode carregar/descarregar módulo"
        )

    def test_api_completa_das_quatro_funcoes(self) -> None:
        for funcao in (
            "dkms_install_patched_module",
            "dkms_remove_patched_module",
            "dkms_module_from_updates",
            "dkms_module_loaded",
        ):
            assert re.search(rf"^{funcao}\(\) \{{", LIB, re.MULTILINE), (
                f"função {funcao} ausente da API"
            )

    def test_idempotencia_resincroniza_so_se_mudou_e_exclui_patch(self) -> None:
        assert "diff -rq -x patch" in LIB, (
            "re-sincronizar /usr/src só quando os assets mudaram (idempotente)"
        )
        assert 'rm -rf "${_srcdst}/patch"' in LIB, (
            "patch/ é referência de rebase/upstream — não entra no build"
        )

    def test_build_e_install_tolerantes_a_reexecucao(self) -> None:
        assert re.search(r"grep -qE 'built\|installed'", LIB), (
            "dkms build só roda se ainda não construído (idempotente)"
        )
        assert re.search(r"grep -q 'installed'", LIB), (
            "dkms install só roda se ainda não instalado (idempotente)"
        )

    def test_validacao_por_caminho_updates_nunca_srcversion(self) -> None:
        assert "modinfo -F filename" in LIB
        assert "*/updates/dkms/*" in LIB
        assert "srcversion" not in LIB, (
            "srcversion não distingue in-tree de DKMS (armadilha do estudo)"
        )

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
        # sudo de mentira: registra e NÃO executa (nada é tocado de verdade).
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
        # sudo executa SÓ dkms (resolvido no stub abaixo); o resto é engolido.
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
    def test_module_from_updates_reconhece_o_caminho_dkms(self, tmp_path: Path) -> None:
        stubs = tmp_path / "bin"
        stubs.mkdir()
        _stub(
            stubs,
            "modinfo",
            'echo "/lib/modules/x/updates/dkms/hid-nintendo.ko"',
        )
        resultado = _roda(
            'dkms_module_from_updates hid_nintendo; printf "RC=%s\\n" "$?"',
            path=str(stubs),
        )
        assert "RC=0" in resultado.stdout, resultado.stderr

    def test_module_from_updates_rejeita_o_in_tree(self, tmp_path: Path) -> None:
        stubs = tmp_path / "bin"
        stubs.mkdir()
        _stub(
            stubs,
            "modinfo",
            'echo "/lib/modules/x/kernel/drivers/hid/hid-nintendo.ko.zst"',
        )
        resultado = _roda(
            'dkms_module_from_updates hid_nintendo; printf "RC=%s\\n" "$?"',
            path=str(stubs),
        )
        assert "RC=1" in resultado.stdout, resultado.stderr

    def test_module_from_updates_falha_se_modinfo_falha(self, tmp_path: Path) -> None:
        stubs = tmp_path / "bin"
        stubs.mkdir()
        _stub(stubs, "modinfo", "exit 1")
        resultado = _roda(
            'dkms_module_from_updates hid_nintendo; printf "RC=%s\\n" "$?"',
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
        # /sys/module usa underscore (hid_nintendo), o pacote usa hífen.
        assert "${1//-/_}" in LIB


def _prepara_e2e(tmp_path: Path, build_falha: bool = False) -> dict[str, Path | str]:
    """Ambiente de execução real da lib SEM root: raízes em tmp (costura
    HEFESTO_DKMS_*), sudo que EXECUTA (paths todos em tmp), dkms stub com
    ESTADO em arquivos (added/built/installed) e modinfo resolvendo p/
    updates/dkms."""
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
    # sudo registra e EXECUTA — todos os caminhos apontam p/ tmp_path.
    _stub(stubs, "sudo", f'echo "sudo $@" >> "{log}"\nexec "$@"')
    _stub(stubs, "modinfo", 'echo "/lib/modules/x/updates/dkms/hid-teste.ko"')
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
        f'  install) touch "{estado}/installed" ;;\n'
        f'  remove) rm -f "{estado}/added" "{estado}/built" "{estado}/installed" ;;\n'
        "esac\nexit 0",
    )
    return {
        "path": f"{stubs}:/usr/bin:/bin",
        "log": log,
        "src_root": src_root,
        "assets": assets,
    }


def _roda_e2e(tmp_path: Path, script: str, build_falha: bool = False) -> tuple[
    subprocess.CompletedProcess[str], str, Path
]:
    cena = _prepara_e2e(tmp_path, build_falha=build_falha)
    resultado = _roda(
        script,
        path=str(cena["path"]),
        env_extra={
            "HEFESTO_DKMS_SRC_ROOT": str(cena["src_root"]),
            "HEFESTO_DKMS_MODULES_ROOT": str(tmp_path / "modules"),
        },
    )
    log = Path(str(cena["log"]))
    registro = log.read_text(encoding="utf-8") if log.exists() else ""
    return resultado, registro, Path(str(cena["src_root"]))


class TestExecucaoDePontaAPonta:
    """Achado #4 do corretor: os contratos "2º install = no-op" e "build
    falho = fail-safe REAL" só existiam em prosa/regex — agora são provados
    por execução (uma regressão em qualquer passo da sequência vira teste
    vermelho, não bug ao vivo na máquina da mantenedora)."""

    SCRIPT_DUAS_CHAMADAS = (
        "dkms_install_patched_module hefesto-teste 9.9.9 {assets} hid-teste\n"
        'printf "RC1=%s\\n" "$?"\n'
        "dkms_install_patched_module hefesto-teste 9.9.9 {assets} hid-teste\n"
        'printf "RC2=%s\\n" "$?"\n'
    )

    def test_primeira_chamada_faz_add_build_install_e_valida(self, tmp_path: Path) -> None:
        script = (
            "dkms_install_patched_module hefesto-teste 9.9.9 "
            f"{tmp_path / 'assets-dkms'} hid-teste\n"
            'printf "RC=%s\\n" "$?"\n'
        )
        resultado, registro, src_root = _roda_e2e(tmp_path, script)
        assert "RC=0" in resultado.stdout, resultado.stderr
        # Conta SÓ as invocações via sudo (o stub de dkms também loga a
        # própria linha — contar "dkms add" pegaria as duas).
        assert registro.count("sudo dkms add hefesto-teste/9.9.9") == 1
        assert registro.count("sudo dkms build hefesto-teste/9.9.9") == 1
        assert registro.count("sudo dkms install hefesto-teste/9.9.9") == 1
        assert "ok: modinfo resolve" in resultado.stdout
        destino = src_root / "hefesto-teste-9.9.9"
        assert (destino / "hid-teste.c").exists(), "source sincronizado no *_SRC_ROOT"
        assert not (destino / "patch").exists(), "patch/ não entra no build"

    def test_segunda_chamada_e_no_op_real(self, tmp_path: Path) -> None:
        script = self.SCRIPT_DUAS_CHAMADAS.format(assets=tmp_path / "assets-dkms")
        resultado, registro, _ = _roda_e2e(tmp_path, script)
        assert "RC1=0" in resultado.stdout and "RC2=0" in resultado.stdout, resultado.stderr
        assert "já sincronizado" in resultado.stdout, (
            "a 2ª chamada precisa reconhecer o source já em dia (diff -rq)"
        )
        # NENHUM passo repetido: 1 remove (da 1ª sincronização), 1 cp -a,
        # 1 add, 1 build, 1 install — a 2ª chamada não re-registra nada.
        assert registro.count("sudo dkms remove") == 1
        assert registro.count("sudo cp -a") == 1
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
    """Achados #7 e #8 do corretor: a remoção era o único caminho com
    comando perigoso sem guarda (set -e do uninstall matava o script) e
    anunciava sucesso mesmo com `dkms remove` falho (registro órfão)."""

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
        # uninstall.sh roda com set -euo pipefail e faz source da lib:
        # um rm -rf falho (fs read-only, sudoers restrito, chattr +i)
        # NÃO pode matar o uninstall inteiro no meio (achado #7).
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
