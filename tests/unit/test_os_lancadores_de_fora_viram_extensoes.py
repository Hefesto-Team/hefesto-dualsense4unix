"""Os lançadores além da Steam e do Heroic viram extensões (19/10/2026).

De fábrica ficam a Steam, o Heroic (Epic · GOG) e o Flatpak (D-1910-O-FLATPAK-FICA-DE-FABRICA). O
Lutris, o RetroArch, o Dolphin, o mGBA, o Azahar e o KytyPS5 moram cada um no repositório da sua
extensão, com o leitor dentro dela; o leitor de terceiro nunca roda dentro do serviço (ADR-021). A
extensão de lançador do tipo ``processo`` entrega os jogos pela porta (``lancador.jogos``), e a
aba 07 os pede ao serviço (``mods.jogos``). Quem tinha o lançador no disco lê na fila que ele virou
extensão e o endereço; nada se instala sozinho.

Tudo em lar de mentira: a porta, o registro e o manifesto são de ``tmp``, e o pedido da aba ao
serviço vai direto ao handler do IPC sobre a porta de mentira.

MORDIDAS (executadas aqui, a cada corrida):

- um leitor de fábrica devolvido ao ``src`` (``pga.db``, ``.lpl``, ``def _lutris``) reprova
  :func:`_leitores_de_fora_no_src`;
- o ``lancador.jogos`` tirado da porta deixa a fila sem os jogos;
- a extensão instalada tira a linha da migração.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.protocolo_do_ipc import CODE_METHOD_NOT_FOUND
from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.mods.instalador import Lugares, instalar, ligar
from hefesto_dualsense4unix.mods.porta import Porta, RecusaError
from tests.unit import test_a_porta_entrega_os_jogos_solta_a_vibracao_e_mostra_o_aviso as _p2
from tests.unit import test_as_modificacoes_rodam_fora_do_daemon as _base

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
DE_FABRICA = SRC / "mods" / "de_fabrica"

_ate, _Cliente = _base._ate, _base._Cliente
curto, lar = _base.curto, _base.lar

#: O que denuncia um leitor de lançador de fora dentro do produto. O banco do Lutris, as listas do
#: RetroArch, os arquivos de configuração do Dolphin, do mGBA, do Azahar e do Kyty, e o leitor
#: com o nome do lançador.
_MARCAS_DE_LEITOR = (
    r"pga\.db", r"\.lpl\b", r"\bdef _lutris\b", r"\bdef _retroarch\b", r"\bdef _dolphin\b",
    r"\bdef _mgba\b", r"Dolphin\.ini", r"qt-config\.ini", r"Kyty\.ini", r"\bshadPS4\b",
    r"\bVita3K\b", r"\bRyujinx\b",
)
_MARCA = re.compile("|".join(_MARCAS_DE_LEITOR))


def _leitores_de_fora_no_src(arquivos: dict[str, str]) -> list[str]:
    """``arquivo:linha`` de cada marca de leitor de fora no texto dado."""
    return [f"{nome}:{n}: {linha.strip()[:80]}"
            for nome, texto in arquivos.items()
            for n, linha in enumerate(texto.splitlines(), 1) if _MARCA.search(linha)]


#: O publicado segue o mockup pelo ``--publicar`` do fecho, e não se edita à mão. A janela do Kyty
#: sai com a experimental adulta (O-HEFESTO-E-PARA-TODA-IDADE-E-O-ADULTO-MORA-NA-EXTENSAO-01), e
#: a régua passa a ler o mockup nela.
_FORA_DA_REGUA = ("interface/paginas/", "interface/experimental/kyty.html")


def _o_src() -> dict[str, str]:
    arquivos = [p for p in sorted(SRC.rglob("*")) if p.is_file()
                and p.suffix in {".py", ".json", ".html", ".css", ".js", ".sh"}
                and not any(f in p.as_posix() for f in _FORA_DA_REGUA)]
    return {str(p.relative_to(RAIZ)): p.read_text(encoding="utf-8", errors="replace")
            for p in arquivos}


# -- o que fica de fábrica ---------------------------------------------------------------


def test_de_fabrica_ficam_a_steam_o_heroic_e_o_flatpak() -> None:
    # D-1910-O-FLATPAK-FICA-DE-FABRICA
    # D-1910-OS-LANCADORES-DE-FORA-VIRAM-EXTENSOES
    pastas = sorted(p.name for p in DE_FABRICA.iterdir() if p.is_dir()
                    and (p / "hefesto-mod.json").is_file())
    assert pastas == ["flatpak", "heroic", "steam"], pastas


def test_nenhum_leitor_de_lancador_de_fora_mora_no_src() -> None:
    # D-1910-O-SERVIDOR-DSU-FICA-COMO-PROTOCOLO
    achados = _leitores_de_fora_no_src(_o_src())
    assert achados == [], "\n".join(achados)


def test_a_regua_dos_leitores_morde_o_leitor_devolvido() -> None:
    devolvido = {"integrations/censo_dos_lancadores.py":
                 'def _lutris(lar):\n    banco = lar / "pga.db"\n'}
    assert len(_leitores_de_fora_no_src(devolvido)) == 2
    assert _leitores_de_fora_no_src({"x.py": 'pasta / "playlists" / "a.lpl"'})


def test_o_mapa_de_janela_dos_emuladores_saiu() -> None:
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    assert not hasattr(a07, "_JANELAS_DO_EMULADOR_ACHADO")
    ids = {str(x["id"]) for x in censo._os_que_viraram_extensao()}
    assert {"lutris", "retroarch", "dolphin", "mgba"} <= ids


# -- a migração: uma linha com o endereço ----------------------------------------------------


def test_quem_tinha_o_lutris_le_que_ele_virou_extensao(tmp_path: Path) -> None:
    (tmp_path / ".var/app/net.lutris.Lutris/data").mkdir(parents=True)
    viraram = censo.lancadores_que_viraram_extensao(
        tmp_path, xdg_config=tmp_path / ".config", xdg_data=tmp_path / ".local/share")
    assert [(v.chave, v.endereco) for v in viraram] == [
        ("lutris", "https://github.com/Hefesto-Team/hefesto-mod-lutris")]
    assert viraram[0].proton is True
    vazio = censo.lancadores_que_viraram_extensao(
        tmp_path / "nada", xdg_config=tmp_path / "c", xdg_data=tmp_path / "d")
    assert vazio == (), "sem a pasta dele, a migração não tem a quem falar"


def test_a_linha_da_migracao_entra_na_fila_e_sai_com_a_extensao(
        monkeypatch: pytest.MonkeyPatch) -> None:
    # D-1910-QUEM-TINHA-O-LANCADOR-LE-QUE-ELE-VIROU-EXTENSAO
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    virado = censo.ViradoExtensao("lutris", "Lutris",
                                  "https://github.com/Hefesto-Team/hefesto-mod-lutris")
    monkeypatch.setattr(censo, "lancadores_que_viraram_extensao", lambda *a, **k: (virado,))
    monkeypatch.setattr(a07.REGISTRO, "ler", lambda: ())
    viraram = a07._os_que_viraram_extensao()
    fila = exp.fila_com_novo_html(a07._fila_de([], viraram))
    assert exp.FRASE_DO_QUE_VIROU in fila and virado.endereco in fila
    assert 'data-gesto="instalar' not in fila.split(exp.FRASE_DO_QUE_VIROU)[1].split("</div>")[0]

    def instaladas(*ids: str) -> tuple[Any, ...]:
        return tuple(a07._Instalada(entrada=SimpleNamespace(id=i), manifesto=None) for i in ids)

    monkeypatch.setattr(a07.REGISTRO, "ler", lambda: instaladas("tema"))
    assert [x[0] for x in a07._os_que_viraram_extensao()] == ["lutris"], (
        "outra extensão instalada apagou a linha da migração")
    monkeypatch.setattr(a07.REGISTRO, "ler", lambda: instaladas("tema", "lutris"))
    assert a07._os_que_viraram_extensao() == (), "a extensão instalada e a linha ficou"


# -- os jogos da extensão de lançador chegam à fila da 07 ----------------------------------

JOGOS = [
    {"chave": "meu:1", "nome": "Celeste", "abrir": ["meulancador", "--jogo", "1"]},
    {"chave": "meu:2", "nome": "Hades", "abrir": ["meulancador", "--jogo", "2"]},
]


def _extensao_de_lancador(pasta: Path, lugares: Lugares) -> None:
    """Uma extensão ``processo`` de lançador instalada pela pasta e ligada, no lar de mentira."""
    pasta.mkdir()
    (pasta / "mod.py").write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    (pasta / "hefesto-mod.json").write_text(json.dumps({
        "id": "meu", "nome": "Meu lançador", "api": ">=2,<3", "licenca": "MIT",
        "versao": "0.1",  # noqa-acento: chave do contrato
        "tipos": ["lancador", "processo"], "processo": {"executar": ["python3", "mod.py"]},
        "permissoes": ["lancador"],  # noqa-acento: chave do contrato
        "lancador": {"rotulo": "Meu lançador", "comandos": ["meulancador"]},
    }), encoding="utf-8")
    instalar(str(pasta), lugares=lugares)
    ligar("meu", permissoes_vistas=["lancador"], lugares=lugares)


async def _nada(_metodo: str, _pedido: dict[str, Any]) -> Any:
    return {"status": "ok"}


def _a_fila_com_os_jogos_da_porta(curto: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """A fila que a 07 desenha depois que a extensão entregou os jogos pela porta."""
    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.integrations import jogos_locais as jl
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    monkeypatch.setattr(jl, "pastas_de_atalhos", lambda: [])
    monkeypatch.setattr(a07, "_achados_por_conteudo", lambda: ())
    a07.REGISTRO.esquecer()

    async def corrida() -> str:
        porta = Porta(curto / "mods.sock", EventBus(), escritor=_nada,
                      o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: _p2.P1)
        await porta.iniciar()
        porta.registrar("ficha", "meu", os.getpid(), ["lancador"], comandos=("meulancador",))
        laco = asyncio.get_running_loop()
        servico = _p2._servico(SimpleNamespace(porta=porta))

        def ao_servico(metodo: str, params: dict[str, Any], **_k: Any) -> Any:
            assert metodo == "mods.jogos", metodo
            return asyncio.run_coroutine_threadsafe(
                IpcHandlersMixin._handle_mods_jogos(servico, params), laco).result(5)

        monkeypatch.setattr(ipc_bridge, "_corpo_do_daemon", ao_servico)
        cliente = _Cliente(curto / "mods.sock")
        try:
            await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})
            await asyncio.to_thread(cliente.pedir, "lancador.jogos", {"jogos": JOGOS})
            lida = await asyncio.to_thread(a07._ler_do_disco)
            return str(a07._resposta(lida)["blocos"][".lanc-fila"])
        finally:
            cliente.fechar()
            await porta.parar()

    return asyncio.run(corrida())


def _a_linha(fila: str, chave: str) -> str:
    achada = re.search(rf'<div class="lf[^"]*" data-lancador="{chave}">(.*?)</div>', fila, re.S)
    return achada.group(1) if achada else ""


def test_os_jogos_que_a_extensao_entrega_pela_porta_aparecem_na_fila(
        lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # D-1910-A-EXTENSAO-DE-LANCADOR-VIRA-LINHA-DA-07
    _extensao_de_lancador(curto / "fonte-meu", lar)
    linha = _a_linha(_a_fila_com_os_jogos_da_porta(curto, monkeypatch), "meu")
    assert "Meu lançador" in linha, "a extensão de lançador não virou linha da fila"
    assert "2 jogos" in linha, linha
    assert 'data-gesto="criar-perfil-para-um-jogo"' in linha


def test_sem_o_metodo_da_porta_a_fila_fica_sem_os_jogos(
        lar: Lugares, curto: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A mordida do ``lancador.jogos``: a porta que não o conhece não entrega nada."""
    def desconhecido(self: Porta, _sessao: Any, _params: Any) -> Any:
        raise RecusaError(CODE_METHOD_NOT_FOUND, "método desconhecido: lancador.jogos")

    monkeypatch.setattr(Porta, "_jogos_do_lancador", desconhecido)
    _extensao_de_lancador(curto / "fonte-meu", lar)
    linha = _a_linha(_a_fila_com_os_jogos_da_porta(curto, monkeypatch), "meu")
    assert "2 jogos" not in linha, "a fila contou jogos que a porta não recebeu"


# -- o perfil por jogo do lançador da extensão ------------------------------------------


def test_o_jogo_da_extensao_ligada_e_do_cartao_dela(monkeypatch: pytest.MonkeyPatch) -> None:
    assert censo.lancador_do_jogo("lutris") == ""
    bloco = censo.LancadorDaModificacao(chave="lutris", rotulo="Lutris")
    monkeypatch.setattr(censo, "lancadores_das_extensoes",
                        lambda lugares=None: (censo.LancadorDaExtensao(bloco),))
    assert censo.lancador_do_jogo("lutris") == "lutris"
    assert censo.lancador_do_jogo("steam") == "steam"
    assert {"steam", "heroic", "lutris"} <= censo.lancadores_com_jogos()


def test_o_achado_por_conteudo_nao_duplica_o_que_virou_extensao(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Medido na bancada de 19/10: o Lutris do Flatpak da máquina virava uma segunda linha."""
    # D-1910-QUEM-TINHA-O-LANCADOR-LE-QUE-ELE-VIROU-EXTENSAO
    from hefesto_dualsense4unix.integrations import jogos_locais as jl
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores as a07

    monkeypatch.setattr(jl, "lancadores_por_conteudo", lambda: {
        "net.lutris.Lutris": "Lutris", "org.exemplo.Lancador": "Lançador de exemplo"})
    monkeypatch.setattr(censo, "lancadores_das_extensoes", lambda lugares=None: ())
    assert [s.nome for s in a07._achados_por_conteudo()] == ["Lançador de exemplo"]

    bloco = censo.LancadorDaModificacao(chave="meu", rotulo="Meu",
                                        atalhos=("org.exemplo.Lancador",))
    monkeypatch.setattr(censo, "lancadores_das_extensoes",
                        lambda lugares=None: (censo.LancadorDaExtensao(bloco),))
    assert a07._achados_por_conteudo() == (), "a extensão ligada e o achado repetiu a linha dela"
