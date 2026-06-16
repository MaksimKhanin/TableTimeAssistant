import React, {useState} from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  TextInput,
  StyleSheet,
  Animated,
} from 'react-native';
import {rollDiceExpression, formatDiceResult} from '../utils/dice';

const DICE_TYPES = [4, 6, 8, 10, 12, 20];

interface Props {
  onResult?: (expr: string, result: string) => void;
}

export default function DiceRoller({onResult}: Props) {
  const [modifier, setModifier] = useState('0');
  const [lastResult, setLastResult] = useState<string | null>(null);
  const [shakeAnim] = useState(new Animated.Value(0));

  const shake = () => {
    Animated.sequence([
      Animated.timing(shakeAnim, {toValue: 8, duration: 60, useNativeDriver: true}),
      Animated.timing(shakeAnim, {toValue: -8, duration: 60, useNativeDriver: true}),
      Animated.timing(shakeAnim, {toValue: 6, duration: 60, useNativeDriver: true}),
      Animated.timing(shakeAnim, {toValue: 0, duration: 60, useNativeDriver: true}),
    ]).start();
  };

  const roll = (sides: number) => {
    const mod = parseInt(modifier, 10) || 0;
    const expr = mod !== 0 ? `1d${sides}${mod >= 0 ? '+' : ''}${mod}` : `1d${sides}`;
    const result = rollDiceExpression(expr);
    const formatted = formatDiceResult(expr, result);
    setLastResult(formatted);
    shake();
    onResult?.(expr, formatted);
  };

  return (
    <View style={styles.container}>
      <View style={styles.diceRow}>
        {DICE_TYPES.map(sides => (
          <TouchableOpacity
            key={sides}
            style={styles.diceButton}
            onPress={() => roll(sides)}
            activeOpacity={0.7}>
            <Text style={styles.diceText}>d{sides}</Text>
          </TouchableOpacity>
        ))}
      </View>
      <View style={styles.modRow}>
        <Text style={styles.modLabel}>Modifier:</Text>
        <TextInput
          style={styles.modInput}
          value={modifier}
          onChangeText={setModifier}
          keyboardType="numeric"
          placeholderTextColor="#666"
        />
      </View>
      {lastResult && (
        <Animated.View
          style={[styles.resultBox, {transform: [{translateX: shakeAnim}]}]}>
          <Text style={styles.resultText}>{lastResult}</Text>
        </Animated.View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: '#2d2d4e',
  },
  diceRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 8,
  },
  diceButton: {
    backgroundColor: '#0f3460',
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 14,
    borderWidth: 1,
    borderColor: '#c9a84c',
    minWidth: 48,
    alignItems: 'center',
  },
  diceText: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 16,
  },
  modRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
    gap: 8,
  },
  modLabel: {
    color: '#a0a0b0',
    fontSize: 13,
  },
  modInput: {
    backgroundColor: '#0d0d1a',
    color: '#e8e8e8',
    borderWidth: 1,
    borderColor: '#2d2d4e',
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 4,
    width: 70,
    fontSize: 14,
  },
  resultBox: {
    marginTop: 10,
    backgroundColor: '#0d0d1a',
    borderRadius: 8,
    padding: 10,
    borderLeftWidth: 3,
    borderLeftColor: '#c9a84c',
  },
  resultText: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 14,
  },
});
