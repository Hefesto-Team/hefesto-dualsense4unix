#!/usr/bin/env python3
"""Reprova documento que cita arquivo, variável de ambiente ou método IPC que"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple

EXTENSOES = frozenset(
    {".py", ".sh", ".md", ".yml", ".yaml", ".toml", ".glade", ".rules"}
)

EXTENSOES_NOME_SOLTO = frozenset({".py", ".sh"})

DIRS_IGNORADOS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "flatpak-repo",
        "flatpak-build-dir",
        "dist",
        "build",
        ".eggs",
    }
)

PREFIXOS_IGNORADOS = (
    "docs/history/",
    "docs/research/",
    "docs/process/",
)

EXTERNOS = frozenset(
    {
        "pydualsense.py",
        "universal-sanitizer.py",
        "setup.py",
        "conftest.py",
        "sony_gamepad.py",
        "checksum.py",
        "enums.py",
        "base_device.py",
        "base_gamepad.py",
        "swGetVer.sh",
        "swExitDinput.sh",
        "swChangeDinput.sh",
        "test_sony.py",
        "8bitso_sn30_windows.md",
    }
)

EXTERNOS_POR_PASTA = ("Pro2/", "SwitchMode/", "SN30ProPlus/", "xpadneo/",
                      "8bitdo-spec/", "tests_kernel/")

FORA_DO_GIT: dict[str, str] = {
    "docs/process/": (
        "os arquivos de estudo e de metalinguagem. Saíram do git em 15/09/2026 "
        "por ordem dela; continuam no disco dela e do André."
    ),
}


def fora_do_git(texto: str) -> str | None:
    """A razão de o caminho não viajar no git, ou None se ele viaja."""
    alvo = texto.lstrip("./")
    for prefixo, razao in FORA_DO_GIT.items():
        if alvo.startswith(prefixo) or ("/" + prefixo) in alvo:
            return razao
    return None


def conferir_fora_do_git(raiz: Path) -> list[str]:
    """Caminho declarado FORA_DO_GIT não pode voltar a ser rastreado."""
    import subprocess

    problemas: list[str] = []
    for prefixo, razao in FORA_DO_GIT.items():
        saida = subprocess.run(
            ["git", "-C", str(raiz), "ls-files", "--", prefixo],
            capture_output=True, text=True, check=False,
        ).stdout.strip()
        if saida:
            quantos = len(saida.splitlines())
            problemas.append(
                f"FORA-DO-GIT-RASTREADO: `{prefixo}` está declarado em "
                f"`FORA_DO_GIT`\n"
                f"    ({razao})\n"
                f"    e o git rastreia {quantos} arquivo(s) dentro dele. Ou a\n"
                "    decisão foi desfeita — e a linha sai daqui, para as\n"
                "    citações voltarem a ser conferidas —, ou alguém versionou\n"
                "    de volta o que ela mandou tirar."
            )
    return problemas

_ESTUDIO = (
    "o estúdio de fotografia da JANELA — os cinco arquivos de "
    "`scripts/gui-captura/`. Apagados em 06/09/2026 (GTK-3). Quem fotografa as "
    "DEZ páginas é `src/hefesto_dualsense4unix/interface/olhar.py --todas "
    "--publicado --doc`."
)

_REGUAS = (
    "régua da JANELA, apagada em 06/09/2026 (GTK-3) com a superfície que ela "
    "media. O veredito de cada uma, uma a uma, está em "  # (noqa-acento: verbo medir, imperfeito)
    "`docs/process/agentes/2026-09-06/GTK-3-segunda-volta.md`."
)

APOSENTADOS: dict[str, str] = {
    "src/hefesto_dualsense4unix/gui/main.glade": (
        "a janela GTK — o XML de 292 KB com as onze abas. Apagado em 06/09/2026 "
        "(GTK-3). O que a tela declara hoje são as dez páginas de "
        "`src/hefesto_dualsense4unix/interface/paginas/`."
    ),
    "src/hefesto_dualsense4unix/app/app.py": (
        "o `HefestoApp`, que montava a janela. Apagado em 06/09/2026 (GTK-3). O "
        "MOTOR que ele pendurava — `app/actions/`, `app/widgets/`, `app/telas/` "
        "— ficou, e é o que a interface nova chama a cada tique."
    ),
    "src/hefesto_dualsense4unix/app/main.py": (
        "o entry point da janela. Apagado em 06/09/2026 (GTK-3). O que nele não "
        "montava janela mudou de casa para `app/arranque.py`; o lançador de hoje "
        "é `scripts/abrir_interface.py`."
    ),
    "scripts/gui-captura/retratar_abas.py": _ESTUDIO,
    "scripts/gui-captura/retratar_dialogos.py": _ESTUDIO,
    "scripts/gui-captura/retrato_offscreen.py": _ESTUDIO,
    "scripts/gui-captura/aba_ativa.sh": _ESTUDIO,
    "scripts/gui-captura/capturar_verificado.sh": _ESTUDIO,
    "tests/unit/test_a5_fechar_a_janela_nao_perde_a_declaracao.py": _REGUAS,
    "tests/unit/test_a_caixinha_que_tira_do_steam_input.py": _REGUAS,
    "tests/unit/test_layout_orcamento_altura.py": _REGUAS,
    "tests/unit/test_lightbar_vao_vertical.py": _REGUAS,
    "tests/unit/test_notebook_switch_page.py": _REGUAS,
    "tests/unit/test_socorro_ao_fechar_diz_por_que_a_janela_nao_fecha.py": _REGUAS,
    "tests/unit/test_status_minimizar_mata_a_captura.py": _REGUAS,
    "tests/unit/test_z2_fita_declara_quem_obedece.py": _REGUAS,
    "scripts/portao_alvo_tem_dono.py": (
        "o portão que importava `HefestoApp` para conferir "
        "`HefestoApp._ALVO_POR_ABA` — a fita da JANELA. Apagado em 06/09/2026 "
        "(GTK-3), junto com o passo do `ci.yml` que o rodava."
    ),
    "tests/unit/test_a_aba_perfis_na_foto.py": (
        "montava a aba Perfis da JANELA a partir do `.glade` e conferia que a "
        "foto dela não perguntava ao daemon. Apagada em 08/09/2026 — o widget "
        "que ela montava saiu com a janela em 06/09 (GTK-3). O fato do "
        "anonimato ficou, medido sobre o retratista de hoje, em "
        "`tests/unit/test_retrato_das_abas_nao_vaza_dado_real.py`."
    ),
    "tests/unit/test_a_foto_do_cabecalho_prova_o_alvo.py": (
        "media a fita 'Ajustes vão para:' no `header_bar` da JANELA, que ficava "  # (noqa-acento: verbo medir, imperfeito)
        "fora do recorte de toda foto de aba. Apagada em 08/09/2026 — não há "
        "`header_bar` nem `main_notebook`. O que ela cobrava do lado da "
        "documentação (as duas fotos existem e o `interface.md` as publica) é "
        "hoje `test_toda_imagem_que_a_documentacao_publica_existe`, que mede o "
        "documento inteiro em vez de duas imagens nomeadas."
    ),
    "tests/unit/test_a_foto_monta_como_o_produto_monta.py": (
        "exigia que o retratista chamasse os mixins de produção em vez de "
        "montar widget GTK à mão. Apagada em 08/09/2026 — o retratista de hoje "
        "não monta widget nenhum: ele abre uma página HTML num Chrome. A regra "
        "de fundo (a foto sai do que o produto renderiza) virou estrutura, e "
        "está em `test_a_foto_da_doc_mostra_a_aba_inteira`."
    ),
    "tests/unit/test_a_mesa_cheia_na_foto.py": (
        "o modo `--mesa-cheia`, que alimentava as onze abas da JANELA com "
        "`tests/fixtures/state_full_quatro_controles.json`. Apagada em "
        "08/09/2026 — não há modo, nem fixture, nem abas montadas em widget. "
        "A garantia de que a foto não nasce de estado vivo ficou em "
        "`test_retrato_das_abas_nao_vaza_dado_real`."
    ),
    "tests/unit/test_home_foto_dos_estados.py": (
        "fotografava a aba Início da JANELA em cinco estados e exigia PNG "
        "diferente para cada um. Apagada em 08/09/2026 — a aba Início é a "
        "página `01-jogar.html`, e nenhum instrumento desta casa a fotografa "
        "por estado. **É a única das seis cujo fato não tem herdeiro**, e fica "
        "escrito: os cinco estados do produto de hoje seguem sem foto de prova."
    ),
    "tests/unit/test_retrato_dos_dialogos_nao_vaza_dado_real.py": (
        "impedia o retratista dos DIÁLOGOS de publicar os perfis dela. Apagada "
        "em 08/09/2026 com `scripts/gui-captura/retratar_dialogos.py`, que saiu "
        "em 06/09 — sem gerador não há o que travar. As cinco imagens que ele "
        "produziu continuam publicadas no `interface.md` como registro datado, "
        "e o único programa que hoje escreve em `docs/usage/assets/` está "
        "travado por `test_retrato_das_abas_nao_vaza_dado_real`."
    ),
}


def aposentado(texto: str) -> str | None:
    """A razão de o caminho ter sido aposentado, ou None se ele não foi."""
    alvo = texto.lstrip("./")
    for caminho, razao in APOSENTADOS.items():
        if caminho.endswith("/"):
            if caminho.rstrip("/").split("/")[-1] + "/" in alvo + "/":
                return razao
            continue
        if alvo == caminho or caminho.endswith("/" + alvo) or alvo.endswith("/" + caminho):
            return razao
        if alvo == caminho.split("/")[-1]:
            return razao
    return None


def conferir_aposentados(raiz: Path) -> list[str]:
    """Arquivo declarado APOSENTADO não pode estar de volta na árvore."""
    problemas: list[str] = []
    for caminho, razao in APOSENTADOS.items():
        if (raiz / caminho.rstrip("/")).exists():
            problemas.append(
                f"APOSENTADO-VIVO: {caminho} está declarado em `APOSENTADOS`\n"
                f"    ({razao})\n"
                "    e EXISTE nesta árvore. Ou a remoção foi desfeita — e a linha sai\n"
                "    daqui, para as citações voltarem a ser conferidas —, ou alguém\n"
                "    recriou o que a decisão dela mandou apagar."
            )
    return problemas

MARCADOR_ISENCAO = "<!-- ref-externa"

PREFIXOS_QUE_ENSINAM = ("docs/usage/", "docs/adr/", "docs/protocol/", "README.md")

EXTENSOES_DE_CODIGO = frozenset(
    {
        ".py",
        ".sh",
        ".bash",
        ".service",
        ".toml",
        ".yml",
        ".yaml",
        ".rules",
        ".desktop",
        ".cfg",
        ".ini",
        ".in",
        ".json",
        ".rs",
        ".nix",
        ".c",
        ".h",
    }
)

NOMES_DE_CODIGO = frozenset({"PKGBUILD", "Makefile", "hefesto-launch"})

ARQUIVOS_FORA_DO_INDICE_DE_ENV = frozenset(
    {
        "scripts/validar-referencias-docs.py",
        "tests/unit/test_validar_referencias_docs.py",
        "tests/unit/test_doc_verdade_02_contagens_derivadas.py",
    }
)

SUFIXOS_DE_ARQUIVO = frozenset(
    {
        "py",
        "sh",
        "md",
        "yml",
        "yaml",
        "toml",
        "glade",
        "rules",
        "json",
        "txt",
        "service",
        "po",
        "pot",
        "c",
        "h",
        "bin",
        "log",
        "patch",
        "desktop",
        "cfg",
        "ini",
        "in",
        "vdf",
        "env",
        "pid",
        "sock",
        "lock",
        "flag",
        "conf",
        "rs",
        "so",
        "ko",
        "deb",
        "xml",
        "html",
        "css",
        "js",
        "png",
        "svg",
        "gz",
        "zip",
        "bak",
        "tmp",
        "d",
    }
)

FONTE_DOS_METODOS_IPC = "src/hefesto_dualsense4unix/daemon/ipc_server.py"

_CRASE = re.compile(r"`([^`\n]{1,120})`")
_LINK = re.compile(r"\]\(([^)\s]{1,200})\)")
_CERCA = re.compile(r"^\s*(```|~~~)")
_TOKEN_LIMPO = re.compile(r"[A-Za-z0-9._/+-]+")
_ENV = re.compile(r"\bHEFESTO_[A-Z0-9_]+")
_METODO = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){1,2}$")
_NOTA_DE_VERIFICACAO = re.compile(r"^#{1,6}\s*Nota de verifica", re.IGNORECASE)

_SUBIDA = re.compile(r"^(?:\.\./)+")

_ABERTURA_DE_FRONTMATTER = "---"
_CHAVE_DO_CRIA = "cria"
_CHAVE_DE_TOPO = re.compile(r"^([a-z_]+):\s*(.*)$")
_ITEM_DE_LISTA = re.compile(r"^\s+-\s+(.+)$")
_COMENTARIO_INLINE = re.compile(r"\s+#.*$")

REGRA_ARQUIVO = "arquivo"
REGRA_ENV = "variável de ambiente"
REGRA_IPC = "método de IPC"


class Achado(NamedTuple):
    """Uma referência morta: documento, linha, o texto citado e a regra."""

    documento: str
    linha: int
    alvo: str
    regra: str = REGRA_ARQUIVO

    def __str__(self) -> str:
        return f"  {self.documento}:{self.linha}: {self.alvo}  [{self.regra}]"


def indexar(raiz: Path) -> set[str]:
    """Devolve todo caminho do repositório mais todos os seus sufixos."""
    sufixos: set[str] = set()
    for pasta, subpastas, arquivos in os.walk(raiz):
        subpastas[:] = [d for d in subpastas if d not in DIRS_IGNORADOS]
        base = Path(pasta)
        for nome in list(arquivos) + list(subpastas):
            try:
                relativo = (base / nome).relative_to(raiz).as_posix()
            except ValueError:  # pragma: no cover - defensivo
                continue
            partes = relativo.split("/")
            for corte in range(len(partes)):
                sufixos.add("/".join(partes[corte:]))
    return sufixos


def nomes_de_raiz(raiz: Path) -> set[str]:
    """Os nomes de arquivo/pasta que moram NO TOPO do repositório."""
    try:
        return {p.name for p in raiz.iterdir() if p.name not in DIRS_IGNORADOS}
    except OSError:  # pragma: no cover - defensivo
        return set()


def indexar_envs(raiz: Path) -> set[str]:
    """Todo literal `HEFESTO_*` que aparece em código, script ou empacotamento."""
    encontrados: set[str] = set()
    for pasta, subpastas, arquivos in os.walk(raiz):
        subpastas[:] = [d for d in subpastas if d not in DIRS_IGNORADOS]
        base = Path(pasta)
        try:
            relativo_pasta = base.relative_to(raiz).as_posix()
        except ValueError:  # pragma: no cover - defensivo
            continue
        if relativo_pasta.startswith("docs"):
            continue
        for nome in arquivos:
            caminho = base / nome
            if caminho.suffix not in EXTENSOES_DE_CODIGO and nome not in NOMES_DE_CODIGO:
                continue
            relativo = f"{relativo_pasta}/{nome}" if relativo_pasta != "." else nome
            if relativo in ARQUIVOS_FORA_DO_INDICE_DE_ENV:
                continue
            try:
                texto = caminho.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            encontrados.update(_ENV.findall(texto))
    return encontrados


def indexar_metodos_ipc(raiz: Path) -> set[str]:
    """As chaves do dicionário `_handlers` de `daemon/ipc_server.py`, por AST."""
    fonte = raiz / FONTE_DOS_METODOS_IPC
    try:
        arvore = ast.parse(fonte.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()

    metodos: set[str] = set()
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Assign):
            continue
        for alvo in no.targets:
            se_e_o_registro = isinstance(alvo, ast.Attribute) and alvo.attr == "_handlers"
            if not se_e_o_registro or not isinstance(no.value, ast.Dict):
                continue
            for chave in no.value.keys:
                if isinstance(chave, ast.Constant) and isinstance(chave.value, str):
                    metodos.add(chave.value)
    return metodos


def _sufixos_de(caminho: str) -> set[str]:
    """Todo sufixo de um caminho: `a/b/c.py` -> `a/b/c.py`, `b/c.py`, `c.py`."""
    partes = caminho.split("/")
    return {
        "/".join(partes[corte:]) for corte in range(len(partes)) if partes[corte]
    }


def _caminhos_do_valor(valor: str) -> list[str]:
    """Os caminhos de um valor de frontmatter: lista inline ou escalar."""
    texto = valor.strip()
    if not texto:
        return []
    inline = texto.startswith("[")
    pedacos = texto[1:].split("]", 1)[0].split(",") if inline else [texto]

    caminhos: list[str] = []
    for pedaco in pedacos:
        limpo = pedaco.strip().strip("'\"")
        if not limpo:
            continue
        primeiro = limpo.split()[0].strip("'\"")
        if _TOKEN_LIMPO.fullmatch(primeiro):
            caminhos.append(primeiro)
    return caminhos


def declarados_no_cria(conteudo: str) -> set[str]:
    """Os arquivos que o frontmatter DESTE documento declara que vai criar."""
    linhas = conteudo.splitlines()
    if not linhas or linhas[0].strip() != _ABERTURA_DE_FRONTMATTER:
        return set()
    try:
        fim = next(
            indice
            for indice in range(1, len(linhas))
            if linhas[indice].strip() == _ABERTURA_DE_FRONTMATTER
        )
    except StopIteration:
        return set()

    declarados: set[str] = set()
    dentro_do_cria = False
    for linha in linhas[1:fim]:
        sem_comentario = _COMENTARIO_INLINE.sub("", linha)
        if not sem_comentario.strip() or sem_comentario.lstrip().startswith("#"):
            continue
        if not sem_comentario[0].isspace():
            chave = _CHAVE_DE_TOPO.match(sem_comentario)
            dentro_do_cria = chave is not None and chave.group(1) == _CHAVE_DO_CRIA
            if dentro_do_cria and chave is not None:
                for caminho in _caminhos_do_valor(chave.group(2)):
                    declarados |= _sufixos_de(caminho)
            continue
        if not dentro_do_cria:
            continue
        item = _ITEM_DE_LISTA.match(sem_comentario)
        if item:
            for caminho in _caminhos_do_valor(item.group(1)):
                declarados |= _sufixos_de(caminho)
    return declarados


def tokens_isentos_por_nota(conteudo: str) -> set[str]:
    """Tokens citados a partir de um cabeçalho "Nota de verificação"."""
    linhas = conteudo.splitlines()
    inicio: int | None = None
    for indice, linha in enumerate(linhas):
        if _NOTA_DE_VERIFICACAO.match(linha):
            inicio = indice
            break
    if inicio is None:
        return set()

    isentos: set[str] = set()
    for linha in linhas[inicio:]:
        for bruto in _CRASE.findall(linha):
            isentos.update(_ENV.findall(bruto))
            texto = bruto.strip()
            if _METODO.fullmatch(texto):
                isentos.add(texto)
    return isentos


def envs_da_linha(linha: str) -> list[str]:
    """Variáveis `HEFESTO_*` citadas entre crases nesta linha."""
    achados: list[str] = []
    for bruto in _CRASE.findall(linha):
        achados.extend(_ENV.findall(bruto))
    return achados


def metodos_da_linha(linha: str, espacos_de_nomes: frozenset[str]) -> list[str]:
    """Tokens `a.b`/`a.b.c` entre crases cujo primeiro segmento é do IPC."""
    achados: list[str] = []
    for bruto in _CRASE.findall(linha):
        texto = bruto.strip()
        if not _METODO.fullmatch(texto):
            continue
        segmentos = texto.split(".")
        if segmentos[0] not in espacos_de_nomes:
            continue
        if segmentos[-1] in SUFIXOS_DE_ARQUIVO:
            continue
        achados.append(texto)
    return achados


def candidatos_da_linha(linha: str) -> list[tuple[str, bool]]:
    """Extrai da linha os textos com cara de caminho de arquivo."""
    brutos = [(m.group(1), True) for m in _CRASE.finditer(linha)]
    brutos += [(m.group(1), False) for m in _LINK.finditer(linha)]

    limpos: list[tuple[str, bool]] = []
    for bruto, veio_de_crase in brutos:
        texto = bruto.strip()
        if not texto or " " in texto:
            continue
        if texto.startswith(("http://", "https://", "mailto:", "#")):
            continue
        texto = texto.split(":", 1)[0].split("#", 1)[0]
        if texto.startswith("./"):
            texto = texto[2:]
        if not texto:
            continue
        if texto[0] in "/~$":
            continue
        if any(ruim in texto for ruim in ("*", "?", "<", ">", "{", "}")):
            continue
        if ".." in _SUBIDA.sub("", texto, count=1):
            continue
        if not _TOKEN_LIMPO.fullmatch(texto):
            continue
        extensao = Path(texto).suffix
        if extensao not in EXTENSOES:
            continue
        if veio_de_crase and "/" not in texto and extensao not in EXTENSOES_NOME_SOLTO:
            continue
        if any(p in texto for p in EXTERNOS_POR_PASTA):
            continue
        if Path(texto).name in EXTERNOS:
            continue
        if aposentado(texto) is not None:
            continue
        if fora_do_git(texto) is not None:
            continue
        limpos.append((texto, veio_de_crase))
    return limpos


def varrer_documento(
    caminho: Path,
    raiz: Path,
    sufixos: set[str],
    envs: set[str] | None = None,
    metodos_ipc: set[str] | None = None,
    raiz_nomes: set[str] | None = None,
) -> list[Achado]:
    """Devolve as referências mortas de um documento -- as três regras."""
    if raiz_nomes is None:
        raiz_nomes = nomes_de_raiz(raiz)
    try:
        conteudo = caminho.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    relativo_doc = caminho.resolve().relative_to(raiz).as_posix()
    ensina = relativo_doc.startswith(PREFIXOS_QUE_ENSINAM)
    cobra_env = ensina and bool(envs)
    cobra_ipc = ensina and bool(metodos_ipc)
    espacos_de_nomes = frozenset(
        m.split(".")[0] for m in (metodos_ipc or set()) if "." in m
    )
    isentos_por_nota = (
        tokens_isentos_por_nota(conteudo) if (cobra_env or cobra_ipc) else set()
    )
    declarados_aqui = declarados_no_cria(conteudo)

    achados: list[Achado] = []
    dentro_de_cerca = False

    for numero, linha in enumerate(conteudo.splitlines(), start=1):
        if _CERCA.match(linha):
            dentro_de_cerca = not dentro_de_cerca
            continue
        if dentro_de_cerca:
            continue
        if MARCADOR_ISENCAO in linha:
            continue

        for referencia, veio_de_crase in candidatos_da_linha(linha):
            vizinho = (caminho.parent / referencia).resolve()
            try:
                relativo = vizinho.relative_to(raiz).as_posix()
            except ValueError:
                relativo = None
            if relativo is not None and (
                relativo in sufixos or relativo in declarados_aqui
            ):
                continue
            leniente = "/" in referencia or veio_de_crase or referencia in raiz_nomes
            if leniente and (referencia in sufixos or referencia in declarados_aqui):
                continue
            if relativo is not None and fora_do_git(relativo) is not None:
                continue
            achados.append(Achado(relativo_doc, numero, referencia, REGRA_ARQUIVO))

        if cobra_env:
            for variavel in envs_da_linha(linha):
                if variavel in envs or variavel in isentos_por_nota:
                    continue
                achados.append(Achado(relativo_doc, numero, variavel, REGRA_ENV))

        if cobra_ipc:
            for metodo in metodos_da_linha(linha, espacos_de_nomes):
                if metodo in metodos_ipc or metodo in isentos_por_nota:
                    continue
                achados.append(Achado(relativo_doc, numero, metodo, REGRA_IPC))

    return achados


def documentos_de(raiz: Path) -> list[Path]:
    """Todos os .md sob docs/ menos o arquivo morto, mais o `README.md`."""
    encontrados = []
    readme = raiz / "README.md"
    if readme.is_file():
        encontrados.append(readme)

    pasta = raiz / "docs"
    if not pasta.is_dir():
        return encontrados
    for md in sorted(pasta.rglob("*.md")):
        relativo = md.relative_to(raiz).as_posix()
        if relativo.startswith(PREFIXOS_IGNORADOS):
            continue
        encontrados.append(md)
    return encontrados


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Reprova documento que cita arquivo inexistente."
    )
    parser.add_argument("arquivos", nargs="*", type=Path, help="documentos a varrer")
    parser.add_argument("--all", action="store_true", help="varre docs/ inteiro")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="raiz do repositório (padrão: a deste script)",
    )
    args = parser.parse_args(argv)

    raiz = args.root.resolve()
    if not raiz.is_dir():
        print(f"ERRO: raiz inexistente: {raiz}")
        return 2

    if args.all:
        alvos = documentos_de(raiz)
    else:
        alvos = [p for p in args.arquivos if p.suffix == ".md" and p.is_file()]
    if not alvos:
        print("Nenhum documento para varrer.")
        return 0

    ressuscitados = conferir_aposentados(raiz)
    if ressuscitados:
        for problema in ressuscitados:
            print(problema)
        print("")
        print(f"{len(ressuscitados)} arquivo(s) declarado(s) em `APOSENTADOS` "
              "existem nesta árvore.")
        return 1

    rastreados = conferir_fora_do_git(raiz)
    if rastreados:
        for problema in rastreados:
            print(problema)
        print("")
        print(f"{len(rastreados)} prefixo(s) declarado(s) em `FORA_DO_GIT` "
              "voltaram a ser rastreados.")
        return 1

    sufixos = indexar(raiz)
    raiz_nomes = nomes_de_raiz(raiz)
    envs = indexar_envs(raiz)
    metodos_ipc = indexar_metodos_ipc(raiz)
    achados: list[Achado] = []
    for alvo in alvos:
        achados.extend(
            varrer_documento(alvo, raiz, sufixos, envs, metodos_ipc, raiz_nomes)
        )

    if achados:
        print(f"{len(achados)} referência(s) morta(s) em {len(alvos)} documento(s):")
        for achado in achados:
            print(str(achado))
        print("")
        print("Cada linha acima cita um arquivo, uma variável de ambiente ou um")
        print("método de IPC que NÃO existe nesta árvore. Corrija o nome, crie o")
        print("que falta, ou -- se a ausência for o assunto do parágrafo --")
        print("marque a linha com o comentário de isenção descrito no cabeçalho")
        print("deste script. Em ADR, a nota de verificação datada no fim do")
        print("arquivo já isenta o documento inteiro daquele nome.")
        return 1

    print(f"OK: {len(alvos)} documento(s) sem referência morta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
