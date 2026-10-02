"""O escape do portão de acentuação tem de prestar contas — todo escape NOVO."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[2]
VALIDADOR = RAIZ / "scripts" / "validar-acentuacao.py"

ESTE_ARQUIVO = "tests/unit/test_todo_escape_de_acento_presta_contas.py"

PISO_DE_ESCAPES = 140

SEM_RAZAO_PINADOS: dict[str, int] = {
    ".github/workflows/ci.yml": 2,
    "scripts/gerar-mapa.py": 2,
    "scripts/generate_glyph_active.py": 1,
    "scripts/install_osk.sh": 2,
    "src/hefesto_dualsense4unix/broker/hidraw_broker.py": 3,
    "src/hefesto_dualsense4unix/cli/cmd_profile.py": 2,
    "src/hefesto_dualsense4unix/integrations/ordens_da_mesa.py": 2,
    "src/hefesto_dualsense4unix/profiles/loader.py": 1,
    "src/hefesto_dualsense4unix/profiles/manager.py": 1,
    "src/hefesto_dualsense4unix/profiles/sanidade.py": 1,
    "tests/unit/test_cli_profile_historico.py": 3,
    "tests/unit/test_hidraw_broker_open_fd.py": 1,
    "tests/unit/test_ipc_server.py": 1,
    "tests/unit/test_modo01_o_modo_jogo_liga_sozinho.py": 1,
    "tests/unit/test_o_gesto_da_ponte_e_universal.py": 2,
    "tests/unit/test_o_preset_nao_escolhe_a_mascara.py": 2,
    "tests/unit/test_profile_manager.py": 2,
    "tests/unit/test_state_full_game_signal.py": 1,
    "tests/unit/test_validar_acentuacao_multiplos_arquivos.py": 2,
}

#: `# (noqa-acento)` não deixe um `)` órfão contando como razão.
_MARCA = re.compile(r"\(?noqa-acento\)?|\(?noqa:\s*acentuacao\)?")

_ABRE_ANOTACAO = ("<!--", "/*", "#", "//")

_SO_DELIMITADOR = ("<!--", "-->", "/*", "*/", "#", "//")


def _carrega_validador() -> ModuleType:
    """O validador é um script com hífen no nome: `import` não o alcança."""
    spec = importlib.util.spec_from_file_location("_validador_acento", VALIDADOR)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tem_razao(linha: str) -> bool:
    """True se a marca vem acompanhada de razão NA MESMA ANOTAÇÃO."""
    m = _MARCA.search(linha)
    if m is None:
        return False
    inicio = 0
    for delim in _ABRE_ANOTACAO:
        pos = linha.rfind(delim, 0, m.start() + 1)
        inicio = max(inicio, pos)
    trecho = linha[inicio : m.start()] + " " + linha[m.end() :]
    for delim in _SO_DELIMITADOR:
        trecho = trecho.replace(delim, " ")
    return bool(re.findall(r"[0-9A-Za-zÀ-ÿ]{2,}", trecho))


def escapes() -> tuple[list[tuple[str, int, str]], list[tuple[str, int, str]]]:
    """Todos os escapes do repo, separados em (com razão, sem razão)."""
    val = _carrega_validador()
    com: list[tuple[str, int, str]] = []
    sem: list[tuple[str, int, str]] = []
    for arq in val.listar_arquivos_git(RAIZ):
        rel = str(arq.resolve().relative_to(RAIZ))
        if val.is_whitelisted(rel) or rel == ESTE_ARQUIVO:
            continue
        try:
            linhas = arq.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for n, linha in enumerate(linhas, 1):
            if _MARCA.search(linha):
                alvo = com if tem_razao(linha) else sem
                alvo.append((rel, n, linha.strip()[:120]))
    return com, sem


def _por_arquivo(achados: list[tuple[str, int, str]]) -> dict[str, int]:
    contas: dict[str, int] = {}
    for rel, _n, _t in achados:
        contas[rel] = contas.get(rel, 0) + 1
    return contas


def test_o_varredor_de_escapes_nao_ficou_cego() -> None:
    """Um leitor que devolve zero faz os testes abaixo passarem por vacuidade."""
    com, sem = escapes()
    total = len(com) + len(sem)
    assert total >= PISO_DE_ESCAPES, (
        f"achei {total} escapes de acentuação no repositório, piso "
        f"{PISO_DE_ESCAPES}.\n"
        "Se eles sumiram de propósito, baixe o piso no mesmo commit. Se não "
        "sumiram, o varredor deste arquivo quebrou — e um varredor que lê zero "
        "aprova qualquer coisa."
    )


def test_nenhum_escape_novo_sem_razao() -> None:
    _com, sem = escapes()
    atual = _por_arquivo(sem)

    novos: list[str] = []
    for rel, quantos in sorted(atual.items()):
        pinado = SEM_RAZAO_PINADOS.get(rel, 0)
        if quantos > pinado:
            linhas = [f"{r}:{n}" for r, n, _t in sem if r == rel]
            novos.append(
                f"  {rel}: {quantos} mudo(s), pinado {pinado} — {linhas}"
            )

    assert not novos, (
        "escape de acentuação SEM RAZÃO, e ele é novo:\n"
        + "\n".join(novos)
        + "\n\nEscreva por que a palavra está certa sem acento, na MESMA linha "
        "da marca — antes ou depois dela:\n"
        '    manager.delete("acao")  # slug literal ASCII (noqa-acento)\n'
        '    <div data-v="acao">     # (noqa-acento): endereço\n'
        "\nA marca vai NA linha da palavra: o escape é por linha, e escrito na "
        "linha de baixo ele não alcança nada.\n"
        "Se o escape não tem razão que se escreva, ele não é escape: é um erro "
        "de acentuação, e o conserto é o acento."
    )


def test_a_lista_de_escapes_mudos_so_encolhe() -> None:
    """`atual <= pinado`, no total. Encolher passa; crescer reprova."""
    _com, sem = escapes()
    teto = sum(SEM_RAZAO_PINADOS.values())
    assert len(sem) <= teto, (
        f"{len(sem)} escapes mudos contra um teto de {teto}. A lista "
        "`SEM_RAZAO_PINADOS` é dívida do dia em que este arquivo nasceu, e ela "
        "só encolhe."
    )


def test_a_lista_pinada_esta_em_dia_com_o_que_existe() -> None:
    """O outro lado da catraca: número pinado ACIMA do real também reprova."""
    _com, sem = escapes()
    atual = _por_arquivo(sem)
    sobrando = sorted(
        (rel, pinado, atual.get(rel, 0))
        for rel, pinado in SEM_RAZAO_PINADOS.items()
        if pinado > atual.get(rel, 0)
    )
    assert not sobrando, (
        "`SEM_RAZAO_PINADOS` promete mais escape mudo do que existe:\n"
        + "\n".join(
            f"  {rel}: pinado {pinado}, real {real}"
            + ("  (apague a linha)" if real == 0 else f"  (baixe para {real})")
            for rel, pinado, real in sobrando
        )
        + "\n\nA lista só encolhe, e encolher se ESCREVE: um número inflado é "
        "uma licença em branco para o próximo escape mudo."
    )


def test_tem_razao_reconhece_as_duas_formas_da_casa() -> None:
    marca = "noqa" + "-acento"
    com_razao = [
        f'manager.delete("x")  # slug literal ASCII ({marca})',
        f"<div>  # ({marca}): endereço",
        f"# comentário  # ({marca}: verbo medir, imperfeito)",
        f"<!-- {marca}: pretérito imperfeito de MEDIR -->",
        f"    /* {marca}: palavra-chave do CSS */",
        f'casa="x"  # ({marca}) variável',
    ]
    sem_razao = [
        f"print('x')  # {marca}",
        f"algo()  # ({marca})",
        f"> uma citação literal dela <!-- {marca} -->",
        f"@media (max-width: 640px) {{   /* {marca} */",
        "assert x  # noqa: acentuacao",
    ]
    for linha in com_razao:
        assert tem_razao(linha), f"devia ter razão: {linha!r}"
    for linha in sem_razao:
        assert not tem_razao(linha), f"NÃO devia ter razão: {linha!r}"


def test_a_razao_da_anotacao_vizinha_nao_conta() -> None:
    """Prosa de OUTRO comentário na mesma linha não é razão do escape."""
    marca = "noqa" + "-acento"
    exemplo = "# o glade não os referencia"  # (noqa-acento: verbo referenciar)
    assert not tem_razao(f"{exemplo}  # ({marca})")
    assert tem_razao(f"{exemplo}  # ({marca}: verbo, não substantivo)")
