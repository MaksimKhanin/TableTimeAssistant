import React, {useState} from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Alert,
} from 'react-native';
import {useNavigation} from '@react-navigation/native';
import {NativeStackNavigationProp} from '@react-navigation/native-stack';
import {v4 as uuidv4} from 'uuid';
import {Character, CharacterStats, Attack, Adventure, RootStackParamList} from '../types';
import {getModifier} from '../utils/dice';
import {saveAdventure} from '../services/storageService';

type Nav = NativeStackNavigationProp<RootStackParamList, 'AdventureSetup'>;

const STAT_KEYS: (keyof CharacterStats)[] = ['STR', 'DEX', 'CON', 'INT', 'WIS', 'CHA'];

function makeCharacter(): Character {
  return {
    id: uuidv4(),
    name: '',
    race: '',
    class: '',
    level: 1,
    hp: 10,
    maxHp: 10,
    ac: 10,
    stats: {STR: 10, DEX: 10, CON: 10, INT: 10, WIS: 10, CHA: 10},
    abilities: [''],
    attacks: [{name: 'Unarmed Strike', attackBonus: 0, damage: '1d4', damageType: 'bludgeoning'}],
  };
}

function StatInput({label, value, onChange}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  const mod = getModifier(value);
  const modStr = mod >= 0 ? `+${mod}` : `${mod}`;
  return (
    <View style={statStyles.box}>
      <Text style={statStyles.label}>{label}</Text>
      <TouchableOpacity onPress={() => onChange(Math.min(20, value + 1))} style={statStyles.btn}>
        <Text style={statStyles.btnText}>▲</Text>
      </TouchableOpacity>
      <Text style={statStyles.val}>{value}</Text>
      <TouchableOpacity onPress={() => onChange(Math.max(3, value - 1))} style={statStyles.btn}>
        <Text style={statStyles.btnText}>▼</Text>
      </TouchableOpacity>
      <Text style={statStyles.mod}>{modStr}</Text>
    </View>
  );
}

const statStyles = StyleSheet.create({
  box: {
    alignItems: 'center',
    flex: 1,
    marginHorizontal: 2,
    backgroundColor: '#0d0d1a',
    borderRadius: 8,
    paddingVertical: 6,
  },
  label: {color: '#666', fontSize: 10, fontWeight: 'bold'},
  btn: {paddingVertical: 2},
  btnText: {color: '#c9a84c', fontSize: 12},
  val: {color: '#e8e8e8', fontSize: 18, fontWeight: 'bold', lineHeight: 22},
  mod: {color: '#c9a84c', fontSize: 11},
});

interface CharFormProps {
  char: Character;
  index: number;
  onChange: (updated: Character) => void;
}

function CharacterForm({char, index, onChange}: CharFormProps) {
  const updateField = <K extends keyof Character>(key: K, val: Character[K]) =>
    onChange({...char, [key]: val});
  const updateStat = (key: keyof CharacterStats, val: number) =>
    onChange({...char, stats: {...char.stats, [key]: val}});
  const updateAbility = (i: number, val: string) => {
    const abilities = [...char.abilities];
    abilities[i] = val;
    onChange({...char, abilities});
  };
  const addAbility = () => onChange({...char, abilities: [...char.abilities, '']});
  const removeAbility = (i: number) =>
    onChange({...char, abilities: char.abilities.filter((_, idx) => idx !== i)});
  const updateAttack = (i: number, field: keyof Attack, val: string | number) => {
    const attacks = char.attacks.map((a, idx) =>
      idx === i ? {...a, [field]: val} : a,
    );
    onChange({...char, attacks});
  };
  const addAttack = () =>
    onChange({
      ...char,
      attacks: [
        ...char.attacks,
        {name: '', attackBonus: 0, damage: '1d6', damageType: 'slashing'},
      ],
    });
  const removeAttack = (i: number) =>
    onChange({...char, attacks: char.attacks.filter((_, idx) => idx !== i)});

  return (
    <View style={cfStyles.container}>
      <Text style={cfStyles.title}>Player {index + 1}</Text>
      <View style={cfStyles.row}>
        <View style={cfStyles.col}>
          <Text style={cfStyles.label}>Name *</Text>
          <TextInput
            style={cfStyles.input}
            value={char.name}
            onChangeText={v => updateField('name', v)}
            placeholder="Character name"
            placeholderTextColor="#444"
          />
        </View>
        <View style={cfStyles.col}>
          <Text style={cfStyles.label}>Level</Text>
          <View style={cfStyles.row}>
            <TouchableOpacity
              onPress={() => updateField('level', Math.max(1, char.level - 1))}
              style={cfStyles.stepBtn}>
              <Text style={cfStyles.stepBtnText}>−</Text>
            </TouchableOpacity>
            <Text style={cfStyles.stepVal}>{char.level}</Text>
            <TouchableOpacity
              onPress={() => updateField('level', Math.min(20, char.level + 1))}
              style={cfStyles.stepBtn}>
              <Text style={cfStyles.stepBtnText}>+</Text>
            </TouchableOpacity>
          </View>
        </View>
      </View>
      <View style={cfStyles.row}>
        <View style={cfStyles.col}>
          <Text style={cfStyles.label}>Race</Text>
          <TextInput
            style={cfStyles.input}
            value={char.race}
            onChangeText={v => updateField('race', v)}
            placeholder="Human, Elf..."
            placeholderTextColor="#444"
          />
        </View>
        <View style={cfStyles.col}>
          <Text style={cfStyles.label}>Class</Text>
          <TextInput
            style={cfStyles.input}
            value={char.class}
            onChangeText={v => updateField('class', v)}
            placeholder="Fighter, Wizard..."
            placeholderTextColor="#444"
          />
        </View>
      </View>
      <View style={cfStyles.row}>
        <View style={cfStyles.col}>
          <Text style={cfStyles.label}>Max HP</Text>
          <TextInput
            style={cfStyles.input}
            value={String(char.maxHp)}
            onChangeText={v => {
              const n = parseInt(v, 10);
              if (!isNaN(n) && n > 0) {
                onChange({...char, maxHp: n, hp: n});
              }
            }}
            keyboardType="numeric"
            placeholderTextColor="#444"
          />
        </View>
        <View style={cfStyles.col}>
          <Text style={cfStyles.label}>AC</Text>
          <TextInput
            style={cfStyles.input}
            value={String(char.ac)}
            onChangeText={v => {
              const n = parseInt(v, 10);
              if (!isNaN(n)) updateField('ac', n);
            }}
            keyboardType="numeric"
            placeholderTextColor="#444"
          />
        </View>
      </View>
      <Text style={cfStyles.sectionLabel}>Ability Scores</Text>
      <View style={cfStyles.statsRow}>
        {STAT_KEYS.map(key => (
          <StatInput
            key={key}
            label={key}
            value={char.stats[key]}
            onChange={v => updateStat(key, v)}
          />
        ))}
      </View>
      <Text style={cfStyles.sectionLabel}>Special Abilities</Text>
      {char.abilities.map((ability, i) => (
        <View key={i} style={cfStyles.abilityRow}>
          <TextInput
            style={[cfStyles.input, {flex: 1}]}
            value={ability}
            onChangeText={v => updateAbility(i, v)}
            placeholder="e.g. Second Wind, Sneak Attack..."
            placeholderTextColor="#444"
          />
          <TouchableOpacity onPress={() => removeAbility(i)} style={cfStyles.removeBtn}>
            <Text style={cfStyles.removeBtnText}>✕</Text>
          </TouchableOpacity>
        </View>
      ))}
      <TouchableOpacity onPress={addAbility} style={cfStyles.addBtn}>
        <Text style={cfStyles.addBtnText}>+ Add Ability</Text>
      </TouchableOpacity>
      <Text style={cfStyles.sectionLabel}>Attacks</Text>
      {char.attacks.map((atk, i) => (
        <View key={i} style={cfStyles.attackBlock}>
          <View style={cfStyles.row}>
            <View style={cfStyles.col}>
              <Text style={cfStyles.label}>Attack Name</Text>
              <TextInput
                style={cfStyles.input}
                value={atk.name}
                onChangeText={v => updateAttack(i, 'name', v)}
                placeholder="Longsword..."
                placeholderTextColor="#444"
              />
            </View>
            <TouchableOpacity onPress={() => removeAttack(i)} style={cfStyles.removeBtn}>
              <Text style={cfStyles.removeBtnText}>✕</Text>
            </TouchableOpacity>
          </View>
          <View style={cfStyles.row}>
            <View style={cfStyles.col}>
              <Text style={cfStyles.label}>To Hit Bonus</Text>
              <TextInput
                style={cfStyles.input}
                value={String(atk.attackBonus)}
                onChangeText={v => updateAttack(i, 'attackBonus', parseInt(v, 10) || 0)}
                keyboardType="numeric"
                placeholderTextColor="#444"
              />
            </View>
            <View style={cfStyles.col}>
              <Text style={cfStyles.label}>Damage Dice</Text>
              <TextInput
                style={cfStyles.input}
                value={atk.damage}
                onChangeText={v => updateAttack(i, 'damage', v)}
                placeholder="1d6+3"
                placeholderTextColor="#444"
              />
            </View>
            <View style={cfStyles.col}>
              <Text style={cfStyles.label}>Type</Text>
              <TextInput
                style={cfStyles.input}
                value={atk.damageType}
                onChangeText={v => updateAttack(i, 'damageType', v)}
                placeholder="slashing"
                placeholderTextColor="#444"
              />
            </View>
          </View>
        </View>
      ))}
      <TouchableOpacity onPress={addAttack} style={cfStyles.addBtn}>
        <Text style={cfStyles.addBtnText}>+ Add Attack</Text>
      </TouchableOpacity>
    </View>
  );
}

const cfStyles = StyleSheet.create({
  container: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#2d2d4e',
  },
  title: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 16,
    marginBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#2d2d4e',
    paddingBottom: 8,
  },
  row: {flexDirection: 'row', gap: 8, marginBottom: 8, alignItems: 'center'},
  col: {flex: 1},
  label: {color: '#888', fontSize: 11, marginBottom: 3},
  input: {
    backgroundColor: '#0d0d1a',
    borderWidth: 1,
    borderColor: '#2d2d4e',
    borderRadius: 8,
    color: '#e8e8e8',
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 14,
  },
  stepBtn: {
    backgroundColor: '#0f3460',
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderWidth: 1,
    borderColor: '#c9a84c',
  },
  stepBtnText: {color: '#c9a84c', fontWeight: 'bold', fontSize: 16},
  stepVal: {color: '#e8e8e8', fontWeight: 'bold', fontSize: 18, paddingHorizontal: 12},
  sectionLabel: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 13,
    marginTop: 10,
    marginBottom: 6,
  },
  statsRow: {flexDirection: 'row', marginBottom: 4},
  abilityRow: {flexDirection: 'row', gap: 8, marginBottom: 6, alignItems: 'center'},
  removeBtn: {
    backgroundColor: '#3d0000',
    borderRadius: 6,
    width: 32,
    height: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  removeBtnText: {color: '#f44336', fontWeight: 'bold'},
  addBtn: {
    borderWidth: 1,
    borderColor: '#2d2d4e',
    borderStyle: 'dashed',
    borderRadius: 8,
    paddingVertical: 8,
    alignItems: 'center',
    marginTop: 4,
  },
  addBtnText: {color: '#666', fontSize: 13},
  attackBlock: {
    backgroundColor: '#0d0d1a',
    borderRadius: 8,
    padding: 10,
    marginBottom: 8,
  },
});

export default function AdventureSetupScreen() {
  const navigation = useNavigation<Nav>();
  const [adventureName, setAdventureName] = useState('');
  const [description, setDescription] = useState('');
  const [playerCount, setPlayerCount] = useState(2);
  const [characters, setCharacters] = useState<Character[]>([makeCharacter(), makeCharacter()]);

  const handlePlayerCountChange = (count: number) => {
    setPlayerCount(count);
    setCharacters(prev => {
      const next = [...prev];
      while (next.length < count) next.push(makeCharacter());
      return next.slice(0, count);
    });
  };

  const handleStartAdventure = async () => {
    if (!adventureName.trim()) {
      Alert.alert('Missing Info', 'Please enter an adventure name.');
      return;
    }
    if (!description.trim()) {
      Alert.alert('Missing Info', 'Please enter an adventure description.');
      return;
    }
    const emptyName = characters.slice(0, playerCount).find(c => !c.name.trim());
    if (emptyName) {
      Alert.alert('Missing Info', 'All characters need a name.');
      return;
    }
    const now = new Date().toISOString();
    const adventure: Adventure = {
      id: uuidv4(),
      name: adventureName.trim(),
      description: description.trim(),
      characters: characters.slice(0, playerCount),
      messages: [],
      createdAt: now,
      updatedAt: now,
    };
    await saveAdventure(adventure);
    navigation.replace('Game', {adventureId: adventure.id});
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.sectionTitle}>Adventure Setup</Text>
      <Text style={styles.label}>Adventure Name *</Text>
      <TextInput
        style={styles.input}
        value={adventureName}
        onChangeText={setAdventureName}
        placeholder="The Dark Caverns of Doom..."
        placeholderTextColor="#444"
      />
      <Text style={styles.label}>Adventure Description *</Text>
      <TextInput
        style={[styles.input, styles.textArea]}
        value={description}
        onChangeText={setDescription}
        placeholder="Describe the setting, tone, and starting situation. The more detail you give, the better the AI Game Master will perform..."
        placeholderTextColor="#444"
        multiline
        numberOfLines={6}
        textAlignVertical="top"
      />
      <Text style={styles.sectionTitle}>Players</Text>
      <View style={styles.playerCountRow}>
        {[1, 2, 3, 4].map(n => (
          <TouchableOpacity
            key={n}
            style={[
              styles.countBtn,
              playerCount === n && styles.countBtnActive,
            ]}
            onPress={() => handlePlayerCountChange(n)}>
            <Text
              style={[
                styles.countBtnText,
                playerCount === n && styles.countBtnTextActive,
              ]}>
              {n}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      {characters.slice(0, playerCount).map((char, i) => (
        <CharacterForm
          key={char.id}
          char={char}
          index={i}
          onChange={updated =>
            setCharacters(prev =>
              prev.map((c, idx) => (idx === i ? updated : c)),
            )
          }
        />
      ))}
      <TouchableOpacity
        style={styles.startBtn}
        onPress={handleStartAdventure}
        activeOpacity={0.8}>
        <Text style={styles.startBtnText}>⚔️ Begin Adventure</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0d0d1a',
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  sectionTitle: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 20,
    marginTop: 8,
    marginBottom: 12,
  },
  label: {
    color: '#a0a0b0',
    fontSize: 13,
    marginBottom: 4,
  },
  input: {
    backgroundColor: '#16213e',
    borderWidth: 1,
    borderColor: '#2d2d4e',
    borderRadius: 10,
    color: '#e8e8e8',
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 15,
    marginBottom: 14,
  },
  textArea: {
    height: 120,
    textAlignVertical: 'top',
  },
  playerCountRow: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 20,
  },
  countBtn: {
    width: 52,
    height: 52,
    borderRadius: 26,
    borderWidth: 2,
    borderColor: '#2d2d4e',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#16213e',
  },
  countBtnActive: {
    borderColor: '#c9a84c',
    backgroundColor: '#2d2000',
  },
  countBtnText: {
    color: '#666',
    fontWeight: 'bold',
    fontSize: 20,
  },
  countBtnTextActive: {
    color: '#c9a84c',
  },
  startBtn: {
    backgroundColor: '#c9a84c',
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: 'center',
    marginTop: 8,
    shadowColor: '#c9a84c',
    shadowOffset: {width: 0, height: 4},
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 8,
  },
  startBtnText: {
    color: '#0d0d1a',
    fontWeight: 'bold',
    fontSize: 18,
  },
});
