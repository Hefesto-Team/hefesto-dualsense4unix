"""O 🎙 ligado — você se ouve enquanto ele está verde.

**A ORDEM É DELA, 21/09/2026**, depois de usar o botão que gravava três
segundos:

    "O FUNCIONAMENTO DO BOTÃO MIC TÁ ZUADO. SE EU ATIVAR COM UM CLICK E ELE
     FICAR VERDE ELE TÁ ATIVADO E SEGUE ASSIM ATÉ EU DESATIVAR CLICANDO
     NOVAMENTE E ELE FICANDO CINZA. POR DEFAULT SEGUE DESLIGADO, ATÉ ALGUEM
     CLICAR E VER ISSO REFLETINDO LÁ."

O ato de 20/09 gravava três segundos e devolvia — uma resposta, e depois
silêncio. O que ela descreve é o **«Let's Check» do Discord**: enquanto ligado,
a voz volta continuamente, e ela ajusta os dois deslizantes OUVINDO o efeito.
Com três segundos por clique não há como ajustar nada: o som some antes de a
mão chegar ao trilho.

O MECANISMO, e por que não é `parec | paplay`
=============================================

`pw-loopback` liga a fonte ao destino **dentro do PipeWire**, sem copiar
amostra nenhuma por um cano de shell. Um par `parec | paplay` custa dois
processos, dois buffers e a soma das duas latências; o loopback custa um
processo e a latência que se pede.

**E O MECANISMO TEM UM DONO SÓ** — `integrations/laco_de_audio.py`, desde
21/09/2026. Este arquivo é a FACHADA daquele dono para o eixo do microfone: ele
diz QUAL nó e com quantos canais; quem guarda o processo, pergunta ao `poll()`
e fecha tudo no `atexit` é o dono. O irmão dele é o `som_do_controle_na_tv`, do
terceiro botão da fileira do som — os dois são *"ligue este nó àquele"*, e
escrever isso duas vezes é como dois donos do mesmo estado divergem.

O QUE ELE NÃO É
===============

**Não é o mudo.** O mudo do microfone é do PLÁSTICO (o botão do controle), e a
tela o reflete no selo «ATIVO»/«DESLIGADO» — decisão dela de 20/09. Este é o
RETORNO: com o microfone mudo não há o que ouvir, e quem recusa antes é o
gesto.

**Não é o volume nem o ganho.** Os dois deslizantes agem no NÓ, e o loopback lê
o nó depois deles — é justamente por isso que ela consegue ajustar ouvindo.
"""

from __future__ import annotations

from hefesto_dualsense4unix.integrations.laco_de_audio import LATENCIA_MS, Lacos

#: **O `alternar` SAIU EM 21/09/2026, e não por descuido.** Ele existia e era
#: elegante — *"liga se estava desligado, desliga se estava ligado"* —, mas
#: NENHUM chamador podia usá-lo: a guarda do microfone mudo mora ENTRE o «está
#: ligado?» e o «ligar» (recusar antes de abrir é o que poupa a ela um botão
#: que promete som e entrega silêncio). Promessa pública sem caminho é resto, e
#: o portão `casa-sabe` a apanhou no mesmo dia em que ela nasceu.
__all__ = [
    "LATENCIA_MS",
    "desligar",
    "desligar_todos",
    "esta_ligado",
    "ligados",
    "ligar",
]

#: A família deste eixo. O nome vai para o nó no PipeWire
#: (`hefesto-retorno-do-mic-<uniq>`), e é o que aparece no `qpwgraph` quando
#: alguém for olhar o grafo: um nome genérico ali faria a próxima pessoa não
#: saber qual botão o criou.
_LACOS = Lacos("retorno-do-mic")


def esta_ligado(uniq: str) -> bool:
    """O retorno deste controle está de pé AGORA?"""
    return _LACOS.esta_ligado(uniq)


def ligados() -> tuple[str, ...]:
    """Os `uniq` com retorno de pé, em ordem estável."""
    return _LACOS.ligados()


def ligar(uniq: str, fonte: str, *, destino: str = "") -> bool:
    """Liga o retorno deste controle. `True` = de pé.

    :param fonte: o nó de captura daquele controle (`hefesto_mic_<hex6>`).
    :param destino: o sink de saída; vazio manda para a saída padrão, que é
        onde ela ouve o jogo — e é a única resposta útil a *"como eu soo"*.

    **MONO, e o mapa vai escrito**: o microfone do DualSense é um canal só, e
    deixar o PipeWire adivinhar o mapa produz um laço estéreo com metade muda.
    """
    if not uniq or not fonte:
        return False
    return _LACOS.ligar(
        uniq, captura=fonte, destino=destino, canais=1, mapa="[ MONO ]")


def desligar(uniq: str) -> bool:
    """Desliga o retorno deste controle. `True` = havia um e ele morreu."""
    return _LACOS.desligar(uniq)


def desligar_todos() -> int:
    """Desliga todos os retornos de voz e devolve quantos eram.

    O `atexit` que fecha isto mora no dono (`laco_de_audio.fechar_tudo`), e
    fecha TODAS as famílias: um `pw-loopback` órfão continua lendo o microfone
    dela depois de a janela fechar, sem nada na tela que o diga.
    """
    return _LACOS.desligar_todos()
