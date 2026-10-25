"""Todo gesto que muda uma escolha do usuário grava no clique — ou diz por que não é escolha."""
from __future__ import annotations

import ast
import inspect
import pathlib

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa o `hefesto_vivo`, o piloto, que é moldura e carrega o GTK")

from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface import hefesto_vivo  # noqa: F401
from tests.unit import test_todo_gesto_que_grava_esta_protegido as protegido

Chave = tuple[str, str]

GRAVAM_SEM_DECLARAR: dict[Chave, str] = {
    ("02-controles.html", "sensor"):
        "`sensor.set`: o daemon grava `ControllerOverrides.sensores` no perfil "
        "que vale (`_handle_sensor_set` → `save_profile`); a outra ponta é "
        "conferida em `test_o_sensor_grava_pelo_daemon`",
    ("*", "importar"):
        "o perfil que ela escolhe no seletor do sistema entra na pasta de "
        "perfis dela (`write_text`), sem sobrescrever nenhum",
    ("10-perfis.html", "ordenar"):
        "a ordem da lista vai ao `gui_preferences.json` dela, o arquivo da "
        "janela (`_prefs`); nenhum perfil nem aparelho muda",
    ("10-perfis.html", "largura-da-coluna"):
        "a largura da coluna vai ao `gui_preferences.json` dela, o arquivo da "
        "janela (`_prefs`); nenhum perfil nem aparelho muda",
}

_RASCUNHO_DO_MAPA = (
    "rascunho da tela: a escolha espera o «Guardar» do mapa do controle, que "
    "declara `grava=`; gravar a cada clique salvaria meia escolha")
_LACO_DO_MAPEAR = (
    "tela do «Mapear entrada a entrada»: as fases do laço; cada resposta "
    "grava no gesto dela (`responder`, `nao_alcanco`, que declaram `grava=`)")
_PERGUNTA_DO_HUB = (
    "tela: abre ou fecha a pergunta do hub (`perguntando_o_hub`); quem liga "
    "o hub e grava o mapa é o «Gravar» dela (`novo-hub-gravar`), que declara `grava=`")
_PERGUNTA_DO_RADIO = (
    "abre a pergunta do rádio; quem muda o pareamento é a confirmação dela, "
    "que declara `grava=`")

ATOS: dict[Chave, str] = {
    ("03-gatilhos.html", "sentir"):
        "ato: toca o efeito da área de criar nos gatilhos do controle e devolve o que ele "
        "recebia antes; nenhuma escolha dela muda (A-ABA-GATILHOS-DO-TODO-01)",
    ("*", "aplicar"):
        "ato: manda o perfil do disco aos controles e não muda escolha "
        "nenhuma (`D-2709-O-SALVAR-LE-O-PERFIL`)",
    ("*", "exportar"):
        "ato: copia o arquivo do perfil para FORA, onde ela escolhe; nenhum "
        "perfil nem aparelho dela muda",
    ("*", "menu-atualizar"):
        "ato: o botão direito manda reler o que o Hefesto lê (`daemon.reload`); "
        "nenhuma escolha dela muda (A-BASE-COMUM-DAS-ABAS-01)",
    ("*", "menu-reconectar"):
        "ato: o botão direito chama o «Reconectar» da aba Jogar (`coop.sync` e "
        "`identity.renumber`); nenhuma escolha muda (19/10/2026)",
    ("*", "escolher-na-fita"):
        "tela: o chip do «Selecionar:» só escolhe qual controle a aba mira "
        "(`hefesto_vivo.ESCOLHA_DA_FITA`); nada de perfil. O «Todos» também devolve o alvo "
        "de saída do serviço a todos (`controller.target.set` com `index: null`), que é "
        "estado do serviço e não escolha guardada",
    ("01-jogar.html", "reconectar"):
        "ato: os jogadores voltam e a numeração se ajeita (`coop.sync`); o que "
        "sobra é o estado da mesa, não um campo de perfil",
    ("02-controles.html", "mic-retorno"):
        "sessão: o retorno do microfone (ouvir a própria voz) é um teste do "
        "momento, e desligar ou fechar a janela o encerra",
    ("04-iluminacao.html", "player"):
        "sessão da mesa: o número do jogador é de quem segura qual lugar, e o "
        "registro de identidade do daemon é o dono dele — não é campo do perfil",
    ("05-vibracao.html", "testar"):
        "sessão: o teste segura os motores enquanto ela olha (o coração da "
        "janela), e nada vai ao perfil — ordem dela de 15/09",
    ("05-vibracao.html", "parar"):
        "sessão: corta o teste daquele controle e devolve os motores ao jogo; "
        "parar não muda a vibração no jogo — ordem dela de 15/09",
    ("05-vibracao.html", "testar-haptica"):
        "sessão: o teste «Háptica» toca a vibração fina daquele controle até o "
        "«Parar» (o coração da janela o rebate), e nada vai ao perfil",
    ("mapa-do-controle.html", "mapa-botao"): _RASCUNHO_DO_MAPA,
    ("mapa-do-controle.html", "mapa-cancelar"): _RASCUNHO_DO_MAPA,
    ("mapa-do-controle.html", "mapa-escolher"): _RASCUNHO_DO_MAPA,
    ("mapa-do-controle.html", "mapa-gravar-tecla"): _RASCUNHO_DO_MAPA,
    ("mapa-do-controle.html", "mapa-mover-com"): _RASCUNHO_DO_MAPA,
    ("mapa-do-controle.html", "mapa-nome"): _RASCUNHO_DO_MAPA,
    ("mapa-do-controle.html", "mapa-padrao"): _RASCUNHO_DO_MAPA,
    ("mapa-do-controle.html", "mapa-perfil"): _RASCUNHO_DO_MAPA,
    ("mapa-do-controle.html", "mapa-usar-em"): _RASCUNHO_DO_MAPA,
    ("mapa-do-controle.html", "mapa-sequencia-gravar"):
        "sessão: o daemon ouve o controle até o segundo clique e a faixa de passos é rascunho "
        "da tela; quem grava no perfil é o «Guardar» do mapa, que declara `grava=`",
    ("mapa-do-controle.html", "mapa-sequencia-jeito"): _RASCUNHO_DO_MAPA,
    ("mapa-do-controle.html", "mapa-sequencia-ritmo"): _RASCUNHO_DO_MAPA,
    ("mapa-do-controle.html", "mapa-sequencia-tocar"):
        "sessão: o «Tocar para ouvir» toca a sequência de agora uma vez no pad virtual, sem "
        "guardar nada; quem grava é o «Guardar» do mapa",
    ("07-lancadores.html", "criar-perfil-para-um-jogo"):
        "abre a escolha do jogo; quem grava é o «Criar» de cada linha "
        "(`criar-perfil-do-jogo`), que declara `grava=`",
    ("07-lancadores.html", "configurar-lancador"):
        "tela: abre a janela «Configurar» do lançador (onde está, como entrou e, na Steam, os "
        "impedimentos lidos agora); quem muda algo é o gesto de lá, que declara `grava=`",
    ("07-lancadores.html", "configurar-modificacao"):
        "tela: abre a janela de opções da extensão com o valor de agora; quem grava as opções "
        "é o Guardar dela (`guardar-modificacao`), que declara `grava=`",
    ("07-lancadores.html", "cancelar-modificacao"):
        "rascunho da janela da extensão: o Cancelar joga o rascunho fora e devolve à extensão o "
        "modo guardado do controle livre; nada se grava, o guardado é o que volta",
    ("07-lancadores.html", "guardar-opcao-da-modificacao"):
        "rascunho da janela da extensão: a opção mudada espera o Guardar "
        "(`guardar-modificacao`), que declara `grava=`; gravar a cada clique salvaria meia escolha",
    ("07-lancadores.html", "escolher-o-lancador"):
        "rascunho da janela «Configurar»: o atalho apontado espera o Guardar "
        "(`guardar-lancador`), que declara `grava=`",
    ("07-lancadores.html", "identificar-lancador"):
        "leitura: esquece o cache, procura o lançador no disco de novo e diz onde ele está",
    ("07-lancadores.html", "parar-tudo-da-modificacao"):
        "ato: o serviço publica o gesto «para» só àquela extensão (`mods.parar_tudo`), e os "
        "aparelhos dela vão a zero; o nível e o perfil guardados não mudam",
    ("07-lancadores.html", "acao-da-modificacao"):
        "ato: o serviço leva o clique só àquela extensão (`mods.acao`), e quem age no aparelho é "
        "ela; nenhuma escolha guardada muda no Hefesto",
    ("07-lancadores.html", "mover-o-livre-da-modificacao"):
        "ato: o arrastar do controle livre vai à extensão (`mods.livre`, 20 por segundo); nada "
        "fica guardado",
    ("07-lancadores.html", "soltar-o-livre-da-modificacao"):
        "ato: o soltar da barra do controle livre vai à extensão com o valor final; nada fica "
        "guardado",
    ("07-lancadores.html", "gravar-o-livre-da-modificacao"):
        "rascunho da janela da extensão: a forma gravada espera o Guardar "
        "(`guardar-modificacao`), que declara `grava=`",
    ("07-lancadores.html", "esquecer-a-forma-do-livre"):
        "rascunho da janela da extensão: a forma esquecida sai no Guardar "
        "(`guardar-modificacao`), que declara `grava=`",
    ("07-lancadores.html", "modo-do-livre-da-modificacao"):
        "rascunho da janela da extensão: o modo do controle livre espera o Guardar "
        "(`guardar-modificacao`), que declara `grava=`; a barra e a extensão o seguem na hora",
    ("07-lancadores.html", "ver-impedimentos"):
        "leitura: sonda a Steam de novo e abre a lista dos impedimentos; quem cura é o "
        "«Resolver», que declara `grava=`",
    ("08-conexoes.html", "abrir-adaptador"):
        "tela: abre um adaptador e fecha os outros (o acordeão)",
    ("08-conexoes.html", "aceitar-sugestao"): _PERGUNTA_DO_RADIO,
    ("08-conexoes.html", "aparelho-menu"):
        "tela: abre o menu «⋮» da linha; quem muda o pareamento é o "
        "«Esquecer» de lá, confirmado na pergunta, que declara `grava=`",
    ("08-conexoes.html", "adaptador-historico"):
        "leitura: o que aconteceu com este adaptador, pela hora",
    ("08-conexoes.html", "alvo"):
        "sessão: para qual controle as ações de saída miram agora "
        "(`controller.target.set`)",
    ("08-conexoes.html", "cancelar-mudanca"):
        "ato: cancela a pergunta do rádio, e nada muda no pareamento",
    ("08-conexoes.html", "entrada-comecar"): _LACO_DO_MAPEAR,
    ("08-conexoes.html", "entrada-levantar"): _LACO_DO_MAPEAR,
    ("08-conexoes.html", "entrada-parar"): _LACO_DO_MAPEAR,
    ("08-conexoes.html", "entrada-pular"): _LACO_DO_MAPEAR,
    ("08-conexoes.html", "equilibrar-radio"): _PERGUNTA_DO_RADIO,
    ("08-conexoes.html", "escolher-aparelho"):
        "tela: o primeiro tempo do mover, o aparelho na mão dela",
    ("08-conexoes.html", "esquecer-aparelho"): _PERGUNTA_DO_RADIO,
    ("08-conexoes.html", "examinar-portas"):
        "leitura: refaz o exame das portas e a leitura do barramento",
    ("08-conexoes.html", "novo-hub"): _PERGUNTA_DO_HUB,
    ("08-conexoes.html", "novo-hub-cancelar"): _PERGUNTA_DO_HUB,
    ("08-conexoes.html", "receptor-descobrir"):
        "ato: começa e anda o «Descobrir a faixa» (tirar, medir, pôr, medir); a banda achada "
        "só vai ao `maquina.json` no tique que fecha a medida, e não é escolha dela",
    ("08-conexoes.html", "mapear-comecar"): _LACO_DO_MAPEAR,
    ("08-conexoes.html", "mapear-parar"): _LACO_DO_MAPEAR,
    ("08-conexoes.html", "sugerir-alocacao"):
        "leitura: a proposta da central do rádio para este adaptador",
    ("08-conexoes.html", "usar-como-botoes"):
        "tela: abre a janela do acionador com o rascunho da linha; quem grava é o «Guardar» "
        "(`acionador-guardar`), que declara `grava=`",
    ("08-conexoes.html", "acionador-nova-tecla"):
        "leitura: espera a próxima tecla do acionador, sem prendê-lo, e a põe no rascunho; "
        "quem grava é o «Guardar»",
    ("08-conexoes.html", "acionador-botao"):
        "tela: escolhe no desenho o botão da tecla, no rascunho; quem grava é o «Guardar»",
    ("09-sistema.html", "atualizar"):
        "ato: o serviço relê a configuração (`daemon.reload`) e confere",
    ("10-perfis.html", "ativar"):
        "ato: ativa o perfil escolhido (`profile.switch`); o perfil que vale é "
        "da sessão do daemon, e os campos do perfil já estão no disco",
    ("10-perfis.html", "procurar"):
        "memória da janela: o filtro que ela digitou; um filtro que voltasse "
        "do disco esconderia perfis dela na próxima abertura",
    ("10-perfis.html", "recarregar"):
        "leitura: relê a lista de perfis do disco agora",
    ("10-perfis.html", "selecionar"):
        "tela: abre o perfil no editor; mudar o perfil é o gesto do campo, que grava",
    ("mapa-das-portas.html", "reexaminar"):
        "leitura: relê a máquina e devolve o arranjo novo para a página",
}


def _declarados() -> set[Chave]:
    return set(pacotes.GESTOS_QUE_MEXEM)


def _categorias() -> dict[str, set[Chave]]:
    return {
        "grava=": _declarados(),
        "isento": set(protegido.ISENTOS),
        "GRAVAM_SEM_DECLARAR": set(GRAVAM_SEM_DECLARAR),
        "ATOS": set(ATOS),
    }


def test_todo_gesto_tem_um_veredito() -> None:
    """Gesto registrado sem veredito reprova, nomeado."""
    classificados = set().union(*_categorias().values())
    sem = sorted(f"{p}·{n}" for p, n in set(pacotes.GESTOS) - classificados)
    assert not sem, (
        "gesto(s) sem veredito — ele muda uma escolha dela e não grava, ou não "
        "é escolha e ninguém disse por quê:\n  " + "\n  ".join(sem)
        + "\n\nSe o gesto muda uma escolha, ele grava no clique e declara "
          "`grava=`; se não é escolha, entra em `ATOS` com a razão.")


def test_toda_entrada_aponta_um_gesto_e_nao_cruza() -> None:
    """As duas tabelas daqui só nomeiam gesto que existe, e cada gesto está numa só."""
    registrados = set(pacotes.GESTOS)
    for nome, tabela in (("GRAVAM_SEM_DECLARAR", GRAVAM_SEM_DECLARAR), ("ATOS", ATOS)):
        fantasmas = sorted(f"{p}·{n}" for p, n in set(tabela) - registrados)
        assert not fantasmas, f"{nome} nomeia gesto que não existe: {fantasmas}"
        sem_razao = sorted(f"{p}·{n}" for (p, n), r in tabela.items()
                           if len(r.strip()) < 30)
        assert not sem_razao, f"{nome} sem razão escrita: {sem_razao}"

    categorias = _categorias()
    nomes = sorted(categorias)
    for i, a in enumerate(nomes):
        for b in nomes[i + 1:]:
            nos_dois = sorted(f"{p}·{n}" for p, n in categorias[a] & categorias[b])
            assert not nos_dois, f"gesto(s) em «{a}» e em «{b}» ao mesmo tempo: {nos_dois}"


ESCREVEM_PELO_DAEMON = frozenset({"sensor_set_detalhado"})


def test_o_ato_nao_grava(monkeypatch: pytest.MonkeyPatch) -> None:
    """A árvore de cada ato não alcança porta de escrita nenhuma."""
    monkeypatch.setattr(protegido, "ESCREVEM",
                        set(protegido.ESCREVEM) | ESCREVEM_PELO_DAEMON)
    gravam = sorted(f"{p}·{n} (por `{sorted(portas)[0]}`)"
                    for (p, n) in ATOS
                    if (portas := protegido._portas(pacotes.GESTOS[(p, n)])))
    assert not gravam, (
        "gesto(s) em `ATOS` que gravam — tire da lista e declare `grava=`:\n  "
        + "\n  ".join(gravam))


def test_o_sensor_grava_pelo_daemon() -> None:
    """As duas pontas do único que grava pelo daemon: o gesto chama, o daemon grava."""
    # A camada embrulha o gesto (recusa no Nativo): o corpo que se lê é o de dentro.
    gesto = inspect.unwrap(pacotes.GESTOS[("02-controles.html", "sensor")])
    fonte = pathlib.Path(gesto.__code__.co_filename).read_text(encoding="utf-8")
    corpo = next(no for no in ast.walk(ast.parse(fonte))
                 if isinstance(no, ast.FunctionDef) and no.name == gesto.__name__)
    chama = {no.func.attr for no in ast.walk(corpo)
             if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)}
    assert "sensor_set_detalhado" in chama, (
        f"o gesto do sensor deixou de chamar `sensor.set`: {sorted(chama)}")

    from hefesto_dualsense4unix.daemon import ipc_handlers

    arvore = ast.parse(pathlib.Path(ipc_handlers.__file__).read_text(encoding="utf-8"))
    handler = next(no for no in ast.walk(arvore)
                   if isinstance(no, ast.AsyncFunctionDef)
                   and no.name == "_handle_sensor_set")
    grava = {getattr(no.func, "id", getattr(no.func, "attr", ""))
             for no in ast.walk(handler) if isinstance(no, ast.Call)}
    assert grava & {"save_profile", "gravar_pelo_gesto"}, (
        "o `sensor.set` do daemon deixou de gravar: o sensor que ela "
        "desliga voltaria ligado no próximo Salvar ou na próxima troca")


def test_a_regua_nao_esta_vazia() -> None:
    """Guarda de vacuidade: o registro e as quatro categorias têm gente."""
    categorias = _categorias()
    assert len(pacotes.GESTOS) >= 100, len(pacotes.GESTOS)
    assert all(categorias.values()), {k: len(v) for k, v in categorias.items()}
