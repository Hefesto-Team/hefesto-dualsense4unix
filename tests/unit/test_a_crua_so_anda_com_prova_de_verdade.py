"""A citação crua só anda com prova de verdade, e o rc do reapontar diz o que FALTA.

Fonte: o conferente da `ferramentas-1-8` (08/10/2026). Três furos do `reapontar-citacoes.py`:

1. a linha ``</span>`` era «longa» (7 caracteres) e a troca ia para a primeira ``</span>`` única;
2. o endereço que uma varredura ou um reapontamento em massa deixou ia sempre à mão, mesmo quando o
   endereço de ANTES dele provava onde o bloco estava (a «segunda chance»);
3. o rc valia 1 pela dívida inteira (1033 «à mão» de antes), e ninguém via o que a mudança de agora
   quebrou.

Os esperados são escritos à mão, a partir do fixture: o ALVO de mentira tem ``VALOR`` na linha 3,
``def segunda():`` na 10, ``return x`` na 12 e ``def terceira():`` na 15; inserir N linhas no topo
empurra tudo N para baixo.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from tests.unit.test_as_citacoes_andam_com_o_codigo import (
    ALVO,
    _escrever_e_commitar,
    _git,
    _inserir_no_topo,
    _script,
)

RAIZ = Path(__file__).resolve().parents[2]
END = "src/hefesto_dualsense4unix/alvo.py"
PAG = "src/hefesto_dualsense4unix/pagina.html"
CURTO = "src/hefesto_dualsense4unix/curto.py"

PAGINA = '<html>\n<body>\n<div id="x">\n<p>texto</p>\n</span>\n</div>\n<br>\n</body>\n</html>\n'


@pytest.fixture()
def repo(tmp_path: Path) -> Iterator[Path]:
    raiz = tmp_path / "repo"
    pacote = raiz / "src" / "hefesto_dualsense4unix"
    pacote.mkdir(parents=True)
    (pacote / "alvo.py").write_text(ALVO, encoding="utf-8")
    (raiz / "docs" / "protocol").mkdir(parents=True)
    _git(raiz, "init", "-q")
    _git(raiz, "add", ".")
    _git(raiz, "commit", "-q", "-m", "o alvo nasce")
    yield raiz


def _empurrar_a_pagina(raiz: Path, linhas: int) -> None:
    pagina = raiz / PAG
    novas = "".join(f"<!-- extra {n} -->\n" for n in range(linhas))
    pagina.write_text(novas + pagina.read_text(encoding="utf-8"), encoding="utf-8")
    _git(raiz, "commit", "-q", "-am", "a página anda")


def _varrer(raiz: Path, arquivos: int) -> None:
    for i in range(arquivos):
        (raiz / "docs" / f"outro{i}.txt").write_text("varrido\n", encoding="utf-8")


@pytest.mark.parametrize(
    ("linha", "uteis"),
    [
        ("</span>", 0),
        ("</div>", 0),
        ("<br>", 0),
        ("<br />", 0),
        ("    }", 0),
        ("})", 0),
        ("pass", 4),
        ("PAR = (1, 2)", 5),
        ("VALOR = 1", 6),
        ("return x", 7),
        ('<div id="x">', 12),
        ('<span class="a">texto</span>', 21),
    ],
)
def test_a_linha_conta_o_que_diz_e_nao_o_cenario(linha: str, uteis: int) -> None:
    assert _script()._caracteres_uteis(linha) == uteis  # type: ignore[no-untyped-call]


def test_a_marcacao_sem_atributo_vai_a_mao_e_a_linha_com_conteudo_anda(repo: Path) -> None:
    """``</span>`` e ``</div>`` (7 e 6 caracteres) são únicos e NÃO identificam o citado."""
    _escrever_e_commitar(repo, PAG, PAGINA, "a página nasce")
    doc = _escrever_e_commitar(
        repo,
        "docs/protocol/pagina.md",
        f"# Página\n\nA caixa, `{PAG}:3`; o fecho do span, `{PAG}:5`; o do div, `{PAG}:6`;"
        f" a quebra, `{PAG}:7`.\n",
        "o documento nasce",
    )
    _empurrar_a_pagina(repo, 12)

    feitos, a_mao = _script().reapontar(repo, escrever=True)  # type: ignore[no-untyped-call]

    texto = doc.read_text(encoding="utf-8")
    assert f"`{PAG}:15`" in texto, "a tag com atributo identifica e anda (3 + 12)"
    for ainda in (5, 6, 7):
        assert f"`{PAG}:{ainda}`" in texto, f"a linha {ainda} é marcação solta: fica como estava"
    assert not any(f"{PAG}:{n}`" in f for f in feitos for n in (5, 6, 7)), feitos
    curtas = [f for f in a_mao if "pagina.md" in f and "curta demais" in f]
    assert len(curtas) == 3, a_mao
    assert all("só marcação ou pontuação" in f for f in curtas), curtas


def test_a_linha_de_codigo_com_conteudo_segue_a_regra_e_anda(repo: Path) -> None:
    """``return x`` (8 caracteres, 7 úteis) é código: anda 12 linhas junto com o alvo."""
    doc = _escrever_e_commitar(
        repo, "docs/protocol/regra.md", f"# Regra\n\nO retorno, `{END}:12`.\n", "o documento nasce"
    )
    _inserir_no_topo(repo, 12, commitar=True)

    _feitos, a_mao = _script().reapontar(repo, escrever=True)  # type: ignore[no-untyped-call]

    assert a_mao == [], a_mao
    assert doc.read_text(encoding="utf-8") == f"# Regra\n\nO retorno, `{END}:24`.\n"


def test_a_varredura_de_duzentos_arquivos_anda_pelo_endereco_de_antes(repo: Path) -> None:
    """O caso do `aba02.py:2268`, sem trocar a constante: 200 arquivos, e ficou ``:12``.

    O documento citava ``:10`` (``def segunda():``) e já existia; a varredura moveu o código
    4 linhas e reescreveu o endereço para ``:12`` (errado). A linha de antes prova o bloco: hoje
    ele está na 14."""
    doc = _escrever_e_commitar(
        repo, "docs/protocol/velho.md", f"# Velho\n\nO corpo, `{END}:10`.\n", "o endereço entra"
    )
    _inserir_no_topo(repo, 4, commitar=False)
    doc.write_text(f"# Velho\n\nO corpo, `{END}:12`.\n", encoding="utf-8")
    _varrer(repo, 200)
    _git(repo, "add", "docs", "src")
    _git(repo, "commit", "-q", "-m", "a varredura")
    mod = _script()  # type: ignore[no-untyped-call]
    assert mod.VARREDURA_DE_ARQUIVOS == 200, "a premissa: a constante de verdade"

    feitos, a_mao = mod.reapontar(repo, escrever=True)

    assert a_mao == [], a_mao
    assert doc.read_text(encoding="utf-8") == f"# Velho\n\nO corpo, `{END}:14`.\n"
    assert any(f"`{END}:12` -> `{END}:14`" in f for f in feitos), feitos
    assert mod.ESTATISTICA["segunda_chance"] == 1, mod.ESTATISTICA
    assert mod.ESTATISTICA["segunda_chance:andou"] == 1, mod.ESTATISTICA


def test_a_varredura_que_acertou_deixa_o_endereco_no_lugar(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A varredura moveu o código 4 linhas e escreveu ``:14``: o bloco de antes já está lá."""
    mod = _script()  # type: ignore[no-untyped-call]
    monkeypatch.setattr(mod, "VARREDURA_DE_ARQUIVOS", 3)
    doc = _escrever_e_commitar(
        repo, "docs/protocol/velho.md", f"# Velho\n\nO corpo, `{END}:10`.\n", "o endereço entra"
    )
    _inserir_no_topo(repo, 4, commitar=False)
    doc.write_text(f"# Velho\n\nO corpo, `{END}:14`.\n", encoding="utf-8")
    _varrer(repo, 3)
    _git(repo, "add", "docs", "src")
    _git(repo, "commit", "-q", "-am", "a varredura")
    antes = doc.read_text(encoding="utf-8")

    feitos, a_mao = mod.reapontar(repo, escrever=True)

    assert (feitos, a_mao) == ([], [])
    assert doc.read_text(encoding="utf-8") == antes
    assert mod.ESTATISTICA["segunda_chance:no_lugar"] == 1, mod.ESTATISTICA


def test_a_varredura_sem_o_endereco_de_antes_continua_a_mao(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A linha de antes não tinha endereço: não há par, e o motivo diz que a chance falhou."""
    mod = _script()  # type: ignore[no-untyped-call]
    monkeypatch.setattr(mod, "VARREDURA_DE_ARQUIVOS", 3)
    doc = _escrever_e_commitar(
        repo, "docs/protocol/velho.md", "# Velho\n\nSai de `x`.\n", "um documento que já existia"
    )
    _inserir_no_topo(repo, 4, commitar=False)
    doc.write_text(f"# Velho\n\nO corpo, `{END}:12`.\n", encoding="utf-8")
    _varrer(repo, 3)
    _git(repo, "add", "docs", "src")
    _git(repo, "commit", "-q", "-am", "a varredura")
    antes = doc.read_text(encoding="utf-8")

    _feitos, a_mao = mod.reapontar(repo, escrever=True)

    assert doc.read_text(encoding="utf-8") == antes
    mao = [f for f in a_mao if "velho.md" in f]
    assert len(mao) == 1 and "varredura" in mao[0] and "sem segunda chance" in mao[0], a_mao


@pytest.mark.parametrize(("antes", "depois"), [("10", "12-13"), ("10-12", "12")])
def test_a_varredura_que_mudou_a_largura_nao_tem_par_e_fica_a_mao(
    repo: Path, monkeypatch: pytest.MonkeyPatch, antes: str, depois: str
) -> None:
    """A varredura trocou ``:10`` por ``:12-13`` (ou ``:10-12`` por ``:12``): o bloco de antes tem
    outra largura que o endereço de hoje. Levá-lo escreveria ``:14-14`` (ou cortaria a faixa em
    ``:14``), um endereço que ninguém escreveu: sem chute, vai à mão e o documento fica."""
    mod = _script()  # type: ignore[no-untyped-call]
    monkeypatch.setattr(mod, "VARREDURA_DE_ARQUIVOS", 3)
    doc = _escrever_e_commitar(
        repo,
        "docs/protocol/largo.md",
        f"# Largo\n\nO corpo, `{END}:{antes}`.\n",
        "o endereço entra",
    )
    _inserir_no_topo(repo, 4, commitar=False)
    doc.write_text(f"# Largo\n\nO corpo, `{END}:{depois}`.\n", encoding="utf-8")
    _varrer(repo, 3)
    _git(repo, "add", "docs", "src")
    _git(repo, "commit", "-q", "-am", "a varredura")

    feitos, a_mao = mod.reapontar(repo, escrever=True)

    assert doc.read_text(encoding="utf-8") == f"# Largo\n\nO corpo, `{END}:{depois}`.\n", feitos
    mao = [f for f in a_mao if "largo.md" in f]
    assert len(mao) == 1 and "sem segunda chance" in mao[0] and "largura" in mao[0], a_mao


def test_a_linha_que_virou_duas_nao_tem_par_e_fica_a_mao(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O reapontamento em massa quebrou a linha em duas (uma removida, duas novas): sem chute."""
    mod = _script()  # type: ignore[no-untyped-call]
    monkeypatch.setattr(mod, "REESCRITA_EM_MASSA", 3)
    doc = _escrever_e_commitar(
        repo,
        "docs/protocol/massa.md",
        f"# Massa\n\nUm, `{END}:3`. Dois, `{END}:10`. Quatro, `{END}:15`.\n",
        "o documento já existia",
    )
    doc.write_text(
        f"# Massa\n\nUm, `{END}:4`. Dois, `{END}:5`.\nQuatro, `{END}:6`.\n", encoding="utf-8"
    )
    _git(repo, "commit", "-q", "-am", "o reapontamento, com a linha quebrada")
    _inserir_no_topo(repo, 12, commitar=True)
    antes = doc.read_text(encoding="utf-8")

    _feitos, a_mao = mod.reapontar(repo, escrever=True)

    assert doc.read_text(encoding="utf-8") == antes
    mao = [f for f in a_mao if "massa.md" in f]
    assert len(mao) == 3, a_mao
    assert all("reapontamento em massa" in f and "sem segunda chance" in f for f in mao), mao


def test_duas_voltas_atras_ainda_e_prova(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Dois reapontamentos em fila: o de antes do segundo é o primeiro (também massa), e o de antes
    DELE é o nascimento do documento, que é prova. A segunda chance dá exatamente duas voltas."""
    mod = _script()  # type: ignore[no-untyped-call]
    monkeypatch.setattr(mod, "REESCRITA_EM_MASSA", 3)
    doc = _escrever_e_commitar(
        repo,
        "docs/protocol/cadeia.md",
        f"# Cadeia\n\nUm, `{END}:3`. Dois, `{END}:10`. Quatro, `{END}:15`.\n",
        "o documento já existia",
    )
    for um, dois, quatro in ((4, 5, 6), (7, 8, 9)):
        doc.write_text(
            f"# Cadeia\n\nUm, `{END}:{um}`. Dois, `{END}:{dois}`. Quatro, `{END}:{quatro}`.\n",
            encoding="utf-8",
        )
        _git(repo, "commit", "-q", "-am", f"o reapontamento em massa {um}")
    _inserir_no_topo(repo, 12, commitar=True)

    _feitos, a_mao = mod.reapontar(repo, escrever=True)

    assert a_mao == [], a_mao
    assert doc.read_text(encoding="utf-8") == (
        f"# Cadeia\n\nUm, `{END}:15`. Dois, `{END}:22`. Quatro, `{END}:27`.\n"
    )


def test_tres_voltas_atras_ja_nao_e_prova_e_o_motivo_diz_por_que(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mod = _script()  # type: ignore[no-untyped-call]
    monkeypatch.setattr(mod, "REESCRITA_EM_MASSA", 3)
    doc = _escrever_e_commitar(
        repo,
        "docs/protocol/cadeia.md",
        f"# Cadeia\n\nUm, `{END}:3`. Dois, `{END}:10`. Quatro, `{END}:15`.\n",
        "o documento já existia",
    )
    for um, dois, quatro in ((4, 5, 6), (7, 8, 9), (1, 2, 13)):
        doc.write_text(
            f"# Cadeia\n\nUm, `{END}:{um}`. Dois, `{END}:{dois}`. Quatro, `{END}:{quatro}`.\n",
            encoding="utf-8",
        )
        _git(repo, "commit", "-q", "-am", f"o reapontamento em massa {um}")
    _inserir_no_topo(repo, 12, commitar=True)
    antes = doc.read_text(encoding="utf-8")

    _feitos, a_mao = mod.reapontar(repo, escrever=True)

    assert doc.read_text(encoding="utf-8") == antes
    mao = [f for f in a_mao if "cadeia.md" in f]
    assert len(mao) == 3, a_mao
    assert all("2 voltas atrás" in f for f in mao), mao


def _main(mod: ModuleType, raiz: Path, *args: str) -> int:
    return int(mod.main(["--root", str(raiz), *args]))


def _commit_de(raiz: Path) -> str:
    return _git(raiz, "rev-parse", "HEAD").strip()


def _tres_massas_e_o_codigo_andou(repo: Path) -> Path:
    doc = _escrever_e_commitar(
        repo,
        "docs/protocol/cadeia.md",
        f"# Cadeia\n\nUm, `{END}:3`. Dois, `{END}:10`. Quatro, `{END}:15`.\n",
        "o documento já existia",
    )
    for um, dois, quatro in ((4, 5, 6), (7, 8, 9), (1, 2, 13)):
        doc.write_text(
            f"# Cadeia\n\nUm, `{END}:{um}`. Dois, `{END}:{dois}`. Quatro, `{END}:{quatro}`.\n",
            encoding="utf-8",
        )
        _git(repo, "commit", "-q", "-am", f"o reapontamento em massa {um}")
    _inserir_no_topo(repo, 12, commitar=True)
    return doc


def test_so_a_divida_de_antes_nao_derruba_o_rc_e_aparece_contada(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = _script()  # type: ignore[no-untyped-call]
    monkeypatch.setattr(mod, "REESCRITA_EM_MASSA", 3)
    _tres_massas_e_o_codigo_andou(repo)

    rc = _main(mod, repo)

    saida = capsys.readouterr().out
    assert rc == 0, saida
    assert "3 à mão (o script não chuta): 0 nova(s) desde" in saida, saida
    assert "3 de antes" in saida, saida
    assert "à mão DE ANTES" in saida and "varredura ou massa sem prova" in saida, saida
    assert "à mão NOVA" not in saida, saida


def test_o_que_a_mudanca_de_agora_quebrou_derruba_o_rc(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """O endereço é de antes do ``--desde``; o commit depois dele mudou a linha citada, e o bloco
    não sobrevive em lugar nenhum: é à mão NOVA, e o rc vale 1. Sem ``--desde`` (o HEAD, já com a
    mudança) a mesma linha é dívida de antes."""
    _escrever_e_commitar(
        repo, "docs/protocol/doc.md", f"# Doc\n\nO corpo, `{END}:10`.\n", "o endereço entra"
    )
    ref = _commit_de(repo)
    alvo = repo / END
    alvo.write_text(
        alvo.read_text(encoding="utf-8").replace("def segunda():", "def outra_coisa():"),
        encoding="utf-8",
    )
    _inserir_no_topo(repo, 3, commitar=False)
    _git(repo, "commit", "-q", "-am", "o corpo mudou e andou")

    mod = _script()  # type: ignore[no-untyped-call]
    rc_novo = _main(mod, repo, "--desde", ref)
    saida_nova = capsys.readouterr().out
    rc_sem = _main(mod, repo)
    saida_sem = capsys.readouterr().out
    rc_cabeca = _main(mod, repo, "--desde", "HEAD")
    capsys.readouterr()

    assert rc_novo == 1, saida_nova
    assert "à mão NOVA" in saida_nova and "doc.md" in saida_nova, saida_nova
    assert "1 nova(s) desde" in saida_nova, saida_nova
    assert rc_sem == 0, saida_sem
    assert "0 nova(s)" in saida_sem and "1 de antes" in saida_sem, saida_sem
    assert rc_cabeca == 0


def test_o_endereco_que_entrou_depois_do_ref_e_nao_se_leva_e_novo(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Documento escrito DEPOIS do ``--desde``, citando uma linha que não identifica nada."""
    _escrever_e_commitar(repo, CURTO, "X = dict(\n    a=1,\n)\n", "o curto nasce")
    ref = _commit_de(repo)
    _escrever_e_commitar(
        repo, "docs/protocol/fecho.md", f"# Fecho\n\nO fecho, `{CURTO}:3`.\n", "a crua nasce"
    )

    mod = _script()  # type: ignore[no-untyped-call]
    rc_novo = _main(mod, repo, "--desde", ref)
    saida = capsys.readouterr().out
    rc_depois = _main(mod, repo, "--desde", "HEAD")
    capsys.readouterr()

    assert rc_novo == 1, saida
    assert "à mão NOVA" in saida and "fecho.md" in saida and "curta demais" in saida, saida
    assert rc_depois == 0


def test_o_endereco_escrito_depois_do_ref_num_documento_que_ja_existia_e_novo(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """O documento existia no ``--desde``, sem a citação; ela entrou depois e não se leva. O citado
    não mudou: só a conta do endereço no documento diz que é desta mudança."""
    _escrever_e_commitar(repo, CURTO, "X = dict(\n    a=1,\n)\n", "o curto nasce")
    _escrever_e_commitar(repo, "docs/protocol/fecho.md", "# Fecho\n\nAinda nada.\n", "o doc nasce")
    ref = _commit_de(repo)
    _escrever_e_commitar(
        repo, "docs/protocol/fecho.md", f"# Fecho\n\nO fecho, `{CURTO}:3`.\n", "a crua entra"
    )

    mod = _script()  # type: ignore[no-untyped-call]
    rc_novo = _main(mod, repo, "--desde", ref)
    saida = capsys.readouterr().out
    rc_depois = _main(mod, repo, "--desde", "HEAD")
    capsys.readouterr()

    assert rc_novo == 1, saida
    assert "1 nova(s) desde" in saida and "fecho.md" in saida, saida
    assert rc_depois == 0


def test_sem_desde_o_ref_e_o_merge_base_com_dev(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A integração nasce do ``dev``: sem ``--desde``, o que mudou desde o ``merge-base`` com ele é
    desta mudança, mesmo já commitado (com o HEAD como ref, a mesma linha seria dívida de antes)."""
    _escrever_e_commitar(
        repo, "docs/protocol/doc.md", f"# Doc\n\nO corpo, `{END}:10`.\n", "o endereço entra"
    )
    ref = _commit_de(repo)
    _git(repo, "checkout", "-q", "-b", "trabalho")
    _git(repo, "branch", "-f", "dev", ref)
    alvo = repo / END
    alvo.write_text(
        alvo.read_text(encoding="utf-8").replace("def segunda():", "def outra_coisa():"),
        encoding="utf-8",
    )
    _inserir_no_topo(repo, 3, commitar=False)
    _git(repo, "commit", "-q", "-am", "o corpo mudou e andou, depois do dev")

    mod = _script()  # type: ignore[no-untyped-call]
    rc = _main(mod, repo)
    saida = capsys.readouterr().out
    rc_cabeca = _main(mod, repo, "--desde", "HEAD")
    capsys.readouterr()

    assert rc == 1, saida
    assert f"1 nova(s) desde {ref[:9]}" in saida, saida
    assert rc_cabeca == 0


def test_a_troca_pendente_em_modo_lista_derruba_o_rc_e_escrever_zera(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc = _escrever_e_commitar(
        repo, "docs/protocol/doc.md", f"# Doc\n\nO corpo, `{END}:10`.\n", "o endereço entra"
    )
    _inserir_no_topo(repo, 12, commitar=True)
    antes = doc.read_text(encoding="utf-8")

    mod = _script()  # type: ignore[no-untyped-call]
    rc_lista = _main(mod, repo)
    saida = capsys.readouterr().out
    assert doc.read_text(encoding="utf-8") == antes, "o modo lista não escreve"
    rc_escrever = _main(mod, repo, "--escrever")
    capsys.readouterr()
    rc_limpo = _main(mod, repo)
    capsys.readouterr()

    assert rc_lista == 1, saida
    assert f"`{END}:10` -> `{END}:22`" in saida, saida
    assert doc.read_text(encoding="utf-8") == f"# Doc\n\nO corpo, `{END}:22`.\n"
    assert rc_escrever == 0
    assert rc_limpo == 0


def test_arvore_limpa_com_desde_head_e_rc_zero(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _escrever_e_commitar(
        repo, "docs/protocol/doc.md", f"# Doc\n\nO corpo, `{END}:10`.\n", "o endereço entra"
    )

    rc = _main(_script(), repo, "--desde", "HEAD")  # type: ignore[no-untyped-call]

    saida = capsys.readouterr().out
    assert rc == 0, saida
    assert "nova(s)" not in saida and "à mão NOVA" not in saida, saida


def test_o_desde_que_nao_e_commit_e_recusado_antes_de_ler(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as parou:
        _main(_script(), repo, "--desde", "nao-existe-este-commit")  # type: ignore[no-untyped-call]

    erro = capsys.readouterr().err
    assert parou.value.code == 2
    assert "não é um commit" in erro, erro
    with pytest.raises(ValueError, match="não é um commit"):
        _script().reapontar(repo, escrever=False, desde="nao-existe-este-commit")  # type: ignore[no-untyped-call]


def test_o_help_diz_a_segunda_chance_a_profundidade_e_o_rc() -> None:
    feito = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "reapontar-citacoes.py"), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    ajuda = " ".join(feito.stdout.split())
    assert "SEGUNDA CHANCE" in ajuda and "2 voltas atrás" in ajuda, ajuda
    assert "TER CONTEÚDO" in ajuda and "</span>" in ajuda, ajuda
    assert "--desde" in ajuda and "O RC diz o que FALTA" in ajuda, ajuda
