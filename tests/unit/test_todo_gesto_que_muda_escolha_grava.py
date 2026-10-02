"""Todo gesto que muda uma escolha dela grava no clique — ou diz por que não é escolha.

O-SALVAR-E-O-APLICAR-LEEM-O-PERFIL-01, 27/09/2026. Desde
`D-2709-O-SALVAR-LE-O-PERFIL` o «Salvar» do rodapé não lê o aparelho: ele
regrava o perfil do disco. Isso só é seguro se toda escolha dela chegar ao
disco no gesto que a fez — a D2 de 05/09. Um gesto que muda uma escolha no
aparelho e não grava é uma escolha que o próximo Salvar, a próxima troca de
perfil ou o próximo boot desfazem, calado.

A RÉGUA É EXAUSTIVA NOS DOIS SENTIDOS, sobre o registro do produto
(`pacotes.GESTOS`), nunca sobre uma lista digitada:

* **todo gesto registrado tem um veredito**, e um só: declara `grava=` (a
  porta que a árvore confere em `test_todo_gesto_que_grava_esta_protegido.py`);
  ou é isento lá (grava o valor que a própria página mostra); ou está em
  :data:`GRAVAM_SEM_DECLARAR` (grava no clique por um caminho que o `grava=`
  não declara, com a razão); ou está em :data:`ATOS` (não é escolha a guardar:
  ato, sessão, tela ou leitura, com a razão). Gesto novo sem nenhum dos quatro
  reprova, nomeado;
* **toda entrada das duas tabelas aponta um gesto que existe**, com a razão
  escrita, sem cruzar com as outras categorias; e o ato não grava — a árvore
  dele não alcança porta de escrita nenhuma.

O SENSOR É O ÚNICO QUE GRAVA PELO DAEMON, e a régua confere a outra ponta: o
gesto chama `sensor.set`, e o `_handle_sensor_set` do daemon chama
`save_profile` (ele grava `ControllerOverrides.sensores` no perfil que vale).

A MORDIDA (medida na entrega): tire o `grava=` do `@gesto("*", "salvar")` e
:func:`test_todo_gesto_tem_um_veredito` reprova nomeando `*·salvar`; ponha em
:data:`ATOS` um gesto que grava (`04-iluminacao.html·cor`) e
:func:`test_toda_entrada_aponta_um_gesto_e_nao_cruza` reprova.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import pacotes
# O PILOTO REGISTRA UM GESTO SÓ AO SER IMPORTADO (`*·escolher-na-fita`). Sem
# esta linha o registro depende da ordem dos arquivos no lote.
from hefesto_dualsense4unix.interface import hefesto_vivo  # noqa: F401
from tests.unit import test_todo_gesto_que_grava_esta_protegido as protegido

Chave = tuple[str, str]

#: AS ESCOLHAS QUE VÃO AO DISCO NO CLIQUE POR UM CAMINHO QUE O `grava=` NÃO
#: DECLARA. Cada uma diz onde a escolha mora.
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

_GUARDAR_DA_06 = (
    "rascunho da tela: a linha trocada espera o «Guardar» da mesma tela, que "
    "declara `grava=`; gravar a cada linha salvaria meia escolha")
_FECHAR_DA_06 = (
    "ato: fechar ou «Cancelar» larga o que ela não guardou; guardar é o "
    "«Guardar» da mesma tela, que declara `grava=`")
_LACO_DO_MAPEAR = (
    "tela do «Mapear entrada a entrada»: as fases do laço; cada resposta "
    "grava no gesto dela (`responder`, `nao_alcanco`, que declaram `grava=`)")
_PERGUNTA_DO_RADIO = (
    "abre a pergunta do rádio; quem muda o pareamento é a confirmação dela, "
    "que declara `grava=`")

#: OS GESTOS QUE NÃO SÃO ESCOLHA A GUARDAR — e por quê. O Salvar nunca os
#: levou ao disco, e nenhum deles muda um campo de perfil.
ATOS: dict[Chave, str] = {
    ("*", "aplicar"):
        "ato: manda o perfil do disco aos controles e não muda escolha "
        "nenhuma (`D-2709-O-SALVAR-LE-O-PERFIL`)",
    ("*", "exportar"):
        "ato: copia o arquivo do perfil para FORA, onde ela escolhe; nenhum "
        "perfil nem aparelho dela muda",
    ("*", "escolher-na-fita"):
        "tela: o chip do «Selecionar:» só escolhe qual controle a aba mira "
        "(`hefesto_vivo.ESCOLHA_DA_FITA`); nada de perfil, nada de daemon",
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
    ("06-navegacao.html", "fechar-definicoes"): _FECHAR_DA_06,
    ("06-navegacao.html", "fechar-ponto"): _FECHAR_DA_06,
    ("06-navegacao.html", "fechar-teclas"): _FECHAR_DA_06,
    ("06-navegacao.html", "fechar-troca"): _FECHAR_DA_06,
    ("06-navegacao.html", "linha-de-botao"): _GUARDAR_DA_06,
    ("06-navegacao.html", "linha-de-troca"): _GUARDAR_DA_06,
    ("06-navegacao.html", "tecla-escrita"): _GUARDAR_DA_06,
    ("07-lancadores.html", "adicionar-a-exclusao"):
        "abre a escolha do jogo; quem grava é a confirmação "
        "(`confirmar-exclusao`), que declara `grava=`",
    ("07-lancadores.html", "criar-perfil-para-um-jogo"):
        "abre a escolha do jogo; quem grava é a confirmação "
        "(`confirmar-perfil`), que declara `grava=`",
    ("07-lancadores.html", "detectar"):
        "leitura: diz qual jogo está aberto, ou recusa dizendo",
    ("07-lancadores.html", "procurar"):
        "leitura: esquece o cache dos lançadores e relê o disco agora",
    ("08-conexoes.html", "abrir-adaptador"):
        "tela: abre um adaptador e fecha os outros (o acordeão)",
    ("08-conexoes.html", "aceitar-sugestao"): _PERGUNTA_DO_RADIO,
    # O «⋮» da linha (ESQUECER-E-LIMPAR-AS-CONEXOES-01): só abre o menu.
    ("08-conexoes.html", "aparelho-menu"):
        "tela: abre o menu «⋮» da linha; quem muda o pareamento é o "
        "«Esquecer» de lá, confirmado na pergunta, que declara `grava=`",
    ("08-conexoes.html", "adaptador-historico"):
        "leitura: o que aconteceu com este adaptador, pela hora",
    ("08-conexoes.html", "alvo"):
        "sessão: para qual controle as ações de saída miram agora "
        "(`controller.target.set`)",
    ("08-conexoes.html", "todos"):
        "sessão: as ações de saída voltam a valer para todos "
        "(`controller.target.set` sem índice)",
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
    ("08-conexoes.html", "luz-nao-acende"):
        "ato: derruba este controle do rádio para ela apertar PS e a luz voltar",
    ("08-conexoes.html", "mapear-comecar"): _LACO_DO_MAPEAR,
    ("08-conexoes.html", "mapear-parar"): _LACO_DO_MAPEAR,
    ("08-conexoes.html", "sugerir-alocacao"):
        "leitura: a proposta da central do rádio para este adaptador",
    ("08-conexoes.html", "trazer-para-ca"):
        "tela: a lista de quem pode vir para este adaptador",
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


#: AS PORTAS QUE GRAVAM DO OUTRO LADO DO IPC e que o `ESCREVEM` da régua irmã
#: não lista: lá, listá-las exigiria o `grava=` do gesto que as chama, e o
#: sensor grava sem declarar (:data:`GRAVAM_SEM_DECLARAR`). Aqui elas contam:
#: um ato que chame o `sensor.set` grava no perfil dela pelo daemon.
ESCREVEM_PELO_DAEMON = frozenset({"sensor_set_detalhado"})


def test_o_ato_nao_grava(monkeypatch: pytest.MonkeyPatch) -> None:
    """A árvore de cada ato não alcança porta de escrita nenhuma.

    As portas são as de `test_todo_gesto_que_grava_esta_protegido.ESCREVEM`,
    mais :data:`ESCREVEM_PELO_DAEMON`, e a descida é a mesma dele: um nome
    aqui que grave é um gesto que muda a máquina dela e se diz ato.

    MORDIDA (conferência de 28/09): mova o `02-controles.html·sensor` para
    :data:`ATOS` e esta reprova pelo `sensor_set_detalhado`; sem as portas
    do daemon, passava.
    """
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
    gesto = pacotes.GESTOS[("02-controles.html", "sensor")]
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
    # Desde a O-QUE-E-DO-COMPUTADOR-NAO-MUDA-COM-O-JOGO-01 (01/10/2026) o
    # sensor é do computador e grava pelo dono do cartão: no `maquina.json`,
    # ou no perfil quando ele já sobrepõe os sensores daquele controle.
    assert grava & {"save_profile", "gravar_pelo_gesto"}, (
        "o `sensor.set` do daemon deixou de gravar: o sensor que ela "
        "desliga voltaria ligado no próximo Salvar ou na próxima troca")


def test_a_regua_nao_esta_vazia() -> None:
    """Guarda de vacuidade: o registro e as quatro categorias têm gente."""
    categorias = _categorias()
    assert len(pacotes.GESTOS) >= 100, len(pacotes.GESTOS)
    assert all(categorias.values()), {k: len(v) for k, v in categorias.items()}
