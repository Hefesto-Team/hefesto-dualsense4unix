"""AS-MODIFICACOES-MARCAM-O-GESTO-ESPERAM-PARAR-E-SAEM-NO-UNINSTALL-01.

Quatro defeitos medidos no conferente do mods-fds (10/10), um caso por defeito:

1. a escrita pela porta chegava ao loader sem a marca do gesto: a modificação
   escrevia como «ninguém» (o IPC marca ``ipc:<método>``);
2. o ``instalar`` ignorava o retorno do ``esperar_parar`` e trocava o código
   debaixo do processo vivo da versão anterior;
3. o ``ligar`` relia o manifesto do disco e aceitava a lista que estivesse lá,
   mesmo diferente da que quem chamou mostrou e ouviu o «sim»;
4. o ``uninstall.sh`` não conhecia as modificações: o processo vivo seguia de pé
   e a pasta de dados dela era varrida como «nenhum passo o nomeia».

O uninstall roda DE VERDADE, no lar de mentira da casa (HOME e XDG desviados,
guarda que sai se vazar, dublês no lugar de tudo o que muda a máquina). O
processo da modificação é um ``sleep`` do próprio teste, com o ambiente que o
supervisor poria; a mordida de cada caso está escrita como teste.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_mod
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.mods import instalador, porta
from hefesto_dualsense4unix.mods.instalador import (
    InstalacaoRecusadaError,
    Lugares,
    instalar,
    ler_registro,
    ligar,
    manifesto_instalado,
)
from tests.unit.test_as_modificacoes_rodam_fora_do_daemon import (
    UNIQ,
    _Cliente,
    _ligar_vendo,
    _manifesto,
    _pasta_do_mod,
    _porta_viva,
)
from tests.unit.test_o_uninstall_nao_deixa_rastro import (
    UNINSTALL,
    _casa_de_mentira,
    _desinstalar,
)


@pytest.fixture
def curto() -> Iterator[Path]:
    """Uma pasta de caminho curto: o socket Unix aceita até 107 bytes."""
    fora_do_tmp = "/var/tmp" if os.access("/var/tmp", os.W_OK) else None
    pasta = Path(tempfile.mkdtemp(prefix="hm", dir=fora_do_tmp))
    try:
        yield pasta
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


@pytest.fixture
def lar(curto: Path, monkeypatch: pytest.MonkeyPatch) -> Lugares:
    """O lar de mentira das modificações: HOME, XDG e a execução dentro da pasta curta."""
    casa, execucao = curto / "casa", curto / "run"
    for pasta in (casa, execucao):
        pasta.mkdir(mode=0o700)
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(casa / ".config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(casa / ".local/share"))
    monkeypatch.setenv("XDG_STATE_HOME", str(casa / ".local/state"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(casa / ".cache"))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(execucao))
    lugares = Lugares.do_xdg()
    for caminho in (lugares.codigo, lugares.dados, lugares.registro, lugares.estado):
        assert str(caminho).startswith(str(curto)), caminho
    return lugares


# -- 1. a escrita pela porta marca o gesto ---------------------------------------------


class _MarcaEspia:
    """No lugar do ``gesto_de_agora``: anota cada ``set`` e cada ``reset``."""

    def __init__(self) -> None:
        self.postas: list[str] = []
        self.soltas: list[str] = []
        self.valor: str | None = None

    def set(self, marca: str) -> str:
        self.postas.append(marca)
        anterior, self.valor = self.valor or "", marca
        return anterior

    def get(self) -> str | None:
        return self.valor

    def reset(self, token: str) -> None:
        self.soltas.append(self.valor or "")
        self.valor = token or None


def _escrever_pela_porta(
    curto: Path, espia: _MarcaEspia, *, escritor_quebra: bool = False
) -> list[str | None]:
    """Uma ``luz.set`` pela porta; devolve a marca que o handler enxergou."""
    vistas: list[str | None] = []

    async def corrida() -> None:
        bus = EventBus()
        sorte = await _porta_viva(curto, bus, ["escrever:luz"])

        async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
            vistas.append(espia.get())
            if escritor_quebra:
                raise RuntimeError("o aparelho não respondeu")
            return {"status": "ok"}

        sorte._escritor = escritor
        cliente = _Cliente(curto / "mods.sock")
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha-certa"})
            await asyncio.to_thread(
                cliente.pedir, "luz.set", {"uniq": UNIQ, "rgb": [1, 2, 3]})
        finally:
            cliente.fechar()
            await sorte.parar()

    asyncio.run(corrida())
    return vistas


def test_a_escrita_pela_porta_chega_ao_handler_com_a_marca_da_modificacao(
    curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    espia = _MarcaEspia()
    monkeypatch.setattr(porta, "gesto_de_agora", espia)
    assert _escrever_pela_porta(curto, espia) == ["mod:exemplo:luz.set"]
    assert espia.postas == ["mod:exemplo:luz.set"] and len(espia.soltas) == 1
    assert espia.get() is None


def test_a_marca_se_solta_mesmo_quando_a_escrita_falha(
    curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    espia = _MarcaEspia()
    monkeypatch.setattr(porta, "gesto_de_agora", espia)
    _escrever_pela_porta(curto, espia, escritor_quebra=True)
    assert len(espia.postas) == 1 and len(espia.soltas) == 1 and espia.get() is None


def test_a_marca_chega_ao_loader_de_verdade(
    curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem dublê da marca: o ``ContextVar`` do loader, lido dentro do handler."""
    from hefesto_dualsense4unix.profiles.loader import gesto_de_agora

    vistas: list[str | None] = []

    async def corrida() -> None:
        sorte = await _porta_viva(curto, EventBus(), ["escrever:luz"])

        async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
            vistas.append(gesto_de_agora.get())
            return {"status": "ok"}

        sorte._escritor = escritor
        cliente = _Cliente(curto / "mods.sock")
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha-certa"})
            await asyncio.to_thread(
                cliente.pedir, "luz.set", {"uniq": UNIQ, "rgb": [1, 2, 3]})
            await asyncio.to_thread(
                cliente.pedir, "luz.set", {"uniq": UNIQ, "rgb": [3, 2, 1]})
        finally:
            cliente.fechar()
            await sorte.parar()

    asyncio.run(corrida())
    assert vistas == ["mod:exemplo:luz.set", "mod:exemplo:luz.set"]
    assert gesto_de_agora.get() is None


# -- 2. o instalar não troca o código debaixo do processo vivo -------------------------


def test_a_versao_anterior_que_nao_parou_recusa_e_o_codigo_antigo_fica(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = _pasta_do_mod(curto / "fontes")
    instalar(str(pasta), lugares=lar)
    _ligar_vendo("exemplo", lar)
    antes = (lar.codigo / "exemplo" / "hefesto-mod.json").read_bytes()
    (pasta / "hefesto-mod.json").write_text(json.dumps(_manifesto(versao="0.2.0")))
    (pasta / "mod.py").write_text("# a versão nova\n", encoding="utf-8")
    monkeypatch.setattr(instalador, "esperar_parar", lambda *a, **k: False)

    with pytest.raises(InstalacaoRecusadaError) as recusa:
        instalar(str(pasta), lugares=lar)

    assert "não parou" in recusa.value.frase
    assert (lar.codigo / "exemplo" / "hefesto-mod.json").read_bytes() == antes
    assert (lar.codigo / "exemplo" / "mod.py").read_text(encoding="utf-8") != "# a versão nova\n"
    entrada = ler_registro(lar.registro)["exemplo"]
    assert entrada.versao == "0.1.0" and entrada.ligada, (
        "a recusa deixa a registro como estava: a que seguia ligada segue ligada")
    assert not [p for p in lar.codigo.iterdir() if p.name.startswith(".")], (
        "o que baixou para a troca não fica na pasta do código")


def test_a_versao_anterior_que_parou_atualiza_como_antes(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pasta = _pasta_do_mod(curto / "fontes")
    instalar(str(pasta), lugares=lar)
    _ligar_vendo("exemplo", lar)
    (pasta / "hefesto-mod.json").write_text(json.dumps(_manifesto(versao="0.2.0")))
    monkeypatch.setattr(instalador, "esperar_parar", lambda *a, **k: True)
    resultado = instalar(str(pasta), lugares=lar)
    assert resultado.entrada.versao == "0.2.0" and resultado.entrada.ligada


# -- 3. o ligar só liga com o que foi mostrado -----------------------------------------


def _trocar_o_pedido_no_disco(lar: Lugares, permissoes: list[str]) -> None:
    caminho = lar.codigo / "exemplo" / "hefesto-mod.json"
    caminho.write_text(json.dumps(_manifesto(permissoes=permissoes)), encoding="utf-8")


def test_o_ligar_recusa_se_o_manifesto_do_disco_pede_outra_lista(
    lar: Lugares, curto: Path
) -> None:
    instalar(str(_pasta_do_mod(curto / "fontes")), lugares=lar)
    vistas = list(manifesto_instalado("exemplo", lugares=lar).permissoes)
    _trocar_o_pedido_no_disco(lar, [*vistas, "rede:internet"])

    with pytest.raises(InstalacaoRecusadaError) as recusa:
        ligar("exemplo", permissoes_vistas=vistas, lugares=lar)

    assert "veja de novo" in recusa.value.frase
    entrada = ler_registro(lar.registro)["exemplo"]
    assert not entrada.ligada and "rede:internet" not in entrada.permissoes_aceitas


def test_o_ligar_recusa_tambem_a_lista_que_encolheu(lar: Lugares, curto: Path) -> None:
    instalar(str(_pasta_do_mod(curto / "fontes")), lugares=lar)
    vistas = list(manifesto_instalado("exemplo", lugares=lar).permissoes)
    _trocar_o_pedido_no_disco(lar, vistas[:1])
    with pytest.raises(InstalacaoRecusadaError):
        ligar("exemplo", permissoes_vistas=vistas, lugares=lar)


def test_o_ligar_liga_com_a_mesma_lista_em_outra_ordem(lar: Lugares, curto: Path) -> None:
    instalar(str(_pasta_do_mod(curto / "fontes")), lugares=lar)
    vistas = list(manifesto_instalado("exemplo", lugares=lar).permissoes)
    entrada = ligar("exemplo", permissoes_vistas=list(reversed(vistas)), lugares=lar)
    assert entrada.ligada and sorted(entrada.permissoes_aceitas) == sorted(vistas)


def test_ligar_sem_dizer_o_que_foi_visto_nao_existe(lar: Lugares, curto: Path) -> None:
    instalar(str(_pasta_do_mod(curto / "fontes")), lugares=lar)
    with pytest.raises(TypeError):
        ligar("exemplo", lugares=lar)  # type: ignore[call-arg]


def test_a_linha_de_comando_liga_com_o_que_mostrou_e_nao_com_o_disco_de_depois(
    lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O código trocado entre o mostrar e o ligar: a CLI passa o que MOSTROU."""
    instalar(str(_pasta_do_mod(curto / "fontes")), lugares=lar)
    mostrado = manifesto_instalado("exemplo", lugares=lar)

    chamadas: list[str] = []

    def mostra_e_troca(mod_id: str, **k: Any) -> Any:
        chamadas.append(mod_id)
        if len(chamadas) > 1:
            return manifesto_instalado(mod_id, **k)  # o disco de agora
        _trocar_o_pedido_no_disco(lar, [*mostrado.permissoes, "rede:internet"])
        return mostrado

    monkeypatch.setattr(cmd_mod, "manifesto_instalado", mostra_e_troca)
    saiu = CliRunner().invoke(cmd_mod.app, ["ligar", "exemplo", "--sim"])

    assert saiu.exit_code == 1, saiu.output
    assert "veja de novo" in saiu.output
    assert not ler_registro(lar.registro)["exemplo"].ligada


# -- 4. o uninstall.sh conhece as modificações -----------------------------------------


def test_o_uninstall_lido_cita_os_tres_lugares_das_modificacoes() -> None:
    texto = UNINSTALL.read_text(encoding="utf-8")
    assert "mods.json" in texto, "o registro"
    assert '_mods_codigo="${_dados_do_xdg}/hefesto-dualsense4unix/mods"' in texto, "o código"
    dados = "${XDG_STATE_HOME:-${HOME}/.local/state}/hefesto-dualsense4unix/mods"
    assert f'_mods_dados="{dados}"' in texto, "os dados"
    assert "mods-estado.json" in texto and "HEFESTO_MOD_ID" in texto, "o processo vivo"


def _quem_vive(mod_id: str, *, com_a_marca: bool) -> subprocess.Popen[bytes]:
    """O processo de mentira da modificação: grupo próprio e o ambiente do supervisor."""
    ambiente = dict(os.environ)
    ambiente.pop("HEFESTO_MOD_ID", None)
    if com_a_marca:
        ambiente["HEFESTO_MOD_ID"] = mod_id
    return subprocess.Popen(
        ["sleep", "120"], env=ambiente, start_new_session=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


@pytest.fixture
def casa(tmp_path: Path) -> Iterator[tuple[Any, Path, list[subprocess.Popen[bytes]]]]:
    r, repo = _casa_de_mentira(tmp_path, xdg_fora=False)
    vivos: list[subprocess.Popen[bytes]] = []
    try:
        yield r, repo, vivos
    finally:
        for p in vivos:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)
            p.wait()


def _instalar_de_mentira(r: Any, vivos: list[subprocess.Popen[bytes]],
                         *, com_a_marca: bool = True) -> dict[str, Path]:
    codigo = r.dados / "hefesto-dualsense4unix/mods/exemplo"
    dados = r.estado / "hefesto-dualsense4unix/mods/exemplo"
    registro = r.config / "hefesto-dualsense4unix/mods.json"
    for pasta in (codigo, dados, registro.parent):
        pasta.mkdir(parents=True, exist_ok=True)
    (codigo / "hefesto-mod.json").write_text("{}", encoding="utf-8")
    (dados / "relato.json").write_text("{}", encoding="utf-8")
    registro.write_text('{"forma": 1, "mods": []}', encoding="utf-8")
    p = _quem_vive("exemplo", com_a_marca=com_a_marca)
    vivos.append(p)
    execucao = r.execucao / "hefesto-dualsense4unix"
    execucao.mkdir(parents=True, exist_ok=True)
    (execucao / "mods-estado.json").write_text(
        json.dumps({"mods": {"exemplo": {"pid": p.pid, "estado": "rodando"}}}),
        encoding="utf-8")
    return {"pasta_do_mod": codigo, "dados": dados, "registro": registro}


def _rodar(casa: Any, tmp_path: Path, flags: str, texto: str | None = None) -> str:
    r, repo, _vivos = casa
    saiu, diario = _desinstalar(
        tmp_path, r, repo, texto if texto is not None else UNINSTALL.read_text(encoding="utf-8"),
        xdg_fora=False, flags=flags)
    assert saiu.returncode == 0, saiu.stdout[-3000:] + saiu.stderr[-3000:]
    assert "RECUSADO" not in diario, diario
    return saiu.stdout


def test_o_uninstall_para_o_processo_vivo_da_modificacao(
    tmp_path: Path, casa: tuple[Any, Path, list[subprocess.Popen[bytes]]]
) -> None:
    _instalar_de_mentira(casa[0], casa[2])
    fora = _rodar(casa, tmp_path, "--yes")
    assert casa[2][0].poll() is not None, "a extensão seguia de pé depois do uninstall"
    assert "parando a extensão exemplo" in fora


def test_a_extensao_que_ignora_o_term_sai_pelo_kill(
    tmp_path: Path, casa: tuple[Any, Path, list[subprocess.Popen[bytes]]]
) -> None:
    """O TERM ignorado não deixa a extensão de pé: depois do prazo, o KILL ao grupo."""
    r, _repo, vivos = casa
    _instalar_de_mentira(r, vivos)
    os.killpg(vivos[0].pid, signal.SIGKILL)
    vivos[0].wait()
    ambiente = {**os.environ, "HEFESTO_MOD_ID": "exemplo"}
    teimosa = subprocess.Popen(
        [sys.executable, "-c",
         "import signal, sys, time\n"
         "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
         "print('pronta', flush=True)\n"
         "time.sleep(120)\n"],
        env=ambiente, start_new_session=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    vivos.append(teimosa)
    assert teimosa.stdout is not None and teimosa.stdout.readline().strip() == b"pronta"
    teimosa.stdout.close()
    estado = r.execucao / "hefesto-dualsense4unix" / "mods-estado.json"
    estado.write_text(
        json.dumps({"mods": {"exemplo": {"pid": teimosa.pid, "estado": "rodando"}}}),
        encoding="utf-8")

    fora = _rodar(casa, tmp_path, "--yes")

    assert teimosa.poll() is not None, "a extensão que ignora o TERM seguia de pé"
    assert teimosa.returncode == -signal.SIGKILL, teimosa.returncode
    assert "a extensão exemplo não parou; mandando o fim" in fora


def test_a_mordida_sem_o_passo_das_modificacoes_o_processo_segue_de_pe(
    tmp_path: Path, casa: tuple[Any, Path, list[subprocess.Popen[bytes]]]
) -> None:
    _instalar_de_mentira(casa[0], casa[2])
    texto = UNINSTALL.read_text(encoding="utf-8")
    assert texto.count("\nparar_as_modificacoes\n") == 1
    _rodar(casa, tmp_path, "--yes", texto.replace("\nparar_as_modificacoes\n", "\n:\n"))
    assert casa[2][0].poll() is None, "arrancada a cura, o processo tinha de seguir vivo"


def test_o_pid_que_nao_e_da_modificacao_nao_recebe_sinal(
    tmp_path: Path, casa: tuple[Any, Path, list[subprocess.Popen[bytes]]]
) -> None:
    """O PID do estado reaproveitado por outro processo: sem o ambiente do usuário, nada."""
    _instalar_de_mentira(casa[0], casa[2], com_a_marca=False)
    fora = _rodar(casa, tmp_path, "--yes")
    assert casa[2][0].poll() is None, "um PID sem o ambiente da modificação foi morto"
    assert "parando a extensão" not in fora


def test_o_ensaio_diz_o_que_faria_e_nao_mata(
    tmp_path: Path, casa: tuple[Any, Path, list[subprocess.Popen[bytes]]]
) -> None:
    _instalar_de_mentira(casa[0], casa[2])
    fora = _rodar(casa, tmp_path, "--dry-run --purge-config")
    assert casa[2][0].poll() is None
    assert f"kill -TERM -- -{casa[2][0].pid}" in fora


def test_por_padrao_o_codigo_os_dados_e_o_registro_ficam_e_o_uninstall_diz(
    tmp_path: Path, casa: tuple[Any, Path, list[subprocess.Popen[bytes]]]
) -> None:
    lugares = _instalar_de_mentira(casa[0], casa[2])
    fora = _rodar(casa, tmp_path, "--yes")
    assert all(p.exists() for p in lugares.values()), lugares
    for lugar in (lugares["pasta_do_mod"].parent, lugares["dados"].parent, lugares["registro"]):
        assert f"as extensões instaladas ficam: {lugar} (apagar de vez: --purge-config)" in fora


def test_com_purge_config_saem_o_codigo_os_dados_e_o_registro_com_backup(
    tmp_path: Path, casa: tuple[Any, Path, list[subprocess.Popen[bytes]]]
) -> None:
    lugares = _instalar_de_mentira(casa[0], casa[2])
    fora = _rodar(casa, tmp_path, "--purge-config --yes")
    assert not any(p.exists() for p in lugares.values()), lugares
    assert "guardando os dados das extensões" in fora
    assert not [x for x in fora.splitlines() if "nenhum passo o nomeia" in x and "/mods " in x]
    backups = list(casa[0].config.glob("hefesto-dualsense4unix.backup-*"))
    assert backups, "o --purge-config sem backup"
    achados = {x.name for b in backups for x in b.rglob("*") if x.is_file()}
    assert {"relato.json", "mods.json", "hefesto-mod.json"} <= achados, achados
