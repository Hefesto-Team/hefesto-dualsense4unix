"""Onda W — DKMS rtw88_usb por DEFAULT no install.sh + uninstall simétrico.

Desenho: docs/process/estudos/2026-07-20-desenho-onda-w-patch-dkms.md (§3).

Regras da casa cobertas (falha-sem/passa-com):
- install SEM FLAGS aplica o DKMS (default ON); `--no-dkms` é o MESMO
  opt-out da Onda T (desliga AMBOS os módulos) — e vale em TODO formato
  (native E flatpak/appimage/deb, padrão do broker/achado #7);
- ativação FAIL-SAFE: a função NUNCA chama modprobe/rmmod (substituir o
  rtw88_usb carregado derrubaria o WiFi da mantenedora AO VIVO) — mensagem
  honesta nos 3 estados, e o marcador de "patchado carregado" é o PARÂMETRO
  hang_reset (o in-tree JÁ expõe parameters/ com switch_usb_mode — só o
  diretório NÃO distingue);
- fail-safe da lib exercitado de verdade: sem sudo, sem dkms e SEM HEADERS
  o install avisa e segue (in-tree continua), sem promessa falsa de ativação;
- uninstall simétrico SEM flag nova: dkms remove + conf.d do NM (se presente);
- o conf.d de powersave do NM (W2) NÃO entra no install por default —
  gateado por evidência da medição;
- paridade packaging (mesmo achado #9 da Onda T): as fontes DKMS viajam em
  todo formato empacotado e o install-host-udev.sh RODA o DKMS do rtw88.

Dois níveis, como test_install_dkms_default.py: execução REAL da função
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
DKMS_CONF_PATH = REPO_ROOT / "assets" / "dkms" / "rtw88-usb" / "dkms.conf"
PARITY_PATH = REPO_ROOT / "scripts" / "check_packaging_parity.sh"
HOST_UDEV_PATH = REPO_ROOT / "scripts" / "install-host-udev.sh"

INSTALL = INSTALL_PATH.read_text(encoding="utf-8") if INSTALL_PATH.exists() else ""
UNINSTALL = UNINSTALL_PATH.read_text(encoding="utf-8") if UNINSTALL_PATH.exists() else ""
DKMS_CONF = DKMS_CONF_PATH.read_text(encoding="utf-8") if DKMS_CONF_PATH.exists() else ""
PARITY = PARITY_PATH.read_text(encoding="utf-8") if PARITY_PATH.exists() else ""
HOST_UDEV = HOST_UDEV_PATH.read_text(encoding="utf-8") if HOST_UDEV_PATH.exists() else ""

NM_CONF_ETC = "/etc/NetworkManager/conf.d/hefesto-wifi-powersave.conf"


def _versao_dkms_conf() -> str:
    match = re.search(r'^PACKAGE_VERSION="([^"]+)"$', DKMS_CONF, re.MULTILINE)
    assert match is not None, "PACKAGE_VERSION ausente no dkms.conf (lote assets)"
    return match.group(1)


def _extrai_funcao_bash(fonte: str, nome: str) -> str:
    """`nome() { ... }` até a primeira `}` em coluna 0."""
    match = re.search(rf"^{re.escape(nome)}\(\) \{{\n", fonte, re.MULTILINE)
    assert match is not None, f"função {nome}() não encontrada"
    fim = re.search(r"^\}\n", fonte[match.end() :], re.MULTILINE)
    assert fim is not None, f"fim de {nome}() não encontrado"
    return fonte[match.start() : match.end() + fim.end()]


def _sem_comentarios(texto: str) -> str:
    linhas = [re.sub(r"(^|\s)#.*$", r"\1", linha) for linha in texto.splitlines()]
    return "\n".join(linhas)


FN = (
    _extrai_funcao_bash(INSTALL, "install_dkms_rtw88_usb_host")
    if "install_dkms_rtw88_usb_host() {" in INSTALL
    else ""
)


def _roda_funcao(
    tmp_path: Path, prologo: str, path_extra: str | None = None
) -> subprocess.CompletedProcess[str]:
    assert FN, "install_dkms_rtw88_usb_host ausente do install.sh"
    stubs = tmp_path / "bin"
    stubs.mkdir(exist_ok=True)
    script = (
        'warn() { printf "WARN: %s\\n" "$*"; }\n'
        f"{prologo}\n{FN}\n"
        "install_dkms_rtw88_usb_host\n"
        'printf "RC=%s\\n" "$?"\n'
    )
    env = dict(os.environ)
    env["PATH"] = path_extra if path_extra is not None else str(stubs)
    return subprocess.run(
        [BASH, "-c", script], capture_output=True, text=True, check=False, env=env
    )


def _stub(stubs: Path, nome: str, corpo: str) -> None:
    caminho = stubs / nome
    caminho.write_text(f"#!/bin/sh\n{corpo}\n", encoding="utf-8")
    caminho.chmod(0o755)


class TestSintaxe:
    def test_bash_n_install_e_uninstall(self) -> None:
        for caminho in (INSTALL_PATH, UNINSTALL_PATH):
            resultado = subprocess.run(
                ["bash", "-n", str(caminho)], capture_output=True, text=True, check=False
            )
            assert resultado.returncode == 0, f"{caminho.name}: {resultado.stderr}"


class TestDefaultOnOptOutCompartilhado:
    def test_no_dkms_nasce_zero_default_e_aplicar(self) -> None:
        assert re.search(r"^NO_DKMS=0$", INSTALL, re.MULTILINE), (
            "install SEM FLAGS aplica o DKMS (regra da casa)"
        )

    def test_gate_compartilhado_com_a_onda_t(self) -> None:
        # --no-dkms desliga AMBOS os módulos (hid-nintendo E rtw88_usb) —
        # nenhuma flag nova nasce aqui.
        assert re.search(r"--no-dkms\)\s+NO_DKMS=1", INSTALL)
        assert "--no-rtw88" not in INSTALL, "opt-out é o --no-dkms compartilhado, sem flag nova"
        assert FN.index('"${NO_DKMS}"') < FN.index("dkms_install_patched_module")
        assert "pulado (--no-dkms)" in FN

    def test_help_documenta_o_default_do_rtw88(self) -> None:
        match = re.search(r"sed -n '2,(\d+)p'", INSTALL)
        assert match is not None, "extração do --help não encontrada"
        cabecalho = "\n".join(INSTALL.splitlines()[: int(match.group(1))])
        assert "DKMS rtw88_usb" in cabecalho, "o --help precisa anunciar o default novo"
        assert "hang_reset" in cabecalho, "o gate de campo do reset fica documentado no --help"


class TestWiringEmTodoFormato:
    def test_passo_3j_do_fluxo_native_chama_a_funcao(self) -> None:
        indice = INSTALL.index('step "3j"')
        assert "install_dkms_rtw88_usb_host" in INSTALL[indice : indice + 400]

    def test_formatos_de_pacote_chamam_antes_do_exit_0(self) -> None:
        # Mesmo achado #7 do broker: flatpak/appimage/deb dão exit 0 cedo —
        # o DKMS é mudança de SISTEMA/kernel e vale em todo formato.
        inicio = INSTALL.index('if [[ "${FORMAT}" != "native" ]]; then')
        fim = re.search(r"^\s+exit 0\s*$", INSTALL[inicio:], re.MULTILINE)
        assert fim is not None, "exit 0 do bloco não-native não encontrado"
        bloco = INSTALL[inicio : inicio + fim.start()]
        assert "install_dkms_rtw88_usb_host" in bloco


class TestFuncaoContrato:
    def test_gates_de_sudo_avisam_e_retornam_0_nunca_die(self) -> None:
        assert "command -v sudo" in FN
        assert "sudo -n true" in FN
        assert not re.search(r"\bdie\b", _sem_comentarios(FN)), (
            "DKMS é fail-safe: o install NUNCA aborta por causa dele"
        )

    def test_usa_a_lib_generica_com_pkg_versao_e_assets_certos(self) -> None:
        # 2ª instância da infra da Onda T: ZERO ajuste na lib, só argumentos.
        assert 'source "${ROOT_DIR}/scripts/dkms_lib.sh"' in FN
        versao = _versao_dkms_conf()
        assert re.search(
            rf"dkms_install_patched_module hefesto-rtw88-usb {re.escape(versao)}\s*\\\s*"
            rf'"\$\{{ROOT_DIR\}}/assets/dkms/rtw88-usb" rtw88_usb',
            FN,
        ), "pkg/versão/src/builtname precisam bater com assets/dkms/rtw88-usb"

    def test_ativacao_nunca_recarrega_modulo(self) -> None:
        assert not re.search(
            r"\b(modprobe(?!\.d)|rmmod|insmod)\b", _sem_comentarios(FN)
        ), "recarregar rtw88_usb derrubaria o WiFi em uso (inviolável)"

    def test_marcador_do_patchado_e_o_param_hang_reset(self) -> None:
        # Diferente do hid_nintendo (0 params no in-tree): o rtw88_usb
        # in-tree JÁ expõe parameters/ (switch_usb_mode) — o diretório
        # sozinho NÃO distingue; o marcador é o PARÂMETRO NOVO hang_reset.
        assert "-e /sys/module/rtw88_usb/parameters/hang_reset" in FN, (
            "detecção do patchado carregado exige o param exclusivo do patch"
        )
        assert re.search(r"-d /sys/module/rtw88_usb\s*\]\]", FN), "in-tree em uso"

    def test_ativacao_distingue_os_tres_estados_com_mensagem_honesta(self) -> None:
        assert "próximo boot" in FN, (
            "replug NÃO troca módulo carregado — a mensagem honesta é boot"
        )
        assert "replug NÃO troca módulo carregado" in FN
        assert "descarregado" in FN, "descarregado: o patchado entra no próximo plug do dongle"

    def test_ativacao_gateada_pelo_staging_real(self) -> None:
        # Mesmo achado #5 do corretor da Onda T: a lib retorna 0 em TODOS os
        # ramos — o único juiz de "staged" é dkms_module_from_updates.
        assert "dkms_module_from_updates rtw88_usb" in FN
        assert FN.index("dkms_module_from_updates rtw88_usb") < FN.index(
            "/sys/module/rtw88_usb/parameters/hang_reset"
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
        resultado = _roda_funcao(tmp_path, "NO_DKMS=0")
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "sudo ausente" in resultado.stdout
        assert "in-tree continua" in resultado.stdout

    def test_staging_falho_nao_anuncia_ativacao_futura(self, tmp_path: Path) -> None:
        # Máquina SEM dkms (ou build falho): a lib avisa e retorna 0; a
        # função NÃO pode prometer ativação — nada foi staged e o próximo
        # plug carrega o in-tree.
        stubs = tmp_path / "bin"
        stubs.mkdir(exist_ok=True)
        _stub(stubs, "uname", 'echo "0.0.0-hefesto-fake"')
        _stub(stubs, "sudo", "exit 0")
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

    def test_sem_headers_do_kernel_avisa_e_segue(self, tmp_path: Path) -> None:
        # (b) do contrato da onda: warn honesto sem headers. Usa a costura de
        # teste da lib (HEFESTO_DKMS_MODULES_ROOT) apontando p/ um diretório
        # vazio — o build nunca é tentado e o in-tree continua.
        stubs = tmp_path / "bin"
        stubs.mkdir(exist_ok=True)
        _stub(stubs, "uname", 'echo "0.0.0-hefesto-fake"')
        _stub(stubs, "sudo", "exit 0")
        _stub(stubs, "dkms", "exit 0")
        (tmp_path / "mods").mkdir()
        resultado = _roda_funcao(
            tmp_path,
            (
                f"NO_DKMS=0\nROOT_DIR='{REPO_ROOT}'\n"
                f"HEFESTO_DKMS_MODULES_ROOT='{tmp_path}/mods'\n"
                f"HEFESTO_DKMS_SRC_ROOT='{tmp_path}/src'"
            ),
            path_extra=str(stubs),
        )
        assert "RC=0" in resultado.stdout, resultado.stderr
        assert "headers do kernel" in resultado.stdout
        assert "NÃO ficou staged" in resultado.stdout, (
            "sem headers nada foi staged — a mensagem de ativação não pode sair"
        )


class TestUninstallSimetrico:
    def test_remove_via_lib_com_a_mesma_versao_do_dkms_conf(self) -> None:
        versao = _versao_dkms_conf()
        assert 'source "${ROOT_DIR}/scripts/dkms_lib.sh"' in UNINSTALL
        assert f"dkms_remove_patched_module hefesto-rtw88-usb {versao}" in UNINSTALL

    def test_sem_flag_nova_simetria_por_default(self) -> None:
        assert "keep-dkms" not in UNINSTALL
        assert "--no-dkms" not in UNINSTALL

    def test_gate_needs_sudo_arma_com_registro_dkms_e_conf_nm(self) -> None:
        indice = UNINSTALL.index("dkms status hefesto-rtw88-usb")
        assert "_NEEDS_SUDO=1" in UNINSTALL[indice : indice + 120], (
            "registro dkms do rtw88 presente também arma o acquire_sudo"
        )
        assert re.search(
            rf"\[\[ -e {re.escape(NM_CONF_ETC)} \]\] && _NEEDS_SUDO=1", UNINSTALL
        ), "conf.d do NM presente também arma o acquire_sudo"

    def test_fallback_manual_quando_sem_sudo(self) -> None:
        versao = _versao_dkms_conf()
        assert f"sudo dkms remove hefesto-rtw88-usb/{versao} --all" in UNINSTALL, (
            "sem sudo o uninstall imprime o comando manual (nunca silêncio)"
        )

    def test_remove_a_conf_do_nm_se_presente(self) -> None:
        # Simetria "se instalado, some" (mesmo padrão do storm.conf): o
        # conf.d do W2 é opt-in, mas o uninstall limpa sem flag nova.
        assert f"sudo rm -f {NM_CONF_ETC}" in UNINSTALL

    def test_uninstall_nunca_recarrega_nem_toca_o_radio(self) -> None:
        codigo = _sem_comentarios(UNINSTALL)
        assert "modprobe rtw88" not in codigo, (
            "o in-tree volta SOZINHO no próximo boot (dkms remove já roda depmod)"
        )
        assert not re.search(r"\bnmcli\b", codigo), "uninstall NUNCA chama nmcli"
        assert not re.search(r"\brfkill\b", codigo), "uninstall NUNCA chama rfkill"

    def test_hang_reset_devolvido_a_0_sem_reload(self) -> None:
        # Diferente da Onda T não há conf externa: p/ o módulo carregado
        # ficar menos agressivo até o boot, o uninstall devolve SÓ o
        # hang_reset a 0 via /sys (0644) — detecção/silenciamento continuam.
        indice = UNINSTALL.index("dkms_remove_patched_module hefesto-rtw88-usb")
        bloco = UNINSTALL[indice : indice + 700]
        assert "/sys/module/rtw88_usb/parameters/hang_reset" in bloco
        assert "tee /sys/module/rtw88_usb/parameters/hang_reset" in bloco


class TestPowersaveGateadoPorEvidencia:
    def test_conf_do_nm_nao_e_aplicada_por_default(self) -> None:
        # (g) do contrato: o asset assets/NetworkManager/*.conf NÃO entra no
        # install por default — só vira default quando a medição W2 provar
        # ganho. Hoje: NENHUM caminho de código do install toca o conf.
        codigo = _sem_comentarios(INSTALL)
        if "hefesto-wifi-powersave" not in codigo:
            return  # gateado por ausência: o install não toca o conf.d do NM
        # Se um dia entrar, TEM de ser opt-in explícito nascendo desligado.
        assert re.search(r"^WIFI_POWERSAVE_OFF=0$", INSTALL, re.MULTILINE), (
            "o conf de powersave só pode entrar atrás de flag opt-in default 0"
        )
        assert re.search(r"--wifi-powersave-off\)\s+WIFI_POWERSAVE_OFF=1", INSTALL), (
            "a flag opt-in precisa existir no parse (--wifi-powersave-off)"
        )

    def test_install_nunca_chama_nmcli_ou_rfkill(self) -> None:
        codigo = _sem_comentarios(INSTALL)
        assert not re.search(r"\bnmcli\b", codigo), (
            "install NUNCA mexe no NetworkManager — medição é do medir_w2_lps.sh"
        )
        assert not re.search(r"\brfkill\b", codigo)


class TestParidadePackaging:
    """Mesmo achado #9 da Onda T: sem as fontes DKMS nos pacotes, a cura de
    raiz do fantasma USB nunca chega a usuários de .deb/rpm/arch/flatpak."""

    def test_fontes_dkms_em_todo_formato_empacotado(self) -> None:
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
            assert "rtw88-usb" in texto, (
                f"{nome} não empacota as fontes DKMS do rtw88 — a cura de raiz "
                "do fantasma USB não chega ao usuário de pacote"
            )

    def test_install_host_udev_roda_o_dkms_dos_pacotes(self) -> None:
        # O caminho pós-instalação OFICIAL (postinst/%post/PKGBUILD apontam
        # p/ este script) precisa construir o módulo, não só carregar fontes.
        assert "dkms_install_patched_module hefesto-rtw88-usb" in HOST_UDEV
        assert "dkms_module_from_updates rtw88_usb" in HOST_UDEV, (
            "mensagem de staging honesta exige a prova por modinfo"
        )

    def test_parity_gate_cobre_a_cura_dkms_do_rtw88(self) -> None:
        assert "rtw88-usb" in PARITY, (
            "sem gate das fontes DKMS do rtw88, o furo 'a cura não viaja nos "
            "pacotes' volta sem aviso (mesma lição do hid-nintendo)"
        )

    def test_remocao_de_pacote_nao_deixa_dkms_orfao(self) -> None:
        # Simetria: o módulo DKMS nasce FORA do manifesto do gerenciador de
        # pacotes — remove/purge precisam desregistrá-lo, senão o patchado
        # vence o in-tree para sempre numa máquina que removeu o app.
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
            assert "dkms remove" in texto and "hefesto-rtw88-usb" in texto, (
                f"{nome} não desregistra o módulo DKMS do rtw88 na remoção"
            )
            assert "modprobe -r" not in texto, (
                f"{nome} NUNCA pode descarregar módulo em uso (WiFi cairia)"
            )
