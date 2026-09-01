#!/usr/bin/env python3
"""A RÉGUA DOS BOTÕES: o clique chega ao daemon, com o método e os parâmetros.

POR QUE ELA EXISTE, e é a diferença entre ligar botão e fingir que ligou: um
gesto registrado no despachante prova que **existe uma função**. Não prova que
ela chama o daemon, nem que chama o método certo, nem que manda os parâmetros
que aquele método lê. As três coisas falham em silêncio — o daemon recusa, ou
ignora, e a tela não muda; quem clicou conclui que o produto está quebrado.

O QUE ESTA RÉGUA COBRA, e cada item nasceu de um defeito real desta casa:

1. **O método existe no daemon.** `pacotes/daemon.py` lê os 39 do
   `ipc_server.py`. Um nome inventado é o defeito mais caro daqui — uma tela que
   promete um ajuste que o produto não faz.
2. **Os parâmetros são os que o handler lê.** `led.set` lê `rgb`, `brightness` e
   `uniq`; mandar `color` seria aceito pelo socket e ignorado pelo daemon.
3. **O gesto REALMENTE chama.** O `ipc` é injetado, então a régua passa um de
   mentira e cobra a chamada. Um gesto que não chama nada passa por qualquer
   régua que só olhe o registro.
4. **Um clique sem dono é RECUSADO.** Um botão que responde calado quando não há
   quem atenda é a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` em miniatura.

A MORDIDA: troque `ipc("led.set", …)` por `pass` em qualquer gesto — o teste
reprova dizendo que ele não chamou nada. Troque `led.set` por `led.color` — o
teste reprova dizendo que o daemon não atende esse método.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: Um controle de mentira. MAC da faixa sintética da casa — há dois portões de
#: anonimato nesta árvore e eles não perdoam.
UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
         "battery_pct": 95, "lightbar_rgb": [0, 0, 255], "is_primary": True,
         "inputs": {}, "audio": {}, "speaker": {}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "starlight-blue", "mascara": "DualSense"}]

#: O PISO E AS PROVAS MORAM NOS PACOTES, não aqui — e a razão é de processo:
#: com oito abas sendo ligadas em paralelo, este arquivo seria editado oito
#: vezes na mesma região, e seriam oito conflitos. Cada `aNN_*.py` declara
#: `PISO_DA_ABA` (quantos gestos tem) e `PROVAS` (o que cada clique deve
#: chamar), e esta régua os LÊ.
#:
#: Território exclusivo é o que torna o paralelo seguro; foi a mesma razão de o
#: dicionário de gestos ter virado o decorador `@gesto`.


def _pacotes():
    """Os módulos de pacote, com o que cada um declara sobre os seus botões."""
    import importlib

    fora = []
    for arq in sorted((RAIZ /
    "src/hefesto_dualsense4unix/interface/pacotes").glob("a[0-9][0-9]_*.py")):
        fora.append((arq.stem, importlib.import_module(f"pacotes.{arq.stem}")))
    return fora


def _provas():
    """Cada prova declarada, com o nome do pacote que a declarou."""
    for nome, mod in _pacotes():
        for prova in getattr(mod, "PROVAS", ()):
            yield nome, prova


class PonteDeMentira:
    """Um dublê da `pacotes/ponte.py`, que guarda o que foi chamado.

    É o que torna a função de gesto TESTÁVEL: ela não importa o `ipc_bridge`,
    RECEBE a ponte. Uma função que abrisse o socket por dentro só poderia ser
    provada com o daemon no ar — e a régua deixaria de rodar no CI.

    O `__getattr__` responde por QUALQUER nome, e isso é de propósito: o dublê
    não pode virar uma segunda lista das funções da ponte, que envelheceria em
    silêncio. Quem confere se o nome EXISTE de verdade é
    `test_nenhum_gesto_chama_funcao_que_a_ponte_nao_tem`, contra a ponte real.
    """

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            # `identity_number_set` devolve `(ok, motivo)`; os outros, `bool`.
            return (True, None) if nome.endswith("_set") and "identity" in nome else True
        return registrar


@pytest.fixture(scope="module")
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def ctx(pac):
    return pac.Contexto(state={"active_profile": "regua"}, mesa=MESA,
                        conectados=[FALSO], estados={})


def _clique(**extra) -> dict:
    base = {"controle": "p1", "uniq": UNIQ, "texto": "Régua"}
    return {**base, **extra}


# --------------------------------------------------------------------------
# 1. o inventário do daemon
# --------------------------------------------------------------------------
def test_o_inventario_le_os_metodos_do_daemon():
    """Zero métodos é ERRO, não silêncio.

    E o número importa: o primeiro censo usou o padrão `[a-z_]+\\.[a-z_]+` e
    achou 30 — os nove que faltavam têm TRÊS níveis, e um deles é justamente o
    `identity.number.set`, que a aba Iluminação precisa. **Uma régua que procura
    o padrão errado não acha nada e não reclama.**
    """
    from pacotes import daemon

    m = daemon.metodos()
    assert len(m) >= 39, (
        f"o inventário achou {len(m)} métodos e o daemon atende pelo menos 39. "
        f"Se caiu, o padrão do `ROTA` voltou a perder os de três níveis.")
    assert "identity.number.set" in m, "o de três níveis sumiu do censo"
    assert daemon.parametros("led.set") == ("rgb", "brightness", "uniq")


def test_nenhum_pacote_cita_metodo_que_o_daemon_nao_atende(pac):
    """Um nome inventado aparece AQUI, não na mão de quem clica."""
    import importlib

    from pacotes import daemon

    usados: set[str] = set()
    for arq in sorted((RAIZ /
    "src/hefesto_dualsense4unix/interface/pacotes").glob("a[0-9][0-9]_*.py")):
        mod = importlib.import_module(f"pacotes.{arq.stem}")
        usados |= set(getattr(mod, "METODOS", set()))
    inventados = daemon.confere(usados)
    assert inventados == [], (
        f"estes métodos não existem no daemon: {inventados}. "
        f"O `ipc_server.py` é a fonte — se o nome mudou, mude aqui também; "
        f"se o método não existe, o botão NÃO tem dono e deve recusar dizendo.")


# --------------------------------------------------------------------------
# 2. o piso por aba
# --------------------------------------------------------------------------
@pytest.mark.parametrize("nome", [n for n, _ in _pacotes()])
def test_a_aba_tem_o_piso_de_gestos(pac, nome):
    """`PISO_DA_ABA` é declarado no pacote e SÓ SOBE.

    Uma queda não aparece na tela: o clique simplesmente não faz nada.
    """
    import importlib

    mod = importlib.import_module(f"pacotes.{nome}")
    piso = getattr(mod, "PISO_DA_ABA", 0)
    if not piso:
        pytest.skip(f"{nome} ainda não declarou PISO_DA_ABA — aba não ligada")
    pagina = getattr(mod, "PAGINA", "")
    assert pagina, f"{nome} declara PISO_DA_ABA e não declara PAGINA"
    quantos = sum(1 for (p, _) in pac.GESTOS if p == pagina)
    assert quantos >= piso, (
        f"{pagina} tem {quantos} gestos com dono e o piso é {piso}.")


# --------------------------------------------------------------------------
# 3. o gesto CHAMA o daemon — a parte que separa ligar de fingir
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("pacote", "prova"), list(_provas()),
    ids=lambda x: x if isinstance(x, str) else x.get("gesto", "?"))
def test_o_gesto_chama_a_funcao_certa(pac, ctx, pacote, prova):
    """O coração da régua: o clique vira chamadas à ponte, com os argumentos.

    E a ponte é o `app/ipc_bridge.py` — a mesma camada que a GUI estável usa.
    A prova é DECLARADA PELO PACOTE, no `PROVAS`, para que ligar uma aba não
    exija editar este arquivo (e oito abas em paralelo não virem oito
    conflitos).

    A forma de uma prova:

        {"pagina": "04-iluminacao.html", "gesto": "cor",  # (noqa-acento) chave do contrato
         "clique": {"hex": "#FF8000"},
         "chama": [("led_set", ((255, 128, 0),), {"uniq": UNIQ})]}

    `chama` é a lista, NA ORDEM: um botão pode precisar de duas chamadas — o
    "Automático" larga o claim e então pinta a cor padrão, e invertidas o reset
    apagaria a cor que acabou de ir.
    """
    fn = pac.gesto_da_pagina(prova["pagina"], prova["gesto"])  # (noqa-acento) chave do contrato
    assert fn is not None, f"{prova['pagina']}:{prova['gesto']} não tem dono"  # (noqa-acento) id

    p = PonteDeMentira()
    fn(ctx, _clique(**prova.get("clique", {})), p)

    assert p.chamadas, (
        f"{prova['pagina']}:{prova['gesto']} não chamou NADA. É o defeito que "  # (noqa-acento) id
        f"esta régua existe para pegar: o gesto registrado que não faz nada "
        f"passa por qualquer teste de registro, e na tela o clique some sem "
        f"uma linha de erro.")

    esperado = prova["chama"]
    nomes = [c[0] for c in p.chamadas]
    assert nomes == [e[0] for e in esperado], (
        f"{prova['pagina']}:{prova['gesto']} chamou {nomes}, esperava "  # (noqa-acento) id
        f"{[e[0] for e in esperado]}. A ORDEM importa.")
    for (chamou, a, kw), (_, args, kwargs) in zip(p.chamadas, esperado, strict=True):
        assert a == tuple(args), (
            f"{prova['gesto']}: passou {a!r} a {chamou}, esperava {tuple(args)!r}")
        for chave, valor in kwargs.items():
            assert kw.get(chave) == valor, (
                f"{prova['gesto']}: mandou {chave}={kw.get(chave)!r}, "
                f"esperava {valor!r}")



def test_nenhum_gesto_chama_funcao_que_a_ponte_nao_tem():
    """O dublê responde a qualquer nome — quem confere a existência é isto.

    Sem este teste, um gesto podia chamar `p.led_color(...)`, o dublê responder
    alegremente, e a régua acima passar. Na tela, `AttributeError` no primeiro
    clique.
    """
    import importlib

    from pacotes import ponte

    for arq in sorted((RAIZ /
    "src/hefesto_dualsense4unix/interface/pacotes").glob("a[0-9][0-9]_*.py")):
        mod = importlib.import_module(f"pacotes.{arq.stem}")
        for nome in sorted(getattr(mod, "PONTE", set())):
            assert hasattr(ponte, nome), (
                f"{arq.name} chama `ponte.{nome}()` e a ponte não tem essa função. "
                f"Ela expõe o `app/ipc_bridge.py` — se o nome não está lá, o "
                f"produto não faz isso, e o botão precisa RECUSAR dizendo.")



def test_o_automatico_larga_o_claim_e_deixa_a_cor_padrao(pac, ctx):
    """Ordem dela, 01/09/2026: a barra NÃO pode ficar preta.

    *"voltar ao automático nesse caso é deixar o jogo escolher"* — e *"deixa em
    uma das cores default se o jogo não escolher ou não tiver rodando."*

    Largar o claim sozinho deixa a última cor no plástico; se a última foi um
    "Desligar", ela fica apagada e parece defeito. São DUAS chamadas, nesta
    ordem: soltar e então pintar. Invertidas, o `reset` apagaria a cor que
    acabou de ir.

    E A COR NÃO É DIGITADA: sai de `core/led_control.player_slot_color`, a
    mesma paleta que acende as cinco lâmpadas. Um literal aqui seria a segunda
    verdade que esta casa persegue.
    """
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    fn = pac.gesto_da_pagina("04-iluminacao.html", "auto")
    p = PonteDeMentira()
    fn(ctx, _clique(), p)

    nomes = [c[0] for c in p.chamadas]
    assert nomes == ["chamar", "led_set"], (
        f"o 'Automático' fez {nomes}, e devia largar o claim e então pintar. "
        f"Só o reset deixa a barra na última cor — preta, se a última foi um "
        f"Desligar.")
    assert p.chamadas[0][1] == ("lightbar.reset",)
    assert p.chamadas[1][1] == (tuple(player_slot_color(1)),), (
        f"a cor padrão veio {p.chamadas[1][1]!r} e a paleta do produto diz "
        f"{tuple(player_slot_color(1))!r}. Ela não se digita — sai da função.")


def test_o_gesto_recusa_o_clique_sem_controle(pac, ctx):
    """Um "Desligar" sem dono apagaria a barra dos QUATRO em vez de um."""
    fn = pac.gesto_da_pagina("04-iluminacao.html", "apagar")
    p = PonteDeMentira()
    with pytest.raises(ValueError):
        fn(ctx, {"controle": "", "uniq": "", "texto": "Desligar"}, p)
    assert p.chamadas == [], "recusou e chamou o daemon assim mesmo"


def test_um_botao_sem_dono_devolve_none(pac):
    """`None` é o estado honesto — e quem chama tem de RECUSAR DIZENDO."""
    assert pac.gesto_da_pagina("09-sistema.html", "desligar") is None, (
        "`desligar` é `systemctl`, não IPC — se ganhou dono, a régua precisa "
        "saber COMO, porque da tela não se chama systemctl sem o helper.")
