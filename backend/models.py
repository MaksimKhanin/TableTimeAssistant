from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Adventure(Base):
    __tablename__ = "adventures"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    gm_role = Column(String(100), default="Мастер игры")
    player_count = Column(Integer, nullable=False)
    status = Column(String(20), default="active")  # active, paused, completed
    pending_roll = Column(JSON, nullable=True)
    scene_state = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    characters = relationship("Character", back_populates="adventure", cascade="all, delete-orphan")
    npcs = relationship("Npc", back_populates="adventure", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="adventure", cascade="all, delete-orphan")


class Character(Base):
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    adventure_id = Column(Integer, ForeignKey("adventures.id"), nullable=False)
    name = Column(String(100), nullable=False)
    race = Column(String(50), default="Человек")
    char_class = Column(String(50), default="Воин")

    # 4 base attributes (default 5; budget 30 total)
    strength = Column(Integer, default=5)
    dexterity = Column(Integer, default=5)
    wisdom = Column(Integer, default=5)
    charisma = Column(Integer, default=5)

    # Derived stats (computed at creation time from attributes)
    max_hp = Column(Integer, default=12)          # 10 + str//2
    current_hp = Column(Integer, default=12)
    phys_defense = Column(Integer, default=2)     # dex//2
    mag_defense = Column(Integer, default=2)      # wis//2
    mental_defense = Column(Integer, default=7)   # 5 + cha//2
    phys_attack_bonus = Column(Integer, default=2)   # dex//2
    mag_attack_bonus = Column(Integer, default=2)    # wis//2
    mental_attack_bonus = Column(Integer, default=2) # cha//2
    damage_dice = Column(String(20), default="1d4")  # base physical damage (modifier added at roll)

    abilities = Column(Text, default="")
    background = Column(Text, default="")
    status = Column(String(50), default="alive")  # alive, unconscious, dead

    adventure = relationship("Adventure", back_populates="characters")


class Npc(Base):
    __tablename__ = "npcs"

    id = Column(Integer, primary_key=True, index=True)
    adventure_id = Column(Integer, ForeignKey("adventures.id"), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(100), default="")
    personality = Column(Text, default="")
    voice_style = Column(Text, default="")

    # 4 base attributes (same system as characters)
    strength = Column(Integer, default=5)
    dexterity = Column(Integer, default=5)
    wisdom = Column(Integer, default=5)
    charisma = Column(Integer, default=5)

    # Derived stats
    max_hp = Column(Integer, default=12)
    current_hp = Column(Integer, default=12)
    phys_defense = Column(Integer, default=2)
    mag_defense = Column(Integer, default=2)
    mental_defense = Column(Integer, default=7)
    attack_bonus = Column(Integer, default=2)     # = phys_attack_bonus (dex//2)
    damage_dice = Column(String(20), default="1d4")
    is_enemy = Column(Integer, default=0)
    status = Column(String(50), default="alive")

    adventure = relationship("Adventure", back_populates="npcs")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    adventure_id = Column(Integer, ForeignKey("adventures.id"), nullable=False)
    role = Column(String(20), nullable=False)  # system, user, assistant, dice
    content = Column(Text, nullable=False)
    player_name = Column(String(100), nullable=True)
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    adventure = relationship("Adventure", back_populates="messages")


class AdventureTemplate(Base):
    __tablename__ = "adventure_templates"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    category = Column(String(50), default="")
    description = Column(Text, nullable=False)
    gm_role = Column(String(100), default="Мастер игры")
    player_count = Column(Integer, default=2)
    characters_json = Column(JSON, default=list)
    npcs_json = Column(JSON, default=list)
    is_builtin = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class CharacterPreset(Base):
    """Библиотека готовых персонажей для повторного использования."""
    __tablename__ = "character_presets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    race = Column(String(50), default="Человек")
    char_class = Column(String(50), default="Воин")
    strength = Column(Integer, default=5)
    dexterity = Column(Integer, default=5)
    wisdom = Column(Integer, default=5)
    charisma = Column(Integer, default=5)
    max_hp = Column(Integer, default=12)
    phys_defense = Column(Integer, default=2)
    mag_defense = Column(Integer, default=2)
    mental_defense = Column(Integer, default=7)
    damage_dice = Column(String(20), default="1d4")
    abilities = Column(Text, default="")
    background = Column(Text, default="")
    created_at = Column(DateTime, server_default=func.now())


class PromptConfig(Base):
    """Single-row config (id=1 always)."""
    __tablename__ = "prompt_config"

    id = Column(Integer, primary_key=True, default=1)
    system_addendum = Column(Text, default="")
    turn_reminder = Column(Text, default="")
    roll_enforcement = Column(Boolean, default=True)
    roll_rules_json = Column(JSON, default=list)
    hp_tracking = Column(Boolean, default=True)
    referee_decide_system = Column(Text, default="")
    referee_analyze_system = Column(Text, default="")
