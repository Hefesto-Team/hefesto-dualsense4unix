#!/usr/bin/env python3
"""O CASAMENTO: o que o pacote emite contra o que a página tem onde pintar.

POR QUE ISTO EXISTE, e é o instrumento que faltava em 01/09/2026: o piloto único
abriu a aba Jogar com um pacote de cinco valores e pintou **UM**. Nada acusou —
`querySelector` de um endereço que não existe devolve `null`, a pintura escreve
zero, e zero passa por "nada mudou".

O defeito tinha uma forma só, e ela é estrutural: **os endereços da página e as
chaves do pacote foram escolhidos separadamente.** O pacote da Jogar emite
`mascara`; a página tem `data-campo="identidade"`. As duas palavras dizem a
mesma coisa e nenhuma máquina sabia disso.

O QUE ELE MEDE, por aba:

    página     os `data-campo` que existem no HTML publicado
    pacote     as chaves que a função de pacote emite, já normalizadas
    casam      a interseção — é o teto do que a tela pode pintar
    órfãos     o pacote emite e a página não tem onde pôr  → marcar o gerador
    vazios     a página tem onde e o pacote não manda      → o campo fica `—`

`casam == 0` com pacote não vazio é ERRO, não silêncio. É a régua contra o verde
sobre nada, e é o que `test_o_casamento_das_dez.py` cobra.
"""
from __future__ import annotations

import pathlib
import re
import sys

AQUI = pathlib.Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
for _p in (str(AQUI), str(RAIZ / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import onde  # noqa: E402
import pacotes  # noqa: E402

#: OS TRÊS VOCABULÁRIOS. `data-campo` nas oito abas novas, `data-papel` só na
#: Vibração (28) e `data-hef` só na Perfis (77) — cada um nasceu com o piloto
#: da sua aba. O piloto único aceita os três, e esta régua conta os três.
CAMPO = re.compile(r'data-(?:campo|papel|hef)="([^"]+)"')
CONTROLE = re.compile(r'data-controle="([^"]+)"')

#: Um controle de mentira com a forma do que o daemon devolve. MAC da faixa
#: sintética da casa — há dois portões de anonimato nesta árvore.
FALSO = {
    "uniq": "aa:bb:cc:00:00:01", "player": 1, "connected": True, "is_primary": True,
    "battery_pct": 95, "transport": "usb", "vpad_backend": "uhid",
    "lightbar_rgb": [0, 0, 255], "lightbar_on": True, "lightbar_source": "perfil",
    "inputs": {"lx": 127, "ly": 128, "rx": 127, "ry": 128,
               "l2_raw": 0, "r2_raw": 0, "buttons": []},
    "audio": {"mic_mudo": False, "mic_mudo_desejado": None},
    "speaker": {"volume": 102, "muted": False, "rota": 0},
}

#: A mesa como o desenho a conhece — `pref`, que é o que o `data-controle` traz.
MESA_FALSA = [{"pref": "p1", "jogador": 1, "cor": "starlight-blue",
               "nome": "Starlight Blue", "via": "USB", "uniq": FALSO["uniq"],
               "mascara": "DualSense", "alvo": True}]


def do_html(pagina: str) -> tuple[set[str], set[str]]:
    """Os `data-campo` e os `data-controle` da página PUBLICADA."""
    caminho = onde.pagina(pagina, publicado=True)
    if not caminho.exists():
        raise SystemExit(f"ERRO: {caminho} não existe — o casamento mediria o vazio.")
    doc = caminho.read_text(encoding="utf-8")
    return set(CAMPO.findall(doc)), set(CONTROLE.findall(doc))


#: O estado que a régua usa. Um teste que monte um perfil de mentira o troca —
#: sem perfil o pacote da Gatilhos emite `Desligado` e o da Perfis lista zero,
#: e o piso cairia por falta de DADO, não por regressão.
ESTADO_DA_REGUA = {"active_profile": "acao", "rumble_policy": "balanceado"}


def do_pacote(pagina: str, estado: dict | None = None) -> tuple[set[str], set[str]]:
    """As chaves que o pacote emite: as da mesa e as por controle.

    Roda com o controle de mentira, e não com a mesa vazia: um pacote que só
    pinta por controle emite zero chaves sem controle nenhum, e reprovaria por
    estar certo.
    """
    ctx = pacotes.Contexto(
        state=estado or ESTADO_DA_REGUA,
        mesa=MESA_FALSA, conectados=[FALSO], estados={})
    bruto = pacotes.pacote_da_pagina(pagina, ctx)
    if bruto is None:
        return set(), set()
    pronto = pacotes.normalizar(bruto, {FALSO["uniq"]: "p1"})
    # O CABEÇALHO ENTRA NA CONTA, como entra na pintura: ele é das dez abas.
    for chave, valor in pacotes.topo(ctx).items():
        pronto["mesa"].setdefault(chave, valor)
    por_controle: set[str] = set()
    for campos in pronto["colunas"].values():
        por_controle |= {k for k, v in campos.items() if not isinstance(v, (dict, list))}
    return set(pronto["mesa"]), por_controle


def medir(pagina: str) -> dict:
    campos, controles = do_html(pagina)
    da_mesa, do_controle = do_pacote(pagina)
    emite = da_mesa | do_controle
    return {
        "pagina": pagina,
        "html": campos, "controles": controles,
        "emite": emite,
        "casam": campos & emite,
        "orfaos": emite - campos,
        "vazios": campos - emite,
    }


def main() -> int:
    alvos = sys.argv[1:] or sorted(pacotes.PACOTES)
    print(f"{'aba':22s} {'html':>5s} {'pac':>5s} {'casam':>6s} {'órfãos':>7s} {'vazios':>7s}")
    print("─" * 60)
    ruim = []
    for pagina in alvos:
        m = medir(pagina)
        print(f"{pagina:22s} {len(m['html']):5d} {len(m['emite']):5d} "
              f"{len(m['casam']):6d} {len(m['orfaos']):7d} {len(m['vazios']):7d}")
        if m["emite"] and not m["casam"]:
            ruim.append(pagina)
    if len(alvos) <= 3:
        for pagina in alvos:
            m = medir(pagina)
            print(f"\n── {pagina}")
            print(f"   casam : {sorted(m['casam'])}")
            print(f"   órfãos: {sorted(m['orfaos'])}")
            print(f"   vazios: {sorted(m['vazios'])}")
    if ruim:
        print(f"\nZERO CASAMENTOS (pacote emite e a página não tem onde): {', '.join(ruim)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
