#!/usr/bin/env python3
"""A ABA SISTEMA PARA DE CONTRADIZER A SI MESMA — 03/09/2026."""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/09-sistema.html"

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
    """O dublê de `DaemonActionsMixin` — e ele NÃO fala com o systemd."""

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

    from hefesto_dualsense4unix.app.actions.config.secao_orcamento import (
        PERFIL_BATERIA_LONGA,
        TETO_POR_PERFIL,
    )
    from hefesto_dualsense4unix.utils.maquina import gravar_maquina

    gravar_maquina({"orcamento": {"teto": TETO_POR_PERFIL[PERFIL_BATERIA_LONGA]}})

    mod._JANELA_ANTIGA[:] = [JanelaDeMentira()]
    monkeypatch.setattr(mod, "_autostart", lambda: "enabled")
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    reposicoes: list[None] = []

    def _repor_de_mentira() -> rl.Recibo:
        reposicoes.append(None)
        return rl.Recibo()

    monkeypatch.setattr(rl, "repor", _repor_de_mentira)
    monkeypatch.setattr(mod, "reposicoes", reposicoes, raising=False)
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


def _pilulas(html: str) -> list[tuple[str, str]]:
    """`(glifo, palavra)` de cada pílula do HTML, na ordem."""
    return re.findall(r'<span class="selo [a-z]+"><span class="sg">([^<]*)</span>([^<]*)</span>',
                      html)


def test_o_status_tem_endereco_na_pagina():
    """A lista do Status leva `data-campo` com o alvo `html` na página publicada."""
    assert re.search(r'data-campo="status-lista" data-hef-alvo="html"', _pagina()), (
        "o Status não tem endereço na página publicada — as quatro linhas voltam "
        "a ser o literal do desenho, e a pílula não tem como discordar de nada.")


def test_o_pacote_emite_o_glifo_de_cada_linha_do_status(a09, ctx):
    """E o pacote escreve as quatro, cada uma com glifo E palavra.

    **A MORDIDA:** esvazie o `g` em `aba_sistema._linha_de_status`. Reprova
    dizendo qual pílula saiu sem glifo.
    """
    pilulas = _pilulas(a09.pacote(ctx)[a09.CAMPO_DO_STATUS])
    assert len(pilulas) == 4, pilulas
    for glifo, palavra in pilulas:
        assert glifo.strip() and palavra.strip(), (
            f"a pílula {palavra!r} saiu sem glifo — quem não distingue verde de "
            "laranja perde a leitura do estado.")


def test_o_glifo_da_pausa_desmente_o_desenho(a09, ctx):
    """Com a pausa ATIVA o Serviço diz `! PAUSADO` — e o DESENHO crava `✓ LIGADO`."""
    import pacotes

    pausado = pacotes.Contexto(state={**ESTADO, "paused": True}, mesa=[],
                               conectados=list(ESTADO["controllers"]), estados={})
    servico = _pilulas(a09.pacote(pausado)[a09.CAMPO_DO_STATUS])[0]
    assert servico == ("!", "PAUSADO"), servico
    cravado = _pilulas(_pagina())[0]
    assert cravado == ("✓", "LIGADO"), (
        "o desenho deixou de cravar `✓ LIGADO` no Serviço. Este teste existe "
        "porque os dois DISCORDAM: sem pintura, a tela mostra o LIGADO do mockup "
        "com o serviço pausado.")


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

    monkeypatch.setattr(a09, "_autostart", lambda: None)
    a09._LENTO.clear()
    p = a09.pacote(ctx)
    assert p["hefesto-autostart"] is None


def test_o_aceso_do_perfil_de_bateria_e_dado(a09, ctx):
    """Qual dos três botões acende sai do DISCO, não do desenho."""
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

    assert a09.pacote(ctx)["bateria-perfil"] == PERFIL_BATERIA_LONGA, (
        "o pacote tem de emitir a CHAVE do perfil gravado em disco. Emitindo o "
        "rótulo, ou nada, o botão aceso volta a ser o do mockup.")


@pytest.mark.parametrize(
    ("matriz", "esperado"),
    [("online_systemd", "online_systemd"), ("online_avulso", "online_avulso"),
     ("iniciando", "iniciando")])
def test_o_estado_do_servico_vem_da_matriz_de_tres_fontes(a09, matriz, esperado):
    """Os quatro estados chegam à tela — não os dois que esta aba colapsava."""
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


def test_o_exame_ganha_o_vigia_do_steam_input(a09, ctx, monkeypatch):
    """O achado condicional de 2,8 ms entra na lista, ao lado do `storm_report`."""
    monkeypatch.setattr(a09._daemon, "medir_guarda_do_steam_input",
                        lambda: ("WARN", "o vigia do Steam Input está morto"))
    frases = [f for _, f in (a09._achados(ESTADO, pode_perguntar=False) or [])]
    assert "o vigia do Steam Input está morto" in frases, (
        f"o vigia do Steam Input não chegou ao exame — a lista tem {len(frases)} "
        "linhas e a janela antiga mostraria uma a mais.")


def test_o_prontuario_de_sete_segundos_nunca_roda_no_tique(a09, monkeypatch):
    """A varredura de 7,1 s NÃO acontece na leitura síncrona da faixa lenta."""
    from hefesto_dualsense4unix.integrations import prontuario_dos_jogos

    chamou: list[dict] = []

    def _censo(*args, **kw):
        chamou.append(kw)
        return None

    monkeypatch.setattr(prontuario_dos_jogos, "levantar_censo", _censo)
    a09._achados(ESTADO, pode_perguntar=False)
    assert not chamou, (
        "a varredura de 7 s foi disparada pela leitura SÍNCRONA da faixa lenta "
        "— a que roda dentro do laço do GTK.")

    a09._achados(ESTADO, pode_perguntar=True)
    for _ in range(200):
        if not a09._PRONTUARIO_EM_VOO[0]:
            break
        import time as _t

        _t.sleep(0.01)
    assert chamou, ("a releitura tem de perguntar — sem isso o prontuário nunca "
                    "chega ao exame e a linha some para sempre.")
    assert chamou[0].get("examinar") is False, (  # (noqa-acento) nome do parâmetro
        "a releitura voltou a varrer os executáveis de todo jogo instalado. "
        f"Ela pediu o censo com {chamou[0]!r}, e o `examinar=True` é o que fez o "
        "tique da 09 custar 1.329 ms num teto de 100 — treze vezes o teto, com "
        "a mesa parada. Esta tela lê UM campo do censo, e ele não depende de "
        "ler executável nenhum (`prontuario_dos_jogos.py:429`).")


def test_a_primeira_leitura_e_sincrona_e_a_releitura_e_thread(a09, ctx):
    """A primeira leva o valor; as seguintes não travam o laço do GTK."""
    valor = a09._faixa_lenta(ESTADO)
    assert len(valor) == 5 and valor[0] is not None, (
        "a primeira leitura da faixa lenta chegou vazia — a primeira pintura "
        "escreveria travessão em cinco lugares e a tela piscaria de 'não sei' "
        "para o valor.")
    a09._LENTO["quando"] = 0.0
    a09._faixa_lenta(ESTADO)
    assert a09._LENTO_EM_VOO[0] or a09._LENTO["quando"] != 0.0, (
        "a releitura não saiu do laço do GTK.")


def test_decisao_2_o_nome_curto_na_tela_e_o_inteiro_na_dica(a09):
    """*"o CURTO na tela (`CosmicTerm`), o INTEIRO na dica"*."""
    vendo = {**ESTADO, "window_detect_seeing": True,
             "window_detect_current_class": "com.system76.CosmicTerm"}
    saida = a09._com_quem_esta_na_frente("Ligado", vendo)
    assert saida is not None
    assert ">CosmicTerm</span>" in saida, (
        f"a tela mostra o nome inteiro e ela pediu o CURTO: {saida!r}")
    assert 'title="com.system76.CosmicTerm"' in saida, (
        f"o nome INTEIRO tem de estar na dica: {saida!r}")

    assert a09._curto("Hefesto-Dualsense4Unix") == "Hefesto-Dualsense4Unix"


def test_o_nome_da_janela_so_aparece_com_o_detector_vendo(a09):
    """`window_detect_last_class` é STICKY, e fora do `vendo` ela é de horas atrás."""
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
    Ele NÃO tem par no HTML, e a decisão de produto é que não passe a ter. A régua
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
    """*"Serial de fábrica: inteiro, e SÓ na aba Sistema (a de diagnóstico)."*"""
    texto = a09.pacote(ctx)[a09.REGISTRO]
    assert a09.ROTULO_DA_IDENTIDADE in texto
    assert SERIAL_DE_MENTIRA in texto, (
        "o serial saiu cortado, e ela pediu INTEIRO.")
    antes_do_diario = texto.split(a09.ROTULO_DO_DIARIO, 1)[0]
    assert SERIAL_DE_MENTIRA in antes_do_diario, texto
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


def test_o_autostart_manda_enable_ou_disable_conforme_o_lido(a09, ctx, monkeypatch):
    """O interruptor morto passa a mexer no systemd — pelo caminho da janela antiga."""
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
    """Sem `is-enabled` legível, ele NÃO adivinha — recusa dizendo."""
    janela = JanelaDeMentira()
    a09._JANELA_ANTIGA[:] = [janela]
    monkeypatch.setattr(a09, "_autostart", lambda: None)
    acao = __import__("pacotes").gesto_da_pagina("09-sistema.html", "autostart")
    with pytest.raises(RuntimeError):
        acao(ctx, {}, None)
    assert not janela.comandos, "recusou e mandou o comando assim mesmo."


def test_o_reiniciar_faz_reset_failed_antes(a09, ctx):
    """`reset-failed` + `restart`, nesta ordem — é a sequência da janela antiga."""
    janela = JanelaDeMentira()
    a09._JANELA_ANTIGA[:] = [janela]
    acao = __import__("pacotes").gesto_da_pagina("09-sistema.html", "reiniciar")
    acao(ctx, {}, None)
    assert janela.comandos == [["reset-failed", a09._unidade()],
                               ["restart", a09._unidade()]], (
        f"o restart foi sem `reset-failed`: {janela.comandos}")
    assert len(a09.reposicoes) == 1, (
        f"a reposição do lançador foi chamada {len(a09.reposicoes)} vez(es) no dublê")


def test_o_systemctl_que_falha_recusa_dizendo(a09, ctx):
    """`rc != 0` vira `RuntimeError` com o `stderr` junto — nunca silêncio."""
    a09._JANELA_ANTIGA[:] = [JanelaDeMentira(rc=1)]
    acao = __import__("pacotes").gesto_da_pagina("09-sistema.html", "reiniciar")
    with pytest.raises(RuntimeError) as erro:
        acao(ctx, {}, None)
    assert "Failed to enable unit." in str(erro.value)
    assert a09.reposicoes == [], "o restart falhou e o lançador foi reposto assim mesmo"


def test_o_retomar_recusa_quando_nao_ha_pausa(a09, ctx):
    """"Retomar" sem pausa é um no-op que se apresenta como ação."""
    class PonteDeMentira:
        def __init__(self):
            self.chamou = []

        def chamar(self, metodo, **kw):
            self.chamou.append(metodo)
            return True

    p = PonteDeMentira()
    with pytest.raises(RuntimeError) as erro:
        a09.retomar(ctx, {}, p)
    assert "não está pausado" in str(erro.value)
    assert not p.chamou, "recusou e mandou `daemon.resume` assim mesmo."

    import pacotes

    pausado = pacotes.Contexto(state={**ESTADO, "paused": True}, mesa=[],
                               conectados=list(ESTADO["controllers"]), estados={})
    a09._LENTO.clear()
    botao = pacotes.gesto_da_pagina("09-sistema.html", "parar-ou-retomar")
    carga = botao(pausado, {}, p)
    assert p.chamou == ["daemon.resume"], (
        "com a pausa ATIVA o botão do serviço tem de retomar — um clique, sem "
        "pergunta.")
    assert carga["blocos"]['[data-gesto="parar-ou-retomar"]'] != a09.CONFIRMA


def test_a_classe_da_linha_esta_declarada_como_sem_alvo(a09, ctx):
    """O `-cls` de cada linha é EMITIDO e não tem onde pousar — declarado, não escondido."""
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
    """Os que ficam de fora ficam ESCRITOS — e a razão MUDOU em 03/09/2026."""
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
    for nome in a09.DESTRUTIVOS:
        if nome not in a09.SEM_MOTOR:
            assert nome in com_dono, (
                f"`{nome}` saiu da declaração e continua sem dono — o botão "
                "voltou a ser morto e nenhuma lista o diz.")
    assert len(com_dono) >= a09.PISO_DA_ABA
