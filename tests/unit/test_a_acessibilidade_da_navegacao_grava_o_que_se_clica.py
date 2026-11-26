"""A janela Acessibilidade da Navegação grava o que se clica.

A-ACESSIBILIDADE-DA-NAVEGACAO-GRAVA-O-QUE-SE-CLICA-01. A janela nasceu apagada (18 `inert`, 28
`disabled`, nenhum gesto) com o motor e o IPC prontos. Agora cada linha que tem motor leva
`data-gesto`; o clique mexe num rascunho que a tela pinta, e o «Guardar» manda o que mudou ao
`perfil.ativacao.set`, ao `perfil.analogicos.set` e, para o giroscópio, ao `mira.set`. Só a linha
«Trocar de lado com», que nenhum motor atende, segue apagada, com a dica.

Estas provas usam o servidor do produto de verdade (o `IpcServer` com o `ProfileManager`), num
diretório de perfis isolado: o que o gesto grava é lido de volta do disco.

MORDIDAS (rodadas e relatadas na entrega): arrancar um `data-gesto` do gerador, tirar o `grava`
do «Guardar» do gesto, o «Guardar» que manda o campo errado e o gesto que grava antes do
«Guardar» reprovam.
"""

from __future__ import annotations

import asyncio
import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup" / "06-navegacao.html"
_P1, _P2 = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02")
_CHAVE_DO_P2 = _P2.replace(":", "")
PAGINA = "06-navegacao.html"


def _janela() -> str:
    bruto = MOCKUP.read_text(encoding="utf-8")
    sem = re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", bruto, flags=re.S)
    inicio = sem.index('id="acessibilidade"')
    return sem[inicio:sem.index("</body>", inicio)]


def _pacotes() -> Any:
    import hefesto_dualsense4unix

    interface = str(pathlib.Path(hefesto_dualsense4unix.__file__).parent / "interface")
    if interface not in sys.path:
        sys.path.insert(0, interface)
    import pacotes
    import pacotes.a06_navegacao as a06

    a06._AC_RASCUNHO.clear()
    a06._AC_ESCOPO["todo_perfil"] = True
    return pacotes, a06


class _Ponte:
    """A ponte do gesto sobre o servidor do produto: cada `resultado` chega ao handler real."""

    def __init__(self, servidor: Any) -> None:
        self.servidor = servidor
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, **params: Any) -> Any:
        self.chamadas.append((metodo, dict(params)))
        if metodo not in self.servidor._handlers:
            return {"status": "metodo_ausente"}
        return asyncio.run(self.servidor._handlers[metodo](dict(params)))

    def __getattr__(self, nome: str) -> Any:
        raise AssertionError(f"o gesto da Acessibilidade chamou `{nome}`, que não é do desenho")


def _servidor(tmp_path: pathlib.Path) -> Any:
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.testing import FakeController

    controle = FakeController(transport="bt")  # type: ignore[arg-type]
    controle.primary_uniq = _P1  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(controller=controle, store=daemon.store, profile_manager=gerente,
                         socket_path=tmp_path / "ac.sock", daemon=daemon)
    daemon._ipc_server = servidor
    perfil = Profile(name="Ensaio", match=MatchAny(type="any"))
    save_profile(perfil)
    servidor.store.set_active_profile(perfil.name)
    return servidor


def _do_disco() -> Any:
    from hefesto_dualsense4unix.profiles.loader import load_profile

    return load_profile("Ensaio")


class _Mesa:
    def __init__(self, tmp_path: pathlib.Path) -> None:
        self.pacotes, self.a06 = _pacotes()
        self.servidor = _servidor(tmp_path)
        self.ponte = _Ponte(self.servidor)
        lugares = [{"uniq": _P1, "nome": "Um", "jogador": 1, "is_primary": True},
                   {"uniq": _P2, "nome": "Dois", "jogador": 2}]
        self.ctx = self.pacotes.Contexto(
            state={"active_profile": "Ensaio"}, mesa=lugares, conectados=lugares, estados={})

    def clica(self, gesto: str, **o: Any) -> dict[str, Any]:
        fn = self.pacotes.gesto_da_pagina(PAGINA, gesto)
        assert fn is not None, f"o gesto {gesto!r} não tem dono"
        return fn(self.ctx, o, self.ponte) or {}

    def liga(self, campo: str, chip: str) -> dict[str, Any]:
        return self.clica("ac-liga", ac=campo, v=chip)

    def passo(self, campo: str, sentido: str, vezes: int = 1) -> None:
        for _ in range(vezes):
            self.clica("ac-passo", ac=campo, v=sentido)

    def pintura(self) -> dict[str, str]:
        return self.a06._pinta_acessibilidade(self.ctx)


def test_toda_linha_com_motor_tem_gesto_e_so_a_sem_motor_segue_apagada() -> None:
    """D-2611-A-ACESSIBILIDADE-DA-NAVEGACAO-GRAVA-NO-GUARDAR:
    a janela acende, menos o que o motor não atende.
    """
    tela = _janela()
    linhas = tela.split('<div class="ac2"')[1:]
    assert len(linhas) == 17, len(linhas)
    apagadas = [linha for linha in linhas if "inert" in linha.split('<div class="ac2"')[0]
                or "opacity:.4" in linha[:40]]
    assert len(apagadas) == 1 and "Trocar de lado com" in apagadas[0], apagadas
    assert tela.count(" inert") == 1, "só a linha sem motor fica inerte"
    for tag in re.findall(r"<(?:button|select|input)\b[^>]*>", tela):
        if "disabled" in tag:
            assert "data-gesto" not in tag, tag
        else:
            assert "data-gesto" in tag or 'href="#"' in tag or "tn-x" in tag, (
                f"um controle vivo da Acessibilidade ficou sem gesto: {tag}")
    rodape = tela[tela.index('class="tn-rod"'):]
    for rotulo, gesto in (("Voltar ao padrão", "ac-padrao"), ("Guardar", "ac-guarda")):
        tag = re.search(rf'<button[^>]*data-gesto="{gesto}"[^>]*>{rotulo}</button>', rodape)
        assert tag and "aria-disabled" not in tag.group(0), f"o «{rotulo}» não está vivo"
    assert re.search(r'<a class="btn" href="#" data-gesto="ac-cancela">Cancelar</a>', rodape)
    assert "aria-disabled" not in tela and "disabled" not in re.sub(
        r'<select class="campo-linha" disabled>', "", tela)


def test_todo_gesto_e_todo_endereco_da_janela_tem_dono() -> None:
    """D-2611-A-ACESSIBILIDADE-DA-NAVEGACAO-GRAVA-NO-GUARDAR:
    página e pacote falam dos mesmos nomes.
    """
    pacotes, a06 = _pacotes()
    tela = _janela()
    for gesto in set(re.findall(r'data-gesto="(ac-[a-z]+)"', tela)):
        assert pacotes.gesto_da_pagina(PAGINA, gesto) is not None, gesto
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    enderecos = set(re.findall(r'data-campo="(ac-[^"]+)"', tela))
    pintados = set(a06._pinta_acessibilidade(ctx))
    assert pintados <= enderecos, sorted(pintados - enderecos)
    assert enderecos <= pintados, sorted(enderecos - pintados)


def test_clicar_so_mexe_no_rascunho_e_o_guardar_grava_o_que_mudou(tmp_path: pathlib.Path) -> None:
    """D-2611-A-ACESSIBILIDADE-DA-NAVEGACAO-GRAVA-NO-GUARDAR:
    o L1 alterna e o tremor de 120 ms chegam ao perfil.
    """
    m = _Mesa(tmp_path)
    eco = m.liga("ativacao.alternar", "l1")
    assert eco["mesa"]["ac-ativacao-alternar-l1"] == "sim"
    m.passo("ativacao.repique_ms", "+", 12)
    assert m.pintura()["ac-ativacao-repique_ms"] == "120"
    assert m.ponte.chamadas == [], "um clique foi ao Hefesto antes do «Guardar»"
    assert _do_disco().ativacao is None
    m.clica("ac-guarda")
    chamadas = dict(m.ponte.chamadas)
    assert chamadas == {"perfil.ativacao.set": {"alternar": ["l1"], "repique_ms": 120}}, chamadas
    ativacao = _do_disco().ativacao
    assert ativacao.alternar == ["l1"] and ativacao.repique_ms == 120
    assert m.a06._AC_RASCUNHO == {}
    assert m.pintura()["ac-ativacao-alternar-l1"] == "sim"


def test_cada_controle_manda_o_campo_certo(tmp_path: pathlib.Path) -> None:
    """D-2611-A-ACESSIBILIDADE-DA-NAVEGACAO-GRAVA-NO-GUARDAR:
    os doze ajustes do perfil chegam ao disco.
    """
    m = _Mesa(tmp_path)
    m.liga("ativacao.repetir", "direcional")
    m.liga("ativacao.travar", "r2")
    m.passo("ativacao.longo_ms", "+", 3)
    m.passo("ativacao.duplo_ms", "-", 1)
    m.passo("ativacao.repete_apos_ms", "+", 2)
    m.passo("ativacao.repete_por_segundo", "+", 4)
    m.passo("ativacao.aperto_minimo_ms", "+", 5)
    m.clica("ac-liga", ac="ativacao.ps_travado_ms")
    m.passo("analogicos.zona_morta", "+", 2)
    m.passo("analogicos.sensibilidade", "-", 2)
    m.clica("ac-escolhe", ac="analogicos.curva", v="precisa")
    m.liga("analogicos.inverter", "y")
    m.clica("ac-escolhe", ac="analogicos.mao", v="direita")
    m.clica("ac-guarda")
    ativacao, analogicos = _do_disco().ativacao, _do_disco().analogicos
    assert ativacao.repetir == ["dpad_up", "dpad_down", "dpad_left", "dpad_right"]
    assert ativacao.travar == ["r2"]
    assert (ativacao.longo_ms, ativacao.duplo_ms, ativacao.repete_apos_ms) == (800, 200, 700)
    assert (ativacao.repete_por_segundo, ativacao.aperto_minimo_ms) == (10, 50)
    assert ativacao.ps_travado_ms == 600
    assert (analogicos.zona_morta, analogicos.sensibilidade) == (10, 90)
    assert analogicos.curva == "precisa"
    assert analogicos.inverter == ["ly", "ry"] and analogicos.mao == "direita"
    assert analogicos.trocar is False


def test_um_botao_um_modo_e_a_mao_e_a_troca_se_excluem(tmp_path: pathlib.Path) -> None:
    """D-2611-A-ACESSIBILIDADE-DA-NAVEGACAO-GRAVA-NO-GUARDAR:
    o botão que muda de modo sai do outro, na mesma volta.
    """
    m = _Mesa(tmp_path)
    m.liga("ativacao.alternar", "l1")
    m.clica("ac-guarda")
    m.liga("ativacao.travar", "l1")
    assert m.pintura()["ac-ativacao-alternar-l1"] == ""
    assert m.pintura()["ac-ativacao-travar-l1"] == "sim"
    m.clica("ac-guarda")
    ativacao = _do_disco().ativacao
    assert ativacao.alternar == [] and ativacao.travar == ["l1"]
    m.clica("ac-escolhe", ac="analogicos.mao", v="esquerda")
    m.liga("analogicos.trocar", "lados")
    assert m.pintura()["ac-analogicos-mao"] == "desligada"
    m.clica("ac-escolhe", ac="analogicos.mao", v="esquerda")
    assert m.pintura()["ac-analogicos-trocar-lados"] == ""


def test_o_pedido_que_o_perfil_recusa_sobe_dito_e_o_rascunho_fica(tmp_path: pathlib.Path) -> None:
    """D-2611-A-ACESSIBILIDADE-DA-NAVEGACAO-GRAVA-NO-GUARDAR:
    botão com dois modos diz qual e não some.
    """
    m = _Mesa(tmp_path)
    asyncio.run(m.servidor._handlers["perfil.ativacao.set"](
        {"longo": {"cross": "circle"}}))
    m.ponte.chamadas.clear()
    m.liga("ativacao.alternar", "cross")
    with pytest.raises(RuntimeError, match="cross"):
        m.clica("ac-guarda")
    assert m.a06._AC_RASCUNHO, "o rascunho sumiu junto com a recusa"
    assert m.ponte.chamadas == [], "a seção inválida foi ao Hefesto"


def test_voltar_ao_padrao_enche_o_rascunho_e_so_o_guardar_devolve_a_fabrica(
    tmp_path: pathlib.Path,
) -> None:
    """D-2611-A-ACESSIBILIDADE-DA-NAVEGACAO-GRAVA-NO-GUARDAR:
    «Voltar ao padrão» só vale depois do «Guardar».
    """
    m = _Mesa(tmp_path)
    m.liga("ativacao.alternar", "r1")
    m.passo("analogicos.zona_morta", "+", 3)
    m.clica("ac-guarda")
    assert _do_disco().analogicos.zona_morta == 15
    m.clica("ac-padrao")
    assert _do_disco().analogicos.zona_morta == 15, "o «Voltar ao padrão» gravou sem o «Guardar»"
    assert m.pintura()["ac-analogicos-zona_morta"] == "0"
    m.clica("ac-guarda")
    assert _do_disco().ativacao.alternar == [] and _do_disco().analogicos.zona_morta == 0


def test_cancelar_larga_o_rascunho(tmp_path: pathlib.Path) -> None:
    """D-2611-A-ACESSIBILIDADE-DA-NAVEGACAO-GRAVA-NO-GUARDAR:
    o «Cancelar» e o «fechar» devolvem o que o perfil diz.
    """
    m = _Mesa(tmp_path)
    m.liga("ativacao.alternar", "l2")
    assert m.pintura()["ac-ativacao-alternar-l2"] == "sim"
    m.clica("ac-cancela")
    assert m.pintura()["ac-ativacao-alternar-l2"] == ""
    assert m.ponte.chamadas == [] and _do_disco().ativacao is None


def test_em_todo_perfil_apagado_grava_na_peca_do_para(tmp_path: pathlib.Path) -> None:
    """D-2611-EM-TODO-PERFIL-GRAVA-NO-PERFIL-E-APAGADO-GRAVA-NA-PECA:
    a chave escolhe onde o «Guardar» escreve.
    """
    m = _Mesa(tmp_path)
    m.liga("ativacao.alternar", "l1")
    m.clica("ac-guarda")
    assert _do_disco().ativacao.alternar == ["l1"] and not _do_disco().controllers
    eco = m.clica("ac-escopo")
    assert eco["mesa"]["ac-todo-perfil"] == "" and eco["mesa"]["ac-todo-perfil-txt"] == "Não"
    m.liga("ativacao.alternar", "r1")
    m.clica("ac-guarda")
    assert m.ponte.chamadas[-1][1]["uniq"] == _P1
    assert _do_disco().ativacao.alternar == ["l1"], "a escolha da peça vazou para o perfil"
    dele = (_do_disco().controllers or {})["aabbcc000001"]
    assert dele.ativacao.alternar == ["l1", "r1"]
    assert m.pintura()["ac-ativacao-alternar-r1"] == "sim"


def test_o_giroscopio_vai_ao_mira_set_do_controle_do_para(tmp_path: pathlib.Path) -> None:
    """D-2611-A-ACESSIBILIDADE-DA-NAVEGACAO-GRAVA-NO-GUARDAR:
    o giro e o gatilho chegam ao `mira.set` da peça.
    """
    m = _Mesa(tmp_path)
    m.clica("ac-escolhe", ac="giro.lado", v="analogico_esquerdo")
    m.clica("ac-escolhe", ac="giro.gatilho", v="l2")
    m.clica("ac-guarda")
    metodo, pedido = m.ponte.chamadas[-1]
    assert metodo == "mira.set"
    assert pedido == {"uniq": _P1, "ligada": True, "lado": "analogico_esquerdo", "gatilho": "l2"}


def test_sem_controle_o_giro_nao_finge_guardar(tmp_path: pathlib.Path) -> None:
    """D-2611-A-ACESSIBILIDADE-DA-NAVEGACAO-GRAVA-NO-GUARDAR:
    sem controle o giroscópio recusa dizendo.
    """
    m = _Mesa(tmp_path)
    m.ctx.mesa.clear()
    m.ctx.conectados.clear()
    m.clica("ac-escolhe", ac="giro.lado", v="analogico_direito")
    with pytest.raises(RuntimeError, match="controle"):
        m.clica("ac-guarda")
    assert m.ponte.chamadas == []


def test_o_clique_que_nao_diz_o_ajuste_ou_o_valor_recusa(tmp_path: pathlib.Path) -> None:
    """D-2611-A-ACESSIBILIDADE-DA-NAVEGACAO-GRAVA-NO-GUARDAR:
    o `data-ac` e o `data-v` são conferidos.
    """
    m = _Mesa(tmp_path)
    for gesto, o in (("ac-liga", {}), ("ac-liga", {"ac": "ativacao.alternar", "v": "xis"}),
                     ("ac-passo", {"ac": "ativacao.longo_ms", "v": "?"}),
                     ("ac-escolhe", {"ac": "analogicos.curva", "v": "torta"}),
                     ("ac-escolhe", {"ac": "analogicos.mao", "v": "nenhuma"})):
        with pytest.raises(ValueError):
            m.clica(gesto, **o)


def test_as_faixas_da_janela_sao_as_do_perfil() -> None:
    """D-2611-A-ACESSIBILIDADE-DA-NAVEGACAO-GRAVA-NO-GUARDAR:
    o passo nunca sai da faixa que o perfil aceita.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        ProfileAnalogicosConfig,
        ProfileAtivacaoConfig,
    )

    a06 = _pacotes()[1]
    for chave, (_passo, minimo, maximo, _un) in a06.AC_PASSOS.items():
        secao, _, campo = chave.partition(".")
        ativa = secao == "ativacao"  # (noqa-acento)
        modelo = ProfileAtivacaoConfig if ativa else ProfileAnalogicosConfig
        padrao = modelo().model_dump()
        modelo.model_validate({**padrao, campo: minimo})
        modelo.model_validate({**padrao, campo: maximo})
        with pytest.raises(ValueError):
            modelo.model_validate({**padrao, campo: maximo + 1})
        assert a06.AC_DE_FABRICA[chave] == padrao[campo], chave
