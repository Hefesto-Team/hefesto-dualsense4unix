"""Z4/T15 — apagar perfil apaga o lock; a higiene do diretório dela.

Frente **Z4** da ONDA 0 (24/08/2026). Medido em 24/08: 34 `.json` e **37**
`.lock` no diretório real dela — três órfãos (`meu_perfil.json.lock`,
`sackboy_nativo.json.lock`, `vitoria.json.lock`), nenhum com `.json`
correspondente. Cura: `delete_profile` (`profiles/loader.py`) agora apaga o
`.lock` junto, DEPOIS de soltar o `FileLock` (nunca dentro do `with`, onde
apagar o próprio arquivo que tranca o processo seria o convite a uma corrida).

Este módulo NÃO varre nem apaga os órfãos que já estão no disco dela — é
decisão da sprint (§6, T15): "nada automático… se for para limpar, é gesto
com nome na aba Perfis" (Onda 6). Aqui só se prova que um apagar NOVO não
deixa rastro NENHUM.
"""

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
    """``.json``/``.lock`` da RAIZ do diretório — exclui ``.historico/``
    (o backup do PERFIL-SEM-RASTRO-01, um assunto completamente diferente
    do lock órfão que a T15 mede)."""
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

        # MORDIDA: a régua conta ARQUIVOS, não confere um caminho fixo — é a
        # diferença que pega o `.lock` órfão, que um `assert not (dir /
        # 'z4-t15-um.json').exists()` sozinho nunca veria.
        depois = _arquivos_de_perfil(destino)
        assert depois == [], f"sobrou rastro depois de apagar: {depois}"

    def test_nao_sobra_lock_mesmo_quando_o_backup_falha(self, monkeypatch) -> None:  # type: ignore[no-untyped-def]
        """O `.lock` é a ÚLTIMA coisa apagada — mesmo que o histórico
        (backup) dê zebra, a higiene do lock não pode depender dele."""
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
        """Um lock por perfil, sumindo por perfil — não é higiene GLOBAL
        disfarçada que só funciona quando o diretório fica vazio no fim."""
        p1, p2 = _perfil("z4-t15-tres"), _perfil("z4-t15-quatro")
        save_profile(p1, origem="teste:z4-t15")
        save_profile(p2, origem="teste:z4-t15")
        destino = profiles_dir(ensure=True)

        delete_profile(p1.name)

        from hefesto_dualsense4unix.profiles.loader import slugify

        # o `.lock` de p2 SOBREVIVE (normal — p2 nunca foi apagado, e é
        # exatamente esse par 1:1 que a medição de 24/08 achou 34 vezes no
        # disco dela). O que não pode sobrar é QUALQUER rastro de p1.
        slug1, slug2 = slugify(p1.name), slugify(p2.name)
        sobrando = _arquivos_de_perfil(destino)
        assert sobrando == sorted([f"{slug2}.json", f"{slug2}.json.lock"]), (
            f"depois de apagar só {p1.name!r}, o diretório tem {sobrando!r}"
        )
        assert not any(nome.startswith(slug1) for nome in sobrando), (
            f"sobrou rastro de {p1.name!r} (apagado): {sobrando!r}"
        )
