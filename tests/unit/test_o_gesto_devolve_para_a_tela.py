#!/usr/bin/env python3
"""A RÉGUA DO CAMINHO DE VOLTA: o gesto que MOSTRA escreve mesmo na página.

POR QUE ELA EXISTE, e a data é 01/09/2026: até este dia um gesto devolvia
`None` e o piloto descartava. Isso deixava sem dono toda a espécie de botão cuja
promessa é MOSTRAR — "Ver os plugins carregados" e "Ver detalhes", da aba
Sistema —, e o próprio pacote registrava a razão:

    "o gesto do piloto devolve `None` (`hefesto_vivo.py:_gesto`), e não há por
     onde escrever a lista na página. Um gesto que chamasse `plugin.list` e
     jogasse o resultado fora seria o botão 'Ver os plugins carregados' que não
     mostra plugin nenhum — o botão que responde calado, exatamente."

O caminho de volta nasceu, e esta régua cobra as TRÊS coisas que fazem dele um
caminho de verdade. Cada uma é um jeito diferente de ele mentir:

1. **O ENDEREÇO EXISTE NA PÁGINA PUBLICADA.** É o modo de falha desta casa que
   mais deu verde sobre nada: a pintura escrevia zero valores e ninguém via, por
   um `data-campo` que a página não tinha. Um gesto que devolve
   `{"mesa": {"registro-txt": …}}` roda sem levantar, o piloto pinta zero, e a
   tela fica com o texto do mockup — que PARECE um registro de verdade.
2. **O CONTEÚDO É O DO PRODUTO.** A lista tem os nomes que o daemon respondeu; o
   registro tem as linhas que o `journalctl` deu.
3. **O PILOTO REALMENTE PINTA.** `_deu_certo` com um dicionário na mão manda
   `pintar(...)` para a página; com `None`, não manda nada.

A MORDIDA: troque o `return {...}` de `ver_plugins` por `return None` — o item 3
reprova dizendo que nada foi para a tela. Troque `REGISTRO` por qualquer outro
nome — o item 1 reprova dizendo que a página não tem esse endereço.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src/hefesto_dualsense4unix/interface"
sys.path.insert(0, str(INTERFACE))

#: O controle de mentira, na faixa sintética da casa — há dois portões de
#: anonimato nesta árvore e eles não perdoam um MAC real.
UNIQ = "aa:bb:cc:00:00:01"


class PonteDeMentira:
    """Um dublê da ponte que RESPONDE o que o daemon responderia.

    Ele difere do dublê da `test_os_botoes_tem_dono` de propósito: lá o que
    importa é QUAL função foi chamada, e um `True` para tudo basta. Aqui o que
    se mede é o que o gesto FAZ com a resposta — e um `True` no lugar da lista
    de plugins provaria só que o gesto sabe ignorar o daemon.
    """

    def __init__(self, resposta=None, aceita: bool = True) -> None:
        self.resposta = resposta
        self.aceita = aceita
        self.chamadas: list[str] = []

    def chamar(self, metodo: str, **_):
        self.chamadas.append(metodo)
        return self.aceita

    def resultado(self, metodo: str, **_):
        self.chamadas.append(metodo)
        return self.resposta


@pytest.fixture(scope="module")
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def ctx(pac):
    return pac.Contexto(state={"active_profile": "regua"}, mesa=[], conectados=[],
                        estados={})


def _enderecos_da_carga(carga: dict) -> list[str]:
    """Todo endereço que a carga pede para pintar, dos dois níveis."""
    fora = list((carga.get("mesa") or {}).keys())
    for campos in (carga.get("colunas") or {}).values():
        fora.extend(campos.keys())
    return fora


# --------------------------------------------------------------------------
# 1. o endereço existe na página que o produto renderiza
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("gesto", "resposta"),
    [("ver-plugins", [{"name": "exemplo", "disabled": False, "profile_match": "*"}]),
     ("ver-detalhes", None)])
def test_o_endereco_que_o_gesto_devolve_existe_na_pagina(pac, ctx, gesto, resposta):
    """Devolver endereço que a página não tem é pintar ZERO, calado.

    E o silêncio é o problema inteiro: o gesto roda, o piloto imprime
    "aplicado", e a tela continua com o texto de exemplo do mockup — que parece
    um registro técnico de verdade. Ninguém que clicou tem como saber.
    """
    from hefesto_dualsense4unix.interface import onde

    fn = pac.gesto_da_pagina("09-sistema.html", gesto)
    assert fn is not None, f"09-sistema.html:{gesto} não tem dono"

    carga = fn(ctx, {"uniq": UNIQ}, PonteDeMentira(resposta=resposta))
    assert isinstance(carga, dict) and carga, (
        f"{gesto} devolveu {carga!r}. Um botão que promete MOSTRAR e devolve "
        f"nada é o botão que responde calado.")

    html = (onde.PUBLICADO / "09-sistema.html").read_text(encoding="utf-8")
    for endereco in _enderecos_da_carga(carga):
        assert f'data-campo="{endereco}"' in html, (
            f"{gesto} devolve o endereço {endereco!r} e a página publicada não "
            f"o tem. A pintura escreveria ZERO valores sem uma linha de erro — "
            f"marque-o no gerador `interface/aba09.py` e publique.")


# --------------------------------------------------------------------------
# 2. o conteúdo é o do produto, e não uma frase nossa
# --------------------------------------------------------------------------
def test_ver_plugins_mostra_os_nomes_que_o_daemon_respondeu(pac, ctx):
    """A lista da tela é a do `plugin.list`, com o estado de cada um."""
    fn = pac.gesto_da_pagina("09-sistema.html", "ver-plugins")
    p = PonteDeMentira(resposta=[
        {"name": "turbo", "disabled": False, "profile_match": "Mortal Kombat"},
        {"name": "eco", "disabled": True, "profile_match": None},
    ])
    texto = fn(ctx, {}, p)["mesa"]["registro-texto"]

    assert p.chamadas == ["plugin.reload", "plugin.list"], (
        f"chamou {p.chamadas}. RELER e então LISTAR: invertidas, a tela mostra "
        f"o estado de antes de reler.")
    assert "turbo" in texto and "eco" in texto, f"os nomes não chegaram: {texto!r}"
    assert "Mortal Kombat" in texto, "o perfil a que o plugin se casa não chegou"
    assert "desligado" in texto, "o plugin desligado apareceu como ligado"
    assert "2 plugin" in texto, f"a contagem não bate com a resposta: {texto!r}"


def test_ver_plugins_sem_plugin_diz_qual_dos_dois_silencios_e(pac, ctx):
    """`[]` é ambíguo no daemon, e a tela tem de desfazer a ambiguidade.

    `_handle_plugin_list` devolve `[]` tanto com o subsistema DESLIGADO quanto
    com ele ligado e o diretório vazio (`ipc_handlers.py:5370-5373`). Um
    "Nenhum plugin carregado" seco faria as duas parecerem a mesma coisa — e
    quem tem plugin no disco concluiria que o arquivo dele está errado.
    """
    fn = pac.gesto_da_pagina("09-sistema.html", "ver-plugins")

    desligado = fn(ctx, {}, PonteDeMentira(resposta=[], aceita=False))
    ligado_vazio = fn(ctx, {}, PonteDeMentira(resposta=[], aceita=True))

    a = desligado["mesa"]["registro-texto"]
    b = ligado_vazio["mesa"]["registro-texto"]
    assert a != b, ("os dois silêncios do daemon chegaram à tela como a MESMA "
                    f"frase: {a!r}")
    assert "não estão habilitados" in a, a
    assert "não há nenhum no diretório" in b, b


def test_ver_detalhes_leva_o_journal_para_o_painel(pac, ctx, monkeypatch):
    """As linhas do painel são as do `journalctl`, e a unit tem dono.

    A UNIT É O PONTO: ela foi digitada uma vez neste pacote, com o nome
    `-dev` que a purga de 01/09 aposentou, e a tela passou a afirmar
    `not-found` sobre uma unit `enabled`. Aqui a régua cobra que o comando
    pergunte pela unit que `utils/identidade` diz ser a desta casa.
    """
    import subprocess

    from hefesto_dualsense4unix.utils import identidade

    visto: dict[str, list[str]] = {}

    class Saida:
        stdout = "set 01 15:03:23 daemon pronto\nset 01 15:03:24 uinput ok"
        stderr = ""

    def falso_run(argv, **_):
        visto["argv"] = list(argv)
        return Saida()

    monkeypatch.setattr(subprocess, "run", falso_run)
    fn = pac.gesto_da_pagina("09-sistema.html", "ver-detalhes")
    texto = fn(ctx, {}, PonteDeMentira())["mesa"]["registro-texto"]

    assert "uinput ok" in texto, f"o journal não chegou ao painel: {texto!r}"
    assert identidade.atual().unit_daemon in visto["argv"], (
        f"perguntou por {visto['argv']!r}. A unit tem dono em `utils/identidade` "
        f"— digitá-la é como a aba passou a mentir sobre o autostart.")
    assert "80" in visto["argv"], "o botão promete as últimas 80 linhas"


def test_ver_detalhes_repassa_o_motivo_do_journalctl(pac, ctx, monkeypatch):
    """Sem linhas, a tela mostra o que o `journalctl` disse — não uma frase nossa.

    Inventar "sem linhas" aqui apagaria a única pista de quem clicou: unit que
    não existe, falta de permissão e journal vazio dizem coisas diferentes.
    """
    import subprocess

    class Saida:
        stdout = ""
        stderr = "Failed to add match: Invalid argument"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Saida())
    fn = pac.gesto_da_pagina("09-sistema.html", "ver-detalhes")
    texto = fn(ctx, {}, PonteDeMentira())["mesa"]["registro-texto"]

    assert "Failed to add match" in texto, (
        f"a queixa do journalctl foi trocada por uma frase nossa: {texto!r}")


# --------------------------------------------------------------------------
# 3. o piloto realmente pinta o que o gesto devolveu
# --------------------------------------------------------------------------
def test_o_piloto_manda_a_resposta_para_a_pagina():
    """`_deu_certo` com um dicionário vira `pintar(...)`; com `None`, nada.

    É a metade da cura que nenhuma outra régua vê: os gestos podem devolver a
    carga certa e o piloto continuar descartando, que era o estado até hoje.
    """
    import hefesto_vivo

    class PilotoDeMentira:
        _deu_certo = hefesto_vivo.Piloto._deu_certo

        def __init__(self):
            self.aplicados: list[str] = []
            self.scripts: list[str] = []

        def _js(self, script: str) -> None:
            self.scripts.append(script)

    piloto = PilotoDeMentira()
    piloto._deu_certo("09-sistema.html", "ver-plugins",
                      {"mesa": {"registro-texto": "duas linhas\ne outra"}})
    assert piloto.scripts, (
        "o gesto devolveu carga e o piloto não mandou nada para a página. É o "
        "descarte que esta cura existe para acabar.")
    assert "pintar(" in piloto.scripts[0], piloto.scripts[0]
    assert "registro-texto" in piloto.scripts[0], piloto.scripts[0]

    piloto.scripts.clear()
    piloto._deu_certo("09-sistema.html", "retomar", None)
    assert piloto.scripts == [], (
        "um gesto que não devolve nada mandou JS mesmo assim — pintaria zero e "
        "poluiria o console de quem depura.")
