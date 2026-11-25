"""A-TELA-NOVA-ENTRA-NA-RÉGUA-DO-MAPA-01 — a régua da fala de tela varria só `app/`."""
from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from tests.unit.test_validar_fala_de_tela import monta_produto

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
        "o defeito que a régua teve de 24/08 a 06/09. Se a pasta mudou de "
        "nome, troque nos DOIS lugares; se a decisão foi outra, a pasta tem de "
        f"sair também deste arquivo, com data e razão. Hoje: {no_roteiro}"
    )


def test_o_piso_compara_e_nao_tem_a_resposta_cravada() -> None:
    """A régua muda de resposta quando o conjunto muda — os quatro casos."""
    valida = _modulo_do_portao().valida_piso_da_regua
    piso = {"raizes": 2, "numeros": 3}

    assert valida({"raizes": 2, "numeros": 3}, piso) == []
    assert valida({"raizes": 9, "numeros": 9}, piso) == [], (
        "crescer tem de PASSAR — régua que reprova quem melhora é o defeito "
        "que onze réguas desta casa já tiveram"
    )

    encolheu = valida({"raizes": 1, "numeros": 3}, piso)
    assert len(encolheu) == 1 and "raizes" in encolheu[0], encolheu

    tudo = valida({"raizes": 0, "numeros": 0}, piso)
    assert len(tudo) == 2, tudo
    assert all("NÃO baixe o piso" in problema for problema in tudo), tudo


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


def _portao_com_raizes(raiz: Path, raizes: tuple[str, ...]) -> Path:
    """O roteiro real copiado para `raiz/scripts/`, com `RAIZES_DE_TELA` trocada."""
    fonte = SCRIPT_REAL.read_text(encoding="utf-8")
    antigo = "RAIZES_DE_TELA: tuple[str, ...] = (APP_RELATIVO, INTERFACE_RELATIVO)"
    assert fonte.count(antigo) == 1, (
        f"a linha {antigo[:60]!r} mudou de forma em {SCRIPT_REAL.name}: sem "
        "a linha, esta mordida rodaria com o roteiro intacto e passaria sempre"
    )
    destino = raiz / "scripts" / SCRIPT_REAL.name
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        fonte.replace(antigo, f"RAIZES_DE_TELA: tuple[str, ...] = {raizes!r}"), encoding="utf-8"
    )
    return destino


def _roda(portao: Path, raiz: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(portao), "--raiz", str(raiz), "--all"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_tirar_uma_raiz_de_tela_reprova_pelo_piso(tmp_path: Path) -> None:
    """A MORDIDA: arranque `interface/` de `RAIZES_DE_TELA` e a régua diz que encolheu."""
    produto = monta_produto(tmp_path / "produto")
    inteiro = _roda(SCRIPT_REAL, produto)
    assert inteiro.returncode == 0, inteiro.stdout + inteiro.stderr

    so_app = _portao_com_raizes(tmp_path / "so_app", ("src/hefesto_dualsense4unix/app",))
    cego = _roda(so_app, produto)
    assert cego.returncode == 1, cego.stdout + cego.stderr
    assert "raizes: a régua mede 1 e o piso é 2" in cego.stdout, cego.stdout


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
    assert "Piso: numeros≥3, raizes≥2." in ultima, ultima
    for raiz in RAIZES_ATE_HOJE:
        assert raiz in ultima, f"a frase de sucesso não diz que varre {raiz}:\n{ultima}"
    assert "PISO NÃO APLICADO" not in processo.stdout, (
        "o produto deixou de ser reconhecido como produto e o piso não foi "
        "aplicado — o portão está verde sobre régua nenhuma:\n" + processo.stdout
    )
