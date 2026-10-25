"""As citações da casa-sabe prometem o nome da linha citada, e nenhuma fica crua.

Sprint AS-CRUAS-DA-CASA-SABE-GANHAM-NOME-E-ELA-FECHA-O-MYPY-01 (25/10/2026). A citação crua
(`arquivo:linha` sem nome) que uma varredura ou um reapontamento em massa escreveu o
`reapontar-citacoes.py` não leva quando o código anda, e cada uma vira trabalho à mão na costura.
Em 25/10 eram 99 cruas na casa-sabe, 79 delas «à mão». Duas provas, para todo arquivo de
`CODIGO_COM_CITACOES`:

- toda citação de arquivo desta árvore promete um nome (``nomes_prometidos`` não vazio);
- o nome está na faixa citada e, na de linha única, não casa na linha vizinha (o
  ``varrer_codigo`` do validador sem achado).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[2]
VALIDADOR = RAIZ / "scripts" / "validar-citacoes-de-linha.py"


def _carregar(caminho: Path, nome: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(nome, caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


VAL = _carregar(VALIDADOR, "validar_citacoes_de_linha_cruas")


def cruas_do_codigo(codigo: Path, raiz: Path) -> list[str]:
    """``linha: endereço`` de cada citação de arquivo de ``raiz`` que não promete nome."""
    cruas: list[str] = []
    for trecho in VAL.trechos_do_codigo(codigo.read_text(encoding="utf-8")):
        for achado in VAL.ENDERECO_CSV.finditer(trecho.texto):
            if not (raiz / achado.group("arq")).is_file():
                continue  # o exemplo fabricado de um teste não é desta árvore
            if not VAL.nomes_prometidos(
                    trecho.texto, achado.start(), achado.end(), VAL.SEPARADORES_DE_BLOCO):
                cruas.append(f"{trecho.linha_de(achado.start())}: {achado.group(0)}")
    return cruas


def _codigos() -> list[Path]:
    codigos: list[Path] = VAL.codigos_de(RAIZ)
    assert codigos, "nenhum arquivo de CODIGO_COM_CITACOES nesta árvore: a régua mede o vazio"
    return codigos


def test_toda_citacao_do_codigo_que_cita_promete_um_nome() -> None:
    falhas = {c.relative_to(RAIZ).as_posix(): cruas_do_codigo(c, RAIZ) for c in _codigos()}
    falhas = {k: v for k, v in falhas.items() if v}
    assert not falhas, (
        "citação crua no código que cita: escreva o nome que só a linha citada tem, "
        "`caminho:N` (`nome`) ou `nome` em `caminho:N` (comentário ou docstring: a faixa até o "
        f"código):\n{falhas}"
    )


def test_o_nome_prometido_esta_na_linha_citada_e_nao_na_vizinha() -> None:
    achados = [str(a) for c in _codigos() for a in VAL.varrer_codigo(c, RAIZ)[0]]
    assert not achados, "\n".join(achados)


def test_a_regua_acusa_a_crua_e_aceita_o_nome(tmp_path: Path) -> None:
    (tmp_path / "alvo.py").write_text("x = 1\ndef dono() -> int:\n    return x\n", encoding="utf-8")
    codigo = tmp_path / "cita.py"
    codigo.write_text(
        'A = "o dono mora em alvo.py:2, e o `dono` em `alvo.py:2` também"\n', encoding="utf-8")
    assert cruas_do_codigo(codigo, tmp_path) == ["1: alvo.py:2"]
