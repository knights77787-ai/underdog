import React, { useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, View } from 'react-native';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { useSession } from '../context/SessionContext';
import { useToast } from '../context/ToastContext';
import { apiPath, API_PATHS } from '../config';
import type { AuthGuestResponse } from '../config';

export function LoginScreen() {
  const { setSessionId } = useSession();
  const { showToast } = useToast();
  const [loading, setLoading] = useState(false);

  const handleGuestLogin = async () => {
    setLoading(true);
    try {
      const res = await fetch(apiPath(API_PATHS.AUTH_GUEST), { method: 'POST' });
      const data = (await res.json()) as AuthGuestResponse & { detail?: string };
      if (data?.ok && data?.session_id) {
        await setSessionId(data.session_id);
        showToast('게스트로 로그인했습니다');
        // 세션 저장 후 RootNavigator가 Live 화면으로 전환
      } else {
        showToast(data?.detail || '로그인에 실패했습니다');
      }
    } catch (e) {
      showToast('네트워크 오류입니다');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Underdog</Text>
      <Text style={styles.subtitle}>라이브 자막 · 알림</Text>
      <Card style={styles.card}>
        {loading ? (
          <ActivityIndicator size="large" color="#2563eb" />
        ) : (
          <Button title="게스트로 시작" onPress={handleGuestLogin} />
        )}
        <Text style={styles.hint}>구글/카카오 로그인은 Phase 2에서 추가됩니다</Text>
      </Card>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
    backgroundColor: '#f8fafc',
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: '#0f172a',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 16,
    color: '#64748b',
    marginBottom: 32,
  },
  card: {
    width: '100%',
    maxWidth: 320,
  },
  hint: {
    marginTop: 16,
    fontSize: 13,
    color: '#94a3b8',
    textAlign: 'center',
  },
});
