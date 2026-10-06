#!/usr/bin/env python3
"""A RÉGUA DO PORTÃO NOVO: nenhum texto de tela confessa dívida NOSSA."""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PORTAO = RAIZ / "scripts" / "check_a_tela_nao_confessa.py"


@pytest.fixture(scope="module")
def portao():
    """O script importado como módulo — sem `sys.path` global e sem subprocesso."""
    spec = importlib.util.spec_from_file_location("_portao_confissao", PORTAO)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_o_portao_passa_na_arvore_de_hoje() -> None:
    """Ele roda no `portoes.sh` e no CI; aqui ele roda também, e no pytest."""
    r = subprocess.run([sys.executable, str(PORTAO)], capture_output=True,
                       text=True, cwd=RAIZ)
    assert r.returncode == 0, (
        f"o portão da confissão reprovou:\n{r.stdout}\n{r.stderr}")


AS_QUE_SAIRAM = (
    ("06-navegacao.html", "o Hefesto ainda não faz"),
    ("02-controles.html", "não faz o som sair neste alto-falante"),
    ("01-jogar.html", "não sabe montar esta máscara"),
)


@pytest.mark.parametrize(("pagina", "frase"), AS_QUE_SAIRAM)  # noqa-acento: nome de parametro
def test_a_frase_que_ela_marcou_saiu_dos_dois_lados(pagina: str, frase: str) -> None:
    from hefesto_dualsense4unix.interface import onde

    for caminho in (onde.pagina(pagina), onde.PUBLICADO / pagina):
        texto = caminho.read_text(encoding="utf-8")
        assert frase not in texto, (
            f"{caminho.name} ainda diz {frase!r} — ela marcou esta frase em "
            f"07/09/2026, e a ordem é que o layout não informe os nossos "
            f"defeitos")


def test_a_celula_do_alto_falante_so_diz_sim_com_prova() -> None:
    """A tela calou; a célula só VIRA com a prova escrita ao lado."""
    import csv
    import pathlib

    from hefesto_dualsense4unix.app.fatos_do_mapa import FATOS

    celula = FATOS["audio.alto_falante@dualsense"]["radio"]
    assert isinstance(celula, dict)
    if celula["aciona"] != "sim":
        return
    mapa = pathlib.Path(__file__).resolve().parents[2] / "docs/data/mapa-controles.csv"
    with mapa.open(newline="", encoding="utf-8") as f:
        linha = next(
            ln for ln in csv.DictReader(f)
            if ln["chave"] == "audio.alto_falante" and ln["controle"] == "dualsense"
        )
    assert linha["radio_de_onde_sei"] == "medido", (
        "a célula do alto-falante no rádio diz `sim` sem procedência `medido`")
    assert linha["radio_evidencia"].strip(), (
        "a célula do alto-falante no rádio diz `sim` sem a evidência escrita")
    assert linha["teste_que_morde"].strip(), (
        "a célula do alto-falante no rádio diz `sim` sem a régua que morde")


CONFISSOES = (
    "Rolar com dois dedos no touchpad é outra coisa, e o Hefesto ainda não faz.",
    "Pelo rádio o Hefesto ainda não faz o som sair neste alto-falante.",
    "O Hefesto não sabe montar esta máscara.",
    "Ainda não sei olhar este lançador.",
    "O perfil ainda não tem por onde limitar estes.",
    "Não conseguimos ler isto por aqui.",
)

LEGITIMAS = (
    "Não sei onde fica",
    "Sem resposta não é o mesmo que “Não sei”.",
    "O perfil não guarda uma configuração: guarda uma por controle.",
)


@pytest.mark.parametrize("frase", CONFISSOES)
def test_morde_a_peneira_acusa_a_confissao(portao, frase: str) -> None:
    """MORDE: tire a alternativa do `ainda` da FORMA e estas seis passam calado."""
    assert portao._forma(frase), (
        f"a peneira deixou passar {frase!r} — é a família que a ordem dela de "
        f"07/09/2026 manda tirar da tela")


@pytest.mark.parametrize("frase", LEGITIMAS)
def test_a_peneira_nao_acusa_a_voz_da_pessoa_nem_a_afirmacao_positiva(
        portao, frase: str) -> None:
    """A voz do usuário respondendo *"não sei"* não é o produto confessando."""
    assert not portao._forma(frase), (
        f"a peneira acusou {frase!r}, que é a voz da pessoa ou uma afirmação "
        f"positiva — obrigar a declarar isto esvazia a tabela de sentido")


def test_a_afirmacao_positiva_e_pega_pela_forma_e_so_a_tabela_a_absolve(portao) -> None:
    """*"O Hefesto não é só para a Steam"* é o oposto de uma confissão — e a"""
    frase = "O Hefesto não é só para a Steam."
    assert portao._forma(frase), "a peneira deixou de casar por forma"
    assert not any(k.lower() in frase.lower() for k in portao.FATOS), (
        "a frase saiu da tela em 11/09/2026 e a declaração dela tinha de sair "
        "junto — uma linha em FATOS sobre uma frase que a tela não tem mais é "
        "a declaração que envelhece calada, e o portão reprova por isso")


def test_morde_a_limpeza_vem_antes_do_casamento(portao) -> None:
    """**A ARMADILHA QUE ESTA CASA PAGOU QUATRO VEZES EM QUATRO DIAS.**"""
    pagina = (
        '<!-- este comentário explica que a frase "o Hefesto ainda não faz" '
        'saiu daqui -->\n'
        '<style>/* e o CSS também fala: o Hefesto ainda não faz */</style>\n'
        '<script>// o Hefesto ainda não faz</script>\n'
        '<p>Rola com o analógico direito.</p>'
    )
    assert not portao._forma(portao._limpo(pagina)), (
        "a régua contou a EXPLICAÇÃO como se fosse o defeito — é a armadilha "
        "de prosa que esta casa pagou quatro vezes em quatro dias")
    assert portao._forma(pagina), (
        "o dublê não tem a frase que a régua deveria achar sem a limpeza — a "
        "mordida não estaria medindo nada")


def test_morde_a_legenda_do_mockup_fica_de_fora_e_a_janela_nao(portao) -> None:
    """O recorte é a JANELA, e a `.nota` é a legenda — *"fora da janela"*."""
    pagina = ('<p title="o Hefesto ainda não faz isto">um</p>'
              '<div class="nota">e aqui o Hefesto ainda não faz aquilo</div>')
    dentro = portao._dentro_da_janela(pagina)
    assert portao._forma(dentro), "a régua deixou de olhar dentro da janela"
    assert len(portao._forma(dentro)) == 1, (
        "a régua entrou na legenda do mockup — ali a dívida é para ser "
        "nomeada, e é o que ela lê para aprovar o desenho")


def test_morde_a_tabela_nao_pode_ficar_orfa(portao) -> None:
    """Declaração que sobrevive à frase envelhece calada — e mente ao contrário."""
    assert "orfas" in PORTAO.read_text(encoding="utf-8"), (
        "o portão perdeu a checagem do sentido inverso")


def test_toda_divida_declarada_diz_o_endereco_e_a_data(portao) -> None:
    """A tabela da dívida só encolhe, e cada linha tem de dizer ONDE e QUANDO."""
    for frase, razao in portao.A_DIVIDA.items():
        assert "/" in razao or "aba" in razao, (
            f"a dívida {frase!r} não diz o endereço de quem a tira")
        assert "/2026" in razao, (
            f"a dívida {frase!r} não diz a data em que foi medida")


def test_o_canal_do_recado_continua_sendo_o_raise(portao) -> None:
    """A PREMISSA DA LEITURA, medida e não afirmada."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
             ).read_text(encoding="utf-8")
    assert 'print(f"[gesto falhou] {pagina} · {nome}: {erro}"' in fonte, (
        "o piloto deixou de mandar `str(erro)` ao diário — o canal que este "
        "portão lê mudou de forma de novo, e a leitura tem de mudar junto")
    assert "self._depositar(" not in fonte, (
        "o piloto voltou a depositar a frase da recusa — ela voltaria à tela")


def test_a_regua_le_os_recados_da_arvore_de_hoje(portao) -> None:
    """Ela lê o canal inteiro, e RECUSA achar pouco."""
    lidos, mudos = portao._recados()
    assert len(lidos) > 150, (
        f"li {len(lidos)} recados de gesto nos pacotes e eles são quase "
        f"duzentos — o caminho mudou, e uma régua que não acha o canal não o "
        f"mede")
    inteiros = [t for _o, t in lidos if portao.VALOR_DE_EXECUCAO not in t]
    assert len(inteiros) > 50, (
        f"só {len(inteiros)} recados foram montados sem buraco — a "
        f"reconstrução parou de resolver constante e f-string, e o portão "
        f"passou a ler menos do que lia")
    assert len(mudos) < len(lidos) // 4, (
        f"{len(mudos)} de {len(lidos)} recados ficaram sem uma letra — a "
        f"reconstrução regrediu")


def test_morde_a_frase_do_raise_e_montada_do_fonte(portao, tmp_path) -> None:
    """MORDE: a régua monta a frase como o fonte a escreve."""
    import ast

    alvo = tmp_path / "a99_dublê.py"
    alvo.write_text(
        'RAZAO = "o Hefesto ainda não sabe abrir este lançador"\n'
        'def gesto(x):\n'
        '    raise RuntimeError(f"{x}: {RAZAO}")\n'
        'def outro():\n'
        '    raise RuntimeError("começo " + RAZAO)\n',
        encoding="utf-8")
    arvore = ast.parse(alvo.read_text(encoding="utf-8"))
    montadas = []
    for fn in ast.walk(arvore):
        if not isinstance(fn, ast.FunctionDef):
            continue
        local = portao._dentro(fn, alvo)
        for no in ast.walk(fn):
            if isinstance(no, ast.Raise) and isinstance(no.exc, ast.Call):
                montadas.append(portao._montar(no.exc.args[0], alvo, local))
    assert len(montadas) == 2
    for texto, _inteiro in montadas:
        assert "o Hefesto ainda não sabe abrir este lançador" in texto, (
            f"a régua não montou a frase do fonte: {texto!r}")
        assert portao._forma(texto), (
            "a peneira não acusou a frase montada — o canal seria lido e "
            "ninguém saberia")
    assert montadas[0][1] is False, (
        "a régua disse que montou a frase INTEIRA, e o `{x}` só existe "
        "rodando — quem lê o verde acharia que a frase toda passou por peneira")
    assert montadas[1][1] is True, (
        "a soma de dois literais é reconstruível por inteiro, e a régua "
        "declarou o contrário")


def test_morde_o_buraco_nao_deixa_a_peneira_atravessar(portao, tmp_path) -> None:
    """**A ARMADILHA QUE O BURACO EVITA, e ela é sutil.**"""
    import ast

    alvo = tmp_path / "a98_dublê.py"
    alvo.write_text(
        'def gesto(quantos):\n'
        '    raise RuntimeError(f"ainda {quantos} não chegaram")\n',
        encoding="utf-8")
    arvore = ast.parse(alvo.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef))
    no = next(n for n in ast.walk(fn) if isinstance(n, ast.Raise))
    texto, _inteiro = portao._montar(no.exc.args[0], alvo, portao._dentro(fn, alvo))
    assert not portao._forma(texto), (
        f"a peneira atravessou o buraco e inventou uma confissão: {texto!r}")


@pytest.fixture
def so_o_terceiro_canal(portao, monkeypatch):
    """O `main` medindo SÓ o canal do recado — as outras duas fontes caladas."""
    monkeypatch.setattr(portao, "_paginas", lambda: [])
    monkeypatch.setattr(portao, "_falas", lambda: [])
    monkeypatch.setattr(portao, "FATOS", {})
    monkeypatch.setattr(portao, "A_DIVIDA", {})
    monkeypatch.setattr(portao, "SEM_LETRA", {})
    monkeypatch.setattr(portao, "_recados", lambda: ([], []))
    return monkeypatch


def test_morde_main_reprova_o_recado_que_confessa(portao, so_o_terceiro_canal) -> None:
    """MORDE: tire `lidos` do `main` e o canal volta a ser cego."""
    assert portao.main() == 0, (
        "o `main` reprovou com as três fontes caladas — a mordida abaixo "
        "mediria outra peneira")
    so_o_terceiro_canal.setattr(
        portao, "_recados",
        lambda: ([("dublê/a99.py:7", "Ainda não sei fazer isto por aqui")], []))
    assert portao.main() == 1, (
        "o `main` não leu o recado do gesto — o canal que pousa no cartão dela "
        "continua fora da peneira")


def test_morde_main_cobra_o_recado_que_nao_conseguiu_ler(
        portao, so_o_terceiro_canal) -> None:
    """O que a régua não alcança NÃO passa calado — ela diz que não conseguiu."""
    muda = ("a99_dublê.py:gesto ← motivo", "dublê/a99.py:9")
    so_o_terceiro_canal.setattr(portao, "_recados", lambda: ([], [muda]))
    assert portao.main() == 1, (
        "o `main` passou sobre um recado que a régua não conseguiu ler — o "
        "ponto cego voltou a ser silencioso")
    so_o_terceiro_canal.setattr(
        portao, "SEM_LETRA", {muda[0]: "a recusa do daemon, palavra por palavra"})
    assert portao.main() == 0, (
        "declarar o dono não bastou — a tabela não está sendo consultada, e "
        "então ela é enfeite")


def test_morde_a_tabela_sem_letra_nao_pode_ficar_orfa(
        portao, so_o_terceiro_canal) -> None:
    """A terceira tabela também vale nos DOIS sentidos."""
    so_o_terceiro_canal.setattr(
        portao, "SEM_LETRA",
        {"a99_dublê.py:gesto ← motivo": "um dono que o fonte não tem mais"})
    assert portao.main() == 1, (
        "o `main` passou com `SEM_LETRA` declarando um recado que o fonte não "
        "tem — a declaração envelhece calada")


def test_todo_recado_sem_letra_diz_de_quem_e_a_frase(portao) -> None:
    """Cada linha da terceira tabela tem de nomear o DONO, não pedir desculpa."""
    for chave, razao in portao.SEM_LETRA.items():
        assert " ← " in chave, (
            f"a chave {chave!r} não diz `arquivo:gesto ← expressão`")
        assert len(razao) > 20, (
            f"o recado {chave!r} não diz de quem é a frase")


def test_a_chave_sem_letra_e_o_trecho_do_fonte_em_qualquer_python(portao) -> None:
    """A chave de `SEM_LETRA` é o que está ESCRITO no arquivo — igual em todo Python."""
    _lidos, mudos = portao._recados()
    assert mudos, "a régua não achou nenhum recado sem letra — o caminho mudou"
    for chave, onde in mudos:
        expressao = chave.split(" ← ", 1)[1]
        arquivo = RAIZ / onde.rsplit(":", 1)[0]
        fonte = " ".join(arquivo.read_text(encoding="utf-8").split())
        assert expressao and expressao in fonte, (
            f"a chave {chave!r} não é o que o fonte escreve em {onde} — ela "
            "depende do interpretador que a montou, e a mesma declaração "
            "passaria num job do CI e reprovaria no outro")
