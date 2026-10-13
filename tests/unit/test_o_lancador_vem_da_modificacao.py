"""O lançador que vem da modificação: O-LANCADOR-DO-KYTYPS5-VEM-DA-MODIFICACAO-01.

A modificação ligada que declara o bloco ``lancador`` no ``hefesto-mod.json``
vira cartão pelo MESMO procurador dos de fábrica e do que a pessoa declara; o
leitor da biblioteca dela roda como processo, com prazo, e nunca derruba o
censo; e o perfil de um jogo dela casa pelo ID no título.

Tudo em ``tmp_path``: o registro, o manifesto e o leitor são de mentira, e o
emulador é um script vazio no ``PATH`` desviado.
"""
from __future__ import annotations

import importlib
import json
import re
import shutil
import sys
import time
from pathlib import Path
from types import ModuleType

import pytest

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.interface import desenho_dos_lancadores as desenho
from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.instalador import Lugares

_LEITOR_BOM = (
    "import json\n"
    "print(json.dumps([\n"
    "  {'chave': 'PPSA21567', 'nome': 'Astro Bot', 'caminho': '/jogos/PPSA21567',\n"
    "   'titulo_do_jogo': 'PPSA21567'},\n"
    "  {'chave': 'PPSA01325', 'nome': 'Demon Souls', 'caminho': '/jogos/PPSA01325',\n"
    "   'titulo_do_jogo': 'PPSA01325'},\n"
    "]))\n"
)


@pytest.fixture(scope="module")
def a07() -> ModuleType:
    return importlib.import_module("hefesto_dualsense4unix.interface.pacotes.a07_lancadores")


@pytest.fixture(autouse=True)
def _a_vigia_so_le_quando_a_regua_pede(a07: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a07.VIGIA, "_disparar", lambda: None)


def _bloco(**extra: object) -> dict[str, object]:
    bloco: dict[str, object] = {
        "rotulo": "KytyPS5",
        "comandos": ["kyty_emulator"],
        "janelas": ["kyty_emulator"],
        "titulo_do_jogo": r"\bPPSA\d{5}\b",
        "leitor": {"executar": ["python3", "ler.py"], "prazo_s": 5},
    }
    bloco.update(extra)
    return bloco


def _plantar(tmp_path: Path, *, mod_id: str = "kytyps5", ligada: bool = True,
             aceitas: tuple[str, ...] = ("lancador",), bloco: object = None,
             leitor: str = _LEITOR_BOM) -> Lugares:
    """Uma modificação instalada no lar de mentira, e o registro dela."""
    lg = Lugares(codigo=tmp_path / "codigo", dados=tmp_path / "dados",  # noqa-acento: campo do Lugares
                 registro=tmp_path / "config" / "mods.json",
                 estado=tmp_path / "run" / "mods-estado.json")
    pasta = lg.codigo / mod_id
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "ler.py").write_text(leitor, encoding="utf-8")
    manifesto = {
        "id": mod_id, "nome": "KytyPS5", "versao": "0.1", "api": ">=1,<2",  # noqa-acento: chave do manifesto
        "licenca": "GPL-2.0-only", "tipos": ["lancador"],
        "permissoes": ["lancador"],  # noqa-acento: chave do manifesto
        "lancador": _bloco() if bloco is None else bloco,
    }
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    instalador.gravar_registro(lg.registro, {mod_id: instalador.Entrada(
        id=mod_id, nome="KytyPS5", versao="0.1", origem="local", endereco=str(pasta),
        permissoes_aceitas=list(aceitas), ligada=ligada)})
    return lg


def _emulador_no_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    from hefesto_dualsense4unix.integrations import jogos_locais as jl

    binarios = tmp_path / "bin"
    binarios.mkdir(exist_ok=True)
    emulador = binarios / "kyty_emulator"
    emulador.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    emulador.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binarios}:/usr/bin:/bin")
    monkeypatch.setattr(jl, "pastas_de_atalhos", lambda: [])
    return emulador


def _no_xdg(monkeypatch: pytest.MonkeyPatch, lg: Lugares) -> None:
    monkeypatch.setattr(Lugares, "do_xdg", classmethod(lambda cls: lg))


def _so_as_modificacoes(a07: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """O ``maquina.json`` e os atalhos por conteúdo de fora: só a terceira fonte."""
    from hefesto_dualsense4unix.utils import maquina

    monkeypatch.setattr(maquina, "carregar_maquina", lambda: maquina.MaquinaConfig())
    monkeypatch.setattr(a07, "_achados_por_conteudo", lambda: ())


def test_a_modificacao_ligada_vira_cartao_pelo_mesmo_procurador(
    a07: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """ARRANQUE o ``+ _das_modificacoes()`` de ``_declarados`` e isto reprova."""
    lg = _plantar(tmp_path)
    _no_xdg(monkeypatch, lg)
    _so_as_modificacoes(a07, monkeypatch)
    emulador = _emulador_no_path(monkeypatch, tmp_path)

    declarados = a07._declarados()
    assert [x.chave for x in declarados] == ["kytyps5"], (
        f"a modificação ligada não chegou ao procurador: {declarados}")
    onde = dict(a07._onde_estao_os_lancadores(declarados))
    assert onde["kytyps5"] == str(emulador), onde

    do_disco = desenho.medir_no_disco(tuple(onde.items()), declarados)
    lida = desenho.Leitura(declarados=declarados, onde_estao=tuple(onde.items()),
                           do_disco=do_disco)
    cartoes = {c.chave: c for c in desenho.cartoes(lida)}
    kyty = cartoes["kytyps5"]
    assert kyty.nome == "KytyPS5" and kyty.presente and kyty.selo == "localizado"
    assert kyty.jogos == "2 jogos na biblioteca · 2 instalados", kyty.jogos
    html = desenho.acoes_html(kyty)
    assert desenho.REMOVER_ROTULO not in html, (
        "o cartão da modificação ganhou o «Tirar daqui»: sair é desligá-la")
    assert "odifica" not in kyty.nome + kyty.diz, (
        "o cartão leva marca de modificação, e a escolha dela de 09/10 diz que não")


def test_desligada_ou_sem_a_permissao_o_cartao_some(
    a07: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _so_as_modificacoes(a07, monkeypatch)
    for caso, kwargs in (("desligada", {"ligada": False}),
                         ("sem a permissão aceita", {"aceitas": ()})):
        lg = _plantar(tmp_path / caso.replace(" ", "-"), **kwargs)
        _no_xdg(monkeypatch, lg)
        assert a07._declarados() == (), f"{caso}: o cartão continuou"
        assert "kytyps5" not in [x.chave for x in desenho.procurados(a07._declarados())]


def test_bloco_torto_deixa_so_aquela_de_fora(
    a07: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    _so_as_modificacoes(a07, monkeypatch)
    for bloco in (_bloco(cor="azul"), _bloco(comandos=[], atalhos=[]),
                  _bloco(titulo_do_jogo="(PPSA"),
                  _bloco(leitor={"executar": ["/usr/bin/python3"]}),
                  _bloco(leitor={"executar": ["ler.py"], "prazo_s": 60})):
        lg = _plantar(tmp_path / str(abs(hash(json.dumps(bloco)))), bloco=bloco)
        _no_xdg(monkeypatch, lg)
        assert a07._declarados() == (), f"o bloco torto virou cartão: {bloco}"
    assert [x.chave for x in desenho.procurados(())] == [
        x.chave for x in desenho.EMBUTIDOS], "sem modificação, a lista mudou"


def test_a_modificacao_com_a_chave_de_fabrica_ensina_sem_dar_o_tirar() -> None:
    leitor = censo.LeitorPorProcesso("retroarch", "RetroArch", ("ler.py",), Path("/x"))
    ensino = desenho.SemCenso("retroarch", "Outro nome", ("meu-retro",), (),
                              janelas=("outra.janela",), leitor=leitor,
                              modificacao="retroarch")
    lista = desenho.procurados((ensino,))
    assert [x.chave for x in lista].count("retroarch") == 1
    ra = next(x for x in lista if x.chave == "retroarch")
    assert ra.nome == "RetroArch" and not ra.declarado
    assert "meu-retro" in ra.atalhos and "org.libretro.RetroArch" in ra.atalhos
    assert ra.janelas == ("com.libretro.RetroArch", "outra.janela")


def test_as_janelas_medidas_sao_a_fabrica_mais_as_da_modificacao(
    a07: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """O RetroArch segue com a janela de fábrica; o KytyPS5 traz a dele."""
    lg = _plantar(tmp_path)
    _no_xdg(monkeypatch, lg)
    _so_as_modificacoes(a07, monkeypatch)
    a07._ESCOLHA.limpar()
    a07._ESCOLHA.modo = desenho.EXCLUIR
    jogos, janelas, emulador = a07._jogos_para_escolher("retroarch", "RetroArch", None)
    assert emulador and "com.libretro.RetroArch" in janelas[jogos[0].chave]
    jogos, janelas, emulador = a07._jogos_para_escolher("kytyps5", "KytyPS5", None)
    assert emulador and jogos[0].chave == "emulador:kytyps5", (
        "na exclusão, o KytyPS5 fica na linha «todos os jogos»: a lista casa por janela")
    assert "kyty_emulator" in janelas["emulador:kytyps5"]
    assert not hasattr(a07, "_JANELAS_MEDIDAS"), "o dicionário cravado voltou"


def _leitor(
    tmp_path: Path, corpo: str, prazo: float = 5.0, molde: str = "",
) -> censo.LeitorPorProcesso:
    pasta = tmp_path / "leitor"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "ler.py").write_text(corpo, encoding="utf-8")
    return censo.LeitorPorProcesso("kytyps5", "KytyPS5", (sys.executable, "ler.py"),
                                   pasta, prazo, molde)


@pytest.mark.parametrize(("corpo", "motivo"), [
    ("import time\ntime.sleep(30)\n", "passou de"),
    ("print('{nada')\n", "JSON"),
    ("print('{}')\n", "lista"),
    ("import sys\nsys.exit(3)\n", "código 3"),
    ("import sys\nsys.stdout.write('[' + ' ' * (2 << 20) + ']')\n", "cabe"),
])
def test_o_leitor_torto_nao_derruba_o_censo(tmp_path: Path, corpo: str, motivo: str) -> None:
    leitor = _leitor(tmp_path, corpo, prazo=0.8)
    antes = time.monotonic()
    biblioteca = censo.ler_por_processo(leitor, bwrap=False)
    assert time.monotonic() - antes < 4.0, "o prazo não segurou o leitor"
    assert biblioteca.estado == censo.ILEGIVEL, biblioteca
    assert motivo in biblioteca.erros[0], biblioteca.erros
    assert biblioteca.resumo.startswith("A biblioteca está aqui e não pôde ser lida")


def test_o_leitor_que_passa_do_prazo_nao_derruba_o_cartao(
    a07: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A pintura segue com os outros cartões, e o do KytyPS5 diz o motivo."""
    lg = _plantar(tmp_path, bloco=_bloco(leitor={"executar": ["python3", "ler.py"],
                                                  "prazo_s": 0.5}),
                  leitor="import time\ntime.sleep(30)\n")
    _no_xdg(monkeypatch, lg)
    _so_as_modificacoes(a07, monkeypatch)
    _emulador_no_path(monkeypatch, tmp_path)
    declarados = a07._declarados()
    onde = a07._onde_estao_os_lancadores(declarados)
    do_disco = desenho.medir_no_disco(onde, declarados)
    assert "passou de 0.5 s" in do_disco.resumo("kytyps5"), do_disco.resumos


def test_a_linha_torta_sai_sozinha_e_o_titulo_fora_da_forma_tambem(tmp_path: Path) -> None:
    corpo = (
        "import json\nprint(json.dumps([\n"
        " {'chave': 'PPSA21567', 'nome': 'Astro Bot', 'titulo_do_jogo': 'PPSA21567'},\n"
        " {'chave': '../fora', 'nome': 'X'},\n"
        " {'chave': 'CUSA00001', 'nome': 'Fora da forma', 'titulo_do_jogo': 'CUSA00001'},\n"
        " 'texto solto',\n"
        "]))\n")
    biblioteca = censo.ler_por_processo(
        _leitor(tmp_path, corpo, molde=r"\bPPSA\d{5}\b"), bwrap=False)
    assert biblioteca.estado == censo.LIDO
    assert [(j.chave, j.titulo_do_jogo) for j in biblioteca.jogos] == [
        ("PPSA21567", "PPSA21567"), ("CUSA00001", "")]


def test_na_caixa_o_leitor_le_a_casa_e_nao_escreve_nem_ve_a_sessao(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        pytest.skip("sem bwrap nesta máquina: a caixa não existe para provar")
    xdg_run = tmp_path / "xdg_run"
    xdg_run.mkdir()
    (xdg_run / "bus").write_text("", encoding="utf-8")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(xdg_run))
    corpo = (
        "import json, os\n"
        "try:\n"
        "    open('escrito', 'w').close(); escreveu = 'sim'\n"
        "except OSError:\n"
        "    escreveu = 'não'\n"
        f"ve = 'sim' if os.listdir({str(xdg_run)!r}) else 'não'\n"
        "print(json.dumps([{'chave': 'A', 'nome': 'escreveu-' + escreveu},\n"
        "                  {'chave': 'B', 'nome': 've-a-sessao-' + ve}]))\n")
    leitor = _leitor(tmp_path, corpo)
    biblioteca = censo.ler_por_processo(leitor, bwrap=bwrap)
    assert biblioteca.estado == censo.LIDO, biblioteca.erros
    assert [j.nome for j in biblioteca.jogos] == ["escreveu-não", "ve-a-sessao-não"]
    assert not (leitor.pasta / "escrito").exists()


def test_o_perfil_do_jogo_casa_pelo_id_no_titulo(
    a07: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """ARRANQUE o ramo do título em ``confirmar_o_perfil`` e isto reprova."""
    from hefesto_dualsense4unix.profiles.schema import MatchCriteria

    lg = _plantar(tmp_path)
    _no_xdg(monkeypatch, lg)
    _so_as_modificacoes(a07, monkeypatch)
    a10 = importlib.import_module(f"{a07.__package__}.a10_perfis")
    nascidos: list[tuple[MatchCriteria, str]] = []

    def _nascer(ctx: object, p: object, regra: MatchCriteria, base: str) -> str:
        nascidos.append((regra, base))
        return "ok"

    monkeypatch.setattr(a10, "_nascer", _nascer)
    monkeypatch.setattr(a10, "criar_para_o_jogo",
                        lambda *a, **k: pytest.fail("o jogo do KytyPS5 nasceu por classe"))

    a07._abrir_a_escolha(desenho.CRIAR_PERFIL, "kytyps5", None)
    assert [j.chave for j in a07._ESCOLHA.jogos] == ["PPSA21567", "PPSA01325"]

    class _Ctx:
        state: dict[str, object] | None = None

    a07.confirmar_o_perfil(_Ctx(), {"forma": {desenho.ESCOLHA: "PPSA21567"}}, None)
    [(regra, base)] = nascidos
    assert base == "Astro Bot"
    assert regra.window_class == [] and regra.process_name == []
    for titulo in ("KytyPS5 | PPSA21567 | Astro Bot | 58 fps",
                   "PPSA21567 - 61 fps"):
        assert regra.matches({"wm_class": "kyty_emulator", "wm_name": titulo}), titulo
    for titulo in ("KytyPS5 | PPSA215670 | 60 fps", "KytyPS5 | PPSA01325 | 60 fps"):
        assert not regra.matches({"wm_class": "kyty_emulator", "wm_name": titulo}), titulo
    assert re.search(regra.window_title_regex or "", "xPPSA21567") is None
