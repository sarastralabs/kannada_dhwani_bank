# What to Speak — Kannada Voice Banking Guide

**Audience:** Demo staff, testers, juniors running the kiosk  
**Agent URL:** `https://127.0.0.1:5173` (or `https://<kiosk-ip>:5173` on same Wi‑Fi)  
**Admin URL:** `https://127.0.0.1:5174` — Customers, Speech turns, Conversation flow  
**Language:** Speak **Kannada** clearly; **English** also works for most intents (STT translates internally).

> **Demo only** — no real money moves. Forms are sample branch slips, not official bank documents.  
> On the agent screen, open **ಹೇಗೆ ಮಾತನಾಡುವುದು · How to speak** (bottom of the screen) for the same tips + demo accounts.

---

## Quick start

1. Admin opens counter → customer steps into camera frame (or taps **Start**).
2. Greeting text appears on screen first, then voice plays — **wait** (do not speak yet).
3. The big status line turns **green: ಈಗ ಮಾತನಾಡಿ · Speak now** → **now speak**.
4. One short request in Kannada. For balance, give the **last 4 digits** of the account number.
5. Confirm each form value with **ಹೌದು** / **ಸರಿ**; fix with **ಮತ್ತೆ ಹೇಳಿ** / **ಇಲ್ಲ**.
6. Say **ಮುಗಿಸು** or tap **End** to finish.

### Screen status (wait vs speak)

The large status box at the top of the conversation screen always shows **one** state:

| Status (colour) | What it means | What you do |
|-----------------|---------------|-------------|
| **ಸ್ವಲ್ಪ ಕಾಯಿರಿ · Please wait** (amber) | Mic or voice still getting ready | **Wait — do not speak** |
| **ಕೇಳಿರಿ · Listen** (blue) | Agent is talking; the text is in the white card | **Listen** |
| **ಈಗ ಮಾತನಾಡಿ · Speak now** (green, mic bar moves) | Your turn | **Speak now** |
| **ಕೇಳುತ್ತಿದ್ದೇನೆ · Hearing you** (green) | Your voice is being recorded | Keep speaking, then pause |
| **ಕೇಳಿದೆ ✓ / ಯೋಚಿಸುತ್ತಿದ್ದೇನೆ · Working on it** (violet) | Speech recognised, being processed | Wait |

Under the card, **ನೀವು ಹೇಳಿದ್ದು · You said** shows exactly what the system heard. If it is wrong, just say it again.

**Tips**

- Tap the screen once if no sound (browser audio unlock).
- Wait until the status is **green** before you talk.
- Speak **slowly and clearly**; for account numbers, say **one digit at a time**, pause between digits.
- Stand within the camera frame during the session (leaving for ~14 s ends the session).

---

## 1. Control commands (use anytime)

These work during conversation, form filling, and confirmation.

### Confirm — value is correct

| Kannada | English |
|---------|---------|
| ಸರಿ | yes |
| ಸರಿಯೇ | yes |
| ಹೌದು | yes |
| ಒಪ್ಪಿದೆ | agreed |
| ದೃಢೀಕರಿಸಿ | confirm |

Also: `ok`, `okay`, `correct`, `right`, `yeah`, `yep`

### Reject — say again

| Kannada | English |
|---------|---------|
| ಮತ್ತೆ ಹೇಳಿ | say again |
| ಮತ್ತೆ | again |
| ತಪ್ಪು | wrong |
| ಇಲ್ಲ | no |

Also: `wrong`, `no`, `repeat`, `again`

### Skip optional field

| Kannada | English |
|---------|---------|
| ಬಿಟ್ಟುಬಿಡಿ | skip |
| ಬಿಟ್ಟುಬಿಡು | skip |

Also: `skip`, `none`, `no need`, `leave it`

### End session

| Kannada | English |
|---------|---------|
| ಮುಗಿಸು | finish |
| ಮುಗಿಸಿ | finish |
| ನಿಲ್ಲಿಸು | stop |
| ಮುಗಿದು | done |

Also: `stop`, `end`, `bye`, `goodbye`, `finish`, `thank you bye`

---

## 2. Main banking requests (7 intents)

Say any phrase below when the status is green (the greeting already asked how to help). The welcome card on screen also shows example phrases.

### A. Check balance → opens balance form

| Say in Kannada | Say in English |
|----------------|----------------|
| ನನ್ನ ಖಾತೆ ಬ್ಯಾಲೆನ್ಸ್ ಹೇಳಿ | Tell me my account balance |
| ನನ್ನ ಖಾತೆಯ ಬಾಕಿ ಎಷ್ಟು? | What is my account balance? |
| ಬಾಕಿ ತಿಳಿಸಿ | Tell me my balance |
| ಖಾತೆ ಬಾಕಿ ಪರಿಶೀಲಿಸಿ | Check my account balance |
| ಬ್ಯಾಲೆನ್ಸ್ ಎಷ್ಟು? | What is the balance? |

**What happens:** Agent asks for the **last 4 digits** of the account number → you speak them → confirm → agent speaks the balance in Kannada.  
If two demo accounts share those 4 digits, the agent asks for the **last 6 digits** (see §5). Saying all **10** digits also works.

---

### B. Withdraw money → cash withdrawal slip

| Say in Kannada | Say in English |
|----------------|----------------|
| ಹಣ ಹಿಂಪಡೆಯಬೇಕು | I want to withdraw money |
| ನಗದು ಹಿಂಪಡೆಯಲು ಬೇಕು | I need to withdraw cash |
| ಹಿಂಪಡೆಯುವ ಸ್ಲಿಪ್ ಬೇಕು | Cash withdrawal slip |

Also: `withdraw`, `withdrawal`, `cash withdrawal`, `take cash`

**Fields asked:** Name → Account number → Amount → Purpose (optional) — date is filled automatically

---

### C. Deposit money → deposit slip

| Say in Kannada | Say in English |
|----------------|----------------|
| ಹಣ ಜಮಾ ಮಾಡಬೇಕು | I want to deposit money |
| ನಗದು ಠೇವಣಿ ಮಾಡಬೇಕು | I need to deposit cash |
| ಠೇವಣಿ ಸ್ಲಿಪ್ ಬೇಕು | Deposit slip |

Also: `deposit`, `cash deposit`, `deposit money`

**Fields asked:** Name → Account number → Amount → Deposit mode (cash/cheque) — date automatic

---

### D. Open account → account opening form

| Say in Kannada | Say in English |
|----------------|----------------|
| ಹೊಸ ಖಾತೆ ತೆರೆಯಬೇಕು | I want to open a new account |
| ಸೇವಿಂಗ್ಸ್ ಅಕೌಂಟ್ ತೆರೆಯುವುದು ಹೇಗೆ | How do I open a savings account |
| ಸೇವಿಂಗ್ಸ್ ಖಾತೆ ಬೇಕು | I want a savings account |

Also: `open account`, `new account`, `savings account`, `current account`

**Fields asked:** Full name → Date of birth → Address → Mobile → Account type — date automatic (no PAN)

---

### E. Apply for loan → loan application

| Say in Kannada | Say in English |
|----------------|----------------|
| ಸಾಲಕ್ಕೆ ಅರ್ಜಿ ಸಲ್ಲಿಸಬೇಕು | I want to apply for a loan |
| ಲೋನ್ ಬೇಕು | I need a loan |
| ವೈಯಕ್ತಿಕ ಸಾಲ ಬೇಕು | I want a personal loan |
| ಮನೆ ಸಾಲ ಬೇಕು | I need a home loan |

Also: `loan`, `apply loan`, `personal loan`, `home loan`

**Fields asked:** Name → Mobile → Loan type (home / personal / education / vehicle) → Loan amount → Annual income — date automatic

---

### F. Interest rates & loan repayment (informational — no form)

| Say in Kannada | Say in English |
|----------------|----------------|
| ಬಡ್ಡಿ ದರ ಎಷ್ಟು? | What is the interest rate? |
| ಸೇವಿಂಗ್ಸ್ ಖಾತೆಗೆ ಎಷ್ಟು ಬಡ್ಡಿ? | Savings account interest rate? |
| FD ಬಡ್ಡಿ ದರ ತಿಳಿಸಿ | Fixed deposit interest rate? |
| ಗೃಹ ಸಾಲದ ಬಡ್ಡಿ ಎಷ್ಟು? | What is the home loan interest rate? |
| ಸಾಲದ ಮರುಪಾವತಿ ಮೊತ್ತ ಎಷ್ಟು? | What is my loan repayment amount? |

Also: `interest rate`, `FD rate`, `loan rate`, `repayment`, `repay`

**What happens:** Agent **speaks** from demo data — no form.
- A specific product ("home loan", "FD 1 year") → only that rate.
- A general question → the full rate list.
- Any **repayment / ಮರುಪಾವತಿ** question → the repayment explanation (it does **not** open the loan form).

---

### G. Account information (informational — no form)

| Say in Kannada | Say in English |
|----------------|----------------|
| ಖಾತೆ ಮಾಹಿತಿ ಬೇಕು | I need account information |
| ATM ಕಾರ್ಡ್ ಬ್ಲಾಕ್ ಮಾಡಬೇಕು | I need to block my ATM card |
| ಪಿನ್ ಬದಲಾಯಿಸಬೇಕು | I want to change my PIN |
| ಪಾಸ್‌ಬುಕ್ ಬೇಕು | I need passbook information |
| IFSC ಕೋಡ್ ತಿಳಿಸಿ | What is the IFSC code? |
| ಖಾತೆ ತೆರೆಯಲು ಯಾವ ದಾಖಲೆ ಬೇಕು? | What documents to open account? |

Also: `bank timings`, `statement`, `cheque book`, `internet banking`, `branch`, `PIN`

**What happens:** Agent **speaks** general procedure text (demo). If the request is unclear it asks you to choose — just say it again more clearly.

---

## 3. Form menu (pick from list)

If you want to see or choose from available forms:

| Say in Kannada | Say in English |
|----------------|----------------|
| ಅರ್ಜಿ ತುಂಬಬೇಕು | I want to fill a form |
| ಯಾವ ಅರ್ಜಿಗಳು ಲಭ್ಯ? | What forms are available? |
| ಫಾರ್ಮ್ ಬೇಕು | I need a form |
| ಚೆಕ್‌ಬುಕ್ ಅರ್ಜಿ | Cheque book form |

Also: `fill form`, `form menu`, `list forms`, `application form`

**Then say the number or name:**

| Say | Opens |
|-----|-------|
| ಒಂದು / one / 1 | 1st form in the list |
| ಎರಡು / two / 2 | 2nd form |
| ಮೂರು / three / 3 | 3rd form |
| … up to 10 | … |
| withdraw / ಹಿಂಪಡೆ | Cash withdrawal |
| deposit / ಠೇವಣಿ | Cash deposit |
| loan / ಸಾಲ | Loan application |
| RTGS / NEFT / transfer | Fund transfer form |
| cheque book | Cheque book request |
| ATM card / debit card | ATM/debit card form |
| fixed deposit / FD | Fixed deposit form |
| mobile update | Mobile number change |
| stop cheque | Stop cheque request |

Staff can also open **Admin → Conversation flow** to see intent → form → field questions.

---

## 4. All forms — what the agent will ask

The question appears **once, in large text** in the form card, with a step counter (e.g. **2 / 5**). Answer in voice; confirm with **ಸರಿ** / **ಹೌದು**. The date is always filled automatically (today).

### 4.1 Balance inquiry

| Field | Agent asks (Kannada) | You say |
|-------|----------------------|---------|
| Account number | ದಯವಿಟ್ಟು ನಿಮ್ಮ ಖಾತೆ ಸಂಖ್ಯೆಯ ಕೊನೆಯ ನಾಲ್ಕು ಅಂಕಿಗಳನ್ನು ಹೇಳಿ | Last **4** digits, one by one (e.g. ಏಳು ಎಂಟು ಒಂಬತ್ತು ಸೊನ್ನೆ for 1234567890) |

### 4.2 Cash withdrawal

| Field | You say (example) |
|-------|-------------------|
| Name | ರಾಮೇಶ್ ಕುಮಾರ್ |
| Account | 1234567890 (digit by digit) |
| Amount | ಐದು ಸಾವಿರ / 5000 |
| Purpose (optional) | ವೈಯಕ್ತಿಕ ಬಳಕೆ — or **ಬಿಟ್ಟುಬಿಡಿ** |

### 4.3 Cash / cheque deposit

| Field | You say (example) |
|-------|-------------------|
| Name | ರಾಮೇಶ್ ಕುಮಾರ್ |
| Account | 1234567890 |
| Amount | ಮೂರು ಸಾವಿರ / 3000 |
| Deposit mode | ನಗದು or ಚೆಕ್ |

### 4.4 Open account

| Field | You say (example) |
|-------|-------------------|
| Full name | ನಿಮ್ಮ ಹೆಸರು |
| Date of birth | 15 ಜೂನ್ 1990 — day, month, year |
| Address | ನಿಮ್ಮ ವಿಳಾಸ |
| Mobile | 9876543210 (digit by digit) |
| Account type | ಉಳಿತಾಯ / ಚಾಲ್ತಿ / ವೇತನ |

### 4.5 Loan application

| Field | You say (example) |
|-------|-------------------|
| Name | ನಿಮ್ಮ ಹೆಸರು |
| Mobile | 9876543210 |
| Loan type | ಗೃಹ ಸಾಲ / ವೈಯಕ್ತಿಕ ಸಾಲ / ಶಿಕ್ಷಣ ಸಾಲ / ವಾಹನ ಸಾಲ |
| Loan amount | ಐದು ಲಕ್ಷ |
| Annual income | ಆರು ಲಕ್ಷ |

### 4.6–4.11 Other forms (via form menu)

RTGS/NEFT, cheque book (10 / 25 / 50 leaves), ATM/debit card, FD, mobile update, stop cheque — follow the on-screen question; optional fields can be skipped with **ಬಿಟ್ಟುಬಿಡಿ**.

At the end the agent reads a **summary** and asks **ಹೌದು / ಇಲ್ಲ**. Say **ಹೌದು** → the filled form appears with **Print / Save PDF** (prints only the form). Say **ಇಲ್ಲ** → the form starts again from the first question.

---

## 5. Demo account numbers (balance only)

**Only these 25 accounts return a balance** (`data/demo_accounts.json`, loaded into the sqlite customer store at API start). Any other number → “account not found” in Kannada.

| Account number | Name (Kannada) | Name (EN) | Balance (₹) | Type |
|----------------|----------------|-----------|-------------|------|
| **1234567890** | ರಾಮೇಶ್ ಕುಮಾರ್ | Ramesh Kumar | 45,230.50 | Savings |
| **9876543210** | ಅನಿತಾ ರಾವ್ | Anita Rao | 12,500.00 | Savings |
| **1111222233** ⚠ | ಸುರೇಶ್ ಗೌಡ | Suresh Gowda | 89,340.75 | Current |
| **2222333344** | ಲಕ್ಷ್ಮಿ ದೇವಿ | Lakshmi Devi | 67,890.25 | Savings |
| **5555666677** ⚠ | ಪ್ರಕಾಶ್ ಶೆಟ್ಟಿ | Prakash Shetty | 15,250.00 | Savings |
| **8888999900** ⚠ | ಮೀನಾ ಪಾಟೀಲ್ | Meena Patil | 2,40,075.50 | Current |
| **3456789012** | ವಿಜಯ್ ನಾಯಕ್ | Vijay Naik | 8,750.00 | Savings |
| **4567890123** | ಕವಿತಾ ರೆಡ್ಡಿ | Kavitha Reddy | 1,25,000.00 | Savings |
| **6789012345** | ಮೋಹನ್ ದಾಸ್ | Mohan Das | 32,400.75 | Savings |
| **7890123456** | ಶಾಂತಾ ಕುಮಾರಿ | Shantha Kumari | 56,780.00 | Savings |
| **2345678901** | ರಾಜು ಹೆಗ್ಡೆ | Raju Hegde | 18,920.50 | Savings |
| **3344556677** ⚠ | ಸವಿತಾ ನಾಯಕ್ | Savitha Nayak | 73,500.25 | Current |
| **4455667788** | ಗಿರೀಶ್ ಭಟ್ | Girish Bhat | 9,200.00 | Savings |
| **5566778899** | ಪುಷ್ಪಾ ರಾಣಿ | Pushpa Rani | 41,600.00 | Savings |
| **6677889900** ⚠ | ನಾಗೇಶ್ ಕುಲಕರ್ಣಿ | Nagesh Kulkarni | 1,95,000.00 | Current |
| **7788990011** | ಉಷಾ ದೇವಿ | Usha Devi | 28,350.75 | Savings |
| **8899001122** | ಅಶೋಕ್ ಪಾಟೀಲ್ | Ashok Patil | 6,800.00 | Savings |
| **9900112233** ⚠ | ರೇಖಾ ಶೆಟ್ಟಿ | Rekha Shetty | 84,200.50 | Savings |
| **1122334455** ⚠ | ದಿನೇಶ್ ಕಾಮತ್ | Dinesh Kamath | 3,10,500.00 | Current |
| **2233445566** | ಮಾಲತಿ ಗೌಡ | Malathi Gowda | 22,100.25 | Savings |
| **3322114455** ⚠ | ವೆಂಕಟೇಶ್ ರಾವ್ | Venkatesh Rao | 51,750.00 | Savings |
| **4411223355** | ಗೀತಾ ಕುಮಾರಿ | Geetha Kumari | 14,300.00 | Savings |
| **5500113366** | ಮಂಜುನಾಥ್ ಶೆಟ್ಟಿ | Manjunath Shetty | 97,800.75 | Current |
| **6611224477** | ಸುಮಾ ಬಾಯಿ | Suma Bai | 33,450.00 | Savings |
| **7722335588** | ಕೃಷ್ಣಮೂರ್ತಿ | Krishnamurthy | 5,600.50 | Savings |

⚠ **Shares its last 4 digits with another account** → the agent will ask for the **last 6 digits**:

| Last 4 | Accounts |
|--------|----------|
| 2233 | 1111222233, 9900112233 |
| 6677 | 5555666677, 3344556677 |
| 9900 | 8888999900, 6677889900 |
| 4455 | 1122334455, 3322114455 |

Admin → **Customers** shows the same list + balance lookup audit.

### How to speak account numbers

**Best:** One digit at a time, pause between each.

**Last 4 digits of 1234567890 (Kannada):**
```
ಏಳು · ಎಂಟು · ಒಂಬತ್ತು · ಸೊನ್ನೆ
```

**English:**
```
seven eight nine zero
```

After the agent repeats the number, say **ಸರಿ** or **ಹೌದು**.

---

## 6. How to speak amounts

| Meaning | Kannada example | English example |
|---------|-----------------|-----------------|
| ₹1,000 | ಒಂದು ಸಾವಿರ ರೂಪಾಯಿ | one thousand rupees |
| ₹5,000 | ಐದು ಸಾವಿರ | five thousand |
| ₹10,000 | ಹತ್ತು ಸಾವಿರ | ten thousand |
| ₹50,000 | ಐವತ್ತು ಸಾವಿರ | fifty thousand |
| ₹1,00,000 | ಒಂದು ಲಕ್ಷ | one lakh |
| ₹2,50,000 | ಎರಡು ಲಕ್ಷ ಐವತ್ತು ಸಾವಿರ | two lakh fifty thousand |

You can also say plain digits: `5000`, `five zero zero zero`.

---

## 7. Full demo scripts

### Script A — Balance (1–2 min) ⭐ Best demo

```
1. [Stand in camera — hear greeting; wait for green "Speak now"]
2. You:  ನನ್ನ ಖಾತೆ ಬ್ಯಾಲೆನ್ಸ್ ಹೇಳಿ
3. Agent: asks for the last 4 digits (wait for green again)
4. You:  ಏಳು ಎಂಟು ಒಂಬತ್ತು ಸೊನ್ನೆ        (7890 → Ramesh Kumar)
5. Agent: repeats the digits — confirm?
6. You:  ಹೌದು
7. Agent: speaks balance for ರಾಮೇಶ್ ಕುಮಾರ್ — ₹45,230.50 (also shown on screen)
8. You:  ಮುಗಿಸು   (or tap End)
```

To show the 6-digit follow-up, say **ಎರಡು ಎರಡು ಮೂರು ಮೂರು** (2233) instead → agent asks for 6 digits → say **ಎರಡು ಎರಡು ಎರಡು ಎರಡು ಮೂರು ಮೂರು** (222233) → Suresh Gowda (1111222233).

### Script B — Cash withdrawal (3–4 min)

```
1. You:  ಹಣ ಹಿಂಪಡೆಯಬೇಕು
2. Name:     ರಾಮೇಶ್ ಕುಮಾರ್
3. Account:  1234567890 (digit by digit) → ಹೌದು
4. Amount:   ಐದು ಸಾವಿರ → ಹೌದು
5. Purpose:  ಬಿಟ್ಟುಬಿಡಿ  (skip)
6. Summary:  ಹೌದು
7. [Form preview → Print / Save PDF if needed]
```

### Script C — Interest rates & repayment (1 min)

```
1. You:  ಬಡ್ಡಿ ದರ ಎಷ್ಟು?
2. [Listen — agent speaks savings, FD, loan rates]
3. You:  ಸಾಲದ ಮರುಪಾವತಿ ಮೊತ್ತ ಎಷ್ಟು?
4. [Listen — agent explains how repayment is calculated]
5. You:  ಮುಗಿಸು
```

### Script D — Form menu (2 min)

```
1. You:  ಅರ್ಜಿ ತುಂಬಬೇಕು
2. [Screen shows numbered list]
3. You:  ಎರಡು   (or say "deposit" / "cheque book")
4. [Follow form prompts]
```

---

## 8. What the agent says to you (fixed phrases)

| When | Agent says (Kannada) |
|------|----------------------|
| After greeting (if spoken) | ದಯವಿಟ್ಟು ಹೇಳಿ — ನಿಮಗೆ ಏನು ಸಹಾಯ ಬೇಕು? |
| Confirm field | [your value]. … ಹೌದು ಅಥವಾ ಮತ್ತೆ ಹೇಳಿ |
| Shared last 4 digits | ಹಲವು ಖಾತೆಗಳಿವೆ. ದಯವಿಟ್ಟು ನಿಮ್ಮ ಖಾತೆ ಸಂಖ್ಯೆಯ ಕೊನೆಯ ಆರು ಅಂಕಿಗಳನ್ನು ಹೇಳಿ. |
| Form summary | ನಿಮ್ಮ ಅರ್ಜಿಯ ಸಾರಾಂಶ ಇಲ್ಲಿದೆ. … |
| Summary confirm | ಎಲ್ಲ ಮಾಹಿತಿಯೂ ಸರಿಯಾಗಿದೆಯೇ? … ಹೌದು / ಇಲ್ಲ |
| Could not hear | ದಯವಿಟ್ಟು ಮತ್ತೆ ಹೇಳಿ |

The text always appears on screen **before** the voice plays; while the voice is being prepared the status shows **Please wait**.

---

## 9. Troubleshooting

| Problem | What to do |
|---------|------------|
| No sound | Tap screen once; check volume; hard-refresh browser |
| “API offline” | Start API: `.\scripts\start-kiosk-api.ps1` on port 8000; TTS box must be ready |
| Long **Please wait** before the voice | A new (never-spoken) reply is being generated on the TTS box — usually 4–8 s; repeated replies are instant (cached) |
| **You said** shows the wrong words | Speak again, shorter and slower; use phrases from §2 |
| Wrong intent | Speak a shorter sentence; use phrases from §2 |
| Account not recognized | Use the demo accounts in §5; say the **last 4** digits slowly; if asked, the last **6** |
| Bot hears itself | Wait until the status is green **Speak now** |
| Form stuck | Say **ಮತ್ತೆ ಹೇಳಿ** or **ಮುಗಿಸು** and start again |

---

## 10. Reference — intent → form mapping

| You ask for… | System intent | Form opened |
|--------------|---------------|-------------|
| Balance | `check_balance` | balance_inquiry |
| Withdraw | `withdraw_money` | cash_withdrawal |
| Deposit | `deposit_money` | cash_deposit |
| Open account | `open_account` | open_account |
| Loan | `apply_loan` | apply_loan |
| Interest rates / loan repayment | `interest_rate_query` | *(speaks info only)* |
| Account help | `account_info_query` | *(speaks info only)* |
| Form menu | form_menu route | *(pick from list)* |

Same map is live under **Admin → Conversation flow**.

---

## Related docs

- [DEMO_AND_INTERACTION_GUIDE.md](./DEMO_AND_INTERACTION_GUIDE.md) — startup, admin, troubleshooting
- [DEPLOYMENT.md](./DEPLOYMENT.md) — kiosk + TTS setup
- [END_TO_END_PROJECT_DOCUMENTATION.md](./END_TO_END_PROJECT_DOCUMENTATION.md) — full system doc

---

*Last updated: 2026-10-07 · Matches the redesigned agent conversation screen, `data/demo_accounts.json` (25 accounts), `data/forms.json`, voice commands, and NLU intents.*
