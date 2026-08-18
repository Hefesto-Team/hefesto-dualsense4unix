"""Onda W — assets DKMS do rtw88_usb patchado (fantasma USB do dongle WiFi).

Desenho: docs/process/estudos/2026-07-20-desenho-onda-w-patch-dkms.md.
Premissas: docs/process/estudos/2026-07-20-estudo-premissas-onda-w-rtw88.md.

Contrato dos assets (falha-sem/passa-com; SEM root, SEM kernel vivo — só
arquivos e ferramentas de usuário):

- dkms.conf com os campos exatos + BUILD_EXCLUSIVE_KERNEL="^7\\.0\\.11-"
  (pino de ABI: os headers privados do rtw88 empacotados congelam o layout
  do v7.0.11 — kernel novo compilaria limpo e CORROMPERIA memória; com o
  pino o dkms PULA o build e o in-tree volta, fail-safe);
- Makefile kbuild mínimo de 2 linhas (obj-m + usb.o);
- usb.c/usb.h com a lógica device-gone + usb_queue_reset_device e a DECISÃO
  -EPROTO do §1.2 do desenho: -ENODEV/-ESHUTDOWN armam imediato (sinal
  definitivo do USB core); -EPROTO NUNCA arma direto — só via >4 erros
  CONSECUTIVOS sem um único sucesso no meio (rajada de EMI não derruba o
  WiFi; qualquer transferência boa zera o contador); o reset é gateado pelo
  module param hang_reset (bool 0644, default Y);
- backport 0001 do memleak upstream (6b964941bbfe/CVE-2026-63821) presente —
  PRÉ-REQUISITO do 0002 (o early-return -ENODEV no TX depende de o chamador
  liberar skb/txcb);
- strings de log do vanilla preservadas byte a byte (kernel-watch/doctor
  atuais continuam casando);
- BASELINE verificável por sha256 RECALCULADO aqui: shipping == PATCHED;
  `patch -R` de 0002+0001 reproduz o VANILLA; os 10 headers intocados batem
  o SHA256_HEADERS_BUNDLE.
"""

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

# Fecho transitivo de includes do usb.c (provado no build do desenho §8):
# 10 headers vanilla INTOCADOS — o linux-headers não os traz.
HEADERS_VANILLA = (
    "main.h",
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
    """Fatia do usb.c da assinatura dada até o início da próxima função
    top-level (`\\nstatic `) — pulando forward declarations (linha que
    termina em `;`), suficiente para asserções de ordem."""
    ini = C.index(assinatura)
    while C[ini : C.index("\n", ini)].rstrip().endswith(";"):
        ini = C.index(assinatura, ini + 1)
    fim = C.index("\nstatic ", ini + 1)
    return C[ini:fim]


def _aplica_patch(cwd: Path, patch_path: Path, reverso: bool) -> None:
    """Aplica o patch (-p6, caminhos a/drivers/net/wireless/realtek/rtw88/*)
    em cwd, com `patch` se existir, senão `git apply` — sem skip: sem
    nenhuma das duas ferramentas o teste FALHA (baseline de CI/dev)."""
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
    # Ordem inversa da aplicação: -R 0002 primeiro, depois -R 0001
    # (0001 toca só o usb.c; 0002 toca usb.c e usb.h).
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
        # O nome do módulo NÃO muda (rtw88_usb): é isso que faz o
        # updates/dkms vencer o in-tree por precedência do depmod.
        assert 'BUILT_MODULE_NAME[0]="rtw88_usb"' in DKMS_CONF

    def test_dest_module_location_updates_dkms(self) -> None:
        assert 'DEST_MODULE_LOCATION[0]="/updates/dkms"' in DKMS_CONF

    def test_autoinstall_reconstrucao_em_update_de_kernel(self) -> None:
        assert 'AUTOINSTALL="yes"' in DKMS_CONF

    def test_pino_de_abi_build_exclusive_kernel(self) -> None:
        # O risco que o hid-nintendo NÃO tinha: os headers privados do rtw88
        # empacotados congelam o layout de struct rtw_dev do v7.0.11 — num
        # kernel novo o AUTOINSTALL linkaria LIMPO e corromperia memória em
        # runtime. O pino tem de ser no BUILD EXATO validado (76070011), não só
        # na versão nominal 7.0.11: um respin da MESMA 7.0.11 com struct
        # diferente casaria "^7\.0\.11-" e corromperia memória. Com o build
        # exato, qualquer outro kernel (respin ou série nova) ⇒ dkms PULA o
        # build (in-tree volta, nunca sem WiFi) até o rebase do BASELINE.
        assert 'BUILD_EXCLUSIVE_KERNEL="^7\\.0\\.11-76070011-"' in DKMS_CONF, (
            "o pino tem de casar o BUILD exato (76070011); só a versão nominal "
            "deixa um respin da mesma 7.0.11 corromper memória silenciosamente"
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
        # Gate de campo da parte agressiva: desliga SÓ o reset; a detecção/
        # silenciamento fica (== rtw89 vanilla, troca consciente documentada).
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
        # Sinal DEFINITIVO: o USB core já sabe que o device sumiu — zero
        # risco de falso-positivo, arma sem passar pelo contador.
        corpo = _funcao_c("static void rtw_usb_io_error(struct rtw_usb *rtwusb, int error)")
        imediato = corpo.index("error == -ENODEV || error == -ESHUTDOWN")
        contador = corpo.index("atomic_inc_return(&rtwusb->continual_io_error)")
        assert imediato < contador, "o ramo definitivo vem ANTES do contador"

    def test_eproto_nunca_arma_direto_so_via_contador(self) -> None:
        # A decisão do risco de design crítico (§1.2): -EPROTO em rajada pode
        # ser EMI transitória — só arma após >4 falhas CONSECUTIVAS sem um
        # único sucesso no meio. No fantasma real o core NUNCA devolveu
        # -ENODEV (o disconnect se perdeu) — o -EPROTO persistente É o único
        # sinal do fantasma, por isso o reset não pode ser só-em-ENODEV.
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
        # Bug lateral §2a do estudo: rtw_usb_read devolvia lixo do ring
        # buffer compartilhado ao polling de power-off contra hardware morto.
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
    """0001 é PRÉ-REQUISITO do 0002: sem ele o early-return -ENODEV no TX
    criaria vazamentos novos (skb/txcb órfãos)."""

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
        # O 0002 reescreve os blocos de erro (early-return/contador) — pode
        # remover a LINHA, mas a STRING tem de voltar idêntica num "+".
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
        # Obrigatório no DKMS: o rtw88_core in-tree continua com o layout
        # dele — o estado novo vive em struct rtw_usb (usb.h), NUNCA em
        # main.h/struct rtw_dev (p/ upstream é rebase trivial p/ rtwdev->flags).
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
        assert re.fullmatch(r"[0-9a-f]{40}", dados.get("POP_LINUX_COMMIT", "")), (
            "POP_LINUX_COMMIT precisa ser o sha do repo pop-os/linux"
        )
        for chave in (
            "SHA256_VANILLA_C",
            "SHA256_VANILLA_H",
            "SHA256_PATCHED_C",
            "SHA256_PATCHED_H",
            "SHA256_HEADERS_BUNDLE",
        ):
            assert re.fullmatch(r"[0-9a-f]{64}", dados.get(chave, "")), f"{chave} inválido"
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
        # Mesma receita gravada no BASELINE: sha256 da SAÍDA do sha256sum
        # (ordem fixa) — pega qualquer edição num dos 10 headers empacotados.
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
        # Os dois sentidos: vanilla + 0001 + 0002 == shipping (rebase e
        # upstream partem daqui).
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
        # Gate check_anonymity: o repo fica anônimo; a submissão real troca o
        # SoB (DCO exige pessoa) — decisão da mantenedora, fora do repo.
        assert SOB_ANONIMO in PATCH2

    def test_patch_adiciona_o_gate_e_o_reset(self) -> None:
        assert "+module_param_named(hang_reset, rtw_usb_hang_reset, bool, 0644);" in PATCH2, (
            "o .patch precisa carregar o gate junto com o .c (invariante de rebase)"
        )
        assert "usb_queue_reset_device" in PATCH2
