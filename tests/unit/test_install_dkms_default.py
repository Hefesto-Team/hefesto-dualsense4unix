"""Onda T — DKMS por DEFAULT no install.sh + uninstall simétrico.

Desenho: docs/process/estudos/2026-07-20-desenho-onda-t-patch-dkms.md
(§install.sh — passo novo / §uninstall.sh — simétrico).

Regras da casa cobertas (falha-sem/passa-com):
- install SEM FLAGS aplica o DKMS (default ON); `--no-dkms` é o único
  opt-out (CI/sem hardware, como --no-udev) — e vale em TODO formato
  (native E flatpak/appimage/deb, mesmo padrão do broker/achado #7);
- ativação FAIL-SAFE: a função NUNCA chama modprobe/rmmod (a mantenedora
  joga com Pro/8BitDo conectados; substituir módulo carregado os derruba) —
  a mensagem honesta é "vale no próximo boot";
- uninstall simétrico SEM flag nova: dkms remove + rm da conf modprobe.d.

Dois níveis, como test_install_broker_step.py: execução REAL da função
extraída (bash de verdade, stubs, sem root) + contrato de texto.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_PATH = REPO_ROOT / "install.sh"
UNINSTALL_PATH = REPO_ROOT / "uninstall.sh"
DKMS_CONF_PATH = REPO_ROOT / "assets" / "dkms" / "hid-nintendo" / "dkms.conf"
PARITY_PATH = REPO_ROOT / "scripts" / "check_packaging_parity.sh"
HOST_UDEV_PATH = REPO_ROOT / "scripts" / "install-host-udev.sh"

INSTALL = INSTALL_PATH.read_text(encoding="utf-8") if INSTALL_PATH.exists() else ""
UNINSTALL = UNINSTALL_PATH.read_text(encoding="utf-8") if UNINSTALL_PATH.exists() else ""
DKMS_CONF = DKMS_CONF_PATH.read_text(encoding="utf-8") if DKMS_CONF_PATH.exists() else ""
PARITY = PARITY_PATH.read_text(encoding="utf-8") if PARITY_PATH.exists() else ""
HOST_UDEV = HOST_UDEV_PATH.read_text(encoding="utf-8") if HOST_UDEV_PATH.exists() else ""

CONF_ETC = "/etc/modprobe.d/hefesto-hid-nintendo.conf"


def _versao_dkms_conf() -> str:
    match = re.search(r'^PACKAGE_VERSION="([^"]+)"$', DKMS_CONF, re.MULTILINE)
    assert match is not None, "PACKAGE_VERSION ausente no dkms.conf (lote assets)"
    return match.group(1)


def _extrai_funcao_bash(fonte: str, nome: str) -> str:
    """`nome() { ... }` até a primeira `}` em coluna 0 (as funções alvo não
    têm chaves aninhadas em coluna 0)."""
    match = re.search(rf"^{re.escape(nome)}\(\) \{{\n", fonte, re.MULTILINE)
    assert match is not None, f"função {nome}() não encontrada"
    fim = re.search(r"^\}\n", fonte[match.end() :], re.MULTILINE)
    assert fim is not None, f"fim de {nome}() não encontrado"
    return fonte[match.start() : match.end() + fim.end()]


def _sem_comentarios(texto: str) -> str:
    linhas = [re.sub(r"(^|\s)#.*$", r"\1", linha) for linha in texto.splitlines()]
    return "\n".join(linhas)


FN = (
    _extrai_funcao_bash(INSTALL, "install_dkms_hid_nintendo_host")
    if "install_dkms_hid_nintendo_host() {" in INSTALL
    else ""
)


def _roda_funcao(
    tmp_path: Path, prologo: str, path_extra: str | None = None
) -> subprocess.CompletedProcess[str]:
    assert FN, "install_dkms_hid_nintendo_host ausente do install.sh"
    stubs = tmp_path / "bin"
    stubs.mkdir(exist_ok=True)
    script = (
        'warn() { printf "WARN: %s\\n" "$*"; }\n'
        f"{prologo}\n{FN}\n"
        "install_dkms_hid_nintendo_host\n"
        'printf "RC=%s\\n" "$?"\n'
    )
    env = dict(os.environ)
    env["PATH"] = path_extra if path_extra is not None else str(stubs)
    return subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, check=False, env=env
    )


class TestSintaxe:
    def test_bash_n_install_e_uninstall(self) -> None:
        for caminho in (INSTALL_PATH, UNINSTALL_PATH):
            resultado = subprocess.run(
                ["bash", "-n", str(caminho)], capture_output=True, text=True, check=False
            )
            assert resultado.returncode == 0, f"{caminho.name}: {resultado.stderr}"


class TestDefaultOnOptOut:
    def test_no_dkms_nasce_zero_default_e_aplicar(self) -> None:
        assert re.search(r"^NO_DKMS=0$", INSTALL, re.MULTILINE), (
            "install SEM FLAGS aplica o DKMS (regra da casa)"
        )

    def test_flag_no_dkms_e_o_opt_out(self) -> None:
        assert re.search(r"--no-dkms\)\s+NO_DKMS=1", INSTALL), (
            "--no-dkms precisa setar NO_DKMS=1 no parse de flags"
        )

    def test_help_documenta_o_default_e_o_opt_out(self) -> None:
        match = re.search(r"sed -n '2,(\d+)p'", INSTALL)
        assert match is not None, "extração do --help não encontrada"
        cabecalho = "\n".join(INSTALL.splitlines()[: int(match.group(1))])
        assert "--no-dkms" in cabecalho, "o --help precisa documentar o opt-out"
        assert "DKMS hid-nintendo" in cabecalho


class TestWiringEmTodoFormato:
    def test_passo_3i_do_fluxo_native_chama_a_funcao(self) -> None:
        indice = INSTALL.index('step "3i"')
        assert "install_dkms_hid_nintendo_host" in INSTALL[indice : indice + 400]

    def test_formatos_de_pacote_chamam_antes_do_exit_0(self) -> None:
        # Mesmo achado #7 do broker: flatpak/appimage/deb dão exit 0 cedo —
        # o DKMS é mudança de SISTEMA/kernel e vale em todo formato.
        inicio = INSTALL.index('if [[ "${FORMAT}" != "native" ]]; then')
        fim = re.search(r"^\s+exit 0\s*$", INSTALL[inicio:], re.MULTILINE)
        assert fim is not None, "exit 0 do bloco não-native não encontrado"
        bloco = INSTALL[inicio : inicio + fim.start()]
        assert "install_dkms_hid_nintendo_host" in bloco


class TestFuncaoContrato:
    def test_opt_out_decide_antes_de_qualquer_acao(self) -> None:
        assert FN.index('"${NO_DKMS}"') < FN.index("dkms_install_patched_module")
        assert "pulado (--no-dkms)" in FN

    def test_gates_de_sudo_avisam_e_retornam_0_nunca_die(self) -> None:
        assert "command -v sudo" in FN
        assert "sudo -n true" in FN
        assert not re.search(r"\bdie\b", _sem_comentarios(FN)), (
            "DKMS é fail-safe: o install NUNCA aborta por causa dele"
        )

    def test_usa_a_lib_generica_com_pkg_versao_e_assets_certos(self) -> None:
        assert 'source "${ROOT_DIR}/scripts/dkms_lib.sh"' in FN
        # PKG-3 (auditoria 21/07): a versão NÃO é mais literal — vem do
        # dkms.conf via `dkms_pkg_version` (fonte da verdade). Confere que a
        # invocação usa o helper com o src certo, e que a versão parseada
        # equivale à do dkms.conf.
        assert re.search(
            r"dkms_install_patched_module hefesto-hid-nintendo\s*\\\s*"
            r'"\$\(dkms_pkg_version "\$\{_hidn_src\}"\)" "\$\{_hidn_src\}" hid-nintendo',
            FN,
        ), "pkg/versão(dkms_pkg_version)/src/builtname precisam bater com o asset"
        assert '_hidn_src="${ROOT_DIR}/assets/dkms/hid-nintendo"' in FN
        assert _versao_dkms_conf()  # dkms.conf parseável (a fonte da verdade existe)

    def test_instala_a_conf_da_cura_em_etc_modprobe_d(self) -> None:
        assert "install -Dm644" in FN
        assert CONF_ETC in FN
        assert "bt_probe_retries=3" in FN

    def test_ativacao_nunca_recarrega_modulo(self) -> None:
        # modprobe.d (o DIRETÓRIO de conf) é legítimo — o PROIBIDO é invocar
        # modprobe/rmmod/insmod (recarga de módulo).
        assert not re.search(
            r"\b(modprobe(?!\.d)|rmmod|insmod)\b", _sem_comentarios(FN)
        ), "recarregar hid_nintendo derrubaria Pro/8BitDo em uso (inviolável)"

    def test_ativacao_distingue_os_tres_estados_com_mensagem_honesta(self) -> None:
        assert "/sys/module/hid_nintendo/parameters" in FN, "patchado já carregado"
        assert re.search(r"-d /sys/module/hid_nintendo\s*\]\]", FN), "in-tree em uso"
        assert "próximo boot" in FN, (
            "replug NÃO troca módulo carregado — a mensagem honesta é boot"
        )
        assert "descarregado" in FN, "descarregado: o patchado entra no próximo plug"

    def test_ativacao_gateada_pelo_staging_real(self) -> None:
        # Achado #5 do corretor: dkms_install_patched_module retorna 0 em
        # TODOS os ramos (fail-safe por desenho) — o único juiz de "staged"
        # é dkms_module_from_updates. Sem o gate, o install anunciava "o
        # patchado entra sozinho no próximo plug" com dkms ausente/falho.
        assert "dkms_module_from_updates hid-nintendo" in FN, (
            "a mensagem de ativação exige prova de staging (modinfo -> updates/dkms)"
        )
        assert FN.index("dkms_module_from_updates hid-nintendo") < FN.index(
            "/sys/module/hid_nintendo/parameters"
        ), "o gate vem ANTES de qualquer mensagem de ativação"
        assert "NÃO ficou staged" in FN, "warn honesto quando o DKMS não pegou"


class TestFuncaoComportamental:
    """Execução REAL da função extraída — sem root, sem tocar no sistema."""

    def test_no_dkms_1_pula_sem_tocar_em_nada(self, tmp_path: Path) -> None:
        resultado = _roda_funcao(tmp_path, "NO_DKMS=1")
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "pulado (--no-dkms)" in resultado.stdout
        assert "dkms" not in resultado.stderr

    def test_sem_sudo_avisa_e_segue_fail_safe(self, tmp_path: Path) -> None:
        # PATH só com stubs (sem sudo): warn honesto + RC=0 — o install
        # continua e o driver in-tree segue valendo.
        resultado = _roda_funcao(tmp_path, "NO_DKMS=0")
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "sudo ausente" in resultado.stdout
        assert "in-tree continua" in resultado.stdout

    def test_staging_falho_nao_anuncia_ativacao_futura(self, tmp_path: Path) -> None:
        # Achado #5 do corretor, cenário real: máquina SEM dkms (ou build
        # falho). A lib avisa e retorna 0; a função NÃO pode seguir para o
        # bloco de ativação e prometer "o patchado entra sozinho no próximo
        # plug/boot" — nada foi staged e o próximo plug carrega o in-tree.
        stubs = tmp_path / "bin"
        stubs.mkdir(exist_ok=True)
        for nome, corpo in (
            ("uname", 'echo "0.0.0-hefesto-fake"'),
            ("sudo", "exit 0"),  # sudo -n true OK; installs de conf engolidos
        ):
            caminho = stubs / nome
            caminho.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
            caminho.chmod(0o755)
        # PATH SÓ com os stubs: sem dkms e sem modinfo — staging impossível.
        resultado = _roda_funcao(
            tmp_path,
            f"NO_DKMS=0\nROOT_DIR='{REPO_ROOT}'",
            path_extra=str(stubs),
        )
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "NÃO ficou staged" in resultado.stdout, (
            "sem staging real o install precisa avisar, não prometer ativação"
        )
        for promessa in (
            "JÁ carregado",
            "vale no próximo boot",
            "entra sozinho no próximo plug",
        ):
            assert promessa not in resultado.stdout, (
                f"promessa de ativação FALSA com DKMS falho: {promessa!r}"
            )


class TestUninstallSimetrico:
    def test_remove_via_lib_com_a_mesma_versao_do_dkms_conf(self) -> None:
        # PKG-3: o remove parseia a versão do dkms.conf (mesma fonte do install).
        assert 'source "${ROOT_DIR}/scripts/dkms_lib.sh"' in UNINSTALL
        assert re.search(
            r"dkms_remove_patched_module hefesto-hid-nintendo\s*\\\s*"
            r'"\$\(dkms_pkg_version "\$\{ROOT_DIR\}/assets/dkms/hid-nintendo"\)"',
            UNINSTALL,
        )
        assert _versao_dkms_conf()

    def test_remove_a_conf_da_cura(self) -> None:
        assert f"sudo rm -f {CONF_ETC}" in UNINSTALL

    def test_sem_flag_nova_simetria_por_default(self) -> None:
        # install SEM FLAGS aplica ⇒ uninstall SEM FLAGS remove (regra da
        # casa da simetria) — nada de --keep-dkms/--no-dkms no uninstall.
        assert "keep-dkms" not in UNINSTALL
        assert "--no-dkms" not in UNINSTALL

    def test_gate_needs_sudo_registra_conf_e_registro_dkms(self) -> None:
        assert re.search(
            rf"\[\[ -e {re.escape(CONF_ETC)} \]\] && _NEEDS_SUDO=1", UNINSTALL
        )
        indice = UNINSTALL.index("dkms status hefesto-hid-nintendo")
        assert "_NEEDS_SUDO=1" in UNINSTALL[indice : indice + 120], (
            "registro dkms presente também arma o acquire_sudo"
        )

    def test_fallback_manual_quando_sem_sudo(self) -> None:
        assert "sudo dkms remove hefesto-hid-nintendo/1.0.0 --all" in UNINSTALL, (
            "sem sudo o uninstall imprime o comando manual (nunca silêncio)"
        )

    def test_uninstall_nunca_recarrega_hid_nintendo(self) -> None:
        codigo = _sem_comentarios(UNINSTALL)
        assert "modprobe hid_nintendo" not in codigo
        assert "modprobe hid-nintendo" not in codigo, (
            "o in-tree volta SOZINHO no próximo boot (depmod já rodou)"
        )


class TestParidadePackaging:
    def test_conf_nova_esta_sob_o_contrato_de_paridade(self) -> None:
        # check_packaging_parity.sh varre assets/modprobe.d/*.conf — a conf
        # da Onda T entra AUTOMATICAMENTE no contrato (qualquer instalador
        # furado vira [FAIL] no gate, sem lista manual).
        assert "assets/modprobe.d/*.conf" in PARITY

    def test_perna_do_uninstall_cumprida(self) -> None:
        assert "hefesto-hid-nintendo.conf" in UNINSTALL

    # ------------------------------------------------------------------
    # Achado #9 do corretor: a cura DKMS nunca chegava a usuários de pacote
    # (.deb/PKGBUILD/spec/flatpak) — só a conf INERTE era empacotada, e o
    # install-host-udev.sh (o passo terminal documentado pelos 3 formatos)
    # não tinha uma linha de dkms sequer.
    # ------------------------------------------------------------------

    def test_fontes_dkms_e_lib_em_todo_formato_empacotado(self) -> None:
        manifestos = {
            "scripts/build_deb.sh": REPO_ROOT / "scripts" / "build_deb.sh",
            "packaging/arch/PKGBUILD": REPO_ROOT / "packaging" / "arch" / "PKGBUILD",
            "packaging/fedora/hefesto-dualsense4unix.spec": (
                REPO_ROOT / "packaging" / "fedora" / "hefesto-dualsense4unix.spec"
            ),
            "flatpak/br.andrefarias.Hefesto.yml": (
                REPO_ROOT / "flatpak" / "br.andrefarias.Hefesto.yml"
            ),
        }
        for nome, caminho in manifestos.items():
            texto = caminho.read_text(encoding="utf-8")
            assert "dkms/hid-nintendo" in texto, (
                f"{nome} não empacota as fontes DKMS — a conf modprobe.d "
                "fica inerte e a cura de raiz do probe BT não chega ao usuário"
            )
            assert "dkms_lib.sh" in texto, f"{nome} não empacota a lib DKMS"

    def test_install_host_udev_roda_o_dkms_dos_pacotes(self) -> None:
        # O caminho pós-instalação OFICIAL (postinst/%post/PKGBUILD apontam
        # p/ este script) precisa construir o módulo, não só copiar a conf.
        assert "dkms_install_patched_module hefesto-hid-nintendo" in HOST_UDEV
        assert "dkms_module_from_updates hid-nintendo" in HOST_UDEV, (
            "mensagem de staging honesta exige a prova por modinfo"
        )
        assert "skip_tx_on_rate_exceeded" in HOST_UDEV, (
            "escrita a quente também do gate do skip-TX (paridade com a conf)"
        )

    def test_parity_gate_cobre_o_spec_e_a_cura_dkms(self) -> None:
        # Achado #10: o .spec ficava fora do gate de modprobe.d (remoção lá
        # passava verde) e não havia gate nenhum p/ as fontes DKMS.
        assert "packaging/fedora/hefesto-dualsense4unix.spec" in PARITY, (
            "o .spec precisa estar sob o contrato de paridade (era o único fora)"
        )
        assert "dkms/hid-nintendo" in PARITY, (
            "sem gate das fontes DKMS, o furo 'só a conf viaja' volta sem aviso"
        )
        assert "dkms_install_patched_module" in PARITY, (
            "o gate cobra que o install-host-udev.sh RODE o DKMS"
        )

    def test_doctor_remedia_tambem_o_usuario_de_pacote(self) -> None:
        # 'rode ./install.sh' é inacionável p/ quem só tem o pacote — o
        # doctor precisa apontar o caminho empacotado equivalente.
        doctor = (REPO_ROOT / "scripts" / "doctor.sh").read_text(encoding="utf-8")
        assert "install-host-udev.sh" in doctor

    def test_remocao_de_pacote_nao_deixa_dkms_orfao(self) -> None:
        # Simetria (mesma exigência do broker/achado #21): o módulo DKMS é
        # construído FORA do manifesto do gerenciador de pacotes — remove/
        # purge precisam desregistrá-lo, senão o patchado vence o in-tree
        # para sempre numa máquina que removeu o app.
        hooks = {
            "packaging/debian/prerm": REPO_ROOT / "packaging" / "debian" / "prerm",
            "packaging/debian/postrm": REPO_ROOT / "packaging" / "debian" / "postrm",
            "packaging/arch/hefesto-dualsense4unix.install": (
                REPO_ROOT / "packaging" / "arch" / "hefesto-dualsense4unix.install"
            ),
            "packaging/fedora/hefesto-dualsense4unix.spec": (
                REPO_ROOT / "packaging" / "fedora" / "hefesto-dualsense4unix.spec"
            ),
        }
        for nome, caminho in hooks.items():
            texto = caminho.read_text(encoding="utf-8")
            assert "dkms remove" in texto and "hefesto-hid-nintendo" in texto, (
                f"{nome} não desregistra o módulo DKMS na remoção do pacote"
            )
            assert "modprobe -r" not in texto, (
                f"{nome} NUNCA pode descarregar módulo em uso (controles cairiam)"
            )
