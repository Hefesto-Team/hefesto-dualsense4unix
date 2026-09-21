"""Testar o microfone como o Discord: fala três segundos e ouve de volta.

**A ORDEM É DELA, 20/09/2026, verbatim:**

    "deixa o slicer 2 dele na telka em contra partida aquele glifo antigo de mic
     que servia para ligar o microfone volta a tela mas ele passa a ter o efeito
     do testar microfone do discord, ele reflete os slicers que vão mostrar no
     jogo como o microfone é ouvido e após três segundos de fala capturada de
     audio ele reproduz na tela o seu som falado."

E ela esclareceu qual glifo, quando perguntei:

    "é esse mesmo que cala que eu tava falando"

E confirmou por que o botão de calar pode sair:

    "esse botão segue desativando o microfone, não precisamos dele mais na
     interface pq o botão do
     proprio  # noqa-acento: citação literal dela
     controle já o faz e ele reflete isso"

TRÊS SEGUNDOS DE FALA, NÃO DE RELÓGIO
=====================================

Ela escreveu *"três segundos de fala capturada"*, e a diferença é o ponto: um
contador de relógio devolveria três segundos de silêncio para quem demorou a
falar, e o teste responderia "seu microfone está mudo" sobre um microfone bom.

Então o contador anda só quando há voz — mas o que se GUARDA é o trecho
inteiro, com as pausas. É o que o Discord devolve, e é o que deixa a pessoa
reconhecer a própria fala.

O LIMIAR TEM DONO, e é o medidor de nível
=========================================

:mod:`~hefesto_dualsense4unix.integrations.nivel_do_microfone` já decide o que
é voz e o que é piso de ruído nesta casa, com histerese. Inventar um segundo
limiar aqui criaria a segunda grafia do mesmo fato — o defeito que esta casa
mata por regra. O que muda é só a unidade: lá o `parec` entrega o PICO em
float32; aqui ele entrega o PCM, e o pico de cada bloco sai do próprio PCM.

AS TRÊS TRAVAS QUE ESTA CASA JÁ PAGOU, e que este módulo herda
==============================================================

1. **`--latency-msec=50` explícito.** Sem ele o `parec` acumula e a voz chega
   dois segundos atrasada — mordeu o microfone e a ponte do rádio.
2. **`stdout=PIPE`, nunca `/dev/null`.** Medido em 03/09: com o cano o `parec`
   morre junto com o pai; com `/dev/null` ele sobrevive órfão segurando o
   microfone dela aberto, e um ficou 39 minutos de pé.
3. **`PR_SET_PDEATHSIG`.** Um daemon morto por SIGKILL não deixa gravador vivo.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import structlog

logger = structlog.get_logger(__name__)

#: **O TESTE DE TRÊS SEGUNDOS SAIU — 21/09/2026, e quem o tirou foi ela.**
#:
#:     *"SE EU ATIVAR COM UM CLICK E ELE FICAR VERDE ELE TÁ ATIVADO E SEGUE
#:     ASSIM ATÉ EU DESATIVAR CLICANDO NOVAMENTE E ELE FICANDO CINZA."*
#:
#: O 🎙 gravava três segundos e devolvia — uma resposta, e depois silêncio. Com
#: isso não há como ajustar os dois deslizantes ouvindo: o som some antes de a
#: mão chegar ao trilho. Ela pediu o botão do Discord, e ele é um RETORNO
#: contínuo (`integrations/monitor_do_microfone.py`).
#:
#: Saíram com ele `testar_e_devolver`, `gravar_ate_falar`, `argv_do_gravador`,
#: `argv_do_reprodutor`, `pico_do_bloco`, a classe `Gravacao` e as constantes
#: da gravação. **Nenhuma era decisão medida — eram o mecanismo de um ato que
#: o produto não oferece mais**, e a regra desta casa separa as duas coisas:
#: *"se apagar isto faria alguém repetir um trabalho ou pagar um custo já
#: pago?"*. Aqui não faria: o que se aprendeu sobre o `pactl` ficou, logo
#: abaixo, na única função que sobrou — e é ela que o retorno usa.
__all__ = ["fonte_do_controle"]



def fonte_do_controle(uniq: str, *, saida_pactl: str = "") -> str | None:
    """O nó de captura DAQUELE controle — ``None`` quando não dá para saber.

    Não reimplementa a escolha: delega a
    :func:`~hefesto_dualsense4unix.integrations.fontes_de_captura.escolher_fonte`,
    que é a dona das cinco regras e já sabe que o nó com identidade
    (``hefesto_mic_<hex6>``) vence quando existe. Uma segunda escolha aqui seria
    a segunda grafia do mesmo fato.

    ``None`` é "não sei", e quem chama não deve tratá-lo como "não há
    microfone": sem o servidor de som, sem `pactl` ou sem o controle no ar, a
    pergunta simplesmente não tem resposta.
    """
    from hefesto_dualsense4unix.integrations.fontes_de_captura import (
        escolher_fonte,
        fontes_dualsense,
    )

    saida = saida_pactl
    if not saida:
        if shutil.which("pactl") is None:
            return None
        ambiente = dict(os.environ)
        # SEM `LC_ALL=C` O `pactl` TRADUZ, e o leitor fica cego sobre aparelho
        # de pé. Já custou duas vezes nesta casa.
        ambiente["LC_ALL"] = "C"
        try:
            saida = subprocess.run(  # argv fixo, sem shell
                # **`short` É OBRIGATÓRIO, E A FALTA DELE CALAVA O BOTÃO** —
                # medido na mesa dela em 21/09/2026, com o microfone ATIVO e o
                # nó de pé: `fontes_dualsense` parseia o formato CURTO
                # (`índice\tnome\tdriver\tformato\testado`), e a docstring
                # dela diz isso com todas as letras. Na saída LONGA o
                # `linha.split("\t")` devolve `["", "Name: hefesto_mic_e64203"]`
                # e o nome sai com o rótulo colado — nenhum nó casa, a lista
                # volta com lixo, e o gesto recusa dizendo *"não consegui abrir
                # o microfone deste controle"* sobre um microfone que está lá.
                #
                # Ela clicou o 🎙 e não ouviu nada: `[gesto falhou]
                # 02-controles.html · mic-testar` no `interface.log`, às 01:36.
                ["pactl", "list", "short", "sources"],
                capture_output=True,
                text=True,
                timeout=5,
                env=ambiente,
                check=False,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return None
    if not saida:
        return None
    return escolher_fonte(fontes_dualsense(saida), str(uniq), [str(uniq)])
