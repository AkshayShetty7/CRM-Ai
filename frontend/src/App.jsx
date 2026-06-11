import React from 'react';
import { useAppContext } from './context/AppContext';
import SetupPage from './components/layout/SetupPage';
import Dashboard from './components/layout/Dashboard';

export default function App() {
  const { state } = useAppContext();
  return state.agentReady ? <Dashboard /> : <SetupPage />;
}
