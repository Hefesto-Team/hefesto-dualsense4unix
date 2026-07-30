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

import shutil
import subprocess
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
        """
        registro = "/tmp/hefesto_teste_pactl_chamadas.txt"
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
