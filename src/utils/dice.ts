export function rollDice(sides: number): number {
  return Math.floor(Math.random() * sides) + 1;
}

export interface DiceResult {
  total: number;
  rolls: number[];
  modifier: number;
}

export function rollDiceExpression(expr: string): DiceResult {
  const match = expr.match(/^(\d+)d(\d+)([+-]\d+)?$/i);
  if (!match) {
    const flat = parseInt(expr, 10);
    return {total: isNaN(flat) ? 0 : flat, rolls: [], modifier: isNaN(flat) ? 0 : flat};
  }
  const count = parseInt(match[1], 10);
  const sides = parseInt(match[2], 10);
  const modifier = match[3] ? parseInt(match[3], 10) : 0;
  const rolls: number[] = [];
  for (let i = 0; i < count; i++) {
    rolls.push(rollDice(sides));
  }
  const total = rolls.reduce((a, b) => a + b, 0) + modifier;
  return {total, rolls, modifier};
}

export function getModifier(stat: number): number {
  return Math.floor((stat - 10) / 2);
}

export function rollInitiative(dexMod: number): number {
  return rollDice(20) + dexMod;
}

export interface AttackResult {
  roll: number;
  total: number;
  isCrit: boolean;
  isFumble: boolean;
}

export function rollAttack(attackBonus: number): AttackResult {
  const roll = rollDice(20);
  return {
    roll,
    total: roll + attackBonus,
    isCrit: roll === 20,
    isFumble: roll === 1,
  };
}

export interface SaveResult {
  roll: number;
  total: number;
  isCrit: boolean;
}

export function rollSavingThrow(modifier: number): SaveResult {
  const roll = rollDice(20);
  return {roll, total: roll + modifier, isCrit: roll === 20};
}

export function formatDiceResult(expr: string, result: DiceResult): string {
  if (result.rolls.length === 0) {
    return `${result.total}`;
  }
  const rollStr = result.rolls.join(', ');
  const modStr =
    result.modifier > 0
      ? ` + ${result.modifier}`
      : result.modifier < 0
      ? ` - ${Math.abs(result.modifier)}`
      : '';
  return `[${expr}] → (${rollStr})${modStr} = ${result.total}`;
}

export function modifierString(mod: number): string {
  return mod >= 0 ? `+${mod}` : `${mod}`;
}
