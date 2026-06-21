from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime

import dnd


class CharacterBase(BaseModel):
    name: str
    race: str = "Human"
    char_class: str = "Fighter"
    strength: int = 10
    dexterity: int = 10
    constitution: int = 10
    intelligence: int = 10
    wisdom: int = 10
    charisma: int = 10
    max_hp: int = 10
    armor_class: int = 10
    attack_bonus: int = 0
    damage_dice: str = "1d6"
    abilities: str = ""
    background: str = ""


class CharacterCreate(CharacterBase):
    @model_validator(mode="after")
    def _check_point_budget(self):
        stats = [getattr(self, k) for k in dnd.STAT_KEYS]
        for s in stats:
            if s < dnd.STAT_MIN or s > dnd.STAT_MAX:
                raise ValueError(f"Каждая характеристика должна быть от {dnd.STAT_MIN} до {dnd.STAT_MAX}")
        if sum(stats) > dnd.POINT_BUDGET:
            raise ValueError(
                f"Сумма характеристик {sum(stats)} превышает лимит {dnd.POINT_BUDGET}"
            )
        return self


class CharacterOut(CharacterBase):
    id: int
    adventure_id: int
    current_hp: int
    status: str

    class Config:
        from_attributes = True


class NpcCreate(BaseModel):
    name: str
    role: str = ""
    personality: str = ""
    voice_style: str = ""
    max_hp: int = 10
    armor_class: int = 10
    attack_bonus: int = 0
    damage_dice: str = "1d6"
    is_enemy: int = 0


class NpcOut(NpcCreate):
    id: int
    adventure_id: int
    current_hp: int
    status: str

    class Config:
        from_attributes = True


class NpcRollRequest(BaseModel):
    npc_id: int
    roll_type: str          # attack, damage, d20, d6, ...
    target_ac: Optional[int] = None
    damage_dice: Optional[str] = None


class NpcHPUpdateRequest(BaseModel):
    npc_id: int
    delta: int


class AdventureCreate(BaseModel):
    title: str
    description: str
    gm_role: str = "Dungeon Master"
    player_count: int = Field(ge=1, le=4)
    characters: list[CharacterCreate]
    npcs: list[NpcCreate] = []


class AdventureOut(BaseModel):
    id: int
    title: str
    description: str
    gm_role: str
    player_count: int
    status: str
    created_at: datetime
    characters: list[CharacterOut]
    npcs: list[NpcOut]

    class Config:
        from_attributes = True


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    player_name: Optional[str]
    metadata_: Optional[dict]
    created_at: datetime

    class Config:
        from_attributes = True


class PlayerAction(BaseModel):
    player_name: str
    action: str
    target: Optional[str] = None


class DiceRollRequest(BaseModel):
    character_id: int
    roll_type: str  # attack, damage, initiative, save_str, save_dex, etc.
    target_ac: Optional[int] = None
    damage_dice: Optional[str] = None


class HPUpdateRequest(BaseModel):
    character_id: int
    delta: int  # positive = heal, negative = damage


class LLMConfigUpdate(BaseModel):
    base_url: str
    model: str
    temperature: float = 0.8
    max_tokens: int = 2048
    show_thinking: bool = False
    use_tools: bool = False


class TemplateOut(BaseModel):
    id: int
    title: str
    category: str
    description: str
    gm_role: str
    player_count: int
    characters_json: list
    npcs_json: list
    is_builtin: bool

    class Config:
        from_attributes = True


class TemplateSaveRequest(BaseModel):
    title: str
    category: str = ""
    adventure_id: Optional[int] = None   # save from existing adventure
    # or provide data directly:
    description: str = ""
    gm_role: str = "Dungeon Master"
    player_count: int = 2
    characters_json: list = []
    npcs_json: list = []


class PromptConfigOut(BaseModel):
    system_addendum: str
    turn_reminder: str

    class Config:
        from_attributes = True


class RollRule(BaseModel):
    category: str = "check"          # save | attack | check | initiative
    name: str = ""
    when: str = ""
    die: str = "d20"
    default_dc: Optional[int] = None
    enabled: bool = True


class PromptConfigUpdate(BaseModel):
    system_addendum: str = ""
    turn_reminder: str = ""
    roll_enforcement: bool = True
    roll_rules: list[RollRule] = []
