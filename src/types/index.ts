export interface CharacterStats {
  STR: number;
  DEX: number;
  CON: number;
  INT: number;
  WIS: number;
  CHA: number;
}

export interface Attack {
  name: string;
  attackBonus: number;
  damage: string;
  damageType: string;
}

export interface Character {
  id: string;
  name: string;
  race: string;
  class: string;
  level: number;
  hp: number;
  maxHp: number;
  ac: number;
  stats: CharacterStats;
  abilities: string[];
  attacks: Attack[];
  initiative?: number;
}

export interface Enemy {
  id: string;
  name: string;
  hp: number;
  maxHp: number;
  ac: number;
  attackBonus: number;
  damage: string;
  initiative?: number;
}

export interface Combatant {
  id: string;
  name: string;
  initiative: number;
  hp: number;
  maxHp: number;
  isPlayer: boolean;
  ac: number;
}

export interface CombatState {
  active: boolean;
  round: number;
  initiativeOrder: Combatant[];
  currentTurnIndex: number;
  enemies: Enemy[];
}

export type MessageRole = 'dm' | 'player' | 'system';

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  playerName?: string;
}

export interface Adventure {
  id: string;
  name: string;
  description: string;
  characters: Character[];
  messages: Message[];
  createdAt: string;
  updatedAt: string;
  combatState?: CombatState;
}

export type RootStackParamList = {
  Home: undefined;
  ModelSetup: undefined;
  AdventureSetup: {adventureId?: string};
  Game: {adventureId: string};
  Combat: {adventureId: string};
};
