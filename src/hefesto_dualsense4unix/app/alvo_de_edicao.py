"""O DONO ÚNICO do alvo de edição — e a diferença entre "Todos" e "não sei".

**O defeito de forma (P3, medido em 23/08/2026).** O alvo de edição por
controle morava num atributo com *default de classe*
(``_edit_target_uniq: str | None = None``, em ``actions/status_actions.py``) e
era lido por nove pontos da janela via ``getattr(self, "_edit_target_uniq",
None)``. O ``None`` do ``getattr`` nunca entrava em ação: o atributo da classe
já respondia ``None``, e ``None`` significa **"edite tudo, globalmente"**.

Resultado medido: com a mesa vazia (os dois controles desligados), um pixel de
arrasto no brilho da Lightbar **apagava os overrides por controle do perfil
inteiro** e a tela dizia *"Cor enviada ao controle"* — no singular, com zero
controles conectados. Nenhum toast, nenhuma recusa.

**A causa é que ``None`` carregava duas coisas diferentes:**

* *"ela clicou em Todos"* — escolha legítima e deliberada, que a R-16 protege;
* *"eu não sei quem é o alvo"* — ausência de informação.

Este módulo separa as duas em estados distintos, e é o único lugar que escreve
o alvo. A regra da casa aplicada literalmente: **ausência de informação se
declara, nunca vira ação padrão silenciosa** — a mesma decisão que a
``alvo_fora_da_mesa`` já tinha tomado para os toasts.

**A ponte com o atributo antigo.** Os nove leitores continuam lendo
``_edit_target_uniq``; migrá-los é de outra leva (quatro das abas estão com
outras frentes agora). Enquanto isso:

* quem DEFINE o alvo passa por aqui, e aqui o atributo antigo é espelhado —
  os leitores não migrados enxergam exatamente o que enxergavam antes;
* quem ESQUECE o alvo (mesa vazia, daemon desligado) passa por aqui, e aqui o
  atributo antigo é **apagado da instância** — os não migrados voltam ao
  ``None`` de sempre (comportamento idêntico ao de hoje, sem colisão), mas o
  estado canônico já diz ``DESCONHECIDO`` para quem souber perguntar;
* ``alvo_de_edicao()`` reconstrói o estado a partir do atributo antigo quando
  ele existe na instância (dublês de teste, código não migrado). É por isso
  que o default de classe teve de sair: **o atributo EXISTIR é o que separa
  "escolheu Todos" de "ninguém escolheu nada"**.

Sem GTK e sem IPC de propósito: é estado puro, e o teste dele custa
milissegundos.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from enum import Enum
from typing import Any

#: Onde o estado canônico mora na instância da janela.
ATRIBUTO_CANONICO = "_alvo_de_edicao"
#: Os atributos legados que os nove leitores ainda consultam.
ATRIBUTO_LEGADO_UNIQ = "_edit_target_uniq"
ATRIBUTO_LEGADO_LABEL = "_edit_target_label"

# Os motivos de não saber. São diferentes na tela porque são diferentes no
# mundo — a mesma razão pela qual o módulo do vocabulário do "guardado" guarda
# três motivos em vez de um.
MOTIVO_SEM_ESTADO = "a janela ainda não leu o estado do Hefesto"
MOTIVO_MESA_VAZIA = "não há controle na mesa"
MOTIVO_DAEMON_DESLIGADO = "o Hefesto está desligado"


class EstadoDoAlvo(Enum):
    """Os três estados que o ``None`` de antes confundia em um."""

    #: Ninguém escolheu nada e a janela não sabe — NÃO é ordem de escrever.
    DESCONHECIDO = "desconhecido"
    #: Ela escolheu "Todos" (ou um alvo sem endereço fixo): escrita global.
    TODOS = "todos"
    #: Ela escolheu um controle com endereço estável: escrita no override.
    CONTROLE = "controle"


@dataclass(frozen=True)
class AlvoDeEdicao:
    """O alvo de edição, com o estado explícito ao lado do endereço."""

    estado: EstadoDoAlvo
    uniq: str | None = None
    label: str | None = None
    motivo: str | None = None

    @property
    def desconhecido(self) -> bool:
        return self.estado is EstadoDoAlvo.DESCONHECIDO

    @property
    def global_(self) -> bool:
        """Escrita global DELIBERADA — "Todos", nunca o fallback do desconhecido."""
        return self.estado is EstadoDoAlvo.TODOS

    @property
    def por_controle(self) -> bool:
        return self.estado is EstadoDoAlvo.CONTROLE

    def pode_escrever(self) -> bool:
        """Só ``DESCONHECIDO`` recusa; os outros dois escrevem como sempre."""
        return not self.desconhecido

    def recusa(self) -> str | None:
        """A frase da recusa; ``None`` quando há alvo e a escrita segue.

        Diz o que NÃO aconteceu e por quê — nem promete o que não fez, nem
        manda a pessoa fazer o impossível (com a mesa vazia não há controle
        para escolher no cabeçalho).
        """
        if not self.desconhecido:
            return None
        return (
            "Não dá para saber em qual controle isto entraria — "
            f"{self.motivo or MOTIVO_SEM_ESTADO}. Nada foi alterado."
        )


ALVO_DESCONHECIDO = AlvoDeEdicao(EstadoDoAlvo.DESCONHECIDO, motivo=MOTIVO_SEM_ESTADO)


def alvo_de_edicao(host: Any) -> AlvoDeEdicao:
    """O alvo de edição da janela ``host`` — nunca ``None``, nunca um chute.

    Sem estado nenhum a resposta é ``DESCONHECIDO``, e é essa a diferença que
    o atributo com default de classe apagava: ele respondia "global".
    """
    atual = getattr(host, ATRIBUTO_CANONICO, None)
    if isinstance(atual, AlvoDeEdicao):
        return atual
    # Ponte para quem ainda escreve o atributo antigo direto. A EXISTÊNCIA do
    # atributo é o sinal: presente = alguém decidiu; ausente = ninguém decidiu.
    if not hasattr(host, ATRIBUTO_LEGADO_UNIQ):
        return ALVO_DESCONHECIDO
    uniq = getattr(host, ATRIBUTO_LEGADO_UNIQ, None)
    label = getattr(host, ATRIBUTO_LEGADO_LABEL, None)
    if isinstance(uniq, str) and uniq:
        return AlvoDeEdicao(EstadoDoAlvo.CONTROLE, uniq=uniq, label=label)
    return AlvoDeEdicao(EstadoDoAlvo.TODOS, uniq=None, label=label)


def definir_alvo(host: Any, uniq: str | None, label: str | None) -> AlvoDeEdicao:
    """Grava o alvo escolhido: ``uniq`` preenchido = controle; vazio = "Todos".

    Espelha os atributos legados para que os nove leitores não migrados vejam
    exatamente o que veriam antes.
    """
    if isinstance(uniq, str) and uniq:
        alvo = AlvoDeEdicao(EstadoDoAlvo.CONTROLE, uniq=uniq, label=label)
    else:
        alvo = AlvoDeEdicao(EstadoDoAlvo.TODOS, uniq=None, label=label)
    _gravar(host, alvo)
    return alvo


def esquecer_alvo(host: Any, motivo: str) -> AlvoDeEdicao:
    """Declara que a janela NÃO sabe qual é o alvo, e por quê.

    Apaga os atributos legados da instância: os leitores não migrados voltam
    ao ``None`` de hoje (mesmo comportamento, sem colisão com outras frentes),
    e quem já pergunta a este módulo recebe a verdade.
    """
    alvo = AlvoDeEdicao(EstadoDoAlvo.DESCONHECIDO, motivo=motivo)
    _gravar(host, alvo)
    return alvo


def _gravar(host: Any, alvo: AlvoDeEdicao) -> None:
    setattr(host, ATRIBUTO_CANONICO, alvo)
    if alvo.desconhecido:
        for nome in (ATRIBUTO_LEGADO_UNIQ, ATRIBUTO_LEGADO_LABEL):
            with contextlib.suppress(AttributeError):
                delattr(host, nome)
        return
    setattr(host, ATRIBUTO_LEGADO_UNIQ, alvo.uniq)
    setattr(host, ATRIBUTO_LEGADO_LABEL, alvo.label)
