import React, { useCallback, useEffect } from 'react';
import {
  ActivityIndicator,
  Alert,
  FlatList,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Button } from '../components/Button';
import { Card } from '../components/Card';
import { useLiveWs, type LogEntry } from '../hooks/useLiveWs';
import { useMic } from '../hooks/useMic';
import { useSession } from '../context/SessionContext';
import { WS_URL } from '../config';

function LogRow({ item }: { item: LogEntry }) {
  const isAlert = item.type === 'alert';
  const danger = isAlert && item.event_type === 'danger';
  return (
    <View style={[styles.logRow, danger && styles.logRowDanger]}>
      <Text style={[styles.logBadge, danger ? styles.logBadgeDanger : styles.logBadgeAlert]}>
        {isAlert ? (danger ? '위험' : '알림') : '자막'}
      </Text>
      <Text style={styles.logText} numberOfLines={2}>{item.text}</Text>
    </View>
  );
}

export function LiveTab() {
  const { sessionId } = useSession();
  const {
    status,
    connected,
    connecting,
    toggle,
    sendAudioChunk,
    logs,
    latestAlert,
    currentCaption,
  } = useLiveWs(WS_URL);
  const { permissionStatus, isRecording, requestPermission, start, stop } = useMic();

  useEffect(() => {
    if (!connected) stop();
  }, [connected, stop]);

  const handleMicToggle = useCallback(async () => {
    if (!sessionId) return;
    if (isRecording) {
      stop();
      return;
    }
    if (permissionStatus === 'denied') {
      Alert.alert(
        '마이크 권한',
        '설정에서 마이크 권한을 허용해 주세요.',
        [{ text: '확인' }]
      );
      return;
    }
    const ok = await start(sessionId, sendAudioChunk);
    if (!ok) {
      Alert.alert('마이크', '마이크를 켤 수 없습니다. 권한을 확인해 주세요.');
    }
  }, [sessionId, isRecording, permissionStatus, start, stop, sendAudioChunk]);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>라이브</Text>
        <Button
          title={connected ? '연결 끊기' : '연결하기'}
          onPress={() => toggle(sessionId ?? null)}
          variant={connected ? 'outline' : 'primary'}
          disabled={connecting || !sessionId}
        />
        {connecting && <ActivityIndicator size="small" color="#2563eb" style={styles.spinner} />}
      </View>

      {!sessionId ? (
        <Text style={styles.hint}>로그인 후 연결할 수 있습니다.</Text>
      ) : connected ? (
        <>
          {latestAlert && (
            <Card style={[styles.hero, latestAlert.event_type === 'danger' && styles.heroDanger]}>
              <Text style={styles.heroLabel}>최근 알림</Text>
              <Text style={styles.heroText}>{latestAlert.text}</Text>
              {latestAlert.keyword ? (
                <Text style={styles.heroKeyword}>#{latestAlert.keyword}</Text>
              ) : null}
            </Card>
          )}

          {currentCaption ? (
            <View style={styles.captionBox}>
              <Text style={styles.captionLabel}>자막</Text>
              <Text style={styles.captionText}>{currentCaption}</Text>
            </View>
          ) : null}

          <Card style={styles.micCard}>
            <Text style={styles.micTitle}>마이크</Text>
            <Text style={styles.micDesc}>
              {isRecording ? '전송 중 — 음성이 서버로 전달됩니다.' : '켜면 음성이 실시간으로 전송됩니다.'}
            </Text>
            <Button
              title={isRecording ? '마이크 끄기' : '마이크 켜기'}
              onPress={handleMicToggle}
              variant={isRecording ? 'outline' : 'primary'}
              style={styles.micBtn}
            />
            {permissionStatus === 'denied' && (
              <Text style={styles.micPermissionHint}>마이크 권한이 거부되었습니다.</Text>
            )}
          </Card>

          <Text style={styles.sectionTitle}>로그</Text>
          <FlatList
            data={logs}
            keyExtractor={(item) => item.id}
            renderItem={({ item }) => <LogRow item={item} />}
            style={styles.list}
            contentContainerStyle={styles.listContent}
            ListEmptyComponent={<Text style={styles.empty}>수신된 로그가 없습니다.</Text>}
          />
        </>
      ) : (
        <Text style={styles.hint}>연결하기를 누르면 자막·알림을 실시간으로 받습니다.</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: '#f8fafc',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 16,
  },
  title: {
    fontSize: 22,
    fontWeight: '600',
    color: '#0f172a',
    flex: 1,
  },
  spinner: {
    marginLeft: 4,
  },
  hint: {
    fontSize: 14,
    color: '#64748b',
    marginTop: 8,
  },
  hero: {
    marginBottom: 12,
    borderLeftWidth: 4,
    borderLeftColor: '#3b82f6',
  },
  heroDanger: {
    borderLeftColor: '#dc2626',
    backgroundColor: '#fef2f2',
  },
  heroLabel: {
    fontSize: 12,
    color: '#64748b',
    marginBottom: 4,
  },
  heroText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#0f172a',
  },
  heroKeyword: {
    fontSize: 12,
    color: '#64748b',
    marginTop: 4,
  },
  captionBox: {
    backgroundColor: '#f1f5f9',
    padding: 12,
    borderRadius: 8,
    marginBottom: 12,
  },
  captionLabel: {
    fontSize: 11,
    color: '#64748b',
    marginBottom: 4,
  },
  captionText: {
    fontSize: 15,
    color: '#0f172a',
  },
  micCard: {
    marginBottom: 12,
  },
  micTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#0f172a',
    marginBottom: 4,
  },
  micDesc: {
    fontSize: 13,
    color: '#64748b',
    marginBottom: 12,
  },
  micBtn: {
    alignSelf: 'flex-start',
  },
  micPermissionHint: {
    fontSize: 12,
    color: '#dc2626',
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#475569',
    marginBottom: 8,
  },
  list: {
    flex: 1,
  },
  listContent: {
    paddingBottom: 24,
  },
  logRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    backgroundColor: '#fff',
    borderRadius: 8,
    marginBottom: 6,
    gap: 10,
  },
  logRowDanger: {
    backgroundColor: '#fef2f2',
  },
  logBadge: {
    fontSize: 11,
    fontWeight: '600',
    color: '#3b82f6',
    backgroundColor: '#eff6ff',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    overflow: 'hidden',
  },
  logBadgeDanger: {
    color: '#dc2626',
    backgroundColor: '#fee2e2',
  },
  logBadgeAlert: {
    color: '#64748b',
    backgroundColor: '#f1f5f9',
  },
  logText: {
    flex: 1,
    fontSize: 14,
    color: '#0f172a',
  },
  empty: {
    fontSize: 14,
    color: '#94a3b8',
    textAlign: 'center',
    marginTop: 24,
  },
});
