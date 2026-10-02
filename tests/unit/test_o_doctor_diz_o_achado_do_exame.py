"""O `doctor` diz o ACHADO do exame, não a etiqueta — e no endereço que existe."""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys


RAIZ = pathlib.Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts/doctor.sh"


def _snippet_do_exame() -> str:
    """O python embutido no `check_exame_da_mesa`, lido do fonte do doctor."""
    fonte = DOCTOR.read_text(encoding="utf-8")
    inicio = fonte.index("check_exame_da_mesa() {")
    fim = fonte.index("\n}\n", inicio)
    m = re.search(r'\| *"\$\{py\}" -c \'\n(.*?)\n\' 2>/dev/null\)"',
                  fonte[inicio:fim], re.S)
    assert m, ("não achei o python do `check_exame_da_mesa` no `doctor.sh` — "
               "ou ele mudou de forma, e esta régua ficaria verde sobre nada")
    return m.group(1)


def _rodar(censo: dict) -> str:
    r = subprocess.run(
        [sys.executable, "-c", _snippet_do_exame()],
        input=json.dumps(censo), capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    return r.stdout


def _censo(*porques: str) -> dict:
    """Um censo de mentira com N ordens — todas com o MESMO rótulo."""
    return {"veredito": "atencao",  # (noqa-acento): valor do JSON, ASCII
            "itens": [{"chave": f"r{i}", "estado": "atencao",  # (noqa-acento): valor do JSON
                       "rotulo": "Mudança recomendada", "porque": p}
                      for i, p in enumerate(porques)]}


def test_ha_snippet_para_medir() -> None:
    """Conjunto vazio não é verde."""
    assert "veredito=" in _snippet_do_exame()


def test_a_linha_traz_o_achado_e_nao_so_a_etiqueta() -> None:
    saida = _rodar(_censo("dois rádios em entradas vizinhas"))
    assert "dois rádios em entradas vizinhas" in saida, (
        f"o doctor não disse o achado, só a etiqueta:\n{saida}")


def test_dois_achados_diferentes_dao_duas_linhas_diferentes() -> None:
    """A MORDIDA QUE PROVOU A CAUSA, virada régua."""
    a = _rodar(_censo("o teclado depende do hub"))
    b = _rodar(_censo("dois rádios em entradas vizinhas"))
    assert a != b, (
        "dois achados DIFERENTES produziram a mesma saída. O doctor voltou a "
        f"ler a etiqueta em vez do achado:\n{a}")


def test_cada_item_sai_numa_linha_propria() -> None:
    """Três ordens → três linhas. Juntá-las com `;` era metade do defeito."""
    saida = _rodar(_censo("primeiro", "segundo", "terceiro"))
    itens = [x for x in saida.splitlines() if x.startswith("item\t")]
    assert len(itens) == 3, f"esperava 3 linhas de item e vieram {len(itens)}:\n{saida}"
    for esperado in ("primeiro", "segundo", "terceiro"):
        assert any(esperado in x for x in itens), f"{esperado!r} sumiu:\n{saida}"


def test_o_certo_nao_vira_linha() -> None:
    """Conferência que passou não é achado — ela não ocupa linha no terminal."""
    censo = {"veredito": "certo",
             "itens": [{"chave": "k", "estado": "certo",
                        "rotulo": "Energia", "porque": "tudo bem"}]}
    itens = [x for x in _rodar(censo).splitlines() if x.startswith("item\t")]
    assert not itens, f"um `certo` virou linha de achado: {itens}"


def test_o_doctor_aponta_para_uma_aba_que_existe() -> None:
    """*"aba Configurações"* não existe em lugar nenhum do produto."""
    bloco = re.search(r"check_exame_da_mesa\(\)\s*\{(.*?)\n\}",
                      DOCTOR.read_text(encoding="utf-8"), re.S)
    assert bloco, "não achei o `check_exame_da_mesa` no doctor"
    corpo = bloco.group(1)
    sem_comentario = "\n".join(
        x for x in corpo.splitlines() if not x.lstrip().startswith("#"))
    assert "aba Configurações" not in sem_comentario, (
        "o `check_exame_da_mesa` voltou a mandar a pessoa para a aba "
        "Configurações, que não existe. O endereço é: aba Conexões, seção "
        "Check-up.")
    assert "Conexões" in sem_comentario, (
        "o doctor parou de dizer ONDE olhar na tela")
