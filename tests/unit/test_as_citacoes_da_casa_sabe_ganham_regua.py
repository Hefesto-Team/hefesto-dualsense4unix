"""As citações da casa-sabe passam pela régua, e a de linha única promete o nome que só a linha tem.

Sprint AS-CITACOES-DA-CASA-SABE-E-AS-DE-LINHA-UNICA-GANHAM-REGUA-01 (25/10/2026). Duas provas:

- a citação escrita numa cadeia de `tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py` reprova
  o `validar-citacoes-de-linha.py` quando o código anda, e o `reapontar-citacoes.py` a leva;
- cada uma das oito citações de linha única da `docs/data/paridade-gtk-html.csv` cujo nome casava
  também na linha vizinha reprova com uma linha inserida acima do alvo, e a promessa velha delas
  reprova pela regra do vizinho;
- a citação crua NOVA numa cadeia da casa-sabe reprova o `--novas`, como a das planilhas, e a crua
  antiga que só mudou de número não.
"""

from __future__ import annotations

import csv
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]
VALIDADOR = RAIZ / "scripts" / "validar-citacoes-de-linha.py"
REAPONTAR = RAIZ / "scripts" / "reapontar-citacoes.py"
PARIDADE = RAIZ / "docs" / "data" / "paridade-gtk-html.csv"
CASA_SABE = "tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py"


def _carregar(caminho: Path, nome: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nome, caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def val() -> ModuleType:
    return _carregar(VALIDADOR, "validar_citacoes_de_linha")


def _git(raiz: Path, *args: str) -> str:
    feito = subprocess.run(
        [
            "git",
            "-C",
            str(raiz),
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "user.name=régua",
            "-c",
            "user.email=regua@exemplo.invalid",
            *args,
        ],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"},
    )
    return feito.stdout


def _validar(raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDADOR), "--all", "--root", str(raiz)],
        capture_output=True,
        text=True,
        check=False,
    )


# --- 1. a casa-sabe: o validador a lê, e o reapontar a leva -------------------------------------

ALVO = '''"""O alvo de mentira."""

VALOR = 1


def primeira():
    return 1


def segunda():
    x = 2
    return x
'''

# A promessa fica no pedaço de BAIXO da cadeia emendada, como o arquivo da casa-sabe escreve.
CASA = (
    '"""A casa-sabe de mentira."""\n'
    "\n"
    "RAZOES = {\n"
    '    "alvo.py::segunda": (\n'
    '        "25/10/2026 — quem soma é src/hefesto_dualsense4unix/alvo.py:10 "\n'
    '        "(`segunda`), e a régua o confere."\n'
    "    ),\n"
    "}\n"
)


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    raiz = tmp_path / "repo"
    pacote = raiz / "src" / "hefesto_dualsense4unix"
    pacote.mkdir(parents=True)
    (pacote / "alvo.py").write_text(ALVO, encoding="utf-8")
    (raiz / "tests" / "unit").mkdir(parents=True)
    (raiz / CASA_SABE).write_text(CASA, encoding="utf-8")
    (raiz / "docs" / "data").mkdir(parents=True)
    (raiz / "docs" / "protocol").mkdir(parents=True)
    _git(raiz, "init", "-q")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "a casa-sabe nasce")
    return raiz


def _o_codigo_anda(raiz: Path, linhas: int) -> None:
    alvo = raiz / "src" / "hefesto_dualsense4unix" / "alvo.py"
    texto = alvo.read_text(encoding="utf-8").split("\n")
    alvo.write_text("\n".join(texto[:2] + [f"EXTRA_{n} = {n}" for n in range(linhas)] + texto[2:]),
                    encoding="utf-8")
    _git(raiz, "commit", "-q", "-am", "o código anda")


def test_a_citacao_da_casa_sabe_com_a_linha_errada_reprova_e_o_reapontar_a_leva(repo: Path) -> None:
    assert _validar(repo).returncode == 0, _validar(repo).stdout
    _o_codigo_anda(repo, 3)

    reprovada = _validar(repo)
    assert reprovada.returncode == 1, reprovada.stdout
    assert f"{CASA_SABE}:5" in reprovada.stdout, reprovada.stdout
    assert "a faixa não contém `segunda`" in reprovada.stdout, reprovada.stdout

    feitos, a_mao = _carregar(REAPONTAR, "reapontar_citacoes").reapontar(repo, escrever=True)

    assert a_mao == [], a_mao
    assert feitos, feitos
    assert _validar(repo).returncode == 0, _validar(repo).stdout
    escrito = (repo / CASA_SABE).read_text(encoding="utf-8")
    assert escrito == CASA.replace("alvo.py:10 ", "alvo.py:13 "), escrito


@pytest.mark.parametrize(
    ("cadeia", "queixa"),
    [
        pytest.param('"o alvo.py:10 soma"', "escreva `src/hefesto_dualsense4unix/alvo.py`",
                     id="caminho-que-so-abre-pelo-fim"),
        pytest.param('"o hefesto_dualsense4unix/alvo.py:10 soma"',
                     "escreva `src/hefesto_dualsense4unix/alvo.py`", id="caminho-sem-o-src"),
        pytest.param('"o `src/hefesto_dualsense4unix/alvo.py`:10 soma"', "forma curta no código",
                     id="arquivo-entre-crases"),
        pytest.param('"src/hefesto_dualsense4unix/alvo.py:10 e (:12)"', "forma curta no código",
                     id="curta"),
        pytest.param('"src/hefesto_dualsense4unix/alvo.py:10+12"', "forma curta no código",
                     id="mais"),
    ],
)
def test_no_codigo_a_citacao_se_escreve_inteira_a_partir_da_raiz(
    repo: Path, cadeia: str, queixa: str
) -> None:
    (repo / CASA_SABE).write_text(f"RAZAO = (\n    {cadeia}\n)\n", encoding="utf-8")
    _git(repo, "add", ".")

    saida = _validar(repo)

    assert saida.returncode == 1, saida.stdout
    assert f"{CASA_SABE}:2" in saida.stdout and queixa in saida.stdout, saida.stdout


def test_o_exemplo_fabricado_que_nao_abre_em_lugar_nenhum_fica_de_fora(repo: Path) -> None:
    (repo / CASA_SABE).write_text('RAZAO = "o fabricado/x.py:1 de um teste"\n', encoding="utf-8")

    assert _validar(repo).returncode == 0, _validar(repo).stdout


def test_a_cadeia_emendada_e_uma_so_e_cada_pedaco_guarda_a_sua_linha(val: ModuleType) -> None:
    texto = (
        'X = (\n    "um src/a.py:3 "\n    # fala\n    "(`nome`) dois"\n)\n'
        'Y = """a\nb src/c.py:9"""\n'
    )

    trechos = val.trechos_do_codigo(texto)
    cadeias = {t.texto: t for t in trechos}

    emendada = cadeias["um src/a.py:3 (`nome`) dois"]
    assert emendada.linha_de(0) == 2 and emendada.linha_de(len("um src/a.py:3 ")) == 4
    longa = cadeias["a\nb src/c.py:9"]
    assert longa.linha_de(longa.texto.index("src/c.py")) == 7
    assert "# fala" in cadeias, cadeias


# --- 2. a de linha única promete o nome que só a linha tem -------------------------------------

OITO = [
    # (aba, começo da feature, arquivo citado, nome de hoje, nome velho)
    ("02-controles", "Clique dos analógicos",
     "src/hefesto_dualsense4unix/interface/pacotes/a02_controles.py", "ROTULO_DO_CLIQUE", None),
    ("02-controles", "Microfone — o controle deslizante de volume",
     "src/hefesto_dualsense4unix/interface/aba02.py", "ROTULO_VOL_MIC", "mic_vol"),
    ("02-controles", "Alto-falante — o controle deslizante de volume",
     "src/hefesto_dualsense4unix/interface/aba02.py", "ROTULO_VOL_ALTO", "alto_v"),
    ("02-controles", "Alto-falante — qual botão de rota está aceso",
     "src/hefesto_dualsense4unix/interface/aba02.py", "ROTULO_SO_OS_EFEITOS", "alto-rota"),
    ("02-controles", "Alto-falante — qual botão de rota está aceso",
     "src/hefesto_dualsense4unix/interface/paginas/02-controles.html", "DualSense", "rota"),
    ("05-vibracao", "Os oito interruptores de lado",
     "src/hefesto_dualsense4unix/interface/hefesto_vivo.py", "gesto", "dono"),
    ("06-navegacao", 'A tela "Estilo Point-and-click"',
     "src/hefesto_dualsense4unix/interface/aba06.py", "select", "point"),
    ("08-conexoes", "Transporte (cabo/rádio) de cada controle",
     "mockup/08-conexoes.html", "gc-nome", "nome"),
]
"""A oitava é a mesma feature da quarta, no publicado. O `ROTULO_DO_CLIQUE` mudou de LINHA (da
`:1392`, que o repetia na de baixo, para a `:477`, a que o define); o nome velho dela é o mesmo."""


def _linha_da_celula(aba: str, feature: str, arquivo: str, nome: str) -> int:
    with PARIDADE.open(encoding="utf-8", newline="") as fluxo:
        for registro in csv.DictReader(fluxo):
            if registro["aba"] == aba and registro["feature"].startswith(feature):
                achado = re.search(rf"{re.escape(arquivo)}:(\d+) \(`{re.escape(nome)}`\)",
                                   registro["html_onde"])
                if achado:
                    return int(achado.group(1))
    raise AssertionError(f"a planilha não cita mais `{arquivo}` com `{nome}` em {aba} · {feature}")


def _montar(tmp_path: Path, arquivo: str, linha: int, nome: str, inserir: int | None) -> Path:
    """Uma raiz com a cópia do alvo (com uma linha em branco nova antes de ``inserir``) e uma
    planilha de uma célula que cita ``arquivo:linha (`nome`)``."""
    raiz = tmp_path / "raiz"
    corpo = (RAIZ / arquivo).read_text(encoding="utf-8").split("\n")
    if inserir is not None:
        corpo.insert(inserir - 1, "")
    (raiz / arquivo).parent.mkdir(parents=True, exist_ok=True)
    (raiz / arquivo).write_text("\n".join(corpo), encoding="utf-8")
    planilha = raiz / "docs" / "data" / "x.csv"
    planilha.parent.mkdir(parents=True, exist_ok=True)
    with planilha.open("w", encoding="utf-8", newline="") as fluxo:
        csv.writer(fluxo).writerows([["id", "html_onde"], ["a", f"{arquivo}:{linha} (`{nome}`)"]])
    return planilha


def _queixas(val: ModuleType, planilha: Path) -> list[str]:
    raiz = planilha.parents[2]
    return [str(a) for a in val.varrer_planilha(planilha, raiz, {})[0]]


@pytest.mark.parametrize(
    ("aba", "feature", "arquivo", "nome", "velho"), OITO, ids=[f"{o[0]}-{o[3]}" for o in OITO]
)
def test_uma_linha_inserida_acima_do_alvo_de_cada_uma_das_oito_reprova(
    val: ModuleType, tmp_path: Path, aba: str, feature: str, arquivo: str, nome: str,
    velho: str | None,
) -> None:
    linha = _linha_da_celula(aba, feature, arquivo, nome)

    assert _queixas(val, _montar(tmp_path / "hoje", arquivo, linha, nome, None)) == []
    for onde in (1, linha):
        queixas = _queixas(val, _montar(tmp_path / f"acima-{onde}", arquivo, linha, nome, onde))
        assert queixas, f"uma linha inserida em {onde} deixou `{nome}` verde na {linha}"


@pytest.mark.parametrize(
    ("aba", "feature", "arquivo", "nome", "velho"), OITO, ids=[f"{o[0]}-{o[3]}" for o in OITO]
)
def test_a_promessa_velha_das_oito_reprova_pelo_vizinho(
    val: ModuleType, tmp_path: Path, aba: str, feature: str, arquivo: str, nome: str,
    velho: str | None,
) -> None:
    """O nome velho casava na citada E na vizinha: a costura de uma linha o deixaria verde."""
    linha = _linha_da_celula(aba, feature, arquivo, nome)
    if velho is None:
        # o `ROTULO_DO_CLIQUE` era citado no uso (`:1392` em 25/10), que o repete na de baixo
        corpo = (RAIZ / arquivo).read_text(encoding="utf-8").split("\n")
        velho, linha = nome, next(
            n for n in range(1, len(corpo))
            if f"{nome}[" in corpo[n - 1] and f"{nome}[" in corpo[n])

    queixas = _queixas(val, _montar(tmp_path, arquivo, linha, velho, None))

    assert any("vizinha da citada" in q for q in queixas), queixas


AS_CINCO_LIGACOES = [
    # (aba, começo da feature, arquivo citado, nome): as cinco da lista da sprint que citam o
    # `def`, cujo `@gesto` repete o nome na linha de cima: a regra do vizinho as guarda
    ("04-iluminacao", "Botão de reenvio explícito da cor",
     "src/hefesto_dualsense4unix/interface/pacotes/a04_iluminacao.py", "cor"),
    ("08-conexoes", 'Alvo de saída ("só este"',
     "src/hefesto_dualsense4unix/interface/pacotes/a08_conexoes.py", "alvo"),
    ("09-sistema", 'Botão "Reiniciar o serviço"',
     "src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py", "reiniciar"),
    ("09-sistema", 'Botão "Atualizar"',
     "src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py", "atualizar"),
    ("09-sistema", 'Chave "Ligar junto com o computador" — AÇÃO',
     "src/hefesto_dualsense4unix/interface/pacotes/a09_sistema.py", "autostart"),
]


def _montar_sem_a_linha(tmp_path: Path, arquivo: str, linha: int, nome: str) -> Path:
    """Como :func:`_montar`, com a última linha em branco acima da citada arrancada (o arquivo
    continua compilando, e a ligação continua sendo lida)."""
    planilha = _montar(tmp_path, arquivo, linha, nome, None)
    alvo = planilha.parents[2] / arquivo
    corpo = alvo.read_text(encoding="utf-8").split("\n")
    del corpo[max(n for n in range(linha - 1) if not corpo[n].strip())]
    alvo.write_text("\n".join(corpo), encoding="utf-8")
    return planilha


@pytest.mark.parametrize(
    ("aba", "feature", "arquivo", "nome"), AS_CINCO_LIGACOES,
    ids=[f"{o[0]}-{o[3]}" for o in AS_CINCO_LIGACOES],
)
def test_a_linha_a_mais_ou_a_menos_acima_do_def_das_cinco_reprova(
    val: ModuleType, tmp_path: Path, aba: str, feature: str, arquivo: str, nome: str
) -> None:
    """Deslocada uma linha, a citação cai no decorador (ou na docstring), que também tem o nome:
    só a regra do vizinho a reprova, e é esta prova que morde a régua com os dados de hoje."""
    linha = _linha_da_celula(aba, feature, arquivo, nome)

    assert _queixas(val, _montar(tmp_path / "hoje", arquivo, linha, nome, None)) == []
    acima = _queixas(val, _montar(tmp_path / "acima", arquivo, linha, nome, 1))
    assert acima, f"uma linha inserida no começo deixou `{nome}` verde na {linha}"
    tirada = _queixas(val, _montar_sem_a_linha(tmp_path / "tirada", arquivo, linha, nome))
    assert tirada, f"uma linha em branco tirada acima deixou `{nome}` verde na {linha}"


ALVO_COM_DECORADOR = '''"""O alvo."""


def gesto(*_a):
    return lambda f: f


@gesto("página", "reiniciar")
def reiniciar():
    return 1


VALOR = "reiniciar"
x = VALOR
'''


@pytest.mark.parametrize(
    ("linha", "nome", "verde"),
    [
        pytest.param(9, "reiniciar", True, id="o-def-liga-o-nome-que-o-decorador-repete"),
        pytest.param(8, "reiniciar", False, id="o-decorador-nao-liga-nada"),
        pytest.param(13, "VALOR", True, id="a-atribuicao-liga-o-nome"),
        pytest.param(14, "VALOR", False, id="o-uso-ao-lado-da-atribuicao"),
    ],
)
def test_o_nome_que_a_linha_liga_e_so_dela(
    val: ModuleType, tmp_path: Path, linha: int, nome: str, verde: bool
) -> None:
    arquivo = "src/hefesto_dualsense4unix/alvo.py"
    (tmp_path / arquivo).parent.mkdir(parents=True)
    (tmp_path / arquivo).write_text(ALVO_COM_DECORADOR, encoding="utf-8")
    planilha = tmp_path / "docs" / "data" / "x.csv"
    planilha.parent.mkdir(parents=True)
    planilha.write_text(f"id,onde\na,{arquivo}:{linha} (`{nome}`)\n", encoding="utf-8")

    queixas = [str(a) for a in val.varrer_planilha(planilha, tmp_path, {})[0]]

    assert (queixas == []) is verde, queixas


def test_a_faixa_nao_passa_pela_regra_do_vizinho(val: ModuleType, tmp_path: Path) -> None:
    """A faixa ``:a-b`` já diz o trecho inteiro: a regra é só da citação de UMA linha."""
    arquivo = "src/hefesto_dualsense4unix/alvo.py"
    (tmp_path / arquivo).parent.mkdir(parents=True)
    (tmp_path / arquivo).write_text(ALVO_COM_DECORADOR, encoding="utf-8")
    planilha = tmp_path / "docs" / "data" / "x.csv"
    planilha.parent.mkdir(parents=True)
    planilha.write_text(f"id,onde\na,{arquivo}:13-14 (`VALOR`)\n", encoding="utf-8")

    assert [str(a) for a in val.varrer_planilha(planilha, tmp_path, {})[0]] == []


# --- 3. o reapontar não leva a casa-sabe pelo caminho que só a mão confere ----------------------


def _casa_crua(um: int, dois: int, quatro: int) -> str:
    end = "src/hefesto_dualsense4unix/alvo.py"
    return (f'RAZAO = (\n    "Um, {end}:{um}. Dois, {end}:{dois}. "\n'
            f'    "Quatro, {end}:{quatro}."\n)\n')


def test_no_codigo_a_massa_nao_da_segunda_chance_e_a_crua_vai_a_mao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O mesmo enredo em que a segunda chance leva o documento (nasce certo, o código anda 4, a
    massa acompanha, o código anda 12): no arquivo de código ela não vale, e as três vão à mão."""
    from tests.unit.test_as_citacoes_andam_com_o_codigo import ALVO as ALVO_DA_SEGUNDA_CHANCE
    from tests.unit.test_as_citacoes_andam_com_o_codigo import (
        _escrever_e_commitar,
        _inserir_no_topo,
    )

    raiz = tmp_path / "repo"
    (raiz / "src" / "hefesto_dualsense4unix").mkdir(parents=True)
    (raiz / "src" / "hefesto_dualsense4unix" / "alvo.py").write_text(
        ALVO_DA_SEGUNDA_CHANCE, encoding="utf-8")
    (raiz / "docs" / "protocol").mkdir(parents=True)
    _git(raiz, "init", "-q")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "o alvo nasce")
    mod = _carregar(REAPONTAR, "reapontar_citacoes")
    monkeypatch.setattr(mod, "REESCRITA_EM_MASSA", 3)
    casa = _escrever_e_commitar(raiz, CASA_SABE, _casa_crua(3, 10, 15), "nasce certo")
    _inserir_no_topo(raiz, 4, commitar=True)
    casa.write_text(_casa_crua(7, 14, 19), encoding="utf-8")
    _git(raiz, "commit", "-q", "-am", "o reapontamento em massa acompanha")
    _inserir_no_topo(raiz, 12, commitar=True)

    feitos, a_mao = mod.reapontar(raiz, escrever=True)

    assert casa.read_text(encoding="utf-8") == _casa_crua(7, 14, 19), (feitos, a_mao)
    mao = [f for f in a_mao if "só se reaponta em massa à mão" in f]
    assert len(mao) == 3, a_mao


def test_a_queixa_de_forma_nao_move_a_citacao(repo: Path) -> None:
    """O nome que casa também na vizinha é queixa de FORMA (o decorador citado, e o `def` logo
    abaixo com o mesmo nome): o código não andou, e o reapontar não a leva; ela vai à mão."""
    arquivo = "src/hefesto_dualsense4unix/alvo.py"
    (repo / arquivo).write_text(ALVO_COM_DECORADOR, encoding="utf-8")
    (repo / CASA_SABE).write_text('RAZAO = "sem citação"\n', encoding="utf-8")
    planilha = repo / "docs" / "data" / "x.csv"
    planilha.write_text(f"id,onde\na,{arquivo}:8 (`reiniciar`)\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "a planilha cita o decorador")
    antes = planilha.read_text(encoding="utf-8")

    feitos, a_mao = _carregar(REAPONTAR, "reapontar_citacoes").reapontar(repo, escrever=True)

    assert planilha.read_text(encoding="utf-8") == antes, (feitos, a_mao)
    assert any("é de forma, e se cura à mão" in f and "x.csv" in f for f in a_mao), a_mao


# --- o `--novas` lê as cadeias da casa-sabe ------------------------------------------------------


def _casa_sabe_com(razao: str) -> str:
    return f'RAZOES = {{\n    "x.py::fala": (\n        "{razao}"\n    ),\n}}\n'


def _repo_da_casa_sabe(tmp_path: Path, razao: str) -> Path:
    """O `dev` já com a casa-sabe de ``razao``; o HEAD no ramo nascido dele."""
    from tests.unit.test_a_citacao_nova_de_linha_promete_o_nome import (
        _commita,
        _escreve,
        _git,
        _repo,
    )

    raiz = _repo(tmp_path, "# P\n")
    _escreve(raiz, CASA_SABE, _casa_sabe_com(razao))
    _commita(raiz)
    _git(raiz, "branch", "-f", "dev", "ramo")
    return raiz


@pytest.mark.parametrize(("antes", "depois", "rc"), [
    ("o laço mora em `fala` em `x.py:3`.", "o laço mora em `x.py:3`, e o resto em `x.py:8`.", 1),
    ("o laço mora em `x.py:3`.", "o laço mora em `x.py:4`.", 0),
    ("nada aqui.", "o laço mora em `fala` em `x.py:3`, e `x.py:8` (`guarda`).", 0),
])
def test_a_crua_nova_na_casa_sabe_reprova_o_novas(
        tmp_path: Path, antes: str, depois: str, rc: int) -> None:
    from tests.unit.test_a_citacao_nova_de_linha_promete_o_nome import _commita, _escreve, _roda

    raiz = _repo_da_casa_sabe(tmp_path, antes)
    _escreve(raiz, CASA_SABE, _casa_sabe_com(depois))
    _commita(raiz)

    feito = _roda(raiz)

    assert feito.returncode == rc, feito.stdout + feito.stderr
    if rc:
        assert f"{CASA_SABE}:3" in feito.stdout and "sem nome prometido" in feito.stdout
