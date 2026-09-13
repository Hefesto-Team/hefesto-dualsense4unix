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

    def _find_repo_file(self, relpath: str):
        """O localizador REAL, e não um dublê — 06/09/2026.

        Ele é PURO (`encontrar_arquivo_do_repo` com as bases de instalação): não
        roda nada, não escreve nada, só procura no disco. Dublá-lo devolvendo um
        caminho inventado deixaria a régua verde sobre um `CONSERTOS` com nome
        de script errado — que é a BUG-GUI-REPO-ROOT-OFFBYONE-01, o botão que
        diz "Correções aplicadas" sem ter rodado nada.
        """
        from hefesto_dualsense4unix.app.actions.daemon_actions import (
            DaemonActionsMixin,
        )

        return DaemonActionsMixin._find_repo_file(self, relpath)

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

    def chamar_detalhado(self, metodo: str, *a):
        """A porta que traz `(ok, motivo)` — a do `atualizar` desde 06/09/2026.

        `motivo` sai `None` de propósito: é o que `_call_checked` devolve para
        toda falha de transporte (`app/ipc_bridge.py:382-387`), que é o caso da
        mesa dela com o serviço parado. **O dublê não pode ser mais frouxo que a
        função real** — foi assim que três réguas desta casa deram verde sobre
        defeito vivo.
        """
        self.chamadas.append((metodo, a))
        return self.releu, None

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
        def chamar_detalhado(self, metodo, *a):
            ordem.append(f"{metodo} · cache={'cheio' if a09._LENTO else 'vazio'}")
            return super().chamar_detalhado(metodo, *a)

    a09.atualizar(ctx, {}, Espia())
    assert ordem == ["daemon.reload · cache=cheio"], ordem


# ---------------------------------------------------------------------------
# 6. OS DOIS CLIQUES QUE ERAM MORTOS — 06/09/2026, a `SISTEMA-STEAM-01`
#
# O CSV registrava a mesma frase para os dois: *"Botão presente, sem dono.
# Clique morto."* As réguas abaixo CLICAM — nenhuma delas lê o texto do fonte,
# e é de propósito: seis instrumentos falsos caíram nesta casa em 05/09 por
# medirem o próprio arquivo em vez do produto.
# ---------------------------------------------------------------------------
def _clicar(gesto, ctx, texto: str = ""):
    """Um clique de verdade, com o que o DOM tinha no botão.

    O `texto` é o que o piloto manda em `o["texto"]` (`hefesto_vivo.BOOTSTRAP`,
    o ouvinte -> `alvo.textContent`), e é ele que carrega o consentimento: o
    segundo clique só vale trazendo a palavra que só existe no botão já armado.
    """
    return gesto(ctx, {"texto": texto}, PonteDeMentira())


def test_o_primeiro_clique_do_consertos_mede_e_nao_mexe(a09, ctx, monkeypatch):
    """Clique 1 de "Refazer os consertos automáticos": mede, mostra, não age.

    ERA UM CLIQUE MORTO — o botão está desenhado desde que a aba nasceu e o
    clique não chegava a lugar nenhum.

    O QUE ESTA RÉGUA COBRA é a D-33 do produto virando desenho de tela: o
    número de jogos com Steam Input só existe ANTES de desligá-lo, e um recibo
    que contasse o DEPOIS mentiria. Então o clique 1 MEDE e o clique 2 usa o
    que o 1 mediu.

    MORDIDA: pus o `subprocess.run` no clique 1 (isto é, tirei o
    `_confirmado`). Reprovou nas duas metades — o painel saiu com o recibo do
    `format_fix_safe_result` em vez do "clique de novo", e `rodou` encheu.
    """
    rodou: list[list[str]] = []
    monkeypatch.setattr(a09, "_matriz", lambda: a09._JANELA_ANTIGA[0])
    monkeypatch.setattr(a09._daemon, "medir_jogos_com_steam_input",
                        lambda: ["Pragmata", "Mullet Mad Jack"])
    import subprocess
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: rodou.append(list(a[0])) or _RC0())

    carga = _clicar(a09.refazer_consertos, ctx)

    assert not rodou, ("o primeiro clique RODOU os scripts. Ele tem de MEDIR e "
                       "perguntar — é o consentimento em dois cliques que ela "
                       "escolheu em 03/09/2026.")
    painel = carga["mesa"][a09.REGISTRO]
    assert "Pragmata" in painel and "Mullet Mad Jack" in painel, (
        "o painel não nomeia os jogos que vão ser tocados. *Nomeia, nunca só "
        "conta* — é a regra do WRAPPER-EM-TODOS-01, e *'3 jogos com pendência'* "
        "é o texto que deixou o Pragmata quebrado a noite inteira.")
    assert "Clique de novo" in painel, painel


def test_o_segundo_clique_do_consertos_roda_os_dois_scripts(a09, ctx, monkeypatch,
                                                           capsys):
    """Clique 2: os dois scripts do produto, e o recibo é do DONO.

    O RECIBO SAIU DO PAINEL EM 13/09/2026 (TELA-CALADA-03): é recibo, e a régua
    dela tira recibo da tela. Continua sendo o do dono e continua escrito — no
    diário da janela —, e o painel volta ao repouso.

    MORDIDA: troquei `CONSERTOS` por uma tupla vazia. Reprovou dizendo que
    nenhum script rodou — e o `format_fix_safe_result` respondeu *"Não encontrei
    os scripts de correção nesta instalação"*, que é a frase certa para essa
    máquina e a errada para esta.
    """
    rodou: list[list[str]] = []
    monkeypatch.setattr(a09, "_matriz", lambda: a09._JANELA_ANTIGA[0])
    monkeypatch.setattr(a09._daemon, "medir_jogos_com_steam_input", lambda: [])
    import subprocess
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: rodou.append(list(a[0])) or _RC0())

    _clicar(a09.refazer_consertos, ctx)                 # arma
    carga = _clicar(a09.refazer_consertos, ctx, a09.CONFIRMA)   # confirma

    assert len(rodou) == len(a09.CONSERTOS), rodou
    for (relpath, args), comando in zip(a09.CONSERTOS, rodou, strict=True):
        assert comando[0] == "bash" and comando[1].endswith(relpath.split("/")[-1])
        assert comando[2:] == args, comando
    # O RECIBO É O DO PRODUTO, e não uma frase desta régua nem do gesto.
    assert set(carga) == {"blocos"}, carga
    assert a09._PAINEL[0] is None, "a pergunta do clique 1 ficou no painel"
    assert a09._daemon.format_fix_safe_result(
        {"ran": 2, "missing": 0, "steam_input": (0, ""), "steam_input_jogos": []},
    ) in capsys.readouterr().err
    assert not a09._LENTO, (
        "a faixa lenta sobreviveu ao conserto: o exame do cartão ao lado acabou "
        "de mudar de valor, e mostrar o de até 2 s atrás ao lado do recibo é a "
        "tela dizendo 'pronto' sobre números que ninguém releu.")


def test_o_conserto_procura_os_scripts_pelo_localizador_do_produto(a09):
    """Os dois scripts de :data:`CONSERTOS` EXISTEM nesta instalação.

    Não é zelo: contar a raiz do checkout à mão já pagou a
    BUG-GUI-REPO-ROOT-OFFBYONE-01 nesta casa — os botões do cartão anti-storm
    viraram no-op SILENCIOSO, com toast de sucesso e nada executado. Um nome de
    script errado aqui reproduziria exatamente isso.

    MORDIDA: troquei um dos nomes por `scripts/nao_existe.sh`. Reprovou
    nomeando-o.
    """
    a09._JANELA_ANTIGA.clear()          # o localizador REAL, não o dublê
    achados = {str(c) for c, _ in a09._consertos_no_disco()}
    assert len(achados) == len(a09.CONSERTOS), (
        f"o localizador do produto achou {len(achados)} dos {len(a09.CONSERTOS)} "
        f"scripts de `CONSERTOS`: {sorted(achados)}. Um nome errado aqui é um "
        "botão que diz 'Correções aplicadas' sem ter rodado nada.")


def test_o_primeiro_clique_das_camadas_mostra_o_censo_e_nao_tira(a09, ctx, monkeypatch):
    """Clique 1 de "Tirar a sobreposição Vulkan": o TEMPO DO MEIO existe.

    O `title` promete TRÊS tempos — *"Mostra, jogo por jogo, a sobreposição
    Vulkan pendurada por dentro, e só então tira"* —, e o que segurava este
    botão era a falta de onde MOSTRAR. O painel de registro desta mesma faixa é
    onde esta aba já põe o que os botões respondem.

    MORDIDA: fiz o clique 1 chamar `curar_todos` direto. Reprovou: `tirou`
    encheu, e o painel saiu com a frase do resultado em vez da do censo.
    """
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    tirou: list[bool] = []
    monkeypatch.setattr(cv, "censo", lambda *a, **k: ["um-prefixo"])
    monkeypatch.setattr(cv, "pastas_compatdata", lambda *a, **k: ["/uma/pasta"])
    monkeypatch.setattr(cv, "curar_todos",
                        lambda *a, **k: tirou.append(True) or [])
    monkeypatch.setattr(a09._emulacao, "frase_do_censo",
                        lambda p, bibliotecas=1: ("achei uma camada", True, False))

    carga = _clicar(a09.procurar_camadas, ctx)

    assert not tirou, "o primeiro clique TIROU. Ele tem de olhar e perguntar."
    painel = carga["mesa"][a09.REGISTRO]
    assert painel.startswith("achei uma camada"), painel
    assert "TIRAR" in painel, (
        "o painel não diz o que o segundo clique vai fazer. Os botões seguem o "
        "que EXISTE, e quem diz qual dos dois atos está na mesa é esta linha.")


def test_sem_nada_a_fazer_as_camadas_nao_armam_o_segundo_tempo(a09, ctx, monkeypatch):
    """Nada a tirar e nada a devolver: mostra o achado e NÃO arma.

    É a regra do desenho da janela antiga, dita com todas as letras em
    `_build_camadas_dialog`: *"Botão que aparece e não faz nada ensina que a
    tela é enfeite"*. Aqui o botão é um só, e quem segue o que existe é o
    ARMAR — deixar "Confirma?" na tela sobre um segundo tempo que não existe é
    o mesmo enfeite.

    MORDIDA: tirei o ramo do `if not (tem_tirar or tem_devolver)`. Reprovou: o
    botão ficou armado com o censo vazio.
    """
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    monkeypatch.setattr(cv, "censo", lambda *a, **k: [])
    monkeypatch.setattr(cv, "pastas_compatdata", lambda *a, **k: ["/uma/pasta"])
    monkeypatch.setattr(a09._emulacao, "frase_do_censo",
                        lambda p, bibliotecas=1: ("nada pendurado", False, False))

    carga = _clicar(a09.procurar_camadas, ctx)

    assert a09._armado_agora() != "procurar-camadas", (
        "o botão ficou armado sem ter o que fazer no segundo clique.")
    assert carga["mesa"][a09.REGISTRO] == "nada pendurado"


def test_o_segundo_clique_das_camadas_segue_o_que_o_censo_achou(a09, ctx, monkeypatch):
    """Só o que EXISTE: com camada ligada TIRA; com camada tirada DEVOLVE.

    MORDIDA: cravei `religar=False`. Reprovou no caso da devolução — o gesto
    tirava de novo o que já estava tirado, e a frase do recibo saiu com o verbo
    trocado.
    """
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    for tem_tirar, tem_devolver, esperado in ((True, False, False),
                                              (False, True, True)):
        pedidos: list[bool] = []
        monkeypatch.setattr(cv, "censo", lambda *a, **k: ["um-prefixo"])
        monkeypatch.setattr(cv, "pastas_compatdata", lambda *a, **k: ["/uma/pasta"])
        monkeypatch.setattr(
            cv, "curar_todos",
            lambda *a, religar=False, _p=pedidos, **k: _p.append(religar) or [])
        monkeypatch.setattr(
            a09._emulacao, "frase_do_censo",
            lambda p, bibliotecas=1, _t=tem_tirar, _d=tem_devolver: ("o censo", _t, _d))
        from hefesto_dualsense4unix.integrations import steam_launch_options as slo
        monkeypatch.setattr(slo, "steam_game_running", lambda *a, **k: False)

        _clicar(a09.procurar_camadas, ctx)
        _clicar(a09.procurar_camadas, ctx, a09.CONFIRMA)
        assert pedidos == [esperado], (tem_tirar, tem_devolver, pedidos)


def test_as_camadas_recusam_com_jogo_aberto(a09, ctx, monkeypatch):
    """Jogo da Steam vivo: recusa DIZENDO, e não mexe.

    A razão é do produto: o Wine mantém o registro do prefixo em MEMÓRIA e o
    regrava ao sair, então escrever agora seria trabalho perdido — e perdido em
    silêncio, que é pior que recusar.

    MORDIDA: tirei o portão. Reprovou — `curar_todos` foi chamado com o jogo
    aberto.
    """
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    tirou: list[bool] = []
    monkeypatch.setattr(cv, "censo", lambda *a, **k: ["um-prefixo"])
    monkeypatch.setattr(cv, "pastas_compatdata", lambda *a, **k: ["/uma/pasta"])
    monkeypatch.setattr(cv, "curar_todos", lambda *a, **k: tirou.append(True) or [])
    monkeypatch.setattr(a09._emulacao, "frase_do_censo",
                        lambda p, bibliotecas=1: ("o censo", True, False))
    monkeypatch.setattr(slo, "steam_game_running", lambda *a, **k: True)

    _clicar(a09.procurar_camadas, ctx)
    with pytest.raises(RuntimeError) as erro:
        _clicar(a09.procurar_camadas, ctx, a09.CONFIRMA)

    assert not tirou
    assert "jogo aberto" in str(erro.value).lower(), erro.value


def test_nenhum_dos_cinco_destrutivos_ficou_sem_dono(a09):
    """`SEM_MOTOR` encolheu, e o que sobra tem razão de MECANISMO.

    Eram três em 04/09; hoje é UM — o `restaurar-de-fabrica`, que não espera
    motor: espera a linha em `hefesto_vivo.PERIGOSOS`, e esse arquivo é de
    outra posse. Sem ela a régua de clique restaura o perfil DELA para provar
    que sabe clicar.

    Esta régua cobra os dois sentidos: quem está em `SEM_MOTOR` não pode ter
    gesto registrado, e quem NÃO está tem de ter.
    """
    import pacotes

    registrados = {n for (p, n) in pacotes.GESTOS if p == "09-sistema.html"}
    for nome in a09.DESTRUTIVOS:
        if nome in a09.SEM_MOTOR:
            assert nome not in registrados, (
                f"{nome!r} está declarado em `SEM_MOTOR` E tem gesto. Se ele "
                "ganhou dono, TIRE a declaração — declaração que envelhece "
                "calada vira paisagem.")
        else:
            assert nome in registrados, (
                f"{nome!r} não está em `SEM_MOTOR` e não tem dono: é um botão "
                "desenhado, prometendo trabalho, com o clique morto. *Um botão "
                "que não faz nada é pior que um botão que não existe.*")


class _RC0:
    """O que `subprocess.run` devolve quando o script correu bem."""

    returncode = 0
    stdout = "resultado=aplicado\n"
    stderr = ""


# ---------------------------------------------------------------------------
# 7. O PERFIL DE BATERIA DEIXOU DE SER LITERAL — 06/09/2026
# ---------------------------------------------------------------------------
def test_as_duas_linhas_do_teto_mudam_quando_o_dono_muda(a09, ctx, monkeypatch):
    """O valor VEIO DO DONO — e não do instante em que a página foi gerada.

    O defeito: as duas linhas do Perfil de Bateria ("O teto alcança" e "Ainda
    sem teto") eram derivadas de `LINHAS_DO_TETO` na hora da GERAÇÃO e ficavam
    cravadas no HTML. No dia em que os "Gatilhos" ganharem ponto de aplicação
    no daemon, a tela dela continuaria dizendo que o teto não os alcança.

    **UMA RÉGUA QUE SÓ CONTASSE LINHAS PASSARIA COM A TELA ESTÁTICA DE HOJE.**
    Esta MOVE o dono: dá aos "Gatilhos" um ponto de aplicação e exige que as
    duas metades andem — a linha entra numa e sai da outra.

    MORDIDA: cravei o valor (`return ("Vibração", "Gatilhos, luz…")`). Reprovou
    nas duas metades.

    A COMPARAÇÃO É SEM CAIXA, e a primeira escrita desta régua REPROVOU A CURA
    por causa disso: a frase do produto é em CAIXA DE FRASE (regra dela, 30/08:
    *"a maiúscula a regra é sobre a primeira letra a ser capitalizada"*), então
    o valor certo é `'Vibração e gatilhos'` — com `g` minúsculo. Uma régua que
    exigisse `"Gatilhos"` estaria cobrando a caixa que ela mandou tirar.
    """
    from hefesto_dualsense4unix.app.actions.config import secao_orcamento as orc

    antes = [t.lower() for t in a09.frases_do_teto()]
    assert "vibração" in antes[0] and "gatilhos" in antes[1], antes

    com_gatilho = tuple(
        orc.LinhaDoTeto(linha.nome, linha.vem_de,
                        "hefesto_dualsense4unix.core.rumble:_effective_mult"
                        if linha.nome == "Gatilhos" else linha.ponto_de_aplicacao)
        for linha in orc.LINHAS_DO_TETO)
    monkeypatch.setattr(orc, "LINHAS_DO_TETO", com_gatilho)

    depois = [t.lower() for t in a09.frases_do_teto()]
    assert "gatilhos" in depois[0], (
        "os 'Gatilhos' ganharam ponto de aplicação no produto e a linha 'O "
        f"teto alcança' continuou dizendo {depois[0]!r}. O valor não veio do "
        "dono — veio do instante em que alguém rodou o gerador.")
    assert "gatilhos" not in depois[1], (
        f"a linha 'Ainda sem teto' continuou listando os Gatilhos: {depois[1]!r}. "
        "As duas metades leem o MESMO dono e têm de andar juntas.")


def test_o_tique_escreve_as_duas_linhas_do_teto(a09, ctx):
    """Elas viajam no pacote — sem isso o valor vivo não chega ao pixel.

    Um `data-campo` na página e nenhum escritor é o buraco por onde o literal
    do mockup volta a aparecer. E o glifo vai junto: uma linha que se contradiz
    dentro de si mesma (valor pintado ao lado de símbolo congelado) é o pior
    defeito desta aba, e já foi fotografado em 03/09.

    MORDIDA: tirei as quatro linhas do `pacote()`. Reprovou nomeando cada uma.
    """
    from hefesto_dualsense4unix.interface.pacotes import normalizar

    mesa = normalizar(dict(a09.pacote(ctx)))["mesa"]
    for campo in (a09.CAMPO_DO_ALCANCE, f"{a09.CAMPO_DO_ALCANCE}-g",
                  a09.CAMPO_DOS_PENDENTES, f"{a09.CAMPO_DOS_PENDENTES}-g"):
        assert campo in mesa, (
            f"o pacote não escreve em {campo!r}. O endereço está na bancada e "
            "ninguém o preenche — a linha volta a mostrar o literal do desenho.")
    assert mesa[a09.CAMPO_DO_ALCANCE] == a09.frases_do_teto()[0]
    assert mesa[a09.CAMPO_DOS_PENDENTES] == a09.frases_do_teto()[1]


def test_o_apelido_da_tela_tem_um_dono_so(a09):
    """O gerador LÊ o apelido daqui — não o digita.

    Ele vivia em `interface/aba09.py` e passou a ter DOIS leitores em
    06/09/2026: o gerador (que escreve o desenho) e o pacote (que escreve o
    valor vivo). Digitado nos dois, os dois se afastariam no dia em que um
    mudasse — que é como a fita viva morreu calada em 27/08.

    MORDIDA: troquei o valor de `"Barra de luz"` no pacote. O gerador saiu com
    a palavra nova, e é isso que prova que ele lê daqui.
    """
    import aba09

    assert aba09.APELIDO_NA_TELA == a09.APELIDO_NA_TELA, (
        "o apelido da tela divergiu entre o gerador e o pacote. O dono é o "
        "pacote, e `aba09._constantes` o lê de lá sem importar nada.")


# ---------------------------------------------------------------------------
# 8. A FRASE DO EXAME NOMEIA O BOTÃO QUE ESTÁ NA TELA — 06/09/2026
# ---------------------------------------------------------------------------
def test_a_frase_do_exame_nomeia_o_botao_que_esta_na_tela(a09):
    """O `storm_doctor` manda clicar num botão que EXISTE nesta página.

    ERA UM DEFEITO VIVO, achado pela `GTK-2`: a frase dizia *"clique 'Consertar
    problemas conhecidos' na aba Sistema"* e nesta aba o botão se chama
    *"Refazer os consertos automáticos"*. A frase chega a esta tela — o exame é
    pintado por `_achados()` — e mandava procurar um botão que não está lá, que
    é a forma exata que o glossário proíbe.

    **E TROCAR O `se_faltar` NÃO CURAVA.** Medido antes: com o glade no disco,
    `rotulo_do_botao` o lê PRIMEIRO e devolve o nome velho; a reserva nem
    chegava a ser usada (`rotulos_de_reserva() == {}`). A cura foi a ORDEM das
    fontes — a página que o produto renderiza responde primeiro.

    MORDIDA: esvaziei `storm_doctor._NA_TELA_VIVA` e o glade voltou a vencer.
    Reprovou nomeando as duas palavras.
    """
    from hefesto_dualsense4unix.integrations import storm_doctor as sd

    sd._ROTULOS_EM_CACHE.clear()
    sd._ROTULOS_DE_RESERVA.clear()
    dito = sd.rotulo_do_botao("btn_storm_fix_safe", "?")
    assert f">{dito}</button>" in _pagina(), (
        f"o exame manda clicar em {dito!r} e a página que o produto renderiza "
        "não tem botão nenhum com esse nome. É a forma que o glossário proíbe: "
        "*'qualquer frase que mande a pessoa procurar um botão que não "
        "existe'*.")
    assert not sd.rotulos_de_reserva(), (
        "o rótulo saiu da RESERVA: nenhuma tela respondeu, e a frase está "
        f"publicando um nome que ninguém conferiu — {sd.rotulos_de_reserva()}.")


def test_os_dois_leitores_do_rotulo_nao_divergem(a09):
    """O gêmeo declarado: o `storm_doctor` e o pacote leem o MESMO botão.

    Os dois não podem ser um só sem um ciclo de import — `a09_sistema` importa
    `storm_doctor`. O que segura o par é esta régua, e ela é a mesma disciplina
    do `test_aba09_a_fita_vem_de_cima`: escritos duas vezes sem régua, os dois
    se afastam no dia em que alguém mudar um.

    MORDIDA: troquei o `data-gesto` de `storm_doctor._NA_TELA_VIVA` por
    `refazer-proton`. Reprovou dizendo os dois rótulos, lado a lado.
    """
    from hefesto_dualsense4unix.integrations import storm_doctor as sd

    sd._ROTULOS_EM_CACHE.clear()
    do_doutor = sd._rotulo_na_tela_viva("btn_storm_fix_safe")
    a09._ROTULOS.clear()
    do_pacote = a09._rotulo_do_desenho("refazer-consertos")
    assert do_doutor == do_pacote, (
        f"os dois leitores do mesmo botão discordam: o `storm_doctor` lê "
        f"{do_doutor!r} e o pacote lê {do_pacote!r}. Eles apontam para o mesmo "
        "`data-gesto` na mesma página — se discordam, um dos dois mudou de "
        "endereço sozinho.")
