"""O-GESTO-DE-GRAVAR-A-OPCAO-DIZ-QUANDO-FALHA-01 — as réguas.

A caixa escreve em ``<dados>/<id>``, e cada gesto de gravar da janela corre pelos dublês de sempre
da extensão de tema. Medido em 07/11/2026: pasta plantada em ``opcoes.json`` e no ``.importado``
recusava os três gestos com ``[Errno 21]``, e o botão só piscava; link e FIFO já se trocavam no
``rename``. O plantio de verdade vai de dentro de um ``bwrap``, no lar de mentira.

MORDIDAS (07/11/2026, executadas sobre a cura e devolvidas):
- sem o desvio da pasta na gravação: ``test_o_gesto_grava_por_cima_do_plantio[pasta]``;
- o desvio da pasta tirado do ``tirar_da_caixa``: ``test_o_tirar_apaga_o_plantado[pasta]``;
- ``shutil.rmtree`` no lugar do ``rename``: ``test_a_pasta_fechada_tambem_sai``;
- ``alvo.unlink()`` sem o ``missing_ok``: ``test_tirar_o_que_ja_nao_existe_nao_e_recusa``;
- o ``unlink`` do arquivo novo tirado: ``test_o_que_nao_grava_diz_e_nao_deixa_resto``;
- sem o ``except OSError`` da gravação: ``test_o_que_nao_grava_diz_e_nao_deixa_resto``;
- sem o ``except OSError`` do ``tirar``: ``test_a_pasta_de_dados_que_nao_e_pasta_diz``;
- sem o ``_dizendo_na_linha`` no ``guardar`` e no ``tirar``: as frases na linha;
- a palavra de sempre na linha do tema: «Não ligou» reprova as frases na linha;
- a linha «Botões» do tema sem a nota: ``test_a_janela_do_tema_diz_a_recusa_na_linha_dos_botoes``;
- o ``mkstemp`` trocado por criar com a máscara da sessão: ``test_o_arquivo_nasce_so_de_quem_usa``.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import stat
import textwrap
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import importados, instalador, opcoes, retrato_do_tema
from hefesto_dualsense4unix.mods.instalador import InstalacaoRecusadaError, Lugares
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit import test_o_diario_da_extensao_mora_fora_da_caixa as diario
from tests.unit import test_o_diario_da_modificacao_tem_teto_enquanto_roda as teto
from tests.unit.test_a_janela_do_tema_importa_e_diz_a_recusa import (  # noqa: F401
    _Ponte,
    a07,
    ctx,
    lg,
)
from tests.unit.test_o_tema_por_escolha_importa_e_personaliza import (
    NOVA,
    _arquivo,
    _ligada,
    _manifesto,
    _pasta,
    _png,
)

curto = teto.curto
lar = teto.lar

_PLANTIOS = ["pasta", "link", "fifo"]
_DA_PESSOA = "da pessoa, fora da caixa\n"


def _plantar(alvo: Path, plantio: str, fora: Path) -> None:
    alvo.parent.mkdir(parents=True, exist_ok=True)
    if plantio == "pasta":
        (alvo / "fundo").mkdir(parents=True)
        (alvo / "fundo" / "miolo").write_text("x", encoding="utf-8")
        (alvo / "para-fora").symlink_to(fora)
    elif plantio == "link":
        alvo.symlink_to(fora)
    else:
        os.mkfifo(alvo)


@pytest.fixture
def fora(tmp_path: Path) -> Path:
    alvo = tmp_path / "da-pessoa.txt"
    alvo.write_text(_DA_PESSOA, encoding="utf-8")
    return alvo


@pytest.fixture
def nova(lg: Lugares, tmp_path: Path) -> Manifesto:  # noqa: F811
    return _ligada(lg, _pasta(tmp_path, _manifesto()))


def _sem_resto(pasta: Path) -> None:
    assert [p.name for p in pasta.iterdir() if p.name.startswith(".")] == []


def _a_opcao(ctx: Any, valor: str = "Claro") -> dict[str, Any]:  # noqa: F811
    return {"v": f"{NOVA}:tema", "evento": "change", "valor": valor}


@pytest.mark.parametrize("plantio", _PLANTIOS)
def test_o_gesto_grava_por_cima_do_plantio(
    a07: Any, ctx: Any, lg: Lugares, nova: Manifesto,  # noqa: F811
    fora: Path, plantio: str,
) -> None:
    alvo = opcoes.caminho(NOVA, lg)
    if alvo.exists():
        alvo.unlink()
    _plantar(alvo, plantio, fora)

    a07.guardar_opcao_da_modificacao(ctx, _a_opcao(ctx), _Ponte(None))

    assert stat.S_ISREG(os.lstat(alvo).st_mode)
    assert opcoes.ler(nova, lg)["tema"] == "Claro"
    assert fora.read_text(encoding="utf-8") == _DA_PESSOA
    _sem_resto(alvo.parent)


@pytest.mark.parametrize("plantio", _PLANTIOS)
def test_o_importar_grava_por_cima_do_plantio(
    a07: Any, ctx: Any, lg: Lugares, nova: Manifesto,  # noqa: F811
    fora: Path, tmp_path: Path, plantio: str,
) -> None:
    alvo = importados.caminho(NOVA, "logo", lg)
    _plantar(alvo, plantio, fora)
    logo = _arquivo(tmp_path, "minha-logo.png", _png())

    a07.importar_na_modificacao(ctx, {"v": f"{NOVA}:logo"}, _Ponte(logo))

    assert alvo.read_bytes() == logo.read_bytes()
    assert opcoes.ler(nova, lg)["logo"] == "minha-logo.png"
    assert fora.read_text(encoding="utf-8") == _DA_PESSOA
    _sem_resto(alvo.parent)


@pytest.mark.parametrize("plantio", _PLANTIOS)
def test_o_tirar_apaga_o_plantado(
    a07: Any, ctx: Any, lg: Lugares, nova: Manifesto,  # noqa: F811
    fora: Path, plantio: str,
) -> None:
    opcoes.guardar(nova, "logo", "minha-logo.png", lg)
    alvo = importados.caminho(NOVA, "logo", lg)
    _plantar(alvo, plantio, fora)

    a07.tirar_da_modificacao(ctx, {"v": f"{NOVA}:logo"}, _Ponte(None))

    assert not os.path.lexists(alvo)
    assert opcoes.ler(nova, lg)["logo"] == ""
    assert fora.read_text(encoding="utf-8") == _DA_PESSOA
    _sem_resto(alvo.parent)


def test_tirar_o_que_ja_nao_existe_nao_e_recusa(
    lg: Lugares, nova: Manifesto,  # noqa: F811
) -> None:
    opcoes.guardar(nova, "logo", "minha-logo.png", lg)
    assert not os.path.lexists(importados.caminho(NOVA, "logo", lg))
    importados.tirar(nova, "logo", lg)
    assert opcoes.ler(nova, lg)["logo"] == ""


def test_a_pasta_fechada_tambem_sai(lg: Lugares, nova: Manifesto, fora: Path) -> None:  # noqa: F811
    alvo = opcoes.caminho(NOVA, lg)
    if alvo.exists():
        alvo.unlink()
    _plantar(alvo, "pasta", fora)
    os.chmod(alvo, 0)
    try:
        opcoes.guardar(nova, "tema", "Claro", lg)
        assert opcoes.ler(nova, lg)["tema"] == "Claro"
    finally:
        for sobra in alvo.parent.glob(".plantado-*"):
            os.chmod(sobra, 0o700)


def test_o_arquivo_nasce_so_de_quem_usa(lg: Lugares, nova: Manifesto) -> None:  # noqa: F811
    antiga = os.umask(0)
    try:
        opcoes.guardar(nova, "tema", "Claro", lg)
    finally:
        os.umask(antiga)
    assert stat.S_IMODE(os.lstat(opcoes.caminho(NOVA, lg)).st_mode) == 0o600


def _sem_escrita(lg: Lugares, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    verdadeiro = os.replace

    def cheio(de: str, para: Any, **mais: Any) -> None:
        if ".gravando-" in str(de):
            raise OSError(28, "Sem espaço no dispositivo")
        verdadeiro(de, para, **mais)

    monkeypatch.setattr(instalador.os, "replace", cheio)


def test_o_que_nao_grava_diz_e_nao_deixa_resto(
    lg: Lugares, nova: Manifesto, monkeypatch: pytest.MonkeyPatch,  # noqa: F811
) -> None:
    _sem_escrita(lg, monkeypatch)
    with pytest.raises(InstalacaoRecusadaError) as recusa:
        opcoes.guardar(nova, "tema", "Claro", lg)
    assert recusa.value.frase == "A opção não foi gravada: Sem espaço no dispositivo."
    _sem_resto(opcoes.caminho(NOVA, lg).parent)


def test_a_janela_diz_na_linha_e_volta_ao_guardado(
    a07: Any, ctx: Any, lg: Lugares, nova: Manifesto,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a07._montar_a_janela_da_extensao(NOVA)
    _sem_escrita(lg, monkeypatch)
    with pytest.raises(RuntimeError, match="não foi gravada"):
        a07.guardar_opcao_da_modificacao(ctx, _a_opcao(ctx), _Ponte(None))
    html = a07._MEXIDA.html_mod
    assert 'data-dica="A opção não foi gravada: Sem espaço no dispositivo."' in html
    assert ">Não gravou</span>" in html and ">Não ligou</span>" not in html
    assert opcoes.ler(nova, lg)["tema"] != "Claro"


def test_a_janela_do_tema_diz_a_recusa_na_linha_dos_botoes(
    a07: Any, ctx: Any, lg: Lugares, nova: Manifesto,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a07._montar_a_janela_da_extensao(NOVA)
    _sem_escrita(lg, monkeypatch)
    botoes = retrato_do_tema.papeis(nova).botoes
    with pytest.raises(RuntimeError, match="não foi gravada"):
        a07.guardar_opcao_da_modificacao(
            ctx, {"v": f"{NOVA}:{botoes}", "evento": "change", "valor": "Direita"}, _Ponte(None))
    linha = a07._MEXIDA.html_mod.split(f'id="mod-op-{botoes}"')[1]
    assert ">Não gravou</span>" in linha.split('id="mod-op-')[0]


def test_o_importar_que_nao_grava_diz_na_linha(
    a07: Any, ctx: Any, lg: Lugares, nova: Manifesto,  # noqa: F811
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    logo = _arquivo(tmp_path, "minha-logo.png", _png())
    _sem_escrita(lg, monkeypatch)
    with pytest.raises(RuntimeError, match="não foi gravado"):
        a07.importar_na_modificacao(ctx, {"v": f"{NOVA}:logo"}, _Ponte(logo))
    assert 'data-dica="O arquivo não foi gravado: Sem espaço no dispositivo."' in (
        a07._MEXIDA.html_mod)


def test_o_tirar_que_nao_apaga_diz_na_linha(
    a07: Any, ctx: Any, lg: Lugares, nova: Manifesto,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opcoes.guardar(nova, "logo", "minha-logo.png", lg)

    def recusa(_alvo: Path) -> None:
        raise PermissionError(13, "Permissão negada")

    monkeypatch.setattr(importados, "tirar_da_caixa", recusa)
    with pytest.raises(RuntimeError, match="não foi apagado"):
        a07.tirar_da_modificacao(ctx, {"v": f"{NOVA}:logo"}, _Ponte(None))
    html = a07._MEXIDA.html_mod
    assert 'data-dica="O arquivo não foi apagado: Permissão negada."' in html
    assert ">Não apagou</span>" in html


def test_a_pasta_de_dados_que_nao_e_pasta_diz(lg: Lugares, nova: Manifesto) -> None:  # noqa: F811
    pasta = lg.dados / NOVA
    shutil.rmtree(pasta, ignore_errors=True)
    pasta.parent.mkdir(parents=True, exist_ok=True)
    pasta.write_text("não é pasta", encoding="utf-8")
    with pytest.raises(InstalacaoRecusadaError, match=r"^A opção não foi gravada: "):
        opcoes.guardar(nova, "tema", "Claro", lg)
    with pytest.raises(InstalacaoRecusadaError, match=r"^O arquivo não foi apagado: "):
        importados.tirar(nova, "logo", lg)


_A_CAIXA_PLANTA = textwrap.dedent('''
    import os, sys
    dados = os.environ["HEFESTO_MOD_DADOS"]
    alvo = os.path.join(dados, "opcoes.json")
    if not os.path.isdir(alvo):
        os.makedirs(os.path.join(alvo, "fundo"))
        open(os.path.join(alvo, "fundo", "miolo"), "w").close()
        os.makedirs(os.path.join(dados, "logo.importado"))
    print("plantei", flush=True)
    sys.exit(3)
''')


def test_o_plantio_de_dentro_do_bwrap_nao_segura_os_gestos(lar: Lugares, curto: Path) -> None:
    exigir_caixa_do_bwrap()
    pasta = curto / "fonte"
    pasta.mkdir()
    corpo = {
        "id": diario._ID, "nome": "Plantador", "versao": "0.1.0",  # (noqa-acento)
        "api": ">=1,<3", "licenca": "MIT", "tipos": ["processo", "tema"],
        "processo": {"executar": ["python3", "mod.py"]},
        "tema": {"logo_pela_opcao": "logo"},
        "permissoes": ["ler:estado", "tema"],  # (noqa-acento)
        "opcoes": [  # (noqa-acento)
            {"id": "faz", "rotulo": "Faz", "tipo": "ligado", "padrao": False},  # (noqa-acento)
            {"id": "logo", "rotulo": "Logo", "tipo": "importar", "formato": "logo"},
        ],
    }
    (pasta / "hefesto-mod.json").write_text(json.dumps(corpo), encoding="utf-8")
    (pasta / "mod.py").write_text(_A_CAIXA_PLANTA, encoding="utf-8")
    instalador.instalar(str(pasta), lugares=lar)
    manifesto = instalador.manifesto_instalado(diario._ID, lugares=lar)
    instalador.ligar(diario._ID, permissoes_vistas=manifesto.permissoes, lugares=lar)

    async def corrida() -> str:
        supervisor = teto._supervisor(lar, bwrap=shutil.which("bwrap"), esperas=(0.05,))
        assert supervisor.bwrap
        await supervisor.iniciar()
        try:
            await teto._ate(
                lambda: getattr(supervisor.estado_de(diario._ID), "estado", "") == "parou")
            estado = supervisor.estado_de(diario._ID)
            assert estado is not None
            return estado.ultima_linha
        finally:
            await supervisor.parar()

    assert diario._em_fio(lambda: asyncio.run(corrida())) == "plantei"
    assert opcoes.caminho(diario._ID, lar).is_dir()
    logo = _arquivo(curto, "minha-logo.png", _png())

    opcoes.guardar(manifesto, "faz", True, lar)
    importados.importar(manifesto, "logo", logo, lar)
    assert opcoes.ler(manifesto, lar) == {"faz": True, "logo": "minha-logo.png"}
    assert importados.caminho(diario._ID, "logo", lar).read_bytes() == logo.read_bytes()

    importados.tirar(manifesto, "logo", lar)
    assert not os.path.lexists(importados.caminho(diario._ID, "logo", lar))
    assert opcoes.ler(manifesto, lar) == {"faz": True, "logo": ""}
