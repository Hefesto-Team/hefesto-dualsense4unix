#!/usr/bin/env python3
"""O ENDEREÇO DE CADA VALOR DA TELA, lido do `docs/data/mapa-controles.csv`.

ELA APONTOU A FONTE, em 01/09/2026: *"olhando o arquivo de specs.html — lá já
temos até a parte do BT mapeada por agentes."* O `specs.html` é a página que se
abre; o CSV é o dado que a gera, e é dele que se lê.

O QUE O CSV RESPONDE, e é exatamente o que falta a um valor de tela para deixar
de ser enfeite (308 linhas, uma por peça × controle):

    cabo_aciona / radio_aciona     o Hefesto MEXE nisso naquele transporte?
    cabo_canal  / radio_canal      por onde (hidraw, uhid, evdev, sysfs…)
    cabo_report_id / radio_...     qual relatório HID
    cabo_comando   / radio_...     o comando, quando há
    estado_hoje                    a ressalva medida, quando existe

POR QUE ISTO É UM MÓDULO E NÃO UM COMENTÁRIO: porque o valor da tela passa a
CITAR a linha, e a citação é conferível. O defeito mais caro desta casa é o
endereço inventado — uma tela que promete um ajuste que o produto não faz, e que
ninguém descobre porque a ausência de notícia se lê como sucesso.

A REGRA, e ela é o motivo deste arquivo existir:

    Todo valor que a tela AFIRMA tem de ter linha aqui, ou dizer que não tem
    dono. `sem_dono()` é como se diz a segunda coisa — e ela aparece na tela.
"""
from __future__ import annotations

import csv
import functools
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[3]
CSV = RAIZ / "docs/data/mapa-controles.csv"


@functools.lru_cache(maxsize=1)
def _linhas() -> list[dict]:
    if not CSV.exists():
        raise SystemExit(f"ERRO: não achei {CSV.relative_to(RAIZ)}. Ele é a fonte "
                         f"dos endereços — sem ele, todo valor da tela vira chute.")
    with CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


@functools.lru_cache(maxsize=512)
def canal(chave: str, transporte: str = "cabo") -> dict | None:
    """O que o mapa diz sobre uma peça naquele transporte.

    Devolve `None` quando a chave não existe — e quem chama TEM de tratar. Um
    `None` engolido é o endereço inventado voltando pela porta dos fundos.
    """
    t = "radio" if transporte.upper() in {"BT", "RADIO", "RÁDIO"} else "cabo"
    for l in _linhas():
        if l["chave"] == chave:
            return {
                "chave": chave, "rotulo": l["rotulo"], "familia": l["familia"],
                "aciona": (l[f"{t}_aciona"] or "").strip().lower() in {"sim", "true", "1"},
                "aceita": (l[f"{t}_aceita"] or "").strip().lower() in {"sim", "true", "1"},
                "canal": l[f"{t}_canal"] or "",
                "report_id": l[f"{t}_report_id"] or "",
                "comando": l[f"{t}_comando"] or "",
                "por_que_nao": l[f"{t}_por_que_nao_aciona"] or "",
                "estado_hoje": l["estado_hoje"] or "",
                "transporte": t,
            }
    return None


@functools.lru_cache(maxsize=64)
def da_familia(familia: str) -> tuple[str, ...]:
    """As chaves de uma família — `luz`, `gatilho`, `vibracao`, `audio`…

    É por aqui que uma aba pergunta "o que existe no meu assunto", em vez de
    alguém digitar a lista e ela envelhecer calada.
    """
    return tuple(dict.fromkeys(l["chave"] for l in _linhas() if l["familia"] == familia))


def sem_dono(oque: str) -> dict:
    """O valor que a tela mostra mas o produto ainda não faz.

    ELE APARECE NA TELA, e é decisão desta casa desde 30/08: *botão sem dono no
    produto não vai para a tela como se funcionasse*. O que ele NÃO pode é
    aparecer calado — quem lê precisa saber que aquilo ainda não tem quem atenda.
    """
    return {"sem_dono": True, "oque": oque}


def confere(chaves: dict[str, str], transporte: str = "cabo") -> list[str]:
    """As chaves que NÃO existem no mapa. Lista vazia = todas têm dono.

    Usada pela régua de cada aba: ela roda sobre o que a aba diz que pinta, e
    reprova antes de a tela ir ao ar. **Uma chave a mais aqui é um endereço
    inventado**, e é o defeito que o `check_paridade_transporte.py` persegue no
    resto da casa.
    """
    return [k for k in chaves if canal(k, transporte) is None]
