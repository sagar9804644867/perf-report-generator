# 📊 Performance Test Report Generator

Upload a **JMeter JTL file** and instantly generate a professional HTML performance test report with charts, SLO validation, and error analysis.

Built by **Sagar Chaudhary**, Performance Engineering Lead @ PwC India.

## ✨ Features

- ✅ **JTL Upload** — supports JMeter CSV JTL files
- ✅ **KPI Dashboard** — Avg, P90, P95, P99, Error Rate, Throughput
- ✅ **SLO Validation** — auto PASS/FAIL against configurable thresholds
- ✅ **Interactive Charts** — Plotly charts for response time, errors, throughput
- ✅ **HTML Report** — download a standalone professional report
- ✅ **CSV Export** — download summary stats as CSV
- ✅ **Error Breakdown** — grouped by transaction and response code
- ✅ **Sample Data** — demo mode with 500 simulated requests

## 🚀 Run Locally

```bash
git clone https://github.com/sagar9804644867/perf-report-generator
cd perf-report-generator
pip install -r requirements.txt
streamlit run app.py
```

## 📋 JTL Format

Your JTL file should have these columns:
```
timeStamp, elapsed, label, responseCode, responseMessage,
threadName, dataType, success, failureMessage, bytes,
sentBytes, grpThreads, allThreads, URL, Latency, IdleTime, Connect
```

Enable these in JMeter: **Options → Save Service Results Configuration**

## 🛠️ Tech Stack
- **Streamlit** — UI
- **Plotly** — Charts
- **Pandas** — Data processing
- **NumPy** — Statistics

## 📬 Contact
**Sagar Chaudhary** — Performance Engineering Lead  
🌐 [Portfolio](https://sagar-portfolio-new.vercel.app)  
💼 [LinkedIn](https://linkedin.com/in/sagar-chaudhary-024254130)  
📧 sagar98chaudhary19@gmail.com
