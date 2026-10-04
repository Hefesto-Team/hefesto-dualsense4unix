"""A faixa do Wi-Fi se lê do NetworkManager, sem varrer — CADA-FAIXA-TEM-DONO-01 (item 2)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import faixa_do_wifi as fw

#: faixa forjada (`aa:bb:cc`): o nome do Wi-Fi USB carrega o endereço do adaptador
INTERFACE_USB = "wlxaabbcc000102"
INTERFACE_PCI = "wlp3s0"


def _canais_pelo_padrao(centro_mhz: int, largura_mhz: int) -> tuple[int, int]:
    """A tabela do padrão como dado: o canal `k` do Bluetooth mora em `2402 + k` MHz."""
    dentro = [
        k for k in range(79)
        if centro_mhz - largura_mhz / 2 <= 2402 + k <= centro_mhz + largura_mhz / 2
    ]
    return dentro[0], dentro[-1] + 1


class NetworkManagerDeMentira:
    """O barramento de sistema com um NetworkManager de mentira, que CONTA o que lhe pedem."""

    def __init__(self, dispositivos: dict[str, dict[str, Any]] | None = None, *,
                 responde: bool = True) -> None:
        self.dispositivos = dispositivos or {}
        self.responde = responde
        self.metodos: list[str] = []
        self.propriedades: list[str] = []

    def chamar(self, destino: str, caminho: str, interface: str, metodo: str,
               assinatura: str, argumentos: Any, *, espera: float) -> bd.Escrita:
        self.metodos.append(metodo)
        if not self.responde:
            return bd.Escrita(False, "org.freedesktop.DBus.Error.ServiceUnknown", "sem dono")
        assert destino == fw.SERVICO
        if metodo == "GetDevices":
            return bd.Escrita(True, resposta=(list(self.dispositivos),))
        assert metodo == "Get" and interface == fw.PROPRIEDADES, metodo
        dona, nome = argumentos
        self.propriedades.append(nome)
        valor = self.dispositivos.get(caminho, {}).get(dona, {}).get(nome)
        if valor is None:
            return bd.Escrita(False, "org.freedesktop.DBus.Error.UnknownProperty", nome)
        return bd.Escrita(True, resposta=(valor,))


def _rede(interface: str, mhz: int, largura: int | None) -> dict[str, dict[str, Any]]:
    ponto = {fw.INTERFACE_DO_PONTO: {"Frequency": mhz}}
    if largura is not None:
        ponto[fw.INTERFACE_DO_PONTO]["Bandwidth"] = largura
    return {
        "dispositivo": {
            fw.INTERFACE_DO_DISPOSITIVO: {"DeviceType": fw.TIPO_WIFI, "Interface": interface},
            fw.INTERFACE_SEM_FIO: {"ActiveAccessPoint": "/ponto"},
        },
        "ponto": ponto,
    }


def _um_wifi(interface: str, mhz: int, largura: int | None) -> NetworkManagerDeMentira:
    r = _rede(interface, mhz, largura)
    return NetworkManagerDeMentira({"/dev/0": r["dispositivo"], "/ponto": r["ponto"]})


def _sys_de_mentira(raiz: Path) -> tuple[str, str]:
    """`/sys/class/net` com um Wi-Fi USB debaixo de `4-1.2:1.0` e um Wi-Fi PCI; devolve
    `(raiz_net, nó USB)`."""
    no = raiz / "usb4" / "4-1" / "4-1.2"
    (no / "4-1.2:1.0").mkdir(parents=True)
    pci = raiz / "pci0000:00" / "0000:03:00.0"
    pci.mkdir(parents=True)
    rede = raiz / "net"
    (rede / INTERFACE_USB).mkdir(parents=True)
    (rede / INTERFACE_PCI).mkdir()
    (rede / INTERFACE_USB / "device").symlink_to(no / "4-1.2:1.0")
    (rede / INTERFACE_PCI / "device").symlink_to(pci)
    return str(rede), str(no.resolve())


@pytest.mark.parametrize(("mhz", "largura", "esperado_largura"), [
    (2437, 20, True),
    (2412, None, False),
    (2462, 40, True),
])
def test_a_faixa_em_2_4_ghz_cai_nos_canais_do_bluetooth_pelo_padrao(
    mhz: int, largura: int | None, esperado_largura: bool
) -> None:
    faixa = fw.faixa_no_bluetooth(fw.RedeSemFio("", mhz, largura))
    ini, fim = _canais_pelo_padrao(mhz, largura or 20)
    assert (faixa.como, faixa.ini, faixa.fim) == (fw.PROVAVEL, ini, fim)
    assert faixa.largura_informada is esperado_largura


def test_o_canal_6_do_wifi_cobre_os_canais_25_a_45() -> None:
    faixa = fw.faixa_no_bluetooth(fw.RedeSemFio("", 2437, 20))
    assert (faixa.ini, faixa.fim) == (25, 46)


def test_a_rede_de_5_ghz_esta_fora_desta_faixa() -> None:
    assert fw.faixa_no_bluetooth(fw.RedeSemFio("", 5805, 80)).como == fw.FORA


def test_sem_networkmanager_ou_sem_rede_ativa_e_none_e_nunca_lista_vazia(tmp_path: Path) -> None:
    raiz_net, _ = _sys_de_mentira(tmp_path)
    assert fw.ler_as_redes(NetworkManagerDeMentira(responde=False), raiz_net=raiz_net) is None
    assert fw.ler_as_redes(NetworkManagerDeMentira({}), raiz_net=raiz_net) is None
    r = _rede(INTERFACE_USB, 2437, 20)
    r["dispositivo"][fw.INTERFACE_SEM_FIO]["ActiveAccessPoint"] = fw.SEM_PONTO_ATIVO
    parado = NetworkManagerDeMentira({"/dev/0": r["dispositivo"]})
    assert fw.ler_as_redes(parado, raiz_net=raiz_net) is None


def test_a_rede_do_usb_casa_com_o_no_e_a_de_dentro_da_maquina_fica_sem_no(tmp_path: Path) -> None:
    raiz_net, no_usb = _sys_de_mentira(tmp_path)
    usb, pci = _rede(INTERFACE_USB, 5805, 80), _rede(INTERFACE_PCI, 2437, None)
    barramento = NetworkManagerDeMentira({
        "/dev/0": usb["dispositivo"], "/ponto": usb["ponto"],
        "/dev/1": pci["dispositivo"],
    })
    pci["dispositivo"][fw.INTERFACE_SEM_FIO]["ActiveAccessPoint"] = "/ponto2"
    barramento.dispositivos["/ponto2"] = pci["ponto"]
    redes = fw.ler_as_redes(barramento, raiz_net=raiz_net)
    assert redes == [fw.RedeSemFio(no_usb, 5805, 80), fw.RedeSemFio("", 2437, None)]


def test_o_nome_da_interface_nao_sai_do_modulo(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    raiz_net, _ = _sys_de_mentira(tmp_path)
    with caplog.at_level(logging.DEBUG):
        redes = fw.ler_as_redes(_um_wifi(INTERFACE_USB, 2437, 20), raiz_net=raiz_net)
    assert redes
    dito = repr(redes) + repr(fw.faixa_no_bluetooth(redes[0])) + caplog.text
    assert "aabbcc" not in dito.lower() and "wlx" not in dito


def test_nunca_varre_e_nunca_le_o_ssid_nem_o_endereco(tmp_path: Path) -> None:
    raiz_net, _ = _sys_de_mentira(tmp_path)
    barramento = _um_wifi(INTERFACE_USB, 2437, 20)
    assert fw.ler_as_redes(barramento, raiz_net=raiz_net)
    assert "RequestScan" not in barramento.metodos
    assert set(barramento.metodos) == {"GetDevices", "Get"}
    assert not {"Ssid", "HwAddress", "PermHwAddress"} & set(barramento.propriedades)


def test_sob_a_suite_o_barramento_de_verdade_nao_abre() -> None:
    """Sem barramento por argumento, a guarda do `bluez_dbus` vale: a suíte não lê a rede dela."""
    assert fw.ler_as_redes() is None
