"""INSTALADOR-QUE-APROVOU-O-MONITOR-01 — o install dizia OK sobre o que o doctor reprova.

MEDIDO em 09/08/2026, na máquina dela, no MESMO terminal, com dois minutos de
diferença:

    passo 10/11 do install.sh:
        OK: microfone padrão ativo = alsa_output.pci-0000_0c_00.4.iec958-stereo.monitor
    scripts/doctor.sh, logo depois:
        [FAIL] a fonte de captura padrão é um MONITOR — o que qualquer app gravar
               é o áudio de SAÍDA do sistema, não a voz

Um dos dois critérios estava errado, e era o do install. O
``verify_active_not_dualsense`` do ``fix_wireplumber_default_source.sh`` só
perguntava *"o ativo é o mic do DualSense?"* — um monitor não é, então a resposta
saía ``OK`` e o instalador imprimia sucesso. A pergunta é estreita demais para a
afirmação que o passo faz com ela. O doctor estava certo: monitor como fonte
padrão é defeito PRÓPRIO, e é privacidade — tudo o que se grava é o áudio de
saída, e o medidor de nível mostra sinal, então PARECE que está funcionando.

A MEDIÇÃO QUE A SPRINT SEM-MICROFONE-NENHUM-01 DEIXOU PENDENTE
==============================================================
Ela estava marcada SEM PROVA ("é plausível que o pipewire-pulse faça a própria
seleção quando a metadata está vazia"). Está feita, e REFUTA a hipótese:

    $ pw-metadata -n default
    default.configured.audio.source = alsa_input.pci-0000_0c_00.4.analog-stereo
    default.audio.source            = alsa_output.pci-0000_0c_00.4.iec958-stereo

A metadata NÃO está vazia, e o valor eleito é o nó do SINK — o ``.monitor`` é
sufixo que a camada pulse acrescenta ao publicar. Quem elege é o WirePlumber, e
cura pelo lado dele CHEGA no ``pactl get-default-source``. GRAU: MEDIDO.

A mesma medição mostra o segundo defeito: o ``configured`` é a onboard, que o
``reset_default_source`` elegeu — e o WirePlumber a recusa (as três portas de
captura dela estão ``not available``) e reelege o sink. O instalador elegia um nó
que não para de pé, sobrescrevia a preferência persistida dela com ele, e chamava
o resultado de sucesso.

O QUE ESTE ARQUIVO TRAVA
========================
1. monitor NUNCA sai como ``OK`` da verificação do install (exit 3, e o texto diz
   o que está acontecendo);
2. a escolha do alvo usa o MESMO filtro de porta usável do doctor — quando não há
   fonte que se sustente, não se elege NADA (RECEITA-ERRADA-01: um critério só);
3. o ``install.sh`` dá um veredito FINAL do microfone, depois da cura, e ele
   reprova o monitor sem oferecer comando impotente.

Molde: tests/unit/test_fonte_padrao_01_e_cura_do_fix_mic.py (funções shell REAIS
executadas por ``source``, com um ``pactl`` dublê num PATH temporário).
Nenhum teste deste arquivo toca o áudio da máquina.
"""

# ruff: noqa: E501  (saída literal do `pactl` — quebrar a linha mudaria o dado)

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
WP_FIX = RAIZ / "scripts" / "fix_wireplumber_default_source.sh"
INSTALL = RAIZ / "install.sh"

#: O nome MEDIDO na máquina dela em 09/08/2026 — o monitor da saída S/PDIF.
MONITOR_DELA = "alsa_output.pci-0000_0c_00.4.iec958-stereo.monitor"
#: A única entrada de captura de verdade da máquina dela — com as TRÊS portas
#: `not available` (nada plugado no jack), medido no mesmo instante.
ONBOARD_DELA = "alsa_input.pci-0000_0c_00.4.analog-stereo"

#: `pactl list sources` (o longo) como ele saiu na máquina dela: o monitor sem
#: portas e a onboard com as três de captura `not available`.
PACTL_LONGO = f"""Source #61288
\tName: {MONITOR_DELA}
\tDescription: Monitor of Digital Stereo (IEC958)
\tMute: no

Source #61289
\tName: {ONBOARD_DELA}
\tDescription: Starship/Matisse HD Audio Controller Analog Stereo
\tMute: no
\tPorts:
\t\tanalog-input-front-mic: Front Microphone (type: Mic, priority: 8500, availability group: Legacy 1, not available)
\t\tanalog-input-rear-mic: Rear Microphone (type: Mic, priority: 8200, availability group: Legacy 2, not available)
\t\tanalog-input-linein: Line In (type: Line, priority: 8100, availability group: Legacy 3, not available)
\tActive Port: analog-input-front-mic
"""

PACTL_CURTO = (
    f"61288\t{MONITOR_DELA}\tPipeWire\ts32le 2ch 48000Hz\tSUSPENDED\n"
    f"61289\t{ONBOARD_DELA}\tPipeWire\ts32le 2ch 48000Hz\tSUSPENDED\n"
)

#: O mesmo cenário com uma webcam plugada: porta de captura `unknown`, que conta
#: como USÁVEL (medido em 26/07 — a entrada do controle grava de verdade com
#: `unknown`, e só o `not available` explícito reprova).
WEBCAM = "alsa_input.usb-046d_C920-02.analog-stereo"
PACTL_LONGO_COM_WEBCAM = PACTL_LONGO + f"""
Source #61300
\tName: {WEBCAM}
\tDescription: C920 Analog Stereo
\tPorts:
\t\tanalog-input-mic: Microphone (type: Mic, priority: 8700)
\tActive Port: analog-input-mic
"""
PACTL_CURTO_COM_WEBCAM = PACTL_CURTO + (
    f"61300\t{WEBCAM}\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n"
)


def _dubla_pactl(
    tmp_path: Path, *, padrao: str, longo: str = PACTL_LONGO, curto: str = PACTL_CURTO
) -> dict[str, str]:
    """Um `pactl` dublê num PATH temporário; devolve o env para o subprocess.

    Só responde o que as funções sob teste perguntam. Qualquer outro subcomando
    sai vazio com status 0 — dublê que finge saber tudo esconde chamada nova.
    """
    binario = tmp_path / "bin"
    binario.mkdir(exist_ok=True)
    (binario / "pactl").write_text(
        "#!/bin/bash\n"
        'case "$*" in\n'
        f'  "get-default-source") printf "%s\\n" "{padrao}" ;;\n'
        '  "list sources short") cat "$0.curto" ;;\n'
        '  "list sources") cat "$0.longo" ;;\n'
        "  *) : ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    (binario / "pactl.longo").write_text(longo, encoding="utf-8")
    (binario / "pactl.curto").write_text(curto, encoding="utf-8")
    (binario / "pactl").chmod(0o755)
    return {
        "PATH": f"{binario}:/usr/bin:/bin",
        "HOME": str(tmp_path / "casa"),
        "WP_FIX": str(WP_FIX),
    }


def _rodar(func: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Executa uma função do wp-fix por `source`, sem despachar o main dele."""
    return subprocess.run(
        ["bash", "-c", f'set --; source "$WP_FIX"; {func}'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**env},
    )


# ---------------------------------------------------------------------------
# 1. Monitor nunca mais sai como OK
# ---------------------------------------------------------------------------


def test_monitor_nao_e_aprovado_pela_verificacao_do_install(tmp_path: Path) -> None:
    """O estado EXATO de 09/08 na máquina dela tem de REPROVAR.

    Este é o teste que morde: com a cura arrancada, a função devolvia 0 e
    imprimia `OK: microfone padrão ativo = …monitor (DualSense fora)`.
    """
    env = _dubla_pactl(tmp_path, padrao=MONITOR_DELA)
    res = _rodar("verify_active_not_dualsense", env)
    assert res.returncode == 3, f"esperava exit 3 (monitor), veio {res.returncode}: {res.stdout}"
    assert "OK" not in res.stdout, f"o monitor voltou a ser aprovado: {res.stdout}"
    assert "MONITOR" in res.stdout
    # A consequência, não só o rótulo: ela precisa saber o que está sendo gravado.
    assert "SAÍDA" in res.stdout


def test_o_monitor_do_proprio_controle_tambem_reprova(tmp_path: Path) -> None:
    """FONTE-PADRÃO-01 (29/07) era este nome, e ele saía como OK duas vezes.

    O `.monitor` do sink do DualSense casa "DualSense" no nome sem ser o mic —
    e a verificação dizia `OK: mic do DualSense desabilitado`. É o mesmo defeito
    com outro nó: gravar a saída do controle não é gravar a voz dela.
    """
    monitor_do_controle = (
        "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
        "Controller-00.analog-surround-40.monitor"
    )
    env = _dubla_pactl(tmp_path, padrao=monitor_do_controle)
    res = _rodar("verify_active_not_dualsense", env)
    assert res.returncode == 3, res.stdout
    assert "OK" not in res.stdout


def test_entrada_de_verdade_continua_passando(tmp_path: Path) -> None:
    """A cura não pode reprovar o que sempre esteve certo."""
    env = _dubla_pactl(tmp_path, padrao=WEBCAM)
    res = _rodar("verify_active_not_dualsense", env)
    assert res.returncode == 0, res.stdout
    assert "OK" in res.stdout


@pytest.mark.parametrize(
    ("nome", "e_monitor"),
    [
        (MONITOR_DELA, True),
        ("alsa_output.pci-0000_0a_00.1.hdmi-stereo.Monitor", True),
        (ONBOARD_DELA, False),
        ("alsa_input.usb-DualSense.monitor-something", False),
        ("", False),
    ],
)
def test_is_monitor_source_classifica_pelo_sufixo(
    tmp_path: Path, nome: str, e_monitor: bool
) -> None:
    """No PipeWire o monitor termina em `.monitor` — sufixo do nó, não palpite.

    O caso do meio importa: um nó cujo nome CONTÉM "monitor" no meio não é um
    monitor, e reprovar por substring transformaria a cura em alarme falso.
    """
    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path), "WP_FIX": str(WP_FIX)}
    res = _rodar(f'is_monitor_source "{nome}"', env)
    assert (res.returncode == 0) is e_monitor, res.stdout


# ---------------------------------------------------------------------------
# 2. Um critério só: o alvo sai do mesmo filtro que a cura do doctor usa
# ---------------------------------------------------------------------------


def test_nao_elege_fonte_sem_porta_usavel(tmp_path: Path) -> None:
    """Sem fonte que se sustente, o instalador não elege NADA.

    Medido na máquina dela: elegia a onboard (três portas `not available`), o
    WirePlumber a recusava e reelegia o sink — e a preferência persistida dela
    tinha sido sobrescrita por um nó que não para de pé.
    """
    env = _dubla_pactl(tmp_path, padrao=MONITOR_DELA)
    res = _rodar("pick_target_source_name", env)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "", f"elegeu um nó sem porta usável: {res.stdout!r}"


def test_elege_a_fonte_com_porta_usavel_quando_ela_existe(tmp_path: Path) -> None:
    """Com a webcam plugada, o alvo é ela — e nunca um monitor."""
    env = _dubla_pactl(
        tmp_path,
        padrao=MONITOR_DELA,
        longo=PACTL_LONGO_COM_WEBCAM,
        curto=PACTL_CURTO_COM_WEBCAM,
    )
    res = _rodar("pick_target_source_name", env)
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == WEBCAM


def test_reset_diz_que_nao_elegeu_em_vez_de_eleger_qualquer_um(tmp_path: Path) -> None:
    """O silêncio é o que enganava: sem alvo, o passo tem de DIZER isso."""
    env = _dubla_pactl(tmp_path, padrao=MONITOR_DELA)
    res = _rodar("reset_default_source", env)
    assert "nenhuma fonte de captura com porta usável" in res.stdout, res.stdout


# ---------------------------------------------------------------------------
# 3. O install.sh dá um veredito FINAL do microfone
# ---------------------------------------------------------------------------


def _texto_do_install() -> str:
    return INSTALL.read_text(encoding="utf-8")


def test_install_confere_a_fonte_padrao_depois_da_cura() -> None:
    """A leitura final existe, e vem DEPOIS do `--fix-mic`.

    Antes desta ordem o veredito era sempre parcial: a verificação do wp-fix roda
    antes da cura, então aprovar ou reprovar ali é falar de um estado que o
    próprio passo ainda vai tentar mudar.
    """
    texto = _texto_do_install()
    assert "INSTALADOR-QUE-APROVOU-O-MONITOR-01" in texto
    pos_fix_mic = texto.find("doctor.sh\" --fix-mic --quiet")
    pos_veredito = texto.find('pactl get-default-source 2>/dev/null || true)"')
    assert pos_fix_mic > 0, "o passo 10 deixou de chamar a cura do microfone"
    assert pos_veredito > pos_fix_mic, "o veredito final do microfone não está DEPOIS da cura"


def test_install_reprova_o_monitor_com_a_consequencia_na_tela() -> None:
    """Não basta dizer "monitor": ela tem de ler o que isso faz com a voz dela."""
    texto = _texto_do_install()
    assert "o microfone padrão do sistema é um MONITOR" in texto
    assert "SAI do PC" in texto, "a consequência sumiu do texto do install"
    # O medidor mostrando sinal é o que faz o defeito não PARECER defeito.
    assert "parece estar funcionando" in texto


def test_install_nao_oferece_comando_impotente_para_o_monitor() -> None:
    """RECEITA-ERRADA-01: sem fonte de captura, não há comando que resolva.

    O bloco do veredito não pode mandar rodar `--fix-mic` (que acabou de rodar) —
    a saída honesta é dizer que o que resolve é conectar uma entrada de verdade.
    """
    texto = _texto_do_install()
    inicio = texto.find("o microfone padrão do sistema é um MONITOR")
    assert inicio > 0
    bloco = texto[inicio : inicio + 900]
    assert "--fix-mic" not in bloco, "o veredito voltou a oferecer um comando impotente"
    assert "conecte" in bloco.lower()


def test_o_wp_fix_documenta_o_exit_3() -> None:
    """Exit code novo sem contrato escrito é armadilha para o próximo chamador."""
    texto = WP_FIX.read_text(encoding="utf-8")
    cabecalho = texto[: texto.find("set -euo pipefail")]
    assert "3 = a fonte padrão é um MONITOR" in cabecalho


def test_install_trata_o_exit_3_sem_declarar_reeleicao() -> None:
    """rc 3 não é falha do drop-in — mas também não é "fonte padrão reeleita"."""
    texto = _texto_do_install()
    inicio = texto.find('step "10/11"')
    bloco = texto[inicio : inicio + 2000]
    assert '"${rc:-0}" -eq 3' in bloco
    assert "a fonte padrão ainda não é um microfone" in bloco


def test_nenhum_teste_daqui_toca_o_audio_da_maquina() -> None:
    """Cinto de segurança: o dublê é o único `pactl` que estes testes alcançam.

    Um comando de trocar a fonte padrão escapando daqui mudaria o áudio de quem
    roda a suíte — e é o áudio da máquina dela.

    A verificação monta os nomes por concatenação DE PROPÓSITO: escrever o
    comando por extenso aqui faria este teste encontrar a si mesmo e reprovar
    para sempre. Foi o que aconteceu na primeira versão — o cinto de segurança
    prendeu o próprio cinto.
    """
    fonte = Path(__file__).read_text(encoding="utf-8")
    proibidos = ("set-default-" + "source", "wpctl set-" + "default")
    for comando in proibidos:
        acertos = [
            linha
            for linha in fonte.splitlines()
            if comando in linha and "proibidos = (" not in linha
        ]
        assert not acertos, f"{comando} escapou em: {acertos}"
