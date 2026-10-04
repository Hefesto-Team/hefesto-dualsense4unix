"""Seção 1 da aba Configurações — um card por controle da mesa.

Aqui entra o que o aparelho não anuncia e o produto não deduz: o modo em que um
controle não-Sony foi ligado, o rótulo dos botões, e a cor do plástico quando a
leitura falha. Todo campo nasce em "não sei", e "não sei" é resposta válida.

TERRITÓRIO DE CONFIG-06. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.

DE ONDE VEM CADA COISA NA TELA
-------------------------------

* **os controles adotados** — `daemon.state_full`, que é o único lugar onde o
  `player_slot` de um DualSense existe (`ipc_handlers.py:2294`); o
  `controller.list` devolve a lista sem ele;
* **os que o Hefesto só vê** — `controller.list {external: true}`, que já traz o
  `player_slot` deles resolvido pelo registro do daemon;
* **a cor do plástico** — lida DO APARELHO, pelos DOIS transportes, por
  `integrations/cor_do_plastico` (decisão T6). Antes desta leva a leitura vivia
  fora do aplicativo, em `scripts/ensaios/`, e toda linha "Cor:" nasceria em
  "Não sei" — inclusive nos controles no cabo, que o desenho mostra com a cor
  lida. **Quem decide se um nó pode responder é `cor_do_plastico`**, dono único
  do envelope de cada transporte — aqui não há `if` de barramento nenhum, e a
  razão está em :meth:`_PainelDosControles._perguntar_as_cores`;
* **o resto** — declaração dela, acumulada em `_maquina_pendente` e gravada
  pelo "Aplicar" do rodapé (`D-A4`: a aba é diferida, o clique só marca).

DUAS CHAMADAS, E NUNCA NUM TIQUE
---------------------------------

Os tiques desta casa são de 100 ms, 500 ms e 2 s. Enumerar o `/dev/input`
inteiro e sondar quem segura cada `hidraw` custa de 10 a 40 ms mais um
subprocesso (`ipc_handlers.py:561`), e nada disso muda entre dois quadros. A
leitura roda ao ENTRAR na aba, e só.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.app.fala_do_mapa import formata_pt_br
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TITULO = "Os controles"

DICA: str | None = (
    "A borda de cada card é a cor do plástico daquele controle. O anel roxo "
    "por dentro marca qual está selecionado no cabeçalho da janela."
)


COLUNAS = 3


# A barra do DualSense por rádio nasce travada em ALGUMAS instâncias de conexão,
# 2. **o produto NÃO reconecta.** O botão PS é dela. Este arquivo derruba e
#    espera; `integrations/gesto_de_reconexao` não tem `reconectar` de propósito;

TEXTO_DO_BOTAO = "A luz não acende"

ESPERA_PELO_PS_S = 60

FRASE_APERTE_PS = "Aperte PS no controle"

TEXTO_CANCELAR = "Cancelar"

DICA_NO_RADIO = (
    "Derruba este controle do BT. Depois aperte PS nele para ele voltar — é "
    "a única cura conhecida para a barra que nasce travada. O Hefesto não "
    "reconecta sozinho: o botão PS é seu."
)

DICA_NO_CABO = (
    "Só vale no BT. Pelo USB a barra obedece — o defeito que este gesto "
    "cura não existe no USB, e por isso o botão fica apagado aqui."
)

# O AVISO DA MESA SUJA SAIU DA DICA — FRASES-E-DICAS-02, 13/09/2026. Aqui

ESPERA_PROCURANDO = "procurando"
ESPERA_VOLTOU = "voltou"
ESPERA_NAO_CAIU = "nao_caiu"  # (noqa-acento): chave de máquina
ESPERA_NAO_VOLTOU = "nao_voltou"  # (noqa-acento): chave de máquina
ESPERA_CANCELADA = "cancelada"

FRASE_NAO_CAIU = (
    "O controle não chegou a cair do rádio, então não houve o que reconectar. "
    "Ele continua pareado."
)


def frase_da_procura(restantes: int) -> str:
    """A linha que conta o tempo, do desenho: ``procurando…  38s``."""
    return f"procurando…  {max(0, int(restantes))}s"


def frase_nao_voltou(segundos: int) -> str:
    """O controle caiu e não voltou no tempo."""
    return (
        f"Não voltou em {int(segundos)}s. Ele continua pareado — aperte PS nele "
        "quando quiser."
    )


# moravam `FRASE_NASCEU_CONDENADO` e `frase_do_nascimento`
# anexo da dica do mesmo botão na aba 08. A ordem dela de 13/09
# O carimbo `nascimento` continua no `state_full`, para o diagnóstico.


def pode_derrubar(dados: Any) -> bool:
    """O botão é clicável neste card?

    Três condições, e a regra dela é a primeira: **no rádio**. As outras duas
    são o que o gesto precisa para existir — um DualSense adotado (o 8BitDo não
    tem barra) e um endereço para o BlueZ procurar.
    """
    return (
        bool(getattr(dados, "adotado", False))
        and not bool(getattr(dados, "no_cabo", False))
        and bool(getattr(dados, "uniq", ""))
    )


def dica_do_botao(dados: Any) -> str:
    """A dica do botão, e ela nunca é vazia."""
    if not pode_derrubar(dados):
        return DICA_NO_CABO
    return DICA_NO_RADIO


def uniq_normalizado(mac: Any) -> str:
    """``AA:BB:CC:00:00:01`` → ``aabbcc000001``; o que não é MAC → ``""``."""
    limpo = str(mac or "").replace(":", "").replace("-", "").strip().lower()
    if len(limpo) != 12 or any(c not in "0123456789abcdef" for c in limpo):
        return ""
    return limpo


def uniqs_no_radio() -> set[str] | None:
    """Os DualSense que estão no rádio AGORA. ``None`` = não consegui olhar.

    Só leitura de sysfs (`integrations/sinal_da_barra.instancias_dualsense`):
    nada aqui abre `/dev/hidraw`, roda subprocesso ou toca o aparelho — é o que
    a torna barata o bastante para um tique de um segundo.

    **A terceira resposta é a razão desta função existir.** Uma lista vazia
    porque `/sys` não pôde ser lido é indistinguível de uma lista vazia porque
    todos os controles caíram — e essa confusão faria a espera anunciar "caiu"
    sem nada ter caído. Por isso a raiz é conferida antes, e a ausência dela
    devolve ``None``, que a espera trata como "continua esperando".
    """
    try:
        import os

        from hefesto_dualsense4unix.integrations.sinal_da_barra import (
            RAIZ_UHID,
            instancias_dualsense,
        )
    except ImportError:
        return None
    if not os.path.isdir(RAIZ_UHID):
        return None
    try:
        vivas = instancias_dualsense()
    except OSError:
        return None
    return {
        uniq_normalizado(instancia.uniq)
        for instancia in vivas
        if instancia.no_radio and uniq_normalizado(instancia.uniq)
    }


class EsperaPeloPS:
    """A espera pelo botão PS de UM controle. Sem GTK, sem IPC, sem relógio."""

    def __init__(
        self,
        uniq: str,
        *,
        total_s: int = ESPERA_PELO_PS_S,
        sonda: Callable[[], set[str] | None] | None = None,
    ) -> None:
        self.alvo = uniq_normalizado(uniq)
        self.total_s = int(total_s)
        self.restantes = int(total_s)
        self.estado = ESPERA_PROCURANDO
        self.caiu = False
        self._sonda = sonda if sonda is not None else uniqs_no_radio

    @property
    def acabou(self) -> bool:
        return self.estado != ESPERA_PROCURANDO

    @property
    def porque(self) -> str:
        """A frase do fim, para a tela. Vazia enquanto ainda procura."""
        if self.estado == ESPERA_NAO_CAIU:
            return FRASE_NAO_CAIU
        if self.estado == ESPERA_NAO_VOLTOU:
            return frase_nao_voltou(self.total_s)
        return ""

    def cancelar(self) -> None:
        """Ela desistiu. NÃO reconecta — não existe reconexão neste produto."""
        if not self.acabou:
            self.estado = ESPERA_CANCELADA

    def tique(self) -> str:
        """Passa um segundo e devolve o estado. Idempotente depois do fim."""
        if self.acabou:
            return self.estado
        presentes = self._olhar()
        if presentes is not None:
            if self.alvo in presentes:
                if self.caiu:
                    self.estado = ESPERA_VOLTOU
                    return self.estado
            else:
                self.caiu = True
        self.restantes = max(0, self.restantes - 1)
        if self.restantes == 0:
            self.estado = ESPERA_NAO_VOLTOU if self.caiu else ESPERA_NAO_CAIU
        return self.estado

    def _olhar(self) -> set[str] | None:
        """A sonda, embrulhada: uma falha dela não pode derrubar a janela."""
        try:
            return self._sonda()
        except Exception:
            logger.debug("config_luz_sonda_falhou", exc_info=True)
            return None


DICA_MIC_SEM_ENDERECO = (
    "Este controle não tem endereço fixo, então o Hefesto não tem como guardar "
    "a quem esta ponte pertence."
)


def _numero(valor: float) -> str:
    """Uma casa decimal, com vírgula — é assim que ela lê número nesta casa.

    Delega ao DONO ÚNICO (`app/fala_do_mapa.formata_pt_br`) desde 26/08/2026.
    Até então era uma segunda implementação da mesma regra, e a saída idêntica
    é o que fazia ninguém notar: no dia em que uma delas mudasse de
    arredondamento, esta seção e a célula do mapa passariam a dizer números
    diferentes sobre o mesmo fato. O nome local fica porque as quatro chamadas
    abaixo o usam e ele diz o que faz nesta seção.
    """
    return formata_pt_br(valor)


def frase_da_capacidade_do_mic() -> str:
    """Quanto do rádio um microfone ocupa. DERIVADA, nunca digitada."""
    from hefesto_dualsense4unix.integrations.radio_da_mesa import (
        HZ_AUDIO_COM_MIC,
        HZ_INPUT_COM_MIC,
        HZ_INPUT_SEM_MIC,
        SLOTS_POR_SEGUNDO,
    )

    total = HZ_INPUT_COM_MIC + HZ_AUDIO_COM_MIC
    return (
        f"Com o microfone ligado, um controle no BT troca {_numero(HZ_INPUT_SEM_MIC)} "
        f"relatórios de entrada por segundo por {_numero(HZ_INPUT_COM_MIC)} mais "
        f"{_numero(HZ_AUDIO_COM_MIC)} quadros de áudio: {_numero(total)} das "
        f"{SLOTS_POR_SEGUNDO} fatias daquele adaptador. Quanto já está em uso "
        f'está na seção "{secao_mesa.TITULO}".'
    )


def _lista(valor: Any) -> list[dict[str, Any]]:
    if not isinstance(valor, list):
        return []
    return [item for item in valor if isinstance(item, dict)]


def _inteiro(valor: Any) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


