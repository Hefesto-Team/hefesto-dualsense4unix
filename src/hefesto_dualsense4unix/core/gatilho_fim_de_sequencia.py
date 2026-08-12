"""O mecanismo: reafirmar o que o produto quer **no fim de uma sequência**.

- **Decisão dela, 12/08/2026**, e é ela quem generalizou: *"reafirmar o que o
  produto quer no fim da sequência, seja cor, número ou o IGNORE do ambiente"*.
- **Este módulo é só o MECANISMO.** O conteúdo — que cor, que número, que
  ambiente — é de quem registra a ação. Ele não sabe o que é lightbar.

A CLASSE DE DEFEITO, com três casos medidos
===========================================
Os três têm a mesma forma: **o produto decide DURANTE uma sequência de
eventos, em vez de esperar ela sossegar.** Não é coincidência de sintoma, é o
mesmo erro de tempo.

1. **Rumble** — o keepalive escrevia dentro da janela em que outro dono acabara
   de ligar o motor, e zerava o rumble alheio (`RUMBLE-SEM-DONO-01`, 11/08).
   Curado por janela de confirmação, já na árvore;
2. **Lightbar e número de jogador** — o produto pinta no *priming*, dentro da
   rajada com que a Steam repinta tudo a cada conexão nova, e perde a última
   palavra (`GATILHO-DA-COR-01`, 12/08). É o primeiro usuário deste módulo;
3. **Co-op / `IGNORE` do ambiente** — a cura que esconde os DualSense físicos
   do jogo exige um vpad por físico, e foi avaliada TRÊS vezes durante a subida
   dos vpads, sempre com cobertura incompleta, e nunca depois que ela ficou
   completa. O quarto vpad ficou pronto ONZE SEGUNDOS depois do primeiro
   (ensaio `coop-ignore-avaliado-cedo` em `docs/data/ensaios.csv`).

O MECANISMO, em uma frase
=========================
**Armar a cada evento conhecido, RE-ADIAR enquanto eles chegam, disparar
quando sossegar por N segundos, e agir sobre tudo o que estiver na mesa.**

As quatro partes não são independentes — cada uma nasceu de um jeito de errar:

- *armar a cada evento*, e não a cada objeto: a rajada é do EVENTO, e um
  relógio por controle perde todos menos o último (medido);
- *re-adiar*: sem isso o primeiro evento decide o instante, e é justamente o
  instante errado;
- *disparar quando sossega*: o número é de quem chama, porque é medido lá —
  1,5 s para a rajada da Steam não tem nada a ver com os 11 s da subida dos
  vpads. Por isso `atraso_s` **não tem valor padrão** aqui: um mecanismo
  genérico não pode inventar o número de ninguém;
- *agir sobre tudo o que está na mesa*: repintar só quem chegou deixa os
  outros no estado do intruso.

COMO OUTRO SUBSISTEMA USA
=========================
Registre uma ação nomeada no `RegistroDeGatilhos` do daemon e arme a cada
evento que você já detecta. Quem conta o tempo e chama a ação é o
`reconnect_loop` (`daemon/connection.py`), que é o único relógio — dois
relógios dariam duas sequências para o mesmo silêncio::

    from hefesto_dualsense4unix.daemon.connection import (
        armar_gatilho, registrar_gatilho,
    )

    registrar_gatilho(daemon, "coop_ignore", reavaliar_ignore, atraso_s=12.0)
    ...
    armar_gatilho(daemon, "coop_ignore", evento="vpad_pronto")

A **ação resolve o conteúdo na hora de agir, nunca antes**. Isto é requisito,
não estilo: o autoswitch troca de perfil quando o jogo abre (medido em 12/08 —
o perfil `Sackboy` tem cor própria `[80,60,220]` e foi aplicado no meio do
ensaio), então uma ação que guardasse o valor no momento de armar reafirmaria
o que o produto queria ANTES, e brigaria com o próprio produto.
"""
from __future__ import annotations

from collections.abc import Callable

from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: A ação de um gatilho: sem argumentos, o retorno é só para o log. Ela é
#: chamada no executor pelo laço que conta o tempo, então pode fazer I/O.
Tarefa = Callable[[], object]


class GatilhoDeFimDeSequencia:
    """Debounce por FIM DE SEQUÊNCIA, com nome e ação próprios.

    Lógica pura no tempo: recebe o instante de fora, não lê relógio nenhum.
    É de propósito — é o que torna um comportamento medido em segundos
    exercitável em milissegundos, sem hardware e sem espera.

    O contrato tem três frases:

    - ``armar`` a cada evento, e cada chamada **RE-ADIA** o disparo;
    - ``consumir_se_a_sequencia_acabou`` devolve quantos eventos a sequência
      juntou — e só quando ninguém mais chegou dentro do atraso. Depois disso
      desarma: **uma ação por sequência**;
    - a **tarefa** é resolvida por quem registra, e só é chamada no disparo.
    """

    def __init__(self, nome: str, tarefa: Tarefa, *, atraso_s: float) -> None:
        self.nome = str(nome)
        self.tarefa = tarefa
        self._atraso_s = float(atraso_s)
        self._ultimo_evento_em: float | None = None
        self._eventos = 0

    @property
    def atraso_s(self) -> float:
        """Quanto se espera depois do último evento. Medido por quem registra."""
        return self._atraso_s

    @property
    def armado(self) -> bool:
        """True enquanto há uma sequência aberta esperando sossegar."""
        return self._ultimo_evento_em is not None

    @property
    def eventos_armados(self) -> int:
        """Quantos eventos esta sequência já juntou."""
        return self._eventos

    def armar(self, agora: float, *, quantos: int = 1) -> None:
        """Registra ``quantos`` eventos em ``agora`` e RE-ADIA o disparo.

        Chamar com a sequência já armada é o caso NORMAL, não a exceção: é o
        segundo, o terceiro e o quarto evento da rajada. Cada um empurra o
        relógio para a frente, porque cada um recomeça o estrago.
        """
        self._ultimo_evento_em = float(agora)
        self._eventos += max(1, int(quantos))

    def desarmar(self) -> None:
        """Esquece a sequência aberta sem disparar.

        Para quando o motivo de agir desapareceu — a mesa esvaziou, o
        subsistema caiu. Uma sequência velha que sobrevive dispara no primeiro
        evento da PRÓXIMA rajada, adiantada: o defeito exato que o mecanismo
        existe para evitar.
        """
        self._ultimo_evento_em = None
        self._eventos = 0

    def falta_para_disparar(self, agora: float) -> float | None:
        """Segundos que faltam, ou ``None`` quando não há sequência armada.

        Serve para quem espera em fatias saber quando acordar — sem isso o
        laço de fora teria de escolher entre dormir demais (a reafirmação
        demora) ou girar apertado (custo por nada, o dia inteiro).
        """
        if self._ultimo_evento_em is None:
            return None
        return max(0.0, self._atraso_s - (float(agora) - self._ultimo_evento_em))

    def consumir_se_a_sequencia_acabou(self, agora: float) -> int:
        """``0`` = ainda não. ``>0`` = aja, e este é o tamanho da sequência.

        Consome: a mesma sequência nunca dispara duas vezes.
        """
        if self._ultimo_evento_em is None:
            return 0
        if float(agora) - self._ultimo_evento_em < self._atraso_s:
            return 0
        eventos = self._eventos
        self.desarmar()
        return eventos


class RegistroDeGatilhos:
    """Os gatilhos vivos deste daemon, por nome — um relógio para todos.

    Existe para que o segundo e o terceiro usuários do mecanismo não copiem
    código nem criem um laço próprio. Quem registra diz **o nome, a ação e o
    seu número medido**; quem conta o tempo é o `reconnect_loop`.

    `registrar` é idempotente e tolerante a ordem: chamar de novo com o mesmo
    nome atualiza a ação (e o atraso, se vier) sem perder a sequência já
    armada. É o que permite registrar tarde — no meio de um hotplug, depois de
    um subsistema subir — sem que a ordem de fiação vire regra escondida.
    """

    def __init__(self) -> None:
        self._gatilhos: dict[str, GatilhoDeFimDeSequencia] = {}

    def registrar(
        self, nome: str, tarefa: Tarefa, *, atraso_s: float | None = None
    ) -> GatilhoDeFimDeSequencia:
        """Cria (ou atualiza) o gatilho ``nome``. Devolve o objeto vivo."""
        gatilho = self._gatilhos.get(nome)
        if gatilho is None:
            if atraso_s is None:
                raise ValueError(
                    f"gatilho '{nome}' novo precisa de `atraso_s` — o número é "
                    "medido por quem registra, e este mecanismo não inventa "
                    "número de ninguém"
                )
            gatilho = GatilhoDeFimDeSequencia(nome, tarefa, atraso_s=atraso_s)
            self._gatilhos[nome] = gatilho
            logger.info("gatilho_registrado", nome=nome, atraso_s=atraso_s)
            return gatilho
        gatilho.tarefa = tarefa
        if atraso_s is not None:
            gatilho._atraso_s = float(atraso_s)
        return gatilho

    def obter(self, nome: str) -> GatilhoDeFimDeSequencia | None:
        """O gatilho ``nome``, ou ``None`` se ninguém o registrou ainda."""
        return self._gatilhos.get(nome)

    def armar(self, nome: str, agora: float, *, quantos: int = 1) -> bool:
        """Arma o gatilho ``nome``. ``False`` se ele não existe (nunca levanta).

        Não levantar é decisão: um subsistema que arma antes de registrar não
        pode derrubar o caminho que o chamou — o pior que acontece é a
        reafirmação daquele nome não sair.
        """
        gatilho = self._gatilhos.get(nome)
        if gatilho is None:
            return False
        gatilho.armar(agora, quantos=quantos)
        return True

    def algum_armado(self) -> bool:
        """True se ao menos uma sequência está aberta (o laço encurta a fatia)."""
        return any(g.armado for g in self._gatilhos.values())

    def devidos(self, agora: float) -> list[tuple[GatilhoDeFimDeSequencia, int]]:
        """Os gatilhos cuja sequência acabou, já consumidos, com o tamanho dela."""
        prontos: list[tuple[GatilhoDeFimDeSequencia, int]] = []
        for gatilho in list(self._gatilhos.values()):
            eventos = gatilho.consumir_se_a_sequencia_acabou(agora)
            if eventos:
                prontos.append((gatilho, eventos))
        return prontos

    def desarmar_todos(self) -> None:
        """Esquece toda sequência aberta (a mesa esvaziou, o daemon vai parar)."""
        for gatilho in self._gatilhos.values():
            gatilho.desarmar()


__all__ = [
    "GatilhoDeFimDeSequencia",
    "RegistroDeGatilhos",
    "Tarefa",
]
