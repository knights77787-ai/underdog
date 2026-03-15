import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { Button } from '../components/Button';
import { useSession } from '../context/SessionContext';

export function SettingsTab() {
  const { signOut } = useSession();

  return (
    <View style={styles.container}>
      <Text style={styles.title}>설정</Text>
      <Text style={styles.subtitle}>Phase 6에서 폰트/알림/쿨다운 등</Text>
      <Button title="로그아웃" onPress={signOut} variant="outline" style={styles.logout} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: '#f8fafc',
  },
  title: {
    fontSize: 22,
    fontWeight: '600',
    color: '#0f172a',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 14,
    color: '#64748b',
  },
  logout: {
    marginTop: 24,
  },
});
