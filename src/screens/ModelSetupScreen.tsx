import React, {useState} from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
} from 'react-native';
import DocumentPicker from 'react-native-document-picker';
import {useNavigation} from '@react-navigation/native';
import {llmService} from '../services/llmService';
import {saveModelPath} from '../services/storageService';

export default function ModelSetupScreen() {
  const navigation = useNavigation();
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [loaded, setLoaded] = useState(false);

  const pickFile = async () => {
    try {
      const result = await DocumentPicker.pickSingle({
        type: [DocumentPicker.types.allFiles],
        copyTo: 'cachesDirectory',
      });
      if (result.fileCopyUri) {
        const filePath = decodeURIComponent(result.fileCopyUri.replace('file://', ''));
        setSelectedPath(filePath);
        setSelectedName(result.name || 'model.gguf');
        setLoaded(false);
        setProgress(0);
      }
    } catch (e) {
      if (!DocumentPicker.isCancel(e)) {
        Alert.alert('Error', 'Failed to select file');
      }
    }
  };

  const loadModel = async () => {
    if (!selectedPath) return;
    setLoading(true);
    setProgress(0);
    try {
      await llmService.loadModel(selectedPath, p => setProgress(Math.round(p)));
      await saveModelPath(selectedPath);
      setLoaded(true);
      Alert.alert('Success', 'Model loaded! You can now start an adventure.', [
        {text: 'OK', onPress: () => navigation.goBack()},
      ]);
    } catch (e: any) {
      Alert.alert('Load Failed', e?.message || 'Could not load model');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <View style={styles.infoBox}>
        <Text style={styles.infoTitle}>🤖 Local AI Model</Text>
        <Text style={styles.infoText}>
          This app runs the AI Game Master entirely on your device — no
          internet connection required. You need a GGUF model file
          (e.g., Mistral-7B, Llama-3, Gemma-2).
        </Text>
        <Text style={styles.infoText}>
          Recommended: a 4-bit quantized model (Q4_K_M) that fits in your
          device RAM. 7B models require ~4 GB RAM.
        </Text>
        <Text style={styles.tipText}>
          💡 Download models from HuggingFace (search "GGUF").
        </Text>
      </View>

      <TouchableOpacity
        style={styles.pickBtn}
        onPress={pickFile}
        disabled={loading}
        activeOpacity={0.8}>
        <Text style={styles.pickBtnText}>📂 Select GGUF Model File</Text>
      </TouchableOpacity>

      {selectedName && (
        <View style={styles.selectedBox}>
          <Text style={styles.selectedLabel}>Selected:</Text>
          <Text style={styles.selectedName}>{selectedName}</Text>
        </View>
      )}

      {selectedPath && !loaded && (
        <TouchableOpacity
          style={[styles.loadBtn, loading && styles.loadBtnDisabled]}
          onPress={loadModel}
          disabled={loading}
          activeOpacity={0.8}>
          {loading ? (
            <View style={styles.loadingInner}>
              <ActivityIndicator color="#0d0d1a" size="small" />
              <Text style={styles.loadBtnText}>Loading... {progress}%</Text>
            </View>
          ) : (
            <Text style={styles.loadBtnText}>⚡ Load Model</Text>
          )}
        </TouchableOpacity>
      )}

      {loading && (
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, {width: `${progress}%` as any}]} />
        </View>
      )}

      {loaded && (
        <View style={styles.successBox}>
          <Text style={styles.successText}>✅ Model loaded successfully!</Text>
        </View>
      )}

      {llmService.isModelLoaded() && !loaded && (
        <View style={styles.currentBox}>
          <Text style={styles.currentText}>
            Currently loaded: {llmService.getModelName()}
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0d0d1a',
    padding: 20,
  },
  infoBox: {
    backgroundColor: '#16213e',
    borderRadius: 12,
    padding: 16,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#2d2d4e',
  },
  infoTitle: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 16,
    marginBottom: 8,
  },
  infoText: {
    color: '#a0a0b0',
    fontSize: 14,
    lineHeight: 20,
    marginBottom: 8,
  },
  tipText: {
    color: '#6666aa',
    fontSize: 13,
    fontStyle: 'italic',
  },
  pickBtn: {
    backgroundColor: '#0f3460',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#c9a84c',
    marginBottom: 16,
  },
  pickBtnText: {
    color: '#c9a84c',
    fontWeight: 'bold',
    fontSize: 16,
  },
  selectedBox: {
    backgroundColor: '#16213e',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  selectedLabel: {
    color: '#666',
    fontSize: 12,
  },
  selectedName: {
    color: '#e8e8e8',
    fontWeight: 'bold',
    fontSize: 14,
    marginTop: 2,
  },
  loadBtn: {
    backgroundColor: '#c9a84c',
    borderRadius: 12,
    paddingVertical: 16,
    alignItems: 'center',
    marginBottom: 12,
  },
  loadBtnDisabled: {
    opacity: 0.7,
  },
  loadBtnText: {
    color: '#0d0d1a',
    fontWeight: 'bold',
    fontSize: 16,
    marginLeft: 8,
  },
  loadingInner: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  progressTrack: {
    height: 6,
    backgroundColor: '#16213e',
    borderRadius: 3,
    overflow: 'hidden',
    marginBottom: 12,
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#c9a84c',
    borderRadius: 3,
  },
  successBox: {
    backgroundColor: '#0a2a0a',
    borderRadius: 8,
    padding: 14,
    borderWidth: 1,
    borderColor: '#4caf50',
    alignItems: 'center',
  },
  successText: {
    color: '#4caf50',
    fontWeight: 'bold',
    fontSize: 15,
  },
  currentBox: {
    backgroundColor: '#16213e',
    borderRadius: 8,
    padding: 12,
    borderWidth: 1,
    borderColor: '#4caf50',
  },
  currentText: {
    color: '#4caf50',
    fontSize: 13,
  },
});
