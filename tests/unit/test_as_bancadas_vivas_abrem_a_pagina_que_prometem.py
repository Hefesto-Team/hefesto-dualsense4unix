#!/usr/bin/env python3
"""As cinco bancadas vivas abrem a página que prometem — e não saem verdes sem ela.

**06/09/2026, costura da ONDA C.** A `ONDA5-07-03` achou que a bancada da aba
Jogar apontava para `AQUI.parent / "01-jogar.html"` — endereço certo enquanto
ela morava em `layout/_ferramentas/`, e morto desde a mudança para `src/`. O
sintoma era o pior possível: ela imprimia *"ERRO DE CARGA"*, ficava em
`voltas: 0` e **devolvia `rc=0`**. Quem a rodasse num laço, num portão ou num
relatório leria SUCESSO sobre uma janela vazia.

Quem costurou mediu as outras quatro e achou **a gêmea**: `perfis_vivos.py`
apontava para `hefesto_dualsense4unix/10-perfis.html`, que também não existe.
Medido antes da cura, com `--oculta --segundos 2`:

    ERRO DE CARGA: carregou OUTRA página: título ''
    voltas: 0 · remontagens: 0 · gestos: 0
    rc=0

Depois: `voltas: 4 · remontagens: 1`, e `rc=2` quando a página não está lá.

**ESTA RÉGUA NÃO IMPORTA AS BANCADAS, e a recusa é medida:** `perfis_vivos.py`
faz `import aba10` no topo, e os geradores escrevem a bancada dela no disco como
efeito de um `import` — foi assim que `mockup/05-vibracao.html` mudou durante uma
COLETA do pytest em 06/09. Uma régua que importasse estes cinco reescreveria o
desenho aprovado dela a cada volta da suíte. Então ela LÊ O FONTE e resolve o
caminho, que é o que ela precisa saber de qualquer jeito.

A MORDIDA: troque o `PAGINA` de qualquer uma das cinco por um nome que não
existe, e esta régua reprova nomeando o arquivo e o caminho.
"""
from __future__ import annotations

import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

#: As bancadas vivas: um arquivo por aba que ela abre para OLHAR a tela nova.
#: Quem acrescentar a sexta acrescenta o nome aqui — uma bancada fora desta
#: lista é uma bancada sem esta régua.
BANCADAS = (
    "jogar_vivo.py",
    "controles_vivos.py",
    "conexoes_vivas.py",
    "sistema_viva.py",
    "perfis_vivos.py",
)


def _caminho_da_pagina(fonte: str) -> pathlib.Path | None:
    """Resolve o `PAGINA = …` do fonte, sem importar o módulo.

    As quatro formas que existem hoje, e todas terminam no mesmo lugar:
    `onde.PUBLICADO / "NN.html"`, a pasta do produto, a mesma com `RAIZ_DEV`, e
    a forma morta `AQUI.parent / "NN.html"`.

    O nome da pasta aparece sem acento porque ele é o NOME NO DISCO, e não
    prosa: pela regra da casa, caminho mantém a forma de fábrica. Acentuá-lo
    quebraria as duas comparações abaixo, que casam com o texto do fonte.
    """
    m = re.search(r"^PAGINA = (.+)$", fonte, re.M)
    if m is None:
        return None
    expr = m.group(1)
    nome = re.search(r'"([\w.-]+\.html)"', expr)
    if nome is None:
        return None
    if "onde.PUBLICADO" in expr or '"paginas"' in expr:  # (noqa-acento) pasta
        return INTERFACE / "paginas" / nome.group(1)  # (noqa-acento) pasta
    # `AQUI.parent` é `src/hefesto_dualsense4unix/` — a forma morta.
    return INTERFACE.parent / nome.group(1)


def test_as_cinco_bancadas_apontam_para_uma_pagina_que_existe() -> None:
    faltam = []
    for nome in BANCADAS:
        arq = INTERFACE / nome
        assert arq.exists(), f"a bancada {nome} sumiu — a lista desta régua envelheceu"
        alvo = _caminho_da_pagina(arq.read_text(encoding="utf-8"))
        assert alvo is not None, (
            f"{nome} não declara `PAGINA = …` numa forma que esta régua leia — "
            "declare-a como as outras quatro, ou ensine a régua a lê-la")
        if not alvo.exists():
            faltam.append(f"{nome} -> {alvo}")
    assert not faltam, (
        "bancada viva apontando para página que não existe:\n  "
        + "\n  ".join(faltam)
        + "\n\nO sintoma não é erro: é `ERRO DE CARGA`, `voltas: 0` e `rc=0` — "
          "verde sobre uma janela vazia.")


def test_as_cinco_bancadas_recusam_a_pagina_ausente_e_a_volta_zero() -> None:
    """A guarda que faz o `rc` contar. Sem ela, achar o defeito acima é sorte."""
    sem_guarda_da_pagina, sem_guarda_da_volta = [], []
    for nome in BANCADAS:
        fonte = (INTERFACE / nome).read_text(encoding="utf-8")
        if "if not PAGINA.exists():" not in fonte:
            sem_guarda_da_pagina.append(nome)
        # A FRASE, e não a forma do contador: a `sistema_viva` guarda os
        # custos do tique em `janela.valores` e as outras quatro têm um
        # `self.voltas`. Cobrar a forma faria esta régua reprovar quem está
        # certo — e cobrar a frase é o que ela quer de fato, porque é a frase
        # que quem roda a bancada lê.
        if "a bancada não deu uma volta" not in fonte:
            sem_guarda_da_volta.append(nome)
    assert not sem_guarda_da_pagina, (
        f"{sem_guarda_da_pagina} não conferem se a página existe antes de subir "
        "a janela — devolveriam `rc=0` sobre o vazio")
    assert not sem_guarda_da_volta, (
        f"{sem_guarda_da_volta} não reprovam quando a bancada não deu uma volta "
        "— uma bancada que não girou não mediu nada, e não sai verde")
