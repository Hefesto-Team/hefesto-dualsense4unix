"""O DONO ÚNICO do alvo de edição — e a diferença entre "Todos" e "não sei".

**O defeito de forma (P3, medido em 23/08/2026).** O alvo de edição por
controle morava num atributo com *default de classe*
(``_edit_target_uniq: str | None = None``, em ``actions/status_actions.py``) e
era lido por **sete pontos da janela, em seis arquivos**, via
``getattr(self, "_edit_target_uniq", None)`` — medido com
``grep -rn 'getattr(\\(self\\|host\\|janela\\|self\\._host\\), *"_edit_target_uniq"' src/``
(a régua declarada da sprint ONDA0-Z2, §2.2; o "nove" de versões anteriores
desta docstring e do briefing da leva **NÃO** era essa contagem — substituído
aqui e na linha de F3 do ``SPRINT_ORDER``). O ``None`` do ``getattr`` nunca
entrava em ação: o atributo da classe já respondia ``None``, e ``None``
significa **"edite tudo, globalmente"**.

Resultado medido: com a mesa vazia (os dois controles desligados), um pixel de
arrasto no brilho da Lightbar **apagava os overrides por controle do perfil
inteiro** e a tela dizia *"Cor enviada ao controle"* — no singular, com zero
controles conectados. Nenhum toast, nenhuma recusa.

**A causa é que ``None`` carregava duas coisas diferentes:**

* *"o usuário clicou em Todos"* — escolha legítima e deliberada, que a R-16 protege;
* *"eu não sei quem é o alvo"* — ausência de informação.

Este módulo separa as duas em estados distintos, e é o único lugar que escreve
o alvo. A regra da casa aplicada literalmente: **ausência de informação se
declara, nunca vira ação padrão silenciosa** — a mesma decisão que a
``alvo_fora_da_mesa`` já tinha tomado para os toasts.

**A ponte com o atributo antigo, e por que ela ainda existe.** Os sete
leitores migraram todos para ``alvo_de_edicao()``/``AlvoDeEdicao`` **nesta
mesma leva** (ONDA0-Z2, 24/08/2026 — a frase *"migrá-los é de outra leva"* de
versões anteriores desta docstring caducou: a leva foi esta). A ponte
continua existindo porque dublês de teste ainda escrevem o atributo antigo
direto (``janela._edit_target_uniq = uniq``, o molde de
``tests/unit/test_p3_alvo_sem_dono.py``), e o portão
``scripts/portao_alvo_tem_dono.py`` reprova a volta do atributo em código de
produção, não em teste:

* quem DEFINE o alvo passa por aqui, e aqui o atributo antigo é espelhado —
  os dublês que ainda o leem enxergam exatamente o que enxergavam antes;
* quem ESQUECE o alvo (mesa vazia, daemon desligado) passa por aqui, e aqui o
  atributo antigo é **apagado da instância** — os dublês voltam ao ``None`` de
  sempre (comportamento idêntico ao de hoje, sem colisão), mas o estado
  canônico já diz ``DESCONHECIDO`` para quem souber perguntar;
* ``alvo_de_edicao()`` reconstrói o estado a partir do atributo antigo quando
  ele existe na instância (dublês de teste). É por isso que o default de
  classe teve de sair: **o atributo EXISTIR é o que separa "escolheu Todos"
  de "ninguém escolheu nada"**.

**O contrato que este módulo entrega às onze abas (§5 da sprint ONDA0-Z2):**

1. Quem quer saber o alvo chama ``alvo_de_edicao(self)``. Nunca ``getattr``.
2. Três estados, três respostas: ``CONTROLE`` → escreve no override por MAC;
   ``TODOS`` → escreve global, como sempre; ``DESCONHECIDO`` → **não
   escreve**, e mostra ``alvo.recusa()``.
3. Aba para quem a pergunta não faz sentido chama
   ``ConfigActionsMixin.set_alvo_inativo(True, motivo)`` — motivo GUARDADO,
   nunca pintado no cabeçalho (decisão de 23/08/2026) — e escreve o
   motivo na própria docstring: foi a docstring que provou, nesta sprint, que
   aquela aba se desqualificou de propósito e não por esquecimento.
4. Aba que ganha widget de escolha novo declara em qual dos três ele cai.

Sem GTK e sem IPC de propósito: é estado puro, e o teste dele custa
milissegundos.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from enum import Enum
from typing import Any

ATRIBUTO_CANONICO = "_alvo_de_edicao"
ATRIBUTO_LEGADO_UNIQ = "_edit_target_uniq"
ATRIBUTO_LEGADO_LABEL = "_edit_target_label"

MOTIVO_SEM_ESTADO = "a janela ainda não leu o estado do Hefesto"


class EstadoDoAlvo(Enum):
    """Os três estados que o ``None`` de antes confundia em um."""

    DESCONHECIDO = "desconhecido"
    TODOS = "todos"
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


    def recusa(self) -> str | None:
        """A frase da recusa; ``None`` quando há alvo e a escrita segue."""
        if not self.desconhecido:
            return None
        return (
            "Não dá para saber em qual controle isto entraria — "
            f"{self.motivo or MOTIVO_SEM_ESTADO}. Nada foi alterado."
        )


ALVO_DESCONHECIDO = AlvoDeEdicao(EstadoDoAlvo.DESCONHECIDO, motivo=MOTIVO_SEM_ESTADO)


def alvo_de_edicao(host: Any) -> AlvoDeEdicao:
    """O alvo de edição da janela ``host`` — nunca ``None``, nunca um chute."""
    atual = getattr(host, ATRIBUTO_CANONICO, None)
    if isinstance(atual, AlvoDeEdicao):
        return atual
    if not hasattr(host, ATRIBUTO_LEGADO_UNIQ):
        return ALVO_DESCONHECIDO
    uniq = getattr(host, ATRIBUTO_LEGADO_UNIQ, None)
    label = getattr(host, ATRIBUTO_LEGADO_LABEL, None)
    if isinstance(uniq, str) and uniq:
        return AlvoDeEdicao(EstadoDoAlvo.CONTROLE, uniq=uniq, label=label)
    return AlvoDeEdicao(EstadoDoAlvo.TODOS, uniq=None, label=label)


def definir_alvo(host: Any, uniq: str | None, label: str | None) -> AlvoDeEdicao:
    """Grava o alvo escolhido: ``uniq`` preenchido = controle; vazio = "Todos"."""
    if isinstance(uniq, str) and uniq:
        alvo = AlvoDeEdicao(EstadoDoAlvo.CONTROLE, uniq=uniq, label=label)
    else:
        alvo = AlvoDeEdicao(EstadoDoAlvo.TODOS, uniq=None, label=label)
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
