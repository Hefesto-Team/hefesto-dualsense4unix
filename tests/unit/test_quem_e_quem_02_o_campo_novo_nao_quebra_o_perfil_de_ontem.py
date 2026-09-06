"""QUEM-E-QUEM-02 — o campo novo não pode quebrar os perfis que já estão no disco.

**O defeito que esta régua fecha, numa frase:** a regra que protege o downgrade
era uma LISTA ESCRITA À MÃO (`profiles/loader.py`,
``_SECOES_OPCIONAIS_OMITIDAS_QUANDO_NONE``), e esquecer de vir até ela não dava
erro — dava um ``"secao": null`` em TODO save e um binário anterior à seção
recusando TODOS os perfis dela num downgrade, não só os que usam a seção.

**E já aconteceu três vezes**, com registro no próprio arquivo: ``teclado_emulado``
(24/08/2026, *"não previsto pela sprint"*) e ``button_actions`` (01/09/2026, cujo
comentário diz em letra *"a terceira vez que ela não foi lembrada"*). As duas
foram pegas por ACIDENTE, por um teste vizinho (`test_profile_speaker_section.py
::test_binario_antigo_ainda_carrega_perfil_salvo_por_este`). Com cinco seções em
fila — microfone, giroscópio, acelerômetro, máscara, touchpad — seria cinco vezes
o mesmo acidente.

O QUE ESTA RÉGUA MEDE, e o que ela deliberadamente NÃO mede
-----------------------------------------------------------
Ela mede a FORMA do arquivo e o contrato de declaração. Ela **não** acrescenta
campo, **não** migra dado e **não** decide o que nasce ligado — isso é dela
(``D-AUDIO-E-GIRO-NASCEM-LIGADOS`` contra ``D-PERFIL-DE-DESEMPENHO``). A sprint só
exige que a resposta esteja ESCRITA onde o portão a enxergue.

NADA AQUI TOCA O DISCO DELA. Os perfis são construídos no teste, num diretório
temporário; ``~/.config/hefesto-dualsense4unix/profiles/`` não é lido nem
gravado em linha nenhuma. A chave por controle é ``aabbcc000002`` — sintética,
na máscara da casa.

AS MORDIDAS, e são três
-----------------------
1. devolver ``for secao in _SECOES_OPCIONAIS_OMITIDAS_QUANDO_NONE`` no lugar da
   regra derivada em ``_payload_do_perfil`` → ``test_secao_nova_de_topo_com_none
   _some_do_arquivo`` reprova, e o binário de ontem recusa nomeando a seção;
2. acrescentar um campo de topo ao ``Profile`` sem declará-lo →
   ``test_toda_secao_de_topo_esta_em_exatamente_uma_lista`` reprova NOMEANDO o
   campo (encenado aqui num modelo do teste, sem tocar o ``Profile`` real);
3. trocar o ``is None`` do laço por um teste falsy → ``test_teclado_silencioso
   _sobrevive`` reprova, porque ``key_bindings: {}`` some do arquivo.
"""
from __future__ import annotations

import json
import types
import typing
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from hefesto_dualsense4unix.app.draft_config import _override_vazio
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import (
    _SECOES_DE_TOPO_QUE_NASCEM_DENSAS,
    _SECOES_OPCIONAIS_OMITIDAS_QUANDO_NONE,
    _payload_do_perfil,
    load_profile,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    LedsConfig,
    MatchAny,
    MatchCriteria,
    Profile,
    ProfileMicConfig,
    ProfileModeConfig,
    ProfileMouseConfig,
    ProfileSpeakerConfig,
    TriggerConfig,
    TriggersConfig,
)

#: Sintética, na máscara da casa (octetos 4 e 5 zerados). Nenhum endereço de
#: rádio desta bancada entra em arquivo versionado — há dois portões.
UNIQ_SINTETICO = "aabbcc000002"


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """O diretório de perfis vai para o tmp — o disco DELA nunca é tocado."""
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _mk_profile(name: str, **kw: object) -> Profile:
    defaults: dict[str, object] = {
        "match": MatchCriteria(window_class=[f"{name}_class"]),
        "priority": 10,
        "triggers": TriggersConfig(
            left=TriggerConfig(mode="Off"),
            right=TriggerConfig(mode="Off"),
        ),
        "leds": LedsConfig(lightbar=(0, 0, 0), player_leds=[False] * 5),
    }
    defaults.update(kw)
    return Profile(name=name, **defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 1. O BINÁRIO DE ONTEM, congelado — é o downgrade sem instalar binário nenhum
# ---------------------------------------------------------------------------


class _ProfileDeBinarioDeOntem(BaseModel):
    """O `Profile` como um hefesto ANTERIOR o conhece: ``extra="forbid"``.

    A lista de campos é LITERAL de propósito. Derivá-la do `Profile` de hoje
    faria este modelo crescer junto com o produto e o teste passaria a medir
    nada — que é a família de defeito *"a régua mediu o mundo de ontem"*, só
    que ao contrário: a régua mediria o mundo de HOJE e chamaria isso de
    ontem. Ele congela o formato v1, e é contra ele que o downgrade se prova.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    version: int = 1
    match: dict[str, Any]
    priority: int = 0
    triggers: dict[str, Any] | None = None
    leds: dict[str, Any] | None = None
    rumble: dict[str, Any] | None = None
    key_bindings: dict[str, Any] | None = None
    mouse: dict[str, Any] | None = None
    mic: dict[str, Any] | None = None
    mode: dict[str, Any] | None = None
    suppress_desktop_emulation: bool = False
    controllers: dict[str, Any] | None = None


def test_binario_de_ontem_aceita_o_perfil_que_hoje_grava(
    isolated_profiles_dir: Path,
) -> None:
    """Prova 1: um perfil gravado HOJE ainda carrega num hefesto de ONTEM.

    É a asserção que a omissão do `None` existe para salvar, e ela é a única
    que fala a língua do prejuízo: sem ela, um `git checkout` para trás recusa
    o diretório inteiro de perfis dela, não só os que usam a seção nova.
    """
    caminho = save_profile(_mk_profile("legado"))
    bruto = json.loads(caminho.read_text(encoding="utf-8"))
    _ProfileDeBinarioDeOntem.model_validate(bruto)  # não levanta


def test_binario_de_ontem_recusa_a_seca_que_ele_nao_conhece() -> None:
    """O dublê SABE RECUSAR — régua que só sabe passar não é régua.

    O caminho de erro é exercido aqui, e não por acidente noutro teste: se o
    `extra="forbid"` deste modelo se perdesse numa edição futura, a prova 1
    passaria a dar verde sobre qualquer coisa, e ninguém veria.
    """
    with pytest.raises(ValidationError, match="secao_inventada"):
        _ProfileDeBinarioDeOntem.model_validate(
            {
                "name": "x",
                "match": {"type": "any"},
                "secao_inventada": {"ligado": True},
            }
        )


# ---------------------------------------------------------------------------
# 2. A seção nova de topo com None some — SEM ninguém a registrar
# ---------------------------------------------------------------------------


class _SecaoInventada(BaseModel):
    """A seção que a próxima sprint vai acrescentar. Aqui ela é anônima."""

    ligado: bool = True


class _ProfileComSecaoNova(Profile):
    """O `Profile` de AMANHÃ: uma seção de topo a mais, e ninguém avisou.

    Encena as cinco sprints em fila (microfone, giroscópio, acelerômetro,
    máscara, touchpad) sem escrever nenhuma delas — a sprint QUEM-E-QUEM-02
    não acrescenta campo, ela é a rede que os cinco vão atravessar.
    """

    secao_inventada: _SecaoInventada | None = None


def test_secao_nova_de_topo_com_none_some_do_arquivo(
    isolated_profiles_dir: Path,
) -> None:
    """Prova 2: a chave nova NÃO aparece, e ninguém precisou registrá-la.

    ``secao_inventada`` não está — e por desenho nunca estará — em
    ``_SECOES_OPCIONAIS_OMITIDAS_QUANDO_NONE``. É esse o ponto inteiro.

    MORDIDA (medida em 06/09/2026): devolva
    ``for secao in _SECOES_OPCIONAIS_OMITIDAS_QUANDO_NONE`` no lugar da regra
    derivada em ``_payload_do_perfil`` e rode de novo — a chave aparece como
    ``"secao_inventada": null`` e o binário de ontem recusa nomeando-a.
    """
    assert "secao_inventada" not in _SECOES_OPCIONAIS_OMITIDAS_QUANDO_NONE

    perfil = _ProfileComSecaoNova(
        name="amanha_sem_secao",
        match=MatchAny(type="any"),
    )
    payload = _payload_do_perfil(perfil)

    assert "secao_inventada" not in payload
    # E o binário de ontem continua aceitando — que é o prejuízo evitado.
    _ProfileDeBinarioDeOntem.model_validate(payload)


def test_secao_nova_de_topo_preenchida_e_que_e_gravada(
    isolated_profiles_dir: Path,
) -> None:
    """A omissão é do ``None``, NUNCA do dado.

    Perfil que USA a seção a grava — e é só ele que fica incompatível com o
    binário de ontem. Esse é o preço aceito, e ele fica restrito a quem pediu.
    Sem este teste, "omitir tudo" passaria pela régua acima.
    """
    perfil = _ProfileComSecaoNova(
        name="amanha_usa",
        match=MatchAny(type="any"),
        secao_inventada=_SecaoInventada(ligado=False),
    )
    payload = _payload_do_perfil(perfil)

    assert payload["secao_inventada"] == {"ligado": False}
    with pytest.raises(ValidationError, match="secao_inventada"):
        _ProfileDeBinarioDeOntem.model_validate(payload)


def test_teclado_silencioso_sobrevive_ao_save(isolated_profiles_dir: Path) -> None:
    """``is None`` e NÃO falsy — a distinção que a regra derivada tinha de manter.

    ``key_bindings: {}`` é a ordem "teclado silencioso" (o perfil desliga
    todos os bindings). Omiti-la faria o perfil herdar os defaults e as teclas
    voltarem a sair sozinhas — o oposto do que ela pediu.

    MORDIDA: troque o ``if valor is None`` de
    ``_secoes_de_topo_omitidas_quando_none`` por ``if not valor`` e veja
    reprovar aqui.
    """
    caminho = save_profile(_mk_profile("silencioso", key_bindings={}))
    assert json.loads(caminho.read_text(encoding="utf-8"))["key_bindings"] == {}
    assert load_profile("silencioso").key_bindings == {}


# ---------------------------------------------------------------------------
# 3. A generalização não muda UM BYTE do que se grava hoje
# ---------------------------------------------------------------------------


def _payload_pela_tupla_escrita_a_mao(profile: Profile) -> dict[str, object]:
    """A regra ANTIGA, reproduzida aqui para servir de padrão de comparação.

    Ela vive no TESTE e não no produto porque é isso que ela é agora: o
    registro do que a casa gravava antes da generalização. Se a regra nova
    divergir em uma chave, a cura mudou o disco dela — e reprova.
    """
    payload: dict[str, object] = profile.model_dump(mode="json")
    for secao in _SECOES_OPCIONAIS_OMITIDAS_QUANDO_NONE:
        if payload.get(secao) is None:
            payload.pop(secao, None)
    if not payload.get("controllers"):
        payload.pop("controllers", None)
    else:
        payload["controllers"] = {
            uniq: cfg.model_dump(mode="json", exclude_unset=True)
            for uniq, cfg in (profile.controllers or {}).items()
        }
    return payload


#: Um valor PREENCHIDO para cada seção que a tupla escrita à mão cobria. As
#: sete são varridas em todas as combinações de "None ou preenchida".
_VALORES_DE_SECAO: dict[str, object] = {
    "speaker": ProfileSpeakerConfig(volume=200, muted=False),
    "mouse": ProfileMouseConfig(enabled=True, speed=8),
    "mic": ProfileMicConfig(button_toggles_system=True, volume=50),
    "mode": ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
    "key_bindings": {"cross": ["KEY_A"]},
    "teclado_emulado": True,
    "button_actions": {"cross": "KEY_ENTER"},
}


def test_a_tupla_registrada_e_exatamente_o_que_este_teste_varre() -> None:
    """Portão do próprio teste: a tupla não pode crescer sem a varredura crescer.

    Sem esta linha, alguém acrescentaria um nome à tupla-registro e a prova 3
    passaria a comparar SEIS de sete seções em silêncio — que é a assinatura
    de instrumento falso que esta casa já pagou seis vezes.
    """
    assert set(_SECOES_OPCIONAIS_OMITIDAS_QUANDO_NONE) == set(_VALORES_DE_SECAO)


@pytest.mark.parametrize("mascara", range(2 ** len(_VALORES_DE_SECAO)))
def test_a_generalizacao_nao_muda_o_arquivo_de_hoje(mascara: int) -> None:
    """Prova 3: para TODA combinação das seções, byte por byte o mesmo dicionário.

    128 combinações — cada uma das sete seções ``None`` ou preenchida. Se a
    regra derivada divergisse da tupla em um caso, o disco dela mudaria de
    forma numa gravação que ninguém pediu, e é isso que aqui reprova.
    """
    kwargs: dict[str, object] = {}
    for bit, (nome, valor) in enumerate(_VALORES_DE_SECAO.items()):
        if mascara & (1 << bit):
            kwargs[nome] = valor

    perfil = _mk_profile("comparado", **kwargs)
    assert _payload_do_perfil(perfil) == _payload_pela_tupla_escrita_a_mao(perfil)


def test_a_generalizacao_nao_muda_o_arquivo_com_mapa_por_controle() -> None:
    """O mesmo, com ``controllers`` preenchido — a regra própria dele fica de pé."""
    perfil = _mk_profile(
        "com_mapa",
        controllers={UNIQ_SINTETICO: ControllerOverrides(leds=LedsConfig())},
    )
    novo = _payload_do_perfil(perfil)
    assert novo == _payload_pela_tupla_escrita_a_mao(perfil)
    assert novo["controllers"] == {UNIQ_SINTETICO: {"leds": {}}}


# ---------------------------------------------------------------------------
# 4. O PORTÃO — toda seção de topo está em EXATAMENTE uma das duas listas
# ---------------------------------------------------------------------------


def _aceita_none(anotacao: object) -> bool:
    """O campo pode valer ``None``? — e por isso a omissão derivada o alcança."""
    if anotacao is None or anotacao is type(None):
        return True
    origem = typing.get_origin(anotacao)
    if origem is typing.Union or origem is types.UnionType:
        return any(arg is type(None) for arg in typing.get_args(anotacao))
    return False


def _classificar(modelo: type[BaseModel]) -> tuple[set[str], set[str]]:
    """Devolve (os que a omissão do None alcança, os que nascem densos)."""
    alcancados = {
        nome
        for nome, campo in modelo.model_fields.items()
        if _aceita_none(campo.annotation)
    }
    densos = set(modelo.model_fields) - alcancados
    return alcancados, densos


def _queixas_do_portao(
    modelo: type[BaseModel], declarados: set[str]
) -> list[str]:
    """As três queixas possíveis, NOMEANDO o campo em cada uma.

    Ela é uma função e não três `assert` soltos por um motivo medido nesta
    casa: `assert` dentro do teste só é exercido pelo caso que passa, e o
    caminho de erro fica sem ninguém. Aqui as três saídas são exercitadas por
    ``test_o_portao_das_duas_listas_morde`` contra modelos de mentira, sem
    tocar o `Profile` real.
    """
    alcancados, densos = _classificar(modelo)
    queixas: list[str] = []

    for nome in sorted(densos - declarados):
        queixas.append(
            f"{nome}: NASCE DENSO e não está declarado em "
            "_SECOES_DE_TOPO_QUE_NASCEM_DENSAS. Ele é gravado em TODO save e "
            "um hefesto anterior a ele recusa os perfis dela inteiros. "
            "Declare-o com o motivo, ou dê a ele `| None = None`."
        )
    for nome in sorted(declarados - set(modelo.model_fields)):
        queixas.append(
            f"{nome}: declarado como nasce-denso e NÃO EXISTE no modelo — "
            "sobra de um campo que saiu. Tire o nome da lista."
        )
    for nome in sorted(declarados & alcancados):
        queixas.append(
            f"{nome}: está nas DUAS listas — aceita None (logo é omitido) e ao "
            "mesmo tempo está declarado como nasce-denso. Uma das duas mente."
        )
    return queixas


def test_toda_secao_de_topo_esta_em_exatamente_uma_lista() -> None:
    """Prova 4: nenhum campo de topo fica sem resposta escrita.

    A regra, e ela tem só duas saídas:

      * o campo ACEITA ``None`` → a omissão derivada o alcança sozinha, e
        acrescentá-lo não custa nada a ninguém no downgrade;
      * o campo NASCE DENSO → ele é gravado em todo save, quebra o downgrade
        por construção, e tem de estar em ``_SECOES_DE_TOPO_QUE_NASCEM_DENSAS``
        com o motivo ao lado.

    Nunca nas duas, nunca em nenhuma. É este o portão que a ONDA-CONTROLES-07
    vai encontrar quando declarar ``sensors`` com ``gyro: bool = True`` no
    topo: ela reprova até declarar, e isso é a régua funcionando.

    MORDIDA MEDIDA em 06/09/2026, no `Profile` REAL: acrescentar
    ``sensors: ProfileSpeakerConfig = ProfileSpeakerConfig(volume=1)`` a
    `schema.py` fez este teste reprovar com
    ``['sensors']: NASCE DENSO e não está declarado``. A mordida foi desfeita.
    """
    queixas = _queixas_do_portao(Profile, set(_SECOES_DE_TOPO_QUE_NASCEM_DENSAS))
    assert not queixas, "\n".join(queixas)


def test_o_portao_das_duas_listas_morde() -> None:
    """A mordida da prova 4, encenada nas TRÊS saídas — sem tocar o `Profile`.

    Régua que só sabe passar não é régua: aqui cada uma das três queixas é
    exercitada, e cada uma tem de NOMEAR o campo. Se este teste passar a dar
    verde, o portão acima deixou de ver a próxima sprint chegar.
    """

    class _ProfileComSecaoDensaEsquecida(Profile):
        sensores_esquecidos: _SecaoInventada = _SecaoInventada()

    declarados = set(_SECOES_DE_TOPO_QUE_NASCEM_DENSAS)

    # (a) denso e não declarado — o caso da ONDA-CONTROLES-07.
    esquecido = _queixas_do_portao(_ProfileComSecaoDensaEsquecida, declarados)
    assert len(esquecido) == 1 and esquecido[0].startswith("sensores_esquecidos:")
    assert "NASCE DENSO" in esquecido[0]

    # (b) declarado e inexistente — a sobra de um campo que saiu do modelo.
    sobra = _queixas_do_portao(Profile, declarados | {"campo_que_saiu"})
    assert len(sobra) == 1 and sobra[0].startswith("campo_que_saiu:")
    assert "NÃO EXISTE" in sobra[0]

    # (c) nas duas listas — `mic` aceita None E foi declarado nasce-denso.
    nas_duas = _queixas_do_portao(Profile, declarados | {"mic"})
    assert len(nas_duas) == 1 and nas_duas[0].startswith("mic:")
    assert "DUAS listas" in nas_duas[0]

    _, densos = _classificar(_ProfileComSecaoDensaEsquecida)
    assert "sensores_esquecidos" in densos
    assert "sensores_esquecidos" not in declarados

    # E o efeito real, medido: a chave vai para o arquivo e o binário de ontem
    # recusa o perfil INTEIRO. O default `None` não a salvaria; a declaração é
    # o único caminho, e é por isso que o portão exige a declaração.
    payload = _payload_do_perfil(
        _ProfileComSecaoDensaEsquecida(name="denso", match=MatchAny(type="any"))
    )
    assert payload["sensores_esquecidos"] == {"ligado": True}
    with pytest.raises(ValidationError, match="sensores_esquecidos"):
        _ProfileDeBinarioDeOntem.model_validate(payload)


def test_a_lista_de_nasce_densas_esta_ordenada_como_o_modelo() -> None:
    """Cosmético? Não: é como se lê a lista contra o `Profile` sem se perder.

    Oito nomes fora de ordem viram oito buscas visuais a cada revisão, e é
    nessa fricção que o nome errado passa.
    """
    declarados = set(_SECOES_DE_TOPO_QUE_NASCEM_DENSAS)
    ordem_do_modelo = [n for n in Profile.model_fields if n in declarados]
    assert list(_SECOES_DE_TOPO_QUE_NASCEM_DENSAS) == ordem_do_modelo


# ---------------------------------------------------------------------------
# 5. A ENTRADA POR CONTROLE já é imune — e não por sorte (F1)
# ---------------------------------------------------------------------------


class _OverrideDeBinarioDeOntem(BaseModel):
    """``ControllerOverrides`` como o binário de ontem o conhece."""

    model_config = ConfigDict(extra="forbid")

    leds: dict[str, Any] | None = None
    triggers: dict[str, Any] | None = None
    rumble: dict[str, Any] | None = None
    speaker: dict[str, Any] | None = None


class _OverrideComCampoNovoRalo(ControllerOverrides):
    """Molde 1: ``| None = None`` — "esta peça não tem opinião"."""

    campo_novo: _SecaoInventada | None = None


class _OverrideComCampoNovoDenso(ControllerOverrides):
    """Molde 2: default denso. É o molde que a ONDA-CONTROLES-07 propõe."""

    campo_novo: _SecaoInventada = _SecaoInventada()


@pytest.mark.parametrize(
    "molde", [_OverrideComCampoNovoRalo, _OverrideComCampoNovoDenso]
)
def test_entrada_por_controle_aceita_campo_novo_nos_dois_moldes(
    molde: type[ControllerOverrides],
) -> None:
    """Prova 5 (congela F1): o ``exclude_unset`` já protege a entrada por controle.

    Um override construído com SÓ ``leds`` escrito sai ``{"leds": {}}`` nos
    dois moldes, e o binário de ontem aceita os dois. É o que impede a próxima
    sprint de pagar um preço que a medição diz que não existe: acrescentar
    campo a ``ControllerOverrides`` **não** é o risco do downgrade.
    """
    override = molde(leds=LedsConfig())
    saida = override.model_dump(mode="json", exclude_unset=True)

    assert saida == {"leds": {}}
    _OverrideDeBinarioDeOntem.model_validate(saida)


def test_o_campo_novo_por_controle_vai_ao_disco_quando_e_escrito(
    isolated_profiles_dir: Path,
) -> None:
    """O ``exclude_unset`` omite o não-escrito, não o dado. O caminho de ida.

    Sem este par, "omitir sempre" passaria pelo teste acima — e o mapa por
    controle deixaria de gravar o que ela ajustou.
    """
    override = _OverrideComCampoNovoRalo(
        leds=LedsConfig(), campo_novo=_SecaoInventada(ligado=False)
    )
    saida = override.model_dump(mode="json", exclude_unset=True)
    assert saida == {"leds": {}, "campo_novo": {"ligado": False}}


# ---------------------------------------------------------------------------
# 6. O default denso POR CONTROLE produz a chave fantasma (F3)
# ---------------------------------------------------------------------------


def test_default_denso_por_controle_produz_a_chave_fantasma() -> None:
    """Prova 6 (congela F3): os dois moldes NÃO são intercambiáveis.

    ``_override_vazio`` decide por ``is None`` em todos os campos declarados.
    Com o molde ralo, um override recém-criado é vazio e SOME do mapa quando
    ela apaga o último ajuste. Com o molde denso, **nenhuma entrada é vazia
    nunca**: a chave de endereço fica no JSON apontando para um override que a
    janela não consegue mais apagar — que é, em letra, o defeito que a
    docstring daquela função diz existir para impedir.

    O RECADO PARA A ONDA-CONTROLES-07: o default denso vale no TOPO do perfil
    (é decisão dela, ``D-AUDIO-E-GIRO-NASCEM-LIGADOS``) e NÃO na entrada por
    controle. São dois moldes, não um.
    """
    assert _override_vazio(ControllerOverrides()) is True
    assert _override_vazio(_OverrideComCampoNovoRalo()) is True
    assert _override_vazio(_OverrideComCampoNovoDenso()) is False


# ---------------------------------------------------------------------------
# 7. Ida e volta das formas que o disco dela tem — SEM tocar no disco dela
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("apelido", "extra", "binario_de_ontem_aceita"),
    [
        ("liso", {}, True),
        ("silencioso", {"key_bindings": {}}, True),
        ("com_teclas", {"key_bindings": {"cross": ["KEY_A"]}}, True),
        ("qualquer_janela", {"match": MatchAny(type="any")}, True),
        ("por_classe", {"match": MatchCriteria(window_class=["steam_app_1"])}, True),
        # O perfil que USA uma seção posterior ao v1 é o único que o binário de
        # ontem recusa — e esse é o preço ACEITO, restrito a quem pediu. A
        # ida-e-volta continua exigida dele: usar a seção não pode fazer o
        # arquivo mudar de forma sozinho na próxima gravação.
        ("com_som", {"speaker": ProfileSpeakerConfig(volume=120)}, False),
    ],
)
def test_ida_e_volta_nao_acrescenta_uma_chave(
    isolated_profiles_dir: Path,
    apelido: str,
    extra: dict[str, object],
    binario_de_ontem_aceita: bool,
) -> None:
    """Prova 7: ``load → save`` não acrescenta UMA chave a nenhuma das formas.

    As formas cobertas são as que o disco dela tem (com e sem
    ``key_bindings: {}``, com e sem ``match`` por classe), CONSTRUÍDAS AQUI.
    ``~/.config/hefesto-dualsense4unix/profiles/`` não é lido nem gravado em
    linha nenhuma deste arquivo — o perfil dela não é bancada de teste.
    """
    caminho = save_profile(_mk_profile(apelido, **extra))
    antes = json.loads(caminho.read_text(encoding="utf-8"))

    caminho2 = save_profile(load_profile(apelido))
    depois = json.loads(caminho2.read_text(encoding="utf-8"))

    assert set(depois) == set(antes)
    assert depois == antes

    if binario_de_ontem_aceita:
        _ProfileDeBinarioDeOntem.model_validate(depois)
    else:
        with pytest.raises(ValidationError):
            _ProfileDeBinarioDeOntem.model_validate(depois)
