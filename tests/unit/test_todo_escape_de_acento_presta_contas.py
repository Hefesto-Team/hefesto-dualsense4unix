"""O escape do portão de acentuação tem de prestar contas — todo escape NOVO.

Nasceu em 31/08/2026. O portão `acentuacao` tem uma válvula por linha: qualquer
linha que contenha ``noqa-acento`` (ou ``noqa: acentuacao``) sai da varredura
inteira. A válvula é NECESSÁRIA — há palavra que o dicionário do validador
acusa e que está CERTA sem acento. As quatro classes desta casa:

- *media*, pretérito imperfeito de MEDIR  (noqa-acento: é o exemplo)
- *referencia*, verbo referenciar  (noqa-acento: é o exemplo)
- *acao*, *nao*: slug de arquivo e valor de chave  (noqa-acento: é o exemplo)
- `@media` do CSS, que é palavra-chave de outra linguagem.

O QUE ELA NÃO PODE VIRAR
------------------------
Paisagem. Medido nesta árvore em 31/08/2026: dos 170 escapes do repositório,
**60 não diziam por quê**. Um escape mudo é indistinguível de um erro de
acentuação que alguém calou para o portão ficar verde — e quem lê depois não
tem como saber qual dos dois é, a não ser refazendo a análise inteira.

É a mesma doença que o ``SERVE_UM_LADO_SO`` de
``test_install_serve_os_dois_lados_da_cerca.py`` existe para impedir: lá a
exceção à cerca do install é um dicionário cujo VALOR é a razão, com data;
aqui a exceção ao portão de acento é uma linha cuja razão vem escrita ao lado
da marca.

A REGRA, e ela é de uma linha só
--------------------------------
A razão tem de morar NA MESMA ANOTAÇÃO da marca. Vale antes ou depois dela —
as duas formas já são uso desta casa::

    manager.delete("acao")  # slug literal ASCII (noqa-acento)   <- razão ANTES
    <div data-v="acao">     # (noqa-acento): endereço            <- razão DEPOIS

O que NÃO vale é a marca sozinha (``# (noqa-acento)``, ``<!-- noqa-acento -->``),
porque ela não diz nada a ninguém.

A LISTA PINADA SÓ ENCOLHE
-------------------------
Os 60 mudos de hoje ficam em ``SEM_RAZAO_PINADOS``, por arquivo. Escape novo
sem razão reprova — num arquivo pinado, porque a conta cresce; num arquivo
fora da lista, porque ele não está lá. Curar um escape mudo faz a conta
encolher, e encolher PASSA: a régua é ``atual <= pinado``, nunca igualdade.

O QUE ESTA RÉGUA NÃO ALCANÇA, e está escrito de propósito
---------------------------------------------------------
O escape é POR LINHA, então um erro de acentuação REAL que caia na MESMA linha
de um ``noqa-acento`` legítimo passa pelos dois portões: pelo de acentuação,
porque a linha inteira é pulada; e por este, porque a marca dele TEM razão.
Este é o custo conhecido da válvula por linha, não um defeito desta régua —
consertá-lo pediria um escape por PALAVRA, e não por linha, no
``validar-acentuacao.py``. Fica medido e escrito; ver a mordida M6 do relatório
de 31/08/2026.

E o defeito irmão, que é o mais fácil de cometer: escrever a razão na linha
DE BAIXO do achado. Aconteceu em 31/08 no
``test_as_abas_vivas_falam_com_o_daemon_certo.py`` — a marca estava um degrau
abaixo da palavra e não alcançava nada. A marca vai NA linha da palavra.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[2]
VALIDADOR = RAIZ / "scripts" / "validar-acentuacao.py"

#: Este arquivo fala SOBRE a marca, então ele a escreve dezenas de vezes. Sem
#: esta exclusão a régua contaria os próprios exemplos como dívida — e cresceria
#: sozinha a cada linha de documentação que alguém acrescentasse aqui.
ESTE_ARQUIVO = "tests/unit/test_todo_escape_de_acento_presta_contas.py"

#: Quantos escapes (com razão + sem razão) o repositório tinha quando esta
#: guarda nasceu. Trava contra varredor quebrado, não meta: um leitor que
#: devolve zero linhas deixa TODOS os testes abaixo passarem por vacuidade, que
#: é o pior estado possível para um portão. Ver `PISO_DE_FUNCOES` no
#: `test_install_serve_os_dois_lados_da_cerca.py`, que nasceu do mesmo medo.
PISO_DE_ESCAPES = 140

#: Os escapes MUDOS de 31/08/2026, por arquivo. Chave é o caminho relativo;
#: valor é quantos aquele arquivo tinha no dia. **Esta lista só encolhe.**
#: Para tirar um daqui: escreva a razão ao lado da marca e baixe o número no
#: MESMO commit.
SEM_RAZAO_PINADOS: dict[str, int] = {
    ".github/workflows/ci.yml": 2,
    "docs/process/estudos/2026-08-06-o-que-so-funciona-na-maquina-dela.md": 2,
    "docs/process/estudos/2026-08-07-O-QUE-EXISTE-E-NAO-CHEGA-a-cobertura-do-install.md": 3,
    "docs/process/estudos/2026-08-07-a-economia-de-energia-e-a-bancada.md": 1,
    "docs/process/sprints/2026-08-06-REGRA-NAO-REGISTRO-01-o-8bitdo-e-um-so-e-o-defeito-e-de-todo-mundo.md": 2,  # noqa: E501
    "docs/process/sprints/2026-08-07-CONTROLE-INTEIRO-NO-RADIO-01-o-mic-e-o-fone-que-nao-atravessam.md": 2,  # noqa: E501
    "docs/process/sprints/2026-08-07-INSTALL-QUE-NAO-CARREGA-01-as-descobertas-que-nunca-viraram-codigo.md": 1,  # noqa: E501
    "docs/process/sprints/2026-08-16-A-MASCARA-QUE-O-PRODUTO-ESCOLHE-01-o-jogo-nao-enxerga-e-a-culpa-nao-e-da-pessoa.md": 1,  # noqa: E501
    "docs/process/sprints/2026-08-16-SENTINELA-WRAPPER-01-a-steam-guarda-uma-linha-por-jogo-e-comeu-a-nossa.md": 1,  # noqa: E501
    "docs/process/sprints/2026-08-24-INFRA-DE-EXECUCAO-01-o-registro-do-que-esta-em-voo.md": 2,
    "scripts/gerar-indice-html.py": 1,
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
    # test_coop_default_on_migration.py saiu em 03/09/2026: o escape mudo que ele
    # tinha não existe mais no arquivo, e a régua da IGUALDADE cobra a linha de
    # volta — número pinado acima do real é licença em branco para o próximo.
    "tests/unit/test_hidraw_broker_open_fd.py": 1,
    "tests/unit/test_ipc_server.py": 1,
    "tests/unit/test_modo01_o_modo_jogo_liga_sozinho.py": 1,
    "tests/unit/test_o_gesto_da_ponte_e_universal.py": 2,
    "tests/unit/test_o_preset_nao_escolhe_a_mascara.py": 2,
    "tests/unit/test_profile_manager.py": 2,
    "tests/unit/test_state_full_game_signal.py": 1,
    "tests/unit/test_validar_acentuacao_fstring.py": 9,
    "tests/unit/test_validar_acentuacao_multiplos_arquivos.py": 2,
}

#: A marca, nas duas grafias que o `validar-acentuacao.py` honra (ver
#: `checar_arquivo`). Os parênteses opcionais entram no casamento para que
#: `# (noqa-acento)` não deixe um `)` órfão contando como razão.
_MARCA = re.compile(r"\(?noqa-acento\)?|\(?noqa:\s*acentuacao\)?")

#: Onde uma anotação começa, em cada linguagem que este repositório escreve.
_ABRE_ANOTACAO = ("<!--", "/*", "#", "//")

#: Delimitadores que não são razão nenhuma — só fecham o comentário.
_SO_DELIMITADOR = ("<!--", "-->", "/*", "*/", "#", "//")


def _carrega_validador() -> ModuleType:
    """O validador é um script com hífen no nome: `import` não o alcança.

    Ele é a fonte de QUAIS arquivos existem (`listar_arquivos_git`) e de quais
    são isentos (`is_whitelisted`). Reimplementar isso aqui criaria uma segunda
    lista de arquivos, e duas listas divergem — foi assim que o `portoes.sh`
    nasceu, em 25/08/2026.
    """
    spec = importlib.util.spec_from_file_location("_validador_acento", VALIDADOR)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tem_razao(linha: str) -> bool:
    """True se a marca vem acompanhada de razão NA MESMA ANOTAÇÃO.

    A anotação é o comentário que contém a marca — do último abridor
    (``#``, ``/*``, ``<!--``, ``//``) antes dela até o fim da linha. Fora dela
    a prosa é CONTEÚDO, não justificativa: numa linha como
    ``# o glade não os referencia  # (noqa-acento)`` o texto da esquerda explica
    o código, e não por que o escape existe.

    Linha sem abridor nenhum (prosa de docstring, célula de `.csv`) usa a linha
    inteira — ali não há como separar anotação de conteúdo, e a régua prefere
    ABSOLVER a acusar falso.
    """
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
        # Arquivo isento do portão não tem escape a prestar contas: a marca ali
        # não desliga nada, porque nada estava ligado.
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


# ---------------------------------------------------------------------------
# 0. A TRAVA DO PRÓPRIO VARREDOR
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# 1. TODO ESCAPE NOVO EXIGE RAZÃO
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# 2. A LISTA SÓ ENCOLHE
# ---------------------------------------------------------------------------
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
    """O outro lado da catraca: número pinado ACIMA do real também reprova.

    Sem esta metade a catraca é decorativa — bastaria inflar um número
    (``"x.py": 1`` virando ``"x.py": 9``) para o teto subir e oito escapes mudos
    novos entrarem sem ninguém ver. E arquivo curado que fica na lista vira lixo
    acumulado, autorizando um escape mudo FUTURO naquele caminho.

    Por isso a régua é IGUALDADE por arquivo, nas duas direções. Curou um
    escape? Baixe o número no mesmo commit. Curou o último? Apague a linha.
    """
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


# ---------------------------------------------------------------------------
# 3. A RÉGUA DA RÉGUA — `tem_razao` medida contra casos escritos à mão
# ---------------------------------------------------------------------------
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
    """Prosa de OUTRO comentário na mesma linha não é razão do escape.

    `# o glade não os referencia  # (noqa-acento)` — a esquerda explica o  (noqa-acento: verbo)
    código, não a válvula. Se contasse, bastaria haver qualquer comentário na
    linha para o escape virar mudo com aparência de justificado.
    """
    marca = "noqa" + "-acento"
    exemplo = "# o glade não os referencia"  # (noqa-acento: verbo referenciar)
    assert not tem_razao(f"{exemplo}  # ({marca})")
    assert tem_razao(f"{exemplo}  # ({marca}: verbo, não substantivo)")
