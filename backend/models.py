from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
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
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    characters = relationship("Character", back_populates="adventure", cascade="all, delete-orphan")
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
