"""A vigia não reinicia o rádio por causa de UM aparelho insistindo.

VIGIA-QUE-DERRUBA-01 (08/08/2026). MEDIDO na máquina dela:

    00:54:26  estado doente suspeito (9 recusas/10min) mas há 3 device(s)
              conectado(s) — restart adiado
    00:56:26  estado doente confirmado (9 recusas/10min, 0 conectados) —
              reiniciando bluetooth.service

**As nove recusas eram de um aparelho só** — o 8BitDo, insistindo depois que o
crash do `bluetoothd` às 00:27:35 levou os quatro bonds embora. A vigia contava
EVENTOS; o que decide é quantos APARELHOS DISTINTOS.

E a "cura" não tinha relação com o sintoma: **reiniciar o serviço não cria bond
nenhum**. Só derrubou quem estava de pé — e matou junto o `hefesto-bt-agent`,
que é justamente quem confirmaria o repareamento. O laço:

    aparelho sem bond insiste  →  BlueZ recusa (unknown device)
            ↑                              ↓
      mais recusas              a vigia conta ≥8 e reinicia
            ↑                              ↓
    alguns não voltam    ←    restart derruba TODOS + mata o agente

A DOENÇA QUE A VIGIA EXISTE PARA PEGAR CONTINUA COBERTA
=======================================================
A de 21/07 é o daemon renascido recusando devices PRESENTES na lista, em loop.
Ela atinge **vários aparelhos ao mesmo tempo**, porque o defeito é do daemon e
não de um aparelho — então o limiar de aparelhos distintos separa as duas
leituras sem inventar instrumento novo e sem cegar a vigia.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "bt_health_watchdog.sh"


def _texto() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_existe_limiar_de_aparelhos_distintos() -> None:
    """A vigia tem um limiar de APARELHOS, além do de eventos.

    ARRANQUE A CURA (tire o `LIMIAR_APARELHOS`) e este teste REPROVA. Sem ele a
    vigia volta a contar eventos, e um aparelho martelando derruba a mesa dela.
    """
    texto = _texto()
    achado = re.search(r"^LIMIAR_APARELHOS=(\d+)$", texto, re.M)
    assert achado, (
        "sumiu o `LIMIAR_APARELHOS` de `scripts/bt_health_watchdog.sh`. Sem ele a "
        "vigia conta EVENTOS, e um aparelho sem bond insistindo nove vezes faz "
        "ela reiniciar o Bluetooth — que foi como ela perdeu os quatro controles "
        "em 08/08. Ver "
        "docs/process/sprints/2026-08-08-BLUETOOTHD-MORTO-POR-NOS-01-*.md"
    )
    assert int(achado.group(1)) >= 2, (
        "o `LIMIAR_APARELHOS` precisa ser pelo menos 2: com 1 ele não distingue "
        "nada, e a vigia volta ao comportamento que custou os controles dela."
    )


def test_o_limiar_de_aparelhos_e_consultado_antes_do_restart() -> None:
    """O limiar não é decorativo: ele guarda o caminho do restart.

    Uma constante declarada e nunca lida é pior que nenhuma — dá a impressão de
    cobertura. Este teste exige que ela apareça na condição, e ANTES de o
    `systemctl restart` ser alcançado.
    """
    texto = _texto()
    assert "${APARELHOS_RECUSADOS}" in texto, (
        "o `APARELHOS_RECUSADOS` não é usado — a contagem de aparelhos distintos "
        "existe mas não decide nada."
    )

    guarda = texto.find("APARELHOS_RECUSADOS}\" -lt \"${LIMIAR_APARELHOS}")
    restart = texto.find("systemctl restart bluetooth.service")
    assert guarda != -1, (
        "a comparação `APARELHOS_RECUSADOS < LIMIAR_APARELHOS` sumiu do caminho "
        "de decisão."
    )
    assert guarda < restart, (
        "a guarda de aparelhos distintos precisa vir ANTES do `systemctl "
        "restart` — depois dele não guarda nada."
    )


def test_um_aparelho_so_vira_aviso_e_nao_restart() -> None:
    """O caminho de um aparelho só termina em AVISO, não em restart.

    O texto do aviso importa: ele é o que alguém vai ler no journal quando o
    controle não voltar, e precisa dizer que o restart NÃO resolveria — senão a
    próxima pessoa "conserta" a vigia baixando o limiar.
    """
    texto = _texto()
    assert re.search(r'log "AVISO: \$\{RECUSAS\}', texto), (
        "sumiu o aviso do caso de um aparelho só. Sem ele o sintoma fica "
        "invisível: nem restart, nem registro."
    )
    aviso = re.search(r'log "AVISO: [^"]+"', texto)
    assert aviso and "restart NÃO resolveria" in aviso.group(0), (
        "o aviso não diz que o restart não resolveria. Essa frase é o que impede "
        "alguém de 'curar' a vigia baixando o limiar de volta."
    )


def test_a_licao_de_2107_continua_coberta() -> None:
    """A doença original — daemon recusando device PRESENTE — não foi cegada.

    O contrapeso desta sprint. Sem esta asserção, alguém poderia "curar" o
    excesso de restart simplesmente desligando a vigia, e o defeito de 21/07
    (o 8BitDo passou 47 min sendo recusado) voltaria sem ninguém notar.
    """
    texto = _texto()
    assert "systemctl restart bluetooth.service" in texto, (
        "o restart sumiu inteiro — a vigia deixou de curar a doença de 21/07, "
        "que é o motivo de ela existir."
    )
    assert re.search(r"^LIMIAR_RECUSAS=\d+$", texto, re.M), (
        "sumiu o `LIMIAR_RECUSAS`: o limiar de eventos continua sendo a primeira "
        "peneira, e o de aparelhos é a segunda."
    )
    assert "RATE_LIMIT_S=" in texto, (
        "sumiu o rate-limit de restart, que impede a vigia de reiniciar em laço."
    )
    assert "restart adiado (nunca derrubo sessão viva)" in texto, (
        "sumiu a trava que impede o restart com device conectado — a regra mais "
        "antiga desta vigia."
    )


def test_o_porque_esta_escrito_no_script() -> None:
    """Quem for mexer no limiar encontra o custo medido de mexer errado."""
    texto = _texto()
    assert "VIGIA-QUE-DERRUBA-01" in texto, (
        "o registro da VIGIA-QUE-DERRUBA-01 saiu do script. Sem ele o "
        "`LIMIAR_APARELHOS` vira um número mágico, e números mágicos são os "
        "primeiros a serem 'simplificados'."
    )
    assert "não cria bond" in texto, (
        "sumiu a frase que explica por que o restart não resolve este sintoma — "
        "é a informação que impede a cura errada de voltar."
    )
