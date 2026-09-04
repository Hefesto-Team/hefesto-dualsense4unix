#!/usr/bin/env python3
"""A ABA SISTEMA FECHA A PARIDADE COM A JANELA ANTIGA — 03/09/2026.

Esta régua mede as OITO features que a fila da paridade
(`docs/data/paridade-gtk-html.csv`, as linhas com `aba == "09-sistema"`) dizia
faltar e que passaram a existir. Ela é o par do CSV: a linha lá afirma
``IGUAL``, e é aqui que a afirmação se sustenta no comportamento — não no
símbolo.

**POR QUE ELA PRECISOU EXISTIR, e é um achado sobre a régua da paridade.** A
regra 6 do `check_paridade_gtk_html.py` (`divida-fechada`) procura o símbolo da
GTK no TEXTO dos arquivos do lado HTML. Ela não distingue CHAMADA de PROSA:
quatro linhas do CSV foram promovidas a ``DIFERENTE`` em 03/09 porque alguém
escreveu o nome da função da GTK dentro de um **comentário** deste pacote.
Medido, arquivo a arquivo, nesta frente:

    símbolo                                  onde ele aparece no lado HTML
    ───────────────────────────────────────  ───────────────────────────────────
    medir_guarda_do_steam_input()            a09_sistema.py:359   CHAMADA
    medir_prontuario_dos_jogos()             a09_sistema.py:444   CHAMADA
    _aplicar_sensibilidade_ligar_desligar    a09_sistema.py:1251  docstring
    on_daemon_service_restart                a09_sistema.py:1408  comentário
    on_daemon_autostart_toggled              a09_sistema.py:1407  comentário
    gui_dialogs.confirm_restore_default      a09_sistema.py:1521  string de dado

As duas primeiras fecharam de verdade; as quatro de baixo não. É a família de
defeito que esta casa já nomeou — *a régua confunde a PALAVRA com o ATO* — e a
resposta desta frente foi medir o ATO aqui, gesto a gesto, valor a valor.

O QUE CADA BLOCO COBRA, e a MORDIDA de cada um está no docstring do teste:

1. **os quatro estados chegam ao PIXEL** — não só ao `_status_do_daemon`;
2. **o interruptor, o botão aceso e o painel em repouso são DADO** — os três
   eram literal congelado do desenho;
3. **o exame tem as OITO fontes da janela antiga**, e as duas condicionais
   entram quando falam;
4. **`ver-plugins` recusa dizendo, e `ver-detalhes` NÃO** — a única trava da
   camada do produto que este pacote desobedece, e ela é declarada;
5. **`atualizar` relê a aba**, que é a metade que o botão de mesmo nome faz na
   janela antiga.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: A página que o PRODUTO renderiza — não a bancada. Uma régua que medisse o
#: `mockup/` daria verde sobre um endereço que a tela dela não tem.
PAGINA = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/09-sistema.html"

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
         "player_slot": 1, "serial": None, "modelo": "White"},
    ],
}


class JanelaDeMentira:
    """O dublê de `DaemonActionsMixin` — e ele NÃO fala com o systemd.

    Sem ele, cada teste desta régua rodaria `systemctl --user` de verdade na
    máquina de quem a executa. Uma régua que reinicia o daemon de quem a roda
    não é régua.
    """

    def __init__(self, status: str = "online_systemd",
                 texto: str = "● unidade ativa") -> None:
        self.status, self.texto = status, texto
        self.comandos: list[list[str]] = []

    def _daemon_status(self) -> str:
        return self.status

    def _systemctl_status_text(self, unit: str) -> str:
        return self.texto

    def _invoke_systemctl(self, args, capture=False, check=False):
        self.comandos.append(list(args))

        class R:
            returncode = 0
            stderr = ""

        return R()


class PonteDeMentira:
    """A ponte dos gestos, gravando o que lhe pediram. Nada sai deste processo."""

    def __init__(self, plugins: list | None = None, releu: bool = True) -> None:
        self.chamadas: list[tuple[str, tuple]] = []
        self.plugins = plugins if plugins is not None else []
        self.releu = releu

    def chamar(self, metodo: str, *a):
        self.chamadas.append((metodo, a))
        return self.releu

    def resultado(self, metodo: str, *a):
        self.chamadas.append((metodo, a))
        return self.plugins


@pytest.fixture
def a09(monkeypatch):
    from pacotes import a09_sistema as mod

    mod._JANELA_ANTIGA[:] = [JanelaDeMentira()]
    # `is-enabled` NÃO PODE SAIR DA MÁQUINA DE QUEM RODA: `_autostart` chama
    # `subprocess.run` direto, fora do mixin.
    monkeypatch.setattr(mod, "_autostart", lambda: "enabled")
    # O EXAME DE VERDADE VARRE O DISCO. Aqui ele é injetado, para que o número
    # de linhas seja o do TESTE e não o da máquina de quem o roda.
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
# 1. OS QUATRO ESTADOS CHEGAM AO PIXEL
# ---------------------------------------------------------------------------
#: OS QUATRO NÃO SE DIGITAM AQUI — eles são as chaves de
#: `aba_sistema._ESTADO_DO_HEFESTO`, e o texto de cada um é o dela. Uma régua
#: que escrevesse "Ligado, em modo improvisado" viraria o segundo dono da frase,
#: e reprovaria a melhora no dia em que ela reescrevesse o texto.
def _os_quatro() -> list[str]:
    from hefesto_dualsense4unix.gui import aba_sistema as tela

    return list(tela._ESTADO_DO_HEFESTO)


@pytest.mark.parametrize("estado", _os_quatro())
def test_cada_estado_da_matriz_chega_ao_valor_da_tela(a09, estado):
    """O texto do estado no pacote é o da camada do produto, para os QUATRO.

    O DEFEITO QUE ISTO MEDE: até 03/09 este pacote colapsava a matriz em dois
    (`"online_systemd" if ctx.state else "offline"`), e com o daemon rodando
    fora do systemd a tela escrevia "Ligado" em verde com a dica *"Se travar,
    ele volta sozinho"* — falso naquele estado.

    O CONTEXTO É O DO DAEMON CALADO, e isso não é conveniência: com um
    `state_full` na mão, `_status_do_daemon` DESEMPATA a favor do `state` — o
    daemon respondeu, logo está de pé, e um `offline` da matriz vira
    `online_avulso`. Esse desempate é comportamento querido e tem régua própria
    (`test_a_09_sistema_sai_do_desenho.test_o_daemon_que_responde_nao_e_chamado_de_desligado`);
    o que se mede AQUI é a travessia dos quatro até o valor da tela, e ela
    precisa da matriz passando limpo. Medido: com `ESTADO` na mão, o caso
    `offline` chega como `'Ligado, em modo improvisado'` — certo, e não é o que
    esta linha pergunta.

    MORDIDA: troquei `_status_do_daemon` por `lambda s: "online_systemd"`.
    Reprovaram 3 dos 4 casos (`online_avulso`, `iniciando`, `offline`), cada um
    dizendo o texto que veio no lugar do esperado.
    """
    import pacotes

    from hefesto_dualsense4unix.gui import aba_sistema as tela

    calado = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    a09._JANELA_ANTIGA[:] = [JanelaDeMentira(status=estado)]
    a09._LENTO.clear()
    fora = a09.pacote(calado)
    esperado = tela._ESTADO_DO_HEFESTO[estado]
    assert fora["hefesto-estado"] == esperado.txt, (
        f"o estado {estado!r} chegou à tela como {fora['hefesto-estado']!r}")
    assert fora["hefesto-estado-g"] == esperado.g
    assert fora["hefesto-estado-cls"] == esperado.cls


def test_o_estado_avulso_nao_promete_que_ele_volta_sozinho(a09, ctx):
    """O `online_avulso` não pode sair com o texto e a cor do `online_systemd`.

    É a consequência que a fila da paridade nomeia: os dois estados "de pé" não
    são o mesmo estado, e a diferença é uma promessa — *"se travar, ele volta
    sozinho"* só vale sob o systemd.

    MORDIDA: fiz `_status_do_daemon` devolver sempre `online_systemd`. Este
    teste reprovou com `'Ligado' == 'Ligado'` no lugar da desigualdade.
    """
    from hefesto_dualsense4unix.gui import aba_sistema as tela

    a09._JANELA_ANTIGA[:] = [JanelaDeMentira(status="online_avulso")]
    a09._LENTO.clear()
    fora = a09.pacote(ctx)
    assert fora["hefesto-estado"] != tela._ESTADO_DO_HEFESTO["online_systemd"].txt
    assert fora["hefesto-estado-cls"] != tela._ESTADO_DO_HEFESTO["online_systemd"].cls


# ---------------------------------------------------------------------------
# 2. O INTERRUPTOR, O BOTÃO ACESO E O PAINEL EM REPOUSO SÃO DADO
# ---------------------------------------------------------------------------
#: OS TRÊS ENDEREÇOS QUE ERAM LITERAL DO DESENHO, e cada um com o valor que a
#: página congelava. A régua NÃO digita o valor esperado — ela pergunta ao dono
#: e exige que o pacote e a página concordem com ele.
TRES_QUE_ERAM_DESENHO = ("hefesto-autostart", "bateria-perfil", "registro-texto")


@pytest.mark.parametrize("endereco", TRES_QUE_ERAM_DESENHO)
def test_o_endereco_que_era_desenho_existe_na_pagina(endereco):
    """A página do PRODUTO tem onde receber os três. Sem o endereço, o valor cai
    no vazio e a tela continua com o literal do mockup — que foi o defeito
    exato de 02/09, com o painel técnico mostrando quatro linhas de registro que
    nunca aconteceram.

    MORDIDA: apaguei `data-campo="bateria-perfil"` dos três botões do Perfil de
    Bateria numa cópia da página. Reprovou nomeando o endereço.
    """
    assert f'data-campo="{endereco}"' in _pagina(), (
        f"a página do produto não tem `data-campo=\"{endereco}\"` — o pacote "
        "escreveria no vazio e a tela ficaria com o literal do desenho.")


def test_o_interruptor_do_autostart_sai_do_systemd_e_nao_do_desenho(a09, ctx, monkeypatch):
    """`hefesto-autostart` acompanha `is-enabled` nos TRÊS desfechos.

    A página nasce com a chave ACESA (`class="chave on"`). Enquanto o pacote não
    escrevia este endereço, ela ficava acesa qualquer que fosse a verdade do
    systemd — e o `✓` verde ao lado dizia o mesmo. Hoje nesta máquina
    `is-enabled` responde `enabled` e o desenho acertava por coincidência.

    O `False` E O `None` SÃO COISAS DIFERENTES, e o glifo é quem os separa:
    `disabled` é "não liga sozinho"; não conseguir perguntar ao systemd não é.

    MORDIDA: apaguei a linha `fora["hefesto-autostart"] = auto` do pacote.
    Reprovou nos três casos com `KeyError: 'hefesto-autostart'`.
    """
    from hefesto_dualsense4unix.gui import aba_sistema as tela

    for cru, esperado in (("enabled", True), ("disabled", False), (None, None)):
        monkeypatch.setattr(a09, "_autostart", lambda cru=cru: cru)
        a09._LENTO.clear()
        fora = a09.pacote(ctx)
        assert fora["hefesto-autostart"] is esperado, (
            f"`is-enabled` = {cru!r} chegou à tela como "
            f"{fora['hefesto-autostart']!r}")
    # O GLIFO SEPARA O `False` DO `None`: os dois apagam a chave, e só o glifo
    # diz qual dos dois é.
    monkeypatch.setattr(a09, "_autostart", lambda: "disabled")
    a09._LENTO.clear()
    desligado = a09.pacote(ctx)["hefesto-autostart-g"]
    monkeypatch.setattr(a09, "_autostart", lambda: None)
    a09._LENTO.clear()
    sem_resposta = a09.pacote(ctx)["hefesto-autostart-g"]
    assert desligado != sem_resposta
    assert sem_resposta == tela.GLIFO_INFO


def test_o_perfil_de_bateria_aceso_sai_do_disco(a09, ctx):
    """`bateria-perfil` é a CHAVE que o produto grava, e ela vem de `perfil_na_tela`.

    O valor pintado é comparado pelo `data-hef-quando` de cada botão, que o
    gerador escreve a partir do mesmo `PERFIS`. Uma régua que digitasse
    `"bateria_longa"` viraria o segundo dono da tradução botão→disco.

    MORDIDA: apaguei `fora["bateria-perfil"] = perfil_da_bateria`. Reprovou com
    `KeyError`. Depois devolvi a linha e troquei o gravado no disco por outro
    perfil sem mexer no pacote: passou, como tem de passar.
    """
    from hefesto_dualsense4unix.app.actions.config.secao_orcamento import (
        PERFIS,
        TETO_POR_PERFIL,
        perfil_na_tela,
    )
    from hefesto_dualsense4unix.utils.maquina import gravar_maquina

    for escolhido in PERFIS:
        gravar_maquina({"orcamento": {"teto": TETO_POR_PERFIL[escolhido]}})
        a09._LENTO.clear()
        fora = a09.pacote(ctx)
        assert fora["bateria-perfil"] == perfil_na_tela(), (
            f"gravei {escolhido!r} no disco e a tela recebeu "
            f"{fora['bateria-perfil']!r}")
        # E O ACESO TEM ONDE POUSAR: o botão daquele perfil declara na página
        # que é ELE quem acende com este valor.
        assert f'data-hef-quando="{escolhido}"' in _pagina()


def test_o_painel_em_repouso_e_o_systemctl_status_e_nao_um_traco(a09, ctx):
    """Sem ninguém clicar, o painel técnico traz o que a janela antiga sempre teve.

    A GTK NUNCA TEVE UM TRAÇO AQUI: o `Gtk.TextView` dela fica sempre com a
    saída de `systemctl status <unit>` (`daemon_actions.py:1970` e `:2549`).
    Esta tela mostrava `—` até alguém clicar em "Ver detalhes".

    MORDIDA: troquei o corpo de `_repouso_do_painel` por `return ""`. Reprovou
    dizendo que o painel voltou ao traço.
    """
    fora = a09.pacote(ctx)
    assert fora["registro-texto"] != "—", "o painel em repouso voltou ao traço"
    assert "unidade ativa" in fora["registro-texto"], (
        "o painel em repouso não traz o `systemctl status` da janela antiga")


def test_o_ultimo_pedido_vence_o_repouso_ate_o_proximo_clique(a09, ctx):
    """Quem clicou em "Ver …" continua lendo o que pediu, tique após tique.

    Sem isto, o texto pedido apareceria e sumiria em meio segundo — o painel é
    repintado a 500 ms.

    MORDIDA: apaguei `_PAINEL[0] = texto` de `_para_o_painel`. Reprovou: o
    segundo pacote já trazia o `systemctl status` de volta.
    """
    a09.ver_detalhes(ctx, {}, PonteDeMentira())
    primeiro = a09.pacote(ctx)["registro-texto"]
    segundo = a09.pacote(ctx)["registro-texto"]
    assert primeiro == segundo
    assert "unidade ativa" not in primeiro


# ---------------------------------------------------------------------------
# 3. O EXAME TEM AS OITO FONTES DA JANELA ANTIGA
# ---------------------------------------------------------------------------
def test_os_dois_achados_condicionais_entram_no_exame(a09, monkeypatch):
    """O vigia do Steam Input e o prontuário dos jogos entram QUANDO FALAM.

    Os dois tinham UM chamador em toda a árvore, e era a GTK
    (`_refresh_storm_diag`, `daemon_actions.py:1136` e `:1145`) — por isso o
    exame desta tela era 6/8 do exame da janela antiga. Os dois só falam quando
    há problema, então a diferença aparece no dia do problema, que é justamente
    o dia em que ela precisa ver.

    MORDIDA: apaguei o `linhas.append(vigia)` de `_achados`. Reprovou dizendo
    que o achado do vigia não estava na lista.
    """
    monkeypatch.setattr(a09._exame, "storm_report", lambda **k: [("[ OK ]", "base")])
    monkeypatch.setattr(a09._exame, "controles_no_cabo", lambda s: 1)
    monkeypatch.setattr(a09._daemon, "medir_guarda_do_steam_input",
                        lambda: ("[WARN]", "o vigia do Steam Input está morto"))
    a09._PRONTUARIO.clear()
    a09._PRONTUARIO["quando"] = 1e18   # nunca vence: a thread de 7 s não roda
    a09._PRONTUARIO["achado"] = ("[WARN]", "um jogo sem perfil no disco")

    linhas = a09._achados(ESTADO)
    frases = [f for _, f in linhas]
    assert "o vigia do Steam Input está morto" in frases
    assert "um jogo sem perfil no disco" in frases
    assert len(linhas) == 3, f"o exame saiu com {len(linhas)} linhas: {linhas}"


def test_um_achado_condicional_que_levanta_nao_come_o_exame(a09, monkeypatch):
    """Uma Steam meio instalada não pode apagar as linhas que já estavam prontas.

    MORDIDA: tirei o `try/except` de volta do `medir_guarda_do_steam_input`.
    Reprovou com a exceção subindo até o teste.
    """
    monkeypatch.setattr(a09._exame, "storm_report", lambda **k: [("[ OK ]", "base")])
    monkeypatch.setattr(a09._exame, "controles_no_cabo", lambda s: 1)

    def explode():
        raise RuntimeError("a Steam não está onde eu esperava")

    monkeypatch.setattr(a09._daemon, "medir_guarda_do_steam_input", explode)
    a09._PRONTUARIO.clear()
    a09._PRONTUARIO["quando"] = 1e18
    a09._PRONTUARIO["achado"] = None
    linhas = a09._achados(ESTADO)
    assert [f for _, f in linhas] == ["base"]


# ---------------------------------------------------------------------------
# 4. A TRAVA QUE VALE, E A ÚNICA QUE NÃO VALE
# ---------------------------------------------------------------------------
def test_ver_plugins_recusa_com_o_servico_desligado(a09, ctx):
    """Com o daemon parado, o clique RECUSA DIZENDO — e a frase é do produto.

    Sem a trava, `plugin.reload` e `plugin.list` iam a um daemon que não está
    lá, o gesto voltava calado e o painel continuava com o texto do último
    pedido: quem clicou concluiria que a lista de agora é aquela.

    A FRASE NÃO SE DIGITA AQUI. Ela é a de `aba_sistema.travas()`, perguntada ao
    dono no próprio teste — digitá-la faria esta régua reprovar a melhora no dia
    em que ela reescrevesse o texto.

    MORDIDA: apaguei as três linhas do `_trava` em `ver_plugins`. Reprovou
    dizendo que o gesto chamou `plugin.reload` com o serviço desligado.
    """
    from hefesto_dualsense4unix.gui import aba_sistema as tela

    a09._JANELA_ANTIGA[:] = [JanelaDeMentira(status="offline")]
    a09._LENTO.clear()
    import pacotes

    parado = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    ponte = PonteDeMentira()
    with pytest.raises(RuntimeError) as erro:
        a09.ver_plugins(parado, {}, ponte)
    esperada = tela.travas(a09._leitura(parado))["ver-plugins"]
    assert str(erro.value) == esperada
    assert ponte.chamadas == [], (
        f"o gesto falou com o daemon parado: {ponte.chamadas}")


def test_ver_plugins_passa_com_o_servico_de_pe(a09, ctx):
    """E a trava não pode trancar o que está de pé — senão ela é um botão morto
    com outro nome.

    MORDIDA: troquei o `if motivo:` por `if True:`. Reprovou aqui.
    """
    ponte = PonteDeMentira(plugins=[{"name": "um", "disabled": False}])
    carga = a09.ver_plugins(ctx, {}, ponte)
    assert [m for m, _ in ponte.chamadas] == ["plugin.reload", "plugin.list"]
    assert "um" in carga["mesa"][a09.REGISTRO]


def test_ver_detalhes_nao_obedece_a_trava_e_a_divergencia_e_declarada(a09):
    """O único gesto desta aba que desobedece a `travas()`, e ele diz por quê.

    `travas()` tranca `ver-plugins` E `ver-detalhes` com a mesma frase — *"O
    serviço está desligado — não há o que perguntar a ele."* Para o segundo ela
    é falsa neste produto: o `ver-detalhes` daqui não pergunta ao daemon, ele lê
    o journal do systemd, que sobrevive à queda da unit. Com o serviço parado,
    este é o botão que responde **por que ele caiu**.

    A RÉGUA COBRA NOS DOIS SENTIDOS, e é o ponto dela: enquanto `travas()`
    trancar o `ver-detalhes`, a divergência TEM de estar declarada; no dia em
    que a camada do produto separar os dois, esta linha reprova e manda apagar a
    declaração — para que ela não fique como um esquecimento.

    ELA COMPARA CONJUNTOS, E NÃO PERCORRE A DECLARAÇÃO — e a primeira versão
    desta régua fazia o contrário. Ela iterava `TRAVA_QUE_NAO_VALE_AQUI.items()`
    e cobrava cada entrada; com o dicionário VAZIO o laço não roda, e a mordida
    de esvaziá-lo passou VERDE. Medido nesta frente, na primeira execução das
    mordidas: 19 passaram com a declaração arrancada. É a régua dando verde
    sobre nada — o defeito que esta casa mais pagou —, e a cura é perguntar aos
    dois donos (quem TRANCA e quem OBEDECE) e exigir que a diferença entre eles
    seja exatamente o que está declarado.

    QUEM OBEDECE SE LÊ NO FONTE, não numa segunda lista: um `_trava(ctx, "x")`
    no arquivo é a prova de que `x` consulta a camada do produto. Manter aqui a
    lista dos que obedecem seria o segundo dono do fato que esta régua mede.

    MORDIDA 1: esvaziei `TRAVA_QUE_NAO_VALE_AQUI`. Reprovou nomeando
    `ver-detalhes` como trava desobedecida sem razão declarada.
    MORDIDA 2: acrescentei `_trava(ctx, "ver-detalhes")` ao gesto — isto é, o
    pacote passou a obedecer. Reprovou mandando apagar a declaração.
    """
    import re

    import pacotes

    from hefesto_dualsense4unix.gui import aba_sistema as tela

    a09._JANELA_ANTIGA[:] = [JanelaDeMentira(status="offline")]
    a09._LENTO.clear()
    parado = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})

    #: QUEM TRANCA — a camada do produto, com o serviço desligado (o único
    #: estado em que ela tranca alguma coisa além do `retomar`).
    tranca = set(tela.travas(a09._leitura(parado)))
    #: QUEM É DESTA PÁGINA — o registro do despachante, e não uma lista minha.
    desta_pagina = {nome for pagina, nome in pacotes.GESTOS if pagina == "09-sistema.html"}
    #: QUEM OBEDECE — lido no fonte do pacote.
    fonte = pathlib.Path(a09.__file__).read_text(encoding="utf-8")
    obedece = set(re.findall(r'_trava\(ctx,\s*"([^"]+)"\)', fonte))

    desobedecidas = (tranca & desta_pagina) - obedece
    assert desobedecidas == set(a09.TRAVA_QUE_NAO_VALE_AQUI), (
        "o que `travas()` tranca, o pacote atende e nenhum gesto consulta:\n"
        f"    medido:    {sorted(desobedecidas)}\n"
        f"    declarado: {sorted(a09.TRAVA_QUE_NAO_VALE_AQUI)}\n"
        "Uma trava desobedecida sem razão escrita é um esquecimento; uma razão "
        "escrita para uma trava que o pacote já obedece é uma nota sobre nada.")
    for nome, motivo in a09.TRAVA_QUE_NAO_VALE_AQUI.items():
        assert len(motivo) > 80, f"a razão de `{nome}` não diz o bastante"

    # E O GESTO REALMENTE PASSA: declarar a razão e obedecer mesmo assim seria
    # uma nota sobre nada.
    ponte = PonteDeMentira()
    carga = a09.ver_detalhes(parado, {}, ponte)
    assert a09.REGISTRO in carga["mesa"]
    assert ponte.chamadas == [], "o `ver-detalhes` não fala com o daemon"


# ---------------------------------------------------------------------------
# 5. O `ATUALIZAR` RELÊ A ABA
# ---------------------------------------------------------------------------
def test_o_atualizar_zera_a_faixa_lenta(a09, ctx):
    """Depois do `daemon.reload`, a próxima pintura relê as cinco leituras caras.

    É a metade que o botão de mesmo nome faz na janela antiga
    (`on_daemon_refresh:2267` relê o estado, o exame e a linha do detector).
    Sem isto a tela ficava com o valor de antes por até `LENTO_S` segundos
    depois de o daemon reaplicar a configuração — e quem clicou não distingue
    "aplicou" de "não pegou".

    MORDIDA: apaguei o `_LENTO.clear()` do gesto. Reprovou dizendo que o cache
    continuava carregado depois do clique.
    """
    a09.pacote(ctx)                      # carrega a faixa lenta
    assert a09._LENTO, "a faixa lenta devia estar carregada antes do clique"
    ponte = PonteDeMentira()
    a09.atualizar(ctx, {}, ponte)
    assert [m for m, _ in ponte.chamadas] == ["daemon.reload"]
    assert not a09._LENTO, (
        "o cache de `LENTO_S` sobreviveu ao Atualizar: a aba continuaria "
        "mostrando o estado de antes do reload.")


def test_o_atualizar_recarrega_antes_de_zerar(a09, ctx):
    """A ordem: primeiro o `daemon.reload`, depois o cache.

    Zerar antes faria a releitura acontecer no meio dos 9,5 s do reload e
    publicar o estado de antes como se fosse o de depois.

    MORDIDA: inverti as duas linhas do gesto. Reprovou: o cache já estava vazio
    quando a ponte foi chamada.
    """
    a09.pacote(ctx)
    ordem: list[str] = []

    class Espia(PonteDeMentira):
        def chamar(self, metodo, *a):
            ordem.append(f"{metodo} · cache={'cheio' if a09._LENTO else 'vazio'}")
            return super().chamar(metodo, *a)

    a09.atualizar(ctx, {}, Espia())
    assert ordem == ["daemon.reload · cache=cheio"], ordem
