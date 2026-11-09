"""A rodada do Proton roda fora da máquina de quem joga: a matriz, o runtime e a perna não medida.

A-RODADA-DO-PROTON-RODA-FORA-DA-MAQUINA-DE-QUEM-JOGA-01. A rodada roda a matriz com um ensaio de
mentira, escreve a linha do recibo com o buildid do runtime e julga as três provas; a perna que
o runner não sustenta sai «não medida». Nada aqui roda Proton, Steam ou rede.

AS MORDIDAS: o endpoint sem os canais 3-4, o vpad sem o report 0x02 e a fonte calada reprovam
`test_cada_prova_estragada_reprova_a_rodada`; tirar o `sustenta` da `rodada` (montar toda perna)
reprova `test_a_perna_nao_medida_nunca_vira_passou`; tirar a coluna `runtime` da
`linha_do_recibo` reprova `test_a_linha_leva_o_runtime_da_rodada`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from hefesto_dualsense4unix.integrations import qualificar_proton as qp

RAIZ = Path(__file__).resolve().parents[2]
ENSAIOS = RAIZ / "scripts" / "ensaios"
FLUXO = RAIZ / ".github" / "workflows" / "rodada-do-proton.yml"

SONDA_QUE_PASSA = "\n".join([
    '{"prova":"contagem","hid_sony":1,"vagas_xinput":1,"ordem_xinput":"0",'
    '"ks_por_container":{"c1":1}}',
    '{"prova":"haptica","achou":true,"canais":4,"tocou":true}',
    '{"prova":"gatilho","escreveu":true,"bytes":"0204"}',
    '{"prova":"microfone","achou":true,"fracao_no_tom":0.9}',
    '{"prova":"fim","container_sony":"c1"}',
])


def _carregar(nome: str) -> ModuleType:
    if str(ENSAIOS) not in sys.path:
        sys.path.insert(0, str(ENSAIOS))
    spec = importlib.util.spec_from_file_location(nome, ENSAIOS / f"{nome}.py")
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture()
def r() -> ModuleType:
    return _carregar("a_rodada_do_proton_candidato")


class _Ensaio:
    def __init__(self, r: ModuleType, *, eco: float = 0.9, bytes_no_uhid: str = "0204",
                 tom: bool = True, fora: frozenset[str] = frozenset()) -> None:
        self.r = r
        self.lado = r.MedidaDoOutroLado(eco, bytes_no_uhid, tom)
        self.fora = fora
        self.montados: list[str] = []

    def sustenta(self, caso: Any) -> str | None:
        return "sem o cabo no runner" if caso.transporte in self.fora else None

    def montar(self, caso: Any) -> dict[str, str]:
        self.montados.append(caso.nome())
        return {}

    def medir(self) -> Any:
        return self.lado

    def desmontar(self) -> None:
        return None


def _so_dualsense(r: ModuleType) -> list[Any]:
    return [c for c in r.matriz() if c.mascara == "dualsense" and c.vpads == 1]


def test_a_matriz_inteira_com_tudo_de_pe_passa(
    r: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(r, "rodar_a_sonda", lambda *_a, **_k: SONDA_QUE_PASSA)
    ensaio = _Ensaio(r)
    resultado = r.rodada(Path("/nada"), Path("/nada"), ensaio, _so_dualsense(r))
    assert resultado.estado() == qp.VEREDITO_PASSOU
    assert len(ensaio.montados) == len(_so_dualsense(r))
    caso_b = next(iter(resultado.relato.values()))
    assert caso_b["b_so_xinput_ve_o_controle"] is True
    assert str(caso_b["a_le_o_nativo"]).startswith("não medido")


@pytest.mark.parametrize(
    ("estrago", "prova"),
    [
        ({"eco": 0.1}, "canais 3-4"),
        ({"bytes_no_uhid": "0205"}, "chegou diferente"),
        ({"tom": False}, "microfone"),
    ],
)
def test_cada_prova_estragada_reprova_a_rodada(
    r: ModuleType, monkeypatch: pytest.MonkeyPatch, estrago: dict[str, Any], prova: str
) -> None:
    monkeypatch.setattr(r, "rodar_a_sonda", lambda *_a, **_k: SONDA_QUE_PASSA)
    resultado = r.rodada(Path("/nada"), Path("/nada"), _Ensaio(r, **estrago), _so_dualsense(r))
    assert resultado.estado() != qp.VEREDITO_PASSOU
    assert prova in resultado.estado(), resultado.estado()


def test_a_perna_nao_medida_nunca_vira_passou(
    r: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D-0811-A-RODADA-DO-PROTON-RODA-NO-RUNNER-DO-GITHUB."""
    monkeypatch.setattr(r, "rodar_a_sonda", lambda *_a, **_k: SONDA_QUE_PASSA)
    ensaio = _Ensaio(r, fora=frozenset({"cabo"}))
    resultado = r.rodada(Path("/nada"), Path("/nada"), ensaio, _so_dualsense(r))
    assert not any("cabo" in nome for nome in ensaio.montados)
    estado = resultado.estado()
    assert estado.startswith(qp.RODADA_NAO_MEDIDA) and "sem o cabo no runner" in estado
    linha = qp.linha_do_recibo(qp.Ficha(versao="GE-Proton11-12-x86_64"), "a" * 64, estado,
                               "2026-11-08", "26116036")
    (lida,) = qp.ler_recibo(",".join(qp.CAMPOS_DO_RECIBO) + "\n" + linha)
    assert lida["veredito"] == qp.RODADA_NAO_MEDIDA
    pino = {"name": "GE-Proton11-12-x86_64", "sha256": "a" * 64}
    assert qp.o_pino_sem_recibo(pino, [lida]) != []


def test_a_linha_leva_o_runtime_da_rodada() -> None:
    """D-0811-A-RODADA-DO-PROTON-RODA-NO-RUNNER-DO-GITHUB."""
    linha = qp.linha_do_recibo(qp.Ficha(versao="GE-Proton11-12-x86_64"), "a" * 64,
                               qp.VEREDITO_PASSOU, "2026-11-08", "26116036")
    (lida,) = qp.ler_recibo(",".join(qp.CAMPOS_DO_RECIBO) + "\n" + linha)
    assert lida["runtime"] == "26116036" and lida["veredito"] == qp.VEREDITO_PASSOU
    pino = {"name": "GE-Proton11-12-x86_64", "sha256": "a" * 64}
    assert qp.o_pino_sem_recibo(pino, [lida]) == []


def test_o_recibo_velho_sem_a_coluna_ainda_se_le() -> None:
    velho = (
        "versão,sha256,ficha,rodada,veredito,prova,data\n"
        "GE-Proton11-7,b,passou,herdada,passou,,d\n"
    )
    (lida,) = qp.ler_recibo(velho)
    assert lida["runtime"] == ""


def test_o_recibo_do_repositorio_tem_a_coluna_runtime() -> None:
    texto = (RAIZ / qp.CAMINHO_DO_RECIBO).read_text(encoding="utf-8")
    cabecalho = next(linha for linha in texto.splitlines() if not linha.startswith("#"))
    assert tuple(cabecalho.split(",")) == qp.CAMPOS_DO_RECIBO


def test_o_buildid_do_runtime_sai_da_pasta_instalada(r: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "steamapps").mkdir()
    (tmp_path / "steamapps" / f"appmanifest_{r.APPID_DO_RUNTIME}.acf").write_text(
        '"AppState"\n{\n\t"buildid"\t\t"26116036"\n}\n', encoding="utf-8"
    )
    assert r.buildid_do_runtime(tmp_path) == "26116036"
    assert r.buildid_do_runtime(tmp_path / "outra") == ""
    assert r.buildid_do_runtime(None) == ""


def test_o_runtime_entra_no_comando_da_sonda(r: ModuleType) -> None:
    sem = r.comando_da_sonda(Path("/ge"), Path("/s.exe"), None)
    com = r.comando_da_sonda(Path("/ge"), Path("/s.exe"), Path("/slr"))
    assert sem == ["/ge/proton", "run", "/s.exe"]
    assert com[0] == "/slr/_v2-entry-point" and com[-3:] == ["/ge/proton", "waitforexitandrun",
                                                            "/s.exe"]


def test_o_sonda_exe_fora_do_pino_e_recusado(
    r: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(r, "na_vm_ou_no_ci", lambda *_a, **_k: True)
    sonda = tmp_path / "sonda.exe"
    sonda.write_bytes(b"MZ outro")
    argv = [str(tmp_path), "--sonda", str(sonda), "--tarball-sha256", "a" * 64]
    assert r.main(argv) == r.RC_SONDA_SEM_PINO


def test_o_ensaio_do_runner_diz_a_peca_que_falta(tmp_path: Path) -> None:
    _carregar("a_rodada_do_proton_candidato")
    ensaio_da_vm = _carregar("ensaio_da_vm")
    r = sys.modules["a_rodada_do_proton_candidato"]
    radio, cabo = r.Caso(1, "radio", "dualsense", False), r.Caso(1, "cabo", "dualsense", False)

    sem_medida = ensaio_da_vm.EnsaioDaVm(None, rodar=lambda _a: 0)
    assert "não foi medido" in str(sem_medida.sustenta(radio))

    medida = tmp_path / "sonda.txt"
    medida.write_text("casa_radio=no_runner\ncasa_cabo=so_da_mao\n", encoding="utf-8")
    sem_som = ensaio_da_vm.EnsaioDaVm(medida, rodar=lambda _a: 1)
    assert "servidor de som" in str(sem_som.sustenta(radio))
    com_som = ensaio_da_vm.EnsaioDaVm(medida, rodar=lambda _a: 0)
    assert "casa_cabo=so_da_mao" in str(com_som.sustenta(cabo))
    assert com_som.sustenta(radio) == ensaio_da_vm.MONTAGEM_DAS_PROVAS


def test_o_fluxo_so_roda_a_mao_e_leva_o_runtime_ao_recibo() -> None:
    fluxo = yaml.safe_load(FLUXO.read_text(encoding="utf-8"))
    gatilhos = fluxo.get("on", fluxo.get(True))
    assert set(gatilhos) == {"workflow_dispatch"}
    (job,) = fluxo["jobs"].values()
    assert job["timeout-minutes"] <= 120
    texto = FLUXO.read_text(encoding="utf-8")
    assert "s/^compilar=//p' pino.txt" in texto
    assert "runtime=(--runtime slr)" in texto and "appmanifest_${SLR_APPID}.acf" in texto
    assert texto.index("80-prazo") < texto.index("apt-get")
