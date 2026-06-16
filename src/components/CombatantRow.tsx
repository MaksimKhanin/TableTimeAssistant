import React from 'react';
import {View, Text, TouchableOpacity, StyleSheet} from 'react-native';
import {Combatant} from '../types';

interface Props {
  combatant: Combatant;
  isCurrentTurn: boolean;
  onHpChange: (id: string, delta: number) => void;
}

export default function CombatantRow({
  combatant,
  isCurrentTurn,
  onHpChange,
}: Props) {
  const isDead = combatant.hp <= 0;
  const pct =
    combatant.maxHp > 0
      ? Math.max(0, Math.min(1, combatant.hp / combatant.maxHp))
      : 0;
  const barColor =
    pct > 0.6 ? '#4caf50' : pct > 0.3 ? '#ff9800' : '#f44336';

  return (
    <View
      style={[
        styles.row,
        isCurrentTurn && styles.activeTurn,
        isDead && styles.deadRow,
        !combatant.isPlayer && styles.enemyRow,
      ]}>
      <View style={styles.initBadge}>
        <Text style={styles.initText}>{combatant.initiative}</Text>
      </View>
      <View style={styles.info}>
        <View style={styles.nameRow}>
          <Text style={[styles.name, isDead && styles.deadName]}>
            {combatant.isPlayer ? '⚔️' : '👹'} {combatant.name}
          </Text>
          {isDead && <Text style={styles.deadTag}>DEAD</Text>}
          {isCurrentTurn && !isDead && (
            <Text style={styles.turnTag}>TURN</Text>
          )}
        </View>
        <View style={styles.hpTrack}>
          <View
            style={[
              styles.hpFill,
              {width: `${pct * 100}%` as any, backgroundColor: barColor},
            ]}
          />
        </View>
        <Text style={styles.hpLabel}>
          HP: {combatant.hp}/{combatant.maxHp} | AC: {combatant.ac}
        </Text>
      </View>
      <View style={styles.controls}>
        <TouchableOpacity
          style={styles.dmgBtn}
          onPress={() => onHpChange(combatant.id, -1)}>
          <Text style={styles.btnText}>-1</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.healBtn}
          onPress={() => onHpChange(combatant.id, 1)}>
          <Text style={styles.btnText}>+1</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#16213e',
    borderRadius: 10,
    padding: 10,
    marginVertical: 4,
    borderWidth: 1,
    borderColor: '#2d2d4e',
    gap: 10,
  },
  activeTurn: {
    borderColor: '#c9a84c',
    borderWidth: 2,
    backgroundColor: '#1e2a4e',
  },
  deadRow: {
    opacity: 0.45,
  },
  enemyRow: {
    borderLeftWidth: 3,
    borderLeftColor: '#8b0000',
  },
  initBadge: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#0d0d1a',
    borderWidth: 1,
    borderColor: '#c9a84c',
    alignItems: 'center',
    justifyContent: 'center',
  },
  initText: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 14,
  },
  info: {flex: 1},
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  name: {
    color: '#e8e8e8',
    fontWeight: 'bold',
    fontSize: 14,
    flex: 1,
  },
  deadName: {
    color: '#666',
    textDecorationLine: 'line-through',
  },
  deadTag: {
    color: '#f44336',
    fontSize: 10,
    fontWeight: 'bold',
    backgroundColor: '#3d0000',
    paddingHorizontal: 5,
    paddingVertical: 2,
    borderRadius: 4,
  },
  turnTag: {
    color: '#c9a84c',
    fontSize: 10,
    fontWeight: 'bold',
    backgroundColor: '#3d3000',
    paddingHorizontal: 5,
    paddingVertical: 2,
    borderRadius: 4,
  },
  hpTrack: {
    height: 5,
    backgroundColor: '#0d0d1a',
    borderRadius: 3,
    overflow: 'hidden',
  },
  hpFill: {
    height: '100%',
    borderRadius: 3,
  },
  hpLabel: {
    color: '#a0a0b0',
    fontSize: 11,
    marginTop: 3,
  },
  controls: {
    flexDirection: 'row',
    gap: 6,
  },
  dmgBtn: {
    backgroundColor: '#5c0000',
    borderRadius: 6,
    paddingVertical: 6,
    paddingHorizontal: 8,
  },
  healBtn: {
    backgroundColor: '#0a4a0a',
    borderRadius: 6,
    paddingVertical: 6,
    paddingHorizontal: 8,
  },
  btnText: {
    color: '#e8e8e8',
    fontWeight: 'bold',
    fontSize: 13,
  },
});
