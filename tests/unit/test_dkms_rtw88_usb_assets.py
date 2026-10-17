"""Onda W — assets DKMS do rtw88_usb patchado (fantasma USB do dongle WiFi)."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = REPO_ROOT / "assets" / "dkms" / "rtw88-usb"
DKMS_CONF_PATH = ASSET_DIR / "dkms.conf"
MAKEFILE_PATH = ASSET_DIR / "Makefile"
C_PATH = ASSET_DIR / "usb.c"
H_PATH = ASSET_DIR / "usb.h"
PATCH1_PATH = (
    ASSET_DIR / "patch" / "0001-wifi-rtw88-usb-fix-memory-leaks-on-USB-write-failures.patch"
)
PATCH2_PATH = (
    ASSET_DIR / "patch" / "0002-wifi-rtw88-usb-detect-device-gone-and-queue-port-reset.patch"
)
BASELINE_PATH = ASSET_DIR / "patch" / "BASELINE"

SOB_ANONIMO = (
    "Signed-off-by: Hefesto DualSense4Unix Project "
    "<hefesto-dualsense4unix@users.noreply.github.com>"
)

HEADERS_VANILLA = (
    "debug.h",
    "mac.h",
    "reg.h",
    "tx.h",
    "rx.h",
    "fw.h",
    "ps.h",
    "util.h",
    "hci.h",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


DKMS_CONF = _read(DKMS_CONF_PATH)
MAKEFILE = _read(MAKEFILE_PATH)
C = _read(C_PATH)
H = _read(H_PATH)
PATCH1 = _read(PATCH1_PATH)
PATCH2 = _read(PATCH2_PATH)
BASELINE = _read(BASELINE_PATH)


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


def _funcao_c(assinatura: str) -> str:
    """Fatia do usb.c da assinatura dada até o início da próxima função"""
    ini = C.index(assinatura)
    while C[ini : C.index("\n", ini)].rstrip().endswith(";"):
        ini = C.index(assinatura, ini + 1)
    fim = C.index("\nstatic ", ini + 1)
    return C[ini:fim]


def _aplica_patch(cwd: Path, patch_path: Path, reverso: bool) -> None:
    """Aplica o patch (-p6, caminhos a/drivers/net/wireless/realtek/rtw88/*)"""
    if shutil.which("patch"):
        cmd = ["patch", "-p6", "-s", "-i", str(patch_path)]
        if reverso:
            cmd.insert(1, "-R")
    else:
        cmd = ["git", "apply", "-p6", str(patch_path)]
        if reverso:
            cmd.insert(2, "-R")
    resultado = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    assert resultado.returncode == 0, (
        f"{patch_path.name} ({'-R' if reverso else 'forward'}) não aplicou limpo: "
        f"{resultado.stdout}{resultado.stderr}"
    )


def _monta_arvore(tmp_path: Path) -> Path:
    trabalho = tmp_path / "rtw88"
    trabalho.mkdir()
    shutil.copy2(C_PATH, trabalho / "usb.c")
    shutil.copy2(H_PATH, trabalho / "usb.h")
    return trabalho


def _reverte_para_vanilla(trabalho: Path) -> None:
    _aplica_patch(trabalho, PATCH2_PATH, reverso=True)
    _aplica_patch(trabalho, PATCH1_PATH, reverso=True)


class TestLayout:
    def test_manifesto_de_assets_completo(self) -> None:
        arquivos = [DKMS_CONF_PATH, MAKEFILE_PATH, C_PATH, H_PATH, ASSET_DIR / "README.md"]
        arquivos += [ASSET_DIR / nome for nome in HEADERS_VANILLA]
        arquivos += [PATCH1_PATH, PATCH2_PATH, BASELINE_PATH]
        for path in arquivos:
            assert path.exists(), f"asset da Onda W ausente: {path.relative_to(REPO_ROOT)}"


class TestDkmsConf:
    def test_package_name(self) -> None:
        assert 'PACKAGE_NAME="hefesto-rtw88-usb"' in DKMS_CONF

    def test_package_version_declarada(self) -> None:
        match = re.search(r'^PACKAGE_VERSION="([^"]+)"$', DKMS_CONF, re.MULTILINE)
        assert match is not None, "PACKAGE_VERSION ausente no dkms.conf"
        assert re.fullmatch(r"\d+\.\d+\.\d+", match.group(1)), (
            "PACKAGE_VERSION precisa ser semver simples (rebase = bump)"
        )

    def test_built_module_name_e_o_mesmo_do_in_tree(self) -> None:
        assert 'BUILT_MODULE_NAME[0]="rtw88_usb"' in DKMS_CONF

    def test_dest_module_location_updates_dkms(self) -> None:
        assert 'DEST_MODULE_LOCATION[0]="/updates/dkms"' in DKMS_CONF

    def test_autoinstall_reconstrucao_em_update_de_kernel(self) -> None:
        assert 'AUTOINSTALL="yes"' in DKMS_CONF

    def test_pino_de_abi_build_exclusive_kernel(self) -> None:
        pino = re.search(r'^BUILD_EXCLUSIVE_KERNEL="(.+)"$', DKMS_CONF, re.MULTILINE)
        assert pino is not None, "BUILD_EXCLUSIVE_KERNEL ausente"
        for build in _baseline()["KERNELS_VALIDADOS"].split():
            assert build.replace(".", "\\.") in pino.group(1), (
                f"o build validado {build} não está no BUILD_EXCLUSIVE_KERNEL — "
                f"o dkms vai PULAR um kernel que a BASELINE diz ter sido medido"
            )
        assert all(b in pino.group(1) for b in ("76070011", "76070105", "76070206")), (
            "o pino tem de casar o BUILD exato; só a versão nominal deixa um "
            "respin da mesma versão corromper memória silenciosamente"
        )

    def test_a_regex_do_pino_e_a_baseline_dizem_o_mesmo(self) -> None:
        """Os dois sentidos: build na regex sem estar em KERNELS_VALIDADOS ninguém mediu."""
        pino = re.search(r'^BUILD_EXCLUSIVE_KERNEL="(.+)"$', DKMS_CONF, re.MULTILINE)
        assert pino is not None, "BUILD_EXCLUSIVE_KERNEL ausente"
        forma = re.fullmatch(r"\^\(?(.+?)\)?-", pino.group(1))
        assert forma, "o pino perdeu a forma `^(build|build)-`"
        na_regex = {alt.replace("\\.", ".") for alt in forma.group(1).split("|")}
        assert na_regex == set(_baseline()["KERNELS_VALIDADOS"].split())

    def test_o_pre_build_escolhe_o_main_do_kernel_alvo(self) -> None:
        """Sem ele, o `main.h` do build ANTERIOR fica — e é a corrupção."""
        assert 'PRE_BUILD="./escolher-o-main.sh $kernelver"' in DKMS_CONF, (
            "o PRE_BUILD sumiu — o build vai usar o `main.h` que estiver na "
            "pasta, e um `main.h` de outro kernel corrompe memória sem avisar"
        )
        escolhedor = ASSET_DIR / "escolher-o-main.sh"
        assert escolhedor.is_file(), f"{escolhedor} não existe"
        assert escolhedor.stat().st_mode & 0o111, "o escolhedor não é executável"

    def test_todo_kernel_validado_tem_o_main_dele(self) -> None:
        """A lista da BASELINE e os arquivos em disco, nos DOIS sentidos."""
        dados = _baseline()
        pasta = ASSET_DIR / "main-por-kernel"
        em_disco = {p.name[len("main-"):-len(".h")] for p in pasta.glob("main-*.h")}
        declarados = set(dados["KERNELS_VALIDADOS"].split())
        assert declarados == em_disco, (
            f"a BASELINE declara {sorted(declarados)} e a pasta tem "
            f"{sorted(em_disco)} — um kernel sem `main.h` faz o PRE_BUILD "
            f"recusar; um `main.h` sem declaração é ABI que ninguém mediu"
        )
        for build in declarados:
            chave = "SHA256_MAIN_" + build.replace(".", "_").replace("-", "_")
            assert _sha256(pasta / f"main-{build}.h") == dados.get(chave), (
                f"o `main.h` de {build} não bate com {chave} — ou o arquivo foi "
                f"editado, ou o sha não foi atualizado no mesmo commit"
            )

    def test_make_e_clean_kbuild(self) -> None:
        make = re.search(r"^MAKE\[0\]=\"(.+)\"$", DKMS_CONF, re.MULTILINE)
        clean = re.search(r"^CLEAN=\"(.+)\"$", DKMS_CONF, re.MULTILINE)
        assert make is not None, "MAKE[0] ausente"
        assert clean is not None, "CLEAN ausente"
        assert "${kernel_source_dir}" in make.group(1)
        assert make.group(1).rstrip().endswith("modules")
        assert clean.group(1).rstrip().endswith("clean")


class TestMakefile:
    def test_kbuild_minimo_de_duas_linhas(self) -> None:
        linhas = [
            linha
            for linha in MAKEFILE.splitlines()
            if linha.strip() and not linha.lstrip().startswith("#")
        ]
        assert linhas == ["obj-m := rtw88_usb.o", "rtw88_usb-objs := usb.o"], (
            "Makefile precisa ser o kbuild mínimo do desenho (2 linhas); os "
            "CONFIG_RTW88_* vêm do autoconf.h do kernel alvo, nunca daqui"
        )


class TestDeviceGoneEDecisaoEproto:
    """§1.1/§1.2 do desenho: os hunks-chave do 0002 no .c shipping."""

    def test_hang_reset_param_bool_0644_default_y(self) -> None:
        assert "static bool rtw_usb_hang_reset = true;" in C, "default TEM de ser Y"
        assert "module_param_named(hang_reset, rtw_usb_hang_reset, bool, 0644);" in C, (
            "0644: precisa ser ajustável AO VIVO (uninstall devolve a 0 via /sys)"
        )

    def test_limiar_igual_ao_rtw89(self) -> None:
        assert re.search(
            r"^#define RTW_USB_MAX_CONTINUAL_IO_ERR\t4$", C, re.MULTILINE
        ), "limiar do contador = 4 (mesmo do rtw89 2135c28be6a8)"

    def test_device_gone_arma_uma_vez_e_reset_gateado(self) -> None:
        corpo = _funcao_c("static void rtw_usb_device_gone(struct rtw_usb *rtwusb)")
        armada = corpo.index("test_and_set_bit(RTW_USB_FLAG_DEVICE_GONE, rtwusb->flags)")
        reset = corpo.index("usb_queue_reset_device(rtwusb->intf);")
        assert armada < reset, (
            "test_and_set_bit ANTES do reset: UM reset por armada, sem tempestade"
        )
        assert "if (rtw_usb_hang_reset)\n\t\tusb_queue_reset_device(rtwusb->intf);" in corpo, (
            "o usb_queue_reset_device só pode disparar com hang_reset=Y"
        )

    def test_enodev_eshutdown_armam_imediato(self) -> None:
        corpo = _funcao_c("static void rtw_usb_io_error(struct rtw_usb *rtwusb, int error)")
        imediato = corpo.index("error == -ENODEV || error == -ESHUTDOWN")
        contador = corpo.index("atomic_inc_return(&rtwusb->continual_io_error)")
        assert imediato < contador, "o ramo definitivo vem ANTES do contador"

    def test_eproto_nunca_arma_direto_so_via_contador(self) -> None:
        corpo = _funcao_c("static void rtw_usb_io_error(struct rtw_usb *rtwusb, int error)")
        assert "EPROTO" not in re.sub(r"/\*.*?\*/", "", corpo, flags=re.DOTALL), (
            "-EPROTO não pode armar device_gone por match de errno — só o contador"
        )
        assert (
            "atomic_inc_return(&rtwusb->continual_io_error) >\n"
            "\t    RTW_USB_MAX_CONTINUAL_IO_ERR" in corpo
        ), "transitórios só armam via contador > RTW_USB_MAX_CONTINUAL_IO_ERR"

    def test_qualquer_sucesso_zera_o_contador(self) -> None:
        corpo = _funcao_c("static void rtw_usb_io_ok(struct rtw_usb *rtwusb)")
        assert "atomic_set(&rtwusb->continual_io_error, 0);" in corpo, (
            "rajada de EMI de 1-4 erros nunca arma: qualquer transferência boa zera"
        )

    def test_rx_complete_classifica_cada_familia_de_erro(self) -> None:
        corpo = _funcao_c("static void rtw_usb_read_port_complete(struct urb *urb)")
        assert (
            "case -ENODEV:\n\t\tcase -ESHUTDOWN:\n\t\t\trtw_usb_device_gone(rtwusb);" in corpo
        ), "device sumiu de verdade → arma imediato"
        assert (
            "case -EPROTO:\n\t\tcase -EILSEQ:\n\t\tcase -ETIME:\n\t\tcase -ECOMM:\n"
            "\t\tcase -EOVERFLOW:\n\t\t\trtw_usb_io_error(rtwusb, urb->status);" in corpo
        ), "família transitória → só o contador"
        assert (
            "case -EINVAL:\n\t\tcase -EPIPE:\n\t\tcase -ENOENT:\n\t\tcase -EINPROGRESS:\n"
            "\t\t\tbreak;" in corpo
        ), (
            "-ENOENT = URB morto pelo PRÓPRIO teardown — contar aqui armaria "
            "device_gone em todo unbind normal (falso-positivo de projeto)"
        )

    def test_write_port_early_return_e_submit_enodev(self) -> None:
        corpo = _funcao_c("static int rtw_usb_write_port(")
        assert (
            "if (test_bit(RTW_USB_FLAG_DEVICE_GONE, rtwusb->flags))\n\t\treturn -ENODEV;"
            in corpo
        ), "TX contra device morto early-returna (o 0001 garante que o chamador libera)"
        assert "if (ret == -ENODEV)\n\t\trtw_usb_device_gone(rtwusb);" in corpo, (
            "usb_submit_urb == -ENODEV → device_gone (paridade rtw89)"
        )

    def test_leitura_devolve_zero_deterministico_nunca_lixo(self) -> None:
        corpo = _funcao_c("static u32 rtw_usb_read(")
        assert "*data = 0;" in corpo, "falha de leitura = valor determinístico 0"
        assert "rtw_usb_io_error(rtwusb, ret);" in corpo
        assert "rtw_usb_io_ok(rtwusb);" in corpo

    def test_reg_sec_early_return_mata_a_duplicacao_do_flood(self) -> None:
        corpo = _funcao_c("static void rtw_usb_reg_sec(")
        assert "if (test_bit(RTW_USB_FLAG_DEVICE_GONE, rtwusb->flags))\n\t\treturn;" in corpo, (
            "cada acesso on-section duplicava a escrita no reg 0x4e0 contra "
            "hardware morto — o early-return corta a duplicação do flood"
        )

    def test_intf_guardado_no_init(self) -> None:
        assert "rtwusb->intf = intf;" in C, (
            "sem o intf salvo não há usb_queue_reset_device(rtwusb->intf)"
        )


class TestBackportMemleak0001:
    """0001 é PRÉ-REQUISITO do 0002: sem ele o early-return -ENODEV no TX"""

    def test_tx_agg_skb_libera_txcb_quando_submit_falha(self) -> None:
        corpo = _funcao_c("static bool rtw_usb_tx_agg_skb(")
        assert "ieee80211_purge_tx_queue(rtwdev->hw, &txcb->tx_ack_queue);" in corpo
        assert "kfree(txcb);" in corpo
        assert "return false;" in corpo

    def test_write_data_libera_skb_quando_submit_falha(self) -> None:
        corpo = _funcao_c("static int rtw_usb_write_data(struct rtw_dev *rtwdev,")
        assert "dev_kfree_skb_any(skb);" in corpo

    def test_patch_0001_e_o_upstream_verbatim(self) -> None:
        assert PATCH1.startswith("From 6b964941bbfe"), (
            "0001 precisa ser o commit upstream 6b964941bbfe (verbatim, offsets só)"
        )
        assert "Subject: [PATCH 1/2] wifi: rtw88: usb: fix memory leaks" in PATCH1
        assert "Fixes: a82dfd33d123" in PATCH1
        assert "Cc: stable@vger.kernel.org" in PATCH1
        assert "CVE-2026-63821" in PATCH1


class TestStringsDeLogPreservadas:
    """kernel-watch/doctor atuais casam nessas strings — não podem mudar."""

    def test_strings_de_erro_de_registrador_byte_a_byte(self) -> None:
        assert 'rtw_err(rtwdev, "read register 0x%x failed with %d\\n",' in C
        assert 'rtw_err(rtwdev, "write register 0x%x failed with %d\\n",' in C
        assert '"%s: reg 0x%x, usb write %u fail, status: %d\\n"' in C

    def test_patch_0002_readiciona_toda_string_que_toca(self) -> None:
        removidas = [
            linha[1:]
            for linha in PATCH2.splitlines()
            if linha.startswith("-") and not linha.startswith("---")
        ]
        adicionadas = [
            linha[1:]
            for linha in PATCH2.splitlines()
            if linha.startswith("+") and not linha.startswith("+++")
        ]
        for alvo in (
            "read register 0x%x failed with %d",
            "write register 0x%x failed with %d",
            "usb write %u fail",
        ):
            n_removidas = sum(alvo in linha for linha in removidas)
            n_adicionadas = sum(alvo in linha for linha in adicionadas)
            assert n_adicionadas >= n_removidas, (
                f"o 0002 remove a string {alvo!r} sem readicioná-la — "
                "kernel-watch/doctor atuais deixariam de casar"
            )


class TestUsbH:
    def test_estado_novo_local_ao_modulo(self) -> None:
        assert "RTW_USB_FLAG_DEVICE_GONE," in H
        assert "NUM_OF_RTW_USB_FLAGS," in H
        assert "DECLARE_BITMAP(flags, NUM_OF_RTW_USB_FLAGS);" in H
        assert "atomic_t continual_io_error;" in H
        assert "struct usb_interface *intf;" in H


class TestBaselineEParidadeDosPatches:
    """Invariante de rebase: shipping == vanilla(BASELINE) + 0001 + 0002."""

    def test_baseline_tem_todas_as_chaves(self) -> None:
        dados = _baseline()
        assert dados.get("KERNEL_BASE") == "v7.0.11"
        assert dados.get("KERNEL_TESTED") == "7.0.11-76070011-generic"
        assert dados.get("KERNEL_TESTED_2") == "7.1.5-76070105-generic"
        assert dados.get("KERNEL_TESTED_3") == "7.2.6-76070206-generic"
        assert dados.get("KERNELS_VALIDADOS", "").split() == [
            "7.0.11-76070011", "7.1.5-76070105", "7.2.6-76070206",
        ]
        assert re.fullmatch(r"[0-9a-f]{40}", dados.get("POP_LINUX_COMMIT", "")), (
            "POP_LINUX_COMMIT precisa ser o sha do repo pop-os/linux"
        )
        for chave in (
            "SHA256_VANILLA_C",
            "SHA256_VANILLA_H",
            "SHA256_PATCHED_C",
            "SHA256_PATCHED_H",
            "SHA256_HEADERS_BUNDLE",
            "SHA256_VANILLA_C_7_0_11",
            "SHA256_VANILLA_C_7_1_5",
            "SHA256_MAIN_7_0_11_76070011",
            "SHA256_MAIN_7_1_5_76070105",
            "SHA256_MAIN_7_2_6_76070206",
            "SHA256_VANILLA_C_7_2_6",
            "SHA256_PATCHED_C_7_2_6",
            "SHA256_RX_H_7_2_6",
            "SHA256_HEADERS_BUNDLE_7_2_6",
        ):
            assert re.fullmatch(r"[0-9a-f]{64}", dados.get(chave, "")), f"{chave} inválido"
        assert re.fullmatch(r"[0-9a-f]{40}", dados.get("POP_LINUX_COMMIT_7_2_6", ""))
        for chave in ("CRC_RTW_USB_PROBE_7_2_6", "CRC_RTW_USB_DISCONNECT_7_2_6"):
            assert re.fullmatch(r"0x[0-9a-f]{8}", dados.get(chave, "")), f"{chave} inválido"
        assert dados.get("PATCH_1") == PATCH1_PATH.name
        assert dados.get("PATCH_2") == PATCH2_PATH.name

    def test_modelo_rtw89_registrado(self) -> None:
        dados = _baseline()
        assert "2135c28be6a8" in dados.get("MODELO_0002", ""), (
            "a proveniência do padrão portado (rtw89) fica gravada no BASELINE"
        )

    def test_sha_do_c_e_h_shipping_batem_com_o_baseline(self) -> None:
        dados = _baseline()
        assert _sha256(C_PATH) == dados["SHA256_PATCHED_C"], (
            "usb.c divergiu do BASELINE — edição manual sem atualizar os "
            ".patch/BASELINE quebra o rebase e a submissão upstream"
        )
        assert _sha256(H_PATH) == dados["SHA256_PATCHED_H"], "usb.h divergiu do BASELINE"

    def test_bundle_dos_headers_vanilla_intocados(self) -> None:
        resultado = subprocess.run(
            ["bash", "-c", f"sha256sum {' '.join(HEADERS_VANILLA)} | sha256sum"],
            cwd=ASSET_DIR,
            capture_output=True,
            text=True,
            check=False,
        )
        assert resultado.returncode == 0, resultado.stderr
        assert resultado.stdout.split()[0] == _baseline()["SHA256_HEADERS_BUNDLE"], (
            "um header vanilla foi tocado — eles só existem no pacote porque o "
            "linux-headers não os traz; mudança neles é rebase, não edição"
        )

    def test_o_main_h_nao_e_versionado(self) -> None:
        """Uma cópia versionada é uma SEGUNDA verdade sobre qual ABI é a nossa."""
        resultado = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "assets/dkms/rtw88-usb/main.h"],
            cwd=ASSET_DIR.parents[2], capture_output=True, text=True, check=False,
        )
        assert resultado.returncode != 0, (
            "`assets/dkms/rtw88-usb/main.h` voltou para o git. Ele é DERIVADO: "
            "as fontes são `main-por-kernel/main-<build>.h`, e quem escolhe é o "
            "`escolher-o-main.sh` no PRE_BUILD."
        )

    def test_patches_revertidos_devolvem_o_vanilla_exato(self, tmp_path: Path) -> None:
        trabalho = _monta_arvore(tmp_path)
        _reverte_para_vanilla(trabalho)
        dados = _baseline()
        assert _sha256(trabalho / "usb.c") == dados["SHA256_VANILLA_C"], (
            "reverter 0002+0001 não reproduz o usb.c vanilla v7.0.11 — o .c e "
            "os .patch divergiram (edite sempre os dois lados juntos)"
        )
        assert _sha256(trabalho / "usb.h") == dados["SHA256_VANILLA_H"], (
            "reverter 0002 não reproduz o usb.h vanilla v7.0.11"
        )

    def test_patches_reaplicados_devolvem_o_shipping_exato(self, tmp_path: Path) -> None:
        trabalho = _monta_arvore(tmp_path)
        _reverte_para_vanilla(trabalho)
        _aplica_patch(trabalho, PATCH1_PATH, reverso=False)
        _aplica_patch(trabalho, PATCH2_PATH, reverso=False)
        dados = _baseline()
        assert _sha256(trabalho / "usb.c") == dados["SHA256_PATCHED_C"]
        assert _sha256(trabalho / "usb.h") == dados["SHA256_PATCHED_H"]


class TestFormatoDoPatch0002Upstream:
    """O mesmo arquivo serve rebase DKMS e submissão a wireless-next."""

    def test_formato_git_format_patch(self) -> None:
        assert PATCH2.startswith("From "), "precisa ser saída de git format-patch"
        assert "Subject: [PATCH 2/2] wifi: rtw88: usb: detect device gone" in PATCH2

    def test_caminhos_do_kernel_tree(self) -> None:
        assert "--- a/drivers/net/wireless/realtek/rtw88/usb.c" in PATCH2
        assert "+++ b/drivers/net/wireless/realtek/rtw88/usb.c" in PATCH2
        assert "--- a/drivers/net/wireless/realtek/rtw88/usb.h" in PATCH2
        assert "+++ b/drivers/net/wireless/realtek/rtw88/usb.h" in PATCH2

    def test_signed_off_by_placeholder_anonimo(self) -> None:
        assert SOB_ANONIMO in PATCH2

    def test_patch_adiciona_o_gate_e_o_reset(self) -> None:
        assert "+module_param_named(hang_reset, rtw_usb_hang_reset, bool, 0644);" in PATCH2, (
            "o .patch precisa carregar o gate junto com o .c (invariante de rebase)"
        )
        assert "usb_queue_reset_device" in PATCH2


KERNEL_726 = "7.2.6-76070206"
POR_KERNEL = ASSET_DIR / "fonte-por-kernel"
PASTA_726 = POR_KERNEL / KERNEL_726
PATCH2_726_PATH = PASTA_726 / "patch" / PATCH2_PATH.name


def _copia_do_pacote(destino: Path) -> Path:
    """O pacote como o DKMS o entrega ao build: a pasta inteira, sem o `main.h` derivado."""
    alvo = destino / "pacote"
    shutil.copytree(ASSET_DIR, alvo)
    (alvo / "main.h").unlink(missing_ok=True)
    return alvo


def _escolhe(pacote: Path, kernelver: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(pacote / "escolher-o-main.sh"), kernelver],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


class TestOFontePorKernel:
    """O 7.2.6 mudou o `usb.c` e o `rx.h` de fábrica: cada kernel recebe o fonte DELE."""

    def test_a_raiz_as_pastas_e_a_baseline_dizem_o_mesmo(self) -> None:
        validados = set(_baseline()["KERNELS_VALIDADOS"].split())
        da_raiz = set(_read(POR_KERNEL / "raiz.txt").split())
        em_pastas = {p.name for p in POR_KERNEL.iterdir() if p.is_dir()}
        assert not da_raiz & em_pastas, "um build não serve da raiz e de uma pasta ao mesmo tempo"
        assert da_raiz | em_pastas == validados, (
            f"a BASELINE declara {sorted(validados)}; `raiz.txt` + pastas dizem "
            f"{sorted(da_raiz | em_pastas)} — kernel sem fonte faz o PRE_BUILD recusar, "
            "e fonte sem declaração é ABI que ninguém mediu"
        )

    def test_o_fonte_do_7_2_6_e_o_patchado_do_baseline(self) -> None:
        dados = _baseline()
        assert _sha256(PASTA_726 / "usb.c") == dados["SHA256_PATCHED_C_7_2_6"]
        assert _sha256(PASTA_726 / "rx.h") == dados["SHA256_RX_H_7_2_6"]
        assert _sha256(PASTA_726 / "rx.h") != _sha256(ASSET_DIR / "rx.h"), (
            "o `rx.h` do 7.2.6 é o mesmo da raiz: a pasta por kernel não teria razão de ser"
        )

    def test_os_outros_oito_headers_do_7_2_6_sao_os_da_raiz(self) -> None:
        """O bundle do 7.2.6 = os oito invariantes da raiz + o `rx.h` dele."""
        arvore = {nome: ASSET_DIR / nome for nome in HEADERS_VANILLA}
        arvore["rx.h"] = PASTA_726 / "rx.h"
        resumo = "".join(f"{_sha256(arvore[n])}  {n}\n" for n in HEADERS_VANILLA)
        assert hashlib.sha256(resumo.encode()).hexdigest() == (
            _baseline()["SHA256_HEADERS_BUNDLE_7_2_6"]
        ), "um header do 7.2.6 divergiu: mudança neles é rebase, não edição"

    def test_o_patch_do_7_2_6_desfeito_devolve_o_de_fabrica(self, tmp_path: Path) -> None:
        trabalho = tmp_path / "rtw88"
        trabalho.mkdir()
        shutil.copy2(PASTA_726 / "usb.c", trabalho / "usb.c")
        shutil.copy2(H_PATH, trabalho / "usb.h")
        _aplica_patch(trabalho, PATCH2_726_PATH, reverso=True)
        dados = _baseline()
        assert _sha256(trabalho / "usb.c") == dados["SHA256_VANILLA_C_7_2_6"], (
            "reverter o 0002 do 7.2.6 não reproduz o usb.c de fábrica dele"
        )
        assert _sha256(trabalho / "usb.h") == dados["SHA256_VANILLA_H"]
        _aplica_patch(trabalho, PATCH2_726_PATH, reverso=False)
        assert _sha256(trabalho / "usb.c") == dados["SHA256_PATCHED_C_7_2_6"]
        assert _sha256(trabalho / "usb.h") == dados["SHA256_PATCHED_H"]

    def test_o_7_2_6_nao_traz_o_0001_que_o_de_fabrica_ja_tem(self) -> None:
        assert sorted(p.name for p in (PASTA_726 / "patch").iterdir()) == [PATCH2_PATH.name]

    def test_o_patch_do_7_2_6_tem_o_formato_do_0002(self) -> None:
        texto = PATCH2_726_PATH.read_text(encoding="utf-8")
        assert texto.startswith("From ")
        assert "Subject: [PATCH 2/2] wifi: rtw88: usb: detect device gone" in texto
        assert SOB_ANONIMO in texto
        assert "+module_param_named(hang_reset, rtw_usb_hang_reset, bool, 0644);" in texto

    def test_o_usb_c_do_7_2_6_consome_o_retorno_novo_do_rx(self) -> None:
        """A razão da pasta: o de fábrica do 7.2.6 testa o `int` de `rtw_rx_query_rx_desc`."""
        c = (PASTA_726 / "usb.c").read_text(encoding="utf-8")
        rx = (PASTA_726 / "rx.h").read_text(encoding="utf-8")
        assert "ret = rtw_rx_query_rx_desc(" in c
        assert "int rtw_rx_query_rx_desc(" in rx
        assert "void rtw_rx_query_rx_desc(" in (ASSET_DIR / "rx.h").read_text(encoding="utf-8")

    def test_o_escolhedor_poe_o_fonte_de_cada_kernel_validado(self, tmp_path: Path) -> None:
        dados = _baseline()
        da_raiz = set(_read(POR_KERNEL / "raiz.txt").split())
        for build in dados["KERNELS_VALIDADOS"].split():
            pacote = _copia_do_pacote(tmp_path / build)
            resultado = _escolhe(pacote, f"{build}-generic")
            assert resultado.returncode == 0, resultado.stderr
            sufixo = build.replace(".", "_").replace("-", "_")
            assert _sha256(pacote / "main.h") == dados[f"SHA256_MAIN_{sufixo}"]
            if build in da_raiz:
                assert _sha256(pacote / "usb.c") == dados["SHA256_PATCHED_C"], build
                assert _sha256(pacote / "rx.h") == _sha256(ASSET_DIR / "rx.h"), build
            else:
                assert _sha256(pacote / "usb.c") == dados["SHA256_PATCHED_C_7_2_6"], build
                assert _sha256(pacote / "rx.h") == dados["SHA256_RX_H_7_2_6"], build

    def test_o_escolhedor_recusa_kernel_sem_fonte_conferido(self, tmp_path: Path) -> None:
        pacote = _copia_do_pacote(tmp_path)
        resultado = _escolhe(pacote, "7.2.7-76070207-generic")
        assert resultado.returncode != 0
        # com o `main.h` presente mas sem fonte, também recusa: os dois trincos são independentes
        shutil.copy2(
            ASSET_DIR / "main-por-kernel" / f"main-{KERNEL_726}.h",
            pacote / "main-por-kernel" / "main-7.2.7-76070207.h",
        )
        resultado = _escolhe(pacote, "7.2.7-76070207-generic")
        assert resultado.returncode != 0, "kernel com main.h e sem fonte conferido compilou"
        assert "fonte conferido" in resultado.stderr
