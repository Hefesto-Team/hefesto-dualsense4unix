#!/usr/bin/env python3
"""O CHIP DO ALTO-FALANTE TEM A CARA DO CHIP DO MICROFONE — 17/09/2026.

**A ORDEM DELA, com um print da aba Controles na mão:** *"deixar esse acordado
com o mesmo estilo do botao que ta MUDO acima"*. <!-- noqa-acento: citação literal dela -->

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
portão `maiuscula-decorativa` reprovou — e ele carrega a palavra dela de
11/09/2026, que cita ESTA palavra pelo nome: *"Leia o cabo e acordado (ambos
minusculo sem iniciar de forma capitular)."* <!-- noqa-acento: citação literal dela -->
As duas ordens dela não brigam: o que ela pediu hoje foi o ESTILO, e a caixa do
chip do microfone não é estilo — é o TEXTO que `mesa_viva.selo_do_mic` devolve.
`TestACaixaNaoSobe` guarda o lado certo, para que ninguém "complete a
semelhança" por CSS depois.

**O PIOR DESFECHO DESTA MUDANÇA É UMA PÍLULA CINZA VAZIA**, e é o estado normal
da mesa dela: pelo rádio o DualSense não publica placa ALSA, o pacote manda o
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

from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.app.widgets.controller_card import (
    TEXTO_SELO_CANAL_DORMINDO,
    TEXTO_SELO_SAIDA_MUDA,
)
from hefesto_dualsense4unix.interface import mesa_viva, monta, onde
from hefesto_dualsense4unix.interface.pacotes import a02_controles

sys.path.insert(0, str(RAIZ / "scripts"))
from check_a_maiuscula_decorativa import SOBE_A_CAIXA as _SOBE_A_CAIXA

PAGINA = "02-controles.html"  # (noqa-acento) nome de arquivo

#: OS TRÊS ENDEREÇOS, e só eles são digitados aqui. `data-campo` é o vocabulário
#: de endereço desta casa — o mesmo que o piloto usa para achar o elemento —, e
#: é por ele que se chega à classe SEM escrever a classe.
CAMPO_DO_CHIP_DO_MIC = "mic-selo"
CAMPO_DO_CHIP_DO_CANAL = "alto-canal-porque"
CAMPO_DO_ALARME = "alto-selo"

#: A COR É O QUE SEPARA OS ESTADOS, e por isso ela não entra na conta do que os
#: três têm de compartilhar: o chip do microfone aceso é verde, o alarme é
#: laranja e o chip do canal é neutro. O resto — fonte, respiro, raio, peso — é
#: a "cara de chip", e é o que ela pediu.
COR = ("background", "color", "background-color")


# ---------------------------------------------------------------------------
# A LEITURA — a marcação primeiro, a folha depois
# ---------------------------------------------------------------------------


def _paginas() -> list[pathlib.Path]:
    """A bancada e o publicado.

    OS DOIS, E NÃO SÓ UM: a bancada é o desenho de hoje e o publicado é o que a
    janela dela renderiza. Medir só a bancada deixaria a régua VERDE com a tela
    dela ainda no chip velho — a armadilha mais cara desta casa —, e medir só o
    publicado daria verde sobre a página congelada.
    """
    return [onde.pagina(PAGINA), onde.pagina(PAGINA, publicado=True)]


def _doc(caminho: pathlib.Path) -> str:
    return caminho.read_text(encoding="utf-8")


def _classe_do_campo(doc: str, campo: str) -> str:
    """A classe do elemento de FORA que carrega este `data-campo`.

    O chip do microfone são TRÊS `<span>` aninhados com o mesmo endereço (a
    pílula, o glifo e a palavra); o de fora é o primeiro em ordem de documento,
    porque é dentro dele que os outros nascem. Dos nomes de classe do elemento
    fica o PRIMEIRO: o segundo, quando existe, é o estado (o piloto acende e
    apaga), e estado não é cara.
    """
    achados = re.findall(
        rf'<span class="([^"]+)"[^>]*\sdata-campo="{re.escape(campo)}"', doc)
    assert achados, (
        f"nenhum elemento com `data-campo={campo!r}` e classe na página — o "
        f"endereço mudou de forma, e esta régua deixou de olhar para o que "
        f"promete")
    return achados[0].split()[0]


def _regras(doc: str) -> list[tuple[list[str], dict[str, str]]]:
    """A folha da página em `[(seletores, {propriedade: valor})]`, em ordem.

    UM VARREDOR COM PROFUNDIDADE, e não um `re.findall` de `{...}`: a folha tem
    `@media` e `@keyframes`, e um casamento raso costura o fim de um at-rule no
    começo do seletor seguinte.
    """
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
    """Este seletor veste QUEM TEM esta classe, sem condição nenhuma?

    Só conta o seletor cujo último passo é a classe sozinha: `.canal`,
    `.rot .canal`. Ficam de fora o composto de estado (`.selo-ativo.on`) e as
    regras condicionais (`:has(...)`, `:empty`), que são outra pergunta.
    """
    return bool(re.fullmatch(rf"[^,]*?\.{re.escape(classe)}", seletor))


def _estilo(doc: str, classe: str) -> dict[str, str]:
    """Tudo o que a folha declara, sem condição, para quem tem esta classe."""
    resolvido: dict[str, str] = {}
    for seletores, decls in _regras(doc):
        if any(_veste(s, classe) for s in seletores):
            resolvido.update(decls)
    return resolvido


def _cara_de_chip(doc: str) -> dict[str, str]:
    """O que os DOIS que já eram pílula concordam — a "cara" que ela apontou.

    Ela não está escrita aqui: sai da página, do encontro entre o chip do
    microfone e o alarme do alto-falante. É isso que impede esta régua de virar
    a quarta cópia digitada da geometria.
    """
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


# ---------------------------------------------------------------------------
# 1. A CARA — o pedido dela, medido
# ---------------------------------------------------------------------------


class TestACaraDoChip:
    def test_os_dois_que_ja_eram_pilula_concordam_em_algo(self, pagina: str) -> None:
        """A régua não pode passar por não ter o que comparar.

        Se o chip do microfone e o alarme deixarem de compartilhar geometria, o
        conjunto vazio faria todo o resto deste arquivo ficar VERDE sobre nada —
        que é a família de instrumento falso que esta casa mais pegou.
        """
        cara = _cara_de_chip(pagina)
        assert len(cara) >= 5, (
            f"o chip do microfone e o alarme do alto-falante só concordam em "
            f"{sorted(cara)} — sem uma cara comum não há o que cobrar do "
            f"terceiro, e esta régua estaria passando por vacuidade")

    def test_o_chip_do_canal_tem_a_cara_que_os_dois_ja_tinham(
        self, pagina: str
    ) -> None:
        """*"deixar esse acordado com o mesmo estilo do botao que ta MUDO acima"*.

        MORDE: devolva `.rot .canal` ao peso 400 sem fundo e sem respiro.
        """
        canal = _classe_do_campo(pagina, CAMPO_DO_CHIP_DO_CANAL)
        tem = _estilo(pagina, canal)
        falta = {p: v for p, v in _cara_de_chip(pagina).items()
                 if tem.get(p) != v}
        assert not falta, (
            f"o chip do canal não veste a cara dos outros dois: {falta} — e o "
            f"que ele tem é {tem}")

    def test_a_cara_do_chip_se_escreve_uma_vez_so(self, pagina: str) -> None:
        """Três cópias divergem no primeiro ajuste. Esta é a trava contra elas.

        Cada declaração da cara comum tem de sair de UMA regra que nomeie os
        três. Valores iguais em três regras separadas passam no caso de cima e
        divergem amanhã.

        MORDE: mantenha os valores e só desagrupe o seletor.
        """
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


# ---------------------------------------------------------------------------
# 2. A CAIXA — decisão de CSS, nunca do texto
# ---------------------------------------------------------------------------


class TestACaixaNaoSobe:
    """A CARA É A PÍLULA; A CAIXA É O TEXTO — e a caixa é dela desde 11/09.

    A primeira tentativa desta frente pôs `text-transform:uppercase` no chip do
    canal, para o par ficar idêntico ao do microfone. O portão
    `maiuscula-decorativa` reprovou, e ele carrega a palavra dela citando ESTA
    palavra pelo nome: *"Leia o cabo e acordado (ambos minusculo sem
    iniciar de forma capitular). Esse tipo de coisa
    nao pode se repetir na interface."*  # noqa-acento: citação dela

    AS DUAS ORDENS DELA NÃO BRIGAM: ela pediu o ESTILO, e a caixa do chip do
    microfone não é estilo — é o TEXTO que `mesa_viva.selo_do_mic` devolve. Este
    caso é o que impede a próxima pessoa de "completar a semelhança" por CSS e
    trazer de volta a mesma palavra com duas grafias.
    """

    def test_a_caixa_do_chip_do_microfone_e_do_texto_e_nao_do_css(
        self, pagina: str
    ) -> None:
        """A premissa do caso de baixo, medida — sem ela ele guarda o nada.

        Se a caixa alta do chip do microfone passar a vir do CSS, "mesmo estilo"
        deixa de significar "mesma pílula, caixa diferente", e todo o argumento
        desta classe cai.
        """
        assert mesa_viva.selo_do_mic(mudo=True, sabemos=True).isupper()
        mic = _estilo(pagina, _classe_do_campo(pagina, CAMPO_DO_CHIP_DO_MIC))
        assert mic.get("text-transform") not in _SOBE_A_CAIXA

    def test_a_palavra_do_canal_continua_a_do_daemon(self) -> None:
        """A minúscula do dono não se reescreve para caber no desenho.

        `audio_saida` traduz o `RUNNING`/`IDLE` do `pactl`, e a moldura da GTK
        escreve a mesma palavra. Subir a caixa no TEXTO mudaria o vocabulário do
        daemon para resolver um problema de tela.
        """
        assert audio_saida.CANAL_ACORDADO.islower()
        assert audio_saida.CANAL_DORMINDO.islower()

    def test_o_chip_do_canal_nao_sobe_a_caixa(self, pagina: str) -> None:
        """MORDE: ponha `text-transform:uppercase` no `.rot .canal`.

        AS FORMAS QUE SOBEM A CAIXA SÃO LIDAS DO PORTÃO, não digitadas: ele é o
        dono dessa lista, e uma segunda cópia aqui divergiria dele no dia em que
        ele ganhasse uma terceira forma.
        """
        canal = _estilo(pagina, _classe_do_campo(pagina, CAMPO_DO_CHIP_DO_CANAL))
        assert canal.get("text-transform") not in _SOBE_A_CAIXA, (
            f"o chip do canal sobe a caixa por CSS "
            f"({canal.get('text-transform')!r}) — a palavra do daemon é "
            f"minúscula e é assim que ela a quer na tela desde 11/09/2026")

    def test_a_caixa_alta_nao_alcanca_o_alarme(self, pagina: str) -> None:
        """A mesma pergunta para o vizinho, cujas palavras são FRASES."""
        for frase in (TEXTO_SELO_SAIDA_MUDA, TEXTO_SELO_CANAL_DORMINDO):
            assert not frase.isupper(), (
                f"{frase!r} virou caixa alta no dono — este caso guarda o "
                f"contrário, releia-o")
        alarme = _estilo(pagina, _classe_do_campo(pagina, CAMPO_DO_ALARME))
        assert alarme.get("text-transform") not in _SOBE_A_CAIXA


# 3. A PÍLULA VAZIA — o pior desfecho, e é o estado normal da mesa dela
# ---------------------------------------------------------------------------


class TestOChipVazio:
    def test_o_marcador_continua_sendo_o_que_o_pacote_manda(self) -> None:
        """A régua de baixo lê a classe daqui; se o marcador mudar, ela erra."""
        assert a02_controles.NADA_A_DIZER == monta.NADA_A_DIZER

    def test_o_chip_vazio_nao_aparece_no_cartao(self, pagina: str) -> None:
        """Sem leitura de canal — o caso do RÁDIO — o chip não pode pintar nada.

        Antes isto era invisível: texto sem fundo não se vê vazio. Com fundo,
        uma regra que deixe de casar põe uma pastilha cinza VAZIA no cartão de
        todo controle por rádio, que é metade da mesa dela.

        MORDE: arranque a regra do marcador no gerador.
        """
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

        # E O MARCADOR TEM DE ESTAR LÁ, senão a regra acima guarda um caso que
        # a página não produz.
        com_marcador = re.findall(
            rf'<span class="{re.escape(canal)}"[^>]*>(.*?)</span></span>',
            pagina)
        assert any(f'class="{marcador}"' in c for c in com_marcador), (
            "nenhum chip do canal carrega o marcador na página — a cena "
            "perdeu o controle por rádio, e a regra de esconder deixou de "
            "guardar alguma coisa")


# ---------------------------------------------------------------------------
# 4. O SEPARADOR — ele era do rótulo, e a pílula o dispensa
# ---------------------------------------------------------------------------


class TestOSeparador:
    def test_o_separador_nao_entra_na_pilula(self, pagina: str) -> None:
        """O valor é a palavra do dono, inteira e sozinha.

        Um `·` colado dentro de uma pílula lê como sujeira: a pílula já é a
        separação. O dono é `a02_controles.sufixo_do_canal`, e ele tem um
        consumidor só — esta tela; a moldura da GTK usa constantes próprias.

        MORDE: devolva o `·` ao valor do dono.
        """
        assert (a02_controles.sufixo_do_canal(audio_saida.CANAL_ACORDADO)
                == audio_saida.CANAL_ACORDADO)
        canal = _classe_do_campo(pagina, CAMPO_DO_CHIP_DO_CANAL)
        escritos = re.findall(
            rf'<span class="{re.escape(canal)}"[^>]*>(.*?)</span></span>',
            pagina)
        assert escritos, "o chip do canal sumiu da página"
        for pedaco in escritos:
            visivel = re.sub(r"<[^>]*>", "", pedaco).strip()
            assert visivel in ("", audio_saida.CANAL_ACORDADO,
                               audio_saida.CANAL_DORMINDO), (
                f"o chip do canal diz {visivel!r} — só a palavra do dono entra "
                f"na pílula, sem separador e sem enfeite")
