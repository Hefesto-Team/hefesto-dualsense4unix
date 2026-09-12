#!/usr/bin/env python3
"""AS QUATRO LINHAS DA ABA `09` QUE NENHUMA SPRINT ENCARREGAVA — 06/09/2026.

Elas estavam `FALTA_NO_HTML` no `docs/data/paridade-gtk-html.csv`, e o enunciado
de cada uma é a própria linha do CSV:

* **L315** — o botão **"Corrigir modo de execução"**. A aba já RECONHECIA o modo
  improvisado desde 03/09 (a linha "O serviço está" escreve *"Ligado, em modo
  improvisado"* em laranja) e **não oferecia saída**: quem caísse nele era
  avisado e não tinha botão de conserto;
* **L323** — o **recibo do gesto**. `retomar`, `atualizar`, `autostart` e
  `reiniciar` agiam e o SUCESSO era mudo;
* **L340** — **"Aplicar aos jogos da Steam"**, a metade que APLICA o que o
  «Copiar a linha» da aba Lançadores só entrega na área de transferência;
* **L343** — **"Restaurar de fábrica"**, o último nome de `a09_sistema.SEM_MOTOR`
  (eram cinco em 03/09) e o gesto mais destrutivo da página.

O QUE ESTA RÉGUA MEDE, e em três camadas — cada uma pega o que a de cima não vê:

1. **os GESTOS**, com o motor dublado no ponto em que ele sairia da máquina: o
   que se confere é o que teria ido ao `systemctl`, à Steam e ao disco dela;
2. **o DESENHO**, que carrega os dois botões novos — e o do modo improvisado
   nasce ESCONDIDO, com a regra de CSS que o esconde e o `data-campo` que o
   acende;
3. **a TELA VIVA**, num WebKit de verdade com o piloto do produto: o botão do
   modo improvisado APARECE quando o produto diz que há modo a corrigir e SOME
   quando não há; e os gestos do recibo **piscam verde** ao voltar sem levantar
   — e **não piscam** quando recusam.

A L323 JÁ TINHA MEIA PROVA, e esta régua fecha a outra metade: o
`test_a_aba_09_sistema_fecha_as_linhas` mede a piscada no `atualizar`, um botão
só. Os outros três nunca foram clicados por régua nenhuma — e `autostart` não é
sequer um `<button>`, é a `.chave` do interruptor. Uma régua que prova UM
elemento e conclui sobre quatro é a forma de defeito que esta casa mais paga.

A MORDIDA, colada no relato desta frente:

* apague o `if not _confirmado(o, "aplicar-aos-jogos")` do gesto e
  `test_o_aplicar_aos_jogos_nao_fecha_a_steam_no_primeiro_clique` reprova
  dizendo que a Steam fechou sem consentimento;
* apague a linha `fora[CAMPO_DO_MODO_AVULSO] = …` do `pacote()` e
  `test_o_campo_do_modo_improvisado_sai_em_todo_tique` reprova nos dois
  estados — inclusive no VAZIO, que é o que faz o botão SUMIR de volta;
* troque `if _status_do_daemon(...) != "online_avulso"` por `if False` no
  `corrigir_modo` e `test_o_corrigir_modo_recusa_fora_do_modo_improvisado`
  reprova: o botão passaria a fazer o trabalho do "Ativar o serviço" ao lado;
* tire o `era=era` do `restaurar_de_fabrica` e
  `test_o_restaurar_de_fabrica_adota_o_perfil_como_ativo` reprova — o `.json`
  mudaria no disco e o controle continuaria com o perfil anterior, que é o
  sintoma que ela leu como *"não está salvando"*;
* tire `.so-avulso:not(.mostra){display:none}` do CSS e o GERADOR reprova antes
  desta régua (`aba09.py`, o portão dos dois blocos) — a guarda de lá é mais
  dura, e é ela que responde.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app.actions import daemon_actions as _daemon
from hefesto_dualsense4unix.app.actions import footer_actions as _rodape
from hefesto_dualsense4unix.interface import onde as _onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, normalizar
from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

PAGINA = "09-sistema.html"

#: O DESENHO DE HOJE, e não o publicado — publicar é ato dela, e os dois botões
#: desta frente só existem na bancada até ela aprovar.
BANCADA = _onde.pagina(PAGINA)


def _html() -> str:
    return BANCADA.read_text(encoding="utf-8")


def _ctx(**estado: object) -> Contexto:
    return Contexto(state=dict(estado) or {"active_profile": "regua"},
                    mesa=[], conectados=[], estados={})


class PonteDeMentira:
    """A ponte que RECUSA e RESPONDE, e guarda o que lhe pediram.

    Todo dublê desta casa tem de saber recusar — um que só sabe passar não é
    régua. `chamar` devolve o que `resposta` disser, e o gesto que ler o retorno
    (nenhum destes três lê, hoje) passa a ser exercitado nas duas respostas.
    """

    def __init__(self, resposta: bool = True) -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []
        self.resposta = resposta

    def chamar(self, metodo: str, *a: object, **k: object) -> bool:
        self.chamadas.append((metodo, a, k))
        return self.resposta

    def chamar_detalhado(self, metodo: str, *a: object, **k: object):
        self.chamadas.append((metodo, a, k))
        return (self.resposta, None)

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(("profile_switch", (nome,), {}))
        return self.resposta

    @property
    def metodos(self) -> list[str]:
        return [m for m, _a, _k in self.chamadas]


@pytest.fixture(autouse=True)
def _sem_nada_armado():
    """O consentimento não atravessa dois testes. `_ARMADO` é do módulo."""
    a09._ARMADO.clear()
    a09._LENTO.clear()
    yield
    a09._ARMADO.clear()
    a09._LENTO.clear()


def _confirma(gesto: str) -> dict[str, object]:
    """O clique que CONFIRMA: ele traz o rótulo que só existe no botão armado."""
    return {"gesto": gesto, "texto": a09.CONFIRMA}


# ---------------------------------------------------------------------------
# CAMADA 0 — A DECLARAÇÃO: nenhum dos três pode nascer sem a rede de segurança
# ---------------------------------------------------------------------------
def test_os_tres_gestos_novos_declaram_o_que_mexem() -> None:
    """Sem isto, a prova botão a botão clica os três na máquina dela.

    Ela roda com o daemon vivo e o perfil dela em disco: um clique de régua no
    `corrigir-modo` mata o serviço, um no `aplicar-aos-jogos` FECHA a Steam e
    reescreve a linha de lançamento de todos os jogos, e um no
    `restaurar-de-fabrica` apaga o perfil dela — para provar que sabe clicar.
    """
    from hefesto_dualsense4unix.interface import pacotes

    perigosos = {g for (pg, g) in pacotes.perigosos() if pg == PAGINA}
    for nome in ("corrigir-modo", "aplicar-aos-jogos", "restaurar-de-fabrica"):
        assert (PAGINA, nome) in pacotes.GESTOS, f"`{nome}` não tem dono"
        assert nome in perigosos, (
            f"`{nome}` mexe na máquina dela e NÃO está protegido — declare a "
            'porta no próprio decorador: `@gesto(…, grava="…")`.')


def test_a_lista_dos_sem_motor_ficou_vazia() -> None:
    """`SEM_MOTOR` era cinco, virou um, e agora é zero.

    A lista FICA (vazia) porque as duas réguas que a cobram nos dois sentidos
    continuam valendo — quem está nela não pode ter dono, e todo `DESTRUTIVOS`
    fora dela TEM de ter.
    """
    assert a09.SEM_MOTOR == {}, (
        "há gesto declarado sem motor nesta aba, e os cinco fecharam: "
        f"{sorted(a09.SEM_MOTOR)}")
    assert "aplicar-aos-jogos" in a09.DESTRUTIVOS, (
        "o «Aplicar aos jogos da Steam» fecha a Steam dela e reescreve a linha "
        "de lançamento de TODOS os jogos — ele é destrutivo, e sem estar na "
        "lista o `blocos:` nunca repõe o rótulo do consentimento.")


# ---------------------------------------------------------------------------
# CAMADA 1 — L315: o botão do modo improvisado
# ---------------------------------------------------------------------------
def test_o_corrigir_modo_recusa_fora_do_modo_improvisado(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Em `online_systemd` não há modo a corrigir; em `offline` o trabalho é do
    botão ao lado. Um botão que faz o trabalho do vizinho é o segundo dono de
    um ato."""
    for estado in ("online_systemd", "offline", "iniciando"):
        monkeypatch.setattr(a09, "_status_do_daemon", lambda _s, e=estado: e)
        with pytest.raises(RuntimeError) as erro:
            a09.corrigir_modo(_ctx(), {"gesto": "corrigir-modo"}, PonteDeMentira())
        # A RÉGUA LÊ A FRASE, NÃO A DIGITA — 11/09/2026, A1-036. Ela cobrava a
        # palavra "modo improvisado", que é vocabulário desta casa e saiu da
        # tela por decisão dela; a régua que digita o texto reprova a melhora
        # em vez do defeito. O dono da frase é `a09.NADA_A_CORRIGIR`, e o que
        # se mede aqui é o ATO: fora do modo avulso, o gesto RECUSA.
        assert str(erro.value) == a09.NADA_A_CORRIGIR, (estado, erro.value)


def test_o_corrigir_modo_pede_ao_avulso_que_saia_e_sobe_a_unit(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Os três tempos da janela antiga, na ordem dela — e NADA é reescrito aqui.

    O `systemctl` é dublado no ponto em que ele sairia do processo
    (`_invoke_systemctl`, da janela antiga): o que se confere é o comando que
    TERIA ido ao systemd, e nenhum byte vai ao daemon de quem roda a suíte.
    """
    monkeypatch.setattr(a09, "_status_do_daemon", lambda _s: "online_avulso")
    monkeypatch.setattr(a09._matriz(), "_read_daemon_pid", lambda: 4242)
    saiu: list[int] = []
    monkeypatch.setattr(a09, "_o_avulso_saiu", lambda pid: (saiu.append(pid), True)[1])

    # OS TRÊS PORTÕES DO PRODUTO respondem "pode subir": unit instalada, serviço
    # inativo, nenhum avulso vivo. Quem os consulta é `ativar_o_servico`, e é
    # ele que continua decidindo — o dublê só lhe dá as entradas.
    from hefesto_dualsense4unix.daemon import service_install

    monkeypatch.setattr(service_install.ServiceInstaller, "detect_installed_unit",
                        lambda self: "hefesto-dualsense4unix.service")
    janela = a09._matriz()
    monkeypatch.setattr(janela, "_is_service_active", lambda: "inactive")
    monkeypatch.setattr(janela, "_daemon_pid_alive", lambda: False)
    comandos: list[list[str]] = []

    class _Saiu:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(
        janela, "_invoke_systemctl",
        lambda args, **k: (comandos.append(list(args)), _Saiu())[1])

    fora = a09.corrigir_modo(_ctx(), {"gesto": "corrigir-modo"}, PonteDeMentira())

    assert saiu == [4242], "o pid do Hefesto improvisado não foi convidado a sair"
    assert [c[0] for c in comandos] == ["reset-failed", "start"], comandos
    assert fora["recado"] == _daemon.MIGRAR_DEU_CERTO, (
        "o recibo não é a frase do dono — e ela saiu de dentro do "
        "`_on_migrate_done` hoje justamente para não haver duas.")


def test_o_corrigir_modo_recusa_quando_o_avulso_nao_sai(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A metade que o dublê frouxo esconderia: o caminho de erro é um caminho.

    Sem esta linha, subir a unit com o avulso vivo criaria um SEGUNDO Hefesto
    disputando o mesmo `hidraw` — a BUG-MULTI-INSTANCE-01.
    """
    monkeypatch.setattr(a09, "_status_do_daemon", lambda _s: "online_avulso")
    monkeypatch.setattr(a09._matriz(), "_read_daemon_pid", lambda: 4242)
    monkeypatch.setattr(a09, "_o_avulso_saiu", lambda _pid: False)
    subiu: list[bool] = []
    monkeypatch.setattr(a09, "ativar_o_servico",
                        lambda: (subiu.append(True), True)[1])

    with pytest.raises(RuntimeError) as erro:
        a09.corrigir_modo(_ctx(), {"gesto": "corrigir-modo"}, PonteDeMentira())
    assert _daemon.MIGRAR_NAO_DEU in str(erro.value)
    assert not subiu, (
        "a unit subiu com o Hefesto improvisado ainda vivo — são dois daemons "
        "disputando o mesmo aparelho.")


@pytest.mark.parametrize("estado,esperado",
                         [("online_avulso", a09.MODO_A_CORRIGIR),
                          ("online_systemd", ""),
                          ("offline", "")])
def test_o_campo_do_modo_improvisado_sai_em_todo_tique(
        monkeypatch: pytest.MonkeyPatch, estado: str, esperado: str) -> None:
    """INCLUSIVE VAZIO, e é isso que faz o botão SUMIR de volta.

    Emitir só quando há modo a corrigir deixaria o botão na tela para sempre
    depois do primeiro modo improvisado: o serviço volta ao systemd e o desenho
    continuaria oferecendo um conserto que já aconteceu.
    """
    monkeypatch.setattr(a09, "_status_do_daemon", lambda _s: estado)
    a09._LENTO.clear()
    saiu = normalizar(dict(a09.pacote(_ctx())))["mesa"]
    assert a09.CAMPO_DO_MODO_AVULSO in saiu, (
        f"o pacote não emitiu `{a09.CAMPO_DO_MODO_AVULSO}` com o serviço em "
        f"{estado!r} — o botão fica congelado no estado da volta anterior.")
    assert saiu[a09.CAMPO_DO_MODO_AVULSO] == esperado


def test_o_campo_do_modo_improvisado_sai_ate_quando_a_camada_levanta(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O caminho de ERRO diz o mesmo que o de sucesso — a lição do `blocos:`.

    Com o serviço parado a camada do produto levanta e este ramo responde. Ele
    já carregava os rótulos dos botões e as razões do cinza pela mesma razão:
    a tela não pode apagar a metade que explica no minuto em que ela é a única
    coisa que importa.
    """
    monkeypatch.setattr(a09._tela, "pacote",
                        lambda _l: (_ for _ in ()).throw(RuntimeError("caiu")))
    monkeypatch.setattr(a09, "_status_do_daemon", lambda _s: "online_avulso")
    a09._LENTO.clear()
    bruto = dict(a09.pacote(_ctx()))
    assert bruto.get("sem_dono"), "o ramo de erro não foi exercido"
    assert bruto[a09.CAMPO_DO_MODO_AVULSO] == a09.MODO_A_CORRIGIR


# ---------------------------------------------------------------------------
# CAMADA 1 — L340: "Aplicar aos jogos da Steam"
# ---------------------------------------------------------------------------
def _com_a_steam(monkeypatch: pytest.MonkeyPatch, *, janela: str = "ok",
                 resultado: object = None) -> dict[str, list]:
    """Dubla o motor da Steam no ponto em que ele MEXERIA na máquina dela."""
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    visto: dict[str, list] = {"fechou": [], "aplicou": []}

    def _aplicar() -> dict[str, object]:
        visto["aplicou"].append(True)
        return resultado if resultado is not None else {
            "applied": 3, "skipped": 0, "errors": 0}

    def _com_a_steam_fechada(acao):
        visto["fechou"].append(True)
        return (janela, acao() if janela == "ok" else None)

    monkeypatch.setattr(slo, "apply_wrapper_to_all_games", _aplicar,
                        raising=False)
    monkeypatch.setattr(slo, "with_steam_closed", _com_a_steam_fechada)
    return visto


def test_o_aplicar_aos_jogos_nao_fecha_a_steam_no_primeiro_clique(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O consentimento é EXIGÊNCIA DO MOTOR: `with_steam_closed` fecha a Steam
    dela por uns 20 segundos, e o primeiro clique só PERGUNTA."""
    visto = _com_a_steam(monkeypatch)
    fora = a09.aplicar_aos_jogos(
        _ctx(), {"gesto": "aplicar-aos-jogos", "texto": "Aplicar aos jogos da Steam"},
        PonteDeMentira())
    assert visto["fechou"] == [] and visto["aplicou"] == [], (
        "a Steam dela foi fechada no PRIMEIRO clique — o consentimento sumiu.")
    assert a09.CONFIRMA in str(fora["blocos"]), fora["blocos"]
    # A FRASE DA PERGUNTA É A DO DONO, palavra por palavra. Uma segunda cópia
    # aqui se afastaria dela no primeiro dia em que alguém mexesse numa das duas.
    esperada = " ".join(_daemon.DaemonActionsMixin._STEAM_APPLY_CORPO.split())
    assert fora["recado"] == esperada


def test_o_segundo_clique_aplica_o_atalho_a_todos_os_jogos(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """E o recibo é o do produto, com o número que ele contou."""
    visto = _com_a_steam(monkeypatch)
    a09.aplicar_aos_jogos(
        _ctx(), {"gesto": "aplicar-aos-jogos", "texto": "Aplicar aos jogos da Steam"},
        PonteDeMentira())
    fora = a09.aplicar_aos_jogos(_ctx(), _confirma("aplicar-aos-jogos"),
                                PonteDeMentira())
    assert visto["fechou"] == [True] and visto["aplicou"] == [True]
    assert fora["recado"] == _daemon.format_apply_wrapper_result(
        {"applied": 3, "skipped": 0, "errors": 0})
    assert "3 jogo(s)" in fora["recado"], fora["recado"]


def test_o_jogo_aberto_recusa_com_a_frase_do_dono(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O dublê tem de saber RECUSAR, e a recusa não é uma frase minha.

    `format_steam_janela_recusa` cobre os três desfechos do motor; escrever a
    frase aqui seria o segundo dono de um texto de tela.
    """
    _com_a_steam(monkeypatch, janela="jogo_aberto")
    a09.aplicar_aos_jogos(
        _ctx(), {"gesto": "aplicar-aos-jogos", "texto": "x"}, PonteDeMentira())
    with pytest.raises(RuntimeError) as erro:
        a09.aplicar_aos_jogos(_ctx(), _confirma("aplicar-aos-jogos"),
                              PonteDeMentira())
    assert str(erro.value) == _daemon.format_steam_janela_recusa("jogo_aberto")
    assert "jogo aberto" in str(erro.value)


def test_a_instalacao_sem_aplicacao_em_massa_recusa_dizendo_como_atualizar(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O contrato PATH-06: `getattr` defensivo, e a frase é a do produto."""
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    monkeypatch.delattr(slo, "apply_wrapper_to_all_games", raising=False)
    with pytest.raises(RuntimeError) as erro:
        a09.aplicar_aos_jogos(_ctx(), _confirma("aplicar-aos-jogos"),
                              PonteDeMentira())
    assert str(erro.value) == _daemon.frase_sem_aplicacao_em_massa()


# ---------------------------------------------------------------------------
# CAMADA 1 — L343: "Restaurar de fábrica"
# ---------------------------------------------------------------------------
@pytest.fixture()
def _preset(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """Um preset de mentira no lugar do asset — e o disco dela fica intacto."""
    from hefesto_dualsense4unix.profiles import loader

    # O PRESET É O DE VERDADE, copiado para um `tmp_path` — o disco dela fica
    # intacto e a régua mede o arquivo que o produto realmente instala. Um JSON
    # montado à mão aqui seria um segundo esqueleto de `Profile`, e o primeiro
    # que o `schema` mudasse deixaria a régua verde sobre um formato morto.
    #
    # O NOME É TROCADO DE PROPÓSITO: é assim que se prova a
    # PERFIL-PADRAO-PERSONALIZADO-01 — o asset pode ser o de uma versão
    # anterior, e o gesto tem de gravar a identidade de HOJE, venha ele de onde
    # vier.
    de_verdade = json.loads(
        _rodape._meu_perfil_asset().read_text(encoding="utf-8"))
    de_verdade["name"] = "nome-velho-do-asset"
    caminho = tmp_path / "personalizado.json"
    caminho.write_text(json.dumps(de_verdade), encoding="utf-8")
    monkeypatch.setattr(_rodape, "_meu_perfil_asset", lambda: caminho)
    gravados: list[object] = []
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **k: (gravados.append(prof), caminho)[1])
    return gravados


def test_o_restaurar_de_fabrica_nao_grava_no_primeiro_clique(_preset) -> None:
    """Ele é o gesto mais destrutivo da página: o primeiro clique só arma."""
    fora = a09.restaurar_de_fabrica(
        _ctx(), {"gesto": "restaurar-de-fabrica", "texto": "Restaurar de fábrica"},
        PonteDeMentira())
    assert _preset == [], "o perfil dela foi restaurado sem consentimento"
    assert a09.CONFIRMA in str(fora["blocos"])


def test_o_restaurar_de_fabrica_adota_o_perfil_como_ativo(
        _preset, monkeypatch: pytest.MonkeyPatch) -> None:
    """Os TRÊS tempos do dono: disco, `profile.switch` e `launch_env.refresh`.

    O `era=` é o que faz o `switch` sair. Sem ele o `.json` muda no disco e o
    controle continua com o perfil anterior — o sintoma que ela leu como *"não
    está salvando"*.
    """
    from hefesto_dualsense4unix.app.actions import profiles_actions

    class _Vale:
        nome = "Mortal Kombat"

    monkeypatch.setattr(profiles_actions, "perfil_que_esta_valendo",
                        lambda _s=None: _Vale())
    ponte = PonteDeMentira()
    a09.restaurar_de_fabrica(
        _ctx(), {"gesto": "restaurar-de-fabrica", "texto": "x"}, ponte)
    fora = a09.restaurar_de_fabrica(_ctx(), _confirma("restaurar-de-fabrica"),
                                    ponte)

    assert len(_preset) == 1, "o perfil de fábrica não foi gravado"
    assert ponte.metodos == ["profile_switch", "launch_env.refresh"], (
        "o perfil foi gravado no disco e o controle não foi avisado — "
        f"{ponte.chamadas}")
    assert ponte.chamadas[0][1] == (_preset[0].name,), ponte.chamadas
    assert fora["recado"] == _rodape.frase_do_restauro()


def test_a_identidade_e_decidida_aqui_e_nao_pelo_arquivo_achado(
        _preset, monkeypatch: pytest.MonkeyPatch) -> None:
    """PERFIL-PADRAO-PERSONALIZADO-01: o asset pode ser o de uma versão
    anterior, e gravar o nome que veio dele criaria de volta o catch-all que ela
    mandou aposentar."""
    from hefesto_dualsense4unix.app.actions import profiles_actions
    from hefesto_dualsense4unix.profiles.loader import NOME_DO_PADRAO

    monkeypatch.setattr(profiles_actions, "perfil_que_esta_valendo",
                        lambda _s=None: type("V", (), {"nome": "x"})())
    a09.restaurar_de_fabrica(_ctx(), {"gesto": "restaurar-de-fabrica"},
                             PonteDeMentira())
    a09.restaurar_de_fabrica(_ctx(), _confirma("restaurar-de-fabrica"),
                             PonteDeMentira())
    assert _preset[0].name == NOME_DO_PADRAO, (
        f"gravou {_preset[0].name!r} — o nome do arquivo achado, e não o do "
        "perfil de hoje.")


def test_o_preset_ausente_recusa_na_lingua_dela(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A frase era dev-fala num toast desde 23/08 (*"Asset 'personalizado.json'
    não encontrado — Restaurar Default indisponível"*), e a régua da palavra a
    carregava como dívida declarada. Trocá-la no DONO pagou os dois chamadores
    de uma vez."""
    monkeypatch.setattr(_rodape, "_meu_perfil_asset", lambda: None)
    with pytest.raises(RuntimeError) as erro:
        a09.restaurar_de_fabrica(_ctx(), _confirma("restaurar-de-fabrica"),
                                 PonteDeMentira())
    assert str(erro.value) == _rodape.frase_do_preset_ausente()
    for jargao in ("Asset", "Restaurar Default", ".json"):
        assert jargao not in str(erro.value), (jargao, erro.value)


# ---------------------------------------------------------------------------
# CAMADA 2 — O DESENHO
# ---------------------------------------------------------------------------
def test_o_desenho_tem_os_dois_botoes_novos() -> None:
    pagina = _html()
    for gesto in ("corrigir-modo", "aplicar-aos-jogos"):
        assert f'data-gesto="{gesto}"' in pagina, (
            f"o botão de {gesto!r} não está na bancada — rode "
            "`src/hefesto_dualsense4unix/interface/aba09.py`.")


def test_o_botao_do_modo_improvisado_nasce_escondido() -> None:
    """A cena que ela aprovou não muda um pixel: no desenho o serviço está de pé
    pelo systemd, e a regra tira o botão do FLUXO — não só da vista."""
    import re

    pagina = _html()
    assert ".so-avulso:not(.mostra){display:none}" in pagina, (
        "a regra que esconde o botão do modo improvisado sumiu — ele passa a "
        "ocupar 30px na coluna do serviço na cena que ela aprovou.")
    botao = re.search(r'<button class="[^"]*so-avulso[^"]*"[^>]*>', pagina)
    assert botao, "o botão perdeu a classe `so-avulso`"
    for exigido in (f'data-campo="{a09.CAMPO_DO_MODO_AVULSO}"',
                    'data-hef-alvo="classe"', 'data-hef-classe="mostra"',
                    'data-gesto="corrigir-modo"'):
        assert exigido in botao.group(0), (exigido, botao.group(0))


def test_o_endereco_do_botao_escondido_tem_um_dono_so() -> None:
    """O gerador LÊ o nome do pacote por AST. Escrito duas vezes, os dois se
    afastam no dia em que alguém mudar um — foi assim que a fita viva morreu em
    silêncio em 27/08."""
    import aba09

    assert aba09.CAMPO_DO_MODO_AVULSO == a09.CAMPO_DO_MODO_AVULSO


def test_a_declaracao_do_que_espera_a_publicacao_bate_com_a_pagina() -> None:
    """O que está declarado como "espera a publicação" NÃO pode estar publicado.

    A RÉGUA MUDOU DE ALVO EM 07/09/2026, e a razão é a que esta casa repete:
    *a régua media o mundo de ontem*.  # (noqa-acento: verbo medir, imperfeito)
    A versão anterior cravava UM campo
    (`CAMPO_DO_MODO_AVULSO`) e exigia que ele estivesse fora da página E dentro
    da declaração. Ela mandou publicar as dez abas para os quatro DualSense
    aparecerem na bancada, os cinco campos chegaram à página — e a régua passou
    a reprovar a publicação que ela pediu, em vez de reprovar defeito.

    O QUE SOBREVIVE É O INVARIANTE, e ele vale para qualquer campo: **declarar
    o que já está publicado é mentira, e é isso que se cobra**. O outro sentido
    — campo do gerador que não chegou à página e ninguém declarou — é do
    `_conferir` da aba, que lê o documento inteiro; aqui seria régua medindo a
    própria saída, porque a lista de campos viria do mesmo módulo.

    Um dicionário VAZIO passa, e é a resposta certa quando não há nada
    esperando. A régua volta a morder na próxima aba que nascer com campo sem
    página.
    """
    publicada = _onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    mentindo = [campo for campo in a09.ESPERA_A_PUBLICACAO
                if f'data-campo="{campo}"' in publicada]
    assert not mentindo, (
        f"{len(mentindo)} campo(s) declarados em `ESPERA_A_PUBLICACAO` JÁ estão "
        f"na página publicada: {sorted(mentindo)}. Publicar é ato dela; a "
        f"declaração é que envelheceu — TIRE a linha de cada um.")


# ---------------------------------------------------------------------------
# CAMADA 3 — A TELA VIVA, num WebKit de verdade
# ---------------------------------------------------------------------------
#: O QUE A RÉGUA LÊ DA PÁGINA. Ela pergunta pelo que se VÊ (`display` vem do
#: CSSOM), e não pela classe: a classe é o mecanismo, e a pergunta é se a pessoa
#: enxerga o botão.
LER_A_TELA = r"""
(function(){
  const b = document.querySelector('[data-gesto="corrigir-modo"]');
  const r = document.querySelector('[data-gesto="reiniciar"]');
  const alvos = {};
  for(const g of ['retomar','reiniciar','autostart','atualizar']){
    const e = document.querySelector('[data-gesto="' + g + '"]');
    alvos[g] = e ? {verde: e.classList.contains('hef-deu-certo'),
                    em_voo: e.classList.contains('hef-em-voo')} : null;
  }
  const m = document.querySelector('.janela > .miolo') ||
            document.querySelector('.miolo');
  return JSON.stringify({
    corrigir: b ? {visivel: getComputedStyle(b).display !== 'none',
                   rotulo: (b.textContent || '').trim()} : null,
    // O VIZINHO QUE SAI NO LUGAR DELE. A pergunta é de PIXEL: quem ela vê é o
    // `.acao` que embrulha o Reiniciar, e é o `display` dele que o CSS troca.
    reiniciar: r ? {visivel: getComputedStyle(r.closest('.acao') || r)
                              .display !== 'none'} : null,
    alvos: alvos,
    rola_por_dentro: m ? Math.max(0, m.scrollHeight - m.clientHeight) : null,
  });
})()
"""

CLICAR = r"""
(function(){
  const nomes = ['retomar','reiniciar','autostart','atualizar'];
  let n = 0;
  for(const g of nomes){
    const e = document.querySelector('[data-gesto="' + g + '"]');
    if(e){ e.click(); n += 1; }
  }
  return String(n);
})()
"""


@pytest.fixture(scope="module")
def na_tela() -> dict:
    """Abre o DESENHO DE HOJE no motor do produto, oculto, e mede.

    A JANELA NASCE NO `Xvfb` da guarda TELA-DELA-01 — ela tem UMA tela, e uma
    janela que nasce na frente dela quebra o que ela está fazendo.

    OS GESTOS SÃO DUBLÊS REGISTRADOS NO `pacotes.GESTOS`, que é o mesmo lugar de
    onde o piloto lê: o caminho INTEIRO do clique é exercitado — ouvinte, voo,
    thread, pouso — e **nada vai ao daemon dela**. Sem isso, clicar `reiniciar`
    aqui reiniciaria o serviço de quem roda a suíte.
    """
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse
    import tempfile
    import time as _time

    import hefesto_vivo as hv

    berco = pathlib.Path(tempfile.mkdtemp(prefix="a09-quatro-"))
    shutil.copytree(_onde.PUBLICADO, berco / "paginas",  # (noqa-acento) PASTA
                    dirs_exist_ok=True)
    shutil.copy2(BANCADA, berco / "paginas" / PAGINA)  # (noqa-acento) PASTA

    chaves = [(PAGINA, g) for g in ("retomar", "reiniciar", "autostart",
                                    "atualizar")]
    guardado = (hv.onde.PUBLICADO, hv.mesa_viva.estado_do_daemon,
                hv.pacotes.PACOTES.get(PAGINA),
                {c: hv.pacotes.GESTOS.get(c) for c in chaves})
    hv.onde.PUBLICADO = berco / "paginas"  # type: ignore[assignment]  # (noqa-acento) PASTA
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: {"active_profile": "regua"}  # type: ignore[assignment]

    # OS DUBLÊS: três voltam sem levantar (o sucesso calado) e um RECUSA. Um
    # dublê que só sabe passar não é régua — e é a recusa que prova que a
    # piscada verde não é um carimbo automático do pouso.
    for pagina, nome in chaves[:3]:
        hv.pacotes.GESTOS[(pagina, nome)] = (  # type: ignore[assignment]
            lambda ctx, o, p: None)
    hv.pacotes.GESTOS[chaves[3]] = (  # type: ignore[assignment]
        lambda ctx, o, p: (_ for _ in ()).throw(RuntimeError("recusei de propósito")))

    carga = {"o_que": {a09.CAMPO_DO_MODO_AVULSO: a09.MODO_A_CORRIGIR}}
    hv.pacotes.PACOTES[PAGINA] = lambda ctx: dict(carga["o_que"])  # type: ignore[assignment]

    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre=PAGINA, prova_no_aparelho=False, entre=2500, espera=1200,
        incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)
    fora: dict[str, object] = {}

    def ler(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = (f"ERRO {erro}" if erro is not None
                            else json.loads(str(valor)))
        return _leu

    def anotar(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = f"ERRO {erro}" if erro is not None else str(valor)
        return _leu

    def com_o_modo_improvisado() -> bool:
        if not piloto.pronto:
            return True
        piloto.ponte.perguntar(LER_A_TELA, ler("com-o-modo"))
        GLib.timeout_add(700, sem_o_modo_improvisado)
        return False

    def sem_o_modo_improvisado() -> bool:
        carga["o_que"] = {a09.CAMPO_DO_MODO_AVULSO: ""}
        GLib.timeout_add(700, leu_sem_o_modo)
        return False

    def leu_sem_o_modo() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("sem-o-modo"))
        GLib.timeout_add(300, clicar)
        return False

    def clicar() -> bool:
        piloto.ponte.perguntar(CLICAR, anotar("cliques"))
        GLib.timeout_add(900, depois_do_pouso)
        return False

    def depois_do_pouso() -> bool:
        piloto.ponte.perguntar(LER_A_TELA, ler("depois-do-pouso"))
        GLib.timeout_add(400, fim)
        return False

    def fim() -> bool:
        fora["fim"] = True
        Gtk.main_quit()
        return False

    GLib.timeout_add(400, lambda: piloto._ir(PAGINA))
    GLib.timeout_add(1800, com_o_modo_improvisado)
    guarda = GLib.timeout_add(60000, Gtk.main_quit)
    try:
        limite = _time.monotonic() + 60.0
        while "fim" not in fora and _time.monotonic() < limite:
            Gtk.main()
    finally:
        GLib.source_remove(guarda)
        piloto.pronto = False
        piloto.tela.janela.destroy()
        (hv.onde.PUBLICADO, hv.mesa_viva.estado_do_daemon, pacote_antigo,
         gestos_antigos) = guardado
        if pacote_antigo is not None:
            hv.pacotes.PACOTES[PAGINA] = pacote_antigo
        for chave, antigo in gestos_antigos.items():
            if antigo is not None:
                hv.pacotes.GESTOS[chave] = antigo
            else:
                hv.pacotes.GESTOS.pop(chave, None)
        shutil.rmtree(berco, ignore_errors=True)
    if "depois-do-pouso" not in fora:
        pytest.fail(f"o roteiro não chegou ao fim: {sorted(fora)}")
    return fora


class TestNaTelaViva:
    """A peça medida onde ela vive: no motor que ela usa."""

    def test_o_botao_do_modo_improvisado_aparece_quando_ha_o_que_corrigir(
            self, na_tela: dict) -> None:
        visto = na_tela["com-o-modo"]["corrigir"]
        assert visto is not None, "o botão sumiu da página"
        assert visto["visivel"] is True, visto
        # O RÓTULO MUDOU POR DECISÃO DELA — 11/09/2026, A1-012: *"modo de
        # execução"* é vocabulário de quem construiu, e o que acontece no
        # clique é o serviço sair e subir do jeito certo. O `data-gesto`
        # (`corrigir-modo`) NÃO mudou: é endereço de contrato, e é por ele que
        # o roteiro acha o botão — este `assert` confere que achou o certo.
        assert visto["rotulo"] == "Corrigir o serviço", visto

    def test_ele_entra_no_lugar_do_reiniciar_e_nao_ao_lado(
            self, na_tela: dict) -> None:
        """A troca, medida no CSSOM — e ela é de altura e de verdade.

        DE ALTURA: com cinco botões a coluna do serviço mede 194px contra 156
        do Perfil de Bateria, e a aba passa a rolar 38px por dentro (medido
        aqui, antes da troca). Esta faixa promete que as colunas irmãs acabam
        no mesmo y.

        DE VERDADE: no modo improvisado o «Reiniciar o serviço» é justamente o
        clique que NÃO funciona — `systemctl restart` sobe a unit, e a unit
        encontra o Hefesto avulso segurando a instância única.
        """
        com = na_tela["com-o-modo"]
        sem = na_tela["sem-o-modo"]
        assert com["reiniciar"]["visivel"] is False, (
            "os dois estão na tela ao mesmo tempo — a coluna cresce, a aba "
            f"rola, e um dos dois cliques não funciona: {com}")
        assert sem["reiniciar"]["visivel"] is True, (
            f"o «Reiniciar o serviço» não voltou quando o modo passou: {sem}")

    def test_e_some_de_volta_quando_o_modo_passa(self, na_tela: dict) -> None:
        """A metade que faz a peça ser um ESTADO e não um carimbo.

        Sem ela, o botão ficaria na tela para sempre depois do primeiro modo
        improvisado — oferecendo um conserto que já aconteceu.
        """
        assert na_tela["sem-o-modo"]["corrigir"]["visivel"] is False, (
            na_tela["sem-o-modo"]["corrigir"])

    def test_a_aba_nao_rola_por_dentro_com_o_botao_a_mostra(
            self, na_tela: dict) -> None:
        """O preço final de a coluna crescer, e é o que ela VÊ."""
        for quando in ("com-o-modo", "sem-o-modo", "depois-do-pouso"):
            assert na_tela[quando]["rola_por_dentro"] == 0, (
                f"{quando}: o miolo rola {na_tela[quando]['rola_por_dentro']}px "
                "por dentro — foi assim que a aba escondeu 93px em 28/08.")

    def test_o_recibo_do_gesto_pisca_nos_tres_que_eram_mudos(
            self, na_tela: dict) -> None:
        """A **L323**, medida nos que ninguém tinha clicado.

        `retomar`, `reiniciar` e `autostart` agiam e o SUCESSO era mudo. Quem
        responde é a piscada verde da `03-Q4` (`hef-deu-certo`), e ela alcança
        os três — inclusive o `autostart`, que **não é um `<button>`**: é a
        `.chave` do interruptor, e a folha da casa pinta `outline`, que qualquer
        elemento aceita.
        """
        assert na_tela["cliques"] == "4", na_tela["cliques"]
        for nome in ("retomar", "reiniciar", "autostart"):
            visto = na_tela["depois-do-pouso"]["alvos"][nome]
            assert visto is not None, f"{nome} não está na página"
            assert visto["verde"] is True, (
                f"`{nome}` voltou sem levantar e a tela não disse nada — é o "
                f"buraco da L323: {visto}")
            assert visto["em_voo"] is False, (
                f"`{nome}` ficou 'trabalhando' depois de pousar: {visto}")

    def test_e_nao_pisca_no_que_recusou(self, na_tela: dict) -> None:
        """A MORDIDA da piscada: um carimbo automático do pouso passaria nas
        três linhas acima e mentiria aqui.

        `certo` chega do `finally` do piloto, que é quem sabe qual dos três
        desfechos aconteceu — e o default é `False` de propósito.

        O BOTÃO É O «Atualizar», e ele é o mesmo que a régua irmã
        (`test_a_aba_09_sistema_fecha_as_linhas`) usa para provar a piscada NO
        SUCESSO. Os dois lados do mesmo botão, em duas réguas: lá o dublê volta
        sem levantar e ele pisca; aqui o dublê RECUSA e ele não pode piscar.
        """
        visto = na_tela["depois-do-pouso"]["alvos"]["atualizar"]
        assert visto is not None, (
            "o botão da recusa não existe na página — sem ele esta régua não "
            "mede nada, e um seletor que casa ZERO é erro, não silêncio.")
        assert visto["verde"] is False, (
            "o gesto RECUSOU e o campo piscou verde — a tela dizendo as duas "
            f"coisas de uma vez: {visto}")
