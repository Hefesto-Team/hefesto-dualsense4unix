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

A MORDIDA: troque o `return {...}` de `ver_detalhes` por `return None` — o
item 1 reprova dizendo que nada foi para a tela. Troque `REGISTRO` por qualquer
outro nome — o item 1 reprova dizendo que a página não tem esse endereço.

O «Ver os plugins» SAIU DA ABA EM 13/09/2026 (SISTEMA-BOTOES-01), pela decisão
dela D-OS-PLUGINS-APARECEM-ONDE-AGEM, e as duas réguas dele saíram junto:
`test_ver_plugins_mostra_os_nomes_que_o_daemon_respondeu` e
`test_ver_plugins_sem_plugin_diz_qual_dos_dois_silencios_e`. Quem cobra a
saída é `test_cada_botao_da_aba_sistema_faz_o_que_diz`.
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
# O «Ver detalhes» SAIU EM 25/09/2026 (A-09-SISTEMA-EM-TRES-SECOES-01): o
# registro passou a estar SEMPRE no painel, relido pela faixa lenta. As três
# réguas abaixo mediam o gesto; agora medem o dono do diário, `_diario()`, e o
# endereço onde ele pousa — o que elas protegiam continua o mesmo.
def test_o_endereco_do_registro_existe_na_pagina(pac):
    """Escrever num endereço que a página não tem é pintar ZERO, calado."""
    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    html = (onde.PUBLICADO / "09-sistema.html").read_text(encoding="utf-8")
    assert f'data-campo="{a09.REGISTRO}"' in html, (
        f"a página publicada não tem `{a09.REGISTRO}` — o registro seria escrito "
        "em lugar nenhum. Marque-o no gerador `interface/aba09.py` e publique.")


# --------------------------------------------------------------------------
# 2. o conteúdo é o do produto, e não uma frase nossa
# --------------------------------------------------------------------------
def test_o_diario_leva_o_journal_para_o_painel(pac, monkeypatch):
    """As linhas do painel são as do `journalctl`, e a unit tem dono.

    A UNIT É O PONTO: ela foi digitada uma vez neste pacote, com o nome
    `-dev` que a purga de 01/09 aposentou, e a tela passou a afirmar
    `not-found` sobre uma unit `enabled`. E o endereço de um controle sai com
    a máscara da casa: o painel existe para ser copiado num relato.
    """
    import subprocess

    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09
    from hefesto_dualsense4unix.utils import identidade

    visto: dict[str, list[str]] = {}

    class Saida:
        stdout = ("set 01 15:03:23 daemon pronto\n"
                  "set 01 15:03:24 controle uniq=aa:bb:cc:12:34:ff ok")
        stderr = ""

    def falso_run(argv, **_):
        visto["argv"] = list(argv)
        return Saida()

    monkeypatch.setattr(subprocess, "run", falso_run)
    texto = a09._diario()

    assert "daemon pronto" in texto, f"o journal não chegou ao painel: {texto!r}"
    assert "aa:bb:cc:00:00:ff" in texto and "12:34" not in texto, (
        f"o endereço do controle saiu sem a máscara da casa: {texto!r}")
    assert identidade.atual().unit_daemon in visto["argv"], (
        f"perguntou por {visto['argv']!r}. A unit tem dono em `utils/identidade`.")
    assert str(a09.LINHAS_DO_DIARIO) in visto["argv"]


def test_o_diario_repassa_o_motivo_do_journalctl(pac, monkeypatch):
    """Sem linhas, a tela mostra o que o `journalctl` disse — não uma frase nossa."""
    import subprocess

    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    class Saida:
        stdout = ""
        stderr = "Failed to add match: Invalid argument"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Saida())
    texto = a09._diario()

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
    piloto._deu_certo("09-sistema.html", "parar-ou-retomar",
                      {"mesa": {"registro-texto": "duas linhas\ne outra"}})
    assert piloto.scripts, (
        "o gesto devolveu carga e o piloto não mandou nada para a página. É o "
        "descarte que esta cura existe para acabar.")
    assert "pintar(" in piloto.scripts[0], piloto.scripts[0]
    assert "registro-texto" in piloto.scripts[0], piloto.scripts[0]

    piloto.scripts.clear()
    piloto._deu_certo("09-sistema.html", "atualizar", None)
    assert piloto.scripts == [], (
        "um gesto que não devolve nada mandou JS mesmo assim — pintaria zero e "
        "poluiria o console de quem depura.")
