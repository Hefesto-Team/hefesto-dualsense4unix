"""MASCARA-NO-PERFIL-01 (08/09/2026) — a máscara por controle entra no perfil.

A PERGUNTA E A RESPOSTA DELA
-----------------------------
*"A máscara por controle deve entrar no perfil, junto com luz, gatilho,
vibração, som, mic e sensores — ou fica da máquina?"* — **"pode entrar sim"**.

O QUE ELA SENTIU, e é o que abriu a sprint: trocar de perfil trocava o modo e
**não trocava a máscara** de ninguém. A máscara era da SESSÃO
(``controller_masks.json``) e sobrevivia ao perfil, então um perfil de jogo que
precisa do P2 em Xbox não tinha como dizer isso.

O QUE ESTE ARQUIVO MEDE, e cada bloco é uma das três mordidas da sprint:

1. **gravar ``mascara=xbox`` no P2 e ativar** → o vpad do P2 nasce ``045e:028e``
   e o do P1 continua ``054c:0df2``; trocar de perfil → os quatro seguem o
   perfil novo;
2. **arrancar o campo do esquema** → a régua reprova nomeando o assento cuja
   máscara ficou da sessão — é o teste ``..._deixa_o_assento_na_sessao`` abaixo,
   que faz a arrancada por dentro em vez de pedir que alguém a faça;
3. **``controller_masks.json`` não decide mais nada** → apagá-lo não muda vpad
   nenhum de quem o perfil declara.

O QUE NÃO ESTÁ AQUI, E POR QUÊ: nenhum gamepad virtual é CRIADO. Criar um vpad
abre ``uinput`` de verdade, e a suíte inteira já derrubou a sessão gráfica dela
uma vez por isso. O par VID/PID é lido do catálogo que o vpad usa
(``uinput_gamepad.FLAVORS``) sobre a máscara que ``mascara_efetiva`` devolve —
o degrau MONTOU fica para a bancada, com os quatro na mesa.

Endereços de rádio: faixa SINTÉTICA da casa (``aabbcc…``, octetos 4 e 5
zerados), nunca o OUI de um aparelho real.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.subsystems import external_mask as mask_mod
from hefesto_dualsense4unix.integrations.uinput_gamepad import FLAVORS
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    MatchAny,
    Profile,
    ProfileModeConfig,
)
from tests.unit.test_por_unidade_01_todas_as_abas import _StoreSemTrava

#: Os quatro assentos da mesa dela, na faixa sintética da casa.
P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"
P4 = "aabbcc000004"


def _par(mascara: str) -> tuple[int, int]:
    """``(vendor, product)`` que o vpad usaria para esta máscara.

    Lido do catálogo do próprio vpad, e não digitado: uma máscara nova não pode
    exigir que esta régua seja reescrita para continuar medindo.
    """
    entrada = FLAVORS[mascara]
    return int(entrada["vendor"]), int(entrada["product"])


@pytest.fixture
def registro_limpo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um ``controller_masks.json`` só deste teste, e um registro zerado.

    O registro é um SINGLETON de processo que lê o disco uma vez por instância
    — sem zerar antes e depois, a máscara de um teste responderia pelo vizinho,
    que é exatamente o modo de falhar que ele existe para impedir no daemon.
    """
    lar = tmp_path / "config"
    lar.mkdir()

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            lar.mkdir(parents=True, exist_ok=True)
        return lar

    monkeypatch.setattr(
        "hefesto_dualsense4unix.utils.xdg_paths.config_dir", _config_dir
    )
    mask_mod._zerar_registro_de_mascaras()
    try:
        yield lar
    finally:
        mask_mod._zerar_registro_de_mascaras()


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis isolado — o mesmo molde do ``isolated_profiles_dir``."""
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


def _gerente() -> ProfileManager:
    return ProfileManager(
        controller=object(),  # type: ignore[arg-type]
        store=_StoreSemTrava(),  # type: ignore[arg-type]
    )


def _perfil(nome: str, **mascaras: str | None) -> Profile:
    """Perfil com uma máscara por assento — ``None`` = aquele não tem opinião."""
    return Profile(
        name=nome,
        match=MatchAny(),
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
        controllers={
            uniq: ControllerOverrides(mascara=valor)
            for uniq, valor in mascaras.items()
            if valor is not None
        },
    )


# ---------------------------------------------------------------------------
# 1. O CAMPO — e o que ele recusa
# ---------------------------------------------------------------------------


def test_o_campo_existe_e_none_e_sem_opiniao() -> None:
    """``mascara`` está ao lado das seis irmãs, e ``None`` é o default.

    Perfil antigo carrega igual: é o que faz esta entrega não mexer em nenhum
    arquivo dela que não peça para ser mexido.
    """
    assert "mascara" in ControllerOverrides.model_fields
    assert ControllerOverrides().mascara is None
    assert ControllerOverrides(mascara="xbox").mascara == "xbox"


def test_o_disco_nao_aceita_mascara_que_o_vpad_nao_sabe_criar() -> None:
    """O catálogo é o do vpad, e a recusa é em voz alta.

    ``"xbox 360"`` é o erro de digitação clássico desta casa — o normalizador
    TOLERANTE o transformaria em ``xbox``, e a fronteira estrita existe para que
    um engano não vire uma troca silenciosa de máscara.
    """
    with pytest.raises(ValidationError):
        ControllerOverrides(mascara="xbox 360")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ControllerOverrides(mascara="banana")  # type: ignore[arg-type]
    # E o que o esquema aceita é exatamente o que o vpad sabe criar.
    for mascara in mask_mod.mascaras_validas():
        assert ControllerOverrides(mascara=mascara).mascara == mascara  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 2. A PRIMEIRA MORDIDA — o P2 em Xbox, o P1 intacto
# ---------------------------------------------------------------------------


def test_a_mascara_do_perfil_vale_naquele_assento_e_so_nele(
    registro_limpo: Path,
) -> None:
    """``mascara=xbox`` no P2 → ``045e:028e``; o P1 continua ``054c:0df2``.

    MORDIDA: tire a chamada de ``apply_controller_mascaras`` do
    ``apply_profile`` (ou o ``set_mask`` de dentro dela) e os dois assentos
    voltam a responder a máscara do jogo — o P2 sai ``054c:0df2``, que é o
    defeito inteiro em um par de números.
    """
    _gerente().apply_controller_mascaras(_perfil("Jogo", **{P2: "xbox"}))

    assert mask_mod.mascara_efetiva(P2, "dualsense") == "xbox"
    assert mask_mod.mascara_efetiva(P1, "dualsense") == "dualsense"
    assert _par(mask_mod.mascara_efetiva(P2, "dualsense")) == (0x045E, 0x028E)
    assert _par(mask_mod.mascara_efetiva(P1, "dualsense")) == (0x054C, 0x0DF2)


def test_trocar_de_perfil_troca_as_quatro_mascaras(registro_limpo: Path) -> None:
    """Os quatro seguem o perfil novo — que é o que ela não tinha.

    É a metade da queixa: antes desta sprint a máscara era da sessão e
    ATRAVESSAVA a troca de perfil, então o segundo `assert` deste teste falharia
    com os quatro valores do perfil velho.
    """
    gerente = _gerente()
    gerente.apply_controller_mascaras(
        _perfil("Antes", **{P1: "xbox", P2: "xbox", P3: "xbox", P4: "xbox"})
    )
    assert [mask_mod.mascara_efetiva(u, "dualsense") for u in (P1, P2, P3, P4)] == [
        "xbox"
    ] * 4

    gerente.apply_controller_mascaras(
        _perfil(
            "Depois",
            **{P1: "dualsense", P2: "nintendo", P3: "dualsense", P4: "xbox"},
        )
    )
    assert [mask_mod.mascara_efetiva(u, "dualsense") for u in (P1, P2, P3, P4)] == [
        "dualsense",
        "nintendo",
        "dualsense",
        "xbox",
    ]


def test_so_quem_mudou_e_repintado(registro_limpo: Path) -> None:
    """NUMA-03: o controle em uso no meio da partida não some e volta.

    ``vpad_ficou_para_tras`` é a função que o laço do co-op consulta antes de
    derrubar um vpad. Depois de ativar um perfil que repete a máscara de três
    assentos e muda a do quarto, ela tem de dizer "para trás" **uma vez só**.
    """
    gerente = _gerente()
    gerente.apply_controller_mascaras(
        _perfil("Antes", **{P1: "xbox", P2: "xbox", P3: "xbox", P4: "xbox"})
    )
    # Os quatro vpads nasceram na máscara do perfil velho.
    vivos = {u: mask_mod.mascara_efetiva(u, "dualsense") for u in (P1, P2, P3, P4)}

    gerente.apply_controller_mascaras(
        _perfil("Depois", **{P1: "xbox", P2: "nintendo", P3: "xbox", P4: "xbox"})
    )

    para_tras = [
        u
        for u, flavor in vivos.items()
        if mask_mod.vpad_ficou_para_tras(flavor, u, "dualsense")
    ]
    assert para_tras == [P2], (
        "a troca de perfil derrubaria o vpad de quem NÃO mudou de máscara — "
        f"para trás: {para_tras}"
    )


def test_o_perfil_sem_opiniao_nao_mexe_na_mascara_de_ninguem(
    registro_limpo: Path,
) -> None:
    """Campo ``None`` = sem opinião, e aqui isso custa mais que em toda irmã.

    Um perfil que não pediu máscara nenhuma não pode derrubar e recriar os
    quatro vpads dela no meio de uma partida. **PROVISÓRIO — decisão dela:** a
    outra leitura possível é *"perfil sem opinião devolve todo mundo ao
    padrão"*, e ela é a contradição aberta que já está registrada na docstring
    de ``ControllerOverrides``.
    """
    gerente = _gerente()
    gerente.apply_controller_mascaras(_perfil("Antes", **{P2: "xbox"}))

    relatorio = gerente.apply_controller_mascaras(
        Profile(name="Calado", match=MatchAny())
    )

    assert relatorio == {}
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "xbox"


def test_o_relatorio_diz_a_peca_e_a_mascara(registro_limpo: Path) -> None:
    """``mascara:<uniq>`` — o mesmo formato-por-peça do ``mic`` e do ``sensores``.

    É por ele que a janela consegue dizer QUAL peça foi atendida, em vez de
    fundir a mesa inteira num rótulo só.
    """
    relatorio = _gerente().apply_controller_mascaras(
        _perfil("Jogo", **{P1: "dualsense", P2: "xbox"})
    )
    assert relatorio == {f"mascara:{P1}": "dualsense", f"mascara:{P2}": "xbox"}


# ---------------------------------------------------------------------------
# 3. A SEGUNDA MORDIDA — arrancar o campo deixa o assento na sessão
# ---------------------------------------------------------------------------


def test_arrancar_o_campo_deixa_o_assento_na_sessao(registro_limpo: Path) -> None:
    """A mordida da sprint, feita por dentro: um override SEM o campo.

    ``ControllerOverrides()`` sem ``mascara`` é exatamente o que o esquema
    ANTIGO produzia para o mesmo JSON dela — o campo não existia, e o valor
    caía no ``extra="forbid"`` ou era ignorado. Com ele arrancado, o assento
    fica com a máscara da SESSÃO (aqui: nenhuma, logo a do jogo), e é isso que
    esta régua nomeia.

    Se um dia alguém tirar ``mascara`` de ``ControllerOverrides``, o
    ``_perfil()`` acima levanta ``ValidationError`` e a suíte inteira desta
    frente cai — que é o barulho certo.
    """
    perfil_sem_o_campo = Profile(
        name="Velho",
        match=MatchAny(),
        controllers={P2: ControllerOverrides()},  # o campo arrancado
    )
    relatorio = _gerente().apply_controller_mascaras(perfil_sem_o_campo)

    assert relatorio == {}, (
        "um override sem `mascara` não pode escrever máscara nenhuma"
    )
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "dualsense", (
        "o assento P2 ficou com a máscara da SESSÃO — é o defeito que o campo "
        "novo existe para curar"
    )


# ---------------------------------------------------------------------------
# 4. A TERCEIRA MORDIDA — o arquivo de sessão não decide mais nada
# ---------------------------------------------------------------------------


def test_apagar_o_arquivo_de_mascaras_nao_muda_vpad_de_quem_o_perfil_declara(
    registro_limpo: Path,
) -> None:
    """``controller_masks.json`` virou cache: apagá-lo custa uma reativação.

    O arquivo continua existindo porque ``mascara_efetiva`` é consultada no
    tique do co-op — ler o perfil do disco ali seria a tempestade de syscalls
    que o mapa de motores já pagou uma vez. O que ele deixou de ser é DONO.
    """
    gerente = _gerente()
    perfil = _perfil("Jogo", **{P1: "xbox", P2: "nintendo"})
    gerente.apply_controller_mascaras(perfil)
    arquivo = registro_limpo / "controller_masks.json"
    assert arquivo.exists(), "o cache nem chegou a ser escrito"
    assert {
        e["identity"]: e["flavor"] for e in json.loads(arquivo.read_text())["masks"]
    } == {P1: "xbox", P2: "nintendo"}

    # A mesa dela: o arquivo some (limpeza, migração, um `rm` curioso).
    arquivo.unlink()
    mask_mod._zerar_registro_de_mascaras()
    assert mask_mod.mascara_efetiva(P1, "dualsense") == "dualsense", (
        "sem o cache e sem reativar, quem responde é a máscara do jogo"
    )

    # E a reativação o traz de volta inteiro, sem ela escolher nada de novo.
    gerente.apply_controller_mascaras(perfil)
    assert mask_mod.mascara_efetiva(P1, "dualsense") == "xbox"
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "nintendo"


# ---------------------------------------------------------------------------
# 5. O GESTO DA TELA — mesma forma, e agora ele grava no perfil
# ---------------------------------------------------------------------------


class _Store:
    """``store`` de mentira: só o ``active_profile``."""

    def __init__(self, ativo: str | None) -> None:
        self.active_profile = ativo


class _Handlers(IpcHandlersMixin):
    """O bastante do mixin para chamar ``_handle_gamepad_mask_set``."""

    def __init__(self, *, ativo: str | None) -> None:
        self.store = _Store(ativo)  # type: ignore[assignment]
        self.controller = SimpleNamespace(  # type: ignore[assignment]
            describe_controllers=lambda: []
        )
        self.daemon = None  # type: ignore[assignment]


def _gesto(h: _Handlers, **params: Any) -> dict[str, Any]:
    return asyncio.run(h._handle_gamepad_mask_set(params))


def test_o_gesto_do_chip_grava_no_perfil_ativo(
    registro_limpo: Path, perfis: Path
) -> None:
    """`gamepad.mask.set {uniq, flavor}` → `controllers[uniq].mascara` no disco.

    A FORMA DO GESTO NÃO MUDOU — é o que a sprint exige (`nao_toca` na aba
    Jogar). O que mudou é onde a escolha para.

    MORDIDA: apague a chamada de ``_mascara_no_perfil`` no handler — o
    ``load_profile`` abaixo devolve o perfil sem o campo, e a máscara volta a
    morrer com a sessão.
    """
    loader_module.save_profile(Profile(name="Bancada", match=MatchAny()))
    h = _Handlers(ativo="Bancada")

    corpo = _gesto(h, uniq=P2, flavor="xbox")

    assert corpo["status"] == "ok" and corpo["flavor"] == "xbox"
    assert corpo["perfil"] == "Bancada" and corpo["gravado"] is True
    dele = (loader_module.load_profile("Bancada").controllers or {})[P2]
    assert dele.mascara == "xbox"
    # E vale AGORA, sem esperar a próxima ativação de perfil.
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "xbox"


def test_o_gesto_vazio_limpa_dos_dois_lados(
    registro_limpo: Path, perfis: Path
) -> None:
    """``flavor`` vazio = *"volta a herdar a do perfil"*, no disco e na sessão.

    E a entrada que esvaziou SOME do mapa: um ``uniq`` apontando para ``{}``
    faria a coluna "Ajuste próprio" da aba Perfis acender sobre nada.
    """
    loader_module.save_profile(Profile(name="Bancada", match=MatchAny()))
    h = _Handlers(ativo="Bancada")
    _gesto(h, uniq=P2, flavor="xbox")

    corpo = _gesto(h, uniq=P2, flavor="")

    assert corpo["flavor"] is None and corpo["gravado"] is True
    assert (loader_module.load_profile("Bancada").controllers or {}) == {}
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "dualsense"


def test_sem_perfil_ativo_o_gesto_ainda_vale_na_sessao(
    registro_limpo: Path, perfis: Path
) -> None:
    """Sem perfil não há onde guardar — e recusar seria pior que a sessão.

    A tela recebe ``gravado: false`` com o ``motivo``, em vez de um "aplicado"
    sobre nada; a máscara vale enquanto o daemon viver.
    """
    corpo = _gesto(_Handlers(ativo=None), uniq=P2, flavor="xbox")

    assert corpo["status"] == "ok" and corpo["gravado"] is False
    assert corpo["motivo"] == "sem_perfil"
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "xbox"


def test_o_gesto_nao_grava_sob_uma_chave_que_ninguem_casa(
    registro_limpo: Path, perfis: Path
) -> None:
    """``path:/dev/input/event9`` não é peça de plástico — e não vira chave.

    ``norm_mac`` devolveria ``"adeee9"`` para esse caminho: uma chave que parece
    boa e que peça nenhuma casa. Para LER é inofensivo; para GRAVAR é a escolha
    dela sumindo calada, e é a medição de 04/09/2026 que o
    ``_chave_de_peca_que_grava`` guarda.
    """
    loader_module.save_profile(Profile(name="Bancada", match=MatchAny()))

    corpo = _gesto(_Handlers(ativo="Bancada"), uniq="path:/dev/input/event9",
                   flavor="xbox")

    assert corpo["gravado"] is False and corpo["motivo"] == "sem_endereco"
    assert (loader_module.load_profile("Bancada").controllers or {}) == {}


def test_o_gesto_repetido_nao_regrava_o_perfil(
    registro_limpo: Path, perfis: Path
) -> None:
    """NADA MUDOU = NÃO REGRAVA — e aqui isso vale mais que no motor.

    Um ``save_profile`` faz o daemon reaplicar o perfil inteiro, e a reaplicação
    passa por ``apply_controller_mascaras`` — que é justamente quem pode
    derrubar vpad.
    """
    loader_module.save_profile(Profile(name="Bancada", match=MatchAny()))
    h = _Handlers(ativo="Bancada")
    _gesto(h, uniq=P2, flavor="xbox")

    corpo = _gesto(h, uniq=P2, flavor="xbox")

    assert corpo["gravado"] is False and corpo["motivo"] == "sem_mudanca"


# ---------------------------------------------------------------------------
# 6. A ORDEM DE DECISÃO MORA NUM LUGAR SÓ
# ---------------------------------------------------------------------------


def test_a_ordem_de_decisao_esta_escrita_onde_ela_e_executada() -> None:
    """Três degraus, e a docstring que os nomeia é a da função que os aplica.

    Uma segunda cópia da ordem em outro módulo é como duas camadas passam a
    discordar sobre quem é a máscara de um controle — foi assim que o ``or
    "xbox"`` do editor de perfis apagou giroscópio e touchpad no jogo dela.
    """
    doc = mask_mod.mascara_efetiva.__doc__ or ""
    assert "controllers[uniq].mascara" in doc
    assert "mode.gamepad_flavor" in doc
    assert "apply_controller_mascaras" in doc
