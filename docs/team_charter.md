# CareFlow Team Charter

## Communication Policy
* **Primary Channel:** [Insert your chat app here, e.g., WhatsApp/Slack]
* **Response Time:** All members must respond to team messages within 24 hours.
* **Absence:** If a member is unresponsive for 48 hours, the Team Lead will report it to the mentor with screenshots as proof. The remaining members continue working and the Work Distribution Document is updated.

## Git Workflow (Updated per Instructor)
* **Rule 1:** Everyone commits strictly to their own assigned branch (`member1-data`, `member2-analysis`, `member3-dashboard`).
* **Rule 2:** NO MERGING to `main` until the final end review.
* **Rule 3:** Commit your work daily to maintain the tracker streak. A valid commit is a real change (code, documentation, configuration, assets). Empty, one-character, duplicated or auto-generated commits do not count.
* **Rule 4:** To use a teammate's file (for example the event log), copy it onto your own branch instead of merging: `git fetch origin`, then `git checkout origin/member1-data -- data/sample_event_log.csv`, then commit it on your branch.
