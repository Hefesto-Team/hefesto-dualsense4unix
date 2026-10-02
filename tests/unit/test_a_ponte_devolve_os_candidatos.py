"""PONTE-SEM-CHAMADOR-01 — o `descobrir` que abria a janela e não devolvia nada.

Até 20/09/2026 o verbo `descobrir` de `scripts/bt_ponte_privilegiada.sh` abria
uma janela de busca no adaptador, **bloqueava pelos segundos pedidos e saía com
zero**. Quem chamasse ficava com um adaptador varrendo e nenhuma lista para
escolher — e sem lista o verbo `parear` só serve a quem já sabe o endereço de
cor, que é exatamente a pessoa que não precisa de botão.

COMO SE MEDE ISTO SEM TOCAR NO RÁDIO DELA
==========================================
A única forma honesta de medir a lista de candidatos é abrindo uma varredura, e
abrir varredura na máquina dela custa de 32% a 43% dos pacotes do adaptador que
a hospeda, com quatro DualSense de pé. Por isso o script ganhou o quarto gancho
de teste, `HEFESTO_BT_BIN`: uma pasta posta na frente do `PATH`, de onde saem o
`busctl` e o `bluetoothctl` que ele chama. Com ela, o barramento que responde é
o desta fixture — e nenhum rádio desta casa é tocado.

O gancho é inerte sob sudo, como os outros três (contenção 3 do cabeçalho do
script), e `test_sem_o_gancho_a_raiz_de_teste_continua_inerte` é a régua que
guarda o caminho antigo: sem o gancho, raiz de teste continua recusando falar
com o barramento real.

PROVA DE MORDIDA (20/09/2026), cada arrancada devolvida em seguida. Controle:
12 verdes neste arquivo.

  a) o laço de `_candidatos_novos` apagado de `verbo_descobrir` (o verbo volta
     a só abrir a janela) — **8 reprovações de 12**; as quatro que sobram são a
     do dry-run, a da inércia sem gancho, a do gancho sob sudo e a do sinal,
     que não dependem da lista;
  b) o `&` que manda a janela para o fundo desfeito (o `bluetoothctl` volta ao
     primeiro plano) — **reprovou
     `test_o_candidato_sai_enquanto_a_janela_ainda_esta_aberta`**. Esta
     arrancada achou um defeito NA PRÓPRIA RÉGUA, e é a lição do dia: escrita
     contra `processo.poll() is None`, ela passava VERDE sobre o defeito, porque
     a ponte ainda corre `wait`, `wc` e o diário depois de despejar a lista.
     Trocada para olhar o marcador da VARREDURA, morde;
  c) o `_higienizar` tirado da coluna do nome — **4 reprovações**, porque o
     `\t` do nome empurra todas as colunas seguintes;
  d) o `kill` arrancado de `_fechar_a_busca` — **reprovou
     `test_a_varredura_cai_junto_com_a_ponte`**: a ponte morre e o
     `bluetoothctl` fica varrendo o adaptador dela;
  e) `HEFESTO_BT_BIN` fora da linha de `unset` sob sudo — **1 reprovação**: o
     gancho de teste sobreviveria ao sudo, que é a contenção 3 caindo.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest
from tests.unit.barramento_de_mentira import (
    ADAPTADOR,
    CLASSE_DO_DUALSENSE,
    CONTROLE,
    PONTE,
    VIZINHO,
    ainda_varrendo,
    ambiente,
    montar,
)

CLASSE_NA_COLUNA = str(CLASSE_DO_DUALSENSE)


@pytest.fixture()
def barramento(tmp_path: Path) -> Path:
    """O BlueZ de mentira da bancada — ver `tests/unit/barramento_de_mentira.py`."""
    return montar(tmp_path)


def _ambiente(raiz: Path) -> dict[str, str]:
    return ambiente(raiz)


ENTRADA = f"{ADAPTADOR}\n"


def _descobrir(barramento: Path, segundos: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(PONTE), "descobrir", segundos],
        capture_output=True,
        text=True,
        input=ENTRADA,
        env=_ambiente(barramento),
        timeout=60,
        check=False,
    )


def _abrir_descobrir(barramento: Path, segundos: str) -> subprocess.Popen[str]:
    """A janela em fluxo, com o adaptador escrito no stdin e o cano FECHADO:"""
    processo = subprocess.Popen(
        ["bash", str(PONTE), "descobrir", segundos],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=_ambiente(barramento),
    )
    assert processo.stdin is not None
    processo.stdin.write(ENTRADA)
    processo.stdin.close()
    return processo


def _linhas(saida: str) -> list[list[str]]:
    return [linha.split("\t") for linha in saida.splitlines() if linha.strip()]


def test_descobrir_devolve_a_lista_de_candidatos_em_tsv(barramento: Path) -> None:
    """Quatro colunas por candidato: MAC, nome, novo|pareado e a classe."""
    feito = _descobrir(barramento, "3")
    assert feito.returncode == 0, feito.stderr
    linhas = _linhas(feito.stdout)
    assert len(linhas) == 2, feito.stdout

    por_mac = {linha[0]: linha for linha in linhas}
    assert set(por_mac) == {CONTROLE.upper(), VIZINHO.upper()}, feito.stdout

    controle = por_mac[CONTROLE.upper()]
    assert controle[1] == "DualSense Wireless Controller"
    assert controle[2] == "novo"
    assert controle[3] == CLASSE_NA_COLUNA


def test_o_candidato_ja_pareado_se_declara(barramento: Path) -> None:
    """`pareado` não é enfeite: é o que impede a tela de mandá-la repetir"""
    feito = _descobrir(barramento, "3")
    por_mac = {linha[0]: linha for linha in _linhas(feito.stdout)}
    assert por_mac[VIZINHO.upper()][2] == "pareado"


def test_a_classe_ausente_sai_vazia_e_nao_inventada(barramento: Path) -> None:
    """O vizinho não publica `Class`. A coluna tem de ficar vazia."""
    feito = _descobrir(barramento, "3")
    por_mac = {linha[0]: linha for linha in _linhas(feito.stdout)}
    assert por_mac[VIZINHO.upper()][3] == ""


def test_o_nome_com_tabulacao_nao_quebra_a_coluna(barramento: Path) -> None:
    """O nome vem do BlueZ, que é terceiro. `\\t` e `\\n` nele viram espaço."""
    feito = _descobrir(barramento, "3")
    for linha in _linhas(feito.stdout):
        assert len(linha) == 4, f"o TSV ganhou colunas: {linha!r}"
    por_mac = {linha[0]: linha for linha in _linhas(feito.stdout)}
    assert por_mac[VIZINHO.upper()][1] == "fone da vizinha"


def test_o_aparelho_que_aparece_no_meio_da_janela_tambem_sai(
    barramento: Path,
) -> None:
    """Quem chega no segundo 1 é candidato como quem já estava lá."""
    assert not (barramento / "marcador").exists()
    feito = _descobrir(barramento, "3")
    assert (barramento / "marcador").exists(), "a janela nem chegou a abrir"
    macs = {linha[0] for linha in _linhas(feito.stdout)}
    assert VIZINHO.upper() in macs, feito.stdout


def test_o_candidato_sai_enquanto_a_janela_ainda_esta_aberta(
    barramento: Path,
) -> None:
    """O FLUXO, e é o que torna o `parear` possível."""
    comeco = time.monotonic()
    varrendo = barramento / "varrendo"
    processo = _abrir_descobrir(barramento, "4")
    try:
        assert processo.stdout is not None
        primeira = processo.stdout.readline()
        ainda_varrendo = varrendo.exists()
        decorrido = time.monotonic() - comeco
        assert primeira.strip(), "a ponte não devolveu candidato nenhum"
        assert ainda_varrendo, (
            f"a primeira linha só chegou com a varredura JÁ FECHADA "
            f"({decorrido:.2f}s) — a lista está sendo despejada no fim, e o "
            "`parear` não tem mais objeto no BlueZ para alcançar"
        )
    finally:
        processo.kill()
        processo.wait(timeout=10)


def test_o_roteiro_pede_pairable_e_scan_no_adaptador_escolhido(
    barramento: Path,
) -> None:
    """Sem `pairable on` a janela vê e não deixa parear."""
    _descobrir(barramento, "3")
    roteiro = (barramento / "roteiro").read_text(encoding="utf-8")
    assert f"select {ADAPTADOR.upper()}" in roteiro
    assert "pairable on" in roteiro
    assert "scan on" in roteiro
    argv = (barramento / "argv").read_text(encoding="utf-8")
    assert "--timeout 3" in argv


def test_o_dry_run_anuncia_a_lista_e_nao_abre_janela(barramento: Path) -> None:
    """`--dry-run` não varre nada — e diz que devolveria a lista."""
    feito = subprocess.run(
        ["bash", str(PONTE), "--dry-run", "descobrir", "3"],
        capture_output=True,
        text=True,
        input=ENTRADA,
        env=_ambiente(barramento),
        timeout=30,
        check=False,
    )
    assert feito.returncode == 0, feito.stderr
    assert not (barramento / "marcador").exists(), "o dry-run abriu a janela"
    assert "novo|pareado" in feito.stdout, feito.stdout


def test_o_diario_conta_os_candidatos_e_nao_os_nomeia(barramento: Path) -> None:
    """Uma varredura vê o celular de quem passa na rua."""
    diario = barramento / "diario.txt"
    env = _ambiente(barramento)
    env["HEFESTO_BT_LOG_DEST"] = str(diario)
    subprocess.run(
        ["bash", str(PONTE), "descobrir", "3"],
        capture_output=True,
        text=True,
        input=ENTRADA,
        env=env,
        timeout=60,
        check=False,
    )
    texto = diario.read_text(encoding="utf-8")
    assert "2 candidato(s)" in texto, texto
    assert CONTROLE.upper() not in texto, "o diário nomeou um candidato"
    assert VIZINHO.upper() not in texto, "o diário nomeou um candidato"


def test_a_varredura_cai_junto_com_a_ponte(barramento: Path) -> None:
    """Quem fecha a tela fecha o rádio junto — inclusive por sinal."""
    processo = _abrir_descobrir(barramento, "60")
    try:
        assert processo.stdout is not None
        assert processo.stdout.readline().strip(), "a ponte não chegou a varrer"
        limite = time.monotonic() + 5.0
        while not ainda_varrendo(barramento) and time.monotonic() < limite:
            time.sleep(0.02)
        assert ainda_varrendo(barramento), "a janela de mentira nem abriu"
        processo.terminate()
        processo.wait(timeout=10)
        limite = time.monotonic() + 5.0
        while ainda_varrendo(barramento) and time.monotonic() < limite:
            time.sleep(0.1)
        assert not ainda_varrendo(barramento), (
            "a ponte morreu e a varredura continuou de pé no adaptador — é o "
            "custo de rádio que esta sprint existe para não pagar"
        )
    finally:
        if processo.poll() is None:
            processo.kill()
            processo.wait(timeout=10)


def test_sem_o_gancho_a_raiz_de_teste_continua_inerte(barramento: Path) -> None:
    """A guarda antiga continua inteira: raiz de teste, sem gancho, não fala."""
    env = _ambiente(barramento)
    env.pop("HEFESTO_BT_BIN")
    feito = subprocess.run(
        ["bash", str(PONTE), "descobrir", "1"],
        capture_output=True,
        text=True,
        input=ENTRADA,
        env=env,
        timeout=30,
        check=False,
    )
    assert feito.returncode == 1, feito.stdout
    assert "não está na mesa" in feito.stderr
    assert feito.stdout == ""


def test_o_gancho_do_barramento_morre_sob_sudo(barramento: Path) -> None:
    """Contenção 3: os ganchos de teste são inertes sob sudo."""
    env = _ambiente(barramento)
    env["SUDO_UID"] = "1000"
    feito = subprocess.run(
        ["bash", str(PONTE), "descobrir", "1"],
        capture_output=True,
        text=True,
        input=ENTRADA,
        env=env,
        timeout=30,
        check=False,
    )
    assert feito.returncode == 1, feito.stdout
    assert feito.stdout == "", "o gancho sobreviveu ao sudo"
