import React, {useCallback, useState} from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Alert,
} from 'react-native';
import {useFocusEffect, useNavigation, useRoute, RouteProp} from '@react-navigation/native';
import {NativeStackNavigationProp} from '@react-navigation/native-stack';
import {v4 as uuidv4} from 'uuid';
import {Adventure, Combatant, Enemy, Message, RootStackParamList} from '../types';
import {getAdventure, saveAdventure} from '../services/storageService';
import {
  rollDice,
  rollDiceExpression,
  rollInitiative,
  rollAttack,
  getModifier,
  formatDiceResult,
} from '../utils/dice';
import CombatantRow from '../components/CombatantRow';
import DiceRoller from '../components/DiceRoller';

type Nav = NativeStackNavigationProp<RootStackParamList, 'Combat'>;
type Route = RouteProp<RootStackParamList, 'Combat'>;

interface CombatLog {
  id: string;
  text: string;
  type: 'attack' | 'damage' | 'heal' | 'initiative' | 'info';
}

export default function CombatScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const {adventureId} = route.params;

  const [adventure, setAdventure] = useState<Adventure | null>(null);
  const [combatants, setCombatants] = useState<Combatant[]>([]);
  const [enemies, setEnemies] = useState<Enemy[]>([]);
  const [round, setRound] = useState(1);
  const [currentTurn, setCurrentTurn] = useState(0);
  const [log, setLog] = useState<CombatLog[]>([]);
  const [combatStarted, setCombatStarted] = useState(false);

  const [newEnemyName, setNewEnemyName] = useState('');
  const [newEnemyHp, setNewEnemyHp] = useState('20');
  const [newEnemyAc, setNewEnemyAc] = useState('12');
  const [newEnemyAtk, setNewEnemyAtk] = useState('3');
  const [newEnemyDmg, setNewEnemyDmg] = useState('1d6+2');

  useFocusEffect(
    useCallback(() => {
      getAdventure(adventureId).then(adv => {
        if (!adv) return;
        setAdventure(adv);
        if (adv.combatState?.active) {
          setCombatants(adv.combatState.initiativeOrder);
          setEnemies(adv.combatState.enemies);
          setRound(adv.combatState.round);
          setCurrentTurn(adv.combatState.currentTurnIndex);
          setCombatStarted(true);
        }
      });
    }, [adventureId]),
  );

  const addLog = (text: string, type: CombatLog['type'] = 'info') => {
    setLog(prev => [{id: uuidv4(), text, type}, ...prev]);
  };

  const saveCombatState = async (
    newCombatants: Combatant[],
    newEnemies: Enemy[],
    newRound: number,
    newTurn: number,
    active: boolean,
  ) => {
    if (!adventure) return;
    const updated: Adventure = {
      ...adventure,
      updatedAt: new Date().toISOString(),
      combatState: {
        active,
        round: newRound,
        initiativeOrder: newCombatants,
        currentTurnIndex: newTurn,
        enemies: newEnemies,
      },
    };
    setAdventure(updated);
    await saveAdventure(updated);
  };

  const startCombat = () => {
    if (!adventure) return;
    const combatantList: Combatant[] = adventure.characters.map(char => ({
      id: char.id,
      name: char.name,
      initiative: rollInitiative(getModifier(char.stats.DEX)),
      hp: char.hp,
      maxHp: char.maxHp,
      isPlayer: true,
      ac: char.ac,
    }));
    const enemyCombatants: Combatant[] = enemies.map(e => ({
      id: e.id,
      name: e.name,
      initiative: rollInitiative(0),
      hp: e.hp,
      maxHp: e.maxHp,
      isPlayer: false,
      ac: e.ac,
    }));
    const all = [...combatantList, ...enemyCombatants].sort(
      (a, b) => b.initiative - a.initiative,
    );
    all.forEach(c => addLog(`🎲 ${c.name} rolls ${c.initiative} for initiative`, 'initiative'));
    setCombatants(all);
    setCurrentTurn(0);
    setRound(1);
    setCombatStarted(true);
    saveCombatState(all, enemies, 1, 0, true);
    addLog(`⚔️ Round 1 begins! ${all[0]?.name} goes first.`, 'info');
  };

  const addEnemy = () => {
    if (!newEnemyName.trim()) {
      Alert.alert('Missing Info', 'Enter an enemy name');
      return;
    }
    const hp = parseInt(newEnemyHp, 10) || 20;
    const enemy: Enemy = {
      id: uuidv4(),
      name: newEnemyName.trim(),
      hp,
      maxHp: hp,
      ac: parseInt(newEnemyAc, 10) || 12,
      attackBonus: parseInt(newEnemyAtk, 10) || 3,
      damage: newEnemyDmg || '1d6+2',
    };
    const newEnemies = [...enemies, enemy];
    setEnemies(newEnemies);
    setNewEnemyName('');
    addLog(`👹 ${enemy.name} joins the battlefield`, 'info');
    if (!combatStarted) {
      saveCombatState(combatants, newEnemies, round, currentTurn, false);
    }
  };

  const handleHpChange = async (id: string, delta: number) => {
    const newCombatants = combatants.map(c => {
      if (c.id !== id) return c;
      const newHp = Math.max(0, Math.min(c.maxHp, c.hp + delta));
      if (delta < 0) {
        addLog(`💀 ${c.name} takes ${Math.abs(delta)} damage → ${newHp} HP`, 'damage');
      } else {
        addLog(`💚 ${c.name} heals ${delta} → ${newHp} HP`, 'heal');
      }
      return {...c, hp: newHp};
    });
    setCombatants(newCombatants);
    await saveCombatState(newCombatants, enemies, round, currentTurn, true);
  };

  const handleBulkDamage = async (id: string, amount: number) => {
    const newCombatants = combatants.map(c => {
      if (c.id !== id) return c;
      const newHp = Math.max(0, c.hp - amount);
      addLog(`💀 ${c.name} takes ${amount} damage → ${newHp} HP`, 'damage');
      if (newHp === 0) addLog(`☠️ ${c.name} is down!`, 'info');
      return {...c, hp: newHp};
    });
    setCombatants(newCombatants);
    await saveCombatState(newCombatants, enemies, round, currentTurn, true);
  };

  const handlePlayerAttack = (targetId: string) => {
    const attacker = combatants[currentTurn];
    const target = combatants.find(c => c.id === targetId);
    if (!attacker || !target) return;
    const char = adventure?.characters.find(c => c.id === attacker.id);
    const atk = char?.attacks[0];
    const attackBonus = atk?.attackBonus ?? 0;
    const {roll, total, isCrit, isFumble} = rollAttack(attackBonus);
    const hitStr = isCrit ? ' 🌟 CRITICAL HIT!' : isFumble ? ' 💨 FUMBLE!' : total >= target.ac ? ' HIT!' : ' MISS';
    addLog(`⚔️ ${attacker.name} attacks ${target.name}: d20=${roll} + ${attackBonus} = ${total} vs AC ${target.ac}${hitStr}`, 'attack');
    if ((total >= target.ac && !isFumble) || isCrit) {
      const dmgExpr = atk?.damage ?? '1d4';
      const dmgResult = rollDiceExpression(dmgExpr);
      const dmg = isCrit ? dmgResult.rolls.reduce((a, b) => a + b, 0) * 2 + dmgResult.modifier : dmgResult.total;
      addLog(`💥 Deals ${dmg} ${atk?.damageType ?? ''} damage`, 'damage');
      handleBulkDamage(targetId, dmg);
    }
  };

  const handleEnemyAttack = (enemyId: string, targetId: string) => {
    const enemy = enemies.find(e => e.id === enemyId);
    const target = combatants.find(c => c.id === targetId);
    if (!enemy || !target) return;
    const {roll, total, isCrit, isFumble} = rollAttack(enemy.attackBonus);
    const hitStr = isCrit ? ' 🌟 CRITICAL HIT!' : isFumble ? ' 💨 FUMBLE!' : total >= target.ac ? ' HIT!' : ' MISS';
    addLog(`👹 ${enemy.name} attacks ${target.name}: d20=${roll} + ${enemy.attackBonus} = ${total} vs AC ${target.ac}${hitStr}`, 'attack');
    if ((total >= target.ac && !isFumble) || isCrit) {
      const dmgResult = rollDiceExpression(enemy.damage);
      const dmg = isCrit ? dmgResult.rolls.reduce((a, b) => a + b, 0) * 2 + dmgResult.modifier : dmgResult.total;
      addLog(`💥 Deals ${dmg} damage`, 'damage');
      handleBulkDamage(targetId, dmg);
    }
  };

  const nextTurn = async () => {
    const liveCombatants = combatants.filter(c => c.hp > 0);
    if (liveCombatants.length === 0) return;
    let nextIdx = currentTurn + 1;
    let newRound = round;
    if (nextIdx >= combatants.length) {
      nextIdx = 0;
      newRound = round + 1;
      addLog(`\n⏱️ Round ${newRound} begins!`, 'info');
    }
    while (combatants[nextIdx]?.hp === 0 && nextIdx < combatants.length) {
      nextIdx++;
    }
    if (nextIdx >= combatants.length) {
      nextIdx = 0;
      newRound = round + 1;
    }
    setCurrentTurn(nextIdx);
    setRound(newRound);
    addLog(`→ ${combatants[nextIdx]?.name}'s turn`, 'info');
    await saveCombatState(combatants, enemies, newRound, nextIdx, true);
  };

  const endCombat = async () => {
    Alert.alert('End Combat', 'End this combat encounter?', [
      {text: 'Cancel', style: 'cancel'},
      {
        text: 'End Combat',
        onPress: async () => {
          setCombatStarted(false);
          setCombatants([]);
          setRound(1);
          setCurrentTurn(0);
          setLog([]);
          if (adventure) {
            const updated = {...adventure, combatState: undefined, updatedAt: new Date().toISOString()};
            setAdventure(updated);
            await saveAdventure(updated);
          }
          navigation.goBack();
        },
      },
    ]);
  };

  const current = combatants[currentTurn];
  const allEnemiesDead = combatants.filter(c => !c.isPlayer).every(c => c.hp === 0);
  const allPlayersDead = combatants.filter(c => c.isPlayer).every(c => c.hp === 0);

  const players = combatants.filter(c => c.isPlayer);
  const enemyCombatants = combatants.filter(c => !c.isPlayer);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <View style={styles.roundBadge}>
          <Text style={styles.roundLabel}>ROUND</Text>
          <Text style={styles.roundNum}>{round}</Text>
        </View>
        <TouchableOpacity style={styles.endBtn} onPress={endCombat}>
          <Text style={styles.endBtnText}>End Combat</Text>
        </TouchableOpacity>
      </View>

      {(allEnemiesDead || allPlayersDead) && combatStarted && (
        <View style={[styles.banner, allEnemiesDead ? styles.victoryBanner : styles.defeatBanner]}>
          <Text style={styles.bannerText}>
            {allEnemiesDead ? '🏆 VICTORY!' : '💀 DEFEAT...'}
          </Text>
        </View>
      )}

      {combatStarted && current && (
        <View style={styles.currentTurnBox}>
          <Text style={styles.currentTurnLabel}>Current Turn</Text>
          <Text style={styles.currentTurnName}>{current.name}</Text>
          {current.isPlayer ? (
            <View style={styles.actionRow}>
              {enemyCombatants.filter(e => e.hp > 0).map(e => (
                <TouchableOpacity
                  key={e.id}
                  style={styles.attackTargetBtn}
                  onPress={() => handlePlayerAttack(e.id)}>
                  <Text style={styles.attackTargetText}>⚔️ Attack {e.name}</Text>
                </TouchableOpacity>
              ))}
            </View>
          ) : (
            <View style={styles.actionRow}>
              {players.filter(p => p.hp > 0).map(p => (
                <TouchableOpacity
                  key={p.id}
                  style={styles.enemyAttackBtn}
                  onPress={() => handleEnemyAttack(current.id, p.id)}>
                  <Text style={styles.attackTargetText}>👹 Attack {p.name}</Text>
                </TouchableOpacity>
              ))}
            </View>
          )}
          <TouchableOpacity style={styles.nextTurnBtn} onPress={nextTurn}>
            <Text style={styles.nextTurnText}>Next Turn →</Text>
          </TouchableOpacity>
        </View>
      )}

      {!combatStarted && (
        <View style={styles.setupSection}>
          <Text style={styles.sectionTitle}>Add Enemies</Text>
          <TextInput
            style={styles.input}
            value={newEnemyName}
            onChangeText={setNewEnemyName}
            placeholder="Enemy name (e.g. Goblin)"
            placeholderTextColor="#444"
          />
          <View style={styles.enemyStatsRow}>
            <View style={styles.col}>
              <Text style={styles.inputLabel}>HP</Text>
              <TextInput
                style={styles.smallInput}
                value={newEnemyHp}
                onChangeText={setNewEnemyHp}
                keyboardType="numeric"
              />
            </View>
            <View style={styles.col}>
              <Text style={styles.inputLabel}>AC</Text>
              <TextInput
                style={styles.smallInput}
                value={newEnemyAc}
                onChangeText={setNewEnemyAc}
                keyboardType="numeric"
              />
            </View>
            <View style={styles.col}>
              <Text style={styles.inputLabel}>Atk+</Text>
              <TextInput
                style={styles.smallInput}
                value={newEnemyAtk}
                onChangeText={setNewEnemyAtk}
                keyboardType="numeric"
              />
            </View>
            <View style={styles.col}>
              <Text style={styles.inputLabel}>Dmg</Text>
              <TextInput
                style={styles.smallInput}
                value={newEnemyDmg}
                onChangeText={setNewEnemyDmg}
              />
            </View>
          </View>
          <TouchableOpacity style={styles.addEnemyBtn} onPress={addEnemy}>
            <Text style={styles.addEnemyText}>+ Add Enemy</Text>
          </TouchableOpacity>
          {enemies.length > 0 && (
            <View style={styles.enemyList}>
              {enemies.map(e => (
                <View key={e.id} style={styles.enemyChip}>
                  <Text style={styles.enemyChipText}>
                    👹 {e.name} (HP {e.hp}, AC {e.ac})
                  </Text>
                </View>
              ))}
            </View>
          )}
          {enemies.length > 0 && (
            <TouchableOpacity style={styles.startCombatBtn} onPress={startCombat}>
              <Text style={styles.startCombatText}>⚔️ Roll Initiative & Begin!</Text>
            </TouchableOpacity>
          )}
        </View>
      )}

      {combatStarted && (
        <>
          <Text style={styles.sectionTitle}>Initiative Order</Text>
          {combatants.map((c, i) => (
            <CombatantRow
              key={c.id}
              combatant={c}
              isCurrentTurn={i === currentTurn}
              onHpChange={handleHpChange}
            />
          ))}
        </>
      )}

      <Text style={styles.sectionTitle}>🎲 Dice Roller</Text>
      <DiceRoller onResult={(expr, result) => addLog(`🎲 ${result}`, 'info')} />

      {log.length > 0 && (
        <View style={styles.logSection}>
          <Text style={styles.sectionTitle}>Combat Log</Text>
          {log.slice(0, 20).map(entry => (
            <View key={entry.id} style={styles.logEntry}>
              <Text
                style={[
                  styles.logText,
                  entry.type === 'attack' && styles.logAttack,
                  entry.type === 'damage' && styles.logDamage,
                  entry.type === 'heal' && styles.logHeal,
                  entry.type === 'initiative' && styles.logInitiative,
                ]}>
                {entry.text}
              </Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0d0d1a',
  },
  content: {
    padding: 14,
    paddingBottom: 40,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  roundBadge: {
    alignItems: 'center',
    backgroundColor: '#16213e',
    borderRadius: 10,
    paddingHorizontal: 18,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: '#c9a84c',
  },
  roundLabel: {
    color: '#666',
    fontSize: 10,
    fontWeight: 'bold',
    letterSpacing: 2,
  },
  roundNum: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 28,
    lineHeight: 32,
  },
  endBtn: {
    backgroundColor: '#3d0000',
    borderRadius: 10,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderWidth: 1,
    borderColor: '#f44336',
  },
  endBtnText: {
    color: '#f44336',
    fontWeight: 'bold',
    fontSize: 14,
  },
  banner: {
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginBottom: 16,
  },
  victoryBanner: {
    backgroundColor: '#0a2a0a',
    borderWidth: 2,
    borderColor: '#4caf50',
  },
  defeatBanner: {
    backgroundColor: '#3d0000',
    borderWidth: 2,
    borderColor: '#f44336',
  },
  bannerText: {
    color: '#e8e8e8',
    fontWeight: 'bold',
    fontSize: 24,
  },
  currentTurnBox: {
    backgroundColor: '#1e2a4e',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    borderWidth: 2,
    borderColor: '#c9a84c',
  },
  currentTurnLabel: {
    color: '#c9a84c',
    fontSize: 12,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  currentTurnName: {
    color: '#e8e8e8',
    fontWeight: 'bold',
    fontSize: 20,
    marginBottom: 10,
  },
  actionRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 10,
  },
  attackTargetBtn: {
    backgroundColor: '#5c0000',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: '#f44336',
  },
  enemyAttackBtn: {
    backgroundColor: '#3d1a00',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: '#ff9800',
  },
  attackTargetText: {
    color: '#e8e8e8',
    fontWeight: 'bold',
    fontSize: 13,
  },
  nextTurnBtn: {
    backgroundColor: '#c9a84c',
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: 'center',
  },
  nextTurnText: {
    color: '#0d0d1a',
    fontWeight: 'bold',
    fontSize: 15,
  },
  setupSection: {
    marginBottom: 16,
  },
  sectionTitle: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 16,
    marginTop: 16,
    marginBottom: 8,
  },
  input: {
    backgroundColor: '#16213e',
    borderWidth: 1,
    borderColor: '#2d2d4e',
    borderRadius: 8,
    color: '#e8e8e8',
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 14,
    marginBottom: 8,
  },
  enemyStatsRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 8,
  },
  col: {flex: 1},
  inputLabel: {color: '#666', fontSize: 11, marginBottom: 3},
  smallInput: {
    backgroundColor: '#16213e',
    borderWidth: 1,
    borderColor: '#2d2d4e',
    borderRadius: 6,
    color: '#e8e8e8',
    paddingHorizontal: 8,
    paddingVertical: 8,
    fontSize: 14,
    textAlign: 'center',
  },
  addEnemyBtn: {
    borderWidth: 1,
    borderColor: '#f44336',
    borderStyle: 'dashed',
    borderRadius: 8,
    paddingVertical: 10,
    alignItems: 'center',
    marginBottom: 10,
  },
  addEnemyText: {
    color: '#f44336',
    fontWeight: 'bold',
  },
  enemyList: {
    gap: 6,
    marginBottom: 10,
  },
  enemyChip: {
    backgroundColor: '#16213e',
    borderRadius: 8,
    padding: 10,
    borderLeftWidth: 3,
    borderLeftColor: '#8b0000',
  },
  enemyChipText: {
    color: '#e8e8e8',
    fontSize: 13,
  },
  startCombatBtn: {
    backgroundColor: '#c9a84c',
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: 'center',
    shadowColor: '#c9a84c',
    shadowOffset: {width: 0, height: 4},
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 8,
  },
  startCombatText: {
    color: '#0d0d1a',
    fontWeight: 'bold',
    fontSize: 16,
  },
  logSection: {marginTop: 8},
  logEntry: {
    paddingVertical: 4,
    borderBottomWidth: 1,
    borderBottomColor: '#16213e',
  },
  logText: {
    color: '#a0a0b0',
    fontSize: 13,
  },
  logAttack: {color: '#e8e8e8'},
  logDamage: {color: '#f44336'},
  logHeal: {color: '#4caf50'},
  logInitiative: {color: '#c9a84c'},
});
