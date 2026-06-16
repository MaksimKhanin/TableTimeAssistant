import React, {useCallback, useEffect, useRef, useState} from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import {useFocusEffect, useNavigation, useRoute, RouteProp} from '@react-navigation/native';
import {NativeStackNavigationProp} from '@react-navigation/native-stack';
import {v4 as uuidv4} from 'uuid';
import {Adventure, Message, RootStackParamList} from '../types';
import {getAdventure, saveAdventure} from '../services/storageService';
import {llmService} from '../services/llmService';
import {buildSystemPrompt} from '../utils/systemPrompt';
import MessageBubble from '../components/MessageBubble';
import DiceRoller from '../components/DiceRoller';

type Nav = NativeStackNavigationProp<RootStackParamList, 'Game'>;
type Route = RouteProp<RootStackParamList, 'Game'>;

export default function GameScreen() {
  const navigation = useNavigation<Nav>();
  const route = useRoute<Route>();
  const {adventureId} = route.params;

  const [adventure, setAdventure] = useState<Adventure | null>(null);
  const [input, setInput] = useState('');
  const [selectedPlayer, setSelectedPlayer] = useState(0);
  const [generating, setGenerating] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [showDice, setShowDice] = useState(false);
  const listRef = useRef<FlatList>(null);
  const adventureRef = useRef<Adventure | null>(null);

  useFocusEffect(
    useCallback(() => {
      getAdventure(adventureId).then(async adv => {
        if (!adv) return;
        setAdventure(adv);
        adventureRef.current = adv;
        if (adv.messages.length === 0) {
          setTimeout(() => triggerOpeningScene(adv), 500);
        }
      });
    }, [adventureId]),
  );

  useEffect(() => {
    navigation.setOptions({
      title: adventure?.name ?? 'Adventure',
      headerRight: () => (
        <View style={{flexDirection: 'row', gap: 14, marginRight: 4}}>
          <TouchableOpacity onPress={() => setShowDice(p => !p)}>
            <Text style={{color: '#c9a84c', fontSize: 20}}>🎲</Text>
          </TouchableOpacity>
          <TouchableOpacity
            onPress={() => navigation.navigate('Combat', {adventureId})}>
            <Text style={{color: '#f44336', fontSize: 20}}>⚔️</Text>
          </TouchableOpacity>
        </View>
      ),
    });
  }, [adventure, navigation, adventureId]);

  const addMessage = async (msg: Message) => {
    const adv = adventureRef.current;
    if (!adv) return;
    const updated: Adventure = {
      ...adv,
      messages: [...adv.messages, msg],
      updatedAt: new Date().toISOString(),
    };
    adventureRef.current = updated;
    setAdventure(updated);
    await saveAdventure(updated);
  };

  const buildChatHistory = (adv: Adventure) => {
    const system = buildSystemPrompt(adv);
    const msgs: {role: string; content: string}[] = [
      {role: 'system', content: system},
    ];
    for (const m of adv.messages) {
      if (m.role === 'system') continue;
      msgs.push({
        role: m.role === 'dm' ? 'assistant' : 'user',
        content:
          m.role === 'player'
            ? `${m.playerName}: ${m.content}`
            : m.content,
      });
    }
    return msgs;
  };

  const triggerOpeningScene = async (adv: Adventure) => {
    if (!llmService.isModelLoaded()) return;
    const systemMsg: Message = {
      id: uuidv4(),
      role: 'system',
      content: '— Adventure begins —',
      timestamp: new Date().toISOString(),
    };
    const advWithSystem: Adventure = {
      ...adv,
      messages: [systemMsg],
      updatedAt: new Date().toISOString(),
    };
    adventureRef.current = advWithSystem;
    setAdventure(advWithSystem);
    await saveAdventure(advWithSystem);
    await generateDMResponse(advWithSystem);
  };

  const generateDMResponse = async (adv: Adventure) => {
    if (!llmService.isModelLoaded()) {
      Alert.alert(
        'No Model',
        'Please load an AI model first.',
        [
          {text: 'Cancel', style: 'cancel'},
          {text: 'Load Model', onPress: () => navigation.navigate('ModelSetup')},
        ],
      );
      return;
    }
    setGenerating(true);
    setStreamingText('');
    let fullText = '';
    try {
      const history = buildChatHistory(adv);
      await llmService.generateResponse(history, token => {
        fullText += token;
        setStreamingText(fullText);
      });
      const dmMsg: Message = {
        id: uuidv4(),
        role: 'dm',
        content: fullText.trim(),
        timestamp: new Date().toISOString(),
      };
      await addMessage(dmMsg);
    } catch (e: any) {
      Alert.alert('Error', e?.message || 'Failed to generate response');
    } finally {
      setGenerating(false);
      setStreamingText('');
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || generating) return;
    const adv = adventureRef.current;
    if (!adv) return;
    setInput('');
    const player = adv.characters[selectedPlayer];
    const playerMsg: Message = {
      id: uuidv4(),
      role: 'player',
      content: text,
      timestamp: new Date().toISOString(),
      playerName: player?.name || `Player ${selectedPlayer + 1}`,
    };
    await addMessage(playerMsg);
    await generateDMResponse(adventureRef.current!);
  };

  const handleDiceResult = async (expr: string, result: string) => {
    const adv = adventureRef.current;
    if (!adv) return;
    const player = adv.characters[selectedPlayer];
    const msg: Message = {
      id: uuidv4(),
      role: 'system',
      content: `🎲 ${player?.name || 'Player'} rolls ${result}`,
      timestamp: new Date().toISOString(),
    };
    await addMessage(msg);
  };

  const messages = adventure?.messages ?? [];
  const streamingMsg: Message | null = generating && streamingText
    ? {id: 'streaming', role: 'dm', content: streamingText, timestamp: ''}
    : null;
  const displayMessages = streamingMsg
    ? [...messages, streamingMsg]
    : messages;

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={80}>
      {showDice && (
        <View style={styles.dicePanel}>
          <DiceRoller onResult={handleDiceResult} />
        </View>
      )}

      {!llmService.isModelLoaded() && (
        <TouchableOpacity
          style={styles.noModelBanner}
          onPress={() => navigation.navigate('ModelSetup')}>
          <Text style={styles.noModelText}>
            ⚠️ AI model not loaded — tap to load
          </Text>
        </TouchableOpacity>
      )}

      <FlatList
        ref={listRef}
        data={displayMessages}
        keyExtractor={item => item.id}
        contentContainerStyle={styles.messageList}
        onContentSizeChange={() => listRef.current?.scrollToEnd({animated: true})}
        renderItem={({item}) => (
          <MessageBubble
            message={item}
            streaming={item.id === 'streaming'}
          />
        )}
        ListEmptyComponent={
          !generating ? (
            <View style={styles.emptyChat}>
              <Text style={styles.emptyChatIcon}>🗺️</Text>
              <Text style={styles.emptyChatText}>Loading adventure...</Text>
            </View>
          ) : null
        }
      />

      {generating && !streamingText && (
        <View style={styles.thinkingRow}>
          <ActivityIndicator color="#c9a84c" size="small" />
          <Text style={styles.thinkingText}>Game Master is thinking...</Text>
        </View>
      )}

      <View style={styles.inputArea}>
        {adventure && adventure.characters.length > 1 && (
          <View style={styles.playerPicker}>
            {adventure.characters.map((char, i) => (
              <TouchableOpacity
                key={char.id}
                style={[
                  styles.playerTab,
                  selectedPlayer === i && styles.playerTabActive,
                ]}
                onPress={() => setSelectedPlayer(i)}>
                <Text
                  style={[
                    styles.playerTabText,
                    selectedPlayer === i && styles.playerTabTextActive,
                  ]}
                  numberOfLines={1}>
                  {char.name || `P${i + 1}`}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        )}
        <View style={styles.inputRow}>
          <TextInput
            style={styles.textInput}
            value={input}
            onChangeText={setInput}
            placeholder="What do you do?"
            placeholderTextColor="#444"
            multiline
            editable={!generating}
            returnKeyType="send"
            onSubmitEditing={handleSend}
          />
          <TouchableOpacity
            style={[styles.sendBtn, (!input.trim() || generating) && styles.sendBtnDisabled]}
            onPress={handleSend}
            disabled={!input.trim() || generating}>
            <Text style={styles.sendBtnText}>▶</Text>
          </TouchableOpacity>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0d0d1a',
  },
  dicePanel: {
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#1a1a2e',
  },
  noModelBanner: {
    backgroundColor: '#2a1a00',
    padding: 10,
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#c9a84c',
  },
  noModelText: {
    color: '#ff9800',
    fontSize: 13,
    fontWeight: 'bold',
  },
  messageList: {
    padding: 12,
    paddingBottom: 8,
  },
  emptyChat: {
    alignItems: 'center',
    paddingTop: 80,
  },
  emptyChatIcon: {fontSize: 48, marginBottom: 12},
  emptyChatText: {color: '#444466', fontSize: 15},
  thinkingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    padding: 10,
    paddingLeft: 16,
  },
  thinkingText: {
    color: '#666',
    fontStyle: 'italic',
    fontSize: 13,
  },
  inputArea: {
    borderTopWidth: 1,
    borderTopColor: '#1a1a2e',
    backgroundColor: '#0d0d1a',
    padding: 10,
  },
  playerPicker: {
    flexDirection: 'row',
    gap: 6,
    marginBottom: 8,
  },
  playerTab: {
    flex: 1,
    paddingVertical: 6,
    alignItems: 'center',
    borderRadius: 8,
    backgroundColor: '#16213e',
    borderWidth: 1,
    borderColor: '#2d2d4e',
  },
  playerTabActive: {
    backgroundColor: '#0f3460',
    borderColor: '#4a9eff',
  },
  playerTabText: {
    color: '#666',
    fontSize: 12,
    fontWeight: 'bold',
  },
  playerTabTextActive: {
    color: '#4a9eff',
  },
  inputRow: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'flex-end',
  },
  textInput: {
    flex: 1,
    backgroundColor: '#16213e',
    borderWidth: 1,
    borderColor: '#2d2d4e',
    borderRadius: 10,
    color: '#e8e8e8',
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 15,
    maxHeight: 100,
  },
  sendBtn: {
    backgroundColor: '#c9a84c',
    borderRadius: 10,
    width: 46,
    height: 46,
    alignItems: 'center',
    justifyContent: 'center',
  },
  sendBtnDisabled: {
    backgroundColor: '#3d3000',
  },
  sendBtnText: {
    color: '#0d0d1a',
    fontWeight: 'bold',
    fontSize: 18,
  },
});
