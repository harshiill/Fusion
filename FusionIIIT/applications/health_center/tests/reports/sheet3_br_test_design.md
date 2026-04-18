# Sheet 3 — BR Test Design

| Test ID | BR ID | Category | Input/Action | Expected Result |
|---------|-------|----------|--------------|----------|
| BR-01-V-01 | PHC-BR-01 | Valid | GET schedule as patient | Schedule + status field |
| BR-01-I-01 | PHC-BR-01 | Invalid | Check response structure | Both fields present |
| BR-02-V-01 | PHC-BR-02 | Valid | Patient views own data | Only own prescriptions |
| BR-02-I-01 | PHC-BR-02 | Invalid | Patient cross-access attempt | Access denied or same data |
| BR-03-V-01 | PHC-BR-03 | Valid | Compounder accesses staff endpoint | HTTP 200 |
| BR-03-I-01 | PHC-BR-03 | Invalid | Student accesses staff endpoint | HTTP 403/404 |
| BR-04-V-01 | PHC-BR-04 | Valid | Staff submits medical relief | HTTP 200/201 |
| BR-04-I-01 | PHC-BR-04 | Invalid | Student submits relief | HTTP 403 or blocked |
| BR-05-V-01 | PHC-BR-05 | Valid | Claim with valid prescription | Accepted |
| BR-05-I-01 | PHC-BR-05 | Invalid | Claim with invalid prescription | HTTP 400 or handled |
| BR-06-V-01 | PHC-BR-06 | Valid | Claim within window (15 days) | HTTP 200/201 |
| BR-06-I-01 | PHC-BR-06 | Invalid | Claim outside window (500 days) | HTTP 400/rejected |
| BR-07-V-01 | PHC-BR-07 | Valid | Stock < threshold | Alert created |
| BR-07-I-01 | PHC-BR-07 | Invalid | Stock > threshold | No alert |
| BR-08-V-01 | PHC-BR-08 | Valid | SUBMITTED → PHC_REVIEWED | HTTP 200, transition valid |
| BR-08-I-01 | PHC-BR-08 | Invalid | SANCTIONED → SUBMITTED | HTTP 400 or blocked |
| BR-09-V-01 | PHC-BR-09 | Valid | Create prescription | Audit log exists |
| BR-09-I-01 | PHC-BR-09 | Invalid | No audit found | BR not enforced |
| BR-10-V-01 | PHC-BR-10 | Valid | Fulfill after approval | HTTP 200 |
| BR-10-I-01 | PHC-BR-10 | Invalid | Fulfill without approval | HTTP 400 or blocked |
| BR-11-V-01 | PHC-BR-11 | Valid | Notification on SANCTIONED | Notification created |
| BR-11-I-01 | PHC-BR-11 | Invalid | No notification at SUBMITTED | No notification |

