"""O decisor da camada 2 do `doctor.sh` — o que ele escolhe, e o que ele recusa.

Por que este arquivo existe: até 26/07/2026 o `--fix-mic` trocava o perfil da
placa sempre que a entrada ativa fosse `iec958`, mirando `input:analog-stereo`,
porque a sprint MIC-USB-01 afirmava que o microfone "vive" na entrada analógica.

Medido no hardware, com o controle no cabo, na madrugada de 26/07: o perfil
analógico estava marcado ``available: no`` pelo próprio ALSA, e forçá-lo produzia
uma source **sem nenhuma porta de captura**, que entrega 327.680 bytes de
silêncio digital. O `iec958-stereo` — o perfil que a sprint mandava evitar —
gravou pico 4606 e RMS 374. A "cura" silenciava o microfone de quem a rodasse.

Os testes abaixo travam a regra nova contra os dados REAIS daquela medição: só
entram na disputa perfis que oferecem fonte de captura (``sources: >= 1``) **e**
que o ALSA declara ``available: yes``; e nada é trocado quando o perfil ativo já
satisfaz os dois.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
DOCTOR = REPO_ROOT / "scripts" / "doctor.sh"

#: Recorte de `LC_ALL=C pactl list cards` com o estado MEDIDO em 26/07: a placa
#: do DualSense com o analógico indisponível e o digital disponível.
#:
#: Montado por concatenação porque as linhas de perfil do `pactl` são longas e
#: quebrá-las corromperia o dado que o `awk` lê — o fonte fica curto, o dado
#: fica literal.
_P_ANALOG = (
    "\t\toutput:analog-surround-40+input:analog-stereo: Surround + Analog In"
    " (sinks: 1, sources: 1, priority: 1265, available: no)\n"
)
_P_DIGITAL = (
    "\t\toutput:analog-surround-40+input:iec958-stereo: Surround + Digital In"
    " (sinks: 1, sources: 1, priority: 1255, available: yes)\n"
)
CARDS_MEDIDO = (
    "Card #675\n"
    "\tName: alsa_card.usb-Sony_Interactive_Entertainment_"
    "DualSense_Wireless_Controller-00\n"
    "\tDriver: alsa\n"
    "\tProfiles:\n"
    "\t\toff: Off (sinks: 0, sources: 0, priority: 0, available: yes)\n"
    + _P_ANALOG
    + _P_DIGITAL
    + "\t\toutput:analog-surround-40: Surround"
    " (sinks: 1, sources: 0, priority: 1200, available: yes)\n"
    "\t\tinput:analog-stereo: Analog In"
    " (sinks: 0, sources: 1, priority: 65, available: no)\n"
    "\t\tinput:iec958-stereo: Digital In"
    " (sinks: 0, sources: 1, priority: 55, available: yes)\n"
    "\tActive Profile: {ativo}\n"
    "\tPorts:\n"
)


def _decide(ativo: str) -> tuple[str, str, str]:
    """Roda `_dualsense_perfil_status` do doctor com um `pactl` de mentira."""
    script = (
        f'set -euo pipefail\n'
        f'source "{DOCTOR}" >/dev/null 2>&1 || true\n'
        f'printf %s "$CARDS" | _dualsense_perfil_status\n'
    )
    proc = subprocess.run(
        [BASH, "-c", script],
        capture_output=True,
        text=True,
        env={
            "CARDS": CARDS_MEDIDO.format(ativo=ativo),
            "PATH": "/usr/bin:/bin",
            "HOME": "/nonexistent",
            "LC_ALL": "C",
        },
        check=False,
    )
    linha = proc.stdout.strip()
    if not linha:
        return ("", "", "")
    partes = linha.split("\t")
    while len(partes) < 3:
        partes.append("")
    return (partes[0], partes[1], partes[2])


@pytest.mark.skipif(not DOCTOR.exists(), reason="scripts/doctor.sh ausente")
class TestOQueODoctorEscolhe:
    def test_nao_troca_quando_o_perfil_ativo_ja_serve(self) -> None:
        """O caso que estragava a máquina dela.

        Ativo = digital, disponível e com fonte. A versão anterior trocava para
        o analógico só porque o nome tinha `iec958`, e o analógico está
        `available: no` — a source nascia sem porta e o microfone emudecia.
        """
        _card, ativo, alvo = _decide(
            "output:analog-surround-40+input:iec958-stereo"
        )
        assert ativo == "output:analog-surround-40+input:iec958-stereo"
        assert alvo == "", (
            "o perfil ativo oferece fonte e esta disponivel — trocar so pode "
            f"piorar, e foi o que a medicao provou; veio alvo={alvo!r}"
        )

    def test_nunca_escolhe_um_perfil_que_o_alsa_marca_indisponivel(self) -> None:
        """Ativo sem fonte de captura: precisa trocar — mas nunca para o `no`."""
        _card, _ativo, alvo = _decide("output:analog-surround-40")
        assert alvo, "sem fonte de captura no ativo, tem de haver alvo"
        assert "analog-stereo" not in alvo, (
            "o perfil analogico esta `available: no` nesta medicao — escolhe-lo "
            f"produz source sem porta; veio {alvo!r}"
        )
        assert alvo == "output:analog-surround-40+input:iec958-stereo", (
            f"esperava o disponivel de maior prioridade com fonte; veio {alvo!r}"
        )

    def test_ativo_que_serve_nao_e_trocado_por_prioridade_maior(self) -> None:
        """Servir basta — não é para perseguir prioridade.

        `input:iec958-stereo` (prioridade 55) oferece fonte e está disponível,
        mas existe um combinado de prioridade 1255 igualmente disponível. Trocar
        aqui seria derrubar uma captura que funciona por outra que talvez
        funcione — a mesma classe de defeito que esta reescrita conserta.
        """
        _card, ativo, alvo = _decide("input:iec958-stereo")
        assert ativo == "input:iec958-stereo"
        assert alvo == "", (
            "o ativo ja oferece fonte disponivel; trocar por prioridade e "
            f"mexer no que funciona. Veio alvo={alvo!r}"
        )

    def test_sem_placa_do_dualsense_nao_inventa_alvo(self) -> None:
        proc = subprocess.run(
            [
                BASH,
                "-c",
                f'source "{DOCTOR}" >/dev/null 2>&1 || true\n'
                'printf "Card #1\\n\\tName: alsa_card.pci-0000_0a_00.1\\n" '
                "| _dualsense_perfil_status",
            ],
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LC_ALL": "C"},
            check=False,
        )
        assert proc.stdout.strip() == ""


@pytest.mark.skipif(not DOCTOR.exists(), reason="scripts/doctor.sh ausente")
class TestAPortaEOCriterio:
    """A porta de captura é o teste honesto de "dá para captar"."""

    def _tem_porta(self, sources: str, nome: str) -> bool:
        proc = subprocess.run(
            [
                BASH,
                "-c",
                f'source "{DOCTOR}" >/dev/null 2>&1 || true\n'
                'pactl() { printf %s "$SOURCES"; }\n'
                f'_dualsense_source_tem_porta "{nome}"',
            ],
            capture_output=True,
            text=True,
            env={
                "SOURCES": sources,
                "PATH": "/usr/bin:/bin",
                "HOME": "/nonexistent",
                "LC_ALL": "C",
            },
            check=False,
        )
        return proc.returncode == 0

    def test_source_com_porta_ativa_capta(self) -> None:
        sources = (
            "Source #1\n\tName: alsa_input.dualsense.iec958-stereo\n"
            "\tActive Port: iec958-stereo-input\n"
        )
        assert self._tem_porta(sources, "alsa_input.dualsense.iec958-stereo")

    def test_source_sem_porta_nenhuma_nao_capta(self) -> None:
        """O estado medido no perfil analógico: nó de pé, lista de portas vazia."""
        sources = "Source #1\n\tName: alsa_input.dualsense.analog-stereo\n"
        assert not self._tem_porta(sources, "alsa_input.dualsense.analog-stereo")

    def test_a_porta_de_outra_source_nao_conta(self) -> None:
        """Porta do vizinho não vale — foi assim que a leitura a olho errou."""
        sources = (
            "Source #1\n\tName: alsa_input.placa_mae.analog-stereo\n"
            "\tActive Port: analog-input-front-mic\n"
            "Source #2\n\tName: alsa_input.dualsense.analog-stereo\n"
        )
        assert not self._tem_porta(sources, "alsa_input.dualsense.analog-stereo")


@pytest.mark.skipif(not DOCTOR.exists(), reason="scripts/doctor.sh ausente")
class TestACuraNaoEncostaNoQueJaFunciona:
    """O ramo da CURA, e não só o do decisor.

    A primeira versão destes testes cobria `_dualsense_perfil_status` e
    `_dualsense_source_tem_porta` isoladamente — e uma mutação que fazia a cura
    IGNORAR a porta passou verde. Testava as peças, não a fiação. Este teste
    entra por `fix_mic_dualsense` e olha o que ela de fato manda o `pactl`
    fazer.
    """

    def _chamadas_de_pactl(self, ativo: str, curta: str, verbosa: str) -> str:
        """Roda `fix_mic_dualsense` com `pactl` dublado e devolve as chamadas.

        O dublê distingue `list sources short` de `list sources` — a primeira
        versão não distinguia, o nome da source saía vazio e a cura nem chegava
        ao ramo que o teste queria vigiar. Passava verde por não exercitar nada.

        BERCO-DE-TMP-01, 07/08/2026: o registro era o caminho FIXO
        ``/tmp/hefesto_teste_pactl_chamadas.txt``, e o retrato do disco o pegou
        vivo em `/tmp` depois da suíte. Caminho fixo tem dois defeitos, não um:
        fica para trás, e **colide entre sessões** — nesta máquina rodam várias
        execuções de `pytest` ao mesmo tempo, e duas delas escreviam no mesmo
        arquivo. Agora o nome vem do `tempfile` (que nasce dentro do berço da
        sessão) e o teste o remove ele mesmo.
        """
        descritor, registro = tempfile.mkstemp(
            prefix="hefesto-pactl-", suffix=".txt"
        )
        os.close(descritor)
        try:
            return self._rodar_dubles(registro, ativo, curta, verbosa)
        finally:
            with contextlib.suppress(OSError):
                os.unlink(registro)

    def _rodar_dubles(
        self, registro: str, ativo: str, curta: str, verbosa: str
    ) -> str:
        script = f"""
set -uo pipefail
: > {registro}
source "{DOCTOR}" >/dev/null 2>&1 || true
pactl() {{
    printf '%s\\n' "pactl $*" >> {registro}
    case "$*" in
        "list cards")         printf %s "$CARDS" ;;
        "list sources short") printf %s "$CURTA" ;;
        "list sources")       printf %s "$VERBOSA" ;;
        *) : ;;
    esac
}}
command() {{ [ "${{2:-}}" = pactl ] && return 0; builtin command "$@"; }}
pass() {{ :; }}
warn() {{ :; }}
info() {{ :; }}
fix_mic_dualsense >/dev/null 2>&1 || true
cat {registro}
"""
        proc = subprocess.run(
            [BASH, "-c", script],
            capture_output=True,
            text=True,
            env={
                "CARDS": CARDS_MEDIDO.format(ativo=ativo),
                "CURTA": curta,
                "VERBOSA": verbosa,
                "PATH": "/usr/bin:/bin",
                "HOME": "/nonexistent",
                "LC_ALL": "C",
            },
            check=False,
        )
        return proc.stdout

    #: Nome real da source medida em 26/07 (curto e verboso batem).
    _SRC = (
        "alsa_input.usb-Sony_Interactive_Entertainment_"
        "DualSense_Wireless_Controller-00.iec958-stereo"
    )

    def test_com_porta_de_captura_a_cura_nao_troca_o_perfil(self) -> None:
        """O cenário que só o ramo da cura protege.

        O perfil ativo NÃO oferece fonte (logo o decisor tem alvo — há para
        onde trocar), mas a source existente TEM porta e está captando. Sem a
        checagem de porta, a cura trocaria o perfil e emudeceria o microfone.
        """
        saida = self._chamadas_de_pactl(
            ativo="output:analog-surround-40",
            curta=f"1\t{self._SRC}\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n",
            verbosa=f"Source #1\n\tName: {self._SRC}\n"
            "\tActive Port: iec958-stereo-input\n",
        )
        assert "list cards" in saida, (
            f"a cura precisa ter rodado de verdade; saida={saida!r}"
        )
        assert "set-card-profile" not in saida, (
            "havia porta de captura: trocar o perfil so pode piorar, e foi "
            f"isso que emudeceu o microfone na medicao. Chamadas: {saida!r}"
        )

    def test_sem_porta_a_cura_troca_para_o_perfil_disponivel(self) -> None:
        """E o contrário também precisa valer, senão a cura vira decoração."""
        saida = self._chamadas_de_pactl(
            ativo="output:analog-surround-40",
            curta=f"1\t{self._SRC}\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n",
            verbosa=f"Source #1\n\tName: {self._SRC}\n",
        )
        assert "set-card-profile" in saida, (
            f"sem porta de captura, a cura TEM de agir; chamadas={saida!r}"
        )
        assert "input:iec958-stereo" in saida, (
            f"e tem de mirar o perfil disponivel; chamadas={saida!r}"
        )


#: As fixtures GRAVADAS da máquina, com o controle no cabo, em 20/09/2026.
#: **A régua LÊ, nunca digita.** Havia prova viva de que isso importa: a linha
#: `iec958-stereo-input: Digital Input (S/PDIF) (…, availability unknown)` que
#: `test_o_microfone_padrao_no_cabo.py` digitava à mão já divergia do vivo — e
#: divergia calada. Fixture digitada envelhece sem avisar ninguém.
FIXTURES_MIC_CABO = REPO_ROOT / "tests" / "fixtures" / "mic-cabo"


@pytest.mark.skipif(not DOCTOR.exists(), reason="scripts/doctor.sh ausente")
@pytest.mark.skipif(
    not FIXTURES_MIC_CABO.is_dir(), reason="tests/fixtures/mic-cabo ausente"
)
class TestAPortaDeCapturaAlcancaOGanho:
    """MIC-CABO-SPDIF-01 — a PORTA, que a camada 2 nunca olhou.

    O `_dualsense_perfil_status` decide no nível do PERFIL e está certo no que
    faz. Mas ele não distingue uma porta que liga o elemento de ganho de
    captura de uma que não liga — e era esse o defeito medido em 17 e
    20/09/2026, invisível aos sessenta portões desta casa.

    O QUE ESTÁ FORA DE ALCANCE: o `Headset Capture Volume` do DualSense
    (0…+48 dB), lido em repouso a 100% / +48,00 dB. Nenhuma porta que o
    PipeWire ativou até hoje o liga — nem a `iec958-stereo-input` da distro em
    17/09, nem a `[In] Mic` do UCM DESTA CASA em 20/09.

    **O FURO, declarado:** esta régua mede o TEXTO de três leituras, não o
    aparelho. Ela prova que o elemento existe e está fora do caminho do
    PipeWire; **não** prova que ele afeta a captura. Quem ler o verde daqui
    como «o microfone está bom» leu errado.
    """

    def _decide(self, sources: str, scontents: str, porta: str) -> tuple[str, str, str]:
        """Roda o decisor puro do doctor com três ARQUIVOS de fixture."""
        script = (
            f'source "{DOCTOR}" >/dev/null 2>&1 || true\n'
            f"_dualsense_porta_de_captura_status"
            f' "{FIXTURES_MIC_CABO / sources}"'
            f' "{FIXTURES_MIC_CABO / scontents}"'
            f' "{FIXTURES_MIC_CABO / porta}"\n'
        )
        proc = subprocess.run(
            [BASH, "-c", script],
            capture_output=True,
            text=True,
            env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LC_ALL": "C"},
            check=False,
        )
        linha = proc.stdout.strip()
        if not linha:
            return ("", "", "")
        partes = linha.split("\t")
        while len(partes) < 3:
            partes.append("")
        return (partes[0], partes[1], partes[2])

    def test_o_estado_de_hoje_reprova(self) -> None:
        """O defeito vivo: a porta do UCM desta casa não liga o `Headset`."""
        porta, elemento, fora = self._decide(
            "sources-cabo-2026-09-20.txt",
            "scontents-dualsense-2026-09-20.txt",
            "porta-ucm-mic-2026-09-20.txt",
        )
        assert porta == "[In] Mic", (
            f"a porta ativa tem de sair da fixture; saiu {porta!r}"
        )
        assert elemento == "Headset", (
            f"o elemento de ganho de captura da placa é o `Headset`; saiu {elemento!r}"
        )
        assert fora == "sim", (
            "a placa TEM `Headset Capture Volume` e a porta ativa não o liga — "
            "o ganho está fora do alcance do PipeWire, da tela e dela"
        )

    def test_a_porta_de_17_09_reprovava_pelo_mesmo_motivo(self) -> None:
        """Dois donos diferentes, o mesmo estado — e o decisor não olha o nome.

        Em 17/09 a porta era a `iec958-stereo-input` do alsa-card-profile da
        distro; em 20/09 é a `[In] Mic` do UCM desta casa. O `.conf` daquela
        tem um `[Element PCM Capture Source]` e nenhum `volume = merge`, então
        ela também não liga ganho nenhum.
        """
        _, elemento, fora = self._decide(
            "sources-cabo-2026-09-20.txt",
            "scontents-dualsense-2026-09-20.txt",
            "porta-acp-iec958-stereo-input.conf",
        )
        assert (elemento, fora) == ("Headset", "sim")

    # --- AS TRÊS MORDIDAS -------------------------------------------------

    def test_mordida_2_placa_sem_elemento_de_captura_da_verde(self) -> None:
        """A mordida que mais importa das três.

        Se a régua reprovasse por achar o nome da porta na string, ela
        reprovaria também aqui — numa placa que não tem NADA a ligar. Reprovar
        aí é inventar defeito, e foi por essa porta que voltaria a «cura» de
        26/07 que emudeceu o microfone de quem a rodou (source sem porta de
        captura, 327.680 bytes de silêncio digital).

        A fixture é GRAVADA: a placa 0 desta máquina é HDMI e não tem captura.
        """
        _, elemento, fora = self._decide(
            "sources-cabo-2026-09-20.txt",
            "scontents-sem-captura-2026-09-20.txt",
            "porta-ucm-mic-2026-09-20.txt",
        )
        assert elemento == "", (
            f"placa sem elemento de captura não tem ganho a ligar; saiu {elemento!r}"
        )
        assert fora == "não", (
            "sem elemento na placa não há nada fora de alcance — reprovar aqui "
            "seria a régua medindo o NOME da porta, não o alcance"
        )

    def test_mordida_3_porta_que_liga_o_ganho_da_verde(self) -> None:
        """Mesma placa, porta diferente: o veredito tem de virar.

        A `analog-input-headset-mic.conf` traz `[Element Headset]` com
        `volume = merge` — ela LIGA o elemento. Se aqui desse vermelho, o
        decisor estaria preso ao texto do nome e não ao que o nome liga.
        """
        _, elemento, fora = self._decide(
            "sources-cabo-2026-09-20.txt",
            "scontents-dualsense-2026-09-20.txt",
            "porta-acp-analog-input-headset-mic.conf",
        )
        assert elemento == "Headset"
        assert fora == "não", (
            "esta porta declara `volume = merge` sobre o `Headset`: o ganho "
            "está no caminho do PipeWire e não há o que reprovar"
        )

    def test_desligar_elemento_nao_conta_como_ligar(self) -> None:
        """Desligar um elemento não é ligá-lo, e confundir os dois daria verde sobre o defeito.

        A `analog-input-headset-mic.conf` traz oito `[Element …]` cujo volume é
        declarado DESLIGADO (Front Mic, Internal Mic, Rear Mic…). Uma régua que
        casasse a chave `volume` sem olhar o valor daria verde para QUALQUER
        porta que apenas desligue elementos — inclusive uma que não ligue
        nenhum.
        """
        conf = FIXTURES_MIC_CABO / "porta-acp-analog-input-headset-mic.conf"
        texto = conf.read_text(encoding="utf-8")
        desligado = "volume = " + "off"
        assert desligado in texto, (
            "a fixture precisa CONTER o caso que a régua tem de recusar, senão "
            "este teste não mede nada"
        )
        so_desligados = "\n".join(
            ln for ln in texto.splitlines() if "volume = merge" not in ln
        )
        alvo = FIXTURES_MIC_CABO / "porta-so-com-volume-desligado.conf"
        alvo.write_text(so_desligados, encoding="utf-8")
        try:
            _, _, fora = self._decide(
                "sources-cabo-2026-09-20.txt",
                "scontents-dualsense-2026-09-20.txt",
                alvo.name,
            )
        finally:
            with contextlib.suppress(OSError):
                alvo.unlink()
        assert fora == "sim", (
            "sem um único `volume = merge`, a porta não liga ganho nenhum — "
            "elemento desligado não pode contar como elemento ligado"
        )

    def test_sem_dualsense_o_decisor_cala(self) -> None:
        """Sem source do DualSense não há veredito — e silêncio não é verde.

        Quem chamar isto tem de distinguir «não há controle no cabo» de «está
        tudo bem», e por isso a saída é VAZIA, não uma linha com `não`.
        """
        assert self._decide(
            "porta-ucm-mic-2026-09-20.txt",  # um arquivo sem nenhuma source
            "scontents-dualsense-2026-09-20.txt",
            "porta-ucm-mic-2026-09-20.txt",
        ) == ("", "", "")
