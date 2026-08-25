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

#: O módulo que é DONO do campo `texto` — o único lugar onde lê-lo é legítimo,
#: porque é ele quem implementa `frase_de_exibicao`.
_DONO_DO_CAMPO = "fala_do_mapa.py"

#: As `Fala` declaradas que ainda não chegaram à tela, uma a uma, com a razão
#: escrita e quem as fecha. **Nasce vazio**, e é para continuar assim.
#:
#: Chaveada por `arquivo::NOME`. Uma entrada que não casa mais com nenhuma
#: `Fala` órfã REPROVA — lápide que sobrevive à própria cura é o defeito que
#: este tipo de lista existe para matar, medido em 25/08/2026 no
#: `portao_a_casa_sabe_e_o_produto_nao_faz`, onde duas notas datadas seguiram
#: dizendo "nada de produção chama" sobre funções que a produção passou a
#: chamar.
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


def declaradas_e_exibidas(
    app_dir: Path, raiz: Path
) -> tuple[list[_FalaDeclarada], set[str]]:
    """As `Fala` ligadas a um nome de módulo, e os nomes que a tela exibe."""
    declaradas: list[_FalaDeclarada] = []
    exibidos: set[str] = set()
    for caminho in _arquivos_de(app_dir):
        try:
            arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
        except (OSError, SyntaxError):  # pragma: no cover - defensivo
            continue
        relativo = str(caminho.relative_to(raiz))
        for no in arvore.body:
            alvos: list[ast.expr] = []
            valor: ast.expr | None = None
            if isinstance(no, ast.Assign):
                alvos, valor = list(no.targets), no.value
            elif isinstance(no, ast.AnnAssign):
                alvos, valor = [no.target], no.value
            if valor is None or not _e_chamada_de(valor, "Fala"):
                continue
            for alvo in alvos:
                if isinstance(alvo, ast.Name):
                    declaradas.append(
                        _FalaDeclarada(arquivo=relativo, linha=no.lineno, nome=alvo.id)
                    )
        for no in ast.walk(arvore):
            if not _e_chamada_de(no, "frase_de_exibicao"):
                continue
            assert isinstance(no, ast.Call)
            for argumento in no.args:
                if isinstance(argumento, ast.Name):
                    exibidos.add(argumento.id)
    return declaradas, exibidos


def falas_orfas(app_dir: Path, raiz: Path) -> list[_FalaDeclarada]:
    """As `Fala` declaradas que nenhuma tela exibe."""
    declaradas, exibidos = declaradas_e_exibidas(app_dir, raiz)
    return [fala for fala in declaradas if fala.nome not in exibidos]


def leituras_cruas_do_texto(app_dir: Path, raiz: Path) -> list[str]:
    """`NOME.texto` onde `NOME` é uma `Fala`, fora do módulo dono do campo."""
    declaradas, _ = declaradas_e_exibidas(app_dir, raiz)
    nomes = {fala.nome for fala in declaradas}
    cruas: list[str] = []
    for caminho in _arquivos_de(app_dir):
        if caminho.name == _DONO_DO_CAMPO:
            continue
        try:
            arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
        except (OSError, SyntaxError):  # pragma: no cover - defensivo
            continue
        relativo = str(caminho.relative_to(raiz))
        for no in ast.walk(arvore):
            if (
                isinstance(no, ast.Attribute)
                and no.attr == "texto"
                and isinstance(no.value, ast.Name)
                and no.value.id in nomes
            ):
                cruas.append(f"{relativo}:{no.lineno}: {no.value.id}.texto")
    return cruas


# ── o portão, sobre a árvore de verdade ──────────────────────────────────


def test_toda_fala_declarada_chega_a_tela() -> None:
    orfas = {fala.endereco: fala for fala in falas_orfas(APP_REAL, RAIZ_REAL)}
    sem_razao = sorted(set(orfas) - set(_FALA_SEM_TELA_HOJE))
    assert not sem_razao, (
        "estas `Fala` estão DECLARADAS e nenhuma tela as exibe:\n  "
        + "\n  ".join(f"{orfas[e].arquivo}:{orfas[e].linha}: {orfas[e].nome}" for e in sem_razao)
        + "\n\nDeclarar uma `Fala` amarra a frase ao mapa; o que a põe na tela "
        "é `frase_de_exibicao(...)`. Sem essa chamada a medição chegou ao "
        "registro e parou ali — a pessoa segue lendo a frase de ontem, e o "
        "portão de `scripts/validar-fala-de-tela.py` fica VERDE por cima "
        "disso. Chame `frase_de_exibicao` onde o texto é escrito, ou declare a "
        "lacuna em `_FALA_SEM_TELA_HOJE` com a razão e com quem a fecha."
    )


def test_a_lista_de_lacunas_nao_envelhece_calada() -> None:
    orfas = {fala.endereco for fala in falas_orfas(APP_REAL, RAIZ_REAL)}
    caducas = sorted(set(_FALA_SEM_TELA_HOJE) - orfas)
    assert not caducas, (
        f"estas entradas de `_FALA_SEM_TELA_HOJE` não casam com nenhuma `Fala` "
        f"órfã: {caducas}. A `Fala` foi ligada, renomeada ou apagada — APAGUE a "
        "entrada no mesmo commit. Lápide que sobrevive à própria cura é o "
        "defeito que esta lista existe para matar."
    )
    vazias = sorted(nome for nome, razao in _FALA_SEM_TELA_HOJE.items() if not razao.strip())
    assert not vazias, f"lacuna sem razão escrita é o mesmo que não ter portão: {vazias}"


def test_ninguem_le_o_texto_cru_de_uma_fala() -> None:
    cruas = leituras_cruas_do_texto(APP_REAL, RAIZ_REAL)
    assert not cruas, (
        "estas linhas leem `Fala.texto` direto:\n  "
        + "\n  ".join(cruas)
        + f"\n\nSó `app/{_DONO_DO_CAMPO}` pode. `Fala.texto` aceita o sentinela "
        "`NAO_MEDIDO`, que NÃO é uma string: lido cru, ele chega à tela como "
        "`<_NaoMedidoSentinela object at 0x…>` em vez da frase única da casa. "
        "Use `frase_de_exibicao(fala)`."
    )


# ── o mesmo defeito, aplicado ao PRÓPRIO portão ──────────────────────────


def test_toda_checagem_do_portao_e_chamada_pelo_main() -> None:
    """Uma checagem escrita e nunca ligada é o defeito-mãe dentro da cura.

    MEDIDO em 25/08/2026, e é por isso que este teste existe: a árvore
    amanheceu com ``valida_abas_promovidas`` escrita, testada em prosa no
    próprio docstring e **nunca chamada** por ``main()``. Promover uma aba não
    teria feito nada, e o portão diria OK. Uma checagem que ninguém chama é
    indistinguível de uma checagem que não existe — só custa mais caro,
    porque quem lê o arquivo acredita nela.
    """
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
        "portão verde sobre exatamente o que ela media."
    )


# ── as mordidas, em árvore de mentira ────────────────────────────────────


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


def test_mordida_fala_declarada_e_nunca_exibida_e_acusada(tmp_path: Path) -> None:
    app = _monta(tmp_path, {"tela.py": _DECLARA})
    orfas = falas_orfas(app, tmp_path)
    assert [fala.nome for fala in orfas] == ["DICA"]


def test_mordida_a_mesma_fala_exibida_deixa_de_ser_acusada(tmp_path: Path) -> None:
    """O outro lado: sem ele, um portão que acusa tudo passaria na mordida."""
    app = _monta(tmp_path, {"tela.py": _DECLARA + _EXIBE})
    assert falas_orfas(app, tmp_path) == []


def test_mordida_exibida_de_outro_arquivo_tambem_conta(tmp_path: Path) -> None:
    """Declarar num módulo e exibir noutro é o desenho de hoje.

    `external_card.py` declara e exibe no mesmo arquivo, mas nada obriga isso —
    uma régua por arquivo acusaria falso na primeira separação, e portão que
    grita falso é desligado na semana seguinte.
    """
    outro = """\
from hefesto_dualsense4unix.app.fala_do_mapa import frase_de_exibicao

from .tela import DICA


def desenha(rotulo: object) -> None:
    rotulo.set_label(frase_de_exibicao(DICA))
"""
    app = _monta(tmp_path, {"tela.py": _DECLARA, "widgets/cartao.py": outro})
    assert falas_orfas(app, tmp_path) == []


def test_mordida_ler_o_texto_cru_nao_satisfaz_o_portao(tmp_path: Path) -> None:
    """A regra 2 existe para esta linha: ela "usa" a `Fala` e fura o sentinela."""
    app = _monta(tmp_path, {"tela.py": _DECLARA + _LE_CRU})
    assert [fala.nome for fala in falas_orfas(app, tmp_path)] == ["DICA"]
    cruas = leituras_cruas_do_texto(app, tmp_path)
    assert len(cruas) == 1 and "DICA.texto" in cruas[0], cruas
