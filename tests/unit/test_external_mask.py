"""MÁSCARA-01 / E1 — a máscara mora no APARELHO, em arquivo PRÓPRIO.

*"Como este controle deve aparecer nos jogos?"* — a escolha é do plástico, não
da configuração de jogo (sprint
``docs/process/sprints/2026-07-25-MASCARA-01-como-este-controle-aparece-nos-jogos.md``).

Esta bateria vigia as quatro propriedades que a reavaliação de 07/08/2026 pôs no
lugar do *"bump de esquema"* que a sprint original pedia:

1. o ``controllers.json`` **não é tocado** e a fila **não é renumerada** (os
   quatro fatos MEDIDOS estão no cabeçalho de ``external_mask.py``);
2. valor inválido **nunca vira Xbox** nem apaga a escolha dela;
3. identidade VOLÁTIL vale na sessão e **não vai ao disco**;
4. arquivo de versão desconhecida **não é lido nem sobrescrito**, e campo que
   não entendemos **sobrevive** ao save.

Bancada espelhada de ``test_external_identity.py``: faixa forjada ``aa:bb:cc:*``
(regra da casa — nada de MAC real em arquivo versionado), ``config_dir`` em
``tmp_path``, nenhum aparelho, nenhum GTK, nenhum Xvfb.
"""
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

#: Dois ROSTOS do mesmo OUI forjado — é o par que a REGRA-NAO-REGISTRO-01 faz
#: dividir um LUGAR na fila, e que aqui tem de continuar com máscaras separadas.
MAC_A = "aa:bb:cc:00:be:ef"
MAC_B = "aa:bb:cc:00:be:f0"
MAC_DS = "aa:bb:cc:00:00:01"

_KEY_A = MAC_A.replace(":", "")
_KEY_B = MAC_B.replace(":", "")
_KEY_DS = MAC_DS.replace(":", "")

#: Identidade VOLÁTIL, no formato que ``_external_dedup_key`` devolve quando o
#: ``uniq`` falta ou é o endereço sintetizado pelo ``usb_probe_degrade``.
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


# --- o que a entrega promete -------------------------------------------------


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
    """``mask_for_entry`` casa pelo MESMO campo com que o daemon numera.

    Se a máscara fosse procurada por outra chave, ela ficaria pendurada num
    aparelho e o número noutro — que é o defeito que ``identity_for_entry``
    existe para impedir (CLONE-01).
    """
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


# --- os quatro fatos MEDIDOS que fecharam a porta do bump de esquema ---------


def test_a_mascara_nao_toca_o_controllers_json_nem_renumera_a_fila(
    tmp_path: Path,
) -> None:
    """O fato que reescreveu a E1: guardar a máscara na fila é DESTRUTIVO.

    ``identity.load`` descarta a fila inteira quando a versão difere
    (``identity.py:858``), e ``_save_locked`` só aproveita as entradas do outro
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
    """A lição do ``payload = {}`` (``identity.py:951``), aplicada contra nós.

    Quem monta o documento do zero destrói o que o outro escritor sabia. O save
    daqui é read-modify-write: chave de TOPO e campo POR ENTRADA que não são
    nossos continuam no arquivo.
    """
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
    """Recusar a gravar é mais barato que destruir a escolha de alguém.

    O ``controllers.json`` descarta o arquivo de outro schema porque a REGRA de
    numeração mudou e a numeração velha não pode congelar. Máscara não tem esse
    problema: um documento que não entendemos é escolha de alguém, e a resposta
    honesta é ficar quieto.
    """
    documento = {VERSION_FIELD: MASKS_SCHEMA_VERSION + 41, MASKS_FIELD: "sei lá"}
    _escrever_mascaras(tmp_path, documento)
    antes = _arquivo_mascaras(tmp_path).read_bytes()

    reg = ExternalMaskRegistry()
    assert reg.mask_for(MAC_A) is None
    assert reg.set_mask(MAC_A, "dualsense") is True  # vale na sessão
    assert _arquivo_mascaras(tmp_path).read_bytes() == antes

    outro = ExternalMaskRegistry()
    assert outro.mask_for(MAC_A) is None


# --- valor inválido nunca vira Xbox -----------------------------------------


def test_valor_invalido_e_recusado_e_nao_apaga_a_escolha(tmp_path: Path) -> None:
    """Nem vira ``xbox``, nem vira ``None``: a escolha anterior FICA.

    Esta casa já pagou o ``or "xbox"`` do editor de perfis, que transformava
    *"sem opinião"* em *"exige Xbox"* (ESCOLHA-DELA-VENCE-01, E1). O erro
    simétrico — inválido tratado como "limpar" — apagaria a escolha dela em
    silêncio. Quem quer *"como ele mesmo"* chama ``clear_mask``.
    """
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


# --- limites declarados, GRAU MEDIDO ----------------------------------------


def test_identidade_volatil_vale_na_sessao_e_nunca_no_disco(tmp_path: Path) -> None:
    """Limite 1: ``dev:``/``path:``/endereço sintetizado não identificam aparelho.

    Persistir máscara ali seria gravar a escolha em cima de uma chave que dois
    aparelhos diferentes podem dividir (CLONE-01 — dois Nintendo-class
    degradados no cabo entregam o MESMO ``uniq``).
    """
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
    """Limite 2: a REGRA-NAO-REGISTRO-01 compartilha RANK, nunca identidade.

    Os dois endereços de hardware do 8BitDo dividem um LUGAR na fila e seguem
    sendo duas chaves. Máscara posta num rosto não vale no outro — e o teste
    ``test_dois_aparelhos_do_mesmo_oui_nunca_se_fundem`` da bancada irmã diz por
    que isso não pode ser "consertado" por OUI.
    """
    reg = ExternalMaskRegistry()
    reg.set_mask(MAC_A, "dualsense")

    assert reg.mask_for(MAC_B) is None
    reg.set_mask(MAC_B, "xbox")
    assert reg.mask_for(MAC_A) == "dualsense"
    assert _mascaras_no_disco(tmp_path) == {_KEY_A: "dualsense", _KEY_B: "xbox"}


# --- canário de FS (CANARIO-FS-01) ------------------------------------------


def test_canario_de_fs_o_arquivo_nasce_no_config_isolado(
    tmp_path: Path, _hermetico: Path
) -> None:
    """O arquivo novo respeita o isolamento XDG do ``conftest``."""
    reg = ExternalMaskRegistry()
    reg.set_mask(MAC_A, "xbox")

    assert ExternalMaskRegistry._path() == _hermetico / "controller_masks.json"
    assert _arquivo_mascaras(tmp_path).exists()
    assert sorted(p.name for p in _hermetico.iterdir()) == ["controller_masks.json"]
