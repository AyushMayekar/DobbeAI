# 🧠 Agentic Doctor Appointment & Reporting Assistant

This project is a **full-stack AI-driven healthcare assistant** that uses **MCP (Model Context Protocol)** to expose backend tools that an AI agent (LLM) can dynamically discover and invoke. It demonstrates **agentic behavior**, where the LLM autonomously chooses which tool to call, when to call it, and how to chain them to fulfill user requests.

The system enables:

* **Patients:** Natural-language appointment scheduling
* **Doctors:** Smart daily summary reports delivered via notifications
* **LLM:** Multi-turn reasoning, memory of past messages, and dynamic tool usage
* **Backend:** FastAPI MCP tools for availability, appointment creation, and analytics

---

# 🚀 Features

### ✅ Scenario 1 — **Patient Appointment Scheduling (LLM + MCP Agent)**

Patients can type prompts like:

> “I want to book an appointment with Dr. Sharma tomorrow morning.”

The AI agent will:

1. Parse the intent
2. Use MCP **get_doctor_availability** tool
3. Suggest available slots
4. Book an appointment using MCP **create_appointment** tool
5. Create a **Google Calendar event**
6. Send a **Gmail confirmation email**
7. Return a friendly confirmation message in the UI

### Example Conversation

**Patient:** “Check Dr. Roy’s availability on Friday afternoon.”
**AI:** “Here are the available slots…”
**Patient:** “Book the 3 PM slot.”
**AI:** “Appointment booked! Check your email.”

This works across **multiple prompts** using session-based context memory.

---

### ✅ Scenario 2 — **Doctor Summary Report + Notification**

Doctors can type:

* “How many patients visited yesterday?”
* “How many fever cases today?”
* “Give me today's summary.”

Or press a **dashboard button**.

The LLM will:

1. Invoke MCP **get_doctor_summary_report**
2. Aggregate:

   * yesterday/today/tomorrow patient counts
   * categorized reasons (fever, checkup, respiratory, pain, etc.)
3. Generate a human-readable summary
4. Send a **Slack notification** (or any chosen channel)

### Example Output

```
Summary report for Dr. Mehta — 2025-12-02  
- Patients yesterday: 2  
- Patients today: 4  
- Patients tomorrow: 1  
- Reason breakdown:
  • Checkup: 2  
  • Fever: 1  
  • Respiratory: 1  
Notification sent: Yes  
```

---

### ✅ Multi-Doctor Support (Dynamic)

Doctors stored in PostgreSQL:

* Dr. Ahuja
* Dr. Mehta
* Dr. Sharma
* Dr. Roy
* Dr. Joy
* Dr. Joshi

LLM has strict rules:

* Never guess doctor names
* Never default to one
* Ask user if missing
* Reject unknown doctors

---

### ✅ RBAC — Role Based Access Control

Login system implemented:

* **Patient**

  * Can chat, book, check availability
  * Cannot request doctor summaries

* **Doctor**

  * Access doctor dashboard
  * Can request summary + notify
  * LLM automatically identifies the doctor identity

---

### ✅ Integrations

| Feature        | Tech                                 |
| -------------- | ------------------------------------ |
| Database       | PostgreSQL                           |
| Backend        | FastAPI                              |
| AI Agent       | OpenAI GPT-4.1 with function calling |
| Protocol       | Model Context Protocol (MCP)         |
| Email          | Gmail API                            |
| Calendar       | Google Calendar API                  |
| Notifications  | Slack Webhook                        |
| Frontend       | ReactJS                              |
| Context Memory | Custom session store                 |

---

# 🏗 Architecture Overview

```
┌────────────────────┐        ┌───────────────────────────┐
│     React UI       │  --->  │   FastAPI Backend (MCP)   │
│ (Patient/Doctor UI)│        │ - /api/ai (LLM endpoint)   │
└────────────────────┘        │ - /doctor/report           │
        ▲   |                 │ - Tool registry            │
        |   │                 └───────────────────────────┘
        |   │                        │
        |   └────────────────────────┤
        ▼                            ▼
┌────────────────────┐      ┌──────────────────────────────┐
│   OpenAI GPT-4.1   │      │      MCP Tools Layer          │
│ (agentic tool use) │ ---> │ get_doctor_availability       │
└────────────────────┘      │ create_appointment            │
                            │ get_doctor_stats              │
                            │ get_doctor_summary_report     │
                            └──────────────────────────────┘
                                      │
                                      ▼
                     ┌────────────────────────────────────┐
                     │ PostgreSQL (Doctors & Appointments)│
                     └────────────────────────────────────┘

Integrations:
 - Google Calendar
 - Gmail Email
 - Slack Notifications
```

---

# ⚙️ Setup Instructions

## 1️⃣ Clone the Repository

```bash
git clone https://github.com/AyushMayekar/DobbeAI
cd DobbeAI
```

---

# 🔧 Backend Setup (FastAPI + PostgreSQL + MCP)

## 2️⃣ Create Backend venv

```bash
cd backend
python -m venv .venv
source .venv/bin/activate     
.venv\Scripts\activate        
```

## 3️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

## 4️⃣ Setup PostgreSQL

Create DB:

```sql
CREATE DATABASE mcp_healthcare;
```

Update `.env`:

```
DATABASE_URL=postgresql://username:password@localhost:5432/mcp_healthcare
OPENAI_API_KEY=your_key
GOOGLE_CLIENT_ID=xxx
GOOGLE_CLIENT_SECRET=xxx
SLACK_WEBHOOK_URL=xxx
EMAIL_SENDER=xxx@gmail.com
```

## 5️⃣ Initialize DB

```bash
python -m app.init_db
python -m app.seed
```

Seeds doctors:

* Ahuja, Mehta, Sharma, Roy, Joy, Joshi

## 6️⃣ Run Backend

```bash
uvicorn app.main:app --reload
```

---

# 💻 Frontend Setup (React)

## 1️⃣ Install Node Modules

```bash
cd frontend
npm install
```

## 2️⃣ Run

```bash
npm start
```

---

# 🧪 Testing the System

## ✔ Patient Booking Example

User:

```
Check Dr. Sharma’s availability tomorrow morning.
```

AI:

```
Here are available slots...
```

User:

```
Book the 10 AM slot for Ayush.
```

AI:

```
Appointment booked with Dr. Sharma on 2025-12-02T10:00.
A confirmation email has been sent!
```

Google Calendar event + Gmail sent.

---

## ✔ Doctor Summary Report Example

Doctor (or dashboard button):

```
Give me today's summary.
```

AI / button:

```
Summary report for Dr. Mehta — 2025-12-02
 - Patients yesterday: 2
 - Patients today: 4
 - Patients tomorrow: 1
 - Reason breakdown:
     • Checkup: 2
     • Fever: 1
     • Respiratory: 1
Notification sent: Yes
```

Slack receives message instantly.

---

# 🔐 Role-Based Access Control (RBAC)

Implemented using:

* Login screen
* Token stored in localStorage
* Backend verifies role
* Doctor-only endpoints
* LLM receives doctor identity (context injection)

Rules:

| Role    | Can book | Can check availability | Can get summary | Notified |
| ------- | -------- | ---------------------- | --------------- | -------- |
| Patient | ✔️       | ✔️                     | ❌               | Email    |
| Doctor  | ❌        | ✔️                     | ✔️              | Slack    |

---

# 🧠 MCP + LLM Agentic Behavior

### Tools exposed via MCP:

* `get_doctor_availability`
* `create_appointment`
* `get_doctor_stats`
* `get_doctor_summary_report`

### AI agent does:

* Uses **OpenAI function-calling**
* Decides which tool to call
* Chains calls if needed
* Maintains multi-turn context
* Validates doctor names
* Requests missing information
* Produces human output

This fulfills all **agentic workflow** expectations.

---

# 🖼 Screenshots (Add yours here)

### ✔ Appointment Booking

   ![1](https://github.com/AyushMayekar/DobbeAI/blob/main/SS00.png)

   ![2](https://github.com/AyushMayekar/DobbeAI/blob/main/SS01.png)


### ✔ Doctor Summary Notification

   ![1](https://github.com/AyushMayekar/DobbeAI/blob/main/SS02.png)

   ![2](https://github.com/AyushMayekar/DobbeAI/blob/main/SS03.png)


---

# 🎯 Conclusion

This project meets **all core assignment requirements**, demonstrating:

* Data-driven agentic LLM behavior
* MCP tool orchestration
* Full-stack integration (React ↔ FastAPI ↔ PostgreSQL ↔ APIs)
* Real-time email, calendar, and Slack notifications
* Strong engineering design and clarity
