"""A ponte privilegiada do Bluetooth recusa entrada suja — e faz o gesto certo.

`scripts/bt_ponte_privilegiada.sh` é o único caminho de ROOT que a janela tem
para mover um controle de um dongle para outro. O `install.sh` grava
`/etc/sudoers.d/49-hefesto-bt-ponte` com NOPASSWD para ele: a partir daí,
qualquer coisa que este script aceite, a usuária executa como root SEM SENHA.

Um helper privilegiado que aceita entrada suja é PIOR que não ter helper —
sem ele o gesto continua sendo trabalho de terminal, com ele vira uma porta.
Por isso este arquivo cobra as duas metades, e as duas na mesma execução:

  1. o que tem de ser RECUSADO (código 2, nada tocado no disco);
  2. o que tem de FUNCIONAR (o bond e o cache SDP realmente somem).

A metade 2 não é cortesia: um portão que só sabe reprovar passa verde com o
script inteiro trocado por `exit 2`. As duas juntas é que medem alguma coisa.

O QUE A FORMA DO MAC EXCLUI POR CONSTRUÇÃO. A validação é uma regex ancorada de
MAC, não uma denylist — então `..`, `/`, `;`, `$(`, backtick, espaço, byte de
controle e quebra de linha caem todos pela mesma porta, e não há lista a manter
atualizada. Os casos abaixo existem para provar isso, um a um, contra o
comportamento real do script.

PROVA DE MORDIDA (22/08/2026), três arrancadas independentes, cada uma
devolvida em seguida (`17 failed`, `51 failed`, `1 failed`; controle: 57 verdes):

  a) `_MAC_FORMA` trocada por `^.*$` (aceita tudo) — **17 reprovações**: 16
     casos de `test_mac_sujo_e_recusado` (todos menos o `vazio`, que ainda cai
     na checagem de ausência) e
     `test_o_verbo_esquecer_nao_toca_em_nada_quando_o_mac_e_sujo`, este com
     `assert 0 == 2`: o script apagou o alvo com um MAC que era um caminho;
  b) `_recusar` trocado de `exit 2` para `return 0` (a recusa vira só uma
     mensagem) — **51 reprovações**, 6 verdes. É a arrancada que mostra que o
     valor do portão está no CÓDIGO DE SAÍDA, não na mensagem;
  c) validação devolvida ao idioma `x="$(_mac "$1")"` — **reprovou
     `test_o_verbo_esquecer_nao_toca_em_nada_quando_o_mac_e_sujo`** com
     `assert 1 == 2`. O detalhe é o que interessa: o `exit 2` morreu na
     subshell, o script seguiu com o MAC VAZIO, montou
     `<raiz>/AA:BB:CC:00:00:11/` e só a SEGUNDA tranca (a guarda de forma do
     `_apagar`) o parou, com "recusando apagar caminho fora da forma
     esperada". Foi um defeito REAL deste script, achado por esta suíte antes
     de qualquer commit — e a prova de que as duas trancas não são exagero.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PONTE = RAIZ / "scripts" / "bt_ponte_privilegiada.sh"

#: Faixa sintética da casa. NUNCA usar MAC real nem mascarado em fixture: o
#: `tests/unit/test_anonimato_de_fixtures.py` reprova, e aqui há um motivo
#: extra — o script MEXE no adaptador de verdade quando o MAC casa com um vivo.
ADAPTADOR = "aa:bb:cc:00:00:11"
ADAPTADOR_2 = "aa:bb:cc:00:00:33"
CONTROLE = "aa:bb:cc:00:00:22"

#: Códigos de saída do contrato: 2 = uso/entrada inválida; 1 = falha
#: operacional. A distinção importa para a janela saber de quem é o problema.
RECUSA = 2

MACS_SUJOS = [
    pytest.param("../../etc/passwd", id="travessia-de-caminho"),
    pytest.param("../../../var/lib/bluetooth", id="travessia-relativa"),
    pytest.param(f"{CONTROLE}/../../x", id="mac-valido-com-travessia-colada"),
    pytest.param(f"{CONTROLE};rm -rf /", id="ponto-e-virgula"),
    pytest.param(f"{CONTROLE}$(id)", id="cifrao-parenteses"),
    pytest.param(f"{CONTROLE}`id`", id="crase"),
    pytest.param(f"{CONTROLE}|tee /tmp/x", id="cano"),
    pytest.param(f"{CONTROLE} && id", id="e-comercial"),
    pytest.param(f"{CONTROLE}\n../../x", id="quebra-de-linha-embutida"),
    pytest.param(f"{CONTROLE} ", id="espaco-ao-final"),
    pytest.param(f" {CONTROLE}", id="espaco-no-inicio"),
    pytest.param("aa:bb:cc:00:00:2z", id="digito-nao-hexadecimal"),
    pytest.param("aa:bb:cc:00:00", id="curto-demais"),
    pytest.param("aa:bb:cc:00:00:22:33", id="longo-demais"),
    pytest.param("aabbcc000022", id="sem-separador"),
    pytest.param("*", id="curinga"),
    pytest.param("", id="vazio"),
]

NOMES_SUJOS = [
    pytest.param("Nintendo; rm -rf /", id="ponto-e-virgula"),
    pytest.param("x$(id)", id="cifrao-parenteses"),
    pytest.param("x`id`", id="crase"),
    pytest.param("a|b", id="cano"),
    pytest.param("a>b", id="redirecionamento"),
    pytest.param("a/b", id="barra"),
    pytest.param("a\\b", id="contrabarra"),
    pytest.param("a&b", id="e-comercial"),
    pytest.param("a'b", id="aspa-simples"),
    pytest.param('a"b', id="aspa-dupla"),
    pytest.param(" comeca com espaco", id="espaco-no-inicio"),
    pytest.param("termina com espaco ", id="espaco-ao-final"),
    pytest.param("", id="vazio"),
    pytest.param("N" * 65, id="longo-demais"),
]

SEGUNDOS_SUJOS = [
    pytest.param("0", id="abaixo-da-faixa"),
    pytest.param("121", id="acima-da-faixa"),
    pytest.param("999", id="muito-acima"),
    pytest.param("-1", id="negativo"),
    pytest.param("abc", id="nao-numero"),
    pytest.param("5;id", id="ponto-e-virgula"),
    pytest.param("$(id)", id="cifrao-parenteses"),
    pytest.param("", id="vazio"),
]


def _ambiente(raiz_falsa: Path) -> dict[str, str]:
    """Ambiente com a raiz do BlueZ desviada para a árvore de teste.

    `HEFESTO_BT_LOG_DEST=none` não é detalhe: sem ele a suíte grava no journal
    DELA linhas que descrevem eventos que nunca aconteceram
    (DIÁRIO-QUE-NAO-MENTE-01). E com a raiz desviada o script se recusa a falar
    com o barramento real — nenhum adaptador vivo desta casa é tocado.
    """
    env = dict(os.environ)
    env["HEFESTO_BT_LIB"] = str(raiz_falsa)
    env["HEFESTO_BT_LOG_DEST"] = "none"
    env.pop("SUDO_UID", None)
    env.pop("SUDO_USER", None)
    return env


def _rodar(
    raiz_falsa: Path,
    *args: str,
    entrada: str | None = None,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = _ambiente(raiz_falsa)
    if env_extra:
        env.update(env_extra)
    #: Alvo fixo: é o próprio script sob teste, nunca um comando montado.
    return subprocess.run(
        ["bash", str(PONTE), *args],
        capture_output=True,
        text=True,
        input=entrada,
        env=env,
        timeout=60,
        check=False,
    )


@pytest.fixture()
def arvore(tmp_path: Path) -> Path:
    """Uma árvore do BlueZ de mentira, com o mesmo formato da de verdade.

    Dois adaptadores; o controle tem bond no primeiro e entrada de cache nos
    DOIS — que é o caso real de quem já pareou o controle num dongle e escaneou
    com o outro. O §3.3 do `docs/usage/bluetooth-varios-adaptadores.md` manda
    apagar o cache dos dois.
    """
    raiz = tmp_path / "bluetooth"
    for adaptador in (ADAPTADOR.upper(), ADAPTADOR_2.upper()):
        (raiz / adaptador / "cache").mkdir(parents=True)
        (raiz / adaptador / "cache" / CONTROLE.upper()).write_text("[General]\n", encoding="utf-8")
    bond = raiz / ADAPTADOR.upper() / CONTROLE.upper()
    bond.mkdir(parents=True)
    (bond / "info").write_text(
        "[General]\nName=DualSense Wireless Controller\n\n[LinkKey]\nKey=00\n",
        encoding="utf-8",
    )
    #: Canário: um vizinho que NÃO é o alvo. Se alguma recusa mal feita virar um
    #: `rm` largo, ele é o primeiro a sumir.
    vizinho = raiz / ADAPTADOR.upper() / "aa:bb:cc:00:00:99".upper()
    vizinho.mkdir(parents=True)
    (vizinho / "info").write_text("[General]\nName=vizinho\n", encoding="utf-8")
    return raiz


def _tudo(raiz: Path) -> set[str]:
    return {str(p.relative_to(raiz)) for p in raiz.rglob("*")}


def _linhas(*dados: str) -> str:
    """O stdin da ponte: uma linha por dado, na ordem do verbo.

    O-SUDO-NAO-GRAVA-O-ENDERECO-NO-DIARIO-01 (29/09/2026): o endereço vem pelo
    stdin, como o nome novo já vinha. No argv, o sudo o gravava no journal.
    """
    return "".join(f"{dado}\n" for dado in dados)


# --- a metade que tem de FUNCIONAR ------------------------------------------
#
# Sem estes dois, o arquivo inteiro passaria com o script trocado por `exit 2`.


def test_esquecer_apaga_o_bond_e_o_cache_de_todos_os_adaptadores(arvore: Path) -> None:
    """O gesto do §6.3, inteiro, numa execução — inclusive o SDP-CACHE-01.

    O cache sai dos DOIS adaptadores de propósito: o dongle de DESTINO também
    pode ter uma entrada velha desse controle, e é ela que faria o pareamento
    novo nascer com SDP vazio, o BlueZ recusar a reconexão como *unknown
    device*, e o link cair sozinho parecendo defeito do controle.
    """
    antes = _tudo(arvore)
    resultado = _rodar(arvore, "esquecer", entrada=_linhas(ADAPTADOR, CONTROLE))
    assert resultado.returncode == 0, resultado.stderr

    assert not (arvore / ADAPTADOR.upper() / CONTROLE.upper()).exists()
    assert not (arvore / ADAPTADOR.upper() / "cache" / CONTROLE.upper()).exists()
    assert not (arvore / ADAPTADOR_2.upper() / "cache" / CONTROLE.upper()).exists()

    #: E NADA além disso. A diferença tem de ser exatamente o alvo.
    sumiram = antes - _tudo(arvore)
    esperado = {
        f"{ADAPTADOR.upper()}/{CONTROLE.upper()}",
        f"{ADAPTADOR.upper()}/{CONTROLE.upper()}/info",
        f"{ADAPTADOR.upper()}/cache/{CONTROLE.upper()}",
        f"{ADAPTADOR_2.upper()}/cache/{CONTROLE.upper()}",
    }
    assert sumiram == esperado


def test_bonds_lista_o_que_esta_pareado_naquele_adaptador(arvore: Path) -> None:
    resultado = _rodar(arvore, "bonds", entrada=_linhas(ADAPTADOR))
    assert resultado.returncode == 0, resultado.stderr
    linhas = [linha.split("\t") for linha in resultado.stdout.splitlines() if linha]
    por_mac = {linha[0]: linha for linha in linhas}
    assert CONTROLE.upper() in por_mac
    assert por_mac[CONTROLE.upper()][1] == "DualSense Wireless Controller"
    #: A coluna de chave é o que distingue bond de sobra de scan.
    assert por_mac[CONTROLE.upper()][2] == "com-chave"
    assert por_mac["AA:BB:CC:00:00:99"][2] == "sem-chave"


def test_dry_run_nao_apaga_nada_e_diz_o_que_faria(arvore: Path) -> None:
    antes = _tudo(arvore)
    resultado = _rodar(arvore, "--dry-run", "esquecer", entrada=_linhas(ADAPTADOR, CONTROLE))
    assert resultado.returncode == 0, resultado.stderr
    assert _tudo(arvore) == antes
    assert "[dry-run]" in resultado.stdout
    assert "cache SDP" in resultado.stdout


# --- a metade que tem de RECUSAR --------------------------------------------


@pytest.mark.parametrize("sujo", MACS_SUJOS)
def test_mac_sujo_e_recusado(arvore: Path, sujo: str) -> None:
    """Recusa com código 2 em TODO verbo que recebe MAC, e sem tocar no disco.

    O sujo vai pela primeira linha do stdin e pela segunda. O que tem quebra de
    linha embutida vira duas linhas, e a recusa é a da linha a mais (ou a do
    nome novo, no ``renomear``): a mesma porta, com o código 2.
    """
    antes = _tudo(arvore)
    for verbo, argv, dados in (
        ("bonds", (), (sujo,)),
        ("esquecer", (), (sujo, CONTROLE)),
        ("esquecer", (), (ADAPTADOR, sujo)),
        ("descobrir", ("5",), (sujo,)),
        ("parear", (), (sujo, CONTROLE)),
        ("parear", (), (ADAPTADOR, sujo)),
        # CONEXAO-ZUMBI-01: o verbo que derruba um link. Ele é o mais perigoso
        # da lista para receber MAC sujo — não apaga arquivo, mas CORTA o rádio
        # de alguém, e do outro lado do sudo.
        ("desconectar", (), (sujo, CONTROLE)),
        ("desconectar", (), (ADAPTADOR, sujo)),
        ("renomear", (), (sujo, "Rack 1")),
    ):
        caso = (verbo, *argv, *dados)
        resultado = _rodar(arvore, verbo, *argv, entrada=_linhas(*dados))
        assert resultado.returncode == RECUSA, f"{caso}: rc={resultado.returncode}"
        assert resultado.stdout == "", f"{caso}: escreveu no stdout"
        assert any(
            motivo in resultado.stderr
            for motivo in ("inválido", "ausente", "linha a mais", "nome novo")
        ), f"{caso}: {resultado.stderr}"
    assert _tudo(arvore) == antes


def test_a_linha_que_nao_vem_e_recusada(arvore: Path) -> None:
    """O stdin que fecha antes do controle: recusa, e o bond fica."""
    antes = _tudo(arvore)
    for entrada in ("", _linhas(ADAPTADOR), ADAPTADOR):
        resultado = _rodar(arvore, "esquecer", entrada=entrada)
        assert resultado.returncode == RECUSA, f"{entrada!r}: rc={resultado.returncode}"
        assert "não veio pelo stdin" in resultado.stderr
    assert _tudo(arvore) == antes


def test_a_linha_a_mais_e_recusada(arvore: Path) -> None:
    """Depois dos dados do verbo o stdin FECHA: linha a mais é pedido montado
    errado, e metade dele não pode ser lida como se fosse o todo."""
    antes = _tudo(arvore)
    for entrada in (
        _linhas(ADAPTADOR, CONTROLE, CONTROLE),
        _linhas(ADAPTADOR, CONTROLE, ""),
        _linhas(ADAPTADOR, CONTROLE) + "resto sem quebra",
    ):
        resultado = _rodar(arvore, "esquecer", entrada=entrada)
        assert resultado.returncode == RECUSA, f"{entrada!r}: rc={resultado.returncode}"
        assert "linha a mais" in resultado.stderr
    assert _tudo(arvore) == antes


def test_o_endereco_no_argv_e_recusado(arvore: Path) -> None:
    """A forma de antes de 29/09 (``esquecer <adaptador> <controle>``) falha
    alto e sem efeito, com a frase que diz o caminho novo — mesmo com o stdin
    certo ao lado. É a que o sudo gravava no journal."""
    antes = _tudo(arvore)
    for verbo, argv in (
        ("esquecer", (ADAPTADOR, CONTROLE)),
        ("parear", (ADAPTADOR, CONTROLE)),
        ("desconectar", (ADAPTADOR, CONTROLE)),
        ("bonds", (ADAPTADOR,)),
        ("renomear", (ADAPTADOR,)),
        ("descobrir", (ADAPTADOR, "5")),
    ):
        resultado = _rodar(arvore, verbo, *argv, entrada=_linhas(ADAPTADOR, CONTROLE))
        assert resultado.returncode == RECUSA, f"{verbo}: rc={resultado.returncode}"
        assert "o endereço vem pelo stdin" in resultado.stderr, resultado.stderr
    assert _tudo(arvore) == antes


def test_o_stdin_que_nao_fecha_e_recusado(arvore: Path) -> None:
    """Os dados certos e o cano aberto: a ponte espera o fim por 10 s e recusa.

    É a razão de quem abre a ponte FECHAR o stdin depois de escrever
    (``gesto_de_pareamento._abrir_de_verdade``): root parado esperando é falha
    de disponibilidade com privilégio.
    """
    antes = _tudo(arvore)
    processo = subprocess.Popen(
        ["bash", str(PONTE), "esquecer"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_ambiente(arvore),
    )
    try:
        assert processo.stdin is not None and processo.stderr is not None
        processo.stdin.write(_linhas(ADAPTADOR, CONTROLE))
        processo.stdin.flush()
        #: O cano segue aberto: a recusa tem de vir do prazo da ponte (10 s).
        codigo = processo.wait(timeout=30)
        erro = processo.stderr.read()
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait(timeout=10)
        if processo.stdin is not None:
            processo.stdin.close()
    assert codigo == RECUSA
    assert "não fechou" in erro
    assert _tudo(arvore) == antes


def test_o_verbo_esquecer_nao_toca_em_nada_quando_o_mac_e_sujo(arvore: Path) -> None:
    """O caso que pegou um defeito REAL deste script (mordida (c) do cabeçalho).

    A validação devolvia pelo stdout, e a chamada era `$(_mac "$1")`. O `exit 2`
    da recusa morria na subshell: o script seguia com o MAC VAZIO e chegava a
    montar caminhos com ele. Aqui a régua não é a mensagem de erro — é o bond
    ainda estar no disco depois.
    """
    bond = arvore / ADAPTADOR.upper() / CONTROLE.upper() / "info"
    resultado = _rodar(arvore, "esquecer", entrada=_linhas(ADAPTADOR, "../../../etc/passwd"))
    assert resultado.returncode == RECUSA
    assert bond.exists(), "a recusa deixou o gesto continuar"


@pytest.mark.parametrize("sujo", NOMES_SUJOS)
def test_nome_novo_sujo_e_recusado(arvore: Path, sujo: str) -> None:
    """O nome do adaptador é o único dado de forma livre — e vem pelo stdin.

    Vir pelo stdin é o que deixa a linha de comando do sudoers COMPLETAMENTE
    fechada (nenhum argumento livre a casar). Em troca, a régua do conteúdo tem
    de morar aqui.
    """
    resultado = _rodar(arvore, "renomear", entrada=_linhas(ADAPTADOR, sujo))
    assert resultado.returncode == RECUSA, resultado.stderr
    assert "nome novo" in resultado.stderr


def test_nome_com_acento_e_aceito(arvore: Path) -> None:
    """A régua não pode ser xenófoba: ela escreve em português.

    Um nome legítimo tem de PASSAR pela validação. O verbo falha depois, com
    código 1 — o adaptador de mentira não existe no barramento —, e é
    exatamente essa diferença de código que prova que a entrada foi aceita.
    """
    resultado = _rodar(arvore, "renomear", entrada=_linhas(ADAPTADOR, "Sótão — rack (nº 1)"))
    assert resultado.returncode != RECUSA, resultado.stderr


def test_nome_com_caractere_de_controle_e_recusado(arvore: Path) -> None:
    resultado = _rodar(arvore, "renomear", entrada=_linhas(ADAPTADOR, "a\tb"))
    assert resultado.returncode == RECUSA
    assert "controle" in resultado.stderr


@pytest.mark.parametrize("sujo", SEGUNDOS_SUJOS)
def test_segundos_sujo_e_recusado(arvore: Path, sujo: str) -> None:
    """A janela de busca BLOQUEIA um processo root pelo tempo pedido.

    Por isso ela tem teto, e por isso o teto é validado aqui: `descobrir X
    999999` seria root parado por onze dias.
    """
    resultado = _rodar(arvore, "descobrir", sujo, entrada=_linhas(ADAPTADOR))
    assert resultado.returncode == RECUSA, resultado.stderr
    assert "segundos" in resultado.stderr


def test_nao_existe_verbo_que_execute_comando_arbitrario(arvore: Path) -> None:
    """A lista de verbos é fechada, e o que não está nela sai com 2."""
    for tentativa in (
        ("executar", "id"),
        ("exec", "id"),
        ("shell", "-c", "id"),
        ("rm", "-rf", "/"),
        ("-c", "id"),
        ("bonds;id", ADAPTADOR),
    ):
        resultado = _rodar(arvore, *tentativa)
        assert resultado.returncode == RECUSA, f"{tentativa}: rc={resultado.returncode}"
        assert "verbo desconhecido" in resultado.stderr


def test_argumento_a_mais_e_recusado(arvore: Path) -> None:
    """Contagem exata de argumentos — sem ela, o `[0-9]` do sudoers não basta.

    A regra do sudoers casa a linha inteira, mas quem constrói a linha é a
    janela. Um verbo que ignora o argumento extra deixa passar o dia em que a
    janela montar a chamada errada e ninguém perceber.
    """
    for tentativa in (
        ("adaptadores", "extra"),
        ("bonds", "extra"),
        ("esquecer", "extra"),
        ("descobrir",),
        ("descobrir", "5", "extra"),
        ("parear", "extra"),
        ("desconectar", "extra"),
        ("renomear", "extra"),
        ("regra-sudo",),
    ):
        resultado = _rodar(arvore, *tentativa, entrada=_linhas(ADAPTADOR, CONTROLE))
        assert resultado.returncode == RECUSA, f"{tentativa}: rc={resultado.returncode}"


@pytest.mark.parametrize(
    "sujo",
    [
        "root ALL=(ALL) NOPASSWD: ALL",
        "ALL",
        "-x",
        "usuaria/x",
        "a" * 40,
        "usuaria=x",
        "usu aria",
        "",
    ],
)
def test_nome_de_usuaria_sujo_e_recusado_na_regra_do_sudoers(arvore: Path, sujo: str) -> None:
    """O texto gerado vira `/etc/sudoers.d/`. Nome sujo ali é regra suja ali."""
    resultado = _rodar(arvore, "regra-sudo", sujo)
    assert resultado.returncode == RECUSA, resultado.stdout
    assert resultado.stdout == ""


# --- a contenção que não se vê ----------------------------------------------


def test_os_ganchos_de_teste_morrem_sob_sudo(arvore: Path) -> None:
    """`SUDO_UID` no ambiente apaga `HEFESTO_BT_LIB` e companhia.

    O `Defaults env_reset` do sudo já faria isso — mas quem o desligou não pode
    ganhar de brinde um `rm` como root em raiz escolhida por ele. Com o gancho
    morto, `bonds` volta a mirar `/var/lib/bluetooth`, que é 700 do root: sem
    root, o script tem de EXIGIR root em vez de trabalhar na raiz injetada.
    """
    resultado = _rodar(
        arvore, "bonds", entrada=_linhas(ADAPTADOR), env_extra={"SUDO_UID": "1000"}
    )
    assert resultado.returncode == 1
    assert "requer root" in resultado.stderr
    #: E a régua do gancho: sem SUDO_UID, o MESMO comando funciona. Sem esta
    #: metade, o teste acima passaria com o script quebrado de qualquer jeito.
    assert _rodar(arvore, "bonds", entrada=_linhas(ADAPTADOR)).returncode == 0


def test_a_raiz_de_teste_nao_fala_com_o_barramento_real(arvore: Path) -> None:
    """Com raiz desviada, os verbos que MEXEM no adaptador ficam inertes.

    A suíte roda estes scripts de verdade, na máquina dela, com quatro DualSense
    e um Pro no rádio. `renomear`, `descobrir`, `parear` e `desconectar` mexem
    no adaptador — bastaria um MAC de teste coincidir com um adaptador vivo
    para um portão derrubar a mesa dela no meio de uma partida. E o
    `desconectar` (CONEXAO-ZUMBI-01) é o que mais dói: ele CORTA um link.
    """
    for verbo, argv, dados in (
        ("renomear", (), (ADAPTADOR, "Rack 1")),
        ("descobrir", ("1",), (ADAPTADOR,)),
        ("parear", (), (ADAPTADOR, CONTROLE)),
        ("desconectar", (), (ADAPTADOR, CONTROLE)),
    ):
        resultado = _rodar(arvore, verbo, *argv, entrada=_linhas(*dados))
        assert resultado.returncode == 1, f"{verbo}: rc={resultado.returncode}"
        assert "não está na mesa" in resultado.stderr
