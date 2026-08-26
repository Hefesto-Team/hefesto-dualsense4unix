"""O recibo do gesto ganha régua, e ganha português (BG-TOAST-02 + BG-07c).

O QUE É O RECIBO. É a frase que a pessoa lê DEPOIS de clicar — o toast na
statusbar. Ela é a única resposta que o produto dá a um gesto, e era o único
pedaço da tela sem régua nenhuma.

OS DOIS DEFEITOS QUE ESTE ARQUIVO FECHA, medidos em 26/08/2026.

1. **O portão da palavra não lia toast.** `scripts/validar-palavra-de-tela.py`
   decide "isto é texto de tela?" por FLUXO: a string tem de chegar a um
   ESCOADOURO. A lista tinha treze nomes e nenhum deles continha "toast";
   `app/` tem 15 ajudantes de toast e 170 chamadas, das quais 163 carregavam
   texto que régua nenhuma lia. Consequência concreta: `"Falha (daemon
   offline?)"` vivia em `profiles_actions.py` com o portão VERDE, e `daemon
   offline` está literalmente em `JARGAO_BANIDO`, com a troca escrita, desde a
   E3 da PALAVRA-01.

2. **Seção de perfil chegava CRUA, em inglês, ao rodapé.** Ela salva um perfil,
   uma seção não entra, e a linha que ela lê é "Aplicado, menos: <chave>." —
   a única linha que ela leria quando o que ela sente falhasse.

3. **A COSTURA não tinha régua** — e é por isso que a suíte inteira deixou
   passar duas regressões em 26/08 (a entrega voltou da conferência). Nenhum
   teste desta casa ligava o `ProfileManager` à FRASE:
   `test_aplicar_verdade_02` monta o payload à mão e nunca passa por
   `apply_emulation`. Os dois últimos testes deste arquivo percorrem o caminho
   inteiro — applier real do daemon incluído — e é o que faltava.

A RÉGUA, declarada, e ela é diferente em cada metade:

* a primeira metade chama o PRÓPRIO validador, carregado do arquivo em
  `scripts/`, e planta um módulo de mentira numa raiz descartável. Nada é
  reimplementado aqui — uma cópia da regra divergiria da original na primeira
  edição, e as duas passariam verdes medindo coisas diferentes;
* a segunda metade lê a FRASE FINAL, a que sai na statusbar, e não o mapa que
  a produz. Um teste contra o mapa não veria o defeito de verdade, que era
  duas grafias (`trigger` e `triggers`) que nunca se encontraram: o mapa do
  rodapé estava certo, o do meio estava certo, e a frase saía errada.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions import profiles_actions
from hefesto_dualsense4unix.profiles.manager import SECAO_DO_APPLIER, ProfileManager
from hefesto_dualsense4unix.profiles.schema import Profile

RAIZ = Path(__file__).resolve().parents[2]
APP = RAIZ / "src" / "hefesto_dualsense4unix" / "app"


def _validador() -> Any:
    """O `validar-palavra-de-tela.py` importado como módulo.

    Ele mora em `scripts/` e tem hífen no nome, então não é importável pelo
    caminho normal. Mesmo carregador do irmão
    `test_palavra_de_tela_alcanca_o_python.py`.
    """
    caminho = RAIZ / "scripts" / "validar-palavra-de-tela.py"
    spec = importlib.util.spec_from_file_location("_validador_do_recibo", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_validador_do_recibo"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def validador() -> Any:
    return _validador()


# ---------------------------------------------------------------------------
# 1. O toast passa pela régua
# ---------------------------------------------------------------------------

#: O módulo de mentira que o teste planta em `app/`. Ele é a prova viva de que
#: a régua enxerga o recibo: a frase só chega à tela por um ajudante de toast, e
#: nenhum outro escoadouro a toca. O jargão é `daemon offline`, o primeiro termo
#: que a E3 da PALAVRA-01 aposentou.
_MODULO_PLANTADO = '''"""Plantado pela régua do recibo — apagado com o `tmp_path` do teste."""


class AbaDeMentira:
    def on_botao_de_mentira(self) -> None:
        self._toast_profile("Daemon offline agora, plantado pela régua do recibo")
'''

_FRASE_PLANTADA = "Daemon offline agora, plantado pela régua do recibo"

#: O segundo módulo de mentira: as DUAS posições do funil, uma em cada método.
#: `_status_toast(context, msg)` recebe o id de contexto na 0 e a frase na 1, e
#: este arquivo põe jargão nas duas para que a régua tenha de ESCOLHER.
#:
#: O id de contexto aqui é sintético de propósito. Os vivos são palavras soltas
#: (`"daemon"`, `"footer"`, `"profiles"`) e nenhuma delas contém termo banido —
#: medido em 26/08/2026 —, e é exatamente por isso que declarar a constante não
#: prova nada: alargar `_status_toast` para `(0, 1)` na árvore de hoje deixa o
#: portão verde. Só um contexto que CARREGA o jargão revela a escolha.
_MODULO_DO_CONTEXTO = '''"""Plantado pela régua do recibo — apagado com o `tmp_path` do teste."""


class AbaDeMentira:
    def on_id_de_contexto(self) -> None:
        self._status_toast("daemon offline", "Tudo certo por aqui")

    def on_mensagem(self) -> None:
        self._status_toast("daemon", "Daemon offline agora, e isto É palavra de tela")
'''


@pytest.fixture
def recibo_plantado(tmp_path: Path) -> Path:
    """Um módulo com um toast de jargão, numa raiz descartável.

    ELE NASCEU DENTRO DE `app/` DE VERDADE, e voltou para o `tmp_path` em
    26/08/2026, na volta da conferência. A razão é o desenho documentado da
    suíte desta casa: ela MORRE no meio, em ponto variável (`CLAUDE.md`), e um
    arquivo escrito em `src/` sobrevive ao `finally` que nunca roda. O que
    sobra depois disso é `validar-palavra-de-tela.py --all` vermelho para todo
    mundo, por um módulo misterioso que ninguém escreveu — e o `git add -A` dos
    portões o encena.

    O alcance não se perde: a REGRA é a mesma em qualquer raiz (`conferir_app`
    aceita `raiz=` justamente por isso), e que a varredura de produção cubra
    `app/` é conferido logo abaixo, com o arquivo real na mão.
    """
    alvo = tmp_path / "_recibo_plantado_pelo_teste.py"
    alvo.write_text(_MODULO_PLANTADO, encoding="utf-8")
    return alvo


def _acusacoes_do_arquivo(validador: Any, raiz: Path, alvo: Path) -> list[str]:
    """As reprovações que apontam para ESTE arquivo, e só elas.

    `conferir_app` também confere se as dívidas declaradas ainda existem, e numa
    raiz de mentira nenhuma existe — esses achados são do outro contrato e não
    dizem nada sobre a régua do recibo.
    """
    return [
        achado
        for achado in validador.conferir_app(raiz=raiz)
        if achado.startswith(f"{alvo}:")
    ]


def test_o_toast_passa_pela_regua(
    validador: Any, recibo_plantado: Path, tmp_path: Path
) -> None:
    """O portão reprova jargão que chega à tela por um toast, com o endereço.

    A MORDIDA: devolvido o `ESCOADOUROS` antigo — isto é, sem os ajudantes de
    toast —, a MESMA frase plantada passa em silêncio. É o estado em que o
    repositório viveu até 26/08/2026, e é o que a segunda metade deste teste
    mede, para que o vermelho da primeira não possa ser confundido com o de
    outra régua.
    """
    acusacoes = _acusacoes_do_arquivo(validador, tmp_path, recibo_plantado)

    assert acusacoes, "o portão ficou verde com jargão dentro de um toast"
    assert _FRASE_PLANTADA in acusacoes[0]
    assert "daemon offline" in acusacoes[0].lower()
    # `arquivo:linha`, e a linha é a do argumento do toast.
    assert acusacoes[0].startswith(f"{recibo_plantado}:6:"), acusacoes

    # E a varredura de PRODUÇÃO continua sendo `app/`: a raiz descartável muda
    # onde se mede, nunca o que o portão varre quando roda de verdade.
    assert validador.APP == APP
    assert APP / "actions" / "profiles_actions.py" in validador.arquivos_de_python()

    # A metade que prova que foi o RECIBO que viu: sem os ajudantes de toast na
    # lista de escoadouros, a mesma frase fica invisível.
    antigos = dict(validador.ESCOADOUROS_DE_RECIBO)
    validador.ESCOADOUROS_DE_RECIBO.clear()
    try:
        cegas = _acusacoes_do_arquivo(validador, tmp_path, recibo_plantado)
    finally:
        validador.ESCOADOUROS_DE_RECIBO.update(antigos)
    assert not cegas, (
        "sem os ajudantes de toast o portão deveria ficar cego — se ele acusou, "
        "quem viu a frase plantada foi outro escoadouro, e esta régua não mede "
        "o que promete"
    )


def test_o_funil_do_toast_nao_arrasta_o_id_de_contexto(
    validador: Any, tmp_path: Path
) -> None:
    """`_status_toast(context, msg)` tem texto de tela na posição 1, só nela.

    O id de contexto da statusbar (`"daemon"`, `"footer"`, `"profiles"`) não é
    palavra de tela — ninguém o lê. Contá-lo faria a régua acusar o que não é
    tela: o defeito que desliga portão em uma semana.

    ESTE TESTE MEDE O ATO, NÃO A DECLARAÇÃO, e a correção é de 26/08/2026, na
    volta da conferência. Ele afirmava que a constante era igual a si mesma —
    uma régua que passa com a cura arrancada, porque trocar `(1,)` por `(0, 1)`
    no script deixava o portão verde na árvore de hoje (nenhum id de contexto
    vivo contém termo banido). Agora um módulo plantado põe jargão NAS DUAS
    posições, e o teste mede QUAL das duas o portão pega.
    """
    alvo = tmp_path / "_contexto_plantado_pelo_teste.py"
    alvo.write_text(_MODULO_DO_CONTEXTO, encoding="utf-8")

    acusacoes = _acusacoes_do_arquivo(validador, tmp_path, alvo)
    assert len(acusacoes) == 1, acusacoes
    # Linha 9 é a MENSAGEM; a linha 6 é o id de contexto, e ele fica de fora.
    assert acusacoes[0].startswith(f"{alvo}:9:"), acusacoes

    # A MORDIDA: alargado o funil para a posição 0, o id de contexto entra —
    # que é o dano exato que a posição `(1,)` existe para impedir.
    antigo = validador.ESCOADOUROS_DE_RECIBO["_status_toast"]
    validador.ESCOADOUROS_DE_RECIBO["_status_toast"] = (0, 1)
    try:
        alargadas = _acusacoes_do_arquivo(validador, tmp_path, alvo)
    finally:
        validador.ESCOADOUROS_DE_RECIBO["_status_toast"] = antigo
    assert len(alargadas) == 2, alargadas
    assert alargadas[0].startswith(f"{alvo}:6:"), alargadas


def test_a_divida_do_recibo_nao_envelhece_calada(validador: Any) -> None:
    """Entrada de dívida que não existe mais em `app/` REPROVA, pedindo a poda.

    Mesmo contrato do `DIVIDA_DA_PALAVRA_01_PY`, e é ele que autoriza a lista a
    nascer vazia: o mecanismo continua vivo, então o próximo toast com jargão
    declara a dívida com endereço ou reprova.
    """
    validador.DIVIDA_DO_RECIBO["Toast de mentira com daemon offline dentro"] = (
        "26/08/2026 — teste."
    )
    try:
        achados = validador.conferir_app()
    finally:
        del validador.DIVIDA_DO_RECIBO["Toast de mentira com daemon offline dentro"]
    assert any("DIVIDA_DO_RECIBO" in achado for achado in achados), achados


# ---------------------------------------------------------------------------
# 2. Nenhuma seção chega crua ao rodapé
# ---------------------------------------------------------------------------

#: A palavra de tela de cada seção que tem applier, e a frase inteira em que ela
#: aparece. Escrita aqui, e não lida do produto, de propósito: uma régua que
#: importasse o mapa do produto passaria verde com o mapa vazio.
#:
#: A completude é conferida contra `SECAO_DO_APPLIER` logo abaixo — seção nova
#: sem palavra de tela reprova aqui, no dia em que o applier nascer.
NOME_NA_TELA: dict[str, str] = {
    "mouse": "mouse",
    "suppression": "modo jogo",
    "mode": "modo",
    "rumble_policy": "vibração",
    # PROVISÓRIO — decisão dela (ver a nota em `profiles_actions.py`).
    "rumble_passthrough": "vibração do jogo",
    "speaker": "alto-falante",
    "mic": "microfone",
}


def _frase_do_rodape(chave: str) -> str:
    """A frase que a statusbar mostra quando só `chave` fica de fora.

    A âncora `keyboard: aplicado` existe porque "nada entrou" tem frase PRÓPRIA
    ("Nada foi aplicado ao controle.") e ela não nomeia seção nenhuma — sem a
    âncora, o teste mediria o outro caminho.
    """
    return profiles_actions.mensagem_de_ativacao(
        "Sackboy", {"secoes": {"keyboard": "aplicado", chave: "falhou"}}
    )


def test_nenhuma_secao_chega_crua_ao_rodape() -> None:
    """Cada seção com applier tem palavra de tela, e ela chega inteira à frase.

    A MORDIDA: arrancada uma entrada de `_NOMES_DAS_SECOES_DA_ATIVACAO`, a
    frase sai com a chave EM INGLÊS dentro de uma sentença em português —
    "Aplicado, menos: rumble_passthrough." — e a comparação abaixo imprime as
    duas lado a lado.
    """
    esperadas = {nome.removesuffix("_applier") for nome in SECAO_DO_APPLIER}
    assert set(NOME_NA_TELA) == esperadas, (
        "applier novo (ou aposentado) sem acerto na palavra de tela: "
        f"{esperadas ^ set(NOME_NA_TELA)}"
    )

    for chave, nome in sorted(NOME_NA_TELA.items()):
        assert _frase_do_rodape(chave) == f"Perfil ativado: Sackboy — Aplicado, menos: {nome}."


def test_as_secoes_no_singular_tambem_tem_palavra() -> None:
    """`trigger` e `led`, no SINGULAR, e o alto-falante de um controle só.

    O defeito era de GRAFIA, não de tradução: o mapa do rodapé
    (`footer_actions._NOMES_DE_SECAO`) tem `triggers` e `leds` no plural, porque
    nasceu para o `profile.apply_draft`; o manager escreve o singular, que é o
    vocabulário da trava manual (`profiles/manager.py:488`). As duas nunca se
    encontraram, e a frase saía "Aplicado, menos: trigger."
    """
    assert _frase_do_rodape("trigger").endswith("Aplicado, menos: gatilhos.")
    assert _frase_do_rodape("led").endswith("Aplicado, menos: luzes.")
    # `speaker:<uniq>` — o alto-falante de UM controle. PROVISÓRIO na redação, e
    # o `uniq` vai junto de propósito: sem ele as peças se FUNDEM (ver
    # `test_o_alto_falante_de_cada_controle_e_uma_peca`).
    assert _frase_do_rodape("speaker:aa:bb:cc:00:00:ff").endswith(
        "Aplicado, menos: alto-falante de um controle (aa:bb:cc:00:00:ff)."
    )


def test_secao_desconhecida_continua_saindo_crua() -> None:
    """A metade que mantém a régua honesta: nome técnico > omissão.

    Daemon mais novo que a janela relata seção que este mapa não conhece.
    `footer_actions._lista_de_secoes` já decidiu esse caso — "melhor um termo
    estranho do que omitir que algo ficou de fora" — e a decisão continua de pé.
    """
    assert _frase_do_rodape("secao_do_futuro").endswith("Aplicado, menos: secao_do_futuro.")


# ---------------------------------------------------------------------------
# 3. A vibração do jogo deixa de ser muda
# ---------------------------------------------------------------------------


def _perfil() -> Profile:
    return Profile.model_validate(
        {
            "name": "teste_do_recibo",
            "version": 1,
            "match": {"type": "any"},
            "priority": 10,
            "rumble": {"passthrough": True},
        }
    )


def test_a_vibracao_do_jogo_entra_no_relatorio() -> None:
    """A sétima seção relata quando TEM o que relatar — e cala quando não sabe.

    A MORDIDA: sem a atribuição a `resultado["rumble_passthrough"]`, o applier
    é chamado, a exceção vira um `logger.warning`, e o relatório sai SEM a
    chave — o rodapé então diz "Perfil aplicado ao controle." com a vibração do
    jogo caída. Ausência de notícia lida como sucesso, que é o padrão que esta
    casa já nomeou.

    A TERCEIRA metade, e ela é de 26/08/2026, na volta da conferência: applier
    que devolve `None` NÃO entra no relatório. É o oposto do `_estado_da_secao`
    das seis irmãs, e a razão está medida em `apply_emulation` — o applier real
    desta seção devolve `None` em todos os caminhos, e carimbar "aplicado" por
    ele matava a frase "Nada foi aplicado ao controle." (o teste da costura,
    logo abaixo).
    """
    from hefesto_dualsense4unix.daemon.lifecycle import ADIADO_LOCK_MANUAL
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    mudo = ProfileManager(
        controller=FakeController(),
        store=StateStore(),
        rumble_passthrough_applier=lambda _valor: None,
    )
    assert "rumble_passthrough" not in mudo.apply_emulation(_perfil())

    falante = ProfileManager(
        controller=FakeController(),
        store=StateStore(),
        rumble_passthrough_applier=lambda _valor: ADIADO_LOCK_MANUAL,
    )
    assert falante.apply_emulation(_perfil())["rumble_passthrough"] == ADIADO_LOCK_MANUAL

    def explode(_valor: bool) -> None:
        raise RuntimeError("o applier caiu")

    quebrado = ProfileManager(
        controller=FakeController(),
        store=StateStore(),
        rumble_passthrough_applier=explode,
    )
    assert quebrado.apply_emulation(_perfil())["rumble_passthrough"] == "falhou"


def test_a_vibracao_do_jogo_caida_aparece_na_frase() -> None:
    """E o relatório vira a linha que ela lê — o caminho inteiro, ponta a ponta.

    Os dois testes acima medem cada metade; este mede a costura, que é onde os
    defeitos desta casa moram (`portoes-em-serie-enganam`, 19/08/2026).
    """
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    def explode(_valor: bool) -> None:
        raise RuntimeError("o applier caiu")

    gerente = ProfileManager(
        controller=FakeController(),
        store=StateStore(),
        mouse_applier=lambda *_a, **_k: None,
        rumble_passthrough_applier=explode,
    )
    perfil = Profile.model_validate(
        {
            "name": "teste_do_recibo",
            "version": 1,
            "match": {"type": "any"},
            "priority": 10,
            "mouse": {"enabled": True},
            "rumble": {"passthrough": True},
        }
    )
    relatorio = gerente.apply_emulation(perfil)
    frase = profiles_actions.mensagem_de_ativacao("Sackboy", {"secoes": relatorio})
    assert frase.endswith("Aplicado, menos: vibração do jogo."), frase


# ---------------------------------------------------------------------------
# 4. As duas regressões que a conferência devolveu (26/08/2026)
#
# As duas passaram pela suíte inteira em silêncio, e a razão é a mesma nas
# duas: nenhuma régua ligava o MANAGER à FRASE. `test_aplicar_verdade_02` monta
# o payload à mão e nunca passa por `apply_emulation`; o teste da vibração do
# jogo, aqui em cima, usava um dublê que não se parece com o applier real. A
# costura é onde os defeitos desta casa moram, e agora ela tem régua.
# ---------------------------------------------------------------------------


def test_o_applier_que_nao_sabe_nao_carimba_aplicado() -> None:
    """Jogo aberto, tudo adiado: o rodapé diz "Nada foi aplicado ao controle."

    O CENÁRIO, e ele é o da APLICAR-VERDADE-02: um jogo aberto, o gate R-04
    adiando TODA seção, e a pergunta que a frase responde — chegou alguma coisa
    no controle? Não chegou nada.

    A MORDIDA: devolvido o `_estado_da_secao` a `rumble_passthrough` no
    `apply_emulation`, esta frase vira "Aplicado, menos: mouse." — porque o
    applier REAL devolve `None`, `_estado_da_secao(None)` lê "aplicado", e o
    `applied` nunca mais fica vazio. A janela comemora depois de nada ter
    chegado ao controle, que é o defeito que a APLICAR-VERDADE-02 e a P3b
    existem para matar. Vale igual no Salvar, que reusa a mesma função.

    A RÉGUA É O PRODUTO, NÃO UM DUBLÊ: o applier deste teste é o método REAL do
    daemon, o mesmo que `daemon/connection.py` injeta em produção. Um dublê que
    devolvesse `"aplicado"` mediria um daemon que não existe.
    """
    from hefesto_dualsense4unix.daemon.lifecycle import (
        ADIADO_JOGO_ABERTO,
        Daemon,
        DaemonConfig,
    )
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    daemon = Daemon(controller=FakeController(), config=DaemonConfig())
    # O applier real não sabe dizer se aplicou — devolve `None` nos quatro
    # caminhos, o feliz e os três no-op de saída antecipada.
    assert daemon.apply_profile_rumble_passthrough(True) is None
    daemon.config.rumble_active = (100, 120)
    assert daemon.apply_profile_rumble_passthrough(True) is None

    gerente = ProfileManager(
        controller=FakeController(),
        store=StateStore(),
        mouse_applier=lambda *_a, **_k: ADIADO_JOGO_ABERTO,
        rumble_passthrough_applier=daemon.apply_profile_rumble_passthrough,
    )
    perfil = Profile.model_validate(
        {
            "name": "Sackboy",
            "version": 1,
            "match": {"type": "any"},
            "priority": 10,
            "mouse": {"enabled": True},
            "rumble": {"passthrough": True},
        }
    )
    relatorio = gerente.apply_emulation(perfil)
    # A frase PRIMEIRO, de propósito: é ela que a pessoa lê, e é ela que a
    # mordida tem de imprimir quando alguém arrancar a cura.
    frase = profiles_actions.mensagem_de_ativacao("Sackboy", {"secoes": relatorio})
    assert frase == "Perfil ativado: Sackboy — Nada foi aplicado ao controle.", frase

    relato = profiles_actions.relato_da_ativacao({"secoes": relatorio})
    assert relato is not None and relato["applied"] == [], relato
    assert "rumble_passthrough" not in relatorio, relatorio


#: Quatro controles, que é a mesa cheia desta casa. Endereços mascarados pela
#: regra da casa (octetos 4 e 5 zerados).
_UNIQS_DA_MESA = (
    "aa:bb:cc:00:00:01",
    "aa:bb:cc:00:00:02",
    "aa:bb:cc:00:00:03",
    "aa:bb:cc:00:00:04",
)


def test_o_alto_falante_de_cada_controle_e_uma_peca() -> None:
    """Quatro alto-falantes caídos são QUATRO peças, nunca um rótulo só.

    A decisão já estava escrita em `ProfileManager.apply_controller_speakers`:
    a chave é `speaker:<uniq>`, *"distinta da `speaker` global de propósito,
    para a GUI conseguir dizer QUAL peça foi ignorada pela trava manual em vez
    de fundir tudo num rótulo só"*.

    A MORDIDA: um nome fixo em `nome_da_secao_da_ativacao` — sem o `uniq` —
    funde as quatro numa entrada só, porque `relato_da_ativacao` indexa
    `failed` pelo NOME traduzido. A frase fica bonita e três controles somem
    dela. Medido em 26/08/2026, com três caídos: "Aplicado, menos: alto-falante
    de um controle."
    """
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    gerente = ProfileManager(
        controller=FakeController(),
        store=StateStore(),
        speaker_applier=lambda *_a, **_k: "falhou_escrita",
    )
    perfil = Profile.model_validate(
        {
            "name": "Sackboy",
            "version": 1,
            "match": {"type": "any"},
            "priority": 10,
            "controllers": {uniq: {"speaker": {"volume": 60}} for uniq in _UNIQS_DA_MESA},
        }
    )
    # A âncora aplicada existe porque "nada entrou" tem frase PRÓPRIA e ela não
    # nomeia seção nenhuma — sem ela o teste mediria o outro caminho.
    relatorio = {"keyboard": "aplicado"}
    gerente.apply_controller_speakers(perfil, relatorio=relatorio)
    assert len(relatorio) == 1 + len(_UNIQS_DA_MESA), relatorio

    relato = profiles_actions.relato_da_ativacao({"secoes": relatorio})
    assert relato is not None
    assert len(relato["failed"]) == len(_UNIQS_DA_MESA), relato["failed"]
    # E cada nome carrega o `uniq` da SUA peça — é o que os mantém distintos.
    for uniq in perfil.controllers or {}:
        assert any(uniq in nome for nome in relato["failed"]), (uniq, relato["failed"])

    # A frase corta em três (`_MAX_SECOES_NO_TEXTO`), e a quarta peça continua
    # CONTADA em vez de sumir — que é a metade da contagem que a ordem pedia.
    frase = profiles_actions.mensagem_de_ativacao("Sackboy", {"secoes": relatorio})
    assert frase.endswith(" e mais 1."), frase
