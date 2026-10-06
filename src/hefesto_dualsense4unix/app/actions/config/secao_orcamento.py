"""Seção 3 da aba Configurações — o PERFIL de desempenho e a conta do rádio.

TERRITÓRIO DE CONFIG-05. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.

A SEÇÃO RESPONDE DUAS PERGUNTAS, E SÓ AGORA A SEGUNDA
------------------------------------------------------

1. *"o que eu quero que fique ligado?"* — o **perfil de desempenho**;
2. *"cabe o que eu quero fazer?"* — a **conta de fatias por adaptador**, que é
   a pergunta que decide o produto (*cabem quatro controles com todas as
   features no rádio, nesta máquina?*) e que a seção nunca soube fazer.

AS DECISÕES QUE ESTE ARQUIVO CARREGA
------------------------------------

**1. Um perfil, três escolhas — `D-PERFIL-DE-DESEMPENHO` (24/08/2026).** Os
cinco degraus viraram três, e não por gosto de redação: medido em
`core/rumble.py`, `_ORCAMENTO_COM_TETO` só casa com `economia`, e
`balanceado`, `max`, `auto` e o não-declarado devolvem `None`. Eram cinco
botões, quatro sem efeito nenhum, governando uma feature. **A chave de disco
NÃO muda** — o esquema continua `Literal["economia", "balanceado", "max",
"auto"] | None`, e :data:`PERFIL_POR_TETO` é a migração 1-para-1 que lê o que
já está gravado.

**2. O microfone fica FORA do perfil.** Ele é o único que **capta a sala**, e
um perfil de DESEMPENHO que o ligasse ou o calasse transformaria uma escolha
de bateria numa escolha de privacidade feita pelas costas. A decisão é dela
(`D-PERFIL-DE-DESEMPENHO`, 24/08/2026) e continua inteira.

**A RAZÃO CITADA CADUCOU — NASCE-LIGADO-MIC-01, 17/09/2026.** Aqui se lia que
*"o mapa de canais registra que ele nasce desligado por privacidade e banda"*.
Ele nasce LIGADO desde 17/09: a chegada do controle põe o microfone no ar
(`daemon/subsystems/hotkey.nascer_no_ar`), que é a `D-O-MIC-LIGADO-VALE-NO-RADIO`
(decisoes-de-produto.csv id 38) finalmente implementada. **A decisão de 24/08 não
depende disso** — ela é sobre o perfil não ser o dono do microfone, e isso vale
igual com o microfone nascendo ligado. A condição que ela mesma pôs, sobre o
preço que o `plano_de_radio` conta, foi: *"LIGADO SEMPRE… COM A TELA DIZENDO O PREÇO"*.

**3. A tabela tem UMA linha com ponto de aplicação, e diz as outras quatro.**
:data:`LINHAS_DO_TETO` é o dono único da lista, e :func:`alcance_de_hoje`
DERIVA a frase dela em vez de repeti-la. Antes eram duas coisas — uma frase
digitada ao lado de uma tabela — e elas podiam divergir sem ninguém notar.

**4. Esta seção NÃO grava.** O dono da escolha é o `machine.declare`, e o
gesto de gravar é o "Aplicar" do rodapé. O clique aqui só acumula em
`host._maquina_pendente`. A ÚNICA conversa com o daemon é a LEITURA de
`daemon.state_full`, sem a qual a conta não sabe quem está no rádio; o portão
`test_o_clique_nao_grava_nada` nomeia essa leitura e reprova qualquer outra.

**5. O número de percentual não é escrito aqui.** Ele vem de
`core.rumble.teto_do_orcamento`, que por sua vez o deriva de
`RUMBLE_POLICY_MULT` — o dono único do degrau. Escrever "30%" à mão nesta tela
é o HARM-19 de novo: a faixa valeu 2.0 no schema, 1.0 no handler e 200% no
deslizador ao mesmo tempo, e quem pagou foi ela.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.core.rumble import SEM_TETO, teto_do_orcamento
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TITULO = "Desempenho"

DICA: str | None = (
    "O que fica ligado em todos os controles, e quanto do rádio isso ocupa. As "
    "abas continuam mandando no que fazem — nenhum ajuste seu é apagado."
)

def _lista(itens: list[str]) -> str:
    """``["a", "b", "c"]`` → ``"a, b e c"``."""
    if len(itens) <= 1:
        return "".join(itens)
    return f"{', '.join(itens[:-1])} e {itens[-1]}"


PERFIL_TUDO_LIGADO = "tudo_ligado"
PERFIL_BATERIA_LONGA = "bateria_longa"
PERFIL_EU_ESCOLHO = "eu_escolho"

PERFIS: tuple[str, ...] = (
    PERFIL_TUDO_LIGADO,
    PERFIL_BATERIA_LONGA,
    PERFIL_EU_ESCOLHO,
)

#: Global de Bateria da Sistema leem daqui.
ROTULOS_DOS_PERFIS: dict[str, str] = {
    PERFIL_TUDO_LIGADO: "Perfil Máximo",
    PERFIL_BATERIA_LONGA: "Perfil Econômico",
    PERFIL_EU_ESCOLHO: "Personalizado",
}

TETO_POR_PERFIL: dict[str, str | None] = {
    PERFIL_TUDO_LIGADO: "balanceado",
    PERFIL_BATERIA_LONGA: "economia",
    PERFIL_EU_ESCOLHO: None,
}

PERFIL_POR_TETO: dict[str, str] = {
    "economia": PERFIL_BATERIA_LONGA,
    "balanceado": PERFIL_TUDO_LIGADO,
    "max": PERFIL_TUDO_LIGADO,
    "auto": PERFIL_TUDO_LIGADO,
}


@dataclass(frozen=True)
class LinhaDoTeto:
    """Uma coisa que o perfil deveria alcançar, e se ela tem por onde."""

    nome: str
    vem_de: str
    ponto_de_aplicacao: str | None = None

    @property
    def tem_ponto(self) -> bool:
        return bool(self.ponto_de_aplicacao)


LINHAS_DO_TETO: tuple[LinhaDoTeto, ...] = (
    LinhaDoTeto(
        "Vibração",
        "Rumble",
        "hefesto_dualsense4unix.core.rumble:_effective_mult",
    ),
    LinhaDoTeto(
        "Gatilhos",
        "Gatilhos",
        "hefesto_dualsense4unix.profiles.manager:_perfil_na_economia",
    ),
    LinhaDoTeto(
        "Barra de luz",
        "Lightbar",
        "hefesto_dualsense4unix.profiles.manager:_perfil_na_economia",
    ),
    LinhaDoTeto("Microfone por BT", "Os controles"),
    LinhaDoTeto("Giroscópio", "Perfis"),
)

#: que a tabela mostra, e o dia em que a barra de luz ganhar esse ponto ela
#: gastando menos»* — a luz fica mais fraca e não apaga. <!-- noqa-acento: citação literal -->
def _dica_da_bateria_longa() -> str:
    """O que o perfil de bateria faz HOJE, e o que fica como está."""
    chave = TETO_POR_PERFIL[PERFIL_BATERIA_LONGA]
    teto = teto_do_orcamento(chave) if isinstance(chave, str) else None
    forca = f"{round(teto * 100)}% da força" if teto is not None else SEM_TETO
    frase = f"Vibração com {forca}"
    mais_fracos = [
        linha.nome.lower()
        for linha in LINHAS_DO_TETO
        if linha.tem_ponto and linha.nome != "Vibração"
    ]
    if mais_fracos:
        frase += f"; {_lista(mais_fracos)} mais fracos, sem apagar"
    pendentes = [linha.nome for linha in LINHAS_DO_TETO if not linha.tem_ponto]
    if not pendentes:
        return f"{frase}."
    return f"{frase}. {_lista(pendentes)} continuam como estão."


DICAS: dict[str, str] = {
    PERFIL_TUDO_LIGADO: (
        "Gatilho adaptativo, vibração no que o jogo pedir, barra de luz, "
        "giroscópio e touchpad."
    ),
    PERFIL_BATERIA_LONGA: _dica_da_bateria_longa(),
    # 05/09 já tinha trocado a mesma ideia por "o teto geral" em `aba_sistema`.
    PERFIL_EU_ESCOLHO: (
        "Nenhum teto geral: os ajustes de cada aba mandam, um por um."
    ),
}

DICAS_DO_CARTAO: dict[str, str] = {
    **DICAS,
    PERFIL_EU_ESCOLHO: "Nenhum teto: os ajustes de cada aba mandam neste controle.",
}

ECONOMIA_POR_PERFIL: dict[str, bool | None] = {
    PERFIL_TUDO_LIGADO: None,
    PERFIL_BATERIA_LONGA: True,
    PERFIL_EU_ESCOLHO: False,
}


def perfil_do_controle(teto_da_mesa: str | None, escolha: bool | None) -> str:
    """O botão aceso no cartão de um controle: a mesa, e depois o controle."""
    from hefesto_dualsense4unix.profiles.schema import economia_vale, mesa_em_economia

    if economia_vale(escolha, mesa_em_economia(teto_da_mesa)):
        return PERFIL_BATERIA_LONGA
    return PERFIL_EU_ESCOLHO if escolha is False else PERFIL_TUDO_LIGADO


def declaracao_do_perfil(uniq: str, perfil: str) -> dict[str, Any]:
    """O corpo do `machine.declare` do clique num perfil do cartão.

    A chave do controle e a validação são as do dono da economia
    (`schema.declaracao_da_economia`); aqui só se troca o valor pelo do perfil.
    `KeyError` num perfil que não existe, e `ValueError` num `uniq` sem chave.
    """
    from hefesto_dualsense4unix.profiles.schema import declaracao_da_economia

    valor = ECONOMIA_POR_PERFIL[perfil]
    corpo = declaracao_da_economia(uniq, True)
    return {"controles": {chave: {"economia": valor} for chave in corpo["controles"]}}


COLUNAS: tuple[str, ...] = ("O que", "Vem de", *(ROTULOS_DOS_PERFIS[p] for p in PERFIS))


def alcance_de_hoje() -> str:
    """A frase de apoio, DERIVADA de :data:`LINHAS_DO_TETO`."""
    com_ponto = [linha.nome for linha in LINHAS_DO_TETO if linha.tem_ponto]
    sem_ponto = [linha.nome for linha in LINHAS_DO_TETO if not linha.tem_ponto]
    alcanca = _lista(com_ponto) if com_ponto else "nada"
    if not sem_ponto:
        return f"Por enquanto o teto alcança {alcanca}."
    return (
        f"Por enquanto o teto alcança {alcanca} e nada mais. "
        f"{_lista(sem_ponto)} entram quando ganharem esse ponto."
    )


DICA = f"{DICA} {alcance_de_hoje()}"


def orcamento_em_vigor(host: Any = None) -> str | None:
    """A chave do orçamento que está GRAVADA — nunca a que espera o "Aplicar"."""
    leitor = getattr(host, "_orcamento_lido", None) if host is not None else None
    if leitor is not None:
        with contextlib.suppress(Exception):
            valor = leitor()
            return valor if isinstance(valor, str) else None
        return None
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    return carregar_maquina().orcamento.teto


def orcamento_na_tela(host: Any = None) -> str | None:
    """A chave que o BOTÃO desta aba mostra — o gravado, ou o que espera o Aplicar.

    **Por que ela existe ao lado de `orcamento_em_vigor`, e não no lugar dela**
    (achado da conferência de 23/08/2026). As duas respondem perguntas
    diferentes, e cada consumidor precisa de uma:

    * a aba Rumble pergunta *"que limite o daemon está impondo AGORA?"* — e
      responde com `orcamento_em_vigor`, que ignora o pendente de propósito.
      Mostrar ali a escolha ainda não aplicada faria aquela linha afirmar um
      limite que ninguém está impondo;
    * o botão DESTA aba pergunta *"o que a pessoa escolheu?"* — e a resposta tem
      de incluir o que ela acabou de declarar. Sem isso a tela se contradiz: o
      rodapé diz "há escolhas por aplicar" e o botão mostra o valor do disco.

    É o mesmo contrato que as seções irmãs já usam (`secao_mesa`,
    `secao_controles`): disco por baixo, declaração por cima.

    O caso que mais dói, e é novo: o "Eu escolho" declara ``teto: None``. Sem
    esta função, remontar a aba traz o botão ANTIGO de volta afundado — a
    escolha da pessoa some da tela sem nada avisar.
    """
    pendente = getattr(host, "_maquina_pendente", None) or {}
    orcamento = pendente.get("orcamento") if isinstance(pendente, dict) else None
    if isinstance(orcamento, dict) and "teto" in orcamento:
        teto = orcamento["teto"]
        return str(teto) if isinstance(teto, str) else None
    return orcamento_em_vigor(host)


def perfil_na_tela(host: Any = None) -> str | None:
    """Qual dos três botões nasce afundado, lendo o que já está no disco."""
    gravado = orcamento_na_tela(host)
    if not isinstance(gravado, str):
        return None
    return PERFIL_POR_TETO.get(gravado)


def _celula(texto: str, *, cabecalho: bool = False) -> Any:
    """Uma célula da tabela: alinhada à esquerda, sem quebra."""
    from gi.repository import Gtk

    rotulo = Gtk.Label(label=_(texto))
    rotulo.set_xalign(0.0)
    if cabecalho:
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("dim-label")
    return rotulo


