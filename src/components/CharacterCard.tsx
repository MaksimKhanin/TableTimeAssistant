import React from 'react';
import {View, Text, StyleSheet} from 'react-native';
import {Character} from '../types';
import {getModifier, modifierString} from '../utils/dice';

interface Props {
  character: Character;
  compact?: boolean;
}

function HpBar({hp, maxHp}: {hp: number; maxHp: number}) {
  const pct = maxHp > 0 ? Math.max(0, Math.min(1, hp / maxHp)) : 0;
  const color =
    pct > 0.6 ? '#4caf50' : pct > 0.3 ? '#ff9800' : '#f44336';
  return (
    <View style={hpStyles.track}>
      <View style={[hpStyles.fill, {width: `${pct * 100}%` as any, backgroundColor: color}]} />
    </View>
  );
}

const hpStyles = StyleSheet.create({
  track: {
    height: 6,
    backgroundColor: '#0d0d1a',
    borderRadius: 3,
    overflow: 'hidden',
    marginTop: 4,
  },
  fill: {
    height: '100%',
    borderRadius: 3,
  },
});

const STAT_KEYS: (keyof Character['stats'])[] = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'];

export default function CharacterCard({character, compact}: Props) {
  if (compact) {
    return (
      <View style={styles.compact}>
        <Text style={styles.compactName}>{character.name}</Text>
        <Text style={styles.compactSub}>
          {character.race} {character.class} | AC {character.ac}
        </Text>
        <HpBar hp={character.hp} maxHp={character.maxHp} />
        <Text style={styles.compactHp}>
          {character.hp}/{character.maxHp} HP
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.name}>{character.name}</Text>
          <Text style={styles.sub}>
            Level {character.level} {character.race} {character.class}
          </Text>
        </View>
        <View style={styles.acBadge}>
          <Text style={styles.acText}>{character.ac}</Text>
          <Text style={styles.acLabel}>AC</Text>
        </View>
      </View>
      <HpBar hp={character.hp} maxHp={character.maxHp} />
      <Text style={styles.hpText}>
        HP: {character.hp}/{character.maxHp}
      </Text>
      <View style={styles.statsRow}>
        {STAT_KEYS.map(key => (
          <View key={key} style={styles.statBox}>
            <Text style={styles.statLabel}>{key}</Text>
            <Text style={styles.statVal}>{character.stats[key]}</Text>
            <Text style={styles.statMod}>
              {modifierString(getModifier(character.stats[key]))}
            </Text>
          </View>
        ))}
      </View>
      {character.abilities.length > 0 && (
        <View style={styles.abilitiesBlock}>
          <Text style={styles.sectionLabel}>Abilities:</Text>
          {character.abilities.map((a, i) => (
            <Text key={i} style={styles.abilityText}>• {a}</Text>
          ))}
        </View>
      )}
      {character.attacks.length > 0 && (
        <View style={styles.attacksBlock}>
          <Text style={styles.sectionLabel}>Attacks:</Text>
          {character.attacks.map((atk, i) => (
            <Text key={i} style={styles.attackText}>
              ⚔️ {atk.name} (+{atk.attackBonus} hit, {atk.damage} {atk.damageType})
            </Text>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 14,
    marginVertical: 6,
    borderWidth: 1,
    borderColor: '#2d2d4e',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 4,
  },
  headerLeft: {flex: 1},
  name: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 18,
  },
  sub: {
    color: '#a0a0b0',
    fontSize: 13,
  },
  acBadge: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#0d0d1a',
    borderWidth: 2,
    borderColor: '#c9a84c',
    alignItems: 'center',
    justifyContent: 'center',
  },
  acText: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 16,
    lineHeight: 18,
  },
  acLabel: {
    color: '#666',
    fontSize: 9,
  },
  hpText: {
    color: '#a0a0b0',
    fontSize: 12,
    marginTop: 4,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 12,
  },
  statBox: {
    alignItems: 'center',
    flex: 1,
    backgroundColor: '#0d0d1a',
    borderRadius: 6,
    paddingVertical: 6,
    marginHorizontal: 2,
  },
  statLabel: {
    color: '#666',
    fontSize: 10,
    fontWeight: 'bold',
  },
  statVal: {
    color: '#e8e8e8',
    fontSize: 16,
    fontWeight: 'bold',
  },
  statMod: {
    color: '#c9a84c',
    fontSize: 11,
  },
  sectionLabel: {
    color: '#c9a84c',
    fontSize: 12,
    fontWeight: 'bold',
    marginBottom: 2,
  },
  abilitiesBlock: {marginTop: 10},
  abilityText: {
    color: '#b0b0c0',
    fontSize: 13,
  },
  attacksBlock: {marginTop: 8},
  attackText: {
    color: '#e8e8e8',
    fontSize: 13,
    marginVertical: 1,
  },
  compact: {
    backgroundColor: '#16213e',
    borderRadius: 8,
    padding: 10,
    borderWidth: 1,
    borderColor: '#2d2d4e',
    marginVertical: 4,
  },
  compactName: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 14,
  },
  compactSub: {
    color: '#a0a0b0',
    fontSize: 12,
  },
  compactHp: {
    color: '#a0a0b0',
    fontSize: 11,
    marginTop: 2,
  },
});
