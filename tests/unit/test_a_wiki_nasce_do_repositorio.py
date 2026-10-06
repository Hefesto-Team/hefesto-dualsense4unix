"""A Wiki nasce do que o repositório já sabe: gerada, idempotente, filtrada e sem texto à mão.

`scripts/wiki/gerar.py` lê o README, `docs/usage`, `docs/protocol` e o mapa dos controles NA HORA.
A régua: toda fonte declarada existe, todo link interno da Wiki gerada resolve, toda página abre com o
cabeçalho da fonte, o mesmo commit gera os mesmos bytes, e uma linha do CSV muda só a página dela. As
mordidas: um endereço real, um termo da lista ou o vocabulário de dentro seguram a página (e o link dos
outros para ela volta ao arquivo no repositório); um link quebrado reprova a régua.
"""
# ruff: noqa: E501
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "scripts" / "wiki"
TERMO = "termoforjado"
CABECALHO_CSV = (
    "chave,controle,familia,rotulo,existe,cabo_aceita,radio_aceita,cabo_aciona,radio_aciona,"
    "cabo_de_onde_sei,radio_de_onde_sei,cabo_ate_onde_foi,radio_ate_onde_foi"
)
PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 16


def _carregar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("wiki_gerar", PASTA / "gerar.py")
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


G = _carregar()


def _endereco_real(mascarado: bool = False) -> str:
    """Um endereço que o portão acusa, montado em tempo de execução (o arquivo não o carrega)."""
    return ":".join(("3c", "12", "a1", "00", "00", "09") if mascarado else ("3c", "12", "a1", "77", "5e", "09"))


@pytest.fixture(autouse=True)
def _lista_de_mentira(monkeypatch: pytest.MonkeyPatch) -> None:
    """O filtro de rastro lê esta lista, e não a da máquina."""
    monkeypatch.setenv("AUTORIA_VEDADOS", f"1 {TERMO}")


def _escreve(raiz: Path, relativo: str, texto: str | bytes) -> None:
    alvo = raiz / relativo
    alvo.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(texto, bytes):
        alvo.write_bytes(texto)
    else:
        alvo.write_text(texto, encoding="utf-8")


def _csv(linhas: list[str]) -> str:
    return CABECALHO_CSV + "\n" + "\n".join(linhas) + "\n"


LINHAS_PADRAO = [
    "gatilho.a,dualsense,gatilho,Gatilho A,tem,sim,sim,sim,sim,medido,medido,O APARELHO OBEDECEU,MONTOU",
    "gatilho.a,pro,gatilho,Gatilho A,nao-tem,não,não,não,não,inferido-do-codigo,inferido-do-codigo,,",
    "luz.b,dualsense,luz,Luz B,tem,sim,parcial,sim,não,medido,medido,MONTOU,",
]


def _arvore(raiz: Path, *, linhas: list[str] | None = None) -> Path:
    _escreve(raiz, "README.md",
             "# Produto\n\n![logo](assets/appimage/logo.png)\n\nVeja [o uso](docs/usage/a.md) e "
             "[a licença](LICENSE).\n")
    _escreve(raiz, "LICENSE", "MIT\n")
    _escreve(raiz, "assets/appimage/logo.png", PNG)
    _escreve(raiz, "docs/usage/assets/foto.png", PNG)
    _escreve(raiz, "docs/usage/a.md",
             "# Usar A\n\nVeja [b](b.md#parte), [o protocolo](../protocol/c.md), [a casa](../process/x.md),\n"
             "[o início](../../README.md) e ![foto](assets/foto.png).\n\n```\n[em código](b.md)\n```\n")
    _escreve(raiz, "docs/usage/b.md", "# Usar B\n\n## Parte\n\nTexto.\n")
    _escreve(raiz, "docs/protocol/c.md", "# Protocolo C\n\nUm byte.\n")
    _escreve(raiz, "docs/protocol/interno.md", "# Interno\n\nDa casa.\n")
    _escreve(raiz, "docs/process/x.md", "# Da casa\n")
    _escreve(raiz, "docs/data/mapa-controles.csv", _csv(linhas or LINHAS_PADRAO))
    return raiz


FORA_DA_FIXTURE = {"docs/protocol/interno.md": "só da casa"}


def _gera(raiz: Path, **kw: Any) -> Any:
    return G.gerar(raiz, fora=FORA_DA_FIXTURE, lar=raiz / "_lar", **kw)


# ---------------------------------------------------------------------------
# A árvore de hoje
# ---------------------------------------------------------------------------


def test_toda_fonte_declarada_existe_e_tem_motivo() -> None:
    assert (RAIZ / G.LEIAME).is_file() and (RAIZ / G.MAPA).is_file()
    assert any((RAIZ / G.USO).glob("*.md")) and any((RAIZ / G.PROTOCOLO).glob("*.md"))
    for fonte, motivo in G.FORA.items():
        assert (RAIZ / fonte).is_file(), f"{fonte} está em FORA e não existe: tire da lista"
        assert motivo.strip(), f"{fonte} está em FORA sem o motivo"


def test_a_wiki_de_hoje_gera_com_link_que_resolve_e_cabecalho_da_fonte() -> None:
    r = G.gerar(RAIZ, filtrar=False)
    arquivos = r.wiki.arquivos()
    fontes = {p for p in G.fontes_publicadas(RAIZ, G.FORA)}
    publicadas = {p.fonte for p in r.wiki.paginas.values()}
    assert fontes <= publicadas, f"fonte sem página: {sorted(fontes - publicadas)}"
    for fonte in (*(f"{G.USO}/{p.name}" for p in (RAIZ / G.USO).glob("*.md")),
                  *(f"{G.PROTOCOLO}/{p.name}" for p in (RAIZ / G.PROTOCOLO).glob("*.md"))):
        assert fonte in publicadas or fonte in G.FORA, f"{fonte} não vai para a Wiki nem está em FORA"
    assert G.links_quebrados(arquivos, set(r.wiki.imagens)) == []
    assert G.paginas_sem_fonte(arquivos) == []
    assert r.wiki.avisos == [], r.wiki.avisos
    assert {"Home", "Mapa-dos-controles", "_Sidebar", "_Footer"} <= set(r.wiki.paginas)


def test_o_mesmo_commit_gera_os_mesmos_bytes_e_o_conferir_fica_vazio(tmp_path: Path) -> None:
    saida = tmp_path / "w"
    assert G.principal(["--saida", str(saida), "--sem-filtros"]) == 0
    primeira = G._do_disco(saida)
    assert G.principal(["--saida", str(saida), "--sem-filtros"]) == 0
    assert G._do_disco(saida) == primeira
    assert G.principal(["--saida", str(saida), "--sem-filtros", "--conferir"]) == 0


def test_o_conferir_acusa_a_pagina_editada_a_mao(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    saida = tmp_path / "w"
    G.principal(["--saida", str(saida), "--sem-filtros"])
    (saida / "Home.md").write_text("escrito à mão\n", encoding="utf-8")
    assert G.principal(["--saida", str(saida), "--sem-filtros", "--conferir"]) == 1
    assert "muda Home.md" in capsys.readouterr().out


def test_o_leitor_do_mapa_e_o_mesmo_do_gerar_mapa() -> None:
    spec = importlib.util.spec_from_file_location("wiki_gerar_mapa", RAIZ / "scripts" / "gerar-mapa.py")
    assert spec and spec.loader
    mapa = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mapa
    spec.loader.exec_module(mapa)
    ids_dele = [ln["id"] for ln in mapa.le_csv()]
    assert [ln["id"] for ln in G.ler_mapa(RAIZ)] == ids_dele
    assert dict(G.CONTROLES) == mapa.ROTULO


def test_o_gerador_nao_grava_pagina_no_repositorio() -> None:
    versionados = subprocess.run(["git", "ls-files", "scripts/wiki"], cwd=RAIZ, check=True,
                                 capture_output=True, text=True).stdout.split()
    de_fora = [f for f in versionados if not f.endswith(".py")]
    assert de_fora == [], f"scripts/wiki só tem código; página gerada não se versiona: {de_fora}"


def test_os_filtros_atravessam_a_wiki_de_hoje_e_dizem_o_que_seguraram(tmp_path: Path) -> None:
    r = G.gerar(RAIZ, lar=tmp_path / "lar")
    assert r.nao_medido == []
    for nome in r.seguradas:
        assert nome not in r.wiki.paginas, f"{nome} está segurada e foi para a Wiki"
    assert G.links_quebrados(r.wiki.arquivos(), set(r.wiki.imagens)) == []


# ---------------------------------------------------------------------------
# O desenho, numa árvore pequena
# ---------------------------------------------------------------------------


def test_os_links_viram_pagina_imagem_arquivo_ou_so_o_texto(tmp_path: Path) -> None:
    r = _gera(_arvore(tmp_path))
    a = r.wiki.paginas["Usar-a"].corpo
    assert "[b](Usar-b#parte)" in a
    assert "[o protocolo](Protocolo-c)" in a
    assert "[o início](Home)" in a
    assert "![foto](images/foto.png)" in a
    assert "[a casa]" not in a and "a casa," in a, "link para o trabalho interno vira só o texto"
    assert "[em código](b.md)" in a, "o que está em bloco de código não muda"
    home = r.wiki.paginas["Home"].corpo
    assert "images/logo.png" in home and "[o uso](Usar-a)" in home
    assert "/blob/dev/LICENSE" in home
    assert r.wiki.imagens == {"images/foto.png": "docs/usage/assets/foto.png",
                              "images/logo.png": "assets/appimage/logo.png"}
    assert G.links_quebrados(r.wiki.arquivos(), set(r.wiki.imagens)) == []
    assert "Protocolo-interno" not in r.wiki.paginas, "o que está em FORA não vai"


def test_link_para_arquivo_que_nao_existe_vira_so_o_texto_e_um_aviso(tmp_path: Path) -> None:
    raiz = _arvore(tmp_path)
    _escreve(raiz, "docs/usage/b.md", "# Usar B\n\nVeja [o sumido](nao-existe.md).\n")
    r = _gera(raiz)
    assert "[o sumido]" not in r.wiki.paginas["Usar-b"].corpo
    assert any("nao-existe.md" in a for a in r.wiki.avisos)


def test_mudar_uma_linha_do_csv_muda_so_a_pagina_dela(tmp_path: Path) -> None:
    raiz = _arvore(tmp_path / "a")
    outra = _arvore(tmp_path / "b", linhas=[
        LINHAS_PADRAO[0], LINHAS_PADRAO[1],
        "luz.b,dualsense,luz,Luz B,tem,sim,sim,sim,sim,medido,medido,O APARELHO OBEDECEU,MONTOU"])
    antes = G.conteudo_da_saida(_gera(raiz).wiki, raiz)
    depois = G.conteudo_da_saida(_gera(outra).wiki, outra)
    assert [n for n in antes if antes[n] != depois[n]] == ["Mapa-luz.md"]


def test_o_mapa_traz_cabo_e_bluetooth_lado_a_lado_com_a_prova(tmp_path: Path) -> None:
    r = _gera(_arvore(tmp_path))
    gatilho = r.wiki.paginas["Mapa-gatilhos"].corpo
    assert "| Gatilho A | DualSense | tem | funciona | funciona | medido; acendeu, girou, saiu som |" in gatilho
    assert "| Gatilho A | Nintendo Pro | não tem | não | não | lido no código | lido no código |" in gatilho
    luz = r.wiki.paginas["Mapa-luz"].corpo
    assert "aceita, o efeito não foi visto" in luz
    indice = r.wiki.paginas["Mapa-dos-controles"].corpo
    assert "[Gatilhos](Mapa-gatilhos)" in indice and "[Luz](Mapa-luz)" in indice
    barra = r.wiki.paginas["_Sidebar"].corpo
    assert "(Mapa-gatilhos)" in barra and "(Usar-a)" in barra and "(Protocolo-c)" in barra


def test_a_pagina_com_vocabulario_de_dentro_e_segurada_e_o_link_volta_ao_repositorio(tmp_path: Path) -> None:
    raiz = _arvore(tmp_path)
    _escreve(raiz, "docs/usage/b.md", "# Usar B\n\nA régua dela mediu.\n")
    r = _gera(raiz)
    assert "Usar-b" in r.seguradas and "Usar-b" not in r.wiki.paginas
    assert any("[dela]" in m for m in r.seguradas["Usar-b"])
    assert "[b](Usar-b" not in r.wiki.paginas["Usar-a"].corpo
    assert "[b](https://" in r.wiki.paginas["Usar-a"].corpo and "docs/usage/b.md#parte" in r.wiki.paginas["Usar-a"].corpo
    assert "(Usar-b)" not in r.wiki.paginas["_Sidebar"].corpo
    assert G.links_quebrados(r.wiki.arquivos(), set(r.wiki.imagens)) == []


def test_endereco_real_numa_fonte_reprova_a_geracao(tmp_path: Path) -> None:
    raiz = _arvore(tmp_path)
    _escreve(raiz, "docs/protocol/c.md", f"# Protocolo C\n\nO adaptador {_endereco_real()} respondeu.\n")
    r = _gera(raiz)
    assert any("endereço [MAC real]" in m for m in r.seguradas["Protocolo-c"])
    assert "Protocolo-c" not in r.wiki.paginas
    assert _endereco_real() not in "".join(r.seguradas["Protocolo-c"]), "o log não repete o endereço"
    # a máscara da casa passa
    _escreve(raiz, "docs/protocol/c.md", f"# Protocolo C\n\nO adaptador {_endereco_real(True)} respondeu.\n")
    assert "Protocolo-c" in _gera(raiz).wiki.paginas


def test_termo_da_lista_segura_a_pagina_sem_imprimir_o_termo(tmp_path: Path) -> None:
    raiz = _arvore(tmp_path)
    _escreve(raiz, "docs/usage/b.md", f"# Usar B\n\nUm {TERMO} aqui.\n")
    r = _gera(raiz)
    assert "Usar-b" in r.seguradas
    assert TERMO not in "".join(m for ms in r.seguradas.values() for m in ms)


def test_sem_a_lista_o_filtro_nao_da_limpo_e_nada_e_escrito(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    raiz = _arvore(tmp_path / "r")
    real = G.filtros.carregar

    def carregar(nome: str) -> Any:
        if nome == "check_autoria":
            class SemLista:
                @staticmethod
                def _lista() -> None:
                    return None
            return SemLista
        return real(nome)

    monkeypatch.setattr(G.filtros, "carregar", carregar)
    saida = tmp_path / "w"
    assert G.principal(["--saida", str(saida), "--raiz", str(raiz), "--lar", str(tmp_path / "lar")]) == 3
    assert not saida.exists(), "o que não dá para medir não sobe"
    assert "NÃO MEDIDO" in capsys.readouterr().err


def test_a_regua_pega_o_link_quebrado_e_a_pagina_sem_cabecalho(tmp_path: Path) -> None:
    r = _gera(_arvore(tmp_path))
    arquivos = r.wiki.arquivos()
    assert G.links_quebrados(arquivos, set(r.wiki.imagens)) == []
    ruim = dict(arquivos)
    ruim["Usar-a.md"] += "\n[sumiu](Usar-que-nao-existe)\n![x](images/nao-tem.png)\n"
    achados = G.links_quebrados(ruim, set(r.wiki.imagens))
    assert achados == ["Usar-a.md: Usar-que-nao-existe", "Usar-a.md: images/nao-tem.png"]
    ruim["Escrita.md"] = "# À mão\n"
    assert G.paginas_sem_fonte(ruim) == ["Escrita.md"]


def test_toda_pagina_diz_de_qual_arquivo_nasce_e_o_rodape_manda_corrigir_la(tmp_path: Path) -> None:
    r = _gera(_arvore(tmp_path))
    for nome, pagina in r.wiki.paginas.items():
        assert pagina.corpo.startswith("<!-- gerado por scripts/wiki/gerar.py a partir de "), nome
        if not nome.startswith("_") and nome != "Home":
            assert f"[`{pagina.fonte}`]" in pagina.corpo and "corrija lá" in pagina.corpo, nome
    assert "corrija lá" in r.wiki.paginas["Home"].corpo
    assert "correção" in r.wiki.paginas["_Footer"].corpo


def test_o_mapa_segue_a_ordem_das_familias_no_indice_e_na_barra(tmp_path: Path) -> None:
    # Pela chave, «audio» abriria o mapa; na ordem de quem lê, os gatilhos abrem e o som vem depois da luz.
    som = "som.c,dualsense,audio,Som C,tem,sim,sim,sim,sim,medido,medido,MONTOU,MONTOU"
    r = _gera(_arvore(tmp_path, linhas=[*LINHAS_PADRAO, som]))
    indice = r.wiki.paginas["Mapa-dos-controles"].corpo
    assert indice.index("(Mapa-gatilhos)") < indice.index("(Mapa-luz)") < indice.index("(Mapa-som)")
    barra = r.wiki.paginas["_Sidebar"].corpo
    assert (barra.index("(Mapa-dos-controles)") < barra.index("(Mapa-gatilhos)") < barra.index("(Mapa-luz)")
            < barra.index("(Mapa-som)"))


def test_a_saida_que_nao_e_wiki_e_recusada_e_nada_se_apaga(tmp_path: Path) -> None:
    raiz = _arvore(tmp_path / "r")
    lar = str(tmp_path / "lar")
    # a própria árvore de origem: a escrita apagaria o repositório
    assert G.principal(["--saida", str(raiz), "--raiz", str(raiz), "--lar", lar]) == 2
    assert G.principal(["--saida", str(tmp_path), "--raiz", str(raiz), "--lar", lar]) == 2
    assert (raiz / "docs/process/x.md").is_file() and (raiz / "LICENSE").is_file()
    # uma pasta com arquivos que não é Wiki
    outra = tmp_path / "outra"
    _escreve(outra, "notas.txt", "minhas\n")
    assert G.principal(["--saida", str(outra), "--raiz", str(raiz), "--lar", lar]) == 2
    assert (outra / "notas.txt").read_text(encoding="utf-8") == "minhas\n"
    # a Wiki de verdade: a página escrita à mão sai, e o `.git` (pasta ou arquivo) fica
    wiki = tmp_path / "wiki"
    _escreve(wiki, "Home.md", "à mão\n")
    _escreve(wiki, "Escrita-a-mao.md", "à mão\n")
    _escreve(wiki, ".git", "gitdir: /em/outro/lugar\n")
    assert G.principal(["--saida", str(wiki), "--raiz", str(raiz), "--lar", lar]) == 0
    assert not (wiki / "Escrita-a-mao.md").exists() and (wiki / ".git").is_file()
    assert (wiki / "Home.md").read_text(encoding="utf-8").startswith("<!-- gerado por")


def test_o_pedaco_escondido_do_endereco_da_maquina_segura_a_pagina(tmp_path: Path) -> None:
    raiz = _arvore(tmp_path / "r")
    lar = tmp_path / "lar"
    octetos = ("e8", "47", "3a", "5c", "6d", "09")      # faixa forjada, montada em tempo de execução
    _escreve(lar, ".config/hefesto-dualsense4unix/maquina.json", '{"radio": "' + ":".join(octetos) + '"}\n')
    pedaco = ":".join(octetos[2:5])                      # a janela com os dois octetos que a máscara esconde
    _escreve(raiz, "docs/protocol/c.md", f"# Protocolo C\n\nO trecho {pedaco} apareceu.\n")
    r = G.gerar(raiz, fora=FORA_DA_FIXTURE, lar=lar)
    assert any("endereço da máquina" in m for m in r.seguradas.get("Protocolo-c", [])), r.seguradas
    assert "Protocolo-c" not in r.wiki.paginas
    assert pedaco not in "".join(r.seguradas["Protocolo-c"]), "o log não repete o pedaço"


# ---------------------------------------------------------------------------
# O workflow
# ---------------------------------------------------------------------------


def test_o_workflow_dispara_com_toda_fonte_que_o_gerador_le(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fonte lida e fora dos `paths` é página que envelhece calada: a Wiki não regera quando ela muda."""
    import fnmatch

    lidos: set[str] = set()
    real = G.filtros.carregar

    def carregar(nome: str) -> Any:
        lidos.add(f"scripts/{nome}.py")
        return real(nome)

    monkeypatch.setattr(G.filtros, "carregar", carregar)
    r = G.gerar(RAIZ, lar=tmp_path / "lar")
    lidos |= {p.fonte for p in r.wiki.paginas.values() if p.fonte and p.fonte != "docs/"}
    lidos |= set(r.wiki.imagens.values())
    lidos |= {p.fonte for p in G.gerar(RAIZ, filtrar=False).wiki.paginas.values() if p.fonte and p.fonte != "docs/"}
    caminhos = (_workflow().get("on") or _workflow().get(True))["push"]["paths"]
    fora = sorted(f for f in lidos if not any(fnmatch.fnmatch(f, c) for c in caminhos))
    assert fora == [], f"lidos pelo gerador e fora dos paths do wiki.yml: {fora}"


def _workflow() -> Any:
    dados: Any = yaml.safe_load((RAIZ / ".github" / "workflows" / "wiki.yml").read_text(encoding="utf-8"))
    return dados


def test_o_workflow_gera_a_cada_push_que_toca_uma_fonte_e_nunca_sem_filtro() -> None:
    texto = (RAIZ / ".github" / "workflows" / "wiki.yml").read_text(encoding="utf-8")
    dados = _workflow()
    gatilho: Any = dados.get("on") or dados.get(True)
    assert gatilho["push"]["branches"] == ["dev"]
    caminhos = gatilho["push"]["paths"]
    for fonte in ("README.md", "docs/usage/**", "docs/protocol/**", "docs/data/mapa-controles.csv",
                  "scripts/wiki/**", ".github/workflows/wiki.yml"):
        assert fonte in caminhos, fonte
    assert "scripts/wiki/gerar.py" in texto
    assert "--sem-filtros" not in texto, "o workflow nunca publica sem os filtros"
    assert "AUTORIA_VEDADOS" in texto, "o filtro de rastro precisa da lista"
    assert "wiki.git" in texto and "git diff --cached --quiet" in texto, "só empurra se mudou"
    assert dados["permissions"] == {"contents": "write"}
    assert "x-access-token:${" not in texto.replace("printf 'x-access-token:%s'", ""), "o token vai no cabeçalho, não na URL"
    assert "http.extraheader" in texto
    for job in dados["jobs"].values():
        for passo in job["steps"]:
            assert "run" in passo or "uses" in passo
            if "uses" in passo:
                assert "@" in passo["uses"] and len(passo["uses"].split("@")[1].split()[0]) == 40, passo["uses"]
