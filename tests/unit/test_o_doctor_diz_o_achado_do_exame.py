"""O `doctor` diz o ACHADO do exame, não a etiqueta — e no endereço que existe.

`EXAME-DA-MESA-03` — 19/09/2026.

**O QUE ELE FAZIA:** juntava `i["rotulo"]` de cada item. Toda ordem de serviço
nasce com o MESMO rótulo constante (`ordens_da_mesa.ROTULO_DA_ORDEM`), então
três ordens abertas viravam três cópias de *"Mudança recomendada"* — o terminal
dizendo a mesma palavra N vezes, sem um endereço sequer.

**A PROVA DA CAUSA É UMA MORDIDA:** trocar o `porque` de uma ordem deixava a
linha do doctor **byte-idêntica**. É o que `test_dois_achados_diferentes_dao_
duas_linhas_diferentes` trava.

**E É O SEGUNDO CHAMADOR DE UMA CURA DE 02/09**, quando a TELA passou a
publicar `porque` como `achado`. O doctor ficou para trás — a assinatura desta
casa: *quando a cura conhece a causa, ela cobre TODOS os chamadores*.

A RÉGUA MEDE O SNIPPET PYTHON EMBUTIDO NO `doctor.sh`, lido do fonte. Não roda
o doctor inteiro de propósito: ele toca `busctl`, `pactl` e o socket do daemon
VIVO dela, e ela está usando a máquina.
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys


RAIZ = pathlib.Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts/doctor.sh"


def _snippet_do_exame() -> str:
    """O python embutido no `check_exame_da_mesa`, lido do fonte do doctor.

    LIDO E NÃO COPIADO: uma cópia aqui envelheceria sozinha, e a régua passaria
    a medir um programa que o doctor não roda mais — que é a forma exata do
    defeito que esta casa chama de *instrumento apontando para outra coisa*.
    """
    fonte = DOCTOR.read_text(encoding="utf-8")
    # O SEGUNDO `py -c` do bloco: o primeiro roda `--censo`, o segundo resume.
    m = re.search(r'\| *"\$\{py\}" -c \'\n(.*?)\n\' 2>/dev/null\)"',
                  fonte, re.S)
    assert m, ("não achei o python do `check_exame_da_mesa` no `doctor.sh` — "
               "ou ele mudou de forma, e esta régua ficaria verde sobre nada")
    return m.group(1)


def _rodar(censo: dict) -> str:
    # O INTERPRETADOR É O DESTA VENV, não entrada livre.
    r = subprocess.run(
        [sys.executable, "-c", _snippet_do_exame()],
        input=json.dumps(censo), capture_output=True, text=True, check=False)
    assert r.returncode == 0, r.stderr
    return r.stdout


def _censo(*porques: str) -> dict:
    """Um censo de mentira com N ordens — todas com o MESMO rótulo.

    O rótulo repetido é o ponto: é assim que o exame real devolve as ordens, e
    é o que fazia o doctor dizer a mesma palavra N vezes.
    """
    return {"veredito": "atencao",  # (noqa-acento): valor do JSON, ASCII
            "itens": [{"chave": f"r{i}", "estado": "atencao",  # (noqa-acento)
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
    """A MORDIDA QUE PROVOU A CAUSA, virada régua.

    Com o código de antes, estas duas saídas eram BYTE-IDÊNTICAS: os dois itens
    tinham o mesmo `rotulo`, e o `porque` nunca era lido.
    """
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
    """*"aba Configurações"* não existe em lugar nenhum do produto.

    As dez abas são `01-jogar` a `10-perfis`. O exame mora na seção **Check-up**
    da aba **Conexões**. Quem lesse o terminal procuraria uma aba que não está
    lá — e a tela é para qualquer pessoa, não só para quem conhece a história
    da janela GTK que tinha esse nome.
    """
    bloco = re.search(r"check_exame_da_mesa\(\)\s*\{(.*?)\n\}",
                      DOCTOR.read_text(encoding="utf-8"), re.S)
    assert bloco, "não achei o `check_exame_da_mesa` no doctor"
    corpo = bloco.group(1)
    # O COMENTÁRIO QUE EXPLICA O ERRO CITA A PALAVRA, e não pode contar como
    # ocorrência — é a armadilha de prosa que esta casa já pagou cinco vezes.
    sem_comentario = "\n".join(
        x for x in corpo.splitlines() if not x.lstrip().startswith("#"))
    assert "aba Configurações" not in sem_comentario, (
        "o `check_exame_da_mesa` voltou a mandar a pessoa para a aba "
        "Configurações, que não existe. O endereço é: aba Conexões, seção "
        "Check-up.")
    assert "Conexões" in sem_comentario, (
        "o doctor parou de dizer ONDE olhar na tela")
