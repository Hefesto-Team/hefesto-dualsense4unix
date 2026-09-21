"""O GANHO DE ENTRADA DO MICROFONE — leitor, escritor e a placa onde ele vive.

**POR QUE ESTE MÓDULO EXISTE, e a razão é a ordem dela de 21/09/2026:**

    *"E LEMBRANDO OS DOIS SLICERS REFLETEM TANTO LÁ QUANTO NO JOGO E ISSO DEVE
    SER SALVO."*

Os dois deslizantes são o VOLUME e o GANHO. O volume já viajava no perfil desde
MIC-VOLUME-01; o ganho nasceu em 20/09 com leitor, barra, número e razão — e
morava inteiro dentro de uma aba da interface. Um valor que só a tela sabe
escrever é um valor que o perfil não pode guardar, e foi por isso que ele saiu
declarado como dívida em vez de gravado.

**A MUDANÇA É DE CAMADA, NÃO DE COMPORTAMENTO.** As funções abaixo vieram
verbatim de `interface/pacotes/a02_controles.py`, com as razões que já
carregavam. O que mudou é que agora `profiles/manager.py` pode chamá-las sem
importar uma aba da interface — a dependência que não pode existir.

**O DONO CONTINUA SENDO O APARELHO.** Quem responde quanto o ganho ficou é o
`amixer`, nunca o número que a tela escreveu nem o que o perfil guardou. É a
regra desta casa para valor com dono, e aqui ela é literal.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from hefesto_dualsense4unix.app import audio_saida

#: O ELEMENTO DE GANHO NÃO SE DIGITA, e esta constante não é o nome dele: é o
#: que o `amixer scontents` chama de CAPACIDADE de volume de captura. Quem
#: escolhe o elemento é a mesma regra do decisor do `doctor`
#: (`_dualsense_porta_de_captura_status`): o primeiro controle simples que tem
#: `cvolume` **e** canais de captura. Cravar `Headset` aqui faria esta aba
#: responder sobre o DualSense e calar em qualquer outro aparelho — e o produto
#: é para qualquer usuário.
_CAPACIDADE_DE_GANHO = "cvolume"

#: O default do ganho, ESCRITO E JUSTIFICADO — §6.3 da sprint, pela ordem dela
#: de 17/09 (*nenhum campo nasce sem opinião*).
#:
#: **É o topo da faixa**, que é o que o firmware entrega: o `Headset Capture
#: Volume` vive em 101/101 = +48,00 dB desde que alguém o mediu. A razão de não
#: baixar é dela e está medida — *o único microfone dela é o do DualSense* —, e
#: baixar por conta própria faria o microfone dela ficar MAIS BAIXO do que está
#: hoje, numa sprint cujo nome é «ter dono», não «mudar o som». O que muda é que
#: a partir daqui o valor é ESCOLHA, e não sobra de firmware.
GANHO_PADRAO_PCT = 100

def _nome_do_scontrol(crua: str) -> str:
    """`'Headset',0` -> `Headset,0` — o que o `amixer sset` aceita em argv."""
    achado = re.match(r"^\s*'(.*)',(\d+)\s*$", crua)
    return f"{achado.group(1)},{achado.group(2)}" if achado else crua.strip()


def ganho_do_scontents(texto: str) -> tuple[int, float] | None:
    """`(por cento, dB)` do elemento de ganho de captura, ou `None`.

    Corpo único com :func:`elemento_e_ganho_do_scontents`, que responde a
    mesma pergunta mais o NOME do elemento. Dois parsers da mesma saída é como
    o leitor e o escritor do mesmo valor começam a escolher elementos
    diferentes na mesma placa.
    """
    achado = elemento_e_ganho_do_scontents(texto)
    return None if achado is None else (achado[1], achado[2])


def elemento_e_ganho_do_scontents(texto: str) -> tuple[str, int, float] | None:
    """`(elemento, por cento, dB)` — o NOME é o que o escritor precisa.

    Lê a saída de `amixer -c N scontents` e devolve o primeiro controle simples
    que tem :data:`_CAPACIDADE_DE_GANHO` e canais de captura — a MESMA regra do
    decisor do `doctor`, para as duas não divergirem sobre qual elemento é o
    ganho desta placa.

    PURA de propósito: quem roda o comando é :func:`_ler_o_ganho`. É assim que a
    régua pode alimentá-la com a gravação de `tests/fixtures/mic-cabo/` em vez
    de conversar com o servidor de som da máquina que roda a suíte.

    `None` = o texto não tem elemento de ganho de captura. Chutar zero pintaria
    «ganho no mínimo» sobre uma placa que não tem ganho nenhum.
    """
    tem_ganho = False
    nome = ""
    for linha in (texto or "").splitlines():
        crua = linha.strip()
        if crua.startswith("Simple mixer control "):
            tem_ganho = False
            # `Simple mixer control 'Headset',0` -> `Headset,0`.
            #
            # **AS ASPAS SÃO DO `scontents`, NÃO DO NOME**, e passá-las adiante
            # é um defeito silencioso: o `sset` recebe argv, não shell, então
            # `'Headset',0` chegaria com as aspas literais e o amixer
            # responderia *"Unable to find simple control"*. O clique falharia
            # com a barra pintada certa.
            #
            # **E O ÍNDICE FICA**, que é a outra metade: `Headset` sem o `,0`
            # escreve no elemento de índice 0 de uma placa cujo ganho pode ser
            # o de índice 1 — escrita plausível no lugar errado, que é pior do
            # que erro.
            nome = _nome_do_scontrol(crua[len("Simple mixer control "):])
            continue
        if crua.startswith("Capabilities:"):
            tem_ganho = _CAPACIDADE_DE_GANHO in crua
            continue
        if not tem_ganho or "Capture " not in crua:
            continue
        # `Mono: Capture 101 [100%] [48.00dB] [on]` — o por cento é a POSIÇÃO na
        # faixa (é o que a barra pinta) e o dB é o que o aparelho amplifica (é o
        # que o número diz). Os dois saem da MESMA linha porque são o mesmo
        # fato: lê-los em passagens separadas é como dois campos do mesmo bloco
        # começam a discordar.
        achado = re.search(r"\[(\d+)%\].*?\[(-?\d+(?:\.\d+)?)dB\]", crua)
        if achado:
            return (nome, max(0, min(100, int(achado.group(1)))),
                    float(achado.group(2)))
    return None


def placa_de_cada_fonte(lista_de_sources: str) -> dict[str, str]:
    """`{nome_do_no: placa_alsa}` da saída de `pactl list sources`.

    PURA de propósito, como o :func:`_ganho_do_scontents`: quem roda o comando
    é quem chama. Ela existe para que o LEITOR do ganho (a thread da camada 1,
    que pergunta pela mesa inteira numa leitura só) e o ESCRITOR (o clique, que
    pergunta por um controle) resolvam a placa pelo MESMO caminho — dois
    resolvedores escreveriam o ganho numa placa e o leriam de outra, e a tela
    diria que o arrasto não pegou.
    """
    placa: dict[str, str] = {}
    atual = ""
    for linha in (lista_de_sources or "").splitlines():
        crua = linha.strip()
        if crua.startswith("Name: "):
            atual = crua[6:]
        elif atual and crua.startswith("alsa.card = "):
            placa[atual] = crua.split("=", 1)[1].strip().strip('"')
    return placa


def placa_do_controle(uniq: str, na_mesa: Sequence[str]) -> str:
    """A placa ALSA deste controle, ou `""` quando não há.

    `""` é resposta honesta em três casos, e nenhum deles é erro: o controle
    está no RÁDIO (o microfone chega como som já digitalizado, sem placa onde
    esse ganho exista — medido em 15/08: a placa segue o transporte), o `pactl`
    não respondeu, ou o nó nativo deste controle não casou com placa nenhuma.

    A PERGUNTA É AO NÓ QUE O KERNEL PUBLICA, não ao que o produto elegeu — a
    mesma cicatriz de 20/09 que o :func:`_ler_o_ganho` documenta: com a ponte
    de pé, `canal_fonte` devolve `hefesto_mic_<hex6>` para os quatro, e aquele
    nó não tem placa ALSA nenhuma.
    """
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone

    if not uniq:
        return ""
    mesa = [u for u in na_mesa if u] or [uniq]
    try:
        no = eleicao_de_microfone.fonte_nativa_do_controle(uniq, mesa)
    except Exception:
        return ""
    if not no:
        return ""
    try:
        lista = audio_saida.rodar_leitura(["pactl", "list", "sources"])
    except Exception:
        return ""
    return placa_de_cada_fonte(lista).get(no, "")


def definir(
    uniq: str, por_cento: int, na_mesa: Sequence[str]
) -> tuple[int, float] | None:
    """Escreve o ganho de entrada no APARELHO e devolve o que ele ficou.

    **ESTE É O ESCRITOR QUE FALTAVA.** O ganho nasceu em 20/09 com leitor,
    barra, número, cinza e razão — e nada que o mudasse. A tela mostrava o
    valor e não havia onde pegá-lo: *"o efeito pronto e sem escolha"*, que é o
    defeito-mãe desta casa, desta vez do lado de fora.

    **O RETORNO É A RELEITURA, NÃO O PEDIDO**, e é a regra da casa para valor
    com dono: o `amixer` arredonda para o passo da placa (a do DualSense anda
    de 1 em 1 dentro de 0-101, e nem toda placa é assim), então devolver o que
    se pediu faria a tela publicar um número que o aparelho não tem. Quem
    responde quanto o ganho ficou é o ganho.

    `None` = não consegui escrever nem reler: sem placa (o rádio), sem
    `amixer`, ou o elemento de ganho não existe nesta placa. Quem chama
    transforma isso em recusa com razão — nunca em silêncio, e nunca num
    número inventado.
    """
    placa = placa_do_controle(uniq, na_mesa)
    if not placa:
        return None
    try:
        antes = elemento_e_ganho_do_scontents(
            audio_saida.rodar_leitura(["amixer", "-c", placa, "scontents"]))
    except Exception:
        return None
    if antes is None:
        return None
    elemento = antes[0]
    alvo = max(0, min(100, int(por_cento)))
    try:
        # `sset <elemento> <N>%` fala a MESMA escala que a barra pinta: o por
        # cento é a posição na faixa, e é o que o `scontents` devolve entre
        # colchetes. Mandar dB daria um segundo vocabulário para o mesmo eixo,
        # e a conversão seria nossa — a placa já a tem.
        audio_saida.rodar_leitura(
            ["amixer", "-c", placa, "sset", elemento, f"{alvo}%"])
        depois = elemento_e_ganho_do_scontents(
            audio_saida.rodar_leitura(["amixer", "-c", placa, "scontents"]))
    except Exception:
        return None
    if depois is None:
        return None
    # O CACHE DA TELA NÃO MORA AQUI. Quem chama recebe a releitura e lembra
    # dela se precisar — a aba precisa (senão o deslizante «pula para trás» nos
    # 2 s entre duas voltas da thread); o perfil, não. Guardar o cache da
    # interface dentro do módulo de sistema faria o `manager` aquecer uma
    # lembrança que ninguém lê.
    return (depois[1], depois[2])
