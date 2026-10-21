"""As citações de commit seguem o mapa — `scripts/remapear-citacoes-de-commit.py`.

Os mapas e os commits são de mentira (SHAs gerados na hora, repositórios em `tmp_path`): nada aqui
lê os mapas da casa nem o repositório de verdade.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "remapear-citacoes-de-commit.py"
ZERO = "0" * 40


def _carregar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("remapear_citacoes_de_commit", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


R = _carregar()


def sha(n: int) -> str:
    """Um SHA de mentira com letras e números, sempre o mesmo para o mesmo `n`."""
    alvo = hashlib.sha1(f"commit-{n}".encode()).hexdigest()
    assert any(c.isalpha() for c in alvo[:7]) and any(c.isdigit() for c in alvo[:7])
    return alvo


def _gravar_mapa(caminho: Path, pares: dict[str, str]) -> Path:
    caminho.write_text("old new\n" + "".join(f"{k} {v}\n" for k, v in pares.items()))
    return caminho


A, B, C, D = sha(1), sha(2), sha(3), sha(4)


# --- o texto ----------


def test_um_salto_troca_o_curto_e_o_inteiro_mantendo_o_comprimento() -> None:
    cadeia = R.Cadeia([{A: B}])
    res = R.remapear_texto(f"desde `{A[:7]}` e {A[:9]} e {A}.\n", cadeia)
    assert res.texto == f"desde `{B[:7]}` e {B[:9]} e {B}.\n"
    assert [(t.velho, t.novo) for t in res.trocas] == [
        (A[:7], B[:7]),
        (A[:9], B[:9]),
        (A, B),
    ]


def test_a_cadeia_segue_agosto_depois_quinze_de_setembro_depois_o_seguinte() -> None:
    cadeia = R.Cadeia([{A: B}, {B: C}, {C: D}])
    assert R.remapear_texto(f"{A[:9]}", cadeia).texto == D[:9]


def test_quem_ja_esta_no_meio_da_cadeia_chega_ao_fim() -> None:
    """A segunda passada: o SHA que a primeira deixou vira chave do mapa novo."""
    cadeia = R.Cadeia([{A: B}, {B: C}, {C: D}])
    assert R.remapear_texto(f"{B[:9]} e {C[:9]}", cadeia).texto == f"{D[:9]} e {D[:9]}"


def test_a_segunda_passada_e_idempotente() -> None:
    primeira = R.remapear_texto(f"{A[:9]}", R.Cadeia([{A: B}, {B: C}]))
    de_novo = R.remapear_texto(primeira.texto, R.Cadeia([{A: B}, {B: C}]))
    assert de_novo.texto == primeira.texto and not de_novo.trocas


def test_o_numero_da_linha_vem_junto_da_troca() -> None:
    res = R.remapear_texto(f"um\ndois\ntrês {A[:8]}\n", R.Cadeia([{A: B}]))
    assert [t.linha for t in res.trocas] == [3]


def test_prefixo_de_dois_shas_e_ambiguo_e_fica() -> None:
    a1 = "abcdef1" + "0" * 33
    a2 = "abcdef1" + "1" * 33
    cadeia = R.Cadeia([{a1: B, a2: C}])
    res = R.remapear_texto(f"{a1[:7]} e {a1[:9]}", cadeia)
    assert res.texto == f"{a1[:7]} e {B[:9]}"


def test_prefixo_de_commit_vivo_do_repositorio_tambem_e_ambiguo() -> None:
    vivo = A[:8] + "f" * 32
    cadeia = R.Cadeia([{A: B}], [vivo, B])
    assert R.remapear_texto(f"{A[:8]}", cadeia).texto == A[:8]
    assert R.remapear_texto(f"{A[:10]}", cadeia).texto == B[:10]


def test_hash_de_terceiros_nao_resolve_e_nao_se_toca() -> None:
    kernel = "c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0"
    assert (
        R.remapear_texto(f"o kernel `{kernel}`", R.Cadeia([{A: B}])).texto == f"o kernel `{kernel}`"
    )


def test_so_letras_ou_so_numeros_fica_e_vai_para_a_lista_a_conferir() -> None:
    """Pode ser número ou palavra: não se troca sozinho, mas também não some calado da lista."""
    letras = "abcdefa" + "1" * 33
    numeros = "1234567" + "a" * 33
    cadeia = R.Cadeia([{letras: B, numeros: C}])
    res = R.remapear_texto(f"{letras[:7]} {numeros[:7]}", cadeia)
    assert res.texto == f"{letras[:7]} {numeros[:7]}" and not res.trocas
    assert [(t.velho, t.novo) for t in res.a_conferir] == [
        (letras[:7], B[:7]),
        (numeros[:7], C[:7]),
    ]
    conferido = R.remapear_texto(f"{numeros[:7]}", cadeia, com_os_a_conferir=True)
    assert conferido.texto == C[:7] and not conferido.a_conferir


def test_o_curto_novo_que_nasce_ambiguo_fica() -> None:
    outra = "e" if B[7] != "e" else "d"
    vizinho = B[:7] + outra * 33
    cadeia = R.Cadeia([{A: B}], [B, vizinho])
    res = R.remapear_texto(f"{A[:7]} e {A[:10]}", cadeia)
    assert res.texto == f"{A[:7]} e {B[:10]}"
    assert [(t.velho, t.novo) for t in res.a_conferir] == [(A[:7], B[:7])]


def test_sequencia_mais_longa_que_um_sha_nao_e_cortada() -> None:
    comprida = A + "0" * 24  # 64 dígitos, como um sha256
    assert R.remapear_texto(comprida, R.Cadeia([{A: B}])).texto == comprida


def test_commit_podado_fica_e_entra_na_conta() -> None:
    res = R.remapear_texto(f"o {A[:9]}", R.Cadeia([{A: ZERO}]))
    assert (
        res.texto == f"o {A[:9]}" and not res.trocas and [t.velho for t in res.podados] == [A[:9]]
    )


def test_podado_num_elo_do_meio_nao_chega_ao_ultimo() -> None:
    res = R.remapear_texto(f"{A[:9]}", R.Cadeia([{A: B}, {B: ZERO}, {B: C}]))
    assert res.texto == A[:9] and len(res.podados) == 1


def test_o_minimo_de_digitos_vale() -> None:
    cadeia = R.Cadeia([{A: B}])
    assert R.remapear_texto(f"{A[:7]}", cadeia, minimo=9).texto == A[:7]
    assert R.remapear_texto(f"{A[:6]}", cadeia).texto == A[:6]


def test_o_ultimo_elo_tem_de_existir_no_repositorio() -> None:
    """A premissa de 21/10 caiu aqui: o mapa de 15/09 devolve SHAs que o `dev` não tem."""
    sem_o_novo = R.Cadeia([{A: B}], [C])
    res = R.remapear_texto(f"{A[:9]}", sem_o_novo)
    assert res.texto == A[:9] and [t.velho for t in res.ausentes] == [A[:9]]
    com_o_novo = R.Cadeia([{A: B}], [C, B])
    assert R.remapear_texto(f"{A[:9]}", com_o_novo).texto == B[:9]


def test_repositorio_que_respondeu_vazio_nao_desliga_a_guarda() -> None:
    """Vazio é «nada existe», não «sem repositório»: o novo que ninguém tem não entra."""
    res = R.remapear_texto(f"{A[:9]}", R.Cadeia([{A: B}], []))
    assert res.texto == A[:9] and [t.velho for t in res.ausentes] == [A[:9]]


def test_git_que_falha_ao_listar_os_commits_e_erro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Engolir a falha devolveria lista vazia, e a guarda de existência sumiria calada."""
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "nao-e-repositorio"))
    with pytest.raises(subprocess.CalledProcessError):
        R._commits_do_repositorio(tmp_path)


# --- os mapas ----------


def test_ler_mapa_aceita_o_cabecalho_e_recusa_o_que_nao_e_sha(tmp_path: Path) -> None:
    assert R.ler_mapa(_gravar_mapa(tmp_path / "ok.txt", {A: B})) == {A: B}
    ruim = tmp_path / "ruim.txt"
    ruim.write_text(f"{A} curto\n")
    with pytest.raises(R.MapaInvalido):
        R.ler_mapa(ruim)


def test_mapa_pedido_que_nao_existe_e_erro(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        R.escolher_mapas([str(tmp_path / "nao-existe.txt")])


def test_so_os_ultimos_mapas_da_casa_podem_faltar(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    m1 = _gravar_mapa(tmp_path / "m1.txt", {A: B})
    m2 = _gravar_mapa(tmp_path / "m2.txt", {B: C})
    ainda_nao = tmp_path / "m3-ainda-nao-existe.txt"
    monkeypatch.setattr(R, "MAPAS_DA_CASA", (m1, m2, ainda_nao))
    assert R.escolher_mapas([]) == ([m1, m2], [ainda_nao])
    m3 = _gravar_mapa(tmp_path / "m3-ja-existe.txt", {C: D})
    monkeypatch.setattr(R, "MAPAS_DA_CASA", (m1, tmp_path / "falta.txt", m3))
    with pytest.raises(FileNotFoundError):
        R.escolher_mapas([])


# --- o repositório ----------


def _git(raiz: Path, *args: str, data: str | None = None) -> str:
    ambiente = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_AUTHOR_NAME": "régua",
        "GIT_AUTHOR_EMAIL": "regua@exemplo.invalid",
        "GIT_COMMITTER_NAME": "régua",
        "GIT_COMMITTER_EMAIL": "regua@exemplo.invalid",
    }
    if data:
        ambiente["GIT_AUTHOR_DATE"] = data
        ambiente["GIT_COMMITTER_DATE"] = data
    feito = subprocess.run(
        [
            "git",
            "-C",
            str(raiz),
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        capture_output=True,
        text=True,
        env=ambiente,
        check=True,
    )
    return feito.stdout.strip()


def _repositorio(raiz: Path) -> Path:
    raiz.mkdir()
    _git(raiz, "init", "-q", "-b", "dev")
    return raiz


def _commit(raiz: Path, conteudo: str, assunto: str, data: str, arquivo: str = "x.txt") -> str:
    (raiz / arquivo).write_text(conteudo)
    _git(raiz, "add", arquivo)
    _git(raiz, "commit", "-q", "-m", assunto, data=data)
    return _git(raiz, "rev-parse", "HEAD")


def test_a_ponte_liga_pela_data_e_pelo_assunto_e_so_quando_o_par_e_unico(tmp_path: Path) -> None:
    # D-2110-AS-CITACOES-SEGUEM-A-PONTE-ATE-O-DEV
    origem = _repositorio(tmp_path / "origem")
    destino = _repositorio(tmp_path / "destino")
    o1 = _commit(origem, "um\n", "feat: um", "2026-08-01T10:00:00-03:00")
    o2 = _commit(origem, "dois\n", "feat: dois", "2026-08-02T10:00:00-03:00")
    o3 = _commit(origem, "três\n", "feat: três", "2026-08-03T10:00:00-03:00")
    o4 = _commit(origem, "quatro\n", "feat: quatro", "2026-08-04T10:00:00-03:00")
    d1 = _commit(destino, "UM\n", "feat: um", "2026-08-01T10:00:00-03:00")
    _commit(destino, "DOIS-a\n", "feat: dois", "2026-08-02T10:00:00-03:00")
    _commit(destino, "DOIS-b\n", "feat: dois", "2026-08-02T10:00:00-03:00", arquivo="y.txt")
    d3 = _commit(destino, "TRÊS\n", "feat: três", "2026-08-03T10:00:00-03:00")
    assert d1 != o1
    mapa = {sha(90): o1, sha(91): o2, sha(92): o3, sha(93): o4, sha(94): ZERO}
    ponte, sem_par = R.gerar_ponte(mapa, origem, destino, "dev")
    assert ponte == {o1: d1, o3: d3}
    assert sem_par == 2  # o2 (dois no destino) e o4 (nenhum)


def test_a_ponte_aceita_copias_do_mesmo_commit_na_origem(tmp_path: Path) -> None:
    origem = _repositorio(tmp_path / "origem")
    destino = _repositorio(tmp_path / "destino")
    o1 = _commit(origem, "um\n", "feat: um", "2026-08-01T10:00:00-03:00")
    _git(origem, "checkout", "-q", "--orphan", "outro")
    o1b = _commit(origem, "um-bis\n", "feat: um", "2026-08-01T10:00:00-03:00")
    d1 = _commit(destino, "UM\n", "feat: um", "2026-08-01T10:00:00-03:00")
    ponte, _ = R.gerar_ponte({sha(90): o1, sha(91): o1b}, origem, destino, "dev")
    assert ponte == {o1: d1, o1b: d1}


def test_de_ponta_a_ponta_a_citacao_morta_chega_ao_commit_vivo(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    origem = _repositorio(tmp_path / "origem")
    repo = _repositorio(tmp_path / "repo")
    novo_de_setembro = _commit(origem, "um\n", "feat: um", "2026-08-01T10:00:00-03:00")
    vivo = _commit(repo, "UM\n", "feat: um", "2026-08-01T10:00:00-03:00")
    velho = sha(7)
    agosto = _gravar_mapa(tmp_path / "agosto.txt", {velho: sha(8)})
    setembro = _gravar_mapa(tmp_path / "setembro.txt", {sha(8): novo_de_setembro})
    ponte = tmp_path / "ponte.txt"
    assert (
        R.main(["--raiz", str(repo), "--gerar-ponte", str(setembro), str(origem), str(ponte)]) == 0
    )
    (repo / "doc.md").write_text(f"o commit `{velho[:9]}` e `{velho[:7]}`.\n")
    (repo / "fora.md").write_text(f"{velho[:9]}\n")  # sem `git add`: não é versionado
    _git(repo, "add", "doc.md")
    base = ["--raiz", str(repo), "--mapa", str(agosto), "--mapa", str(setembro)]

    # sem a ponte a cadeia termina num SHA que o repositório não tem: nada se troca
    assert R.main([*base, "doc.md"]) == 0
    assert "sem o commit novo no repositório (ficam): 2" in capsys.readouterr().out
    assert velho[:9] in (repo / "doc.md").read_text()

    com_ponte = [*base, "--mapa", str(ponte)]
    assert R.main([*com_ponte, "doc.md"]) == 0  # sem --escrever só mostra
    assert (repo / "doc.md").read_text() == f"o commit `{velho[:9]}` e `{velho[:7]}`.\n"
    capsys.readouterr()

    assert R.main([*com_ponte, "--escrever", "doc.md"]) == 0
    assert (repo / "doc.md").read_text() == f"o commit `{vivo[:9]}` e `{vivo[:7]}`.\n"
    assert (repo / "fora.md").read_text() == f"{velho[:9]}\n"
    capsys.readouterr()

    assert R.main([*com_ponte, "--escrever", "doc.md"]) == 0
    assert "total: 0 trocas" in capsys.readouterr().out


def test_mapa_pedido_que_falta_encerra_com_erro(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _repositorio(tmp_path / "repo")
    assert R.main(["--raiz", str(repo), "--mapa", str(tmp_path / "falta.txt"), "x.md"]) == 2
    assert "mapa que não existe" in capsys.readouterr().err


def test_caminho_que_nao_casa_arquivo_versionado_encerra_com_erro(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Varrer zero arquivo e dizer «0 trocas» seria verde sobre nada (`$PASTAS` no zsh)."""
    repo = _repositorio(tmp_path / "repo")
    _commit(repo, "x\n", "feat: x", "2026-08-01T10:00:00-03:00")
    mapa = _gravar_mapa(tmp_path / "m.txt", {sha(1): sha(2)})
    base = ["--raiz", str(repo), "--mapa", str(mapa)]
    assert R.main([*base, "docs/method scripts"]) == 2
    assert "nenhum arquivo versionado casa" in capsys.readouterr().err
