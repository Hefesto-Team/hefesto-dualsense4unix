"""A aritmética de caminho dos instrumentos, e o `rc` que não pode mentir.

DOIS DEFEITOS MEDIDOS EM 04/09/2026, e os dois estavam vivos há tempo:

1. **`RAIZ = AQUI.parents[1]` estava errado por um.** Com `AQUI` em
   `<árvore>/src/hefesto_dualsense4unix/interface`, `parents[1]` é o **`src`** —
   não a árvore. Logo `RAIZ / "src"` resolvia para `<árvore>/src/src`, que não
   existe. Duas consequências, as duas caladas:

   - o `sys.path.insert` virava no-op, e o piloto rodado à mão importava o
     produto de OUTRA árvore pelo `.pth` do editable install. É o
     `SRC-DESTA-ARVORE-01` pela TERCEIRA porta — a suíte e os portões já
     tinham sido curados no mesmo dia, e o script à mão não;
   - `sistema_viva.PAGINA` e `controles_vivos.PAGINA` apontavam para um HTML
     inexistente.

   É a assinatura de 03/09 de novo: **as pastas mudaram de nome e a aritmética
   não foi junto.** Estes arquivos nasceram em `novo-layout/_ferramentas/`,
   onde `parents[1]` ERA a árvore.

2. **`--prova-de-mockup` imprimia `ERRO DE CARGA` e saía `rc=0` sem medir uma
   aba.** Quem a chamasse num portão leria VERDE sobre o vazio. A causa era uma
   corrida — a régua navegava antes de a carga inicial confirmar — e o estrago
   era a forma de sair, não a corrida.
"""

from __future__ import annotations

import os
import subprocess
import sys
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

#: Os arquivos que calculam a árvore a partir de si mesmos.
_COM_RAIZ = ("hefesto_vivo.py", "controles_vivos.py", "sistema_viva.py", "casamento.py")


@pytest.mark.parametrize("nome", _COM_RAIZ)
def test_a_raiz_calculada_e_a_arvore_e_nao_o_src(nome: str) -> None:
    """A METADE QUE MEDE: a conta é REFEITA aqui, não lida no texto."""
    fonte = (INTERFACE / nome).read_text(encoding="utf-8")
    m = re.search(r"^RAIZ = AQUI\.parents\[(\d)\]", fonte, re.M)
    assert m, f"{nome}: não achei o cálculo da RAIZ"
    nivel = int(m.group(1))

    aqui = INTERFACE
    raiz = aqui.parents[nivel]
    assert (raiz / "src").is_dir(), (
        f"{nome}: `AQUI.parents[{nivel}] / 'src'` dá {raiz / 'src'}, que NÃO "
        "EXISTE. Com `[1]` a conta cai no próprio `src` e o `RAIZ / \"src\"` "
        "vira `src/src` — o defeito de 04/09/2026."
    )
    assert raiz == RAIZ, f"{nome}: a RAIZ calculada ({raiz}) não é a árvore"


@pytest.mark.parametrize("nome", ("controles_vivos.py", "sistema_viva.py"))
def test_a_pagina_que_o_instrumento_abre_existe_no_disco(nome: str) -> None:
    """E o efeito visível do erro: um HTML que não está lá."""
    fonte = (INTERFACE / nome).read_text(encoding="utf-8")
    m = re.search(r'^PAGINA = RAIZ / "src" / (.+?)(?:  #|$)', fonte, re.M)
    assert m, f"{nome}: não achei o cálculo da PAGINA"
    pedacos = [p.strip().strip('"') for p in m.group(1).split(" / ")]
    caminho = RAIZ / "src"
    for p in pedacos:
        caminho = caminho / p
    assert caminho.is_file(), (
        f"{nome}: `PAGINA` aponta para {caminho}, que não existe no disco. "
        "O instrumento abriria o vazio."
    )


def test_a_regua_do_mockup_nao_sai_verde_sobre_o_vazio() -> None:
    """Página morta REPROVA — medido rodando o piloto, não lendo o fonte dele.

    **ESTA RÉGUA DIGITAVA, E POR ISSO REPROVOU A MELHORA — 05/09/2026.** Ela
    cobrava a linha `if e_regua and piloto.tela.morreu is not None:` letra por
    letra. Quando a guarda ficou mais ESTRITA — o `e_regua` saiu, e toda
    execução com página morta passou a reprovar, não só as três provas —, a
    régua ficou vermelha sobre a cura. É o defeito que esta casa nomeou onze
    vezes numa leva só: *a régua digita o que devia LER*.

    O QUE ELA MEDE AGORA é o comportamento: roda o piloto oculto pedindo uma
    página que não existe e exige `rc != 0`. Custa ~6 s e não abre nada na tela
    dela (`--oculta` é `Gtk.OffscreenWindow`).

    A MORDIDA: devolva o `e_regua` ao gate de saída e este teste reprova — sem
    régua ligada, `--abre 99` volta a sair `rc=0` sobre uma janela morta.
    """
    piloto = INTERFACE / "hefesto_vivo.py"
    ambiente = dict(os.environ, PYTHONPATH=str(RAIZ / "src"))
    # `--abre 99` não existe: o `_ir` confere o disco e mata a janela. É o
    # caminho mais barato até uma página morta — sem daemon, sem perfil, sem
    # tocar em nada dela.
    fim = subprocess.run(
        [sys.executable, str(piloto), "--oculta", "--abre", "99", "--segundos", "3"],
        capture_output=True, text=True, env=ambiente, timeout=180, check=False,
    )
    assert "ERRO DE CARGA" in fim.stderr, (
        "o piloto nem chegou a acusar a página morta — a medição não aconteceu "
        f"e o resto deste teste não vale nada. stderr: {fim.stderr[-400:]}")
    assert fim.returncode != 0, (
        "o piloto imprimiu `ERRO DE CARGA` e saiu rc=0: quem o chamar num "
        "script lê VERDE sobre uma janela morta. Uma régua que imprime o erro "
        "e sai zero é pior que régua nenhuma.")

    # AS DUAS GUARDAS QUE SOBRAM SÃO LIDAS NO FONTE, e não rodadas, por
    # honestidade de custo: exercitá-las de verdade exigiria uma execução de
    # `--prova-de-mockup` inteira (dez abas) por asserção. O que se lê aqui é
    # a EXISTÊNCIA da guarda, não a sua letra — por isso o regex casa a forma
    # (`if <condição>: ... raise SystemExit(1)`) e não a linha digitada.
    fonte = (INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8")
    assert re.search(
        r"if args\.prova_de_mockup and not piloto\.visitadas:.*?raise SystemExit\(1\)",
        fonte, re.S,
    ), (
        "sumiu a guarda do ZERO: `--prova-de-mockup` sem visitar aba nenhuma "
        "tem de REPROVAR. Zero é erro, não silêncio."
    )
    # E a corrida que a causou: a espera é pela PÁGINA, não pelo relógio — e
    # ela vale para os QUATRO chamadores, não só para o `--prova-de-mockup`.
    # A cura nasceu em 04/09 aplicada a um só, e em 05/09 `--abre 10` ainda
    # reproduzia o `título ''` em toda execução: quem conhece a causa e cobre
    # um chamador deixa a próxima pessoa remedindo o mesmo defeito.
    assert "if not piloto.tela.na_aba:" in fonte, (
        "a espera voltou a partir de um `timeout` fixo: o piloto navegava "
        "antes de a carga inicial confirmar, e a confirmação chegava com o "
        "título vazio."
    )
    #
    # O PAREAMENTO, e não a presença: a primeira versão desta asserção pedia
    # "`_quando_a_pagina_estiver_de_pe` aparece E `piloto._ir(args.abre)`
    # aparece", e passou com a cura arrancada — trocar a espera por um
    # `GLib.timeout_add(400, ...)` deixa as duas frases no arquivo, em linhas
    # diferentes. O que se cobra é o chamador DENTRO da espera.
    for chamador in ("piloto._provar_mockup", "piloto._provar_no_aparelho",
                     "piloto._provar_cliques", "piloto._ir(args.abre)"):
        assert re.search(
            r"_quando_a_pagina_estiver_de_pe\(\s*(?:lambda:\s*)?[^)]*?"
            + re.escape(chamador), fonte, re.S), (
            f"`{chamador}` saiu de dentro de `_quando_a_pagina_estiver_de_pe`. "
            "Um relógio fixo aqui faz o piloto navegar antes de a carga "
            "confirmar — e a janela morre acusando a página, que não tem "
            "culpa. Foi assim que `--abre 10` reprovou em toda execução.")


def test_a_janela_guarda_o_motivo_da_morte() -> None:
    """A outra metade, no dono: sem o atributo, o piloto não teria o que ler."""
    fonte = (
        RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "ponte_da_tela.py"
    ).read_text(encoding="utf-8")
    assert "self.morreu: str | None = None" in fonte
    assert "self.morreu = motivo" in fonte
