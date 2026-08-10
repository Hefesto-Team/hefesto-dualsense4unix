"""O-PRODUTO-PROMOVE-E-RECLAMA-01 — o doctor acusava a escolha dela como falha.

O QUE ELA VIU, no fim do install de 10/08/2026
==============================================
Duas linhas seguidas do doctor, o mesmo aparelho, vereditos opostos::

    [FAIL] DualSense é o microfone ATIVO com outra fonte disponível — rode: ...
    [ OK ] a fonte de captura padrão é uma entrada de verdade (alsa_input...DualSense...)

E as seis linhas seguintes, todas OK: a saída preservada, o sink não-mudo, sem
mute persistido na camada 1, a source não-muda, a porta de captura presente. Um
microfone inteiramente saudável — declarado FALHA.

A CAUSA, MEDIDA
===============
Em 08/08 (MONITOR-QUE-VENCE-01, commit `6c428cd`) o drop-in **51** deixou de
SUPRIMIR e passou a PROMOVER a entrada do controle (`priority.session = 1500`,
acima de qualquer monitor). E ele entra por **DEFAULT** no install
(`WITH_WIREPLUMBER_FIX=1`).

Ou seja: **o produto passou a criar exatamente a condição que este check
continuava acusando.** O nome do arquivo — `51-hefesto-dualsense-no-default-source
.conf` — é o fóssil da regra antiga, e ajudou a esconder a inversão.

O OPT-IN QUE EXISTIA NÃO ERA DELA
=================================
Havia um opt-in: a variável de ambiente
`HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED=1`. Pela regra desta casa — *"tudo
tem que focar em funcionar na interface do app e no install"* — opt-in que só se
alcança exportando env não é opt-in dela; é opt-in de quem lê o código. Ela
disse, com todas as letras, que quer o microfone do controle: *"sobre o microfone
tem que gravar minha voz"*.

O promotor no disco, esse sim, é gesto dela: só existe se o install rodou sem
`--keep-dualsense-mic`, ou se ela clicou "Ligar" na aba Emulação.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
PROMOTOR = "51-hefesto-dualsense-no-default-source.conf"

#: O trecho da função que dá o veredito, isolado do resto do doctor.
_FUNCAO = "check_wireplumber_source"


def _fonte_da_funcao() -> str:
    texto = DOCTOR.read_text(encoding="utf-8")
    i = texto.index(f"{_FUNCAO}()")
    return texto[i : texto.index("\n}\n", i)]


def test_o_promotor_no_disco_conta_como_opt_in() -> None:
    """A cura. Morde ao apagar a guarda do promotor.

    Arranque para ver reprovar: tirar o `if [[ -f ... 51-... ]]` da função. É o
    estado do produto até 10/08/2026 — e o efeito é o install dela terminar em
    FALHA por causa da configuração que o próprio install acabou de criar.
    """
    fonte = _fonte_da_funcao()
    assert PROMOTOR in fonte, (
        "a função não olha o promotor — volta a acusar como falha o microfone "
        "que o próprio install promoveu"
    )
    i_promotor = fonte.index(PROMOTOR)
    i_fail = fonte.index("fail ")
    assert i_promotor < i_fail, (
        "a guarda do promotor tem de vir ANTES do `fail`, senão não guarda nada"
    )


def test_a_guarda_por_variavel_de_ambiente_continua_valendo() -> None:
    """A cura ACRESCENTA um opt-in; não tira o que já existia.

    Quem já exporta `DUALSENSE_MIC_INTENDED=1` (scripts de terceiros, CI,
    ambientes headless) continua atendido. Não se apaga decisão medida.
    """
    fonte = _fonte_da_funcao()
    assert "HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED" in fonte


def test_sem_o_promotor_o_alarme_continua() -> None:
    """O contraponto — a cura não pode calar o check que ela veio ajustar.

    O caso que o `fail` existe para pegar é outro: o DualSense virando microfone
    padrão **sozinho**, sem promotor nenhum, com um microfone melhor disponível.
    Isso é o mic dela sequestrado sem ninguém pedir, e continua sendo falha.

    Morde ao trocar a guarda por um `return` incondicional.
    """
    fonte = _fonte_da_funcao()
    assert "fail " in fonte, "o alarme sumiu — o check virou decoração"
    assert "has_other" in fonte, (
        "a distinção entre 'há outra fonte' e 'é a única' se perdeu"
    )


@pytest.mark.skipif(
    not shutil.which("bash"), reason="precisa de bash para rodar o doctor"
)
def test_a_guarda_le_o_home_da_chamada_e_nao_um_caminho_cravado(
    tmp_path: Path,
) -> None:
    """O caminho do promotor sai do `HOME` vivo, não de um literal de instalação.

    É a mesma correção que a `conftest` desta casa já registrou para o
    `storm_doctor` e o `_wp_dropin_dir` em 05/08, a pedido dela: *"preciso que as
    constantes apontem pros arquivos reais"*. Com `HOME` cravado, o doctor
    responderia sobre a máquina de quem empacotou, não sobre a dela — e num
    teste isso vaza para o `~/.config` de verdade.

    Aqui a prova é direta: com um `HOME` de mentira e o promotor DENTRO dele, o
    texto do veredito tem de citar o promotor.
    """
    fonte = _fonte_da_funcao()
    assert '${HOME}' in fonte, "o caminho do promotor não sai do HOME vivo"

    falso_home = tmp_path / "home"
    (falso_home / ".config" / "wireplumber" / "wireplumber.conf.d").mkdir(parents=True)
    (
        falso_home / ".config" / "wireplumber" / "wireplumber.conf.d" / PROMOTOR
    ).write_text("x", encoding="utf-8")
    # Só a expansão do caminho é exercitada — o doctor inteiro precisaria de
    # wpctl e de sessão de áudio, que um unitário não tem.
    script = (
        f'HOME="{falso_home}"\n'
        'if [[ -f "${HOME}/.config/wireplumber/wireplumber.conf.d/'
        f'{PROMOTOR}" ]]; then echo ACHOU; else echo NAO; fi\n'
    )
    r = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, env=dict(os.environ)
    )
    assert r.stdout.strip() == "ACHOU"
