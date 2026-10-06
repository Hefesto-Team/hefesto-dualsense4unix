"""varredura_do_radio.py — quais adaptadores estão VARRENDO, e o que isso custa.

RESERVA-DO-RADIO-01 (20/09/2026). A sprint nasceu querendo **reservar** um
adaptador para os controles e deixar outro para o resto do mundo. A medição de
20/09 derrubou a premissa: não existe *"o adaptador onde o COSMIC varre"*.

    **A varredura é do adaptador que a PESSOA ABRE. Um só, o que o usuário escolheu,
    e nenhum enquanto ela não escolhe.**

Quatro corridas com a mão do usuário, a última conferida por foto da tela no instante
da medição. A tela de Bluetooth do ``cosmic-settings`` **lista** os adaptadores
sem varrer nenhum; a busca mora um nível abaixo, dentro do adaptador em que ela
entra, e a lista "Dispositivos próximos" **é** a busca.

Uma reserva estática teria de adivinhar em qual adaptador ela vai clicar — e
erraria. No dia da medição o arranjo dela estava certo **por acaso**: ela entrou
no único adaptador vazio. Bastava ter clicado no primeiro da lista pelo nome,
que hospeda um DualSense, para a perda ser real e silenciosa.

**Este módulo não adivinha: ele PERGUNTA.** ``Discovering`` é propriedade
pública do ``org.bluez.Adapter1``, não custa privilégio nenhum, responde pelo
estado de agora e cobre de graça a **cauda** — na corrida 3 o adaptador varreu
por mais 21 segundos depois de a janela fechar.

E ele não pressupõe bancada nenhuma. A ordem de 11/09 é que o produto é
para qualquer usuário; uma reserva que pressupõe três adaptadores é a bancada escrita no código, e
é por isso que a reserva morreu e esta leitura ficou.

AUSÊNCIA É RESPOSTA, E É O CONTRATO INTEIRO DESTE MÓDULO
=========================================================
``set()`` vazio quer dizer **duas coisas opostas**: "nenhum adaptador está
varrendo" e "eu não consegui olhar". Devolver as duas com a mesma string é o
defeito que esta casa persegue há um mês — *o instrumento respondia sobre outra
coisa que não o produto*.

Por isso a resposta é a :class:`Varredura`, e não um ``set``: sem ``busctl``,
sem ``bluetoothd`` ou sem permissão ela vem com :attr:`Varredura.motivo`
preenchido e :attr:`Varredura.sei` em ``False``. Quem lê **tem de** olhar o
``sei`` antes de escrever "nenhum" em qualquer lugar.

O DONO DO NÚMERO MORA AQUI
===========================
:data:`QUEDA_MINIMA_MEDIDA` e :data:`QUEDA_MAXIMA_MEDIDA` são as duas corridas
em que a varredura correu **no mesmo adaptador do controle**. Elas são o único
lugar do produto onde esse par de números é dado, e não prosa: o aviso do
``scripts/doctor.sh`` cita os dois, e
``tests/unit/test_a_varredura_do_radio_se_le_e_custa.py`` reprova se os dois
lados divergirem. Número digitado em dois donos diverge na primeira remedição.

O QUE ELE NÃO FAZ
==================
Não liga nem desliga busca. ``StartDiscovery`` e ``StopDiscovery`` são contados
**por cliente** pelo BlueZ (medido em 19/09: ``StopDiscovery`` de terceiro
devolve ``No discovery started`` e a busca continua), então não há alavanca de
fora — só quem ligou desliga. Ler é tudo o que se pode fazer daqui, e é o
bastante para o motor escolher outro destino.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from hefesto_dualsense4unix.integrations import bluez_dbus
from hefesto_dualsense4unix.integrations.conexao_zumbi import mac_limpo

#: um DualSense no rádio do adaptador medido, instrumentadas pelo evdev de
QUEDA_MINIMA_MEDIDA = 32.5
QUEDA_MAXIMA_MEDIDA = 43.4


_NO_DO_ADAPTADOR = re.compile(r"^/org/bluez/(hci[0-9]+)$")

SEM_BUSCTL = "não há `busctl` nesta máquina — não consigo perguntar ao BlueZ"

SEM_BLUEZ = "o `org.bluez` não respondeu no barramento — não sei quem varre"

MESA_TODA_MUDA = "nenhum adaptador respondeu ao `Discovering` — não sei quem varre"

SEM_RESPOSTA_A_TEMPO = (
    "o `org.bluez` não respondeu dentro do orçamento — não sei quem varre"
)

#: do GTK. :func:`varredura_recente` é chamada de ``_aplicar_estado``, que o
ORCAMENTO_DA_LEITURA = 0.5

_MINIMO_POR_PERGUNTA = 0.02


@dataclass(frozen=True)
class Varredura:
    """Quem está varrendo agora, e a confissão de quem eu não consegui olhar."""

    varrendo: frozenset[str] = field(default_factory=frozenset)
    mudos: frozenset[str] = field(default_factory=frozenset)
    motivo: str = ""

    @property
    def sei(self) -> bool:
        """``False`` quando a leitura inteira falhou — "não sei", nunca "nenhum"."""
        return not self.motivo

    @property
    def completa(self) -> bool:
        """A leitura respondeu por TODOS os adaptadores que a árvore listou."""
        return self.sei and not self.mudos


def _resta(fim: float) -> float:
    """O que sobra do orçamento para a próxima pergunta, nunca menos do que o mínimo."""
    return max(_MINIMO_POR_PERGUNTA, fim - time.monotonic())


def quem_esta_varrendo(*, orcamento: float = ORCAMENTO_DA_LEITURA) -> Varredura:
    """Os adaptadores com ``Discovering=true``, por endereço — ou "não sei"."""
    leitor = bluez_dbus.dono()
    if not leitor.pode_perguntar():
        return Varredura(motivo=SEM_BUSCTL)

    ate = time.monotonic() + orcamento
    arvore = leitor.caminhos(espera=_resta(ate)) or ()
    adaptadores = [
        (achado.group(1), caminho)
        for caminho in arvore
        if (achado := _NO_DO_ADAPTADOR.match(caminho)) is not None
    ]
    if not adaptadores:
        return Varredura(motivo=SEM_BLUEZ)

    varrendo: set[str] = set()
    mudos: set[str] = set()
    ouvidos = 0
    estourou = False
    for hci, caminho in adaptadores:
        if time.monotonic() >= ate:
            estourou = True
            mudos.add(hci)
            continue
        estado = bluez_dbus.como_booleano(
            leitor.propriedade(caminho, bluez_dbus.ADAPTADOR, "Discovering", espera=_resta(ate))
        )
        if estado is None:
            mudos.add(hci)
            continue
        ouvidos += 1
        if not estado:
            continue
        endereco = mac_limpo(leitor.endereco_do_adaptador(caminho, espera=_resta(ate)))
        if endereco is None:
            mudos.add(hci)
            continue
        varrendo.add(endereco)
    if estourou:
        motivo = SEM_RESPOSTA_A_TEMPO
    elif ouvidos == 0:
        motivo = MESA_TODA_MUDA
    else:
        motivo = ""
    return Varredura(
        varrendo=frozenset(varrendo), mudos=frozenset(mudos), motivo=motivo
    )


SEGUNDOS_DE_VALIDADE = 3.0

_LEMBRANCA: tuple[float, Varredura] | None = None


def varredura_recente(
    *,
    validade: float = SEGUNDOS_DE_VALIDADE,
    relogio: Callable[[], float] = time.monotonic,
) -> Varredura:
    """Como :func:`quem_esta_varrendo`, mas no máximo uma pergunta por ``validade``."""
    global _LEMBRANCA
    agora = relogio()
    lembranca = _LEMBRANCA
    if lembranca is not None and 0.0 <= agora - lembranca[0] < validade:
        return lembranca[1]
    leitura = quem_esta_varrendo()
    _LEMBRANCA = (agora, leitura)
    return leitura


__all__ = [
    "MESA_TODA_MUDA",
    "ORCAMENTO_DA_LEITURA",
    "QUEDA_MAXIMA_MEDIDA",
    "QUEDA_MINIMA_MEDIDA",
    "SEGUNDOS_DE_VALIDADE",
    "SEM_BLUEZ",
    "SEM_BUSCTL",
    "SEM_RESPOSTA_A_TEMPO",
    "Varredura",
    "quem_esta_varrendo",
    "varredura_recente",
]
