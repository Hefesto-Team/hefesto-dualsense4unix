"""O GANHO DE ENTRADA DO MICROFONE — leitor, escritor e a placa onde ele vive."""

from __future__ import annotations

import re
from collections.abc import Sequence

from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.integrations import porta_do_som

#: responder sobre o DualSense e calar em qualquer outro aparelho — e o produto
_CAPACIDADE_DE_GANHO = "cvolume"

#: **É o topo da faixa**, que é o que o firmware entrega: o `Headset Capture Volume`
#: vive em 101/101 = +48,00 dB. A razão de não baixar está medida: o único microfone
#: do usuário é o do DualSense, e baixar por conta própria faria o microfone ficar
#: MAIS BAIXO do que está hoje, numa sprint cujo nome é «ter dono», não «mudar o som».
#: O que muda é que, a partir daqui, o valor é ESCOLHA, e não sobra de firmware.
GANHO_PADRAO_PCT = 100

def _nome_do_scontrol(crua: str) -> str:
    """`'Headset',0` -> `Headset,0` — o que o `amixer sset` aceita em argv."""
    achado = re.match(r"^\s*'(.*)',(\d+)\s*$", crua)
    return f"{achado.group(1)},{achado.group(2)}" if achado else crua.strip()


def ganho_do_scontents(texto: str) -> tuple[int, float] | None:
    """`(por cento, dB)` do elemento de ganho de captura, ou `None`."""
    achado = elemento_e_ganho_do_scontents(texto)
    return None if achado is None else (achado[1], achado[2])


def elemento_e_ganho_do_scontents(texto: str) -> tuple[str, int, float] | None:
    """`(elemento, por cento, dB)` — o NOME é o que o escritor precisa."""
    tem_ganho = False
    nome = ""
    for linha in (texto or "").splitlines():
        crua = linha.strip()
        if crua.startswith("Simple mixer control "):
            tem_ganho = False
            nome = _nome_do_scontrol(crua[len("Simple mixer control "):])
            continue
        if crua.startswith("Capabilities:"):
            tem_ganho = _CAPACIDADE_DE_GANHO in crua
            continue
        if not tem_ganho or "Capture " not in crua:
            continue
        achado = re.search(r"\[(\d+)%\].*?\[(-?\d+(?:\.\d+)?)dB\]", crua)
        if achado:
            return (nome, max(0, min(100, int(achado.group(1)))),
                    float(achado.group(2)))
    return None


def placa_de_cada_fonte(lista_de_sources: str) -> dict[str, str]:
    """`{nome_do_no: placa_alsa}` da saída de `pactl --format=json list sources`."""
    return {
        no.nome: no.propriedades["alsa.card"]
        for no in porta_do_som.nos_do_texto(lista_de_sources or "")
        if no.nome and no.propriedades.get("alsa.card")
    }


def placa_do_controle(uniq: str, na_mesa: Sequence[str]) -> str:
    """A placa ALSA deste controle, ou `""` quando não há."""
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
        placas = porta_do_som.placa_de_cada_fonte(audio_saida.rodar_leitura)
    except Exception:
        return ""
    return (placas or {}).get(no, "")


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
        audio_saida.rodar_leitura(
            ["amixer", "-c", placa, "sset", elemento, f"{alvo}%"])
        depois = elemento_e_ganho_do_scontents(
            audio_saida.rodar_leitura(["amixer", "-c", placa, "scontents"]))
    except Exception:
        return None
    if depois is None:
        return None
    return (depois[1], depois[2])
