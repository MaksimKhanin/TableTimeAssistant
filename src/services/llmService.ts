import {initLlama, LlamaContext} from 'llama.rn';

interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

class LLMService {
  private context: LlamaContext | null = null;
  private modelPath: string | null = null;

  async loadModel(
    path: string,
    onProgress?: (progress: number) => void,
  ): Promise<void> {
    if (this.context) {
      await this.context.release();
      this.context = null;
    }
    this.context = await initLlama(
      {
        model: path,
        use_mlock: true,
        n_ctx: 4096,
        n_batch: 512,
        n_threads: 4,
        n_gpu_layers: 0,
      },
      (progress: number) => {
        onProgress?.(progress);
      },
    );
    this.modelPath = path;
  }

  isModelLoaded(): boolean {
    return this.context !== null;
  }

  getModelPath(): string | null {
    return this.modelPath;
  }

  getModelName(): string | null {
    if (!this.modelPath) return null;
    const parts = this.modelPath.split('/');
    return parts[parts.length - 1];
  }

  async generateResponse(
    messages: ChatMessage[],
    onToken?: (token: string) => void,
  ): Promise<string> {
    if (!this.context) {
      throw new Error('Model not loaded');
    }

    const result = await this.context.completion(
      {
        messages,
        n_predict: 1024,
        temperature: 0.8,
        top_p: 0.9,
        top_k: 40,
        min_p: 0.05,
        stop: ['<|end|>', '<|im_end|>', '</s>', '[INST]'],
        emit_partial_completion: !!onToken,
      },
      data => {
        if (onToken && data.token) {
          onToken(data.token);
        }
      },
    );

    return result.text.trim();
  }

  async release(): Promise<void> {
    if (this.context) {
      await this.context.release();
      this.context = null;
      this.modelPath = null;
    }
  }
}

export const llmService = new LLMService();
