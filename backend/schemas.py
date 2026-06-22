from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime

import dnd


class CharacterBase(BaseModel):
    name: str
    race: str = "Человек"
    char_class: str = "Воин"
    # 4 base attributes
    strength: int = 5
    dexterity: int = 5
    wisdom: int = 5
    charisma: int = 5
    # Derived stats (auto-computed if not supplied)
    max_hp: int = 12
    phys_defense: int = 2
    mag_defense: int = 2
    mental_defense: int = 7
    phys_attack_bonus: int = 2
    mag_attack_bonus: int = 2
    mental_attack_bonus: int = 2
    damage_dice: str = "1d4"
    abilities: str = ""
    background: str = ""


class CharacterCreate(CharacterBase):
    @model_validator(mode="after")
    def _validate_and_derive(self):
        stats = [self.strength, self.dexterity, self.wisdom, self.charisma]
        for s in stats:
            if s < dnd.STAT_MIN or s > dnd.STAT_MAX:
                raise ValueError(
                    f"Каждая характеристика должна быть от {dnd.STAT_MIN} до {dnd.STAT_MAX}"
                )
        if sum(stats) > dnd.POINT_BUDGET:
            raise ValueError(
                f"Сумма характеристик {sum(stats)} превышает лимит {dnd.POINT_BUDGET}"
            )
        # Auto-compute derived stats from attributes
        derived = dnd.derive_stats(self.strength, self.dexterity, self.wisdom, self.charisma)
        for k, v in derived.items():
            setattr(self, k, v)
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
    is_enemy: int = 0
    # 4 base attributes
    strength: int = 5
    dexterity: int = 5
    wisdom: int = 5
    charisma: int = 5
    # Derived (auto-computed)
    max_hp: int = 12
    phys_defense: int = 2
    mag_defense: int = 2
    mental_defense: int = 7
    attack_bonus: int = 2
    damage_dice: str = "1d4"

    @model_validator(mode="after")
    def _validate_and_derive(self):
        stats = [self.strength, self.dexterity, self.wisdom, self.charisma]
        for s in stats:
            if s < dnd.STAT_MIN or s > dnd.STAT_MAX:
                raise ValueError(
                    f"Каждая характеристика должна быть от {dnd.STAT_MIN} до {dnd.STAT_MAX}"
                )
        if sum(stats) > dnd.POINT_BUDGET:
            raise ValueError(
                f"Сумма характеристик {sum(stats)} превышает лимит {dnd.POINT_BUDGET}"
            )
        derived = dnd.derive_stats(self.strength, self.dexterity, self.wisdom, self.charisma)
        self.max_hp = derived["max_hp"]
        self.phys_defense = derived["phys_defense"]
        self.mag_defense = derived["mag_defense"]
        self.mental_defense = derived["mental_defense"]
        self.attack_bonus = derived["phys_attack_bonus"]
        return self


class NpcOut(NpcCreate):
    id: int
    adventure_id: int
    current_hp: int
    status: str

    class Config:
        from_attributes = True


class NpcRollRequest(BaseModel):
    npc_id: int
    roll_type: str
    target_ac: Optional[int] = None
    damage_dice: Optional[str] = None


class NpcHPUpdateRequest(BaseModel):
    npc_id: int
    delta: int


class AdventureCreate(BaseModel):
    title: str
    description: str
    gm_role: str = "Мастер игры"
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
    scene_state: Optional[dict] = None

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
    roll_type: str  # attack, mag_attack, mental_attack, damage, save_phys, save_mag, save_mental, check_str/dex/wis/cha, initiative
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
    utility_model: str = ""
    utility_temperature: float = 0.2


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
    adventure_id: Optional[int] = None
    description: str = ""
    gm_role: str = "Мастер игры"
    player_count: int = 2
    characters_json: list = []
    npcs_json: list = []


class CharacterPresetCreate(CharacterBase):
    pass


class CharacterPresetOut(CharacterBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class PromptConfigOut(BaseModel):
    system_addendum: str
    turn_reminder: str

    class Config:
        from_attributes = True


class RollRule(BaseModel):
    category: str = "check"
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
    hp_tracking: bool = True
    referee_decide_system: str = ""
    referee_analyze_system: str = ""
