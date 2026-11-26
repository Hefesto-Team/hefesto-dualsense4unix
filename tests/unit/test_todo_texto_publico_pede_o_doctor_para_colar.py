"""Todo texto público que pede a saída do doctor pede a de colar (25/11/2026).

O-CONVITE-A-CONTRIBUIR-PEDE-O-DOCTOR-NA-MASCARA-01, que segue
D-2511-O-DOCTOR-PARA-COLAR-SAI-NA-MASCARA. Medido: o guia de contribuição mandava rodar
``doctor`` e colar a saída na issue, e a descrição do rótulo «precisa do doctor» citava o
comando sem a opção; a saída crua traz o endereço inteiro do controle, e a issue é pública. A
régua anterior olhava quatro arquivos escolhidos a dedo; esta varre ``.github/``, o README e
``docs/`` (menos o que é de processo, pesquisa, dados e histórico, que não é texto de quem usa),
e reprova todo pedido da saída do doctor sem a opção ``--para-colar``.

MORDIDA: devolver a linha do CONTRIBUTING (ou a descrição do rótulo) a «doctor» sem a opção
reprova ``test_nenhum_texto_publico_pede_o_doctor_cru``; os dois testes seguintes cobrem a régua.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SUFIXOS = {".md", ".yml", ".yaml", ".txt"}
FORA_DE_DOCS = {"process", "research", "data", "history"}
PEDIDO = re.compile(r"hefesto-dualsense4unix doctor((?: +--?[\w-]+)*)")
DE_COLAR = re.compile(
    r"\b(cole|colar|colad[oa]s?|relat\w+|issues?|sa[ií]da|resultado|anex\w+|mande|envie)\b",
    re.IGNORECASE)
JANELA = 120


def _textos_publicos() -> list[Path]:
    achados = [RAIZ / "README.md"]
    achados += [p for p in (RAIZ / ".github").rglob("*") if p.is_file()]
    for p in (RAIZ / "docs").rglob("*"):
        if p.is_file() and p.relative_to(RAIZ / "docs").parts[0] not in FORA_DE_DOCS:
            achados.append(p)
    return sorted(p for p in achados if p.suffix in SUFIXOS)


def pedidos_do_doctor_cru(texto: str) -> list[str]:
    """Os trechos que pedem a saída do doctor (contexto de colar ou relatar) sem a opção."""
    crus = []
    for achado in PEDIDO.finditer(texto):
        if "--para-colar" in achado.group(1) or "--help" in achado.group(1):
            continue
        linha_ini = texto.rfind("\n", 0, achado.start()) + 1
        linha_fim = texto.find("\n", achado.end())
        linha = texto[linha_ini: len(texto) if linha_fim < 0 else linha_fim]
        de, ate = achado.start() - linha_ini, achado.end() - linha_ini
        trecho = linha[max(0, de - JANELA): ate + JANELA]
        if DE_COLAR.search(trecho):
            crus.append(trecho.strip())
    return crus


def test_a_varredura_alcanca_o_guia_o_rotulo_o_readme_e_os_documentos() -> None:
    nomes = {str(p.relative_to(RAIZ)) for p in _textos_publicos()}
    for esperado in (".github/CONTRIBUTING.md", ".github/repositorio.yml", "README.md",
                     ".github/ISSUE_TEMPLATE/bug.yml", "docs/usage/troubleshooting.md"):
        assert esperado in nomes, esperado
    assert not any(n.startswith(("docs/process/", "docs/research/")) for n in nomes)


def test_nenhum_texto_publico_pede_o_doctor_cru() -> None:
    cruas = {str(p.relative_to(RAIZ)): pedidos_do_doctor_cru(p.read_text(encoding="utf-8"))
             for p in _textos_publicos()}
    assert {nome: achados for nome, achados in cruas.items() if achados} == {}


def test_a_regua_reconhece_o_pedido_cru_e_aceita_o_de_colar() -> None:
    assert pedidos_do_doctor_cru(
        "Rodar `hefesto-dualsense4unix doctor` e colar a saída na issue") != []
    assert pedidos_do_doctor_cru(
        'descrição: "Falta a saída do comando hefesto-dualsense4unix doctor"') != []
    assert pedidos_do_doctor_cru(
        "Rodar `hefesto-dualsense4unix doctor --para-colar` e colar a saída na issue") == []
    assert pedidos_do_doctor_cru("o `hefesto-dualsense4unix doctor` dá `[FAIL]` ao serviço") == []


def test_o_guia_e_o_rotulo_pedem_o_de_colar_e_o_guia_diz_o_que_a_saida_nao_traz() -> None:
    guia = (RAIZ / ".github/CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "doctor --para-colar" in guia
    assert "não traz o endereço do controle" in guia
    rotulos = (RAIZ / ".github/repositorio.yml").read_text(encoding="utf-8")
    linha = next(ln for ln in rotulos.splitlines() if '"precisa do doctor"' in ln)
    assert "doctor --para-colar" in linha
