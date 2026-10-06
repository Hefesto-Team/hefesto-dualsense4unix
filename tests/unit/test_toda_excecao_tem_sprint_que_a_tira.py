"""Toda exceção tem dona (VERDE-NAO-E-PROVA-01, passo 2)."""
from __future__ import annotations

import ast
import io
import re
import subprocess
import tokenize
from dataclasses import dataclass
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SPRINTS = RAIZ / "docs" / "process" / "sprints"
ESTE = "tests/unit/test_toda_excecao_tem_sprint_que_a_tira.py"

RAIZES = re.compile(
    r"ISENT|ISENC|EXCEC|ACEIT|PODEM|TOLERAD|DIVIDA|PENDENT|(?<!DES)CONHECID"
    r"|PERMITID|SEM_DONO|SEM_MAO|SEM_CAMINHO|APOSENTAD|FORA_DO|_HOJE\b|^HOJE"
    r"|IGNORAD|LIBERAD|PERDOAD|DISPENS"
)
_ATRIBUICAO = re.compile(r"^(_?[A-Z][A-Z0-9_]*)\s*(?::[^=\n]*)?=", re.M)
_MARCA = re.compile(r"#:?\s*(sai com|fica):\s*(\S.*)$")
_ID = re.compile(r"[A-Z0-9][A-Z0-9-]*[A-Z0-9]")
_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
ESTADOS_VIVOS = frozenset({"aberta", "espera-ela"})
_RECIPIENTES = frozenset({"frozenset", "set", "tuple", "list", "dict"})
_NAO_E_RECIPIENTE = object()


@dataclass(frozen=True)
class Lista:
    """Uma lista achada pelo censo, com o endereço de cada entrada."""

    arquivo: str
    nome: str
    linha: int
    entradas: tuple[tuple[int, int], ...] | None
    marcas: tuple[tuple[int, str, str], ...]
    acima: frozenset[int]

    @property
    def chave(self) -> str:
        return f"{self.arquivo}::{self.nome}"


def _entradas(valor: ast.expr | None) -> object:
    if isinstance(valor, ast.Dict):
        return tuple(((k or v).lineno, v.end_lineno or v.lineno)
                     for k, v in zip(valor.keys, valor.values, strict=True))
    if isinstance(valor, (ast.List, ast.Tuple, ast.Set)):
        return tuple((e.lineno, e.end_lineno or e.lineno) for e in valor.elts)
    if (isinstance(valor, ast.Call) and isinstance(valor.func, ast.Name)
            and valor.func.id in _RECIPIENTES):
        return _entradas(valor.args[0]) if valor.args else ()
    if isinstance(valor, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return None
    return _NAO_E_RECIPIENTE


def _marcas(texto: str) -> tuple[tuple[int, str, str], ...]:
    achadas = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(texto).readline):
            if tok.type == tokenize.COMMENT and (m := _MARCA.search(tok.string)):
                achadas.append((tok.start[0], m.group(1), m.group(2).strip()))
    except (tokenize.TokenError, SyntaxError):
        pass
    return tuple(achadas)


def listas_do_arquivo(raiz: Path, relativo: str) -> list[Lista]:
    """As listas de exceção de UM arquivo, pelo nome."""
    texto = (raiz / relativo).read_text(encoding="utf-8")
    if not any(RAIZES.search(nome) for nome in _ATRIBUICAO.findall(texto)):
        return []
    try:
        arvore = ast.parse(texto)
    except SyntaxError:
        return []
    linhas = texto.splitlines()
    marcas = _marcas(texto)
    achadas = []
    for no in arvore.body:
        if isinstance(no, ast.Assign):
            nomes = [a.id for a in no.targets if isinstance(a, ast.Name)]
        elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
            nomes = [no.target.id]
        else:
            continue
        entradas = _entradas(no.value)
        if entradas is _NAO_E_RECIPIENTE:
            continue
        k = no.lineno - 1
        while k > 0 and linhas[k - 1].lstrip().startswith("#"):
            k -= 1
        for nome in nomes:
            if nome == nome.upper() and RAIZES.search(nome):
                achadas.append(Lista(relativo, nome, no.lineno, entradas,  # type: ignore[arg-type]
                                     marcas, frozenset(range(k + 1, no.lineno))))
    return achadas


def _versionados(raiz: Path) -> list[str]:
    feito = subprocess.run(["git", "-C", str(raiz), "ls-files", "--", "tests", "scripts"],
                           capture_output=True, text=True, timeout=60, check=False)
    return sorted(r for r in feito.stdout.split("\n") if r.endswith(".py") and r != ESTE)


def censo(raiz: Path = RAIZ, arquivos: list[str] | None = None) -> dict[str, Lista]:
    """Toda lista de exceção dos arquivos versionados de `tests/` e `scripts/`."""
    achadas: dict[str, Lista] = {}
    for relativo in _versionados(raiz) if arquivos is None else arquivos:
        for lista in listas_do_arquivo(raiz, relativo):
            achadas[lista.chave] = lista
    return achadas


def dona(lista: Lista, ini: int, fim: int) -> tuple[str, str] | None:
    """A marca que vale para a entrada `[ini, fim]`, ou `None`."""
    spans = lista.entradas or ()
    propria = [(t, r) for n, t, r in lista.marcas if ini <= n <= fim]
    if propria:
        return propria[0]
    soltas = [(n, t, r) for n, t, r in lista.marcas
              if lista.linha <= n < ini and not any(a <= n <= b for a, b in spans)]
    if soltas:
        return max(soltas)[1:]
    acima = [(n, t, r) for n, t, r in lista.marcas if n in lista.acima]
    return max(acima)[1:] if acima else None


def entradas_sem_dona(lista: Lista) -> list[str]:
    """As entradas de uma lista de dívida que não dizem quem as tira."""
    faltas = []
    for ini, fim in lista.entradas or ():
        marca = dona(lista, ini, fim)
        if marca is None:
            faltas.append(f"{lista.arquivo}:{ini}: entrada de `{lista.nome}` sem `sai com:` "
                          "nem `fica:`")
        elif marca[0] == "sai com" and not _ID.match(marca[1]):
            faltas.append(f"{lista.arquivo}:{ini}: `sai com:` sem o nome da sprint")
        elif marca[0] == "fica" and len(marca[1]) < 20:
            faltas.append(f"{lista.arquivo}:{ini}: `fica:` sem a razão ({marca[1]!r})")
    return faltas


def sprints_citadas(lista: Lista) -> set[str]:
    citadas = set()
    for ini, fim in lista.entradas or ():
        marca = dona(lista, ini, fim)
        if marca and marca[0] == "sai com" and (m := _ID.match(marca[1])):
            citadas.add(m.group(0))
    return citadas


def estados_das_sprints(pasta: Path = SPRINTS) -> dict[str, str]:
    """`sprint -> estado`, do frontmatter; a pasta viva vence `arquivados/`."""
    estados: dict[str, str] = {}
    for arquivo in sorted(pasta.rglob("*.md"), key=lambda p: "arquivados" not in p.parts):
        m = _FRONTMATTER.match(arquivo.read_text(encoding="utf-8", errors="replace"))
        if not m:
            continue
        campos = dict(re.findall(r"^(sprint|estado):\s*(\S+)", m.group(1), re.M))
        if "sprint" in campos:
            estados[campos["sprint"]] = campos.get("estado", "aberta")
    return estados


def sprints_fechadas(citadas: dict[str, set[str]], estados: dict[str, str]) -> list[str]:
    """As entradas que apontam para sprint que não existe ou que não tem mais trabalho."""
    faltas = []
    for chave, ids in sorted(citadas.items()):
        for sprint in sorted(ids):
            estado = estados.get(sprint)
            if estado is None:
                faltas.append(f"{chave}: `sai com: {sprint}`, e essa sprint não existe")
            elif estado not in ESTADOS_VIVOS:
                faltas.append(f"{chave}: `sai com: {sprint}`, que está `{estado}` — a "
                              "entrada ficou depois da sprint que a tirava")
    return faltas


def catraca(achadas: dict[str, Lista], dividas: dict[str, int]) -> list[str]:
    faltas = []
    for chave, tamanho in sorted(dividas.items()):
        lista = achadas.get(chave)
        if lista is None or lista.entradas is None:
            continue
        hoje = len(lista.entradas)
        if hoje > tamanho:
            faltas.append(f"{chave} cresceu de {tamanho} para {hoje}: a entrada nova diz "
                          "a sprint que a tira, e a catraca sobe aqui, no mesmo commit")
        elif hoje < tamanho:
            faltas.append(f"{chave} encolheu de {tamanho} para {hoje}: baixe a catraca aqui")
    return faltas


DIVIDAS: dict[str, int] = {
    "scripts/check_a_cor_vem_do_aparelho.py::ISENCOES": 0,
    "scripts/check_a_maiuscula_decorativa.py::DIVIDA": 34,
    "scripts/check_a_tela_nao_confessa.py::A_DIVIDA": 4,
    "scripts/check_cabo_bt_perfil_controle.py::A_DIVIDA_CONHECIDA": 1,
    "scripts/check_identidade_vem_de_cima.py::ISENCOES": 0,
    "scripts/validar-citacoes-de-linha.py::CSV_FORA_DO_PORTAO": 0,
    "scripts/validar-palavra-de-tela.py::DIVIDA_DA_PALAVRA_01": 0,
    "scripts/validar-palavra-de-tela.py::DIVIDA_DA_PALAVRA_01_PY": 0,
    "scripts/validar-palavra-de-tela.py::DIVIDA_DO_RECIBO": 0,
    "tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py::_SEM_CAMINHO_HOJE": 2,
    "tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py::_SEM_MAO_HOJE": 0,
    "tests/unit/test_a_costura_da_onda_2.py::_OS_QUE_PODEM": 8,
    "tests/unit/test_a_janela_estreita_nao_engole_o_desenho.py::CORTE_CONHECIDO_NO_DESENHO": 0,
    "tests/unit/test_guarda_gi_falso_precisa_de_exigir_gi_real.py::DIVIDA_GI_FALSO": 0,
    "tests/unit/test_mic_volume_01_o_slider_que_faltava.py::_SEM_MIC_HOJE": 0,
    "tests/unit/test_o_pacote_cabe_na_pagina_publicada.py::EXCECOES_DATADAS": 0,
    "tests/unit/test_o_pacote_leva_os_alvos_das_regras_82_e_83.py::LACUNA_HOJE": 0,
    "tests/unit/test_os_donos_de_fato.py::EXCECOES_DATADAS": 4,
    "tests/unit/test_portao_o_par_com_metade_ligada.py::_CITACOES_PENDENTES": 0,
    "tests/unit/test_portao_o_par_com_metade_ligada.py::_PAR_ACEITO": 0,
    "tests/unit/test_portao_todo_portao_tem_chamador.py::_SEM_CHAMADOR_HOJE": 2,
    "tests/unit/test_toda_fala_declarada_chega_a_tela.py::_FALA_SEM_TELA_HOJE": 0,
    "tests/unit/test_todo_campo_do_caderno_tem_consumidor.py::ISENTOS": 0,
    "tests/unit/test_todo_texto_que_abre_uma_linha_comeca_com_maiuscula.py::PENDENTES": 1,
}

_A_PROPRIA_REGUA = "o próprio arquivo da régua, a cura ou a mordida: eles escrevem o que ela caça"
_DADO_DE_TESTE = "dado do teste (o que o desenho não tem, a resposta de mentira), não isenção"
_PASTAS_DE_MAQUINA = "pastas e binários de máquina (.git, venv, caches), que nenhuma régua lê"

NAO_SAO_DIVIDA: dict[str, str] = {
    "scripts/recibo_da_medida.py::_IGNORADOS_QUE_ENTRAM": (
        "as pastas ignoradas pelo git que a chave da memória dos portões lê (medido por strace: "
        "quatro portões abrem arquivos de scripts/ que o git não leva); "
        "entra na chave, não isenta nada"),
    "scripts/github/aplicar.py::DONOS_PERMITIDOS": (
        "os donos em que o aplicador aceita escrever (a organização e a conta de quem mantém): "
        "é a guarda contra escrever no repositório errado, não um caso isento"),
    "scripts/github/aplicar.py::EXCECOES": (
        "o nome do campo do repositorio.yml que declara quem passa pela porta do ruleset "
        "(a resposta dela de 06/10: os administradores passam), não uma isenção da régua"),
    "scripts/ensaios/quem_e_quem.py::CONHECIDOS": (
        "os endereços da mesa, lidos quando o ensaio roda, para o dono da máscara "
        "pegar toda forma deles; nasce vazia e não isenta nada"),
    "scripts/check_a_grafia_do_nome.py::ISENTOS": _A_PROPRIA_REGUA,
    "scripts/check_broadcast_proibido.py::_EXCECOES_DELIBERADAS": (
        "o broadcast deliberado, com a frase de verdade no docstring da função"),
    "scripts/check_faixa_sintetica.py::_ARVORE_IGNORADA": (
        "onde a faixa sintética é o próprio dado: fixture, documento e captura"),
    "scripts/check_nada_aponta_para_a_janela.py::_PASTAS_IGNORADAS": _PASTAS_DE_MAQUINA,
    "scripts/check_paridade_gtk_html.py::APOSENTADOS": (
        "os arquivos da janela GTK, aposentada por decisão dela (D-0609-GTK-LEVA-INTEIRA)"),
    "scripts/medir_decisoes_sem_prova.py::ESTADOS_CONHECIDOS": (
        "o vocabulário do campo `estado` do CSV das decisões"),
    "scripts/validar-glifos.py::EXCECOES_DELA": (
        "os quatro glifos que ela nomeou em 20/09/2026, um a um"),
    "scripts/validar-glifos.py::PADROES_IGNORADOS": _PASTAS_DE_MAQUINA,
    "scripts/validar-glifos.py::_IGNORADOS_RE": "a mesma lista de cima, compilada",
    "scripts/validar-referencias-docs.py::APOSENTADOS": (
        "arquivos apagados por decisão (GTK-3), citados como registro histórico"),
    "scripts/validar-referencias-docs.py::ARQUIVOS_FORA_DO_INDICE_DE_ENV": _A_PROPRIA_REGUA,
    "scripts/validar-referencias-docs.py::DIRS_IGNORADOS": _PASTAS_DE_MAQUINA,
    "scripts/validar-referencias-docs.py::FORA_DO_GIT": (
        "o `docs/process/`, fora do git por ordem dela de 15/09/2026"),
    "scripts/validar-referencias-docs.py::PREFIXOS_IGNORADOS": (
        "arquivo morto por definição (história, pesquisa) e o que saiu do git"),
    "tests/conftest.py::_EXCECOES_DO_FILHO": (
        "o vocabulário das exceções que o processo filho devolve ao pai"),
    "tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py::_MAO_FORA_DO_AMBIENTE": (
        "a mão de cada chave, declarada pelo nome e conferida pela própria régua"),
    "tests/unit/test_a_04_o_anel_do_dono_veste_o_aparelho.py::FORA_DO_DESENHO": _DADO_DE_TESTE,
    "tests/unit/test_a_aba05_publica_os_hexes_do_mapa.py::FORA_DO_DESENHO": _DADO_DE_TESTE,
    "tests/unit/test_a_aba_10_perfis_fecha_as_linhas.py::FORMAS_FORA_DO_DICIONARIO": (
        "o vocabulário das formas que `from_simple_choice` escreve fora do dicionário"),
    "tests/unit/test_a_fala_de_tela_alcanca_a_interface_nova.py::PISO_ATE_HOJE": (
        "o piso que só sobe, e não uma folga"),
    "tests/unit/test_a_fala_de_tela_alcanca_a_interface_nova.py::RAIZES_ATE_HOJE": (
        "as raízes de tela de hoje, um conjunto que só cresce"),
    "tests/unit/test_a_frase_que_ela_baniu_nao_chega_a_tela.py::ISENTOS_EM_COMENTARIO": (
        "a lápide em comentário, que não chega a tela nenhuma"),
    "tests/unit/test_a_frase_que_ela_baniu_nao_chega_a_tela.py::ISENTOS_INTEIROS": (
        "o dono da lista de frases banidas: os trechos são o dado"),
    "tests/unit/test_a_porta_que_a_casa_construiu_01.py::EXCECOES": (
        "arquivos que citam o nó e não o abrem, conferidos um a um"),
    "tests/unit/test_a_trava_do_jogo_aberto_tem_um_dono.py::ISENTOS": (
        "quem lê o sinal do jogo para o plano, e não para recriar o pad: cada linha diz por quê"),
    "tests/unit/test_aba02_a_borda_veste_o_controle_do_mapa.py::FORA_DO_DESENHO": _DADO_DE_TESTE,
    "tests/unit/test_abas_promovidas_so_crescem_p09.py::ABAS_PROMOVIDAS_ATE_HOJE": (
        "o conjunto de abas promovidas, que só cresce"),
    "tests/unit/test_guarda_gi_falso_precisa_de_exigir_gi_real.py::GUARDAS_ACEITAS": (
        "o vocabulário das duas guardas de GTK real"),
    "tests/unit/test_install_garante_deps_em_qualquer_familia.py::VAZIOS_ACEITOS": (
        "o pacote que não existe com esse nome na família: ausência decidida"),
    "tests/unit/test_mic_em_todo_formato_01.py::_MODOS_FORA_DO_MIC": (
        "o modo que não é decisão sobre o microfone (o nó que não dorme)"),
    "tests/unit/test_nativo_rumble_01_a_recusa_chega_na_tela.py::RESPOSTA_DE_ACEITE": (
        _DADO_DE_TESTE),
    "tests/unit/test_nenhum_arquivo_manda_rodar_install_com_sudo.py::DISPENSAS": _A_PROPRIA_REGUA,
    "tests/unit/test_o_binding_do_webkit_entra_no_install.py::VAZIOS_ACEITOS_NO_CENSO": (
        "o pacote que não existe com esse nome na família: ausência decidida"),
    "tests/unit/test_o_controle_que_conecta_e_nao_vira_controle.py::CONHECIDOS": _DADO_DE_TESTE,
    "tests/unit/test_o_flatpak_alcanca_o_broker.py::FORA_DO_SANDBOX": (
        "o broker é um serviço root do host e nunca roda no sandbox"),
    "tests/unit/test_os_portoes_declaram_o_que_importam.py::EXCECOES": (
        "o `gi` vem do pacote do sistema, e o install o garante no censo"),
    "tests/unit/test_paleta_unica.py::PERMITIDAS": (
        "as cores fora da paleta de propósito (alto contraste e os tingidos do hover)"),
    "tests/unit/test_paridade_quente_dos_instaladores.py::EXCECAO_INSTALL_SH": (
        "o quirk tem um dono só (`install_snd_quirk.sh`), e o install o chama"),
    ("tests/unit/test_portao_connected_nao_se_escreve_a_mao.py"
     "::_HANDLERS_QUE_PODEM_ESCREVER_CONNECTED"): (
        "os três handlers auditados, cada um com a derivação certa da sua fonte"),
    "tests/unit/test_release_workflow_nomes_e_portoes.py::PUBLICADORES_DE_HOJE": (
        "o piso dos publicadores que o detector tem de reconhecer"),
    "tests/unit/test_t07_a_frase_que_ela_derrubou_nao_volta.py::ARQUIVOS_ISENTOS": (
        "a nota datada que registra a morte da frase"),
    "tests/unit/test_todo_gesto_que_grava_esta_protegido.py::ISENTOS": (
        "gestos idempotentes, medidos por nome em 03/09/2026"),
}

PENDENTES: dict[str, tuple[str, str]] = {
    # 02/10/2026: o espelho dos `SEM_GESTO` da 06 e da 08 (a régua dos sem dono
    "tests/unit/test_cada_gesto_diz_de_quem_e.py::SEM_DONO_PERMITIDOS": (
        "A-NAVEGACAO-INTERNA-E-UM-MODO-QUE-SE-LIGA-EM-QUALQUER-ABA-01",
        "cinco das seis entradas esperam a sprint da onda da 08 para ganhar dona"),
}


@pytest.fixture(scope="module")
def achadas() -> dict[str, Lista]:
    return censo()


def test_toda_lista_achada_mora_numa_tabela(achadas: dict[str, Lista]) -> None:
    tabelas = [set(DIVIDAS), set(NAO_SAO_DIVIDA), set(PENDENTES)]
    for i, a in enumerate(tabelas):
        for b in tabelas[i + 1:]:
            assert not a & b, f"a mesma lista em duas tabelas: {sorted(a & b)}"
    soltas = sorted(set(achadas) - set().union(*tabelas))
    assert not soltas, (
        "lista de exceção nova, sem tabela: se é defeito aceito, vai para "
        "`DIVIDAS` com a dona de cada entrada; se não é, para `NAO_SAO_DIVIDA` "
        "com a razão:\n  " + "\n  ".join(soltas))


def test_toda_lista_das_tabelas_existe(achadas: dict[str, Lista]) -> None:
    mortas = sorted((set(DIVIDAS) | set(NAO_SAO_DIVIDA) | set(PENDENTES)) - set(achadas))
    assert not mortas, "declaração de lista que o censo não acha mais:\n  " + "\n  ".join(mortas)
    curtas = sorted(k for k, r in NAO_SAO_DIVIDA.items() if len(r) < 30)
    assert not curtas, f"`NAO_SAO_DIVIDA` sem a razão: {curtas}"


def test_toda_entrada_de_divida_diz_quem_a_tira(achadas: dict[str, Lista]) -> None:
    faltas = [f for chave in sorted(DIVIDAS) if chave in achadas
              for f in entradas_sem_dona(achadas[chave])]
    assert not faltas, "\n".join(faltas)


def test_a_catraca_das_dividas(achadas: dict[str, Lista]) -> None:
    faltas = catraca(achadas, DIVIDAS)
    assert not faltas, "\n".join(faltas)


@pytest.mark.insumo_fora_do_git("docs/process/sprints")
def test_a_sprint_que_tira_a_entrada_tem_trabalho(achadas: dict[str, Lista]) -> None:
    citadas = {chave: sprints_citadas(achadas[chave]) for chave in DIVIDAS if chave in achadas}
    for chave, (sprint, _razao) in PENDENTES.items():
        citadas.setdefault(chave, set()).add(sprint)
    faltas = sprints_fechadas(citadas, estados_das_sprints())
    assert not faltas, "\n".join(faltas)


_MODULO = '''\
#: sai com: A-SPRINT-DA-LISTA-01
DIVIDA_DE_MENTIRA = {
    "a": 1,
    # fica: esta entrada é o próprio dado da régua, não defeito
    "b": 2,
    "c": 3,  # sai com: OUTRA-SPRINT-01
}
ISENTOS_SEM_DONA = ("x", "y")
'''


def _mentira(tmp_path: Path, texto: str = _MODULO) -> dict[str, Lista]:
    (tmp_path / "scripts").mkdir(exist_ok=True)
    (tmp_path / "scripts" / "regua.py").write_text(texto, encoding="utf-8")
    return censo(tmp_path, ["scripts/regua.py"])


def test_a_mordida_a_marca_vale_para_o_grupo_e_a_propria_vence(tmp_path: Path) -> None:
    lista = _mentira(tmp_path)["scripts/regua.py::DIVIDA_DE_MENTIRA"]
    donas = [dona(lista, i, f) for i, f in lista.entradas or ()]
    assert donas == [("sai com", "A-SPRINT-DA-LISTA-01"),
                     ("fica", "esta entrada é o próprio dado da régua, não defeito"),
                     ("sai com", "OUTRA-SPRINT-01")]
    assert entradas_sem_dona(lista) == []


def test_a_mordida_entrada_sem_dona_reprova(tmp_path: Path) -> None:
    lista = _mentira(tmp_path)["scripts/regua.py::ISENTOS_SEM_DONA"]
    assert len(entradas_sem_dona(lista)) == 2


def test_a_mordida_lista_nova_fora_das_tabelas_e_achada(tmp_path: Path) -> None:
    achadas = _mentira(tmp_path)
    assert set(achadas) == {"scripts/regua.py::DIVIDA_DE_MENTIRA",
                            "scripts/regua.py::ISENTOS_SEM_DONA"}


def test_a_mordida_a_catraca_pega_o_que_cresce_e_o_que_encolhe(tmp_path: Path) -> None:
    achadas = _mentira(tmp_path)
    chave = "scripts/regua.py::DIVIDA_DE_MENTIRA"
    assert catraca(achadas, {chave: 3}) == []
    assert "cresceu" in catraca(achadas, {chave: 2})[0]
    assert "encolheu" in catraca(achadas, {chave: 4})[0]


def test_a_mordida_sprint_fechada_ou_inexistente_reprova(tmp_path: Path) -> None:
    pasta = tmp_path / "sprints"
    (pasta / "arquivados").mkdir(parents=True)
    (pasta / "arquivados" / "a.md").write_text(
        "---\nsprint: A-SPRINT-DA-LISTA-01\nestado: feita\n---\n", encoding="utf-8")
    (pasta / "b.md").write_text(
        "---\nsprint: OUTRA-SPRINT-01\nestado: aberta\n---\n", encoding="utf-8")
    lista = _mentira(tmp_path)["scripts/regua.py::DIVIDA_DE_MENTIRA"]
    faltas = sprints_fechadas({lista.chave: sprints_citadas(lista) | {"NENHUMA-01"}},
                              estados_das_sprints(pasta))
    assert len(faltas) == 2
    assert "`feita`" in faltas[0] and "não existe" in faltas[1]
