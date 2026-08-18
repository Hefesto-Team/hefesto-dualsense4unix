"""Um microfone de verdade nunca perde para um monitor.

MONITOR-QUE-VENCE-01 (08/08/2026). MEDIDO na máquina dela, com o drop-in
instalado pelo `install.sh`:

    alsa_output…DualSense…analog-surround-40.monitor   priority.session = 1109
    alsa_input…DualSense…iec958-stereo                 priority.session =   50
    alsa_input.pci-…analog-stereo (a placa do PC)      priority.session = 2009

O monitor vencia o microfone por **vinte e duas vezes**, e a eleição de fonte
padrão entregava o áudio de SAÍDA no lugar da voz dela. O `install.sh` criava
essa condição por default, e a conferência final do próprio install a denunciava
no mesmo fôlego (`[FAIL] a fonte de captura padrão é um MONITOR`).

POR QUE A CURA DE 30/07 NÃO FUNCIONOU
=====================================
A `FONTE-PADRÃO-01` tinha visto o problema e acrescentado uma regra para rebaixar
o monitor. A regra está escrita, está correta na intenção, e **não dispara**:
`monitor.alsa.rules` só alcança nós criados pelo monitor de ALSA do WirePlumber,
e o nó `.monitor` de uma saída é derivado pelo **PipeWire** a partir do sink —
aquela camada não o vê. A medição prova: 1109, intocado.

O QUE ESTE ARQUIVO TRAVA
========================
O invariante, não o número mágico: **a entrada do controle tem de ficar acima de
qualquer monitor e abaixo de qualquer captura real.** Os limites da faixa são os
valores medidos, e estão escritos aqui para que a próxima pessoa saiba de onde
eles vieram.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DROPIN = RAIZ / "assets" / "wireplumber" / "51-hefesto-dualsense-no-default-source.conf"

#: MEDIDO em 08/08/2026 na máquina dela. O monitor mais alto que existe lá — e o
#: piso que a entrada do controle precisa vencer.
MONITOR_MAIS_ALTO_MEDIDO = 1109

#: MEDIDO no mesmo instante: a captura REAL da placa do PC. É o teto — acima
#: disto o controle voltaria a roubar o posto de um microfone de verdade, que é a
#: queixa que criou este arquivo.
CAPTURA_REAL_MEDIDA = 2009


def _prioridades_da_entrada() -> list[int]:
    """As `priority.session` dos blocos que casam `alsa_input.*DualSense`."""
    texto = DROPIN.read_text(encoding="utf-8")
    # cada bloco começa em `matches = [` e vai até o fim do `update-props`
    blocos = re.split(r"\n\s*\{\s*\n", texto)
    saida: list[int] = []
    for bloco in blocos:
        if "alsa_input" not in bloco:
            continue
        # ignora o comentário: só conta linha de regra de verdade
        linhas_de_regra = [ln for ln in bloco.splitlines() if not ln.lstrip().startswith("#")]
        corpo = "\n".join(linhas_de_regra)
        if "alsa_input" not in corpo:
            continue
        achado = re.search(r"priority\.session\s*=\s*(\d+)", corpo)
        if achado:
            saida.append(int(achado.group(1)))
    return saida


def test_a_entrada_do_controle_vence_qualquer_monitor() -> None:
    """A voz dela nunca pode perder para o laço de retorno do que sai.

    ARRANQUE A CURA (volte a entrada para 50) e este teste REPROVA. É o defeito
    que o `install.sh` instalava por default: o monitor a 1109 vencia o microfone
    a 50, e o que qualquer aplicativo gravasse era o áudio de saída.
    """
    prioridades = _prioridades_da_entrada()
    assert prioridades, (
        "nenhuma regra casa `alsa_input.*DualSense` com `priority.session` — o "
        "drop-in deixou de decidir a prioridade da ENTRADA do controle."
    )
    for valor in prioridades:
        assert valor > MONITOR_MAIS_ALTO_MEDIDO, (
            f"a entrada do controle está em {valor}, e o monitor do próprio "
            f"controle foi MEDIDO em {MONITOR_MAIS_ALTO_MEDIDO}. Um monitor "
            "vencendo um microfone significa que a gravação dela captura o áudio "
            "de SAÍDA, não a voz. Ver "
            "docs/process/sprints/2026-08-08-MONITOR-QUE-VENCE-01-*.md"
        )


def test_a_entrada_do_controle_nao_rouba_de_um_microfone_de_verdade() -> None:
    """O contrapeso: o objetivo original do arquivo continua cumprido.

    Sem esta asserção, "curar" o defeito viraria pôr o controle no topo — e a
    queixa que criou este drop-in ("o controle fica mexendo no microfone") voltaria
    inteira, agora com o produto tendo escolhido isso de propósito.
    """
    for valor in _prioridades_da_entrada():
        assert valor < CAPTURA_REAL_MEDIDA, (
            f"a entrada do controle está em {valor}, acima da captura real medida "
            f"({CAPTURA_REAL_MEDIDA}). O controle voltaria a virar microfone "
            "padrão sozinho — que é exatamente a queixa que criou este arquivo."
        )


def test_a_placa_e_o_monitor_continuam_rebaixados() -> None:
    """Nem a placa nem o monitor são microfone; nenhum dos dois deve ser padrão."""
    texto = DROPIN.read_text(encoding="utf-8")
    linhas = [ln for ln in texto.splitlines() if not ln.lstrip().startswith("#")]
    corpo = "\n".join(linhas)
    assert "alsa_card" in corpo, "sumiu a regra que cobre a placa do controle"
    assert "[Mm]onitor" in corpo, (
        "sumiu a regra do monitor. Ela não dispara hoje (o `.monitor` não é nó do "
        "monitor de ALSA), mas fica porque a intenção está certa e custa zero — e "
        "passa a valer sozinha se a camada estender o alcance."
    )


def test_o_porque_esta_no_arquivo() -> None:
    """Os números medidos moram junto da regra que eles justificam.

    Sem eles, `1500` é número mágico — e número mágico é o primeiro a ser
    "simplificado" de volta para 50 por quem leu só o título do arquivo.
    """
    texto = DROPIN.read_text(encoding="utf-8")
    assert "MONITOR-QUE-VENCE-01" in texto, "o registro da medição saiu do arquivo"
    for numero in (str(MONITOR_MAIS_ALTO_MEDIDO), str(CAPTURA_REAL_MEDIDA)):
        assert numero in texto, (
            f"o valor medido {numero} sumiu do arquivo — sem ele a faixa vira "
            "opinião, e a próxima pessoa não sabe contra o que ela foi calibrada."
        )
