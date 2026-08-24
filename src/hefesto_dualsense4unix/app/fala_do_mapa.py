"""fala_do_mapa.py — onde a tela declara de que célula do mapa está falando.

Executa Z6-03 (docs/process/sprints/2026-08-24-ONDA0-Z6-COMUNHAO-COM-O-SPECS-01…
.md), a Peça 2 do contrato desenhado na
docs/process/sprints/2026-08-24-PAREAMENTO-01-a-medicao-nova-tem-de-chegar-sozinha-na-tela.md.

Escrito à mão — este módulo NÃO é gerado. É o único lugar onde uma frase de
tela declara "estou falando da chave X, do lado Y, e afirmo Z" — o endereço
que faltava entre o mapa de canais e a interface (§1 da Z6).

O VOCABULÁRIO DE `afirma`, E O PORQUÊ DE `AFIRMA_NAO_ACIONA` EXIGIR CAUSA
---------------------------------------------------------------------------
`aciona = não` sozinho não diz de quem é a culpa: as quatro colunas de causa
do mapa (`cabo_por_que_nao_aciona`/`radio_por_que_nao_aciona`) hoje valem
`nada-a-acionar`, `decisao-tomada`, `so-ela-decide` ou `divida`, e SÓ as duas
primeiras nomeiam causa fora do nosso código — o portão (Z6-04) checa isso
antes de aceitar `AFIRMA_NAO_ACIONA`, para nunca licenciar uma frase que
culpa o aparelho pelo que é nosso.

A REGRA QUE MORA NO TIPO, NÃO NUM DOCUMENTO
----------------------------------------------
"Ausência de medição se declara, nunca se preenche com zero, porque zero
pinta verde." `Fala.__post_init__` recusa `texto` numérico ou booleano
incondicionalmente, e recusa a combinação `pendente=` + texto que não seja a
sentinela `NAO_MEDIDO` (e vice-versa) — a régua está no construtor, não numa
convenção que alguém tem de lembrar de seguir.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final


class _NaoMedidoSentinela:
    """O tipo da sentinela `NAO_MEDIDO`. Nunca instancie um segundo — use a
    constante do módulo. `isinstance(x, str)` é `False` de propósito: quem
    tenta tratar `NAO_MEDIDO` como texto comum (`.strip()`, concatenar) quebra
    alto, em vez de produzir uma tela com "None" ou string vazia por engano.
    """

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover — só ajuda debug
        return "NAO_MEDIDO"


#: A sentinela. Não é `""`, não é `None`, não é `0` — as três formas que
#: pintariam verde ou sumiriam da tela em vez de declarar a ausência.
NAO_MEDIDO: Final = _NaoMedidoSentinela()

#: A frase única da casa, por lado — nunca escrita de novo por quem declara
#: uma `Fala` com `pendente=`. Ver Z6-11 (a fila) e P-02(a) da PAREAMENTO-01.
FRASE_NAO_MEDIDO: Final[dict[str, str]] = {
    "cabo": "Ainda não medimos isto no cabo.",
    "radio": "Ainda não medimos isto no rádio.",
}

# ── O vocabulário de `afirma` — minúsculo, mapeado 1:1 em coluna do mapa ──
AFIRMA_EXISTE: Final = "existe"
AFIRMA_NAO_EXISTE: Final = "nao-existe"
AFIRMA_ACIONA: Final = "aciona"
AFIRMA_PARCIAL: Final = "parcial"
AFIRMA_NAO_ACIONA: Final = "nao-aciona"
AFIRMA_NADA: Final = "nada"

AFIRMA_VALIDOS: Final[frozenset[str]] = frozenset(
    {
        AFIRMA_EXISTE,
        AFIRMA_NAO_EXISTE,
        AFIRMA_ACIONA,
        AFIRMA_PARCIAL,
        AFIRMA_NAO_ACIONA,
        AFIRMA_NADA,
    }
)

#: As duas únicas causas, entre as quatro do domínio de `*_por_que_nao_aciona`,
#: que nomeiam algo FORA do nosso código (Z6-05/P-07). `divida`,
#: `decisao-tomada` e `so-ela-decide` são nossas — com elas o único `afirma`
#: legal é `AFIRMA_NADA` com `porque=` explícito.
CAUSA_DE_FORA: Final[frozenset[str]] = frozenset({"nada-a-acionar", "o-aparelho-recusa"})

LADOS_VALIDOS: Final[frozenset[str]] = frozenset({"cabo", "radio"})


@dataclass(frozen=True)
class Pendencia:
    """O que falta para uma `Fala` deixar de ser `NAO_MEDIDO`.

    `pendente is not None` é o que `--fila` (Z6-11) varre por AST — a lista de
    compras da bancada, gerada pela própria interface.
    """

    aberta_em: str
    prazo_dias: int
    quem_fecha: str
    o_que_falta: str

    def __post_init__(self) -> None:
        for nome, valor in (
            ("aberta_em", self.aberta_em),
            ("quem_fecha", self.quem_fecha),
            ("o_que_falta", self.o_que_falta),
        ):
            if isinstance(valor, bool) or not isinstance(valor, str) or not valor.strip():
                raise TypeError(
                    f"Pendencia.{nome} tem de ser texto não vazio, não {valor!r} — "
                    "ausência de medição se declara em prosa, nunca em número ou "
                    "booleano."
                )
        # `bool` é subclasse de `int` em Python: sem o `isinstance(..., bool)`
        # primeiro, `prazo_dias=True` passaria como `1` silenciosamente.
        if isinstance(self.prazo_dias, bool) or not isinstance(self.prazo_dias, int):
            raise TypeError(
                f"Pendencia.prazo_dias tem de ser int, não {self.prazo_dias!r} "
                "(nunca booleano — bool é subclasse de int e passaria calado)."
            )
        if self.prazo_dias <= 0:
            raise ValueError(f"Pendencia.prazo_dias tem de ser positivo, não {self.prazo_dias!r}.")
        try:
            date.fromisoformat(self.aberta_em)
        except ValueError as exc:
            raise ValueError(
                f"Pendencia.aberta_em={self.aberta_em!r} não é data ISO (AAAA-MM-DD)."
            ) from exc


@dataclass(frozen=True)
class Fala:
    """Uma frase de tela declarando de que célula do mapa ela fala.

    `chave` é o `id` do mapa (`chave@controle` — nunca `chave` sozinha, que
    não é endereço). `lado` é `"cabo"` ou `"radio"`. `afirma` é um dos seis
    `AFIRMA_*`. `porque=` é obrigatório (não-vazio) quando `afirma=AFIRMA_NADA`
    — é o que impede a tela de ficar muda sem dizer por quê.
    """

    chave: str
    lado: str
    aba: str
    texto: str | _NaoMedidoSentinela
    afirma: str
    porque: str = ""
    pendente: Pendencia | None = None

    def __post_init__(self) -> None:
        if not self.chave.strip() or "@" not in self.chave:
            raise ValueError(
                f"Fala.chave={self.chave!r} não parece um `id` do mapa "
                "(esperado `chave@controle`)."
            )
        if self.lado not in LADOS_VALIDOS:
            raise ValueError(f"Fala.lado={self.lado!r} fora de {sorted(LADOS_VALIDOS)}.")
        if not self.aba.strip():
            raise ValueError("Fala.aba não pode ser vazia.")
        if self.afirma not in AFIRMA_VALIDOS:
            raise ValueError(f"Fala.afirma={self.afirma!r} fora de {sorted(AFIRMA_VALIDOS)}.")
        if self.afirma == AFIRMA_NADA and self.pendente is None and not self.porque.strip():
            raise ValueError(
                "Fala com afirma=AFIRMA_NADA exige porque= explícito (ou "
                "pendente= declarada, se o motivo é dívida de medição) — a "
                "tela não pode ficar muda sem dizer por quê."
            )

        # A regra que mora no tipo: nunca número, nunca booleano, porque zero
        # pinta verde e False some da tela como se não houvesse nada a dizer.
        if isinstance(self.texto, (bool, int, float)):
            raise TypeError(
                f"Fala.texto={self.texto!r} é número/booleano — proibido. Use "
                "NAO_MEDIDO enquanto não houver medição, nunca 0/False/0.0."
            )

        eh_nao_medido = self.texto is NAO_MEDIDO
        if eh_nao_medido and self.pendente is None:
            raise ValueError(
                "Fala com texto=NAO_MEDIDO precisa de pendente= declarada — a "
                "dívida tem de ficar visível na fila (--fila), nunca implícita."
            )
        if self.pendente is not None and not eh_nao_medido:
            raise ValueError(
                "Fala com pendente= declarada tem de usar texto=NAO_MEDIDO — "
                "não se mistura frase escrita com dívida aberta."
            )
        if not eh_nao_medido and (not isinstance(self.texto, str) or not self.texto.strip()):
            raise ValueError(
                "Fala.texto vazio não é permitido — nunca vazio: escreva a "
                "frase ou declare pendente= com texto=NAO_MEDIDO."
            )


def frase_de_exibicao(fala: Fala) -> str:
    """O que a tela mostra: a frase escrita, ou a frase única de `NAO_MEDIDO`."""
    if fala.texto is NAO_MEDIDO:
        return FRASE_NAO_MEDIDO[fala.lado]
    assert isinstance(fala.texto, str)
    return fala.texto


@dataclass(frozen=True)
class Numero:
    """Amarra uma constante Python MEDIDA a uma célula em prosa do mapa (Z6-08).

    O número medido tem um dono só: a constante Python é o valor de verdade,
    e o portão (Z6-04) confere que a célula `coluna` do mapa cita esse mesmo
    valor, no formato pt-BR (`260,4`), na chave `chave`. Trocar a constante
    sem atualizar a célula reprova, nomeando os dois endereços.
    """

    constante: str
    valor: float
    chave: str
    coluna: str

    def __post_init__(self) -> None:
        if isinstance(self.valor, bool) or not isinstance(self.valor, (int, float)):
            raise TypeError(f"Numero.valor tem de ser numérico, não {self.valor!r}.")
        if not self.constante.strip() or not self.chave.strip() or not self.coluna.strip():
            raise ValueError("Numero.constante/chave/coluna não podem ser vazios.")


def formata_pt_br(valor: float) -> str:
    """`260.4` → `"260,4"`. A MESMA forma que `_numero()` de
    `app/actions/config/secao_controles.py:431` produz (uma casa decimal,
    vírgula) — nunca redigitada aqui, para as duas nunca divergirem em como
    arredondam (Z6-08).
    """
    return f"{valor:.1f}".replace(".", ",")
