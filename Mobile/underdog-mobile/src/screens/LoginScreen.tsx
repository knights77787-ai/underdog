import * as WebBrowser from 'expo-web-browser';
import * as Linking from 'expo-linking';
import React, { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { useSession } from '../context/SessionContext';
import { useToast } from '../context/ToastContext';
import { apiPath, API_PATHS } from '../config';
import type { AuthGuestResponse } from '../config';

function parseSessionFromUrl(url: string): string | null {
  try {
    const parsed = Linking.parse(url);
    const q = (parsed.queryParams as Record<string, string>) || {};
    return q.session_id ?? null;
  } catch {
    return null;
  }
}

export function LoginScreen() {
  const { setSessionId } = useSession();
  const { showToast } = useToast();
  const [loading, setLoading] = useState<'guest' | 'google' | 'kakao' | null>(null);

  const applySessionFromUrl = useCallback(
    (url: string) => {
      const sid = parseSessionFromUrl(url);
      if (sid) {
        setSessionId(sid);
        showToast('로그인되었습니다');
      }
    },
    [setSessionId, showToast]
  );

  useEffect(() => {
    const sub = Linking.addEventListener('url', (e) => {
      applySessionFromUrl(e.url);
    });
    Linking.getInitialURL().then((url) => {
      if (url) applySessionFromUrl(url);
    });
    return () => sub.remove();
  }, [applySessionFromUrl]);

  const handleGuestLogin = async () => {
    setLoading('guest');
    try {
      const res = await fetch(apiPath(API_PATHS.AUTH_GUEST), { method: 'POST' });
      const data = (await res.json()) as AuthGuestResponse & { detail?: string };
      if (data?.ok && data?.session_id) {
        await setSessionId(data.session_id);
        showToast('게스트로 로그인했습니다');
      } else {
        showToast(data?.detail || '로그인에 실패했습니다');
      }
    } catch {
      showToast('네트워크 오류입니다');
    } finally {
      setLoading(null);
    }
  };

  const handleGoogleLogin = async () => {
    setLoading('google');
    try {
      const url = `${apiPath(API_PATHS.AUTH_GOOGLE_LOGIN)}?mobile=1`;
      await WebBrowser.openBrowserAsync(url, { createTask: false });
      showToast('브라우저에서 구글 로그인 후 앱으로 돌아오세요');
    } catch {
      showToast('브라우저를 열 수 없습니다');
    } finally {
      setLoading(null);
    }
  };

  const handleKakaoLogin = async () => {
    setLoading('kakao');
    try {
      const url = `${apiPath(API_PATHS.AUTH_KAKAO_LOGIN)}?mobile=1`;
      await WebBrowser.openBrowserAsync(url, { createTask: false });
      showToast('브라우저에서 카카오 로그인 후 앱으로 돌아오세요');
    } catch {
      showToast('브라우저를 열 수 없습니다');
    } finally {
      setLoading(null);
    }
  };

  const loadingAny = loading !== null;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Underdog</Text>
      <Text style={styles.subtitle}>라이브 자막 · 알림</Text>
      <Card style={styles.card}>
        {loadingAny ? (
          <ActivityIndicator size="large" color="#2563eb" style={styles.loader} />
        ) : null}
        <Button
          title="게스트로 시작"
          onPress={handleGuestLogin}
          disabled={loadingAny}
        />
        <Button
          title="Google로 로그인"
          onPress={handleGoogleLogin}
          variant="outline"
          disabled={loadingAny}
          style={styles.btn}
        />
        <Button
          title="카카오로 로그인"
          onPress={handleKakaoLogin}
          variant="secondary"
          disabled={loadingAny}
          style={styles.btn}
        />
        <Text style={styles.hint}>
          구글/카카오는 브라우저에서 로그인 후 자동으로 앱으로 돌아옵니다.
        </Text>
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
  loader: {
    marginBottom: 16,
  },
  btn: {
    marginTop: 12,
  },
  hint: {
    marginTop: 16,
    fontSize: 13,
    color: '#94a3b8',
    textAlign: 'center',
  },
});
