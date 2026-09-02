"""O que a eleição do microfone RESPONDEU — guardado até a tela conseguir ler.

MIC-RECUSA-NA-TELA-01 (02/09/2026). Este módulo existe por causa de UMA linha,
e a linha é esta, em `daemon/subsystems/hotkey.py`:

    logger.info("mic_da_mesa_eleicao", uniq=uniq, mudo=mudo,
                ok=resultado.ok, ativo=resultado.ativo, motivo=resultado.motivo)

`integrations/eleicao_de_microfone.ResultadoDaEleicao` escreve cinco frases
boas — *"não há canal de captura atribuível a este controle"*, *"o WirePlumber
reelegeu por cima"*, *"não há microfone para onde voltar"* — e o docstring dele
diz, com todas as letras, que `motivo` **"é o texto que vai para a tela"**. Até
aqui ele ia para o `journalctl`. A regra desta casa é outra: *recusar dizendo é
obrigatório, e a frase VAI PARA A TELA* — escrita para quem está com o controle
na mão, não para quem lê log.

**POR QUE UM DEPÓSITO, e não um evento.** A interface pinta a cada 500 ms lendo
`daemon.state_full`; o toque no botão do microfone dura um instante. Uma frase
publicada só no tique em que a borda chegou tem probabilidade ~0 de coincidir
com o tique em que a tela lê — ela existiria e ninguém a veria. O recado fica
guardado no daemon e sai em TODO `state_full` até a próxima borda daquele
controle o substituir.

**POR QUE UM POR `uniq`, e não um só.** Na mesa de quatro que ela nomeou, a J1
elege e o J2 é recusado no mesmo segundo. Um depósito único faria a recusa do
J2 apagar a resposta da J1 (e vice-versa), e o card errado mostraria a frase do
vizinho. A chave é o endereço do controle, que é o mesmo endereço que o card já
usa (`data-uniq`).

**O RELÓGIO É MONOTÔNICO, e a idade sai calculada.** Quem lê a tela decide se
uma frase de dois minutos atrás ainda vale; o daemon não decide isso por ela.
Publicar o instante cru (`time.monotonic()`) seria publicar um número sem
origem — ele só significa algo comparado com o "agora" de quem o gravou, que é
justamente o que o consumidor não tem.

**O QUE ESTE MÓDULO NÃO FAZ:** não decide cor, não escolhe onde a frase aparece
na página e não inventa frase de sucesso. `ok=True` sai com `motivo` vazio, de
propósito — a eleição que deu certo já se anuncia pelo LED do plástico, e
escrever "pronto" seria a tela repetindo o que o aparelho já disse.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from hefesto_dualsense4unix.utils.logging_config import get_logger

if TYPE_CHECKING:  # pragma: no cover - só para tipo
    from hefesto_dualsense4unix.daemon.protocols import DaemonProtocol

logger = get_logger(__name__)

#: Onde o depósito fica pendurado no daemon. Mesmo padrão do
#: `_eleitor_de_microfone` (`hotkey._eleitor`): atributo do objeto vivo, não
#: global de módulo — dois daemons no mesmo processo (a suíte faz isso) não
#: podem partilhar a memória de quem apertou o quê.
ATRIBUTO = "_recados_do_microfone"

#: Teto de recados guardados. A mesa dela tem quatro lugares; o dobro cobre o
#: vaivém de hotplug sem deixar o dicionário crescer sem fim num daemon que
#: fica dias de pé. Ao estourar, sai o mais VELHO — o mais novo é o que a
#: pessoa acabou de provocar e é o único que ela está esperando ver.
TETO: int = 8

#: Os três gestos que produzem recado, e eles são distintos na tela:
#:
#: * ``eleger``  — o botão do mic subiu (não-mudo): este controle quer o canal;
#: * ``devolver``— o ELEITO foi a mudo: o microfone da mesa volta para a máquina;
#: * ``recusa``  — quem não é o eleito foi a mudo. Não há o que devolver, e o
#:   produto só apaga a luz DELE. É o caminho que estava mais calado dos três.
GESTOS = ("eleger", "devolver", "recusa")


@dataclass(frozen=True)
class RecadoDoMicrofone:
    """A resposta do produto a UM toque no botão do microfone de UM controle.

    Espelha `ResultadoDaEleicao` (`ok`/`ativo`/`motivo`) e acrescenta as três
    coisas que ela não tem e a tela precisa: de QUEM foi o toque (`uniq`), o
    que se tentou (`gesto`) e QUANDO (`quando_s`, monotônico).

    `eleito` é o dono do microfone da mesa DEPOIS do gesto — a tela usa para
    dizer que o canal está com outra pessoa sem ter de adivinhar. `None` é
    "ninguém", e não "não sei".
    """

    uniq: str
    gesto: str
    ok: bool
    motivo: str
    ativo: str | None
    eleito: str | None
    quando_s: float

    def em_dicionario(self, agora_s: float) -> dict[str, Any]:
        """O recado como o IPC o publica, com a IDADE já calculada.

        `agora_s` entra por argumento em vez de ser lido aqui para a régua
        poder medir o envelhecimento sem dormir — um teste que precisa de
        `sleep` para provar idade é um teste que mede o relógio, não o código.
        """
        return {
            "uniq": self.uniq,
            "gesto": self.gesto,
            "ok": self.ok,
            "motivo": self.motivo,
            "ativo": self.ativo,
            "eleito": self.eleito,
            "idade_s": round(max(0.0, agora_s - self.quando_s), 3),
        }


def _deposito(daemon: Any) -> dict[str, RecadoDoMicrofone]:
    """O dicionário do daemon, criado na primeira escrita. Nunca `None`."""
    atual = getattr(daemon, ATRIBUTO, None)
    if not isinstance(atual, dict):
        atual = {}
        setattr(daemon, ATRIBUTO, atual)
    return atual


def anotar(
    daemon: DaemonProtocol,
    uniq: str,
    *,
    gesto: str,
    ok: bool,
    motivo: str = "",
    ativo: str | None = None,
    eleito: str | None = None,
    agora_s: float | None = None,
) -> RecadoDoMicrofone:
    """Guarda o que aconteceu com o microfone DESTE controle.

    Substitui o recado anterior do mesmo `uniq`: o que interessa é o último
    toque, e empilhar histórico aqui faria a tela ter de escolher qual das
    frases mostrar — decisão que não é do daemon.
    """
    if gesto not in GESTOS:
        # Gesto desconhecido é erro de programação, e ele sai NOMEADO: aceitar
        # calado faria a tela receber uma palavra que ela não sabe pintar e
        # cair no ramo genérico sem que ninguém soubesse por quê.
        raise ValueError(f"gesto de microfone desconhecido: {gesto!r}")
    recado = RecadoDoMicrofone(
        uniq=uniq,
        gesto=gesto,
        ok=bool(ok),
        motivo=str(motivo or ""),
        ativo=ativo,
        eleito=eleito,
        quando_s=time.monotonic() if agora_s is None else agora_s,
    )
    deposito = _deposito(daemon)
    deposito[uniq] = recado
    while len(deposito) > TETO:
        mais_velho = min(deposito, key=lambda k: deposito[k].quando_s)
        deposito.pop(mais_velho, None)
    logger.info(
        "mic_da_mesa_recado",
        uniq=uniq,
        gesto=gesto,
        ok=recado.ok,
        motivo=recado.motivo,
        eleito=eleito,
    )
    return recado


def publicar(daemon: Any, agora_s: float | None = None) -> dict[str, Any]:
    """O bloco `mic_da_mesa` do `daemon.state_full`. Shape SEMPRE o mesmo.

    Duas chaves:

    * ``eleito`` — de quem é o microfone da mesa AGORA, lido do eleitor da
      sessão (`hotkey._eleitor`). **Lido, nunca criado**: um `getattr` que
      instanciasse o eleitor aqui faria o handler de leitura mexer no estado
      que ele existe para relatar, e a 10 Hz.
    * ``recados`` — um por `uniq`, com a frase e a idade dela.

    Daemon ausente (testes legados, modos sem daemon) devolve o bloco VAZIO em
    vez de sumir: chave que aparece e desaparece é o defeito que o
    `test_mic_da_mesa_o_ipc_a_tela_e_o_gesto` já pagou com a chave `audio` —
    `bool(None)` virava `False` e a tela pintava "ATIVO" sobre a ausência.
    """
    agora = time.monotonic() if agora_s is None else agora_s
    eleitor = getattr(daemon, "_eleitor_de_microfone", None)
    eleito = getattr(eleitor, "eleito", None) if eleitor is not None else None
    deposito = getattr(daemon, ATRIBUTO, None)
    recados: dict[str, Any] = {}
    if isinstance(deposito, dict):
        for uniq, recado in deposito.items():
            if isinstance(recado, RecadoDoMicrofone):
                recados[str(uniq)] = recado.em_dicionario(agora)
    return {
        "eleito": eleito if isinstance(eleito, str) else None,
        "recados": recados,
    }


__all__ = [
    "ATRIBUTO",
    "GESTOS",
    "TETO",
    "RecadoDoMicrofone",
    "anotar",
    "publicar",
]
