"""A peça Python monta as rodas ao baixar, instala sem rede e volta se o Hefesto não sobe.

O-PYTHON-SOBE-SEM-COMPILAR-NA-HORA-E-VOLTA-SE-QUEBRAR-01 (09/11/2026). O pip é um falso_pip com um
índice de mentira: o ``evdev`` 2.0.0 só existe em fonte, como no índice de verdade, e o
``install --no-index`` que acha só o fonte falha como falhou na máquina de quem usa. Nada vai à
rede: o ``install`` sem ``--no-index`` reprova.

AS MORDIDAS (feitas na sprint, com a cura devolvida): o «Baixar» de volta ao ``pip download``
reprova o caso do fonte (o «Instalar» acha só o ``.tar.gz``); o «Instalar» sem a conferência
reprova o caso da volta (o ``evdev`` 2.0.0 fica); a prova sem a linha do ``_find_device`` reprova
o caso do evdev que mudou o gancho.

O-PYTHON-QUE-FALHA-VOLTA-E-A-TROCA-ESPERA-O-REINICIO-01 (19/11/2026), AS MORDIDAS: o ``rc != 0``
sem a volta reprova o caso do pip que quebra na segunda roda; o voltar sem segurar a versão por
biblioteca reprova o caso da segurada; a troca de volta ao «instalar» reprova o caso da ordem.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import atualizador as at
from hefesto_dualsense4unix.app.actions import pecas_do_atualizador as pa

_atrasadas_de_verdade = pa._atrasadas
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
        self.quebra_em: tuple[str, str] | None = None

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
                if (nome, versao) == self.quebra_em:
                    return 1, f"ERROR: No space left on device: {nome}"
                self.instalados[nome] = versao
            return 0, ""
        return 2, f"verbo sem falso_pip: {verbo}"


@pytest.fixture
def pip(monkeypatch: pytest.MonkeyPatch) -> _PipDeMentira:
    falso_pip = _PipDeMentira()
    monkeypatch.setattr(pa, "_pip", falso_pip)
    monkeypatch.setattr(pa, "_atrasadas", lambda _corte=None: {
        nome: (falso_pip.instalados[nome], para)
        for nome, para in (("evdev", "2.0.0"), ("pydantic", "2.14.3"))
        if falso_pip.instalados[nome] != para})
    return falso_pip


def _baixar_e_instalar() -> dict[str, Any]:
    dados = pa._baixar_o_python(at.Passo(), {})
    pa._instalar_o_python(at.Passo(), dados)
    pa._trocar_o_python(dados)
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
                     peca.baixar, peca.instalar, peca.aplicar, peca.voltar, trocar=peca.trocar)]
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


def test_o_pip_que_quebra_na_segunda_roda_volta_as_de_antes_e_prova(
        pip: _PipDeMentira, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-O-PYTHON-TROCA-LOGO-ANTES-DO-REINICIO: o pip que falha no meio volta e se prova."""
    provas: list[dict[str, str]] = []
    monkeypatch.setattr(pa, "_o_produto_sobe", lambda: provas.append(dict(pip.instalados)) or "")
    pip.quebra_em = ("pydantic", "2.14.3")
    with pytest.raises(at.EtapaFalhouError) as erro:
        _baixar_e_instalar()
    assert pip.instalados == {"evdev": "1.9.3", "pydantic": "2.13.5"}
    assert provas == [{"evdev": "1.9.3", "pydantic": "2.13.5"}], "a volta não se provou"
    assert "No space left" in str(erro.value) and "voltou às versões de antes" in str(erro.value)


def test_a_versao_recusada_pelo_voltar_nao_volta_quando_outra_publica(
        pip: _PipDeMentira, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-O-PYTHON-TROCA-LOGO-ANTES-DO-REINICIO: o segurado do Python é por biblioteca."""
    monkeypatch.setattr(pa, "_o_produto_sobe", lambda: "")
    reinicios: list[bool] = []
    monkeypatch.setattr(at, "_reiniciar_o_servico", lambda: reinicios.append(True) or True)
    dados = _baixar_e_instalar()
    pa._voltar_o_python({"dados": dados})
    assert pip.instalados == {"evdev": "1.9.3", "pydantic": "2.13.5"} and reinicios == [True]
    publicadas = [("evdev", "2.0.0"), ("pydantic", "2.14.3")]
    monkeypatch.setattr(pa, "_dependencias_do_produto", lambda: ["evdev", "pydantic"])
    monkeypatch.setattr(pa, "_saida", lambda _argv, **_k: json.dumps(
        [{"name": n, "version": pip.instalados[n], "latest_version": u} for n, u in publicadas]))
    assert _atrasadas_de_verdade() == {}
    publicadas[1] = ("pydantic", "2.15.0")
    assert _atrasadas_de_verdade() == {"pydantic": ("2.13.5", "2.15.0")}
    publicadas[0] = ("evdev", "2.0.1")
    assert _atrasadas_de_verdade()["evdev"] == ("1.9.3", "2.0.1")


def test_a_troca_na_venv_vem_logo_antes_do_reinicio(
        pip: _PipDeMentira, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-1911-O-PYTHON-TROCA-LOGO-ANTES-DO-REINICIO: as rodas trocam na etapa do fim, logo antes do
    reinício do serviço, depois das outras peças."""
    eventos: list[str] = []
    monkeypatch.setattr(pa, "_o_produto_sobe", lambda: "")
    pip_de_antes = pa._pip

    def pip_que_anota(*args: str, **k: Any) -> tuple[int, str]:
        if args[0] == "install":
            eventos.append("pip install")
        return pip_de_antes(*args, **k)

    monkeypatch.setattr(pa, "_pip", pip_que_anota)
    peca = next(p for p in pa.registro() if p.id == "python")
    python = at.Peca(peca.id, peca.nome, peca.dica, peca.dica_do_aplicar,
                     lambda _rede: at.Versoes("", "2", rotulo="2 pacotes", nova=True),
                     peca.baixar, peca.instalar, peca.aplicar, peca.voltar, trocar=peca.trocar)

    def etapa(nome: str) -> Any:
        return lambda _p, _d: eventos.append(nome)

    outra = at.Peca("b", "B", "dica", "todos", lambda _r: at.Versoes("1", "2"),
                    etapa("b:baixar"), etapa("b:instalar"), etapa("b:aplicar"))
    at.conferir(rede=True, lista=[python, outra])
    rc = at.rodar(["python", "b"], lista=[python, outra], jogo_aberto=lambda: False,
                  reiniciar=lambda: eventos.append("reiniciar") or True,
                  reabrir=lambda: eventos.append("reabrir") or True, dormir=lambda _s: None)
    assert rc == 0, at.ler_o_andamento()
    assert eventos == ["b:baixar", "b:instalar", "b:aplicar", "pip install", "reiniciar",
                       "reabrir"]
    assert pip.instalados == {"evdev": "2.0.0", "pydantic": "2.14.3"}
    assert at.ler_o_andamento()["pecas"][0]["selo"] == at.PRONTA
