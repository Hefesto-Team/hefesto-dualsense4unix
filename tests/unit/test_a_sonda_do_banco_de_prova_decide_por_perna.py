"""A sonda do banco de prova (parte 0 de O-FORJA-E-O-BANCO-DE-PROVA-DO-HEFESTO-01) decide por perna.

O job `banco-de-prova-sonda` mede no runner do CI o que decide onde o banco mora, e só em
`workflow_dispatch`. Esta casa não tem como rodá-lo (cria aparelho no kernel), então o que se
prova aqui é o que se pode provar sem kernel:

1. o job: só à mão, no runner certo, com teto, e a saída sobe mesmo se a sonda falhar;
2. as peças puras do plástico mínimo (`sonda_plastico.py`), contra o oráculo do produto: o CRC dos
   feature reports de rádio é o do `ds_output_report.bt_crc32`, e não um que a sonda inventou;
3. o roteiro inteiro (`sonda.sh`) numa árvore de mentira (sysfs, /dev, `sudo` e `python3` de
   mentira): a decisão por perna sai do que o kernel de mentira respondeu, e a medida que não se
   fez vira `não-mediu`, nunca `sim`.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import stat
import struct
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
CI = RAIZ / ".github" / "workflows" / "ci.yml"
PORTOES = RAIZ / "scripts" / "portoes.sh"
SONDA_SH = RAIZ / "scripts" / "banco_de_prova" / "sonda.sh"
SONDA_PY = RAIZ / "scripts" / "banco_de_prova" / "sonda_plastico.py"
FIXTURES = RAIZ / "tests" / "fixtures" / "hid"
JOB = "banco-de-prova-sonda"


def _plastico() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sonda_plastico_sob_teste", SONDA_PY)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def sp() -> ModuleType:
    return _plastico()


# 1. O JOB DO CI


def _job() -> dict[str, Any]:
    dados = yaml.safe_load(CI.read_text(encoding="utf-8"))
    assert JOB in dados["jobs"], f"o ci.yml perdeu o job `{JOB}`"
    job: dict[str, Any] = dados["jobs"][JOB]
    return job


def test_o_job_so_roda_a_mao() -> None:
    """Cria aparelho no kernel e roda o install.sh com sudo: nunca a cada push."""
    condicao = str(_job().get("if", "")).replace(" ", "")
    assert condicao == "github.event_name=='workflow_dispatch'", (
        f"o job tem de ser só de `workflow_dispatch`, e o `if` dele é {condicao!r}")
    assert "workflow_dispatch" in yaml.safe_load(CI.read_text(encoding="utf-8"))[True], (
        "o ci.yml perdeu o gatilho `workflow_dispatch`: o job nunca rodaria")


def test_o_job_roda_no_runner_do_banco_e_tem_teto() -> None:
    job = _job()
    assert job["runs-on"] == "ubuntu-24.04"
    assert isinstance(job.get("timeout-minutes"), int) and job["timeout-minutes"] <= 90, (
        "o job não tem teto: um install.sh pendurado seguraria o runner por seis horas")


def test_o_job_roda_a_sonda_e_sobe_a_saida_mesmo_se_ela_falhar() -> None:
    passos = _job()["steps"]
    corridas = [p for p in passos if "sonda.sh" in str(p.get("run", ""))]
    assert corridas, "nenhum passo roda `scripts/banco_de_prova/sonda.sh`"
    subidas = [p for p in passos if str(p.get("uses", "")).startswith("actions/upload-artifact")]
    assert subidas, "a saída da sonda não sobe como artefato"
    assert str(subidas[0].get("if", "")) == "always()", (
        "sem `if: always()` a sonda que reprova perde exatamente a saída que a explica")
    assert subidas[0]["with"]["path"].rstrip("/") == "sonda-saida"
    assert subidas[0]["with"].get("if-no-files-found") == "error"


def test_o_shellcheck_enxerga_a_pasta_da_sonda() -> None:
    """Uma pasta de scripts que nenhum linter vê é o portão cego de sempre."""
    for arquivo in (CI, PORTOES):
        linhas = [li for li in arquivo.read_text(encoding="utf-8").splitlines()
                  if "shellcheck -S error" in li]
        assert linhas, f"{arquivo.name} perdeu a varredura do shellcheck"
        assert all("scripts/banco_de_prova/*.sh" in li for li in linhas), (
            f"{arquivo.name}: a varredura não inclui scripts/banco_de_prova/*.sh")


# 2. AS PEÇAS PURAS DO PLÁSTICO


def test_o_crc_dos_features_de_radio_e_o_que_o_produto_calcula(sp: ModuleType) -> None:
    from hefesto_dualsense4unix.core.ds_output_report import BT_FEATURE_CRC_SEED, bt_crc32

    assert sp.SEMENTE_DO_FEATURE == BT_FEATURE_CRC_SEED == 0xA3
    for numero, report in sp.features_de_radio("aa:bb:cc:00:00:01").items():
        esperado = bt_crc32(report[:-4], seed=BT_FEATURE_CRC_SEED)
        assert struct.unpack("<I", report[-4:])[0] == esperado, f"0x{numero:02x}"


def test_os_tres_features_tem_o_tamanho_que_o_driver_pede(sp: ModuleType) -> None:
    for fabrica in (sp.features_do_aparelho, sp.features_de_radio):
        features = fabrica("aa:bb:cc:00:00:01")
        assert {n: len(r) for n, r in features.items()} == {0x05: 41, 0x09: 20, 0x20: 64}
        assert all(r[0] == n for n, r in features.items()), "o primeiro byte é o id do report"


def test_o_endereco_do_feature_09_e_o_da_faixa_sintetica_em_little_endian(sp: ModuleType) -> None:
    assert sp.mac_em_bytes("aa:bb:cc:00:00:01") == bytes.fromhex("010000ccbbaa")
    assert sp.feature_pareamento("aa:bb:cc:00:00:01")[1:7] == bytes.fromhex("010000ccbbaa")
    with pytest.raises(ValueError):
        sp.mac_em_bytes("aa:bb:cc")


def test_so_a_faixa_sintetica_aparece_nos_arquivos_da_sonda() -> None:
    """Nada de endereço real: os padrões são `aa:bb:cc:00:00:0N`, e é só isso."""
    import re

    for arquivo in (SONDA_SH, SONDA_PY):
        enderecos = set(re.findall(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", arquivo.read_text()))
        assert enderecos <= {"aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"}, (arquivo.name, enderecos)


def test_o_create2_do_radio_vai_no_barramento_0005_e_tem_o_tamanho_do_uhid(sp: ModuleType) -> None:
    descritor = (FIXTURES / "dualsense_usb_descriptor_054c0ce6.bin").read_bytes()
    evento = sp.evento_create2(descritor, "aa:bb:cc:00:00:01", sp.BUS_BLUETOOTH)
    assert len(evento) == 4 + 128 + 64 + 64 + 2 + 2 + 16 + 4096
    assert struct.unpack("<I", evento[:4])[0] == sp.UHID_CREATE2
    rd_size, bus = struct.unpack("<HH", evento[4 + 128 + 64 + 64:4 + 128 + 64 + 64 + 4])
    assert (rd_size, bus) == (len(descritor), 0x05)
    assert sp.BUS_BLUETOOTH == 0x05 != sp.BUS_USB


def test_o_verbo_radio_cria_o_aparelho_no_0005_e_o_destroi_no_fim(
        sp: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O que o verbo ESCREVE no `/dev/uhid`: o `UHID_CREATE2` no barramento do rádio, e o
    `UHID_DESTROY` ao sair (sem ele o aparelho de mentira ficaria no kernel do runner)."""
    leitura, escrita = os.pipe()
    abertos: list[str] = []

    def abrir(caminho: str, *_a: Any, **_k: Any) -> int:
        abertos.append(caminho)
        return escrita

    monkeypatch.setattr(sp.os, "open", abrir)
    raiz = _arvore_do_sys(tmp_path / "sys", bt=True)
    saida = tmp_path / "radio.txt"
    args = sp.argparse.Namespace(fixtures=str(FIXTURES), mac="aa:bb:cc:00:00:01",
                                 saida=str(saida), segundos=2.0, fica=False, sys=str(raiz))
    assert sp.verbo_radio(args) == 0
    assert abertos == ["/dev/uhid"]
    escrito = os.read(leitura, 1 << 16)
    os.close(leitura)
    assert struct.unpack("<I", escrito[:4])[0] == sp.UHID_CREATE2
    deslocamento = 4 + 128 + 64 + 64
    assert struct.unpack("<HH", escrito[deslocamento:deslocamento + 4])[1] == sp.BUS_BLUETOOTH
    assert struct.unpack("<I", escrito[-4:])[0] == sp.UHID_DESTROY
    linhas = dict(li.split("=", 1) for li in saida.read_text(encoding="utf-8").splitlines())
    assert linhas["registrou"] == "sim" and linhas["no_hid"] == "0005:054C:0CE6.0001"


def test_sem_o_dev_uhid_o_verbo_radio_diz_que_nao_abriu_e_nao_que_registrou(
        sp: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def recusar(*_a: Any, **_k: Any) -> int:
        raise PermissionError(13, "negado")

    monkeypatch.setattr(sp.os, "open", recusar)
    saida = tmp_path / "radio.txt"
    args = sp.argparse.Namespace(fixtures=str(FIXTURES), mac="aa:bb:cc:00:00:01",
                                 saida=str(saida), segundos=1.0, fica=False, sys=str(tmp_path))
    assert sp.verbo_radio(args) == 0
    texto = saida.read_text(encoding="utf-8")
    assert "abriu_uhid=não" in texto and "PermissionError" in texto and "registrou=sim" not in texto


def test_a_resposta_do_get_report_leva_o_id_do_pedido_e_o_feature_certo(sp: ModuleType) -> None:
    features = sp.features_de_radio("aa:bb:cc:00:00:01")
    pedido = struct.pack("<IIBB", sp.UHID_GET_REPORT, 77, 0x09, 0)
    resposta = sp.resposta_de_get_report(pedido, features)
    tipo, ident, erro = struct.unpack("<IIH", resposta[:10])
    tamanho = struct.unpack("<H", resposta[10:12])[0]
    assert (tipo, ident, erro, tamanho) == (sp.UHID_GET_REPORT_REPLY, 77, 0, 20)
    assert resposta[12:12 + 20] == features[0x09]
    desconhecido = sp.resposta_de_get_report(struct.pack("<IIBB", sp.UHID_GET_REPORT, 5, 0x7F, 0),
                                             features)
    assert struct.unpack("<IIH", desconhecido[:10])[2] != 0, "report que não existe tem de dar erro"


def test_o_ioctl_do_gadget_e_o_do_cabecalho_do_kernel(sp: ModuleType) -> None:
    """`_IOW('g', 0x42, struct usb_hidg_report)`, a struct com 72 bytes."""
    assert sp._HIDG_REPORT.size == 72
    assert sp.GADGET_HID_WRITE_GET_REPORT == 0x40486742
    cabecalho = Path("/usr/include/linux/usb/g_hid.h")
    if cabecalho.is_file():
        assert "GADGET_HID_WRITE_GET_REPORT     _IOW('g', 0x42, struct usb_hidg_report)" \
            in cabecalho.read_text(encoding="utf-8")


def _arvore_do_sys(raiz: Path, *, bt: bool = False, usb: bool = False) -> Path:
    driver = raiz / "bus" / "hid" / "drivers" / "playstation"
    driver.mkdir(parents=True)
    if bt:
        (driver / "0005:054C:0CE6.0001").mkdir()
    if usb:
        (driver / "0003:054C:0CE6.0002").mkdir()
    return raiz


def test_o_veredito_do_kernel_separa_os_barramentos(sp: ModuleType, tmp_path: Path) -> None:
    so_usb = _arvore_do_sys(tmp_path / "a", usb=True)
    assert sp.veredito_do_kernel(so_usb, sp.BUS_BLUETOOTH)["registrou"] == "não"
    assert sp.veredito_do_kernel(so_usb, sp.BUS_USB)["registrou"] == "sim"
    com_bt = _arvore_do_sys(tmp_path / "b", bt=True)
    veredito = sp.veredito_do_kernel(com_bt, sp.BUS_BLUETOOTH)
    assert veredito["registrou"] == "sim" and veredito["no_hid"] == "0005:054C:0CE6.0001"
    assert sp.veredito_do_kernel(tmp_path / "vazio", sp.BUS_BLUETOOTH)["driver_existe"] == "não"


def test_os_nos_do_vpad_do_hefesto_se_acham_pelo_phys_e_nao_pelo_plastico(
        sp: ModuleType, tmp_path: Path) -> None:
    raiz = tmp_path
    for nome, phys in (("hidraw3", "hefesto-vpad"), ("hidraw4", "sonda-plastico")):
        pasta = raiz / "class" / "hidraw" / nome / "device"
        pasta.mkdir(parents=True)
        (pasta / "uevent").write_text(f"DRIVER=playstation\nHID_PHYS={phys}\n")
    for nome, phys in (("event9", "hefesto-vpad"), ("event10", "sonda-plastico")):
        pasta = raiz / "class" / "input" / nome / "device"
        pasta.mkdir(parents=True)
        (pasta / "phys").write_text(phys + "\n")
    assert sp.nos_do_vpad(raiz) == {"hidraw": ["/dev/hidraw3"], "evdev": ["/dev/input/event9"]}


def test_acl_nao_achada_nunca_vira_sim(sp: ModuleType, tmp_path: Path) -> None:
    """ACL que não se mediu não é ACL: sem nó do vpad o veredito é `não-achou`."""
    veredito = sp.veredito_da_acl(tmp_path, abre=lambda _c: "sim")
    assert veredito["acl_hidraw"] == "não-achou" and veredito["acl_evdev"] == "não-achou"


def test_acl_recusada_aparece_com_o_errno_e_aberta_vira_sim(sp: ModuleType, tmp_path: Path) -> None:
    pasta = tmp_path / "class" / "hidraw" / "hidraw3" / "device"
    pasta.mkdir(parents=True)
    (pasta / "uevent").write_text("HID_PHYS=hefesto-vpad\n")
    recusa = sp.veredito_da_acl(tmp_path, abre=lambda _c: "não: PermissionError errno=13")
    assert recusa["acl_hidraw"].startswith("não: PermissionError")
    assert sp.veredito_da_acl(tmp_path, abre=lambda _c: "sim")["acl_hidraw"] == "sim"


def test_abre_como_quem_roda_diz_o_errno_da_recusa(sp: ModuleType, tmp_path: Path) -> None:
    arquivo = tmp_path / "no"
    arquivo.write_text("x")
    assert sp.abre_como_quem_roda(str(arquivo)) == "sim"
    assert sp.abre_como_quem_roda(str(tmp_path / "não-existe")).startswith("não: FileNotFoundError")
    if os.geteuid() != 0:
        arquivo.chmod(0)
        assert sp.abre_como_quem_roda(str(arquivo)).startswith("não: PermissionError")


# 3. O ROTEIRO NUMA ÁRVORE DE MENTIRA

_SUDO = """#!/usr/bin/env bash
[ "${FAKE_SEM_SUDO:-}" = "1" ] && exit 1
[ "$1" = "-n" ] && shift
[ "$1" = "true" ] && exit 0
exec "$@"
"""

_PYTHON3 = """#!/usr/bin/env bash
verbo="$2"
saida=""
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
    [ "${args[i]}" = "--saida" ] && saida="${args[i + 1]}"
done
case "${verbo}" in
    radio)
        if [ "${args[*]}" = "${args[*]/--fica/}" ]; then printf '%s' "${FAKE_RADIO:-}" >"${saida}"
        else printf '%s' "${FAKE_RADIO_FICA:-${FAKE_RADIO:-}}" >"${saida}"; fi ;;
    acl) printf '%s' "${FAKE_ACL:-}" >"${saida}" ;;
    cabo-features) printf '%s' "${FAKE_CABO:-}" >"${saida}" ;;
esac
exit 0
"""

_USBIP = """#!/usr/bin/env bash
if [ "$1" = "attach" ] && [ "${FAKE_CABO_REGISTRA:-0}" = "1" ]; then
    mkdir -p "${SONDA_SYS}/bus/hid/drivers/playstation/0003:054C:0CE6.0001"
fi
exit 0
"""


def _exe(caminho: Path, corpo: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(corpo, encoding="utf-8")
    caminho.chmod(caminho.stat().st_mode | stat.S_IXUSR)


def _montar(tmp_path: Path, *, modulos: tuple[str, ...], tem_udc: bool = True,
            com_usbip: bool = True) -> dict[str, Path]:
    raiz = tmp_path / "raiz"
    (raiz / "scripts" / "banco_de_prova").mkdir(parents=True)
    shutil.copy(SONDA_SH, raiz / "scripts" / "banco_de_prova" / "sonda.sh")
    (raiz / "tests" / "fixtures").mkdir(parents=True)
    shutil.copytree(FIXTURES, raiz / "tests" / "fixtures" / "hid")
    _exe(raiz / "install.sh", "#!/usr/bin/env bash\nexit \"${FAKE_INSTALL_RC:-0}\"\n")
    sys_ = tmp_path / "sys"
    for modulo in modulos:
        (sys_ / "module" / modulo).mkdir(parents=True)
    (sys_ / "kernel" / "config").mkdir(parents=True)
    if tem_udc:
        (sys_ / "class" / "udc" / "usbip-vudc.0").mkdir(parents=True)
    dev = tmp_path / "dev"
    dev.mkdir()
    for nome in ("uhid", "hidg0"):
        (dev / nome).write_text("")
    tools = tmp_path / "tools"
    tools.mkdir()
    if com_usbip:
        _exe(tools / "6.8" / "usbip", _USBIP)
        _exe(tools / "6.8" / "usbipd",
             "#!/usr/bin/env bash\nexec " + str(shutil.which("sleep")) + " 30\n")
    bin_ = tmp_path / "bin"
    _exe(bin_ / "sudo", _SUDO)
    _exe(bin_ / "python3", _PYTHON3)
    _exe(bin_ / "sleep", "#!/usr/bin/env bash\nexit 0\n")
    for nome in ("modprobe", "mount", "apt-get"):
        _exe(bin_ / nome, "#!/usr/bin/env bash\nexit 0\n")
    _exe(bin_ / "modinfo", "#!/usr/bin/env bash\nexit 1\n")
    _exe(bin_ / "mountpoint", "#!/usr/bin/env bash\nexit 0\n")
    _exe(bin_ / "dmesg",
         "#!/usr/bin/env bash\necho 'playstation 0003:054C:0CE6.0001: de mentira'\n")
    _exe(bin_ / "systemctl", "#!/usr/bin/env bash\necho active\n")
    _exe(bin_ / "systemd-detect-virt", "#!/usr/bin/env bash\necho microsoft\n")
    _exe(bin_ / "hefesto-dualsense4unix",
         "#!/usr/bin/env bash\nexec " + str(shutil.which("sleep")) + " 30\n")
    return {"raiz": raiz, "sys": sys_, "dev": dev, "tools": tools, "bin": bin_,
            "pasta": tmp_path / "saida"}


_TODOS_OS_MODULOS = ("uhid", "uinput", "hid_playstation", "libcomposite", "usb_f_hid",
                     "usbip_vudc", "vhci_hcd")

_RADIO_OK = "abriu_uhid=sim\nregistrou=sim\nno_hid=0005:054C:0CE6.0001\n"
_ACL_OK = ("acl_hidraw_nos=/dev/hidraw3\nacl_hidraw=sim\n"
           "acl_evdev_nos=/dev/input/event9\nacl_evdev=sim\n")


def _rodar(tmp_path: Path, *, modulos: tuple[str, ...] = _TODOS_OS_MODULOS,
           tem_udc: bool = True, com_usbip: bool = True,
           **ambiente: str) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
    pecas = _montar(tmp_path, modulos=modulos, tem_udc=tem_udc, com_usbip=com_usbip)
    env = {
        "PATH": f"{pecas['bin']}:/usr/bin:/bin",
        "HOME": str(tmp_path / "casa"),
        "SONDA_SYS": str(pecas["sys"]),
        "SONDA_DEV": str(pecas["dev"]),
        "SONDA_LINUX_TOOLS": str(pecas["tools"]),
        "SONDA_PASTA": str(pecas["pasta"]),
        "FAKE_RADIO": _RADIO_OK,
        "FAKE_ACL": _ACL_OK,
        "FAKE_CABO": "abriu_hidg=sim\n",
        "FAKE_CABO_REGISTRA": "1",
        **ambiente,
    }
    resultado = subprocess.run(
        ["bash", str(pecas["raiz"] / "scripts" / "banco_de_prova" / "sonda.sh")],
        env=env, cwd=tmp_path, capture_output=True, text=True, timeout=180, check=False)
    saida = pecas["pasta"] / "sonda.txt"
    pares: dict[str, str] = {}
    if saida.is_file():
        for linha in saida.read_text(encoding="utf-8").splitlines():
            chave, _, valor = linha.partition("=")
            pares[chave] = valor
    return resultado, pares


def test_tudo_responde_e_a_casa_diz_no_runner_nas_duas_pernas(tmp_path: Path) -> None:
    r, p = _rodar(tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    assert p["casa_radio"] == "no_runner" and p["casa_cabo"] == "no_runner", p
    assert p["cabo_registrou"] == "sim" and p["radio_registrou"] == "sim"
    assert p["medidas_que_nao_se_fizeram"] == "0"


def test_sem_a_acl_do_pad_o_radio_mora_so_na_vm(tmp_path: Path) -> None:
    """O `uhid` registrou, mas o jogo não abre o pad: sem ACL o banco do rádio é da VM."""
    negada = ("acl_hidraw_nos=/dev/hidraw3\nacl_hidraw=não: PermissionError errno=13\n"
              "acl_evdev_nos=/dev/input/event9\nacl_evdev=não: PermissionError errno=13\n")
    r, p = _rodar(tmp_path, FAKE_ACL=negada)
    assert r.returncode == 0
    assert p["casa_radio"] == "so_na_vm", p
    assert p["casa_cabo"] == "no_runner", "a ACL do pad não decide a perna do cabo"


def test_acl_nao_medida_nao_conta_como_acl(tmp_path: Path) -> None:
    r, p = _rodar(tmp_path, FAKE_ACL="acl_hidraw_nos=\nacl_hidraw=não-achou\n"
                                      "acl_evdev_nos=\nacl_evdev=não-achou\n")
    assert r.returncode == 0
    assert p["casa_radio"] == "so_na_vm"
    assert int(p["medidas_que_nao_se_fizeram"]) >= 2, "o `não-achou` tem de aparecer na contagem"


def test_sem_hid_playstation_registrado_o_radio_mora_so_na_vm(tmp_path: Path) -> None:
    r, p = _rodar(tmp_path, FAKE_RADIO="abriu_uhid=sim\nregistrou=não\nno_hid=\n")
    assert r.returncode == 0
    assert p["casa_radio"] == "so_na_vm" and p["casa_cabo"] == "no_runner"


def test_sem_o_usb_f_hid_o_cabo_fica_so_da_mao(tmp_path: Path) -> None:
    faltando = tuple(m for m in _TODOS_OS_MODULOS if m != "usb_f_hid")
    r, p = _rodar(tmp_path, modulos=faltando)
    assert r.returncode == 0
    assert p["casa_cabo"] == "so_da_mao" and p["casa_radio"] == "no_runner", p
    assert p["cabo_modulo_usb_f_hid"] == "ausente"
    assert p["cabo_veredito"].startswith("sem-modulo:") and "usb_f_hid" in p["cabo_veredito"]


def test_gadget_que_enumera_e_o_driver_nao_registra_e_cabo_so_da_mao(tmp_path: Path) -> None:
    """O `usb_f_hid` existe, mas o probe não passou (o GET_REPORT não foi respondido)."""
    r, p = _rodar(tmp_path, FAKE_CABO_REGISTRA="0")
    assert r.returncode == 0
    assert p["casa_cabo"] == "so_da_mao" and p["cabo_registrou"] == "não", p


def test_sem_o_usbip_a_medida_diz_nao_mediu_e_nao_sim(tmp_path: Path) -> None:
    r, p = _rodar(tmp_path, com_usbip=False)
    assert r.returncode == 0
    assert p["cabo_veredito"].startswith("não-mediu: sem o usbip"), p
    assert p["casa_cabo"] == "so_da_mao" and "cabo_registrou" not in p
    assert int(p["medidas_que_nao_se_fizeram"]) >= 1


def test_sem_sudo_sem_senha_a_sonda_nao_finge_medir(tmp_path: Path) -> None:
    r, p = _rodar(tmp_path, FAKE_SEM_SUDO="1")
    assert r.returncode == 1, "sem sudo a sonda não mediu nada: tem de reprovar, e não passar"
    assert p["casa_radio"] == "so_na_vm" and p["casa_cabo"] == "so_da_mao"
    assert p["motivo"].startswith("não-mediu:")
    assert "radio_registrou" not in p


def test_o_install_que_falha_fica_registrado_com_o_codigo(tmp_path: Path) -> None:
    r, p = _rodar(tmp_path, FAKE_INSTALL_RC="3")
    assert r.returncode == 0
    assert p["install_rc"] == "3"


def test_a_saida_chega_ao_resumo_do_job(tmp_path: Path) -> None:
    resumo = tmp_path / "resumo.md"
    r, _p = _rodar(tmp_path, GITHUB_STEP_SUMMARY=str(resumo))
    assert r.returncode == 0
    texto = resumo.read_text(encoding="utf-8")
    assert "casa_radio=no_runner" in texto and "| rádio" in texto and "no_runner" in texto
