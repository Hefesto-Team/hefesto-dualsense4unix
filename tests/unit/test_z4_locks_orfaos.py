"""Z4/T15 — apagar perfil apaga o lock; a higiene do diretório dela."""

from __future__ import annotations

from hefesto_dualsense4unix.profiles.loader import (
    delete_profile,
    profiles_dir,
    save_profile,
)
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile


def _perfil(nome: str) -> Profile:
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=[f"steam_app_{nome}"]),
        priority=1,
    )


def _arquivos_de_perfil(destino: object) -> list[str]:
    """``.json``/``.lock`` da RAIZ do diretório — exclui ``.historico/``"""
    from pathlib import Path

    assert isinstance(destino, Path)
    return sorted(p.name for p in destino.iterdir() if p.is_file())


class TestApagarPerfilApagaOLock:
    def test_nem_json_nem_lock_sobrevivem(self) -> None:
        perfil = _perfil("z4-t15-um")
        save_profile(perfil, origem="teste:z4-t15")
        destino = profiles_dir(ensure=True)

        antes = sorted(p.name for p in destino.glob("*"))
        assert f"{perfil.name}.json" in antes or any(
            n.endswith(".json") for n in antes
        ), "setup inválido: o perfil não foi gravado"

        delete_profile(perfil.name)

        depois = _arquivos_de_perfil(destino)
        assert depois == [], f"sobrou rastro depois de apagar: {depois}"

    def test_nao_sobra_lock_mesmo_quando_o_backup_falha(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """O `.lock` é a ÚLTIMA coisa apagada — mesmo que o histórico"""
        import hefesto_dualsense4unix.profiles.loader as loader_mod

        perfil = _perfil("z4-t15-dois")
        save_profile(perfil, origem="teste:z4-t15")
        destino = profiles_dir(ensure=True)

        monkeypatch.setattr(
            loader_mod, "_arquivar_versao", lambda *a, **kw: None
        )
        delete_profile(perfil.name)

        depois = _arquivos_de_perfil(destino)
        assert depois == [], depois

    def test_apagar_dois_perfis_nao_deixa_lock_de_nenhum(self) -> None:
        """Um lock por perfil, sumindo por perfil — não é higiene GLOBAL"""
        p1, p2 = _perfil("z4-t15-tres"), _perfil("z4-t15-quatro")
        save_profile(p1, origem="teste:z4-t15")
        save_profile(p2, origem="teste:z4-t15")
        destino = profiles_dir(ensure=True)

        delete_profile(p1.name)

        from hefesto_dualsense4unix.profiles.loader import slugify

        slug1, slug2 = slugify(p1.name), slugify(p2.name)
        sobrando = _arquivos_de_perfil(destino)
        assert sobrando == sorted([f"{slug2}.json", f"{slug2}.json.lock"]), (
            f"depois de apagar só {p1.name!r}, o diretório tem {sobrando!r}"
        )
        assert not any(nome.startswith(slug1) for nome in sobrando), (
            f"sobrou rastro de {p1.name!r} (apagado): {sobrando!r}"
        )
