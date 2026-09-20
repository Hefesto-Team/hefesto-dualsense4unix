"""A CATRACA DA TRADUÇÃO MORDE — as cinco mordidas da TRADUZIR-O-PROJETO-01.

Régua que passa com a cura arrancada não mede nada. Aqui cada mordida ARRANCA
a cura, vê reprovar, e devolve — e o que cada uma arranca está escrito no
docstring do teste, não só no nome dele.

AS CINCO, E A QUARTA É A QUE ESTA CASA MAIS ESQUECE
----------------------------------------------------
1. **A frase nova sem endereço** — na verdade, a propriedade que ela mede: *uma
   trava que se mede contra a própria saída não trava nada*. O que se arranca é
   a comparação com o piso GRAVADO, trocando-a por uma comparação do censo com
   ele mesmo. Medido em 07/09/2026: a régua que devia impedir o CSV de perder
   colunas comparava o arquivo novo com ele mesmo e passou verde enquanto o
   mapa perdia 50 colunas.
2. **O arquivo fora de zona** — o que se arranca é a exigência de REGRA:
   aceitar o não-classificado como CODIGO por omissão. *Omissão que vira
   default silencioso é como uma fronteira deixa de existir.*
3. **O comentário novo no byte publicado** — o que se arranca é o piso.
4. **A MORDIDA DO VAZIO** — o que se arranca é a peneira do universo. Esta casa
   mediu o mesmo defeito em quatro instrumentos diferentes: *o portão escolhia
   a venv pela POSIÇÃO*; *as pastas mudaram de nome e as réguas não foram
   junto*; *lote montado da árvore ERRADA morre calado, e `no tests ran` lê-se
   como limpo*; *o `--prova-gesto` nunca clicava o botão do microfone e dava
   verde sobre dois botões mortos*. **O conjunto vazio nunca é a resposta
   certa.**
5. **O PENDENTE** — o que se arranca é a recusa de comparar: tratar a medida
   que não pode medir como se ela tivesse devolvido zero. *Zero se lê como
   verde.*

E DUAS QUE A §7 NÃO PEDIU E QUE O DESENHO EXIGE: a medida que ACORDA (piso
PENDENTE sobre um censo que passou a medir reprova sozinha, em vez de esperar
alguém reparar) e o `--aceitar` que se recusa a SUBIR piso.

ONDE CADA MORDIDA RODA, E POR QUE NÃO NA ÁRVORE DE VERDADE
-----------------------------------------------------------
As mordidas que precisam MUDAR um arquivo rodam contra uma árvore em
miniatura, montada em `tmp_path` com exatamente o que cada medida lê. Mexer na
árvore de verdade para ver uma régua reprovar deixaria o estrago no disco de
quem rodou a suíte — e a árvore de trabalho é o que roda.

A §7.3 pede o comentário acrescentado ao GERADOR e a página republicada. Aqui
ele é acrescentado à página publicada, que é o mesmo byte que o WebKit baixa e
o que a medida lê; republicar de verdade abriria o Chrome, e a tela é dela.

A §7.2 pede o arquivo `docs/uma-pagina-nova.md`. Medido nesta árvore: `docs/`
já tem prosa na raiz (o glossário da casa), e a regra que a alcança é
`docs/*.md` — que alcançaria também aquele nome. Cobrir o glossário por NOME
seria a exceção por nome que a própria sprint proíbe, então a mordida usa um
caminho que nenhuma regra alcança de verdade. A propriedade medida é a mesma.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "check_o_projeto_e_traduzivel.py"
MOTOR = RAIZ / "scripts" / "catraca.py"


def _carregar(caminho: Path, nome: str):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


catraca = _carregar(MOTOR, "_catraca_sob_teste")
chk = _carregar(SCRIPT, "_check_traduzivel_sob_teste")


# ---------------------------------------------------------------------------
# A árvore em miniatura
# ---------------------------------------------------------------------------
_PAGINA = """<!doctype html>
<html><head>
<!-- um comentário de HTML, que conta -->
<style>
/* UM BLOCO DE RAZÃO DATADA, que é o que a medida 3 persegue */
body { content: "/* isto NÃO é comentário: mora dentro de uma string */"; }
</style>
</head><body>
<h1>A aba de mentira</h1>
<button title="a dica do botão">Aplicar</button>
<script>/* comentário de JS, que a medida NÃO conta, e a razão está no fonte */</script>
</body></html>
"""

_ZONAS = """
[[regra]]
caminho = "src/hefesto_dualsense4unix/interface/paginas/**"
zona = "TELA"
razao = "as páginas publicadas."

[[regra]]
caminho = "src/**"
zona = "CODIGO"
razao = "o resto do produto."

[[regra]]
caminho = "docs/data/**"
zona = "ENSINA"
razao = "as planilhas com dono."

[[regra]]
caminho = ".github/**"
zona = "ENSINA"
razao = "fala com quem contribui."
"""


def _arvore(tmp_path: Path, *, com_zonas: bool = True, quantas: int = 1) -> Path:
    raiz = tmp_path / "arvore"
    (raiz / "docs" / "data").mkdir(parents=True)
    # Os dois endereços vêm do DONO deles — o script —, nunca digitados aqui:
    # o dia em que a pasta das páginas mudar de lugar, a miniatura vai junto.
    (raiz / chk.PAGINAS).mkdir(parents=True)
    for n in range(1, quantas + 1):
        (raiz / chk.GERADORES / f"aba{n:02d}.py").write_text(
            "# gerador de mentira\n", encoding="utf-8"
        )
        (raiz / chk.PAGINAS / f"{n:02d}-aba.html").write_text(_PAGINA, encoding="utf-8")
    if com_zonas:
        (raiz / "docs" / "data" / "zonas-de-lingua.toml").write_text(_ZONAS, encoding="utf-8")
    # A conferência do CONTRIBUTING roda junto das três medidas, então a
    # miniatura precisa dela também — senão a mordida mediria a ausência do
    # documento em vez da catraca.
    (raiz / chk.ACOES).mkdir(parents=True)
    (raiz / chk.ACOES / "um.py").write_text('X = "ação"\n', encoding="utf-8")
    (raiz / ".github").mkdir()
    (raiz / chk.CONTRIBUINDO).write_text(
        f"# de mentira\n\n{chk.MARCA_ABRE} -->\n{chk.MARCA_FECHA}\n", encoding="utf-8"
    )
    chk.conferir_contribuindo(raiz, publicar=True)
    return raiz


def _motor(raiz: Path) -> catraca.Catraca:
    return catraca.Catraca(
        caderno=raiz / chk.CADERNO, medidas=chk.MEDIDAS, raiz=raiz
    )


def _estados(raiz: Path) -> dict[str, str]:
    return {v.medida.nome: v.estado for v in _motor(raiz).comparar()}


def _rodar(raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--raiz", str(raiz), *args],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# MORDIDA 1 — a trava que se mede contra a própria saída
# ---------------------------------------------------------------------------
def test_mordida_1_a_catraca_compara_com_o_piso_do_disco_e_nao_consigo_mesma(
    tmp_path: Path,
) -> None:
    """O QUE A MORDIDA ARRANCA: a comparação com o piso GRAVADO.

    O piso é gravado numa execução, o fonte muda, e a comparação roda em OUTRA
    execução, lendo o caderno do disco. Arrancada a cura — trocando a leitura
    do disco por uma comparação do censo com ele mesmo, que é o defeito de
    07/09/2026 —, a mesma mudança passa VERDE.
    """
    raiz = _arvore(tmp_path)
    motor = _motor(raiz)
    motor.aceitar(["prosa-publicada"], "piso da mordida")

    pagina = raiz / chk.PAGINAS / "01-aba.html"
    pagina.write_text(
        pagina.read_text(encoding="utf-8").replace(
            "</style>", "/* " + "prosa nova datada " * 120 + "*/\n</style>"
        ),
        encoding="utf-8",
    )

    vereditos = {v.medida.nome: v for v in _motor(raiz).comparar(["prosa-publicada"])}
    v = vereditos["prosa-publicada"]
    assert v.estado == catraca.VERMELHO, "a prosa publicada subiu e a catraca calou"
    assert v.numero is not None and v.piso.numero is not None
    assert v.numero > v.piso.numero
    # E ela diz O QUE ENTROU, com a página e o delta — nunca só o número.
    assert any("01-aba.html" in linha for linha in v.entrou), v.entrou

    # --- A CURA ARRANCADA: comparar o censo com ele mesmo -----------------
    class _ContraAPropriaSaida(catraca.Catraca):
        def _comparar_uma(self, medida):  # type: ignore[no-untyped-def]
            censo = medida.censo(self.raiz)
            piso = catraca.Piso(
                numero=censo.numero, data="hoje", razao="o próprio censo"
            )
            return catraca.Veredito(medida, catraca.VERDE, censo.numero, piso, censo)

    arrancada = _ContraAPropriaSaida(
        caderno=raiz / chk.CADERNO, medidas=chk.MEDIDAS, raiz=raiz
    )
    assert (
        arrancada.comparar(["prosa-publicada"])[0].estado == catraca.VERDE
    ), "com a cura arrancada a régua tinha de PASSAR — se não passa, ela não é a cura"


# ---------------------------------------------------------------------------
# MORDIDA 2 — o arquivo fora de zona
# ---------------------------------------------------------------------------
def test_mordida_2_arquivo_que_nenhuma_regra_alcanca_reprova(tmp_path: Path) -> None:
    """O QUE A MORDIDA ARRANCA: a exigência de REGRA.

    Com a regra pega-tudo `**` no fim da tabela — que é "aceitar como CODIGO
    por omissão" —, o arquivo fora de zona passa VERDE, e a próxima pessoa
    nunca mais declara zona nenhuma.
    """
    raiz = _arvore(tmp_path)
    motor = _motor(raiz)
    motor.aceitar(["fronteira-de-lingua"], "piso da mordida")
    assert _estados(raiz)["fronteira-de-lingua"] == catraca.VERDE

    (raiz / "traducoes").mkdir()
    (raiz / "traducoes" / "uma-pagina-nova.md").write_text("prosa\n", encoding="utf-8")

    v = _motor(raiz).comparar(["fronteira-de-lingua"])[0]
    assert v.estado == catraca.VERMELHO
    assert v.numero == 1
    assert any("traducoes/uma-pagina-nova.md" in linha for linha in v.entrou), v.entrou

    # --- A CURA ARRANCADA: a regra pega-tudo ------------------------------
    zonas = raiz / chk.ZONAS
    zonas.write_text(
        zonas.read_text(encoding="utf-8")
        + '\n[[regra]]\ncaminho = "**"\nzona = "CODIGO"\nrazao = "o resto, por omissão."\n',
        encoding="utf-8",
    )
    assert (
        _estados(raiz)["fronteira-de-lingua"] == catraca.VERDE
    ), "com o pega-tudo a fronteira tinha de sumir — e é por isso que ele não existe"


def test_a_tabela_de_zonas_da_arvore_de_verdade_nao_tem_pega_tudo() -> None:
    """A régua da régua: um `**` solto na tabela desligaria a medida 1 calado."""
    regras, _ = chk.carregar_zonas(RAIZ)
    assert regras, "a tabela de zonas sumiu da árvore"
    assert not [r for r in regras if r.caminho.strip() in {"**", "*", "**/*"}]


def test_toda_regra_de_zona_diz_a_razao_e_uma_das_quatro_zonas() -> None:
    """Regra sem razão é lista de arquivo com outro nome."""
    regras, _ = chk.carregar_zonas(RAIZ)
    for regra in regras:
        assert regra.zona in chk.ZONAS_VALIDAS, regra.caminho
        assert regra.razao.strip(), regra.caminho


# ---------------------------------------------------------------------------
# MORDIDA 3 — o comentário novo no byte publicado
# ---------------------------------------------------------------------------
def test_mordida_3_comentario_novo_na_pagina_publicada_reprova_pelo_script(
    tmp_path: Path,
) -> None:
    """O QUE A MORDIDA ARRANCA: o piso.

    Esta roda o SCRIPT de verdade, por subprocesso, contra a árvore em
    miniatura: é a superfície que o portão executa, e uma mordida que só
    exercita a função por dentro não prova que o portão reprova.
    """
    raiz = _arvore(tmp_path)
    assert _rodar(raiz, "--aceitar").returncode == 0

    pagina = raiz / chk.PAGINAS / "01-aba.html"
    pagina.write_text(
        pagina.read_text(encoding="utf-8").replace(
            "</style>", "/*" + "x" * 2048 + "*/\n</style>"
        ),
        encoding="utf-8",
    )

    vermelho = _rodar(raiz)
    assert vermelho.returncode == 1, vermelho.stdout + vermelho.stderr
    assert "prosa-publicada" in vermelho.stdout
    assert "01-aba.html" in vermelho.stdout, vermelho.stdout

    # --- A CURA ARRANCADA: o piso ----------------------------------------
    # E o caminho fácil está fechado: `--aceitar` RECUSA subir. Quem quiser o
    # verde escreve a razão, e a razão fica no diff de quem revisa.
    recusa = _rodar(raiz, "--aceitar", "prosa-publicada")
    assert recusa.returncode != 0 and "só desce" in recusa.stderr + recusa.stdout
    assert _rodar(raiz, "--forcar-piso", "prosa-publicada", "a mordida").returncode == 0
    assert _rodar(raiz).returncode == 0


def test_o_comentario_de_css_nao_conta_o_que_mora_dentro_de_uma_string() -> None:
    """PERGUNTE AO PARSER, não ao regex.

    Os 33,1% da sprint vieram de expressão regular sobre texto cru, que casa
    `/*` dentro de uma string CSS. Esta é a diferença entre as duas leituras,
    escrita como caso: a folha abaixo tem UM comentário, e a string que o
    imita não é um segundo.
    """
    css = 'a { content: "/* não sou comentário */"; } /* eu sou */'
    achados = chk.comentarios_css(css)
    assert achados == ["/* eu sou */"], achados


# ---------------------------------------------------------------------------
# MORDIDA 4 — A MORDIDA DO VAZIO
# ---------------------------------------------------------------------------
def test_mordida_4_universo_vazio_reprova_em_vez_de_dar_verde(tmp_path: Path) -> None:
    """O QUE A MORDIDA ARRANCA: a peneira do universo.

    Sem ela, o zero de uma pasta vazia chega à comparação (`0 <= piso`) e passa
    VERDE — que é o portão desligado sem ninguém notar.
    """
    vazia = tmp_path / "vazia"
    vazia.mkdir()

    resultado = _rodar(vazia)
    assert resultado.returncode == 1, resultado.stdout + resultado.stderr
    assert catraca.IMPOSSIVEL in resultado.stdout, resultado.stdout

    # --- A CURA ARRANCADA: a comparação crua, sem peneira nenhuma ---------
    class _SemAPeneiraDoVazio(catraca.Catraca):
        def _comparar_uma(self, medida):  # type: ignore[no-untyped-def]
            piso = self.ler_piso(medida.nome)
            censo = medida.censo(self.raiz)
            numero = 0 if censo.numero is None else censo.numero
            base = 0 if piso.numero is None else piso.numero
            estado = catraca.VERDE if numero <= base else catraca.VERMELHO
            return catraca.Veredito(medida, estado, numero, piso, censo)

    arrancada = _SemAPeneiraDoVazio(
        caderno=vazia / chk.CADERNO, medidas=chk.MEDIDAS, raiz=vazia
    )
    assert {v.estado for v in arrancada.comparar()} == {catraca.VERDE}, (
        "com a peneira arrancada a pasta vazia tinha de ficar VERDE — e é "
        "exatamente esse verde que a peneira existe para não deixar acontecer"
    )


def test_mordida_4_pagina_que_some_e_vermelho_e_nao_um_numero_menor(
    tmp_path: Path,
) -> None:
    """O QUE A MORDIDA ARRANCA: a pergunta ao DONO de quantas abas existem.

    O dono é a pasta dos geradores, não um número digitado na régua. Com três
    geradores e uma página no disco, a medida acharia menos prosa — e menos
    prosa lê-se como melhora. Aqui ela reprova.
    """
    raiz = _arvore(tmp_path, quantas=3)
    assert _rodar(raiz, "--aceitar").returncode == 0
    (raiz / chk.PAGINAS / "03-aba.html").unlink()

    v = {x.medida.nome: x for x in _motor(raiz).comparar()}["prosa-publicada"]
    assert v.estado == catraca.IMPOSSIVEL
    assert "gerador" in " ".join(v.queixas)


def test_o_motor_recusa_gravar_piso_sobre_universo_vazio(tmp_path: Path) -> None:
    """Gravar o silêncio como fato é pior do que não ter piso."""
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    with pytest.raises(catraca.CatracaTorta):
        _motor(vazia).aceitar(["prosa-publicada"], "não deveria passar")


# ---------------------------------------------------------------------------
# MORDIDA 5 — o PENDENTE
# ---------------------------------------------------------------------------
def test_mordida_5_pendente_nunca_e_verde_na_arvore_de_verdade() -> None:
    """O QUE A MORDIDA ARRANCA: a recusa de comparar o que não se mede.

    Hoje não existe forma de endereço de tradução neste projeto, e a medida da
    tela diz isso em vez de devolver zero. O estado é PENDENTE, **nunca**
    VERDE: a diferença entre as duas palavras é a diferença entre "não mediu" e
    "mediu e está limpo".
    """
    vereditos = {v.medida.nome: v for v in chk.montar(RAIZ).comparar()}
    v = vereditos["tela-sem-endereco"]
    assert v.estado == catraca.ESTADO_PENDENTE
    assert v.estado != catraca.VERDE
    assert v.numero is None, "medida pendente não devolve número"
    assert "endereco_de_traducao" in " ".join(v.queixas)


def test_mordida_5_tratar_pendente_como_zero_daria_verde_sobre_nada(
    tmp_path: Path,
) -> None:
    """O QUE A MORDIDA ARRANCA: o `None` de quem não pode medir, virando `0`.

    Esta é a forma exata do defeito que a §7.5 descreve. Uma medida que
    devolvesse `0` em vez de se declarar indisponível ganharia um piso `0` e
    ficaria VERDE para sempre, medindo nada.
    """
    raiz = _arvore(tmp_path)

    def censo_que_mente(_: Path) -> catraca.Censo:
        return catraca.Censo(numero=0, universo=1)

    mentirosa = catraca.Medida(
        nome="tela-sem-endereco",
        o_que_conta="a versão que devolve zero quando não sabe medir",
        censo=censo_que_mente,
    )
    motor = catraca.Catraca(
        caderno=raiz / chk.CADERNO, medidas=[mentirosa], raiz=raiz
    )
    motor.aceitar(["tela-sem-endereco"], "o piso do zero")
    assert motor.comparar()[0].estado == catraca.VERDE, (
        "com o zero no lugar do None, o portão fica verde sobre uma medida "
        "desligada — que é o defeito inteiro"
    )


def test_o_motor_recusa_a_forma_que_esconde_o_defeito() -> None:
    """Instrumento que sabe do próprio risco RESOLVE, não avisa.

    `numero` e `indisponivel` andam juntos. Devolver `0` **e** uma razão é a
    forma que deixaria a próxima pessoa escolher entre as duas — e ela
    escolheria o número.
    """
    with pytest.raises(catraca.CatracaTorta):
        catraca.Censo(numero=0, universo=1, indisponivel="não sei medir")
    with pytest.raises(catraca.CatracaTorta):
        catraca.Censo(numero=None, universo=1)


def test_pendente_sem_razao_escrita_estoura(tmp_path: Path) -> None:
    """Pendência sem razão é portão desligado com aparência de decisão."""
    raiz = _arvore(tmp_path)
    caderno = raiz / chk.CADERNO
    caderno.parent.mkdir(parents=True, exist_ok=True)
    caderno.write_text(
        json.dumps({"medidas": {"prosa-publicada": {"piso": "PENDENTE"}}}),
        encoding="utf-8",
    )
    with pytest.raises(catraca.CatracaTorta):
        _motor(raiz).ler_piso("prosa-publicada")


# ---------------------------------------------------------------------------
# AS DUAS QUE O DESENHO EXIGE E A §7 NÃO PEDIU
# ---------------------------------------------------------------------------
def test_a_medida_que_acorda_reprova_sozinha(tmp_path: Path) -> None:
    """O dia em que o encanamento existir, o portão AVISA — e não fica calado.

    Aviso no cabeçalho de um comando que termina verde ninguém lê. Por isso a
    medida pendente que passa a medir não vira verde silenciosamente: ela
    reprova pedindo o piso novo.
    """
    raiz = _arvore(tmp_path)
    # piso PENDENTE com a razão do próprio censo
    _motor(raiz).aceitar(["tela-sem-endereco"], "")
    assert _estados(raiz)["tela-sem-endereco"] == catraca.ESTADO_PENDENTE

    # a I18N-DA-TELA-NOVA-01 chega e define a forma do endereço
    zonas = raiz / chk.ZONAS
    zonas.write_text(
        zonas.read_text(encoding="utf-8")
        + '\n[endereco_de_traducao]\natributo = "data-i18n"\n'
        'definido_em = "uma sprint de mentira"\n',
        encoding="utf-8",
    )
    v = _motor(raiz).comparar(["tela-sem-endereco"])[0]
    assert v.estado == catraca.VERMELHO
    assert v.numero is not None and v.numero > 0
    assert "PASSOU A MEDIR" in " ".join(v.queixas)


def test_a_medida_da_tela_conta_quem_tem_endereco_como_fora_da_conta(
    tmp_path: Path,
) -> None:
    """A régua mede o ATO, não a palavra: o nó endereçado sai da conta.

    Sem este caso, a medida poderia ignorar o atributo e continuar devolvendo o
    total todo dia — e o dia em que alguém endereçasse a primeira frase, o
    número não cairia.
    """
    raiz = _arvore(tmp_path)
    zonas = raiz / chk.ZONAS
    zonas.write_text(
        zonas.read_text(encoding="utf-8")
        + '\n[endereco_de_traducao]\natributo = "data-i18n"\n',
        encoding="utf-8",
    )
    antes = chk.censo_da_tela(raiz)
    pagina = raiz / chk.PAGINAS / "01-aba.html"
    pagina.write_text(
        pagina.read_text(encoding="utf-8").replace("<h1>", '<h1 data-i18n="titulo">'),
        encoding="utf-8",
    )
    depois = chk.censo_da_tela(raiz)
    assert antes.numero is not None and depois.numero is not None
    assert depois.numero == antes.numero - 1, (
        "endereçar uma frase tem de FAZER O NÚMERO CAIR; se não cai, a medida "
        "não está lendo o endereço"
    )


def test_aceitar_so_desce_e_subir_pede_razao(tmp_path: Path) -> None:
    """`--aceitar` que também subisse seria um botão de silenciar com nome bonito."""
    raiz = _arvore(tmp_path)
    motor = _motor(raiz)
    motor.aceitar(["prosa-publicada"], "piso")

    pagina = raiz / chk.PAGINAS / "01-aba.html"
    pagina.write_text(
        pagina.read_text(encoding="utf-8").replace("</style>", "/*maior*/</style>"),
        encoding="utf-8",
    )
    with pytest.raises(catraca.CatracaTorta):
        _motor(raiz).aceitar(["prosa-publicada"], "quero subir escondido")
    with pytest.raises(catraca.CatracaTorta):
        _motor(raiz).forcar_piso("prosa-publicada", "   ")

    _motor(raiz).forcar_piso("prosa-publicada", "a razão escrita, no diff")
    caderno = json.loads((raiz / chk.CADERNO).read_text(encoding="utf-8"))
    subidas = caderno["medidas"]["prosa-publicada"]["subidas"]
    assert subidas[-1]["razao"] == "a razão escrita, no diff"
    assert subidas[-1]["para"] > subidas[-1]["de"]


# ---------------------------------------------------------------------------
# A árvore de verdade, e o registro nos dois lugares
# ---------------------------------------------------------------------------
def test_a_arvore_de_verdade_esta_verde_e_a_tela_pendente() -> None:
    """O portão passa hoje, com a medida da tela declarada pendente."""
    vereditos = chk.montar(RAIZ).comparar()
    ruins = [v for v in vereditos if not v.passa]
    assert not ruins, [(v.medida.nome, v.queixas, v.entrou[:5]) for v in ruins]
    estados = {v.medida.nome: v.estado for v in vereditos}
    assert estados["fronteira-de-lingua"] == catraca.VERDE
    assert estados["prosa-publicada"] == catraca.VERDE
    assert estados["tela-sem-endereco"] == catraca.ESTADO_PENDENTE


def test_o_caderno_versionado_guarda_o_censo_bruto_ao_lado_do_pendente() -> None:
    """PENDENTE sem o número bruto ao lado esconderia o tamanho do problema."""
    caderno = json.loads((RAIZ / chk.CADERNO).read_text(encoding="utf-8"))
    tela = caderno["medidas"]["tela-sem-endereco"]
    assert tela["piso"] == catraca.PENDENTE
    assert tela["razao"].strip()
    assert tela["bruto"]["unidades"] > 1000, tela["bruto"]


def test_o_portao_esta_registrado_nos_dois_lugares() -> None:
    """Um comando que só mora no contrato da casa é um comando que a próxima
    pessoa não tem: o contrato é `.gitignore` e não existe em árvore de agente.
    """
    portoes = (RAIZ / "scripts" / "portoes.sh").read_text(encoding="utf-8")
    assert "scripts/check_o_projeto_e_traduzivel.py" in portoes
    assert "rapido|projeto-traduzivel|" in portoes
    pre_commit = (RAIZ / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "scripts/check_o_projeto_e_traduzivel.py" in pre_commit


def test_a_contagem_do_contribuindo_e_gerada_e_nao_digitada() -> None:
    """O número que já saiu de seis jeitos passa a sair de um só — do AST."""
    assert chk.conferir_contribuindo(RAIZ, publicar=False) == 0
    texto = (RAIZ / chk.CONTRIBUINDO).read_text(encoding="utf-8")
    assert chk.MARCA_ABRE in texto and chk.MARCA_FECHA in texto
    numeros = chk.censo_das_acoes(RAIZ)
    assert numeros["arquivos"] > 0
    assert str(numeros["arquivos"]) in texto


def test_a_contagem_do_contribuindo_reprova_quando_o_documento_envelhece(
    tmp_path: Path,
) -> None:
    """O QUE A MORDIDA ARRANCA: a conferência do bloco publicado.

    Envelhecer o número no documento — que é exatamente o que aconteceu seis
    vezes — tem de reprovar. A mordida roda numa cópia, porque mexer no
    documento de verdade deixaria o estrago no disco de quem rodou a suíte.
    """
    copia = tmp_path / "arvore"
    (copia / ".github").mkdir(parents=True)
    (copia / chk.ACOES).mkdir(parents=True)
    (copia / chk.ACOES / "um.py").write_text('X = "ação"\n', encoding="utf-8")
    original = (RAIZ / chk.CONTRIBUINDO).read_text(encoding="utf-8")
    (copia / chk.CONTRIBUINDO).write_text(original, encoding="utf-8")

    assert chk.conferir_contribuindo(copia, publicar=False) == 1
    assert chk.conferir_contribuindo(copia, publicar=True) == 0
    assert chk.conferir_contribuindo(copia, publicar=False) == 0

    sem_bloco = copia / "sem"
    (sem_bloco / ".github").mkdir(parents=True)
    (sem_bloco / chk.CONTRIBUINDO).write_text("sem bloco nenhum\n", encoding="utf-8")
    assert chk.conferir_contribuindo(sem_bloco, publicar=False) == 1
