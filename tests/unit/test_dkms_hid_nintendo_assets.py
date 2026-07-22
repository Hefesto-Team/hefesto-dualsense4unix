"""Onda T (T2.2/T2.3) — assets DKMS do hid-nintendo patchado.

Desenho: docs/process/estudos/2026-07-20-desenho-onda-t-patch-dkms.md.
Premissas: docs/process/estudos/2026-07-20-estudo-premissas-onda-t-hid-nintendo.md.

Contrato dos assets (falha-sem/passa-com; SEM root, SEM kernel vivo — só
arquivos e ferramentas de usuário):

- dkms.conf com os campos exatos (PACKAGE_NAME/BUILT_MODULE_NAME[0]/
  DEST_MODULE_LOCATION[0]=/updates/dkms/AUTOINSTALL) — é a precedência
  updates/dkms que faz o patchado vencer o in-tree SEM blacklist;
- Makefile kbuild mínimo com -DCONFIG_NINTENDO_FF=1 (o in-tree tem
  CONFIG_NINTENDO_FF=y; sem a flag o rumble sumiria — provado no build-test);
- hid-nintendo.c com os 5 module_param uint + 1 bool (defaults == vanilla,
  zero regressão) e o -EAGAIN no enforce_subcmd_rate GATEADO por
  skip_tx_on_rate_exceeded (achado #1 do corretor: mudança de comportamento
  não pode ser incondicional), com a string "exceeded max attempts"
  preservada byte a byte (kernel-watch/doctor atuais continuam casando);
- BASELINE verificável por sha256 recalculado AQUI: o .c shipping bate
  SHA256_PATCHED_C e o patch REVERTIDO (`patch -R -p3`) devolve exatamente
  SHA256_VANILLA_C — o invariante `.c == vanilla + 0001-*.patch` pega
  qualquer edição manual que não passou pelo .patch (e vice-versa);
- conf do modprobe.d com a cura opt-in (bt_probe_retries=3 +
  skip_tx_on_rate_exceeded=1) e NADA mais;
- desenho da onda com as claims corrigidas pelo corretor (achados #2, #3 e
  #10: precedente do resume, escopo HZ=1000 e manifesto com o lote
  packaging).
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = REPO_ROOT / "assets" / "dkms" / "hid-nintendo"
DKMS_CONF_PATH = ASSET_DIR / "dkms.conf"
MAKEFILE_PATH = ASSET_DIR / "Makefile"
C_PATH = ASSET_DIR / "hid-nintendo.c"
HID_IDS_PATH = ASSET_DIR / "hid-ids.h"
PATCH_PATH = (
    ASSET_DIR / "patch" / "0001-HID-nintendo-do-not-transmit-after-rate-limit-exhaus.patch"
)
# Fix 21/07: 0002 registra os LEDs mesmo com o SET inicial falho (-110 em BT
# congestionado) — sem ele o controle fica sem LEDs de player pela conexão
# inteira. O invariante de paridade passa a ser a SEQUÊNCIA dos dois patches.
PATCH2_PATH = (
    ASSET_DIR / "patch" / "0002-HID-nintendo-register-leds-even-when-initial-set-fai.patch"
)
PATCH_PATHS = (PATCH_PATH, PATCH2_PATH)
BASELINE_PATH = ASSET_DIR / "patch" / "BASELINE"
MODPROBE_CONF_PATH = REPO_ROOT / "assets" / "modprobe.d" / "hefesto-hid-nintendo.conf"
DESENHO_PATH = (
    REPO_ROOT / "docs" / "process" / "estudos" / "2026-07-20-desenho-onda-t-patch-dkms.md"
)

SOB_ANONIMO = (
    "Signed-off-by: Hefesto DualSense4Unix Project "
    "<hefesto-dualsense4unix@users.noreply.github.com>"
)

PARAMS = (
    "input_report_wait_ms",
    "subcmd_rate_max_attempts",
    "sync_send_tries",
    "probe_info_timeout_ms",
    "bt_probe_retries",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


DKMS_CONF = _read(DKMS_CONF_PATH)
MAKEFILE = _read(MAKEFILE_PATH)
C = _read(C_PATH)
PATCH = _read(PATCH_PATH)
PATCH2 = _read(PATCH2_PATH)
PATCHES = (PATCH, PATCH2)
BASELINE = _read(BASELINE_PATH)
MODPROBE_CONF = _read(MODPROBE_CONF_PATH)
DESENHO = _read(DESENHO_PATH)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _baseline() -> dict[str, str]:
    dados: dict[str, str] = {}
    for linha in BASELINE.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        chave, _, valor = linha.partition("=")
        dados[chave] = valor
    return dados


def _baseline_patches() -> list[str]:
    """Linhas PATCH= do BASELINE, NA ORDEM (o dict de `_baseline` colapsa
    chaves repetidas; a ordem dos patches é parte do invariante)."""
    return [
        linha.strip().partition("=")[2]
        for linha in BASELINE.splitlines()
        if linha.strip().startswith("PATCH=")
    ]


def _funcao_c(assinatura: str) -> str:
    """Fatia do .c da assinatura dada até o início da próxima função
    top-level (`\\nstatic `) — suficiente para asserções de ordem."""
    ini = C.index(assinatura)
    fim = C.index("\nstatic ", ini + 1)
    return C[ini:fim]


def _aplica_um_patch(
    cwd: Path, reverso: bool, patch_path: Path
) -> subprocess.CompletedProcess[str]:
    """Aplica UM .patch em cwd (contra hid-nintendo.c local), com `patch`
    se existir, senão `git apply` — sem skip: sem nenhuma das duas
    ferramentas o teste FALHA (as duas são baseline de CI/dev)."""
    if shutil.which("patch"):
        cmd = ["patch", "-p3", "-s", "-i", str(patch_path)]
        if reverso:
            cmd.insert(1, "-R")
    else:
        cmd = ["git", "apply", "-p3", str(patch_path)]
        if reverso:
            cmd.insert(2, "-R")
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


def _aplica_serie(cwd: Path, reverso: bool) -> subprocess.CompletedProcess[str]:
    """Série completa: forward na ordem do BASELINE, reverso na inversa.
    Para no primeiro erro (returncode != 0)."""
    serie = tuple(reversed(PATCH_PATHS)) if reverso else PATCH_PATHS
    resultado = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    for patch_path in serie:
        resultado = _aplica_um_patch(cwd, reverso, patch_path)
        if resultado.returncode != 0:
            return resultado
    return resultado


class TestLayout:
    def test_manifesto_de_assets_completo(self) -> None:
        for path in (
            DKMS_CONF_PATH,
            MAKEFILE_PATH,
            C_PATH,
            HID_IDS_PATH,
            PATCH_PATH,
            BASELINE_PATH,
            MODPROBE_CONF_PATH,
        ):
            assert path.exists(), f"asset da Onda T ausente: {path.relative_to(REPO_ROOT)}"


class TestDkmsConf:
    def test_package_name(self) -> None:
        assert 'PACKAGE_NAME="hefesto-hid-nintendo"' in DKMS_CONF

    def test_package_version_declarada(self) -> None:
        match = re.search(r'^PACKAGE_VERSION="([^"]+)"$', DKMS_CONF, re.MULTILINE)
        assert match is not None, "PACKAGE_VERSION ausente no dkms.conf"
        assert re.fullmatch(r"\d+\.\d+\.\d+", match.group(1)), (
            "PACKAGE_VERSION precisa ser semver simples (rebase = bump)"
        )

    def test_built_module_name_e_o_mesmo_do_in_tree(self) -> None:
        # O nome do módulo NÃO muda (hid-nintendo): é isso que faz o
        # updates/dkms vencer o in-tree por precedência do depmod.
        assert 'BUILT_MODULE_NAME[0]="hid-nintendo"' in DKMS_CONF

    def test_dest_module_location_updates_dkms(self) -> None:
        assert 'DEST_MODULE_LOCATION[0]="/updates/dkms"' in DKMS_CONF

    def test_autoinstall_reconstrucao_em_update_de_kernel(self) -> None:
        assert 'AUTOINSTALL="yes"' in DKMS_CONF

    def test_make_e_clean_kbuild(self) -> None:
        make = re.search(r"^MAKE\[0\]=\"(.+)\"$", DKMS_CONF, re.MULTILINE)
        clean = re.search(r"^CLEAN=\"(.+)\"$", DKMS_CONF, re.MULTILINE)
        assert make is not None, "MAKE[0] ausente"
        assert clean is not None, "CLEAN ausente"
        assert "${kernel_source_dir}" in make.group(1)
        assert make.group(1).rstrip().endswith("modules")
        assert clean.group(1).rstrip().endswith("clean")


class TestMakefile:
    def test_obj_m_do_modulo(self) -> None:
        assert re.search(r"^obj-m\s*:=\s*hid-nintendo\.o$", MAKEFILE, re.MULTILINE)

    def test_config_nintendo_ff_sem_ele_o_rumble_some(self) -> None:
        assert re.search(
            r"^ccflags-y\s*:=.*-DCONFIG_NINTENDO_FF=1", MAKEFILE, re.MULTILINE
        ), "-DCONFIG_NINTENDO_FF=1 ausente — o in-tree tem CONFIG_NINTENDO_FF=y"


class TestModuleParamsC:
    """[C] do desenho: 5 params uint em 0644, defaults == vanilla."""

    def test_os_cinco_module_param_uint_0644(self) -> None:
        for nome in PARAMS:
            assert re.search(
                rf"^module_param\({nome}, uint, 0644\);$", C, re.MULTILINE
            ), f"module_param de {nome} ausente/errado"
            assert re.search(rf"^MODULE_PARM_DESC\({nome},$", C, re.MULTILINE), (
                f"MODULE_PARM_DESC de {nome} ausente"
            )

    def test_defaults_identicos_ao_vanilla(self) -> None:
        assert "static unsigned int input_report_wait_ms = 250;" in C
        assert "static unsigned int subcmd_rate_max_attempts = 25;" in C
        assert "static unsigned int sync_send_tries = 2;" in C
        assert "static unsigned int probe_info_timeout_ms = 2000;" in C

    def test_bt_probe_retries_default_zero_sem_inicializador(self) -> None:
        # default 0 (sem retry) == comportamento vanilla; a CURA (3) entra
        # só pela conf do modprobe.d — opt-in auditável e reversível.
        assert re.search(r"^static unsigned int bt_probe_retries;$", C, re.MULTILINE)

    def test_params_realmente_lidos_nos_pontos_certos(self) -> None:
        assert "msecs_to_jiffies(input_report_wait_ms)" in C
        assert "clamp_t(int, subcmd_rate_max_attempts, 1, 1000)" in C
        assert "clamp_t(int, sync_send_tries, 1, 10)" in C
        assert "msecs_to_jiffies(probe_info_timeout_ms)" in C
        assert "clamp_t(int, bt_probe_retries, 0, 10)" in C


class TestPatchBNaoTransmitirNoPiorMomento:
    """[B] do desenho: -EAGAIN ao esgotar; nenhum call-site transmite às cegas."""

    def test_enforce_virou_int_e_retorna_eagain(self) -> None:
        assert "static int joycon_enforce_subcmd_rate(struct joycon_ctlr *ctlr)" in C
        assert "static void joycon_enforce_subcmd_rate" not in C
        corpo = _funcao_c("static int joycon_enforce_subcmd_rate")
        assert "return -EAGAIN;" in corpo, "esgotou == -EAGAIN (não transmitir)"

    def test_skip_tx_e_gateado_por_param_default_vanilla(self) -> None:
        # Achado #1 do corretor: o skip-TX mudava comportamento observável
        # com TODOS os defaults, sem opt-out — a UX (rumble) mais sensível a
        # congestionamento BT do projeto. O gate devolve o default ao
        # vanilla (transmitir) e torna o skip opt-in/reversível via /sys.
        assert re.search(r"^static bool skip_tx_on_rate_exceeded;$", C, re.MULTILINE), (
            "param-gate ausente: default TEM de ser 0 (== vanilla, transmitir)"
        )
        assert re.search(
            r"^module_param\(skip_tx_on_rate_exceeded, bool, 0644\);$", C, re.MULTILINE
        ), "gate precisa ser ajustável AO VIVO (0644) p/ a validação A/B"
        corpo = _funcao_c("static int joycon_enforce_subcmd_rate")
        assert "if (skip_tx_on_rate_exceeded)\n\t\t\treturn -EAGAIN;" in corpo, (
            "o -EAGAIN só pode sair com o gate LIGADO; com ele desligado o "
            "fluxo cai no caminho vanilla (transmite como sempre)"
        )

    def test_patch_adiciona_o_gate_bool(self) -> None:
        assert "+module_param(skip_tx_on_rate_exceeded, bool, 0644);" in PATCH, (
            "o .patch precisa carregar o gate junto com o .c (invariante de rebase)"
        )

    def test_string_exceeded_preservada_byte_a_byte(self) -> None:
        # kernel-watch/doctor atuais casam nessa string — não pode mudar.
        assert 'hid_warn(ctlr->hdev, "%s: exceeded max attempts", __func__);' in C

    def test_send_sync_consome_a_try_sem_transmitir(self) -> None:
        corpo = _funcao_c("static int joycon_hid_send_sync")
        chamada = corpo.index("ret = joycon_enforce_subcmd_rate(ctlr);")
        envio = corpo.index("__joycon_hid_send")
        assert chamada < envio, "o rate-limit tem de ser consultado ANTES do TX"
        pulo = corpo[chamada:envio]
        assert "ret = -ETIMEDOUT;" in pulo, (
            "semântica externa preservada: chamador segue vendo -ETIMEDOUT"
        )
        assert "continue;" in pulo, "a try é consumida SEM transmitir"

    def test_rumble_dropa_o_pacote_em_vez_de_martelar(self) -> None:
        corpo = _funcao_c("static int joycon_send_rumble_data")
        chamada = corpo.index("ret = joycon_enforce_subcmd_rate(ctlr);")
        envio = corpo.index("__joycon_hid_send")
        assert chamada < envio
        assert "return ret;" in corpo[chamada:envio], (
            "sem janela segura o pacote de rumble é dropado (return -EAGAIN)"
        )

    def test_rumble_worker_silencia_o_drop(self) -> None:
        corpo = _funcao_c("static void joycon_rumble_worker")
        assert "ret != -EAGAIN" in corpo, (
            "sem isso cada drop viraria um 'Failed to set rumble; e=-11' espúrio"
        )


class TestPatchAProbeResiliente:
    """[A] do desenho: retry de probe SÓ em BT, backoff exponencial com teto."""

    def test_retry_condicionado_a_bluetooth(self) -> None:
        assert "if (ret && !joycon_using_usb(ctlr))" in C, (
            "por USB o transporte é confiável — a falha é significativa, sem retry"
        )

    def test_backoff_exponencial_com_teto_1600ms(self) -> None:
        corpo = _funcao_c("static int nintendo_hid_probe")
        assert "unsigned int backoff_ms = 100;" in corpo
        assert "backoff_ms *= 2;" in corpo
        assert "backoff_ms < 1600" in corpo

    def test_mensagem_do_retry_e_a_que_doctor_e_storm_watch_casam(self) -> None:
        assert '"init over bluetooth failed (%d); retrying (%d left)\\n"' in C


class TestBaselineEParidadeDoPatch:
    """Invariante de rebase: .c shipping == vanilla(BASELINE) + 0001-*.patch."""

    def test_baseline_tem_todas_as_chaves(self) -> None:
        dados = _baseline()
        assert dados.get("KERNEL_BASE") == "v7.0.11"
        assert dados.get("KERNEL_TESTED") == "7.0.11-76070011-generic"
        assert re.fullmatch(r"[0-9a-f]{40}", dados.get("POP_LINUX_COMMIT", "")), (
            "POP_LINUX_COMMIT precisa ser o sha do repo pop-os/linux"
        )
        for chave in ("SHA256_VANILLA_C", "SHA256_PATCHED_C", "SHA256_HID_IDS_H"):
            assert re.fullmatch(r"[0-9a-f]{64}", dados.get(chave, "")), f"{chave} inválido"
        assert _baseline_patches() == [p.name for p in PATCH_PATHS], (
            "as linhas PATCH= do BASELINE devem listar a série completa, na ordem"
        )

    def test_sha_do_c_shipping_bate_com_o_baseline(self) -> None:
        assert _sha256(C_PATH) == _baseline()["SHA256_PATCHED_C"], (
            "hid-nintendo.c divergiu do BASELINE — edição manual sem atualizar "
            "o .patch/BASELINE quebra o rebase e a submissão upstream"
        )

    def test_sha_do_hid_ids_intocado(self) -> None:
        assert _sha256(HID_IDS_PATH) == _baseline()["SHA256_HID_IDS_H"], (
            "hid-ids.h deve ser o do commit pop-os do BASELINE, intocado"
        )

    def test_patch_revertido_devolve_o_vanilla_exato(self, tmp_path: Path) -> None:
        trabalho = tmp_path / "rev"
        trabalho.mkdir()
        alvo = trabalho / "hid-nintendo.c"
        shutil.copy2(C_PATH, alvo)
        resultado = _aplica_serie(trabalho, reverso=True)
        assert resultado.returncode == 0, (
            f"patch -R não aplicou limpo: {resultado.stdout}{resultado.stderr}"
        )
        assert _sha256(alvo) == _baseline()["SHA256_VANILLA_C"], (
            "reverter a série não reproduz o vanilla v7.0.11 — o .c e os .patch "
            "divergiram (edite sempre os DOIS juntos)"
        )

    def test_patch_reaplicado_devolve_o_patchado_exato(self, tmp_path: Path) -> None:
        # Os dois sentidos: vanilla + série == shipping (rebase e upstream
        # partem daqui).
        trabalho = tmp_path / "fwd"
        trabalho.mkdir()
        alvo = trabalho / "hid-nintendo.c"
        shutil.copy2(C_PATH, alvo)
        assert _aplica_serie(trabalho, reverso=True).returncode == 0
        resultado = _aplica_serie(trabalho, reverso=False)
        assert resultado.returncode == 0, (
            f"patch forward não aplicou limpo: {resultado.stdout}{resultado.stderr}"
        )
        assert _sha256(alvo) == _baseline()["SHA256_PATCHED_C"]


class TestFormatoDoPatchUpstream:
    """T2.4: o mesmo arquivo serve rebase DKMS e submissão a linux-input."""

    def test_formato_git_format_patch(self) -> None:
        for corpo in PATCHES:
            assert corpo.startswith("From "), "precisa ser saída de git format-patch"
            assert "Subject: [PATCH] HID: nintendo:" in corpo

    def test_caminhos_do_kernel_tree(self) -> None:
        for corpo in PATCHES:
            assert "--- a/drivers/hid/hid-nintendo.c" in corpo
            assert "+++ b/drivers/hid/hid-nintendo.c" in corpo

    def test_signed_off_by_placeholder_anonimo(self) -> None:
        # Gate check_anonymity: o repo fica anônimo; a submissão real troca o
        # SoB (DCO exige pessoa) — decisão da mantenedora, fora do repo.
        for corpo in PATCHES:
            assert SOB_ANONIMO in corpo

    def test_adiciona_exatamente_os_cinco_module_param(self) -> None:
        adicionados = re.findall(r"^\+module_param\((\w+), uint, 0644\);$", PATCH, re.MULTILINE)
        assert sorted(adicionados) == sorted(PARAMS)

    def test_0002_adiciona_o_param_bool_dos_leds(self) -> None:
        assert re.search(
            r"^\+module_param\(register_leds_on_set_failure, bool, 0644\);$",
            PATCH2,
            re.MULTILINE,
        ), "0002 adiciona o opt-in register_leds_on_set_failure (default N == vanilla)"

    def test_nao_remove_a_string_exceeded(self) -> None:
        for corpo in PATCHES:
            for linha in corpo.splitlines():
                if linha.startswith("-") and not linha.startswith("---"):
                    assert "exceeded max attempts" not in linha, (
                        "o patch não pode remover/alterar a string que o "
                        "kernel-watch/doctor casam"
                    )


class TestModprobeConf:
    def test_cura_opt_in_completa(self) -> None:
        # As pontas da cura são opt-in daqui (defaults do módulo == vanilla):
        # retry de probe BT + não-transmitir após exceeded + registrar LEDs
        # com SET inicial falho (fix 21/07 — medido: -110 no probe deixava o
        # Pro Controller sem LEDs de player pela conexão inteira).
        assert re.search(
            r"^options hid_nintendo bt_probe_retries=3 skip_tx_on_rate_exceeded=1"
            r" register_leds_on_set_failure=1"
            r" sync_send_tries=4 input_report_wait_ms=500 probe_info_timeout_ms=4000$",
            MODPROBE_CONF,
            re.MULTILINE,
        ), "a cura entra pela conf: retries + skip_tx + regleds + tuning BT medido"

    def test_conf_documenta_o_opt_out_a_quente_do_skip(self) -> None:
        assert "echo 0" in MODPROBE_CONF and "skip_tx_on_rate_exceeded" in MODPROBE_CONF, (
            "a conf documenta a reversão AO VIVO (validação A/B da onda usa esse knob)"
        )

    def test_tuning_persistido_e_medido_e_documentado(self) -> None:
        # Decisão 21/07 (supersede "só a cura, nada de tuning" da Onda T):
        # com 4 controles BT o rádio congestionado derrubou o probe (13x
        # timeout + -110); os limiares maiores SÃO parte da cura e ficam
        # persistidos — mas cada um precisa estar JUSTIFICADO no comentário
        # da conf (sem números órfãos) e reversível ao vivo via /sys.
        linhas_options = [
            linha
            for linha in MODPROBE_CONF.splitlines()
            if linha.strip().startswith("options ")
        ]
        assert len(linhas_options) == 1, "uma única linha options"
        for nome in ("sync_send_tries", "input_report_wait_ms", "probe_info_timeout_ms"):
            assert nome in linhas_options[0], f"{nome} faz parte da cura BT medida"
            assert MODPROBE_CONF.count(nome) >= 2, (
                f"{nome} precisa de justificativa em comentário, não só o valor"
            )
        assert "subcmd_rate_max_attempts" not in linhas_options[0], (
            "subcmd_rate_max_attempts segue no default (== vanilla) — sem medição"
        )


class TestDesenhoClaimsCorrigidas:
    """Achados #2/#3/#10 do corretor: claims do desenho que eram falsas ou
    generalizadas demais — corrigidas ANTES de qualquer submissão upstream."""

    def test_desenho_existe(self) -> None:
        assert DESENHO, "desenho da Onda T ausente"

    def test_precedente_do_resume_corrigido_para_bt(self) -> None:
        # Achado #2: o resume vanilla re-chama joycon_init() SÓ no ramo USB;
        # em BT é no-op explícito — o precedente citado p/ justificar o retry
        # BT não existia. O desenho precisa carregar o argumento corrigido.
        assert "SÓ NO RAMO USB" in DESENHO, (
            "a justificativa de idempotência não pode citar o resume como "
            "precedente BT (nintendo_hid_resume é no-op para bluetooth)"
        )
        assert "no-op resume for bt ctlr" in DESENHO, (
            "o desenho cita a evidência literal do no-op BT do resume"
        )

    def test_claim_de_equivalencia_escopada_a_hz_1000(self) -> None:
        # Achado #3: msecs_to_jiffies arredonda p/ CIMA e HZ/4 trunca — em
        # HZ=250 o input_report_wait diverge 1 jiffy do vanilla. A claim de
        # equivalência exata vale SÓ p/ HZ=1000 e o desenho diz isso.
        assert "VÁLIDA SÓ PARA HZ=1000" in DESENHO
        assert "HZ=250" in DESENHO, (
            "o desenho documenta a divergência de arredondamento p/ HZ != 1000 "
            "(reuso do padrão pela Onda W exige re-verificação por kernel)"
        )

    def test_manifesto_inclui_o_lote_packaging(self) -> None:
        # Achado #10: a implementação tocou 5 arquivos de packaging fora do
        # manifesto original (exigência do gate check_packaging_parity.sh).
        for trecho in (
            "check_packaging_parity.sh",
            "packaging/fedora/hefesto-dualsense4unix.spec",
            "scripts/install-host-udev.sh",
            "flatpak/br.andrefarias.Hefesto.yml",
            "packaging/arch/PKGBUILD",
            "scripts/build_deb.sh",
        ):
            assert trecho in DESENHO, f"manifesto do desenho sem o arquivo tocado: {trecho}"
