import AsyncStorage from '@react-native-async-storage/async-storage';

const SESSION_KEY = '@underdog/session_id';

export async function getSessionId(): Promise<string | null> {
  return AsyncStorage.getItem(SESSION_KEY);
}

export async function setSessionId(sessionId: string): Promise<void> {
  await AsyncStorage.setItem(SESSION_KEY, sessionId);
}

export async function clearSessionId(): Promise<void> {
  await AsyncStorage.removeItem(SESSION_KEY);
}
