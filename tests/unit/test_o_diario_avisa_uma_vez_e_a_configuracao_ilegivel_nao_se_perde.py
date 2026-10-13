"""O diário avisa uma vez, e a configuração ilegível não se perde.

O-DIARIO-AVISA-UMA-VEZ-E-A-CONFIGURACAO-ILEGIVEL-NAO-SE-PERDE-01: o perfil
corrompido, o ouvinte do som sem servidor e o `maquina.json` truncado.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import stat
import textwrap
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.subsystems import ouvinte_do_som as ods
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.utils import maquina

so_sem_root = pytest.mark.skipif(
    os.geteuid() == 0,
    reason="como root o chmod 000 não nega nada, então a régua não morde",
)

# -- perfis -----------------------------------------------------------------


@pytest.fixture
def pasta_de_perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "perfis"
    alvo.mkdir()
    monkeypatch.setattr(loader, "profiles_dir", lambda ensure=False: alvo)
    return alvo


def _avisos(captured: Sequence[Mapping[str, Any]], evento: str) -> list[Mapping[str, Any]]:
    return [r for r in captured if r.get("event") == evento]


def test_o_perfil_corrompido_avisa_uma_vez_e_de_novo_quando_muda(
    pasta_de_perfis: Path,
) -> None:
    ruim = pasta_de_perfis / "ruim.json"
    ruim.write_text("{ isso não é json", encoding="utf-8")
    with structlog.testing.capture_logs() as captured:
        for _ in range(5):
            loader.load_all_profiles()
    assert len(_avisos(captured, "profile_invalid")) == 1

    ruim.write_text("{ ainda não é json, e maior", encoding="utf-8")
    with structlog.testing.capture_logs() as captured:
        for _ in range(5):
            loader.load_all_profiles()
    assert len(_avisos(captured, "profile_invalid")) == 1


def test_as_quatro_portas_de_leitura_dividem_a_mesma_memoria(
    pasta_de_perfis: Path,
) -> None:
    (pasta_de_perfis / "ruim.json").write_text("[1,", encoding="utf-8")
    with structlog.testing.capture_logs() as captured:
        loader.load_all_profiles()
        loader.perfis_para_consulta()
        loader.perfil_em_disco("ruim")
        loader.arquivo_do_perfil("inexistente", pasta_de_perfis)
    assert len(_avisos(captured, "profile_invalid")) == 1


def test_quem_pergunta_continua_vendo_a_lista_inteira(pasta_de_perfis: Path) -> None:
    (pasta_de_perfis / "um.json").write_text("{", encoding="utf-8")
    (pasta_de_perfis / "dois.json").write_text("[", encoding="utf-8")
    loader.load_all_profiles()
    loader.load_all_profiles()
    nomes = sorted(nome for nome, _erro in loader.audit_profiles())
    assert nomes == ["dois.json", "um.json"]
    assert (pasta_de_perfis / "um.json").exists(), "o arquivo não é renomeado"


# -- som --------------------------------------------------------------------


class _Diario:
    def __init__(self) -> None:
        self.eventos: list[str] = []

    def info(self, evento: str, **_k: Any) -> None:
        self.eventos.append(evento)

    warning = info
    debug = info
    error = info


def _pactl_de_mentira(pasta: Path, mortes: int) -> Path:
    """Um `pactl` cujo `subscribe` morre na hora nas `mortes` primeiras vezes."""
    bin_ = pasta / "bin"
    bin_.mkdir()
    contador = pasta / "contador"
    contador.write_text("0", encoding="utf-8")
    script = bin_ / "pactl"
    script.write_text(textwrap.dedent(f"""\
        #!/bin/bash
        if [ "$1" != "subscribe" ]; then exit 1; fi
        n=$(<{contador})
        echo $((n + 1)) > {contador}
        if [ "$n" -lt {mortes} ]; then exit 1; fi
        echo "Event 'change' on server #0"
        read -t 0.3 <> /dev/null
        """), encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return bin_


def _roda_o_ouvinte(monkeypatch: pytest.MonkeyPatch, bin_: Path, voltas: int) -> list[str]:
    """Roda o laço do ouvinte por `voltas` voltas do `subscribe` e o cancela."""
    diario = _Diario()
    monkeypatch.setenv("PATH", str(bin_))
    monkeypatch.setattr(ods, "ESPERA_PARA_RELIGAR_S", 0.0)
    monkeypatch.setattr(ods, "logger", diario)
    feitas = 0
    original = ods._uma_volta

    async def contando(daemon: Any, **k: Any) -> bool:
        nonlocal feitas
        if feitas >= voltas:
            raise asyncio.CancelledError
        feitas += 1
        return await original(daemon, **k)

    monkeypatch.setattr(ods, "_uma_volta", contando)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(ods.ouvinte_do_som_loop(SimpleNamespace(bus=None, _tasks=[])))
    return diario.eventos


def test_sem_servidor_o_ouvinte_avisa_uma_vez_e_nunca_diz_ligado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eventos = _roda_o_ouvinte(monkeypatch, _pactl_de_mentira(tmp_path, 999), voltas=6)
    assert eventos.count("ouvinte_do_som_sem_servidor") == 1, eventos
    assert "ouvinte_do_som_ligado" not in eventos, eventos
    assert "ouvinte_do_som_voltou" not in eventos, eventos


def test_o_servidor_que_volta_diz_voltou_e_nao_ligado(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eventos = _roda_o_ouvinte(monkeypatch, _pactl_de_mentira(tmp_path, 3), voltas=4)
    assert eventos.count("ouvinte_do_som_sem_servidor") == 1, eventos
    assert eventos.count("ouvinte_do_som_voltou") >= 1, eventos
    assert eventos.index("ouvinte_do_som_sem_servidor") < eventos.index(
        "ouvinte_do_som_voltou"
    )
    assert "ouvinte_do_som_ligado" not in eventos, eventos


def test_o_servidor_vivo_desde_o_inicio_diz_ligado_uma_vez_por_volta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    eventos = _roda_o_ouvinte(monkeypatch, _pactl_de_mentira(tmp_path, 0), voltas=2)
    assert eventos.count("ouvinte_do_som_ligado") == 2, eventos
    assert "ouvinte_do_som_sem_servidor" not in eventos, eventos


def test_o_recuo_dobra_ate_o_teto(monkeypatch: pytest.MonkeyPatch) -> None:
    esperas: list[float] = []

    async def morta(_daemon: Any, **_k: Any) -> bool:
        return False

    async def dormir(segundos: float) -> None:
        esperas.append(segundos)
        if len(esperas) >= 8:
            raise asyncio.CancelledError

    monkeypatch.setattr(shutil, "which", lambda _n: "/usr/bin/pactl")
    monkeypatch.setattr(ods, "_uma_volta", morta)
    monkeypatch.setattr(asyncio, "sleep", dormir)
    monkeypatch.setattr(ods, "logger", _Diario())

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(ods.ouvinte_do_som_loop(SimpleNamespace(bus=None, _tasks=[])))
    assert esperas == [3.0, 6.0, 12.0, 24.0, 48.0, 60.0, 60.0, 60.0]


# -- máquina ----------------------------------------------------------------

TRUNCADO = '{"version": 1, "computador": {"global": {"modo'


def _ao_lado() -> list[Path]:
    arquivo = maquina.caminho_da_maquina()
    return sorted(arquivo.parent.glob(f"{arquivo.name}.ilegivel-*"))


def test_o_maquina_json_truncado_vai_para_o_lado_antes_de_ser_refeito() -> None:
    arquivo = maquina.caminho_da_maquina()
    arquivo.write_text(TRUNCADO, encoding="utf-8")
    with structlog.testing.capture_logs() as captured:
        maquina.carregar_maquina()
        maquina.carregar_maquina()
        assert maquina.gravar_o_computador({}) is True
    assert len(_avisos(captured, "maquina_ilegivel")) == 1
    assert str(arquivo) == _avisos(captured, "maquina_ilegivel")[0]["caminho"]
    guardados = _ao_lado()
    assert len(guardados) == 1
    assert guardados[0].read_text(encoding="utf-8") == TRUNCADO
    assert maquina.carregar_maquina().version == 1
    assert '"version": 1' in arquivo.read_text(encoding="utf-8")


def test_o_documento_que_nao_e_objeto_tambem_e_guardado() -> None:
    arquivo = maquina.caminho_da_maquina()
    arquivo.write_text("[1, 2, 3]", encoding="utf-8")
    assert maquina.gravar_o_computador({}) is True
    assert [p.read_text(encoding="utf-8") for p in _ao_lado()] == ["[1, 2, 3]"]


def test_o_arquivo_ausente_nao_deixa_copia_nenhuma() -> None:
    assert not maquina.caminho_da_maquina().exists()
    assert maquina.gravar_o_computador({}) is True
    assert _ao_lado() == []


def test_duas_gravacoes_seguidas_sobre_lixo_guardam_so_a_primeira() -> None:
    maquina.caminho_da_maquina().write_text(TRUNCADO, encoding="utf-8")
    assert maquina.gravar_o_computador({}) is True
    assert maquina.gravar_o_computador({}) is True
    assert len(_ao_lado()) == 1


@pytest.fixture
def maquina_sem_leitura() -> Iterator[Path]:
    arquivo = maquina.caminho_da_maquina()
    arquivo.write_text('{"version": 1}', encoding="utf-8")
    arquivo.chmod(0)
    yield arquivo
    arquivo.chmod(stat.S_IRUSR | stat.S_IWUSR)


@so_sem_root
def test_o_arquivo_que_nao_se_le_por_permissao_nao_e_escrito_por_cima(
    maquina_sem_leitura: Path,
) -> None:
    with structlog.testing.capture_logs() as captured:
        assert maquina.gravar_o_computador({}) is False
    recusas = _avisos(captured, "maquina_save_recusado_arquivo_nao_lido")
    assert len(recusas) == 1
    assert str(maquina_sem_leitura) in recusas[0]["caminho"]
    assert _ao_lado() == []
    maquina_sem_leitura.chmod(stat.S_IRUSR | stat.S_IWUSR)
    assert maquina_sem_leitura.read_text(encoding="utf-8") == '{"version": 1}'
