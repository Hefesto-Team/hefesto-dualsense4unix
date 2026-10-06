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
    medir_guarda_do_steam_input()            a09_sistema.py:151   CHAMADA
    medir_prontuario_dos_jogos()             a09_sistema.py:183   CHAMADA
    _aplicar_sensibilidade_ligar_desligar    a09_sistema.py:751  docstring
    on_daemon_service_restart                a09_sistema.py:860  comentário
    on_daemon_autostart_toggled              a09_sistema.py:859  comentário
    gui_dialogs.confirm_restore_default      a09_sistema.py:950  string de dado

As duas primeiras fecharam de verdade; as quatro de baixo não. É a família de
defeito que esta casa já nomeou — *a régua confunde a PALAVRA com o ATO* — e a
resposta desta frente foi medir o ATO aqui, gesto a gesto, valor a valor.

O QUE CADA BLOCO COBRA, e a MORDIDA de cada um está no docstring do teste:

1. **os quatro estados chegam ao PIXEL** — não só ao `_status_do_daemon`;
2. **o interruptor, o botão aceso e o painel em repouso são DADO** — os três
   eram literal congelado do desenho;
3. **o exame tem as OITO fontes da janela antiga**, e as duas condicionais
   entram quando falam;
4. **`ver-detalhes` NÃO obedece à trava** — a única da camada do produto que
   este pacote desobedece, e ela é declarada (o `ver-plugins`, que recusava
   dizendo, saiu da aba em 13/09/2026 — SISTEMA-BOTOES-01);
5. **`atualizar` relê a aba**, que é a metade que o botão de mesmo nome faz na
   janela antiga.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

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


from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.sistema`, que carrega o GTK")

class JanelaDeMentira:
    """O dublê de `DaemonActionsMixin` — e ele NÃO fala com o systemd."""

    def __init__(self, status: str = "online_systemd",
                 texto: str = "● unidade ativa") -> None:
        self.status, self.texto = status, texto
        self.comandos: list[list[str]] = []

    def _daemon_status(self) -> str:
        return self.status

    def _systemctl_status_text(self, unit: str) -> str:
        return self.texto

    def _find_repo_file(self, relpath: str):
        """O localizador REAL, e não um dublê — 06/09/2026."""
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
        """A porta que traz `(ok, motivo)` — a do `atualizar` desde 06/09/2026."""
        self.chamadas.append((metodo, a))
        return self.releu, None

    def resultado(self, metodo: str, *a):
        self.chamadas.append((metodo, a))
        return self.plugins


@pytest.fixture
def a09(monkeypatch):
    from pacotes import a09_sistema as mod

    mod._JANELA_ANTIGA[:] = [JanelaDeMentira()]
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


#: `aba_sistema._ESTADO_DO_HEFESTO`, e o texto de cada um é o dela. Uma régua
def _os_quatro() -> list[str]:
    from hefesto_dualsense4unix.interface import sistema as tela

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

    from hefesto_dualsense4unix.interface import sistema as tela

    calado = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    a09._JANELA_ANTIGA[:] = [JanelaDeMentira(status=estado)]
    a09._LENTO.clear()
    fora = a09.pacote(calado)
    esperado = tela.status_do_servico(estado, {})
    lista = fora[a09.CAMPO_DO_STATUS]
    servico = lista.split("</div>", 1)[0]
    assert f'<span class="selo {esperado["cls"]}">' in servico, (
        f"o estado {estado!r} chegou à tela como {servico!r}")
    assert esperado["selo"] in servico and esperado["txt"] in servico, servico


def test_o_estado_avulso_nao_promete_que_ele_volta_sozinho(a09, ctx):
    """O `online_avulso` não pode sair com o texto e a cor do `online_systemd`."""
    from hefesto_dualsense4unix.interface import sistema as tela

    a09._JANELA_ANTIGA[:] = [JanelaDeMentira(status="online_avulso")]
    a09._LENTO.clear()
    fora = a09.pacote(ctx)
    servico = fora[a09.CAMPO_DO_STATUS].split("</div>", 1)[0]
    de_pe = tela.status_do_servico("online_systemd", {})
    assert f'<span class="selo {de_pe["cls"]}">' not in servico, servico
    assert "improvisado" in servico, servico


TRES_QUE_ERAM_DESENHO = ("hefesto-autostart", "bateria-perfil", "registro-texto")


@pytest.mark.parametrize("endereco", TRES_QUE_ERAM_DESENHO)
def test_o_endereco_que_era_desenho_existe_na_pagina(endereco):
    """A página do PRODUTO tem onde receber os três. Sem o endereço, o valor cai"""
    assert f'data-campo="{endereco}"' in _pagina(), (
        f"a página do produto não tem `data-campo=\"{endereco}\"` — o pacote "
        "escreveria no vazio e a tela ficaria com o literal do desenho.")


def test_o_interruptor_do_autostart_sai_do_systemd_e_nao_do_desenho(a09, ctx, monkeypatch):
    """`hefesto-autostart` acompanha `is-enabled` nos TRÊS desfechos."""
    from hefesto_dualsense4unix.interface import sistema as tela

    for cru, esperado in (("enabled", True), ("disabled", False), (None, None)):
        monkeypatch.setattr(a09, "_autostart", lambda cru=cru: cru)
        a09._LENTO.clear()
        fora = a09.pacote(ctx)
        assert fora["hefesto-autostart"] is esperado, (
            f"`is-enabled` = {cru!r} chegou à tela como "
            f"{fora['hefesto-autostart']!r}")
    assert tela.GLIFO_INFO


def test_o_perfil_de_bateria_aceso_sai_do_disco(a09, ctx):
    """`bateria-perfil` é a CHAVE que o produto grava, e ela vem de `perfil_na_tela`.

    O valor pintado é comparado pelo `data-hef-quando` de cada botão, que o
    gerador escreve a partir do mesmo `PERFIS`. Uma régua que digitasse
    `"bateria_longa"` viraria o segundo dono da tradução botão→disco.

    MORDIDA: apagar `fora["bateria-perfil"] = perfil_da_bateria` reprova com
    `KeyError`; devolvida a linha, trocar o gravado no disco por outro
    perfil sem mexer no pacote passa, como tem de passar.
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
        assert f'data-hef-quando="{escolhido}"' in _pagina()


def test_o_painel_em_repouso_e_o_systemctl_status_e_nao_um_traco(a09, ctx):
    """Sem ninguém clicar, o painel técnico traz o que a janela antiga sempre teve."""
    fora = a09.pacote(ctx)
    assert fora["registro-texto"] != "—", "o painel em repouso voltou ao traço"
    assert "unidade ativa" in fora["registro-texto"], (
        "o painel em repouso não traz o `systemctl status` da janela antiga")


def test_o_ultimo_pedido_vence_o_repouso_ate_o_proximo_clique(a09, ctx):
    """Quem clicou em "Ver …" continua lendo o que pediu, tique após tique."""
    a09._para_o_painel("o que ela pediu")
    primeiro = a09.pacote(ctx)["registro-texto"]
    segundo = a09.pacote(ctx)["registro-texto"]
    assert primeiro == segundo == "o que ela pediu"
    a09._limpar_o_painel()


def test_os_dois_achados_condicionais_entram_no_exame(a09, monkeypatch):
    """O vigia do Steam Input e o prontuário dos jogos entram QUANDO FALAM."""
    monkeypatch.setattr(a09._exame, "storm_report", lambda **k: [("[ OK ]", "base")])
    monkeypatch.setattr(a09._exame, "controles_no_cabo", lambda s: 1)
    monkeypatch.setattr(a09._daemon, "medir_guarda_do_steam_input",
                        lambda: ("[WARN]", "o vigia do Steam Input está morto"))
    a09._PRONTUARIO.clear()
    a09._PRONTUARIO["quando"] = 1e18
    a09._PRONTUARIO["achado"] = ("[WARN]", "um jogo sem perfil no disco")

    linhas = a09._achados(ESTADO)
    frases = [f for _, f in linhas]
    assert "o vigia do Steam Input está morto" in frases
    assert "um jogo sem perfil no disco" in frases
    assert len(linhas) == 3, f"o exame saiu com {len(linhas)} linhas: {linhas}"


def test_um_achado_condicional_que_levanta_nao_come_o_exame(a09, monkeypatch):
    """Uma Steam meio instalada não pode apagar as linhas que já estavam prontas."""
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


def test_ver_os_plugins_saiu_da_aba_com_a_trava_dele(a09):
    """«Ver os plugins» SAIU — SISTEMA-BOTOES-01, 13/09/2026.

    ERAM DUAS RÉGUAS: `test_ver_plugins_recusa_com_o_servico_desligado` e
    `test_ver_plugins_passa_com_o_servico_de_pe`, e mediam a trava do gesto. O
    gesto saiu pela decisão de produto D-OS-PLUGINS-APARECEM-ONDE-AGEM
    (`docs/data/decisoes-de-produto.csv`): plugin não ganha seção própria. O que se
    cobra é a saída inteira — sem dono no pacote, sem trava e sem dono na
    camada do produto. A CLI e o IPC do daemon ficam.

    MORDIDA: devolva `"ver-plugins"` à conta de `aba_sistema.travas()`.
    """
    import pacotes

    from hefesto_dualsense4unix.interface import sistema as tela

    a09._JANELA_ANTIGA[:] = [JanelaDeMentira(status="offline")]
    a09._LENTO.clear()
    parado = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    assert pacotes.gesto_da_pagina("09-sistema.html", "ver-plugins") is None
    assert "ver-plugins" not in tela.travas(a09._leitura(parado))
    assert "ver-plugins" not in tela.GESTOS


def test_ver_detalhes_nao_obedece_a_trava_e_a_divergencia_e_declarada(a09):
    """O único gesto desta aba que desobedece a `travas()`, e ele diz por quê."""
    import re

    import pacotes

    from hefesto_dualsense4unix.interface import sistema as tela

    a09._JANELA_ANTIGA[:] = [JanelaDeMentira(status="offline")]
    a09._LENTO.clear()
    parado = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})

    tranca = set(tela.travas(a09._leitura(parado)))
    desta_pagina = {nome for pagina, nome in pacotes.GESTOS if pagina == "09-sistema.html"}
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


def test_o_atualizar_zera_a_faixa_lenta(a09, ctx):
    """Depois do `daemon.reload`, a próxima pintura relê as cinco leituras caras.

    É a metade que o botão de mesmo nome faz na janela antiga
    (`on_daemon_refresh:2267` relê o estado, o exame e a linha do detector).
    Sem isto a tela ficava com o valor de antes por até `LENTO_S` segundos
    depois de o daemon reaplicar a configuração — e quem clicou não distingue
    "aplicou" de "não pegou".

    MORDIDA: apagar o `_LENTO.clear()` do gesto reprova dizendo que o cache
    continuava carregado depois do clique.
    """
    a09.pacote(ctx)
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


def _clicar(gesto, ctx, texto: str = ""):
    """Um clique de verdade, com o que o DOM tinha no botão."""
    return gesto(ctx, {"texto": texto}, PonteDeMentira())


def test_o_primeiro_clique_do_consertos_mede_e_nao_mexe(a09, ctx, monkeypatch):
    """Clique 1 de "Refazer os consertos automáticos": mede, mostra, não age."""
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
    """Clique 2: os dois scripts do produto, e o recibo é do DONO."""
    rodou: list[list[str]] = []
    monkeypatch.setattr(a09, "_matriz", lambda: a09._JANELA_ANTIGA[0])
    monkeypatch.setattr(a09._daemon, "medir_jogos_com_steam_input", lambda: [])
    import subprocess
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: rodou.append(list(a[0])) or _RC0())

    _clicar(a09.refazer_consertos, ctx)
    carga = _clicar(a09.refazer_consertos, ctx, a09.CONFIRMA)

    assert len(rodou) == len(a09.CONSERTOS), rodou
    for (relpath, args), comando in zip(a09.CONSERTOS, rodou, strict=True):
        assert comando[0] == "bash" and comando[1].endswith(relpath.split("/")[-1])
        assert comando[2:] == args, comando
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
    """Os dois scripts de :data:`CONSERTOS` EXISTEM nesta instalação."""
    a09._JANELA_ANTIGA.clear()
    achados = {str(c) for c, _ in a09._consertos_no_disco()}
    assert len(achados) == len(a09.CONSERTOS), (
        f"o localizador do produto achou {len(achados)} dos {len(a09.CONSERTOS)} "
        f"scripts de `CONSERTOS`: {sorted(achados)}. Um nome errado aqui é um "
        "botão que diz 'Correções aplicadas' sem ter rodado nada.")


def test_as_camadas_recusam_com_jogo_aberto(a09, ctx, monkeypatch):
    """O Wine regrava o registro do prefixo ao sair: escrever agora é perder calado."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    cv.gravar_camadas_da_steam_fora(True)
    cv.gravar_estado({"222": {"x": {"feito": "desligada", "valor_antes": "00000000"}}})
    curou: list[object] = []
    monkeypatch.setattr(rl, "jogo_aberto", lambda: True)
    monkeypatch.setattr(cv, "curar_todos", lambda **k: curou.append(k) or [])
    with pytest.raises(RuntimeError) as recusa:
        a09.corrigir_vulkan(ctx, {}, None)
    assert "jogo aberto" in str(recusa.value)
    assert curou == []
    assert cv.camadas_da_steam_fora() is True


def test_ligar_as_camadas_com_jogo_aberto_nao_recusa(a09, ctx, monkeypatch):
    """Ligar não mexe em registro nenhum: vale no próximo jogo, e não espera."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
    from hefesto_dualsense4unix.integrations import reposicao_dos_lancadores as rl

    curou: list[object] = []
    monkeypatch.setattr(rl, "jogo_aberto", lambda: True)
    monkeypatch.setattr(cv, "curar_todos", lambda **k: curou.append(k) or [])
    a09.corrigir_vulkan(ctx, {}, None)
    assert cv.camadas_da_steam_fora() is True
    assert curou == []


def test_nenhum_dos_cinco_destrutivos_ficou_sem_dono(a09):
    """`SEM_MOTOR` encolheu, e o que sobra tem razão de MECANISMO."""
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


def test_o_tique_escreve_o_status_e_os_tres_ligaveis(a09, ctx):
    """As duas linhas do teto SAÍRAM em 25/09/2026, por pedido (as tabelas"""
    from hefesto_dualsense4unix.interface.pacotes import normalizar

    mesa = normalizar(dict(a09.pacote(ctx)))["mesa"]
    for campo in (a09.CAMPO_DO_STATUS, "hefesto-autostart", "proton-fixado",
                  "vulkan-corrigido", a09.CAMPO_DO_VERDE):
        assert campo in mesa, (
            f"o pacote não escreve em {campo!r}. O endereço está na página e "
            "ninguém o preenche — a tela volta a mostrar o literal do desenho.")
        assert f'data-campo="{campo}"' in _pagina(), campo


def test_o_apelido_da_tela_tem_um_dono_so(a09):
    """O gerador LÊ o apelido daqui — não o digita."""
    import aba09

    assert aba09.APELIDO_NA_TELA == a09.APELIDO_NA_TELA, (
        "o apelido da tela divergiu entre o gerador e o pacote. O dono é o "
        "pacote, e `aba09._constantes` o lê de lá sem importar nada.")


def test_a_frase_do_exame_nomeia_o_botao_que_esta_na_tela(a09):
    """O `storm_doctor` manda clicar num botão que EXISTE nesta página."""
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
    """O gêmeo declarado: o `storm_doctor` e o pacote leem o MESMO botão."""
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
