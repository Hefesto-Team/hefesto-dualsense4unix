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

**POR QUE UM POR `uniq`, e não um só.** Na mesa de quatro que o usuário nomeou, a J1
elege e o J2 é recusado no mesmo segundo. Um depósito único faria a recusa do
J2 apagar a resposta da J1 (e vice-versa), e o card errado mostraria a frase do
vizinho. A chave é o endereço do controle, que é o mesmo endereço que o card já
usa (`data-uniq`).

**O RELÓGIO É MONOTÔNICO, e a idade sai calculada.** Publicar o instante cru
(`time.monotonic()`) seria publicar um número sem origem — ele só significa
algo comparado com o "agora" de quem o gravou, que é justamente o que o
consumidor não tem.

**E O RECADO TEM PRAZO — decisão, 02/09/2026:** *"a frase de recusa some
depois de um tempo, na ordem de 30 segundos. É aviso, não estado."* Passado o
`VALIDADE_DO_RECADO_S`, o recado deixa de ser publicado e a chave do `uniq`
some do bloco. Antes disso o depósito republicava a última resposta até o
toque seguinte DAQUELE controle — e como um controle pode ficar horas sem
tocar no botão, a tela mostrava uma frase de meia hora atrás com cara de
agora. O que NÃO expira é o estado do canal (`eleito`, `eleito_na_mesa`): esse
é fato da máquina, não aviso.

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

ATRIBUTO = "_recados_do_microfone"

TETO: int = 8

GESTOS = ("eleger", "devolver", "recusa")

VALIDADE_DO_RECADO_S: float = 30.0


@dataclass(frozen=True)
class RecadoDoMicrofone:
    """A resposta do produto a UM toque no botão do microfone de UM controle."""

    uniq: str
    gesto: str
    ok: bool
    motivo: str
    ativo: str | None
    eleito: str | None
    quando_s: float

    def expirou(self, agora_s: float) -> bool:
        """Passou de `VALIDADE_DO_RECADO_S`? Então ele não é mais publicado."""
        return (agora_s - self.quando_s) >= VALIDADE_DO_RECADO_S

    def em_dicionario(self, agora_s: float, *, dono_agora: str | None) -> dict[str, Any]:
        """O recado como o IPC o publica, com a IDADE e a VALIDADE calculadas."""
        return {
            "uniq": self.uniq,
            "gesto": self.gesto,
            "ok": self.ok,
            "motivo": self.motivo,
            "ativo": self.ativo,
            "eleito": self.eleito,
            "idade_s": round(max(0.0, agora_s - self.quando_s), 3),
            "vale_agora": self.eleito == dono_agora,
        }


def mesa_de_agora(daemon: Any) -> list[str] | None:
    """Os `uniq` na mesa AGORA, ou `None` quando o backend não sabe dizer.

    **É A ÚNICA LEITURA DE "TEM CARD NA TELA", e ela é pública por isso.**
    Nasceu privada em 02/09/2026 e o preço apareceu no mesmo dia: o
    `hotkey._eleger_ou_devolver` perguntava a mesma coisa a `_uniqs_conectados`,
    que NÃO exige o `connected`, e as duas respostas divergiam exatamente na
    cena que a onda existe para curar. Reproduzido com o laço do produto e um
    backend que devolve o handle com `connected: False` (que é o que o backend
    real faz — ver abaixo):

        bloco = {"eleito": "…011", "eleito_na_mesa": false,
                 "recados": {"…022": {"motivo": "o microfone da mesa está com
                 OUTRO CONTROLE…"}}}

    O mesmo `state_full` dizia, em duas chaves, que o dono saiu da mesa e que o
    canal está com ele. Duas réguas sobre o mesmo estado é o defeito que esta
    casa já pagou onze vezes; agora há uma.

    **A diferença entre `[]` e `None` é a diferença entre "a mesa está vazia" e
    "não perguntei a ninguém"**, e confundi-las é como esta casa já publicou
    ausência de dado como negação — o `bool(None)` que pintava ATIVO sobre o
    controle que tinha acabado de cair. Backend legado, `FakeController` ou
    `describe_controllers` que levanta devolvem `None`, e quem lê trata isso
    como "não dá para afirmar que alguém saiu".

    É a mesma fonte que `hotkey._uniqs_conectados` e
    `ipc_handlers._uniqs_conectados` leem — só getattrs baratos, sem HID I/O —
    e por isso ela cabe no caminho de leitura, que roda a 10 Hz.

    **E ELA EXIGE O `connected`, que aquelas duas não exigem** — que é
    justamente por que a pergunta *"tem card na tela?"* tem de vir a esta
    função e não a elas. O
    `describe_controllers` do backend real devolve uma entrada POR HANDLE e
    preenche o `uniq` mesmo com `connected: False`
    (`core/backend_pydualsense.py:5470`) — ler só o `uniq` daria "está na mesa"
    a um handle que o controle já largou, que é exatamente o defeito que este
    campo existe para matar. As outras duas montam a lista que vai para a
    ELEIÇÃO (`eleger_o_controle`), e mudá-las mexeria em quem pode ser eleito;
    aqui a pergunta é outra — *tem card na tela?* — e a resposta certa é a que
    o backend dá no `connected`.
    """
    controlador = getattr(daemon, "controller", None)
    descrever = getattr(controlador, "describe_controllers", None)
    if not callable(descrever):
        return None
    try:
        itens = descrever()
    except Exception:  # pragma: no cover - defensivo, igual ao do hotkey
        return None
    if not isinstance(itens, list):
        return None
    return [
        item["uniq"]
        for item in itens
        if isinstance(item, dict)
        and isinstance(item.get("uniq"), str)
        and item.get("uniq")
        and item.get("connected")
    ]


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
    """Guarda o que aconteceu com o microfone DESTE controle."""
    if gesto not in GESTOS:
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

    Três chaves:

    * ``eleito`` — de quem o ELEITOR da sessão diz que é o microfone da mesa,
      lido de `hotkey._eleitor`. **Lido, nunca criado**: um `getattr` que
      instanciasse o eleitor aqui faria o handler de leitura mexer no estado
      que ele existe para relatar, e a 10 Hz. É a verdade da MÁQUINA — a fonte
      padrão do sistema aponta para lá — e não a da mesa; ver a chave seguinte.
    * ``eleito_na_mesa`` — o `eleito` ainda está entre os controles
      conectados? ``True``/``False``, e ``None`` quando não há eleito ou
      quando o backend não sabe dizer quem está na mesa. **``False`` é o
      hotplug-out sem devolução**: o controle caiu do cabo/rádio e nada em
      `src/` limpou a posse, então a tela tem um dono que não tem card. Pintar
      o nome dele seria a nona vez que esta casa nomeia um controle fora da
      mesa.
    * ``recados`` — um por `uniq`, com a frase, a idade dela e o ``vale_agora``
      que diz se o retrato da mesa gravado JUNTO com a frase ainda é o de
      agora. **Recado passado de `VALIDADE_DO_RECADO_S` não sai** — a chave do
      `uniq` some, e a tela fica sem o que pintar, que é o que o usuário decidiu
      (*"campo sem informação não mostra nada"*).

    **O PRAZO FILTRA, NÃO APAGA.** `publicar` roda a 10 Hz no caminho de
    LEITURA, e este módulo já recusou mexer no estado por aqui uma vez (o
    `getattr` que não instancia o eleitor). Jogar o recado fora daria a este
    caminho uma escrita, e não compra nada: quem limita a memória é o `TETO`,
    e um recado expirado é substituído pelo próximo toque daquele controle.

    **O QUE `vale_agora` LICENCIA, e a tela não pode ir além disso.** Ele é a
    comparação entre o `eleito` CONGELADO no recado e o dono de agora do ponto
    de vista da mesa. ``False`` significa: a mesa mudou desde o toque, o
    `eleito` de dentro do recado virou história, e uma frase de ``recusa`` —
    que nasce exatamente desse retrato — não pode mais ser pintada no
    presente. ``True`` não promete que a frase é verdade; promete que o mundo
    que ela descreve ainda é este.

    Daemon ausente (testes legados, modos sem daemon) devolve o bloco VAZIO em
    vez de sumir: chave que aparece e desaparece é o defeito que o
    `test_mic_da_mesa_o_ipc_a_tela_e_o_gesto` já pagou com a chave `audio` —
    `bool(None)` virava `False` e a tela pintava "ATIVO" sobre a ausência.
    """
    agora = time.monotonic() if agora_s is None else agora_s
    eleitor = getattr(daemon, "_eleitor_de_microfone", None)
    cru = getattr(eleitor, "eleito", None) if eleitor is not None else None
    eleito = cru if isinstance(cru, str) else None

    mesa = mesa_de_agora(daemon)
    eleito_na_mesa = None if (eleito is None or mesa is None) else eleito in mesa
    dono_agora = None if eleito_na_mesa is False else eleito

    deposito = getattr(daemon, ATRIBUTO, None)
    recados: dict[str, Any] = {}
    if isinstance(deposito, dict):
        for uniq, recado in deposito.items():
            if isinstance(recado, RecadoDoMicrofone) and not recado.expirou(agora):
                recados[str(uniq)] = recado.em_dicionario(agora, dono_agora=dono_agora)
    return {
        "eleito": eleito,
        "eleito_na_mesa": eleito_na_mesa,
        "recados": recados,
    }


__all__ = [
    "ATRIBUTO",
    "GESTOS",
    "TETO",
    "VALIDADE_DO_RECADO_S",
    "RecadoDoMicrofone",
    "anotar",
    "mesa_de_agora",
    "publicar",
]
