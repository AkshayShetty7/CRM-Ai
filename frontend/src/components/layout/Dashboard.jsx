import React from 'react';
import { useAppContext } from '../../context/AppContext';
import Sidebar from './Sidebar';
import QueryPanel from '../query/QueryPanel';
import SchemaPanel from '../schema/SchemaPanel';
import CampaignPanel from '../campaign/CampaignPanel';
import styles from './Dashboard.module.css';
import AboutPanel from '../about/AboutPanel';
import HomePanel from "../home/HomePanel";

const PANELS = {
  home: HomePanel,
  query: QueryPanel,
  schema: SchemaPanel,
  campaign: CampaignPanel,
  about: AboutPanel,
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
