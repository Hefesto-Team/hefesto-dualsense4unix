"""FONTE-PADRAO-01 — a fonte de captura padrão do sistema era um MONITOR.

MEDIDO na máquina da mantenedora em 29/07/2026, com o DualSense no cabo:

    $ pactl get-default-source
    alsa_output.usb-...DualSense...analog-surround-40.monitor

Monitor é o loopback da SAÍDA. Enquanto ele é a fonte padrão, todo aplicativo
que grava sem escolher a fonte na mão capta o som que SAI do controle — o jogo,
a música, a chamada inteira — e nunca a voz de quem fala. E o `doctor.sh` dava
[OK] para exatamente isso: o `check_wireplumber_source` tinha um `pass`
EXPLÍCITO para qualquer fonte cujo nome contivesse "monitor". O racional estava
certo pela metade (monitor não é o mic do controle, então aquele check não tem o
que reprovar) e errado na conclusão (ser a FONTE PADRÃO é defeito próprio).

Três coisas são fixadas aqui:

(1) A CURA DO `--fix-mic`, PORTADA de `84d9f4e` (que ficou só na `main`). O
    `--fix-mic` trocava o perfil da placa sempre que a entrada ativa fosse
    `iec958`, mirando `input:analog-stereo`, porque a sprint MIC-USB-01 dizia
    que o microfone "vive" na entrada analógica. Medido no hardware em 26/07: o
    perfil analógico está `available: no` e forçá-lo produz uma source SEM PORTA
    DE CAPTURA — 327.680 bytes de silêncio digital; o `iec958-stereo`, que a
    sprint mandava evitar, gravou pico 4606. A cura SILENCIAVA o microfone, e o
    `install.sh` a reaplicava a cada instalação.

(2) O PORTÃO PARA DE APROVAR O SINTOMA: monitor como fonte padrão é [FAIL], com
    cura oferecida no `--fix-mic`, e a promoção respeita os sinais EXPLÍCITOS de
    quem configurou a máquina (drop-in 52 = mic desligado de propósito;
    `DUALSENSE_MIC_INTENDED`; drop-in 51 = política default de rebaixar).

(3) O `install.sh` passa a chamar `scripts/install_fonts.sh`. Medido:
    `grep -c fonts install.sh` = 0 — o script existia, com download pinado e
    SHA-256, e ninguém o chamava.

Molde: tests/unit/test_mic_usb_01_tres_camadas.py (funções shell REAIS do
doctor, executadas por `source`; contratos de texto para a fiação) e
tests/unit/test_install_headless.py (leitura do texto do install.sh).

Nenhum teste deste arquivo toca o áudio da máquina: o `pactl` é um dublê num
diretório temporário, e o PATH do subprocesso não alcança o de verdade.
"""
# ruff: noqa: E501 — as amostras de `pactl` são cópias FIÉIS da saída desta
# máquina, e o nome do card do DualSense sozinho já passa de 100 colunas.
# Quebrar as linhas inventaria uma entrada que o parser jamais receberia, e é
# justamente o parser que está sendo testado.
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
INSTALL = RAIZ / "install.sh"
FONTS = RAIZ / "scripts" / "install_fonts.sh"

TEXTO_DOCTOR = DOCTOR.read_text(encoding="utf-8")
TEXTO_INSTALL = INSTALL.read_text(encoding="utf-8")

DROPIN_51 = "51-hefesto-dualsense-no-default-source.conf"
DROPIN_52 = "52-hefesto-dualsense-disable-source.conf"

SRC_DS = (
    "alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.iec958-stereo"
)
MONITOR_DS = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40.monitor"
)
SRC_ONBOARD = "alsa_input.pci-0000_0c_00.4.analog-stereo"
CARD_DS = (
    "alsa_card.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00"
)


# ---------------------------------------------------------------------------
# Amostras — cópias de `LC_ALL=C pactl ...` desta máquina em 29/07/2026
# ---------------------------------------------------------------------------

#: `pactl list sources short`. A fonte padrão de verdade é a 3a linha (monitor).
SOURCES_SHORT = f"""\
61\talsa_output.pci-0000_0c_00.4.iec958-stereo.monitor\tPipeWire\ts32le 2ch 48000Hz\tSUSPENDED
62\t{SRC_ONBOARD}\tPipeWire\ts32le 2ch 48000Hz\tSUSPENDED
2489\t{MONITOR_DS}\tPipeWire\ts16le 4ch 48000Hz\tSUSPENDED
2490\t{SRC_DS}\tPipeWire\ts16le 2ch 48000Hz\tRUNNING
7745\talsa_output.pci-0000_0a_00.1.hdmi-stereo.monitor\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED
"""

#: `pactl list sources` (recorte). A onboard tem porta ativa `not available`
#: (nada plugado no jack); a do DualSense tem `availability unknown` — e é ela
#: que gravou pico 4606 na medição de 26/07.
SOURCES_LONGO = f"""\
Source #62
\tState: SUSPENDED
\tName: {SRC_ONBOARD}
\tMute: no
\tProperties:
\t\tdevice.api = "alsa"
\tPorts:
\t\tanalog-input-front-mic: Front Microphone (type: Mic, priority: 8500, availability group: Legacy 1, not available)
\t\tanalog-input-rear-mic: Rear Microphone (type: Mic, priority: 8200, availability group: Legacy 2, not available)
\tActive Port: analog-input-front-mic

Source #2489
\tState: SUSPENDED
\tName: {MONITOR_DS}
\tMute: no
\tPorts:
\tActive Port: (null)

Source #2490
\tState: RUNNING
\tName: {SRC_DS}
\tMute: no
\tProperties:
\t\tdevice.api = "alsa"
\tPorts:
\t\tiec958-stereo-input: Digital Input (S/PDIF) (type: SPDIF, priority: 0, availability unknown)
\tActive Port: iec958-stereo-input
"""

#: `pactl list cards` (recorte fiel). O perfil ATIVO é o `iec958-stereo`, que a
#: sprint MIC-USB-01 mandava evitar — e é o único com fonte de captura E
#: `available: yes`. O analógico, que a cura antiga mirava, é `available: no`.
CARDS_MEDIDO = f"""\
Card #51
\tName: alsa_card.pci-0000_0c_00.4
\tProfiles:
\t\toutput:iec958-stereo+input:analog-stereo: Duplex (sinks: 1, sources: 1, priority: 5565, available: yes)
\t\tinput:analog-stereo: Input (sinks: 0, sources: 1, priority: 65, available: no)
\tActive Profile: output:iec958-stereo+input:analog-stereo
\tPorts:
\t\tanalog-input-front-mic: Front Microphone (type: Mic, priority: 8500, not available)
\t\t\tPart of profile(s): input:analog-stereo

Card #91
\tName: {CARD_DS}
\tDriver: PipeWire
\tProperties:
\t\tdevice.bus = "usb"
\tProfiles:
\t\toff: Off (sinks: 0, sources: 0, priority: 0, available: yes)
\t\toutput:analog-surround-40+input:analog-stereo: Surround 4.0 + Input (sinks: 1, sources: 1, priority: 1265, available: no)
\t\toutput:analog-surround-40+input:iec958-stereo: Surround 4.0 + IEC958 (sinks: 1, sources: 1, priority: 1255, available: yes)
\t\toutput:analog-surround-40: Surround 4.0 (sinks: 1, sources: 0, priority: 1200, available: yes)
\t\tinput:analog-stereo: Input (sinks: 0, sources: 1, priority: 65, available: no)
\t\tinput:iec958-stereo: Digital Input (sinks: 0, sources: 1, priority: 55, available: yes)
\t\tpro-audio: Pro Audio (sinks: 1, sources: 1, priority: 1, available: yes)
\tActive Profile: output:analog-surround-40+input:iec958-stereo
\tPorts:
\t\tanalog-input-headset-mic: Headset Microphone (type: Headset, priority: 8800, availability group: Legacy 1, not available)
\t\t\tPart of profile(s): input:analog-stereo, output:analog-surround-40+input:analog-stereo
\t\tiec958-stereo-input: Digital Input (S/PDIF) (type: SPDIF, priority: 0, availability unknown)
\t\t\tPart of profile(s): input:iec958-stereo, output:analog-surround-40+input:iec958-stereo
\t\tanalog-output: Analog Output (type: Analog, priority: 9900, availability unknown)
\t\t\tPart of profile(s): output:analog-surround-40, output:analog-surround-40+input:analog-stereo, output:analog-surround-40+input:iec958-stereo
"""

#: A mesma placa, com o perfil ativo SEM fonte de captura (`sources: 0`) — é o
#: caso em que a cura de fato tem de trocar de perfil.
CARDS_SEM_FONTE = CARDS_MEDIDO.replace(
    "\tActive Profile: output:analog-surround-40+input:iec958-stereo",
    "\tActive Profile: output:analog-surround-40",
)


# ---------------------------------------------------------------------------
# Execução das funções shell REAIS do doctor.sh
# ---------------------------------------------------------------------------


def _rodar(func: str, *args: str, entrada: str | None = None) -> str:
    """Executa uma função PURA do doctor (source, sem rodar o main)."""
    linha = " ".join([func, *[f'"{a}"' for a in args]])
    res = subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"; {linha}'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        input=entrada,
        env={"PATH": "/usr/bin:/bin", "DOCTOR_SH": str(DOCTOR), "HOME": "/nao-existe"},
    )
    assert res.returncode == 0, res.stderr
    return res.stdout.strip("\n")


def _rc(func: str, *args: str, entrada: str | None = None) -> int:
    """Igual ao `_rodar`, mas devolve o EXIT CODE (predicados 0/1)."""
    linha = " ".join([func, *[f'"{a}"' for a in args]])
    res = subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"; {linha}'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        input=entrada,
        env={"PATH": "/usr/bin:/bin", "DOCTOR_SH": str(DOCTOR), "HOME": "/nao-existe"},
    )
    return res.returncode


@pytest.fixture
def cenario(tmp_path: Path) -> Cenario:
    return Cenario(tmp_path)


class Cenario:
    """Máquina de mentira: HOME em tmp + `pactl` dublê no PATH.

    O dublê distingue `list sources short` de `list sources` — sem isso o nome
    da source sai vazio e a cura nem chega ao ramo que o teste diz vigiar
    (verde por não exercitar nada). Foi esse exatamente o segundo defeito
    confessado no commit `84d9f4e`, e ele fica registrado aqui.

    O PATH do subprocesso NÃO inclui o diretório do `pactl` de verdade: nenhum
    teste deste arquivo pode mexer no áudio de quem roda a suíte.
    """

    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.home = tmp_path / "home"
        self.conf = self.home / ".config" / "wireplumber" / "wireplumber.conf.d"
        self.conf.mkdir(parents=True)
        self.bin = tmp_path / "bin"
        self.bin.mkdir()
        self.log = tmp_path / "pactl.log"
        self.default_source = MONITOR_DS
        self.cards = CARDS_MEDIDO
        self.sources_short = SOURCES_SHORT
        self.sources_longo = SOURCES_LONGO

    def com_dropin(self, nome: str) -> Cenario:
        (self.conf / nome).write_text("# dublê\n", encoding="utf-8")
        return self

    def _escrever_pactl(self) -> None:
        arq_short = self.tmp / "sources_short.txt"
        arq_longo = self.tmp / "sources_longo.txt"
        arq_cards = self.tmp / "cards.txt"
        arq_short.write_text(self.sources_short, encoding="utf-8")
        arq_longo.write_text(self.sources_longo, encoding="utf-8")
        arq_cards.write_text(self.cards, encoding="utf-8")
        stub = self.bin / "pactl"
        stub.write_text(
            "#!/bin/sh\n"
            f'printf "%s\\n" "$*" >> "{self.log}"\n'
            'case "$*" in\n'
            f'  "get-default-source") printf "%s\\n" "{self.default_source}" ;;\n'
            f'  "list sources short"|"list short sources") cat "{arq_short}" ;;\n'
            f'  "list sources") cat "{arq_longo}" ;;\n'
            f'  "list cards") cat "{arq_cards}" ;;\n'
            '  "get-source-mute "*) printf "Mute: no\\n" ;;\n'
            "  *) : ;;\n"
            "esac\n"
            "exit 0\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)

    def roda(self, func: str) -> subprocess.CompletedProcess[str]:
        self._escrever_pactl()
        return subprocess.run(
            ["bash", "-c", f'set --; source "$DOCTOR_SH"; {func}'],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={
                "PATH": f"{self.bin}:/usr/bin:/bin",
                "DOCTOR_SH": str(DOCTOR),
                "HOME": str(self.home),
            },
        )

    def chamadas(self) -> list[str]:
        if not self.log.exists():
            return []
        return self.log.read_text(encoding="utf-8").splitlines()


# ---------------------------------------------------------------------------
# TAREFA 1 — a cura de `84d9f4e`, portada
# ---------------------------------------------------------------------------


class TestCuraPortadaDoFixMic:
    """A regra que a medição de 26/07 impôs: porta e `available`, não nome."""

    def test_o_iec958_ativo_e_medido_nao_pede_troca(self) -> None:
        """O estado REAL desta máquina agora: `iec958-stereo` ativo.

        A regra antiga trocaria para `input:analog-stereo` só porque o nome do
        ativo tem "iec958" — e a source nasceria sem porta de captura, com
        327.680 bytes de silêncio digital. Alvo vazio é a cura.
        """
        card, ativo, alvo = _rodar(
            "_dualsense_perfil_status", entrada=CARDS_MEDIDO
        ).split("\t")
        assert card == CARD_DS
        assert ativo == "output:analog-surround-40+input:iec958-stereo"
        assert alvo == "", (
            "o ativo oferece fonte e está `available: yes`: trocar aqui é a "
            f"cura refutada. Veio alvo={alvo!r}"
        )

    def test_o_alvo_e_filtrado_por_available(self) -> None:
        """O CONTRÁRIO exato do teste que a regra antiga tinha.

        Existiu aqui um `test_o_alvo_nao_e_filtrado_por_available`, com o
        argumento de que filtrar "deixaria o microfone embutido inalcançável
        para sempre". Quando o ALSA diz `available: no`, ele já é: forçá-lo
        entrega uma source sem porta. O analógico (prioridade 1265) perde para o
        `iec958` (1255) porque prioridade só desempata entre os DISPONÍVEIS.
        """
        assert "priority: 1265, available: no" in CARDS_SEM_FONTE, (
            "a amostra precisa manter o analógico indisponível — é o caso"
        )
        alvo = _rodar("_dualsense_perfil_status", entrada=CARDS_SEM_FONTE).split("\t")[2]
        assert alvo == "output:analog-surround-40+input:iec958-stereo", (
            f"perfil `available: no` nunca pode ser alvo; veio {alvo!r}"
        )

    def test_o_alvo_preserva_a_saida_do_controle(self) -> None:
        """Contrato antigo que CONTINUA valendo, agora pela prioridade.

        Trocar para um perfil só-de-entrada emudeceria o alto-falante/fone do
        controle e derrubaria o canal de haptic-de-áudio junto.
        """
        alvo = _rodar("_dualsense_perfil_status", entrada=CARDS_SEM_FONTE).split("\t")[2]
        assert alvo.startswith("output:"), f"o alvo tem de manter a saída; veio {alvo!r}"

    def test_active_profile_e_lido_apesar_de_vir_depois_da_lista(self) -> None:
        """O primeiro defeito confessado em `84d9f4e`.

        No `pactl` a linha `Active Profile:` vem DEPOIS da lista inteira de
        perfis. Comparar com o ativo dentro do laço fazia a guarda nunca ligar.
        Aqui a prova é indireta e suficiente: o campo `ativo` chega preenchido.
        """
        _card, ativo, _alvo = _rodar(
            "_dualsense_perfil_status", entrada=CARDS_MEDIDO
        ).split("\t")
        assert ativo != "", "o `Active Profile:` não foi capturado"

    def test_a_onboard_nao_e_confundida(self) -> None:
        so_onboard = CARDS_MEDIDO.split("Card #91")[0]
        assert "iec958" in so_onboard
        assert _rodar("_dualsense_perfil_status", entrada=so_onboard) == ""

    def test_porta_ativa_de_verdade_e_reconhecida(self) -> None:
        """A PORTA é o critério honesto de "dá para captar"."""
        assert _rc("_source_tem_porta_ativa", SRC_DS, entrada=SOURCES_LONGO) == 0

    def test_porta_nula_nao_conta(self) -> None:
        """`Active Port: (null)` é o que a cura refutada produzia."""
        assert _rc("_source_tem_porta_ativa", MONITOR_DS, entrada=SOURCES_LONGO) == 1

    def test_source_inexistente_nao_tem_porta(self) -> None:
        assert _rc("_source_tem_porta_ativa", "alsa_input.fantasma", entrada=SOURCES_LONGO) == 1

    def test_a_cura_nao_troca_o_perfil_de_quem_ja_capta(self, cenario: Cenario) -> None:
        """O ramo que estragava a máquina, agora executado de verdade.

        Cenário construído para o pior caso: o perfil ativo NÃO oferece fonte
        (logo há alvo), mas a source do DualSense TEM porta ativa. Trocar aqui
        é trocar o que capta pelo que o ALSA marca indisponível.
        """
        cenario.cards = CARDS_SEM_FONTE
        cenario.com_dropin(DROPIN_51)
        res = cenario.roda("fix_mic_dualsense")
        assert res.returncode == 0, res.stderr
        trocas = [c for c in cenario.chamadas() if c.startswith("set-card-profile")]
        assert trocas == [], (
            f"a cura trocou o perfil de uma source que JÁ captava: {trocas}\n"
            f"{res.stdout}"
        )
        assert "já tem porta de captura" in res.stdout, res.stdout

    def test_o_check_da_camada_2_aprova_pela_porta_e_nao_pelo_nome(
        self, cenario: Cenario
    ) -> None:
        """No estado REAL desta máquina o veredito tem de ser [OK].

        Antes da cura o mesmo estado dava [FAIL] ("está no S/PDIF, que NÃO
        carrega sinal") e mandava rodar o `--fix`, que silenciava o microfone.
        """
        cenario.com_dropin(DROPIN_51)
        res = cenario.roda("check_mic_perfil_sem_sinal")
        assert res.returncode == 0, res.stderr
        assert "tem porta de captura" in res.stdout, res.stdout
        assert "S/PDIF, que NÃO carrega sinal" not in res.stdout, res.stdout


class TestFiacaoDaCuraDaCamada2:
    """Contratos de texto — padrão do repo para a lógica do doctor.sh."""

    def test_a_troca_de_perfil_e_guardada_pela_porta(self) -> None:
        inicio = TEXTO_DOCTOR.index("fix_mic_dualsense() {")
        corpo = TEXTO_DOCTOR[inicio : TEXTO_DOCTOR.index("\n}", inicio)]
        assert "_dualsense_source_tem_porta" in corpo, (
            "o `--fix-mic` voltou a trocar o perfil sem olhar a porta — é a "
            "cura que a medição de 26/07 refutou"
        )

    def test_o_decisor_nao_mira_mais_o_analogico_por_nome(self) -> None:
        inicio = TEXTO_DOCTOR.index("_dualsense_perfil_status() {")
        corpo = TEXTO_DOCTOR[inicio : TEXTO_DOCTOR.index("\n}", inicio)]
        assert 'ativo ~ /input:iec958/' not in corpo, (
            "a regra refutada voltou: trocar de perfil porque o nome do ativo "
            "tem 'iec958'"
        )
        assert "available: yes" in corpo, "o filtro por disponibilidade sumiu"

    def test_a_nota_do_incidente_continua_no_codigo(self) -> None:
        """A guarda desta casa vem com o porquê datado. Sem a nota, o próximo
        a passar por aqui refaz a cura que silenciou o microfone."""
        assert "327.680" in TEXTO_DOCTOR, (
            "a medição que refutou a cura antiga saiu do comentário"
        )


# ---------------------------------------------------------------------------
# TAREFA 2 — monitor como fonte padrão é DEFEITO, não [OK]
# ---------------------------------------------------------------------------


class TestClassificacaoDaFontePadrao:
    def test_monitor_e_monitor(self) -> None:
        assert _rodar("_default_source_classe", MONITOR_DS) == "monitor"

    def test_entrada_de_verdade_e_captura(self) -> None:
        assert _rodar("_default_source_classe", SRC_DS) == "captura"
        assert _rodar("_default_source_classe", SRC_ONBOARD) == "captura"

    def test_vazio_e_vazio(self) -> None:
        assert _rodar("_default_source_classe", "") == "vazio"

    def test_monitor_no_meio_do_nome_nao_engana(self) -> None:
        """O sufixo `.monitor` é do nó, não uma busca por substring: uma placa
        chamada "MonitorAudio" não é um loopback de saída."""
        assert _rodar("_default_source_classe", "alsa_input.usb-MonitorAudio-00") == (
            "captura"
        )


class TestEscolhaDaFonteDeCaptura:
    def test_monitor_nunca_e_eleito(self) -> None:
        for prefere in ("0", "1"):
            escolha = _rodar("_melhor_source_de_captura", prefere, entrada=SOURCES_SHORT)
            assert ".monitor" not in escolha, (
                f"prefere={prefere} elegeu um monitor: {escolha!r} — é ele o defeito"
            )

    def test_sem_preferencia_o_controle_fica_por_ultimo(self) -> None:
        """Política default do install (drop-in 51): o controle não é eleito
        sozinho. Eleger o DualSense aqui faria `check_wireplumber_source`
        REPROVAR a máquina que acabamos de curar."""
        assert _rodar("_melhor_source_de_captura", "0", entrada=SOURCES_SHORT) == (
            SRC_ONBOARD
        )

    def test_com_preferencia_o_controle_vem_primeiro(self) -> None:
        assert _rodar("_melhor_source_de_captura", "1", entrada=SOURCES_SHORT) == SRC_DS

    def test_o_controle_e_ultimo_recurso_mas_nunca_descartado(self) -> None:
        """Escassez: um mic de verdade, mesmo o do controle, é melhor que
        gravar o próprio alto-falante."""
        so_ds = "\n".join(
            linha
            for linha in SOURCES_SHORT.splitlines()
            if "pci-0000_0c_00.4.analog-stereo" not in linha
        )
        assert _rodar("_melhor_source_de_captura", "0", entrada=so_ds + "\n") == SRC_DS

    def test_sem_nenhuma_captura_o_silencio_e_a_resposta(self) -> None:
        so_monitores = "\n".join(
            linha for linha in SOURCES_SHORT.splitlines() if ".monitor" in linha
        )
        assert _rodar("_melhor_source_de_captura", "0", entrada=so_monitores + "\n") == ""


class TestQuemPodeSerPromovido:
    """Os três sinais EXPLÍCITOS, e a ordem deles é a hierarquia de quem manda."""

    def _rc_prefere(self, cenario: Cenario, env: dict[str, str] | None = None) -> int:
        ambiente = {
            "PATH": "/usr/bin:/bin",
            "DOCTOR_SH": str(DOCTOR),
            "HOME": str(cenario.home),
        }
        ambiente.update(env or {})
        return subprocess.run(
            ["bash", "-c", 'set --; source "$DOCTOR_SH"; _prefere_mic_do_dualsense'],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=ambiente,
        ).returncode

    def test_o_dropin_51_rebaixa_o_controle(self, cenario: Cenario) -> None:
        cenario.com_dropin(DROPIN_51)
        assert self._rc_prefere(cenario) == 1, (
            "com o drop-in 51 no lugar (política DEFAULT do install), promover "
            "o controle desfaz a escolha do instalador"
        )

    def test_sem_o_dropin_51_a_promocao_e_explicita(self, cenario: Cenario) -> None:
        """A ausência do 51 é o que `--promote-source` / `mic promote` deixam."""
        assert self._rc_prefere(cenario) == 0

    def test_o_opt_in_da_usuaria_vence_o_dropin_51(self, cenario: Cenario) -> None:
        cenario.com_dropin(DROPIN_51)
        env = {"HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED": "1"}
        assert self._rc_prefere(cenario, env) == 0

    def test_quem_desligou_de_proposito_vence_tudo(self, cenario: Cenario) -> None:
        """Precedente do próprio doctor (`check_dualsense_sink_disabled`) e do
        passo 10 do install: o drop-in 52 é "o controle é só-HID"."""
        cenario.com_dropin(DROPIN_52)
        env = {"HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED": "1"}
        assert self._rc_prefere(cenario, env) == 1, (
            "o drop-in 52 (mic desligado de propósito) foi atropelado"
        )


class TestPortaoParaDeAprovarOSintoma:
    def test_monitor_como_fonte_padrao_reprova(self, cenario: Cenario) -> None:
        cenario.com_dropin(DROPIN_51)
        res = cenario.roda("check_default_source_monitor")
        assert "[FAIL]" in res.stdout or "FAIL" in res.stdout, (
            "o monitor como fonte padrão continua sendo aprovado:\n" + res.stdout
        )
        assert "MONITOR" in res.stdout
        assert "áudio de SAÍDA" in res.stdout, res.stdout

    def test_a_cura_e_oferecida_no_texto(self, cenario: Cenario) -> None:
        cenario.com_dropin(DROPIN_51)
        res = cenario.roda("check_default_source_monitor")
        assert f"pactl set-default-source {SRC_ONBOARD}" in res.stdout, res.stdout

    def test_entrada_de_verdade_aprova(self, cenario: Cenario) -> None:
        cenario.default_source = SRC_DS
        cenario.com_dropin(DROPIN_51)
        res = cenario.roda("check_default_source_monitor")
        assert "entrada de verdade" in res.stdout, res.stdout
        assert "[FAIL]" not in res.stdout, res.stdout

    def test_o_check_conta_a_metade_que_faltava(self, cenario: Cenario) -> None:
        """Fonte legítima que grava SILÊNCIO não pode sair só como [OK].

        Medido em 29/07: eleita a entrada da onboard, as portas de captura dela
        estavam todas `not available` (nada plugado), e o único mic que captava
        era o do controle. Aprovar sem dizer isso seria o mesmo pecado do
        `pass` que aprovava o monitor.
        """
        cenario.default_source = SRC_ONBOARD
        cenario.com_dropin(DROPIN_51)
        res = cenario.roda("check_default_source_monitor")
        assert "vai gravar silêncio" in res.stdout, res.stdout
        assert "mic promote" in res.stdout, res.stdout

    def test_o_check_wireplumber_source_nao_aprova_mais_monitor(
        self, cenario: Cenario
    ) -> None:
        """A guarda antiga (monitor não é o mic do controle) fica; o [OK] sai.

        Ela existe para este check não reprovar por causa do loopback da saída —
        isso continua verdade e continua não sendo [FAIL] aqui. O que mudou é
        não encerrar o assunto com um selo de aprovação.
        """
        cenario.com_dropin(DROPIN_51)
        res = cenario.roda("check_wireplumber_source")
        assert "[ OK ]" not in res.stdout and "[OK]" not in res.stdout, (
            "o `pass` que aprovava o monitor voltou:\n" + res.stdout
        )
        assert "MONITOR" in res.stdout, res.stdout


class TestCuraDaFontePadrao:
    def test_a_cura_elege_uma_entrada_de_verdade(self, cenario: Cenario) -> None:
        """CORRIGIDO em 30/07 — este teste afirmava o contrário do próprio
        comentário da fixture que ele usa.

        A `SOURCES_LONGO` diz, três linhas acima dela: *"a onboard tem porta
        ativa `not available` (nada plugado no jack); a do DualSense tem
        `availability unknown` — e é ela que gravou pico 4606"*. O raciocínio
        estava certo e a afirmação, errada: o teste exigia que a cura elegesse a
        ONBOARD.

        Provado na máquina dela em 30/07, depois de um `uninstall` + `install`
        limpos: eleger a onboard não gruda. O `pactl set-default-source` aceita,
        o WirePlumber não consegue honrar um nó sem porta usável, reelege
        sozinho e volta para o MONITOR em segundos — com a cura tendo impresso
        `[ OK ] fonte padrão trocada`. Relatório que mente é pior que cura que
        não roda.

        Com o filtro de porta ligado (o `_source_porta_ativa_indisponivel`, que
        existia e não era chamado), a onboard sai da disputa e sobra o mic do
        controle — que é o único microfone de verdade desta máquina.
        """
        cenario.com_dropin(DROPIN_51)
        res = cenario.roda("fix_default_source_monitor")
        assert res.returncode == 0, res.stderr
        eleicoes = [
            c for c in cenario.chamadas() if c.startswith("set-default-source")
        ]
        assert eleicoes == [f"set-default-source {SRC_DS}"], (
            "a onboard tem as três portas `not available` — elegê-la é eleger "
            f"silêncio, e o WirePlumber devolve o monitor.\n{eleicoes}\n{res.stdout}"
        )

    def test_com_opt_in_a_cura_elege_o_controle(self, cenario: Cenario) -> None:
        cenario._escrever_pactl()
        res = subprocess.run(
            ["bash", "-c", 'set --; source "$DOCTOR_SH"; fix_default_source_monitor'],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env={
                "PATH": f"{cenario.bin}:/usr/bin:/bin",
                "DOCTOR_SH": str(DOCTOR),
                "HOME": str(cenario.home),
                "HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED": "1",
            },
        )
        assert res.returncode == 0, res.stderr
        assert f"set-default-source {SRC_DS}" in cenario.chamadas(), res.stdout

    def test_a_cura_nao_toca_em_fonte_de_captura_escolhida(
        self, cenario: Cenario
    ) -> None:
        """Fonte de captura de verdade — QUALQUER uma — é escolha de quem usa a
        máquina. Mesmo que não seja a que elegeríamos."""
        cenario.default_source = SRC_ONBOARD
        res = cenario.roda("fix_default_source_monitor")
        assert res.returncode == 0, res.stderr
        eleicoes = [
            c for c in cenario.chamadas() if c.startswith("set-default-source")
        ]
        assert eleicoes == [], f"a cura atropelou a escolha dela: {eleicoes}"

    def test_sem_nenhuma_captura_a_cura_avisa_e_nao_inventa(
        self, cenario: Cenario
    ) -> None:
        cenario.sources_short = "\n".join(
            linha for linha in SOURCES_SHORT.splitlines() if ".monitor" in linha
        ) + "\n"
        res = cenario.roda("fix_default_source_monitor")
        assert res.returncode == 0, res.stderr
        assert [c for c in cenario.chamadas() if c.startswith("set-default-source")] == []
        assert "não há nenhuma fonte de captura" in res.stdout, res.stdout


class TestFiacaoDaFontePadrao:
    def test_o_check_esta_no_diagnostico_completo(self) -> None:
        assert "\n    check_default_source_monitor\n" in TEXTO_DOCTOR, (
            "o check novo não é chamado pelo main — portão que ninguém roda"
        )

    def test_o_check_esta_na_rota_curta_do_fix_mic(self) -> None:
        inicio = TEXTO_DOCTOR.index('if [[ "${FIX_MIC}" -eq 1 ]]; then')
        corpo = TEXTO_DOCTOR[inicio : TEXTO_DOCTOR.index("\n    fi", inicio)]
        assert "check_default_source_monitor" in corpo, corpo

    def test_a_cura_esta_no_fix_mic(self) -> None:
        inicio = TEXTO_DOCTOR.index("fix_mic_dualsense() {")
        corpo = TEXTO_DOCTOR[inicio : TEXTO_DOCTOR.index("\n}", inicio)]
        assert "fix_default_source_monitor" in corpo, (
            "a cura existe e ninguém a chama — foi o defeito do próprio "
            "`--fix-mic` antes do install passar a chamá-lo"
        )

    def test_a_cura_vem_depois_da_camada_2(self) -> None:
        """É a troca de perfil que decide qual `alsa_input` existe; eleger antes
        elegeria um nó que vai desaparecer."""
        inicio = TEXTO_DOCTOR.index("fix_mic_dualsense() {")
        corpo = TEXTO_DOCTOR[inicio : TEXTO_DOCTOR.index("\n}", inicio)]
        assert corpo.index("set-card-profile") < corpo.index(
            "fix_default_source_monitor"
        ), "a eleição da fonte padrão passou para antes da troca de perfil"

    def test_a_medicao_de_29_07_esta_registrada(self) -> None:
        assert "FONTE-PADRAO-01" in TEXTO_DOCTOR
        assert "analog-surround-40.monitor" in TEXTO_DOCTOR, (
            "o sintoma medido saiu do comentário"
        )


# ---------------------------------------------------------------------------
# TAREFA 3 — o install.sh chama o scripts/install_fonts.sh
# ---------------------------------------------------------------------------


class TestInstallChamaAsFontes:
    def test_o_script_de_fontes_existe(self) -> None:
        assert FONTS.is_file()

    def _invocacoes(self) -> list[str]:
        """Linhas que de fato EXECUTAM o script — não as que só o citam.

        Este detalhe é a diferença entre um teste que morde e um que não morde:
        a primeira versão daqui procurava a string `scripts/install_fonts.sh` no
        arquivo inteiro, e continuou VERDE com a chamada arrancada — o nome
        sobrevivia no comentário do passo e na mensagem de "ausente". Medido
        arrancando: 9 testes passaram com o install sem instalar fonte nenhuma.
        """
        return [
            linha.strip()
            for linha in TEXTO_INSTALL.splitlines()
            if not linha.lstrip().startswith("#")
            and "scripts/install_fonts.sh" in linha
            and ("bash " in linha or "sh " in linha or "install_fonts.sh\"" in linha)
            and "-r " not in linha
            and "warn " not in linha
            and "printf " not in linha
        ]

    def test_o_install_chama_o_script(self) -> None:
        """Medido em 29/07: `grep -c fonts install.sh` = 0. O script existia,
        com download pinado e SHA-256, e NINGUÉM o chamava — o `gui/theme.css`
        pedia duas famílias que numa máquina limpa não existem, e o fontconfig
        substituía em silêncio."""
        assert self._invocacoes(), (
            "o install voltou a não EXECUTAR o scripts/install_fonts.sh — citar "
            "o nome em comentário não instala fonte nenhuma"
        )

    def test_a_chamada_e_best_effort(self) -> None:
        """Fonte é acabamento, não requisito: derrubar a instalação inteira por
        causa disso trocaria um problema cosmético por um problema real."""
        invocacoes = self._invocacoes()
        assert invocacoes
        bloco = TEXTO_INSTALL[
            TEXTO_INSTALL.index("# 4e. Fontes da identidade visual") :
        ]
        bloco = bloco[: bloco.index("# 5. Symlink")]
        for linha in invocacoes:
            assert linha in bloco.replace("\n", " ").replace("  ", " ") or linha in bloco, (
                f"chamada ao install_fonts.sh fora do passo 4e: {linha!r}"
            )
        # Sob `set -e` uma chamada nua abortaria a instalação inteira.
        assert "||" in bloco, (
            "a chamada não está protegida do `set -e` (falta o `|| printf`):\n" + bloco
        )

    def test_tem_gate_de_flag_para_desligar(self) -> None:
        assert "--no-fonts)" in TEXTO_INSTALL, "falta a flag de opt-out no parser"
        assert "NO_FONTS=0" in TEXTO_INSTALL, "a flag nasce sem valor default"
        bloco = TEXTO_INSTALL[
            TEXTO_INSTALL.index("# 4e. Fontes da identidade visual") :
        ]
        bloco = bloco[: bloco.index("# 5. Symlink")]
        assert 'NO_FONTS' in bloco, "o gate não é consultado no passo:\n" + bloco

    def test_a_flag_esta_documentada_no_cabecalho(self) -> None:
        """Regra desta casa (BUG-INSTALL-HELP-TRUNCADO-01): flag real que não
        está no cabeçalho não aparece no `--help` e vira flag invisível."""
        cabecalho = TEXTO_INSTALL[: TEXTO_INSTALL.index("\nset -euo pipefail")]
        assert "--no-fonts" in cabecalho

    def test_o_no_fonts_sai_no_help(self) -> None:
        res = subprocess.run(
            ["bash", str(INSTALL), "--help"],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert res.returncode == 0, res.stderr
        assert "--no-fonts" in res.stdout, res.stdout

    def test_o_parser_conhece_a_flag(self) -> None:
        """O install não pode aceitar em silêncio uma flag que ele rejeita —
        nem rejeitar uma que ele documenta (BUG-INSTALL-ARG-DESCONHECIDO-...)."""
        assert "desconhecid" in TEXTO_INSTALL.lower()
        inicio = TEXTO_INSTALL.index('for arg in "$@"; do')
        corpo = TEXTO_INSTALL[inicio : TEXTO_INSTALL.index("\ndone", inicio)]
        assert "--no-fonts)" in corpo

    def test_o_passo_fica_junto_do_resto_da_gui(self) -> None:
        """Mesma natureza dos passos 4b/4c/4d: acabamento da GUI, no HOME dela,
        sem sudo obrigatório — e antes do passo 5."""
        assert TEXTO_INSTALL.index("# 4d. Catalogos i18n") < TEXTO_INSTALL.index(
            "# 4e. Fontes da identidade visual"
        ) < TEXTO_INSTALL.index("# 5. Symlink")

    def test_o_theme_css_ainda_pede_as_duas_familias(self) -> None:
        """Se um dia o CSS parar de pedir, este passo perde o motivo — e o
        teste tem de contar isso em vez de continuar verde por inércia."""
        css = (
            RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "theme.css"
        ).read_text(encoding="utf-8")
        assert "Space Grotesk" in css
        assert "JetBrains Mono" in css
