#!/usr/bin/env python3
"""O CARTÃO CARREGA O MESMO ENDEREÇO EM TODO ESTADO — aba 07, Lançadores.

A RÉGUA MORA NO GERADOR (`interface/aba07.py`, `_INSTAVEIS` e
`_SEM_OBRIGATORIOS`), e roda a cada `python3 aba07.py`. Este teste a morde pela
porta do IMPORT: as duas checagens correm no nível do módulo, e o gerador só
escreve dentro do `if __name__ == "__main__"` — então `import aba07` roda a
régua inteira **sem tocar a bancada dela**. É a mesma guarda que o
`test_a_palavra_do_transporte_tem_um_dono_so` cobra.

O DEFEITO QUE ELA EXISTE PARA IMPEDIR foi medido em 07/09/2026 com os quatro
DualSense dela na mesa, nas abas por CONTROLE (01-06, 08): o daemon publica
quatro, a carga chega com os quatro, e a tela mostra DOIS. A causa é um ramo
separado para o lugar vazio, que devolve um cartão **sem nenhum `data-campo`
por dentro** — o pintor procura o endereço DENTRO do bloco daquele controle
(`hefesto_vivo.achar`), e um bloco sem endereço come a carga em silêncio.

ESTA ABA NÃO TEM CARTÃO POR CONTROLE: `data-controle` não aparece uma vez
sequer no gerador nem na página publicada, porque nenhum dos cinco impedimentos
de `prontuario_dos_jogos` recebe controle. O cartão daqui é por LANÇADOR, e o
eixo do mesmo defeito é o `selo` — `ok`, `warn`, `off`, `nao_sei`.

POR QUE A RÉGUA VELHA NÃO BASTAVA, e é o ponto deste arquivo: o `_FALTAM` lê o
`MIOLO`, e o `MIOLO` sai de `cartoes(None)` — o estado de PARTIDA, em que os
seis cartões nascem `nao_sei`. A página publicada tem `class="lanc ausente"`
seis vezes e nenhuma outra. Um ramo que largasse um endereço no estado `ok`
passaria verde e quebraria **exatamente na máquina dela**, que é onde os
lançadores são achados. Régua que só vê um estado mede um instante.

AS DUAS MORDIDAS abaixo são as duas coisas que o `_FALTAM` não alcança:

    tira o `-diz` só no estado `ok`      → `_INSTAVEIS` reprova
                                           (`_FALTAM` fica VERDE: o MIOLO é
                                            todo `nao_sei` e não perdeu nada)
    move o `-diz` do heroic para o       → `_SEM_OBRIGATORIOS` reprova
    cartão da steam, em todo estado        (`_FALTAM` fica VERDE: ele testa
                                            substring no MIOLO inteiro, e o
                                            endereço continua lá — no cartão
                                            errado)
"""
import io
import pathlib
import subprocess
import sys
import tokenize

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

#: O trecho do `_FALTAM`, a régua VELHA. As duas mordidas exigem que ela NÃO
#: seja quem reprovou — senão o teste passaria sem provar nada sobre a nova.
VELHA = "endereço(s) que o pacote pinta não existem no"


def _importar(veneno: str) -> subprocess.CompletedProcess[str]:
    """Importa o gerador com `um_cartao` envenenado, e devolve o que ele disse.

    `cwd` é a pasta da interface porque o gerador importa `onde` e `monta` como
    módulos de topo — é como o `regerar.py` o chama. O veneno entra por
    `sys.modules`: o `aba07` faz `import desenho_dos_lancadores as dl`, e o
    módulo já está carregado e trocado quando ele chega lá.
    """
    programa = (
        "import sys, re\n"
        "import desenho_dos_lancadores as dl\n"
        "_orig = dl.um_cartao\n"
        f"{veneno}\n"
        "dl.um_cartao = quebrado\n"
        "dl.cartoes_html = lambda ls: '\\n'.join(quebrado(x) for x in ls)\n"
        "import aba07\n"
    )
    return subprocess.run([sys.executable, "-c", programa],
                          capture_output=True, text=True,
                          cwd=str(INTERFACE), check=False)


def test_a_pagina_de_hoje_passa():
    """Sem veneno o gerador importa limpo — a régua não reprova o que está certo."""
    r = subprocess.run([sys.executable, "-c", "import aba07"],
                       capture_output=True, text=True,
                       cwd=str(INTERFACE), check=False)
    assert r.returncode == 0, (
        "o gerador da aba 07 reprovou a si mesmo sem veneno nenhum:\n"
        f"{r.stderr}{r.stdout}")


def test_a_regua_morde_o_endereco_que_muda_com_o_estado():
    """Um endereço que só existe num `selo` é pintura perdida nos outros três."""
    r = _importar(
        "def quebrado(l):\n"
        "    h = _orig(l)\n"
        "    if l.selo == 'ok':\n"
        "        h = re.sub(r'\\sdata-campo=\"[^\"]*-diz\"', '', h)\n"
        "    return h")
    assert r.returncode != 0, (
        "arranquei o `-diz` do estado `ok` e o gerador passou — a régua do "
        "estado não mede nada")
    assert "mudam de ENDEREÇO conforme o estado" in r.stderr, (
        f"reprovou por outra coisa que não a régua nova:\n{r.stderr}")
    assert VELHA not in r.stderr, (
        "quem reprovou foi o `_FALTAM`, a régua velha — então esta mordida não "
        "prova que a nova alcança o que a velha não vê. O MIOLO é todo "
        f"`nao_sei` e não devia ter perdido endereço:\n{r.stderr}")


def test_a_regua_morde_o_endereco_no_cartao_errado():
    """O endereço existe na página, mas dentro do cartão de outro lançador.

    O pintor procura DENTRO do bloco (`data-lancador`), então um endereço no
    cartão vizinho é tão invisível quanto um que não existe — e o `_FALTAM`,
    que testa substring no miolo inteiro, não tem como ver a diferença.
    """
    r = _importar(
        "def quebrado(l):\n"
        "    h = _orig(l)\n"
        "    if l.chave == 'heroic':\n"
        "        h = re.sub(r'\\sdata-campo=\"heroic-diz\"', '', h)\n"
        "    if l.chave == 'steam':\n"
        "        h = h.replace('data-campo=\"steam-diz\"',\n"
        "                      'data-campo=\"steam-diz\" data-campo=\"heroic-diz\"')\n"
        "    return h")
    assert r.returncode != 0, (
        "movi o `-diz` do heroic para o cartão da steam e o gerador passou — a "
        "régua não mede POR CARTÃO")
    assert "sem os 4 endereços que o pacote pinta" in r.stderr, (
        f"reprovou por outra coisa que não a régua nova:\n{r.stderr}")
    assert VELHA not in r.stderr, (
        "quem reprovou foi o `_FALTAM` — mas o endereço continua no miolo, só "
        f"que no cartão errado, e é isso que a régua nova existe para ver:\n{r.stderr}")


def test_esta_aba_nao_tem_cartao_por_controle():
    """A evidência de por que a régua daqui não é a das abas 01-06 e 08.

    Se um dia esta aba ganhar cartão por controle, este teste cai — e cair é o
    recado certo: a régua acima passa a ter de cobrir o eixo conectado/vazio
    também, que é onde o defeito de 07/09/2026 morava.
    """
    pagina = (INTERFACE / "paginas" / "07-lancadores.html").read_text(encoding="utf-8")  # noqa-acento: `paginas` é o nome da PASTA
    assert 'data-controle="p' not in pagina, (
        "a página 07 ganhou cartão por controle — ver o docstring")

    # A PROSA NÃO CONTA, e esta linha nasceu de cair nela: o comentário que
    # EXPLICA por que esta aba não tem `data-controle` escreve a palavra, e uma
    # busca crua no fonte se reprova a si mesma. É a armadilha que o `CLAUDE.md`
    # registra três vezes em três dias — *um comentário que descreve o padrão
    # proibido vira a primeira ocorrência dele*. Só os COMENTÁRIOS saem: o que
    # sobra é código, e uma string com `data-controle` aí dentro é emissão de
    # verdade, que é o que se quer pegar.
    fonte = (INTERFACE / "aba07.py").read_text(encoding="utf-8")
    sem_prosa = "".join(
        "" if tok.type == tokenize.COMMENT else tok.string
        for tok in tokenize.generate_tokens(io.StringIO(fonte).readline))
    assert "data-controle" not in sem_prosa, (
        "o gerador da aba 07 passou a emitir `data-controle` — ver o docstring")
