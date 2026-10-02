"""A CATRACA DA TRADUÇÃO MORDE — as cinco mordidas da TRADUZIR-O-PROJETO-01."""

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
    (raiz / chk.PAGINAS).mkdir(parents=True)
    for n in range(1, quantas + 1):
        (raiz / chk.GERADORES / f"aba{n:02d}.py").write_text(
            "# gerador de mentira\n", encoding="utf-8"
        )
        (raiz / chk.PAGINAS / f"{n:02d}-aba.html").write_text(_PAGINA, encoding="utf-8")
    if com_zonas:
        (raiz / "docs" / "data" / "zonas-de-lingua.toml").write_text(_ZONAS, encoding="utf-8")
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


def test_mordida_1_a_catraca_compara_com_o_piso_do_disco_e_nao_consigo_mesma(
    tmp_path: Path,
) -> None:
    """O QUE A MORDIDA ARRANCA: a comparação com o piso GRAVADO."""
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
    assert any("01-aba.html" in linha for linha in v.entrou), v.entrou

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


def test_mordida_2_arquivo_que_nenhuma_regra_alcanca_reprova(tmp_path: Path) -> None:
    """O QUE A MORDIDA ARRANCA: a exigência de REGRA."""
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


def test_mordida_3_comentario_novo_na_pagina_publicada_reprova_pelo_script(
    tmp_path: Path,
) -> None:
    """O QUE A MORDIDA ARRANCA: o piso."""
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

    recusa = _rodar(raiz, "--aceitar", "prosa-publicada")
    assert recusa.returncode != 0 and "só desce" in recusa.stderr + recusa.stdout
    assert _rodar(raiz, "--forcar-piso", "prosa-publicada", "a mordida").returncode == 0
    assert _rodar(raiz).returncode == 0


def test_o_comentario_de_css_nao_conta_o_que_mora_dentro_de_uma_string() -> None:
    """PERGUNTE AO PARSER, não ao regex."""
    css = 'a { content: "/* não sou comentário */"; } /* eu sou */'
    achados = chk.comentarios_css(css)
    assert achados == ["/* eu sou */"], achados


def test_mordida_4_universo_vazio_reprova_em_vez_de_dar_verde(tmp_path: Path) -> None:
    """O QUE A MORDIDA ARRANCA: a peneira do universo."""
    vazia = tmp_path / "vazia"
    vazia.mkdir()

    resultado = _rodar(vazia)
    assert resultado.returncode == 1, resultado.stdout + resultado.stderr
    assert catraca.IMPOSSIVEL in resultado.stdout, resultado.stdout

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
    """O QUE A MORDIDA ARRANCA: a pergunta ao DONO de quantas abas existem."""
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


def test_mordida_5_pendente_nunca_e_verde_na_arvore_de_verdade() -> None:
    """O QUE A MORDIDA ARRANCA: a recusa de comparar o que não se mede."""
    vereditos = {v.medida.nome: v for v in chk.montar(RAIZ).comparar()}
    v = vereditos["tela-sem-endereco"]
    assert v.estado == catraca.ESTADO_PENDENTE
    assert v.estado != catraca.VERDE
    assert v.numero is None, "medida pendente não devolve número"
    assert "endereco_de_traducao" in " ".join(v.queixas)


def test_mordida_5_tratar_pendente_como_zero_daria_verde_sobre_nada(
    tmp_path: Path,
) -> None:
    """O QUE A MORDIDA ARRANCA: o `None` de quem não pode medir, virando `0`."""
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
    """Instrumento que sabe do próprio risco RESOLVE, não avisa."""
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


def test_a_medida_que_acorda_reprova_sozinha(tmp_path: Path) -> None:
    """O dia em que o encanamento existir, o portão AVISA — e não fica calado."""
    raiz = _arvore(tmp_path)
    _motor(raiz).aceitar(["tela-sem-endereco"], "")
    assert _estados(raiz)["tela-sem-endereco"] == catraca.ESTADO_PENDENTE

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
    """A régua mede o ATO, não a palavra: o nó endereçado sai da conta."""
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
    """Um comando que só mora no contrato da casa é um comando que a próxima"""
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
    """O QUE A MORDIDA ARRANCA: a conferência do bloco publicado."""
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


def _repo_de_git(raiz: Path) -> None:
    """Faz da miniatura uma árvore de git com tudo no índice, menos o que vier."""
    subprocess.run(["git", "init"], cwd=raiz, check=True, capture_output=True)
    for arquivo in sorted(raiz.rglob("*")):
        if arquivo.is_file() and ".git" not in arquivo.parts:
            subprocess.run(
                ["git", "add", "--", arquivo.relative_to(raiz).as_posix()],
                cwd=raiz,
                check=True,
                capture_output=True,
            )


def test_mordida_4_a_peneira_do_vazio_vale_medida_a_medida(tmp_path: Path) -> None:
    """O QUE A MORDIDA ARRANCA: o `universo <= 0` do motor, e por medida."""
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    estados = {v.medida.nome: v.estado for v in chk.montar(vazia).comparar()}
    assert set(estados) == {m.nome for m in chk.MEDIDAS}, estados
    assert estados == {nome: catraca.IMPOSSIVEL for nome in estados}, (
        "numa pasta vazia, medida que diz qualquer coisa que não IMPOSSIVEL "
        f"está passando sobre o vazio: {estados}"
    )


def test_mordida_4_pagina_sem_gerador_nenhum_e_impossivel(tmp_path: Path) -> None:
    """O QUE A MORDIDA ARRANCA: a queixa de «nenhum gerador de aba»."""
    raiz = _arvore(tmp_path)
    _motor(raiz).aceitar(None, "piso da mordida")
    for gerador in (raiz / chk.GERADORES).glob("aba[0-9][0-9].py"):
        gerador.unlink()

    v = {x.medida.nome: x for x in _motor(raiz).comparar()}["prosa-publicada"]
    assert v.estado == catraca.IMPOSSIVEL, v.estado
    assert "gerador" in " ".join(v.queixas), v.queixas


def test_mordida_2_o_arquivo_novo_reprova_antes_do_git_add(tmp_path: Path) -> None:
    """O QUE A MORDIDA ARRANCA: o `--others` do `git ls-files`."""
    raiz = _arvore(tmp_path)
    _repo_de_git(raiz)
    _motor(raiz).aceitar(["fronteira-de-lingua"], "piso da mordida")
    assert _estados(raiz)["fronteira-de-lingua"] == catraca.VERDE

    (raiz / "traducoes").mkdir()
    (raiz / "traducoes" / "uma-pagina-nova.md").write_text("prosa\n", encoding="utf-8")
    indice = subprocess.run(
        ["git", "ls-files", "--cached"], cwd=raiz, capture_output=True, text=True
    ).stdout
    assert "traducoes/uma-pagina-nova.md" not in indice, (
        "a mordida perdeu o sentido: o arquivo entrou no índice e deixou de "
        "ser o caso difícil"
    )

    v = _motor(raiz).comparar(["fronteira-de-lingua"])[0]
    assert v.estado == catraca.VERMELHO, v.estado
    assert any("traducoes/uma-pagina-nova.md" in linha for linha in v.entrou), v.entrou


def test_a_tabela_de_zonas_recusa_regra_sem_razao_e_zona_desconhecida(
    tmp_path: Path,
) -> None:
    """O QUE A MORDIDA ARRANCA: as duas guardas de `carregar_zonas`."""
    raiz = tmp_path / "t"
    (raiz / "docs" / "data").mkdir(parents=True)
    alvo = raiz / chk.ZONAS

    alvo.write_text(
        '[[regra]]\ncaminho = "src/**"\nzona = "CODIGO"\nrazao = "   "\n',
        encoding="utf-8",
    )
    with pytest.raises(SystemExit):
        chk.carregar_zonas(raiz)

    alvo.write_text(
        '[[regra]]\ncaminho = "src/**"\nzona = "TALVEZ"\nrazao = "uma razão"\n',
        encoding="utf-8",
    )
    with pytest.raises(SystemExit):
        chk.carregar_zonas(raiz)


def test_a_prosa_publicada_conta_o_comentario_de_html_tambem(tmp_path: Path) -> None:
    """O QUE A MORDIDA ARRANCA: a contagem do comentário de HTML."""
    raiz = _arvore(tmp_path)
    antes = chk.censo_da_prosa(raiz).numero
    recheio = "<!--" + "r" * 512 + "-->"
    pagina = raiz / chk.PAGINAS / "01-aba.html"
    pagina.write_text(
        pagina.read_text(encoding="utf-8").replace("</body>", recheio + "\n</body>"),
        encoding="utf-8",
    )
    depois = chk.censo_da_prosa(raiz).numero
    assert antes is not None and depois is not None
    assert depois == antes + len(recheio.encode("utf-8")), (antes, depois)


def test_a_medida_da_tela_conta_o_atributo_e_nao_so_a_frase(tmp_path: Path) -> None:
    """O QUE A MORDIDA ARRANCA: a lista de atributos de tela."""
    raiz = _arvore(tmp_path)
    zonas = raiz / chk.ZONAS
    zonas.write_text(
        zonas.read_text(encoding="utf-8")
        + '\n[endereco_de_traducao]\natributo = "data-i18n"\n',
        encoding="utf-8",
    )
    antes = chk.censo_da_tela(raiz).numero
    pagina = raiz / chk.PAGINAS / "01-aba.html"
    pagina.write_text(
        pagina.read_text(encoding="utf-8").replace(
            "<h1>", '<h1 title="uma dica que o leitor de tela pronuncia">'
        ),
        encoding="utf-8",
    )
    depois = chk.censo_da_tela(raiz).numero
    assert antes is not None and depois is not None
    assert depois == antes + 1, (antes, depois)


def test_a_medida_da_tela_nao_conta_o_que_mora_em_script_ou_style(
    tmp_path: Path,
) -> None:
    """O QUE A MORDIDA ARRANCA: a lista de nós mudos."""
    raiz = _arvore(tmp_path)
    leitor = chk._LeitorDeTela(None)
    leitor.feed((raiz / chk.PAGINAS / "01-aba.html").read_text(encoding="utf-8"))
    juntas = " | ".join(sorted(leitor.frases_sem))
    assert "A aba de mentira" in juntas, juntas
    assert "comentário de JS" not in juntas, juntas
    assert "body {" not in juntas, juntas


def test_a_medida_que_para_de_medir_com_piso_numerico_reprova(tmp_path: Path) -> None:
    """O QUE A MORDIDA ARRANCA: o vermelho de «piso sobre o que não se mede»."""
    raiz = _arvore(tmp_path)
    _motor(raiz).aceitar(["fronteira-de-lingua"], "piso numérico de partida")
    assert _estados(raiz)["fronteira-de-lingua"] == catraca.VERDE

    (raiz / chk.ZONAS).unlink()
    v = _motor(raiz).comparar(["fronteira-de-lingua"])[0]
    assert v.estado == catraca.VERMELHO, v.estado
    assert "piso falso" in " ".join(v.queixas), v.queixas


def test_catraca_sem_piso_reprova_em_vez_de_passar(tmp_path: Path) -> None:
    """O QUE A MORDIDA ARRANCA: o estado SEM-PISO."""
    raiz = _arvore(tmp_path)
    vereditos = {v.medida.nome: v for v in _motor(raiz).comparar()}
    v = vereditos["prosa-publicada"]
    assert v.estado == catraca.SEM_PISO, v.estado
    assert not v.passa


def test_o_portao_soma_a_conferencia_do_contribuindo_no_proprio_rc(
    tmp_path: Path,
) -> None:
    """O QUE A MORDIDA ARRANCA: a costura da conferência ao rc do portão."""
    raiz = _arvore(tmp_path)
    (raiz / chk.ACOES / "dois.py").write_text('Y = "outra ação"\n', encoding="utf-8")
    assert _rodar(raiz, "--aceitar").returncode == 0

    resultado = _rodar(raiz)
    assert resultado.returncode == 1, resultado.stdout + resultado.stderr
    assert "não é a de hoje" in resultado.stdout + resultado.stderr


def test_forcar_piso_recusa_universo_vazio(tmp_path: Path) -> None:
    """O QUE A MORDIDA ARRANCA: a recusa de SUBIR piso sobre o vazio."""
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    with pytest.raises(catraca.CatracaTorta):
        _motor(vazia).forcar_piso("prosa-publicada", "uma razão qualquer")


def test_o_portao_ainda_sobe_num_python_sem_tomllib(tmp_path: Path) -> None:
    """O QUE A MORDIDA ARRANCA: o `try/except` em volta do `import tomllib`."""
    receita = (
        "import sys\n"
        "class _SemTomllib:\n"
        "    def find_spec(self, nome, caminho=None, alvo=None):\n"
        "        if nome == 'tomllib':\n"
        "            raise ModuleNotFoundError(\"No module named 'tomllib'\")\n"
        "        return None\n"
        "sys.modules.pop('tomllib', None)\n"
        "sys.meta_path.insert(0, _SemTomllib())\n"
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('alvo', {str(SCRIPT)!r})\n"
        "spec.loader.exec_module(importlib.util.module_from_spec(spec))\n"
    )
    prova = subprocess.run(
        [sys.executable, "-c", receita], capture_output=True, text=True
    )
    ultima = [linha for linha in prova.stderr.splitlines() if linha.strip()]
    ultima_queixa = ultima[-1] if ultima else ""
    assert "tomllib" not in ultima_queixa, (
        "o `import tomllib` está pelado: num Python 3.10 este arquivo nem "
        f"chega a ser coletado.\n{prova.stderr[-600:]}"
    )
