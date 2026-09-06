"""A-TELA-NOVA-ENTRA-NA-RÉGUA-DO-MAPA-01 — a régua da fala de tela varria só `app/`.

O DEFEITO, MEDIDO EM 06/09/2026
================================
``scripts/validar-fala-de-tela.py`` existe para impedir que a tela afirme o que
``docs/data/mapa-controles.csv`` não sustenta. Ela conhecia **uma** raiz —
``src/hefesto_dualsense4unix/app`` — e a tela nova mora em
``src/hefesto_dualsense4unix/interface``. Das 170 frases de transporte que o
``--censo-de-transporte`` conta hoje, **123 estavam fora do alcance**, contra 47
dentro: a maior parte do texto de transporte da casa estava fora da régua que
existe para ele.

Não foi decisão. A régua é de 24/08/2026 e a tela nova nasceu depois — ela
mediu o mundo em que a única tela era `app/`. A pergunta que desenterrou isto é
dela: *"olharam o mapa dos controles e o csv que alimenta o specs.html?"*, e na
sequência *"se coisas assim aconteceram antes não so nessas duas sprints. entao
tem coisa errada."*  <!-- noqa-acento: citação literal dela -->

E ELA TERMINAVA VERDE DIZENDO QUE QUASE NÃO MEDIU
==================================================
``rc=0`` imprimindo *"A RÉGUA QUASE NÃO MEDIU: 1 `Fala` declarada(s) … contra
as 308 célula(s)"*. É a forma que a casa nomeou em 04/09/2026: **o instrumento
sabe do próprio risco e AVISA em vez de RESOLVER**. O que resolve é o piso:
o conjunto medido não pode ENCOLHER. Não enchê-lo continua verde; esvaziá-lo,
não.

O QUE ESTA RÉGUA NÃO FAZ, E É DECISÃO DELA
===========================================
Ela INFORMA; não VETA. Palavra dela, 06/09/2026, sobre o mapa: *"Esse mapa é
funcional e real. tá desatualizado no sentido de não ter sido medido. foi e
tudo funciona."* Uma célula em ``aciona=não`` quer dizer *ninguém escreveu a
medição de volta*, não *o aparelho não faz* — e uma régua que reprovasse a tela
por causa disso transformaria mapa atrasado em freio. Nenhuma asserção deste
arquivo reprova frase de tela por causa de célula atrasada.
<!-- noqa-acento: citação literal dela -->

AS DUAS LISTAS LITERAIS DESTE ARQUIVO NÃO SÃO LIDAS DO ROTEIRO
===============================================================
``RAIZES_ATE_HOJE`` e ``PISO_ATE_HOJE`` são escritas à mão AQUI. É a lição que
a ADR-016 pagou por um mês e que ``test_o_mapa_separa_divida_de_decisao.py``
deixou escrita: um teto lido da própria fonte passa sempre. Encolher o alcance
ou baixar o piso passa a exigir editar este arquivo, e isso aparece no diff.
"""
from __future__ import annotations

import ast
import csv
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from tests.unit.test_validar_fala_de_tela import FATOS_BASE, monta_arvore

RAIZ_REAL = Path(__file__).resolve().parents[2]
SCRIPT_REAL = RAIZ_REAL / "scripts" / "validar-fala-de-tela.py"

#: As raízes de tela de HOJE, à mão. O conjunto SÓ CRESCE: perder uma é perder
#: alcance em silêncio, que é o defeito de 24/08 a 06/09 medido acima.
RAIZES_ATE_HOJE: tuple[str, ...] = (
    "src/hefesto_dualsense4unix/app",
    "src/hefesto_dualsense4unix/interface",
)

#: O piso de HOJE, à mão. Ele SOBE quando a casa declarar mais — nunca desce
#: sem uma linha datada aqui dizendo o que foi retirado e por quem.
PISO_ATE_HOJE: dict[str, int] = {"raizes": 2, "falas": 1, "numeros": 3, "abas": 0}


# ─────────────────────────────────────────────────────────────────────────
# o roteiro, lido por AST e carregado por caminho
# ─────────────────────────────────────────────────────────────────────────
def _modulo_do_portao() -> ModuleType:
    """O roteiro carregado como módulo — para exercer as funções puras.

    Carregado por caminho de arquivo (nunca importado como pacote): ele mora em
    `scripts/`, que não é pacote, e é assim que `gerar-mapa.py` e
    `gerar-painel.py` já o carregam.
    """
    spec = importlib.util.spec_from_file_location("validar_fala_de_tela_sob_teste", SCRIPT_REAL)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["validar_fala_de_tela_sob_teste"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _constante_por_ast(nome: str) -> object:
    """Uma constante de módulo do roteiro, lida por AST.

    Por AST e não por import de propósito, como a catraca de
    ``test_abas_promovidas_so_crescem_p09.py``: a forma tem de ser literal, e
    qualquer coisa calculada em tempo de execução reprova em voz alta em vez de
    entregar um valor que ninguém consegue conferir lendo o arquivo.
    """
    arvore = ast.parse(SCRIPT_REAL.read_text(encoding="utf-8"), filename=str(SCRIPT_REAL))
    for no in arvore.body:
        alvo: str | None = None
        valor: ast.expr | None = None
        if isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
            alvo, valor = no.target.id, no.value
        elif (
            isinstance(no, ast.Assign)
            and len(no.targets) == 1
            and isinstance(no.targets[0], ast.Name)
        ):
            alvo, valor = no.targets[0].id, no.value
        if alvo != nome or valor is None:
            continue
        try:
            return ast.literal_eval(valor)
        except (ValueError, TypeError, SyntaxError):
            # `RAIZES_DE_TELA` cita `APP_RELATIVO`/`INTERFACE_RELATIVO`, que são
            # nomes: resolve-os pelo módulo, mas só depois de exigir que a forma
            # seja uma tupla/lista de nomes ou literais.
            assert isinstance(valor, (ast.Tuple, ast.List)), (
                f"{nome} deixou de ser uma tupla literal no roteiro"
            )
            modulo = _modulo_do_portao()
            resolvidos: list[object] = []
            for item in valor.elts:
                if isinstance(item, ast.Name):
                    resolvidos.append(getattr(modulo, item.id))
                else:
                    resolvidos.append(ast.literal_eval(item))
            return tuple(resolvidos)
    raise AssertionError(f"o roteiro perdeu `{nome}`")


# ─────────────────────────────────────────────────────────────────────────
# as catracas — as duas listas só crescem
# ─────────────────────────────────────────────────────────────────────────
def test_o_alcance_da_regua_so_cresce() -> None:
    """`RAIZES_DE_TELA` é superconjunto do literal deste arquivo."""
    no_roteiro = tuple(_constante_por_ast("RAIZES_DE_TELA"))  # type: ignore[call-overload]
    perdidas = [raiz for raiz in RAIZES_ATE_HOJE if raiz not in no_roteiro]
    assert not perdidas, (
        f"as raízes {perdidas} saíram de `RAIZES_DE_TELA`. Tirar uma raiz é "
        "cegar a régua para uma tela inteira sem que nada acuse — é exatamente "
        "o defeito que ela passou de 24/08 a 06/09 tendo. Se a pasta mudou de "
        "nome, troque nos DOIS lugares; se a decisão foi outra, ela tem de "
        f"sair também deste arquivo, com data e razão. Hoje: {no_roteiro}"
    )


def test_o_piso_da_regua_so_sobe() -> None:
    """`PISO_DA_REGUA` nunca fica abaixo do literal deste arquivo."""
    no_roteiro = _constante_por_ast("PISO_DA_REGUA")
    assert isinstance(no_roteiro, dict)
    baixaram = {
        nome: (no_roteiro.get(nome), valor)
        for nome, valor in PISO_ATE_HOJE.items()
        if no_roteiro.get(nome, 0) < valor
    }
    assert not baixaram, (
        f"o piso do roteiro caiu abaixo do medido em 06/09/2026: {baixaram} "
        "(roteiro, este arquivo). NÃO baixe o piso para ficar verde — descubra "
        "o que encolheu. É a mesma regra de `test_o_mapa_nunca_encolhe.py`."
    )


# ─────────────────────────────────────────────────────────────────────────
# o miolo do veredito, exercido com números sintéticos
# ─────────────────────────────────────────────────────────────────────────
def test_o_piso_compara_e_nao_tem_a_resposta_cravada() -> None:
    """A régua muda de resposta quando o conjunto muda — os quatro casos.

    Sem isto ela poderia estar acertando por ter a resposta escrita, e não por
    comparar (o molde de `tem_lastro_nos_dois`, em
    `test_a_aba_emulacao_nao_promete_transporte_sem_lastro.py`).
    """
    valida = _modulo_do_portao().valida_piso_da_regua
    piso = {"raizes": 2, "falas": 1, "numeros": 3, "abas": 1}

    assert valida({"raizes": 2, "falas": 1, "numeros": 3, "abas": 1}, piso) == []
    assert valida({"raizes": 9, "falas": 9, "numeros": 9, "abas": 9}, piso) == [], (
        "crescer tem de PASSAR — régua que reprova quem melhora é o defeito "
        "que onze réguas desta casa já tiveram"
    )

    encolheu = valida({"raizes": 1, "falas": 1, "numeros": 3, "abas": 1}, piso)
    assert len(encolheu) == 1 and "raizes" in encolheu[0], encolheu

    tudo = valida({"raizes": 0, "falas": 0, "numeros": 0, "abas": 0}, piso)
    assert len(tudo) == 4, tudo
    assert all("NÃO baixe o piso" in problema for problema in tudo), tudo


def test_a_arvore_de_mentira_nao_e_o_produto_e_a_de_verdade_e() -> None:
    """O piso vale para o produto — e a pergunta nunca se desliga calada.

    A ponta que importa é a SEGUNDA asserção: se `e_a_arvore_do_produto`
    apodrecer para sempre-falso (uma raiz renomeada, o mapa movido de lugar),
    o piso deixaria de valer no único lugar onde ele existe para valer, e o
    portão seguiria verde. Aqui isso reprova.
    """
    modulo = _modulo_do_portao()
    e_produto, por_que = modulo.e_a_arvore_do_produto(RAIZ_REAL)
    assert e_produto, (
        "a árvore do produto deixou de ser reconhecida como tal "
        f"({por_que!r}) — com isso o piso de `PISO_DA_REGUA` não vale em lugar "
        "nenhum, e o portão fica verde sobre uma régua que encolheu"
    )
    fora, razao = modulo.e_a_arvore_do_produto(RAIZ_REAL / "docs")
    assert not fora and razao, "uma pasta qualquer passou por árvore do produto"


# ─────────────────────────────────────────────────────────────────────────
# a árvore de mentira que É um produto — para as mordidas do piso
# ─────────────────────────────────────────────────────────────────────────
#: A frase de tela das abas de mentira. Sem palavra de transporte de propósito:
#: as mordidas do piso medem o PISO, e uma frase de transporte solta traria
#: junto a reprovação de `valida_abas_promovidas`, misturando dois vereditos.
_ABA_SEM_TRANSPORTE = '''\
"""Uma aba de mentira."""
from __future__ import annotations

DICA = "O ajuste foi gravado no perfil."
'''


def _produto_de_mentira(tmp_path: Path, arquivos_da_interface: dict[str, str]) -> Path:
    """Uma árvore que `e_a_arvore_do_produto` reconhece: mapa + as duas raízes."""
    raiz = monta_arvore(tmp_path, FATOS_BASE, {"aba_inicio.py": _ABA_SEM_TRANSPORTE})
    interface = raiz / "src" / "hefesto_dualsense4unix" / "interface"
    interface.mkdir(parents=True, exist_ok=True)
    for relativo, conteudo in arquivos_da_interface.items():
        caminho = interface / relativo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(conteudo, encoding="utf-8")
    dados = raiz / "docs" / "data"
    dados.mkdir(parents=True, exist_ok=True)
    with (dados / "mapa-controles.csv").open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=["id", "radio_ressalva"])
        escritor.writeheader()
    return raiz


def _portao_com(
    raiz: Path,
    *,
    abas: frozenset[str] | set[str] = frozenset(),
    arquivos_da_aba: dict[str, tuple[str, ...]] | None = None,
    piso: dict[str, int] | None = None,
    raizes: tuple[str, ...] | None = None,
) -> Path:
    """O roteiro real copiado para `raiz/scripts/`, com as linhas trocadas.

    Cada troca AFIRMA que casou: uma substituição que não casa devolveria o
    roteiro intacto, e a mordida passaria sem morder nada. Instrumento que
    falha calado é pior que instrumento nenhum.
    """
    fonte = SCRIPT_REAL.read_text(encoding="utf-8")
    trocas = {
        "ABAS_COM_FALA_DECLARADA: frozenset[str] = frozenset()": (
            f"ABAS_COM_FALA_DECLARADA: frozenset[str] = frozenset({sorted(abas)!r})"
        ),
        "ARQUIVOS_DA_ABA: dict[str, tuple[str, ...]] = {}": (
            f"ARQUIVOS_DA_ABA: dict[str, tuple[str, ...]] = {(arquivos_da_aba or {})!r}"
        ),
    }
    if piso is not None:
        trocas[
            'PISO_DA_REGUA: dict[str, int] = {"raizes": 2, "falas": 1, "numeros": 3, "abas": 0}'
        ] = f"PISO_DA_REGUA: dict[str, int] = {piso!r}"
    if raizes is not None:
        trocas["RAIZES_DE_TELA: tuple[str, ...] = (APP_RELATIVO, INTERFACE_RELATIVO)"] = (
            f"RAIZES_DE_TELA: tuple[str, ...] = {raizes!r}"
        )
    for antigo, novo in trocas.items():
        assert fonte.count(antigo) == 1, (
            f"a linha {antigo[:60]!r} mudou de forma em {SCRIPT_REAL.name}: sem "
            "ela esta mordida rodaria com o roteiro intacto e passaria sempre"
        )
        fonte = fonte.replace(antigo, novo)
    destino = raiz / "scripts" / SCRIPT_REAL.name
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(fonte, encoding="utf-8")
    return destino


def _roda(portao: Path, raiz: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(portao), "--raiz", str(raiz), *args],
        capture_output=True,
        text=True,
        check=False,
    )


# ─────────────────────────────────────────────────────────────────────────
# A MORDIDA DO PASSO 1 — devolver a raiz única cega a régua
# ─────────────────────────────────────────────────────────────────────────
def _censo_por_raiz(saida: str) -> dict[str, int]:
    """`{raiz: frases}` lido do rodapé do `--censo-de-transporte`."""
    contas: dict[str, int] = {}
    for linha in saida.splitlines():
        pedaco = linha.strip()
        if ": " not in pedaco or " frase(s) em " not in pedaco:
            continue
        raiz, resto = pedaco.split(": ", 1)
        contas[raiz] = int(resto.split(" ", 1)[0])
    return contas


def test_a_regua_ve_a_tela_nova_e_cega_de_novo_com_a_raiz_unica(tmp_path: Path) -> None:
    """A MORDIDA: arranque `interface/` de `RAIZES_DE_TELA` e conte o que sumiu.

    Sobre a árvore de VERDADE — é o alcance dela que a sprint veio devolver, e
    medi-lo numa árvore de mentira provaria só que o laço tem duas voltas.
    """
    # O QUANTO se perde é medido, nunca digitado: um roteiro com as raízes
    # deste arquivo forçadas diz o que a régua DEVERIA ver, e o roteiro real
    # diz o que ela vê. Um número literal aqui envelheceria e puniria quem
    # curasse uma frase.
    forcado = _portao_com(tmp_path / "forcado", raizes=RAIZES_ATE_HOJE)
    deveria = _censo_por_raiz(_roda(forcado, RAIZ_REAL, "--censo-de-transporte").stdout)

    com_as_duas = _roda(SCRIPT_REAL, RAIZ_REAL, "--censo-de-transporte")
    assert com_as_duas.returncode == 0, com_as_duas.stdout + com_as_duas.stderr
    antes = _censo_por_raiz(com_as_duas.stdout)
    cegas = {
        raiz: quantas
        for raiz, quantas in deveria.items()
        if antes.get(raiz, 0) < quantas
    }
    assert not cegas, (
        f"a régua deixou de ver {sum(cegas.values())} frase(s) de transporte, "
        f"por raiz: {cegas}. Ou `RAIZES_DE_TELA` encolheu, ou a tela mudou de "
        "casa — nos dois casos a régua está cega para uma tela inteira, que é "
        f"o defeito de 24/08 a 06/09. Vendo hoje: {antes}"
    )
    assert antes.get("src/hefesto_dualsense4unix/interface", 0) > 0, (
        "o censo não achou UMA frase de transporte em `interface/` — se a tela "
        "nova foi curada por inteiro, troque este caso pela prova disso"
    )

    so_app = _portao_com(tmp_path, raizes=("src/hefesto_dualsense4unix/app",))
    cego = _roda(so_app, RAIZ_REAL, "--censo-de-transporte")
    assert cego.returncode == 0, cego.stdout + cego.stderr
    depois = _censo_por_raiz(cego.stdout)
    assert "src/hefesto_dualsense4unix/interface" not in depois, (
        "com a raiz única a régua continuou enxergando `interface/` — a troca "
        "não pegou, e esta mordida não morde nada"
    )
    assert depois.get("src/hefesto_dualsense4unix/app", 0) == antes.get(
        "src/hefesto_dualsense4unix/app", 0
    ), "acrescentar `interface/` não pode mudar o que a régua via em `app/`"


def test_a_raiz_unica_reprova_pelo_piso_do_alcance(tmp_path: Path) -> None:
    """A outra ponta da mesma mordida: encurtar `RAIZES_DE_TELA` é `rc=1`.

    O censo acima mostra o que se PERDE; este mostra que a perda não passa
    calada. Sem ele, alguém podia tirar a raiz e o portão seguir verde.
    """
    raiz = _produto_de_mentira(tmp_path, {})
    portao = _portao_com(
        raiz,
        piso={"raizes": 2, "falas": 0, "numeros": 0, "abas": 0},
        raizes=("src/hefesto_dualsense4unix/app",),
    )
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 1, processo.stdout
    assert "ENCOLHEU" in processo.stdout, processo.stdout
    assert "raizes: a régua mede 1 e o piso é 2" in processo.stdout, processo.stdout


def test_a_fala_declarada_na_tela_nova_e_vista(tmp_path: Path) -> None:
    """O outro lado do alcance: uma `Fala` em `interface/` passa a contar.

    `interface/` não tem nenhuma hoje — 06/09/2026 —, e é por isso que este
    caso planta uma. Sem ele, o alcance novo estaria provado só pelo censo, e o
    censo não é o que o `--all` compara contra o mapa.
    """
    declarada = '''\
"""Uma tela nova de mentira."""
from __future__ import annotations

from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_ACIONA, Fala

DICA = Fala(
    chave="audio.alto_falante@dualsense",
    lado="radio",
    aba="Conexões",
    texto="O alto-falante toca também por rádio.",
    afirma=AFIRMA_ACIONA,
)
'''
    raiz = _produto_de_mentira(tmp_path, {"pacotes/a08_conexoes.py": declarada})
    portao = _portao_com(raiz, piso={"raizes": 2, "falas": 1, "numeros": 0, "abas": 0})
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 0, processo.stdout
    assert "1 `Fala` declarada(s)" in processo.stdout, processo.stdout


# ─────────────────────────────────────────────────────────────────────────
# AS MORDIDAS DO PASSO 2 — o piso das abas promovidas
# ─────────────────────────────────────────────────────────────────────────
def test_despromover_uma_aba_reprova_dizendo_o_piso(tmp_path: Path) -> None:
    """A MORDIDA: duas abas promovidas, o piso em 2, uma sai — `rc=1`."""
    raiz = _produto_de_mentira(tmp_path, {})
    portao = _portao_com(
        raiz,
        abas={"Início"},
        arquivos_da_aba={"Início": ("aba_inicio.py",)},
        piso={"raizes": 2, "falas": 0, "numeros": 0, "abas": 2},
    )
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 1, processo.stdout
    assert "ENCOLHEU" in processo.stdout, processo.stdout
    assert "abas: a régua mede 1 e o piso é 2" in processo.stdout, processo.stdout
    assert "ABAS_COM_FALA_DECLARADA" in processo.stdout, processo.stdout


def test_promover_mais_uma_aba_passa_e_o_piso_nao_pune(tmp_path: Path) -> None:
    """A SEGUNDA MORDIDA: acrescentar uma aba PASSA.

    É a metade que decide. Um piso comparado por igualdade reprovaria quem
    melhora — o defeito que onze réguas desta casa já tiveram em 26/08, todas
    pela mesma forma: digitavam o que deviam ler. Sem este caso, o de cima
    passaria também numa régua que reprova qualquer conjunto diferente de 2.
    """
    raiz = _produto_de_mentira(tmp_path, {})
    portao = _portao_com(
        raiz,
        abas={"Início", "Status", "Conexões"},
        arquivos_da_aba={
            "Início": ("aba_inicio.py",),
            "Status": ("aba_inicio.py",),
            "Conexões": ("aba_inicio.py",),
        },
        piso={"raizes": 2, "falas": 0, "numeros": 0, "abas": 2},
    )
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 0, processo.stdout
    assert "ENCOLHEU" not in processo.stdout, processo.stdout
    assert "3 aba(s) promovida(s)" in processo.stdout, processo.stdout


def test_a_aba_promovida_pode_morar_na_tela_nova(tmp_path: Path) -> None:
    """`ARQUIVOS_DA_ABA` passa a achar o arquivo em QUALQUER raiz de tela.

    Sem isto, promover uma aba que já migrou para `interface/` reprovaria com
    "não existe" — o portão vermelho por uma mudança de casa que não mudou uma
    palavra da tela.
    """
    raiz = _produto_de_mentira(tmp_path, {"aba_conexoes.py": _ABA_SEM_TRANSPORTE})
    portao = _portao_com(
        raiz,
        abas={"Conexões"},
        arquivos_da_aba={"Conexões": ("aba_conexoes.py",)},
        piso={"raizes": 2, "falas": 0, "numeros": 0, "abas": 0},
    )
    processo = _roda(portao, raiz, "--all")
    assert processo.returncode == 0, processo.stdout

    sumido = _portao_com(
        raiz,
        abas={"Conexões"},
        arquivos_da_aba={"Conexões": ("aba_que_ninguem_escreveu.py",)},
        piso={"raizes": 2, "falas": 0, "numeros": 0, "abas": 0},
    )
    ausente = _roda(sumido, raiz, "--all")
    assert ausente.returncode == 1, ausente.stdout
    assert "não existe" in ausente.stdout, ausente.stdout


# ─────────────────────────────────────────────────────────────────────────
# a árvore de verdade, hoje
# ─────────────────────────────────────────────────────────────────────────
def test_o_portao_de_hoje_esta_no_piso_e_diz_qual_e() -> None:
    """O produto de hoje passa, e a frase de sucesso NOMEIA o piso.

    O verde de hoje é o piso, não uma promessa — e quem lê o `portoes.sh` tem
    de conseguir ver contra o que ele está sendo medido sem abrir o roteiro.
    """
    processo = subprocess.run(
        [sys.executable, str(SCRIPT_REAL), "--all"],
        cwd=RAIZ_REAL,
        capture_output=True,
        text=True,
        check=False,
    )
    assert processo.returncode == 0, processo.stdout + processo.stderr
    ultima = processo.stdout.strip().splitlines()[-1]
    assert "PISO" in ultima, ultima
    for raiz in RAIZES_ATE_HOJE:
        assert raiz in ultima, f"a frase de sucesso não diz que varre {raiz}:\n{ultima}"
    assert "PISO NÃO APLICADO" not in processo.stdout, (
        "o produto deixou de ser reconhecido como produto e o piso não foi "
        "aplicado — o portão está verde sobre régua nenhuma:\n" + processo.stdout
    )
