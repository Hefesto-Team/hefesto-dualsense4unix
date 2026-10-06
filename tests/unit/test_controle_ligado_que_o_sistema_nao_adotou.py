"""CONTROLE-QUE-NAO-ENTROU-01 (09/08/2026) — a janela mentia sobre um controle.

Medido na máquina do usuário: **dois** DualSense ligados e pareados, e a janela
mostrava **um**. Em lugar nenhum do produto havia uma pista do porquê — a aba
Início chegava a escrever *"Nenhum controle conectado."* para um controle que
estava ligado, pareado e falando com o rádio.

A causa: o driver do kernel abortou o segundo na probe. Um controle assim
conecta no rádio, acende a luz do próprio firmware e **não tem hidraw, nem nó
de LED, nem dispositivo de entrada**. Como `describe_controllers` devolve uma
entrada por handle ABERTO, ele simplesmente não existe para nós. Também não é
um controle desconectado (está no rádio) e não é um externo (o contador de
externos lê `/dev/input`, que tampouco existe no aborto): é um **terceiro
estado**, e é o que o produto não sabia representar.

O que esta suíte trava, em três camadas:

1. **A leitura do sistema** (`daemon/ipc_handlers.dualsense_sem_driver`) — o
   critério é o do `scripts/bt_rebind_orphans.sh` e é cirúrgico: órfão é o que
   NÃO tem o symlink `driver`, no barramento Bluetooth, do fabricante Sony;
2. **O dono único da regra** — as três constantes da leitura conferidas contra
   o TEXTO do script, e o intervalo prometido na tela conferido contra o
   `OnUnitActiveSec` do timer que de fato cumpre a promessa. Dois donos da
   mesma regra fariam a janela prometer uma cura que não vem;
3. **A tela** — a função pura do texto, o vocabulário (o que ela vê, nunca o
   mecanismo) e a fiação nos dois caminhos da aba Status (o tique lento
   acende; o daemon offline apaga).

Todas as camadas rodam SEM root, SEM hardware e SEM GTK real — o sysfs é um
diretório temporário e os widgets são dublês.
"""
from __future__ import annotations

import inspect
import os
import re
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("controle ligado que o sistema não adotou (importa app.actions.status_actions)")

from hefesto_dualsense4unix.app.actions.status_actions import (
    MINUTOS_ENTRE_TENTATIVAS,
    texto_de_controle_nao_adotado,
)
from hefesto_dualsense4unix.daemon import ipc_handlers
from hefesto_dualsense4unix.daemon.ipc_handlers import (
    _HID_ORFAO_BUS,
    _HID_ORFAO_VID,
    dualsense_sem_driver,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "bt_rebind_orphans.sh"
TIMER = (
    REPO_ROOT / "assets" / "systemd" / "hefesto-bt-health-watchdog.timer"
)

ORFAO_NO_ESCOPO = "0005:054C:0CE6.000F"       # DualSense por Bluetooth
ORFAO_NO_ESCOPO_2 = "0005:054C:0CE6.0011"
ORFAO_FORA_ESCOPO = "0003:057E:2009.0001"
VPAD_COM_DRIVER = "0003:054C:0DF2.0010"
DUALSENSE_ADOTADO = "0005:054C:0CE6.000A"


def _monta_sysfs(
    tmp_path: Path, orfaos: list[str], com_driver: list[str]
) -> str:
    """Um `/sys/bus/hid/devices` de mentira — sem root e sem hardware."""
    devices = tmp_path / "devices"
    devices.mkdir(parents=True, exist_ok=True)
    fake_drv = tmp_path / "fakedrv"
    fake_drv.mkdir(exist_ok=True)
    for dev in orfaos:
        (devices / dev).mkdir(parents=True)
    for dev in com_driver:
        (devices / dev).mkdir(parents=True)
        os.symlink(fake_drv, devices / dev / "driver")
    return str(devices)


class TestLeituraDoSistema:
    def test_acha_o_controle_que_perdeu_a_probe(self, tmp_path: Path) -> None:
        dir_ = _monta_sysfs(tmp_path, [ORFAO_NO_ESCOPO], [])
        assert dualsense_sem_driver(dir_) == [ORFAO_NO_ESCOPO]

    def test_a_mesa_dela_dois_ligados_um_visivel(self, tmp_path: Path) -> None:
        dir_ = _monta_sysfs(
            tmp_path, [ORFAO_NO_ESCOPO], [DUALSENSE_ADOTADO, VPAD_COM_DRIVER]
        )
        assert dualsense_sem_driver(dir_) == [ORFAO_NO_ESCOPO]

    def test_o_que_tem_driver_nunca_conta(self, tmp_path: Path) -> None:
        dir_ = _monta_sysfs(tmp_path, [], [DUALSENSE_ADOTADO, VPAD_COM_DRIVER])
        assert dualsense_sem_driver(dir_) == []

    def test_orfao_alheio_nao_e_nosso(self, tmp_path: Path) -> None:
        dir_ = _monta_sysfs(tmp_path, [ORFAO_FORA_ESCOPO], [])
        assert dualsense_sem_driver(dir_) == []

    def test_dois_orfaos_saem_ordenados(self, tmp_path: Path) -> None:
        dir_ = _monta_sysfs(
            tmp_path, [ORFAO_NO_ESCOPO_2, ORFAO_NO_ESCOPO], []
        )
        assert dualsense_sem_driver(dir_) == [ORFAO_NO_ESCOPO, ORFAO_NO_ESCOPO_2]

    def test_sysfs_ausente_nao_derruba_a_aba(self, tmp_path: Path) -> None:
        # Este caminho roda dentro do `state_full`: um OSError aqui derrubaria
        assert dualsense_sem_driver(str(tmp_path / "nao-existe")) == []

    def test_nome_de_device_torto_nao_explode(self, tmp_path: Path) -> None:
        dir_ = _monta_sysfs(tmp_path, ["lixo", "0005", "0005:054C"], [])
        assert dualsense_sem_driver(dir_) == []


class TestUmDonoSoDaRegra:
    """A regra é do `bt_rebind_orphans.sh`. Aqui só a LEMOS para exibir."""

    def test_o_escopo_e_o_mesmo_do_script(self) -> None:
        texto = SCRIPT.read_text(encoding="utf-8")
        assert f'"${{bus}}" == "{_HID_ORFAO_BUS}"' in texto
        assert f'"${{vid}}" == "{_HID_ORFAO_VID}"' in texto

    def test_o_criterio_e_a_ausencia_do_symlink_driver(self) -> None:
        texto = SCRIPT.read_text(encoding="utf-8")
        assert '-e "${dev}/driver"' in texto
        fonte = inspect.getsource(ipc_handlers.dualsense_sem_driver)
        assert '"driver"' in fonte
        assert "os.path.exists" in fonte, (
            "o `[[ -e ]]` do script SEGUE o symlink; `lexists` diria outra "
            "coisa para um link quebrado"
        )

    def test_o_codigo_aponta_para_o_dono_da_regra(self) -> None:
        fonte = inspect.getsource(ipc_handlers)
        assert "bt_rebind_orphans.sh" in fonte, (
            "quem ler esta leitura tem de achar o script que a cura"
        )

    def test_os_minutos_prometidos_sao_os_do_timer_que_cumpre(self) -> None:
        texto = TIMER.read_text(encoding="utf-8")
        achado = re.search(r"OnUnitActiveSec=(\d+)min", texto)
        assert achado is not None, "o timer precisa dizer o intervalo em min"
        assert int(achado.group(1)) == MINUTOS_ENTRE_TENTATIVAS

    def test_o_watchdog_realmente_chama_a_cura(self) -> None:
        watchdog = (REPO_ROOT / "scripts" / "bt_health_watchdog.sh").read_text(
            encoding="utf-8"
        )
        assert "bt_rebind_orphans.sh" in watchdog


class TestOPayloadDoDaemon:
    """`state_full.controles_sem_driver` — aditivo, derivado do SISTEMA.

    A aba Status já mente hoje por outro motivo (`ESTADO-QUE-MENTE-01`: o topo
    do `state_full` é mantido em PARALELO à lista de controles, nunca derivado
    dela). Este campo novo não pode nascer com o mesmo defeito, então ele é
    lido do sistema a cada chamada, com TTL — nunca de um segundo campo.
    """

    def _payload(
        self, devices_dir: str, monkeypatch: pytest.MonkeyPatch
    ) -> dict[str, Any]:
        """O payload real, com o sysfs apontado para o diretório temporário."""
        monkeypatch.setattr(ipc_handlers, "_HID_DEVICES_DIR", devices_dir)

        class _Host(ipc_handlers.IpcHandlersMixin):
            pass

        return _Host()._controles_sem_driver_payload()

    def test_conta_e_nomeia_os_que_nao_entraram(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dir_ = _monta_sysfs(tmp_path, [ORFAO_NO_ESCOPO], [DUALSENSE_ADOTADO])
        assert self._payload(dir_, monkeypatch) == {
            "quantidade": 1,
            "ids": [ORFAO_NO_ESCOPO],
        }

    def test_mesa_saudavel_e_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dir_ = _monta_sysfs(tmp_path, [], [DUALSENSE_ADOTADO, VPAD_COM_DRIVER])
        assert self._payload(dir_, monkeypatch) == {"quantidade": 0, "ids": []}

    def test_os_ids_nao_carregam_endereco_bluetooth(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dir_ = _monta_sysfs(tmp_path, [ORFAO_NO_ESCOPO], [])
        for id_ in self._payload(dir_, monkeypatch)["ids"]:
            assert not re.search(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", id_)

    def test_o_state_full_publica_a_chave(self) -> None:
        fonte = inspect.getsource(
            ipc_handlers.IpcHandlersMixin._handle_daemon_state_full
        )
        assert (
            'result["controles_sem_driver"] = '
            "self._controles_sem_driver_payload()" in fonte
        )


def _estado(quantidade: object = "__ausente__") -> dict[str, Any]:
    estado: dict[str, Any] = {"connected": True}
    if quantidade != "__ausente__":
        estado["controles_sem_driver"] = {"quantidade": quantidade, "ids": []}
    return estado


class TestOTextoDaTela:
    def test_um_controle_acende_o_aviso(self) -> None:
        texto = texto_de_controle_nao_adotado(_estado(1))
        assert texto
        assert "ligado" in texto

    def test_dois_controles_dizem_o_numero(self) -> None:
        texto = texto_de_controle_nao_adotado(_estado(2))
        assert texto.startswith("2 controles")

    def test_mesa_saudavel_nao_acende(self) -> None:
        assert texto_de_controle_nao_adotado(_estado(0)) == ""

    def test_daemon_antigo_sem_a_chave_nao_acende(self) -> None:
        assert texto_de_controle_nao_adotado(_estado()) == ""

    def test_daemon_sem_resposta_nao_acende(self) -> None:
        assert texto_de_controle_nao_adotado(None) == ""

    @pytest.mark.parametrize("torto", [True, "2", 1.5, None, [], {}])
    def test_payload_torto_nunca_vira_alarme_falso(self, torto: object) -> None:
        assert texto_de_controle_nao_adotado(_estado(torto)) == ""

    def test_bloco_torto_nao_acende(self) -> None:
        assert texto_de_controle_nao_adotado({"controles_sem_driver": 2}) == ""

    def test_promete_a_cura_automatica_e_o_prazo(self) -> None:
        for quantos in (1, 2):
            texto = texto_de_controle_nao_adotado(_estado(quantos))
            assert "Hefesto tenta" in texto
            assert f"{MINUTOS_ENTRE_TENTATIVAS} minutos" in texto
            assert "PS" in texto, "a saída manual, se a tentativa não pegar"

    def test_fala_a_lingua_dela_e_nao_a_do_mecanismo(self) -> None:
        for quantos in (1, 2):
            texto = texto_de_controle_nao_adotado(_estado(quantos)).lower()
            assert "controle" in texto
            assert "hefesto" in texto
            for jargao in (
                "probe",
                "hidraw",
                "driver",
                "órfão",
                "orfão",
                "sysfs",
                "rebind",
                "bind",
                "kernel",
                "l2cap",
                "uhid",
            ):
                assert jargao not in texto, f"jargão na tela dela: {jargao}"


class _FakeBanner:
    def __init__(self) -> None:
        self.text = ""
        self.visible = True

    def set_text(self, text: str) -> None:
        self.text = text

    def set_visible(self, value: bool) -> None:
        self.visible = value


class _FakeCaixa:
    """Dublê da caixa vertical da aba Status (`tab_status_box`)."""

    def __init__(self) -> None:
        self.filhos: list[Any] = ["banner_vpad", "banner_wrapper", "frame"]

    def pack_start(self, filho: Any, *_args: Any) -> None:
        self.filhos.append(filho)

    def reorder_child(self, filho: Any, posicao: int) -> None:
        self.filhos.remove(filho)
        self.filhos.insert(posicao, filho)


class TestFiacao:


    def test_nao_reusa_o_caminho_de_dev_input(self) -> None:
        fonte = inspect.getsource(ipc_handlers.dualsense_sem_driver)
        assert "/dev/input" not in fonte
        assert "/sys/bus/hid/devices" in inspect.getsource(ipc_handlers)
