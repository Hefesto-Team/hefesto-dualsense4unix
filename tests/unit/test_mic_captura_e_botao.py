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
# arquivo desta máquina; quebrar as linhas mudaria o dado sob teste.
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
from hefesto_dualsense4unix.app.widgets import controller_card
from hefesto_dualsense4unix.app.widgets.controller_card import (
    TEXTO_BOTAO_MIC_ATIVAR,
    TEXTO_BOTAO_MIC_DEVOLVER,
    TEXTO_BOTAO_MIC_SEM_LEITURA,
    TEXTO_BOTAO_MIC_SILENCIAR,
    AcaoMic,
    ControllerCard,
    acao_mic,
)

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = RAIZ / "install.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"


# ---------------------------------------------------------------------------
# (A) o instalador chama a cura
# ---------------------------------------------------------------------------


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
        """A chamada mora num `if`, que é o que impede o `set -e` de abortar.

        O instalador roda com `set -euo pipefail`: um `bash doctor.sh --fix-mic`
        solto abortaria a instalação inteira quando o doctor saísse != 0 — e ele
        sai != 0 a cada FAIL. A regra da casa para este passo é best-effort.
        """
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


# ---------------------------------------------------------------------------
# (B) o falso positivo do alto-falante
# ---------------------------------------------------------------------------


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


#: Cópia FIEL do `~/.local/state/wireplumber/default-routes` desta máquina em
#: 28/07 — a rota muda é a de SAÍDA (o alto-falante do controle) e a de
#: captura está intacta. Era este arquivo que produzia o [FAIL] de microfone.
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
        """`...:profile:output:...+input:analog-stereo` NÃO é rota de captura.

        O `+input:` (com `+`, não com `:`) mora dentro do NOME do perfil. Um
        filtro que casasse "input" solto reabriria o mesmo falso positivo por
        outra porta.
        """
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


# ---------------------------------------------------------------------------
# (C) o botão do microfone, fiado ao mic_set que já existia
# ---------------------------------------------------------------------------


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
        """Sem esta saída, o primeiro clique sequestraria o botão FÍSICO.

        `mic_set(False)` desmuta E toma a posse do registrador: enquanto ela
        durar, o botão de microfone do controle deixa de valer. Um botão que
        só soubesse mutar/desmutar tiraria o botão físico dela para sempre.
        """
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
        """Um botão só, e nenhum estado fica inalcançável.

        mudo --Ativar--> ativo/posse nossa --Devolver--> ativo/posse do
        kernel --Silenciar--> mudo. Nenhum canto sem saída.
        """
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


@pytest.mark.skipif(
    not controller_card._GTK_DISPONIVEL, reason="sem GTK3 real neste ambiente"
)
class TestFiacaoDoBotaoNoCard:
    """O DEFEITO (C): o método existia e ninguém o chamava."""

    def _card_com(
        self, monkeypatch: pytest.MonkeyPatch, entry: dict[str, Any]
    ) -> tuple[Any, list[tuple[Any, ...]]]:
        pedidos: list[tuple[Any, ...]] = []

        def _mic_set(muted: bool | None, uniq: str | None = None) -> bool:
            pedidos.append((muted, uniq))
            return True

        monkeypatch.setattr(controller_card.ipc_bridge, "mic_set", _mic_set)
        # `run_in_thread` real precisa de GLib.idle_add e de um laço vivo; o
        # dublê roda a função na hora e mantém o teste determinístico.
        monkeypatch.setattr(
            controller_card.ipc_bridge,
            "run_in_thread",
            lambda fn, on_success, on_failure=None: on_success(fn()),
        )
        card = ControllerCard(compact=False)
        card.update(entry, {})
        return card, pedidos

    def test_o_clique_chega_no_mic_set_com_o_uniq_do_card(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        card, pedidos = self._card_com(
            monkeypatch,
            {
                "uniq": "AA:BB:CC:DD:EE:FF",
                "audio": {"mic_mudo": True, "mic_mudo_desejado": None},
            },
        )
        card._mic_botao.clicked()
        assert pedidos == [(False, "AA:BB:CC:DD:EE:FF")], (
            "o botão precisa mandar DESMUTAR e ir só no controle deste card — "
            "sem o uniq o daemon aplicaria no primário e com quatro controles "
            "isso mutaria o microfone de outra pessoa"
        )

    def test_o_clique_no_estado_ativo_manda_mutar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        card, pedidos = self._card_com(
            monkeypatch,
            {"uniq": "AA:BB:CC:11:22:33", "audio": {"mic_mudo": False}},
        )
        card._mic_botao.clicked()
        assert pedidos == [(True, "AA:BB:CC:11:22:33")]

    def test_o_clique_com_posse_nossa_devolve_o_botao_fisico(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        card, pedidos = self._card_com(
            monkeypatch,
            {
                "uniq": "AA:BB:CC:11:22:33",
                "audio": {"mic_mudo": False, "mic_mudo_desejado": False},
            },
        )
        card._mic_botao.clicked()
        assert pedidos == [(None, "AA:BB:CC:11:22:33")]

    def test_sem_leitura_o_botao_esta_insensivel_e_nao_manda_nada(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        card, pedidos = self._card_com(monkeypatch, {"uniq": "AA:BB:CC:11:22:33"})
        assert card._mic_botao.get_sensitive() is False
        card._mic_botao.clicked()
        assert pedidos == []

    def test_o_bloco_do_mic_continua_sempre_visivel(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MIC-PRESENTE-01 não pode ser desfeita por esta entrega."""
        card, _ = self._card_com(monkeypatch, {"uniq": "AA:BB:CC:11:22:33"})
        card.show_all()
        assert card._mic_box.get_visible() is True
        assert card._mic_botao.get_visible() is True
        card.reset_inputs()
        assert card._mic_box.get_visible() is True
        assert card._mic_botao.get_visible() is True
        assert card._mic_botao_rotulo.get_text() == TEXTO_BOTAO_MIC_SEM_LEITURA

    def test_o_botao_reflete_a_leitura_do_daemon_e_nao_o_que_mandamos(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Guardar o valor mandado como leitura é o hábito que a sprint veta."""
        card, _ = self._card_com(
            monkeypatch,
            {"uniq": "AA:BB:CC:11:22:33", "audio": {"mic_mudo": True}},
        )
        card._mic_botao.clicked()
        # O daemon ainda não confirmou: o rótulo continua o do estado LIDO.
        assert card._mic_botao_rotulo.get_text() == TEXTO_BOTAO_MIC_ATIVAR
        card.update(
            {
                "uniq": "AA:BB:CC:11:22:33",
                "audio": {"mic_mudo": False, "mic_mudo_desejado": False},
            },
            {},
        )
        assert card._mic_botao_rotulo.get_text() == TEXTO_BOTAO_MIC_DEVOLVER


# ---------------------------------------------------------------------------
# (D) a source da ponte de mic por Bluetooth
# ---------------------------------------------------------------------------


_PACTL_DOIS_CONTROLES_POR_BT = (
    "40\thefesto_dualsense_bt_aabbcc\tPipeWire\ts16le 1ch 16000Hz\tIDLE\n"
    "41\thefesto_dualsense_bt_112233\tPipeWire\ts16le 1ch 16000Hz\tIDLE\n"
    "42\talsa_output.pci-0000_0a_00.1.hdmi-stereo.monitor\tPipeWire\t-\tIDLE\n"
)


class TestFonteDaPonteBluetooth:
    def test_a_source_da_ponte_e_descoberta(self) -> None:
        assert fontes_dualsense(_PACTL_DOIS_CONTROLES_POR_BT) == [
            "hefesto_dualsense_bt_aabbcc",
            "hefesto_dualsense_bt_112233",
        ]

    def test_cada_controle_casa_com_a_sua_propria_source(self) -> None:
        """O DEFEITO (D): com 2+ controles por BT o medidor nunca aparecia."""
        fontes = fontes_dualsense(_PACTL_DOIS_CONTROLES_POR_BT)
        uniqs = ["e8:47:3a:aa:bb:cc", "e8:47:3a:11:22:33"]
        assert escolher_fonte(fontes, uniqs[0], uniqs) == (
            "hefesto_dualsense_bt_aabbcc"
        )
        assert escolher_fonte(fontes, uniqs[1], uniqs) == (
            "hefesto_dualsense_bt_112233"
        )

    def test_controle_sem_source_publicada_continua_sem_medidor(self) -> None:
        """Ausência é resposta: nada de apontar a source do vizinho."""
        fontes = fontes_dualsense(_PACTL_DOIS_CONTROLES_POR_BT)
        uniqs = ["e8:47:3a:aa:bb:cc", "e8:47:3a:11:22:33", "e8:47:3a:99:88:77"]
        assert escolher_fonte(fontes, uniqs[2], uniqs) is None

    def test_o_prefixo_do_nome_nao_vira_mac_por_acidente(self) -> None:
        """`hefesto_dualsense_bt_` é cheio de letras hex (e, f, d, a, b).

        Filtrar hex do nome INTEIRO produziria um "MAC" com lixo do prefixo
        grudado na frente — casamento por acaso, que é o beco que a regra do
        `bluez_*` já evitava de propósito.
        """
        assert sufixo_da_ponte_bt("hefesto_dualsense_bt_aabbcc") == "aabbcc"
        assert mic_monitor._so_hex("hefesto_dualsense_bt_aabbcc") != "aabbcc"

    @pytest.mark.parametrize(
        "nome",
        [
            "hefesto_dualsense_bt_hidraw3",  # fallback: nó sem HID_UNIQ
            "hefesto_dualsense_bt_abc",  # curto demais para identificar
            "hefesto_dualsense_bt_",
            "alsa_input.usb-Sony_Interactive_Entertainment_DualSense-00.mono",
            "bluez_input.E8_47_3A_AA_BB_CC",
        ],
    )
    def test_nome_que_nao_carrega_mac_nao_vira_sufixo(self, nome: str) -> None:
        assert sufixo_da_ponte_bt(nome) == ""

    def test_o_fallback_sem_mac_nao_casa_com_controle_nenhum(self) -> None:
        """Dois controles e um nome sem MAC: o certo é não exibir nada."""
        fontes = ["hefesto_dualsense_bt_hidraw3", "hefesto_dualsense_bt_hidraw4"]
        uniqs = ["e8:47:3a:aa:bb:cc", "e8:47:3a:11:22:33"]
        assert escolher_fonte(fontes, uniqs[0], uniqs) is None

    def test_o_bluez_continua_ganhando_quando_existe(self) -> None:
        """A regra do MAC inteiro vem primeiro e não foi mexida."""
        fontes = ["hefesto_dualsense_bt_aabbcc", "bluez_input.E8_47_3A_AA_BB_CC"]
        uniqs = ["e8:47:3a:aa:bb:cc", "e8:47:3a:11:22:33"]
        assert escolher_fonte(fontes, uniqs[0], uniqs) == (
            "bluez_input.E8_47_3A_AA_BB_CC"
        )

    def test_um_para_um_continua_valendo(self) -> None:
        """A regra 3 (uma source, um controle) não pode ter sido comida."""
        fontes = ["alsa_input.usb-Sony_DualSense-00.analog-stereo"]
        assert escolher_fonte(fontes, "aa:bb", ["aa:bb"]) == fontes[0]
