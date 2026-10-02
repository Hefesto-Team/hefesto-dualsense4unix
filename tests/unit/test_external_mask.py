"""MÁSCARA-01 / E1 — a máscara mora no APARELHO, em arquivo PRÓPRIO."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    EXTERNAL_IDENTITY_FIELD,
    ExternalIdentityRegistry,
)
from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
    FLAVOR_FIELD,
    IDENTITY_FIELD,
    MASKS_FIELD,
    MASKS_SCHEMA_VERSION,
    VERSION_FIELD,
    ExternalMaskRegistry,
    mascaras_validas,
    normalizar_mascara,
)

MAC_A = "aa:bb:cc:00:be:ef"
MAC_B = "aa:bb:cc:00:be:f0"
MAC_DS = "aa:bb:cc:00:00:01"

_KEY_A = MAC_A.replace(":", "")
_KEY_B = MAC_B.replace(":", "")
_KEY_DS = MAC_DS.replace(":", "")

IDENTIDADE_VOLATIL = "dev:0003:057E:2009.0001"

BOOT = "boot-atual"


@pytest.fixture(autouse=True)
def _hermetico(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``config_dir`` em tmp + boot_id fixo — espelho do ``test_external_identity``."""
    from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
    from hefesto_dualsense4unix.utils import xdg_paths

    target = tmp_path / "config"

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    return target


def _arquivo_mascaras(tmp_path: Path) -> Path:
    return tmp_path / "config" / "controller_masks.json"


def _mascaras_no_disco(tmp_path: Path) -> dict[str, str]:
    dados = json.loads(_arquivo_mascaras(tmp_path).read_text(encoding="utf-8"))
    return {
        str(e[IDENTITY_FIELD]): str(e[FLAVOR_FIELD])
        for e in dados[MASKS_FIELD]
        if isinstance(e, dict)
    }


def _arquivo_fila(tmp_path: Path) -> Path:
    return tmp_path / "config" / "controllers.json"


def _gravar_fila(
    tmp_path: Path,
    *,
    dualsense: dict[str, int] | None = None,
    externos: dict[str, int] | None = None,
) -> None:
    """``controllers.json`` no schema vigente — cópia mínima da bancada irmã."""
    entradas: list[dict[str, object]] = [
        {"addr": addr, "kind": id_mod.KIND_DUALSENSE, "rank": rank}
        for addr, rank in (dualsense or {}).items()
    ]
    entradas += [
        {"addr": addr, "kind": id_mod.KIND_EXTERNAL, "rank": rank}
        for addr, rank in (externos or {}).items()
    ]
    _arquivo_fila(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _arquivo_fila(tmp_path).write_text(
        json.dumps(
            {
                "version": id_mod.CONTROLLERS_SCHEMA_VERSION,
                "boot_id": BOOT,
                id_mod.ORDER_FIELD: entradas,
            }
        ),
        encoding="utf-8",
    )


def _escrever_mascaras(tmp_path: Path, documento: dict[str, Any]) -> None:
    _arquivo_mascaras(tmp_path).parent.mkdir(parents=True, exist_ok=True)
    _arquivo_mascaras(tmp_path).write_text(
        json.dumps(documento, ensure_ascii=False), encoding="utf-8"
    )


def test_a_mascara_do_aparelho_atravessa_o_processo(tmp_path: Path) -> None:
    """A escolha é do plástico: ela sobrevive ao registro morrer e renascer."""
    reg = ExternalMaskRegistry()
    assert reg.set_mask(MAC_A, "dualsense") is True

    outro = ExternalMaskRegistry()
    assert outro.mask_for(MAC_A) == "dualsense"
    assert _mascaras_no_disco(tmp_path) == {_KEY_A: "dualsense"}


def test_sem_escolha_o_controle_aparece_como_ele_mesmo(tmp_path: Path) -> None:
    """Ausência de máscara é ``None`` — nunca um default disfarçado de escolha."""
    reg = ExternalMaskRegistry()
    assert reg.mask_for(MAC_A) is None
    assert reg.snapshot() == {}
    assert not _arquivo_mascaras(tmp_path).exists()


def test_limpar_devolve_como_ele_mesmo_e_some_do_disco(tmp_path: Path) -> None:
    reg = ExternalMaskRegistry()
    reg.set_mask(MAC_A, "xbox")
    reg.set_mask(MAC_B, "dualsense")

    assert reg.clear_mask(MAC_A) is True
    assert reg.clear_mask(MAC_A) is False
    assert reg.mask_for(MAC_A) is None
    assert _mascaras_no_disco(tmp_path) == {_KEY_B: "dualsense"}


def test_a_chave_e_a_identidade_que_numera_o_aparelho(tmp_path: Path) -> None:
    """``mask_for_entry`` casa pelo MESMO campo com que o daemon numera."""
    reg = ExternalMaskRegistry()
    reg.set_mask(MAC_A, "dualsense")
    entrada = {
        "name": "Pro Controller",
        "vid": "057e",
        "pid": "2009",
        "bus": "bluetooth",
        EXTERNAL_IDENTITY_FIELD: MAC_A,
    }
    assert reg.mask_for_entry(entrada) == "dualsense"
    entrada_b = dict(entrada, **{EXTERNAL_IDENTITY_FIELD: MAC_B})
    assert reg.mask_for_entry(entrada_b) is None


def test_a_mascara_nao_toca_o_controllers_json_nem_renumera_a_fila(
    tmp_path: Path,
) -> None:
    """O fato que reescreveu a E1: guardar a máscara na fila é DESTRUTIVO.

    ``identity.load`` descarta a fila inteira quando a versão difere
    (``identity.py:558``), e ``_save_locked`` só aproveita as entradas do outro
    lado no MESMO schema (``:940-950``) — um bump renumeraria a mesa dela e o
    primeiro save de DualSense apagaria a fila dos externos. Este teste é o
    guarda disso: registrar máscara não pode deixar UM BYTE diferente no
    ``controllers.json``, e a fila tem de renascer idêntica.
    """
    _gravar_fila(
        tmp_path, dualsense={_KEY_DS: 1}, externos={_KEY_A: 2, _KEY_B: 3}
    )
    antes = _arquivo_fila(tmp_path).read_bytes()

    reg = ExternalMaskRegistry()
    assert reg.set_mask(MAC_A, "dualsense") is True
    assert reg.set_mask(MAC_B, "xbox") is True

    assert _arquivo_fila(tmp_path).read_bytes() == antes
    fila = ExternalIdentityRegistry()
    fila.load()
    assert fila.snapshot() == {_KEY_A: 2, _KEY_B: 3}
    assert _arquivo_mascaras(tmp_path).exists()


def test_campos_desconhecidos_sobrevivem_ao_save(tmp_path: Path) -> None:
    """A lição do ``payload = {}`` (``identity.py:633``), aplicada contra nós."""
    _escrever_mascaras(
        tmp_path,
        {
            VERSION_FIELD: MASKS_SCHEMA_VERSION,
            "anotacao_de_versao_futura": {"quem": "a E4"},
            MASKS_FIELD: [
                {
                    IDENTITY_FIELD: _KEY_A,
                    FLAVOR_FIELD: "dualsense",
                    "escolhida_em": "2026-08-07",
                }
            ],
        },
    )

    reg = ExternalMaskRegistry()
    assert reg.mask_for(MAC_A) == "dualsense"
    assert reg.set_mask(MAC_B, "xbox") is True

    dados = json.loads(_arquivo_mascaras(tmp_path).read_text(encoding="utf-8"))
    assert dados["anotacao_de_versao_futura"] == {"quem": "a E4"}
    entrada_a = next(e for e in dados[MASKS_FIELD] if e[IDENTITY_FIELD] == _KEY_A)
    assert entrada_a["escolhida_em"] == "2026-08-07"
    assert entrada_a[FLAVOR_FIELD] == "dualsense"


def test_arquivo_de_versao_desconhecida_nao_e_lido_nem_sobrescrito(
    tmp_path: Path,
) -> None:
    """Recusar a gravar é mais barato que destruir a escolha de alguém."""
    documento = {VERSION_FIELD: MASKS_SCHEMA_VERSION + 41, MASKS_FIELD: "sei lá"}
    _escrever_mascaras(tmp_path, documento)
    antes = _arquivo_mascaras(tmp_path).read_bytes()

    reg = ExternalMaskRegistry()
    assert reg.mask_for(MAC_A) is None
    assert reg.set_mask(MAC_A, "dualsense") is True
    assert _arquivo_mascaras(tmp_path).read_bytes() == antes

    outro = ExternalMaskRegistry()
    assert outro.mask_for(MAC_A) is None


def test_valor_invalido_e_recusado_e_nao_apaga_a_escolha(tmp_path: Path) -> None:
    """Nem vira ``xbox``, nem vira ``None``: a escolha anterior FICA."""
    reg = ExternalMaskRegistry()
    reg.set_mask(MAC_A, "dualsense")

    for lixo in ("banana", "xbox 360", "", None, 3, ["xbox"]):
        assert reg.set_mask(MAC_A, lixo) is False

    assert reg.mask_for(MAC_A) == "dualsense"
    assert _mascaras_no_disco(tmp_path) == {_KEY_A: "dualsense"}


def test_valor_invalido_no_disco_e_descartado_nao_coagido(tmp_path: Path) -> None:
    _escrever_mascaras(
        tmp_path,
        {
            VERSION_FIELD: MASKS_SCHEMA_VERSION,
            MASKS_FIELD: [
                {IDENTITY_FIELD: _KEY_A, FLAVOR_FIELD: "banana"},
                {IDENTITY_FIELD: _KEY_B, FLAVOR_FIELD: "DualSense"},
            ],
        },
    )
    reg = ExternalMaskRegistry()
    assert reg.mask_for(MAC_A) is None
    assert reg.mask_for(MAC_B) == "dualsense"


def test_o_catalogo_de_mascaras_e_o_do_vpad(tmp_path: Path) -> None:
    """Sem segunda lista: uma máscara que o vpad não sabe criar não é aceita."""
    from hefesto_dualsense4unix.integrations.uinput_gamepad import FLAVORS

    assert mascaras_validas() == frozenset(FLAVORS)
    for chave in FLAVORS:
        assert normalizar_mascara(chave.upper()) == chave
    assert normalizar_mascara("como ele mesmo") is None


def test_identidade_volatil_vale_na_sessao_e_nunca_no_disco(tmp_path: Path) -> None:
    """Limite 1: ``dev:``/``path:``/endereço sintetizado não identificam aparelho."""
    reg = ExternalMaskRegistry()
    assert reg.set_mask(IDENTIDADE_VOLATIL, "xbox") is True
    assert reg.mask_for(IDENTIDADE_VOLATIL) == "xbox"
    assert not _arquivo_mascaras(tmp_path).exists()

    assert reg.set_mask(MAC_A, "dualsense") is True
    assert _mascaras_no_disco(tmp_path) == {_KEY_A: "dualsense"}

    outro = ExternalMaskRegistry()
    assert outro.mask_for(IDENTIDADE_VOLATIL) is None


def test_a_mascara_e_por_rosto_e_nao_por_grupo_do_mesmo_oui(
    tmp_path: Path,
) -> None:
    """Limite 2: a REGRA-NAO-REGISTRO-01 compartilha RANK, nunca identidade."""
    reg = ExternalMaskRegistry()
    reg.set_mask(MAC_A, "dualsense")

    assert reg.mask_for(MAC_B) is None
    reg.set_mask(MAC_B, "xbox")
    assert reg.mask_for(MAC_A) == "dualsense"
    assert _mascaras_no_disco(tmp_path) == {_KEY_A: "dualsense", _KEY_B: "xbox"}


def test_canario_de_fs_o_arquivo_nasce_no_config_isolado(
    tmp_path: Path, _hermetico: Path
) -> None:
    """O arquivo novo respeita o isolamento XDG do ``conftest``."""
    reg = ExternalMaskRegistry()
    reg.set_mask(MAC_A, "xbox")

    assert ExternalMaskRegistry._path() == _hermetico / "controller_masks.json"
    assert _arquivo_mascaras(tmp_path).exists()
    assert sorted(p.name for p in _hermetico.iterdir()) == ["controller_masks.json"]
