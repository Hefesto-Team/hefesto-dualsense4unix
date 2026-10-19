"""A-VARREDURA-DOS-CONTRATOS-DE-FORA-LE-OS-MANIFESTOS-01: o portão dos contratos de fora lê
também os ``hefesto-mod.json``.

Desde 17/10 os seis lançadores de fábrica são manifestos (``mods/de_fabrica/*/hefesto-mod.json``),
e os comandos de fora que eles chamam (``flatpak``, ``heroic``, ``lutris``, ``steam``…) saíram
dos ``.py``: o portão, que só varria Python, deixou de ver o ponto de contato, e uma linha do
censo que dependia só dele podia sair como «morta» sem que o contato tivesse sumido.

Quatro réguas:

1. um manifesto de mentira que declara um comando sem linha no censo reprova; com a linha, passa;
2. o que o conferidor aceita no bloco ``lancador`` conta: ``comandos``, ``reposicao.nativo`` e o
   ``leitor.executar`` que é ferramenta do ``PATH`` (e não o script da própria pasta);
3. a linha do censo de um comando que o manifesto deixou de declarar sai como morta;
4. os manifestos REAIS de fábrica entram na varredura, comando por comando.

MORDIDA (arrancar a leitura dos manifestos do ``varrer`` e ver as réguas 1, 3 e 4 reprovarem):
é o que o arquivo do portão faz hoje, e o teste de mordida abaixo refaz sem editar nada, pelo
``varrer`` com a leitura trocada por uma que não lê manifesto.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
_SCRIPT = RAIZ / "scripts" / "check_os_contratos_de_fora.py"
_spec = importlib.util.spec_from_file_location("check_os_contratos_de_fora_manifestos", _SCRIPT)
assert _spec and _spec.loader
regua = importlib.util.module_from_spec(_spec)
sys.modules["check_os_contratos_de_fora_manifestos"] = regua
_spec.loader.exec_module(regua)

DE_FABRICA = RAIZ / "src" / "hefesto_dualsense4unix" / "mods" / "de_fabrica"
MANIFESTO = "src/hefesto_dualsense4unix/mods/de_fabrica/novo/hefesto-mod.json"


def _manifesto(lancador: dict[str, object] | None) -> str:
    dado: dict[str, object] = {
        "id": "novo",
        "nome": "Novo",
        "versao": "1",  # (noqa-acento): contrato ASCII
        "api": ">=1,<3",
        "tipos": ["lancador"],
        "permissoes": ["lancador"],  # (noqa-acento): contrato ASCII
    }
    if lancador is not None:
        dado["lancador"] = lancador
    return json.dumps(dado, ensure_ascii=False)


def _arvore(tmp_path: Path, manifestos: dict[str, str], linhas: list[dict[str, str]]) -> Path:
    for rel, texto in manifestos.items():
        destino = tmp_path / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(texto, encoding="utf-8")
    (tmp_path / "docs/data").mkdir(parents=True, exist_ok=True)
    with (tmp_path / "docs/data/contratos-de-fora.csv").open(
        "w", newline="", encoding="utf-8"
    ) as fh:
        w = csv.DictWriter(fh, fieldnames=regua.COLUNAS, lineterminator="\n")
        w.writeheader()
        w.writerows(linhas)
    return tmp_path


def _linha(arquivo: str, alvo: str) -> dict[str, str]:
    return {
        "dono": "lancadores",
        "arquivo": arquivo,
        "alvo": alvo,
        "onde": "*",
        "porta": "oficial",
        "pergunta": "capacidade",
        "forma": "converge",
        "o_que_quebra_se_mudar": "o comando muda de nome",
        "como_o_doctor_ve": "-",
        "motivo": "",
        "sprint_filha": "",
    }


# --- 1. comando de manifesto sem linha reprova; com a linha, passa -----------------------


def test_comando_de_manifesto_sem_linha_reprova(tmp_path: Path) -> None:
    """MORDIDA: sem a leitura dos manifestos o ``varrer`` não vê o comando e a lista vem vazia."""
    manifesto = _manifesto({"rotulo": "Novo", "comandos": ["rodaje"]})
    raiz = _arvore(tmp_path, {MANIFESTO: manifesto}, [])
    queixas = regua.julgar(raiz)
    assert any("SEM LINHA" in q and "cmd:rodaje" in q and MANIFESTO in q for q in queixas), queixas


def test_com_a_linha_o_mesmo_manifesto_passa(tmp_path: Path) -> None:
    raiz = _arvore(
        tmp_path,
        {MANIFESTO: _manifesto({"rotulo": "Novo", "comandos": ["rodaje"]})},
        [_linha(MANIFESTO, "cmd:rodaje")],
    )
    assert regua.julgar(raiz) == []


def test_o_manifesto_fora_de_src_tambem_e_varrido(tmp_path: Path) -> None:
    """O formato é o de qualquer modificação, não só o de fábrica: o nome do arquivo é que vale."""
    fora = "exemplos/uma-mod/hefesto-mod.json"
    raiz = _arvore(tmp_path, {fora: _manifesto({"rotulo": "Novo", "comandos": ["rodaje"]})}, [])
    assert any("SEM LINHA" in q and fora in q for q in regua.julgar(raiz))


# --- 2. o que o conferidor aceita no bloco conta -----------------------------------------


def test_reposicao_nativo_e_leitor_do_path_contam_e_o_script_da_pasta_nao(tmp_path: Path) -> None:
    bloco = {
        "rotulo": "Novo",
        "atalhos": ["novo"],
        "comandos": ["rodaje"],
        "reposicao": {"nome": "Novo", "processos": ["novo"], "nativo": "novo-nativo"},
        "leitor": {"executar": ["python3", "lista.py"]},
    }
    pasta = tmp_path / Path(MANIFESTO).parent
    pasta.mkdir(parents=True)
    contatos = regua.contatos_do_manifesto(_manifesto(bloco), MANIFESTO, pasta)
    assert {c.alvo for c in contatos} == {"cmd:rodaje", "cmd:novo-nativo", "cmd:python3"}

    (pasta / "lista.py").write_text("", encoding="utf-8")
    proprio = dict(bloco, leitor={"executar": ["lista.py"]})
    contatos = regua.contatos_do_manifesto(_manifesto(proprio), MANIFESTO, pasta)
    assert {c.alvo for c in contatos} == {"cmd:rodaje", "cmd:novo-nativo"}, (
        "o script da própria modificação não é ferramenta de fora"
    )


def test_atalho_e_processo_nao_sao_comando() -> None:
    """``atalhos`` são nomes de ``.desktop``; ``processos`` são o que se fecha. Nenhum é lançado."""
    bloco = {
        "rotulo": "Novo",
        "atalhos": ["org.novo.Novo"],
        "reposicao": {"nome": "Novo", "processos": ["novowebhelper"]},
    }
    assert regua.contatos_do_manifesto(_manifesto(bloco), MANIFESTO) == []


def test_manifesto_sem_lancador_nao_tem_contato() -> None:
    assert regua.contatos_do_manifesto(_manifesto(None), MANIFESTO) == []


def test_manifesto_que_nao_e_json_estoura() -> None:
    """Arquivo ilegível não é limpo (como o Python com erro de sintaxe)."""
    with pytest.raises(regua.CatracaTorta, match="não é JSON"):
        regua.contatos_do_manifesto("{ isto não é json", MANIFESTO)


# --- 3. a linha de um comando que o manifesto largou sai como morta ----------------------


def test_linha_de_comando_que_o_manifesto_largou_e_morta(tmp_path: Path) -> None:
    raiz = _arvore(
        tmp_path,
        {MANIFESTO: _manifesto({"rotulo": "Novo", "comandos": ["rodaje"]})},
        [_linha(MANIFESTO, "cmd:rodaje"), _linha(MANIFESTO, "cmd:antigo")],
    )
    queixas = regua.julgar(raiz)
    assert any("MORTA" in q and "cmd:antigo" in q for q in queixas), queixas
    assert not any("cmd:rodaje" in q for q in queixas)


# --- 4. os manifestos reais de fábrica entram na varredura -------------------------------


def _comandos_declarados() -> dict[str, set[str]]:
    achado: dict[str, set[str]] = {}
    for manifesto in sorted(DE_FABRICA.glob("*/hefesto-mod.json")):
        bloco = json.loads(manifesto.read_text(encoding="utf-8")).get("lancador", {})
        achado[manifesto.relative_to(RAIZ).as_posix()] = set(bloco.get("comandos", []))
    return achado


def test_os_comandos_dos_manifestos_de_fabrica_entram_na_varredura() -> None:
    """Os seis lançadores de fábrica declaram comandos; a varredura os acha, um a um.

    MORDIDA: tirar o ``elif`` do manifesto em ``varrer`` — nenhum aparece.
    """
    declarados = _comandos_declarados()
    assert len(declarados) >= 6, sorted(declarados)
    assert sum(len(v) for v in declarados.values()) >= 8
    vistos: dict[str, set[str]] = {}
    for c in regua.varrer(RAIZ):
        if c.arquivo in declarados:
            vistos.setdefault(c.arquivo, set()).add(c.alvo.removeprefix("cmd:"))
    for arquivo, comandos in declarados.items():
        assert comandos <= vistos.get(arquivo, set()), (arquivo, comandos, vistos.get(arquivo))


def test_a_varredura_sem_a_leitura_dos_manifestos_nao_ve_nada_deles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mordida refeita por dentro: com a leitura trocada por uma que não lê, a régua 4 cai.

    É o estado do portão antes desta sprint, e prova que o teste acima mede a leitura e não o
    acaso de o censo ter, por outro arquivo, a mesma linha.
    """
    monkeypatch.setattr(regua, "contatos_do_manifesto", lambda *a, **k: [])
    declarados = _comandos_declarados()
    vistos = {c.arquivo for c in regua.varrer(RAIZ) if c.arquivo in declarados}
    assert vistos == set()
