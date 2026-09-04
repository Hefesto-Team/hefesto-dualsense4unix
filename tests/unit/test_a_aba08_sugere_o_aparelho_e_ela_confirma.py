#!/usr/bin/env python3
"""A TELA SUGERE O APARELHO, E ELA CONFIRMA — e nada é gravado sem o toque dela.

**03/09/2026.** O kernel chama um aparelho de "Câmera" e a lista dela oferece
"Webcam". Perguntada se são a mesma coisa, ela respondeu:

    "Depende do aparelho. Nem toda 'Câmera' do kernel é a webcam que você quer
     marcar. A tela pode SUGERIR e deixar você confirmar, em vez de decidir
     sozinha."

O QUE A ABA FAZIA ATÉ AQUI: perguntava `— O que é? —` para os QUATRO rádios
vizinhos, inclusive para os TRÊS que o kernel já classificou. Medido nesta
bancada, lendo `/sys` sem escrever nada —

    3554:fa09  03/01/01  Teclado           grau=lido
    25a7:fa07  03/01/02  Mouse             grau=lido
    046d:08e5  0e/01/00  Câmera            grau=lido       ← o caso DELA
    2357:012d  ff/ff/ff  Não identificado  grau=desconhecido

A janela estável já lia isso desde 22/08 (`secao_mesa._celula_do_que_e`, com o
selo `(lido)` e o botão "Corrigir"); a tela nova, não.

**A REGRA QUE ESTA RÉGUA EXISTE PARA TRAVAR, e ela é sobre PERDA DE DADO:** a
sugestão do kernel **nunca** pode virar resposta dela no `maquina.json`. Uma
palavra em `MesaDeclarada.radios[…].tipo` é uma afirmação DELA sobre o hardware
DELA — o produto decide com base nela *o que dá para desligar e o que não dá*.

AS DUAS MORDIDAS, e cada uma derruba um caso diferente:

1. em `vizinho_o_que_e`, tire o `or rotulo in _perguntas_sugeridas()` — o gesto
   volta a levantar `ValueError` na sugestão, que nesta aba é recusa **calada**;
2. em `_pergunta_sugerida`, devolva `palavra` cru em vez de moldurá-la — a
   sugestão passa a ser indistinguível da resposta dela, e o gesto passa a
   GRAVAR "Teclado" no disco dela sem que ela tenha dito nada.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "08-conexoes.html"


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def a08():
    from pacotes import a08_conexoes

    return a08_conexoes


class PonteDeMentira:
    """Guarda o que foi pedido à ponte, e nunca fala com daemon nenhum."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args: Any, **kwargs: Any):
            self.chamadas.append((nome, args, kwargs))
            return True

        return registrar


class AparelhoDeMentira:
    def __init__(self, especie: str, grau: str) -> None:
        self.especie = especie
        self.grau = grau


class CensoDeMentira:
    """O censo do barramento com os nós que a régua escolher — nunca o `/sys`.

    Ler o `/sys` de quem roda faria esta régua passar nesta bancada e reprovar
    em qualquer outra: é a mesma razão pela qual o gabinete dos outros testes
    desta aba é de bancada.
    """

    def __init__(self, por_no: dict[str, AparelhoDeMentira]) -> None:
        self._por_no = por_no

    def aparelho(self, no: str) -> AparelhoDeMentira | None:
        return self._por_no.get(no)


def _rotulos(a08) -> dict[str, str]:
    """`{rótulo: id}` — PERGUNTADO ao dono (`secao_mesa._TIPOS_DE_RADIO`)."""
    para_id, _ = a08._tipos_de_radio()
    assert para_id, "sem a lista do produto esta régua não mede nada"
    return para_id


def _com_o_censo(a08, monkeypatch, por_no: dict[str, tuple[str, str]]) -> None:
    censo = CensoDeMentira(
        {no: AparelhoDeMentira(especie, grau) for no, (especie, grau) in por_no.items()}
    )
    monkeypatch.setattr(a08, "_censo", lambda *_a, **_k: censo)


# ---------------------------------------------------------------------------
# 1. O KERNEL SUGERE — e a sugestão sai vestida de PERGUNTA
# ---------------------------------------------------------------------------
def test_a_palavra_do_kernel_que_ja_e_a_dela_vira_sugestao(a08, monkeypatch):
    """"Teclado" (kernel) e "Teclado" (lista dela) casam sem tabela nenhuma."""
    _com_o_censo(a08, monkeypatch, {"/sys/x": ("Teclado", "lido")})
    assert a08._sugestao_do_vizinho("/sys/x", _rotulos(a08)) == "Teclado"


def test_a_camera_do_kernel_vira_a_webcam_dela(a08, monkeypatch):
    """O caso que ELA respondeu, e o único da tabela que a bancada exercita."""
    _com_o_censo(a08, monkeypatch, {"/sys/cam": ("Câmera", "lido")})
    assert a08._sugestao_do_vizinho("/sys/cam", _rotulos(a08)) == "Webcam"


def test_a_sugestao_nunca_sai_como_resposta(a08):
    """`— Teclado? —`, e não `Teclado`. A moldura É a marca de que é sugestão."""
    pergunta = a08._a_pergunta()
    sugerida = a08._pergunta_sugerida("Teclado", pergunta)
    assert sugerida != "Teclado"
    assert "Teclado" in sugerida
    assert sugerida not in _rotulos(a08), (
        "a sugestão caiu em cima de uma resposta da lista dela — o gesto a "
        "gravaria no `maquina.json` como se ela tivesse respondido")


def test_a_moldura_sai_da_pergunta_e_nao_e_digitada(a08):
    """A régua PERGUNTA: troque a pergunta e a moldura vai junto.

    Um `f"— {palavra}? —"` digitado passaria neste caso e envelheceria no dia em
    que o texto da primeira opção mudasse — a sugestão ficaria com a moldura de
    uma pergunta que a tela não faz mais.
    """
    assert a08._moldura_da_pergunta("— O que é? —") == ("— ", "? —")
    assert a08._pergunta_sugerida("Mouse", "«O que é isso?»") == "«Mouse?»"
    assert a08._pergunta_sugerida("Mouse", "O que e") == "Mouse"


# ---------------------------------------------------------------------------
# 2. O KERNEL CALA — e a pergunta continua sendo a única resposta honesta
# ---------------------------------------------------------------------------
def test_a_classe_ff_nao_sugere_nada(a08, monkeypatch):
    """Grau `desconhecido` é o fabricante declinando de classificar.

    É o `2357:012d` desta bancada. Chutar "Wi-Fi" aqui seria o número plausível
    e falso que esta aba não escreve.
    """
    _com_o_censo(a08, monkeypatch, {"/sys/ff": ("Não identificado", "desconhecido")})
    assert a08._sugestao_do_vizinho("/sys/ff", _rotulos(a08)) == ""


def test_a_palavra_sem_par_na_lista_dela_nao_vira_sugestao(a08, monkeypatch):
    """"Impressora" o kernel diz; a lista dela não a tem. Então não há sugestão.

    Uma sugestão fora da lista seria pior que nenhuma: o `<select>` só aceita o
    que oferece, e o pintor a descartaria calado.
    """
    _com_o_censo(a08, monkeypatch, {"/sys/p": ("Impressora", "lido")})
    assert a08._sugestao_do_vizinho("/sys/p", _rotulos(a08)) == ""


def test_o_no_vazio_e_o_censo_ausente_nao_sugerem(a08, monkeypatch):
    """Sem nó e sem censo, a tela não inventa. Ausência não é resposta."""
    _com_o_censo(a08, monkeypatch, {"/sys/x": ("Teclado", "lido")})
    assert a08._sugestao_do_vizinho("", _rotulos(a08)) == ""
    monkeypatch.setattr(a08, "_censo", lambda *_a, **_k: None)
    assert a08._sugestao_do_vizinho("/sys/x", _rotulos(a08)) == ""


# ---------------------------------------------------------------------------
# 3. TODA SUGESTÃO POSSÍVEL É RECONHECIDA — conjunto, não contagem
# ---------------------------------------------------------------------------
def test_toda_sugestao_possivel_cabe_na_lista_dela(a08):
    """O destino de cada equivalência EXISTE em `_TIPOS_DE_RADIO`.

    Um destino digitado errado (`"Caixa de Som"`, com o `S` maiúsculo) não daria
    erro em lugar nenhum: a sugestão simplesmente sumiria, calada, e a linha
    voltaria a perguntar o que o kernel já respondeu.
    """
    rotulos = _rotulos(a08)
    fora = sorted(d for d in a08._SUGESTAO_DO_KERNEL.values() if d not in rotulos)
    assert fora == [], f"destino que a lista dela não oferece: {fora}"


def test_o_conjunto_das_perguntas_sugeridas_cobre_a_lista_inteira(a08):
    """Toda resposta da lista dela tem a sua pergunta sugerida reconhecida.

    É conjunto e não contagem de propósito: uma opção nova na lista entra aqui
    sozinha, em vez de reprovar um `== 8` que ninguém lembraria de mexer.
    """
    pergunta = a08._a_pergunta()
    sugeridas = a08._perguntas_sugeridas()
    for rotulo in _rotulos(a08):
        assert a08._pergunta_sugerida(rotulo, pergunta) in sugeridas


# ---------------------------------------------------------------------------
# 4. O GESTO — a sugestão NÃO vira resposta dela no disco
# ---------------------------------------------------------------------------
def _declarou(ponte: PonteDeMentira) -> list[dict[str, Any]]:
    return [c[1][0] for c in ponte.chamadas if c[0] == "machine_declare"]


@pytest.fixture
def um_vizinho(a08, monkeypatch):
    """UM rádio pintado na posição 0, e o disco relido vira dublê.

    `_reler_a_declaracao` abre o `maquina.json` de quem roda; num teste
    unitário isso é ler o arquivo DELA sem precisar.
    """
    monkeypatch.setattr(a08, "_VIZINHOS", ("3554:fa09",), raising=False)
    monkeypatch.setattr(a08, "_reler_a_declaracao", lambda: None)


def _clicar(pac, a08, ponte, valor: str) -> None:
    fn = pac.gesto_da_pagina(PAGINA, "vizinho-o-que-e")
    assert fn is not None, "vizinho-o-que-e perdeu o dono"
    ctx = pac.Contexto(state={"active_profile": "regua"}, mesa=[],
                       conectados=[], estados={})
    fn(ctx, {"v": "0", "valor": valor}, ponte)


def test_o_gesto_nao_grava_a_sugestao_como_resposta_dela(pac, a08, um_vizinho):
    """A REGRA INTEIRA numa linha: sugestão escolhida grava `tipo: None`.

    `None` é "ela ainda não respondeu" — a mesma coisa que "— O que é? —" e que
    "Não sei" (docstring do gesto). Gravar `"teclado"` aqui poria na boca dela
    uma resposta que ela não deu.
    """
    ponte = PonteDeMentira()
    sugerida = a08._pergunta_sugerida("Teclado", a08._a_pergunta())
    _clicar(pac, a08, ponte, sugerida)
    assert _declarou(ponte) == [{"mesa": {"radios": {"3554:fa09": {"tipo": None}}}}]


def test_o_gesto_nao_recusa_calado_na_sugestao(pac, a08, um_vizinho):
    """Sem a linha da sugestão, isto levanta `ValueError` — recusa CALADA.

    `hefesto_vivo._recusou_dizendo` só leva `RuntimeError` à tela: um
    `ValueError` some no terminal de quem lançou a janela, e o segundo clique
    parece o primeiro. É a forma dos quatro gestos que esta aba já tem assim.
    """
    ponte = PonteDeMentira()
    for rotulo in _rotulos(a08):
        _clicar(pac, a08, ponte, a08._pergunta_sugerida(rotulo, a08._a_pergunta()))


def test_a_resposta_dela_continua_gravando(pac, a08, um_vizinho):
    """A confirmação — um toque — grava, e grava o ID do esquema, não o rótulo."""
    ponte = PonteDeMentira()
    _clicar(pac, a08, ponte, "Webcam")
    assert _declarou(ponte) == [{"mesa": {"radios": {"3554:fa09": {"tipo": "webcam"}}}}]


def test_a_palavra_que_nao_e_da_lista_continua_recusando(pac, a08, um_vizinho):
    """A trava do pydantic continua de pé: rótulo estranho não chega ao disco.

    Sem ela, `"Fone"` iria cru para `RadioDeclarado.tipo`, que é `Literal[…]`, e
    o pydantic recusaria o DOCUMENTO INTEIRO — a tela diria "não consegui
    gravar" onde o defeito é "valor inválido".
    """
    ponte = PonteDeMentira()
    with pytest.raises(ValueError):
        _clicar(pac, a08, ponte, "Fone sem fio da TV")
    assert _declarou(ponte) == []


# ---------------------------------------------------------------------------
# 5. A TELA TEM ONDE POUSAR — o endereço existe na página, e é UM por bloco
# ---------------------------------------------------------------------------
def test_a_pagina_tem_o_endereco_da_pergunta_uma_vez_por_vizinho():
    """`vizinho-pergunta` mora na PRIMEIRA `<option>` de cada `<select>`.

    Emitir um endereço que a página não tem é o defeito que esta aba já tem dez
    vezes (medido em 03/09) — o pacote fala, `achar()` não encontra ninguém, e
    o valor morre calado. A régua conta CONTRA `vizinho-tipo`, que é o dono da
    caixa: um bloco de vizinho tem exatamente uma pergunta.
    """
    import re

    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    caixas = len(re.findall(r'data-campo="vizinho-tipo"', html))
    perguntas = len(re.findall(r'data-campo="vizinho-pergunta"', html))
    assert caixas > 0, "o desenho perdeu os blocos de vizinho"
    assert perguntas == caixas, (
        f"{perguntas} pergunta(s) endereçada(s) para {caixas} caixa(s)")
    assert re.search(
        r'<option[^>]*data-campo="vizinho-pergunta"[^>]*>[^<]*\?', html), (
        "o endereço saiu da opção que FAZ a pergunta")
