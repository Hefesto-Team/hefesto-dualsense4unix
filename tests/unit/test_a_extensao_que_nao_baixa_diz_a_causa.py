"""A-EXTENSAO-QUE-NAO-BAIXA-DIZ-A-CAUSA-E-O-GESTO-01 — a recusa do clone diz a causa e o gesto.

Medido em 31/10/2026 com `git clone --depth 1 --quiet` (git 2.43, `LC_ALL=C`): a última linha do
git ia crua para a tela, em inglês, e por ssh era só «and the repository exists.». As saídas
abaixo são as medidas, com o host e o caminho trocados por nomes de mentira.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.instalador import (
    FRASE_PEDE_LOGIN,
    FRASE_SEM_CAUSA,
    FRASE_SEM_CONEXAO_SEGURA,
    FRASE_SEM_EXTENSAO,
    FRASE_SEM_REDE,
    InstalacaoRecusadaError,
    Lugares,
    frase_da_recusa_do_git,
    instalar,
)

POR_SSH = ("fatal: Could not read from remote repository.\n\n"
           "Please make sure you have the correct access rights\nand the repository exists.\n")

MEDIDOS = {
    "host que não resolve": (
        "fatal: unable to access 'https://exemplo.invalid/a/b.git/': "
        "Could not resolve host: exemplo.invalid\n", FRASE_SEM_REDE),
    "porta fechada": (
        "fatal: unable to access 'https://127.0.0.1:9/x.git/': Failed to connect to 127.0.0.1 "
        "port 9 after 0 ms: Couldn't connect to server\n", FRASE_SEM_REDE),
    "ssh sem host": (
        "ssh: Could not resolve hostname exemplo.invalid: Name or service not known\n" + POR_SSH,
        FRASE_SEM_REDE),
    "ssh recusado": (
        "ssh: connect to host 127.0.0.1 port 9: Connection refused\n" + POR_SSH, FRASE_SEM_REDE),
    "ssh sem chave": (
        "git@exemplo.invalid: Permission denied (publickey).\n" + POR_SSH, FRASE_PEDE_LOGIN),
    "ssh sem repositório": ("ERROR: Repository not found.\n" + POR_SSH, FRASE_SEM_EXTENSAO),
    "https sem repositório": (
        "remote: Repository not found.\n"
        "fatal: repository 'https://exemplo.invalid/fulano/nada/' not found\n",
        FRASE_SEM_EXTENSAO),
    "https que pede login": (
        "fatal: could not read Username for 'https://exemplo.invalid': "
        "terminal prompts disabled\n", FRASE_PEDE_LOGIN),
    "caminho sem repositório": (
        "fatal: repository '/tmp/exemplo/nao-existe' does not exist\n", FRASE_SEM_EXTENSAO),
    "file:// sem repositório": (
        "fatal: '/tmp/exemplo/nao-existe' does not appear to be a git repository\n" + POR_SSH,
        FRASE_SEM_EXTENSAO),
    "certificado inválido": (
        "fatal: unable to access 'https://exemplo.invalid/x.git/': server certificate "
        "verification failed. CAfile: none CRLfile: none\n", FRASE_SEM_CONEXAO_SEGURA),
    "sem causa conhecida": ("fatal: algo que o git ainda não disse\n", FRASE_SEM_CAUSA),
    "sem nada no erro": ("", FRASE_SEM_CAUSA),
}


@pytest.mark.parametrize("caso", list(MEDIDOS))
def test_cada_erro_medido_vira_a_frase_da_causa(caso: str) -> None:
    """Cada saída medida do git dá a frase da sua causa, sem o inglês do git."""
    erro, esperada = MEDIDOS[caso]
    frase = frase_da_recusa_do_git(erro)
    assert frase == esperada, (caso, frase)
    assert "git" not in frase.lower() and "fatal" not in frase.lower()


def test_a_versao_que_nao_existe_diz_o_nome_pedido() -> None:
    """O `--ref` que o endereço não tem dá a frase da versão, com o nome que se pediu."""
    erro = ("warning: Could not find remote branch v9.9 to clone.\n"
            "fatal: Remote branch v9.9 not found in upstream origin\n")
    assert frase_da_recusa_do_git(erro, "v9.9") == (
        "A versão «v9.9» não existe nesse endereço. Confira o nome da versão.")


def test_o_endereco_com_palavra_de_outra_causa_nao_engana() -> None:
    """O endereço vem entre aspas no erro do git e sai antes da leitura: uma pasta chamada
    «Permission denied» que não existe é endereço errado, não login."""
    erro = "fatal: repository '/tmp/Permission denied/Connection refused' does not exist\n"
    assert frase_da_recusa_do_git(erro) == FRASE_SEM_EXTENSAO


def test_toda_frase_e_curta_e_diz_o_gesto() -> None:
    """Toda frase cabe numa linha da tela e manda conferir ou tentar alguma coisa."""
    frases = (FRASE_SEM_REDE, FRASE_SEM_CONEXAO_SEGURA, FRASE_SEM_EXTENSAO, FRASE_PEDE_LOGIN,
              FRASE_SEM_CAUSA, instalador.FRASE_SEM_VERSAO, instalador.FRASE_DO_PRAZO)
    for frase in frases:
        assert len(frase) <= 120, frase
        assert re.search(r"\b(Confira|tente|use)\b", frase), frase


def test_o_clone_de_verdade_sem_repositorio_diz_o_endereco(tmp_path: Path) -> None:
    """O git de verdade, num caminho cru e num `file://` sem repositório: a frase do endereço."""
    lar = Lugares(codigo=tmp_path / "codigo", dados=tmp_path / "dados",  # (noqa-acento)
                  registro=tmp_path / "registro.json", estado=tmp_path / "estado.json")
    for origem in (str(tmp_path / "nao-existe"), f"file://{tmp_path}/nao-existe"):
        with pytest.raises(InstalacaoRecusadaError) as recusa:
            instalar(origem, lugares=lar)
        assert recusa.value.frase == FRASE_SEM_EXTENSAO, (origem, recusa.value.frase)


def test_o_prazo_estourado_diz_os_minutos(monkeypatch: pytest.MonkeyPatch,
                                          tmp_path: Path) -> None:
    """O clone que passa do prazo dá a frase do tempo, com o prazo em minutos."""
    import subprocess

    def demora(*_a: object, **_k: object) -> None:
        raise subprocess.TimeoutExpired(cmd="git", timeout=instalador._PRAZO_DO_GIT_S)

    monkeypatch.setattr(instalador, "_git", demora)
    with pytest.raises(InstalacaoRecusadaError) as recusa:
        instalador._clonar("https://exemplo.invalid/x.git", None, tmp_path / "mod")
    assert recusa.value.frase == instalador.FRASE_DO_PRAZO.format(minutos=5)
