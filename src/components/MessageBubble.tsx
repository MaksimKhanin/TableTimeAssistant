import React from 'react';
import {View, Text, StyleSheet} from 'react-native';
import {Message} from '../types';

interface Props {
  message: Message;
  streaming?: boolean;
}

export default function MessageBubble({message, streaming}: Props) {
  if (message.role === 'system') {
    return (
      <View style={styles.systemContainer}>
        <Text style={styles.systemText}>{message.content}</Text>
      </View>
    );
  }

  if (message.role === 'dm') {
    return (
      <View style={styles.dmContainer}>
        <View style={styles.dmHeader}>
          <Text style={styles.dmLabel}>👑 Game Master</Text>
          {streaming && <Text style={styles.streamingDot}>●</Text>}
        </View>
        <Text style={styles.dmText}>{message.content}</Text>
      </View>
    );
  }

  return (
    <View style={styles.playerContainer}>
      <View style={styles.playerHeader}>
        <Text style={styles.playerName}>
          ⚔️ {message.playerName || 'Player'}
        </Text>
      </View>
      <Text style={styles.playerText}>{message.content}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  systemContainer: {
    alignSelf: 'center',
    marginVertical: 8,
    paddingHorizontal: 16,
    paddingVertical: 6,
    backgroundColor: '#16213e',
    borderRadius: 20,
  },
  systemText: {
    color: '#6666aa',
    fontSize: 12,
    fontStyle: 'italic',
    textAlign: 'center',
  },
  dmContainer: {
    alignSelf: 'flex-start',
    maxWidth: '90%',
    marginVertical: 8,
    marginLeft: 4,
    backgroundColor: '#16213e',
    borderRadius: 12,
    borderLeftWidth: 3,
    borderLeftColor: '#c9a84c',
    padding: 12,
  },
  dmHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
    gap: 8,
  },
  dmLabel: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 13,
  },
  streamingDot: {
    color: '#c9a84c',
    fontSize: 10,
  },
  dmText: {
    color: '#e8e8e8',
    fontSize: 15,
    lineHeight: 22,
    fontStyle: 'italic',
  },
  playerContainer: {
    alignSelf: 'flex-end',
    maxWidth: '85%',
    marginVertical: 6,
    marginRight: 4,
    backgroundColor: '#1e3a5f',
    borderRadius: 12,
    borderRightWidth: 3,
    borderRightColor: '#4a9eff',
    padding: 12,
  },
  playerHeader: {
    marginBottom: 4,
  },
  playerName: {
    color: '#4a9eff',
    fontWeight: 'bold',
    fontSize: 12,
  },
  playerText: {
    color: '#e8e8e8',
    fontSize: 15,
    lineHeight: 22,
  },
});
