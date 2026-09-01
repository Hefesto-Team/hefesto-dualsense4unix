#!/usr/bin/env python3
"""A RÉGUA DO MAPA DO GABINETE: o desenho é o DELA, e os seis botões o mudam.

O QUE ESTAVA ERRADO ATÉ 01/09/2026, e é a razão de esta régua existir: a aba
Conexões mostrava um gabinete de BANCADA — duas faces e dez entradas escritas
como constantes no gerador (`FACES`, `QUEM_ESTA`, `CENSO`) — enquanto o
`maquina.json` dela **não existe** e o mapa declarado está vazio.

Era por isso que os seis botões do mapa não podiam ser ligados: clicar
declararia no disco DELA o desenho de um exemplo. A medição que os segurava
estava certa; o que faltava era a aba pintar o gabinete dela.

AS QUATRO COISAS QUE ESTA RÉGUA COBRA:

1. **O desenho é UM SÓ.** `gui/aba_conexoes.html_do_mapa` desenha, e o gerador
   do mockup usa o MESMO. Foi assim que a extração se provou fiel — a página
   regerada saiu byte a byte igual à que ela aprovou.
2. **O veredito vem do MOTOR.** O gerador tinha uma reescrita à mão do
   `arranjo_da_mesa.julgar`, com os cinco vereditos digitados como constantes.
3. **O mapa vazio DIZ que está vazio.** Caixa em branco é indistinguível de
   "isto quebrou", e o produto já tinha a frase (`ROTULO_SEM_FACE`).
4. **Os seis gestos mudam o rascunho e GRAVAM O INTEIRO.** As faces são uma
   LISTA e `fundir_declaracao` troca lista inteira — mandar pedaço apagaria as
   faces que ela já tinha.

A MORDIDA: troque `como_documento()` por um pedaço no `_gravar_o_mapa` — o caso
do inteiro reprova dizendo que as faces antigas se perderiam.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))


class PonteDeMentira:
    """Guarda o que foi declarado ao daemon."""

    def __init__(self) -> None:
        self.declarado: list[dict[str, Any]] = []

    def machine_declare(self, documento: dict[str, Any]) -> tuple[bool, str]:
        self.declarado.append(documento)
        return True, ""


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def a08():
    from pacotes import a08_conexoes

    return a08_conexoes


@pytest.fixture(autouse=True)
def rascunho_limpo(a08, monkeypatch):
    """Um rascunho novo por caso, e NUNCA o disco dela.

    O `_logica_do_mapa` guarda o rascunho num global de propósito (é ele que
    segura o aparelho na mão entre os dois tempos do gesto). Sem esta limpeza um
    caso herdaria o do anterior — e, pior, o primeiro leria o `maquina.json` da
    máquina de quem roda.
    """
    from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import LogicaDoMapa
    from hefesto_dualsense4unix.utils.maquina import MapaDaMesa

    monkeypatch.setattr(a08, "_LOGICA", LogicaDoMapa(MapaDaMesa()), raising=False)
    return a08


def _gesto(pac, nome: str):
    fn = pac.gesto_da_pagina("08-conexoes.html", nome)
    assert fn is not None, f"08-conexoes.html:{nome} perdeu o dono"
    return fn


def _ctx(pac):
    return pac.Contexto(state={}, mesa=[], conectados=[], estados={})


# --------------------------------------------------------------------------
# 1. o desenho é um só, e o mockup prova a fidelidade
# --------------------------------------------------------------------------
def test_o_gerador_do_mockup_usa_o_desenho_do_produto() -> None:
    """Se o gerador voltar a desenhar sozinho, as duas telas divergem calado.

    É o que já tinha acontecido: o desenho do gerador julgava por uma tabela de
    vizinhos do mockup, e o produto julga pela mesa real.
    """
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py").read_text(
        encoding="utf-8")
    assert "_aba_conexoes.html_do_mapa(" in fonte, (
        "o gerador da aba Conexões parou de usar `gui/aba_conexoes.html_do_mapa`. "
        "Com dois desenhos, o que ela aprova e o que ela usa deixam de ser o "
        "mesmo — e ninguém compara.")


def test_o_mapa_vazio_diz_que_esta_vazio() -> None:
    """Caixa em branco é indistinguível de "isto quebrou"."""
    from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import ROTULO_SEM_FACE
    from hefesto_dualsense4unix.gui.aba_conexoes import html_do_mapa

    saiu = html_do_mapa([], quem_esta={}, extensoes={},
                        veredito_de=lambda n, e: ("", "", ""),
                        rotulos={"vazia": "", "por_extensao": "", "nova_entrada": ""},
                        dicas={"esticada": "", "enumera": "", "nova_entrada": "",
                               "novo_hub": ""})
    assert ROTULO_SEM_FACE.split(".")[0] in saiu, (
        f"o mapa vazio saiu sem a frase do produto: {saiu!r}")


def test_cada_quadrado_leva_o_endereco_da_entrada() -> None:
    """Sem `data-entrada`, o clique não diz em qual buraco ela clicou."""
    from hefesto_dualsense4unix.gui.aba_conexoes import html_do_mapa

    saiu = html_do_mapa(
        [{"nome": "Traseira", "portas": ["1", "2"]}],
        quem_esta={"1": ("Bluetooth", "3-1.1.1")}, extensoes={},
        veredito_de=lambda n, e: ("cheia", "ocupada", "clique para tirar"),
        rotulos={"vazia": "vazia", "por_extensao": "por extensão",
                 "nova_entrada": "Acrescentar entrada"},
        dicas={"esticada": "", "enumera": "enumera {c}", "nova_entrada": "",
               "novo_hub": ""})
    assert 'data-entrada="1"' in saiu and 'data-entrada="2"' in saiu
    assert 'data-face="0"' in saiu, "a face sem endereço deixa `nova-entrada` sem alvo"
    assert "3-1.1.1" in saiu, "a dica não diz como o sistema enumera o aparelho"


# --------------------------------------------------------------------------
# 2. os seis gestos
# --------------------------------------------------------------------------
def test_o_gesto_de_dois_tempos(pac, a08) -> None:
    """Escolher não grava; pôr grava. E sem escolher antes, RECUSA dizendo."""
    p = PonteDeMentira()
    a08._LOGICA.acrescentar_face("Traseira")
    a08._LOGICA.acrescentar_entrada(0)

    with pytest.raises(RuntimeError) as erro:
        _gesto(pac, "escolher-entrada")(_ctx(pac), {"entrada": "1"}, p)
    assert "escolha antes" in str(erro.value).lower(), str(erro.value)
    assert p.declarado == [], "recusou e ainda assim declarou"

    _gesto(pac, "escolher-aparelho")(_ctx(pac), {"caminho": "3-1.1.1"}, p)
    assert p.declarado == [], "escolher é estado de tela — não pode gravar"
    assert a08._LOGICA.escolhido == "3-1.1.1"

    _gesto(pac, "escolher-entrada")(_ctx(pac), {"entrada": "1"}, p)
    assert a08._LOGICA.portas["1"]["caminho"] == "3-1.1.1"
    assert len(p.declarado) == 1, "pôr o aparelho na entrada tem de gravar"


def test_grava_o_mapa_inteiro_e_nao_um_pedaco(pac, a08) -> None:
    """As faces são uma LISTA, e `fundir_declaracao` troca lista inteira.

    Mandar meia lista apagaria as faces que ela já tinha — e era uma das razões
    escritas para `nova-face` não ser ligada. Mandar o rascunho inteiro é o que
    torna a troca de lista o comportamento CERTO.
    """
    p = PonteDeMentira()
    a08._LOGICA.acrescentar_face("Frente")
    _gesto(pac, "nova-face")(_ctx(pac), {"valor": "Traseira"}, p)

    documento = p.declarado[-1]["mapa"]
    nomes = [f["nome"] for f in documento["faces"]]
    assert nomes == ["Frente", "Traseira"], (
        f"o que foi ao disco tem {nomes} — a face que já existia precisa ir "
        f"junto, senão criar uma apaga as outras.")


def test_face_sem_nome_recusa(pac) -> None:
    """*"Sem nome, não cria"* — é o que o `title` do botão promete."""
    p = PonteDeMentira()
    with pytest.raises(ValueError):
        _gesto(pac, "nova-face")(_ctx(pac), {"valor": "   "}, p)
    assert p.declarado == []


def test_nova_entrada_pega_o_menor_numero_livre(pac, a08) -> None:
    """A regra é do produto: os números são do GABINETE e não se repetem."""
    p = PonteDeMentira()
    a08._LOGICA.acrescentar_face("Frente")
    a08._LOGICA.acrescentar_face("Traseira")
    for _ in range(2):
        _gesto(pac, "nova-entrada")(_ctx(pac), {"face": "0"}, p)
    _gesto(pac, "nova-entrada")(_ctx(pac), {"face": "1"}, p)

    assert a08._LOGICA.faces[0]["portas"] == ["1", "2"]
    assert a08._LOGICA.faces[1]["portas"] == ["3"], (
        "a segunda face repetiu um número da primeira — dois buracos diferentes "
        "não podem levar o mesmo número")


def test_tirar_esvazia_e_a_entrada_fica(pac, a08) -> None:
    """A entrada CONTINUA no desenho — é o que o `title` promete."""
    p = PonteDeMentira()
    a08._LOGICA.acrescentar_face("Frente")
    a08._LOGICA.acrescentar_entrada(0)
    _gesto(pac, "escolher-aparelho")(_ctx(pac), {"caminho": "3-1"}, p)
    _gesto(pac, "escolher-entrada")(_ctx(pac), {"entrada": "1"}, p)

    _gesto(pac, "tirar-daqui")(_ctx(pac), {"entrada": "1"}, p)
    assert "1" in a08._LOGICA.faces[0]["portas"], "a entrada sumiu do desenho"
    assert not a08._LOGICA.portas["1"].get("caminho"), "o aparelho continuou lá"

    with pytest.raises(RuntimeError):
        _gesto(pac, "tirar-daqui")(_ctx(pac), {"entrada": "1"}, p)


def test_extensao_vira_filha_com_letra(pac, a08) -> None:
    """A `10` vira `10a`, depois `10b`. E não há neta."""
    p = PonteDeMentira()
    a08._LOGICA.acrescentar_face("Traseira")
    a08._LOGICA.acrescentar_entrada(0)
    _gesto(pac, "nova-extensao")(_ctx(pac), {"entrada": "1"}, p)
    assert "1a" in a08._LOGICA.portas
    assert a08._LOGICA.portas["1a"]["filha_de"] == "1"

    with pytest.raises(RuntimeError):
        _gesto(pac, "nova-extensao")(_ctx(pac), {"entrada": "1a"}, p)


def test_um_aparelho_esta_em_um_lugar_so(pac, a08) -> None:
    """Pôr onde ele não estava o tira de onde estava, no mesmo gesto.

    A razão é do produto: *"sem isso o mesmo dongle apareceria em duas entradas
    e o mapa passaria a mentir de um jeito novo"*.
    """
    p = PonteDeMentira()
    a08._LOGICA.acrescentar_face("Traseira")
    for _ in range(2):
        a08._LOGICA.acrescentar_entrada(0)
    for entrada in ("1", "2"):
        _gesto(pac, "escolher-aparelho")(_ctx(pac), {"caminho": "3-1"}, p)
        _gesto(pac, "escolher-entrada")(_ctx(pac), {"entrada": entrada}, p)

    onde = [n for n, v in a08._LOGICA.portas.items() if v.get("caminho") == "3-1"]
    assert onde == ["2"], f"o aparelho ficou em {onde} — tem de estar em UM lugar"


def test_clique_sem_alvo_recusa(pac) -> None:
    """Nenhum dos seis mira um alvo padrão quando o clique não o disse."""
    p = PonteDeMentira()
    for nome, clique in (("escolher-aparelho", {}), ("escolher-entrada", {}),
                         ("tirar-daqui", {}), ("nova-entrada", {}),
                         ("nova-extensao", {}), ("nova-face", {})):
        with pytest.raises((ValueError, RuntimeError)):
            _gesto(pac, nome)(_ctx(pac), clique, p)
    assert p.declarado == [], "algum deles declarou sem saber o alvo"
