"""O `pw-loopback` com dono — um nó ligado a outro, por chave, e quem fecha.

**POR QUE ESTE MÓDULO EXISTE.** Em 21/09/2026 o produto ganhou dois botões que
fazem a mesma coisa mecânica com propósitos diferentes:

* o 🎙 da coluna do microfone — a voz dela volta pela saída padrão enquanto o
  botão está verde (o «Let's Check» do Discord);
* «Tudo na TV e Nada no Controle» — o som que o jogo endereça ao controle sai
  pela TV em vez de morrer no nó.

Os dois são *"ligue este nó àquele, e me avise quando cair"*. Escrever isso duas
vezes é como dois donos do mesmo estado começam a divergir: um lembra de matar
o processo no fecho, o outro não; um pergunta ao `poll()`, o outro guarda um
booleano. Esta casa já pagou por essa divergência com 22 `null-sinks` vivos onde
cabiam 4.

**O ESTADO É DO SISTEMA, NUNCA DA LEMBRANÇA.** :meth:`Lacos.esta_ligado`
pergunta ao `poll()` do processo; um `bool` guardado à parte mentiria no
instante em que o `pw-loopback` morresse sozinho (o controle saiu, o servidor de
som reiniciou), e o botão ficaria aceso sobre um laço que não existe mais.

**TODA FAMÍLIA MORRE NO FECHO.** O `atexit` no fim do arquivo fecha as laçadas
de todas as famílias registradas. Um `pw-loopback` órfão continua lendo o
microfone dela — ou empurrando som para a TV — depois de a janela fechar, sem
nada na tela que o diga. A interface morre; o processo, não.
"""

from __future__ import annotations

import atexit
import shutil
import subprocess
import threading

import structlog

logger = structlog.get_logger(__name__)

__all__ = ["LATENCIA_MS", "Lacos", "fechar_tudo"]

#: A latência dos laços, em milissegundos.
#:
#: **50 ms é o mesmo número dos gravadores desta casa**, e ele não é gosto: sem
#: latência explícita o PipeWire escolhe um buffer generoso e o som chega com
#: quase dois segundos de atraso — mordeu o microfone e a ponte do rádio, as
#: duas vezes com o mesmo sintoma (*"o som sai, mas atrasado"*). No retorno de
#: voz o atraso é pior que em qualquer outro lugar: quem se ouve com meio
#: segundo de atraso não consegue falar.
LATENCIA_MS = 50

_FAMILIAS: list[Lacos] = []


class Lacos:
    """As laçadas de UMA família, guardadas por chave (normalmente o `uniq`).

    `familia` vira o nome do nó no PipeWire (`hefesto-<familia>-<chave>`), e é
    o que aparece no `pw-link`/`qpwgraph` quando alguém for olhar o grafo. Um
    nome genérico ali faria a próxima pessoa não saber qual botão o criou.
    """

    def __init__(self, familia: str) -> None:
        self.familia = familia
        self._vivos: dict[str, subprocess.Popen[bytes]] = {}
        self._trava = threading.Lock()
        _FAMILIAS.append(self)

    def esta_ligado(self, chave: str) -> bool:
        """Esta laçada está de pé AGORA? Pergunta ao processo, não à lembrança."""
        if not chave:
            return False
        with self._trava:
            proc = self._vivos.get(chave)
            if proc is None:
                return False
            if proc.poll() is None:
                return True
            self._vivos.pop(chave, None)
            return False

    def ligados(self) -> tuple[str, ...]:
        """As chaves com laçada de pé, em ordem ESTÁVEL.

        Ordem alfabética porque a lista vai para a tela: uma que mudasse de
        ordem a cada tique faria dois estados iguais parecerem diferentes.
        """
        with self._trava:
            vivos = [c for c, p in self._vivos.items() if p.poll() is None]
            for morto in [c for c in self._vivos if c not in vivos]:
                self._vivos.pop(morto, None)
        return tuple(sorted(vivos))

    def ligar(
        self,
        chave: str,
        *,
        captura: str,
        destino: str = "",
        canais: int = 1,
        mapa: str = "[ MONO ]",
    ) -> bool:
        """Abre a laçada. `True` = de pé.

        :param captura: o nó de onde o som SAI.
        :param destino: o nó para onde ele VAI; vazio manda à saída padrão.

        **LIGAR DUAS VEZES NÃO ABRE DUAS**: o segundo pedido responde `True`
        sobre o que já está de pé. Sem esta linha, dois cliques rápidos
        deixariam um `pw-loopback` órfão — e foi assim que um `parec` ficou 39
        minutos com o microfone dela aberto em 03/09.
        """
        if not chave or not captura:
            return False
        if self.esta_ligado(chave):
            return True
        if shutil.which("pw-loopback") is None:
            logger.info("laco_sem_pw_loopback", familia=self.familia, chave=chave)
            return False
        argv = [
            "pw-loopback",
            "--capture", captura,
            "--latency", str(LATENCIA_MS),
            "--channels", str(canais),
            "--channel-map", mapa,
            "--name", f"hefesto-{self.familia}-{chave}",
        ]
        if destino:
            argv += ["--playback", destino]
        try:
            proc = subprocess.Popen(  # argv fixo, sem shell
                argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.info(
                "laco_nao_subiu", familia=self.familia, chave=chave, err=str(exc))
            return False
        with self._trava:
            self._vivos[chave] = proc
        logger.info(
            "laco_ligado", familia=self.familia, chave=chave,
            captura=captura, destino=destino or "(padrão)")
        return True

    def desligar(self, chave: str) -> bool:
        """Fecha a laçada. `True` = havia uma e ela morreu.

        `kill` e não `terminate` com espera longa: é um loopback de áudio, não
        há estado a salvar, e um segundo entre o clique e o silêncio é um
        segundo em que o botão mente.
        """
        with self._trava:
            proc = self._vivos.pop(chave, None)
        if proc is None:
            return False
        try:
            proc.kill()
            proc.wait(timeout=2)
        except (OSError, subprocess.SubprocessError):
            pass
        logger.info("laco_desligado", familia=self.familia, chave=chave)
        return True

    def alternar(self, chave: str, *, captura: str, **kw: object) -> bool:
        """Liga se estava desligada, desliga se estava ligada. Devolve o estado NOVO.

        O retorno é o estado novo de propósito: quem chama pinta a luz com o
        que recebe, sem uma segunda consulta que poderia responder diferente no
        meio.
        """
        if self.esta_ligado(chave):
            self.desligar(chave)
            return False
        return self.ligar(chave, captura=captura, **kw)  # type: ignore[arg-type]

    def desligar_todos(self) -> int:
        """Fecha tudo desta família e devolve quantas eram."""
        return sum(1 for chave in list(self._vivos) if self.desligar(chave))


def fechar_tudo() -> int:
    """Fecha as laçadas de TODAS as famílias. Registrado no `atexit` abaixo."""
    return sum(familia.desligar_todos() for familia in _FAMILIAS)


atexit.register(fechar_tudo)
