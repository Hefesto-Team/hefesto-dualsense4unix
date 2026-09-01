#!/usr/bin/env python3
"""O QUE O DAEMON ATENDE — lido do `ipc_server.py`, nunca digitado.

POR QUE ISTO EXISTE, e é a peça que faltava para ligar os botões: a tela tem
**202 botões** e o daemon atende **39 métodos**. Sem uma lista conferível, cada
pessoa que ligasse um botão iria procurar o método no código, e a que não achasse
inventaria um nome — que é o defeito mais caro desta casa: uma tela que promete
um ajuste que o produto não faz, e que ninguém descobre porque a ausência de
notícia se lê como sucesso.

A LISTA SAI DO CÓDIGO. `metodos()` lê o dicionário de rotas do `ipc_server.py` e  # (noqa-acento) id
devolve o que está lá HOJE. Um método que sair do daemon some daqui no mesmo
instante, e o `confere()` reprova quem o citava — em vez de a chamada falhar em
silêncio na mão de quem clicou.

CUIDADO MEDIDO, 01/09/2026: o primeiro censo destes métodos usou o padrão
`[a-z_]+\\.[a-z_]+` e achou **30**. Os nove que faltavam têm TRÊS níveis —
`identity.number.set`, `mouse.emulation.set`, `daemon.emulation.suppress`. Um
deles é justamente o que responde "este controle é o Player 2", que a aba
Iluminação precisa. **Uma régua que procura o padrão errado não acha nada e não
reclama.**
"""
from __future__ import annotations

import functools
import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[3]
SERVIDOR = RAIZ / "src/hefesto_dualsense4unix/daemon/ipc_server.py"
HANDLERS = RAIZ / "src/hefesto_dualsense4unix/daemon/ipc_handlers.py"

#: Os dois níveis NÃO bastam: `identity.number.set` tem três, e foi o que o
#: primeiro censo perdeu.
ROTA = re.compile(r'"([a-z_]+(?:\.[a-z_]+)+)"\s*:\s*self\._handle_([a-z_]+)')


@functools.lru_cache(maxsize=1)
def metodos() -> dict[str, str]:
    """`{"led.set": "_handle_led_set", …}` — o que o daemon atende hoje."""
    if not SERVIDOR.exists():
        raise SystemExit(
            f"ERRO: não achei {SERVIDOR}. Ele é a fonte do que o daemon atende — "
            f"sem ele, todo botão que se ligar vira promessa não conferida.")
    return {m: f"_handle_{h}" for m, h in ROTA.findall(SERVIDOR.read_text(encoding="utf-8"))}


@functools.lru_cache(maxsize=128)
def parametros(metodo: str) -> tuple[str, ...]:
    """Os `params.get("…")` que o handler daquele método lê, na ordem.

    É aproximado de propósito — lê o corpo do handler por texto — e serve para
    UMA coisa: quem liga um botão vê que nomes o daemon espera, em vez de
    adivinhar. A prova de que a chamada funciona é o clique chegando, não isto.
    """
    nome = metodos().get(metodo)
    if not nome or not HANDLERS.exists():
        return ()
    texto = HANDLERS.read_text(encoding="utf-8")
    inicio = texto.find(f"def {nome}(")
    if inicio < 0:
        return ()
    # até o próximo `def` no mesmo nível, ou 8000 caracteres — o que vier antes
    fim = texto.find("\n    async def ", inicio + 10)
    if fim < 0:
        fim = texto.find("\n    def ", inicio + 10)
    corpo = texto[inicio:fim if fim > 0 else inicio + 8000]
    return tuple(dict.fromkeys(re.findall(r'params(?:\.get\(|\[)"([a-z_]+)"', corpo)))


def existe(metodo: str) -> bool:
    """O daemon atende este método? Um `False` aqui é um botão sem dono."""
    return metodo in metodos()


def confere(usados: set[str]) -> list[str]:
    """Os métodos citados que o daemon NÃO atende. Lista vazia = todos existem.

    É a régua da ligação: cada gesto declara o método que chama, e um nome
    inventado aparece aqui antes de chegar à mão de quem clica.
    """
    return sorted(m for m in usados if m not in metodos())
