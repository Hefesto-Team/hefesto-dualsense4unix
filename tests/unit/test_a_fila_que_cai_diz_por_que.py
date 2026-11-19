"""A fila que cai diz por quê, e perguntar se a fila roda não a trava.

A-FILA-QUE-CAI-DIZ-POR-QUE-E-A-PERGUNTA-NAO-A-TRAVA-01 (19/11/2026). TUDO É DE MENTIRA: o lar é
``tmp_path`` com ``XDG_*`` desviados; nenhum caso abre unidade nem roda o ajudante.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): o ``--rodar`` sem o
``try`` deixa o registro mudo; o ``em_curso`` que toma a trava exclusiva de volta reprova o caso
do fio (medido alternado); a trava ilegível lida como ocupada reprova o caso da trava
ilegível; a unidade da fila sem o diário reprova o caso do stderr.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.integrations import fora_do_servico as fds


@pytest.fixture(autouse=True)
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    casa = tmp_path / "casa"
    for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_STATE_HOME", ".local/state"),
                     ("XDG_CACHE_HOME", ".cache"), ("XDG_DATA_HOME", ".local/share"),
                     ("XDG_RUNTIME_DIR", "run")):
        (casa / sub).mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv(var, str(casa / sub))
    monkeypatch.setenv("HOME", str(casa))
    return casa


def _peca(ident: str) -> at.Peca:
    return at.Peca(ident, ident.upper(), "dica", "todos", lambda _r: at.Versoes("1.0", "1.1"))


def test_a_fila_que_levanta_deixa_o_traceback_e_fecha_o_andamento_com_o_motivo(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-A-FILA-QUE-CAI-DIZ-POR-QUE: o registro traz o traceback e o andamento, o motivo."""
    def rodar(_ids: Any, **_kw: Any) -> int:
        lista = [_peca("a"), _peca("b")]
        versoes = {p.id: at.Versoes("1.0", "1.1") for p in lista}
        andamento = at._Andamento(lista, versoes, dict.fromkeys(versoes, at.SUBIR))
        andamento.peca("a")["selo"] = at.INSTALANDO
        andamento.gravar()
        raise ValueError("o andamento estragou")

    monkeypatch.setattr(at, "rodar", rodar)
    with pytest.raises(ValueError):
        at.main(["--rodar", "a", "b"])
    registro = at.caminho_do_registro().read_text(encoding="utf-8")
    assert "a fila caiu: o andamento estragou" in registro
    assert "Traceback" in registro and "ValueError: o andamento estragou" in registro
    andamento = at._ler_json(at._estado() / at.ARQUIVO_DO_ANDAMENTO)
    assert andamento["fase"] == at.PARADO
    assert andamento["motivo"] == "a fila caiu: o andamento estragou"
    linhas = {p["id"]: p for p in andamento["pecas"]}
    assert linhas["a"]["selo"] == at.FILA
    assert linhas["a"]["motivo"] == "a fila caiu: o andamento estragou"
    assert linhas["b"]["motivo"] == ""


def test_perguntar_em_laco_nao_impede_a_fila_de_tomar_a_trava() -> None:
    """D-1911-A-FILA-QUE-CAI-DIZ-POR-QUE: a pergunta da tela não toma a trava da fila."""
    parar = threading.Event()
    respostas: list[bool] = []

    def perguntar() -> None:
        while not parar.is_set():
            respostas.append(at.em_curso())

    fio = threading.Thread(target=perguntar)
    fio.start()
    recusadas = 0
    try:
        for _ in range(3000):
            trava = at._a_trava()
            if trava is None:
                recusadas += 1
            else:
                at.os.close(trava)
    finally:
        parar.set()
        fio.join()
    assert respostas, "o fio não perguntou"
    assert recusadas == 0, f"a fila perdeu a trava {recusadas} vezes para a pergunta"


def test_a_fila_viva_responde_e_a_trava_ilegivel_e_erro_dito() -> None:
    assert at.em_curso() is False
    trava = at._a_trava()
    assert trava is not None
    try:
        assert at.em_curso() is True
    finally:
        at.os.close(trava)
    assert at.em_curso() is False
    caminho = at._runtime() / at.TRAVA
    caminho.chmod(0)
    try:
        assert at.em_curso() is False
    finally:
        caminho.chmod(0o600)
    assert "a trava não abre" in at.caminho_do_registro().read_text(encoding="utf-8")


def test_o_stderr_da_fila_vai_ao_diario() -> None:
    """D-1911-A-FILA-QUE-CAI-DIZ-POR-QUE: o erro que mata o processo antes do registro fica no
    diário do usuário."""
    recebido: dict[str, Any] = {}
    assert at.soltar(["a"], abrir=lambda argv, **kw: recebido.update(kw))
    assert recebido["diario"] is True
    linha = fds.argv_da_unidade(["x"], {}, unidade="u.service", forma="ExitType=main", oom=None,
                                diario=True)
    assert "--property=StandardError=journal" in linha
    assert "--property=StandardError=null" in fds.argv_da_unidade(
        ["x"], {}, unidade="u.service", forma="ExitType=main", oom=None)
