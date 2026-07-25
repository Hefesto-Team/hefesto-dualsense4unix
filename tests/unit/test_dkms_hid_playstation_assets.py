"""Contenção BT (25/07) — assets DKMS do hid-playstation patchado.

O problema que estes assets curam, medido nesta máquina: dois DualSense
conectando no mesmo adaptador com ~1 s de diferença. O primeiro concluiu a
probe em 74 ms; o segundo pegou o pairing info (reportID 9) e perdeu o
firmware info (reportID 32) com `-5`, e o device inteiro sumiu — sem hidraw,
sem input, sem LED, sem bateria. Com o alvo do projeto sendo QUATRO controles
por Bluetooth, essa disputa deixa de ser exceção.

O `-5` é máscara, não diagnóstico — a cadeia real (as três medidas que o
README do pacote documenta):

1. o `uhid` do kernel achata QUALQUER erro do transporte em `-EIO`
   (`uhid_hid_get_report`: ``if (req->err) ret = -EIO;``);
2. passaram 3,26 s até a falha, e a espera do `uhid` é de 5 s — logo o kernel
   ainda esperava; quem desistiu foi o userspace;
3. o `bluetoothd` registrou quem desistiu, no mesmo segundo:
   ``hidp_report_req_timeout() ... HIDP GET_REPORT request timed out`` — o
   `REPORT_REQ_TIMEOUT` do BlueZ, que é de 3 s.

Contrato dos assets (falha-sem/passa-com; SEM root, SEM kernel vivo — só
arquivos e ferramentas de usuário):

- dkms.conf com os campos exatos (PACKAGE_NAME/BUILT_MODULE_NAME[0]/
  DEST_MODULE_LOCATION[0]=/updates/dkms/AUTOINSTALL) — é a precedência
  updates/dkms que faz o patchado vencer o in-tree SEM blacklist;
- Makefile kbuild mínimo com -DCONFIG_PLAYSTATION_FF=1 (o in-tree tem
  CONFIG_PLAYSTATION_FF=y; sem a flag o rumble sumiria);
- o retry GATEADO pelo module param `feature_retries`, default 0 == vanilla
  (uma tentativa) — mudança de comportamento nunca é incondicional;
- BASELINE verificável por sha256 RECALCULADO aqui: o .c shipping bate
  SHA256_PATCHED_C e o patch REVERTIDO devolve exatamente SHA256_VANILLA_C;
- o `hid-ids.h` é o MESMO do pacote hid-nintendo, byte a byte — é essa
  coincidência que prova que o commit vanilla baixado é o certo.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = REPO_ROOT / "assets" / "dkms" / "hid-playstation"
NINTENDO_ASSET_DIR = REPO_ROOT / "assets" / "dkms" / "hid-nintendo"
DKMS_CONF_PATH = ASSET_DIR / "dkms.conf"
MAKEFILE_PATH = ASSET_DIR / "Makefile"
C_PATH = ASSET_DIR / "hid-playstation.c"
HID_IDS_PATH = ASSET_DIR / "hid-ids.h"
README_PATH = ASSET_DIR / "README.md"
PATCH_PATH = (
    ASSET_DIR / "patch" / "0001-HID-playstation-retry-feature-reports-that-time-out-o.patch"
)
PATCH_PATHS = (PATCH_PATH,)
BASELINE_PATH = ASSET_DIR / "patch" / "BASELINE"
MODPROBE_CONF_PATH = REPO_ROOT / "assets" / "modprobe.d" / "hefesto-hid-playstation.conf"

SOB_ANONIMO = (
    "Signed-off-by: Hefesto DualSense4Unix Project "
    "<hefesto-dualsense4unix@users.noreply.github.com>"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


DKMS_CONF = _read(DKMS_CONF_PATH)
MAKEFILE = _read(MAKEFILE_PATH)
C = _read(C_PATH)
PATCH = _read(PATCH_PATH)
BASELINE = _read(BASELINE_PATH)
README = _read(README_PATH)
MODPROBE_CONF = _read(MODPROBE_CONF_PATH)


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
    return [
        linha.strip().partition("=")[2]
        for linha in BASELINE.splitlines()
        if linha.strip().startswith("PATCH=")
    ]


def _aplica_um_patch(
    cwd: Path, reverso: bool, patch_path: Path
) -> subprocess.CompletedProcess[str]:
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
            README_PATH,
            PATCH_PATH,
            BASELINE_PATH,
            MODPROBE_CONF_PATH,
        ):
            assert path.exists(), f"asset ausente: {path.relative_to(REPO_ROOT)}"


class TestDkmsConf:
    def test_package_name(self) -> None:
        assert 'PACKAGE_NAME="hefesto-hid-playstation"' in DKMS_CONF

    def test_package_version_semver(self) -> None:
        match = re.search(r'^PACKAGE_VERSION="([^"]+)"$', DKMS_CONF, re.MULTILINE)
        assert match is not None, "PACKAGE_VERSION ausente no dkms.conf"
        assert re.fullmatch(r"\d+\.\d+\.\d+", match.group(1))

    def test_built_module_e_destino_updates_dkms(self) -> None:
        # É a precedência updates/dkms que faz o patchado vencer o in-tree
        # SEM blacklist (/etc/depmod.d/ubuntu.conf: "search updates ...").
        assert 'BUILT_MODULE_NAME[0]="hid-playstation"' in DKMS_CONF
        assert 'DEST_MODULE_LOCATION[0]="/updates/dkms"' in DKMS_CONF
        assert 'AUTOINSTALL="yes"' in DKMS_CONF


class TestMakefile:
    def test_kbuild_minimo_com_playstation_ff(self) -> None:
        # O in-tree tem CONFIG_PLAYSTATION_FF=y; sem a flag o rumble sumiria.
        assert "obj-m := hid-playstation.o" in MAKEFILE
        assert "-DCONFIG_PLAYSTATION_FF=1" in MAKEFILE


class TestRetryOptIn:
    def test_param_existe_com_default_vanilla(self) -> None:
        # `static unsigned int feature_retries;` sem inicializador == 0 ==
        # uma tentativa == comportamento de hoje. O default NUNCA pode mudar
        # de comportamento sozinho (disciplina do projeto).
        assert re.search(r"^static unsigned int feature_retries;$", C, re.MULTILINE), (
            "feature_retries precisa ser 0 por default (== vanilla)"
        )
        assert re.search(r"^module_param\(feature_retries, uint, 0644\);$", C, re.MULTILINE)

    def test_parm_desc_diz_o_default_e_o_porque(self) -> None:
        desc = C.split("MODULE_PARM_DESC(feature_retries,", 1)[1].split(");", 1)[0]
        assert "default 0" in desc, "o MODULE_PARM_DESC tem que declarar o default"
        assert "same as before" in desc
        assert "bluetooth" in desc.lower()

    def test_o_retry_e_gateado_e_nao_incondicional(self) -> None:
        # O corpo original virou __ps_get_report (intocado) e o wrapper novo
        # é quem repete — com o gate no contador.
        assert "static int __ps_get_report(" in C, "o corpo vanilla vira __ps_get_report"
        wrapper = C.split("static int ps_get_report(", 1)[1].split("\n}", 1)[0]
        assert "feature_retries" in wrapper, "o wrapper tem que ler o param"
        assert "__ps_get_report(" in wrapper
        assert "msleep" in wrapper, "backoff entre tentativas"

    def test_backoff_declarado_como_constante(self) -> None:
        assert re.search(
            r"^#define PS_FEATURE_RETRY_DELAY_MS\s+\d+$", C, re.MULTILINE
        ), "o backoff é constante nomeada, não número solto"

    def test_delay_h_incluido(self) -> None:
        # msleep() exige <linux/delay.h>; hoje ele chega por transitividade,
        # o que é acidente de header, não contrato.
        assert "#include <linux/delay.h>" in C


class TestBaselineEParidadeDoPatch:
    def test_baseline_tem_todas_as_chaves(self) -> None:
        dados = _baseline()
        assert dados.get("KERNEL_BASE") == "v7.0.11"
        assert dados.get("KERNEL_TESTED") == "7.0.11-76070011-generic"
        assert re.fullmatch(r"[0-9a-f]{40}", dados.get("POP_LINUX_COMMIT", "")), (
            "POP_LINUX_COMMIT precisa ser o sha do repo pop-os/linux"
        )
        for chave in ("SHA256_VANILLA_C", "SHA256_PATCHED_C", "SHA256_HID_IDS_H"):
            assert re.fullmatch(r"[0-9a-f]{64}", dados.get(chave, "")), f"{chave} inválido"
        assert _baseline_patches() == [p.name for p in PATCH_PATHS]

    def test_mesmo_commit_do_pacote_hid_nintendo(self) -> None:
        # Os dois pacotes vendoram do MESMO kernel; divergir aqui significa
        # que um dos dois rebaseou sozinho e a série vai quebrar no próximo.
        nintendo_baseline = _read(NINTENDO_ASSET_DIR / "patch" / "BASELINE")
        alvo = _baseline()["POP_LINUX_COMMIT"]
        assert f"POP_LINUX_COMMIT={alvo}" in nintendo_baseline

    def test_sha_do_c_shipping_bate_com_o_baseline(self) -> None:
        assert _sha256(C_PATH) == _baseline()["SHA256_PATCHED_C"], (
            "hid-playstation.c divergiu do BASELINE — edição manual sem "
            "atualizar o .patch/BASELINE quebra o rebase e o upstream"
        )

    def test_hid_ids_e_o_mesmo_do_pacote_nintendo_byte_a_byte(self) -> None:
        # É a prova de proveniência: o header privado veio do mesmo commit e
        # está intocado nos dois pacotes.
        assert _sha256(HID_IDS_PATH) == _baseline()["SHA256_HID_IDS_H"]
        assert _sha256(HID_IDS_PATH) == _sha256(NINTENDO_ASSET_DIR / "hid-ids.h")

    def test_patch_revertido_devolve_o_vanilla_exato(self, tmp_path: Path) -> None:
        trabalho = tmp_path / "rev"
        trabalho.mkdir()
        alvo = trabalho / "hid-playstation.c"
        shutil.copy2(C_PATH, alvo)
        resultado = _aplica_serie(trabalho, reverso=True)
        assert resultado.returncode == 0, (
            f"patch -R não aplicou limpo: {resultado.stdout}{resultado.stderr}"
        )
        assert _sha256(alvo) == _baseline()["SHA256_VANILLA_C"], (
            "reverter a série não reproduz o vanilla v7.0.11 — o .c e o "
            ".patch divergiram (edite sempre os DOIS juntos)"
        )

    def test_patch_reaplicado_devolve_o_patchado_exato(self, tmp_path: Path) -> None:
        trabalho = tmp_path / "fwd"
        trabalho.mkdir()
        alvo = trabalho / "hid-playstation.c"
        shutil.copy2(C_PATH, alvo)
        assert _aplica_serie(trabalho, reverso=True).returncode == 0
        resultado = _aplica_serie(trabalho, reverso=False)
        assert resultado.returncode == 0, (
            f"patch forward não aplicou limpo: {resultado.stdout}{resultado.stderr}"
        )
        assert _sha256(alvo) == _baseline()["SHA256_PATCHED_C"]


class TestFormatoDoPatchUpstream:
    def test_formato_git_format_patch(self) -> None:
        assert PATCH.startswith("From "), "precisa ser saída de git format-patch"
        assert "Subject: [PATCH] HID: playstation:" in PATCH

    def test_caminhos_do_kernel_tree(self) -> None:
        assert "--- a/drivers/hid/hid-playstation.c" in PATCH
        assert "+++ b/drivers/hid/hid-playstation.c" in PATCH

    def test_signed_off_by_placeholder_anonimo(self) -> None:
        # Gate check_anonymity: o repo fica anônimo; a submissão real troca o
        # SoB (DCO exige pessoa) — decisão da mantenedora, fora do repo.
        assert SOB_ANONIMO in PATCH

    def test_commit_message_carrega_a_cadeia_causal_medida(self) -> None:
        # O valor upstream deste patch É o diagnóstico: sem ele o revisor só
        # vê "retry porque às vezes falha". As três medidas têm que estar lá.
        corpo = PATCH.split("---", 1)[0]
        assert "reportID 32" in corpo, "o sintoma medido"
        assert "uhid" in corpo and "-EIO" in corpo, "o achatamento do erro real"
        assert "hidp_report_req_timeout" in corpo, "quem realmente desistiu"
        assert "REPORT_REQ_TIMEOUT" in corpo, "o timeout de 3 s do BlueZ"

    def test_nao_remove_as_strings_de_log_do_vanilla(self) -> None:
        # doctor/kernel-watch casam por essas strings; o patch acrescenta,
        # nunca reescreve.
        for texto in (
            "Failed to retrieve feature with reportID %d: %d\\n",
            "Invalid byte count transferred",
            "CRC check failed for reportID=%d\\n",
        ):
            assert texto in C, f"string de log do vanilla sumiu: {texto}"


class TestModprobeConf:
    def test_cura_opt_in_pela_conf(self) -> None:
        assert re.search(
            r"^options hid_playstation feature_retries=2$", MODPROBE_CONF, re.MULTILINE
        ), "a cura entra pela conf (o default do módulo é 0 == vanilla)"

    def test_conf_explica_a_cadeia_causal_nao_so_o_valor(self) -> None:
        # Quem abrir esse arquivo em 6 meses precisa entender por que o -5
        # não é o erro real — senão alguém "simplifica" o valor e volta o bug.
        cabecalho = MODPROBE_CONF.split("options ")[0]
        assert "uhid" in cabecalho
        assert "REPORT_REQ_TIMEOUT" in cabecalho
        assert "3 s" in cabecalho or "3s" in cabecalho

    def test_conf_avisa_que_nunca_se_recarrega_o_modulo(self) -> None:
        # Recarregar hid_playstation derruba TODOS os DualSense (os por BT
        # perdem o link). A conf tem que dizer isso.
        cabecalho = MODPROBE_CONF.split("options ")[0]
        assert "reload" in cabecalho.lower()


class TestReadmeHonesto:
    def test_readme_separa_fato_medido_de_hipotese(self) -> None:
        # Regra da casa: relatório honesto > cura inventada. O retry NÃO pôde
        # ser validado ao vivo (exigiria derrubar os DualSense em uso), e o
        # texto tem que dizer isso sem diluir no meio do que É medido.
        assert "NÃO medido (hipótese)" in README
        assert "Medido (fato)" in README
        assert "próximo boot" in README, "tem que dizer QUANDO a validação acontece"

    def test_readme_marca_o_rebind_como_a_cura_validada_e_de_1a_linha(self) -> None:
        # Os dois níveis de confiança NÃO podem se misturar: o rebind está
        # provado ao vivo (25/07 12:06), o feature_retries não.
        assert "bt_rebind_orphans.sh" in README
        assert "VALIDADA AO VIVO" in README
        assert "SEGUNDA linha" in README, (
            "este DKMS é a cura estrutural, não a que está funcionando hoje"
        )

    def test_readme_registra_que_o_rebind_prova_o_device_integro(self) -> None:
        # O dado que o rebind acrescenta ao diagnóstico: a falha é só na
        # JANELA DE PROBE — o controle, o bond e o link seguem sãos.
        # Espaços normalizados: o texto é quebrado em linhas de 79 colunas e a
        # frase cai no meio da quebra.
        corrido = " ".join(README.lower().replace("*", " ").split())
        assert "janela de probe" in corrido
        assert "vanilla" in corrido

    def test_readme_registra_a_alternativa_rejeitada(self) -> None:
        # Degradar (seguir sem firmware info) foi avaliado e rejeitado porque
        # o update_version decide use_vibration_v2 — errar isso entrega um
        # controle que vibra errado, calado.
        assert "REJEITADO" in README or "Rejeitado" in README
        assert "use_vibration_v2" in README

    def test_readme_avisa_que_srcversion_nao_prova_proveniencia(self) -> None:
        # Armadilha real: srcversion NÃO é reprodutível entre build in-tree e
        # out-of-tree (controle feito com o hid-nintendo vanilla).
        assert "srcversion" in README
        assert "sha256" in README.lower()
