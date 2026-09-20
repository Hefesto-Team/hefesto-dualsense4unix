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

    def _decide(
        self,
        sources: str | Path,
        scontents: str | Path,
        porta: str | Path,
    ) -> tuple[str, str, str]:
        """Roda o decisor puro do doctor com três ARQUIVOS.

        Um `str` é nome dentro de `tests/fixtures/mic-cabo/` — as gravações. Um
        `Path` ABSOLUTO passa direto, e é assim que os casos DERIVADOS entram:
        eles nascem no `tmp_path` do pytest, nunca dentro da pasta de fixtures.
        (`Path("/a") / Path("/b")` devolve `/b`, então a barra abaixo já faz as
        duas coisas — e esta linha existe para que isso seja escolha, e não
        acidente que a próxima pessoa desfaça.)
        """
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

    def test_desligar_elemento_nao_conta_como_ligar(self, tmp_path: Path) -> None:
        """Desligar um elemento não é ligá-lo, e confundir os dois daria verde sobre o defeito.

        A `analog-input-headset-mic.conf` traz oito `[Element …]` cujo volume é
        declarado DESLIGADO (Front Mic, Internal Mic, Rear Mic…). Uma régua que
        casasse a chave `volume` sem olhar o valor daria verde para QUALQUER
        porta que apenas desligue elementos — inclusive uma que não ligue
        nenhum.

        O derivado nasce no `tmp_path`: escrever dentro de `tests/fixtures/`
        com nome fixo faz duas corridas colidirem, e um `kill` duro deixa o
        arquivo para trás — foi a cicatriz BERCO-DE-TMP-01, e ela vale aqui
        igual.
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
        alvo = tmp_path / "porta-so-com-volume-desligado.conf"
        alvo.write_text(so_desligados, encoding="utf-8")
        _, _, fora = self._decide(
            "sources-cabo-2026-09-20.txt",
            "scontents-dualsense-2026-09-20.txt",
            alvo,
        )
        assert fora == "sim", (
            "sem um único `volume = merge`, a porta não liga ganho nenhum — "
            "elemento desligado não pode contar como elemento ligado"
        )

    def test_valor_fixo_nao_e_o_deslizante(self, tmp_path: Path) -> None:
        """Prender o elemento num valor não é entregá-lo a quem mexe no volume.

        A tabela é da distro, e está no disco desta máquina:
        `/usr/share/alsa-card-profile/mixer/paths/analog-output.conf.common`
        linhas 103-107 listam os cinco valores que a chave aceita e dizem o que
        cada um faz. **Só o `merge` junta o elemento ao deslizante do
        dispositivo**; os outros dois que trazem número — o que crava 0 dB e o
        que crava um passo — PRENDEM o elemento onde o arquivo mandou, que é
        palavra por palavra o defeito que este decisor existe para acusar.

        Esta régua nasceu de um defeito vivo: o decisor contava os dois como
        «a porta liga o ganho», e com isso daria verde sobre o estado que a
        sprint mediu.
        """
        for valor in ("zero", "12"):
            alvo = tmp_path / f"porta-presa-em-{valor}.conf"
            alvo.write_text(
                f"[Element Headset]\nswitch = mute\nvolume = {valor}\n",
                encoding="utf-8",
            )
            _, elemento, fora = self._decide(
                "sources-cabo-2026-09-20.txt",
                "scontents-dualsense-2026-09-20.txt",
                alvo,
            )
            assert (elemento, fora) == ("Headset", "sim"), (
                f"`volume = {valor}` prende o elemento num valor fixo e NÃO o "
                f"põe no deslizante; veio elemento={elemento!r} fora={fora!r}"
            )

    def test_merge_de_outro_elemento_nao_alcanca_o_ganho(
        self, tmp_path: Path
    ) -> None:
        """O `merge` tem de ser DO elemento achado, não de um qualquer.

        Uma porta que liga o alto-falante e não menciona o elemento de captura
        em lugar nenhum deixa o ganho de captura exatamente onde estava. Se o
        decisor varrer o arquivo inteiro atrás da palavra, ele declara «alcança
        o ganho» sobre uma porta que não o alcança — verde sobre o defeito.
        """
        alvo = tmp_path / "porta-que-liga-outro-elemento.conf"
        alvo.write_text(
            "[Element Speaker]\nswitch = mute\nvolume = merge\n",
            encoding="utf-8",
        )
        _, elemento, fora = self._decide(
            "sources-cabo-2026-09-20.txt",
            "scontents-dualsense-2026-09-20.txt",
            alvo,
        )
        assert (elemento, fora) == ("Headset", "sim"), (
            "o `merge` aqui é do `Speaker`; o elemento de captura da placa é o "
            f"`Headset` e continua fora. Veio elemento={elemento!r} fora={fora!r}"
        )

    def test_o_elemento_com_indice_ainda_e_o_mesmo_elemento(
        self, tmp_path: Path
    ) -> None:
        """`[Element Headset,1]` é o `Headset` — amarrar não pode virar cegueira.

        O `analog-output.conf.common:90` diz que o nome da seção é «o nome do
        elemento, ou nome e índice separados por vírgula». Recusar a forma com
        índice trocaria um verde falso por um vermelho falso.
        """
        alvo = tmp_path / "porta-com-indice.conf"
        alvo.write_text(
            "[Element Headset,1]\nswitch = mute\nvolume = merge\n",
            encoding="utf-8",
        )
        _, elemento, fora = self._decide(
            "sources-cabo-2026-09-20.txt",
            "scontents-dualsense-2026-09-20.txt",
            alvo,
        )
        assert (elemento, fora) == ("Headset", "não")

    def test_o_ucm_que_liga_outro_elemento_nao_conta(self, tmp_path: Path) -> None:
        """O mesmo defeito no outro dialeto, e o UCM é quem manda HOJE.

        Um `SectionDevice` que declare `CaptureVolume` sobre outro elemento da
        placa põe ESSE no deslizante e deixa o de captura fora. A régua tem de
        ver o nome, não a palavra-chave.
        """
        alvo = tmp_path / "porta-ucm-de-outro-elemento.txt"
        alvo.write_text(
            'SectionDevice."Mic" {\n'
            "\tValue {\n"
            '\t\tCapturePCM "hw:${CardId},0"\n'
            '\t\tCaptureMixerElem "Mic Boost"\n'
            "\t}\n"
            "}\n",
            encoding="utf-8",
        )
        _, elemento, fora = self._decide(
            "sources-cabo-2026-09-20.txt",
            "scontents-dualsense-2026-09-20.txt",
            alvo,
        )
        assert (elemento, fora) == ("Headset", "sim"), (
            "o `CaptureMixerElem` aqui nomeia o `Mic Boost`; o `Headset` da "
            f"placa continua fora. Veio elemento={elemento!r} fora={fora!r}"
        )

    def test_o_ucm_que_liga_o_elemento_da_verde(self, tmp_path: Path) -> None:
        """E o contrário precisa valer, senão a amarra vira recusa cega.

        Este é o arquivo que o `assets/ucm/DualSense-HiFi.conf` PRECISARIA ter
        para o ganho entrar no caminho — e é a forma que a cura vai tomar no
        dia em que ela decidir ligá-lo.
        """
        alvo = tmp_path / "porta-ucm-que-liga.txt"
        alvo.write_text(
            'SectionDevice."Mic" {\n'
            "\tValue {\n"
            '\t\tCapturePCM "hw:${CardId},0"\n'
            "\t\tCaptureVolume \"name='Headset Capture Volume'\"\n"
            "\t}\n"
            "}\n",
            encoding="utf-8",
        )
        _, elemento, fora = self._decide(
            "sources-cabo-2026-09-20.txt",
            "scontents-dualsense-2026-09-20.txt",
            alvo,
        )
        assert (elemento, fora) == ("Headset", "não")

    def test_elemento_so_de_chave_nao_e_ganho(self, tmp_path: Path) -> None:
        """Um elemento que só LIGA e DESLIGA não é um ganho, e não é o alvo.

        No vocabulário do `amixer scontents`, `cvolume` é a capacidade de
        volume de captura e `cswitch` é a de chave. Sem `cvolume` não há valor
        a pôr no deslizante — logo não há nada «fora de alcance», e reprovar
        aí seria inventar defeito numa placa que não tem o que ligar.

        **Por que DERIVADO e não gravado:** medido nesta bancada em 20/09/2026,
        as três placas desta máquina não têm um só elemento de captura com
        `cswitch` e sem `cvolume` (placa 0: só `pswitch`; placa 1: `cvolume
        cswitch`; placa 2, o DualSense: `cvolume … cswitch …`). O caso existe
        no mundo e não existe aqui, então ele nasce da gravação por UMA
        subtração declarada — e o teste reprova se a subtração não morder.
        """
        gravada = FIXTURES_MIC_CABO / "scontents-dualsense-2026-09-20.txt"
        texto = gravada.read_text(encoding="utf-8")
        so_chave = texto.replace("cvolume cvolume-joined ", "")
        assert so_chave != texto, (
            "a gravação mudou de forma: sem tirar a capacidade de volume de "
            "captura, este teste mede o mesmo que o de cima e não morde nada"
        )
        alvo = tmp_path / "scontents-so-chave.txt"
        alvo.write_text(so_chave, encoding="utf-8")
        _, elemento, fora = self._decide(
            "sources-cabo-2026-09-20.txt", alvo, "porta-ucm-mic-2026-09-20.txt"
        )
        assert elemento == "", (
            f"elemento só de chave não é ganho de captura; saiu {elemento!r}"
        )
        assert fora == "não", (
            "sem ganho na placa não há o que ficar fora de alcance"
        )

    def test_o_ganho_ganha_do_elemento_so_de_chave(self, tmp_path: Path) -> None:
        """E quando a placa tem os dois, quem responde é o que tem VOLUME.

        Ordem importa: o elemento só de chave vem PRIMEIRO no arquivo. Uma
        régua que parasse no primeiro elemento de captura devolveria o nome
        errado, e o veredito passaria a ser sobre outro elemento.
        """
        gravada = FIXTURES_MIC_CABO / "scontents-dualsense-2026-09-20.txt"
        texto = gravada.read_text(encoding="utf-8")
        mudo = (
            "Simple mixer control 'Headset Mute',0\n"
            "  Capabilities: cswitch cswitch-joined\n"
            "  Capture channels: Mono\n"
            "  Mono: Capture [on]\n"
        )
        alvo = tmp_path / "scontents-com-os-dois.txt"
        alvo.write_text(mudo + texto, encoding="utf-8")
        _, elemento, fora = self._decide(
            "sources-cabo-2026-09-20.txt", alvo, "porta-ucm-mic-2026-09-20.txt"
        )
        assert elemento == "Headset", (
            "com um elemento só de chave na frente, o ganho continua sendo o "
            f"`Headset`; saiu {elemento!r}"
        )
        assert fora == "sim"

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


#: Recorte GRAVADO de `/proc/asound/cards` desta bancada, 20/09/2026, com o
#: controle no cabo. O `check_mic_ganho_de_captura` lê daqui UMA coisa — o
#: índice da placa que casa a marca —, e é por isso que o gancho
#: `HEFESTO_PROC_CARDS` existe: sem ele, nenhum teste alcança a metade que fala
#: com a máquina, e ela ficou sem régua até 20/09.
CARDS_COM_DUALSENSE = (
    " 0 [NVidia         ]: HDA-Intel - HDA NVidia\n"
    "                      HDA NVidia at 0xfc080000 irq 83\n"
    " 2 [Controller     ]: USB-Audio - DualSense Wireless Controller\n"
    "                      Sony Interactive Entertainment DualSense Wireless"
    " Controller\n"
)
CARDS_SEM_DUALSENSE = (
    " 0 [NVidia         ]: HDA-Intel - HDA NVidia\n"
    "                      HDA NVidia at 0xfc080000 irq 83\n"
)


@pytest.mark.skipif(not DOCTOR.exists(), reason="scripts/doctor.sh ausente")
@pytest.mark.skipif(
    not FIXTURES_MIC_CABO.is_dir(), reason="tests/fixtures/mic-cabo ausente"
)
class TestOChamadorDoDoctorFalaComAMaquina:
    """A METADE QUE FALA COM A MÁQUINA, que não tinha régua nenhuma.

    O decisor puro acima era medido de sete jeitos; `check_mic_ganho_de_captura`
    e `_definicao_da_porta_de_captura` — os dois que juntam as leituras, acham a
    definição da porta no disco e escolhem a FRASE que sai no `doctor` — não
    eram medidos de nenhum. Dava para arrancar a busca da definição, inverter o
    veredito ou trocar a ordem dos dois arquivos que o chamador passa, e os
    testes ficavam todos verdes: a cura tinha um buraco do tamanho dela mesma.

    Ela roda sem aparelho e sem servidor de som: `pactl` e `amixer` são funções
    de shell que imprimem as gravações, e os três ganchos do próprio produto
    (`HEFESTO_PROC_CARDS`, `HEFESTO_RAIZ_UCM`, `HEFESTO_RAIZ_ACP`) apontam para
    o `tmp_path`. Nada daqui toca o som da máquina de quem roda.
    """

    _RECEITA = """
set -uo pipefail
source "{doctor}" >/dev/null 2>&1 || true
pactl() {{ [ "$*" = "list sources" ] && cat "${{SOURCES}}"; }}
amixer() {{ cat "${{SCONTENTS}}"; }}
pass() {{ printf 'PASS %s\\n' "$*"; }}
warn() {{ printf 'WARN %s\\n' "$*"; }}
info() {{ printf 'INFO %s\\n' "$*"; }}
check_mic_ganho_de_captura
"""

    def _doctor_diz(
        self,
        tmp_path: Path,
        *,
        cards: str = CARDS_COM_DUALSENSE,
        sources: str = "sources-cabo-2026-09-20.txt",
        scontents: str = "scontents-dualsense-2026-09-20.txt",
        ucm: str | None = "assets/ucm/DualSense-HiFi.conf",
        acp: dict[str, str] | None = None,
    ) -> str:
        """Roda o `check_` inteiro e devolve as linhas que ele mandou à tela."""
        cards_txt = tmp_path / "cards"
        cards_txt.write_text(cards, encoding="utf-8")
        raiz_ucm = tmp_path / "ucm2"
        (raiz_ucm / "USB-Audio" / "Hefesto").mkdir(parents=True, exist_ok=True)
        if ucm is not None:
            destino = raiz_ucm / "USB-Audio" / "Hefesto" / "DualSense-HiFi.conf"
            destino.write_text(
                (REPO_ROOT / ucm).read_text(encoding="utf-8"), encoding="utf-8"
            )
        raiz_acp = tmp_path / "paths"
        raiz_acp.mkdir(exist_ok=True)
        for nome, corpo in (acp or {}).items():
            (raiz_acp / nome).write_text(corpo, encoding="utf-8")
        proc = subprocess.run(
            [BASH, "-c", self._RECEITA.format(doctor=DOCTOR)],
            capture_output=True,
            text=True,
            env={
                "SOURCES": str(FIXTURES_MIC_CABO / sources),
                "SCONTENTS": str(FIXTURES_MIC_CABO / scontents),
                "HEFESTO_PROC_CARDS": str(cards_txt),
                "HEFESTO_RAIZ_UCM": str(raiz_ucm),
                "HEFESTO_RAIZ_ACP": str(raiz_acp),
                "PATH": "/usr/bin:/bin",
                "HOME": "/nonexistent",
                "LC_ALL": "C",
            },
            check=False,
        )
        return proc.stdout

    def test_a_definicao_da_porta_do_ucm_sai_do_disco(self, tmp_path: Path) -> None:
        """M3 pela frente: sem a definição da porta não há veredito honesto.

        `_definicao_da_porta_de_captura` é a única parte IMPURA da dupla. Se ela
        voltar de mãos vazias — por retornar cedo, por procurar o arquivo
        errado, por qualquer motivo — o decisor recebe um arquivo vazio, não
        acha ligação nenhuma e REPROVA TUDO, inclusive o que está certo. Um
        instrumento que reprova sempre não é rigor: é ruído.
        """
        raiz_ucm = tmp_path / "ucm2" / "USB-Audio" / "Hefesto"
        raiz_ucm.mkdir(parents=True)
        alvo = raiz_ucm / "DualSense-HiFi.conf"
        alvo.write_text(
            (REPO_ROOT / "assets" / "ucm" / "DualSense-HiFi.conf").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        saida = tmp_path / "porta"
        proc = subprocess.run(
            [
                BASH,
                "-c",
                f'source "{DOCTOR}" >/dev/null 2>&1 || true\n'
                f'_definicao_da_porta_de_captura "[In] Mic" "{saida}"\n',
            ],
            capture_output=True,
            text=True,
            env={
                "HEFESTO_RAIZ_UCM": str(tmp_path / "ucm2"),
                "PATH": "/usr/bin:/bin",
                "HOME": "/nonexistent",
                "LC_ALL": "C",
            },
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        texto = saida.read_text(encoding="utf-8")
        assert 'SectionDevice."Mic"' in texto, (
            f"a definição da porta ativa tem de sair do disco; veio {texto!r}"
        )
        assert "CapturePCM" in texto, "o corpo do dispositivo, não só a linha"
        assert "SectionDevice.\"Speaker\"" not in texto, (
            "o recorte é do dispositivo da porta ATIVA; trazer o vizinho junto "
            "faria o decisor responder sobre o alto-falante"
        )

    def test_o_estado_de_hoje_chega_ao_doctor_como_aviso(
        self, tmp_path: Path
    ) -> None:
        """O achado da sprint, na frase que sai na máquina dela.

        É WARN e nunca FAIL de propósito — o estado nasceu com o produto e a
        cura é decisão dela. E a linha diz, dentro dela mesma, que não é um
        veredito sobre a qualidade do áudio: verde aqui nunca significou
        «o microfone está bom».
        """
        saida = self._doctor_diz(tmp_path)
        assert "WARN" in saida, f"o estado de hoje tem de avisar; veio {saida!r}"
        assert "PASS" not in saida, f"e não pode passar; veio {saida!r}"
        assert "[In] Mic" in saida, "a frase nomeia a porta ativa"
        assert "'Headset'" in saida, "e nomeia o elemento que ficou fora"
        assert "FAIL" not in saida, "nunca FAIL: a cura é decisão dela"
        assert "não sobre a qualidade do áudio" in saida, (
            "a ressalva mora na própria linha, senão o verde é lido como "
            f"«o microfone está bom». Veio {saida!r}"
        )

    def test_uma_porta_que_liga_o_ganho_chega_como_verde(
        self, tmp_path: Path
    ) -> None:
        """O outro lado, e é ele que mata as três mutações de uma vez.

        A porta ativa passa a ser uma do alsa-card-profile que declara
        `volume = merge` sobre o `Headset`. Com a busca da definição arrancada
        (M3), com o veredito invertido (M6) ou com os dois arquivos trocados de
        ordem no chamador (M7), esta linha deixa de sair verde.
        """
        conf = (
            FIXTURES_MIC_CABO / "porta-acp-analog-input-headset-mic.conf"
        ).read_text(encoding="utf-8")
        gravada = (
            FIXTURES_MIC_CABO / "sources-cabo-2026-09-20.txt"
        ).read_text(encoding="utf-8")
        trocada = gravada.replace("[In] Mic", "analog-input-headset-mic")
        assert trocada != gravada, (
            "a gravação mudou de forma: sem trocar a porta ativa este teste "
            "mede o mesmo cenário do anterior"
        )
        sources = tmp_path / "sources-com-porta-que-liga.txt"
        sources.write_text(trocada, encoding="utf-8")
        cards_txt = tmp_path / "cards"
        cards_txt.write_text(CARDS_COM_DUALSENSE, encoding="utf-8")
        raiz_acp = tmp_path / "paths"
        raiz_acp.mkdir(exist_ok=True)
        (raiz_acp / "analog-input-headset-mic.conf").write_text(
            conf, encoding="utf-8"
        )
        proc = subprocess.run(
            [BASH, "-c", self._RECEITA.format(doctor=DOCTOR)],
            capture_output=True,
            text=True,
            env={
                "SOURCES": str(sources),
                "SCONTENTS": str(
                    FIXTURES_MIC_CABO / "scontents-dualsense-2026-09-20.txt"
                ),
                "HEFESTO_PROC_CARDS": str(cards_txt),
                "HEFESTO_RAIZ_UCM": str(tmp_path / "sem-ucm"),
                "HEFESTO_RAIZ_ACP": str(raiz_acp),
                "PATH": "/usr/bin:/bin",
                "HOME": "/nonexistent",
                "LC_ALL": "C",
            },
            check=False,
        )
        saida = proc.stdout
        assert "PASS" in saida, (
            f"esta porta LIGA o `Headset`: tem de sair verde. Veio {saida!r}"
        )
        assert "WARN" not in saida, f"e não pode avisar; veio {saida!r}"
        assert "analog-input-headset-mic" in saida, "a frase nomeia a porta"

    def test_sem_placa_do_dualsense_o_check_diz_que_nao_conferiu(
        self, tmp_path: Path
    ) -> None:
        """Sem controle no cabo não há veredito — e não há verde.

        Calar e passar são coisas diferentes: «não conferi» tem de chegar à
        tela como informação, nunca como aprovação.
        """
        saida = self._doctor_diz(tmp_path, cards=CARDS_SEM_DUALSENSE)
        assert "PASS" not in saida and "WARN" not in saida, (
            f"sem placa não se decide nada; veio {saida!r}"
        )
        assert "nenhum DualSense no cabo" in saida, saida
