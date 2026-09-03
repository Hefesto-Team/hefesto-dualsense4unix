"""A ABA 07 NÃO CRAVA COR DE APARELHO — e três formas de cravar eram cegas.

A LEI, e ela é dela (03/09/2026)::

    "imagina que cada pessoa tenha um dualsense diferente. eu mapeei as cores,
     glifos, controles, id e tudo mais. é pro projeto usar esse meu trabalho
     entende? nada hardcoded."

    "os svgs do dualsense, as bordas das fitas das áreas, as escolhas dos
     players com cada controle — tudo isso muda de acordo com o controle
     identificado no canto superior. é white no p1, mas a borda de tudo é
     cosmic red e os svgs não são os que o meu mapa cataloga. isso tá errado"

O QUE ESTA ABA JÁ TINHA, e não se repete aqui:
`scripts/check_identidade_vem_de_cima.py` e
`tests/unit/test_a_aba_07_usa_o_controle_da_fita.py` cobrem DUAS formas de
cravar — o NOME do modelo no texto (`Cosmic Red`) e o `--plastico:` no `style`.

O QUE ELAS NÃO ENXERGAM. Medido nesta árvore em 03/09/2026, envenenando a
`mockup/07-lancadores.html` com uma forma de cada vez e rodando as duas réguas
sobre a página envenenada — a tabela abaixo é a saída daquela corrida::

    página envenenada com          check_identidade_vem_de_cima   a régua irmã
    ---------------------------    ----------------------------   ------------
    "Cosmic Red" no texto                      1  (pega)             1 (pega)
    --plastico:#A51C48                         1  (pega)             1 (pega)
    data-colorway="cosmic-red"                 0  CEGA               0 CEGA
    border-color:#A51C48                       0  CEGA               0 CEGA
    var(--cosmic-red)                          0  CEGA               0 CEGA
    --nova-pink:#ff0000 no esqueleto           0  CEGA               0 CEGA

As três primeiras cegueiras são exatamente as formas que a frase dela nomeia: o
apelido é o que vai num `data-colorway` (*"os svgs não são os que o meu mapa
cataloga"*) e o hexadecimal solto é o que pinta uma borda (*"a borda de tudo é
cosmic red"*). Nenhuma delas escreve "Cosmic Red" em lugar nenhum.

**Esta tabela é uma MEDIÇÃO daquele dia, não um requisito.** Se alguém ampliar
`check_identidade_vem_de_cima.py` para cobrir as quatro, ótimo — este arquivo
não reprova por isso. Reprovar a melhora em vez do defeito é o defeito que esta
casa mais pagou.

A RÉGUA NOVA MORA NO GERADOR, em `interface/aba07.identidade_congelada`, e ela
roda a cada `python3 aba07.py`. O teste a morde pela porta `--conferir`, que lê
um HTML qualquer e não gera nada — assim a regra tem UMA escrita só. Duas
escritas da mesma regra é como o `novo-layout/` divergiu 25 KB calado.

A MORDIDA, e ela é de seis formas — uma por `test_a_regua_morde_*`:
cada `test_a_regua_morde_*` abaixo envenena a página com uma forma e exige
`rc=1`; `test_a_pagina_de_hoje_esta_limpa` exige `rc=0` sobre a página real, e
`test_a_regua_nao_acusa_o_svg_ja_endereçado` exige `rc=0` sobre um SVG ligado
como manda o contrato — acusar quem já está curado é o pior defeito de uma
régua, porque manda consertar o que está certo.
"""
from __future__ import annotations

import csv
import pathlib
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
GERADOR = INTERFACE / "aba07.py"
PAGINA = "07-lancadores.html"

#: A ÂNCORA DO VENENO: o chip `Todos`, que é ESTRUTURA da fita (não nomeia
#: aparelho nenhum) e existe em toda página desta aba. Envenenar em cima dele
#: põe cada forma no lugar em que ela apareceria de verdade — dentro da fita.
ANCORA = '<span class="chip on">Todos</span>'


def _bancada() -> pathlib.Path:
    """A página da BANCADA — o desenho de HOJE, não o publicado.

    Apontar para o publicado daria verde sobre a página congelada, que é a
    armadilha mais cara do `COMO-OLHAR-A-TELA.md`: publicar é ato dela.
    """
    sys.path.insert(0, str(INTERFACE))
    from hefesto_dualsense4unix.interface import onde

    caminho = onde.pagina(PAGINA)
    if not caminho.exists():
        pytest.fail(f"{caminho} não existe — a régua mediria o vazio.")
    return caminho


def _mapa() -> list[dict[str, str]]:
    """As linhas do `docs/data/cores-do-dualsense.csv`, que é o dono dos modelos.

    Digitar aqui um nome, um apelido ou um hexadecimal criaria a segunda lista
    que o CSV existe para não ter.
    """
    bruto = (RAIZ / "docs/data/cores-do-dualsense.csv").read_text(encoding="utf-8")
    linhas = [ln for ln in bruto.splitlines()
              if ln.strip() and not ln.lstrip().startswith("#")]
    return list(csv.DictReader(linhas))


def _conferir(caminho: pathlib.Path) -> subprocess.CompletedProcess[str]:
    """Roda a régua do gerador sobre um HTML, sem gerar nada.

    `cwd` é a pasta da interface porque o gerador faz
    `sys.path.insert(0, Path(__file__).parent)` e importa `onde` e `monta` como
    módulos de topo — é como o `regerar.py` o chama.
    """
    return subprocess.run(
        [sys.executable, str(GERADOR), "--conferir", str(caminho)],
        capture_output=True, text=True, cwd=str(INTERFACE), check=False)


@pytest.fixture
def envenenar(tmp_path):
    """Devolve uma função que põe UM veneno na página real e devolve o caminho."""
    limpa = _bancada().read_text(encoding="utf-8")

    def _por(veneno: str, nome: str) -> pathlib.Path:
        assert ANCORA in limpa, (
            f"a âncora {ANCORA!r} sumiu da página — sem ela o veneno não entra "
            f"e todo caso abaixo passaria sobre a página LIMPA, que é verde "
            f"sobre nada.")
        alvo = tmp_path / f"{nome}.html"
        alvo.write_text(limpa.replace(ANCORA, veneno, 1), encoding="utf-8")
        return alvo

    return _por


# ---------------------------------------------------------------------------
# 1. A PÁGINA DE HOJE — o piso é ZERO, e ele é medido, não prometido
# ---------------------------------------------------------------------------
def test_a_pagina_de_hoje_esta_limpa() -> None:
    """A `07-lancadores` não tem UMA cor de aparelho cravada, por nenhuma forma.

    O CENSO DA LEVA dizia `0 --plastico · 0 data-colorway · 0 hex de zona` para
    esta aba, e ele lia só três formas. Esta régua lê CINCO e o número continua
    zero — a afirmação do censo se sustenta, agora por uma medida mais larga.
    """
    r = _conferir(_bancada())
    assert r.returncode == 0, (
        f"a página da bancada tem cor de aparelho cravada:\n{r.stderr}")


def test_a_pagina_publicada_tambem_esta_limpa() -> None:
    """O que ela VÊ hoje, e não só o que está na bancada.

    As duas páginas são a mesma até ela mandar publicar de novo; medir só a
    bancada deixaria de fora exatamente a tela dela.
    """
    # O nome abaixo é o da pasta em disco, não prosa.
    r = _conferir(INTERFACE / "paginas" / PAGINA)  # (noqa-acento)
    assert r.returncode == 0, (
        f"a página PUBLICADA tem cor de aparelho cravada:\n{r.stderr}")


# ---------------------------------------------------------------------------
# 2. AS CINCO MORDIDAS — uma por forma
# ---------------------------------------------------------------------------
def test_a_regua_morde_o_nome_do_modelo(envenenar) -> None:
    """`Cosmic Red` escrito na tela. A forma que as duas réguas velhas já pegam."""
    alvo = envenenar(f"{ANCORA}<span>Cosmic Red</span>", "nome")
    r = _conferir(alvo)
    assert r.returncode == 1, "a régua passou com um nome de modelo na página"
    assert "Cosmic Red" in r.stderr, r.stderr


def test_a_regua_morde_o_plastico_cravado(envenenar) -> None:
    """`--plastico:` no `style`. A outra que as réguas velhas já pegam."""
    alvo = envenenar('<span class="chip on" style="--plastico:#A51C48">Todos</span>',
                     "plastico")
    r = _conferir(alvo)
    assert r.returncode == 1, "a régua passou com um `--plastico:` cravado"
    assert "--plastico" in r.stderr, r.stderr


def test_a_regua_morde_o_apelido_do_modelo(envenenar) -> None:
    """`data-colorway="cosmic-red"` — CEGA nas duas réguas velhas.

    É a forma de *"os svgs não são os que o meu mapa cataloga"*: o SVG do
    desenho nasce com o colorway do mockup, e não há um "Cosmic Red" na página
    para a régua por nome encontrar.
    """
    alvo = envenenar('<svg class="ds-svg" data-colorway="cosmic-red"></svg>',
                     "apelido")
    r = _conferir(alvo)
    assert r.returncode == 1, "a régua passou com o apelido de um modelo cravado"
    assert "cosmic-red" in r.stderr, r.stderr


def test_a_regua_morde_o_hexadecimal_do_mapa(envenenar) -> None:
    """`border-color:#A51C48` — CEGA nas duas réguas velhas.

    É a forma de *"a borda de tudo é cosmic red"*: um hexadecimal que o mapa
    dela cataloga, sem nome e sem `--plastico:` para denunciá-lo.
    """
    alvo = envenenar('<span class="chip on" style="border-color:#A51C48">Todos</span>',
                     "hex")
    r = _conferir(alvo)
    assert r.returncode == 1, "a régua passou com um hexadecimal do mapa cravado"
    assert "#a51c48" in r.stderr.lower(), r.stderr


def test_a_regua_morde_a_paleta_de_cinco_do_esqueleto(envenenar) -> None:
    """`var(--cosmic-red)` — a mais silenciosa das três cegueiras.

    O `topo.html` declara cinco plásticos no `:root` das dez páginas. Eles
    respondem por 5 dos 28 modelos do mapa; usá-los é escolher a cor de um
    aparelho que pode não ser o dela, sem escrever nome, apelido nem hexa.
    """
    alvo = envenenar(
        '<span class="chip on" style="border-color:var(--cosmic-red)">Todos</span>',
        "var")
    r = _conferir(alvo)
    assert r.returncode == 1, "a régua passou com a paleta do esqueleto emprestada"
    assert "var(--cosmic-red)" in r.stderr, r.stderr


def test_a_regua_morde_o_plastico_do_esqueleto_que_diverge_do_mapa(tmp_path) -> None:
    """A ISENÇÃO DAS CINCO É MEDIDA, e não decretada.

    `monta.monta()` reescreve o valor das cinco variáveis com `cor_da_zona`,
    que lê o CSV. A régua confere cada uma contra o mapa em vez de acreditar:
    um sexto plástico digitado à mão no esqueleto, ou um dos cinco divergindo,
    é acusado. **Isenção sem razão é ponto cego com nome bonito.**
    """
    limpa = _bancada().read_text(encoding="utf-8")
    do_mapa = [ln for ln in _mapa() if (ln.get("id") or "").strip() == "nova-pink"]
    assert do_mapa, "o `nova-pink` sumiu do mapa — o caso mediria o vazio"
    agulha = "--nova-pink:"
    assert agulha in limpa, (
        f"{agulha!r} não está mais na página: ou o esqueleto parou de declarar "
        f"os cinco plásticos, ou o nome mudou — e este caso ficaria verde "
        f"sobre nada.")
    i = limpa.index(agulha)
    fim = limpa.index(";", i)
    alvo = tmp_path / "sexto.html"
    alvo.write_text(limpa[:i] + agulha + "#ff0000" + limpa[fim:], encoding="utf-8")

    r = _conferir(alvo)
    assert r.returncode == 1, (
        "a régua aceitou um plástico do esqueleto que o mapa dela contradiz")
    assert "nova-pink" in r.stderr and "#ff0000" in r.stderr, r.stderr


# ---------------------------------------------------------------------------
# 3. A CONTRAPROVA — a régua não acusa quem já está curado
# ---------------------------------------------------------------------------
def test_a_regua_nao_acusa_o_svg_ja_enderecado(envenenar) -> None:
    """Um `data-colorway` COM o endereço do contrato passa, e tem de passar.

    O CONTRATO vem da frente base desta leva (03/09/2026):
    `data-hef-alvo="atributo"` mais `data-hef-atributo="data-colorway"` no MESMO
    elemento — o par em atributos separados, como o alvo `classe` já faz com
    `data-hef-classe`/`data-hef-quando`. Com ele o produto reescreve o colorway
    a cada tique, e o desenho deixa de mandar.

    ESTA ABA NÃO TEM SVG DE CONTROLE HOJE (medido: o único `<svg>` da página é
    a logo do Hefesto). O caso existe para o dia em que ela ganhar um: sem ele,
    a régua nova estaria pronta para acusar o conserto.
    """
    alvo = envenenar(
        '<svg data-campo="desenho" data-hef-alvo="atributo"'
        ' data-hef-atributo="data-colorway" data-colorway=""></svg>',
        "endereçado")
    r = _conferir(alvo)
    assert r.returncode == 0, (
        f"a régua acusou um SVG ligado como manda o contrato — ela mandaria "
        f"desfazer o conserto:\n{r.stderr}")


# ---------------------------------------------------------------------------
# 4. OS VINTE E OITO — o chip não conhece uma tabela de quatro
# ---------------------------------------------------------------------------
def test_o_chip_da_fita_nomeia_os_vinte_e_oito_modelos() -> None:
    """Ela mapeou 28; o desenho usa 4. O chip tem de servir aos 28.

    *"imagina que cada pessoa tenha um dualsense diferente… nada hardcoded"* —
    e a forma de provar que não há tabela nenhuma é passar o mapa inteiro pelo
    chip e cobrar o nome de volta, um por um. Quem escrever aqui um
    `if nome in (…os quatro do desenho…)` reprova neste caso, e não em nenhum
    outro desta casa.
    """
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    nomes = sorted({(ln.get("nome") or "").strip() for ln in _mapa()} - {""})
    assert len(nomes) == 28, (
        f"o mapa dela tem {len(nomes)} modelos e este caso esperava 28. Se ela "
        f"mapeou mais um, o número sobe — o que não pode é o chip parar nos "
        f"quatro do desenho.")

    faltaram = []
    for nome in nomes:
        mesa = [{"pref": "p1", "jogador": 1, "cor": "sim", "nome": nome,
                 "via": "USB", "transporte": "usb", "alvo": True}]
        fita = a07.fita_html(mesa)
        if nome not in fita:
            faltaram.append(nome)
    assert not faltaram, (
        f"{len(faltaram)} dos {len(nomes)} modelos do mapa não chegam ao chip "
        f"da fita: {faltaram}. Quem tiver um deles vê a cor de outro aparelho.")


def test_o_chip_nao_nomeia_modelo_nenhum_com_a_mesa_vazia() -> None:
    """SEM COR LIDA, SEM COR NA TELA — e sem mesa, sem chip.

    Pelo rádio a leitura de cor às vezes não chega, e a regra dela é que campo
    sem informação não mostra nada. Cair de volta nos `CONECTADOS` do desenho é
    exatamente o defeito que esta leva existe para matar: era assim que a fita
    dizia `P1 · Cosmic Red · USB` com um White na mesa dela.
    """
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    fita = a07.fita_html([])
    nomes = {(ln.get("nome") or "").strip() for ln in _mapa()} - {""}
    achados = sorted(n for n in nomes if n in fita)
    assert not achados, (
        f"a fita de uma mesa VAZIA nomeia {achados} — o desenho voltou a mandar "
        f"na tela do produto.")
    assert "Selecionar:" in fita and "Todos" in fita, (
        f"a fita perdeu a ESTRUTURA e não só a identidade:\n{fita}")
