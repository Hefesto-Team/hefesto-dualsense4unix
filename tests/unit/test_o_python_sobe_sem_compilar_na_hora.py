"""A peça Python monta as rodas ao baixar, instala sem rede e volta se o Hefesto não sobe.

O-PYTHON-SOBE-SEM-COMPILAR-NA-HORA-E-VOLTA-SE-QUEBRAR-01 (09/11/2026). O pip é um falso_pip com um
índice de mentira: o ``evdev`` 2.0.0 só existe em fonte, como no índice de verdade, e o
``install --no-index`` que acha só o fonte falha como falhou na máquina de quem usa. Nada vai à
rede: o ``install`` sem ``--no-index`` reprova.

AS MORDIDAS (feitas na sprint, com a cura devolvida): o «Baixar» de volta ao ``pip download``
reprova o caso do fonte (o «Instalar» acha só o ``.tar.gz``); o «Instalar» sem a conferência
reprova o caso da volta (o ``evdev`` 2.0.0 fica); a prova sem a linha do ``_find_device`` reprova
o caso do evdev que mudou o gancho.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa

SO_FONTE = {"evdev"}
NO_INDICE = {("evdev", "2.0.0"), ("evdev", "1.9.3"), ("pydantic", "2.14.3"),
             ("pydantic", "2.13.5")}


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


class _PipDeMentira:
    def __init__(self) -> None:
        self.instalados = {"evdev": "1.9.3", "pydantic": "2.13.5"}
        self.chamadas: list[tuple[str, ...]] = []

    @staticmethod
    def _pedidos(args: tuple[str, ...]) -> list[tuple[str, str]]:
        return [tuple(a.split("==", 1)) for a in args if "==" in a]  # type: ignore[misc]

    def __call__(self, *args: str, **_k: Any) -> tuple[int, str]:
        self.chamadas.append(args)
        verbo = args[0]
        if verbo in ("download", "wheel"):
            pasta = Path(args[args.index("--dest" if verbo == "download" else "--wheel-dir") + 1])
            pasta.mkdir(parents=True, exist_ok=True)
            for nome, versao in self._pedidos(args):
                if (nome, versao) not in NO_INDICE:
                    return 1, f"ERROR: No matching distribution found for {nome}=={versao}"
                fonte = nome in SO_FONTE and verbo == "download"
                arquivo = (f"{nome}-{versao}.tar.gz" if fonte
                           else f"{nome}-{versao}-cp312-cp312-linux_x86_64.whl")
                (pasta / arquivo).write_bytes(b"")
            return 0, ""
        if verbo == "install":
            if "--no-index" not in args:
                return 1, "o teste da peça Python foi à rede"
            pasta = Path(args[args.index("--find-links") + 1])
            for nome, versao in self._pedidos(args):
                if any(pasta.glob(f"{nome}-{versao}-*.whl")):
                    continue
                if (pasta / f"{nome}-{versao}.tar.gz").exists():
                    return 1, (f"ERROR: Failed to build '{nome}' when installing build "
                               f"dependencies for {nome}")
                return 1, f"ERROR: No matching distribution found for {nome}=={versao}"
            for nome, versao in self._pedidos(args):
                self.instalados[nome] = versao
            return 0, ""
        return 2, f"verbo sem falso_pip: {verbo}"


@pytest.fixture
def pip(monkeypatch: pytest.MonkeyPatch) -> _PipDeMentira:
    falso_pip = _PipDeMentira()
    monkeypatch.setattr(pa, "_pip", falso_pip)
    monkeypatch.setattr(pa, "_atrasadas", lambda: {
        nome: (falso_pip.instalados[nome], para)
        for nome, para in (("evdev", "2.0.0"), ("pydantic", "2.14.3"))
        if falso_pip.instalados[nome] != para})
    return falso_pip


def _baixar_e_instalar() -> dict[str, Any]:
    dados = pa._baixar_o_python(at.Passo(), {})
    pa._instalar_o_python(at.Passo(), dados)
    return dados


def test_o_pacote_so_em_fonte_vira_roda_ao_baixar_e_instala_sem_rede(
        pip: _PipDeMentira, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pa, "_o_produto_sobe", lambda: "")
    _baixar_e_instalar()
    assert pip.instalados == {"evdev": "2.0.0", "pydantic": "2.14.3"}
    assert not any(c[0] == "download" for c in pip.chamadas)
    instalar = next(c for c in pip.chamadas if c[0] == "install")
    assert "--no-index" in instalar and "--only-binary" in instalar


def test_o_hefesto_que_nao_sobe_com_as_novas_volta_as_de_antes_sem_rede(
        pip: _PipDeMentira, monkeypatch: pytest.MonkeyPatch) -> None:
    """Prova da D-0911-O-PYTHON-SOBE-POR-RODAS-E-VOLTA-SE-QUEBRAR: não sobe, volta sem rede."""
    monkeypatch.setattr(pa, "_o_produto_sobe", lambda: (
        "o evdev novo não chama o _find_device que a cura do pad usa"
        if pip.instalados["evdev"] == "2.0.0" else ""))
    with pytest.raises(at.EtapaFalhouError) as erro:
        _baixar_e_instalar()
    assert pip.instalados == {"evdev": "1.9.3", "pydantic": "2.13.5"}
    assert "_find_device" in str(erro.value) and "voltou às versões de antes" in str(erro.value)


def test_o_motor_marca_a_falha_e_nao_troca_a_anterior(
        pip: _PipDeMentira, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pa, "_o_produto_sobe", lambda: "quebrou")
    peca = next(p for p in pa.registro() if p.id == "python")
    lista = [at.Peca(peca.id, peca.nome, peca.dica, peca.dica_do_aplicar,
                     lambda _rede: at.Versoes("", "2", rotulo="2 pacotes", nova=True),
                     peca.baixar, peca.instalar, peca.aplicar, peca.voltar)]
    at.conferir(rede=True, lista=lista)
    rc = at.rodar(["python"], lista=lista, jogo_aberto=lambda: False,
                  reiniciar=lambda: True, reabrir=lambda: True, dormir=lambda _s: None)
    linha = at.ler_o_andamento()["pecas"][0]
    assert rc == 1 and linha["selo"] == at.FALHOU and "voltou" in linha["motivo"]
    assert "python" not in at.ler_as_anteriores()
    assert pip.instalados["evdev"] == "1.9.3"


def test_a_prova_do_produto_sobe_no_python_de_agora() -> None:
    assert pa._o_produto_sobe() == ""


def test_a_prova_reprova_o_evdev_que_nao_chama_mais_o_gancho(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    falso = tmp_path / "falso" / "evdev"
    falso.mkdir(parents=True)
    (falso / "__init__.py").write_text(
        "class UInput:\n    def __init__(self, *a, **k):\n        self.fd = 0\n",
        encoding="utf-8")
    origem = Path(pa.__file__).resolve().parents[3]
    monkeypatch.setenv("PYTHONPATH", f"{falso.parent}:{origem}")
    motivo = pa._o_produto_sobe()
    assert "_find_device" in motivo, motivo
