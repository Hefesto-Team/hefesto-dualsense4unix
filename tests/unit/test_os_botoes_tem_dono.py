#!/usr/bin/env python3
"""A RÉGUA DOS BOTÕES: o clique chega ao daemon, com o método e os parâmetros."""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
         "battery_pct": 95, "lightbar_rgb": [0, 0, 255], "is_primary": True,
         "inputs": {}, "audio": {"mic_mudo": False},
         "speaker": {"volume": 100, "muted": False}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "starlight-blue", "mascara": "DualSense"}]


from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

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
    """Um dublê da `pacotes/ponte.py`, que guarda o que foi chamado."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            # `identity_number_set` e a família `*_detalhado` devolvem
            duas = (nome.endswith("_set") and "identity" in nome) or nome.endswith(
                "_detalhado"
            )
            return (True, None) if duas else True
        return registrar


@pytest.fixture(autouse=True)
def _perfil_ativo_no_disco() -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    profiles_dir().mkdir(parents=True, exist_ok=True)
    for nome in ("regua", "Bancada"):
        if not (profiles_dir() / f"{nome.lower()}.json").exists():
            loader.save_profile(Profile(name=nome, match=MatchManual()),
                                origem="regua")


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


def test_o_inventario_le_os_metodos_do_daemon():
    """Zero métodos é ERRO, não silêncio."""
    from tests.unit import inventario_do_daemon as daemon

    m = daemon.metodos()
    assert len(m) >= 39, (
        f"o inventário achou {len(m)} métodos e o daemon atende pelo menos 39. "
        f"Se caiu, o padrão do `ROTA` voltou a perder os de três níveis.")
    assert "identity.number.set" in m, "o de três níveis sumiu do censo"
    assert daemon.parametros("led.set") == ("rgb", "brightness", "uniq")


def test_nenhum_pacote_cita_metodo_que_o_daemon_nao_atende(pac):
    """Um nome inventado aparece AQUI, não na mão de quem clica."""
    import importlib

    from tests.unit import inventario_do_daemon as daemon

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


@pytest.mark.parametrize("nome", [n for n, _ in _pacotes()])
def test_a_aba_tem_o_piso_de_gestos(pac, nome):
    """`PISO_DA_ABA` é declarado no pacote e SÓ SOBE."""
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
    """O dublê responde a qualquer nome — quem confere a existência é isto."""
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


# `profile.switch` (`clear_manual_trigger_active()` sem argumento), que é o que


def test_o_gesto_recusa_o_clique_sem_controle(pac, ctx):
    """Um "Desligar" sem dono apagaria a barra dos QUATRO em vez de um."""
    fn = pac.gesto_da_pagina("04-iluminacao.html", "apagar")
    p = PonteDeMentira()
    with pytest.raises(ValueError):
        fn(ctx, {"controle": "", "uniq": "", "texto": "Desligar"}, p)
    assert p.chamadas == [], "recusou e chamou o daemon assim mesmo"


def test_um_botao_sem_dono_devolve_none(pac):
    """`None` é o estado honesto — e quem chama tem de RECUSAR DIZENDO."""
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    sem_motor = sorted(a09_sistema.SEM_MOTOR)
    if not sem_motor:
        pytest.skip("a aba Sistema não tem mais botão sem motor — apague esta régua")
    for nome in sem_motor:
        assert pac.gesto_da_pagina(a09_sistema.PAGINA, nome) is None, (
            f"`{nome}` está declarado em `SEM_MOTOR` e TEM dono. Se o ato saiu "
            "do handler da janela velha, tire-o da declaração.")
