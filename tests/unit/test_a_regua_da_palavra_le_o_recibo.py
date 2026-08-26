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

A RÉGUA, declarada, e ela é diferente em cada metade:

* a primeira metade chama o PRÓPRIO validador, carregado do arquivo em
  `scripts/`, e planta um módulo de mentira dentro de `app/`. Nada é
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
_MODULO_PLANTADO = '''"""Plantado pela régua do recibo — apagado no `finally` do teste."""


class AbaDeMentira:
    def on_botao_de_mentira(self) -> None:
        self._toast_profile("Daemon offline agora, plantado pela régua do recibo")
'''

_FRASE_PLANTADA = "Daemon offline agora, plantado pela régua do recibo"


@pytest.fixture
def recibo_plantado() -> Any:
    """Um módulo de `app/` com um toast de jargão, apagado ao fim do teste.

    Plantado em `app/` DE VERDADE, e não num `tmp_path`, porque o alcance do
    portão é `app/` — medir noutro lugar mediria outra coisa.
    """
    alvo = APP / "_recibo_plantado_pelo_teste.py"
    alvo.write_text(_MODULO_PLANTADO, encoding="utf-8")
    try:
        yield alvo
    finally:
        alvo.unlink(missing_ok=True)


def test_o_toast_passa_pela_regua(
    validador: Any, recibo_plantado: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """O portão reprova jargão que chega à tela por um toast, com o endereço.

    A MORDIDA: devolvido o `ESCOADOUROS` antigo — isto é, sem os ajudantes de
    toast —, a MESMA frase plantada passa em silêncio. É o estado em que o
    repositório viveu até 26/08/2026, e é o que a segunda metade deste teste
    mede, para que o vermelho da primeira não possa ser confundido com o de
    outra régua.
    """
    codigo = validador.main(["--all"])
    saida = capsys.readouterr().out

    assert codigo == 1, "o portão ficou verde com jargão dentro de um toast"
    assert _FRASE_PLANTADA in saida
    assert "daemon offline" in saida.lower()
    # `arquivo:linha`, e a linha é a do argumento do toast.
    assert f"{recibo_plantado}:6:" in saida, saida

    # A metade que prova que foi o RECIBO que viu: sem os ajudantes de toast na
    # lista de escoadouros, a mesma frase fica invisível.
    antigos = dict(validador.ESCOADOUROS_DE_RECIBO)
    validador.ESCOADOUROS_DE_RECIBO.clear()
    try:
        codigo_antigo = validador.main(["--all"])
        capsys.readouterr()
    finally:
        validador.ESCOADOUROS_DE_RECIBO.update(antigos)
    assert codigo_antigo == 0, (
        "sem os ajudantes de toast o portão deveria ficar cego — se ele acusou, "
        "quem viu a frase plantada foi outro escoadouro, e esta régua não mede "
        "o que promete"
    )


def test_o_funil_do_toast_nao_arrasta_o_id_de_contexto(validador: Any) -> None:
    """`_status_toast(context, msg)` tem texto de tela na posição 1, só nela.

    O id de contexto da statusbar (`"daemon"`, `"footer"`, `"profiles"`) não é
    palavra de tela — ninguém o lê. Contá-lo levaria `"daemon"` para dentro do
    portão, que é o começo de um termo banido, e a régua passaria a acusar o
    que não é tela: o defeito que desliga portão em uma semana.
    """
    assert validador.ESCOADOUROS_DE_RECIBO["_status_toast"] == (1,)
    for nome, posicoes in validador.ESCOADOUROS_DE_RECIBO.items():
        if nome != "_status_toast":
            assert posicoes == (0,), nome


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
    # `speaker:<uniq>` — o alto-falante de UM controle. PROVISÓRIO: a frase não
    # diz qual, e o porquê está escrito em `profiles_actions.py`.
    assert _frase_do_rodape("speaker:aa:bb:cc:00:00:ff").endswith(
        "Aplicado, menos: alto-falante de um controle."
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
    """A sétima seção relata como as seis irmãs — no sucesso e na falha.

    A MORDIDA: sem a atribuição a `resultado["rumble_passthrough"]`, o applier
    é chamado, a exceção vira um `logger.warning`, e o relatório sai SEM a
    chave — o rodapé então diz "Perfil aplicado ao controle." com a vibração do
    jogo caída. Ausência de notícia lida como sucesso, que é o padrão que esta
    casa já nomeou.
    """
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    gerente = ProfileManager(
        controller=FakeController(),
        store=StateStore(),
        rumble_passthrough_applier=lambda _valor: None,
    )
    assert gerente.apply_emulation(_perfil())["rumble_passthrough"] == "aplicado"

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
