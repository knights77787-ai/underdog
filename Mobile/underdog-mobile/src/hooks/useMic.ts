import { encode as base64Encode } from 'base-64';
import { Audio } from 'expo-av';
import { useCallback, useRef, useState } from 'react';
import { AUDIO_CHUNK_SAMPLES } from '../config';

const CHUNK_MS = 2000; // 2초 청크 (ws_protocol: 32000 samples @ 16kHz, rolling buffer)

function pcmChunkToBase64(samples: Int16Array): string {
  const u8 = new Uint8Array(samples.buffer);
  let binary = '';
  const chunkSize = 8192;
  for (let i = 0; i < u8.length; i += chunkSize) {
    const slice = u8.subarray(i, Math.min(i + chunkSize, u8.length));
    binary += String.fromCharCode.apply(null, Array.from(slice));
  }
  return base64Encode(binary);
}

export type MicPermissionStatus = 'undetermined' | 'granted' | 'denied';

export function useMic() {
  const [permissionStatus, setPermissionStatus] = useState<MicPermissionStatus>('undetermined');
  const [isRecording, setIsRecording] = useState(false);
  const recordingRef = useRef<Audio.Recording | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const requestPermission = useCallback(async (): Promise<boolean> => {
    const { status } = await Audio.requestPermissionsAsync();
    const granted = status === 'granted';
    setPermissionStatus(granted ? 'granted' : 'denied');
    return granted;
  }, []);

  const stop = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    const rec = recordingRef.current;
    if (rec) {
      try {
        rec.stopAndUnloadAsync().catch(() => {});
      } catch {}
      recordingRef.current = null;
    }
    setIsRecording(false);
  }, []);

  const start = useCallback(
    async (
      sessionId: string,
      sendChunk: (sessionId: string, tsMs: number, dataB64: string) => boolean
    ): Promise<boolean> => {
      const granted = permissionStatus === 'granted' || (await requestPermission());
      if (!granted) return false;

      stop();

      try {
        await Audio.setAudioModeAsync({
          allowsRecordingIOS: true,
          playsInSilentModeIOS: true,
          staysActiveInBackground: false,
          shouldDuckAndroid: true,
          playThroughEarpieceAndroid: false,
        });

        const { recording } = await Audio.Recording.createAsync(
          Audio.RecordingOptionsPresets.HIGH_QUALITY
        );
        recordingRef.current = recording;
        setIsRecording(true);

        const silence = new Int16Array(AUDIO_CHUNK_SAMPLES);
        silence.fill(0);
        const dataB64 = pcmChunkToBase64(silence);

        intervalRef.current = setInterval(() => {
          const sent = sendChunk(sessionId, Date.now(), dataB64);
          if (!sent) stop();
        }, CHUNK_MS);

        return true;
      } catch {
        stop();
        return false;
      }
    },
    [permissionStatus, requestPermission, stop]
  );

  return {
    permissionStatus,
    isRecording,
    requestPermission,
    start,
    stop,
  };
}
