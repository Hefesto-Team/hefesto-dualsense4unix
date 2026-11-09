"""A atualização que desfez uma cura da casa se diz: no exame, no «Suporte ao controle» e no boot.

A-ABA-SISTEMA-DIZ-QUANDO-A-ATUALIZACAO-DESFEZ-UMA-CURA-01 (09/11/2026). O dono é
``integrations/curas_da_casa.py``: quatro perguntas (os módulos DKMS, o BlueZ, o PipeWire e o
portal), lidas como o doctor lê. TUDO É DE MENTIRA: o ``/sys/module``, o ``/var/lib/dkms``, o
dpkg, o ``modinfo``, o ``systemctl`` e os binários são de um lar em ``tmp_path``.

AS MORDIDAS (feitas na sprint, com a cura devolvida): o «Suporte ao controle» de volta a «há um
módulo» reprova o caso de fábrica; notificar a cada boot reprova o «uma vez por kernel»; o
estado do ``fonte-<kernel>.txt`` ignorado reprova o caso do kernel sem fonte; outra distribuição
lida como caída reprova o «não se aplica».
"""
from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import curas_da_casa as cc
from hefesto_dualsense4unix.integrations import exame_da_mesa, storm_doctor

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
KERNEL = "7.2.18-76070218-generic"
MARCA_BZ = "report dropped, %llu so far"
MARCA_PORTAL = "hefesto-cosmic-protocols-92/client-toolkit/src/screencopy/dispatch.rs"


class Lar:
    """Uma máquina com as quatro curas de pé; cada caso derruba uma."""

    def __init__(self, base: Path) -> None:
        self.base = base
        self.sys_module = base / "sys" / "module"
        self.dkms = base / "dkms"
        self.assets = base / "assets"
        self.cache = base / "cache"
        (self.assets / "bluez-backport").mkdir(parents=True)
        (self.assets / "bluez-backport" / "BASELINE").write_text(
            f"MARCA_hefesto-0002={MARCA_BZ}\n")
        (self.assets / "pipewire-backport").mkdir()
        (self.assets / "pipewire-backport" / "BASELINE").write_text("PW_VERSAO_UPSTREAM=1.6.11\n")
        (self.assets / "portal-cosmic-backport").mkdir()
        self.portal = base / "xdg-desktop-portal-cosmic"
        (self.assets / "portal-cosmic-backport" / "BASELINE").write_text(
            f"PORTAL_PACOTE=xdg-desktop-portal-cosmic\nPORTAL_EXEC={self.portal}\n"
            f"SUFIXO=+0~hefesto1\nMARCA_cosmic-protocols-92={MARCA_PORTAL}\n")
        self.bluetoothd = base / "bluetoothd"
        self.bluetoothd.write_bytes(b"\x7fELF ... " + MARCA_BZ.encode() + b" ...")
        self.portal.write_bytes(b"\x7fELF ... " + MARCA_PORTAL.encode() + b" ...")
        self.dpkg = {"bluez": "5.88-0ubuntu0.1~hefesto24.04.6",
                     "libpipewire-0.3-modules": "1.6.11-0~hefesto24.04.1",
                     "xdg-desktop-portal-cosmic": "1.11.0~1792525517~24.04~f448ddf+0~hefesto1",
                     "cosmic-comp": "1.0.0"}
        self.modinfo: dict[str, tuple[str, str]] = {}
        self.carregados: dict[str, str] = {}
        for pacote, nome, _rotulo in cc.MODULOS:
            (self.dkms / pacote / "1.0.0").mkdir(parents=True)
            (self.dkms / pacote / "1.0.0" / f"fonte-{KERNEL}.txt").write_text("cache\nok\n")
            self.modinfo[nome] = (f"/lib/modules/{KERNEL}/updates/dkms/{nome}.ko.zst",
                                  f"SRC{nome.upper()}")
        self.carregar("hid_playstation", "SRCHID_PLAYSTATION")

    def carregar(self, nome: str, srcversion: str) -> None:
        (self.sys_module / nome).mkdir(parents=True, exist_ok=True)
        (self.sys_module / nome / "srcversion").write_text(srcversion + "\n")

    def comando(self, argv: Sequence[str]) -> str | None:
        if argv[0] == "modinfo" and argv[-1] in self.modinfo:
            arquivo, src = self.modinfo[argv[-1]]
            return f"filename:       {arquivo}\nsrcversion:     {src}\nlicense:        GPL\n"
        if argv[0] == "dpkg-query" and argv[-1] in self.dpkg:
            return f"ii |{self.dpkg[argv[-1]]}\n"
        if argv[:2] == ["systemctl", "show"]:
            return f"{{ path={self.bluetoothd} ; argv[]={self.bluetoothd} ; ignore_errors=no }}\n"
        return None

    def maquina(self) -> cc.Maquina:
        return cc.Maquina(sys_module=self.sys_module, dkms=self.dkms, assets=self.assets,
                          cache=self.cache, kernel=KERNEL, comando=self.comando)


@pytest.fixture
def lar(tmp_path: Path) -> Lar:
    return Lar(tmp_path)


def _estados(lar: Lar) -> dict[str, str]:
    return {c.id: c.estado for c in cc.curas(lar.maquina())}


def test_as_quatro_de_pe_dao_verde(lar: Lar) -> None:
    assert _estados(lar) == {"dkms": cc.VALE, "bluetooth": cc.VALE, "som": cc.VALE,
                             "portal": cc.VALE}
    total = cc.resumo(cc.curas(lar.maquina()))
    assert total.estado == cc.VALE and total.nome == "Correções do sistema"
    assert storm_doctor.check_curas_da_casa(cc.curas(lar.maquina()))[0] == storm_doctor.OK


def test_o_kernel_novo_sem_fonte_derruba_o_modulo(lar: Lar) -> None:
    (lar.dkms / "hefesto-hid-nintendo" / "1.0.0" / f"fonte-{KERNEL}.txt").write_text(
        "sem-fonte\no kernel não traz o fonte\n")
    cura = cc.modulos_da_casa(lar.maquina())
    assert cura.estado == cc.CAIU
    assert cura.frase == (
        f"O driver do controle Nintendo do Hefesto ficou de fora no kernel {KERNEL}")
    assert cura.dica == cc.RODE_O_INSTALADOR


def test_o_modulo_de_fabrica_e_o_reinicio_pendente(lar: Lar) -> None:
    lar.modinfo["rtw88_usb"] = (f"/lib/modules/{KERNEL}/kernel/drivers/rtw88_usb.ko.zst", "X")
    fabrica = cc.modulos_da_casa(lar.maquina()).frase
    assert fabrica == f"O driver do Wi-Fi USB é o de fábrica no kernel {KERNEL}"
    lar.modinfo["rtw88_usb"] = (f"/lib/modules/{KERNEL}/updates/dkms/rtw88_usb.ko.zst", "NOVO")
    lar.carregar("rtw88_usb", "VELHO")
    cura = cc.modulos_da_casa(lar.maquina())
    assert (cura.frase, cura.dica) == ("O driver do Wi-Fi USB em uso não é o do Hefesto",
                                       cc.REINICIE)


def test_o_bluez_da_distro_derruba_o_bluetooth(lar: Lar) -> None:
    lar.bluetoothd.write_bytes(b"\x7fELF bluez da distro")
    cura = cc.bluetooth(lar.maquina())
    assert cura.estado == cc.CAIU and "sem as correções do Hefesto" in cura.frase


def test_o_pipewire_da_distro_so_cai_se_for_mais_velho(lar: Lar) -> None:
    lar.dpkg["libpipewire-0.3-modules"] = "1.6.8-1pop1~1787688714~24.04~fdff050"
    assert cc.som(lar.maquina()).estado == cc.CAIU
    lar.dpkg["libpipewire-0.3-modules"] = "1.6.12-1pop1"
    assert cc.som(lar.maquina()).estado == cc.VALE, "a distro que passou a casa não é queda"


def test_o_portal_sem_a_marca_cai_e_o_que_ja_cura_de_cima_vale(lar: Lar) -> None:
    lar.portal.write_bytes(b"\x7fELF portal do pop")
    lar.dpkg["xdg-desktop-portal-cosmic"] = "1.12.0~1794000000~24.04~aaaaaaa"
    assert cc.portal(lar.maquina()).estado == cc.CAIU
    curadas = lar.cache / "portal-cosmic-backport" / "A-ORIGEM-JA-CURA.txt"
    curadas.parent.mkdir(parents=True)
    curadas.write_text("1.12.0~1794000000~24.04~aaaaaaa\n")
    assert cc.portal(lar.maquina()).estado == cc.VALE


def test_outra_distro_nao_se_aplica_nunca_vermelho(lar: Lar, tmp_path: Path) -> None:
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    outra = cc.Maquina(sys_module=vazio, dkms=vazio, assets=lar.assets, cache=vazio,
                       kernel=KERNEL, comando=lambda _argv: None)
    assert {c.estado for c in cc.curas(outra)} == {cc.NAO_SE_APLICA}
    assert cc.resumo(cc.curas(outra)).estado == cc.NAO_SE_APLICA
    assert storm_doctor.check_curas_da_casa(cc.curas(outra))[0] == storm_doctor.INFO


def test_a_que_caiu_vira_o_aviso_do_exame_e_do_boot(lar: Lar) -> None:
    lar.bluetoothd.write_bytes(b"sem marca")
    lar.dpkg["libpipewire-0.3-modules"] = "1.6.8-1pop1"
    respostas = cc.curas(lar.maquina())
    tag, frase = storm_doctor.check_curas_da_casa(respostas)
    assert tag == storm_doctor.WARN
    assert frase.startswith("O Bluetooth voltou ao da distribuição")
    assert "(e mais 1)" in frase and frase.endswith(cc.RODE_O_INSTALADOR)
    assert len(cc.linhas_de_aviso(respostas)) == 2
    relatorio = storm_doctor.storm_report(
        lar.base, quirks_text="", dropin_dir=lar.base, rules_dir=lar.base, snd_quirk_text="",
        snd_conf_path=lar.base / "x.conf", cards_text="", curas=respostas)
    assert relatorio[6] == (tag, frase)


def test_o_suporte_ao_controle_diz_quando_o_driver_e_o_de_fabrica(lar: Lar) -> None:
    modulos = lar.base / "modules"
    modulos.write_text("hid_playstation 61440 0 - Live 0x0000000000000000\n")
    certo = exame_da_mesa.suporte_ao_controle(modulos=modulos, maquina=lar.maquina())
    assert certo.estado == exame_da_mesa.ESTADO_CERTO
    lar.modinfo["hid_playstation"] = (f"/lib/modules/{KERNEL}/kernel/hid-playstation.ko", "F")
    fabrica = exame_da_mesa.suporte_ao_controle(modulos=modulos, maquina=lar.maquina())
    assert fabrica.estado == exame_da_mesa.ESTADO_ATENCAO
    assert fabrica.porque.startswith("O driver do DualSense é o de fábrica")
    assert fabrica.cura == cc.RODE_O_INSTALADOR


def test_a_notificacao_sai_uma_vez_por_kernel(lar: Lar, tmp_path: Path) -> None:
    """Prova da D-0911-A-CURA-DESFEITA-SE-DIZ-PELO-DONO-DAS-CURAS: um aviso por kernel."""
    lar.bluetoothd.write_bytes(b"sem marca")
    respostas = cc.curas(lar.maquina())
    estado = tmp_path / "estado" / cc.ARQUIVO_DO_AVISO
    ditas: list[tuple[str, str]] = []

    def notificar(titulo: str, corpo: str) -> bool:
        ditas.append((titulo, corpo))
        return True

    def avisar(kernel: str) -> bool | None:
        maquina = cc.Maquina(kernel=kernel, comando=lambda _a: None)
        return cc.avisar_uma_vez_por_kernel(respostas, maquina=maquina, estado=estado,
                                            notificar=notificar)

    assert avisar(KERNEL) is True
    assert avisar(KERNEL) is None, "o segundo boot no mesmo kernel não avisa de novo"
    assert avisar("7.2.19-generic") is True
    assert [t for t, _c in ditas] == [cc.ROTULO, cc.ROTULO]
    assert ditas[0][1].startswith("O Bluetooth voltou ao da distribuição")


def test_a_notificacao_recusada_fica_para_depois(lar: Lar, tmp_path: Path) -> None:
    lar.bluetoothd.write_bytes(b"sem marca")
    estado = tmp_path / cc.ARQUIVO_DO_AVISO
    feito = cc.avisar_uma_vez_por_kernel(cc.curas(lar.maquina()), maquina=lar.maquina(),
                                         estado=estado, notificar=lambda _t, _c: False)
    assert feito is False and not estado.exists()
    assert cc.avisar_uma_vez_por_kernel(cc.curas(lar.maquina()), maquina=lar.maquina(),
                                        estado=estado, notificar=lambda _t, _c: True) is True


def test_o_boot_tenta_de_novo_quando_a_sessao_ainda_nao_subiu(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.core import system_check

    respostas = iter([False, False, True])
    monkeypatch.setattr(cc, "avisar_uma_vez_por_kernel", lambda: next(respostas))
    dormidas: list[float] = []
    system_check.avisar_da_infra_no_boot(dormir=dormidas.append)
    assert dormidas == [system_check.ESPERA_DO_AVISO_DAS_CURAS_S] * 2


def test_a_suite_le_um_lar_vazio_e_o_boot_nao_avisa() -> None:
    from hefesto_dualsense4unix.core import system_check

    assert {c.estado for c in cc.curas_de_agora()} == {cc.NAO_SE_APLICA}
    assert not any("Hefesto" in aviso and "distribuição" in aviso
                   for aviso in system_check.system_warnings())


def _doctor(funcao: str, env: dict[str, str]) -> str:
    feito = subprocess.run(
        ["bash", "-c", f'set --; source "{DOCTOR}"; {funcao}; true'], capture_output=True,
        text=True, timeout=60, check=False,
        env={"PATH": "/usr/bin:/bin", "HOME": "/nao-existe", **env})
    return feito.stdout


@pytest.mark.skipif(shutil.which("dpkg") is None, reason="o doctor confere o BlueZ pelo dpkg")
@pytest.mark.parametrize("com_a_marca", [True, False])
def test_o_doctor_e_o_dono_respondem_igual_no_bluez(lar: Lar, com_a_marca: bool) -> None:
    if not com_a_marca:
        lar.bluetoothd.write_bytes(b"sem marca")
    saida = _doctor("check_bluez_curas_do_backport", {
        "HEFESTO_DOCTOR_BLUETOOTHD": str(lar.bluetoothd),
        "HEFESTO_DOCTOR_BLUEZ_BASELINE": str(lar.assets / "bluez-backport" / "BASELINE")})
    doctor_passa = "[ OK ]" in saida and "[WARN]" not in saida
    assert doctor_passa == (cc.bluetooth(lar.maquina()).estado == cc.VALE), saida


@pytest.mark.parametrize(("estado", "cai"), [("cache", False), ("fabrica", False),
                                             ("sem-fonte", True)])
def test_o_doctor_e_o_dono_respondem_igual_no_fonte_do_dkms(lar: Lar, estado: str,
                                                           cai: bool) -> None:
    (lar.dkms / "hefesto-hid-nintendo" / "1.0.0" / f"fonte-{KERNEL}.txt").write_text(
        f"{estado}\no kernel não traz o fonte\n")
    saida = _doctor(f"_dkms_veredito hefesto-hid-nintendo 1.0.0 {KERNEL}",
                    {"HEFESTO_DKMS_TREE": str(lar.dkms)})
    assert bool(saida.strip()) == cai
    assert (cc.modulos_da_casa(lar.maquina()).estado == cc.CAIU) == cai
