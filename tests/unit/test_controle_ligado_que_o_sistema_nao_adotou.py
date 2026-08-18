"""CONTROLE-QUE-NAO-ENTROU-01 (09/08/2026) — a janela mentia sobre um controle.

Medido na máquina dela: **dois** DualSense ligados e pareados, e a janela
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

# GI-REAL-01: este módulo importa `app/`, que sobe PyGObject no import.
# Sem esta guarda ele não COLETA num runner sem GTK, e o censo de coleta
# do `ci.yml` reprova a leva inteira. Medido em 13/08/2026: era um dos
# três módulos que derrubavam o `lint-test` nas três versões de Python.
exigir_gi_real("controle ligado que o sistema não adotou (importa app.actions.status_actions)")

from hefesto_dualsense4unix.app.actions.status_actions import (
    MINUTOS_ENTRE_TENTATIVAS,
    POSICAO_DO_BANNER_NAO_ADOTADO,
    StatusActionsMixin,
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

# Os mesmos dublês do `test_bt_rebind_orphans.py`, e de propósito: as duas
# leituras da MESMA regra têm de concordar sobre os mesmos devices.
ORFAO_NO_ESCOPO = "0005:054C:0CE6.000F"       # DualSense por Bluetooth
ORFAO_NO_ESCOPO_2 = "0005:054C:0CE6.0011"     # o segundo da mesa dela
ORFAO_FORA_ESCOPO = "0003:057E:2009.0001"     # Pro Controller por USB
VPAD_COM_DRIVER = "0003:054C:0DF2.0010"       # vpad do hefesto (uhid, bus 0003)
DUALSENSE_ADOTADO = "0005:054C:0CE6.000A"     # o que subiu bem: TEM driver


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


# ---------------------------------------------------------------------------
# 1. A leitura do sistema
# ---------------------------------------------------------------------------


class TestLeituraDoSistema:
    def test_acha_o_controle_que_perdeu_a_probe(self, tmp_path: Path) -> None:
        dir_ = _monta_sysfs(tmp_path, [ORFAO_NO_ESCOPO], [])
        assert dualsense_sem_driver(dir_) == [ORFAO_NO_ESCOPO]

    def test_a_mesa_dela_dois_ligados_um_visivel(self, tmp_path: Path) -> None:
        # O caso medido: um subiu, o outro abortou. A lista tem de ter UM.
        dir_ = _monta_sysfs(
            tmp_path, [ORFAO_NO_ESCOPO], [DUALSENSE_ADOTADO, VPAD_COM_DRIVER]
        )
        assert dualsense_sem_driver(dir_) == [ORFAO_NO_ESCOPO]

    def test_o_que_tem_driver_nunca_conta(self, tmp_path: Path) -> None:
        # Contar quem TEM driver faria a janela avisar sobre o controle que
        # está funcionando — e sobre o gamepad virtual do próprio Hefesto.
        dir_ = _monta_sysfs(tmp_path, [], [DUALSENSE_ADOTADO, VPAD_COM_DRIVER])
        assert dualsense_sem_driver(dir_) == []

    def test_orfao_alheio_nao_e_nosso(self, tmp_path: Path) -> None:
        # A cura automática (`bt_rebind_orphans.sh`) NÃO toca em device de
        # outro fabricante. Avisar sobre ele seria prometer uma cura que não
        # vem — o aviso diz "o Hefesto tenta sozinho".
        dir_ = _monta_sysfs(tmp_path, [ORFAO_FORA_ESCOPO], [])
        assert dualsense_sem_driver(dir_) == []

    def test_dois_orfaos_saem_ordenados(self, tmp_path: Path) -> None:
        dir_ = _monta_sysfs(
            tmp_path, [ORFAO_NO_ESCOPO_2, ORFAO_NO_ESCOPO], []
        )
        assert dualsense_sem_driver(dir_) == [ORFAO_NO_ESCOPO, ORFAO_NO_ESCOPO_2]

    def test_sysfs_ausente_nao_derruba_a_aba(self, tmp_path: Path) -> None:
        # Este caminho roda dentro do `state_full`: um OSError aqui derrubaria
        # a aba Status inteira por causa da linha menos importante dela.
        assert dualsense_sem_driver(str(tmp_path / "nao-existe")) == []

    def test_nome_de_device_torto_nao_explode(self, tmp_path: Path) -> None:
        dir_ = _monta_sysfs(tmp_path, ["lixo", "0005", "0005:054C"], [])
        assert dualsense_sem_driver(dir_) == []


# ---------------------------------------------------------------------------
# 2. O dono único da regra
# ---------------------------------------------------------------------------


class TestUmDonoSoDaRegra:
    """A regra é do `bt_rebind_orphans.sh`. Aqui só a LEMOS para exibir.

    Se as duas leituras divergirem, a janela passa a avisar sobre um controle
    que a cura automática não vai tentar — ou a calar sobre um que ela vai. O
    defeito que esta casa mais persegue é justamente o segundo dono.
    """

    def test_o_escopo_e_o_mesmo_do_script(self) -> None:
        texto = SCRIPT.read_text(encoding="utf-8")
        assert f'"${{bus}}" == "{_HID_ORFAO_BUS}"' in texto
        assert f'"${{vid}}" == "{_HID_ORFAO_VID}"' in texto

    def test_o_criterio_e_a_ausencia_do_symlink_driver(self) -> None:
        texto = SCRIPT.read_text(encoding="utf-8")
        # No script: `[[ -e "${dev}/driver" ]] && continue`.
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
        # A tela promete "em até N minutos". Quem cumpre é o timer do
        # watchdog, que chama o `bt_rebind_orphans.sh`. Um número escolhido a
        # gosto aqui viraria promessa falsa no dia em que o timer mudasse.
        texto = TIMER.read_text(encoding="utf-8")
        achado = re.search(r"OnUnitActiveSec=(\d+)min", texto)
        assert achado is not None, "o timer precisa dizer o intervalo em min"
        assert int(achado.group(1)) == MINUTOS_ENTRE_TENTATIVAS

    def test_o_watchdog_realmente_chama_a_cura(self) -> None:
        watchdog = (REPO_ROOT / "scripts" / "bt_health_watchdog.sh").read_text(
            encoding="utf-8"
        )
        assert "bt_rebind_orphans.sh" in watchdog


# ---------------------------------------------------------------------------
# 3. O dado no IPC
# ---------------------------------------------------------------------------


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
        """O payload real, com o sysfs apontado para o diretório temporário.

        O `monkeypatch` mira a CONSTANTE do módulo (e não o default da
        função) porque é ela o único lugar onde o caminho está escrito — a
        `dualsense_sem_driver` a resolve na hora da chamada exatamente para
        isto ser possível sem um segundo dono do caminho.
        """
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
        # O nome do diretório é BUS:VID:PID.INSTANCIA — não há MAC nele, e
        # este payload atravessa o IPC e pode acabar num log colado por ela.
        dir_ = _monta_sysfs(tmp_path, [ORFAO_NO_ESCOPO], [])
        for id_ in self._payload(dir_, monkeypatch)["ids"]:
            assert not re.search(r"([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}", id_)

    def test_o_state_full_publica_a_chave(self) -> None:
        # Fiação: a chave existe no handler e vem do método (nunca inline).
        fonte = inspect.getsource(
            ipc_handlers.IpcHandlersMixin._handle_daemon_state_full
        )
        assert (
            'result["controles_sem_driver"] = '
            "self._controles_sem_driver_payload()" in fonte
        )


# ---------------------------------------------------------------------------
# 4. A tela
# ---------------------------------------------------------------------------


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
        # `True` entra na lista de propósito: em Python `isinstance(True, int)`
        # é verdadeiro, e um bool aqui viraria "1 controle" fantasma.
        assert texto_de_controle_nao_adotado(_estado(torto)) == ""

    def test_bloco_torto_nao_acende(self) -> None:
        assert texto_de_controle_nao_adotado({"controles_sem_driver": 2}) == ""

    def test_promete_a_cura_automatica_e_o_prazo(self) -> None:
        # Não assustar sem dar saída: a cura existe, é automática, e o texto
        # tem de dizer em quanto tempo — senão ela desliga o controle bom
        # para "resolver".
        for quantos in (1, 2):
            texto = texto_de_controle_nao_adotado(_estado(quantos))
            assert "Hefesto tenta" in texto
            assert f"{MINUTOS_ENTRE_TENTATIVAS} minutos" in texto
            assert "PS" in texto, "a saída manual, se a tentativa não pegar"

    def test_fala_a_lingua_dela_e_nao_a_do_mecanismo(self) -> None:
        # A dona recusa nome que não deriva do que já existe na tela.
        # "controle", "ligado", "Hefesto" são o léxico dela; o resto descreve
        # o mecanismo, e o mecanismo não é o que ela vê.
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


# ---------------------------------------------------------------------------
# 5. A fiação na aba Status
# ---------------------------------------------------------------------------


class _FakeBanner:
    def __init__(self) -> None:
        self.text = ""
        self.visible = True  # sobra visível: o refresh precisa apagar

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


def _stub(banner: _FakeBanner | None) -> Any:
    class _Stub:
        _refresh_banner_nao_adotado = (
            StatusActionsMixin._refresh_banner_nao_adotado
        )
        _banner_nao_adotado = banner

    return _Stub()


class TestOBannerNaAbaStatus:
    def test_acende_com_o_texto_certo(self) -> None:
        banner = _FakeBanner()
        _stub(banner)._refresh_banner_nao_adotado(_estado(1))
        assert banner.visible is True
        assert banner.text == texto_de_controle_nao_adotado(_estado(1))

    def test_apaga_quando_o_controle_volta(self) -> None:
        banner = _FakeBanner()
        _stub(banner)._refresh_banner_nao_adotado(_estado(0))
        assert banner.visible is False

    def test_apaga_com_o_daemon_sem_resposta(self) -> None:
        banner = _FakeBanner()
        _stub(banner)._refresh_banner_nao_adotado(None)
        assert banner.visible is False

    def test_sem_widget_nao_explode(self) -> None:
        _stub(None)._refresh_banner_nao_adotado(_estado(1))  # não levanta

    def test_o_aviso_nasce_acima_dos_cards(self) -> None:
        # Sem a reordenação, o `pack_start` empurra o aviso para o FIM da
        # caixa vertical — abaixo dos cards, que é onde ninguém procura o
        # motivo de um controle estar faltando.
        caixa = _FakeCaixa()

        class _Host:
            _montar_banner_nao_adotado = (
                StatusActionsMixin._montar_banner_nao_adotado
            )

            def _get(self, nome: str) -> Any:
                from hefesto_dualsense4unix.app.actions.status_actions import (
                    ABA_STATUS,
                )

                return caixa if nome == ABA_STATUS else None

        host = _Host()
        host._montar_banner_nao_adotado()
        assert host._banner_nao_adotado is not None
        assert (
            caixa.filhos.index(host._banner_nao_adotado)
            == POSICAO_DO_BANNER_NAO_ADOTADO
        )

    def test_montagem_sem_caixa_nao_explode(self) -> None:
        class _Host:
            _montar_banner_nao_adotado = (
                StatusActionsMixin._montar_banner_nao_adotado
            )

            def _get(self, _nome: str) -> Any:
                return None

        _Host()._montar_banner_nao_adotado()  # não levanta


class TestFiacao:
    def test_o_tique_lento_acende_e_o_offline_apaga(self) -> None:
        lento = inspect.getsource(StatusActionsMixin._render_slow_state)
        assert "_refresh_banner_nao_adotado(state)" in lento
        offline = inspect.getsource(StatusActionsMixin._render_offline)
        assert "_refresh_banner_nao_adotado(None)" in offline

    def test_a_montagem_entra_no_install(self) -> None:
        fonte = inspect.getsource(StatusActionsMixin.install_status_polling)
        assert "_montar_banner_nao_adotado()" in fonte

    def test_nao_reusa_o_caminho_de_dev_input(self) -> None:
        # O contador de externos lê /dev/input, que TAMBÉM não existe quando a
        # probe aborta. Reusar aquele caminho daria zero — e zero é
        # indistinguível de "não há problema nenhum".
        fonte = inspect.getsource(ipc_handlers.dualsense_sem_driver)
        assert "/dev/input" not in fonte
        assert "/sys/bus/hid/devices" in inspect.getsource(ipc_handlers)
