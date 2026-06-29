import React from 'react';
import { useAppContext } from '../../context/AppContext';
import Sidebar from './Sidebar';
import QueryPanel from '../query/QueryPanel';
import SchemaPanel from '../schema/SchemaPanel';
import CampaignPanel from '../campaign/CampaignPanel';
import styles from './Dashboard.module.css';

const PANELS = {
  query: QueryPanel,
  schema: SchemaPanel,
  campaign: CampaignPanel,
};

export default function Dashboard() {
  const { state } = useAppContext();
  const ActivePanel = PANELS[state.activeTab] || QueryPanel;

  return (
    <div className={styles.layout}>
      <Sidebar />
      <main className={styles.main}>
        <ActivePanel />
      </main>
    </div>
  );
}
