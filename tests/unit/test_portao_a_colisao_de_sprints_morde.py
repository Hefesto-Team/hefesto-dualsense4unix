"""O PORTÃO DA COLISÃO DE SPRINTS — e ele tem de acusar o que a MÃO achou.

Em 23/08/2026 quatro colisões de posse passaram sem ser declaradas, e só
apareceram no conferente humano depois de tudo escrito. A mais cara não é
nenhuma das quatro: é ``PAREAMENTO-01 x Z6``, que mandam **criar os mesmos
quatro módulos** -- e naquele dia esses módulos **não existiam no disco**, então
nenhum ``grep`` na árvore os acharia. Onze mais seis agentes para a mesma obra.
(Os quatro passaram a existir em 24/08, quando a Z6 fechou; por isso o dublê
deste teste usa caminhos fictícios -- ver a nota datada em ``_OS_QUATRO``.)

O QUE ESTE PORTÃO COBRA, e é o teste do desenho e não do código:

  - o par que a mão achou é acusado, e nomeando os arquivos;
  - **arrancar o campo ``cria:`` faz o par PAREAMENTO x Z6 DESAPARECER** -- é a
    mordida que prova qual é o campo caro (``test_sem_o_campo_cria_a_duplicata
    _some``);
  - colisão **declarada** (``depois_de`` ou ``nao_toca``) não é acusada: a régua
    separa descuido de decisão, senão vira ruído e alguém a desliga;
  - **citação não é posse**: uma sprint que só MENCIONA um arquivo no corpo não
    o reivindica. Uma régua ingênua leria a coluna "NÃO toca" da Z7 como
    reivindicação de ``daemon_actions.py`` e acusaria quem fez a coisa certa.

E ele **nasce reprovando ZERO** contra a árvore de verdade, de propósito: sprint
sem frontmatter entra na lista de DÍVIDA, não numa reprovação. Portão que reprova
vinte e três de uma vez é portão que alguém desliga na segunda-feira.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "check_colisao_de_sprints.py"

_spec = importlib.util.spec_from_file_location("_colisao", SCRIPT)
assert _spec and _spec.loader
colisao = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(colisao)


# Os quatro módulos do par PAREAMENTO x Z6.
#
# NOTA DATADA — 25/08/2026: quando a INFRA-DE-EXECUCAO-01 os mediu, em 24/08,
# os quatro NÃO existiam, e era esse o ponto. **Hoje os quatro existem**: a Z6
# fechou e os criou. O par continua valendo como o caso a reproduzir, mas o
# dublê deste teste NÃO pode usar os caminhos reais, ou a prova de "nenhum grep
# acharia" deixa de provar coisa alguma. Por isso os caminhos abaixo são
# deliberadamente fictícios -- e há uma guarda que reprova se algum dia
# passarem a existir.
_OS_QUATRO = [
    "scripts/gerar-fatos-de-tela-que-ninguem-escreveu.py",
    "src/hefesto_dualsense4unix/app/fatos_do_mapa_que_ninguem_escreveu.py",
    "src/hefesto_dualsense4unix/app/fala_do_mapa_que_ninguem_escreveu.py",
    "scripts/validar-fala-de-tela-que-ninguem-escreveu.py",
]


def _sprint(nome: str, *, posse=None, cria=None, depois_de=None, nao_toca=None) -> str:
    linhas = ["---", f"sprint: {nome}", "posse:"]
    for agente, arquivos in (posse or {}).items():
        linhas.append(f"  {agente}:")
        linhas += [f"    - {a}" for a in arquivos]
    linhas.append("cria:")
    linhas += [f"  - {a}" for a in (cria or [])]
    linhas.append("bancada: false")
    linhas.append("depois_de:")
    linhas += [f"  - {a}" for a in (depois_de or [])]
    linhas.append("nao_toca:")
    linhas += [f"  - {a}" for a in (nao_toca or [])]
    linhas += ["---", "", "# o corpo, que a régua NUNCA lê", ""]
    return "\n".join(linhas)


def _confere(**sprints: str) -> list[str]:
    anotadas = {}
    for nome, texto in sprints.items():
        dados = colisao.le_frontmatter(texto, nome)
        assert dados is not None, f"o dublê {nome} não foi lido como frontmatter"
        anotadas[Path(nome)] = dados
    return colisao.confere(anotadas)


# ---------------------------------------------------------------------------
# Os pares que a mão achou
# ---------------------------------------------------------------------------


def test_acusa_o_par_que_reivindica_os_mesmos_arquivos() -> None:
    """Z1 x Z2 — os mesmos quatro arquivos, e nenhuma das duas o declarou."""
    quatro = [
        "src/hefesto_dualsense4unix/app/textos_de_aplicacao.py",
        "src/hefesto_dualsense4unix/app/lightbar_actions.py",
        "src/hefesto_dualsense4unix/app/triggers_actions.py",
        "src/hefesto_dualsense4unix/app/rumble_actions.py",
    ]
    queixas = _confere(
        z1=_sprint("ONDA0-Z1", posse={"A": quatro}),
        z2=_sprint("ONDA0-Z2", posse={"B": quatro}),
    )
    assert len(queixas) == 1, queixas
    assert "ONDA0-Z1 x ONDA0-Z2" in queixas[0]
    for arquivo in quatro:
        assert arquivo in queixas[0], "a acusação não nomeia " + arquivo


def test_acusa_a_duplicata_de_arquivo_que_ainda_nao_existe() -> None:
    """PAREAMENTO x Z6 — e a régua DIZ que os arquivos não estão no disco."""
    for arquivo in _OS_QUATRO:
        assert not (RAIZ / arquivo).exists(), (
            f"{arquivo} passou a existir; escolha outro caminho inexistente para "
            "o dublê, ou a mordida deixa de provar o que promete"
        )
    queixas = _confere(
        pareamento=_sprint("PAREAMENTO-01", cria=_OS_QUATRO),
        z6=_sprint("ONDA0-Z6", cria=_OS_QUATRO),
    )
    assert len(queixas) == 1, queixas
    assert "PAREAMENTO-01 x ONDA0-Z6" in queixas[0]
    assert "NÃO EXISTEM no disco" in queixas[0], (
        "acusou o par mas não disse que nenhum grep o acharia — que é a razão "
        "de o campo `cria:` existir:\n" + queixas[0]
    )


def test_sem_o_campo_cria_a_duplicata_some() -> None:
    """A MORDIDA que prova qual é o campo caro: sem `cria:`, o par é invisível."""
    queixas = _confere(
        pareamento=_sprint("PAREAMENTO-01", cria=_OS_QUATRO),
        z6=_sprint("ONDA0-Z6", cria=_OS_QUATRO),
    )
    assert queixas, "com `cria:` o par tem de aparecer"

    sem_cria = _confere(
        pareamento=_sprint("PAREAMENTO-01"),
        z6=_sprint("ONDA0-Z6"),
    )
    assert sem_cria == [], (
        "sem o campo `cria:` o par continuou aparecendo — então não foi ele que "
        "o pegou, e a régua não prova o que diz provar"
    )


# ---------------------------------------------------------------------------
# O que NÃO é colisão, e é aqui que uma régua ingênua vira ruído
# ---------------------------------------------------------------------------


def test_colisao_serializada_por_depois_de_nao_e_acusada() -> None:
    queixas = _confere(
        z2=_sprint("ONDA0-Z2", posse={"A": ["src/app/x.py"]}),
        z5=_sprint("ONDA0-Z5", posse={"B": ["src/app/x.py"]}, depois_de=["ONDA0-Z2"]),
    )
    assert queixas == [], queixas


def test_quem_declara_nao_toca_deixa_de_reivindicar() -> None:
    queixas = _confere(
        z7=_sprint(
            "ONDA0-Z7",
            posse={"A": ["src/app/state_store.py", "src/app/daemon_actions.py"]},
            nao_toca=["src/app/daemon_actions.py"],
        ),
        z9=_sprint("ONDA0-Z9", posse={"B": ["src/app/daemon_actions.py"]}),
    )
    assert queixas == [], queixas


def test_a_pasta_declarada_cobre_o_que_esta_dentro() -> None:
    queixas = _confere(
        infra=_sprint("INFRA-01", posse={"A": ["scripts/portoes.sh"]},
                      nao_toca=["src/hefesto_dualsense4unix/"]),
        aba=_sprint("ABA-01", posse={"B": ["src/hefesto_dualsense4unix/app/x.py"]}),
    )
    assert queixas == [], queixas


def test_citar_no_corpo_nao_e_reivindicar() -> None:
    """Frequência de citação NÃO é posse — o limite da régua, declarado."""
    corpo = _sprint("SO-CITA-01", posse={"A": ["docs/x.md"]})
    corpo += "\n\nEste texto cita src/app/daemon_actions.py trinta vezes.\n" * 5
    queixas = _confere(
        cita=corpo,
        dona=_sprint("DONA-01", posse={"B": ["src/app/daemon_actions.py"]}),
    )
    assert queixas == [], queixas


def test_a_sprint_que_se_contradiz_e_acusada() -> None:
    queixas = _confere(
        confusa=_sprint("CONFUSA-01", posse={"A": ["src/app/x.py"]}, nao_toca=["src/app/x.py"]),
        outra=_sprint("OUTRA-01", posse={"B": ["docs/y.md"]}),
    )
    assert queixas == [], "nao_toca vence: o arquivo sai da reivindicação, sem contradição"


# ---------------------------------------------------------------------------
# O analisador recusa o que não entende — nunca adivinha
# ---------------------------------------------------------------------------


def test_sprint_sem_frontmatter_nao_e_erro_e_vira_divida() -> None:
    assert colisao.le_frontmatter("# uma sprint qualquer\n", "x.md") is None


def test_campo_desconhecido_e_recusado_dizendo_a_linha() -> None:
    texto = "---\nsprint: X\npossse:\n  A:\n---\n"
    with pytest.raises(colisao.FormatoInvalido) as exc:
        colisao.le_frontmatter(texto, "x.md")
    assert "possse" in str(exc.value) and "x.md:3" in str(exc.value)


def test_frontmatter_que_nunca_fecha_e_recusado() -> None:
    with pytest.raises(colisao.FormatoInvalido):
        colisao.le_frontmatter("---\nsprint: X\n", "x.md")


# ---------------------------------------------------------------------------
# `estado:` — só o que está aberta disputa posse e se despacha (06/09/2026)
# ---------------------------------------------------------------------------


def _com_estado(texto: str, estado: str) -> str:
    return texto.replace("sprint: ", f"estado: {estado}\nsprint: ", 1)


def test_estado_desconhecido_e_recusado() -> None:
    with pytest.raises(colisao.FormatoInvalido) as exc:
        colisao.le_frontmatter(_com_estado(_sprint("X"), "pronta"), "x.md")
    assert "pronta" in str(exc.value) and "aberta" in str(exc.value)


def test_sem_estado_e_aberta_por_padrao() -> None:
    dados = colisao.le_frontmatter(_sprint("X"), "x.md")
    assert dados is not None and dados["estado"] == "aberta" and colisao.aberta(dados)


def test_sprint_feita_nao_disputa_posse() -> None:
    """Duas sprints no mesmo arquivo: com as duas abertas o portão grita; com
    uma delas `feita`, cala — trabalho que já aconteceu não colide."""
    abertas = _confere(
        a=_sprint("A-01", posse={"A": ["src/x.py"]}),
        b=_sprint("B-01", posse={"B": ["src/x.py"]}),
    )
    assert abertas, "a mordida: com as duas abertas tem de gritar"
    uma_feita = _confere(
        a=_com_estado(_sprint("A-01", posse={"A": ["src/x.py"]}), "feita"),
        b=_sprint("B-01", posse={"B": ["src/x.py"]}),
    )
    assert uma_feita == []


def test_exigir_recusa_sprint_que_nao_esta_aberta(tmp_path) -> None:
    (tmp_path / "2026-09-06-FEITA-01.md").write_text(
        _com_estado(_sprint("FEITA-01", posse={"A": ["src/x.py"]}), "feita"),
        encoding="utf-8",
    )
    (tmp_path / "2026-09-06-VIVA-01.md").write_text(
        _sprint("VIVA-01", posse={"A": ["src/y.py"]}), encoding="utf-8"
    )
    base = [sys.executable, str(SCRIPT), "--pasta", str(tmp_path)]
    r = subprocess.run([*base, "--exigir", "FEITA-01"], capture_output=True, text=True)
    assert r.returncode == 1 and "estado: feita" in r.stderr
    r = subprocess.run([*base, "--exigir", "VIVA-01"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run([*base, "--abertas"], capture_output=True, text=True)
    assert "VIVA-01" in r.stdout and "FEITA-01" not in r.stdout


# ---------------------------------------------------------------------------
# Contra a árvore de verdade
# ---------------------------------------------------------------------------


def test_nasce_reprovando_zero_na_arvore_de_verdade() -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPT)], cwd=RAIZ, capture_output=True, text=True
    )
    assert r.returncode == 0, (
        "o portão nasceu reprovando, e ele foi desenhado para nascer verde — "
        "sprint sem frontmatter é DÍVIDA, não reprovação:\n" + r.stdout + r.stderr
    )
    assert "DÍVIDA" in r.stdout, "a lista de dívida sumiu da saída:\n" + r.stdout


def test_exigir_recusa_sprint_sem_frontmatter_e_aceita_a_que_tem(tmp_path) -> None:
    """É o que o despachante chama para não deixar agente nascer sem posse.

    Numa pasta própria: a árvore de verdade muda de estado (a sprint que este
    teste citava, INFRA-DE-EXECUCAO-01, virou `estado: feita` em 06/09/2026, e
    feita não se despacha).
    """
    (tmp_path / "2026-09-06-COM-POSSE-01.md").write_text(
        _sprint("COM-POSSE-01", posse={"A": ["src/x.py"]}), encoding="utf-8"
    )
    (tmp_path / "2026-09-06-SEM-FRONTMATTER-01.md").write_text(
        "# uma sprint sem posse\n", encoding="utf-8"
    )
    base = [sys.executable, str(SCRIPT), "--pasta", str(tmp_path)]
    r = subprocess.run([*base, "--exigir", "COM-POSSE-01"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

    r = subprocess.run(
        [*base, "--exigir", "SEM-FRONTMATTER-01"], capture_output=True, text=True
    )
    assert r.returncode == 1 and "SEM-FRONTMATTER-01" in r.stderr

    r = subprocess.run(
        [sys.executable, str(SCRIPT), "--exigir", "SPRINT-QUE-NAO-EXISTE"],
        cwd=RAIZ, capture_output=True, text=True,
    )
    assert r.returncode == 1
    assert "SPRINT-QUE-NAO-EXISTE" in r.stderr


def test_o_comentario_inline_nao_gruda_no_caminho() -> None:
    """Um `# dona: A` no fim da linha cegava o portão INTEIRO.

    MEDIDO em 25/08/2026. A linha de comentário SOZINHA já era pulada; a
    anotação no fim de um caminho, não — o caminho entrava no conjunto com o
    comentário grudado, e por isso **nunca casava com o mesmo arquivo declarado
    por outra sprint**.

    O estrago não era hipotético: a `CONFIGURACOES-O-LEXICO-01` anota assim
    exatamente os quatro caminhos que ela CEDE — que são, por definição, os
    disputados. O portão devolvia *"nenhuma colisão não declarada"* enquanto
    duas sprints reivindicavam `secao_mesa.py`, e quem coordenava usou esse
    verde para autorizar uma leva.

    É o defeito que esta casa chama de *o instrumento mente mais que o
    produto*: a régua desliga sozinha exatamente quando alguém documenta bem.
    """
    dados = colisao.le_frontmatter(
        _sprint(
            "COM-COMENTARIO",
            posse={"A1": ["src/alvo.py       # dona: outra frente", "src/limpo.py"]},
        ),
        "COM-COMENTARIO",
    )
    assert dados is not None
    assert dados["posse"]["A1"] == ["src/alvo.py", "src/limpo.py"], (
        "o comentário inline entrou no caminho. Enquanto ele estiver ali, este "
        f"caminho não casa com nenhum outro e a colisão fica invisível: "
        f"{dados['posse']['A1']!r}"
    )


def test_a_colisao_com_comentario_inline_e_acusada() -> None:
    """A prova de ponta a ponta: duas sprints, uma anotando o caminho."""
    achados = _confere(
        UMA=_sprint("UMA", posse={"A1": ["src/disputado.py"]}),
        OUTRA=_sprint(
            "OUTRA", posse={"B1": ["src/disputado.py   # cedo, mas edito"]}
        ),
    )
    assert any("src/disputado.py" in a for a in achados), (
        "as duas reivindicam o mesmo arquivo e uma o anotou — a colisão tem de "
        f"ser acusada mesmo assim. Achados: {achados!r}"
    )


def test_o_hash_colado_no_caminho_sobrevive() -> None:
    """A cura não pode ter começado a cortar caminho legítimo.

    Nome de arquivo com `#` colado é esquisito e legal. Exigir o espaço antes
    do `#` é o que separa "anotação" de "parte do nome" — sem esta guarda, o
    conserto trocaria um erro de leitura por outro, mais silencioso.
    """
    dados = colisao.le_frontmatter(
        _sprint("HASH", posse={"A1": ["src/rel#1.py"]}), "HASH"
    )
    assert dados is not None
    assert dados["posse"]["A1"] == ["src/rel#1.py"]
