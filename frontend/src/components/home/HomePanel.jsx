import React from "react";
import { useAppContext } from "../../context/AppContext";
import styles from "./HomePanel.module.css";

export default function HomePanel() {
  const { setTab } = useAppContext();

  return (
    <div className={styles.page}>
      <div className={styles.background}></div>

      <div className={styles.hero}>

        <div className={styles.badge}>
          AI Powered CRM Platform
        </div>

        <h1>
          CRM AI Agent
        </h1>

        <p className={styles.description}>
          Upload your customer dataset and use AI to analyze CRM data,
          query customers in natural language, generate personalized
          email campaigns, review AI-generated drafts, and send emails
          with a single click.
        </p>

        <div className={styles.buttons}>
          <button
            className={styles.primaryBtn}
            onClick={() => setTab("schema")}
          >
            Upload Customer Dataset
          </button>

          <a
            className={styles.secondaryBtn}
            href="https://www.youtube.com/watch?v=iTBWpNFR2kg"
            target="_blank"
            rel="noreferrer"
          >
            ▶ Watch Demo
          </a>
        </div>

        <div className={styles.divider}></div>

        <div className={styles.features}>

          <div className={styles.feature}>
         
            <span>Excel Upload</span>
          </div>

          <span>→</span>
                
          <div className={styles.feature}>
            
            <span>Natural Language Query</span>
          </div>
            <span>→</span>
          <div className={styles.feature}>
            
            <span>AI Email Generation</span>
          </div>
<span>→</span>
          <div className={styles.feature}>
           
            <span>One-click Send</span>
          </div>

        </div>

      

      </div>
    </div>
  );
}