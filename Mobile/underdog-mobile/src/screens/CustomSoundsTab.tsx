import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

export function CustomSoundsTab() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>커스텀 소리</Text>
      <Text style={styles.subtitle}>Phase 9에서 등록/목록</Text>
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
});
