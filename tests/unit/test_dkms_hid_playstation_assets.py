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

O segundo defeito que estes assets curam (patch 0002, medido em 25/07 ~21:02):
o clone 8BitDo Pro em modo DirectInput/PS4 **no cabo** anuncia-se como
`054c:05c4`, responde o pairing info (report `0x12`) com **9 bytes em vez de
16** e perde o device inteiro — ``Failed to get MAC address from DualShock4``,
``probe with driver playstation failed with error -22``. Não é timing: o
`feature_retries` acima dispara e as três tentativas trazem os MESMOS 9 bytes.
Por Bluetooth esse report nem é lido (o endereço vem do `uniq` do HIDP), que é
por que o mesmo controle sobe por BT e só morre no cabo.

Contrato dos assets (falha-sem/passa-com; SEM root, SEM kernel vivo — só
arquivos e ferramentas de usuário):

- dkms.conf com os campos exatos (PACKAGE_NAME/BUILT_MODULE_NAME[0]/
  DEST_MODULE_LOCATION[0]=/updates/dkms/AUTOINSTALL) — é a precedência
  updates/dkms que faz o patchado vencer o in-tree SEM blacklist;
- Makefile kbuild mínimo com -DCONFIG_PLAYSTATION_FF=1 (o in-tree tem
  CONFIG_PLAYSTATION_FF=y; sem a flag o rumble sumiria);
- o retry GATEADO pelo module param `feature_retries`, default 0 == vanilla
  (uma tentativa) — mudança de comportamento nunca é incondicional;
- o patch 0002 (clone DualShock4 no cabo) GATEADO por `ds4_short_pairing_info`
  e `ds4_synthetic_mac`, ambos default N == vanilla;
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
# 25/07 à noite: 0002 cura a morte de probe do CLONE no cabo (8BitDo Pro em
# modo DirectInput/PS4, que se anuncia 054c:05c4) — pairing info curto vira
# endereço aproveitado ou sintetizado, em vez de device sem driver nenhum.
PATCH2_PATH = (
    ASSET_DIR / "patch" / "0002-HID-playstation-survive-a-DualShock4-pairing-info-rep.patch"
)
PATCH_PATHS = (PATCH_PATH, PATCH2_PATH)
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
PATCH2 = _read(PATCH2_PATH)
PATCHES = (PATCH, PATCH2)
BASELINE = _read(BASELINE_PATH)
README = _read(README_PATH)
MODPROBE_CONF = _read(MODPROBE_CONF_PATH)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _funcao_c(assinatura: str) -> str:
    """Corpo da função C que começa em ``assinatura`` (até a chave de fecho)."""
    inicio = C.index(assinatura)
    fim = C.index("\n}\n", inicio)
    return C[inicio:fim]


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
            PATCH2_PATH,
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


class TestCloneDs4NoCaboOptIn:
    """Patch 0002 — o clone que responde o pairing info curto (25/07 ~21:02).

    ``expected 16 got 9``: o driver pede 16 bytes do report ``0x12`` e recebe
    9. Como no cabo esse report é a ÚNICA fonte do endereço, a probe inteira
    morre com ``-22`` e o device fica sem driver nenhum (sem hidraw, sem input,
    sem LED, sem bateria; o hid-generic não assume porque um driver específico
    deu match). Dos 16 bytes o driver usa 7 — report ID + 6 do endereço; o
    resto é o endereço do host do último pareamento, que ele nunca lê.
    """

    PARAMS_DS4 = ("ds4_short_pairing_info", "ds4_synthetic_mac")

    def test_os_dois_params_sao_bool_default_vanilla_e_ajustaveis_a_quente(self) -> None:
        for nome in self.PARAMS_DS4:
            # sem inicializador == false == vanilla (convenção do módulo)
            assert re.search(rf"^static bool {nome};$", C, re.MULTILINE), (
                f"{nome} precisa nascer FALSE (default == vanilla, zero regressão)"
            )
            assert re.search(rf"^module_param\({nome}, bool, 0644\);$", C, re.MULTILINE), (
                f"{nome} precisa ser ajustável AO VIVO (0644) — o A/B é "
                "escrever no /sys e RECONECTAR, nunca reload (derrubaria "
                "todos os DualSense, e os por BT perdem o link)"
            )
            desc = C.split(f"MODULE_PARM_DESC({nome},", 1)[1].split(");", 1)[0]
            assert "default N" in desc, "o MODULE_PARM_DESC tem que declarar o default"
            assert "same as before" in desc

    def test_resposta_curta_so_vale_com_o_report_id_certo(self) -> None:
        # Aplicações hidraw (Steam) emitem feature request próprios — é por
        # isso que dualshock4_get_calibration_data já retenta. Endereço tirado
        # da resposta de OUTRO report seria pior do que endereço nenhum.
        corpo = _funcao_c("static bool dualshock4_pairing_info_has_mac")
        assert "if (buf[0] != DS4_FEATURE_REPORT_PAIRING_INFO)" in corpo
        assert "return false;" in corpo
        # campo todo zerado não é endereço
        assert "if (buf[DS4_PAIRING_INFO_MAC_OFFSET + i])" in corpo

    def test_endereco_sintetico_segue_a_convencao_02_vid_pid_bus(self) -> None:
        # MESMA convenção do usb_probe_degrade do hid-nintendo: o hefesto
        # trata MAC começando em 02 como identidade VOLÁTIL (ganha número na
        # sessão, nunca vai ao disco). Divergir aqui desarmaria essa cura.
        # mac_address é little endian e sai por %pMR, então o índice 5 é o
        # PRIMEIRO octeto impresso — é ele que tem de ser 0x02.
        corpo = _funcao_c("static int dualshock4_degrade_mac")
        assert "ds4->base.mac_address[5] = 0x02;" in corpo, (
            "o primeiro octeto IMPRESSO tem que ser 02 (índice 5, %pMR)"
        )
        assert "ds4->base.mac_address[4] = (u8)(hdev->vendor >> 8);" in corpo
        assert "ds4->base.mac_address[3] = (u8)hdev->vendor;" in corpo
        assert "ds4->base.mac_address[2] = (u8)(hdev->product >> 8);" in corpo
        assert "ds4->base.mac_address[1] = (u8)hdev->product;" in corpo
        assert "ds4->base.mac_address[0] = (u8)hdev->bus;" in corpo
        # estável entre replugs: nada de contador de instância na composição
        assert "hdev->id" not in corpo, (
            "hdev->id muda a cada replug — o endereço tem que ser estável"
        )

    def test_com_os_dois_gates_desligados_sobra_o_vanilla(self) -> None:
        corpo = _funcao_c("static int dualshock4_degrade_mac")
        assert "if (ds4_short_pairing_info &&" in corpo
        assert "} else if (ds4_synthetic_mac) {" in corpo
        assert "return err;" in corpo, (
            "sem gate ligado a função devolve o erro original — a falha "
            "histórica byte a byte"
        )

    def test_degrade_e_so_no_cabo(self) -> None:
        # Por Bluetooth o report 0x12 nem é lido: o endereço vem do uniq do
        # HIDP. O ramo curado tem que ficar dentro do `if (bus == BUS_USB)`.
        corpo = _funcao_c("static int dualshock4_get_mac_address")
        usb, _, bt = corpo.partition("} else {")
        assert "if (hdev->bus == BUS_USB) {" in usb
        assert "ret = dualshock4_degrade_mac(ds4, buf, ret);" in usb
        assert "dualshock4_degrade_mac" not in bt
        assert "Rely on HIDP for Bluetooth" in bt

    def test_nao_engole_o_hid_err_do_vanilla(self) -> None:
        # doctor/kernel-watch casam pela string; e um controle que degradou
        # tem que deixar rastro do POR QUÊ, não só do resultado.
        corpo = _funcao_c("static int dualshock4_get_mac_address")
        assert 'hid_err(hdev, "Failed to retrieve DualShock4 pairing info: %d\\n", ret);' in corpo
        assert 'hid_info(hdev, "DualShock4 MAC = %pMR (%s)\\n"' in C, (
            "o log tem que dizer QUAL endereço entrou e DE ONDE"
        )

    def test_patch_carrega_os_gates_junto_com_o_c(self) -> None:
        for nome in self.PARAMS_DS4:
            assert f"+module_param({nome}, bool, 0644);" in PATCH2, (
                "o .patch precisa carregar o gate junto com o .c "
                "(invariante de rebase/upstream)"
            )


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
        for corpo in PATCHES:
            assert corpo.startswith("From "), "precisa ser saída de git format-patch"
            assert "Subject: [PATCH] HID: playstation:" in corpo

    def test_caminhos_do_kernel_tree(self) -> None:
        for corpo in PATCHES:
            assert "--- a/drivers/hid/hid-playstation.c" in corpo
            assert "+++ b/drivers/hid/hid-playstation.c" in corpo

    def test_signed_off_by_placeholder_anonimo(self) -> None:
        # Gate check_anonymity: o repo fica anônimo; a submissão real troca o
        # SoB (DCO exige pessoa) — decisão da mantenedora, fora do repo.
        for corpo in PATCHES:
            assert SOB_ANONIMO in corpo

    def test_0002_carrega_a_medicao_do_clone_e_o_que_ela_refuta(self) -> None:
        # O valor upstream do 0002 é o mesmo do 0001: o diagnóstico. Sem os
        # números, um revisor só vê "aceita resposta curta".
        corpo = PATCH2.split("\n---\n", 1)[0]
        assert "expected 16 got 9" in corpo, "o sintoma medido"
        assert "054c:05c4" in corpo, "o clone se anuncia com os IDs da Sony"
        assert "retrying feature reportID 18" in corpo, (
            "os retries do 0001 são a PROVA de que não é timing"
        )
        assert "uniq" in corpo, "por BT o endereço vem do HIDP — por isso lá funciona"
        assert "locally administered" in corpo, "a natureza do endereço fabricado"

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
            "Failed to retrieve DualShock4 pairing info: %d\\n",
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

    def test_cura_do_clone_no_cabo_tambem_entra_pela_conf(self) -> None:
        # Linha SEPARADA de propósito: o kmod concatena todas as `options` do
        # mesmo módulo, então cada cura fica com o seu próprio cabeçalho e o
        # A/B de uma não obriga a reescrever a linha da outra.
        assert re.search(
            r"^options hid_playstation ds4_short_pairing_info=1 ds4_synthetic_mac=1$",
            MODPROBE_CONF,
            re.MULTILINE,
        ), "a cura do clone no cabo entra pela conf (o default do módulo é N)"

    def test_conf_explica_o_clone_e_o_que_o_endereco_sintetico_nao_e(self) -> None:
        # Quem abrir isso em 6 meses precisa saber que 02:VID:PID:bus NÃO
        # identifica aparelho — senão alguém persiste o endereço e funde dois
        # controles num só registro (defeito já medido em 25/07).
        assert "expected 16 got 9" in MODPROBE_CONF, "o sintoma medido"
        assert "054c:05c4" in MODPROBE_CONF
        assert "02:VID:PID:bus" in MODPROBE_CONF
        assert "-EEXIST" in MODPROBE_CONF, (
            "dois clones idênticos no mesmo barramento colidem — tem que estar dito"
        )

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
