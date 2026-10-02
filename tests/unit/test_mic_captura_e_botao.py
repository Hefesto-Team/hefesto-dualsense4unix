"""MIC-CAPTURA-01 — o microfone que grava ela, e não o jogo.

Quatro defeitos medidos em 28/07 na máquina da mantenedora, um teste por
defeito. O que liga os quatro: **saída não é entrada**, e o produto estava
confundindo as duas em três lugares diferentes.

(A) O instalador nunca chamava a cura. `grep -c 'fix-mic' install.sh` = 0. A
    cura das camadas 1 e 2 existia pronta em `scripts/doctor.sh --fix-mic` e
    uma instalação limpa entregava o microfone mudo — é a entrega 7 da
    MIC-USB-01, aberta desde 25/07.

(B) O check do microfone dava FALSO POSITIVO. O filtro do `doctor.sh` casava
    qualquer rota do WirePlumber cujo nome tivesse "dualsense", e a única
    rota muda do arquivo desta máquina era
    `...DualSense...:output:analog-output` — o ALTO-FALANTE. O portão
    reprovava o microfone por causa da caixa de som, e essa linha [FAIL]
    levou dois levantamentos do mesmo dia a conclusões opostas.

(C) `ipc_bridge.mic_set` estava escrita, documentada com o ponto exato de
    fiação, e sem um único chamador na interface. O único caminho para
    desmutar o microfone era o botão físico do controle.

(D) `escolher_fonte` só procurava MAC em nomes `bluez_*`, e o nome que a
    ponte de mic por Bluetooth deste projeto publica é
    `hefesto_dualsense_bt_<hex>`. Com dois controles ou mais por Bluetooth —
    o cenário-alvo declarado do projeto — o medidor NUNCA aparecia.
"""
# ruff: noqa: E501 — as amostras do `default-routes` são cópias FIÉIS do
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app import mic_monitor
from hefesto_dualsense4unix.app.mic_monitor import (
    escolher_fonte,
    fontes_dualsense,
    sufixo_da_ponte_bt,
)
from hefesto_dualsense4unix.interface.cartao_do_controle import TEXTO_BOTAO_MIC_ATIVAR, TEXTO_BOTAO_MIC_DEVOLVER, TEXTO_BOTAO_MIC_SEM_LEITURA, TEXTO_BOTAO_MIC_SILENCIAR, AcaoMic, acao_mic

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"


class TestInstaladorChamaACura:
    """Entrega 7 da MIC-USB-01, aberta em 25/07 e nunca feita."""

    def test_o_install_chama_o_fix_mic(self) -> None:
        texto = INSTALL.read_text(encoding="utf-8")
        assert "--fix-mic" in texto, (
            "o instalador precisa chamar scripts/doctor.sh --fix-mic; sem isso "
            "uma instalação limpa deixa o microfone mudo com a cura pronta no "
            "repositório e ninguém a chamando"
        )

    def test_a_cura_e_best_effort_e_nao_derruba_a_instalacao(self) -> None:
        """A chamada mora num `if`, que é o que impede o `set -e` de abortar."""
        linhas = INSTALL.read_text(encoding="utf-8").splitlines()
        chamadas = [
            ln.strip()
            for ln in linhas
            if "--fix-mic" in ln and 'bash "${ROOT_DIR}/scripts/doctor.sh"' in ln
        ]
        assert chamadas, "nenhuma chamada ao doctor.sh --fix-mic no install.sh"
        for despido in chamadas:
            assert despido.startswith(("if ", "elif ")) or "||" in despido, (
                f"chamada sem guarda de best-effort: {despido!r}"
            )

    def test_a_cura_nao_roda_quando_a_source_foi_desabilitada_de_proposito(
        self,
    ) -> None:
        """`--with-wireplumber-disable-mic` desliga a source DE PROPÓSITO."""
        texto = INSTALL.read_text(encoding="utf-8")
        chamada = texto.index('bash "${ROOT_DIR}/scripts/doctor.sh" --fix-mic')
        antes = texto[:chamada]
        guarda = antes.rindex('if [[ "${WITH_WIREPLUMBER_DISABLE_MIC}" -ne 1 ]]')
        assert guarda > antes.rindex('step "10/11"'), (
            "a cura precisa estar dentro do passo de áudio e fora do caminho "
            "que desabilita a source a pedido da usuária"
        )

    def test_a_cura_entra_no_passo_de_audio_que_ja_existe(self) -> None:
        """Nada de passo novo: 10/11 é o passo de áudio e continua sendo."""
        texto = INSTALL.read_text(encoding="utf-8")
        assert texto.index('step "10/11"') < texto.index("--fix-mic")
        assert texto.index("--fix-mic") < texto.index('step "11/11"')


def _rodar_doctor(
    func: str, *args: str, home: str = "/nao-existe"
) -> subprocess.CompletedProcess[str]:
    """Executa uma função shell REAL do doctor (source, sem rodar o main)."""
    linha = " ".join([func, *[f'"{a}"' for a in args]])
    return subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"; {linha}'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PATH": "/usr/bin:/bin", "DOCTOR_SH": str(DOCTOR), "HOME": home},
    )


_ROTAS_SO_A_SAIDA_MUDA = """\
[default-routes]
alsa_card.pci-0000_0a_00.1:output:hdmi-output-0={"channelMap":["FL", "FR"], "mute":false}
alsa_card.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00:input:iec958-stereo-input={"channelVolumes":[1.000000], "mute":false}
alsa_card.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00:output:analog-output={"channelVolumes":[0.063997], "mute":true}
alsa_card.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00:profile:output:analog-surround-40+input:analog-stereo={"mute":true}
"""

_ROTA_SAIDA = (
    "alsa_card.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00:output:analog-output"
)
_ROTA_CAPTURA = (
    "alsa_card.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00:input:iec958-stereo-input"
)


class TestSaidaNaoEEntrada:
    def test_o_alto_falante_mudo_nao_conta_como_microfone_mudo(
        self, tmp_path: Path
    ) -> None:
        """O DEFEITO (B), em uma linha: era isto que dava [FAIL] de mic."""
        arq = tmp_path / "default-routes"
        arq.write_text(_ROTAS_SO_A_SAIDA_MUDA, encoding="utf-8")
        res = _rodar_doctor("_dualsense_rotas_mudas", str(arq))
        assert res.returncode == 0, res.stderr
        assert res.stdout.strip("\n") == "", (
            "só o ALTO-FALANTE está mudo neste arquivo; a consulta de "
            "microfone tem que sair vazia"
        )

    def test_a_rota_de_saida_continua_visivel_quando_perguntada(
        self, tmp_path: Path
    ) -> None:
        """Separar não é esconder: o fato da saída continua consultável."""
        arq = tmp_path / "default-routes"
        arq.write_text(_ROTAS_SO_A_SAIDA_MUDA, encoding="utf-8")
        res = _rodar_doctor("_dualsense_rotas_mudas", str(arq), "output")
        assert res.stdout.strip("\n").splitlines() == [_ROTA_SAIDA]

    def test_a_rota_de_captura_muda_continua_sendo_achada(
        self, tmp_path: Path
    ) -> None:
        """A cura não pode cegar o check para o defeito que ele existe p/ ver."""
        arq = tmp_path / "default-routes"
        arq.write_text(
            _ROTAS_SO_A_SAIDA_MUDA.replace(
                '[1.000000], "mute":false', '[1.000000], "mute":true'
            ),
            encoding="utf-8",
        )
        res = _rodar_doctor("_dualsense_rotas_mudas", str(arq))
        assert res.stdout.strip("\n").splitlines() == [_ROTA_CAPTURA]

    def test_a_entrada_de_perfil_nao_e_confundida_com_rota_de_captura(
        self, tmp_path: Path
    ) -> None:
        """`...:profile:output:...+input:analog-stereo` NÃO é rota de captura."""
        arq = tmp_path / "default-routes"
        arq.write_text(_ROTAS_SO_A_SAIDA_MUDA, encoding="utf-8")
        res = _rodar_doctor("_dualsense_rotas_mudas", str(arq))
        assert "profile" not in res.stdout

    def test_o_veredito_do_check_deixa_de_ser_fail(self, tmp_path: Path) -> None:
        """Ponta a ponta: o check inteiro, com o arquivo real desta máquina."""
        estado = tmp_path / ".local" / "state" / "wireplumber"
        estado.mkdir(parents=True)
        (estado / "default-routes").write_text(
            _ROTAS_SO_A_SAIDA_MUDA, encoding="utf-8"
        )
        res = _rodar_doctor("check_mic_mute_persistido", home=str(tmp_path))
        assert "[FAIL]" not in res.stdout, res.stdout
        assert "[ OK ]" in res.stdout
        assert "ALTO-FALANTE" in res.stdout, (
            "o alto-falante mudo é um fato e some é pior — ele vira INFO"
        )


class TestAcaoDoBotaoDeMicrofone:
    """A tabela dos quatro estados — o que o clique MANDA em cada um."""

    def test_firmware_mudo_oferece_ativar_e_manda_false(self) -> None:
        acao = acao_mic({"audio": {"mic_mudo": True, "mic_mudo_desejado": None}})
        assert acao.rotulo == TEXTO_BOTAO_MIC_ATIVAR
        assert acao.valor is False
        assert acao.sensivel is True

    def test_ativo_com_posse_do_kernel_oferece_silenciar_e_manda_true(self) -> None:
        acao = acao_mic({"audio": {"mic_mudo": False, "mic_mudo_desejado": None}})
        assert acao.rotulo == TEXTO_BOTAO_MIC_SILENCIAR
        assert acao.valor is True

    def test_ativo_com_posse_nossa_oferece_devolver_e_manda_none(self) -> None:
        """Sem esta saída, o primeiro clique sequestraria o botão FÍSICO."""
        acao = acao_mic({"audio": {"mic_mudo": False, "mic_mudo_desejado": False}})
        assert acao.rotulo == TEXTO_BOTAO_MIC_DEVOLVER
        assert acao.valor is None
        assert acao.sensivel is True

    def test_none_de_devolver_e_diferente_de_none_de_sem_leitura(self) -> None:
        """`valor=None` só vale quando `sensivel` — os dois usam None."""
        sem_leitura = acao_mic({})
        assert sem_leitura.valor is None
        assert sem_leitura.sensivel is False
        assert sem_leitura.rotulo == TEXTO_BOTAO_MIC_SEM_LEITURA

    @pytest.mark.parametrize(
        "entrada",
        [None, {}, {"audio": None}, {"audio": {}}, {"audio": {"mic_mudo": "sim"}}],
    )
    def test_sem_leitura_o_botao_fica_insensivel_em_vez_de_sumir(
        self, entrada: Any
    ) -> None:
        acao = acao_mic(entrada)
        assert acao == AcaoMic(
            TEXTO_BOTAO_MIC_SEM_LEITURA, None, False, acao.dica
        )
        assert acao.dica

    def test_o_ciclo_passa_por_todos_os_estados(self) -> None:
        """Um botão só, e nenhum estado fica inalcançável."""
        rotulos = [
            acao_mic({"audio": a}).rotulo
            for a in (
                {"mic_mudo": True, "mic_mudo_desejado": None},
                {"mic_mudo": False, "mic_mudo_desejado": False},
                {"mic_mudo": False, "mic_mudo_desejado": None},
            )
        ]
        assert rotulos == [
            TEXTO_BOTAO_MIC_ATIVAR,
            TEXTO_BOTAO_MIC_DEVOLVER,
            TEXTO_BOTAO_MIC_SILENCIAR,
        ]


_PACTL_DOIS_CONTROLES_POR_BT = (
    "40\thefesto_dualsense_bt_112233\tPipeWire\ts16le 1ch 16000Hz\tIDLE\n"
    "41\thefesto_dualsense_bt_445566\tPipeWire\ts16le 1ch 16000Hz\tIDLE\n"
    "42\talsa_output.pci-0000_0a_00.1.hdmi-stereo.monitor\tPipeWire\t-\tIDLE\n"
)


class TestFonteDaPonteBluetooth:
    def test_a_source_da_ponte_e_descoberta(self) -> None:
        assert fontes_dualsense(_PACTL_DOIS_CONTROLES_POR_BT) == [
            "hefesto_dualsense_bt_112233",
            "hefesto_dualsense_bt_445566",
        ]

    def test_cada_controle_casa_com_a_sua_propria_source(self) -> None:
        """O DEFEITO (D): com 2+ controles por BT o medidor nunca aparecia."""
        fontes = fontes_dualsense(_PACTL_DOIS_CONTROLES_POR_BT)
        uniqs = ["aa:bb:cc:11:22:33", "aa:bb:cc:44:55:66"]
        assert escolher_fonte(fontes, uniqs[0], uniqs) == (
            "hefesto_dualsense_bt_112233"
        )
        assert escolher_fonte(fontes, uniqs[1], uniqs) == (
            "hefesto_dualsense_bt_445566"
        )

    def test_controle_sem_source_publicada_continua_sem_medidor(self) -> None:
        """Ausência é resposta: nada de apontar a source do vizinho."""
        fontes = fontes_dualsense(_PACTL_DOIS_CONTROLES_POR_BT)
        uniqs = ["aa:bb:cc:11:22:33", "aa:bb:cc:44:55:66", "aa:bb:cc:77:88:99"]
        assert escolher_fonte(fontes, uniqs[2], uniqs) is None

    def test_o_prefixo_do_nome_nao_vira_mac_por_acidente(self) -> None:
        """`hefesto_dualsense_bt_` é cheio de letras hex (e, f, d, a, b)."""
        assert sufixo_da_ponte_bt("hefesto_dualsense_bt_112233") == "112233"
        assert mic_monitor._so_hex("hefesto_dualsense_bt_112233") != "aabbcc"

    @pytest.mark.parametrize(
        "nome",
        [
            "hefesto_dualsense_bt_hidraw3",
            "hefesto_dualsense_bt_abc",
            "hefesto_dualsense_bt_",
            "alsa_input.usb-Sony_Interactive_Entertainment_DualSense-00.mono",
            "bluez_input.AA_BB_CC_11_22_33",
        ],
    )
    def test_nome_que_nao_carrega_mac_nao_vira_sufixo(self, nome: str) -> None:
        assert sufixo_da_ponte_bt(nome) == ""

    def test_o_fallback_sem_mac_nao_casa_com_controle_nenhum(self) -> None:
        """Dois controles e um nome sem MAC: o certo é não exibir nada."""
        fontes = ["hefesto_dualsense_bt_hidraw3", "hefesto_dualsense_bt_hidraw4"]
        uniqs = ["aa:bb:cc:11:22:33", "aa:bb:cc:44:55:66"]
        assert escolher_fonte(fontes, uniqs[0], uniqs) is None

    def test_o_bluez_continua_ganhando_quando_existe(self) -> None:
        """A regra do MAC inteiro vem primeiro e não foi mexida."""
        fontes = ["hefesto_dualsense_bt_112233", "bluez_input.AA_BB_CC_11_22_33"]
        uniqs = ["aa:bb:cc:11:22:33", "aa:bb:cc:44:55:66"]
        assert escolher_fonte(fontes, uniqs[0], uniqs) == (
            "bluez_input.AA_BB_CC_11_22_33"
        )

    def test_um_para_um_continua_valendo(self) -> None:
        """A regra 3 (uma source, um controle) não pode ter sido comida."""
        fontes = ["alsa_input.usb-Sony_DualSense-00.analog-stereo"]
        assert escolher_fonte(fontes, "aa:bb", ["aa:bb"]) == fontes[0]
