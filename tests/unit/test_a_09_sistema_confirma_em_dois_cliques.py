#!/usr/bin/env python3
"""OS CINCO DESTRUTIVOS PEDEM DOIS CLIQUES — decisão dela, 03/09/2026.

ELA ESCOLHEU **"Dois cliques, como na Lançadores"**, e escolheu a palavra do
botão armado entre três: **"Confirma?"**. Esta régua mede as duas metades do que
isso virou, e mede o PAR que ela pediu no mesmo dia — *"em sistema um específico
pra parar o Daemon E Ativar o Daemon (sendo que em jogar também consegue isso)"*.

O QUE ELA COBRA, e cada bloco traz a MORDIDA que o derruba:

1. **o primeiro clique não age** — ele arma, e nenhum comando sai para o systemd;
2. **o botão armado diz `Confirma?`**, e o rótulo chega pelo `blocos:` do gesto;
3. **o segundo clique só vale com o rótulo do botão armado** — um clique com a
   palavra do desenho REARMA em vez de agir;
4. **fora do prazo ele recusa DIZENDO**, e não age;
5. **quem repõe o rótulo é o TIQUE** — sem isso o "Confirma?" ficaria na tela
   para sempre depois de ela armar e sair;
6. **o par Parar/Ativar** — com o serviço parado o mesmo botão diz "Ativar o
   serviço" e LIGA em UM clique, porque ligar o que já está parado não perde nada;
7. **a aba Jogar liga o serviço no "Ligado"**, e não no "Desligado".

NENHUM `systemctl` DE VERDADE RODA AQUI: o `_invoke_systemctl` é dublado pela
janela de mentira, e os três portões de `ativar_o_servico` são exercitados por
dublê. Uma régua que para o daemon de quem a executa não é régua — e nesta aba
isso não é hipótese: o gesto medido é o que desliga o Hefesto dela.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: A página que o PRODUTO renderiza. A bancada daria verde sobre um endereço que
#: a tela dela não tem — a armadilha do `COMO-OLHAR-A-TELA.md`.
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

    #: Só os verbos que MEXEM. O `reset-failed` do `_systemctl` é preparo, e
    #: contá-lo faria toda mordida ver "um comando" onde não houve ato.
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
    """O que o ouvinte do piloto manda: o rótulo do elemento clicado.

    O NOME DA CHAVE NÃO É ESCOLHA MINHA — é `texto`, e quem o escreve é
    `hefesto_vivo.BOOTSTRAP` (`texto: (alvo.textContent || '').trim()`).
    """
    return {"texto": texto}


# ---------------------------------------------------------------------------
# 1. O PRIMEIRO CLIQUE NÃO AGE
# ---------------------------------------------------------------------------
def test_o_primeiro_clique_arma_e_nao_para_nada(a09, ctx, janela):
    """Clicar "Parar o serviço" uma vez NÃO manda `stop` a ninguém.

    É a metade que faltava e que `SEM_CONFIRMACAO` dizia com todas as letras:
    *"ligar sem a confirmação seria pior que o botão morto"*. O `title` deste
    botão promete "Pergunta antes, dizendo o que se perde", e é esta linha que
    faz a promessa valer.

    A MORDIDA: tire o `if not _confirmado(...)` do gesto `desligar` e esta régua
    reprova dizendo que o `stop` saiu no primeiro clique. Executada:

        AssertionError: o primeiro clique mandou ['stop'] ao systemd
    """
    a09.desligar(ctx, _clique(a09._rotulo_do_desenho("desligar")), None)

    assert janela.atos() == [], (
        f"o primeiro clique mandou {janela.atos()} ao systemd — ele tinha de "
        "ARMAR e mais nada.")
    assert a09._armado_agora() == "desligar"


def test_o_botao_armado_veste_a_palavra_dela(a09, ctx):
    """O `blocos:` de volta troca o rótulo do botão por `Confirma?`, na hora.

    NÃO É O TIQUE QUEM FAZ ISSO — é a resposta do próprio gesto. Esperar o tique
    deixaria um vão em que ela clicou e a tela não respondeu, e o segundo clique
    pareceria o primeiro; é o defeito mais caro desta casa.

    A MORDIDA: faça o gesto devolver `None` no ramo de armar. Reprova dizendo
    que o botão não vestiu a pergunta.
    """
    carga = a09.desligar(ctx, _clique("Parar o serviço"), None)

    assert carga["blocos"]['[data-gesto="desligar"]'] == a09.CONFIRMA
    # E OS OUTROS QUATRO NÃO SE MEXEM: armar um botão não pode pôr "Confirma?"
    # em cinco. Cada um continua com a palavra do desenho.
    for nome in a09.DESTRUTIVOS:
        if nome != "desligar":
            assert carga["blocos"][f'[data-gesto="{nome}"]'] != a09.CONFIRMA


def test_o_seletor_do_blocos_existe_na_pagina_publicada(a09, ctx):
    """Um `blocos:` que não acha onde pousar some CALADO — e daria verde aqui.

    O `pintar()` do piloto faz `document.querySelector(seletor)` e, sem alvo,
    não escreve nada e não conta nada. Uma régua que só olhasse o dicionário
    devolvido pelo gesto passaria sobre cinco seletores mortos.

    A MORDIDA: troque o `_seletor` para `[data-acao="…"]` — atributo que a
    página não tem — e esta régua reprova nomeando os cinco.
    """
    doc = PAGINA.read_text(encoding="utf-8")
    for seletor in a09.blocos_dos_botoes(True):
        atributo, valor = re.match(r'\[([a-z-]+)="([^"]+)"\]', seletor).groups()
        assert f'{atributo}="{valor}"' in doc, (
            f"o `blocos:` mira {seletor}, e a página publicada não tem esse "
            "endereço — o `querySelector` devolve `null` e a troca some calada.")


# ---------------------------------------------------------------------------
# 2. O SEGUNDO CLIQUE
# ---------------------------------------------------------------------------
def test_o_segundo_clique_so_vale_com_o_rotulo_do_botao_armado(a09, ctx, janela):
    """O guarda é o VALOR que só existe no botão já armado — como na Lançadores.

    Lá é o `data-v` `steam:confirmo`; aqui é o rótulo, porque esta página é
    estática e o rótulo é o que a pintura troca. O efeito é o mesmo: a prova
    automática clica o que o DOM TINHA, e o DOM tinha a pergunta.

    A MORDIDA: faça `_confirmado` devolver `True` só pelo relógio, sem olhar o
    rótulo. Reprova dizendo que dois cliques na palavra do desenho pararam o
    serviço.
    """
    rotulo = a09._rotulo_do_desenho("desligar")
    a09.desligar(ctx, _clique(rotulo), None)
    a09.desligar(ctx, _clique(rotulo), None)

    assert janela.atos() == [], (
        f"dois cliques na palavra do desenho mandaram {janela.atos()} — o "
        "segundo tinha de REARMAR, não de agir.")
    assert a09._armado_agora() == "desligar", "o segundo clique desarmou"


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
    a09.desligar(ctx, _clique(a09._rotulo_do_desenho("desligar")), None)
    carga = a09.desligar(ctx, _clique(a09.CONFIRMA), None)

    assert janela.atos() == ["stop"]
    assert janela._user_stopped_daemon is True, (
        "o `stop` saiu e o `_user_stopped_daemon` não foi armado — o daemon "
        "volta sozinho na próxima abertura da janela.")
    assert a09._armado_agora() == "", "o botão ficou armado depois de agir"
    # E o botão já volta a oferecer o caminho de volta, sem esperar o tique.
    assert carga["blocos"]['[data-gesto="desligar"]'] == a09.ATIVAR


def test_fora_do_prazo_ele_recusa_dizendo_e_nao_age(a09, ctx, janela, monkeypatch):
    """Passado o prazo, o `Confirma?` recusa com a frase — e nada vai ao systemd.

    A frase chega à tela pela tarja (`hefesto_vivo._recusou_dizendo`), que é o
    caminho do `RuntimeError` nesta casa. Rearmar calado deixaria a tela dizendo
    "Confirma?" sobre um consentimento que já tinha vencido.

    A MORDIDA: tire o `raise` do ramo `if not armado`. Reprova dizendo que um
    clique de dez minutos depois parou o serviço.
    """
    a09.desligar(ctx, _clique(a09._rotulo_do_desenho("desligar")), None)
    # O RELÓGIO É O DO PRODUTO, e o teste o EMPURRA em vez de digitar 21: quem
    # diz quanto dura o consentimento é `a07_lancadores.SEGUNDOS_PARA_CONFIRMAR`.
    a09._ARMADO["ate"] -= a09.segundos_para_confirmar() + 1

    with pytest.raises(RuntimeError, match="segundos"):
        a09.desligar(ctx, _clique(a09.CONFIRMA), None)

    assert janela.atos() == []
    assert a09._armado_agora() == "", "a recusa deixou o botão armado"


def test_a_janela_do_consentimento_e_a_da_aba_que_ja_confirma(a09):
    """O relógio é PERGUNTADO, nunca digitado — o dono é a aba Lançadores.

    A MORDIDA: troque `segundos_para_confirmar()` por um `20.0` literal e mude o
    `SEGUNDOS_PARA_CONFIRMAR` de lá. Reprova, porque as duas deixam de casar.
    """
    from pacotes import a07_lancadores

    assert a09.segundos_para_confirmar() == a07_lancadores.SEGUNDOS_PARA_CONFIRMAR


# ---------------------------------------------------------------------------
# 3. QUEM REPÕE O RÓTULO É O TIQUE
# ---------------------------------------------------------------------------
def test_o_tique_repoe_o_rotulo_quando_o_prazo_passa(a09, ctx):
    """Ela armou e saiu: o botão TEM de voltar a dizer o que o desenho diz.

    Sem esta metade, um "Confirma?" ficaria na tela para sempre — a tela
    mentindo sobre o estado, que é o defeito que esta aba inteira existe para
    não repetir.

    A MORDIDA: tire o `fora["blocos"] = …` do `pacote()`. Reprova dizendo que o
    tique deixou a pergunta na tela depois do prazo.
    """
    a09.desligar(ctx, _clique("Parar o serviço"), None)
    assert a09.pacote(ctx)["blocos"]['[data-gesto="desligar"]'] == a09.CONFIRMA

    a09._ARMADO["ate"] -= a09.segundos_para_confirmar() + 1
    depois = a09.pacote(ctx)["blocos"]['[data-gesto="desligar"]']

    assert depois == a09._rotulo_do_desenho("desligar"), (
        f"o tique deixou {depois!r} no botão depois de o prazo passar.")


def test_armar_o_segundo_repoe_o_primeiro(a09, ctx):
    """Uma pergunta por vez. Dois "Confirma?" na tela seriam duas perguntas.

    A MORDIDA: troque o `if gesto == _armado_agora()` de `_rotulo_de_agora` por
    `if _armado_agora()`. Reprova dizendo que os dois botões vestiram a pergunta.
    Executada: 2 reprovaram (este e o `..._veste_a_palavra_dela`).

    **A MORDIDA QUE NÃO MORDEU, e ela fica escrita:** tirar o `_ARMADO.clear()`
    de antes do `update` em `_confirmado` passou VERDE — e está certo que passe.
    O `_ARMADO` é UM dicionário com UMA chave `gesto`; o `update` sobrescreve, e
    não há caminho em que dois fiquem armados. A invariante é estrutural, não
    defendida por aquela linha — e uma mordida que não morde é o instrumento
    mentindo sobre o que mede.
    """
    a09.desligar(ctx, _clique("Parar o serviço"), None)
    carga = a09.refazer_proton(ctx, _clique("Refazer a fixação do Proton"), None)

    assert carga["blocos"]['[data-gesto="refazer-proton"]'] == a09.CONFIRMA
    assert carga["blocos"]['[data-gesto="desligar"]'] == a09._rotulo_do_desenho(
        "desligar")


def test_os_rotulos_saem_da_pagina_e_nao_de_uma_lista_aqui(a09):
    """O rótulo tem dono — o gerador —, e esta régua confere que ele foi LIDO.

    Digitar "Parar o serviço" no pacote seria o segundo dono de uma palavra que
    ELA escolheu, e envelheceria calado no dia em que ela trocasse o verbo — o
    que já aconteceu uma vez ("encerrar" -> "parar", 31/08/2026).

    A MORDIDA: devolva `"Desligar o Hefesto"` — a palavra da JANELA VELHA, que é
    a regressão realista — em `_rotulo_do_desenho`. Reprova comparando com o HTML
    publicado. Executada: 1 reprovou.

    **A MORDIDA QUE NÃO MORDEU:** devolver `"Parar o serviço"` cravado passou
    verde, e tinha de passar — é a MESMA palavra que a página traz hoje. Uma
    mordida que escreve por acaso a resposta certa não mede o canal; ela mede a
    sorte de quem a escreveu.
    """
    doc = PAGINA.read_text(encoding="utf-8")
    for nome in a09.DESTRUTIVOS:
        achado = re.search(
            r'data-gesto="' + re.escape(nome) + r'"[^>]*>([^<]*)</button>', doc)
        assert achado, f"a página publicada não tem mais o botão `{nome}`"
        assert a09._rotulo_do_desenho(nome) == achado.group(1).strip()


# ---------------------------------------------------------------------------
# 4. O PAR QUE ELA PEDIU — Parar o serviço / Ativar o serviço
# ---------------------------------------------------------------------------
def test_com_o_servico_parado_o_botao_oferece_ligar(a09, ctx_parado, janela):
    """*"um específico pra parar o Daemon E Ativar o Daemon"* — um botão, duas caras.

    A MORDIDA: tire o ramo do `ATIVAR` de `_rotulo_de_agora`. Reprova dizendo
    que o botão continua oferecendo parar o que já está parado.
    """
    janela.status = "offline"
    a09._LENTO.clear()

    assert a09.blocos_dos_botoes(False)['[data-gesto="desligar"]'] == a09.ATIVAR


def test_o_pacote_veste_o_botao_mesmo_com_a_aba_muda(a09, ctx_parado, janela,
                                                     monkeypatch):
    """Com o daemon parado a aba emudece — e é AÍ que o botão precisa falar.

    `pacote()` cai no ramo do `sem_dono` quando a camada do produto levanta (é o
    que acontece sem daemon), e esse ramo continua emitindo os rótulos. Deixá-lo
    sem eles faria a saída de emergência existir só enquanto não é necessária.

    A MORDIDA: tire o `blocos` do `return` do `except` de `pacote()`. Reprova
    com `KeyError`, dizendo que a aba muda não veste o botão.
    """
    janela.status = "offline"
    a09._LENTO.clear()
    monkeypatch.setattr(a09._tela, "pacote",
                        lambda _l: (_ for _ in ()).throw(RuntimeError("mudo")))

    carga = a09.pacote(ctx_parado)

    assert carga["sem_dono"]["tela"]["sem_dono"] is True
    assert carga["blocos"]['[data-gesto="desligar"]'] == a09.ATIVAR


def test_ligar_e_um_clique_so_e_desarma_a_trava_do_religa(a09, ctx_parado, janela,
                                                          monkeypatch):
    """Ligar o que já está parado não perde nada — logo não pede confirmação.

    Pedir dois cliques aqui seria uma parede na saída de emergência: com o
    daemon parado esta aba emudece inteira, e este botão é o único caminho de
    volta que a interface nova tem.

    A MORDIDA: mande o ramo do `ATIVAR` passar por `_confirmado`. Reprova
    dizendo que o `start` não saiu no primeiro clique.
    """
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
    """`ativar_o_servico` não liga nada em três casos, e nenhum é palpite meu.

    Eles são os de `daemon_actions.ensure_daemon_running`: sem unit instalada,
    já ativo, ou daemon avulso vivo. O PRIMEIRO é também o que mantém a suíte
    fora do systemd de quem a roda — o `conftest.py` desvia o `HOME` e não há
    unit no lar de mentira.

    A MORDIDA: apague o portão do `_daemon_pid_alive`. Reprova dizendo que a
    aba subiria uma segunda instância por cima de um daemon avulso.
    """
    from hefesto_dualsense4unix.daemon.service_install import ServiceInstaller

    # 1. sem unit instalada — o HOME de mentira do `conftest.py` já garante isto,
    #    e a asserção o TORNA EXPLÍCITO em vez de contar com sorte.
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
    """A guarda de vacuidade dos três acima: com os portões abertos, ele LIGA.

    Sem esta, os quatro testes de cima passariam com `ativar_o_servico`
    devolvendo `False` sempre — a régua dando verde sobre uma função morta.
    """
    from hefesto_dualsense4unix.daemon import service_install

    monkeypatch.setattr(service_install.ServiceInstaller, "detect_installed_unit",
                        lambda self: "hefesto.service")
    janela.ativo, janela.pid_vivo = "inactive", False

    assert a09.ativar_o_servico() is True
    assert janela.atos() == ["start"]


# ---------------------------------------------------------------------------
# 5. A ABA JOGAR — *"sendo que em jogar também consegue isso"*
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("modo,liga", [("gamepad", True), ("native", False)])
def test_o_interruptor_da_jogar_liga_o_servico_so_no_ligado(monkeypatch, modo, liga):
    """"Ligado" liga o serviço; "Desligado" não sobe o que ela mandou sair.

    Quem diz quais posições são "ligado" é o produto (`painel.MODOS_LIGADOS`) —
    o `gamepad` e o `desktop` são o Hefesto no meio, o `native` é ele fora dele.

    E ELE VEM ANTES DO PLANO: sem o daemon de pé a ponte não tem socket, e a
    ordem inversa recusaria o clique deixando o serviço parado — o gesto
    falhando exatamente no caso que ela pediu que passasse a funcionar.

    A MORDIDA 1: tire o `ativar_o_servico()` do gesto. Reprova no caso `gamepad`.
    A MORDIDA 2: chame-o sem o `if`. Reprova no caso `native`.
    """
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
