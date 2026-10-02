"""As fotos da documentação defasaram em silêncio — FOTOS-DA-VERSAO-01."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

FOTOS = "docs/usage/assets"

SUBPASTA_DA_VISTA = "maximizada"
FOTOS_DA_VISTA = f"{FOTOS}/{SUBPASTA_DA_VISTA}"

FAMILIAS_DE_FOTO = (FOTOS, FOTOS_DA_VISTA)

CODIGO_DA_TELA = (
    "src/hefesto_dualsense4unix/interface",
    "src/hefesto_dualsense4unix/app",
    "src/hefesto_dualsense4unix/gui",
)

CONFERIDO = f"{FOTOS}/CONFERIDO-EM.txt"

RETRATISTA = "src/hefesto_dualsense4unix/interface/olhar.py"
COMANDOS_DE_CURA = (
    f"    {RETRATISTA} --todas --publicado --doc                 # {FOTOS}\n"
    f"    {RETRATISTA} --todas --publicado --doc --vista dela    # {FOTOS_DA_VISTA}"
)


def _git(raiz: Path, *args: str) -> str:
    saida = subprocess.run(
        ["git", *args],
        cwd=str(raiz),
        capture_output=True,
        text=True,
    )
    if saida.returncode != 0:
        return ""
    return saida.stdout.strip()


def _ultimo_commit(raiz: Path, *caminhos: str) -> str:
    return _git(raiz, "log", "-1", "--format=%H", "--", *caminhos)


def familias_sob(fotos: str) -> tuple[str, ...]:
    """As famílias de foto que moram em `fotos`, ela inclusive."""
    return tuple(
        f for f in FAMILIAS_DE_FOTO if f == fotos or f.startswith(fotos + "/")
    )


def _pathspec(familia: str) -> list[str]:
    """Os caminhos que são DESTA família e de nenhuma outra."""
    return [familia] + [
        f":(exclude){outra}"
        for outra in FAMILIAS_DE_FOTO
        if outra != familia and outra.startswith(familia + "/")
    ]


def uma_familia_em_dia(
    raiz: Path, familia: str, codigo: tuple[str, ...]
) -> bool | None:
    """A pergunta da topologia, para UMA família de foto."""
    commit_das_fotos = _ultimo_commit(raiz, *_pathspec(familia))
    commit_do_codigo = _ultimo_commit(raiz, *codigo)
    if not commit_das_fotos or not commit_do_codigo:
        return None
    if commit_das_fotos == commit_do_codigo:
        return True
    pergunta = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit_do_codigo, commit_das_fotos],
        cwd=str(raiz),
        capture_output=True,
    )
    return pergunta.returncode == 0


def fotos_em_dia(raiz: Path, fotos: str, codigo: tuple[str, ...]) -> bool | None:
    """TODAS as famílias sob `fotos` foram refeitas depois da mexida na tela?"""
    vereditos = [uma_familia_em_dia(raiz, f, codigo) for f in familias_sob(fotos)]
    if any(v is False for v in vereditos):
        return False
    if all(v is None for v in vereditos):
        return None
    return True


def familias_atrasadas(
    raiz: Path, fotos: str, codigo: tuple[str, ...]
) -> list[str]:
    """Quais famílias estão devendo foto — o que a mensagem precisa nomear."""
    return [
        f
        for f in familias_sob(fotos)
        if uma_familia_em_dia(raiz, f, codigo) is False
    ]


def fotos_sendo_refeitas_agora(raiz: Path, fotos: str) -> bool:
    """As fotos estão MODIFICADAS na árvore de trabalho ou no índice?"""
    return bool(_git(raiz, "status", "--porcelain", "--", *_pathspec(fotos)))


def familias_sujas(raiz: Path, fotos: str) -> set[str]:
    """As famílias que estão sendo refeitas AGORA — o perdão, uma pasta por vez."""
    return {f for f in familias_sob(fotos) if fotos_sendo_refeitas_agora(raiz, f)}


def conferencia_declarada(raiz: Path, conferido: str) -> set[str]:
    """Os commits de tela que alguém declarou ter conferido, lidos do arquivo."""
    try:
        texto = (raiz / conferido).read_text(encoding="utf-8")
    except OSError:
        return set()

    achados: set[str] = set()
    for linha in texto.splitlines():
        campos = linha.split("#", 1)[0].split()
        if not campos:
            continue
        primeiro = campos[0].lower()
        if len(primeiro) == 40 and all(c in "0123456789abcdef" for c in primeiro):
            achados.add(primeiro)
    return achados


def portao_fechado(
    raiz: Path, fotos: str, codigo: tuple[str, ...], conferido: str
) -> bool | None:
    """As DUAS portas, na ordem: a topologia primeiro, a declaração depois."""
    veredito = fotos_em_dia(raiz, fotos, codigo)
    if veredito is not False:
        return veredito

    commit_do_codigo = _ultimo_commit(raiz, *codigo)
    return bool(commit_do_codigo) and commit_do_codigo in conferencia_declarada(
        raiz, conferido
    )


def _sem_historico(raiz: Path) -> bool:
    """Clone raso ou pasta sem git: aqui não há o que medir, e não há defeito."""
    if not (raiz / ".git").exists():
        return True
    if (raiz / ".git" / "shallow").exists():
        return True
    return not _git(raiz, "rev-parse", "HEAD")


def test_as_fotos_nao_ficam_atras_do_codigo_da_tela() -> None:
    """As imagens do README acompanham a versão: foto conferida depois do código da tela."""
    if _sem_historico(RAIZ):
        pytest.skip("sem histórico git completo (clone raso ou pasta sem git)")

    sujas = familias_sujas(RAIZ, FOTOS)
    a_medir = [f for f in familias_sob(FOTOS) if f not in sujas]
    if not a_medir:
        return

    vereditos = [portao_fechado(RAIZ, f, CODIGO_DA_TELA, CONFERIDO) for f in a_medir]
    if all(v is None for v in vereditos):
        pytest.skip("as fotos ou o código da tela ainda não têm commit próprio")
    veredito = not any(v is False for v in vereditos)

    atrasadas = [f for f, v in zip(a_medir, vereditos, strict=True) if v is False]
    commit_das_fotos = (
        _ultimo_commit(RAIZ, *_pathspec(atrasadas[0]))[:7] if atrasadas else ""
    )
    commit_do_codigo = _ultimo_commit(RAIZ, *CODIGO_DA_TELA)

    assert veredito, (
        f"a interface mudou em {commit_do_codigo[:7]} e as fotos de "
        f"`{'`, `'.join(atrasadas)}` "
        f"são de {commit_das_fotos}, que veio ANTES. As imagens do `README.md` "
        "e do `docs/usage/AS-DEZ-ABAS-o-que-cada-uma-faz.md` documentam uma "
        "tela que pode não existir mais.\n\n"
        f"{COMANDOS_DE_CURA}\n\n"
        "Uma execução, nenhum clique. Se as imagens saírem DIFERENTES, olhe-as "
        "antes de commitar: mudança de DESENHO é palavra dela "
        "(PROVA-DE-TELA-01), não de quem tirou a foto.\n\n"
        "Se saírem IGUAIS não há o que commitar, e aí é a segunda porta — "
        f"acrescente a `{CONFERIDO}` a linha\n\n"
        f"    {commit_do_codigo}  <data>  <o que você mediu>\n\n"
        "NÃO refotografe só para gerar bytes: a foto carrega o estado VIVO da "
        "máquina de quem a tira (quantos controles na mesa, a cor lida de cada "
        "um), e commitar a sua troca a mesa dela pela sua, calada."
    )


def _repo_de_mentira(tmp_path: Path, fotos_por_ultimo: bool) -> Path:
    """Um repositório com dois commits, na ordem pedida."""
    raiz = tmp_path / ("em_dia" if fotos_por_ultimo else "atrasado")
    (raiz / FOTOS).mkdir(parents=True)
    (raiz / CODIGO_DA_TELA[0]).mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=str(raiz), check=True)
    subprocess.run(
        ["git", "config", "user.email", "portao@exemplo.invalido"],
        cwd=str(raiz),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Portão"], cwd=str(raiz), check=True
    )
    sem_hooks = tmp_path / "sem_hooks"
    sem_hooks.mkdir(exist_ok=True)
    subprocess.run(
        ["git", "config", "core.hooksPath", str(sem_hooks)],
        cwd=str(raiz),
        check=True,
    )

    def _commitar(caminho: str, conteudo: str, mensagem: str) -> None:
        (raiz / caminho).write_text(conteudo, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", mensagem], cwd=str(raiz), check=True
        )

    primeiro = (
        (f"{CODIGO_DA_TELA[0]}/home_actions.py", "a aba mudou")
        if fotos_por_ultimo
        else (f"{FOTOS}/aba-01-jogar.png", "a foto")
    )
    segundo = (
        (f"{FOTOS}/aba-01-jogar.png", "a foto nova")
        if fotos_por_ultimo
        else (f"{CODIGO_DA_TELA[0]}/home_actions.py", "a aba mudou depois")
    )
    _commitar(primeiro[0], primeiro[1], "primeiro")
    _commitar(segundo[0], segundo[1], "segundo")
    return raiz


def test_o_portao_acusa_foto_atrasada(tmp_path: Path) -> None:
    """A MORDIDA: com a tela mexida depois da foto, o comparador tem de reprovar."""
    raiz = _repo_de_mentira(tmp_path, fotos_por_ultimo=False)

    assert fotos_em_dia(raiz, FOTOS, CODIGO_DA_TELA) is False, (
        "o comparador aceitou um repositório em que a interface mudou DEPOIS "
        "da última foto. É a situação exata de 13/08/2026, com três commits de "
        "`app/`/`gui/` entre a foto e a tag — e é o que este arquivo existe "
        "para não deixar acontecer de novo."
    )


def test_o_portao_acusa_retrato_mexido_depois_da_foto(tmp_path: Path) -> None:
    """A MORDIDA do Z0-1 (§2.2/M1): o INSTRUMENTO conta como código da tela."""
    raiz = tmp_path / "so_retrato_mexido"
    (raiz / FOTOS).mkdir(parents=True)
    (raiz / "src" / "hefesto_dualsense4unix" / "interface").mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=str(raiz), check=True)
    subprocess.run(
        ["git", "config", "user.email", "portao@exemplo.invalido"],
        cwd=str(raiz),
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Portão"], cwd=str(raiz), check=True)
    sem_hooks = tmp_path / "sem_hooks_retrato"
    sem_hooks.mkdir(exist_ok=True)
    subprocess.run(
        ["git", "config", "core.hooksPath", str(sem_hooks)],
        cwd=str(raiz),
        check=True,
    )

    def _commitar(caminho: str, conteudo: str, mensagem: str) -> None:
        (raiz / caminho).write_text(conteudo, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", mensagem], cwd=str(raiz), check=True
        )

    _commitar(f"{FOTOS}/aba-01-jogar.png", "a foto", "primeiro")
    _commitar(
        "src/hefesto_dualsense4unix/interface/olhar.py",
        "o retratista das dez, mexido",
        "segundo — só o instrumento",
    )

    assert fotos_em_dia(raiz, FOTOS, CODIGO_DA_TELA) is False, (
        "o comparador não acusou uma mudança em `interface/olhar.py` "
        "posterior à foto. É o buraco exato do F14: o instrumento que decide "
        "o que a foto mostra mudou +645 linhas no commit `3de95ff` e nada "
        "acusou, porque `CODIGO_DA_TELA` não o citava."
    )


def test_a_foto_da_vista_nao_paga_a_divida_das_dez_do_readme(tmp_path: Path) -> None:
    """A MORDIDA DA PASTA NOVA: cada família de foto responde por si."""
    raiz = tmp_path / "so_a_vista_refeita"
    (raiz / FOTOS_DA_VISTA).mkdir(parents=True)
    (raiz / CODIGO_DA_TELA[0]).mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=str(raiz), check=True)
    for chave, valor in (
        ("user.email", "portao@exemplo.invalido"),
        ("user.name", "Portão"),
    ):
        subprocess.run(["git", "config", chave, valor], cwd=str(raiz), check=True)
    sem_hooks = tmp_path / "sem_hooks_vista"
    sem_hooks.mkdir(exist_ok=True)
    subprocess.run(
        ["git", "config", "core.hooksPath", str(sem_hooks)], cwd=str(raiz), check=True
    )

    def _commitar(caminho: str, conteudo: str, mensagem: str) -> None:
        (raiz / caminho).write_text(conteudo, encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=str(raiz), check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", mensagem], cwd=str(raiz), check=True
        )

    _commitar(f"{FOTOS}/aba-01-jogar.png", "a foto do README", "primeiro")
    _commitar(f"{CODIGO_DA_TELA[0]}/aba01.py", "a aba mudou", "segundo — a tela")
    _commitar(
        f"{FOTOS_DA_VISTA}/aba-01-jogar.png",
        "a foto da vista, refeita",
        "terceiro — só a pasta nova",
    )

    assert uma_familia_em_dia(raiz, FOTOS_DA_VISTA, CODIGO_DA_TELA) is True, (
        "a família da VISTA foi refeita depois da mudança de tela e mesmo "
        "assim não passou — a régua ficaria reprovando quem fez o certo."
    )
    assert uma_familia_em_dia(raiz, FOTOS, CODIGO_DA_TELA) is False, (
        "as dez fotos do README são anteriores à mudança de tela e a régua "
        "disse que estavam em dia. A foto da pasta `maximizada/` pagou a "
        "dívida delas — o buraco medido em 11/09/2026."
    )
    assert fotos_em_dia(raiz, FOTOS, CODIGO_DA_TELA) is False, (
        "uma família atrasada tem de reprovar por todas: a pergunta do portão "
        "é 'a tela de hoje está fotografada?', e meia resposta é não."
    )
    assert familias_atrasadas(raiz, FOTOS, CODIGO_DA_TELA) == [FOTOS], (
        "a mensagem precisa NOMEAR a pasta que está devendo — sem isso quem "
        "apanha roda o comando da outra família e conclui que o portão quebrou."
    )


def test_o_portao_aprova_foto_em_dia(tmp_path: Path) -> None:
    """E o outro lado: fotografar depois de mexer na tela tem de passar."""
    raiz = _repo_de_mentira(tmp_path, fotos_por_ultimo=True)

    assert fotos_em_dia(raiz, FOTOS, CODIGO_DA_TELA) is True, (
        "o comparador reprovou um repositório em que a foto veio DEPOIS da "
        "mudança de tela, que é o caminho bom."
    )


def _declarar(raiz: Path, texto: str) -> None:
    """Escreve a declaração de conferência, sem commitar."""
    (raiz / CONFERIDO).write_text(texto, encoding="utf-8")


def test_a_declaracao_so_vale_para_o_commit_que_ela_nomeia(tmp_path: Path) -> None:
    """A MORDIDA da segunda porta: SHA de outro commit não abre nada."""
    raiz = _repo_de_mentira(tmp_path, fotos_por_ultimo=False)

    _declarar(
        raiz,
        "# conferido por ninguém\n"
        "0123456789abcdef0123456789abcdef01234567  03/09/2026  outro commit\n"
        "rodei o retratista, juro\n",
    )

    assert portao_fechado(raiz, FOTOS, CODIGO_DA_TELA, CONFERIDO) is False, (
        "a segunda porta abriu com uma declaração que NÃO nomeia o commit de "
        "tela deste repositório. Assim ela deixaria de ser a prova de um gesto "
        "e viraria um arquivo que, uma vez criado, cala o portão para sempre."
    )


def test_a_declaracao_fecha_o_portao_quando_a_foto_nao_muda(tmp_path: Path) -> None:
    """E o outro lado: declarando o commit CERTO, o portão fecha."""
    raiz = _repo_de_mentira(tmp_path, fotos_por_ultimo=False)
    commit_do_codigo = _ultimo_commit(raiz, *CODIGO_DA_TELA)

    _declarar(
        raiz,
        f"{commit_do_codigo}  03/09/2026  rodei o retratista, 14 fotos idênticas\n",
    )

    assert portao_fechado(raiz, FOTOS, CODIGO_DA_TELA, CONFERIDO) is True, (
        "o portão recusou uma declaração que nomeia exatamente o commit de tela "
        "atual. Nesse estado ele fica vermelho para sempre quando a mudança de "
        "tela não move pixel — e a única saída vira refotografar por bytes, "
        "que escreve o estado da máquina de quem rodou dentro da documentação."
    )


def test_sem_historico_o_portao_se_cala(tmp_path: Path) -> None:
    """Clone raso não é defeito de foto — e não pode virar vermelho no CI."""
    assert _sem_historico(tmp_path), (
        "uma pasta sem `.git` foi tratada como repositório com histórico. No "
        "CI, com `actions/checkout` raso, isto viraria um vermelho que não "
        "aponta defeito nenhum."
    )
