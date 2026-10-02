"""A-TELA-NOVA-ENTRA-NA-RÉGUA-DO-MAPA-01 — a régua da fala de tela varria só `app/`."""
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

RAIZES_ATE_HOJE: tuple[str, ...] = (
    "src/hefesto_dualsense4unix/app",
    "src/hefesto_dualsense4unix/interface",
)


def _modulo_do_portao() -> ModuleType:
    """O roteiro carregado como módulo — para exercer as funções puras."""
    spec = importlib.util.spec_from_file_location("validar_fala_de_tela_sob_teste", SCRIPT_REAL)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["validar_fala_de_tela_sob_teste"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _constante_por_ast(nome: str) -> object:
    """Uma constante de módulo do roteiro, lida por AST."""
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


def test_a_arvore_de_mentira_nao_e_o_produto_e_a_de_verdade_e() -> None:
    """O piso vale para o produto — e a pergunta nunca se desliga calada."""
    modulo = _modulo_do_portao()
    e_produto, por_que = modulo.e_a_arvore_do_produto(RAIZ_REAL)
    assert e_produto, (
        "a árvore do produto deixou de ser reconhecida como tal "
        f"({por_que!r}) — com isso o piso de `PISO_DA_REGUA` não vale em lugar "
        "nenhum, e o portão fica verde sobre uma régua que encolheu"
    )
    fora, razao = modulo.e_a_arvore_do_produto(RAIZ_REAL / "docs")
    assert not fora and razao, "uma pasta qualquer passou por árvore do produto"


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
    """O roteiro real copiado para `raiz/scripts/`, com as linhas trocadas."""
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
    """A MORDIDA: arranque `interface/` de `RAIZES_DE_TELA` e conte o que sumiu."""
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


def test_o_portao_de_hoje_esta_no_piso_e_diz_qual_e() -> None:
    """O produto de hoje passa, e a frase de sucesso NOMEIA o piso."""
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
