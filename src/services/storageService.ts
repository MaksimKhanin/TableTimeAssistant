import AsyncStorage from '@react-native-async-storage/async-storage';
import {Adventure} from '../types';

const KEYS = {
  adventures: 'adventures_index',
  adventure: (id: string) => `adventure_${id}`,
  modelPath: 'model_path',
};

export async function saveAdventure(adventure: Adventure): Promise<void> {
  const index = await getAllAdventureIds();
  if (!index.includes(adventure.id)) {
    index.push(adventure.id);
    await AsyncStorage.setItem(KEYS.adventures, JSON.stringify(index));
  }
  await AsyncStorage.setItem(
    KEYS.adventure(adventure.id),
    JSON.stringify(adventure),
  );
}

export async function getAdventure(id: string): Promise<Adventure | null> {
  const data = await AsyncStorage.getItem(KEYS.adventure(id));
  return data ? JSON.parse(data) : null;
}

export async function getAllAdventures(): Promise<Adventure[]> {
  const ids = await getAllAdventureIds();
  const adventures: Adventure[] = [];
  for (const id of ids) {
    const adventure = await getAdventure(id);
    if (adventure) {
      adventures.push(adventure);
    }
  }
  return adventures.sort(
    (a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
  );
}

export async function deleteAdventure(id: string): Promise<void> {
  const index = await getAllAdventureIds();
  const newIndex = index.filter(i => i !== id);
  await AsyncStorage.setItem(KEYS.adventures, JSON.stringify(newIndex));
  await AsyncStorage.removeItem(KEYS.adventure(id));
}

async function getAllAdventureIds(): Promise<string[]> {
  const data = await AsyncStorage.getItem(KEYS.adventures);
  return data ? JSON.parse(data) : [];
}

export async function saveModelPath(path: string): Promise<void> {
  await AsyncStorage.setItem(KEYS.modelPath, path);
}

export async function getModelPath(): Promise<string | null> {
  return AsyncStorage.getItem(KEYS.modelPath);
}
