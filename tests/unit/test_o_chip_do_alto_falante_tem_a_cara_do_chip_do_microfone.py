#!/usr/bin/env python3
"""O CHIP DO ALTO-FALANTE TEM A CARA DO CHIP DO MICROFONE — 17/09/2026.

**A ORDEM DE PRODUTO, com um print da aba Controles na mão:** o chip «acordado» ganha o mesmo
estilo do botão MUDO acima.

Os dois moram no MESMO cartão de dispositivo, um debaixo do outro: o rótulo da
moldura do Microfone termina num chip (`MUDO` / `ATIVO`, com ícone e risco) e o
rótulo da moldura do Alto-falante trazia a palavra do canal solta, em peso 400 e
cinza, com um `·` colado na frente. Era texto ao lado de uma pílula.

**O QUE ESTA RÉGUA MEDE, e por que ela não digita nenhum nome de classe.** Três
elementos deste rótulo querem a mesma cara de chip, e a geometria dela já vivia
DUAS vezes escrita à mão no gerador. Uma régua que digitasse `padding:1px 6px`
viraria a quarta cópia e divergiria junto com as outras no primeiro ajuste —
que é exatamente a forma pela qual onze réguas desta casa já caíram. Então:

1. os **nomes de classe** saem da MARCAÇÃO, achados pelo `data-campo` de cada
   um (o endereço, que é como esta casa aponta para um campo);
2. o **que é "cara de chip"** sai da própria página: são as declarações em que o
   chip do microfone e o alarme do alto-falante — os dois que já eram pílula —
   JÁ CONCORDAM. Nada disso é digitado aqui;
3. o chip do canal tem de casar todas elas;
4. e a declaração que as escreve tem de ser **UMA**, com os três seletores
   dentro. É o que impede a terceira cópia de nascer de novo.

**A CAIXA NÃO ENTRA NA CONTA, E ISSO CUSTOU UMA VOLTA.** A primeira tentativa
desta frente subiu a caixa por CSS, para o par ficar idêntico ao do microfone. O
portão `maiuscula-decorativa` reprovou — e ele carrega a palavra de
11/09/2026, que cita ESTA palavra pelo nome: *"Leia o cabo e acordado (ambos
minusculo sem iniciar de forma capitular)."* <!-- noqa-acento: citação literal -->
As duas ordens de produto não brigam: o que o usuário pediu hoje foi o ESTILO, e a caixa do
chip do microfone não é estilo — é o TEXTO que `mesa_viva.selo_do_mic` devolve.
`TestACaixaNaoSobe` guarda o lado certo, para que ninguém "complete a
semelhança" por CSS depois.

**O PIOR DESFECHO DESTA MUDANÇA É UMA PÍLULA CINZA VAZIA**, e é o estado normal
da bancada: pelo rádio o DualSense não publica placa ALSA, o pacote manda o
marcador de "não há o que dizer" e uma regra o esconde. Sem fundo isso não se
via; com fundo, uma regra que deixe de casar põe uma pastilha vazia no cartão de
TODO controle por rádio. A régua cobra que todo chip que carrega o marcador seja
alcançado por um `display:none`.

AS MORDIDAS, feitas e devolvidas antes deste arquivo ser commitado — o vermelho
de cada uma está no relatório da frente:

* desagrupe o seletor e devolva o `.canal` ao peso 400 sem fundo —
  `test_o_chip_do_canal_tem_a_cara_que_os_dois_ja_tinham` reprova;
* mantenha os valores e só QUEBRE o agrupamento em duas cópias —
  `test_a_cara_do_chip_se_escreve_uma_vez_so` reprova;
* ponha `text-transform:uppercase` no chip do canal —
  `test_o_chip_do_canal_nao_sobe_a_caixa` reprova, e o portão
  `maiuscula-decorativa` reprova junto;
* arranque a regra do marcador — `test_o_chip_vazio_nao_aparece_no_cartao`
  reprova com a pílula vazia do controle por rádio;
* devolva o `·` ao valor — `test_o_separador_nao_entra_na_pilula` reprova.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.interface.cartao_do_controle import (
    TEXTO_SELO_SAIDA_MUDA,
)
from hefesto_dualsense4unix.interface import mesa_viva, monta, onde
from hefesto_dualsense4unix.interface.pacotes import a02_controles

sys.path.insert(0, str(RAIZ / "scripts"))
from check_a_maiuscula_decorativa import SOBE_A_CAIXA as _SOBE_A_CAIXA

PAGINA = "02-controles.html"  # (noqa-acento) nome de arquivo

CAMPO_DO_CHIP_DO_MIC = "mic-selo"
CAMPO_DO_CHIP_DO_CANAL = "alto-canal"
CAMPO_DO_ALARME = "alto-selo"

COR = ("background", "color", "background-color")


def _paginas() -> list[pathlib.Path]:
    """A bancada e o publicado."""
    return [onde.pagina(PAGINA), onde.pagina(PAGINA, publicado=True)]


def _doc(caminho: pathlib.Path) -> str:
    return caminho.read_text(encoding="utf-8")


def _pilulas(doc: str, classe: str) -> list[str]:
    """Cada pílula daquela classe, INTEIRA — conta profundidade de `<span>`."""
    fora: list[str] = []
    for abre in re.finditer(rf'<span class="{re.escape(classe)}[^"]*"', doc):
        nivel = 0
        for marca in re.finditer(r"<span\b|</span>", doc[abre.start():]):
            nivel += 1 if marca.group(0) == "<span" else -1
            if nivel == 0:
                fora.append(doc[abre.start():abre.start() + marca.end()])
                break
    return fora


def _classe_do_campo(doc: str, campo: str) -> str:
    """A classe do elemento de FORA que carrega este `data-campo`."""
    achados = re.findall(
        rf'<span class="([^"]+)"[^>]*\sdata-campo="{re.escape(campo)}"', doc)
    assert achados, (
        f"nenhum elemento com `data-campo={campo!r}` e classe na página — o "
        f"endereço mudou de forma, e esta régua deixou de olhar para o que "
        f"promete")
    return achados[0].split()[0]


def _regras(doc: str) -> list[tuple[list[str], dict[str, str]]]:
    """A folha da página em `[(seletores, {propriedade: valor})]`, em ordem."""
    folha = "".join(re.findall(r"<style[^>]*>(.*?)</style>", doc, flags=re.S))
    folha = re.sub(r"/\*.*?\*/", "", folha, flags=re.S)
    fora: list[tuple[list[str], dict[str, str]]] = []
    cabeca: list[str] = []
    pedaco = ""
    for ch in folha:
        if ch == "{":
            cabeca.append(pedaco)
            pedaco = ""
        elif ch == "}":
            if cabeca and not pedaco.strip().endswith("}"):
                bruto = cabeca[-1].strip()
                if bruto and not bruto.startswith("@"):
                    decls = {}
                    for d in pedaco.split(";"):
                        if ":" in d:
                            nome, _, valor = d.partition(":")
                            decls[nome.strip()] = " ".join(valor.split())
                    if decls:
                        fora.append(
                            ([" ".join(s.split()) for s in bruto.split(",")],
                             decls))
            if cabeca:
                cabeca.pop()
            pedaco = ""
        else:
            pedaco += ch
    return fora


def _veste(seletor: str, classe: str) -> bool:
    """Este seletor veste QUEM TEM esta classe, sem condição nenhuma?"""
    return bool(re.fullmatch(rf"[^,]*?\.{re.escape(classe)}", seletor))


def _estilo(doc: str, classe: str) -> dict[str, str]:
    """Tudo o que a folha declara, sem condição, para quem tem esta classe."""
    resolvido: dict[str, str] = {}
    for seletores, decls in _regras(doc):
        if any(_veste(s, classe) for s in seletores):
            resolvido.update(decls)
    return resolvido


def _cara_de_chip(doc: str) -> dict[str, str]:
    """O que os DOIS que já eram pílula concordam — a "cara" que o usuário apontou."""
    mic = _estilo(doc, _classe_do_campo(doc, CAMPO_DO_CHIP_DO_MIC))
    alarme = _estilo(doc, _classe_do_campo(doc, CAMPO_DO_ALARME))
    return {p: v for p, v in mic.items()
            if p not in COR and alarme.get(p) == v}


@pytest.fixture(params=["bancada", "publicado"])
def pagina(request: pytest.FixtureRequest) -> str:
    caminho = _paginas()[0 if request.param == "bancada" else 1]
    if not caminho.exists():  # pragma: no cover - a página existe nas duas
        pytest.skip(f"{caminho} não existe")
    return _doc(caminho)


class TestACaraDoChip:
    def test_os_dois_que_ja_eram_pilula_concordam_em_algo(self, pagina: str) -> None:
        """A régua não pode passar por não ter o que comparar."""
        cara = _cara_de_chip(pagina)
        assert len(cara) >= 5, (
            f"o chip do microfone e o alarme do alto-falante só concordam em "
            f"{sorted(cara)} — sem uma cara comum não há o que cobrar do "
            f"terceiro, e esta régua estaria passando por vacuidade")

    def test_o_chip_do_canal_tem_a_cara_que_os_dois_ja_tinham(
        self, pagina: str
    ) -> None:
        """*"deixar esse acordado com o mesmo estilo do botao que ta MUDO acima"*."""
        canal = _classe_do_campo(pagina, CAMPO_DO_CHIP_DO_CANAL)
        tem = _estilo(pagina, canal)
        falta = {p: v for p, v in _cara_de_chip(pagina).items()
                 if tem.get(p) != v}
        assert not falta, (
            f"o chip do canal não veste a cara dos outros dois: {falta} — e o "
            f"que ele tem é {tem}")

    def test_a_cara_do_chip_se_escreve_uma_vez_so(self, pagina: str) -> None:
        """Três cópias divergem no primeiro ajuste. Esta é a trava contra elas."""
        classes = [_classe_do_campo(pagina, c) for c in
                   (CAMPO_DO_CHIP_DO_MIC, CAMPO_DO_ALARME,
                    CAMPO_DO_CHIP_DO_CANAL)]
        espalhadas = []
        for prop in _cara_de_chip(pagina):
            juntas = any(
                prop in decls
                and all(any(_veste(s, c) for s in seletores) for c in classes)
                for seletores, decls in _regras(pagina))
            if not juntas:
                espalhadas.append(prop)
        assert not espalhadas, (
            f"{espalhadas} é declarado em regra que não alcança os três chips "
            f"({classes}) — a geometria voltou a ser cópia, e cópia diverge")


class TestACaixaNaoSobe:
    """A CARA É A PÍLULA; A CAIXA É O TEXTO — e a caixa é dela desde 11/09."""

    def test_a_caixa_do_chip_do_microfone_e_do_texto_e_nao_do_css(
        self, pagina: str
    ) -> None:
        """A premissa do caso de baixo, medida — sem ela ele guarda o nada."""
        assert mesa_viva.selo_do_mic(mudo=True, sabemos=True).isupper()
        mic = _estilo(pagina, _classe_do_campo(pagina, CAMPO_DO_CHIP_DO_MIC))
        assert mic.get("text-transform") not in _SOBE_A_CAIXA

    def test_a_palavra_do_canal_continua_a_do_daemon(self) -> None:
        """A minúscula do dono não se reescreve para caber no desenho."""
        assert audio_saida.CANAL_ACORDADO.islower()
        assert audio_saida.CANAL_DORMINDO.islower()

    def test_o_chip_do_canal_nao_sobe_a_caixa(self, pagina: str) -> None:
        """MORDE: ponha `text-transform:uppercase` no `.rot .canal`."""
        canal = _estilo(pagina, _classe_do_campo(pagina, CAMPO_DO_CHIP_DO_CANAL))
        assert canal.get("text-transform") not in _SOBE_A_CAIXA, (
            f"o chip do canal sobe a caixa por CSS "
            f"({canal.get('text-transform')!r}) — a palavra do daemon é "
            f"minúscula e é assim que ela a quer na tela desde 11/09/2026")

    def test_a_caixa_alta_nao_alcanca_o_alarme(self, pagina: str) -> None:
        """A mesma pergunta para o vizinho, cujas palavras são FRASES."""
        for frase in (TEXTO_SELO_SAIDA_MUDA,):
            assert not frase.isupper(), (
                f"{frase!r} virou caixa alta no dono — este caso guarda o "
                f"contrário, releia-o")
        alarme = _estilo(pagina, _classe_do_campo(pagina, CAMPO_DO_ALARME))
        assert alarme.get("text-transform") not in _SOBE_A_CAIXA


class TestOChipVazio:
    def test_o_marcador_continua_sendo_o_que_o_pacote_manda(self) -> None:
        """A régua de baixo lê a classe daqui; se o marcador mudar, ela erra."""
        assert a02_controles.NADA_A_DIZER == monta.NADA_A_DIZER

    def test_o_chip_vazio_nao_aparece_no_cartao(self, pagina: str) -> None:
        """Sem leitura de canal — o caso do RÁDIO — o chip não pode pintar nada."""
        marcador = re.search(r'class="([^"]+)"',
                             monta.NADA_A_DIZER).group(1).split()[0]
        canal = _classe_do_campo(pagina, CAMPO_DO_CHIP_DO_CANAL)
        esconde = [
            (seletores, decls) for seletores, decls in _regras(pagina)
            if decls.get("display") == "none"
            and any(f".{canal}" in s and f".{marcador}" in s for s in seletores)
        ]
        assert esconde, (
            f"nenhuma regra apaga `.{canal}` quando ele carrega o marcador "
            f"`.{marcador}` — no rádio o cartão ganha uma pílula vazia")

        com_marcador = _pilulas(pagina, canal)
        assert any(f'class="{marcador}"' in c for c in com_marcador), (
            "nenhum chip do canal carrega o marcador na página — a cena "
            "perdeu o lugar sem canal, e a regra de esconder deixou de "
            "guardar alguma coisa")


class TestOSeparador:
    def test_o_separador_nao_entra_na_pilula(self, pagina: str) -> None:
        """O valor é a palavra do dono, inteira e sozinha."""
        palavras = (mesa_viva.ATIVO, mesa_viva.DESLIGADO, mesa_viva.SEM_LEITOR)
        assert mesa_viva.selo_do_alto_falante(False, True) == mesa_viva.ATIVO
        canal = _classe_do_campo(pagina, CAMPO_DO_CHIP_DO_CANAL)
        escritos = _pilulas(pagina, canal)
        assert escritos, "o chip do canal sumiu da página"
        for pedaco in escritos:
            visivel = re.sub(r"<[^>]*>", "", pedaco).strip()
            assert visivel in ("", *palavras), (
                f"o chip do canal diz {visivel!r} — só a palavra do dono entra "
                f"na pílula, sem separador e sem enfeite")
