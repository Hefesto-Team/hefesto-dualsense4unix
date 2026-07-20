"""BROKER-01 (Onda S — fd-injection): passo 3h do install.sh + simetria no
uninstall.sh + doctor.sh.

Desenho: docs/process/estudos/2026-07-20-desenho-onda-s-broker-fd-injection.md §7.

Dois níveis de teste, os dois falha-sem/passa-com:

1. Comportamental REAL: `_render_broker_units` (função pura do install.sh, sem
   sudo/systemctl) é extraída e executada com bash de verdade contra os
   assets REAIS de B1 (assets/systemd/hefesto-hidraw-broker.{service,socket})
   — prova que o sed produz uid/grupo reais e que a guarda pós-render pega
   placeholder sobrando (ex.: asset com o token errado, sed não substitui).

2. Contrato de TEXTO (padrão do repo para o resto da lógica shell — ver
   test_plataforma_wiring.py/test_udev_kernel07_path06.py): a mensagem de
   abort do uid 0, a ordem "uid==0 decide ANTES de qualquer sudo install", o
   registro de posse, o daemon-reload/enable --now e a simetria do
   uninstall.sh (restore-all ANTES do rm; header do hefesto antes de remover;
   disable+stop antes do belt) — a validação viva acontece no ciclo final do
   install (gate do orquestrador).
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALL_PATH = REPO_ROOT / "install.sh"
UNINSTALL_PATH = REPO_ROOT / "uninstall.sh"
DOCTOR_PATH = REPO_ROOT / "scripts" / "doctor.sh"
SERVICE_ASSET = REPO_ROOT / "assets" / "systemd" / "hefesto-hidraw-broker.service"
SOCKET_ASSET = REPO_ROOT / "assets" / "systemd" / "hefesto-hidraw-broker.socket"
PRERM_PATH = REPO_ROOT / "packaging" / "debian" / "prerm"
POSTRM_PATH = REPO_ROOT / "packaging" / "debian" / "postrm"
POSTINST_PATH = REPO_ROOT / "packaging" / "debian" / "postinst"

INSTALL = INSTALL_PATH.read_text(encoding="utf-8") if INSTALL_PATH.exists() else ""
UNINSTALL = UNINSTALL_PATH.read_text(encoding="utf-8") if UNINSTALL_PATH.exists() else ""
DOCTOR = DOCTOR_PATH.read_text(encoding="utf-8") if DOCTOR_PATH.exists() else ""
PRERM = PRERM_PATH.read_text(encoding="utf-8") if PRERM_PATH.exists() else ""
POSTRM = POSTRM_PATH.read_text(encoding="utf-8") if POSTRM_PATH.exists() else ""
POSTINST = POSTINST_PATH.read_text(encoding="utf-8") if POSTINST_PATH.exists() else ""


def _extract_bash_function(source: str, name: str) -> str:
    """Extrai `name() { ... }` (fecha na 1ª `}` sozinha numa linha após o
    início) — as funções deste módulo só usam `if/fi`, nunca chaves
    aninhadas, então o primeiro `}` de coluna 0 é sempre o fim real."""
    match = re.search(rf"^{re.escape(name)}\(\) \{{\n", source, re.MULTILINE)
    if match is None:
        raise AssertionError(f"função {name}() não encontrada")
    start = match.start()
    end_match = re.search(r"^\}\n", source[match.end() :], re.MULTILINE)
    if end_match is None:
        raise AssertionError(f"fim de {name}() não encontrado")
    end = match.end() + end_match.end()
    return source[start:end]


@pytest.fixture(scope="module")
def render_fn_src() -> str:
    if not INSTALL:
        pytest.skip("install.sh não encontrado no repo")
    return _extract_bash_function(INSTALL, "_render_broker_units")


def _run_render(
    render_fn_src: str,
    service_src: Path,
    socket_src: Path,
    out_dir: Path,
    uid: str,
    grupo: str,
) -> subprocess.CompletedProcess[str]:
    script = (
        f"{render_fn_src}\n"
        f'_render_broker_units "{service_src}" "{socket_src}" "{out_dir}" "{uid}" "{grupo}"\n'
    )
    return subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=False
    )


class TestRenderBrokerUnitsComportamental:
    """Execução REAL de bash contra os assets de B1 — comportamento, não texto."""

    def test_sed_produz_uid_e_grupo_reais(self, render_fn_src: str, tmp_path: Path) -> None:
        if not SERVICE_ASSET.exists() or not SOCKET_ASSET.exists():
            pytest.skip("assets/systemd/hefesto-hidraw-broker.{service,socket} ausentes (lote B1)")
        result = _run_render(
            render_fn_src, SERVICE_ASSET, SOCKET_ASSET, tmp_path, "1000", "usuaria"
        )
        assert result.returncode == 0, result.stderr

        service_out = (tmp_path / "hefesto-hidraw-broker.service").read_text(encoding="utf-8")
        socket_out = (tmp_path / "hefesto-hidraw-broker.socket").read_text(encoding="utf-8")

        assert "HEFESTO_BROKER_ALLOWED_UID=1000" in service_out
        assert "SocketGroup=usuaria" in socket_out
        assert "__SESSION_" not in service_out
        assert "__SESSION_" not in socket_out

    def test_uid_e_grupo_nunca_cruzam(self, render_fn_src: str, tmp_path: Path) -> None:
        """Placeholders são DISTINTOS por arquivo — uid nunca vaza pro
        .socket nem grupo pro .service (cada sed só conhece o próprio par)."""
        if not SERVICE_ASSET.exists() or not SOCKET_ASSET.exists():
            pytest.skip("assets/systemd/hefesto-hidraw-broker.{service,socket} ausentes (lote B1)")
        result = _run_render(
            render_fn_src, SERVICE_ASSET, SOCKET_ASSET, tmp_path, "4242", "grupo-teste"
        )
        assert result.returncode == 0, result.stderr
        service_out = (tmp_path / "hefesto-hidraw-broker.service").read_text(encoding="utf-8")
        socket_out = (tmp_path / "hefesto-hidraw-broker.socket").read_text(encoding="utf-8")
        assert "grupo-teste" not in service_out
        assert "4242" not in socket_out

    def test_guarda_pos_render_pega_placeholder_sobrando(
        self, render_fn_src: str, tmp_path: Path
    ) -> None:
        """Asset com o token ERRADO (typo/edição futura sem seguir o
        contrato) faz o sed não casar nada — a guarda devolve 1 e NENHUM
        arquivo de saída fica utilizável (placeholder ainda presente)."""
        fake_service = tmp_path / "fake.service"
        fake_socket = tmp_path / "fake.socket"
        fake_service.write_text(
            "Environment=HEFESTO_BROKER_ALLOWED_UID=__SESSION_UID_TYPO__\n",
            encoding="utf-8",
        )
        fake_socket.write_text("SocketGroup=__SESSION_GROUP__\n", encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = _run_render(render_fn_src, fake_service, fake_socket, out_dir, "1000", "usuaria")
        assert result.returncode == 1

        service_out = (out_dir / "hefesto-hidraw-broker.service").read_text(encoding="utf-8")
        assert "__SESSION_UID_TYPO__" in service_out, "sed não deveria ter casado o token errado"

    def test_guarda_pega_service_ok_mas_socket_com_placeholder_sobrando(
        self, render_fn_src: str, tmp_path: Path
    ) -> None:
        """Um dos dois arquivos renderizar limpo não basta — a guarda olha
        os DOIS (grep com 2 argumentos) antes de devolver sucesso."""
        fake_service = tmp_path / "fake.service"
        fake_socket = tmp_path / "fake.socket"
        fake_service.write_text(
            "Environment=HEFESTO_BROKER_ALLOWED_UID=__SESSION_UID__\n", encoding="utf-8"
        )
        fake_socket.write_text("SocketGroup=__SESSION_GRUPO_TYPO__\n", encoding="utf-8")
        out_dir = tmp_path / "out"
        out_dir.mkdir()

        result = _run_render(render_fn_src, fake_service, fake_socket, out_dir, "1000", "usuaria")
        assert result.returncode == 1


class TestInstallStep3hContrato:
    """Contrato de texto (padrão do repo) — a validação viva é o ciclo do install real."""

    def test_step_existe_com_label_correto(self) -> None:
        assert 'step "3h"' in INSTALL
        assert "BROKER-01" in INSTALL

    def test_sem_flag_de_opt_out_e_default_sem_udev_skip(self) -> None:
        # Gate = mesmo padrão dos passos de plataforma (3d/3f/3g): SKIP_UDEV +
        # sudo disponível. NENHUMA flag própria de opt-out (broker é DEFAULT).
        assert "--no-broker" not in INSTALL
        step3h = INSTALL[INSTALL.index('step "3h"') - 400 : INSTALL.index('step "3h"')]
        assert '"${SKIP_UDEV}" -eq 0' in step3h
        assert "command -v sudo" in step3h

    def test_uid_resolvido_como_sudo_uid_ou_id_u(self) -> None:
        assert '_broker_uid="${SUDO_UID:-$(id -u)}"' in INSTALL

    def test_uid_0_aborta_com_a_mensagem_antes_de_qualquer_sudo_install(self) -> None:
        msg_idx = INSTALL.index("SESSION_UID resolveu 0")
        assert "Passo ABORTADO" in INSTALL[msg_idx : msg_idx + 400]
        # A checagem de uid==0 precisa vir ANTES do primeiro `sudo install`
        # do binário do broker — nunca instala nada com uid inválido.
        uid_check_idx = INSTALL.index('"${_broker_uid}" == "0"')
        broker_install_idx = INSTALL.index("_broker_bin_dst}\" 2>/dev/null")
        assert uid_check_idx < broker_install_idx

    def test_render_chamado_antes_de_instalar_o_binario(self) -> None:
        render_call_idx = INSTALL.index("_render_broker_units \\")
        broker_install_idx = INSTALL.index('sudo install -Dm755 "${_broker_bin_src}"')
        assert render_call_idx < broker_install_idx

    def test_daemon_reload_e_enable_now_do_socket(self) -> None:
        assert "systemctl daemon-reload" in INSTALL
        assert "systemctl enable --now hefesto-hidraw-broker.socket" in INSTALL

    def test_registro_de_posse_grava_caminhos_e_sha256(self) -> None:
        assert "broker-owner.conf" in INSTALL
        assert "sha256sum" in INSTALL

    def test_help_sed_range_cobre_o_novo_bullet_do_broker(self) -> None:
        # -h/--help extrai o cabeçalho por range de linha; o bullet do
        # broker precisa estar DENTRO do range extraído (senão o --help
        # não documenta o passo).
        match = re.search(r"sed -n '2,(\d+)p'", INSTALL)
        assert match is not None, "extração do --help não encontrada"
        end_line = int(match.group(1))
        header = "\n".join(INSTALL.splitlines()[:end_line])
        assert "BROKER-01" in header


class TestUninstallSimetriaContrato:
    def test_bloco_do_broker_presente(self) -> None:
        assert "hefesto-hidraw-broker" in UNINSTALL
        assert "BROKER-01" in UNINSTALL

    def test_needs_sudo_gate_registrado(self) -> None:
        assert "/etc/systemd/system/hefesto-hidraw-broker.service" in UNINSTALL
        assert "_NEEDS_SUDO=1" in UNINSTALL

    def test_disable_stop_antes_do_belt_restore_all(self) -> None:
        disable_idx = UNINSTALL.index("systemctl disable --now hefesto-hidraw-broker.socket")
        restore_idx = UNINSTALL.index('"${BROKER_BIN}" --restore-all-and-exit')
        assert disable_idx < restore_idx

    def test_belt_restore_all_antes_de_remover_o_binario(self) -> None:
        # O binário precisa existir ainda quando o restore-all-and-exit roda
        # — a remoção (rm, dentro do loop do broker-owner.conf OU no branch
        # sem registro) tem de vir DEPOIS.
        restore_idx = UNINSTALL.index('"${BROKER_BIN}" --restore-all-and-exit')
        owner_loop_idx = UNINSTALL.index('while IFS=\'=\' read -r _bp _bsum')
        assert restore_idx < owner_loop_idx

    def test_remocao_verifica_header_do_hefesto(self) -> None:
        assert "instalado por hefesto-dualsense4unix" in UNINSTALL

    def test_owner_file_removido_ao_final(self) -> None:
        assert 'sudo rm -f "${BROKER_OWNER_FILE}"' in UNINSTALL


class TestDoctorCheckContrato:
    def test_check_existe_e_esta_wireado_no_main(self) -> None:
        assert "check_hidraw_broker()" in DOCTOR
        assert re.search(r"^\s*check_hidraw_broker\s*$", DOCTOR, re.MULTILINE), (
            "check_hidraw_broker precisa ser CHAMADA em main(), não só definida"
        )

    def test_checa_unit_de_sistema_sem_flag_user(self) -> None:
        assert "systemctl cat hefesto-hidraw-broker.socket" in DOCTOR
        assert "systemctl --user cat hefesto-hidraw-broker" not in DOCTOR

    def test_ping_valida_peer_uid(self) -> None:
        assert '"cmd": "ping"' in DOCTOR
        assert "peer_uid" in DOCTOR

    def test_cmd_open_e_testado_funcionalmente(self) -> None:
        """Achado Onda S #9: a tabela de riscos do desenho (§9) promete
        'doctor cobre com teste funcional de open' para DeviceAllow=
        char-hidraw — ping/status não exercitam o open(2) sob o device
        cgroup. O check precisa mandar o cmd `open` de verdade e receber o
        fd via SCM_RIGHTS (e fechá-lo)."""
        assert '"cmd": "open"' in DOCTOR
        assert "SCM_RIGHTS" in DOCTOR
        assert "recvmsg" in DOCTOR

    def test_falha_do_open_vira_fail_com_dica_de_deviceallow(self) -> None:
        # Regressão típica: DeviceAllow com 'r' em vez de 'rw', ou
        # CapabilityBoundingSet sem CAP_DAC_OVERRIDE — o fail precisa
        # apontar exatamente onde olhar.
        assert "DeviceAllow=char-hidraw rw" in DOCTOR
        assert "CAP_DAC_OVERRIDE" in DOCTOR

    def test_sem_candidato_e_skip_informativo_nunca_falso_verde(self) -> None:
        # Sem DualSense físico visível o teste é PULADO com info (nunca
        # pass) — reject_not_physical_dualsense (vpad) não conta como ok.
        assert "reject_not_physical_dualsense" in DOCTOR
        assert "cmd open não testado" in DOCTOR


class TestBrokerEmTodosOsFormatos:
    """Achado Onda S #7: broker é DEFAULT em TODO formato do install.sh —
    flatpak/appimage/deb davam `exit 0` antes do passo 3h e ficavam sem a
    cura de raiz do duplicado, sem nenhum aviso."""

    def test_funcao_compartilhada_existe(self) -> None:
        assert "install_broker_host() {" in INSTALL

    def test_passo_3h_nativo_chama_a_funcao(self) -> None:
        idx = INSTALL.index('step "3h"')
        assert "install_broker_host" in INSTALL[idx : idx + 400]

    def test_formatos_de_pacote_chamam_o_broker_antes_do_exit(self) -> None:
        bloco_ini = INSTALL.index('if [[ "${FORMAT}" != "native" ]]; then')
        # O fim do bloco é a LINHA `exit 0` (indentada) — não menções em
        # comentário ("dão `exit 0` antes...").
        fim = re.search(r"^\s+exit 0\s*$", INSTALL[bloco_ini:], re.MULTILINE)
        assert fim is not None, "exit 0 do bloco não-native não encontrado"
        bloco = INSTALL[bloco_ini : bloco_ini + fim.start()]
        assert "install_broker_host" in bloco, (
            "o bloco flatpak/appimage/deb precisa instalar o broker antes do exit 0"
        )

    def test_postinst_do_deb_instrui_a_ativacao(self) -> None:
        # O postinst roda como root SEM sessão (renderizaria uid 0 —
        # PROIBIDO), então ele não ativa: ele INSTRUI, como o Arch e o
        # Fedora já faziam. Antes não havia menção nenhuma.
        assert "BROKER-01" in POSTINST
        assert "install-host-udev.sh" in POSTINST


class TestDebRemocaoBrokerContrato:
    """Achados Onda S #2/#8 (lição 6/#21): purge/remoção do .deb precisa
    desabilitar + restaurar + remover a unit ROOT do broker — como o Arch
    (pre_remove) e o Fedora (%preun) já faziam. As units vivem FORA do
    manifesto do dpkg (render por-máquina), então sem isto o apt nunca as
    tocaria."""

    def test_prerm_desabilita_restaura_e_remove_no_remove(self) -> None:
        assert "hefesto-hidraw-broker.socket" in PRERM
        disable_idx = PRERM.index("systemctl disable --now hefesto-hidraw-broker.socket")
        # O COMANDO do belt (não menções em comentário — por isso o sufixo).
        restore_idx = PRERM.index("--restore-all-and-exit 2>/dev/null || true")
        rm_idx = PRERM.index("rm -f /etc/systemd/system/hefesto-hidraw-broker.service")
        # Ordem: disable (dispara o ExecStopPost) → belt restore → rm units.
        assert disable_idx < restore_idx < rm_idx
        assert "daemon-reload" in PRERM

    def test_prerm_nao_mexe_no_broker_em_upgrade(self) -> None:
        # upgrade NÃO pode derrubar o broker (o serviço sobrevive à troca de
        # versão do pacote): o teardown mora num case exclusivo de remove.
        bloco_remove = PRERM.split("remove)", 1)
        assert len(bloco_remove) == 2
        assert "hefesto-hidraw-broker" not in bloco_remove[0]

    def test_postrm_purge_tem_o_belt_completo(self) -> None:
        purge = POSTRM.split("purge)", 1)
        assert len(purge) == 2, "case purge ausente no postrm"
        corpo = purge[1].split(";;", 1)[0]
        assert "systemctl disable --now hefesto-hidraw-broker.socket" in corpo
        assert "--restore-all-and-exit" in corpo
        assert "rm -f /etc/systemd/system/hefesto-hidraw-broker.service" in corpo

    def test_scripts_do_deb_tem_sintaxe_valida(self) -> None:
        import subprocess

        for path in (PRERM_PATH, POSTRM_PATH, POSTINST_PATH):
            result = subprocess.run(
                ["bash", "-n", str(path)], capture_output=True, text=True, check=False
            )
            assert result.returncode == 0, f"{path.name}: {result.stderr}"
