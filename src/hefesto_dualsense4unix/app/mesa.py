"""O dono único de "quem está na mesa" — na JANELA, para as onze abas.

ONDA0-Z5/T5. **O defeito de forma (F6/F3), medido em 23/08/2026**: a única
função canônica que já existia para "quantos controles" (`ContagemDeControles`
e `texto_de_contagem`, nascidas na CONTAGEM-E-COOP-01 de 29/07) morava
*dentro do mixin da aba Status* (`app/actions/status_actions.py`). Nove abas
precisam da resposta; só uma é dona do arquivo. É a mesma doença que a F3 já
tinha causado noutro fato — e essa já custou perda de dado dela em 23/08.

Este módulo não importa GTK nem IPC — é estado puro, migrado sem mudar
comportamento (mesmo corpo, mesmos testes). O molde é
`app/alvo_de_edicao.py` (23/08): módulo novo, dono único, os leitores antigos
continuam funcionando por espelho enquanto migram — aqui o espelho é literal,
``status_actions.py`` reexporta os três nomes deste módulo.

**O que este módulo NÃO faz** (fora do escopo de T5, ver ONDA0-Z5 §6):
não decide o que a tela FAZ com a contagem — isso é `_render_online`/
`_render_slow_state` (T6) e cada aba que migrar (Ondas 1-11). Ele só responde
"quantos, e quem é o primário", a partir do `state` que `daemon.state_full`
publica.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.utils.i18n import _


def controles_conectados(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Controles conectados (FEAT-DSX-MULTI-CONTROLLER-01).

    Vem de `state["controllers"]` (bloco do `daemon.state_full`); o primário
    é o primeiro da lista (ordem de inserção). Lista vazia se o daemon não
    expõe o bloco (versão antiga) — os renderers caem no caminho single.
    """
    controllers = state.get("controllers")
    if not isinstance(controllers, list):
        return []
    return [c for c in controllers if isinstance(c, dict) and c.get("connected")]


@dataclass(frozen=True)
class ContagemDeControles:
    """A contagem de controles da janela — os DOIS espaços, num só lugar.

    CONTAGEM-E-COOP-01 (29/07). A mesma tela dizia números diferentes para
    "quantos controles": o cabeçalho e a linha "Conectado (N controles)"
    contavam só os DualSense adotados, enquanto a fita de chips do topo e a
    faixa "Número deste controle" contavam adotados + externos. Com dois
    DualSense e dois externos vivos, o cabeçalho dizia "2 controles" ao lado
    de quatro chips e de uma faixa oferecendo os números 1 a 4.

    A resposta certa NÃO é somar tudo em um número só: os dois espaços são
    reais e cada um tem razão histórica registrada —

    - ``adotados`` — DualSense que o Hefesto governa (tem vpad, card, bateria,
      alvo de edição). É a base da numeração dos externos (``_dualsense_count``
      → `external_controllers.slot_of`) e o denominador dos cards
      (`_status_card_keys_for`, filtrado por ``connected``);
    - ``externos`` — Nintendo Pro, 8BitDo… que o daemon NUMERA mas não adota.
      Read-only POR DECISÃO DE PRODUTO (EXT-COUNT-01, 25/07: "numerar e acender
      o LED certo != adotar o controle"), então eles não têm card nem bateria —
      mas dividem o MESMO espaço de numeração dos adotados (R-24/NUM-01), e é
      por isso que a faixa de números tem de oferecer 1..``na_mesa``.

    Inflar ``adotados`` com os externos regrediria as duas coisas: os cards
    ganhariam entradas sem controle por trás e o rótulo dos externos deslizaria
    (o ponto cego do incidente de 14:42 citado em `slot_of`).

    A cura, então, é DERIVAR tudo daqui e NOMEAR cada número na tela — ver
    :func:`texto_de_contagem`.
    """

    adotados: int
    externos: int

    @property
    def na_mesa(self) -> int:
        """Quantos controles estão na mesa — o espaço de numeração (R-24/NUM-01)."""
        return self.adotados + self.externos


def contagem_de_controles(state: dict[str, Any], externos: int) -> ContagemDeControles:
    """A contagem, a partir do `state` de `daemon.state_full` e do inventário
    de externos (`_externals`, que a janela já mantém — este módulo não sabe
    ler externos sozinho, é a única dependência que o mixin ainda empresta)."""
    return ContagemDeControles(adotados=len(controles_conectados(state)), externos=externos)


def texto_de_contagem(contagem: ContagemDeControles) -> str:
    """Frase NOMEADA da contagem, ou ``""`` quando não há plural a explicar.

    CONTAGEM-E-COOP-01: quem lê a tela precisa saber de QUAL número se trata.
    Três regimes:

    - ``na_mesa <= 1``: string vazia — não há contagem a exibir e quem chama
      segue pelo caminho single de sempre ("Conectado Via USB");
    - sem externos: ``"3 controles"`` — o texto de sempre, e aqui ele não
      mente: ``na_mesa == adotados``, nenhuma ambiguidade a desfazer (mantido
      idêntico também para não crescer a largura do cabeçalho no caso comum,
      lição dos 12px de folga da CI de 29/07);
    - com externos: ``"2 do Hefesto + 2 externos"`` — o número do cabeçalho
      passa a explicar por que a fita ao lado tem quatro chips.
    """
    adotados = contagem.adotados
    externos = contagem.externos
    if contagem.na_mesa <= 1:
        return ""
    if externos == 0:
        return _("{n} controles").format(n=adotados)
    parte_ext = (
        _("1 externo") if externos == 1 else _("{n} externos").format(n=externos)
    )
    if adotados == 0:
        # Defensivo: `state["connected"]` é do DualSense primário, então este
        # regime não deveria alcançar a tela — mas "0 do Hefesto" seria pior.
        return _("{ext} (nenhum do Hefesto)").format(ext=parte_ext)
    return _("{n} do Hefesto + {ext}").format(n=adotados, ext=parte_ext)


__all__ = [
    "ContagemDeControles",
    "contagem_de_controles",
    "controles_conectados",
    "texto_de_contagem",
]
