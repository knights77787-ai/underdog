import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import React from 'react';
import { Text } from 'react-native';
import { CustomSoundsTab } from './CustomSoundsTab';
import { LiveTab } from './LiveTab';
import { SettingsTab } from './SettingsTab';

const Tab = createBottomTabNavigator();

export function LiveScreen() {
  return (
    <Tab.Navigator
      screenOptions={{
        tabBarActiveTintColor: '#2563eb',
        tabBarInactiveTintColor: '#94a3b8',
        headerStyle: { backgroundColor: '#f8fafc' },
        headerTitleStyle: { fontWeight: '600', color: '#0f172a' },
      }}
    >
      <Tab.Screen
        name="LiveTab"
        component={LiveTab}
        options={{
          title: '라이브',
          tabBarLabel: '라이브',
          tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 20 }}>📡</Text>,
        }}
      />
      <Tab.Screen
        name="SettingsTab"
        component={SettingsTab}
        options={{
          title: '설정',
          tabBarLabel: '설정',
          tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 20 }}>⚙️</Text>,
        }}
      />
      <Tab.Screen
        name="CustomSoundsTab"
        component={CustomSoundsTab}
        options={{
          title: '커스텀 소리',
          tabBarLabel: '소리',
          tabBarIcon: ({ color }) => <Text style={{ color, fontSize: 20 }}>🔊</Text>,
        }}
      />
    </Tab.Navigator>
  );
}
