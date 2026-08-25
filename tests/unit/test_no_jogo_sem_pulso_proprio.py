"""NO-JOGO-SEM-FALSO-VERDE-01/T8 — o painel não pode ganhar pulso próprio.

**O defeito era do PORTÃO, não do produto.** A docstring de `PainelNoJogo`
promete, em letra grande, que este widget não acrescenta nenhuma ocorrência de
``GLib.timeout_add`` *"de propósito"*, e diz de quem é a régua: *"O gate de
timers da `status_actions` conta as ocorrências no fonte"*. Só que aquele gate
(`test_status_cards.py`, o `test_o_numero_de_timers_nao_sobe`) lê **dois**
arquivos — `status_actions.py` e `controller_card.py` — e `painel_no_jogo.py`
não é nenhum dos dois. Um `GLib.timeout_add(500, lambda: True)` plantado no
painel passava por ele sem um vermelho.

**Por que um arquivo novo e não uma linha a mais no gate de lá.** Não é o mesmo
fato: aquele gate trava o número de timers do card e da mixin, e a conta dele é
uma decisão relida a cada vez que sobe. Aqui o número é **zero**, e zero é
contrato de desenho deste widget, não um teto negociado. Nesta leva
`test_status_cards.py` também não é desta bancada.

**Por que zero, e não "um one-shot tudo bem".** O painel é montado **por
controle**: um periódico aqui roda quatro vezes com a mesa cheia, e foi um
``idle_add`` devolvendo ``True`` que rendeu os 104% de um núcleo da v3.8.1
nesta casa. Quem repinta é o tique lento de 2 Hz que a mixin já tinha, e só com
esta aba à vista — a carona é a cura, e o pulso próprio é a recaída.

É também a **Mordida 3** da MESA-CHEIA-07 §3 (*"pintar a cor num
`GLib.timeout_add` próprio em vez de pegar carona no tique lento"*), que a T5
desta sprint herda: com esta régua no lugar, a cor por jogador não tem como
entrar por um pulso novo sem alguém ver vermelho.
"""

from __future__ import annotations

import re
from pathlib import Path

from hefesto_dualsense4unix.app.widgets import painel_no_jogo as pnj_mod

#: As três formas de agendar do GLib que a casa já pagou para conhecer. As duas
#: primeiras são o laço clássico; a `idle_add` é a que custou os 104% de CPU.
_AGENDADORES = (
    r"GLib\.timeout_add\(",
    r"GLib\.timeout_add_seconds\(",
    r"GLib\.idle_add\(",
)


def _fonte_do_painel() -> str:
    return Path(pnj_mod.__file__).read_text(encoding="utf-8")


def test_o_painel_no_jogo_nao_agenda_nada() -> None:
    """Zero timers no fonte do widget — o que a docstring dele promete.

    Arranque para ver reprovar: plantar ``GLib.timeout_add(500, lambda: True)``
    em ``PainelNoJogo.__init__``. Antes desta régua isso passava por todos os
    portões desta casa, inclusive pelo gate de timers que a própria docstring
    do widget cita como sua guarda.
    """
    fonte = _fonte_do_painel()

    encontrados = {
        padrao: len(re.findall(padrao, fonte)) for padrao in _AGENDADORES
    }

    assert encontrados == dict.fromkeys(_AGENDADORES, 0), (
        "O painel da aba No jogo ganhou pulso próprio "
        f"({encontrados}). Ele é montado POR CONTROLE: com a mesa cheia isso "
        "são quatro laços. Quem repinta é o tique de 2 Hz da "
        "`_sync_paineis_no_jogo`, e só com esta aba à vista."
    )


def test_a_regua_enxerga_o_arquivo_certo() -> None:
    """A contraprova da régua de cima, e ela não é cerimônia.

    Uma régua que lesse o arquivo errado — ou um arquivo vazio — passaria no
    teste anterior com um `timeout_add` plantado, que é exatamente o defeito
    que esta bancada existe para curar. Duas âncoras: o arquivo é o do painel,
    e o texto que ele lê é o fonte de verdade.
    """
    caminho = Path(pnj_mod.__file__)
    fonte = _fonte_do_painel()

    assert caminho.name == "painel_no_jogo.py"
    assert "class PainelNoJogo" in fonte
    # A promessa que esta régua passa a cobrir, no fonte do próprio widget.
    assert "GLib.timeout_add" in fonte, (
        "A docstring do painel cita `GLib.timeout_add` para dizer que não usa "
        "nenhum. Se nem a menção sobrou, a régua de cima passou a medir a "
        "ausência de um texto que ninguém escreveu."
    )
