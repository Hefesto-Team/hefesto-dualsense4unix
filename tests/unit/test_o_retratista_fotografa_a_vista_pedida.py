"""O `--vista` do retratista, e as três medidas que nasceram com ele.

**POR QUE ESTE ARQUIVO EXISTE, e a acusação é do conferente — 11/09/2026.** A
PRINTS-DAS-DEZ-01 entregou o `--vista`, o `VISTA_DELA`, a pasta
`maximizada/`, as medidas `morto_abaixo` e `vao_dos_lados`, a linha `vista:` do
recibo, e o `passa_da_dobra` deixando de comparar com um `1080` digitado.
**Nada disso tinha régua.** As três mordidas foram feitas à mão e ficaram
escritas no texto da entrega — que é onde régua nenhuma vive, e a próxima
pessoa não as tem. É o padrão que o `CLAUDE.md` nomeia com todas as letras:
*instrumento que sabe do próprio risco RESOLVE, não avisa.*

O QUE CADA CASO GUARDA
----------------------

* **o parser recusa** — `--vista 1918` aceito calado viraria uma vista
  inventada, e a foto sairia respondendo sobre outra tela;
* **a vista tem conta, e as dez fotos respondem por ela** — `VISTA_DELA` é
  `1918x840`, a conta das parcelas fica escrita, e o recibo da pasta
  `maximizada/` tem de declarar essa mesma vista: mudar a constante sem
  refotografar deixa dez imagens afirmando uma tela que ninguém tirou;
* **as duas famílias de foto não se pisam** — o `--doc` sem vista grava as dez
  do README, com vista grava as dez da maximizada, e um nome só apagaria a
  segunda calada na execução seguinte;
* **as três medidas respondem sobre a vista EM QUE ESTÃO**, e nenhuma devolve
  número negativo.

A MORDIDA — as quatro, e as quatro foram aplicadas
---------------------------------------------------

1. Troque `window.innerHeight` do `passa_da_dobra` pelo `1080` digitado, em
   `MEDIDA_NA_VISTA`: `test_a_dobra_pergunta_a_vista_em_que_esta` reprova com
   "passa 0" sobre uma página que passa 200 — a régua respondendo sobre o
   viewport de ontem, que é o defeito que a sprint achou.
2. Tire o `Math.max(0, …)` do `morto_abaixo`:
   `test_nenhuma_medida_de_sobra_sai_negativa` reprova com -200. É o achado do
   conferente: ali não SOBRA nada, ali FALTA — e o que falta já tem
   instrumento próprio.
3. Faça `destino_das_fotos` ignorar a vista (devolver sempre `DESTINO_DOC`):
   `test_a_foto_da_vista_nao_cai_por_cima_da_do_readme` reprova.
4. Faça `_vista_pedida` aceitar `int(texto)` quando não houver `x`:
   `test_o_parser_recusa_o_que_nao_e_vista` reprova.
"""

from __future__ import annotations

import ast
import importlib.util
import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
RETRATISTA = INTERFACE / "olhar.py"
CHROME = pathlib.Path("/usr/bin/google-chrome")


def _retrato() -> Any:
    """Importa o retratista como módulo, sem rodar o `main`.

    Ele faz `sys.path.insert` do próprio diretório para achar o `onde`, então o
    import basta — nenhum navegador abre, e `playwright` só é importado dentro
    das funções que fotografam.
    """
    assert RETRATISTA.is_file(), (
        f"{RETRATISTA} sumiu. Se o retratista mudou de casa, esta régua muda "
        "com ele."
    )
    espec = importlib.util.spec_from_file_location("_retrato_da_vista", RETRATISTA)
    assert espec is not None and espec.loader is not None
    modulo = importlib.util.module_from_spec(espec)
    sys.modules["_retrato_da_vista"] = modulo
    espec.loader.exec_module(modulo)
    return modulo


# ------------------------------------------------------------ o parser


def test_a_palavra_dela_resolve_para_a_vista_medida() -> None:
    """`--vista dela` não redigita número nenhum: ele tem dono em `VISTA_DELA`.

    Um número com dono, redigitado a cada execução, é um número esperando para
    envelhecer — e esta casa já pagou por isso mais de uma vez.
    """
    retrato = _retrato()
    assert retrato._vista_pedida("dela") == retrato.VISTA_DELA
    assert retrato._vista_pedida("  DELA  ") == retrato.VISTA_DELA


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("1918x840", (1918, 840)),
        ("1918X840", (1918, 840)),
        # O sinal de multiplicar, escrito por escape de propósito: o regex do
        # `_vista_pedida` aceita `[xX\u00d7]`, e a régua tem de exercitar as
        # três — mas o caractere cru aqui é ambíguo para o `ruff` (RUF001).
        ("1918\u00d7840", (1918, 840)),
        ("  1920 x 1080 ", (1920, 1080)),
    ],
)
def test_o_parser_aceita_a_forma_larguraxaltura(
    texto: str, esperado: tuple[int, int]
) -> None:
    """E o outro lado: "recusar sempre" satisfaria a mordida abaixo."""
    assert _retrato()._vista_pedida(texto) == esperado


@pytest.mark.parametrize(
    "texto", ["1918", "grande", "", "x840", "1918x", "muito x grande", "19x8"]
)
def test_o_parser_recusa_o_que_nao_e_vista(texto: str) -> None:
    """A MORDIDA: recusar é metade do trabalho deste argumento.

    Um `--vista 1918` aceito calado viraria uma vista inventada, e a foto
    sairia respondendo sobre outra tela — que é o defeito que esta sprint
    inteira existe para não repetir.
    """
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        _retrato()._vista_pedida(texto)


def test_o_main_recusa_a_vista_torta_em_vez_de_fotografar() -> None:
    """E a recusa chega até a LINHA DE COMANDO, não só até a função.

    Sem isto, `_vista_pedida` poderia estar perfeita e não estar ligada ao
    argumento — o destino de toda função escrita e nunca chamada.
    """
    with pytest.raises(SystemExit) as saiu:
        _retrato().main(["--todas", "--publicado", "--vista", "1918"])
    assert saiu.value.code == 2, (
        "o `--vista 1918` não morreu no parser. Se ele passou, o Chrome abriu "
        "numa vista inventada e a foto responde sobre outra tela."
    )


# ------------------------------------------------------- a conta da vista


def test_a_vista_dela_fecha_a_conta_das_parcelas() -> None:
    """1918x840 não é número escolhido: é a TV dela menos o que o compositor come.

    A altura foi medida pixel a pixel na foto dela (`ALTURA-DA-VISTA-01` §1); a
    largura é derivada, e está declarada como derivada na entrega. Aqui a conta
    fica ESCRITA, de modo que mexer numa parcela sem mexer no total seja
    acusado em vez de passar.

    **O QUE ESTA RÉGUA DELIBERADAMENTE NÃO FAZ, e a razão é uma decisão dela:**
    a parcela da barra tem dono vivo (`ALTURA_DA_BARRA`, no módulo da ponte,
    dentro de `gui/`), e ler o número de lá seria o jeito de nunca o redigitar.
    Não se faz: `D-0609-GTK-LEVA-INTEIRA` diz *"não apontar nada mais pra lá"*,
    e `scripts/check_nada_aponta_para_a_janela.py` reprova citação nova — o
    inventário daquela pasta **só diminui**. Uma citação a mais aqui seria mais
    uma coisa a reapontar quando o motor mudar de casa. O que segura a parcela
    no lugar dela, então, é o caso abaixo: as dez fotos declaram, no recibo, a
    vista em que nasceram.
    """
    retrato = _retrato()
    tv_larg, tv_alt = 1920, 1080
    painel, doca, borda, barra = 82, 110, 1, 46
    da_conta = (
        tv_larg - 2 * borda,
        tv_alt - painel - borda - barra - borda - doca,
    )

    medida = retrato.VISTA_DELA
    assert medida == da_conta, (
        f"`VISTA_DELA` é {medida} e a conta das parcelas dá {da_conta}. Cada "
        "parcela tem origem declarada no fonte do retratista; um total que não "
        "bate com elas é um número que perdeu o dono."
    )


def test_as_dez_fotos_da_vista_nasceram_na_vista_dela() -> None:
    """E a constante responde pelas IMAGENS que existem — não só por si mesma.

    Sem este caso, o de cima é um congelamento: quem trocasse `VISTA_DELA` e a
    conta junto passaria, e as dez fotos de `maximizada/` continuariam no
    disco afirmando uma tela que ninguém mais tira. O recibo é quem sabe — ele
    grava a `vista:` do ensaio, e é a única coisa na pasta que a sabe: nada no
    PNG diz em que viewport ele nasceu.
    """
    retrato = _retrato()
    pasta = retrato.DESTINO_DOC / retrato.SUBPASTA_DA_VISTA
    recibo = pasta / retrato.NOME_DA_PROVA
    if not recibo.is_file():
        pytest.skip(f"{pasta} ainda não foi fotografada nesta árvore")

    larg, alt = retrato.VISTA_DELA
    texto = recibo.read_text(encoding="utf-8")
    assert f"vista:   {larg}x{alt}" in texto, (
        f"o recibo de `{pasta.name}/` não declara a vista `{larg}x{alt}` que "
        "`VISTA_DELA` diz ser a dela. Ou a constante mudou e as dez fotos "
        "ficaram para trás, ou as fotos saíram de outra vista — e nos dois "
        "casos a pasta afirma uma tela que ninguém tirou.\n\n"
        "    src/hefesto_dualsense4unix/interface/olhar.py "
        "--todas --publicado --doc --vista dela\n\n"
        f"Recibo lido:\n{texto}"
    )


# --------------------------------------------- as duas famílias de foto


def test_a_foto_da_vista_nao_cai_por_cima_da_do_readme(tmp_path: pathlib.Path) -> None:
    """A MORDIDA da pasta própria: os dois destinos têm de ser DIFERENTES.

    O `CLAUDE.md` manda todo mundo rodar `--todas --publicado --doc` antes de
    commitar. Com o mesmo nome de arquivo, essa execução apagaria a foto da
    vista **calada** — sem erro, sem recibo divergente, sem nada a ver depois.
    """
    del tmp_path
    retrato = _retrato()
    do_readme = retrato.destino_das_fotos(True, None)
    da_vista = retrato.destino_das_fotos(True, retrato.VISTA_DELA)

    assert do_readme == retrato.DESTINO_DOC
    assert da_vista == retrato.DESTINO_DOC / retrato.SUBPASTA_DA_VISTA
    assert do_readme != da_vista, (
        "as duas famílias de foto estão caindo na MESMA pasta. A execução "
        "seguinte do retrato apagaria a foto da vista sem uma linha de aviso."
    )
    assert retrato.destino_das_fotos(False, retrato.VISTA_DELA) == pathlib.Path(
        "/tmp"
    ), "sem `--doc` a foto é rascunho e não pode encostar em `docs/`"


def test_o_recibo_declara_a_vista_em_que_a_foto_nasceu(
    tmp_path: pathlib.Path,
) -> None:
    """Duas fotos da mesma página em vistas diferentes são TELAS diferentes.

    Nada no PNG diz em qual delas ele nasceu. Sem a linha `vista:`, a foto da
    maximizada e o recorte de 1600x777 ficam indistinguíveis na pasta — que é a
    mesma ambiguidade que o recibo existe para desfazer entre bancada e
    produto.
    """
    retrato = _retrato()
    saida = tmp_path / "ensaio"
    saida.mkdir()
    (saida / f"{retrato.PREFIXO_NOVO}01-jogar.png").write_bytes(b"\x89PNG-de-mentira")

    retrato._gravar_prova_da_foto(
        saida,
        modo="--todas --publicado --doc --vista 1918x840",
        origem="src/hefesto_dualsense4unix/interface/paginas",
        vista="1918x840",
    )
    com_vista = (saida / retrato.NOME_DA_PROVA).read_text(encoding="utf-8")
    assert "vista:   1918x840" in com_vista, com_vista

    retrato._gravar_prova_da_foto(
        saida,
        modo="--todas --publicado --doc",
        origem="src/hefesto_dualsense4unix/interface/paginas",
    )
    sem_vista = (saida / retrato.NOME_DA_PROVA).read_text(encoding="utf-8")
    assert "vista:   recorte da .janela" in sem_vista, (
        "sem `--vista` o recibo tem de dizer que a foto é o RECORTE, e não "
        f"calar-se: um campo vazio lê-se como 'a tela inteira'.\n{sem_vista}"
    )


def test_a_vista_chega_ao_retratista_e_ao_recibo() -> None:
    """O `--vista` está LIGADO — senão as réguas acima medem código morto.

    Verificação por AST, a mesma do `test_o_modo_doc_grava_recibo`: dentro de
    `_todas` a chamada de `_retratar` tem de passar `vista=`, e a de
    `_gravar_prova_da_foto` também. Um argumento que o parser aceita e ninguém
    repassa é o `_fotografar_o_cabecalho` de novo — dez dias escrito e nunca
    ligado.
    """
    arvore = ast.parse(RETRATISTA.read_text(encoding="utf-8"))
    todas = next(
        (
            no
            for no in ast.walk(arvore)
            if isinstance(no, ast.FunctionDef) and no.name == "_todas"
        ),
        None,
    )
    assert todas is not None, "o `_todas` sumiu do retratista"

    for alvo in ("_retratar", "_gravar_prova_da_foto"):
        chamadas = [
            no
            for no in ast.walk(todas)
            if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Name)
            and no.func.id == alvo
        ]
        assert chamadas, f"o `_todas` parou de chamar `{alvo}`"
        for chamada in chamadas:
            assert "vista" in {kw.arg for kw in chamada.keywords}, (
                f"a chamada de `{alvo}` na linha {chamada.lineno} não repassa "
                "`vista=`. O argumento seria aceito na linha de comando e "
                "morreria ali — o Chrome abriria na vista de sempre, e o "
                "recibo diria 'recorte da .janela' sobre uma foto de 1918x840."
            )


# ------------------------------------- as três medidas, num Chrome de verdade


PAGINA_DE_MEDIDA = """<!doctype html><meta charset="utf-8">
<style>
  html,body{margin:0;padding:0}
  .janela{width:600px;height:%(alt)dpx;margin:0 auto;background:#123}
</style>
<div class="janela"></div>
"""


def _medir(tmp_path: pathlib.Path, altura_da_janela: int, vista: tuple[int, int]):
    """Roda o `MEDIDA_NA_VISTA` do retratista contra uma página de medida conhecida.

    A página é feita aqui de propósito: medir contra uma das dez abas amarraria
    esta régua ao desenho de hoje, e ela é sobre o INSTRUMENTO, não sobre a
    tela. `.janela` de 600 px de largura numa vista de 1000 dá 200 px de vão de
    cada lado — números que se conferem de cabeça.
    """
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    retrato = _retrato()
    alvo = tmp_path / "medida.html"
    alvo.write_text(PAGINA_DE_MEDIDA % {"alt": altura_da_janela}, encoding="utf-8")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = retrato._navegador(pw)
        try:
            pg = nav.new_page(
                viewport={"width": vista[0], "height": vista[1]},
                device_scale_factor=1,
            )
            try:
                pg.goto(f"file://{alvo}")
                return pg.evaluate(retrato.MEDIDA_NA_VISTA)
            finally:
                pg.close()
        finally:
            nav.close()


def test_a_dobra_pergunta_a_vista_em_que_esta(tmp_path: pathlib.Path) -> None:
    """A MORDIDA que a sprint achou: o `passa_da_dobra` comparava com `1080`.

    Uma `.janela` de 1000 px numa vista de 800 passa 200 da dobra. Com o `1080`
    digitado a resposta seria **0** — *uma página que transborda reportada como
    cabendo*, que é a assinatura desta casa: o instrumento respondendo sobre o
    viewport de ontem.
    """
    medido = _medir(tmp_path, altura_da_janela=1000, vista=(1000, 800))

    assert medido["vista"] == "1000x800", medido
    assert medido["passa_da_dobra"] == 200, (
        f"a dobra devolveu {medido['passa_da_dobra']} numa vista de 800 com "
        "uma página de 1000. Se veio 0, a régua voltou a comparar com uma "
        "altura digitada, e toda foto fora de 1080 passa a dizer que cabe."
    )


def test_o_morto_e_o_vao_medem_o_que_fica_fora_da_janela(
    tmp_path: pathlib.Path,
) -> None:
    """As duas medidas que nasceram para a foto maximizada, conferidas de cabeça.

    `.janela` de 600x400 numa vista de 1000x800: sobram 400 px abaixo dela e
    200 de cada lado. Nenhuma régua desta casa via esses números antes — todas
    paravam na borda da `.janela`, e a tela dela não para ali
    (`ALTURA-DA-VISTA-01` §4.3).
    """
    medido = _medir(tmp_path, altura_da_janela=400, vista=(1000, 800))

    assert medido["larg"] == 600 and medido["alt"] == 400, medido
    assert medido["morto_abaixo"] == 400, (
        f"o morto embaixo deu {medido['morto_abaixo']}; a `.janela` termina em "
        "400 e a vista tem 800."
    )
    assert medido["vao_dos_lados"] == 200, (
        f"o vão dos lados deu {medido['vao_dos_lados']}; 1000 menos 600, "
        "dividido por dois."
    )
    assert medido["passa_da_dobra"] == 0 and medido["rolagem_lateral"] is False


def test_nenhuma_medida_de_sobra_sai_negativa(tmp_path: pathlib.Path) -> None:
    """A MORDIDA DO PISO — o achado do conferente, 11/09/2026.

    Medido na vista de 1918x500, o `morto_abaixo` saía **-293**, e o `--todas`
    imprimia *"-293 px mortos embaixo"*. Ali não SOBRA nada: ali FALTA — e o
    que falta já tem instrumento próprio, o `passa_da_dobra` na altura e o
    `rolagem_lateral` na largura. Um número negativo num campo cujo nome
    promete sobra é afirmação falsa com cara de medida.

    Aqui a `.janela` tem 1000 px numa vista de 800: o rodapé dela está 200
    abaixo da borda.
    """
    medido = _medir(tmp_path, altura_da_janela=1000, vista=(1000, 800))

    assert medido["morto_abaixo"] == 0, (
        f"o morto embaixo devolveu {medido['morto_abaixo']} com a `.janela` "
        "passando da borda. Negativo aqui vira a frase '-200 px mortos "
        "embaixo' na saída do `--todas` — o instrumento afirmando sobra onde "
        "há falta."
    )
    assert medido["vao_dos_lados"] >= 0, (
        f"o vão dos lados devolveu {medido['vao_dos_lados']}. O irmão na "
        "largura tem o mesmo piso pela mesma razão; quem denuncia largura que "
        "falta é o `rolagem_lateral`."
    )


def test_a_pagina_sem_moldura_devolve_o_motivo_e_nao_um_numero(
    tmp_path: pathlib.Path,
) -> None:
    """Seletor que casou ZERO elemento é ERRO, nunca medida.

    O caso perigoso não é o estouro barulhento — é o silencioso, com um número
    inventado no lugar da medida.
    """
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    retrato = _retrato()
    alvo = tmp_path / "sem-moldura.html"
    alvo.write_text("<!doctype html><meta charset='utf-8'><p>nada</p>", encoding="utf-8")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        nav = retrato._navegador(pw)
        try:
            pg = nav.new_page(viewport={"width": 800, "height": 600})
            try:
                pg.goto(f"file://{alvo}")
                medido = pg.evaluate(retrato.MEDIDA_NA_VISTA)
            finally:
                pg.close()
        finally:
            nav.close()

    assert "erro" in medido and "não há o que medir" in medido["erro"], medido
