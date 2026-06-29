"""Экономика навыков: получение навыка из тома (манифест: навыки).

Навык покупается за деньги и остаётся с персонажем навсегда (его нельзя
продать). Один из путей получить навык — **прочитать том**: купленный том лежит
в инвентаре, при чтении он расходуется, а персонаж получает постоянный навык,
который больше не занимает слот инвентаря.
"""
from __future__ import annotations

from ..db.models import Character, SpellBook, Skill


class LearnError(ValueError):
    """Навык нельзя выучить (том ничему не учит или уже выучен)."""


def learn_from_tome(character: Character, tome: SpellBook) -> Skill:
    """Прочитать том: выдать персонажу навык и израсходовать том.

    Идемпотентно по навыку (повторное чтение не дублирует навык). Том удаляется
    из инвентаря персонажа, если он там был.
    """
    skill = tome.teaches_skill
    if skill is None:
        raise LearnError(f"Том «{tome.name}» не обучает навыку")

    if skill not in character.skills:
        character.skills.append(skill)

    # том прочитан и израсходован — освобождает слот инвентаря
    if tome in character.inventory:
        character.inventory.remove(tome)

    return skill
