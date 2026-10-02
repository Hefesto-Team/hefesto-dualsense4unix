#!/usr/bin/env python3
"""OS CINCO DESTRUTIVOS PEDEM DOIS CLIQUES — decisão dela, 03/09/2026."""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/09-sistema.html"


class JanelaDeMentira:
    """O dublê de `DaemonActionsMixin`. Guarda o que TERIA ido ao systemd."""

    def __init__(self, status: str = "online_systemd", ativo: str = "active",
                 pid_vivo: bool = False, rc: int = 0) -> None:
        self.status, self.ativo, self.pid_vivo, self.rc = status, ativo, pid_vivo, rc
        self.comandos: list[list[str]] = []
        self._user_stopped_daemon: bool | None = None

    def _daemon_status(self) -> str:
        return self.status

    def _systemctl_status_text(self, unit: str) -> str:
        return "● unidade ativa"

    def _is_service_active(self) -> str:
        return self.ativo

    def _daemon_pid_alive(self) -> bool:
        return self.pid_vivo

    def _invoke_systemctl(self, args, capture=False, check=False):
        self.comandos.append(list(args))

        class R:
            returncode = self.rc
            stderr = "" if self.rc == 0 else "Failed to start unit."

        return R()

    def atos(self) -> list[str]:
        return [a[0] for a in self.comandos if a and a[0] != "reset-failed"]


@pytest.fixture
def a09(monkeypatch):
    from pacotes import a09_sistema as mod

    janela = JanelaDeMentira()
    mod._JANELA_ANTIGA[:] = [janela]
    monkeypatch.setattr(mod, "_autostart", lambda: "enabled")
    mod._LENTO.clear()
    mod._LENTO_EM_VOO[0] = False
    mod._ARMADO.clear()
    mod._PAINEL[0] = None
    yield mod
    mod._JANELA_ANTIGA.clear()
    mod._LENTO.clear()
    mod._ARMADO.clear()
    mod._PAINEL[0] = None


@pytest.fixture
def janela(a09):
    return a09._JANELA_ANTIGA[0]


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(state={"paused": False, "controllers": []},
                            mesa=[], conectados=[], estados={})


@pytest.fixture
def ctx_parado():
    """O contexto de quem NÃO tem daemon: `state` vazio, como o piloto o passa.

    O `state` NÃO É DETALHE AQUI, e a régua aprendeu isso reprovando:
    `_status_do_daemon` usa o `state` como PISO — *"se o daemon respondeu, ele
    está de pé"* — e um `state` de mentira preenchido faria a aba dizer
    `online_avulso` sobre um systemd que respondeu `offline`. Com o daemon
    parado de verdade, o `state_full` não volta e o piloto passa vazio.
    """
    import pacotes

    return pacotes.Contexto(state=None, mesa=[], conectados=[], estados={})


def _clique(texto: str) -> dict[str, str]:
    """O que o ouvinte do piloto manda: o rótulo do elemento clicado."""
    return {"texto": texto}


def test_o_primeiro_clique_arma_e_nao_para_nada(a09, ctx, janela):
    """Clicar "Parar o serviço" uma vez NÃO manda `stop` a ninguém."""
    a09.desligar(ctx, _clique(a09._rotulo_do_desenho(a09.DESLIGAR)), None)

    assert janela.atos() == [], (
        f"o primeiro clique mandou {janela.atos()} ao systemd — ele tinha de "
        "ARMAR e mais nada.")
    assert a09._armado_agora() == a09.DESLIGAR


def test_o_botao_armado_veste_a_palavra_dela(a09, ctx):
    """O `blocos:` de volta troca o rótulo do botão por `Confirma?`, na hora."""
    carga = a09.desligar(ctx, _clique("Parar o serviço"), None)

    assert carga["blocos"]['[data-gesto="parar-ou-retomar"]'] == a09.CONFIRMA
    for nome in a09.DESTRUTIVOS:
        if nome != a09.DESLIGAR:
            assert carga["blocos"][f'[data-gesto="{nome}"]'] != a09.CONFIRMA


def test_o_seletor_do_blocos_existe_na_pagina_publicada(a09, ctx):
    """Um `blocos:` que não acha onde pousar some CALADO — e daria verde aqui."""
    doc = PAGINA.read_text(encoding="utf-8")
    for seletor in a09.blocos_dos_botoes(True):
        atributo, valor = re.match(r'\[([a-z-]+)="([^"]+)"\]', seletor).groups()
        assert f'{atributo}="{valor}"' in doc, (
            f"o `blocos:` mira {seletor}, e a página publicada não tem esse "
            "endereço — o `querySelector` devolve `null` e a troca some calada.")


def test_o_segundo_clique_so_vale_com_o_rotulo_do_botao_armado(a09, ctx, janela):
    """O guarda é o VALOR que só existe no botão já armado — como na Lançadores."""
    rotulo = a09._rotulo_do_desenho(a09.DESLIGAR)
    a09.desligar(ctx, _clique(rotulo), None)
    a09.desligar(ctx, _clique(rotulo), None)

    assert janela.atos() == [], (
        f"dois cliques na palavra do desenho mandaram {janela.atos()} — o "
        "segundo tinha de REARMAR, não de agir.")
    assert a09._armado_agora() == a09.DESLIGAR, "o segundo clique desarmou"


def test_os_dois_cliques_param_o_servico_e_seguram_o_autostart(a09, ctx, janela):
    """Armado, o clique com `Confirma?` manda `stop` — e arma a trava do religa.

    O `_user_stopped_daemon` é a metade que a janela antiga já tinha
    (`daemon_actions.on_daemon_stop:2234`): sem ele o `ensure_daemon_running`
    ressuscita o daemon na próxima abertura, e o "Parar" dura até o próximo F5.
    Ele é armado NO SUCESSO — e aqui isso sai de graça, porque `_systemctl`
    levanta quando o `rc != 0`.

    A MORDIDA: apague o `_matriz()._user_stopped_daemon = True`. Reprova dizendo
    que o desligamento não segura o autostart.
    """
    a09.desligar(ctx, _clique(a09._rotulo_do_desenho(a09.DESLIGAR)), None)
    carga = a09.desligar(ctx, _clique(a09.CONFIRMA), None)

    assert janela.atos() == ["stop"]
    assert janela._user_stopped_daemon is True, (
        "o `stop` saiu e o `_user_stopped_daemon` não foi armado — o daemon "
        "volta sozinho na próxima abertura da janela.")
    assert a09._armado_agora() == "", "o botão ficou armado depois de agir"
    assert carga["blocos"]['[data-gesto="parar-ou-retomar"]'] == a09.ATIVAR


def test_fora_do_prazo_ele_recusa_dizendo_e_nao_age(a09, ctx, janela, monkeypatch):
    """Passado o prazo, o `Confirma?` recusa com a frase — e nada vai ao systemd.

    A frase chega à tela pela tarja (`hefesto_vivo._recusou_dizendo`), que é o
    caminho do `RuntimeError` nesta casa. Rearmar calado deixaria a tela dizendo
    "Confirma?" sobre um consentimento que já tinha vencido.

    A MORDIDA: tire o `raise` do ramo `if not armado`. Reprova dizendo que um
    clique de dez minutos depois parou o serviço.
    """
    a09.desligar(ctx, _clique(a09._rotulo_do_desenho(a09.DESLIGAR)), None)
    # diz quanto dura o consentimento é `confirmacao.SEGUNDOS_PARA_CONFIRMAR`.
    a09._ARMADO["ate"] -= a09.segundos_para_confirmar() + 1

    with pytest.raises(RuntimeError, match="segundos"):
        a09.desligar(ctx, _clique(a09.CONFIRMA), None)

    assert janela.atos() == []
    assert a09._armado_agora() == "", "a recusa deixou o botão armado"


def test_a_janela_do_consentimento_e_a_da_aba_que_ja_confirma(a09):
    """O relógio é PERGUNTADO, nunca digitado — o dono é `pacotes/confirmacao`.

    A MORDIDA: troque `segundos_para_confirmar()` por um `20.0` literal e mude o
    `SEGUNDOS_PARA_CONFIRMAR` de lá. Reprova, porque as duas deixam de casar.
    """
    from pacotes import confirmacao

    assert a09.segundos_para_confirmar() == confirmacao.SEGUNDOS_PARA_CONFIRMAR


def test_o_tique_repoe_o_rotulo_quando_o_prazo_passa(a09, ctx):
    """Ela armou e saiu: o botão TEM de voltar a dizer o que o desenho diz."""
    a09.desligar(ctx, _clique("Parar o serviço"), None)
    assert a09.pacote(ctx)["blocos"]['[data-gesto="parar-ou-retomar"]'] == a09.CONFIRMA

    a09._ARMADO["ate"] -= a09.segundos_para_confirmar() + 1
    depois = a09.pacote(ctx)["blocos"]['[data-gesto="parar-ou-retomar"]']

    assert depois == a09._rotulo_do_desenho(a09.DESLIGAR), (
        f"o tique deixou {depois!r} no botão depois de o prazo passar.")


def test_armar_o_segundo_repoe_o_primeiro(a09, ctx, monkeypatch):
    """Uma pergunta por vez. Dois "Confirma?" na tela seriam duas perguntas."""
    a09.desligar(ctx, _clique("Parar o serviço"), None)
    carga = a09.aplicar_aos_jogos(
        ctx, _clique("Aplicar soluções nos lançadores"), None)

    assert carga["blocos"]['[data-gesto="aplicar-aos-jogos"]'] == a09.CONFIRMA
    assert carga["blocos"]['[data-gesto="parar-ou-retomar"]'] == a09._rotulo_do_desenho(
        a09.DESLIGAR)


def test_os_rotulos_saem_da_pagina_e_nao_de_uma_lista_aqui(a09):
    """O rótulo tem dono — o gerador —, e esta régua confere que ele foi LIDO."""
    doc = PAGINA.read_text(encoding="utf-8")
    for nome in a09.DESTRUTIVOS:
        achado = re.search(
            r'data-gesto="' + re.escape(nome) + r'"[^>]*>([^<]*)</button>', doc)
        assert achado, f"a página publicada não tem mais o botão `{nome}`"
        assert a09._rotulo_do_desenho(nome) == achado.group(1).strip()


def test_com_o_servico_parado_o_botao_oferece_ligar(a09, ctx_parado, janela):
    """*"um específico pra parar o Daemon E Ativar o Daemon"* — um botão, duas caras."""
    janela.status = "offline"
    a09._LENTO.clear()

    assert a09.blocos_dos_botoes(False)['[data-gesto="parar-ou-retomar"]'] == a09.ATIVAR


def test_o_pacote_veste_o_botao_mesmo_com_a_aba_muda(a09, ctx_parado, janela,
                                                     monkeypatch):
    """Com o daemon parado a aba emudece — e é AÍ que o botão precisa falar."""
    janela.status = "offline"
    a09._LENTO.clear()
    monkeypatch.setattr(a09._tela, "pacote",
                        lambda _l: (_ for _ in ()).throw(RuntimeError("mudo")))

    carga = a09.pacote(ctx_parado)

    assert carga["sem_dono"]["tela"]["sem_dono"] is True
    assert carga["blocos"]['[data-gesto="parar-ou-retomar"]'] == a09.ATIVAR


def test_ligar_e_um_clique_so_e_desarma_a_trava_do_religa(a09, ctx_parado, janela,
                                                          monkeypatch):
    """Ligar o que já está parado não perde nada — logo não pede confirmação."""
    from hefesto_dualsense4unix.daemon import service_install

    monkeypatch.setattr(service_install.ServiceInstaller, "detect_installed_unit",
                        lambda self: "hefesto.service")
    janela.status, janela.ativo = "offline", "inactive"
    a09._LENTO.clear()

    carga = a09.desligar(ctx_parado, _clique(a09.ATIVAR), None)

    assert janela.atos() == ["start"]
    assert janela._user_stopped_daemon is False, (
        "ligou e não desarmou o `_user_stopped_daemon` — o autostart continuaria "
        "respeitando um desligamento que ela acabou de desfazer.")
    assert carga["blocos"]


def test_os_tres_portoes_do_produto_seguram_o_start(a09, janela):
    """`ativar_o_servico` não liga nada em três casos, e nenhum é palpite meu."""
    from hefesto_dualsense4unix.daemon.service_install import ServiceInstaller

    assert ServiceInstaller().detect_installed_unit() is None
    assert a09.ativar_o_servico() is False
    assert janela.atos() == [], "ligou sem unit instalada"


@pytest.mark.parametrize("ativo,pid_vivo,porque", [
    ("active", False, "o serviço já está ativo"),
    ("inactive", True, "há um daemon avulso vivo"),
])
def test_os_portoes_dois_e_tres_com_a_unit_instalada(a09, janela, monkeypatch,
                                                     ativo, pid_vivo, porque):
    """Com unit instalada, os outros dois portões continuam segurando."""
    from hefesto_dualsense4unix.daemon import service_install

    monkeypatch.setattr(service_install.ServiceInstaller, "detect_installed_unit",
                        lambda self: "hefesto.service")
    janela.ativo, janela.pid_vivo = ativo, pid_vivo

    assert a09.ativar_o_servico() is False, f"ligou mesmo com {porque}"
    assert janela.atos() == []


def test_com_a_unit_instalada_e_o_servico_parado_ele_liga(a09, janela, monkeypatch):
    """A guarda de vacuidade dos três acima: com os portões abertos, ele LIGA."""
    from hefesto_dualsense4unix.daemon import service_install

    monkeypatch.setattr(service_install.ServiceInstaller, "detect_installed_unit",
                        lambda self: "hefesto.service")
    janela.ativo, janela.pid_vivo = "inactive", False

    assert a09.ativar_o_servico() is True
    assert janela.atos() == ["start"]


@pytest.mark.parametrize("modo,liga", [("gamepad", True), ("native", False)])
def test_o_interruptor_da_jogar_liga_o_servico_so_no_ligado(monkeypatch, modo, liga):
    """"Ligado" liga o serviço; "Desligado" não sobe o que ela mandou sair."""
    from pacotes import a01_jogar, a09_sistema

    ordem: list[str] = []
    monkeypatch.setattr(a09_sistema, "ativar_o_servico",
                        lambda: ordem.append("ligou") or True)
    monkeypatch.setattr(a01_jogar, "_plano",
                        lambda *_a, **_k: (ordem.append("plano"), [])[1])
    monkeypatch.setattr(a01_jogar, "_lembrar", lambda *_a, **_k: None)

    a01_jogar.hefesto(None, {"modo": modo, "texto": "x"}, None)

    assert ("ligou" in ordem) is liga, (
        f"a posição {modo!r} {'não ' if liga else ''}ligou o serviço")
    if liga:
        assert ordem == ["ligou", "plano"], (
            "o plano saiu antes de o serviço subir — com a ponte sem socket, o "
            f"clique recusaria. Ordem medida: {ordem}")


def test_o_ato_de_ligar_tem_um_dono_so(monkeypatch):
    """A aba Jogar não reescreve o `systemctl` — ela chama o dono.

    Duas cópias deste ato se afastariam: uma desarmaria o `_user_stopped_daemon`
    e a outra não, e o daemon voltaria a morrer no próximo F5 por um caminho e
    não pelo outro.

    A MORDIDA: escreva `_systemctl("start")` dentro de `a01_jogar`. Reprova
    nomeando a segunda cópia.
    """
    fonte = pathlib.Path(
        RAIZ / "src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py"
    ).read_text(encoding="utf-8")

    assert "ativar_o_servico" in fonte
    assert "systemctl" not in fonte.replace("# ", ""), (
        "a aba Jogar passou a falar `systemctl` por conta própria — o ato tem "
        "dono em `a09_sistema.ativar_o_servico`.")
