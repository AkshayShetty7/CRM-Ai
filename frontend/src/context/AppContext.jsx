import React, { createContext, useContext, useReducer, useCallback } from 'react';

const AppContext = createContext(null);

const initialState = {
  // Agent
  agentReady: false,
  orgName: '',
  // Schema
  schema: null,
  // Last query
  lastResult: null,
  queryHistory: [],
  // Campaigns
  campaigns: {},
  // UI
  activeTab: 'query',
};

function reducer(state, action) {
  switch (action.type) {
    case 'AGENT_READY':
      return { ...state, agentReady: true, orgName: action.orgName };
    case 'SCHEMA_LOADED':
      return { ...state, schema: action.schema };
    case 'QUERY_RESULT':
      return {
        ...state,
        lastResult: action.result,
        queryHistory: [
          { question: action.question, result: action.result, ts: new Date().toISOString() },
          ...state.queryHistory.slice(0, 19),
        ],
      };
    case 'CAMPAIGN_CREATED':
      return {
        ...state,
        campaigns: { ...state.campaigns, [action.campaign.campaign_id]: action.campaign },
      };

    case 'CAMPAIGN_DELETED': {
      const campaigns = { ...state.campaigns };

      delete campaigns[action.campaignId];

      return {
        ...state,
        campaigns,
      };
    }
    case 'CAMPAIGN_SENT':
      return {
        ...state,
        campaigns: {
          ...state.campaigns,
          [action.campaignId]: {
            ...state.campaigns[action.campaignId],
            status: 'completed',
            sendResult: action.result,
          },
        },
      };
    case 'SET_TAB':
      return { ...state, activeTab: action.tab };
    case 'RESET':
      return { ...initialState };
    default:
      return state;
  }
}

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const setAgentReady = useCallback((orgName) =>
    dispatch({ type: 'AGENT_READY', orgName }), []);
  const setSchema = useCallback((schema) =>
    dispatch({ type: 'SCHEMA_LOADED', schema }), []);
  const setQueryResult = useCallback((question, result) =>
    dispatch({ type: 'QUERY_RESULT', question, result }), []);
  const setCampaign = useCallback((campaign) =>
    dispatch({ type: 'CAMPAIGN_CREATED', campaign }), []);
  const setCampaignSent = useCallback((campaignId, result) =>
    dispatch({ type: 'CAMPAIGN_SENT', campaignId, result }), []);
  const setTab = useCallback((tab) =>
    dispatch({ type: 'SET_TAB', tab }), []);
  const removeCampaign = useCallback((campaignId) =>
    dispatch({type: 'CAMPAIGN_DELETED',campaignId,}),[]);

  return (
    <AppContext.Provider
      value={{state,setAgentReady,setSchema,setQueryResult,setCampaign,setCampaignSent,removeCampaign,setTab}}
    >
      {children}
    </AppContext.Provider>
  );
}

export const useAppContext = () => {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useAppContext must be used within AppProvider');
  return ctx;
};
