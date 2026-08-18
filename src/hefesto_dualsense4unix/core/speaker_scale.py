"""A régua de volume do alto-falante do DualSense — a conta, e só ela.

Este módulo existe porque a mesma grandeza é falada por TRÊS superfícies: a
barra de leitura e o controle deslizante da aba Status, e o comando
`speaker volume` da linha de comando. Enquanto a conta viveu junto dos widgets,
a linha de comando tinha uma cópia linear dela — e `speaker volume 60` mandava
para o registrador um valor diferente dos 60 % do controle deslizante, no mesmo
hardware, com resultado audível diferente. Duas contas para a mesma grandeza é
a classe de defeito que esta casa mais paga.

Mora em `core/` e não em `app/` por dois motivos, e o segundo é o duro:

1. a curva é propriedade do **DualSense**, não do desenho da tela — quem a
   mediu foi o microfone do controle, não o GTK;
2. `app/widgets/` puxa GTK no import do pacote, e a linha de comando roda em
   servidor sem interface. Importar a régua de lá fazia `speaker volume`
   carregar a interface gráfica inteira para escrever um byte. Há teste
   travando isso (`tests/unit/test_speaker_regua_unica_cli_e_janela.py`).

Python puro de propósito: nenhum import de `gi`, de widget ou de daemon. O
`sensor_widgets` reexporta o que está aqui, para o código de tela continuar
lendo como sempre leu.
"""

from __future__ import annotations

from typing import Final

#: Borda de baixo da faixa útil do registrador de volume do alto-falante, em
#: unidades CRUAS do protocolo (0-255). Até aqui — inclusive — o alto-falante
#: fica MUDO por mais que o número suba.
#:
#: **Número EMPÍRICO, medido no hardware em 01/08/2026**, e não uma constante
#: do protocolo: tom de 1 kHz no sink, o microfone do próprio DualSense como
#: instrumento, Goertzel no bin de 1 kHz, sink e mixer ALSA travados e só o
#: registrador variando. A curva medida (registrador cru -> magnitude)::
#:
#:     0 -> 3,9    13 -> 5,3    26 -> 3,1    38 -> 6,2     <- tudo isto é MUDO
#:     51 -> 35    64 -> 172    76 -> 687                  <- a faixa audível
#:     102 -> 8759  128 -> 8488  255 -> 8793               <- saturado
#:
#: Bate com a documentação de comunidade do report 0x02, que anota o
#: alto-falante usando na prática só a faixa 0x3D-0x64 (61-100) dos 255.
#:
#: Trate os dois números como ESTIMATIVA de um rig, não como verdade do
#: silício: foram medidos num controle, num sink e numa cadeia de áudio. Quem
#: repetir a medição e achar outra borda troca o número aqui — é o único lugar
#: em que ele existe, e as três funções abaixo o seguem juntas.
#:
#: RESSALVA MEDIDA EM UM CANAL SÓ: o mesmo pedido escreve o volume do
#: ALTO-FALANTE e o do FONE (``set_audio_volumes(headphone=..., speaker=...)``
#: em `backend_pydualsense`, a armadilha 3 da SOM-02), e a curva acima foi
#: levantada pelo alto-falante — o microfone do controle não ouve o P2. Se o
#: amplificador do fone usar os 255 de verdade, quem tiver headset plugado
#: perde o curso acima de 102. Ninguém mediu isso ainda; está escrito aqui
#: para que a próxima medição saiba o que procurar, e não para ser presumido
#: em nenhum dos dois sentidos.
_SPEAKER_REG_MUDO_ATE: Final[int] = 38
#: Borda de cima da mesma faixa: daqui para frente o volume não muda mais.
#: Mesma medição, mesma data, mesma ressalva.
_SPEAKER_REG_SATURA_EM: Final[int] = 102


def fracao_do_volume(volume: int) -> float:
    """Volume bruto 0-255 do alto-falante -> fração 0.0-1.0 da barra.

    SOM-03/E2 — a fração NÃO é ``bruto / 255``. A resposta do registrador é
    fortemente não-linear (:data:`_SPEAKER_REG_MUDO_ATE`): abaixo da borda de
    baixo tudo é mudo e acima da de cima tudo é o mesmo volume, de modo que
    ``bruto / 255`` desenhava 50 % para um registrador em 128 que soa
    exatamente igual a 255 — a barra dizia "metade" sobre o volume máximo.

    Aqui a fração é a posição dentro da faixa que de fato AUDIBILIZA, com as
    duas pontas grampeadas. É o que faz a barra de leitura e o controle de
    comando falarem a mesma língua: as três funções deste bloco são a mesma
    conta em três formas, então não existe caminho em que a barra leia uma
    grandeza e o controle mande outra.

    O que NÃO muda: o protocolo. ``speaker.set`` continua recebendo 0-255 cru,
    o perfil continua persistindo 0-255 cru e a chave ``speaker.volume`` do IPC
    continua significando o registrador. O remapeamento é de APRESENTAÇÃO.
    """
    bruto = max(0, min(255, int(volume)))
    if bruto <= _SPEAKER_REG_MUDO_ATE:
        return 0.0
    if bruto >= _SPEAKER_REG_SATURA_EM:
        return 1.0
    faixa = _SPEAKER_REG_SATURA_EM - _SPEAKER_REG_MUDO_ATE
    return (bruto - _SPEAKER_REG_MUDO_ATE) / faixa


def percentual_do_volume(volume: int) -> int:
    """Volume bruto 0-255 -> a porcentagem que a tela mostra (0-100)."""
    return round(fracao_do_volume(volume) * 100)


def volume_do_percentual(percentual: float) -> int:
    """Porcentagem da tela (0-100) -> volume bruto 0-255 do protocolo.

    O INVERSO de :func:`fracao_do_volume`, e mora ao lado dela de propósito: o
    controle deslizante da SOM-02 manda no protocolo o que a barra lê dele, e
    duas contas em dois arquivos acabariam divergindo por um arredondamento —
    o tipo de diferença que só aparece na tela, como "80 %" que volta como
    "79 %" no tique seguinte.

    **0 % é MUDO DE VERDADE, e não o piso da faixa útil**: o zero da tela vira
    zero no registrador, e não :data:`_SPEAKER_REG_MUDO_ATE`. Os dois soam
    igual (silêncio), mas só um deles é o valor que o resto do sistema
    reconhece como desligado — e é o único ponto do curso em que a conta não é
    a régua da faixa útil.

    Qualquer porcentagem ACIMA de zero sai pelo menos um passo acima da borda
    de mudo: pedir 1 % e receber silêncio seria o defeito de novo, uma ponta do
    curso que não faz nada.

    O resultado é sempre um inteiro 0-255 EXPLÍCITO: ``speaker.set`` sem
    ``volume`` toma a posse e manda ZERO (armadilha 1 da SOM-02, medida), então
    não existe caminho em que esta função devolva "não mexer".

    LIMITE DECLARADO: a faixa útil tem 64 passos de registrador para 100 pontos
    percentuais de tela, então a volta ``pct -> bruto -> pct`` pode andar um
    ponto (51 % vira 71 cru e relê 52 %). É a resolução do registrador
    aparecendo, não uma discordância: barra, rótulo e controle passam TODOS por
    estas funções e saltam juntos para o mesmo número.
    """
    pct = max(0.0, min(100.0, float(percentual)))
    if pct <= 0.0:
        return 0
    faixa = _SPEAKER_REG_SATURA_EM - _SPEAKER_REG_MUDO_ATE
    passo = max(1, round(pct * faixa / 100.0))
    return max(0, min(255, _SPEAKER_REG_MUDO_ATE + passo))



__all__ = [
    "fracao_do_volume",
    "percentual_do_volume",
    "volume_do_percentual",
]
