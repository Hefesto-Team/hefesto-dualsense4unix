"""MASCARA-NO-PERFIL-01 (08/09/2026) — a máscara por controle entra no perfil."""
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
from hefesto_dualsense4unix.integrations.uinput_gamepad import (
    FLAVORS,
    normalize_flavor,
)
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    ControllerOverrides,
    MatchAny,
    Profile,
    ProfileModeConfig,
)
from tests.unit.test_por_unidade_01_todas_as_abas import _StoreSemTrava

P1 = "aabbcc000001"
P2 = "aabbcc000002"
P3 = "aabbcc000003"
P4 = "aabbcc000004"


def _par(mascara: str) -> tuple[int, int]:
    """``(vendor, product)`` que o vpad usaria para esta máscara."""
    entrada = FLAVORS[mascara]
    return int(entrada["vendor"]), int(entrada["product"])


@pytest.fixture
def registro_limpo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um ``controller_masks.json`` só deste teste, e um registro zerado."""
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


def test_o_campo_existe_e_none_e_sem_opiniao() -> None:
    """``mascara`` está ao lado das seis irmãs, e ``None`` é o default."""
    assert "mascara" in ControllerOverrides.model_fields
    assert ControllerOverrides().mascara is None
    assert ControllerOverrides(mascara="xbox").mascara == "xbox"


def test_o_disco_nao_aceita_mascara_que_o_vpad_nao_sabe_criar() -> None:
    """O catálogo é o do vpad, e a recusa é em voz alta."""
    with pytest.raises(ValidationError):
        ControllerOverrides(mascara="xbox 360")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ControllerOverrides(mascara="banana")  # type: ignore[arg-type]
    for mascara in mask_mod.mascaras_validas():
        assert ControllerOverrides(mascara=mascara).mascara == mascara  # type: ignore[arg-type]


def test_a_mascara_do_perfil_vale_naquele_assento_e_so_nele(
    registro_limpo: Path,
) -> None:
    """``mascara=xbox`` no P2 → ``045e:028e``; o P1 continua ``054c:0df2``."""
    _gerente().apply_controller_mascaras(_perfil("Jogo", **{P2: "xbox"}))

    assert mask_mod.mascara_efetiva(P2, "dualsense") == "xbox"
    assert mask_mod.mascara_efetiva(P1, "dualsense") == "dualsense"
    assert _par(mask_mod.mascara_efetiva(P2, "dualsense")) == (0x045E, 0x028E)
    assert _par(mask_mod.mascara_efetiva(P1, "dualsense")) == (0x054C, 0x0DF2)


def test_trocar_de_perfil_troca_as_quatro_mascaras(registro_limpo: Path) -> None:
    """Os quatro seguem o perfil novo — que é o que ela não tinha."""
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
    """NUMA-03: o controle em uso no meio da partida não some e volta."""
    gerente = _gerente()
    gerente.apply_controller_mascaras(
        _perfil("Antes", **{P1: "xbox", P2: "xbox", P3: "xbox", P4: "xbox"})
    )
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


def test_o_perfil_calado_devolve_todo_mundo_ao_padrao(
    registro_limpo: Path,
) -> None:
    """DECISÃO, 09/09/2026: *"Default é Hefesto dualsense padrão"*."""
    gerente = _gerente()
    gerente.apply_controller_mascaras(_perfil("Antes", **{P2: "xbox"}))
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "xbox"

    relatorio = gerente.apply_controller_mascaras(
        Profile(
            name="Calado",
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
        )
    )

    assert mask_mod.mascara_efetiva(P2, "dualsense") == "dualsense", (
        "o perfil calado tinha de ter devolvido o P2 ao padrão"
    )
    assert relatorio == {f"mascara:{P2}": "padrão"}, (
        "quem voltou ao padrão tem de aparecer no relatório — a janela precisa "
        "poder dizer o que mudou naquela peça"
    )
    assert mask_mod.registro_de_mascaras().snapshot() == {}, (
        "a entrada do cache é o que sobrevivia à troca de perfil; ela some"
    )


def test_o_perfil_calado_devolve_ate_quem_ele_nunca_viu(
    registro_limpo: Path,
) -> None:
    """A devolução alcança QUEM O PERFIL NÃO MENCIONA — inclusive um externo."""
    externo = "aabbcc0000ff"
    mask_mod.registro_de_mascaras().set_mask(externo, "nintendo")
    assert mask_mod.mascara_efetiva(externo, "dualsense") == "nintendo"

    _gerente().apply_controller_mascaras(_perfil("Jogo", **{P1: "xbox"}))

    assert mask_mod.mascara_efetiva(externo, "dualsense") == "dualsense"
    assert mask_mod.mascara_efetiva(P1, "dualsense") == "xbox"


def test_o_que_a_devolucao_custa_e_so_o_vpad_de_quem_estava_fora(
    registro_limpo: Path,
) -> None:
    """O CUSTO DA DECISÃO DE PRODUTO, medido — e ele é o que a torna barata."""
    calado = Profile(
        name="Calado",
        match=MatchAny(),
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
    )
    assentos = (P1, P2, P3, P4)

    def _quantos_caem(antes: dict[str, str]) -> int:
        mask_mod._zerar_registro_de_mascaras()
        (registro_limpo / "controller_masks.json").unlink(missing_ok=True)
        gerente = _gerente()
        if antes:
            gerente.apply_controller_mascaras(_perfil("Antes", **antes))
        vivos = {u: mask_mod.mascara_efetiva(u, "dualsense") for u in assentos}
        gerente.apply_controller_mascaras(calado)
        return sum(
            mask_mod.vpad_ficou_para_tras(vivos[u], u, "dualsense") for u in assentos
        )

    assert _quantos_caem({}) == 0, "mesa já no padrão: ninguém pode cair"
    assert _quantos_caem({P2: "xbox"}) == 1, "só o assento que estava fora cai"
    assert _quantos_caem(dict.fromkeys(assentos, "xbox")) == 4, (
        "os quatro estavam fora do padrão; os quatro voltam, e é a decisão dela"
    )
    assert _quantos_caem(dict.fromkeys(assentos, "dualsense")) == 0, (
        "quatro entradas APAGADAS e nenhum vpad derrubado — é este número que "
        "responde ao custo levantado na entrega de 08/09"
    )


def test_o_relatorio_diz_a_peca_e_a_mascara(registro_limpo: Path) -> None:
    """``mascara:<uniq>`` — o mesmo formato-por-peça do ``mic`` e do ``sensores``."""
    relatorio = _gerente().apply_controller_mascaras(
        _perfil("Jogo", **{P1: "dualsense", P2: "xbox"})
    )
    assert relatorio == {f"mascara:{P1}": "dualsense", f"mascara:{P2}": "xbox"}


def test_arrancar_o_campo_deixa_o_assento_na_sessao(registro_limpo: Path) -> None:
    """A mordida da sprint, feita por dentro: um override SEM o campo."""
    perfil_sem_o_campo = Profile(
        name="Velho",
        match=MatchAny(),
        controllers={P2: ControllerOverrides()},
    )
    relatorio = _gerente().apply_controller_mascaras(perfil_sem_o_campo)

    assert relatorio == {}, (
        "um override sem `mascara` não pode escrever máscara nenhuma"
    )
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "dualsense", (
        "o assento P2 ficou com a máscara da SESSÃO — é o defeito que o campo "
        "novo existe para curar"
    )


def test_apagar_o_arquivo_de_mascaras_nao_muda_vpad_de_quem_o_perfil_declara(
    registro_limpo: Path,
) -> None:
    """``controller_masks.json`` virou cache: apagá-lo custa uma reativação."""
    gerente = _gerente()
    perfil = _perfil("Jogo", **{P1: "xbox", P2: "nintendo"})
    gerente.apply_controller_mascaras(perfil)
    arquivo = registro_limpo / "controller_masks.json"
    assert arquivo.exists(), "o cache nem chegou a ser escrito"
    assert {
        e["identity"]: e["flavor"] for e in json.loads(arquivo.read_text())["masks"]
    } == {P1: "xbox", P2: "nintendo"}

    arquivo.unlink()
    mask_mod._zerar_registro_de_mascaras()
    assert mask_mod.mascara_efetiva(P1, "dualsense") == "dualsense", (
        "sem o cache e sem reativar, quem responde é a máscara do jogo"
    )

    gerente.apply_controller_mascaras(perfil)
    assert mask_mod.mascara_efetiva(P1, "dualsense") == "xbox"
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "nintendo"


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
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "xbox"


def test_o_gesto_vazio_limpa_dos_dois_lados(
    registro_limpo: Path, perfis: Path
) -> None:
    """``flavor`` vazio = *"volta a herdar a do perfil"*, no disco e na sessão."""
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
    """Sem perfil não há onde guardar — e recusar seria pior que a sessão."""
    corpo = _gesto(_Handlers(ativo=None), uniq=P2, flavor="xbox")

    assert corpo["status"] == "ok" and corpo["gravado"] is False
    assert corpo["motivo"] == "sem_perfil"
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "xbox"


def test_o_gesto_nao_grava_sob_uma_chave_que_ninguem_casa(
    registro_limpo: Path, perfis: Path
) -> None:
    """``path:/dev/input/event9`` não é peça de plástico — e não vira chave."""
    loader_module.save_profile(Profile(name="Bancada", match=MatchAny()))

    corpo = _gesto(_Handlers(ativo="Bancada"), uniq="path:/dev/input/event9",
                   flavor="xbox")

    assert corpo["gravado"] is False and corpo["motivo"] == "sem_endereco"
    assert (loader_module.load_profile("Bancada").controllers or {}) == {}


def test_o_gesto_repetido_nao_regrava_o_perfil(
    registro_limpo: Path, perfis: Path
) -> None:
    """NADA MUDOU = NÃO REGRAVA — e aqui isso vale mais que no motor."""
    loader_module.save_profile(Profile(name="Bancada", match=MatchAny()))
    h = _Handlers(ativo="Bancada")
    _gesto(h, uniq=P2, flavor="xbox")

    corpo = _gesto(h, uniq=P2, flavor="xbox")

    assert corpo["gravado"] is False and corpo["motivo"] == "sem_mudanca"


def test_a_ordem_de_decisao_vale_degrau_a_degrau(registro_limpo: Path) -> None:
    """Os três degraus, medidos no COMPORTAMENTO — não na prosa que os descreve."""
    gerente = _gerente()
    gerente.apply_controller_mascaras(
        Profile(
            name="Ordem",
            match=MatchAny(),
            mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="nintendo"),
            controllers={P2: ControllerOverrides(mascara="xbox")},
        )
    )

    assert mask_mod.mascara_efetiva(P2, "nintendo") == "xbox"
    assert mask_mod.mascara_efetiva(P1, "nintendo") == "nintendo"
    assert mask_mod.mascara_efetiva(P1, None) == normalize_flavor(None)
    assert mask_mod.mascara_efetiva(None, None) == normalize_flavor(None)


def test_quem_executa_o_primeiro_degrau_nao_e_a_mascara_efetiva(
    registro_limpo: Path,
) -> None:
    """O degrau 1 é EXECUTADO por quem escreve o cache, não por quem o lê."""
    perfil = _perfil("Jogo", **{P2: "xbox"})

    assert perfil.controllers is not None
    assert perfil.controllers[P2].mascara == "xbox"
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "dualsense", (
        "`mascara_efetiva` não lê perfil: se ela executasse o degrau 1, este "
        "`assert` seria 'xbox' sem ninguém ter ativado o perfil"
    )

    _gerente().apply_controller_mascaras(perfil)
    assert mask_mod.mascara_efetiva(P2, "dualsense") == "xbox"
