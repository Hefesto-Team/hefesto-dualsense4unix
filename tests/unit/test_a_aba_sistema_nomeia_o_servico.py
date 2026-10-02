"""O PORTÃO DA PALAVRA, do lado do PRODUTO — 31/08/2026, e ele guarda uma
decisão dela.

A COLISÃO QUE ELA MANDOU DESFAZER
---------------------------------
Duas abas diziam *"Hefesto ligado/desligado"* e significavam coisas
**diferentes**: na **Jogar** é o MODO (o Hefesto no meio do jogo, ou o aparelho
puro), e na **Sistema** é o PROCESSO (``systemctl --user stop``). Quem desligava
na Jogar continuava com o serviço rodando; quem desligava na Sistema matava
tudo. **A palavra "Hefesto" ficou com a aba Jogar**, e a Sistema passa a nomear
o SERVIÇO.

O DESENHO JÁ MUDOU — E O PRODUTO É QUEM ESCREVE AS DICAS
--------------------------------------------------------
``src/hefesto_dualsense4unix/interface/aba09.py`` tem o portão dele desde o mesmo dia: a faixa é
"O serviço", a linha é "O serviço está", os botões são "Reiniciar o serviço" e
"Parar o serviço". **Mas a tela nova lê as dicas e os motivos do produto**, e
enquanto o produto escrevia "Hefesto" o resultado, na tela viva, era a linha
dizendo *"O serviço está"* com a dica dizendo *"O Hefesto está rodando…"* — a
tela se contradizendo dentro de si mesma. Nenhuma régua de caixa podia ver
isso: **defeito de VOCABULÁRIO é invisível para quem só mede pixel.**

ELE OLHA SÓ PARA ONDE O RÓTULO DIZ "SERVIÇO", E É DE PROPÓSITO
---------------------------------------------------------------
É a mesma disciplina do portão do gerador. O ``title`` do botão vermelho
**precisa** dizer "Hefesto" — *"não é o interruptor Hefesto da aba Jogar"* —, e
é justamente essa frase que explica a diferença. Onde "Hefesto" é o PROGRAMA
(quem enxerga a janela, quem escreve nos controles, de quem é a saída crua) a
palavra fica: trocá-la seria o defeito ao contrário, a tela dizendo que quem
enxerga janela é uma unidade do systemd. Uma régua que varresse a aba inteira
reprovaria a cura junto com o defeito — o erro das onze réguas de 26/08.

Por isso :class:`TestOQueFicaComOHefesto` morde **no outro sentido**: se alguém
passar um "trocar tudo" por cima, ele reprova.

NADA É DIGITADO
---------------
Os rótulos saem do HTML que a aba abre
(``src/hefesto_dualsense4unix/interface/paginas/09-sistema.html``) e as dicas
saem de ``aba_sistema.pacote()`` — o mesmo código que a interface roda. A régua
prova primeiro que **sabe achar** (``test_a_regua_sabe_onde_olhar``): sem isso,
um rótulo renomeado calaria o portão inteiro em silêncio, que é a armadilha nº1
do ``COMO-OLHAR-A-TELA.md``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.sistema`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import ambiente_na_tela
from hefesto_dualsense4unix.interface import sistema as aba_sistema

RAIZ = Path(__file__).resolve().parents[2]
PAGINA = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "paginas" / "09-sistema.html"  # noqa-acento (`paginas` e o nome da PASTA; caminho nao leva acento)

PALAVRA = "Hefesto"


def _html() -> str:
    if not PAGINA.is_file():
        pytest.fail(
            f"{PAGINA} não existe — a aba Sistema da interface nova é essa "
            "página, e sem ela esta régua não sabe qual rótulo cobre qual "
            "linha. Portão que não acha o alvo tem de falar, não calar."
        )
    return PAGINA.read_text(encoding="utf-8")


def _rotulos_das_linhas() -> dict[str, str]:
    """``data-id`` → o rótulo que a pessoa LÊ naquela linha de estado."""
    achados: dict[str, str] = {}
    for linha in re.findall(r'<(?:div|a) class="saude[^"]*"[^>]*data-id="[^"]+".*?</(?:div|a)>',
                            _html(), re.S):
        ident = re.search(r'data-id="([^"]+)"', linha)
        rot = re.search(r'<span class="txt"[^>]*><span>([^<]*)</span>', linha)
        if ident and rot:
            achados[ident.group(1)] = rot.group(1).strip()
    return achados


def _rotulos_dos_botoes() -> dict[str, str]:
    """``data-gesto`` → o texto do botão. O ``title`` fica de fora de propósito."""
    return {
        gesto: texto.strip()
        for gesto, texto in re.findall(
            r'<button[^>]*data-gesto="([^"]+)"[^>]*>([^<]*)</button>', _html()
        )
    }


def _leituras() -> list[tuple[str, aba_sistema.Leitura]]:
    estados: list[str | None] = [None, "estado-que-esta-tela-nao-conhece"]
    estados += list(aba_sistema._ESTADO_DO_HEFESTO)
    leituras: list[tuple[str, aba_sistema.Leitura]] = []
    for estado in estados:
        for nome, state in (
            ("sem state", None),
            ("pausado", {"paused": True, "controllers": []}),
            ("despachando", {"paused": False, "controllers": [{"connected": True}]}),
        ):
            leituras.append(
                (f"status={estado!r} · {nome}", aba_sistema.Leitura(status=estado, state=state))
            )
    return leituras


def _onde_diz(pacote: dict[str, Any], ident: str) -> list[str]:
    """O valor e a dica de uma linha — os dois textos que a pessoa lê."""
    linha = pacote["valores"].get(ident)
    return [] if linha is None else [linha["txt"], linha["dica"]]


def test_a_regua_sabe_onde_olhar() -> None:
    """Sem isto, um rótulo renomeado calaria o portão em silêncio."""
    linhas = _rotulos_das_linhas()
    botoes = _rotulos_dos_botoes()

    assert linhas, f"nenhuma linha de estado achada em {PAGINA.name} — a régua cegou"
    assert botoes, f"nenhum botão achado em {PAGINA.name} — a régua cegou"

    com_servico = [i for i, r in linhas.items() if "serviço" in r.lower()]
    assert com_servico, (
        "NENHUM rótulo de linha desta aba diz 'serviço' — e a decisão dela de "
        "31/08/2026 é justamente que esta aba nomeia o SERVIÇO. Ou o desenho "
        "voltou atrás (e aí é decisão dela, escrita aqui), ou esta régua "
        f"deixou de saber ler {PAGINA.name}. Rótulos vistos: {sorted(linhas.values())}"
    )
    assert [g for g, t in botoes.items() if "serviço" in t.lower()], (
        "NENHUM botão desta aba diz 'serviço' — mesma pergunta da linha acima. "
        f"Botões vistos: {botoes}"
    )
    # as nomeia é `aba_sistema.linhas_do_status` — é com ela que a página casa.
    do_produto = {linha["id"] for linha in aba_sistema.linhas_do_status(
        aba_sistema.Leitura())}
    assert set(_rotulos_das_linhas()) & do_produto, (
        "os `data-id` da página e os endereços de `aba_sistema.ENDERECOS` não "
        "se encontram mais — sem interseção, esta régua percorre o vazio"
    )


class TestOQueONomeDaLinhaObriga:
    def test_a_dica_nao_contradiz_o_rotulo(self) -> None:
        rotulos = _rotulos_das_linhas()
        alvos = {i: r for i, r in rotulos.items() if "serviço" in r.lower()}
        recaidas = []
        for caso, leitura in _leituras():
            pacote = aba_sistema.pacote(leitura)
            for ident, rotulo in alvos.items():
                for texto in _onde_diz(pacote, ident):
                    if PALAVRA in texto:
                        recaidas.append(f"[{caso}] {ident} ({rotulo!r}) diz {texto!r}")
        assert not recaidas, (
            "a linha da tela nomeia o SERVIÇO e o produto escreve 'Hefesto' na "
            "mesma linha — a tela se contradiz dentro de si mesma:\n  "
            + "\n  ".join(recaidas)
            + "\n\nA palavra 'Hefesto' ficou com a aba Jogar por decisão dela "
            "(31/08/2026), onde ela quer dizer o MODO: o Hefesto no meio do "
            "jogo, ou o aparelho puro. Quem desliga lá continua com o serviço "
            "rodando; quem para aqui mata tudo. Onde 'Hefesto' é o PROGRAMA — "
            "quem enxerga a janela, quem escreve nos controles — a palavra "
            "fica; aqui o rótulo nomeia o serviço, e a dica tem de acompanhar."
        )

    def test_o_motivo_do_botao_cinza_nao_contradiz_o_botao(self) -> None:
        """Botão "Parar o serviço" cinza não explica com "O Hefesto já está…"."""
        alvos = {g: t for g, t in _rotulos_dos_botoes().items() if "serviço" in t.lower()}
        recaidas = []
        for caso, leitura in _leituras():
            travas = aba_sistema.travas(leitura)
            for gesto, rotulo in alvos.items():
                motivo = travas.get(gesto, "")
                if PALAVRA in motivo:
                    recaidas.append(f"[{caso}] {gesto} ({rotulo!r}) diz {motivo!r}")
        assert not recaidas, (
            "o botão diz 'serviço' e o motivo de ele estar cinza diz "
            "'Hefesto' — a mesma contradição da linha de estado, no tooltip:\n"
            "  " + "\n  ".join(recaidas)
        )

    def test_o_titulo_do_botao_pode_dizer_hefesto(self) -> None:
        """O ``title`` explica a DIFERENÇA — e para isso precisa da palavra."""
        titulos = re.findall(
            r'<button[^>]*title="([^"]*)"[^>]*data-gesto="parar-ou-retomar"', _html())
        assert titulos, "o botão de parar o serviço perdeu o `title` que explica a diferença"
        assert any(PALAVRA in t for t in titulos), (
            "o `title` do botão que para o serviço deixou de citar o Hefesto. "
            "É lá — e só lá — que a diferença entre parar o SERVIÇO e desligar "
            "o HEFESTO na aba Jogar se explica. Um portão de palavra que varre "
            f"tudo apaga esta frase junto com o defeito. Títulos: {titulos}"
        )


class TestOQueFicaComOHefesto:
    """Onde "Hefesto" é o PROGRAMA, a palavra fica — e um "trocar tudo" reprova."""

    def test_quem_enxerga_a_janela_e_o_programa(self) -> None:
        vendo = ambiente_na_tela.descrever_display_grafico(
            {"window_detect_backend": "cosmic", "window_detect_seeing": True}
        )
        assert PALAVRA in vendo, (
            f"{vendo!r} — quem enxerga qual programa está na frente é o "
            "HEFESTO, não uma unidade do systemd. Esta é a metade do censo que "
            "NÃO muda (a mesma que o gerador do desenho preservou em 'o "
            "Hefesto criou N gamepads virtuais')."
        )

    def test_a_dica_sem_fonte_do_ambiente_fala_do_programa(self) -> None:
        dica = aba_sistema.linha_do_ambiente(None).dica
        assert PALAVRA in dica, (
            f"{dica!r} — 'por qual caminho o Hefesto enxerga a janela' é o "
            "MECANISMO do programa. O rótulo desta linha ('Como ele enxerga a "
            "janela') não diz 'serviço', e por isso a palavra fica."
        )


