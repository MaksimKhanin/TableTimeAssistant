import React, {useCallback, useEffect, useState} from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  Alert,
  StatusBar,
} from 'react-native';
import {useFocusEffect, useNavigation} from '@react-navigation/native';
import {NativeStackNavigationProp} from '@react-navigation/native-stack';
import {Adventure, RootStackParamList} from '../types';
import {getAllAdventures, deleteAdventure} from '../services/storageService';
import {llmService} from '../services/llmService';

type Nav = NativeStackNavigationProp<RootStackParamList, 'Home'>;

export default function HomeScreen() {
  const navigation = useNavigation<Nav>();
  const [adventures, setAdventures] = useState<Adventure[]>([]);
  const [modelName, setModelName] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      getAllAdventures().then(setAdventures);
      setModelName(llmService.getModelName());
    }, []),
  );

  const handleDelete = (adventure: Adventure) => {
    Alert.alert(
      'Delete Adventure',
      `Delete "${adventure.name}"? This cannot be undone.`,
      [
        {text: 'Cancel', style: 'cancel'},
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            await deleteAdventure(adventure.id);
            setAdventures(prev => prev.filter(a => a.id !== adventure.id));
          },
        },
      ],
    );
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {month: 'short', day: 'numeric', year: 'numeric'});
  };

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor="#0d0d1a" />
      <View style={styles.hero}>
        <Text style={styles.title}>⚔️ Table Time</Text>
        <Text style={styles.subtitle}>AI Game Master</Text>
        <TouchableOpacity
          style={[
            styles.modelChip,
            modelName ? styles.modelLoaded : styles.modelMissing,
          ]}
          onPress={() => navigation.navigate('ModelSetup')}>
          <Text style={styles.modelChipText}>
            {modelName ? `🤖 ${modelName}` : '⚠️ No AI Model — Tap to Load'}
          </Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={adventures}
        keyExtractor={item => item.id}
        contentContainerStyle={styles.list}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyIcon}>🗺️</Text>
            <Text style={styles.emptyText}>No adventures yet</Text>
            <Text style={styles.emptyHint}>
              Start a new quest to begin your journey
            </Text>
          </View>
        }
        renderItem={({item}) => (
          <TouchableOpacity
            style={styles.card}
            onPress={() => navigation.navigate('Game', {adventureId: item.id})}
            onLongPress={() => handleDelete(item)}
            activeOpacity={0.8}>
            <View style={styles.cardHeader}>
              <Text style={styles.cardTitle}>{item.name}</Text>
              <Text style={styles.cardDate}>{formatDate(item.updatedAt)}</Text>
            </View>
            <Text style={styles.cardSub} numberOfLines={2}>
              {item.description}
            </Text>
            <View style={styles.cardFooter}>
              <Text style={styles.cardMeta}>
                👥 {item.characters.length} player{item.characters.length !== 1 ? 's' : ''}
              </Text>
              <Text style={styles.cardMeta}>
                💬 {item.messages.length} messages
              </Text>
              {item.combatState?.active && (
                <Text style={styles.combatBadge}>⚔️ IN COMBAT</Text>
              )}
            </View>
          </TouchableOpacity>
        )}
      />

      <TouchableOpacity
        style={styles.newBtn}
        onPress={() => navigation.navigate('AdventureSetup', {})}
        activeOpacity={0.8}>
        <Text style={styles.newBtnText}>+ New Adventure</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0d0d1a',
  },
  hero: {
    alignItems: 'center',
    paddingTop: 60,
    paddingBottom: 20,
    paddingHorizontal: 20,
    borderBottomWidth: 1,
    borderBottomColor: '#1a1a2e',
  },
  title: {
    color: '#c9a84c',
    fontSize: 34,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  subtitle: {
    color: '#6666aa',
    fontSize: 14,
    letterSpacing: 3,
    marginTop: 2,
    textTransform: 'uppercase',
  },
  modelChip: {
    marginTop: 14,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    borderWidth: 1,
  },
  modelLoaded: {
    backgroundColor: '#0a2a0a',
    borderColor: '#4caf50',
  },
  modelMissing: {
    backgroundColor: '#2a1a00',
    borderColor: '#ff9800',
  },
  modelChipText: {
    color: '#e8e8e8',
    fontSize: 13,
  },
  list: {
    padding: 16,
    paddingBottom: 100,
  },
  empty: {
    alignItems: 'center',
    paddingTop: 60,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: 12,
  },
  emptyText: {
    color: '#6666aa',
    fontSize: 18,
    fontWeight: 'bold',
  },
  emptyHint: {
    color: '#444466',
    fontSize: 13,
    marginTop: 6,
    textAlign: 'center',
  },
  card: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 14,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#2d2d4e',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  cardTitle: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 17,
    flex: 1,
  },
  cardDate: {
    color: '#555577',
    fontSize: 12,
  },
  cardSub: {
    color: '#a0a0b0',
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 8,
  },
  cardFooter: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'center',
  },
  cardMeta: {
    color: '#555577',
    fontSize: 12,
  },
  combatBadge: {
    color: '#f44336',
    fontSize: 11,
    fontWeight: 'bold',
    backgroundColor: '#3d0000',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  newBtn: {
    position: 'absolute',
    bottom: 24,
    left: 24,
    right: 24,
    backgroundColor: '#c9a84c',
    borderRadius: 14,
    paddingVertical: 16,
    alignItems: 'center',
    shadowColor: '#c9a84c',
    shadowOffset: {width: 0, height: 4},
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 8,
  },
  newBtnText: {
    color: '#0d0d1a',
    fontWeight: 'bold',
    fontSize: 17,
  },
});
