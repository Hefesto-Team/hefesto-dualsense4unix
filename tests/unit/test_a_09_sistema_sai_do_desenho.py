#!/usr/bin/env python3
"""A ABA SISTEMA PARA DE CONTRADIZER A SI MESMA — 03/09/2026.

O DEFEITO ESTAVA NA FOTO, e é a pior espécie desta aba porque a linha se
contradiz DENTRO DE SI MESMA. Fotografado às 04:26 com o daemon dela vivo e dois
controles na mesa (um White no cabo, um Galactic Purple no rádio):

    o que a tela mostrava              o que a máquina dizia
    ─────────────────────────────────  ──────────────────────────────
    ✓  Pausado                  Não    o glifo é o `!` laranja do DESENHO
    ✓  Trocar de perfil …  Sem ver…    o glifo é o `✓` verde do DESENHO
    ✓  Ligar junto …      [chave on]   `is-enabled` nunca chegou ao pixel
       Perfil de Bateria  [Tudo ligado] o disco nunca chegou ao pixel
       Detalhes técnicos            —   a GTK sempre teve `systemctl status` ali

O VALOR estava certo em quatro deles — o pacote já o escrevia. Quem mentia era o
SELO ao lado, que nunca foi endereçado; e o próprio `?` desta aba diz por que
isso não é enfeite: *o selo carrega símbolo e cor ao mesmo tempo, para quem não
distingue verde de laranja ler o estado pelo desenho*. Um glifo congelado é a
leitura acessível dizendo o contrário da visual.

O QUE ESTA RÉGUA COBRA, e cada bloco é uma forma diferente de recair:

1. **o glifo de cada linha é DADO** — e é o `-g` que a camada do produto já
   devolvia e ninguém consumia;
2. **o interruptor e o botão aceso são CLASSE** — `NAO_CHEGA_NA_TELA` os
   segurava com uma nota que CADUCOU quando o piloto ganhou o alvo `classe`;
3. **o estado do serviço tem os QUATRO da matriz** — e não os dois que esta aba
   colapsava;
4. **o exame tem os DOIS achados condicionais da janela antiga** — e o de 7
   segundos NUNCA roda dentro do tique;
5. **as decisões 2, 3 e 10 dela**, de 03/09/2026.

AS MORDIDAS estão no docstring de cada teste, e todas foram executadas.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: A página que o PRODUTO renderiza — não a bancada. Uma régua que medisse o
#: `mockup/` daria verde sobre um endereço que a tela dela não tem, e é a
#: armadilha que o `docs/process/COMO-OLHAR-A-TELA.md` chama de "régua que
#: pergunta no lugar errado".
PAGINA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/09-sistema.html"

#: O SERIAL É SINTÉTICO E MASCARADO, e as duas coisas foram cobradas por um
#: portão: a primeira versão desta constante era um serial PLAUSÍVEL de 17
#: caracteres, e o `anonimato` reprovou —
#:
#:     ANONIMATO VIOLADO — SERIAL DE FÁBRICA real em arquivo versionado
#:
#: — porque ele acusa pela FORMA, sem consultar bancada nenhuma. Um serial de
#: fábrica identifica a unidade tão bem quanto um MAC. A máscara da casa é 6
#: caracteres públicos e o resto em `#` (`scripts/ensaios/cor_do_plastico.py`,
#: `mascarar_serial`), e o prefixo aqui é forjado: `Z` onde o padrão exige
#: dígito, para que nem por acaso ele case com a forma real. Dezessete
#: caracteres, que é o comprimento do de verdade — o teste da decisão 10 mede o
#: texto inteiro, e um número curto aqui deixaria a régua verde sobre um corte.
SERIAL_DE_MENTIRA = "ZZZ0ZZ###########"

#: O `state_full` de mentira. O MAC é da faixa sintética da casa.
ESTADO = {
    "active_profile": "meu_perfil",
    "paused": False,
    "rumble_policy": "balanceado",
    "window_detect_backend": "xlib",
    "window_detect_seeing": False,
    "window_detect_reason": "sem_foco_x",
    "controllers": [
        {"uniq": "aa:bb:cc:00:00:01", "connected": True, "transport": "usb",
         "player_slot": 1, "serial": SERIAL_DE_MENTIRA, "modelo": "White"},
        {"uniq": "aa:bb:cc:00:00:02", "connected": True, "transport": "bt",
         "player_slot": 2, "serial": None, "modelo": None},
    ],
}


class JanelaDeMentira:
    """O dublê de `DaemonActionsMixin` — e ele NÃO fala com o systemd.

    Sem ele, cada teste desta régua rodaria `systemctl --user` de verdade na
    máquina de quem a executa: o `_status_do_daemon` faz dois, o repouso do
    painel faz mais um, e o `autostart`/`reiniciar` fariam `enable` e `restart`.
    Uma régua que reinicia o daemon de quem a roda não é régua.
    """

    def __init__(self, status="online_systemd", texto="● unidade ativa", rc=0):
        self.status, self.texto, self.rc = status, texto, rc
        self.comandos: list[list[str]] = []

    def _daemon_status(self):
        return self.status

    def _systemctl_status_text(self, unit):
        return self.texto

    def _invoke_systemctl(self, args, capture=False, check=False):
        self.comandos.append(list(args))

        class R:
            returncode = self.rc
            stderr = "" if self.rc == 0 else "Failed to enable unit."

        return R()


@pytest.fixture
def a09(monkeypatch):
    from pacotes import a09_sistema as mod

    # O PERFIL DE BATERIA É GRAVADO NO DISCO DE MENTIRA, e não injetado: o
    # `conftest.py` desvia `HOME` e os quatro `XDG_*` para um lar que nasce sem
    # `maquina.json`. Gravando pelo caminho do PRODUTO, a régua atravessa o
    # mesmo disco que a mão dela atravessa.
    from hefesto_dualsense4unix.app.actions.config.secao_orcamento import (
        PERFIL_BATERIA_LONGA,
        TETO_POR_PERFIL,
    )
    from hefesto_dualsense4unix.utils.maquina import gravar_maquina

    gravar_maquina({"orcamento": {"teto": TETO_POR_PERFIL[PERFIL_BATERIA_LONGA]}})

    mod._JANELA_ANTIGA[:] = [JanelaDeMentira()]
    # `is-enabled` NÃO PODE SAIR DA MÁQUINA DE QUEM RODA: `_autostart` chama
    # `subprocess.run` direto, fora do mixin.
    monkeypatch.setattr(mod, "_autostart", lambda: "enabled")
    mod._LENTO.clear()
    mod._LENTO_EM_VOO[0] = False
    mod._PRONTUARIO.clear()
    mod._PRONTUARIO_EM_VOO[0] = False
    mod._PAINEL[0] = None
    yield mod
    mod._JANELA_ANTIGA.clear()
    mod._LENTO.clear()
    mod._PRONTUARIO.clear()
    mod._PAINEL[0] = None


@pytest.fixture
def ctx():
    import pacotes

    return pacotes.Contexto(
        state=ESTADO, mesa=[], conectados=list(ESTADO["controllers"]), estados={})


def _pagina() -> str:
    return PAGINA.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. O GLIFO DE CADA LINHA É DADO
# ---------------------------------------------------------------------------
#: As seis linhas de estado que o pacote pinta. Saem do contrato do produto, e
#: não digitadas: o que se lista aqui é só quais delas o `est()` monta.
LINHAS = ("hefesto-estado", "hefesto-pausa", "hefesto-troca-de-perfil",
          "hefesto-ambiente", "bateria-impoe", "bateria-vale-para")


@pytest.mark.parametrize("linha", LINHAS)
def test_o_glifo_de_cada_linha_tem_endereco_na_pagina(linha):
    """O `<span class="g">` de cada linha de estado leva `data-campo="…-g"`.

    **A MORDIDA:** tire o `gc` da `est()` em `interface/aba09.py`, regere e
    publique os endereços. Executada em 03/09/2026:

        AssertionError: o glifo de `hefesto-estado` não tem endereço na página
        publicada — ele volta a ser o literal do desenho, e a linha passa a
        mostrar um selo que não tem como discordar de nada porque ninguém o
        escreve.
    """
    assert f'data-campo="{linha}-g"' in _pagina(), (
        f"o glifo de `{linha}` não tem endereço na página publicada — ele volta "
        f"a ser o literal do desenho, e a linha passa a mostrar um selo que não "
        f"tem como discordar de nada porque ninguém o escreve.")


@pytest.mark.parametrize("linha", LINHAS)
def test_o_pacote_emite_o_glifo_de_cada_linha(a09, ctx, linha):
    """E o pacote escreve nele. Endereço sem escritor é pior que endereço nenhum.

    **A MORDIDA:** apague a linha `fora[f"{chave}-g"] = …` do achatamento em
    `pacote()`. Executada:

        AssertionError: o pacote não emite `hefesto-estado-g`. O endereço existe
        na página e ninguém escreve nele — a régua da identidade conta isso como
        endereço morto, e a tela continua com o glifo do desenho.
    """
    p = a09.pacote(ctx)
    assert f"{linha}-g" in p, (
        f"o pacote não emite `{linha}-g`. O endereço existe na página e ninguém "
        f"escreve nele — a régua da identidade conta isso como endereço morto, e "
        f"a tela continua com o glifo do desenho.")
    assert p[f"{linha}-g"], f"`{linha}-g` saiu vazio, e vazio apaga o glifo."


def test_o_glifo_da_pausa_desmente_o_desenho(a09, ctx):
    """Com `paused: False`, o glifo é `✓` — e o DESENHO crava `!`.

    É o teste que prende o defeito da foto de 04:26: valor certo, selo do
    mockup. Ele mede as duas metades ao mesmo tempo — o que o pacote diz e o
    que a página traz cravado —, porque só as duas juntas provam que a pintura
    é necessária.

    **A MORDIDA:** faça `fora[f"{chave}-g"] = ""` e o teste reprova dizendo que
    o glifo saiu vazio; troque a emissão por `v.get("cls")` e ele reprova
    dizendo que `ok` não é glifo nenhum.
    """
    p = a09.pacote(ctx)
    assert p["hefesto-pausa"] == "Não"
    assert p["hefesto-pausa-g"] == "✓", (
        "com o daemon NÃO pausado o selo é o de estado bom. O que o pacote "
        f"emitiu foi {p['hefesto-pausa-g']!r}.")
    cravado = re.search(
        r'data-campo="hefesto-pausa-g">(.)</span>', _pagina())
    assert cravado and cravado.group(1) == "!", (
        "o desenho deixou de cravar `!` no glifo da pausa. Este teste existe "
        "porque os dois DISCORDAM: sem pintura, a tela mostra o `!` do mockup "
        "ao lado do valor `Não`.")


# ---------------------------------------------------------------------------
# 2. O INTERRUPTOR E O BOTÃO ACESO SÃO CLASSE
# ---------------------------------------------------------------------------
def test_o_interruptor_do_autostart_e_dado(a09, ctx, monkeypatch):
    """A chave "Ligar junto com o computador" recebe o que `is-enabled` responde.

    ATÉ 03/09/2026 ELA ERA UM LITERAL DE GERAÇÃO (`AUTOSTART_LIGADO = True`), e
    `NAO_CHEGA_NA_TELA` a segurava dizendo que *"a pintura não tem alvo de
    classe"*. O piloto ganhou o alvo `classe` em 02/09; a nota tinha caducado.

    **A MORDIDA:** tire `data-hef-alvo="classe"` do `<span class="chave">` no
    gerador. Executada:

        AssertionError: a chave do autostart não declara o alvo `classe` — sem
        ele o piloto escreveria o texto `True` DENTRO do interruptor.
    """
    pag = _pagina()
    assert 'data-campo="hefesto-autostart" data-hef-alvo="classe"' in pag, (
        "a chave do autostart não declara o alvo `classe` — sem ele o piloto "
        "escreveria o texto `True` DENTRO do interruptor.")

    monkeypatch.setattr(a09, "_autostart", lambda: "enabled")
    a09._LENTO.clear()
    assert a09.pacote(ctx)["hefesto-autostart"] is True

    monkeypatch.setattr(a09, "_autostart", lambda: "disabled")
    a09._LENTO.clear()
    p = a09.pacote(ctx)
    assert p["hefesto-autostart"] is False, (
        "com `is-enabled` respondendo `disabled` a chave tem de APAGAR. Hoje "
        "ela acerta por coincidência nesta máquina, e é isso que este teste "
        "existe para não deixar voltar.")
    assert p["hefesto-autostart-g"] == "○", (
        "o glifo da linha do autostart tem de acompanhar a chave — os dois "
        "saíam de `AUTOSTART_LIGADO` no gerador justamente para não poderem "
        "discordar, e agora saem os dois da mesma leitura.")

    # `None` NÃO É `False`: "não consegui perguntar ao systemd" não é "desligado".
    monkeypatch.setattr(a09, "_autostart", lambda: None)
    a09._LENTO.clear()
    p = a09.pacote(ctx)
    assert p["hefesto-autostart"] is None
    assert p["hefesto-autostart-g"] not in ("✓", "○"), (
        "sem leitura, o glifo não pode afirmar nem ligado nem desligado.")


def test_o_aceso_do_perfil_de_bateria_e_dado(a09, ctx):
    """Qual dos três botões acende sai do DISCO, não do desenho.

    O CASO DEMONSTRÁVEL, e é o que a medição de 02/09 já tinha escrito: o gesto
    `perfil-da-mesa` GRAVA em disco e o botão NÃO se move. Ela clica "Bateria
    longa", o teto muda, e a tela continua dizendo "Tudo ligado".

    O `data-hef-quando` DE CADA BOTÃO TEM DE SER O `data-v` DELE — são as duas
    pontas do mesmo botão (o que o clique manda e o que a pintura compara), e
    escritas separadas sem régua elas divergem no dia em que alguém renomear um
    perfil no produto.

    **A MORDIDA:** troque `data-hef-quando="{p}"` por `data-hef-quando="on"` no
    `_botoes_bateria`. Executada:

        AssertionError: o botão `tudo_ligado` compara com 'on' e o clique dele
        manda 'tudo_ligado' — as duas pontas do mesmo botão discordam.
    """
    botoes = re.findall(
        r'<button class="(?:on)?" data-gesto="perfil-da-mesa" data-v="([^"]+)"'
        r' data-campo="bateria-perfil" data-hef-alvo="classe"'
        r' data-hef-classe="on" data-hef-quando="([^"]+)"', _pagina())
    assert len(botoes) == 3, (
        f"achei {len(botoes)} botões endereçados no Perfil de Bateria e o "
        "produto declara três. Sem o endereço, o aceso continua sendo o do "
        "desenho.")
    for v, quando in botoes:
        assert v == quando, (
            f"o botão `{v}` compara com {quando!r} e o clique dele manda {v!r} "
            "— as duas pontas do mesmo botão discordam.")

    from hefesto_dualsense4unix.app.actions.config.secao_orcamento import (
        PERFIL_BATERIA_LONGA,
    )

    # A `a09` já gravou `bateria_longa` no disco de mentira. O desenho crava
    # `tudo_ligado` (`PERFIS[0]`) — logo os dois DISCORDAM, que é o ponto.
    assert a09.pacote(ctx)["bateria-perfil"] == PERFIL_BATERIA_LONGA, (
        "o pacote tem de emitir a CHAVE do perfil gravado em disco. Emitindo o "
        "rótulo, ou nada, o botão aceso volta a ser o do mockup.")


# ---------------------------------------------------------------------------
# 3. O ESTADO DO SERVIÇO TEM OS QUATRO DA MATRIZ
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("matriz", "esperado"),
    [("online_systemd", "online_systemd"), ("online_avulso", "online_avulso"),
     ("iniciando", "iniciando")])
def test_o_estado_do_servico_vem_da_matriz_de_tres_fontes(a09, matriz, esperado):
    """Os quatro estados chegam à tela — não os dois que esta aba colapsava.

    Com `online_avulso`, a camada de tela escreve *"Ligado, em modo
    improvisado"* em laranja; a versão de dois estados escrevia "Ligado" com
    selo verde e a dica *"Se travar, ele volta sozinho"*, que é FALSA nesse
    estado.

    **A MORDIDA:** devolva `"online_systemd" if state else "offline"` em
    `_status_do_daemon`. Executada:

        AssertionError: a matriz respondeu 'online_avulso' e a aba disse
        'online_systemd' — os dois estados que a camada de tela sabe escrever e
        nunca recebe.
    """
    a09._JANELA_ANTIGA[:] = [JanelaDeMentira(status=matriz)]
    assert a09._status_do_daemon(ESTADO) == esperado, (
        f"a matriz respondeu {matriz!r} e a aba disse "
        f"{a09._status_do_daemon(ESTADO)!r} — os dois estados que a camada de "
        "tela sabe escrever e nunca recebe.")


def test_o_daemon_que_responde_nao_e_chamado_de_desligado(a09):
    """`offline` da matriz + `state_full` vivo = `online_avulso`, e não `offline`.

    O desempate é do `state`: o daemon RESPONDEU, logo está de pé. Chamá-lo de
    `online_systemd` afirmaria uma unit que ninguém viu; chamá-lo de `offline`
    faria a tela dizer "Desligado" sobre um daemon que acabou de publicar o
    estado inteiro.
    """
    a09._JANELA_ANTIGA[:] = [JanelaDeMentira(status="offline")]
    assert a09._status_do_daemon(ESTADO) == "online_avulso"
    assert a09._status_do_daemon(None) == "offline"


# ---------------------------------------------------------------------------
# 4. O EXAME, E OS SETE SEGUNDOS QUE NÃO PODEM ENTRAR NO TIQUE
# ---------------------------------------------------------------------------
def test_o_exame_ganha_o_vigia_do_steam_input(a09, ctx, monkeypatch):
    """O achado condicional de 2,8 ms entra na lista, ao lado do `storm_report`.

    Ele tinha UM chamador em toda a árvore e era a GTK — por isso o exame desta
    tela era 6/8 do exame da janela antiga.

    **A MORDIDA:** apague o bloco do `vigia` em `_achados`. Executada:

        AssertionError: o vigia do Steam Input não chegou ao exame — a lista
        tem 6 linhas e a janela antiga mostraria 7.
    """
    monkeypatch.setattr(a09._daemon, "medir_guarda_do_steam_input",
                        lambda: ("WARN", "o vigia do Steam Input está morto"))
    frases = [f for _, f in (a09._achados(ESTADO, pode_perguntar=False) or [])]
    assert "o vigia do Steam Input está morto" in frases, (
        f"o vigia do Steam Input não chegou ao exame — a lista tem {len(frases)} "
        "linhas e a janela antiga mostraria uma a mais.")


def test_o_prontuario_de_sete_segundos_nunca_roda_no_tique(a09, monkeypatch):
    """A varredura de 7,1 s NÃO acontece na leitura síncrona da faixa lenta.

    MEDIDO em 03/09/2026, com `time.monotonic` em volta da chamada:
    `medir_prontuario_dos_jogos` leva **7.148,8 ms** na máquina dela — e o
    comentário que a chama na janela antiga diz *"leva ~1 s"*. Ela roda dentro
    de um worker lá; aqui a faixa lenta roda no laço do GTK. Com a pergunta
    solta, o primeiro tique da janela custou **13.676 ms** e a aba pintou ZERO
    valores em oito segundos.

    **A MORDIDA:** troque `_prontuario(pode_perguntar)` por `_prontuario()` em
    `_achados`. Executada:

        AssertionError: a varredura de 7 s foi disparada pela leitura SÍNCRONA
        da faixa lenta — a que roda dentro do laço do GTK.
    """
    chamou: list[int] = []

    def _lenta():
        chamou.append(1)
        return None

    monkeypatch.setattr(a09._daemon, "medir_prontuario_dos_jogos", _lenta)
    a09._achados(ESTADO, pode_perguntar=False)
    assert not chamou, (
        "a varredura de 7 s foi disparada pela leitura SÍNCRONA da faixa lenta "
        "— a que roda dentro do laço do GTK.")

    # E a releitura, que já é thread, PODE perguntar — senão o achado nunca
    # chegaria à tela e o exame ficaria em 7/8 para sempre.
    a09._achados(ESTADO, pode_perguntar=True)
    for _ in range(200):
        if not a09._PRONTUARIO_EM_VOO[0]:
            break
        import time as _t

        _t.sleep(0.01)
    assert chamou, ("a releitura tem de perguntar — sem isso o prontuário nunca "
                    "chega ao exame e a linha some para sempre.")


def test_a_primeira_leitura_e_sincrona_e_a_releitura_e_thread(a09, ctx):
    """A primeira leva o valor; as seguintes não travam o laço do GTK.

    As duas metades são requisito: síncrona na primeira porque a PRIMEIRA
    pintura tem de ser verdadeira (e porque `_LENTO` é o ponto de injeção das
    réguas), em thread nas releituras porque o disco disputado com o prontuário
    levou uma volta a **1.840 ms** — a janela dela travada por quase dois
    segundos.

    **A MORDIDA:** faça a primeira também disparar a thread e este teste reprova
    dizendo que o primeiro valor chegou vazio.
    """
    valor = a09._faixa_lenta(ESTADO)
    assert len(valor) == 5 and valor[0] is not None, (
        "a primeira leitura da faixa lenta chegou vazia — a primeira pintura "
        "escreveria travessão em cinco lugares e a tela piscaria de 'não sei' "
        "para o valor.")
    a09._LENTO["quando"] = 0.0  # vencida
    a09._faixa_lenta(ESTADO)
    assert a09._LENTO_EM_VOO[0] or a09._LENTO["quando"] != 0.0, (
        "a releitura não saiu do laço do GTK.")


# ---------------------------------------------------------------------------
# 5. AS DECISÕES DELA — 03/09/2026
# ---------------------------------------------------------------------------
def test_decisao_2_o_nome_curto_na_tela_e_o_inteiro_na_dica(a09):
    """*"o CURTO na tela (`CosmicTerm`), o INTEIRO na dica"*.

    O nome é o da janela que está na frente, e é o mesmo dado que a GTK já
    mostra: `descrever_deteccao_de_janela` escreve *"funcionando (na frente
    agora: com.system76.CosmicTerm)"*. Nesta tela ele não aparecia nem curto nem
    inteiro.

    **A MORDIDA:** faça `_curto` devolver a classe inteira. Executada:

        AssertionError: a tela mostra 'com.system76.CosmicTerm' e ela pediu o
        nome CURTO.
    """
    vendo = {**ESTADO, "window_detect_seeing": True,
             "window_detect_current_class": "com.system76.CosmicTerm"}
    saida = a09._com_quem_esta_na_frente("Ligado", vendo)
    assert saida is not None
    assert ">CosmicTerm</span>" in saida, (
        f"a tela mostra o nome inteiro e ela pediu o CURTO: {saida!r}")
    assert 'title="com.system76.CosmicTerm"' in saida, (
        f"o nome INTEIRO tem de estar na dica: {saida!r}")

    # Uma classe SEM ponto volta inteira — é o caso medido na mesa dela.
    assert a09._curto("Hefesto-Dualsense4Unix") == "Hefesto-Dualsense4Unix"


def test_o_nome_da_janela_so_aparece_com_o_detector_vendo(a09):
    """`window_detect_last_class` é STICKY, e fora do `vendo` ela é de horas atrás.

    MEDIDO na mesa dela em 03/09/2026: `seeing=False`, `current=unknown`,
    `last=Hefesto-Dualsense4Unix`, `useful_age_sec=5861` — uma hora e meia. Ler
    o `last` fora do ramo `vendo` faria a linha dizer "Sem ver a janela agora ·
    Hefesto" e nomear uma janela que não está na frente há uma hora e meia.

    **A MORDIDA:** tire a guarda do `window_detect_seeing` em
    `_quem_esta_na_frente`. Executada:

        AssertionError: a linha nomeou uma janela com o detector CEGO.
    """
    cego = {**ESTADO, "window_detect_seeing": False,
            "window_detect_last_class": "Hefesto-Dualsense4Unix"}
    assert a09._quem_esta_na_frente(cego) == "", (
        "a linha nomeou uma janela com o detector CEGO — e o `last_class` não "
        "decai, então esse nome é de horas atrás.")
    assert a09._com_quem_esta_na_frente("Sem ver a janela agora", cego) is None


def test_decisao_3_o_aviso_do_process_name_nao_aparece(a09):
    """*"Aviso do `process_name`: Não deve aparecer."* Sai.

    O aviso é o `profile_process_name_aviso` da janela antiga
    (`gui/main.glade:2603`, com `profiles_actions.texto_do_processo_que_nao_casa`).
    Ele NÃO tem par no HTML, e a decisão dela é que não passe a ter. A régua
    existe porque a dívida está registrada no inventário como
    `FALTA_NO_HTML` — quem fechar a lista sem ler esta decisão o traria de volta
    achando que está fechando um buraco.
    """
    pag = _pagina()
    for palavra in ("process_name", "texto_do_processo_que_nao_casa",
                    "nome do processo"):
        assert palavra not in pag, (
            f"a página traz {palavra!r}. A decisão 3 dela, de 03/09/2026, é que "
            "o aviso do `process_name` NÃO deve aparecer.")


def test_decisao_10_o_serial_de_fabrica_aparece_inteiro(a09, ctx):
    """*"Serial de fábrica: inteiro, e SÓ na aba Sistema (a de diagnóstico)."*

    ELE APARECE PELA PRIMEIRA VEZ EM QUALQUER TELA DO PRODUTO. O daemon o
    publica desde 02/09 (ROTA-A) e nem esta aba nem a GTK o mostravam.

    O LUGAR É O PAINEL "Detalhes técnicos", que é a caixa de diagnóstico desta
    aba — e ele entra POR ÚLTIMO porque o painel leva `data-hef-rolar="fim"`:
    com a identidade no começo, a foto de 04:41 mostrou seis linhas de journal e
    nenhuma da identidade.

    **A MORDIDA:** corte o serial em oito caracteres. Executada:

        AssertionError: o serial saiu cortado, e ela pediu INTEIRO.
    """
    texto = a09.pacote(ctx)[a09.REGISTRO]
    assert a09.ROTULO_DA_IDENTIDADE in texto
    assert SERIAL_DE_MENTIRA in texto, (
        "o serial saiu cortado, e ela pediu INTEIRO.")
    # E ele é o FIM do painel, que é o pedaço que a tela mostra sem rolar.
    cauda = "\n".join(texto.splitlines()[-3:])
    assert SERIAL_DE_MENTIRA in cauda, (
        "o serial está no painel e fora da vista: o painel rola para o FIM, e "
        "a identidade tem de ser o fim.")
    # O controle SEM leitura não inventa serial nenhum.
    assert a09.SEM_SERIAL_LIDO in texto, (
        "o controle do rádio não deu serial, e a linha dele tem de dizer isso "
        "em vez de mostrar um travessão que lê como defeito.")


def test_o_serial_nao_vaza_para_as_outras_nove_paginas():
    """*"SÓ na aba Sistema"* — e o resto do produto continua sem mostrá-lo.

    A régua olha os PACOTES, não as páginas: o serial é dado do `state_full`, e
    quem poderia levá-lo à tela é quem escreve nela.
    """
    pasta = RAIZ / "src/hefesto_dualsense4unix/interface/pacotes"
    culpados = [
        p.name for p in sorted(pasta.glob("a*.py"))
        if p.name != "a09_sistema.py" and '"serial"' in p.read_text(encoding="utf-8")
    ]
    assert not culpados, (
        f"{culpados} leem o serial de fábrica. A decisão 10 dela o restringe à "
        "aba Sistema, que é a de diagnóstico.")


# ---------------------------------------------------------------------------
# 6. OS DOIS GESTOS QUE GANHARAM DONO, E A TRAVA QUE JÁ EXISTIA
# ---------------------------------------------------------------------------
def test_o_autostart_manda_enable_ou_disable_conforme_o_lido(a09, ctx, monkeypatch):
    """O interruptor morto passa a mexer no systemd — pelo caminho da janela antiga.

    Ele era o pior tipo de botão morto: PARECE um interruptor de dois estados, o
    clique não muda nem a aparência (não há `<script>` na página), e quem clica
    não tem como saber que não pegou.

    **A MORDIDA:** apague o `@gesto("09-sistema.html", "autostart")`. Executada:

        AssertionError: `autostart` voltou a não ter dono — o clique cai em
        `[gesto sem dono]`, no stdout do processo.
    """
    import pacotes

    acao = pacotes.gesto_da_pagina("09-sistema.html", "autostart")
    assert acao is not None, (
        "`autostart` voltou a não ter dono — o clique cai em `[gesto sem dono]`, "
        "no stdout do processo.")

    janela = JanelaDeMentira()
    a09._JANELA_ANTIGA[:] = [janela]
    monkeypatch.setattr(a09, "_autostart", lambda: "enabled")
    acao(ctx, {}, None)
    assert janela.comandos == [["disable", a09._unidade()]], (
        f"com o autostart LIGADO o clique tem de desligar. Mandou: "
        f"{janela.comandos}")

    janela.comandos.clear()
    monkeypatch.setattr(a09, "_autostart", lambda: "disabled")
    acao(ctx, {}, None)
    assert janela.comandos == [["enable", a09._unidade()]]


def test_o_autostart_recusa_quando_nao_sabe_o_estado(a09, ctx, monkeypatch):
    """Sem `is-enabled` legível, ele NÃO adivinha — recusa dizendo.

    Um `enable` disparado sobre "não sei" tem 50% de chance de desfazer a
    escolha dela sem que ninguém tenha pedido.
    """
    janela = JanelaDeMentira()
    a09._JANELA_ANTIGA[:] = [janela]
    monkeypatch.setattr(a09, "_autostart", lambda: None)
    acao = __import__("pacotes").gesto_da_pagina("09-sistema.html", "autostart")
    with pytest.raises(RuntimeError):
        acao(ctx, {}, None)
    assert not janela.comandos, "recusou e mandou o comando assim mesmo."


def test_o_reiniciar_faz_reset_failed_antes(a09, ctx):
    """`reset-failed` + `restart`, nesta ordem — é a sequência da janela antiga.

    Sem o `reset-failed`, o `StartLimitBurst` do systemd recusa o restart de
    quem clicou duas vezes, e a tela receberia "não consegui" sobre uma unit
    perfeitamente sã.

    **A MORDIDA:** tire o ramo do `reset-failed` em `_systemctl`. Executada:

        AssertionError: o restart foi sem `reset-failed` — dois cliques
        seguidos passam a falhar por limite de partida.
    """
    janela = JanelaDeMentira()
    a09._JANELA_ANTIGA[:] = [janela]
    acao = __import__("pacotes").gesto_da_pagina("09-sistema.html", "reiniciar")
    acao(ctx, {}, None)
    assert janela.comandos == [["reset-failed", a09._unidade()],
                               ["restart", a09._unidade()]], (
        f"o restart foi sem `reset-failed`: {janela.comandos}")


def test_o_systemctl_que_falha_recusa_dizendo(a09, ctx):
    """`rc != 0` vira `RuntimeError` com o `stderr` junto — nunca silêncio.

    Um gesto que engolisse o `rc != 0` deixaria o interruptor parado sem uma
    palavra, que é o silêncio que este arquivo inteiro existe para acabar.
    """
    a09._JANELA_ANTIGA[:] = [JanelaDeMentira(rc=1)]
    acao = __import__("pacotes").gesto_da_pagina("09-sistema.html", "reiniciar")
    with pytest.raises(RuntimeError) as erro:
        acao(ctx, {}, None)
    assert "Failed to enable unit." in str(erro.value)


def test_o_retomar_recusa_quando_nao_ha_pausa(a09, ctx):
    """"Retomar" verde e clicável sem pausa é um no-op que se apresenta como ação.

    A conta é da camada do produto — `aba_sistema.travas()` —, que já estava
    escrita e ligada até a penúltima camada: ela cobre `retomar`, `desligar`,
    `reiniciar`, `ver-plugins` e `ver-detalhes`, com o motivo pronto para o
    tooltip. Faltava alguém chamá-la.

    **A MORDIDA:** apague a checagem do `_trava` em `retomar`. Executada:

        Failed: DID NOT RAISE <class 'RuntimeError'> — o clique mandou
        `daemon.resume` a um daemon que não está pausado.
    """
    class PonteDeMentira:
        def __init__(self):
            self.chamou = []

        def chamar(self, metodo, **kw):
            self.chamou.append(metodo)
            return True

    p = PonteDeMentira()
    acao = __import__("pacotes").gesto_da_pagina("09-sistema.html", "retomar")
    with pytest.raises(RuntimeError) as erro:
        acao(ctx, {}, p)
    assert "não está pausado" in str(erro.value)
    assert not p.chamou, "recusou e mandou `daemon.resume` assim mesmo."

    import pacotes

    pausado = pacotes.Contexto(state={**ESTADO, "paused": True}, mesa=[],
                               conectados=list(ESTADO["controllers"]), estados={})
    a09._LENTO.clear()
    acao(pausado, {}, p)
    assert p.chamou == ["daemon.resume"], (
        "com a pausa ATIVA o botão tem de agir — a trava não pode virar uma "
        "recusa permanente.")


def test_a_classe_da_linha_esta_declarada_como_sem_alvo(a09, ctx):
    """O `-cls` de cada linha é EMITIDO e não tem onde pousar — declarado, não escondido.

    É a dívida que sobra desta frente e ela é de MECANISMO: o alvo `classe` do
    piloto acende UMA classe por elemento, e a linha de estado tem três
    exclusivas no mesmo `<div>`. Na tela dela isso é a linha "Trocar de perfil ao
    abrir o jogo" mostrando **Sem ver a janela agora** em VERDE.

    A DECLARAÇÃO TEM DE CASAR COM O QUE SE EMITE, nos dois sentidos: uma lista
    que envelhecesse viraria paisagem, e paisagem ninguém lê.
    """
    p = a09.pacote(ctx)
    for endereco, razao in a09.SEM_ALVO_NA_PAGINA.items():
        assert razao.strip(), f"`{endereco}` está declarado sem razão"
        assert endereco in p, (
            f"`{endereco}` está declarado como emitido-sem-alvo e o pacote não "
            "o emite mais. Se ele saiu, tire-o da declaração.")
        assert f'data-campo="{endereco}"' not in _pagina(), (
            f"`{endereco}` ganhou endereço na página e continua declarado como "
            "sem alvo — a dívida fechou e a declaração ficou.")


def test_os_que_ficam_sem_motor_estao_declarados_com_a_razao(a09):
    """Os que ficam de fora ficam ESCRITOS — e a razão MUDOU em 03/09/2026.

    Até hoje a lista se chamava `SEM_CONFIRMACAO` e a razão era *"não há
    primitiva de confirmação"*. **Esse fato caiu**: ela escolheu os dois cliques
    e eles existem (`a09_sistema.CONFIRMA`). O que segura os que sobram é de
    MOTOR — o ato mora dentro de um handler da janela GTK.

    A RÉGUA COBRA NOS DOIS SENTIDOS, e é o que a impede de virar paisagem: quem
    está em `SEM_MOTOR` não pode ter dono, e todo nome ali tem de ser um dos
    `DESTRUTIVOS` — uma linha órfã seria uma declaração sobre um botão que não
    existe mais.

    A MORDIDA: registre `@gesto("09-sistema.html", "procurar-camadas")` sem
    tirá-lo do `SEM_MOTOR`, e isto reprova nomeando o gesto.
    """
    import pacotes

    com_dono = {g for (pg, g) in pacotes.GESTOS if pg == a09.PAGINA}
    assert set(a09.SEM_MOTOR) <= set(a09.DESTRUTIVOS), (
        "há nome em `SEM_MOTOR` que não é um dos cinco destrutivos desta "
        f"página: {sorted(set(a09.SEM_MOTOR) - set(a09.DESTRUTIVOS))}")
    for nome, razao in a09.SEM_MOTOR.items():
        assert nome not in com_dono, (
            f"`{nome}` ganhou dono e continua declarado como sem motor. "
            "Se o ato saiu do handler da janela velha, tire-o desta lista.")
        assert len(razao) > 20, f"`{nome}` está declarado sem razão escrita."
    # E A OUTRA METADE: os destrutivos que NÃO estão declarados têm de ter dono.
    # Sem esta linha, apagar um do `SEM_MOTOR` e não ligá-lo passaria verde.
    for nome in a09.DESTRUTIVOS:
        if nome not in a09.SEM_MOTOR:
            assert nome in com_dono, (
                f"`{nome}` saiu da declaração e continua sem dono — o botão "
                "voltou a ser morto e nenhuma lista o diz.")
    assert len(com_dono) >= a09.PISO_DA_ABA
