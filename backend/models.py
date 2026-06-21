from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Adventure(Base):
    __tablename__ = "adventures"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    gm_role = Column(String(100), default="Dungeon Master")
    player_count = Column(Integer, nullable=False)
    status = Column(String(20), default="active")  # active, paused, completed
    # When set, the session is blocked waiting for a player dice roll. Holds the
    # roll spec parsed from the LLM directive: {actor, type, dc, reason}.
    pending_roll = Column(JSON, nullable=True)
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
    race = Column(String(50), default="Human")
    char_class = Column(String(50), default="Fighter")
    level = Column(Integer, default=1)

    # D&D Stats
    strength = Column(Integer, default=10)
    dexterity = Column(Integer, default=10)
    constitution = Column(Integer, default=10)
    intelligence = Column(Integer, default=10)
    wisdom = Column(Integer, default=10)
    charisma = Column(Integer, default=10)

    max_hp = Column(Integer, default=10)
    current_hp = Column(Integer, default=10)
    armor_class = Column(Integer, default=10)
    attack_bonus = Column(Integer, default=0)
    damage_dice = Column(String(20), default="1d6")

    abilities = Column(Text, default="")
    background = Column(Text, default="")
    status = Column(String(50), default="alive")  # alive, unconscious, dead

    adventure = relationship("Adventure", back_populates="characters")


class Npc(Base):
    __tablename__ = "npcs"

    id = Column(Integer, primary_key=True, index=True)
    adventure_id = Column(Integer, ForeignKey("adventures.id"), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(String(100), default="")          # злодей, союзник, торговец...
    personality = Column(Text, default="")          # характер, манера речи
    voice_style = Column(Text, default="")          # как говорит
    max_hp = Column(Integer, default=10)
    current_hp = Column(Integer, default=10)
    armor_class = Column(Integer, default=10)
    attack_bonus = Column(Integer, default=0)
    damage_dice = Column(String(20), default="1d6")
    is_enemy = Column(Integer, default=0)           # 1 = враг, 0 = союзник/нейтральный
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
    category = Column(String(50), default="")       # dungeon, horror, intrigue, sea, ...
    description = Column(Text, nullable=False)
    gm_role = Column(String(100), default="Dungeon Master")
    player_count = Column(Integer, default=2)
    characters_json = Column(JSON, default=list)    # list of character dicts
    npcs_json = Column(JSON, default=list)          # list of npc dicts
    is_builtin = Column(Boolean, default=False)     # built-in cannot be deleted
    created_at = Column(DateTime, server_default=func.now())


class PromptConfig(Base):
    """Single-row config (id=1 always)."""
    __tablename__ = "prompt_config"

    id = Column(Integer, primary_key=True, default=1)
    system_addendum = Column(Text, default="")     # appended to every system prompt
    turn_reminder = Column(Text, default="")       # injected into each player message
    # Dice-validation: when enabled, the GM must request rolls via directives and
    # the session blocks until the player submits a result.
    roll_enforcement = Column(Boolean, default=True)
    roll_rules_json = Column(JSON, default=list)   # customizable trigger rules
    # Auto-track HP: apply model-reported damage/healing to the DB automatically.
    hp_tracking = Column(Boolean, default=True)
