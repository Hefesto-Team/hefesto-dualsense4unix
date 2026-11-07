"""O que a caixa escreve se lê sem confiar (O-QUE-A-CAIXA-ESCREVE-SE-LE-SEM-CONFIAR-01).

Medido em 07/11/2026: a caixa monta ``<dados>/<id>`` com escrita, e a janela lia dali sem confiar
só no nome. FIFO em ``opcoes.json`` travou o leitor (rc=137 no teto de 6 s), 3 GiB esparsos também;
link em ``meu.css`` ou na cópia importada entregou arquivo de fora; a corrida entre arquivo comum e
FIFO travou o retrato do tema; o ``meu.css`` gigante da substituída se copiou até o ``ENOSPC``; e
JSON ou CSS fundo demais levantou ``RecursionError`` na janela. Tudo em lar de mentira.

MORDIDAS (07/11/2026, executadas sobre a cura e devolvidas):
- sem ``O_NONBLOCK`` no abridor: ``test_o_plantio_nao_alcanca_o_leitor[*-fifo]``;
- sem ``O_NOFOLLOW``: ``test_o_plantio_nao_alcanca_o_leitor[*-link]``;
- sem o ``fstat`` que recusa o não regular: ``test_o_plantio_nao_alcanca_o_leitor[*-pasta]``;
- sem o teto: ``test_o_plantio_nao_alcanca_o_leitor[*-gigante]``;
- cada leitor de volta à leitura direta: o seu ``test_o_plantio_nao_alcanca_o_leitor[leitor-link]``;
- sem o ``RecursionError`` no ``_guardados``: ``test_o_json_hostil_nao_levanta``;
- sem o ``FUNDO_MAXIMO``: ``test_o_css_fundo_demais_se_recusa_nas_duas_portas``;
- sem descontar a saída do fundo: ``test_regras_lado_a_lado_nao_contam_como_fundo``;
- sem o conjunto das recusas ditas: ``test_a_recusa_vai_ao_registro_uma_vez_por_motivo``;
- o ``open(..., "xb")`` de volta a ``write_bytes``: ``test_o_destino_com_link_nao_recebe_o_css``;
- sem o ``RecursionError`` no ``herdar``: ``test_a_troca_herda_mesmo_com_json_fundo_na_nova``;
- sem o ``ENXIO``: ``test_o_plantio_nao_alcanca_o_leitor[*-socket]``;
- ``NAO_ABRIU`` trocado por ``NAO_E_COMUM``: ``[*-sem-permissao]``;
- o teto em ``>=``: ``test_no_teto_exato_ainda_se_le``;
- sem o ``UnicodeDecodeError`` no retrato: ``test_o_que_nao_e_texto_vale_o_padrao[retrato]``.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import stat
import sys
import textwrap
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import (
    importados,
    instalador,
    leitura_da_caixa,
    meu_css,
    opcoes,
    tema,
)
from hefesto_dualsense4unix.mods import retrato_do_tema as rt
from hefesto_dualsense4unix.mods import supervisor as supervisor_mod
from hefesto_dualsense4unix.mods.instalador import Lugares
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit import test_o_diario_da_extensao_mora_fora_da_caixa as diario
from tests.unit import test_o_diario_da_modificacao_tem_teto_enquanto_roda as teto
from tests.unit.test_o_tema_por_escolha_importa_e_personaliza import (
    NOVA,
    _ligada,
    _manifesto,
    _pasta,
    _png,
)

curto = teto.curto
lar = teto.lar

_ID = "tema-x"
_OUTRA = "tema-y"
_TETO_S = 5.0
_COR = '{"cor": "#123456"}'
_CSS = ".a{color:red}\n"
_TEMA = ":root{--green:#123456}"
_GIGANTE = 3 << 30
_BASE: dict[str, Any] = {
    "id": _ID, "nome": "T", "api": ">=2,<3", "licenca": "MIT",
    "versao": "1.0.0",  # (noqa-acento)
    "tipos": ["tema"], "tema": {"arquivo": "tema.css"},
    "permissoes": ["tema"],  # (noqa-acento)
}
_MANIFESTO = Manifesto.model_validate({**_BASE, "opcoes": [  # (noqa-acento)
    {"id": "cor", "rotulo": "Cor", "tipo": "cor", "padrao": "#ffffff"}]})  # (noqa-acento)
_COM_CSS = Manifesto.model_validate({**_BASE, "id": _OUTRA, "opcoes": [  # (noqa-acento)
    {"id": "css", "rotulo": "CSS", "tipo": "css", "padrao": False}]})  # (noqa-acento)


def _lido_pelo_levar(lg: Lugares) -> str:
    instalador._levar_o_meu_css(lg, _COM_CSS, [_ID])
    destino = meu_css.caminho(_OUTRA, lg)
    return destino.read_text(encoding="utf-8") if destino.exists() else ""


_LEITORES: dict[str, tuple[str, bytes, Callable[[Lugares], Any], Any]] = {
    "opcoes": ("opcoes.json",  # (noqa-acento)
               _COR.encode(), lambda lg: opcoes.ler(_MANIFESTO, lg)["cor"],
               "#ffffff"),
    "meu_css": ("meu.css", _CSS.encode(), lambda lg: meu_css.ler(_ID, lg).folha, ""),
    "tema": ("t.importado", _TEMA.encode(), lambda lg: importados.ler_o_tema(_ID, "t", lg), ""),
    "logo": ("l.importado", _png(), lambda lg: importados.css_da_logo(_ID, "l", lg), ""),
    "retrato": ("meu.css", _CSS.encode(), lambda lg: rt._primeiras_linhas(_ID, lg), ()),
    "levar": ("meu.css", _CSS.encode(), _lido_pelo_levar, ""),
}
_TETOS = {"opcoes.json": opcoes.TETO_DO_ARQUIVO, "meu.css": meu_css.TAMANHO_MAXIMO,
          "t.importado": tema.TAMANHO_MAXIMO, "l.importado": importados.TAMANHO_DA_LOGO}


class _Registro:
    def __init__(self) -> None:
        self.motivos: list[str] = []

    def warning(self, _evento: str, **campos: Any) -> None:
        self.motivos.append(campos["motivo"])


@pytest.fixture
def registro(monkeypatch: pytest.MonkeyPatch) -> _Registro:
    falso = _Registro()
    monkeypatch.setattr(leitura_da_caixa, "logger", falso)
    monkeypatch.setattr(leitura_da_caixa, "_ditas", set())
    return falso


@pytest.fixture
def lg(tmp_path: Path) -> Lugares:
    lugares = Lugares(codigo=tmp_path / "codigo",  # (noqa-acento)
                      dados=tmp_path / "dados",
                      registro=tmp_path / "mods.json", estado=tmp_path / "estado.json")
    (lugares.dados / _ID).mkdir(parents=True)
    return lugares


def _plantar(alvo: Path, plantio: str, corpo: bytes) -> str:
    """Planta ``plantio`` em ``alvo`` e devolve o motivo que o registro tem de dizer."""
    if plantio == "fifo":
        os.mkfifo(alvo)
        return leitura_da_caixa.NAO_E_COMUM
    if plantio == "pasta":
        alvo.mkdir()
        return leitura_da_caixa.NAO_E_COMUM
    if plantio == "socket":
        with socket.socket(socket.AF_UNIX) as ponta:
            ponta.bind(str(alvo))
        return leitura_da_caixa.NAO_E_COMUM
    if plantio == "sem-permissao":
        alvo.write_bytes(corpo)
        alvo.chmod(0)
        return leitura_da_caixa.NAO_ABRIU
    if plantio == "link":
        fora = alvo.parent.parent.parent / "da-pessoa"
        fora.write_bytes(corpo)
        alvo.symlink_to(fora)
        return leitura_da_caixa.NAO_E_COMUM
    if plantio == "gigante":
        alvo.write_bytes(corpo)
        with alvo.open("ab") as arquivo:
            arquivo.write(b" " * (_TETOS[alvo.name] + 1))
        return leitura_da_caixa.GRANDE_DEMAIS
    with alvo.open("wb") as arquivo:
        arquivo.truncate(_GIGANTE)
    return leitura_da_caixa.GRANDE_DEMAIS


@pytest.mark.parametrize(
    "plantio", ["fifo", "link", "pasta", "socket", "sem-permissao", "gigante", "esparso"])
@pytest.mark.parametrize("leitor", list(_LEITORES))
def test_o_plantio_nao_alcanca_o_leitor(
    lg: Lugares, registro: _Registro, leitor: str, plantio: str,
) -> None:
    nome, corpo, ler, esperado = _LEITORES[leitor]
    motivo = _plantar(lg.dados / _ID / nome, plantio, corpo)

    assert diario._em_fio(lambda: ler(lg), _TETO_S) == esperado
    assert registro.motivos == [motivo]


@pytest.mark.parametrize("leitor", list(_LEITORES))
def test_o_arquivo_comum_chega_ao_leitor(lg: Lugares, registro: _Registro, leitor: str) -> None:
    nome, corpo, ler, esperado = _LEITORES[leitor]
    (lg.dados / _ID / nome).write_bytes(corpo)

    assert ler(lg) != esperado
    assert registro.motivos == []


@pytest.mark.parametrize("nome", list(_TETOS))
def test_no_teto_exato_ainda_se_le(lg: Lugares, registro: _Registro, nome: str) -> None:
    alvo = lg.dados / _ID / nome
    alvo.write_bytes(b" " * _TETOS[nome])

    assert leitura_da_caixa.ler_da_caixa(alvo, _TETOS[nome]) == alvo.read_bytes()
    assert registro.motivos == []


@pytest.mark.parametrize("leitor", [n for n in _LEITORES if n not in ("levar", "logo")])
def test_o_que_nao_e_texto_vale_o_padrao(lg: Lugares, leitor: str) -> None:
    nome, _corpo, ler, esperado = _LEITORES[leitor]
    (lg.dados / _ID / nome).write_bytes(b"\xff\xfe")

    assert ler(lg) == esperado


@pytest.mark.parametrize("leitor", list(_LEITORES))
def test_sem_arquivo_o_registro_cala(
    lg: Lugares, registro: _Registro, leitor: str,
) -> None:
    _nome, _corpo, ler, esperado = _LEITORES[leitor]

    assert ler(lg) == esperado
    assert registro.motivos == []


@pytest.mark.parametrize("leitor", list(_LEITORES))
def test_a_troca_entre_arquivo_e_fifo_nao_trava(lg: Lugares, leitor: str) -> None:
    """A corrida que travou o retrato: entre a conferência e o ``open`` o arquivo vira FIFO."""
    nome, corpo, ler, _esperado = _LEITORES[leitor]
    pasta = lg.dados / _ID
    alvo = pasta / nome
    alvo.write_bytes(corpo)
    parar = threading.Event()

    def trocar() -> None:
        comum, fila = pasta / ".comum", pasta / ".fila"
        while not parar.is_set():
            comum.write_bytes(corpo)
            os.replace(comum, alvo)
            os.mkfifo(fila)
            os.replace(fila, alvo)

    def ler_varias() -> None:
        fim = time.monotonic() + 0.4
        while time.monotonic() < fim:
            ler(lg)
            meu_css.caminho(_OUTRA, lg).unlink(missing_ok=True)

    fio = threading.Thread(target=trocar, daemon=True)
    fio.start()
    try:
        diario._em_fio(ler_varias, _TETO_S)
    finally:
        parar.set()
        fio.join(_TETO_S)


@pytest.mark.parametrize("texto", [
    "[" * 100_000, "1" * 5_000, '{"cor":' + "[" * 100_000, "[1, 2]", "isto não é json",
], ids=["fundo", "inteiro", "fundo-no-valor", "lista", "texto"])
def test_o_json_hostil_nao_levanta(lg: Lugares, registro: _Registro, texto: str) -> None:
    opcoes.caminho(_ID, lg).write_text(texto, encoding="utf-8")

    assert opcoes.ler(_MANIFESTO, lg) == {"cor": "#ffffff"}
    assert registro.motivos == ["nao_e_um_objeto"]


def test_a_troca_herda_mesmo_com_json_fundo_na_nova(lg: Lugares) -> None:
    """O ``herdar`` regrava o que a nova guardou, e o ``dump`` não aceita o fundo do ``loads``."""
    opcoes.caminho(_OUTRA, lg).parent.mkdir()
    opcoes.caminho(_ID, lg).write_text('{"cor": "#00ff00"}', encoding="utf-8")
    fundo = '{"sobra":' + "[" * 2_000 + "]" * 2_000 + "}"
    nova = Manifesto.model_validate({**_MANIFESTO.model_dump(mode="json"), "id": _OUTRA})
    opcoes.caminho(_OUTRA, lg).write_text(fundo, encoding="utf-8")

    assert opcoes.herdar(nova, [_ID], lg) == {"cor": "#00ff00"}
    assert opcoes.ler(nova, lg)["cor"] == "#00ff00"


def test_o_css_fundo_demais_se_recusa_nas_duas_portas(lg: Lugares, tmp_path: Path) -> None:
    metade = meu_css.TAMANHO_MAXIMO // 4
    fundo = "a{" * metade + "}" * metade
    meu_css.caminho(_ID, lg).write_text(fundo, encoding="utf-8")

    recusa = meu_css.ler(_ID, lg)
    assert recusa.folha == "" and recusa.recusa_curta == "Linha 1: chaves demais"
    escolhido = tmp_path / "escolhido.css"
    escolhido.write_text(fundo, encoding="utf-8")
    with pytest.raises(instalador.InstalacaoRecusadaError, match="chaves demais"):
        importados.importar(_COM_CSS, "css", escolhido, lg)


def test_o_css_no_fundo_que_a_pessoa_usa_ainda_vale() -> None:
    fundos = meu_css.FUNDO_MAXIMO - 2
    folha = meu_css.aplicar("@media x{" * fundos + ".a{color:red}" + "}" * fundos)
    assert "color:red !important" in folha


def test_regras_lado_a_lado_nao_contam_como_fundo() -> None:
    assert meu_css.aplicar(".a{color:red}\n" * 100).count("!important") == 100


def test_a_recusa_vai_ao_registro_uma_vez_por_motivo(lg: Lugares, registro: _Registro) -> None:
    alvo = meu_css.caminho(_ID, lg)
    os.mkfifo(alvo)
    for _ in range(3):
        meu_css.ler(_ID, lg)
    assert registro.motivos == [leitura_da_caixa.NAO_E_COMUM]
    alvo.unlink()
    alvo.write_bytes(b" " * (meu_css.TAMANHO_MAXIMO + 1))
    for _ in range(3):
        meu_css.ler(_ID, lg)
    assert registro.motivos == [leitura_da_caixa.NAO_E_COMUM, leitura_da_caixa.GRANDE_DEMAIS]


@pytest.mark.parametrize(("plantio", "curta", "frase"), [
    ("fifo", "Não é arquivo comum", "arquivo comum"),
    ("link", "Não é arquivo comum", "arquivo comum"),
    ("gigante", "Passa de 16 KB", "16 KB"),
])
def test_a_aba_diz_a_recusa_do_css(lg: Lugares, plantio: str, curta: str, frase: str) -> None:
    _plantar(meu_css.caminho(_ID, lg), plantio, _CSS.encode())

    lida = meu_css.ler(_ID, lg)
    assert lida.recusa_curta == curta and frase in lida.recusa


@pytest.mark.parametrize("plantio", ["fifo", "link"])
def test_escolher_uma_opcao_troca_o_plantio_e_nao_o_alvo(
    lg: Lugares, tmp_path: Path, plantio: str,
) -> None:
    alvo = opcoes.caminho(_ID, lg)
    _plantar(alvo, plantio, _COR.encode())

    opcoes.guardar(_MANIFESTO, "cor", "#00ff00", lg)

    assert stat.S_ISREG(os.lstat(alvo).st_mode)
    assert opcoes.ler(_MANIFESTO, lg)["cor"] == "#00ff00"
    if plantio == "link":
        assert (tmp_path / "da-pessoa").read_text(encoding="utf-8") == _COR


def test_o_destino_com_link_nao_recebe_o_css(lg: Lugares, tmp_path: Path) -> None:
    meu_css.caminho(_ID, lg).write_text(_CSS, encoding="utf-8")
    destino = meu_css.caminho(_OUTRA, lg)
    destino.parent.mkdir()
    fora = tmp_path / "ainda-nao-existe"
    destino.symlink_to(fora)

    instalador._levar_o_meu_css(lg, _COM_CSS, [_ID])

    assert not fora.exists()


def test_o_arquivo_escolhido_pode_ser_um_link(lg: Lugares, tmp_path: Path) -> None:
    real = tmp_path / "meu-tema.css"
    real.write_text(_CSS, encoding="utf-8")
    atalho = tmp_path / "atalho.css"
    atalho.symlink_to(real)

    assert importados.importar(_COM_CSS, "css", atalho, lg) == "atalho.css"
    assert meu_css.caminho(_OUTRA, lg).read_text(encoding="utf-8") == _CSS


def test_o_abridor_e_um_so() -> None:
    assert supervisor_mod.abrir_sem_seguir is leitura_da_caixa.abrir_sem_seguir
    pasta = Path(leitura_da_caixa.__file__).parent
    com_abridor = [p.name for p in pasta.glob("*.py") if "O_NOFOLLOW" in p.read_text("utf-8")]
    assert com_abridor == ["leitura_da_caixa.py"]


_A_CAIXA_PLANTA = textwrap.dedent('''
    import os, sys
    dados = os.environ["HEFESTO_MOD_DADOS"]
    alvo = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "plantio")).read()
    for nome in ("opcoes.json", "meu.css", "t.importado", "l.importado"):
        if os.path.lexists(os.path.join(dados, nome)):
            os.unlink(os.path.join(dados, nome))
    os.mkfifo(os.path.join(dados, "opcoes.json"))
    os.symlink(alvo, os.path.join(dados, "meu.css"))
    with open(os.path.join(dados, "t.importado"), "wb") as arquivo:
        arquivo.truncate(3 << 30)
    os.mkfifo(os.path.join(dados, "l.importado"))
    print("plantei", flush=True)
    sys.exit(3)
''')


def test_o_plantio_de_dentro_do_bwrap_nao_alcanca_a_janela(
    lar: Lugares, curto: Path, registro: _Registro,
) -> None:
    exigir_caixa_do_bwrap()
    fora = curto / "casa" / "da-pessoa.css"
    fora.write_text(_CSS, encoding="utf-8")
    diario._instalar(lar, curto, _A_CAIXA_PLANTA, str(fora))
    mod_id = diario._ID

    async def corrida() -> str:
        supervisor = teto._supervisor(lar, bwrap=shutil.which("bwrap"), esperas=(0.05,))
        assert supervisor.bwrap
        await supervisor.iniciar()
        try:
            await teto._ate(
                lambda: getattr(supervisor.estado_de(mod_id), "estado", "") == "parou")
            estado = supervisor.estado_de(mod_id)
            assert estado is not None
            return estado.ultima_linha
        finally:
            await supervisor.parar()

    assert diario._em_fio(lambda: asyncio.run(corrida())) == "plantei"
    dados = lar.dados / mod_id
    assert stat.S_ISFIFO(os.lstat(dados / "opcoes.json").st_mode)
    assert stat.S_ISLNK(os.lstat(dados / "meu.css").st_mode)
    assert (dados / "t.importado").stat().st_size == 3 << 30

    def ler_tudo() -> tuple[Any, ...]:
        manifesto = instalador.manifesto_instalado(mod_id, lugares=lar)
        return (opcoes.ler(manifesto, lar), meu_css.ler(mod_id, lar).folha,
                importados.ler_o_tema(mod_id, "t", lar),
                importados.css_da_logo(mod_id, "l", lar), rt._primeiras_linhas(mod_id, lar))

    assert diario._em_fio(ler_tudo, _TETO_S) == ({}, "", "", "", ())
    assert fora.read_text(encoding="utf-8") == _CSS
    assert sorted(set(registro.motivos)) == [leitura_da_caixa.GRANDE_DEMAIS,
                                             leitura_da_caixa.NAO_E_COMUM]


def test_o_tema_da_casa_nao_trava(lg: Lugares) -> None:
    pasta = lg.codigo / _ID
    pasta.mkdir(parents=True)
    (pasta / "tema.css").write_text(_TEMA, encoding="utf-8")
    bloco = {**_BASE, "opcoes": [  # (noqa-acento)
        {"id": "css", "rotulo": "CSS", "tipo": "css", "padrao": False}]}  # (noqa-acento)
    (pasta / "hefesto-mod.json").write_text(json.dumps(bloco), encoding="utf-8")
    registro = instalador.ler_registro(lg.registro)
    registro[_ID] = instalador.Entrada(
        id=_ID, nome="T", versao="1.0.0", origem="local", endereco=str(pasta),
        permissoes_aceitas=["tema"], ligada=True, ligada_em="2026-11-07T10:00:00")
    instalador.gravar_registro(lg.registro, registro)
    os.mkfifo(opcoes.caminho(_ID, lg))
    os.mkfifo(meu_css.caminho(_ID, lg))

    casa = diario._em_fio(lambda: tema.tema_da_casa(lg), _TETO_S)

    assert casa.css == ""


def test_a_janela_da_extensao_abre_igual_com_o_plantio(
    lg: Lugares, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A porta que travou na medida: a janela de opções monta o mesmo HTML que sem plantio."""
    sys.path.insert(0, str(Path(tema.__file__).parents[1] / "interface"))
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    monkeypatch.setattr(Lugares, "do_xdg", classmethod(lambda cls: lg))
    monkeypatch.setattr(a07.VIGIA, "_disparar", lambda: None)
    a07.REGISTRO.esquecer()
    a07._MEXIDA.limpar()
    _ligada(lg, _pasta(tmp_path, _manifesto()))

    a07._montar_a_janela_da_extensao(NOVA)
    limpa = a07._MEXIDA.html_mod
    pasta = lg.dados / NOVA
    pasta.mkdir(exist_ok=True)
    os.mkfifo(opcoes.caminho(NOVA, lg))
    _plantar(meu_css.caminho(NOVA, lg), "link", _CSS.encode())
    _plantar(importados.caminho(NOVA, "logo", lg), "esparso", b"")

    diario._em_fio(lambda: a07._montar_a_janela_da_extensao(NOVA), _TETO_S)

    assert limpa and a07._MEXIDA.html_mod == limpa
