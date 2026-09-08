#!/usr/bin/env python3
"""AS TRÊS LINHAS DE ESTADO DA NAVEGAÇÃO SÃO DO PRODUTO — não desta aba.

O QUE FALTAVA, medido em 03/09/2026 contra a GTK que ela usa: a aba nova
respondia *o que está configurado* e calava *o que está acontecendo*. As três
perguntas que a GTK responde e a tela nova não:

    por que o cursor não anda?          `mouse_actions._refresh_mouse_view`
    o teclado está ligado e calado?     `emulation_actions.descrever_teclado_emulado`
    há teclado na tela nesta máquina?   `input_actions.frase_do_teclado_na_tela`

As três eram emitidas para o vazio (`SEM_ENDERECO`) porque o desenho não tinha
linha — e a dica do quadro Navegação já citava *"a linha de estado abaixo"*
desde 27/08, para uma linha que não existia.

O QUE ESTA RÉGUA COBRA, e é o inverso do que parece: **que esta aba NÃO tenha
frase própria.** A LEI 0 desta empreitada é dela — *"Não temos que recriar nada.
só aproveitar o que foi feito e integrar ao novo desenho"* —, e a forma de
quebrá-la aqui seria reescrever as frases da GTK em português "melhor". Então
cada linha abaixo compara o que a tela recebe com o que a função do produto
devolve, chamando as duas.

A ÚNICA CÓPIA DECLARADA é `PRONTO_PARA_MOUSE`: ela é um literal DENTRO de
`_refresh_mouse_view`, que é método de mixin GTK e escreve num widget. Extraí-la
para uma constante é edição em `app/actions/mouse_actions.py`, que não é desta
frente — então ela é copiada e esta régua lê o FONTE de lá para reprovar no dia
em que as duas divergirem.

AS MORDIDAS:

* troque uma palavra de `PRONTO_PARA_MOUSE` — a linha do fonte da GTK reprova;
* faça `_o_mouse_virtual_em_uma_linha` escrever a própria frase do bloqueio em
  vez de ler `BLOQUEIO_DO_MOUSE_EM_PORTUGUES`;
* tire uma das três `<div class="estado">` de `aba06.ESTADOS`.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app.actions.emulation_actions import (
    descrever_teclado_emulado,
)
from hefesto_dualsense4unix.app.actions.input_actions import frase_do_teclado_na_tela
from hefesto_dualsense4unix.app.actions.mouse_actions import (
    BLOQUEIO_DO_MOUSE_EM_PORTUGUES,
)
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo

UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
         "battery_pct": 90, "is_primary": True, "inputs": {}, "audio": {},
         "speaker": {}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "cosmic-red", "mascara": "DualSense"}]

#: As três linhas, e o nome de cada uma no desenho.
AS_TRES = ("rato-estado", "teclado-bloqueio", "teclado-osk")

#: "Não há o que dizer", dito de um jeito que a tela sabe APAGAR. O
#: `escrever()` do piloto troca vazio por `—` (`hefesto_vivo.py:141`), então uma
#: frase vazia viraria um travessão solto embaixo do interruptor — visto na
#: primeira foto de 03/09. O marcador vem do pacote para a régua não digitar a
#: segunda verdade sobre a forma dele.
from pacotes import a06_navegacao as _mod

NADA_A_DIZER = _mod.NADA_A_DIZER

_SO_TEXTO = re.compile(r"<[^>]+>")


def _mesa(rato: dict | None = None, tecla: dict | None = None) -> dict:
    from pacotes import Contexto
    from pacotes import a06_navegacao as mod

    estado: dict = {"active_profile": "regua", "controllers": [FALSO]}
    if rato is not None:
        estado["mouse_emulation"] = rato
    if tecla is not None:
        estado["keyboard_emulation"] = tecla
    return mod.pacote(Contexto(state=estado, mesa=MESA, conectados=[FALSO]))["mesa"]


@pytest.fixture(scope="module")
def bancada() -> str:
    return onde.pagina(PAGINA).read_text(encoding="utf-8")


def test_as_tres_linhas_tem_lugar_no_desenho(bancada: str) -> None:
    """Sem lugar, a frase do produto continua indo para o vazio.

    LUGAR, E NÃO A TIRA — 07/09/2026. Duas das três continuam na tira de
    `.estados`; `teclado-osk` mudou de endereço na PÁGINA (foi para o `?` da
    "Função do teclado", por ordem dela: *"navegacao tem essas 3 frases aqui na
    parte de baixo que quebram o layout"*). O que esta régua cobra é o que
    sempre cobrou — que a frase do produto tenha ONDE cair, com o alvo `html` —,
    e por isso ela não pergunta em que `<div>` o endereço está.
    """
    for campo in AS_TRES:
        assert f'data-campo="{campo}" data-hef-alvo="html"' in bancada, (
            f"a linha `{campo}` não tem endereço na bancada. O alvo é `html` "
            "porque as frases do produto trazem `<b>` e `<tt>` — o alvo padrão "
            "escreveria os marcadores como texto na tela dela.")
    assert ".estado:empty{display:none}" in bancada, (
        "a regra que apaga a linha VIRGEM sumiu: sem ela, três faixas em branco "
        "empurram a fileira dos botões para baixo enquanto o Hefesto não fala.")
    assert ".estado:has(.nada){display:none}" in bancada, (
        "a regra que apaga a linha SEM CONTEÚDO sumiu. Ela não é a mesma do "
        "`:empty`: depois do primeiro tique a linha tem o marcador dentro, e "
        "sem esta regra a tela mostra um travessão solto — que é ruído com "
        "cara de dado.")
    assert 'class="estados"' in bancada, (
        "a tira de estados sumiu. Empilhadas fora dela, as linhas empurram a "
        "fileira dos botões para FORA da janela — medido em 03/09, e medido de "
        "novo em 07/09: com três frases no pé, o quadro das opções ia de 215px "
        "a 300,25px e a fileira terminava 41,25px fora.")


def test_as_tres_sairam_da_lista_de_orfaos() -> None:
    """Declaração que sobrevive à cura é a régua se desligando sozinha."""
    from pacotes import a06_navegacao as mod

    for campo in ("rato-ligado", "rato-bloqueio", "teclado-osk"):
        assert campo not in mod.SEM_ENDERECO, (
            f"`{campo}` ganhou endereço em 03/09/2026 e continua declarado "
            "como órfão.")


def test_o_mouse_pronto_diz_a_frase_da_gtk() -> None:
    """Device no ar segundo o DAEMON → a frase verde, palavra por palavra."""
    from pacotes import a06_navegacao as mod

    linha = _mesa({"enabled": True, "device_ativo": True, "bloqueio": None})
    assert mod.PRONTO_PARA_MOUSE in linha["rato-estado"], linha["rato-estado"]
    assert 'class="verde"' in linha["rato-estado"]


def test_a_frase_do_pronto_e_a_mesma_que_a_gtk_escreve() -> None:
    """A cópia declarada não pode divergir calada.

    Ela é um literal dentro de `_refresh_mouse_view` — método de mixin GTK, que
    escreve num widget e não dá para importar. Então esta linha lê o FONTE e
    exige que a frase ainda esteja lá.

    NÃO É ASSEIO: no dia em que alguém melhorar o texto da GTK, a tela nova
    passaria a dizer outra coisa sobre o MESMO estado, e as duas janelas do
    mesmo produto discordariam sem ninguém acusar.
    """
    from pacotes import a06_navegacao as mod

    fonte = (RAIZ / "src/hefesto_dualsense4unix/app/actions/mouse_actions.py"
             ).read_text(encoding="utf-8")
    assert mod.PRONTO_PARA_MOUSE in fonte, (
        f"{mod.PRONTO_PARA_MOUSE!r} não está mais em `mouse_actions.py`. Ou a "
        "GTK mudou a frase — e esta aba tem de acompanhar —, ou ela virou "
        "constante lá, e o certo passou a ser IMPORTÁ-LA em vez de copiar.")


@pytest.mark.parametrize("bloqueio", sorted(BLOQUEIO_DO_MOUSE_EM_PORTUGUES))
def test_o_motivo_do_bloqueio_e_a_tabela_do_produto(bloqueio: str) -> None:
    """Cada motivo do daemon vira a frase que a GTK já traduzia.

    `desligada` é o único que NÃO vira linha, e é a hierarquia da GTK: sem
    device porque ela desligou não é defeito nenhum, e mandá-la consertar um
    interruptor que ela mesma baixou seria alarme falso.
    """
    linha = _mesa({"enabled": True, "device_ativo": False, "bloqueio": bloqueio})
    texto = _SO_TEXTO.sub("", linha["rato-estado"])
    if bloqueio == "desligada":
        assert texto == "" and linha["rato-estado"] == NADA_A_DIZER, (
            "`desligada` virou linha de estado: é escolha dela, não defeito — "
            "a própria GTK a classifica como 'não sei' em `_anotar_mouse_virtual`.")
        return
    esperado = BLOQUEIO_DO_MOUSE_EM_PORTUGUES[bloqueio].replace(
        "{gesto}", como_atualizar_esta_instalacao())
    assert esperado in texto, (
        f"a tela diz {texto!r} e a tabela do produto diz {esperado!r} — a aba "
        "escreveu frase própria em vez de ler `BLOQUEIO_DO_MOUSE_EM_PORTUGUES`.")


def test_o_motivo_novo_nao_e_engolido() -> None:
    """Um `bloqueio` que esta janela não conhece aparece cru, e não some.

    É o que a GTK faz em `frase_da_recusa_do_mouse`: dizer o código é feio, e é
    honesto — melhor que afirmar que está funcionando.
    """
    linha = _mesa({"enabled": True, "device_ativo": False, "bloqueio": "coisa_nova"})
    assert "coisa_nova" in linha["rato-estado"], linha["rato-estado"]


@pytest.mark.parametrize("bloco", [
    {"enabled": True, "bloqueio": "modo_jogo"},
    {"enabled": True, "bloqueio": None},
    {"enabled": False},
    {},
])
def test_a_linha_do_teclado_e_a_funcao_do_produto(bloco: dict) -> None:
    """A frase é a de `descrever_teclado_emulado`, chamada e não copiada."""
    _posicao, esperado = descrever_teclado_emulado(bloco or None)
    linha = _mesa(tecla=bloco)
    if not esperado:
        assert linha["teclado-bloqueio"] == NADA_A_DIZER, linha["teclado-bloqueio"]
        return
    assert _SO_TEXTO.sub("", linha["teclado-bloqueio"]) == esperado, (
        f"com {bloco} a tela diz {linha['teclado-bloqueio']!r} e o produto diz "
        f"{esperado!r}")


@pytest.mark.parametrize("osk", [True, False, None])
def test_a_linha_do_teclado_na_tela_e_a_funcao_do_produto(osk: bool | None) -> None:
    """`None` devolve `""` — não se afirma sobre uma máquina que ninguém olhou.

    O tri-estado é do produto, e é a razão de a função existir: a frase de "não
    tem" manda instalar um pacote, e dizê-la porque ninguém respondeu mandaria
    ela instalar o que talvez já esteja lá.
    """
    linha = _mesa(tecla={"enabled": True, "osk_disponivel": osk})
    esperado = frase_do_teclado_na_tela(osk) or NADA_A_DIZER
    assert linha["teclado-osk"] == esperado, (
        f"com `osk_disponivel={osk}` a tela diz {linha['teclado-osk']!r}")


def test_com_o_daemon_mudo_o_mouse_nao_afirma_nada() -> None:
    """Sem bloco, sem linha — a régua da tela vazia é a regra dela.

    *"se não tá mostrando agora, não tem info pra mostrar no produto; mas
    quando tiver, aparece a info correta"* (30/08/2026).
    """
    mesa = _mesa(None, None)
    assert mesa["rato-estado"] == NADA_A_DIZER
    assert mesa["teclado-osk"] == NADA_A_DIZER


# "O homem é a medida de todas as coisas." — Protágoras
