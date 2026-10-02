"""O elo medição→tela não pode parar no registro — PAREAMENTO-01, o mecanismo.

O título da sprint é o contrato: *"a medição nova tem de chegar SOZINHA na
tela"*. ``scripts/validar-fala-de-tela.py`` guarda uma das pontas — que a
``Fala`` declarada não afirme mais do que o mapa mede. **Este arquivo guarda a
outra**, e ela é a que some calada: uma ``Fala`` DECLARADA que nenhuma tela
EXIBE.

POR QUE ISSO NÃO É HIPÓTESE
----------------------------
É a família ``A-CASA-SABE-E-O-PRODUTO-NAO-FAZ`` acontecendo DENTRO da cura que
a combate, e ela já aconteceu duas vezes nesta mesma leva. Medido em
25/08/2026 por quem coordena: ``app/fala_do_mapa.py::formata_pt_br`` e
``::Numero`` nasceram na ONDA0-Z6 (``26e0ccc``, 24/08) sob o título *"a
medição chega à tela por portão, não por lembrança"* — e nenhuma tela os
chama. Os dois estão registrados como órfãos em
``tests/unit/portao_a_casa_sabe_e_o_produto_nao_faz.py``.

E o caminho para o defeito acontecer de novo está DESENHADO na PAREAMENTO-01:
a fase F1 é *de carona* — quem conserta uma aba declara ``Fala`` para as
frases que a aba já tem. Nada no portão de P-09 obriga a frase declarada a ser
a frase que a tela mostra. Sem esta prova, o gesto que satisfaz P-09 é
*declarar uma ``Fala`` e deixar o literal antigo na tela*: o portão fica verde,
a medição chega ao registro, e a pessoa continua lendo a frase de ontem. O
portão viraria o contrário do que a sprint quer — uma lembrança a mais para
alguém ter.

O QUE ESTE PORTÃO EXIGE, E POR QUE SÃO DUAS REGRAS E NÃO UMA
--------------------------------------------------------------
1. **Toda ``Fala`` de módulo em ``app/`` é passada a ``frase_de_exibicao``
   em algum ponto de ``app/``.** É "chegou à tela".
2. **Ninguém lê ``fala.texto`` fora de ``app/fala_do_mapa.py``.** Sem a
   segunda, a primeira se satisfaz com ``set_label(DICA.texto)`` — e aí o
   ``NAO_MEDIDO`` da sprint, que é um SENTINELA e não uma string, chega à tela
   como ``<_NaoMedidoSentinela object at 0x…>``. A regra
   *"ausência de medição se declara, nunca se preenche com zero"* mora no
   tipo justamente para não depender de alguém lembrar; ler o campo cru
   contorna o tipo.

O QUE ELE NÃO EXIGE, DE PROPÓSITO
----------------------------------
Que a frase esteja num widget concreto, ou que o widget seja visível. Isso é
fluxo, e a régua desta casa é de DECLARAÇÃO, não de fluxo (Z6-10): seguir
condicional e ramo por AST tem falso-negativo mudo, e portão que perde em
silêncio é pior que portão nenhum. ``frase_de_exibicao`` é o sítio declarado
de "isto vai para a tela", como ``Fala`` é o sítio declarado de "isto fala do
mapa".
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

RAIZ_REAL = Path(__file__).resolve().parents[2]
APP_REAL = RAIZ_REAL / "src" / "hefesto_dualsense4unix" / "app"
PORTAO_REAL = RAIZ_REAL / "scripts" / "validar-fala-de-tela.py"

_DONO_DO_CAMPO = "fala_do_mapa.py"

#: `portao_a_casa_sabe_e_o_produto_nao_faz`, onde duas notas datadas seguiram
_FALA_SEM_TELA_HOJE: dict[str, str] = {}


@dataclass(frozen=True)
class _FalaDeclarada:
    arquivo: str
    linha: int
    nome: str

    @property
    def endereco(self) -> str:
        return f"{self.arquivo}::{self.nome}"


def _arquivos_de(app_dir: Path) -> list[Path]:
    return [
        caminho
        for caminho in sorted(app_dir.rglob("*.py"))
        if "__pycache__" not in caminho.parts
    ]


def _e_chamada_de(no: ast.AST, nome: str) -> bool:
    """`f(...)` ou `modulo.f(...)` — as duas formas de chamar a mesma função."""
    if not isinstance(no, ast.Call):
        return False
    alvo = no.func
    if isinstance(alvo, ast.Name):
        return alvo.id == nome
    return isinstance(alvo, ast.Attribute) and alvo.attr == nome


def test_toda_checagem_do_portao_e_chamada_pelo_main() -> None:
    """Uma checagem escrita e nunca ligada é o defeito-mãe dentro da cura."""
    arvore = ast.parse(PORTAO_REAL.read_text(encoding="utf-8"), filename=str(PORTAO_REAL))
    checagens = {
        no.name
        for no in arvore.body
        if isinstance(no, ast.FunctionDef) and no.name.startswith("valida")
    }
    main = next(
        (no for no in arvore.body if isinstance(no, ast.FunctionDef) and no.name == "main"),
        None,
    )
    assert main is not None, "o portão perdeu o `main()`"
    chamadas = {
        no.func.id
        for no in ast.walk(main)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
    }
    soltas = sorted(checagens - chamadas)
    assert not soltas, (
        f"estas checagens de {PORTAO_REAL.name} não são chamadas por `main()`: "
        f"{soltas}. Ligue-as ou apague-as: uma checagem que ninguém roda deixa o "
        "portão verde sobre exatamente o que ela media."  # (noqa-acento: verbo medir, imperfeito)
    )


def _monta(tmp_path: Path, arquivos: dict[str, str]) -> Path:
    app = tmp_path / "src" / "hefesto_dualsense4unix" / "app"
    app.mkdir(parents=True, exist_ok=True)
    for relativo, conteudo in arquivos.items():
        caminho = app / relativo
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(conteudo, encoding="utf-8")
    return app


_DECLARA = '''\
"""Uma tela de mentira."""
from __future__ import annotations

from hefesto_dualsense4unix.app.fala_do_mapa import AFIRMA_ACIONA, Fala

DICA = Fala(
    chave="audio.alto_falante@dualsense",
    lado="radio",
    aba="Início",
    texto="Toca pelo rádio.",
    afirma=AFIRMA_ACIONA,
)
'''

_EXIBE = """

def desenha(rotulo: object) -> None:
    rotulo.set_label(frase_de_exibicao(DICA))
"""

_LE_CRU = """

def desenha(rotulo: object) -> None:
    rotulo.set_label(DICA.texto)
"""


