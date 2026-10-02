"""A ponte privilegiada do Bluetooth recusa entrada suja — e faz o gesto certo."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PONTE = RAIZ / "scripts" / "bt_ponte_privilegiada.sh"

ADAPTADOR = "aa:bb:cc:00:00:11"
ADAPTADOR_2 = "aa:bb:cc:00:00:33"
CONTROLE = "aa:bb:cc:00:00:22"

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
    """Ambiente com a raiz do BlueZ desviada para a árvore de teste."""
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
    """Uma árvore do BlueZ de mentira, com o mesmo formato da de verdade."""
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
    vizinho = raiz / ADAPTADOR.upper() / "aa:bb:cc:00:00:99".upper()
    vizinho.mkdir(parents=True)
    (vizinho / "info").write_text("[General]\nName=vizinho\n", encoding="utf-8")
    return raiz


def _tudo(raiz: Path) -> set[str]:
    return {str(p.relative_to(raiz)) for p in raiz.rglob("*")}


def _linhas(*dados: str) -> str:
    """O stdin da ponte: uma linha por dado, na ordem do verbo."""
    return "".join(f"{dado}\n" for dado in dados)


def test_esquecer_apaga_o_bond_e_o_cache_de_todos_os_adaptadores(arvore: Path) -> None:
    """O gesto do §6.3, inteiro, numa execução — inclusive o SDP-CACHE-01."""
    antes = _tudo(arvore)
    resultado = _rodar(arvore, "esquecer", entrada=_linhas(ADAPTADOR, CONTROLE))
    assert resultado.returncode == 0, resultado.stderr

    assert not (arvore / ADAPTADOR.upper() / CONTROLE.upper()).exists()
    assert not (arvore / ADAPTADOR.upper() / "cache" / CONTROLE.upper()).exists()
    assert not (arvore / ADAPTADOR_2.upper() / "cache" / CONTROLE.upper()).exists()

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
    assert por_mac[CONTROLE.upper()][2] == "com-chave"
    assert por_mac["AA:BB:CC:00:00:99"][2] == "sem-chave"


def test_dry_run_nao_apaga_nada_e_diz_o_que_faria(arvore: Path) -> None:
    antes = _tudo(arvore)
    resultado = _rodar(arvore, "--dry-run", "esquecer", entrada=_linhas(ADAPTADOR, CONTROLE))
    assert resultado.returncode == 0, resultado.stderr
    assert _tudo(arvore) == antes
    assert "[dry-run]" in resultado.stdout
    assert "cache SDP" in resultado.stdout


@pytest.mark.parametrize("sujo", MACS_SUJOS)
def test_mac_sujo_e_recusado(arvore: Path, sujo: str) -> None:
    """Recusa com código 2 em TODO verbo que recebe MAC, e sem tocar no disco."""
    antes = _tudo(arvore)
    for verbo, argv, dados in (
        ("bonds", (), (sujo,)),
        ("esquecer", (), (sujo, CONTROLE)),
        ("esquecer", (), (ADAPTADOR, sujo)),
        ("descobrir", ("5",), (sujo,)),
        ("parear", (), (sujo, CONTROLE)),
        ("parear", (), (ADAPTADOR, sujo)),
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
    """Depois dos dados do verbo o stdin FECHA: linha a mais é pedido montado"""
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
    """A forma de antes de 29/09 (``esquecer <adaptador> <controle>``) falha"""
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
    """Os dados certos e o cano aberto: a ponte espera o fim por 10 s e recusa."""
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
    """O caso que pegou um defeito REAL deste script (mordida (c) do cabeçalho)."""
    bond = arvore / ADAPTADOR.upper() / CONTROLE.upper() / "info"
    resultado = _rodar(arvore, "esquecer", entrada=_linhas(ADAPTADOR, "../../../etc/passwd"))
    assert resultado.returncode == RECUSA
    assert bond.exists(), "a recusa deixou o gesto continuar"


@pytest.mark.parametrize("sujo", NOMES_SUJOS)
def test_nome_novo_sujo_e_recusado(arvore: Path, sujo: str) -> None:
    """O nome do adaptador é o único dado de forma livre — e vem pelo stdin."""
    resultado = _rodar(arvore, "renomear", entrada=_linhas(ADAPTADOR, sujo))
    assert resultado.returncode == RECUSA, resultado.stderr
    assert "nome novo" in resultado.stderr


def test_nome_com_acento_e_aceito(arvore: Path) -> None:
    """A régua não pode ser xenófoba: ela escreve em português."""
    resultado = _rodar(arvore, "renomear", entrada=_linhas(ADAPTADOR, "Sótão — rack (nº 1)"))
    assert resultado.returncode != RECUSA, resultado.stderr


def test_nome_com_caractere_de_controle_e_recusado(arvore: Path) -> None:
    resultado = _rodar(arvore, "renomear", entrada=_linhas(ADAPTADOR, "a\tb"))
    assert resultado.returncode == RECUSA
    assert "controle" in resultado.stderr


@pytest.mark.parametrize("sujo", SEGUNDOS_SUJOS)
def test_segundos_sujo_e_recusado(arvore: Path, sujo: str) -> None:
    """A janela de busca BLOQUEIA um processo root pelo tempo pedido."""
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
    """Contagem exata de argumentos — sem ela, o `[0-9]` do sudoers não basta."""
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


def test_os_ganchos_de_teste_morrem_sob_sudo(arvore: Path) -> None:
    """`SUDO_UID` no ambiente apaga `HEFESTO_BT_LIB` e companhia."""
    resultado = _rodar(
        arvore, "bonds", entrada=_linhas(ADAPTADOR), env_extra={"SUDO_UID": "1000"}
    )
    assert resultado.returncode == 1
    assert "requer root" in resultado.stderr
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
