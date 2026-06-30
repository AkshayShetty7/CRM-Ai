import React from "react";
import styles from "./AboutPanel.module.css";

export default function AboutPanel() {
  return (
    <div className={styles.container}>
      <h1 className={styles.heading}>About</h1>
      <p className={styles.subtitle}>
        Developer
      </p>

      <div className={styles.card}>
        <div className={styles.avatar}>AS</div>

        <div className={styles.info}>
          <h2>Akshay Shetty</h2>

          <p className={styles.role}>
            Computer Science & Engineering Student
          </p>

          <p className={styles.role2}>
            AI/ML Developer | Generative AI, RAG Systems & Computer Vision
          </p>

          <div className={styles.links}>
            <a
              href="https://portfolio-akshayshetty.vercel.app/"
              target="_blank"
              rel="noreferrer"
            >
              Portfolio
            </a>

            <a
              href="https://www.linkedin.com/in/akshay-shetty-25b3a624a/"
              target="_blank"
              rel="noreferrer"
            >
              LinkedIn
            </a>

            <a
              href="https://github.com/AkshayShetty7"
              target="_blank"
              rel="noreferrer"
            >
              GitHub
            </a>

            <a
              href="https://github.com/AkshayShetty7/CRM-Ai"
              target="_blank"
              rel="noreferrer"
            >
              Repository
            </a>

            <a href="mailto:akshayshetty747@gmail.com">
              Email
            </a>
          </div>
        </div>
      </div>

      <div className={styles.footer}>
        <h3>CRM AI Agent</h3>

        <p>
          An AI powered CRM platform that enables natural language querying,
          schema exploration, customer segmentation, and personalized email
          campaign generation using Large Language Models.
        </p>

        <div className={styles.links}>

              <a
                href="https://www.youtube.com/watch?v=iTBWpNFR2kg"
                target="_blank"
                rel="noreferrer"
            >
                Demo Video
            </a>
        </div>

      </div>
    </div>
  );
}