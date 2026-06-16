import React from 'react';
import {NavigationContainer} from '@react-navigation/native';
import {createNativeStackNavigator} from '@react-navigation/native-stack';
import {SafeAreaProvider} from 'react-native-safe-area-context';
import {StatusBar} from 'react-native';
import HomeScreen from './src/screens/HomeScreen';
import ModelSetupScreen from './src/screens/ModelSetupScreen';
import AdventureSetupScreen from './src/screens/AdventureSetupScreen';
import GameScreen from './src/screens/GameScreen';
import CombatScreen from './src/screens/CombatScreen';
import {RootStackParamList} from './src/types';

const Stack = createNativeStackNavigator<RootStackParamList>();

const NAV_THEME = {
  dark: true,
  colors: {
    primary: '#c9a84c',
    background: '#0d0d1a',
    card: '#1a1a2e',
    text: '#e8e8e8',
    border: '#2d2d4e',
    notification: '#c9a84c',
  },
};

export default function App() {
  return (
    <SafeAreaProvider>
      <StatusBar barStyle="light-content" backgroundColor="#0d0d1a" />
      <NavigationContainer theme={NAV_THEME}>
        <Stack.Navigator
          initialRouteName="Home"
          screenOptions={{
            headerStyle: {backgroundColor: '#1a1a2e'},
            headerTintColor: '#c9a84c',
            headerTitleStyle: {fontWeight: 'bold'},
            contentStyle: {backgroundColor: '#0d0d1a'},
          }}>
          <Stack.Screen
            name="Home"
            component={HomeScreen}
            options={{headerShown: false}}
          />
          <Stack.Screen
            name="ModelSetup"
            component={ModelSetupScreen}
            options={{title: 'Load AI Model'}}
          />
          <Stack.Screen
            name="AdventureSetup"
            component={AdventureSetupScreen}
            options={{title: 'New Adventure'}}
          />
          <Stack.Screen
            name="Game"
            component={GameScreen}
            options={{title: 'Adventure'}}
          />
          <Stack.Screen
            name="Combat"
            component={CombatScreen}
            options={{title: 'Combat'}}
          />
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
