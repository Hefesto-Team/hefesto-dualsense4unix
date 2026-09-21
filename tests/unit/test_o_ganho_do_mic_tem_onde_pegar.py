"""O-GANHO-DO-MIC-TEM-DONO-01/B — o deslizante que faltava, e o lugar dela.

Ordem dela, 20/09/2026, olhando a tela instalada:

    "o slicer tá diferente da posição de onde ficaria o slicer da
     versao  # noqa-acento: citação literal dela, e a digitação dela
            não se limpa
     original que eu havia aprovado. além disso não tá funcionando"

São duas queixas e uma falta só. O ganho nasceu naquela manhã com leitor,
barra, número, cinza e razão — e com um `<span class="cheio">` no lugar do
deslizante, na LINHA DO RÓTULO, porque ali custava zero altura. Um `span`
pinta; ele não recebe arrasto.

O desenho que ela aprovou está em
`docs/process/assets/2026-09-20-o-ganho-do-mic-como-ficaria.png`: duas linhas
EMPILHADAS no mesmo estilo, cada uma com o nome à esquerda — «Volume» e
«Ganho» —, o trilho no meio, o número e a unidade à direita.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from hefesto_dualsense4unix.interface.pacotes.a02_controles import (
    RAZAO_DO_GANHO_FORA,
    _elemento_e_ganho_do_scontents,
    _ganho_do_scontents,
    _nome_do_scontrol,
    _placa_de_cada_fonte,
)

PUBLICADO = pathlib.Path(
    "src/hefesto_dualsense4unix/interface/paginas/02-controles.html")
BANCADA = pathlib.Path("mockup/02-controles.html")
GERADOR = pathlib.Path("src/hefesto_dualsense4unix/interface/aba02.py")
PACOTE = pathlib.Path(
    "src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py")

#: Quantos cartões a página tem. O ganho é um POR CARTÃO — uma régua que mede
#: "existe pelo menos um" passa verde sobre o ganho que só o P1 recebeu, que é
#: a família `regua-que-mede-o-arranjo-facil`.
MESA = 4


@pytest.mark.parametrize("alvo", [PUBLICADO, BANCADA], ids=["publicado", "mockup"])
class TestOGanhoTemOndePegar:
    def test_ha_um_input_de_ganho_em_cada_cartao(self, alvo: pathlib.Path) -> None:
        """**A MORDIDA PRINCIPAL: troque o `<input>` por um `<span>`.**

        É literalmente o estado em que o ganho nasceu, e o defeito que ela
        reportou olhando a tela.
        """
        corpo = alvo.read_text(encoding="utf-8")
        inputs = re.findall(
            r'<input[^>]*data-gesto="ganho-mic"[^>]*>', corpo)
        assert len(inputs) == MESA, (
            f"o ganho tem {len(inputs)} deslizante(s) e devia ter {MESA} — "
            f"sem `<input type=\"range\">` a barra PINTA o valor e não há "
            f"onde pegá-la, que é a queixa dela de 20/09")
        for tag in inputs:
            assert 'type="range"' in tag, f"não é deslizante: {tag}"
            assert 'data-hef-alvo="valor"' in tag, (
                "sem o alvo `valor` o tique escreve o número como TEXTO dentro "
                f"do input, em vez de mover o cursor: {tag}")

    def test_o_ganho_desceu_para_linha_propria(self, alvo: pathlib.Path) -> None:
        """A POSIÇÃO É DELA, e ela a aprovou por imagem.

        MORDIDA: devolva o `<span class="ganho">` para dentro da `div.rot` da
        linha do rótulo — o «arranjo D», que é o que ela recusou.
        """
        corpo = alvo.read_text(encoding="utf-8")
        assert re.search(r'<div class="vol ganho"', corpo), (
            "o ganho não é uma linha de volume — ele voltou para a linha do "
            "rótulo, que é a posição que ela recusou")
        # A linha do rótulo NÃO pode voltar a hospedá-lo: o `.ganho` dentro de
        # um `<div class="rot` é exatamente o arranjo D.
        for linha_do_rotulo in re.findall(r'<div class="rot rot-linha">.*?</div>',
                                          corpo, re.S):
            assert "ganho" not in linha_do_rotulo, (
                "o ganho voltou para a linha do rótulo do Microfone")

    def test_as_duas_linhas_dizem_o_nome(self, alvo: pathlib.Path) -> None:
        """Sem o nome, são dois trilhos iguais empilhados.

        MORDIDA: tire o `<span class="rot-vol">` de uma das duas. O olho passa
        a ter de deduzir qual deslizante é qual pelo número que ele mostra —
        e os dois mostram número.
        """
        corpo = alvo.read_text(encoding="utf-8")
        for nome in ("Volume", "Ganho"):
            vistos = corpo.count(f'<span class="rot-vol">{nome}</span>')
            assert vistos == MESA, (
                f"o rótulo «{nome}» está em {vistos} lugar(es) e devia estar "
                f"em {MESA}")

    def test_a_unidade_separa_os_dois_eixos(self, alvo: pathlib.Path) -> None:
        """Um sai em por cento e o outro em decibéis.

        MORDIDA: tire o `dB`. Os dois números viram a mesma escala aos olhos de
        quem lê, e `+48` ao lado de `80` lê-se como «48 de 100».
        """
        corpo = alvo.read_text(encoding="utf-8")
        assert corpo.count('<span class="un">dB</span>') == MESA


class TestOAtoChegaAoAparelho:
    """*A cura escrita e nunca ligada* é o defeito mais caro desta casa."""

    def test_o_gesto_esta_registrado_e_chama_o_escritor(self) -> None:
        """MORDIDA: tire o decorador, ou troque a chamada por um `pass`."""
        fonte = PACOTE.read_text(encoding="utf-8")
        assert '@gesto("02-controles.html", "ganho-mic")' in fonte
        i = fonte.index("def ganho_mic(")
        corpo = fonte[i:i + 2500]
        assert "definir_ganho_do_microfone(" in corpo, (
            "o gesto não chama o escritor — é a cura escrita e nunca ligada")
        assert "RAZAO_DO_GANHO_FORA" in corpo, (
            "a recusa não tem razão, ou inventou uma segunda frase para o "
            "mesmo fato que o cinza do trilho já explica")

    def test_o_escritor_relê_o_aparelho_e_nao_devolve_o_pedido(self) -> None:
        """**A regra da casa: quando um valor tem dono, pergunte ao dono.**

        O `amixer` arredonda para o passo da placa. Devolver o que se pediu
        faria a tela publicar um número que o aparelho não tem.

        MORDIDA: devolva `(por_cento, 0.0)` sem reler.
        """
        fonte = PACOTE.read_text(encoding="utf-8")
        i = fonte.index("def definir_ganho_do_microfone(")
        corpo = fonte[i:fonte.index("\ndef ", i + 10)]
        assert corpo.count("scontents") >= 2, (
            "o escritor não relê o aparelho depois de escrever")
        assert "depois[1], depois[2]" in corpo, (
            "o retorno não é a releitura")

    def test_o_guarda_do_clique_duplo_esta_no_lugar(self) -> None:
        """Um `<input type=range>` clicado dispara `change` E `click`.

        Sem o guarda, cada clique na pista escreve DUAS vezes na placa — o
        mesmo defeito que o trilho de brilho da aba Iluminação pagou em 03/09.

        MORDIDA: tire o `return` do ramo `input`/`click`.
        """
        fonte = PACOTE.read_text(encoding="utf-8")
        i = fonte.index("def ganho_mic(")
        corpo = fonte[i:i + 2500]
        assert '"tipo"' in corpo and '"click"' in corpo, (
            "o gesto não separa o `click` que vem depois do `change`")


class TestOElementoNaoSeDigita:
    def test_o_nome_perde_as_aspas_e_guarda_o_indice(self) -> None:
        """`'Headset',0` -> `Headset,0`.

        As aspas são do `scontents`, não do nome: passá-las adiante faria o
        `amixer sset` responder «Unable to find simple control» — e o clique
        falharia com a barra pintada certa.

        MORDIDA: devolva `crua.strip()` sempre. O primeiro caso reprova.
        """
        assert _nome_do_scontrol("'Headset',0") == "Headset,0"
        assert _nome_do_scontrol("'Mic Boost',1") == "Mic Boost,1"
        assert _nome_do_scontrol("Capture,0") == "Capture,0"

    def test_o_indice_nao_se_perde(self) -> None:
        """`Headset` sem o `,0` escreve no elemento 0 de uma placa cujo ganho
        pode ser o 1 — escrita plausível no lugar errado, que é pior que erro.
        """
        assert _nome_do_scontrol("'Headset',2").endswith(",2")

    def test_o_parser_devolve_elemento_por_cento_e_db(self) -> None:
        texto = (
            "Simple mixer control 'Headset',0\n"
            "  Capabilities: cvolume cswitch\n"
            "  Capture channels: Mono\n"
            "  Mono: Capture 101 [100%] [48.00dB] [on]\n")
        assert _elemento_e_ganho_do_scontents(texto) == ("Headset,0", 100, 48.0)

    def test_os_dois_parsers_tem_corpo_unico(self) -> None:
        """Dois parsers da mesma saída é como o leitor e o escritor do mesmo
        valor começam a escolher elementos diferentes na mesma placa.

        MORDIDA: reescreva o `_ganho_do_scontents` com um laço próprio.
        """
        texto = (
            "Simple mixer control 'Mic',1\n"
            "  Capabilities: cvolume\n"
            "  Mono: Capture 40 [37%] [12.50dB] [on]\n")
        inteiro = _elemento_e_ganho_do_scontents(texto)
        assert inteiro is not None
        assert _ganho_do_scontents(texto) == (inteiro[1], inteiro[2])

    def test_sem_elemento_de_ganho_nao_se_chuta_zero(self) -> None:
        """Chutar zero pintaria «ganho no mínimo» sobre uma placa sem ganho."""
        assert _elemento_e_ganho_do_scontents(
            "Simple mixer control 'PCM',0\n  Capabilities: pvolume\n") is None
        assert _ganho_do_scontents("") is None


class TestAPlacaSaiDoServidorDeSom:
    def test_o_no_casa_com_a_placa_alsa(self) -> None:
        lista = (
            'Source #7\n'
            '\tName: alsa_input.usb-Sony-00.mono-fallback\n'
            '\t\talsa.card = "3"\n'
            'Source #9\n'
            '\tName: hefesto_mic_a0fa9c\n')
        assert _placa_de_cada_fonte(lista) == {
            "alsa_input.usb-Sony-00.mono-fallback": "3"}

    def test_lista_vazia_nao_inventa_placa(self) -> None:
        assert _placa_de_cada_fonte("") == {}
        assert _placa_de_cada_fonte("lixo\nsem nada\n") == {}


def test_a_razao_do_cinza_e_a_mesma_da_recusa() -> None:
    """Uma frase só para o mesmo fato — o trilho cinza e o clique recusado.

    Duas frases fariam a tela explicar a mesma coisa de duas maneiras, e a
    segunda envelheceria sozinha.
    """
    assert "cabo" in RAZAO_DO_GANHO_FORA.lower()
    fonte = PACOTE.read_text(encoding="utf-8")
    i = fonte.index("def ganho_mic(")
    assert "RAZAO_DO_GANHO_FORA" in fonte[i:i + 2500]
