"""LIGAR-QUE-APAGAVA-A-CURA-01 — o botão "Ligar" desarmava a cura de 08/08.

MEDIDO no código, em 10/08/2026, seguindo a cadeia inteira de ponta a ponta:

    gui/main.glade:3121            <signal handler="on_emulation_mic_on"/>
    emulation_actions.py:511-526   -> _run_mic("--enable-mic", ...)
    fix_wireplumber_default_source.sh (enable_mic_dualsense)
                                   -> rm -f nos TRÊS drop-ins, o 51 junto

O 51 **era** supressão: até MONITOR-QUE-VENCE-01 (commit 6c428cd, 08/08) ele
rebaixava a entrada do controle para ``priority.session = 50``, e removê-lo ao
ligar o mic era coerente com o nome da operação. Naquele commit ele virou o
CONTRÁRIO — a entrada passou a **1500**, a faixa medida que fica acima de
qualquer monitor (1109) e abaixo de qualquer captura real (2009). O 51 é o
PROMOTOR desde então.

O ``rm -f`` que ficou no ``--enable-mic`` desarmava, portanto, a cura de 08/08
no gesto de LIGAR o microfone: sem o arquivo, a entrada volta ao 50 de fábrica,
o monitor da saída vence o microfone por vinte e duas vezes, e o que qualquer
aplicativo grava é o eco do que sai. É o defeito que a sprint
``2026-08-08-MONITOR-QUE-VENCE-01`` mediu e provou ao vivo, reintroduzido pelo
único botão que existe para o caso contrário.

E a tela afirmava o oposto do que tinha acontecido: ``_mic_is_on()`` perguntava
só pelo 52/53, então logo depois de apagar o promotor o rótulo escrevia
**"Ligado"** em verde.

O QUE ESTE ARQUIVO TRAVA
========================
1. ``--enable-mic`` não apaga o promotor, e o GARANTE quando ele falta;
2. ``--enable-mic`` continua removendo a supressão de verdade (52/53) — sem este
   contrapeso, "curar" viraria não fazer nada;
3. a promoção EXPLÍCITA (``--promote-source``) continua removendo o 51, porque
   ``doctor.sh:_prefere_mic_do_dualsense`` lê a ausência dele como a escolha a
   dedo da usuária;
4. a tela só chama de "Ligado" o que está ligado de verdade.

Nada aqui toca o áudio da máquina: as funções de shell exercitadas são as que
só mexem em ARQUIVO, num ``HOME`` de mentira, e ainda assim com um ``systemctl``
dublê na frente do PATH — cinto e suspensório, porque o preço de um engano seria
o WirePlumber da sessão do usuário.
"""

from __future__ import annotations

import subprocess
from pathlib import Path



RAIZ = Path(__file__).resolve().parents[2]
WP_FIX = RAIZ / "scripts" / "fix_wireplumber_default_source.sh"

PROMOTOR = "51-hefesto-dualsense-no-default-source.conf"
DISABLE_SRC = "52-hefesto-dualsense-disable-source.conf"
DISABLE_OUT = "53-hefesto-dualsense-disable-output.conf"

ASSET_PROMOTOR = RAIZ / "assets" / "wireplumber" / PROMOTOR


def _ambiente(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    """Devolve ``(dir_dos_dropins, env)`` para rodar o wp-fix com segurança."""
    casa = tmp_path / "casa"
    dropins = casa / ".config" / "wireplumber" / "wireplumber.conf.d"
    dropins.mkdir(parents=True)
    binario = tmp_path / "bin"
    binario.mkdir()
    for nome in ("systemctl", "wpctl", "pactl"):
        alvo = binario / nome
        alvo.write_text(
            f'#!/bin/bash\nprintf "DUBLE {nome} %s\\n" "$*" >&2\nexit 0\n',
            encoding="utf-8",
        )
        alvo.chmod(0o755)
    env = {
        "PATH": f"{binario}:/usr/bin:/bin",
        "HOME": str(casa),
        "WP_FIX": str(WP_FIX),
    }
    return dropins, env


def _rodar(func: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Executa uma função REAL do wp-fix por ``source``, sem despachar o main."""
    return subprocess.run(
        ["bash", "-c", f'set --; source "$WP_FIX"; {func}'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**env},
    )


def _planta(dropins: Path, *nomes: str) -> None:
    for nome in nomes:
        if nome == PROMOTOR:
            dropins.joinpath(nome).write_text(
                ASSET_PROMOTOR.read_text(encoding="utf-8"), encoding="utf-8"
            )
        else:
            dropins.joinpath(nome).write_text("# dublê\n", encoding="utf-8")


def test_ligar_o_mic_nao_apaga_o_promotor(tmp_path: Path) -> None:
    """O defeito, em uma asserção."""
    dropins, env = _ambiente(tmp_path)
    _planta(dropins, PROMOTOR, DISABLE_SRC, DISABLE_OUT)

    res = _rodar("_arma_dropins_do_mic", env)

    assert res.returncode == 0, res.stderr
    assert (dropins / PROMOTOR).is_file(), (
        "o `--enable-mic` apagou o drop-in 51 — que desde MONITOR-QUE-VENCE-01 "
        "é o PROMOTOR (priority.session = 1500), não uma supressão. Sem ele o "
        "monitor da saída (1109) vence o microfone (50) e o que se grava é o "
        f"eco do que sai.\n{res.stdout}"
    )
    assert "priority.session = 1500" in (dropins / PROMOTOR).read_text(encoding="utf-8")


def test_ligar_o_mic_instala_o_promotor_quando_ele_falta(tmp_path: Path) -> None:
    """Ligar o mic é ARMAR a cura, não só deixar de desarmá-la."""
    dropins, env = _ambiente(tmp_path)
    _planta(dropins, DISABLE_SRC, DISABLE_OUT)

    res = _rodar("_arma_dropins_do_mic", env)

    assert res.returncode == 0, res.stderr
    assert (dropins / PROMOTOR).is_file(), (
        f"o promotor não foi instalado; o mic ficaria livre e sem prioridade.\n{res.stdout}"
    )
    assert "priority.session = 1500" in (dropins / PROMOTOR).read_text(encoding="utf-8")


def test_ligar_o_mic_e_idempotente(tmp_path: Path) -> None:
    """Dois cliques seguidos em "Ligar" terminam no mesmo lugar."""
    dropins, env = _ambiente(tmp_path)
    _planta(dropins, DISABLE_SRC, DISABLE_OUT)

    primeiro = _rodar("_arma_dropins_do_mic", env)
    segundo = _rodar("_arma_dropins_do_mic", env)

    assert primeiro.returncode == 0, primeiro.stderr
    assert segundo.returncode == 0, segundo.stderr
    assert (dropins / PROMOTOR).is_file()
    assert "promotor mantido" in segundo.stdout, segundo.stdout


def test_ligar_o_mic_continua_removendo_a_supressao_de_verdade(tmp_path: Path) -> None:
    """Sem isto, "curar" viraria não fazer nada."""
    dropins, env = _ambiente(tmp_path)
    _planta(dropins, PROMOTOR, DISABLE_SRC, DISABLE_OUT)

    res = _rodar("_arma_dropins_do_mic", env)

    assert res.returncode == 0, res.stderr
    assert not (dropins / DISABLE_SRC).exists(), (
        f"o 52 (node.disabled do mic) ficou — o mic continua sumido.\n{res.stdout}"
    )
    assert not (dropins / DISABLE_OUT).exists(), (
        f"o 53 (node.disabled da saída) ficou — o fone do controle segue mudo.\n{res.stdout}"
    )


def test_a_promocao_explicita_continua_removendo_o_51(tmp_path: Path) -> None:
    """A ausência do 51 é um SINAL que outro programa lê."""
    dropins, env = _ambiente(tmp_path)
    _planta(dropins, PROMOTOR, DISABLE_SRC)

    res = _rodar('_arma_dropins_do_mic "sem-promotor"', env)

    assert res.returncode == 0, res.stderr
    assert not (dropins / PROMOTOR).exists(), (
        f"a promoção explícita deixou o 51 no lugar.\n{res.stdout}"
    )
    assert not (dropins / DISABLE_SRC).exists(), res.stdout


def test_a_promocao_pede_sem_promotor_ao_enable_mic() -> None:
    """A fiação: quem promove tem de pedir o modo, senão herda o novo padrão."""
    texto = WP_FIX.read_text(encoding="utf-8")
    inicio = texto.index("promote_source_dualsense() {")
    corpo = texto[inicio : texto.index("\n}\n", inicio)]
    assert 'enable_mic_dualsense "sem-promotor"' in corpo, (
        "a promoção explícita voltou a herdar o padrão do `--enable-mic`, que "
        "MANTÉM o 51 — e a ausência do 51 é o sinal que o doctor lê como "
        "promoção a dedo da usuária."
    )


def test_o_enable_mic_do_despacho_nao_pede_sem_promotor() -> None:
    """O caminho do botão "Ligar" usa o padrão, e o padrão guarda o promotor."""
    texto = WP_FIX.read_text(encoding="utf-8")
    inicio = texto.index("    enable-mic)")
    bloco = texto[inicio : texto.index("    unmute-routes)", inicio)]
    assert "enable_mic_dualsense" in bloco
    assert "sem-promotor" not in bloco, (
        "o `--enable-mic` (o que o botão “Ligar” da aba Emulação roda) voltou a "
        "apagar o promotor"
    )


class _RotuloFalso:
    """Um GtkLabel de mentira que só guarda o que lhe mandam escrever."""

    def __init__(self) -> None:
        self.markup = ""
        self.tooltip = ""

    def set_markup(self, texto: str) -> None:
        self.markup = texto

    def set_tooltip_text(self, texto: str) -> None:
        self.tooltip = texto


#: QUARTO estado, `MIC_SEM_ALVO`: sem placa ALSA de DualSense em
#: DualSense no cabo desta máquina. É o vício de bancada da NO-MEU-FUNCIONA-01,
_CARDS_COM_UM_DUALSENSE = """\
 0 [HDMI           ]: HDA-Intel - HDA ATI HDMI
                      HDA ATI HDMI at 0xfe960000 irq 66
 2 [Controller     ]: USB-Audio - DualSense Wireless Controller
                      Sony Interactive Entertainment DualSense Wireless Controller at usb-0000:0d
"""


